#!/usr/bin/env python3
"""
Lab Hands-on: Visual Formatting Model, Box Dynamics, dan Paint Profiling
Kategori: 03-Frontend-and-Mobile | Bab 02: CSS Deep Dive

Simulasi komprehensif Visual Formatting Model (CSS Box Model, Vertical Margin Collapsing,
Stacking Context Ordering) dan Lifecycle Rendering Engine (Reflow, Repaint, Composite Profiler).
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict
import time
import math

# --- ANSI Terminal Styling ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_BG_DARK = "\033[48;5;236m"


class DisplayType(Enum):
    BLOCK = auto()
    INLINE = auto()
    NONE = auto()


class PositionType(Enum):
    STATIC = auto()
    RELATIVE = auto()
    ABSOLUTE = auto()


class PipelineStage(Enum):
    STYLE_RECALC = "Recalculate Style"
    LAYOUT_REFLOW = "Layout / Reflow"
    PAINT = "Paint (Rasterization)"
    COMPOSITE = "Compositing Layers"


@dataclass
class EdgeInsets:
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    @property
    def horizontal(self) -> float:
        return self.left + self.right

    @property
    def vertical(self) -> float:
        return self.top + self.bottom


@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    def union(self, other: "Rect") -> "Rect":
        """Menghitung bounding box penyatuan untuk dirty rect invalidation."""
        if self.width == 0 and self.height == 0:
            return other
        if other.width == 0 and other.height == 0:
            return self
        min_x = min(self.x, other.x)
        min_y = min(self.y, other.y)
        max_x = max(self.x + self.width, other.x + other.width)
        max_y = max(self.y + self.height, other.y + other.height)
        return Rect(min_x, min_y, max_x - min_x, max_y - min_y)


@dataclass
class ComputedBox:
    content: Rect = field(default_factory=Rect)
    padding: EdgeInsets = field(default_factory=EdgeInsets)
    border: EdgeInsets = field(default_factory=EdgeInsets)
    margin: EdgeInsets = field(default_factory=EdgeInsets)

    @property
    def border_box(self) -> Rect:
        return Rect(
            x=self.content.x - self.padding.left - self.border.left,
            y=self.content.y - self.padding.top - self.border.top,
            width=self.content.width + self.padding.horizontal + self.border.horizontal,
            height=self.content.height + self.padding.vertical + self.border.vertical,
        )

    @property
    def margin_box(self) -> Rect:
        bb = self.border_box
        return Rect(
            x=bb.x - self.margin.left,
            y=bb.y - self.margin.top,
            width=bb.width + self.margin.horizontal,
            height=bb.height + self.margin.vertical,
        )


class RenderNode:
    """Representasi elemen dalam Layout Tree."""

    def __init__(
        self,
        node_id: str,
        display: DisplayType = DisplayType.BLOCK,
        position: PositionType = PositionType.STATIC,
        width: Optional[float] = None,
        height: float = 0.0,
        margin: Optional[EdgeInsets] = None,
        padding: Optional[EdgeInsets] = None,
        border: Optional[EdgeInsets] = None,
        z_index: int = 0,
        opacity: float = 1.0,
        bg_color: str = "#FFFFFF",
    ):
        self.node_id = node_id
        self.display = display
        self.position = position
        self.declared_width = width
        self.declared_height = height
        self.margin = margin or EdgeInsets()
        self.padding = padding or EdgeInsets()
        self.border = border or EdgeInsets()
        self.z_index = z_index
        self.opacity = opacity
        self.bg_color = bg_color

        self.children: List["RenderNode"] = []
        self.parent: Optional["RenderNode"] = None
        self.box = ComputedBox()
        self.is_layer: bool = False  # True jika membentuk composited layer independen

    def add_child(self, child: "RenderNode") -> None:
        child.parent = self
        self.children.append(child)

    def creates_stacking_context(self) -> bool:
        """Kriteria pembentukan Stacking Context sesuai spesifikasi CSS 2.1 & CSS3."""
        if self.position in (PositionType.ABSOLUTE, PositionType.RELATIVE) and self.z_index != 0:
            return True
        if self.opacity < 1.0 or self.is_layer:
            return True
        return False


class VisualFormattingModel:
    """
    Mesin kalkulasi geometri CSS:
    Mengimplementasikan normal flow BFC (Block Formatting Context) dan Vertical Margin Collapsing.
    """

    @staticmethod
    def collapse_margins(margin_a: float, margin_b: float) -> float:
        """
        Algoritma Margin Collapsing Standar W3C:
        - Jika keduanya positif: max(A, B)
        - Jika keduanya negatif: -max(abs(A), abs(B))
        - Jika berbeda tanda: A + B
        """
        if margin_a >= 0 and margin_b >= 0:
            return max(margin_a, margin_b)
        elif margin_a < 0 and margin_b < 0:
            return -max(abs(margin_a), abs(margin_b))
        else:
            return margin_a + margin_b

    def layout(self, root: RenderNode, viewport_width: float) -> None:
        """Menjalankan full-pass layout traversal."""
        root.box.margin = root.margin
        root.box.padding = root.padding
        root.box.border = root.border
        
        # Resolusi lebar Root
        c_width = root.declared_width if root.declared_width is not None else viewport_width
        root.box.content = Rect(
            x=root.margin.left + root.border.left + root.padding.left,
            y=root.margin.top + root.border.top + root.padding.top,
            width=c_width - (root.margin.horizontal + root.border.horizontal + root.padding.horizontal),
            height=root.declared_height,
        )

        self._layout_block_children(root)

    def _layout_block_children(self, parent: RenderNode) -> None:
        cursor_y = parent.box.content.y
        prev_bottom_margin = 0.0
        total_content_height = 0.0

        for idx, child in enumerate(parent.children):
            if child.display == DisplayType.NONE:
                continue

            child.box.padding = child.padding
            child.box.border = child.border
            child.box.margin = child.margin

            # Kalkulasi Lebar Konten
            avail_width = parent.box.content.width
            if child.declared_width is not None:
                content_w = child.declared_width
            else:
                # Blok mengisi sisa lebar kontainer secara default
                content_w = (
                    avail_width
                    - child.margin.horizontal
                    - child.border.horizontal
                    - child.padding.horizontal
                )

            # Eksekusi Margin Collapsing Vertikal antar Sibling
            if idx == 0:
                collapsed_margin_top = child.margin.top
            else:
                collapsed_margin_top = self.collapse_margins(prev_bottom_margin, child.margin.top)

            pos_x = (
                parent.box.content.x
                + child.margin.left
                + child.border.left
                + child.padding.left
            )
            pos_y = (
                cursor_y
                + collapsed_margin_top
                + child.border.top
                + child.padding.top
            )

            child.box.content = Rect(
                x=pos_x,
                y=pos_y,
                width=max(0.0, content_w),
                height=child.declared_height,
            )

            # Rekursif layout turunan
            if child.children:
                self._layout_block_children(child)
                # Jika height tidak ditentukan, shrink-wrap ke konten anak
                if child.declared_height == 0.0:
                    child.box.content.height = child.children[-1].box.border_box.y + \
                        child.children[-1].box.border_box.height - child.box.content.y

            border_box = child.box.border_box
            cursor_y = border_box.y + border_box.height
            prev_bottom_margin = child.margin.bottom
            total_content_height = (cursor_y + child.margin.bottom) - parent.box.content.y

        if parent.declared_height == 0.0 and total_content_height > 0:
            parent.box.content.height = total_content_height


class StackingContextEngine:
    """Mengimplementasikan spesifikasi urutan rendering CSS 2.1 Lampiran E."""

    @classmethod
    def compile_paint_order(cls, root: RenderNode) -> List[RenderNode]:
        order: List[RenderNode] = []

        def traverse_stack(node: RenderNode) -> None:
            # Pengelompokan anak berdasarkan z-index
            neg_z: List[RenderNode] = []
            normal_flow: List[RenderNode] = []
            pos_z: List[RenderNode] = []

            for ch in node.children:
                if ch.creates_stacking_context():
                    if ch.z_index < 0:
                        neg_z.append(ch)
                    else:
                        pos_z.append(ch)
                else:
                    normal_flow.append(ch)

            neg_z.sort(key=lambda n: n.z_index)
            pos_z.sort(key=lambda n: n.z_index)

            # 1. Stacking contexts dengan z-index negatif
            for child in neg_z:
                order.append(child)
                traverse_stack(child)

            # 2. Node saat ini (Background & Borders)
            order.append(node)

            # 3. Normal in-flow, non-positioned descendant blocks
            for child in normal_flow:
                traverse_stack(child)

            # 4. Stacking contexts dengan z-index positif (>= 0)
            for child in pos_z:
                order.append(child)
                traverse_stack(child)

        traverse_stack(root)
        return order


class RenderPipelineProfiler:
    """
    Simulasi pipeline performa browser modern:
    Menganalisis biaya CPU/GPU dari DOM Mutation (Reflow vs Repaint vs Composite-only).
    """

    def __init__(self, root: RenderNode, viewport_w: float = 1024.0):
        self.root = root
        self.viewport_w = viewport_w
        self.layout_engine = VisualFormattingModel()

    def profile_mutation(self, target_id: str, property_name: str, new_value: any) -> Dict[str, any]:
        target = self._find_node(self.root, target_id)
        if not target:
            raise ValueError(f"Node '{target_id}' tidak ditemukan dalam render tree.")

        # Menentukan invalidation scope berdasarkan spesifikasi CSS triggers
        stages_triggered: List[PipelineStage] = [PipelineStage.STYLE_RECALC]
        if property_name in ("width", "height", "margin", "padding", "display"):
            stages_triggered.extend([PipelineStage.LAYOUT_REFLOW, PipelineStage.PAINT, PipelineStage.COMPOSITE])
        elif property_name in ("background-color", "color", "border-color", "box-shadow"):
            stages_triggered.extend([PipelineStage.PAINT, PipelineStage.COMPOSITE])
        elif property_name in ("opacity", "transform"):
            stages_triggered.append(PipelineStage.COMPOSITE)
        else:
            stages_triggered.extend([PipelineStage.LAYOUT_REFLOW, PipelineStage.PAINT, PipelineStage.COMPOSITE])

        # Benchmark eksekusi simulasi
        durations: Dict[PipelineStage, float] = {}
        old_border_box = target.box.border_box

        # 1. Style Recalculation
        t0 = time.perf_counter_ns()
        self._apply_style_change(target, property_name, new_value)
        # Simulasi overhead style matching
        math.factorial(2500)
        durations[PipelineStage.STYLE_RECALC] = (time.perf_counter_ns() - t0) / 1_000_000.0

        # 2. Layout / Reflow (jika dipicu)
        if PipelineStage.LAYOUT_REFLOW in stages_triggered:
            t0 = time.perf_counter_ns()
            self.layout_engine.layout(self.root, self.viewport_w)
            durations[PipelineStage.LAYOUT_REFLOW] = (time.perf_counter_ns() - t0) / 1_000_000.0

        # 3. Paint (Rasterization)
        if PipelineStage.PAINT in stages_triggered:
            t0 = time.perf_counter_ns()
            # Simulasi rasterisasi dirty rect
            math.factorial(4000)
            durations[PipelineStage.PAINT] = (time.perf_counter_ns() - t0) / 1_000_000.0

        # 4. Composite Layers
        if PipelineStage.COMPOSITE in stages_triggered:
            t0 = time.perf_counter_ns()
            StackingContextEngine.compile_paint_order(self.root)
            durations[PipelineStage.COMPOSITE] = (time.perf_counter_ns() - t0) / 1_000_000.0

        new_border_box = target.box.border_box
        dirty_damage_rect = old_border_box.union(new_border_box)

        total_frame_time = sum(durations.values())
        fps_budget = 16.67  # 60 FPS target budget (ms)

        return {
            "target": target_id,
            "property": property_name,
            "new_value": str(new_value),
            "stages": stages_triggered,
            "durations_ms": durations,
            "total_ms": total_frame_time,
            "budget_consumed_pct": (total_frame_time / fps_budget) * 100.0,
            "dirty_rect": dirty_damage_rect,
        }

    def _apply_style_change(self, target: RenderNode, prop: str, val: any) -> None:
        if prop == "width":
            target.declared_width = float(val)
        elif prop == "height":
            target.declared_height = float(val)
        elif prop == "background-color":
            target.bg_color = str(val)
        elif prop == "opacity":
            target.opacity = float(val)
        elif prop == "margin":
            target.margin = val

    def _find_node(self, current: RenderNode, node_id: str) -> Optional[RenderNode]:
        if current.node_id == node_id:
            return current
        for ch in current.children:
            found = self._find_node(ch, node_id)
            if found:
                return found
        return None


# --- Demonstrasi & CLI Profiler Output ---

def print_box_visualizer(node: RenderNode) -> None:
    bb = node.box.border_box
    cb = node.box.content
    m = node.box.margin
    p = node.box.padding
    b = node.box.border

    print(f"\n{CLR_BOLD}{CLR_CYAN}── Box Metrics: [{node.node_id}] ──{CLR_RESET}")
    print(f"  {CLR_YELLOW}Margin Box  {CLR_RESET}: Rect(x={node.box.margin_box.x:.1f}, y={node.box.margin_box.y:.1f}, w={node.box.margin_box.width:.1f}, h={node.box.margin_box.height:.1f})")
    print(f"  {CLR_MAGENTA}Border Box  {CLR_RESET}: Rect(x={bb.x:.1f}, y={bb.y:.1f}, w={bb.width:.1f}, h={bb.height:.1f})")
    print(f"  {CLR_GREEN}Content Box {CLR_RESET}: Rect(x={cb.x:.1f}, y={cb.y:.1f}, w={cb.width:.1f}, h={cb.height:.1f})")
    print(f"  {CLR_BLUE}Offsets     {CLR_RESET}: M({m.top:.0f},{m.right:.0f},{m.bottom:.0f},{m.left:.0f}) | B({b.top:.0f}) | P({p.top:.0f})")


def print_profile_result(res: Dict[str, any]) -> None:
    print(f"\n{CLR_BOLD}>> Mutation Profiler Report: [Mutation on '{res['target']}' => {res['property']}: {res['new_value']}]{CLR_RESET}")
    print(f"   Dirty Invalidation Rect : [x:{res['dirty_rect'].x:.1f}, y:{res['dirty_rect'].y:.1f}, w:{res['dirty_rect'].width:.1f}, h:{res['dirty_rect'].height:.1f}]")
    print("   Pipeline Execution Breakdown:")
    for stage, dur in res["durations_ms"].items():
        color = CLR_GREEN if stage == PipelineStage.COMPOSITE else (CLR_YELLOW if stage == PipelineStage.PAINT else CLR_RED)
        print(f"    - {color}{stage.value:<25}{CLR_RESET}: {dur:6.3f} ms")
    
    total = res['total_ms']
    pct = res['budget_consumed_pct']
    status_clr = CLR_GREEN if pct < 50 else (CLR_YELLOW if pct <= 100 else CLR_RED)
    print(f"   Frame Budget (16.67ms)  : {status_clr}{total:6.3f} ms ({pct:.1f}% consumed){CLR_RESET}")


def main() -> None:
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}   Visual Formatting Model, Box Dynamics, & Paint Profiling Lab       {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")

    # 1. Konstruksi Pohon Render (Simulasi DOM + RenderTree)
    root = RenderNode(
        "html_root",
        declared_width=1000.0,
        margin=EdgeInsets(0, 0, 0, 0),
        padding=EdgeInsets(20, 20, 20, 20),
    )

    header = RenderNode(
        "header_hero",
        declared_height=120.0,
        margin=EdgeInsets(top=10, right=0, bottom=40, left=0),  # bottom margin: 40px
        padding=EdgeInsets(10, 10, 10, 10),
        border=EdgeInsets(2, 2, 2, 2),
        bg_color="#1E293B",
    )

    main_content = RenderNode(
        "main_article",
        declared_height=300.0,
        margin=EdgeInsets(top=25, right=0, bottom=30, left=0),  # top margin: 25px -> COLLAPSE dgn 40px => max(40, 25) = 40px
        padding=EdgeInsets(15, 15, 15, 15),
        border=EdgeInsets(1, 1, 1, 1),
        bg_color="#FFFFFF",
    )

    popup_overlay = RenderNode(
        "modal_overlay",
        position=PositionType.ABSOLUTE,
        declared_width=400.0,
        declared_height=200.0,
        z_index=10,
        opacity=0.95,
        bg_color="#000000",
    )
    popup_overlay.is_layer = True

    root.add_child(header)
    root.add_child(main_content)
    root.add_child(popup_overlay)

    # 2. Eksekusi Layout Awal (BFC Pass)
    profiler = RenderPipelineProfiler(root, viewport_w=1000.0)
    profiler.layout_engine.layout(root, 1000.0)

    print(f"\n{CLR_BOLD}[FASE 1] Verifikasi Box Model & Vertical Margin Collapsing{CLR_RESET}")
    print_box_visualizer(header)
    print_box_visualizer(main_content)

    expected_collapse_gap = max(header.margin.bottom, main_content.margin.top)
    actual_gap = main_content.box.border_box.y - (header.box.border_box.y + header.box.border_box.height)
    print(f"\n{CLR_CYAN}Analisis Margin Collapsing Sibling:{CLR_RESET}")
    print(f"  Header Margin-Bottom    : {header.margin.bottom:.1f}px")
    print(f"  Article Margin-Top      : {main_content.margin.top:.1f}px")
    print(f"  Calculated Dynamic Gap  : {actual_gap:.1f}px (Target Spec Max: {expected_collapse_gap:.1f}px)")
    assert math.isclose(actual_gap, expected_collapse_gap), "Kesalahan perhitungan margin collapsing!"

    # 3. Urutan Stacking Context (CSS 2.1 Appendix E)
    print(f"\n{CLR_BOLD}[FASE 2] Visual Stacking Context Compilation (Paint Order){CLR_RESET}")
    paint_order = StackingContextEngine.compile_paint_order(root)
    for idx, node in enumerate(paint_order):
        print(f"  Layer [{idx}] -> {CLR_YELLOW}{node.node_id:<18}{CLR_RESET} (z-index: {node.z_index}, pos: {node.position.name})")

    # 4. Profiling Dynamic Pipeline Triggers
    print(f"\n{CLR_BOLD}[FASE 3] Profiling Pipeline Invalidation (Reflow vs Repaint vs Composite){CLR_RESET}")

    # Skenario A: Mutasi Geometri (Layout Invalidation: Triggers Reflow + Paint + Composite)
    res_reflow = profiler.profile_mutation("main_article", "height", 450.0)
    print_profile_result(res_reflow)

    # Skenario B: Mutasi Visual (Paint Invalidation: Triggers Paint + Composite)
    res_repaint = profiler.profile_mutation("header_hero", "background-color", "#0EA5E9")
    print_profile_result(res_repaint)

    # Skenario C: Mutasi Layer Compositor (Composite Only: Triggers Composite)
    res_composite = profiler.profile_mutation("modal_overlay", "opacity", 0.8)
    print_profile_result(res_composite)

    print(f"\n{CLR_BOLD}{CLR_GREEN}✓ Seluruh pengujian Visual Formatting Model dan Paint Profiling selesai tanpa anomali.{CLR_RESET}\n")


if __name__ == "__main__":
    main()