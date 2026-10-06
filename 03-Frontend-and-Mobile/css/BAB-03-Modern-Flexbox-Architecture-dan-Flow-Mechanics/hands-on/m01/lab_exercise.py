#!/usr/bin/env python3
"""
Lab Exercise M01: CSS Modern Flexbox Architecture & Flow Mechanics Simulator
=============================================================================
Simulasi algoritma perhitungan kalkulasi Flexbox CSS tingkat rendah:
1. Resolusi Main Axis vs Cross Axis (flex-direction & writing-mode).
2. Perhitungan Hypo-basis & Available Free Space (Positive / Negative).
3. Proporsional Flex Grow Expansion.
4. Normalized Weighted Flex Shrink Reduction (Scaled Shrink Factor).
5. Alignment (justify-content & align-items).
"""

import sys
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional

# ANSI Color codes untuk visualisasi terminal
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
BG_MAGENTA = "\033[45m"
BG_GRAY = "\033[100m"

@dataclass
class FlexItem:
    id: str
    flex_basis: float      # in px
    flex_grow: float       # unitless
    flex_shrink: float     # unitless
    min_size: float = 0.0  # min-width / min-height clamp
    max_size: float = math.inf # max-width / max-height clamp
    calculated_size: float = 0.0

@dataclass
class FlexContainer:
    main_size: float       # Container main axis dimension in px
    direction: str = "row" # row, column, row-reverse, column-reverse
    justify_content: str = "flex-start" # flex-start, flex-end, center, space-between, space-around, space-evenly
    items: List[FlexItem] = None

    def __post_init__(self):
        if self.items is None:
            self.items = []

def print_header(title: str):
    width = 75
    print("\n" + BOLD + CYAN + "=" * width + RESET)
    print(BOLD + WHITE + f" {title.center(width - 2)} " + RESET)
    print(BOLD + CYAN + "=" * width + RESET)

def print_sub_header(subtitle: str):
    print(f"\n{BOLD}{YELLOW}>>> {subtitle}{RESET}")

def render_bar(label: str, size: float, color: str, max_render_width: int = 40, total_scale: float = 600.0) -> str:
    scaled_len = max(1, int((size / total_scale) * max_render_width))
    block = "█" * scaled_len
    return f"{BOLD}{label:<8}{RESET} |{color}{block:<{max_render_width}}{RESET}| {BOLD}{size:.1f}px{RESET}"

def calculate_flex_layout(container: FlexContainer) -> Tuple[float, List[float]]:
    """
    Mengimplementasikan CSS Flexible Box Layout Module Level 1 (W3C Spec Section 9).
    Menghitung ukuran akhir setiap item di sepanjang Main Axis.
    """
    sum_hypothetical = sum(item.flex_basis for item in container.items)
    free_space = container.main_size - sum_hypothetical

    print(f"{DIM}Total Container Main Size : {BOLD}{container.main_size:.1f}px{RESET}")
    print(f"{DIM}Total Sum of Flex Basis   : {BOLD}{sum_hypothetical:.1f}px{RESET}")
    
    final_sizes = []

    if free_space > 0:
        # Positive Free Space -> Flex Grow
        print(f"Status Ruang Main Axis   : {GREEN}{BOLD}POSITIVE FREE SPACE (+{free_space:.1f}px){RESET}")
        total_grow = sum(item.flex_grow for item in container.items)
        print(f"Total Flex Grow Factor   : {CYAN}{total_grow:.2f}{RESET}")

        for item in container.items:
            if total_grow > 0 and item.flex_grow > 0:
                grow_share = (item.flex_grow / total_grow) * free_space
                target_size = item.flex_basis + grow_share
            else:
                target_size = item.flex_basis

            # Clamping min/max
            clamped_size = max(item.min_size, min(target_size, item.max_size))
            item.calculated_size = clamped_size
            final_sizes.append(clamped_size)

    elif free_space < 0:
        # Negative Free Space -> Flex Shrink
        deficit = abs(free_space)
        print(f"Status Ruang Main Axis   : {RED}{BOLD}NEGATIVE FREE SPACE (Deficit: -{deficit:.1f}px){RESET}")
        
        # Algoritma W3C: Scaled Flex Shrink Factor = flex_shrink * flex_basis
        scaled_shrink_factors = [item.flex_shrink * item.flex_basis for item in container.items]
        total_scaled_shrink = sum(scaled_shrink_factors)
        
        print(f"Total Scaled Shrink W3C  : {MAGENTA}{total_scaled_shrink:.2f}{RESET}")

        for idx, item in enumerate(container.items):
            if total_scaled_shrink > 0 and item.flex_shrink > 0:
                scaled_factor = scaled_shrink_factors[idx]
                shrink_share = (scaled_factor / total_scaled_shrink) * deficit
                target_size = item.flex_basis - shrink_share
            else:
                target_size = item.flex_basis

            clamped_size = max(item.min_size, min(target_size, item.max_size))
            item.calculated_size = clamped_size
            final_sizes.append(clamped_size)
    else:
        print(f"Status Ruang Main Axis   : {YELLOW}{BOLD}EXACT FIT (0px Free Space){RESET}")
        for item in container.items:
            item.calculated_size = item.flex_basis
            final_sizes.append(item.flex_basis)

    return free_space, final_sizes

def calculate_alignment(container: FlexContainer) -> List[Tuple[float, float]]:
    """
    Menghitung posisi offset (start_pos, end_pos) setiap item berdasarkan justify-content.
    """
    total_items_size = sum(item.calculated_size for item in container.items)
    remaining_space = max(0.0, container.main_size - total_items_size)
    n = len(container.items)
    
    positions = []
    
    if n == 0:
        return positions

    if container.justify_content == "flex-start":
        current_offset = 0.0
        for item in container.items:
            positions.append((current_offset, current_offset + item.calculated_size))
            current_offset += item.calculated_size

    elif container.justify_content == "flex-end":
        current_offset = remaining_space
        for item in container.items:
            positions.append((current_offset, current_offset + item.calculated_size))
            current_offset += item.calculated_size

    elif container.justify_content == "center":
        current_offset = remaining_space / 2.0
        for item in container.items:
            positions.append((current_offset, current_offset + item.calculated_size))
            current_offset += item.calculated_size

    elif container.justify_content == "space-between":
        gap = remaining_space / (n - 1) if n > 1 else 0.0
        current_offset = 0.0
        for item in container.items:
            positions.append((current_offset, current_offset + item.calculated_size))
            current_offset += item.calculated_size + gap

    elif container.justify_content == "space-around":
        gap = remaining_space / n
        current_offset = gap / 2.0
        for item in container.items:
            positions.append((current_offset, current_offset + item.calculated_size))
            current_offset += item.calculated_size + gap

    elif container.justify_content == "space-evenly":
        gap = remaining_space / (n + 1)
        current_offset = gap
        for item in container.items:
            positions.append((current_offset, current_offset + item.calculated_size))
            current_offset += item.calculated_size + gap

    return positions

def render_terminal_layout(container: FlexContainer, positions: List[Tuple[float, float]]):
    """
    Merender visualisasi ASCII box 1D container Flexbox di terminal.
    """
    cols = 64
    scale = cols / container.main_size
    line = [" "] * cols

    colors = [BLUE, GREEN, MAGENTA, YELLOW, CYAN]

    print(f"\n{BOLD}Container Visual Representation ({container.main_size:.0f}px Total):{RESET}")
    print("┌" + "─" * cols + "┐")

    info_legend = []
    for idx, (item, (start, end)) in enumerate(zip(container.items, positions)):
        c_idx = idx % len(colors)
        col_start = int(start * scale)
        col_end = min(cols, max(col_start + 1, int(end * scale)))
        
        char = chr(65 + idx) # A, B, C...
        for c in range(col_start, col_end):
            line[c] = f"{colors[c_idx]}{char}{RESET}"
        
        info_legend.append(f"{colors[c_idx]}[{char}] {item.id}: {item.calculated_size:.1f}px{RESET}")

    rendered_line = "".join(line)
    print(f"│{rendered_line}│")
    print("└" + "─" * cols + "┘")
    print("Legend: " + " | ".join(info_legend))

def run_case_study(title: str, container: FlexContainer):
    print_header(title)
    print(f"{BOLD}Properties:{RESET} main_size={container.main_size}px, direction={container.direction}, justify_content={container.justify_content}")
    print("\nInitial Items:")
    for item in container.items:
        print(f"  • {BOLD}{item.id:<10}{RESET}: basis={item.flex_basis:5.1f}px | grow={item.flex_grow} | shrink={item.flex_shrink} | min={item.min_size}px")

    print_sub_header("Execution & Calculation Step")
    free_space, final_sizes = calculate_flex_layout(container)

    print_sub_header("Results & Size Bars")
    palette = [BLUE, GREEN, MAGENTA, YELLOW, CYAN]
    for idx, item in enumerate(container.items):
        color = palette[idx % len(palette)]
        delta = item.calculated_size - item.flex_basis
        diff_str = f"(+{delta:.1f}px)" if delta > 0 else (f"({delta:.1f}px)" if delta < 0 else "(no change)")
        print(render_bar(item.id, item.calculated_size, color, total_scale=container.main_size) + f"  {DIM}{diff_str}{RESET}")

    positions = calculate_alignment(container)
    render_terminal_layout(container, positions)

def interactive_mode():
    print_header("FLEXBOX INTERACTIVE LABORATORY")
    try:
        container_width_in = input(f"{BOLD}Enter Container Width in px (default 500): {RESET}").strip()
        container_width = float(container_width_in) if container_width_in else 500.0

        items = []
        num_items_in = input(f"{BOLD}Enter number of flex items (2-4, default 3): {RESET}").strip()
        num_items = int(num_items_in) if num_items_in else 3

        for i in range(num_items):
            print(f"\n{CYAN}--- Configure Item {chr(65+i)} ---{RESET}")
            b_in = input(f"  Flex Basis px (default 100): ").strip()
            g_in = input(f"  Flex Grow (default 1): ").strip()
            s_in = input(f"  Flex Shrink (default 1): ").strip()
            
            basis = float(b_in) if b_in else 100.0
            grow = float(g_in) if g_in else 1.0
            shrink = float(s_in) if s_in else 1.0
            
            items.append(FlexItem(id=f"Item-{chr(65+i)}", flex_basis=basis, flex_grow=grow, flex_shrink=shrink))

        jc_in = input(f"\n{BOLD}Justify Content [flex-start/center/flex-end/space-between/space-around/space-evenly] (default space-between): {RESET}").strip()
        jc = jc_in if jc_in else "space-between"

        custom_container = FlexContainer(main_size=container_width, justify_content=jc, items=items)
        run_case_study("CUSTOM INTERACTIVE EXPERIMENT", custom_container)

    except (ValueError, KeyboardInterrupt) as e:
        print(f"\n{RED}Input dibatalkan atau tidak valid. Menjalankan skenario otomatis default.{RESET}")
        run_default_scenarios()

def run_default_scenarios():
    # Skenario 1: Flex Grow & Positive Free Space Distribution
    c1 = FlexContainer(
        main_size=600.0,
        justify_content="flex-start",
        items=[
            FlexItem(id="Nav-Brand", flex_basis=100.0, flex_grow=0.0, flex_shrink=1.0),
            FlexItem(id="Nav-Search", flex_basis=150.0, flex_grow=3.0, flex_shrink=1.0),
            FlexItem(id="Nav-Links", flex_basis=150.0, flex_grow=1.0, flex_shrink=1.0)
        ]
    )
    run_case_study("STUDI KASUS 1: POSITIVE FREE SPACE & ASYMMETRIC FLEX-GROW", c1)

    # Skenario 2: W3C Scaled Flex Shrink Algorithm dengan Negative Free Space
    c2 = FlexContainer(
        main_size=400.0,
        justify_content="flex-start",
        items=[
            FlexItem(id="Card-Alpha", flex_basis=250.0, flex_grow=0.0, flex_shrink=1.0),
            FlexItem(id="Card-Beta", flex_basis=250.0, flex_grow=0.0, flex_shrink=3.0),
            FlexItem(id="Card-Fixed", flex_basis=100.0, flex_grow=0.0, flex_shrink=0.0) # rigid item
        ]
    )
    run_case_study("STUDI KASUS 2: NEGATIVE FREE SPACE & W3C WEIGHTED SHRINK MECHANICS", c2)

    # Skenario 3: Justify Content Flow Alignment Spacing
    c3 = FlexContainer(
        main_size=550.0,
        justify_content="space-between",
        items=[
            FlexItem(id="Tag-A", flex_basis=80.0, flex_grow=0.0, flex_shrink=0.0),
            FlexItem(id="Tag-B", flex_basis=90.0, flex_grow=0.0, flex_shrink=0.0),
            FlexItem(id="Tag-C", flex_basis=110.0, flex_grow=0.0, flex_shrink=0.0)
        ]
    )
    run_case_study("STUDI KASUS 3: JUSTIFY-CONTENT SPACE-BETWEEN MULTI-ITEM DISTRIBUTION", c3)

def main():
    print(f"{BOLD}{GREEN}=== SISTEM SIMULASI TEKNIS CSS FLEXBOX ARCHITECTURE (BAB 03) ==={RESET}")
    print(f"Modul Lab: {CYAN}hands-on/m01/lab_exercise.py{RESET}")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        run_default_scenarios()
        print(f"\n{BOLD}{WHITE}Tips:{RESET} Jalankan dengan opsi {YELLOW}--interactive{RESET} untuk menguji konfigurasi custom fleksibel.")
        print(f"{GREEN}Simulasi komputasi Flexbox selesai tanpa error.{RESET}\n")

if __name__ == "__main__":
    main()
