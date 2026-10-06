#!/usr/bin/env python3
"""
Next.js Core Optimization Lab: Asset Optimization, Web Vitals & Zero Runtime Overhead
Simulasi interaktif teknis Next.js App Router:
- next/image: Responsive srcset, AVIF/WebP transcoding, aspect ratio placeholder (Anti-CLS)
- next/font: Self-hosting, Google Font inlining, size-adjust fallback font matching
- Core Web Vitals Calculator: LCP, INP, CLS thresholds & Lighthouse performance score
- Server Components (RSC): Zero-runtime JavaScript client payload analysis
"""

import sys
import time
import math
from typing import Dict, List, Tuple

# ANSI Escape Colors for Rich Terminal Display
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def print_header(title: str) -> None:
    print(f"\n{BG_BLUE}{WHITE}{BOLD} === {title} === {RESET}\n")


def simulate_next_image() -> None:
    print_header("SIMULASI 1: next/image AUTOMATIC OPTIMIZATION & ANTI-CLS")
    print(f"{CYAN}Skenario:{RESET} Memuat hero banner mentah format JPEG 4000x2500 px (3.4 MB).")
    print(f"{YELLOW}Transformasi otomatis oleh Image Optimization API (Sharp / Squoosh)...{RESET}\n")

    sizes = [640, 1080, 1920]
    raw_size_bytes = 3400 * 1024  # 3.4 MB

    print(f"{BOLD}{'Target Width':<15} | {'Format':<10} | {'Ukuran File':<14} | {'Penghematan':<12} | {'CLS Protection'}{RESET}")
    print("-" * 75)

    for width in sizes:
        height = int(width * (2500 / 4000))
        # WebP / AVIF compression simulation
        avif_size = int(raw_size_bytes * (width / 4000) * 0.12)
        savings = (1 - (avif_size / raw_size_bytes)) * 100

        print(
            f"{width}px x {height}px{'':<3} | "
            f"{GREEN}image/avif{RESET} | "
            f"{avif_size / 1024:6.1f} KB{'':<5} | "
            f"{GREEN}-{savings:5.1f}%{RESET}{'':<4} | "
            f"{MAGENTA}aspect-ratio: {width}/{height}{RESET}"
        )

    print(f"\n{BOLD}Output Tag HTML (Next.js Hydration Target):{RESET}")
    srcset = ", ".join([f"/_next/image?url=hero.jpg&w={w}&q=75 {w}w" for w in sizes])
    print(f'{CYAN}<img srcset="{srcset}"')
    print(f'     sizes="(max-width: 768px) 100vw, 1920px"')
    print(f'     style="aspect-ratio: 16/10; object-fit: cover;"')
    print(f'     loading="eager" fetchpriority="high" decoding="async" />{RESET}\n')
    print(f"{GREEN}✓ Zero CLS didapat karena browser mereservasi ruang piksel sebelum gambar terunduh.{RESET}")


def simulate_next_font() -> None:
    print_header("SIMULASI 2: next/font ZERO-RUNTIME & SIZE-ADJUST FALLBACK")
    print(f"{CYAN}Skenario:{RESET} Menggunakan font 'Geist Sans' & 'Inter' via next/font/google.")
    print(f"Tanpa next/font, browser mengalami FOUT (Flash of Unstyled Text) atau FOIT saat swap.")

    font_configs = [
        {"name": "Inter", "subset": "latin", "fallback": "Arial", "size_adjust": "103.2%", "ascent": "92.5%"},
        {"name": "Geist Sans", "subset": "latin,latin-ext", "fallback": "system-ui", "size_adjust": "98.7%", "ascent": "95.0%"},
    ]

    print(f"\n{BOLD}{'Web Font':<14} | {'Subsetting':<18} | {'Fallback Font':<14} | {'size-adjust':<12} | {'Network Overhead'}{RESET}")
    print("-" * 80)

    for font in font_configs:
        print(
            f"{CYAN}{font['name']:<14}{RESET} | "
            f"{WHITE}{font['subset']:<18}{RESET} | "
            f"{YELLOW}{font['fallback']:<14}{RESET} | "
            f"{GREEN}{font['size_adjust']:<12}{RESET} | "
            f"{GREEN}0 External Req (Self-hosted){RESET}"
        )

    print(f"\n{BOLD}Generated CSS via @font-face (Build Time):{RESET}")
    print(f"""{WHITE}@font-face {{
  font-family: '__Inter_Fallback';
  src: local('Arial');
  ascent-override: 92.5%;
  size-adjust: 103.2%;
}}
.font-sans {{
  font-family: '__Inter_b8a92f', '__Inter_Fallback', sans-serif;
}}{RESET}""")
    print(f"{GREEN}✓ Zero Layout Shift (CLS: 0.000) saat font asli selesai didownload dari domain yang sama!{RESET}")


def evaluate_web_vitals(lcp_ms: float, inp_ms: float, cls_val: float) -> Tuple[int, List[Dict[str, str]]]:
    results = []

    # LCP Assessment (Good <= 2500ms, Needs Improvement <= 4000ms, Poor > 4000ms)
    if lcp_ms <= 2500:
        lcp_stat = ("GOOD", GREEN, 100)
    elif lcp_ms <= 4000:
        lcp_stat = ("NEEDS IMPROVEMENT", YELLOW, 65)
    else:
        lcp_stat = ("POOR", RED, 25)
    results.append({"metric": "LCP (Largest Contentful Paint)", "value": f"{lcp_ms:.0f} ms", "status": lcp_stat[0], "color": lcp_stat[1]})

    # INP Assessment (Good <= 200ms, Needs Improvement <= 500ms, Poor > 500ms)
    if inp_ms <= 200:
        inp_stat = ("GOOD", GREEN, 100)
    elif inp_ms <= 500:
        inp_stat = ("NEEDS IMPROVEMENT", YELLOW, 65)
    else:
        inp_stat = ("POOR", RED, 20)
    results.append({"metric": "INP (Interaction to Next Paint)", "value": f"{inp_ms:.0f} ms", "status": inp_stat[0], "color": inp_stat[1]})

    # CLS Assessment (Good <= 0.1, Needs Improvement <= 0.25, Poor > 0.25)
    if cls_val <= 0.10:
        cls_stat = ("GOOD", GREEN, 100)
    elif cls_val <= 0.25:
        cls_stat = ("NEEDS IMPROVEMENT", YELLOW, 60)
    else:
        cls_stat = ("POOR", RED, 15)
    results.append({"metric": "CLS (Cumulative Layout Shift)", "value": f"{cls_val:.3f}", "status": cls_stat[0], "color": cls_stat[1]})

    # Lighthouse Performance Weighting approx: LCP: 25%, INP: 25%, CLS: 25%, Others: 25% (normalized)
    weighted_score = int((lcp_stat[2] * 0.40) + (inp_stat[2] * 0.35) + (cls_stat[2] * 0.25))
    return weighted_score, results


def simulate_web_vitals() -> None:
    print_header("SIMULASI 3: CORE WEB VITALS (CWV) AUDITOR")
    print(f"Perbandingan Performa Sebelum vs Sesudah Optimasi Next.js:\n")

    scenarios = [
        {"name": "Sebelum Optimasi (SPA Tradisional / Unoptimized Assets)", "lcp": 4200.0, "inp": 540.0, "cls": 0.285},
        {"name": "Setelah Optimasi (next/image, next/font, RSC Streaming)", "lcp": 1350.0, "inp": 85.0, "cls": 0.005},
    ]

    for sc in scenarios:
        score, metrics = evaluate_web_vitals(sc["lcp"], sc["inp"], sc["cls"])
        color_score = GREEN if score >= 90 else (YELLOW if score >= 50 else RED)

        print(f"{BOLD}{sc['name']}:{RESET}")
        for m in metrics:
            print(f"  • {m['metric']:<32}: {m['value']:<10} -> {m['color']}{m['status']}{RESET}")
        print(f"  {BOLD}Lighthouse Score:{RESET} {color_score}{score}/100{RESET}\n")


def simulate_zero_runtime_rsc() -> None:
    print_header("SIMULASI 4: ZERO RUNTIME OVERHEAD DENGAN REACT SERVER COMPONENTS")
    print(f"Analisis ukuran bundle JavaScript yang dikirim ke browser (Client Footprint):\n")

    modules = [
        {"module": "Markdown/MDX Parser", "traditional_kb": 128.5, "rsc_kb": 0.0, "type": "Server Only"},
        {"module": "Date-fns / Moment formatting", "traditional_kb": 65.2, "rsc_kb": 0.0, "type": "Server Only"},
        {"module": "Syntax Highlighter (Shiki/Prism)", "traditional_kb": 240.0, "rsc_kb": 0.0, "type": "Server Only"},
        {"module": "Interactive Filter & Search Box", "traditional_kb": 14.5, "rsc_kb": 14.5, "type": "Client Component ('use client')"},
        {"module": "Pagination Control", "traditional_kb": 8.0, "rsc_kb": 8.0, "type": "Client Component ('use client')"},
    ]

    total_trad = sum(m["traditional_kb"] for m in modules)
    total_rsc = sum(m["rsc_kb"] for m in modules)

    print(f"{BOLD}{'Dependensi / Modul':<35} | {'Tradisional (KB)':<18} | {'Next.js RSC (KB)':<18} | {'Jenis Boundary'}{RESET}")
    print("-" * 88)

    for m in modules:
        print(
            f"{WHITE}{m['module']:<35}{RESET} | "
            f"{RED}{m['traditional_kb']:>14.1f} KB{RESET} | "
            f"{GREEN}{m['rsc_kb']:>14.1f} KB{RESET} | "
            f"{CYAN}{m['type']}{RESET}"
        )

    reduction = ((total_trad - total_rsc) / total_trad) * 100
    print("-" * 88)
    print(f"{BOLD}{'TOTAL CLIENT RUNTIME BUNDLE':<35} | {RED}{total_trad:>14.1f} KB{RESET} | {GREEN}{total_rsc:>14.1f} KB{RESET} | {BOLD}{GREEN}-{reduction:.1f}% Payloads{RESET}\n")
    print(f"{GREEN}✓ Server Components mengeksekusi kode berat di node runtime, mengirimkan HTML murni tanpa payload JS ke browser!{RESET}")


def interactive_menu() -> None:
    while True:
        print(f"\n{BOLD}{CYAN}================================================================={RESET}")
        print(f"{BOLD}{WHITE}   NEXT.JS OPTIMIZATION & WEB VITALS INTERACTIVE WORKSHOP       {RESET}")
        print(f"{BOLD}{CYAN}================================================================={RESET}")
        print("  1. Simulasi next/image (Srcset, WebP/AVIF, Anti-CLS)")
        print("  2. Simulasi next/font (Subsetting, Zero-layout shift)")
        print("  3. Simulasi Audit Web Vitals (LCP, INP, CLS)")
        print("  4. Simulasi Zero Runtime Overhead (React Server Components)")
        print("  5. Jalankan Semua Simulasi Sekaligus")
        print("  6. Keluar")
        print(f"{BOLD}{CYAN}-----------------------------------------------------------------{RESET}")

        try:
            choice = input(f"{BOLD}Pilih modul simulasi (1-6): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari program.")
            sys.exit(0)

        if choice == "1":
            simulate_next_image()
        elif choice == "2":
            simulate_next_font()
        elif choice == "3":
            simulate_web_vitals()
        elif choice == "4":
            simulate_zero_runtime_rsc()
        elif choice == "5":
            simulate_next_image()
            simulate_next_font()
            simulate_web_vitals()
            simulate_zero_runtime_rsc()
        elif choice == "6":
            print(f"\n{GREEN}Workshop selesai. Tetap jaga Web Vitals di zona hijau!{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1 - 6.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        simulate_next_image()
        simulate_next_font()
        simulate_web_vitals()
        simulate_zero_runtime_rsc()
    else:
        # Check if stdin is a tty, otherwise run all for non-interactive test
        if sys.stdin.isatty():
            interactive_menu()
        else:
            simulate_next_image()
            simulate_next_font()
            simulate_web_vitals()
            simulate_zero_runtime_rsc()
