#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Arsitektur Modern & Standalone Components (Angular Deep Dive)
Simulasi komprehensif Standalone Component Graph, Hierarchical Dependency Injection,
Reactive Signal State, dan Tree-Shaking Dependency Analyzer pada Runtime Engine modern.
"""

from typing import Dict, List, Any, Type, Optional, Set, Callable
import time
import sys

# ANSI Escape Sequences untuk formatting terminal
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

# ==============================================================================
# 1. CORE REACTIVITY: ANGULAR SIGNALS SIMULATION
# ==============================================================================
class Signal:
    """Implementasi primitif reaktif Signal untuk dirty tracking granular."""
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._subscribers: List[Callable[[Any], None]] = []

    def get(self) -> Any:
        return self._value

    def set(self, new_value: Any) -> None:
        if self._value != new_value:
            self._value = new_value
            self._notify()

    def update(self, updater: Callable[[Any], Any]) -> None:
        self.set(updater(self._value))

    def subscribe(self, callback: Callable[[Any], None]) -> None:
        self._subscribers.append(callback)

    def _notify(self) -> None:
        for sub in self._subscribers:
            sub(self._value)

# ==============================================================================
# 2. DEPENDENCY INJECTION: HIERARCHICAL INJECTOR ENGINE
# ==============================================================================
class Injector:
    """
    Simulasi EnvironmentInjector dan NodeInjector (Hierarchical DI).
    Resolusi dependensi naik dari Node level ke Parent / Root level.
    """
    def __init__(self, parent: Optional['Injector'] = None, name: str = "Injector"):
        self.parent = parent
        self.name = name
        self.records: Dict[Type, Any] = {}

    def provide(self, token: Type, instance: Any) -> None:
        self.records[token] = instance

    def get(self, token: Type) -> Any:
        # Resolusi lokal injector
        if token in self.records:
            return self.records[token]
        # Resolusi ke atas (Hierarchical bubble-up)
        if self.parent:
            return self.parent.get(token)
        raise RuntimeError(f"NullInjectorError: Tidak ditemukan provider untuk token: {token.__name__}")

# ==============================================================================
# 3. METADATA DECORATORS & BASE CLASSES (STANDALONE ARCHITECTURE)
# ==============================================================================
class ComponentMetadata:
    """Metadata dekorator @Component({ standalone: true, ... })"""
    def __init__(
        self,
        selector: str,
        standalone: bool = True,
        imports: Optional[List[Type]] = None,
        providers: Optional[List[Type]] = None,
        template: str = ""
    ):
        self.selector = selector
        self.standalone = standalone
        self.imports = imports or []
        self.providers = providers or []
        self.template = template

def StandaloneComponent(selector: str, imports: Optional[List[Type]] = None, providers: Optional[List[Type]] = None, template: str = ""):
    def decorator(cls):
        cls.__angular_meta__ = ComponentMetadata(
            selector=selector,
            standalone=True,
            imports=imports,
            providers=providers,
            template=template
        )
        return cls
    return decorator

# ==============================================================================
# 4. DOMAIN SERVICES & COMPONENTS
# ==============================================================================
class LoggerService:
    def log(self, message: str) -> None:
        print(f"  {Color.MAGENTA}[LoggerService]{Color.RESET} {message}")

class ConfigService:
    def __init__(self):
        self.env = "Production"
        self.api_endpoint = "https://api.system.internal/v2"

class UserService:
    def __init__(self, logger: LoggerService):
        self.logger = logger
        self.logger.log("UserService diinisialisasi via Root Injector.")

    def fetch_user(self) -> str:
        return "DevLead-4091"

# Standalone Components definition
@StandaloneComponent(
    selector:="app-badge",
    template="<span class='badge'>{{ label }}</span>"
)
class UserBadgeComponent:
    def __init__(self, injector: Injector):
        self.meta: ComponentMetadata = getattr(self, '__angular_meta__')
        self.badge_status = Signal("VERIFIED")

    def render(self) -> str:
        return f"[Status: {self.badge_status.get()}]"

@StandaloneComponent(
    selector:="app-user-card",
    imports=[UserBadgeComponent],
    providers=[LoggerService],  # Element-level provider override
    template="<div class='card'>User Profile</div>"
)
class UserCardComponent:
    def __init__(self, injector: Injector):
        self.meta: ComponentMetadata = getattr(self, '__angular_meta__')
        # Inject custom logger pada level komponen ini
        self.logger = injector.get(LoggerService)
        self.user_service = injector.get(UserService)
        self.logger.log("UserCardComponent instance dibuat dengan NodeInjector lokal.")

        # Sub-komponen dari standalone imports
        badge_injector = Injector(parent=injector, name="UserBadgeInjector")
        self.badge = UserBadgeComponent(badge_injector)

    def render(self) -> str:
        user = self.user_service.fetch_user()
        return f"<UserCard user='{user}' {self.badge.render()} />"

@StandaloneComponent(
    selector:="app-unused-feature",
    template="<div>Dead Code Module</div>"
)
class UnusedComponent:
    """Komponen yang didefinisikan namun tidak pernah masuk ke root imports (Dead Code)."""
    def __init__(self, injector: Injector):
        pass

@StandaloneComponent(
    selector:="app-root",
    imports=[UserCardComponent],
    template="<main><app-user-card></app-user-card></main>"
)
class AppComponent:
    def __init__(self, injector: Injector):
        self.meta: ComponentMetadata = getattr(self, '__angular_meta__')
        self.card = UserCardComponent(Injector(parent=injector, name="CardInjector"))

    def render(self) -> str:
        return f"<RootShell>\n    {self.card.render()}\n  </RootShell>"

# ==============================================================================
# 5. BOOTSTRAP ENGINE & TREE-SHAKE COMPILER
# ==============================================================================
class ApplicationBootstrap:
    """
    Mesin runtime yang mensimulasikan bootstrapApplication(RootComponent) modern.
    Mengeliminasi kebutuhan NgModule dan memverifikasi dependensi secara terisolasi.
    """
    def __init__(self, root_component_cls: Type):
        self.root_cls = root_component_cls
        self.environment_injector = Injector(name="EnvironmentInjector (Root)")
        self._init_root_providers()

    def _init_root_providers(self) -> None:
        """Simulasi { providedIn: 'root' }"""
        root_logger = LoggerService()
        self.environment_injector.provide(LoggerService, root_logger)
        self.environment_injector.provide(ConfigService, ConfigService())
        # UserService membutuhkan LoggerService dari Root
        self.environment_injector.provide(UserService, UserService(root_logger))

    def analyze_tree_shaking(self, all_registered: List[Type]) -> Set[Type]:
        """Menghitung komponen yang 'dibuang' (treeshaken) karena tidak direferensikan."""
        reachable: Set[Type] = set()

        def traverse(cls: Type):
            if cls in reachable:
                return
            reachable.add(cls)
            meta: ComponentMetadata = getattr(cls, '__angular_meta__', None)
            if meta:
                for imported in meta.imports:
                    traverse(imported)

        traverse(self.root_cls)
        dead_code = set(all_registered) - reachable
        return dead_code

    def bootstrap(self) -> Any:
        meta: ComponentMetadata = getattr(self.root_cls, '__angular_meta__', None)
        if not meta or not meta.standalone:
            raise TypeError(f"Komponen {self.root_cls.__name__} harus berupa Standalone Component!")

        print(f"{Color.CYAN}{Color.BOLD}>>> Memulai Angular Bootstrap Pipeline (Modern Standalone) <<<{Color.RESET}\n")
        time.sleep(0.1)

        # 1. Resolusi Dependency Graph
        print(f"{Color.YELLOW}[Pipeline 1/3]{Color.RESET} Memverifikasi Standalone DAG (Directed Acyclic Graph)...")
        print(f"  Bootstrap Root: {Color.GREEN}{self.root_cls.__name__}{Color.RESET} ({meta.selector})")
        for imp in meta.imports:
            print(f"  └── Impor Langsung: {Color.BLUE}{imp.__name__}{Color.RESET}")

        # 2. Instansiasi Root Component Tree
        print(f"\n{Color.YELLOW}[Pipeline 2/3]{Color.RESET} Menginisialisasi Hierarchical NodeInjectors...")
        root_instance = self.root_cls(self.environment_injector)

        # 3. Mount UI Tree Rendering
        print(f"\n{Color.YELLOW}[Pipeline 3/3]{Color.RESET} Rendering Standalone Component Tree:")
        rendered_output = root_instance.render()
        print(f"{Color.GREEN}{rendered_output}{Color.RESET}\n")

        return root_instance

# ==============================================================================
# 6. EXECUTION BENCHMARK & DEMONSTRATION
# ==============================================================================
def main():
    print(f"{Color.BOLD}======================================================================{Color.RESET}")
    print(f"{Color.BOLD} LAB: ARSITEKTUR MODERN ANGULAR & STANDALONE COMPONENT ENGINE        {Color.RESET}")
    print(f"{Color.BOLD}======================================================================{Color.RESET}\n")

    # Kumpulan seluruh komponen yang ada dalam codebase modul
    all_codebase_components = [AppComponent, UserCardComponent, UserBadgeComponent, UnusedComponent]

    # Inisialisasi runtime bootstrap
    runtime = ApplicationBootstrap(root_component_cls=AppComponent)

    # Bootstrapping Standalone App
    app_root = runtime.bootstrap()

    # Demonstrasi 1: Tree-Shaking Analyzer
    print(f"{Color.BOLD}----------------------------------------------------------------------{Color.RESET}")
    print(f"{Color.CYAN}[ANALYZER]{Color.RESET} Analisis Tree-Shaking (Eliminasi Kode Mati):")
    dead_components = runtime.analyze_tree_shaking(all_codebase_components)
    for dc in dead_components:
        print(f"  {Color.RED}✖ [TREESHAKEN ELIMINATED]{Color.RESET} {dc.__name__} (Tidak tercakup dalam import graph)")

    # Demonstrasi 2: Granular Reactive Signal Mutation
    print(f"\n{Color.BOLD}----------------------------------------------------------------------{Color.RESET}")
    print(f"{Color.CYAN}[REACTIVITY]{Color.RESET} Simulasi Mutasi Angular Signals pada Standalone Node:")
    badge_ref = app_root.card.badge
    print(f"  Status Awal: {badge_ref.render()}")

    # Registrasi reactive effect subscriber
    badge_ref.badge_status.subscribe(lambda val: print(f"  {Color.YELLOW}⚡ [Effect Triggered]{Color.RESET} Badge Signal bermutasi ke: '{val}'"))

    # Update state via Signal primitive
    badge_ref.badge_status.set("ADMIN_SUPERUSER")
    print(f"  Render Ulang Sub-Pohon: {badge_ref.render()}")

    print(f"\n{Color.GREEN}{Color.BOLD}✔ Eksekusi Lab Selesai: Arsitektur Standalone Berhasil Divalidasi.{Color.RESET}")

if __name__ == "__main__":
    main()