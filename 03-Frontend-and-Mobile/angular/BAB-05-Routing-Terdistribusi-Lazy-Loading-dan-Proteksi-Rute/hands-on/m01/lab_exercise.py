#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Engine Routing Terdistribusi, Lazy Loading & Proteksi Rute (Angular Concept)
BAB-05: Routing Terdistribusi, Lazy Loading, dan Proteksi Rute

Skrip ini memodelkan arsitektur Angular Router v17+ (Stand-alone & Feature Modules):
- Tree-shakeable functional route guards (canMatch, canActivate, canDeactivate)
- Route Resolvers (ResolveFn)
- Code-splitting & On-Demand Chunk Loading (loadChildren / loadComponent)
- Router Navigation Events Lifecycle
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional


# ANSI Color Codes
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class UserSession:
    is_authenticated: bool = False
    role: str = "guest"  # guest, user, admin
    token: Optional[str] = None
    form_is_dirty: bool = False


@dataclass
class ActivatedRouteSnapshot:
    path: str
    params: Dict[str, str] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Route:
    path: str
    component: Optional[str] = None
    load_children: Optional[Callable[[], List["Route"]]] = None
    can_match: List[Callable[[UserSession, str], bool]] = field(default_factory=list)
    can_activate: List[Callable[[UserSession, ActivatedRouteSnapshot], bool]] = field(default_factory=list)
    can_deactivate: List[Callable[[UserSession], bool]] = field(default_factory=list)
    resolve: Dict[str, Callable[[ActivatedRouteSnapshot], Any]] = field(default_factory=dict)
    children: List["Route"] = field(default_factory=list)
    title: Optional[str] = None


# --- Simulated Guards & Resolvers ---
def auth_guard(session: UserSession, snapshot: ActivatedRouteSnapshot) -> bool:
    print(f"  {Colors.CYAN}→ [Guard: canActivate]{Colors.RESET} Checking user authentication state...")
    return session.is_authenticated


def admin_role_match_guard(session: UserSession, segment: str) -> bool:
    print(f"  {Colors.CYAN}→ [Guard: canMatch]{Colors.RESET} Verifying feature access permissions for segment '{segment}'...")
    return session.is_authenticated and session.role == "admin"


def unsaved_changes_deactivate_guard(session: UserSession) -> bool:
    print(f"  {Colors.CYAN}→ [Guard: canDeactivate]{Colors.RESET} Verifying form dirty status...")
    if session.form_is_dirty:
        print(f"  {Colors.YELLOW}⚠ Ada perubahan formulir yang belum disimpan!{Colors.RESET}")
        return False
    return True


def analytics_data_resolver(snapshot: ActivatedRouteSnapshot) -> Dict[str, Any]:
    print(f"  {Colors.MAGENTA if hasattr(Colors, 'MAGENTA') else Colors.CYAN}→ [Resolver: resolve]{Colors.RESET} Prefetching analytics metadata before component activation...")
    time.sleep(0.1)
    return {"page_views": 142050, "cache_hit_rate": "98.4%", "server_latency_ms": 12}


# --- Lazy-Loaded Feature Modules Simulation ---
def load_admin_feature_routes() -> List[Route]:
    print(f"  {Colors.YELLOW}⚡ [ChunkLoader]{Colors.RESET} Fetching bundle chunk: 'chunk-admin-feature.js' on-demand...")
    time.sleep(0.15)
    return [
        Route(
            path="dashboard",
            component="AdminDashboardComponent",
            title="Admin :: Dashboard Panel"
        ),
        Route(
            path="metrics",
            component="AdminMetricsComponent",
            resolve={"analytics": analytics_data_resolver},
            title="Admin :: Performance Metrics"
        )
    ]


def load_user_feature_routes() -> List[Route]:
    print(f"  {Colors.YELLOW}⚡ [ChunkLoader]{Colors.RESET} Fetching bundle chunk: 'chunk-user-portal.js' on-demand...")
    time.sleep(0.1)
    return [
        Route(
            path="profile",
            component="UserProfileComponent",
            title="User :: Profile Settings"
        )
    ]


class AngularRouterSimulator:
    def __init__(self, routes: List[Route], session: UserSession):
        self.routes = routes
        self.session = session
        self.current_url: str = "/"
        self.active_component: Optional[str] = "RootComponent"
        self.active_route: Optional[Route] = None
        self.navigation_history: List[str] = ["/"]

    def _log_event(self, event_name: str, details: str = ""):
        print(f"{Colors.BLUE}[RouterEvent - {event_name}]{Colors.RESET} {details}")

    def navigate(self, target_url: str) -> bool:
        normalized_url = "/" + target_url.strip("/") if target_url != "/" else "/"
        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}Memulai Navigasi ke URL: {Colors.CYAN}{normalized_url}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")

        self._log_event("NavigationStart", f"Target: '{normalized_url}' | Origin: '{self.current_url}'")

        # 1. Check canDeactivate on current active route
        if self.active_route and self.active_route.can_deactivate:
            self._log_event("GuardsCheckStart", "Evaluating canDeactivate...")
            for guard in self.active_route.can_deactivate:
                can_leave = guard(self.session)
                if not can_leave:
                    self._log_event("NavigationCancel", f"Dibatalkan oleh canDeactivate pada '{self.current_url}'")
                    print(f"{Colors.RED}✖ Navigasi Dibatalkan: Guard melarang meninggalkan halaman aktif.{Colors.RESET}")
                    return False

        # 2. Route Matching & canMatch
        self._log_event("RouteConfigLoadStart", f"Pencocokan URL segment...")
        matched_route, resolved_params = self._resolve_route_tree(normalized_url)

        if not matched_route:
            self._log_event("NavigationError", f"404 Not Found or Access Denied by canMatch.")
            print(f"{Colors.RED}✖ Gagal: Rute '{normalized_url}' tidak ditemukan atau ditolak oleh canMatch guard.{Colors.RESET}")
            return False

        # 3. Check canActivate
        if matched_route.can_activate:
            self._log_event("GuardsCheckStart", "Evaluating canActivate...")
            snapshot = ActivatedRouteSnapshot(path=normalized_url, params=resolved_params)
            for guard in matched_route.can_activate:
                allowed = guard(self.session, snapshot)
                if not allowed:
                    self._log_event("NavigationCancel", "Ditolak oleh canActivate (Unauthorized/Unauthenticated)")
                    print(f"{Colors.RED}✖ Akses Ditolak: Guard canActivate memblokir rute ini.{Colors.RESET}")
                    print(f"{Colors.YELLOW}ℹ Hint: Silakan login atau perbarui level role Anda.{Colors.RESET}")
                    return False

        # 4. Resolve Data
        resolved_data: Dict[str, Any] = {}
        if matched_route.resolve:
            self._log_event("ResolveStart", "Menjalankan Data Resolvers...")
            snapshot = ActivatedRouteSnapshot(path=normalized_url, params=resolved_params)
            for key, resolver in matched_route.resolve.items():
                resolved_data[key] = resolver(snapshot)
            self._log_event("ResolveEnd", f"Data terisi: {list(resolved_data.keys())}")

        # 5. Activation & Outlet Swap
        self._log_event("ActivationStart", f"Mengaktifkan Component: {matched_route.component}")
        self.active_route = matched_route
        self.active_component = matched_route.component
        self.current_url = normalized_url
        self.navigation_history.append(normalized_url)

        self._log_event("NavigationEnd", f"Berhasil merender rute '{normalized_url}'")
        print(f"\n{Colors.GREEN}✔ Navigasi Berhasil!{Colors.RESET}")
        print(f"  {Colors.BOLD}Document Title   :{Colors.RESET} {matched_route.title or 'Angular App'}")
        print(f"  {Colors.BOLD}Mounted Component:{Colors.RESET} <{matched_route.component} />")
        if resolved_data:
            print(f"  {Colors.BOLD}Resolved RouteData:{Colors.RESET} {resolved_data}")
        return True

    def _resolve_route_tree(self, url: str) -> tuple[Optional[Route], Dict[str, str]]:
        segments = [s for s in url.strip("/").split("/") if s]
        if not segments:
            for r in self.routes:
                if r.path == "":
                    return r, {}
            return None, {}

        return self._match_recursive(self.routes, segments, {})

    def _match_recursive(self, current_routes: List[Route], segments: List[str], params: Dict[str, str]) -> tuple[Optional[Route], Dict[str, str]]:
        if not segments:
            return None, params

        target_seg = segments[0]
        remaining = segments[1:]

        for r in current_routes:
            if r.path == target_seg:
                # Check canMatch
                can_match_passed = True
                for cm in r.can_match:
                    if not cm(self.session, target_seg):
                        can_match_passed = False
                        break
                if not can_match_passed:
                    continue

                # Handle lazy loading (load_children)
                child_routes = r.children
                if r.load_children:
                    loaded = r.load_children()
                    child_routes = loaded

                if remaining:
                    res, resolved_p = self._match_recursive(child_routes, remaining, params)
                    if res:
                        return res, resolved_p
                else:
                    if r.component:
                        return r, params
                    # Check empty path child
                    for cr in child_routes:
                        if cr.path == "":
                            return cr, params
        return None, params


def build_app_routes() -> List[Route]:
    return [
        Route(
            path="",
            component="HomeComponent",
            title="Angular App :: Home"
        ),
        Route(
            path="dashboard",
            component="PublicDashboardComponent",
            title="Dashboard Publik"
        ),
        Route(
            path="admin",
            can_match=[admin_role_match_guard],
            can_activate=[auth_guard],
            load_children=load_admin_feature_routes
        ),
        Route(
            path="user",
            can_activate=[auth_guard],
            load_children=load_user_feature_routes
        ),
        Route(
            path="editor",
            component="DraftEditorComponent",
            can_deactivate=[unsaved_changes_deactivate_guard],
            title="Content Editor"
        )
    ]


def run_automated_suite(router: AngularRouterSimulator):
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== MENJALANKAN AUTOMATED SUITE TEST KASUS ROUTING ==={Colors.RESET}")
    tests = [
        ("Navigasi Public Home ('/')", "/", True),
        ("Navigasi Public Dashboard ('/dashboard')", "/dashboard", True),
        ("Navigasi Admin Dashboard ('/admin/dashboard') tanpa Login", "/admin/dashboard", False),
        ("Navigasi Editor Form ('/editor')", "/editor", True),
    ]

    passed = 0
    for name, path, expected in tests:
        print(f"\n{Colors.BOLD}Test:{Colors.RESET} {name}")
        res = router.navigate(path)
        if res == expected:
            print(f"{Colors.GREEN}→ PASSED{Colors.RESET}")
            passed += 1
        else:
            print(f"{Colors.RED}→ FAILED (Expected: {expected}, Got: {res}){Colors.RESET}")

    print(f"\n{Colors.BOLD}Hasil Otomasi:{Colors.RESET} {passed}/{len(tests)} test passed.\n")


def print_status(session: UserSession, router: AngularRouterSimulator):
    auth_badge = f"{Colors.GREEN}Logged In{Colors.RESET}" if session.is_authenticated else f"{Colors.RED}Guest{Colors.RESET}"
    dirty_badge = f"{Colors.RED}Dirty (Unsaved){Colors.RESET}" if session.form_is_dirty else f"{Colors.GREEN}Clean{Colors.RESET}"
    print(f"\n{Colors.DIM}{'─'*60}{Colors.RESET}")
    print(f" {Colors.BOLD}Status Sesi:{Colors.RESET} Auth=[{auth_badge}] | Role=[{Colors.YELLOW}{session.role}{Colors.RESET}] | Form=[{dirty_badge}]")
    print(f" {Colors.BOLD}Rute Aktif :{Colors.RESET} {Colors.CYAN}{router.current_url}{Colors.RESET} -> <{router.active_component} />")
    print(f"{Colors.DIM}{'─'*60}{Colors.RESET}")


def main():
    session = UserSession()
    routes = build_app_routes()
    router = AngularRouterSimulator(routes, session)

    # Initial activation
    router.navigate("/")

    while True:
        print_status(session, router)
        print(f"{Colors.BOLD}PILIHAN AKSI SIMULATOR ROUTER ANGULAR:{Colors.RESET}")
        print("  1. Navigasi ke '/' (Home)")
        print("  2. Navigasi ke '/dashboard' (Public)")
        print("  3. Navigasi ke '/admin/dashboard' (Lazy Loaded + Proteksi canMatch & canActivate)")
        print("  4. Navigasi ke '/admin/metrics' (Lazy Loaded + Resolver analytics data)")
        print("  5. Navigasi ke '/editor' (Komponen dengan canDeactivate guard)")
        print("  6. Toggle Login/Logout")
        print("  7. Ganti Role Pengguna (guest / user / admin)")
        print("  8. Toggle Status Form Dirty (Simulasi unsaved state)")
        print("  9. Jalankan Automated Verification Test Suite")
        print("  0. Keluar")

        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan (0-9): {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.YELLOW}Keluar dari simulator.{Colors.RESET}")
            break

        if choice == "1":
            router.navigate("/")
        elif choice == "2":
            router.navigate("/dashboard")
        elif choice == "3":
            router.navigate("/admin/dashboard")
        elif choice == "4":
            router.navigate("/admin/metrics")
        elif choice == "5":
            router.navigate("/editor")
        elif choice == "6":
            session.is_authenticated = not session.is_authenticated
            if session.is_authenticated:
                session.role = "user" if session.role == "guest" else session.role
            else:
                session.role = "guest"
            print(f"{Colors.CYAN}Status login diubah ke: {session.is_authenticated}{Colors.RESET}")
        elif choice == "7":
            print("Pilih Role: 1. guest | 2. user | 3. admin")
            r_choice = input("Pilihan: ").strip()
            if r_choice == "1":
                session.role = "guest"
                session.is_authenticated = False
            elif r_choice == "2":
                session.role = "user"
                session.is_authenticated = True
            elif r_choice == "3":
                session.role = "admin"
                session.is_authenticated = True
            print(f"{Colors.CYAN}Role diubah ke: {session.role}{Colors.RESET}")
        elif choice == "8":
            session.form_is_dirty = not session.form_is_dirty
            print(f"{Colors.CYAN}Form Dirty state diubah ke: {session.form_is_dirty}{Colors.RESET}")
        elif choice == "9":
            run_automated_suite(router)
        elif choice == "0":
            print(f"{Colors.GREEN}Terima kasih! Simulator routing selesai.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid, silakan coba lagi.{Colors.RESET}")


if __name__ == "__main__":
    main()
