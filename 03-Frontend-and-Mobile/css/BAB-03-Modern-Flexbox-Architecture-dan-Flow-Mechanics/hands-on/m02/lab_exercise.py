#!/usr/bin/env python3
"""
Lab Exercise: Modern Flexbox Architecture & Flow Mechanics
Modul: 03-Frontend-and-Mobile / Bab 03: Modern Flexbox Architecture dan Flow Mechanics

Deskripsi:
Script ini mengimplementasikan replikasi mesin kalkulasi tata letak CSS Flexible Box
(W3C Flexbox Specification Level 1). Mensimulasikan secara presisi:
  1. Hypothetical Main Size calculation.
  2. Resolving Flexible Lengths (multi-pass freeze-and-redistribute algorithm).
  3. Negative Free Space distribution proportional to (flex-shrink * flex-basis).
  4. Justify-Content positioning & Cross-Axis alignment (align-items).
  5. ASCII layout rendering ke terminal dengan indikator visual per-item.
"""

import sys
import math
from typing import List, Optional

# --- ANSI Terminal Color Codes ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"
CLR_GRAY = "\033[90m"


class FlexItem:
    """
    Merepresentasikan flex item individual dengan flex factors dan box constraints.
    """
    def __init__(
        self,
        name: str,
        flex_basis: float,
        flex_grow: float = 0.0,
        flex_shrink: float = 1.0,
        min_size: float = 0.0,
        max_size: float = float("inf"),
        cross_size: float = 40.0,
    ):
        self.name = name
        self.flex_basis = float(flex_basis)
        self.flex_grow = float(flex_grow)
        self.flex_shrink = float(flex_shrink)
        self.min_size = float(min_size)
        self.max_size = float(max_size)
        self.cross_size = float(cross_size)

        # Output states hasil kalkulasi flex engine
        self.target_main_size: float = self.flex_basis
        self.hypothetical_main_size: float = self.flex_basis
        self.is_frozen: bool = False
        self.main_offset: float = 0.0
        self.cross_offset: float = 0.0

    def reset_state(self):
        self.target_main_size = self.flex_basis
        self.hypothetical_main_size = self.flex_basis
        self.is_frozen = False
        self.main_offset = 0.0
        self.cross_offset = 0.0


class FlexContainer:
    """
    Mengimplementasikan spesifikasi W3C Flexbox Flow & Distribution Algorithm.
    """
    def __init__(
        self,
        width: float,
        height: float,
        justify_content: str = "flex-start",
        align_items: str = "stretch",
    ):
        self.width = float(width)
        self.height = float(height)
        self.justify_content = justify_content  # flex-start, flex-end, center, space-between, space-around
        self.align_items = align_items          # flex-start, flex-end, center, stretch
        self.items: List[FlexItem] = []

    def add_item(self, item: FlexItem) -> None:
        self.items.append(item)

    def resolve_flexible_lengths(self) -> None:
        """
        W3C Flexbox Spec - Resolving Flexible Lengths Algorithm (Bagian Inti):
        9.7. Resolving Flexible Lengths
        Algoritma iteratif multi-pass untuk mendistribusikan sisa ruang kosong
        (positif maupun negatif) dengan menghormati min/max constraints melalui freezing.
        """
        # Step 1: Inisialisasi Hypothetical Main Size
        for item in self.items:
            item.reset_state()
            clamped = max(item.min_size, min(item.flex_basis, item.max_size))
            item.hypothetical_main_size = clamped
            item.target_main_size = item.hypothetical_main_size

        sum_hypothetical = sum(i.hypothetical_main_size for i in self.items)
        initial_free_space = self.width - sum(i.flex_basis for i in self.items)

        is_growing = initial_free_space > 0
        iteration = 1

        print(f"{CLR_GRAY}  [Flex Engine] Initial Free Space: {initial_free_space:+.2f}px "
              f"({'Distributing Grow' if is_growing else 'Distributing Shrink'}){CLR_RESET}")

        # Step 2: Loop hingga semua item stabil (tidak ada pelanggaran batas min/max baru)
        while True:
            unfrozen = [i for i in self.items if not i.is_frozen]
            if not unfrozen:
                break

            # Hitung ruang bebas relatif terhadap item yang belum dibekukan
            sum_flex_basis_unfrozen = sum(i.flex_basis for i in unfrozen)
            sum_frozen_target = sum(i.target_main_size for i in self.items if i.is_frozen)
            available_inner_space = self.width - sum_frozen_target
            remaining_free_space = available_inner_space - sum_flex_basis_unfrozen

            # Distribusikan ruang
            if is_growing:
                total_grow = sum(i.flex_grow for i in unfrozen)
                if total_grow < 1.0 and total_grow > 0:
                    remaining_free_space *= total_grow
                for item in unfrozen:
                    if total_grow > 0:
                        share = (item.flex_grow / total_grow) * remaining_free_space
                        item.target_main_size = item.flex_basis + share
                    else:
                        item.target_main_size = item.flex_basis
            else:
                # W3C Shrink Factor dihitung proporsional terhadap (flex-shrink * flex-basis)
                total_scaled_shrink = sum(i.flex_shrink * i.flex_basis for i in unfrozen)
                for item in unfrozen:
                    if total_scaled_shrink > 0:
                        scaled_factor = item.flex_shrink * item.flex_basis
                        shrink_amount = (scaled_factor / total_scaled_shrink) * abs(remaining_free_space)
                        item.target_main_size = item.flex_basis - shrink_amount
                    else:
                        item.target_main_size = item.flex_basis

            # Step 3: Check min/max violations
            violations = []
            for item in unfrozen:
                if item.target_main_size < item.min_size:
                    violations.append((item, item.min_size, "min violation"))
                elif item.target_main_size > item.max_size:
                    violations.append((item, item.max_size, "max violation"))

            # Step 4: Freeze violating items
            if not violations:
                break  # Konvergensi tercapai, tidak ada item yang melanggar batas

            print(f"{CLR_GRAY}  [Loop {iteration}] Clamping & Freezing {len(violations)} item(s)...{CLR_RESET}")
            for item, limit, reason in violations:
                item.target_main_size = limit
                item.is_frozen = True
                print(f"    - Freeze {CLR_YELLOW}{item.name}{CLR_RESET} to {limit:.1f}px ({reason})")

            iteration += 1

    def resolve_positions(self) -> None:
        """
        W3C Flexbox Spec - Section 9.4 & 9.5:
        Mengkalkulasikan offset Main-Axis (Justify-Content) dan Cross-Axis (Align-Items).
        """
        used_main_space = sum(i.target_main_size for i in self.items)
        leftover_main = max(0.0, self.width - used_main_space)
        n = len(self.items)

        # Main Axis Justification Mechanics
        current_offset = 0.0
        gap = 0.0

        if self.justify_content == "flex-start":
            current_offset = 0.0
        elif self.justify_content == "flex-end":
            current_offset = leftover_main
        elif self.justify_content == "center":
            current_offset = leftover_main / 2.0
        elif self.justify_content == "space-between":
            current_offset = 0.0
            gap = leftover_main / (n - 1) if n > 1 else 0.0
        elif self.justify_content == "space-around":
            gap = leftover_main / n if n > 0 else 0.0
            current_offset = gap / 2.0

        for item in self.items:
            item.main_offset = current_offset
            current_offset += item.target_main_size + gap

            # Cross Axis Alignment Mechanics
            if self.align_items == "flex-start":
                item.cross_offset = 0.0
            elif self.align_items == "flex-end":
                item.cross_offset = self.height - item.cross_size
            elif self.align_items == "center":
                item.cross_offset = (self.height - item.cross_size) / 2.0
            elif self.align_items == "stretch":
                item.cross_offset = 0.0
                item.cross_size = self.height


def render_ascii_layout(container: FlexContainer, scale_width: int = 70) -> None:
    """
    Merender layout container dan flex item dalam format ASCII bar berbasis proporsi terminal.
    """
    scale = scale_width / container.width
    canvas_w = scale_width

    # Buat array buffer karakter 1D untuk representasi bar
    bar = [" "] * canvas_w
    label_layer = [" "] * canvas_w

    colors = [CLR_CYAN, CLR_GREEN, CLR_YELLOW, CLR_MAGENTA, CLR_BLUE]

    print(f"\n{CLR_BOLD}Terminal Flow Visualization (Container: {container.width:.0f}px x {container.height:.0f}px):{CLR_RESET}")
    print("+" + "-" * canvas_w + "+")

    colored_bar_parts = []
    last_idx = 0

    for idx, item in enumerate(container.items):
        start_x = int(math.floor(item.main_offset * scale))
        size_x = max(1, int(round(item.target_main_size * scale)))
        end_x = min(canvas_w, start_x + size_x)
        color = colors[idx % len(colors)]

        # Isi blok item
        item_text = f"[{item.name}:{item.target_main_size:.0f}px]"
        for i in range(start_x, end_x):
            if i < canvas_w:
                bar[i] = "█"

        # Tulis label jika muat
        text_start = start_x + max(0, (size_x - len(item_text)) // 2)
        for c_idx, ch in enumerate(item_text):
            target = text_start + c_idx
            if 0 <= target < canvas_w and target < end_x:
                label_layer[target] = ch

    # Gabungkan bar dengan warna
    output_line = ""
    for i in range(canvas_w):
        # Tentukan kepemilikan item untuk warna
        assigned_color = CLR_RESET
        for idx, item in enumerate(container.items):
            start_x = int(math.floor(item.main_offset * scale))
            size_x = max(1, int(round(item.target_main_size * scale)))
            if start_x <= i < (start_x + size_x):
                assigned_color = colors[idx % len(colors)]
                break

        char_to_print = label_layer[i] if label_layer[i] != " " else (bar[i] if bar[i] != " " else ".")
        if char_to_print == ".":
            output_line += f"{CLR_GRAY}.{CLR_RESET}"
        else:
            output_line += f"{assigned_color}{char_to_print}{CLR_RESET}"

    print(f"|{output_line}|")
    print("+" + "-" * canvas_w + "+")


def execute_flex_pipeline(scenario_title: str, container: FlexContainer) -> None:
    """
    Eksekusi kalkulasi lengkap flex pipeline dan cetak metrik teknisnya.
    """
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== {scenario_title} ==={CLR_RESET}")
    print(f"Container Config: width={container.width}px, justify-content='{container.justify_content}', align-items='{container.align_items}'")
    
    # Jalankan algoritma
    container.resolve_flexible_lengths()
    container.resolve_positions()

    # Cetak tabel rincian item
    print(f"\n{CLR_BOLD}{'Item':<8} {'Basis':<10} {'Grow':<6} {'Shrink':<8} {'Min/Max':<14} {'Final Width':<14} {'Main Offset':<12}{CLR_RESET}")
    print("-" * 75)
    for it in container.items:
        min_max_str = f"{it.min_size:.0f}..{'∞' if math.isinf(it.max_size) else f'{it.max_size:.0f}'}"
        print(f"{it.name:<8} {it.flex_basis:>6.1f}px   {it.flex_grow:<6.1f} {it.flex_shrink:<8.1f} {min_max_str:<14} "
              f"{CLR_GREEN}{it.target_main_size:>7.2f}px{CLR_RESET}   {it.main_offset:>7.2f}px")

    render_ascii_layout(container)


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}----------------------------------------------------------------------{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}   LAB: Modern Flexbox Flow Mechanics & W3C Length Resolution Engine  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}----------------------------------------------------------------------{CLR_RESET}")

    # -------------------------------------------------------------
    # Skenario 1: Positive Free Space Distribution dengan Max Clamping
    # Item A, B, C memperebutkan sisa ruang 400px. Item B mentok di max-width.
    # -------------------------------------------------------------
    c1 = FlexContainer(width=800, height=100, justify_content="flex-start", align_items="center")
    c1.add_item(FlexItem(name="Box-A", flex_basis=100, flex_grow=1, max_size=500))
    c1.add_item(FlexItem(name="Box-B", flex_basis=100, flex_grow=2, max_size=220))  # Akan ter-freeze di pass 1
    c1.add_item(FlexItem(name="Box-C", flex_basis=200, flex_grow=1, max_size=500))
    execute_flex_pipeline("SCENARIO 1: Positive Space Distribution & Max Clamping", c1)

    # -------------------------------------------------------------
    # Skenario 2: Negative Free Space (Shrink Algorithm)
    # Total basis (300+300+400 = 1000px) melebihi container (600px).
    # Item menyusut proporsional dengan basis * flex_shrink.
    # -------------------------------------------------------------
    c2 = FlexContainer(width=600, height=100, justify_content="flex-start")
    c2.add_item(FlexItem(name="Tab-1", flex_basis=300, flex_shrink=1, min_size=100))
    c2.add_item(FlexItem(name="Tab-2", flex_basis=300, flex_shrink=2, min_size=50))
    c2.add_item(FlexItem(name="Tab-3", flex_basis=400, flex_shrink=1, min_size=280)) # Akan ter-clamp di min_size
    execute_flex_pipeline("SCENARIO 2: Negative Space & Weighted Shrink Clamping", c2)

    # -------------------------------------------------------------
    # Skenario 3: Justify-Content Mechanics (Space-Between)
    # Menguji distribusi sisa ruang horizontal ketika item tidak grow.
    # -------------------------------------------------------------
    c3 = FlexContainer(width=750, height=80, justify_content="space-between", align_items="center")
    c3.add_item(FlexItem(name="Nav-L", flex_basis=120, flex_grow=0, flex_shrink=0))
    c3.add_item(FlexItem(name="Nav-M", flex_basis=150, flex_grow=0, flex_shrink=0))
    c3.add_item(FlexItem(name="Nav-R", flex_basis=100, flex_grow=0, flex_shrink=0))
    execute_flex_pipeline("SCENARIO 3: Justification Mechanics (Space-Between)", c3)

    print(f"\n{CLR_GREEN}{CLR_BOLD}✔ Seluruh simulasi kalkulasi Flexbox W3C berhasil dijalankan.{CLR_RESET}\n")


if __name__ == "__main__":
    main()