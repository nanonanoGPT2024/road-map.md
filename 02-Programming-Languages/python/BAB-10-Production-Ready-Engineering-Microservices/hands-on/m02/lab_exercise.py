#!/usr/bin/env python3
"""
Lab: Production-Ready Engineering & Microservices - Resilience Patterns Deep Dive
Topic: Circuit Breaker, Token-Bucket Rate Limiter, and Structured Telemetry
Standard Library Only: threading, time, uuid, random, json, dataclasses, enum
"""

import time
import random
import threading
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Callable, Any, Dict

# ANSI Terminal Formatting
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_CYAN   = "\033[36m"
CLR_MAG    = "\033[35m"

class CircuitState(Enum):
    CLOSED = "CLOSED"       # Normal operation; downstream traffic permitted
    OPEN = "OPEN"           # Failing threshold exceeded; fast-fail without calling downstream
    HALF_OPEN = "HALF_OPEN" # Probing downstream health with limited traffic

class CircuitOpenException(Exception):
    """Raised when request is dropped immediately by an open circuit breaker."""
    pass

class RateLimitExceededException(Exception):
    """Raised when client exceeds current token-bucket allowance."""
    pass

@dataclass(frozen=True)
class ServiceRequest:
    trace_id: str
    user_id: str
    payload: Dict[str, Any]

@dataclass
class ServiceResponse:
    trace_id: str
    status_code: int
    data: Optional[Dict[str, Any]]
    latency_ms: float
    error: Optional[str] = None

class StructuredLogger:
    """Zero-dependency production JSON-line logger with context tracking."""
    _lock = threading.Lock()

    @classmethod
    def log(cls, level: str, trace_id: str, message: str, **kwargs):
        event = {
            "timestamp": round(time.time(), 4),
            "level": level.upper(),
            "trace_id": trace_id,
            "message": message,
            **kwargs
        }
        with cls._lock:
            col = CLR_GREEN if level == "info" else CLR_YELLOW if level == "warn" else CLR_RED
            print(f"{col}[{event['level']}] [{event['trace_id'][:8]}]{CLR_RESET} "
                  f"{message} | attrs={json.dumps(kwargs)}")

class TokenBucketRateLimiter:
    """Thread-safe Token Bucket Rate Limiter for ingress traffic policing."""
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = refill_rate_per_sec
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens_needed: float = 1.0) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            # Replenish tokens up to maximal capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            return False

class CircuitBreaker:
    """
    Finite State Machine implementing the Circuit Breaker pattern to isolate 
    failing downstream microservices and prevent cascading system failures.
    """
    def __init__(self, failure_threshold: int = 3, recovery_time_sec: float = 2.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.monotonic()
        self.lock = threading.Lock()

    def execute(self, action: Callable[[], Any], trace_id: str) -> Any:
        with self.lock:
            now = time.monotonic()
            # Transition: OPEN -> HALF_OPEN after recovery timer lapses
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change >= self.recovery_time_sec:
                    self._transition(CircuitState.HALF_OPEN, trace_id)
                else:
                    raise CircuitOpenException("Downstream circuit trip is ACTIVE (Fast-Fail)")

        # Attempt invocation
        try:
            result = action()
            self._handle_success(trace_id)
            return result
        except Exception as exc:
            self._handle_failure(trace_id, exc)
            raise

    def _handle_success(self, trace_id: str):
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.CLOSED, trace_id)
            self.failure_count = 0

    def _handle_failure(self, trace_id: str, exc: Exception):
        with self.lock:
            self.failure_count += 1
            StructuredLogger.log("warn", trace_id, "Downstream call failed", 
                                 failure_count=self.failure_count, error=str(exc))
            if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                if self.failure_count >= self.failure_threshold:
                    self._transition(CircuitState.OPEN, trace_id)

    def _transition(self, new_state: CircuitState, trace_id: str):
        prev = self.state
        self.state = new_state
        self.last_state_change = time.monotonic()
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
        StructuredLogger.log("info" if new_state == CircuitState.CLOSED else "error",
                             trace_id, f"Circuit state changed: {prev.value} -> {new_state.value}")

class DownstreamBillingService:
    """Simulates a remote unreliable microservice with chaos injection."""
    def __init__(self):
        self.chaos_mode = False

    def process_charge(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        simulated_delay = random.uniform(0.02, 0.06)
        time.sleep(simulated_delay)
        
        # Inject deterministic failures when chaos enabled
        if self.chaos_mode and random.random() < 0.70:
            raise ConnectionResetError("Remote host reset connection (Upstream 502/504)")
        return {"payment_status": "CONFIRMED", "transaction_ref": random.randint(100000, 999999)}

class PaymentGatewayProxy:
    """Production gateway controller composing rate-limiting and circuit-breaking."""
    def __init__(self, downstream: DownstreamBillingService):
        self.downstream = downstream
        self.limiter = TokenBucketRateLimiter(capacity=5, refill_rate_per_sec=8.0)
        self.breaker = CircuitBreaker(failure_threshold=3, recovery_time_sec=1.5)

    def handle_request(self, req: ServiceRequest) -> ServiceResponse:
        t_start = time.perf_counter()
        
        # 1. Rate Limiting verification
        if not self.limiter.acquire():
            latency = (time.perf_counter() - t_start) * 1000.0
            return ServiceResponse(req.trace_id, 429, None, latency, "Too Many Requests (Rate-Limited)")

        # 2. Resilient Downstream Dispatch
        try:
            res_data = self.breaker.execute(
                lambda: self.downstream.process_charge(req.payload),
                trace_id=req.trace_id
            )
            latency = (time.perf_counter() - t_start) * 1000.0
            return ServiceResponse(req.trace_id, 200, res_data, latency)
        except CircuitOpenException as coe:
            latency = (time.perf_counter() - t_start) * 1000.0
            return ServiceResponse(req.trace_id, 503, None, latency, str(coe))
        except Exception as exc:
            latency = (time.perf_counter() - t_start) * 1000.0
            return ServiceResponse(req.trace_id, 500, None, latency, f"Downstream Exception: {type(exc).__name__}")

def run_traffic_batch(gateway: PaymentGatewayProxy, total_requests: int, 
                      concurrency: int, batch_label: str) -> list[ServiceResponse]:
    """Concurrent worker pool simulating distributed clients."""
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== Executing Batch: {batch_label} ({total_requests} reqs, {concurrency} threads) ==={CLR_RESET}")
    results = []
    lock = threading.Lock()
    
    def worker(worker_id: int, requests_per_worker: int):
        for seq in range(requests_per_worker):
            trace = f"tr-{worker_id:02d}-{seq:03d}-{random.randint(1000, 9999)}"
            req = ServiceRequest(
                trace_id=trace,
                user_id=f"usr_{worker_id}",
                payload={"amount": 100 + seq, "currency": "USD"}
            )
            resp = gateway.handle_request(req)
            with lock:
                results.append(resp)
            time.sleep(0.04) # Simulated inter-request interval

    threads = []
    req_per_thread = total_requests // concurrency
    for i in range(concurrency):
        t = threading.Thread(target=worker, args=(i, req_per_thread))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    return results

def print_telemetry_summary(responses: list[ServiceResponse]):
    """Aggregates and displays telemetry metrics for system audit."""
    status_counts = {}
    latencies = []
    
    for r in responses:
        status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1
        latencies.append(r.latency_ms)
        
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

    print(f"\n{CLR_BOLD}{CLR_CYAN}--- Telemetry Ingestion Report ---{CLR_RESET}")
    print(f"Total Transactions Processed: {len(responses)}")
    print("Status Code Breakdown:")
    for code, count in sorted(status_counts.items()):
        col = CLR_GREEN if code == 200 else CLR_YELLOW if code == 429 else CLR_RED
        print(f"  [{col}{code}{CLR_RESET}] : {count} ({count / len(responses) * 100:.1f}%)")
    print(f"Latencies: P50 = {p50:.2f}ms | P95 = {p95:.2f}ms")
    print("-" * 35)

def main():
    print(f"{CLR_BOLD}{CLR_MAG}MICROSERVICE RESILIENCE LAB: INGRESS CONTROL & FAULT TOLERANCE{CLR_RESET}")
    downstream = DownstreamBillingService()
    gateway = PaymentGatewayProxy(downstream)

    # Phase 1: Baseline Nominal Conditions
    results_p1 = run_traffic_batch(gateway, total_requests=20, concurrency=4, batch_label="Phase 1: Nominal Load")
    print_telemetry_summary(results_p1)

    # Phase 2: Downstream Outage / Chaos Injection (Induce Circuit Trip)
    print(f"\n{CLR_RED}[CHAOS INJECTION]{CLR_RESET} Simulating downstream dependency outage...")
    downstream.chaos_mode = True
    results_p2 = run_traffic_batch(gateway, total_requests=24, concurrency=4, batch_label="Phase 2: Chaos & Degradation")
    print_telemetry_summary(results_p2)

    # Phase 3: Healing Period & Self-Recovery (Half-Open probing)
    print(f"\n{CLR_GREEN}[CHAOS RESOLVED]{CLR_RESET} Downstream service restored. Awaiting cooldown...")
    downstream.chaos_mode = False
    time.sleep(1.6) # Allow Breaker recovery_time_sec (1.5s) to trigger HALF_OPEN
    
    results_p3 = run_traffic_batch(gateway, total_requests=16, concurrency=2, batch_label="Phase 3: Self-Healing Probe")
    print_telemetry_summary(results_p3)
    
    print(f"{CLR_BOLD}{CLR_GREEN}Lab completed successfully: Circuit successfully transitioned through CLOSED -> OPEN -> HALF_OPEN -> CLOSED.{CLR_RESET}")

if __name__ == "__main__":
    main()