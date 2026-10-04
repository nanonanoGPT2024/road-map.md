#!/usr/bin/env python3
"""
Lab Hands-on: Android DI Enterprise (Dagger-Hilt & KSP Deep Dive Simulation)
Simulates:
  1. KSP (Kotlin Symbol Processing) compile-time AST/metadata inspection.
  2. DAG validation (Cyclic Dependency & Scope Leak Detection).
  3. Direct Code Generation of Factory & Binding classes (avoiding runtime reflection).
  4. Scoped Component Hierarchies (SingletonComponent -> ActivityComponent).
"""

import sys
import time
from typing import Dict, Any, List, Set, Type, Optional, Callable

# --- ANSI Terminal Color Palette ---
CLR_RESET  = "\033[0m"
CLR_CYAN   = "\033[1;36m"
CLR_GREEN  = "\033[1;32m"
CLR_YELLOW = "\033[1;33m"
CLR_RED    = "\033[1;31m"
CLR_MAG    = "\033[1;35m"
CLR_GRAY   = "\033[0;90m"
CLR_BOLD   = "\033[1m"


# =====================================================================
# 1. KSP METADATA & ANNOTATION ABSTRACTIONS
# =====================================================================

class Scope:
    SINGLETON = "Singleton"
    ACTIVITY = "ActivityScoped"
    UNSCOPED = "Unscoped"

def Inject(cls_or_func):
    """Marks a constructor or provider method for compile-time processing."""
    setattr(cls_or_func, "__dagger_injected__", True)
    return cls_or_func

def Singleton(cls):
    """Binds lifecycle to SingletonComponent."""
    setattr(cls, "__dagger_scope__", Scope.SINGLETON)
    return cls

def ActivityScoped(cls):
    """Binds lifecycle to ActivityComponent."""
    setattr(cls, "__dagger_scope__", Scope.ACTIVITY)
    return cls

def Module(cls):
    """Declares a Dagger Module providing dependencies."""
    setattr(cls, "__dagger_module__", True)
    return cls

def Provides(scope: str = Scope.UNSCOPED):
    """Simulates @Provides method annotation with an explicit target scope."""
    def decorator(func):
        setattr(func, "__dagger_provides__", True)
        setattr(func, "__dagger_scope__", scope)
        return func
    return decorator


# =====================================================================
# 2. DOMAIN LOGIC (Target Android Enterprise Architecture)
# =====================================================================

class NetworkClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = f"NET-{id(self) % 10000:04d}"

class DatabaseDriver:
    def __init__(self):
        self.db_id = f"SQLITE-{id(self) % 10000:04d}"

@Singleton
class UserRepository:
    @Inject
    def __init__(self, client: NetworkClient, db: DatabaseDriver):
        self.client = client
        self.db = db
        self.repo_id = f"REPO-{id(self) % 10000:04d}"

@ActivityScoped
class NavigationRouter:
    @Inject
    def __init__(self):
        self.router_id = f"ROUTER-{id(self) % 10000:04d}"

@ActivityScoped
class UserViewModel:
    @Inject
    def __init__(self, repo: UserRepository, router: NavigationRouter):
        self.repo = repo
        self.router = router
        self.vm_id = f"VM-{id(self) % 10000:04d}"

@Module
class NetworkModule:
    @Provides(scope=Scope.SINGLETON)
    @staticmethod
    def provide_network_client() -> NetworkClient:
        return NetworkClient("https://api.enterprise.android.internal")

    @Provides(scope=Scope.SINGLETON)
    @staticmethod
    def provide_db_driver() -> DatabaseDriver:
        return DatabaseDriver()


# =====================================================================
# 3. KSP SIMULATION & DAG COMPILER VERIFIER
# =====================================================================

class SymbolSymbolProcessor:
    """Simulates KSP AST Parsing, Scope Validation, and DAG compilation."""
    
    def __init__(self):
        self.bindings: Dict[str, Dict[str, Any]] = {}
        self.dependency_graph: Dict[str, List[str]] = {}

    def register_type(self, cls: Type[Any], deps: List[str]):
        scope = getattr(cls, "__dagger_scope__", Scope.UNSCOPED)
        name = cls.__name__
        self.bindings[name] = {
            "type": "CONSTRUCTOR",
            "target": cls,
            "scope": scope,
            "deps": deps
        }
        self.dependency_graph[name] = deps

    def register_provider(self, name: str, return_type: Type[Any], scope: str, provider_fn: Callable, deps: List[str]):
        self.bindings[name] = {
            "type": "PROVIDER",
            "target": provider_fn,
            "return_type": return_type,
            "scope": scope,
            "deps": deps
        }
        self.dependency_graph[name] = deps

    def validate_no_cycles(self):
        """Standard DFS cycle detector across compile-time dependency symbols."""
        visited: Set[str] = set()
        recursion_stack: Set[str] = set()

        def dfs(node: str, path: List[str]):
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)

            for neighbor in self.dependency_graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in recursion_stack:
                    cycle = " -> ".join(path + [neighbor])
                    raise ValueError(f"Dagger Graph Cycle Detected: {cycle}")

            recursion_stack.remove(node)
            path.pop()

        for node in list(self.dependency_graph.keys()):
            if node not in visited:
                dfs(node, [])

    def validate_scope_hierarchy(self):
        """
        Validates Dagger Scope invariants:
        A broader scope (e.g. Singleton) MUST NEVER hold a direct reference
        to a narrower scope (e.g. ActivityScoped).
        """
        scope_precedence = {Scope.SINGLETON: 1, Scope.ACTIVITY: 2, Scope.UNSCOPED: 3}
        for parent_node, deps in self.dependency_graph.items():
            parent_scope = self.bindings[parent_node]["scope"]
            for child_node in deps:
                if child_node in self.bindings:
                    child_scope = self.bindings[child_node]["scope"]
                    if scope_precedence.get(parent_scope, 99) < scope_precedence.get(child_scope, 99):
                        raise RuntimeError(
                            f"Scope Invariant Violation: '{parent_node}' [{parent_scope}] "
                            f"attempts to hold '{child_node}' [{child_scope}]."
                        )


# =====================================================================
# 4. KSP CODE GENERATION (Generates Static Factory Providers)
# =====================================================================

class GeneratedFactory:
    """Base class for code-generated factory instances (like generated Dagger Factories)."""
    def get(self, locator: Callable[[str], Any]) -> Any:
        raise NotImplementedError()

def synthesize_factory(binding_meta: Dict[str, Any]) -> GeneratedFactory:
    """Emulates compiler emitting ClassName_Factory.java to omit runtime reflection."""
    deps = binding_meta["deps"]
    target = binding_meta["target"]
    is_provider = binding_meta["type"] == "PROVIDER"

    class CompiledFactory(GeneratedFactory):
        def get(self, locator: Callable[[str], Any]) -> Any:
            resolved_args = [locator(dep) for dep in deps]
            return target(*resolved_args)

    return CompiledFactory()


# =====================================================================
# 5. ENTERPRISE HIERARCHICAL RUNTIME CONTAINERS
# =====================================================================

class SingletonComponent:
    """Root Application Component simulating Android Application lifecycle."""
    def __init__(self, processor: SymbolSymbolProcessor):
        self.processor = processor
        self.factories: Dict[str, GeneratedFactory] = {
            k: synthesize_factory(v) for k, v in processor.bindings.items()
        }
        self.scoped_cache: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        meta = self.processor.bindings.get(key)
        if not meta:
            raise KeyError(f"No binding found for key: {key}")

        if meta["scope"] == Scope.ACTIVITY:
            raise RuntimeError(f"Cannot resolve [{key}] directly from SingletonComponent!")

        if meta["scope"] == Scope.SINGLETON:
            if key not in self.scoped_cache:
                self.scoped_cache[key] = self.factories[key].get(self.get)
            return self.scoped_cache[key]

        return self.factories[key].get(self.get)

class ActivityComponent:
    """Subcomponent simulating Activity context tied to lifecycle boundaries."""
    def __init__(self, parent: SingletonComponent, activity_id: str):
        self.parent = parent
        self.activity_id = activity_id
        self.scoped_cache: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        meta = self.parent.processor.bindings.get(key)
        if not meta:
            raise KeyError(f"No binding found for key: {key}")

        # Check local Activity scope
        if meta["scope"] == Scope.ACTIVITY:
            if key not in self.scoped_cache:
                # Delegate sub-dependencies through this component's locator
                self.scoped_cache[key] = self.parent.factories[key].get(self.get)
            return self.scoped_cache[key]

        # Delegate upward to SingletonComponent
        return self.parent.get(key)


# =====================================================================
# 6. EXECUTION RUNTIME & VERIFICATION HARNESS
# =====================================================================

def main():
    print(f"{CLR_CYAN}{CLR_BOLD}=== [Android Hilt & KSP Compilation & Runtime Simulator] ==={CLR_RESET}\n")

    # --- Phase 1: Symbol Processing (KSP) ---
    print(f"{CLR_MAG}[Phase 1: KSP Symbol Processing]{CLR_RESET}")
    processor = SymbolSymbolProcessor()

    # Emulate symbol scanning of NetworkModule
    processor.register_provider("NetworkClient", NetworkClient, Scope.SINGLETON, NetworkModule.provide_network_client, [])
    processor.register_provider("DatabaseDriver", DatabaseDriver, Scope.SINGLETON, NetworkModule.provide_db_driver, [])

    # Emulate constructor processing
    processor.register_type(UserRepository, ["NetworkClient", "DatabaseDriver"])
    processor.register_type(NavigationRouter, [])
    processor.register_type(UserViewModel, ["UserRepository", "NavigationRouter"])

    for symbol, meta in processor.bindings.items():
        print(f"  {CLR_GRAY}→ Processed Symbol:{CLR_RESET} {CLR_BOLD}{symbol:<18}{CLR_RESET} "
              f"[{CLR_YELLOW}{meta['scope']:<14}{CLR_RESET}] Deps: {meta['deps']}")

    # --- Phase 2: Graph Validation ---
    print(f"\n{CLR_MAG}[Phase 2: Graph Validation & Lint Checks]{CLR_RESET}")
    start = time.perf_counter_ns()
    processor.validate_no_cycles()
    processor.validate_scope_hierarchy()
    duration_us = (time.perf_counter_ns() - start) / 1000
    print(f"  {CLR_GREEN}✔ Graph is acyclic (DAG validated in {duration_us:.2f} µs){CLR_RESET}")
    print(f"  {CLR_GREEN}✔ Scope hierarchy valid (No Singleton -> Activity scope leaks){CLR_RESET}")

    # --- Phase 3: Code Generation ---
    print(f"\n{CLR_MAG}[Phase 3: Code Generation (KSP Factory Emulation)]{CLR_RESET}")
    app_component = SingletonComponent(processor)
    for key in processor.bindings:
        print(f"  {CLR_GRAY}Generated:{CLR_RESET} {key}_Factory.py")

    # --- Phase 4: Lifecycle Injection Workflow ---
    print(f"\n{CLR_MAG}[Phase 4: Runtime Execution & Scope Identity Verification]{CLR_RESET}")

    # Launching Activity 1
    print(f"\n{CLR_CYAN}--- Launching MainActivity (Instance #1) ---{CLR_RESET}")
    activity_comp_1 = ActivityComponent(app_component, "Activity-101")
    
    vm_1a = activity_comp_1.get("UserViewModel")
    vm_1b = activity_comp_1.get("UserViewModel")

    print(f"  Instantiated UserViewModel: {CLR_BOLD}{vm_1a.vm_id}{CLR_RESET}")
    print(f"    ├─ Scoped Router:          {CLR_BOLD}{vm_1a.router.router_id}{CLR_RESET}")
    print(f"    └─ Singleton Repo:        {CLR_BOLD}{vm_1a.repo.repo_id}{CLR_RESET}")
    print(f"         ├─ Net Client:       {CLR_BOLD}{vm_1a.repo.client.session_id}{CLR_RESET}")
    print(f"         └─ DB Driver:        {CLR_BOLD}{vm_1a.repo.db.db_id}{CLR_RESET}")

    # Assert Activity scoping
    assert vm_1a is vm_1b, "Activity-scoped ViewModel must maintain reference identity"
    assert vm_1a.router is vm_1b.router, "Activity-scoped Router must maintain reference identity"
    print(f"  {CLR_GREEN}✔ Verified: Internal Activity-Scope cached instances match identically.{CLR_RESET}")

    # Triggering configuration change (Activity Re-creation)
    print(f"\n{CLR_CYAN}--- Configuration Change: Activity Destroyed -> Instance #2 Re-created ---{CLR_RESET}")
    activity_comp_2 = ActivityComponent(app_component, "Activity-102")

    vm_2 = activity_comp_2.get("UserViewModel")
    print(f"  New UserViewModel:        {CLR_BOLD}{vm_2.vm_id}{CLR_RESET}")
    print(f"    ├─ New Scoped Router:      {CLR_BOLD}{vm_2.router.router_id}{CLR_RESET}")
    print(f"    └─ Singleton Repo:        {CLR_BOLD}{vm_2.repo.repo_id}{CLR_RESET}")

    # Assert Cross-Activity Scoping Rules
    assert vm_1a is not vm_2, "ViewModels across distinct Activities must not be identical"
    assert vm_1a.router is not vm_2.router, "Routers across distinct Activities must be unique instances"
    assert vm_1a.repo is vm_2.repo, "Singleton repositories MUST survive activity destructions"
    print(f"  {CLR_GREEN}✔ Verified: Singleton survived recreation; Activity-scoped objects recreated correctly.{CLR_RESET}")

    # --- Phase 5: Scope Leak Error Handling Test ---
    print(f"\n{CLR_MAG}[Phase 5: Negative Testing (Scope Boundary Invariants)]{CLR_RESET}")
    try:
        print(f"  Attempting invalid resolution of ActivityScoped NavigationRouter directly via SingletonComponent...")
        app_component.get("NavigationRouter")
    except RuntimeError as ex:
        print(f"  {CLR_RED}Expected Exception Intercepted:{CLR_RESET} {ex}")

    print(f"\n{CLR_GREEN}{CLR_BOLD}ALL HILT & KSP ARCHITECTURAL CHECKS PASSED SUCCESSFULLY.{CLR_RESET}\n")

if __name__ == "__main__":
    main()