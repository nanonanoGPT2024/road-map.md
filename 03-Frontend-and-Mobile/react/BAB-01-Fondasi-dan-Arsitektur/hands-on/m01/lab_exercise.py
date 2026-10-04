#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Mandiri Fondasi & Arsitektur React
- Virtual DOM Tree Representation
- VDOM Diffing & Patch Engine (Reconciliation)
- Hook Simulation (useState & Component Lifecycle)
- Commit Phase & Batching Execution
"""

import sys
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Callable

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"

class VNode:
    """Representasi Node Virtual DOM (Mirip React.createElement)"""
    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None, children: Optional[List[Any]] = None):
        self.tag = tag
        self.props = props or {}
        self.children = children or []

    def to_dict(self) -> Dict[str, Any]:
        rendered_children = []
        for c in self.children:
            if isinstance(c, VNode):
                rendered_children.append(c.to_dict())
            else:
                rendered_children.append(str(c))
        return {
            "type": self.tag,
            "props": self.props,
            "children": rendered_children
        }

    def print_tree(self, indent: int = 0) -> str:
        prefix = "  " * indent
        props_str = f" {CYAN}{json.dumps(self.props)}{RESET}" if self.props else ""
        lines = [f"{prefix}{BOLD}<{self.tag}>{RESET}{props_str}"]
        for c in self.children:
            if isinstance(c, VNode):
                lines.append(c.print_tree(indent + 1))
            else:
                lines.append(f"{prefix}  {YELLOW}\"{c}\"{RESET}")
        lines.append(f"{prefix}{BOLD}</{self.tag}>{RESET}")
        return "\n".join(lines)


class DiffType:
    CREATE = "CREATE"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"
    UPDATE_PROPS = "UPDATE_PROPS"
    CHILDREN = "CHILDREN"


class Patch:
    """Instruksi mutasi Real DOM yang dihasilkan dari reconciler"""
    def __init__(self, diff_type: str, path: str, old_val: Any = None, new_val: Any = None):
        self.diff_type = diff_type
        self.path = path
        self.old_val = old_val
        self.new_val = new_val

    def __repr__(self) -> str:
        if self.diff_type == DiffType.CREATE:
            return f"[{GREEN}+ CREATE{RESET}] At '{self.path}': Tambah node baru -> {self.new_val}"
        elif self.diff_type == DiffType.REMOVE:
            return f"[{RED}- REMOVE{RESET}] At '{self.path}': Hapus node lama -> {self.old_val}"
        elif self.diff_type == DiffType.REPLACE:
            return f"[{MAGENTA}~ REPLACE{RESET}] At '{self.path}': Ganti '{self.old_val}' dengan '{self.new_val}'"
        elif self.diff_type == DiffType.UPDATE_PROPS:
            return f"[{BLUE}* PROPS{RESET}] At '{self.path}': Props berubah: {self.old_val} -> {self.new_val}"
        return f"[{CYAN}CHILDREN{RESET}] At '{self.path}'"


class ReactEngine:
    """Mini Reconciler & Fiber Execution Engine"""
    def __init__(self):
        self._current_vdom: Optional[VNode] = None
        self._hook_states: List[Any] = []
        self._hook_index: int = 0
        self._root_component: Optional[Callable[[], VNode]] = None
        self._patch_history: List[List[Patch]] = []

    def use_state(self, initial_value: Any) -> Tuple[Any, Callable[[Any], None]]:
        idx = self._hook_index
        if len(self._hook_states) <= idx:
            self._hook_states.append(initial_value)

        current_val = self._hook_states[idx]

        def set_state(new_value: Any):
            if callable(new_value):
                self._hook_states[idx] = new_value(self._hook_states[idx])
            else:
                self._hook_states[idx] = new_value
            self._schedule_render()

        self._hook_index += 1
        return current_val, set_state

    def mount(self, component: Callable[[], VNode]):
        print(f"\n{BOLD}{GREEN}=== [MOUNT] Initial Rendering Phase ==={RESET}")
        self._root_component = component
        self._hook_index = 0
        new_vdom = component()
        self._current_vdom = new_vdom

        print(f"{BLUE}Virtual DOM Terbentuk:{RESET}")
        print(new_vdom.print_tree(indent=1))
        print(f"{GREEN}[Commit Phase] Memasang seluruh struktur ke Real DOM.{RESET}")

    def _schedule_render(self):
        print(f"\n{BOLD}{MAGENTA}=== [STATE CHANGE] Triggering Reconciliation Loop ==={RESET}")
        self._hook_index = 0
        new_vdom = self._root_component()

        # Render Phase: Diffing (kalkulasi perubahan tanpa menyentuh DOM)
        patches = self._diff(self._current_vdom, new_vdom, path="root")
        self._patch_history.append(patches)

        print(f"\n{BOLD}{YELLOW}[1. Render Phase - Diffing Virtual DOM]:{RESET}")
        if not patches:
            print(f"  {DIM}Tidak ada perbedaan terdeteksi. Bailing out render.{RESET}")
        else:
            for p in patches:
                print(f"  {p}")

        # Commit Phase: Menerapkan patch hasil diffing
        print(f"\n{BOLD}{GREEN}[2. Commit Phase - Mutasi Real DOM Minimum]:{RESET}")
        print(f"  Menerapkan total {len(patches)} operasi mutasi terisolasi ke DOM host...")
        self._current_vdom = new_vdom

        print(f"\n{BLUE}Pohon Virtual DOM Terkini:{RESET}")
        print(new_vdom.print_tree(indent=1))

    def _diff(self, old_node: Any, new_node: Any, path: str) -> List[Patch]:
        patches: List[Patch] = []

        if old_node is None and new_node is not None:
            val = new_node.tag if isinstance(new_node, VNode) else new_node
            patches.append(Patch(DiffType.CREATE, path, new_val=val))
            return patches

        if old_node is not None and new_node is None:
            val = old_node.tag if isinstance(old_node, VNode) else old_node
            patches.append(Patch(DiffType.REMOVE, path, old_val=val))
            return patches

        # Perbandingan teks/literal child
        if not isinstance(old_node, VNode) and not isinstance(new_node, VNode):
            if old_node != new_node:
                patches.append(Patch(DiffType.REPLACE, path, old_val=old_node, new_val=new_node))
            return patches

        # Salah satu ganti tipe (teks ke VNode atau sebaliknya)
        if isinstance(old_node, VNode) != isinstance(new_node, VNode):
            patches.append(Patch(DiffType.REPLACE, path, old_val=old_node, new_val=new_node))
            return patches

        # Tag berbeda: unmount lama & mount baru
        if old_node.tag != new_node.tag:
            patches.append(Patch(DiffType.REPLACE, path, old_val=old_node.tag, new_val=new_node.tag))
            return patches

        # Cek perbedaan props
        if old_node.props != new_node.props:
            patches.append(Patch(DiffType.UPDATE_PROPS, path, old_val=old_node.props, new_val=new_node.props))

        # Diffing Children
        max_len = max(len(old_node.children), len(new_node.children))
        for i in range(max_len):
            old_child = old_node.children[i] if i < len(old_node.children) else None
            new_child = new_node.children[i] if i < len(new_node.children) else None
            child_path = f"{path} > {old_node.tag}[{i}]"
            patches.extend(self._diff(old_child, new_child, child_path))

        return patches


# Instance runtime global engine
engine = ReactEngine()

# State holders untuk interaksi manual di lab
class AppState:
    set_count: Optional[Callable] = None
    set_theme: Optional[Callable] = None
    set_items: Optional[Callable] = None

app_state = AppState()

def App() -> VNode:
    """Komponen Representasi Aplikasi Simulasi"""
    count, set_count = engine.use_state(0)
    theme, set_theme = engine.use_state("dark")
    items, set_items = engine.use_state(["Virtual DOM", "Fiber Architecture"])

    app_state.set_count = set_count
    app_state.set_theme = set_theme
    app_state.set_items = set_items

    item_nodes = [
        VNode("li", {"key": f"item-{idx}"}, [text])
        for idx, text in enumerate(items)
    ]

    return VNode("div", {"id": "app-container", "class": f"theme-{theme}"}, [
        VNode("header", {}, [
            VNode("h1", {}, ["React Architecture Lab (BAB-01)"]),
            VNode("span", {"class": "badge"}, [f"Mode: {theme.upper()}"])
        ]),
        VNode("main", {}, [
            VNode("section", {"id": "counter-box"}, [
                VNode("p", {}, [f"Counter State: {count}"]),
                VNode("p", {"class": "hint"}, ["Status: " + ("Genap" if count % 2 == 0 else "Ganjil")])
            ]),
            VNode("section", {"id": "list-box"}, [
                VNode("h3", {}, ["Pilar Fondasi React:"]),
                VNode("ul", {}, item_nodes)
            ])
        ])
    ])


def print_banner():
    print(f"""{CYAN}{BOLD}
============================================================
  LAB EXERCISE M01: SIMULATOR FONDASI & ARSITEKTUR REACT
  Konsep: VDOM, Fiber Reconciler, Diffing & State Lifecycle
============================================================{RESET}
{DIM}Simulasi ini membedah bagaimana React meminimalisir interaksi
DOM asli melalui reconciler tree-diffing.{RESET}
""")


def interactive_menu():
    print(f"\n{BOLD}Pilih Aksi Interaktif:{RESET}")
    print(f"  {CYAN}[1]{RESET} Increment Counter (Modifikasi text node child)")
    print(f"  {CYAN}[2]{RESET} Toggle Theme 'light'/'dark' (Modifikasi container props)")
    print(f"  {CYAN}[3]{RESET} Tambah Pilar Fondasi Baru (Modifikasi list children)")
    print(f"  {CYAN}[4]{RESET} Reset Seluruh State")
    print(f"  {RED}[0]{RESET} Keluar")


def main():
    print_banner()
    engine.mount(App)

    # Mode interaktif atau non-interactive run (CI/automated execution)
    if not sys.stdin.isatty():
        print(f"\n{YELLOW}[Non-Interactive Environment Terdeteksi]{RESET}")
        print("Menjalankan skenario otomatis demonstrasi lifecycle...")
        
        print("\n--> Skenario 1: Increment State Counter")
        app_state.set_count(lambda c: c + 1)
        
        print("\n--> Skenario 2: Update Tema Props")
        app_state.set_theme(lambda t: "light" if t == "dark" else "dark")

        print("\n--> Skenario 3: Tambah Item List Baru")
        app_state.set_items(lambda it: it + ["Reconciliation Diff"])

        print(f"\n{GREEN}{BOLD}Demonstrasi Reconciler Berhasil 100%.{RESET}\n")
        return

    while True:
        interactive_menu()
        try:
            choice = input(f"\n{YELLOW}Pilihan Anda (0-4): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            app_state.set_count(lambda c: c + 1)
        elif choice == "2":
            app_state.set_theme(lambda t: "light" if t == "dark" else "dark")
        elif choice == "3":
            new_item = input("Masukkan nama pilar/fitur baru: ").strip() or "Concurrent Renderer"
            app_state.set_items(lambda it: it + [new_item])
        elif choice == "4":
            app_state.set_count(0)
            app_state.set_theme("dark")
            app_state.set_items(["Virtual DOM", "Fiber Architecture"])
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")

if __name__ == "__main__":
    main()
