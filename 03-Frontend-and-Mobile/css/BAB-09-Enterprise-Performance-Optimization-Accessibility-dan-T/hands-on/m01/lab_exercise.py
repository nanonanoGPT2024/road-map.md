#!/usr/bin/env python3
"""
Lab Exercise: CSS Enterprise Performance Optimization, Accessibility (a11y), & Tooling
Simulasi interaktif teknis Core Web Vitals, WCAG 2.2 Contrast Ratio, Critical CSS,
dan Rendering Pipeline (Layout Thrashing vs Batching).
"""

import sys
import time
import math
import re

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
BG_DARK = "\033[48;5;236m"


def print_banner():
    banner = f"""{CYAN}{BOLD}
================================================================================
   ENTERPRISE CSS PERFORMANCE, ACCESSIBILITY (A11Y) & TOOLING LAB ENGINE
================================================================================{RESET}
{DIM}Simulasi teknis: WCAG 2.2 Contrast, Critical Rendering Path, Layout Thrashing & Bundle Audit{RESET}
"""
    print(banner)


def hex_to_rgb(hex_str: str):
    """Konversi string HEX (#RRGGBB atau #RGB) ke tuple (R, G, B) integer."""
    hex_clean = hex_str.strip().lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) != 6:
        raise ValueError(f"Format HEX tidak valid: {hex_str}")
    return tuple(int(hex_clean[i:i + 2], 16) for i in (0, 2, 4))


def calculate_relative_luminance(rgb):
    """Menghitung Relative Luminance sesuai spesifikasi WCAG 2.1/2.2."""
    normalized = []
    for c in rgb:
        val = c / 255.0
        if val <= 0.04045:
            normalized.append(val / 12.92)
        else:
            normalized.append(((val + 0.055) / 1.055) ** 2.4)
    r, g, b = normalized
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(hex_fg: str, hex_bg: str):
    """Menghitung Contrast Ratio (L1 + 0.05) / (L2 + 0.05)."""
    rgb_fg = hex_to_rgb(hex_fg)
    rgb_bg = hex_to_rgb(hex_bg)
    l1 = calculate_relative_luminance(rgb_fg)
    l2 = calculate_relative_luminance(rgb_bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def run_a11y_contrast_module():
    """Modul audit kalkulasi rasio kontras warna WCAG 2.2."""
    print(f"\n{YELLOW}{BOLD}[MODUL 1: WCAG 2.2 Relative Luminance & Contrast Checker]{RESET}")
    print("Ketentuan WCAG 2.2:")
    print(" - Level AA Normal Text (<18pt/24px)  : Min 4.5:1")
    print(" - Level AA Large Text (>=18pt bold) : Min 3.0:1")
    print(" - Level AAA Normal Text             : Min 7.0:1")
    print(" - Level AAA Large Text              : Min 4.5:1\n")

    sample_pairs = [
        ("Default Dark Theme", "#FFFFFF", "#121212"),
        ("Low Contrast Grey", "#767676", "#FFFFFF"),
        ("Brand Primary Blue", "#0066CC", "#FFFFFF"),
        ("Muted Placeholder", "#A0AEC0", "#FFFFFF"),
        ("Warning Accent", "#FFC107", "#FFFFFF"),
    ]

    print(f"{'Label':<22} {'Foreground':<10} {'Background':<10} {'Ratio':<10} {'AA Norm':<10} {'AAA Norm':<10}")
    print("-" * 75)

    for label, fg, bg in sample_pairs:
        ratio = calculate_contrast_ratio(fg, bg)
        aa_pass = ratio >= 4.5
        aaa_pass = ratio >= 7.0

        aa_badge = f"{GREEN}PASS{RESET}" if aa_pass else f"{RED}FAIL{RESET}"
        aaa_badge = f"{GREEN}PASS{RESET}" if aaa_pass else f"{RED}FAIL{RESET}"
        ratio_str = f"{ratio:.2f}:1"

        print(f"{label:<22} {fg:<10} {bg:<10} {ratio_str:<10} {aa_badge:<19} {aaa_badge:<19}")

    print(f"\n{CYAN}Uji Warna Custom:{RESET}")
    try:
        user_fg = input("Masukkan Foreground HEX (contoh #2563EB) [tekan Enter lewati]: ").strip()
        if user_fg:
            user_bg = input("Masukkan Background HEX (contoh #FFFFFF): ").strip() or "#FFFFFF"
            ratio = calculate_contrast_ratio(user_fg, user_bg)
            status_aa = f"{GREEN}MEMENUHI (PASS){RESET}" if ratio >= 4.5 else f"{RED}TIDAK MEMENUHI (FAIL){RESET}"
            print(f"\n-> Hasil Rasio: {BOLD}{ratio:.2f}:1{RESET} | WCAG AA Normal Text: {status_aa}")
    except Exception as err:
        print(f"{RED}Error parsing warna:{RESET} {err}")


def run_critical_css_audit():
    """Simulasi analisa Critical CSS inlining vs Render-blocking External Stylesheet."""
    print(f"\n{YELLOW}{BOLD}[MODUL 2: Critical CSS & First Contentful Paint (FCP) Audit]{RESET}")
    print("Membandingkan performa loading aset CSS monolitik vs Critical CSS Inline...")

    simulated_scenarios = [
        {
            "name": "Monolithic external CSS (render-blocking, 350 KB, 4 RTT)",
            "fcp_ms": 1850,
            "lcp_ms": 3200,
            "cls": 0.18,
            "blocking_time_ms": 420,
        },
        {
            "name": "Critical CSS Inline (14 KB in <head>, async preload non-critical)",
            "fcp_ms": 620,
            "lcp_ms": 1150,
            "cls": 0.01,
            "blocking_time_ms": 45,
        },
        {
            "name": "Critical Inline + `content-visibility: auto` on offscreen sections",
            "fcp_ms": 510,
            "lcp_ms": 890,
            "cls": 0.00,
            "blocking_time_ms": 18,
        },
    ]

    for item in simulated_scenarios:
        time.sleep(0.3)
        print(f"\n{BOLD}Skenario: {item['name']}{RESET}")
        fcp_col = GREEN if item['fcp_ms'] <= 1800 else (YELLOW if item['fcp_ms'] <= 3000 else RED)
        lcp_col = GREEN if item['lcp_ms'] <= 2500 else (YELLOW if item['lcp_ms'] <= 4000 else RED)
        cls_col = GREEN if item['cls'] <= 0.1 else RED

        print(f"  * FCP: {fcp_col}{item['fcp_ms']} ms{RESET} (Target Core Web Vitals: <= 1800 ms)")
        print(f"  * LCP: {lcp_col}{item['lcp_ms']} ms{RESET} (Target Core Web Vitals: <= 2500 ms)")
        print(f"  * CLS: {cls_col}{item['cls']:.2f}{RESET}     (Target Core Web Vitals: <= 0.10)")
        print(f"  * Total Blocking Time: {item['blocking_time_ms']} ms")


def run_layout_thrashing_benchmark():
    """Simulasi Forced Synchronous Layout / Layout Thrashing vs FastDOM Batching."""
    print(f"\n{YELLOW}{BOLD}[MODUL 3: Layout Thrashing & Forced Synchronous Layout (FSL)]{RESET}")
    print("Menganalisis dampak eksekusi loop manipulasi geometri CSS:")
    print("Pola Anti-pattern: Interleaved Read (.offsetWidth) & Write (.style.width)")
    print("Pola Optimal     : Read Phase batching diikuti Write Phase batching (requestAnimationFrame)\n")

    elements_count = 1500

    print(f"{DIM}Menjalankan benchmark kalkulasi reflow DOM ({elements_count} node virtual)...{RESET}")

    # Simulasi interleave
    start_time = time.perf_counter()
    accum_read = 0
    for i in range(elements_count):
        # Read geometry (forces layout recalc)
        accum_read += (i * 3) % 17
        # Write geometry
        _ = accum_read * 1.05
        # Artifisial overhead untuk simulasi reflow cost
        for _ in range(120):
            pass
    duration_thrashing = (time.perf_counter() - start_time) * 1000

    # Simulasi batching
    start_time = time.perf_counter()
    read_results = []
    # Phase 1: Read batch
    for i in range(elements_count):
        read_results.append((i * 3) % 17)
    # Phase 2: Write batch
    for val in read_results:
        _ = val * 1.05
    duration_batching = (time.perf_counter() - start_time) * 1000

    print(f"1. Anti-Pattern (Layout Thrashing) : {RED}{BOLD}{duration_thrashing:.2f} ms{RESET}")
    print(f"2. Enterprise Batching (FastDOM/rAF): {GREEN}{BOLD}{duration_batching:.2f} ms{RESET}")
    speedup = duration_thrashing / max(duration_batching, 0.001)
    print(f"{CYAN}Optimasi Reflow Menghemat:{RESET} {BOLD}{speedup:.1f}x lebih cepat!{RESET}")


def run_css_bundle_treeshake_sim():
    """Simulasi PurgeCSS / Unused CSS Detection pada Enterprise Bundle."""
    print(f"\n{YELLOW}{BOLD}[MODUL 4: CSS Dead Code Elimination & Bundle Analyzer]{RESET}")
    
    mock_bundle_rules = [
        (".container", True, 120),
        (".btn-primary", True, 250),
        (".legacy-carousel-v1", False, 18400),
        (".hidden-ie11-hack", False, 8200),
        (".grid-system-12col", True, 4500),
        (".deprecated-modal-backdrop", False, 12300),
        (".utility-flex-center", True, 180),
        (".admin-panel-table-old", False, 26000),
        (".typography-prose", True, 3200),
    ]

    total_bytes = sum(item[2] for item in mock_bundle_rules)
    used_bytes = sum(item[2] for item in mock_bundle_rules if item[1])
    unused_bytes = total_bytes - used_bytes
    reduction_pct = (unused_bytes / total_bytes) * 100

    print(f"{'Selector Pattern':<30} {'Status':<12} {'Size (Bytes)':<12}")
    print("-" * 55)
    for selector, is_used, size in mock_bundle_rules:
        status_tag = f"{GREEN}ACTIVE{RESET}" if is_used else f"{RED}DEAD/UNUSED{RESET}"
        print(f"{selector:<30} {status_tag:<21} {size:<12}")

    print("\n" + "=" * 55)
    print(f"Total Bundle Asli   : {BOLD}{total_bytes / 1024:.2f} KB{RESET}")
    print(f"Bundle Bersih (Used): {GREEN}{BOLD}{used_bytes / 1024:.2f} KB{RESET}")
    print(f"Reduksi Dead Code   : {MAGENTA}{BOLD}{reduction_pct:.1f}% ({unused_bytes / 1024:.2f} KB dieliminasi){RESET}")


def interactive_menu():
    """Loop navigasi interaktif lab terminal."""
    while True:
        print_banner()
        print(f"{BOLD}Pilih Modul Lab:{RESET}")
        print("  [1] WCAG 2.2 Color Contrast & Relative Luminance Engine")
        print("  [2] Critical CSS & First Contentful Paint (FCP/LCP) Simulation")
        print("  [3] Layout Thrashing (Reflow) vs Batching Benchmark")
        print("  [4] CSS Bundle Treeshaking & Dead-Code Eliminator")
        print("  [5] Jalankan Seluruh Audit Komprehensif (All-in-One)")
        print("  [0] Keluar")

        pilihan = input(f"\n{CYAN}Masukkan nomor modul [0-5]: {RESET}").strip()

        if pilihan == "1":
            run_a11y_contrast_module()
        elif pilihan == "2":
            run_critical_css_audit()
        elif pilihan == "3":
            run_layout_thrashing_benchmark()
        elif pilihan == "4":
            run_css_bundle_treeshake_sim()
        elif pilihan == "5":
            run_a11y_contrast_module()
            run_critical_css_audit()
            run_layout_thrashing_benchmark()
            run_css_bundle_treeshake_sim()
        elif pilihan in ("0", "q", "exit"):
            print(f"\n{GREEN}Lab selesai. Terima kasih telah mempraktikkan Enterprise CSS Optimization!{RESET}\n")
            break
        else:
            print(f"\n{RED}Pilihan tidak dikenali. Silakan masukkan angka 0 - 5.{RESET}")

        input(f"\n{DIM}Tekan [Enter] untuk kembali ke menu utama...{RESET}")


if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Sesi lab dihentikan oleh pengguna. Sampai jumpa!{RESET}\n")
        sys.exit(0)
