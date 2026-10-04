#!/usr/bin/env python3
"""
Lab Exercise: ASP.NET Core Dependency Injection & Configuration Deep Dive Simulator
Simulasi teknis interaktif arsitektur IServiceCollection, ServiceProvider,
Service Lifetime (Transient, Scoped, Singleton), Captive Dependency Detection,
serta Hierarchical IConfiguration & Options Pattern.
"""

import sys
import uuid
import time
from enum import Enum, auto
from typing import Dict, Any, Type, Callable, Optional, List

# ANSI Color Codes for Rich Terminal Output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

class ServiceLifetime(Enum):
    TRANSIENT = auto()
    SCOPED = auto()
    SINGLETON = auto()

class ServiceDescriptor:
    def __init__(self, service_type: str, implementation_factory: Callable[['ServiceProvider'], Any], lifetime: ServiceLifetime):
        self.service_type = service_type
        self.factory = implementation_factory
        self.lifetime = lifetime

class ServiceCollection:
    def __init__(self):
        self.descriptors: Dict[str, ServiceDescriptor] = {}

    def add_transient(self, service_type: str, factory: Callable[['ServiceProvider'], Any]):
        self.descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.TRANSIENT)

    def add_scoped(self, service_type: str, factory: Callable[['ServiceProvider'], Any]):
        self.descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.SCOPED)

    def add_singleton(self, service_type: str, factory: Callable[['ServiceProvider'], Any]):
        self.descriptors[service_type] = ServiceDescriptor(service_type, factory, ServiceLifetime.SINGLETON)

    def build_service_provider(self, validate_scopes: bool = True) -> 'ServiceProvider':
        return ServiceProvider(self.descriptors, validate_scopes=validate_scopes)

class ServiceProvider:
    def __init__(self, descriptors: Dict[str, ServiceDescriptor], parent: Optional['ServiceProvider'] = None, validate_scopes: bool = True):
        self.descriptors = descriptors
        self.parent = parent
        self.validate_scopes = validate_scopes
        self.is_root = parent is None
        self.singletons: Dict[str, Any] = parent.singletons if parent else {}
        self.scoped_instances: Dict[str, Any] = {}
        self.disposables: List[Any] = []
        self.scope_id = str(uuid.uuid4())[:8] if not self.is_root else "ROOT"

    def create_scope(self) -> 'ServiceProvider':
        return ServiceProvider(self.descriptors, parent=self, validate_scopes=self.validate_scopes)

    def get_service(self, service_type: str, resolution_chain: Optional[List[str]] = None) -> Any:
        if resolution_chain is None:
            resolution_chain = []

        descriptor = self.descriptors.get(service_type)
        if not descriptor:
            raise KeyError(f"Layanan '{service_type}' belum terdaftar di IServiceCollection.")

        # ASP.NET Core ValidateScopes: Mendeteksi Captive Dependency (Singleton memakan Scoped)
        if self.validate_scopes and descriptor.lifetime == ServiceLifetime.SCOPED and self.is_root:
            raise RuntimeError(
                f"[CaptiveDependencyException] Tidak dapat me-resolve scoped service '{service_type}' dari Root Provider! "
                f"Ini akan mengakibatkan memory leak / multi-threading state corruption di ASP.NET Core."
            )

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type not in self.singletons:
                # Validasi rantai resolusi Singleton terhadap Scoped
                resolution_chain.append(service_type)
                instance = descriptor.factory(self)
                self.singletons[service_type] = instance
                if hasattr(instance, "dispose"):
                    self.disposables.append(instance)
                resolution_chain.pop()
            return self.singletons[service_type]

        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if self.is_root and not self.validate_scopes:
                # Perilaku berbahaya tanpa scope validation
                pass
            if service_type not in self.scoped_instances:
                instance = descriptor.factory(self)
                self.scoped_instances[service_type] = instance
                if hasattr(instance, "dispose"):
                    self.disposables.append(instance)
            return self.scoped_instances[service_type]

        else:  # TRANSIENT
            instance = descriptor.factory(self)
            if hasattr(instance, "dispose"):
                self.disposables.append(instance)
            return instance

    def dispose(self):
        for item in reversed(self.disposables):
            if hasattr(item, "dispose"):
                item.dispose()
        self.scoped_instances.clear()
        self.disposables.clear()

# Domain Services & Simulating ASP.NET Core Options Pattern
class DatabaseContext:
    def __init__(self, connection_string: str):
        self.id = str(uuid.uuid4())[:8]
        self.connection_string = connection_string
        print(f"  {Colors.GREEN}+ [DbContext:{self.id}]{Colors.RESET} Diinisialisasi (Conn: {self.connection_string})")

    def query(self, sql: str) -> str:
        return f"Hasil query '{sql}' via DbContext [{self.id}]"

    def dispose(self):
        print(f"  {Colors.RED}- [DbContext:{self.id}]{Colors.RESET} Disposed (Koneksi database dikembalikan ke pool)")

class OperationIdService:
    def __init__(self, lifetime_name: str):
        self.id = str(uuid.uuid4())[:8]
        self.lifetime_name = lifetime_name

class OrderService:
    def __init__(self, db: DatabaseContext, op_transient: OperationIdService, op_scoped: OperationIdService):
        self.db = db
        self.op_transient = op_transient
        self.op_scoped = op_scoped

    def process(self, order_id: str):
        print(f"    -> OrderService memproses pesanan #{order_id}")
        print(f"       * Transient ID : {self.op_transient.id} ({self.op_transient.lifetime_name})")
        print(f"       * Scoped ID    : {self.op_scoped.id} ({self.op_scoped.lifetime_name})")
        print(f"       * DbContext ID : {self.db.id}")

class ConfigurationManager:
    """Simulasi IConfiguration Hierarkis ASP.NET Core (appsettings.json + Environment Variables)."""
    def __init__(self):
        self._config: Dict[str, Any] = {
            "Logging:LogLevel:Default": "Information",
            "ConnectionStrings:DefaultConnection": "Server=tcp:sql.internal;Database=ProdDb;",
            "Features:EnableDiscount": True,
            "RateLimit:MaxRequestsPerMinute": 100
        }

    def get_value(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set_environment_override(self, key: str, value: Any):
        self._config[key] = value

def run_lifetime_demo():
    print(f"\n{Colors.BOLD}{Colors.CYAN}=== DEMO 1: Transient vs Scoped vs Singleton ==={Colors.RESET}")
    services = ServiceCollection()

    services.add_transient("IOperationTransient", lambda sp: OperationIdService("Transient"))
    services.add_scoped("IOperationScoped", lambda sp: OperationIdService("Scoped"))
    services.add_singleton("IOperationSingleton", lambda sp: OperationIdService("Singleton"))
    services.add_scoped("AppDbContext", lambda sp: DatabaseContext("Server=sql.cluster;Database=OrdersDb"))

    services.add_transient("OrderService", lambda sp: OrderService(
        db=sp.get_service("AppDbContext"),
        op_transient=sp.get_service("IOperationTransient"),
        op_scoped=sp.get_service("IOperationScoped")
    ))

    root_sp = services.build_service_provider(validate_scopes=True)

    print(f"\n{Colors.YELLOW}[Scope 1: Simulasi HTTP Request #1 (GET /api/orders)]{Colors.RESET}")
    scope1 = root_sp.create_scope()
    svc1_a = scope1.get_service("OrderService")
    svc1_a.process("ORD-101")
    print("  ..Memanggil OrderService kedua kali di dalam Scope 1:")
    svc1_b = scope1.get_service("OrderService")
    svc1_b.process("ORD-102")
    print(f"  {Colors.DIM}Membuang Scope 1 (HTTP Request selesai):{Colors.RESET}")
    scope1.dispose()

    print(f"\n{Colors.YELLOW}[Scope 2: Simulasi HTTP Request #2 (POST /api/checkout)]{Colors.RESET}")
    scope2 = root_sp.create_scope()
    svc2 = scope2.get_service("OrderService")
    svc2.process("ORD-201")
    print(f"  {Colors.DIM}Membuang Scope 2 (HTTP Request selesai):{Colors.RESET}")
    scope2.dispose()

def run_captive_dependency_demo():
    print(f"\n{Colors.BOLD}{Colors.CYAN}=== DEMO 2: Deteksi Captive Dependency (ValidateScopes) ==={Colors.RESET}")
    services = ServiceCollection()

    services.add_scoped("ScopedRepo", lambda sp: DatabaseContext("SqlRepoConn"))

    # Anti-Pattern: Singleton bergantung langsung pada Scoped Service
    services.add_singleton("SingletonCache", lambda sp: {
        "repo": sp.get_service("ScopedRepo")
    })

    print(f"{Colors.BLUE}[Test A] Membangun Provider dengan ValidateScopes = True (Default di ASP.NET Core Development){Colors.RESET}")
    strict_provider = services.build_service_provider(validate_scopes=True)
    try:
        strict_provider.get_service("SingletonCache")
    except RuntimeError as ex:
        print(f"  {Colors.GREEN}SUKSES DITANGKAP:{Colors.RESET} {Colors.RED}{ex}{Colors.RESET}")

    print(f"\n{Colors.BLUE}[Test B] Simulasi Jika ValidateScopes = False (Bencana Produksi){Colors.RESET}")
    loose_provider = services.build_service_provider(validate_scopes=False)
    leaked_singleton = loose_provider.get_service("SingletonCache")
    print(f"  {Colors.YELLOW}PERINGATAN!{Colors.RESET} Scoped service berhasil diculik oleh Singleton:")
    print(f"  SingletonCache memiliki ref ke: {leaked_singleton['repo']}")
    print(f"  {Colors.DIM}Efek: DbContext tidak akan pernah di-dispose, koneksi bocor, dan state tercampur antar user!{Colors.RESET}")

def run_configuration_demo():
    print(f"\n{Colors.BOLD}{Colors.CYAN}=== DEMO 3: IConfiguration & Hierarchical Key-Value Override ==={Colors.RESET}")
    config = ConfigurationManager()

    print(f"1. Nilai Dasar dari appsettings.json:")
    print(f"   ConnectionStrings:DefaultConnection = {Colors.GREEN}{config.get_value('ConnectionStrings:DefaultConnection')}{Colors.RESET}")
    print(f"   RateLimit:MaxRequestsPerMinute      = {Colors.GREEN}{config.get_value('RateLimit:MaxRequestsPerMinute')}{Colors.RESET}")

    print(f"\n2. Simulasi Injeksi Environment Variable (Overriding):")
    print(f"   Exporting ASPNETCORE_ConnectionStrings__DefaultConnection='Server=cloud.pg;Database=ProdDb'...")
    config.set_environment_override("ConnectionStrings:DefaultConnection", "Server=cloud.pg;Database=ProdDb")

    print(f"\n3. Nilai Efektif Runtime:")
    print(f"   ConnectionStrings:DefaultConnection = {Colors.CYAN}{config.get_value('ConnectionStrings:DefaultConnection')}{Colors.RESET}")

def main():
    print(f"{Colors.BOLD}{Colors.HEADER}===================================================================={Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}    ASP.NET CORE DEPENDENCY INJECTION & CONFIGURATION LAB          {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.HEADER}===================================================================={Colors.RESET}")

    while True:
        print(f"\n{Colors.BOLD}Menu Simulasi Interaktif:{Colors.RESET}")
        print(" [1] Jalankan Demo Service Lifetime (Transient, Scoped, Singleton)")
        print(" [2] Jalankan Demo Deteksi Captive Dependency (ValidateScopes)")
        print(" [3] Jalankan Demo IConfiguration Hierarkis & Overrides")
        print(" [4] Jalankan Semua Demonstrasi Berurutan")
        print(" [0] Keluar")

        try:
            choice = input(f"\n{Colors.CYAN}Pilih opsi [0-4]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == '1':
            run_lifetime_demo()
        elif choice == '2':
            run_captive_dependency_demo()
        elif choice == '3':
            run_configuration_demo()
        elif choice == '4':
            run_lifetime_demo()
            run_captive_dependency_demo()
            run_configuration_demo()
        elif choice == '0':
            print(f"{Colors.GREEN}Terima kasih telah menjalankan simulasi ASP.NET Core DI & Configuration.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan masukkan angka 0 - 4.{Colors.RESET}")

if __name__ == "__main__":
    main()
