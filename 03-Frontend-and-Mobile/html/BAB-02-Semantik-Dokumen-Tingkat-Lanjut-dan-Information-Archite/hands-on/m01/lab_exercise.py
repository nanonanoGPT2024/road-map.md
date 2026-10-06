#!/usr/bin/env python3
"""
Hands-on Lab Exercise: HTML5 Advanced Semantic Architecture & Document Outline Simulator
BAB-02: Semantik Dokumen Tingkat Lanjut dan Information Architecture (IA)
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

# ANSI Terminal Colors for Rich Interactive CLI
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

class SemanticRole(Enum):
    BANNER = ("header", "banner", "Top-level page header / branding")
    NAVIGATION = ("nav", "navigation", "Major navigation links")
    MAIN = ("main", "main", "Central unique content of the document")
    ARTICLE = ("article", "article", "Self-contained distributable composition")
    SECTION = ("section", "region", "Thematic grouping of content with heading")
    COMPLEMENTARY = ("aside", "complementary", "Supporting sidebar or tangent")
    CONTENTINFO = ("footer", "contentinfo", "Metadata, copyright, and footer links")
    DIV = ("div", "generic", "Non-semantic generic container (Anti-pattern if overused)")

@dataclass
class SemanticNode:
    tag: str
    role: str
    heading_level: Optional[int] = None
    title: str = ""
    landmark: bool = False
    children: List["SemanticNode"] = field(default_factory=list)

    def is_div_soup(self) -> bool:
        return self.tag.lower() == "div"

class DocumentTreeAuditor:
    def __init__(self, root: SemanticNode):
        self.root = root
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []

    def audit(self):
        self.issues.clear()
        self.warnings.clear()
        self.passed.clear()
        
        main_count = 0
        h1_count = 0
        headings: List[int] = []

        def traverse(node: SemanticNode, depth: int = 0):
            nonlocal main_count, h1_count
            
            if node.tag.lower() == "main":
                main_count += 1
            if node.heading_level == 1:
                h1_count += 1
            if node.heading_level is not None:
                headings.append(node.heading_level)

            if node.tag.lower() == "section" and (node.heading_level is None and not any(c.heading_level for c in node.children)):
                self.warnings.append(f"Elemen <section> ('{node.title}') sebaiknya memiliki heading judul sendiri.")

            if node.tag.lower() == "div" and node.title:
                self.warnings.append(f"Terdeteksi potret Div-Soup: <div class='{node.title}'> berpotensi diganti tag semantik.")

            for child in node.children:
                traverse(child, depth + 1)

        traverse(self.root)

        # Rule 1: Exactly one <main> per document
        if main_count == 1:
            self.passed.append("Aksesibilitas Valid: Tepat 1 elemen <main> terdefinisi sebagai landmark utama.")
        elif main_count == 0:
            self.issues.append("Pelanggaran Kritis: Dokumen tidak memiliki landmark <main>.")
        else:
            self.issues.append(f"Pelanggaran Kritis: Ditemukan {main_count} elemen <main>. Dokumen hanya boleh punya 1 <main> aktif.")

        # Rule 2: Heading H1 presence & hierarchy
        if h1_count == 1:
            self.passed.append("Struktur Heading: Memiliki tepat 1 <h1> sebagai root outline.")
        elif h1_count == 0:
            self.warnings.append("Struktur Heading: Dokumen tidak memiliki <h1>.")
        else:
            self.warnings.append(f"Struktur Heading: Ditemukan {h1_count} <h1>. Pastikan tidak membingungkan screen reader.")

        # Rule 3: Heading level skipping check
        skipped = False
        for i in range(len(headings) - 1):
            if headings[i+1] > headings[i] + 1:
                self.issues.append(f"Heading Skipped: Terjadi loncatan dari h{headings[i]} langsung ke h{headings[i+1]}.")
                skipped = True
        if not skipped and headings:
            self.passed.append("Urutan Tingkat Heading: Berjenjang rapi tanpa level melompat (e.g. h1 -> h2 -> h3).")

    def print_tree(self, node: Optional[SemanticNode] = None, prefix: str = "", is_last: bool = True):
        if node is None:
            node = self.root

        branch = "└── " if is_last else "├── "
        tag_color = Color.GREEN if node.landmark else (Color.RED if node.tag == "div" else Color.CYAN)
        heading_badge = f"{Color.YELLOW}[H{node.heading_level}]{Color.RESET} " if node.heading_level else ""
        landmark_badge = f"{Color.MAGENTA}<Landmark: {node.role}>{Color.RESET} " if node.landmark else ""

        print(f"{prefix}{branch}{tag_color}<{node.tag}>{Color.RESET} {heading_badge}{landmark_badge}{Color.WHITE}{node.title}{Color.RESET}")

        prefix += "    " if is_last else "│   "
        child_count = len(node.children)
        for idx, child in enumerate(node.children):
            self.print_tree(child, prefix, idx == (child_count - 1))

def create_sample_bad_architecture() -> SemanticNode:
    """Simulasi struktur situs kuno / div-soup tanpa semantik standar."""
    return SemanticNode(
        tag="div", role="generic", title="page-wrapper", landmark=False,
        children=[
            SemanticNode(tag="div", role="generic", title="header-banner", children=[
                SemanticNode(tag="div", role="generic", heading_level=1, title="Portal Berita Modern (Div Soup)")
            ]),
            SemanticNode(tag="div", role="generic", title="nav-bar", children=[
                SemanticNode(tag="div", role="generic", title="Link Home | Berita | Kontak")
            ]),
            SemanticNode(tag="div", role="generic", title="content-area", children=[
                SemanticNode(tag="div", role="generic", heading_level=3, title="Skandal Keamanan Siber (Lompat dari H1 ke H3)"),
                SemanticNode(tag="div", role="generic", title="body-text"),
                SemanticNode(tag="div", role="generic", heading_level=2, title="Sub-topik tidak terstruktur")
            ]),
            SemanticNode(tag="div", role="generic", title="footer-box", children=[
                SemanticNode(tag="p", role="generic", title="Copyright 2026")
            ])
        ]
    )

def create_sample_semantic_architecture() -> SemanticNode:
    """Simulasi arsitektur informasi bersih berbasis HTML5 Semantic & Landmark WCAG."""
    return SemanticNode(
        tag="body", role="document", title="Root Dokumen", landmark=False,
        children=[
            SemanticNode(
                tag="header", role="banner", title="Header Utama Portal", landmark=True,
                children=[
                    SemanticNode(tag="h1", role="heading", heading_level=1, title="TechInsight: Jurnal Rekayasa Perangkat Lunak"),
                    SemanticNode(tag="nav", role="navigation", title="Navigasi Utama", landmark=True)
                ]
            ),
            SemanticNode(
                tag="main", role="main", title="Area Konten Inti", landmark=True,
                children=[
                    SemanticNode(
                        tag="article", role="article", title="Artikel: Fondasi Semantik Web",
                        children=[
                            SemanticNode(tag="h2", role="heading", heading_level=2, title="Mengapa Semantik Berdampak pada SEO & Aksesibilitas"),
                            SemanticNode(
                                tag="section", role="region", title="Bagian 1: Document Outline",
                                children=[
                                    SemanticNode(tag="h3", role="heading", heading_level=3, title="Algoritma Outline vs Aksesibilitas Nyata")
                                ]
                            ),
                            SemanticNode(
                                tag="section", role="region", title="Bagian 2: Landmark Regions",
                                children=[
                                    SemanticNode(tag="h3", role="heading", heading_level=3, title="Screen Reader Navigation Shortcuts")
                                ]
                            )
                        ]
                    ),
                    SemanticNode(
                        tag="aside", role="complementary", title="Artikel Terkait & Glosarium", landmark=True,
                        children=[
                            SemanticNode(tag="h2", role="heading", heading_level=2, title="Glosarium Landmark")
                        ]
                    )
                ]
            ),
            SemanticNode(
                tag="footer", role="contentinfo", title="Footer Situs & Hak Cipta", landmark=True,
                children=[
                    SemanticNode(tag="p", role="generic", title="© 2026 TechInsight Media Ltd.")
                ]
            )
        ]
    )

def banner():
    print(f"{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}   LAB SIMULASI INTERAKTIF: SEMANTIK ARSITEKTUR DOKUMEN HTML5   {Color.RESET}")
    print(f"{Color.CYAN}   BAB 02: Information Architecture, Landmark Roles & Document Outline   {Color.RESET}")
    print(f"{Color.CYAN}{'=' * 75}{Color.RESET}\n")

def run_audit_report(name: str, root_node: SemanticNode):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} [AUDIT TARGET] : {name} {Color.RESET}\n")
    auditor = DocumentTreeAuditor(root_node)
    
    print(f"{Color.BOLD}Visualisasi Pohon Elemen DOM & Landmark:{Color.RESET}")
    auditor.print_tree()
    print()

    print(f"{Color.DIM}Menganalisis kepatuhan WCAG 2.1 & HTML5 Living Standard...{Color.RESET}")
    time.sleep(0.3)
    auditor.audit()

    print(f"\n{Color.BOLD}--- HASIL AUDIT TEKNIS ---{Color.RESET}")
    for item in auditor.passed:
        print(f"  {Color.GREEN}[PASSED]{Color.RESET} {item}")
    for item in auditor.warnings:
        print(f"  {Color.YELLOW}[WARN]  {Color.RESET} {item}")
    for item in auditor.issues:
        print(f"  {Color.RED}[FAIL]  {Color.RESET} {item}")

    score = max(0, 100 - (len(auditor.issues) * 30) - (len(auditor.warnings) * 10))
    score_color = Color.GREEN if score >= 80 else (Color.YELLOW if score >= 50 else Color.RED)
    print(f"\nSkor Kualitas Arsitektur Semantik: {score_color}{score}/100{Color.RESET}\n")

def interactive_menu():
    while True:
        banner()
        print("Pilih skenario simulasi audit:")
        print(f"  {Color.BOLD}1.{Color.RESET} Audit Contoh Dokumen 'Div-Soup' (Anti-Pattern Warisan)")
        print(f"  {Color.BOLD}2.{Color.RESET} Audit Contoh Arsitektur Semantik Standar Modern (HTML5 + ARIA Landmarks)")
        print(f"  {Color.BOLD}3.{Color.RESET} Uji Coba Kustom: Bangun Outline Dokumen & Evaluasi Heading Level")
        print(f"  {Color.BOLD}4.{Color.RESET} Keluar (Exit)")
        print()
        
        choice = input(f"{Color.YELLOW}Masukkan pilihan (1-4): {Color.RESET}").strip()
        
        if choice == "1":
            run_audit_report("Situs Div-Soup Warisan (Non-Semantis)", create_bad_architecture := create_sample_bad_architecture())
            input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")
        elif choice == "2":
            run_audit_report("Arsitektur Semantik Modern (HTML5)", create_sample_semantic_architecture())
            input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")
        elif choice == "3":
            custom_exercise()
        elif choice == "4":
            print(f"\n{Color.GREEN}Simulasi selesai. Terapkan prinsip semantik murni pada markup Anda!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, coba lagi.{Color.RESET}\n")
            time.sleep(0.5)

def custom_exercise():
    print(f"\n{Color.BOLD}--- Latihan Cepat: Evaluasi Hierarki Heading Dokumen Anda ---{Color.RESET}")
    print("Masukkan urutan heading yang Anda rancang dipisahkan spasi (contoh: 1 2 2 3 2 4):")
    raw_input = input(f"{Color.CYAN}Tingkat Heading (h1-h6): {Color.RESET}").strip()
    
    if not raw_input:
        return
        
    try:
        levels = [int(x) for x in raw_input.split()]
    except ValueError:
        print(f"{Color.RED}Format salah! Masukkan angka 1 sampai 6.{Color.RESET}")
        return

    root = SemanticNode(tag="main", role="main", title="Custom Outline Test", landmark=True)
    current_parent = root
    for idx, lvl in enumerate(levels):
        node = SemanticNode(
            tag=f"h{lvl}",
            role="heading",
            heading_level=lvl,
            title=f"Judul Seksi Ke-{idx+1} (Level {lvl})"
        )
        root.children.append(node)

    auditor = DocumentTreeAuditor(root)
    auditor.audit()
    print(f"\n{Color.BOLD}Evaluasi Hierarki:{Color.RESET}")
    auditor.print_tree()
    print()
    for item in auditor.passed:
        print(f"  {Color.GREEN}[PASSED]{Color.RESET} {item}")
    for item in auditor.warnings:
        print(f"  {Color.YELLOW}[WARN]  {Color.RESET} {item}")
    for item in auditor.issues:
        print(f"  {Color.RED}[FAIL]  {Color.RESET} {item}")
    print()
    input(f"{Color.DIM}Tekan [Enter] untuk kembali ke menu...{Color.RESET}")

if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Color.YELLOW}Program dihentikan oleh pengguna.{Color.RESET}")
        sys.exit(0)
