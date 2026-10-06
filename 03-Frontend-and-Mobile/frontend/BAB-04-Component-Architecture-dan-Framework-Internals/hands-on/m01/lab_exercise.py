#!/usr/bin/env python3
"""
================================================================================
LAB EXERCISE M01: COMPONENT ARCHITECTURE & FRAMEWORK INTERNALS
Bab 04: Component Architecture dan Framework Internals
================================================================================
Simulasi teknis interaktif mengenai:
1. Virtual DOM (VNode) Tree Construction
2. Reactive Signal Engine (Dependency Tracking & Automatic Batching)
3. Fiber-like Hook Dispatcher & Lifecycle Emulation
4. Tree Reconciliation & DOM Patch Generation (Diffing Algorithm)
================================================================================
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# ANSI Color Codes for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RED = "\033[91m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN} [CORE LAB] {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{YELLOW}>>> {title}{RESET}")


def log_event(category: str, msg: str, color: str = GREEN) -> None:
    print(f"  {color}[{category.upper():^12}]{RESET} {msg}")


# ==============================================================================
# 1. REACTIVITY PRIMITIVE: SIGNALS & RUNTIME DEPENDENCY TRACKING
# ==============================================================================

_ACTIVE_EFFECT: Optional[Callable[[], None]] = None


class Signal:
    """Implementasi Fine-grained Reactivity (mirip Solid.js / Preact Signals)"""

    def __init__(self, value: Any, name: str = "unnamed"):
        self._val = value
        self.name = name
        self.subscribers: Set[Callable[[], None]] = set()

    def get(self) -> Any:
        global _ACTIVE_EFFECT
        if _ACTIVE_EFFECT is not None:
            self.subscribers.add(_ACTIVE_EFFECT)
            log_event(
                "Signal Track",
                f"Effect registered as dependency for {BOLD}'{self.name}'{RESET}",
                BLUE,
            )
        return self._val

    def set(self, new_val: Any) -> None:
        if self._val == new_val:
            return
        old = self._val
        self._val = new_val
        log_event(
            "Signal Write",
            f"'{self.name}': {old} -> {BOLD}{new_val}{RESET} (Notifying {len(self.subscribers)} deps)",
            MAGENTA,
        )
        self._notify()

    def _notify(self) -> None:
        for sub in list(self.subscribers):
            sub()


def create_effect(fn: Callable[[], None]) -> None:
    """Mengeksekusi efek dan mendaftarkannya ke sinyal yang diakses."""
    global _ACTIVE_EFFECT

    def run_effect() -> None:
        global _ACTIVE_EFFECT
        prev_effect = _ACTIVE_EFFECT
        _ACTIVE_EFFECT = run_effect
        try:
            fn()
        finally:
            _ACTIVE_EFFECT = prev_effect

    run_effect()


# ==============================================================================
# 2. VIRTUAL DOM & RECONCILIATION ENGINE
# ==============================================================================


@dataclass
class VNode:
    tag: str
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[Union["VNode", str]] = field(default_factory=list)
    key: Optional[str] = None

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        props_str = " ".join([f'{k}="{v}"' for k, v in self.props.items()])
        props_str = f" {props_str}" if props_str else ""
        key_str = f" [key={self.key}]" if self.key else ""

        res = [f"{indent}{CYAN}<{self.tag}{key_str}{props_str}>{RESET}"]
        for child in self.children:
            if isinstance(child, VNode):
                res.append(child.render_tree(depth + 1))
            else:
                res.append(f"{indent}  {GREEN}\"{child}\"{RESET}")
        res.append(f"{indent}{CYAN}</{self.tag}>{RESET}")
        return "\n".join(res)


@dataclass
class Patch:
    action: str  # REPLACE, REMOVE, INSERT, UPDATE_PROPS, TEXT
    node_path: str
    payload: Any


def diff(old_node: Optional[Union[VNode, str]], new_node: Optional[Union[VNode, str]], path: str = "root") -> List[Patch]:
    """Algoritma rekonsiliasi VNode yang menghasilkan list instruksi perubahan (patches)."""
    patches: List[Patch] = []

    # Node dihapus
    if new_node is None:
        if old_node is not None:
            patches.append(Patch("REMOVE", path, None))
        return patches

    # Node baru dimasukkan
    if old_node is None:
        patches.append(Patch("INSERT", path, new_node))
        return patches

    # Tipe berbeda (teks vs VNode)
    if isinstance(old_node, str) or isinstance(new_node, str):
        if old_node != new_node:
            patches.append(Patch("TEXT", path, new_node))
        return patches

    # Tag berbeda -> Replace seluruh subtree
    if old_node.tag != new_node.tag:
        patches.append(Patch("REPLACE", path, new_node))
        return patches

    # Cek perubahan props
    prop_changes: Dict[str, Any] = {}
    all_props = set(old_node.props.keys()).union(new_node.props.keys())
    for prop in all_props:
        old_val = old_node.props.get(prop)
        new_val = new_node.props.get(prop)
        if old_val != new_val:
            prop_changes[prop] = new_val

    if prop_changes:
        patches.append(Patch("UPDATE_PROPS", path, prop_changes))

    # Rekonsiliasi Children
    max_len = max(len(old_node.children), len(new_node.children))
    for i in range(max_len):
        child_path = f"{path} > child[{i}]"
        old_child = old_node.children[i] if i < len(old_node.children) else None
        new_child = new_node.children[i] if i < len(new_node.children) else None
        patches.extend(diff(old_child, new_child, child_path))

    return patches


# ==============================================================================
# 3. FIBER-STYLE HOOKS & COMPONENT RUNTIME
# ==============================================================================


class FiberRuntime:
    """Meniru Hooks state dispatcher berurutan seperti React Fiber."""

    def __init__(self) -> None:
        self.hook_states: List[Any] = []
        self.cursor: int = 0
        self.render_count: int = 0

    def reset_cursor(self) -> None:
        self.cursor = 0
        self.render_count += 1

    def use_state(self, initial_value: Any) -> Tuple[Any, Callable[[Any], None]]:
        idx = self.cursor
        if len(self.hook_states) <= idx:
            self.hook_states.append(initial_value)

        current_val = self.hook_states[idx]

        def set_state(new_value: Any) -> None:
            if callable(new_value):
                self.hook_states[idx] = new_value(self.hook_states[idx])
            else:
                self.hook_states[idx] = new_value
            log_event("Fiber State", f"Slot [{idx}] diubah -> {self.hook_states[idx]}", YELLOW)

        self.cursor += 1
        return current_val, set_state


# ==============================================================================
# 4. SIMULATION WORKFLOWS & DEMONSTRATION
# ==============================================================================


def simulate_reactive_signals() -> None:
    subheader("Simulasi 1: Fine-Grained Reactive Signals vs Re-rendering")
    print(f"{DIM}Signals mentracking dependensi secara otomatis saat getter dipanggil.{RESET}")

    count = Signal(0, name="counter")
    multiplier = Signal(2, name="multiplier")

    derived_log: List[int] = []

    def reactive_printer() -> None:
        total = count.get() * multiplier.get()
        derived_log.append(total)
        log_event("Reactive DOM", f"Rendered computed value: {count.get()} * {multiplier.get()} = {BOLD}{total}{RESET}")

    log_event("Setup", "Mendaftarkan create_effect...", BLUE)
    create_effect(reactive_printer)

    time.sleep(0.05)
    print(f"\n{BOLD}-> Menjalankan mutasi nilai sinyal:{RESET}")
    count.set(1)
    count.set(5)
    multiplier.set(10)


def simulate_vdom_diffing() -> None:
    subheader("Simulasi 2: Virtual DOM Reconciliation & Diffing Operations")

    tree_v1 = VNode(
        tag="div",
        props={"class": "card", "id": "main-card"},
        children=[
            VNode(tag="h1", children=["Dashboard Overview"]),
            VNode(
                tag="ul",
                props={"role": "list"},
                children=[
                    VNode(tag="li", props={"id": "item-1"}, children=["Item Alpha"]),
                    VNode(tag="li", props={"id": "item-2"}, children=["Item Beta"]),
                ],
            ),
            VNode(tag="button", props={"disabled": True}, children=["Submit"]),
        ],
    )

    print(f"{BOLD}[Initial VNode Tree v1]{RESET}")
    print(tree_v1.render_tree())

    tree_v2 = VNode(
        tag="div",
        props={"class": "card active", "id": "main-card"},
        children=[
            VNode(tag="h1", children=["Dashboard Overview (Live)"]),
            VNode(
                tag="ul",
                props={"role": "list"},
                children=[
                    VNode(tag="li", props={"id": "item-1"}, children=["Item Alpha"]),
                    VNode(tag="li", props={"id": "item-2"}, children=["Item Beta Updated"]),
                    VNode(tag="li", props={"id": "item-3"}, children=["Item Gamma Baru"]),
                ],
            ),
            VNode(tag="button", props={"disabled": False, "class": "btn-primary"}, children=["Submit Now"]),
        ],
    )

    print(f"\n{BOLD}[Updated VNode Tree v2]{RESET}")
    print(tree_v2.render_tree())

    log_event("Diffing", "Menghitung delta perubahan antara v1 dan v2...", BLUE)
    patches = diff(tree_v1, tree_v2)

    print(f"\n{BOLD}{GREEN}=== HASIL PATCHES YANG DIKIRIM KE REAL DOM BROWSER ({len(patches)} Instruksi) ==={RESET}")
    for idx, p in enumerate(patches, 1):
        color = GREEN if p.action in ("INSERT", "UPDATE_PROPS") else YELLOW
        print(f"  {idx}. {color}{p.action:<14}{RESET} di path {CYAN}{p.node_path:<26}{RESET} -> payload: {p.payload}")


def simulate_fiber_runtime() -> None:
    subheader("Simulasi 3: Fiber Hook Dispatcher & Lifecycle Ordering")
    fiber = FiberRuntime()

    def render_my_component() -> VNode:
        fiber.reset_cursor()
        count, set_count = fiber.use_state(10)
        user, set_user = fiber.use_state("Alice")

        return VNode(
            tag="section",
            props={"data-render": str(fiber.render_count)},
            children=[
                VNode(tag="span", children=[f"User: {user}"]),
                VNode(tag="span", children=[f"Score: {count}"]),
            ],
        )

    print("Render 1:")
    c1 = render_my_component()
    print(c1.render_tree(1))

    # Simulasi mutasi state
    log_event("Action", "User mengklik tombol penambah score (+5)...", MAGENTA)
    _, set_count = fiber.use_state(10)  # Reference dummy
    fiber.hook_states[0] += 5

    print("\nRender 2 (Post State Mutation):")
    c2 = render_my_component()
    print(c2.render_tree(1))


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================


def main() -> None:
    header("Frontend Core Architecture & Framework Internals Simulator")
    print(f"{DIM}Interactive Diagnostic & Emulation Engine (Python 3 Runnable){RESET}")

    simulate_reactive_signals()
    simulate_vdom_diffing()
    simulate_fiber_runtime()

    print(f"\n{BOLD}{GREEN}[SUCCESS]{RESET} Seluruh rangkaian demonstrasi arsitektur frontend tuntas dieksekusi!\n")


if __name__ == "__main__":
    main()
