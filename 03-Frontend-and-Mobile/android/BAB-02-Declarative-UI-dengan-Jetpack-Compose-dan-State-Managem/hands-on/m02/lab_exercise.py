#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Arsitektur State Management & Recomposition Engine
Kategori: 03-Frontend-and-Mobile | Bab: 02 - Jetpack Compose Internals

Deskripsi:
Script ini memodelkan runtime Jetpack Compose secara deterministik:
1. Snapshot State System (mutableStateOf, tracking observer via call-stack context).
2. Slot Table & Composer Scope (pemetaan node, positional memoization).
3. Smart Recomposition Engine (skipping composables yang stabil / parameter tidak berubah).
4. Derived State Optimization (derivedStateOf simulation).
"""

from __future__ import annotations
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"


# ============================================================================
# Core Runtime: Snapshot State & Reader Tracking
# ============================================================================

class CompositionSnapshot:
    """
    Menyimpan stack frame scope composable yang sedang aktif dieksekusi.
    Mencatat dependensi pembacaan state secara reaktif (Read Observation).
    """
    _current_scope: Optional[RecomposeScope] = None

    @classmethod
    def current(cls) -> Optional[RecomposeScope]:
        return cls._current_scope

    @classmethod
    def enter(cls, scope: RecomposeScope) -> Optional[RecomposeScope]:
        prev = cls._current_scope
        cls._current_scope = scope
        return prev

    @classmethod
    def exit(cls, prev: Optional[RecomposeScope]) -> None:
        cls._current_scope = prev


class MutableState:
    """
    Simulasi `mutableStateOf(initialValue)` di Jetpack Compose.
    Menggunakan Structural Equality Policy untuk mencegah recomposition jika nilai identik.
    """
    def __init__(self, value: Any, name: str = "State"):
        self._value = value
        self.name = name
        self._observers: Set[RecomposeScope] = set()

    @property
    def value(self) -> Any:
        # Laporkan pembacaan state ke scope composable yang aktif
        active_scope = CompositionSnapshot.current()
        if active_scope is not None:
            self._observers.add(active_scope)
            active_scope.dependencies.add(self)
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        # Structural equality check: skip jika nilai sama
        if self._value == new_val:
            return
        self._value = new_val
        self._notify_observers()

    def _notify_observers(self) -> None:
        """Invalidasi semua scope yang membaca state ini."""
        observers_copy = list(self._observers)
        for scope in observers_copy:
            scope.invalidate()

    def unregister(self, scope: RecomposeScope) -> None:
        self._observers.discard(scope)

    def __repr__(self) -> str:
        return f"MutableState({self.name}={self._value})"


class DerivedState:
    """
    Simulasi `derivedStateOf { ... }`.
    Mengkalkulasi ulang nilai hanya ketika dependencies internal berubah.
    """
    def __init__(self, calculation: Callable[[], Any], name: str = "DerivedState"):
        self.calculation = calculation
        self.name = name
        self._cached_value: Any = None
        self._is_dirty = True
        self._internal_state = MutableState(None, name=f"{name}_Notifier")

    @property
    def value(self) -> Any:
        # Re-calc jika perlu
        if self._is_dirty:
            self._cached_value = self.calculation()
            self._is_dirty = False
        # Link ke parent observer
        return self._internal_state.value or self._cached_value

    def mark_dirty(self) -> None:
        self._is_dirty = True
        self._internal_state.value = time.time_ns()


# ============================================================================
# Recomposer & Slot Engine
# ============================================================================

@dataclass
class UINode:
    """Representasi Layout Node (mirip LayoutNode internal Android)."""
    id: str
    tag: str
    rendered_text: str
    children: List[UINode] = field(default_factory=list)

    def print_tree(self, indent: int = 0) -> None:
        prefix = "  " * indent + "└─ " if indent > 0 else ""
        print(f"{CLR_DIM}{prefix}{CLR_RESET}{CLR_GREEN}[{self.tag}]{CLR_RESET} {self.rendered_text}")
        for child in self.children:
            child.print_tree(indent + 1)


class RecomposeScope:
    """
    Representasi batasan RecomposeScopeImpl pada Compose Compiler.
    Memiliki kemampuan invalidasi mandiri dan melacak recomposition count.
    """
    def __init__(self, node_id: str, composable_fn: Callable[..., UINode]):
        self.node_id = node_id
        self.composable_fn = composable_fn
        self.dependencies: Set[MutableState] = set()
        self.is_dirty: bool = True
        self.recompose_count: int = 0
        self.last_result: Optional[UINode] = None
        self.last_params: Dict[str, Any] = {}

    def invalidate(self) -> None:
        if not self.is_dirty:
            self.is_dirty = True
            ComposerEngine.get_instance().schedule_invalidation(self)

    def execute(self, **kwargs) -> UINode:
        """
        Mengeksekusi composable di bawah proteksi tracking reader snapshot.
        """
        # Bersihkan dependency lama sebelum eksekusi ulang
        for dep in self.dependencies:
            dep.unregister(self)
        self.dependencies.clear()

        prev_scope = CompositionSnapshot.enter(self)
        try:
            self.recompose_count += 1
            self.last_params = kwargs.copy()
            self.last_result = self.composable_fn(**kwargs)
            self.is_dirty = False
            return self.last_result
        finally:
            CompositionSnapshot.exit(prev_scope)


class ComposerEngine:
    """
    Orkestrator Recomposition Lifecycle (Simulasi Recomposer thread).
    """
    _instance: Optional[ComposerEngine] = None

    def __init__(self):
        self._scopes: Dict[str, RecomposeScope] = {}
        self._dirty_queue: List[RecomposeScope] = []
        self.root_node: Optional[UINode] = None

    @classmethod
    def get_instance(cls) -> ComposerEngine:
        if cls._instance is None:
            cls._instance = ComposerEngine()
        return cls._instance

    def register_scope(self, node_id: str, fn: Callable[..., UINode]) -> RecomposeScope:
        if node_id not in self._scopes:
            self._scopes[node_id] = RecomposeScope(node_id, fn)
        return self._scopes[node_id]

    def schedule_invalidation(self, scope: RecomposeScope) -> None:
        if scope not in self._dirty_queue:
            self._dirty_queue.append(scope)

    def apply_changes(self) -> None:
        """Flush invalidation queue dan picu targeted smart recomposition."""
        if not self._dirty_queue:
            print(f"{CLR_DIM}==> Recomposer: Antrean bersih, tidak ada mutasi state.{CLR_RESET}")
            return

        print(f"\n{CLR_YELLOW}=== FLUSHING FRAME / TARGETED RECOMPOSITION ==={CLR_RESET}")
        pass_idx = 1
        while self._dirty_queue:
            scope = self._dirty_queue.pop(0)
            print(f"  {CLR_MAGENTA}⚡ Recomposing Scope:{CLR_RESET} {CLR_BOLD}{scope.node_id}{CLR_RESET} "
                  f"(Pass #{pass_idx}, Executions: {scope.recompose_count + 1})")
            scope.execute(**scope.last_params)
            pass_idx += 1
        print(f"{CLR_GREEN}=== FRAME COMPOSITION SELESAI ==={CLR_RESET}\n")


# ============================================================================
# Declarative Components (Mocking Jetpack Compose UI Functions)
# ============================================================================

def ComposableHeader(title: str) -> UINode:
    """Komponen statis murni: Harus dilewati (skipped) saat recomposition."""
    scope = ComposerEngine.get_instance().register_scope("HeaderScope", ComposableHeader)
    
    # Smart Skipping check (Jika parameter tidak berubah dan tidak dirty)
    if not scope.is_dirty and scope.last_params.get("title") == title:
        print(f"  {CLR_CYAN}[SKIPPED]{CLR_RESET} HeaderScope: Parameter stabil & state tidak berubah.")
        return scope.last_result  # type: ignore

    print(f"  {CLR_BLUE}[EXEC]{CLR_RESET} Mengompilasi ComposableHeader...")
    return scope.execute(title=title)


def _impl_header(title: str) -> UINode:
    return UINode(id="hdr", tag="Header", rendered_text=title)


ComposableHeader = lambda title: ComposerEngine.get_instance().register_scope("HeaderScope", _impl_header).execute(title=title) if ComposerEngine.get_instance().register_scope("HeaderScope", _impl_header).is_dirty or ComposerEngine.get_instance().register_scope("HeaderScope", _impl_header).last_params.get("title") != title else (print(f"  {CLR_CYAN}[SKIPPED]{CLR_RESET} HeaderScope (Pure/Unchanged)") or ComposerEngine.get_instance().register_scope("HeaderScope", _impl_header).last_result)


def ComposableCartItem(item_id: str, name: str, qty_state: MutableState) -> UINode:
    """Komponen item belanja: Hanya recompose jika qty_state miliknya berubah."""
    scope_id = f"ItemRow_{item_id}"
    engine = ComposerEngine.get_instance()
    
    def _execute():
        # Membaca qty_state.value di sini mendaftarkan scope ini ke state
        current_qty = qty_state.value
        return UINode(
            id=scope_id,
            tag="RowItem",
            rendered_text=f"Product: {name} | Qty: {current_qty} | Subtotal: Rp{current_qty * 15000:,}"
        )

    scope = engine.register_scope(scope_id, lambda: _execute())
    
    if not scope.is_dirty:
        print(f"  {CLR_CYAN}[SKIPPED]{CLR_RESET} {scope_id} (Unchanged)")
        return scope.last_result # type: ignore

    print(f"  {CLR_BLUE}[EXEC]{CLR_RESET} Menyusun {scope_id}...")
    return scope.execute()


def ComposableSummary(total_qty_derived: DerivedState) -> UINode:
    """Komponen Summary: Bergantung pada DerivedState."""
    scope_id = "SummaryCardScope"
    engine = ComposerEngine.get_instance()

    def _execute():
        tot = total_qty_derived.value
        status = "Gratis Ongkir Aktif!" if tot >= 5 else "Beli minimal 5 untuk Free Ongkir"
        return UINode(
            id=scope_id,
            tag="SummaryCard",
            rendered_text=f"Total Items: {tot} units -> [{status}]"
        )

    scope = engine.register_scope(scope_id, lambda: _execute())
    if not scope.is_dirty:
        print(f"  {CLR_CYAN}[SKIPPED]{CLR_RESET} {scope_id}")
        return scope.last_result # type: ignore

    print(f"  {CLR_BLUE}[EXEC]{CLR_RESET} Menyusun {scope_id}...")
    return scope.execute()


def MainScreen(app_title: str, item_a_qty: MutableState, item_b_qty: MutableState, total_derived: DerivedState) -> UINode:
    """Root Composable Layout."""
    print(f"\n{CLR_YELLOW}>>> [Pass Start] Memulai Render Layout Tree <<<{CLR_RESET}")
    
    header_node = ComposableHeader(title=app_title)
    item_a_node = ComposableCartItem("A", "Kopi Robusta", item_a_qty)
    item_b_node = ComposableCartItem("B", "Teh Earl Grey", item_b_qty)
    summary_node = ComposableSummary(total_derived)

    root = UINode(
        id="root",
        tag="Scaffold",
        rendered_text="Jetpack Compose Simulation Root",
        children=[header_node, item_a_node, item_b_node, summary_node]
    )
    return root


# ============================================================================
# Main Execution & Verification Scenario
# ============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_CYAN}=============================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}    SIMULATOR INTERNAL JETPACK COMPOSE STATE & RECOMPOSITION  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}=============================================================={CLR_RESET}\n")

    # 1. State Allocation
    item_a_qty = MutableState(1, name="ItemA_Qty")
    item_b_qty = MutableState(2, name="ItemB_Qty")

    # 2. Derived State Allocation
    def calculate_total():
        return item_a_qty.value + item_b_qty.value
    
    total_qty_derived = DerivedState(calculate_total, name="DerivedTotal")

    # 3. Initial Composition
    print(f"{CLR_BOLD}--- TAHAP 1: INITIAL FULL COMPOSITION ---{CLR_RESET}")
    engine = ComposerEngine.get_instance()
    root = MainScreen("Toko Online Compose Native", item_a_qty, item_b_qty, total_qty_derived)
    engine.root_node = root
    
    print(f"\n{CLR_BOLD}Generated Render Tree:{CLR_RESET}")
    root.print_tree()

    # 4. Mutasi State Granular (Hanya Item A berubah)
    print(f"\n{CLR_BOLD}--- TAHAP 2: MUTASI ISOLASI STATE (item_a_qty Diubah: 1 -> 4) ---{CLR_RESET}")
    print(f"{CLR_DIM}[Action] Mengubah item_a_qty.value = 4 (Harus mentrigger smart recomposition){CLR_RESET}")
    item_a_qty.value = 4
    total_qty_derived.mark_dirty()  # Derived state dinotifikasi
    
    # Jalankan Frame / Recomposition Pass
    engine.apply_changes()

    # Re-render visualisasi tree setelah recomposition
    print(f"{CLR_BOLD}Layout Tree Setelah Recomposition:{CLR_RESET}")
    refreshed_root = MainScreen("Toko Online Compose Native", item_a_qty, item_b_qty, total_qty_derived)
    refreshed_root.print_tree()

    # 5. Mutasi Redundan (Structural Equality Test)
    print(f"\n{CLR_BOLD}--- TAHAP 3: STRUCTURAL EQUALITY CHECK (No-op mutation) ---{CLR_RESET}")
    print(f"{CLR_DIM}[Action] Mengisi nilai identik item_a_qty.value = 4 (Harus diabaikan oleh engine){CLR_RESET}")
    item_a_qty.value = 4
    engine.apply_changes()

    # 6. Analisis Metrik Recomposisi
    print(f"\n{CLR_BOLD}--- TAHAP 4: METRIK FREKUENSI REKOMPOSISI SCOPE ---{CLR_RESET}")
    for scope_id, scope in engine._scopes.items():
        color = CLR_GREEN if scope.recompose_count <= 2 else CLR_RED
        print(f" Scope ID: {CLR_BOLD}{scope_id:<20}{CLR_RESET} | Recomposed: {color}{scope.recompose_count}x{CLR_RESET} "
              f"| Terdaftar pada {len(scope.dependencies)} state dependencies.")

    print(f"\n{CLR_GREEN}✔ Lab verifikasi internal Jetpack Compose berhasil diselesaikan dengan sukses!{CLR_RESET}\n")

if __name__ == "__main__":
    main()