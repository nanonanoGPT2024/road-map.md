#!/usr/bin/env python3
"""
Simulasi Arsitektur Next.js App Router (RSC, Hydration, Streaming, & Server Actions)
Bab 03: Meta-Frameworks Next.js App Router
Lab Hands-on Mandiri M01
"""

import sys
import time
import json
import uuid
from typing import Dict, List, Any, Optional

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
BG_DARK = "\033[40m"


class ServerDataStore:
    """Mock Database & Server-side Cache Layer."""
    def __init__(self):
        self.products = [
            {"id": "p-101", "name": "Next.js Mastery Course", "stock": 14, "views": 1200},
            {"id": "p-102", "name": "Rust for Web Engineers", "stock": 8, "views": 840},
            {"id": "p-103", "name": "Distributed Systems Handbook", "stock": 25, "views": 3100},
        ]
        self.data_cache: Dict[str, Any] = {}
        self.tag_cache: Dict[str, List[str]] = {}

    def fetch_products(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        cache_key = "query:products"
        if use_cache and cache_key in self.data_cache:
            return self.data_cache[cache_key]
        time.sleep(0.3)  # Simulasi network / DB latency
        self.data_cache[cache_key] = [dict(p) for p in self.products]
        return self.data_cache[cache_key]

    def mutate_product(self, prod_id: str, new_stock: int) -> bool:
        for p in self.products:
            if p["id"] == prod_id:
                p["stock"] = new_stock
                # Cache invalidation (revalidatePath / revalidateTag)
                self.revalidate_path("/products")
                return True
        return False

    def revalidate_path(self, path: str):
        if path == "/products" and "query:products" in self.data_cache:
            del self.data_cache["query:products"]


db = ServerDataStore()


def print_banner():
    print(f"\n{BG_BLUE}{WHITE}{BOLD} ======================================================== {RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD}    NEXT.JS APP ROUTER RUNTIME ARCHITECTURE SIMULATOR    {RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD} ======================================================== {RESET}")
    print(f"{CYAN}Eksplorasi Interaktif: RSC Payload, Hydration, Streaming, & Server Actions{RESET}\n")


def simulate_rsc_render():
    print(f"\n{BOLD}{MAGENTA}[1] SIMULASI RENDER TREE (Server Component vs Client Component){RESET}")
    print(f"{DIM}Request masuk: GET /products (Next.js server-side flight render){RESET}\n")

    time.sleep(0.2)
    print(f" {BLUE}--> [Server Component]{RESET} RootLayout: Rendering server shell...")
    print(f" {BLUE}--> [Server Component]{RESET} ProductsPage: Mengambil data langsung dari DB (Zero client JS bundle)...")
    
    start_t = time.time()
    products = db.fetch_products(use_cache=True)
    fetch_ms = int((time.time() - start_t) * 1000)
    print(f"     {GREEN}✓ Data fetched ({len(products)} item) dalam {fetch_ms}ms{RESET}")

    # Serialized RSC payload
    flight_payload = [
        {"type": "layout", "runtime": "server", "tag": "RootLayout"},
        {"type": "page", "runtime": "server", "tag": "ProductsPage", "items": len(products)},
        {"type": "component", "runtime": "client", "tag": "ProductCounterButton", "module": "ProductCounter.client.js", "props": {"initial": 0}},
        {"type": "component", "runtime": "client", "tag": "BuyButton", "module": "BuyButton.client.js", "props": {"action": "serverAction$buy"}}
    ]

    print(f"\n{YELLOW}--- RSC Flight Wire Format (Streaming Payload) ---{RESET}")
    for item in flight_payload:
        rt_badge = f"{GREEN}[SERVER]{RESET}" if item["runtime"] == "server" else f"{CYAN}[CLIENT-SLOT]{RESET}"
        print(f" {rt_badge} {item['tag']:22} | Ref: {item.get('module', 'inline-rsc')}")
    
    print(f"\n{GREEN}Keunggulan RSC:{RESET} Server component code tidak pernah terkirim ke browser. Ukuran bundle JS browser tetap minimal!")


def simulate_streaming_suspense():
    print(f"\n{BOLD}{MAGENTA}[2] SIMULASI STREAMING SSR DENGAN SUSPENSE BOUNDARY{RESET}")
    print(f"{DIM}GET /dashboard (Layout instan + Slot lambat di-stream progresif){RESET}\n")

    print(f"[{GREEN}CHUNK 0{RESET}] Mengirim HTML Frame Dasar + Static Layout...")
    print(f"  {CYAN}<html><body><nav>Dashboard Nav</nav><div id='suspense-root'>Loading Skeleton...</div>{RESET}")
    sys.stdout.flush()

    time.sleep(0.6)
    print(f"[{GREEN}CHUNK 1{RESET}] Stream Slot Instan: QuickStatsComponent (Database cache hit)")
    print(f"  {CYAN}<script>self.__next_f.push(['$Stats', '{{ sales: 42, activeUsers: 1580 }}'])</script>{RESET}")
    sys.stdout.flush()

    time.sleep(1.0)
    print(f"[{GREEN}CHUNK 2{RESET}] Stream Slow Slot (Suspense Resolve): HeavyAnalyticsChart (Microservice finish)")
    print(f"  {CYAN}<template id='B:1'><div>Rendered Visual Chart [4.2k Data Points]</div></template>{RESET}")
    print(f"  {GREEN}✓ Browser mengganti Skeleton loader dengan template utuh tanpa page reload.{RESET}\n")


def simulate_server_actions():
    print(f"\n{BOLD}{MAGENTA}[3] SIMULASI SERVER ACTIONS & OPTIMISTIC UI{RESET}")
    products = db.fetch_products(use_cache=True)
    target = products[0]

    print(f"Target Produk: {YELLOW}{target['name']}{RESET}")
    print(f"Stock saat ini di Server: {GREEN}{target['stock']}{RESET}")
    
    delta = -1
    print(f"\n{CYAN}[Client Event]{RESET} User mengklik tombol 'Buy Now'.")
    print(f"{CYAN}[Optimistic UI]{RESET} Tampilan stock di browser langsung berubah: {target['stock']} -> {target['stock'] + delta} (0ms latency visual)")

    print(f"{YELLOW}[Server Action Invocation]{RESET} POST /products?_rsc_action=serverAction$buy")
    print(f" {DIM}Menjalankan logika aman di server (verifikasi sesi auth, DB transaction)...{RESET}")
    time.sleep(0.4)

    success = db.mutate_product(target["id"], target["stock"] + delta)
    if success:
        print(f" {GREEN}✓ Server Action Sukses!{RESET} Mutasi database tersimpan.")
        print(f" {MAGENTA}⚡ revalidatePath('/products'){RESET} membuang stale Data Cache di server.")
    else:
        print(f" {RED}✗ Mutasi gagal.{RESET} Optimistic UI di browser melakukan rollback!")

    updated = [p for p in db.products if p["id"] == target["id"]][0]
    print(f"Status Final Data Server: {GREEN}{updated['stock']} units tersisa.{RESET}\n")


def inspect_cache_layers():
    print(f"\n{BOLD}{MAGENTA}[4] INSPEKSI NEXT.JS 4-TIER CACHING BEHAVIOR{RESET}")
    table_data = [
        ("1. Request Memoization", "React Server Component", "Per-request lifecycle", "Deduplikasi fetch identik"),
        ("2. Data Cache", "Next.js Server", "Cross-request & Per-tag", "Menyimpan response fetch() ke disk/memory"),
        ("3. Full Route Cache", "Next.js Server", "Persistent HTML & RSC", "Static Site Generation (SSG) output"),
        ("4. Router Cache", "Browser Client", "In-memory session", "Menyimpan RSC payload per segment route"),
    ]
    print(f"{BOLD}{'Layer Caching':25} | {'Lokasi':22} | {'Durasi':22} | {'Fungsi Utama'}{RESET}")
    print("-" * 95)
    for name, loc, dur, desc in table_data:
        print(f"{CYAN}{name:25}{RESET} | {WHITE}{loc:22}{RESET} | {YELLOW}{dur:22}{RESET} | {desc}")
    print()


def interactive_menu():
    while True:
        print_banner()
        print(f"{BOLD}Pilih Modul Simulasi:{RESET}")
        print(f" {GREEN}[1]{RESET} Render Tree: React Server Components (RSC) vs Client Components")
        print(f" {GREEN}[2]{RESET} Streaming SSR & Suspense Progressive Hydration")
        print(f" {GREEN}[3]{RESET} Server Actions, Optimistic UI, & Cache Revalidation")
        print(f" {GREEN}[4]{RESET} Diagnostik 4-Tier Caching System Next.js")
        print(f" {GREEN}[5]{RESET} Jalankan Seluruh Pipeline Simulasi (Full Demo)")
        print(f" {RED}[0]{RESET} Keluar (Exit)")
        
        choice = input(f"\n{BOLD}{WHITE}Masukkan nomor pilihan [0-5]: {RESET}").strip()
        
        if choice == "1":
            simulate_rsc_render()
        elif choice == "2":
            simulate_streaming_suspense()
        elif choice == "3":
            simulate_server_actions()
        elif choice == "4":
            inspect_cache_layers()
        elif choice == "5":
            simulate_rsc_render()
            simulate_streaming_suspense()
            simulate_server_actions()
            inspect_cache_layers()
        elif choice == "0":
            print(f"\n{GREEN}Selesai. Terus eksplorasi fondasi modern Next.js App Router!{RESET}\n")
            break
        else:
            print(f"\n{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")
        
        input(f"{DIM}Tekan [Enter] untuk kembali ke menu...{RESET}")


if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Simulasi dihentikan oleh user.{RESET}\n")
        sys.exit(0)
