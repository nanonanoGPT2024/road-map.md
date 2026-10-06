#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Routing Architecture, Code-Splitting, & Code Organization
Mata Kuliah / Modul: React Advanced Architecture (BAB-07)
Mendemonstrasikan secara teknis di terminal:
 1. Client-Side Routing Tree & Nested Layouts (Outlet pattern)
 2. Dynamic Param Matching (:id, wildcard)
 3. Protected Route Middleware / Navigation Guards
 4. Code Splitting, Dynamic import() simulation, Chunk Caching
 5. React.lazy & Suspense boundary state machine
"""

import sys
import time
import re
from typing import Dict, List, Any, Optional, Callable

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"

def print_header(title: str):
    width = 68
    print(f"\n{CLR_CYAN}{'=' * width}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  {title}{CLR_RESET}")
    print(f"{CLR_CYAN}{'=' * width}{CLR_RESET}\n")

def print_badge(label: str, text: str, color: str = CLR_GREEN):
    print(f"{color}[{label}]{CLR_RESET} {text}")

# --- 1. CODE SPLITTING & LAZY BUNDLE SIMULATION ---

class ChunkRegistry:
    """Simulasi Webpack/Vite Chunk Loader & Cache Registry"""
    def __init__(self):
        self.downloaded_chunks: Dict[str, float] = {}
        self.chunk_definitions = {
            "chunk-home": {"name": "HomeFeatureModule", "size_kb": 14.2, "latency": 0.25},
            "chunk-dashboard": {"name": "DashboardLayoutModule", "size_kb": 38.6, "latency": 0.40},
            "chunk-analytics": {"name": "AnalyticsWidgetsModule", "size_kb": 92.4, "latency": 0.65},
            "chunk-profile": {"name": "UserProfileModule", "size_kb": 22.1, "latency": 0.30},
            "chunk-admin": {"name": "AdminPortalModule", "size_kb": 115.0, "latency": 0.80},
        }

    def load_chunk(self, chunk_id: str) -> bool:
        if chunk_id in self.downloaded_chunks:
            print_badge("CACHE_HIT", f"Chunk '{chunk_id}' diambil instan dari Memory Cache!", CLR_MAGENTA)
            return True

        meta = self.chunk_definitions.get(chunk_id)
        if not meta:
            print_badge("404_CHUNK", f"Chunk bundle {chunk_id} tidak ditemukan di CDN build!", CLR_RED)
            return False

        # Suspense Fallback Triggered
        print_badge("SUSPENSE", f"<Suspense fallback={{<Spinner />}}> Aktif! Mengunduh {meta['name']} ({meta['size_kb']} KB)...", CLR_YELLOW)
        time.sleep(meta['latency'])
        self.downloaded_chunks[chunk_id] = meta['size_kb']
        print_badge("RESOLVED", f"Chunk '{chunk_id}' berhasil dimuat & dievaluasi oleh V8 runtime.", CLR_GREEN)
        return True


# --- 2. ROUTE & LAYOUT HIERARCHY (Feature-Sliced Organization) ---

class Route:
    def __init__(
        self,
        path: str,
        name: str,
        chunk_id: str,
        render_fn: Callable[[Dict[str, str]], str],
        requires_auth: bool = False,
        required_role: Optional[str] = None,
        layout_name: Optional[str] = None
    ):
        self.path = path
        self.name = name
        self.chunk_id = chunk_id
        self.render_fn = render_fn
        self.requires_auth = requires_auth
        self.required_role = required_role
        self.layout_name = layout_name

        # Kompilasi pattern regex untuk dynamic params (:id)
        pattern = re.sub(r':([a-zA-Z0-9_]+)', r'(?P<\1>[^/]+)', path)
        pattern = pattern.replace('*', '(?P<wildcard>.*)')
        self.regex = re.compile(f"^{pattern}$")

    def match(self, url: str) -> Optional[Dict[str, str]]:
        m = self.regex.match(url)
        return m.groupdict() if m else None


class AuthContext:
    def __init__(self):
        self.is_authenticated = False
        self.username = "Guest"
        self.role = "guest"

    def login(self, username: str, role: str):
        self.is_authenticated = True
        self.username = username
        self.role = role

    def logout(self):
        self.is_authenticated = False
        self.username = "Guest"
        self.role = "guest"


class ClientRouter:
    """Simulasi Declarative Router (React Router v6 / TanStack Router)"""
    def __init__(self, chunk_registry: ChunkRegistry, auth: AuthContext):
        self.registry = chunk_registry
        self.auth = auth
        self.routes: List[Route] = []
        self.history_stack: List[str] = []
        self.current_url: str = "/"

    def add_route(self, route: Route):
        self.routes.append(route)

    def navigate(self, target_url: str):
        print(f"\n{CLR_BOLD}--> Melakukan Push State: {CLR_CYAN}{target_url}{CLR_RESET}")
        matched_route = None
        params: Dict[str, str] = {}

        for route in self.routes:
            match_res = route.match(target_url)
            if match_res is not None:
                matched_route = route
                params = match_res
                break

        if not matched_route:
            print_badge("ROUTER_ERR", f"Tidak ada rute yang cocok untuk '{target_url}' (HTTP 404 Route Not Found)", CLR_RED)
            return

        # Navigation Guard (Protected Route)
        if matched_route.requires_auth and not self.auth.is_authenticated:
            print_badge("AUTH_GUARD", f"Akses ditolak! Halaman '{target_url}' dilindungi ProtectedRoute. Redirecting ke /login", CLR_RED)
            return

        if matched_route.required_role and self.auth.role != matched_route.required_role:
            print_badge("ROLE_GUARD", f"Role '{self.auth.role}' tidak memiliki otorisasi (Memerlukan: {matched_route.required_role})", CLR_RED)
            return

        # Lazy Loading & Code Splitting via React.lazy
        success = self.registry.load_chunk(matched_route.chunk_id)
        if not success:
            print_badge("RENDER_ERR", "Error Boundary menangkap kegagalan chunk fetch!", CLR_RED)
            return

        # Render Layout & Page (Outlet Pattern)
        self.history_stack.append(self.current_url)
        self.current_url = target_url

        print_badge("MOUNT", f"Rendering View: {matched_route.name}", CLR_GREEN)
        if matched_route.layout_name:
            print(f"{CLR_DIM}  [Layout Outlet: {matched_route.layout_name} -> Menyelipkan Komponen]{CLR_RESET}")
        
        rendered_content = matched_route.render_fn(params)
        print(f"{CLR_BOLD}  Output DOM:{CLR_RESET}\n    {rendered_content}")


# --- 3. SAMPLE COMPONENT RENDERERS ---

def render_home(params):
    return f"{CLR_GREEN}<h1>Selamat Datang di Portal Edukasi React Architecture</h1>{CLR_RESET}"

def render_dashboard(params):
    return f"{CLR_BLUE}<section className='dashboard-grid'><WidgetKpi /><ActivityFeed /></section>{CLR_RESET}"

def render_analytics(params):
    return f"{CLR_MAGENTA}<div className='analytics-chart'>[Highcharts / D3 SVG Rendered]</div>{CLR_RESET}"

def render_user_profile(params):
    uid = params.get("id", "unknown")
    return f"{CLR_CYAN}<div className='profile-card'>Profile Card for User #{uid} (Loaded via dynamic :id)</div>{CLR_RESET}"

def render_admin(params):
    return f"{CLR_YELLOW}<div className='admin-panel'>Admin Superuser Control Panel & Telemetry</div>{CLR_RESET}"


def setup_router() -> tuple[ClientRouter, ChunkRegistry, AuthContext]:
    registry = ChunkRegistry()
    auth = AuthContext()
    router = ClientRouter(registry, auth)

    router.add_route(Route("/", "HomePage", "chunk-home", render_home))
    router.add_route(Route("/dashboard", "DashboardOverview", "chunk-dashboard", render_dashboard, layout_name="DashboardLayout"))
    router.add_route(Route("/dashboard/analytics", "DashboardAnalytics", "chunk-analytics", render_analytics, layout_name="DashboardLayout"))
    router.add_route(Route("/users/:id", "UserProfile", "chunk-profile", render_user_profile))
    router.add_route(Route("/admin", "AdminPortal", "chunk-admin", render_admin, requires_auth=True, required_role="admin"))

    return router, registry, auth


def run_interactive_simulation():
    router, registry, auth = setup_router()
    print_header("SIMULASI TEKNIS: REACT ROUTING & CODE-SPLITTING")
    print(f"{CLR_DIM}Arsitektur: Dynamic Chunk Import, Suspense Latency, Layout Outlet, Role Guards{CLR_RESET}\n")

    actions = [
        ("1", "Navigasi: Ke Halaman Utama '/' (Download chunk-home)", "/"),
        ("2", "Navigasi: Ke '/dashboard' (Nested Layout + Code Split)", "/dashboard"),
        ("3", "Navigasi: Ke '/dashboard/analytics' (Chunk berat, simulasi Suspense)", "/dashboard/analytics"),
        ("4", "Navigasi: Cache-Hit Test - Kembali ke '/dashboard' (Instan)", "/dashboard"),
        ("5", "Navigasi: Dynamic Route '/users/42' (Param extraction)", "/users/42"),
        ("6", "Navigasi: Protected Route '/admin' saat Belum Login (Guard Block)", "/admin"),
        ("7", "Auth Action: Login sebagai Admin", "LOGIN_ADMIN"),
        ("8", "Navigasi: Protected Route '/admin' setelah Login (Guard Pass + Chunk Load)", "/admin"),
        ("9", "Auth Action: Logout (Reset AuthContext)", "LOGOUT"),
        ("0", "Keluar dari Simulasi", "EXIT")
    ]

    # Mode headless/non-interactive check
    if not sys.stdin.isatty():
        print_badge("AUTO_TEST", "Menjalankan auto-demo karena terminal berjalan non-interaktif...", CLR_YELLOW)
        for num, desc, payload in actions:
            if payload == "EXIT":
                break
            print(f"\n{CLR_BOLD}Langkah {num}: {desc}{CLR_RESET}")
            if payload == "LOGIN_ADMIN":
                auth.login("SarahArch", "admin")
                print_badge("AUTH", f"User logged in: {auth.username} (Role: {auth.role})", CLR_GREEN)
            elif payload == "LOGOUT":
                auth.logout()
                print_badge("AUTH", "User telah logout.", CLR_YELLOW)
            else:
                router.navigate(payload)
        print_header("SIMULASI SELESAI DENGAN SUKSES [STATUS OK]")
        return

    while True:
        print(f"\n{CLR_BOLD}Menu Simulasi Routing:{CLR_RESET}")
        for num, desc, _ in actions:
            print(f"  {CLR_CYAN}[{num}]{CLR_RESET} {desc}")
        
        try:
            choice = input(f"\n{CLR_YELLOW}Pilih opsi [0-9]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break

        selected = next((item for item in actions if item[0] == choice), None)
        if not selected:
            print(f"{CLR_RED}Pilihan tidak valid! Masukkan angka yang sesuai.{CLR_RESET}")
            continue

        _, _, target = selected
        if target == "EXIT":
            print(f"{CLR_GREEN}Terima kasih! Sampai jumpa di arsitektur modul berikutnya.{CLR_RESET}")
            break
        elif target == "LOGIN_ADMIN":
            auth.login("SarahArch", "admin")
            print_badge("AUTH", f"Berhasil login sebagai '{auth.username}' dengan role '{auth.role}'.", CLR_GREEN)
        elif target == "LOGOUT":
            auth.logout()
            print_badge("AUTH", "Sesi login diakhiri (Status: Guest).", CLR_YELLOW)
        else:
            router.navigate(target)

if __name__ == "__main__":
    run_interactive_simulation()
