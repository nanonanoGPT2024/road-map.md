#!/usr/bin/env python3
"""
Simulasi Teknis Observability, Structured Logging & Production Diagnostics
(ASP.NET Core / .NET Runtime Architecture Simulation)

Modul ini mensimulasikan komponen inti observability pada ASP.NET Core:
1. OpenTelemetry Distributed Tracing via ActivitySource & Activity (W3C TraceContext)
2. Structured Logging dengan ILogger<T> / Serilog Semantic Logging & Scopes
3. Application Metrics (System.Diagnostics.Metrics: Counter, Histogram, Gauge)
4. Health Checks Subsystem (IHealthCheck, Liveness vs Readiness Probes)
5. EventPipe & DiagnosticSource Notification Pipeline
"""

import sys
import time
import uuid
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "=" * 70
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f" >>> {title.upper()} <<<")
    print(f"{line}{CLR_RESET}\n")


def subheader(title: str) -> None:
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[#] {title}{CLR_RESET}")
    print(f"{CLR_DIM}{'-' * 50}{CLR_RESET}")


# --- 1. Distributed Tracing: Activity & ActivitySource ---
@dataclass
class ActivitySpan:
    operation_name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    start_time: float
    duration_ms: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)

    def add_event(self, event_name: str) -> None:
        self.events.append(f"{event_name} @ {time.strftime('%H:%M:%S')}")

    def set_tag(self, key: str, value: Any) -> None:
        self.tags[key] = value

    def complete(self) -> None:
        self.duration_ms = (time.time() - self.start_time) * 1000.0


class ActivitySource:
    """Simulasi System.Diagnostics.ActivitySource (OpenTelemetry Tracing Engine)."""

    def __init__(self, source_name: str, version: str = "1.0.0"):
        self.source_name = source_name
        self.version = version

    def start_activity(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> ActivitySpan:
        current_trace_id = trace_id or uuid.uuid4().hex
        current_span_id = uuid.uuid4().hex[:16]
        span = ActivitySpan(
            operation_name=operation_name,
            trace_id=current_trace_id,
            span_id=current_span_id,
            parent_span_id=parent_span_id,
            start_time=time.time(),
        )
        return span


# --- 2. Structured Logging: ILogger & Scope Provider ---
class LogLevel:
    TRACE = "TRC"
    DEBUG = "DBG"
    INFO = "INF"
    WARN = "WRN"
    ERROR = "ERR"
    CRITICAL = "CRT"


class Logger:
    """Simulasi Microsoft.Extensions.Logging.ILogger<TCategory> dengan Structured Scopes."""

    def __init__(self, category_name: str):
        self.category_name = category_name
        self.current_scope: Dict[str, Any] = {}

    def begin_scope(self, **kwargs) -> None:
        self.current_scope.update(kwargs)

    def clear_scope(self) -> None:
        self.current_scope.clear()

    def log(
        self,
        level: str,
        message_template: str,
        properties: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        props = properties or {}
        combined = {**self.current_scope, **props}

        color_map = {
            LogLevel.TRACE: CLR_DIM,
            LogLevel.DEBUG: CLR_WHITE,
            LogLevel.INFO: CLR_GREEN,
            LogLevel.WARN: CLR_YELLOW,
            LogLevel.ERROR: CLR_RED,
            LogLevel.CRITICAL: f"{CLR_RED}{CLR_BOLD}",
        }
        color = color_map.get(level, CLR_WHITE)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Format message template simulation
        formatted_message = message_template
        for key, val in props.items():
            formatted_message = formatted_message.replace(f"{{{key}}}", str(val))

        scope_str = (
            f" {CLR_MAGENTA}{combined}{CLR_RESET}"
            if combined
            else ""
        )

        print(
            f"{CLR_DIM}[{timestamp}]{CLR_RESET} "
            f"{color}[{level}]{CLR_RESET} "
            f"{CLR_BLUE}[{self.category_name}]{CLR_RESET} "
            f"{formatted_message}{scope_str}"
        )

        if exception:
            print(
                f"   {CLR_RED}Exception Details: {type(exception).__name__}: {exception}{CLR_RESET}"
            )


# --- 3. Metrics: System.Diagnostics.Metrics (Meter, Counter, Histogram) ---
class AppMetrics:
    """Simulasi System.Diagnostics.Metrics untuk ASP.NET Core."""

    def __init__(self, meter_name: str):
        self.meter_name = meter_name
        self.requests_total: int = 0
        self.requests_failed: int = 0
        self.latency_histogram_ms: List[float] = []

    def record_request(self, status_code: int, duration_ms: float) -> None:
        self.requests_total += 1
        if status_code >= 400:
            self.requests_failed += 1
        self.latency_histogram_ms.append(duration_ms)

    def print_summary(self) -> None:
        subheader("Telemetry Metrics Dashboard (Prometheus / OTLP Exporter)")
        avg_latency = (
            sum(self.latency_histogram_ms) / len(self.latency_histogram_ms)
            if self.latency_histogram_ms
            else 0.0
        )
        p95_latency = (
            sorted(self.latency_histogram_ms)[
                int(len(self.latency_histogram_ms) * 0.95)
            ]
            if self.latency_histogram_ms
            else 0.0
        )

        print(
            f"{CLR_BOLD}Meter:{CLR_RESET} {self.meter_name}\n"
            f" -> {CLR_CYAN}http_server_request_count_total:{CLR_RESET} {self.requests_total}\n"
            f" -> {CLR_RED}http_server_failed_requests_total:{CLR_RESET} {self.requests_failed}\n"
            f" -> {CLR_GREEN}http_server_duration_avg_ms:{CLR_RESET} {avg_latency:.2f} ms\n"
            f" -> {CLR_YELLOW}http_server_duration_p95_ms:{CLR_RESET} {p95_latency:.2f} ms"
        )


# --- 4. Health Checks: IHealthCheck ---
class HealthStatus:
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNHEALTHY = "Unhealthy"


class HealthCheckService:
    """Simulasi ASP.NET Core Health Checks Subsystem (/healthz, /ready, /live)."""

    def __init__(self):
        self.checks: Dict[str, Any] = {}

    def register_check(self, name: str, check_fn) -> None:
        self.checks[name] = check_fn

    def execute_all(self) -> Dict[str, Any]:
        results = {}
        overall_status = HealthStatus.HEALTHY

        for name, fn in self.checks.items():
            status, latency, desc = fn()
            results[name] = {"status": status, "latency_ms": latency, "desc": desc}
            if status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif (
                status == HealthStatus.DEGRADED
                and overall_status != HealthStatus.UNHEALTHY
            ):
                overall_status = HealthStatus.DEGRADED

        return {"overall": overall_status, "entries": results}


# --- Simulation Workflow Runners ---
def simulate_distributed_request(
    activity_source: ActivitySource, logger: Logger, metrics: AppMetrics
) -> None:
    subheader("Simulasi Distributed Trace: Inbound HTTP Request -> Pipeline")

    # 1. Root Activity: ASP.NET Core Request Pipeline
    root_span = activity_source.start_activity("Microsoft.AspNetCore.Hosting.HttpRequestIn")
    root_span.set_tag("http.method", "POST")
    root_span.set_tag("http.route", "/api/v1/orders/checkout")
    root_span.set_tag("http.scheme", "https")

    logger.begin_scope(
        TraceId=root_span.trace_id,
        SpanId=root_span.span_id,
        CorrelationId=str(uuid.uuid4())[:8],
    )
    logger.log(
        LogLevel.INFO,
        "Request received: {Method} {Path}",
        {"Method": "POST", "Path": "/api/v1/orders/checkout"},
    )

    # 2. Child Activity: OrderService Domain Logic
    time.sleep(0.04)
    service_span = activity_source.start_activity(
        "OrderProcessingService.ExecuteCheckoutAsync",
        trace_id=root_span.trace_id,
        parent_span_id=root_span.span_id,
    )
    service_span.set_tag("order.items_count", 3)
    logger.log(
        LogLevel.DEBUG,
        "Validating inventory and customer credit balance for OrderId: {OrderId}",
        {"OrderId": "ORD-94812"},
    )
    service_span.add_event("InventoryReserved")

    # 3. Child Activity: Entity Framework Core SQL Query
    time.sleep(0.06)
    db_span = activity_source.start_activity(
        "Npgsql.EntityFrameworkCore.PostgreSQL.ExecuteDbCommand",
        trace_id=root_span.trace_id,
        parent_span_id=service_span.span_id,
    )
    db_span.set_tag("db.system", "postgresql")
    db_span.set_tag("db.statement", "UPDATE inventory SET stock = stock - 1 WHERE sku = @p0")
    logger.log(
        LogLevel.DEBUG,
        "Executing EF Core SQL command against database {Database}",
        {"Database": "commerce_db"},
    )
    time.sleep(0.03)
    db_span.complete()

    # Finish Service Span
    time.sleep(0.02)
    service_span.complete()

    # Complete Root Span
    root_span.complete()
    status_code = 200
    metrics.record_request(status_code, root_span.duration_ms)

    logger.log(
        LogLevel.INFO,
        "HTTP {Method} {Path} completed with status code {StatusCode} in {Elapsed:0.000}ms",
        {
            "Method": "POST",
            "Path": "/api/v1/orders/checkout",
            "StatusCode": status_code,
            "Elapsed": root_span.duration_ms,
        },
    )
    logger.clear_scope()

    # Render OpenTelemetry Trace Waterfall Visualization
    print(f"\n{CLR_CYAN}{CLR_BOLD}[W3C Trace Waterfall Visualization]{CLR_RESET}")
    print(f"TraceId: {CLR_YELLOW}{root_span.trace_id}{CLR_RESET}")
    print(
        f" └─ [Span {root_span.span_id}] {CLR_BOLD}{root_span.operation_name}{CLR_RESET} "
        f"({root_span.duration_ms:.2f} ms)"
    )
    print(
        f"     └─ [Span {service_span.span_id}] {CLR_GREEN}{service_span.operation_name}{CLR_RESET} "
        f"({service_span.duration_ms:.2f} ms) [Parent: {service_span.parent_span_id}]"
    )
    print(
        f"         └─ [Span {db_span.span_id}] {CLR_MAGENTA}{db_span.operation_name}{CLR_RESET} "
        f"({db_span.duration_ms:.2f} ms) [Parent: {db_span.parent_span_id}]"
    )


def simulate_production_incident(logger: Logger, metrics: AppMetrics) -> None:
    subheader("Simulasi Diagnostik Kegagalan & Structured Error Logging")
    err_scope = {"TraceId": uuid.uuid4().hex, "TenantId": "enterprise-corp-01"}
    logger.begin_scope(**err_scope)

    logger.log(
        LogLevel.WARN,
        "Circuit breaker for downstream PaymentGateway is nearing trip threshold. Failure rate: {Rate}%",
        {"Rate": 48.5},
    )

    time.sleep(0.05)
    try:
        raise TimeoutError("Downstream payment service 'https://pay.gateway.internal' failed to respond in 3000ms")
    except Exception as ex:
        logger.log(
            LogLevel.ERROR,
            "Failed executing payment transaction for CustomerId: {CustomerId}",
            {"CustomerId": "CUST-8831"},
            exception=ex,
        )
        metrics.record_request(504, 3012.4)

    logger.clear_scope()


def run_health_checks(health_service: HealthCheckService) -> None:
    subheader("Pemeriksaan Status Kesehatan Sistem (Health Checks Report)")
    result = health_service.execute_all()

    overall_color = CLR_GREEN if result["overall"] == HealthStatus.HEALTHY else (
        CLR_YELLOW if result["overall"] == HealthStatus.DEGRADED else CLR_RED
    )
    print(f"Overall Application Status: {overall_color}{CLR_BOLD}{result['overall']}{CLR_RESET}\n")

    for name, data in result["entries"].items():
        st = data["status"]
        st_color = (
            CLR_GREEN
            if st == HealthStatus.HEALTHY
            else (CLR_YELLOW if st == HealthStatus.DEGRADED else CLR_RED)
        )
        print(
            f"  * {CLR_BOLD}{name:<22}{CLR_RESET} : "
            f"[{st_color}{st:<9}{CLR_RESET}] "
            f"({data['latency_ms']:5.1f} ms) - {CLR_DIM}{data['desc']}{CLR_RESET}"
        )


def main() -> None:
    header("ASP.NET Core Observability & Diagnostics Interactive Lab")

    activity_source = ActivitySource("Enterprise.Commerce.Platform", "2.1.0")
    logger = Logger("Microsoft.AspNetCore.Hosting.Diagnostics")
    metrics = AppMetrics("Enterprise.Commerce.Metrics")
    health = HealthCheckService()

    # Registrasi Probes
    health.register_check(
        "Npgsql-PostgreSQL",
        lambda: (
            HealthStatus.HEALTHY,
            12.4,
            "PostgreSQL 16 connection pool ready. 8/20 connections active.",
        ),
    )
    health.register_check(
        "StackExchange-Redis",
        lambda: (
            HealthStatus.HEALTHY,
            1.8,
            "Redis cluster response PONG within SLA.",
        ),
    )
    health.register_check(
        "Payment-Gateway-API",
        lambda: (
            HealthStatus.DEGRADED,
            420.5,
            "Third-party webhook endpoint experiencing high latency (>400ms).",
        ),
    )
    health.register_check(
        "Disk-Storage-Probe",
        lambda: (
            HealthStatus.HEALTHY,
            0.5,
            "Root partition has 64.2% free capacity.",
        ),
    )

    menu = (
        f"\n{CLR_BOLD}Pilih Skenario Observability yang Ingin Dijalankan:{CLR_RESET}\n"
        f"  {CLR_CYAN}[1]{CLR_RESET} Simulasi W3C Distributed Trace & OpenTelemetry Activity Spans\n"
        f"  {CLR_CYAN}[2]{CLR_RESET} Simulasi Structured Logging & Incident Diagnostics (Serilog Scope)\n"
        f"  {CLR_CYAN}[3]{CLR_RESET} Eksekusi ASP.NET Core Health Checks Probes (/healthz)\n"
        f"  {CLR_CYAN}[4]{CLR_RESET} Tampilkan Telemetry Metrics Dashboard (Prometheus/OTLP)\n"
        f"  {CLR_CYAN}[5]{CLR_RESET} Jalankan Automated End-to-End Diagnostic Lifecycle\n"
        f"  {CLR_RED}[0]{CLR_RESET} Keluar (Exit)\n"
    )

    # Check non-interactive argument or fallback
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"{CLR_YELLOW}[Mode Otomatis / Non-Interaktif Diaktifkan]{CLR_RESET}")
        simulate_distributed_request(activity_source, logger, metrics)
        simulate_production_incident(logger, metrics)
        run_health_checks(health)
        metrics.print_summary()
        header("Simulasi Selesai dengan Sukses!")
        return

    while True:
        print(menu)
        try:
            choice = input(f"{CLR_BOLD}Masukkan pilihan [0-5]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{CLR_DIM}Keluar dari lab.{CLR_RESET}")
            break

        if choice == "1":
            simulate_distributed_request(activity_source, logger, metrics)
        elif choice == "2":
            simulate_production_incident(logger, metrics)
        elif choice == "3":
            run_health_checks(health)
        elif choice == "4":
            metrics.print_summary()
        elif choice == "5":
            simulate_distributed_request(activity_source, logger, metrics)
            simulate_production_incident(logger, metrics)
            run_health_checks(health)
            metrics.print_summary()
        elif choice == "0":
            print(f"\n{CLR_GREEN}Lab selesai. Observability pipeline dihentikan secara graceful.{CLR_RESET}\n")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan masukkan angka 0-5.{CLR_RESET}")


if __name__ == "__main__":
    main()
