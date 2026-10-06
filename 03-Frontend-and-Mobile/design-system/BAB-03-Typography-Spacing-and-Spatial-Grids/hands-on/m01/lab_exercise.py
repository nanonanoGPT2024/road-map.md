#!/usr/bin/env python3
"""
Lab Exercise: Typography, Spacing & Spatial Grids Simulation Engine
Module: 03-Frontend-and-Mobile / Design System / BAB-03

Materi Inti:
1. Modular Scale Typography & Line-Height / Baseline Grid Snapping (4px/8px)
2. 8-Point & 4-Point Spacing Token Generation & Design Token Linter
3. 12-Column Responsive Spatial Grid Simulator & Terminal ASCII Art Renderer
4. Vertical Rhythm Rhythm Validator
"""

import sys
import math
import argparse
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# ANSI Color Codes for Terminal UI
class ANSI:
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
    
    # High-intensity foreground
    FG_HI_BLUE = "\033[94m"
    FG_HI_CYAN = "\033[96m"
    FG_HI_GREEN = "\033[92m"
    FG_HI_YELLOW = "\033[93m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"
    BG_DARK_GRAY = "\033[100m"
    BG_BLACK = "\033[40m"


# ---------------------------------------------------------------------------
# 1. TYPOGRAPHY ENGINE (MODULAR SCALE & BASELINE RHYTHM)
# ---------------------------------------------------------------------------
SCALE_RATIOS = {
    "minor-second": 1.067,
    "major-second": 1.125,
    "minor-third": 1.200,
    "major-third": 1.250,
    "perfect-fourth": 1.333,
    "augmented-fourth": 1.414,
    "perfect-fifth": 1.500,
    "golden-ratio": 1.618,
}

@dataclass
class TypeStep:
    name: str
    step_index: int
    font_size_px: float
    font_size_rem: float
    raw_line_height_px: float
    snapped_line_height_px: int
    vertical_grid_units: int

class TypographyEngine:
    def __init__(self, base_size_px: float = 16.0, ratio_name: str = "perfect-fourth", baseline_grid_px: int = 4):
        self.base_size_px = base_size_px
        self.ratio_name = ratio_name
        self.ratio = SCALE_RATIOS.get(ratio_name, 1.333)
        self.baseline_grid_px = baseline_grid_px

    def snap_to_baseline(self, px_value: float) -> int:
        """Snap a px value upward to the nearest multiple of the baseline grid."""
        return math.ceil(px_value / self.baseline_grid_px) * self.baseline_grid_px

    def generate_scale(self) -> List[TypeStep]:
        steps = [
            ("caption", -1),
            ("body-sm", 0),
            ("body-base", 1),
            ("h4 / subtitle", 2),
            ("h3 / title", 3),
            ("h2 / section", 4),
            ("h1 / display", 5),
            ("hero", 6)
        ]
        results = []
        for name, step_idx in steps:
            font_size = round(self.base_size_px * (self.ratio ** (step_idx - 1)), 2)
            rem = round(font_size / 16.0, 4)
            # Optimal proportional line height: headings ~1.2-1.3, body ~1.5-1.6
            proportional_lh_ratio = 1.55 if step_idx <= 1 else 1.25
            raw_lh = font_size * proportional_lh_ratio
            snapped_lh = self.snap_to_baseline(raw_lh)
            grid_units = snapped_lh // self.baseline_grid_px
            results.append(TypeStep(
                name=name,
                step_index=step_idx,
                font_size_px=font_size,
                font_size_rem=rem,
                raw_line_height_px=round(raw_lh, 2),
                snapped_line_height_px=snapped_lh,
                vertical_grid_units=grid_units
            ))
        return results


# ---------------------------------------------------------------------------
# 2. SPACING SCALE & DESIGN TOKEN LINTER
# ---------------------------------------------------------------------------
@dataclass
class SpacingToken:
    name: str
    px_value: int
    rem_value: float
    grid_units: int
    description: str

class SpacingEngine:
    def __init__(self, base_unit_px: int = 8):
        self.base_unit_px = base_unit_px
        self.tokens: Dict[str, SpacingToken] = self._build_tokens()

    def _build_tokens(self) -> Dict[str, SpacingToken]:
        # Industry standard 8pt/4pt token scale
        token_defs = [
            ("space-0", 0, "Zero reset"),
            ("space-0.5", 2, "Micro optical correction"),
            ("space-1", 4, "Half-step / border adjustment"),
            ("space-2", 8, "Base unit: tight padding/icon gap"),
            ("space-3", 12, "Compact component internal padding"),
            ("space-4", 16, "Standard padding/input internal"),
            ("space-5", 20, "Relaxed component internal"),
            ("space-6", 24, "Medium gap / card layout"),
            ("space-8", 32, "Section gutter / card outer margin"),
            ("space-10", 40, "Comfortable separation"),
            ("space-12", 48, "Large container vertical rhythm"),
            ("space-16", 64, "Hero section gap / display margin"),
            ("space-20", 80, "Page layout delimiter"),
        ]
        result = {}
        for name, px, desc in token_defs:
            result[name] = SpacingToken(
                name=name,
                px_value=px,
                rem_value=px / 16.0,
                grid_units=px // self.base_unit_px,
                description=desc
            )
        return result

    def lint_value(self, px_input: int) -> Tuple[bool, Optional[str], Optional[int]]:
        """Check if an arbitrary pixel value complies with the 8pt or 4pt subgrid."""
        if px_input < 0:
            return False, "Negative values not allowed in spatial tokens", None
        if px_input % 8 == 0:
            return True, "Valid 8-point hard grid token", px_input
        if px_input % 4 == 0:
            return True, "Valid 4-point soft grid sub-step", px_input
        
        # Calculate closest valid snapped values
        nearest_floor = (px_input // 4) * 4
        nearest_ceil = nearest_floor + 4
        closest = nearest_floor if (px_input - nearest_floor) < (nearest_ceil - px_input) else nearest_ceil
        return False, f"Violation! {px_input}px breaks baseline grid (4pt/8pt)", closest


# ---------------------------------------------------------------------------
# 3. SPATIAL GRID & 12-COLUMN LAYOUT ENGINE
# ---------------------------------------------------------------------------
@dataclass
class ColumnLayoutConfig:
    container_width: int
    columns: int
    gutter: int
    margin: int

class SpatialGridEngine:
    def __init__(self, config: ColumnLayoutConfig):
        self.config = config

    def calculate_column_width(self) -> float:
        content_width = self.config.container_width - (2 * self.config.margin)
        total_gutters = (self.config.columns - 1) * self.config.gutter
        available_column_space = content_width - total_gutters
        if available_column_space <= 0:
            raise ValueError("Container width too small for specified margin and gutters.")
        return available_column_space / self.config.columns

    def calculate_span_width(self, span_columns: int) -> float:
        if span_columns < 1 or span_columns > self.config.columns:
            raise ValueError(f"Span must be between 1 and {self.config.columns}")
        col_w = self.calculate_column_width()
        return (span_columns * col_w) + ((span_columns - 1) * self.config.gutter)

    def render_ascii_grid(self, total_terminal_chars: int = 72) -> str:
        """Render visual 12-column bar showing margins, columns, and gutters."""
        col_w = self.calculate_column_width()
        lines = []
        lines.append(f"{ANSI.BOLD}Spatial 12-Column Grid Visualization:{ANSI.RESET}")
        lines.append(f"Container: {self.config.container_width}px | Margins: {self.config.margin}px | "
                     f"Gutters: {self.config.gutter}px | Column: {col_w:.1f}px")
        
        # Scale to terminal characters
        char_scale = total_terminal_chars / self.config.container_width
        margin_chars = max(1, int(self.config.margin * char_scale))
        gutter_chars = max(1, int(self.config.gutter * char_scale))
        col_chars = max(2, int(col_w * char_scale))

        # Top border
        visual_bar = []
        visual_bar.append(f"{ANSI.FG_YELLOW}[M]{ANSI.RESET}")
        for i in range(self.config.columns):
            visual_bar.append(f"{ANSI.FG_HI_BLUE}{'█' * col_chars}{ANSI.RESET}")
            if i < self.config.columns - 1:
                visual_bar.append(f"{ANSI.FG_RED}{'·' * gutter_chars}{ANSI.RESET}")
        visual_bar.append(f"{ANSI.FG_YELLOW}[M]{ANSI.RESET}")

        lines.append("".join(visual_bar))
        lines.append(f"{ANSI.DIM}Legend: {ANSI.FG_YELLOW}[M] Margin{ANSI.RESET} | "
                     f"{ANSI.FG_HI_BLUE}█ Column{ANSI.RESET} | "
                     f"{ANSI.FG_RED}· Gutter{ANSI.RESET}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. INTERACTIVE & RUNNABLE DEMO SUITE
# ---------------------------------------------------------------------------
def banner():
    print(f"\n{ANSI.BG_BLUE}{ANSI.FG_WHITE}{ANSI.BOLD} === DESIGN SYSTEM: TYPOGRAPHY, SPACING & SPATIAL GRIDS === {ANSI.RESET}\n")

def demo_typography():
    print(f"{ANSI.BOLD}{ANSI.FG_CYAN}--- [MODUL 1: TYPOGRAPHY SCALE & BASELINE RHYTHM (4px Lock)] ---{ANSI.RESET}")
    ratio_choice = "perfect-fourth"
    engine = TypographyEngine(base_size_px=16.0, ratio_name=ratio_choice, baseline_grid_px=4)
    scale = engine.generate_scale()

    header = (f"{'Token / Role':<16} | {'Font Size':<10} | {'Rem':<8} | "
              f"{'Raw LH':<10} | {'Snapped LH':<12} | {'4px Grid Units'}")
    print(f"{ANSI.BOLD}{header}{ANSI.RESET}")
    print("-" * len(header))

    for step in scale:
        color = ANSI.FG_HI_GREEN if step.step_index >= 1 else ANSI.FG_HI_CYAN
        row = (f"{color}{step.name:<16}{ANSI.RESET} | "
               f"{step.font_size_px:>7.2f}px | "
               f"{step.font_size_rem:>6.3f}r | "
               f"{step.raw_line_height_px:>8.2f}px | "
               f"{ANSI.BOLD}{step.snapped_line_height_px:>10}px{ANSI.RESET} | "
               f"{step.vertical_grid_units:>8} units")
        print(row)
    print(f"\n{ANSI.DIM}* Baseline rhythm locked to multiples of 4px for crisp sub-pixel pixel alignment.{ANSI.RESET}\n")

def demo_spacing():
    print(f"{ANSI.BOLD}{ANSI.FG_CYAN}--- [MODUL 2: 8-POINT SPACING SYSTEM & TOKEN AUDITOR] ---{ANSI.RESET}")
    spacing_eng = SpacingEngine(base_unit_px=8)
    
    print(f"{ANSI.BOLD}{'Token':<12} | {'Value (px)':<10} | {'Value (rem)':<12} | {'Visual Gauge'}{ANSI.RESET}")
    print("-" * 65)
    for name, tok in spacing_eng.tokens.items():
        gauge_dots = "■" * (tok.px_value // 4)
        print(f"{ANSI.FG_HI_YELLOW}{name:<12}{ANSI.RESET} | "
              f"{tok.px_value:>8}px | "
              f"{tok.rem_value:>10.3f}rem | "
              f"{ANSI.FG_GREEN}{gauge_dots}{ANSI.RESET}")
    
    print(f"\n{ANSI.BOLD}Running Spacing Linter Against Mock CSS Values:{ANSI.RESET}")
    test_cases = [8, 12, 14, 16, 22, 24, 30, 32, 45, 64]
    for val in test_cases:
        valid, msg, suggestion = spacing_eng.lint_value(val)
        if valid:
            status = f"{ANSI.FG_GREEN}[PASS]{ANSI.RESET}"
            print(f" {status} {val:>2}px -> {msg}")
        else:
            status = f"{ANSI.FG_RED}[FAIL]{ANSI.RESET}"
            print(f" {status} {val:>2}px -> {msg} -> Suggested: {ANSI.BOLD}{suggestion}px{ANSI.RESET}")
    print()

def demo_grid():
    print(f"{ANSI.BOLD}{ANSI.FG_CYAN}--- [MODUL 3: 12-COLUMN RESPONSIVE SPATIAL GRID] ---{ANSI.RESET}")
    config = ColumnLayoutConfig(container_width=1200, columns=12, gutter=24, margin=32)
    grid_eng = SpatialGridEngine(config)
    print(grid_eng.render_ascii_grid(total_terminal_chars=68))
    
    print(f"\n{ANSI.BOLD}Common Layout Spans & Exact Computed Widths:{ANSI.RESET}")
    span_scenarios = [
        ("Full Width (Hero / Banner)", 12),
        ("Halves (Split 50-50 Content)", 6),
        ("Thirds (Feature Cards)", 4),
        ("Quarters (Product Grid)", 3),
        ("Main / Sidebar (8 / 4 Split)", 8),
    ]
    for label, span_count in span_scenarios:
        width = grid_eng.calculate_span_width(span_count)
        print(f"  • {label:<32} (col-span-{span_count:>2}): {ANSI.FG_HI_BLUE}{width:>7.2f}px{ANSI.RESET}")
    print()

def run_self_test() -> bool:
    """Automated assertion checks for continuous integration & test pass."""
    typo = TypographyEngine(base_size_px=16.0, ratio_name="perfect-fourth", baseline_grid_px=4)
    scale = typo.generate_scale()
    for item in scale:
        assert item.snapped_line_height_px % 4 == 0, f"Line height {item.snapped_line_height_px} not snapped to 4px"

    spacing = SpacingEngine(base_unit_px=8)
    assert spacing.lint_value(16)[0] is True
    assert spacing.lint_value(14)[0] is False
    assert spacing.lint_value(14)[2] in (12, 16)

    grid = SpatialGridEngine(ColumnLayoutConfig(1200, 12, 24, 32))
    col_w = grid.calculate_column_width()
    # Verification: 1200 - 64 (margins) - 11*24 (264) = 872 -> 872 / 12 = 72.6666...
    assert abs(col_w - 72.6666) < 0.01
    span_12 = grid.calculate_span_width(12)
    # Span 12 must match container minus 2*margin = 1136
    assert abs(span_12 - 1136.0) < 0.01

    return True

def main():
    parser = argparse.ArgumentParser(description="Typography, Spacing & Spatial Grids Interactive Lab")
    parser.add_argument("--test", action="store_true", help="Run automated test assertions and exit")
    parser.add_argument("--all", action="store_true", default=True, help="Run all modular demonstrations")
    args = parser.parse_args()

    if args.test:
        success = run_self_test()
        if success:
            print(f"{ANSI.FG_GREEN}✓ All Design System mathematical assertions PASSED.{ANSI.RESET}")
            sys.exit(0)
        else:
            print(f"{ANSI.FG_RED}✗ Assertions failed.{ANSI.RESET}")
            sys.exit(1)

    banner()
    demo_typography()
    demo_spacing()
    demo_grid()
    
    # Run test verification
    run_self_test()
    print(f"{ANSI.BG_DARK_GRAY}{ANSI.FG_HI_GREEN} [OK] Automated unit checks passed: 100% compliant with 4pt/8pt grid standards. {ANSI.RESET}\n")

if __name__ == "__main__":
    main()
