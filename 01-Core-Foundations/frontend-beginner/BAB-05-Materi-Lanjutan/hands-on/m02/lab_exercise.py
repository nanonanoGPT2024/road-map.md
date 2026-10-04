#!/usr/bin/env python3
"""
Lab Hands-on: Responsive Web Design, CSS Architecture & Design Systems Engine
Topik: frontend-beginner (01-Core-Foundations) - Bab 05, Modul 02 Deep Dive

Simulasi komprehensif arsitektur CSS modern:
1. Design Token Compiler & WCAG 2.1 Contrast Validator
2. Fluid Typography & Spacing Calculator (Linear Interpolation / CSS clamp())
3. CSS Specificity Calculator & Cascade Resolution Engine
4. BEM (Block Element Modifier) Strict Linter
5. Media Query & Responsive Breakpoint Resolver
"""

import math
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Terminal ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"


# ==============================================================================
# 1. DESIGN TOKEN COMPILER & ACCESSIBILITY (WCAG 2.1)
# ==============================================================================

def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Mengonversi format heksadesimal ke tuple RGB (0-255)."""
    hex_clean = hex_code.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    return int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)


def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Menghitung relative luminance sesuai spesifikasi W3C WCAG 2.1."""
    srgb = [c / 255.0 for c in rgb]
    lum = []
    for c in srgb:
        if c <= 0.03928:
            lum.append(c / 12.92)
        else:
            lum.append(((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2]


def calculate_contrast_ratio(hex1: str, hex2: str) -> float:
    """Menghitung contrast ratio antara 2 warna ((L1 + 0.05) / (L2 + 0.05))."""
    l1 = calculate_relative_luminance(hex_to_rgb(hex1))
    l2 = calculate_relative_luminance(hex_to_rgb(hex2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ==============================================================================
# 2. FLUID TYPOGRAPHY & SPACING ENGINE (CSS clamp() Simulation)
# ==============================================================================

class FluidScaleCalculator:
    """
    Menghitung ukuran dinamis menggunakan interpolasi linier berbasis viewport.
    Formula: y = mx + b -> V = Min + (Max - Min) * ((Viewport - MinVP) / (MaxVP - MinVP))
    """
    def __init__(self, min_vp: float = 375.0, max_vp: float = 1440.0):
        self.min_vp = min_vp
        self.max_vp = max_vp

    def calculate_clamp(self, min_size: float, max_size: float, current_vp: float) -> float:
        """Menghitung nilai fluid terkomputasi untuk viewport saat ini (dalam pixel)."""
        if current_vp <= self.min_vp:
            return min_size
        if current_vp >= self.max_vp:
            return max_size
        
        slope = (max_size - min_size) / (self.max_vp - self.min_vp)
        return round(min_size + slope * (current_vp - self.min_vp), 2)

    def generate_css_clamp(self, min_px: float, max_px: float, rem_base: float = 16.0) -> str:
        """Menghasilkan syntax CSS clamp() standar produksi."""
        slope = (max_px - min_px) / (self.max_vp - self.min_vp)
        y_axis_intersection = -self.min_vp * slope + min_px
        vw_val = round(slope * 100, 4)
        rem_val = round(y_axis_intersection / rem_base, 4)
        min_rem = round(min_px / rem_base, 4)
        max_rem = round(max_px / rem_base, 4)
        return f"clamp({min_rem}rem, {rem_val}rem + {vw_val}vw, {max_rem}rem)"


# ==============================================================================
# 3. CSS SPECIFICITY CALCULATOR & CASCADE RESOLVER
# ==============================================================================

@dataclass
class Specificity:
    inline: int = 0
    ids: int = 0
    classes: int = 0
    elements: int = 0

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.inline, self.ids, self.classes, self.elements)

    def __str__(self) -> str:
        return f"({self.inline}, {self.ids}, {self.classes}, {self.elements})"

    def __gt__(self, other: "Specificity") -> bool:
        return self.as_tuple() > other.as_tuple()

    def __eq__(self, other: "Specificity") -> bool:
        return self.as_tuple() == other.as_tuple()


class SpecificityParser:
    """Parser regex untuk mengukur bobot specificity CSS selector (A, B, C, D)."""
    @staticmethod
    def calculate(selector: str, is_inline: bool = False) -> Specificity:
        if is_inline:
            return Specificity(inline=1, ids=0, classes=0, elements=0)

        clean_sel = selector.strip()
        # Buang pseudo-element untuk parsing pseudo-class terlebih dahulu
        pseudo_elements = len(re.findall(r"::(before|after|first-line|first-letter|placeholder)", clean_sel))
        clean_sel = re.sub(r"::(before|after|first-line|first-letter|placeholder)", "", clean_sel)

        # IDs (#id)
        ids = len(re.findall(r"#[A-Za-z0-9_-]+", clean_sel))
        clean_sel = re.sub(r"#[A-Za-z0-9_-]+", "", clean_sel)

        # Classes, Attributes, & Pseudo-classes (.class, [attr=val], :hover, dsb.)
        classes = len(re.findall(r"\.[A-Za-z0-9_-]+", clean_sel))
        attributes = len(re.findall(r"\[[^\]]+\]", clean_sel))
        pseudo_classes = len(re.findall(r":\b[A-Za-z0-9_-]+\b", clean_sel))
        total_b = classes + attributes + pseudo_classes

        # Elements & Pseudo-elements
        # Menghapus operator combinator (+, >, ~, spasi)
        clean_sel = re.sub(r"\.[A-Za-z0-9_-]+|\[[^\]]+\]|:\b[A-Za-z0-9_-]+\b", "", clean_sel)
        tokens = re.split(r"[\s+>~]+", clean_sel.strip())
        elements = sum(1 for t in tokens if t and re.match(r"^[A-Za-z0-9]+$", t)) + pseudo_elements

        return Specificity(inline=0, ids=ids, classes=total_b, elements=elements)


# ==============================================================================
# 4. BEM CONVENTION LINTER
# ==============================================================================

class BEMLinter:
    """Linter arsitektur CSS metodologi Block Element Modifier."""
    # Pattern: block, block__element, block--modifier, block__element--modifier
    BEM_REGEX = re.compile(
        r"^[a-z0-9]+(-[a-z0-9]+)*"                    # Block
        r"(__[a-z0-9]+(-[a-z0-9]+)*)?"                # Optional Element
        r"(--[a-z0-9]+(-[a-z0-9]+)*)?$"               # Optional Modifier
    )

    @classmethod
    def lint_selector(cls, selector: str) -> List[Tuple[str, bool, str]]:
        classes = re.findall(r"\.([A-Za-z0-9_-]+)", selector)
        results = []
        for cls_name in classes:
            is_valid = bool(cls.BEM_REGEX.match(cls_name))
            reason = "Valid BEM Token" if is_valid else "Violates BEM naming (use block__element--modifier)"
            results.append((cls_name, is_valid, reason))
        return results


# ==============================================================================
# 5. RESPONSIVE BREAKPOINT & CASCADE SIMULATION RUNNER
# ==============================================================================

@dataclass
class CSSRule:
    selector: str
    properties: Dict[str, str]
    media_min_width: int = 0
    source_order: int = 0
    specificity: Specificity = Specificity()


class ResponsiveEngine:
    """Simulasi rendering cascade CSS berdasarkan Viewport & Media Query."""
    def __init__(self):
        self.rules: List[CSSRule] = []
        self._order_counter = 0

    def add_rule(self, selector: str, properties: Dict[str, str], min_width: int = 0, is_inline: bool = False):
        self._order_counter += 1
        spec = SpecificityParser.calculate(selector, is_inline=is_inline)
        self.rules.append(CSSRule(
            selector=selector,
            properties=properties,
            media_min_width=min_width,
            source_order=self._order_counter,
            specificity=spec
        ))

    def resolve_styles(self, viewport_width: int, element_matching_selectors: List[str]) -> Dict[str, Tuple[str, str]]:
        """
        Menyelesaikan Cascade CSS:
        1. Media Query Match
        2. Selector Match
        3. Specificity Comparison
        4. Source Order (Tie-breaking)
        Returns: Dict[property, (value, winner_selector)]
        """
        active_rules = []
        for r in self.rules:
            if viewport_width >= r.media_min_width and r.selector in element_matching_selectors:
                active_rules.append(r)

        # Sort berdasarkan Specificity lalu Source Order
        sorted_rules = sorted(
            active_rules,
            key=lambda r: (r.specificity.as_tuple(), r.source_order)
        )

        computed_styles: Dict[str, Tuple[str, str]] = {}
        for rule in sorted_rules:
            for prop, val in rule.properties.items():
                computed_styles[prop] = (val, rule.selector)

        return computed_styles


# ==============================================================================
# LAB TEST HARNESS & DEMONSTRATION
# ==============================================================================

def main():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== LAB: RESPONSIVE WEB ARCHITECTURE & DESIGN SYSTEM DEEP DIVE ==={CLR_RESET}\n")

    # 1. DESIGN TOKENS & ACCESSIBILITY VALIDATION
    print(f"{CLR_BOLD}[1] DESIGN TOKENS & WCAG 2.1 CONTRAST VALIDATION{CLR_RESET}")
    design_tokens = {
        "color-primary": "#0D6EFD",
        "color-primary-dark": "#0A58CA",
        "color-surface": "#FFFFFF",
        "color-muted": "#6C757D",
        "color-dark": "#212529"
    }

    pairs_to_test = [
        ("color-surface", "color-primary", "Primary Button on White"),
        ("color-surface", "color-muted", "Muted Text on White"),
        ("color-surface", "color-dark", "Dark Text on White"),
        ("color-primary-dark", "color-surface", "White Text on Primary Dark")
    ]

    for bg_key, fg_key, desc in pairs_to_test:
        bg = design_tokens[bg_key]
        fg = design_tokens[fg_key]
        ratio = calculate_contrast_ratio(bg, fg)
        aa_normal = ratio >= 4.5
        aa_large = ratio >= 3.0
        status = f"{CLR_GREEN}PASS (AA){CLR_RESET}" if aa_normal else (
            f"{CLR_YELLOW}PASS (Large text only){CLR_RESET}" if aa_large else f"{CLR_RED}FAIL{CLR_RESET}"
        )
        print(f"  • {desc:<30} Ratio: {ratio:5.2f}:1 -> {status}")

    # 2. FLUID DESIGN SCALING (clamp() Math)
    print(f"\n{CLR_BOLD}[2] FLUID TYPOGRAPHY & SPACING ENGINE (CSS clamp()){CLR_RESET}")
    fluid_calc = FluidScaleCalculator(min_vp=375.0, max_vp=1440.0)
    h1_clamp = fluid_calc.generate_css_clamp(min_px=24.0, max_px=48.0)
    print(f"  Token 'font-size-h1': {CLR_MAGENTA}{h1_clamp}{CLR_RESET}")
    print("  Viewport interpolation step evaluation:")

    test_viewports = [375, 480, 768, 1024, 1440, 1920]
    for vp in test_viewports:
        computed = fluid_calc.calculate_clamp(24.0, 48.0, vp)
        bar_len = int((computed - 24.0) / (48.0 - 24.0) * 20)
        bar = "■" * bar_len + " " * (20 - bar_len)
        print(f"    VP: {vp:4d}px -> Computed: {computed:5.2f}px |{CLR_BLUE}{bar}{CLR_RESET}|")

    # 3. BEM LINTER TEST
    print(f"\n{CLR_BOLD}[3] CSS ARCHITECTURE: BEM LINTER VALIDATION{CLR_RESET}")
    selectors_to_lint = [
        ".c-btn",
        ".c-btn--primary",
        ".c-card__header",
        ".c-card__header__title",    # Anti-pattern (nested element)
        ".button_active",            # Non-standard separator
        ".navItem--hover-state"      # CamelCase violation
    ]

    for sel in selectors_to_lint:
        results = BEMLinter.lint_selector(sel)
        for cls_name, is_valid, msg in results:
            tag = f"{CLR_GREEN}VALID{CLR_RESET}" if is_valid else f"{CLR_RED}INVALID{CLR_RESET}"
            print(f"  • Class: {cls_name:<26} [{tag}] {msg}")

    # 4. CASCADE & SPECIFICITY RESOLUTION SIMULATION
    print(f"\n{CLR_BOLD}[4] CSS SPECIFICITY & CASCADE RESOLVER EXECUTION{CLR_RESET}")
    engine = ResponsiveEngine()

    # Rule Definition
    engine.add_rule("button", {"background": "#6c757d", "color": "#fff", "font-size": "14px"})
    engine.add_rule(".c-btn", {"background": "#0d6efd", "padding": "8px 16px"})
    engine.add_rule("#submit-btn", {"background": "#198754"})
    engine.add_rule(".c-card .c-btn", {"background": "#ffc107"})
    # Responsive override on mobile breakpoint vs desktop
    engine.add_rule(".c-btn", {"padding": "16px 32px", "font-size": "18px"}, min_width=768)
    engine.add_rule("#submit-btn", {"padding": "12px 24px"}, min_width=1024)

    # Simulated Element in DOM:
    # <div class="c-card"> <button id="submit-btn" class="c-btn">Submit</button> </div>
    element_classes = ["button", ".c-btn", ".c-card .c-btn", "#submit-btn"]

    simulated_screens = [375, 768, 1200]
    for vp in simulated_screens:
        print(f"\n  --- Rendering at Viewport: {CLR_BOLD}{vp}px{CLR_RESET} ---")
        resolved = engine.resolve_styles(vp, element_classes)
        for prop, (val, winner) in sorted(resolved.items()):
            spec = SpecificityParser.calculate(winner)
            print(f"    {prop:<15}: {CLR_YELLOW}{val:<10}{CLR_RESET} "
                  f"(Source: {CLR_CYAN}{winner:<16}{CLR_RESET} Specificity: {spec})")

    print(f"\n{CLR_BOLD}{CLR_GREEN}✓ Engine Execution Completed Successfully.{CLR_RESET}\n")


if __name__ == "__main__":
    main()