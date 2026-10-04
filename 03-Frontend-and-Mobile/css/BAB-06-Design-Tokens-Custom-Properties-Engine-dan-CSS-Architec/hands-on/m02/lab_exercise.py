#!/usr/bin/env python3
"""
Lab Hands-on: Design Tokens, Custom Properties Engine & CSS Architecture
Modul 02 Deep Dive: W3C Token Transformation, Cascading Scope, and Cycle Resolution

Script ini mengimplementasikan CSS Custom Properties & Design Token Engine mandiri:
1. W3C DTCG (Design Tokens Community Group) Token Parser & Transformer (px->rem, alias dereferencing).
2. CSS Variable Resolver Engine yang mensimulasikan DOM Scoping/Inheritance (Cascade).
3. Evaluator ekspresi CSS `var(--name, fallback)` dengan deteksi dependensi sirkular (Cycle Detection).
4. Export generator untuk file CSS terkompilasi.
"""

import sys
import re
import json
import time
from typing import Dict, Any, List, Optional, Set, Tuple

# ANSI Escape Sequences untuk styling terminal output
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RESET = "\033[0m"

# -------------------------------------------------------------------------
# 1. DESIGN TOKEN PARSER & TRANSFORMER
# -------------------------------------------------------------------------

class DesignTokenTransformer:
    """
    Mengonversi token W3C standar menjadi variabel CSS siap pakai.
    Mendukung transformasi unit (px -> rem) dan dereferensi token alias.
    """
    BASE_FONT_SIZE_PX = 16.0

    @staticmethod
    def px_to_rem(value: str) -> str:
        """Mengonversi nilai absolut px ke proporsional rem berbasis standard font size."""
        match = re.match(r"^([0-9.]+)px$", value.strip())
        if match:
            px_val = float(match.group(1))
            rem_val = px_val / DesignTokenTransformer.BASE_FONT_SIZE_PX
            return f"{rem_val:.4f}".rstrip('0').rstrip('.') + "rem"
        return value

    @classmethod
    def transform_value(cls, token_type: str, raw_value: Any) -> str:
        """Mentransformasikan nilai token mentah berdasarkan tipe metadata-nya."""
        str_val = str(raw_value)
        if token_type in ("dimension", "spacing", "fontSize"):
            return cls.px_to_rem(str_val)
        return str_val


# -------------------------------------------------------------------------
# 2. CSS VARIABLE ENGINE & DOM SCOPING
# -------------------------------------------------------------------------

class DOMScopeNode:
    """
    Representasi node DOM hirarkis untuk simulasi inheritance variabel CSS.
    Node mewarisi custom properties dari parent (Lexical/DOM Scoping).
    """
    def __init__(self, name: str, parent: Optional['DOMScopeNode'] = None):
        self.name = name
        self.parent = parent
        self.children: List['DOMScopeNode'] = []
        self.local_properties: Dict[str, str] = {}
        if parent:
            parent.children.append(self)

    def set_property(self, name: str, val: str):
        if not name.startswith("--"):
            name = f"--{name}"
        self.local_properties[name] = val

    def lookup_property(self, prop_name: str) -> Optional[str]:
        """Menelusuri scope tree ke atas (bubbling) sesuai aturan CSS Cascade."""
        if prop_name in self.local_properties:
            return self.local_properties[prop_name]
        if self.parent:
            return self.parent.lookup_property(prop_name)
        return None


class CSSCustomPropertiesEngine:
    """
    Engine untuk memecahkan ekspresi CSS var() dengan dukungan fallback berulang
    dan algoritma Cycle Detection (DFS) untuk mencegah infinite recursion.
    """
    # Regex untuk mendeteksi pemanggilan var(--identifier, fallback)
    VAR_REGEX = re.compile(r"var\(\s*(--[a-zA-Z0-9\-_]+)\s*(?:,\s*([^()]+|\((?:[^()]+|\([^()]*\))*\)))?\s*\)")

    def __init__(self):
        self.diagnostics: List[str] = []

    def parse_and_resolve(self, expression: str, scope: DOMScopeNode, visited: Optional[Set[str]] = None) -> Tuple[str, bool]:
        """
        Mengevaluasi ekspresi nilai CSS secara rekursif.
        Mengembalikan tuple: (computed_value, is_valid).
        Sesuai spesifikasi CSS: dependensi sirkular menghasilkan 'guaranteed-invalid at computed-value time'.
        """
        if visited is None:
            visited = set()

        if "var(" not in expression:
            return expression, True

        result = expression
        matches = list(self.VAR_REGEX.finditer(expression))
        
        for match in matches:
            full_match = match.group(0)
            var_name = match.group(1)
            fallback = match.group(2)

            if var_name in visited:
                self.diagnostics.append(f"Cycle terdeteksi pada {CLR_RED}{var_name}{CLR_RESET} di node '{scope.name}'")
                return "unset /* [INVALID: Circular Dependency] */", False

            raw_val = scope.lookup_property(var_name)

            if raw_val is not None:
                new_visited = visited.copy()
                new_visited.add(var_name)
                resolved_val, valid = self.parse_and_resolve(raw_val, scope, new_visited)
                if valid:
                    result = result.replace(full_match, resolved_val, 1)
                else:
                    # Jika dependensi gagal, coba fallback jika ada
                    if fallback:
                        fb_resolved, fb_valid = self.parse_and_resolve(fallback.strip(), scope, visited)
                        result = result.replace(full_match, fb_resolved, 1)
                    else:
                        return "unset /* [INVALID: Unresolved Cycle] */", False
            else:
                # Variabel tidak ditemukan, gunakan fallback jika ada
                if fallback:
                    fb_resolved, fb_valid = self.parse_and_resolve(fallback.strip(), scope, visited)
                    result = result.replace(full_match, fb_resolved, 1)
                else:
                    self.diagnostics.append(f"Undefined variable {CLR_YELLOW}{var_name}{CLR_RESET} tanpa fallback di '{scope.name}'")
                    result = result.replace(full_match, "initial /* [UNSET] */", 1)

        return result, True


# -------------------------------------------------------------------------
# 3. LAB EXECUTION SIMULATION
# -------------------------------------------------------------------------

def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}>>> {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")

def main():
    print_header("Design Tokens, Custom Properties Engine & CSS Architecture")
    
    # --- STEP 1: Ingestion W3C Design Tokens ---
    print(f"\n{CLR_BOLD}[1] INGESTION & TRANSFORMATION: W3C Token Specification{CLR_RESET}")
    w3c_tokens_raw = {
        "color": {
            "brand": {"primary": {"$value": "#1d4ed8", "$type": "color"}},
            "surface": {"dark": {"$value": "#0f172a", "$type": "color"}}
        },
        "spacing": {
            "sm": {"$value": "8px", "$type": "spacing"},
            "md": {"$value": "16px", "$type": "spacing"},
            "lg": {"$value": "32px", "$type": "spacing"}
        },
        "typography": {
            "font-base": {"$value": "16px", "$type": "fontSize"},
            "font-h1": {"$value": "48px", "$type": "fontSize"}
        }
    }

    flattened_root_css: Dict[str, str] = {}

    def extract_tokens(data: dict, prefix="--"):
        for key, val in data.items():
            if isinstance(val, dict):
                if "$value" in val:
                    transformed = DesignTokenTransformer.transform_value(val.get("$type", ""), val["$value"])
                    prop_name = f"{prefix}{key}"
                    flattened_root_css[prop_name] = transformed
                else:
                    extract_tokens(val, f"{prefix}{key}-")

    extract_tokens(w3c_tokens_raw)
    
    for prop, val in flattened_root_css.items():
        print(f"  {CLR_GREEN}✔{CLR_RESET} Ingested Token: {CLR_BOLD}{prop}{CLR_RESET} => {CLR_MAGENTA}{val}{CLR_RESET}")

    # --- STEP 2: Scoped DOM Simulation & Custom Properties ---
    print_header("CSS Scope Hierarchy & Dynamic Cascade Simulator")
    
    # Root: :root scope
    root_scope = DOMScopeNode(name=":root")
    for prop, val in flattened_root_css.items():
        root_scope.set_property(prop, val)

    # Tambahkan variabel dinamis berbasis token
    root_scope.set_property("--theme-bg", "var(--color-surface-dark)")
    root_scope.set_property("--theme-text", "#f8fafc")
    root_scope.set_property("--btn-padding", "var(--spacing-sm) var(--spacing-md)")

    # Komponen 1: Card container (.card)
    card_scope = DOMScopeNode(name=".card", parent=root_scope)
    card_scope.set_property("--card-bg", "var(--theme-bg)")
    card_scope.set_property("--card-spacing", "var(--spacing-lg)")

    # Komponen 2: Nested Theme Inversion (.card.dark-invert)
    inverted_card = DOMScopeNode(name=".card.theme-inverted", parent=card_scope)
    inverted_card.set_property("--theme-bg", "#ffffff")
    inverted_card.set_property("--theme-text", "#000000")

    # Komponen 3: Button inside Inverted Card (.btn)
    btn_scope = DOMScopeNode(name=".btn-action", parent=inverted_card)
    btn_scope.set_property("--btn-bg", "var(--theme-bg, #000)")
    btn_scope.set_property("--btn-color", "var(--theme-text, #fff)")

    # Menampilkan Cascade Lookup
    engine = CSSCustomPropertiesEngine()

    print(f"\n{CLR_BOLD}Resolusi Properti CSS di scope {CLR_YELLOW}.card.theme-inverted -> .btn-action{CLR_RESET}:")
    properties_to_resolve = [
        ("Background", "var(--btn-bg)"),
        ("Text Color", "var(--btn-color)"),
        ("Padding", "var(--btn-padding)"),
        ("Spacing Parent", "var(--card-spacing)"),
        ("Unset Prop w/ Fallback", "var(--non-existent, #e2e8f0)")
    ]

    for label, expr in properties_to_resolve:
        resolved, valid = engine.parse_and_resolve(expr, btn_scope)
        status = f"{CLR_GREEN}[VALID]{CLR_RESET}" if valid else f"{CLR_RED}[FAIL]{CLR_RESET}"
        print(f"  {status} {label:<22} : {CLR_DIM}{expr:<30}{CLR_RESET} -> {CLR_BOLD}{CLR_CYAN}{resolved}{CLR_RESET}")

    # --- STEP 3: Circular Dependency Resolution Stress Test ---
    print_header("Cycle Detection Stress Test (Guaranteed Invalid Engine)")

    cycle_scope = DOMScopeNode(name=".danger-zone-cycle", parent=root_scope)
    # Membuat ring dependency: --cycle-a -> --cycle-b -> --cycle-c -> --cycle-a
    cycle_scope.set_property("--cycle-a", "calc(var(--cycle-b) + 2px)")
    cycle_scope.set_property("--cycle-b", "calc(var(--cycle-c) * 1.5)")
    cycle_scope.set_property("--cycle-c", "var(--cycle-a)")
    cycle_scope.set_property("--safe-fallback", "var(--cycle-a, 40px)")

    print(f"Definisi Cyclic Variables:")
    print(f"  --cycle-a: calc(var(--cycle-b) + 2px)")
    print(f"  --cycle-b: calc(var(--cycle-c) * 1.5)")
    print(f"  --cycle-c: var(--cycle-a)")
    print(f"  --safe-fallback: var(--cycle-a, 40px)")
    print(f"\n{CLR_BOLD}Mengeksekusi Resolusi AST...{CLR_RESET}")

    expr_direct = "var(--cycle-a)"
    computed_val, valid = engine.parse_and_resolve(expr_direct, cycle_scope)
    print(f"  Result --cycle-a       : {CLR_RED}{computed_val}{CLR_RESET} (Valid: {valid})")

    expr_with_fallback = "var(--safe-fallback)"
    fallback_val, fb_valid = engine.parse_and_resolve(expr_with_fallback, cycle_scope)
    print(f"  Result --safe-fallback : {CLR_GREEN}{fallback_val}{CLR_RESET} (Fallback berhasil diaktifkan)")

    if engine.diagnostics:
        print(f"\n{CLR_YELLOW}Engine Diagnostic Logs:{CLR_RESET}")
        for log in engine.diagnostics:
            print(f"  {CLR_DIM}⚠ {log}{CLR_RESET}")

    # --- STEP 4: CSS Architecture Artifact Generation ---
    print_header("CSS Artifact Generation (Clean Layered Output)")
    
    css_output = []
    css_output.append("/* Layer: Base & Design Tokens (Auto-Generated) */")
    css_output.append(":root {")
    for k, v in flattened_root_css.items():
        css_output.append(f"  {k}: {v};")
    css_output.append("  --theme-bg: var(--color-surface-dark);")
    css_output.append("  --theme-text: #f8fafc;")
    css_output.append("  --btn-padding: var(--spacing-sm) var(--spacing-md);")
    css_output.append("}\n")

    css_output.append("/* Layer: Component Theming Architecture */")
    css_output.append(".card {")
    css_output.append("  background-color: var(--card-bg, var(--theme-bg));")
    css_output.append("  padding: var(--card-spacing, var(--spacing-lg));")
    css_output.append("}")
    css_output.append(".card.theme-inverted {")
    css_output.append("  --theme-bg: #ffffff;")
    css_output.append("  --theme-text: #000000;")
    css_output.append("}")
    css_output.append(".btn-action {")
    css_output.append("  background-color: var(--btn-bg);")
    css_output.append("  color: var(--btn-color);")
    css_output.append("  padding: var(--btn-padding);")
    css_output.append("}")

    compiled_css = "\n".join(css_output)
    print(f"{CLR_DIM}{compiled_css}{CLR_RESET}")
    print(f"\n{CLR_GREEN}✔ Lab selesai dieksekusi dengan sukses. Arsitektur Token & CSS Engine terverifikasi.{CLR_RESET}\n")

if __name__ == "__main__":
    main()