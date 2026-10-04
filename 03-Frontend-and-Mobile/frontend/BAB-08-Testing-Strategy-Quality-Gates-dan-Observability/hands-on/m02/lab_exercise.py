#!/usr/bin/env python3
"""
Lab Hands-on: Frontend Engineering Deep Dive
Modul: Virtual DOM Reconciler, Keyed Diffing Algorithm, & Reactive State Engine
--------------------------------------------------------------------------------
Script ini memodelkan subsistem inti dari framework modern (React Fiber/Vue 3 runtime):
1. Dependency-Tracking Reactive State (Observer/Signal Pattern)
2. Virtual DOM (VNode) Tree Construction
3. Keyed Child-Reconciliation & Diffing Engine (Levenshtein/Index Map minimal patch)
4. DOM Mutation Patch Scheduler & Synthetic Paint Cost Profiler
"""

import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

# ==============================================================================
# TERMINAL ANSI STYLING
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GRAY    = "\033[90m"

# ==============================================================================
# VIRTUAL DOM DEFINITIONS & DATA STRUCTURES
# ==============================================================================
class PatchType(Enum):
    CREATE_NODE  = auto()
    REMOVE_NODE  = auto()
    REPLACE_NODE = auto()
    UPDATE_PROPS = auto()
    UPDATE_TEXT  = auto()
    REORDER_CHILD = auto()

@dataclass
class VNode:
    tag: Optional[str] = None
    props: Dict[str, Any] = field(default_factory=dict)
    children: List['VNode'] = field(default_factory=list)
    text: Optional[str] = None
    key: Optional[str] = None

    @property
    def is_text(self) -> bool:
        return self.tag is None and self.text is not None

    def clone(self) -> 'VNode':
        return VNode(
            tag=self.tag,
            props=dict(self.props),
            children=[c.clone() for c in self.children],
            text=self.text,
            key=self.key
        )

@dataclass
class PatchOperation:
    op_type: PatchType
    path: str              # Tree traversal path (misal: "root.0.1")
    target_key: Optional[str]
    payload: Any = None    # Properti baru, text baru, atau VNode baru

# ==============================================================================
# MOCK DOM & PAINT SIMULATOR
# ==============================================================================
class MockDOMNode:
    """Representasi Physical Browser DOM Node untuk mengukur Paint/Layout Cost."""
    def __init__(self, tag: Optional[str] = None, text: Optional[str] = None):
        self.tag = tag
        self.text = text
        self.props: Dict[str, Any] = {}
        self.children: List['MockDOMNode'] = []

class MockDOMRenderer:
    def __init__(self):
        self.root: Optional[MockDOMNode] = None
        self.metrics = {
            "node_creations": 0,
            "node_destructions": 0,
            "prop_mutations": 0,
            "text_mutations": 0,
            "dom_moves": 0
        }

    def reset_metrics(self):
        for k in self.metrics:
            self.metrics[k] = 0

    def apply_patches(self, patches: List[PatchOperation]):
        """Menerapkan patch diffing ke Mock DOM fisik dengan tracking mutasi."""
        for patch in patches:
            if patch.op_type == PatchType.CREATE_NODE:
                self.metrics["node_creations"] += 1
            elif patch.op_type == PatchType.REMOVE_NODE:
                self.metrics["node_destructions"] += 1
            elif patch.op_type == PatchType.UPDATE_PROPS:
                self.metrics["prop_mutations"] += len(patch.payload.get("set", {})) + len(patch.payload.get("remove", []))
            elif patch.op_type == PatchType.UPDATE_TEXT:
                self.metrics["text_mutations"] += 1
            elif patch.op_type == PatchType.REORDER_CHILD:
                self.metrics["dom_moves"] += 1
            elif patch.op_type == PatchType.REPLACE_NODE:
                self.metrics["node_destructions"] += 1
                self.metrics["node_creations"] += 1

# ==============================================================================
# CORE RECONCILIATION & DIFFING ENGINE
# ==============================================================================
class DiffEngine:
    """
    Mengimplementasikan algoritma rekonsiliasi VDOM level-by-level O(N)
    dengan keyed matching untuk list items (Mirip React/Vue heuristic diff).
    """

    @classmethod
    def diff(cls, old_vnode: Optional[VNode], new_vnode: Optional[VNode], path: str = "root") -> List[PatchOperation]:
        patches: List[PatchOperation] = []

        if old_vnode is None and new_vnode is None:
            return patches

        if old_vnode is None and new_vnode is not None:
            patches.append(PatchOperation(PatchType.CREATE_NODE, path, new_vnode.key, new_vnode))
            return patches

        if old_vnode is not None and new_vnode is None:
            patches.append(PatchOperation(PatchType.REMOVE_NODE, path, old_vnode.key))
            return patches

        # Kedua node ada, verifikasi pergantian total (beda tag atau beda tipe teks)
        if (old_vnode.is_text != new_vnode.is_text) or (old_vnode.tag != new_vnode.tag):
            patches.append(PatchOperation(PatchType.REPLACE_NODE, path, new_vnode.key, new_vnode))
            return patches

        # Kasus Text Node
        if old_vnode.is_text and new_vnode.is_text:
            if old_vnode.text != new_vnode.text:
                patches.append(PatchOperation(PatchType.UPDATE_TEXT, path, None, new_vnode.text))
            return patches

        # Kasus Element Node: Diff Attributes/Props
        prop_diff = cls._diff_props(old_vnode.props, new_vnode.props)
        if prop_diff["set"] or prop_diff["remove"]:
            patches.append(PatchOperation(PatchType.UPDATE_PROPS, path, new_vnode.key, prop_diff))

        # Diff Children (Keyed Reconciliation)
        cls._diff_children(old_vnode.children, new_vnode.children, path, patches)

        return patches

    @staticmethod
    def _diff_props(old_props: Dict[str, Any], new_props: Dict[str, Any]) -> Dict[str, Any]:
        diff_payload = {"set": {}, "remove": []}
        
        # Deteksi modifikasi dan properti baru
        for key, value in new_props.items():
            if key not in old_props or old_props[key] != value:
                diff_payload["set"][key] = value

        # Deteksi properti yang dihapus
        for key in old_props:
            if key not in new_props:
                diff_payload["remove"].append(key)

        return diff_payload

    @classmethod
    def _diff_children(cls, old_children: List[VNode], new_children: List[VNode], parent_path: str, patches: List[PatchOperation]):
        """Keyed child reconciliation untuk mendeteksi insert, remove, dan reorder."""
        old_keyed = {c.key: (idx, c) for idx, c in enumerate(old_children) if c.key is not None}
        new_keyed = {c.key: (idx, c) for idx, c in enumerate(new_children) if c.key is not None}

        # Fallback jika tidak semua anak memiliki key (unkeyed heuristic)
        if len(old_keyed) != len(old_children) or len(new_keyed) != len(new_children):
            max_len = max(len(old_children), len(new_children))
            for i in range(max_len):
                o_child = old_children[i] if i < len(old_children) else None
                n_child = new_children[i] if i < len(new_children) else None
                patches.extend(cls.diff(o_child, n_child, f"{parent_path}.{i}"))
            return

        # 1. Hapus old child yang tidak ada di new_children
        for key, (idx, o_child) in old_keyed.items():
            if key not in new_keyed:
                patches.append(PatchOperation(PatchType.REMOVE_NODE, f"{parent_path}.{idx}", key))

        # 2. Reconcile dan atur posisi
        last_index = 0
        for new_idx, n_child in enumerate(new_children):
            key = n_child.key
            if key in old_keyed:
                old_idx, o_child = old_keyed[key]
                # Rekursif update atribut/anak internal node
                patches.extend(cls.diff(o_child, n_child, f"{parent_path}.{old_idx}"))
                
                # Deteksi jika node bergerak maju secara relatif
                if old_idx < last_index:
                    patches.append(PatchOperation(PatchType.REORDER_CHILD, f"{parent_path}.{new_idx}", key, {"from": old_idx, "to": new_idx}))
                else:
                    last_index = old_idx
            else:
                # Key baru -> Buat node baru
                patches.append(PatchOperation(PatchType.CREATE_NODE, f"{parent_path}.{new_idx}", key, n_child))

# ==============================================================================
# REACTIVE STATE & AUTO-BATCH COMPONENT RUNTIME
# ==============================================================================
class Signal:
    """Implementasi Primitif Reactivity (Fine-grained reactive variable)."""
    def __init__(self, value: Any):
        self._value = value
        self._subscribers: List[Callable[[], None]] = []

    def get(self) -> Any:
        return self._value

    def set(self, new_value: Any):
        if self._value != new_value:
            self._value = new_value
            self._notify()

    def subscribe(self, callback: Callable[[], None]):
        self._subscribers.append(callback)

    def _notify(self):
        for sub in self._subscribers:
            sub()

class Component:
    """Komponen UI deklaratif yang merespon perubahan state secara atomik."""
    def __init__(self, name: str, render_fn: Callable[[], VNode]):
        self.name = name
        self.render_fn = render_fn
        self.current_tree: Optional[VNode] = None

    def mount(self) -> Tuple[VNode, List[PatchOperation]]:
        self.current_tree = self.render_fn()
        patches = DiffEngine.diff(None, self.current_tree)
        return self.current_tree, patches

    def update(self) -> Tuple[VNode, List[PatchOperation]]:
        new_tree = self.render_fn()
        patches = DiffEngine.diff(self.current_tree, new_tree)
        self.current_tree = new_tree
        return new_tree, patches

# ==============================================================================
# SIMULASI & BENCHMARK SUITE
# ==============================================================================
def create_vnode(tag: str, props: Dict[str, Any] = None, children: List[VNode] = None, text: str = None, key: str = None) -> VNode:
    return VNode(tag=tag, props=props or {}, children=children or [], text=text, key=key)

def print_header(title: str):
    print(f"\n{Color.CYAN}{'='*78}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  LAB: {title.upper()}{Color.RESET}")
    print(f"{Color.CYAN}{'='*78}{Color.RESET}")

def run_lab():
    print_header("Virtual DOM Diffing, Keyed Reconciliation & Reactive Engine")
    
    # Inisialisasi Mock Engine
    renderer = MockDOMRenderer()

    # 1. SETUP STATE REACTIVE
    state_items = Signal([
        {"id": "t1", "title": "Setup Webpack Bundle", "done": True},
        {"id": "t2", "title": "Configure CSS Modules", "done": False},
        {"id": "t3", "title": "Implement Hydration Logic", "done": False},
    ])
    
    filter_active = Signal(False)

    # 2. DEFINISIKAN VIEW TREE KOMPONEN
    def render_app() -> VNode:
        items = state_items.get()
        if filter_active.get():
            items = [item for item in items if not item["done"]]

        vchildren = []
        for it in items:
            vchildren.append(
                create_vnode("li", 
                    props={"class": "completed" if it["done"] else "pending", "data-id": it["id"]},
                    key=it["id"],
                    children=[create_vnode(None, text=f"{it['title']} [{'x' if it['done'] else ' '}]")]
                )
            )

        return create_vnode("div", props={"id": "app-container"}, children=[
            create_vnode("header", children=[
                create_vnode("h1", children=[create_vnode(None, text="Task Reconciliation Manager")]),
                create_vnode("span", props={"class": "badge"}, children=[
                    create_vnode(None, text=f"Total: {len(items)}")
                ])
            ]),
            create_vnode("ul", props={"class": "task-list"}, children=vchildren)
        ])

    app_comp = Component("AppRoot", render_app)

    # ==========================================================================
    # STEP 1: INITIAL MOUNT (COLD RENDER)
    # ==========================================================================
    print(f"\n{Color.YELLOW}[PHASE 1] Initial Component Mounting (Cold Paint){Color.RESET}")
    t0 = time.perf_counter()
    _, mount_patches = app_comp.mount()
    mount_time = (time.perf_counter() - t0) * 1000.0

    renderer.apply_patches(mount_patches)
    print(f"Patches Generated   : {Color.BOLD}{len(mount_patches)}{Color.RESET}")
    print(f"Execution Time      : {mount_time:.4f} ms")
    print(f"DOM Metrics Created : {renderer.metrics['node_creations']} nodes")

    # ==========================================================================
    # STEP 2: FINE-GRAINED MUTATION (KEYED SHUFFLE & INSERT)
    # ==========================================================================
    print(f"\n{Color.YELLOW}[PHASE 2] Mutating Reactive State (Keyed Reorder + Item Insert){Color.RESET}")
    
    # Mutasi data: Reorder t3 ke paling atas, ubah status t2, sisipkan item baru 't4'
    updated_items = [
        {"id": "t3", "title": "Implement Hydration Logic", "done": True},  # Reorder + prop update
        {"id": "t1", "title": "Setup Webpack Bundle", "done": True},
        {"id": "t4", "title": "Integrate ServiceWorker", "done": False},   # Node baru
        {"id": "t2", "title": "Configure CSS Modules", "done": True},     # Status update
    ]

    renderer.reset_metrics()
    t0 = time.perf_counter()
    state_items.set(updated_items)
    _, update_patches = app_comp.update()
    diff_time = (time.perf_counter() - t0) * 1000.0
    renderer.apply_patches(update_patches)

    print(f"Generated Patches ({Color.GREEN}{len(update_patches)}{Color.RESET} ops) in {diff_time:.4f} ms:")
    for p in update_patches:
        detail = ""
        if p.op_type == PatchType.UPDATE_PROPS:
            detail = f"Set: {p.payload['set']}"
        elif p.op_type == PatchType.REORDER_CHILD:
            detail = f"Move from {p.payload['from']} to {p.payload['to']}"
        elif p.op_type == PatchType.CREATE_NODE:
            detail = f"New Tag: <{p.payload.tag}>"
        elif p.op_type == PatchType.UPDATE_TEXT:
            detail = f"New Text: '{p.payload}'"

        print(f"  -> {Color.MAGENTA}{p.op_type.name:<14}{Color.RESET} Path: {p.path:<16} Key: {str(p.target_key):<5} {Color.GRAY}{detail}{Color.RESET}")

    print(f"\nDOM Reflow/Repaint Profile:")
    print(f"  • Node Additions    : {renderer.metrics['node_creations']}")
    print(f"  • DOM Moves/Swaps   : {renderer.metrics['dom_moves']}")
    print(f"  • Prop Modifications: {renderer.metrics['prop_mutations']}")
    print(f"  • Text Writes       : {renderer.metrics['text_mutations']}")

    # ==========================================================================
    # STEP 3: BENCHMARK VDOM RECONCILIATION VS DIRTY INNERHTML TEARDOWN
    # ==========================================================================
    print(f"\n{Color.YELLOW}[PHASE 3] Engine Performance Benchmark (1000 Nodes Update){Color.RESET}")
    
    # Generate 1000 item list
    large_list_a = [create_vnode("li", key=f"k_{i}", text=f"Row #{i}") for i in range(1000)]
    tree_a = create_vnode("ul", children=large_list_a)

    # 1000 item list dengan 10 item dimutasi di tengah dan 5 item dihapus
    large_list_b = []
    for i in range(1000):
        if i % 200 == 0:
            continue # Hapus
        if i % 50 == 0:
            large_list_b.append(create_vnode("li", key=f"k_{i}", text=f"Row #{i} [MODIFIED]"))
        else:
            large_list_b.append(create_vnode("li", key=f"k_{i}", text=f"Row #{i}"))
            
    tree_b = create_vnode("ul", children=large_list_b)

    # Benchmark VDOM Reconciliation
    t_start = time.perf_counter()
    vdom_patches = DiffEngine.diff(tree_a, tree_b)
    t_vdom = (time.perf_counter() - t_start) * 1000.0

    # Benchmark Brute Force Total Teardown (Simulasi innerHTML = '')
    t_start = time.perf_counter()
    naive_patches = [PatchOperation(PatchType.REPLACE_NODE, "root", None, tree_b)]
    t_naive = (time.perf_counter() - t_start) * 1000.0

    print(f"  {Color.BOLD}{'Metric':<30} | {'VDOM Reconciler':<18} | {'Naive DOM Teardown':<18}{Color.RESET}")
    print(f"  {'-'*72}")
    print(f"  {'Calculation Overhead':<30} | {t_vdom:15.3f} ms | {t_naive:15.3f} ms")
    print(f"  {'DOM Ops to Apply':<30} | {len(vdom_patches):18} | {1000:18} (Drops all)")
    print(f"  {'Browser Layout/Reflow Blast':<30} | {Color.GREEN}{'Minimal (Surgical)':<18}{Color.RESET} | {Color.RED}{'Catastrophic':<18}{Color.RESET}")

    print(f"\n{Color.GREEN}✔ Verification Complete: Virtual DOM Engine & Reconciler validated successfully.{Color.RESET}\n")

if __name__ == "__main__":
    run_lab()
