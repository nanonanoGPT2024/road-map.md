#!/usr/bin/env python3
"""
Lab Exercise: Responsive Media, Resource Hints, and Asset Optimization Simulation
Materi: BAB-05 Media Responsif, Resource Hints, dan Optimasi Aset (HTML5)
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple


class ANSI:
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
    BG_GREEN = "\033[42m"


@dataclass
class ImageCandidate:
    url: str
    width: int
    format_type: str
    size_kb: float


@dataclass
class ResourceHint:
    rel: str
    href: str
    as_type: Optional[str] = None
    fetchpriority: Optional[str] = None
    crossorigin: bool = False


class MediaOptimizerSimulator:
    def __init__(self):
        self.image_candidates = [
            ImageCandidate("hero-mobile.webp", 480, "webp", 35.0),
            ImageCandidate("hero-tablet.webp", 800, "webp", 78.0),
            ImageCandidate("hero-desktop.webp", 1200, "webp", 145.0),
            ImageCandidate("hero-desktop-2x.webp", 2400, "webp", 310.0),
            ImageCandidate("hero-desktop.avif", 1200, "avif", 88.0),
            ImageCandidate("hero-desktop.jpg", 1200, "jpeg", 280.0),
        ]

    def banner(self, title: str):
        print(f"\n{ANSI.BOLD}{ANSI.BG_BLUE}{ANSI.WHITE} [SIMULASI] {title} {ANSI.RESET}\n")

    def simulate_responsive_selection(self, viewport_width: int, dpr: float):
        self.banner(f"Simulasi Algoritma Browser: srcset + sizes (Viewport: {viewport_width}px, DPR: {dpr}x)")
        
        # Skenario sizes: (max-width: 600px) 100vw, (max-width: 1024px) 80vw, 1200px
        if viewport_width <= 600:
            slot_css = viewport_width
            rule = "(max-width: 600px) -> 100vw"
        elif viewport_width <= 1024:
            slot_css = int(viewport_width * 0.8)
            rule = "(max-width: 1024px) -> 80vw"
        else:
            slot_css = 1200
            rule = "default -> 1200px"

        needed_physical_px = int(slot_css * dpr)
        print(f"{ANSI.CYAN}1. Evaluasi Sizes Descriptor:{ANSI.RESET} Aturan cocok = {ANSI.YELLOW}{rule}{ANSI.RESET}")
        print(f"   Slot render CSS       : {slot_css}px")
        print(f"   DPR (Device Pixel)    : {dpr}x")
        print(f"   Kebutuhan fisik riil  : {slot_css} * {dpr} = {ANSI.BOLD}{needed_physical_px}px{ANSI.RESET}")

        # Browser memilih candidate dengan width descriptor terdekat yang >= needed_physical_px
        candidates_webp = sorted(
            [c for c in self.image_candidates if c.format_type == "webp"],
            key=lambda x: x.width
        )

        chosen = None
        for cand in candidates_webp:
            if cand.width >= needed_physical_px:
                chosen = cand
                break
        if not chosen:
            chosen = candidates_webp[-1]

        print(f"\n{ANSI.CYAN}2. Kandidat srcset Terdaftar:{ANSI.RESET}")
        for c in candidates_webp:
            marker = f"{ANSI.GREEN} <-- TERPILIH{ANSI.RESET}" if c == chosen else ""
            print(f"   - {c.url:<22} w={c.width:>4}px | {c.size_kb:>5.1f} KB {marker}")

        print(f"\n{ANSI.GREEN}{ANSI.BOLD}Hasil Akhir:{ANSI.RESET} Browser mengunduh aset {ANSI.YELLOW}{chosen.url}{ANSI.RESET} ({chosen.size_kb} KB)")
        print(f"{ANSI.DIM}Efisiensi: Menghindari pemborosan bandwidth layar mobile sekaligus mencegah blur pada high-DPI.{ANSI.RESET}")

    def simulate_art_direction(self, viewport_width: int, prefers_dark: bool = False):
        self.banner("Simulasi Art Direction (<picture> element)")
        print(f"Viewport width saat ini : {ANSI.BOLD}{viewport_width}px{ANSI.RESET}")
        print(f"Tema Sistem Operasi     : {ANSI.BOLD}{'Dark Mode' if prefers_dark else 'Light Mode'}{ANSI.RESET}\n")

        print(f"{ANSI.CYAN}Daftar <source> dalam markup:{ANSI.RESET}")
        sources = [
            ('(prefers-color-scheme: dark) and (max-width: 768px)', 'hero-mobile-dark.webp', 'Crop vertikal 4:5 + tema gelap kontras tinggi'),
            ('(prefers-color-scheme: dark)', 'hero-desktop-dark.webp', 'Landscape 16:9 + tema gelap'),
            ('(max-width: 768px)', 'hero-mobile-light.webp', 'Crop vertikal 4:5 fokus subjek tengah'),
            ('default <img> fallback', 'hero-fallback.jpg', 'Foto landscape standar'),
        ]

        selected = None
        for condition, asset, purpose in sources:
            matched = False
            if condition.startswith('(prefers-color-scheme: dark) and (max-width: 768px)'):
                matched = prefers_dark and viewport_width <= 768
            elif condition.startswith('(prefers-color-scheme: dark)'):
                matched = prefers_dark
            elif condition.startswith('(max-width: 768px)'):
                matched = viewport_width <= 768
            elif 'fallback' in condition:
                matched = True

            status = f"{ANSI.GREEN}MATCH{ANSI.RESET}" if matched and not selected else f"{ANSI.DIM}SKIP{ANSI.RESET}"
            if matched and not selected:
                selected = (asset, purpose)
            print(f"   [{status}] media=\"{condition:<50}\" -> {asset}")

        print(f"\n{ANSI.BOLD}{ANSI.YELLOW}Keputusan Rendering Browser:{ANSI.RESET}")
        print(f"   File Digunakan : {ANSI.GREEN}{selected[0]}{ANSI.RESET}")
        print(f"   Tujuan Desain  : {selected[1]}")

    def simulate_resource_hints(self):
        self.banner("Simulasi Pipeline Resource Hints & Network Waterfall")
        hints = [
            ResourceHint("dns-prefetch", "https://fonts.gstatic.com"),
            ResourceHint("preconnect", "https://assets.cdn-provider.com", crossorigin=True),
            ResourceHint("preload", "/fonts/inter-var.woff2", as_type="font", crossorigin=True),
            ResourceHint("preload", "/images/lcp-hero.avif", as_type="image", fetchpriority="high"),
            ResourceHint("prefetch", "/js/subsequent-dashboard.js", as_type="script"),
        ]

        print(f"{ANSI.CYAN}Tahapan Eksekusi Browser saat Parsing Dokumen Head:{ANSI.RESET}\n")
        time_offset_ms = 0
        for hint in hints:
            if hint.rel == "dns-prefetch":
                desc = "Resolve nama domain via DNS lebih awal (hemat ~30-80ms RTT)"
                time_cost = 15
            elif hint.rel == "preconnect":
                desc = "DNS Lookup + TCP Handshake + TLS Negotiation segera dieksekusi"
                time_cost = 65
            elif hint.rel == "preload":
                prio = f" [priority={hint.fetchpriority or 'normal'}]"
                desc = f"Unduh aset kritis sebelum parser menemukan referensi di DOM/CSS{prio}"
                time_cost = 110
            elif hint.rel == "prefetch":
                desc = "Unduh aset saat browser IDLE untuk navigasi rute halaman berikutnya"
                time_cost = 250
            else:
                desc = "Standard fetch"
                time_cost = 100

            print(f" {ANSI.BOLD}+{time_offset_ms:>4}ms{ANSI.RESET} | rel=\"{ANSI.MAGENTA}{hint.rel:<12}{ANSI.RESET}\" | href=\"{hint.href}\"")
            print(f"         └─ {ANSI.DIM}{desc}{ANSI.RESET}")
            time_offset_ms += time_cost

        print(f"\n{ANSI.GREEN}Keuntungan Kinerja:{ANSI.RESET} Hero LCP siap lebih awal sebesar 280ms, Cumulative Layout Shift terminimalisir.")

    def simulate_cls_and_decoding(self):
        self.banner("Optimasi Aset: Pencegahan Layout Shift (CLS) & Async Decoding")
        
        test_cases = [
            ("Kasus Buruk", '<img src="banner.jpg">', False, 0.28, "Menyebabkan reflow layout saat gambar terunduh"),
            ("Praktik Baik", '<img src="banner.jpg" width="1200" height="600" loading="lazy" decoding="async">', True, 0.001, "Aspect-ratio tereservasi, decoding di thread terpisah")
        ]

        for label, markup, is_good, cls_score, explanation in test_cases:
            color = ANSI.GREEN if is_good else ANSI.RED
            status = "LOLOS AUDIT CORE WEB VITALS" if is_good else "GAGAL (TERJADI CLS TINGGI)"
            print(f"{color}{ANSI.BOLD}[{label}] - {status}{ANSI.RESET}")
            print(f" Markup : {markup}")
            print(f" CLS    : {color}{cls_score:.3f}{ANSI.RESET}")
            print(f" Dampak : {explanation}\n")


def run_interactive_menu():
    sim = MediaOptimizerSimulator()
    while True:
        print(f"{ANSI.BOLD}{ANSI.WHITE}================================================================={ANSI.RESET}")
        print(f"{ANSI.BOLD}{ANSI.CYAN} LAB HTML: MEDIA RESPONSIF, RESOURCE HINTS, & OPTIMASI ASET{ANSI.RESET}")
        print(f"{ANSI.BOLD}{ANSI.WHITE}================================================================={ANSI.RESET}")
        print(" 1. Simulasi Resolusi Responsif (srcset + sizes)")
        print(" 2. Simulasi Art Direction (<picture> media queries)")
        print(" 3. Analisis Network Waterfall Resource Hints (preload/preconnect)")
        print(" 4. Audit CLS (Cumulative Layout Shift) & Image Decoding")
        print(" 5. Jalankan Seluruh Demonstrasi Sekaligus")
        print(" 0. Keluar")
        print("-----------------------------------------------------------------")
        
        try:
            choice = input(f"{ANSI.YELLOW}Pilih modul simulasi [0-5]: {ANSI.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            try:
                w_str = input("Masukkan lebar viewport (default 412): ").strip()
                w = int(w_str) if w_str else 412
                d_str = input("Masukkan DPR layar 1.0 - 3.0 (default 2.0): ").strip()
                d = float(d_str) if d_str else 2.0
            except ValueError:
                w, d = 412, 2.0
            sim.simulate_responsive_selection(w, d)
        elif choice == "2":
            try:
                w_str = input("Masukkan lebar viewport (default 650): ").strip()
                w = int(w_str) if w_str else 650
                dark_str = input("Aktifkan dark mode? (y/n, default n): ").strip().lower()
                is_dark = dark_str == "y"
            except ValueError:
                w, is_dark = 650, False
            sim.simulate_art_direction(w, is_dark)
        elif choice == "3":
            sim.simulate_resource_hints()
        elif choice == "4":
            sim.simulate_cls_and_decoding()
        elif choice == "5":
            sim.simulate_responsive_selection(390, 3.0)
            sim.simulate_responsive_selection(1440, 1.0)
            sim.simulate_art_direction(500, True)
            sim.simulate_resource_hints()
            sim.simulate_cls_and_decoding()
        elif choice == "0":
            print(f"{ANSI.GREEN}Terima kasih telah menggunakan lab simulasi.{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid, silakan ulangi.{ANSI.RESET}")


def main():
    sim = MediaOptimizerSimulator()
    # Jika dijalankan secara non-interaktif (piped/CI/test), jalankan demonstrasi penuh langsung
    if not sys.stdin.isatty() or len(sys.argv) > 1 and sys.argv[1] == "--demo":
        print(f"{ANSI.BOLD}Mode Batch / Non-Interaktif Terdeteksi: Menjalankan semua modul...{ANSI.RESET}")
        sim.simulate_responsive_selection(412, 2.6)
        sim.simulate_art_direction(720, True)
        sim.simulate_resource_hints()
        sim.simulate_cls_and_decoding()
    else:
        run_interactive_menu()


if __name__ == "__main__":
    main()
