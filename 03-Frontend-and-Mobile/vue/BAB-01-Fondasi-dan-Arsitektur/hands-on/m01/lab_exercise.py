#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi dan Arsitektur Inti Vue 3
=============================================================
Topik:
  1. Sistem Reaktivitas (Dependency Tracking: track, trigger, effect, ref, reactive)
  2. Virtual DOM & Diff/Patch Engine Sederhana
  3. Siklus Hidup Komponen (Lifecycle Hooks)
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union


# ============================================================================
# ANSI Color Formatting Helpers
# ============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"


def header(text: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}  {text}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 65}{Color.RESET}")


def log_event(module: str, msg: str, color: str = Color.GREEN) -> None:
    print(f"{Color.DIM}[{time.strftime('%H:%M:%S')}]{Color.RESET} {color}[{module}]{Color.RESET} {msg}")


# ============================================================================
# 1. Vue 3 Reactivity Engine (Simulasi Dependency Injection & Proxy Interceptor)
# ============================================================================
active_effect: Optional[Callable[[], Any]] = None
target_map: Dict[Any, Dict[str, Set[Callable[[], Any]]]] = {}


def track(target: Any, key: str) -> None:
    """Mengaitkan efek aktif ke dependency (target.key)."""
    if active_effect is None:
        return

    deps_map = target_map.setdefault(target, {})
    dep = deps_map.setdefault(key, set())
    if active_effect not in dep:
        dep.add(active_effect)
        log_event(
            "Reactivity.track",
            f"Dep terdaftar: property '{Color.YELLOW}{key}{Color.RESET}' dipantau oleh effect()",
            Color.BLUE,
        )


def trigger(target: Any, key: str) -> None:
    """Menjalankan semua effect yang bergantung pada property target.key."""
    deps_map = target_map.get(target)
    if not deps_map:
        return
    dep = deps_map.get(key)
    if not dep:
        return

    log_event(
        "Reactivity.trigger",
        f"Mutasi pada '{Color.YELLOW}{key}{Color.RESET}' -> Mengeksekusi {len(dep)} listener effect",
        Color.MAGENTA,
    )
    # Buat salinan set agar mutasi selama iterasi aman
    effects_to_run = list(dep)
    for effect_fn in effects_to_run:
        effect_fn()


def effect(fn: Callable[[], Any]) -> Callable[[], Any]:
    """Membungkus fungsi render/watch dalam execution context reaktif."""

    def reactive_runner():
        global active_effect
        try:
            active_effect = reactive_runner
            return fn()
        finally:
            active_effect = None

    reactive_runner()
    return reactive_runner


class ReactiveDict(dict):
    """Simulasi Proxy object di JavaScript untuk intercept get/set."""

    def __getitem__(self, key: str) -> Any:
        track(self, key)
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: Any) -> None:
        old_val = self.get(key)
        if old_val != value:
            super().__setitem__(key, value)
            trigger(self, key)


def reactive(obj: dict) -> ReactiveDict:
    return ReactiveDict(obj)


class Ref:
    """Simulasi Ref object (primitives container dengan .value accessor)."""

    def __init__(self, value: Any):
        self._value = value

    @property
    def value(self) -> Any:
        track(self, "value")
        return self._value

    @value.setter
    def value(self, new_val: Any) -> None:
        if self._value != new_val:
            self._value = new_val
            trigger(self, "value")

    def __repr__(self) -> str:
        return f"Ref<{self._value}>"


def ref(value: Any) -> Ref:
    return Ref(value)


# ============================================================================
# 2. Virtual DOM (VNode) & Algoritma Diffing / Patching Sederhana
# ============================================================================
class VNode:

    def __init__(
        self,
        tag: str,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[Union[str, List["VNode"]]] = None,
    ):
        self.tag = tag
        self.props = props or {}
        self.children = children or []

    def to_html(self, indent: int = 0) -> str:
        pad = "  " * indent
        prop_str = " ".join([f'{k}="{v}"' for k, v in self.props.items()])
        attr_part = f" {prop_str}" if prop_str else ""

        if isinstance(self.children, str):
            return f"{pad}<{self.tag}{attr_part}>{self.children}</{self.tag}>"

        inner = "\n".join([c.to_html(indent + 1) for c in self.children])
        return f"{pad}<{self.tag}{attr_part}>\n{inner}\n{pad}</{self.tag}>"


def h(
    tag: str,
    props: Optional[Dict[str, Any]] = None,
    children: Optional[Union[str, List[VNode]]] = None,
) -> VNode:
    """Helper hyperscript untuk membangun Virtual DOM tree."""
    return VNode(tag, props, children)


def diff(old_node: Optional[VNode], new_node: Optional[VNode]) -> List[str]:
    """Menghasilkan representasi patch operations perubahan UI."""
    patches: List[str] = []

    if old_node is None and new_node is not None:
        patches.append(f"CREATE: <{new_node.tag}>")
        return patches
    if old_node is not None and new_node is None:
        patches.append(f"REMOVE: <{old_node.tag}>")
        return patches

    assert old_node is not None and new_node is not None

    if old_node.tag != new_node.tag:
        patches.append(f"REPLACE: <{old_node.tag}> dengan <{new_node.tag}>")
        return patches

    # Prop updates
    all_keys = set(old_node.props.keys()).union(new_node.props.keys())
    for k in all_keys:
        if k not in new_node.props:
            patches.append(f"REMOVE_PROP [{old_node.tag}]: {k}")
        elif old_node.props.get(k) != new_node.props.get(k):
            patches.append(
                f"UPDATE_PROP [{new_node.tag}]: {k}='{new_node.props[k]}'"
            )

    # Children updates
    if isinstance(old_node.children, str) and isinstance(new_node.children, str):
        if old_node.children != new_node.children:
            patches.append(
                f"UPDATE_TEXT [{new_node.tag}]: '{old_node.children}' -> '{new_node.children}'"
            )
    elif isinstance(old_node.children, list) and isinstance(
        new_node.children, list
    ):
        max_len = max(len(old_node.children), len(new_node.children))
        for i in range(max_len):
            child_old = old_node.children[i] if i < len(old_node.children) else None
            child_new = new_node.children[i] if i < len(new_node.children) else None
            patches.extend(diff(child_old, child_new))
    elif old_node.children != new_node.children:
        patches.append(f"STRUCTURAL_CHANGE_CHILDREN [{new_node.tag}]")

    return patches


# ============================================================================
# 3. Component Architecture & Lifecycle Mount Pipeline
# ============================================================================
class VueComponent:

    def __init__(self, name: str):
        self.name = name
        self.is_mounted = False
        self._current_vnode: Optional[VNode] = None

    def before_create(self) -> None:
        log_event(f"Lifecycle:{self.name}", "hook -> beforeCreate()", Color.CYAN)

    def created(self) -> None:
        log_event(f"Lifecycle:{self.name}", "hook -> created() (State terinisialisasi)", Color.CYAN)

    def before_mount(self) -> None:
        log_event(f"Lifecycle:{self.name}", "hook -> beforeMount() (Template ter-compile ke VNode)", Color.CYAN)

    def mounted(self) -> None:
        log_event(f"Lifecycle:{self.name}", "hook -> mounted() (DOM fisik tersambung)", Color.GREEN)

    def before_update(self) -> None:
        log_event(f"Lifecycle:{self.name}", "hook -> beforeUpdate() (Perubahan state terdeteksi)", Color.YELLOW)

    def updated(self) -> None:
        log_event(f"Lifecycle:{self.name}", "hook -> updated() (VTree re-patched ke DOM)", Color.YELLOW)

    def setup(self) -> Dict[str, Any]:
        """Didefinisikan oleh turunan komponen."""
        return {}

    def render(self, state: Dict[str, Any]) -> VNode:
        """Menghasilkan VNode berdasarkan state saat ini."""
        raise NotImplementedError


class CounterApp(VueComponent):

    def __init__(self):
        super().__init__("CounterApp")
        self.before_create()
        self.state = self.setup()
        self.created()

    def setup(self) -> Dict[str, Any]:
        count = ref(0)
        user = reactive({"name": "Developer Vue", "role": "Fullstack"})
        return {"count": count, "user": user}

    def render(self, state: Dict[str, Any]) -> VNode:
        count_val = state["count"].value
        user_name = state["user"]["name"]
        status_color = "red" if count_val >= 5 else "green"

        return h("div", {"id": "app", "class": "container"}, [
            h("h1", {"class": "title"}, f"Halo, {user_name}!"),
            h("div", {"class": f"badge badge-{status_color}"}, [
                h("span", {}, f"Counter Value: {count_val}")
            ]),
            h("p", {"class": "hint"}, "Reactivity Proxy memicu Diffing Engine secara otomatis.")
        ])


def mount_app(component: VueComponent) -> None:
    """Menggerakkan pipeline Reaktif & Render effect loop."""
    component.before_mount()

    def component_update_effect():
        new_vnode = component.render(component.state)
        if not component.is_mounted:
            log_event("Mount", "Inisialisasi Virtual DOM tree awal:", Color.GREEN)
            print(f"{Color.DIM}{new_vnode.to_html(1)}{Color.RESET}\n")
            component._current_vnode = new_vnode
            component.is_mounted = True
            component.mounted()
        else:
            component.before_update()
            log_event("Patch", "Menghitung delta perubahan VNode...", Color.YELLOW)
            patches = diff(component._current_vnode, new_vnode)
            for p in patches:
                print(f"  {Color.BOLD}{Color.YELLOW}-> {p}{Color.RESET}")
            component._current_vnode = new_vnode
            component.updated()
            print(f"\n{Color.DIM}DOM Baru:{Color.RESET}\n{Color.DIM}{new_vnode.to_html(1)}{Color.RESET}\n")

    effect(component_update_effect)


# ============================================================================
# Interactive CLI Runner
# ============================================================================
def run_interactive_demo():
    header("VUE 3 CORE ENGINE SIMULATION (BAB-01)")
    print(f"{Color.BOLD}Simulasi teknis mandiri konsep Reaktivitas & Virtual DOM.{Color.RESET}\n")

    app = CounterApp()
    mount_app(app)

    while True:
        print(f"\n{Color.BOLD}PILIH TINDAKAN SIMULASI:{Color.RESET}")
        print("  1. Tambah Counter (Mutasi Ref: count.value += 1)")
        print("  2. Kurang Counter (Mutasi Ref: count.value -= 1)")
        print("  3. Ubah Nama User (Mutasi Reactive Dict: user['name'] = ...)")
        print("  4. Mutasi Masif (Multiple triggers dalam 1 batch)")
        print("  5. Keluar")

        choice = input(f"\n{Color.CYAN}Pilihan Anda [1-5]: {Color.RESET}").strip()

        if choice == "1":
            print(f"\n{Color.BOLD}>> Mengeksekusi: count.value += 1{Color.RESET}")
            app.state["count"].value += 1
        elif choice == "2":
            print(f"\n{Color.BOLD}>> Mengeksekusi: count.value -= 1{Color.RESET}")
            app.state["count"].value -= 1
        elif choice == "3":
            new_name = input(f"{Color.YELLOW}Masukkan nama baru: {Color.RESET}").strip()
            if new_name:
                print(f"\n{Color.BOLD}>> Mengeksekusi: user['name'] = '{new_name}'{Color.RESET}")
                app.state["user"]["name"] = new_name
        elif choice == "4":
            print(f"\n{Color.BOLD}>> Mengeksekusi mutasi beruntun:{Color.RESET}")
            app.state["count"].value = 10
            app.state["user"]["name"] = "Lead Architect"
        elif choice == "5" or choice.lower() == "q":
            print(f"\n{Color.GREEN}Simulasi selesai. Fondasi reaktivitas terbukti!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, coba lagi.{Color.RESET}")


if __name__ == "__main__":
    try:
        run_interactive_demo()
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Program dihentikan oleh user.{Color.RESET}")
        sys.exit(0)
