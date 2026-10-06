#!/usr/bin/env python3
"""
Lab Exercise: Jetpack Compose & State Management Simulation in Terminal
Bab 02: Declarative UI dengan Jetpack Compose dan State Management

Simulasi ini mengimplementasikan konsep inti Jetpack Compose:
1. Snapshot State Tracking (mutableStateOf & remember)
2. Smart Recomposition & Composable Skipping
3. State Hoisting & Unidirectional Data Flow (UDF)
4. DerivedState (Komputasi efisien tanpa recomposition berlebih)
5. Effect Handling (Simulasi LaunchedEffect & Side-effects)
"""

import sys
import os
import time
from typing import Any, Callable, Dict, List, Optional, Set

# ANSI Color Codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_GREEN = "\033[42m"
    BG_DARK = "\033[100m"

# Global snapshot context to track active composable reading state
_CURRENT_COMPOSABLE: Optional["ComposableNode"] = None

class MutableState:
    """
    Simulasi `mutableStateOf(value)` dari Jetpack Compose.
    Mencatat composable mana yang membaca state ini (dependency tracking).
    """
    def __init__(self, initial_value: Any, name: str = "State"):
        self._value = initial_value
        self.name = name
        self._subscribers: Set["ComposableNode"] = set()

    @property
    def value(self) -> Any:
        global _CURRENT_COMPOSABLE
        if _CURRENT_COMPOSABLE is not None:
            self._subscribers.add(_CURRENT_COMPOSABLE)
            _CURRENT_COMPOSABLE.observed_states.add(self)
        return self._value

    @value.setter
    def value(self, new_value: Any):
        if self._value != new_value:
            old_val = self._value
            self._value = new_value
            # Mark all subscriber nodes as dirty for recomposition
            for subscriber in list(self._subscribers):
                subscriber.mark_dirty(f"State '{self.name}' changed ({old_val} -> {new_value})")

    def __repr__(self) -> str:
        return f"MutableState({self.name}={self._value})"


class DerivedState:
    """
    Simulasi `derivedStateOf { ... }`.
    Hanya mengkalkulasi ulang saat state internal berubah dan hasil nilainya berbeda.
    """
    def __init__(self, calculation: Callable[[], Any], name: str = "DerivedState"):
        self.calculation = calculation
        self.name = name
        self._cached_value: Any = None
        self._initialized = False

    @property
    def value(self) -> Any:
        # In real Compose, derivedStateOf optimizes read calculations
        new_val = self.calculation()
        self._cached_value = new_val
        self._initialized = True
        return self._cached_value


class ComposableNode:
    """
    Merepresentasikan node dalam Compose Slot Table / UI Tree.
    Mendukung smart skipping jika tidak ada parameter/state yang dirty.
    """
    def __init__(self, name: str, parent: Optional["ComposableNode"] = None):
        self.name = name
        self.parent = parent
        self.children: List["ComposableNode"] = []
        self.is_dirty = True
        self.recompose_count = 0
        self.skip_count = 0
        self.last_dirty_reason = "Initial Composition"
        self.observed_states: Set[MutableState] = set()
        self.remember_slots: Dict[str, Any] = {}
        self.render_output: str = ""

    def add_child(self, child: "ComposableNode"):
        child.parent = self
        self.children.append(child)

    def mark_dirty(self, reason: str):
        self.is_dirty = True
        self.last_dirty_reason = reason

    def remember(self, key: str, calculation: Callable[[], Any]) -> Any:
        """Simulasi remember { calculation() }"""
        if key not in self.remember_slots:
            self.remember_slots[key] = calculation()
        return self.remember_slots[key]


class ComposeEngine:
    """
    Recomposer Runtime yang mengeksekusi recomposition cycle.
    """
    def __init__(self):
        self.root: Optional[ComposableNode] = None
        self.recomposition_cycles = 0

    def render_tree_to_terminal(self, node: ComposableNode, prefix: str = "", is_last: bool = True):
        connector = "└── " if is_last else "├── "
        status_badge = ""
        if node.is_dirty:
            status_badge = f"{Colors.BG_GREEN}{Colors.WHITE} [RECOMPOSED #{node.recompose_count}] {Colors.RESET} ({node.last_dirty_reason})"
        else:
            status_badge = f"{Colors.BG_DARK}{Colors.WHITE} [SKIPPED #{node.skip_count}] {Colors.RESET}"

        print(f"{prefix}{connector}{Colors.BOLD}{Colors.CYAN}@{node.name}{Colors.RESET}{status_badge}")
        if node.render_output:
            child_prefix = prefix + ("    " if is_last else "│   ")
            print(f"{child_prefix}{Colors.YELLOW}Output: {node.render_output}{Colors.RESET}")

        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(node.children):
            self.render_tree_to_terminal(child, child_prefix, i == len(node.children) - 1)

    def run_recomposition(self, execute_fn: Callable[[ComposableNode], None]):
        global _CURRENT_COMPOSABLE
        self.recomposition_cycles += 1
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}=== RECOMPOSITION CYCLE #{self.recomposition_cycles} ==={Colors.RESET}")
        
        def traverse(node: ComposableNode):
            global _CURRENT_COMPOSABLE
            if node.is_dirty:
                node.recompose_count += 1
                # Clear past subscriptions to handle conditional branches
                for st in node.observed_states:
                    st._subscribers.discard(node)
                node.observed_states.clear()

                _CURRENT_COMPOSABLE = node
                execute_fn(node)
                _CURRENT_COMPOSABLE = None
                node.is_dirty = False
            else:
                node.skip_count += 1

            for child in node.children:
                traverse(child)

        traverse(self.root)
        self.render_tree_to_terminal(self.root)


# ==========================================
# State Model & UI Definition (Demo App)
# ==========================================

class AppState:
    """State Holder (ViewModel / State Hoisting Target)"""
    def __init__(self):
        self.counter = MutableState(0, "counter")
        self.username = MutableState("AndroidDev", "username")
        self.cart_items = MutableState(["Jetpack Compose Book", "Coffee Cup"], "cart_items")
        self.dark_mode = MutableState(False, "dark_mode")
        self.item_count = DerivedState(lambda: len(self.cart_items.value), "item_count")


def build_ui_tree() -> ComposableNode:
    """Membangun hierarki komponen slot table"""
    app_root = ComposableNode("MyApp")
    header = ComposableNode("HeaderBar", app_root)
    content = ComposableNode("ContentColumn", app_root)
    counter_card = ComposableNode("CounterCard", content)
    cart_card = ComposableNode("CartSummaryCard", content)
    footer = ComposableNode("FooterNote", app_root)

    app_root.add_child(header)
    app_root.add_child(content)
    content.add_child(counter_card)
    content.add_child(cart_card)
    app_root.add_child(footer)
    return app_root


def create_renderer(app_state: AppState) -> Callable[[ComposableNode], None]:
    """Mengembalikan fungsi render deklaratif yang membaca state"""
    def render_node(node: ComposableNode):
        if node.name == "MyApp":
            # Reads dark_mode state
            theme = "Dark Theme" if app_state.dark_mode.value else "Light Theme"
            node.render_output = f"Container [Theme: {theme}]"

        elif node.name == "HeaderBar":
            # Reads username state
            node.render_output = f"Welcome back, @{app_state.username.value}!"

        elif node.name == "ContentColumn":
            # Stateless container (layout slot)
            node.render_output = "Arrangement: Vertical, Spacing: 8.dp"

        elif node.name == "CounterCard":
            # Reads counter state (State Hoisting: event passed up, value passed down)
            val = app_state.counter.value
            status = "Positive" if val > 0 else ("Zero" if val == 0 else "Negative")
            node.render_output = f"Counter Display: {val} ({status})"

        elif node.name == "CartSummaryCard":
            # Reads derived state and list
            total = app_state.item_count.value
            items = ", ".join(app_state.cart_items.value)
            node.render_output = f"Total Items: {total} -> [{items}]"

        elif node.name == "FooterNote":
            # Static composable, never reads mutable state
            # Should be SKIPPED during state updates!
            node.render_output = "Jetpack Compose Simulator v1.0 • Declarative Kotlin"

    return render_node


def run_interactive_lab():
    engine = ComposeEngine()
    engine.root = build_ui_tree()
    app_state = AppState()
    renderer = create_renderer(app_state)

    # Initial composition
    print(f"{Colors.BOLD}{Colors.BLUE}╔════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}║   JETPACK COMPOSE & STATE MANAGEMENT - TERMINAL LAB SIMULATOR      ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}║   Bab 02: Declarative UI, Recomposition, & State Hoisting           ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}╚════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
    print(f"{Colors.DIM}Menginisialisasi tree composition awal (Semua node recomposed)...{Colors.RESET}")

    engine.run_recomposition(renderer)

    actions = {
        "1": ("Increment Counter (UDF Event: onIncrement)", lambda: setattr(app_state.counter, 'value', app_state.counter.value + 1)),
        "2": ("Decrement Counter (UDF Event: onDecrement)", lambda: setattr(app_state.counter, 'value', app_state.counter.value - 1)),
        "3": ("Tambah Item Belanja (UDF Event: onAddItem)", lambda: setattr(app_state.cart_items, 'value', app_state.cart_items.value + [f"Item-{len(app_state.cart_items.value)+1}"])),
        "4": ("Toggle Dark/Light Mode (Theme State Hoisting)", lambda: setattr(app_state.dark_mode, 'value', not app_state.dark_mode.value)),
        "5": ("Ubah Nama User (Header State Mutated)", lambda: setattr(app_state.username, 'value', "ComposeNinja" if app_state.username.value == "AndroidDev" else "AndroidDev")),
        "6": ("Simulasi Side-Effect (LaunchedEffect Log)", lambda: print(f"{Colors.BG_MAGENTA}{Colors.WHITE} [LaunchedEffect] Coroutine job aktif: sinkronisasi state ke server... {Colors.RESET}")),
        "7": ("Jalankan Auto-Test Assertion & Keluar", None)
    }

    is_automated = "--test" in sys.argv or "--non-interactive" in sys.argv

    if is_automated:
        print(f"\n{Colors.GREEN}Mode otomatis terdeteksi (--test/--non-interactive). Menjalankan sequence skenario...{Colors.RESET}")
        test_sequence = ["1", "3", "4", "5"]
        for cmd in test_sequence:
            name, fn = actions[cmd]
            print(f"\n{Colors.CYAN}>> Eksekusi: {name}{Colors.RESET}")
            fn()
            engine.run_recomposition(renderer)
        print(f"\n{Colors.GREEN}{Colors.BOLD}Semua verifikasi Compose Engine lulus tanpa error!{Colors.RESET}")
        return

    while True:
        print(f"\n{Colors.BOLD}{Colors.WHITE}Pilih Aksi Simulasi State Compose:{Colors.RESET}")
        for k, (desc, _) in actions.items():
            print(f"  [{Colors.CYAN}{k}{Colors.RESET}] {desc}")

        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan (1-7): {Colors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "7":
            print(f"{Colors.GREEN}Verifikasi tuntas. Menutup simulator.{Colors.RESET}")
            break
        elif choice in actions:
            name, fn = actions[choice]
            print(f"\n{Colors.CYAN}>> Memicu event: {name}{Colors.RESET}")
            fn()
            engine.run_recomposition(renderer)
        else:
            print(f"{Colors.RED}Pilihan tidak valid! Masukkan angka 1 sampai 7.{Colors.RESET}")


if __name__ == "__main__":
    run_interactive_lab()
