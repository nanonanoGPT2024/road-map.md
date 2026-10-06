#!/usr/bin/env python3
"""
Lab Exercise: Vue Router 4 - Enterprise Client-Side Routing Engine Simulation
BAB-05: Client-Side Routing Enterprise
Architecture: Pipeline Guards, Dynamic Path Regex Matcher, Meta Access Control, History Stack
"""

import sys
import re
import time
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"
CLR_GRAY = "\033[90m"
CLR_BG_DARK = "\033[40m"


@dataclass
class RouteRecord:
    name: str
    path: str
    component_name: str
    meta: Dict[str, Any] = field(default_factory=dict)
    regex: Optional[re.Pattern] = None
    param_keys: List[str] = field(default_factory=list)
    before_enter: Optional[Callable[['RouteLocation', 'RouteLocation'], Any]] = None


@dataclass
class RouteLocation:
    path: str
    name: Optional[str] = None
    params: Dict[str, str] = field(default_factory=dict)
    query: Dict[str, str] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    matched_record: Optional[RouteRecord] = None


class UserContext:
    def __init__(self, username: str = "guest", roles: Optional[List[str]] = None, is_authenticated: bool = False):
        self.username = username
        self.roles = roles or []
        self.is_authenticated = is_authenticated


class EnterpriseVueRouter:
    """
    Simulation of Vue Router 4 Core Resolution & Navigation Lifecycle:
    1. compile_route: Transform route pattern (e.g. /users/:id) into regex with param keys
    2. resolve: Parse target URL, match against route table, extract params
    3. pipeline guards: beforeEach -> beforeEnter -> beforeResolve -> afterEach
    4. history stack: push, replace, back, forward emulation
    """

    def __init__(self):
        self.routes: List[RouteRecord] = []
        self.before_each_guards: List[Callable] = []
        self.before_resolve_guards: List[Callable] = []
        self.after_each_hooks: List[Callable] = []
        self.history: List[RouteLocation] = []
        self.history_index: int = -1
        self.current_route: Optional[RouteLocation] = None

    def add_route(self, name: str, path: str, component_name: str, meta: Optional[Dict[str, Any]] = None, before_enter: Optional[Callable] = None):
        param_keys = re.findall(r':([a-zA-Z_][a-zA-Z0-9_]*)', path)
        regex_pattern = "^" + re.sub(r':[a-zA-Z_][a-zA-Z0-9_]*', r'([^/]+)', path) + "$"
        compiled_regex = re.compile(regex_pattern)

        record = RouteRecord(
            name=name,
            path=path,
            component_name=component_name,
            meta=meta or {},
            regex=compiled_regex,
            param_keys=param_keys,
            before_enter=before_enter
        )
        self.routes.append(record)

    def before_each(self, guard: Callable):
        self.before_each_guards.append(guard)

    def before_resolve(self, guard: Callable):
        self.before_resolve_guards.append(guard)

    def after_each(self, hook: Callable):
        self.after_each_hooks.append(hook)

    def resolve(self, target_url: str) -> Optional[RouteLocation]:
        # Split path & query
        if "?" in target_url:
            path, query_str = target_url.split("?", 1)
            query_items = query_str.split("&")
            query = {k: v for k, v in [item.split("=") if "=" in item else (item, "") for item in query_items]}
        else:
            path = target_url
            query = {}

        for record in self.routes:
            if not record.regex:
                continue
            match = record.regex.match(path)
            if match:
                extracted_params = {}
                for key, val in zip(record.param_keys, match.groups()):
                    extracted_params[key] = val

                return RouteLocation(
                    path=path,
                    name=record.name,
                    params=extracted_params,
                    query=query,
                    meta=record.meta.copy(),
                    matched_record=record
                )

        # Fallback 404
        return RouteLocation(
            path=path,
            name="not-found",
            params={},
            query=query,
            meta={"title": "Page Not Found"},
            matched_record=None
        )

    def push(self, target_url: str, user_ctx: UserContext) -> bool:
        to_route = self.resolve(target_url)
        from_route = self.current_route or RouteLocation(path="", name=None)

        print(f"\n{CLR_BLUE}▶ Initiating Navigation: {CLR_BOLD}'{from_route.path or 'None'}' ➔ '{to_route.path}'{CLR_RESET}")

        # 1. Pipeline: Global beforeEach
        for guard in self.before_each_guards:
            decision = guard(to_route, from_route, user_ctx)
            if decision is False:
                print(f"  {CLR_RED}✖ [beforeEach] Navigation Aborted by Guard.{CLR_RESET}")
                return False
            elif isinstance(decision, str) and decision != to_route.path:
                print(f"  {CLR_YELLOW}↻ [beforeEach] Redirecting ➔ {decision}{CLR_RESET}")
                return self.push(decision, user_ctx)

        # 2. Pipeline: In-Route beforeEnter
        if to_route.matched_record and to_route.matched_record.before_enter:
            decision = to_route.matched_record.before_enter(to_route, from_route, user_ctx)
            if decision is False:
                print(f"  {CLR_RED}✖ [beforeEnter] Route-specific Guard Aborted Navigation.{CLR_RESET}")
                return False
            elif isinstance(decision, str) and decision != to_route.path:
                print(f"  {CLR_YELLOW}↻ [beforeEnter] Redirecting ➔ {decision}{CLR_RESET}")
                return self.push(decision, user_ctx)

        # 3. Pipeline: Global beforeResolve
        for guard in self.before_resolve_guards:
            decision = guard(to_route, from_route, user_ctx)
            if decision is False:
                print(f"  {CLR_RED}✖ [beforeResolve] Guard Aborted Navigation.{CLR_RESET}")
                return False
            elif isinstance(decision, str) and decision != to_route.path:
                print(f"  {CLR_YELLOW}↻ [beforeResolve] Redirecting ➔ {decision}{CLR_RESET}")
                return self.push(decision, user_ctx)

        # 4. Commit Navigation to History
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
        self.history.append(to_route)
        self.history_index += 1
        self.current_route = to_route

        # 5. Pipeline: Global afterEach
        for hook in self.after_each_hooks:
            hook(to_route, from_route)

        print(f"  {CLR_GREEN}✔ Navigation Confirmed: Rendered Component [{to_route.matched_record.component_name if to_route.matched_record else 'NotFoundView'}]{CLR_RESET}")
        return True


def render_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}======================================================================
     VUE ROUTER 4 - ENTERPRISE CLIENT-SIDE ROUTING LAB SIMULATION
  Core Mechanics: Guards Pipeline, Regex Matcher, RBAC Meta, State Stack
======================================================================{CLR_RESET}"""
    print(banner)


def setup_enterprise_router() -> EnterpriseVueRouter:
    router = EnterpriseVueRouter()

    # Route Table Setup
    router.add_route("home", "/", "HomeView", meta={"title": "Enterprise Portal", "requiresAuth": False})
    router.add_route("login", "/login", "LoginView", meta={"title": "Sign In", "requiresAuth": False})
    router.add_route("dashboard", "/dashboard", "DashboardView", meta={"title": "User Dashboard", "requiresAuth": True, "roles": ["user", "admin"]})
    router.add_route("user_profile", "/users/:userId", "UserProfileView", meta={"title": "Profile Details", "requiresAuth": True, "roles": ["user", "admin"]})
    router.add_route("admin_audit", "/admin/audit-logs", "AuditLogsView", meta={"title": "Security Audit", "requiresAuth": True, "roles": ["admin"]})
    router.add_route("forbidden", "/403", "ForbiddenView", meta={"title": "403 Forbidden Access", "requiresAuth": False})

    # Guard 1: Authentication & Authorization Enforcement
    def auth_guard(to: RouteLocation, from_route: RouteLocation, user: UserContext):
        requires_auth = to.meta.get("requiresAuth", False)
        required_roles = to.meta.get("roles", [])

        if requires_auth and not user.is_authenticated:
            print(f"  {CLR_GRAY}↳ [AuthGuard] Anonymous user blocked from protected route '{to.path}'{CLR_RESET}")
            return "/login"

        if requires_auth and required_roles:
            has_role = any(role in user.roles for role in required_roles)
            if not has_role:
                print(f"  {CLR_GRAY}↳ [RBACGuard] User '{user.username}' with roles {user.roles} lacking required {required_roles}{CLR_RESET}")
                return "/403"

        return True

    # Guard 2: Telemetry & Title Resolver
    def telemetry_hook(to: RouteLocation, from_route: RouteLocation):
        title = to.meta.get("title", "Vue App")
        print(f"  {CLR_MAGENTA}ℹ [afterEach] Document title updated: '{title}' | Path: {to.path}{CLR_RESET}")
        if to.params:
            print(f"  {CLR_MAGENTA}ℹ [afterEach] Extracted Route Params: {to.params}{CLR_RESET}")

    router.before_each(auth_guard)
    router.after_each(telemetry_hook)
    return router


def run_interactive_lab():
    render_banner()
    router = setup_enterprise_router()

    # Pre-configured Session Persona State
    personas = {
        "1": UserContext(username="anonymous", roles=[], is_authenticated=False),
        "2": UserContext(username="john_doe", roles=["user"], is_authenticated=True),
        "3": UserContext(username="sarah_sysadmin", roles=["user", "admin"], is_authenticated=True),
    }
    current_persona_key = "1"

    menu = f"""
{CLR_BOLD}[Interactive Control Panel]{CLR_RESET}
1. Switch Persona (Current: {CLR_YELLOW}{{username}}{CLR_RESET} | Auth: {{auth}} | Roles: {{roles}})
2. Navigate to Public Route (/)
3. Navigate to Protected Dashboard (/dashboard)
4. Navigate to Dynamic Parameter Route (/users/1042)
5. Navigate to Admin Sensitive Route (/admin/audit-logs)
6. Test Custom URL Input
7. View Routing Table & Regex Patterns
8. View Navigation History Stack
9. Run Automated Test Suite (Self-Verification)
0. Exit Lab
"""

    while True:
        p = personas[current_persona_key]
        print(menu.format(username=p.username, auth=p.is_authenticated, roles=p.roles))
        choice = input(f"{CLR_BOLD}Select an option (0-9): {CLR_RESET}").strip()

        if choice == "0":
            print(f"\n{CLR_GREEN}Exiting Vue Router Enterprise Simulation. Session closed successfully.{CLR_RESET}")
            sys.exit(0)

        elif choice == "1":
            print("\nSelect Active Persona:")
            print("1. Anonymous Guest (Unauthenticated)")
            print("2. Standard User (john_doe: ['user'])")
            print("3. System Admin (sarah_sysadmin: ['user', 'admin'])")
            sub_c = input("Choose persona (1-3): ").strip()
            if sub_c in personas:
                current_persona_key = sub_c
                new_p = personas[sub_c]
                print(f"{CLR_GREEN}Active user persona switched to '{new_p.username}'!{CLR_RESET}")
            else:
                print(f"{CLR_RED}Invalid selection.{CLR_RESET}")

        elif choice == "2":
            router.push("/", personas[current_persona_key])

        elif choice == "3":
            router.push("/dashboard", personas[current_persona_key])

        elif choice == "4":
            uid = input("Enter User ID to view (e.g. 8839): ").strip() or "8839"
            router.push(f"/users/{uid}", personas[current_persona_key])

        elif choice == "5":
            router.push("/admin/audit-logs", personas[current_persona_key])

        elif choice == "6":
            custom_url = input("Enter raw URI path to navigate (e.g. /users/99?view=compact): ").strip()
            if custom_url:
                router.push(custom_url, personas[current_persona_key])

        elif choice == "7":
            print(f"\n{CLR_CYAN}{CLR_BOLD}=== Registered Route Definitions ==={CLR_RESET}")
            for r in router.routes:
                pattern = r.regex.pattern if r.regex else "N/A"
                print(f" - {CLR_BOLD}{r.name:<14}{CLR_RESET} | Path: {r.path:<20} | Pattern: {CLR_GRAY}{pattern}{CLR_RESET} | Meta: {r.meta}")

        elif choice == "8":
            print(f"\n{CLR_CYAN}{CLR_BOLD}=== Router History Stack (State Pointer: {router.history_index}) ==={CLR_RESET}")
            if not router.history:
                print(f"{CLR_GRAY}(History stack is currently empty){CLR_RESET}")
            for idx, loc in enumerate(router.history):
                marker = f"{CLR_GREEN}➔ [ACTIVE]{CLR_RESET}" if idx == router.history_index else "  "
                print(f" {marker} Step {idx + 1}: path='{loc.path}' (name='{loc.name}', params={loc.params})")

        elif choice == "9":
            print(f"\n{CLR_CYAN}Running Automated Pipeline & Guard Verification Suite...{CLR_RESET}")
            run_verification_suite()

        time.sleep(0.4)


def run_verification_suite():
    """Automated assertions validating Vue Router 4 enterprise design compliance."""
    test_router = setup_enterprise_router()
    guest = UserContext("guest", [], False)
    admin = UserContext("admin", ["admin", "user"], True)
    user = UserContext("user", ["user"], True)

    print(f" [Test 1] Public route accessibility: ", end="")
    success = test_router.push("/", guest)
    assert success is True and test_router.current_route.name == "home"
    print(f"{CLR_GREEN}PASSED{CLR_RESET}")

    print(f" [Test 2] Guest redirect to login on protected dashboard: ", end="")
    success = test_router.push("/dashboard", guest)
    assert success is True and test_router.current_route.path == "/login"
    print(f"{CLR_GREEN}PASSED{CLR_RESET}")

    print(f" [Test 3] User access to dashboard permitted: ", end="")
    success = test_router.push("/dashboard", user)
    assert success is True and test_router.current_route.name == "dashboard"
    print(f"{CLR_GREEN}PASSED{CLR_RESET}")

    print(f" [Test 4] Regular user denied access to admin audit log (RBAC 403): ", end="")
    success = test_router.push("/admin/audit-logs", user)
    assert success is True and test_router.current_route.path == "/403"
    print(f"{CLR_GREEN}PASSED{CLR_RESET}")

    print(f" [Test 5] Dynamic route parameter extraction (/users/:userId): ", end="")
    success = test_router.push("/users/usr-7749", user)
    assert success is True and test_router.current_route.params.get("userId") == "usr-7749"
    print(f"{CLR_GREEN}PASSED{CLR_RESET}")

    print(f" [Test 6] Admin access to audit logs permitted: ", end="")
    success = test_router.push("/admin/audit-logs", admin)
    assert success is True and test_router.current_route.name == "admin_audit"
    print(f"{CLR_GREEN}PASSED{CLR_RESET}")

    print(f"\n{CLR_GREEN}{CLR_BOLD}All 6 Pipeline & Routing Invariants Verified Successfully!{CLR_RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        render_banner()
        run_verification_suite()
    else:
        run_interactive_lab()
