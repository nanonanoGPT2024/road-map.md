#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Grammar of Graphics & Visualisasi Tingkat Lanjut (R BAB-05)
Fokus: Arsitektur ggplot2, Skala Warna, Theming Kustom, & Komposisi Patchwork di Terminal.
"""

import sys
import math
import time
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

# ==============================================================================
# ANSI Color Codes & Terminal Styling
# ==============================================================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    FG_BLACK = "\033[30m"
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_WHITE = "\033[37m"
    FG_BRIGHT_CYAN = "\033[96m"
    FG_BRIGHT_GREEN = "\033[92m"
    FG_BRIGHT_YELLOW = "\033[93m"
    FG_BRIGHT_MAGENTA = "\033[95m"

    # Background
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_GRAY = "\033[100m"

# ==============================================================================
# Domain Models: Grammar of Graphics
# ==============================================================================
class GeomType(Enum):
    POINT = "geom_point"
    BAR = "geom_col"
    LINE = "geom_line"

@dataclass(frozen=True)
class Theme:
    name: str
    grid_char: str
    axis_color: str
    grid_color: str
    title_style: str

THEME_MINIMAL = Theme(
    name="theme_minimal()",
    grid_char="·",
    axis_color=Style.FG_WHITE,
    grid_color=Style.FG_BLACK + Style.BOLD,
    title_style=Style.BOLD + Style.FG_BRIGHT_CYAN
)

THEME_DARK = Theme(
    name="theme_dark()",
    grid_char="┼",
    axis_color=Style.FG_YELLOW,
    grid_color=Style.FG_BLUE,
    title_style=Style.BOLD + Style.FG_BRIGHT_YELLOW
)

THEME_CLASSIC = Theme(
    name="theme_classic()",
    grid_char=" ",
    axis_color=Style.FG_WHITE,
    grid_color="",
    title_style=Style.BOLD + Style.FG_GREEN
)

@dataclass
class DataPoint:
    x: float
    y: float
    group: str = "A"

@dataclass
class PlotSpecification:
    title: str
    x_label: str
    y_label: str
    geom: GeomType
    data: List[DataPoint]
    theme: Theme = THEME_MINIMAL
    palette_name: str = "viridis"

# ==============================================================================
# Palette & Color Theory
# ==============================================================================
VIRIDIS_PALETTE = {
    "A": (Style.FG_MAGENTA, "●"),
    "B": (Style.FG_CYAN, "▲"),
    "C": (Style.FG_BRIGHT_GREEN, "■")
}

BREWER_SET1 = {
    "A": (Style.FG_RED, "♦"),
    "B": (Style.FG_BLUE, "▲"),
    "C": (Style.FG_YELLOW, "★")
}

def get_palette(name: str) -> Dict[str, Tuple[str, str]]:
    if name.lower() == "brewer":
        return BREWER_SET1
    return VIRIDIS_PALETTE

# ==============================================================================
# Terminal Canvas Renderer (Emulasi Raster Engine R)
# ==============================================================================
class TerminalPlotRenderer:
    def __init__(self, width: int = 48, height: int = 14):
        self.width = width
        self.height = height

    def render(self, spec: PlotSpecification) -> str:
        palette = get_palette(spec.palette_name)
        theme = spec.theme

        if not spec.data:
            return f"{Style.FG_RED}[Error: Data kosong]{Style.RESET}"

        xs = [p.x for p in spec.data]
        ys = [p.y for p in spec.data]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if min_x == max_x: max_x += 1.0
        if min_y == max_y: max_y += 1.0

        # Initialize grid
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]

        # Apply grid theme
        if theme.grid_char != " ":
            for r in range(self.height):
                for c in range(self.width):
                    if r % 3 == 0 or c % 8 == 0:
                        grid[r][c] = f"{theme.grid_color}{theme.grid_char}{Style.RESET}"

        # Rasterize Geoms
        if spec.geom == GeomType.POINT:
            for p in spec.data:
                col_idx = int(((p.x - min_x) / (max_x - min_x)) * (self.width - 1))
                row_idx = int(((p.y - min_y) / (max_y - min_y)) * (self.height - 1))
                row_idx = self.height - 1 - row_idx  # Invert Y for screen buffer
                col, glyph = palette.get(p.group, (Style.FG_WHITE, "●"))
                grid[row_idx][col_idx] = f"{col}{glyph}{Style.RESET}"

        elif spec.geom == GeomType.BAR:
            bar_width = max(1, self.width // (len(spec.data) * 2))
            for i, p in enumerate(spec.data):
                center_col = int(((i + 0.5) / len(spec.data)) * (self.width - 1))
                bar_h = int(((p.y - min_y) / (max_y - min_y)) * (self.height - 1))
                col, _ = palette.get(p.group, (Style.FG_CYAN, "█"))
                for h in range(bar_h + 1):
                    r_idx = self.height - 1 - h
                    for w_offset in range(-bar_width // 2, bar_width // 2 + 1):
                        target_col = center_col + w_offset
                        if 0 <= target_col < self.width:
                            grid[r_idx][target_col] = f"{col}█{Style.RESET}"

        # Compose output frame
        out = []
        out.append(f"{theme.title_style}┌─ {spec.title} ({spec.theme.name}) ─┐{Style.RESET}")

        # Render Canvas with Y-axis label
        for r in range(self.height):
            y_val = max_y - (r / (self.height - 1)) * (max_y - min_y)
            y_str = f"{y_val:5.1f} │ "
            row_str = "".join(grid[r])
            out.append(f"{theme.axis_color}{y_str}{Style.RESET}{row_str}│")

        # X-axis line
        axis_line = "─" * self.width
        out.append(f"{theme.axis_color}      └{axis_line}┘{Style.RESET}")

        # X ticks and label
        ticks_str = f"{min_x:<6.1f}" + " " * (self.width - 14) + f"{max_x:>6.1f}"
        out.append(f"{theme.axis_color}       {ticks_str}{Style.RESET}")
        out.append(f"{Style.DIM}       {spec.x_label.center(self.width)}{Style.RESET}")

        # Legend
        legend_items = [
            f"{palette[grp][0]}{palette[grp][1]} Kelompok {grp}{Style.RESET}"
            for grp in palette if any(p.group == grp for p in spec.data)
        ]
        out.append(f"  {Style.BOLD}Legend [{spec.palette_name}]:{Style.RESET} " + " | ".join(legend_items))

        return "\n".join(out)

# ==============================================================================
# Komposisi Multi-Plot (Patchwork Engine R)
# ==============================================================================
class PatchworkComposer:
    @staticmethod
    def side_by_side(plot_a_str: str, plot_b_str: str, separator: str = "   ║   ") -> str:
        lines_a = plot_a_str.split("\n")
        lines_b = plot_b_str.split("\n")
        max_lines = max(len(lines_a), len(lines_b))

        width_a = max(len(line) for line in lines_a) if lines_a else 0

        # Note: ANSI codes affect raw len, but for display padding we estimate visible length
        composed = []
        for i in range(max_lines):
            la = lines_a[i] if i < len(lines_a) else ""
            lb = lines_b[i] if i < len(lines_b) else ""
            # Simple pad estimation
            composed.append(f"{la:<55}{separator}{lb}")
        return "\n".join(composed)

# ==============================================================================
# Pipeline & Interactive Simulations
# ==============================================================================
def create_sample_data() -> Tuple[List[DataPoint], List[DataPoint]]:
    scatter_pts = []
    groups = ["A", "B", "C"]
    for i in range(24):
        grp = groups[i % 3]
        base_x = (i % 8) * 1.5 + (1.2 if grp == "B" else (2.4 if grp == "C" else 0.5))
        base_y = math.sin(base_x / 2.0) * 10 + (i * 0.8) + random.uniform(-1.5, 1.5)
        scatter_pts.append(DataPoint(x=round(base_x, 2), y=round(base_y, 2), group=grp))

    bar_pts = [
        DataPoint(x=1.0, y=24.5, group="A"),
        DataPoint(x=2.0, y=38.2, group="B"),
        DataPoint(x=3.0, y=19.4, group="C")
    ]
    return scatter_pts, bar_pts

def run_grammar_simulation():
    print(f"\n{Style.BG_BLUE}{Style.BOLD}{Style.FG_WHITE} === MODUL 01: SIMULASI GRAMMAR OF GRAPHICS (R / GGPLOT2) === {Style.RESET}\n")
    print(f"{Style.FG_CYAN}1. Memuat Data & Mentransformasikan Aesthetic Mapping: aes(x = Waktu, y = Metrik, color = Kelompok)...{Style.RESET}")
    time.sleep(0.4)

    scatter_data, bar_data = create_sample_data()
    renderer = TerminalPlotRenderer(width=42, height=10)

    # Plot 1: Scatter dengan theme_minimal & viridis
    spec1 = PlotSpecification(
        title="Dispersion: aes(x, y)",
        x_label="Waktu Eksperimen (jam)",
        y_label="Respon",
        geom=GeomType.POINT,
        data=scatter_data,
        theme=THEME_MINIMAL,
        palette_name="viridis"
    )

    # Plot 2: Bar chart dengan theme_dark & brewer
    spec2 = PlotSpecification(
        title="Agregat Kelompok: geom_col()",
        x_label="Kategori",
        y_label="Total",
        geom=GeomType.BAR,
        data=bar_data,
        theme=THEME_DARK,
        palette_name="brewer"
    )

    print(f"{Style.FG_BRIGHT_GREEN}2. Mengompilasi Layer & Geometri ggplot2... Selesai.{Style.RESET}\n")
    rendered1 = renderer.render(spec1)
    print(rendered1)

    print(f"\n{Style.FG_BRIGHT_YELLOW}3. Menguji Perubahan Skala (Scale) & Tema (Theme):{Style.RESET}\n")
    rendered2 = renderer.render(spec2)
    print(rendered2)

    print(f"\n{Style.BG_GRAY}{Style.BOLD} 4. Patchwork Operator Simulation (plot1 | plot2) {Style.RESET}\n")
    time.sleep(0.3)
    composite = PatchworkComposer.side_by_side(rendered1, rendered2)
    print(composite)

def interactive_cli():
    print(f"\n{Style.BOLD}{Style.FG_BRIGHT_CYAN}================================================================{Style.RESET}")
    print(f"{Style.BOLD} R BAB-05 Interactive Graphic System Sandbox {Style.RESET}")
    print(f"{Style.BOLD}{Style.FG_BRIGHT_CYAN}================================================================{Style.RESET}")
    print(f"Pilihan Tema R yang tersedia: [1] minimal, [2] dark, [3] classic")
    print(f"Pilihan Palet Warna: [A] Viridis, [B] ColorBrewer")

    theme_map = {"1": THEME_MINIMAL, "2": THEME_DARK, "3": THEME_CLASSIC}
    palette_map = {"A": "viridis", "B": "brewer"}

    t_choice = "1"
    p_choice = "A"

    if sys.stdin.isatty():
        try:
            val_t = input(f"{Style.FG_YELLOW}Pilih Tema (1-3) [Default 1]: {Style.RESET}").strip()
            if val_t in theme_map: t_choice = val_t
            val_p = input(f"{Style.FG_YELLOW}Pilih Palet (A/B) [Default A]: {Style.RESET}").strip().upper()
            if val_p in palette_map: p_choice = val_p
        except (EOFError, KeyboardInterrupt):
            pass

    scatter_data, _ = create_sample_data()
    selected_theme = theme_map[t_choice]
    selected_palette = palette_map[p_choice]

    custom_spec = PlotSpecification(
        title=f"Custom ggplot2 Pipeline ({selected_theme.name})",
        x_label="Variabel X Independen",
        y_label="Variabel Y Dependen",
        geom=GeomType.POINT,
        data=scatter_data,
        theme=selected_theme,
        palette_name=selected_palette
    )

    renderer = TerminalPlotRenderer(width=50, height=12)
    print("\n" + renderer.render(custom_spec) + "\n")
    print(f"{Style.FG_BRIGHT_GREEN}✓ Rendering berhasil dieksekusi dengan standar visual Grammar of Graphics.{Style.RESET}")

# ==============================================================================
# Self Test Verification
# ==============================================================================
def run_verification_tests():
    print(f"{Style.BOLD}[VERIFIKASI SISTEM]{Style.RESET} Menjalankan unit tests internal...")
    scatter_data, bar_data = create_sample_data()
    assert len(scatter_data) > 0, "Data scatter gagal dibuat!"
    assert len(bar_data) == 3, "Data bar agregasi harus berjumlah 3 kategori!"

    renderer = TerminalPlotRenderer(width=20, height=8)
    spec = PlotSpecification(
        title="Test Plot",
        x_label="X",
        y_label="Y",
        geom=GeomType.POINT,
        data=scatter_data[:5],
        theme=THEME_MINIMAL
    )
    res = renderer.render(spec)
    assert "Test Plot" in res, "Judul plot gagal dirender!"
    assert "Legend" in res, "Legend gagal dirender!"
    print(f"{Style.FG_GREEN}✓ Semua 3 assertions lolos.{Style.RESET}")

if __name__ == "__main__":
    if "--test" in sys.argv:
        run_verification_tests()
    else:
        run_grammar_simulation()
        interactive_cli()
        run_verification_tests()
