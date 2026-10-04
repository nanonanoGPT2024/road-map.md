#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core - Dependency Injection & Configuration Deep Dive
Simulasi mendalam arsitektur Inversion of Control (IoC) Container dan Hierarchical Configuration
sesuai spesifikasi internal Microsoft.Extensions.DependencyInjection & Configuration.
"""

from __future__ import annotations
import inspect
import sys
import uuid
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints

# ANSI Palette untuk visualisasi enterprise CLI
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"


class ServiceLifetime(Enum):
    TRANSIENT = auto()
    SCOPED = auto()
    SINGLETON = auto()


# ============================================================================
# 1. HIERARCHICAL CONFIGURATION ENGINE (Microsoft.Extensions.Configuration)
# ============================================================================

class ConfigurationRoot:
    """
    Mensimulasikan IConfigurationRoot ASP.NET Core.
    Mendukung perataan kunci berjenjang (key flattening) dengan separator ':'
    dan mekanisme overriding bertingkat (Base -> Environment -> Overrides).
    """
    def __init__(self):
        self._data: Dict[str, Any] = {}

    def load_layer(self, source_name: str, raw_data: Dict[str, Any], prefix: str = "") -> None:
        """Memflatisasi struktur nested dictionary menjadi token separated keys (misal: Logging:LogLevel:Default)."""
        for key, value in raw_data.items():
            full_key = f"{prefix}:{key}" if prefix else key
            if isinstance(value, dict):
                self.load_layer(source_name, value, full_key)
            else:
                self._data[full_key.lower()] = value
        print(f" {CLR_CYAN}⮞ Configuration Provider Loaded:{CLR_RESET} {source_name} ({len(raw_data)} direct nodes)")

    def get_value(self, key: str, default: Any = None) -> Any:
        return self._data.get(key.lower(), default)

    def bind(self, section_prefix: str, target_class: Type) -> Any:
        """Mensimulasikan .Get<TOptions>() / .Bind() pattern pada strongly-typed options."""
        section_prefix = section_prefix.lower() + ":"
        kwargs = {}
        for k, v in self._data.items():
            if k.startswith(section_prefix):
                param_name = k[len(section_prefix):]
                if ":" not in param_name:  # Atribut langsung level pertama
                    kwargs[param_name] = v
        try:
            return target_class(**kwargs)
        except TypeError as e:
            raise ValueError(f"Gagal melakukan binding konfigurasi ke {target_class.__name__}: {e}")


# ============================================================================
# 2. DEPENDENCY INJECTION ENGINE (Microsoft.Extensions.DependencyInjection)
# ============================================================================

class ServiceDescriptor:
    def __init__(
        self,
        service_type: Type,
        implementation_type: Optional[Type] = None,
        implementation_instance: Optional[Any] = None,
        implementation_factory: Optional[Callable[[ServiceProvider], Any]] = None,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    ):
        self.service_type = service_type
        self.implementation_type = implementation_type or (service_type if not implementation_instance and not implementation_factory else None)
        self.implementation_instance = implementation_instance
        self.implementation_factory = implementation_factory
        self.lifetime = lifetime


class ServiceCollection:
    """Koleksi ServiceDescriptor (Contract builder sebelum ServiceProvider dikompilasi)."""
    def __init__(self):
        self.descriptors: List[ServiceDescriptor] = []

    def add_singleton(self, service_type: Type, implementation_type: Optional[Type] = None, instance: Optional[Any] = None) -> ServiceCollection:
        self.descriptors.append(ServiceDescriptor(service_type, implementation_type, instance, lifetime=ServiceLifetime.SINGLETON))
        return self

    def add_scoped(self, service_type: Type, implementation_type: Optional[Type] = None) -> ServiceCollection:
        self.descriptors.append(ServiceDescriptor(service_type, implementation_type, lifetime=ServiceLifetime.SCOPED))
        return self

    def add_transient(self, service_type: Type, implementation_type: Optional[Type] = None) -> ServiceCollection:
        self.descriptors.append(ServiceDescriptor(service_type, implementation_type, lifetime=ServiceLifetime.TRANSIENT))
        return self

    def build_service_provider(self, validate_scopes: bool = True) -> ServiceProvider:
        return ServiceProvider(self.descriptors, validate_scopes=validate_scopes)


class ServiceScope:
    """Mewakili IServiceScope untuk isolasi dependensi per request/siklus scoped."""
    def __init__(self, root_provider: ServiceProvider):
        self.service_provider = ServiceProvider(
            descriptors=root_provider.descriptors,
            root_provider=root_provider,
            validate_scopes=root_provider.validate_scopes,
            is_root=False
        )

    def __enter__(self) -> ServiceProvider:
        return self.service_provider

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.service_provider.dispose()


class ServiceProvider:
    """
    Mesin Resolver DI Runtime.
    Mengelola active instances, mendeteksi captive dependency, dan meng-handle circular references.
    """
    def __init__(
        self,
        descriptors: List[ServiceDescriptor],
        root_provider: Optional[ServiceProvider] = None,
        validate_scopes: bool = True,
        is_root: bool = True
    ):
        self.descriptors = descriptors
        self.descriptor_map: Dict[Type, ServiceDescriptor] = {d.service_type: d for d in descriptors}
        self.root_provider = root_provider if root_provider else self
        self.validate_scopes = validate_scopes
        self.is_root = is_root
        self._scoped_instances: Dict[Type, Any] = {}
        self._singleton_instances: Dict[Type, Any] = {}
        self._resolving_stack: List[Type] = []

    def create_scope(self) -> ServiceScope:
        return ServiceScope(self.root_provider)

    def get_service(self, service_type: Type) -> Any:
        return self._resolve_core(service_type, current_target_lifetime=None)

    def _resolve_core(self, service_type: Type, current_target_lifetime: Optional[ServiceLifetime]) -> Any:
        if service_type not in self.descriptor_map:
            raise RuntimeError(f"Layanan tipe '{service_type.__name__}' tidak terdaftar pada ServiceCollection.")

        descriptor = self.descriptor_map[service_type]

        # Validasi Valid Scope Engine (Captive Dependency Detector)
        # ASP.NET Core throws InvalidOperationException jika Singleton memakan Scoped dependency
        if self.validate_scopes:
            if current_target_lifetime == ServiceLifetime.SINGLETON and descriptor.lifetime == ServiceLifetime.SCOPED:
                raise ValueError(
                    f"{CLR_RED}[CAPTIVE DEPENDENCY DETECTED]{CLR_RESET} "
                    f"Singleton mencoba mengonsumsi Scoped service '{service_type.__name__}'. "
                    f"Ini menyebabkan Scoped service terikat permanen dan memicu memory leak serta thread-safety bugs!"
                )
            if self.is_root and descriptor.lifetime == ServiceLifetime.SCOPED:
                raise ValueError(
                    f"{CLR_RED}[INVALID SCOPE ACCESS]{CLR_RESET} "
                    f"Tidak dapat me-resolve scoped service '{service_type.__name__}' dari Root Provider. "
                    f"Harus di-resolve di dalam cakupan ServiceScope (request lifecycle)."
                )

        # Siklus Resolusi Berdasarkan Lifetime
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self.root_provider._singleton_instances:
                return self.root_provider._singleton_instances[service_type]
            
            instance = self._create_instance(descriptor, target_lifetime=ServiceLifetime.SINGLETON)
            self.root_provider._singleton_instances[service_type] = instance
            return instance

        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if descriptor.service_type in self._scoped_instances:
                return self._scoped_instances[descriptor.service_type]

            instance = self._create_instance(descriptor, target_lifetime=ServiceLifetime.SCOPED)
            self._scoped_instances[descriptor.service_type] = instance
            return instance

        elif descriptor.lifetime == ServiceLifetime.TRANSIENT:
            return self._create_instance(descriptor, target_lifetime=ServiceLifetime.TRANSIENT)

        raise NotImplementedError(f"Lifetime {descriptor.lifetime} belum didukung.")

    def _create_instance(self, descriptor: ServiceDescriptor, target_lifetime: ServiceLifetime) -> Any:
        # Penanganan circular dependency
        if descriptor.service_type in self._resolving_stack:
            chain = " -> ".join([t.__name__ for t in self._resolving_stack] + [descriptor.service_type.__name__])
            raise RuntimeError(f"Circular dependency terdeteksi pada graph aktivasi: {chain}")

        self._resolving_stack.append(descriptor.service_type)

        try:
            if descriptor.implementation_instance:
                return descriptor.implementation_instance

            target_class = descriptor.implementation_type
            constructor = getattr(target_class, "__init__")
            
            # Introspeksi Parameter Konstruktor (Constructor Injection via Reflection)
            sig = inspect.signature(constructor)
            hints = get_type_hints(constructor)
            dependencies = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                param_type = hints.get(param_name)
                if not param_type:
                    raise TypeError(f"Parameter '{param_name}' pada kelas '{target_class.__name__}' tidak memiliki Type Hint.")

                # Rekursi resolving dependensi konstruktor
                dependencies[param_name] = self._resolve_core(param_type, current_target_lifetime=target_lifetime)

            return target_class(**dependencies)
        finally:
            self._resolving_stack.pop()

    def dispose(self):
        """Disposal simulation saat Scope berakhir."""
        for inst in self._scoped_instances.values():
            if hasattr(inst, "dispose") and callable(getattr(inst, "dispose")):
                inst.dispose()
        self._scoped_instances.clear()


# ============================================================================
# 3. LAB DOMAIN SERVICES & CONFIGURATION BINDING SIMULATION
# ============================================================================

@dataclass
class DatabaseOptions:
    connection_string: str = ""
    command_timeout: int = 30
    enable_pooling: bool = True


class IAppLogger:
    def log(self, message: str) -> None: ...

class AppLogger(IAppLogger):
    def __init__(self):
        self.instance_id = str(uuid.uuid4())[:8]

    def log(self, message: str) -> None:
        print(f"  {CLR_BLUE}[Logger:{self.instance_id}]{CLR_RESET} {message}")


class IDbConnectionContext:
    def execute(self, sql: str) -> None: ...
    def dispose(self) -> None: ...

class SqlDbContext(IDbConnectionContext):
    def __init__(self, options: DatabaseOptions, logger: IAppLogger):
        self.instance_id = str(uuid.uuid4())[:8]
        self.options = options
        self.logger = logger
        self.is_disposed = False
        self.logger.log(f"SqlDbContext [{self.instance_id}] dibentuk. Target Host: {self.options.connection_string}")

    def execute(self, sql: str) -> None:
        if self.is_disposed:
            raise RuntimeError(f"DbContext {self.instance_id} sudah di-dispose!")
        print(f"    {CLR_GREEN}⮑ EXECUTE DB [{self.instance_id}]:{CLR_RESET} '{sql}' (Pool={self.options.enable_pooling})")

    def dispose(self) -> None:
        self.is_disposed = True
        print(f"  {CLR_YELLOW}[DbContext:{self.instance_id}]{CLR_RESET} Released / Disposed successfully.")


class IOrderRepository:
    def get_order(self, order_id: int) -> None: ...

class OrderRepository(IOrderRepository):
    def __init__(self, db_context: IDbConnectionContext):
        self.instance_id = str(uuid.uuid4())[:8]
        self.db = db_context

    def get_order(self, order_id: int) -> None:
        self.db.execute(f"SELECT * FROM Orders WHERE Id = {order_id} (RepoInstance: {self.instance_id})")


class IOrderService:
    def process_order(self, order_id: int) -> None: ...

class OrderService(IOrderService):
    def __init__(self, repo: IOrderRepository, logger: IAppLogger):
        self.instance_id = str(uuid.uuid4())[:8]
        self.repo = repo
        self.logger = logger

    def process_order(self, order_id: int) -> None:
        self.logger.log(f"Processing Order #{order_id} di Transient OrderService [{self.instance_id}]")
        self.repo.get_order(order_id)


# Komponen Ilegal: Singleton yang mengonsumsi Scoped Service
class InvalidReportBackgroundWorker:
    def __init__(self, db: IDbConnectionContext):
        self.db = db


# ============================================================================
# 4. TEST HARNESS & SIMULATION WORKFLOW
# ============================================================================

def banner(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}{'='*75}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}  {title}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}{'='*75}{CLR_RESET}\n")

def main():
    banner("MODUL 02 DEEP DIVE: ASP.NET CORE DI & CONFIGURATION INTERNALS")

    # A. PIPELINE KONFIGURASI HIERARKIS (Layering Model)
    print(f"{CLR_BOLD}[FASE 1] Membangun Layered Configuration Pipeline{CLR_RESET}")
    config = ConfigurationRoot()
    
    # 1. Base Appsettings
    config.load_layer("appsettings.json", {
        "Database": {
            "connection_string": "Server=tcp:sql.local,1433;Database=CommerceDb;",
            "command_timeout": 30,
            "enable_pooling": True
        },
        "Logging": {
            "LogLevel": "Information"
        }
    })

    # 2. Environment Override (Production)
    config.load_layer("appsettings.Production.json", {
        "Database": {
            "connection_string": "Server=tcp:sql.prod.enterprise:1433;Database=CommerceProd;",
            "command_timeout": 15
        }
    })

    # 3. Environment Variable Injection (Prefix __)
    config.load_layer("EnvironmentVariables", {
        "Database:command_timeout": 10
    })

    # Bind strongly-typed DatabaseOptions
    db_options: DatabaseOptions = config.bind("Database", DatabaseOptions)
    print(f"\n{CLR_GREEN}✓ Configuration Options Resolved:{CLR_RESET}")
    print(f"  Connection: {db_options.connection_string}")
    print(f"  Timeout   : {db_options.command_timeout}s (Overridden by EnvVar)")
    print(f"  Pooling   : {db_options.enable_pooling}")

    # B. SERVICE CONTAINER REGISTRATION
    banner("[FASE 2] Registrasi ServiceCollection & Scope Validation")
    services = ServiceCollection()

    # Registrasi dependensi dengan explicit lifetimes
    services.add_singleton(DatabaseOptions, instance=db_options)
    services.add_singleton(IAppLogger, AppLogger)
    services.add_scoped(IDbConnectionContext, SqlDbContext)
    services.add_scoped(IOrderRepository, OrderRepository)
    services.add_transient(IOrderService, OrderService)

    # Validasi Scope diaktifkan secara default pada Development Profile ASP.NET Core
    provider = services.build_service_provider(validate_scopes=True)
    print(f"{CLR_GREEN}✓ ServiceProvider terkompilasi dengan validate_scopes=True{CLR_RESET}")

    # C. SIMULASI DETEKSI ROOT SCOPE LEAKAGE
    print(f"\n{CLR_BOLD}[FASE 3] Test: Mencoba Resolve Scoped Service dari Root Provider...{CLR_RESET}")
    try:
        provider.get_service(IDbConnectionContext)
    except ValueError as ex:
        print(f"  {ex}")

    # D. SIMULASI REQUEST LIFECYCLE (SCOPED WORKFLOW)
    banner("[FASE 4] Simulasi Pipeline HTTP Request (Scoped Isolation Test)")

    # Request 1
    print(f"{CLR_BOLD}--- INCOMING HTTP REQUEST 1 [GET /orders/101] ---{CLR_RESET}")
    with provider.create_scope() as scope_1:
        logger_req1 = scope_1.get_service(IAppLogger)
        logger_req1.log("HTTP Context Initialized.")
        
        svc_a = scope_1.get_service(IOrderService)
        svc_b = scope_1.get_service(IOrderService)

        print(f"  * OrderService (Transient A): {svc_a.instance_id}")
        print(f"  * OrderService (Transient B): {svc_b.instance_id} -> {CLR_YELLOW}(ID berbeda: Transient behavior benar){CLR_RESET}")
        print(f"  * Same Repo in Scope?       : {svc_a.repo is svc_b.repo} -> {CLR_YELLOW}(True: Scoped shared antar dependensi){CLR_RESET}")
        
        svc_a.process_order(101)
    print(f"{CLR_BOLD}--- HTTP REQUEST 1 CLOSED (Scope Disposed) ---\n{CLR_RESET}")

    # Request 2 (Memastikan isolasi state)
    print(f"{CLR_BOLD}--- INCOMING HTTP REQUEST 2 [GET /orders/202] ---{CLR_RESET}")
    with provider.create_scope() as scope_2:
        logger_req2 = scope_2.get_service(IAppLogger)
        print(f"  * Singleton Logger Shared?  : {logger_req1 is logger_req2} -> {CLR_YELLOW}(True: Singleton lintas scope){CLR_RESET}")
        
        svc_2 = scope_2.get_service(IOrderService)
        svc_2.process_order(202)
    print(f"{CLR_BOLD}--- HTTP REQUEST 2 CLOSED (Scope Disposed) ---\n{CLR_RESET}")

    # E. SIMULASI DETEKSI CAPTIVE DEPENDENCY
    banner("[FASE 5] Simulasi Fatal Error: Captive Dependency Detection")
    print("Mendaftarkan 'InvalidReportBackgroundWorker' (Singleton) yang bergantung pada 'IDbConnectionContext' (Scoped)...")
    
    flawed_services = ServiceCollection()
    flawed_services.add_singleton(DatabaseOptions, instance=db_options)
    flawed_services.add_singleton(IAppLogger, AppLogger)
    flawed_services.add_scoped(IDbConnectionContext, SqlDbContext)
    flawed_services.add_singleton(InvalidReportBackgroundWorker) # BENCANA ARSITEKTUR

    strict_provider = flawed_services.build_service_provider(validate_scopes=True)

    try:
        strict_provider.get_service(InvalidReportBackgroundWorker)
    except ValueError as ex:
        print(f"\n{CLR_BOLD}Deteksi Eksepsi Berhasil Dicegat:{CLR_RESET}\n{ex}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}✓ Seluruh pengujian internal IoC & Configuration ASP.NET Core selesai dengan sukses.{CLR_RESET}")


if __name__ == "__main__":
    main()