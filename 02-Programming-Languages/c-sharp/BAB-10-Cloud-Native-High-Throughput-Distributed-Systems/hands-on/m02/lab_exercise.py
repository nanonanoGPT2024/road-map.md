#!/usr/bin/env python3
"""
Lab Hands-on: C# Cloud-Native, High-Throughput & Distributed Systems (Deep Dive)
Simulasi Komputasi:
 - Polly-style Reactive Resilience (Circuit Breaker State Machine & Bulkhead Isolation)
 - Microsoft Orleans-style Virtual Actor Runtime (Grains with Turn-Based Concurrency)
 - System.Threading.Channels Bounded Work Pipeline (Backpressure Simulation)
 - W3C Distributed TraceContext Propagation (TraceID/SpanID correlation)
"""

import time
import uuid
import random
import threading
from enum import Enum
from queue import Queue, Full, Empty
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable

# ============================================================================
# ANSI Color Palette for High-Visibility Telemetry Output
# ============================================================================
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_GRAY    = "\033[90m"

# ============================================================================
# 1. W3C Distributed Tracing (TraceContext Model)
# ============================================================================
@dataclass
class TraceContext:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    sampled: bool = True

    def create_child(self) -> 'TraceContext':
        """Membuat child span context sesuai spesifikasi W3C Distributed Tracing."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:16],
            sampled=self.sampled
        )

    def to_header(self) -> str:
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"


# ============================================================================
# 2. Polly-Style Resilience: Circuit Breaker & Bulkhead Isolation
# ============================================================================
class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    pass

class BulkheadRejectedException(Exception):
    pass

class CircuitBreaker:
    """
    State machine pemutus sirkuit: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.
    Mencegah cascading failures pada downstream cloud dependencies.
    """
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 1.5):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()
        self._lock = threading.Lock()

    def execute(self, action: Callable, *args, **kwargs) -> Any:
        with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change > self.recovery_time_sec:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                else:
                    raise CircuitBreakerOpenException("Circuit is OPEN. Fast-failing downstream call.")

        try:
            result = action(*args, **kwargs)
            with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.last_state_change = time.time()
            return result
        except Exception as ex:
            with self._lock:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.OPEN
                    self.last_state_change = time.time()
            raise ex

class BulkheadIsolation:
    """
    Membatasi concurrency maksimum yang dapat mengakses resource kritis
    menggunakan Semaphore (serupa Polly BulkheadEngine di C#).
    """
    def __init__(self, max_concurrent_calls: int):
        self._semaphore = threading.BoundedSemaphore(max_concurrent_calls)

    def execute(self, action: Callable, *args, **kwargs) -> Any:
        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            raise BulkheadRejectedException("Bulkhead capacity saturated. Execution rejected.")
        try:
            return action(*args, **kwargs)
        finally:
            self._semaphore.release()


# ============================================================================
# 3. Microsoft Orleans-Style Virtual Actor (Grain Runtime)
# ============================================================================
class OrderGrain:
    """
    Virtual Grain: Single-threaded turn-based execution via Mailbox Queue.
    Mempertahankan state in-memory tanpa race condition multi-thread.
    """
    def __init__(self, grain_id: str):
        self.grain_id = grain_id
        self.balance: float = 1000.0
        self.order_history = []
        self._mailbox = Queue()
        self._is_active = True
        self._worker_thread = threading.Thread(target=self._process_mailbox, daemon=True)
        self._worker_thread.start()

    def _process_mailbox(self):
        while self._is_active:
            try:
                task, ctx, response_queue = self._mailbox.get(timeout=0.1)
                try:
                    result = task()
                    response_queue.put((True, result))
                except Exception as ex:
                    response_queue.put((False, ex))
                finally:
                    self._mailbox.task_done()
            except Empty:
                continue

    def post_async(self, action: Callable, ctx: TraceContext) -> Any:
        """Memasukkan invocation ke mailbox turn-based grain runtime."""
        resp_q = Queue()
        self._mailbox.put((action, ctx, resp_q))
        success, value = resp_q.get()
        if success:
            return value
        raise value

    def debit_balance(self, amount: float, order_id: str) -> float:
        if self.balance < amount:
            raise ValueError(f"Insufficient funds: Balance={self.balance}, Requested={amount}")
        self.balance -= amount
        self.order_history.append(order_id)
        # Simulasi disk/memory I/O latency
        time.sleep(0.01)
        return self.balance


# ============================================================================
# 4. System.Threading.Channels Work Pipeline (Backpressure Simulation)
# ============================================================================
@dataclass
class ChannelMessage:
    order_id: str
    customer_id: str
    amount: float
    context: TraceContext

class ChannelPipeline:
    """
    Mensimulasikan Channel<T>.CreateBounded(new BoundedChannelOptions(capacity))
    dengan strategi backpressure (FullMode.Wait / FullMode.DropWrite).
    """
    def __init__(self, capacity: int = 10):
        self._channel = Queue(maxsize=capacity)
        self.processed_counter = 0
        self.rejected_counter = 0
        self._lock = threading.Lock()

    def try_write(self, msg: ChannelMessage) -> bool:
        try:
            self._channel.put(msg, block=False)
            return True
        except Full:
            with self._lock:
                self.rejected_counter += 1
            return False

    def read_message(self, timeout: float = 0.2) -> Optional[ChannelMessage]:
        try:
            return self._channel.get(timeout=timeout)
        except Empty:
            return None

    def mark_done(self):
        self._channel.task_done()
        with self._lock:
            self.processed_counter += 1


# ============================================================================
# 5. Distributed Service Simulation Orchestrator
# ============================================================================
class DistributedMeshOrchestrator:
    def __init__(self):
        self.channel = ChannelPipeline(capacity=12)
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_time_sec=1.0)
        self.bulkhead = BulkheadIsolation(max_concurrent_calls=4)
        self.grains: Dict[str, OrderGrain] = {}
        self.grain_lock = threading.Lock()

    def get_or_activate_grain(self, customer_id: str) -> OrderGrain:
        with self.grain_lock:
            if customer_id not in self.grains:
                self.grains[customer_id] = OrderGrain(customer_id)
            return self.grains[customer_id]

    def _unreliable_payment_gateway(self, amount: float, ctx: TraceContext) -> bool:
        """Simulasi external gateway yang mengalami jitter dan intermittent errors."""
        time.sleep(0.015)
        # Transient failure injection: 25% probabilitas kegagalan
        if random.random() < 0.28:
            raise ConnectionResetError("HTTP/2 503 Service Unavailable (Target Mesh degraded)")
        return True

    def process_order(self, msg: ChannelMessage):
        ctx = msg.context.create_child()
        grain = self.get_or_activate_grain(msg.customer_id)
        status_label = ""
        log_color = CLR_GREEN

        try:
            # Step 1: Bulkhead + Circuit Breaker execution ke Payment Gateway
            def payment_invocation():
                return self.circuit_breaker.execute(
                    self._unreliable_payment_gateway, msg.amount, ctx
                )

            self.bulkhead.execute(payment_invocation)

            # Step 2: Virtual Grain turn-based state modification
            remaining_balance = grain.post_async(
                lambda: grain.debit_balance(msg.amount, msg.order_id), ctx
            )

            status_label = f"SUCCESS (Rem Bal: ${remaining_balance:.2f})"
            log_color = CLR_GREEN

        except BulkheadRejectedException:
            status_label = "REJECTED (Bulkhead saturated)"
            log_color = CLR_YELLOW
        except CircuitBreakerOpenException:
            status_label = f"FAST-FAILED (Circuit: {self.circuit_breaker.state.value})"
            log_color = CLR_RED
        except ConnectionResetError as cre:
            status_label = f"FAILED ({str(cre)[:26]}...)"
            log_color = CLR_MAGENTA
        except ValueError as ve:
            status_label = f"DECLINED ({str(ve)})"
            log_color = CLR_RED

        cb_state_colored = (
            f"{CLR_GREEN}CLOSED{CLR_RESET}" if self.circuit_breaker.state == CircuitState.CLOSED else
            f"{CLR_RED}OPEN{CLR_RESET}" if self.circuit_breaker.state == CircuitState.OPEN else
            f"{CLR_YELLOW}HALF_OPEN{CLR_RESET}"
        )

        print(f"{CLR_GRAY}[{time.strftime('%H:%M:%S.%f')[:-3]}]{CLR_RESET} "
              f"{CLR_CYAN}Trace:{ctx.trace_id[:8]}..{CLR_RESET} | "
              f"Grain:{CLR_BOLD}{msg.customer_id}{CLR_RESET} | "
              f"Order:{msg.order_id} | "
              f"CB:[{cb_state_colored}] -> "
              f"{log_color}{status_label}{CLR_RESET}")


# ============================================================================
# Main Execution Entrypoint
# ============================================================================
def main():
    print(f"\n{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} .NET / C# CLOUD-NATIVE & HIGH-THROUGHPUT DISTRIBUTED RUNTIME LAB{CLR_RESET}")
    print(f"{CLR_GRAY} Architecture: Orleans Grains | Polly Resilience | Bounded Channels | W3C Trace{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}\n")

    orchestrator = DistributedMeshOrchestrator()
    is_running = True

    # Background Consumer Workers (Simulating ThreadPool Tasks)
    def worker_loop(worker_id: int):
        while is_running:
            msg = orchestrator.channel.read_message()
            if msg:
                orchestrator.process_order(msg)
                orchestrator.channel.mark_done()

    threads = []
    for wid in range(3):
        t = threading.Thread(target=worker_loop, args=(wid,), daemon=True)
        t.start()
        threads.append(t)

    # Ingestion Producer (Generating distributed traffic)
    total_requests = 35
    customers = ["cust-alpha", "cust-beta", "cust-gamma", "cust-delta"]

    print(f"{CLR_BOLD}Injecting {total_requests} transactional events into Channel<OrderEvent> pipeline...{CLR_RESET}\n")

    start_time = time.time()
    for i in range(1, total_requests + 1):
        root_context = TraceContext()
        msg = ChannelMessage(
            order_id=f"ORD-{i:03d}",
            customer_id=random.choice(customers),
            amount=random.uniform(50.0, 350.0),
            context=root_context
        )
        
        # C# Channel try-write pattern with backpressure detection
        written = orchestrator.channel.try_write(msg)
        if not written:
            print(f"{CLR_RED}[BACKPRESSURE TRIGGERED] Channel full. Dropped Order: {msg.order_id}{CLR_RESET}")
        
        # Pacing traffic to demonstrate circuit breaker transition windows
        time.sleep(0.04)

    # Allow workers to drain remaining channel messages
    time.sleep(1.8)
    is_running = False
    duration = time.time() - start_time

    # Telemetry Summary Report
    print(f"\n{CLR_BOLD}{CLR_BLUE}=========================== RUNTIME TELEMETRY ==========================={CLR_RESET}")
    print(f" Elapsed Wall Time     : {CLR_BOLD}{duration:.2f}s{CLR_RESET}")
    print(f" Total Ingested Events : {total_requests}")
    print(f" Channel Processed     : {CLR_GREEN}{orchestrator.channel.processed_counter}{CLR_RESET}")
    print(f" Channel Backpressure  : {CLR_RED}{orchestrator.channel.rejected_counter} rejected{CLR_RESET}")
    print(f" Final Circuit State   : {orchestrator.circuit_breaker.state.value}")
    
    print(f"\n{CLR_BOLD}Active Grain In-Memory States (Turn-Based Consistency):{CLR_RESET}")
    for cid, grain in orchestrator.grains.items():
        print(f" -> Grain [{CLR_CYAN}{cid}{CLR_RESET}] | Final Balance: {CLR_GREEN}${grain.balance:.2f}{CLR_RESET} | Processed Transactions: {len(grain.order_history)}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}\n")

if __name__ == "__main__":
    main()