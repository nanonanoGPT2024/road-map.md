#!/usr/bin/env python3
"""
Lab Hands-on: Semantik HTML5, Aksesibilitas (a11y) & Engine Pohon DOM
Modul 02 Deep Dive - 01-Core-Foundations

Deskripsi Teknis:
Script ini memodelkan cara kerja internal Browser Engine dalam:
1. Mem-parsing string HTML menjadi struktur data DOM Tree (In-Memory Object Model).
2. Melakukan komputasi pemetaan DOM Tree menjadi Accessibility Tree (a11y tree).
3. Melakukan audit aksesibilitas otomatis (A11y Linter): heading order, missing alt, interactive semantics.
4. Mensimulasikan output navigasi Screen Reader berbasis Virtual Landmark Buffer.
"""

from html.parser import HTMLParser
from typing import List, Dict, Optional, Tuple
import sys

# Konstanta ANSI Color untuk Terminal Dashboard
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"

# Mapping Implisit Semantik HTML5 ke ARIA Roles berdasarkan spesifikasi W3C HTML-AAM
HTML5_TO_ARIA_ROLES = {
    "header": "banner",
    "nav": "navigation",
    "main": "main",
    "article": "article",
    "section": "region",
    "aside": "complementary",
    "footer": "contentinfo",
    "button": "button",
    "a": "link",
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "h5": "heading",
    "h6": "heading",
    "img": "img",
    "p": "paragraph",
    "ul": "list",
    "li": "listitem",
}

class DOMNode:
    """Representasi Node dalam Struktur Data Document Object Model (DOM)."""
    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional['DOMNode'] = None):
        self.tag = tag.lower()
        self.attrs = attrs
        self.parent = parent
        self.children: List['DOMNode'] = []
        self.text_content: str = ""

    def append_child(self, child: 'DOMNode'):
        child.parent = self
        self.children.append(child)

    def is_text_node(self) -> bool:
        return self.tag == "#text"


class AccessibilityNode:
    """Node pada Accessibility Tree yang dikonsumsi oleh Assistive Technologies (AT)."""
    def __init__(self, role: str, name: str, node_ref: DOMNode):
        self.role = role
        self.name = name.strip()
        self.node_ref = node_ref
        self.children: List['AccessibilityNode'] = []

    def append_child(self, child: 'AccessibilityNode'):
        self.children.append(child)


class DOMTreeBuilder(HTMLParser):
    """HTML Tokenizer & Tree Construction Engine menggunakan State Machine internal."""
    def __init__(self):
        super().__init__()
        self.root = DOMNode("document", {})
        self.current = self.root
        self._self_closing_tags = {"img", "br", "hr", "input", "meta", "link"}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k: v or "" for k, v in attrs}
        new_node = DOMNode(tag, attr_dict, self.current)
        self.current.append_child(new_node)
        if tag.lower() not in self._self_closing_tags:
            self.current = new_node

    def handle_endtag(self, tag: str):
        if self.current != self.root and self.current.tag == tag.lower():
            if self.current.parent:
                self.current = self.current.parent

    def handle_data(self, data: str):
        cleaned = data.strip()
        if cleaned:
            text_node = DOMNode("#text", {}, self.current)
            text_node.text_content = cleaned
            self.current.append_child(text_node)


class AccessibilityEngine:
    """
    Engine untuk mengonversi DOM Tree menjadi Accessibility Tree
    dan menjalankan audit kepatuhan WCAG 2.1 / Semantic Health.
    """
    @classmethod
    def compute_accessible_name(cls, node: DOMNode) -> str:
        """Kalkulasi Accessible Name Computation (aria-label > alt > textContent)."""
        if "aria-label" in node.attrs:
            return node.attrs["aria-label"]
        if node.tag == "img" and "alt" in node.attrs:
            return node.attrs["alt"]
        
        # Recursive text accumulator
        texts = []
        for child in node.children:
            if child.is_text_node():
                texts.append(child.text_content)
            else:
                texts.append(cls.compute_accessible_name(child))
        return " ".join(filter(None, texts))

    @classmethod
    def build_a11y_tree(cls, dom_node: DOMNode) -> Optional[AccessibilityNode]:
        """Rekursi untuk membangun Accessibility Tree, mengabaikan non-semantic wrappers."""
        if dom_node.is_text_node():
            return None

        role = dom_node.attrs.get("role")
        if not role:
            role = HTML5_TO_ARIA_ROLES.get(dom_node.tag, "generic")

        name = cls.compute_accessible_name(dom_node)
        a11y_node = AccessibilityNode(role=role, name=name, node_ref=dom_node)

        for child in dom_node.children:
            child_a11y = cls.build_a11y_tree(child)
            if child_a11y:
                a11y_node.append_child(child_a11y)

        return a11y_node


class AccessibilityAuditor:
    """Static Analyzer untuk mendeteksi pelanggaran aksesibilitas & semantik."""
    def __init__(self):
        self.violations: List[Dict[str, str]] = []
        self.heading_levels: List[int] = []

    def audit(self, node: DOMNode):
        """Menjalankan traversal preorder untuk auditing."""
        tag = node.tag

        # Check 1: Image Accessibility
        if tag == "img":
            if "alt" not in node.attrs:
                self.violations.append({
                    "rule": "WCAG 1.1.1 Non-text Content",
                    "severity": "CRITICAL",
                    "node": f"<{tag} src='{node.attrs.get('src', 'unknown')}'>",
                    "message": "Elemen <img> wajib memiliki atribut 'alt'."
                })

        # Check 2: Clickable Non-Interactive Element (Div-Soup anti-pattern)
        if tag in ("div", "span") and ("onclick" in node.attrs or "cursor:pointer" in node.attrs.get("style", "")):
            if "role" not in node.attrs or node.attrs.get("role") != "button":
                self.violations.append({
                    "rule": "WCAG 4.1.2 Name, Role, Value",
                    "severity": "HIGH",
                    "node": f"<{tag} class='{node.attrs.get('class', '')}'>",
                    "message": f"Elemen non-semantik <{tag}> digunakan untuk interaksi tanpa role='button' atau tabindex."
                })

        # Check 3: Heading Hierarchy Sequence
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            current_level = int(tag[1])
            if self.heading_levels:
                last_level = self.heading_levels[-1]
                if current_level > last_level + 1:
                    self.violations.append({
                        "rule": "WCAG 1.3.1 Info and Relationships",
                        "severity": "MEDIUM",
                        "node": f"<{tag}>",
                        "message": f"Urutan heading melompat dari <h{last_level}> langsung ke <h{current_level}>."
                    })
            self.heading_levels.append(current_level)

        # Check 4: Interactive element with missing accessible name
        if tag in ("button", "a"):
            acc_name = AccessibilityEngine.compute_accessible_name(node)
            if not acc_name.strip():
                self.violations.append({
                    "rule": "WCAG 2.4.4 Link/Button Purpose",
                    "severity": "CRITICAL",
                    "node": f"<{tag} href='{node.attrs.get('href', '')}'>",
                    "message": f"Elemen interaktif <{tag}> kosong, tidak memiliki nama terakses (accessible name)."
                })

        for child in node.children:
            self.audit(child)


class VirtualScreenReader:
    """Simulator Screen Reader (seperti NVDA / VoiceOver) mengonsumsi a11y tree."""
    def __init__(self):
        self.speech_buffer: List[str] = []

    def traverse_and_speak(self, node: AccessibilityNode, depth: int = 0):
        # Abaikan node generic/tanpa arti semantik langsung kecuali memiliki name relevan
        is_landmark = node.role in ("banner", "navigation", "main", "contentinfo", "region", "article")
        is_interactive = node.role in ("button", "link")
        is_heading = node.role == "heading"

        indent = "  " * depth
        if is_landmark:
            self.speech_buffer.append(f"{indent}[Landmark: {node.role.upper()}] {node.name}")
        elif is_heading:
            level = node.node_ref.tag.upper()
            self.speech_buffer.append(f"{indent}[{level}] '{node.name}'")
        elif is_interactive:
            self.speech_buffer.append(f"{indent}[{node.role.capitalize()}] '{node.name}'")
        elif node.role == "img":
            self.speech_buffer.append(f"{indent}[Graphic] '{node.name}'")
        elif node.role == "generic" and node.name and len(node.children) == 0:
            self.speech_buffer.append(f"{indent}'{node.name}'")

        for child in node.children:
            self.traverse_and_speak(child, depth + 1)


# Dataset Sampel: Kasus 'Div-Soup' (Buruk) vs Kasus 'HTML5 Semantic' (Baik)
SAMPLE_BAD_HTML = """
<div class="wrapper">
    <div class="header">
        <div class="title">Sistem Akademik Kampus</div>
        <div class="nav-btn" onclick="goToMenu()">Menu Utama</div>
    </div>
    <div class="content">
        <div class="banner-img">
            <img src="/assets/hero.jpg">
        </div>
        <h4>Pengumuman Ujian</h4>
        <div class="btn-group">
            <a href="/download"></a>
        </div>
    </div>
</div>
"""

SAMPLE_SEMANTIC_HTML = """
<div class="wrapper">
    <header>
        <h1>Sistem Akademik Kampus</h1>
        <nav aria-label="Navigasi Utama">
            <button onclick="goToMenu()">Menu Utama</button>
        </nav>
    </header>
    <main>
        <article>
            <img src="/assets/hero.jpg" alt="Foto suasana rektorat di pagi hari">
            <h2>Pengumuman Ujian</h2>
            <p>Jadwal ujian semester genap telah dirilis.</p>
            <a href="/download" aria-label="Unduh Jadwal Ujian PDF">Unduh Jadwal</a>
        </article>
    </main>
    <footer>
        <p>&copy; 2025 Universitas Terbuka</p>
    </footer>
</div>
"""

def print_dom_tree(node: DOMNode, indent: int = 0):
    """Mencetak struktur pohon DOM secara visual."""
    spacing = "  " * indent
    if node.tag == "#text":
        print(f"{spacing}└─ {CLR_CYAN}\"{node.text_content}\"{CLR_RESET}")
    elif node.tag != "document":
        attrs = " ".join([f'{k}="{v}"' for k, v in node.attrs.items()])
        attr_str = f" {CLR_YELLOW}{attrs}{CLR_RESET}" if attrs else ""
        print(f"{spacing}├─ {CLR_BOLD}<{node.tag}>{CLR_RESET}{attr_str}")

    for child in node.children:
        print_dom_tree(child, indent + 1)


def run_pipeline(html_data: str, label: str):
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}==================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}  EKSEKUSI PIPELINE: {label}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}==================================================================={CLR_RESET}")

    # 1. Parsing DOM
    parser = DOMTreeBuilder()
    parser.feed(html_data)
    dom_root = parser.root

    print(f"\n{CLR_BLUE}1. Render Visual DOM Tree:{CLR_RESET}")
    print_dom_tree(dom_root)

    # 2. Audit Aksesibilitas
    auditor = AccessibilityAuditor()
    auditor.audit(dom_root)
    print(f"\n{CLR_BLUE}2. Hasil Pemeriksaan Aksesibilitas (WCAG Engine):{CLR_RESET}")
    if auditor.violations:
        for v in auditor.violations:
            sev_color = CLR_RED if v['severity'] in ("CRITICAL", "HIGH") else CLR_YELLOW
            print(f"  {sev_color}[{v['severity']}]{CLR_RESET} {v['rule']}")
            print(f"    Target:  {v['node']}")
            print(f"    Alasan:  {v['message']}")
    else:
        print(f"  {CLR_GREEN}✔ Lulus Audit! Tidak ditemukan pelanggaran struktur semantik dasar.{CLR_RESET}")

    # 3. Komputasi a11y Tree & Screen Reader Traversal
    a11y_root = AccessibilityEngine.build_a11y_tree(dom_root)
    screen_reader = VirtualScreenReader()
    if a11y_root:
        screen_reader.traverse_and_speak(a11y_root)

    print(f"\n{CLR_BLUE}3. Simulasi Assistive Audio Buffer (Output Screen Reader):{CLR_RESET}")
    if screen_reader.speech_buffer:
        for speech in screen_reader.speech_buffer:
            print(f"  {CLR_CYAN}🔊 {speech}{CLR_RESET}")
    else:
        print(f"  {CLR_RED}[Screen Reader Mengalami Kegagalan: Tidak ada node landmark/semantik terdeteksi!]{CLR_RESET}")


def main():
    print(f"{CLR_BOLD}{CLR_CYAN}LAB: Core Foundations - Semantik HTML5, a11y & Engine DOM{CLR_RESET}")
    print(f"Interpreter: Python {sys.version.split()[0]} | Zero Dependency\n")

    # Jalankan simulasi untuk Anti-Pattern (Non-Semantic Div Soup)
    run_pipeline(SAMPLE_BAD_HTML, "Kasus 1: Anti-Pattern (Div-Soup & Aset Tanpa Alt)")

    # Jalankan simulasi untuk Best Practice (HTML5 Semantic Elements)
    run_pipeline(SAMPLE_SEMANTIC_HTML, "Kasus 2: Best-Practice (Semantic HTML5 & Standard ARIA)")


if __name__ == "__main__":
    main()