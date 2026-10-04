#!/usr/bin/env python3
"""
Lab Hands-on: SwiftUI Layout Engine & Adaptive System Deep Dive
Simulasi komputasi three-phase layout negotiation SwiftUI, Stack distribution algorithm,
layout priority partitioning, dan responsive adaptive size classes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import math
import sys
import time

# --- ANSI Formatting Constants ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"
CLR_BG_DARK = "\033[48;5;236m"


# --- Data Structures & Geometry Primitives ---

@dataclass(frozen=True)
class ProposedSize:
    """
    Merepresentasikan ukuran yang diusulkan oleh Parent View ke Child View.
    None melambangkan nilai 'unspecified' (analog dengan nil pada ProposedViewSize SwiftUI).
    math.inf melambangkan proposal ukuran tak hingga (greedy test).
    """
    width: Optional[float]
    height: Optional[float]

    @classmethod
    def unspecified(cls) -> "ProposedSize":
        return cls(None, None)

    @classmethod
    def infinity(cls) -> "ProposedSize":
        return cls(math.inf, math.inf)

    @classmethod
    def exact(cls, w: float, h: float) -> "ProposedSize":
        return cls(float(w), float(h))


@dataclass(copy=True)
class Size:
    width: float
    height: float


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Rect:
    origin: Point
    size: Size


class UserInterfaceSizeClass(Enum):
    COMPACT = "Compact"
    REGULAR = "Regular"


@dataclass
class EnvironmentValues:
    horizontal_size_class: UserInterfaceSizeClass
    vertical_size_class: UserInterfaceSizeClass


# --- Base View Protocol ---

class View:
    """
    Protokol dasar View yang mematuhi kontrak Layout SwiftUI:
    1. Parent mengusulkan ukuran via size_that_fits(proposal)
    2. Child menentukan ukurannya sendiri
    3. Parent memposisikan Child via place(at, anchor)
    """
    def __init__(self, layout_priority: float = 0.0):
        self.layout_priority: float = layout_priority
        self.frame: Rect = Rect(Point(0.0, 0.0), Size(0.0, 0.0))
        self.id: str = f"{self.__class__.__name__}_{id(self) % 10000}"

    def size_that_fits(self, proposal: ProposedSize, env: EnvironmentValues) -> Size:
        raise NotImplementedError

    def place(self, position: Point, computed_size: Size):
        self.frame = Rect(Point(position.x, position.y), Size(computed_size.width, computed_size.height))

    def get_children(self) -> List["View"]:
        return []


# --- Concrete Primitive Views ---

class Text(View):
    """
    Intrinsic content sizing: Memecah teks per kata untuk mensimulasikan
    word wrapping dinamis berdasarkan proposal lebar.
    """
    def __init__(self, content: str, line_height: float = 14.0, char_width: float = 7.5, **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.line_height = line_height
        self.char_width = char_width

    def size_that_fits(self, proposal: ProposedSize, env: EnvironmentValues) -> Size:
        words = self.content.split()
        if not words:
            return Size(0.0, 0.0)

        # Jika lebar tidak dibatasi/unspecified
        if proposal.width is None or math.isinf(proposal.width):
            total_chars = len(self.content)
            return Size(total_chars * self.char_width, self.line_height)

        # Algoritma dynamic word-wrap
        max_allowed_w = proposal.width
        lines = 1
        current_line_w = 0.0

        for word in words:
            word_w = len(word) * self.char_width
            space_w = self.char_width if current_line_w > 0 else 0.0

            if current_line_w + space_w + word_w <= max_allowed_w:
                current_line_w += space_w + word_w
            else:
                lines += 1
                current_line_w = word_w

        return Size(min(max_allowed_w, len(self.content) * self.char_width), lines * self.line_height)


class Spacer(View):
    """
    Greedy flexible space view: Menelan sisa ruang yang tersedia di Stack.
    """
    def __init__(self, min_length: float = 8.0, **kwargs):
        super().__init__(**kwargs)
        self.min_length = min_length

    def size_that_fits(self, proposal: ProposedSize, env: EnvironmentValues) -> Size:
        # Default fallback ke min_length jika proposal unspecified
        w = proposal.width if (proposal.width is not None and not math.isinf(proposal.width)) else self.min_length
        h = proposal.height if (proposal.height is not None and not math.isinf(proposal.height)) else self.min_length
        return Size(max(self.min_length, w), max(self.min_length, h))


class FrameModifier(View):
    """
    Modifier .frame(width, height) yang mengunci proposal dimensi child.
    """
    def __init__(self, content: View, width: Optional[float] = None, height: Optional[float] = None, **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.target_w = width
        self.target_h = height

    def size_that_fits(self, proposal: ProposedSize, env: EnvironmentValues) -> Size:
        resolved_w = self.target_w if self.target_w is not None else proposal.width
        resolved_h = self.target_h if self.target_h is not None else proposal.height

        child_proposal = ProposedSize(resolved_w, resolved_h)
        child_size = self.content.size_that_fits(child_proposal, env)

        return Size(
            self.target_w if self.target_w is not None else child_size.width,
            self.target_h if self.target_h is not None else child_size.height
        )

    def place(self, position: Point, computed_size: Size):
        super().place(position, computed_size)
        # Tempatkan child di tengah modifier frame
        self.content.place(position, computed_size)

    def get_children(self) -> List[View]:
        return [self.content]


# --- Container Layout Views (HStack Layout Engine) ---

class HStack(View):
    """
    Implementasi akurat algoritma SwiftUI HStack Distribution:
    1. Mengelompokkan views berdasarkan Layout Priority.
    2. Menghitung 'flexibility' tiap view melalui variansi response ukuran saat diajukan min vs max.
    3. Mengalokasikan sisa ruang linier ke view paling kaku terlebih dahulu,
       kemudian membagi rata sisa ruang untuk flexible views.
    """
    def __init__(self, spacing: float = 8.0, children: List[View] = None, **kwargs):
        super().__init__(**kwargs)
        self.spacing = spacing
        self.children: List[View] = children or []

    def get_children(self) -> List[View]:
        return self.children

    def _distribute_widths(self, available_w: float, env: EnvironmentValues) -> Dict[int, float]:
        """
        Sub-algoritma pembagian lebar HStack SwiftUI.
        """
        n = len(self.children)
        if n == 0:
            return {}

        total_spacing = self.spacing * (n - 1)
        remaining_w = max(0.0, available_w - total_spacing)
        allocated: Dict[int, float] = {}

        # Kelompokkan indeks berdasarkan layout priority (descending)
        priorities = sorted(list({c.layout_priority for c in self.children}), reverse=True)

        for prio in priorities:
            group_indices = [idx for idx, c in enumerate(self.children) if c.layout_priority == prio]
            unallocated_in_group = list(group_indices)

            while unallocated_in_group:
                # Bagikan sisa ruang merata ke elemen tersisa dalam priority bucket ini
                target_proposal = remaining_w / len(unallocated_in_group)
                
                # Cari view dengan fleksibilitas terkecil (perbedaan respon ukuran thd target)
                def measure_clamp(idx: int) -> float:
                    c = self.children[idx]
                    sz = c.size_that_fits(ProposedSize(target_proposal, None), env)
                    return sz.width

                # Sort by intrinsic width taken
                unallocated_in_group.sort(key=measure_clamp)
                least_flex_idx = unallocated_in_group[0]
                
                child_sz = self.children[least_flex_idx].size_that_fits(ProposedSize(target_proposal, None), env)
                actual_w = min(child_sz.width, remaining_w)
                
                allocated[least_flex_idx] = actual_w
                remaining_w = max(0.0, remaining_w - actual_w)
                unallocated_in_group.remove(least_flex_idx)

        return allocated

    def size_that_fits(self, proposal: ProposedSize, env: EnvironmentValues) -> Size:
        n = len(self.children)
        if n == 0:
            return Size(0.0, 0.0)

        total_spacing = self.spacing * (n - 1)

        # Unspecified atau Infinity width: biarkan tiap anak mengukur diri secara ideal
        if proposal.width is None or math.isinf(proposal.width):
            total_w = total_spacing
            max_h = 0.0
            for child in self.children:
                sz = child.size_that_fits(ProposedSize.unspecified(), env)
                total_w += sz.width
                max_h = max(max_h, sz.height)
            return Size(total_w, max_h)

        # Specified width: jalankan algoritma distribusi
        allocated = self._distribute_widths(proposal.width, env)
        max_h = 0.0
        for idx, child in enumerate(self.children):
            w = allocated.get(idx, 0.0)
            sz = child.size_that_fits(ProposedSize(w, proposal.height), env)
            max_h = max(max_h, sz.height)

        return Size(proposal.width, max_h)

    def place(self, position: Point, computed_size: Size):
        super().place(position, computed_size)
        if not self.children:
            return

        env_default = EnvironmentValues(UserInterfaceSizeClass.REGULAR, UserInterfaceSizeClass.REGULAR)
        allocated = self._distribute_widths(computed_size.width, env_default)

        current_x = position.x
        for idx, child in enumerate(self.children):
            w = allocated.get(idx, 0.0)
            sz = child.size_that_fits(ProposedSize(w, computed_size.height), env_default)
            # Alignment vertikal Center
            y_offset = position.y + (computed_size.height - sz.height) / 2.0
            child.place(Point(current_x, y_offset), Size(w, sz.height))
            current_x += w + self.spacing


# --- Adaptive Layout View (SizeClass Branching) ---

class AdaptiveContainer(View):
    """
    Mensimulasikan deklarasi adaptif seperti:
    if horizontalSizeClass == .compact { VStack } else { HStack }
    """
    def __init__(self, compact_view: View, regular_view: View, **kwargs):
        super().__init__(**kwargs)
        self.compact_view = compact_view
        self.regular_view = regular_view
        self.active_view: View = regular_view

    def _resolve(self, env: EnvironmentValues) -> View:
        if env.horizontal_size_class == UserInterfaceSizeClass.COMPACT:
            return self.compact_view
        return self.regular_view

    def size_that_fits(self, proposal: ProposedSize, env: EnvironmentValues) -> Size:
        self.active_view = self._resolve(env)
        return self.active_view.size_that_fits(proposal, env)

    def place(self, position: Point, computed_size: Size):
        super().place(position, computed_size)
        self.active_view.place(position, computed_size)

    def get_children(self) -> List[View]:
        return [self.active_view]


# --- ASCII Canvas Renderer & Diagnostics ---

def dump_layout_tree(view: View, depth: int = 0):
    indent = "  " * depth
    f = view.frame
    prio_str = f" [prio: {CLR_YELLOW}{view.layout_priority}{CLR_RESET}]" if view.layout_priority > 0 else ""
    type_str = f"{CLR_CYAN}{view.__class__.__name__}{CLR_RESET}"
    rect_str = f"({CLR_GREEN}x:{f.origin.x:5.1f}, y:{f.origin.y:5.1f}{CLR_RESET} | {CLR_MAGENTA}w:{f.size.width:5.1f}, h:{f.size.height:5.1f}{CLR_RESET})"
    
    extra = ""
    if isinstance(view, Text):
        extra = f' "{CLR_DIM}{view.content[:15]}...{CLR_RESET}"'
    elif isinstance(view, FrameModifier):
        extra = f" (target_w={view.target_w}, target_h={view.target_h})"

    print(f"{indent}↳ {type_str}{prio_str} -> {rect_str}{extra}")
    for child in view.get_children():
        dump_layout_tree(child, depth + 1)


def render_ascii_wireframe(view: View, canvas_width: int = 70, canvas_height: int = 12):
    """
    Merender representasi grafis ASCII sederhana dari tree koordinat.
    """
    grid = [[" " for _ in range(canvas_width)] for _ in range(canvas_height)]

    def draw_rect(r: Rect, label: str):
        # Scale to canvas coordinates
        scale_x = (canvas_width - 1) / max(view.frame.size.width, 1.0)
        scale_y = (canvas_height - 1) / max(view.frame.size.height, 1.0)

        x1 = int(round(r.origin.x * scale_x))
        y1 = int(round(r.origin.y * scale_y))
        x2 = min(canvas_width - 1, int(round((r.origin.x + r.size.width) * scale_x)))
        y2 = min(canvas_height - 1, int(round((r.origin.y + r.size.height) * scale_y)))

        for x in range(x1, x2 + 1):
            if 0 <= y1 < canvas_height: grid[y1][x] = "─"
            if 0 <= y2 < canvas_height: grid[y2][x] = "─"
        for y in range(y1, y2 + 1):
            if 0 <= x1 < canvas_width: grid[y][x1] = "│"
            if 0 <= x2 < canvas_width: grid[y][x2] = "│"

        if 0 <= x1 < canvas_width and 0 <= y1 < canvas_height: grid[y1][x1] = "┌"
        if 0 <= x2 < canvas_width and 0 <= y1 < canvas_height: grid[y1][x2] = "┐"
        if 0 <= x1 < canvas_width and 0 <= y2 < canvas_height: grid[y2][x1] = "└"
        if 0 <= x2 < canvas_width and 0 <= y2 < canvas_height: grid[y2][x2] = "┘"

        # Tulis label
        lbl_x = x1 + 1
        lbl_y = y1 + 1
        for i, char in enumerate(label[:max(0, x2 - x1 - 1)]):
            if 0 <= lbl_y < canvas_height and 0 <= lbl_x + i < canvas_width:
                grid[lbl_y][lbl_x + i] = char

    def traverse(node: View):
        if node != view and node.frame.size.width > 0 and node.frame.size.height > 0:
            draw_rect(node.frame, node.__class__.__name__)
        for ch in node.get_children():
            traverse(ch)

    traverse(view)
    border = "+" + "-" * canvas_width + "+"
    print(f"{CLR_BLUE}{border}{CLR_RESET}")
    for row in grid:
        print(f"{CLR_BLUE}│{CLR_RESET}" + "".join(row) + f"{CLR_BLUE}│{CLR_RESET}")
    print(f"{CLR_BLUE}{border}{CLR_RESET}")


# --- Test Cases & Simulation Scenarios ---

def scenario_1_layout_priority_competition():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== SKENARIO 1: Kompetisi Layout Priority pada HStack Sempit ==={CLR_RESET}")
    print(f"{CLR_DIM}Deskripsi: Container berlebar 200pt dengan 2 Text view bersaing.{CLR_RESET}")
    print(f"{CLR_DIM}Text A (Priority 0) vs Text B (Priority 1). Parent mengalokasikan ruang ke Priority 1 duluan.{CLR_RESET}\n")

    # View hierarchy
    txt_low_prio = Text("Low Priority Label Text", layout_priority=0.0)
    txt_high_prio = Text("Critical High Priority Content", layout_priority=1.0)
    root_stack = HStack(spacing=10.0, children=[txt_low_prio, txt_high_prio])

    env = EnvironmentValues(UserInterfaceSizeClass.REGULAR, UserInterfaceSizeClass.REGULAR)
    proposal = ProposedSize.exact(220.0, 40.0)

    # 1. Measure phase
    chosen_size = root_stack.size_that_fits(proposal, env)
    # 2. Placement phase
    root_stack.place(Point(0.0, 0.0), chosen_size)

    dump_layout_tree(root_stack)
    print("\nVisualisasi Wireframe ASCII:")
    render_ascii_wireframe(root_stack, canvas_width=60, canvas_height=6)


def scenario_2_adaptive_size_classes():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== SKENARIO 2: Adaptasi Size Class (Compact vs Regular) ==={CLR_RESET}")
    print(f"{CLR_DIM}Deskripsi: Viewport berubah dari iPhone Portrait (Compact) ke iPad Full (Regular).{CLR_RESET}\n")

    compact_tree = HStack(spacing=5.0, children=[
        FrameModifier(Text("C-Icon"), width=30.0, height=20.0),
        Text("Stacked Compact View Summary")
    ])

    regular_tree = HStack(spacing=20.0, children=[
        FrameModifier(Text("R-Sidebar"), width=120.0, height=40.0),
        Text("Detailed Primary Content Layout Engine Data"),
        Spacer(),
        FrameModifier(Text("Badge"), width=40.0, height=20.0)
    ])

    adaptive_root = AdaptiveContainer(compact_view=compact_tree, regular_view=regular_tree)

    # Pass A: Compact Mode
    print(f"{CLR_YELLOW}--- Subpass A: iPhone Portrait (Compact Width) ---{CLR_RESET}")
    env_compact = EnvironmentValues(UserInterfaceSizeClass.COMPACT, UserInterfaceSizeClass.REGULAR)
    prop_compact = ProposedSize.exact(280.0, 30.0)
    size_a = adaptive_root.size_that_fits(prop_compact, env_compact)
    adaptive_root.place(Point(0.0, 0.0), size_a)
    dump_layout_tree(adaptive_root)
    render_ascii_wireframe(adaptive_root, canvas_width=50, canvas_height=5)

    # Pass B: Regular Mode
    print(f"\n{CLR_GREEN}--- Subpass B: iPad Landscape (Regular Width) ---{CLR_RESET}")
    env_regular = EnvironmentValues(UserInterfaceSizeClass.REGULAR, UserInterfaceSizeClass.REGULAR)
    prop_regular = ProposedSize.exact(650.0, 50.0)
    size_b = adaptive_root.size_that_fits(prop_regular, env_regular)
    adaptive_root.place(Point(0.0, 0.0), size_b)
    dump_layout_tree(adaptive_root)
    render_ascii_wireframe(adaptive_root, canvas_width=70, canvas_height=7)


def benchmark_engine_negotiation():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== BENCHMARK: Komputasi Layout Engine Pass (Stress Test) ==={CLR_RESET}")
    print(f"{CLR_DIM}Mengukur waktu kalkulasi recursive negotiation untuk 10,000 passes...{CLR_RESET}")

    leafs = [FrameModifier(Text(f"T_{i}"), width=20.0 + (i % 5) * 5.0, height=15.0) for i in range(12)]
    nested = HStack(spacing=4.0, children=leafs)
    env = EnvironmentValues(UserInterfaceSizeClass.REGULAR, UserInterfaceSizeClass.REGULAR)
    proposal = ProposedSize.exact(400.0, 100.0)

    start = time.perf_counter()
    iterations = 10_000
    for _ in range(iterations):
        sz = nested.size_that_fits(proposal, env)
        nested.place(Point(0.0, 0.0), sz)
    end = time.perf_counter()

    elapsed = end - start
    rate = iterations / elapsed
    print(f"Hasil: {CLR_GREEN}{iterations:,}{CLR_RESET} pass diselesaikan dalam {CLR_YELLOW}{elapsed:.4f} detik{CLR_RESET}")
    print(f"Throughput Engine: {CLR_BOLD}{rate:,.2f} layout frames/detik{CLR_RESET}\n")


def main():
    print(f"{CLR_BOLD}SwiftUI Deep Dive: Layout Engine & Adaptive System Engine Simulator{CLR_RESET}")
    print(f"{CLR_DIM}Standard Library Core Mechanics Emulation - Python 3 Runtime{CLR_RESET}")
    print("=" * 70)

    scenario_1_layout_priority_competition()
    scenario_2_adaptive_size_classes()
    benchmark_engine_negotiation()

    print(f"{CLR_GREEN}✔ Lab Berhasil: Semua fase layout SwiftUI (Propose -> Size -> Place) berhasil dimodelkan.{CLR_RESET}")


if __name__ == "__main__":
    main()