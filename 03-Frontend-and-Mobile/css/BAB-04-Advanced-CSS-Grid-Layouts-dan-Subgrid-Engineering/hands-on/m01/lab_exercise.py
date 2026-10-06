#!/usr/bin/env python3
"""
Advanced CSS Grid Layout & Subgrid Technical Engine Simulator
BAB-04: Advanced CSS Grid Layouts dan Subgrid Engineering

Simulasi interaktif algoritma resolusi track CSS Grid Level 2,
distribusi fractional unit (fr), minmax bounds, dan alignment subgrid inheritance.
"""

from __future__ import annotations
import math
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_GRAY = "\033[100m"

class TrackUnit(Enum):
    PX = "px"
    FR = "fr"
    PERCENT = "%"
    MINMAX = "minmax"
    AUTO = "auto"
    SUBGRID = "subgrid"

@dataclass
class TrackDef:
    unit: TrackUnit
    value: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    name: str = ""

    def __str__(self) -> str:
        if self.unit == TrackUnit.MINMAX:
            return f"minmax({self.min_val}px, {self.max_val}fr)"
        elif self.unit == TrackUnit.FR:
            return f"{self.value}fr"
        elif self.unit == TrackUnit.PX:
            return f"{self.value}px"
        elif self.unit == TrackUnit.SUBGRID:
            return "subgrid"
        return f"{self.value}{self.unit.value}"

@dataclass
class GridItem:
    name: str
    col_start: int  # 1-indexed (CSS Grid line convention)
    col_end: int    # 1-indexed
    is_subgrid: bool = False
    children: List[GridItem] = field(default_factory=list)
    color: str = Color.CYAN

@dataclass
class ComputedTrack:
    index: int
    raw_def: TrackDef
    resolved_px: float
    start_pos: float
    end_pos: float

class CSSGridEngine:
    def __init__(self, container_width: float, column_gap: float, tracks: List[TrackDef]):
        self.container_width = container_width
        self.column_gap = column_gap
        self.tracks = tracks

    def resolve_tracks(self) -> List[ComputedTrack]:
        """
        Mengimplementasikan 3-phase CSS Grid Track Sizing Algorithm:
        1. Alokasi track statis (px, base minmax).
        2. Pengurangan gap antar track dari sisa ruang (free space).
        3. Normalisasi & distribusi sisa ruang ke flexible tracks (fr).
        """
        n = len(self.tracks)
        if n == 0:
            return []

        total_gaps = (n - 1) * self.column_gap
        available_space = self.container_width - total_gaps

        allocated_px = [0.0] * n
        fr_weights = [0.0] * n

        # Fase 1: Alokasi Non-Flexible Tracks
        for i, track in enumerate(self.tracks):
            if track.unit == TrackUnit.PX:
                allocated_px[i] = track.value
            elif track.unit == TrackUnit.MINMAX:
                allocated_px[i] = track.min_val  # base minimum
                if track.max_val > 0:
                    fr_weights[i] = track.max_val
            elif track.unit == TrackUnit.FR:
                fr_weights[i] = track.value

        used_space = sum(allocated_px)
        free_space = max(0.0, available_space - used_space)
        total_fr = sum(fr_weights)

        # Fase 2: Distribusi Flexible Units (fr)
        if total_fr > 0 and free_space > 0:
            fr_size = free_space / total_fr
            for i, track in enumerate(self.tracks):
                if track.unit == TrackUnit.FR:
                    allocated_px[i] = fr_size * track.value
                elif track.unit == TrackUnit.MINMAX:
                    extra = fr_size * track.max_val
                    allocated_px[i] = max(track.min_val, extra)

        # Fase 3: Kalkulasi Posisi Garis (Grid Lines)
        results = []
        current_pos = 0.0
        for i, (track, size) in enumerate(zip(self.tracks, allocated_px)):
            results.append(
                ComputedTrack(
                    index=i + 1,
                    raw_def=track,
                    resolved_px=round(size, 2),
                    start_pos=round(current_pos, 2),
                    end_pos=round(current_pos + size, 2)
                )
            )
            current_pos += size + self.column_gap

        return results

class SubgridResolver:
    """
    Menangani resolusi CSS Subgrid Level 2:
    Mewarisi track lines dan ukuran track dari induk tanpa membuat grid konteks terpisah.
    """
    def __init__(self, parent_tracks: List[ComputedTrack], parent_gap: float):
        self.parent_tracks = parent_tracks
        self.parent_gap = parent_gap

    def resolve_subgrid(self, col_start: int, col_end: int) -> List[ComputedTrack]:
        # Grid line CSS 1-indexed
        span_tracks = [
            t for t in self.parent_tracks 
            if col_start <= t.index < col_end
        ]
        return span_tracks

class TerminalRenderer:
    @staticmethod
    def render_header(title: str, subtitle: str = ""):
        width = 72
        print(f"\n{Color.BLUE}{'=' * width}{Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}  {title.center(width - 4)}{Color.RESET}")
        if subtitle:
            print(f"{Color.CYAN}  {subtitle.center(width - 4)}{Color.RESET}")
        print(f"{Color.BLUE}{'=' * width}{Color.RESET}\n")

    @staticmethod
    def render_grid_visualization(container_width: float, computed: List[ComputedTrack], items: List[GridItem], gap: float):
        print(f"{Color.BOLD}Grid Layout Visualization (Container: {container_width}px, Gap: {gap}px):{Color.RESET}")
        
        # Skala terminal: 1 karakter ~ 12px
        scale = 12.0
        header_line = "Line: "
        track_boxes = "Tracks: "
        
        for i, ct in enumerate(computed):
            chars = max(4, int(ct.resolved_px / scale))
            header_line += f"|{ct.index:<{chars}}"
            track_label = f"T{ct.index} ({ct.resolved_px:.0f}px)"
            track_boxes += f"[{track_label:^{chars}}]"
            if i < len(computed) - 1:
                track_boxes += f"{Color.DIM}.{Color.RESET}"
                header_line += " "
        header_line += f"|{len(computed) + 1}"
        
        print(f"{Color.YELLOW}{header_line}{Color.RESET}")
        print(f"{Color.GREEN}{track_boxes}{Color.RESET}")
        print()

        # Render Item & Subgrid Representation
        print(f"{Color.BOLD}Item Placements & Subgrid Bounds:{Color.RESET}")
        for item in items:
            span_size = sum(
                ct.resolved_px for ct in computed 
                if item.col_start <= ct.index < item.col_end
            ) + (item.col_end - item.col_start - 1) * gap
            
            subgrid_badge = f"{Color.BG_MAGENTA}{Color.WHITE} [SUBGRID] {Color.RESET}" if item.is_subgrid else ""
            print(f" -> {item.color}■ {item.name:<18}{Color.RESET} "
                  f"Col: {item.col_start} to {item.col_end} "
                  f"({span_size:.1f}px) {subgrid_badge}")
            
            if item.is_subgrid and item.children:
                for child in item.children:
                    child_span = sum(
                        ct.resolved_px for ct in computed 
                        if child.col_start <= ct.index < child.col_end
                    )
                    print(f"    └── {Color.MAGENTA}↳ {child.name:<15}{Color.RESET} "
                          f"Inherited Col: {child.col_start} to {child.col_end} "
                          f"({child_span:.1f}px alignment lock)")

def demo_scenario_1_fr_resolution():
    TerminalRenderer.render_header(
        "SCENARIO 1: Track Sizing & Fractional Units (fr) Resolution",
        "grid-template-columns: 200px 1fr 2fr minmax(100px, 1fr)"
    )
    container_width = 1200.0
    gap = 20.0
    tracks = [
        TrackDef(TrackUnit.PX, value=200.0),
        TrackDef(TrackUnit.FR, value=1.0),
        TrackDef(TrackUnit.FR, value=2.0),
        TrackDef(TrackUnit.MINMAX, min_val=100.0, max_val=1.0)
    ]
    
    engine = CSSGridEngine(container_width, gap, tracks)
    computed = engine.resolve_tracks()
    
    items = [
        GridItem("Sidebar-Nav", col_start=1, col_end=2, color=Color.YELLOW),
        GridItem("Main-Feed", col_start=2, col_end=4, color=Color.GREEN),
        GridItem("Ad-Widget", col_start=4, col_end=5, color=Color.RED)
    ]
    
    print(f"{Color.CYAN}Perhitungan Matematis:{Color.RESET}")
    print(f" • Total Container: {container_width}px")
    print(f" • Total Gap ({len(tracks)-1} x {gap}px): {(len(tracks)-1)*gap}px")
    print(f" • Static Allocated (Fixed 200px + Minmax min 100px): 300px")
    print(f" • Remaining Free Space: {container_width - 60 - 300}px")
    print(f" • Total fr units: 1fr + 2fr + 1fr = 4fr")
    print(f" • 1fr Value: {(container_width - 60 - 300)/4.0}px\n")
    
    TerminalRenderer.render_grid_visualization(container_width, computed, items, gap)

def demo_scenario_2_subgrid_engineering():
    TerminalRenderer.render_header(
        "SCENARIO 2: CSS Subgrid Level 2 Alignment Engine",
        "Parent Grid (12-Col System) + Subgrid Card Component"
    )
    container_width = 1200.0
    gap = 16.0
    # 6 equal columns for demo clarity
    tracks = [TrackDef(TrackUnit.FR, value=1.0) for _ in range(6)]
    
    engine = CSSGridEngine(container_width, gap, tracks)
    computed = engine.resolve_tracks()
    
    # Subgrid card spanning column 2 to 6 (4 tracks)
    card_subgrid = GridItem(
        name="Card-Container",
        col_start=2,
        col_end=6,
        is_subgrid=True,
        color=Color.CYAN,
        children=[
            GridItem("Avatar-Image", col_start=2, col_end=3, color=Color.MAGENTA),
            GridItem("Header-Title", col_start=3, col_end=5, color=Color.GREEN),
            GridItem("Action-Button", col_start=5, col_end=6, color=Color.YELLOW)
        ]
    )
    
    items = [
        GridItem("Side-Banner", col_start=1, col_end=2, color=Color.RED),
        card_subgrid,
        GridItem("Footer-Note", col_start=6, col_end=7, color=Color.WHITE)
    ]
    
    TerminalRenderer.render_grid_visualization(container_width, computed, items, gap)
    
    print(f"\n{Color.BOLD}{Color.MAGENTA}[Subgrid Insight]:{Color.RESET}")
    print(f" Subgrid mewarisi definisi trek kolom langsung dari grid induk.")
    print(f" Anak dari Card-Container berbaris sempurna dengan trek global tanpa nested-margin hacks.")

def interactive_calculator():
    TerminalRenderer.render_header(
        "INTERACTIVE CALCULATOR: CSS Grid Track Solver",
        "Uji berbagai ukuran container & distribusi fr"
    )
    try:
        raw_width = input(f"{Color.YELLOW}Masukkan Container Width (px) [default 960]: {Color.RESET}").strip()
        width = float(raw_width) if raw_width else 960.0
        
        raw_gap = input(f"{Color.YELLOW}Masukkan Gap (px) [default 24]: {Color.RESET}").strip()
        gap = float(raw_gap) if raw_gap else 24.0
        
        print(f"\n{Color.CYAN}Konfigurasi Trek: [1fr, 300px, 2fr]{Color.RESET}")
        tracks = [
            TrackDef(TrackUnit.FR, value=1.0),
            TrackDef(TrackUnit.PX, value=300.0),
            TrackDef(TrackUnit.FR, value=2.0)
        ]
        
        engine = CSSGridEngine(width, gap, tracks)
        computed = engine.resolve_tracks()
        
        items = [
            GridItem("Col-1 (1fr)", col_start=1, col_end=2, color=Color.GREEN),
            GridItem("Col-2 (300px)", col_start=2, col_end=3, color=Color.BLUE),
            GridItem("Col-3 (2fr)", col_start=3, col_end=4, color=Color.YELLOW)
        ]
        TerminalRenderer.render_grid_visualization(width, computed, items, gap)
        
    except ValueError:
        print(f"{Color.RED}Input numerik tidak valid! Menggunakan default.{Color.RESET}")

def run_automated_tests() -> bool:
    """Verifikasi unit test algoritma resolusi track CSS Grid."""
    print(f"\n{Color.BOLD}Menjalankan Self-Test Verifikasi Algoritma CSS Grid...{Color.RESET}")
    
    # Test 1: Simple 2fr 1fr with 600px, 0 gap
    eng1 = CSSGridEngine(600.0, 0.0, [TrackDef(TrackUnit.FR, 2.0), TrackDef(TrackUnit.FR, 1.0)])
    res1 = eng1.resolve_tracks()
    assert math.isclose(res1[0].resolved_px, 400.0, rel_tol=1e-2), f"Expected 400, got {res1[0].resolved_px}"
    assert math.isclose(res1[1].resolved_px, 200.0, rel_tol=1e-2), f"Expected 200, got {res1[1].resolved_px}"
    print(f" {Color.GREEN}✓ Test 1: Simple Fr Allocation Passed!{Color.RESET}")

    # Test 2: Fixed + Fr with Gap
    eng2 = CSSGridEngine(500.0, 20.0, [TrackDef(TrackUnit.PX, 180.0), TrackDef(TrackUnit.FR, 1.0)])
    res2 = eng2.resolve_tracks()
    # 500 - 20 (gap) - 180 (fixed) = 300px for 1fr
    assert math.isclose(res2[1].resolved_px, 300.0, rel_tol=1e-2), f"Expected 300, got {res2[1].resolved_px}"
    print(f" {Color.GREEN}✓ Test 2: Fixed Track + Gap Subtraction Passed!{Color.RESET}")

    # Test 3: Subgrid Track Inheritance
    sub_resolver = SubgridResolver(res2, 20.0)
    sub_tracks = sub_resolver.resolve_subgrid(2, 3)
    assert len(sub_tracks) == 1 and sub_tracks[0].index == 2, "Subgrid inheritance failed!"
    print(f" {Color.GREEN}✓ Test 3: Subgrid Slice Resolution Passed!{Color.RESET}")
    
    print(f"{Color.BOLD}{Color.GREEN}Semua 3 Assertion Test Lolos 100%!{Color.RESET}\n")
    return True

def main():
    print(f"{Color.BOLD}{Color.WHITE}")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║     CSS Grid Level 2 & Subgrid Technical Engine Simulator           ║")
    print("║            Modul 01: Fondasi Inti Grid Sizing                       ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"{Color.RESET}")
    
    # 1. Jalankan Unit Test Validasi
    run_automated_tests()
    
    # 2. Skenario 1: Resolusi Fr dan Minmax
    demo_scenario_1_fr_resolution()
    
    # 3. Skenario 2: Subgrid Alignment
    demo_scenario_2_subgrid_engineering()
    
    # 4. Mode Interaktif (bila dijalankan di TTY)
    if sys.stdin.isatty():
        interactive_calculator()
    else:
        print(f"{Color.DIM}[Non-interactive mode detected: skipping CLI prompt]{Color.RESET}")

if __name__ == "__main__":
    main()
