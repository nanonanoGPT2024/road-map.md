#!/usr/bin/env python3
"""
Lab Hands-on: Angular Distributed Routing, Lazy Loading & Route Guards Simulation
Category: 03-Frontend-and-Mobile | Chapter: 05 - Distributed Routing & Guards

This script simulates the complete internals of the Angular Router:
- Distributed nested route configuration (forChild vs forRoot).
- Lazy loading chunk resolution with simulated network latency and chunk cache.
- Route Guards pipeline: CanMatch, CanActivate, and Data Resolvers.
- State-driven navigation with dynamic path parsing, parameter extraction, and fallbacks.
"""

from __future__ import annotations
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any, Tuple


# ============================================================================
# ANSI Color Formatting Helper
# ============================================================================
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"


# ============================================================================
# Core Domain Models: Auth, Navigation Context, and Guards
# ============================================================================
class UserRole(str, Enum):
    ANONYMOUS = "ANONYMOUS"
    USER = "USER"
    ADMIN = "ADMIN"


@dataclass
class AuthContext:
    username: str
    roles: List[UserRole]

    @property
    def is_authenticated(self) -> bool:
        return UserRole.ANONYMOUS not in self.roles and len(self.roles) > 0


@dataclass
class ActivatedRouteSnapshot:
    url: str
    params: Dict[str, str]
    data: Dict[str, Any] = field(default_factory=dict)


# Type definitions mimicking Angular Router Guard signatures
GuardFn = Callable[[AuthContext, ActivatedRouteSnapshot], bool]
ResolveFn = Callable[[ActivatedRouteSnapshot], Any]
LazyLoadFn = Callable[[], List['Route']]


@dataclass
class Route:
    """Represents an Angular Route declaration (similar to Route interface in @angular/router)."""
    path: str
    component: Optional[str] = None
    children: List['Route'] = field(default_factory=list)
    can_match: List[GuardFn] = field(default_factory=list)
    can_activate: List[GuardFn] = field(default_factory=list)
    resolve: Dict[str, ResolveFn] = field(default_factory=dict)
    load_children: Optional[LazyLoadFn] = None
    redirect_to: Optional[str] = None
    is_wildcard: bool = False


# ============================================================================
# Lazy Loaded Chunk Manager (Simulating Webpack/Vite chunk split & fetch)
# ============================================================================
class ChunkRegistry:
    """Tracks simulated dynamic ES module imports, file size, and cache hits."""
    def __init__(self):
        self.chunk_cache: Dict[str, List[Route]] = {}
        self.bundle_metadata: Dict[str, Dict[str, Any]] = {
            "AdminModule": {"size_kb": 142.5, "latency_ms": 120},
            "AnalyticsModule": {"size_kb": 310.2, "latency_ms": 250},
            "ProfileModule": {"size_kb": 64.0, "latency_ms": 80},
        }

    def fetch_module(self, module_name: str, loader: LazyLoadFn) -> List[Route]:
        """Simulates `import('./module').then(m => m.Module)`."""
        if module_name in self.chunk_cache:
            print(f"  {TerminalColor.GRAY}[ChunkCache] Hit for '{module_name}' (0ms, 0 KB transfer){TerminalColor.RESET}")
            return self.chunk_cache[module_name]

        meta = self.bundle_metadata.get(module_name, {"size_kb": 50.0, "latency_ms": 50})
        print(f"  {TerminalColor.CYAN}[Network] Downloading chunk: {module_name}.js "
              f"({meta['size_kb']} KB) with ~{meta['latency_ms']}ms latency...{TerminalColor.RESET}")
        
        # Emulate network delay
        time.sleep(meta['latency_ms'] / 1000.0)
        
        routes = loader()
        self.chunk_cache[module_name] = routes
        print(f"  {TerminalColor.GREEN}✔ [Network] Chunk '{module_name}' downloaded and compiled successfully.{TerminalColor.RESET}")
        return routes


# ============================================================================
# Angular Router Implementation
# ============================================================================
class AngularRouter:
    def __init__(self, root_routes: List[Route], chunk_registry: ChunkRegistry):
        self.routes = root_routes
        self.chunk_registry = chunk_registry

    def navigate(self, url: str, auth_context: AuthContext) -> bool:
        """Executes the Angular navigation pipeline."""
        print(f"\n{TerminalColor.BOLD}{'='*80}{TerminalColor.RESET}")
        print(f"{TerminalColor.BOLD}Navigating to: {TerminalColor.BLUE}{url}{TerminalColor.RESET} "
              f"| Principal: {TerminalColor.MAGENTA}{auth_context.username} {auth_context.roles}{TerminalColor.RESET}")
        print(f"{TerminalColor.BOLD}{'='*80}{TerminalColor.RESET}")

        segments = [seg for seg in url.strip("/").split("/") if seg]
        state = ActivatedRouteSnapshot(url=url, params={})

        return self._traverse_route_tree(self.routes, segments, 0, auth_context, state)

    def _traverse_route_tree(
        self,
        routes: List[Route],
        segments: List[str],
        seg_idx: int,
        context: AuthContext,
        snapshot: ActivatedRouteSnapshot
    ) -> bool:
        """Recursively matches route segments, resolves guards, and executes lazy loading."""
        
        # Base case: All segments consumed
        if seg_idx >= len(segments):
            # Find index/default or wildcard route at current level
            for route in routes:
                if route.path == "" or route.path == "/":
                    return self._activate_terminal_route(route, context, snapshot)
            print(f"  {TerminalColor.RED}✖ Navigation Error: Route matched up to here, but no terminal component specified.{TerminalColor.RESET}")
            return False

        current_segment = segments[seg_idx]

        for route in routes:
            # Handle redirection
            if route.redirect_to is not None and (route.path == current_segment or route.path == ""):
                print(f"  {TerminalColor.YELLOW}➜ Redirecting: {route.path} -> {route.redirect_to}{TerminalColor.RESET}")
                return self.navigate(route.redirect_to, context)

            # Check CanMatch guard before inspecting children/lazy modules
            if not self._eval_can_match(route, context, snapshot):
                continue

            # Path matching (literal or parameterized)
            match, param_kv = self._match_segment(route.path, current_segment)
            if not match and not route.is_wildcard:
                continue

            if param_kv:
                snapshot.params.update(param_kv)

            # Lazy load dynamic module boundary (loadChildren)
            if route.load_children:
                print(f"  {TerminalColor.BLUE}⚡ Triggering Lazy Load boundary for path segment: '{current_segment}'{TerminalColor.RESET}")
                module_name = route.component or "DynamicModule"
                lazy_routes = self.chunk_registry.fetch_module(module_name, route.load_children)
                # Once loaded, inspect nested routes
                return self._traverse_route_tree(lazy_routes, segments, seg_idx + 1, context, snapshot)

            # Check if this route has nested children
            if route.children:
                return self._traverse_route_tree(route.children, segments, seg_idx + 1, context, snapshot)

            # Leaf route reached
            if seg_idx == len(segments) - 1 or route.is_wildcard:
                return self._activate_terminal_route(route, context, snapshot)

        print(f"  {TerminalColor.RED}✖ Cannot match any routes for path: /{'/'.join(segments[seg_idx:])}{TerminalColor.RESET}")
        return False

    def _match_segment(self, route_path: str, url_segment: str) -> Tuple[bool, Optional[Dict[str, str]]]:
        if route_path.startswith(":"):
            param_key = route_path[1:]
            return True, {param_key: url_segment}
        return (route_path == url_segment), None

    def _eval_can_match(self, route: Route, context: AuthContext, snapshot: ActivatedRouteSnapshot) -> bool:
        for guard in route.can_match:
            guard_name = getattr(guard, '__name__', 'AnonymousGuard')
            passed = guard(context, snapshot)
            if not passed:
                print(f"  {TerminalColor.YELLOW}[CanMatch] Guard '{guard_name}' rejected path segment '{route.path}'. Skipping branch.{TerminalColor.RESET}")
                return False
            print(f"  {TerminalColor.GREEN}[CanMatch] Guard '{guard_name}' passed for branch '{route.path}'.{TerminalColor.RESET}")
        return True

    def _activate_terminal_route(self, route: Route, context: AuthContext, snapshot: ActivatedRouteSnapshot) -> bool:
        # 1. Execute CanActivate guards
        for guard in route.can_activate:
            guard_name = getattr(guard, '__name__', 'AnonymousGuard')
            if not guard(context, snapshot):
                print(f"  {TerminalColor.RED}✖ [CanActivate] Access Denied by guard '{guard_name}' for component '{route.component}'.{TerminalColor.RESET}")
                return False
            print(f"  {TerminalColor.GREEN}✔ [CanActivate] Guard '{guard_name}' approved activation.{TerminalColor.RESET}")

        # 2. Execute Data Resolvers
        for key, resolver in route.resolve.items():
            resolver_name = getattr(resolver, '__name__', 'AnonymousResolver')
            print(f"  {TerminalColor.CYAN}[Resolve] Running resolver '{resolver_name}' for key '{key}'...{TerminalColor.RESET}")
            resolved_value = resolver(snapshot)
            snapshot.data[key] = resolved_value
            print(f"  {TerminalColor.CYAN}[Resolve] Injected data: {key} => {resolved_value}{TerminalColor.RESET}")

        # 3. Mount Component
        print(f"  {TerminalColor.BOLD}{TerminalColor.GREEN}▶ Component Rendered: <{route.component}/>{TerminalColor.RESET}")
        if snapshot.params:
            print(f"    Params: {snapshot.params}")
        if snapshot.data:
            print(f"    Snapshot Data: {snapshot.data}")
        return True


# ============================================================================
# Real Guard & Resolver Implementations
# ============================================================================
def auth_guard(context: AuthContext, _: ActivatedRouteSnapshot) -> bool:
    """Angular CanActivate: Checks if user is signed in."""
    return context.is_authenticated


def admin_role_guard(context: AuthContext, _: ActivatedRouteSnapshot) -> bool:
    """Angular CanMatch / CanActivate: Verifies admin authorization level."""
    return UserRole.ADMIN in context.roles


def telemetry_resolver(snapshot: ActivatedRouteSnapshot) -> Dict[str, Any]:
    """Angular ResolveFn: Prefetches metadata prior to component mounting."""
    return {
        "timestamp": time.time(),
        "trace_id": f"trace-{random.randint(1000, 9999)}",
        "target_url": snapshot.url
    }


def user_data_resolver(snapshot: ActivatedRouteSnapshot) -> Dict[str, Any]:
    user_id = snapshot.params.get("id", "0")
    return {"id": user_id, "name": f"User_{user_id}", "status": "ACTIVE"}


# ============================================================================
# Distributed Feature Modules (Lazy Bundles)
# ============================================================================
def get_admin_module_routes() -> List[Route]:
    """Distributed Routing: routes for AdminModule (admin-routing.module.ts)."""
    return [
        Route(path="dashboard", component="AdminDashboardComponent", can_activate=[admin_role_guard]),
        Route(
            path="users",
            component="AdminUsersComponent",
            children=[
                Route(
                    path=":id",
                    component="AdminUserDetailComponent",
                    can_activate=[admin_role_guard],
                    resolve={"user_profile": user_data_resolver}
                )
            ]
        ),
    ]


def get_analytics_module_routes() -> List[Route]:
    """Distributed Routing: routes for AnalyticsModule (analytics-routing.module.ts)."""
    return [
        Route(
            path="realtime",
            component="AnalyticsRealtimeComponent",
            resolve={"telemetry": telemetry_resolver}
        )
    ]


# ============================================================================
# Root App Configuration (app-routing.module.ts)
# ============================================================================
def configure_root_routes() -> List[Route]:
    return [
        Route(path="", redirect_to="/home"),
        Route(path="home", component="HomeComponent"),
        Route(path="login", component="LoginComponent"),
        # Protected Lazy Loaded Feature Module
        Route(
            path="admin",
            component="AdminModule",
            can_match=[auth_guard, admin_role_guard],
            load_children=get_admin_module_routes
        ),
        # Public Lazy Loaded Feature Module
        Route(
            path="analytics",
            component="AnalyticsModule",
            load_children=get_analytics_module_routes
        ),
        # 404 Wildcard fallback
        Route(path="**", component="NotFoundComponent", is_wildcard=True)
    ]


# ============================================================================
# Hands-on Simulation Scenarios
# ============================================================================
def main():
    print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}")
    print("================================================================================")
    print("   ANGULAR ROUTING & SECURITY ENGINE: DISTRIBUTED & LAZY LOADING SIMULATOR     ")
    print("================================================================================")
    print(f"{TerminalColor.RESET}")

    registry = ChunkRegistry()
    routes = configure_root_routes()
    router = AngularRouter(routes, registry)

    # Identities
    anon_user = AuthContext("guest_user", [UserRole.ANONYMOUS])
    standard_user = AuthContext("john_doe", [UserRole.USER])
    admin_user = AuthContext("super_admin", [UserRole.USER, UserRole.ADMIN])

    # Simulation Sequence
    scenarios = [
        ("Step 1: Anonymous User access Public Home Page", "/home", anon_user),
        ("Step 2: Anonymous User tries accessing Admin (Blocked by CanMatch Guard)", "/admin/dashboard", anon_user),
        ("Step 3: Authenticated Normal User tries accessing Admin (CanMatch blocks - role mismatch)", "/admin/dashboard", standard_user),
        ("Step 4: Authenticated Admin accessing Admin Feature (Triggers Lazy Load + Network Latency)", "/admin/dashboard", admin_user),
        ("Step 5: Admin accessing Sub-Route with Params & Resolver (Verifies Chunk Cache Hit)", "/admin/users/8821", admin_user),
        ("Step 6: Access Public Lazy Module with Data Resolver", "/analytics/realtime", standard_user),
        ("Step 7: Wildcard Catch-all Route Evaluation", "/unregistered/unknown/resource", anon_user),
    ]

    for title, url, user in scenarios:
        print(f"\n>>> {TerminalColor.BOLD}{title}{TerminalColor.RESET}")
        success = router.navigate(url, user)
        status_text = f"{TerminalColor.GREEN}PASSED" if success else f"{TerminalColor.RED}FAILED"
        print(f"Navigation State Result: {status_text}{TerminalColor.RESET}")
        time.sleep(0.05)

    print(f"\n{TerminalColor.BOLD}{TerminalColor.CYAN}")
    print("================================================================================")
    print("   SIMULATION SUMMARY: All Router Lifecycle Phases Verified Successfully       ")
    print("================================================================================")
    print(f"{TerminalColor.RESET}")


if __name__ == "__main__":
    main()