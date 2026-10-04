#!/usr/bin/env python3
"""
Lab Exercise: Fondasi Observabilitas (Metrics, Logs, Traces)
BAB-09 DevOps Beginner

Simulasi interaktif 3 pilar observabilitas:
1. Metrics (Counter, Gauge, Histogram/Latency)
2. Structured Logging (JSON + Correlation IDs)
3. Distributed Tracing (Trace ID, Span ID, Hierarchy, Latency)
"""

import sys
import time
import uuid
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"

# -------------------------------------------------------------
# 1. PILLAR: METRICS
# -------------------------------------------------------------
class MetricsRegistry:
    def __init__(self):
        self.request_counter: Dict[str, int] = {"200": 0, "400": 0, "500": 0}
        self.active_workers: int = 5
        self.latencies_ms: List[float] = []

    def record_request(self, status_code: int, latency_ms: float):
        status_key = str(status_code)
        if status_key in self.request_counter:
            self.request_counter[status_key] += 1
        else:
            self.request_counter[status_key] = 1
        self.latencies_ms.append(latency_ms)

    def set_active_workers(self, count: int):
        self.active_workers = count

    def get_summary(self) -> Dict[str, float]:
        total_reqs = sum(self.request_counter.values())
        avg_lat = sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0
        p95_lat = 0.0
        if self.latencies_ms:
            sorted_lat = sorted(self.latencies_ms)
            p95_idx = int(0.95 * len(sorted_lat))
            p95_lat = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]

        return {
            "total_requests": total_reqs,
            "error_500": self.request_counter.get("500", 0),
            "avg_latency": avg_lat,
            "p95_latency": p95_lat,
            "active_workers": self.active_workers
        }

# -------------------------------------------------------------
# 2. PILLAR: DISTRIBUTED TRACING
# -------------------------------------------------------------
@dataclass
class Span:
    trace_id: str
    span_id: str
    name: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    status: str = "OK"  # "OK" or "ERROR"
    tags: Dict[str, str] = field(default_factory=dict)

class Tracer:
    def __init__(self):
        self.spans: List[Span] = []

    def create_trace_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def create_span_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def record_span(self, span: Span):
        self.spans.append(span)

# -------------------------------------------------------------
# 3. PILLAR: STRUCTURED LOGGING
# -------------------------------------------------------------
class Logger:
    def __init__(self):
        self.logs: List[Dict] = []

    def emit(self, level: str, message: str, trace_id: str, span_id: str, **kwargs):
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
            "level": level.upper(),
            "message": message,
            "trace_id": trace_id,
            "span_id": span_id,
            **kwargs
        }
        self.logs.append(log_entry)
        return log_entry

# -------------------------------------------------------------
# SIMULATED APPLICATION SERVICES
# -------------------------------------------------------------
class ECommerceSimulator:
    def __init__(self):
        self.metrics = MetricsRegistry()
        self.tracer = Tracer()
        self.logger = Logger()

    def process_order(self, customer_id: str, force_anomaly: bool = False):
        trace_id = self.tracer.create_trace_id()
        
        # 1. API Gateway Span
        gw_span_id = self.tracer.create_span_id()
        gw_span = Span(
            trace_id=trace_id,
            span_id=gw_span_id,
            name="API-Gateway::POST /orders",
            tags={"http.method": "POST", "http.route": "/orders"}
        )
        
        self.logger.emit("INFO", f"Request received for customer {customer_id}", trace_id, gw_span_id, route="/orders")
        
        # 2. Auth Service Span (Child of Gateway)
        auth_span_id = self.tracer.create_span_id()
        auth_span = Span(
            trace_id=trace_id,
            span_id=auth_span_id,
            name="AuthService::validateToken",
            parent_span_id=gw_span_id
        )
        t0 = time.time()
        time.sleep(random.uniform(0.02, 0.05))
        auth_span.duration_ms = (time.time() - t0) * 1000
        self.tracer.record_span(auth_span)
        self.logger.emit("DEBUG", "JWT Token validated successfully", trace_id, auth_span_id, user_role="buyer")

        # 3. Order Processing Service Span (Child of Gateway)
        order_span_id = self.tracer.create_span_id()
        order_span = Span(
            trace_id=trace_id,
            span_id=order_span_id,
            name="OrderService::createOrderRecord",
            parent_span_id=gw_span_id
        )

        # 4. Database Query Span (Child of OrderService)
        db_span_id = self.tracer.create_span_id()
        db_span = Span(
            trace_id=trace_id,
            span_id=db_span_id,
            name="PostgreSQL::INSERT orders",
            parent_span_id=order_span_id,
            tags={"db.system": "postgresql", "db.table": "orders"}
        )

        t_db = time.time()
        if force_anomaly:
            # Anomaly: Database timeout / deadlock
            time.sleep(0.25)
            db_span.status = "ERROR"
            db_span.tags["error.message"] = "QueryTimeout: lock wait timeout exceeded"
            db_span.duration_ms = (time.time() - t_db) * 1000
            self.tracer.record_span(db_span)

            order_span.status = "ERROR"
            order_span.duration_ms = db_span.duration_ms + 10
            self.tracer.record_span(order_span)

            gw_span.status = "ERROR"
            gw_span.duration_ms = order_span.duration_ms + auth_span.duration_ms + 5
            self.tracer.record_span(gw_span)

            self.logger.emit("ERROR", "Database transaction failed on table orders", trace_id, db_span_id, error="lock_wait_timeout")
            self.logger.emit("ERROR", "Order creation aborted with HTTP 500", trace_id, gw_span_id, status_code=500)
            
            self.metrics.record_request(500, gw_span.duration_ms)
            return False, trace_id, gw_span.duration_ms
        else:
            time.sleep(random.uniform(0.04, 0.08))
            db_span.duration_ms = (time.time() - t_db) * 1000
            self.tracer.record_span(db_span)

            order_span.duration_ms = db_span.duration_ms + random.uniform(5, 15)
            self.tracer.record_span(order_span)

            gw_span.duration_ms = order_span.duration_ms + auth_span.duration_ms + random.uniform(5, 10)
            self.tracer.record_span(gw_span)

            self.logger.emit("INFO", "Order row inserted into DB", trace_id, db_span_id, rows_affected=1)
            self.logger.emit("INFO", "Order processed successfully (HTTP 200)", trace_id, gw_span_id, status_code=200)

            self.metrics.record_request(200, gw_span.duration_ms)
            return True, trace_id, gw_span.duration_ms

# -------------------------------------------------------------
# INTERACTIVE CLI VIEW
# -------------------------------------------------------------
def display_header():
    print(f"\n{BOLD}{CYAN}=================================================================={RESET}")
    print(f"{BOLD}{BG_BLUE}{WHITE}  SIMULATOR OBSERVABILITAS: METRICS, LOGS & TRACES (BAB-09)      {RESET}")
    print(f"{BOLD}{CYAN}=================================================================={RESET}")

def render_metrics_dashboard(metrics: MetricsRegistry):
    summary = metrics.get_summary()
    print(f"\n{BOLD}{YELLOW}[1. METRICS DASHBOARD (AGGREGATION)]{RESET}")
    print(f"┌─────────────────────────────┬──────────────────────────┐")
    print(f"│ Metric Name                 │ Value                    │")
    print(f"├─────────────────────────────┼──────────────────────────┤")
    print(f"│ total_http_requests (Count) │ {summary['total_requests']:<24} │")
    
    err_color = RED if summary['error_500'] > 0 else GREEN
    print(f"│ http_errors_500     (Count) │ {err_color}{summary['error_500']:<24}{RESET} │")
    print(f"│ active_worker_pool  (Gauge) │ {summary['active_workers']:<24} │")
    print(f"│ avg_latency_ms  (Histogram) │ {summary['avg_latency']:<21.2f} ms │")
    print(f"│ p95_latency_ms  (Histogram) │ {summary['p95_latency']:<21.2f} ms │")
    print(f"└─────────────────────────────┴──────────────────────────┘")

def render_recent_logs(logs: List[Dict], limit: int = 6):
    print(f"\n{BOLD}{MAGENTA}[2. STRUCTURED LOGS STREAM (LAST {limit} ENTRIES)]{RESET}")
    recent = logs[-limit:] if len(logs) >= limit else logs
    if not recent:
        print(f"  {DIM}(Belum ada logs. Jalankan simulasi request terlebih dahulu){RESET}")
        return

    for entry in recent:
        lvl = entry.get("level", "INFO")
        color = GREEN if lvl == "INFO" else (YELLOW if lvl == "DEBUG" else RED)
        ts = entry.get("timestamp")
        tr_id = entry.get("trace_id", "-")
        sp_id = entry.get("span_id", "-")
        msg = entry.get("message")
        
        # Format as realistic JSON log
        compact_json = json.dumps(entry)
        print(f"  {color}[{lvl:<5}]{RESET} {DIM}{ts}{RESET} [tr:{tr_id} sp:{sp_id}] {msg}")
        print(f"         {DIM}{compact_json}{RESET}")

def render_trace_flamegraph(tracer: Tracer, trace_id: str):
    print(f"\n{BOLD}{GREEN}[3. DISTRIBUTED TRACE WATERFALL / FLAMEGRAPH]{RESET}")
    print(f"Trace ID: {BOLD}{trace_id}{RESET}")
    spans = [s for s in tracer.spans if s.trace_id == trace_id]
    if not spans:
        print(f"  {RED}Trace ID tidak ditemukan.{RESET}")
        return

    # Sort root to leaf
    print(f"\n  {'Span Hierarchy / Service':<38} | {'Status':<7} | {'Duration (ms)':<15} | Gantt Bar")
    print(f"  {'-'*38}-+-{'-'*7}-+-{'-'*15}-+---------------------------")
    
    max_duration = max((s.duration_ms for s in spans), default=1.0)
    for s in spans:
        indent = "  " if not s.parent_span_id else ("    └── " if "::" in s.name and "PostgreSQL" not in s.name else "        └── ")
        status_badge = f"{GREEN}OK{RESET}" if s.status == "OK" else f"{RED}ERR{RESET}"
        bar_len = int((s.duration_ms / max(max_duration, 1.0)) * 25)
        bar = "█" * max(bar_len, 1)
        bar_color = RED if s.status == "ERROR" else CYAN
        
        name_display = f"{indent}{s.name}"[:38]
        print(f"  {name_display:<38} | {status_badge:<16} | {s.duration_ms:>10.2f} ms   | {bar_color}{bar}{RESET}")

def main():
    sim = ECommerceSimulator()
    last_trace_id = ""

    # Pre-seed 3 normal requests
    for i in range(3):
        _, tid, _ = sim.process_order(f"cust-{100+i}", force_anomaly=False)
        last_trace_id = tid

    while True:
        display_header()
        print(f"Menu Pilihan:")
        print(f"  {BOLD}1{RESET}. Jalankan Normal Request (HTTP 200 - Tracing + Logs + Metrics)")
        print(f"  {BOLD}2{RESET}. Simulasikan Anomali/Outage (HTTP 500 DB Deadlock)")
        print(f"  {BOLD}3{RESET}. Tampilkan Metrics Dashboard (Counters, Gauges, Latency)")
        print(f"  {BOLD}4{RESET}. Tampilkan Structured Logs (JSON + Correlation ID)")
        print(f"  {BOLD}5{RESET}. Visualisasikan Trace Terakhir (Flamegraph Waterfall)")
        print(f"  {BOLD}6{RESET}. Batched Stress Test (15 Requests Beragam)")
        print(f"  {BOLD}0{RESET}. Keluar dari Program\n")

        try:
            choice = input(f"{BOLD}{WHITE}Pilih menu [0-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan.{RESET}")
            break

        if choice == "1":
            cust_id = f"cust-{random.randint(200, 999)}"
            print(f"\n{CYAN}>>> Mengirim request order normal untuk {cust_id}...{RESET}")
            success, last_trace_id, lat = sim.process_order(cust_id, force_anomaly=False)
            print(f"{GREEN}✔ Berhasil! Latensi: {lat:.2f}ms | Trace ID: {last_trace_id}{RESET}")
        
        elif choice == "2":
            cust_id = f"cust-err-{random.randint(100, 999)}"
            print(f"\n{RED}>>> Mengirim request order yang memicu DATABASE DEADLOCK...{RESET}")
            success, last_trace_id, lat = sim.process_order(cust_id, force_anomaly=True)
            print(f"{RED}✖ Gagal (HTTP 500)! Latensi: {lat:.2f}ms | Trace ID: {last_trace_id}{RESET}")
            print(f"{YELLOW}Tips: Periksa menu 3 (Metrics), 4 (Logs), atau 5 (Traces) untuk menganalisis akar masalah.{RESET}")

        elif choice == "3":
            render_metrics_dashboard(sim.metrics)

        elif choice == "4":
            render_recent_logs(sim.logger.logs, limit=8)

        elif choice == "5":
            if not last_trace_id:
                print(f"{YELLOW}Belum ada trace tersimpan.{RESET}")
            else:
                render_trace_flamegraph(sim.tracer, last_trace_id)

        elif choice == "6":
            print(f"\n{BLUE}>>> Menjalankan stress test 15 request...{RESET}")
            for i in range(15):
                is_anomaly = random.random() < 0.20  # 20% error rate
                cid = f"batch-{i+1}"
                _, last_trace_id, _ = sim.process_order(cid, force_anomaly=is_anomaly)
                print(".", end="", flush=True)
                time.sleep(0.05)
            print(f"\n{GREEN}✔ Selesai! Periksa hasil di menu 3 (Metrics).{RESET}")

        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah mempelajari Fondasi Observabilitas (MELT)!{RESET}")
            sys.exit(0)
        else:
            print(f"\n{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")

        time.sleep(0.4)

if __name__ == "__main__":
    main()
