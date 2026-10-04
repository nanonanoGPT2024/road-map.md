#!/usr/bin/env python3
"""
Lab Hands-on: Frontend Engineering Deep Dive
Modul: Virtual DOM Architecture, Reconciliation Algorithm, and Reactive Rendering Engine.

Mendemonstrasikan:
1. Virtual DOM representation (AST-like tree node).
2. Fiber-like Tree Reconciliation Diffing Algorithm (Keyed Children Diffing).
3. Patch calculation (CREATE, REMOVE, REPLACE, UPDATE_PROPS, TEXT_MUTATION).
4. Real DOM simulation with Mutation Tracking & Performance Cost Analysis vs Naive innerHTML.
"""

from __future__ import annotations
import sys
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

# Terminal ANSI Color Formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class PatchType(Enum):
    """Tipe mutasi DOM yang dihasilkan oleh proses diffing reconciliation."""
    NOOP = auto()
    CREATE = auto()
    REMOVE = auto()
    REPLACE = auto()
    UPDATE_PROPS = auto()
    UPDATE_TEXT = auto()
    REORDER = auto()


@dataclass
class Patch:
    """Instruksi atomic perbaikan untuk diterapkan pada Real DOM."""
    patch_type: PatchType
    path: List[int]  # Indeks jalur traversal pada pohon DOM (e.g. [0, 1] -> child 1 dari child 0)
    old_node: Optional[VNode] = None
    new_node: Optional[VNode] = None
    props_diff: Dict[str, Any] = field(default_factory=dict)
    text_content: Optional[str] = None


class VNode:
    """
    Virtual DOM Node: Representasi ringan in-memory dari elemen UI.
    Tidak memiliki referensi native C++ browser DOM API, sehingga komputasi sangat cepat.
    """
    def __init__(
        self,
        tag: str,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List[VNode | str]] = None,
        key: Optional[str] = None
    ):
        self.tag = tag
        self.props = props or {}
        self.key = key or self.props.get("key")
        self.children: List[VNode] = []
        
        if children:
            for child in children:
                if isinstance(child, str):
                    self.children.append(VNode("#text", props={"nodeValue": child}))
                elif isinstance(child, VNode):
                    self.children.append(child)

    @property
    def is_text_node(self) -> bool:
        return self.tag == "#text"

    def __repr__(self) -> str:
        if self.is_text_node:
            return f'"{self.props.get("nodeValue", "")}"'
        key_str = f" key='{self.key}'" if self.key else ""
        return f"<{self.tag}{key_str}> (children: {len(self.children)})"


def h(tag: str, props: Optional[Dict[str, Any]] = None, *children: VNode | str) -> VNode:
    """Helper function (HyperScript) untuk memudahkan pembuatan Virtual DOM tree."""
    return VNode(tag=tag, props=props, children=list(children))


class RealDOMNode:
    """
    Simulasi elemen Real DOM native browser.
    Mencatat metrik mutasi aktual (Reflow & Repaint footprint).
    """
    total_mutations = 0
    dom_write_cost_us = 120  # Estimasi latency mikrosekon per operasi mutasi native DOM

    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None):
        self.tag = tag
        self.props = props or {}
        self.children: List[RealDOMNode] = []
        RealDOMNode.total_mutations += 1

    def append_child(self, child: RealDOMNode):
        RealDOMNode.total_mutations += 1
        self.children.append(child)

    def remove_child_at(self, index: int) -> RealDOMNode:
        RealDOMNode.total_mutations += 1
        return self.children.pop(index)

    def replace_child_at(self, index: int, new_child: RealDOMNode):
        RealDOMNode.total_mutations += 2
        self.children[index] = new_child

    def update_prop(self, key: str, value: Any):
        RealDOMNode.total_mutations += 1
        if value is None and key in self.props:
            del self.props[key]
        else:
            self.props[key] = value

    def to_string(self, depth: int = 0) -> str:
        indent = "  " * depth
        if self.tag == "#text":
            return f"{indent}{GREEN}{self.props.get('nodeValue', '')}{RESET}"
        
        props_str = " ".join(f'{k}="{v}"' for k, v in self.props.items())
        opening = f"{indent}<{CYAN}{self.tag}{RESET}{' ' + props_str if props_str else ''}>"
        
        if not self.children:
            return f"{opening}</{CYAN}{self.tag}{RESET}>"
        
        child_renders = [c.to_string(depth + 1) for c in self.children]
        closing = f"{indent}</{CYAN}{self.tag}{RESET}>"
        return f"{opening}\n" + "\n".join(child_renders) + f"\n{closing}"


class Reconciler:
    """
    Mesin diffing O(N) dengan keyed heuristic matching (mirip implementasi React / Vue core).
    Membandingkan Old VNode tree dengan New VNode tree dan menghasilkan Patch set.
    """
    def diff(self, old_node: Optional[VNode], new_node: Optional[VNode], path: List[int]) -> List[Patch]:
        patches: List[Patch] = []

        # Kasus 1: Node lama dihapus
        if old_node and not new_node:
            patches.append(Patch(PatchType.REMOVE, path=path, old_node=old_node))
            return patches

        # Kasus 2: Node baru ditambahkan
        if not old_node and new_node:
            patches.append(Patch(PatchType.CREATE, path=path, new_node=new_node))
            return patches

        if not old_node or not new_node:
            return patches

        # Kasus 3: Node diganti total (Tag berbeda atau tipe text berubah)
        if old_node.tag != new_node.tag:
            patches.append(Patch(PatchType.REPLACE, path=path, old_node=old_node, new_node=new_node))
            return patches

        # Kasus 4: Node Text berubah nilainya
        if old_node.is_text_node and new_node.is_text_node:
            old_val = old_node.props.get("nodeValue")
            new_val = new_node.props.get("nodeValue")
            if old_val != new_val:
                patches.append(Patch(PatchType.UPDATE_TEXT, path=path, text_content=new_val))
            return patches

        # Kasus 5: Props diffing (Atribut & event listeners)
        props_diff = self._diff_props(old_node.props, new_node.props)
        if props_diff:
            patches.append(Patch(PatchType.UPDATE_PROPS, path=path, props_diff=props_diff))

        # Kasus 6: Children reconciliation (Key-aware)
        children_patches = self._diff_children(old_node.children, new_node.children, path)
        patches.extend(children_patches)

        return patches

    def _diff_props(self, old_props: Dict[str, Any], new_props: Dict[str, Any]) -> Dict[str, Any]:
        """Menemukan properti yang berubah, bertambah, atau dihapus (None)."""
        diff = {}
        for key, val in new_props.items():
            if old_props.get(key) != val:
                diff[key] = val
        for key in old_props:
            if key not in new_props:
                diff[key] = None
        return diff

    def _diff_children(self, old_children: List[VNode], new_children: List[VNode], parent_path: List[int]) -> List[Patch]:
        """
        Reconciliation berbobot berbasis Key untuk meminimalkan DOM Thrashing saat reordering/insert.
        """
        patches: List[Patch] = []
        old_keyed = {c.key: (i, c) for i, c in enumerate(old_children) if c.key is not None}
        new_keyed = {c.key: (i, c) for i, c in enumerate(new_children) if c.key is not None}

        # Fallback ke index-based matching jika anak-anak tidak memakai key
        if len(old_keyed) == 0 and len(new_keyed) == 0:
            max_len = max(len(old_children), len(new_children))
            for i in range(max_len):
                o_child = old_children[i] if i < len(old_children) else None
                n_child = new_children[i] if i < len(new_children) else None
                patches.extend(self.diff(o_child, n_child, parent_path + [i]))
            return patches

        # Key-based Diffing:
        # Step A: Deteksi elemen yang dihapus
        for key, (idx, node) in old_keyed.items():
            if key not in new_keyed:
                patches.append(Patch(PatchType.REMOVE, path=parent_path + [idx], old_node=node))

        # Step B: Deteksi elemen baru atau yang diupdate
        for key, (idx, node) in new_keyed.items():
            if key in old_keyed:
                old_idx, old_child = old_keyed[key]
                child_patches = self.diff(old_child, node, parent_path + [idx])
                patches.extend(child_patches)
            else:
                patches.append(Patch(PatchType.CREATE, path=parent_path + [idx], new_node=node))

        return patches


class DOMRenderer:
    """Menerapkan VNode awal ke RealDOM dan mem-patch mutasi berikutnya."""
    
    @staticmethod
    def mount(vnode: VNode) -> RealDOMNode:
        """Membuat Real DOM tree baru dari Virtual DOM tree."""
        real_node = RealDOMNode(vnode.tag, dict(vnode.props))
        for child in vnode.children:
            real_node.append_child(DOMRenderer.mount(child))
        return real_node

    @staticmethod
    def patch_dom(root: RealDOMNode, patches: List[Patch]):
        """Mengaplikasikan instruksi diff langsung ke node Real DOM target."""
        for patch in patches:
            target = DOMRenderer._resolve_path(root, patch.path)
            
            if patch.patch_type == PatchType.UPDATE_TEXT:
                target.props["nodeValue"] = patch.text_content
                RealDOMNode.total_mutations += 1

            elif patch.patch_type == PatchType.UPDATE_PROPS:
                for k, v in patch.props_diff.items():
                    target.update_prop(k, v)

            elif patch.patch_type == PatchType.REPLACE:
                parent = DOMRenderer._resolve_parent(root, patch.path)
                idx = patch.path[-1]
                parent.replace_child_at(idx, DOMRenderer.mount(patch.new_node))

            elif patch.patch_type == PatchType.REMOVE:
                parent = DOMRenderer._resolve_parent(root, patch.path)
                idx = patch.path[-1]
                if idx < len(parent.children):
                    parent.remove_child_at(idx)

            elif patch.patch_type == PatchType.CREATE:
                parent = DOMRenderer._resolve_parent(root, patch.path)
                parent.append_child(DOMRenderer.mount(patch.new_node))

    @staticmethod
    def _resolve_path(root: RealDOMNode, path: List[int]) -> RealDOMNode:
        curr = root
        for idx in path:
            if idx < len(curr.children):
                curr = curr.children[idx]
        return curr

    @staticmethod
    def _resolve_parent(root: RealDOMNode, path: List[int]) -> RealDOMNode:
        curr = root
        for idx in path[:-1]:
            curr = curr.children[idx]
        return curr


def simulate_lab():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}   HANDS-ON LAB: DEEP DIVE FRONTEND RECONCILIATION & VIRTUAL DOM      {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    reconciler = Reconciler()

    # 1. State Awal: Komponen Data Feed
    print(f"{BOLD}[1] INITIAL RENDER (Mounting Initial State){RESET}")
    old_vdom = h(
        "div", {"id": "app-container", "class": "dark-theme"},
        h("header", {}, h("h1", {}, "Task Monitoring Feed")),
        h(
            "ul", {"class": "task-list"},
            h("li", {"key": "t-101", "class": "task-item"}, "Task 101: Init WebWorker Sync"),
            h("li", {"key": "t-102", "class": "task-item"}, "Task 102: Preload Critical Chunk"),
            h("li", {"key": "t-103", "class": "task-item"}, "Task 103: Evaluate Frame Budget")
        ),
        h("footer", {}, "System Status: Nominal")
    )

    t0 = time.perf_counter_ns()
    real_dom = DOMRenderer.mount(old_vdom)
    mount_time_us = (time.perf_counter_ns() - t0) / 1000
    initial_mutations = RealDOMNode.total_mutations

    print(f"{DIM}Initial Tree Structure:{RESET}")
    print(real_dom.to_string())
    print(f"\nReal DOM Initial Mutations: {YELLOW}{initial_mutations}{RESET} operations")
    print(f"Mount Execution Time:       {YELLOW}{mount_time_us:.2f} µs{RESET}\n")

    # 2. State Mutasi: Update item, Hapus item, Tambah item baru dengan Keyed Diff
    print(f"{BOLD}----------------------------------------------------------------------{RESET}")
    print(f"{BOLD}[2] STATE MUTATION & RECONCILIATION PROCESS{RESET}")
    print(f"{DIM}Mutasi yang terjadi:{RESET}")
    print(f"  • Item 't-102' dihapus (Selesai)")
    print(f"  • Item 't-101' diubah teksnya (Proses -> Sukses)")
    print(f"  • Item 't-104' ditambahkan ke daftar tugas")
    print(f"  • Footer status berubah 'Nominal' -> 'Updated'")

    new_vdom = h(
        "div", {"id": "app-container", "class": "dark-theme"},
        h("header", {}, h("h1", {}, "Task Monitoring Feed")),
        h(
            "ul", {"class": "task-list"},
            # t-101 dimodifikasi teksnya
            h("li", {"key": "t-101", "class": "task-item resolved"}, "Task 101: WebWorker Sync [OK]"),
            # t-102 dihapus
            # t-103 tetap ada
            h("li", {"key": "t-103", "class": "task-item"}, "Task 103: Evaluate Frame Budget"),
            # t-104 node baru ditambahkan
            h("li", {"key": "t-104", "class": "task-item new"}, "Task 104: Drain GC Allocations")
        ),
        h("footer", {}, "System Status: Updated")
    )

    # Menghitung diff patches
    t_diff_start = time.perf_counter_ns()
    patches = reconciler.diff(old_vdom, new_vdom, path=[])
    diff_duration_us = (time.perf_counter_ns() - t_diff_start) / 1000

    print(f"\n{BOLD}Generated Atomic Patches ({len(patches)} ops):{RESET}")
    for idx, p in enumerate(patches, 1):
        color = GREEN if p.patch_type == PatchType.CREATE else (RED if p.patch_type == PatchType.REMOVE else MAGENTA)
        print(f"  {idx}. Type: {color}{p.patch_type.name:<14}{RESET} Path: {p.path} Detail: {p.props_diff or p.text_content or p.new_node or p.old_node}")

    # Mengaplikasikan patch ke Real DOM
    mutations_before_patch = RealDOMNode.total_mutations
    t_patch_start = time.perf_counter_ns()
    DOMRenderer.patch_dom(real_dom, patches)
    patch_duration_us = (time.perf_counter_ns() - t_patch_start) / 1000
    delta_mutations = RealDOMNode.total_mutations - mutations_before_patch

    print(f"\n{BOLD}[3] REAL DOM POST-PATCH STATE:{RESET}")
    print(real_dom.to_string())

    # 3. Analisis Efisiensi: Virtual DOM vs Naive Full Re-render (innerHTML)
    print(f"\n{BOLD}----------------------------------------------------------------------{RESET}")
    print(f"{BOLD}[4] PERFORMANCE & EFFICIENCY BENCHMARK ANALYSIS{RESET}")
    
    # Hitung estimasi jika menggunakan naive innerHTML replacement
    # Naive re-render menghancurkan seluruh subtree dan membuat ulang semua elemen (11 nodes)
    naive_total_nodes = 11
    naive_mutations = naive_total_nodes * 2  # Discard + Recreation
    vdom_saved_mutations = naive_mutations - delta_mutations
    efficiency_gain = (vdom_saved_mutations / naive_mutations) * 100

    print(f"Diff Algorithm Latency:        {CYAN}{diff_duration_us:.3f} µs{RESET}")
    print(f"DOM Patch Latency:             {CYAN}{patch_duration_us:.3f} µs{RESET}")
    print(f"Actual Targeted DOM Mutations: {GREEN}{delta_mutations} operations{RESET}")
    print(f"Naive innerHTML Re-render Ops: {RED}{naive_mutations} operations{RESET}")
    print(f"Eliminated DOM Thrashing:      {YELLOW}{vdom_saved_mutations} operations ({efficiency_gain:.1f}% reduction){RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")


if __name__ == "__main__":
    simulate_lab()
03-Frontend-and-Mobile/06-Bab-06-Modul-02-Deep-Dive/lab_reconciler_advanced.py
#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Frontend Reconciliation Engine
Modul: Virtual DOM Architecture, Double-Buffering Fiber Tree, & Concurrent Reconciler Simulation.

Mendemonstrasikan:
1. Virtual DOM AST Representation with Component Fiber Nodes.
2. Two-Pass Reconciliation: Work Loop (Render Phase) & Commit Phase.
3. List Reconciliation with Longest Increasing Subsequence (LIS) Heuristic.
4. Mutation Cost Benchmark: Surgical Keyed Reconciliation vs Dirty Subtree Re-render.
"""

from __future__ import annotations
import sys
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

# Terminal Styling Constants
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class EffectTag(Enum):
    """Flags instruksi mutasi commit phase (Fiber architecture parity)."""
    PLACEMENT = auto()
    UPDATE = auto()
    DELETION = auto()
    MOVE = auto()
    NOOP = auto()


@dataclass
class VNode:
    """Virtual Node representing immutable UI Blueprint."""
    tag: str
    props: Dict[str, Any] = field(default_factory=dict)
    key: Optional[str] = None
    children: List[VNode] = field(default_factory=list)
    text_content: Optional[str] = None

    @property
    def is_text(self) -> bool:
        return self.tag == "#text"

    def __repr__(self) -> str:
        if self.is_text:
            return f'"{self.text_content}"'
        k = f" key='{self.key}'" if self.key else ""
        return f"<{self.tag}{k}> ({len(self.children)} children)"


def h(tag: str, props: Optional[Dict[str, Any]] = None, *children: VNode | str, key: Optional[str] = None) -> VNode:
    """Hyperscript factory function."""
    props = props or {}
    derived_key = key or props.get("key")
    v_children: List[VNode] = []
    
    for c in children:
        if isinstance(c, str):
            v_children.append(VNode(tag="#text", text_content=c))
        elif isinstance(c, VNode):
            v_children.append(c)
            
    return VNode(tag=tag, props=props, key=str(derived_key) if derived_key else None, children=v_children)


class RealDOMNode:
    """Simulated Native Browser DOM Node with Performance Metrics Tracking."""
    total_dom_ops = 0

    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None, text_content: Optional[str] = None):
        self.tag = tag
        self.props = props or {}
        self.text_content = text_content
        self.children: List[RealDOMNode] = []
        RealDOMNode.total_dom_ops += 1

    def append_child(self, child: RealDOMNode):
        RealDOMNode.total_dom_ops += 1
        self.children.append(child)

    def insert_before(self, new_child: RealDOMNode, index: int):
        RealDOMNode.total_dom_ops += 1
        self.children.insert(index, new_child)

    def remove_at(self, index: int) -> RealDOMNode:
        RealDOMNode.total_dom_ops += 1
        return self.children.pop(index)

    def set_attribute(self, key: str, value: Any):
        RealDOMNode.total_dom_ops += 1
        if value is None:
            self.props.pop(key, None)
        else:
            self.props[key] = value

    def to_tree_view(self, depth: int = 0) -> str:
        indent = "  " * depth
        if self.tag == "#text":
            return f"{indent}{GREEN}{self.text_content}{RESET}"
        
        attrs = " ".join(f'{k}="{v}"' for k, v in self.props.items())
        tag_open = f"{indent}<{CYAN}{self.tag}{RESET}{' ' + attrs if attrs else ''}>"
        
        if not self.children:
            return f"{tag_open}</{CYAN}{self.tag}{RESET}>"
        
        body = "\n".join(c.to_tree_view(depth + 1) for c in self.children)
        return f"{tag_open}\n{body}\n{indent}</{CYAN}{self.tag}{RESET}>"


@dataclass
class FiberWorkItem:
    """Atomic task description during Render Phase."""
    effect: EffectTag
    parent_path: List[int]
    target_index: int
    old_vnode: Optional[VNode] = None
    new_vnode: Optional[VNode] = None
    prop_changes: Dict[str, Any] = field(default_factory=dict)
    text_mutation: Optional[str] = None


class AdvancedReconciler:
    """
    Two-pass Reconciliation Engine (Render/Diff Phase -> Commit Phase).
    Utilizes Key-Map Indexing and LIS-based minimal displacement detection.
    """
    
    @staticmethod
    def get_lis_indices(arr: List[int]) -> List[int]:
        """
        Calculates Longest Increasing Subsequence indices in O(N log N).
        Used by modern frameworks (e.g. Vue 3) to minimize DOM moves.
        """
        if not arr:
            return []
        
        n = len(arr)
        tails = [0] * n
        tails_indices = [0] * n
        parent = [-1] * n
        length = 0

        for i in range(n):
            val = arr[i]
            if val < 0:
                continue

            low, high = 0, length
            while low < high:
                mid = (low + high) // 2
                if tails[mid] < val:
                    low = mid + 1
                else:
                    high = mid

            tails[low] = val
            tails_indices[low] = i
            if low > 0:
                parent[i] = tails_indices[low - 1]

            if low == length:
                length += 1

        result = []
        curr = tails_indices[length - 1] if length > 0 else -1
        while curr >= 0:
            result.append(curr)
            curr = parent[curr]
            
        return result[::-1]

    def render_phase(self, old_root: Optional[VNode], new_root: Optional[VNode]) -> List[FiberWorkItem]:
        """Phase 1: Pure functional computation with zero DOM mutations."""
        work_list: List[FiberWorkItem] = []
        self._diff_nodes(old_root, new_root, path=[], work_list=work_list)
        return work_list

    def _diff_nodes(
        self,
        old_n: Optional[VNode],
        new_n: Optional[VNode],
        path: List[int],
        work_list: List[FiberWorkItem]
    ):
        if not old_n and new_n:
            work_list.append(FiberWorkItem(
                effect=EffectTag.PLACEMENT,
                parent_path=path[:-1],
                target_index=path[-1] if path else 0,
                new_vnode=new_n
            ))
            return

        if old_n and not new_n:
            work_list.append(FiberWorkItem(
                effect=EffectTag.DELETION,
                parent_path=path[:-1],
                target_index=path[-1] if path else 0,
                old_vnode=old_n
            ))
            return

        if not old_n or not new_n:
            return

        # Replace completely if tags differ
        if old_n.tag != new_n.tag:
            work_list.append(FiberWorkItem(
                effect=EffectTag.DELETION,
                parent_path=path[:-1],
                target_index=path[-1] if path else 0,
                old_vnode=old_n
            ))
            work_list.append(FiberWorkItem(
                effect=EffectTag.PLACEMENT,
                parent_path=path[:-1],
                target_index=path[-1] if path else 0,
                new_vnode=new_n
            ))
            return

        # Text Node reconciliation
        if old_n.is_text and new_n.is_text:
            if old_n.text_content != new_n.text_content:
                work_list.append(FiberWorkItem(
                    effect=EffectTag.UPDATE,
                    parent_path=path[:-1],
                    target_index=path[-1] if path else 0,
                    text_mutation=new_n.text_content
                ))
            return

        # Attribute and Prop Diffing
        prop_diff = self._diff_props(old_n.props, new_n.props)
        if prop_diff:
            work_list.append(FiberWorkItem(
                effect=EffectTag.UPDATE,
                parent_path=path[:-1],
                target_index=path[-1] if path else 0,
                prop_changes=prop_diff
            ))

        # Children reconciliation
        self._reconcile_children(old_n.children, new_n.children, path, work_list)

    def _diff_props(self, old_p: Dict[str, Any], new_p: Dict[str, Any]) -> Dict[str, Any]:
        diff = {}
        for k, v in new_p.items():
            if old_p.get(k) != v:
                diff[k] = v
        for k in old_p:
            if k not in new_p:
                diff[k] = None
        return diff

    def _reconcile_children(
        self,
        old_ch: List[VNode],
        new_ch: List[VNode],
        parent_path: List[int],
        work_list: List[FiberWorkItem]
    ):
        """Advanced keyed list reconciliation with LIS-driven placement detection."""
        old_map: Dict[str, Tuple[int, VNode]] = {c.key: (i, c) for i, c in enumerate(old_ch) if c.key}
        new_map: Dict[str, Tuple[int, VNode]] = {c.key: (i, c) for i, c in enumerate(new_ch) if c.key}

        # Non-keyed fallback: sequential 1:1 diffing
        if not old_map and not new_map:
            max_len = max(len(old_ch), len(new_ch))
            for i in range(max_len):
                o = old_ch[i] if i < len(old_ch) else None
                n = new_ch[i] if i < len(new_ch) else None
                self._diff_nodes(o, n, parent_path + [i], work_list)
            return

        # Step 1: Remove unmounted keys
        for key, (o_idx, o_node) in old_map.items():
            if key not in new_map:
                work_list.append(FiberWorkItem(
                    effect=EffectTag.DELETION,
                    parent_path=parent_path,
                    target_index=o_idx,
                    old_vnode=o_node
                ))

        # Step 2: Track movement indices for LIS calculation
        index_mapping = [-1] * len(new_ch)
        for n_idx, n_node in enumerate(new_ch):
            if n_node.key and n_node.key in old_map:
                o_idx, o_node = old_map[n_node.key]
                index_mapping[n_idx] = o_idx
                # Recursive sub-tree update
                self._diff_nodes(o_node, n_node, parent_path + [n_idx], work_list)
            else:
                work_list.append(FiberWorkItem(
                    effect=EffectTag.PLACEMENT,
                    parent_path=parent_path,
                    target_index=n_idx,
                    new_vnode=n_node
                ))

        # Step 3: Compute stable sub-sequence to prevent redundant moves
        lis_stable_indices = set(self.get_lis_indices(index_mapping))

        for n_idx, o_idx in enumerate(index_mapping):
            if o_idx != -1 and n_idx not in lis_stable_indices:
                work_list.append(FiberWorkItem(
                    effect=EffectTag.MOVE,
                    parent_path=parent_path,
                    target_index=n_idx,
                    new_vnode=new_ch[n_idx]
                ))

    def commit_phase(self, root: RealDOMNode, work_list: List[FiberWorkItem]):
        """Phase 2: Synchronous execution of minimal native DOM side-effects."""
        for item in work_list:
            parent = self._resolve_target(root, item.parent_path)
            
            if item.effect == EffectTag.UPDATE:
                target = parent if not item.parent_path else parent.children[item.target_index]
                if item.text_mutation is not None:
                    target.text_content = item.text_mutation
                    RealDOMNode.total_dom_ops += 1
                for k, v in item.prop_changes.items():
                    target.set_attribute(k, v)

            elif item.effect == EffectTag.DELETION:
                if item.target_index < len(parent.children):
                    parent.remove_at(item.target_index)

            elif item.effect == EffectTag.PLACEMENT and item.new_vnode:
                new_dom = self._instantiate_dom(item.new_vnode)
                if item.target_index >= len(parent.children):
                    parent.append_child(new_dom)
                else:
                    parent.insert_before(new_dom, item.target_index)

            elif item.effect == EffectTag.MOVE and item.new_vnode:
                # Optimized DOM displacement
                if item.target_index < len(parent.children):
                    moved_node = parent.remove_at(item.target_index)
                    parent.insert_before(moved_node, item.target_index)

    def _instantiate_dom(self, vnode: VNode) -> RealDOMNode:
        dom = RealDOMNode(tag=vnode.tag, props=dict(vnode.props), text_content=vnode.text_content)
        for child in vnode.children:
            dom.append_child(self._instantiate_dom(child))
        return dom

    def _resolve_target(self, root: RealDOMNode, path: List[int]) -> RealDOMNode:
        curr = root
        for idx in path:
            if idx < len(curr.children):
                curr = curr.children[idx]
        return curr


def run_benchmark():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}    ADVANCED FRONTEND LAB: FIBER WORK-LOOP & LIS RECONCILIATION       {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    reconciler = AdvancedReconciler()

    # Initial State Definition
    print(f"{BOLD}[PHASE 1] Initial Mount & Tree Generation{RESET}")
    initial_vdom = h(
        "div", {"id": "viewport", "class": "terminal-ui"},
        h("nav", {"role": "navigation"}, h("span", {}, "DevTools Inspector")),
        h(
            "section", {"class": "metrics-grid"},
            h("div", {"class": "card"}, "FPS: 60.0", key="card-fps"),
            h("div", {"class": "card"}, "Heap: 42MB", key="card-heap"),
            h("div", {"class": "card"}, "DOM Nodes: 182", key="card-dom"),
            h("div", {"class": "card"}, "Threads: 4", key="card-threads")
        ),
        h("footer", {}, "Status: Monitoring Active")
    )

    t0 = time.perf_counter_ns()
    simulated_dom = reconciler._instantiate_dom(initial_vdom)
    mount_latency_us = (time.perf_counter_ns() - t0) / 1000
    initial_ops = RealDOMNode.total_dom_ops

    print(f"{DIM}Rendered Initial DOM Layout:{RESET}")
    print(simulated_dom.to_tree_view())
    print(f"\nMount Operations: {YELLOW}{initial_ops}{RESET} ops | Latency: {YELLOW}{mount_latency_us:.2f} µs{RESET}\n")

    # High-Velocity Mutation Scenario:
    # 1. Reorder cards (card-dom moved ahead)
    # 2. Update Heap reading
    # 3. Remove Threads card
    # 4. Insert Network Latency card
    print(f"{BOLD}----------------------------------------------------------------------{RESET}")
    print(f"{BOLD}[PHASE 2] High-Velocity State Dispatch{RESET}")
    print(f"{DIM}Plan Mutasi:{RESET}")
    print(f"  [-] Hapus key 'card-threads'")
    print(f"  [*] Mutasi nilai Heap: 42MB -> 56MB")
    print(f"  [+] Sisipkan card baru: 'card-net' (Latency: 14ms)")
    print(f"  [~] Reorder posisi: 'card-dom' digeser ke posisi pertama")

    mutated_vdom = h(
        "div", {"id": "viewport", "class": "terminal-ui"},
        h("nav", {"role": "navigation"}, h("span", {}, "DevTools Inspector")),
        h(
            "section", {"class": "metrics-grid"},
            h("div", {"class": "card highlighted"}, "DOM Nodes: 185", key="card-dom"),
            h("div", {"class": "card"}, "FPS: 60.0", key="card-fps"),
            h("div", {"class": "card warning"}, "Heap: 56MB", key="card-heap"),
            h("div", {"class": "card"}, "Network: 14ms", key="card-net")
        ),
        h("footer", {}, "Status: High Pressure Detected")
    )

    # Execute Render Phase (Diffing)
    t_render = time.perf_counter_ns()
    work_list = reconciler.render_phase(initial_vdom, mutated_vdom)
    render_time_us = (time.perf_counter_ns() - t_render) / 1000

    print(f"\n{BOLD}Render Phase Work List ({len(work_list)} Atomic Side-Effects Detected):{RESET}")
    for idx, w in enumerate(work_list, 1):
        color = GREEN if w.effect == EffectTag.PLACEMENT else (RED if w.effect == EffectTag.DELETION else MAGENTA)
        print(f"  {idx}. Effect: {color}{w.effect.name:<11}{RESET} Index: {w.target_index} Context: {w.prop_changes or w.text_mutation or w.new_vnode or w.old_vnode}")

    # Execute Commit Phase (DOM Side-Effects)
    ops_before_commit = RealDOMNode.total_dom_ops
    t_commit = time.perf_counter_ns()
    reconciler.commit_phase(simulated_dom, work_list)
    commit_time_us = (time.perf_counter_ns() - t_commit) / 1000
    committed_ops = RealDOMNode.total_dom_ops - ops_before_commit

    print(f"\n{BOLD}[PHASE 3] Final Real DOM Tree Post-Commit:{RESET}")
    print(simulated_dom.to_tree_view())

    # Architectural Cost Profiling
    print(f"\n{BOLD}----------------------------------------------------------------------{RESET}")
    print(f"{BOLD}[PHASE 4] Cost Profiling vs Naive Full Replacement (innerHTML){RESET}")

    # Total nodes in mutated tree: 14 nodes (div + nav + span + text + section + 4 cards*2 + footer + text)
    naive_destructive_ops = 14 * 2  # Complete unmount and reconstruction
    ops_saved = naive_destructive_ops - committed_ops
    gain_pct = (ops_saved / naive_destructive_ops) * 100

    print(f"Concurrent Render/Diff Time: {CYAN}{render_time_us:.3f} µs{RESET}")
    print(f"Commit Phase Execution Time: {CYAN}{commit_time_us:.3f} µs{RESET}")
    print(f"Surgical DOM Modifications:  {GREEN}{committed_ops} ops{RESET}")
    print(f"Naive Full-Rebuild Cost:     {RED}{naive_destructive_ops} ops{RESET}")
    print(f"Browser Reflow/Paint Saved:  {YELLOW}{ops_saved} ops ({gain_pct:.1f}% reduction){RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")


if __name__ == "__main__":
    run_benchmark()