#!/usr/bin/env python3
"""
Lab Hands-on: Observabilitas Fondasi (Metrics, Logs, & Traces)
Bab 09 - Modul 02 Deep Dive (01-Core-Foundations / devops-beginner)

Deskripsi:
Script ini mensimulasikan implementasi internal sistem Observabilitas (Three Pillars):
1. Distributed Tracing: Propagasi context (Trace ID, Span ID, Parent Span ID) dan waterfall tree.
2. Structured Logging: JSON log engine yang terikat secara otomatis dengan TraceContext.
3. Telemetry Metrics: Implementasi Counter, Gauge, dan Histogram (P50, P90, P99).
Semua komponen dibangun murni menggunakan standard library Python.
"""

import time
import json
import uuid
import random
import threading
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

# --- ANSI Formatting Helper ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    RED = "\033[31m"
    GRAY = "\033[90m"

# --- 1. DISTRIBUTED TRACING ENGINE ---
@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    status: str = "OK"
    attributes: Dict[str, str] = field(default_factory=dict)

    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000.0

class Tracer:
    """Mengelola siklus hidup Span dan penjejakan konteks per-thread."""
    _thread_local = threading.local()

    def __init__(self):
        self.completed_spans: List[Span] = []
        self._lock = threading.Lock()

    @classmethod
    def get_current_span(cls) -> Optional[Span]:
        stack = getattr(cls._thread_local, 'active_spans', None)
        return stack[-1] if stack else None

    def start_span(self, name: str, trace_id: Optional[str] = None, attributes: Dict[str, str] = None) -> 'SpanContextManager':
        return SpanContextManager(self, name, trace_id, attributes)

    def record_span(self, span: Span):
        with self._lock:
            self.completed_spans.append(span)

class SpanContextManager:
    def __init__(self, tracer: Tracer, name: str, trace_id: Optional[str], attributes: Optional[Dict[str, str]]):
        self.tracer = tracer
        self.name = name
        self.explicit_trace_id = trace_id
        self.attributes = attributes or {}
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        parent = Tracer.get_current_span()
        trace_id = self.explicit_trace_id or (parent.trace_id if parent else uuid.uuid4().hex[:16])
        parent_id = parent.span_id if parent else None
        span_id = uuid.uuid4().hex[:8]

        self.span = Span(
            name=self.name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            attributes=self.attributes
        )
        
        if not hasattr(Tracer._thread_local, 'active_spans'):
            Tracer._thread_local.active_spans = []
        Tracer._thread_local.active_spans.append(self.span)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.span.end_time = time.time()
        if exc_type is not None:
            self.span.status = "ERROR"
            self.span.attributes["error.message"] = str(exc_val)
        
        Tracer._thread_local.active_spans.pop()
        self.tracer.record_span(self.span)
        return False  # Jangan tangkap/supress exception

# --- 2. STRUCTURED LOGGING ENGINE ---
class StructuredLogger:
    """Logger JSON kontekstual yang otomatis menginjeksi trace_id dan span_id."""
    def __init__(self, service_name: str):
        self.service_name = service_name

    def _emit(self, level: str, message: str, **kwargs):
        current_span = Tracer.get_current_span()
        log_payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.", time.gmtime()) + f"{int(time.time()*1000)%1000:03d}Z",
            "service": self.service_name,
            "level": level,
            "message": message,
            "trace_id": current_span.trace_id if current_span else None,
            "span_id": current_span.span_id if current_span else None,
            **kwargs
        }
        color = Color.GREEN if level == "INFO" else (Color.RED if level == "ERROR" else Color.YELLOW)
        print(f"{Color.GRAY}[LOG]{Color.RESET} {color}{json.dumps(log_payload)}{Color.RESET}")

    def info(self, msg: str, **kwargs): self._emit("INFO", msg, **kwargs)
    def warn(self, msg: str, **kwargs): self._emit("WARN", msg, **kwargs)
    def error(self, msg: str, **kwargs): self._emit("ERROR", msg, **kwargs)

# --- 3. METRICS COLLECTOR ---
class MetricsRegistry:
    """Implementasi in-memory metrics: Counter, Gauge, dan Percentile Latency."""
    def __init__(self):
        self._counters = defaultdict(float)
        self._gauges = defaultdict(float)
        self._histograms = defaultdict(list)
        self._lock = threading.Lock()

    def inc_counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        key = self._format_key(name, tags)
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        key = self._format_key(name, tags)
        with self._lock:
            self._gauges[key] = value

    def observe_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        key = self._format_key(name, tags)
        with self._lock:
            self._histograms[key].append(value)

    def _format_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        if not tags:
            return name
        tag_str = ",".join(f'{k}="{v}"' for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"

    def get_summary(self):
        with self._lock:
            counters_copy = dict(self._counters)
            gauges_copy = dict(self._gauges)
            histo_copy = {k: sorted(v) for k, v in self._histograms.items()}

        percentiles = {}
        for key, values in histo_copy.items():
            if values:
                p50 = values[int(len(values) * 0.50)]
                p90 = values[int(len(values) * 0.90)]
                p99 = values[min(int(len(values) * 0.99), len(values)-1)]
                percentiles[key] = {"count": len(values), "p50_ms": p50, "p90_ms": p90, "p99_ms": p99}
        
        return counters_copy, gauges_copy, percentiles

# --- 4. WORKLOAD SIMULATION ---
tracer = Tracer()
logger_gateway = StructuredLogger("api-gateway")
logger_auth = StructuredLogger("auth-service")
logger_db = StructuredLogger("order-database")
metrics = MetricsRegistry()

def call_database(order_id: str):
    with tracer.start_span("database:write_record", attributes={"db.system": "postgresql"}) as span:
        latency = random.uniform(0.010, 0.045)
        time.sleep(latency)
        metrics.observe_histogram("db_query_duration_ms", latency * 1000, {"operation": "INSERT"})
        logger_db.info("Order persistence succeeded", order_id=order_id, duration_ms=round(latency*1000, 2))

def call_auth(user_id: str) -> bool:
    with tracer.start_span("auth:verify_jwt", attributes={"user.id": user_id}) as span:
        time.sleep(random.uniform(0.005, 0.015))
        if user_id == "user_blocked":
            logger_auth.warn("JWT validation failed: User Revoked", user_id=user_id)
            span.status = "UNAUTHENTICATED"
            return False
        logger_auth.info("JWT identity verified", user_id=user_id)
        return True

def handle_http_request(req_id: str, user_id: str, order_id: str):
    metrics.set_gauge("concurrent_active_requests", 1)
    req_start = time.time()
    
    with tracer.start_span("HTTP POST /orders", attributes={"http.method": "POST", "http.route": "/orders"}):
        logger_gateway.info("Incoming checkout request received", request_id=req_id, user_id=user_id)
        
        is_auth = call_auth(user_id)
        if not is_auth:
            metrics.inc_counter("http_requests_total", tags={"status": "401", "endpoint": "/orders"})
            logger_gateway.error("Request rejected by authentication layer", request_id=req_id)
            metrics.set_gauge("concurrent_active_requests", 0)
            return

        call_database(order_id)
        metrics.inc_counter("http_requests_total", tags={"status": "201", "endpoint": "/orders"})
        logger_gateway.info("Checkout request processed successfully", order_id=order_id)
        
    duration = (time.time() - req_start) * 1000.0
    metrics.observe_histogram("http_request_duration_ms", duration, {"endpoint": "/orders"})
    metrics.set_gauge("concurrent_active_requests", 0)

# --- 5. WATERFALL TRACE VISUALIZER ---
def visualize_trace_waterfall(spans: List[Span], trace_id: str):
    """Menyusun tree terstruktur dari spans yang memiliki trace_id yang sama."""
    trace_spans = [s for s in spans if s.trace_id == trace_id]
    if not trace_spans:
        return
    
    trace_spans.sort(key=lambda x: x.start_time)
    root_start = trace_spans[0].start_time
    total_trace_duration = max(s.end_time for s in trace_spans) - root_start

    print(f"\n{Color.BOLD}{Color.CYAN}=== DISTRIBUTED TRACE WATERFALL [TraceID: {trace_id}] ==={Color.RESET}")
    print(f"Total Latency: {total_trace_duration * 1000:.2f} ms | Total Spans: {len(trace_spans)}\n")
    print(f"{'SPAN NAME':<30} {'STATUS':<10} {'OFFSET':<12} {'DURATION':<12} {'TIMELINE (Bar)'}")
    print("-" * 80)

    for span in trace_spans:
        offset_ms = (span.start_time - root_start) * 1000
        dur_ms = span.duration_ms()
        status_color = Color.GREEN if span.status == "OK" else Color.RED
        
        # ASCII timeline generation (scaled to 20 units)
        scale = 20.0 / (total_trace_duration * 1000) if total_trace_duration > 0 else 1
        leading_spaces = int(offset_ms * scale)
        bar_len = max(1, int(dur_ms * scale))
        timeline_bar = " " * leading_spaces + "█" * bar_len

        parent_prefix = "  └── " if span.parent_span_id else "■ "
        span_display = parent_prefix + span.name

        print(f"{span_display:<30} {status_color}{span.status:<10}{Color.RESET} "
              f"{offset_ms:>7.2f} ms   {dur_ms:>7.2f} ms   "
              f"{Color.MAGENTA}{timeline_bar}{Color.RESET}")

# --- 6. MAIN EXECUTION PIPELINE ---
def main():
    print(f"{Color.BOLD}{Color.BLUE}╔════════════════════════════════════════════════════════════════════════╗{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}║     LAB 09: OBSERVABILITY FOUNDATIONS (LOGS, METRICS, TRACES)          ║{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}╚════════════════════════════════════════════════════════════════════════╝{Color.RESET}\n")

    print(f"{Color.YELLOW}[1] MENJALANKAN SIMULASI TRAFFIC MICROSERVICES...{Color.RESET}")
    
    # Skenario 1: Transaksi Normal
    handle_http_request("req-001", "user_alpha", "ord-98231")
    
    # Skenario 2: Transaksi Gagal (Unauthenticated)
    handle_http_request("req-002", "user_blocked", "ord-98232")
    
    # Skenario 3: Transaksi Normal Berulang untuk membentuk histogram
    for i in range(3, 10):
        handle_http_request(f"req-00{i}", "user_beta", f"ord-9823{i}")

    print(f"\n{Color.YELLOW}[2] HASIL COLLECTOR METRICS (Prometheus/StatsD Style):{Color.RESET}")
    counters, gauges, percentiles = metrics.get_summary()
    
    print(f"\n{Color.BOLD}--- Counters ---{Color.RESET}")
    for k, v in counters.items():
        print(f"  metric: {Color.CYAN}{k}{Color.RESET} = {Color.BOLD}{v}{Color.RESET}")

    print(f"\n{Color.BOLD}--- Gauges ---{Color.RESET}")
    for k, v in gauges.items():
        print(f"  metric: {Color.CYAN}{k}{Color.RESET} = {Color.BOLD}{v}{Color.RESET}")

    print(f"\n{Color.BOLD}--- Latency Histograms (Percentiles) ---{Color.RESET}")
    for k, p in percentiles.items():
        print(f"  metric: {Color.CYAN}{k}{Color.RESET} (Samples: {p['count']})")
        print(f"    P50: {p['p50_ms']:.2f} ms | P90: {p['p90_ms']:.2f} ms | P99: {p['p99_ms']:.2f} ms")

    print(f"\n{Color.YELLOW}[3] KORELASI TRACE (Waterfall Analysis):{Color.RESET}")
    # Visualisasikan Trace dari transaksi pertama
    sample_trace_id = tracer.completed_spans[0].trace_id
    visualize_trace_waterfall(tracer.completed_spans, sample_trace_id)
    
    # Visualisasikan Trace dari transaksi yang gagal
    failed_spans = [s for s in tracer.completed_spans if s.status != "OK"]
    if failed_spans:
        visualize_trace_waterfall(tracer.completed_spans, failed_spans[0].trace_id)

    print(f"\n{Color.GREEN}{Color.BOLD}✓ Lab Observabilitas Selesai: Metrik, Log terstruktur, dan Trace berhasil terintegrasi.{Color.RESET}")

if __name__ == "__main__":
    main()