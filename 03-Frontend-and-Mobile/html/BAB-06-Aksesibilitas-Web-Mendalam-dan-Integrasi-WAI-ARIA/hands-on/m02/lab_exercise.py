#!/usr/bin/env python3
"""
Lab Hands-on: Deep Web Accessibility (A11y) & WAI-ARIA Engine
Bab 06: Aksesibilitas Web Mendalam & Integrasi WAI-ARIA - Modul 02 Deep Dive

Skrip ini memodelkan Accessibility Engine browser secara mandiri:
1. Mem-parsing DOM HTML ke dalam Accessibility Tree (AXTree) semantik.
2. Menghitung 'Accessible Name' dan 'Accessible Description' (AccName Computation).
3. Melakukan audit komprehensif WCAG 2.1 (Level A, AA) & WAI-ARIA 1.2 state validation.
4. Menghitung rasio kontras warna sRGB matematis (WCAG Relative Luminance).
5. Mensimulasikan Screen Reader Virtual Buffer Speech Dispatcher.
"""

import sys
import re
from html.parser import HTMLParser
from typing import List, Dict, Optional, Tuple

# ANSI Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"
C_GRAY = "\033[90m"


class AXNode:
    """Node semantik dalam browser Accessibility Tree (AXTree)."""
    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional['AXNode'] = None):
        self.tag = tag.lower()
        self.attrs = attrs
        self.parent = parent
        self.children: List['AXNode'] = []
        self.text_content: str = ""
        
        # Computed Accessibility Properties
        self.role: str = self._compute_role()
        self.accessible_name: str = ""
        self.is_ignored: bool = False
        self.states: Dict[str, str] = {}

    def _compute_role(self) -> str:
        """Memetakan tag HTML standar ke Role WAI-ARIA implisit atau eksplisit."""
        if "role" in self.attrs:
            return self.attrs["role"].strip()
            
        implicit_roles = {
            "a": "link" if "href" in self.attrs else "generic",
            "button": "button",
            "img": "img",
            "input": self._input_role(),
            "nav": "navigation",
            "main": "main",
            "header": "banner",
            "footer": "contentinfo",
            "h1": "heading", "h2": "heading", "h3": "heading",
            "ul": "list", "ol": "list", "li": "listitem",
            "dialog": "dialog"
        }
        return implicit_roles.get(self.tag, "generic")

    def _input_role(self) -> str:
        itype = self.attrs.get("type", "text").lower()
        return "checkbox" if itype == "checkbox" else "textbox"


class AccessibilityTreeBuilder(HTMLParser):
    """HTML Parser yang membangun Accessibility Tree dan mengumpulkan metadata."""
    def __init__(self):
        super().__init__()
        self.root = AXNode("document", {})
        self.current_node = self.root
        self.id_map: Dict[str, AXNode] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        attr_dict = dict(attrs)
        new_node = AXNode(tag, attr_dict, parent=self.current_node)
        
        if "id" in attr_dict:
            self.id_map[attr_dict["id"]] = new_node
            
        self.current_node.children.append(new_node)
        # Handle void elements yang tidak memiliki closing tag
        if tag not in ["img", "input", "br", "hr", "meta", "link"]:
            self.current_node = new_node

    def handle_endtag(self, tag: str):
        if tag not in ["img", "input", "br", "hr", "meta", "link"]:
            if self.current_node.parent:
                self.current_node = self.current_node.parent

    def handle_data(self, data: str):
        cleaned = data.strip()
        if cleaned:
            self.current_node.text_content += (" " + cleaned if self.current_node.text_content else cleaned)

    def finalize(self):
        """Kompilasi Accessible Name Computation (W3C AccName Spec)."""
        self._compute_acc_names(self.root)

    def _compute_acc_names(self, node: AXNode):
        # 1. aria-hidden nodes diabaikan dari pohon aksesibilitas
        if node.attrs.get("aria-hidden") == "true":
            node.is_ignored = True

        # 2. aria-labelledby priority
        if "aria-labelledby" in node.attrs:
            ref_ids = node.attrs["aria-labelledby"].split()
            label_parts = [self.id_map[ref].text_content for ref in ref_ids if ref in self.id_map]
            node.accessible_name = " ".join(label_parts)
            
        # 3. aria-label priority
        elif "aria-label" in node.attrs:
            node.accessible_name = node.attrs["aria-label"]
            
        # 4. Native semantic attributes (alt untuk img, placeholder/value untuk input)
        elif node.tag == "img":
            node.accessible_name = node.attrs.get("alt", "")
        elif node.tag == "input" and "placeholder" in node.attrs:
            node.accessible_name = node.attrs["placeholder"]
            
        # 5. Descendant text content computation
        elif not node.accessible_name and node.text_content:
            node.accessible_name = node.text_content

        # Ekstraksi status ARIA (aria-expanded, aria-checked, aria-disabled)
        for attr, val in node.attrs.items():
            if attr.startswith("aria-") and attr not in ["aria-label", "aria-labelledby", "aria-hidden"]:
                node.states[attr] = val

        for child in node.children:
            self._compute_acc_names(child)


class WCAGColorContrast:
    """Kalkulator Rasio Kontras Luminansi Relatif WCAG 2.1."""
    @staticmethod
    def _srgb_to_linear(c_byte: int) -> float:
        c = c_byte / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    @classmethod
    def relative_luminance(cls, hex_rgb: str) -> float:
        hex_clean = hex_rgb.lstrip("#")
        r, g, b = (int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
        r_lin = cls._srgb_to_linear(r)
        g_lin = cls._srgb_to_linear(g)
        b_lin = cls._srgb_to_linear(b)
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    @classmethod
    def contrast_ratio(cls, hex_fg: str, hex_bg: str) -> float:
        l1 = cls.relative_luminance(hex_fg)
        l2 = cls.relative_luminance(hex_bg)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)


class A11yAuditor:
    """Mesin Audit Validasi WCAG & Integritas WAI-ARIA."""
    def __init__(self):
        self.findings: List[Dict[str, str]] = []

    def audit(self, root: AXNode):
        self._traverse(root)

    def _traverse(self, node: AXNode):
        if node.tag != "document":
            self._check_node(node)
        for child in node.children:
            self._traverse(child)

    def _check_node(self, node: AXNode):
        # Rule 1: Non-text Content (WCAG 1.1.1 Level A)
        if node.tag == "img":
            if "alt" not in node.attrs:
                self.findings.append({
                    "level": "VIOLATION",
                    "code": "WCAG_1.1.1",
                    "msg": f"Tag <img src='{node.attrs.get('src', '')}'> kehilangan atribut 'alt'."
                })
            elif node.attrs["alt"] == "" and node.attrs.get("role") != "presentation":
                self.findings.append({
                    "level": "INFO",
                    "code": "WCAG_1.1.1_DECORATIVE",
                    "msg": f"Gambar dengan alt='' diperlakukan sebagai dekoratif murni."
                })

        # Rule 2: Interactive Element Accessible Name (WCAG 4.1.2 Level A)
        if node.role in ["button", "link"]:
            if not node.accessible_name.strip():
                self.findings.append({
                    "level": "VIOLATION",
                    "code": "WCAG_4.1.2",
                    "msg": f"Elemen interaktif <{node.tag} role='{node.role}'> tidak memiliki Accessible Name."
                })

        # Rule 3: WAI-ARIA Mandatory Attributes
        if node.role == "checkbox":
            if "aria-checked" not in node.states:
                self.findings.append({
                    "level": "VIOLATION",
                    "code": "WAI_ARIA_STATE_MISSING",
                    "msg": "Elemen dengan role='checkbox' wajib menyertakan atribut 'aria-checked'."
                })

        # Rule 4: Keyboard Trap & Interactive Div Anti-Pattern
        if node.tag in ["div", "span"] and node.role in ["button", "link"]:
            if "tabindex" not in node.attrs:
                self.findings.append({
                    "level": "WARNING",
                    "code": "A11Y_KEYBOARD_NAV",
                    "msg": f"Elemen semantik non-interaktif <{node.tag}> dijadikan '{node.role}' tanpa 'tabindex'."
                })


def simulate_screen_reader(node: AXNode, indent: int = 0):
    """Simulasi virtual buffer screen reader membaca DOM yang dinavigasi pengguna."""
    if node.is_ignored:
        return

    if node.role not in ["generic", "document"]:
        prefix = "  " * indent
        name_str = f"\"{node.accessible_name}\"" if node.accessible_name else "<Unnamed>"
        state_str = f" [{', '.join(f'{k}={v}' for k, v in node.states.items())}]" if node.states else ""
        print(f"{C_BLUE}{prefix}▶ {C_BOLD}{node.role.upper()}:{C_RESET} {name_str}{C_YELLOW}{state_str}{C_RESET}")

    for child in node.children:
        simulate_screen_reader(child, indent + (1 if node.role != "generic" else 0))


def run_pipeline():
    sample_html = """
    <header>
        <h1 id="app-title">Portal Pelayanan Publik</h1>
    </header>
    <main>
        <img src="banner.jpg">
        <img src="divider.png" alt="" role="presentation">
        <section>
            <div id="btn-lbl">Kirim Data</div>
            <div role="button" aria-labelledby="btn-lbl"></div>
            <button aria-label="Tutup Dialog">X</button>
            <button></button>
            <div role="checkbox" aria-checked="mixed">Saya menyetujui S&K</div>
            <div role="checkbox">Ingat Akun Saya</div>
        </section>
        <footer aria-hidden="true">
            <p>Konten rahasia internal</p>
        </footer>
    </main>
    """

    print(f"{C_BOLD}{C_MAGENTA}======================================================================{C_RESET}")
    print(f"{C_BOLD}{C_MAGENTA}     LAB A11Y & WAI-ARIA DEEP DIVE: ACCESSIBILITY TREE COMPILATION    {C_RESET}")
    print(f"{C_BOLD}{C_MAGENTA}======================================================================{C_RESET}\n")

    # 1. Parsing & Tree Construction
    parser = AccessibilityTreeBuilder()
    parser.feed(sample_html)
    parser.finalize()

    # 2. Screen Reader Virtual Speech Simulator
    print(f"{C_CYAN}{C_BOLD}[1] SIMULASI OUTPUT SPEECH SCREEN READER (VIRTUAL BUFFER){C_RESET}")
    print("-" * 70)
    simulate_screen_reader(parser.root)
    print("-" * 70 + "\n")

    # 3. Rule Violations Audit
    auditor = A11yAuditor()
    auditor.audit(parser.root)

    print(f"{C_CYAN}{C_BOLD}[2] WCAG 2.1 & WAI-ARIA 1.2 AUTOMATED AUDIT DIAGNOSTICS{C_RESET}")
    print("-" * 70)
    for issue in auditor.findings:
        badge_color = C_RED if issue["level"] == "VIOLATION" else C_YELLOW if issue["level"] == "WARNING" else C_GRAY
        print(f"{badge_color}[{issue['level']}]{C_RESET} {C_BOLD}{issue['code']}{C_RESET}: {issue['msg']}")
    print("-" * 70 + "\n")

    # 4. Color Contrast Engine (WCAG 1.4.3 Check)
    print(f"{C_CYAN}{C_BOLD}[3] WCAG COLOR CONTRAST RATIO MATHEMATICAL BENCHMARK{C_RESET}")
    print("-" * 70)
    test_palette = [
        ("#FFFFFF", "#000000", "Teks Putih di Latar Hitam"),
        ("#777777", "#FFFFFF", "Teks Abu-abu redup di Latar Putih"),
        ("#3B82F6", "#FFFFFF", "Primary Blue di Latar Putih"),
        ("#005A9C", "#FFFFFF", "W3C Blue di Latar Putih"),
    ]

    for fg, bg, desc in test_palette:
        ratio = WCAGColorContrast.contrast_ratio(fg, bg)
        aa_normal = ratio >= 4.5
        aa_large = ratio >= 3.0
        
        status = f"{C_GREEN}PASS (AA){C_RESET}" if aa_normal else (
            f"{C_YELLOW}PASS (Large Only){C_RESET}" if aa_large else f"{C_RED}FAIL{C_RESET}"
        )
        print(f"Palette: {desc} ({fg} on {bg})")
        print(f"  └─ Contrast Ratio: {C_BOLD}{ratio:.2f}:1{C_RESET} -> Status: {status}")

    print(f"\n{C_GREEN}{C_BOLD}✔ Siklus Parsing A11y Tree dan Analisis Integritas ARIA Berhasil.{C_RESET}")


if __name__ == "__main__":
    run_pipeline()
