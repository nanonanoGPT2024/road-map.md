#!/usr/bin/env python3
"""
Lab Exercise: Cloud Native Infrastructure & Observability (Go Simulation)
BAB-09: Cloud-Native-Infrastructure-Observability

This hands-on lab simulates Golang's cloud-native observability patterns:
1. Distributed Tracing (W3C TraceContext, Spans, Hierarchy)
2. Telemetry Metrics (Prometheus-style Counter, Gauge, Histogram)
3. Structured Logging (Zap/Slog pattern with Trace context binding)
4. Kubernetes Health Probes (Liveness & Readiness lifecycle)
"""

import sys
import time
import uuid
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


# --- OpenTelemetry Distributed Tracing Simulation ---
@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    status: str = "OK"

    def finish(self, status: str = "OK"):
        self.end_time = time.time()
        self.status = status

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000


class Tracer:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.spans: List[Span] = []

    def start_span(self, name: str, parent: Optional[Span] = None) -> Span:
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        parent_id = parent.span_id if parent else None
        span = Span(name=name, trace_id=trace_id, span_id=span_id, parent_span_id=parent_id)
        span.attributes["service.name"] = self.service_name
        self.spans.append(span)
        return span


# --- Prometheus Metrics Simulation ---
class PrometheusMetrics:
    def __init__(self):
        self.request_counter: Dict[str, int] = {}
        self.active_goroutines: int = 10
        self.http_duration_buckets = [10, 25, 50, 100, 250, 500, 1000]
        self.http_duration_hist: Dict[int, int] = {b: 0 for b in self.http_duration_buckets}
        self.http_duration_sum: float = 0.0
        self.http_duration_count: int = 0

    def inc_request(self, method: str, path: str, status_code: int):
        key = f'{method}:{path}:{status_code}'
        self.request_counter[key] = self.request_counter.get(key, 0) + 1

    def observe_duration(self, duration_ms: float):
        self.http_duration_sum += duration_ms
        self.http_duration_count += 1
        for b in self.http_duration_buckets:
            if duration_ms <= b:
                self.http_duration_hist[b] += 1

    def scrape_metrics(self) -> str:
        lines = []
        lines.append(f"# HELP http_requests_total Total number of HTTP requests processed")
        lines.append(f"# TYPE http_requests_total counter")
        for key, val in self.request_counter.items():
            method, path, status = key.split(':')
            lines.append(f'http_requests_total{{method="{method}",path="{path}",code="{status}"}} {val}')

        lines.append(f"# HELP go_goroutines Number of active Go routines")
        lines.append(f"# TYPE go_goroutines gauge")
        lines.append(f"go_goroutines {self.active_goroutines}")

        lines.append(f"# HELP http_request_duration_ms Histogram of request durations")
        lines.append(f"# TYPE http_request_duration_ms histogram")
        for b, count in self.http_duration_hist.items():
            lines.append(f'http_request_duration_ms_bucket{{le="{b}"}} {count}')
        lines.append(f'http_request_duration_ms_bucket{{le="+Inf"}} {self.http_duration_count}')
        lines.append(f"http_request_duration_ms_sum {self.http_duration_sum:.2f}")
        lines.append(f"http_request_duration_ms_count {self.http_duration_count}")
        return "\n".join(lines)


# --- Structured Logger Simulation (slog / zap) ---
class StructuredLogger:
    def __init__(self, service: str):
        self.service = service

    def log(self, level: str, msg: str, span: Optional[Span] = None, **kwargs):
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level,
            "service": self.service,
            "msg": msg,
        }
        if span:
            payload["trace_id"] = span.trace_id
            payload["span_id"] = span.span_id
        payload.update(kwargs)

        # Terminal colored output
        color_map = {
            "INFO": Color.GREEN,
            "WARN": Color.YELLOW,
            "ERROR": Color.RED,
            "DEBUG": Color.CYAN
        }
        col = color_map.get(level, Color.WHITE)
        print(f"{col}[{level}]{Color.RESET} {Color.WHITE}{payload['timestamp']}{Color.RESET} - {Color.BOLD}{msg}{Color.RESET}")
        print(f"  {Color.BLUE}↳ JSON Payload:{Color.RESET} {json.dumps(payload)}")


# --- Health & Readiness Probe Engine ---
class KubernetesProbes:
    def __init__(self):
        self.is_alive = True
        self.is_ready = True
        self.db_connected = True
        self.cache_warm = True

    def liveness(self) -> (int, str):
        if self.is_alive:
            return 200, "OK: Process is running healthy"
        return 500, "ERROR: Deadlock detected, pod requires restart"

    def readiness(self) -> (int, str):
        if not self.db_connected:
            return 503, "FAIL: Database connection unavailable"
        if not self.cache_warm:
            return 503, "FAIL: Cache warm-up in progress"
        return 200, "OK: Ready to accept ingress traffic"


# --- Interactive Simulation Orchestration ---
def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}======================================================================
  GOLANG OBSERVABILITY & CLOUD-NATIVE ARCHITECTURE LAB (BAB-09)
  OpenTelemetry (Tracing) | Prometheus (Metrics) | Slog (Logs) | K8s
======================================================================{Color.RESET}
"""
    print(banner)


def run_synthetic_transaction(tracer: Tracer, metrics: PrometheusMetrics, logger: StructuredLogger):
    print(f"\n{Color.YELLOW}[*] Executing Ingress Request: GET /api/v1/orders/create{Color.RESET}")
    root_span = tracer.start_span("HTTP Ingress: /api/v1/orders/create")
    logger.log("INFO", "Incoming HTTP request received", span=root_span, path="/api/v1/orders/create")

    # Simulate Auth Middleware
    time.sleep(0.015)
    auth_span = tracer.start_span("Middleware: AuthenticateJWT", parent=root_span)
    logger.log("DEBUG", "Validating JWT bearer token", span=auth_span)
    auth_span.finish()

    # Simulate Business Logic & Database query
    time.sleep(0.035)
    db_span = tracer.start_span("Repository: SQL ExecContext InsertOrder", parent=root_span)
    logger.log("DEBUG", "Executing PostgreSQL query", span=db_span, query="INSERT INTO orders ...")
    db_span.finish()

    # Finish root span
    root_span.finish()
    duration = root_span.duration_ms
    metrics.inc_request("GET", "/api/v1/orders/create", 200)
    metrics.observe_duration(duration)

    logger.log("INFO", "Request completed successfully", span=root_span, status=200, latency_ms=f"{duration:.2f}")

    print(f"{Color.GREEN}✓ Distributed Trace captured:{Color.RESET}")
    print(f"  TraceID: {Color.BOLD}{root_span.trace_id}{Color.RESET}")
    print(f"  Root SpanID: {root_span.span_id} ({duration:.2f}ms)")
    print(f"  Child Spans: Auth ({auth_span.duration_ms:.2f}ms), DB ({db_span.duration_ms:.2f}ms)")


def display_trace_tree(tracer: Tracer):
    print(f"\n{Color.CYAN}{Color.BOLD}=== OpenTelemetry Trace Explorer ==={Color.RESET}")
    if not tracer.spans:
        print("Belum ada spans yang tercatat. Jalankan transaksi terlebih dahulu.")
        return

    for span in tracer.spans:
        indent = "    " if span.parent_span_id else "  • "
        parent_info = f" (parent: {span.parent_span_id})" if span.parent_span_id else " [ROOT]"
        print(f"{indent}{Color.GREEN}{span.name}{Color.RESET}{parent_info}")
        print(f"    {Color.WHITE}SpanID: {span.span_id} | TraceID: {span.trace_id[:8]}... | Duration: {span.duration_ms:.2f}ms{Color.RESET}")


def main_interactive():
    tracer = Tracer("order-service")
    metrics = PrometheusMetrics()
    logger = StructuredLogger("order-service")
    probes = KubernetesProbes()

    # Initial mock traffic
    for _ in range(3):
        metrics.inc_request("GET", "/healthz", 200)
        metrics.observe_duration(random.uniform(5.0, 18.0))

    while True:
        print_banner()
        print(f"{Color.WHITE}Pilih skenario observability untuk dieksekusi:{Color.RESET}")
        print(f" {Color.BOLD}1.{Color.RESET} Simulasikan Ingress Request (Trace + Metric + Structured Log)")
        print(f" {Color.BOLD}2.{Color.RESET} Tampilkan OpenTelemetry Trace Tree")
        print(f" {Color.BOLD}3.{Color.RESET} Scrape Prometheus /metrics Endpoint (OpenMetrics Format)")
        print(f" {Color.BOLD}4.{Color.RESET} Uji Kubernetes Liveness & Readiness Probes")
        print(f" {Color.BOLD}5.{Color.RESET} Simulasikan Outage Database (Uji Degraded Readiness)")
        print(f" {Color.BOLD}6.{Color.RESET} Reset & Recovery Status Layanan")
        print(f" {Color.BOLD}0.{Color.RESET} Keluar")
        
        choice = input(f"\n{Color.MAGENTA}Input menu [0-6] (default 1): {Color.RESET}").strip()
        if not choice:
            choice = "1"

        if choice == "1":
            run_synthetic_transaction(tracer, metrics, logger)
        elif choice == "2":
            display_trace_tree(tracer)
        elif choice == "3":
            print(f"\n{Color.YELLOW}{Color.BOLD}=== GET /metrics (Prometheus Exporter Output) ==={Color.RESET}")
            print(Color.WHITE + metrics.scrape_metrics() + Color.RESET)
        elif choice == "4":
            print(f"\n{Color.CYAN}{Color.BOLD}=== Kubernetes Health Probe Evaluation ==={Color.RESET}")
            code, msg = probes.liveness()
            col = Color.GREEN if code == 200 else Color.RED
            print(f"  [Liveness Probe  /healthz] -> {col}HTTP {code}{Color.RESET}: {msg}")
            
            code_r, msg_r = probes.readiness()
            col_r = Color.GREEN if code_r == 200 else Color.RED
            print(f"  [Readiness Probe /readyz]   -> {col_r}HTTP {code_r}{Color.RESET}: {msg_r}")
        elif choice == "5":
            probes.db_connected = False
            logger.log("ERROR", "Database connection pool exhausted", None, error="pq: connection refused")
            print(f"{Color.RED}[!] Database ditandai DOWN! Cek kesiapan pod di opsi 4.{Color.RESET}")
        elif choice == "6":
            probes.db_connected = True
            probes.is_alive = True
            probes.cache_warm = True
            logger.log("INFO", "Service health and dependencies restored successfully", None)
            print(f"{Color.GREEN}[✓] Seluruh dependency berhasil dipulihkan.{Color.RESET}")
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah mempelajari Cloud-Native Observability!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid.{Color.RESET}")

        if not sys.stdin.isatty():
            # Non-interactive fallback (e.g. CI / testing pipes)
            break

        input(f"\n{Color.CYAN}Tekan Enter untuk melanjutkan...{Color.RESET}")


if __name__ == "__main__":
    main_interactive()
