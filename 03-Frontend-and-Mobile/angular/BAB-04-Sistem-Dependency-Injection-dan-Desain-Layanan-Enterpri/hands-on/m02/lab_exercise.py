#!/usr/bin/env python3
"""
Lab Hands-on: Angular Hierarchical Dependency Injection & Enterprise Service Architecture
Bab: 04 - Sistem Dependency Injection (DI) & Desain Layanan Enterprise (Deep Dive)

Simulasi runtime komprehensif dari Angular DI Engine:
- Hierarchical Injectors (Root, Module, Element/Component tree)
- Injection Tokens & Multi-Providers (e.g., HTTP_INTERCEPTORS)
- Resolution Modifiers: @Self(), @SkipSelf(), @Optional(), @Host()
- Provider recipes: useClass, useValue, useFactory, useExisting
"""

import enum
import inspect
from typing import Any, Callable, Dict, List, Optional, Type, Union

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"


class LookupFlags(enum.IntFlag):
    """Modifier resolusi dependensi Angular."""
    DEFAULT = 0
    SELF = 1 << 0       # @Self(): Hanya mencari di injector lokal
    SKIP_SELF = 1 << 1  # @SkipSelf(): Melewati injector lokal, cari ke parent
    OPTIONAL = 1 << 2   # @Optional(): Mengembalikan None jika tidak ditemukan, jangan throw error


class InjectionToken:
    """Representasi Angular InjectionToken untuk tipe non-class atau multi-providers."""
    def __init__(self, description: str, multi: bool = False):
        self.description = description
        self.multi = multi

    def __repr__(self) -> str:
        return f"InjectionToken('{self.description}', multi={self.multi})"


class Provider:
    """Konfigurasi Provider Angular (useClass, useValue, useFactory, useExisting)."""
    def __init__(
        self,
        provide: Union[Type, InjectionToken],
        use_class: Optional[Type] = None,
        use_value: Any = None,
        use_factory: Optional[Callable] = None,
        deps: Optional[List[Any]] = None,
        use_existing: Optional[Union[Type, InjectionToken]] = None,
        multi: bool = False
    ):
        self.provide = provide
        self.use_class = use_class
        self.use_value = use_value
        self.use_factory = use_factory
        self.deps = deps or []
        self.use_existing = use_existing
        self.multi = multi


class NullInjector:
    """Ujung akhir dari hirarki resolusi injector Angular (melemparkan NullInjectorError)."""
    def get(self, token: Any, not_found_value: Any = None, flags: LookupFlags = LookupFlags.DEFAULT) -> Any:
        if flags & LookupFlags.OPTIONAL:
            return not_found_value
        raise LookupError(f"NullInjectorError: No provider found for '{token}'!")


class Injector:
    """
    Simulasi Inti Angular Injector Engine.
    Mendukung hirarki hierarkis, cache singleton per-scope, dan eksekusi resolusi token.
    """
    def __init__(self, name: str, parent: Optional["Injector"] = None):
        self.name = name
        self.parent = parent
        self._records: Dict[Any, List[Provider]] = {}
        self._instances: Dict[Any, Any] = {}

    def register(self, provider: Provider) -> None:
        """Mendaftarkan provider ke injector instance saat ini."""
        key = provider.provide
        if key not in self._records:
            self._records[key] = []
        self._records[key].append(provider)

    def get(self, token: Any, not_found_value: Any = None, flags: LookupFlags = LookupFlags.DEFAULT) -> Any:
        """
        Algoritma pencarian Angular DI:
        1. Evaluasi flags (SKIP_SELF, SELF, OPTIONAL).
        2. Cari di injector saat ini (jika tidak SKIP_SELF).
        3. Naik ke parent injector secara rekursif (jika bukan SELF).
        4. Berhenti di NullInjector jika tidak ditemukan.
        """
        start_in_parent = bool(flags & LookupFlags.SKIP_SELF)
        target_injector = self.parent if start_in_parent else self

        return self._resolve_token(token, target_injector, flags, not_found_value)

    def _resolve_token(
        self,
        token: Any,
        current_injector: Optional["Injector"],
        flags: LookupFlags,
        not_found_value: Any
    ) -> Any:
        if current_injector is None:
            return NullInjector().get(token, not_found_value, flags)

        # 1. Cek apakah token terdaftar di current injector
        if token in current_injector._records:
            providers = current_injector._records[token]
            is_multi = getattr(token, "multi", False) or any(p.multi for p in providers)

            if is_multi:
                # Resolve multi-providers (array of instances, misal HTTP_INTERCEPTORS)
                results = []
                for p in providers:
                    results.append(current_injector._instantiate_provider(p))
                return results

            # Standard Singleton per Injector Scope
            if token not in current_injector._instances:
                current_injector._instances[token] = current_injector._instantiate_provider(providers[-1])
            return current_injector._instances[token]

        # 2. Jika modifier @Self aktif, jangan cari ke parent!
        if flags & LookupFlags.SELF:
            if flags & LookupFlags.OPTIONAL:
                return not_found_value
            raise LookupError(f"NodeInjectorError (SelfScope): Token '{token}' not found inside {self.name}!")

        # 3. Propagasi ke Parent Injector
        return self._resolve_token(token, current_injector.parent, flags, not_found_value)

    def _instantiate_provider(self, provider: Provider) -> Any:
        """Instansiasi dependensi berdasarkan recipe."""
        if provider.use_value is not None:
            return provider.use_value

        if provider.use_existing is not None:
            return self.get(provider.use_existing)

        if provider.use_factory is not None:
            resolved_deps = [self.get(dep) for dep in provider.deps]
            return provider.use_factory(*resolved_deps)

        if provider.use_class is not None:
            cls = provider.use_class
            sig = inspect.signature(cls.__init__)
            param_names = [p for p in sig.parameters.keys() if p != 'self']
            
            # Resolusi dependensi konstruktor via types annotations
            resolved_args = []
            annotations = getattr(cls.__init__, "__annotations__", {})
            for p_name in param_names:
                param_type = annotations.get(p_name)
                if param_type:
                    resolved_args.append(self.get(param_type))
                else:
                    raise TypeError(f"Cannot resolve parameter '{p_name}' for class {cls.__name__}. Missing typing annotation!")
            return cls(*resolved_args)

        raise ValueError(f"Invalid provider configuration for {provider.provide}")


# ==============================================================================
# Model Enterprise Services & Tokens
# ==============================================================================

HTTP_INTERCEPTORS = InjectionToken("HTTP_INTERCEPTORS", multi=True)
API_CONFIG = InjectionToken("API_CONFIG")

class LoggerService:
    def __init__(self):
        self.scope_id = id(self)

    def log(self, origin: str, msg: str):
        print(f"  {CLR_CYAN}[Logger#{self.scope_id % 1000:03d}][{origin}]{CLR_RESET} {msg}")


class LoggingInterceptor:
    def intercept(self, request_url: str) -> str:
        print(f"    {CLR_BLUE}--> [LoggingInterceptor] Intercepting request: {request_url}{CLR_RESET}")
        return request_url


class AuthInterceptor:
    def intercept(self, request_url: str) -> str:
        print(f"    {CLR_BLUE}--> [AuthInterceptor] Attaching Bearer JWT Token to: {request_url}{CLR_RESET}")
        return f"{request_url}?auth=bearer_valid_token"


class HttpClient:
    """Enterprise Http Client yang mengeksekusi pipeline interceptors."""
    def __init__(self, logger: LoggerService, config: Any, interceptors: Any):
        self.logger = logger
        self.config = config
        self.interceptors = interceptors or []

    def get(self, endpoint: str) -> str:
        full_url = f"{self.config['base_url']}/{endpoint}"
        self.logger.log("HttpClient", f"Initiating request: {full_url}")
        for interceptor in self.interceptors:
            full_url = interceptor.intercept(full_url)
        return f"Response [200 OK] from {full_url}"


class ScopedFormStateService:
    """Layanan terisolasi pada level Element/Component Tree."""
    def __init__(self):
        self.instance_id = id(self) % 1000
        self.dirty = False

    def mark_dirty(self):
        self.dirty = True


# ==============================================================================
# Laboratorium Eksekusi & Validasi Skenario
# ==============================================================================

def main():
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}  LAB: ANGULAR ENTERPRISE DEPENDENCY INJECTION ENGINE SIMULATOR {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}\n")

    # 1. Inisialisasi Hirarki Injector
    # Root Injector (Application Scope - Singleton Global)
    root_injector = Injector("RootInjector")

    # Module / Route Injector
    feature_injector = Injector("FeatureModuleInjector", parent=root_injector)

    # Element Injectors (Component Hierarchy: Parent Component -> Child Component)
    parent_comp_injector = Injector("OrderParentComponentInjector", parent=feature_injector)
    child_comp_injector = Injector("OrderChildComponentInjector", parent=parent_comp_injector)

    # 2. Pendaftaran Provider di Root Scope
    root_injector.register(Provider(provide=LoggerService, use_class=LoggerService))
    root_injector.register(Provider(
        provide=API_CONFIG,
        use_value={"base_url": "https://api.enterprise.corp/v2", "timeout_ms": 5000}
    ))
    # Daftarkan multi-providers untuk HTTP_INTERCEPTORS
    root_injector.register(Provider(provide=HTTP_INTERCEPTORS, use_class=LoggingInterceptor, multi=True))
    root_injector.register(Provider(provide=HTTP_INTERCEPTORS, use_class=AuthInterceptor, multi=True))

    # HttpClient menggunakan factory dengan dependensi
    def http_client_factory(logger: LoggerService, config: Any, interceptors: Any):
        return HttpClient(logger, config, interceptors)

    root_injector.register(Provider(
        provide=HttpClient,
        use_factory=http_client_factory,
        deps=[LoggerService, API_CONFIG, HTTP_INTERCEPTORS]
    ))

    # Pendaftaran Service Terisolasi di Level Komponen Parent
    parent_comp_injector.register(Provider(provide=ScopedFormStateService, use_class=ScopedFormStateService))

    # ==============================================================================
    # Scenario A: Resolusi Multi-Providers & HttpClient Factory di Root Scope
    # ==============================================================================
    print(f"{CLR_BOLD}{CLR_GREEN}[SKENARIO A] Resolusi Singleton & Multi-Provider Pipeline (Root Scope){CLR_RESET}")
    client = root_injector.get(HttpClient)
    resp = client.get("orders/search")
    print(f"  {CLR_YELLOW}Hasil Resolusi:{CLR_RESET} {resp}\n")

    # ==============================================================================
    # Scenario B: Hierarchical Scoping & Isolasi Instance
    # ==============================================================================
    print(f"{CLR_BOLD}{CLR_GREEN}[SKENARIO B] Hierarchical Scoping (Element/Component Isolation){CLR_RESET}")
    parent_form_svc = parent_comp_injector.get(ScopedFormStateService)
    parent_form_svc.mark_dirty()

    child_form_svc = child_comp_injector.get(ScopedFormStateService)

    print(f"  Parent Component FormState Instance ID : {CLR_BOLD}#{parent_form_svc.instance_id}{CLR_RESET} (Dirty: {parent_form_svc.dirty})")
    print(f"  Child Component FormState Instance ID  : {CLR_BOLD}#{child_form_svc.instance_id}{CLR_RESET} (Dirty: {child_form_svc.dirty})")
    assert parent_form_svc is child_form_svc, "Child harusnya mewarisi instance dari parent jika tidak disediakan sendiri!"
    print(f"  {CLR_GREEN}✓ Verified:{CLR_RESET} Child Component mewarisi service dari Parent Injector yang sama.\n")

    # Sekarang isolasi child dengan meregister instance sendiri di child component
    child_comp_injector.register(Provider(provide=ScopedFormStateService, use_class=ScopedFormStateService))
    new_child_svc = child_comp_injector.get(ScopedFormStateService)
    print(f"  Child Component FormState (Diberi Provider Baru) ID : {CLR_BOLD}#{new_child_svc.instance_id}{CLR_RESET} (Dirty: {new_child_svc.dirty})")
    assert parent_form_svc is not new_child_svc, "Child harusnya memiliki instance terisolasi sendiri!"
    print(f"  {CLR_GREEN}✓ Verified:{CLR_RESET} Child Component sekarang terisolasi dari Parent Component State.\n")

    # ==============================================================================
    # Scenario C: Pengujian Resolution Modifiers (@Self, @SkipSelf, @Optional)
    # ==============================================================================
    print(f"{CLR_BOLD}{CLR_GREEN}[SKENARIO C] Resolution Modifiers (@Self, @SkipSelf, @Optional){CLR_RESET}")

    # 1. @Self() Test: Cari LoggerService di child component injector saja
    print("  1. Testing @Self() LoggerService di Child Component (Harus Gagal):")
    try:
        child_comp_injector.get(LoggerService, flags=LookupFlags.SELF)
    except LookupError as e:
        print(f"     {CLR_RED}Expected Error Captured:{CLR_RESET} {e}")

    # 2. @Self() + @Optional() Test
    print("  2. Testing @Self() + @Optional() LoggerService di Child Component:")
    opt_result = child_comp_injector.get(LoggerService, not_found_value=None, flags=LookupFlags.SELF | LookupFlags.OPTIONAL)
    print(f"     Hasil: {CLR_YELLOW}{opt_result}{CLR_RESET} (Graceful fallback berhasil tanpa melempar crash)")

    # 3. @SkipSelf() Test: Ambil ScopedFormStateService melewati child injector sendiri
    print("  3. Testing @SkipSelf() ScopedFormStateService di Child Component:")
    bypassed_svc = child_comp_injector.get(ScopedFormStateService, flags=LookupFlags.SKIP_SELF)
    print(f"     SkipSelf mengembalikan Instance Parent: #{bypassed_svc.instance_id} (Dirty: {bypassed_svc.dirty})")
    assert bypassed_svc.instance_id == parent_form_svc.instance_id, "SkipSelf gagal melewati level lokal!"
    print(f"     {CLR_GREEN}✓ Verified:{CLR_RESET} Mengabaikan provider lokal child, langsung mengambil milik parent.\n")

    print(f"{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}  SEMUA SIMULASI DEPENDENCY INJECTION ANGULAR BERHASIL LULUS!     {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}================================================================={CLR_RESET}\n")


if __name__ == "__main__":
    main()