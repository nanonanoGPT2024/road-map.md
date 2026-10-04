#!/usr/bin/env python3
"""
Lab Exercise: ASP.NET Core Modern Web API Routing (Minimal APIs vs Controllers)
Simulasi Arsitektur Endpoint Routing Engine, Route Pattern Matching, Model Binding,
Endpoint Filters, dan Perbandingan Pipeline Overhead.
"""

import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    BG_CYAN = "\033[46m\033[30m"
    BG_MAGENTA = "\033[45m\033[30m"


class RouteStyle(Enum):
    MINIMAL_API = "Minimal API (Endpoint Routing)"
    CONTROLLER = "Controller (Action Invoker / MVC)"


@dataclass
class HttpRequest:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None


@dataclass
class HttpResponse:
    status_code: int
    data: Any
    content_type: str = "application/json"
    execution_time_ms: float = 0.0
    pipeline_trace: List[str] = field(default_factory=list)


@dataclass
class EndpointMetadata:
    pattern: str
    http_method: str
    handler_name: str
    style: RouteStyle
    constraints: Dict[str, str] = field(default_factory=dict)
    filters: List[str] = field(default_factory=list)
    handler_func: Optional[Callable[[HttpRequest, Dict[str, Any]], HttpResponse]] = None


class AspNetCoreRoutingEngine:
    def __init__(self):
        self.endpoints: List[EndpointMetadata] = []
        self._init_endpoints()

    def _init_endpoints(self):
        # 1. Minimal API endpoints (app.MapGet, app.MapPost)
        self.endpoints.append(
            EndpointMetadata(
                pattern="/api/v1/products",
                http_method="GET",
                handler_name="app.MapGet(\"/api/v1/products\", ...)",
                style=RouteStyle.MINIMAL_API,
                filters=["AddCorrelationIdFilter", "LoggingFilter"],
                handler_func=lambda req, params: HttpResponse(
                    status_code=200,
                    data=[
                        {"id": 1, "name": "Mechanical Keyboard", "price": 120.0},
                        {"id": 2, "name": "Ultra-wide Monitor", "price": 450.0},
                    ],
                ),
            )
        )

        self.endpoints.append(
            EndpointMetadata(
                pattern="/api/v1/products/{id:int}",
                http_method="GET",
                handler_name="app.MapGet(\"/api/v1/products/{id:int}\", ...)",
                style=RouteStyle.MINIMAL_API,
                constraints={"id": r"^\d+$"},
                filters=["AddCorrelationIdFilter", "ValidateProductExistsFilter"],
                handler_func=lambda req, params: HttpResponse(
                    status_code=200,
                    data={"id": int(params["id"]), "name": "Mechanical Keyboard", "stock": 42},
                ),
            )
        )

        self.endpoints.append(
            EndpointMetadata(
                pattern="/api/v1/orders",
                http_method="POST",
                handler_name="app.MapPost(\"/api/v1/orders\", ...)",
                style=RouteStyle.MINIMAL_API,
                filters=["EndpointValidationFilter"],
                handler_func=lambda req, params: HttpResponse(
                    status_code=201,
                    data={"order_id": "ORD-9912", "status": "Confirmed", "item_count": len(req.body or {})},
                ),
            )
        )

        # 2. Controller-based endpoints ([ApiController], [Route("api/[controller]")])
        self.endpoints.append(
            EndpointMetadata(
                pattern="/api/customers",
                http_method="GET",
                handler_name="CustomersController.GetAllAsync() [HttpGet]",
                style=RouteStyle.CONTROLLER,
                filters=["AuthorizeFilter", "ActionModelBindingFilter", "ResultTransformFilter"],
                handler_func=lambda req, params: HttpResponse(
                    status_code=200,
                    data=[
                        {"id": 101, "customer": "Acme Corp", "tier": "Enterprise"},
                        {"id": 102, "customer": "Stark Industries", "tier": "VIP"},
                    ],
                ),
            )
        )

        self.endpoints.append(
            EndpointMetadata(
                pattern="/api/customers/{id:int}",
                http_method="GET",
                handler_name="CustomersController.GetByIdAsync(int id) [HttpGet(\"{id:int}\")]",
                style=RouteStyle.CONTROLLER,
                constraints={"id": r"^\d+$"},
                filters=["AuthorizeFilter", "ActionModelBindingFilter", "ResponseCachingFilter"],
                handler_func=lambda req, params: HttpResponse(
                    status_code=200,
                    data={"id": int(params["id"]), "customer": "Acme Corp", "credit_limit": 50000},
                ),
            )
        )

        self.endpoints.append(
            EndpointMetadata(
                pattern="/api/customers/{id:int}/deactivate",
                http_method="POST",
                handler_name="CustomersController.DeactivateAsync(int id) [HttpPost(\"{id:int}/deactivate\")]",
                style=RouteStyle.CONTROLLER,
                constraints={"id": r"^\d+$"},
                filters=["AuthorizeFilter", "AutoValidateAntiforgeryFilter", "AuditLogActionFilter"],
                handler_func=lambda req, params: HttpResponse(
                    status_code=200,
                    data={"id": int(params["id"]), "active": False, "message": "Account deactivated"},
                ),
            )
        )

    def _convert_pattern_to_regex(self, pattern: str, constraints: Dict[str, str]) -> Tuple[re.Pattern, List[str]]:
        param_names: List[str] = []

        def replacer(match):
            token = match.group(1)
            parts = token.split(":")
            p_name = parts[0]
            param_names.append(p_name)
            p_type = parts[1] if len(parts) > 1 else None

            if p_type == "int":
                return r"(?P<" + p_name + r">\d+)"
            elif p_name in constraints:
                return r"(?P<" + p_name + r">" + constraints[p_name] + r")"
            return r"(?P<" + p_name + r">[^/]+)"

        regex_str = "^" + re.sub(r"\{([^}]+)\}", replacer, pattern) + "$"
        return re.compile(regex_str), param_names

    def match_route(self, req: HttpRequest) -> Tuple[Optional[EndpointMetadata], Dict[str, Any], List[str]]:
        trace: List[str] = []
        trace.append(f"Routing Middleware: Mencari match untuk HTTP {req.method} {req.path}")

        for ep in self.endpoints:
            if ep.http_method != req.method:
                continue

            rx, param_names = self._convert_pattern_to_regex(ep.pattern, ep.constraints)
            m = rx.match(req.path)
            if m:
                extracted = m.groupdict()
                trace.append(f"-> Endpoint Matched: {ep.pattern} via {ep.style.value}")
                trace.append(f"-> Bound Route Parameters: {extracted}")
                return ep, extracted, trace

        trace.append("-> No endpoint matched. Yield 404 Not Found.")
        return None, {}, trace

    def execute_request(self, req: HttpRequest) -> HttpResponse:
        start_time = time.perf_counter()
        ep, params, trace = self.match_route(req)

        if not ep:
            dur = (time.perf_counter() - start_time) * 1000
            return HttpResponse(
                status_code=404,
                data={"error": "Not Found", "message": f"Endpoint {req.method} {req.path} tidak terdaftar."},
                execution_time_ms=dur,
                pipeline_trace=trace,
            )

        if ep.style == RouteStyle.MINIMAL_API:
            trace.append("Pipeline: [Direct Endpoint Invocation - Zero Reflection Overhead]")
            for f in ep.filters:
                trace.append(f"  + Executing EndpointFilter: {f}")
            trace.append(f"  * Executing Lambda/Delegate Handler: {ep.handler_name}")
            # Simulasi latensi ultra-rendah Minimal API
            time.sleep(0.001)
        else:
            trace.append("Pipeline: [Controller Action Invoker Pipeline]")
            trace.append("  + Instantiating Controller via IControllerActivator / DI Scope")
            for f in ep.filters:
                trace.append(f"  + Executing ActionFilter / Authorization: {f}")
            trace.append("  + Model Metadata Provider & Complex Model Binder Reflection")
            trace.append(f"  * Executing Action Method: {ep.handler_name}")
            trace.append("  + IActionResult / ObjectResult Formatting Pipeline")
            # Simulasi overhead tambahan reflection & filter lifecycle
            time.sleep(0.0035)

        res = ep.handler_func(req, params) if ep.handler_func else HttpResponse(200, "OK")
        dur = (time.perf_counter() - start_time) * 1000
        res.execution_time_ms = dur
        res.pipeline_trace = trace
        return res


def print_banner():
    print(f"{ANSI.CYAN}{ANSI.BOLD}======================================================================{ANSI.RESET}")
    print(f"{ANSI.BG_CYAN} ASP.NET CORE: MODERN WEB API ROUTING (MINIMAL API vs CONTROLLERS) {ANSI.RESET}")
    print(f"{ANSI.DIM} Hands-on Engine Simulation: DfaMatcher, RouteConstraints, & Filters{ANSI.RESET}")
    print(f"{ANSI.CYAN}======================================================================{ANSI.RESET}\n")


def print_table(engine: AspNetCoreRoutingEngine):
    print(f"{ANSI.BOLD}Registered Route Table (DFA Endpoint Tree):{ANSI.RESET}")
    print(f"{'-' * 88}")
    print(f"{'METHOD':<7} {'PATTERN':<32} {'TYPE':<14} {'HANDLER'}")
    print(f"{'-' * 88}")
    for ep in engine.endpoints:
        color = ANSI.GREEN if ep.style == RouteStyle.MINIMAL_API else ANSI.MAGENTA
        style_label = "Minimal API" if ep.style == RouteStyle.MINIMAL_API else "Controller"
        print(f"{ANSI.BOLD}{ep.http_method:<7}{ANSI.RESET} {ep.pattern:<32} {color}{style_label:<14}{ANSI.RESET} {ep.handler_name}")
    print(f"{'-' * 88}\n")


def display_response(res: HttpResponse, req: HttpRequest):
    status_color = ANSI.GREEN if res.status_code < 400 else ANSI.RED
    print(f"\n{ANSI.BOLD}>>> HTTP SIMULATION RESULT:{ANSI.RESET}")
    print(f"Request  : {ANSI.CYAN}{req.method} {req.path}{ANSI.RESET}")
    print(f"Status   : {status_color}{ANSI.BOLD}{res.status_code}{ANSI.RESET}")
    print(f"Latency  : {ANSI.YELLOW}{res.execution_time_ms:.3f} ms{ANSI.RESET}")
    print(f"\n{ANSI.BOLD}Diagnostic Pipeline Trace:{ANSI.RESET}")
    for step in res.pipeline_trace:
        print(f"  {ANSI.DIM}{step}{ANSI.RESET}")
    print(f"\n{ANSI.BOLD}Response Body:{ANSI.RESET}")
    print(f"{ANSI.CYAN}{res.data}{ANSI.RESET}\n")


def run_benchmark(engine: AspNetCoreRoutingEngine):
    print(f"{ANSI.YELLOW}{ANSI.BOLD}[BENCHMARK] Minimal API vs Controller Pipeline Latency (1000 iterasi){ANSI.RESET}")
    req_minimal = HttpRequest(method="GET", path="/api/v1/products/42")
    req_controller = HttpRequest(method="GET", path="/api/customers/101")

    # Warmup
    for _ in range(50):
        engine.execute_request(req_minimal)
        engine.execute_request(req_controller)

    # Measure Minimal API
    t0 = time.perf_counter()
    for _ in range(1000):
        engine.execute_request(req_minimal)
    time_minimal = (time.perf_counter() - t0) * 1000

    # Measure Controller
    t1 = time.perf_counter()
    for _ in range(1000):
        engine.execute_request(req_controller)
    time_controller = (time.perf_counter() - t1) * 1000

    print(f"\n1. {ANSI.GREEN}Minimal API (`app.MapGet`):{ANSI.RESET}       {ANSI.BOLD}{time_minimal:.2f} ms{ANSI.RESET} total (~{time_minimal/1000:.3f} ms/req)")
    print(f"2. {ANSI.MAGENTA}Controller (`[ApiController]`):{ANSI.RESET}    {ANSI.BOLD}{time_controller:.2f} ms{ANSI.RESET} total (~{time_controller/1000:.3f} ms/req)")
    ratio = time_controller / time_minimal if time_minimal > 0 else 1.0
    print(f"\n{ANSI.BOLD}Insight:{ANSI.RESET} Minimal API {ANSI.GREEN}{ratio:.1f}x lebih cepat{ANSI.RESET} karena memotong alokasi ActionDescriptor, ModelMetadata, dan filter chain MVC yang tebal.\n")


def interactive_repl(engine: AspNetCoreRoutingEngine):
    print(f"{ANSI.BOLD}Mode Interaktif: Ketik request dalam format '<METHOD> <PATH>' (e.g., 'GET /api/v1/products'){ANSI.RESET}")
    print(f"{ANSI.DIM}Ketik 'exit' atau 'back' untuk kembali ke menu utama.{ANSI.RESET}\n")
    while True:
        try:
            line = input(f"{ANSI.CYAN}dotnet-run > {ANSI.RESET}").strip()
            if not line:
                continue
            if line.lower() in ("exit", "back", "q"):
                break
            parts = line.split(maxsplit=1)
            method = parts[0].upper()
            path = parts[1] if len(parts) > 1 else "/"
            req = HttpRequest(method=method, path=path)
            res = engine.execute_request(req)
            display_response(res, req)
        except (KeyboardInterrupt, EOFError):
            print("\n")
            break


def main():
    engine = AspNetCoreRoutingEngine()
    print_banner()

    menu = (
        f"{ANSI.BOLD}Menu Simulasi ASP.NET Core Routing:{ANSI.RESET}\n"
        f"  {ANSI.CYAN}[1]{ANSI.RESET} Tampilkan Routing Table & Endpoint Metadata\n"
        f"  {ANSI.CYAN}[2]{ANSI.RESET} Test Request Minimal API (GET /api/v1/products/1)\n"
        f"  {ANSI.CYAN}[3]{ANSI.RESET} Test Request Controller (GET /api/customers/101)\n"
        f"  {ANSI.CYAN}[4]{ANSI.RESET} Test Route Constraint Fail (GET /api/v1/products/abc -> 404)\n"
        f"  {ANSI.CYAN}[5]{ANSI.RESET} Jalankan Benchmark Pipeline Minimal API vs Controller\n"
        f"  {ANSI.CYAN}[6]{ANSI.RESET} REPL Interaktif Request Terminal\n"
        f"  {ANSI.CYAN}[7]{ANSI.RESET} Keluar\n"
    )

    while True:
        print(menu)
        try:
            choice = input(f"{ANSI.BOLD}Pilih opsi [1-7]: {ANSI.RESET}").strip()
            if choice == "1":
                print_table(engine)
            elif choice == "2":
                req = HttpRequest(method="GET", path="/api/v1/products/1")
                res = engine.execute_request(req)
                display_response(res, req)
            elif choice == "3":
                req = HttpRequest(method="GET", path="/api/customers/101")
                res = engine.execute_request(req)
                display_response(res, req)
            elif choice == "4":
                req = HttpRequest(method="GET", path="/api/v1/products/abc")
                res = engine.execute_request(req)
                display_response(res, req)
            elif choice == "5":
                run_benchmark(engine)
            elif choice == "6":
                interactive_repl(engine)
            elif choice in ("7", "exit", "q"):
                print(f"{ANSI.GREEN}Simulasi selesai. Sampai jumpa!{ANSI.RESET}")
                break
            else:
                print(f"{ANSI.RED}Opsi tidak valid.{ANSI.RESET}\n")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{ANSI.GREEN}Keluar dari simulasi.{ANSI.RESET}")
            break


if __name__ == "__main__":
    main()
