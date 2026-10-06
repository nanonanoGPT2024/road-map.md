#!/usr/bin/env python3
"""
Simulasi Interaktif: Angular Server-Side Rendering (SSR), Prerendering, & Hydration
BAB-09: Rendering Sisi Server, Prerendering, dan Hydration

Modul ini mendemonstrasikan secara visual cara kerja:
1. Prerendering (SSG) & Route Parameter Scraping
2. Server-Side Rendering (SSR) dinamis via mock CommonEngine
3. TransferState Mechanism (Eliminasi Double-Fetching)
4. Non-Destructive Hydration & Hydration Mismatch Detection
5. Event Replay Mechanism (Browser event queueing sebelum Angular siap)
"""

import sys
import time
import json
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

def print_header(title: str):
    width = 72
    print(f"\n{Style.BRIGHT_CYAN}{'═' * width}{Style.RESET}")
    print(f"{Style.BOLD}{Style.BRIGHT_WHITE}  {title.center(width - 4)}{Style.RESET}")
    print(f"{Style.BRIGHT_CYAN}{'═' * width}{Style.RESET}\n")

def print_step(step_num: int, label: str):
    print(f"{Style.BRIGHT_YELLOW}[TAHAP {step_num}]{Style.RESET} {Style.BOLD}{label}{Style.RESET}")

def print_info(tag: str, msg: str, color: str = Style.CYAN):
    print(f"  {color}❯ [{tag}]{Style.RESET} {msg}")

def print_success(tag: str, msg: str):
    print(f"  {Style.BRIGHT_GREEN}✔ [{tag}]{Style.RESET} {msg}")

def print_warning(tag: str, msg: str):
    print(f"  {Style.BRIGHT_YELLOW}▲ [{tag}]{Style.RESET} {msg}")

def print_error(tag: str, msg: str):
    print(f"  {Style.BRIGHT_RED}✖ [{tag}]{Style.RESET} {msg}")

# --- Data Models & Simulator Classes ---

@dataclass
class DomNode:
    tag: str
    attributes: Dict[str, str] = field(default_factory=dict)
    text_content: str = ""
    children: List['DomNode'] = field(default_factory=list)
    ng_reflect_id: Optional[str] = None
    hydrated: bool = False

    def to_html(self, indent: int = 0) -> str:
        pad = "  " * indent
        attrs = " ".join([f'{k}="{v}"' for k, v in self.attributes.items()])
        if self.ng_reflect_id:
            attrs += f' ng-reflect-id="{self.ng_reflect_id}"'
        attrs = (" " + attrs) if attrs.strip() else ""
        
        if not self.children and not self.text_content:
            return f"{pad}<{self.tag}{attrs} />"
        
        if not self.children:
            return f"{pad}<{self.tag}{attrs}>{self.text_content}</{self.tag}>"
        
        inner = "\n".join([c.to_html(indent + 1) for c in self.children])
        if self.text_content:
            inner = f"{pad}  {self.text_content}\n" + inner
        return f"{pad}<{self.tag}{attrs}>\n{inner}\n{pad}</{self.tag}>"

class MockTransferState:
    def __init__(self):
        self._store: Dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self._store[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def has_key(self, key: str) -> bool:
        return key in self._store

    def serialize(self) -> str:
        return json.dumps(self._store)

    def hydrate_from_json(self, json_str: str):
        self._store = json.loads(json_str)

@dataclass
class QueuedEvent:
    target_selector: str
    event_name: str
    timestamp: float
    handled: bool = False

class AngularHydrationEngine:
    def __init__(self):
        self.transfer_state = MockTransferState()
        self.server_dom_tree: Optional[DomNode] = None
        self.client_event_queue: List[QueuedEvent] = []

    def mock_fetch_api_products(self) -> List[Dict[str, Any]]:
        time.sleep(0.3)  # Simulasi latency DB/API
        return [
            {"id": "ng-101", "name": "Angular Masterclass Book", "price": 450000, "stock": 14},
            {"id": "ng-102", "name": "Enterprise Architecture Guide", "price": 620000, "stock": 8},
            {"id": "ng-103", "name": "Fullstack Standalone Signals Pack", "price": 310000, "stock": 25},
        ]

    # 1. Prerendering (SSG)
    def run_prerender(self):
        print_header("1. SIMULASI PRERENDERING (STATIC SITE GENERATION / SSG)")
        print_info("BUILD", "Membaca static routes dari `angular.json` / `prerender: true`...")
        routes = ["/", "/about", "/faq", "/docs/installation"]
        
        for idx, route in enumerate(routes, 1):
            time.sleep(0.2)
            html_size = random.randint(18, 42)
            print_success(f"SSG-{idx}", f"Prerendered: {Style.BOLD}{route:<20}{Style.RESET} -> dist/browser{route}/index.html ({html_size} KB)")
        
        print_info("SUMMARY", "File HTML statis siap disajikan langsung dari Edge CDN / Nginx tanpa komputasi Node.js runtime.\n")

    # 2. Server-Side Rendering (SSR) Dinamis
    def run_ssr_dynamic(self, route: str = "/products") -> str:
        print_header("2. SIMULASI DYNAMIC SSR ENGINE (Node.js CommonEngine)")
        print_step(1, f"Menerima HTTP GET Request untuk URL: {Style.BRIGHT_MAGENTA}{route}{Style.RESET}")
        
        state_key = "PRODUCTS_API_DATA"
        print_info("PLATFORM_ID", "Eksekusi di lingkungan: isPlatformServer(platformId) = True")
        print_info("FETCH", "Mengambil data produk dari backend database via HttpClient...")
        
        products = self.mock_fetch_api_products()
        print_success("DATA_LOADED", f"Berhasil menarik {len(products)} records dari backend.")
        
        # Simpan ke TransferState
        self.transfer_state.set(state_key, products)
        print_info("TRANSFER_STATE", f"Menyimpan cache ke TransferState (Key: '{state_key}')")

        # Render Component Tree ke HTML DOM
        root = DomNode(tag="app-root", attributes={"ng-version": "18.2.0"})
        container = DomNode(tag="main", attributes={"class": "container-fluid"})
        header = DomNode(tag="h1", text_content="Katalog Produk Kursus Angular", ng_reflect_id="h1_0")
        container.children.append(header)

        list_node = DomNode(tag="ul", attributes={"class": "product-list"}, ng_reflect_id="ul_list")
        for i, item in enumerate(products):
            item_node = DomNode(
                tag="li",
                attributes={"class": "product-card"},
                ng_reflect_id=f"item_{i}",
                text_content=f"{item['name']} - Rp {item['price']:,} (Stok: {item['stock']})"
            )
            btn = DomNode(
                tag="button",
                attributes={"class": "btn-buy", "data-product-id": item["id"]},
                ng_reflect_id=f"btn_{i}",
                text_content="Beli Sekarang"
            )
            item_node.children.append(btn)
            list_node.children.append(item_node)
        
        container.children.append(list_node)
        root.children.append(container)
        self.server_dom_tree = root

        # Serialized HTML + Script tag transfer state
        html_markup = root.to_html(indent=1)
        transfer_script = f'  <script id="ng-state" type="application/json">\n    {self.transfer_state.serialize()}\n  </script>'
        full_html = f"<!DOCTYPE html>\n<html lang=\"id\">\n<head>\n  <title>SSR Angular Store</title>\n</head>\n<body>\n{html_markup}\n{transfer_script}\n</body>\n</html>"
        
        print_step(2, "SSR Berhasil Menghasilkan Markup HTML Lengkap dengan Embedded TransferState:")
        print(f"{Style.DIM}{full_html}{Style.RESET}\n")
        return full_html

    # 3. Non-Destructive Hydration & Event Replay
    def run_client_hydration(self, trigger_mismatch: bool = False):
        print_header("3. SIMULASI HYDRATION SISI KLIEN (provideClientHydration)")
        print_step(1, "Browser menerima HTML server & memuat bundle runtime JavaScript Angular...")
        print_info("FCP", "First Contentful Paint (FCP) tercapai langsung! User melihat teks & UI tanpa layar putih.")

        # Simulasi aksi user mengklik tombol sebelum JS selesai booting (Event Replay)
        print_step(2, "Simulasi Event Replay: Pengguna mengklik tombol beli saat Angular JS masih loading...")
        ev1 = QueuedEvent(target_selector="button[data-product-id='ng-101']", event_name="click", timestamp=time.time())
        self.client_event_queue.append(ev1)
        print_warning("EVENT_BUFFER", f"Event '{ev1.event_name}' pada '{ev1.target_selector}' ditangkap oleh pre-bootstrap event listener dan diantrikan.")

        # Hydrate TransferState
        print_step(3, "Angular Client Initializing: Membaca script #ng-state untuk TransferState...")
        client_state = MockTransferState()
        state_key = "PRODUCTS_API_DATA"
        serialized = self.transfer_state.serialize()
        client_state.hydrate_from_json(serialized)
        
        if client_state.has_key(state_key):
            cached_data = client_state.get(state_key)
            print_success("NO_DOUBLE_FETCH", f"TransferState ditemukan! Memakai {len(cached_data)} data cache. TIDAK ADA HTTP request ulang ke server!")
        else:
            print_error("CACHE_MISS", "TransferState kosong! Terjadi double-fetching ke server!")

        # DOM Reconciliation (Non-Destructive Hydration)
        print_step(4, "Non-Destructive Hydration: Pencocokan DOM Node Server vs VDOM Client...")
        
        if trigger_mismatch:
            print_warning("INJECTING_BUG", "Mengaktifkan kondisi Hydration Mismatch: Browser mencoba merender tag berbeda!")
            client_dom_tag = "div"
            server_dom_tag = self.server_dom_tree.children[0].children[0].tag  # 'h1'
            print_error("MISMATCH_DETECTED", f"Hydration Mismatch Error (NG0500):")
            print(f"    Server rendered: <{server_dom_tag}>Katalog Produk Kursus Angular</{server_dom_tag}>")
            print(f"    Client expected: <{client_dom_tag}>Katalog Produk Kursus Angular</{client_dom_tag}>")
            print_info("FALLBACK", "Angular terpaksa menghancurkan DOM dan merender ulang dari awal (Destructive Re-render / Screen Flicker).\n")
            return

        # Pencocokan Sukses
        print_success("RECONCILE", "DOM Node server dipertahankan tanpa re-render (Zero DOM Flickering).")
        print_success("SIGNAL_ATTACH", "Reactive Signals dan Angular Event Listeners berhasil ditempelkan ke DOM yang sudah ada.")

        # Eksekusi Event Replay
        print_step(5, "Memutar kembali (Replaying) buffered events...")
        while self.client_event_queue:
            ev = self.client_event_queue.pop(0)
            time.sleep(0.2)
            print_success("EVENT_DISPATCHED", f"Event '{ev.event_name}' pada '{ev.target_selector}' berhasil dieksekusi oleh Component Handler!")
        
        print_info("STATUS", "Aplikasi kini 100% interaktif dan terhidrasi penuh!\n")

def run_interactive_suite():
    engine = AngularHydrationEngine()
    
    while True:
        print_header("MENU LAB EKSPLORASI: ANGULAR SSR, PRERENDER & HYDRATION")
        print(f" {Style.BRIGHT_GREEN}1.{Style.RESET} Jalankan Simulasi Prerendering (SSG Static Build)")
        print(f" {Style.BRIGHT_GREEN}2.{Style.RESET} Jalankan Dynamic SSR Server (RenderApplication + TransferState)")
        print(f" {Style.BRIGHT_GREEN}3.{Style.RESET} Jalankan Client Non-Destructive Hydration & Event Replay")
        print(f" {Style.BRIGHT_GREEN}4.{Style.RESET} Simulasikan Error Hydration Mismatch (NG0500)")
        print(f" {Style.BRIGHT_GREEN}5.{Style.RESET} Jalankan Full Pipeline (1 -> 2 -> 3)")
        print(f" {Style.BRIGHT_RED}0.{Style.RESET} Keluar")
        
        try:
            choice = input(f"\n{Style.BOLD}Pilih nomor menu (0-5) [default: 5]: {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "" or choice == "5":
            engine.run_prerender()
            engine.run_ssr_dynamic()
            engine.run_client_hydration(trigger_mismatch=False)
            break
        elif choice == "1":
            engine.run_prerender()
        elif choice == "2":
            engine.run_ssr_dynamic()
        elif choice == "3":
            if not engine.server_dom_tree:
                print_warning("NOTICE", "Menjalankan SSR terlebih dahulu agar DOM server tersedia...")
                engine.run_ssr_dynamic()
            engine.run_client_hydration(trigger_mismatch=False)
        elif choice == "4":
            if not engine.server_dom_tree:
                engine.run_ssr_dynamic()
            engine.run_client_hydration(trigger_mismatch=True)
        elif choice == "0":
            print("Sampai jumpa!")
            break
        else:
            print_error("INPUT", "Pilihan tidak valid, silakan coba lagi.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        eng = AngularHydrationEngine()
        eng.run_prerender()
        eng.run_ssr_dynamic()
        eng.run_client_hydration(trigger_mismatch=False)
        eng.run_client_hydration(trigger_mismatch=True)
    else:
        # Jalankan jika interactive TTY, atau auto-run jika pipe
        if sys.stdin.isatty():
            run_interactive_suite()
        else:
            eng = AngularHydrationEngine()
            eng.run_prerender()
            eng.run_ssr_dynamic()
            eng.run_client_hydration(trigger_mismatch=False)
