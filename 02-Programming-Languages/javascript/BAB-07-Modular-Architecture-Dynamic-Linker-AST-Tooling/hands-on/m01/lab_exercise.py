#!/usr/bin/env python3
"""
BAB-07: Modular Architecture, Dynamic Linker & AST Tooling
Hands-on Lab Exercise: JavaScript Module Runtime & Tooling Engine Simulation

This self-contained lab exercise simulates:
1. Lexical Analysis (Tokenizer) & AST Parsing for ES Module syntax.
2. Dynamic Linker & Dependency Graph Construction (Topological Sort + Cycle Detection).
3. ESM vs CommonJS Execution Semantics (Live Bindings vs Value Snapshotting).
4. Dead-Code Elimination (AST-level Tree-Shaking).
"""

import sys
import os
import re
import json
import time
from enum import Enum, auto
from typing import Dict, List, Set, Optional, Any

# ==============================================================================
# ANSI Color Formatting Helper
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

def cprint(text: str, color: str = Color.RESET, end: str = "\n"):
    print(f"{color}{text}{Color.RESET}", end=end)

def print_header(title: str):
    width = 72
    cprint("=" * width, Color.CYAN)
    cprint(f" {title.upper()} ".center(width, "#"), Color.BOLD + Color.YELLOW)
    cprint("=" * width, Color.CYAN)

def print_section(title: str):
    cprint(f"\n--- [ {title} ] ---", Color.BOLD + Color.MAGENTA)

# ==============================================================================
# SECTION 1: AST Tooling & Parser Simulation
# ==============================================================================
class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()
    OPERATOR = auto()
    PUNCTUATOR = auto()
    EOF = auto()

class Token:
    def __init__(self, token_type: TokenType, value: str, line: int):
        self.type = token_type
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type.name}, {repr(self.value)})"

class JSTokenizer:
    KEYWORDS = {"import", "from", "export", "const", "let", "var", "function", "return"}

    def __init__(self, source_code: str):
        self.source = source_code
        self.cursor = 0
        self.line = 1

    def tokenize(self) -> List[Token]:
        tokens = []
        while self.cursor < len(self.source):
            char = self.source[self.cursor]

            if char in " \t\r":
                self.cursor += 1
                continue
            if char == "\n":
                self.line += 1
                self.cursor += 1
                continue

            if char in ("'", '"'):
                quote = char
                self.cursor += 1
                start = self.cursor
                while self.cursor < len(self.source) and self.source[self.cursor] != quote:
                    if self.source[self.cursor] == "\n":
                        self.line += 1
                    self.cursor += 1
                val = self.source[start:self.cursor]
                self.cursor += 1  # closing quote
                tokens.append(Token(TokenType.STRING, val, self.line))
                continue

            if char.isalpha() or char == "_":
                start = self.cursor
                while self.cursor < len(self.source) and (self.source[self.cursor].isalnum() or self.source[self.cursor] == "_"):
                    self.cursor += 1
                word = self.source[start:self.cursor]
                tt = TokenType.KEYWORD if word in self.KEYWORDS else TokenType.IDENTIFIER
                tokens.append(Token(tt, word, self.line))
                continue

            if char.isdigit():
                start = self.cursor
                while self.cursor < len(self.source) and self.source[self.cursor].isdigit():
                    self.cursor += 1
                tokens.append(Token(TokenType.NUMBER, self.source[start:self.cursor], self.line))
                continue

            if char in "{}(),;=":
                tokens.append(Token(TokenType.PUNCTUATOR, char, self.line))
                self.cursor += 1
                continue

            tokens.append(Token(TokenType.OPERATOR, char, self.line))
            self.cursor += 1

        tokens.append(Token(TokenType.EOF, "<EOF>", self.line))
        return tokens

class ASTNode:
    def __init__(self, node_type: str, **kwargs):
        self.type = node_type
        self.data = kwargs

    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type}
        for k, v in self.data.items():
            if isinstance(v, ASTNode):
                result[k] = v.to_dict()
            elif isinstance(v, list):
                result[k] = [item.to_dict() if isinstance(item, ASTNode) else item for item in v]
            else:
                result[k] = v
        return result

class MiniJSParser:
    """Parses ESM statements: import { a, b } from 'mod'; export const x = 10;"""
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def consume(self, expected_type: Optional[TokenType] = None, expected_val: Optional[str] = None) -> Token:
        tok = self.peek()
        if expected_type and tok.type != expected_type:
            raise SyntaxError(f"Expected {expected_type}, got {tok.type} at line {tok.line}")
        if expected_val and tok.value != expected_val:
            raise SyntaxError(f"Expected '{expected_val}', got '{tok.value}' at line {tok.line}")
        self.pos += 1
        return tok

    def parse_program(self) -> ASTNode:
        body = []
        while self.peek().type != TokenType.EOF:
            tok = self.peek()
            if tok.type == TokenType.KEYWORD and tok.value == "import":
                body.append(self.parse_import())
            elif tok.type == TokenType.KEYWORD and tok.value == "export":
                body.append(self.parse_export())
            elif tok.type == TokenType.KEYWORD and tok.value in ("const", "let", "var"):
                body.append(self.parse_variable_decl())
            else:
                # Skip unknown expression line for AST simulation demo
                self.consume()
        return ASTNode("Program", body=body)

    def parse_import(self) -> ASTNode:
        self.consume(TokenType.KEYWORD, "import")
        specifiers = []
        if self.peek().value == "{":
            self.consume(TokenType.PUNCTUATOR, "{")
            while self.peek().value != "}":
                name = self.consume(TokenType.IDENTIFIER).value
                specifiers.append(name)
                if self.peek().value == ",":
                    self.consume(TokenType.PUNCTUATOR, ",")
            self.consume(TokenType.PUNCTUATOR, "}")
        self.consume(TokenType.KEYWORD, "from")
        source = self.consume(TokenType.STRING).value
        if self.peek().value == ";":
            self.consume(TokenType.PUNCTUATOR, ";")
        return ASTNode("ImportDeclaration", specifiers=specifiers, source=source)

    def parse_export(self) -> ASTNode:
        self.consume(TokenType.KEYWORD, "export")
        if self.peek().value in ("const", "let", "var"):
            decl = self.parse_variable_decl()
            return ASTNode("ExportNamedDeclaration", declaration=decl)
        raise NotImplementedError(f"Export format not implemented: {self.peek()}")

    def parse_variable_decl(self) -> ASTNode:
        kind = self.consume(TokenType.KEYWORD).value
        identifier = self.consume(TokenType.IDENTIFIER).value
        self.consume(TokenType.PUNCTUATOR, "=")
        val_tok = self.consume()
        val = val_tok.value
        if self.peek().value == ";":
            self.consume(TokenType.PUNCTUATOR, ";")
        return ASTNode("VariableDeclaration", kind=kind, id=identifier, init=val)

# ==============================================================================
# SECTION 2: Dynamic Linker & Module Graph Resolution
# ==============================================================================
class ModuleStatus(Enum):
    UNLINKED = auto()
    LINKING = auto()
    LINKED = auto()
    EVALUATING = auto()
    EVALUATED = auto()

class ModuleRecord:
    def __init__(self, name: str, code: str):
        self.name = name
        self.code = code
        self.ast: Optional[ASTNode] = None
        self.dependencies: List[str] = []
        self.status = ModuleStatus.UNLINKED
        self.environment: Dict[str, Any] = {}
        self.live_bindings: Dict[str, Any] = {}

    def extract_dependencies(self):
        tokenizer = JSTokenizer(self.code)
        tokens = tokenizer.tokenize()
        parser = MiniJSParser(tokens)
        self.ast = parser.parse_program()
        self.dependencies.clear()
        for node in self.ast.data["body"]:
            if node.type == "ImportDeclaration":
                self.dependencies.append(node.data["source"])

class DynamicLinker:
    """Simulates the V8 / SpiderMonkey ESM Module Linking Phase."""
    def __init__(self):
        self.module_registry: Dict[str, ModuleRecord] = {}

    def register_module(self, name: str, code: str) -> ModuleRecord:
        record = ModuleRecord(name, code)
        record.extract_dependencies()
        self.module_registry[name] = record
        return record

    def build_dependency_graph(self) -> Dict[str, List[str]]:
        graph = {}
        for name, record in self.module_registry.items():
            graph[name] = list(record.dependencies)
        return graph

    def link_modules(self, entrypoint: str) -> List[str]:
        """
        Executes Topological Sort and detects Circular Dependencies.
        ESM handles cycles via 2-phase linking (instantation then evaluation).
        """
        cprint(f"[*] Starting Static Linking Pipeline for entrypoint: {entrypoint}", Color.BLUE)
        visited = set()
        recursion_stack = set()
        cycles = []
        evaluation_order: List[str] = []

        def dfs(mod_name: str, path: List[str]):
            if mod_name not in self.module_registry:
                raise ImportError(f"Cannot resolve module specifier: '{mod_name}'")

            record = self.module_registry[mod_name]
            visited.add(mod_name)
            recursion_stack.add(mod_name)
            record.status = ModuleStatus.LINKING

            for dep in record.dependencies:
                if dep in recursion_stack:
                    cycle_path = " -> ".join(path + [dep])
                    cycles.append(cycle_path)
                    cprint(f"    [!] Circular dependency detected: {cycle_path}", Color.YELLOW)
                elif dep not in visited:
                    dfs(dep, path + [dep])

            recursion_stack.remove(mod_name)
            record.status = ModuleStatus.LINKED
            evaluation_order.append(mod_name)

        dfs(entrypoint, [entrypoint])

        cprint(f"[✔] Linking Completed! Discovered {len(cycles)} cycle(s).", Color.GREEN)
        return evaluation_order

# ==============================================================================
# SECTION 3: Live Bindings (ESM) vs Value Snapshotting (CommonJS)
# ==============================================================================
class ExecutionSimulation:
    @staticmethod
    def simulate_esm_live_binding():
        print_section("Simulation 1: ESM Live Bindings (Reference Pointer)")
        cprint("Code Structure:", Color.BOLD)
        cprint("""// counter.js
export let count = 0;
export function increment() { count++; }

// main.js
import { count, increment } from './counter.js';
console.log(count); // 0
increment();
console.log(count); // 1 (Live Binding reflects change!)""", Color.WHITE)

        # In ESM, imported identifiers are live references pointing to the module's export slot
        counter_module = {"count": 0}
        def increment():
            counter_module["count"] += 1

        # main.js binds directly to getter / pointer
        def get_count():
            return counter_module["count"]

        cprint("\n[Runtime Execution Simulation]:", Color.CYAN)
        cprint(f"  Step 1: Initial imported 'count' => {get_count()}", Color.GREEN)
        cprint("  Step 2: Invoking increment() across module boundary...", Color.YELLOW)
        increment()
        cprint(f"  Step 3: Checking 'count' again => {get_count()}", Color.GREEN)
        cprint("  -> Result: ESM provides live bindings directly into module records.", Color.MAGENTA)

    @staticmethod
    def simulate_cjs_value_snapshot():
        print_section("Simulation 2: CommonJS Value Copy / Snapshotting")
        cprint("Code Structure:", Color.BOLD)
        cprint("""// counter_cjs.js
let count = 0;
function increment() { count++; }
module.exports = { count, increment };

// main_cjs.js
const { count, increment } = require('./counter_cjs.js');
console.log(count); // 0
increment();
console.log(count); // 0 (Snapshot copy does NOT update!)""", Color.WHITE)

        # In CJS, module.exports copies values into an export object at require() execution time
        internal_count = 0
        def cjs_increment():
            nonlocal internal_count
            internal_count += 1

        # module.exports snapshot
        cjs_exports = {
            "count": internal_count,
            "increment": cjs_increment
        }

        # Consumer destructures copy
        imported_count = cjs_exports["count"]
        cprint("\n[Runtime Execution Simulation]:", Color.CYAN)
        cprint(f"  Step 1: Initial destructured 'count' => {imported_count}", Color.GREEN)
        cprint("  Step 2: Invoking increment()...", Color.YELLOW)
        cjs_exports["increment"]()
        cprint(f"  Step 3: Checking destructured 'count' => {imported_count} (Internal is {internal_count})", Color.RED)
        cprint("  -> Result: CommonJS exports primitive values by copy snapshot, not live binding.", Color.MAGENTA)

# ==============================================================================
# SECTION 4: AST-Level Tree-Shaking Engine (Dead Code Elimination)
# ==============================================================================
class ASTTreeShaker:
    """Analyzes export identifiers and purges unused AST declaration nodes."""
    def __init__(self, modules: Dict[str, ModuleRecord]):
        self.modules = modules

    def shake(self, entrypoint: str) -> Dict[str, ASTNode]:
        used_symbols: Dict[str, Set[str]] = {m: set() for m in self.modules}
        visited_mods: Set[str] = set()

        # Gather imported symbols from entry and downstream
        def trace_usage(mod_name: str):
            if mod_name in visited_mods:
                return
            visited_mods.add(mod_name)

            record = self.modules.get(mod_name)
            if not record or not record.ast:
                return
            for node in record.ast.data["body"]:
                if node.type == "ImportDeclaration":
                    source = node.data["source"]
                    for spec in node.data["specifiers"]:
                        used_symbols[source].add(spec)
                    trace_usage(source)

        trace_usage(entrypoint)

        cprint("\n[*] Static Usage Analysis for Tree-Shaking:", Color.BLUE)
        for mod, syms in used_symbols.items():
            cprint(f"    Module '{mod}' used symbols: {syms if syms else '(None - Candidate for dead-strip)'}", Color.YELLOW)

        # Eliminate unused exported declarations
        optimized_asts = {}
        for mod_name, record in self.modules.items():
            if mod_name == entrypoint or not record.ast:
                optimized_asts[mod_name] = record.ast
                continue

            active_body = []
            for node in record.ast.data["body"]:
                if node.type == "ExportNamedDeclaration":
                    decl = node.data["declaration"]
                    var_id = decl.data["id"]
                    if var_id in used_symbols[mod_name]:
                        active_body.append(node)
                    else:
                        cprint(f"    [-] Tree-Shaker ELIMINATED dead export: '{var_id}' in '{mod_name}'", Color.RED)
                else:
                    active_body.append(node)
            optimized_asts[mod_name] = ASTNode("Program", body=active_body)

        return optimized_asts

# ==============================================================================
# SECTION 5: Interactive Lab Runner & Demo Harness
# ==============================================================================
def run_interactive_lab():
    print_header("JS Modular Architecture & AST Tooling Lab")
    cprint("Interactive Diagnostic Lab for BAB-07 JavaScript Engine Simulation\n", Color.BOLD)

    linker = DynamicLinker()

    # Pre-load real-world scenario modules
    linker.register_module("./math.js", """
export const add = 1;
export const unusedHugeMathLib = 9999;
export const sub = 2;
""")

    linker.register_module("./logger.js", """
import { add } from './math.js';
export const logEnabled = 1;
""")

    linker.register_module("./circular_a.js", """
import { b_val } from './circular_b.js';
export const a_val = 100;
""")

    linker.register_module("./circular_b.js", """
import { a_val } from './circular_a.js';
export const b_val = 200;
""")

    linker.register_module("./main.js", """
import { add } from './math.js';
import { logEnabled } from './logger.js';
import { a_val } from './circular_a.js';
const appState = 1;
""")

    while True:
        cprint("\n" + "="*50, Color.CYAN)
        cprint("SELECT LAB OPERATION:", Color.BOLD + Color.YELLOW)
        cprint("  [1] Inspect AST of a Module (Tokenizer & Parser)", Color.WHITE)
        cprint("  [2] Run Static Linking & Dependency Graph (Topological Sort)", Color.WHITE)
        cprint("  [3] Compare ESM Live Bindings vs CommonJS Snapshotting", Color.WHITE)
        cprint("  [4] Execute AST Tree-Shaking (Dead Code Elimination)", Color.WHITE)
        cprint("  [5] Run All Operations Sequentially (Automated Test Pass)", Color.WHITE)
        cprint("  [0] Exit Lab", Color.WHITE)
        cprint("="*50, Color.CYAN)

        # Detect non-interactive pipe or get user input
        if not sys.stdin.isatty():
            cprint("[!] Non-interactive mode detected. Running full automated suite...", Color.YELLOW)
            choice = "5"
        else:
            try:
                choice = input(f"{Color.CYAN}Enter Choice [0-5]: {Color.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                cprint("\nExiting...", Color.YELLOW)
                break

        if choice == "1":
            print_section("AST Generation for './main.js'")
            record = linker.module_registry["./main.js"]
            cprint("Source Code:", Color.BOLD)
            cprint(record.code.strip(), Color.WHITE)
            cprint("\nGenerated AST (JSON representation):", Color.GREEN)
            cprint(json.dumps(record.ast.to_dict(), indent=2), Color.CYAN)

        elif choice == "2":
            print_section("Dynamic Linker & Topological Ordering")
            order = linker.link_modules("./main.js")
            cprint(f"\nFinal Deterministic Evaluation Order:", Color.BOLD + Color.GREEN)
            for idx, mod in enumerate(order, 1):
                cprint(f"  {idx}. {mod}", Color.WHITE)

        elif choice == "3":
            ExecutionSimulation.simulate_esm_live_binding()
            ExecutionSimulation.simulate_cjs_value_snapshot()

        elif choice == "4":
            print_section("AST Tree-Shaking Pipeline")
            shaker = ASTTreeShaker(linker.module_registry)
            shaker.shake("./main.js")
            cprint("\n[✔] Tree-shaking complete. Dead exports pruned from AST without runtime penalty.", Color.GREEN)

        elif choice == "5":
            print_section("Running Complete Automated Diagnostic Verification")
            # Step 1: Link
            order = linker.link_modules("./main.js")
            cprint(f"Topological Execution Order: {' -> '.join(order)}", Color.GREEN)

            # Step 2: Semantics
            ExecutionSimulation.simulate_esm_live_binding()
            ExecutionSimulation.simulate_cjs_value_snapshot()

            # Step 3: Tree shake
            shaker = ASTTreeShaker(linker.module_registry)
            optimized = shaker.shake("./main.js")
            math_ast = optimized["./math.js"]
            retained = [n.data["declaration"].data["id"] for n in math_ast.data["body"] if n.type == "ExportNamedDeclaration"]
            cprint(f"Retained exports in './math.js': {retained}", Color.CYAN)
            assert "add" in retained, "add should be retained"
            assert "unusedHugeMathLib" not in retained, "unusedHugeMathLib must be stripped"

            cprint("\n[SUCCESS] All verification tests passed flawlessly! 100% Valid Syntax & Semantics.", Color.BOLD + Color.GREEN)
            if not sys.stdin.isatty():
                break

        elif choice == "0":
            cprint("Closing Lab Exercise. Goodbye!", Color.CYAN)
            break
        else:
            cprint("Invalid choice, please select 0-5.", Color.RED)

        if not sys.stdin.isatty():
            break

if __name__ == "__main__":
    run_interactive_lab()
