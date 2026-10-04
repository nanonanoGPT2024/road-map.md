#!/usr/bin/env python3
"""
Lab Hands-on: Fluid Responsive Typography dan Container Queries (CQ) Engine
Topik: 03-Frontend-and-Mobile / Bab 05 - Fluid Typography & Container Queries

Skrip ini mereplikasi dan mensimulasikan komputasi CSS engine internal untuk:
1. Perhitungan matematis Fluid Typography menggunakan formula CSS `clamp()`.
2. Evaluasi layout adaptif menggunakan Container Queries vs Viewport Media Queries.
3. Simulasi rendering token desain berbasis Container Query Units (cqw, cqh, cqi).
"""

import sys
import math
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum

# --- ANSI Styling Setup ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

# --- Bagian 1: Fluid Typography Mathematical Engine ---

@dataclass
class FluidTypeConfig:
    min_width_px: float       # Viewport minimum (e.g., 360px)
    max_width_px: float       # Viewport maximum (e.g., 1200px)
    min_font_px: float        # Font size saat min viewport (e.g., 16px)
    max_font_px: float        # Font size saat max viewport (e.g., 28px)
    root_font_size: float = 16.0  # Basis rem browser standar

class FluidTypographyCalculator:
    """
    Menghitung formula linear interpolation untuk CSS clamp():
    clamp(MIN, SLOPE*100vw + INTERCEPT, MAX)
    """
    def __init__(self, config: FluidTypeConfig):
        self.cfg = config
        self.slope: float = 0.0
        self.intercept_px: float = 0.0
        self.slope_vw: float = 0.0
        self.intercept_rem: float = 0.0
        self._calculate_interpolation()

    def _calculate_interpolation(self) -> None:
        # Menghitung gradien linear: m = (y2 - y1) / (x2 - x1)
        self.slope = (self.cfg.max_font_px - self.cfg.min_font_px) / (self.cfg.max_width_px - self.cfg.min_width_px)
        # Menghitung titik potong y (intercept): b = y1 - (m * x1)
        self.intercept_px = self.cfg.min_font_px - (self.slope * self.cfg.min_width_px)
        
        # Konversi ke unit viewport (vw) dan rem
        self.slope_vw = self.slope * 100.0
        self.intercept_rem = self.intercept_px / self.cfg.root_font_size

    def generate_css_clamp(self) -> str:
        min_rem = self.cfg.min_font_px / self.cfg.root_font_size
        max_rem = self.cfg.max_font_px / self.cfg.root_font_size
        sign = "+" if self.intercept_rem >= 0 else "-"
        abs_intercept = abs(self.intercept_rem)
        
        return (
            f"clamp({min_rem:.3f}rem, "
            f"{abs_intercept:.4f}rem {sign} {self.slope_vw:.4f}vw, "
            f"{max_rem:.3f}rem)"
        )

    def compute_size(self, current_viewport_px: float) -> float:
        """Evaluasi runtime browser terhadap clamp()"""
        ideal_px = (self.slope * current_viewport_px) + self.intercept_px
        clamped_px = max(self.cfg.min_font_px, min(ideal_px, self.cfg.max_font_px))
        return clamped_px

# --- Bagian 2: Container Query Evaluation Engine ---

class LayoutMode(Enum):
    COMPACT_STACK = "COMPACT_STACK"       # Tampilan satu kolom / vertical card
    HORIZONTAL_CARD = "HORIZONTAL_CARD"   # Gambar disamping, teks disamping
    FEATURED_HERO = "FEATURED_HERO"       # Multi-kolom luas dengan metadata lengkap

@dataclass
class ContainerContext:
    name: str
    width: float
    height: float

@dataclass
class ContainerRule:
    min_width: float
    mode: LayoutMode
    padding_cqw: float  # Satuan 1cqw = 1% dari container width

class CardComponent:
    """Komponen UI Card yang menerapkan CQ dan unit cqw."""
    def __init__(self, title: str):
        self.title = title
        # Aturan Container Queries terdaftar
        self.rules: List[ContainerRule] = [
            ContainerRule(min_width=650.0, mode=LayoutMode.FEATURED_HERO, padding_cqw=4.0),
            ContainerRule(min_width=400.0, mode=LayoutMode.HORIZONTAL_CARD, padding_cqw=3.0),
            ContainerRule(min_width=0.0,   mode=LayoutMode.COMPACT_STACK,   padding_cqw=2.0),
        ]

    def render(self, container: ContainerContext, viewport_width: float) -> Dict[str, any]:
        # Cari aturan container query yang cocok (dari breakpoint terbesar)
        active_rule = self.rules[-1]
        for rule in sorted(self.rules, key=lambda r: r.min_width, reverse=True):
            if container.width >= rule.min_width:
                active_rule = rule
                break
        
        # Evaluasi Container Query Units (1 cqw = 1% dari container.width)
        computed_padding_px = (active_rule.padding_cqw / 100.0) * container.width
        
        # Simulasi Media Query naive (viewport-based) untuk pembanding
        naive_viewport_mode = LayoutMode.COMPACT_STACK
        if viewport_width >= 1024.0:
            naive_viewport_mode = LayoutMode.FEATURED_HERO
        elif viewport_width >= 600.0:
            naive_viewport_mode = LayoutMode.HORIZONTAL_CARD

        return {
            "title": self.title,
            "container_name": container.name,
            "container_width": container.width,
            "viewport_width": viewport_width,
            "active_layout": active_rule.mode,
            "naive_mq_layout": naive_viewport_mode,
            "computed_padding_px": round(computed_padding_px, 1),
            "is_broken_in_narrow_parent": (naive_viewport_mode != active_rule.mode) and (container.width < 400.0 and naive_viewport_mode == LayoutMode.FEATURED_HERO)
        }

# --- Execution & Verification ---

def print_header(title: str):
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}{'='*72}{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN} [LAB] {title.center(64)} {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}{'='*72}{TermColor.RESET}")

def run_typography_simulation():
    print_header("Simulasi Fluid Typography Math (CSS clamp)")
    
    config = FluidTypeConfig(
        min_width_px=375.0,   # iPhone standard
        max_width_px=1280.0,  # Desktop target
        min_font_px=16.0,     # Body mobile
        max_font_px=24.0      # Body desktop
    )
    
    engine = FluidTypographyCalculator(config)
    clamp_expression = engine.generate_css_clamp()
    
    print(f"{TermColor.BOLD}Target Range:{TermColor.RESET} Viewport {config.min_width_px}px -> {config.max_width_px}px")
    print(f"{TermColor.BOLD}Font Range:{TermColor.RESET}   Font Size {config.min_font_px}px -> {config.max_font_px}px")
    print(f"{TermColor.YELLOW}Compiled CSS :{TermColor.RESET} {TermColor.BOLD}font-size: {clamp_expression};{TermColor.RESET}\n")
    
    print(f"{'Viewport (px)':<15} | {'Computed Font (px)':<20} | {'Status Limit':<15} | Visual Ratio")
    print("-" * 72)
    
    test_viewports = [320.0, 375.0, 600.0, 768.0, 1024.0, 1280.0, 1440.0]
    for vp in test_viewports:
        size = engine.compute_size(vp)
        
        status = "Active Linear"
        color = TermColor.GREEN
        if vp <= config.min_width_px:
            status = "Min Clamped"
            color = TermColor.CYAN
        elif vp >= config.max_width_px:
            status = "Max Clamped"
            color = TermColor.MAGENTA
            
        bar = "█" * int(size - 10)
        print(f"{vp:<15.1f} | {color}{size:<20.2f}{TermColor.RESET} | {status:<15} | {color}{bar}{TermColor.RESET}")

def run_container_queries_simulation():
    print_header("Simulasi Container Queries (CQ) vs Viewport Media Queries (MQ)")
    
    card = CardComponent(title="ProductCard")
    
    # Skenario: Viewport lebar (Desktop 1200px)
    # Terdapat Sidebar (lebar 300px) dan Main Content (lebar 900px)
    viewport = 1200.0
    sidebar_container = ContainerContext(name="sidebar-slot", width=320.0, height=800.0)
    main_container = ContainerContext(name="main-slot", width=880.0, height=800.0)
    
    print(f"Viewport Aktif: {TermColor.BOLD}{viewport}px{TermColor.RESET}")
    print(f"Skenario: Memasang komponen yang sama persis di dua kontainer berbeda ukuran.\n")
    
    render_sidebar = card.render(sidebar_container, viewport)
    render_main = card.render(main_container, viewport)
    
    for res in [render_sidebar, render_main]:
        print(f"{TermColor.BOLD}Slot Container: '{res['container_name']}' (Width: {res['container_width']}px){TermColor.RESET}")
        print(f"  ├─ Mode Container Query (CQ) : {TermColor.GREEN}{res['active_layout'].value}{TermColor.RESET}")
        print(f"  ├─ Mode Media Query (MQ)     : {TermColor.RED if res['is_broken_in_narrow_parent'] else TermColor.YELLOW}{res['naive_mq_layout'].value}{TermColor.RESET}")
        print(f"  ├─ Dynamic Padding (cqw)     : {res['computed_padding_px']}px")
        
        if res['is_broken_in_narrow_parent']:
            print(f"  └─ {TermColor.RED}[COLLISION DETECTED]{TermColor.RESET} MQ memaksa tampilan HERO pada kontainer 320px!")
        else:
            print(f"  └─ {TermColor.GREEN}[OPTIMAL]{TermColor.RESET} Layout teradaptasi secara isolatif berdasarkan container context.")
        print()

def main():
    try:
        run_typography_simulation()
        run_container_queries_simulation()
        print(f"{TermColor.BOLD}{TermColor.GREEN}✓ Lab Deep Dive Berhasil Dieksekusi Tanpa Runtime Error.{TermColor.RESET}\n")
    except Exception as exc:
        print(f"{TermColor.RED}Execution Failure: {exc}{TermColor.RESET}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()