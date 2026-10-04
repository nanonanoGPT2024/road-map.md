#!/usr/bin/env python3
"""
Lab Hands-on: Enterprise Testing, Observability & Delivery (Scala Ecosystem Deep Dive)
Simulasi komprehensif konsep enterprise runtime Scala:
1. Property-Based Testing Engine (Simulasi ScalaCheck: Arbitrary Generator, Invariant Verification, Shrinking).
2. Distributed Tracing & Metrics (Simulasi OpenTelemetry / Kamon untuk Akka/ZIO HTTP).
3. Canary Deployment & Automated Delivery Verification (SLO & Metric Threshold Validation).
"""

import sys
import time
import math
import random
import uuid
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any, Optional, Tuple

# ==============================================================================
# ANSI Color Codes & Logging Helpers
# ==============================================================================
class ANSI:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    GRAY    = "\033[90m"

def log_header(title: str):
    print(f"\n{ANSI.BOLD}{ANSI.MAGENTA}=== [{title.upper()}] ==={ANSI.RESET}")

def log_info(msg: str):
    print(f"{ANSI.CYAN}[INFO]{ANSI.RESET} {msg}")

def log_success(msg: str):
    print(f"{ANSI.GREEN}[PASS]{ANSI.RESET} {msg}")

def log_warn(msg: str):
    print(f"{ANSI.YELLOW}[WARN]{ANSI.RESET} {msg}")

def log_error(msg: str):
    print(f"{ANSI.RED}[FAIL]{ANSI.RESET} {msg}")

# ==============================================================================
# 1. PROPERTY-BASED TESTING (Simulasi ScalaCheck)
# ==============================================================================
class PropertyCheckEngine:
    """
    Simulasi mesin ScalaCheck. Menjalankan evaluasi properti formal matematis
    menggunakan input pseudorandom generator dan mekanisme shrinking otomatis saat gagal.
    """
    @staticmethod
    def generate_int(min_val: int = -1000, max_val: int = 1000) -> int:
        return random.randint(min_val, max_val)

    @staticmethod
    def generate_string(max_len: int = 20) -> str:
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        length = random.randint(0, max_len)
        return "".join(random.choice(chars) for _ in range(length))

    @classmethod
    def shrink_int(cls, counterexample: int, predicate: Callable[[int], bool]) -> int:
        """Mengecilkan nilai counterexample menuju 0 untuk isolasi root-cause."""
        current = counterexample
        step = 1 if current > 0 else -1
        while current != 0:
            next_cand = current - step
            if not predicate(next_cand):
                current = next_cand
            else:
                break
        return current

    @classmethod
    def for_all_ints(cls, name: str, property_fn: Callable[[int], bool], samples: int = 100) -> bool:
        log_info(f"ScalaCheck: Mengevaluasi properti '{name}' ({samples} iterasi)...")
        for i in range(samples):
            val = cls.generate_int()
            if not property_fn(val):
                shrunk = cls.shrink_int(val, property_fn)
                log_error(f"Falsified setelah {i+1} sample! Input awal: {val}, Shrunk Minimal: {shrunk}")
                return False
        log_success(f"Properti '{name}' TERBUKTI valid untuk {samples} sample acak.")
        return True

# ==============================================================================
# 2. OBSERVABILITY ENGINE (Simulasi OpenTelemetry / Kamon)
# ==============================================================================
@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000.0

class MetricsRegistry:
    """Registry Metrik: Mengumpulkan Histograms dan Counters untuk Latency & Traffic."""
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.latencies: List[float] = []

    def increment(self, metric_name: str, delta: int = 1):
        self.counters[metric_name] = self.counters.get(metric_name, 0) + delta

    def record_latency(self, latency_ms: float):
        self.latencies.append(latency_ms)

    def calculate_percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        k = (len(sorted_latencies) - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_latencies[int(k)]
        d0 = sorted_latencies[int(f)] * (c - k)
        d1 = sorted_latencies[int(c)] * (k - f)
        return d0 + d1

class DistributedTracer:
    """Tracer konteks terdistribusi dengan propagasi trace ID antar domain actor."""
    def __init__(self):
        self.spans: List[Span] = []

    def start_span(self, name: str, parent: Optional[Span] = None) -> Span:
        trace_id = parent.trace_id if parent else uuid.uuid4().hex[:16]
        span_id = uuid.uuid4().hex[:8]
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id if parent else None,
            operation_name=name,
            start_time=time.time()
        )
        return span

    def finish_span(self, span: Span, tags: Optional[Dict[str, Any]] = None):
        span.end_time = time.time()
        if tags:
            span.tags.update(tags)
        self.spans.append(span)

# ==============================================================================
# 3. ENTERPRISE SERVICE & CANARY DELIVERY
# ==============================================================================
class OrderProcessingService:
    """Simulasi Enterprise Microservice Scala (ZIO/Akka-Http)."""
    def __init__(self, version: str, failure_rate: float, base_latency_ms: float):
        self.version = version
        self.failure_rate = failure_rate
        self.base_latency_ms = base_latency_ms

    def handle_checkout(self, tracer: DistributedTracer, metrics: MetricsRegistry, user_id: int) -> bool:
        # Parent Span: HTTP Ingress
        root_span = tracer.start_span("HttpRoute.POST /orders/checkout")
        root_span.tags["version"] = self.version
        root_span.tags["user_id"] = user_id

        # Simulasi overhead komputasi/IO
        jitter = random.uniform(-10.0, 45.0)
        simulated_lat = max(5.0, self.base_latency_ms + jitter)
        time.sleep(simulated_lat / 1000.0)

        # Child Span: Database persistence simulation
        db_span = tracer.start_span("SlickDB.executeTransaction", parent=root_span)
        time.sleep(0.008)  # 8ms simulated DB write
        tracer.finish_span(db_span, {"db.table": "orders", "db.status": "OK"})

        # Tentukan status keberhasilan
        is_success = random.random() >= self.failure_rate
        metrics.record_latency(simulated_lat + 8.0)

        if is_success:
            metrics.increment(f"orders.success.{self.version}")
            tracer.finish_span(root_span, {"http.status_code": 200})
            return True
        else:
            metrics.increment(f"orders.failure.{self.version}")
            tracer.finish_span(root_span, {"http.status_code": 500, "error": "InternalDBDeadlock"})
            return False

class CanaryReleaseManager:
    """Memverifikasi SLO (Service Level Objective) sebelum traffic dipromosikan penuh."""
    def __init__(self, target_max_p95_ms: float, target_max_error_rate: float):
        self.target_max_p95_ms = target_max_p95_ms
        self.target_max_error_rate = target_max_error_rate

    def evaluate(self, metrics: MetricsRegistry, version: str) -> bool:
        p95 = metrics.calculate_percentile(95.0)
        success = metrics.counters.get(f"orders.success.{version}", 0)
        failure = metrics.counters.get(f"orders.failure.{version}", 0)
        total = success + failure

        error_rate = (failure / total) if total > 0 else 0.0

        print(f"\n{ANSI.BOLD}Telemetry Audit ({version}):{ANSI.RESET}")
        print(f" - Total Requests : {total}")
        print(f" - Error Rate     : {error_rate * 100:.2f}% (SLO Max: {self.target_max_error_rate * 100:.1f}%)")
        print(f" - P95 Latency    : {p95:.2f} ms (SLO Max: {self.target_max_p95_ms:.2f} ms)")

        passed = (error_rate <= self.target_max_error_rate) and (p95 <= self.target_max_p95_ms)
        if passed:
            log_success(f"Canary {version} memenuhi SLO. Otomatis promosi ke Production!")
        else:
            log_error(f"Canary {version} melanggar SLO! Rollback otomatis dipicu!")
        return passed

# ==============================================================================
# MAIN EXECUTION PIPELINE
# ==============================================================================
def main():
    print(f"{ANSI.BOLD}{ANSI.CYAN}====================================================================")
    print(" LAB: SCALA ENTERPRISE TESTING, OBSERVABILITY & DELIVERY RUNTIME")
    print(f"===================================================================={ANSI.RESET}")

    # -------------------------------------------------------------------------
    # PHASE 1: Property-Based Testing (Formal Invariant Validation)
    # -------------------------------------------------------------------------
    log_header("Fase 1: Enterprise Testing - ScalaCheck Property Verification")

    # Invariant 1: Idempotensi Math Absolute (Harus valid untuk seluruh Z)
    # Catatan edge-case: Python int unbounded, tapi kita tes properti non-negatif.
    prop_non_negative = lambda x: abs(x) >= 0
    PropertyCheckEngine.for_all_ints("Invariant Absolut Non-Negatif", prop_non_negative, samples=150)

    # Invariant 2: Bug Injection: Asumsi salah bahwa perkalian genap selalu menghasilkan nilai > input
    # Akan ditolak oleh counterexample x <= 0 dan dishrink ke 0.
    flawed_property = lambda x: (x * 2) > x
    log_info("Menguji properti cacat untuk memicu algoritma Shrinking ScalaCheck...")
    PropertyCheckEngine.for_all_ints("Invariant Cacat (x * 2 > x)", flawed_property, samples=150)

    # -------------------------------------------------------------------------
    # PHASE 2 & 3: Distributed Tracing, Metrics & Automated Delivery Verification
    # -------------------------------------------------------------------------
    log_header("Fase 2 & 3: Observability (Kamon/OTel) & Canary Deployment")

    tracer = DistributedTracer()
    metrics = MetricsRegistry()
    canary_evaluator = CanaryReleaseManager(target_max_p95_ms=90.0, target_max_error_rate=0.05)

    # Uji Coba Deployment 1: Canary Version v2.4.0-RC1 (Stable Build)
    log_info("Mengalirkan Synthetic Traffic ke Canary Node: [v2.4.0-RC1]...")
    stable_service = OrderProcessingService(version="v2.4.0-RC1", failure_rate=0.02, base_latency_ms=45.0)
    for req_id in range(40):
        stable_service.handle_checkout(tracer, metrics, user_id=1000 + req_id)

    canary_evaluator.evaluate(metrics, "v2.4.0-RC1")

    # Uji Coba Deployment 2: Canary Version v2.4.0-RC2 (Regresi Performa & Error)
    metrics_broken = MetricsRegistry()
    log_info("\nMengalirkan Synthetic Traffic ke Canary Node: [v2.4.0-RC2 (Degraded)]...")
    broken_service = OrderProcessingService(version="v2.4.0-RC2", failure_rate=0.15, base_latency_ms=85.0)
    for req_id in range(40):
        broken_service.handle_checkout(tracer, metrics_broken, user_id=2000 + req_id)

    canary_evaluator.evaluate(metrics_broken, "v2.4.0-RC2")

    # -------------------------------------------------------------------------
    # TRACE VISUALIZATION INSPECTION
    # -------------------------------------------------------------------------
    log_header("Telemetry Trace Waterfall Sampling")
    sample_trace = tracer.spans[-2:] # Ambil 2 span terakhir (child dan parent)
    for s in sample_trace:
        indent = "   " if s.parent_span_id else "-> "
        span_meta = f"TraceID: {s.trace_id} | SpanID: {s.span_id}"
        if s.parent_span_id:
            span_meta += f" | Parent: {s.parent_span_id}"
        print(f"{ANSI.GRAY}{indent}[SPAN]{ANSI.RESET} {ANSI.BOLD}{s.operation_name:<30}{ANSI.RESET} "
              f"| {s.duration_ms:6.2f}ms | {span_meta} | Tags: {s.tags}")

    log_success("Pipeline Verifikasi Enterprise Selesai Tanpa Hambatan Sistem.")

if __name__ == "__main__":
    main()