#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Arsitektur Runtime SwiftUI & Paradigma Deklaratif
Topik: swift-ui | Bab 01 - Modul 02

Script ini mensimulasikan mekanisme internal SwiftUI:
1. View Tree & Structural Identity (Representasi View berbasis struct/value type).
2. Property Wrapper Reaktif (@State, Dependency Tracking mirip AttributeGraph Apple).
3. Reconciliation Engine / Diffing (Hanya mengevaluasi node dirty saat state bermutasi).
4. Frame Commit Pipeline (Render terminal berbasis hirarki deklaratif).
"""

from __future__ import annotations
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set, Type

# ==============================================================================
# ANSI Color Codes untuk visualisasi rendering terminal
# ==============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"
GRAY = "\033[90m"

# ==============================================================================
# AttributeGraph Simulator: State Dependency Tracking Engine
# ==============================================================================
class DependencyTracker:
    """
    Melacak View mana yang membaca State tertentu saat evaluasi body (mirip dynamic
    dependency graph AG::Graph pada framework internal SwiftUI).
    """
    _current_evaluating_node: Optional[GraphNode] = None

    @classmethod
    def set_current(cls, node: Optional[GraphNode]) -> None:
        cls._current_evaluating_node = node

    @classmethod
    def current(cls) -> Optional[GraphNode]:
        return cls._current_evaluating_node


class State:
    """
    Simulasi property wrapper @State di SwiftUI.
    Menyimpan value di storage terpisah di luar struct View dan menandai node dirty.
    """
    def __init__(self, initial_value: Any, name: str = ""):
        self._value = initial_value
        self.name = name
        self._subscribers: Set[GraphNode] = set()

    @property
    def value(self) -> Any:
        active_node = DependencyTracker.current()
        if active_node:
            self._subscribers.add(active_node)
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        if self._value != new_val:
            self._value = new_val
            # Invalidation pass: Tandai seluruh dependent view nodes sebagai dirty
            for node in self._subscribers:
                node.mark_dirty()


# ==============================================================================
# Declarative View Primitives
# ==============================================================================
class View:
    """Protokol dasar View: Pure declarative description."""
    @property
    def body(self) -> View:
        raise NotImplementedError("Setiap custom View wajib mengimplementasikan 'body'.")

    def __repr__(self) -> str:
        return self.__class__.__name__


class PrimitiveView(View):
    """Marker untuk view primitif yang langsung dirender (Text, Spacer, Divider)."""
    @property
    def body(self) -> View:
        return self


class Text(PrimitiveView):
    def __init__(self, content: str):
        self.content = content

    def __repr__(self) -> str:
        return f"Text('{self.content}')"


class Button(PrimitiveView):
    def __init__(self, title: str, action: Callable[[], None]):
        self.title = title
        self.action = action

    def __repr__(self) -> str:
        return f"Button('{self.title}')"


class VStack(PrimitiveView):
    def __init__(self, children: List[View]):
        self.children = children

    def __repr__(self) -> str:
        return f"VStack(count={len(self.children)})"


class HStack(PrimitiveView):
    def __init__(self, children: List[View]):
        self.children = children

    def __repr__(self) -> str:
        return f"HStack(count={len(self.children)})"


# ==============================================================================
# Runtime Graph Node & Reconciliation Engine (AttributeGraph Emulation)
# ==============================================================================
class GraphNode:
    """
    Representasi node pada memori runtime SwiftUI (AGNode).
    Mempertahankan state identity di antara re-evaluasi body struct View.
    """
    def __init__(self, view_instance: View, identity: str):
        self.identity = identity
        self.view_instance = view_instance
        self.is_dirty: bool = True
        self.children_nodes: List[GraphNode] = []
        self.rendered_output: List[str] = []
        self.eval_count: int = 0

    def mark_dirty(self) -> None:
        self.is_dirty = True

    def reconcile(self) -> None:
        """
        Reconciliation Pass: Evaluasi body HANYA jika node ditandai dirty.
        """
        if not self.is_dirty:
            return

        self.eval_count += 1
        self.is_dirty = False
        DependencyTracker.set_current(self)

        try:
            if isinstance(self.view_instance, PrimitiveView):
                # Primitive Node: Bangun buffer render primitif
                self._reconcile_primitive()
            else:
                # Composite View: Evaluasi body deklaratif
                evaluated_body = self.view_instance.body
                child_id = f"{self.identity}/0"
                if not self.children_nodes:
                    child_node = GraphNode(evaluated_body, child_id)
                    self.children_nodes = [child_node]
                else:
                    self.children_nodes[0].view_instance = evaluated_body
                    self.children_nodes[0].mark_dirty()

                self.children_nodes[0].reconcile()
                self.rendered_output = self.children_nodes[0].rendered_output
        finally:
            DependencyTracker.set_current(None)

    def _reconcile_primitive(self) -> None:
        view = self.view_instance
        if isinstance(view, Text):
            self.rendered_output = [f"📄 {view.content}"]
        elif isinstance(view, Button):
            self.rendered_output = [f"🔘 [{view.title}]"]
        elif isinstance(view, VStack):
            self._sync_children(view.children)
            self.rendered_output = []
            for child in self.children_nodes:
                child.reconcile()
                self.rendered_output.extend(child.rendered_output)
        elif isinstance(view, HStack):
            self._sync_children(view.children)
            temp: List[str] = []
            for child in self.children_nodes:
                child.reconcile()
                temp.append(" | ".join(child.rendered_output))
            self.rendered_output = ["  " + "  <=>  ".join(temp)]

    def _sync_children(self, new_children: List[View]) -> None:
        """Structural Identity matching berdasar posisi hirarki."""
        new_nodes: List[GraphNode] = []
        for idx, child_view in enumerate(new_children):
            child_id = f"{self.identity}/{idx}_{type(child_view).__name__}"
            existing = next((n for n in self.children_nodes if n.identity == child_id), None)
            if existing:
                existing.view_instance = child_view
                existing.mark_dirty()
                new_nodes.append(existing)
            else:
                new_nodes.append(GraphNode(child_view, child_id))
        self.children_nodes = new_nodes


class SwiftUIHost:
    """Host container yang mengeksekusi render pipeline mirip UIHostingController."""
    def __init__(self, root_view: View):
        self.root_node = GraphNode(root_view, identity="root")
        self.frame_index = 0

    def trigger_render_loop(self, reason: str) -> None:
        self.frame_index += 1
        print(f"\n{BOLD}{CYAN}=== FRAME #{self.frame_index} [Trigger: {reason}] ==={RESET}")
        
        start_time = time.perf_counter()
        self.root_node.reconcile()
        render_time = (time.perf_counter() - start_time) * 1000

        print(f"{GRAY}Pipeline Diff & Re-evaluation: {render_time:.4f} ms{RESET}")
        print(f"{YELLOW}--- Canvas Frame Output ---{RESET}")
        for line in self.root_node.rendered_output:
            print(f"  {line}")
        print(f"{YELLOW}---------------------------{RESET}")

        # Metrics Node Invalidation
        self._print_graph_telemetry(self.root_node)

    def _print_graph_telemetry(self, node: GraphNode, depth: int = 0) -> None:
        indent = "  " * depth
        eval_badge = f"{GREEN}evaluated ({node.eval_count}x){RESET}" if node.eval_count > 0 else f"{GRAY}cached{RESET}"
        print(f"{indent}• [{node.identity}] {type(node.view_instance).__name__} -> {eval_badge}")
        for child in node.children_nodes:
            self._print_graph_telemetry(child, depth + 1)


# ==============================================================================
# Userland SwiftUI Sample: Counter & Profile Dashboard
# ==============================================================================
class StaticHeaderView(View):
    """Sub-view statis yang TIDAK boleh dievaluasi ulang saat counter berubah."""
    @property
    def body(self) -> View:
        return VStack([
            Text(f"{BOLD}SwiftUI Core Architecture Simulation{RESET}"),
            Text("Module: AttributeGraph & Fine-grained Reconciliation Engine"),
        ])


class UserProfileView(View):
    """View dinamis yang terikat pada state independen."""
    def __init__(self, is_online: State):
        self.is_online = is_online

    @property
    def body(self) -> View:
        status_text = f"{GREEN}ONLINE{RESET}" if self.is_online.value else f"{RED}OFFLINE{RESET}"
        return HStack([
            Text("User Status"),
            Text(status_text)
        ])


class DashboardApp(View):
    """Root Application View yang memodelkan dependensi State."""
    def __init__(self):
        self.counter_state = State(0, name="Counter")
        self.online_state = State(False, name="OnlineToggle")

    def increment(self) -> None:
        self.counter_state.value += 1

    def toggle_status(self) -> None:
        self.online_state.value = not self.online_state.value

    @property
    def body(self) -> View:
        # StaticHeaderView tidak memiliki dependensi State apa pun
        return VStack([
            StaticHeaderView(),
            Text("----------------------------------------"),
            UserProfileView(self.online_state),
            Text("----------------------------------------"),
            HStack([
                Text(f"Counter Value: {BOLD}{self.counter_state.value}{RESET}"),
                Button("+ Increment", self.increment),
            ]),
            Button("Toggle Online/Offline Status", self.toggle_status)
        ])


# ==============================================================================
# Eksekusi Lab Interaktif
# ==============================================================================
def main() -> None:
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{MAGENTA}   LAB: MEMBEDAH RUNTIME DEKLARATIF & ATTRIBUTE GRAPH SWIFTUI         {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print("Mendemonstrasikan identitas struktural, auto-dependency tracking,")
    print("serta optimasi subtree re-evaluation tanpa Virtual DOM kaku.")

    app = DashboardApp()
    host = SwiftUIHost(app)

    # 1. First Render Pass (Semua node di-build & dievaluasi)
    host.trigger_render_loop(reason="Initial Render Hierarchy")

    # 2. Mutasi State Counter
    # Observasi: StaticHeaderView dan UserProfileView TIDAK boleh dievaluasi ulang!
    print(f"\n{BOLD}[Aksi User: Menekan tombol '+ Increment']{RESET}")
    app.increment()
    host.trigger_render_loop(reason="State(Counter) diubah ke 1")

    # 3. Mutasi State Counter kedua
    print(f"\n{BOLD}[Aksi User: Menekan tombol '+ Increment' kedua kali]{RESET}")
    app.increment()
    host.trigger_render_loop(reason="State(Counter) diubah ke 2")

    # 4. Mutasi State OnlineToggle
    # Observasi: Counter value dipertahankan di storage terpisah, hanya Profile yang re-render!
    print(f"\n{BOLD}[Aksi User: Menekan tombol 'Toggle Online/Offline Status']{RESET}")
    app.toggle_status()
    host.trigger_render_loop(reason="State(OnlineToggle) diubah ke True")


if __name__ == "__main__":
    main()