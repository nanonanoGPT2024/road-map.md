#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Arsitektur Produksi ASP.NET Core
Materi: BAB-01-Fondasi-dan-Arsitektur
Deskripsi:
    Simulasi mandiri siklus hidup runtime ASP.NET Core:
    - WebApplicationBuilder & Generic Host lifecycle
    - Dependency Injection Container (Singleton, Scoped, Transient lifetimes)
    - Captive Dependency Detector (Scope validation pada Singleton)
    - Middleware Pipeline Execution (Onion Architecture / Request Pipeline)
    - Health Checks & Diagnostic Logging dengan ANSI color terminal
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


# ==========================================
# 1. ANSI Terminal Color Palette
# ==========================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Background
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_RED = "\033[41m"
    BG_DARK = "\033[40m"


def header(text: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {text} === {Color.RESET}")


def subheader(text: str) -> None:
    print(f"\n{Color.CYAN}{Color.BOLD}>>> {text}{Color.RESET}")


def success(text: str) -> None:
    print(f"  {Color.GREEN}✔ {text}{Color.RESET}")


def info(text: str) -> None:
    print(f"  {Color.BLUE}ℹ {text}{Color.RESET}")


def warn(text: str) -> None:
    print(f"  {Color.YELLOW}⚠ {text}{Color.RESET}")


def error(text: str) -> None:
    print(f"  {Color.RED}✖ {text}{Color.RESET}")


# ==========================================
# 2. Dependency Injection Engine (IoC Container)
# ==========================================
class ServiceLifetime(Enum):
    TRANSIENT = auto()
    SCOPED = auto()
    SINGLETON = auto()


@dataclass
class ServiceDescriptor:
    service_type: str
    implementation_factory: Callable[['ServiceProvider'], Any]
    lifetime: ServiceLifetime


class ServiceScope:
    def __init__(self, provider: 'ServiceProvider'):
        self.root_provider = provider
        self.scoped_instances: Dict[str, Any] = {}
        self.scope_id = str(uuid.uuid4())[:8]

    def get_service(self, service_type: str) -> Any:
        return self.resolve(service_type)

    def resolve(self, service_type: str) -> Any:
        return self.root_provider._resolve_internal(service_type, self)

    def dispose(self) -> None:
        self.scoped_instances.clear()


class ServiceProvider:
    def __init__(self, descriptors: Dict[str, ServiceDescriptor], validate_scopes: bool = True):
        self.descriptors = descriptors
        self.validate_scopes = validate_scopes
        self.singleton_instances: Dict[str, Any] = {}

    def create_scope(self) -> ServiceScope:
        return ServiceScope(self)

    def get_service(self, service_type: str) -> Any:
        return self._resolve_internal(service_type, current_scope=None)

    def _resolve_internal(self, service_type: str, current_scope: Optional[ServiceScope]) -> Any:
        if service_type not in self.descriptors:
            raise KeyError(f"Layanan '{service_type}' belum didaftarkan di IServiceCollection.")

        descriptor = self.descriptors[service_type]

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type not in self.singleton_instances:
                # Singleton selalu menggunakan root provider sebagai resolver
                self.singleton_instances[service_type] = descriptor.implementation_factory(self)
            return self.singleton_instances[service_type]

        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if current_scope is None:
                if self.validate_scopes:
                    raise RuntimeError(
                        f"Captive Dependency Error: Layanan Scoped '{service_type}' "
                        f"diakses langsung dari Root Provider tanpa HTTP Request Scope!"
                    )
                return descriptor.implementation_factory(self)
            
            if service_type not in current_scope.scoped_instances:
                current_scope.scoped_instances[service_type] = descriptor.implementation_factory(current_scope)
            return current_scope.scoped_instances[service_type]

        elif descriptor.lifetime == ServiceLifetime.TRANSIENT:
            resolver = current_scope if current_scope is not None else self
            return descriptor.implementation_factory(resolver)

        raise ValueError(f"Unknown lifetime: {descriptor.lifetime}")


class ServiceCollection:
    def __init__(self):
        self._descriptors: Dict[str, ServiceDescriptor] = {}

    def add_transient(self, service_type: str, factory: Callable[[ServiceProvider], Any]) -> 'ServiceCollection':
        self._descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.TRANSIENT)
        return self

    def add_scoped(self, service_type: str, factory: Callable[[ServiceProvider], Any]) -> 'ServiceCollection':
        self._descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.SCOPED)
        return self

    def add_singleton(self, service_type: str, factory: Callable[[ServiceProvider], Any]) -> 'ServiceCollection':
        self._descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.SINGLETON)
        return self

    def build_service_provider(self, validate_scopes: bool = True) -> ServiceProvider:
        return ServiceProvider(self._descriptors, validate_scopes=validate_scopes)


# ==========================================
# 3. HTTP Context & Middleware Pipeline
# ==========================================
@dataclass
class HttpRequest:
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None


@dataclass
class HttpResponse:
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None


class HttpContext:
    def __init__(self, request: HttpRequest, scope: ServiceScope):
        self.request = request
        self.response = HttpResponse()
        self.request_services = scope
        self.trace_id = str(uuid.uuid4())[:12]
        self.items: Dict[str, Any] = {}


RequestDelegate = Callable[[HttpContext], None]
MiddlewareFactory = Callable[[RequestDelegate], RequestDelegate]


class ApplicationBuilder:
    def __init__(self, service_provider: ServiceProvider):
        self.service_provider = service_provider
        self._components: List[MiddlewareFactory] = []

    def use(self, middleware: MiddlewareFactory) -> 'ApplicationBuilder':
        self._components.append(middleware)
        return self

    def build_pipeline(self) -> RequestDelegate:
        # Terminal delegate (404 Not Found default handler)
        def endpoint_fallback(context: HttpContext) -> None:
            if context.response.body is None:
                context.response.status_code = 404
                context.response.body = '{"status": 404, "error": "Endpoint not found"}'

        pipeline = endpoint_fallback
        for middleware in reversed(self._components):
            pipeline = middleware(pipeline)
        return pipeline


# ==========================================
# 4. Standard ASP.NET Core Middleware Implementations
# ==========================================
def use_exception_handler(next_middleware: RequestDelegate) -> RequestDelegate:
    def invoke(context: HttpContext) -> None:
        print(f"  {Color.DIM}[Pipeline -> ExceptionHandlerMiddleware]{Color.RESET}")
        try:
            next_middleware(context)
        except Exception as ex:
            error(f"ExceptionHandler menangkap fatal exception: {ex}")
            context.response.status_code = 500
            context.response.body = f'{{"status": 500, "error": "Internal Server Error", "details": "{str(ex)}"}}'
        print(f"  {Color.DIM}[Pipeline <- ExceptionHandlerMiddleware Handled]{Color.RESET}")
    return invoke


def use_request_logging(next_middleware: RequestDelegate) -> RequestDelegate:
    def invoke(context: HttpContext) -> None:
        start_time = time.perf_counter()
        print(f"  {Color.DIM}[Pipeline -> RequestLoggingMiddleware] Incoming {context.request.method} {context.request.path} (Trace: {context.trace_id}){Color.RESET}")
        next_middleware(context)
        duration_ms = (time.perf_counter() - start_time) * 1000
        print(f"  {Color.DIM}[Pipeline <- RequestLoggingMiddleware] HTTP {context.response.status_code} in {duration_ms:.2f}ms{Color.RESET}")
    return invoke


def use_authentication(next_middleware: RequestDelegate) -> RequestDelegate:
    def invoke(context: HttpContext) -> None:
        print(f"  {Color.DIM}[Pipeline -> AuthenticationMiddleware]{Color.RESET}")
        auth_header = context.request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            context.items["User"] = f"user_{token[:6]}"
            info(f"Autentikasi Berhasil: Dikenali sebagai {context.items['User']}")
        else:
            context.items["User"] = "Anonymous"
            warn("Autentikasi: Request Tanpa Token Bearer (Anonymous User)")
        next_middleware(context)
        print(f"  {Color.DIM}[Pipeline <- AuthenticationMiddleware]{Color.RESET}")
    return invoke


def use_endpoints(routes: Dict[str, Callable[[HttpContext], None]]) -> MiddlewareFactory:
    def factory(next_middleware: RequestDelegate) -> RequestDelegate:
        def invoke(context: HttpContext) -> None:
            key = f"{context.request.method} {context.request.path}"
            print(f"  {Color.DIM}[Pipeline -> EndpointRoutingMiddleware] Matching route: {key}{Color.RESET}")
            if key in routes:
                routes[key](context)
            else:
                next_middleware(context)
            print(f"  {Color.DIM}[Pipeline <- EndpointRoutingMiddleware]{Color.RESET}")
        return invoke
    return factory


# ==========================================
# 5. Domain Services Sample (E-Commerce Order)
# ==========================================
class DatabaseConnection:
    """Scoped Service: Mewakili DbContext per HTTP request"""
    def __init__(self):
        self.conn_id = str(uuid.uuid4())[:6]
        info(f"DbContext [{self.conn_id}]: Koneksi database dibuka.")

    def query(self, sql: str) -> str:
        return f"Result<{sql}> via Conn[{self.conn_id}]"


class OrderRepository:
    """Scoped Service: Menggunakan DbContext"""
    def __init__(self, db: DatabaseConnection):
        self.db = db

    def create_order(self, customer: str, item: str) -> str:
        return f"Order[Cust={customer}, Item={item}] tersimpan ({self.db.query('INSERT ORDER')})"


class SystemClock:
    """Singleton Service: Thread-safe global instance"""
    def __init__(self):
        self.init_time = time.strftime("%Y-%m-%d %H:%M:%S")

    def utc_now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ")


class SecurityHasher:
    """Transient Service: Dibuat baru setiap resolusi"""
    def __init__(self):
        self.salt = str(uuid.uuid4())[:4]

    def hash(self, data: str) -> str:
        return f"SHA256:{hash(data + self.salt)}"


# ==========================================
# 6. Interactive Simulator Application
# ==========================================
class AspNetCoreSimulator:
    def __init__(self):
        self.services = ServiceCollection()
        self.provider: Optional[ServiceProvider] = None
        self.pipeline: Optional[RequestDelegate] = None
        self._setup_services()
        self._setup_pipeline()

    def _setup_services(self) -> None:
        # Pendaftaran Dependency Injection
        self.services.add_singleton("ISystemClock", lambda sp: SystemClock())
        self.services.add_scoped("DatabaseConnection", lambda sp: DatabaseConnection())
        self.services.add_scoped("OrderRepository", lambda sp: OrderRepository(sp.get_service("DatabaseConnection")))
        self.services.add_transient("SecurityHasher", lambda sp: SecurityHasher())
        self.provider = self.services.build_service_provider(validate_scopes=True)

    def _setup_pipeline(self) -> None:
        builder = ApplicationBuilder(self.provider)

        # Mapping Endpoint Controllers
        def handle_health(ctx: HttpContext) -> None:
            clock: SystemClock = ctx.request_services.resolve("ISystemClock")
            ctx.response.status_code = 200
            ctx.response.body = f'{{"status": "Healthy", "timestamp": "{clock.utc_now()}"}}'

        def handle_create_order(ctx: HttpContext) -> None:
            user = ctx.items.get("User", "Guest")
            repo: OrderRepository = ctx.request_services.resolve("OrderRepository")
            res = repo.create_order(user, ctx.request.body or "Item-Default")
            ctx.response.status_code = 201
            ctx.response.body = f'{{"status": "Created", "message": "{res}"}}'

        def handle_fault(ctx: HttpContext) -> None:
            raise RuntimeError("Database deadlock saat transaksi checkout!")

        routes = {
            "GET /health": handle_health,
            "POST /api/orders": handle_create_order,
            "GET /api/fault": handle_fault
        }

        builder.use(use_exception_handler)
        builder.use(use_request_logging)
        builder.use(use_authentication)
        builder.use(use_endpoints(routes))

        self.pipeline = builder.build_pipeline()

    def dispatch_request(self, method: str, path: str, headers: Dict[str, str], body: Optional[str] = None) -> None:
        header(f"DISPATCH HTTP: {method} {path}")
        req = HttpRequest(method=method, path=path, headers=headers, body=body)
        
        # Setiap HTTP Request membuat ServiceScope baru
        scope = self.provider.create_scope()
        info(f"Kestrel Server: Membuka HTTP Request Scope [{scope.scope_id}]")
        
        ctx = HttpContext(req, scope)
        try:
            self.pipeline(ctx)
        finally:
            scope.dispose()
            info(f"Kestrel Server: Request Selesai. Dispose HTTP Scope [{scope.scope_id}].")

        print(f"\n{Color.BOLD}HTTP Response Received:{Color.RESET}")
        color = Color.GREEN if ctx.response.status_code < 400 else Color.RED
        print(f"  Status : {color}{ctx.response.status_code}{Color.RESET}")
        print(f"  Body   : {Color.YELLOW}{ctx.response.body}{Color.RESET}\n")

    def test_captive_dependency(self) -> None:
        header("SIMULASI: Captive Dependency Detection")
        info("Mencoba meregistrasi Scoped Service ke dalam Singleton...")
        
        test_services = ServiceCollection()
        test_services.add_scoped("ScopedDb", lambda sp: DatabaseConnection())
        
        # Bad design: Singleton menahan Scoped service
        test_services.add_singleton("BadSingleton", lambda sp: {
            "db": sp.get_service("ScopedDb")
        })
        
        provider = test_services.build_service_provider(validate_scopes=True)
        try:
            warn("Mengakses 'BadSingleton' langsung dari root provider...")
            _ = provider.get_service("BadSingleton")
            error("Gagal mendeteksi Captive Dependency!")
        except RuntimeError as ex:
            success(f"Berhasil mendeteksi Captive Dependency Exception:")
            print(f"    {Color.RED}{ex}{Color.RESET}")
            info("ASP.NET Core mencegah memory leak dan concurrency bug pada scoped state!")

    def inspect_lifetimes(self) -> None:
        header("DEMONSTRASI LIFETIME: Transient vs Scoped vs Singleton")
        scope1 = self.provider.create_scope()
        scope2 = self.provider.create_scope()

        # Singleton Check
        s1 = scope1.resolve("ISystemClock")
        s2 = scope2.resolve("ISystemClock")
        print(f"  Singleton Instance ID: Scope1={id(s1)} == Scope2={id(s2)}: {Color.GREEN}{id(s1) == id(s2)}{Color.RESET}")

        # Scoped Check
        db1_a = scope1.resolve("DatabaseConnection")
        db1_b = scope1.resolve("DatabaseConnection")
        db2_a = scope2.resolve("DatabaseConnection")
        print(f"  Scoped (Scope1 sama) : db1_a={id(db1_a)} == db1_b={id(db1_b)}: {Color.GREEN}{id(db1_a) == id(db1_b)}{Color.RESET}")
        print(f"  Scoped (Beda scope)  : db1_a={id(db1_a)} == db2_a={id(db2_a)}: {Color.YELLOW}{id(db1_a) == id(db2_a)}{Color.RESET}")

        # Transient Check
        t1 = scope1.resolve("SecurityHasher")
        t2 = scope1.resolve("SecurityHasher")
        print(f"  Transient (Scope1)   : t1={id(t1)} == t2={id(t2)}: {Color.YELLOW}{id(t1) == id(t2)} (Setiap inject instans baru){Color.RESET}")

        scope1.dispose()
        scope2.dispose()


def interactive_menu() -> None:
    simulator = AspNetCoreSimulator()

    while True:
        print(f"\n{Color.BG_MAGENTA}{Color.WHITE}{Color.BOLD} LAB EXERCISE: ARSITEKTUR RUNTIME ASP.NET CORE {Color.RESET}")
        print(f"{Color.CYAN}Pilih skenario pengujian runtime:{Color.RESET}")
        print("  [1] Kirim Request GET /health (Kestrel Pipeline + Singleton Clock)")
        print("  [2] Kirim Request POST /api/orders (Authenticated + Scoped DbContext)")
        print("  [3] Kirim Request POST /api/orders (Anonymous + Scoped DbContext)")
        print("  [4] Kirim Request GET /api/fault (Global Exception Handling Middleware)")
        print("  [5] Uji Validasi Captive Dependency (Singleton -> Scoped Trap)")
        print("  [6] Audit Objek Memory (Transient vs Scoped vs Singleton ID)")
        print("  [7] Jalankan Semua Skenario Otomatis (Full Automated Verification)")
        print("  [0] Keluar")

        choice = input(f"\n{Color.BOLD}Masukkan pilihan (0-7): {Color.RESET}").strip()
        if choice == "1":
            simulator.dispatch_request("GET", "/health", {})
        elif choice == "2":
            simulator.dispatch_request(
                "POST", 
                "/api/orders", 
                {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}, 
                body="Laptop-Pro-16"
            )
        elif choice == "3":
            simulator.dispatch_request("POST", "/api/orders", {}, body="Keyboard-Mechanical")
        elif choice == "4":
            simulator.dispatch_request("GET", "/api/fault", {})
        elif choice == "5":
            simulator.test_captive_dependency()
        elif choice == "6":
            simulator.inspect_lifetimes()
        elif choice == "7":
            print(f"\n{Color.YELLOW}Menjalankan uji otomatis seluruh subsistem...{Color.RESET}")
            simulator.dispatch_request("GET", "/health", {})
            simulator.dispatch_request("POST", "/api/orders", {"Authorization": "Bearer token123"}, "Server-Rack-U4")
            simulator.dispatch_request("GET", "/api/fault", {})
            simulator.test_captive_dependency()
            simulator.inspect_lifetimes()
            success("Seluruh skenario pengujian arsitektur selesai dijalankan tanpa error fatal.")
        elif choice == "0":
            print(f"{Color.GREEN}Terima kasih telah mempelajari arsitektur produksi ASP.NET Core!{Color.RESET}")
            break
        else:
            warn("Pilihan tidak valid, silakan ulangi.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        sim = AspNetCoreSimulator()
        sim.dispatch_request("GET", "/health", {})
        sim.dispatch_request("POST", "/api/orders", {"Authorization": "Bearer tokensecret"}, "AutoItem")
        sim.test_captive_dependency()
        sim.inspect_lifetimes()
        sys.exit(0)
    interactive_menu()
