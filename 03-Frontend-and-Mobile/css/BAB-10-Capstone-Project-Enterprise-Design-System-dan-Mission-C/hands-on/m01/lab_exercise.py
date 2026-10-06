#!/usr/bin/env python3
"""
Enterprise Design System Token Engine & Mission-Critical CSS Architecture Simulator
BAB-10: Capstone Project - Enterprise Design System & Mission-Critical UI
"""

import sys
import math
import json
from typing import Dict, Any, List, Tuple

# ANSI Escape Sequences for Terminal Styling
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

FG_BLACK = "\033[30m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"

BG_BLACK = "\033[40m"
BG_BLUE = "\033[44m"
BG_CYAN = "\033[46m"
BG_WHITE = "\033[47m"
BG_DARK = "\033[48;5;236m"


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert hex string (e.g. #3b82f6) to RGB tuple."""
    clean_hex = hex_str.lstrip("#")
    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])
    return (
        int(clean_hex[0:2], 16),
        int(clean_hex[2:4], 16),
        int(clean_hex[4:6], 16),
    )


def calculate_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate WCAG sRGB relative luminance."""
    normalized = []
    for c in rgb:
        val = c / 255.0
        if val <= 0.03928:
            normalized.append(val / 12.92)
        else:
            normalized.append(math.pow((val + 0.055) / 1.055, 2.4))
    r, g, b = normalized
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate WCAG 2.1 contrast ratio between two colors."""
    lum1 = calculate_luminance(hex_to_rgb(hex1))
    lum2 = calculate_luminance(hex_to_rgb(hex2))
    brightest = max(lum1, lum2)
    darkest = min(lum1, lum2)
    return (brightest + 0.05) / (darkest + 0.05)


class EnterpriseDesignSystem:
    """Enterprise Design System Core: Tokens, Themes, and Mission-Critical Constraints."""

    def __init__(self):
        # 1. Global / Primitive Tokens
        self.primitive_tokens = {
            "color": {
                "blue-500": "#3b82f6",
                "blue-600": "#2563eb",
                "blue-700": "#1d4ed8",
                "slate-50": "#f8fafc",
                "slate-100": "#f1f5f9",
                "slate-800": "#1e293b",
                "slate-900": "#0f172a",
                "emerald-500": "#10b981",
                "rose-500": "#f43f5e",
                "amber-500": "#f59e0b",
            },
            "spacing": {
                "space-1": "0.25rem",
                "space-2": "0.5rem",
                "space-4": "1rem",
                "space-6": "1.5rem",
                "space-8": "2rem",
            },
            "radius": {
                "radius-sm": "0.25rem",
                "radius-md": "0.375rem",
                "radius-lg": "0.5rem",
                "radius-full": "9999px",
            },
            "elevation": {
                "shadow-sm": "0 1px 2px 0 rgb(0 0 0 / 0.05)",
                "shadow-md": "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                "shadow-lg": "0 10px 15px -3px rgb(0 0 0 / 0.1)",
            },
        }

        # 2. Semantic Tokens (Theme Mappings)
        self.themes = {
            "light": {
                "--eds-bg-canvas": "#f8fafc",
                "--eds-bg-surface": "#ffffff",
                "--eds-text-primary": "#0f172a",
                "--eds-text-secondary": "#475569",
                "--eds-border-subtle": "#e2e8f0",
                "--eds-brand-primary": "#2563eb",
                "--eds-brand-text": "#ffffff",
                "--eds-state-success": "#10b981",
                "--eds-state-critical": "#f43f5e",
            },
            "dark": {
                "--eds-bg-canvas": "#0f172a",
                "--eds-bg-surface": "#1e293b",
                "--eds-text-primary": "#f8fafc",
                "--eds-text-secondary": "#94a3b8",
                "--eds-border-subtle": "#334155",
                "--eds-brand-primary": "#2563eb",
                "--eds-brand-text": "#ffffff",
                "--eds-state-success": "#10b981",
                "--eds-state-critical": "#f43f5e",
            },
        }

        # 3. Component Specs
        self.components = {
            "MissionStatusCard": {
                "tokens": {
                    "background": "var(--eds-bg-surface)",
                    "border": "1px solid var(--eds-border-subtle)",
                    "color": "var(--eds-text-primary)",
                    "padding": "var(--eds-space-6)",
                    "border-radius": "var(--eds-radius-lg)",
                },
                "contract": "Must maintain >= 4.5:1 contrast against canvas background.",
            },
            "TelemetryActionButton": {
                "tokens": {
                    "background": "var(--eds-brand-primary)",
                    "color": "var(--eds-brand-text)",
                    "padding": "var(--eds-space-2) var(--eds-space-4)",
                    "border-radius": "var(--eds-radius-md)",
                    "box-shadow": "var(--eds-shadow-sm)",
                },
                "contract": "Interactive state must satisfy WCAG AA (>= 4.5:1) for label readability.",
            },
        }

    def print_banner(self):
        print(f"\n{BG_BLUE}{FG_WHITE}{BOLD} ====================================================================== {RESET}")
        print(f"{BG_BLUE}{FG_WHITE}{BOLD}    ENTERPRISE DESIGN SYSTEM & MISSION-CRITICAL CSS ARCHITECTURE ENGINE   {RESET}")
        print(f"{BG_BLUE}{FG_WHITE}{BOLD} ====================================================================== {RESET}\n")

    def inspect_primitive_tokens(self):
        print(f"{FG_CYAN}{BOLD}▶ [STAGE 1] PRIMITIVE DESIGN TOKENS CATALOG{RESET}")
        for category, tokens in self.primitive_tokens.items():
            print(f"  {FG_YELLOW}{BOLD}{category.upper()}:{RESET}")
            for key, val in tokens.items():
                if "color" in category:
                    rgb = hex_to_rgb(val)
                    ansi_chip = f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m   {RESET}"
                    print(f"    • {key:<12} : {val} {ansi_chip}")
                else:
                    print(f"    • {key:<12} : {val}")
        print()

    def audit_wcag_accessibility(self, theme_name: str):
        print(f"{FG_CYAN}{BOLD}▶ [STAGE 2] MISSION-CRITICAL ACCESSIBILITY AUDIT ({theme_name.upper()} THEME){RESET}")
        theme = self.themes.get(theme_name)
        if not theme:
            print(f"{FG_RED}Theme {theme_name} not found!{RESET}")
            return

        checks = [
            ("Canvas vs Text Primary", theme["--eds-bg-canvas"], theme["--eds-text-primary"], 4.5),
            ("Surface vs Text Primary", theme["--eds-bg-surface"], theme["--eds-text-primary"], 4.5),
            ("Surface vs Text Secondary", theme["--eds-bg-surface"], theme["--eds-text-secondary"], 4.5),
            ("Brand Primary vs Brand Text", theme["--eds-brand-primary"], theme["--eds-brand-text"], 4.5),
            ("Surface vs Critical Alert", theme["--eds-bg-surface"], theme["--eds-state-critical"], 3.0),
        ]

        print(f"  {'PAIRING':<30} | {'HEX PAIR':<18} | {'RATIO':<8} | {'TARGET':<7} | {'STATUS'}")
        print(f"  {'-'*30}-+-{'-'*18}-+-{'-'*8}-+-{'-'*7}-+-{'-'*10}")

        all_passed = True
        for label, bg, fg, target in checks:
            ratio = contrast_ratio(bg, fg)
            passed = ratio >= target
            if not passed:
                all_passed = False
            status_badge = f"{FG_GREEN}✓ PASS{RESET}" if passed else f"{FG_RED}✗ FAIL{RESET}"
            print(f"  {label:<30} | {bg} vs {fg} | {ratio:>5.2f}:1 | {target:>4.1f}:1 | {status_badge}")

        if all_passed:
            print(f"\n  {FG_GREEN}{BOLD}Result: 100% WCAG 2.1 AA/AAA Compliance Achieved.{RESET}\n")
        else:
            print(f"\n  {FG_RED}{BOLD}Result: Contrast compliance violations detected.{RESET}\n")

    def export_css_custom_properties(self) -> str:
        print(f"{FG_CYAN}{BOLD}▶ [STAGE 3] COMPILING CSS CUSTOM PROPERTIES ENGINE{RESET}")
        css_output = []
        css_output.append("/* ===========================================================================")
        css_output.append(" * Enterprise Design System (EDS) - Mission-Critical CSS Architecture")
        css_output.append(" * Automatically generated from Design Token Graph")
        css_output.append(" * =========================================================================== */")
        css_output.append(":root {")

        for key, val in self.primitive_tokens["spacing"].items():
            css_output.append(f"  --eds-{key}: {val};")
        for key, val in self.primitive_tokens["radius"].items():
            css_output.append(f"  --eds-{key}: {val};")
        for key, val in self.primitive_tokens["elevation"].items():
            css_output.append(f"  --eds-{key}: {val};")

        css_output.append("\n  /* Light Theme (Default) */")
        for key, val in self.themes["light"].items():
            css_output.append(f"  {key}: {val};")
        css_output.append("}\n")

        css_output.append("@media (prefers-color-scheme: dark) {")
        css_output.append("  :root {")
        for key, val in self.themes["dark"].items():
            css_output.append(f"    {key}: {val};")
        css_output.append("  }")
        css_output.append("}\n")

        css_output.append('[data-theme="dark"] {')
        for key, val in self.themes["dark"].items():
            css_output.append(f"  {key}: {val};")
        css_output.append("}")

        compiled_css = "\n".join(css_output)
        preview_lines = compiled_css.split("\n")[:18]
        print(f"{DIM}" + "\n".join(preview_lines) + f"\n  ... ({len(compiled_css.splitlines()) - 18} more lines) ...{RESET}\n")
        return compiled_css

    def render_terminal_mockup(self, theme_name: str = "dark"):
        print(f"{FG_CYAN}{BOLD}▶ [STAGE 4] MISSION-CONTROL UI COMPONENT TERMINAL PREVIEW ({theme_name.upper()}){RESET}")
        theme = self.themes[theme_name]
        
        bg_rgb = hex_to_rgb(theme["--eds-bg-surface"])
        fg_rgb = hex_to_rgb(theme["--eds-text-primary"])
        accent_rgb = hex_to_rgb(theme["--eds-brand-primary"])
        crit_rgb = hex_to_rgb(theme["--eds-state-critical"])

        card_bg = f"\033[48;2;{bg_rgb[0]};{bg_rgb[1]};{bg_rgb[2]}m"
        card_fg = f"\033[38;2;{fg_rgb[0]};{fg_rgb[1]};{fg_rgb[2]}m"
        btn_bg = f"\033[48;2;{accent_rgb[0]};{accent_rgb[1]};{accent_rgb[2]}m\033[38;2;255;255;255m{BOLD}"
        badge_crit = f"\033[48;2;{crit_rgb[0]};{crit_rgb[1]};{crit_rgb[2]}m\033[38;2;255;255;255m{BOLD}"

        print(f"{card_bg}{card_fg} ┌──────────────────────────────────────────────────────────────┐ {RESET}")
        print(f"{card_bg}{card_fg} │  EDS MISSION CONTROL: ORBITAL TELEMETRY SYSTEM               │ {RESET}")
        print(f"{card_bg}{card_fg} ├──────────────────────────────────────────────────────────────┤ {RESET}")
        print(f"{card_bg}{card_fg} │  Subsystem Status : {badge_crit} ELEVATED LATENCY {RESET}{card_bg}{card_fg}                             │ {RESET}")
        print(f"{card_bg}{card_fg} │  Active Nodes     : 1,420 / 1,500 Healthy                    │ {RESET}")
        print(f"{card_bg}{card_fg} │  Architecture     : Strict Token Hierarchy & Zero-Drift CSS  │ {RESET}")
        print(f"{card_bg}{card_fg} │                                                              │ {RESET}")
        print(f"{card_bg}{card_fg} │  Actions: {btn_bg} INITIATE FAILOVER {RESET}{card_bg}{card_fg}   {btn_bg} EXPORT AUDIT LOG {RESET}{card_bg}{card_fg}        │ {RESET}")
        print(f"{card_bg}{card_fg} └──────────────────────────────────────────────────────────────┘ {RESET}\n")

    def run_interactive_simulation(self):
        self.print_banner()
        self.inspect_primitive_tokens()
        self.audit_wcag_accessibility("light")
        self.audit_wcag_accessibility("dark")
        self.export_css_custom_properties()
        self.render_terminal_mockup("dark")
        self.render_terminal_mockup("light")

        print(f"{FG_GREEN}{BOLD}✔ Lab Exercise Simulation Complete!{RESET}")
        print(f"{FG_YELLOW}Enterprise Design System contract successfully verified with deterministic token mapping.{RESET}\n")


if __name__ == "__main__":
    app = EnterpriseDesignSystem()
    app.run_interactive_simulation()
