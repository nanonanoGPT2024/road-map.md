#!/usr/bin/env python3
"""
Hands-on Lab M02: Simulasi Arsitektur Routing Produksi, Code-Splitting, & Code Organization
BAB-07: Routing Architecture, Code Splitting, dan Code Organization (React Ecosystem)

Fitur Simulasi:
1. Feature-First vs Layer-Based Directory Architecture Model
2. Dynamic Route Registry dengan Nested Route Layouts & Outlet Resolution
3. Code-Splitting Simulation (React.lazy + Dynamic import() chunk loader)
4. Suspense Fallback lifecycle & Network Latency profiling
5. Protected Route Guards & Role-Based Access Control (RBAC)
6. Route Error Boundary Simulation dengan recovery strategies
"""

import sys
import time
import random
from typing import Dict, List, Optional, Any

# ==============================================================================
# ANSI Terminal Color Palette
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"

# ==============================================================================
# Data Structures: Route, Chunk, & User Context
# ==============================================================================
class UserContext:
    def __init__(self, username: str = "guest", role: str = "guest", is_authenticated: bool = False):
        self.username = username
        self.role = role
        self.is_authenticated = is_authenticated

class RouteDefinition:
    def __init__(
        self,
        path: str,
        name: str,
        chunk_name: str,
        chunk_size_kb: int,
        component_view: str,
        requires_auth: bool = False,
        required_role: Optional[str] = None,
        parent: Optional[str] = None,
        can_fail: bool = False
    ):
        self.path = path
        self.name = name
        self.chunk_name = chunk_name
        self.chunk_size_kb = chunk_size_kb
        self.component_view = component_view
        self.requires_auth = requires_auth
        self.required_role = required_role
        self.parent = parent
        self.can_fail = can_fail

# ==============================================================================
# Core Engine: Bundler Cache & Route Orchestrator
# ==============================================================================
class ReactRouterSimulator:
    def __init__(self):
        self.user = UserContext()
        self.current_path = "/"
        self.loaded_chunks: Dict[str, float] = {}  # chunk_name -> load_timestamp
        self.routes: Dict[str, RouteDefinition] = {}
        self.history: List[str] = []
        self._init_routes()

    def _init_routes(self):
        # Struktur direktori feature-based yang dipetakan ke route bundle
        self.routes = {
            "/": RouteDefinition(
                path="/",
                name="Landing & Hero Module",
                chunk_name="features/home/HomeView.chunk.js",
                chunk_size_kb=42,
                component_view="[Feature: Home] Sambutan selamat datang di platform produksi modern."
            ),
            "/features": RouteDefinition(
                path="/features",
                name="Feature Showcase",
                chunk_name="features/catalog/FeatureList.chunk.js",
                chunk_size_kb=88,
                component_view="[Feature: Catalog] Daftar kapabilitas micro-frontend & modular code splitting."
            ),
            "/dashboard": RouteDefinition(
                path="/dashboard",
                name="Main Dashboard (Protected)",
                chunk_name="features/dashboard/DashboardLayout.chunk.js",
                chunk_size_kb=156,
                component_view="[Feature: Dashboard] Ringkasan KPI performa client bundle dan routing metrics.",
                requires_auth=True
            ),
            "/dashboard/analytics": RouteDefinition(
                path="/dashboard/analytics",
                name="Deep Analytics (Heavy Chunk)",
                chunk_name="features/analytics/AnalyticsCharts.chunk.js",
                chunk_size_kb=430,
                component_view="[Feature: Analytics] Grafik interaktif Recharts/Echarts dengan lazy hydration.",
                requires_auth=True,
                parent="/dashboard"
            ),
            "/admin": RouteDefinition(
                path="/admin",
                name="Enterprise Admin Console",
                chunk_name="features/admin/AdminControl.chunk.js",
                chunk_size_kb=280,
                component_view="[Feature: Admin] Panel audit keamanan, permission matrix, dan konfigurasi server.",
                requires_auth=True,
                required_role="admin"
            ),
            "/error-lab": RouteDefinition(
                path="/error-lab",
                name="Corrupted Route (Error Boundary Tester)",
                chunk_name="features/experimental/CorruptedModule.chunk.js",
                chunk_size_kb=64,
                component_view="[Feature: Experimental] Modul bermasalah untuk simulasi runtime crash.",
                can_fail=True
            )
        }

    def simulate_suspense_loading(self, chunk_name: str, size_kb: int) -> bool:
        """Simulasi network waterfall, React.lazy dynamic import & Suspense fallback."""
        if chunk_name in self.loaded_chunks:
            print(f"  {Color.GREEN}⚡ [Cache Hit]{Color.RESET} {Color.GRAY}{chunk_name} telah berada di memory cache browser.{Color.RESET}")
            return True

        print(f"  {Color.YELLOW}⌛ [Suspense Fallback]{Color.RESET} <Spinner message=\"Memuat {chunk_name} ({size_kb} KB)...\" />")
        
        # Simulasi network delay berdasarkan ukuran chunk
        steps = 5
        base_delay = 0.04 + (size_kb / 1500.0) * 0.1
        sys.stdout.write("  " + Color.CYAN + "[" + Color.RESET)
        for i in range(steps):
            time.sleep(base_delay)
            sys.stdout.write(Color.CYAN + "█" + Color.RESET)
            sys.stdout.flush()
        sys.stdout.write(Color.CYAN + "] " + Color.RESET + f"{Color.GREEN}100% Downloaded{Color.RESET}\n")

        self.loaded_chunks[chunk_name] = time.time()
        return True

    def navigate(self, target_path: str):
        print(f"\n{Color.BOLD}{Color.BLUE}===> Menjalankan Navigasi: history.pushState('{target_path}'){Color.RESET}")
        
        if target_path not in self.routes:
            print(f"{Color.RED}✖ 404 Not Found:{Color.RESET} Tidak ada route definition untuk '{target_path}'.")
            print(f"  {Color.GRAY}Rendering generic <NotFoundCatchAll /> component.{Color.RESET}")
            return

        route = self.routes[target_path]

        # 1. Navigation Guard (Auth Check)
        if route.requires_auth and not self.user.is_authenticated:
            print(f"{Color.RED}⛔ [Guard Rejection]{Color.RESET} Route '{target_path}' membutuhkan autentikasi!")
            print(f"  {Color.YELLOW}↪ Redirecting ke /login?redirect={target_path}{Color.RESET}")
            return

        # 2. RBAC Guard (Role Check)
        if route.required_role and self.user.role != route.required_role:
            print(f"{Color.RED}⛔ [RBAC Forbidden]{Color.RESET} Role saat ini '{self.user.role}' tidak memiliki akses (Dibutuhkan: '{route.required_role}').")
            print(f"  {Color.YELLOW}↪ Rendering <UnauthorizedView reason=\"Insufficient privileges\" />{Color.RESET}")
            return

        # 3. Handle Nested Route Parent Loading
        if route.parent:
            parent_route = self.routes.get(route.parent)
            if parent_route and parent_route.chunk_name not in self.loaded_chunks:
                print(f"{Color.MAGENTA}↳ [Nested Layout]{Color.RESET} Memuat Parent Layout terlebih dahulu ({parent_route.name})...")
                self.simulate_suspense_loading(parent_route.chunk_name, parent_route.chunk_size_kb)

        # 4. Code-Splitting & Dynamic Import via Suspense
        self.simulate_suspense_loading(route.chunk_name, route.chunk_size_kb)

        # 5. Error Boundary Check
        if route.can_fail and random.random() < 0.75:
            print(f"\n{Color.RED}{Color.BOLD}💥 [React ErrorBoundary Caught Runtime Exception]{Color.RESET}")
            print(f"  {Color.RED}Error: TypeError: Cannot read properties of undefined (reading 'renderPayload'){Color.RESET}")
            print(f"  {Color.YELLOW}Fallback UI:{Color.RESET} <RouteErrorBoundary onReset={{{{() => window.location.reload()}}}} />")
            print(f"  {Color.GRAY}[Telemetry]{Color.RESET} Sentry error report sent with breadcrumb trace.")
            return

        # 6. Successful Mount
        self.current_path = target_path
        self.history.append(target_path)
        print(f"\n{Color.GREEN}✔ [Mounted Successfully]{Color.RESET} {Color.BOLD}{route.name}{Color.RESET}")
        print(f"  {Color.CYAN}Path:{Color.RESET} {route.path}")
        print(f"  {Color.CYAN}View:{Color.RESET} {route.component_view}")
        print(f"  {Color.GRAY}Active Tree:{Color.RESET} <AppRoot> -> <NavigationProvider> -> <Suspense> -> {route.name}")

    def print_bundle_inspector(self):
        print(f"\n{Color.BOLD}{Color.WHITE}------------------------------------------------------------{Color.RESET}")
        print(f"{Color.BOLD}{Color.YELLOW}📦 BUNDLE & CHUNK CACHE INSPECTOR (Webpack / Vite SplitChunks){Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}------------------------------------------------------------{Color.RESET}")
        total_size = sum(r.chunk_size_kb for r in self.routes.values())
        loaded_size = sum(self.routes[p].chunk_size_kb for p in self.routes if self.routes[p].chunk_name in self.loaded_chunks)
        
        print(f"Total Bundle Available: {Color.CYAN}{total_size} KB{Color.RESET}")
        print(f"Loaded in Browser RAM : {Color.GREEN}{loaded_size} KB{Color.RESET} ({len(self.loaded_chunks)} chunks aktif)")
        print(f"Bandwidth Saved       : {Color.MAGENTA}{total_size - loaded_size} KB (via Lazy Loading){Color.RESET}\n")

        for path, r in self.routes.items():
            status = f"{Color.GREEN}[LOADED]{Color.RESET}" if r.chunk_name in self.loaded_chunks else f"{Color.GRAY}[LAZY]  {Color.RESET}"
            print(f"  {status} {r.path.ljust(22)} -> {r.chunk_name} ({r.chunk_size_kb} KB)")
        print(f"{Color.BOLD}{Color.WHITE}------------------------------------------------------------{Color.RESET}")

    def switch_user_session(self, is_admin: bool = False, login: bool = True):
        if not login:
            self.user = UserContext("guest", "guest", False)
            print(f"{Color.YELLOW}ℹ Sesi di-logout. Kembali menjadi mode 'guest'.{Color.RESET}")
        elif is_admin:
            self.user = UserContext("sys_admin", "admin", True)
            print(f"{Color.GREEN}✔ Login berhasil: 'sys_admin' (Role: admin, Full Access){Color.RESET}")
        else:
            self.user = UserContext("member_1", "user", True)
            print(f"{Color.GREEN}✔ Login berhasil: 'member_1' (Role: user, Standard Access){Color.RESET}")

# ==============================================================================
# Interactive Terminal User Interface (TUI)
# ==============================================================================
def display_header(sim: ReactRouterSimulator):
    auth_badge = (
        f"{Color.GREEN}Authenticated ({sim.user.username} | {sim.user.role}){Color.RESET}"
        if sim.user.is_authenticated
        else f"{Color.GRAY}Guest / Unauthenticated{Color.RESET}"
    )
    print("\n" + "=" * 68)
    print(f"{Color.BOLD}{Color.CYAN}⚛ REACT ROUTING & CODE-SPLITTING ARCHITECTURE LAB (CLI SIMULATOR){Color.RESET}")
    print(f"  Current URL  : {Color.BOLD}{Color.YELLOW}{sim.current_path}{Color.RESET}")
    print(f"  Auth Status  : {auth_badge}")
    print(f"  Cached Chunks: {Color.MAGENTA}{len(sim.loaded_chunks)}{Color.RESET} file(s)")
    print("=" * 68)

def print_menu():
    print(f"\n{Color.BOLD}Navigasi & Operasi Arsitektur:{Color.RESET}")
    print(f"  {Color.CYAN}1.{Color.RESET} Navigasi ke '/' (Home Landing)")
    print(f"  {Color.CYAN}2.{Color.RESET} Navigasi ke '/features' (Feature List)")
    print(f"  {Color.CYAN}3.{Color.RESET} Navigasi ke '/dashboard' (Protected Route)")
    print(f"  {Color.CYAN}4.{Color.RESET} Navigasi ke '/dashboard/analytics' (Nested & Heavy Chunk)")
    print(f"  {Color.CYAN}5.{Color.RESET} Navigasi ke '/admin' (RBAC Admin Only)")
    print(f"  {Color.CYAN}6.{Color.RESET} Uji Error Boundary ('/error-lab')")
    print(f"  {Color.CYAN}7.{Color.RESET} Buka Bundle & Chunk Inspector")
    print(f"  {Color.CYAN}8.{Color.RESET} Toggle Auth: Login User Standar")
    print(f"  {Color.CYAN}9.{Color.RESET} Toggle Auth: Login Admin Enterprise")
    print(f"  {Color.CYAN}0.{Color.RESET} Logout ke Guest")
    print(f"  {Color.RED}q.{Color.RESET} Keluar (Exit)")

def run_automated_tour(sim: ReactRouterSimulator):
    """Jalankan demonstrasi otomatis jika terminal non-interaktif."""
    print(f"{Color.BOLD}{Color.YELLOW}=== Memulai Automated Architecture Verification Tour ==={Color.RESET}")
    sim.navigate("/")
    sim.navigate("/features")
    sim.navigate("/dashboard")  # Harus ditolak oleh guard
    sim.switch_user_session(is_admin=False, login=True)
    sim.navigate("/dashboard")
    sim.navigate("/dashboard/analytics")
    sim.navigate("/admin")      # Harus ditolak oleh RBAC
    sim.switch_user_session(is_admin=True, login=True)
    sim.navigate("/admin")
    sim.print_bundle_inspector()
    print(f"\n{Color.GREEN}✔ Automated tour selesai tanpa crash tak terduga.{Color.RESET}\n")

def main():
    simulator = ReactRouterSimulator()

    # Jika argumen --auto diberikan atau input dialihkan (CI/headless), jalankan mode otomatis
    if "--auto" in sys.argv or not sys.stdin.isatty():
        run_automated_tour(simulator)
        return

    while True:
        display_header(simulator)
        print_menu()
        try:
            choice = input(f"\n{Color.BOLD}{Color.WHITE}Pilih aksi [0-9, q]: {Color.RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            simulator.navigate("/")
        elif choice == "2":
            simulator.navigate("/features")
        elif choice == "3":
            simulator.navigate("/dashboard")
        elif choice == "4":
            simulator.navigate("/dashboard/analytics")
        elif choice == "5":
            simulator.navigate("/admin")
        elif choice == "6":
            simulator.navigate("/error-lab")
        elif choice == "7":
            simulator.print_bundle_inspector()
        elif choice == "8":
            simulator.switch_user_session(is_admin=False, login=True)
        elif choice == "9":
            simulator.switch_user_session(is_admin=True, login=True)
        elif choice == "0":
            simulator.switch_user_session(login=False)
        elif choice == "q":
            print(f"\n{Color.CYAN}Terima kasih telah mengeksplorasi arsitektur routing & code-splitting!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}")
        
        time.sleep(0.3)

if __name__ == "__main__":
    main()
