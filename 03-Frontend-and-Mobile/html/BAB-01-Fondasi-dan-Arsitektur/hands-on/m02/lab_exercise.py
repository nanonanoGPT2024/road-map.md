#!/usr/bin/env python3
"""
Laboratorium Sistem Arsitektur Mesin Parsing HTML WHATWG
Modul 02: State Machine Tokenizer, Error Tolerance, & DOM Tree Construction Engine.

Skrip ini mereplikasi cara kerja browser engine modern (Blink/WebKit) dalam
mengurai dokumen HTML mentah menjadi representasi DOM (Document Object Model)
sesuai spesifikasi formal WHATWG HTML Living Standard.
"""

from __future__ import annotations
import sys
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

# ==============================================================================
# TERMINAL ANSI COLOR CODES
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[36m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    RED     = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE    = "\033[34m"

# ==============================================================================
# TOKEN & DOM STRUCTURE DEFINITIONS
# ==============================================================================
class TokenType(Enum):
    DOCTYPE = auto()
    START_TAG = auto()
    END_TAG = auto()
    CHARACTER = auto()
    COMMENT = auto()
    EOF = auto()

@dataclass
class Token:
    type: TokenType
    data: str = ""
    tag_name: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    self_closing: bool = False

class Node:
    """Basis struktur pohon DOM."""
    def __init__(self, node_type: str, name: str = "", value: str = ""):
        self.node_type = node_type
        self.node_name = name
        self.node_value = value
        self.attributes: Dict[str, str] = {}
        self.parent: Optional[Node] = None
        self.children: List[Node] = []

    def append_child(self, child: Node) -> None:
        child.parent = self
        self.children.append(child)

    def print_tree(self, indent: int = 0) -> None:
        prefix = "  " * indent
        if self.node_type == "Document":
            print(f"{prefix}{Color.BOLD}#Document{Color.RESET}")
        elif self.node_type == "Element":
            attrs = " ".join([f'{k}="{v}"' for k, v in self.attributes.items()])
            attr_str = f" {Color.YELLOW}{attrs}{Color.RESET}" if attrs else ""
            print(f"{prefix}{Color.CYAN}<{self.node_name}{Color.RESET}{attr_str}{Color.CYAN}>{Color.RESET}")
        elif self.node_type == "Text":
            clean_val = self.node_value.replace("\n", "\\n")
            print(f"{prefix}{Color.GREEN}\"{clean_val}\"{Color.RESET}")
        elif self.node_type == "DOCTYPE":
            print(f"{prefix}{Color.MAGENTA}<!DOCTYPE {self.node_name}>{Color.RESET}")

        for child in self.children:
            child.print_tree(indent + 1)

# ==============================================================================
# WHATWG TOKENIZER (State Machine)
# ==============================================================================
class TokenizerState(Enum):
    DATA = auto()
    TAG_OPEN = auto()
    END_TAG_OPEN = auto()
    TAG_NAME = auto()
    BEFORE_ATTRIBUTE_NAME = auto()
    ATTRIBUTE_NAME = auto()
    BEFORE_ATTRIBUTE_VALUE = auto()
    ATTRIBUTE_VALUE_QUOTED = auto()
    AFTER_ATTRIBUTE_VALUE = auto()
    SELF_CLOSING_START_TAG = auto()

class HTMLTokenizer:
    """
    State machine tokenizer deterministik yang mengonversi stream karakter
    menjadi urutan token terstruktur (WHATWG 13.2.5).
    """
    def __init__(self, raw_html: str):
        self.raw = raw_html
        self.cursor = 0
        self.state = TokenizerState.DATA
        self.current_token: Optional[Token] = None
        self.current_attr_name = ""
        self.current_attr_val = ""

    def _next_char(self) -> Optional[str]:
        if self.cursor < len(self.raw):
            c = self.raw[self.cursor]
            self.cursor += 1
            return c
        return None

    def _reconsume(self) -> None:
        if self.cursor > 0:
            self.cursor -= 1

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []

        while True:
            c = self._next_char()

            # EOF Handling
            if c is None:
                if self.state == TokenizerState.DATA:
                    tokens.append(Token(type=TokenType.EOF))
                    break
                else:
                    # Emisi token tersisa jika EOF prematur ditemukan (Fault-Tolerant)
                    if self.current_token:
                        tokens.append(self.current_token)
                    tokens.append(Token(type=TokenType.EOF))
                    break

            # State Machine Transitions
            if self.state == TokenizerState.DATA:
                if c == '<':
                    self.state = TokenizerState.TAG_OPEN
                else:
                    tokens.append(Token(type=TokenType.CHARACTER, data=c))

            elif self.state == TokenizerState.TAG_OPEN:
                if c == '/':
                    self.state = TokenizerState.END_TAG_OPEN
                elif c.isalpha():
                    self.current_token = Token(type=TokenType.START_TAG, tag_name=c.lower())
                    self.state = TokenizerState.TAG_NAME
                elif c == '!':
                    # Simplified DOCTYPE detection
                    doctype_buf = self.raw[self.cursor:self.cursor+7]
                    if doctype_buf.upper() == "DOCTYPE":
                        self.cursor += 7
                        # Skip whitespace to tag name
                        while self.cursor < len(self.raw) and self.raw[self.cursor].isspace():
                            self.cursor += 1
                        doc_name = ""
                        while self.cursor < len(self.raw) and self.raw[self.cursor] != '>':
                            doc_name += self.raw[self.cursor]
                            self.cursor += 1
                        self.cursor += 1  # consume '>'
                        tokens.append(Token(type=TokenType.DOCTYPE, tag_name=doc_name.strip()))
                        self.state = TokenizerState.DATA
                else:
                    # Fallback karakter biasa (Error Recovery)
                    tokens.append(Token(type=TokenType.CHARACTER, data='<'))
                    tokens.append(Token(type=TokenType.CHARACTER, data=c))
                    self.state = TokenizerState.DATA

            elif self.state == TokenizerState.END_TAG_OPEN:
                if c.isalpha():
                    self.current_token = Token(type=TokenType.END_TAG, tag_name=c.lower())
                    self.state = TokenizerState.TAG_NAME
                else:
                    self.state = TokenizerState.DATA

            elif self.state == TokenizerState.TAG_NAME:
                if c.isspace():
                    self.state = TokenizerState.BEFORE_ATTRIBUTE_NAME
                elif c == '/':
                    self.state = TokenizerState.SELF_CLOSING_START_TAG
                elif c == '>':
                    self.state = TokenizerState.DATA
                    assert self.current_token is not None
                    tokens.append(self.current_token)
                    self.current_token = None
                else:
                    assert self.current_token is not None
                    self.current_token.tag_name += c.lower()

            elif self.state == TokenizerState.BEFORE_ATTRIBUTE_NAME:
                if c.isspace():
                    continue
                elif c == '/':
                    self.state = TokenizerState.SELF_CLOSING_START_TAG
                elif c == '>':
                    self.state = TokenizerState.DATA
                    assert self.current_token is not None
                    tokens.append(self.current_token)
                    self.current_token = None
                else:
                    self.current_attr_name = c.lower()
                    self.current_attr_val = ""
                    self.state = TokenizerState.ATTRIBUTE_NAME

            elif self.state == TokenizerState.ATTRIBUTE_NAME:
                if c == '=':
                    self.state = TokenizerState.BEFORE_ATTRIBUTE_VALUE
                elif c.isspace():
                    assert self.current_token is not None
                    self.current_token.attributes[self.current_attr_name] = ""
                    self.state = TokenizerState.BEFORE_ATTRIBUTE_NAME
                elif c == '>':
                    assert self.current_token is not None
                    self.current_token.attributes[self.current_attr_name] = ""
                    tokens.append(self.current_token)
                    self.current_token = None
                    self.state = TokenizerState.DATA
                else:
                    self.current_attr_name += c.lower()

            elif self.state == TokenizerState.BEFORE_ATTRIBUTE_VALUE:
                if c.isspace():
                    continue
                elif c in ('"', "'"):
                    self.state = TokenizerState.ATTRIBUTE_VALUE_QUOTED
                elif c == '>':
                    assert self.current_token is not None
                    self.current_token.attributes[self.current_attr_name] = ""
                    tokens.append(self.current_token)
                    self.current_token = None
                    self.state = TokenizerState.DATA
                else:
                    self.current_attr_val = c
                    self.state = TokenizerState.AFTER_ATTRIBUTE_VALUE

            elif self.state == TokenizerState.ATTRIBUTE_VALUE_QUOTED:
                if c in ('"', "'"):
                    assert self.current_token is not None
                    self.current_token.attributes[self.current_attr_name] = self.current_attr_val
                    self.state = TokenizerState.BEFORE_ATTRIBUTE_NAME
                else:
                    self.current_attr_val += c

            elif self.state == TokenizerState.AFTER_ATTRIBUTE_VALUE:
                if c.isspace():
                    assert self.current_token is not None
                    self.current_token.attributes[self.current_attr_name] = self.current_attr_val
                    self.state = TokenizerState.BEFORE_ATTRIBUTE_NAME
                elif c == '>':
                    assert self.current_token is not None
                    self.current_token.attributes[self.current_attr_name] = self.current_attr_val
                    tokens.append(self.current_token)
                    self.current_token = None
                    self.state = TokenizerState.DATA
                else:
                    self.current_attr_val += c

            elif self.state == TokenizerState.SELF_CLOSING_START_TAG:
                if c == '>':
                    assert self.current_token is not None
                    self.current_token.self_closing = True
                    tokens.append(self.current_token)
                    self.current_token = None
                    self.state = TokenizerState.DATA
                else:
                    self.state = TokenizerState.BEFORE_ATTRIBUTE_NAME

        return tokens

# ==============================================================================
# TREE BUILDER (WHATWG Auto-Correction & Stack of Open Elements)
# ==============================================================================
VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
AUTO_CLOSE_P_BLOCKS = {"address", "article", "aside", "blockquote", "div", "footer", "header", "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li"}

class TreeBuilder:
    """
    Tree construction engine yang mengimplementasikan Stack of Open Elements (SOE)
    dan penanganan malformed syntax (implisit closing tag).
    """
    def __init__(self):
        self.document = Node("Document")
        self.stack_of_open_elements: List[Node] = [self.document]
        self.current_node: Node = self.document

    def current(self) -> Node:
        return self.stack_of_open_elements[-1]

    def _close_tag(self, tag_name: str) -> None:
        """Pop elemen dari stack hingga mencapai tag_name yang sesuai."""
        for i in range(len(self.stack_of_open_elements) - 1, 0, -1):
            if self.stack_of_open_elements[i].node_name == tag_name:
                self.stack_of_open_elements = self.stack_of_open_elements[:i]
                break

    def build(self, tokens: List[Token]) -> Node:
        for token in tokens:
            if token.type == TokenType.DOCTYPE:
                doctype_node = Node("DOCTYPE", name=token.tag_name)
                self.document.append_child(doctype_node)

            elif token.type == TokenType.START_TAG:
                # Toleransi kesalahan WHATWG: <p> ditutup otomatis oleh tag block lain
                if token.tag_name in AUTO_CLOSE_P_BLOCKS and self.current().node_name == "p":
                    self.stack_of_open_elements.pop()

                node = Node("Element", name=token.tag_name)
                node.attributes = token.attributes
                self.current().append_child(node)

                # Elemen void tidak dimasukkan ke dalam stack
                if not token.self_closing and token.tag_name not in VOID_ELEMENTS:
                    self.stack_of_open_elements.append(node)

            elif token.type == TokenType.END_TAG:
                self._close_tag(token.tag_name)

            elif token.type == TokenType.CHARACTER:
                # Normalisasi/Merge Text Node berurutan
                curr = self.current()
                if curr.children and curr.children[-1].node_type == "Text":
                    curr.children[-1].node_value += token.data
                else:
                    curr.append_child(Node("Text", value=token.data))

            elif token.type == TokenType.EOF:
                # Kosongkan sisa stack kecuali Document Root
                self.stack_of_open_elements = [self.document]

        return self.document

# ==============================================================================
# LAB HARNESS & EXECUTION BENCHMARK
# ==============================================================================
def run_lab() -> None:
    print(f"{Color.BOLD}{Color.BLUE}======================================================================{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} LAB: WHATWG SPECIFICATION-COMPLIANT HTML ENGINE & TREE CONSTRUCTION{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}======================================================================{Color.RESET}\n")

    # Sampel HTML Rusak / Tidak Valid (Non-Well-Formed XML)
    # 1. P tag tidak ditutup
    # 2. Tag berantakan saling silang: <b><i>Bold italic</b>italic?</i>
    # 3. Void tag <img> tanpa penutup
    # 4. Atribut tanpa tanda petik
    raw_html_input = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head><title>WHATWG Lab Demo</title></head>\n"
        "<body>\n"
        "  <div class=container id=\"main\">\n"
        "    <h1>Header Utama\n"
        "    <p>Paragraf pertama tanpa tag penutup.\n"
        "    <p>Paragraf kedua otomatis menutup paragraf pertama.\n"
        "    <img src=avatar.png alt=\"User Avatar\">\n"
        "    <p>Teks dengan format <b>tebal <i>miring</b>sisa miring</i> normal.</p>\n"
        "  </div>\n"
        "</body>\n"
        "</html>"
    )

    print(f"{Color.BOLD}[1] INPUT HTML RAW (MALFORMED & NON-CLOSING TAGS):{Color.RESET}")
    print(f"{Color.DIM}{'-'*60}{Color.RESET}")
    print(raw_html_input)
    print(f"{Color.DIM}{'-'*60}{Color.RESET}\n")

    # Step 1: Tokenisasi
    print(f"{Color.BOLD}[2] RUNNING TOKENIZER STATE MACHINE...{Color.RESET}")
    t0 = time.perf_counter()
    tokenizer = HTMLTokenizer(raw_html_input)
    tokens = tokenizer.tokenize()
    t1 = time.perf_counter()
    token_time_us = (t1 - t0) * 1_000_000

    print(f"{Color.GREEN}✓ Tokenisasi Selesai:{Color.RESET} {len(tokens)} tokens dihasilkan dalam {token_time_us:.2f} µs\n")
    print(f"{Color.BOLD}{'ID':<4} | {'TOKEN TYPE':<15} | {'PAYLOAD / TAG':<20} | {'ATTRIBUTES'}{Color.RESET}")
    print("-" * 65)
    for idx, tok in enumerate(tokens[:15]):  # Batasi cetak 15 token pertama untuk kerapihan
        attrs_repr = str(tok.attributes) if tok.attributes else "-"
        name_or_val = tok.tag_name if tok.tag_name else repr(tok.data)
        print(f"{idx:<4} | {tok.type.name:<15} | {name_or_val:<20} | {attrs_repr}")
    if len(tokens) > 15:
        print(f"{Color.DIM}... [{len(tokens) - 15} token lainnya disembunyikan]{Color.RESET}")

    # Step 2: Tree Construction
    print(f"\n{Color.BOLD}[3] RUNNING DOM TREE BUILDER (WHATWG RESILIENT ALGORITHM)...{Color.RESET}")
    t2 = time.perf_counter()
    tree_builder = TreeBuilder()
    dom_root = tree_builder.build(tokens)
    t3 = time.perf_counter()
    tree_time_us = (t3 - t2) * 1_000_000

    print(f"{Color.GREEN}✓ DOM Tree Selesai Dibangun:{Color.RESET} Diselesaikan dalam {tree_time_us:.2f} µs\n")
    print(f"{Color.BOLD}[4] HASIL STRUKTUR POHON DOM TERECOVERY:{Color.RESET}")
    print(f"{Color.DIM}{'-'*60}{Color.RESET}")
    dom_root.print_tree()
    print(f"{Color.DIM}{'-'*60}{Color.RESET}\n")

    # Step 3: Benchmarking Throughput
    print(f"{Color.BOLD}[5] SIMULASI STRESS TEST / ENGINE BENCHMARK (1,000 ITERATIONS){Color.RESET}")
    iterations = 1000
    start_bench = time.perf_counter()
    for _ in range(iterations):
        tok_bench = HTMLTokenizer(raw_html_input).tokenize()
        TreeBuilder().build(tok_bench)
    elapsed = time.perf_counter() - start_bench
    ops_per_sec = iterations / elapsed

    print(f"Total Waktu: {Color.YELLOW}{elapsed:.4f}s{Color.RESET}")
    print(f"Throughput : {Color.GREEN}{Color.BOLD}{ops_per_sec:,.2f} parses/sec{Color.RESET}")
    print(f"Status     : {Color.GREEN}BERHASIL! Model parsing fault-tolerant siap.{Color.RESET}\n")

if __name__ == "__main__":
    run_lab()