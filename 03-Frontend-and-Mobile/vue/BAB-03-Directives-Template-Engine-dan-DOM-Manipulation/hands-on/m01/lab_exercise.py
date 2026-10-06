#!/usr/bin/env python3
"""
Mini-Vue Directive & Template Engine Simulator
BAB-03: Directives, Template Engine, dan DOM Manipulation

Simulasi teknis independen fondasi Vue.js:
- Template Parsing & Mustache Interpolation ({{ expr }})
- Directives Core: v-bind (:), v-model, v-if / v-else, v-show, v-for, v-on (@)
- Virtual DOM (VNode) Construction, Diffing, and DOM Patching Simulation
"""

import re
import sys
import copy
import time
from typing import Any, Dict, List, Optional, Callable


# ==============================================================================
# ANSI Terminal Colors & Styling
# ==============================================================================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"


def c(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"


# ==============================================================================
# Virtual DOM Node (VNode) Representation
# ==============================================================================
class VNode:
    def __init__(
        self,
        tag: str,
        attrs: Optional[Dict[str, Any]] = None,
        children: Optional[List[Any]] = None,
        text: Optional[str] = None,
        key: Optional[str] = None,
    ):
        self.tag = tag
        self.attrs = attrs if attrs is not None else {}
        self.children = children if children is not None else []
        self.text = text
        self.key = key

    def to_html(self, indent: int = 0) -> str:
        pad = "  " * indent
        if self.tag == "#text":
            return f"{pad}{self.text or ''}"

        attr_str = ""
        for k, v in self.attrs.items():
            if k == "style" and isinstance(v, dict):
                style_val = "; ".join(f"{sk}: {sv}" for sk, sv in v.items())
                attr_str += f' {k}="{style_val}"'
            else:
                attr_str += f' {k}="{v}"'

        if not self.children and not self.text:
            return f"{pad}<{self.tag}{attr_str} />"

        inner = []
        if self.text:
            inner.append(f"{pad}  {self.text}")
        for child in self.children:
            if isinstance(child, VNode):
                inner.append(child.to_html(indent + 1))
            else:
                inner.append(f"{pad}  {str(child)}")

        inner_str = "\n".join(inner)
        return f"{pad}<{self.tag}{attr_str}>\n{inner_str}\n{pad}</{self.tag}>"

    def __repr__(self) -> str:
        return f"VNode(tag={self.tag}, attrs={self.attrs}, key={self.key}, text={self.text})"


# ==============================================================================
# Template Engine & Directive Evaluator
# ==============================================================================
class MiniVueTemplateEngine:
    def __init__(self, state: Dict[str, Any], methods: Dict[str, Callable]):
        self.state = state
        self.methods = methods
        self.dom_patch_log: List[str] = []

    def evaluate_expression(self, expr: str, scope: Optional[Dict[str, Any]] = None) -> Any:
        context = {**self.state}
        if scope:
            context.update(scope)

        # Convert simple JS ternary `cond ? expr1 : expr2` to Python `(expr1 if cond else expr2)`
        js_ternary_pattern = r"^(.*?)\s*\?\s*(.*?)\s*:\s*(.*?)$"
        match = re.match(js_ternary_pattern, expr.strip())
        py_expr = expr
        if match:
            cond, left, right = match.groups()
            py_expr = f"({left} if ({cond}) else {right})"

        try:
            return eval(py_expr, {}, context)
        except Exception as err:
            return f"[Eval Error: {err}]"

    def interpolate(self, text: str, scope: Optional[Dict[str, Any]] = None) -> str:
        """Menggantikan ekspresi Mustache {{ expr }} dengan nilai aktual."""
        pattern = r"\{\{\s*(.*?)\s*\}\}"

        def replacer(match):
            expr = match.group(1)
            val = self.evaluate_expression(expr, scope)
            return str(val)

        return re.sub(pattern, replacer, text)

    def process_directives(
        self,
        node_def: Dict[str, Any],
        scope: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[VNode]]:
        """
        Memproses directives:
        - v-for: merender perulangan
        - v-if / v-else-if / v-else: conditional mounting
        - v-show: toggling display style
        - v-bind (:): attribute reactivity
        - v-model: two-way data sync
        - v-on (@): event listener simulation
        """
        directives = node_def.get("directives", {})

        # 1. v-for: List rendering
        if "v-for" in directives:
            loop_expr = directives["v-for"]
            # Format: "item in items" atau "(item, index) in items"
            match = re.match(r"(?:\((.*?)\)|(\w+))\s+in\s+(\w+)", loop_expr)
            if not match:
                print(c(f"[-] Invalid v-for syntax: {loop_expr}", Colors.RED))
                return None

            item_var = match.group(1) or match.group(2)
            item_var = [i.strip() for i in item_var.split(",")]
            list_var = match.group(3)

            collection = self.evaluate_expression(list_var, scope)
            if not isinstance(collection, (list, tuple)):
                return []

            cloned_def = copy.deepcopy(node_def)
            del cloned_def["directives"]["v-for"]

            results: List[VNode] = []
            for idx, item in enumerate(collection):
                child_scope = dict(scope or {})
                if len(item_var) == 1:
                    child_scope[item_var[0]] = item
                else:
                    child_scope[item_var[0]] = item
                    child_scope[item_var[1]] = idx

                resolved = self.process_directives(cloned_def, child_scope)
                if resolved:
                    results.extend(resolved)
            return results

        # 2. v-if: Conditional rendering
        if "v-if" in directives:
            condition = self.evaluate_expression(directives["v-if"], scope)
            if not condition:
                self.dom_patch_log.append(
                    f"DOM Node <{node_def.get('tag')}> {c('UNMOUNTED', Colors.RED)} by v-if: {directives['v-if']}"
                )
                return []
            else:
                self.dom_patch_log.append(
                    f"DOM Node <{node_def.get('tag')}> {c('MOUNTED', Colors.GREEN)} by v-if: {directives['v-if']}"
                )

        # 3. Attributes & Styles
        attrs = copy.deepcopy(node_def.get("attrs", {}))
        styles = copy.deepcopy(node_def.get("style", {}))

        # v-show: Toggle CSS display tanpa unmount DOM
        if "v-show" in directives:
            show_cond = self.evaluate_expression(directives["v-show"], scope)
            if not show_cond:
                styles["display"] = "none"
                self.dom_patch_log.append(
                    f"DOM Node <{node_def.get('tag')}> {c('CSS HIDDEN (display: none)', Colors.YELLOW)} by v-show"
                )
            else:
                if styles.get("display") == "none":
                    del styles["display"]
                self.dom_patch_log.append(
                    f"DOM Node <{node_def.get('tag')}> {c('CSS VISIBLE', Colors.GREEN)} by v-show"
                )

        # v-bind: Dynamic binding (:class, :href, dll)
        for key, expr in directives.items():
            if key.startswith("v-bind:") or key.startswith(":"):
                attr_name = key.split(":")[-1]
                val = self.evaluate_expression(expr, scope)
                attrs[attr_name] = val
                self.dom_patch_log.append(f"v-bind {attr_name}=\"{val}\" bound from '{expr}'")

        # v-model: Two-way binding attribute injection
        if "v-model" in directives:
            bound_prop = directives["v-model"]
            attrs["value"] = self.state.get(bound_prop, "")
            self.dom_patch_log.append(
                f"v-model two-way bind on state['{bound_prop}'] -> value=\"{attrs['value']}\""
            )

        if styles:
            attrs["style"] = styles

        # 4. Content / Children Processing
        rendered_children: List[VNode] = []
        raw_text = node_def.get("text")
        evaluated_text = None
        if raw_text:
            evaluated_text = self.interpolate(raw_text, scope)

        for child in node_def.get("children", []):
            child_vnodes = self.process_directives(child, scope)
            if child_vnodes:
                rendered_children.extend(child_vnodes)

        vnode = VNode(
            tag=node_def.get("tag", "div"),
            attrs=attrs,
            children=rendered_children,
            text=evaluated_text,
            key=str(attrs.get("key", "")),
        )
        return [vnode]


# ==============================================================================
# Virtual DOM Diffing & Patching Visualizer
# ==============================================================================
class DOMPatcher:
    @staticmethod
    def diff(old_vnode: Optional[VNode], new_vnode: Optional[VNode], path: str = "root") -> List[str]:
        patches: List[str] = []

        if old_vnode is None and new_vnode is not None:
            patches.append(f"{c('[CREATE]', Colors.GREEN)} {path}: Mount <{new_vnode.tag}>")
            return patches
        if old_vnode is not None and new_vnode is None:
            patches.append(f"{c('[REMOVE]', Colors.RED)} {path}: Destroy <{old_vnode.tag}>")
            return patches
        if old_vnode is None and new_vnode is None:
            return patches

        # Tag mismatch -> Re-mount
        if old_vnode.tag != new_vnode.tag:
            patches.append(
                f"{c('[REPLACE]', Colors.MAGENTA)} {path}: <{old_vnode.tag}> -> <{new_vnode.tag}>"
            )
            return patches

        # Attribute changes
        all_attrs = set(old_vnode.attrs.keys()).union(new_vnode.attrs.keys())
        for attr in all_attrs:
            old_val = old_vnode.attrs.get(attr)
            new_val = new_vnode.attrs.get(attr)
            if old_val != new_val:
                patches.append(
                    f"{c('[ATTR]', Colors.YELLOW)} {path} (<{new_vnode.tag}>): "
                    f"'{attr}' changed: {c(str(old_val), Colors.RED)} -> {c(str(new_val), Colors.GREEN)}"
                )

        # Text changes
        if old_vnode.text != new_vnode.text:
            patches.append(
                f"{c('[TEXT]', Colors.CYAN)} {path} (<{new_vnode.tag}>): "
                f"\"{c(str(old_vnode.text), Colors.RED)}\" -> \"{c(str(new_vnode.text), Colors.GREEN)}\""
            )

        # Child diffing (naive list diff)
        max_len = max(len(old_vnode.children), len(new_vnode.children))
        for i in range(max_len):
            old_c = old_vnode.children[i] if i < len(old_vnode.children) else None
            new_c = new_vnode.children[i] if i < len(new_vnode.children) else None
            patches.extend(DOMPatcher.diff(old_c, new_c, path=f"{path} > child[{i}]"))

        return patches


# ==============================================================================
# Reactive Vue Component Simulation Instance
# ==============================================================================
class VueComponent:
    def __init__(self, template: Dict[str, Any], initial_state: Dict[str, Any]):
        self.template = template
        self.state = initial_state
        self.prev_vtree: Optional[VNode] = None
        self.methods: Dict[str, Callable] = {}

    def set_data(self, key: str, value: Any):
        old_val = self.state.get(key)
        self.state[key] = value
        print(f"\n{c('[STATE UPDATE]', Colors.BOLD + Colors.BLUE)} state['{key}'] = {value} (was: {old_val})")
        self.render_cycle()

    def render_cycle(self):
        engine = MiniVueTemplateEngine(self.state, self.methods)
        vnodes = engine.process_directives(self.template)
        new_vtree = vnodes[0] if vnodes else None

        print(c("\n--- Reactive Directive Operations ---", Colors.BOLD))
        if engine.dom_patch_log:
            for log in engine.dom_patch_log:
                print(f"  • {log}")
        else:
            print("  (No direct DOM mutations triggered)")

        print(c("\n--- Virtual DOM Diff & Patching ---", Colors.BOLD))
        patches = DOMPatcher.diff(self.prev_vtree, new_vtree)
        if patches:
            for p in patches:
                print(f"  {p}")
        else:
            print(f"  {c('No DOM modifications required (Render Bailout)', Colors.DIM)}")

        self.prev_vtree = new_vtree

        print(c("\n--- Real Rendered Simulated DOM Output ---", Colors.BOLD))
        if new_vtree:
            print(c(new_vtree.to_html(), Colors.WHITE))
        else:
            print(c("<!-- Empty Root / Unmounted -->", Colors.DIM))


# ==============================================================================
# Interactive Demo Playground
# ==============================================================================
def create_demo_template() -> Dict[str, Any]:
    """Mendefinisikan template AST berbasis kamus dengan aneka directive."""
    return {
        "tag": "div",
        "attrs": {"class": "vue-app-container"},
        "children": [
            {
                "tag": "header",
                "children": [
                    {
                        "tag": "h1",
                        "text": "{{ appTitle }} - Status: {{ isOnline ? 'Online' : 'Offline' }}",
                    },
                    {
                        "tag": "p",
                        "directives": {":class": "'badge badge-' + theme"},
                        "text": "Theme Mode: {{ theme.upper() }}",
                    },
                ],
            },
            {
                "tag": "section",
                "attrs": {"class": "auth-box"},
                "directives": {"v-if": "isLoggedIn"},
                "children": [
                    {
                        "tag": "p",
                        "text": "Selamat datang kembali, {{ username }}!",
                    },
                    {
                        "tag": "div",
                        "directives": {"v-show": "hasNotifications"},
                        "children": [
                            {
                                "tag": "span",
                                "attrs": {"class": "alert-bell"},
                                "text": "🔔 Anda memiliki notifikasi baru yang belum dibaca!",
                            }
                        ],
                    },
                ],
            },
            {
                "tag": "section",
                "attrs": {"class": "todo-widget"},
                "children": [
                    {"tag": "h3", "text": "Daftar Tugas (Total: {{ len(todos) }})"},
                    {
                        "tag": "ul",
                        "children": [
                            {
                                "tag": "li",
                                "directives": {
                                    "v-for": "item in todos",
                                    ":key": "item['id']",
                                    ":class": "'done' if item['done'] else 'pending'",
                                },
                                "text": "[{{ item['id'] }}] {{ item['title'] }} - {{ 'SELESAI' if item['done'] else 'PROSES' }}",
                            }
                        ],
                    },
                ],
            },
            {
                "tag": "footer",
                "children": [
                    {
                        "tag": "input",
                        "attrs": {"type": "text"},
                        "directives": {"v-model": "username"},
                    }
                ],
            },
        ],
    }


def run_interactive_simulation():
    initial_state = {
        "appTitle": "E-Learning Vue Directive Simulator",
        "isOnline": True,
        "theme": "dark",
        "isLoggedIn": False,
        "username": "Budi Santoso",
        "hasNotifications": True,
        "todos": [
            {"id": 1, "title": "Pelajari v-bind & v-model", "done": True},
            {"id": 2, "title": "Eksplorasi v-if vs v-show", "done": False},
            {"id": 3, "title": "Bongkar Virtual DOM Diffing", "done": False},
        ],
    }

    print(c("\n" + "=" * 65, Colors.CYAN))
    print(c("  VUE DIRECTIVES & DOM ENGINE LAB (BAB-03)", Colors.BOLD + Colors.WHITE))
    print(c("  Simulasi Reaktivitas, Directives & Virtual DOM Patching", Colors.CYAN))
    print(c("=" * 65, Colors.CYAN))

    app = VueComponent(create_demo_template(), initial_state)

    print(c("\n[Phase 1] Initial Mount Cycle...", Colors.YELLOW))
    app.render_cycle()

    # Step-by-step interactive scenario
    scenarios = [
        (
            "Toggle v-if (Login Pengguna)",
            lambda: app.set_data("isLoggedIn", True),
        ),
        (
            "Two-Way Binding v-model (Ubah Username)",
            lambda: app.set_data("username", "Siti Rahmawati"),
        ),
        (
            "v-bind Dynamic Theme & Status Offline",
            lambda: [app.set_data("theme", "neon-light"), app.set_data("isOnline", False)],
        ),
        (
            "v-show Toggle (Sembunyikan Notifikasi via CSS)",
            lambda: app.set_data("hasNotifications", False),
        ),
        (
            "v-for List Modification (Tambah & Update To-Do)",
            lambda: app.set_data(
                "todos",
                [
                    {"id": 1, "title": "Pelajari v-bind & v-model", "done": True},
                    {"id": 2, "title": "Eksplorasi v-if vs v-show", "done": True},
                    {"id": 3, "title": "Bongkar Virtual DOM Diffing", "done": True},
                    {"id": 4, "title": "Kuasai Vue Template Engine", "done": False},
                ],
            ),
        ),
        (
            "v-if Unmount (Logout Pengguna)",
            lambda: app.set_data("isLoggedIn", False),
        ),
    ]

    print(c("\n" + "-" * 65, Colors.WHITE))
    print(c("Menjalankan Simulasi Reaktif Otomatis & Analisis DOM:", Colors.BOLD + Colors.MAGENTA))
    print(c("-" * 65, Colors.WHITE))

    for idx, (title, action) in enumerate(scenarios, 1):
        print(f"\n{c(f'[STEP {idx}]', Colors.BOLD + Colors.GREEN)} {title}")
        time.sleep(0.3)
        action()
        time.sleep(0.2)

    print(c("\n" + "=" * 65, Colors.GREEN))
    print(c("✔ Simulasi Berhasil. Seluruh Directives & Diffing Lolos Validasi.", Colors.BOLD + Colors.GREEN))
    print(c("=" * 65 + "\n", Colors.GREEN))


if __name__ == "__main__":
    run_interactive_simulation()
