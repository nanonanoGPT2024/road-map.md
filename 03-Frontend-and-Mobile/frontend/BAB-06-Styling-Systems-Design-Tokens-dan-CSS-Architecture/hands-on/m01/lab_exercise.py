#!/usr/bin/env python3
"""
BAB-06: Styling Systems, Design Tokens, & CSS Architecture Simulator
Hands-on Interactive Lab Exercise (Module 01)

Features:
1. Multi-tier Design Token Resolution (Global -> Semantic -> Component)
2. Theme Switching & Token Transformation (CSS Custom Properties & JSON)
3. CSS Selector Specificity Matrix Calculator
4. ANSI Terminal UI Visualizer with Live Theme Preview
"""

import sys
import json
import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

# ANSI Escape Codes for CLI Terminal Styling
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

# Standard Foreground Colors
FG_BLACK = "\033[30m"
FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"

# Standard Background Colors
BG_BLACK = "\033[40m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_BLUE = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"
BG_WHITE = "\033[47m"


def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Converts a 6-digit hex color string to an RGB tuple."""
    hex_clean = hex_code.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    return int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)


def rgb_to_ansi_fg(r: int, g: int, b: int) -> str:
    """Returns ANSI 24-bit truecolor escape sequence for foreground."""
    return f"\033[38;2;{r};{g};{b}m"


def rgb_to_ansi_bg(r: int, g: int, b: int) -> str:
    """Returns ANSI 24-bit truecolor escape sequence for background."""
    return f"\033[48;2;{r};{g};{b}m"


# Token Definitions
GLOBAL_TOKENS = {
    "color": {
        "blue-100": "#dbeafe",
        "blue-500": "#3b82f6",
        "blue-600": "#2563eb",
        "blue-900": "#1e3a8a",
        "slate-50": "#f8fafc",
        "slate-100": "#f1f5f9",
        "slate-800": "#1e293b",
        "slate-900": "#0f172a",
        "emerald-500": "#10b981",
        "rose-500": "#f43f5e",
        "amber-500": "#f59e0b",
    },
    "spacing": {
        "xs": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "32px",
    },
    "font-family": {
        "sans": "system-ui, -apple-system, sans-serif",
        "mono": "ui-monospace, SFMono-Regular, monospace",
    },
    "radius": {
        "none": "0px",
        "sm": "4px",
        "md": "8px",
        "full": "9999px",
    }
}

SEMANTIC_TOKENS_LIGHT = {
    "color-bg-canvas": "{color.slate-50}",
    "color-bg-surface": "#ffffff",
    "color-text-primary": "{color.slate-900}",
    "color-text-muted": "{color.slate-800}",
    "color-action-primary": "{color.blue-600}",
    "color-action-primary-hover": "{color.blue-900}",
    "color-status-success": "{color.emerald-500}",
    "color-status-error": "{color.rose-500}",
    "color-status-warning": "{color.amber-500}",
}

SEMANTIC_TOKENS_DARK = {
    "color-bg-canvas": "{color.slate-900}",
    "color-bg-surface": "{color.slate-800}",
    "color-text-primary": "{color.slate-50}",
    "color-text-muted": "{color.slate-100}",
    "color-action-primary": "{color.blue-500}",
    "color-action-primary-hover": "{color.blue-600}",
    "color-status-success": "{color.emerald-500}",
    "color-status-error": "{color.rose-500}",
    "color-status-warning": "{color.amber-500}",
}

COMPONENT_TOKENS = {
    "button-bg": "{color-action-primary}",
    "button-text": "#ffffff",
    "button-padding-y": "{spacing.sm}",
    "button-padding-x": "{spacing.md}",
    "button-radius": "{radius.md}",
    "card-bg": "{color-bg-surface}",
    "card-text": "{color-text-primary}",
    "card-padding": "{spacing.lg}",
    "card-radius": "{radius.md}",
}


class TokenResolver:
    """Resolves aliased tokens across hierarchy tiers."""

    def __init__(self, globals_dict: Dict[str, Any], semantic_dict: Dict[str, str]):
        self.globals = globals_dict
        self.semantics = semantic_dict
        self.alias_pattern = re.compile(r"\{([^}]+)\}")

    def lookup_global(self, path: str) -> str:
        parts = path.split(".")
        current = self.globals
        for p in parts:
            if isinstance(current, dict) and p in current:
                current = current[p]
            else:
                return f"[UNRESOLVED:{path}]"
        return str(current)

    def resolve_value(self, val: str, depth: int = 0) -> str:
        if depth > 5:
            return val
        match = self.alias_pattern.search(val)
        if not match:
            return val
        token_ref = match.group(1)
        if token_ref in self.semantics:
            resolved_ref = self.resolve_value(self.semantics[token_ref], depth + 1)
        elif "." in token_ref:
            resolved_ref = self.lookup_global(token_ref)
        else:
            resolved_ref = f"[UNKNOWN_ALIAS:{token_ref}]"
        new_val = val[:match.start()] + resolved_ref + val[match.end():]
        return self.resolve_value(new_val, depth + 1)

    def resolve_all_semantics(self) -> Dict[str, str]:
        return {k: self.resolve_value(v) for k, v in self.semantics.items()}

    def resolve_components(self, components: Dict[str, str]) -> Dict[str, str]:
        resolved = {}
        for k, v in components.items():
            match = self.alias_pattern.search(v)
            if match:
                ref = match.group(1)
                if ref in self.semantics:
                    resolved[k] = self.resolve_value(self.semantics[ref])
                elif "." in ref:
                    resolved[k] = self.lookup_global(ref)
                else:
                    resolved[k] = self.resolve_value(v)
            else:
                resolved[k] = v
        return resolved


def export_css_variables(theme_name: str, resolved_tokens: Dict[str, str]) -> str:
    """Transforms resolved tokens into CSS custom property declarations."""
    selector = ":root" if theme_name == "light" else "[data-theme='dark']"
    lines = [f"{selector} {{"]
    for k, v in sorted(resolved_tokens.items()):
        lines.append(f"  --{k}: {v};")
    lines.append("}")
    return "\n".join(lines)


@dataclass
class SpecificityScore:
    inline: int = 0
    ids: int = 0
    classes: int = 0
    elements: int = 0

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.inline, self.ids, self.classes, self.elements)

    def __str__(self) -> str:
        return f"({self.inline}, {self.ids}, {self.classes}, {self.elements})"


def calculate_css_specificity(selector: str) -> SpecificityScore:
    """Calculates standard CSS specificity vector (Inline, ID, Class/Attr/Pseudo-class, Element)."""
    clean_selector = selector.strip()
    if clean_selector.startswith("style="):
        return SpecificityScore(inline=1, ids=0, classes=0, elements=0)

    # Remove string literals inside quotes to avoid false positives
    s = re.sub(r"\"[^\"]*\"|'[^']*'", "", clean_selector)
    # Remove pseudo-elements (double colon) first
    pseudo_elements = len(re.findall(r"::[a-zA-Z-]+", s))
    s = re.sub(r"::[a-zA-Z-]+", "", s)

    # Count IDs
    ids = len(re.findall(r"#[a-zA-Z0-9_-]+", s))

    # Count classes, attributes, pseudo-classes
    classes = len(re.findall(r"\.[a-zA-Z0-9_-]+", s))
    attrs = len(re.findall(r"\[[^\]]+\]", s))
    pseudo_classes = len(re.findall(r":(?!:)[a-zA-Z0-9_-]+(\([^)]*\))?", s))
    class_level = classes + attrs + pseudo_classes

    # Clean up matched items to evaluate element selectors
    s_elems = re.sub(r"#[a-zA-Z0-9_-]+", "", s)
    s_elems = re.sub(r"\.[a-zA-Z0-9_-]+", "", s_elems)
    s_elems = re.sub(r"\[[^\]]+\]", "", s_elems)
    s_elems = re.sub(r":(?!:)[a-zA-Z0-9_-]+(\([^)]*\))?", "", s_elems)
    s_elems = re.sub(r"[>+~*,]", " ", s_elems)

    elements_found = [token for token in s_elems.split() if token and not token.isdigit()]
    elements_count = len(elements_found) + pseudo_elements

    return SpecificityScore(inline=0, ids=ids, classes=class_level, elements=elements_count)


def render_button_component(label: str, bg_hex: str, fg_hex: str, radius_str: str) -> None:
    """Renders a simulated button in terminal using 24-bit ANSI colors."""
    try:
        bg_r, bg_g, bg_b = hex_to_rgb(bg_hex)
        fg_r, fg_g, fg_b = hex_to_rgb(fg_hex)
        fg_seq = rgb_to_ansi_fg(fg_r, fg_g, fg_b)
        bg_seq = rgb_to_ansi_bg(bg_r, bg_g, bg_b)
    except Exception:
        fg_seq = FG_WHITE
        bg_seq = BG_BLUE

    pad = "  "
    print(f"{BOLD}Simulated Component Output:{RESET}")
    print(f"  {bg_seq}{fg_seq} {pad}{label.center(16)}{pad} {RESET}")
    print(f"  {DIM}Tokens: bg={bg_hex} | text={fg_hex} | radius={radius_str}{RESET}\n")


def display_token_table(title: str, token_map: Dict[str, str]) -> None:
    """Prints a styled token inspection table."""
    print(f"{FG_CYAN}{BOLD}=== {title} ==={RESET}")
    print(f"{DIM}{'Token Name':<32} {'Resolved Value':<24}{RESET}")
    print(f"{DIM}{'-'*56}{RESET}")
    for name, val in sorted(token_map.items()):
        preview = ""
        if val.startswith("#"):
            try:
                r, g, b = hex_to_rgb(val)
                bg_ansi = rgb_to_ansi_bg(r, g, b)
                preview = f" {bg_ansi}    {RESET}"
            except Exception:
                preview = ""
        print(f"{FG_YELLOW}{name:<32}{RESET} {FG_WHITE}{val:<24}{RESET}{preview}")
    print()


def run_specificity_lab() -> None:
    """Demonstrates and compares CSS selector specificities."""
    print(f"{FG_MAGENTA}{BOLD}=== CSS Selector Specificity Analyzer ==={RESET}")
    selectors = [
        ("BEM Class Pattern", ".c-card__header--highlighted"),
        ("Overly Nested Selector", "div.main-container > #content .c-card span.c-card__title"),
        ("Single ID Selector", "#user-profile-widget"),
        ("Utility Class", ".u-text-center"),
        ("Inline CSS Attribute", "style=\"color: red;\""),
        ("Element + Pseudo Class", "button:hover:not(:disabled)"),
    ]

    print(f"{DIM}{'Category':<24} {'Selector':<44} {'Score (I,ID,C,E)':<16}{RESET}")
    print(f"{DIM}{'-'*88}{RESET}")
    for category, sel in selectors:
        score = calculate_css_specificity(sel)
        print(f"{FG_GREEN}{category:<24}{RESET} {FG_WHITE}{sel:<44}{RESET} {FG_CYAN}{BOLD}{str(score):<16}{RESET}")
    print()


def run_pipeline() -> None:
    """Executes the full pipeline demonstrating design tokens and CSS generation."""
    print(f"\n{BOLD}{FG_BLUE}=================================================================={RESET}")
    print(f"{BOLD}{FG_BLUE}  FRONTEND ARCHITECTURE: DESIGN TOKENS & STYLING SYSTEMS LAB     {RESET}")
    print(f"{BOLD}{FG_BLUE}=================================================================={RESET}\n")

    # Light Theme Resolution
    light_resolver = TokenResolver(GLOBAL_TOKENS, SEMANTIC_TOKENS_LIGHT)
    resolved_light_semantics = light_resolver.resolve_all_semantics()
    resolved_light_components = light_resolver.resolve_components(COMPONENT_TOKENS)

    # Dark Theme Resolution
    dark_resolver = TokenResolver(GLOBAL_TOKENS, SEMANTIC_TOKENS_DARK)
    resolved_dark_semantics = dark_resolver.resolve_all_semantics()
    resolved_dark_components = dark_resolver.resolve_components(COMPONENT_TOKENS)

    display_token_table("Semantic Tokens [Light Theme]", resolved_light_semantics)
    display_token_table("Semantic Tokens [Dark Theme]", resolved_dark_semantics)
    display_token_table("Component Tokens [Light Theme]", resolved_light_components)

    print(f"{FG_CYAN}{BOLD}=== CSS Custom Properties Code Generation ==={RESET}")
    light_css = export_css_variables("light", resolved_light_semantics)
    dark_css = export_css_variables("dark", resolved_dark_semantics)
    print(f"{DIM}/* Generated Light Theme CSS Variables */{RESET}")
    print(f"{FG_WHITE}{light_css}{RESET}\n")
    print(f"{DIM}/* Generated Dark Theme CSS Variables */{RESET}")
    print(f"{FG_WHITE}{dark_css}{RESET}\n")

    # Render Component Preview
    print(f"{FG_CYAN}{BOLD}=== UI Component Rendering in Light Theme ==={RESET}")
    render_button_component(
        "Confirm Action",
        resolved_light_components["button-bg"],
        resolved_light_components["button-text"],
        resolved_light_components["button-radius"]
    )

    print(f"{FG_CYAN}{BOLD}=== UI Component Rendering in Dark Theme ==={RESET}")
    render_button_component(
        "Confirm Action",
        resolved_dark_components["button-bg"],
        resolved_dark_components["button-text"],
        resolved_dark_components["button-radius"]
    )

    # Specificity Matrix
    run_specificity_lab()


def interactive_menu() -> None:
    """Provides interactive shell to experiment with tokens and selectors."""
    while True:
        print(f"{FG_YELLOW}{BOLD}[Menu Options]{RESET}")
        print("1. Run Full Architectural Pipeline (Tokens -> CSS -> UI Render)")
        print("2. Test Custom CSS Selector Specificity")
        print("3. Export CSS Variables to File (output_theme.css)")
        print("4. Exit")
        try:
            choice = input(f"{BOLD}Select an option (1-4): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if choice == "1":
            run_pipeline()
        elif choice == "2":
            try:
                sel = input("Enter CSS Selector: ").strip()
                if sel:
                    score = calculate_css_specificity(sel)
                    print(f"\n{FG_GREEN}Selector:{RESET} {sel}")
                    print(f"{FG_CYAN}Specificity Score (Inline, ID, Class, Element): {BOLD}{score}{RESET}\n")
            except (EOFError, KeyboardInterrupt):
                break
        elif choice == "3":
            light_resolver = TokenResolver(GLOBAL_TOKENS, SEMANTIC_TOKENS_LIGHT)
            resolved = light_resolver.resolve_all_semantics()
            css_code = export_css_variables("light", resolved)
            with open("output_theme.css", "w", encoding="utf-8") as f:
                f.write(css_code)
            print(f"\n{FG_GREEN}Saved output_theme.css successfully.{RESET}\n")
        elif choice == "4" or choice.lower() == "q":
            print(f"{FG_CYAN}Exiting Lab Simulator.{RESET}")
            break
        else:
            print(f"{FG_RED}Invalid option selected.{RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        run_pipeline()
    else:
        # If interactive stdin is available, run pipeline then menu
        if sys.stdin.isatty():
            run_pipeline()
            interactive_menu()
        else:
            run_pipeline()
