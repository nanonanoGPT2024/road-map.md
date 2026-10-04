#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Fondasi & Arsitektur CSS
Topik:
  1. Penghitungan Specificity Vector (Inline, ID, Class/Attr/Pseudo, Element)
  2. Resolusi Cascade Engine (Origin, Specificity, Source Order)
  3. Box Model Calculation (content-box vs border-box)
"""

import sys
import re
from typing import Dict, List, Tuple


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
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def print_banner(title: str) -> None:
    border = "=" * 65
    print(f"\n{ANSI.CYAN}{ANSI.BOLD}{border}")
    print(f" {title.center(63)} ")
    print(f"{border}{ANSI.RESET}\n")


def calculate_specificity(selector: str, is_inline: bool = False) -> Tuple[int, int, int, int]:
    """
    Menghitung Specificity Vector: (Inline, ID, Class, Type)
    - a: style inline (1 jika inline, 0 jika selector)
    - b: ID selector (#id)
    - c: Class (.class), attribute ([type=text]), pseudo-class (:hover)
    - d: Type/element (div, p, span), pseudo-element (::before)
    """
    if is_inline:
        return (1, 0, 0, 0)

    # Bersihkan spasi berlebih
    s = selector.strip()

    # Hitung pseudo-elements (::after, ::before)
    pseudo_elements = len(re.findall(r"::[a-zA-Z0-9_-]+", s))
    s_clean = re.sub(r"::[a-zA-Z0-9_-]+", "", s)

    # Hitung IDs (#main, #nav)
    ids = len(re.findall(r"#[a-zA-Z0-9_-]+", s_clean))
    s_clean = re.sub(r"#[a-zA-Z0-9_-]+", "", s_clean)

    # Hitung Classes (.btn, .active)
    classes = len(re.findall(r"\.[a-zA-Z0-9_-]+", s_clean))
    s_clean = re.sub(r"\.[a-zA-Z0-9_-]+", "", s_clean)

    # Hitung Attributes ([type="text"])
    attributes = len(re.findall(r"\[[^\]]+\]", s_clean))
    s_clean = re.sub(r"\[[^\]]+\]", "", s_clean)

    # Hitung Pseudo-classes (:hover, :focus, kecuali :not/is/where)
    pseudo_classes = len(re.findall(r":[a-zA-Z0-9_-]+", s_clean))
    s_clean = re.sub(r":[a-zA-Z0-9_-]+", "", s_clean)

    # Hitung Type / Element selectors
    elements = len(re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]*\b", s_clean))

    c_score = classes + attributes + pseudo_classes
    d_score = elements + pseudo_elements

    return (0, ids, c_score, d_score)


def format_specificity(spec: Tuple[int, int, int, int]) -> str:
    a, b, c, d = spec
    return (
        f"{ANSI.RED}[{a}]{ANSI.RESET},"
        f"{ANSI.YELLOW}[{b}]{ANSI.RESET},"
        f"{ANSI.CYAN}[{c}]{ANSI.RESET},"
        f"{ANSI.GREEN}[{d}]{ANSI.RESET}"
    )


class CSSRule:
    def __init__(self, selector: str, properties: Dict[str, str], origin: str = "author", order: int = 0):
        self.selector = selector
        self.properties = properties
        self.origin = origin  # 'user-agent', 'user', 'author'
        self.order = order
        self.specificity = calculate_specificity(selector)

    def __repr__(self):
        return f"<CSSRule '{self.selector}' {self.specificity}>"


def simulate_cascade(rules: List[CSSRule], target_property: str) -> None:
    print_banner(f"CASCADE ENGINE RESOLUTION: '{target_property}'")
    print(f"{ANSI.BOLD}{'Order':<6} | {'Selector':<30} | {'Specificity':<20} | {'Value':<15}{ANSI.RESET}")
    print("-" * 75)

    candidates = []
    for r in rules:
        if target_property in r.properties:
            candidates.append(r)
            val = r.properties[target_property]
            print(f"{r.order:<6} | {r.selector:<30} | {format_specificity(r.specificity):<30} | {ANSI.BOLD}{val:<15}{ANSI.RESET}")

    if not candidates:
        print(f"{ANSI.RED}Tidak ada aturan untuk properti '{target_property}'{ANSI.RESET}")
        return

    # Sorter: Specificity descending, lalu Order descending (aturan paling bawah menang jika specificity imbang)
    def sort_key(rule: CSSRule):
        return (rule.specificity, rule.order)

    sorted_rules = sorted(candidates, key=sort_key)
    winner = sorted_rules[-1]

    print("-" * 75)
    print(f"\n{ANSI.GREEN}{ANSI.BOLD}[PEMENANG CASCADE]{ANSI.RESET}")
    print(f"  Selector     : {ANSI.CYAN}{winner.selector}{ANSI.RESET}")
    print(f"  Specificity  : {format_specificity(winner.specificity)}")
    print(f"  Source Order : Baris index #{winner.order}")
    print(f"  Computed Val : {ANSI.YELLOW}{winner.properties[target_property]}{ANSI.RESET}\n")


def simulate_box_model(box_sizing: str, width: float, height: float, padding: float, border: float, margin: float) -> None:
    print_banner(f"BOX MODEL SIMULATOR ({box_sizing.upper()})")

    if box_sizing == "content-box":
        content_w = width
        content_h = height
        total_w = content_w + (padding * 2) + (border * 2)
        total_h = content_h + (padding * 2) + (border * 2)
    else:  # border-box
        content_w = max(0.0, width - (padding * 2) - (border * 2))
        content_h = max(0.0, height - (padding * 2) - (border * 2))
        total_w = width
        total_h = height

    outer_w = total_w + (margin * 2)
    outer_h = total_h + (margin * 2)

    print(f"{ANSI.BOLD}Input CSS Dimensi:{ANSI.RESET}")
    print(f"  width: {width}px | height: {height}px | padding: {padding}px | border: {border}px | margin: {margin}px\n")

    print(f"{ANSI.BOLD}Hasil Kalkulasi Fisik Layout di Layar:{ANSI.RESET}")
    print(f"  {ANSI.BLUE}+-- Margin Area     : {outer_w}px x {outer_h}px{ANSI.RESET}")
    print(f"  |   {ANSI.YELLOW}+-- Border Area     : {total_w}px x {total_h}px{ANSI.RESET}")
    print(f"  |   |   {ANSI.GREEN}+-- Padding Area    : {content_w + padding*2}px x {content_h + padding*2}px{ANSI.RESET}")
    print(f"  |   |   |   {ANSI.WHITE}{ANSI.BOLD}+-- Content Box : {content_w}px x {content_h}px{ANSI.RESET}")
    print()


def run_interactive_menu():
    rules_db = [
        CSSRule("div", {"color": "black", "font-size": "14px"}, order=1),
        CSSRule(".card p", {"color": "gray", "font-size": "16px"}, order=2),
        CSSRule("p.highlight", {"color": "blue"}, order=3),
        CSSRule("#main-content p.highlight", {"color": "purple"}, order=4),
        CSSRule("body #main-content p.highlight", {"color": "red"}, order=5),
        CSSRule(".highlight", {"color": "green"}, order=6),
    ]

    while True:
        print_banner("LAB M01: CSS FOUNDATIONS & ARCHITECTURE ENGINE")
        print(f"{ANSI.BOLD}Pilih mode simulasi:{ANSI.RESET}")
        print(" [1] Specificity Vector Calculator (Selector Bebas)")
        print(" [2] Cascade Resolution Engine Demo")
        print(" [3] Box Model Comparison (content-box vs border-box)")
        print(" [4] Jalankan Audit Lengkap Semua Modul")
        print(" [0] Keluar")
        print()

        try:
            choice = input(f"{ANSI.YELLOW}Pilihan Anda (0-4): {ANSI.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{ANSI.CYAN}Lab diakhiri.{ANSI.RESET}")
            sys.exit(0)

        if choice == "0":
            print(f"{ANSI.CYAN}Sampai jumpa di Lab berikutnya!{ANSI.RESET}")
            break
        elif choice == "1":
            print(f"\n{ANSI.BOLD}Format Specificity: (A: Inline, B: ID, C: Class/Attr, D: Element){ANSI.RESET}")
            sample = input("Masukkan CSS Selector (contoh: 'header #nav ul.menu > li.active a:hover'): ").strip()
            if sample:
                spec = calculate_specificity(sample)
                print(f"\nSelector   : {ANSI.CYAN}{sample}{ANSI.RESET}")
                print(f"Specificity: {format_specificity(spec)}")
                print(f"Detail     : (Inline={spec[0]}, ID={spec[1]}, Class/Attr/Pseudo={spec[2]}, Element={spec[3]})\n")
        elif choice == "2":
            simulate_cascade(rules_db, "color")
        elif choice == "3":
            simulate_box_model("content-box", width=300, height=150, padding=20, border=5, margin=15)
            simulate_box_model("border-box", width=300, height=150, padding=20, border=5, margin=15)
        elif choice == "4":
            print_banner("AUDIT ENGINE: JALANKAN SEMUA UJI LAB")
            test_selectors = [
                "body",
                ".btn.btn-primary",
                "#navbar .nav-item a:hover",
                "div#app main.container article.post p::first-line",
            ]
            for sel in test_selectors:
                sp = calculate_specificity(sel)
                print(f"Selector: {sel:<50} => {format_specificity(sp)}")

            simulate_cascade(rules_db, "color")
            simulate_box_model("content-box", 250, 100, 15, 2, 10)
            simulate_box_model("border-box", 250, 100, 15, 2, 10)
        else:
            print(f"{ANSI.RED}Pilihan tidak valid! Silakan masukkan 0, 1, 2, 3, atau 4.{ANSI.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Non-interactive automated mode
        print_banner("RUNNING M01 SIMULATION IN AUTOMATED MODE")
        simulate_cascade([
            CSSRule("p", {"color": "black"}, order=1),
            CSSRule(".text", {"color": "blue"}, order=2),
            CSSRule("#main .text", {"color": "red"}, order=3),
        ], "color")
        simulate_box_model("content-box", 200, 100, 10, 5, 10)
        simulate_box_model("border-box", 200, 100, 10, 5, 10)
        print(f"{ANSI.GREEN}Auto-test selesai dengan sukses.{ANSI.RESET}")
    else:
        run_interactive_menu()
