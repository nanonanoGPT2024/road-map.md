#!/usr/bin/env python3
"""
SwiftUI Layout Engine & Adaptive System - Interactive CLI Simulation
BAB-02: 3-Step Layout Negotiation, Sizing Behaviors, and Adaptive Systems
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

# --- ANSI Color Codes ---
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
    BG_DARK = "\033[48;5;236m"


@dataclass
class CGSize:
    width: float
    height: float

    def __str__(self) -> str:
        return f"({self.width:.1f} x {self.height:.1f})"


@dataclass
class ProposedViewSize:
    width: Optional[float]
    height: Optional[float]

    def or_default(self, default_w: float = 393.0, default_h: float = 852.0) -> CGSize:
        return CGSize(
            self.width if self.width is not None else default_w,
            self.height if self.height is not None else default_h,
        )

    def __str__(self) -> str:
        w_str = f"{self.width:.1f}" if self.width is not None else "nil"
        h_str = f"{self.height:.1f}" if self.height is not None else "nil"
        return f"Proposed({w_str}, {h_str})"


class SwiftUIElement:
    def __init__(self, name: str, layout_priority: float = 0.0):
        self.name = name
        self.layout_priority = layout_priority

    def size_that_fits(self, proposal: ProposedViewSize) -> CGSize:
        raise NotImplementedError

    def behavior_type(self) -> str:
        raise NotImplementedError


class TextElement(SwiftUIElement):
    """Neutral sizing: fits intrinsic text length unless constrained."""
    def __init__(self, text: str, font_size: float = 14.0, layout_priority: float = 0.0):
        super().__init__(f'Text("{text}")', layout_priority)
        self.text = text
        self.font_size = font_size
        self.char_width = font_size * 0.55
        self.line_height = font_size * 1.3

    def behavior_type(self) -> str:
        return f"{Color.CYAN}Neutral (Intrinsic){Color.RESET}"

    def size_that_fits(self, proposal: ProposedViewSize) -> CGSize:
        single_line_w = len(self.text) * self.char_width
        if proposal.width is None or single_line_w <= proposal.width:
            return CGSize(single_line_w, self.line_height)
        
        # Word wrap simulation
        max_w = max(proposal.width, self.char_width * 3)
        chars_per_line = max(1, int(max_w / self.char_width))
        lines = (len(self.text) + chars_per_line - 1) // chars_per_line
        actual_w = min(single_line_w, max_w)
        actual_h = lines * self.line_height
        return CGSize(actual_w, actual_h)


class ColorElement(SwiftUIElement):
    """Greedy sizing: expands to take all proposed space (like Color.blue)."""
    def __init__(self, color_name: str, layout_priority: float = 0.0):
        super().__init__(f"Color.{color_name}", layout_priority)

    def behavior_type(self) -> str:
        return f"{Color.GREEN}Greedy (Expands){Color.RESET}"

    def size_that_fits(self, proposal: ProposedViewSize) -> CGSize:
        # Default fallback if unconstrained is 10x10 or proposal
        w = proposal.width if proposal.width is not None else 10.0
        h = proposal.height if proposal.height is not None else 10.0
        return CGSize(w, h)


class SpacerElement(SwiftUIElement):
    """Greedy layout element: absorbs remaining space."""
    def __init__(self, min_length: float = 8.0, layout_priority: float = 0.0):
        super().__init__("Spacer()", layout_priority)
        self.min_length = min_length

    def behavior_type(self) -> str:
        return f"{Color.GREEN}Greedy (Flexible Space){Color.RESET}"

    def size_that_fits(self, proposal: ProposedViewSize) -> CGSize:
        w = max(self.min_length, proposal.width if proposal.width is not None else self.min_length)
        h = max(self.min_length, proposal.height if proposal.height is not None else self.min_length)
        return CGSize(w, h)


class FrameModifier(SwiftUIElement):
    """Modifies child with fixed or min/max constraints."""
    def __init__(self, child: SwiftUIElement, fixed_w: Optional[float] = None, fixed_h: Optional[float] = None):
        super().__init__(f"{child.name}.frame({fixed_w}, {fixed_h})", child.layout_priority)
        self.child = child
        self.fixed_w = fixed_w
        self.fixed_h = fixed_h

    def behavior_type(self) -> str:
        return f"{Color.MAGENTA}Fixed / Constrained{Color.RESET}"

    def size_that_fits(self, proposal: ProposedViewSize) -> CGSize:
        inner_proposal = ProposedViewSize(
            width=self.fixed_w if self.fixed_w is not None else proposal.width,
            height=self.fixed_h if self.fixed_h is not None else proposal.height,
        )
        child_size = self.child.size_that_fits(inner_proposal)
        final_w = self.fixed_w if self.fixed_w is not None else child_size.width
        final_h = self.fixed_h if self.fixed_h is not None else child_size.height
        return CGSize(final_w, final_h)


class HStackLayout:
    """SwiftUI HStack layout algorithm simulation with 3-step negotiation and layoutPriority."""
    def __init__(self, children: List[SwiftUIElement], spacing: float = 8.0):
        self.children = children
        self.spacing = spacing

    def solve(self, total_proposal: ProposedViewSize) -> Tuple[CGSize, List[Tuple[SwiftUIElement, CGSize, float]]]:
        total_w = total_proposal.width if total_proposal.width is not None else 300.0
        container_h = total_proposal.height if total_proposal.height is not None else 50.0

        n = len(self.children)
        if n == 0:
            return CGSize(0, 0), []

        total_spacing = self.spacing * (n - 1)
        remaining_w = max(0.0, total_w - total_spacing)

        # Group by layout priority (highest first)
        priorities = sorted(list({c.layout_priority for c in self.children}), reverse=True)
        allocated_sizes: dict = {}

        unallocated = list(self.children)

        for p in priorities:
            group = [c for c in unallocated if c.layout_priority == p]
            # Sizing negotiation for this priority tier
            # SwiftUI sorts elements by flexibility (least flexible / smallest claim first)
            while group:
                available_per_child = remaining_w / len(group)
                # Query each child with equal slice
                claims = []
                for c in group:
                    child_proposal = ProposedViewSize(width=available_per_child, height=container_h)
                    claim_sz = c.size_that_fits(child_proposal)
                    claims.append((c, claim_sz))
                
                # Sort by width claimed
                claims.sort(key=lambda item: item[1].width)
                chosen_child, chosen_size = claims[0]
                
                allocated_w = min(chosen_size.width, remaining_w)
                allocated_sizes[chosen_child] = CGSize(allocated_w, chosen_size.height)
                remaining_w -= allocated_w
                group.remove(chosen_child)
                unallocated.remove(chosen_child)

        # Place children sequentially
        results = []
        current_x = 0.0
        max_h = 0.0
        for child in self.children:
            sz = allocated_sizes.get(child, CGSize(0, 0))
            results.append((child, sz, current_x))
            current_x += sz.width + self.spacing
            max_h = max(max_h, sz.height)

        actual_w = current_x - (self.spacing if n > 0 else 0)
        return CGSize(actual_w, max_h), results


class AdaptiveEngine:
    """Demonstrates Adaptive Layout, Size Classes, and ViewThatFits."""
    @staticmethod
    def classify_screen(width: float) -> str:
        if width < 430:
            return "Compact Width (iPhone Portrait)"
        elif width < 800:
            return "Compact / Medium (iPhone Landscape / iPad Split)"
        else:
            return "Regular Width (iPad Fullscreen / Mac)"

    @staticmethod
    def view_that_fits_demo(container_w: float) -> str:
        options = [
            ("Option 1 (Full Bar)", "HStack { Logo; NavigationMenu; UserAvatar; SearchField }", 380.0),
            ("Option 2 (Compact Bar)", "HStack { Logo; SearchField; HamburgerMenu }", 220.0),
            ("Option 3 (Minimal)", "HStack { Logo; HamburgerMenu }", 120.0),
        ]
        for name, view_desc, min_w in options:
            if container_w >= min_w:
                return f"{Color.GREEN}{name}{Color.RESET}: `{view_desc}` (needs >= {min_w:.0f}pt)"
        return f"{Color.RED}Fallback: ScrollView needed{Color.RESET}"


def print_header(title: str):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}")


def run_three_step_negotiation_demo():
    print_header("1. Three-Step Layout Negotiation Lifecycle")
    print(f"{Color.DIM}Simulating: SwiftUI Parent <--> Child Layout Protocol{Color.RESET}")
    
    text_view = TextElement("Halo Dunia SwiftUI Layout Engine!", font_size=16.0)
    proposals = [
        ProposedViewSize(None, None),          # Unconstrained
        ProposedViewSize(300.0, 100.0),        # Plenty of room
        ProposedViewSize(120.0, 100.0),        # Narrow width (triggers wrapping)
        ProposedViewSize(0.0, 0.0),            # Zero proposal
    ]

    for idx, prop in enumerate(proposals, 1):
        print(f"\n{Color.BOLD}Iterasi {idx}:{Color.RESET}")
        print(f"  {Color.YELLOW}[Step 1: Parent Proposes]{Color.RESET} -> {prop}")
        sz = text_view.size_that_fits(prop)
        print(f"  {Color.CYAN}[Step 2: Child Chooses]  {Color.RESET} -> Returns {Color.BOLD}{sz}{Color.RESET}")
        print(f"  {Color.GREEN}[Step 3: Parent Places]  {Color.RESET} -> Placed at origin (x=0.0, y=0.0) with frame {sz}")


def run_sizing_behavior_matrix():
    print_header("2. Sizing Behavior Matrix (Greedy vs Neutral vs Fixed)")
    items: List[SwiftUIElement] = [
        TextElement("Short Text"),
        ColorElement("blue"),
        SpacerElement(min_length=10.0),
        FrameModifier(TextElement("Inside Fixed Frame"), fixed_w=150.0, fixed_h=40.0),
    ]

    proposal = ProposedViewSize(200.0, 60.0)
    print(f"Parent Proposal to all views: {Color.BOLD}{proposal}{Color.RESET}\n")
    print(f"{'View Element':<32} | {'Behavior Class':<30} | {'Result Size':<15}")
    print("-" * 80)
    for it in items:
        computed = it.size_that_fits(proposal)
        print(f"{it.name:<32} | {it.behavior_type():<40} | {Color.WHITE}{computed}{Color.RESET}")


def run_hstack_priority_simulation():
    print_header("3. HStack Layout with .layoutPriority() Resolution")
    print(f"{Color.DIM}Scenario: Container Width = 260pt, Spacing = 8pt (Total spacing = 16pt, Content available = 244pt){Color.RESET}\n")

    # Three views competing for width
    v1 = TextElement("User: @septian", font_size=14.0, layout_priority=0.0)
    v2 = TextElement("[VERIFIED BADGE - IMPORTANT]", font_size=14.0, layout_priority=1.0)
    v3 = TextElement("Active 2m ago", font_size=14.0, layout_priority=0.0)

    stack = HStackLayout([v1, v2, v3], spacing=8.0)
    container_proposal = ProposedViewSize(260.0, 40.0)

    final_size, placements = stack.solve(container_proposal)
    print(f"{Color.YELLOW}Final HStack Computed Dimension:{Color.RESET} {Color.BOLD}{final_size}{Color.RESET}\n")

    for child, sz, pos_x in placements:
        p_str = f"priority={child.layout_priority:.0f}"
        p_colored = f"{Color.GREEN}{p_str}{Color.RESET}" if child.layout_priority > 0 else f"{Color.DIM}{p_str}{Color.RESET}"
        print(f"  - {child.name:<32} ({p_colored}):")
        print(f"      Assigned Width: {sz.width:.1f}pt | Placed at X: {pos_x:.1f}pt")


def run_adaptive_viewthatfits_demo():
    print_header("4. Adaptive System: Size Classes & ViewThatFits")
    test_widths = [200.0, 320.0, 420.0, 840.0]
    
    for w in test_widths:
        size_class = AdaptiveEngine.classify_screen(w)
        best_fit = AdaptiveEngine.view_that_fits_demo(w)
        print(f"\n{Color.BOLD}Device Screen Width: {w:.0f} pt{Color.RESET}")
        print(f"  Classification : {Color.MAGENTA}{size_class}{Color.RESET}")
        print(f"  ViewThatFits   : {best_fit}")


def interactive_menu():
    while True:
        print("\n" + "=" * 60)
        print(f"{Color.CYAN}{Color.BOLD}SWIFTUI LAYOUT ENGINE & ADAPTIVE SYSTEM LAB (BAB-02){Color.RESET}")
        print("=" * 60)
        print("1. Run 3-Step Layout Negotiation Simulation")
        print("2. Run Sizing Behavior Matrix (Neutral / Greedy / Fixed)")
        print("3. Run HStack Layout Priority Demonstration")
        print("4. Run Adaptive Size Classes & ViewThatFits Engine")
        print("5. Run All Lab Tests Concurrently")
        print("6. Exit")
        print("-" * 60)
        
        try:
            choice = input(f"{Color.YELLOW}Pilih modul simulasi (1-6): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if choice == "1":
            run_three_step_negotiation_demo()
        elif choice == "2":
            run_sizing_behavior_matrix()
        elif choice == "3":
            run_hstack_priority_simulation()
        elif choice == "4":
            run_adaptive_viewthatfits_demo()
        elif choice == "5":
            run_three_step_negotiation_demo()
            run_sizing_behavior_matrix()
            run_hstack_priority_simulation()
            run_adaptive_viewthatfits_demo()
            print(f"\n{Color.GREEN}{Color.BOLD}[SUCCESS] Seluruh modul simulasi Layout Engine tuntas dieksekusi.{Color.RESET}")
        elif choice == "6":
            print(f"{Color.GREEN}Terima kasih telah menjalankan lab SwiftUI Layout Engine.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Masukkan angka 1-6.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_three_step_negotiation_demo()
        run_sizing_behavior_matrix()
        run_hstack_priority_simulation()
        run_adaptive_viewthatfits_demo()
        print(f"\n{Color.GREEN}{Color.BOLD}[CI/AUTO] Verification completed without error.{Color.RESET}")
    else:
        interactive_menu()
