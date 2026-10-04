#!/usr/bin/env python3
"""
Enterprise Microservices & Distributed Systems: Resilience4j Circuit Breaker & Distributed Tracing
Simulasi implementasi core pattern Java Enterprise (Spring Cloud / Resilience4j / OpenTelemetry):
1. Finite State Machine (CLOSED, OPEN, HALF_OPEN) dengan Ring Buffer Sliding Window.
2. Context Propagation (TraceId, SpanId) ala Spring Cloud Sleuth / Micrometer Tracing.
3. Fallback Mechanism & Thread-safe Concurrent Execution.
"""

import time
import threading
import random
import uuid
from enum import Enum
from dataclasses import dataclass
from collections import deque
from typing import Callable, Any, Optional, Dict

# ANSI Terminal Colors untuk visualisasi enterprise dashboard
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"


class CircuitState(Enum):
    CLOSED = "CLOSED"        # Normal operation: request diteruskan ke downstream
    OPEN = "OPEN"            # Trip/Fail-Fast: request langsung ditolak/fallback
    HALF_OPEN = "HALF_OPEN"  # Trial state: menguji apakah downstream sudah pulih


@dataclass(frozen=True)
class TraceContext:
    """Representasi W3C Trace Context untuk korelasi log antar microservices."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None

    @staticmethod
    def create_root() -> "TraceContext":
        return TraceContext(
            trace_id=uuid.uuid4().hex[:16],
            span_id=uuid.uuid4().hex[:8],
            parent_span_id=None
        )

    def create_child(self) -> "TraceContext":
        return TraceContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:8],
            parent_span_id=self.span_id
        )


class CallNotPermittedException(Exception):
    """Exception dilempar saat Circuit Breaker berada pada status OPEN."""
    pass


class CircuitBreakerConfig:
    def __init__(
        self,
        sliding_window_size: int = 10,
        failure_rate_threshold: float = 50.0,
        wait_duration_in_open_state: float = 2.0,
        permitted_calls_in_half_open: int = 3
    ):
        self.sliding_window_size = sliding_window_size
        self.failure_rate_threshold = failure_rate_threshold
        self.wait_duration_in_open_state = wait_duration_in_open_state
        self.permitted_calls_in_half_open = permitted_calls_in_half_open


class ResilienceCircuitBreaker:
    """
    Engine Circuit Breaker enterprise thread-safe terinspirasi oleh Resilience4j di ekosistem Java.
    """
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self._state = CircuitState.CLOSED
        self._lock = threading.RLock()
        self._sliding_window: deque = deque(maxlen=config.sliding_window_size)
        self._last_state_change = time.monotonic()
        self._half_open_success_count = 0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            # Otomatis evaluasi transisi OPEN -> HALF_OPEN setelah timeout berakhir
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_state_change
                if elapsed >= self.config.wait_duration_in_open_state:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def _transition_to(self, new_state: CircuitState):
        prev = self._state
        self._state = new_state
        self._last_state_change = time.monotonic()
        
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._sliding_window.clear()

        print(f"{CLR_MAGENTA}[CIRCUIT TRANSITION] {self.name}: "
              f"{CLR_BOLD}{prev.value}{CLR_RESET}{CLR_MAGENTA} -> "
              f"{CLR_BOLD}{new_state.value}{CLR_RESET}")

    def execute(self, action: Callable[[], Any], fallback: Callable[[Exception], Any], ctx: TraceContext) -> Any:
        with self._lock:
            current_state = self.state
            if current_state == CircuitState.OPEN:
                return fallback(CallNotPermittedException("CircuitBreaker is OPEN (Downstream unavailable)"))

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.permitted_calls_in_half_open:
                    return fallback(CallNotPermittedException("Half-Open trial quota exhausted"))
                self._half_open_calls += 1

        # Eksekusi downstream service di luar lock kritis untuk throughput tinggi
        try:
            result = action()
            self._on_success()
            return result
        except Exception as ex:
            self._on_error(ex)
            return fallback(ex)

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_success_count += 1
                if self._half_open_success_count >= self.config.permitted_calls_in_half_open:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._sliding_window.append(True)

    def _on_error(self, ex: Exception):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # 1 kegagalan saat half-open langsung membuka kembali sirkuit
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._sliding_window.append(False)
                if len(self._sliding_window) >= self.config.sliding_window_size:
                    failures = self._sliding_window.count(False)
                    failure_rate = (failures / len(self._sliding_window)) * 100.0
                    if failure_rate >= self.config.failure_rate_threshold:
                        self._transition_to(CircuitState.OPEN)

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._sliding_window)
            failures = self._sliding_window.count(False)
            rate = (failures / total * 100.0) if total > 0 else 0.0
            return {
                "state": self.state.value,
                "buffered_calls": total,
                "failure_rate": rate
            }


# =====================================================================
# Simulasi Microservice Arsitektur Java Enterprise
# =====================================================================

class PaymentGatewayService:
    """Mock downstream service eksternal yang rentan terhadap latency / HTTP 500."""
    def __init__(self):
        self.is_degraded = False

    def process_payment(self, ctx: TraceContext, order_id: str, amount: float) -> str:
        # Simulasi network delay
        time.sleep(0.05)
        if self.is_degraded:
            raise ConnectionResetError("HTTP 503: Payment Gateway upstream connection timed out.")
        return f"TXN_{uuid.uuid4().hex[:6].upper()}_OK"


class OrderProcessingService:
    """Mock Core Service (e.g., Spring Boot Controller + Service layer)."""
    def __init__(self, payment_gateway: PaymentGatewayService):
        self.payment_gateway = payment_gateway
        self.circuit_breaker = ResilienceCircuitBreaker(
            name="PaymentGatewayServiceCB",
            config=CircuitBreakerConfig(
                sliding_window_size=8,
                failure_rate_threshold=50.0,
                wait_duration_in_open_state=1.5,
                permitted_calls_in_half_open=3
            )
        )

    def checkout(self, trace_ctx: TraceContext, order_id: str, amount: float) -> str:
        child_span = trace_ctx.create_child()

        def call_remote():
            return self.payment_gateway.process_payment(child_span, order_id, amount)

        def fallback_handler(ex: Exception):
            # Fallback enterprise: enqueue to Kafka / local Outbox DB table
            return f"QUEUED_FOR_OUTBOX_RETRY [Reason: {ex.__class__.__name__}]"

        result = self.circuit_breaker.execute(call_remote, fallback_handler, child_span)
        return result


def worker_simulate_traffic(order_svc: OrderProcessingService, batch_name: str, num_requests: int):
    """Simulasi konkurensi request HTTP masuk ke endpoint order."""
    for i in range(num_requests):
        root_ctx = TraceContext.create_root()
        order_id = f"ORD-{random.randint(1000, 9999)}"
        res = order_svc.checkout(root_ctx, order_id, 150.0)

        # Log format microservice terdistribusi (TraceId, SpanId, CircuitState, Action)
        metrics = order_svc.circuit_breaker.get_metrics()
        color = CLR_GREEN if "TXN_" in res else CLR_YELLOW
        status_color = CLR_GREEN if metrics['state'] == "CLOSED" else (CLR_RED if metrics['state'] == "OPEN" else CLR_CYAN)

        print(f"[{CLR_BLUE}{batch_name}{CLR_RESET}] "
              f"Trace: {CLR_BOLD}{root_ctx.trace_id[:8]}...{CLR_RESET} | "
              f"State: {status_color}{metrics['state']:<9}{CLR_RESET} | "
              f"FailRate: {metrics['failure_rate']:>5.1f}% | "
              f"Result: {color}{res}{CLR_RESET}")
        time.sleep(0.08)


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}  JAVA ENTERPRISE ARCHITECTURE LAB: RESILIENCE4J & DISTRIBUTED TRACING{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

    payment_gw = PaymentGatewayService()
    order_service = OrderProcessingService(payment_gw)

    print(f"{CLR_BOLD}--- SKENARIO 1: Downstream Sehat (Circuit Breaker CLOSED) ---{CLR_RESET}")
    worker_simulate_traffic(order_service, "Normal-Pool", 8)

    print(f"\n{CLR_BOLD}--- SKENARIO 2: Downstream Padam / HTTP 503 (Memicu Circuit Trip ke OPEN) ---{CLR_RESET}")
    payment_gw.is_degraded = True
    worker_simulate_traffic(order_service, "Failure-Pool", 10)

    print(f"\n{CLR_BOLD}--- SKENARIO 3: Fast-Fail Terjadi Saat OPEN (Pencegahan Cascading Failure) ---{CLR_RESET}")
    # Mengirim request saat circuit masih open; seharusnya di-short-circuit tanpa delay downstream
    start_time = time.monotonic()
    worker_simulate_traffic(order_service, "FastFail-Pool", 4)
    duration = time.monotonic() - start_time
    print(f"{CLR_CYAN}Total durasi short-circuit requests: {duration:.3f} detik (Responsifitas terjaga){CLR_RESET}")

    print(f"\n{CLR_BOLD}--- SKENARIO 4: Downstream Pulih & Pengujian Pemulihan (HALF_OPEN -> CLOSED) ---{CLR_RESET}")
    print(f"{CLR_YELLOW}Menunggu masa sewa Open-State berakhir (1.5s sleep)...{CLR_RESET}")
    time.sleep(1.6)
    payment_gw.is_degraded = False

    # Traffic baru akan memicu HALF_OPEN, menguji 'permitted_calls_in_half_open' (3 request), lalu auto-recover
    worker_simulate_traffic(order_service, "Recovery-Pool", 8)

    final_metrics = order_service.circuit_breaker.get_metrics()
    print(f"\n{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}HASIL EVALUASI METRIK SISTEM:{CLR_RESET}")
    print(f"Status Sirkuit Akhir : {CLR_GREEN}{CLR_BOLD}{final_metrics['state']}{CLR_RESET}")
    print(f"Sample Buffer Aktif  : {final_metrics['buffered_calls']} calls")
    print(f"Kegagalan Berjalan   : {final_metrics['failure_rate']:.1f}%")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")


if __name__ == "__main__":
    main()