#!/usr/bin/env python3
"""
Lab Exercise: Semantik HTML5 dan Aksesibilitas Web (WCAG & ARIA Simulator)
BAB-02: Fondasi Inti Frontend Beginner

Script mandiri interaktif dengan visualisasi ANSI terminal untuk memvalidasi
struktur semantik HTML5, pohon aksesibilitas (Accessibility Object Model - AOM),
dan kepatuhan WCAG 2.1 AA.
"""

import sys
import re
import math
from typing import List, Dict, Tuple, Optional


class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    BG_DARK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def header(title: str) -> None:
    border = "=" * 65
    print(f"\n{TerminalColor.CYAN}{TerminalColor.BOLD}{border}")
    print(f" {title.center(63)} ")
    print(f"{border}{TerminalColor.RESET}\n")


def section(title: str) -> None:
    print(f"\n{TerminalColor.MAGENTA}{TerminalColor.BOLD}>>> [MODUL] {title}{TerminalColor.RESET}")


def badge_pass(text: str) -> str:
    return f"{TerminalColor.BG_GREEN}{TerminalColor.WHITE}{TerminalColor.BOLD} PASS {TerminalColor.RESET} {text}"


def badge_fail(text: str) -> str:
    return f"{TerminalColor.BG_RED}{TerminalColor.WHITE}{TerminalColor.BOLD} FAIL {TerminalColor.RESET} {text}"


def badge_warn(text: str) -> str:
    return f"{TerminalColor.YELLOW}{TerminalColor.BOLD}[WARN]{TerminalColor.RESET} {text}"


def info_item(label: str, desc: str) -> None:
    print(f"  {TerminalColor.CYAN}•{TerminalColor.RESET} {TerminalColor.BOLD}{label:<22}{TerminalColor.RESET} : {desc}")


def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Menghitung relative luminance sesuai rumus WCAG 2.1."""
    channels = []
    for val in rgb:
        srgb = val / 255.0
        if srgb <= 0.03928:
            channels.append(srgb / 12.92)
        else:
            channels.append(((srgb + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def calculate_contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """Menghitung rasio kontras warna (L1 + 0.05) / (L2 + 0.05)."""
    l1 = calculate_relative_luminance(rgb1)
    l2 = calculate_relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


SAMPLE_BAD_HTML = """<!DOCTYPE html>
<html lang="">
<head><title>Toko Online Murah</title></head>
<body>
  <div class="header">
    <div class="logo"><img src="logo.png"></div>
    <div class="nav">
      <div class="link" onclick="navigate('home')">Home</div>
      <div class="link" onclick="navigate('products')">Produk</div>
    </div>
  </div>
  <div class="container">
    <div class="judul">Daftar Produk Unggulan</div>
    <h4>Kategori Fashion</h4>
    <div class="btn-beli" onclick="buyItem()">Beli Sekarang</div>
    <form>
      <input type="text" placeholder="Masukkan voucher">
    </form>
  </div>
  <div class="footer">&copy; 2026 Toko Sembarang</div>
</body>
</html>"""


SAMPLE_GOOD_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Toko Online Aksesibel</title>
</head>
<body>
  <header>
    <a href="#main-content" class="skip-link">Lewati ke konten utama</a>
    <img src="logo.svg" alt="Logo Resmi Toko Aksesibel">
    <nav aria-label="Navigasi Utama">
      <ul>
        <li><a href="/home">Home</a></li>
        <li><a href="/products">Produk</a></li>
      </ul>
    </nav>
  </header>
  <main id="main-content">
    <h1>Daftar Produk Unggulan</h1>
    <section aria-labelledby="sec-fashion">
      <h2 id="sec-fashion">Kategori Fashion</h2>
      <button type="button" aria-label="Beli Produk Kemeja Katun">Beli Sekarang</button>
    </section>
    <form>
      <label for="voucher-code">Kode Voucher Diskon:</label>
      <input id="voucher-code" type="text" name="voucher" required aria-required="true">
    </form>
  </main>
  <footer>
    <p>&copy; 2026 Toko Aksesibel. Berstandar Semantik HTML5.</p>
  </footer>
</body>
</html>"""


class SemanticAuditEngine:
    def __init__(self, raw_html: str):
        self.raw_html = raw_html
        self.issues: List[Dict[str, str]] = []
        self.passes: List[str] = []

    def audit_landmarks(self) -> None:
        """Memverifikasi penggunaan landmark semantik HTML5 standar."""
        required_landmarks = ["header", "nav", "main", "footer"]
        for landmark in required_landmarks:
            if re.search(rf"<{landmark}\b", self.raw_html, re.IGNORECASE):
                self.passes.append(f"Elemen landmark semantik <{landmark}> ditemukan.")
            else:
                self.issues.append({
                    "level": "FAIL",
                    "rule": "Landmark Semantik",
                    "msg": f"Missing <{landmark}>. Hindari '<div class=\"{landmark}\">'"
                })

    def audit_images(self) -> None:
        """Memeriksa atribut alt pada seluruh tag <img>."""
        img_tags = re.findall(r"<img\b([^>]*)>", self.raw_html, re.IGNORECASE)
        if not img_tags:
            self.passes.append("Tidak ada elemen <img> yang membutuhkan teks alternatif.")
            return

        for tag in img_tags:
            alt_match = re.search(r'alt\s*=\s*(["\'])(.*?)\1', tag, re.IGNORECASE)
            if not alt_match:
                self.issues.append({
                    "level": "FAIL",
                    "rule": "WCAG 1.1.1 Non-Text Content",
                    "msg": "Elemen <img> ditemukan tanpa atribut 'alt'. Screen reader akan mengeja nama file URL!"
                })
            elif len(alt_match.group(2).strip()) == 0:
                self.issues.append({
                    "level": "WARN",
                    "rule": "WCAG 1.1.1 Alt Kosong",
                    "msg": "Elemen <img> memiliki alt=\"\" (dekoratif). Pastikan gambar bukan konten informatif."
                })
            else:
                self.passes.append(f"Elemen <img> memiliki teks alt valid: '{alt_match.group(2)}'")

    def audit_headings(self) -> None:
        """Memeriksa hierarki heading (h1, h2, h3, dst) dan ketiadaan h1 ganda/loncat."""
        headings = re.findall(r"<(h[1-6])\b", self.raw_html, re.IGNORECASE)
        if not headings:
            self.issues.append({
                "level": "FAIL",
                "rule": "WCAG 1.3.1 Heading Hierarchy",
                "msg": "Halaman tidak memiliki heading (<h1> - <h6>). Navigasi screen reader terganggu."
            })
            return

        levels = [int(h[1]) for h in headings]
        if levels.count(1) == 0:
            self.issues.append({
                "level": "FAIL",
                "rule": "WCAG 2.4.6 Heading Primer",
                "msg": "Halaman kehilangan tag <h1> utama sebagai konteks primer dokumen."
            })
        elif levels.count(1) > 1:
            self.issues.append({
                "level": "WARN",
                "rule": "Best Practice SEO/A11y",
                "msg": f"Ditemukan {levels.count(1)} elemen <h1>. Disarankan 1 <h1> per dokumen."
            })
        else:
            self.passes.append("Struktur memiliki tepat 1 buah <h1> primer.")

        for i in range(len(levels) - 1):
            curr_lvl, next_lvl = levels[i], levels[i + 1]
            if next_lvl > curr_lvl + 1:
                self.issues.append({
                    "level": "FAIL",
                    "rule": "WCAG 1.3.1 Skip Heading Level",
                    "msg": f"Hierarki heading melompat dari <h{curr_lvl}> langsung ke <h{next_lvl}>!"
                })

    def audit_interactive_elements(self) -> None:
        """Mendeteksi tombol palsu div/span dengan onclick tanpa peranan aksesibel."""
        fake_buttons = re.findall(r"<div[^>]*onclick=[^>]*>", self.raw_html, re.IGNORECASE)
        if fake_buttons:
            self.issues.append({
                "level": "FAIL",
                "rule": "WCAG 2.1.1 Keyboard Accessible",
                "msg": f"Ditemukan {len(fake_buttons)} tombol non-semantik (<div onclick=...>). Tidak fokusable via TAB!"
            })
        else:
            self.passes.append("Interaksi tombol menggunakan elemen asli (<button>) atau semantic tag.")

    def audit_forms(self) -> None:
        """Memverifikasi bahwa setiap input berasosiasi dengan label."""
        inputs = re.findall(r"<input\b([^>]*)>", self.raw_html, re.IGNORECASE)
        
        for inp in inputs:
            if 'type="hidden"' in inp.lower() or 'type="submit"' in inp.lower():
                continue
            id_match = re.search(r'id\s*=\s*(["\'])([\w\-]+)\1', inp)
            aria_label = re.search(r'aria-label(ledby)?', inp)
            
            if not id_match and not aria_label:
                self.issues.append({
                    "level": "FAIL",
                    "rule": "WCAG 3.3.2 Form Labels",
                    "msg": "Ditemukan <input> tanpa id terkait <label for=\"...\"> atau atribut aria-label."
                })
            else:
                self.passes.append("Input form terhubung dengan label identifikasi yang valid.")

    def run_all(self) -> None:
        self.audit_landmarks()
        self.audit_images()
        self.audit_headings()
        self.audit_interactive_elements()
        self.audit_forms()


def print_audit_report(engine: SemanticAuditEngine, title: str) -> None:
    section(f"Laporan Audit Aksesibilitas: {title}")
    
    for p in engine.passes:
        print(f"  {badge_pass(p)}")
        
    for issue in engine.issues:
        rule_name = issue['rule']
        msg_text = issue['msg']
        detail = f"[{rule_name}] {msg_text}"
        if issue["level"] == "FAIL":
            print(f"  {badge_fail(detail)}")
        else:
            print(f"  {badge_warn(detail)}")
            
    total = len(engine.passes) + len(engine.issues)
    score = int((len(engine.passes) / total) * 100) if total > 0 else 0
    
    score_color = TerminalColor.GREEN if score >= 80 else (TerminalColor.YELLOW if score >= 50 else TerminalColor.RED)
    print(f"\n  {TerminalColor.BOLD}Skor Aksesibilitas:{TerminalColor.RESET} {score_color}{score}/100{TerminalColor.RESET}")


def simulate_screen_reader(html_snippet: str) -> None:
    section("Simulasi Screen Reader (Speech Synthesis & Virtual Buffer)")
    print(f"{TerminalColor.DIM}Membaca apa yang didengar pengguna tuna netra saat menelusuri DOM:{TerminalColor.RESET}\n")
    
    if "header" in html_snippet:
        print(f"  {TerminalColor.YELLOW}[Voice Synth]{TerminalColor.RESET} \"Landmark banner, awal dari navigasi atas.\"")
    else:
        print(f"  {TerminalColor.RED}[Voice Synth]{TerminalColor.RESET} \"Div, tidak ada landmark peran pembuka.\"")
        
    if 'alt="Logo Resmi Toko Aksesibel"' in html_snippet:
        print(f"  {TerminalColor.YELLOW}[Voice Synth]{TerminalColor.RESET} \"Gambar: Logo Resmi Toko Aksesibel.\"")
    elif 'src="logo.png"' in html_snippet:
        print(f"  {TerminalColor.RED}[Voice Synth]{TerminalColor.RESET} \"Gambar: logo dot png (Nama file mentah, tidak informatif!)\"")
        
    if "<h1>" in html_snippet:
        print(f"  {TerminalColor.YELLOW}[Voice Synth]{TerminalColor.RESET} \"Heading level 1: Daftar Produk Unggulan.\"")
    elif 'class="judul"' in html_snippet:
        print(f"  {TerminalColor.RED}[Voice Synth]{TerminalColor.RESET} \"Div: Daftar Produk Unggulan (Bukan heading! Melewatkan shortcut keyboard 'H')\"")
        
    if "<button" in html_snippet:
        print(f"  {TerminalColor.YELLOW}[Voice Synth]{TerminalColor.RESET} \"Tombol: Beli Produk Kemeja Katun. Tekan spasi untuk aktivasi.\"")
    elif 'class="btn-beli"' in html_snippet:
        print(f"  {TerminalColor.RED}[Voice Synth]{TerminalColor.RESET} \"Teks biasa: Beli Sekarang (Tidak dapat dijangkau tombol TAB keyboard!)\"")


def simulate_color_contrast_tool() -> None:
    section("Simulasi WCAG 2.1 Color Contrast Checker")
    pairs = [
        ("Teks Abu Terang di Background Putih", (180, 180, 180), (255, 255, 255), "Anti-pattern umum"),
        ("Teks Abu Sedang di Background Putih", (115, 115, 115), (255, 255, 255), "Batas WCAG AA Normal Text"),
        ("Teks Hitam Elegan di Background Putih", (17, 24, 39), (255, 255, 255), "Sangat Kontras & Ideal"),
        ("Teks Biru Link di Background Abu", (37, 99, 235), (243, 244, 246), "Link Semantik"),
        ("Teks Kuning di Background Putih", (250, 204, 21), (255, 255, 255), "Kontras Sangat Buruk"),
    ]
    
    print(f"  {'Pasangan Warna':<35} | {'Rasio':<8} | {'Status WCAG AA':<15} | {'Status AAA':<10}")
    print("  " + "-" * 75)
    
    for label, fg, bg, note in pairs:
        ratio = calculate_contrast_ratio(fg, bg)
        pass_aa = ratio >= 4.5
        pass_aaa = ratio >= 7.0
        
        aa_badge = f"{TerminalColor.GREEN}PASS (>=4.5){TerminalColor.RESET}" if pass_aa else f"{TerminalColor.RED}FAIL (<4.5){TerminalColor.RESET}"
        aaa_badge = f"{TerminalColor.GREEN}PASS{TerminalColor.RESET}" if pass_aaa else f"{TerminalColor.DIM}FAIL{TerminalColor.RESET}"
        
        print(f"  {label:<35} | {ratio:>5.2f}:1  | {aa_badge:<24} | {aaa_badge:<18}")


def interactive_menu() -> None:
    while True:
        header("LAB INTERAKTIF: SEMANTIK HTML5 & AKSESIBILITAS WEB")
        print(f"  {TerminalColor.BOLD}[1]{TerminalColor.RESET} Jalankan Audit pada Kode HTML Non-Semantik (Div-Soup Bad Practice)")
        print(f"  {TerminalColor.BOLD}[2]{TerminalColor.RESET} Jalankan Audit pada Kode HTML5 Semantik (WCAG 2.1 AA Compliant)")
        print(f"  {TerminalColor.BOLD}[3]{TerminalColor.RESET} Simulasi Audio Screen Reader (Perbandingan Navigasi Tunarungu/Netra)")
        print(f"  {TerminalColor.BOLD}[4]{TerminalColor.RESET} Kalkulator Rasio Kontras Warna WCAG (Contrast Ratio Formula)")
        print(f"  {TerminalColor.BOLD}[5]{TerminalColor.RESET} Panduan Ringkas Aturan Inti Semantik HTML5")
        print(f"  {TerminalColor.BOLD}[0]{TerminalColor.RESET} Keluar dari Lab")
        print("-" * 65)
        
        try:
            choice = input(f"{TerminalColor.CYAN}Pilih opsi menu [0-5]: {TerminalColor.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari sesi latihan.")
            break
            
        if choice == "1":
            engine = SemanticAuditEngine(SAMPLE_BAD_HTML)
            engine.run_all()
            print_audit_report(engine, "HTML Non-Semantik (Div-Soup)")
        elif choice == "2":
            engine = SemanticAuditEngine(SAMPLE_GOOD_HTML)
            engine.run_all()
            print_audit_report(engine, "HTML5 Semantik Modern")
        elif choice == "3":
            print(f"\n{TerminalColor.RED}=== Menjalankan Audio Screen Reader pada Div-Soup ==={TerminalColor.RESET}")
            simulate_screen_reader(SAMPLE_BAD_HTML)
            print(f"\n{TerminalColor.GREEN}=== Menjalankan Audio Screen Reader pada Semantik HTML5 ==={TerminalColor.RESET}")
            simulate_screen_reader(SAMPLE_GOOD_HTML)
        elif choice == "4":
            simulate_color_contrast_tool()
        elif choice == "5":
            section("Prinsip Utama Semantik HTML5 & Aksesibilitas")
            info_item("1. Gunakan Native Tag", "Gunakan <button> bukan <div onclick>, <nav> bukan <div class=\"nav\">.")
            info_item("2. Alt Text Gambar", "Setiap <img> wajib memiliki 'alt'. Kosongkan (alt=\"\") HANYA jika murni dekoratif.")
            info_item("3. Hierarki Heading", "Hanya satu <h1> per laman; jangan pernah melompat dari <h1> langsung ke <h3>.")
            info_item("4. Form & Input Label", "Selalu kaitkan <label for=\"id_input\"> dengan <input id=\"id_input\">.")
            info_item("5. Kontras Warna", "Minimal rasio kontras 4.5:1 untuk teks standar (WCAG AA).")
        elif choice == "0":
            print(f"\n{TerminalColor.GREEN}Selamat belajar! Fondasi semantik HTML5 siap diterapkan.{TerminalColor.RESET}\n")
            break
        else:
            print(f"\n{TerminalColor.RED}Pilihan tidak valid. Silakan coba lagi.{TerminalColor.RESET}")


def run_automated_suite() -> None:
    """Mode non-interaktif saat dijalankan di pipeline CI atau lingkungan headless."""
    header("SUITE AUDIT OTOMATIS: FONDASI SEMANTIK HTML5 & AKSESIBILITAS")
    
    engine_bad = SemanticAuditEngine(SAMPLE_BAD_HTML)
    engine_bad.run_all()
    print_audit_report(engine_bad, "Uji Sampel Div-Soup (Ekspektasi: Banyak Isu)")
    
    engine_good = SemanticAuditEngine(SAMPLE_GOOD_HTML)
    engine_good.run_all()
    print_audit_report(engine_good, "Uji Sampel Standar Semantik (Ekspektasi: 100/100)")
    
    simulate_color_contrast_tool()
    simulate_screen_reader(SAMPLE_GOOD_HTML)
    print(f"\n{TerminalColor.GREEN}{TerminalColor.BOLD}[SUKSES] Semua modul simulasi fondasi berhasil dieksekusi.{TerminalColor.RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_automated_suite()
    elif not sys.stdin.isatty():
        run_automated_suite()
    else:
        interactive_menu()
