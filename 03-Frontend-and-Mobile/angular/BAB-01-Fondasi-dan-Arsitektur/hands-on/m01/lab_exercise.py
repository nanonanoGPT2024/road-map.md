#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi dan Arsitektur Inti Angular (BAB-01)
Mendemonstrasikan secara interaktif dengan ANSI Terminal:
1. Hierarchical Dependency Injection (Root vs Component Injector)
2. Component Lifecycle Hooks Pipeline (ngOnInit -> ngDoCheck -> ngOnDestroy)
3. Change Detection Mechanism (Zone-like Dirty Checking vs Reactive Signal)
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Type

# ==============================================================================
# ANSI Color Palette for Terminal Output
# ==============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"


def header(title: str) -> None:
    print(f"\n{BG_BLUE}{WHITE}{BOLD} [ANGULAR LAB] {title.upper()} {RESET}")
    print(f"{CYAN}{'=' * 65}{RESET}")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{MAGENTA}>>> {title}{RESET}")


def info(msg: str) -> None:
    print(f"  {CYAN}ℹ{RESET}  {msg}")


def success(msg: str) -> None:
    print(f"  {GREEN}✔{RESET}  {BOLD}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET}  {msg}")


# ==============================================================================
# 1. Hierarchical Dependency Injection System
# ==============================================================================
class InjectionToken:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"Token({self.name})"


class Injector:
    def __init__(self, name: str, parent: Optional["Injector"] = None):
        self.name = name
        self.parent = parent
        self.records: Dict[Any, Any] = {}
        self.instances: Dict[Any, Any] = {}

    def provide(self, token: Any, provider: Callable[[], Any], singleton: bool = True) -> None:
        self.records[token] = {"factory": provider, "singleton": singleton}

    def get(self, token: Any) -> Any:
        if token in self.records:
            spec = self.records[token]
            if spec["singleton"]:
                if token not in self.instances:
                    self.instances[token] = spec["factory"]()
                return self.instances[token]
            return spec["factory"]()

        if self.parent:
            return self.parent.get(token)

        raise LookupError(f"No provider found for token {token} in injector hierarchy!")


# Sample Services for DI Simulation
class ApiService:
    def __init__(self):
        self.instance_id = id(self)
        self.base_url = "https://api.example.com/v1"


class FeatureConfigService:
    def __init__(self, scope_name: str):
        self.instance_id = id(self)
        self.scope_name = scope_name


# ==============================================================================
# 2. Component Architecture & Lifecycle Pipeline
# ==============================================================================
class AngularComponent:
    def __init__(self, selector: str, injector: Injector):
        self.selector = selector
        self.injector = injector
        self.inputs: Dict[str, Any] = {}
        self._prev_inputs: Dict[str, Any] = {}
        self.is_destroyed = False
        print(f"  {DIM}[Constructor]{RESET} Instantiating <{self.selector}>")

    def ng_on_init(self) -> None:
        print(f"  {GREEN}[ngOnInit]{RESET} Component initialized: <{self.selector}>")

    def ng_on_changes(self, changes: Dict[str, Dict[str, Any]]) -> None:
        print(f"  {YELLOW}[ngOnChanges]{RESET} Detected Input changes: {changes}")

    def ng_do_check(self) -> None:
        print(f"  {CYAN}[ngDoCheck]{RESET} Running manual/custom change detection")

    def ng_after_view_init(self) -> None:
        print(f"  {BLUE}[ngAfterViewInit]{RESET} Template DOM rendered for <{self.selector}>")

    def ng_on_destroy(self) -> None:
        self.is_destroyed = True
        print(f"  {RED}[ngOnDestroy]{RESET} Cleaning subscriptions and DOM node for <{self.selector}>")

    def set_input(self, key: str, value: Any) -> None:
        old_val = self.inputs.get(key)
        if old_val != value:
            self.inputs[key] = value
            self.ng_on_changes({key: {"previous": old_val, "current": value}})
            self.ng_do_check()


# ==============================================================================
# 3. Change Detection & Reactive Signals Simulation
# ==============================================================================
class Signal:
    """Simulates Angular modern fine-grained signal reactive primitive."""
    def __init__(self, initial_value: Any, name: str = "signal"):
        self._value = initial_value
        self.name = name
        self.subscribers: List[Callable[[Any], None]] = []

    def get(self) -> Any:
        return self._value

    def set(self, new_value: Any) -> None:
        if self._value != new_value:
            old = self._value
            self._value = new_value
            for subscriber in self.subscribers:
                subscriber(new_value)

    def update(self, fn: Callable[[Any], Any]) -> None:
        self.set(fn(self._value))

    def subscribe(self, callback: Callable[[Any], None]) -> None:
        self.subscribers.append(callback)


class Computed:
    """Simulates Angular computed() signal."""
    def __init__(self, formula: Callable[[], Any], dependencies: List[Signal]):
        self.formula = formula
        self.dependencies = dependencies
        self._cached_value = formula()
        for dep in self.dependencies:
            dep.subscribe(self._on_dependency_change)

    def _on_dependency_change(self, _: Any) -> None:
        self._cached_value = self.formula()

    def get(self) -> Any:
        return self._cached_value


# ==============================================================================
# Interactive Demos
# ==============================================================================
def demo_hierarchical_di() -> None:
    header("1. Hierarchical Dependency Injection Demonstration")
    info("Membangun Root Injector dan Child Component Injector")

    # 1. Create Root Injector (providedIn: 'root')
    root_injector = Injector("RootInjector")
    root_injector.provide(ApiService, lambda: ApiService(), singleton=True)

    # 2. Create Child Injectors (provided in Component providers: [...])
    dashboard_injector = Injector("DashboardComponentInjector", parent=root_injector)
    dashboard_injector.provide(
        FeatureConfigService, lambda: FeatureConfigService("DashboardScope"), singleton=True
    )

    settings_injector = Injector("SettingsComponentInjector", parent=root_injector)
    settings_injector.provide(
        FeatureConfigService, lambda: FeatureConfigService("SettingsScope"), singleton=True
    )

    info("Resolving ApiService dari Root Injector vs Child Injectors:")
    api_root = root_injector.get(ApiService)
    api_dash = dashboard_injector.get(ApiService)
    api_sett = settings_injector.get(ApiService)

    print(f"    - Root ApiService ID     : {YELLOW}{api_root.instance_id}{RESET}")
    print(f"    - Dashboard ApiService ID: {YELLOW}{api_dash.instance_id}{RESET}")
    print(f"    - Settings ApiService ID : {YELLOW}{api_sett.instance_id}{RESET}")

    if api_root.instance_id == api_dash.instance_id == api_sett.instance_id:
        success("Singleton Berhasil: ApiService dibagikan via bubbling ke parent Root!")

    info("Resolving FeatureConfigService yang scoped pada masing-masing Component Injector:")
    config_dash = dashboard_injector.get(FeatureConfigService)
    config_sett = settings_injector.get(FeatureConfigService)

    print(f"    - Dashboard Config Scope: {MAGENTA}{config_dash.scope_name}{RESET} (ID: {config_dash.instance_id})")
    print(f"    - Settings Config Scope : {MAGENTA}{config_sett.scope_name}{RESET} (ID: {config_sett.instance_id})")

    if config_dash.instance_id != config_sett.instance_id:
        success("Isolation Berhasil: Setiap component memiliki instance terisolasi sendiri!")

    info("Mencoba resolve token scoped dari Root (akan gagal karena isolasi anak):")
    try:
        root_injector.get(FeatureConfigService)
    except LookupError as e:
        success(f"Diharapkan Error Terjadi: {e}")


def demo_lifecycle_pipeline() -> None:
    header("2. Component Lifecycle Pipeline Simulation")
    info("Mensimulasikan transisi status: Creation -> Inputs -> Checked -> Destroy")

    dummy_injector = Injector("MockInjector")
    cmp = AngularComponent(selector="app-user-card", injector=dummy_injector)

    time.sleep(0.1)
    cmp.set_input("username", "budi_developer")

    time.sleep(0.1)
    cmp.ng_on_init()

    time.sleep(0.1)
    cmp.ng_after_view_init()

    subheader("Triggering Property Mutator / Change Detection")
    cmp.set_input("username", "budi_tech_lead")

    subheader("Triggering Component Teardown (Navigation Out)")
    cmp.ng_on_destroy()
    success("Komponen berhasil menyelesaikan siklus hidup penuh (Lifecycle compliant)!")


def demo_change_detection_signals() -> None:
    header("3. Change Detection: Zone.js (Dirty-Check) vs Signal Reactive")
    info("A. Zone.js Model: Tree Traversal Dirty Checking")
    components = ["AppRoot", "Navbar", "Sidebar", "UserProfile", "AvatarIcon"]
    dirty_state = {"UserProfile": True}

    print(f"    {DIM}State dirty pada 'UserProfile'. Zone.js memicu Tick CD dari Root:{RESET}")
    for node in components:
        is_dirty = dirty_state.get(node, False)
        status = f"{RED}[DIRTY -> RE-CHECK]{RESET}" if is_dirty else f"{GREEN}[CHECKED NO-CHANGE]{RESET}"
        print(f"    Checking node: {node:<15} {status}")

    info("B. Modern Angular Signal Model: Fine-Grained Reactive Execution")
    count_signal = Signal(10, name="counter")
    multiplier_signal = Signal(2, name="multiplier")

    total_computed = Computed(
        lambda: count_signal.get() * multiplier_signal.get(),
        dependencies=[count_signal, multiplier_signal],
    )

    print(f"    Nilai Awal Counter    : {CYAN}{count_signal.get()}{RESET}")
    print(f"    Nilai Awal Multiplier : {CYAN}{multiplier_signal.get()}{RESET}")
    print(f"    Nilai Computed Total  : {YELLOW}{total_computed.get()}{RESET}")

    info("Mengubah nilai signal counter -> 25:")
    count_signal.set(25)
    print(f"    Nilai Akhir Computed  : {BOLD}{GREEN}{total_computed.get()}{RESET} (Hanya computed yang bereaksi!)")
    success("Fine-Grained Change Detection selesai tanpa menjelajah seluruh component tree!")


def run_full_suite() -> None:
    print(f"{BOLD}{WHITE}Memulai Simulasi Teknis Lengkap Arsitektur Angular...{RESET}")
    demo_hierarchical_di()
    demo_lifecycle_pipeline()
    demo_change_detection_signals()
    header("Kesimpulan Evaluasi Lab")
    success("Semua simulasi fondasi arsitektur Angular (DI, Lifecycle, Signals) selesai dengan sukses!")


def interactive_menu() -> None:
    while True:
        print(f"\n{BOLD}{CYAN}=== ANGULAR ARCHITECTURE LAB MENU ==={RESET}")
        print("1. Jalankan Simulasi Hierarchical Dependency Injection")
        print("2. Jalankan Simulasi Siklus Hidup Komponen (Lifecycle Hooks)")
        print("3. Jalankan Simulasi Change Detection (Dirty Check vs Signals)")
        print("4. Jalankan Semua Simulasi Otomatis (Full Suite)")
        print("5. Keluar")
        choice = input(f"{BOLD}Pilih opsi [1-5]: {RESET}").strip()

        if choice == "1":
            demo_hierarchical_di()
        elif choice == "2":
            demo_lifecycle_pipeline()
        elif choice == "3":
            demo_change_detection_signals()
        elif choice == "4":
            run_full_suite()
        elif choice == "5":
            print(f"{GREEN}Terima kasih telah menjalankan Lab Fondasi Angular!{RESET}")
            break
        else:
            warn("Pilihan tidak valid, silakan ulangi.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_full_suite()
    else:
        # Defaults to interactive if tty, otherwise run suite automatically
        if sys.stdin.isatty():
            interactive_menu()
        else:
            run_full_suite()
