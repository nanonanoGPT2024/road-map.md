#!/usr/bin/env python3
"""
Simulasi Teknis Fondasi CSS: Fluid Typography & Container Queries
Laboratorium Hands-on Interaktif (CLI ANSI Terminal)

Topik yang Disimulasikan:
1. Fluid Typography Math: kalkulasi slope, y-intercept, dan representasi clamp(MIN, VAL, MAX).
2. Container Queries Engine: container-type: inline-size, unit cqw/cqh vs vw/vh.
3. Component-driven adaptation vs Viewport-driven Media Queries.
"""

from __future__ import annotations
import math
import sys
from dataclasses import dataclass
from typing import List, Tuple, Optional

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
RED = "\033[31m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"


@dataclass
class FluidTypeConfig:
    min_width_px: float = 375.0      # Mobile breakpoint
    max_width_px: float = 1440.0     # Desktop breakpoint
    min_font_rem: float = 1.0        # 16px (basis 1rem = 16px)
    max_font_rem: float = 2.5        # 40px
    root_font_size_px: float = 16.0


class FluidTypographyEngine:
    """Mesin kalkulasi CSS Clamp Linear Interpolation."""

    def __init__(self, config: FluidTypeConfig):
        self.cfg = config

    def calculate_clamp_formula(self) -> Tuple[float, float, str]:
        """
        Menghitung slope dan y-intercept untuk clamp():
        slope = (max_font - min_font) / (max_width - min_width)
        preferred = y_intercept_rem + (slope * 100)vw
        """
        min_font_px = self.cfg.min_font_rem * self.cfg.root_font_size_px
        max_font_px = self.cfg.max_font_rem * self.cfg.root_font_size_px

        slope = (max_font_px - min_font_px) / (self.cfg.max_width_px - self.cfg.min_width_px)
        y_axis_intersection_px = -self.cfg.min_width_px * slope + min_font_px
        y_axis_intersection_rem = y_axis_intersection_px / self.cfg.root_font_size_px
        slope_vw = slope * 100.0

        clamp_str = (
            f"clamp({self.cfg.min_font_rem:.3f}rem, "
            f"{y_axis_intersection_rem:.3f}rem + {slope_vw:.3f}vw, "
            f"{self.cfg.max_font_rem:.3f}rem)"
        )
        return slope_vw, y_axis_intersection_rem, clamp_str

    def resolve_font_size_px(self, viewport_width_px: float) -> float:
        """Menghitung ukuran font aktual pada viewport tertentu (logika runtime CSS clamp)."""
        min_font_px = self.cfg.min_font_rem * self.cfg.root_font_size_px
        max_font_px = self.cfg.max_font_rem * self.cfg.root_font_size_px

        if viewport_width_px <= self.cfg.min_width_px:
            return min_font_px
        if viewport_width_px >= self.cfg.max_width_px:
            return max_font_px

        slope_vw, y_rem, _ = self.calculate_clamp_formula()
        preferred_px = (y_rem * self.cfg.root_font_size_px) + (slope_vw / 100.0 * viewport_width_px)
        return min(max(preferred_px, min_font_px), max_font_px)


class ContainerQuerySimulator:
    """Simulator layout berbasis CSS Container Queries vs Viewport Queries."""

    @staticmethod
    def render_card_component(container_width_px: float, label: str) -> List[str]:
        """
        Simulasi CSS:
        @container card-box (min-width: 650px) -> Horizontal 2-Column
        @container card-box (min-width: 400px) -> Two-line Compact
        Default -> Vertical Stack
        """
        lines = []
        cqw = container_width_px / 100.0  # 1 cqw = 1% container inline-size

        if container_width_px >= 650.0:
            layout_name = "Desktop Multi-Column (Large Container)"
            color = GREEN
            ascii_art = [
                f"{color}┌─[ IMG (25cqw) ]──┬───────────────────────────────────────┐{RESET}",
                f"{color}│  [ Thumbnail ]   │ Title: Adaptif terhadap Parent Box     │{RESET}",
                f"{color}│  Width: {25*cqw:.0f}px     │ Desc : Berubah tanpa bergantung layar!│{RESET}",
                f"{color}└──────────────────┴───────────────────────────────────────┘{RESET}",
            ]
        elif container_width_px >= 400.0:
            layout_name = "Medium Compact (Medium Container)"
            color = CYAN
            ascii_art = [
                f"{color}┌──────────────────────────────────────────────────────────┐{RESET}",
                f"{color}│ [Thumbnail] Title: Adaptif terhadap Parent Box           │{RESET}",
                f"{color}│ Desc: Compact horizontal row display                     │{RESET}",
                f"{color}└──────────────────────────────────────────────────────────┘{RESET}",
            ]
        else:
            layout_name = "Vertical Stack (Narrow Container)"
            color = YELLOW
            ascii_art = [
                f"{color}┌──────────────────────────────┐{RESET}",
                f"{color}│ [       Thumbnail        ]   │{RESET}",
                f"{color}├──────────────────────────────┤{RESET}",
                f"{color}│ Title: Adaptif Parent Box    │{RESET}",
                f"{color}│ Desc : Stack Vertikal        │{RESET}",
                f"{color}└──────────────────────────────┘{RESET}",
            ]

        lines.append(f"{BOLD}{label}{RESET} (Container: {MAGENTA}{container_width_px:.1f}px{RESET}) -> Layout: {color}{layout_name}{RESET}")
        lines.extend(ascii_art)
        return lines


def print_header(title: str) -> None:
    print(f"\n{BOLD}{BG_BLUE} ✦ {title.upper()} ✦ {RESET}")


def run_fluid_typography_demo(engine: FluidTypographyEngine) -> None:
    print_header("Simulasi Fluid Typography Math [clamp()]")
    _, _, clamp_css = engine.calculate_clamp_formula()
    print(f"Konfigurasi Boundary: Mobile = {engine.cfg.min_width_px}px, Desktop = {engine.cfg.max_width_px}px")
    print(f"Target Font         : {engine.cfg.min_font_rem}rem ({engine.cfg.min_font_rem * 16:.0f}px) → {engine.cfg.max_font_rem}rem ({engine.cfg.max_font_rem * 16:.0f}px)")
    print(f"Hasil Formula CSS   : {BOLD}{GREEN}{clamp_css}{RESET}\n")

    print(f"{'Viewport':<12} | {'Aktual (px)':<14} | {'Aktual (rem)':<14} | Visual Bar")
    print("-" * 65)

    test_viewports = [320.0, 375.0, 500.0, 768.0, 1024.0, 1280.0, 1440.0, 1920.0]
    for vp in test_viewports:
        px = engine.resolve_font_size_px(vp)
        rem = px / engine.cfg.root_font_size_px
        bar_len = int((px - 14.0) * 1.5)
        bar = f"{CYAN}{'█' * max(1, bar_len)}{RESET}"
        status = ""
        if vp <= engine.cfg.min_width_px:
            status = f"{DIM}(Min Clamped){RESET}"
        elif vp >= engine.cfg.max_width_px:
            status = f"{DIM}(Max Clamped){RESET}"
        else:
            status = f"{GREEN}(Fluid Active){RESET}"

        print(f"{vp:>6.0f}px      | {px:>6.2f}px       | {rem:>6.3f}rem      | {bar} {status}")


def run_container_queries_demo() -> None:
    print_header("Simulasi Container Queries (@container vs @media)")
    print(
        f"{DIM}Skenario: Layar Desktop Luas (1280px).\n"
        f"Komponen Card yang sama ditaruh di 2 tempat berbeda:\n"
        f"1. Sidebar Sempit (320px)\n"
        f"2. Main Content Area (800px){RESET}\n"
    )

    sim = ContainerQuerySimulator()
    sidebar_output = sim.render_card_component(320.0, "Card di dalam <aside class='sidebar'>")
    for line in sidebar_output:
        print(line)

    print()
    main_output = sim.render_card_component(800.0, "Card di dalam <main class='content'>")
    for line in main_output:
        print(line)

    print(f"\n{BOLD}{YELLOW}Kelebihan Container Queries:{RESET}")
    print(f"• Media query (@media) hanya melihat viewport (1280px) sehingga Card di sidebar akan rusak jika dipaksa multi-column.")
    print(f"• Container query (@container) menginspeksi parent box masing-masing secara independen dan modular.")


def interactive_mode(engine: FluidTypographyEngine) -> None:
    print_header("Mode Interaktif Eksplorasi CSS")
    print(f"Ketik angka viewport (px) untuk menguji kalkulasi font, atau 'cq <lebar_px>' untuk uji container query.")
    print(f"Ketik 'q' atau 'exit' untuk selesai.\n")

    while True:
        try:
            user_input = input(f"{BOLD}{CYAN}CSS-Lab > {RESET}").strip().lower()
            if not user_input or user_input in ("q", "exit", "quit"):
                print(f"{GREEN}Lab selesai. Praktikkan pemahaman ini pada kode CSS Anda!{RESET}")
                break

            if user_input.startswith("cq"):
                parts = user_input.split()
                if len(parts) >= 2 and parts[1].replace(".", "", 1).isdigit():
                    c_width = float(parts[1])
                    for l in ContainerQuerySimulator.render_card_component(c_width, "Komponen Kustom"):
                        print(l)
                else:
                    print(f"{RED}Format salah. Gunakan contoh: cq 550{RESET}")
            elif user_input.replace(".", "", 1).isdigit():
                vp = float(user_input)
                px = engine.resolve_font_size_px(vp)
                rem = px / engine.cfg.root_font_size_px
                print(f"-> Viewport {vp:.1f}px -> Font Size: {BOLD}{GREEN}{px:.2f}px ({rem:.3f}rem){RESET}")
            else:
                print(f"{RED}Perintah tidak dikenal. Masukkan angka pixel (contoh: 800) atau 'cq 500'.{RESET}")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{GREEN}Keluar dari lab.{RESET}")
            break


def main() -> None:
    cfg = FluidTypeConfig()
    engine = FluidTypographyEngine(cfg)

    # Jalankan simulasi inti terformat
    run_fluid_typography_demo(engine)
    run_container_queries_demo()

    # Jika terminal interaktif dan tanpa argumen --no-interactive / --demo, buka prompt
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "--test", "--headless"):
        print(f"\n{GREEN}[OK] Simulasi headless selesai tanpa error.{RESET}")
        sys.exit(0)

    if sys.stdin.isatty():
        interactive_mode(engine)
    else:
        print(f"\n{DIM}Non-interactive terminal terdeteksi. Simulasi demonstrasi selesai.{RESET}")


if __name__ == "__main__":
    main()
