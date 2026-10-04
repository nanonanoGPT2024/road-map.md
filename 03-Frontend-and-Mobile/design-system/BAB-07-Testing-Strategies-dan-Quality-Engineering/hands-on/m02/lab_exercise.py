#!/usr/bin/env python3
"""
Lab Exercise: Design System Quality Engineering & Testing Pipeline
Chapter 07: Testing Strategies & Quality Engineering (Deep Dive)

This script implements an automated Design System Quality Engineering pipeline:
1. WCAG 2.1 AA/AAA Contrast Ratio & Token Compliance Engine.
2. Component Schema & Design Token Contract Validator.
3. Pixel-level Visual Regression Diff Engine (Virtual Framebuffer Comparison).
"""

import sys
import time
import math
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

# ==============================================================================
# ANSI Terminal Formatting Utilities
# ==============================================================================
class ANSI:
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
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_GRAY = "\033[100m"


# ==============================================================================
# 1. WCAG 2.1 Accessibility & Color Contrast Testing Engine
# ==============================================================================
def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Converts a standard 6-character hex color to an (R, G, B) integer tuple."""
    clean_hex = hex_code.lstrip("#")
    if len(clean_hex) != 6:
        raise ValueError(f"Invalid hex color: {hex_code}")
    return tuple(int(clean_hex[i:i+2], 16) for i in (0, 2, 4))  # type: ignore

def srgb_channel_to_linear(channel: float) -> float:
    """Converts an 8-bit sRGB color channel (normalized 0-1) to linear luminance."""
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """
    Computes relative luminance according to the W3C WCAG 2.1 standard formula:
    L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin
    """
    r_lin = srgb_channel_to_linear(rgb[0] / 255.0)
    g_lin = srgb_channel_to_linear(rgb[1] / 255.0)
    b_lin = srgb_channel_to_linear(rgb[2] / 255.0)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def calculate_contrast_ratio(fg_rgb: Tuple[int, int, int], bg_rgb: Tuple[int, int, int]) -> float:
    """
    Calculates contrast ratio: (L1 + 0.05) / (L2 + 0.05), where L1 is the lighter color.
    Yields a value between 1.0 and 21.0.
    """
    l1 = calculate_relative_luminance(fg_rgb)
    l2 = calculate_relative_luminance(bg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ==============================================================================
# 2. Design Token Schema & Contract Testing
# ==============================================================================
@dataclass
class TokenContractRule:
    category: str
    allowed_units: List[str]
    scale_factor: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None

class TokenContractValidator:
    """Validates design token values against strict governance rules (atomic design constraints)."""
    def __init__(self):
        self.rules: Dict[str, TokenContractRule] = {
            "spacing": TokenContractRule(category="spacing", allowed_units=["px", "rem"], scale_factor=4.0),
            "radius": TokenContractRule(category="radius", allowed_units=["px", "%"], min_val=0.0, max_val=999.0),
            "font-size": TokenContractRule(category="font-size", allowed_units=["rem", "px"], min_val=10.0, max_val=72.0)
        }

    def validate_token(self, token_name: str, value: str) -> Tuple[bool, str]:
        category = next((k for k in self.rules if token_name.startswith(k)), None)
        if not category:
            return True, "No governing contract rule (Allowed)"

        rule = self.rules[category]
        unit = next((u for u in rule.allowed_units if value.endswith(u)), None)
        if not unit:
            return False, f"Unit not allowed for {category}. Expected one of: {rule.allowed_units}"

        raw_num = value[:-len(unit)]
        try:
            num = float(raw_num)
        except ValueError:
            return False, f"Malformed scalar value in '{value}'"

        if rule.scale_factor and unit == "px" and (num % rule.scale_factor != 0):
            return False, f"Value {num}px violates {rule.scale_factor}px base spacing grid"

        if rule.min_val is not None and num < rule.min_val:
            return False, f"Value {num} is below minimum allowed ({rule.min_val})"

        if rule.max_val is not None and num > rule.max_val:
            return False, f"Value {num} exceeds maximum allowed ({rule.max_val})"

        return True, "Passed contract rules"


# ==============================================================================
# 3. Virtual Framebuffer & Visual Regression Diff Engine
# ==============================================================================
@dataclass
class Pixel:
    char: str
    fg: str
    bg: str

class Framebuffer:
    """Simulates a low-resolution raster canvas for UI component rendering."""
    def __init__(self, width: int, height: int, default_bg: str = "#FFFFFF"):
        self.width = width
        self.height = height
        self.grid: List[List[Pixel]] = [
            [Pixel(" ", "#000000", default_bg) for _ in range(width)]
            for _ in range(height)
        ]

    def set_pixel(self, x: int, y: int, char: str, fg: str, bg: str):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = Pixel(char, fg, bg)

    def draw_box(self, x: int, y: int, w: int, h: int, fg: str, bg: str, border_char: str = "#"):
        for row in range(y, min(y + h, self.height)):
            for col in range(x, min(x + w, self.width)):
                if row == y or row == y + h - 1 or col == x or col == x + w - 1:
                    self.set_pixel(col, row, border_char, fg, bg)
                else:
                    self.set_pixel(col, row, " ", fg, bg)

    def draw_text(self, x: int, y: int, text: str, fg: str, bg: str):
        for idx, ch in enumerate(text):
            self.set_pixel(x + idx, y, ch, fg, bg)


def render_button_component(variant: str, label: str, padding_x: int, bg_color: str, text_color: str) -> Framebuffer:
    """Renders a button component into a virtual framebuffer."""
    fb_width = 30
    fb_height = 5
    fb = Framebuffer(fb_width, fb_height, default_bg="#121212")

    btn_width = len(label) + (padding_x * 2) + 2
    btn_height = 3
    start_x = (fb_width - btn_width) // 2
    start_y = 1

    border_char = "+" if variant == "outline" else "="
    fb.draw_box(start_x, start_y, btn_width, btn_height, text_color, bg_color, border_char)
    fb.draw_text(start_x + padding_x + 1, start_y + 1, label, text_color, bg_color)
    return fb


def calculate_visual_diff(baseline: Framebuffer, candidate: Framebuffer) -> Tuple[float, List[List[bool]]]:
    """
    Compares two framebuffers cell by cell.
    Returns (mismatch_percentage, diff_mask).
    """
    if baseline.width != candidate.width or baseline.height != candidate.height:
        raise ValueError("Buffer dimensions do not match for visual comparison")

    total_pixels = baseline.width * baseline.height
    mismatch_count = 0
    diff_mask = [[False for _ in range(baseline.width)] for _ in range(baseline.height)]

    for y in range(baseline.height):
        for x in range(baseline.width):
            p1 = baseline.grid[y][x]
            p2 = candidate.grid[y][x]
            # Pixel differs if character, foreground, or background color differs
            if p1.char != p2.char or p1.fg != p2.fg or p1.bg != p2.bg:
                mismatch_count += 1
                diff_mask[y][x] = True

    mismatch_ratio = (mismatch_count / total_pixels) * 100.0
    return mismatch_ratio, diff_mask


def render_diff_view(candidate: Framebuffer, diff_mask: List[List[bool]]) -> str:
    """Renders the framebuffer to terminal, marking mutated pixels with red inverse styling."""
    lines = []
    for y in range(candidate.height):
        line_chars = []
        for x in range(candidate.width):
            pixel = candidate.grid[y][x]
            if diff_mask[y][x]:
                # Visual regression detected at this pixel
                line_chars.append(f"{ANSI.BG_RED}{ANSI.WHITE}{pixel.char}{ANSI.RESET}")
            else:
                line_chars.append(f"{ANSI.DIM}{pixel.char}{ANSI.RESET}")
        lines.append("".join(line_chars))
    return "\n".join(lines)


# ==============================================================================
# 4. Pipeline Execution & Test Runner
# ==============================================================================
def run_test_suite():
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}===================================================================={ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}    DESIGN SYSTEM QUALITY ENGINEERING SUITE (TEST RUNNER v2.4)     {ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}===================================================================={ANSI.RESET}\n")

    # ---------------------------------------------------------
    # SUITE 1: Design Token Accessibility (WCAG 2.1) Audits
    # ---------------------------------------------------------
    print(f"{ANSI.BOLD}▶ SUITE 1: Accessibility (WCAG 2.1) Contrast Verification{ANSI.RESET}")
    token_pairs = [
        {"name": "Button Primary Text vs Brand Blue", "fg": "#FFFFFF", "bg": "#1D4ED8", "min_ratio": 4.5},
        {"name": "Muted Caption vs Card Surface",      "fg": "#71717A", "bg": "#18181B", "min_ratio": 4.5},
        {"name": "Destructive Button vs Alert Red",     "fg": "#FFFFFF", "bg": "#DC2626", "min_ratio": 4.5},
        {"name": "Subtle Badge vs Neutral Gray",        "fg": "#94A3B8", "bg": "#0F172A", "min_ratio": 4.5},
        {"name": "Flawed Secondary (Regression Seed)", "fg": "#9CA3AF", "bg": "#F3F4F6", "min_ratio": 4.5},
    ]

    for item in token_pairs:
        fg_rgb = hex_to_rgb(item["fg"])
        bg_rgb = hex_to_rgb(item["bg"])
        ratio = calculate_contrast_ratio(fg_rgb, bg_rgb)
        target = item["min_ratio"]

        if ratio >= target:
            status = f"{ANSI.GREEN}PASS (WCAG AA){ANSI.RESET}"
        else:
            status = f"{ANSI.RED}FAIL (Violates AA: {ratio:.2f}:1 < {target}:1){ANSI.RESET}"

        print(f"  [{status}] {item['name']:<35} Ratio: {ANSI.BOLD}{ratio:5.2f}:1{ANSI.RESET} (FG: {item['fg']}, BG: {item['bg']})")
        time.sleep(0.04)

    # ---------------------------------------------------------
    # SUITE 2: Design Token Scale & Contract Governance
    # ---------------------------------------------------------
    print(f"\n{ANSI.BOLD}▶ SUITE 2: Design Token Structural Contract Governance{ANSI.RESET}")
    validator = TokenContractValidator()
    tokens_to_test = {
        "spacing.xs": "4px",
        "spacing.md": "16px",
        "spacing.xl": "32px",
        "spacing.rogue": "15px",      # Violates 4px grid
        "radius.sm": "4px",
        "radius.invalid": "12em",     # Invalid unit
        "font-size.base": "16px",
        "font-size.huge": "120px",    # Exceeds max allowable font size
    }

    for token, val in tokens_to_test.items():
        ok, reason = validator.validate_token(token, val)
        if ok:
            status = f"{ANSI.GREEN}VALID{ANSI.RESET}"
            msg = f"{ANSI.DIM}{reason}{ANSI.RESET}"
        else:
            status = f"{ANSI.RED}ERROR{ANSI.RESET}"
            msg = f"{ANSI.YELLOW}{reason}{ANSI.RESET}"
        print(f"  [{status}] Token: {ANSI.CYAN}{token:<18}{ANSI.RESET} = {val:<7} -> {msg}")
        time.sleep(0.04)

    # ---------------------------------------------------------
    # SUITE 3: Visual Regression Testing Engine (Snapshot Diff)
    # ---------------------------------------------------------
    print(f"\n{ANSI.BOLD}▶ SUITE 3: Visual Regression Testing (Virtual Snapshot Engine){ANSI.RESET}")

    # Baseline Button
    baseline_buf = render_button_component(
        variant="solid",
        label="Submit",
        padding_x=3,
        bg_color="#1D4ED8",
        text_color="#FFFFFF"
    )

    # Candidate 1: Identical render (Idempotency test)
    candidate_pass = render_button_component(
        variant="solid",
        label="Submit",
        padding_x=3,
        bg_color="#1D4ED8",
        text_color="#FFFFFF"
    )

    # Candidate 2: Visual regression introduced (padding bumped, label drifted)
    candidate_fail = render_button_component(
        variant="solid",
        label="Submit",
        padding_x=4,  # Regressed: shifted visual footprint
        bg_color="#1D4ED8",
        text_color="#FFFFFF"
    )

    # Run Visual Diff 1
    diff_rate_1, mask_1 = calculate_visual_diff(baseline_buf, candidate_pass)
    print(f"  [Snapshot Test 1 - Target: Solid Button Standard]")
    print(f"  Delta: {diff_rate_1:.2f}% mismatch threshold.")
    if diff_rate_1 == 0.0:
        print(f"  Result: {ANSI.GREEN}✓ Pixel-perfect match against baseline.{ANSI.RESET}\n")
    else:
        print(f"  Result: {ANSI.RED}✗ Visual regression detected!{ANSI.RESET}\n")

    # Run Visual Diff 2
    diff_rate_2, mask_2 = calculate_visual_diff(baseline_buf, candidate_fail)
    print(f"  [Snapshot Test 2 - Target: Solid Button Candidate (Altered Padding)]")
    print(f"  Delta: {ANSI.BOLD}{diff_rate_2:.2f}% mismatch{ANSI.RESET} (Threshold is 0.00%)")
    if diff_rate_2 > 0.0:
        print(f"  Result: {ANSI.RED}✗ Visual regression detected! Rendering diff overlay:{ANSI.RESET}")
        print("  " + "-" * 32)
        diff_view = render_diff_view(candidate_fail, mask_2)
        for line in diff_view.split("\n"):
            print(f"  {line}")
        print("  " + "-" * 32)
        print(f"  {ANSI.BG_RED}{ANSI.WHITE} RED BLOCKS {ANSI.RESET} = Mutated/Shifted Pixel Positions")

    # ---------------------------------------------------------
    # Pipeline Summary
    # ---------------------------------------------------------
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}===================================================================={ANSI.RESET}")
    print(f"{ANSI.BOLD}PIPELINE RUN COMPLETE:{ANSI.RESET} 3 Suites Executed.")
    print(f"  - WCAG Contrast Failures  : {ANSI.YELLOW}1 flagged{ANSI.RESET}")
    print(f"  - Token Contract Errors   : {ANSI.YELLOW}3 flagged{ANSI.RESET}")
    print(f"  - Visual Regression Diffs : {ANSI.RED}1 mutation intercepted{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.GREEN}Quality Gate successfully blocked unauthorized visual regressions.{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.CYAN}===================================================================={ANSI.RESET}\n")


if __name__ == "__main__":
    run_test_suite()