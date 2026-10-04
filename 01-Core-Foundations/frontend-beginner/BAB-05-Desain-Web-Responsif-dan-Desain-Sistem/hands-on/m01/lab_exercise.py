#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Responsif Web Design & Design System Foundation
BAB 05: Desain Web Responsif dan Desain Sistem (Frontend Beginner)

Simulasi interaktif CLI mandiri menggunakan ANSI terminal formatting untuk memahami:
1. Breakpoint & Fluid Layout Engine (Mobile, Tablet, Desktop)
2. Fluid Typography Math Engine (CSS clamp calculation)
3. Design Token Architecture (Spacing, Typography scale, Color Semantic tokens)
4. Responsive Component Simulator (Card Grid breakdown per breakpoint)
"""

import sys
import time

# --- ANSI Color Palette ---
class TermColor:
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
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_DARK = "\033[100m"

# --- Design Tokens Definition ---
DESIGN_TOKENS = {
    "spacing": {
        "xs": "4px (0.25rem)",
        "sm": "8px (0.5rem)",
        "md": "16px (1.0rem)",
        "lg": "24px (1.5rem)",
        "xl": "32px (2.0rem)",
        "2xl": "48px (3.0rem)"
    },
    "breakpoints": {
        "mobile": {"min": 0, "max": 639, "name": "Mobile (<640px)"},
        "tablet": {"min": 640, "max": 1023, "name": "Tablet (640px - 1023px)"},
        "desktop": {"min": 1024, "max": 9999, "name": "Desktop (>=1024px)"}
    },
    "colors": {
        "primary": ("#3B82F6", "Blue 500", TermColor.FG_CYAN),
        "success": ("#10B981", "Emerald 500", TermColor.FG_GREEN),
        "warning": ("#F59E0B", "Amber 500", TermColor.FG_YELLOW),
        "danger": ("#EF4444", "Red 500", TermColor.FG_RED),
        "neutral_dark": ("#1F2937", "Gray 800", TermColor.FG_WHITE),
        "neutral_light": ("#F9FAFB", "Gray 50", TermColor.FG_WHITE)
    }
}

def print_header(title: str):
    width = 65
    print("\n" + TermColor.FG_CYAN + "=" * width + TermColor.RESET)
    print(f"{TermColor.BOLD}{TermColor.FG_WHITE}  {title.center(width - 4)}{TermColor.RESET}")
    print(TermColor.FG_CYAN + "=" * width + TermColor.RESET)

def print_badge(label: str, color_code: str):
    return f"{color_code}{TermColor.BOLD}[ {label} ]{TermColor.RESET}"

def get_breakpoint_category(viewport_width: int):
    for key, data in DESIGN_TOKENS["breakpoints"].items():
        if data["min"] <= viewport_width <= data["max"]:
            return key, data["name"]
    return "desktop", "Desktop (>=1024px)"

def simulate_clamp_typography(viewport_width: int, min_size: float = 1.0, max_size: float = 2.5, min_vp: int = 375, max_vp: int = 1280):
    """
    Simulasi CSS clamp(min_size, preferred_val, max_size)
    preferred_val = min_size + (max_size - min_size) * ((vp - min_vp) / (max_vp - min_vp))
    """
    if viewport_width <= min_vp:
        calculated_rem = min_size
    elif viewport_width >= max_vp:
        calculated_rem = max_size
    else:
        slope = (max_size - min_size) / (max_vp - min_vp)
        calculated_rem = min_size + slope * (viewport_width - min_vp)
    
    calculated_px = calculated_rem * 16.0
    return calculated_rem, calculated_px

def demo_viewport_debugger(width: int):
    bp_key, bp_label = get_breakpoint_category(width)
    rem_font, px_font = simulate_clamp_typography(width)
    
    # Layout Grid columns simulation
    if bp_key == "mobile":
        cols = 1
        container_padding = "16px"
        nav_state = "Collapsed (Hamburger Drawer)"
        badge = print_badge("MOBILE VIEW", TermColor.FG_YELLOW)
    elif bp_key == "tablet":
        cols = 2
        container_padding = "24px"
        nav_state = "Compact Horizontal / Sidebar Icon"
        badge = print_badge("TABLET VIEW", TermColor.FG_BLUE)
    else:
        cols = 4
        container_padding = "32px"
        nav_state = "Full Horizontal Expanded Navigation"
        badge = print_badge("DESKTOP VIEW", TermColor.FG_GREEN)

    print(f"\n{badge} Viewport Width: {TermColor.BOLD}{width}px{TermColor.RESET}")
    print(f"  {TermColor.FG_WHITE}Breakpoint Match :{TermColor.RESET} {TermColor.BOLD}{bp_label}{TermColor.RESET}")
    print(f"  {TermColor.FG_WHITE}Fluid Title Size :{TermColor.RESET} {rem_font:.3f}rem (~{px_font:.1f}px) [Formula: clamp(1.0rem, 3.5vw, 2.5rem)]")
    print(f"  {TermColor.FG_WHITE}Grid Layout      :{TermColor.RESET} {cols} Kolom (Card Flex/Grid Direction: {'Column' if cols == 1 else 'Row Wrap'})")
    print(f"  {TermColor.FG_WHITE}Container Padding:{TermColor.RESET} {container_padding}")
    print(f"  {TermColor.FG_WHITE}Navigation Mode  :{TermColor.RESET} {nav_state}")

    # Visual ASCII Card Layout Preview
    print(f"  {TermColor.FG_MAGENTA}Visual Layout Representation:{TermColor.RESET}")
    if cols == 1:
        print("    +------------------------------+")
        print("    | [Card 1] Full Width (100%)  |")
        print("    +------------------------------+")
        print("    | [Card 2] Full Width (100%)  |")
        print("    +------------------------------+")
    elif cols == 2:
        print("    +----------------+ +----------------+")
        print("    | [Card 1] 50%   | | [Card 2] 50%   |")
        print("    +----------------+ +----------------+")
        print("    | [Card 3] 50%   | | [Card 4] 50%   |")
        print("    +----------------+ +----------------+")
    else:
        print("    +--------+ +--------+ +--------+ +--------+")
        print("    | C1 25% | | C2 25% | | C3 25% | | C4 25% |")
        print("    +--------+ +--------+ +--------+ +--------+")

def demo_design_tokens():
    print_header("DESIGN SYSTEM TOKENS CATALOG")
    print(f"\n{TermColor.BOLD}1. Spacing Tokens (Scale Base 4px):{TermColor.RESET}")
    for token, val in DESIGN_TOKENS["spacing"].items():
        print(f"   --space-{token:<4} : {TermColor.FG_GREEN}{val}{TermColor.RESET}")

    print(f"\n{TermColor.BOLD}2. Semantic Color Palette Tokens:{TermColor.RESET}")
    for name, (hex_code, desc, color_code) in DESIGN_TOKENS["colors"].items():
        swatch = f"{color_code}[████]{TermColor.RESET}"
        print(f"   {swatch} --color-{name:<13} : {color_code}{hex_code:<8}{TermColor.RESET} ({desc})")

    print(f"\n{TermColor.BOLD}3. Standard Media Query Breakpoints:{TermColor.RESET}")
    for name, bp in DESIGN_TOKENS["breakpoints"].items():
        print(f"   @{name:<8} : min-width: {bp['min']}px  --> {bp['name']}")

def run_responsive_simulation_sweep():
    print_header("REAL-TIME VIEWPORT RESIZE SIMULATION SWEEP")
    test_widths = [360, 480, 640, 768, 900, 1024, 1280, 1440]
    for w in test_widths:
        demo_viewport_debugger(w)
        time.sleep(0.08)

def interactive_cli():
    while True:
        print_header("LAB 05: RESPONSIVE DESIGN & DESIGN SYSTEM ENGINE")
        print(f"{TermColor.BOLD}Pilihan Menu Praktikum:{TermColor.RESET}")
        print("  1. Uji Manual Resolusi Viewport (Custom Width)")
        print("  2. Jalankan Simulasi Sweep (Mobile -> Tablet -> Desktop)")
        print("  3. Eksplorasi Design Tokens (Spacing, Typography & Color)")
        print("  4. Kalkulator Fluid Typography CSS clamp()")
        print("  5. Keluar")
        
        choice = input(f"\n{TermColor.FG_YELLOW}Pilih opsi [1-5]: {TermColor.RESET}").strip()
        
        if choice == "1":
            try:
                raw_w = input(f"{TermColor.FG_CYAN}Masukkan lebar viewport (px) [misal: 375, 768, 1280]: {TermColor.RESET}").strip()
                width = int(raw_w)
                if width <= 0:
                    print(f"{TermColor.FG_RED}Lebar viewport harus lebih dari 0!{TermColor.RESET}")
                    continue
                demo_viewport_debugger(width)
            except ValueError:
                print(f"{TermColor.FG_RED}Input tidak valid. Masukkan angka bulat.{TermColor.RESET}")
        elif choice == "2":
            run_responsive_simulation_sweep()
        elif choice == "3":
            demo_design_tokens()
        elif choice == "4":
            print_header("CSS clamp() FLUID TYPOGRAPHY CALCULATOR")
            print("Formula: clamp(1rem, 1rem + 1.5vw, 2.5rem)")
            print("-" * 55)
            print(f"{'Viewport':<12} | {'Rem Size':<12} | {'Pixel Approx':<12} | {'Status'}")
            print("-" * 55)
            for v in [320, 375, 600, 768, 1024, 1280, 1600]:
                rem_val, px_val = simulate_clamp_typography(v)
                status = "Min Clamped" if v <= 375 else ("Max Clamped" if v >= 1280 else "Fluid Scaling")
                color = TermColor.FG_YELLOW if "Clamp" in status else TermColor.FG_GREEN
                print(f"{v}px{' ' * 6} | {rem_val:.3f}rem{' ' * 4} | {px_val:.1f}px{' ' * 5} | {color}{status}{TermColor.RESET}")
        elif choice == "5":
            print(f"\n{TermColor.FG_GREEN}Praktikum selesai. Selamat belajar Desain Web Responsif & Design Systems!{TermColor.RESET}\n")
            sys.exit(0)
        else:
            print(f"{TermColor.FG_RED}Opsi tidak dikenali. Silakan pilih 1-5.{TermColor.RESET}")
        
        input(f"\n{TermColor.DIM}Tekan [Enter] untuk melanjutkan...{TermColor.RESET}")

if __name__ == "__main__":
    try:
        # Jika dipanggil dengan flag non-interaktif (--auto / --test)
        if len(sys.argv) > 1 and sys.argv[1] in ["--test", "--auto", "-t"]:
            print_badge("AUTO TEST MODE", TermColor.FG_GREEN)
            demo_design_tokens()
            run_responsive_simulation_sweep()
            rem_val, px_val = simulate_clamp_typography(768)
            assert rem_val > 1.0 and px_val > 16.0, "Fluid typography calculation error"
            print(f"\n{TermColor.FG_GREEN}Semua test simulasi responsive lolos verifikasi!{TermColor.RESET}")
            sys.exit(0)
        else:
            interactive_cli()
    except KeyboardInterrupt:
        print(f"\n\n{TermColor.FG_YELLOW}Keluar dari simulator.{TermColor.RESET}")
        sys.exit(0)
