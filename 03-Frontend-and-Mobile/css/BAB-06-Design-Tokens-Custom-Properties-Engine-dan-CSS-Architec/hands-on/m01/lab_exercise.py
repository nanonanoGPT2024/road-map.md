#!/usr/bin/env python3
"""
Lab Exercise: Design Tokens, CSS Custom Properties Engine, and Architecture Simulator
BAB-06: Design Tokens, Custom Properties Engine, dan CSS Architecture

Fitur Inti:
1. Multi-tier Design Token Dictionary (Primitive -> Semantic -> Component)
2. Recursive CSS var() Parser & Resolver dengan Fallback Chain
3. Circular Dependency Detection (mencegah infinite loop)
4. DOM Cascade & Custom Property Scope Inheritance Simulator
5. Terminal UI interaktif berbasis kode ANSI warna
"""

import sys
import re
from typing import Dict, List, Optional, Tuple, Set


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[48;5;236m"


def header(title: str) -> None:
    print(f"\n{ANSI.BOLD}{ANSI.BG_BLUE}{ANSI.WHITE} [DEMO] {title.ljust(64)} {ANSI.RESET}")


def subheader(title: str) -> None:
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}--- {title} ---{ANSI.RESET}")


class TokenEngine:
    """Mesin resolusi variabel CSS Custom Properties dengan dukungan fallback dan pendeteksi siklus."""

    def __init__(self):
        # Primitive / Global tokens (:root)
        self.primitive_tokens: Dict[str, str] = {}
        # Semantic / Alias tokens
        self.semantic_tokens: Dict[str, str] = {}
        # Component-level scoped tokens
        self.component_tokens: Dict[str, Dict[str, str]] = {}

    def register_primitive(self, name: str, val: str) -> None:
        self.primitive_tokens[name] = val

    def register_semantic(self, name: str, val: str) -> None:
        self.semantic_tokens[name] = val

    def register_component_token(self, component: str, prop: str, val: str) -> None:
        if component not in self.component_tokens:
            self.component_tokens[component] = {}
        self.component_tokens[component][prop] = val

    def parse_var_expr(self, expr: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Menguraikan string 'var(--prop, fallback)' menjadi tuple ('--prop', 'fallback').
        Mendukung nested fallback sederhana.
        """
        expr = expr.strip()
        if not expr.startswith("var(") or not expr.endswith(")"):
            return None, None

        inner = expr[4:-1].strip()
        # Cari koma pemisah pertama di luar tanda kurung nested
        depth = 0
        split_idx = -1
        for idx, ch in enumerate(inner):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                split_idx = idx
                break

        if split_idx != -1:
            var_name = inner[:split_idx].strip()
            fallback = inner[split_idx + 1:].strip()
            return var_name, fallback
        else:
            return inner.strip(), None

    def resolve(
        self,
        prop_or_expr: str,
        scope: Optional[Dict[str, str]] = None,
        visited: Optional[Set[str]] = None,
        trace: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], List[str]]:
        """
        Menyelesaikan nilai token secara rekursif mengikuti cascade CSS.
        Scope order: Scoped/Component -> Semantic -> Primitive -> Fallback.
        """
        if visited is None:
            visited = set()
        if trace is None:
            trace = []

        val = prop_or_expr.strip()

        # Jika bukan ekspresi var(), kembalikan nilai literal
        if not (val.startswith("var(") and val.endswith(")")):
            if val.startswith("--"):
                # Mencari nilai variabel dari scope hierarchy
                candidate = None
                source = "unknown"
                if scope and val in scope:
                    candidate = scope[val]
                    source = "component-scope"
                elif val in self.semantic_tokens:
                    candidate = self.semantic_tokens[val]
                    source = "semantic-layer"
                elif val in self.primitive_tokens:
                    candidate = self.primitive_tokens[val]
                    source = "primitive-layer"

                if candidate is None:
                    trace.append(f"{ANSI.RED}UNDEF({val}){ANSI.RESET}")
                    return None, trace

                trace.append(f"{val} ({ANSI.DIM}{source}{ANSI.RESET}) -> {candidate}")

                if val in visited:
                    trace.append(f"{ANSI.RED}CIRCULAR REF DETECTED ON {val}!{ANSI.RESET}")
                    return f"[CIRCULAR_ERROR:{val}]", trace

                new_visited = visited | {val}
                return self.resolve(candidate, scope, new_visited, trace)
            return val, trace

        # Parsing var(--name, fallback)
        var_name, fallback = self.parse_var_expr(val)
        if not var_name:
            return None, trace

        trace.append(f"Resolving: var({var_name}{f', fallback={fallback}' if fallback else ''})")

        resolved_val, trace = self.resolve(var_name, scope, visited, trace)

        if resolved_val is not None and not resolved_val.startswith("[CIRCULAR_ERROR:"):
            return resolved_val, trace

        # Jika variabel tidak ditemukan atau circular, gunakan fallback jika ada
        if fallback:
            trace.append(f"{ANSI.YELLOW}Trigger fallback -> {fallback}{ANSI.RESET}")
            return self.resolve(fallback, scope, visited, trace)

        return None, trace


class CSSNode:
    """Representasi elemen dalam pohon DOM untuk mensimulasikan CSS Custom Property Cascade."""

    def __init__(self, tag: str, class_name: str = "", parent: Optional["CSSNode"] = None):
        self.tag = tag
        self.class_name = class_name
        self.parent = parent
        self.styles: Dict[str, str] = {}
        self.children: List["CSSNode"] = []
        if parent:
            parent.children.append(self)

    def set_custom_property(self, prop: str, value: str) -> None:
        self.styles[prop] = value

    def get_computed_property(self, prop: str, engine: TokenEngine) -> Tuple[Optional[str], List[str]]:
        # Kumpulkan cascade scope dari root turun ke node ini
        hierarchy: List["CSSNode"] = []
        curr: Optional["CSSNode"] = self
        while curr:
            hierarchy.insert(0, curr)
            curr = curr.parent

        merged_scope: Dict[str, str] = {}
        for node in hierarchy:
            merged_scope.update(node.styles)

        return engine.resolve(prop, scope=merged_scope)


def run_benchmark_and_demo():
    engine = TokenEngine()

    header("1. REGISTRASI TOKEN MULTI-TIER (SYSTEM ARCHITECTURE)")
    # Tier 1: Primitives (Design System Foundations)
    engine.register_primitive("--color-blue-500", "#1d4ed8")
    engine.register_primitive("--color-blue-600", "#2563eb")
    engine.register_primitive("--color-gray-100", "#f3f4f6")
    engine.register_primitive("--color-gray-900", "#111827")
    engine.register_primitive("--space-unit", "4px")
    engine.register_primitive("--space-4", "calc(var(--space-unit) * 4)")
    engine.register_primitive("--radius-md", "8px")

    print(f"{ANSI.BOLD}Layer 1: Primitive Tokens (:root){ANSI.RESET}")
    for k, v in engine.primitive_tokens.items():
        print(f"  {ANSI.GREEN}{k}{ANSI.RESET}: {v}")

    # Tier 2: Semantic (Design Intent / Theming)
    engine.register_semantic("--color-surface-bg", "var(--color-gray-100)")
    engine.register_semantic("--color-surface-text", "var(--color-gray-900)")
    engine.register_semantic("--color-brand-primary", "var(--color-blue-600)")
    engine.register_semantic("--action-primary-default", "var(--color-brand-primary)")

    print(f"\n{ANSI.BOLD}Layer 2: Semantic Tokens (Design Decisions){ANSI.RESET}")
    for k, v in engine.semantic_tokens.items():
        print(f"  {ANSI.CYAN}{k}{ANSI.RESET}: {v}")

    # Tier 3: Component Tokens (BEM / Scoped Contracts)
    engine.register_component_token("button-primary", "--btn-bg", "var(--action-primary-default)")
    engine.register_component_token("button-primary", "--btn-padding", "var(--space-4, 16px)")
    engine.register_component_token("button-primary", "--btn-radius", "var(--radius-md, 4px)")

    print(f"\n{ANSI.BOLD}Layer 3: Component Tokens (Component API Scope){ANSI.RESET}")
    for comp, props in engine.component_tokens.items():
        print(f"  Component [{ANSI.MAGENTA}.c-{comp}{ANSI.RESET}]:")
        for pk, pv in props.items():
            print(f"    {pk}: {pv}")

    header("2. SIMULASI RESOLUSI VAR() DENGAN TRACE & FALLBACK")
    test_queries = [
        ("--btn-bg", engine.component_tokens["button-primary"]),
        ("var(--unknown-brand-color, var(--color-blue-500))", {}),
        ("var(--missing-token, var(--also-missing, #ff0055))", {}),
        ("var(--action-primary-default)", {}),
    ]

    for expr, comp_scope in test_queries:
        subheader(f"Query: {expr}")
        final_val, traces = engine.resolve(expr, scope=comp_scope)
        for step in traces:
            print(f"  {ANSI.DIM}|-{ANSI.RESET} {step}")
        print(f"  {ANSI.BOLD}{ANSI.GREEN}>>> COMPUTED VALUE: {final_val}{ANSI.RESET}")

    header("3. PENDETEKSI SIKLUS (CIRCULAR DEPENDENCY DETECTION)")
    engine.register_semantic("--loop-alpha", "var(--loop-beta)")
    engine.register_semantic("--loop-beta", "var(--loop-gamma)")
    engine.register_semantic("--loop-gamma", "var(--loop-alpha, #fallback-green)")

    print("Definisi variabel melingkar: --loop-alpha -> --loop-beta -> --loop-gamma -> --loop-alpha")
    val, cycle_traces = engine.resolve("var(--loop-alpha)")
    for step in cycle_traces:
        print(f"  {ANSI.DIM}|-{ANSI.RESET} {step}")
    print(f"  Hasil resolusi aman: {ANSI.YELLOW}{val}{ANSI.RESET}")

    header("4. SIMULASI CASCADE & INHERITANCE PADA DOM TREE")
    # Tree: html (:root) -> body.theme-dark -> main -> button.c-btn
    root_node = CSSNode("html", ":root")
    root_node.set_custom_property("--bg-color", "#ffffff")
    root_node.set_custom_property("--text-color", "#111827")

    dark_container = CSSNode("section", "theme-dark", parent=root_node)
    dark_container.set_custom_property("--bg-color", "#0f172a")  # override
    dark_container.set_custom_property("--text-color", "#f8fafc")  # override

    btn = CSSNode("button", "c-btn", parent=dark_container)
    btn.set_custom_property("--btn-local-padding", "12px 24px")

    print("DOM Hierarchy:")
    print("  <html :root> [def: --bg-color: #ffffff, --text-color: #111827]")
    print("    <section class='theme-dark'> [override: --bg-color: #0f172a, --text-color: #f8fafc]")
    print("      <button class='c-btn'> [def: --btn-local-padding: 12px 24px]")

    print(f"\n{ANSI.BOLD}Resolving properties pada node `<button>`:{ANSI.RESET}")
    for prop in ["--bg-color", "--text-color", "--btn-local-padding", "--missing-prop"]:
        computed, _ = btn.get_computed_property(prop, engine)
        print(f"  {prop} inherited computed = {ANSI.CYAN}{computed}{ANSI.RESET}")


def interactive_mode():
    engine = TokenEngine()
    engine.register_primitive("--brand-primary", "#4f46e5")
    engine.register_primitive("--spacing-base", "8px")
    engine.register_semantic("--btn-bg", "var(--brand-primary)")

    header("MODE INTERAKTIF CSS CUSTOM PROPERTIES ENGINE")
    print(f"{ANSI.YELLOW}Ketik ekspresi CSS var (contoh: `var(--brand-primary)` atau `var(--missing, #000)`)")
    print(f"Ketik 'exit' atau tekan Ctrl+D untuk keluar.{ANSI.RESET}\n")

    while True:
        try:
            line = input(f"{ANSI.BOLD}{ANSI.MAGENTA}css-engine>{ANSI.RESET} ").strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit"):
                print("Keluar dari simulator.")
                break
            val, trace = engine.resolve(line)
            for t in trace:
                print(f"  {ANSI.DIM}>{ANSI.RESET} {t}")
            print(f"  {ANSI.BOLD}{ANSI.GREEN}Computed: {val}{ANSI.RESET}\n")
        except (EOFError, KeyboardInterrupt):
            print("\nSesi interaktif selesai.")
            break


def main():
    print(f"{ANSI.BOLD}{ANSI.CYAN}===================================================================={ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.WHITE} CSS CUSTOM PROPERTIES & DESIGN TOKENS ARCHITECTURE ENGINE v1.0 {ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}===================================================================={ANSI.RESET}")

    run_benchmark_and_demo()

    if sys.stdin.isatty():
        interactive_mode()
    else:
        print(f"\n{ANSI.DIM}[Automated Run]: Non-TTY stdin terdeteksi. Sesi simulasi selesai sukses.{ANSI.RESET}\n")


if __name__ == "__main__":
    main()
