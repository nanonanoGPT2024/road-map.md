#!/usr/bin/env python3
"""
BAB 08: Observabilitas, Monitoring, & Logging
Hands-on Lab Exercise: 3 Pillars of Observability Simulation Engine

Simulasi mandiri interaktif mendemonstrasikan:
1. Metrics (RED Method: Rate, Errors, Duration & Gauges/Counters)
2. Structured Logging (JSON Logging dengan Log Levels & Correlation IDs)
3. Distributed Tracing (Trace ID, Span ID, Parent Span, Latency Propagation)
4. Alerting & SLO/SLI Evaluation Engine
"""

import sys
import time
import json
import uuid
import random
from datetime import datetime, timezone

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BG_BLUE = "\033[44m\033[97m"
BG_RED = "\033[41m\033[97m"

class StructuredLogger:
    """Komponen Pilar 1: Structured Logging dengan Correlation Context"""
    def __init__(self, service_name: str):
        self.service_name = service_name

    def log(self, level: str, message: str, trace_id: str = None, span_id: str = None, **extra):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "level": level,
            "message": message,
            "trace_id": trace_id or "N/A",
            "span_id": span_id or "N/A",
            "context": extra
        }
        color = GREEN if level == "INFO" else (YELLOW if level == "WARN" else RED)
        raw_json = json.dumps(payload)
        print(f"{color}[{level:<5}]{RESET} {CYAN}{payload['timestamp']}{RESET} | {BOLD}{self.service_name}{RESET} | {message}")
        print(f"       {MAGENTA}-> JSON Output:{RESET} {raw_json}")

class MetricsCollector:
    """Komponen Pilar 2: Metrics Collection (RED Method & Resource Gauges)"""
    def __init__(self):
        self.total_requests = 0
        self.error_count = 0
        self.latencies = []
        self.active_connections = 12

    def record_request(self, duration_ms: float, is_error: bool):
        self.total_requests += 1
        if is_error:
            self.error_count += 1
        self.latencies.append(duration_ms)

    def get_summary(self):
        if not self.latencies:
            return {"rate": 0, "error_rate": 0.0, "p95_latency": 0.0}
        
        sorted_latencies = sorted(self.latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]
        error_rate = (self.error_count / self.total_requests) * 100

        return {
            "total_requests": self.total_requests,
            "error_count": self.error_count,
            "error_rate_pct": round(error_rate, 2),
            "avg_latency_ms": round(sum(self.latencies) / len(self.latencies), 2),
            "p95_latency_ms": round(p95_latency, 2),
            "active_connections": self.active_connections
        }

class DistributedTracer:
    """Komponen Pilar 3: Distributed Tracing & Span Hierarchy"""
    def __init__(self):
        self.spans = []

    def start_trace(self) -> str:
        return f"trace-{uuid.uuid4().hex[:12]}"

    def create_span(self, trace_id: str, name: str, parent_id: str = None) -> dict:
        span_id = f"span-{uuid.uuid4().hex[:8]}"
        span = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_id": parent_id,
            "operation": name,
            "start_time": time.time(),
            "duration_ms": 0.0,
            "tags": {}
        }
        return span

    def finish_span(self, span: dict, status: str = "OK", **tags):
        span["duration_ms"] = round((time.time() - span["start_time"]) * 1000, 2)
        span["status"] = status
        span["tags"].update(tags)
        self.spans.append(span)

    def print_trace_waterfall(self, trace_id: str):
        print(f"\n{BOLD}{BG_BLUE} DISTRIBUTED TRACE WATERFALL [{trace_id}] {RESET}\n")
        trace_spans = [s for s in self.spans if s["trace_id"] == trace_id]
        if not trace_spans:
            print("Tidak ada span untuk trace ID ini.")
            return

        min_start = min(s["start_time"] for s in trace_spans)
        for s in trace_spans:
            offset = int((s["start_time"] - min_start) * 200)
            bar_len = max(1, int(s["duration_ms"] / 10))
            indent = "  " if s["parent_id"] else ""
            status_color = GREEN if s["status"] == "OK" else RED
            bar = "=" * bar_len

            print(f"{indent}{CYAN}{s['operation']:<24}{RESET} [{s['span_id']}] -> Parent: {s['parent_id'] or 'ROOT'}")
            print(f"{indent}{' ' * offset}{status_color}[{bar}] {s['duration_ms']}ms ({s['status']}){RESET}")
            if s["tags"]:
                print(f"{indent}  └─ tags: {s['tags']}")

class ObservabilityLab:
    def __init__(self):
        self.logger_gateway = StructuredLogger("api-gateway")
        self.logger_auth = StructuredLogger("auth-service")
        self.logger_db = StructuredLogger("user-db")
        self.metrics = MetricsCollector()
        self.tracer = DistributedTracer()

    def simulate_request(self, request_num: int, force_error: bool = False):
        trace_id = self.tracer.start_trace()
        print(f"\n{BOLD}======================================================================{RESET}")
        print(f"{BOLD} Memproses Transaksi Request #{request_num} | TraceID: {trace_id}{RESET}")
        print(f"{BOLD}======================================================================{RESET}")

        # 1. Root Span: API Gateway
        span_gw = self.tracer.create_span(trace_id, "API-Gateway:POST /api/v1/checkout")
        self.logger_gateway.log("INFO", "Menerima HTTP POST /checkout", trace_id, span_gw["span_id"], http_method="POST")
        time.sleep(random.uniform(0.02, 0.05))

        # 2. Child Span: Auth Service
        span_auth = self.tracer.create_span(trace_id, "Auth-Service:ValidateToken", parent_id=span_gw["span_id"])
        self.logger_auth.log("INFO", "Validasi Bearer JWT token", trace_id, span_auth["span_id"], sub="user_491")
        time.sleep(random.uniform(0.01, 0.03))
        self.tracer.finish_span(span_auth, status="OK", role="customer")

        # 3. Child Span: Database Query
        span_db = self.tracer.create_span(trace_id, "Database:SELECT user_balance", parent_id=span_gw["span_id"])
        db_duration = random.uniform(0.04, 0.09)
        time.sleep(db_duration)

        if force_error:
            self.logger_db.log("ERROR", "Connection Timeout: Database pool exhausted", trace_id, span_db["span_id"], pool_idle=0)
            self.tracer.finish_span(span_db, status="ERROR", error="TimeoutException")
            self.logger_gateway.log("WARN", "Degraded Response: Return HTTP 500", trace_id, span_gw["span_id"], http_status=500)
            self.tracer.finish_span(span_gw, status="ERROR", http_status=500)
            self.metrics.record_request(duration_ms=db_duration * 1000 + 70, is_error=True)
        else:
            self.logger_db.log("INFO", "Query eksekusi berhasil dalam 42ms", trace_id, span_db["span_id"], rows_affected=1)
            self.tracer.finish_span(span_db, status="OK", cache_hit=False)
            self.logger_gateway.log("INFO", "Response Berhasil HTTP 200 OK", trace_id, span_gw["span_id"], http_status=200)
            self.tracer.finish_span(span_gw, status="OK", http_status=200)
            self.metrics.record_request(duration_ms=db_duration * 1000 + 70, is_error=False)

        # Cetak Waterfall Trace
        self.tracer.print_trace_waterfall(trace_id)

    def display_metrics_dashboard(self):
        summary = self.metrics.get_summary()
        print(f"\n{BOLD}{BG_BLUE} REAL-TIME PROMETHEUS/GRAFANA METRICS DASHBOARD {RESET}")
        print(f"Total Transactions : {BOLD}{summary['total_requests']}{RESET}")
        print(f"Failed Transactions: {RED}{summary['error_count']}{RESET}")
        
        # Color coding untuk error rate
        err_color = GREEN if summary['error_rate_pct'] < 5.0 else RED
        print(f"Error Rate (RED)   : {err_color}{summary['error_rate_pct']}%{RESET} (Threshold SLO: < 5.0%)")
        print(f"Avg Latency        : {CYAN}{summary['avg_latency_ms']} ms{RESET}")
        print(f"P95 Latency (RED)  : {YELLOW}{summary['p95_latency_ms']} ms{RESET} (Threshold SLO: < 200ms)")
        print(f"Active Conns (USE) : {MAGENTA}{summary['active_connections']}{RESET}")
        print("----------------------------------------------------------------------")

        # Evaluasi Alert Rules
        if summary['error_rate_pct'] >= 5.0:
            print(f"{BG_RED} [ALERT FIRED] HighErrorRateCritical: Error rate melampaui toleransi SLO! {RESET}")
        else:
            print(f"{GREEN}[ALERT STATUS: HEALTHY] Semua Service Level Objectives (SLO) terpenuhi.{RESET}")

    def run_simulation(self):
        print(f"{BOLD}{GREEN}=== SIMULASI INTERAKTIF OBSERVABILITAS SRE & DEVOPS ==={RESET}")
        print("Menjalankan simulasi traffic mikroservis dan mencatat telemetri...\n")

        # Jalankan beberapa request sukses dan simulasi anomali
        for i in range(1, 5):
            self.simulate_request(request_num=i, force_error=False)
            time.sleep(0.1)

        # Inject Failure untuk memicu logging error, span error, dan alert metrics
        print(f"\n{YELLOW}[INJECTING FAULT] Memicu kegagalan koneksi database untuk menguji observabilitas...{RESET}")
        self.simulate_request(request_num=5, force_error=True)
        self.simulate_request(request_num=6, force_error=True)

        # Tampilkan dashboard metrik gabungan
        self.display_metrics_dashboard()
        print(f"\n{BOLD}{GREEN}[LAB SELESAI] Simulasi pilar observabilitas (Logs, Metrics, Traces) berhasil dijalankan.{RESET}\n")

if __name__ == "__main__":
    lab = ObservabilityLab()
    lab.run_simulation()
