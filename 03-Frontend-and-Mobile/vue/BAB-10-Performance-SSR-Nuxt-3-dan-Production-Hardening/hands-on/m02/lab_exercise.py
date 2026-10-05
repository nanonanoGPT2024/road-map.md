#!/usr/bin/env python3
"""
Lab Exercise M02: Simulasi Arsitektur Produksi Vue 3 / Nuxt 3 & Production Hardening
Topik: BAB-10 Performance, SSR, Nuxt 3, Nitro Engine & Production Hardening

Fitur Simulasi:
1. Universal Rendering & Hydration Mismatch Detector
2. Cross-Request State Pollution Isolation (Pinia/useState SSR Safety)
3. SWR (Stale-While-Revalidate) Cache Engine & CDN Edge Tags
4. Security Hardening: Strict CSP Nonce Injection & Memory Leak Profiler
"""

import sys
import time
import random
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"


def print_banner():
    print(f"\n{CYAN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD}   NUXT 3 NITRO ENGINE & PRODUCTION HARDENING ARCHITECTURE LAB    {RESET}")
    print(f"{CYAN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"{DIM}Simulasi Universal Rendering, State Isolation, Cache Tags & Security Audit{RESET}\n")


# -----------------------------------------------------------------------------
# 1. SSR & Hydration Simulation
# -----------------------------------------------------------------------------
@dataclass
class SSRRenderResult:
    html: str
    server_time: str
    client_payload: Dict[str, Any]


class NuxtHydrationEngine:
    @staticmethod
    def render_server(user_agent: str, query: str) -> SSRRenderResult:
        # Simulasi Server Render (Nitro Engine)
        server_timestamp = "2026-10-05T12:00:00.000Z"
        data_payload = {
            "title": "Enterprise Dashboard",
            "items": [f"Metric #{i}" for i in range(1, 4)],
            "renderedBy": "Nitro-V3-Edge",
            "timestamp": server_timestamp
        }
        
        # HTML output with hydration markers
        html = (
            f"<!--[nuxt-ssr-start]-->\n"
            f"<div id=\"__nuxt\">\n"
            f"  <header class=\"hero\"><h1>{data_payload['title']}</h1></header>\n"
            f"  <main data-testid=\"metrics\">\n"
            f"    <span class=\"server-time\">{data_payload['timestamp']}</span>\n"
            f"  </main>\n"
            f"</div>\n"
            f"<script>window.__NUXT__={data_payload}</script>\n"
            f"<!--[nuxt-ssr-end]-->"
        )
        return SSRRenderResult(html=html, server_time=server_timestamp, client_payload=data_payload)

    @staticmethod
    def simulate_client_hydration(ssr: SSRRenderResult, induce_mismatch: bool = False) -> bool:
        print(f"\n{YELLOW}[HYDRATION]{RESET} Memulai Client-Side Hydration pada VDOM...")
        time.sleep(0.3)
        client_time = "2026-10-05T12:00:01.240Z" if induce_mismatch else ssr.server_time
        
        print(f"  {BLUE}→{RESET} Server Virtual DOM : <span class='server-time'>{ssr.server_time}</span>")
        print(f"  {BLUE}→{RESET} Client Virtual DOM : <span class='server-time'>{client_time}</span>")
        
        if ssr.server_time != client_time:
            print(f"\n{BG_RED}{WHITE}{BOLD} [HYDRATION MISMATCH DETECTED] {RESET}")
            print(f"{RED}Error: Server rendered timestamp ({ssr.server_time}) does not match client evaluation ({client_time}).{RESET}")
            print(f"{YELLOW}Solusi Rekayasa Nuxt 3:{RESET}")
            print(f"  1. Gunakan `<ClientOnly>` untuk konten berbasis browser-time.")
            print(f"  2. Gunakan `useState()` untuk memastikan state diserialisasi ke `window.__NUXT__`.")
            print(f"  3. Hindari `Date.now()` langsung di template tanpa hydration sync guard.\n")
            return False
        else:
            print(f"\n{GREEN}{BOLD}✓ Hydration Sempurna!{RESET} Server HTML diadopsi tanpa repaint atau tree tearing.")
            return True


# -----------------------------------------------------------------------------
# 2. Cross-Request State Pollution Isolation
# -----------------------------------------------------------------------------
class SafeSSRStoreManager:
    """Simulasi proteksi cross-request state pollution dalam SSR"""
    def __init__(self):
        # Global variable unsafe pattern simulation vs SSR context-safe pattern
        self.unsafe_global_state = {"user_id": None, "session_token": None}
        self.request_contexts: Dict[str, Dict[str, Any]] = {}

    def simulate_unsafe_leak(self, req1_user: str, req2_user: str):
        print(f"\n{RED}[UNSAFE PATTERN]{RESET} Menggunakan Singleton Global Variable di Module Level:")
        # Request 1 arrives
        self.unsafe_global_state["user_id"] = req1_user
        print(f"  {RED}Req 1{RESET} (User: {req1_user}) set state.user_id = {req1_user}")
        
        # Async delay where Request 2 interleaves before Request 1 finishes response
        self.unsafe_global_state["user_id"] = req2_user
        print(f"  {RED}Req 2{RESET} (User: {req2_user}) mengintervensi set state.user_id = {req2_user}")
        
        print(f"  {RED}Req 1{RESET} merender response dengan state.user_id = {BOLD}{self.unsafe_global_state['user_id']}{RESET}")
        if self.unsafe_global_state["user_id"] != req1_user:
            print(f"  {BG_RED}{WHITE}{BOLD} CRITICAL DATA LEAK! {RESET} User {req1_user} melihat data user {req2_user}!\n")

    def simulate_safe_pinia_ssr(self, req_id: str, user_id: str):
        # Safe pattern: per-request SSR context via useState / createPinia() per request
        ctx = {"request_id": req_id, "user_id": user_id, "created_at": time.time()}
        self.request_contexts[req_id] = ctx
        print(f"  {GREEN}[SAFE SSR]{RESET} Request {req_id} diisolasi dalam EventContext Nuxt: user={user_id}")
        return ctx


# -----------------------------------------------------------------------------
# 3. SWR (Stale-While-Revalidate) & Edge Cache Engine
# -----------------------------------------------------------------------------
@dataclass
class CacheEntry:
    content: str
    cache_tags: List[str]
    created_at: float
    max_age: float
    stale_age: float


class EdgeSWREngine:
    def __init__(self):
        self.storage: Dict[str, CacheEntry] = {}

    def set(self, route: str, content: str, tags: List[str], max_age: float = 2.0, stale_age: float = 5.0):
        self.storage[route] = CacheEntry(
            content=content,
            cache_tags=tags,
            created_at=time.time(),
            max_age=max_age,
            stale_age=stale_age
        )

    def fetch(self, route: str) -> (str, str):
        now = time.time()
        entry = self.storage.get(route)
        if not entry:
            return "MISS", "Rendered fresh from Origin SSR"
        
        age = now - entry.created_at
        if age < entry.max_age:
            return "HIT", entry.content
        elif age < (entry.max_age + entry.stale_age):
            # Background revalidation trigger
            entry.created_at = now
            return "STALE-HIT (SWR Triggered Revalidate)", entry.content
        else:
            return "EXPIRED", "Rendered fresh from Origin SSR"

    def purge_by_tag(self, tag: str) -> int:
        purged = 0
        to_del = []
        for route, entry in self.storage.items():
            if tag in entry.cache_tags:
                to_del.append(route)
        for r in to_del:
            del self.storage[r]
            purged += 1
        return purged


# -----------------------------------------------------------------------------
# 4. Production Hardening & CSP Nonce Generator
# -----------------------------------------------------------------------------
class SecurityProductionHardener:
    @staticmethod
    def generate_csp_headers() -> Dict[str, str]:
        # Cryptographic nonce for inline Nuxt scripts
        raw_nonce = f"{random.randint(100000, 999999)}-{time.time()}"
        nonce = hashlib.sha256(raw_nonce.encode()).hexdigest()[:24]
        
        csp_policy = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data: https:; "
            f"connect-src 'self' https://api.production.internal; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self';"
        )
        return {
            "Content-Security-Policy": csp_policy,
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Nonce": nonce
        }


# -----------------------------------------------------------------------------
# Interactive CLI Workflow
# -----------------------------------------------------------------------------
def run_interactive_lab():
    print_banner()
    swr = EdgeSWREngine()
    swr.set("/products/42", "<html>[Products Page Body v1]</html>", tags=["product", "product-42"])
    swr.set("/categories/tech", "<html>[Tech Catalog Body v1]</html>", tags=["catalog", "product-42"])
    
    store_mgr = SafeSSRStoreManager()
    
    while True:
        print(f"\n{BOLD}Pilih Modul Simulasi Produksi Nuxt 3:{RESET}")
        print(f" {CYAN}1.{RESET} Simulasi Hydration & Deteksi Hydration Mismatch")
        print(f" {CYAN}2.{RESET} Simulasi Cross-Request State Pollution (Security Bug vs Isolated Context)")
        print(f" {CYAN}3.{RESET} Simulasi Edge SWR Caching & Tag-Based Invalidation")
        print(f" {CYAN}4.{RESET} Simulasi Strict CSP Nonce Injection & Production Header Audit")
        print(f" {CYAN}5.{RESET} Jalankan Automated Full Production Health Check")
        print(f" {CYAN}0.{RESET} Keluar")
        
        try:
            choice = input(f"\n{BOLD}Masukkan pilihan [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab...")
            break
            
        if choice == "0":
            print(f"{GREEN}Lab selesai. Sampai jumpa di arsitektur produksi!{RESET}")
            break
            
        elif choice == "1":
            print(f"\n{MAGENTA}{BOLD}--- [1] Hydration Mismatch Diagnostic Lab ---{RESET}")
            res = NuxtHydrationEngine.render_server("Mozilla/5.0", "q=enterprise")
            print(f"{DIM}Server SSR Output Preview:{RESET}\n{res.html[:160]}...\n")
            
            sub = input(f"Simulasikan mismatch sengaja? ({BOLD}y/N{RESET}): ").strip().lower()
            induce = (sub == 'y')
            NuxtHydrationEngine.simulate_client_hydration(res, induce_mismatch=induce)
            
        elif choice == "2":
            print(f"\n{MAGENTA}{BOLD}--- [2] Cross-Request State Pollution Test ---{RESET}")
            store_mgr.simulate_unsafe_leak("Alice_Admin", "Bob_Attacker")
            
            print(f"{GREEN}{BOLD}Solusi Produksi:{RESET} Menggunakan `useState()` / SSR Context per Request:")
            store_mgr.simulate_safe_pinia_ssr("req_9011_alice", "Alice_Admin")
            store_mgr.simulate_safe_pinia_ssr("req_9012_bob", "Bob_Attacker")
            print(f"{GREEN}✓ State antar concurrent request terisolasi sempurna.{RESET}")
            
        elif choice == "3":
            print(f"\n{MAGENTA}{BOLD}--- [3] Nitro SWR & Cache-Tags Purge ---{RESET}")
            status, body = swr.fetch("/products/42")
            print(f"Fetch #1 `/products/42` -> Status: {GREEN}{status}{RESET}")
            
            print(f"{DIM}Menunggu 2.2 detik agar cache masuk ke jendela STALE...{RESET}")
            time.sleep(2.2)
            
            status, body = swr.fetch("/products/42")
            print(f"Fetch #2 `/products/42` -> Status: {YELLOW}{status}{RESET}")
            
            print(f"\nMelakukan Cache Purge dengan tag {BOLD}'product-42'{RESET}:")
            count = swr.purge_by_tag("product-42")
            print(f"{CYAN}Purged {count} entries dari edge cache.{RESET}")
            
            status, body = swr.fetch("/products/42")
            print(f"Fetch #3 `/products/42` setelah purge -> Status: {RED}{status}{RESET}")
            
        elif choice == "4":
            print(f"\n{MAGENTA}{BOLD}--- [4] Strict CSP & Production Header Hardening ---{RESET}")
            sec = SecurityProductionHardener.generate_csp_headers()
            for header, val in sec.items():
                if header == "Nonce":
                    continue
                print(f" {GREEN}✓{RESET} {BOLD}{header}{RESET}: {CYAN}{val}{RESET}")
            print(f"\n{YELLOW}Injecting Dynamic Script Tag in Nuxt template:{RESET}")
            print(f" <script nonce=\"{sec['Nonce']}\">")
            print(f"   window.__NUXT_INIT__ = true;")
            print(f" </script>")
            print(f"{GREEN}Script lolos validasi Content-Security-Policy browser.{RESET}")
            
        elif choice == "5":
            print(f"\n{BG_GREEN}{WHITE}{BOLD} RUNNING AUTOMATED PRODUCTION HEALTH AUDIT {RESET}")
            time.sleep(0.3)
            print(f" [PASS] Memory leak check: Zero long-lived event listeners on SSR server")
            print(f" [PASS] Telemetry disabled: nuxt.config.ts telemetry=false")
            print(f" [PASS] Cross-Request Pollution: Isolated Pinia root instance initialized")
            print(f" [PASS] Compression: Gzip & Brotli pre-compression generated by Nitro")
            print(f" [PASS] Bundle analyzer: Chunks < 150KB, Vendor split verified")
            print(f"{GREEN}{BOLD}Status: READY FOR HIGH-CONCURRENCY PRODUCTION DEPLOYMENT!{RESET}\n")
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 0-5.{RESET}")


if __name__ == "__main__":
    run_interactive_lab()
