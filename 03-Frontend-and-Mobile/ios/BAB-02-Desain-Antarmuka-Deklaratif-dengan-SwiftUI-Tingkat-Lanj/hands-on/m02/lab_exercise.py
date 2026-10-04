#!/usr/bin/env python3
"""
Lab Hands-on: Desain Antarmuka Deklaratif dengan SwiftUI Tingkat Lanjut
Topik: Declarative UI Engine, AttributeGraph, State Reconciliation, & 3-Pass Layout Protocol
Kategori: 03-Frontend-and-Mobile / Bab 02 - Modul 02 Deep Dive

Skrip ini memodelkan arsitektur internal runtime SwiftUI:
1. Declarative View Tree & View Modifier Pipeline (.padding, .frame).
2. Reactive State & Dependency Tracking (@State, Invalidation Graph).
3. SwiftUI 3-Pass Layout Engine (Proposal -> Negotiation -> Frame Placement).
4. Structural Identity Reconciliation (AttributeGraph Diffing).
"""

from __future__ import annotations
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Callable

# ============================================================================
# ANSI Color Palette untuk Output Terminal Informatif
# ============================================================================
class Style:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    RED     = "\033[31m"
    BG_DARK = "\033[48;5;236m"

# ============================================================================
# Modul 1: Layout Primitives & Geometri (SwiftUI Layout Protocol)
# ============================================================================
@dataclass(frozen=True)
class ProposedSize:
    """Representasi ukuran yang diajukan oleh parent ke child."""
    width: Optional[float]
    height: Optional[float]

    @property
    def is_unspecified(self) -> bool:
        return self.width is None and self.height is None

@dataclass(frozen=True)
class Size:
    width: float
    height: float

@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

# ============================================================================
# Modul 2: Reactive State System (@State & Invalidation Tracker)
# ============================================================================
class State:
    """
    Simulasi properti @State SwiftUI.
    Menyimpan nilai independen dan memicu invalidasi graf ketika bermutasi.
    """
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._owner_graph: Optional[AttributeGraph] = None
        self._node_id: Optional[str] = None

    def bind(self, graph: AttributeGraph, node_id: str):
        self._owner_graph = graph
        self._node_id = node_id

    @property
    def value(self) -> Any:
        return self._value

    @value.setter
    def value(self, new_val: Any):
        if self._value != new_val:
            self._value = new_val
            if self._owner_graph and self._node_id:
                # Trigger re-evaluation pada sub-tree terkait
                self._owner_graph.mark_dirty(self._node_id)

# ============================================================================
# Modul 3: Declarative View Hierarchy & Modifier Chains
# ============================================================================
class View:
    """Base protocol untuk seluruh elemen UI deklaratif."""
    def __init__(self):
        self.node_id: str = f"{self.__class__.__name__}_{id(self)}"

    def body(self) -> Optional[View]:
        """Secara default leaf node tidak memiliki body."""
        return None

    def size_that_fits(self, proposal: ProposedSize) -> Size:
        """Kompensasi ukuran berdasarkan proposal dari parent (SwiftUI Pass 1-2)."""
        b = self.body()
        if b:
            return b.size_that_fits(proposal)
        return Size(width=0.0, height=0.0)

    # Modifier Chain Pipeline
    def padding(self, amount: float = 8.0) -> View:
        return PaddingModifier(content=self, amount=amount)

    def frame(self, width: Optional[float] = None, height: Optional[float] = None) -> View:
        return FrameModifier(content=self, width=width, height=height)

class PaddingModifier(View):
    """View Modifier yang menyisipkan ruang luar di sekitar view target."""
    def __init__(self, content: View, amount: float):
        super().__init__()
        self.content = content
        self.amount = amount

    def size_that_fits(self, proposal: ProposedSize) -> Size:
        padding_2x = self.amount * 2.0
        reduced_prop = ProposedSize(
            width=max(0.0, proposal.width - padding_2x) if proposal.width else None,
            height=max(0.0, proposal.height - padding_2x) if proposal.height else None
        )
        child_size = self.content.size_that_fits(reduced_prop)
        return Size(child_size.width + padding_2x, child_size.height + padding_2x)

class FrameModifier(View):
    """View Modifier yang memaksakan ukuran tertentu jika ditentukan."""
    def __init__(self, content: View, width: Optional[float] = None, height: Optional[float] = None):
        super().__init__()
        self.content = content
        self.explicit_w = width
        self.explicit_h = height

    def size_that_fits(self, proposal: ProposedSize) -> Size:
        child_prop = ProposedSize(
            width=self.explicit_w if self.explicit_w is not None else proposal.width,
            height=self.explicit_h if self.explicit_h is not None else proposal.height
        )
        child_size = self.content.size_that_fits(child_prop)
        return Size(
            width=self.explicit_w if self.explicit_w is not None else child_size.width,
            height=self.explicit_h if self.explicit_h is not None else child_size.height
        )

# ============================================================================
# Modul 4: Concrete Leaf & Container Views
# ============================================================================
class Text(View):
    """Leaf node deklaratif untuk merender teks dan menghitung bounding box."""
    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def size_that_fits(self, proposal: ProposedSize) -> Size:
        # Simulasi teks monospace: lebar = panjang karakter, tinggi = 1 unit
        text_len = float(len(self.text))
        if proposal.width is not None and proposal.width < text_len:
            # Simulasi truncation jika proposal terlalu sempit
            return Size(width=proposal.width, height=1.0)
        return Size(width=text_len, height=1.0)

class VStack(View):
    """Container layout vertikal: menghitung layout fleksibel untuk anak-anaknya."""
    def __init__(self, children: List[View], spacing: float = 2.0):
        super().__init__()
        self.children = children
        self.spacing = spacing

    def size_that_fits(self, proposal: ProposedSize) -> Size:
        total_height = 0.0
        max_width = 0.0
        count = len(self.children)

        for idx, child in enumerate(self.children):
            c_size = child.size_that_fits(proposal)
            total_height += c_size.height
            if c_size.width > max_width:
                max_width = c_size.width
            if idx < count - 1:
                total_height += self.spacing

        return Size(width=max_width, height=total_height)

class HStack(View):
    """Container layout horizontal: membagi ruang secara adil pada child nodes."""
    def __init__(self, children: List[View], spacing: float = 4.0):
        super().__init__()
        self.children = children
        self.spacing = spacing

    def size_that_fits(self, proposal: ProposedSize) -> Size:
        total_width = 0.0
        max_height = 0.0
        count = len(self.children)

        # Simplifikasi proposal pembagian rata
        child_prop_w = (proposal.width - (self.spacing * (count - 1))) / count if proposal.width else None
        child_prop = ProposedSize(width=child_prop_w, height=proposal.height)

        for idx, child in enumerate(self.children):
            c_size = child.size_that_fits(child_prop)
            total_width += c_size.width
            if c_size.height > max_height:
                max_height = c_size.height
            if idx < count - 1:
                total_width += self.spacing

        return Size(width=total_width, height=max_height)

# ============================================================================
# Modul 5: AttributeGraph Engine (Reconciliation & Layout Solver)
# ============================================================================
@dataclass
class RenderedFrame:
    node_id: str
    view_type: str
    rect: Rect
    content_repr: str
    was_recalculated: bool

class AttributeGraph:
    """
    Simulasi runtime backend SwiftUI (AttributeGraph AG::Graph).
    Menangani pelacakan dependensi, rekonsiliasi graf, dan eksekusi layout tree.
    """
    def __init__(self):
        self._dirty_nodes: set[str] = set()
        self._previous_frames: Dict[str, RenderedFrame] = {}

    def mark_dirty(self, node_id: str):
        self._dirty_nodes.add(node_id)

    def layout_tree(self, root: View, window_rect: Rect) -> List[RenderedFrame]:
        """
        Menjalankan layout 3 langkah SwiftUI:
        1. Propose Size (Window/Parent -> View)
        2. Size That Fits (View mengembalikan respons dimensi)
        3. Place Child (Penetapan koordinat absolut)
        """
        frames: List[RenderedFrame] = []
        is_tree_invalidated = len(self._dirty_nodes) > 0 or len(self._previous_frames) == 0

        def traverse(node: View, origin_x: float, origin_y: float, proposed: ProposedSize):
            computed_size = node.size_that_fits(proposed)
            node_rect = Rect(origin_x, origin_y, computed_size.width, computed_size.height)
            
            # Hitung apakah node direkonstruksi ulang
            recomputed = is_tree_invalidated or (node.node_id in self._dirty_nodes)
            
            # Resolve konten deskriptif
            repr_str = ""
            if isinstance(node, Text):
                repr_str = f"\"{node.text}\""
            elif isinstance(node, (HStack, VStack)):
                repr_str = f"children=[{len(node.children)}]"
            elif isinstance(node, PaddingModifier):
                repr_str = f"pad={node.amount}"
            elif isinstance(node, FrameModifier):
                repr_str = f"w={node.explicit_w},h={node.explicit_h}"

            frame_entry = RenderedFrame(
                node_id=node.node_id,
                view_type=node.__class__.__name__,
                rect=node_rect,
                content_repr=repr_str,
                was_recalculated=recomputed
            )
            frames.append(frame_entry)

            # Traverse child hierarchies
            if isinstance(node, PaddingModifier):
                inner_x = origin_x + node.amount
                inner_y = origin_y + node.amount
                traverse(node.content, inner_x, inner_y, proposed)
                
            elif isinstance(node, FrameModifier):
                traverse(node.content, origin_x, origin_y, proposed)

            elif isinstance(node, VStack):
                curr_y = origin_y
                for child in node.children:
                    traverse(child, origin_x, curr_y, proposed)
                    child_sz = child.size_that_fits(proposed)
                    curr_y += child_sz.height + node.spacing

            elif isinstance(node, HStack):
                curr_x = origin_x
                child_w_prop = (proposed.width - (node.spacing * (len(node.children) - 1))) / len(node.children) if proposed.width else None
                h_prop = ProposedSize(width=child_w_prop, height=proposed.height)
                for child in node.children:
                    traverse(child, curr_x, origin_y, h_prop)
                    child_sz = child.size_that_fits(h_prop)
                    curr_x += child_sz.width + node.spacing
                    
            elif node.body() is not None:
                traverse(node.body(), origin_x, origin_y, proposed)

        # Mulai kalkulasi layout
        traverse(root, window_rect.x, window_rect.y, ProposedSize(window_rect.width, window_rect.height))
        
        # Simpan state snapshot
        self._dirty_nodes.clear()
        self._previous_frames = {f.node_id: f for f in frames}
        return frames

# ============================================================================
# Modul 6: Mock App SwiftUI Komposit
# ============================================================================
class OrderSummaryView(View):
    """
    View deklaratif tingkat lanjut dengan state binding dan modifier composition.
    """
    def __init__(self, graph: AttributeGraph):
        super().__init__()
        # Inisialisasi reactive state
        self.item_count = State(1)
        self.item_count.bind(graph, self.node_id)
        self.unit_price = 120.0

    def body(self) -> View:
        subtotal = self.item_count.value * self.unit_price
        
        # Hierarchy:
        # VStack
        #  ├── HStack (Header Title & Badge)
        #  ├── HStack (Item Name & Dynamic Subtotal)
        #  └── Text (Footer Status)
        return VStack([
            HStack([
                Text("ORDER #104"),
                Text("[EXPRESS]").padding(2.0)
            ], spacing=3.0),
            HStack([
                Text(f"Qty: {self.item_count.value}"),
                Text(f"Subtotal: ${subtotal:.2f}")
            ], spacing=6.0),
            Text("Tax Included (Free Priority Shipping)")
                .padding(4.0)
                .frame(width=45.0)
        ], spacing=1.0).padding(6.0)

# ============================================================================
# Modul 7: Driver Eksekusi Lab Visual
# ============================================================================
def render_terminal_dashboard(cycle_name: str, frames: List[RenderedFrame], total_elapsed_ms: float):
    print(f"\n{Style.BG_DARK}{Style.BOLD} {cycle_name.upper()} {Style.RESET}")
    print(f"{Style.DIM}Reconciliation & Layout Compute Time: {total_elapsed_ms:.4f} ms{Style.RESET}")
    print(f"{'-'*75}")
    print(f"{'Node Identitas':<32} | {'Tipe Node':<16} | {'Computed Frame (x, y, w, h)':<22}")
    print(f"{'-'*75}")
    
    for f in frames:
        status_color = Style.GREEN if f.was_recalculated else Style.DIM
        diff_tag = "[RE-RENDER]" if f.was_recalculated else "[CACHED]   "
        frame_box = f"({f.rect.x:.1f}, {f.rect.y:.1f}, {f.rect.w:.1f}, {f.rect.h:.1f})"
        
        # Alias label ringkas
        label = f.content_repr if f.content_repr else f.view_type
        print(f"{status_color}{diff_tag}{Style.RESET} {label:<20} | {Style.CYAN}{f.view_type:<16}{Style.RESET} | {Style.YELLOW}{frame_box:<22}{Style.RESET}")

def main():
    print(f"{Style.BOLD}{Style.MAGENTA}======================================================================{Style.RESET}")
    print(f"{Style.BOLD}{Style.MAGENTA}  SWIFTUI ADVANCED ENGINE SIMULATOR (AttributeGraph & Layout Protocol) {Style.RESET}")
    print(f"{Style.BOLD}{Style.MAGENTA}======================================================================{Style.RESET}")

    graph = AttributeGraph()
    app_view = OrderSummaryView(graph)
    window = Rect(x=0.0, y=0.0, width=80.0, height=24.0)

    # ------------------------------------------------------------------------
    # Skenario 1: Initial Render Pipeline
    # ------------------------------------------------------------------------
    print(f"\n{Style.BOLD}[1] Triggering Initial Render Pass...{Style.RESET}")
    t0 = time.perf_counter()
    frames_cycle_1 = graph.layout_tree(app_view, window)
    t1 = time.perf_counter()
    render_terminal_dashboard("Render Pass 1: Tree Construction", frames_cycle_1, (t1 - t0) * 1000)

    time.sleep(0.4)

    # ------------------------------------------------------------------------
    # Skenario 2: State Mutation (@State Value Changed -> Invalidation)
    # ------------------------------------------------------------------------
    print(f"\n{Style.BOLD}[2] Mutating State: order.item_count = 3 (Reactive Trigger)...{Style.RESET}")
    app_view.item_count.value = 3  # Akan memicu graph.mark_dirty() secara otomatis

    t2 = time.perf_counter()
    frames_cycle_2 = graph.layout_tree(app_view, window)
    t3 = time.perf_counter()
    render_terminal_dashboard("Render Pass 2: Invalidation Diffing & Relayout", frames_cycle_2, (t3 - t2) * 1000)

    time.sleep(0.4)

    # ------------------------------------------------------------------------
    # Skenario 3: Layout Shift Verification (Larger State Expansion)
    # ------------------------------------------------------------------------
    print(f"\n{Style.BOLD}[3] Mutating State: order.item_count = 25 (Layout Shift / Bounding Box Check)...{Style.RESET}")
    app_view.item_count.value = 25

    t4 = time.perf_counter()
    frames_cycle_3 = graph.layout_tree(app_view, window)
    t5 = time.perf_counter()
    render_terminal_dashboard("Render Pass 3: Geometry Expansion Pass", frames_cycle_3, (t5 - t4) * 1000)

    # ------------------------------------------------------------------------
    # Ringkasan Teoretis Arsitektur
    # ------------------------------------------------------------------------
    print(f"\n{Style.CYAN}{Style.BOLD}--- TECHNICAL SUMMARY: SWIFTUI RUNTIME DYNAMICS ---{Style.RESET}")
    print(f"1. {Style.BOLD}AttributeGraph Diffing:{Style.RESET} SwiftUI mempertahankan Identity stabil dari struct View.")
    print(f"2. {Style.BOLD}3-Pass Layout Protocol:{Style.RESET} Ukuran akhir adalah hasil negosiasi bottom-up dan top-down.")
    print(f"3. {Style.BOLD}Modifier Wrapping:{Style.RESET} Modifier tidak memodifikasi objek, melainkan membungkusnya dalam node baru.")
    print(f"{Style.GREEN}Simulasi Selesai dengan Sukses.{Style.RESET}\n")

if __name__ == "__main__":
    main()