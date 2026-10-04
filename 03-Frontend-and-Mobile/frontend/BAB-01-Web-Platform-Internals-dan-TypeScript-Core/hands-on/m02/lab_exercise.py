#!/usr/bin/env python3
"""
Lab Hands-on: Frontend Engineering Deep Dive
Topik: Virtual DOM (VDOM) Tree Reconciliation & Differential Patching Engine
Kategori: 03-Frontend-and-Mobile (Bab 01 - Modul 02)

Deskripsi:
Script ini mengimplementasikan simulasi engine inti framework frontend modern:
1. Virtual DOM (VDOM) tree representation dengan props, key, dan hierarchical children.
2. Heuristic Tree Diffing Algorithm (O(N) reconciliation) untuk mendeteksi CREATE,
   REMOVE, REPLACE, dan UPDATE_PROPS.
3. Patch Engine yang mengeksekusi mutasi minimal ke Real DOM tiruan.
4. Metric Tracker yang membandingkan efisiensi patch terarah vs destruktif re-render (naive).
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional
import json
import time

# --- ANSI Terminal Color Formatting ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"


class PatchType(Enum):
    CREATE = auto()
    REMOVE = auto()
    REPLACE = auto()
    UPDATE_PROPS = auto()
    CHILDREN_UPDATE = auto()


@dataclass
class Patch:
    """Mewakili instruksi mutasi atomik yang diaplikasikan ke Real DOM."""
    patch_type: PatchType
    node_id: str
    props: Optional[Dict[str, Any]] = None
    new_vnode: Optional['VNode'] = None
    child_patches: List['Patch'] = field(default_factory=list)


class VNode:
    """Virtual DOM Node murni (in-memory, lightweight object)."""
    def __init__(
        self,
        tag: str,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List['VNode']] = None,
        text: Optional[str] = None,
        key: Optional[str] = None
    ):
        self.tag = tag
        self.props = props or {}
        self.children = children or []
        self.text = text
        self.key = key or self.props.get("id")

    def to_dict(self) -> Dict[str, Any]:
        """Konversi struktural ke format serializable untuk debugging visual."""
        d: Dict[str, Any] = {"tag": self.tag}
        if self.props:
            d["props"] = self.props
        if self.text is not None:
            d["text"] = self.text
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


class RealDOMNode:
    """Simulasi Node pada Browser DOM asli yang mahal untuk dimutasi."""
    def __init__(self, tag: str, props: Optional[Dict[str, Any]] = None, text: Optional[str] = None):
        self.tag = tag
        self.props = props or {}
        self.text = text
        self.children: List['RealDOMNode'] = []
        self.parent: Optional['RealDOMNode'] = None

    def append_child(self, child: 'RealDOMNode'):
        child.parent = self
        self.children.append(child)

    def remove_child(self, index: int) -> 'RealDOMNode':
        child = self.children.pop(index)
        child.parent = None
        return child

    def replace_child(self, index: int, new_child: 'RealDOMNode'):
        new_child.parent = self
        self.children[index].parent = None
        self.children[index] = new_child

    def render_tree(self, level: int = 0) -> str:
        """Visualisasi struktur hierarki Real DOM dalam format string."""
        indent = "  " * level
        props_str = f" {self.props}" if self.props else ""
        text_str = f' "{self.text}"' if self.text else ""
        res = f"{indent}<{self.tag}{props_str}>{text_str}\n"
        for child in self.children:
            res += child.render_tree(level + 1)
        res += f"{indent}</{self.tag}>\n"
        return res


class ReconciliationEngine:
    """Algoritma Diffing dan Patching Virtual DOM."""
    
    def __init__(self):
        self.dom_mutations = 0

    def diff(self, old_vnode: Optional[VNode], new_vnode: Optional[VNode], node_path: str = "root") -> Optional[Patch]:
        """
        Membandingkan dua virtual tree dan menghasilkan Tree of Patches.
        Menerapkan optimasi:
        1. Node beda tag -> REPLACE seluruh subtree.
        2. Teks atau Props berubah -> UPDATE_PROPS.
        3. Rekursif diffing pada list children.
        """
        # Kasus 1: Node dihapus
        if old_vnode and not new_vnode:
            return Patch(PatchType.REMOVE, node_id=node_path)

        # Kasus 2: Node baru ditambahkan
        if not old_vnode and new_vnode:
            return Patch(PatchType.CREATE, node_id=node_path, new_vnode=new_vnode)

        # Kasus 3: Tag berubah total (contoh: 'div' menjadi 'section') -> Replace instan
        if old_vnode.tag != new_vnode.tag:
            return Patch(PatchType.REPLACE, node_id=node_path, new_vnode=new_vnode)

        # Kasus 4: Node setara, bandingkan mutasi properti dan teks
        prop_updates = {}
        # Cek atribut yang berubah atau baru
        for k, v in new_vnode.props.items():
            if old_vnode.props.get(k) != v:
                prop_updates[k] = v
        # Cek atribut yang dihapus
        for k in old_vnode.props:
            if k not in new_vnode.props:
                prop_updates[k] = None
        
        # Cek perubahan text leaf
        if old_vnode.text != new_vnode.text:
            prop_updates["#text"] = new_vnode.text

        patch = None
        if prop_updates:
            patch = Patch(PatchType.UPDATE_PROPS, node_id=node_path, props=prop_updates)

        # Diffing Children secara berurutan
        child_patches = []
        max_len = max(len(old_vnode.children), len(new_vnode.children))
        for i in range(max_len):
            old_child = old_vnode.children[i] if i < len(old_vnode.children) else None
            new_child = new_vnode.children[i] if i < len(new_vnode.children) else None
            child_patch = self.diff(old_child, new_child, f"{node_path}/{i}")
            if child_patch:
                child_patches.append(child_patch)

        if child_patches:
            if not patch:
                patch = Patch(PatchType.CHILDREN_UPDATE, node_id=node_path)
            patch.child_patches = child_patches

        return patch

    def create_real_dom(self, vnode: VNode) -> RealDOMNode:
        """Membuat Real DOM Node utuh dari VNode (Cold Boot / Initial Render)."""
        self.dom_mutations += 1
        dom_node = RealDOMNode(tag=vnode.tag, props=dict(vnode.props), text=vnode.text)
        for child in vnode.children:
            dom_node.append_child(self.create_real_dom(child))
        return dom_node

    def apply_patch(self, real_node: RealDOMNode, patch: Patch):
        """Mengeksekusi mutasi atomik langsung ke Real DOM tree."""
        if not patch:
            return

        if patch.patch_type == PatchType.UPDATE_PROPS:
            self.dom_mutations += 1
            for k, v in (patch.props or {}).items():
                if k == "#text":
                    real_node.text = v
                elif v is None:
                    real_node.props.pop(k, None)
                else:
                    real_node.props[k] = v

        elif patch.patch_type == PatchType.REPLACE:
            self.dom_mutations += 1
            if patch.new_vnode and real_node.parent:
                idx = real_node.parent.children.index(real_node)
                new_dom = self.create_real_dom(patch.new_vnode)
                real_node.parent.replace_child(idx, new_dom)

        # Eksekusi child patch secara presisi berdasarkan index path
        for cp in patch.child_patches:
            child_idx = int(cp.node_id.split("/")[-1])
            if cp.patch_type == PatchType.CREATE:
                self.dom_mutations += 1
                if cp.new_vnode:
                    real_node.append_child(self.create_real_dom(cp.new_vnode))
            elif cp.patch_type == PatchType.REMOVE:
                self.dom_mutations += 1
                real_node.remove_child(child_idx)
            else:
                self.apply_patch(real_node.children[child_idx], cp)


def count_all_vnodes(vnode: VNode) -> int:
    """Menghitung total node pada Virtual DOM Tree."""
    return 1 + sum(count_all_vnodes(child) for child in vnode.children)


def run_benchmark():
    print(f"{BOLD}{CYAN}=== [LAB] FRONTEND DEEP DIVE: VIRTUAL DOM RECONCILER ==={RESET}\n")

    engine = ReconciliationEngine()

    # 1. INITIAL TREE SETUP (VNode Tree State 0)
    print(f"{BLUE}[1] Initializing Component State (Mount Phase)...{RESET}")
    initial_vdom = VNode("div", props={"id": "app", "class": "container"}, children=[
        VNode("header", props={"class": "header"}, children=[
            VNode("h1", text="Frontend Micro-Dashboard"),
            VNode("span", props={"class": "status"}, text="Sync Status: OK")
        ]),
        VNode("ul", props={"id": "task-list"}, children=[
            VNode("li", props={"key": "t1", "class": "todo-item"}, text="Review React 18 Concurrency"),
            VNode("li", props={"key": "t2", "class": "todo-item"}, text="Benchmark Layout Thrashing"),
            VNode("li", props={"key": "t3", "class": "todo-item"}, text="Analyze V8 TurboFan Deopts")
        ]),
        VNode("footer", props={"class": "footer"}, text="Engine: Custom Reconciliation v1.0")
    ])

    real_dom_root = engine.create_real_dom(initial_vdom)
    initial_mutations = engine.dom_mutations
    print(f"{GREEN}✓ Initial Real DOM Tree Mounted with {initial_mutations} DOM creation calls.{RESET}\n")
    print(f"{YELLOW}--- CURRENT REAL DOM SNAPSHOT ---{RESET}")
    print(real_dom_root.render_tree())

    # 2. TRIGGER RE-RENDER DENGAN MUTASI PARSIAL (State 1)
    print(f"{BLUE}[2] Simulating Reactive State Change...{RESET}")
    # Perubahan: 
    # - Header status berubah (UPDATE_PROPS/Text)
    # - Todo Item 2 berubah teksnya (UPDATE_PROPS/Text)
    # - Todo Item 4 ditambahkan (CREATE)
    # - Footer diganti tag menjadi 'aside' (REPLACE)
    updated_vdom = VNode("div", props={"id": "app", "class": "container active"}, children=[
        VNode("header", props={"class": "header"}, children=[
            VNode("h1", text="Frontend Micro-Dashboard"),
            VNode("span", props={"class": "status warning"}, text="Sync Status: SYNCING...")
        ]),
        VNode("ul", props={"id": "task-list"}, children=[
            VNode("li", props={"key": "t1", "class": "todo-item"}, text="Review React 18 Concurrency"),
            VNode("li", props={"key": "t2", "class": "todo-item done"}, text="Benchmark Layout Thrashing [RESOLVED]"),
            VNode("li", props={"key": "t3", "class": "todo-item"}, text="Analyze V8 TurboFan Deopts"),
            VNode("li", props={"key": "t4", "class": "todo-item new"}, text="Profile Garbage Collection")
        ]),
        VNode("aside", props={"class": "footer-aside"}, text="Engine: Custom Reconciliation v1.0 (Migrated to Aside)")
    ])

    # 3. RECONCILIATION & DIFFING
    t_start = time.perf_counter()
    patches = engine.diff(initial_vdom, updated_vdom)
    t_diff = (time.perf_counter() - t_start) * 1_000_000

    print(f"{GREEN}✓ Tree Diffing completed in {t_diff:.2f} µs.{RESET}")
    print(f"{MAGENTA}Computed Patch Details:{RESET}")
    
    def debug_patch(p: Patch, indent=2):
        ind = " " * indent
        print(f"{ind}├── Type: {BOLD}{p.patch_type.name}{RESET} on Path: [{p.node_id}] Props: {p.props or 'None'}")
        for cp in p.child_patches:
            debug_patch(cp, indent + 4)

    if patches:
        debug_patch(patches)

    # 4. PATCH APPLICATION
    engine.dom_mutations = 0
    t_patch_start = time.perf_counter()
    engine.apply_patch(real_dom_root, patches)
    t_patch = (time.perf_counter() - t_patch_start) * 1_000_000

    print(f"\n{GREEN}✓ Minimal Differential Patch applied in {t_patch:.2f} µs.{RESET}")
    print(f"{YELLOW}--- UPDATED REAL DOM SNAPSHOT ---{RESET}")
    print(real_dom_root.render_tree())

    # 5. METRICS & ANALYSIS: NAIIVE RE-RENDER VS VDOM
    total_nodes = count_all_vnodes(updated_vdom)
    vdom_mutations = engine.dom_mutations
    naive_mutations = total_nodes  # Naive innerHTML = Recreate entire tree

    print(f"{BOLD}{CYAN}=== EFFICIENCY BENCHMARK & SYSTEM ANALYSIS ==={RESET}")
    print(f"Total Virtual DOM Nodes Processed: {BOLD}{total_nodes}{RESET}")
    print(f"Naive Destruction Operations:     {RED}{naive_mutations} Node Rewrites{RESET}")
    print(f"Reconciliation Patch Mutations:    {GREEN}{vdom_mutations} Operations{RESET}")
    
    saved_ratio = ((naive_mutations - vdom_mutations) / naive_mutations) * 100
    print(f"Layout Thrashing Avoidance:        {BOLD}{GREEN}{saved_ratio:.1f}% reduction in DOM writes{RESET}\n")

    print(f"{CYAN}Deep Dive Takeaway:{RESET}")
    print("Browser DOM mutations trigger reflow and repaint passes. By generating an")
    print("intermediate structural difference in user space (VDOM), we reduce real-world")
    print("rendering pipeline overhead to optimal O(K) where K is the number of true mutations.")


if __name__ == "__main__":
    run_benchmark()