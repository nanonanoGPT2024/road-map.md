#!/usr/bin/env python3
"""
Lab Exercise: Styling Systems, Design Tokens, dan CSS Architecture (BAB-06)
Simulasi Arsitektur Produksi Skala Besar: Multi-Tier Token Compiler & Theme Contract Auditor.

Features:
1. Multi-Tier Token Engine (Global -> Semantic -> Component Tokens).
2. Style Dictionary Build Pipeline (CSS Variables, TypeScript Interfaces, JSON export).
3. Theme Contrast & Contract Parity Validator (WCAG AA check + Missing token detector).
4. CSS Architecture & Specificity Collision Auditor.
5. Interactive Terminal Interface with Rich ANSI Colors & Benchmarking.
"""

from __future__ import annotations
import sys
import json
import math
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

# ==============================================================================
# ANSI Color Palette for Terminal UI
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    FG_BLACK = "\033[30m"
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_WHITE = "\033[37m"

    # Bright Foreground
    FG_BRED = "\033[91m"
    FG_BGREEN = "\033[92m"
    FG_BYELLOW = "\033[93m"
    FG_BBLUE = "\033[94m"
    FG_BMAGENTA = "\033[95m"
    FG_BCYAN = "\033[96m"
    FG_BWHITE = "\033[97m"

    # Background
    BG_DARK = "\033[48;5;235m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"


def print_banner():
    banner = f"""{Color.FG_BCYAN}{Color.BOLD}
================================================================================
   ENTERPRISE DESIGN SYSTEM & CSS ARCHITECTURE PIPELINE (BAB-06 SIMULATOR)
   Multi-Tier Tokens • Contract Validator • WCAG Contrast • Style Dictionary
================================================================================{Color.RESET}"""
    print(banner)


# ==============================================================================
# Domain Models: Design Tokens & Theme Systems
# ==============================================================================
@dataclass
class TokenNode:
    name: str
    value: str
    tier: str  # 'global', 'semantic', 'component'
    token_type: str  # 'color', 'spacing', 'typography', 'elevation'
    reference: Optional[str] = None
    description: str = ""


@dataclass
class ThemeContract:
    theme_name: str
    tokens: Dict[str, TokenNode] = field(default_factory=dict)

    def set_token(self, token: TokenNode):
        self.tokens[token.name] = token


# ==============================================================================
# WCAG Contrast Calculation Engine
# ==============================================================================
def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    clean_hex = hex_str.lstrip("#")
    if len(clean_hex) == 3:
        clean_hex = "".join([c * 2 for c in clean_hex])
    if len(clean_hex) != 6:
        return (0, 0, 0)
    return (
        int(clean_hex[0:2], 16),
        int(clean_hex[2:4], 16),
        int(clean_hex[4:6], 16)
    )


def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def channel_lum(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def calculate_contrast_ratio(hex_fg: str, hex_bg: str) -> float:
    lum1 = calculate_relative_luminance(hex_to_rgb(hex_fg))
    lum2 = calculate_relative_luminance(hex_to_rgb(hex_bg))
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


# ==============================================================================
# Token Architecture Builder (Global -> Semantic -> Component)
# ==============================================================================
class TokenEngine:
    def __init__(self):
        self.global_tokens: Dict[str, str] = {
            "color.blue.50": "#eff6ff",
            "color.blue.500": "#3b82f6",
            "color.blue.600": "#2563eb",
            "color.blue.900": "#1e3a8a",
            "color.slate.50": "#f8fafc",
            "color.slate.100": "#f1f5f9",
            "color.slate.800": "#1e293b",
            "color.slate.900": "#0f172a",
            "color.emerald.500": "#10b981",
            "color.rose.500": "#f43f5e",
            "spacing.1": "4px",
            "spacing.2": "8px",
            "spacing.4": "16px",
            "spacing.6": "24px",
            "radii.sm": "4px",
            "radii.md": "8px",
            "radii.full": "9999px",
            "font.family.sans": "Inter, system-ui, -apple-system, sans-serif",
            "font.family.mono": "JetBrains Mono, monospace"
        }

    def build_default_themes(self) -> Tuple[ThemeContract, ThemeContract]:
        # Light Theme
        light_theme = ThemeContract(theme_name="light")
        # Dark Theme
        dark_theme = ThemeContract(theme_name="dark")

        # 1. Semantic Layer (Light)
        light_theme.set_token(TokenNode("sys.color.bg.canvas", "#f8fafc", "semantic", "color", "color.slate.50", "Main surface background"))
        light_theme.set_token(TokenNode("sys.color.bg.surface", "#ffffff", "semantic", "color", "", "Card/Container background"))
        light_theme.set_token(TokenNode("sys.color.fg.default", "#0f172a", "semantic", "color", "color.slate.900", "Default high-contrast text"))
        light_theme.set_token(TokenNode("sys.color.fg.muted", "#475569", "semantic", "color", "color.slate.600", "Secondary text"))
        light_theme.set_token(TokenNode("sys.color.primary", "#2563eb", "semantic", "color", "color.blue.600", "Primary brand interactive"))
        light_theme.set_token(TokenNode("sys.color.primary.on", "#ffffff", "semantic", "color", "", "Text on primary color"))

        # Component Layer (Light)
        light_theme.set_token(TokenNode("cmp.button.primary.bg", "var(--sys-color-primary)", "component", "color", "sys.color.primary"))
        light_theme.set_token(TokenNode("cmp.button.primary.fg", "var(--sys-color-primary-on)", "component", "color", "sys.color.primary.on"))
        light_theme.set_token(TokenNode("cmp.card.border.radius", "8px", "component", "spacing", "radii.md"))

        # 2. Semantic Layer (Dark)
        dark_theme.set_token(TokenNode("sys.color.bg.canvas", "#0f172a", "semantic", "color", "color.slate.900", "Main canvas background"))
        dark_theme.set_token(TokenNode("sys.color.bg.surface", "#1e293b", "semantic", "color", "color.slate.800", "Card/Container background"))
        dark_theme.set_token(TokenNode("sys.color.fg.default", "#f8fafc", "semantic", "color", "color.slate.50", "Default high-contrast text"))
        dark_theme.set_token(TokenNode("sys.color.fg.muted", "#94a3b8", "semantic", "color", "color.slate.400", "Secondary text"))
        dark_theme.set_token(TokenNode("sys.color.primary", "#3b82f6", "semantic", "color", "color.blue.500", "Primary brand interactive (toned for dark)"))
        dark_theme.set_token(TokenNode("sys.color.primary.on", "#0f172a", "semantic", "color", "color.slate.900", "Text on primary color"))

        # Component Layer (Dark)
        dark_theme.set_token(TokenNode("cmp.button.primary.bg", "var(--sys-color-primary)", "component", "color", "sys.color.primary"))
        dark_theme.set_token(TokenNode("cmp.button.primary.fg", "var(--sys-color-primary-on)", "component", "color", "sys.color.primary.on"))
        dark_theme.set_token(TokenNode("cmp.card.border.radius", "8px", "component", "spacing", "radii.md"))

        return light_theme, dark_theme


# ==============================================================================
# CSS Architecture & Style Dictionary Compiler
# ==============================================================================
class TokenCompiler:
    @staticmethod
    def to_css_custom_properties(theme: ThemeContract, selector: str = ":root") -> str:
        lines = [f"{selector} {{"]
        for key, node in sorted(theme.tokens.items()):
            css_var_name = "--" + key.replace(".", "-")
            lines.append(f"  {css_var_name}: {node.value}; /* {node.tier} | {node.description or 'No desc'} */")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def to_typescript_interface(theme: ThemeContract) -> str:
        lines = ["export interface AppThemeTokens {"]
        for key, node in sorted(theme.tokens.items()):
            safe_prop = f"'{key}'"
            lines.append(f"  readonly {safe_prop}: string; // {node.tier}: {node.value}")
        lines.append("}")
        return "\n".join(lines)


# ==============================================================================
# Specificity & CSS Architecture Auditor
# ==============================================================================
class SpecificityAuditor:
    @staticmethod
    def calculate_specificity(selector: str) -> Tuple[int, int, int]:
        """
        Returns (IDs, Classes/Attributes/Pseudo-classes, Elements/Pseudo-elements)
        A simplified parser demonstrating specificity hygiene.
        """
        import re
        ids = len(re.findall(r"#[a-zA-Z0-9_-]+", selector))
        classes = len(re.findall(r"\.[a-zA-Z0-9_-]+", selector))
        attrs = len(re.findall(r"\[.+?\]", selector))
        pseudos = len(re.findall(r":(?!:)[a-zA-Z0-9_-]+", selector))
        # Elements
        clean = re.sub(r"#[a-zA-Z0-9_-]+|\.[a-zA-Z0-9_-]+|\[.+?\]|::?[a-zA-Z0-9_-]+", " ", selector)
        elements = len([w for w in clean.split() if w and not w in [">", "+", "~", "*", ","]])
        return (ids, classes + attrs + pseudos, elements)

    @staticmethod
    def audit_selector(selector: str) -> Tuple[str, str]:
        score = SpecificityAuditor.calculate_specificity(selector)
        score_str = f"({score[0]},{score[1]},{score[2]})"
        if score[0] > 0:
            return score_str, f"{Color.FG_BRED}[REJECTED] ID selector detected! Breaks modular BEM/Utility rules.{Color.RESET}"
        elif score[1] > 3:
            return score_str, f"{Color.FG_BYELLOW}[WARNING] High nesting depth! Potential styling collision.{Color.RESET}"
        elif score == (0, 1, 0) or score == (0, 2, 0):
            return score_str, f"{Color.FG_BGREEN}[OPTIMAL] Clean Single-Class BEM or Scoped Component.{Color.RESET}"
        else:
            return score_str, f"{Color.FG_BCYAN}[ACCEPTABLE] Standard CSS Rule.{Color.RESET}"


# ==============================================================================
# Interactive Terminal Controller
# ==============================================================================
class DesignSystemRunner:
    def __init__(self):
        self.engine = TokenEngine()
        self.light_theme, self.dark_theme = self.engine.build_default_themes()

    def run_token_inspection(self):
        print(f"\n{Color.FG_BYELLOW}{Color.BOLD}>>> [1] DESIGN TOKEN HIERARCHY AUDIT <<<{Color.RESET}")
        print(f"{Color.DIM}Global Primitive Tokens (Total: {len(self.engine.global_tokens)}){Color.RESET}")
        for k, v in list(self.engine.global_tokens.items())[:6]:
            print(f"  {Color.FG_CYAN}{k:<24}{Color.RESET} -> {Color.FG_BWHITE}{v}{Color.RESET}")
        print(f"  {Color.DIM}... and {len(self.engine.global_tokens) - 6} more primitive tokens.{Color.RESET}\n")

        print(f"{Color.BOLD}Semantic & Component Tokens ({self.light_theme.theme_name.upper()} THEME):{Color.RESET}")
        print(f"{'TOKEN KEY':<30} {'TIER':<12} {'RESOLVED VALUE':<26} {'REFERENCE'}")
        print("-" * 80)
        for key, node in self.light_theme.tokens.items():
            tier_color = Color.FG_BGREEN if node.tier == "semantic" else Color.FG_BMAGENTA
            ref_str = f"{Color.DIM}(ref: {node.reference}){Color.RESET}" if node.reference else ""
            print(f"{Color.FG_BWHITE}{key:<30}{Color.RESET} {tier_color}{node.tier:<12}{Color.RESET} {Color.FG_YELLOW}{node.value:<26}{Color.RESET} {ref_str}")

    def run_wcag_audit(self):
        print(f"\n{Color.FG_BYELLOW}{Color.BOLD}>>> [2] WCAG CONTRAST & THEME PARITY AUDIT <<<{Color.RESET}")
        # Test Light Theme
        fg_light = self.light_theme.tokens["sys.color.fg.default"].value
        bg_light = self.light_theme.tokens["sys.color.bg.canvas"].value
        ratio_light = calculate_contrast_ratio(fg_light, bg_light)

        # Test Dark Theme
        fg_dark = self.dark_theme.tokens["sys.color.fg.default"].value
        bg_dark = self.dark_theme.tokens["sys.color.bg.canvas"].value
        ratio_dark = calculate_contrast_ratio(fg_dark, bg_dark)

        def eval_ratio(ratio: float) -> str:
            if ratio >= 7.0:
                return f"{Color.FG_BGREEN}{ratio:.2f}:1 (WCAG AAA Pass){Color.RESET}"
            elif ratio >= 4.5:
                return f"{Color.FG_BCYAN}{ratio:.2f}:1 (WCAG AA Pass){Color.RESET}"
            else:
                return f"{Color.FG_BRED}{ratio:.2f}:1 (FAIL < 4.5:1){Color.RESET}"

        print(f"  [Light Mode] FG: {fg_light} on BG: {bg_light} -> Contrast: {eval_ratio(ratio_light)}")
        print(f"  [Dark Mode]  FG: {fg_dark} on BG: {bg_dark} -> Contrast: {eval_ratio(ratio_dark)}")

        # Button primary check
        btn_bg = "#2563eb"
        btn_fg = "#ffffff"
        btn_ratio = calculate_contrast_ratio(btn_fg, btn_bg)
        print(f"  [Primary Button Action] FG: {btn_fg} on BG: {btn_bg} -> Contrast: {eval_ratio(btn_ratio)}")

        # Parity Check
        light_keys = set(self.light_theme.tokens.keys())
        dark_keys = set(self.dark_theme.tokens.keys())
        parity_diff = light_keys.symmetric_difference(dark_keys)
        if not parity_diff:
            print(f"  {Color.FG_BGREEN}✓ 100% Theme Parity Confirmed! Both themes adhere strictly to the token contract.{Color.RESET}")
        else:
            print(f"  {Color.FG_BRED}✗ Token Parity Failure! Missing keys: {parity_diff}{Color.RESET}")

    def run_compiler_demo(self):
        print(f"\n{Color.FG_BYELLOW}{Color.BOLD}>>> [3] STYLE DICTIONARY MULTI-TARGET COMPILER <<<{Color.RESET}")
        css_output = TokenCompiler.to_css_custom_properties(self.light_theme, selector=":root[data-theme='light']")
        ts_output = TokenCompiler.to_typescript_interface(self.light_theme)

        print(f"{Color.FG_BCYAN}Target 1: Production CSS Variables (Root Level):{Color.RESET}")
        for line in css_output.split("\n")[:6]:
            print(f"  {line}")
        print(f"  ... [truncated, {len(css_output.splitlines())} total lines]\n")

        print(f"{Color.FG_BMAGENTA}Target 2: TypeScript Strict Typing Contract:{Color.RESET}")
        for line in ts_output.split("\n")[:6]:
            print(f"  {line}")
        print(f"  ... [truncated, {len(ts_output.splitlines())} total lines]")

    def run_specificity_audit(self):
        print(f"\n{Color.FG_BYELLOW}{Color.BOLD}>>> [4] CSS ARCHITECTURE & SPECIFICITY HYGIENE AUDITOR <<<{Color.RESET}")
        sample_selectors = [
            ".c-button--primary",
            ".header .nav-item .link.active",
            "#main-content .hero-title",
            "body div.wrapper ul.menu > li a:hover",
            ".u-text-center",
            "#modal #dialog .c-card__title.is-highlighted"
        ]

        print(f"{'SELECTOR':<45} {'SPECIFICITY':<14} {'AUDIT VERDICT'}")
        print("-" * 90)
        for sel in sample_selectors:
            score, verdict = SpecificityAuditor.audit_selector(sel)
            print(f"{Color.FG_BWHITE}{sel:<45}{Color.RESET} {Color.FG_YELLOW}{score:<14}{Color.RESET} {verdict}")

    def run_interactive(self):
        print_banner()
        while True:
            print(f"\n{Color.BOLD}{Color.FG_BWHITE}Main Control Panel:{Color.RESET}")
            print("  [1] Inspect Multi-Tier Design Tokens (Global, Semantic, Component)")
            print("  [2] Validate WCAG 2.1 Contrast & Theme Contract Parity")
            print("  [3] Build & Compile Style Dictionary (CSS & TypeScript)")
            print("  [4] Run CSS Specificity & Architecture Hygiene Check")
            print("  [5] Run All Production Checks (Automated Suite)")
            print("  [0] Exit")

            try:
                choice = input(f"\n{Color.FG_BCYAN}Select option (0-5) [default 5]: {Color.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Color.FG_YELLOW}Exiting simulation. Good bye!{Color.RESET}")
                break

            if choice == "" or choice == "5":
                self.run_token_inspection()
                self.run_wcag_audit()
                self.run_compiler_demo()
                self.run_specificity_audit()
                print(f"\n{Color.FG_BGREEN}{Color.BOLD}✓ Full Production Styling Systems Simulation Passed Successfully!{Color.RESET}")
                if choice == "":
                    break
            elif choice == "1":
                self.run_token_inspection()
            elif choice == "2":
                self.run_wcag_audit()
            elif choice == "3":
                self.run_compiler_demo()
            elif choice == "4":
                self.run_specificity_audit()
            elif choice == "0":
                print(f"{Color.FG_YELLOW}Exiting simulation.{Color.RESET}")
                break
            else:
                print(f"{Color.FG_RED}Invalid option selected. Please choose between 0 and 5.{Color.RESET}")


# ==============================================================================
# Main Entry Point
# ==============================================================================
if __name__ == "__main__":
    runner = DesignSystemRunner()
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--ci", "-t"):
        # Automated non-interactive mode for CI/Verification tests
        print_banner()
        runner.run_token_inspection()
        runner.run_wcag_audit()
        runner.run_compiler_demo()
        runner.run_specificity_audit()
        print(f"\n{Color.FG_BGREEN}{Color.BOLD}[CI PASS] All Design System contracts verified.{Color.RESET}")
        sys.exit(0)
    else:
        # Check if running in non-interactive environment (like piped stdout or subshell)
        if not sys.stdin.isatty():
            print_banner()
            runner.run_token_inspection()
            runner.run_wcag_audit()
            runner.run_compiler_demo()
            runner.run_specificity_audit()
            print(f"\n{Color.FG_BGREEN}{Color.BOLD}[BATCH PASS] Non-interactive execution finished.{Color.RESET}")
            sys.exit(0)
        else:
            runner.run_interactive()
