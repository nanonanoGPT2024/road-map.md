#!/usr/bin/env python3
"""
Lab Hands-on: Frontend Engineering Deep Dive
Modul 02 - Virtual DOM Reconciliation & Reactive State Engine Simulator

Simulasi performa dan arsitektur inti Virtual DOM (VDOM), keyed diffing algorithm,
dan patch generation engine yang mendasari framework frontend modern (React Fiber/Vue 3).
"""

import sys
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union

# --- ANSI Formatting Constants ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"

# --- Core VDOM Structures ---
@dataclass
class VNode:
    tag: str
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[Union['VNode', str]] = field(default_factory=list)
    key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "key": self.key,
            "props": self.props,
            "children": [c.to_dict() if isinstance(c, VNode) else c for c in self.children]
        }

@dataclass
class Patch:
    op: str  # 'CREATE', 'REMOVE', 'REPLACE', 'UPDATE_PROPS', 'TEXT', 'REORDER'
    path: str
    data: Any

# --- Virtual DOM Diffing Engine ---
class VDOMReconciler:
    """
    Mengimplementasikan algoritma reconciliation tree-diffing O(n)
    dengan key-indexed heuristic untuk dynamic list rendering.
    """

    def __init__(self):
        self.patch_count = 0

    def diff(self, old_node: Optional[Union[VNode, str]], 
             new_node: Optional[Union[VNode, str]], 
             path: str = "root") -> List[Patch]:
        """
        Menghasilkan set delta operasi (patches) antara dua Virtual Tree node.
        """
        patches: List[Patch] = []

        # Kasus 1: Node lama dihapus
        if old_node is not None and new_node is None:
            patches.append(Patch(op="REMOVE", path=path, data=None))
            return patches

        # Kasus 2: Node baru dibuat
        if old_node is None and new_node is not None:
            patches.append(Patch(op="CREATE", path=path, data=new_node))
            return patches

        # Kasus 3: Node berupa teks primitif
        if isinstance(old_node, str) or isinstance(new_node, str):
            if old_node != new_node:
                patches.append(Patch(op="TEXT", path=path, data=new_node))
            return patches

        # Kasus 4: Node type/tag berbeda (Full replacement)
        if old_node.tag != new_node.tag:
            patches.append(Patch(op="REPLACE", path=path, data=new_node))
            return patches

        # Kasus 5: Tag sama, evaluasi diffing properti (Attributes/Props)
        prop_patches = self._diff_props(old_node.props, new_node.props)
        if prop_patches:
            patches.append(Patch(op="UPDATE_PROPS", path=path, data=prop_patches))

        # Kasus 6: Diffing children (Keyed Reconciliation)
        patches.extend(self._diff_children(old_node.children, new_node.children, path))

        return patches

    def _diff_props(self, old_props: Dict[str, Any], new_props: Dict[str, Any]) -> Dict[str, Any]:
        """Deteksi penambahan, perubahan, dan penghapusan atribut props."""
        delta = {}
        for k, v in new_props.items():
            if k not in old_props or old_props[k] != v:
                delta[k] = v
        for k in old_props:
            if k not in new_props:
                delta[k] = None  # None menandakan attribute deletion
        return delta

    def _diff_children(self, old_children: List[Union[VNode, str]], 
                       new_children: List[Union[VNode, str]], 
                       path: str) -> List[Patch]:
        """
        Keyed list diffing simulation.
        Menggunakan key identifier untuk mengoptimasi reposisi vs re-mount.
        """
        patches: List[Patch] = []
        old_keyed = {c.key: (i, c) for i, c in enumerate(old_children) if isinstance(c, VNode) and c.key}
        new_keyed = {c.key: (i, c) for i, c in enumerate(new_children) if isinstance(c, VNode) and c.key}

        # Jika kedua list children keyed, lakukan keyed strategy
        if old_keyed and new_keyed:
            patches.extend(self._reconcile_keyed_children(old_children, new_children, old_keyed, new_keyed, path))
        else:
            # Fallback naive index-based diffing
            max_len = max(len(old_children), len(new_children))
            for i in range(max_len):
                child_path = f"{path}.children[{i}]"
                o_child = old_children[i] if i < len(old_children) else None
                n_child = new_children[i] if i < len(new_children) else None
                patches.extend(self.diff(o_child, n_child, child_path))

        return patches

    def _reconcile_keyed_children(self, old_c, new_c, old_keyed, new_keyed, path) -> List[Patch]:
        patches = []
        # Deteksi node yang dipindahkan atau diperbarui
        for key, (new_idx, new_node) in new_keyed.items():
            child_path = f"{path}.keyed[{key}]"
            if key in old_keyed:
                old_idx, old_node = old_keyed[key]
                if old_idx != new_idx:
                    patches.append(Patch(op="REORDER", path=child_path, data={"from": old_idx, "to": new_idx}))
                # Recursive diff pada node yang sama
                patches.extend(self.diff(old_node, new_node, child_path))
            else:
                patches.append(Patch(op="CREATE", path=child_path, data=new_node))

        # Deteksi node yang dihapus
        for key, (old_idx, old_node) in old_keyed.items():
            if key not in new_keyed:
                patches.append(Patch(op="REMOVE", path=f"{path}.keyed[{key}]", data=None))

        return patches

# --- Real DOM / Layout Simulation Engine ---
class SimulatedDOM:
    """Simulasi render pipeline: Virtual Tree -> Real DOM Layout/Mutation Costs."""

    def __init__(self):
        self.mutation_cost_ms = 0.0
        self.dom_nodes_count = 0

    def apply_patches(self, patches: List[Patch]):
        start = time.perf_counter()
        for p in patches:
            # Simulasi overhead komputasi browser reflow/paint untuk operasi DOM nyata
            if p.op in ("CREATE", "REPLACE"):
                self.dom_nodes_count += 1
                time.sleep(0.0008)  # Node parsing & stylesheet recalculation
            elif p.op == "REMOVE":
                self.dom_nodes_count = max(0, self.dom_nodes_count - 1)
                time.sleep(0.0004)  # GC & memory unbinding
            elif p.op == "UPDATE_PROPS":
                time.sleep(0.0002)  # Attribute repaint cost
            elif p.op == "REORDER":
                time.sleep(0.0003)  # DOM insertBefore rearrangement
        self.mutation_cost_ms = (time.perf_counter() - start) * 1000

# --- Helper Component Builders ---
def h(tag: str, props: Dict[str, Any] = None, children: List[Any] = None, key: str = None) -> VNode:
    """Hyperscript helper factory untuk konstruksi VNode deklaratif."""
    return VNode(tag=tag, props=props or {}, children=children or [], key=key)

def print_banner(title: str):
    width = 75
    print(f"\n{Color.CYAN}{'=' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.MAGENTA} >>> {title.upper()} <<<{Color.RESET}")
    print(f"{Color.CYAN}{'=' * width}{Color.RESET}")

# --- Lab Scenarios Execution ---
def main():
    print_banner("Frontend Engine Deep Dive: VDOM & Reconciliation Lab")
    reconciler = VDOMReconciler()
    dom = SimulatedDOM()

    # --- Skenario 1: Initial Render Tree ---
    print(f"\n{Color.BOLD}[1] Initial Mount - Membangun Reactive Task List Component{Color.RESET}")
    initial_tree = h("div", {"class": "app-container", "theme": "dark"}, [
        h("header", {}, [h("h1", {}, ["Task Tracker Pro"])]),
        h("ul", {"class": "task-list"}, [
            h("li", {"class": "task-item"}, ["Persiapkan Presentasi Frontend"], key="t1"),
            h("li", {"class": "task-item"}, ["Refactor Reactive Pipeline"], key="t2"),
            h("li", {"class": "task-item pending"}, ["Benchmarking Garbage Collection"], key="t3")
        ])
    ])

    patches_initial = reconciler.diff(None, initial_tree)
    dom.apply_patches(patches_initial)

    print(f"{Color.GREEN}✓ Initial Tree Mounted.{Color.RESET}")
    print(f"  Total Patches: {Color.BOLD}{len(patches_initial)}{Color.RESET} operations")
    print(f"  DOM Layout/Mount Latency: {Color.YELLOW}{dom.mutation_cost_ms:.4f} ms{Color.RESET}")

    # --- Skenario 2: Surgical State Mutation (Minimal Update) ---
    print(f"\n{Color.BOLD}[2] State Mutation: Toggle Status & Class Modification{Color.RESET}")
    updated_tree = h("div", {"class": "app-container", "theme": "dark"}, [
        h("header", {}, [h("h1", {}, ["Task Tracker Pro"])]),
        h("ul", {"class": "task-list"}, [
            h("li", {"class": "task-item"}, ["Persiapkan Presentasi Frontend"], key="t1"),
            h("li", {"class": "task-item"}, ["Refactor Reactive Pipeline"], key="t2"),
            # Modifikasi class: pending -> completed
            h("li", {"class": "task-item completed"}, ["Benchmarking Garbage Collection"], key="t3")
        ])
    ])

    patches_update = reconciler.diff(initial_tree, updated_tree)
    dom.apply_patches(patches_update)

    print(f"  Diferensiasi Node Terdeteksi:")
    for patch in patches_update:
        print(f"    - Op: {Color.CYAN}{patch.op:<12}{Color.RESET} Path: {patch.path} | Data: {patch.data}")
    print(f"  Reconciliation Latency: {Color.YELLOW}{dom.mutation_cost_ms:.4f} ms{Color.RESET} (Sub-millisecond)")

    # --- Skenario 3: Structural Reordering & Invalidation ---
    print(f"\n{Color.BOLD}[3] Dynamic Array Mutation: Reorder Keyed Elements, Add & Delete{Color.RESET}")
    # t2 dihapus, t1 dipindah ke bawah, task baru t4 ditambahkan di awal
    reordered_tree = h("div", {"class": "app-container", "theme": "dark"}, [
        h("header", {}, [h("h1", {}, ["Task Tracker Pro"])]),
        h("ul", {"class": "task-list"}, [
            h("li", {"class": "task-item new"}, ["Audit Bundle Size Webpack"], key="t4"),
            h("li", {"class": "task-item completed"}, ["Benchmarking Garbage Collection"], key="t3"),
            h("li", {"class": "task-item"}, ["Persiapkan Presentasi Frontend"], key="t1")
        ])
    ])

    patches_reorder = reconciler.diff(updated_tree, reordered_tree)
    dom.apply_patches(patches_reorder)

    print(f"  Daftar Patch Terhitung ({len(patches_reorder)} operasi):")
    for patch in patches_reorder:
        color = Color.GREEN if patch.op == "CREATE" else (Color.RED if patch.op == "REMOVE" else Color.YELLOW)
        print(f"    {color}[{patch.op}]{Color.RESET} Target: {patch.path}")
        if patch.data:
            print(f"      Payload: {Color.GRAY}{patch.data}{Color.RESET}")

    print(f"  Reordering Overhead: {Color.YELLOW}{dom.mutation_cost_ms:.4f} ms{Color.RESET}")

    # --- Skenario 4: Performance Metric Comparison vs Full InnerHTML Rewrite ---
    print_banner("Benchmark: VDOM Reconciliation vs Naive innerHTML Reset")
    total_items = 1000
    
    # 1. Bangun large dataset
    vtree_large_a = h("div", {}, [h("p", {}, [f"Entry #{i}"], key=f"k_{i}") for i in range(total_items)])
    # Mutasi 1 item di tengah
    vtree_large_b = h("div", {}, [
        h("p", {}, [f"Entry #{i} (UPDATED)" if i == 500 else f"Entry #{i}"], key=f"k_{i}") 
        for i in range(total_items)
    ])

    # Reconciler diff
    t0 = time.perf_counter()
    vdom_patches = reconciler.diff(vtree_large_a, vtree_large_b)
    dom.apply_patches(vdom_patches)
    vdom_elapsed = (time.perf_counter() - t0) * 1000

    # Naive DOM rewrite (destroy & recreate all 1000 elements)
    t0 = time.perf_counter()
    naive_patches = [Patch(op="REMOVE", path="all", data=None)] * total_items + \
                    [Patch(op="CREATE", path="all", data=None)] * total_items
    dom.apply_patches(naive_patches)
    naive_elapsed = (time.perf_counter() - t0) * 1000

    print(f"Ukuran Dataset: {Color.BOLD}{total_items} nodes{Color.RESET}")
    print(f"1. VDOM Surgical Reconciliation : {Color.GREEN}{vdom_elapsed:8.2f} ms{Color.RESET} ({len(vdom_patches)} patches applied)")
    print(f"2. Naive Full DOM Replace       : {Color.RED}{naive_elapsed:8.2f} ms{Color.RESET} ({len(naive_patches)} raw mutations)")
    ratio = naive_elapsed / max(vdom_elapsed, 0.0001)
    print(f"Efisiensi Pipeline: {Color.BOLD}{Color.CYAN}{ratio:.1f}x lebih cepat{Color.RESET} dibanding re-mount total.")
    print(f"\n{Color.GREEN}✔ Skenario pengujian reconciliation Virtual DOM selesai sukses.{Color.RESET}")

if __name__ == "__main__":
    main()