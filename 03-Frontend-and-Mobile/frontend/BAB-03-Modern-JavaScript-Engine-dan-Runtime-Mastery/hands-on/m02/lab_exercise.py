#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Frontend Architecture - Virtual DOM & Reconciliation Engine
Bab: 03 - Modul 02: Core Frontend Mechanics & Diffing Algorithms

Deskripsi:
Simulasi komprehensif dari Reactive State, Virtual DOM (VDOM) Tree,
Heuristic Diffing Algorithm (mirip React/Vue), dan DOM Mutation Batching
lengkap dengan analisis performa (Reflow/Repaint overhead metrics).
"""

import sys
import time
import json
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

# --- Terminal ANSI Styling ---
class Style:
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
    BG_DARK = "\033[48;5;236m"

# --- Virtual DOM & Patch Definitions ---
class PatchType(Enum):
    CREATE_NODE = auto()
    REMOVE_NODE = auto()
    REPLACE_NODE = auto()
    UPDATE_PROPS = auto()
    UPDATE_TEXT = auto()
    REORDER_CHILDREN = auto()

@dataclass
class VNode:
    tag: Optional[str] = None          # None menunjukkan Text Node
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[Union['VNode', str]] = field(default_factory=list)
    key: Optional[str] = None
    text: Optional[str] = None

    def is_text_node(self) -> bool:
        return self.tag is None and self.text is not None

    def to_dict(self) -> Dict[str, Any]:
        if self.is_text_node():
            return {"#text": self.text}
        return {
            "tag": self.tag,
            "key": self.key,
            "props": self.props,
            "children": [c.to_dict() if isinstance(c, VNode) else {"#text": str(c)} for c in self.children]
        }

@dataclass
class Patch:
    patch_type: PatchType
    path: str
    old_val: Any = None
    new_val: Any = None
    key: Optional[str] = None

# --- Mock Physical DOM Tree Simulator ---
class MockDOMNode:
    """Mensimulasikan real DOM tree di browser dengan kalkulasi biaya reflow/repaint."""
    def __init__(self, tag: Optional[str], text: Optional[str] = None, props: Dict = None):
        self.tag = tag
        self.text = text
        self.props = props or {}
        self.children: List['MockDOMNode'] = []

    def count_nodes(self) -> int:
        return 1 + sum(child.count_nodes() for child in self.children)

class MockBrowserRenderer:
    """Mengukur metrik komputasi browser engine (DOM mutation overhead)."""
    def __init__(self):
        self.root: Optional[MockDOMNode] = None
        self.dom_ops_count = 0
        self.layout_reflow_count = 0
        self.repaint_count = 0
        self.mutation_time_ms = 0.0

    def reset_metrics(self):
        self.dom_ops_count = 0
        self.layout_reflow_count = 0
        self.repaint_count = 0
        self.mutation_time_ms = 0.0

    def apply_patches(self, patches: List[Patch]):
        """Menerapkan daftar patch hasil diffing ke Simulated Real DOM."""
        start_time = time.perf_counter()
        for patch in patches:
            self.dom_ops_count += 1
            if patch.patch_type in (PatchType.CREATE_NODE, PatchType.REMOVE_NODE, PatchType.REPLACE_NODE):
                self.layout_reflow_count += 1
                self.repaint_count += 1
            elif patch.patch_type == PatchType.UPDATE_PROPS:
                # Perubahan dimensi / layout props memicu reflow, sisanya repaint
                layout_affecting = {"width", "height", "margin", "padding", "display", "font-size"}
                changed_keys = set(patch.new_val.keys()) if isinstance(patch.new_val, dict) else set()
                if changed_keys.intersection(layout_affecting):
                    self.layout_reflow_count += 1
                self.repaint_count += 1
            elif patch.patch_type == PatchType.UPDATE_TEXT:
                self.repaint_count += 1
            elif patch.patch_type == PatchType.REORDER_CHILDREN:
                self.layout_reflow_count += 1
                self.repaint_count += 1
        
        self.mutation_time_ms = (time.perf_counter() - start_time) * 1000

    def naive_full_rerender(self, vdom: VNode):
        """Metode Naive: Menghancurkan dan membangun ulang seluruh DOM subtree."""
        start_time = time.perf_counter()
        
        def build_recursive(node: VNode) -> MockDOMNode:
            self.dom_ops_count += 1
            dom = MockDOMNode(tag=node.tag, text=node.text, props=node.props)
            for c in node.children:
                child_vnode = c if isinstance(c, VNode) else VNode(text=str(c))
                dom.children.append(build_recursive(child_vnode))
            return dom

        self.root = build_recursive(vdom)
        # Full teardown and recreation memicu reflow dan repaint massal
        self.layout_reflow_count = self.dom_ops_count
        self.repaint_count = self.dom_ops_count
        self.mutation_time_ms = (time.perf_counter() - start_time) * 1000

# --- Virtual DOM Diffing Engine ---
class VDOMDiffEngine:
    """Implementasi heuristik diffing VDOM (O(n) tree traversal)."""

    @classmethod
    def diff(cls, old_tree: Optional[VNode], new_tree: Optional[VNode], path: str = "root") -> List[Patch]:
        patches: List[Patch] = []

        if old_tree is None and new_tree is None:
            return patches

        # Kasus 1: Node baru dibuat
        if old_tree is None and new_tree is not None:
            patches.append(Patch(PatchType.CREATE_NODE, path, None, new_tree))
            return patches

        # Kasus 2: Node lama dihapus
        if old_tree is not None and new_tree is None:
            patches.append(Patch(PatchType.REMOVE_NODE, path, old_tree, None))
            return patches

        # Kasus 3: Text Node update
        if old_tree.is_text_node() and new_tree.is_text_node():
            if old_tree.text != new_tree.text:
                patches.append(Patch(PatchType.UPDATE_TEXT, path, old_tree.text, new_tree.text))
            return patches

        # Kasus 4: Node type diganti (contoh: <div> ke <span> atau Element ke Text)
        if old_tree.tag != new_tree.tag:
            patches.append(Patch(PatchType.REPLACE_NODE, path, old_tree, new_tree))
            return patches

        # Kasus 5: Tag sama -> Diff Properties
        props_patch = cls._diff_props(old_tree.props, new_tree.props)
        if props_patch:
            patches.append(Patch(PatchType.UPDATE_PROPS, path, old_tree.props, props_patch))

        # Kasus 6: Diff Children (Keyed & Non-keyed reconciliation)
        patches.extend(cls._diff_children(old_tree.children, new_tree.children, path))

        return patches

    @classmethod
    def _diff_props(cls, old_p: Dict[str, Any], new_p: Dict[str, Any]) -> Dict[str, Any]:
        diff = {}
        # Cek prop yang berubah atau baru ditambahkan
        for k, v in new_p.items():
            if k not in old_p or old_p[k] != v:
                diff[k] = v
        # Cek prop yang dihapus (diberi flag None)
        for k in old_p:
            if k not in new_p:
                diff[k] = None
        return diff

    @classmethod
    def _diff_children(cls, old_children: List[Union[VNode, str]], new_children: List[Union[VNode, str]], path: str) -> List[Patch]:
        patches: List[Patch] = []
        
        # Normalisasi child text primitives menjadi VNode
        norm_old = [c if isinstance(c, VNode) else VNode(text=str(c)) for c in old_children]
        norm_new = [c if isinstance(c, VNode) else VNode(text=str(c)) for c in new_children]

        # Strategi Rekonsiliasi Berbasis Key vs Indeks Posisi
        old_keyed = {c.key: c for c in norm_old if c.key is not None}
        new_keyed = {c.key: c for c in norm_new if c.key is not None}

        if old_keyed and new_keyed:
            # Reorder detection heuristic sederhana
            old_order = [c.key for c in norm_old if c.key is not None]
            new_order = [c.key for c in norm_new if c.key is not None]
            if old_order != new_order:
                patches.append(Patch(PatchType.REORDER_CHILDREN, f"{path}/*", old_order, new_order))

        max_len = max(len(norm_old), len(norm_new))
        for i in range(max_len):
            child_path = f"{path}[{i}]"
            c_old = norm_old[i] if i < len(norm_old) else None
            c_new = norm_new[i] if i < len(norm_new) else None
            patches.extend(cls.diff(c_old, c_new, child_path))

        return patches

# --- Reactive State Store ---
class ReactiveComponent:
    """Komponen UI dengan state reaktif dan auto-trigger reconciliation cycle."""
    def __init__(self, name: str):
        self.name = name
        self._state: Dict[str, Any] = {}
        self.current_vdom: Optional[VNode] = None
        self.engine = VDOMDiffEngine()
        self.renderer = MockBrowserRenderer()

    def set_state(self, updates: Dict[str, Any]):
        """Memperbarui state lokal dan mengeksekusi lifecycle render & diffing."""
        self._state.update(updates)
        new_vdom = self.render()
        
        patches = self.engine.diff(self.current_vdom, new_vdom)
        self.renderer.apply_patches(patches)
        self.current_vdom = new_vdom
        return patches

    def render(self) -> VNode:
        raise NotImplementedError("Subclass wajib mengimplementasikan render()")

# --- Concrete Demo Component ---
class ShoppingCartComponent(ReactiveComponent):
    def __init__(self):
        super().__init__("ShoppingCart")
        # Inisialisasi State
        self._state = {
            "title": "Keranjang Belanja",
            "dark_mode": False,
            "items": [
                {"id": "p1", "name": "Mechanical Keyboard", "qty": 1, "price": 120},
                {"id": "p2", "name": "Ergonomic Mouse", "qty": 2, "price": 60}
            ]
        }
        self.current_vdom = self.render()
        self.renderer.naive_full_rerender(self.current_vdom)

    def render(self) -> VNode:
        theme_class = "dark-theme" if self._state["dark_mode"] else "light-theme"
        
        item_nodes = []
        for it in self._state["items"]:
            item_nodes.append(
                VNode(
                    tag="li",
                    key=it["id"],
                    props={"class": "cart-item", "data-id": it["id"]},
                    children=[
                        VNode(tag="span", props={"class": "item-name"}, children=[it["name"]]),
                        VNode(tag="span", props={"class": "item-qty"}, children=[f"x{it['qty']}"]),
                        VNode(tag="span", props={"class": "item-price"}, children=[f"${it['price'] * it['qty']}"])
                    ]
                )
            )

        return VNode(
            tag="div",
            props={"id": "cart-root", "class": f"container {theme_class}"},
            children=[
                VNode(tag="h2", children=[self._state["title"]]),
                VNode(tag="ul", props={"class": "item-list"}, children=item_nodes),
                VNode(tag="footer", children=[
                    VNode(text=f"Total: ${sum(i['price'] * i['qty'] for i in self._state['items'])}")
                ])
            ]
        )

# --- Reporting & Visual Output Helper ---
def print_banner(text: str):
    print(f"\n{Style.BG_DARK}{Style.CYAN}{Style.BOLD} === {text.upper()} === {Style.RESET}\n")

def print_patch_entry(idx: int, patch: Patch):
    type_color = {
        PatchType.CREATE_NODE: Style.GREEN,
        PatchType.REMOVE_NODE: Style.RED,
        PatchType.REPLACE_NODE: Style.MAGENTA,
        PatchType.UPDATE_PROPS: Style.YELLOW,
        PatchType.UPDATE_TEXT: Style.BLUE,
        PatchType.REORDER_CHILDREN: Style.CYAN
    }.get(patch.patch_type, Style.WHITE)

    print(f"  {Style.DIM}[#{idx:02d}]{Style.RESET} {type_color}{Style.BOLD}{patch.patch_type.name:<18}{Style.RESET} "
          f"Target: {Style.CYAN}{patch.path:<16}{Style.RESET}")
    
    if patch.patch_type == PatchType.UPDATE_PROPS:
        print(f"       {Style.DIM}Changes:{Style.RESET} {patch.new_val}")
    elif patch.patch_type == PatchType.UPDATE_TEXT:
        print(f"       {Style.DIM}Delta:{Style.RESET} '{patch.old_val}' -> '{Style.GREEN}{patch.new_val}{Style.RESET}'")
    elif patch.patch_type == PatchType.REORDER_CHILDREN:
        print(f"       {Style.DIM}Keys:{Style.RESET} {patch.old_val} -> {patch.new_val}")

# --- Benchmark Engine ---
def run_stress_benchmark():
    print_banner("Benchmark Performa: VDOM Reconciliation vs Naive DOM Re-render")
    
    # Generate large tree
    def generate_large_vdom(num_items: int, salt: str = "") -> VNode:
        items = []
        for i in range(num_items):
            items.append(
                VNode(
                    tag="div",
                    key=f"k_{i}",
                    props={"class": "list-row", "data-index": i},
                    children=[
                        VNode(tag="b", children=[f"Item #{i}{salt}"]),
                        VNode(tag="span", children=[f"Status: OK"]),
                    ]
                )
            )
        return VNode(tag="main", props={"id": "app-container"}, children=items)

    NODE_COUNT = 1500
    print(f"[*] Menyiapkan VDOM tree dengan {Style.BOLD}{NODE_COUNT}{Style.RESET} elemen turunan...")
    
    tree_a = generate_large_vdom(NODE_COUNT)
    # Tree B hanya mengubah 1 teks pada indeks ke-42 dan menambah 1 node baru
    tree_b = generate_large_vdom(NODE_COUNT)
    tree_b.children[42].children[0].children[0] = f"Item #42 [MODIFIED]"
    tree_b.children.append(VNode(tag="div", key="k_new", children=[VNode(text="Inserted Element")]))

    # Test Naive Full Re-render
    renderer_naive = MockBrowserRenderer()
    start_naive = time.perf_counter()
    renderer_naive.naive_full_rerender(tree_b)
    elapsed_naive = (time.perf_counter() - start_naive) * 1000

    # Test VDOM Engine Diff + Patch
    renderer_vdom = MockBrowserRenderer()
    start_vdom = time.perf_counter()
    patches = VDOMDiffEngine.diff(tree_a, tree_b)
    renderer_vdom.apply_patches(patches)
    elapsed_vdom = (time.perf_counter() - start_vdom) * 1000

    print(f"\n{Style.BOLD}Hasil Komparasi:{Style.RESET}")
    print(f"{'Metrik':<28} | {'Naive Re-render':<18} | {'VDOM Engine (Diff+Patch)':<22}")
    print("-" * 75)
    print(f"{'Eksekusi Total (ms)':<28} | {Style.RED}{elapsed_naive:15.3f} ms{Style.RESET} | {Style.GREEN}{elapsed_vdom:19.3f} ms{Style.RESET}")
    print(f"{'DOM Operations Count':<28} | {renderer_naive.dom_ops_count:<18} | {renderer_vdom.dom_ops_count:<22}")
    print(f"{'Layout Reflow Triggers':<28} | {renderer_naive.layout_reflow_count:<18} | {renderer_vdom.layout_reflow_count:<22}")
    print(f"{'Repaint Triggers':<28} | {renderer_naive.repaint_count:<18} | {renderer_vdom.repaint_count:<22}")
    print(f"{'Jumlah Patch Terkalkulasi':<28} | {'N/A (Full Wipe)':<18} | {len(patches):<22}")
    
    efficiency = ((elapsed_naive - elapsed_vdom) / elapsed_naive) * 100 if elapsed_naive > 0 else 0
    print(f"\nEfisiensi komputasi VDOM: {Style.BOLD}{Style.GREEN}{efficiency:.2f}% lebih optimal{Style.RESET} pada surgical updates.")

# --- Main Driver Script ---
def main():
    print(f"{Style.BOLD}{Style.CYAN}================================================================={Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE} LAB HANDS-ON: FRONTEND ARCHITECTURE & VIRTUAL DOM RECONCILIATION {Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}================================================================={Style.RESET}")

    cart = ShoppingCartComponent()
    print(f"[*] Initial Tree Rendering Selesai. Total Node Fisik: {cart.renderer.root.count_nodes()}")

    # Skenario 1: Update Property & Quantity (Text Change + Attribute Change)
    print_banner("Skenario 1: Mutasi State Lokal (Update Qty Item & Ganti Tema)")
    cart.renderer.reset_metrics()
    
    patches_1 = cart.set_state({
        "dark_mode": True,
        "items": [
            {"id": "p1", "name": "Mechanical Keyboard", "qty": 3, "price": 120},  # Qty naik dari 1 -> 3
            {"id": "p2", "name": "Ergonomic Mouse", "qty": 2, "price": 60}
        ]
    })

    print(f"[*] Terdeteksi {Style.BOLD}{len(patches_1)}{Style.RESET} operasi patch:")
    for idx, p in enumerate(patches_1, 1):
        print_patch_entry(idx, p)

    print(f"\n{Style.DIM}Metrik Mutasi DOM Browser:")
    print(f" - DOM Ops: {cart.renderer.dom_ops_count} ops")
    print(f" - Reflow: {cart.renderer.layout_reflow_count} events")
    print(f" - Repaint: {cart.renderer.repaint_count} events{Style.RESET}")

    # Skenario 2: Penambahan Elemen Baru & Perubahan Susunan Elemen (Reorder)
    print_banner("Skenario 2: Structural Mutation (Penambahan Elemen & Reorder Key)")
    cart.renderer.reset_metrics()

    patches_2 = cart.set_state({
        "items": [
            {"id": "p2", "name": "Ergonomic Mouse", "qty": 2, "price": 60},        # Dipindah ke atas
            {"id": "p1", "name": "Mechanical Keyboard", "qty": 3, "price": 120},
            {"id": "p3", "name": "USB-C Hub Multiport", "qty": 1, "price": 45}     # Item baru
        ]
    })

    print(f"[*] Terdeteksi {Style.BOLD}{len(patches_2)}{Style.RESET} operasi patch:")
    for idx, p in enumerate(patches_2, 1):
        print_patch_entry(idx, p)

    print(f"\n{Style.DIM}Metrik Mutasi DOM Browser:")
    print(f" - DOM Ops: {cart.renderer.dom_ops_count} ops")
    print(f" - Reflow: {cart.renderer.layout_reflow_count} events")
    print(f" - Repaint: {cart.renderer.repaint_count} events{Style.RESET}")

    # Skenario 3: Benchmark Stress Test
    run_stress_benchmark()

    print(f"\n{Style.GREEN}{Style.BOLD}[DONE]{Style.RESET} Lab Hands-on VDOM & Diffing Selesai dieksekusi secara native.\n")

if __name__ == "__main__":
    main()