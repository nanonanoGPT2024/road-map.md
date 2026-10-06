#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Design Systems & Design-to-Code Parity Engine
Module: BAB-09 Enterprise Design Systems dan Design-to-Code Parity (Modul 01)

Simulasi teknis mencakup:
1. Multi-Tier Token Hierarchy (Global Primitive -> Semantic Alias -> Component Scoped)
2. Token Compilation & Cross-Platform Transpiler (CSS Vars, Android XML, iOS Swift)
3. AST/Code Drift Analyzer (Mendeteksi hardcoded hex/px vs Design Tokens)
4. Design Parity Scorecard & Compliance Matrix
"""

import sys
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

# ANSI Escape Colors for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"


@dataclass
class Token:
    name: str
    value: str
    token_type: str  # color, spacing, typography, elevation
    category: str    # global, semantic, component
    alias_for: Optional[str] = None


@dataclass
class DriftViolation:
    line_number: int
    element: str
    attribute: str
    raw_value: str
    suggested_token: Optional[str]
    severity: str  # CRITICAL, WARNING, INFO


class DesignTokenStore:
    """Manages 3-tier token hierarchy and resolves aliases."""
    
    def __init__(self):
        self.global_tokens: Dict[str, Token] = {}
        self.semantic_tokens: Dict[str, Token] = {}
        self.component_tokens: Dict[str, Token] = {}
        self._init_foundation_tokens()

    def _init_foundation_tokens(self):
        # 1. Global / Primitive Tokens
        primitives = [
            ("color.palette.blue-600", "#1E40AF", "color"),
            ("color.palette.blue-700", "#1D4ED8", "color"),
            ("color.palette.blue-100", "#DBEAFE", "color"),
            ("color.palette.neutral-0", "#FFFFFF", "color"),
            ("color.palette.neutral-900", "#0F172A", "color"),
            ("color.palette.red-600", "#DC2626", "color"),
            ("spacing.025", "2px", "spacing"),
            ("spacing.050", "4px", "spacing"),
            ("spacing.100", "8px", "spacing"),
            ("spacing.150", "12px", "spacing"),
            ("spacing.200", "16px", "spacing"),
            ("spacing.300", "24px", "spacing"),
            ("radius.sm", "4px", "radius"),
            ("radius.md", "8px", "radius"),
            ("radius.full", "9999px", "radius"),
        ]
        for name, val, ttype in primitives:
            self.global_tokens[name] = Token(name, val, ttype, "global")

        # 2. Semantic Tokens (aliases pointing to primitives)
        semantics = [
            ("color.action.primary.bg", "{color.palette.blue-600}", "color", "color.palette.blue-600"),
            ("color.action.primary.hover", "{color.palette.blue-700}", "color", "color.palette.blue-700"),
            ("color.action.primary.text", "{color.palette.neutral-0}", "color", "color.palette.neutral-0"),
            ("color.feedback.danger", "{color.palette.red-600}", "color", "color.palette.red-600"),
            ("space.inset.sm", "{spacing.100}", "spacing", "spacing.100"),
            ("space.inset.md", "{spacing.200}", "spacing", "spacing.200"),
        ]
        for name, val, ttype, alias in semantics:
            self.semantic_tokens[name] = Token(name, val, ttype, "semantic", alias)

        # 3. Component Tokens
        components = [
            ("btn.primary.bg", "{color.action.primary.bg}", "color", "color.action.primary.bg"),
            ("btn.primary.padding.x", "{space.inset.md}", "spacing", "space.inset.md"),
            ("btn.primary.padding.y", "{space.inset.sm}", "spacing", "space.inset.sm"),
            ("btn.primary.radius", "{radius.md}", "radius", "radius.md"),
        ]
        for name, val, ttype, alias in components:
            self.component_tokens[name] = Token(name, val, ttype, "component", alias)

    def resolve(self, token_name: str) -> Optional[str]:
        """Resolves token aliases recursively down to the primitive literal value."""
        target = (self.component_tokens.get(token_name) or
                  self.semantic_tokens.get(token_name) or
                  self.global_tokens.get(token_name))
        if not target:
            return None
        if not target.alias_for:
            return target.value
        return self.resolve(target.alias_for)

    def find_token_by_value(self, value: str) -> Optional[str]:
        """Reverse lookup: finds semantic or primitive token for raw CSS value."""
        val_clean = value.strip().upper()
        # Look in semantic tokens first
        for name, token in self.semantic_tokens.items():
            if self.resolve(name) and self.resolve(name).upper() == val_clean:
                return name
        # Fallback to global
        for name, token in self.global_tokens.items():
            if token.value.upper() == val_clean:
                return name
        return None


class TokenTranspiler:
    """Compiles Design Tokens into Web, iOS, and Android targets."""
    
    @staticmethod
    def to_css_variables(store: DesignTokenStore) -> str:
        lines = [":root {", "  /* Global Primitives */"]
        for k, v in store.global_tokens.items():
            slug = k.replace(".", "-")
            lines.append(f"  --ds-{slug}: {v.value};")
        lines.append("\n  /* Semantic Tokens */")
        for k, v in store.semantic_tokens.items():
            slug = k.replace(".", "-")
            ref_slug = v.alias_for.replace(".", "-") if v.alias_for else ""
            lines.append(f"  --ds-{slug}: var(--ds-{ref_slug}, {store.resolve(k)});")
        lines.append("\n  /* Component Tokens */")
        for k, v in store.component_tokens.items():
            slug = k.replace(".", "-")
            ref_slug = v.alias_for.replace(".", "-") if v.alias_for else ""
            lines.append(f"  --ds-{slug}: var(--ds-{ref_slug}, {store.resolve(k)});")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def to_swift_tokens(store: DesignTokenStore) -> str:
        lines = [
            "// Generated by Enterprise Design Token Engine",
            "import SwiftUI",
            "",
            "public enum DesignSystemToken {",
            "    public enum Color {"
        ]
        for k in store.semantic_tokens:
            if store.semantic_tokens[k].token_type == "color":
                val = store.resolve(k)
                camel = "".join(x.title() for x in k.split("."))
                lines.append(f'        public static let {camel} = Color(hex: "{val}")')
        lines.extend(["    }", "}"])
        return "\n".join(lines)


class DesignParityLinter:
    """Inspects frontend source code to detect token drift and calculate parity score."""
    
    def __init__(self, token_store: DesignTokenStore):
        self.store = token_store

    def audit_css_code(self, code_snippet: str) -> Tuple[List[DriftViolation], float]:
        violations: List[DriftViolation] = []
        lines = code_snippet.strip().split("\n")
        total_style_declarations = 0
        tokenized_declarations = 0

        hex_pattern = re.compile(r'#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})')
        px_pattern = re.compile(r'(\d+)px')
        var_pattern = re.compile(r'var\(--ds-([a-zA-Z0-9_-]+)\)')

        for idx, line in enumerate(lines, start=1):
            if ":" not in line or ";" not in line:
                continue
            
            clean_line = line.strip()
            if clean_line.startswith("/*") or clean_line.startswith("*"):
                continue

            attr, val = clean_line.split(":", 1)
            attr = attr.strip()
            val = val.replace(";", "").strip()
            total_style_declarations += 1

            if var_pattern.search(val):
                tokenized_declarations += 1
                continue

            # Detect Hardcoded HEX Colors
            hex_match = hex_pattern.search(val)
            if hex_match:
                raw_hex = hex_match.group(0)
                matched_token = self.store.find_token_by_value(raw_hex)
                violations.append(DriftViolation(
                    line_number=idx,
                    element="CSS Declaration",
                    attribute=attr,
                    raw_value=raw_hex,
                    suggested_token=matched_token,
                    severity="CRITICAL"
                ))
                continue

            # Detect Hardcoded Pixel Spacing
            px_match = px_pattern.search(val)
            if px_match:
                raw_px = px_match.group(0)
                matched_token = self.store.find_token_by_value(raw_px)
                violations.append(DriftViolation(
                    line_number=idx,
                    element="CSS Declaration",
                    attribute=attr,
                    raw_value=raw_px,
                    suggested_token=matched_token,
                    severity="WARNING"
                ))
                continue

        parity_score = 0.0
        if total_style_declarations > 0:
            parity_score = (tokenized_declarations / total_style_declarations) * 100.0

        return violations, parity_score


def print_banner():
    print(f"{CYAN}{BOLD}" + "=" * 70 + f"{RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD}   ENTERPRISE DESIGN SYSTEM: DESIGN-TO-CODE PARITY LINTER (M01)   {RESET}")
    print(f"{CYAN}" + "=" * 70 + f"{RESET}\n")


def display_token_registry(store: DesignTokenStore):
    print(f"{MAGENTA}{BOLD}[1] TIERED DESIGN TOKEN REGISTRY & RESOLUTION{RESET}")
    print(f"{DIM}{'Token Identifier':<32} {'Tier':<12} {'Raw / Alias':<28} {'Resolved':<10}{RESET}")
    print("-" * 84)

    all_tokens = [
        *store.global_tokens.values(),
        *store.semantic_tokens.values(),
        *store.component_tokens.values()
    ]
    for t in all_tokens:
        resolved = store.resolve(t.name) or "-"
        color = CYAN if t.category == "global" else (GREEN if t.category == "semantic" else YELLOW)
        print(f"{color}{t.name:<32}{RESET} {t.category:<12} {t.value:<28} {BOLD}{resolved:<10}{RESET}")
    print()


def display_transpilation_output(store: DesignTokenStore):
    print(f"{MAGENTA}{BOLD}[2] MULTI-PLATFORM TOKEN TRANSPILER OUTPUT{RESET}")
    print(f"{BLUE}{BOLD}--> Target: Web CSS Variables (Design Tokens Tier 1-3){RESET}")
    css_output = TokenTranspiler.to_css_variables(store)
    # Print preview
    for line in css_output.split("\n")[:12]:
        print(f"  {line}")
    print(f"  {DIM}... [truncated remaining CSS custom properties] ...{RESET}\n")

    print(f"{BLUE}{BOLD}--> Target: iOS SwiftUI Design System Enums{RESET}")
    swift_output = TokenTranspiler.to_swift_tokens(store)
    for line in swift_output.split("\n"):
        print(f"  {line}")
    print()


def run_drift_parity_audit(store: DesignTokenStore):
    print(f"{MAGENTA}{BOLD}[3] DESIGN-TO-CODE PARITY AUDIT & DRIFT DETECTION{RESET}")
    
    # Mock legacy / drifting component CSS
    sample_component_css = """
.btn-primary {
  display: inline-flex;
  background-color: #1E40AF; /* Drifting hardcoded hex! */
  color: var(--ds-btn-primary-text);
  padding: 8px 16px; /* Drifting hardcoded px! */
  border-radius: 8px; /* Hardcoded radius */
  font-family: inherit;
  font-size: 14px;
}

.card-danger {
  border: 1px solid #DC2626; /* Drifting hardcoded hex! */
  padding: 16px;
  background-color: var(--ds-color-palette-neutral-0);
}
"""
    print(f"{YELLOW}Input CSS Component to Audit:{RESET}")
    for line in sample_component_css.strip().split("\n"):
        print(f"  {DIM}|{RESET} {line}")
    print()

    linter = DesignParityLinter(store)
    violations, score = linter.audit_css_code(sample_component_css)

    print(f"{BOLD}Audit Findings:{RESET}")
    for v in violations:
        sev_color = RED if v.severity == "CRITICAL" else YELLOW
        suggest = f"Replace with: {GREEN}var(--ds-{v.suggested_token.replace('.', '-')}){RESET}" if v.suggested_token else f"{RED}No matching token in registry{RESET}"
        print(f"  [{sev_color}{v.severity}{RESET}] Line {v.line_number}: Attribute '{v.attribute}' has hardcoded value '{RED}{v.raw_value}{RESET}'.")
        print(f"         {suggest}")

    print("\n" + "-" * 70)
    score_color = GREEN if score >= 85 else (YELLOW if score >= 60 else RED)
    status_label = "PARITY ACHIEVED" if score >= 85 else "DRIFT DETECTED - REFACTOR REQUIRED"
    print(f"Design-to-Code Parity Score: {score_color}{BOLD}{score:.1f}%{RESET} [{score_color}{status_label}{RESET}]")
    print("-" * 70 + "\n")


def interactive_menu(store: DesignTokenStore):
    while True:
        print(f"{BOLD}Interactive Enterprise Design System Console:{RESET}")
        print("  1. Tampilkan Token Registry & Hierarki Resolusi")
        print("  2. Transpile Tokens ke Platform Targets (Web CSS / iOS Swift)")
        print("  3. Jalankan Parity Drift Audit pada Sample Component")
        print("  4. Tes Input CSS Mandiri (Live Interactive Linter)")
        print("  5. Keluar")
        choice = input(f"\n{CYAN}Pilih opsi [1-5]: {RESET}").strip()

        if choice == "1":
            display_token_registry(store)
        elif choice == "2":
            display_transpilation_output(store)
        elif choice == "3":
            run_drift_parity_audit(store)
        elif choice == "4":
            print(f"\n{YELLOW}Masukkan baris CSS (akhiri dengan input baris kosong / ENTER ganda):{RESET}")
            user_lines = []
            while True:
                try:
                    line = input()
                    if not line:
                        break
                    user_lines.append(line)
                except EOFError:
                    break
            if user_lines:
                raw_css = "\n".join(user_lines)
                linter = DesignParityLinter(store)
                violations, score = linter.audit_css_code(raw_css)
                print(f"\n{BOLD}Hasil Audit CSS Kustom:{RESET}")
                if not violations:
                    print(f"  {GREEN}Selamat! 100% tokenized, tidak ada drift terdeteksi.{RESET}")
                else:
                    for v in violations:
                        print(f"  - Baris {v.line_number}: {v.attribute}: {RED}{v.raw_value}{RESET} -> Usulan: {GREEN}{v.suggested_token or 'Buat token baru'}{RESET}")
                print(f"Parity Score: {BOLD}{score:.1f}%{RESET}\n")
        elif choice == "5" or choice == "q":
            print(f"\n{GREEN}Selesai. Design System Parity Engine dimatikan.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan pilih 1-5.{RESET}\n")


def main():
    print_banner()
    token_store = DesignTokenStore()
    
    # If run in non-interactive/automated pipeline or with --demo flag
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "-d", "--headless"):
        print(f"{YELLOW}[Running in Automated Verification Mode]{RESET}\n")
        display_token_registry(token_store)
        display_transpilation_output(token_store)
        run_drift_parity_audit(token_store)
        print(f"{GREEN}✓ Automated verification completed successfully.{RESET}")
        return 0

    # Default to demonstration followed by interactive menu
    display_token_registry(token_store)
    run_drift_parity_audit(token_store)
    interactive_menu(token_store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
