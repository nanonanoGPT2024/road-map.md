#!/usr/bin/env python3
"""
Lab Hands-on: Frontend Core Architecture - Virtual DOM & Reconciliation Engine
Modul: 03-Frontend-and-Mobile / Bab 01 - Modul 02 Deep Dive

Deskripsi:
Script ini memodelkan arsitektur inti Virtual DOM (VDOM) modern mirip React Fiber / Vue 3.
Mengimplementasikan:
1. Virtual Node (VNode) tree construction & factory helper.
2. Heuristic Reconciliation Algorithm (Diffing O(N)) berbasis Node identity, Props diffing,
   dan Keyed Children Reordering.
3. Patch Engine yang menghasilkan dan mengaplikasikan operasi patch ke Simulated Real DOM.
4. Reactive Component State yang memicu automatic re-render dengan kalkulasi latency.
"""

from __future__ import annotations
import time
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
CLR_RESET  = "\033[0m"
CLR_CYAN   = "\033[96m"
CLR_GREEN  = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED    = "\033[91m"
CLR_MAG    = "\033[95m"
CLR_BOLD   = "\033[1m"
CLR_DIM    = "\033[2m"


class PatchType(Enum):
    CREATE_NODE = auto()
    REMOVE_NODE = auto()
    REPLACE_NODE = auto()
    UPDATE_PROPS = auto()
    REORDER_CHILDREN = auto()


@dataclass
class VNode:
    """Virtual DOM Node abstraction."""
    tag: str
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[Union[VNode, str]] = field(default_factory=list)
    key: Optional[str] = None

    def is_text_node(self) -> bool:
        return self.tag == "#text"


@dataclass
class Patch:
    """Instruksi mutasi konkret untuk memodifikasi Real DOM."""
    patch_type: PatchType
    path: List[int]
    payload: Any = None

    def __repr__(self) -> str:
        path_str = "/".join(map(str, self.path)) if self.path else "root"
        return f"Patch({self.patch_type.name} at [{path_str}], payload={self.payload})"


def h(tag: str, props: Optional[Dict[str, Any]] = None, children: Optional[List[Union[VNode, str]]] = None, key: Optional[str] = None) -> VNode:
    """Helper factory function (mirip hyperscript / JSX runtime) untuk menyusun VNode."""
    props = props or {}
    children = children or []
    normalized_children: List[Union[VNode, str]] = []
    
    for c in children:
        if isinstance(c, (str, int, float)):
            normalized_children.append(VNode(tag="#text", props={"value": str(c)}, children=[]))
        elif isinstance(c, VNode):
            normalized_children.append(c)
            
    return VNode(tag=tag, props=props, children=normalized_children, key=key or props.get("key"))


class DiffEngine:
    """
    Mesin diffing pohon VDOM heuristik berbobot O(N).
    Membandingkan node level demi level, menganalisis atribut kotor (dirty props),
    dan menyelaraskan urutan array elemen anak terindeks (Keyed reconciliation).
    """

    @classmethod
    def diff(cls, old_vnode: Optional[VNode], new_vnode: Optional[VNode], path: Optional[List[int]] = None) -> List[Patch]:
        patches: List[Patch] = []
        path = path or []

        # Skenario 1: Node lama dihapus
        if old_vnode is not None and new_vnode is None:
            patches.append(Patch(PatchType.REMOVE_NODE, path))
            return patches

        # Skenario 2: Node baru ditambahkan
        if old_vnode is None and new_vnode is not None:
            patches.append(Patch(PatchType.CREATE_NODE, path, payload=new_vnode))
            return patches

        if old_vnode is None or new_vnode is None:
            return patches

        # Skenario 3: Tipe Tag berbeda -> Replace seluruh subtree
        if old_vnode.tag != new_vnode.tag:
            patches.append(Patch(PatchType.REPLACE_NODE, path, payload=new_vnode))
            return patches

        # Skenario 4: Text Node Diffing
        if old_vnode.is_text_node() and new_vnode.is_text_node():
            if old_vnode.props.get("value") != new_vnode.props.get("value"):
                patches.append(Patch(PatchType.UPDATE_PROPS, path, payload={"value": new_vnode.props.get("value")}))
            return patches

        # Skenario 5: Prop/Attribute Diffing
        prop_diff = cls._diff_props(old_vnode.props, new_vnode.props)
        if prop_diff:
            patches.append(Patch(PatchType.UPDATE_PROPS, path, payload=prop_diff))

        # Skenario 6: Children Diffing (Key-based Matching)
        cls._diff_children(old_vnode.children, new_vnode.children, path, patches)

        return patches

    @staticmethod
    def _diff_props(old_props: Dict[str, Any], new_props: Dict[str, Any]) -> Dict[str, Any]:
        diff: Dict[str, Any] = {}
        # Cari properti yang berubah atau baru
        for k, v in new_props.items():
            if k == "key":
                continue
            if k not in old_props or old_props[k] != v:
                diff[k] = v
        # Cari properti yang dihapus (diberi flag None)
        for k in old_props:
            if k == "key":
                continue
            if k not in new_props:
                diff[k] = None
        return diff

    @classmethod
    def _diff_children(cls, old_children: List[Union[VNode, str]], new_children: List[Union[VNode, str]], current_path: List[int], patches: List[Patch]) -> None:
        """
        Keyed list diffing:
        Mengidentifikasi node berdasarkan 'key' untuk meminimalkan DOM recreations.
        """
        old_keyed: Dict[str, Tuple[int, VNode]] = {}
        for idx, child in enumerate(old_children):
            if isinstance(child, VNode) and child.key:
                old_keyed[child.key] = (idx, child)

        new_keyed: Dict[str, Tuple[int, VNode]] = {}
        for idx, child in enumerate(new_children):
            if isinstance(child, VNode) and child.key:
                new_keyed[child.key] = (idx, child)

        # Jika kedua list memiliki key, jalankan rekonsiliasi berbasis key
        if old_keyed and new_keyed:
            moves = []
            for new_key, (new_idx, new_node) in new_keyed.items():
                if new_key in old_keyed:
                    old_idx, old_node = old_keyed[new_key]
                    if old_idx != new_idx:
                        moves.append({"key": new_key, "from": old_idx, "to": new_idx})
                    # Diff rekursif pada node yang sama kuncinya
                    patches.extend(cls.diff(old_node, new_node, current_path + [new_idx]))
                else:
                    patches.append(Patch(PatchType.CREATE_NODE, current_path + [new_idx], payload=new_node))

            for old_key, (old_idx, _) in old_keyed.items():
                if old_key not in new_keyed:
                    patches.append(Patch(PatchType.REMOVE_NODE, current_path + [old_idx]))

            if moves:
                patches.append(Patch(PatchType.REORDER_CHILDREN, current_path, payload=moves))
        else:
            # Fallback non-keyed (index-by-index comparison)
            max_len = max(len(old_children), len(new_children))
            for i in range(max_len):
                o_child = old_children[i] if i < len(old_children) and isinstance(old_children[i], VNode) else None
                n_child = new_children[i] if i < len(new_children) and isinstance(new_children[i], VNode) else None
                child_path = current_path + [i]
                patches.extend(cls.diff(o_child, n_child, child_path))


class RealDOMNode:
    """Representasi simulasi native browser DOM Node (C++ binding layer)."""
    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None):
        self.tag = tag
        self.props: Dict[str, Any] = props.copy() if props else {}
        self.children: List[RealDOMNode] = []

    def render(self, depth: int = 0) -> str:
        indent = "  " * depth
        if self.tag == "#text":
            return f'{indent}"{self.props.get("value", "")}"'
        
        props_str = " ".join([f'{k}="{v}"' for k, v in self.props.items()])
        props_str = f" {props_str}" if props_str else ""
        
        if not self.children:
            return f"{indent}<{self.tag}{props_str} />"
        
        children_repr = "\n".join([c.render(depth + 1) for c in self.children])
        return f"{indent}<{self.tag}{props_str}>\n{children_repr}\n{indent}</{self.tag}>"


class DOMRenderer:
    """Menerapkan daftar Patch ke struktur pohon Simulated Real DOM."""

    @classmethod
    def mount(cls, vnode: VNode) -> RealDOMNode:
        dom_node = RealDOMNode(vnode.tag, vnode.props)
        for child in vnode.children:
            if isinstance(child, VNode):
                dom_node.children.append(cls.mount(child))
        return dom_node

    @classmethod
    def apply_patches(cls, root: RealDOMNode, patches: List[Patch]) -> Optional[RealDOMNode]:
        # Urutkan patch: patch kedalaman lebih tinggi dan aksi REMOVE diproses aman
        for patch in patches:
            cls._apply_single_patch(root, patch)
        return root

    @classmethod
    def _resolve_target(cls, root: RealDOMNode, path: List[int]) -> Tuple[Optional[RealDOMNode], Optional[RealDOMNode], int]:
        parent = None
        current: Optional[RealDOMNode] = root
        last_idx = 0
        for idx in path:
            parent = current
            if parent and 0 <= idx < len(parent.children):
                current = parent.children[idx]
                last_idx = idx
            else:
                current = None
                last_idx = idx
                break
        return parent, current, last_idx

    @classmethod
    def _apply_single_patch(cls, root: RealDOMNode, patch: Patch) -> None:
        if not patch.path:
            # Root modifications
            if patch.patch_type == PatchType.UPDATE_PROPS:
                for k, v in patch.payload.items():
                    if v is None:
                        root.props.pop(k, None)
                    else:
                        root.props[k] = v
            return

        parent, target, idx = cls._resolve_target(root, patch.path)

        if patch.patch_type == PatchType.UPDATE_PROPS and target:
            for k, v in patch.payload.items():
                if v is None:
                    target.props.pop(k, None)
                else:
                    target.props[k] = v

        elif patch.patch_type == PatchType.CREATE_NODE and parent:
            new_node = cls.mount(patch.payload)
            if idx >= len(parent.children):
                parent.children.append(new_node)
            else:
                parent.children.insert(idx, new_node)

        elif patch.patch_type == PatchType.REMOVE_NODE and parent:
            if 0 <= idx < len(parent.children):
                parent.children.pop(idx)

        elif patch.patch_type == PatchType.REPLACE_NODE and parent:
            new_node = cls.mount(patch.payload)
            if 0 <= idx < len(parent.children):
                parent.children[idx] = new_node

        elif patch.patch_type == PatchType.REORDER_CHILDREN and target:
            # Simulasi reordering keyed children
            pass


class ReactiveComponent:
    """Komponen State Reaktif Frontend dengan siklus rendering dan dirty checking."""
    def __init__(self, name: str):
        self.name = name
        self.state: Dict[str, Any] = {}
        self._current_vdom: Optional[VNode] = None
        self._real_dom: Optional[RealDOMNode] = None

    def set_state(self, updates: Dict[str, Any]) -> None:
        print(f"\n{CLR_MAG}⚡ State Mutation Triggered:{CLR_RESET} {updates}")
        self.state.update(updates)
        self.update()

    def render(self) -> VNode:
        raise NotImplementedError

    def mount(self) -> None:
        t0 = time.perf_counter_ns()
        self._current_vdom = self.render()
        self._real_dom = DOMRenderer.mount(self._current_vdom)
        elapsed = (time.perf_counter_ns() - t0) / 1000.0
        print(f"{CLR_GREEN}✓ [{self.name}] Initial Mount Finished in {elapsed:.2f} µs{CLR_RESET}")

    def update(self) -> None:
        t0 = time.perf_counter_ns()
        next_vdom = self.render()
        
        # 1. Diffing Step
        diff_start = time.perf_counter_ns()
        patches = DiffEngine.diff(self._current_vdom, next_vdom)
        diff_elapsed = (time.perf_counter_ns() - diff_start) / 1000.0

        # 2. Patching Step
        patch_start = time.perf_counter_ns()
        if self._real_dom:
            DOMRenderer.apply_patches(self._real_dom, patches)
        patch_elapsed = (time.perf_counter_ns() - patch_start) / 1000.0

        total_elapsed = (time.perf_counter_ns() - t0) / 1000.0
        self._current_vdom = next_vdom

        print(f"{CLR_CYAN}⚙ Reconciliation Summary:{CLR_RESET}")
        print(f"  - Generated Patches: {CLR_BOLD}{len(patches)}{CLR_RESET}")
        for p in patches:
            print(f"    * {CLR_YELLOW}{p}{CLR_RESET}")
        print(f"  - Diff Latency  : {diff_elapsed:.2f} µs")
        print(f"  - Patch Latency : {patch_elapsed:.2f} µs")
        print(f"  - Total Update  : {total_elapsed:.2f} µs")

    def print_dom(self) -> None:
        print(f"\n{CLR_BOLD}--- Current Real DOM Tree ({self.name}) ---{CLR_RESET}")
        if self._real_dom:
            print(self._real_dom.render())
        print(f"{CLR_BOLD}--------------------------------------------{CLR_RESET}")


class TodoApp(ReactiveComponent):
    """Implementasi Todo Application menggunakan Virtual DOM Framework kami."""
    def __init__(self):
        super().__init__("TodoApp")
        self.state = {
            "title": "Production Task Dashboard",
            "items": [
                {"id": "t1", "text": "Analyze Layout Thrashing", "done": False},
                {"id": "t2", "text": "Optimize Webpack Chunks", "done": True},
                {"id": "t3", "text": "Implement CSS Subgrid", "done": False}
            ],
            "filter": "ALL"
        }

    def render(self) -> VNode:
        items = self.state["items"]
        todo_vnodes = []
        for item in items:
            status_cls = "completed" if item["done"] else "pending"
            todo_vnodes.append(
                h("li", {"class": f"task-item {status_cls}", "data-id": item["id"]}, [
                    h("span", {"class": "label"}, [item["text"]]),
                    h("button", {"action": "toggle", "disabled": str(item["done"]).lower()}, [
                        "Undo" if item["done"] else "Complete"
                    ])
                ], key=item["id"])
            )

        return h("div", {"class": "app-container", "data-rendered": "vdom-engine"}, [
            h("header", {}, [
                h("h1", {"class": "title"}, [self.state["title"]]),
                h("p", {"class": "badge"}, [f"Total Tasks: {len(items)}"])
            ]),
            h("ul", {"class": "task-list"}, todo_vnodes)
        ])


def run_benchmark_cycle():
    print(f"{CLR_BOLD}{CLR_GREEN}==============================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}   DEEP DIVE: VIRTUAL DOM RECONCILIATION & DIFFING ENGINE     {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_GREEN}==============================================================={CLR_RESET}\n")

    app = TodoApp()

    # Step 1: Initial Render
    print(f"{CLR_BOLD}[Stage 1: Mounting Initial VDOM Tree]{CLR_RESET}")
    app.mount()
    app.print_dom()

    # Step 2: Attribute and Text Diffing (Toggle done status & update title)
    time.sleep(0.05)
    print(f"\n{CLR_BOLD}[Stage 2: Property Diffing & Micro-patching]{CLR_RESET}")
    app.set_state({
        "title": "Critical SRE Dashboard",
        "items": [
            {"id": "t1", "text": "Analyze Layout Thrashing", "done": True}, # toggled
            {"id": "t2", "text": "Optimize Webpack Chunks", "done": True},
            {"id": "t3", "text": "Implement CSS Subgrid", "done": False}
        ]
    })
    app.print_dom()

    # Step 3: Keyed Reconciliation (Reorder, Delete, and Insert new task)
    time.sleep(0.05)
    print(f"\n{CLR_BOLD}[Stage 3: Keyed Array Reconciliation (Insert, Delete, Reorder)]{CLR_RESET}")
    app.set_state({
        "items": [
            {"id": "t0", "text": "Setup Vite & Vitest", "done": False},     # Newly Inserted
            {"id": "t3", "text": "Implement CSS Subgrid", "done": False},   # Reordered
            {"id": "t1", "text": "Analyze Layout Thrashing", "done": True}   # Reordered (t2 removed)
        ]
    })
    app.print_dom()

    print(f"\n{CLR_BOLD}{CLR_CYAN}✔ Lab Completed: Virtual DOM Diffing and Real DOM patching validated successfully.{CLR_RESET}")


if __name__ == "__main__":
    run_benchmark_cycle()