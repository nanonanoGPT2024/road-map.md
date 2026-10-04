#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi dan Arsitektur ASP.NET Core
Materi: BAB-01 Fondasi dan Arsitektur (.NET Generic Host, Middleware Pipeline, DI Container)

Skrip ini mereplikasi cara kerja internal runtime ASP.NET Core:
1. IServiceCollection & IServiceProvider (Dependency Injection: Transient, Scoped, Singleton)
2. HttpContext & Middleware Pipeline (Delegates, Request Pipeline, Onion Architecture)
3. WebHost runtime life-cycle & request processing
"""

import sys
import time
import uuid
from enum import Enum
from typing import Callable, Dict, List, Any, Optional

# ANSI Color Codes untuk visualisasi terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"
    BG_BLUE = "\033[44m"
    WHITE = "\033[97m"

def print_banner():
    print(f"{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}{Color.BG_BLUE}   ASP.NET CORE RUNTIME SIMULATOR: BAB 01 - FONDASI & ARSITEKTUR   {Color.RESET}")
    print(f"{Color.CYAN}{'=' * 75}{Color.RESET}\n")

# -----------------------------------------------------------------------------
# 1. DEPENDENCY INJECTION ENGINE (Simulasi Microsoft.Extensions.DependencyInjection)
# -----------------------------------------------------------------------------
class ServiceLifetime(Enum):
    TRANSIENT = "Transient (Instance baru setiap resolve)"
    SCOPED = "Scoped (Instance tunggal per request/scope)"
    SINGLETON = "Singleton (Instance tunggal sepanjang umur aplikasi)"

class ServiceDescriptor:
    def __init__(self, service_type: str, implementation_factory: Callable[[], Any], lifetime: ServiceLifetime):
        self.service_type = service_type
        self.factory = implementation_factory
        self.lifetime = lifetime
        self.singleton_instance = None

class ServiceScope:
    def __init__(self, provider: 'ServiceProvider'):
        self.provider = provider
        self.scoped_instances: Dict[str, Any] = {}

    def resolve(self, service_type: str) -> Any:
        return self.provider.resolve(service_type, self)

class ServiceCollection:
    def __init__(self):
        self.descriptors: Dict[str, ServiceDescriptor] = {}

    def add_transient(self, service_name: str, factory: Callable[[], Any]):
        self.descriptors[service_name] = ServiceDescriptor(service_name, factory, ServiceLifetime.TRANSIENT)

    def add_scoped(self, service_name: str, factory: Callable[[], Any]):
        self.descriptors[service_name] = ServiceDescriptor(service_name, factory, ServiceLifetime.SCOPED)

    def add_singleton(self, service_name: str, factory: Callable[[], Any]):
        self.descriptors[service_name] = ServiceDescriptor(service_name, factory, ServiceLifetime.SINGLETON)

    def build_service_provider(self) -> 'ServiceProvider':
        return ServiceProvider(self.descriptors)

class ServiceProvider:
    def __init__(self, descriptors: Dict[str, ServiceDescriptor]):
        self.descriptors = descriptors

    def create_scope(self) -> ServiceScope:
        return ServiceScope(self)

    def resolve(self, service_type: str, scope: Optional[ServiceScope] = None) -> Any:
        if service_type not in self.descriptors:
            raise KeyError(f"Service '{service_type}' belum diregistrasikan di IServiceCollection.")
        
        desc = self.descriptors[service_type]

        if desc.lifetime == ServiceLifetime.SINGLETON:
            if desc.singleton_instance is None:
                desc.singleton_instance = desc.factory()
            return desc.singleton_instance

        elif desc.lifetime == ServiceLifetime.SCOPED:
            if scope is None:
                raise RuntimeError(f"Tidak dapat me-resolve Scoped service '{service_type}' dari Root Provider!")
            if service_type not in scope.scoped_instances:
                scope.scoped_instances[service_type] = desc.factory()
            return scope.scoped_instances[service_type]

        elif desc.lifetime == ServiceLifetime.TRANSIENT:
            return desc.factory()

# Layanan dummy untuk demonstrasi
class GuidService:
    def __init__(self, tag: str):
        self.tag = tag
        self.id = str(uuid.uuid4())[:8]

# -----------------------------------------------------------------------------
# 2. HTTP CONTEXT & MIDDLEWARE PIPELINE (Simulasi Kestrel & RequestDelegate)
# -----------------------------------------------------------------------------
class HttpRequest:
    def __init__(self, path: str, method: str = "GET", headers: Optional[Dict[str, str]] = None):
        self.path = path
        self.method = method
        self.headers = headers or {}

class HttpResponse:
    def __init__(self):
        self.status_code = 200
        self.body = ""
        self.headers: Dict[str, str] = {}

class HttpContext:
    def __init__(self, request: HttpRequest, scope: ServiceScope):
        self.request = request
        self.response = HttpResponse()
        self.items: Dict[str, Any] = {}
        self.request_services = scope

MiddlewareDelegate = Callable[[HttpContext, Callable[[], None]], None]

class ApplicationBuilder:
    def __init__(self, service_provider: ServiceProvider):
        self.service_provider = service_provider
        self.middlewares: List[MiddlewareDelegate] = []

    def use(self, middleware: MiddlewareDelegate) -> 'ApplicationBuilder':
        self.middlewares.append(middleware)
        return self

    def build(self) -> Callable[[HttpContext], None]:
        # Membangun rantai delegate (Pipeline) dari belakang ke depan
        app: Callable[[HttpContext], None] = lambda ctx: None

        for middleware in reversed(self.middlewares):
            current_mw = middleware
            next_app = app
            app = lambda ctx, mw=current_mw, nxt=next_app: mw(ctx, lambda: nxt(ctx))

        return app

# -----------------------------------------------------------------------------
# 3. CONTOH IMPLEMENTASI MIDDLEWARE ASP.NET CORE
# -----------------------------------------------------------------------------
def logging_middleware(ctx: HttpContext, next_delegate: Callable[[], None]):
    start = time.time()
    print(f"  {Color.BLUE}[--> Middleware 1: Logger]{Color.RESET} Menerima {ctx.request.method} {ctx.request.path}")
    next_delegate()
    elapsed = (time.time() - start) * 1000
    print(f"  {Color.BLUE}[<-- Middleware 1: Logger]{Color.RESET} Selesai dalam {elapsed:.2f}ms. Status: {ctx.response.status_code}")

def authentication_middleware(ctx: HttpContext, next_delegate: Callable[[], None]):
    auth_header = ctx.request.headers.get("Authorization", "")
    print(f"  {Color.MAGENTA}[--> Middleware 2: Auth]{Color.RESET} Memeriksa header otentikasi...")
    
    if ctx.request.path.startswith("/secure") and auth_header != "Bearer valid-token":
        print(f"  {Color.RED}[!!! Middleware 2: Auth]{Color.RESET} Akses ditolak! Short-circuiting pipeline.")
        ctx.response.status_code = 401
        ctx.response.body = "401 Unauthorized: Token tidak valid atau hilang."
        return  # Short-circuit: tidak memanggil next_delegate()

    print(f"  {Color.MAGENTA}[--> Middleware 2: Auth]{Color.RESET} Otentikasi Lolos.")
    next_delegate()
    print(f"  {Color.MAGENTA}[<-- Middleware 2: Auth]{Color.RESET} Mengembalikan respon ke caller.")

def routing_and_endpoint_middleware(ctx: HttpContext, next_delegate: Callable[[], None]):
    print(f"  {Color.GREEN}[--> Middleware 3: Endpoint]{Color.RESET} Menjalankan Route Handler...")
    
    # Resolving layanan via DI scope request
    db_ctx = ctx.request_services.resolve("IDatabaseContext")
    user_svc = ctx.request_services.resolve("IUserService")
    cache_svc = ctx.request_services.resolve("ICacheService")

    if ctx.request.path == "/api/status":
        ctx.response.status_code = 200
        ctx.response.body = f"OK. Server Healthy. DB Instance: {db_ctx.id}"
    elif ctx.request.path == "/secure/profile":
        ctx.response.status_code = 200
        ctx.response.body = f"Profile User: Admin. UserSvc: {user_svc.id}, Cache: {cache_svc.id}"
    else:
        ctx.response.status_code = 404
        ctx.response.body = f"404 Not Found: Path '{ctx.request.path}' tidak dikenal."

    next_delegate()
    print(f"  {Color.GREEN}[<-- Middleware 3: Endpoint]{Color.RESET} Handler selesai mengeksekusi.")

# -----------------------------------------------------------------------------
# 4. DEMO RUNNER & INTERACTIVE LAB
# -----------------------------------------------------------------------------
def run_di_demonstration(provider: ServiceProvider):
    print(f"\n{Color.YELLOW}=== DEMO 1: Siklus Hidup DI Container (Lifetimes) ==={Color.RESET}")
    print("Membuka Request Scope 1...")
    scope1 = provider.create_scope()
    
    s1_single1 = scope1.resolve("ICacheService")
    s1_single2 = scope1.resolve("ICacheService")
    s1_scoped1 = scope1.resolve("IDatabaseContext")
    s1_scoped2 = scope1.resolve("IDatabaseContext")
    s1_trans1  = scope1.resolve("IUserService")
    s1_trans2  = scope1.resolve("IUserService")

    print(f"  Scope 1 - Singleton: id1={s1_single1.id}, id2={s1_single2.id} -> Identik: {s1_single1.id == s1_single2.id}")
    print(f"  Scope 1 - Scoped   : id1={s1_scoped1.id}, id2={s1_scoped2.id} -> Identik: {s1_scoped1.id == s1_scoped2.id}")
    print(f"  Scope 1 - Transient: id1={s1_trans1.id}, id2={s1_trans2.id}   -> Berbeda: {s1_trans1.id != s1_trans2.id}")

    print("\nMembuka Request Scope 2 (Request Baru)...")
    scope2 = provider.create_scope()
    s2_single = scope2.resolve("ICacheService")
    s2_scoped = scope2.resolve("IDatabaseContext")

    print(f"  Scope 2 - Singleton: id={s2_single.id} -> Sama dgn Scope 1: {s2_single.id == s1_single1.id}")
    print(f"  Scope 2 - Scoped   : id={s2_scoped.id} -> Beda dgn Scope 1: {s2_scoped.id != s1_scoped1.id}")

def run_pipeline_simulation(app_runner: Callable[[HttpContext], None], provider: ServiceProvider, path: str, token: Optional[str] = None):
    print(f"\n{Color.YELLOW}=== MEMPROSES HTTP REQUEST: {path} ==={Color.RESET}")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = HttpRequest(path=path, method="GET", headers=headers)
    
    scope = provider.create_scope()
    context = HttpContext(req, scope)

    print(f"{Color.GRAY}Alur Eksekusi Onion/Russian-Doll Pipeline:{Color.RESET}")
    app_runner(context)

    color_stat = Color.GREEN if context.response.status_code == 200 else Color.RED
    print(f"\n{Color.BOLD}Hasil HTTP Response:{Color.RESET}")
    print(f"  Status Code : {color_stat}{context.response.status_code}{Color.RESET}")
    print(f"  Body        : {context.response.body}\n")

def main():
    print_banner()

    # 1. Konfigurasi Dependency Injection (Program.cs / ConfigureServices)
    services = ServiceCollection()
    services.add_singleton("ICacheService", lambda: GuidService("CacheSingleton"))
    services.add_scoped("IDatabaseContext", lambda: GuidService("DbContextScoped"))
    services.add_transient("IUserService", lambda: GuidService("UserSvcTransient"))
    provider = services.build_service_provider()

    # 2. Konfigurasi Middleware Pipeline (Program.cs / app.Use...)
    app_builder = ApplicationBuilder(provider)
    app_builder.use(logging_middleware)
    app_builder.use(authentication_middleware)
    app_builder.use(routing_and_endpoint_middleware)
    app_runner = app_builder.build()

    while True:
        print(f"{Color.BOLD}PILIH SKENARIO PENGUJIAN FONDASI ASP.NET CORE:{Color.RESET}")
        print(" 1. Jalankan Analisis Dependency Injection Lifetimes")
        print(" 2. Request Sukses (GET /api/status - Public)")
        print(" 3. Request Terproteksi - Gagal 401 Unauthorized (GET /secure/profile)")
        print(" 4. Request Terproteksi - Lolos Token (GET /secure/profile + Bearer Token)")
        print(" 5. Request 404 Not Found (GET /api/unknown)")
        print(" 0. Keluar")
        
        choice = input(f"\n{Color.CYAN}Masukkan pilihan (0-5): {Color.RESET}").strip()
        
        if choice == "1":
            run_di_demonstration(provider)
        elif choice == "2":
            run_pipeline_simulation(app_runner, provider, "/api/status")
        elif choice == "3":
            run_pipeline_simulation(app_runner, provider, "/secure/profile", token=None)
        elif choice == "4":
            run_pipeline_simulation(app_runner, provider, "/secure/profile", token="valid-token")
        elif choice == "5":
            run_pipeline_simulation(app_runner, provider, "/api/unknown")
        elif choice == "0":
            print(f"\n{Color.GREEN}Simulasi selesai. Terima kasih.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}\n")

if __name__ == "__main__":
    main()
