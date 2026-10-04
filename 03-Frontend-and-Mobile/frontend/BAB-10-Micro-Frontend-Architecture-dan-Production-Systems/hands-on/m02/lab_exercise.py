#!/usr/bin/env python3
"""
Frontend Architecture Deep Dive: Virtual DOM Diffing Engine & Reactive State Store
Simulasi komprehensif reconciliation algorithm (heuristic O(n) diff), batch render scheduling,
dan reactive state management tanpa pustaka eksternal.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable
import time
import json
import sys


# ==============================================================================
# ANSI Color Formatting untuk Visualisasi Terminal
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"


# ==============================================================================
# Virtual DOM Data Structures
# ==============================================================================
class PatchType(Enum):
    CREATE_NODE = auto()
    REMOVE_NODE = auto()
    REPLACE_NODE = auto()
    UPDATE_PROPS = auto()
    UPDATE_TEXT = auto()
    REORDER_CHILDREN = auto()


@dataclass
class VNode:
    tag: str
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[Any] = field(default_factory=list)  # List of VNode or str
    key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialisasi VNode untuk inspeksi debugging."""
        return {
            "tag": self.tag,
            "key": self.key,
            "props": self.props,
            "children": [
                c.to_dict() if isinstance(c, VNode) else c for c in self.children
            ],
        }


@dataclass
class Patch:
    patch_type: PatchType
    target_path: str  # Path tree identifier, misal: "root/0/1"
    payload: Any = None


# ==============================================================================
# Simulated Real DOM & Paint Metrics Tracker
# ==============================================================================
class DOMNode:
    """Mock representasi node DOM Browser sesungguhnya."""

    def __init__(self, tag: str, text: Optional[str] = None):
        self.tag = tag
        self.text = text
        self.props: Dict[str, Any] = {}
        self.children: List["DOMNode"] = []


class DOMRenderer:
    """
    Simulasi DOM Host Environment. Melacak biaya komputasi browser
    seperti layout thrashing, DOM mutations, dan repaint calls.
    """

    def __init__(self):
        self.root: Optional[DOMNode] = None
        self.mutation_count = 0
        self.reflow_count = 0

    def apply_patches(self, patches: List[Patch]):
        """Menerapkan instruksi mutasi minimal dari Diffing Engine ke Mock DOM."""
        for patch in patches:
            self.mutation_count += 1
            if patch.patch_type in (
                PatchType.CREATE_NODE,
                PatchType.REMOVE_NODE,
                PatchType.REPLACE_NODE,
            ):
                self.reflow_count += 1  # Struktural perubahan memicu reflow/layout

            print(
                f"  {Color.GRAY}⚡ [Browser DOM Mutation]{Color.RESET} "
                f"Path: {Color.CYAN}{patch.target_path:<10}{Color.RESET} | "
                f"Op: {Color.YELLOW}{patch.patch_type.name:<16}{Color.RESET} | "
                f"Detail: {patch.payload}"
            )


# ==============================================================================
# Heuristic Tree Reconciliation / Diffing Engine
# ==============================================================================
class VDOMReconciler:
    """
    Algoritma rekonsiliasi VDOM terinspirasi dari React Fiber / Vue 3 core.
    Menggunakan heuristic level-by-level comparison berbobot O(n).
    """

    @classmethod
    def diff(
        cls, old_node: Optional[Any], new_node: Optional[Any], path: str = "root"
    ) -> List[Patch]:
        patches: List[Patch] = []

        # Kasus 1: Node lama dihapus
        if old_node is not None and new_node is None:
            patches.append(Patch(PatchType.REMOVE_NODE, path))
            return patches

        # Kasus 2: Node baru ditambahkan
        if old_node is None and new_node is not None:
            payload = (
                new_node.tag
                if isinstance(new_node, VNode)
                else f"text('{new_node}')"
            )
            patches.append(Patch(PatchType.CREATE_NODE, path, payload=payload))
            return patches

        # Kasus 3: Keduanya bertipe teks (primitive string/number)
        if isinstance(old_node, (str, int)) or isinstance(new_node, (str, int)):
            if str(old_node) != str(new_node):
                patches.append(
                    Patch(
                        PatchType.UPDATE_TEXT,
                        path,
                        payload={"from": str(old_node), "to": str(new_node)},
                    )
                )
            return patches

        # Kasus 4: Node diganti secara total jika Tag atau Key berbeda
        if (
            isinstance(old_node, VNode)
            and isinstance(new_node, VNode)
            and (old_node.tag != new_node.tag or old_node.key != new_node.key)
        ):
            patches.append(
                Patch(
                    PatchType.REPLACE_NODE,
                    path,
                    payload={"old": old_node.tag, "new": new_node.tag},
                )
            )
            return patches

        # Kasus 5: Tag & Key sama -> Lakukan diff pada atribut (props)
        if isinstance(old_node, VNode) and isinstance(new_node, VNode):
            prop_diff = cls._diff_props(old_node.props, new_node.props)
            if prop_diff:
                patches.append(
                    Patch(PatchType.UPDATE_PROPS, path, payload=prop_diff)
                )

            # Diff children secara rekursif
            child_patches = cls._diff_children(
                old_node.children, new_node.children, path
            )
            patches.extend(child_patches)

        return patches

    @staticmethod
    def _diff_props(
        old_props: Dict[str, Any], new_props: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mendeteksi penambahan, pembaruan, dan penghapusan atribut props."""
        changes = {}
        for key, value in new_props.items():
            if key not in old_props or old_props[key] != value:
                changes[key] = value
        for key in old_props:
            if key not in new_props:
                changes[key] = None  # None merepresentasikan properti dihapus
        return changes

    @classmethod
    def _diff_children(
        cls, old_children: List[Any], new_children: List[Any], parent_path: str
    ) -> List[Patch]:
        """Diffing koleksi children dengan penelusuran index (Simulasi Keyed List)."""
        patches: List[Patch] = []
        max_len = max(len(old_children), len(new_children))

        for idx in range(max_len):
            child_path = f"{parent_path}/{idx}"
            old_child = (
                old_children[idx] if idx < len(old_children) else None
            )
            new_child = (
                new_children[idx] if idx < len(new_children) else None
            )

            patches.extend(cls.diff(old_child, new_child, child_path))

        return patches


# ==============================================================================
# Reactive State & Microtask Batching Scheduler
# ==============================================================================
class ReactiveStore:
    """
    Store reaktif yang mengimplementasikan Dirty-Checking dan
    Batch Execution Loop (Mencegah synchronous layout thrashing).
    """

    def __init__(self, initial_state: Dict[str, Any]):
        self._state = initial_state
        self._listeners: List[Callable[[], None]] = []
        self._is_batching = False
        self._has_pending_render = False

    def get_state(self) -> Dict[str, Any]:
        return self._state

    def set_state(self, updates: Dict[str, Any]):
        """Memperbarui state. Jika batching aktif, render ditunda ke batch flush."""
        self._state.update(updates)
        if self._is_batching:
            self._has_pending_render = True
        else:
            self._notify()

    def subscribe(self, callback: Callable[[], None]):
        self._listeners.append(callback)

    def _notify(self):
        for listener in self._listeners:
            listener()

    def batch(self, update_fn: Callable[[], None]):
        """Eksekusi multiple state updates secara atomik dalam 1 frame render."""
        self._is_batching = True
        try:
            update_fn()
        finally:
            self._is_batching = False
            if self._has_pending_render:
                self._has_pending_render = False
                self._notify()


# ==============================================================================
# Component Layer (Simulasi declarative UI)
# ==============================================================================
class TaskListComponent:
    """Komponen deklaratif yang me-render daftar todo berdasarkan status."""

    def __init__(self, store: ReactiveStore):
        self.store = store

    def render(self) -> VNode:
        state = self.store.get_state()
        filter_mode = state.get("filter", "ALL")
        items = state.get("items", [])

        # Filter items
        filtered = [
            it
            for it in items
            if filter_mode == "ALL"
            or (filter_mode == "COMPLETED" and it["done"])
            or (filter_mode == "ACTIVE" and not it["done"])
        ]

        # Buat representasi tree VNode
        children_nodes = []
        for item in filtered:
            children_nodes.append(
                VNode(
                    tag="li",
                    key=str(item["id"]),
                    props={
                        "class": "completed" if item["done"] else "pending",
                        "data-id": item["id"],
                    },
                    children=[
                        VNode(
                            tag="span",
                            props={"class": "title"},
                            children=[item["title"]],
                        ),
                        VNode(
                            tag="span",
                            props={"class": "badge"},
                            children=[
                                "✓ Done" if item["done"] else "⏳ In Progress"
                            ],
                        ),
                    ],
                )
            )

        return VNode(
            tag="div",
            props={"class": "todo-container", "data-theme": state.get("theme")},
            children=[
                VNode(
                    tag="h2",
                    children=[f"Dashboard Tasks ({state.get('theme')})"],
                ),
                VNode(
                    tag="ul",
                    props={"class": "todo-list"},
                    children=children_nodes,
                ),
            ],
        )


# ==============================================================================
# Application Runtime Execution
# ==============================================================================
def main():
    print(f"{Color.BOLD}{Color.CYAN}======================================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} LAB: DEEP DIVE FRONTEND ARCHITECTURE & VIRTUAL DOM RECONCILIATION   {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}======================================================================{Color.RESET}\n")

    # Inisialisasi Mock Engine
    dom_renderer = DOMRenderer()
    store = ReactiveStore(
        {
            "theme": "light",
            "filter": "ALL",
            "items": [
                {"id": 1, "title": "Setup Webpack Bundler", "done": True},
                {"id": 2, "title": "Implement Fiber Architecture", "done": False},
                {"id": 3, "title": "Optimize Repaint & Reflow", "done": False},
            ],
        }
    )
    component = TaskListComponent(store)

    current_vnode: Optional[VNode] = None

    def render_pipeline():
        nonlocal current_vnode
        new_vnode = component.render()
        print(f"\n{Color.BOLD}{Color.MAGENTA}▶ [Pipeline Triggered] Recomputing Virtual DOM Diff...{Color.RESET}")
        
        t0 = time.perf_counter()
        patches = VDOMReconciler.diff(current_vnode, new_vnode)
        duration_us = (time.perf_counter() - t0) * 1_000_000

        print(
            f"  Computed {len(patches)} patch(es) in {Color.GREEN}{duration_us:.2f} µs{Color.RESET}"
        )
        dom_renderer.apply_patches(patches)
        current_vnode = new_vnode

    # Daftarkan render loop ke store
    store.subscribe(render_pipeline)

    # 1. Mount Awal (Initial Paint)
    print(f"{Color.BOLD}[1] Initial Mount Render Phase{Color.RESET}")
    render_pipeline()

    # 2. Mutasi State Tunggal (Single Prop Change)
    print(f"\n{Color.BOLD}[2] Mutasi Satuan: Mengubah Theme (Micro-Update){Color.RESET}")
    store.set_state({"theme": "dark"})

    # 3. Mutasi State Tanpa Batching (Naive Approach: Boros Paint & Reflow)
    print(f"\n{Color.BOLD}[3] Simulasi Mutasi Ekstrim: Batched vs Unbatched Execution{Color.RESET}")
    print(f"{Color.GRAY}-- Skenario: Batching State Update (Atomic Commit) --{Color.RESET}")
    
    initial_mutations = dom_renderer.mutation_count
    
    # Jalankan batching: 3 mutasi sekaligus hanya menghasilkan 1 siklus render & diff
    store.batch(lambda: (
        store.set_state({"filter": "ACTIVE"}),
        store.set_state({"theme": "high-contrast"}),
        store.set_state({
            "items": [
                {"id": 1, "title": "Setup Webpack Bundler", "done": True},
                {"id": 2, "title": "Implement Fiber Architecture", "done": True}, # Task 2 selesai
                {"id": 3, "title": "Optimize Repaint & Reflow", "done": False},
                {"id": 4, "title": "Audit Web Vitals LCP/CLS", "done": False},   # Node baru ditambahkan
            ]
        })
    ))

    # Reviewing DOM Tree Result
    print(f"\n{Color.BOLD}{Color.CYAN}======================================================================{Color.RESET}")
    print(f"{Color.BOLD}FINAL RECONCILIATION SUMMARY{Color.RESET}")
    print(f"{Color.CYAN}======================================================================{Color.RESET}")
    print(f"Total Cumulative DOM Mutations : {Color.GREEN}{dom_renderer.mutation_count}{Color.RESET}")
    print(f"Total Layout Reflows Caused    : {Color.YELLOW}{dom_renderer.reflow_count}{Color.RESET}")
    print(f"Final VDOM Structure Keys      : {[c.key for c in current_vnode.children[1].children]}")
    print(f"{Color.GREEN}✓ Lab selesai. Rekonsiliasi diff dan reactive scheduler berjalan valid.{Color.RESET}\n")


if __name__ == "__main__":
    main()