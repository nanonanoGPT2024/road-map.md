#!/usr/bin/env python3
"""
Lab Hands-on: Modern Layout Engines (Flexbox 1D & CSS Grid 2D) Deep Dive
Simulasi matematis dan algoritma layout resolver untuk CSS Flexible Box Layout
dan CSS Grid Multi-Dimensi Track Sizing & Placement.
"""

from typing import List, Dict, Tuple, Optional
import math
import sys

# ANSI Color Codes untuk visualisasi terminal
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_CYAN   = "\033[36m"
C_GREEN  = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE   = "\033[34m"
C_MAG    = "\033[35m"
C_WHITE  = "\033[37m"
C_RED    = "\033[31m"


class FlexItem:
    """Merepresentasikan item di dalam Flex Container sesuai W3C Flexbox spec."""
    def __init__(self, name: str, basis: float, grow: float = 0.0, shrink: float = 1.0, 
                 min_size: float = 0.0, max_size: float = float('inf')):
        self.name = name
        self.basis = basis
        self.grow = grow
        self.shrink = shrink
        self.min_size = min_size
        self.max_size = max_size
        self.computed_size = 0.0
        self.offset = 0.0


class FlexboxResolver:
    """
    Engine deterministik untuk menghitung distribusi ruang 1-dimensi
    berdasarkan CSS Flexible Box Layout Module Level 1.
    """
    def __init__(self, container_size: float, justify_content: str = "flex-start"):
        self.container_size = container_size
        self.justify_content = justify_content
        self.items: List[FlexItem] = []

    def add_item(self, item: FlexItem) -> None:
        self.items.append(item)

    def resolve(self) -> None:
        """
        Algoritma W3C:
        1. Hitung sum(basis).
        2. Tentukan free space: container_size - sum(basis).
        3. Jika free space > 0: distribusikan via flex-grow.
        4. Jika free space < 0: lakukan penyusutan via scaled flex-shrink (shrink * basis).
        5. Clamp ukuran terhadap min_size dan max_size.
        6. Terapkan justify-content alignment.
        """
        total_basis = sum(i.basis for i in self.items)
        free_space = self.container_size - total_basis

        if free_space >= 0:
            total_grow = sum(i.grow for i in self.items)
            for item in self.items:
                if total_grow > 0:
                    growth = (item.grow / total_grow) * free_space
                    item.computed_size = item.basis + growth
                else:
                    item.computed_size = item.basis
                item.computed_size = max(item.min_size, min(item.computed_size, item.max_size))
        else:
            deficit = abs(free_space)
            total_scaled_shrink = sum(i.shrink * i.basis for i in self.items)
            for item in self.items:
                if total_scaled_shrink > 0:
                    shrink_factor = (item.shrink * item.basis) / total_scaled_shrink
                    item.computed_size = item.basis - (shrink_factor * deficit)
                else:
                    item.computed_size = item.basis
                item.computed_size = max(item.min_size, min(item.computed_size, item.max_size))

        # Alignment: justify-content
        total_resolved = sum(i.computed_size for i in self.items)
        remaining_gap = self.container_size - total_resolved
        current_offset = 0.0

        if self.justify_content == "flex-start":
            for item in self.items:
                item.offset = current_offset
                current_offset += item.computed_size
        elif self.justify_content == "center":
            current_offset = max(0.0, remaining_gap / 2.0)
            for item in self.items:
                item.offset = current_offset
                current_offset += item.computed_size
        elif self.justify_content == "space-between":
            gap = remaining_gap / (len(self.items) - 1) if len(self.items) > 1 else 0.0
            for item in self.items:
                item.offset = current_offset
                current_offset += item.computed_size + gap


class GridItem:
    """Elemen dalam Grid 2D dengan koordinat baris dan kolom 1-indexed (CSS style)."""
    def __init__(self, name: str, col_start: int, col_span: int, row_start: int, row_span: int):
        self.name = name
        self.col_start = col_start
        self.col_span = col_span
        self.row_start = row_start
        self.row_span = row_span
        # Bounding box absolut: x, y, width, height
        self.bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


class GridTrack:
    """Tipe track: 'fixed' (pixel eksplisit) atau 'fr' (fraksi ruang fleksibel)."""
    def __init__(self, spec: str):
        self.spec = spec
        if spec.endswith("px"):
            self.kind = "fixed"
            self.value = float(spec[:-2])
        elif spec.endswith("fr"):
            self.kind = "fr"
            self.value = float(spec[:-2])
        else:
            raise ValueError(f"Unit tidak didukung: {spec}")
        self.resolved_size = 0.0
        self.start_coord = 0.0


class GridResolver:
    """
    Engine perhitungan track 2D dan perataan matriks koordinat
    CSS Grid Layout Module Level 2.
    """
    def __init__(self, width: float, height: float, col_specs: List[str], row_specs: List[str], gap: float = 0.0):
        self.width = width
        self.height = height
        self.gap = gap
        self.col_tracks = [GridTrack(s) for s in col_specs]
        self.row_tracks = [GridTrack(s) for s in row_specs]
        self.items: List[GridItem] = []

    def add_item(self, item: GridItem) -> None:
        self.items.append(item)

    def _resolve_dimension(self, available_space: float, tracks: List[GridTrack]) -> None:
        """Menyelesaikan ukuran track CSS Grid: fixed vs 'fr' proportional space."""
        total_gaps = (len(tracks) - 1) * self.gap
        fixed_sum = sum(t.value for t in tracks if t.kind == "fixed")
        space_for_fr = max(0.0, available_space - total_gaps - fixed_sum)
        total_fr = sum(t.value for t in tracks if t.kind == "fr")

        for track in tracks:
            if track.kind == "fixed":
                track.resolved_size = track.value
            elif track.kind == "fr":
                track.resolved_size = (track.value / total_fr) * space_for_fr if total_fr > 0 else 0.0

        current_pos = 0.0
        for track in tracks:
            track.start_coord = current_pos
            current_pos += track.resolved_size + self.gap

    def resolve(self) -> None:
        """Hitung dimensi absolut seluruh kolom, baris, dan penempatan item."""
        self._resolve_dimension(self.width, self.col_tracks)
        self._resolve_dimension(self.height, self.row_tracks)

        for item in self.items:
            # Hitung X dan Lebar
            c_start_idx = item.col_start - 1
            c_end_idx = c_start_idx + item.col_span - 1
            x = self.col_tracks[c_start_idx].start_coord
            w = (self.col_tracks[c_end_idx].start_coord + self.col_tracks[c_end_idx].resolved_size) - x

            # Hitung Y dan Tinggi
            r_start_idx = item.row_start - 1
            r_end_idx = r_start_idx + item.row_span - 1
            y = self.row_tracks[r_start_idx].start_coord
            h = (self.row_tracks[r_end_idx].start_coord + self.row_tracks[r_end_idx].resolved_size) - y

            item.bounds = (x, y, w, h)


class TerminalVisualizer:
    """Merender layout berbasis karakter ASCII / ANSI Block."""
    @staticmethod
    def render_canvas(width_chars: int, height_chars: int, rects: List[Tuple[str, int, int, int, int, str]]) -> None:
        canvas = [[" " for _ in range(width_chars)] for _ in range(height_chars)]
        
        # Gambar border canvas
        for r in range(height_chars):
            canvas[r][0] = "│"
            canvas[r][width_chars - 1] = "│"
        for c in range(width_chars):
            canvas[0][c] = "─"
            canvas[height_chars - 1][c] = "─"
        canvas[0][0] = "┌"
        canvas[0][width_chars - 1] = "┐"
        canvas[height_chars - 1][0] = "└"
        canvas[height_chars - 1][width_chars - 1] = "┘"

        # Gambar setiap item
        for name, x, y, w, h, color in rects:
            for r in range(y, min(y + h, height_chars - 1)):
                for c in range(x, min(x + w, width_chars - 1)):
                    if r == y or r == y + h - 1:
                        canvas[r][c] = f"{color}━{C_RESET}"
                    elif c == x or c == x + w - 1:
                        canvas[r][c] = f"{color}┃{C_RESET}"
                    else:
                        canvas[r][c] = f"{color}░{C_RESET}"
            
            # Print label di tengah kotak jika muat
            label = f" {name} "
            if w > len(label) + 2 and h >= 3:
                mid_r = y + h // 2
                mid_c = x + (w - len(label)) // 2
                for idx, ch in enumerate(label):
                    if 0 <= mid_c + idx < width_chars - 1:
                        canvas[mid_r][mid_c + idx] = f"{C_BOLD}{color}{ch}{C_RESET}"

        # Cetak ke layar
        for row in canvas:
            print("".join(row))


def run_flexbox_lab() -> None:
    print(f"\n{C_BOLD}{C_CYAN}=== [1] SIMULASI 1D: FLEXBOX RESOLUTION ALGORITHM ==={C_RESET}")
    print("Mendistribusikan elemen dengan Flex-Grow & Flex-Shrink secara matematis.\n")

    # Skenario 1: Flex Grow (Positif Free Space)
    container_width = 800.0
    fb = FlexboxResolver(container_size=container_width, justify_content="flex-start")
    fb.add_item(FlexItem(name="Sidebar", basis=200.0, grow=1.0, shrink=0.0))
    fb.add_item(FlexItem(name="Content", basis=300.0, grow=2.0, shrink=1.0))
    fb.add_item(FlexItem(name="Widget",  basis=100.0, grow=1.0, shrink=1.0))

    fb.resolve()

    print(f"{C_BOLD}Skenario A: Free Space Positif (Container: {container_width}px){C_RESET}")
    print("Initial Basis: 200px + 300px + 100px = 600px | Free Space: +200px")
    print(f"{'Item Name':<12} | {'Basis':<8} | {'Grow':<5} | {'Computed Width':<15} | {'Offset'}")
    print("-" * 60)
    for item in fb.items:
        print(f"{C_GREEN}{item.name:<12}{C_RESET} | {item.basis:<8.1f} | {item.grow:<5.1f} | {C_YELLOW}{item.computed_size:<15.2f}{C_RESET} | {item.offset:.2f}px")

    # Skenario 2: Flex Shrink (Defisit Ruang Negatif)
    narrow_container = 450.0
    fb_shrink = FlexboxResolver(container_size=narrow_container)
    fb_shrink.add_item(FlexItem(name="Card-A", basis=200.0, grow=0.0, shrink=1.0))
    fb_shrink.add_item(FlexItem(name="Card-B", basis=250.0, grow=0.0, shrink=2.0))
    fb_shrink.add_item(FlexItem(name="Card-C", basis=150.0, grow=0.0, shrink=1.0))

    fb_shrink.resolve()
    print(f"\n{C_BOLD}Skenario B: Ruang Terbatas / Defisit (Container: {narrow_container}px){C_RESET}")
    print("Initial Basis: 200px + 250px + 150px = 600px | Defisit: -150px")
    print("Penyusutan proporsional berbasis `shrink * basis`")
    print(f"{'Item Name':<12} | {'Basis':<8} | {'Shrink':<6} | {'Computed Width':<15} | {'Penyusutan'}")
    print("-" * 65)
    for item in fb_shrink.items:
        shrink_amount = item.basis - item.computed_size
        print(f"{C_RED}{item.name:<12}{C_RESET} | {item.basis:<8.1f} | {item.shrink:<6.1f} | {C_YELLOW}{item.computed_size:<15.2f}{C_RESET} | -{shrink_amount:.2f}px")


def run_css_grid_lab() -> None:
    print(f"\n{C_BOLD}{C_CYAN}=== [2] SIMULASI 2D: CSS GRID MULTI-DIMENSIONAL ENGINE ==={C_RESET}")
    print("Layout Kompleks: Track Sizing (fixed px + fr units) & 2D Grid Area Placement\n")

    grid_width = 80.0   # Diskalakan ke karakter terminal
    grid_height = 20.0  # Karakter tinggi
    
    # Template: Columns: [15px, 2fr, 1fr], Rows: [4px, 1fr, 3px]
    grid = GridResolver(
        width=grid_width, 
        height=grid_height, 
        col_specs=["16px", "2fr", "1fr"], 
        row_specs=["3px", "1fr", "3px"], 
        gap=1.0
    )

    # Tambahkan Item Grid dengan grid-column & grid-row
    grid.add_item(GridItem("Header", col_start=1, col_span=3, row_start=1, row_span=1))
    grid.add_item(GridItem("Sidebar", col_start=1, col_span=1, row_start=2, row_span=1))
    grid.add_item(GridItem("Main", col_start=2, col_span=1, row_start=2, row_span=1))
    grid.add_item(GridItem("Ads", col_start=3, col_span=1, row_start=2, row_span=1))
    grid.add_item(GridItem("Footer", col_start=1, col_span=3, row_start=3, row_span=1))

    grid.resolve()

    print(f"{C_BOLD}Spesifikasi Kolom:{C_RESET} [16px, 2fr, 1fr]")
    for idx, c in enumerate(grid.col_tracks, 1):
        print(f"  Track Col #{idx}: Spec={c.spec:<5} -> Resolved: {c.resolved_size:.2f} unit (X={c.start_coord:.2f})")

    print(f"\n{C_BOLD}Spesifikasi Baris:{C_RESET} [3px, 1fr, 3px]")
    for idx, r in enumerate(grid.row_tracks, 1):
        print(f"  Track Row #{idx}: Spec={r.spec:<5} -> Resolved: {r.resolved_size:.2f} unit (Y={r.start_coord:.2f})")

    print(f"\n{C_BOLD}Calculated Bounding Boxes (X, Y, Width, Height):{C_RESET}")
    for item in grid.items:
        x, y, w, h = item.bounds
        print(f"  [{item.name:<7}] Col:{item.col_start} span {item.col_span} | Row:{item.row_start} span {item.row_span} => BoundingBox=({x:.1f}, {y:.1f}, {w:.1f}, {h:.1f})")

    print(f"\n{C_BOLD}{C_MAG}Visualisasi Virtual DOM Terminal (Representasi Grafis Hasil Komputasi Grid):{C_RESET}")
    colors = [C_CYAN, C_GREEN, C_YELLOW, C_BLUE, C_MAG]
    rects_to_draw = []
    for idx, item in enumerate(grid.items):
        x, y, w, h = item.bounds
        rects_to_draw.append((
            item.name, 
            int(round(x)), 
            int(round(y)), 
            int(round(w)), 
            int(round(h)), 
            colors[idx % len(colors)]
        ))

    TerminalVisualizer.render_canvas(int(grid_width), int(grid_height), rects_to_draw)


def main() -> None:
    print(f"{C_BOLD}{C_WHITE}╔═══════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_WHITE}║   ENGINE LAB: SISTEM TATA LETAK MODERN (FLEXBOX & CSS GRID 2D)   ║{C_RESET}")
    print(f"{C_BOLD}{C_WHITE}╚═══════════════════════════════════════════════════════════════════╝{C_RESET}")

    run_flexbox_lab()
    run_css_grid_lab()
    
    print(f"\n{C_GREEN}{C_BOLD}✔ Eksekusi simulasi layout engine selesai tanpa dependensi eksternal.{C_RESET}\n")


if __name__ == "__main__":
    main()