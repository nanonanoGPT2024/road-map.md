#!/usr/bin/env python3
"""
Lab Exercise: Declarative UI Engineering & Advanced Rendering Pipeline
Demonstrating Flutter's Three-Tree Architecture (Widget, Element, RenderObject)
and the Frame Pipeline (Reconciliation, Layout, Paint, Compositing).

Standard Library Only (Zero External Dependencies).
"""

from __future__ import annotations
import sys
import time
from typing import List, Optional, Tuple, Dict, Any

# ANSI Color Codes for terminal visual reporting
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_DIM    = "\033[2m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAGENTA= "\033[35m"
CLR_CYAN   = "\033[36m"


# ============================================================================
# 1. GEOMETRY & CONSTRAINTS (Box Model)
# ============================================================================

class BoxConstraints:
    """Simulates Flutter's BoxConstraints: Constraints go down, sizes go up."""
    def __init__(self, min_w: float = 0.0, max_w: float = float('inf'),
                 min_h: float = 0.0, max_h: float = float('inf')):
        self.min_w = min_w
        self.max_w = max_w
        self.min_h = min_h
        self.max_h = max_h

    def constrain_width(self, width: float) -> float:
        return max(self.min_w, min(self.max_w, width))

    def constrain_height(self, height: float) -> float:
        return max(self.min_h, min(self.max_h, height))

    def __repr__(self) -> str:
        return f"BoxConstraints(w:[{self.min_w:.1f}..{self.max_w:.1f}], h:[{self.min_h:.1f}..{self.max_h:.1f}])"


class Size:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def __repr__(self) -> str:
        return f"Size({self.width:.1f} x {self.height:.1f})"


# ============================================================================
# 2. THE THREE TREES ARCHITECTURE
# ============================================================================

# --- WIDGET TREE (Immutable Configuration) ---
class Widget:
    """Blueprint configuration. Cheap to instantiate and discard."""
    def __init__(self, key: Optional[str] = None):
        self.key = key

    def create_element(self) -> Element:
        raise NotImplementedError

    @staticmethod
    def can_update(old_widget: Widget, new_widget: Widget) -> bool:
        """Core Flutter reconciliation rule: match runtimeType and Key."""
        return (type(old_widget) is type(new_widget)) and (old_widget.key == new_widget.key)


class RenderObjectWidget(Widget):
    """Widgets that create and configure RenderObjects directly."""
    def create_render_object(self) -> RenderObject:
        raise NotImplementedError

    def update_render_object(self, render_object: RenderObject) -> None:
        raise NotImplementedError


# --- RENDER TREE (Mutable Layout & Paint Engine) ---
class RenderObject:
    """Retains layout geometry and performs rendering commands."""
    def __init__(self, debug_label: str):
        self.debug_label = debug_label
        self.constraints: Optional[BoxConstraints] = None
        self.size: Optional[Size] = None
        self.offset: Tuple[float, float] = (0.0, 0.0)
        self.needs_layout = True
        self.needs_paint = True
        self.parent: Optional[RenderObject] = None

    def mark_needs_layout(self) -> None:
        if not self.needs_layout:
            self.needs_layout = True
            if self.parent:
                self.parent.mark_needs_layout()

    def mark_needs_paint(self) -> None:
        if not self.needs_paint:
            self.needs_paint = True
            if self.parent:
                self.parent.mark_needs_paint()

    def layout(self, constraints: BoxConstraints) -> None:
        if not self.needs_layout and self.constraints == constraints:
            return  # Cache hit (Layout pass optimization)
        self.constraints = constraints
        self.perform_layout()
        self.needs_layout = False
        self.mark_needs_paint()

    def perform_layout(self) -> None:
        raise NotImplementedError

    def paint(self, canvas_ops: List[str], offset: Tuple[float, float]) -> None:
        raise NotImplementedError


# --- ELEMENT TREE (Lifecycle & Reconciliation Host) ---
class Element:
    """Persistent lifecycle entity binding Widget blueprints to RenderObjects."""
    def __init__(self, widget: Widget):
        self.widget = widget
        self.parent: Optional[Element] = None
        self.render_object: Optional[RenderObject] = None
        self.is_dirty = True

    def mount(self, parent: Optional[Element]) -> None:
        self.parent = parent

    def mark_needs_build(self) -> None:
        self.is_dirty = True

    def rebuild(self) -> None:
        if not self.is_dirty:
            return
        self.perform_rebuild()
        self.is_dirty = False

    def perform_rebuild(self) -> None:
        pass

    def update(self, new_widget: Widget) -> None:
        self.widget = new_widget


class RenderObjectElement(Element):
    """Element that manages the lifecycle of a RenderObject."""
    def mount(self, parent: Optional[Element]) -> None:
        super().mount(parent)
        rowidget = self.widget  # type: ignore
        self.render_object = rowidget.create_render_object()

    def update(self, new_widget: Widget) -> None:
        super().update(new_widget)
        rowidget = new_widget  # type: ignore
        if self.render_object:
            rowidget.update_render_object(self.render_object)


# ============================================================================
# 3. CONCRETE WIDGETS & RENDER OBJECTS
# ============================================================================

class RenderText(RenderObject):
    def __init__(self, text: str):
        super().__init__(f"RenderText('{text}')")
        self.text = text

    def perform_layout(self) -> None:
        # Approximate font metrics: char_width=8px, line_height=16px
        w = len(self.text) * 8.0
        h = 16.0
        assert self.constraints is not None
        self.size = Size(self.constraints.constrain_width(w),
                         self.constraints.constrain_height(h))

    def paint(self, canvas_ops: List[str], offset: Tuple[float, float]) -> None:
        ox, oy = offset[0] + self.offset[0], offset[1] + self.offset[1]
        canvas_ops.append(f"DRAW_TEXT '{self.text}' at ({ox:.1f}, {oy:.1f})")
        self.needs_paint = False


class Text(RenderObjectWidget):
    def __init__(self, text: str, key: Optional[str] = None):
        super().__init__(key)
        self.text = text

    def create_element(self) -> Element:
        return RenderObjectElement(self)

    def create_render_object(self) -> RenderObject:
        return RenderText(self.text)

    def update_render_object(self, render_object: RenderObject) -> None:
        r_text = render_object  # type: ignore
        if r_text.text != self.text:
            r_text.text = self.text
            r_text.debug_label = f"RenderText('{self.text}')"
            r_text.mark_needs_layout()


class RenderFlex(RenderObject):
    """Simulates Column/Row layout: Distributes vertical offsets."""
    def __init__(self):
        super().__init__("RenderFlex[Column]")
        self.children: List[RenderObject] = []

    def perform_layout(self) -> None:
        assert self.constraints is not None
        total_height = 0.0
        max_child_width = 0.0

        for child in self.children:
            child.parent = self
            # Unbounded vertical constraint inside flex child
            child_constraints = BoxConstraints(
                min_w=0.0, max_w=self.constraints.max_w,
                min_h=0.0, max_h=float('inf')
            )
            child.layout(child_constraints)
            child.offset = (0.0, total_height)
            assert child.size is not None
            total_height += child.size.height + 4.0  # 4px gap
            max_child_width = max(max_child_width, child.size.width)

        self.size = Size(
            self.constraints.constrain_width(max_child_width),
            self.constraints.constrain_height(total_height)
        )

    def paint(self, canvas_ops: List[str], offset: Tuple[float, float]) -> None:
        ox, oy = offset[0] + self.offset[0], offset[1] + self.offset[1]
        canvas_ops.append(f"PUSH_LAYER ColumnBounds ({ox:.1f}, {oy:.1f}, {self.size.width:.1f}x{self.size.height:.1f})")  # type: ignore
        for child in self.children:
            child.paint(canvas_ops, (ox, oy))
        canvas_ops.append("POP_LAYER")
        self.needs_paint = False


class ColumnElement(RenderObjectElement):
    def __init__(self, widget: Widget):
        super().__init__(widget)
        self.child_elements: List[Element] = []

    def perform_rebuild(self) -> None:
        col_widget: Column = self.widget  # type: ignore
        r_flex: RenderFlex = self.render_object  # type: ignore

        # --- Reconciler Diffing Algorithm (update_children) ---
        new_widgets = col_widget.children
        old_elements = self.child_elements
        new_elements: List[Element] = []
        new_render_children: List[RenderObject] = []

        max_len = max(len(new_widgets), len(old_elements))
        for i in range(max_len):
            if i < len(new_widgets) and i < len(old_elements):
                old_elem = old_elements[i]
                new_w = new_widgets[i]
                if Widget.can_update(old_elem.widget, new_w):
                    # Element reuse: Mutate existing RenderObject
                    old_elem.update(new_w)
                    old_elem.rebuild()
                    new_elements.append(old_elem)
                    new_render_children.append(old_elem.render_object)  # type: ignore
                    continue

            if i < len(new_widgets):
                # Element creation: Mount new subtree
                new_elem = new_widgets[i].create_element()
                new_elem.mount(self)
                new_elem.rebuild()
                new_elements.append(new_elem)
                new_render_children.append(new_elem.render_object)  # type: ignore

        self.child_elements = new_elements
        r_flex.children = new_render_children
        r_flex.mark_needs_layout()


class Column(RenderObjectWidget):
    def __init__(self, children: List[Widget], key: Optional[str] = None):
        super().__init__(key)
        self.children = children

    def create_element(self) -> Element:
        return ColumnElement(self)

    def create_render_object(self) -> RenderObject:
        return RenderFlex()

    def update_render_object(self, render_object: RenderObject) -> None:
        render_object.mark_needs_layout()


# ============================================================================
# 4. PIPELINE OWNER & ENGINE EXECUTION SIMULATION
# ============================================================================

class EnginePipelineOwner:
    """Coordinates Frame steps: Rebuild -> Layout -> Paint -> Composite."""
    def __init__(self):
        self.root_element: Optional[Element] = None
        self.viewport_constraints = BoxConstraints(min_w=320.0, max_w=320.0, min_h=240.0, max_h=240.0)

    def render_frame(self, frame_no: int, new_root_widget: Widget) -> None:
        print(f"\n{CLR_BOLD}{CLR_BLUE}=== [FRAME {frame_no}] ENGINE FRAME PIPELINE INITIATED ==={CLR_RESET}")
        t_start = time.perf_counter()

        # Step 1: Declarative Build / Reconciliation Phase
        print(f"{CLR_MAGENTA}Phase 1: Build & Reconciliation{CLR_RESET}")
        if self.root_element is None:
            print(f"  {CLR_GREEN}↳ Initializing Element Tree from Root Widget...{CLR_RESET}")
            self.root_element = new_root_widget.create_element()
            self.root_element.mount(None)
            self.root_element.rebuild()
        else:
            if Widget.can_update(self.root_element.widget, new_root_widget):
                print(f"  {CLR_CYAN}↳ CanUpdate matched! Reusing root element structure.{CLR_RESET}")
                self.root_element.update(new_root_widget)
                self.root_element.rebuild()
            else:
                print(f"  {CLR_RED}↳ CanUpdate failed. Tearing down element tree!{CLR_RESET}")
                self.root_element = new_root_widget.create_element()
                self.root_element.mount(None)
                self.root_element.rebuild()

        root_ro = self.root_element.render_object
        assert root_ro is not None

        # Step 2: Layout Phase (Constraints Down, Sizes Up)
        print(f"{CLR_YELLOW}Phase 2: Layout Pass (Dirty layout nodes only){CLR_RESET}")
        layout_visited = 0
        if root_ro.needs_layout:
            root_ro.layout(self.viewport_constraints)
            layout_visited += 1
            print(f"  ↳ Layout Solved: Root size is {root_ro.size}")
        else:
            print("  ↳ Layout Skipped (Clean subtrees cached)")

        # Step 3: Paint Phase (Recording to Skia/Impeller Canvas)
        print(f"{CLR_CYAN}Phase 3: Paint Pass (Recording Canvas Operations){CLR_RESET}")
        canvas_commands: List[str] = []
        if root_ro.needs_paint:
            root_ro.paint(canvas_commands, (0.0, 0.0))
            for cmd in canvas_commands:
                print(f"  {CLR_DIM}🎨 {cmd}{CLR_RESET}")
        else:
            print("  ↳ Paint Skipped (Compositor caches valid)")

        # Step 4: Rasterization & Metrics
        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        print(f"{CLR_GREEN}✔ Compositing Complete in {t_elapsed:.3f} ms{CLR_RESET}")


# ============================================================================
# 5. TEST HARNESS: MUTATION BENCHMARK & DEMONSTRATION
# ============================================================================

def inspect_tree(element: Element, depth: int = 0) -> None:
    """Helper to visualize 3 trees concurrently."""
    indent = "  " * depth
    ro_info = "None"
    if element.render_object:
        ro = element.render_object
        ro_info = f"{ro.debug_label} [Sz:{ro.size}]"
    print(f"{indent}{CLR_BOLD}W:{CLR_RESET}{element.widget.__class__.__name__} "
          f"--> {CLR_GREEN}E:{CLR_RESET}{element.__class__.__name__} "
          f"--> {CLR_YELLOW}RO:{CLR_RESET}{ro_info}")

    if isinstance(element, ColumnElement):
        for child in element.child_elements:
            inspect_tree(child, depth + 1)


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}Flutter Declarative UI Engineering & Rendering Internals Simulation{CLR_RESET}")
    print(f"{CLR_DIM}Simulating: Reconciliation diffing, Layout solver, Repaint boundaries.{CLR_RESET}")

    engine = EnginePipelineOwner()

    # Frame 1: Initial Render
    frame1_ui = Column([
        Text("App Header: System Terminal", key="header"),
        Text("Counter: 0", key="counter"),
        Text("Static Status Bar", key="status")
    ])
    engine.render_frame(1, frame1_ui)

    print(f"\n{CLR_BOLD}--- Three-Tree Hierarchy Snapshot (Post-Frame 1) ---{CLR_RESET}")
    assert engine.root_element is not None
    inspect_tree(engine.root_element)

    # Frame 2: State Mutation (Declarative change: Counter incremented, Header/Status identical)
    print(f"\n{CLR_BOLD}--- Triggering State Mutation: Counter += 1 ---{CLR_RESET}")
    frame2_ui = Column([
        Text("App Header: System Terminal", key="header"),
        Text("Counter: 1", key="counter"),
        Text("Static Status Bar", key="status")
    ])
    engine.render_frame(2, frame2_ui)

    # Frame 3: Structural Mutation (Injecting item at front)
    print(f"\n{CLR_BOLD}--- Triggering Structural Mutation: Adding Alert Banner ---{CLR_RESET}")
    frame3_ui = Column([
        Text("[ALERT] Thermal High", key="alert"),
        Text("App Header: System Terminal", key="header"),
        Text("Counter: 1", key="counter"),
        Text("Static Status Bar", key="status")
    ])
    engine.render_frame(3, frame3_ui)

    print(f"\n{CLR_BOLD}--- Three-Tree Hierarchy Snapshot (Post-Frame 3) ---{CLR_RESET}")
    inspect_tree(engine.root_element)

    print(f"\n{CLR_BOLD}{CLR_GREEN}Simulation finished successfully with clean pipeline lifecycles.{CLR_RESET}")


if __name__ == "__main__":
    main()