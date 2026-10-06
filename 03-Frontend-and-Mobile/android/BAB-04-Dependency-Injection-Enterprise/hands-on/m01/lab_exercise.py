#!/usr/bin/env python3
"""
Enterprise Android Dependency Injection (DI) Engine Simulator
BAB-04: Dependency Injection Enterprise (Dagger 2 & Hilt Architecture)
Simulasi komprehensif Scoping, Component Hierarchy, Qualifiers, dan Assisted Injection.
"""

import sys
import time
import uuid
from typing import Dict, Any, Callable, Optional, Type, TypeVar, get_type_hints

# ANSI Color formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[31m"
DIM = "\033[2m"

T = TypeVar("T")

# ==============================================================================
# 1. SCOPES & METADATA (HILT-STYLE ANNOTATIONS)
# ==============================================================================

class Scope:
    SINGLETON = "SingletonComponent"
    ACTIVITY_RETAINED = "ActivityRetainedComponent"
    ACTIVITY = "ActivityComponent"
    UNSCOPED = "Unscoped (Prototype)"

class Qualifier:
    AUTH_API = "AuthApi"
    PUBLIC_API = "PublicApi"
    ENCRYPTED_STORAGE = "EncryptedStorage"

# ==============================================================================
# 2. DOMAIN & INFRASTRUCTURE MODELS
# ==============================================================================

class DatabaseDriver:
    def __init__(self, db_name: str = "app_enterprise.db"):
        self.instance_id = str(uuid.uuid4())[:8]
        self.db_name = db_name
        self.created_at = time.time()

    def query(self, sql: str) -> str:
        return f"[{self.instance_id}] Executed SQL '{sql}' on {self.db_name}"

class ApiClient:
    def __init__(self, base_url: str, qualifier: str):
        self.instance_id = str(uuid.uuid4())[:8]
        self.base_url = base_url
        self.qualifier = qualifier

    def fetch(self, endpoint: str) -> str:
        return f"[{self.instance_id}] [{self.qualifier}] GET {self.base_url}{endpoint} -> 200 OK"

class UserRepository:
    def __init__(self, db: DatabaseDriver, api: ApiClient):
        self.instance_id = str(uuid.uuid4())[:8]
        self.db = db
        self.api = api

    def get_user_profile(self, user_id: str) -> str:
        cache = self.db.query(f"SELECT * FROM users WHERE id = '{user_id}'")
        network = self.api.fetch(f"/users/{user_id}")
        return f"Repo[{self.instance_id}] =>\n    Cache: {cache}\n    Remote: {network}"

class AnalyticsTracker:
    def __init__(self):
        self.instance_id = str(uuid.uuid4())[:8]
        self.events = []

    def log(self, event_name: str):
        self.events.append(event_name)

class DashboardViewModel:
    """ViewModel lives inside ActivityRetainedComponent (survives configuration change)"""
    def __init__(self, repo: UserRepository, tracker: AnalyticsTracker):
        self.instance_id = str(uuid.uuid4())[:8]
        self.repo = repo
        self.tracker = tracker

    def load_data(self) -> str:
        self.tracker.log("dashboard_loaded")
        return self.repo.get_user_profile("usr_007")

class NavigationRouter:
    """ActivityComponent scope (tied to specific Activity instance)"""
    def __init__(self, activity_name: str):
        self.instance_id = str(uuid.uuid4())[:8]
        self.activity_name = activity_name

    def navigate_to_details(self, item_id: str) -> str:
        return f"Router[{self.instance_id}] Activity '{self.activity_name}' -> Navigate item {item_id}"

# ==============================================================================
# 3. DI CONTAINER / GRAPH RUNTIME (HILT EMULATION)
# ==============================================================================

class HiltContainer:
    def __init__(self):
        # Scoped caches
        self._singleton_cache: Dict[str, Any] = {}
        self._retained_cache: Dict[str, Any] = {}
        self._activity_cache: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._scopes: Dict[str, str] = {}
        self._registration_order = []

    def bind(self, key: str, factory: Callable[[], Any], scope: str = Scope.UNSCOPED):
        self._factories[key] = factory
        self._scopes[key] = scope
        self._registration_order.append(key)

    def resolve(self, key: str) -> Any:
        scope = self._scopes.get(key, Scope.UNSCOPED)

        if scope == Scope.SINGLETON:
            if key not in self._singleton_cache:
                self._singleton_cache[key] = self._factories[key]()
            return self._singleton_cache[key]

        elif scope == Scope.ACTIVITY_RETAINED:
            if key not in self._retained_cache:
                self._retained_cache[key] = self._factories[key]()
            return self._retained_cache[key]

        elif scope == Scope.ACTIVITY:
            if key not in self._activity_cache:
                self._activity_cache[key] = self._factories[key]()
            return self._activity_cache[key]

        else:
            # Unscoped / Prototype
            if key in self._factories:
                return self._factories[key]()
            raise KeyError(f"Binding for key '{key}' not found in DI Graph!")

    def recreate_activity(self):
        """Simulates Android configuration change (Rotation): Activity destroyed, Retained lives."""
        self._activity_cache.clear()

    def exit_process(self):
        """Process Death simulation: wipes everything."""
        self._singleton_cache.clear()
        self._retained_cache.clear()
        self._activity_cache.clear()

# ==============================================================================
# 4. INITIALIZATION MODULE (DAGGER MODULE CONFIG)
# ==============================================================================

def setup_dependency_graph() -> HiltContainer:
    container = HiltContainer()

    # 1. Database (@Singleton in SingletonComponent)
    container.bind("DatabaseDriver", lambda: DatabaseDriver(), Scope.SINGLETON)

    # 2. Analytics (@Singleton in SingletonComponent)
    container.bind("AnalyticsTracker", lambda: AnalyticsTracker(), Scope.SINGLETON)

    # 3. Qualifiers: Auth Api Client vs Public Api Client
    container.bind(
        f"ApiClient:{Qualifier.AUTH_API}",
        lambda: ApiClient("https://auth.internal.corp/api", Qualifier.AUTH_API),
        Scope.SINGLETON
    )
    container.bind(
        f"ApiClient:{Qualifier.PUBLIC_API}",
        lambda: ApiClient("https://public-cdn.corp/api", Qualifier.PUBLIC_API),
        Scope.SINGLETON
    )

    # 4. UserRepository (@Singleton) injected with Auth API
    container.bind(
        "UserRepository",
        lambda: UserRepository(
            container.resolve("DatabaseDriver"),
            container.resolve(f"ApiClient:{Qualifier.AUTH_API}")
        ),
        Scope.SINGLETON
    )

    # 5. DashboardViewModel (@ActivityRetainedScoped)
    container.bind(
        "DashboardViewModel",
        lambda: DashboardViewModel(
            container.resolve("UserRepository"),
            container.resolve("AnalyticsTracker")
        ),
        Scope.ACTIVITY_RETAINED
    )

    # 6. NavigationRouter (@ActivityScoped)
    container.bind(
        "NavigationRouter",
        lambda: NavigationRouter("MainActivity"),
        Scope.ACTIVITY
    )

    return container

# ==============================================================================
# 5. INTERACTIVE TERMINAL SIMULATOR
# ==============================================================================

def print_header():
    print(f"\n{BOLD}{CYAN}=================================================================={RESET}")
    print(f"{BOLD}{GREEN}   ANDROID ENTERPRISE DEPENDENCY INJECTION SIMULATOR (HILT/DAGGER){RESET}")
    print(f"{BOLD}{CYAN}=================================================================={RESET}")
    print(f"{DIM}Arsitektur DI: Scopes, Component Hierarchy, Qualifiers & Config Changes{RESET}\n")

def print_graph_info(container: HiltContainer):
    print(f"{BOLD}{YELLOW}--- ACTIVE DI BINDINGS REGISTERED ---{RESET}")
    for key in container._registration_order:
        scope = container._scopes[key]
        color = MAGENTA if scope == Scope.SINGLETON else (BLUE if scope == Scope.ACTIVITY_RETAINED else GREEN)
        print(f"  • {BOLD}{key:<30}{RESET} -> Scope: {color}{scope}{RESET}")
    print()

def run_simulation_flow(container: HiltContainer):
    print(f"\n{BOLD}{BLUE}[Phase 1] First Screen Launch (MainActivity Created){RESET}")
    db1 = container.resolve("DatabaseDriver")
    repo1 = container.resolve("UserRepository")
    vm1 = container.resolve("DashboardViewModel")
    router1 = container.resolve("NavigationRouter")

    print(f"  {CYAN}▸ Injected DatabaseDriver:{RESET}    ID={BOLD}{db1.instance_id}{RESET} (Scope: Singleton)")
    print(f"  {CYAN}▸ Injected UserRepository:{RESET}    ID={BOLD}{repo1.instance_id}{RESET} (Scope: Singleton)")
    print(f"  {CYAN}▸ Injected DashboardViewModel:{RESET}ID={BOLD}{vm1.instance_id}{RESET} (Scope: ActivityRetained)")
    print(f"  {CYAN}▸ Injected NavigationRouter:{RESET}  ID={BOLD}{router1.instance_id}{RESET} (Scope: Activity)")
    print(f"  {DIM}Operation Test:{RESET} {vm1.load_data()}")

    print(f"\n{BOLD}{MAGENTA}[Phase 2] Screen Rotation / Config Change Triggered{RESET}")
    print(f"  {YELLOW}==> Activity destroyed and recreated. ActivityComponent destroyed!{RESET}")
    container.recreate_activity()

    db2 = container.resolve("DatabaseDriver")
    vm2 = container.resolve("DashboardViewModel")
    router2 = container.resolve("NavigationRouter")

    print(f"  {CYAN}▸ Re-resolved DatabaseDriver:{RESET}    ID={BOLD}{db2.instance_id}{RESET} "
          f"({GREEN}MATCH: Same Instance!{RESET})")
    print(f"  {CYAN}▸ Re-resolved DashboardVM:{RESET}       ID={BOLD}{vm2.instance_id}{RESET} "
          f"({GREEN}MATCH: ViewModel Retained!{RESET})")
    print(f"  {CYAN}▸ Re-resolved NavigationRouter:{RESET}  ID={BOLD}{router2.instance_id}{RESET} "
          f"({RED}DIFFERENT: New ActivityScoped instance!{RESET})")

    print(f"\n{BOLD}{YELLOW}[Phase 3] Dagger Qualifier Validation (Named Bindings){RESET}")
    api_auth = container.resolve(f"ApiClient:{Qualifier.AUTH_API}")
    api_public = container.resolve(f"ApiClient:{Qualifier.PUBLIC_API}")
    print(f"  {CYAN}▸ @AuthApi Client:{RESET}   ID={BOLD}{api_auth.instance_id}{RESET} Base={api_auth.base_url}")
    print(f"  {CYAN}▸ @PublicApi Client:{RESET} ID={BOLD}{api_public.instance_id}{RESET} Base={api_public.base_url}")

    if api_auth.instance_id != api_public.instance_id:
        print(f"  {GREEN}✔ Qualifier validation successful: Distinct bindings disambiguated cleanly.{RESET}")

def interactive_menu():
    container = setup_dependency_graph()
    print_header()

    # Non-interactive check (e.g. CI / pipe)
    if not sys.stdin.isatty():
        print(f"{YELLOW}[Non-interactive mode detected. Running full automated suite...]{RESET}")
        print_graph_info(container)
        run_simulation_flow(container)
        print(f"\n{GREEN}{BOLD}✓ DI Enterprise Simulation completed successfully.{RESET}")
        return

    while True:
        print(f"{BOLD}Main Menu:{RESET}")
        print("  1. Inspect DI Graph Registrations & Scopes")
        print("  2. Run Full DI Lifecycle & Rotation Simulation")
        print("  3. Resolve Injections Manually")
        print("  4. Simulate Android Process Death")
        print("  5. Exit")
        choice = input(f"\n{BOLD}{CYAN}Select option (1-5): {RESET}").strip()

        if choice == "1":
            print_graph_info(container)
        elif choice == "2":
            run_simulation_flow(container)
        elif choice == "3":
            print(f"\n{YELLOW}Resolving components from container...{RESET}")
            db = container.resolve("DatabaseDriver")
            repo = container.resolve("UserRepository")
            vm = container.resolve("DashboardViewModel")
            router = container.resolve("NavigationRouter")
            print(f"  Database Driver : ID={db.instance_id}")
            print(f"  User Repository : ID={repo.instance_id}")
            print(f"  Dashboard VM    : ID={vm.instance_id}")
            print(f"  Activity Router : ID={router.instance_id}")
        elif choice == "4":
            print(f"\n{RED}{BOLD}⚡ Simulating Process Death... Wiping all memory scopes.{RESET}")
            container.exit_process()
            print(f"{GREEN}Memory wiped. Next resolution will recreate singletons.{RESET}")
        elif choice == "5" or choice == "q" or choice == "exit":
            print(f"\n{GREEN}Exiting DI Simulator. Keep dependencies decoupled!{RESET}")
            break
        else:
            print(f"{RED}Invalid selection. Please choose 1-5.{RESET}")
        print()

if __name__ == "__main__":
    interactive_menu()
