#!/usr/bin/env python3
"""
Enterprise CSS Performance Optimization, Accessibility (A11y), and Tooling Engine.
Simulates an industrial build pipeline analyzing CSS AST, computing selector specificity,
evaluating WCAG 2.1 luminance contrast ratios, and purging dead styles (Tree-Shaking).
"""

import sys
import re
import math
import time
from typing import List, Dict, Tuple, Set

# Terminal ANSI Styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"


class WCAGContrastAuditor:
    """
    Evaluates color accessibility according to W3C WCAG 2.1 relative luminance algorithms.
    Computes contrast ratios and asserts AA / AAA compliance for normal and large text.
    """

    @staticmethod
    def _hex_to_rgb(hex_code: str) -> Tuple[float, float, float]:
        hex_code = hex_code.lstrip("#")
        if len(hex_code) == 3:
            hex_code = "".join([c * 2 for c in hex_code])
        if len(hex_code) != 6:
            raise ValueError(f"Malformed hex color: #{hex_code}")
        r, g, b = (int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
        return r / 255.0, g / 255.0, b / 255.0

    @classmethod
    def _linearize_srgb(cls, c: float) -> float:
        # W3C IEC 61966-2-1 transfer function
        return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)

    @classmethod
    def calculate_relative_luminance(cls, hex_color: str) -> float:
        r, g, b = cls._hex_to_rgb(hex_color)
        r_lin = cls._linearize_srgb(r)
        g_lin = cls._linearize_srgb(g)
        b_lin = cls._linearize_srgb(b)
        # Standard ITU-R BT.709 coefficients
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    @classmethod
    def calculate_contrast_ratio(cls, foreground_hex: str, background_hex: str) -> float:
        lum1 = cls.calculate_relative_luminance(foreground_hex)
        lum2 = cls.calculate_relative_luminance(background_hex)
        lighter = max(lum1, lum2)
        darker = min(lum1, lum2)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def audit_pair(cls, fg: str, bg: str) -> Dict[str, any]:
        ratio = cls.calculate_contrast_ratio(fg, bg)
        return {
            "ratio": ratio,
            "aa_normal": ratio >= 4.5,
            "aa_large": ratio >= 3.0,
            "aaa_normal": ratio >= 7.0,
            "aaa_large": ratio >= 4.5,
        }


class SpecificityCalculator:
    """
    Computes CSS selector specificity according to W3C Selectors Level 4 specification.
    Returns a 3-tuple (A, B, C):
      A: ID selectors
      B: Classes, attributes, pseudo-classes
      C: Type (element) selectors and pseudo-elements
    """

    RE_ID = re.compile(r"#[A-Za-z0-9_-]+")
    RE_CLASS = re.compile(r"\.[A-Za-z0-9_-]+")
    RE_ATTR = re.compile(r"\[[^\]]+\]")
    RE_PSEUDO_CLASS = re.compile(r":(?!:)[A-Za-z0-9_-]+(\([^)]*\))?")
    RE_PSEUDO_ELEMENT = re.compile(r"::[A-Za-z0-9_-]+")
    RE_ELEMENT = re.compile(r"(^|[\s>+~])([A-Za-z0-9_-]+)")

    @classmethod
    def calculate(cls, selector: str) -> Tuple[int, int, int]:
        s = selector.strip()
        # Clean combinators and wildcards
        cleaned = re.sub(r"[*+>~]", " ", s)

        # Count A (IDs)
        ids = len(cls.RE_ID.findall(cleaned))
        cleaned = cls.RE_ID.sub(" ", cleaned)

        # Count B (Classes, Attributes, Pseudo-classes)
        classes = len(cls.RE_CLASS.findall(cleaned))
        cleaned = cls.RE_CLASS.sub(" ", cleaned)

        attrs = len(cls.RE_ATTR.findall(cleaned))
        cleaned = cls.RE_ATTR.sub(" ", cleaned)

        pseudo_classes = len(cls.RE_PSEUDO_CLASS.findall(cleaned))
        cleaned = cls.RE_PSEUDO_CLASS.sub(" ", cleaned)

        # Count C (Pseudo-elements, Elements)
        pseudo_elements = len(cls.RE_PSEUDO_ELEMENT.findall(cleaned))
        cleaned = cls.RE_PSEUDO_ELEMENT.sub(" ", cleaned)

        elements = len([m for m in cls.RE_ELEMENT.findall(cleaned) if m[1] != ""])

        a = ids
        b = classes + attrs + pseudo_classes
        c = elements + pseudo_elements
        return (a, b, c)


class CSSRule:
    """Represents an individual parsed CSS declaration block."""

    def __init__(self, selector: str, declarations: str):
        self.selector = selector.strip()
        self.declarations = declarations.strip()
        self.specificity = SpecificityCalculator.calculate(self.selector)

    def extract_colors(self) -> Tuple[str, str]:
        """Extracts hex color and background-color if defined."""
        color_match = re.search(r"(?<!-)color\s*:\s*(#[0-9a-fA-F]{3,6})", self.declarations)
        bg_match = re.search(r"background(-color)?\s*:\s*(#[0-9a-fA-F]{3,6})", self.declarations)
        fg = color_match.group(1) if color_match else None
        bg = bg_match.group(2) if bg_match else None
        return fg, bg

    def serialize(self, minified: bool = False) -> str:
        if minified:
            clean_decls = re.sub(r"\s*([:;])\s*", r"\1", self.declarations)
            clean_decls = clean_decls.rstrip(";")
            return f"{self.selector}{{{clean_decls}}}"
        return f"{self.selector} {{\n  {self.declarations}\n}}"


class EnterpriseOptimizerEngine:
    """
    Parses stylesheets, maps dependencies against target HTML DOM tokens,
    purges dead selectors, and reports performance/accessibility telemetry.
    """

    RE_RULE = re.compile(r"([^{]+)\{([^}]+)\}")

    def __init__(self, raw_css: str):
        self.raw_css = raw_css
        self.rules: List[CSSRule] = []
        self._parse()

    def _parse(self):
        # Strip comments
        sanitized = re.sub(r"/\*.*?\*/", "", self.raw_css, flags=re.DOTALL)
        for match in self.RE_RULE.finditer(sanitized):
            selector, decls = match.groups()
            for sub_sel in selector.split(","):
                sub_sel = sub_sel.strip()
                if sub_sel and not sub_sel.startswith("@"):
                    self.rules.append(CSSRule(sub_sel, decls))

    @staticmethod
    def extract_dom_tokens(html_content: str) -> Tuple[Set[str], Set[str], Set[str]]:
        """Extracts HTML tags, classes, and IDs used in the markup."""
        tags = set(re.findall(r"<([a-zA-Z0-9]+)", html_content))
        class_matches = re.findall(r'class=["\']([^"\']+)["\']', html_content)
        classes = {cls for group in class_matches for cls in group.split()}
        id_matches = re.findall(r'id=["\']([^"\']+)["\']', html_content)
        ids = set(id_matches)
        return tags, classes, ids

    def purge_unused(self, tags: Set[str], classes: Set[str], ids: Set[str]) -> Tuple[List[CSSRule], List[CSSRule]]:
        used_rules = []
        purged_rules = []

        for rule in self.rules:
            tokens = re.findall(r"([.#]?[A-Za-z0-9_-]+)", rule.selector)
            is_active = True
            for tok in tokens:
                if tok.startswith("#") and tok[1:] not in ids:
                    is_active = False
                    break
                elif tok.startswith(".") and tok[1:] not in classes:
                    is_active = False
                    break
                elif not tok.startswith((".", "#")) and tok.lower() not in tags:
                    # Ignore pseudo-classes or pseudo-elements
                    if not (tok.startswith(":") or tok in {"root", "focus", "hover"}):
                        is_active = False
                        break
            if is_active:
                used_rules.append(rule)
            else:
                purged_rules.append(rule)

        return used_rules, purged_rules


# =====================================================================
# LAB EXECUTION HARNESS
# =====================================================================

SAMPLE_CSS = """
/* Global Baseline Styles */
body {
    background-color: #ffffff;
    color: #333333;
    font-size: 16px;
}

header.navbar {
    background: #1a202c;
    color: #edf2f7;
    padding: 10px;
}

/* Problematic Accessibility Section (Low Contrast) */
.alert-warning {
    background-color: #ffff00;
    color: #ffffff;
    border: 1px solid #e2e8f0;
}

/* High Specificity Anti-Pattern */
#app div.container div.wrapper ul.menu-list li.item a.active {
    color: #3182ce;
    font-weight: bold;
}

/* Interactive States */
button.btn-primary {
    background-color: #2b6cb0;
    color: #ffffff;
}

/* Dead Enterprise Rules (Unused Legacy Features) */
.legacy-datatable-v1 {
    display: none;
    background: #000000;
}

#legacy-modal-container .widget-popup {
    margin: 50px;
    color: #999999;
}

aside.deprecated-sidebar {
    width: 250px;
    color: #718096;
}
"""

SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Enterprise Gateway</title></head>
<body>
    <header class="navbar">Enterprise Console</header>
    <div id="app">
        <div class="container">
            <div class="wrapper">
                <ul class="menu-list">
                    <li class="item"><a class="active">Dashboard</a></li>
                </ul>
            </div>
        </div>
        <div class="alert-warning">Warning: Migration scheduled tonight.</div>
        <button class="btn-primary">Acknowledge</button>
    </div>
</body>
</html>
"""


def main():
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}   ENTERPRISE CSS PERFORMANCE, A11Y & OPTIMIZATION PIPELINE LAB      {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    start_time = time.perf_counter()

    # Step 1: Ingestion & AST Parsing
    print(f"{BOLD}[*] Phase 1: Ingesting Stylesheet & Parsing AST Rules...{RESET}")
    engine = EnterpriseOptimizerEngine(SAMPLE_CSS)
    raw_size = len(SAMPLE_CSS.encode("utf-8"))
    print(f"    - Parsed Rules Detected: {GREEN}{len(engine.rules)}{RESET}")
    print(f"    - Raw Ingest Size:       {YELLOW}{raw_size} bytes{RESET}\n")

    # Step 2: Specificity Analysis & Code Smell Detection
    print(f"{BOLD}[*] Phase 2: Static Selector Specificity Audit (W3C Level 4)...{RESET}")
    for rule in engine.rules:
        a, b, c = rule.specificity
        # Flag specificity smells where ID >= 1 and class count >= 3
        smell = f"{RED}[HIGH SPECIFICITY SMELL]{RESET}" if a >= 1 and b >= 3 else f"{GREEN}[OPTIMAL]{RESET}"
        spec_repr = f"({a},{b},{c})"
        print(f"    - {spec_repr.ljust(10)} | {rule.selector.ljust(50)} {smell}")
    print()

    # Step 3: Accessibility (WCAG 2.1) Color Contrast Engine
    print(f"{BOLD}[*] Phase 3: Accessibility & Luminance Contrast Engine (WCAG 2.1)...{RESET}")
    for rule in engine.rules:
        fg, bg = rule.extract_colors()
        if fg and bg:
            audit = WCAGContrastAuditor.audit_pair(fg, bg)
            ratio = audit["ratio"]
            status = f"{GREEN}PASS (AA Large & Normal){RESET}" if audit["aa_normal"] else f"{RED}FAIL (Contrast: {ratio:.2f}:1 < 4.5:1){RESET}"
            print(f"    Rule: {rule.selector}")
            print(f"      FG: {fg} | BG: {bg} -> Contrast Ratio: {ratio:.2f}:1")
            print(f"      Compliance Result: {status}")
    print()

    # Step 4: Dead Code Elimination (PurgeCSS Simulation)
    print(f"{BOLD}[*] Phase 4: Tree-Shaking & Dead Code Elimination (DOM Diffing)...{RESET}")
    tags, classes, ids = engine.extract_dom_tokens(SAMPLE_HTML)
    used_rules, purged_rules = engine.purge_unused(tags, classes, ids)

    print(f"    - Retained Selectors ({len(used_rules)}):")
    for r in used_rules:
        print(f"       {GREEN}✔{RESET} {r.selector}")

    print(f"    - Purged Zombie Selectors ({len(purged_rules)}):")
    for r in purged_rules:
        print(f"       {RED}✖{RESET} {r.selector}")
    print()

    # Step 5: Minification & Emission
    print(f"{BOLD}[*] Phase 5: Critical CSS Minification & Byte Delta Analysis...{RESET}")
    minified_css = "".join([r.serialize(minified=True) for r in used_rules])
    optimized_size = len(minified_css.encode("utf-8"))
    reduction = ((raw_size - optimized_size) / raw_size) * 100

    elapsed = (time.perf_counter() - start_time) * 1000

    print(f"    {BOLD}Minified Output:{RESET}\n    {MAGENTA}{minified_css}{RESET}\n")
    print(f"{BOLD}========================= METRICS SUMMARY ========================={RESET}")
    print(f"  Pre-Optimization Payload:   {YELLOW}{raw_size} bytes{RESET}")
    print(f"  Post-Optimization Payload:  {GREEN}{optimized_size} bytes{RESET}")
    print(f"  Net Bandwidth Optimization: {GREEN}{reduction:.2f}% reduction{RESET}")
    print(f"  Pipeline Execution Latency: {CYAN}{elapsed:.3f} ms{RESET}")
    print(f"{BOLD}==================================================================={RESET}")


if __name__ == "__main__":
    main()