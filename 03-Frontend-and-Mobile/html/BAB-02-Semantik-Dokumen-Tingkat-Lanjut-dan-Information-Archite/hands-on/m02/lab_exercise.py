#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Document Semantics & Information Architecture (IA)
Category: 03-Frontend-and-Mobile | Chapter: 02 - Deep Dive

Deskripsi:
Script ini memodelkan Semantic Outline Engine & Landmark Tree Parser mandiri.
Mesin ini membedah struktur dokumen HTML, merekonstruksi Document Outline (HTML5
Heading & Sectioning Hierarchy), memetakan implicit ARIA Landmarks, mendeteksi
kesalahan Information Architecture (IA) seperti skipping heading levels, orphan
sections, duplicate/missing main landmarks, serta menghitung Semantic Purity Index.
"""

import sys
import re
from html.parser import HTMLParser
from typing import List, Dict, Optional, Tuple

# --- ANSI Formatting Helper ---
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BG_DARK = "\033[48;5;235m"


# --- Structural Models ---
class SemanticNode:
    """Node representasi hierarki Information Architecture."""
    def __init__(self, tag: str, attrs: Dict[str, str], depth: int):
        self.tag = tag.lower()
        self.attrs = attrs
        self.depth = depth
        self.heading_text: Optional[str] = None
        self.heading_level: Optional[int] = None
        self.children: List['SemanticNode'] = []
        self.parent: Optional['SemanticNode'] = None
        self.landmark_role: Optional[str] = self._resolve_aria_landmark()

    def _resolve_aria_landmark(self) -> Optional[str]:
        """Memetakan tag HTML5 ke implicit ARIA landmark roles."""
        role_map = {
            'main': 'main',
            'nav': 'navigation',
            'aside': 'complementary',
            'header': 'banner',
            'footer': 'contentinfo',
            'section': 'region',
            'article': 'article',
            'form': 'form'
        }
        explicit_role = self.attrs.get('role')
        if explicit_role:
            return explicit_role
        return role_map.get(self.tag)


class SemanticParserEngine(HTMLParser):
    """
    Parser HTML berbasis Event-driven untuk mengekstrak dan memvalidasi
    semantic tree serta sectioning content.
    """
    SECTIONING_TAGS = {'article', 'section', 'nav', 'aside', 'main', 'header', 'footer'}
    GENERIC_CONTAINERS = {'div', 'span'}
    HEADING_TAGS = {f'h{i}': i for i in range(1, 7)}

    def __init__(self):
        super().__init__()
        self.root = SemanticNode(tag='document_root', attrs={}, depth=0)
        self.current_node = self.root
        self.current_heading_node: Optional[SemanticNode] = None
        self.raw_heading_stream: List[Tuple[int, str]] = []
        self.semantic_tag_count = 0
        self.generic_tag_count = 0

    def handle_starttag(self, tag: str, attrs: list):
        attr_dict = dict(attrs)
        tag = tag.lower()

        if tag in self.SECTIONING_TAGS:
            self.semantic_tag_count += 1
            new_node = SemanticNode(tag, attr_dict, self.current_node.depth + 1)
            new_node.parent = self.current_node
            self.current_node.children.append(new_node)
            self.current_node = new_node
        elif tag in self.GENERIC_CONTAINERS:
            self.generic_tag_count += 1
        elif tag in self.HEADING_TAGS:
            self.current_heading_node = self.current_node
            self._active_heading_level = self.HEADING_TAGS[tag]
            self._buffer_heading_text = []

    def handle_data(self, data: str):
        if hasattr(self, '_active_heading_level') and self._active_heading_level is not None:
            clean_text = data.strip()
            if clean_text:
                self._buffer_heading_text.append(clean_text)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self.SECTIONING_TAGS:
            if self.current_node.parent is not None:
                self.current_node = self.current_node.parent
        elif tag in self.HEADING_TAGS:
            if hasattr(self, '_active_heading_level') and self._active_heading_level is not None:
                heading_content = " ".join(self._buffer_heading_text)
                self.raw_heading_stream.append((self._active_heading_level, heading_content))
                # Mengaitkan heading terdekat ke section induk
                if self.current_node.heading_text is None:
                    self.current_node.heading_text = heading_content
                    self.current_node.heading_level = self._active_heading_level
                self._active_heading_level = None
                self._buffer_heading_text = []


class InformationArchitectureAuditor:
    """
    Mesin Audit Semantik: Memeriksa kualitas Information Architecture (IA)
    berdasarkan standar W3C HTML5 & WCAG 2.1 Section 1.3.1 (Info and Relationships).
    """
    def __init__(self, parser: SemanticParserEngine):
        self.parser = parser
        self.violations: List[Dict[str, str]] = []

    def audit_heading_progression(self):
        """Memvalidasi aturan heading traversal (tidak boleh skip heading level)."""
        headings = self.parser.raw_heading_stream
        if not headings:
            self.violations.append({
                "severity": "CRITICAL",
                "code": "IA-E01",
                "message": "Dokumen tidak memiliki struktur heading sama sekali (WCAG 2.4.6 violation)."
            })
            return

        if headings[0][0] != 1:
            self.violations.append({
                "severity": "HIGH",
                "code": "IA-W01",
                "message": f"Heading pertama adalah H{headings[0][0]}, idealnya dokumen diawali H1 tunggal."
            })

        h1_count = sum(1 for lvl, _ in headings if lvl == 1)
        if h1_count > 1:
            self.violations.append({
                "severity": "MEDIUM",
                "code": "IA-W02",
                "message": f"Ditemukan {h1_count} elemen H1. Top-level Document IA disarankan memiliki single primary H1."
            })

        for i in range(len(headings) - 1):
            curr_lvl, curr_txt = headings[i]
            next_lvl, next_txt = headings[i + 1]
            if next_lvl > curr_lvl + 1:
                self.violations.append({
                    "severity": "HIGH",
                    "code": "IA-E02",
                    "message": f"Skipped Heading: H{curr_lvl} ('{curr_txt[:20]}...') loncat langsung ke H{next_lvl} ('{next_txt[:20]}...')."
                })

    def audit_landmarks(self):
        """Memeriksa keberadaan dan keunikan ARIA Landmark elements."""
        landmarks: Dict[str, int] = {}

        def walk(node: SemanticNode):
            if node.landmark_role:
                landmarks[node.landmark_role] = landmarks.get(node.landmark_role, 0) + 1
            for child in node.children:
                walk(child)

        walk(self.parser.root)

        if landmarks.get('main', 0) == 0:
            self.violations.append({
                "severity": "CRITICAL",
                "code": "IA-E03",
                "message": "Landmark <main> tidak ditemukan. Screen reader kesulitan menemukan konten utama."
            })
        elif landmarks.get('main', 0) > 1:
            self.violations.append({
                "severity": "CRITICAL",
                "code": "IA-E04",
                "message": f"Terdapat {landmarks['main']} landmark <main>. Dokumen hanya boleh memiliki 1 visible <main>."
            })

        if landmarks.get('navigation', 0) == 0:
            self.violations.append({
                "severity": "MEDIUM",
                "code": "IA-W03",
                "message": "Tidak ditemukan landmark <nav> navigasi struktural."
            })

    def audit_orphan_sections(self):
        """Memverifikasi bahwa setiap sectioning tag memiliki heading yang mengidentifikasinya."""
        def walk(node: SemanticNode):
            if node.tag in {'section', 'article'} and not node.heading_text:
                self.violations.append({
                    "severity": "LOW",
                    "code": "IA-W04",
                    "message": f"Elemen <{node.tag}> tanpa heading eksplisit (Sectioning content unlabelled)."
                })
            for child in node.children:
                walk(child)

        walk(self.parser.root)

    def calculate_semantic_purity(self) -> float:
        """Menghitung rasio tag semantik terhadap total struktural (anti Div-Soup index)."""
        sem = self.parser.semantic_tag_count
        gen = self.parser.generic_tag_count
        total = sem + gen
        if total == 0:
            return 0.0
        return (sem / total) * 100.0

    def execute_full_audit(self):
        self.audit_heading_progression()
        self.audit_landmarks()
        self.audit_orphan_sections()


# --- CLI Visualizers ---
def render_ia_tree(node: SemanticNode, prefix: str = "", is_last: bool = True):
    """Menampilkan tree IA secara visual di terminal."""
    if node.tag != "document_root":
        connector = "└── " if is_last else "├── "
        role_badge = f"{TermColor.CYAN}[{node.landmark_role}]{TermColor.RESET}" if node.landmark_role else ""
        heading_info = f"{TermColor.YELLOW}(H{node.heading_level}: '{node.heading_text}'){TermColor.RESET}" if node.heading_text else ""
        print(f"{prefix}{connector}{TermColor.BOLD}<{node.tag}>{TermColor.RESET} {role_badge} {heading_info}")
        prefix += "    " if is_last else "│   "

    children = node.children
    for idx, child in enumerate(children):
        render_ia_tree(child, prefix, idx == (len(children) - 1))


def run_benchmark_suite(html_doc: str, label: str):
    """Menjalankan engine terhadap sample dokumen dan mencetak diagnostik komprehensif."""
    print(f"\n{TermColor.BG_DARK}{TermColor.BOLD}=== RUNNING IA ENGINE ON: {label.upper()} ==={TermColor.RESET}")
    parser = SemanticParserEngine()
    parser.feed(html_doc)

    auditor = InformationArchitectureAuditor(parser)
    auditor.execute_full_audit()

    print(f"\n{TermColor.BOLD}Document Semantic Tree Visualizer:{TermColor.RESET}")
    render_ia_tree(parser.root)

    print(f"\n{TermColor.BOLD}Heading Sequence Captured:{TermColor.RESET}")
    if parser.raw_heading_stream:
        seq_str = " -> ".join([f"H{lvl} ('{txt[:15]}...')" for lvl, txt in parser.raw_heading_stream])
        print(f"  {TermColor.MAGENTA}{seq_str}{TermColor.RESET}")
    else:
        print(f"  {TermColor.RED}[No headings found]{TermColor.RESET}")

    purity = auditor.calculate_semantic_purity()
    color_purity = TermColor.GREEN if purity >= 70 else (TermColor.YELLOW if purity >= 40 else TermColor.RED)
    print(f"\n{TermColor.BOLD}Semantic Purity Index:{TermColor.RESET} {color_purity}{purity:.1f}%{TermColor.RESET} "
          f"({parser.semantic_tag_count} semantic vs {parser.generic_tag_count} generic elements)")

    print(f"\n{TermColor.BOLD}Diagnostic & Accessibility (WCAG) Findings:{TermColor.RESET}")
    if not auditor.violations:
        print(f"  {TermColor.GREEN}✔ Dokumen lolos seluruh validasi Information Architecture! Struktur sempurna.{TermColor.RESET}")
    else:
        for v in auditor.violations:
            sev = v["severity"]
            sev_color = TermColor.RED if sev == "CRITICAL" else (TermColor.YELLOW if sev == "HIGH" else TermColor.BLUE)
            print(f"  [{sev_color}{sev:<8}{TermColor.RESET}] {v['code']} - {v['message']}")


# --- Sample Test Documents ---
BAD_IA_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="header">
        <div class="logo">My App</div>
        <div class="nav-links">
            <a href="/">Home</a>
            <a href="/about">About</a>
        </div>
    </div>
    <div class="content-wrapper">
        <h3>Breaking News Without Top Level</h3>
        <div>
            <p>Some random intro paragraph.</p>
            <h6>Direct Jump to H6</h6>
        </div>
    </div>
    <div class="footer">
        <p>&copy; 2025 Div Soup Enterprise</p>
    </div>
</body>
</html>
"""

GOOD_IA_HTML = """
<!DOCTYPE html>
<html lang="id">
<body>
    <header>
        <h1>Sistem Informasi Terdistribusi</h1>
        <nav aria-label="Menu Utama">
            <ul>
                <li><a href="#overview">Overview</a></li>
                <li><a href="#arch">Arsitektur</a></li>
            </ul>
        </nav>
    </header>
    <main>
        <article>
            <h2>Modul 02: Advanced Semantics</h2>
            <p>Analisis Information Architecture dan Document Outline.</p>
            <section id="arch">
                <h3>Heading Hierarchy & Algoritma Outline</h3>
                <p>Heading harus merepresentasikan kedalaman hierarki konten.</p>
            </section>
            <section id="landmarks">
                <h3>ARIA Landmarks & Accessibility</h3>
                <p>Screen reader menavigasi page menggunakan landmark nodes.</p>
            </section>
        </article>
        <aside>
            <h2>Referensi Terkait</h2>
            <p>Spesifikasi W3C HTML Living Standard.</p>
        </aside>
    </main>
    <footer>
        <p>Lab Runtime Engine Ver 2.4 - Lead System Programmer Architecture</p>
    </footer>
</body>
</html>
"""

def main():
    print(f"{TermColor.BOLD}{TermColor.CYAN}========================================================================{TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN} LAB: ADVANCED DOCUMENT SEMANTICS & INFORMATION ARCHITECTURE ANALYZER   {TermColor.RESET}")
    print(f"{TermColor.BOLD}{TermColor.CYAN}========================================================================{TermColor.RESET}")

    # Uji Coba Dokumen 1: Anti-pattern "Div Soup" & Heading Disorder
    run_benchmark_suite(BAD_IA_HTML, "Anti-pattern Document (Div Soup & Broken IA)")

    print("\n" + "=" * 72)

    # Uji Coba Dokumen 2: Strict Semantic & Accessible Information Architecture
    run_benchmark_suite(GOOD_IA_HTML, "Strict Semantic Document (Valid IA & W3C Compliant)")

if __name__ == '__main__':
    main()