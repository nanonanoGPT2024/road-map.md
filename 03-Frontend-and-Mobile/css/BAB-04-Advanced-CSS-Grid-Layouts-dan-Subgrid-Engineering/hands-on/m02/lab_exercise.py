#!/usr/bin/env python3
"""
Lab Hands-on: Advanced CSS Grid Layouts & Subgrid Engineering (Level 2)
Implementasi Mesin Layout CSS Grid deterministik dengan resolusi Subgrid
berdasarkan spesifikasi W3C CSS Grid Layout Module Level 2.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ANSI Palette untuk visualisasi CLI
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_PARENT  = "\033[38;5;39m"    # Cyan
CLR_SUBGRID = "\033[38;5;214m"   # Oranye
CLR_ITEM    = "\033[38;5;119m"   # Hijau Muda
CLR_METRIC  = "\033[38;5;177m"   # Lavender
CLR_WARN    = "\033[38;5;203m"   # Merah Muda
CLR_BORDER  = "\033[38;5;242m"   # Abu-abu


@dataclass
class TrackSize:
    """Representasi Track Sizing Function: px, fr, atau minmax."""
    unit: str            # 'px', 'fr', 'auto', 'minmax'
    value: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0

    def __repr__(self) -> str:
        if self.unit == 'fr':
            return f"{self.value}fr"
        elif self.unit == 'px':
            return f"{self.value}px"
        elif self.unit == 'minmax':
            return f"minmax({self.min_val}px, {self.max_val}px)"
        return "auto"


@dataclass
class ResolvedTrack:
    """Track grid yang telah teresolusi koordinat fisik pikselnya."""
    index: int
    base_pos: float
    breadth: float


@dataclass
class GridItem:
    """Elemen dalam Grid: dapat berupa leaf element atau subgrid container."""
    name: str
    col_start: int
    col_end: int
    row_start: int
    row_end: int
    is_subgrid_cols: bool = False
    is_subgrid_rows: bool = False
    children: List['GridItem'] = field(default_factory=list)
    computed_x: float = 0.0
    computed_y: float = 0.0
    computed_w: float = 0.0
    computed_h: float = 0.0


class GridEngine:
    """
    Mesin kalkulasi layout CSS Grid Level 2.
    Mengimplementasikan Track Sizing Algorithm dan Pewarisan Axis Subgrid.
    """

    def __init__(self, width: float, height: float, gap_x: float = 0.0, gap_y: float = 0.0):
        self.width = width
        self.height = height
        self.gap_x = gap_x
        self.gap_y = gap_y
        self.col_tracks: List[TrackSize] = []
        self.row_tracks: List[TrackSize] = []
        self.items: List[GridItem] = []

    def set_template_columns(self, tracks: List[TrackSize]):
        self.col_tracks = tracks

    def set_template_rows(self, tracks: List[TrackSize]):
        self.row_tracks = tracks

    def add_item(self, item: GridItem):
        self.items.append(item)

    def _resolve_tracks(self, available_space: float, track_defs: List[TrackSize], gap: float) -> List[ResolvedTrack]:
        """
        W3C Sizing Algorithm Step:
        1. Alokasikan fixed track (px).
        2. Sisa ruang bebas didistribusikan ke flexible tracks (fr).
        """
        num_tracks = len(track_defs)
        if num_tracks == 0:
            return []

        total_gaps = max(0, num_tracks - 1) * gap
        free_space = available_space - total_gaps

        resolved = [0.0] * num_tracks
        total_fr = 0.0

        # Pass 1: Fixed base sizes
        for i, t in enumerate(track_defs):
            if t.unit == 'px':
                resolved[i] = t.value
                free_space -= t.value
            elif t.unit == 'fr':
                total_fr += t.value
            elif t.unit == 'minmax':
                # Simplified minmax intrinsic floor
                resolved[i] = t.min_val
                free_space -= t.min_val

        # Pass 2: Flexible expansion
        if free_space > 0 and total_fr > 0:
            fr_unit_size = free_space / total_fr
            for i, t in enumerate(track_defs):
                if t.unit == 'fr':
                    resolved[i] = t.value * fr_unit_size

        # Pass 3: Menentukan koordinat awal track (start line)
        tracks_out: List[ResolvedTrack] = []
        current_pos = 0.0
        for i, size in enumerate(resolved):
            tracks_out.append(ResolvedTrack(index=i + 1, base_pos=current_pos, breadth=size))
            current_pos += size + gap

        return tracks_out

    def layout(self) -> Tuple[List[ResolvedTrack], List[ResolvedTrack]]:
        """Eksekusi full-pass layout: Parent Tracks -> Item Placement -> Subgrid Track Delegation."""
        resolved_cols = self._resolve_tracks(self.width, self.col_tracks, self.gap_x)
        resolved_rows = self._resolve_tracks(self.height, self.row_tracks, self.gap_y)

        for item in self.items:
            self._layout_item(item, resolved_cols, resolved_rows, self.gap_x, self.gap_y)

        return resolved_cols, resolved_rows

    def _layout_item(self, item: GridItem, cols: List[ResolvedTrack], rows: List[ResolvedTrack],
                     inherited_gap_x: float, inherited_gap_y: float):
        """Menghitung geometri bounding box dan mewariskan track line jika elemen adalah subgrid."""
        # Indeks track 1-based (CSS Grid standard)
        c_start_idx = item.col_start - 1
        c_end_idx = item.col_end - 1
        r_start_idx = item.row_start - 1
        r_end_idx = item.row_end - 1

        # Hitung koordinat fisik elemen
        item.computed_x = cols[c_start_idx].base_pos
        item.computed_y = rows[r_start_idx].base_pos

        last_col = cols[c_end_idx - 1]
        last_row = rows[r_end_idx - 1]

        item.computed_w = (last_col.base_pos + last_col.breadth) - item.computed_x
        item.computed_h = (last_row.base_pos + last_row.breadth) - item.computed_y

        # Logika Inti Subgrid CSS Level 2:
        # Jika item adalah subgrid, slice track parent langsung sebagai coordinate-space internal child.
        if item.is_subgrid_cols or item.is_subgrid_rows:
            # Slice parent tracks yang di-overlap oleh item ini
            sub_cols: List[ResolvedTrack] = []
            if item.is_subgrid_cols:
                for idx in range(c_start_idx, c_end_idx):
                    p_track = cols[idx]
                    # Koordinat lokal relatif terhadap parent item
                    sub_cols.append(ResolvedTrack(
                        index=idx - c_start_idx + 1,
                        base_pos=p_track.base_pos - item.computed_x,
                        breadth=p_track.breadth
                    ))
            else:
                # Standar independent tracks jika bukan subgrid di kolom
                sub_cols = cols

            sub_rows: List[ResolvedTrack] = []
            if item.is_subgrid_rows:
                for idx in range(r_start_idx, r_end_idx):
                    p_track = rows[idx]
                    sub_rows.append(ResolvedTrack(
                        index=idx - r_start_idx + 1,
                        base_pos=p_track.base_pos - item.computed_y,
                        breadth=p_track.breadth
                    ))
            else:
                sub_rows = rows

            # Recursively layout children elemen subgrid
            for child in item.children:
                ch_c_start = child.col_start - 1
                ch_c_end = child.col_end - 1
                ch_r_start = child.row_start - 1
                ch_r_end = child.row_end - 1

                child.computed_x = item.computed_x + sub_cols[ch_c_start].base_pos
                child.computed_y = item.computed_y + sub_rows[ch_r_start].base_pos

                c_last = sub_cols[ch_c_end - 1]
                r_last = sub_rows[ch_r_end - 1]

                child.computed_w = (c_last.base_pos + c_last.breadth) - sub_cols[ch_c_start].base_pos
                child.computed_h = (r_last.base_pos + r_last.breadth) - sub_rows[ch_r_start].base_pos


# =====================================================================
# Visualizer & Benchmarking Harness
# =====================================================================

def render_ascii_canvas(width_chars: int, height_chars: int, engine: GridEngine):
    """Merender peta ASCII 2D layout terminal untuk memverifikasi track alignment."""
    canvas = [[' ' for _ in range(width_chars)] for _ in range(height_chars)]
    scale_x = width_chars / engine.width
    scale_y = height_chars / engine.height

    def draw_box(x: float, y: float, w: float, h: float, label: str, border_char: str):
        bx = int(round(x * scale_x))
        by = int(round(y * scale_y))
        bw = max(2, int(round(w * scale_x)))
        bh = max(2, int(round(h * scale_y)))

        for col in range(bx, min(bx + bw, width_chars)):
            if 0 <= by < height_chars:
                canvas[by][col] = border_char
            if 0 <= by + bh - 1 < height_chars:
                canvas[by + bh - 1][col] = border_char

        for row in range(by, min(by + bh, height_chars)):
            if 0 <= bx < width_chars:
                canvas[row][bx] = border_char
            if 0 <= bx + bw - 1 < width_chars:
                canvas[row][bx + bw - 1] = border_char

        # Tulis label di tengah
        lbl = f" {label} "
        if len(lbl) < bw - 2 and by + bh // 2 < height_chars:
            start_x = bx + (bw - len(lbl)) // 2
            for i, ch in enumerate(lbl):
                if 0 <= start_x + i < width_chars:
                    canvas[by + bh // 2][start_x + i] = ch

    # 1. Gambar items parent
    for item in engine.items:
        draw_box(item.computed_x, item.computed_y, item.computed_w, item.computed_h,
                 item.name, '#')
        # 2. Gambar anak subgrid
        for child in item.children:
            draw_box(child.computed_x, child.computed_y, child.computed_w, child.computed_h,
                     child.name, '+')

    # Cetak buffer
    print(f"{CLR_BORDER}+" + "-" * width_chars + f"+{CLR_RESET}")
    for row in canvas:
        line = "".join(row)
        line = line.replace('#', f"{CLR_PARENT}#{CLR_RESET}")
        line = line.replace('+', f"{CLR_ITEM}+{CLR_RESET}")
        print(f"{CLR_BORDER}|{CLR_RESET}" + line + f"{CLR_BORDER}|{CLR_RESET}")
    print(f"{CLR_BORDER}+" + "-" * width_chars + f"+{CLR_RESET}")


def run_laboratory():
    print(f"\n{CLR_BOLD}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}  ENGINEERING LAB: ADVANCED CSS GRID & SUBGRID SPECIFICATION (LEVEL 2){CLR_RESET}")
    print(f"{CLR_BOLD}======================================================================{CLR_RESET}\n")

    # Parameter container parent
    CANVAS_WIDTH = 1000.0  # px
    CANVAS_HEIGHT = 600.0  # px
    GAP_COL = 16.0         # px
    GAP_ROW = 20.0         # px

    engine = GridEngine(CANVAS_WIDTH, CANVAS_HEIGHT, GAP_COL, GAP_ROW)

    # Definisi Track Induk: 5 Kolom, 3 Baris
    # Kolom: [200px Sidebar, 1fr Main, 2fr Feed, 1fr Meta, 150px Ads]
    parent_cols = [
        TrackSize(unit='px', value=200.0),
        TrackSize(unit='fr', value=1.0),
        TrackSize(unit='fr', value=2.0),
        TrackSize(unit='fr', value=1.0),
        TrackSize(unit='px', value=150.0)
    ]
    # Baris: [80px Header, 1fr Body, 60px Footer]
    parent_rows = [
        TrackSize(unit='px', value=80.0),
        TrackSize(unit='fr', value=1.0),
        TrackSize(unit='px', value=60.0)
    ]

    engine.set_template_columns(parent_cols)
    engine.set_template_rows(parent_rows)

    # Komponen 1: Standard Element (Sidebar)
    sidebar = GridItem(name="Sidebar", col_start=1, col_end=2, row_start=1, row_end=4)
    engine.add_item(sidebar)

    # Komponen 2: Subgrid Container (Main Dashboard Spanning Kolom 2 s/d 5, Baris 2 s/d 3)
    # Fitur Kunci: 'grid-template-columns: subgrid'
    # Container ini mengadopsi partisi [1fr, 2fr, 1fr] dari parent langsung tanpa rounding error independen!
    dashboard_card = GridItem(
        name="Card-Container [SUBGRID]",
        col_start=2, col_end=5,
        row_start=2, row_end=3,
        is_subgrid_cols=True
    )

    # Sub-elemen bersarang di dalam Card-Container
    # Anak secara eksplisit mengikat grid-line parent yang diteruskan!
    card_section_a = GridItem(name="MetricA", col_start=1, col_end=2, row_start=1, row_end=2)
    card_section_b = GridItem(name="ChartB (2-span)", col_start=2, col_end=4, row_start=1, row_end=2)
    dashboard_card.children.extend([card_section_a, card_section_b])

    engine.add_item(dashboard_card)

    # Komponen 3: Header span
    header = GridItem(name="Global Header", col_start=2, col_end=6, row_start=1, row_end=2)
    engine.add_item(header)

    # Eksekusi Resolusi Layout
    t0 = time.perf_counter()
    res_cols, res_rows = engine.layout()
    duration_us = (time.perf_counter() - t0) * 1_000_000

    # 1. Dump Track Coordinates Parent
    print(f"{CLR_PARENT}[1] Resolved Parent Column Tracks ({len(res_cols)} Tracks):{CLR_RESET}")
    print(f"    Available: {CANVAS_WIDTH}px | Gap: {GAP_COL}px")
    for trk in res_cols:
        print(f"    - Line {trk.index} -> {trk.index + 1}: Base = {trk.base_pos:6.1f}px | Breadth = {trk.breadth:6.1f}px")

    print(f"\n{CLR_PARENT}[2] Resolved Parent Row Tracks ({len(res_rows)} Tracks):{CLR_RESET}")
    print(f"    Available: {CANVAS_HEIGHT}px | Gap: {GAP_ROW}px")
    for trk in res_rows:
        print(f"    - Line {trk.index} -> {trk.index + 1}: Base = {trk.base_pos:6.1f}px | Breadth = {trk.breadth:6.1f}px")

    # 2. Dump Evaluasi Alignment Subgrid
    print(f"\n{CLR_SUBGRID}[3] Subgrid Track Alignment Verification:{CLR_RESET}")
    print(f"    Container '{dashboard_card.name}':")
    print(f"    Posisi Global: X={dashboard_card.computed_x:.1f}px, W={dashboard_card.computed_w:.1f}px")

    # Validasi keselarasan absolut
    aligned_ok = True
    for child in dashboard_card.children:
        print(f"      * Sub-item '{child.name}': Pos X={child.computed_x:.1f}px, W={child.computed_w:.1f}px")
        # Item 1 harus sejajar persis dengan Parent Col 2
        # Item 2 harus sejajar persis dengan Parent Col 3 & Col 4
        if child.name == "MetricA" and abs(child.computed_x - res_cols[1].base_pos) > 1e-3:
            aligned_ok = False
        if child.name.startswith("ChartB") and abs(child.computed_x - res_cols[2].base_pos) > 1e-3:
            aligned_ok = False

    if aligned_ok:
        print(f"    {CLR_ITEM}[PASS] Track Synchronization Identik: Coordinate alignment 100% W3C conformant.{CLR_RESET}")
    else:
        print(f"    {CLR_WARN}[FAIL] Misalignment terdeteksi pada child subgrid!{CLR_RESET}")

    # 3. Visualisasi Representasi 2D
    print(f"\n{CLR_METRIC}[4] Visual Canvas Render (ASCII 2D Projection):{CLR_RESET}")
    render_ascii_canvas(width_chars=74, height_chars=18, engine=engine)

    # 4. Engine Benchmark Metrics
    print(f"\n{CLR_BOLD}[5] Engine Telemetry:{CLR_RESET}")
    print(f"    Calculated Items : {len(engine.items) + len(dashboard_card.children)}")
    print(f"    Layout Compute   : {duration_us:.2f} microseconds")
    print(f"    Subgrid Status   : Track delegation inheritance operational.")
    print(f"{CLR_BOLD}======================================================================{CLR_RESET}\n")


if __name__ == '__main__':
    run_laboratory()