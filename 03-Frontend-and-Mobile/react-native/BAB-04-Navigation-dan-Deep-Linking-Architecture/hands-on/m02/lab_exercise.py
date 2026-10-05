#!/usr/bin/env python3
"""
Simulasi Arsitektur Produksi React Native: Navigation & Deep Linking Engine
BAB-04: Navigation dan Deep Linking Architecture
"""

import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

# ANSI Color Codes untuk Terminal Styling
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class RouteConfig:
    pattern: str
    target_screen: str
    navigator_path: List[str]
    requires_auth: bool = False
    param_keys: List[str] = field(default_factory=list)


@dataclass
class NavigationAction:
    screen: str
    params: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class DeepLinkingEngine:
    def __init__(self, prefixes: List[str]):
        self.prefixes = prefixes
        self.routes: List[RouteConfig] = []

    def register_route(self, pattern: str, target: str, nav_path: List[str], requires_auth: bool = False):
        # Convert path pattern e.g., "products/:id/details" to regex
        param_keys = re.findall(r":([a-zA-Z0-9_]+)", pattern)
        regex_pattern = "^" + re.sub(r":([a-zA-Z0-9_]+)", r"(?P<\1>[^/]+)", pattern) + "$"
        self.routes.append(
            RouteConfig(
                pattern=regex_pattern,
                target_screen=target,
                navigator_path=nav_path,
                requires_auth=requires_auth,
                param_keys=param_keys,
            )
        )

    def parse_url(self, url: str) -> Optional[Dict[str, Any]]:
        matched_prefix = None
        for prefix in self.prefixes:
            if url.startswith(prefix):
                matched_prefix = prefix
                break

        if not matched_prefix:
            return None

        clean_path = url[len(matched_prefix):]
        if not clean_path.startswith("/"):
            clean_path = "/" + clean_path

        parsed = urlparse(clean_path)
        path = parsed.path.strip("/")
        query_params = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}

        for route in self.routes:
            match = re.match(route.pattern, path)
            if match:
                route_params = match.groupdict()
                combined_params = {**query_params, **route_params}
                return {
                    "matched": True,
                    "target_screen": route.target_screen,
                    "navigator_path": route.navigator_path,
                    "params": combined_params,
                    "requires_auth": route.requires_auth,
                    "original_url": url,
                }

        return {
            "matched": False,
            "target_screen": "NotFound",
            "navigator_path": ["RootStack", "NotFoundModal"],
            "params": {"attempted_path": path},
            "requires_auth": False,
            "original_url": url,
        }


class ProductionNavigationContainer:
    def __init__(self):
        self.is_authenticated = False
        self.current_user = None
        self.nav_stack: List[NavigationAction] = []
        self.pending_deep_link: Optional[str] = None
        self.linking_engine = DeepLinkingEngine(
            prefixes=["myapp://", "https://app.production.io", "https://*.production.io"]
        )
        self._init_linking_schema()
        self.navigate("FeedScreen", {})

    def _init_linking_schema(self):
        # Nested Hierarchies: Root -> MainTabs / Modals / Auth
        self.linking_engine.register_route(
            pattern="feed",
            target="FeedScreen",
            nav_path=["RootStack", "MainTabs", "HomeStack", "FeedScreen"],
            requires_auth=False,
        )
        self.linking_engine.register_route(
            pattern="products/:id",
            target="ProductDetailScreen",
            nav_path=["RootStack", "MainTabs", "CatalogStack", "ProductDetailScreen"],
            requires_auth=False,
        )
        self.linking_engine.register_route(
            pattern="orders/:orderId/tracking",
            target="OrderTrackingScreen",
            nav_path=["RootStack", "MainTabs", "OrdersStack", "OrderTrackingScreen"],
            requires_auth=True,
        )
        self.linking_engine.register_route(
            pattern="account/settings",
            target="AccountSettingsScreen",
            nav_path=["RootStack", "MainTabs", "ProfileStack", "AccountSettingsScreen"],
            requires_auth=True,
        )
        self.linking_engine.register_route(
            pattern="checkout/pay",
            target="PaymentModalScreen",
            nav_path=["RootStack", "PaymentModalStack", "PaymentModalScreen"],
            requires_auth=True,
        )

    def navigate(self, screen: str, params: Dict[str, Any]):
        action = NavigationAction(screen=screen, params=params)
        self.nav_stack.append(action)

    def go_back(self) -> bool:
        if len(self.nav_stack) > 1:
            popped = self.nav_stack.pop()
            return True
        return False

    def handle_incoming_url(self, url: str) -> Dict[str, Any]:
        result = self.linking_engine.parse_url(url)
        if not result:
            return {"status": "FAILED", "reason": "URL prefix tidak dikenali oleh prefix configuration"}

        if not result["matched"]:
            self.navigate("NotFoundScreen", result["params"])
            return {"status": "NOT_FOUND", "details": result}

        if result["requires_auth"] and not self.is_authenticated:
            # Save pending link for post-auth continuation (Return URL pattern)
            self.pending_deep_link = url
            self.navigate("AuthModalScreen", {"returnTo": result["target_screen"], "params": result["params"]})
            return {
                "status": "AUTH_GUARD_TRIGGERED",
                "details": result,
                "message": "Screen membutuhkan otentikasi. Mengarahkan ke AuthModalScreen.",
            }

        # Auth lolos atau route publik
        self.navigate(result["target_screen"], result["params"])
        return {"status": "SUCCESS", "details": result}

    def login(self, username: str):
        self.is_authenticated = True
        self.current_user = username
        # Jika ada deep link tertunda, proses sekarang
        if self.pending_deep_link:
            resuming_url = self.pending_deep_link
            self.pending_deep_link = None
            return self.handle_incoming_url(resuming_url)
        return None

    def logout(self):
        self.is_authenticated = False
        self.current_user = None
        self.nav_stack = [NavigationAction(screen="FeedScreen", params={})]


def print_banner():
    print(f"{Colors.CYAN}{Colors.BOLD}" + "=" * 70)
    print("  REACT NATIVE NAVIGATION & DEEP LINKING ARCHITECTURE SIMULATOR")
    print("  Enterprise-grade Deep Link Parser & Protected Route Engine")
    print("=" * 70 + f"{Colors.RESET}\n")


def print_state(container: ProductionNavigationContainer):
    auth_badge = (
        f"{Colors.GREEN}[AUTHENTICATED: {container.current_user}]{Colors.RESET}"
        if container.is_authenticated
        else f"{Colors.YELLOW}[GUEST / UNAUTHENTICATED]{Colors.RESET}"
    )

    current_screen = container.nav_stack[-1].screen if container.nav_stack else "None"
    current_params = container.nav_stack[-1].params if container.nav_stack else {}

    print(f"\n{Colors.HEADER}--- STATE NAVIGATION CONTAINER ---{Colors.RESET}")
    print(f"Status Sesi   : {auth_badge}")
    print(f"Layar Aktif   : {Colors.BOLD}{Colors.CYAN}{current_screen}{Colors.RESET}")
    print(f"Params Aktif  : {Colors.DIM}{current_params}{Colors.RESET}")
    print(f"Pending DeepLink: {Colors.YELLOW}{container.pending_deep_link or 'None'}{Colors.RESET}")
    print("Navigation Stack (History):")
    for idx, act in enumerate(container.nav_stack):
        pointer = " -> " if idx == len(container.nav_stack) - 1 else "    "
        print(f"  {idx + 1}.{pointer}{Colors.BOLD}{act.screen}{Colors.RESET} {Colors.DIM}{act.params}{Colors.RESET}")
    print(f"{Colors.HEADER}----------------------------------{Colors.RESET}\n")


def interactive_cli():
    print_banner()
    container = ProductionNavigationContainer()

    sample_urls = [
        ("1", "myapp://feed", "Publik: Feed Home Screen"),
        ("2", "myapp://products/prod-9981?ref=banner&promo=OCT26", "Publik: Detail Produk dengan Path & Query params"),
        ("3", "https://app.production.io/orders/ORD-7721/tracking", "Protected: Pelacakan Pesanan (Harus Login)"),
        ("4", "myapp://account/settings", "Protected: Pengaturan Akun (Harus Login)"),
        ("5", "myapp://checkout/pay?currency=IDR&amount=150000", "Protected Modal: Alur Pembayaran"),
        ("6", "myapp://unknown/endpoint/testing", "Edge Case: Invalid Route (404 Screen)"),
        ("7", "unsupported://external-link/foo", "Edge Case: Invalid Prefix"),
    ]

    while True:
        print_state(container)
        print(f"{Colors.BOLD}Pilihan Aksi:{Colors.RESET}")
        print(f"  [{Colors.CYAN}D{Colors.RESET}] Dispatch Deep Link dari daftar presisi")
        print(f"  [{Colors.CYAN}C{Colors.RESET}] Masukkan Custom URL Deep Link secara manual")
        print(f"  [{Colors.CYAN}B{Colors.RESET}] Navigasi Kembali (goBack)")
        if not container.is_authenticated:
            print(f"  [{Colors.GREEN}L{Colors.RESET}] Login Simulasi (Otentikasi Pengguna)")
        else:
            print(f"  [{Colors.RED}O{Colors.RESET}] Logout Simulasi")
        print(f"  [{Colors.DIM}Q{Colors.RESET}] Keluar dari Simulator")

        choice = input(f"\n{Colors.BOLD}Masukkan pilihan anda [D/C/B/L/O/Q]: {Colors.RESET}").strip().upper()

        if choice == "Q":
            print(f"\n{Colors.GREEN}Terima kasih telah mencoba Simulator Deep Linking React Native!{Colors.RESET}")
            sys.exit(0)

        elif choice == "D":
            print(f"\n{Colors.BOLD}Pilih Preset URL Deep Link:{Colors.RESET}")
            for key, url, desc in sample_urls:
                print(f"  [{Colors.YELLOW}{key}{Colors.RESET}] {url} - {Colors.DIM}{desc}{Colors.RESET}")
            sel = input(f"{Colors.BOLD}Pilih nomor (1-7): {Colors.RESET}").strip()
            chosen = next((u for k, u, _ in sample_urls if k == sel), None)
            if chosen:
                print(f"\n{Colors.CYAN}[Dispatching Link]{Colors.RESET} Memproses: {chosen} ...")
                res = container.handle_incoming_url(chosen)
                print(f"{Colors.BOLD}Hasil Routing: {Colors.RESET}{res['status']}")
                if "details" in res and "navigator_path" in res["details"]:
                    nav_chain = " -> ".join(res["details"]["navigator_path"])
                    print(f"Resolved Tree: {Colors.GREEN}{nav_chain}{Colors.RESET}")
                if "message" in res:
                    print(f"Pesan        : {Colors.YELLOW}{res['message']}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Pilihan tidak valid!{Colors.RESET}")

        elif choice == "C":
            custom_url = input(f"{Colors.BOLD}Ketikkan URL (misal: myapp://products/8821?ref=test): {Colors.RESET}").strip()
            if custom_url:
                print(f"\n{Colors.CYAN}[Dispatching Custom Link]{Colors.RESET} Memproses: {custom_url} ...")
                res = container.handle_incoming_url(custom_url)
                print(f"{Colors.BOLD}Hasil Routing: {Colors.RESET}{res['status']}")
                if "details" in res and "navigator_path" in res["details"]:
                    nav_chain = " -> ".join(res["details"]["navigator_path"])
                    print(f"Resolved Tree: {Colors.GREEN}{nav_chain}{Colors.RESET}")
                elif "reason" in res:
                    print(f"{Colors.RED}Gagal: {res['reason']}{Colors.RESET}")

        elif choice == "B":
            if container.go_back():
                print(f"{Colors.GREEN}Navigasi berhasil mundur 1 step.{Colors.RESET}")
            else:
                print(f"{Colors.RED}Tidak dapat mundur lebih jauh (Root stack reached).{Colors.RESET}")

        elif choice == "L" and not container.is_authenticated:
            uname = input(f"{Colors.BOLD}Masukkan username simulasi: {Colors.RESET}").strip() or "developer"
            resume_res = container.login(uname)
            print(f"\n{Colors.GREEN}Otentikasi Berhasil sebagai: {uname}{Colors.RESET}")
            if resume_res:
                print(f"{Colors.CYAN}[Resume Deep Link Terdeteksi]{Colors.RESET}")
                print(f"Melanjutkan navigasi tertunda ke: {resume_res['details']['target_screen']}")
                nav_chain = " -> ".join(resume_res["details"]["navigator_path"])
                print(f"Resolved Tree: {Colors.GREEN}{nav_chain}{Colors.RESET}")

        elif choice == "O" and container.is_authenticated:
            container.logout()
            print(f"\n{Colors.YELLOW}Pengguna telah keluar. Stack di-reset ke default feed.{Colors.RESET}")

        else:
            print(f"{Colors.RED}Pilihan tidak dikenali.{Colors.RESET}")

        time.sleep(0.5)


if __name__ == "__main__":
    try:
        interactive_cli()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Simulator dihentikan oleh user.{Colors.RESET}")
        sys.exit(0)
