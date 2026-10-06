#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Paradigma Rendering Next.js App Router
BAB 03: React Server Components (RSC), Streaming Suspense, & Partial Prerendering (PPR)
"""

import sys
import time
import json
import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass

# ANSI Color Codes untuk visualisasi terminal
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background colors
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"


@dataclass
class ComponentNode:
    name: str
    component_type: str  # 'server' | 'client'
    fetch_latency_ms: int
    fallback_ui: str
    resolved_ui: str


def print_banner():
    banner = f"""
{Style.CYAN}{Style.BOLD}================================================================================
    NEXT.JS APP ROUTER: ARCHITECTURE & RENDERING ENGINE SIMULATOR
    BAB 03: RSC, Streaming with Suspense, & Partial Prerendering (PPR)
================================================================================{Style.RESET}
"""
    print(banner)


async def simulate_flight_protocol_generation():
    print(f"\n{Style.BOLD}{Style.BLUE}>>> [1] SIMULASI RSC FLIGHT PROTOCOL SERIALIZATION <<<{Style.RESET}")
    print(f"{Style.DIM}RSC tidak mengirimkan HTML mentah atau bundle JavaScript komponen server.{Style.RESET}")
    print(f"{Style.DIM}RSC menghasilkan representasi visual virtual JSON Stream (RSC Flight Payload).{Style.RESET}\n")

    flight_chunks = [
        ('1:I["app/components/header.client.js",["Header"],"default"]', "Client Component Reference Marker"),
        ('0:["$","div",null,{"className":"layout-container","children":["$L1",["$","$L2",null,{}]]}]', "Server Root Layout Wireframe"),
        ('2:{"name":"Navbar","user":{"id":101,"role":"admin"},"theme":"dark"}', "Client Component Props Serialized"),
        ('3:I["app/components/cart-badge.client.js",["CartBadge"],"Cart"]', "Client Interactive Boundary"),
        ('4:["$","main",null,{"children":[["$","h1",null,{"children":"Dashboard"}],["$","$L3",null,{"itemsCount":3}]]}]', "Resolved Server UI Node"),
    ]

    for line_id, (chunk, desc) in enumerate(flight_chunks, start=1):
        await asyncio.sleep(0.35)
        print(f"{Style.MAGENTA}[Flight Line {line_id}]{Style.RESET} {Style.WHITE}{chunk}{Style.RESET}")
        print(f"  {Style.GREEN}↳ Penjelasan:{Style.RESET} {Style.DIM}{desc}{Style.RESET}")

    print(f"\n{Style.GREEN}{Style.BOLD}✓ Zero-Bundle Overhead:{Style.RESET} Kode library seperti `markdown-parser` atau `db-driver`")
    print(f"  dieksekusi 100% di server, hanya tree data string di atas yang dikirim ke browser.")


async def simulate_streaming_suspense():
    print(f"\n{Style.BOLD}{Style.YELLOW}>>> [2] SIMULASI STREAMING SSR DENGAN SUSPENSE BOUNDARIES <<<{Style.RESET}")
    print(f"{Style.DIM}Server melakukan HTTP Chunked Transfer Encoding. Shell statis di-flush instan.{Style.RESET}\n")

    # Layout & Component definitions
    components = [
        ComponentNode("Sidebar & Navigation", "server", 50, "", "<nav>Links: [Home, Reports, Settings]</nav>"),
        ComponentNode("Header Shell", "server", 100, "", "<header><h1>Acme Cloud Console</h1></header>"),
        ComponentNode("UserProfileCard", "server", 400, "<div class='skeleton skeleton-user'>Loading profile...</div>", "<div class='user-card'>User: @alex (Tier: Pro Enterprise)</div>"),
        ComponentNode("RealtimeMetrics", "server", 950, "<div class='skeleton skeleton-chart'>Loading live metrics...</div>", "<div class='metrics'>QPS: 14,250 | Latency: 18ms | Errors: 0.00%</div>"),
        ComponentNode("InvoiceHistoryTable", "server", 1400, "<div class='skeleton skeleton-table'>Generating ledger items...</div>", "<table class='invoices'><tr><td>INV-2026-001</td><td>$2,450.00 (Paid)</td></tr></table>"),
    ]

    start_time = time.time()

    # Step 1: Flush Shell Instan
    print(f"{Style.CYAN}[t=0ms] HTTP/1.1 200 OK | Transfer-Encoding: chunked{Style.RESET}")
    print(f"{Style.CYAN}[t=0ms] FLUSHING INITIAL HTML SHELL (Layout + Suspense Fallbacks):{Style.RESET}")
    
    html_shell = f"""
    <!DOCTYPE html>
    <html>
      <body>
        <div id="root">
          <div class="header">{components[1].resolved_ui}</div>
          <div class="sidebar">{components[0].resolved_ui}</div>
          <main>
            <!-- $Sreact.suspense (Profile) -->
            <div id="slot-profile">{components[2].fallback_ui}</div>
            <!-- $Sreact.suspense (Metrics) -->
            <div id="slot-metrics">{components[3].fallback_ui}</div>
            <!-- $Sreact.suspense (Invoices) -->
            <div id="slot-invoices">{components[4].fallback_ui}</div>
          </main>
        </div>
      </body>
    </html>
    """
    for line in html_shell.strip().split("\n"):
        print(f"  {Style.DIM}{line}{Style.RESET}")
    print(f"{Style.GREEN}>>> First Contentful Paint (FCP) tercapai instan tanpa blocking database query! <<<{Style.RESET}\n")

    # Step 2: Concurrent resolution task
    async def resolve_boundary(comp: ComponentNode, slot_id: str):
        await asyncio.sleep(comp.fetch_latency_ms / 1000.0)
        elapsed = int((time.time() - start_time) * 1000)
        print(f"{Style.YELLOW}[t={elapsed}ms STREAM CHUNK FLUSHED]{Style.RESET}")
        print(f"  {Style.BOLD}Boundary Resolved:{Style.RESET} {comp.name} (Latency: {comp.fetch_latency_ms}ms)")
        print(f"  {Style.MAGENTA}<template id=\"P:{slot_id}\">{comp.resolved_ui}</template>{Style.RESET}")
        print(f"  {Style.MAGENTA}<script>$RC('{slot_id}','P:{slot_id}')</script>{Style.RESET} {Style.DIM}/* React swap runtime */{Style.RESET}\n")

    tasks = [
        resolve_boundary(components[2], "slot-profile"),
        resolve_boundary(components[3], "slot-metrics"),
        resolve_boundary(components[4], "slot-invoices"),
    ]

    await asyncio.gather(*tasks)
    total_elapsed = int((time.time() - start_time) * 1000)
    print(f"{Style.GREEN}{Style.BOLD}✓ Semua Suspense boundaries ter-stream dan ter-resolve dalam {total_elapsed}ms.{Style.RESET}")


async def simulate_partial_prerender():
    print(f"\n{Style.BOLD}{Style.CYAN}>>> [3] SIMULASI PARTIAL PRERENDERING (PPR) NEXT.JS <<<{Style.RESET}")
    print(f"{Style.DIM}PPR menggabungkan kecepatan Static CDN (SSG) dengan dinamika Streaming SSR dalam 1 request.{Style.RESET}\n")

    print(f"{Style.WHITE}{Style.BOLD}[Fase 1: Build-Time (Next.js Static Generation)]{Style.RESET}")
    await asyncio.sleep(0.3)
    print(f"  {Style.BLUE}• Komponen Statis (Layout, Nav, Footer, Desain Skeleton) dikompilasi jadi HTML statis.{Style.RESET}")
    print(f"  {Style.BLUE}• Edge Prerender Hole dibuat pada batas <Suspense fallback={{...}}>...{Style.RESET}")
    print(f"  {Style.GREEN}✓ File prerender tersimpan di CDN Edge Cache.{Style.RESET}\n")

    await asyncio.sleep(0.5)
    print(f"{Style.WHITE}{Style.BOLD}[Fase 2: Request-Time (Pengunjung Membuka Halaman)]{Style.RESET}")
    print(f"  {Style.CYAN}[t=5ms] CDN Edge langsung mengembalikan Static Shell (TTFB < 20ms)!{Style.RESET}")
    print(f"  {Style.YELLOW}[t=15ms] Serverless Worker memulai stream isi dinamis secara paralel...{Style.RESET}")

    dynamic_streams = [
        ("Auth Session Check (cookies)", 60, "User: Jane Doe (Member VIP)"),
        ("Dynamic Cart Items (header)", 140, "3 items ($129.00)"),
        ("Personalized AI Recommendation", 380, "Rekomendasi: 'Next.js Design Patterns'"),
    ]

    for name, lat, payload in dynamic_streams:
        await asyncio.sleep(lat / 1000.0)
        print(f"    {Style.GREEN}↳ Stream injected:{Style.RESET} [{name}] -> {Style.WHITE}{payload}{Style.RESET}")

    print(f"\n{Style.GREEN}{Style.BOLD}✓ Hasil Evaluasi PPR:{Style.RESET} Pengguna merasakan instan loading CDN, data personal tetap up-to-date!")


def display_comparison_table():
    print(f"\n{Style.BOLD}{Style.WHITE}>>> [4] MATRIKS PERBANDINGAN PARADIGMA RENDERING NEXT.JS <<<{Style.RESET}")
    header = f"| {'Paradigma':<12} | {'Build Time':<12} | {'Server Overhead':<17} | {'Client JS Size':<16} | {'Kelemahan Utama':<22} |"
    divider = "-" * len(header)
    print(divider)
    print(f"{Style.BOLD}{header}{Style.RESET}")
    print(divider)
    
    rows = [
        ("SPA / CSR", "None", "Hampir Nol", "Sangat Besar", "SEO buruk, FCP lambat"),
        ("Legacy SSR", "None", "Tinggi per-request", "Besar (Full Hydrate)", "TTFB terblokir DB"),
        ("SSG", "Paling Lama", "Nol (CDN Hosted)", "Sedang", "Data stale / basi"),
        ("ISR", "Sedang", "Rendah (Background)", "Sedang", "Kompleksitas cache invalidation"),
        ("RSC + Stream", "Cepat", "Optimal (Streaming)", "Minimal (Zero-bundle)", "Mindset arsitektur baru"),
        ("PPR (Next.js)", "Otomatis", "Paling Efisien", "Ultra-Minimal", "Butuh Next.js 14/15/Canary"),
    ]
    
    for p, b, s, c, k in rows:
        print(f"| {Style.CYAN}{p:<12}{Style.RESET} | {b:<12} | {s:<17} | {c:<16} | {Style.RED}{k:<22}{Style.RESET} |")
    print(divider)


async def interactive_menu():
    while True:
        print(f"\n{Style.BOLD}PILIH SIMULASI LAB (BAB-03 NEXT.JS):{Style.RESET}")
        print(f"  {Style.CYAN}[1]{Style.RESET} Simulasi RSC Flight Protocol Serialization")
        print(f"  {Style.YELLOW}[2]{Style.RESET} Simulasi Streaming SSR & Suspense Pipeline")
        print(f"  {Style.GREEN}[3]{Style.RESET} Simulasi Partial Prerendering (PPR) Lifecycle")
        print(f"  {Style.MAGENTA}[4]{Style.RESET} Tabel Matriks Arsitektur Rendering")
        print(f"  {Style.WHITE}[5]{Style.RESET} Jalankan Seluruh Lab Sekaligus")
        print(f"  {Style.RED}[0]{Style.RESET} Keluar")

        try:
            choice = input(f"\n{Style.BOLD}Masukkan nomor pilihan (0-5): {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Sesi lab diakhiri.{Style.RESET}")
            break

        if choice == "1":
            await simulate_flight_protocol_generation()
        elif choice == "2":
            await simulate_streaming_suspense()
        elif choice == "3":
            await simulate_partial_prerender()
        elif choice == "4":
            display_comparison_table()
        elif choice == "5":
            await simulate_flight_protocol_generation()
            await simulate_streaming_suspense()
            await simulate_partial_prerender()
            display_comparison_table()
        elif choice == "0":
            print(f"{Style.GREEN}Terima kasih! Lab exercise Next.js selesai.{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Pilihan tidak valid, silakan ulangi.{Style.RESET}")


def main():
    print_banner()
    try:
        asyncio.run(interactive_menu())
    except KeyboardInterrupt:
        print(f"\n{Style.YELLOW}Keluar dari program.{Style.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
