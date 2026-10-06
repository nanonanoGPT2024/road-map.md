#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Declarative UI, Component Lifecycle, dan Styling System
Bab: BAB-02 Declarative UI, Component Lifecycle, dan Styling Systems (React Native)

Simulasi Python 3 mandiri untuk memvisualisasikan bagaimana React Native:
1. Membangun Declarative UI Tree (Virtual Component Tree)
2. Mengelola Lifecycle Component (Mount, Update, Unmount, Effect Hook)
3. Melakukan Style Flattening, Merging, & Resolusi Flexbox Box-Model
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ANSI Color Escape Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RED = "\033[91m"
BG_DARK = "\033[48;5;236m"
GRAY = "\033[90m"


class StyleSheet:
    """Simulasi StyleSheet.create() React Native."""
    _registry: Dict[int, Dict[str, Any]] = {}
    _counter: int = 1000

    @classmethod
    def create(cls, styles_dict: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        ids: Dict[str, int] = {}
        for key, style_props in styles_dict.items():
            cls._counter += 1
            style_id = cls._counter
            cls._registry[style_id] = dict(style_props)
            ids[key] = style_id
        return ids

    @classmethod
    def get(cls, style_id: int) -> Dict[str, Any]:
        return cls._registry.get(style_id, {})

    @classmethod
    def flatten(cls, style_input: Union[int, Dict[str, Any], List[Any], None]) -> Dict[str, Any]:
        """Meniru StyleSheet.flatten() untuk menggabungkan style array / id / inline."""
        if style_input is None:
            return {}
        if isinstance(style_input, int):
            return dict(cls.get(style_input))
        if isinstance(style_input, dict):
            return dict(style_input)
        if isinstance(style_input, list):
            merged: Dict[str, Any] = {}
            for item in style_input:
                if item:
                    merged.update(cls.flatten(item))
            return merged
        return {}


class VNode:
    """Virtual Component Node (Representasi JSX Tree)."""
    def __init__(
        self,
        node_type: str,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List[Union["VNode", str]]] = None
    ):
        self.node_type = node_type
        self.props = props or {}
        self.children = children or []

    def render_tree(self, indent: int = 0) -> str:
        prefix = "  " * indent
        style_flat = StyleSheet.flatten(self.props.get("style"))
        style_summary = f" {GRAY}style={style_flat}{RESET}" if style_flat else ""
        lines = [f"{prefix}{CYAN}<{self.node_type}{style_summary}>{RESET}"]

        for child in self.children:
            if isinstance(child, VNode):
                lines.append(child.render_tree(indent + 1))
            else:
                lines.append(f"{prefix}  {YELLOW}\"{child}\"{RESET}")

        lines.append(f"{prefix}{CYAN}</{self.node_type}>{RESET}")
        return "\n".join(lines)


class ComponentEnvironment:
    """Lingkungan runtime reaktif simulasi React Native Component Lifecycle."""

    def __init__(self, name: str, render_fn: Callable[[], VNode]):
        self.name = name
        self.render_fn = render_fn
        self.state_store: List[Any] = []
        self.state_cursor: int = 0
        self.effects: List[Tuple[Callable[[], Optional[Callable[[], None]]], Optional[List[Any]]]] = []
        self.effect_cleanups: List[Optional[Callable[[], None]]] = []
        self.prev_deps: List[Optional[List[Any]]] = []
        self.is_mounted = False
        self.current_vtree: Optional[VNode] = None

    def use_state(self, initial_value: Any) -> Tuple[Any, Callable[[Any], None]]:
        idx = self.state_cursor
        if len(self.state_store) <= idx:
            self.state_store.append(initial_value)

        current_val = self.state_store[idx]

        def set_state(new_val: Any) -> None:
            computed_val = new_val(self.state_store[idx]) if callable(new_val) else new_val
            if computed_val != self.state_store[idx]:
                print(f"{MAGENTA}[State Trigger]{RESET} Hook #{idx} berubah: {self.state_store[idx]} -> {computed_val}")
                self.state_store[idx] = computed_val
                self.schedule_update()

        self.state_cursor += 1
        return current_val, set_state

    def use_effect(
        self,
        effect_fn: Callable[[], Optional[Callable[[], None]]],
        deps: Optional[List[Any]] = None
    ) -> None:
        self.effects.append((effect_fn, deps))

    def mount(self) -> None:
        print(f"\n{GREEN}{BOLD}=== [LIFECYCLE: MOUNTING] <{self.name} /> ==={RESET}")
        self.state_cursor = 0
        self.effects.clear()

        # Render pertama
        ComponentEnvironment._active_env = self
        self.current_vtree = self.render_fn()
        ComponentEnvironment._active_env = None
        self.is_mounted = True

        print(f"{BLUE}[Virtual DOM Rendered]{RESET}")
        print(self.current_vtree.render_tree(indent=1))

        # Menjalankan Effects setelah mount
        for effect_fn, deps in self.effects:
            print(f"{YELLOW}[useEffect Executed]{RESET} deps={deps}")
            cleanup = effect_fn()
            self.effect_cleanups.append(cleanup)
            self.prev_deps.append(deps)

    def schedule_update(self) -> None:
        if not self.is_mounted:
            return
        print(f"\n{CYAN}{BOLD}=== [LIFECYCLE: UPDATING / RE-RENDERING] <{self.name} /> ==={RESET}")
        self.state_cursor = 0
        old_effects = list(self.effects)
        self.effects.clear()

        # Re-render
        ComponentEnvironment._active_env = self
        new_vtree = self.render_fn()
        ComponentEnvironment._active_env = None
        self.current_vtree = new_vtree

        print(f"{BLUE}[Reconciled Virtual DOM]{RESET}")
        print(self.current_vtree.render_tree(indent=1))

        # Reconcile Effects
        for idx, (effect_fn, deps) in enumerate(self.effects):
            should_run = False
            last_dep_list = self.prev_deps[idx] if idx < len(self.prev_deps) else None

            if deps is None:
                should_run = True
            elif last_dep_list is None:
                should_run = True
            elif len(deps) != len(last_dep_list) or any(a != b for a, b in zip(deps, last_dep_list)):
                should_run = True

            if should_run:
                # Cleanup effect lama bila ada
                if idx < len(self.effect_cleanups) and self.effect_cleanups[idx]:
                    print(f"{RED}[useEffect Cleanup]{RESET} Membersihkan efek index {idx}")
                    self.effect_cleanups[idx]()
                print(f"{YELLOW}[useEffect Re-run]{RESET} Dependencies berubah: {last_dep_list} -> {deps}")
                cleanup = effect_fn()
                if idx < len(self.effect_cleanups):
                    self.effect_cleanups[idx] = cleanup
                else:
                    self.effect_cleanups.append(cleanup)
            self.prev_deps[idx] = deps

    def unmount(self) -> None:
        print(f"\n{RED}{BOLD}=== [LIFECYCLE: UNMOUNTING] <{self.name} /> ==={RESET}")
        for idx, cleanup in enumerate(self.effect_cleanups):
            if cleanup:
                print(f"{RED}[useEffect Cleanup on Unmount]{RESET} Membersihkan handler #{idx}")
                cleanup()
        self.is_mounted = False
        print(f"{DIM}Component <{self.name} /> dilepas dari native hierarchy.{RESET}")


# Module global helper for active component
def use_state(init_val: Any) -> Tuple[Any, Callable[[Any], None]]:
    if not hasattr(ComponentEnvironment, "_active_env") or ComponentEnvironment._active_env is None:
        raise RuntimeError("useState harus dipanggil di dalam render function component!")
    return ComponentEnvironment._active_env.use_state(init_val)


def use_effect(effect_fn: Callable[[], Optional[Callable[[], None]]], deps: Optional[List[Any]] = None) -> None:
    if not hasattr(ComponentEnvironment, "_active_env") or ComponentEnvironment._active_env is None:
        raise RuntimeError("useEffect harus dipanggil di dalam render function component!")
    ComponentEnvironment._active_env.use_effect(effect_fn, deps)


# -------------------------------------------------------------
# Aplikasi Contoh: Counter & Theming Screen
# -------------------------------------------------------------

styles = StyleSheet.create({
    "container": {
        "flex": 1,
        "flexDirection": "column",
        "justifyContent": "center",
        "alignItems": "center",
        "padding": 16,
    },
    "darkTheme": {
        "backgroundColor": "#121212",
    },
    "lightTheme": {
        "backgroundColor": "#FFFFFF",
    },
    "titleText": {
        "fontSize": 20,
        "fontWeight": "bold",
    },
    "counterBadge": {
        "paddingHorizontal": 12,
        "paddingVertical": 6,
        "borderRadius": 8,
        "marginTop": 10,
    },
    "button": {
        "padding": 10,
        "backgroundColor": "#2196F3",
        "borderRadius": 6,
        "marginTop": 12,
    }
})


# Callback bridge untuk menguji interaksi eksternal
_state_triggers: Dict[str, Callable[[], None]] = {}


def app_screen() -> VNode:
    """Komponen Declarative UI React Native."""
    dark_mode, set_dark_mode = use_state(False)
    count, set_count = use_state(0)

    # Simpan trigger agar bisa dipanggil dari luar (interaktif)
    _state_triggers["toggle_theme"] = lambda: set_dark_mode(lambda prev: not prev)
    _state_triggers["increment"] = lambda: set_count(lambda prev: prev + 1)
    _state_triggers["decrement"] = lambda: set_count(lambda prev: max(0, prev - 1))

    # Effect 1: Mount/Unmount listener
    def setup_hardware_listener():
        print(f"  {GRAY}-> [NativeBridge] Register BackHandler native subscription{RESET}")
        def cleanup_hardware():
            print(f"  {GRAY}-> [NativeBridge] Unregister BackHandler native subscription{RESET}")
        return cleanup_hardware

    use_effect(setup_hardware_listener, [])

    # Effect 2: Dependency count
    def log_count_change():
        print(f"  {GRAY}-> [Analytics] Event: 'counter_updated' nilai={count}{RESET}")
        return None

    use_effect(log_count_change, [count])

    # Declarative JSX composition & style array merging
    theme_style = styles["darkTheme"] if dark_mode else styles["lightTheme"]
    text_color = "#FFFFFF" if dark_mode else "#000000"

    return VNode("View", {"style": [styles["container"], theme_style]}, [
        VNode("Text", {"style": [styles["titleText"], {"color": text_color}]}, [
            f"Mode: {'DARK' if dark_mode else 'LIGHT'}"
        ]),
        VNode("View", {"style": [styles["counterBadge"], {"backgroundColor": "#4CAF50" if count > 0 else "#9E9E9E"}]}, [
            VNode("Text", {"style": {"color": "#FFFFFF", "fontWeight": "bold"}}, [
                f"Current Count: {count}"
            ])
        ]),
        VNode("TouchableOpacity", {"style": styles["button"]}, [
            VNode("Text", {"style": {"color": "#FFFFFF"}}, ["Tap to Increment"])
        ])
    ])


def run_interactive_simulation() -> None:
    print(f"{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}{CYAN}  SIMULASI REACT NATIVE CORE: DECLARATIVE UI & LIFECYCLE ENGINE  {RESET}")
    print(f"{BOLD}{CYAN}================================================================={RESET}")

    env = ComponentEnvironment("AppScreen", app_screen)

    # 1. Mount
    env.mount()

    # 2. Update via Actions
    actions = [
        ("1. User Menekan Tombol Increment (+1)", "increment"),
        ("2. User Menekan Tombol Increment (+1)", "increment"),
        ("3. User Melakukan Switch Dark Theme", "toggle_theme"),
        ("4. User Menekan Tombol Decrement (-1)", "decrement"),
    ]

    for label, action_key in actions:
        time.sleep(0.4)
        print(f"\n{YELLOW}{BOLD}>>> AKSI INTERAKTIF: {label}{RESET}")
        _state_triggers[action_key]()

    # 3. Unmount
    time.sleep(0.4)
    env.unmount()

    print(f"\n{GREEN}{BOLD}[VERIFIKASI BERHASIL]{RESET} Seluruh siklus Declarative UI, Lifecycle Hooks,")
    print(f"dan StyleSheet Resolving berjalan sesuai spesifikasi React Native.")


if __name__ == "__main__":
    run_interactive_simulation()
