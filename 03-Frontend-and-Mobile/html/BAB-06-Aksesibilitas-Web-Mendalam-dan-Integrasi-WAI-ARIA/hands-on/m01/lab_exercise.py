#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB 06 - Aksesibilitas Web Mendalam & Integrasi WAI-ARIA
Simulasi Teknis Interaktif: Accessibility Tree, AccName Computation, & WCAG Contrast.
"""

import sys
import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# ANSI Terminal Color Palette
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
    BG_DARK = "\033[40m"


@dataclass
class AccessibleNode:
    tag: str
    role: str
    attributes: Dict[str, str] = field(default_factory=dict)
    inner_text: str = ""
    children: List['AccessibleNode'] = field(default_factory=list)

    def get_attr(self, name: str) -> Optional[str]:
        return self.attributes.get(name)


class WAIARIAEngine:
    """Simulasi mesin Accessibility Tree dan komputasi Accessible Name."""

    # Default implicit ARIA roles for standard HTML elements
    IMPLICIT_ROLES = {
        "button": "button",
        "a": "link",
        "input[type=checkbox]": "checkbox",
        "input[type=radio]": "radio",
        "input[type=text]": "textbox",
        "nav": "navigation",
        "main": "main",
        "header": "banner",
        "footer": "contentinfo",
        "aside": "complementary",
        "h1": "heading",
        "h2": "heading",
        "h3": "heading",
        "ul": "list",
        "li": "listitem",
        "dialog": "dialog"
    }

    @classmethod
    def resolve_role(cls, node: AccessibleNode) -> str:
        # Explicit role has precedence
        explicit_role = node.get_attr("role")
        if explicit_role:
            return explicit_role

        # Implicit mapping based on tag & attributes
        tag_key = node.tag
        if node.tag == "input" and "type" in node.attributes:
            tag_key = f"input[type={node.attributes['type']}]"

        return cls.IMPLICIT_ROLES.get(tag_key, "generic")

    @classmethod
    def compute_accessible_name(cls, node: AccessibleNode, element_lookup: Dict[str, AccessibleNode]) -> str:
        """
        Implementasi W3C Accessible Name and Description Computation (AccName 1.2):
        1. aria-labelledby
        2. aria-label
        3. Native label (e.g. alt text for img, subtree text for button/link)
        4. title attribute fallback
        """
        # Step 1: aria-labelledby (referensi id lain)
        labelledby = node.get_attr("aria-labelledby")
        if labelledby:
            target_ids = labelledby.split()
            accumulated = []
            for tid in target_ids:
                if tid in element_lookup:
                    accumulated.append(element_lookup[tid].inner_text.strip())
            if accumulated:
                return " ".join(accumulated)

        # Step 2: aria-label
        aria_label = node.get_attr("aria-label")
        if aria_label:
            return aria_label.strip()

        # Step 3: Native labeling
        if node.tag == "img" and node.get_attr("alt") is not None:
            return node.get_attr("alt").strip()

        if node.inner_text.strip():
            return node.inner_text.strip()

        # Step 4: Fallback attribute title
        title_attr = node.get_attr("title")
        if title_attr:
            return title_attr.strip()

        return ""


class ContrastValidator:
    """Kalkulator rasio kontras WCAG 2.1 (Relative Luminance)."""

    @staticmethod
    def hex_to_rgb(hex_code: str):
        hex_code = hex_code.lstrip("#")
        if len(hex_code) == 3:
            hex_code = "".join([c * 2 for c in hex_code])
        return tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))

    @classmethod
    def relative_luminance(cls, r: int, g: int, b: int) -> float:
        channels = []
        for val in (r, g, b):
            s = val / 255.0
            if s <= 0.04045:
                channels.append(s / 12.92)
            else:
                channels.append(((s + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    @classmethod
    def calculate_contrast(cls, fg_hex: str, bg_hex: str) -> float:
        rgb1 = cls.hex_to_rgb(fg_hex)
        rgb2 = cls.hex_to_rgb(bg_hex)
        l1 = cls.relative_luminance(*rgb1)
        l2 = cls.relative_luminance(*rgb2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)


def print_banner():
    banner = f"""{Color.BOLD}{Color.CYAN}
======================================================================
  SIMULATOR AKSESIBILITAS WEB & WAI-ARIA ACCNAME COMPUTATION ENGINE
  BAB 06: Aksesibilitas Web Mendalam dan Integrasi WAI-ARIA
======================================================================{Color.RESET}"""
    print(banner)


def run_accname_simulation():
    print(f"\n{Color.BOLD}{Color.YELLOW}[1] SIMULASI ACCESSIBLE NAME COMPUTATION (AccName 1.2){Color.RESET}")
    print(f"{Color.DIM}Mengevaluasi bagaimana screen reader membentuk nama aksesibel dari tree node.{Color.RESET}\n")

    # Mock elements repository
    elements: Dict[str, AccessibleNode] = {
        "cart-heading": AccessibleNode("h2", "heading", inner_text="Keranjang Belanja"),
        "badge-count": AccessibleNode("span", "generic", inner_text="3 barang"),
        "btn-1": AccessibleNode(
            tag="button",
            role="button",
            attributes={"aria-labelledby": "cart-heading badge-count"},
            inner_text="Checkout"
        ),
        "btn-2": AccessibleNode(
            tag="button",
            role="button",
            attributes={"aria-label": "Tutup formulir pendaftaran modal"},
            inner_text="X"
        ),
        "img-1": AccessibleNode(
            tag="img",
            role="img",
            attributes={"src": "banner.jpg", "alt": "Diagram arsitektur Micro-Frontend v2"}
        ),
        "bad-btn": AccessibleNode(
            tag="div",
            role="generic",
            attributes={"class": "clickable-icon"},
            inner_text=""
        )
    }

    test_cases = [
        ("Tombol dengan aria-labelledby majemuk", elements["btn-1"]),
        ("Tombol dengan aria-label overriding teks 'X'", elements["btn-2"]),
        ("Elemen Gambar dengan Native alt attribute", elements["img-1"]),
        ("Div Clickable Tanpa Semantik (Anti-Pattern)", elements["bad-btn"]),
    ]

    for label, node in test_cases:
        computed_role = WAIARIAEngine.resolve_role(node)
        acc_name = WAIARIAEngine.compute_accessible_name(node, elements)

        print(f"  {Color.WHITE}-> Uji Skenario: {Color.BOLD}{label}{Color.RESET}")
        print(f"     HTML Tag     : <{node.tag}>")
        print(f"     Computed Role: {Color.MAGENTA}{computed_role}{Color.RESET}")
        if acc_name:
            print(f"     AccName Name : {Color.GREEN}'{acc_name}'{Color.RESET}")
            print(f"     Status Screen Reader: {Color.GREEN}ACCESSIBLE (OK){Color.RESET}\n")
        else:
            print(f"     AccName Name : {Color.RED}[KOSONG / UNNAMED]{Color.RESET}")
            print(f"     Status Screen Reader: {Color.RED}VIOLATION: Unnamed interactive element!{Color.RESET}\n")


def run_contrast_audit():
    print(f"{Color.BOLD}{Color.YELLOW}[2] SIMULASI WCAG 2.1 CONTRAST RATIO VALIDATOR{Color.RESET}")
    print(f"{Color.DIM}Standar WCAG 2.1: Min 4.5:1 untuk teks normal (AA), 7.0:1 (AAA), 3.0:1 teks besar/UI.{Color.RESET}\n")

    color_pairs = [
        ("Teks Abu Terang di Background Putih (Bad UX)", "#94A3B8", "#FFFFFF"),
        ("Teks Abu Gelap di Background Putih (Brand Safe)", "#334155", "#FFFFFF"),
        ("Teks Biru Link di Background Putih", "#1D4ED8", "#FFFFFF"),
        ("Teks Kuning di Background Putih (Danger)", "#EAB308", "#FFFFFF"),
        ("Teks Putih di Latar Gelap (Dark Mode Primary)", "#F8FAFC", "#0F172A"),
    ]

    print(f"  {'Foreground':<12} {'Background':<12} {'Rasio':<10} {'WCAG AA':<10} {'WCAG AAA':<10}")
    print(f"  {'-'*12} {'-'*12} {'-'*10} {'-'*10} {'-'*10}")

    for name, fg, bg in color_pairs:
        ratio = ContrastValidator.calculate_contrast(fg, bg)
        pass_aa = ratio >= 4.5
        pass_aaa = ratio >= 7.0

        aa_badge = f"{Color.GREEN}PASS{Color.RESET}" if pass_aa else f"{Color.RED}FAIL{Color.RESET}"
        aaa_badge = f"{Color.GREEN}PASS{Color.RESET}" if pass_aaa else f"{Color.RED}FAIL{Color.RESET}"

        print(f"  {fg:<12} {bg:<12} {ratio:>6.2f}:1   {aa_badge:<19} {aaa_badge:<19}")
        print(f"  {Color.DIM}(Deskripsi: {name}){Color.RESET}\n")


def run_aria_live_demo():
    print(f"{Color.BOLD}{Color.YELLOW}[3] SIMULASI WAI-ARIA LIVE REGION (polite vs assertive){Color.RESET}")
    events = [
        ("pemberitahuan-1", "polite", "Barang berhasil ditambahkan ke keranjang belanja."),
        ("peringatan-urgent", "assertive", "Koneksi internet terputus! Data belum tersimpan.")
    ]

    for elem_id, live_type, message in events:
        badge_color = Color.CYAN if live_type == "polite" else Color.RED
        print(f"  [DOM Event] Element ID: #{elem_id}")
        print(f"  Attribute : {badge_color}aria-live=\"{live_type}\"{Color.RESET}")
        if live_type == "polite":
            behavior = "Screen reader menunggu antrian pidato saat ini selesai sebelum mengumumkan."
        else:
            behavior = "Screen reader langsung menginterupsi suara yang sedang dibaca!"
        print(f"  Perilaku  : {Color.WHITE}{behavior}{Color.RESET}")
        print(f"  Suara SR  : \"{Color.BOLD}{message}{Color.RESET}\"\n")


def main():
    print_banner()
    run_accname_simulation()
    run_contrast_audit()
    run_aria_live_demo()
    print(f"{Color.BOLD}{Color.GREEN}Semua modul uji coba simulasi WAI-ARIA selesai dijalankan.{Color.RESET}\n")


if __name__ == "__main__":
    main()
