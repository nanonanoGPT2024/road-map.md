#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core Modern Web API & Routing: Minimal API vs Controllers
Bab 03 - Modul 02 Deep Dive

Simulasi arsitektural internal ASP.NET Core Kestrel HTTP Pipeline:
1. Controller-Based Routing:
   - Dynamic reflection & method metadata inspection.
   - Per-request Controller Activation (IControllerActivator via DI Scope).
   - Full MVC Action Execution Pipeline (Action Filters, Action Context, Result Executing).
2. Minimal API Routing:
   - Direct Endpoint Routing via RouteEndpoint.
   - Pre-compiled RequestDelegate / Direct Invocation.
   - Zero-allocation per-request pipeline & lightweight Endpoint Filters.
3. Benchmarking Engine:
   - Pengukuran Throughput (ops/sec), Latency distribution (P50, P99),
     serta Alokasi Objek Runtime (Allocation Footprint).
"""

import inspect
import re
import time
import statistics
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Optional, Tuple

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"
CLR_BLUE = "\033[34m"

# --- HTTP Pipeline Primitives ---
@dataclass
class HttpRequest:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    route_values: Dict[str, str] = field(default_factory=dict)

@dataclass
class HttpResponse:
    status_code: int = 200
    body: Any = None
    headers: Dict[str, str] = field(default_factory=dict)

@dataclass
class HttpContext:
    request: HttpRequest
    response: HttpResponse = field(default_factory=HttpResponse)
    items: Dict[str, Any] = field(default_factory=dict)

# Global tracker untuk simulasi alokasi memori runtime (GC pressure)
ALLOCATION_COUNTER = 0

def track_allocation(obj_name: str):
    """Mencatat alokasi objek untuk mensimulasikan GC allocations di CLR Heap."""
    global ALLOCATION_COUNTER
    ALLOCATION_COUNTER += 1


# --- Controller-Based Pipeline Emulation ---
class ControllerBase:
    """Basis kelas controller yang di-instantiate per-request oleh IControllerActivator."""
    def __init__(self):
        track_allocation("ControllerInstance")
        self.http_context: Optional[HttpContext] = None

    def ok(self, data: Any) -> HttpResponse:
        track_allocation("OkObjectResult")
        return HttpResponse(status_code=200, body=data)

    def not_found(self, message: str = "Not Found") -> HttpResponse:
        track_allocation("NotFoundResult")
        return HttpResponse(status_code=404, body={"error": message})


def http_get(template: str):
    """Atribut dekorator untuk metadata Action Controller."""
    def decorator(func: Callable):
        func.__http_method__ = "GET"
        func.__route_template__ = template
        return func
    return decorator


def api_controller(route_prefix: str):
    """Atribut dekorator untuk menandai kelas sebagai API Controller."""
    def decorator(cls):
        cls.__is_controller__ = True
        cls.__route_prefix__ = route_prefix.strip("/")
        return cls
    return decorator


class ActionExecutingContext:
    """Context wrapper untuk Action Filter Pipeline."""
    def __init__(self, http_context: HttpContext, controller: Any, action_name: str):
        track_allocation("ActionExecutingContext")
        self.http_context = http_context
        self.controller = controller
        self.action_name = action_name
        self.cancel = False


class ControllerActionDescriptor:
    """Metadata hasil scanning Controller Action via Reflection saat Startup."""
    def __init__(self, controller_cls: type, action_name: str, http_method: str, route_regex: re.Pattern, param_keys: List[str]):
        self.controller_cls = controller_cls
        self.action_name = action_name
        self.http_method = http_method
        self.route_regex = route_regex
        self.param_keys = param_keys


class ControllerPipelineDispatcher:
    """
    Simulasi ControllerActionInvoker ASP.NET Core:
    Mencakup lifecycle: Activator -> ActionFilters -> Method Invoke -> Result Execution.
    """
    def __init__(self):
        self.actions: List[ControllerActionDescriptor] = []

    def register_controller(self, controller_cls: type):
        """Memeriksa metadata Controller dengan Reflection (inspect)."""
        prefix = getattr(controller_cls, "__route_prefix__", "")
        for attr_name in dir(controller_cls):
            method = getattr(controller_cls, attr_name)
            if callable(method) and hasattr(method, "__http_method__"):
                http_method = method.__http_method__
                template = method.__route_template__.strip("/")
                full_pattern = f"/{prefix}/{template}".strip("/")
                
                # Ubah route template seperti 'users/{id}' menjadi regex
                param_keys = re.findall(r"\{(\w+)\}", full_pattern)
                regex_str = "^/" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", full_pattern) + "$"
                
                descriptor = ControllerActionDescriptor(
                    controller_cls=controller_cls,
                    action_name=attr_name,
                    http_method=http_method,
                    route_regex=re.compile(regex_str),
                    param_keys=param_keys
                )
                self.actions.append(descriptor)

    def dispatch(self, context: HttpContext) -> Optional[HttpResponse]:
        for descriptor in self.actions:
            if descriptor.http_method != context.request.method:
                continue
            
            match = descriptor.route_regex.match(context.request.path)
            if match:
                context.request.route_values = match.groupdict()
                
                # 1. Controller Activation (IControllerActivator via DI Container)
                controller_instance = descriptor.controller_cls()
                controller_instance.http_context = context

                # 2. Action Filter Pipeline: OnActionExecuting
                filter_ctx = ActionExecutingContext(context, controller_instance, descriptor.action_name)
                
                # 3. Model Binding & Dynamic Method Invocation
                method = getattr(controller_instance, descriptor.action_name)
                sig = inspect.signature(method)
                kwargs = {}
                for param_name in sig.parameters:
                    if param_name in context.request.route_values:
                        kwargs[param_name] = context.request.route_values[param_name]

                track_allocation("ActionInvocationFrame")
                result: HttpResponse = method(**kwargs)
                
                # 4. Action Filter Pipeline: OnActionExecuted
                track_allocation("ActionExecutedContext")
                return result
        return None


# --- Minimal API Pipeline Emulation ---
@dataclass
class RouteEndpoint:
    """Representasi ASP.NET Core RouteEndpoint (Direct Delegate Execution)."""
    http_method: str
    route_regex: re.Pattern
    param_keys: List[str]
    handler: Callable[[HttpContext, Any], HttpResponse]


class MinimalApiEndpointRouteBuilder:
    """
    Simulasi WebApplication Minimal API Endpoint Routing:
    Memetakan URL langsung ke RequestDelegate tanpa overhead MVC Controller pipeline.
    """
    def __init__(self):
        self.endpoints: List[RouteEndpoint] = []

    def map_get(self, pattern: str, handler: Callable[..., HttpResponse]):
        clean_pattern = pattern.strip("/")
        param_keys = re.findall(r"\{(\w+)\}", clean_pattern)
        regex_str = "^/" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", clean_pattern) + "$"
        
        endpoint = RouteEndpoint(
            http_method="GET",
            route_regex=re.compile(regex_str),
            param_keys=param_keys,
            handler=handler
        )
        self.endpoints.append(endpoint)

    def dispatch(self, context: HttpContext) -> Optional[HttpResponse]:
        # Direct Endpoint Matching & RequestDelegate Execution
        for ep in self.endpoints:
            if ep.http_method != context.request.method:
                continue
            
            match = ep.route_regex.match(context.request.path)
            if match:
                context.request.route_values = match.groupdict()
                # Langsung eksekusi target delegate tanpa instansiasi controller class
                return ep.handler(context, **context.request.route_values)
        return None


# --- Definisi Endpoint Implementasi ---

# 1. Controller Implementation
@api_controller("api/v1/controllers")
class UsersController(ControllerBase):
    def __init__(self):
        super().__init__()
        self.db = {"101": "Satya Nadella", "102": "Scott Hanselman"}

    @http_get("users/{id}")
    def get_user_by_id(self, id: str) -> HttpResponse:
        if id in self.db:
            return self.ok({"id": id, "name": self.db[id], "arch": "Controller"})
        return self.not_found("User does not exist")


# 2. Minimal API Implementation Setup
def configure_minimal_apis(builder: MinimalApiEndpointRouteBuilder):
    db = {"101": "Satya Nadella", "102": "Scott Hanselman"}

    def get_user_handler(ctx: HttpContext, id: str) -> HttpResponse:
        # Minimal API: Fast path, direct return tanpa intermediary action filter objects
        if id in db:
            return HttpResponse(status_code=200, body={"id": id, "name": db[id], "arch": "MinimalAPI"})
        return HttpResponse(status_code=404, body={"error": "User does not exist"})

    builder.map_get("/api/v1/minimal/users/{id}", get_user_handler)


# --- Benchmark Harness ---
def run_benchmark(name: str, dispatch_fn: Callable[[HttpContext], Optional[HttpResponse]], sample_requests: List[HttpRequest], iterations: int) -> Tuple[float, float, float, int]:
    """
    Mengeksekusi benchmark throughput, latensi percentile, dan konsumsi alokasi objek.
    """
    global ALLOCATION_COUNTER
    ALLOCATION_COUNTER = 0

    latencies_ns: List[int] = []
    total_reqs = len(sample_requests) * iterations
    
    start_total = time.perf_counter()
    for _ in range(iterations):
        for req in sample_requests:
            ctx = HttpContext(request=req)
            t_start = time.perf_counter_ns()
            res = dispatch_fn(ctx)
            t_end = time.perf_counter_ns()
            
            assert res is not None and res.status_code == 200, "Request handling failed!"
            latencies_ns.append(t_end - t_start)
    end_total = time.perf_counter()

    elapsed_sec = end_total - start_total
    ops_per_sec = total_reqs / elapsed_sec
    p50_us = statistics.median(latencies_ns) / 1000.0
    p99_us = statistics.quantiles(latencies_ns, n=100)[98] / 1000.0
    allocations = ALLOCATION_COUNTER

    return ops_per_sec, p50_us, p99_us, allocations


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  ASP.NET Core Architecture Lab: Minimal APIs vs Controllers Pipeline {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

    # Inisialisasi Dispatcher & Routing Tables
    controller_dispatcher = ControllerPipelineDispatcher()
    controller_dispatcher.register_controller(UsersController)

    minimal_builder = MinimalApiEndpointRouteBuilder()
    configure_minimal_apis(minimal_builder)

    print(f"{CLR_BOLD}[1] Endpoint Routing Table Initialization:{CLR_RESET}")
    for action in controller_dispatcher.actions:
        print(f"  {CLR_MAGENTA}[Controller Route]{CLR_RESET}  {action.http_method} {action.route_regex.pattern} -> {action.controller_cls.__name__}.{action.action_name}")
    for ep in minimal_builder.endpoints:
        print(f"  {CLR_GREEN}[Minimal Endpoint]{CLR_RESET} {ep.http_method} {ep.route_regex.pattern} -> RequestDelegate (FuncPtr: 0x{id(ep.handler):X})")

    print(f"\n{CLR_BOLD}[2] Pipeline Verification & Sanity Checks:{CLR_RESET}")
    test_req_ctrl = HttpRequest("GET", "/api/v1/controllers/users/101")
    test_req_min = HttpRequest("GET", "/api/v1/minimal/users/101")

    res_ctrl = controller_dispatcher.dispatch(HttpContext(request=test_req_ctrl))
    res_min = minimal_builder.dispatch(HttpContext(request=test_req_min))

    print(f"  - Controller Response: StatusCode={res_ctrl.status_code}, Body={res_ctrl.body}")
    print(f"  - Minimal API Response: StatusCode={res_min.status_code}, Body={res_min.body}")

    print(f"\n{CLR_BOLD}[3] High-Throughput Microbenchmark Execution (5,000 requests per pipeline):{CLR_RESET}")
    iterations = 2500
    requests_ctrl = [
        HttpRequest("GET", "/api/v1/controllers/users/101"),
        HttpRequest("GET", "/api/v1/controllers/users/102")
    ]
    requests_min = [
        HttpRequest("GET", "/api/v1/minimal/users/101"),
        HttpRequest("GET", "/api/v1/minimal/users/102")
    ]

    ctrl_ops, ctrl_p50, ctrl_p99, ctrl_allocs = run_benchmark(
        "Controller", controller_dispatcher.dispatch, requests_ctrl, iterations
    )
    min_ops, min_p50, min_p99, min_allocs = run_benchmark(
        "Minimal API", minimal_builder.dispatch, requests_min, iterations
    )

    # Output Benchmark Table
    print("\n" + "-" * 75)
    print(f"{CLR_BOLD}{'Metric':<25} | {'Controllers':<22} | {'Minimal APIs':<22}{CLR_RESET}")
    print("-" * 75)
    print(f"{'Throughput (req/s)':<25} | {CLR_YELLOW}{ctrl_ops:18.1f} req/s{CLR_RESET} | {CLR_GREEN}{min_ops:18.1f} req/s{CLR_RESET}")
    print(f"{'Latency P50 (median)':<25} | {ctrl_p50:18.2f} us    | {CLR_GREEN}{min_p50:18.2f} us{CLR_RESET}")
    print(f"{'Latency P99 (tail)':<25} | {ctrl_p99:18.2f} us    | {CLR_GREEN}{min_p99:18.2f} us{CLR_RESET}")
    print(f"{'Simulated Heap Allocs':<25} | {CLR_RED}{ctrl_allocs:18,d} objs{CLR_RESET}  | {CLR_GREEN}{min_allocs:18,d} objs{CLR_RESET}")
    print("-" * 75)

    speedup = ((min_ops - ctrl_ops) / ctrl_ops) * 100.0
    alloc_reduction = ((ctrl_allocs - min_allocs) / ctrl_allocs) * 100.0

    print(f"\n{CLR_BOLD}[4] Technical Analysis & Deep Dive Findings:{CLR_RESET}")
    print(f"  * {CLR_BOLD}Throughput Gain:{CLR_RESET} Minimal API menghasilkan {CLR_GREEN}+{speedup:.1f}%{CLR_RESET} lebih tinggi.")
    print(f"  * {CLR_BOLD}Memory Allocations:{CLR_RESET} Minimal API mereduksi overhead objek hingga {CLR_GREEN}{alloc_reduction:.1f}%{CLR_RESET}.")
    print(f"  * {CLR_BOLD}Arsitektural Controller:{CLR_RESET} Membutuhkan alokasi ControllerInstance, ActionExecutingContext,")
    print("    ActionExecutedContext, dan dynamic reflection frame setiap request masuk.")
    print(f"  * {CLR_BOLD}Arsitektural Minimal API:{CLR_RESET} Mengabaikan MVC Filter Pipeline & Action Invoker;")
    print("    routing langsung terikat pada `RequestDelegate` endpoint yang dioptimasi oleh JIT.")
    print(f"\n{CLR_CYAN}Lab exercise selesai dengan status: SUCCESS.{CLR_RESET}\n")

if __name__ == "__main__":
    main()