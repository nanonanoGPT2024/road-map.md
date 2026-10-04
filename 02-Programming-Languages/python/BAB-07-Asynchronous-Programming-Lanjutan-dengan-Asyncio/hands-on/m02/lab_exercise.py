#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Asyncio Architecture - Resilient Pipeline Engine
Bab 07: Asynchronous Programming Lanjutan dengan Asyncio (Deep Dive)

Komponen Inti:
1. Context-propagating Async Execution (ContextVars tracing)
2. Token Bucket Rate Limiter terkoordinasi (Concurrency Governor)
3. Three-State Asynchronous Circuit Breaker (CLOSED, OPEN, HALF-OPEN)
4. Worker Pool Terdistribusi berbasis Asyncio PriorityQueue
5. Graceful Cancellation & Structured Exception Handling
"""

import asyncio
import contextvars
import dataclasses
import enum
import random
import sys
import time
from typing import Any, Dict, List, Optional

# ANSI Color Codes untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"

# ContextVar untuk pelacakan transaksi antar-coroutine boundary
trace_context: contextvars.ContextVar[str] = contextvars.ContextVar("trace_context", default="SYSTEM")


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"      # Normal operation: traffic flows through
    OPEN = "OPEN"          # Tripped: fail-fast mode, traffic blocked
    HALF_OPEN = "HALF_OPEN"  # Testing downstream recovery


@dataclasses.dataclass(order=True)
class PriorityTask:
    priority: int
    created_at: float = dataclasses.field(compare=False)
    task_id: str = dataclasses.field(compare=False)
    payload: Dict[str, Any] = dataclasses.field(compare=False)
    retries: int = dataclasses.field(default=0, compare=False)


class AsyncCircuitBreaker:
    """
    State machine pemutus sirkuit non-blocking untuk memitigasi kegagalan kaskade.
    Transisi otomatis: CLOSED -> (failures >= threshold) -> OPEN -> (cooldown) -> HALF-OPEN -> CLOSED
    """
    def __init__(self, failure_threshold: int = 3, recovery_time: float = 2.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            if self.state == CircuitState.OPEN:
                if now - self.last_failure_time >= self.recovery_time:
                    self.state = CircuitState.HALF_OPEN
                    print(f"{CLR_YELLOW}⚡ [CIRCUIT] State transitioning to HALF-OPEN (Canary probe active){CLR_RESET}")
                    return True
                return False
            return True

    async def record_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                print(f"{CLR_GREEN}✔ [CIRCUIT] Recovery verified! State reset to CLOSED.{CLR_RESET}")
            self.state = CircuitState.CLOSED
            self.failure_count = 0

    async def record_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN) and self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                print(f"{CLR_RED}✖ [CIRCUIT] Threshold exceeded! Circuit tripped to OPEN. Downstream isolation enabled.{CLR_RESET}")


class TokenBucketRateLimiter:
    """
    Rate Limiter non-blocking berbasis leaky-bucket / token bucket algorithm.
    Memastikan dispatch rate tidak melebihi alokasi RPS yang diizinkan.
    """
    def __init__(self, rate_limit: float, capacity: float):
        self.rate = rate_limit  # Token generated per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                # Hitung waktu tunggu hingga token berikutnya tersedia
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)


class ResilientAsyncPipeline:
    """
    Pipeline engine yang mengelola ingest queue, pool concurrent workers,
    circuit breaker downstream, dan rate-limiting throttle.
    """
    def __init__(self, worker_concurrency: int, rps_limit: float):
        self.worker_concurrency = worker_concurrency
        self.queue: asyncio.PriorityQueue[PriorityTask] = asyncio.PriorityQueue()
        self.circuit_breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_time=1.5)
        self.rate_limiter = TokenBucketRateLimiter(rate_limit=rps_limit, capacity=rps_limit)
        self.workers: List[asyncio.Task] = []
        self.metrics = {"processed": 0, "failed": 0, "retried": 0, "short_circuited": 0}
        self._shutdown_event = asyncio.Event()

    async def _mock_remote_service(self, task: PriorityTask) -> str:
        """
        Simulasi downstream remote call yang flappy (memiliki latensi dan kegagalan sporadis).
        """
        await asyncio.sleep(random.uniform(0.05, 0.15))
        # Simulasi fault injection berdasarkan payload
        if task.payload.get("chaos_trigger", False):
            raise ConnectionResetError("Remote Peer Dropped Connection (Fault Injected)")
        return f"ACK:OK:{task.task_id}"

    async def _worker_loop(self, worker_id: int):
        """
        Loop eksekusi utama worker consumer dengan context tracing dan retry handling.
        """
        while not self._shutdown_event.is_set():
            try:
                # Polling queue dengan timeout agar thread worker dapat mengevaluasi shutdown signal
                task: PriorityTask = await asyncio.wait_for(self.queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Binding contextvar unik untuk tracing per execution scope
            trace_token = trace_context.set(f"TX-{task.task_id}")
            tid = trace_context.get()

            try:
                # 1. Throttle dengan Rate Limiter
                await self.rate_limiter.acquire()

                # 2. Validasi via Circuit Breaker
                if not await self.circuit_breaker.can_execute():
                    print(f"{CLR_MAGENTA}[W-{worker_id:02d}][{tid}] Fast-Fail: Circuit Breaker OPEN. Re-queuing...{CLR_RESET}")
                    self.metrics["short_circuited"] += 1
                    # Penalti backoff sebelum task di-requeue
                    await asyncio.sleep(0.1)
                    await self.queue.put(task)
                    self.queue.task_done()
                    continue

                # 3. Eksekusi I/O ke Downstream Service
                result = await self._mock_remote_service(task)
                await self.circuit_breaker.record_success()
                self.metrics["processed"] += 1
                print(f"{CLR_GREEN}✔ [W-{worker_id:02d}][{tid}] Processed [Prio: {task.priority}] -> {result}{CLR_RESET}")

            except ConnectionResetError as ex:
                await self.circuit_breaker.record_failure()
                if task.retries < 2:
                    task.retries += 1
                    task.priority += 1  # Degradasi prioritas pada retry
                    self.metrics["retried"] += 1
                    print(f"{CLR_YELLOW}⚠ [W-{worker_id:02d}][{tid}] Failed ({ex}). Scheduling Retry #{task.retries}...{CLR_RESET}")
                    # Hilangkan flag chaos pada retry terakhir untuk memverifikasi recovery
                    if task.retries == 2:
                        task.payload["chaos_trigger"] = False
                    await self.queue.put(task)
                else:
                    self.metrics["failed"] += 1
                    print(f"{CLR_RED}✖ [W-{worker_id:02d}][{tid}] Max Retries Exhausted. Sent to Dead Letter Channel.{CLR_RESET}")
            except Exception as unhandled:
                self.metrics["failed"] += 1
                print(f"{CLR_RED}✖ [W-{worker_id:02d}][{tid}] Unhandled Fault: {unhandled}{CLR_RESET}")
            finally:
                trace_context.reset(trace_token)
                self.queue.task_done()

    async def ingest(self, priority: int, task_id: str, payload: Dict[str, Any]):
        """Menambahkan task baru ke PriorityQueue secara non-blocking."""
        item = PriorityTask(priority=priority, created_at=time.time(), task_id=task_id, payload=payload)
        await self.queue.put(item)

    async def start(self):
        """Inisialisasi concurrent worker pool."""
        self.workers = [
            asyncio.create_task(self._worker_loop(i + 1), name=f"PipelineWorker-{i+1}")
            for i in range(self.worker_concurrency)
        ]

    async def stop(self):
        """Graceful shutdown sequence: tunggu queue kosong lalu hentikan workers."""
        await self.queue.join()
        self._shutdown_event.set()
        for w in self.workers:
            w.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)


async def main():
    print(f"{CLR_BOLD}{CLR_CYAN}====================================================================")
    print(" LAB HANDS-ON: ADVANCED ASYNCIO ARCHITECTURE & RESILIENCE PATTERNS")
    print(f"===================================================================={CLR_RESET}")

    worker_count = 4
    rps_limit = 20.0
    pipeline = ResilientAsyncPipeline(worker_concurrency=worker_count, rps_limit=rps_limit)

    print(f"{CLR_BLUE}[SYSTEM] Bootstrapping Worker Pool: {worker_count} concurrent tasks.{CLR_RESET}")
    print(f"{CLR_BLUE}[SYSTEM] Governor Active: Rate Limiter at {rps_limit} RPS.{CLR_RESET}\n")

    await pipeline.start()
    start_time = time.perf_counter()

    # Dispatch workload simulasi: Berbagai macam prioritas & fault injection
    print(f"{CLR_BOLD}[PRODUCER] Menghasilkan 24 task beban kerja heterogen...{CLR_RESET}")
    for i in range(1, 25):
        # Setiap kelipatan 6 disisipkan chaos trigger untuk memicu trip pada circuit breaker
        is_chaos = (i % 6 == 0)
        # Prioritas: 1 (Tinggi), 5 (Sedang), 10 (Rendah)
        prio = 1 if i % 3 == 0 else (5 if i % 2 == 0 else 10)
        
        await pipeline.ingest(
            priority=prio,
            task_id=f"REQ-{i:03d}",
            payload={"chaos_trigger": is_chaos, "payload_bytes": random.randint(128, 1024)}
        )
        # Ingestion burst cepat
        await asyncio.sleep(0.02)

    print(f"{CLR_YELLOW}[PRODUCER] Seluruh task berhasil di-enqueue. Menunggu pemrosesan worker...{CLR_RESET}\n")

    # Tunggu seluruh proses selesai dan lakukan shutdown terstruktur
    await pipeline.stop()
    total_duration = time.perf_counter() - start_time

    # Output Metrik Lab
    print(f"\n{CLR_BOLD}{CLR_CYAN}====================================================================")
    print(" PIPELINE EXECUTION TELEMETRY SUMMARY")
    print(f"===================================================================={CLR_RESET}")
    print(f" Total Runtime          : {CLR_BOLD}{total_duration:.3f} s{CLR_RESET}")
    print(f" Tasks Processed (ACK)  : {CLR_GREEN}{pipeline.metrics['processed']}{CLR_RESET}")
    print(f" Re-queued / Retried    : {CLR_YELLOW}{pipeline.metrics['retried']}{CLR_RESET}")
    print(f" Circuit Breaker Blocks : {CLR_MAGENTA}{pipeline.metrics['short_circuited']}{CLR_RESET}")
    print(f" Dead Letter / Dropped  : {CLR_RED}{pipeline.metrics['failed']}{CLR_RESET}")
    effective_tps = (pipeline.metrics['processed'] + pipeline.metrics['failed']) / total_duration
    print(f" Effective Throughput   : {CLR_BOLD}{effective_tps:.2f} tasks/sec{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}===================================================================={CLR_RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}[ABORT] Eksekusi dihentikan manual oleh user.{CLR_RESET}")
        sys.exit(130)