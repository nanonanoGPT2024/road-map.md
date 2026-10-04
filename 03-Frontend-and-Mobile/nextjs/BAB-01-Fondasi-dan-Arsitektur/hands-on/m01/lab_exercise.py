#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi & Arsitektur Inti Next.js
BAB-01: Fondasi dan Arsitektur Next.js (App Router, RSC, Rendering Modes & Hydration)

Simulasi mandiri interaktif menggunakan Python 3 murni tanpa dependensi eksternal.
Menjelaskan mekanisme internal:
1. File-system Routing & Nested Layout Hierarchy
2. Server vs Client Component Boundary & RSC Payload Serialization
3. Rendering Strategies Pipeline (SSR, SSG, ISR, Streaming / Suspense)
4. Client-side Hydration Phase
"""

import sys
import time
import json
import random
from typing import Dict, Any, List

# --- ANSI Terminal Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Colors
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    WHITE = "\033[37m"
    
    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


def header(title: str) -> None:
    print(f"\n{Style.BOLD}{Style.BG_BLUE}{Style.WHITE} === {title.upper()} === {Style.RESET}\n")


def subheader(title: str) -> None:
    print(f"{Style.BOLD}{Style.CYAN}▶ {title}{Style.RESET}")


def log_step(step: str, detail: str, delay: float = 0.05) -> None:
    print(f"  {Style.GREEN}✔{Style.RESET} {Style.BOLD}{step}{Style.RESET}: {Style.DIM}{detail}{Style.RESET}")
    if delay > 0:
        time.sleep(delay)


def log_chunk(chunk_id: str, content: str, latency_ms: int) -> None:
    print(f"  {Style.MAGENTA}[Chunk {chunk_id}]{Style.RESET} (+{latency_ms}ms) -> {content}")


# --- Simulasi Modul 1: App Router & Nested Layouts ---
def simulate_app_router() -> None:
    header("1. App Router: Nested Layout Resolution")
    route = "/dashboard/analytics"
    print(f"Menganalisis URL Request: {Style.YELLOW}{route}{Style.RESET}\n")

    layout_tree = [
        {"file": "app/layout.tsx", "scope": "Root Layout (<html>, <body>, Navbar Global)", "type": "RSC"},
        {"file": "app/dashboard/layout.tsx", "scope": "Dashboard Layout (Sidebar, UserContext)", "type": "RSC"},
        {"file": "app/dashboard/analytics/page.tsx", "scope": "Leaf Page (Metric Cards, Chart)", "type": "Mixed"}
    ]

    print(f"{Style.BOLD}Membangun Pohon Komposisi Komponen:{Style.RESET}")
    indent = ""
    for level in layout_tree:
        badge = f"{Style.BG_MAGENTA}{Style.WHITE} {level['type']} {Style.RESET}"
        print(f"{indent}└── {Style.BOLD}{level['file']}{Style.RESET} {badge}")
        print(f"{indent}    {Style.DIM}Peran: {level['scope']}{Style.RESET}")
        indent += "    "
        time.sleep(0.08)
    
    print(f"\n{Style.GREEN}Hasil:{Style.RESET} Next.js membungkus Page ke dalam DashboardLayout, lalu RootLayout tanpa re-render induk saat navigasi child.")


# --- Simulasi Modul 2: RSC vs Client Component Boundary ---
def simulate_rsc_payload() -> None:
    header("2. RSC Wire Format & Component Boundary Serialization")
    print("Mengeksekusi komponen di Server Node.js runtime...\n")

    log_step("Server Component", "UserHeader (RSC) membaca data langsung dari database/filesystem tanpa expose credentials.")
    log_step("Client Component", "InteractiveCounter ('use client') ditandai sebagai client reference placeholder.")

    rsc_payload: List[Dict[str, Any]] = [
        {"id": "c1", "type": "header", "props": {"title": "Production Analytics", "serverTime": time.strftime("%Y-%m-%dT%H:%M:%SZ")}},
        {"id": "c2", "type": "$L_ClientModuleRef", "module": "./components/InteractiveCounter.client.js", "props": {"initialCount": 42}},
        {"id": "c3", "type": "footer", "props": {"copy": "© 2026 Next.js Enterprise Hub"}}
    ]

    print(f"\n{Style.CYAN}--- Raw Streamed Flight Data (RSC Payload Protocol) ---{Style.RESET}")
    for item in rsc_payload:
        serialized = json.dumps(item)
        print(f"{Style.DIM}M: {item['id']}:{Style.RESET} {serialized}")
        time.sleep(0.06)
    
    print(f"\n{Style.YELLOW}Catatan Arsitektur:{Style.RESET} Kode JS untuk 'header' dan 'footer' {Style.BOLD}TIDAK DIKIRIM{Style.RESET} ke bundle browser! Hanya referensi client component yang membebani bundle JS.")


# --- Simulasi Modul 3: Rendering Pipelines (SSG, SSR, ISR, Streaming) ---
def simulate_rendering_strategies() -> None:
    header("3. Rendering Strategies Engine: SSG, SSR, ISR, Streaming")

    strategies = [
        {"name": "SSG (Static Site Generation)", "ttfb": "5ms (CDN Edge Hit)", "desc": "Prerender saat build time (output: HTML + JSON static)."},
        {"name": "SSR (Server-Side Rendering)", "ttfb": "95ms (On-Demand Compute)", "desc": "Dihasilkan secara dinamis tiap request via dynamic functions (cookies, headers)."},
        {"name": "ISR (Incremental Static Reg.)", "ttfb": "10ms (Stale-While-Revalidate)", "desc": "Sajikan cache lama, trigger background rebuild jika revalidate period habis."},
        {"name": "Streaming SSR (Suspense)", "ttfb": "18ms (Progressive HTML Chunks)", "desc": "Kirim shell UI instan, stream data lambat via React Suspense boundary."}
    ]

    for st in strategies:
        print(f"{Style.BOLD}• {st['name']}{Style.RESET}")
        print(f"  {Style.DIM}Karakteristik : {st['desc']}{Style.RESET}")
        print(f"  {Style.GREEN}Latency TTFB  : {st['ttfb']}{Style.RESET}\n")
        time.sleep(0.08)

    subheader("Simulasi Streaming HTML & Suspense Boundary:")
    print("Membuka HTTP Connection (Transfer-Encoding: chunked)...")
    
    log_chunk("0", "<html><head>...</head><body><div id='shell'>Loading Layout...</div>", 15)
    log_chunk("1", "<div id='user-profile'>Halo, Engineer Team!</div>", 40)
    print(f"  {Style.YELLOW}⏳ Suspense fallback aktif: <SkeletonChart />...{Style.RESET}")
    time.sleep(0.2)
    log_chunk("2", "<div id='heavy-analytics-chart'><svg>Rendered 100K Points</svg></div>", 320)
    log_chunk("3", "<script>__next_f.push(['hydration-complete'])</script></body></html>", 10)
    print(f"\n{Style.GREEN}✔ Streaming selesai! FCP (First Contentful Paint) tercapai sebelum query database berat usai.{Style.RESET}")


# --- Simulasi Modul 4: Client Hydration ---
def simulate_hydration() -> None:
    header("4. Client-side Hydration Phase")
    print("Browser menerima HTML statis + RSC Payload + Client Component JS Bundles.\n")

    steps = [
        ("DOM Parsing", "Browser merekonstruksi DOM node dari HTML stream."),
        ("Flight Parser", "Next.js runtime membaca stream RSC payload untuk merajut Virtual DOM."),
        ("Event Attachment", "React memasang Event Listener (onClick, onChange) ke komponen 'use client'."),
        ("Interactive State", "Hydration rampung. Web app bertransisi mulus menjadi Single Page Application (SPA).")
    ]

    for idx, (action, detail) in enumerate(steps, start=1):
        log_step(f"Tahap {idx} - {action}", detail, delay=0.1)

    print(f"\n{Style.BOLD}{Style.GREEN}Status: APLIKASI SEPENUHNYA INTERAKTIF (Zero Mismatch Error){Style.RESET}")


# --- CLI Interactive Controller ---
def display_menu() -> None:
    print(f"\n{Style.BOLD}{Style.WHITE}Pilih Modul Simulasi:{Style.RESET}")
    print(f"  {Style.CYAN}1.{Style.RESET} App Router & Nested Layout Hierarchy")
    print(f"  {Style.CYAN}2.{Style.RESET} RSC Wire Format vs Client Component Boundary")
    print(f"  {Style.CYAN}3.{Style.RESET} Rendering Strategies (SSG, SSR, ISR & Streaming)")
    print(f"  {Style.CYAN}4.{Style.RESET} Client Hydration Lifecycle")
    print(f"  {Style.CYAN}5.{Style.RESET} Jalankan Seluruh Pipeline Arsitektur (E2E Flow)")
    print(f"  {Style.RED}0.{Style.RESET} Keluar\n")


def main() -> None:
    print(f"{Style.BOLD}{Style.BG_CYAN}{Style.WHITE} LABORATORIUM ARSITEKTUR CORE NEXT.JS - BAB 01 {Style.RESET}")
    print(f"{Style.DIM}Simulasi Mekanisme Internal App Router, RSC, dan Rendering Pipeline{Style.RESET}\n")

    # Jika dijalankan non-interaktif (piped atau scripted), jalankan demo penuh
    if not sys.stdin.isatty():
        simulate_app_router()
        simulate_rsc_payload()
        simulate_rendering_strategies()
        simulate_hydration()
        print(f"\n{Style.BOLD}{Style.GREEN}✔ Eksekusi simulasi non-interaktif selesai dengan sukses.{Style.RESET}\n")
        return

    while True:
        display_menu()
        try:
            choice = input(f"{Style.BOLD}Pilihan Anda (0-5): {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Sesi ditutup.{Style.RESET}")
            break

        if choice == "1":
            simulate_app_router()
        elif choice == "2":
            simulate_rsc_payload()
        elif choice == "3":
            simulate_rendering_strategies()
        elif choice == "4":
            simulate_hydration()
        elif choice == "5":
            simulate_app_router()
            simulate_rsc_payload()
            simulate_rendering_strategies()
            simulate_hydration()
        elif choice == "0":
            print(f"{Style.GREEN}Terima kasih! Sesi simulasi lab selesai.{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid. Silakan masukkan angka 0 - 5.{Style.RESET}")


if __name__ == "__main__":
    main()
