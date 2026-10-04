#!/usr/bin/env python3
"""
Lab Hands-on: Capstone Project - Enterprise-Grade Design System & High-Performance Dashboard
Module: CSS Optimization Engine, Multi-Tier Token Resolver, & Tree-Shaking Purger

Deskripsi Teknis:
Script ini memodelkan runtime compiler & optimizer CSS modern untuk dashboard enterprise.
Komponen utama:
1. Multi-tier Token Resolution Engine (Global -> Semantic -> Component variables)
2. Dependency Graph & Cycle Detection untuk CSS Custom Properties
3. AST-like CSS Tokenizer & Parser
4. Template Analyzer & Dead Code Eliminator (Tree-shaking CSS untuk Dashboard Widgets)
5. Critical CSS Path Splitter (Above-The-Fold vs Deferred/Async Payload)
6. Zlib-based Payload & Latency Compression Estimator
"""

import re
import sys
import time
import zlib
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

# ANSI Terminal Formatting
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_BG_DARK = "\033[48;5;235m"


class TokenEngine:
    """
    Mesin resolusi CSS Custom Properties multi-tier:
    Layer 1: Global Primitive Tokens (raw values: hex, rem, font-stack)
    Layer 2: Semantic Intent Tokens (mapped: surface-default, text-brand)
    Layer 3: Component-Scoped Tokens (button-primary-bg, kpi-card-border)
    """

    def __init__(self):
        self.raw_tokens: Dict[str, str] = {}
        self.resolved_tokens: Dict[str, str] = {}
        self.var_regex = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*(?:,\s*([^)]+))?\)")

    def register_tokens(self, token_dict: Dict[str, str]) -> None:
        """Mendaftarkan token ke dalam dictionary global/semantic."""
        self.raw_tokens.update(token_dict)

    def resolve_all(self) -> Dict[str, str]:
        """
        Menyelesaikan resolusi dependensi token hierarkis menggunakan Topological Order
        dan mendeteksi error jika terjadi siklus referensi (circular dependency).
        """
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        in_degree: Dict[str, int] = {k: 0 for k in self.raw_tokens}

        for token, val in self.raw_tokens.items():
            refs = self.var_regex.findall(val)
            for ref, _ in refs:
                if ref in self.raw_tokens:
                    adjacency[ref].add(token)
                    in_degree[token] = in_degree.get(token, 0) + 1

        queue = deque([t for t, deg in in_degree.items() if deg == 0])
        resolved_count = 0

        # Clone raw tokens for in-place value substitution
        resolved = dict(self.raw_tokens)

        while queue:
            curr = queue.popleft()
            resolved_count += 1

            for neighbor in adjacency[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if resolved_count < len(self.raw_tokens):
            unresolved = [t for t, deg in in_degree.items() if deg > 0]
            raise ValueError(f"Circular dependency terdeteksi pada tokens: {unresolved}")

        # Substitusi bertahap sampai konvergen
        for _ in range(5):  # Max nesting depth limit
            has_var = False
            for k, v in resolved.items():
                if "var(" in v:
                    has_var = True
                    resolved[k] = self.var_regex.sub(
                        lambda m: resolved.get(m.group(1), m.group(2) or m.group(0)), v
                    )
            if not has_var:
                break

        self.resolved_tokens = resolved
        return self.resolved_tokens


class CSSRule:
    """Representasi atomik sebuah CSS Rule (Selector + Property Block)."""

    def __init__(self, selector: str, declarations: str, is_critical: bool = False):
        self.selector = selector.strip()
        self.declarations = declarations.strip()
        self.is_critical = is_critical

    def serialize(self, minified: bool = True) -> str:
        """Serialisasi rule ke format string."""
        if minified:
            decl = re.sub(r"\s+", " ", self.declarations).strip()
            return f"{self.selector}{{{decl}}}"
        return f"{self.selector} {{\n  {self.declarations}\n}}"


class DesignSystemCompiler:
    """
    Compiler parser CSS yang menangani de-duplikasi, token-inlining,
    dan Dead Code Elimination (Purging) berdasarkan dashboard HTML usage.
    """

    def __init__(self, token_engine: TokenEngine):
        self.token_engine = token_engine
        self.rules: List[CSSRule] = []

    def parse_stylesheet(self, raw_css: str, critical_selectors: Set[str]) -> None:
        """Melakukan tokenization kasar dan pembentukan list CSSRule."""
        # Menghapus komentar CSS
        clean_css = re.sub(r"/\*.*?\*/", "", raw_css, flags=re.DOTALL)
        rule_blocks = re.findall(r"([^{]+)\{([^}]+)\}", clean_css)

        for raw_sel, raw_decl in rule_blocks:
            selectors = [s.strip() for s in raw_sel.split(",") if s.strip()]
            for sel in selectors:
                is_crit = any(crit in sel for crit in critical_selectors)
                self.rules.append(CSSRule(sel, raw_decl, is_critical=is_crit))

    def inline_tokens(self) -> None:
        """Mengganti var(--token) dengan nilai computed dari TokenEngine."""
        tokens = self.token_engine.resolved_tokens
        for rule in self.rules:
            for t_name, t_val in tokens.items():
                if t_name in rule.declarations:
                    rule.declarations = rule.declarations.replace(f"var({t_name})", t_val)

    def tree_shake(self, dashboard_html: str) -> Tuple[List[CSSRule], List[CSSRule]]:
        """
        Menganalisis file template HTML/DOM dashboard dan menghapus CSS selectors
        yang tidak pernah direferensikan dalam template.
        """
        # Ekstrak class, id, dan tag dari HTML
        used_classes = set(re.findall(r'class=["\']([^"\']+)["\']', dashboard_html))
        flattened_classes = set()
        for c_group in used_classes:
            flattened_classes.update(c_group.split())

        used_ids = set(re.findall(r'id=["\']([^"\']+)["\']', dashboard_html))
        used_tags = set(re.findall(r'<([a-zA-Z0-9]+)', dashboard_html))

        kept_rules: List[CSSRule] = []
        purged_rules: List[CSSRule] = []

        for rule in self.rules:
            sel = rule.selector

            # Rule global seperti :root, *, html, body selalu disimpan
            if sel in [":root", "*", "html", "body"] or sel.startswith(":"):
                kept_rules.append(rule)
                continue

            # Check class selectors (.btn, .kpi-card, dsb)
            class_matches = re.findall(r"\.([a-zA-Z0-9_-]+)", sel)
            id_matches = re.findall(r"#([a-zA-Z0-9_-]+)", sel)
            tag_matches = re.findall(r"^([a-zA-Z0-9]+)", sel)

            is_used = False
            if class_matches and any(c in flattened_classes for c in class_matches):
                is_used = True
            elif id_matches and any(i in used_ids for i in id_matches):
                is_used = True
            elif tag_matches and any(t in used_tags for t in tag_matches):
                is_used = True

            if is_used:
                kept_rules.append(rule)
            else:
                purged_rules.append(rule)

        return kept_rules, purged_rules


def simulate_network_metrics(css_content: str, label: str) -> None:
    """Menghitung metrik performa transfer (Raw vs Gzip compressed)."""
    raw_bytes = len(css_content.encode("utf-8"))
    compressed = zlib.compress(css_content.encode("utf-8"), level=9)
    comp_bytes = len(compressed)
    ratio = (1.0 - (comp_bytes / raw_bytes)) * 100 if raw_bytes > 0 else 0

    print(f"  {CLR_CYAN}[{label}]{CLR_RESET}")
    print(f"    Raw Size       : {raw_bytes:>7} bytes")
    print(f"    Gzip (Level 9) : {comp_bytes:>7} bytes")
    print(f"    Savings Ratio  : {ratio:>6.2f}%")


def main():
    print(f"{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}  CAPSTONE LAB: HIGH-PERFORMANCE DESIGN SYSTEM COMPILER & OPTIMIZER    {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}\n")

    t_start = time.perf_counter()

    # 1. Definisi Multi-Tier Design Tokens
    print(f"{CLR_BOLD}[FASE 1] Inisialisasi & Resolusi Multi-Tier Design Tokens...{CLR_RESET}")
    token_engine = TokenEngine()
    tokens = {
        # Tier 1: Primitive Palette
        "--ds-primitive-blue-500": "#0284c7",
        "--ds-primitive-blue-600": "#0369a1",
        "--ds-primitive-gray-100": "#f1f5f9",
        "--ds-primitive-gray-800": "#1e293b",
        "--ds-primitive-emerald":  "#10b981",
        "--ds-primitive-rose":     "#f43f5e",
        "--ds-primitive-spacing-4": "1rem",
        "--ds-primitive-spacing-8": "2rem",
        "--ds-primitive-radius-md": "0.375rem",

        # Tier 2: Semantic Intent Tokens
        "--ds-color-bg-canvas":    "var(--ds-primitive-gray-100)",
        "--ds-color-text-main":    "var(--ds-primitive-gray-800)",
        "--ds-color-brand":        "var(--ds-primitive-blue-500)",
        "--ds-color-brand-hover":  "var(--ds-primitive-blue-600)",
        "--ds-color-success":      "var(--ds-primitive-emerald)",
        "--ds-color-danger":       "var(--ds-primitive-rose)",

        # Tier 3: Component-Scoped Tokens
        "--kpi-card-bg":           "#ffffff",
        "--kpi-card-padding":      "var(--ds-primitive-spacing-4)",
        "--kpi-card-radius":       "var(--ds-primitive-radius-md)",
        "--btn-primary-bg":        "var(--ds-color-brand)",
        "--btn-primary-hover":     "var(--ds-color-brand-hover)",
    }

    token_engine.register_tokens(tokens)
    resolved_map = token_engine.resolve_all()
    print(f"  {CLR_GREEN}✓{CLR_RESET} Berhasil menyelesaikan {len(resolved_map)} token tanpa circular dependency.")
    print(f"  Sample Resolved: '--btn-primary-bg' -> {CLR_YELLOW}{resolved_map['--btn-primary-bg']}{CLR_RESET}")

    # 2. Master CSS Design System (Termasuk Atomic Utilities & Unused Legacy Components)
    raw_design_system_css = """
    :root {
        --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background-color: var(--ds-color-bg-canvas); color: var(--ds-color-text-main); font-family: var(--font-family); }
    
    /* Critical Above-the-fold Dashboard Widgets */
    .dashboard-header { display: flex; justify-content: space-between; padding: var(--ds-primitive-spacing-4); background: #ffffff; }
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--ds-primitive-spacing-4); padding: var(--ds-primitive-spacing-4); }
    .kpi-card { background: var(--kpi-card-bg); padding: var(--kpi-card-padding); border-radius: var(--kpi-card-radius); box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .kpi-title { font-size: 0.875rem; color: #64748b; }
    .kpi-metric { font-size: 1.5rem; font-weight: bold; margin-top: 0.5rem; }
    .metric-trend-up { color: var(--ds-color-success); font-size: 0.875rem; }
    .metric-trend-down { color: var(--ds-color-danger); font-size: 0.875rem; }
    .btn-action { background: var(--btn-primary-bg); color: #ffffff; padding: 0.5rem 1rem; border: none; border-radius: var(--ds-primitive-radius-md); cursor: pointer; }
    .btn-action:hover { background: var(--btn-primary-hover); }

    /* Deferred Below-the-fold or Unused Legacy Components */
    .legacy-carousel { display: none; width: 100%; height: 300px; }
    .legacy-banner-popup { position: fixed; top: 50%; left: 50%; z-index: 9999; }
    .audit-table { width: 100%; border-collapse: collapse; margin-top: var(--ds-primitive-spacing-8); }
    .audit-table th { background: #f8fafc; padding: 0.75rem; border-bottom: 1px solid #e2e8f0; }
    .audit-table td { padding: 0.75rem; border-bottom: 1px solid #e2e8f0; }
    .slider-knob { width: 24px; height: 24px; border-radius: 50%; background: #94a3b8; }
    .chart-tooltip-floating { position: absolute; pointer-events: none; opacity: 0; transition: opacity 0.2s; }
    
    /* Utility Bloat (Simulasi CSS Framework Atomic Utilities) */
    .p-1 { padding: 0.25rem; }
    .p-2 { padding: 0.5rem; }
    .p-4 { padding: 1rem; }
    .p-8 { padding: 2rem; }
    .m-1 { margin: 0.25rem; }
    .m-2 { margin: 0.5rem; }
    .hidden { display: none; }
    .flex { display: flex; }
    .inline-block { display: inline-block; }
    """

    # 3. Representasi Dashboard Template HTML
    dashboard_template_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Analytics Executive Dashboard</title></head>
    <body>
        <header class="dashboard-header">
            <h1>Executive Summary</h1>
            <button class="btn-action">Export Report</button>
        </header>
        <main class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Monthly Recurring Revenue</div>
                <div class="kpi-metric">$128,450</div>
                <span class="metric-trend-up">+14.2%</span>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Churn Rate</div>
                <div class="kpi-metric">1.12%</div>
                <span class="metric-trend-down">-0.4%</span>
            </div>
        </main>
        <section>
            <table class="audit-table">
                <thead><tr><th>Timestamp</th><th>User</th></tr></thead>
                <tbody><tr><td>2026-03-30</td><td>admin@corp.internal</td></tr></tbody>
            </table>
        </section>
    </body>
    </html>
    """

    print(f"\n{CLR_BOLD}[FASE 2] Parsing Master CSS & Token Inlining...{CLR_RESET}")
    compiler = DesignSystemCompiler(token_engine)
    critical_selectors = {".dashboard-header", ".kpi-grid", ".kpi-card", ".kpi-title", ".kpi-metric", ".btn-action", "body", "*", ":root"}
    compiler.parse_stylesheet(raw_design_system_css, critical_selectors)
    compiler.inline_tokens()
    print(f"  {CLR_GREEN}✓{CLR_RESET} Parsed {len(compiler.rules)} CSS atomic rules.")

    # 4. Dead Code Elimination (Tree-Shaking)
    print(f"\n{CLR_BOLD}[FASE 3] Menjalankan AST Tree-Shaking (Purging unreferenced selectors)...{CLR_RESET}")
    active_rules, purged_rules = compiler.tree_shake(dashboard_template_html)
    print(f"  {CLR_GREEN}✓ Kept Rules   :{CLR_RESET} {len(active_rules)} rules aktif.")
    print(f"  {CLR_RED}✗ Purged Rules :{CLR_RESET} {len(purged_rules)} rules usang/tidak terpakai.")
    for pr in purged_rules:
        print(f"    - Terpangkas: {CLR_YELLOW}{pr.selector}{CLR_RESET}")

    # 5. Critical Path CSS Splitting
    print(f"\n{CLR_BOLD}[FASE 4] Ekstraksi Critical Path CSS (Above-the-fold vs Deferred)...{CLR_RESET}")
    critical_css_rules = [r for r in active_rules if r.is_critical]
    deferred_css_rules = [r for r in active_rules if not r.is_critical]

    critical_bundle = "\n".join([r.serialize(minified=True) for r in critical_css_rules])
    deferred_bundle = "\n".join([r.serialize(minified=True) for r in deferred_css_rules])
    full_compiled_css = "\n".join([r.serialize(minified=True) for r in active_rules])

    print(f"  {CLR_CYAN}Critical Rules (Inlined in <head>) :{CLR_RESET} {len(critical_css_rules)} rules")
    print(f"  {CLR_CYAN}Deferred Rules (Async loaded)     :{CLR_RESET} {len(deferred_css_rules)} rules")

    # 6. Benchmark Kompresi & Payload Report
    print(f"\n{CLR_BOLD}[FASE 5] Network Payload & Latency Benchmark{CLR_RESET}")
    simulate_network_metrics(raw_design_system_css, "Raw Unoptimized Design System")
    simulate_network_metrics(full_compiled_css, "Tree-Shaken & Minified CSS")
    simulate_network_metrics(critical_bundle, "Critical Path CSS Bundle")

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ Lab Berhasil Selesai dalam {elapsed_ms:.2f} ms.{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}")


if __name__ == "__main__":
    main()