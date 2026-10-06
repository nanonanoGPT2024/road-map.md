#!/usr/bin/env python3
"""
Lab Exercise: Aksesibilitas Digital & Desain Inklusif Lanjutan (BAB-08)
Simulasi Teknis Fondasi:
  1. Kalkulasi Rasio Kontras Relatif WCAG 2.1/2.2 (Luminansi & Formula sRGB)
  2. Evaluasi Ambang Batas WCAG AA vs AAA (Normal vs Teks Besar vs Target Sentuh)
  3. Audit Aksesibilitas Komponen UI (AOM, Atribut ARIA, Focus Trap, Keyboard Flow)
  4. Simulasi Evaluasi Defisiensi Penglihatan Warna (Color Vision Deficiency - CVD)
"""

import sys
import math
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# --- Terminal ANSI Styling ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    FG_RED = "\033[91m"
    FG_GREEN = "\033[92m"
    FG_YELLOW = "\033[93m"
    FG_BLUE = "\033[94m"
    FG_MAGENTA = "\033[95m"
    FG_CYAN = "\033[96m"
    FG_WHITE = "\033[97m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

def print_header(title: str):
    width = 72
    print(f"\n{Style.FG_CYAN}{Style.BOLD}{'=' * width}")
    print(f" {title.center(width - 2)}")
    print(f"{'=' * width}{Style.RESET}")

def print_badge(text: str, success: bool, note: str = ""):
    badge = f"{Style.FG_GREEN}[PASS]{Style.RESET}" if success else f"{Style.FG_RED}[FAIL]{Style.RESET}"
    print(f"  {badge} {Style.BOLD}{text:<32}{Style.RESET} {Style.DIM}{note}{Style.RESET}")

# --- 1. Algoritma Kalkulasi Luminansi Relatif & Kontras WCAG ---
def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    cleaned = hex_str.strip().lstrip('#')
    if len(cleaned) == 3:
        cleaned = ''.join(c * 2 for c in cleaned)
    if len(cleaned) != 6:
        raise ValueError(f"Format hex tidak valid: {hex_str}")
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))

def srgb_channel_to_linear(val_8bit: int) -> float:
    """Linearisasi kurva sRGB sesuai standar WCAG 2.1/2.2."""
    c = val_8bit / 255.0
    if c <= 0.04045:
        return c / 12.92
    return math.pow((c + 0.055) / 1.055, 2.4)

def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Menghitung Luminansi Relatif (L) berdasarkan bobot spektral CIE."""
    r_lin = srgb_channel_to_linear(rgb[0])
    g_lin = srgb_channel_to_linear(rgb[1])
    b_lin = srgb_channel_to_linear(rgb[2])
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def calculate_contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Menghitung Rasio Kontras WCAG: (L1 + 0.05) / (L2 + 0.05)."""
    l1 = calculate_relative_luminance(hex_to_rgb(fg_hex))
    l2 = calculate_relative_luminance(hex_to_rgb(bg_hex))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

# --- 2. Data Structure & Model Komponen UI ---
@dataclass
class UIComponent:
    id: str
    name: str
    element_type: str
    fg_color: str
    bg_color: str
    font_size_pt: float
    is_bold: bool
    touch_target_dp: Tuple[int, int]
    role: Optional[str]
    aria_label: Optional[str]
    focusable: bool
    keyboard_trapped: bool
    has_focus_indicator: bool

@dataclass
class AuditResult:
    component: UIComponent
    contrast_ratio: float
    wcag_aa_text: bool
    wcag_aaa_text: bool
    wcag_aa_target_size: bool
    keyboard_accessible: bool
    aria_compliant: bool
    issues: List[str]

# --- 3. Accessibility Evaluator Engine ---
class AccessibilityAuditEngine:
    @staticmethod
    def audit_component(comp: UIComponent) -> AuditResult:
        issues = []
        ratio = calculate_contrast_ratio(comp.fg_color, comp.bg_color)
        
        # Ambang batas WCAG
        is_large_text = (comp.font_size_pt >= 18.0) or (comp.font_size_pt >= 14.0 and comp.is_bold)
        req_aa = 3.0 if is_large_text else 4.5
        req_aaa = 4.5 if is_large_text else 7.0
        
        pass_aa = ratio >= req_aa
        pass_aaa = ratio >= req_aaa
        
        if not pass_aa:
            issues.append(f"Gagal WCAG 1.4.3 (Kontras Rendah): Rasio {ratio:.2f}:1 di bawah syarat minimum {req_aa}:1")
        elif not pass_aaa:
            issues.append(f"Peringatan WCAG 1.4.6 (Tingkat AAA): Rasio {ratio:.2f}:1 belum memenuhi standar AAA ({req_aaa}:1)")
            
        # Target Sentuh (WCAG 2.5.5 / 2.5.8 Target Size)
        w, h = comp.touch_target_dp
        pass_target = (w >= 44 and h >= 44) if comp.element_type in ["button", "link", "input"] else True
        if not pass_target:
            issues.append(f"Gagal WCAG 2.5.8 (Target Size): Area interaktif {w}x{h}dp kurang dari rekomendasi 44x44dp")

        # Aksesibilitas Keyboard (WCAG 2.1.1 & 2.1.2)
        kbd_ok = True
        if comp.element_type in ["button", "link", "input"]:
            if not comp.focusable:
                kbd_ok = False
                issues.append("Gagal WCAG 2.1.1 (Keyboard Navigation): Komponen interaktif tidak dapat difokus via Tab")
            if comp.keyboard_trapped:
                kbd_ok = False
                issues.append("Pelanggaran Berat WCAG 2.1.2 (No Keyboard Trap): Pengguna terjebak dan tidak bisa navigasi keluar")
            if not comp.has_focus_indicator:
                kbd_ok = False
                issues.append("Gagal WCAG 2.4.7 (Focus Visible): Indikator cincin fokus visual tidak ada / di-outline:none")

        # Semantik ARIA (WCAG 4.1.2 Name, Role, Value)
        aria_ok = True
        if comp.element_type == "button" and not comp.aria_label and not comp.name:
            aria_ok = False
            issues.append("Gagal WCAG 4.1.2: Komponen tombol tidak memiliki Accessible Name yang dapat dibaca screen reader")
            
        return AuditResult(
            component=comp,
            contrast_ratio=ratio,
            wcag_aa_text=pass_aa,
            wcag_aaa_text=pass_aaa,
            wcag_aa_target_size=pass_target,
            keyboard_accessible=kbd_ok,
            aria_compliant=aria_ok,
            issues=issues
        )

# --- 4. Modul Simulasi Color Vision Deficiency (CVD) ---
def simulate_cvd_rgb(rgb: Tuple[int, int, int], cvd_type: str) -> Tuple[int, int, int]:
    """Aproksimasi matriks transformasi spektrum penglihatan warna."""
    r, g, b = [c / 255.0 for c in rgb]
    
    if cvd_type == "deuteranopia":  # Buta warna hijau (paling lazim)
        nr = 0.625 * r + 0.375 * g
        ng = 0.700 * r + 0.300 * g
        nb = 0.300 * g + 0.700 * b
    elif cvd_type == "protanopia":    # Buta warna merah
        nr = 0.567 * r + 0.433 * g
        ng = 0.558 * r + 0.442 * g
        nb = 0.242 * g + 0.758 * b
    elif cvd_type == "tritanopia":    # Buta warna biru-kuning
        nr = 0.950 * r + 0.050 * g
        ng = 0.433 * g + 0.567 * b
        nb = 0.475 * g + 0.525 * b
    else:
        nr, ng, nb = r, g, b
        
    clamp = lambda v: max(0, min(255, int(v * 255)))
    return (clamp(nr), clamp(ng), clamp(nb))

# --- 5. Dataset Mock Usecase Komponen Digital ---
SAMPLE_COMPONENTS = [
    UIComponent(
        id="cmp_01",
        name="Tombol Primary 'Simpan & Bayar'",
        element_type="button",
        fg_color="#FFFFFF",
        bg_color="#0052CC",
        font_size_pt=14.0,
        is_bold=True,
        touch_target_dp=(48, 48),
        role="button",
        aria_label="Simpan dan Lanjutkan ke Pembayaran",
        focusable=True,
        keyboard_trapped=False,
        has_focus_indicator=True
    ),
    UIComponent(
        id="cmp_02",
        name="Teks Peringatan Disclaimer",
        element_type="text",
        fg_color="#A0A0A0",
        bg_color="#FFFFFF",
        font_size_pt=10.0,
        is_bold=False,
        touch_target_dp=(0, 0),
        role=None,
        aria_label=None,
        focusable=False,
        keyboard_trapped=False,
        has_focus_indicator=False
    ),
    UIComponent(
        id="cmp_03",
        name="Modal Dialog Pop-up Promo",
        element_type="button",
        fg_color="#172B4D",
        bg_color="#FFE380",
        font_size_pt=12.0,
        is_bold=False,
        touch_target_dp=(32, 28),
        role="button",
        aria_label=None,
        focusable=True,
        keyboard_trapped=True,
        has_focus_indicator=False
    ),
    UIComponent(
        id="cmp_04",
        name="Judul Seksi Halaman (Hero Heading)",
        element_type="heading",
        fg_color="#091E42",
        bg_color="#F4F5F7",
        font_size_pt=24.0,
        is_bold=True,
        touch_target_dp=(0, 0),
        role="heading",
        aria_label="Pengaturan Akun dan Keamanan Inklusif",
        focusable=False,
        keyboard_trapped=False,
        has_focus_indicator=False
    )
]

# --- 6. Antarmuka CLI & Alur Interaktif ---
def run_full_suite():
    print_header("AUDIT LENGKAP SISTEM DESAIN INKLUSIF (WCAG 2.2)")
    engine = AccessibilityAuditEngine()
    
    total = len(SAMPLE_COMPONENTS)
    passed_aa = 0
    severe_issues = 0
    
    for idx, comp in enumerate(SAMPLE_COMPONENTS, 1):
        print(f"\n{Style.BOLD}[{idx}/{total}] Menganalisis: {comp.name} ({comp.id}){Style.RESET}")
        print(f"  {Style.DIM}Tipe: {comp.element_type} | Warna: FG={comp.fg_color}, BG={comp.bg_color} | Target: {comp.touch_target_dp[0]}x{comp.touch_target_dp[1]}dp{Style.RESET}")
        
        res = engine.audit_component(comp)
        
        print_badge("WCAG Contrast Ratio", res.wcag_aa_text, f"{res.contrast_ratio:.2f}:1")
        print_badge("WCAG AAA Enhanced", res.wcag_aaa_text, "Tingkat Kontras Tertinggi")
        print_badge("Touch Target Size (>=44dp)", res.wcag_aa_target_size, f"{comp.touch_target_dp[0]}x{comp.touch_target_dp[1]} dp")
        print_badge("Navigasi Bebas Trap", res.keyboard_accessible, "Akses Keyboard Utuh")
        print_badge("Aria & Semantik Layar", res.aria_compliant, f"Role: '{comp.role}'")
        
        if res.issues:
            print(f"  {Style.FG_YELLOW}Daftar Temuan Evaluasi:{Style.RESET}")
            for issue in res.issues:
                if "Berat" in issue or "Gagal" in issue:
                    severe_issues += 1
                print(f"    - {issue}")
        else:
            print(f"  {Style.FG_GREEN}Semua kepatuhan terpenuhi secara sempurna.{Style.RESET}")
            
        if res.wcag_aa_text and res.keyboard_accessible and res.wcag_aa_target_size:
            passed_aa += 1
            
    print_header("RINGKASAN SKOR AKSESIBILITAS")
    pct = (passed_aa / total) * 100
    color = Style.FG_GREEN if pct >= 75 else (Style.FG_YELLOW if pct >= 50 else Style.FG_RED)
    print(f"  Tingkat Kepatuhan WCAG AA: {color}{Style.BOLD}{pct:.1f}% ({passed_aa}/{total} Komponen Lolos){Style.RESET}")
    print(f"  Total Temuan Masalah Kritis : {Style.FG_RED if severe_issues else Style.FG_GREEN}{severe_issues}{Style.RESET}")

def interactive_contrast_calculator():
    print_header("KALKULATOR INTERAKTIF RASIO KONTRAS WCAG")
    print("Masukkan kode warna heksadesimal (contoh: #0052CC atau #FFFFFF):")
    try:
        fg = input(f"  {Style.BOLD}Warna Foreground (Teks) [Default #FFFFFF]: {Style.RESET}").strip() or "#FFFFFF"
        bg = input(f"  {Style.BOLD}Warna Background (Latar) [Default #172B4D]: {Style.RESET}").strip() or "#172B4D"
        
        ratio = calculate_contrast_ratio(fg, bg)
        print(f"\n{Style.FG_CYAN}{Style.BOLD}Hasil Perhitungan:{Style.RESET}")
        print(f"  Rasio Kontras: {Style.BOLD}{ratio:.2f}:1{Style.RESET}")
        
        print_badge("WCAG AA Normal Text (>=4.5:1)", ratio >= 4.5)
        print_badge("WCAG AA Large Text  (>=3.0:1)", ratio >= 3.0)
        print_badge("WCAG AAA Normal Text(>=7.0:1)", ratio >= 7.0)
        print_badge("WCAG AAA Large Text (>=4.5:1)", ratio >= 4.5)
        
        print(f"\n{Style.BOLD}Simulasi Penglihatan Defisiensi Warna (Foreground):{Style.RESET}")
        rgb = hex_to_rgb(fg)
        for cvd in ["deuteranopia", "protanopia", "tritanopia"]:
            sim = simulate_cvd_rgb(rgb, cvd)
            sim_hex = f"#{sim[0]:02X}{sim[1]:02X}{sim[2]:02X}"
            sim_ratio = calculate_contrast_ratio(sim_hex, bg)
            print(f"  - {cvd.capitalize():<14}: {sim_hex} (Rasio simulasi: {sim_ratio:.2f}:1)")
            
    except Exception as e:
        print(f"{Style.FG_RED}Terjadi kesalahan input: {e}{Style.RESET}")

def run_self_verification_test() -> bool:
    """Verifikasi otomatis logika matematis dan algoritma WCAG."""
    # Test 1: Hitam ke Putih wajib rasio 21:1
    bw_ratio = calculate_contrast_ratio("#000000", "#FFFFFF")
    assert math.isclose(bw_ratio, 21.0, rel_tol=1e-2), f"Expected 21:1, got {bw_ratio}"
    
    # Test 2: Warna identik wajib rasio 1:1
    ident_ratio = calculate_contrast_ratio("#4A90E2", "#4A90E2")
    assert math.isclose(ident_ratio, 1.0, rel_tol=1e-2), f"Expected 1:1, got {ident_ratio}"
    
    # Test 3: Luminansi relatif murni
    assert math.isclose(calculate_relative_luminance((255, 255, 255)), 1.0, rel_tol=1e-2)
    assert math.isclose(calculate_relative_luminance((0, 0, 0)), 0.0, rel_tol=1e-2)
    
    return True

def main():
    # Jalankan verifikasi internal terlebih dahulu
    try:
        run_self_verification_test()
    except AssertionError as err:
        print(f"{Style.FG_RED}Self-test verifikasi gagal: {err}{Style.RESET}")
        sys.exit(1)
        
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_full_suite()
        return

    while True:
        print_header("LAB SIMULATOR: AKSESIBILITAS DIGITAL & DESAIN INKLUSIF")
        print(f"  {Style.BOLD}1.{Style.RESET} Jalankan Audit Desain Komponen Otomatis")
        print(f"  {Style.BOLD}2.{Style.RESET} Kalkulator Kontras Interaktif & Simulasi CVD")
        print(f"  {Style.BOLD}3.{Style.RESET} Jalankan Tes Regresi Fondasi Matematika")
        print(f"  {Style.BOLD}4.{Style.RESET} Keluar")
        
        choice = input(f"\n{Style.FG_YELLOW}Pilih opsi menu [1-4]: {Style.RESET}").strip()
        if choice == "1":
            run_full_suite()
        elif choice == "2":
            interactive_contrast_calculator()
        elif choice == "3":
            if run_self_verification_test():
                print(f"\n{Style.FG_GREEN}{Style.BOLD}[VERIFIKASI BERHASIL] Seluruh algoritma formula WCAG terbukti akurat.{Style.RESET}")
        elif choice in ["4", "q", "exit"]:
            print(f"\n{Style.FG_CYAN}Terima kasih. Utamakan Aksesibilitas sejak awal perancangan!{Style.RESET}\n")
            break
        else:
            print(f"{Style.FG_RED}Opsi tidak dikenali.{Style.RESET}")
        time.sleep(0.5)

if __name__ == "__main__":
    main()
