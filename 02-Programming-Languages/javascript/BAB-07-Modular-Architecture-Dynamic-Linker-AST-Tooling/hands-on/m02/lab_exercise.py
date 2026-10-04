#!/usr/bin/env python3
"""
Lab Hands-on: JavaScript Engine Internals - Modular Architecture, Dynamic Linker & AST Tooling
Category: 02-Programming-Languages / Chapter 07 - Module 02 Deep Dive

Simulates the ECMAScript Module (ESM) lifecycle:
1. Lexical Analysis & Abstract Syntax Tree (AST) Construction.
2. Dynamic Linking, Module Record Graph construction & Cycle Detection.
3. ESM Live-Binding Memory Model Simulation (mutable export slots).
4. AST Transformation & Static Tree-Shaking Optimizer.
"""

from __future__ import annotations
import re
import sys
from enum import Enum, auto
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field

# ============================================================================
# ANSI Formatting Helpers
# ============================================================================
class Console:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    DIM = "\033[2m"

    @classmethod
    def info(cls, title: str, msg: str):
        print(f"{cls.CYAN}[INFO]{cls.RESET} {cls.BOLD}{title}:{cls.RESET} {msg}")

    @classmethod
    def step(cls, phase: str, desc: str):
        print(f"\n{cls.MAGENTA}=== [{phase.upper()}] {desc} ==={cls.RESET}")

    @classmethod
    def success(cls, msg: str):
        print(f"{cls.GREEN}[SUCCESS]{cls.RESET} {msg}")

    @classmethod
    def warn(cls, msg: str):
        print(f"{cls.YELLOW}[WARN]{cls.RESET} {msg}")

    @classmethod
    def dump_json(cls, data: Any):
        import json
        print(f"{cls.DIM}{json.dumps(data, indent=2)}{cls.RESET}")


# ============================================================================
# Phase 1: AST Tooling & Lexical Extraction
# ============================================================================
class ASTNodeType(Enum):
    PROGRAM = auto()
    IMPORT_DECL = auto()
    EXPORT_DECL = auto()
    VAR_DECL = auto()
    FUNC_DECL = auto()
    EXPR_STMT = auto()


@dataclass
class ASTNode:
    type: ASTNodeType
    data: Dict[str, Any] = field(default_factory=dict)
    children: List[ASTNode] = field(default_factory=list)


class JSEngineParser:
    """Simulates a micro-parser extracting ESM syntax and declarations into an AST."""

    IMPORT_REGEX = re.compile(r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"];?")
    EXPORT_VAR_REGEX = re.compile(r"export\s+const\s+(\w+)\s*=\s*(.+?);?")
    EXPORT_FUNC_REGEX = re.compile(r"export\s+function\s+(\w+)\s*\((.*?)\)\s*\{([^}]*)\}")
    LOCAL_VAR_REGEX = re.compile(r"const\s+(\w+)\s*=\s*(.+?);?")

    @staticmethod
    def parse(source: str, specifier: str) -> ASTNode:
        root = ASTNode(type=ASTNodeType.PROGRAM, data={"specifier": specifier})
        lines = [line.strip() for line in source.splitlines() if line.strip() and not line.strip().startswith("//")]

        for line in lines:
            # 1. Match imports: import { a, b } from './mod.js'
            imp_match = JSEngineParser.IMPORT_REGEX.match(line)
            if imp_match:
                specifiers = [s.strip() for s in imp_match.group(1).split(",")]
                source_path = imp_match.group(2)
                root.children.append(ASTNode(
                    type=ASTNodeType.IMPORT_DECL,
                    data={"imported_symbols": specifiers, "source": source_path}
                ))
                continue

            # 2. Match export const: export const x = 42
            exp_var_match = JSEngineParser.EXPORT_VAR_REGEX.match(line)
            if exp_var_match:
                name, val = exp_var_match.group(1), exp_var_match.group(2)
                root.children.append(ASTNode(
                    type=ASTNodeType.EXPORT_DECL,
                    data={"name": name, "kind": "const", "value": val}
                ))
                continue

            # 3. Match export function: export function foo(x) { ... }
            exp_fn_match = JSEngineParser.EXPORT_FUNC_REGEX.match(line)
            if exp_fn_match:
                name, params, body = exp_fn_match.group(1), exp_fn_match.group(2), exp_fn_match.group(3)
                root.children.append(ASTNode(
                    type=ASTNodeType.FUNC_DECL,
                    data={"name": name, "params": [p.strip() for p in params.split(",") if p.strip()], "body": body, "exported": True}
                ))
                continue

            # 4. Standard declarations
            loc_var_match = JSEngineParser.LOCAL_VAR_REGEX.match(line)
            if loc_var_match:
                name, val = loc_var_match.group(1), loc_var_match.group(2)
                root.children.append(ASTNode(
                    type=ASTNodeType.VAR_DECL,
                    data={"name": name, "value": val, "exported": False}
                ))
                continue

            # Fallback statement
            root.children.append(ASTNode(type=ASTNodeType.EXPR_STMT, data={"raw": line}))

        return root


# ============================================================================
# Phase 2: Live-Binding Slots (ESM Memory Model)
# ============================================================================
class BindingSlot:
    """Models V8/SpiderMonkey indirect export pointers for dynamic live-bindings."""
    def __init__(self, value: Any):
        self._value = value

    def get(self) -> Any:
        return self._value

    def set(self, new_val: Any):
        self._value = new_val

    def __repr__(self):
        return f"BindingSlot({repr(self._value)})"


# ============================================================================
# Phase 3: Dynamic Linker & Module Record
# ============================================================================
class ModuleStatus(Enum):
    UNLINKED = auto()
    LINKING = auto()
    LINKED = auto()
    EVALUATING = auto()
    EVALUATED = auto()


class ModuleRecord:
    """Models an ECMAScript Source Text Module Record."""

    def __init__(self, specifier: str, source_code: str):
        self.specifier = specifier
        self.source_code = source_code
        self.ast: ASTNode = JSEngineParser.parse(source_code, specifier)
        self.status: ModuleStatus = ModuleStatus.UNLINKED
        self.dependencies: List[str] = []
        self.exported_slots: Dict[str, BindingSlot] = {}
        self.imported_bindings: Dict[str, Tuple[str, str]] = {}  # local_alias -> (source_mod, export_name)
        self.environment: Dict[str, Any] = {}

        self._extract_dependencies()

    def _extract_dependencies(self):
        for child in self.ast.children:
            if child.type == ASTNodeType.IMPORT_DECL:
                dep_source = child.data["source"]
                if dep_source not in self.dependencies:
                    self.dependencies.append(dep_source)
                for sym in child.data["imported_symbols"]:
                    self.imported_bindings[sym] = (dep_source, sym)
            elif child.type in (ASTNodeType.EXPORT_DECL, ASTNodeType.FUNC_DECL) and child.data.get("exported", True):
                name = child.data["name"]
                # Pre-allocate export slots with uninitialized pointer
                self.exported_slots[name] = BindingSlot(None)


class DynamicLinker:
    """Handles dependency graphs, cycle detection, linking phase, and evaluation phase."""

    def __init__(self):
        self.module_registry: Dict[str, ModuleRecord] = {}

    def register_module(self, specifier: str, source_code: str) -> ModuleRecord:
        mod = ModuleRecord(specifier, source_code)
        self.module_registry[specifier] = mod
        return mod

    def detect_cycles(self) -> List[List[str]]:
        """Tarjan/DFS cycle detection in dependency graph."""
        visited: Set[str] = set()
        recursion_stack: List[str] = []
        cycles: List[List[str]] = []

        def dfs(node: str):
            visited.add(node)
            recursion_stack.append(node)

            mod = self.module_registry.get(node)
            if mod:
                for neighbor in mod.dependencies:
                    if neighbor not in visited:
                        dfs(neighbor)
                    elif neighbor in recursion_stack:
                        cycle_start = recursion_stack.index(neighbor)
                        cycles.append(recursion_stack[cycle_start:] + [neighbor])

            recursion_stack.pop()

        for specifier in self.module_registry:
            if specifier not in visited:
                dfs(specifier)

        return cycles

    def link(self, root_specifier: str):
        """ESM Link Phase: Resolves module bindings and wires indirect pointers."""
        root = self.module_registry[root_specifier]
        if root.status in (ModuleStatus.LINKING, ModuleStatus.LINKED):
            return

        root.status = ModuleStatus.LINKING

        for dep_spec in root.dependencies:
            if dep_spec not in self.module_registry:
                raise ImportError(f"Cannot resolve module '{dep_spec}' from '{root_specifier}'")
            self.link(dep_spec)

        # Wire imports to targets' dynamic export slots
        for local_sym, (dep_spec, exp_name) in root.imported_bindings.items():
            dep_module = self.module_registry[dep_spec]
            if exp_name not in dep_module.exported_slots:
                raise AttributeError(f"Module '{dep_spec}' does not export '{exp_name}' (imported by '{root_specifier}')")

        root.status = ModuleStatus.LINKED

    def evaluate(self, root_specifier: str):
        """ESM Evaluation Phase: Executes module bodies and populates live export slots."""
        root = self.module_registry[root_specifier]
        if root.status == ModuleStatus.EVALUATED:
            return
        if root.status == ModuleStatus.EVALUATING:
            # ESM allows circular execution; evaluation continues with existing slots
            return

        root.status = ModuleStatus.EVALUATING

        # Post-order evaluation (dependencies evaluate first)
        for dep_spec in root.dependencies:
            self.evaluate(dep_spec)

        # Populate internal module environment & write into export slots
        for child in root.ast.children:
            if child.type == ASTNodeType.EXPORT_DECL:
                name = child.data["name"]
                val = eval(child.data["value"], {}, root.environment)
                root.environment[name] = val
                root.exported_slots[name].set(val)

            elif child.type == ASTNodeType.FUNC_DECL:
                name = child.data["name"]
                body_code = child.data["body"]
                # Create callable abstraction
                fn = lambda *args, b=body_code: f"executed({b.strip()})"
                root.environment[name] = fn
                if child.data.get("exported"):
                    root.exported_slots[name].set(fn)

            elif child.type == ASTNodeType.VAR_DECL:
                name = child.data["name"]
                val = eval(child.data["value"], {}, root.environment)
                root.environment[name] = val

        root.status = ModuleStatus.EVALUATED


# ============================================================================
# Phase 4: AST Transformation & Tree-Shaking Tooling
# ============================================================================
class ASTOptimizer:
    """Performs static dead-code elimination (Tree-Shaking) on the linked graph."""

    @staticmethod
    def eliminate_dead_exports(registry: Dict[str, ModuleRecord], entry_point: str) -> Dict[str, List[str]]:
        # 1. Collect all reachable imported symbols
        used_symbols: Dict[str, Set[str]] = {k: set() for k in registry}

        for specifier, mod in registry.items():
            for local_sym, (dep_spec, exp_name) in mod.imported_bindings.items():
                if dep_spec in used_symbols:
                    used_symbols[dep_spec].add(exp_name)

        # 2. Entry point exports are marked as explicitly used
        entry_mod = registry[entry_point]
        for exp in entry_mod.exported_slots:
            used_symbols[entry_point].add(exp)

        # 3. Identify and prune unused AST nodes
        pruned_nodes: Dict[str, List[str]] = {k: [] for k in registry}
        for specifier, mod in registry.items():
            new_children = []
            for child in mod.ast.children:
                if child.type in (ASTNodeType.EXPORT_DECL, ASTNodeType.FUNC_DECL) and child.data.get("exported", True):
                    symbol_name = child.data["name"]
                    if symbol_name not in used_symbols[specifier]:
                        pruned_nodes[specifier].append(symbol_name)
                        continue  # Drop unused AST node
                new_children.append(child)
            mod.ast.children = new_children

        return pruned_nodes


# ============================================================================
# Lab Execution & Verification
# ============================================================================
def main():
    Console.step("Setup", "Initializing Virtual Modules (Including Circular Reference)")

    files = {
        "./math.js": """
            export const counter = 100;
            export const pi = 3.14159;
            export function unusedMathHelper() { return 'dead_code'; }
            export function add(a, b) { return a + b; }
        """,
        "./state_a.js": """
            import { stateB } from './state_b.js';
            export const stateA = 'ALPHA';
            export function getCombined() { return stateA + '_' + stateB; }
        """,
        "./state_b.js": """
            import { stateA } from './state_a.js';
            export const stateB = 'BETA';
        """,
        "./main.js": """
            import { counter, pi } from './math.js';
            import { stateA } from './state_a.js';
            const localMultiplier = 2;
            export const result = counter * localMultiplier;
        """
    }

    linker = DynamicLinker()
    for specifier, code in files.items():
        linker.register_module(specifier, code)
        Console.info("Parsed AST", f"{specifier} -> {len(linker.module_registry[specifier].ast.children)} statements")

    Console.step("Linker", "Static Dependency Analysis & Cycle Detection")
    cycles = linker.detect_cycles()
    if cycles:
        for c in cycles:
            Console.warn(f"Detected Circular Module Dependency: {' -> '.join(c)}")
    else:
        Console.info("Cycles", "No circular dependencies detected.")

    Console.step("Linker", "Executing ESM Linking Phase on Entry: './main.js'")
    linker.link("./main.js")
    for spec, mod in linker.module_registry.items():
        Console.info("Module Linked", f"{spec} | State: {mod.status.name} | Bindings: {list(mod.imported_bindings.keys())}")

    Console.step("Runtime", "Evaluating Modules & Demonstrating Live Bindings")
    linker.evaluate("./main.js")

    math_mod = linker.module_registry["./math.js"]
    main_mod = linker.module_registry["./main.js"]

    initial_counter = math_mod.exported_slots["counter"].get()
    evaluated_result = main_mod.exported_slots["result"].get()

    Console.info("Slot Value", f"math.js:counter = {initial_counter}")
    Console.info("Evaluated", f"main.js:result = {evaluated_result}")

    # ESM Dynamic Live-Binding Verification: Mutate slot directly
    Console.info("Mutation", "Mutating dynamic memory slot 'counter' in './math.js' -> 250")
    math_mod.exported_slots["counter"].set(250)

    # Re-evaluate variable utilizing mutated imported reference
    updated_result = math_mod.exported_slots["counter"].get() * main_mod.environment["localMultiplier"]
    Console.success(f"Live Binding Reflected: counter is now {math_mod.exported_slots['counter'].get()}, calculated {updated_result}")

    Console.step("Optimization", "AST Tree-Shaking Pass (Dead Export Elimination)")
    pruned = ASTOptimizer.eliminate_dead_exports(linker.module_registry, "./main.js")
    for spec, removed in pruned.items():
        if removed:
            Console.warn(f"Tree-shaker purged unreachable exports in {spec}: {removed}")
        else:
            Console.info("Tree-shaker", f"{spec}: No unused exports eliminated.")

    # Validate AST compaction
    remaining_math_exports = [
        c.data["name"] for c in linker.module_registry["./math.js"].ast.children
        if c.type in (ASTNodeType.EXPORT_DECL, ASTNodeType.FUNC_DECL)
    ]
    Console.success(f"Final Optimized AST Exports for './math.js': {remaining_math_exports}")
    assert "unusedMathHelper" not in remaining_math_exports, "Tree shaker failed to purge dead export!"
    Console.success("Verification complete. All module stages cleanly executed.")


if __name__ == "__main__":
    main()