#!/usr/bin/env python3
"""
Lab Hands-on: Foundations & Architecture of Modern Design Systems
Chapter 01 - Module 02 Deep Dive: Design Token Architecture, Resolution Engine & Multi-Target Transpiler

Features:
1. DTCG-compliant Design Token Graph Parser (Hierarchical: Primitive -> Semantic -> Component).
2. DAG Topological / Recursive Alias Resolver with Cycle Detection.
3. WCAG 2.1 Contrast Ratio Verification Engine (Build-time A11y Linting).
4. Multi-Platform Code Generators (CSS Custom Properties, Android XML, Swift Theme Engine).
"""

import math
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# Terminal ANSI Color Formatting Utilities
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GRAY = "\033[90m"


@dataclass
class Token:
    path: str
    raw_value: Any
    resolved_value: Optional[Any] = None
    token_type: str = "undefined"
    description: str = ""
    is_alias: bool = False
    dependencies: Set[str] = field(default_factory=set)


class ColorA11yEngine:
    """WCAG 2.1 Relative Luminance and Contrast Ratio Calculation Engine."""

    @staticmethod
    def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
        clean_hex = hex_str.lstrip("#")
        if len(clean_hex) == 3:
            clean_hex = "".join([c * 2 for c in clean_hex])
        if len(clean_hex) != 6:
            raise ValueError(f"Invalid Hex color value: {hex_str}")
        return tuple(int(clean_hex[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

    @staticmethod
    def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
        """Converts sRGB to linear RGB and returns relative luminance (Y)."""
        transformed = []
        for channel in rgb:
            c = channel / 255.0
            if c <= 0.04045:
                transformed.append(c / 12.92)
            else:
                transformed.append(math.pow((c + 0.055) / 1.055, 2.4))
        return (
            0.2126 * transformed[0]
            + 0.7152 * transformed[1]
            + 0.0722 * transformed[2]
        )

    @classmethod
    def calculate_contrast(cls, hex_fg: str, hex_bg: str) -> float:
        """Calculates contrast ratio: (L1 + 0.05) / (L2 + 0.05)."""
        lum1 = cls.calculate_relative_luminance(cls.hex_to_rgb(hex_fg))
        lum2 = cls.calculate_relative_luminance(cls.hex_to_rgb(hex_bg))
        l_max = max(lum1, lum2)
        l_min = min(lum1, lum2)
        return (l_max + 0.05) / (l_min + 0.05)


class DesignTokenArchitectureEngine:
    """
    Core token architecture engine implementing:
    - Token ingestion following DTCG principles
    - Recursive Reference Resolution with cycle detection
    - Artifact Compilation for Web (CSS), Android (XML), and iOS (Swift)
    """

    ALIAS_REGEX = re.compile(r"^\{([a-zA-Z0-9_\-\.]+)\}$")

    def __init__(self, raw_tokens: Dict[str, Any]):
        self.raw_tree = raw_tokens
        self.tokens: Dict[str, Token] = {}
        self._flatten_and_index()

    def _flatten_and_index(self):
        """Flattens the nested dictionary into dot-notated token paths."""
        def walk(sub_tree: Dict[str, Any], prefix: str = ""):
            for key, val in sub_tree.items():
                current_path = f"{prefix}.{key}" if prefix else key
                if isinstance(val, dict) and "$value" in val:
                    raw_val = val["$value"]
                    t_type = val.get("$type", "string")
                    desc = val.get("$description", "")
                    is_ref = bool(
                        isinstance(raw_val, str)
                        and self.ALIAS_REGEX.match(raw_val)
                    )
                    deps = set()
                    if is_ref:
                        match = self.ALIAS_REGEX.match(raw_val)
                        if match:
                            deps.add(match.group(1))

                    self.tokens[current_path] = Token(
                        path=current_path,
                        raw_value=raw_val,
                        token_type=t_type,
                        description=desc,
                        is_alias=is_ref,
                        dependencies=deps,
                    )
                elif isinstance(val, dict):
                    walk(val, current_path)

        walk(self.raw_tree)

    def resolve_tokens(self):
        """Resolves alias tokens to final values using Depth-First-Search with Cycle Detection."""
        visiting = set()

        def resolve_path(path: str) -> Any:
            if path not in self.tokens:
                raise KeyError(f"Broken token reference: '{{{path}}}' does not exist.")

            tok = self.tokens[path]
            if tok.resolved_value is not None:
                return tok.resolved_value

            if path in visiting:
                raise ValueError(f"Circular dependency detected at token '{path}'")

            visiting.add(path)

            if tok.is_alias:
                match = self.ALIAS_REGEX.match(tok.raw_value)
                if match:
                    ref_path = match.group(1)
                    target_val = resolve_path(ref_path)
                    tok.resolved_value = target_val
                    # Inherit token_type if undefined
                    if tok.token_type == "undefined" and ref_path in self.tokens:
                        tok.token_type = self.tokens[ref_path].token_type
            else:
                tok.resolved_value = tok.raw_value

            visiting.remove(path)
            return tok.resolved_value

        for token_path in self.tokens:
            resolve_path(token_path)

    def run_a11y_audits(self, checks: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
        """
        Validates token color pairings against WCAG 2.1 AA/AAA compliance.
        Format: (fg_token_path, bg_token_path, level_required)
        """
        results = []
        for fg_path, bg_path, required_level in checks:
            fg_tok = self.tokens.get(fg_path)
            bg_tok = self.tokens.get(bg_path)

            if not fg_tok or not bg_tok:
                results.append({
                    "fg": fg_path,
                    "bg": bg_path,
                    "status": "MISSING_TOKEN",
                    "ratio": 0.0,
                    "passed": False,
                })
                continue

            ratio = ColorA11yEngine.calculate_contrast(
                str(fg_tok.resolved_value), str(bg_tok.resolved_value)
            )
            threshold = 4.5 if required_level == "AA" else 7.0
            results.append({
                "fg": fg_path,
                "fg_val": fg_tok.resolved_value,
                "bg": bg_path,
                "bg_val": bg_tok.resolved_value,
                "level": required_level,
                "ratio": ratio,
                "passed": ratio >= threshold,
            })
        return results

    # ================= Multi-Target Transpilers =================

    def transpile_css(self) -> str:
        """Compiles tokens into CSS Custom Properties."""
        lines = [":root {"]
        for path, token in sorted(self.tokens.items()):
            css_var_name = "--" + path.replace(".", "-")
            val = token.resolved_value
            if token.token_type == "dimension" and isinstance(val, (int, float)):
                val = f"{val}px"
            lines.append(f"  {css_var_name}: {val}; /* {token.description or path} */")
        lines.append("}")
        return "\n".join(lines)

    def transpile_android_xml(self) -> str:
        """Compiles tokens into Android resource values (colors & dimensions)."""
        lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
        for path, token in sorted(self.tokens.items()):
            xml_name = path.replace(".", "_")
            if token.token_type == "color":
                clean_hex = str(token.resolved_value).replace("#", "")
                if len(clean_hex) == 6:
                    clean_hex = "FF" + clean_hex.upper()
                lines.append(f'    <color name="{xml_name}">#{clean_hex}</color>')
            elif token.token_type == "dimension":
                lines.append(f'    <dimen name="{xml_name}">{token.resolved_value}dp</dimen>')
        lines.append("</resources>")
        return "\n".join(lines)

    def transpile_swift(self) -> str:
        """Compiles tokens into Swift static theme structures."""
        lines = [
            "// Auto-generated Design System Tokens for iOS",
            "import SwiftUI",
            "",
            "public enum DesignTokens {",
        ]

        def sanitize_identifier(s: str) -> str:
            parts = [p.capitalize() for p in s.replace("-", ".").split(".")]
            return parts[0].lower() + "".join(parts[1:])

        for path, token in sorted(self.tokens.items()):
            var_name = sanitize_identifier(path)
            if token.token_type == "color":
                clean_hex = str(token.resolved_value).lstrip("#")
                lines.append(
                    f'    public static let {var_name} = Color(hex: 0x{clean_hex}) // {token.description}'
                )
            elif token.token_type == "dimension":
                lines.append(
                    f"    public static let {var_name}: CGFloat = {token.resolved_value}.0"
                )
        lines.append("}")
        return "\n".join(lines)


def run_pipeline():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}   FOUNDATIONS & ARCHITECTURE: DESIGN TOKEN COMPILATION PIPELINE      {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    # Tiered Token Tree (Primitive -> Semantic -> Component-Specific)
    raw_design_system_tokens = {
        "global": {
            "color": {
                "blue": {
                    "100": {"$value": "#dbeafe", "$type": "color", "$description": "Light sky blue"},
                    "600": {"$value": "#2563eb", "$type": "color", "$description": "Core primary blue"},
                    "900": {"$value": "#1e3a8a", "$type": "color", "$description": "Deep midnight blue"},
                },
                "neutral": {
                    "white": {"$value": "#ffffff", "$type": "color", "$description": "Pure white base"},
                    "gray": {
                        "100": {"$value": "#f3f4f6", "$type": "color", "$description": "Canvas tint"},
                        "900": {"$value": "#111827", "$type": "color", "$description": "High-contrast text"},
                    },
                },
            },
            "spacing": {
                "sm": {"$value": 8, "$type": "dimension", "$description": "Small spacing unit"},
                "md": {"$value": 16, "$type": "dimension", "$description": "Medium base spacing"},
                "lg": {"$value": 24, "$type": "dimension", "$description": "Large section padding"},
            },
        },
        "semantic": {
            "color": {
                "brand": {
                    "primary": {"$value": "{global.color.blue.600}", "$type": "color", "$description": "Primary brand accent"},
                    "dark": {"$value": "{global.color.blue.900}", "$type": "color", "$description": "Brand dark surface"},
                },
                "surface": {
                    "canvas": {"$value": "{global.color.neutral.gray.100}", "$type": "color"},
                    "card": {"$value": "{global.color.neutral.white}", "$type": "color"},
                },
                "text": {
                    "body": {"$value": "{global.color.neutral.gray.900}", "$type": "color"},
                    "inverse": {"$value": "{global.color.neutral.white}", "$type": "color"},
                },
            },
            "layout": {
                "gutter": {"$value": "{global.spacing.md}", "$type": "dimension"},
            },
        },
        "component": {
            "button": {
                "primary": {
                    "background": {"$value": "{semantic.color.brand.primary}", "$type": "color"},
                    "text": {"$value": "{semantic.color.text.inverse}", "$type": "color"},
                    "padding": {"$value": "{semantic.layout.gutter}", "$type": "dimension"},
                },
                "subtle": {
                    "background": {"$value": "{global.color.blue.100}", "$type": "color"},
                    "text": {"$value": "{semantic.color.brand.dark}", "$type": "color"},
                },
                "badContrastButton": {
                    "background": {"$value": "{global.color.blue.100}", "$type": "color"},
                    "text": {"$value": "{global.color.neutral.white}", "$type": "color"},
                },
            }
        },
    }

    # Step 1: Ingestion & Dependency Indexing
    print(f"{BOLD}[1/4] INGESTION & DEPENDENCY GRAPH INDEXING...{RESET}")
    engine = DesignTokenArchitectureEngine(raw_design_system_tokens)
    print(f"      Total indexed nodes: {BOLD}{len(engine.tokens)}{RESET}")
    alias_count = sum(1 for t in engine.tokens.values() if t.is_alias)
    print(f"      Primitive tokens:    {len(engine.tokens) - alias_count}")
    print(f"      Semantic aliases:    {alias_count}")

    # Step 2: DAG Resolution
    print(f"\n{BOLD}[2/4] RESOLVING TOKEN ALIAS GRAPH...{RESET}")
    try:
        engine.resolve_tokens()
        print(f"      {GREEN}✔ All references resolved successfully without cycles.{RESET}")
    except Exception as e:
        print(f"      {RED}✖ Resolution failed: {e}{RESET}")
        sys.exit(1)

    # Step 3: Accessibility Engine (WCAG 2.1 Contrast Testing)
    print(f"\n{BOLD}[3/4] BUILD-TIME WCAG 2.1 CONTRAST VALIDATION...{RESET}")
    a11y_rules = [
        ("component.button.primary.text", "component.button.primary.background", "AA"),
        ("component.button.subtle.text", "component.button.subtle.background", "AA"),
        ("component.button.badContrastButton.text", "component.button.badContrastButton.background", "AA"),
    ]
    results = engine.run_a11y_audits(a11y_rules)

    for res in results:
        status_symbol = f"{GREEN}PASS [AA]{RESET}" if res["passed"] else f"{RED}FAIL [AA]{RESET}"
        print(
            f"      [{status_symbol}] Contrast Ratio: {BOLD}{res['ratio']:.2f}:1{RESET} | "
            f"FG: {res['fg_val']} ({res['fg']}) on BG: {res['bg_val']} ({res['bg']})"
        )

    # Step 4: Multi-target Transpiler Export
    print(f"\n{BOLD}[4/4] TRANSPILING MULTI-PLATFORM ARTIFACTS...{RESET}")

    # 4a. CSS Custom Properties
    print(f"\n{MAGENTA}--- Generated: Web (CSS Custom Properties) ---{RESET}")
    css_output = engine.transpile_css()
    css_preview = "\n".join(css_output.splitlines()[:6]) + "\n  ..."
    print(f"{GRAY}{css_preview}{RESET}")

    # 4b. Android XML
    print(f"\n{YELLOW}--- Generated: Android (XML Resources) ---{RESET}")
    android_output = engine.transpile_android_xml()
    android_preview = "\n".join(android_output.splitlines()[:6]) + "\n    ..."
    print(f"{GRAY}{android_preview}{RESET}")

    # 4c. Swift (iOS)
    print(f"\n{CYAN}--- Generated: iOS (Swift Theme System) ---{RESET}")
    swift_output = engine.transpile_swift()
    swift_preview = "\n".join(swift_output.splitlines()[:8]) + "\n    ..."
    print(f"{GRAY}{swift_preview}{RESET}")

    print(f"\n{BOLD}{GREEN}✔ Pipeline execution completed successfully.{RESET}\n")


if __name__ == "__main__":
    run_pipeline()