#!/usr/bin/env python3
"""
Lab Exercise: Visual Systems, Typography Scale & Color Science Engine
BAB-05: Visual Systems, Typography, dan Color Science

Simulasi teknis mandiri:
1. Color Science & WCAG 2.1 Contrast Ratio Matrix (sRGB to linear, relative luminance)
2. Typography Modular Scale & Baseline Grid Alignment (8pt / 4pt grid system)
3. Design Token Generator & ANSI TrueColor Terminal Preview
"""

import sys
import math
from typing import Dict, List, Tuple, Optional

# --- ANSI Styling Helpers ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

def fg_rgb(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

def bg_rgb(r: int, g: int, b: int) -> str:
    return f"\033[48;2;{r};{g};{b}m"

def badge_pass(text: str = "PASS") -> str:
    return f"{bg_rgb(34, 139, 34)}{fg_rgb(255, 255, 255)}{BOLD} {text} {RESET}"

def badge_fail(text: str = "FAIL") -> str:
    return f"{bg_rgb(178, 34, 34)}{fg_rgb(255, 255, 255)}{BOLD} {text} {RESET}"

def badge_warn(text: str = "WARN") -> str:
    return f"{bg_rgb(204, 153, 0)}{fg_rgb(0, 0, 0)}{BOLD} {text} {RESET}"

# --- 1. Color Science & WCAG 2.1 Engine ---

class Color:
    def __init__(self, hex_code: str, name: str = ""):
        self.hex_code = hex_code.strip().lstrip("#").upper()
        if len(self.hex_code) == 3:
            self.hex_code = "".join([c * 2 for c in self.hex_code])
        if len(self.hex_code) != 6:
            raise ValueError(f"Invalid HEX color: #{hex_code}")
        
        self.name = name or f"#{self.hex_code}"
        self.r = int(self.hex_code[0:2], 16)
        self.g = int(self.hex_code[2:4], 16)
        self.b = int(self.hex_code[4:6], 16)

    @property
    def rgb(self) -> Tuple[int, int, int]:
        return (self.r, self.g, self.b)

    @property
    def relative_luminance(self) -> float:
        """
        Calculates relative luminance according to WCAG 2.1:
        sRGB channel to linear channel with gamma correction:
        C_linear = C_srgb / 12.92 if C_srgb <= 0.04045 else ((C_srgb + 0.055) / 1.055) ^ 2.4
        L = 0.2126 * R_linear + 0.7152 * G_linear + 0.0722 * B_linear
        """
        def to_linear(c_byte: int) -> float:
            c = c_byte / 255.0
            if c <= 0.04045:
                return c / 12.92
            return math.pow((c + 0.055) / 1.055, 2.4)

        r_lin = to_linear(self.r)
        g_lin = to_linear(self.g)
        b_lin = to_linear(self.b)
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    def contrast_ratio(self, other: "Color") -> float:
        """
        Calculates WCAG 2.1 contrast ratio: (L1 + 0.05) / (L2 + 0.05)
        where L1 is the lighter color and L2 is the darker color.
        """
        l1 = self.relative_luminance
        l2 = other.relative_luminance
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    def wcag_audit(self, background: "Color") -> Dict[str, bool]:
        ratio = self.contrast_ratio(background)
        return {
            "ratio": ratio,
            "AA_normal": ratio >= 4.5,
            "AA_large": ratio >= 3.0,
            "AAA_normal": ratio >= 7.0,
            "AAA_large": ratio >= 4.5,
        }

    def render_chip(self, label: Optional[str] = None) -> str:
        text = label if label else f" #{self.hex_code} "
        # determine ideal text contrast for chip label
        white = Color("FFFFFF")
        black = Color("000000")
        fg = fg_rgb(255, 255, 255) if self.contrast_ratio(white) >= self.contrast_ratio(black) else fg_rgb(0, 0, 0)
        return f"{bg_rgb(self.r, self.g, self.b)}{fg}{text}{RESET}"

# --- 2. Typography Modular Scale Engine ---

SCALES = {
    "Minor Second": 1.067,
    "Major Second": 1.125,
    "Minor Third": 1.200,
    "Major Third": 1.250,
    "Perfect Fourth": 1.333,
    "Augmented Fourth": 1.414,
    "Perfect Fifth": 1.500,
    "Golden Ratio": 1.618,
}

class ModularScale:
    def __init__(self, base_px: float = 16.0, ratio_name: str = "Major Third", baseline_grid: int = 4):
        self.base_px = base_px
        self.ratio_name = ratio_name
        self.ratio = SCALES.get(ratio_name, 1.250)
        self.baseline_grid = baseline_grid

    def calculate_step(self, step: int) -> float:
        return self.base_px * math.pow(self.ratio, step)

    def calculate_line_height(self, font_size_px: float) -> int:
        """
        Computes ideal line-height adhering to baseline vertical rhythm.
        Multiplier typically ranges 1.2 - 1.5 based on font size.
        """
        raw_lh = font_size_px * 1.35
        # Round up to next baseline grid unit
        grid = self.baseline_grid
        aligned_lh = int(math.ceil(raw_lh / grid) * grid)
        # Ensure line-height is strictly larger than font size
        while aligned_lh <= font_size_px:
            aligned_lh += grid
        return aligned_lh

    def generate_type_scale(self) -> List[Dict]:
        steps = [
            ("Display", 4),
            ("Heading 1 (h1)", 3),
            ("Heading 2 (h2)", 2),
            ("Heading 3 (h3)", 1),
            ("Body Regular (p)", 0),
            ("Caption / Small", -1),
            ("Microcopy", -2),
        ]
        results = []
        for name, step in steps:
            size_px = self.calculate_step(step)
            lh_px = self.calculate_line_height(size_px)
            results.append({
                "role": name,
                "step": step,
                "size_px": round(size_px, 2),
                "rem": round(size_px / self.base_px, 3),
                "line_height_px": lh_px,
                "relative_lh": round(lh_px / size_px, 2)
            })
        return results

# --- 3. Interactive CLI Displays ---

def print_header(title: str):
    print(f"\n{BOLD}{fg_rgb(79, 140, 255)}" + ("━" * 70))
    print(f" {title.upper()}")
    print(("━" * 70) + f"{RESET}")

def run_color_science_demo():
    print_header("1. Color Science & WCAG 2.1 Contrast Matrix Audit")
    
    palette = [
        Color("FFFFFF", "Surface-Light"),
        Color("0F172A", "Surface-Dark (Slate-900)"),
        Color("2563EB", "Primary (Blue-600)"),
        Color("10B981", "Success (Emerald-500)"),
        Color("EF4444", "Danger (Red-500)"),
        Color("F59E0B", "Warning (Amber-500)"),
        Color("64748B", "Muted-Text (Slate-500)"),
    ]

    print(f"{BOLD}Design System Color Swatches:{RESET}")
    for c in palette:
        lum = c.relative_luminance
        print(f"  {c.render_chip(f' {c.name:<24} ')}  RGB: {str(c.rgb):<16}  Luminance: {lum:.4f}")
    
    print(f"\n{BOLD}WCAG 2.1 Accessibility Matrix Evaluation:{RESET}\n")
    headers = f"{'Foreground':<18} {'Background':<18} {'Ratio':<8} {'AA Norm':<9} {'AA Lrg':<8} {'AAA Norm':<9} {'Status'}"
    print(f"{DIM}{headers}{RESET}")
    print("-" * 80)

    test_pairs = [
        (Color("0F172A", "Slate-900"), Color("FFFFFF", "White")),
        (Color("64748B", "Slate-500"), Color("FFFFFF", "White")),
        (Color("2563EB", "Blue-600"), Color("FFFFFF", "White")),
        (Color("FFFFFF", "White"), Color("2563EB", "Blue-600")),
        (Color("10B981", "Emerald-500"), Color("FFFFFF", "White")),
        (Color("EF4444", "Red-500"), Color("FFFFFF", "White")),
        (Color("F59E0B", "Amber-500"), Color("0F172A", "Slate-900")),
        (Color("64748B", "Slate-500"), Color("0F172A", "Slate-900")),
    ]

    for fg_c, bg_c in test_pairs:
        audit = fg_c.wcag_audit(bg_c)
        ratio = audit["ratio"]
        aa_n = badge_pass(" PASS ") if audit["AA_normal"] else badge_fail(" FAIL ")
        aa_l = badge_pass(" PASS ") if audit["AA_large"] else badge_fail(" FAIL ")
        aaa_n = badge_pass(" PASS ") if audit["AAA_normal"] else badge_fail(" FAIL ")
        
        status_summary = badge_pass("WCAG AA") if audit["AA_normal"] else (badge_warn("LARGE ONLY") if audit["AA_large"] else badge_fail("NON-COMPLIANT"))

        fg_chip = f"{fg_rgb(fg_c.r, fg_c.g, fg_c.b)}■ {fg_c.name}{RESET}"
        bg_chip = f"{fg_rgb(bg_c.r, bg_c.g, bg_c.b)}■ {bg_c.name}{RESET}"

        print(f"{fg_chip:<28} {bg_chip:<28} {ratio:>5.2f}:1  {aa_n:<9} {aa_l:<8} {aaa_n:<9} {status_summary}")

def run_typography_demo():
    print_header("2. Modular Typography Scale & Baseline Vertical Rhythm")
    
    print(f"{BOLD}Active Presets: Base = 16px, Ratio = 1.250 (Major Third), Grid = 4px/8px Baseline{RESET}\n")
    ms = ModularScale(base_px=16.0, ratio_name="Major Third", baseline_grid=4)
    tokens = ms.generate_type_scale()

    fmt = "{:<18} {:<6} {:<11} {:<9} {:<15} {:<12}"
    print(f"{DIM}" + fmt.format("Role", "Step", "Font Size", "REM", "Line-Height", "Ratio (LH/Size)") + f"{RESET}")
    print("-" * 75)

    for item in tokens:
        step_str = f"{item['step']:+d}"
        size_str = f"{item['size_px']:.2f}px"
        rem_str = f"{item['rem']:.3f}rem"
        lh_str = f"{item['line_height_px']}px (grid-aligned)"
        rel_lh = f"{item['relative_lh']:.2f}x"
        
        # Simulated visual rendering with ANSI styling
        color_weight = BOLD if item["step"] >= 1 else RESET
        print(fmt.format(f"{color_weight}{item['role']}{RESET}", step_str, size_str, rem_str, lh_str, rel_lh))

    print(f"\n{BOLD}Baseline Rhythm Visualizer Sample (4px Grid):{RESET}")
    for item in tokens[:4]:
        bar_len = int(item["line_height_px"] // 2)
        grid_ticks = "░" * bar_len
        print(f"  {item['role']:<18} |{fg_rgb(79, 140, 255)}{grid_ticks}{RESET}| {item['line_height_px']}px")

def run_interactive_contrast_checker():
    print_header("3. Interactive Color Contrast Diagnostic Utility")
    print("Test custom HEX color pairs for WCAG 2.1 compliance (e.g. #0F172A and #FFFFFF).\n")
    
    def prompt_color(prompt_text: str, default_hex: str) -> Color:
        raw = input(f"{BOLD}{prompt_text} [{default_hex}]: {RESET}").strip()
        hex_val = raw if raw else default_hex
        try:
            return Color(hex_val)
        except Exception as e:
            print(f"  {badge_warn('ERR')} Input tidak valid ({e}), fallback ke {default_hex}")
            return Color(default_hex)

    fg_col = prompt_color("Masukkan Text / Foreground HEX", "2563EB")
    bg_col = prompt_color("Masukkan Background HEX", "FFFFFF")

    audit = fg_col.wcag_audit(bg_col)
    ratio = audit["ratio"]

    print(f"\n{BOLD}=== HASIL AUDIT AKSESIBILITAS ==={RESET}")
    print(f"Visual Preview: {bg_rgb(bg_col.r, bg_col.g, bg_col.b)}{fg_rgb(fg_col.r, fg_col.g, fg_col.b)} Sample Typography Text ({fg_col.name} on {bg_col.name}) {RESET}")
    print(f"Contrast Ratio : {BOLD}{ratio:.2f}:1{RESET}")
    print(f"Luminance FG   : {fg_col.relative_luminance:.4f}")
    print(f"Luminance BG   : {bg_col.relative_luminance:.4f}")
    print("\nStandar Kepatuhan:")
    print(f"  - WCAG AA Normal Text (Min 4.5:1)  : {badge_pass('LOLOS') if audit['AA_normal'] else badge_fail('GAGAL')}")
    print(f"  - WCAG AA Large Text  (Min 3.0:1)  : {badge_pass('LOLOS') if audit['AA_large'] else badge_fail('GAGAL')}")
    print(f"  - WCAG AAA Normal Text (Min 7.0:1) : {badge_pass('LOLOS') if audit['AAA_normal'] else badge_fail('GAGAL')}")
    print(f"  - WCAG AAA Large Text  (Min 4.5:1) : {badge_pass('LOLOS') if audit['AAA_large'] else badge_fail('GAGAL')}")

def interactive_menu():
    while True:
        print_header("BAB-05 Product Design: Visual Systems & Color Science Lab")
        print("Pilih modul laboratorium:")
        print("  1. Evaluasi Color Science & Matriks Kontras WCAG 2.1 (Presisi sRGB)")
        print("  2. Generator Modular Typography Scale & Baseline Rhythm 4px/8px")
        print("  3. Custom Interactive Color Pair Contrast Checker")
        print("  4. Jalankan Semua Simulasi (Full Suite Demo)")
        print("  5. Keluar")
        
        try:
            choice = input(f"\n{BOLD}Pilihan Anda [1-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{DIM}Sesi dihentikan.{RESET}")
            break

        if choice == "1":
            run_color_science_demo()
        elif choice == "2":
            run_typography_demo()
        elif choice == "3":
            run_interactive_contrast_checker()
        elif choice == "4":
            run_color_science_demo()
            run_typography_demo()
            print_header("Simulasi Kustom Demo Standar")
            c1 = Color("3B82F6", "Tailwind-Blue-500")
            c2 = Color("0F172A", "Slate-900")
            print(f"Preview {c1.name} di {c2.name}: Kontras {c1.contrast_ratio(c2):.2f}:1")
        elif choice == "5":
            print(f"\n{fg_rgb(16, 185, 129)}✔ Lab selesai. Selamat belajar!{RESET}\n")
            break
        else:
            print(f"{badge_warn('INFO')} Pilihan tidak valid, silakan pilih angka 1-5.")

def main():
    # If stdin is not a tty (piped or non-interactive runner), run all demos without blocking
    if not sys.stdin.isatty() or "--demo" in sys.argv:
        print(f"{DIM}[Mode Non-Interaktif / CI terdeteksi: Menjalankan Full Suite Automation]{RESET}")
        run_color_science_demo()
        run_typography_demo()
        print(f"\n{badge_pass('SUCCESS')} Simulasi Visual Systems & Color Science berhasil dieksekusi 100% valid.\n")
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
