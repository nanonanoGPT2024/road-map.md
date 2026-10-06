#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Engine Tata Letak & Siklus Hidup SwiftUI Tingkat Lanjut
Topik: BAB-02 Desain Antarmuka Deklaratif dengan SwiftUI Tingkat Lanjut
Fitur Simulasi:
  1. Layout Protocol Engine (Parent Proposes, Child Decides, Parent Places)
  2. Modifiers Chaining & View Hierarchy Graph
  3. Reactive Dependency Tracking (@State, @Binding, Invalidation Re-render)
  4. Interactive ANSI Terminal Visualization
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Callable, Dict, Any

# --- ANSI Formatting Helper ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[100m"

@dataclass
class ProposedViewSize:
    width: Optional[float]
    height: Optional[float]

    def __str__(self):
        w_str = f"{self.width:.1f}" if self.width is not None else "unspecified"
        h_str = f"{self.height:.1f}" if self.height is not None else "unspecified"
        return f"ProposedSize(w: {w_str}, h: {h_str})"

@dataclass
class ViewSize:
    width: float
    height: float

    def __str__(self):
        return f"Size({self.width:.1f}x{self.height:.1f})"

@dataclass
class Point:
    x: float
    y: float

class ViewAlignment(Enum):
    LEADING = auto()
    CENTER = auto()
    TRAILING = auto()
    TOP = auto()
    BOTTOM = auto()

class SwiftUIComponent:
    """Base class untuk setiap View deklaratif SwiftUI."""
    def __init__(self, identifier: str):
        self.identifier = identifier
        self.modifiers: List[str] = []
        self.resolved_size: Optional[ViewSize] = None
        self.resolved_origin: Point = Point(0.0, 0.0)

    def size_that_fits(self, proposal: ProposedViewSize) -> ViewSize:
        raise NotImplementedError

    def place(self, at: Point, proposal: ProposedViewSize):
        self.resolved_origin = at
        self.resolved_size = self.size_that_fits(proposal)

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        mod_info = f" -> [{', '.join(self.modifiers)}]" if self.modifiers else ""
        size_info = f" (bounds: {self.resolved_size} at ({self.resolved_origin.x:.1f}, {self.resolved_origin.y:.1f}))" if self.resolved_size else ""
        return f"{indent}{Color.CYAN}• {self.identifier}{Color.RESET}{mod_info}{Color.YELLOW}{size_info}{Color.RESET}\n"

class Text(SwiftUIComponent):
    def __init__(self, content: str):
        super().__init__(f"Text(\"{content}\")")
        self.content = content
        self.char_width = 8.0
        self.char_height = 16.0

    def size_that_fits(self, proposal: ProposedViewSize) -> ViewSize:
        intrinsic_width = len(self.content) * self.char_width
        intrinsic_height = self.char_height
        
        # Penanganan text wrapping jika proposal.width lebih kecil
        if proposal.width is not None and proposal.width < intrinsic_width:
            chars_per_line = max(1, int(proposal.width // self.char_width))
            lines = (len(self.content) + chars_per_line - 1) // chars_per_line
            actual_w = chars_per_line * self.char_width
            actual_h = lines * self.char_height
            return ViewSize(actual_w, actual_h)
        
        return ViewSize(intrinsic_width, intrinsic_height)

class PaddingModifier(SwiftUIComponent):
    def __init__(self, child: SwiftUIComponent, insets: float = 16.0):
        super().__init__(f"Padding({insets:.0f}pt)")
        self.child = child
        self.insets = insets
        self.modifiers = child.modifiers.copy()

    def size_that_fits(self, proposal: ProposedViewSize) -> ViewSize:
        child_proposal_w = max(0.0, proposal.width - (self.insets * 2)) if proposal.width is not None else None
        child_proposal_h = max(0.0, proposal.height - (self.insets * 2)) if proposal.height is not None else None
        
        child_size = self.child.size_that_fits(ProposedViewSize(child_proposal_w, child_proposal_h))
        return ViewSize(child_size.width + (self.insets * 2), child_size.height + (self.insets * 2))

    def place(self, at: Point, proposal: ProposedViewSize):
        super().place(at, proposal)
        child_origin = Point(at.x + self.insets, at.y + self.insets)
        child_proposal = ProposedViewSize(
            proposal.width - (self.insets * 2) if proposal.width is not None else None,
            proposal.height - (self.insets * 2) if proposal.height is not None else None
        )
        self.child.place(child_origin, child_proposal)

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        node = f"{indent}{Color.MAGENTA}▼ Modifier: Padding({self.insets:.0f}pt){Color.RESET}\n"
        return node + self.child.render_tree(depth + 1)

class FrameModifier(SwiftUIComponent):
    def __init__(self, child: SwiftUIComponent, fixed_w: Optional[float] = None, fixed_h: Optional[float] = None):
        super().__init__(f"Frame(w={fixed_w}, h={fixed_h})")
        self.child = child
        self.fixed_w = fixed_w
        self.fixed_h = fixed_h

    def size_that_fits(self, proposal: ProposedViewSize) -> ViewSize:
        child_w = self.fixed_w if self.fixed_w is not None else proposal.width
        child_h = self.fixed_h if self.fixed_h is not None else proposal.height
        child_size = self.child.size_that_fits(ProposedViewSize(child_w, child_h))
        
        return ViewSize(
            self.fixed_w if self.fixed_w is not None else child_size.width,
            self.fixed_h if self.fixed_h is not None else child_size.height
        )

    def place(self, at: Point, proposal: ProposedViewSize):
        super().place(at, proposal)
        self.child.place(at, ProposedViewSize(self.fixed_w, self.fixed_h))

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        node = f"{indent}{Color.BLUE}▼ Modifier: Frame(w={self.fixed_w}, h={self.fixed_h}){Color.RESET}\n"
        return node + self.child.render_tree(depth + 1)

class VStack(SwiftUIComponent):
    """Simulasi Custom Layout Protocol untuk Stack Vertikal."""
    def __init__(self, children: List[SwiftUIComponent], spacing: float = 8.0, alignment: ViewAlignment = ViewAlignment.CENTER):
        super().__init__(f"VStack(spacing: {spacing:.0f}, alignment: {alignment.name})")
        self.children = children
        self.spacing = spacing
        self.alignment = alignment

    def size_that_fits(self, proposal: ProposedViewSize) -> ViewSize:
        total_height = 0.0
        max_width = 0.0
        
        for i, child in enumerate(self.children):
            c_size = child.size_that_fits(proposal)
            total_height += c_size.height
            if i > 0:
                total_height += self.spacing
            max_width = max(max_width, c_size.width)
            
        return ViewSize(max_width, total_height)

    def place(self, at: Point, proposal: ProposedViewSize):
        super().place(at, proposal)
        current_y = at.y
        stack_width = self.resolved_size.width if self.resolved_size else 0.0
        
        for child in self.children:
            c_size = child.size_that_fits(proposal)
            if self.alignment == ViewAlignment.LEADING:
                c_x = at.x
            elif self.alignment == ViewAlignment.TRAILING:
                c_x = at.x + (stack_width - c_size.width)
            else: # CENTER
                c_x = at.x + (stack_width - c_size.width) / 2.0
            
            child.place(Point(c_x, current_y), ProposedViewSize(c_size.width, c_size.height))
            current_y += c_size.height + self.spacing

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        header = f"{indent}{Color.GREEN}▼ Container: {self.identifier}{Color.RESET}\n"
        children_str = "".join(child.render_tree(depth + 1) for child in self.children)
        return header + children_str

# --- State & Reactive Graph Simulation ---
class StateProperty:
    def __init__(self, initial_value: Any, name: str, on_changed: Optional[Callable[[], None]] = None):
        self._value = initial_value
        self.name = name
        self.on_changed = on_changed

    @property
    def wrapped_value(self) -> Any:
        return self._value

    @wrapped_value.setter
    def wrapped_value(self, new_val: Any):
        if self._value != new_val:
            old_val = self._value
            self._value = new_val
            print(f"{Color.YELLOW}⚡ [State Mutation]{Color.RESET} '{self.name}': {old_val} ➜ {new_val} (Graph Invalidation Triggered)")
            if self.on_changed:
                self.on_changed()

class LayoutSimulator:
    def __init__(self):
        self.screen_width = 390.0   # iPhone 14 / 15 logical width
        self.screen_height = 844.0  # iPhone 14 / 15 logical height
        self.re_render_count = 0

    def run_layout_pass(self, root_view: SwiftUIComponent) -> ViewSize:
        self.re_render_count += 1
        print(f"\n{Color.BOLD}{Color.WHITE}======================================================================{Color.RESET}")
        print(f"{Color.CYAN}🚀 MEMULAI SIKLUS LAYOUT SWIFTUI (Pass #{self.re_render_count}){Color.RESET}")
        print(f"Device Viewport: {Color.BOLD}{self.screen_width:.0f} x {self.screen_height:.0f} pt{Color.RESET}")
        print(f"======================================================================")
        
        # 1. Parent Proposes Size
        root_proposal = ProposedViewSize(self.screen_width, self.screen_height)
        print(f"{Color.BLUE}[Fase 1: Size Proposal]{Color.RESET} Root container diajukan proposal: {root_proposal}")
        
        # 2. Child Decides Size
        final_size = root_view.size_that_fits(root_proposal)
        print(f"{Color.MAGENTA}[Fase 2: Size Negotiation]{Color.RESET} Child memutuskan ukuran aktual: {final_size}")
        
        # 3. Parent Places Child
        root_view.place(Point(0.0, 0.0), root_proposal)
        print(f"{Color.GREEN}[Fase 3: Coordinate Placement]{Color.RESET} Child ditempatkan pada origin: (0.0, 0.0)")
        
        print(f"\n{Color.BOLD}Struktur View Hierarchy Tree:{Color.RESET}")
        print(root_view.render_tree())
        return final_size

def run_interactive_demo():
    simulator = LayoutSimulator()
    
    # State reactive model
    title_state = StateProperty("SwiftUI Advanced Layout", name="viewTitle")
    padding_state = StateProperty(20.0, name="containerPadding")
    
    def build_view() -> SwiftUIComponent:
        header_text = Text(title_state.wrapped_value)
        subtitle_text = Text("Memahami Layout Protocol 3 Tahap")
        author_text = Text("Kompilasi Deklaratif iOS")
        
        # Modifiers chaining
        styled_header = FrameModifier(header_text, fixed_w=280.0, fixed_h=30.0)
        
        body_stack = VStack(
            children=[styled_header, subtitle_text, author_text],
            spacing=12.0,
            alignment=ViewAlignment.CENTER
        )
        padded_stack = PaddingModifier(body_stack, insets=padding_state.wrapped_value)
        return padded_stack

    root_view = build_view()
    simulator.run_layout_pass(root_view)

    print(f"\n{Color.BOLD}{Color.YELLOW}--- Uji Reaktivitas State & Invalidation Graph ---{Color.RESET}")
    print("Mengubah nilai @State secara dinamis...")
    time.sleep(0.3)
    
    # Trigger mutation 1
    title_state.wrapped_value = "Advanced Declarative UI (Updated)"
    updated_view = build_view()
    simulator.run_layout_pass(updated_view)
    
    # Trigger mutation 2
    time.sleep(0.3)
    padding_state.wrapped_value = 32.0
    final_view = build_view()
    simulator.run_layout_pass(final_view)
    
    print(f"\n{Color.BOLD}{Color.GREEN}✔ Simulasi Engine SwiftUI Selesai tanpa Syntax Error! (Total Pass: {simulator.re_render_count}){Color.RESET}\n")

if __name__ == "__main__":
    run_interactive_demo()
