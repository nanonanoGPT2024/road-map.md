#!/usr/bin/env python3
"""
Lab Hands-on: Design Tokens Architecture & Engineering
Category: 03-Frontend-and-Mobile | Chapter: 02 (Deep Dive)

This script demonstrates an end-to-end Design Token Engine:
1. Token Graph Resolution: Resolving multi-tier aliases (Global -> Semantic -> Component).
2. Cycle Detection: Detecting circular token references via DFS graph traversal.
3. WCAG 2.1 Contrast Engine: Mathematical validation of sRGB luminance and contrast ratios.
4. Multi-Platform Exporter: Compiling resolved tokens to CSS Variables, Swift (iOS), and Jetpack Compose (Android).
"""

import sys
import re
import math
import json
from typing import Dict, Any, List, Tuple, Set, Optional
from dataclasses import dataclass, field

# ==============================================================================
# ANSI Terminal Colors
# ==============================================================================
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

# ==============================================================================
# Data Models
# ==============================================================================
@dataclass
class Token:
    path: str
    raw_value: Any
    token_type: str
    computed_value: Optional[Any] = None
    references: List[str] = field(default_factory=list)
    tier: str = "global"  # global, semantic, component

# ==============================================================================
# WCAG 2.1 Contrast Calculator
# ==============================================================================
class AccessibilityValidator:
    """Calculates relative luminance and contrast ratio according to W3C WCAG 2.1 specs."""

    @staticmethod
    def _parse_hex(hex_str: str) -> Tuple[float, float, float]:
        hex_clean = hex_str.lstrip("#")
        if len(hex_clean) == 3:
            hex_clean = "".join(c * 2 for c in hex_clean)
        if len(hex_clean) != 6:
            raise ValueError(f"Invalid hex color: {hex_str}")
        r, g, b = (int(hex_clean[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return r, g, b

    @classmethod
    def calculate_relative_luminance(cls, hex_color: str) -> float:
        """Applies gamma correction to sRGB channels and calculates luminance."""
        r, g, b = cls._parse_hex(hex_color)
        channels = [
            c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)
            for c in (r, g, b)
        ]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    @classmethod
    def calculate_contrast_ratio(cls, foreground_hex: str, background_hex: str) -> float:
        """Determines contrast ratio (L1 + 0.05) / (L2 + 0.05)."""
        l1 = cls.calculate_relative_luminance(foreground_hex)
        l2 = cls.calculate_relative_luminance(background_hex)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

# ==============================================================================
# Token Engine & Resolver
# ==============================================================================
class TokenEngine:
    ALIAS_REGEX = re.compile(r"\{([a-zA-Z0-9_\-\.]+)\}")

    def __init__(self):
        self.tokens: Dict[str, Token] = {}

    def ingest_dtcg(self, raw_tokens: Dict[str, Any], prefix: str = "", tier: str = "global"):
        """Recursively parses DTCG (Design Tokens Community Group) formatted dictionary."""
        for key, val in raw_tokens.items():
            current_path = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                if "$value" in val or "value" in val:
                    val_data = val.get("$value", val.get("value"))
                    val_type = val.get("$type", val.get("type", "string"))
                    refs = self.ALIAS_REGEX.findall(str(val_data))
                    self.tokens[current_path] = Token(
                        path=current_path,
                        raw_value=val_data,
                        token_type=val_type,
                        references=refs,
                        tier=tier
                    )
                else:
                    self.ingest_dtcg(val, current_path, tier)

    def _resolve_token_path(self, path: str, visited: Set[str]) -> Any:
        """DFS recursive resolution with circular dependency detection."""
        if path in visited:
            raise RecursionError(f"Circular dependency detected: {' -> '.join(visited)} -> {path}")

        if path not in self.tokens:
            raise KeyError(f"Referenced token '{path}' does not exist.")

        token = self.tokens[path]
        if token.computed_value is not None:
            return token.computed_value

        visited.add(path)
        val_str = str(token.raw_value)
        refs = self.ALIAS_REGEX.findall(val_str)

        if not refs:
            token.computed_value = token.raw_value
        else:
            resolved_str = val_str
            for ref in refs:
                resolved_subval = self._resolve_token_path(ref, visited.copy())
                resolved_str = resolved_str.replace(f"{{{ref}}}", str(resolved_subval))
            token.computed_value = resolved_str

        return token.computed_value

    def resolve_all(self):
        """Resolves all aliases across the DAG token tree."""
        for path in self.tokens:
            if self.tokens[path].computed_value is None:
                self._resolve_token_path(path, set())

# ==============================================================================
# Cross-Platform Exporters
# ==============================================================================
class CrossPlatformExporter:
    @staticmethod
    def to_css(tokens: Dict[str, Token]) -> str:
        """Compiles tokens to standard CSS custom properties."""
        lines = [":root {"]
        for path, token in sorted(tokens.items()):
            css_var_name = "--" + path.replace(".", "-")
            lines.append(f"  {css_var_name}: {token.computed_value};")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def to_swift(tokens: Dict[str, Token]) -> str:
        """Compiles tokens to Swift static members for iOS."""
        lines = ["import SwiftUI", "", "public struct DesignTokens {"]
        for path, token in sorted(tokens.items()):
            identifier = "".join(part.capitalize() for part in path.split("."))
            identifier = identifier[0].lower() + identifier[1:]
            
            if token.token_type == "color":
                val = str(token.computed_value).lstrip("#")
                lines.append(f"    public static let {identifier} = Color(hex: 0x{val})")
            elif token.token_type == "dimension":
                val = str(token.computed_value).replace("px", "").replace("rem", "")
                lines.append(f"    public static let {identifier}: CGFloat = {val}")
            else:
                lines.append(f"    public static let {identifier} = \"{token.computed_value}\"")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def to_compose(tokens: Dict[str, Token]) -> str:
        """Compiles tokens to Kotlin Jetpack Compose for Android."""
        lines = [
            "package com.designsystem.tokens",
            "",
            "import androidx.compose.ui.graphics.Color",
            "import androidx.compose.ui.unit.dp",
            "import androidx.compose.ui.unit.sp",
            "",
            "object DesignTokens {"
        ]
        for path, token in sorted(tokens.items()):
            val_name = "".join(part.capitalize() for part in path.split("."))
            if token.token_type == "color":
                val = str(token.computed_value).lstrip("#")
                lines.append(f"    val {val_name} = Color(0xFF{val.upper()})")
            elif token.token_type == "dimension":
                num = re.findall(r"[-+]?\d*\.\d+|\d+", str(token.computed_value))[0]
                unit = "sp" if "font" in path else "dp"
                lines.append(f"    val {val_name} = {num}.{unit}")
            else:
                lines.append(f"    val {val_name} = \"{token.computed_value}\"")
        lines.append("}")
        return "\n".join(lines)

# ==============================================================================
# Lab Execution & Demonstration
# ==============================================================================
def main():
    print(f"{TermColor.BOLD}{TermColor.CYAN}======================================================================{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}    DESIGN TOKENS ARCHITECTURE & COMPILATION ENGINE LAB                {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}======================================================================{TermColor.RESET}\n")

    # 1. Define Raw DTCG Token Structure (Global, Semantic, Component)
    raw_global_tokens = {
        "color": {
            "palette": {
                "blue": {"50": {"$value": "#eff6ff", "$type": "color"}, "600": {"$value": "#2563eb", "$type": "color"}},
                "slate": {"900": {"$value": "#0f172a", "$type": "color"}, "50": {"$value": "#f8fafc", "$type": "color"}}
            }
        },
        "spacing": {
            "scale": {
                "1": {"$value": "4px", "$type": "dimension"},
                "2": {"$value": "8px", "$type": "dimension"},
                "4": {"$value": "16px", "$type": "dimension"}
            }
        }
    }

    raw_semantic_tokens = {
        "color": {
            "text": {
                "primary": {"$value": "{color.palette.slate.900}", "$type": "color"},
                "inverse": {"$value": "{color.palette.slate.50}", "$type": "color"}
            },
            "bg": {
                "canvas": {"$value": "{color.palette.slate.50}", "$type": "color"},
                "interactive": {"$value": "{color.palette.blue.600}", "$type": "color"}
            }
        }
    }

    raw_component_tokens = {
        "button": {
            "primary": {
                "bg": {"$value": "{color.bg.interactive}", "$type": "color"},
                "text": {"$value": "{color.text.inverse}", "$type": "color"},
                "padding": {"$value": "{spacing.scale.4}", "$type": "dimension"}
            }
        }
    }

    engine = TokenEngine()
    print(f"{TermColor.YELLOW}[+] Ingesting Tier 1 (Global Tokens)...{TermColor.RESET}")
    engine.ingest_dtcg(raw_global_tokens, tier="global")

    print(f"{TermColor.YELLOW}[+] Ingesting Tier 2 (Semantic Aliases)...{TermColor.RESET}")
    engine.ingest_dtcg(raw_semantic_tokens, tier="semantic")

    print(f"{TermColor.YELLOW}[+] Ingesting Tier 3 (Component Tokens)...{TermColor.RESET}")
    engine.ingest_dtcg(raw_component_tokens, tier="component")

    # 2. Resolve Graph Dependencies
    print(f"{TermColor.YELLOW}[+] Resolving Token Dependency Graph (DAG Traversal)...{TermColor.RESET}")
    engine.resolve_all()
    print(f"{TermColor.GREEN}[✓] Successfully resolved {len(engine.tokens)} tokens across 3 tiers.{TermColor.RESET}\n")

    # Print Resolved Tokens
    print(f"{TermColor.BOLD}Resolved Token Map:{TermColor.RESET}")
    for path, token in sorted(engine.tokens.items()):
        print(f"  {TermColor.GRAY}[{token.tier.upper():<9}]{TermColor.RESET} {path:<32} "
              f"-> {TermColor.CYAN}{token.computed_value:<12}{TermColor.RESET} "
              f"{TermColor.GRAY}(Raw: {token.raw_value}){TermColor.RESET}")

    # 3. Accessibility & Contrast Ratio Checks
    print(f"\n{TermColor.BOLD}Running Accessibility (WCAG 2.1) Audits:{TermColor.RESET}")
    fg = engine.tokens["button.primary.text"].computed_value
    bg = engine.tokens["button.primary.bg"].computed_value
    ratio = AccessibilityValidator.calculate_contrast_ratio(fg, bg)
    aa_pass = ratio >= 4.5
    status = f"{TermColor.GREEN}PASS" if aa_pass else f"{TermColor.RED}FAIL"
    print(f"  Token Pair: 'button.primary.text' ({fg}) vs 'button.primary.bg' ({bg})")
    print(f"  Contrast Ratio: {TermColor.BOLD}{ratio:.2f}:1{TermColor.RESET} -> WCAG AA Normal Text (>= 4.5:1): [{status}{TermColor.RESET}]")

    # 4. Cycle Detection Simulation
    print(f"\n{TermColor.BOLD}Testing Cyclic Dependency Detection Safeguard:{TermColor.RESET}")
    cycle_engine = TokenEngine()
    cycle_engine.ingest_dtcg({
        "color": {
            "a": {"$value": "{color.b}", "$type": "color"},
            "b": {"$value": "{color.c}", "$type": "color"},
            "c": {"$value": "{color.a}", "$type": "color"}
        }
    })
    try:
        cycle_engine.resolve_all()
    except RecursionError as e:
        print(f"  {TermColor.MAGENTA}[Captured Expected Error]{TermColor.RESET} {e}")

    # 5. Multi-Platform Exporters Execution
    print(f"\n{TermColor.BOLD}Multi-Platform Artifact Generation:{TermColor.RESET}")
    css_output = CrossPlatformExporter.to_css(engine.tokens)
    swift_output = CrossPlatformExporter.to_swift(engine.tokens)
    compose_output = CrossPlatformExporter.to_compose(engine.tokens)

    print(f"\n{TermColor.CYAN}--- CSS Variables (Web) Sample ---{TermColor.RESET}")
    print("\n".join(css_output.splitlines()[:6]) + "\n  ...")

    print(f"\n{TermColor.CYAN}--- Swift (iOS SwiftUI) Sample ---{TermColor.RESET}")
    print("\n".join(swift_output.splitlines()[:6]) + "\n  ...")

    print(f"\n{TermColor.CYAN}--- Jetpack Compose (Android) Sample ---{TermColor.RESET}")
    print("\n".join(compose_output.splitlines()[:9]) + "\n  ...")

    print(f"\n{TermColor.GREEN}{TermColor.BOLD}[✓] Lab Complete: Token Engine is stable, accessible, and multi-platform ready.{TermColor.RESET}\n")

if __name__ == "__main__":
    main()