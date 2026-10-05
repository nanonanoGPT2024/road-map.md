#!/usr/bin/env python3
"""
Lab Exercise: Advanced Production Observability, Monitoring & Logging Simulation
Bab 08: Observabilitas, Monitoring, & Logging
Fokus: The Three Pillars (Metrics, Logs, Traces), SLI/SLO Error Budget, Alerting Engine
"""

import sys
import time
import uuid
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ANSI Color Codes for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    service: str
    start_time: float
    duration_ms: float = 0.0
    status: str = "OK"
    attributes: Dict[str, str] = field(default_factory=dict)


class OpenTelemetryTracer:
    """Simulates OpenTelemetry distributed tracing context propagation."""

    def __init__(self):
        self.spans: List[Span] = []

    def start_trace(self, service: str, operation: str) -> Span:
        trace_id = uuid.uuid4().hex[:16]
        span_id = uuid.uuid4().hex[:8]
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            name=operation,
            service=service,
            start_time=time.time(),
        )
        self.spans.append(span)
        return span

    def create_child_span(self, parent: Span, service: str, operation: str) -> Span:
        span_id = uuid.uuid4().hex[:8]
        span = Span(
            trace_id=parent.trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id,
            name=operation,
            service=service,
            start_time=time.time(),
        )
        self.spans.append(span)
        return span

    def finish_span(self, span: Span, status: str = "OK", duration_ms: float = 0.0, attributes: Optional[Dict[str, str]] = None):
        span.status = status
        span.duration_ms = duration_ms
        if attributes:
            span.attributes.update(attributes)


class StructuredLogger:
    """Production JSON-formatted logger with contextual correlation IDs."""

    @staticmethod
    def log(level: str, message: str, service: str, trace_id: str, span_id: str, extra: Optional[Dict] = None):
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level.upper(),
            "service": service,
            "trace_id": trace_id,
            "span_id": span_id,
            "message": message,
        }
        if extra:
            payload["extra"] = extra

        color_map = {
            "DEBUG": DIM + BLUE,
            "INFO": CYAN,
            "WARN": YELLOW,
            "ERROR": RED,
            "CRITICAL": BG_RED + BOLD,
        }
        prefix_color = color_map.get(level.upper(), RESET)
        print(f"{prefix_color}[{payload['level']}]{RESET} {DIM}{payload['timestamp']}{RESET} "
              f"[{BOLD}{service}{RESET}] trace={MAGENTA}{trace_id}{RESET} span={BLUE}{span_id}{RESET} -> {message}")


class PrometheusMetricRegistry:
    """Simulates standard Prometheus exposition format (Counter, Gauge, Histogram)."""

    def __init__(self):
        self.http_requests_total: Dict[str, int] = {}
        self.http_request_duration_ms: List[float] = []
        self.active_connections: int = 120
        self.error_count: int = 0
        self.total_count: int = 0

    def record_request(self, service: str, method: str, status_code: int, duration_ms: float):
        key = f'{service}{{method="{method}",status="{status_code}"}}'
        self.http_requests_total[key] = self.http_requests_total.get(key, 0) + 1
        self.http_request_duration_ms.append(duration_ms)
        self.total_count += 1
        if status_code >= 500:
            self.error_count += 1

    def scrape_exposition_format(self) -> str:
        lines = [
            "# HELP http_requests_total Total number of HTTP requests processed.",
            "# TYPE http_requests_total counter"
        ]
        for key, val in self.http_requests_total.items():
            lines.append(f"http_requests_total{key} {val}")

        lines.extend([
            "",
            "# HELP active_backend_connections Number of live backend connection pool workers.",
            "# TYPE active_backend_connections gauge",
            f"active_backend_connections {self.active_connections}",
            "",
            "# HELP http_request_duration_milliseconds Summary of request latencies.",
            "# TYPE http_request_duration_milliseconds summary"
        ])
        if self.http_request_duration_ms:
            sorted_latencies = sorted(self.http_request_duration_ms)
            n = len(sorted_latencies)
            p50 = sorted_latencies[int(n * 0.50)]
            p90 = sorted_latencies[int(n * 0.90)]
            p99 = sorted_latencies[int(n * 0.99)]
            lines.append(f'http_request_duration_milliseconds{{quantile="0.5"}} {p50:.2f}')
            lines.append(f'http_request_duration_milliseconds{{quantile="0.9"}} {p90:.2f}')
            lines.append(f'http_request_duration_milliseconds{{quantile="0.99"}} {p99:.2f}')
            lines.append(f"http_request_duration_milliseconds_count {n}")
            lines.append(f"http_request_duration_milliseconds_sum {sum(sorted_latencies):.2f}")
        return "\n".join(lines)


class SREBudgetEngine:
    """Calculates Service Level Indicators (SLI) and Error Budget consumption."""

    def __init__(self, target_slo: float = 99.5):
        self.target_slo = target_slo  # 99.5% availability target

    def evaluate(self, total_requests: int, error_requests: int):
        if total_requests == 0:
            current_sli = 100.0
            error_rate = 0.0
        else:
            error_rate = (error_requests / total_requests) * 100.0
            current_sli = 100.0 - error_rate

        allowed_error_rate = 100.0 - self.target_slo
        budget_consumed_pct = (error_rate / allowed_error_rate) * 100.0 if allowed_error_rate > 0 else 0.0
        remaining_budget_pct = max(0.0, 100.0 - budget_consumed_pct)

        return {
            "target_slo": self.target_slo,
            "current_sli": current_sli,
            "error_rate": error_rate,
            "budget_consumed_pct": budget_consumed_pct,
            "remaining_budget_pct": remaining_budget_pct,
        }


class ProductionSimulator:
    """Microservice architecture pipeline: Gateway -> Auth -> Payment -> Database."""

    def __init__(self):
        self.tracer = OpenTelemetryTracer()
        self.metrics = PrometheusMetricRegistry()
        self.sre = SREBudgetEngine(target_slo=99.5)
        self.logger = StructuredLogger()

    def simulate_transaction(self, chaos_mode: bool = False):
        root_span = self.tracer.start_trace("api-gateway", "POST /v1/checkout")
        trace_id = root_span.trace_id
        gateway_span_id = root_span.span_id

        self.logger.log("INFO", "Inbound request received at edge ingress proxy", "api-gateway", trace_id, gateway_span_id)

        # 1. Auth Service
        auth_span = self.tracer.create_child_span(root_span, "auth-service", "VerifyToken")
        auth_latency = random.uniform(10.0, 35.0)
        time.sleep(0.01)
        self.tracer.finish_span(auth_span, "OK", auth_latency, {"token.type": "Bearer", "jwt.valid": "true"})
        self.logger.log("INFO", f"JWT validated in {auth_latency:.1f}ms", "auth-service", trace_id, auth_span.span_id)

        # 2. Payment & DB Service with Chaos Injection
        pay_span = self.tracer.create_child_span(root_span, "payment-service", "ProcessCharge")
        db_span = self.tracer.create_child_span(pay_span, "postgres-db", "UPDATE user_balances")

        is_failure = chaos_mode and (random.random() < 0.40)
        is_latency_spike = chaos_mode and (random.random() < 0.50)

        db_latency = random.uniform(150.0, 480.0) if is_latency_spike else random.uniform(8.0, 45.0)
        pay_latency = db_latency + random.uniform(15.0, 50.0)
        total_gateway_latency = auth_latency + pay_latency + random.uniform(5.0, 15.0)

        if is_failure:
            self.tracer.finish_span(db_span, "ERROR", db_latency, {"db.error": "ConnectionTimeout", "sql.state": "08001"})
            self.logger.log("ERROR", f"PostgreSQL pool exhausted: query timeout after {db_latency:.1f}ms", "postgres-db", trace_id, db_span.span_id)

            self.tracer.finish_span(pay_span, "ERROR", pay_latency, {"http.status": "503", "payment.declined": "pool_timeout"})
            self.logger.log("CRITICAL", "Payment upstream dependency failure (HTTP 503)", "payment-service", trace_id, pay_span.span_id)

            self.tracer.finish_span(root_span, "ERROR", total_gateway_latency, {"http.status": "503"})
            self.logger.log("ERROR", f"Transaction failed [HTTP 503 Service Unavailable] total={total_gateway_latency:.1f}ms", "api-gateway", trace_id, gateway_span_id)
            self.metrics.record_request("api_gateway", "POST", 503, total_gateway_latency)
        else:
            self.tracer.finish_span(db_span, "OK", db_latency, {"rows_affected": "1"})
            self.tracer.finish_span(pay_span, "OK", pay_latency, {"http.status": "200", "txn.amount": "129.50"})
            self.tracer.finish_span(root_span, "OK", total_gateway_latency, {"http.status": "200"})
            self.logger.log("INFO", f"Checkout completed successfully [HTTP 200 OK] total={total_gateway_latency:.1f}ms", "api-gateway", trace_id, gateway_span_id)
            self.metrics.record_request("api_gateway", "POST", 200, total_gateway_latency)


def render_dashboard(sim: ProductionSimulator):
    print("\n" + "=" * 80)
    print(f"{BOLD}{CYAN}PRODUCTION OBSERVABILITY & SRE STATUS DASHBOARD{RESET}".center(90))
    print("=" * 80)

    stats = sim.sre.evaluate(sim.metrics.total_count, sim.metrics.error_count)
    sli_color = GREEN if stats["current_sli"] >= stats["target_slo"] else RED
    budget_color = GREEN if stats["remaining_budget_pct"] > 30.0 else (YELLOW if stats["remaining_budget_pct"] > 0 else RED)

    print(f"\n{BOLD}[1] Service Level Objectives (SLO) & Error Budget{RESET}")
    print(f"  • SLO Target (Availability): {BOLD}{stats['target_slo']}%{RESET}")
    print(f"  • Current Measured SLI     : {sli_color}{BOLD}{stats['current_sli']:.2f}%{RESET}")
    print(f"  • Total Requests Processed : {sim.metrics.total_count} (Errors: {sim.metrics.error_count})")
    print(f"  • Error Budget Remaining   : {budget_color}{BOLD}{stats['remaining_budget_pct']:.1f}%{RESET}")

    # Visual gauge bar
    bar_width = 30
    filled = int((stats["remaining_budget_pct"] / 100.0) * bar_width)
    bar = f"{budget_color}{'█' * filled}{DIM}{'░' * (bar_width - filled)}{RESET}"
    print(f"  • Budget Health Bar        : [{bar}]")

    print(f"\n{BOLD}[2] Active Alerts (Prometheus Alertmanager Rules){RESET}")
    if stats["remaining_budget_pct"] <= 0:
        print(f"  {BG_RED}{BOLD} [CRITICAL ALERT FIRING] {RESET} {RED}ErrorBudgetExhausted: Service deployment freeze enforced!{RESET}")
    elif stats["error_rate"] > 2.0:
        print(f"  {BG_YELLOW}{BOLD} [WARNING ALERT FIRING] {RESET} {YELLOW}HighErrorRateBurnRate: 5m error rate is > 2.0%{RESET}")
    else:
        print(f"  {GREEN}✓ No alerting rules triggered. All systems operational within tolerance.{RESET}")

    print("=" * 80)


def print_trace_waterfall(sim: ProductionSimulator, count: int = 4):
    print(f"\n{BOLD}{MAGENTA}Distributed Trace Waterfall (OpenTelemetry Visualization):{RESET}")
    recent_spans = sim.tracer.spans[-count:] if len(sim.tracer.spans) >= count else sim.tracer.spans
    for s in recent_spans:
        status_badge = f"{GREEN}OK{RESET}" if s.status == "OK" else f"{RED}ERR{RESET}"
        indent = "    " if s.parent_span_id else "  "
        print(f"{indent}↳ [{status_badge}] {BOLD}{s.service:<16}{RESET} op={CYAN}{s.name:<24}{RESET} duration={s.duration_ms:6.1f}ms")


def run_interactive():
    sim = ProductionSimulator()
    print(f"{BOLD}{GREEN}========================================================================{RESET}")
    print(f"{BOLD}{GREEN} LAB EXERCISE: CLOUD-NATIVE OBSERVABILITY (METRICS, LOGS, TRACES)       {RESET}")
    print(f"{BOLD}{GREEN} BAB 08 - DevOps, Observability, Monitoring & Logging                   {RESET}")
    print(f"{BOLD}{GREEN}========================================================================{RESET}")

    while True:
        print(f"\n{BOLD}PILIH TINDAKAN SIMULASI OBSERVABILITAS:{RESET}")
        print("  1. Kirim Batch Request Normal (Baseline Steady-State)")
        print("  2. Simulasikan Chaos Engineering (Spike Latensi & DB Connection Timeout)")
        print("  3. Scrape Endpoint Prometheus (/metrics Exposition Format)")
        print("  4. Tampilkan Detail OpenTelemetry Distributed Trace")
        print("  5. Tampilkan SRE Error Budget & Alerting Status Dashboard")
        print("  6. Keluar (Exit)")

        try:
            choice = input(f"\n{BOLD}{CYAN}Masukkan pilihan [1-6]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == "1":
            print(f"\n{BLUE}>>> Mengirim 10 request transaksi normal ke API Gateway...{RESET}")
            for _ in range(10):
                sim.simulate_transaction(chaos_mode=False)
            render_dashboard(sim)
        elif choice == "2":
            print(f"\n{YELLOW}>>> Mengaktifkan Chaos Mode (Simulasi kegagalan upstream & latensi)...{RESET}")
            for _ in range(12):
                sim.simulate_transaction(chaos_mode=True)
            render_dashboard(sim)
        elif choice == "3":
            print(f"\n{BOLD}{YELLOW}--- HTTP GET /metrics (Prometheus Format) ---{RESET}")
            print(sim.metrics.scrape_exposition_format())
            print(f"{BOLD}{YELLOW}---------------------------------------------{RESET}")
        elif choice == "4":
            print_trace_waterfall(sim, count=8)
        elif choice == "5":
            render_dashboard(sim)
        elif choice == "6":
            print(f"\n{GREEN}Lab exercise selesai. Terima kasih.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1 - 6.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        # Verification run mode
        sim = ProductionSimulator()
        sim.simulate_transaction(chaos_mode=False)
        sim.simulate_transaction(chaos_mode=True)
        render_dashboard(sim)
        print_trace_waterfall(sim)
        print(sim.metrics.scrape_exposition_format())
    else:
        run_interactive()
