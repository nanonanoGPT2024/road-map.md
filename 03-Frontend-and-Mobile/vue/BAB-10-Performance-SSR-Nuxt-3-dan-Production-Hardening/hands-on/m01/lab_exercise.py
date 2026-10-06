#!/usr/bin/env python3
"""
Lab Exercise: Vue 3 / Nuxt 3 Performance, SSR, and Production Hardening Simulator.
Simulasi konsep teknis:
1. SSR Rendering Pipeline & Hydration Mismatch Detection
2. Universal Data Fetching (`useAsyncData`) & Payload Transfer (__NUXT__)
3. Code-Splitting, Lazy Loading & Virtual Windowing
4. Production Hardening: Security Headers & Memory Leak Inspection
"""

import sys
import time
import json
import hashlib
from typing import Dict, List, Any, Optional

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{CYAN}[LAB] {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


class SSRHydrationEngine:
    """Simulasi Server-Side Rendering dan Client-Side Hydration."""

    def __init__(self):
        self.server_state: Dict[str, Any] = {}
        self.client_state: Dict[str, Any] = {}

    def render_to_string(self, component_name: str, props: Dict[str, Any], server_time: str) -> str:
        self.server_state = {"component": component_name, "props": props, "rendered_at": server_time}
        html = (
            f'<div data-v-app id="app">'
            f'<article class="card" data-server-rendered="true">'
            f'<h1>{props.get("title", "Nuxt App")}</h1>'
            f'<p class="meta">Rendered at: {server_time}</p>'
            f'<span class="badge status-active">Active Users: {props.get("users_count", 0)}</span>'
            f'</article>'
            f'</div>'
        )
        return html

    def hydrate(self, server_html: str, client_render_time: str, strict_mode: bool = True) -> bool:
        print(f"{DIM}[Hydration] Scanning SSR HTML DOM nodes...{RESET}")
        time.sleep(0.15)
        
        # Simulasi bug umum: client hydration mismatch karena non-deterministic timestamp
        has_mismatch = (self.server_state.get("rendered_at") != client_render_time)

        if has_mismatch:
            print(f"{YELLOW}[WARN] Hydration text content mismatch detected!{RESET}")
            print(f"  {RED}- Server Output : 'Rendered at: {self.server_state.get('rendered_at')}'{RESET}")
            print(f"  {GREEN}+ Client Virtual: 'Rendered at: {client_render_time}'{RESET}")
            if strict_mode:
                print(f"{RED}[FAIL] Hydration failed! Vue falls back to full client re-render.{RESET}")
                return False
            else:
                print(f"{YELLOW}[WARN] Suppressing hydration mismatch. Patching DOM in-place.{RESET}")
                return True
        else:
            print(f"{GREEN}[SUCCESS] Perfect DOM hydration match. Event listeners attached seamlessly.{RESET}")
            return True


class NitroPayloadManager:
    """Simulasi useAsyncData deduplication & __NUXT__ state serialization."""

    def __init__(self):
        self.payload_store: Dict[str, Any] = {}
        self.fetch_call_count = 0

    def use_async_data(self, key: str, fetcher_fn, is_client: bool) -> Dict[str, Any]:
        if key in self.payload_store and is_client:
            print(f"{GREEN}[Payload Cache Hit] Key '{key}' reused from SSR payload! Zero client network fetch.{RESET}")
            return {"data": self.payload_store[key], "cached": True}

        print(f"{MAGENTA}[Network Call] Fetching data for key '{key}'...{RESET}")
        self.fetch_call_count += 1
        data = fetcher_fn()
        self.payload_store[key] = data
        return {"data": data, "cached": False}

    def serialize_payload(self) -> str:
        return json.dumps(self.payload_store, indent=2)


class BundleOptimizer:
    """Simulasi Code-Splitting, Lazy Loading, dan Virtual Windowing."""

    @staticmethod
    def simulate_lazy_import(route: str) -> None:
        print(f"\n{BOLD}[Router Navigation] Requesting route: '{route}'{RESET}")
        if route == "/dashboard":
            print(f"{DIM}  Downloading main vendor chunk: 24.5 kB (gzip){RESET}")
            time.sleep(0.1)
            print(f"{GREEN}  Dynamic chunk loaded: 'pages/dashboard-[hash].js' (12.2 kB){RESET}")
        elif route == "/admin/analytics":
            print(f"{DIM}  Dynamic chunk loaded: 'pages/admin-analytics-[hash].js' (85.4 kB){RESET}")
            print(f"{DIM}  Lazy chart library: 'chart-vendor-[hash].js' (42.0 kB){RESET}")
        else:
            print(f"{GREEN}  Static route loaded directly.{RESET}")

    @staticmethod
    def virtual_window_benchmark(total_items: int = 10000, window_size: int = 20) -> None:
        print(f"\n{BOLD}[Performance] Virtual List vs Standard DOM List ({total_items:,} items){RESET}")
        standard_dom_nodes = total_items * 4
        virtual_dom_nodes = window_size * 4
        savings = ((standard_dom_nodes - virtual_dom_nodes) / standard_dom_nodes) * 100

        print(f"  Standard v-for DOM Nodes : {RED}{standard_dom_nodes:,} nodes{RESET} (~{standard_dom_nodes * 0.05:.1f} MB memory)")
        print(f"  Virtual Window DOM Nodes : {GREEN}{virtual_dom_nodes} nodes{RESET} (~{virtual_dom_nodes * 0.05:.2f} MB memory)")
        print(f"  {BOLD}{GREEN}DOM footprint reduction: {savings:.2f}%{RESET}")


class ProductionHardeningAudit:
    """Audit konfigurasi keamanan & sanitasi production Nuxt 3 / Nitro."""

    REQUIRED_HEADERS = {
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'nonce-...'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
    }

    @classmethod
    def audit_headers(cls, configured_headers: Dict[str, str]) -> None:
        print(f"\n{BOLD}[Security Audit] Checking Nitro Server Security Headers:{RESET}")
        passed = 0
        for header_name, recommended in cls.REQUIRED_HEADERS.items():
            if header_name in configured_headers:
                print(f"  {GREEN}[PASS]{RESET} {header_name}: {configured_headers[header_name]}")
                passed += 1
            else:
                print(f"  {RED}[FAIL]{RESET} Missing header: {BOLD}{header_name}{RESET}")
                print(f"         Recommended: {DIM}{recommended}{RESET}")
        
        score = (passed / len(cls.REQUIRED_HEADERS)) * 100
        print(f"\nHardening Compliance Score: {BOLD}{GREEN if score == 100 else YELLOW}{score:.0f}%{RESET}")


def run_interactive_lab():
    header("Vue 3 & Nuxt 3 Production Hardening Interactive Lab")
    
    ssr_engine = SSRHydrationEngine()
    payload_mgr = NitroPayloadManager()
    optimizer = BundleOptimizer()
    
    # Step 1: SSR Rendering
    print(f"\n{BOLD}{MAGENTA}--- 1. SERVER-SIDE RENDERING (SSR) & HYDRATION ---{RESET}")
    server_time = "2026-10-06 04:30:00 UTC"
    ssr_html = ssr_engine.render_to_string(
        "UserProfileCard",
        {"title": "Enterprise Cloud Console", "users_count": 4820},
        server_time=server_time
    )
    print(f"{CYAN}Generated SSR HTML output:{RESET}\n{DIM}{ssr_html}{RESET}\n")

    print(f"{BOLD}Simulasi 1A: Client Hydration Mismatch (Timestamp dynamic di client){RESET}")
    ssr_engine.hydrate(ssr_html, client_render_time="2026-10-06 04:30:02 UTC", strict_mode=True)

    print(f"\n{BOLD}Simulasi 1B: Clean Hydration (Deterministic / Frozen State){RESET}")
    ssr_engine.hydrate(ssr_html, client_render_time=server_time, strict_mode=True)

    # Step 2: Nitro Universal Fetching
    print(f"\n{BOLD}{MAGENTA}--- 2. NUXT 3 useAsyncData & PAYLOAD DEDUPLICATION ---{RESET}")
    fetch_counter = 0

    def mock_api_call():
        nonlocal fetch_counter
        fetch_counter += 1
        return {"id": 101, "role": "SiteAdmin", "tenant": "APAC-01", "version": "3.12.0"}

    print(f"{DIM}Fase 1: SSR Execution di Nitro Server...{RESET}")
    server_fetch = payload_mgr.use_async_data("auth-session", mock_api_call, is_client=False)
    print(f"  Server fetched data: {server_fetch['data']}")

    print(f"\n{DIM}Fase 2: Client Hydration di Browser...{RESET}")
    client_fetch = payload_mgr.use_async_data("auth-session", mock_api_call, is_client=True)
    print(f"  Client fetched data: {client_fetch['data']}")
    print(f"  Total actual API requests dispatched: {BOLD}{GREEN}{payload_mgr.fetch_call_count}{RESET} (Expected: 1)")

    # Step 3: Bundle Optimization & Virtual Windowing
    print(f"\n{BOLD}{MAGENTA}--- 3. CODE-SPLITTING & VIRTUAL SCROLLING ---{RESET}")
    optimizer.simulate_lazy_import("/dashboard")
    optimizer.simulate_lazy_import("/admin/analytics")
    optimizer.virtual_window_benchmark(total_items=25000, window_size=25)

    # Step 4: Security Headers
    print(f"\n{BOLD}{MAGENTA}--- 4. NITRO PRODUCTION SECURITY HEADERS ---{RESET}")
    mock_headers = {
        "Content-Security-Policy": "default-src 'self'; script-src 'self'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
    }
    ProductionHardeningAudit.audit_headers(mock_headers)

    print(f"\n{BOLD}{GREEN}================================================================={RESET}")
    print(f"{BOLD}{GREEN}[VERIFIED] Lab exercise finished successfully with 0 errors!{RESET}")
    print(f"{BOLD}{GREEN}================================================================={RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()
