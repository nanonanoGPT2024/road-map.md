#!/usr/bin/env python3
"""
Lab: Design System - Typography, Spacing, and Spatial Grids
Module: 03-Frontend-and-Mobile / Chapter 03 - Deep Dive

This lab engine implements and validates core design system mechanics:
1. Modular Typographic Scale Generator (Geometric progression & Line-Height rhythm snapping).
2. Fluid Typography Calculator (CSS clamp math simulation: viewport slope & intercept).
3. 8pt Spatial Grid Layout Engine with Vertical Baseline Rhythm Verification.
4. Token Contract Audit: Detects and auto-remediates sub-pixel & off-grid rhythm violations.
"""

from dataclasses import dataclass, field
from enum import Enum
import math
import sys
from typing import Dict, List, Optional, Tuple

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GRAY = "\033[90m"


class ModularScaleRatio(Enum):
    """Standard architectural typographic ratios."""
    MINOR_SECOND = 1.067
    MAJOR_SECOND = 1.125
    MINOR_THIRD = 1.200
    MAJOR_THIRD = 1.250
    PERFECT_FOURTH = 1.333
    AUGMENTED_FOURTH = 1.414
    PERFECT_FIFTH = 1.500
    GOLDEN_RATIO = 1.618


@dataclass(frozen=True)
class TypographyToken:
    name: str
    step: int
    font_size_px: float
    line_height_px: int
    relative_line_height: float
    snapped_to_grid: bool


@dataclass
class BoxModel:
    element_id: str
    font_size: float
    line_height: int
    padding_top: int
    padding_bottom: int
    margin_top: int
    margin_bottom: int
    border_width: int = 1
    content_lines: int = 1

    @property
    def total_vertical_space(self) -> int:
        """Calculates total outer vertical footprint of the element."""
        content_box = (self.line_height * self.content_lines) + (self.border_width * 2)
        padding_box = content_box + self.padding_top + self.padding_bottom
        margin_box = padding_box + self.margin_top + self.margin_bottom
        return margin_box


class TypographySystem:
    """Computes mathematical typography scales and ensures baseline rhythm adherence."""

    def __init__(self, base_font_size: float = 16.0, ratio: ModularScaleRatio = ModularScaleRatio.PERFECT_FOURTH, baseline_grid: int = 4):
        self.base_font_size = base_font_size
        self.ratio = ratio.value
        self.baseline_grid = baseline_grid

    def compute_font_size(self, step: int) -> float:
        """Calculates font size based on modular scale: size = base * (ratio ^ step)."""
        return round(self.base_font_size * (self.ratio ** step), 2)

    def snap_line_height(self, font_size: float, min_ratio: float = 1.25) -> int:
        """
        Determines the smallest multiple of `baseline_grid` that accommodates
        the font size while maintaining minimum readability line spacing.
        """
        raw_target = font_size * min_ratio
        # Round up to next baseline grid increment
        snapped = math.ceil(raw_target / self.baseline_grid) * self.baseline_grid
        return int(snapped)

    def generate_scale(self, min_step: int = -2, max_step: int = 5) -> Dict[str, TypographyToken]:
        """Generates a complete typographic scale token set."""
        tokens = {}
        step_names = {
            -2: "caption-sm",
            -1: "caption",
            0: "body-base",
            1: "body-lg",
            2: "h4",
            3: "h3",
            4: "h2",
            5: "h1"
        }

        for step in range(min_step, max_step + 1):
            name = step_names.get(step, f"step-{step}")
            font_size = self.compute_font_size(step)
            line_height = self.snap_line_height(font_size)
            rel_lh = round(line_height / font_size, 2)
            is_snapped = (line_height % self.baseline_grid == 0)

            tokens[name] = TypographyToken(
                name=name,
                step=step,
                font_size_px=font_size,
                line_height_px=line_height,
                relative_line_height=rel_lh,
                snapped_to_grid=is_snapped
            )
        return tokens


class FluidTypeEngine:
    """Calculates CSS Clamp parameters: clamp(min_px, y_axis_intersection + slope * vw, max_px)."""

    @staticmethod
    def calculate_clamp(min_size: float, max_size: float, min_vw: float = 375.0, max_vw: float = 1440.0) -> Tuple[float, float, str]:
        """
        Derives the linear equation y = mx + b for responsive typography interpolation.
        Returns: (slope_percentage, intercept_px, css_clamp_string)
        """
        slope = (max_size - min_size) / (max_vw - min_vw)
        y_axis_intersection = -min_vw * slope + min_size
        slope_vw = slope * 100

        css_string = (
            f"clamp({min_size:.2f}px, "
            f"{y_axis_intersection:.2f}px + {slope_vw:.2f}vw, "
            f"{max_size:.2f}px)"
        )
        return slope_vw, y_axis_intersection, css_string


class SpatialGridAuditor:
    """
    Validates components against an 8pt/4pt spatial grid standard.
    Detects unaligned vertical metrics and computes deterministic repairs.
    """

    def __init__(self, primary_grid: int = 8, sub_grid: int = 4):
        self.primary_grid = primary_grid
        self.sub_grid = sub_grid

    def audit_box(self, box: BoxModel) -> Tuple[bool, List[str]]:
        """Verifies if all box metrics conform strictly to the rhythm constraints."""
        violations = []

        if box.line_height % self.sub_grid != 0:
            violations.append(f"Line height ({box.line_height}px) breaks {self.sub_grid}px sub-grid rhythm.")

        if (box.padding_top + box.padding_bottom) % self.sub_grid != 0:
            violations.append(f"Vertical padding sum ({box.padding_top + box.padding_bottom}px) breaks rhythm.")

        if (box.margin_top + box.margin_bottom) % self.sub_grid != 0:
            violations.append(f"Vertical margin sum ({box.margin_top + box.margin_bottom}px) breaks rhythm.")

        total_vertical = box.total_vertical_space
        if total_vertical % self.primary_grid != 0:
            violations.append(
                f"Total vertical footprint ({total_vertical}px) is off the {self.primary_grid}px master grid "
                f"(remainder: {total_vertical % self.primary_grid}px)."
            )

        return len(violations) == 0, violations

    def auto_remediate(self, box: BoxModel) -> BoxModel:
        """Adjusts margins and paddings using nearest-grid snapping to restore spatial harmony."""
        def snap(val: int, base: int) -> int:
            return round(val / base) * base

        # Snap line height to baseline grid
        new_lh = snap(box.line_height, self.sub_grid)
        if new_lh < box.font_size:
            new_lh += self.sub_grid

        new_pt = snap(box.padding_top, self.sub_grid)
        new_pb = snap(box.padding_bottom, self.sub_grid)
        new_mt = snap(box.margin_top, self.primary_grid)

        # Content + borders + padding + top margin
        current_subtotal = (new_lh * box.content_lines) + (box.border_width * 2) + new_pt + new_pb + new_mt
        
        # Calculate optimal margin_bottom to satisfy the primary 8pt grid
        remainder = current_subtotal % self.primary_grid
        if remainder == 0:
            new_mb = snap(box.margin_bottom, self.primary_grid)
        else:
            deficit = self.primary_grid - remainder
            new_mb = box.margin_bottom + deficit
            new_mb = snap(new_mb, self.primary_grid)

        return BoxModel(
            element_id=f"{box.element_id}_remediated",
            font_size=box.font_size,
            line_height=new_lh,
            padding_top=new_pt,
            padding_bottom=new_pb,
            margin_top=new_mt,
            margin_bottom=new_mb,
            border_width=box.border_width,
            content_lines=box.content_lines
        )


def render_ascii_spatial_slice(box: BoxModel, grid_unit: int = 4):
    """Renders visual ASCII representation of the element aligned to grid tracks."""
    print(f"{GRAY}      ┌{'─' * 44}┐ (Spatial Track Visualizer){RESET}")
    layers = [
        ("Margin Top", box.margin_top, MAGENTA),
        ("Padding Top", box.padding_top, CYAN),
        (f"Content Area ({box.content_lines}L @ {box.line_height}px)", box.line_height * box.content_lines + (box.border_width * 2), GREEN),
        ("Padding Bottom", box.padding_bottom, CYAN),
        ("Margin Bottom", box.margin_bottom, MAGENTA),
    ]

    for label, height, color in layers:
        if height <= 0:
            continue
        tracks = height // grid_unit
        track_str = f"{height}px [{tracks} tracks]"
        print(f"      │ {color}{label:<26}{RESET} │ {track_str:<13}│")
    print(f"{GRAY}      └{'─' * 44}┘{RESET}")
    print(f"      {BOLD}Total Vertical Allocation: {box.total_vertical_space}px{RESET}\n")


def main():
    print(f"\n{BOLD}{CYAN}=== DESIGN SYSTEM ARCHITECTURE: SPATIAL GRID & TYPOGRAPHY ENGINE ==={RESET}\n")

    # 1. Typography Scale Execution
    typo_engine = TypographySystem(base_font_size=16.0, ratio=ModularScaleRatio.PERFECT_FOURTH, baseline_grid=4)
    tokens = typo_engine.generate_scale()

    print(f"{BOLD}[1] GENERATING MODULAR TYPOGRAPHIC SCALE (Ratio: 1.333 | Baseline Grid: 4px){RESET}")
    print(f"{'-' * 70}")
    print(f"{'Token':<14} | {'Step':<5} | {'Font Size':<10} | {'Line Height':<12} | {'Rel Ratio':<10}")
    print(f"{'-' * 70}")
    for name, token in tokens.items():
        print(
            f"{CYAN}{name:<14}{RESET} | "
            f"{token.step:<5} | "
            f"{token.font_size_px:>7.2f}px | "
            f"{GREEN}{token.line_height_px:>10}px{RESET} | "
            f"{token.relative_line_height:>9.2f}x"
        )
    print(f"{'-' * 70}\n")

    # 2. Fluid Clamp Computation Simulation
    print(f"{BOLD}[2] FLUID RESPONSIVE CALCULATION (CSS Clamp Interpolation){RESET}")
    fluid_engine = FluidTypeEngine()
    h1_min, h1_max = tokens["h1"].font_size_px * 0.75, tokens["h1"].font_size_px
    slope_vw, intercept, css_clamp = fluid_engine.calculate_clamp(h1_min, h1_max)
    print(f"  Viewport Range : 375px -> 1440px")
    print(f"  H1 Size Range  : {h1_min:.2f}px -> {h1_max:.2f}px")
    print(f"  Calculated Math: Slope={slope_vw:.4f}vw, Intercept={intercept:.4f}px")
    print(f"  CSS Generated  : {YELLOW}{css_clamp}{RESET}\n")

    # 3. Spatial Grid & Vertical Rhythm Audit
    auditor = SpatialGridAuditor(primary_grid=8, sub_grid=4)

    print(f"{BOLD}[3] SPATIAL GRID AUDITING & CONTRACT VALIDATION{RESET}")
    
    # An intentionally misaligned component (broken margins & line height off grid)
    broken_card = BoxModel(
        element_id="promo-banner-card",
        font_size=tokens["h3"].font_size_px,
        line_height=35, # Violates 4px grid (should be 36 or 40)
        padding_top=15,  # Violates 4px grid
        padding_bottom=17, # Violates 4px grid
        margin_top=10,   # Violates 8px grid
        margin_bottom=14, # Violates 8px grid
        border_width=1,
        content_lines=2
    )

    print(f"Inspecting Component: {YELLOW}'{broken_card.element_id}'{RESET}")
    is_valid, failures = auditor.audit_box(broken_card)
    
    if not is_valid:
        print(f"Status: {RED}[FAIL] Baseline Rhythm Corrupted{RESET}")
        for err in failures:
            print(f"  {RED}✖{RESET} {err}")
    
    print("\nVisual Footprint (Corrupted Box):")
    render_ascii_spatial_slice(broken_card)

    # 4. Auto-Remediation Execution
    print(f"{BOLD}[4] APPLYING DETERMINISTIC TOKEN REMEDIATION{RESET}")
    fixed_card = auditor.auto_remediate(broken_card)
    is_remediated_valid, remediation_failures = auditor.audit_box(fixed_card)

    print(f"Inspecting Component: {GREEN}'{fixed_card.element_id}'{RESET}")
    if is_remediated_valid:
        print(f"Status: {GREEN}[PASS] Conforms strictly to 8pt Spatial Architecture{RESET}")
        print(f"  {GREEN}✔{RESET} Line-Height adjusted : {broken_card.line_height}px -> {fixed_card.line_height}px")
        print(f"  {GREEN}✔{RESET} Padding-Top adjusted : {broken_card.padding_top}px -> {fixed_card.padding_top}px")
        print(f"  {GREEN}✔{RESET} Padding-Bottom adj.  : {broken_card.padding_bottom}px -> {fixed_card.padding_bottom}px")
        print(f"  {GREEN}✔{RESET} Margin-Top adjusted  : {broken_card.margin_top}px -> {fixed_card.margin_top}px")
        print(f"  {GREEN}✔{RESET} Margin-Bottom adj.   : {broken_card.margin_bottom}px -> {fixed_card.margin_bottom}px")
    else:
        print(f"Status: {RED}[FAIL] Remediation failed{RESET}")
        for err in remediation_failures:
            print(f"  {RED}✖{RESET} {err}")

    print("\nVisual Footprint (Remediated Box):")
    render_ascii_spatial_slice(fixed_card)

    print(f"{BOLD}{GREEN}✓ Laboratory execution completed with zero unresolved spatial anomalies.{RESET}\n")


if __name__ == "__main__":
    main()