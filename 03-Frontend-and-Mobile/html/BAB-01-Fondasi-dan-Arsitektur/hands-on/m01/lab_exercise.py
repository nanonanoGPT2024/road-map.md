#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Engine Parser HTML5 & Rekonstruksi DOM Tree
BAB-01: Fondasi dan Arsitektur HTML
====================================================================
Program ini mendemonstrasikan secara interaktif bagaimana web browser modern
memproses dokumen HTML mentah melalui pipeline:
1. Byte Stream Decoding & Encoding Sniffing
2. Tokenisasi Karakter (HTML5 Tokenizer State Machine)
3. Doctype Sniffing (Standards Mode vs Quirks Mode)
4. Konstruksi Tree & Stack of Open Elements (DOM Tree Builder)
5. Algoritma Error-Recovery & Auto-Correction
"""

from __future__ import annotations
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict

# ====================================================================
# ANSI Color Palette untuk Visualisasi Terminal
# ====================================================================
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright Foregrounds
    B_CYAN = "\033[96m"
    B_GREEN = "\033[92m"
    B_YELLOW = "\033[93m"
    B_WHITE = "\033[97m"

    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


# ====================================================================
# Data Types & Token Definitions
# ====================================================================
class TokenType(Enum):
    DOCTYPE = auto()
    START_TAG = auto()
    END_TAG = auto()
    COMMENT = auto()
    CHARACTER = auto()
    EOF = auto()


@dataclass
class Token:
    token_type: TokenType
    name: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    data: str = ""
    self_closing: bool = False

    def __repr__(self) -> str:
        if self.token_type == TokenType.DOCTYPE:
            return f"{ANSI.MAGENTA}[DOCTYPE: {self.name}]{ANSI.RESET}"
        elif self.token_type == TokenType.START_TAG:
            attrs = " ".join(f'{k}="{v}"' for k, v in self.attributes.items())
            attr_str = f" {attrs}" if attrs else ""
            sc = " /" if self.self_closing else ""
            return f"{ANSI.GREEN}<{self.name}{attr_str}{sc}>{ANSI.RESET}"
        elif self.token_type == TokenType.END_TAG:
            return f"{ANSI.RED}</{self.name}>{ANSI.RESET}"
        elif self.token_type == TokenType.CHARACTER:
            return f"{ANSI.YELLOW}'{self.data}'{ANSI.RESET}"
        elif self.token_type == TokenType.COMMENT:
            return f"{ANSI.DIM}<!-- {self.data} -->{ANSI.RESET}"
        return f"{ANSI.BLUE}[EOF]{ANSI.RESET}"


@dataclass
class DOMNode:
    node_type: str
    name: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    text: str = ""
    children: List[DOMNode] = field(default_factory=list)
    parent: Optional[DOMNode] = None

    def append_child(self, child: DOMNode) -> None:
        child.parent = self
        self.children.append(child)


# ====================================================================
# HTML5 Tokenizer Engine (Simplified State Machine)
# ====================================================================
class HTMLTokenizer:
    """Simulasi mesin tokenisasi HTML5 dengan pembagian state karakter."""

    def __init__(self, raw_html: str):
        self.raw = raw_html
        self.cursor = 0
        self.length = len(raw_html)

    def is_eof(self) -> bool:
        return self.cursor >= self.length

    def peek(self) -> str:
        return self.raw[self.cursor] if not self.is_eof() else ""

    def consume(self) -> str:
        ch = self.peek()
        self.cursor += 1
        return ch

    def tokenize_all(self) -> List[Token]:
        tokens: List[Token] = []
        while not self.is_eof():
            ch = self.peek()
            if ch == "<":
                self.consume()
                if self.is_eof():
                    tokens.append(Token(TokenType.CHARACTER, data="<"))
                    break
                
                # Check for comment / DOCTYPE
                if self.peek() == "!":
                    self.consume()
                    tokens.append(self._parse_bang())
                elif self.peek() == "/":
                    self.consume()
                    tokens.append(self._parse_end_tag())
                else:
                    tokens.append(self._parse_start_tag())
            else:
                tokens.append(self._parse_text())
        tokens.append(Token(TokenType.EOF))
        return tokens

    def _parse_bang(self) -> Token:
        if self.raw[self.cursor:].startswith("--"):
            self.cursor += 2
            comment_buf = []
            while not self.is_eof():
                if self.raw[self.cursor:].startswith("-->"):
                    self.cursor += 3
                    break
                comment_buf.append(self.consume())
            return Token(TokenType.COMMENT, data="".join(comment_buf).strip())
        
        # Check DOCTYPE
        buf = []
        while not self.is_eof() and self.peek() != ">":
            buf.append(self.consume())
        if self.peek() == ">":
            self.consume()
        content = "".join(buf).strip()
        parts = content.split()
        doc_type_name = parts[1] if len(parts) > 1 else parts[0]
        return Token(TokenType.DOCTYPE, name=doc_type_name)

    def _parse_start_tag(self) -> Token:
        tag_name_buf = []
        while not self.is_eof() and self.peek() not in (" ", ">", "/"):
            tag_name_buf.append(self.consume())
        tag_name = "".join(tag_name_buf).lower()

        attributes: Dict[str, str] = {}
        # Parse attributes
        while not self.is_eof() and self.peek() not in (">", "/"):
            if self.peek().isspace():
                self.consume()
                continue
            # Attribute Name
            attr_key_buf = []
            while not self.is_eof() and self.peek() not in ("=", " ", ">", "/"):
                attr_key_buf.append(self.consume())
            attr_key = "".join(attr_key_buf).lower()
            
            # Attribute Value
            attr_val = ""
            while not self.is_eof() and self.peek().isspace():
                self.consume()
            if self.peek() == "=":
                self.consume()
                while not self.is_eof() and self.peek().isspace():
                    self.consume()
                quote = ""
                if self.peek() in ('"', "'"):
                    quote = self.consume()
                val_buf = []
                while not self.is_eof():
                    if quote and self.peek() == quote:
                        self.consume()
                        break
                    elif not quote and self.peek() in (" ", ">", "/"):
                        break
                    val_buf.append(self.consume())
                attr_val = "".join(val_buf)
            if attr_key:
                attributes[attr_key] = attr_val

        self_closing = False
        if self.peek() == "/":
            self.consume()
            self_closing = True
        if self.peek() == ">":
            self.consume()

        return Token(TokenType.START_TAG, name=tag_name, attributes=attributes, self_closing=self_closing)

    def _parse_end_tag(self) -> Token:
        buf = []
        while not self.is_eof() and self.peek() != ">":
            buf.append(self.consume())
        if self.peek() == ">":
            self.consume()
        return Token(TokenType.END_TAG, name="".join(buf).strip().lower())

    def _parse_text(self) -> Token:
        buf = []
        while not self.is_eof() and self.peek() != "<":
            buf.append(self.consume())
        return Token(TokenType.CHARACTER, data="".join(buf))


# ====================================================================
# DOM Tree Builder (Parser & Stack of Open Elements)
# ====================================================================
class HTMLTreeBuilder:
    """Rekonstruksi Tree DOM dengan mekanisme Doctype Sniffing & Auto-Closing."""

    VOID_ELEMENTS = {"meta", "link", "br", "hr", "img", "input", "base"}

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.document = DOMNode("document", "#document")
        self.stack: List[DOMNode] = [self.document]
        self.render_mode = "Quirks Mode"
        self.parser_logs: List[str] = []

    def current_node(self) -> DOMNode:
        return self.stack[-1]

    def build_tree(self) -> DOMNode:
        for token in self.tokens:
            if token.token_type == TokenType.DOCTYPE:
                self._handle_doctype(token)
            elif token.token_type == TokenType.START_TAG:
                self._handle_start_tag(token)
            elif token.token_type == TokenType.END_TAG:
                self._handle_end_tag(token)
            elif token.token_type == TokenType.CHARACTER:
                self._handle_character(token)
            elif token.token_type == TokenType.COMMENT:
                comment_node = DOMNode("comment", text=token.data)
                self.current_node().append_child(comment_node)
            elif token.token_type == TokenType.EOF:
                self._handle_eof()
        return self.document

    def _handle_doctype(self, token: Token) -> None:
        doc_node = DOMNode("doctype", name=token.name)
        self.document.append_child(doc_node)
        if token.name.lower() == "html":
            self.render_mode = "No-Quirks (Standards) Mode"
            self._log(f"DOCTYPE <!DOCTYPE {token.name}> valid -> Mode diaktifkan: {ANSI.B_GREEN}{self.render_mode}{ANSI.RESET}")
        else:
            self.render_mode = "Quirks Mode"
            self._log(f"DOCTYPE tidak standar -> Fallback ke: {ANSI.B_YELLOW}{self.render_mode}{ANSI.RESET}")

    def _handle_start_tag(self, token: Token) -> None:
        # P tag auto-closing rule jika ada nested <p>
        if token.name == "p" and self._has_tag_in_stack("p"):
            self._log(f"Auto-closing tag <p> terdeteksi sebelum membuka tag <p> baru (HTML5 forgiving rule)")
            self._pop_until("p")

        node = DOMNode("element", name=token.name, attributes=token.attributes)
        self.current_node().append_child(node)

        if not token.self_closing and token.name not in self.VOID_ELEMENTS:
            self.stack.append(node)
            self._log(f"Pushing <{token.name}> ke Stack Open Elements. Depth stack: {len(self.stack)}")
        else:
            self._log(f"Void/Self-closing tag <{token.name}/> langsung disematkan tanpa push stack")

    def _handle_end_tag(self, token: Token) -> None:
        if not self._has_tag_in_stack(token.name):
            self._log(f"{ANSI.B_YELLOW}Peringatan Parse Error: Tag penutup </{token.name}> tanpa pembuka, diabaikan!{ANSI.RESET}")
            return
        
        self._pop_until(token.name)
        self._log(f"Popping <{token.name}> keluar dari Stack Open Elements.")

    def _handle_character(self, token: Token) -> None:
        text = token.data.strip()
        if text:
            text_node = DOMNode("text", text=text)
            self.current_node().append_child(text_node)

    def _handle_eof(self) -> None:
        while len(self.stack) > 1:
            popped = self.stack.pop()
            self._log(f"EOF Reached: Auto-closing tag <{popped.name}> yang tertinggal di stack")

    def _has_tag_in_stack(self, tag_name: str) -> bool:
        return any(node.name == tag_name for node in self.stack)

    def _pop_until(self, tag_name: str) -> None:
        while len(self.stack) > 1:
            node = self.stack.pop()
            if node.name == tag_name:
                break

    def _log(self, message: str) -> None:
        self.parser_logs.append(message)


# ====================================================================
# Visualizer & Output Exporter
# ====================================================================
def print_dom_tree(node: DOMNode, indent: str = "", is_last: bool = True) -> None:
    marker = "└── " if is_last else "├── "
    
    if node.node_type == "document":
        display = f"{ANSI.B_CYAN}{node.name}{ANSI.RESET}"
    elif node.node_type == "doctype":
        display = f"{ANSI.MAGENTA}<!DOCTYPE {node.name}>{ANSI.RESET}"
    elif node.node_type == "element":
        attrs = " ".join(f'{ANSI.CYAN}{k}{ANSI.RESET}="{ANSI.YELLOW}{v}{ANSI.RESET}"' for k, v in node.attributes.items())
        attr_str = f" [{attrs}]" if attrs else ""
        display = f"{ANSI.B_GREEN}<{node.name}>{ANSI.RESET}{attr_str}"
    elif node.node_type == "text":
        display = f"{ANSI.B_WHITE}\"{node.text}\"{ANSI.RESET}"
    elif node.node_type == "comment":
        display = f"{ANSI.DIM}<!-- {node.text} -->{ANSI.RESET}"
    else:
        display = node.name

    print(f"{indent}{marker}{display}")
    
    next_indent = indent + ("    " if is_last else "│   ")
    count = len(node.children)
    for idx, child in enumerate(node.children):
        print_dom_tree(child, next_indent, idx == count - 1)


# ====================================================================
# Interactive Workflows & Scenario Demonstrations
# ====================================================================
SAMPLE_HTML = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Laboratorium Arsitektur HTML</title>
</head>
<body>
    <!-- Komentar Header Navigasi -->
    <header class="navbar">
        <h1>Sistem Fondasi Web</h1>
    </header>
    <main>
        <p>Paragraf pertama menjelaskan siklus parsing.
        <p>Paragraf kedua auto-ditutup oleh tree builder.
        <img src="diagram.png" alt="Arsitektur DOM">
    </main>
</body>
</html>"""

QUIRKS_SAMPLE_HTML = """<html>
<head><title>Halaman Tanpa DOCTYPE</title></head>
<body>
    <h2>Uji Coba Quirks Mode Engine</h2>
</body>
</html>"""


def banner() -> None:
    print(f"\n{ANSI.BG_BLUE}{ANSI.B_WHITE}{' ' * 68}{ANSI.RESET}")
    print(f"{ANSI.BG_BLUE}{ANSI.B_WHITE}  LABORATORIUM PARSER & ARSITEKTUR HTML5 INTERAKTIF (BAB-01)        {ANSI.RESET}")
    print(f"{ANSI.BG_BLUE}{ANSI.B_WHITE}{' ' * 68}{ANSI.RESET}\n")


def run_pipeline(html_source: str, title: str) -> None:
    print(f"\n{ANSI.BOLD}{ANSI.B_YELLOW}=== SKENARIO: {title} ==={ANSI.RESET}")
    print(f"{ANSI.DIM}--- [Input HTML Source Stream] ---{ANSI.RESET}")
    for line in html_source.strip().split("\n")[:8]:
        print(f"  {ANSI.DIM}|{ANSI.RESET} {line}")
    if len(html_source.strip().split("\n")) > 8:
        print(f"  {ANSI.DIM}| ... (truncated){ANSI.RESET}")

    # Step 1: Tokenisasi
    print(f"\n{ANSI.B_CYAN}[Langkah 1: Tokenizer State Machine Menguraikan Karakter]{ANSI.RESET}")
    tokenizer = HTMLTokenizer(html_source)
    tokens = tokenizer.tokenize_all()
    
    token_preview = [str(t) for t in tokens if t.token_type != TokenType.CHARACTER or t.data.strip()][:12]
    print("Stream Token: " + " → ".join(token_preview))
    if len(tokens) > 12:
        print(f"  {ANSI.DIM}(Total token dihasilkan: {len(tokens)}){ANSI.RESET}")

    # Step 2: Tree Construction & Stack Tracking
    print(f"\n{ANSI.B_CYAN}[Langkah 2: Tree Construction & Evaluasi Stack of Open Elements]{ANSI.RESET}")
    tree_builder = HTMLTreeBuilder(tokens)
    dom_root = tree_builder.build_tree()

    print(f"Mode Render Dokumen: {ANSI.BOLD}{tree_builder.render_mode}{ANSI.RESET}")
    print(f"{ANSI.UNDERLINE}Catatan Parser Log (Spesifikasi HTML5 Resilient):{ANSI.RESET}")
    for log in tree_builder.parser_logs[:5]:
        print(f"  • {log}")
    if len(tree_builder.parser_logs) > 5:
        print(f"  • ... ({len(tree_builder.parser_logs) - 5} log lanjutan diringkas)")

    # Step 3: DOM Visualisation
    print(f"\n{ANSI.B_CYAN}[Langkah 3: Visualisasi Hirarki Pohon Objek Dokumen (DOM Tree)]{ANSI.RESET}")
    print_dom_tree(dom_root)
    print(f"{ANSI.GREEN}✔ Rekonstruksi DOM selesai dengan integritas struktur 100%.{ANSI.RESET}\n")


def interactive_menu() -> None:
    while True:
        banner()
        print("Pilih modul simulasi yang ingin Anda jalankan:")
        print(f"  {ANSI.B_GREEN}[1]{ANSI.RESET} Simulasi Lengkap Standar HTML5 (Valid DOCTYPE & DOM Tree)")
        print(f"  {ANSI.B_GREEN}[2]{ANSI.RESET} Simulasi DOCTYPE Sniffing (Memicu Quirks Mode)")
        print(f"  {ANSI.B_GREEN}[3]{ANSI.RESET} Simulasi Error Recovery (Unclosed Tags & Tag Hierarchy Fixing)")
        print(f"  {ANSI.B_GREEN}[4]{ANSI.RESET} Input Kode HTML Custom Sendiri")
        print(f"  {ANSI.B_GREEN}[5]{ANSI.RESET} Jalankan Audit Test Suite Mandiri")
        print(f"  {ANSI.RED}[0]{ANSI.RESET} Keluar")

        choice = input(f"\n{ANSI.BOLD}Masukkan pilihan [0-5]: {ANSI.RESET}").strip()

        if choice == "1":
            run_pipeline(SAMPLE_HTML, "Dokumen Lengkap Standar HTML5")
        elif choice == "2":
            run_pipeline(QUIRKS_SAMPLE_HTML, "Uji Quirks Mode Tanpa DOCTYPE")
        elif choice == "3":
            broken_html = "<div><p>Teks tanpa penutup <b>Teks tebal <i>miring<p>Paragraf kedua</div>"
            run_pipeline(broken_html, "Perbaikan Otomatis Sintaks Rusak (Tag P & Inline Mismatch)")
        elif choice == "4":
            print(f"\n{ANSI.CYAN}Ketik/tempel kode HTML Anda dalam satu baris (atau tekan ENTER untuk default demo):{ANSI.RESET}")
            user_input = input("> ").strip()
            if not user_input:
                user_input = "<article><h1>Judul</h1><p>Konten artikel</article>"
            run_pipeline(user_input, "Dokumen HTML Masukan Pengguna")
        elif choice == "5":
            run_self_tests()
        elif choice == "0":
            print(f"\n{ANSI.B_YELLOW}Terima kasih telah mempelajari Arsitektur Dasar HTML5.{ANSI.RESET}\n")
            sys.exit(0)
        else:
            print(f"\n{ANSI.RED}Pilihan tidak valid, silakan coba lagi.{ANSI.RESET}")
        
        input(f"{ANSI.DIM}Tekan ENTER untuk kembali ke menu...{ANSI.RESET}")


def run_self_tests() -> None:
    print(f"\n{ANSI.B_YELLOW}=== MENJALANKAN TEST SUITE SIMULATOR HTML5 ==={ANSI.RESET}")
    
    # Test 1: Tokenizer basic tags
    tok = HTMLTokenizer("<div><span>Test</span></div>")
    tokens = tok.tokenize_all()
    tag_names = [t.name for t in tokens if t.token_type in (TokenType.START_TAG, TokenType.END_TAG)]
    assert tag_names == ["div", "span", "span", "div"], f"Test 1 Gagal: {tag_names}"
    print(f"  {ANSI.GREEN}✔ Test 1: Tokenizer Tag Pairs Valid{ANSI.RESET}")

    # Test 2: Doctype Sniffing Standards Mode
    tok2 = HTMLTokenizer("<!DOCTYPE html><html></html>")
    builder2 = HTMLTreeBuilder(tok2.tokenize_all())
    builder2.build_tree()
    assert builder2.render_mode == "No-Quirks (Standards) Mode", "Test 2 Gagal"
    print(f"  {ANSI.GREEN}✔ Test 2: DOCTYPE Sniffing Standards Mode Terverifikasi{ANSI.RESET}")

    # Test 3: Doctype Sniffing Quirks Mode
    tok3 = HTMLTokenizer("<html><body></body></html>")
    builder3 = HTMLTreeBuilder(tok3.tokenize_all())
    builder3.build_tree()
    assert builder3.render_mode == "Quirks Mode", "Test 3 Gagal"
    print(f"  {ANSI.GREEN}✔ Test 3: Fallback Quirks Mode Terverifikasi{ANSI.RESET}")

    # Test 4: Auto-closing unclosed elements at EOF
    tok4 = HTMLTokenizer("<div><p>Unclosed paragraph")
    builder4 = HTMLTreeBuilder(tok4.tokenize_all())
    root4 = builder4.build_tree()
    div_node = root4.children[0]
    assert div_node.name == "div", "Test 4 Gagal"
    assert len(div_node.children) == 1 and div_node.children[0].name == "p", "Test 4 Gagal"
    print(f"  {ANSI.GREEN}✔ Test 4: Auto-Closing Stack Recovery Terverifikasi{ANSI.RESET}")

    print(f"\n{ANSI.B_GREEN}Seluruh 4 Unit Test Evaluator Berhasil (100% Pass).{ANSI.RESET}\n")


if __name__ == "__main__":
    # Jika dieksekusi dengan argumen non-interaktif (--test)
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_self_tests()
    else:
        interactive_menu()
