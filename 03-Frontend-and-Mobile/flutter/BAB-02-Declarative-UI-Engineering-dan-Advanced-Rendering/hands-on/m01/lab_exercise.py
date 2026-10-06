#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Arsitektur Flutter Three Trees & Rendering Pipeline
Materi: BAB-02 Declarative UI Engineering & Advanced Rendering
Konsep:
  1. Declarative paradigm: UI = f(state)
  2. The Three Trees: Widget Tree -> Element Tree -> RenderObject Tree
  3. Constraint propagation: "Constraints go down. Sizes go up. Parent sets position."
  4. Dirty element marking & reconciliation (canUpdate / element reuse)
  5. Paint & Compositing Boundary Simulation
"""

import time
import sys
from typing import List, Optional, Tuple, Dict, Any

# ANSI Color Codes for terminal output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BG_DARK = "\033[40m"


class BoxConstraints:
    """Simulasi BoxConstraints di Flutter: minWidth, maxWidth, minHeight, maxHeight."""
    def __init__(self, min_w: float, max_w: float, min_h: float, max_h: float):
        self.min_w = max(0.0, min_w)
        self.max_w = max(self.min_w, max_w)
        self.min_h = max(0.0, min_h)
        self.max_h = max(self.min_h, max_h)

    def constrain(self, width: float, height: float) -> Tuple[float, float]:
        w = max(self.min_w, min(width, self.max_w))
        h = max(self.min_h, min(height, self.max_h))
        return (w, h)

    def is_tight(self) -> bool:
        return self.min_w >= self.max_w and self.min_h >= self.max_h

    def __str__(self) -> str:
        return f"Constraints(w:[{self.min_w:.0f}..{self.max_w:.0f}], h:[{self.min_h:.0f}..{self.max_h:.0f}])"


class Size:
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def __str__(self) -> str:
        return f"{self.width:.1f}x{self.height:.1f}"


# ---------------------------------------------------------------------------
# 1. RENDER OBJECT LAYER
# ---------------------------------------------------------------------------
class RenderObject:
    def __init__(self, name: str):
        self.name = name
        self.constraints: Optional[BoxConstraints] = None
        self.size: Optional[Size] = None
        self.offset: Tuple[float, float] = (0.0, 0.0)
        self.children: List['RenderObject'] = []
        self.is_repaint_boundary: bool = False
        self.needs_layout: bool = True
        self.needs_paint: bool = True

    def layout(self, constraints: BoxConstraints, parent_uses_size: bool = True):
        self.constraints = constraints
        self.perform_layout()
        self.needs_layout = False

    def perform_layout(self):
        # Override di subclass
        pass

    def paint(self, canvas_layer: List[str], depth: int = 0):
        indent = "  " * depth
        boundary_flag = f" {MAGENTA}[RepaintBoundary]{RESET}" if self.is_repaint_boundary else ""
        canvas_layer.append(
            f"{indent}{GREEN}• Render{self.name}{RESET} @ {self.offset} (Size: {self.size}){boundary_flag}"
        )
        for child in self.children:
            child.paint(canvas_layer, depth + 1)
        self.needs_paint = False


class RenderBoxView(RenderObject):
    def __init__(self, desired_w: float, desired_h: float, is_boundary: bool = False):
        super().__init__("BoxView")
        self.desired_w = desired_w
        self.desired_h = desired_h
        self.is_repaint_boundary = is_boundary

    def perform_layout(self):
        # "Constraints go down. Sizes go up."
        cw, ch = self.constraints.constrain(self.desired_w, self.desired_h)
        self.size = Size(cw, ch)


class RenderFlex(RenderObject):
    """Simulasi RenderFlex (Column/Row layout)."""
    def __init__(self, direction: str = "vertical"):
        super().__init__("Flex")
        self.direction = direction

    def perform_layout(self):
        max_cross = 0.0
        total_main = 0.0
        current_y = 0.0

        for child in self.children:
            child_constraints = BoxConstraints(
                0.0, self.constraints.max_w,
                0.0, self.constraints.max_h - total_main
            )
            child.layout(child_constraints, parent_uses_size=True)
            child.offset = (0.0, current_y)
            current_y += child.size.height
            total_main += child.size.height
            max_cross = max(max_cross, child.size.width)

        w, h = self.constraints.constrain(max_cross, total_main)
        self.size = Size(w, h)


# ---------------------------------------------------------------------------
# 2. WIDGET LAYER (Immutable Configuration)
# ---------------------------------------------------------------------------
class Widget:
    def __init__(self, key: Optional[str] = None):
        self.key = key

    def create_element(self) -> 'Element':
        raise NotImplementedError()

    @staticmethod
    def can_update(old_widget: 'Widget', new_widget: 'Widget') -> bool:
        return (type(old_widget) == type(new_widget)) and (old_widget.key == new_widget.key)


class StatelessWidget(Widget):
    def create_element(self) -> 'Element':
        return StatelessElement(self)

    def build(self, context: 'BuildContext') -> Widget:
        raise NotImplementedError()


class Container(Widget):
    def __init__(self, width: float, height: float, child: Optional[Widget] = None, repaint_boundary: bool = False):
        super().__init__()
        self.width = width
        self.height = height
        self.child = child
        self.repaint_boundary = repaint_boundary

    def create_element(self) -> 'Element':
        return ContainerElement(self)


class Column(Widget):
    def __init__(self, children: List[Widget]):
        super().__init__()
        self.children = children

    def create_element(self) -> 'Element':
        return ColumnElement(self)


# ---------------------------------------------------------------------------
# 3. ELEMENT LAYER (Mutable Lifecycle & Tree Reconciliation)
# ---------------------------------------------------------------------------
class BuildContext:
    def __init__(self, element: 'Element'):
        self.element = element


class Element:
    _id_counter = 0

    def __init__(self, widget: Widget):
        Element._id_counter += 1
        self.element_id = Element._id_counter
        self.widget = widget
        self.render_object: Optional[RenderObject] = None
        self.children: List['Element'] = []
        self.is_dirty: bool = True

    def mount(self, parent: Optional['Element']):
        self.is_dirty = False

    def update(self, new_widget: Widget):
        self.widget = new_widget
        self.is_dirty = False

    def mark_needs_build(self):
        self.is_dirty = True

    def collect_render_objects(self) -> List['RenderObject']:
        """Mengumpulkan RenderObject dari element ini atau keturunan non-RenderObject."""
        if self.render_object:
            return [self.render_object]
        objs = []
        for c in self.children:
            objs.extend(c.collect_render_objects())
        return objs

    def reconcile_children(self, new_widgets: List[Widget]) -> List['Element']:
        """Simulasi element reconciliation (re-use element jika can_update bernilai True)."""
        reconciled: List['Element'] = []
        for i, new_w in enumerate(new_widgets):
            if i < len(self.children) and Widget.can_update(self.children[i].widget, new_w):
                # REUSE existing Element & RenderObject!
                elem = self.children[i]
                elem.update(new_w)
                reconciled.append(elem)
            else:
                # INFLATE new Element!
                elem = new_w.create_element()
                elem.mount(self)
                reconciled.append(elem)
        return reconciled


class StatelessElement(Element):
    def mount(self, parent: Optional[Element]):
        super().mount(parent)
        self.rebuild()

    def rebuild(self):
        widget: StatelessWidget = self.widget  # type: ignore
        built_widget = widget.build(BuildContext(self))
        self.children = self.reconcile_children([built_widget])

    def update(self, new_widget: Widget):
        super().update(new_widget)
        self.rebuild()


class ContainerElement(Element):
    def mount(self, parent: Optional[Element]):
        super().mount(parent)
        w: Container = self.widget  # type: ignore
        self.render_object = RenderBoxView(w.width, w.height, is_boundary=w.repaint_boundary)
        if w.child:
            self.children = self.reconcile_children([w.child])
            if self.children[0].render_object:
                self.render_object.children.append(self.children[0].render_object)

    def update(self, new_widget: Widget):
        old_w: Container = self.widget  # type: ignore
        super().update(new_widget)
        w: Container = new_widget  # type: ignore
        if self.render_object and isinstance(self.render_object, RenderBoxView):
            self.render_object.desired_w = w.width
            self.render_object.desired_h = w.height
            self.render_object.is_repaint_boundary = w.repaint_boundary
            self.render_object.needs_layout = True

        if w.child:
            self.children = self.reconcile_children([w.child])
            if self.children[0].render_object and self.render_object:
                self.render_object.children = [self.children[0].render_object]


class ColumnElement(Element):
    def mount(self, parent: Optional[Element]):
        super().mount(parent)
        self.render_object = RenderFlex(direction="vertical")
        w: Column = self.widget  # type: ignore
        self.children = self.reconcile_children(w.children)
        for child_elem in self.children:
            if child_elem.render_object:
                self.render_object.children.append(child_elem.render_object)

    def update(self, new_widget: Widget):
        super().update(new_widget)
        w: Column = new_widget  # type: ignore
        self.children = self.reconcile_children(w.children)
        if self.render_object:
            self.render_object.children = [
                c.render_object for c in self.children if c.render_object
            ]
            self.render_object.needs_layout = True


# ---------------------------------------------------------------------------
# 4. APP DEMO WIDGETS
# ---------------------------------------------------------------------------
class CounterCard(StatelessWidget):
    def __init__(self, count: int, card_color: str = "default"):
        super().__init__()
        self.count = count
        self.card_color = card_color

    def build(self, context: BuildContext) -> Widget:
        # Dynamic layout based on state count
        box_width = 120.0 + (self.count * 10.0)
        box_height = 40.0
        return Container(
            width=box_width,
            height=box_height,
            repaint_boundary=(self.count % 2 == 0)
        )


class RootApp(StatelessWidget):
    def __init__(self, count: int):
        super().__init__()
        self.count = count

    def build(self, context: BuildContext) -> Widget:
        return Column(
            children=[
                Container(width=200.0, height=30.0),
                CounterCard(self.count),
                Container(width=180.0, height=25.0)
            ]
        )


# ---------------------------------------------------------------------------
# 5. PIPELINE ENGINE & VISUALIZER
# ---------------------------------------------------------------------------
class FlutterSimulationEngine:
    def __init__(self):
        self.state_count = 0
        self.root_element: Optional[Element] = None
        self.root_constraints = BoxConstraints(min_w=300.0, max_w=300.0, min_h=600.0, max_h=600.0)

    def run_pipeline(self, initial_count: int = 0):
        self.state_count = initial_count
        print(f"\n{BOLD}{CYAN}=== FLUTTER FRAME PIPELINE TRIGGERED (State = {self.state_count}) ==={RESET}")
        
        # Phase 1: Build Phase
        t0 = time.perf_counter()
        app_widget = RootApp(self.state_count)
        
        if self.root_element is None:
            print(f"{YELLOW}[Phase 1: Build & Mount]{RESET} First-time inflation of Element Tree...")
            self.root_element = app_widget.create_element()
            self.root_element.mount(None)
        else:
            print(f"{YELLOW}[Phase 1: Re-Build & Reconciliation]{RESET} Diffing Widget Tree with existing Element Tree...")
            self.root_element.update(app_widget)
        t_build = (time.perf_counter() - t0) * 1000

        # Phase 2: Layout Phase ("Constraints Down, Sizes Up")
        t0 = time.perf_counter()
        print(f"{BLUE}[Phase 2: Layout Pass]{RESET} Propagating constraints: {self.root_constraints}")
        render_root = self._get_root_render_object(self.root_element)
        if render_root:
            render_root.layout(self.root_constraints)
        t_layout = (time.perf_counter() - t0) * 1000

        # Phase 3: Paint & Compositing Phase
        t0 = time.perf_counter()
        print(f"{MAGENTA}[Phase 3: Paint Pass]{RESET} Walking RenderObject Tree with RepaintBoundary tracking...")
        canvas_buffer: List[str] = []
        if render_root:
            render_root.paint(canvas_buffer)
        t_paint = (time.perf_counter() - t0) * 1000

        # Print Benchmark Timing
        print(f"{DIM}⏱ Frame Timing: Build={t_build:.3f}ms | Layout={t_layout:.3f}ms | Paint={t_paint:.3f}ms{RESET}")

        # Visualizations
        self.print_three_trees(app_widget, self.root_element, render_root)
        print(f"\n{BOLD}{GREEN}--- Canvas Paint Output Buffer ---{RESET}")
        for line in canvas_buffer:
            print(line)

    def _get_root_render_object(self, elem: Element) -> Optional[RenderObject]:
        if elem.render_object:
            return elem.render_object
        for child in elem.children:
            res = self._get_root_render_object(child)
            if res:
                return res
        return None

    def print_three_trees(self, widget: Widget, element: Element, render_root: Optional[RenderObject]):
        print(f"\n{BOLD}{CYAN}------------------- THE THREE TREES DUALITY -------------------{RESET}")
        
        # 1. Widget Tree (Immutable Blueprints)
        print(f"\n{BOLD}{YELLOW}1. Widget Tree (Immutable Configurations):{RESET}")
        self._print_widget_tree(widget, depth=1)

        # 2. Element Tree (Persistent State & Reconciliation)
        print(f"\n{BOLD}{CYAN}2. Element Tree (Lifecycle & Context Managers):{RESET}")
        self._print_element_tree(element, depth=1)

        # 3. RenderObject Tree (Geometry & Paint)
        print(f"\n{BOLD}{GREEN}3. RenderObject Tree (Layout & Compositing Layer):{RESET}")
        if render_root:
            self._print_render_tree(render_root, depth=1)
        print(f"{BOLD}{CYAN}---------------------------------------------------------------{RESET}")

    def _print_widget_tree(self, w: Widget, depth: int):
        indent = "  " * depth
        extra = ""
        if isinstance(w, Container):
            extra = f" (target_size: {w.width}x{w.height})"
        elif isinstance(w, CounterCard):
            extra = f" (count: {w.count})"
        print(f"{indent}{YELLOW}↳ {w.__class__.__name__}{RESET}{extra}")

        if isinstance(w, Container) and w.child:
            self._print_widget_tree(w.child, depth + 1)
        elif isinstance(w, Column):
            for child in w.children:
                self._print_widget_tree(child, depth + 1)

    def _print_element_tree(self, e: Element, depth: int):
        indent = "  " * depth
        ro_link = f" -> {GREEN}Linked to {e.render_object.name}#{id(e.render_object) % 10000}{RESET}" if e.render_object else f" -> {DIM}(No RenderObject){RESET}"
        print(f"{indent}{CYAN}⚙ {e.__class__.__name__}[ID:{e.element_id}]{RESET}{ro_link}")
        for child in e.children:
            self._print_element_tree(child, depth + 1)

    def _print_render_tree(self, ro: RenderObject, depth: int):
        indent = "  " * depth
        boundary = f" {MAGENTA}[Layer Boundary]{RESET}" if ro.is_repaint_boundary else ""
        size_str = f"Size={ro.size}" if ro.size else "Size=Uncalculated"
        print(f"{indent}{GREEN}▣ Render{ro.name}#{id(ro) % 10000}{RESET} : {size_str}, Offset={ro.offset}{boundary}")
        for child in ro.children:
            self._print_render_tree(child, depth + 1)


# ---------------------------------------------------------------------------
# 6. INTERACTIVE CLI RUNNER
# ---------------------------------------------------------------------------
def run_interactive_simulation():
    engine = FlutterSimulationEngine()
    print(f"{BOLD}{GREEN}================================================================{RESET}")
    print(f"{BOLD}{GREEN}  FLUTTER LAB M01: DECLARATIVE UI & ADVANCED RENDERING PIPELINE {RESET}")
    print(f"{BOLD}{GREEN}================================================================{RESET}")
    print("Simulasi interaktif pohon Flutter (Widget, Element, RenderObject)")
    print("Konsep yang didemonstrasikan:")
    print("  • UI = f(state) saat Counter bertambah")
    print("  • Element reuse (ID Element tetap sama meski Widget diganti)")
    print("  • BoxConstraints & RenderFlex pass")
    print("  • RepaintBoundary marking ketika count genap")

    # Initial frame
    engine.run_pipeline(initial_count=0)

    # Interactive loops
    step = 0
    while step < 3:
        step += 1
        print(f"\n{BOLD}{YELLOW}>>> SIMULASI PERUBAHAN STATE #{step} (setState) <<<{RESET}")
        print(f"Triggering setState(() => count = {step})...")
        time.sleep(0.5)
        engine.run_pipeline(initial_count=step)

    print(f"\n{BOLD}{GREEN}✔ Simulasi Lab M01 Selesai dengan Sukses.{RESET}")
    print("Perhatikan bagaimana:")
    print("  1. Widget Tree selalu dibuat ulang (baru setiap build).")
    print("  2. Element ID tidak berubah (Element Tree dipertahankan dan direkonsiliasi).")
    print("  3. RenderObject melakukan relayout dan menghitung ukuran baru secara deterministik.")


if __name__ == "__main__":
    run_interactive_simulation()
