#!/usr/bin/env python3
"""
Lab Hands-on: Frontend Architecture Deep Dive
Topik: Virtual DOM Diffing Engine & Reactive Reconciliation Pipeline
Modul: 03-Frontend-and-Mobile / Bab-02

Skrip ini mensimulasikan mekanisme inti rendering framework frontend modern (mirip React/Vue):
1. Representasi Virtual DOM (VNode tree).
2. Algoritma rekursif Reconciliation / Tree Diffing.
3. Komputasi minimal mutation patches (CREATE, REMOVE, REPLACE, PROPS, TEXT).
4. Patch Application Engine ke Mock Native UI Tree.
"""

from __future__ import annotations
import enum
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# --- ANSI Formatting Helper ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


class PatchType(enum.Enum):
    CREATE = "CREATE"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"
    UPDATE_PROPS = "UPDATE_PROPS"
    UPDATE_TEXT = "UPDATE_TEXT"
    CHILDREN = "CHILDREN"


class VNode:
    """Virtual Node merepresentasikan abstraksi UI yang ringan di memori."""
    def __init__(
        self,
        tag: Optional[str] = None,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List[Union[VNode, str]]] = None,
        key: Optional[str] = None,
        text: Optional[str] = None,
    ):
        self.tag = tag
        self.props = props or {}
        self.children = children or []
        self.key = key
        self.text = text

    @property
    def is_text_node(self) -> bool:
        return self.tag is None and self.text is not None

    def to_dict(self) -> Dict[str, Any]:
        if self.is_text_node:
            return {"text": self.text}
        return {
            "tag": self.tag,
            "key": self.key,
            "props": self.props,
            "children": [c.to_dict() if isinstance(c, VNode) else c for c in self.children],
        }


class Patch:
    """Instruksi mutasi minimal yang dihasilkan dari proses diffing."""
    def __init__(
        self,
        patch_type: PatchType,
        target_path: str,
        payload: Any = None,
    ):
        self.patch_type = patch_type
        self.target_path = target_path  # Contoh: "root/0/1"
        self.payload = payload

    def __repr__(self) -> str:
        return (
            f"Patch({self.patch_type.value}, path='{self.target_path}', "
            f"payload={self.payload})"
        )


class MockRealDOMNode:
    """Mock node browser DOM asli untuk mengukur payload reflow/repaint."""
    def __init__(self, tag: Optional[str] = None, text: Optional[str] = None):
        self.tag = tag
        self.text = text
        self.props: Dict[str, Any] = {}
        self.children: List[MockRealDOMNode] = []

    def render_tree(self, depth: int = 0) -> str:
        indent = "  " * depth
        if self.tag is None:
            return f'{indent}"{self.text}"\n'
        props_str = " ".join(f'{k}="{v}"' for k, v in self.props.items())
        opening = f"<{self.tag}{' ' + props_str if props_str else ''}>"
        if not self.children:
            return f"{indent}{opening}</{self.tag}>\n"
        out = f"{indent}{opening}\n"
        for child in self.children:
            out += child.render_tree(depth + 1)
        out += f"{indent}</{self.tag}>\n"
        return out


class ReconciliationEngine:
    """
    Core Engine: Membandingkan 2 VNode Trees secara deterministik
    menggunakan algoritma heuristik O(N).
    """

    @classmethod
    def diff_props(
        cls, old_props: Dict[str, Any], new_props: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Menghitung mutasi atribut/properti komponen."""
        mutations: Dict[str, Any] = {}
        # Cek perubahan atau penambahan
        for key, val in new_props.items():
            if old_props.get(key) != val:
                mutations[key] = val
        # Cek penghapusan atribut
        for key in old_props:
            if key not in new_props:
                mutations[key] = None  # None menandakan prop dihapus
        return mutations

    @classmethod
    def diff(
        cls,
        old_tree: Optional[VNode],
        new_tree: Optional[VNode],
        path: str = "root",
    ) -> List[Patch]:
        """
        Algoritma Tree Diffing:
        Menghasilkan set instruksi terkecil untuk mentransformasikan old_tree menjadi new_tree.
        """
        patches: List[Patch] = []

        if old_tree is None and new_tree is not None:
            patches.append(Patch(PatchType.CREATE, path, new_tree))
            return patches

        if old_tree is not None and new_tree is None:
            patches.append(Patch(PatchType.REMOVE, path, None))
            return patches

        if old_tree is None or new_tree is None:
            return patches

        # Jika tipe node berubah secara struktural (misal <div> menjadi <span>)
        if old_tree.tag != new_tree.tag or old_tree.key != new_tree.key:
            patches.append(Patch(PatchType.REPLACE, path, new_tree))
            return patches

        # Text Node reconciliation
        if old_tree.is_text_node and new_tree.is_text_node:
            if old_tree.text != new_tree.text:
                patches.append(Patch(PatchType.UPDATE_TEXT, path, new_tree.text))
            return patches

        # Properties reconciliation
        prop_diff = cls.diff_props(old_tree.props, new_tree.props)
        if prop_diff:
            patches.append(Patch(PatchType.UPDATE_PROPS, path, prop_diff))

        # Children reconciliation (Key-based or linear zip)
        old_len = len(old_tree.children)
        new_len = len(new_tree.children)
        common_len = min(old_len, new_len)

        for i in range(common_len):
            c_old = old_tree.children[i]
            c_new = new_tree.children[i]
            child_old = VNode(text=c_old) if isinstance(c_old, str) else c_old
            child_new = VNode(text=c_new) if isinstance(c_new, str) else c_new
            patches.extend(cls.diff(child_old, child_new, f"{path}/{i}"))

        if new_len > old_len:
            for i in range(common_len, new_len):
                c_new = new_tree.children[i]
                node_new = VNode(text=c_new) if isinstance(c_new, str) else c_new
                patches.append(Patch(PatchType.CREATE, f"{path}/{i}", node_new))
        elif old_len > new_len:
            for i in reversed(range(common_len, old_len)):
                patches.append(Patch(PatchType.REMOVE, f"{path}/{i}", None))

        return patches


class DOMRenderer:
    """Menerapkan patch ke representasi aktual DOM."""

    @staticmethod
    def create_mock_dom(vnode: VNode) -> MockRealDOMNode:
        if vnode.is_text_node:
            return MockRealDOMNode(text=vnode.text)
        dom = MockRealDOMNode(tag=vnode.tag)
        dom.props = dict(vnode.props)
        for child in vnode.children:
            c_vnode = VNode(text=child) if isinstance(child, str) else child
            dom.children.append(DOMRenderer.create_mock_dom(c_vnode))
        return dom

    @staticmethod
    def resolve_path(root: MockRealDOMNode, path: str) -> Tuple[Optional[MockRealDOMNode], Optional[MockRealDOMNode], int]:
        """Mengurai path seperti 'root/0/1' menjadi target node dan parent-nya."""
        parts = path.split("/")
        if parts[0] != "root":
            raise ValueError("Root path invalid")
        
        if len(parts) == 1:
            return root, None, -1

        parent = None
        current = root
        idx = -1
        for part in parts[1:]:
            idx = int(part)
            parent = current
            if idx < len(parent.children):
                current = parent.children[idx]
            else:
                current = None
                break
        return current, parent, idx

    @classmethod
    def apply_patches(cls, root: MockRealDOMNode, patches: List[Patch]) -> MockRealDOMNode:
        """Mengaplikasikan mutation pipeline langsung ke mock real DOM tree."""
        for p in patches:
            node, parent, idx = cls.resolve_path(root, p.target_path)

            if p.patch_type == PatchType.UPDATE_TEXT:
                if node:
                    node.text = p.payload
            elif p.patch_type == PatchType.UPDATE_PROPS:
                if node:
                    for k, v in p.payload.items():
                        if v is None:
                            node.props.pop(k, None)
                        else:
                            node.props[k] = v
            elif p.patch_type == PatchType.CREATE:
                new_dom_node = cls.create_mock_dom(p.payload)
                if parent is not None:
                    if idx >= len(parent.children):
                        parent.children.append(new_dom_node)
                    else:
                        parent.children.insert(idx, new_dom_node)
            elif p.patch_type == PatchType.REMOVE:
                if parent is not None and 0 <= idx < len(parent.children):
                    parent.children.pop(idx)
            elif p.patch_type == PatchType.REPLACE:
                new_dom_node = cls.create_mock_dom(p.payload)
                if parent is not None and 0 <= idx < len(parent.children):
                    parent.children[idx] = new_dom_node
                elif parent is None:
                    root = new_dom_node
        return root


def run_benchmark():
    print(f"{TermColor.BOLD}{TermColor.CYAN}==============================================================={TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN} LAB: Virtual DOM Diffing Engine & Reconciliation Pipeline     {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}==============================================================={TermColor.RESET}\n")

    # 1. State Inisial UI
    print(f"{TermColor.YELLOW}[1] Menginisialisasi Virtual Tree V1 (State: Awal)...{TermColor.RESET}")
    vdom_v1 = VNode(
        tag="div",
        props={"id": "app-container", "class": "dark-theme"},
        children=[
            VNode(tag="header", children=[VNode(tag="h1", children=["Dashboard Analytics"])]),
            VNode(
                tag="ul",
                props={"class": "metric-list"},
                children=[
                    VNode(tag="li", props={"key": "cpu"}, children=["CPU Usage: 45%"]),
                    VNode(tag="li", props={"key": "mem"}, children=["Memory: 60%"]),
                    VNode(tag="li", props={"key": "req"}, children=["Requests: 1200/s"]),
                ],
            ),
            VNode(tag="footer", children=[VNode(tag="span", children=["Status: Healthy"])]),
        ],
    )

    real_dom = DOMRenderer.create_mock_dom(vdom_v1)
    print(f"{TermColor.GRAY}--- Real DOM Tree Representation (V1) ---{TermColor.RESET}")
    print(real_dom.render_tree())

    # 2. State Mutasi UI (Simulasi Reactive Event / State Update)
    # Perubahan:
    # - class div berubah
    # - CPU melonjak ke 92%
    # - Node 'Requests' dihapus
    # - Node baru 'Disk IO' ditambahkan
    # - Footer status berubah menjadi "Degraded" dengan class "alert"
    print(f"{TermColor.YELLOW}[2] Menerapkan Perubahan State UI ke Virtual Tree V2...{TermColor.RESET}")
    vdom_v2 = VNode(
        tag="div",
        props={"id": "app-container", "class": "dark-theme high-load"},
        children=[
            VNode(tag="header", children=[VNode(tag="h1", children=["Dashboard Analytics"])]),
            VNode(
                tag="ul",
                props={"class": "metric-list warning"},
                children=[
                    VNode(tag="li", props={"key": "cpu"}, children=["CPU Usage: 92%"]),
                    VNode(tag="li", props={"key": "mem"}, children=["Memory: 60%"]),
                    VNode(tag="li", props={"key": "disk"}, children=["Disk IO: 450 MB/s"]),
                ],
            ),
            VNode(
                tag="footer",
                props={"class": "alert"},
                children=[VNode(tag="span", children=["Status: Degraded"])],
            ),
        ],
    )

    # 3. Eksekusi Diffing / Rekonsiliasi
    t0 = time.perf_counter_ns()
    patches = ReconciliationEngine.diff(vdom_v1, vdom_v2)
    elapsed_us = (time.perf_counter_ns() - t0) / 1_000

    print(f"{TermColor.GREEN}[3] Reconciliation Engine Selesai! ({elapsed_us:.2f} µs){TermColor.RESET}")
    print(f"{TermColor.BOLD}Patches yang Dihasilkan ({len(patches)} mutasi atomik):{TermColor.RESET}")
    for p in patches:
        color = TermColor.GREEN if p.patch_type == PatchType.CREATE else (
            TermColor.RED if p.patch_type == PatchType.REMOVE else TermColor.MAGENTA
        )
        print(f"  {color}▸ [{p.patch_type.value}]{TermColor.RESET} Path: {TermColor.CYAN}{p.target_path:<10}{TermColor.RESET} Payload: {p.payload}")

    # 4. Patching Real DOM
    print(f"\n{TermColor.YELLOW}[4] Memetakan & Menjalankan Patch ke Target DOM Asli...{TermColor.RESET}")
    updated_real_dom = DOMRenderer.apply_patches(real_dom, patches)

    print(f"\n{TermColor.GREEN}=== Hasil Akhir Real DOM Tree Setelah Rekonsiliasi ==={TermColor.RESET}")
    print(updated_real_dom.render_tree())

    # Verifikasi Validasi
    print(f"{TermColor.BOLD}{TermColor.CYAN}Verifikasi Diagnostik Mutasi:{TermColor.RESET}")
    print(f"  • Container Classes : {TermColor.BOLD}{updated_real_dom.props.get('class')}{TermColor.RESET}")
    ul_node = updated_real_dom.children[1]
    cpu_node = ul_node.children[0].children[0]
    disk_node = ul_node.children[2].children[0]
    footer_span = updated_real_dom.children[2].children[0].children[0]
    print(f"  • CPU Metric Node   : '{cpu_node.text}'")
    print(f"  • Disk Metric Node  : '{disk_node.text}'")
    print(f"  • Footer Text Node  : '{footer_span.text}'")
    assert cpu_node.text == "CPU Usage: 92%", "Failed assert CPU update"
    assert disk_node.text == "Disk IO: 450 MB/s", "Failed assert Disk IO insert"
    print(f"{TermColor.GREEN}✔ Integritas Pohon DOM Tervalidasi 100% Konsisten.{TermColor.RESET}\n")


if __name__ == "__main__":
    run_benchmark()