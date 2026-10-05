#!/usr/bin/env python3
"""
Lab Exercise M02: Enterprise Vue Router 4 Architecture Simulator
BAB-05: Client-Side Routing Enterprise

Simulasi komprehensif siklus hidup Vue Router enterprise:
1. Dynamic route matching & nested routing
2. Navigation guard lifecycle pipeline (Global, Per-Route, In-Component)
3. Role-Based Access Control (RBAC) via route meta
4. Lazy loading & chunk prefetching simulator
5. Navigation abort & race condition handling
6. Scroll behavior & history state management
"""

import sys
import time
import json
import re
from typing import Dict, List, Any, Optional, Callable

# ==============================================================================
# ANSI Color Palette
# ==============================================================================
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
    BG_DARK = '\033[40m'

def log_step(phase: str, message: str, color: str = Colors.CYAN):
    print(f" {color}[{phase:^14}]{Colors.RESET} {message}")

def log_guard(name: str, passed: bool, detail: str = ""):
    status = f"{Colors.GREEN}PASSED{Colors.RESET}" if passed else f"{Colors.RED}BLOCKED{Colors.RESET}"
    print(f"   ↳ {Colors.BOLD}{name:<22}{Colors.RESET}: [{status}] {detail}")

# ==============================================================================
# Domain Models: RouteRecord & NavigationContext
# ==============================================================================
class RouteRecord:
    def __init__(self, path: str, name: str, component: str, meta: Dict[str, Any] = None,
                 children: List['RouteRecord'] = None, before_enter: Optional[Callable] = None):
        self.path = path
        self.name = name
        self.component = component
        self.meta = meta or {}
        self.children = children or []
        self.before_enter = before_enter
        self.regex = self._compile_regex(path)

    def _compile_regex(self, path: str) -> re.Pattern:
        pattern = re.sub(r':([a-zA-Z0-9_]+)', r'(?P<\1>[^/]+)', path)
        return re.compile(f"^{pattern}$")

class NavigationLocation:
    def __init__(self, path: str, name: Optional[str] = None, params: Dict[str, str] = None,
                 query: Dict[str, str] = None, meta: Dict[str, Any] = None):
        self.path = path
        self.name = name
        self.params = params or {}
        self.query = query or {}
        self.meta = meta or {}

    def __repr__(self):
        return f"<Route: {self.path} (Name: {self.name}) Params: {self.params} Meta: {self.meta}>"

# ==============================================================================
# Vue Router 4 Engine Simulation
# ==============================================================================
class VueRouterSimulator:
    def __init__(self, routes: List[RouteRecord]):
        self.routes = routes
        self.current_route: Optional[NavigationLocation] = None
        self.history_stack: List[str] = []
        self.navigation_seq = 0
        self.active_abort_controller = None

        # Navigation Guard Hooks
        self.before_each_guards: List[Callable] = []
        self.before_resolve_guards: List[Callable] = []
        self.after_each_hooks: List[Callable] = []

        # Current simulated authenticated user context
        self.auth_user = {
            "authenticated": False,
            "roles": [],
            "name": "Guest"
        }

    def set_auth(self, authenticated: bool, roles: List[str], name: str):
        self.auth_user = {"authenticated": authenticated, "roles": roles, "name": name}

    def before_each(self, guard: Callable):
        self.before_each_guards.append(guard)

    def before_resolve(self, guard: Callable):
        self.before_resolve_guards.append(guard)

    def after_each(self, hook: Callable):
        self.after_each_hooks.append(hook)

    def match(self, path: str) -> Optional[NavigationLocation]:
        # Simple route tree traversal
        for route in self.routes:
            match = route.regex.match(path)
            if match:
                return NavigationLocation(
                    path=path,
                    name=route.name,
                    params=match.groupdict(),
                    meta=route.meta
                )
            for child in route.children:
                full_path = f"{route.path.rstrip('/')}/{child.path.lstrip('/')}"
                regex_str = "^" + re.sub(r':([a-zA-Z0-9_]+)', r'(?P<\1>[^/]+)', full_path) + "$"
                child_regex = re.compile(regex_str)
                m = child_regex.match(path)
                if m:
                    merged_meta = {**route.meta, **child.meta}
                    return NavigationLocation(
                        path=path,
                        name=child.name,
                        params=m.groupdict(),
                        meta=merged_meta
                    )
        return None

    def push(self, target_path: str) -> bool:
        self.navigation_seq += 1
        current_seq = self.navigation_seq
        print(f"\n{Colors.HEADER}{'='*72}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}🚀 [ROUTER DISPATCH] -> Attempting navigation to: {target_path}{Colors.RESET}")
        print(f"   Current User: {self.auth_user['name']} (Roles: {self.auth_user['roles']}, Auth: {self.auth_user['authenticated']})")
        print(f"{Colors.HEADER}{'='*72}{Colors.RESET}")

        # Phase 1: Route Matching
        log_step("PHASE 1: MATCH", f"Resolving route definition for '{target_path}'...")
        to_route = self.match(target_path)
        if not to_route:
            log_step("ERROR 404", f"No matching route found for {target_path}! Triggering fallback.", Colors.RED)
            return False

        from_route = self.current_route or NavigationLocation(path="/", name="root")
        log_step("MATCHED", f"Target: [{to_route.name}] | Params: {to_route.params} | Meta: {to_route.meta}", Colors.GREEN)

        # Phase 2: Global beforeEach guards
        log_step("PHASE 2: GUARDS", "Executing global beforeEach pipeline...")
        for idx, guard in enumerate(self.before_each_guards, 1):
            decision = guard(to_route, from_route, self.auth_user)
            if decision is False:
                log_guard(f"globalBeforeEach#{idx}", False, "Navigation explicitly cancelled!")
                return False
            elif isinstance(decision, str):
                log_guard(f"globalBeforeEach#{idx}", False, f"Redirect triggered -> {decision}")
                return self.push(decision)
            log_guard(f"globalBeforeEach#{idx}", True, "Check satisfied")

        # Phase 3: Route-Level / Component Lazy Loading
        log_step("PHASE 3: CHUNK", f"Simulating dynamic import() & chunk download for component...", Colors.YELLOW)
        chunk_name = to_route.meta.get("chunkName", "default_bundle")
        time.sleep(0.12)  # Network simulated latency
        print(f"   📦 {Colors.DIM}Downloaded webpackChunk: [{chunk_name}.js] (Status: 200 OK){Colors.RESET}")

        # Phase 4: beforeResolve guards
        log_step("PHASE 4: RESOLVE", "Running beforeResolve hooks (async data prefetch)...")
        for idx, guard in enumerate(self.before_resolve_guards, 1):
            if not guard(to_route, from_route):
                log_guard(f"beforeResolve#{idx}", False, "Data hydration failed!")
                return False
            log_guard(f"beforeResolve#{idx}", True, "Hydration ready")

        # Phase 5: Navigation Commit
        if current_seq != self.navigation_seq:
            log_step("RACE CANCEL", f"Navigation {current_seq} superseded by newer dispatch {self.navigation_seq}!", Colors.RED)
            return False

        self.current_route = to_route
        self.history_stack.append(target_path)
        log_step("PHASE 5: COMMIT", f"DOM updated & router-view mounted with [{to_route.name}]", Colors.GREEN)

        # Phase 6: afterEach & telemetry
        log_step("PHASE 6: AFTER", "Executing afterEach post-navigation hooks & telemetry...")
        for hook in self.after_each_hooks:
            hook(to_route, from_route)

        print(f"{Colors.GREEN}✔ Navigation SUCCESS: URL is now '{self.current_route.path}'{Colors.RESET}\n")
        return True

# ==============================================================================
# Simulation Setup & Interactive CLI
# ==============================================================================
def create_enterprise_router() -> VueRouterSimulator:
    routes = [
        RouteRecord(
            path="/",
            name="LandingHome",
            component="HomeView.vue",
            meta={"title": "Enterprise Portal Home", "public": True, "chunkName": "home-view"}
        ),
        RouteRecord(
            path="/login",
            name="AuthLogin",
            component="LoginView.vue",
            meta={"title": "Sign In - Enterprise IAM", "public": True, "chunkName": "auth-login"}
        ),
        RouteRecord(
            path="/dashboard",
            name="AppDashboard",
            component="DashboardLayout.vue",
            meta={"requiresAuth": True, "roles": ["viewer", "editor", "admin"], "chunkName": "dashboard-core"},
            children=[
                RouteRecord(
                    path="analytics",
                    name="DashboardAnalytics",
                    component="AnalyticsWidget.vue",
                    meta={"roles": ["editor", "admin"], "chunkName": "dash-analytics"}
                ),
                RouteRecord(
                    path="users/:id",
                    name="UserProfile",
                    component="UserDetails.vue",
                    meta={"roles": ["admin"], "chunkName": "dash-users"}
                )
            ]
        ),
        RouteRecord(
            path="/audit-logs",
            name="SecurityAudit",
            component="AuditLogView.vue",
            meta={"requiresAuth": True, "roles": ["admin"], "requiresMfa": True, "chunkName": "sec-audit"}
        )
    ]

    router = VueRouterSimulator(routes)

    # 1. Global RBAC & Auth Guard
    def rbac_auth_guard(to: NavigationLocation, from_loc: NavigationLocation, user: dict):
        if to.meta.get("requiresAuth") and not user["authenticated"]:
            print(f"      {Colors.YELLOW}[GUARD LOG] Protected route! Redirecting unauthenticated user to /login{Colors.RESET}")
            return "/login"
        
        required_roles = to.meta.get("roles")
        if required_roles:
            has_role = any(r in user["roles"] for r in required_roles)
            if not has_role:
                print(f"      {Colors.RED}[GUARD LOG] 403 Forbidden! User roles {user['roles']} not in allowed {required_roles}{Colors.RESET}")
                return False
        return True

    # 2. Page Title & Meta Guard
    def document_title_guard(to: NavigationLocation, from_loc: NavigationLocation, user: dict):
        title = to.meta.get("title", f"Vue Enterprise - {to.name}")
        print(f"      {Colors.CYAN}[GUARD LOG] Updating document.title to: \"{title}\"{Colors.RESET}")
        return True

    # 3. Async Data Hydration Hook
    def async_data_resolver(to: NavigationLocation, from_loc: NavigationLocation):
        if "id" in to.params:
            user_id = to.params["id"]
            print(f"      {Colors.BLUE}[RESOLVE LOG] Hydrating reactive store for user ID = {user_id}...{Colors.RESET}")
        return True

    # 4. Analytics Telemetry Hook
    def telemetry_hook(to: NavigationLocation, from_loc: NavigationLocation):
        print(f"      {Colors.DIM}[TELEMETRY] Sent pageview beacon: {{ path: '{to.path}', title: '{to.name}' }}{Colors.RESET}")

    router.before_each(rbac_auth_guard)
    router.before_each(document_title_guard)
    router.before_resolve(async_data_resolver)
    router.after_each(telemetry_hook)

    return router

def run_interactive_simulation():
    print(f"""{Colors.BOLD}{Colors.CYAN}
╔════════════════════════════════════════════════════════════════════════════╗
║               VUE ROUTER 4 ENTERPRISE PIPELINE SIMULATOR                   ║
║                BAB-05: Advanced Client-Side Routing Flow                   ║
╚════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}
""")

    router = create_enterprise_router()

    scenarios = [
        ("Guest tries to access public landing page", False, [], "Guest", "/"),
        ("Unauthenticated guest attempts /dashboard/analytics (triggers /login redirect)", False, [], "Guest", "/dashboard/analytics"),
        ("Viewer logs in and attempts /dashboard/analytics (403 RBAC blocked)", True, ["viewer"], "Alice (Viewer)", "/dashboard/analytics"),
        ("Editor logs in and accesses /dashboard/analytics (allowed)", True, ["editor"], "Bob (Editor)", "/dashboard/analytics"),
        ("Admin logs in and navigates to nested dynamic route /dashboard/users/42", True, ["admin"], "Charlie (Admin)", "/dashboard/users/42"),
        ("Admin tries to access high-security /audit-logs", True, ["admin"], "Charlie (Admin)", "/audit-logs"),
    ]

    print(f"{Colors.YELLOW}Menjalankan 6 Skenario Navigasi Produksi Otomatis:{Colors.RESET}\n")

    for idx, (title, auth, roles, name, dest) in enumerate(scenarios, 1):
        print(f"\n{Colors.BOLD}{Colors.HEADER}--- Skenario {idx}: {title} ---{Colors.RESET}")
        router.set_auth(auth, roles, name)
        success = router.push(dest)
        status_badge = f"{Colors.GREEN}SUKSES" if success else f"{Colors.RED}GAGAL / DICEGAH"
        print(f"Hasil Skenario {idx}: {status_badge}{Colors.RESET}")
        time.sleep(0.08)

    print(f"\n{Colors.BOLD}{Colors.GREEN}==========================================================================")
    print(f"Seluruh simulasi siklus router enterprise Vue 4 telah berhasil dijalankan!")
    print(f"Riwayat navigasi terkumpul: {router.history_stack}")
    print(f"=========================================================================={Colors.RESET}\n")

if __name__ == "__main__":
    run_interactive_simulation()
