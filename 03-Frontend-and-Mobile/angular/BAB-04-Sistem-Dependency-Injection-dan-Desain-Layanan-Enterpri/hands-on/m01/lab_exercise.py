#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Sistem Dependency Injection (DI) & Desain Layanan Enterprise Angular
BAB 04 - Hierarchical Injectors, Resolution Modifiers, Injection Tokens, & Multi-Providers

Panduan:
Jalankan file ini secara langsung:
  python3 hands-on/m01/lab_exercise.py
"""

from __future__ import annotations
import sys
import time
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field

# ==============================================================================
# Terminal ANSI Color Formatting
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def c(text: str, color_code: str) -> str:
    return f"{color_code}{text}{Color.RESET}"

# ==============================================================================
# Angular DI Core Primitives Simulation
# ==============================================================================

class ResolutionModifier(Enum):
    SELF = auto()
    SKIP_SELF = auto()
    OPTIONAL = auto()
    HOST = auto()

@dataclass(frozen=True)
class InjectionToken:
    description: str

    def __repr__(self) -> str:
        return f"InjectionToken('{self.description}')"

@dataclass
class Provider:
    provide: Any
    use_class: Optional[Type[Any]] = None
    use_value: Optional[Any] = None
    use_factory: Optional[Callable[..., Any]] = None
    deps: List[Any] = field(default_factory=list)
    multi: bool = False

class NullInjector:
    """
    Simulasi NullInjector pada Angular:
    Berada di pucuk rantai resolusi injector. Melemparkan error jika token tidak ditemukan
    kecuali jika diminta dengan modifier @Optional().
    """
    def get(self, token: Any, optional: bool = False) -> Any:
        if optional:
            return None
        raise RuntimeError(f"NullInjectorError: No provider for {token}!")

class Injector:
    """
    Simulasi Node Hierarchical Injector (Root, Platform, atau Element Injector).
    Mendukung singleton caching per injector, multi-provider tokens, dan upward delegation.
    """
    def __init__(self, name: str, parent: Optional[Union[Injector, NullInjector]] = None):
        self.name = name
        self.parent = parent or NullInjector()
        self.providers: Dict[Any, List[Provider]] = {}
        self.records: Dict[Any, Any] = {}  # Singleton cache per-injector instance

    def register(self, provider: Provider) -> None:
        token = provider.provide
        if provider.multi:
            if token not in self.providers:
                self.providers[token] = []
            self.providers[token].append(provider)
        else:
            self.providers[token] = [provider]

    def _instantiate(self, provider: Provider) -> Any:
        if provider.use_value is not None:
            return provider.use_value
        if provider.use_factory is not None:
            resolved_deps = [self.get(d) for d in provider.deps]
            return provider.use_factory(*resolved_deps)
        if provider.use_class is not None:
            return provider.use_class()
        raise ValueError(f"Provider {provider} tidak memiliki strategi instansiasi valid.")

    def get(
        self,
        token: Any,
        modifiers: Optional[List[ResolutionModifier]] = None
    ) -> Any:
        modifiers = modifiers or []
        is_self = ResolutionModifier.SELF in modifiers
        is_skip_self = ResolutionModifier.SKIP_SELF in modifiers
        is_optional = ResolutionModifier.OPTIONAL in modifiers

        print(f"  {c('→ Resolving:', Color.GRAY)} token {c(str(token), Color.CYAN)} di injector [{c(self.name, Color.YELLOW)}]")

        # Kasus 1: @SkipSelf() - Lewati injector ini, langsung lempar ke parent
        if is_skip_self:
            print(f"    {c('⚡ [@SkipSelf detected]', Color.MAGENTA)} Melompati injector [{self.name}], mencari di parent...")
            try:
                # Parent dipanggil tanpa @SkipSelf untuk injector berikutnya
                remaining_mods = [m for m in modifiers if m != ResolutionModifier.SKIP_SELF]
                return self.parent.get(token, optional=is_optional) if isinstance(self.parent, NullInjector) else self.parent.get(token, remaining_mods)
            except RuntimeError as err:
                if is_optional:
                    return None
                raise err

        # Kasus 2: Cek apakah token ada di lokal injector ini
        if token in self.providers:
            if token not in self.records:
                provider_list = self.providers[token]
                is_multi = any(p.multi for p in provider_list)
                if is_multi:
                    instances = [self._instantiate(p) for p in provider_list]
                    self.records[token] = instances
                else:
                    self.records[token] = self._instantiate(provider_list[0])
                print(f"    {c('✔ [Found Locally - Instantiated & Cached]', Color.GREEN)} di [{self.name}]")
            else:
                print(f"    {c('✔ [Found in Cache (Singleton Scope)]', Color.GREEN)} di [{self.name}]")
            return self.records[token]

        # Kasus 3: Jika memakai @Self() dan tidak ditemukan di sini, dilarang naik ke parent
        if is_self:
            if is_optional:
                print(f"    {c('⚠ [@Self + @Optional]', Color.YELLOW)} Token tidak ditemukan di [{self.name}], return None.")
                return None
            raise RuntimeError(f"NodeInjectorError: [@Self] No provider for {token} ditemukan di level [{self.name}]!")

        # Kasus 4: Naik secara hierarkis ke parent (Bubble Up)
        print(f"    {c('↑ [Bubble Up]', Color.BLUE)} Tidak ada di [{self.name}], delegasikan ke parent [{getattr(self.parent, 'name', 'NullInjector')}]...")
        try:
            return self.parent.get(token, optional=is_optional) if isinstance(self.parent, NullInjector) else self.parent.get(token, modifiers)
        except RuntimeError as err:
            if is_optional:
                return None
            raise err

# ==============================================================================
# Enterprise Service Mocks (Logika Bisnis Realistis)
# ==============================================================================

class LoggerService:
    def __init__(self, prefix: str = "RootLogger"):
        self.prefix = prefix
    def log(self, message: str) -> str:
        return f"[{self.prefix}] {message}"

class TenantConfigService:
    def __init__(self, tenant_id: str = "default_tenant"):
        self.tenant_id = tenant_id

HTTP_INTERCEPTORS = InjectionToken("HTTP_INTERCEPTORS")

class AuthInterceptor:
    def intercept(self, req: str) -> str:
        return f"{req} + [BearerTokenHeader]"

class LoggingInterceptor:
    def intercept(self, req: str) -> str:
        return f"{req} + [TimestampLogging]"

class CachingInterceptor:
    def intercept(self, req: str) -> str:
        return f"{req} + [ETagCacheValidation]"

# ==============================================================================
# Interactive Demo & Verification Harness
# ==============================================================================

def print_header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.BG_BLUE}{Color.WHITE} === {title} === {Color.RESET}\n")

def build_angular_injector_tree():
    """
    Membangun arsitektur hirarki injector Angular standar:
    NullInjector
      └─ RootInjector (providedIn: 'root' / AppModule)
          └─ ParentComponentInjector (DashboardFeatureComponent)
              └─ ChildComponentInjector (AnalyticsWidgetComponent)
    """
    root_injector = Injector("RootInjector")
    # Daftarkan logger default di root
    root_injector.register(Provider(provide=LoggerService, use_value=LoggerService("GLOBAL_ROOT")))
    
    # Daftarkan Multi-Providers HTTP Interceptors
    root_injector.register(Provider(provide=HTTP_INTERCEPTORS, use_class=AuthInterceptor, multi=True))
    root_injector.register(Provider(provide=HTTP_INTERCEPTORS, use_class=LoggingInterceptor, multi=True))

    # Parent Element Injector (Dashboard Component)
    parent_injector = Injector("DashboardComponentInjector", parent=root_injector)
    # Override Logger khusus Dashboard (Isolated Service Pattern)
    parent_injector.register(Provider(provide=LoggerService, use_value=LoggerService("TENANT_DASHBOARD")))
    parent_injector.register(Provider(provide=TenantConfigService, use_value=TenantConfigService("CORP-ALPHA-99")))

    # Child Element Injector (Analytics Widget Component)
    child_injector = Injector("AnalyticsWidgetInjector", parent=parent_injector)

    return root_injector, parent_injector, child_injector

def demo_hierarchical_resolution(child_inj, parent_inj, root_inj):
    print_header("1. DEMO RESOLUSI HIERARKIS & ISOLATED INSTANCE")
    print(c("Skenario:", Color.BOLD) + " Child memanggil LoggerService tanpa modifier khusus.")
    print("Harapan: Menemukan override di DashboardComponentInjector, BUKAN RootInjector.\n")
    
    logger = child_inj.get(LoggerService)
    print(f"\n{c('Hasil Eksekusi:', Color.BOLD)} {c(logger.log('Transaksi Finansial'), Color.GREEN)}\n")

    print(c("Skenario 2:", Color.BOLD) + " Root memanggil LoggerService.")
    print("Harapan: RootInjector mengembalikan instance GLOBAL_ROOT miliknya sendiri.\n")
    root_logger = root_inj.get(LoggerService)
    print(f"\n{c('Hasil Eksekusi:', Color.BOLD)} {c(root_logger.log('Sistem Bootstrapping'), Color.GREEN)}\n")

def demo_resolution_modifiers(child_inj, parent_inj):
    print_header("2. DEMO RESOLUTION MODIFIERS (@SkipSelf, @Self, @Optional)")
    
    print(c("A. @SkipSelf() pada Child:", Color.BOLD))
    print("Widget sengaja ingin logger dari level di atasnya langsung atau root, melompati definisi lokal.\n")
    skip_logger = child_inj.get(LoggerService, modifiers=[ResolutionModifier.SKIP_SELF])
    print(f"\n{c('Logger didapat:', Color.BOLD)} {skip_logger.prefix}\n")

    print(c("B. @Self() pada Child untuk TenantConfigService (Tidak disediakan di Child):", Color.BOLD))
    try:
        child_inj.get(TenantConfigService, modifiers=[ResolutionModifier.SELF])
    except RuntimeError as e:
        print(f"\n{c('Error Berhasil Ditangkap (Expected):', Color.RED)} {e}\n")

    print(c("C. @Self() + @Optional() pada Child untuk TenantConfigService:", Color.BOLD))
    result = child_inj.get(TenantConfigService, modifiers=[ResolutionModifier.SELF, ResolutionModifier.OPTIONAL])
    print(f"\n{c('Hasil Kembalian Aman (Graceful Fallback):', Color.GREEN)} {result}\n")

def demo_multi_providers(root_inj):
    print_header("3. DEMO MULTI-PROVIDER PATTERN (HTTP_INTERCEPTORS)")
    print(c("Konsep:", Color.BOLD) + " Mengumpulkan array instans dari banyak interceptor yang didaftarkan terpisah.")
    
    interceptors = root_inj.get(HTTP_INTERCEPTORS)
    print(f"\nJumlah interceptor aktif: {len(interceptors)}")
    req = "GET /api/v1/payroll"
    for interceptor in interceptors:
        req = interceptor.intercept(req)
    print(f"{c('Payload Pipeline Setelah Interceptors:', Color.CYAN)} {req}\n")

def run_self_verification():
    print_header("4. RUNNING AUTOMATED UNIT TESTS & QUALITY GATE")
    root_inj, parent_inj, child_inj = build_angular_injector_tree()
    
    # Test 1: Hierarchical resolution
    logger = child_inj.get(LoggerService)
    assert logger.prefix == "TENANT_DASHBOARD", "Test 1 Gagal: Harus resolve ke parent terdekat"
    print(f"{c('✔ Test 1 Lolos:', Color.GREEN)} Resolusi hierarki terdekat berhasil.")

    # Test 2: Singleton scoping in same injector
    logger_again = child_inj.get(LoggerService)
    assert logger is logger_again, "Test 2 Gagal: Scope singleton dalam 1 injector harus identik"
    print(f"{c('✔ Test 2 Lolos:', Color.GREEN)} Singleton caching dalam satu scope terverifikasi.")

    # Test 3: Multi provider returns list
    interceptors = root_inj.get(HTTP_INTERCEPTORS)
    assert len(interceptors) == 2, f"Test 3 Gagal: Diharapkan 2 interceptors, didapat {len(interceptors)}"
    print(f"{c('✔ Test 3 Lolos:', Color.GREEN)} Multi-provider array tokenization valid.")

    # Test 4: @Optional handling
    MISSING_TOKEN = InjectionToken("MISSING_TOKEN")
    val = root_inj.get(MISSING_TOKEN, modifiers=[ResolutionModifier.OPTIONAL])
    assert val is None, "Test 4 Gagal: @Optional harus mengembalikan None saat token absen"
    print(f"{c('✔ Test 4 Lolos:', Color.GREEN)} @Optional modifier mencegah NullInjectorError.")

    print(f"\n{c('SELURUH 4 PENGUJIAN INTELEKTUAL DI SISTEM VALID 100%!', Color.BOLD + Color.GREEN)}\n")

def interactive_cli():
    root_inj, parent_inj, child_inj = build_angular_injector_tree()
    
    while True:
        print(f"{Color.BOLD}{Color.CYAN}--- ANGULAR ENTERPRISE DI SIMULATOR MENU ---{Color.RESET}")
        print("1. Visualisasi Rantai Resolusi Hirarki Injector")
        print("2. Simulasi Resolution Modifiers (@SkipSelf, @Self, @Optional)")
        print("3. Uji Coba Multi-Provider Tokens (HTTP_INTERCEPTORS)")
        print("4. Jalankan Otomatisasi Quality Gate Test")
        print("5. Keluar")
        
        choice = input(f"{Color.YELLOW}Pilih menu (1-5): {Color.RESET}").strip()
        if choice == "1":
            demo_hierarchical_resolution(child_inj, parent_inj, root_inj)
        elif choice == "2":
            demo_resolution_modifiers(child_inj, parent_inj)
        elif choice == "3":
            demo_multi_providers(root_inj)
        elif choice == "4":
            run_self_verification()
        elif choice == "5":
            print(f"{Color.GREEN}Terima kasih telah mempelajari Angular Dependency Injection!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 1-5.{Color.RESET}\n")

if __name__ == "__main__":
    # Jika dijalankan tanpa terminal interaktif (CI/test batch mode)
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        run_self_verification()
    elif not sys.stdin.isatty():
        # Non-interactive fallback: jalankan seluruh demo & verifikasi langsung
        root_inj, parent_inj, child_inj = build_angular_injector_tree()
        demo_hierarchical_resolution(child_inj, parent_inj, root_inj)
        demo_resolution_modifiers(child_inj, parent_inj)
        demo_multi_providers(root_inj)
        run_self_verification()
    else:
        interactive_cli()
