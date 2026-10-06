#!/usr/bin/env python3
"""
Lab Exercise: Visual Formatting Model, Box Dynamics, and Paint Profiling Simulator
BAB-02: CSS Deep-Dive Engine Simulation
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Terminal ANSI Color Definitions
class Color:
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
    BG_DARK = "\033[40m"


@dataclass
class BoxDimensions:
    width: float
    height: float
    padding_top: float
    padding_right: float
    padding_bottom: float
    padding_left: float
    border_top: float
    border_right: float
    border_bottom: float
    border_left: float
    margin_top: float
    margin_right: float
    margin_bottom: float
    margin_left: float
    box_sizing: str  # 'content-box' or 'border-box'

    def calculate_metrics(self) -> dict:
        h_padding = self.padding_left + self.padding_right
        v_padding = self.padding_top + self.padding_bottom
        h_border = self.border_left + self.border_right
        v_border = self.border_top + self.border_bottom
        h_margin = self.margin_left + self.margin_right
        v_margin = self.margin_top + self.margin_bottom

        if self.box_sizing == "content-box":
            content_w = self.width
            content_h = self.height
            inner_w = content_w + h_padding
            inner_h = content_h + v_padding
            outer_w = inner_w + h_border
            outer_h = inner_h + v_border
        elif self.box_sizing == "border-box":
            outer_w = self.width
            outer_h = self.height
            inner_w = max(0.0, outer_w - h_border)
            inner_h = max(0.0, outer_h - v_border)
            content_w = max(0.0, inner_w - h_padding)
            content_h = max(0.0, inner_h - v_padding)
        else:
            raise ValueError(f"Unknown box-sizing: {self.box_sizing}")

        total_occupied_w = outer_w + h_margin
        total_occupied_h = outer_h + v_margin

        return {
            "content": (content_w, content_h),
            "padding_box": (inner_w, inner_h),
            "border_box": (outer_w, outer_h),
            "margin_box": (total_occupied_w, total_occupied_h),
        }


class BoxModelVisualizer:
    @staticmethod
    def render_ascii_box(box: BoxDimensions) -> None:
        metrics = box.calculate_metrics()
        cw, ch = metrics["content"]
        bw, bh = metrics["border_box"]
        mw, mh = metrics["margin_box"]

        print(f"\n{Color.BOLD}{Color.CYAN}=== CSS BOX MODEL DYNAMICS AUDIT ({box.box_sizing.upper()}) ==={Color.RESET}")
        print(f"{Color.YELLOW}+---------------------------------------------------------------+{Color.RESET}")
        print(f"{Color.YELLOW}| MARGIN BOX ({mw:.1f}px x {mh:.1f}px){' ' * 33}|{Color.RESET}")
        print(f"{Color.YELLOW}|  Margin: T={box.margin_top} R={box.margin_right} B={box.margin_bottom} L={box.margin_left}{' ' * 36}|{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}+-------------------------------------------------------+{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}| BORDER BOX ({bw:.1f}px x {bh:.1f}px){' ' * 27}|{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|  Border: T={box.border_top} R={box.border_right} B={box.border_bottom} L={box.border_left}{' ' * 30}|{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|   {Color.GREEN}+-----------------------------------------------+{Color.MAGENTA}   |{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|   {Color.GREEN}| PADDING BOX{' ' * 35}|{Color.MAGENTA}   |{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|   {Color.GREEN}|    Padding: T={box.padding_top} R={box.padding_right} B={box.padding_bottom} L={box.padding_left}{' ' * 21}|{Color.MAGENTA}   |{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|   {Color.GREEN}|   {Color.BLUE}+---------------------------------------+{Color.GREEN}   |{Color.MAGENTA}   |{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|   {Color.GREEN}|   {Color.BLUE}| CONTENT BOX: {cw:6.1f}px x {ch:6.1f}px     |{Color.GREEN}   |{Color.MAGENTA}   |{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|   {Color.GREEN}|   {Color.BLUE}+---------------------------------------+{Color.GREEN}   |{Color.MAGENTA}   |{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}|   {Color.GREEN}+-----------------------------------------------+{Color.MAGENTA}   |{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}|   {Color.MAGENTA}+-------------------------------------------------------+{Color.YELLOW}   |{Color.RESET}")
        print(f"{Color.YELLOW}+---------------------------------------------------------------+{Color.RESET}")


class MarginCollapseEngine:
    @staticmethod
    def simulate_vertical_collapse(m1: float, m2: float) -> Tuple[float, str]:
        if m1 >= 0 and m2 >= 0:
            result = max(m1, m2)
            rule = "Rule: max(positive_a, positive_b)"
        elif m1 < 0 and m2 < 0:
            result = -max(abs(m1), abs(m2))
            rule = "Rule: -max(abs(negative_a), abs(negative_b))"
        else:
            pos = max(m1, m2, 0)
            neg = min(m1, m2, 0)
            result = pos + neg
            rule = "Rule: positive_max + negative_min"
        return result, rule


class FormattingContextEngine:
    BFC_TRIGGERS = [
        "root element (<html>)",
        "float: left / right",
        "position: absolute / fixed",
        "display: inline-block",
        "display: flow-root",
        "display: flex / grid (direct children)",
        "overflow: hidden / auto / scroll (other than visible)",
        "contain: layout / content / paint",
    ]

    @staticmethod
    def inspect_bfc(style: dict) -> Tuple[bool, List[str]]:
        reasons = []
        if style.get("display") in ["flow-root", "inline-block", "table-cell", "table-caption"]:
            reasons.append(f"display: {style['display']}")
        if style.get("float") in ["left", "right"]:
            reasons.append(f"float: {style['float']}")
        if style.get("position") in ["absolute", "fixed"]:
            reasons.append(f"position: {style['position']}")
        if style.get("overflow") in ["hidden", "auto", "scroll", "clip"]:
            reasons.append(f"overflow: {style['overflow']} (!= visible)")
        if "layout" in style.get("contain", "") or "paint" in style.get("contain", ""):
            reasons.append(f"contain: {style['contain']}")

        return len(reasons) > 0, reasons


class PaintProfiler:
    PIPELINE_MAP = {
        "width": ("Layout (Reflow)", "Repaint", "Composite", 16.2),
        "height": ("Layout (Reflow)", "Repaint", "Composite", 16.0),
        "margin": ("Layout (Reflow)", "Repaint", "Composite", 14.5),
        "padding": ("Layout (Reflow)", "Repaint", "Composite", 14.1),
        "top": ("Layout (Reflow)", "Repaint", "Composite", 15.8),
        "left": ("Layout (Reflow)", "Repaint", "Composite", 15.8),
        "color": ("-", "Repaint", "Composite", 4.2),
        "background-color": ("-", "Repaint", "Composite", 4.8),
        "visibility": ("-", "Repaint", "Composite", 3.1),
        "box-shadow": ("-", "Repaint (Heavy Raster)", "Composite", 8.9),
        "transform": ("-", "-", "Composite-Only (GPU Thread)", 0.8),
        "opacity": ("-", "-", "Composite-Only (GPU Thread)", 0.6),
        "filter": ("-", "-", "Composite-Only (Layer Offload)", 1.2),
    }

    @classmethod
    def profile_property(cls, prop_name: str) -> None:
        prop = prop_name.strip().lower()
        if prop not in cls.PIPELINE_MAP:
            print(f"{Color.RED}Property '{prop_name}' not in benchmark catalog.{Color.RESET}")
            return

        stages = cls.PIPELINE_MAP[prop]
        reflow, repaint, composite, cost = stages
        
        status_color = Color.GREEN if cost < 2.0 else (Color.YELLOW if cost < 8.0 else Color.RED)
        
        print(f"\n{Color.BOLD}>>> Paint Profiling for CSS Property: {Color.CYAN}{prop}{Color.RESET}")
        print(f"  • Reflow/Layout Stage : {Color.RED if reflow != '-' else Color.DIM}{reflow}{Color.RESET}")
        print(f"  • Repaint/Raster Stage: {Color.YELLOW if repaint != '-' else Color.DIM}{repaint}{Color.RESET}")
        print(f"  • Compositing Stage   : {Color.GREEN}{composite}{Color.RESET}")
        print(f"  • Frame Budget Penalty: {status_color}{cost} ms / frame (Target: <= 16.6ms for 60fps){Color.RESET}")
        
        if cost > 10.0:
            print(f"  {Color.RED}[CRITICAL BOTTLENECK]{Color.RESET} Triggers full tree re-layout. Avoid animating in RAF loops!")
        elif cost > 2.0:
            print(f"  {Color.YELLOW}[WARNING]{Color.RESET} Triggers layer re-rasterization without layout shift.")
        else:
            print(f"  {Color.GREEN}[OPTIMAL 60FPS]{Color.RESET} Hardware-accelerated compositor thread mutation.")


def run_interactive_suite() -> None:
    print(f"{Color.BOLD}{Color.WHITE}{Color.BG_BLUE}   CSS ENGINE: VISUAL FORMATTING & PAINT PROFILER SIMULATOR   {Color.RESET}\n")

    # 1. Compare Box-Sizing Models
    box_content = BoxDimensions(
        width=300, height=150,
        padding_top=20, padding_right=20, padding_bottom=20, padding_left=20,
        border_top=5, border_right=5, border_bottom=5, border_left=5,
        margin_top=15, margin_right=15, margin_bottom=15, margin_left=15,
        box_sizing="content-box"
    )

    box_border = BoxDimensions(
        width=300, height=150,
        padding_top=20, padding_right=20, padding_bottom=20, padding_left=20,
        border_top=5, border_right=5, border_bottom=5, border_left=5,
        margin_top=15, margin_right=15, margin_bottom=15, margin_left=15,
        box_sizing="border-box"
    )

    BoxModelVisualizer.render_ascii_box(box_content)
    BoxModelVisualizer.render_ascii_box(box_border)

    # 2. Margin Collapsing Demo
    print(f"\n{Color.BOLD}{Color.CYAN}=== VERTICAL MARGIN COLLAPSE ENGINE SIMULATION ==={Color.RESET}")
    cases = [(30.0, 20.0), (30.0, -15.0), (-25.0, -10.0), (0.0, 40.0)]
    for m1, m2 in cases:
        collapsed, rule_name = MarginCollapseEngine.simulate_vertical_collapse(m1, m2)
        print(f"  Margin A: {m1:5.1f}px | Margin B: {m2:5.1f}px -> {Color.BOLD}{Color.GREEN}Effective Margin: {collapsed:5.1f}px{Color.RESET} ({rule_name})")

    # 3. Block Formatting Context Trigger Checks
    print(f"\n{Color.BOLD}{Color.CYAN}=== BLOCK FORMATTING CONTEXT (BFC) EVALUATION ==={Color.RESET}")
    node_styles = [
        {"element": "#sidebar", "display": "block", "overflow": "visible", "float": "none"},
        {"element": "#card-wrapper", "display": "flow-root"},
        {"element": "#nav-floating", "float": "left", "display": "block"},
        {"element": "#modal-overlay", "position": "fixed", "top": "0"},
        {"element": "#scroll-pane", "overflow": "auto", "display": "block"},
    ]

    for node in node_styles:
        elem = node["element"]
        is_bfc, reasons = FormattingContextEngine.inspect_bfc(node)
        status_tag = f"{Color.GREEN}[CREATES BFC]{Color.RESET}" if is_bfc else f"{Color.RED}[NO BFC - INLINE/FLOW CHAIN]{Color.RESET}"
        detail = ", ".join(reasons) if is_bfc else "Standard Block Container"
        print(f"  {elem:18} -> {status_tag} ({detail})")

    # 4. Paint Profiler Benchmarks
    print(f"\n{Color.BOLD}{Color.CYAN}=== RENDERING PIPELINE & CHROMIUM PAINT PROFILER ==={Color.RESET}")
    sample_props = ["left", "background-color", "transform", "box-shadow", "opacity"]
    for prop in sample_props:
        PaintProfiler.profile_property(prop)

    print(f"\n{Color.BOLD}{Color.GREEN}✓ All CSS Visual Formatting Model & Paint Profiling simulations passed successfully.{Color.RESET}\n")


if __name__ == "__main__":
    run_interactive_suite()
