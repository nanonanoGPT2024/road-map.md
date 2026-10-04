#!/usr/bin/env python3
"""
Lab Hands-on: Frontend Architecture Deep Dive
Bab 04 - Modul 02: Virtual DOM Diffing Engine & Reactive State Reconciliation

Mekanisme yang disimulasikan:
1. Virtual DOM Tree Representation (VNode abstraction).
2. Keyed Child Reconciliation & Heuristic Tree Diffing (Linear O(N) diff).
3. Patch Generation (Node replacement, attribute mutation, text node update, reordering).
4. Reactive State Container (Fine-grained reactive signals triggering diff & patch cycles).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import time

# --- ANSI Terminal Color Configuration ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_MAG    = "\033[35m"
CLR_CYAN   = "\033[36m"
CLR_GRAY   = "\033[90m"

@dataclass
class VNode:
    """
    Abstraksi Virtual Node yang merepresentasikan elemen DOM di memori.
    """
    tag: Optional[str] = None
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[Union['VNode', str]] = field(default_factory=list)
    key: Optional[str] = None
    text: Optional[str] = None

    @property
    def is_text_node(self) -> bool:
        return self.tag is None and self.text is not None

    def serialize(self) -> str:
        """Serialisasi ringkas untuk visualisasi tree."""
        if self.is_text_node:
            return f'"{self.text}"'
        key_str = f" key='{self.key}'" if self.key else ""
        props_str = " " + " ".join(f"{k}='{v}'" for k, v in self.props.items()) if self.props else ""
        return f"<{self.tag}{key_str}{props_str}>"

@dataclass
class Patch:
    """Instruksi mutasi minimal untuk diaplikasikan ke host environment."""
    action: str  # CREATE, REMOVE, REPLACE, UPDATE_PROPS, UPDATE_TEXT, REORDER
    path: str    # Path representasi indeks DOM tree (misal: "0.1.2")
    payload: Any = None

class DiffEngine:
    """
    Engine Diffing Virtual DOM: Membandingkan Old Tree vs New Tree
    dan menghasilkan daftar patch seminimal mungkin.
    """
    @classmethod
    def diff(cls, old_tree: Optional[VNode], new_tree: Optional[VNode], path: str = "root") -> List[Patch]:
        patches: List[Patch] = []

        # Kasus 1: Node lama dihapus
        if old_tree is not None and new_tree is None:
            patches.append(Patch("REMOVE", path, old_tree))
            return patches

        # Kasus 2: Node baru ditambahkan
        if old_tree is None and new_tree is not None:
            patches.append(Patch("CREATE", path, new_tree))
            return patches

        if old_tree is None or new_tree is None:
            return patches

        # Kasus 3: Text Node Update
        if old_tree.is_text_node and new_tree.is_text_node:
            if old_tree.text != new_tree.text:
                patches.append(Patch("UPDATE_TEXT", path, new_tree.text))
            return patches

        # Kasus 4: Penggantian total (Tag berbeda atau tipe node berubah)
        if old_tree.tag != new_tree.tag:
            patches.append(Patch("REPLACE", path, new_tree))
            return patches

        # Kasus 5: Node sama -> Diff Attributes/Props
        prop_patches = cls._diff_props(old_tree.props, new_tree.props)
        if prop_patches:
            patches.append(Patch("UPDATE_PROPS", path, prop_patches))

        # Kasus 6: Diffing Children menggunakan Keyed Reconciliation
        child_patches = cls._diff_children(old_tree.children, new_tree.children, path)
        patches.extend(child_patches)

        return patches

    @staticmethod
    def _diff_props(old_props: Dict[str, Any], new_props: Dict[str, Any]) -> Dict[str, Any]:
        mutations = {}
        # Cek prop yang berubah atau baru
        for k, v in new_props.items():
            if k not in old_props or old_props[k] != v:
                mutations[k] = v
        # Cek prop yang dihapus
        for k in old_props:
            if k not in new_props:
                mutations[k] = None
        return mutations

    @classmethod
    def _diff_children(
        cls, 
        old_ch: List[Union[VNode, str]], 
        new_ch: List[Union[VNode, str]], 
        parent_path: str
    ) -> List[Patch]:
        patches: List[Patch] = []

        # Standarisasi anak bertipe teks ke VNode
        old_normalized = [c if isinstance(c, VNode) else VNode(text=str(c)) for c in old_ch]
        new_normalized = [c if isinstance(c, VNode) else VNode(text=str(c)) for c in new_ch]

        # Map child berdasarkan key untuk deteksi pergeseran posisi (O(N) reconciliation)
        old_key_map = {node.key: (idx, node) for idx, node in enumerate(old_normalized) if node.key}
        new_key_map = {node.key: (idx, node) for idx, node in enumerate(new_normalized) if node.key}

        # Jika kedua child list menggunakan key
        if old_key_map and new_key_map:
            # Deteksi deletion
            for key, (idx, old_node) in old_key_map.items():
                if key not in new_key_map:
                    patches.append(Patch("REMOVE_CHILD", f"{parent_path}.{idx}", {"key": key}))

            # Deteksi reorder & update
            for new_idx, new_node in enumerate(new_normalized):
                key = new_node.key
                if key in old_key_map:
                    old_idx, old_node = old_key_map[key]
                    if old_idx != new_idx:
                        patches.append(Patch("REORDER_CHILD", f"{parent_path}.{new_idx}", {
                            "key": key, "from_idx": old_idx, "to_idx": new_idx
                        }))
                    # Recursive diff untuk subtree node ini
                    patches.extend(cls.diff(old_node, new_node, f"{parent_path}.{key}"))
                else:
                    patches.append(Patch("INSERT_CHILD", f"{parent_path}.{new_idx}", {
                        "node": new_node, "at_index": new_idx
                    }))
        else:
            # Fallback ke positional matching diff
            max_len = max(len(old_normalized), len(new_normalized))
            for i in range(max_len):
                o = old_normalized[i] if i < len(old_normalized) else None
                n = new_normalized[i] if i < len(new_normalized) else None
                child_path = f"{parent_path}[{i}]"
                patches.extend(cls.diff(o, n, child_path))

        return patches

class ReactiveState:
    """Implementasi primitif State Reaktif (Observer Pattern)."""
    def __init__(self, initial_value: Any):
        self._value = initial_value
        self._subscribers = []

    def get(self) -> Any:
        return self._value

    def set(self, new_val: Any) -> None:
        if self._value != new_val:
            self._value = new_val
            self._notify()

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def _notify(self) -> None:
        for cb in self._subscribers:
            cb(self._value)

class MockBrowserRenderer:
    """Simulasi eksekusi mutasi ke DOM Engine asli."""
    @staticmethod
    def apply_patches(patches: List[Patch]) -> None:
        if not patches:
            print(f"  {CLR_GRAY}⚡ DOM Reconciliation selesai: Tidak ada mutasi yang diperlukan.{CLR_RESET}")
            return

        for p in patches:
            if p.action == "UPDATE_TEXT":
                print(f"  {CLR_CYAN}➜ [DOM MUTATION]{CLR_RESET} Set TextContent at {CLR_YELLOW}{p.path}{CLR_RESET} to {CLR_GREEN}'{p.payload}'{CLR_RESET}")
            elif p.action == "UPDATE_PROPS":
                print(f"  {CLR_BLUE}➜ [DOM MUTATION]{CLR_RESET} Update Attributes at {CLR_YELLOW}{p.path}{CLR_RESET} with {json.dumps(p.payload)}")
            elif p.action == "REORDER_CHILD":
                payload = p.payload
                print(f"  {CLR_MAG}➜ [DOM REORDER]{CLR_RESET} Move Key {CLR_BOLD}#{payload['key']}{CLR_RESET} from idx {payload['from_idx']} to {payload['to_idx']}")
            elif p.action == "INSERT_CHILD":
                node = p.payload['node']
                print(f"  {CLR_GREEN}➜ [DOM INSERT]{CLR_RESET} Insert node {node.serialize()} at index {p.payload['at_index']}")
            elif p.action == "REMOVE_CHILD":
                print(f"  {CLR_RED}➜ [DOM REMOVE]{CLR_RESET} Detach node with Key #{p.payload['key']} at {p.path}")
            elif p.action == "REPLACE":
                print(f"  {CLR_RED}➜ [DOM REPLACE]{CLR_RESET} Replace node at {p.path} with {p.payload.serialize()}")

def render_vtree_preview(node: Union[VNode, str], indent: int = 0) -> None:
    """Mencetak struktur VTree secara visual."""
    prefix = "  " * indent
    if isinstance(node, str) or (isinstance(node, VNode) and node.is_text_node):
        text = node if isinstance(node, str) else node.text
        print(f"{prefix}{CLR_GREEN}#text: \"{text}\"{CLR_RESET}")
        return

    key_repr = f" {CLR_YELLOW}[key={node.key}]{CLR_RESET}" if node.key else ""
    props_repr = f" {CLR_GRAY}{json.dumps(node.props)}{CLR_RESET}" if node.props else ""
    print(f"{prefix}{CLR_BOLD}<{node.tag}>{CLR_RESET}{key_repr}{props_repr}")
    for ch in node.children:
        render_vtree_preview(ch, indent + 1)

def build_todo_tree(todos: List[Dict[str, Any]], filter_mode: str) -> VNode:
    """Komponen deklaratif: Memetakan state ke Virtual DOM Tree."""
    items = []
    for item in todos:
        if filter_mode == "ACTIVE" and item["completed"]:
            continue
        status_cls = "done" if item["completed"] else "pending"
        items.append(
            VNode(
                tag="li",
                key=item["id"],
                props={"class": f"todo-item {status_cls}"},
                children=[
                    VNode(tag="span", children=[item["title"]]),
                    VNode(tag="span", props={"class": "badge"}, children=[status_cls.upper()])
                ]
            )
        )

    return VNode(
        tag="div",
        props={"id": "app-container", "class": "container"},
        children=[
            VNode(tag="header", children=[
                VNode(tag="h1", children=["Task Coordinator"]),
                VNode(tag="span", props={"class": "counter"}, children=[f"Total: {len(items)}"])
            ]),
            VNode(tag="ul", props={"class": "todo-list"}, children=items)
        ]
    )

def main():
    print(f"\n{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} LAB: FRONTEND ARCHITECTURE - VIRTUAL DOM & RECONCILIATION ENGINE {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}\n")

    # State reaktif awal
    initial_todos = [
        {"id": "t1", "title": "Implement Webpack bundler", "completed": False},
        {"id": "t2", "title": "Write Unit Tests for Diff Engine", "completed": False},
        {"id": "t3", "title": "Profile CSS Reflows", "completed": True},
    ]

    state_todos = ReactiveState(initial_todos)
    state_filter = ReactiveState("ALL")

    current_vtree: Optional[VNode] = None

    def trigger_reconciliation(step_desc: str):
        nonlocal current_vtree
        print(f"\n{CLR_BOLD}{CLR_YELLOW}>>> ACTION TRIGGERED: {step_desc} <<<{CLR_RESET}")
        start_time = time.perf_counter()

        new_vtree = build_todo_tree(state_todos.get(), state_filter.get())
        patches = DiffEngine.diff(current_vtree, new_vtree)
        duration_ms = (time.perf_counter() - start_time) * 1000

        print(f"{CLR_GRAY}[Diff Engine Runtime: {duration_ms:.4f} ms | Patches Produced: {len(patches)}]{CLR_RESET}")
        MockBrowserRenderer.apply_patches(patches)
        current_vtree = new_vtree

    # --- Phase 1: Mount Initial Render ---
    print(f"{CLR_BOLD}[1] Initial Mount Cycle:{CLR_RESET}")
    new_vtree = build_todo_tree(state_todos.get(), state_filter.get())
    print("Virtual DOM Tree Snapshot:")
    render_vtree_preview(new_vtree)
    patches = DiffEngine.diff(None, new_vtree)
    MockBrowserRenderer.apply_patches(patches)
    current_vtree = new_vtree

    # --- Phase 2: Update Props / Attributes & Nested Text ---
    time.sleep(0.05)
    updated_todos = [
        {"id": "t1", "title": "Implement Webpack bundler (OPTIMIZED)", "completed": True}, # Ubah teks & toggle status
        {"id": "t2", "title": "Write Unit Tests for Diff Engine", "completed": False},
        {"id": "t3", "title": "Profile CSS Reflows", "completed": True},
    ]
    state_todos.set(updated_todos)
    trigger_reconciliation("Toggle Task #1 completion & append text label")

    # --- Phase 3: List Reordering & Keyed Insertion ---
    time.sleep(0.05)
    reordered_todos = [
        {"id": "t4", "title": "Analyze Bundle Memory Leaks", "completed": False}, # Item baru dimasukkan di awal
        {"id": "t3", "title": "Profile CSS Reflows", "completed": True},           # Posisi berpindah
        {"id": "t1", "title": "Implement Webpack bundler (OPTIMIZED)", "completed": True},
        # t2 dihapus
    ]
    state_todos.set(reordered_todos)
    trigger_reconciliation("Prepend Task #4, reorder #3, and delete Task #2")

    # --- Phase 4: State Filtration (Removing nodes from tree) ---
    time.sleep(0.05)
    state_filter.set("ACTIVE")
    trigger_reconciliation("Apply Filter: ACTIVE ONLY (Exclude completed tasks)")

    print(f"\n{CLR_BOLD}Final Virtual DOM State:{CLR_RESET}")
    render_vtree_preview(current_vtree)
    print(f"\n{CLR_GREEN}{CLR_BOLD}✔ Deep Dive Lab Complete. Virtual DOM diffing & reconciliation simulated successfully.{CLR_RESET}\n")

if __name__ == "__main__":
    main()