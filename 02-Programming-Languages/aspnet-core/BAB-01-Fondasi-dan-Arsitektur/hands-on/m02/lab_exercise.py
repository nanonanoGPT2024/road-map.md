#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core Pipeline & Hosting Architecture Simulation
Modul: 01 (.NET Runtime, Hosting, & Request Pipeline Architecture) - Modul 02 Deep Dive

Simulasi arsitektur internal ASP.NET Core:
1. DI Container (ServiceCollection & ServiceProvider) dengan lifetime: Singleton, Scoped, Transient.
2. HttpContext & FeatureCollection model.
3. Middleware Pipeline (Russian Doll / Onion Pattern via Func<RequestDelegate, RequestDelegate>).
4. WebApplicationBuilder / WebHost lifecycle.
5. Concurrent request processing (Simulasi Kestrel server worker threads).
"""

import time
import uuid
import threading
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum, auto

# --- ANSI Terminal Color Formatting ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"

def log_info(msg: str) -> None:
    print(f"{CLR_CYAN}[INFO]{CLR_RESET} {msg}")

def log_diag(stage: str, msg: str) -> None:
    print(f"{CLR_MAGENTA}[{stage:<12}]{CLR_RESET} {msg}")

def log_success(msg: str) -> None:
    print(f"{CLR_GREEN}[SUCCESS]{CLR_RESET} {msg}")

def log_error(msg: str) -> None:
    print(f"{CLR_RED}[ERROR]{CLR_RESET} {msg}")


# --- 1. Dependency Injection Framework (Simulasi Microsoft.Extensions.DependencyInjection) ---

class ServiceLifetime(Enum):
    SINGLETON = auto()
    SCOPED = auto()
    TRANSIENT = auto()


@dataclass
class ServiceDescriptor:
    service_type: str
    implementation_factory: Callable[['ServiceProvider'], Any]
    lifetime: ServiceLifetime


class ServiceProvider:
    """Simulasi IServiceProvider yang menangani resolusi dependensi dengan scope."""
    def __init__(self, descriptors: Dict[str, ServiceDescriptor], parent_scope: Optional['ServiceProvider'] = None):
        self._descriptors = descriptors
        self._parent = parent_scope
        self._singleton_instances: Dict[str, Any] = {} if parent_scope is None else parent_scope._singleton_instances
        self._scoped_instances: Dict[str, Any] = {}

    def get_service(self, service_type: str) -> Any:
        descriptor = self._descriptors.get(service_type)
        if not descriptor:
            raise KeyError(f"Service not registered: {service_type}")

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type not in self._singleton_instances:
                self._singleton_instances[service_type] = descriptor.implementation_factory(self)
            return self._singleton_instances[service_type]

        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type not in self._scoped_instances:
                self._scoped_instances[service_type] = descriptor.implementation_factory(self)
            return self._scoped_instances[service_type]

        elif descriptor.lifetime == ServiceLifetime.TRANSIENT:
            return descriptor.implementation_factory(self)


class ServiceCollection:
    """Simulasi IServiceCollection untuk mendaftarkan dependensi sebelum BuildServiceProvider."""
    def __init__(self):
        self.descriptors: Dict[str, ServiceDescriptor] = {}

    def add_singleton(self, service_type: str, factory: Callable[[ServiceProvider], Any]):
        self.descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.SINGLETON)

    def add_scoped(self, service_type: str, factory: Callable[[ServiceProvider], Any]):
        self.descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.SCOPED)

    def add_transient(self, service_type: str, factory: Callable[[ServiceProvider], Any]):
        self.descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.TRANSIENT)

    def build_service_provider(self) -> ServiceProvider:
        return ServiceProvider(self.descriptors)


# --- 2. ASP.NET Core Abstractions (HttpContext, HttpRequest, HttpResponse) ---

@dataclass
class HttpRequest:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""


@dataclass
class HttpResponse:
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""


class HttpContext:
    """
    Representasi state request terisolasi per koneksi Kestrel.
    Menyimpan scope DI (RequestServices), item-bag, dan status IO.
    """
    def __init__(self, request: HttpRequest, service_provider: ServiceProvider):
        self.trace_identifier = str(uuid.uuid4())[:8]
        self.request = request
        self.response = HttpResponse()
        self.items: Dict[str, Any] = {}
        # Scoped container khusus untuk request ini
        self.request_services = ServiceProvider(service_provider._descriptors, parent_scope=service_provider)
        self.user: Optional[Dict[str, Any]] = None


# --- 3. Pipeline Architecture (IApplicationBuilder & Middleware Delegates) ---

RequestDelegate = Callable[[HttpContext], None]
Middleware = Callable[[RequestDelegate], RequestDelegate]


class ApplicationBuilder:
    """
    Simulasi IApplicationBuilder yang mengompilasi chain middleware
    menggunakan pola Russian Doll / Reverse Delegate Wrap.
    """
    def __init__(self, service_provider: ServiceProvider):
        self.service_provider = service_provider
        self._components: List[Middleware] = []

    def use(self, middleware: Middleware) -> 'ApplicationBuilder':
        self._components.append(middleware)
        return self

    def build(self) -> RequestDelegate:
        # Default terminal delegate jika pipeline mencapai ujung terdalam
        def terminal_delegate(context: HttpContext) -> None:
            context.response.status_code = 404
            context.response.body = '{"error": "Endpoint Not Found"}'

        pipeline = terminal_delegate
        # Reverse chaining: membungkus dari dalam ke luar
        for middleware in reversed(self._components):
            pipeline = middleware(pipeline)
        return pipeline


# --- 4. Middleware Konkret (Mirip bawaan ASP.NET Core) ---

def exception_handler_middleware(next_delegate: RequestDelegate) -> RequestDelegate:
    """Global Exception Handling (mirip app.UseExceptionHandler())."""
    def invoke(context: HttpContext) -> None:
        try:
            next_delegate(context)
        except Exception as ex:
            log_error(f"[{context.trace_identifier}] Unhandled Exception: {str(ex)}")
            context.response.status_code = 500
            context.response.body = f'{{"error": "Internal Server Error", "trace_id": "{context.trace_identifier}"}}'
    return invoke


def diagnostics_logger_middleware(next_delegate: RequestDelegate) -> RequestDelegate:
    """Request Profiler/Logger (mirip app.UseHttpLogging())."""
    def invoke(context: HttpContext) -> None:
        start_time = time.perf_counter()
        thread_name = threading.current_thread().name
        log_diag("KESTREL-IN", f"[{context.trace_identifier}] {context.request.method} {context.request.path} on {thread_name}")

        next_delegate(context)

        duration_ms = (time.perf_counter() - start_time) * 1000
        color = CLR_GREEN if context.response.status_code < 400 else CLR_RED
        log_diag("KESTREL-OUT", f"[{context.trace_identifier}] Finished with status {color}{context.response.status_code}{CLR_RESET} in {duration_ms:.2f}ms")
    return invoke


def authentication_middleware(next_delegate: RequestDelegate) -> RequestDelegate:
    """Security Claims Principal Injector (mirip app.UseAuthentication())."""
    def invoke(context: HttpContext) -> None:
        auth_header = context.request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            # Simulasi decoding JWT token
            context.user = {"sub": "usr_99182", "roles": ["Architect", "Developer"], "token": token}
            log_diag("AUTH", f"[{context.trace_identifier}] Authenticated Principal: {context.user['sub']}")
        next_delegate(context)
    return invoke


def endpoint_routing_middleware(routes: Dict[str, Callable[[HttpContext], None]]) -> Middleware:
    """Endpoint Routing & Execution Middleware (mirip app.UseRouting() + app.UseEndpoints())."""
    def middleware(next_delegate: RequestDelegate) -> RequestDelegate:
        def invoke(context: HttpContext) -> None:
            route_key = f"{context.request.method} {context.request.path}"
            handler = routes.get(route_key)
            if handler:
                log_diag("ROUTER", f"[{context.trace_identifier}] Matched Endpoint: '{route_key}'")
                handler(context)
            else:
                next_delegate(context)
        return invoke
    return middleware


# --- 5. Host & Web Server Simulator ---

class KestrelServerSimulator:
    """Simulasi Kestrel Server: menerima request, memetakan ke thread pool worker."""
    def __init__(self, root_provider: ServiceProvider, pipeline: RequestDelegate):
        self.root_provider = root_provider
        self.pipeline = pipeline

    def handle_request(self, raw_request: HttpRequest) -> HttpResponse:
        # Inisialisasi HttpContext per request beserta scoped container
        context = HttpContext(raw_request, self.root_provider)
        self.pipeline(context)
        return context.response


# --- 6. Eksekusi Lab Hands-on ---

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}=== LAB: ASP.NET Core Runtime, Hosting & Pipeline Architecture ==={CLR_RESET}\n")

    # Step 1: Konfigurasi Service Container (WebApplicationBuilder.Services)
    log_info("1. Mengonfigurasi ServiceCollection (Dependency Injection Container)...")
    services = ServiceCollection()

    # Singleton: Service shared di seluruh aplikasi
    services.add_singleton("DatabasePool", lambda sp: f"PoolConnection_{uuid.uuid4().hex[:6]}")
    # Scoped: Instance unik per satu request HttpContext
    services.add_scoped("DbContext", lambda sp: f"DbContext_{uuid.uuid4().hex[:6]} (Owner: {sp.get_service('DatabasePool')})")
    # Transient: Instance selalu baru setiap di-resolve
    services.add_transient("RequestIdGenerator", lambda sp: f"Gen_{uuid.uuid4().hex[:4]}")

    root_provider = services.build_service_provider()
    log_success("DI Container berhasil dibangun.\n")

    # Step 2: Registrasi Route Handlers (Minimal APIs/Controllers)
    def handle_api_status(ctx: HttpContext):
        # Resolve Scoped DbContext dari request scope saat ini
        scoped_db = ctx.request_services.get_service("DbContext")
        ctx.response.status_code = 200
        ctx.response.body = f'{{"status": "Healthy", "db_instance": "{scoped_db}"}}'

    def handle_secure_data(ctx: HttpContext):
        if not ctx.user:
            ctx.response.status_code = 401
            ctx.response.body = '{"error": "Unauthorized: Bearer token required"}'
            return
        scoped_db = ctx.request_services.get_service("DbContext")
        ctx.response.status_code = 200
        ctx.response.body = f'{{"user": "{ctx.user['sub']}", "data": "Classified .NET Payload", "db": "{scoped_db}"}}'

    def handle_crash_test(ctx: HttpContext):
        raise SystemError("Simulasi InvalidOperationException pada unhandled database deadlock.")

    routes = {
        "GET /health": handle_api_status,
        "GET /api/secure": handle_secure_data,
        "POST /api/fail": handle_crash_test,
    }

    # Step 3: Pembangunan Pipeline Middleware
    log_info("2. Membangun Middleware Pipeline (Onion-Architecture)...")
    app = ApplicationBuilder(root_provider)
    app.use(exception_handler_middleware)
    app.use(diagnostics_logger_middleware)
    app.use(authentication_middleware)
    app.use(endpoint_routing_middleware(routes))

    request_pipeline = app.build()
    server = KestrelServerSimulator(root_provider, request_pipeline)
    log_success("Pipeline siap memproses koneksi.\n")

    # Step 4: Simulasi Request Masuk secara Konkuren via Multi-Threading
    log_info("3. Memulai Simulasi Worker Threads Menjalankan Request Pipeline...")

    test_requests = [
        HttpRequest("GET", "/health"),
        HttpRequest("GET", "/api/secure"), # Tanpa auth header (401)
        HttpRequest("GET", "/api/secure", headers={"Authorization": "Bearer jwt.token.mock123"}), # Auth berhasil (200)
        HttpRequest("POST", "/api/fail"), # Error 500 tertangkap ExceptionHandler
        HttpRequest("GET", "/unknown/route"), # 404 Endpoint Not Found
    ]

    threads: List[threading.Thread] = []

    def dispatch(req: HttpRequest, idx: int):
        time.sleep(idx * 0.05) # Menghindari race output murni di terminal
        res = server.handle_request(req)
        print(f"    {CLR_YELLOW}Response Payload [{req.path}]:{CLR_RESET} {res.body}")

    for idx, req in enumerate(test_requests):
        t = threading.Thread(target=dispatch, args=(req, idx), name=f".NET-ThreadPool-W{idx+1}")
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print(f"\n{CLR_BOLD}{CLR_GREEN}=== LAB SELESAI: Arsitektur Pipeline Berhasil Disimulasikan ==={CLR_RESET}")


if __name__ == "__main__":
    main()