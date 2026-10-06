#!/usr/bin/env python3
"""
Lab Exercise: TypeScript Compiler Internals & Monorepo Tooling Simulation
BAB-09: Compiler Internals, Project References, and Monorepo Orchestration

Simulates the core phases of the TypeScript compiler (tsc):
1. Scanner / Lexer (Tokenization)
2. Parser (Abstract Syntax Tree generation)
3. Binder (Symbol Table creation and Scope Resolution)
4. TypeChecker (Structural Type Checking and TS Diagnostics)
5. Emitter (Transpilation to JavaScript)
6. Monorepo Project Reference Dependency Graph & Topological Build
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Set


# ==============================================================================
# ANSI Terminal Colors
# ==============================================================================
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


def header(title: str):
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 70}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE} [SIMULASI TS COMPILER] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 70}{Color.RESET}")


def step_banner(num: int, name: str):
    print(f"\n{Color.BOLD}{Color.YELLOW}--- Phase {num}: {name} ---{Color.RESET}")


# ==============================================================================
# Phase 1: Scanner / Lexer
# ==============================================================================
class SyntaxKind(Enum):
    KEYWORD_LET = auto()
    KEYWORD_CONST = auto()
    KEYWORD_TYPE = auto()
    IDENTIFIER = auto()
    COLON = auto()
    EQUALS = auto()
    SEMICOLON = auto()
    TYPE_NUMBER = auto()
    TYPE_STRING = auto()
    LITERAL_NUMBER = auto()
    LITERAL_STRING = auto()
    EOF = auto()


@dataclass
class Token:
    kind: SyntaxKind
    text: str
    pos: int


class Scanner:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0

    def tokenize(self) -> List[Token]:
        tokens = []
        keywords = {
            "let": SyntaxKind.KEYWORD_LET,
            "const": SyntaxKind.KEYWORD_CONST,
            "type": SyntaxKind.KEYWORD_TYPE,
            "number": SyntaxKind.TYPE_NUMBER,
            "string": SyntaxKind.TYPE_STRING,
        }

        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch.isspace():
                self.pos += 1
                continue

            start = self.pos
            if ch == ":":
                tokens.append(Token(SyntaxKind.COLON, ":", start))
                self.pos += 1
            elif ch == "=":
                tokens.append(Token(SyntaxKind.EQUALS, "=", start))
                self.pos += 1
            elif ch == ";":
                tokens.append(Token(SyntaxKind.SEMICOLON, ";", start))
                self.pos += 1
            elif ch.isdigit():
                while self.pos < len(self.source) and self.source[self.pos].isdigit():
                    self.pos += 1
                tokens.append(Token(SyntaxKind.LITERAL_NUMBER, self.source[start:self.pos], start))
            elif ch == '"' or ch == "'":
                quote = ch
                self.pos += 1
                while self.pos < len(self.source) and self.source[self.pos] != quote:
                    self.pos += 1
                self.pos += 1  # closing quote
                tokens.append(Token(SyntaxKind.LITERAL_STRING, self.source[start:self.pos], start))
            elif ch.isalpha() or ch == "_":
                while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
                    self.pos += 1
                word = self.source[start:self.pos]
                kind = keywords.get(word, SyntaxKind.IDENTIFIER)
                tokens.append(Token(kind, word, start))
            else:
                self.pos += 1

        tokens.append(Token(SyntaxKind.EOF, "<EOF>", self.pos))
        return tokens


# ==============================================================================
# Phase 2: Parser & AST
# ==============================================================================
@dataclass
class ASTNode:
    kind: str
    children: List["ASTNode"] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)

    def print_tree(self, indent: int = 0):
        prefix = "  " * indent
        attr_str = " ".join(f"{k}='{v}'" for k, v in self.attributes.items())
        print(f"{prefix}{Color.MAGENTA}Node({self.kind}){Color.RESET} {Color.DIM}{attr_str}{Color.RESET}")
        for child in self.children:
            child.print_tree(indent + 1)


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.index = 0

    def current(self) -> Token:
        return self.tokens[self.index]

    def consume(self, expected: SyntaxKind) -> Token:
        t = self.current()
        if t.kind == expected:
            self.index += 1
            return t
        raise ValueError(f"Expected {expected}, got {t.kind} at pos {t.pos}")

    def parse(self) -> ASTNode:
        root = ASTNode(kind="SourceFile")
        while self.current().kind != SyntaxKind.EOF:
            if self.current().kind in (SyntaxKind.KEYWORD_LET, SyntaxKind.KEYWORD_CONST):
                decl_kind = self.current().text
                self.index += 1
                ident = self.consume(SyntaxKind.IDENTIFIER)
                
                type_name = "any"
                if self.current().kind == SyntaxKind.COLON:
                    self.consume(SyntaxKind.COLON)
                    t_tok = self.current()
                    type_name = t_tok.text
                    self.index += 1

                self.consume(SyntaxKind.EQUALS)
                val_tok = self.current()
                val_type = "string" if val_tok.kind == SyntaxKind.LITERAL_STRING else "number"
                val_str = val_tok.text
                self.index += 1

                if self.current().kind == SyntaxKind.SEMICOLON:
                    self.consume(SyntaxKind.SEMICOLON)

                decl_node = ASTNode(
                    kind="VariableDeclaration",
                    attributes={
                        "keyword": decl_kind,
                        "name": ident.text,
                        "declaredType": type_name,
                        "value": val_str,
                        "inferredValueType": val_type
                    }
                )
                root.children.append(decl_node)
            else:
                self.index += 1
        return root


# ==============================================================================
# Phase 3 & 4: Binder & TypeChecker
# ==============================================================================
@dataclass
class Symbol:
    name: str
    declared_type: str
    value: str
    inferred_type: str


class TypeChecker:
    def __init__(self, ast: ASTNode):
        self.ast = ast
        self.symbol_table: Dict[str, Symbol] = {}
        self.diagnostics: List[str] = []

    def bind_and_check(self):
        # Binding Phase
        for node in self.ast.children:
            if node.kind == "VariableDeclaration":
                name = node.attributes["name"]
                sym = Symbol(
                    name=name,
                    declared_type=node.attributes["declaredType"],
                    value=node.attributes["value"],
                    inferred_type=node.attributes["inferredValueType"]
                )
                self.symbol_table[name] = sym

        # Type Checking Phase
        for name, sym in self.symbol_table.items():
            if sym.declared_type != "any" and sym.declared_type != sym.inferred_type:
                diag = (
                    f"{Color.RED}error TS2322: Type '{sym.inferred_type}' is not assignable "
                    f"to type '{sym.declared_type}'.{Color.RESET}\n"
                    f"  Variable '{Color.BOLD}{name}{Color.RESET}' declared with type '{sym.declared_type}' "
                    f"assigned value {sym.value}"
                )
                self.diagnostics.append(diag)


# ==============================================================================
# Phase 5: Emitter (JS Transpilation)
# ==============================================================================
class Emitter:
    @staticmethod
    def emit_js(ast: ASTNode, target_es5: bool = False) -> str:
        lines = []
        for node in ast.children:
            if node.kind == "VariableDeclaration":
                kw = "var" if target_es5 else node.attributes["keyword"]
                name = node.attributes["name"]
                val = node.attributes["value"]
                lines.append(f"{kw} {name} = {val};")
        return "\n".join(lines)


# ==============================================================================
# Phase 6: Monorepo Project References & Build Orchestration
# ==============================================================================
@dataclass
class ProjectPackage:
    name: str
    path: str
    dependencies: List[str] = field(default_factory=list)


class MonorepoOrchestrator:
    def __init__(self, packages: List[ProjectPackage]):
        self.packages = {pkg.name: pkg for pkg in packages}

    def compute_build_order(self) -> List[str]:
        # Topological Sort (Kahn's Algorithm)
        in_degree = {name: 0 for name in self.packages}
        adj: Dict[str, List[str]] = {name: [] for name in self.packages}

        for name, pkg in self.packages.items():
            for dep in pkg.dependencies:
                if dep in adj:
                    adj[dep].append(name)
                    in_degree[name] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.packages):
            raise RuntimeError("Circular dependency detected in Project References!")
        return order


# ==============================================================================
# Interactive Terminal Runner
# ==============================================================================
def run_interactive_lab():
    header("TypeScript Compiler Internals & Monorepo Tooling")
    print(f"{Color.WHITE}Selamat datang di simulasi arsitektur internal compiler TypeScript (tsc){Color.RESET}")
    print(f"Materi: Scanner -> Parser -> Binder -> TypeChecker -> Emitter -> Project References\n")

    sample_ts = """
const port: number = 8080;
let serviceName: string = "AuthGateway";
let invalidAssignment: number = "BukanAngka";
let dynamicConfig: any = 42;
""".strip()

    print(f"{Color.BOLD}Contoh Kode TypeScript:{Color.RESET}")
    for line in sample_ts.split("\n"):
        print(f"  {Color.CYAN}|{Color.RESET} {line}")

    # Step 1: Scanner
    step_banner(1, "Scanner / Lexical Analyzer (Tokens)")
    scanner = Scanner(sample_ts)
    tokens = scanner.tokenize()
    print(f"Dihasilkan {Color.GREEN}{len(tokens)}{Color.RESET} tokens:")
    for tok in tokens[:8]:
        print(f"  [{tok.kind.name:<18}] -> '{tok.text}'")
    print(f"  {Color.DIM}... dan {len(tokens)-8} token lainnya.{Color.RESET}")

    # Step 2: Parser
    step_banner(2, "Parser -> Abstract Syntax Tree (AST)")
    parser = Parser(tokens)
    ast = parser.parse()
    ast.print_tree()

    # Step 3 & 4: Binder & TypeChecker
    step_banner(3, "Binder (Symbols) & TypeChecker (Diagnostics)")
    checker = TypeChecker(ast)
    checker.bind_and_check()

    print(f"{Color.BOLD}Symbol Table:{Color.RESET}")
    for sym_name, sym in checker.symbol_table.items():
        print(f"  - Symbol '{Color.GREEN}{sym_name}{Color.RESET}': declared={sym.declared_type}, inferred={sym.inferred_type}")

    print(f"\n{Color.BOLD}Diagnostic Results:{Color.RESET}")
    if checker.diagnostics:
        for diag in checker.diagnostics:
            print(f"  {diag}\n")
    else:
        print(f"  {Color.GREEN}✓ No type diagnostics found.{Color.RESET}")

    # Step 5: Emitter
    step_banner(4, "Emitter (Code Generation)")
    js_modern = Emitter.emit_js(ast, target_es5=False)
    js_es5 = Emitter.emit_js(ast, target_es5=True)
    print(f"{Color.BOLD}[Target: ESNext/ES2022]{Color.RESET}\n{Color.DIM}{js_modern}{Color.RESET}\n")
    print(f"{Color.BOLD}[Target: ES5]{Color.RESET}\n{Color.DIM}{js_es5}{Color.RESET}")

    # Step 6: Monorepo Orchestrator
    step_banner(5, "Monorepo Project References (tsc -b)")
    pkgs = [
        ProjectPackage(name="@monorepo/tsconfig", path="packages/tsconfig", dependencies=[]),
        ProjectPackage(name="@monorepo/types", path="packages/types", dependencies=["@monorepo/tsconfig"]),
        ProjectPackage(name="@monorepo/utils", path="packages/utils", dependencies=["@monorepo/types"]),
        ProjectPackage(name="@monorepo/core", path="packages/core", dependencies=["@monorepo/utils", "@monorepo/types"]),
        ProjectPackage(name="@monorepo/api", path="packages/api", dependencies=["@monorepo/core"]),
    ]

    print("Struktur Dependensi Monorepo:")
    for p in pkgs:
        dep_str = ", ".join(p.dependencies) if p.dependencies else "(None)"
        print(f"  * {Color.BOLD}{p.name:<18}{Color.RESET} -> Depends on: {Color.CYAN}{dep_str}{Color.RESET}")

    orchestrator = MonorepoOrchestrator(pkgs)
    build_order = orchestrator.compute_build_order()

    print(f"\n{Color.GREEN}{Color.BOLD}Urutan Kompilasi Otomatis (Topological Build Order):{Color.RESET}")
    for idx, pkg_name in enumerate(build_order, 1):
        print(f"  {idx}. {Color.BOLD}{pkg_name}{Color.RESET} [{Color.DIM}packages/{pkg_name.split('/')[1]}{Color.RESET}]")

    print(f"\n{Color.BOLD}{Color.GREEN}✓ Simulasi Compiler Internals & Monorepo Tooling Selesai.{Color.RESET}\n")


if __name__ == "__main__":
    run_interactive_lab()
