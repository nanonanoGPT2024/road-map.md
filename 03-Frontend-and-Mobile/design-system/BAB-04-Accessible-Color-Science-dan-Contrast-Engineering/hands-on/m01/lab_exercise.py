#!/usr/bin/env python3
"""
BAB-04: Accessible Color Science & Contrast Engineering
Hands-on Lab Exercise (Modul 01): Color Science, Luminance & Contrast Analyzer

Topik yang disimulasikan:
1. Konversi Linearisasi sRGB & Perhitungan Relative Luminance (WCAG 2.1 Standar CIE 1931).
2. Perhitungan Rasio Kontras WCAG 2.1 (Algoritma (L1 + 0.05) / (L2 + 0.05)).
3. Evaluasi Kepatuhan Aksesibilitas (WCAG AA Normal, AAA Normal, Large Text, UI Components).
4. Simulasi Model APCA (Accessible Perceptual Contrast Algorithm) Dasar (L* Perceptual).
5. Mesin Audit Palet Token Desain Sistem Interaktif dengan Rendering ANSI Truecolor 24-bit.
"""

from __future__ import annotations
import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ============================================================================
# 1. STRUKTUR DATA & MODEL WARNA
# ============================================================================

@dataclass(frozen=True)
class RGBColor:
    r: int  # 0 - 255
    g: int  # 0 - 255
    b: int  # 0 - 255

    @classmethod
    def from_hex(cls, hex_str: str) -> RGBColor:
        clean_hex = hex_str.strip().lstrip("#")
        if len(clean_hex) == 3:
            clean_hex = "".join([c * 2 for c in clean_hex])
        if len(clean_hex) != 6:
            raise ValueError(f"Hex color format tidak valid: {hex_str}")
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
        return cls(r, g, b)

    def to_hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def to_ansi_fg(self) -> str:
        return f"\033[38;2;{self.r};{self.g};{self.b}m"

    def to_ansi_bg(self) -> str:
        return f"\033[48;2;{self.r};{self.g};{self.b}m"


@dataclass
class ColorToken:
    name: str
    category: str
    color: RGBColor
    role_description: str


@dataclass
class WCAGAuditResult:
    fg_token: ColorToken
    bg_token: ColorToken
    fg_luminance: float
    bg_luminance: float
    ratio: float
    apca_approx: float
    pass_aa_normal: bool    # >= 4.5:1
    pass_aaa_normal: bool   # >= 7.0:1
    pass_aa_large: bool     # >= 3.0:1
    pass_ui_component: bool # >= 3.0:1


# ============================================================================
# 2. COLOR SCIENCE & ALGORITMA PERHITUNGAN KONTRAK
# ============================================================================

def srgb_channel_to_linear(channel_8bit: int) -> float:
    """
    Mengonversi kanal 8-bit sRGB (0-255) ke nilai linear (0.0 - 1.0)
    sesuai spesifikasi IEC 61966-2-1 dan W3C WCAG 2.1.
    """
    c_srgb = channel_8bit / 255.0
    if c_srgb <= 0.04045:
        return c_srgb / 12.92
    else:
        return math.pow((c_srgb + 0.055) / 1.055, 2.4)


def calculate_relative_luminance(color: RGBColor) -> float:
    """
    Menghitung Relative Luminance (L) berdasarkan kurva sensitivitas fotopik mata manusia
    (CIE 1931: R=0.2126, G=0.7152, B=0.0722).
    """
    r_lin = srgb_channel_to_linear(color.r)
    g_lin = srgb_channel_to_linear(color.g)
    b_lin = srgb_channel_to_linear(color.b)
    return (0.2126 * r_lin) + (0.7152 * g_lin) + (0.0722 * b_lin)


def calculate_wcag21_contrast(fg: RGBColor, bg: RGBColor) -> Tuple[float, float, float]:
    """
    Menghitung rasio kontras WCAG 2.1 antara Foreground dan Background.
    Return: (contrast_ratio, fg_luminance, bg_luminance)
    Formula: (L1 + 0.05) / (L2 + 0.05) di mana L1 >= L2.
    """
    l_fg = calculate_relative_luminance(fg)
    l_bg = calculate_relative_luminance(bg)

    l1 = max(l_fg, l_bg)
    l2 = min(l_fg, l_bg)

    ratio = (l1 + 0.05) / (l2 + 0.05)
    return round(ratio, 2), l_fg, l_bg


def calculate_perceptual_lightness(luminance: float) -> float:
    """
    Menghitung persepsi kecerahan CIELAB L* (perceptual lightness)
    dari nilai relative luminance (Y / Yn).
    """
    if luminance <= (216.0 / 24389.0):  # (6/29)^3
        return luminance * (24389.0 / 27.0) / 100.0  # Normalized 0.0 - 1.0
    else:
        return (1.16 * math.pow(luminance, 1.0 / 3.0) - 0.16)


def estimate_apca_contrast(fg: RGBColor, bg: RGBColor) -> float:
    """
    Aproksimasi model APCA (Accessible Perceptual Contrast Algorithm - WCAG 3.0 draft).
    Menghasilkan Lightness Contrast (Lc) berbasis polaritas (negatif jika dark on light).
    """
    l_fg = calculate_relative_luminance(fg)
    l_bg = calculate_relative_luminance(bg)

    # Perceptual power response
    y_fg = math.pow(l_fg, 0.56) if l_fg > 0.0 else 0.0
    y_bg = math.pow(l_bg, 0.56) if l_bg > 0.0 else 0.0

    # Polarity check: text on background
    if y_bg >= y_fg:
        # Dark text on light background (positive contrast in APCA convention)
        c = (y_bg - y_fg) * 100.0
    else:
        # Light text on dark background (negative contrast)
        c = (y_bg - y_fg) * 100.0

    return round(c, 1)


# ============================================================================
# 3. ANSI TERMINAL FORMATTER
# ============================================================================

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"


def badge(text: str, success: bool) -> str:
    if success:
        return f"\033[38;2;16;185;129;1m\u2714 {text}{RESET}"  # Emerald Green
    else:
        return f"\033[38;2;239;68;68;1m\u2718 {text}{RESET}"  # Red


def render_color_chip(fg: RGBColor, bg: RGBColor, sample_text: str = " Aa Sample ") -> str:
    """Merender kotak sampel visual di terminal menggunakan ANSI truecolor."""
    return f"{fg.to_ansi_fg()}{bg.to_ansi_bg()}{sample_text}{RESET}"


# ============================================================================
# 4. AUDIT ENGINE & SIMULATOR TOKEN DESIGN SYSTEM
# ============================================================================

def audit_pair(fg_token: ColorToken, bg_token: ColorToken) -> WCAGAuditResult:
    ratio, l_fg, l_bg = calculate_wcag21_contrast(fg_token.color, bg_token.color)
    apca_val = estimate_apca_contrast(fg_token.color, bg_token.color)

    return WCAGAuditResult(
        fg_token=fg_token,
        bg_token=bg_token,
        fg_luminance=l_fg,
        bg_luminance=l_bg,
        ratio=ratio,
        apca_approx=apca_val,
        pass_aa_normal=(ratio >= 4.5),
        pass_aaa_normal=(ratio >= 7.0),
        pass_aa_large=(ratio >= 3.0),
        pass_ui_component=(ratio >= 3.0),
    )


def build_default_design_system_tokens() -> List[ColorToken]:
    """Palet token design system standar enterprise (Light & Dark modes)."""
    return [
        ColorToken("text.primary.light", "Text", RGBColor.from_hex("#0F172A"), "Teks utama slate-900"),
        ColorToken("text.secondary.light", "Text", RGBColor.from_hex("#475569"), "Teks sekunder slate-600"),
        ColorToken("text.muted.light", "Text", RGBColor.from_hex("#94A3B8"), "Teks dinonaktifkan slate-400"),
        ColorToken("text.on-brand.light", "Text", RGBColor.from_hex("#FFFFFF"), "Teks putih pada background brand"),
        ColorToken("surface.canvas.light", "Surface", RGBColor.from_hex("#FFFFFF"), "Background utama aplikasi"),
        ColorToken("surface.muted.light", "Surface", RGBColor.from_hex("#F1F5F9"), "Background card/surface sekunder"),
        ColorToken("brand.primary.light", "Brand", RGBColor.from_hex("#2563EB"), "Aksen tombol & link utama (blue-600)"),
        ColorToken("feedback.danger.light", "Feedback", RGBColor.from_hex("#DC2626"), "Error state teks & tombol (red-600)"),
        ColorToken("feedback.warning.light", "Feedback", RGBColor.from_hex("#F59E0B"), "Warning state (amber-500)"),
        
        # Dark Mode Tokens
        ColorToken("text.primary.dark", "Text Dark", RGBColor.from_hex("#F8FAFC"), "Teks utama dark slate-50"),
        ColorToken("text.secondary.dark", "Text Dark", RGBColor.from_hex("#94A3B8"), "Teks sekunder dark slate-400"),
        ColorToken("surface.canvas.dark", "Surface Dark", RGBColor.from_hex("#0B0F19"), "Background dark canvas"),
        ColorToken("surface.card.dark", "Surface Dark", RGBColor.from_hex("#1E293B"), "Surface container dark slate-800"),
        ColorToken("brand.primary.dark", "Brand Dark", RGBColor.from_hex("#3B82F6"), "Aksen brand dark mode (blue-500)"),
    ]


def print_header(title: str) -> None:
    print(f"\n{BOLD}\033[38;2;59;130;246m" + "=" * 80 + f"{RESET}")
    print(f"{BOLD}\033[38;2;147;197;253m  {title.upper()}{RESET}")
    print(f"{BOLD}\033[38;2;59;130;246m" + "=" * 80 + f"{RESET}\n")


def display_token_registry(tokens: List[ColorToken]) -> None:
    print_header("1. Registry Token Desain & Nilai Luminance")
    print(f"{'Token Name':<26} {'Category':<14} {'Hex':<9} {'Luminance (L)':<16} {'Sample Chip'}")
    print("-" * 80)
    for tok in tokens:
        lum = calculate_relative_luminance(tok.color)
        chip = render_color_chip(
            fg=RGBColor(255, 255, 255) if lum < 0.18 else RGBColor(0, 0, 0),
            bg=tok.color,
            sample_text=f"  {tok.color.to_hex()}  "
        )
        print(f"{tok.name:<26} {tok.category:<14} {tok.color.to_hex():<9} {lum:<16.4f} {chip}")


def run_system_audit_matrix(tokens: List[ColorToken]) -> None:
    print_header("2. Audit Matriks Kontras Aksesibilitas (WCAG 2.1 & APCA)")

    # Definisi pairing kritis yang perlu dievaluasi
    critical_pairs = [
        # Light Mode Tests
        ("text.primary.light", "surface.canvas.light"),
        ("text.secondary.light", "surface.canvas.light"),
        ("text.muted.light", "surface.canvas.light"),
        ("text.on-brand.light", "brand.primary.light"),
        ("brand.primary.light", "surface.canvas.light"),
        ("feedback.danger.light", "surface.canvas.light"),
        ("feedback.warning.light", "surface.canvas.light"),
        ("text.primary.light", "surface.muted.light"),
        
        # Dark Mode Tests
        ("text.primary.dark", "surface.canvas.dark"),
        ("text.secondary.dark", "surface.canvas.dark"),
        ("brand.primary.dark", "surface.canvas.dark"),
        ("text.primary.dark", "surface.card.dark"),
    ]

    token_map: Dict[str, ColorToken] = {t.name: t for t in tokens}

    header_cols = (
        f"{'Pairing (FG vs BG)':<40} {'Sample':<14} {'Ratio':<8} "
        f"{'AA-Norm':<10} {'AAA-Norm':<10} {'UI-Comp':<10} {'APCA (Lc)':<10}"
    )
    print(header_cols)
    print("-" * 105)

    failure_count = 0
    total_evaluated = 0

    for fg_name, bg_name in critical_pairs:
        if fg_name not in token_map or bg_name not in token_map:
            continue

        fg_tok = token_map[fg_name]
        bg_tok = token_map[bg_name]
        res = audit_pair(fg_tok, bg_tok)
        total_evaluated += 1

        pair_label = f"{fg_tok.name} on {bg_tok.name}"
        if len(pair_label) > 38:
            pair_label = pair_label[:35] + "..."

        chip = render_color_chip(fg_tok.color, bg_tok.color, " Contoh Teks ")
        aa_badge = badge("AA", res.pass_aa_normal)
        aaa_badge = badge("AAA", res.pass_aaa_normal)
        ui_badge = badge("3:1", res.pass_ui_component)

        apca_str = f"{res.apca_approx:+5.1f}"

        print(
            f"{pair_label:<40} {chip:<14} {res.ratio:>5.2f}:1  "
            f"{aa_badge:<19} {aaa_badge:<19} {ui_badge:<19} {apca_str:<10}"
        )

        if not res.pass_aa_normal:
            failure_count += 1

    print("-" * 105)
    print(f"\n{BOLD}Ringkasan Audit Aksesibilitas:{RESET}")
    print(f"Total Pair Dievaluasi : {total_evaluated}")
    print(f"Lolos Standar AA Normal : {total_evaluated - failure_count}")
    print(f"Gagal Standar AA Normal : {failure_count}")

    if failure_count > 0:
        print(f"\n{BOLD}\033[38;2;239;68;68m[PERINGATAN SISTEM DESAIN]{RESET} Terdapat token yang melanggar WCAG 2.1 AA.")
        print("Rekomendasi Rekayasa Kontras:")
        print("  1. Tingkatkan darkness pada 'text.muted' atau gunakan hanya untuk teks dekoratif.")
        print("  2. 'feedback.warning.light' (#F59E0B) membutuhkan dark background atau border penegas.")
        print("  3. Untuk 'brand.primary.light' sebagai teks link di atas canvas, rasio minimal wajib 4.5:1.")


def interactive_contrast_calculator() -> None:
    print_header("3. Kalkulator Kontras Interaktif (Custom Hex Input)")
    print("Masukkan dua kode hex (contoh: #0F172A dan #FFFFFF) untuk pengujian instan.")

    try:
        fg_input = input(f"{BOLD}Masukkan Hex Foreground [Default #2563EB]: {RESET}").strip()
        if not fg_input:
            fg_input = "#2563EB"

        bg_input = input(f"{BOLD}Masukkan Hex Background [Default #FFFFFF]: {RESET}").strip()
        if not bg_input:
            bg_input = "#FFFFFF"

        fg = RGBColor.from_hex(fg_input)
        bg = RGBColor.from_hex(bg_input)

        ratio, l_fg, l_bg = calculate_wcag21_contrast(fg, bg)
        apca_val = estimate_apca_contrast(fg, bg)

        print(f"\n{BOLD}Hasil Pengukuran Presisi Color Science:{RESET}")
        print(f"  \u2022 Foreground Hex       : {fg.to_hex()} (Luminance L = {l_fg:.5f})")
        print(f"  \u2022 Background Hex       : {bg.to_hex()} (Luminance L = {l_bg:.5f})")
        print(f"  \u2022 Rasio Kontras WCAG   : {BOLD}{ratio:.2f}:1{RESET}")
        print(f"  \u2022 Estimasi Skor APCA    : {BOLD}{apca_val:+5.1f} Lc{RESET}")

        sample = render_color_chip(fg, bg, f"   Pratinjau Teks Aksesibel: {fg.to_hex()} di atas {bg.to_hex()}   ")
        print(f"\n  Pratinjau Visual Terminal:")
        print(f"  {sample}\n")

        print("  Status Kepatuhan WCAG 2.1:")
        print(f"    - WCAG AA Normal Text (>= 4.5:1)     : {badge('LULUS', ratio >= 4.5)}")
        print(f"    - WCAG AAA Normal Text (>= 7.0:1)    : {badge('LULUS', ratio >= 7.0)}")
        print(f"    - WCAG AA Large Text (>= 3.0:1)      : {badge('LULUS', ratio >= 3.0)}")
        print(f"    - UI Components & Borders (>= 3.0:1) : {badge('LULUS', ratio >= 3.0)}")

    except Exception as err:
        print(f"\033[38;2;239;68;68mTerjadi kesalahan input: {err}{RESET}")


def main() -> None:
    print(f"\n{BOLD}\033[38;2;99;102;241m================================================================================")
    print("   DESAIN SISTEM ELEMEN DASAR: SIMULATOR & AUDITOR ILMU WARNA AKSESIBEL")
    print("   Modul 01: Fondasi Sains Kontras, CIE 1931 Luminance, & Algoritma WCAG 2.1")
    print(f"================================================================================{RESET}\n")

    tokens = build_default_design_system_tokens()

    # Eksekusi bagian audit otomatis
    display_token_registry(tokens)
    run_system_audit_matrix(tokens)

    # Interaksi pengguna opsional jika berjalan di TTY interaktif
    if sys.stdin.isatty():
        print()
        choice = input(f"{BOLD}Jalankan kalkulator kontras kustom interaktif? (y/n) [default: y]: {RESET}").strip().lower()
        if choice in ("", "y", "yes"):
            interactive_contrast_calculator()
    else:
        print(f"\n{DIM}[Info: Non-interactive environment terdeteksi. Melewati input interaktif.]{RESET}")

    print(f"\n{BOLD}\033[38;2;16;185;129m\u2714 Simulasi audit color science selesai secara sukses.{RESET}\n")


if __name__ == "__main__":
    main()
