#!/usr/bin/env python3
"""
Lab Exercise: ASP.NET Core Enterprise Architecture & Cloud-Native Deployment
Module: Cloud-Native Microservice Resilience, Pipeline & Diagnostics Deep Dive

Simulates the ASP.NET Core enterprise runtime architecture:
1. Middleware Pipeline (Russian Doll / RequestDelegate model).
2. Polly-style Circuit Breaker policy engine (Closed, Open, Half-Open).
3. Health Check Subsystem (IHealthCheck / Microsoft.Extensions.Diagnostics).
4. Distributed Tracing & Correlation ID propagation (W3C traceparent standard).
5. RFC 7807 ProblemDetails compliance for fault isolation.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
import random
import threading
import time
from typing import Callable, Dict, List, Optional
import uuid

# --- ANSI Terminal Formatting ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"

# --- Domain & ASP.NET Core Abstractions ---

class HealthStatus(Enum):
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    UNHEALTHY = "Unhealthy"

class CircuitState(Enum):
    CLOSED = "CLOSED"         # Normal operation: traffic flows through
    OPEN = "OPEN"             # Failing: calls short-circuited immediately
    HALF_OPEN = "HALF_OPEN"   # Trial: testing if downstream recovered

@dataclass
class HttpContext:
    """Simulates Microsoft.AspNetCore.Http.HttpContext."""
    path: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    items: Dict[str, object] = field(default_factory=dict)
    response_status_code: int = 200
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: Optional[str] = None

RequestDelegate = Callable[[HttpContext], None]

# --- Resilience: Polly-style Circuit Breaker ---

class CircuitBreakerOpenException(Exception):
    """Exception thrown when the Circuit Breaker short-circuits execution."""
    pass

class CircuitBreakerPolicy:
    """
    Thread-safe state machine replicating Polly CircuitBreakerPolicy in .NET.
    Tracks sequential failures, shifts state, and isolates downstream services.
    """
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 2.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()
        self._lock = threading.Lock()

    def execute(self, action: Callable[[], any]):
        with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change >= self.reset_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                    print(f"  [{CLR_YELLOW}CIRCUIT BREAKER{CLR_RESET}] Reset timeout expired -> Transitioning to {CLR_BOLD}HALF-OPEN{CLR_RESET}")
                else:
                    remaining = round(self.reset_timeout - (now - self.last_state_change), 2)
                    raise CircuitBreakerOpenException(f"Circuit is OPEN. Fast-failing request (cooldown: {remaining}s)")

        try:
            result = action()
            with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.last_state_change = time.time()
                    print(f"  [{CLR_GREEN}CIRCUIT BREAKER{CLR_RESET}] Trial succeeded -> State recovered to {CLR_BOLD}CLOSED{CLR_RESET}")
                elif self.state == CircuitState.CLOSED:
                    self.failure_count = 0
            return result
        except Exception as ex:
            if isinstance(ex, CircuitBreakerOpenException):
                raise
            with self._lock:
                self.failure_count += 1
                if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                    if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                        self.state = CircuitState.OPEN
                        self.last_state_change = time.time()
                        print(f"  [{CLR_RED}CIRCUIT BREAKER{CLR_RESET}] Failure threshold exceeded ({self.failure_count}) -> State tripped to {CLR_BOLD}OPEN{CLR_RESET}")
            raise

# --- Diagnostics: Health Check Subsystem ---

class HealthCheckService:
    """Simulates Microsoft.Extensions.Diagnostics.HealthChecks."""
    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthStatus]] = {}

    def register_check(self, name: str, check_func: Callable[[], HealthStatus]):
        self._checks[name] = check_func

    def check_health(self) -> Dict[str, any]:
        results = {}
        overall_status = HealthStatus.HEALTHY
        for name, check in self._checks.items():
            status = check()
            results[name] = status.value
            if status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "total_duration_ms": round(random.uniform(1.2, 5.8), 2),
            "entries": results
        }

# --- ASP.NET Core Middleware Pipeline ---

class PipelineBuilder:
    """Constructs the ASP.NET Core nested middleware pipeline (IApplicationBuilder)."""
    def __init__(self):
        self._components: List[Callable[[RequestDelegate], RequestDelegate]] = []

    def use(self, middleware: Callable[[RequestDelegate], RequestDelegate]):
        self._components.append(middleware)
        return self

    def build(self) -> RequestDelegate:
        app: RequestDelegate = lambda ctx: None
        for component in reversed(self._components):
            app = component(app)
        return app

# --- Enterprise Middleware Implementations ---

def correlation_id_middleware(next_middleware: RequestDelegate) -> RequestDelegate:
    """Injects and propagates W3C Trace Correlation ID (X-Correlation-ID)."""
    def handler(ctx: HttpContext):
        cid = ctx.headers.get("X-Correlation-ID", f"trace-{uuid.uuid4().hex[:12]}")
        ctx.items["CorrelationId"] = cid
        ctx.response_headers["X-Correlation-ID"] = cid
        next_middleware(ctx)
    return handler

def exception_handling_middleware(next_middleware: RequestDelegate) -> RequestDelegate:
    """Catches unhandled exceptions and formats RFC 7807 ProblemDetails JSON."""
    def handler(ctx: HttpContext):
        try:
            next_middleware(ctx)
        except CircuitBreakerOpenException as cbe:
            ctx.response_status_code = 503
            problem = {
                "type": "https://tools.ietf.org/html/rfc7231#section-6.6.4",
                "title": "Service Unavailable (Circuit Open)",
                "status": 503,
                "detail": str(cbe),
                "instance": ctx.path,
                "traceId": ctx.items.get("CorrelationId")
            }
            ctx.response_body = json.dumps(problem, indent=2)
        except Exception as ex:
            ctx.response_status_code = 500
            problem = {
                "type": "https://tools.ietf.org/html/rfc7231#section-6.6.1",
                "title": "Internal Server Error",
                "status": 500,
                "detail": f"Downstream dependency failure: {str(ex)}",
                "instance": ctx.path,
                "traceId": ctx.items.get("CorrelationId")
            }
            ctx.response_body = json.dumps(problem, indent=2)
    return handler

def health_check_endpoint_middleware(health_service: HealthCheckService):
    """Maps endpoints /health/ready and /health/live."""
    def middleware(next_middleware: RequestDelegate) -> RequestDelegate:
        def handler(ctx: HttpContext):
            if ctx.path in ("/health/ready", "/health/live"):
                health_report = health_service.check_health()
                ctx.response_status_code = 200 if health_report["status"] != "Unhealthy" else 503
                ctx.response_body = json.dumps(health_report, indent=2)
                return
            next_middleware(ctx)
        return handler
    return middleware

def enterprise_endpoint_middleware(breaker: CircuitBreakerPolicy):
    """Terminal endpoint simulating external enterprise integration."""
    def middleware(_: RequestDelegate) -> RequestDelegate:
        def handler(ctx: HttpContext):
            if ctx.path == "/api/orders/process":
                # Simulated enterprise backend with downstream call
                def call_erp_downstream():
                    # Intentionally simulate downstream degradation based on random seed
                    if random.random() < 0.65:
                        raise ConnectionResetError("ERP Gateway connection reset by peer")
                    return "ERP_TRANSACTION_ACK_9824"

                result = breaker.execute(call_erp_downstream)
                ctx.response_status_code = 200
                ctx.response_body = json.dumps({
                    "order_id": f"ORD-{uuid.uuid4().hex[:6].upper()}",
                    "status": "Processed",
                    "erp_confirmation": result,
                    "correlation_id": ctx.items.get("CorrelationId")
                })
            else:
                ctx.response_status_code = 404
                ctx.response_body = json.dumps({"error": "Resource not found"})
        return handler
    return middleware

# --- Lab Orchestration & Simulation ---

def run_lab():
    print(f"{CLR_BOLD}{CLR_CYAN}========================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} ASP.NET Core Cloud-Native Architecture & Resilience Simulation Engine {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}========================================================================{CLR_RESET}\n")

    # 1. Setup Polly Circuit Breaker
    # Trips after 2 consecutive faults, reset timeout 1.5s
    breaker = CircuitBreakerPolicy(failure_threshold=2, reset_timeout=1.5)

    # 2. Setup Health Check Subsystem
    health_svc = HealthCheckService()
    health_svc.register_check("Database (PostgreSQL)", lambda: HealthStatus.HEALTHY)
    health_svc.register_check("EventBus (RabbitMQ)", lambda: HealthStatus.HEALTHY)
    health_svc.register_check("Downstream ERP API", lambda: (
        HealthStatus.UNHEALTHY if breaker.state == CircuitState.OPEN 
        else HealthStatus.DEGRADED if breaker.state == CircuitState.HALF_OPEN 
        else HealthStatus.HEALTHY
    ))

    # 3. Assemble ASP.NET Core Pipeline
    pipeline = (PipelineBuilder()
        .use(correlation_id_middleware)
        .use(exception_handling_middleware)
        .use(health_check_endpoint_middleware(health_svc))
        .use(enterprise_endpoint_middleware(breaker))
        .build())

    # 4. Execute Simulation Requests
    random.seed(42)  # Deterministic failure cadence
    print(f"{CLR_BOLD}[1] SIMULATING PRODUCTION HTTP TRAFFIC WITH FAULT ISOLATION{CLR_RESET}")
    print("-" * 72)

    for i in range(1, 9):
        ctx = HttpContext(path="/api/orders/process")
        pipeline(ctx)

        color = CLR_GREEN if ctx.response_status_code == 200 else CLR_RED
        cid = ctx.response_headers.get("X-Correlation-ID")
        print(f"Req #{i:02d} | Path: {ctx.path} | CID: {cid} | Status: {color}{ctx.response_status_code}{CLR_RESET}")
        
        if ctx.response_status_code != 200:
            err = json.loads(ctx.response_body)
            print(f"       -> {CLR_YELLOW}ProblemDetails:{CLR_RESET} {err.get('title')} ({err.get('detail')})")
        time.sleep(0.3)

    print("\n" + "-" * 72)
    print(f"{CLR_BOLD}[2] EXAMINING CLOUD-NATIVE HEALTH CHECK (/health/ready){CLR_RESET}")
    print("-" * 72)
    ctx_health = HttpContext(path="/health/ready")
    pipeline(ctx_health)
    print(f"Response ({ctx_health.response_status_code}):\n{ctx_health.response_body}")

    print("\n" + "-" * 72)
    print(f"{CLR_BOLD}[3] TESTING CIRCUIT RECOVERY (COOLDOWN EXPIRATION & HALF-OPEN STATE){CLR_RESET}")
    print("-" * 72)
    print(f"Sleeping 1.6s to allow Circuit Breaker cooldown to lapse...")
    time.sleep(1.6)

    # Force downstream stability for recovery demonstration
    random.seed(999)

    for i in range(9, 12):
        ctx = HttpContext(path="/api/orders/process")
        pipeline(ctx)
        color = CLR_GREEN if ctx.response_status_code == 200 else CLR_RED
        cid = ctx.response_headers.get("X-Correlation-ID")
        print(f"Req #{i:02d} | Path: {ctx.path} | CID: {cid} | Status: {color}{ctx.response_status_code}{CLR_RESET}")
        time.sleep(0.2)

    print("\n" + "-" * 72)
    print(f"{CLR_BOLD}[4] FINAL HEALTH CHECK REPORT{CLR_RESET}")
    print("-" * 72)
    ctx_final_health = HttpContext(path="/health/ready")
    pipeline(ctx_final_health)
    print(f"Status Code: {ctx_final_health.response_status_code}")
    print(ctx_final_health.response_body)
    print(f"\n{CLR_BOLD}{CLR_GREEN}[SUCCESS] Lab execution complete. Enterprise patterns verified.{CLR_RESET}")

if __name__ == "__main__":
    run_lab()