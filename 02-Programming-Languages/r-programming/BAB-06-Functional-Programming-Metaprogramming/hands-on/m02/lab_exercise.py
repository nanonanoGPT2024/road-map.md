#!/usr/bin/env python3
"""
Lab Hands-on: R Programming Internals - Functional Programming & Metaprogramming
Bab 06 - Modul 02 Deep Dive

Simulasi arsitektur internal R:
1. Lazy Evaluation & Promise Objects (R argument evaluation model)
2. Non-Standard Evaluation (NSE), Metaprogramming & Data Masking (mirip rlang/tidy_eval)
3. AST Introspection (mirip lobstr::ast)
4. Functional Operators / Adverbs (mirip purrr::safely, purrr::compose)
"""

import sys
import ast
import time
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field

# --- Terminal Styling ANSI ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"

def print_header(title: str) -> None:
    print(f"\n{Style.BOLD}{Style.CYAN}{'='*70}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}[LAB] {title.upper()}{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}{'='*70}{Style.RESET}")

def print_substep(step: str, desc: str) -> None:
    print(f"\n{Style.BOLD}{Style.YELLOW}>>> {step}:{Style.RESET} {Style.DIM}{desc}{Style.RESET}")


# ============================================================================
# 1. SIMULASI PROMISE & LAZY EVALUATION (R RUNTIME MODEL)
# ============================================================================

class Environment:
    """Representasi Lexical Environment di R (frame penyimpan variabel dan pointer parent)."""
    def __init__(self, parent: Optional['Environment'] = None, bindings: Optional[Dict[str, Any]] = None):
        self.parent = parent
        self.bindings: Dict[str, Any] = bindings or {}

    def get(self, name: str) -> Any:
        if name in self.bindings:
            return self.bindings[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Objek '{name}' tidak ditemukan di lexical scope.")

    def set(self, name: str, val: Any) -> None:
        self.bindings[name] = val


class Promise:
    """
    Simulasi struktur internal R 'PROMSXP'.
    Argumen fungsi di R tidak langsung dievaluasi saat pemanggilan (Call by Need).
    Promise membawa unevaluated code (thunk), environment lexical, dan slot caching value.
    """
    def __init__(self, expr_thunk: Callable[[], Any], env: Environment, expr_raw: str):
        self.expr_thunk = expr_thunk
        self.env = env
        self.expr_raw = expr_raw
        self.evaluated: bool = False
        self.value: Any = None

    def force(self) -> Any:
        """Memaksa evaluasi promise (R internal: Rf_eval / force_promise)."""
        if not self.evaluated:
            print(f"  {Style.MAGENTA}[Promise]{Style.RESET} Memaksa evaluasi ekspresi: `{self.expr_raw}`")
            self.value = self.expr_thunk()
            self.evaluated = True
        else:
            print(f"  {Style.MAGENTA}[Promise]{Style.RESET} Mengambil nilai dari cache: `{self.expr_raw}` -> {self.value}")
        return self.value


def lazy_function(a: Promise, b: Promise, use_b: bool) -> Any:
    """
    Fungsi R simulasi: jika use_b=False, b tidak akan pernah di-force.
    """
    val_a = a.force()
    if use_b:
        val_b = b.force()
        return val_a + val_b
    return val_a


# ============================================================================
# 2. METAPROGRAMMING, AST INTROSPECTION & NON-STANDARD EVALUATION (NSE)
# ============================================================================

class ASTPrinter(ast.NodeVisitor):
    """Visualisasi pohon sintaksis abstrak (mirip paket R 'lobstr::ast')."""
    def __init__(self):
        self.indent = 0

    def print_node(self, node: ast.AST, label: str):
        pad = "  " * self.indent
        print(f"{pad}{Style.BLUE}o-{Style.RESET} {Style.GREEN}{label}{Style.RESET}")

    def generic_visit(self, node: ast.AST):
        label = node.__class__.__name__
        if isinstance(node, ast.Name):
            label += f" (Symbol: '{node.id}')"
        elif isinstance(node, ast.Constant):
            label += f" (Literal: {repr(node.value)})"
        elif isinstance(node, ast.Compare):
            label += f" (Comparison: {[op.__class__.__name__ for op in node.ops]})"
        elif isinstance(node, ast.BinOp):
            label += f" (Operator: {node.op.__class__.__name__})"

        self.print_node(node, label)
        self.indent += 1
        super().generic_visit(node)
        self.indent -= 1


class DataMaskEvaluator:
    """
    Mengimplementasikan tidy evaluation / Non-Standard Evaluation (NSE).
    Mengevaluasi ekspresi AST di mana 'kolom dataframe' bertindak sebagai prioritas
    utama (data mask), dengan fallback ke environment global jika simbol tidak ditemukan.
    """
    def __init__(self, data_row: Dict[str, Any], parent_env: Dict[str, Any]):
        self.data_row = data_row
        self.parent_env = parent_env

    def eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.eval_node(node.body)

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            # Prioritas 1: Data Mask (Kolom Dataset)
            if node.id in self.data_row:
                return self.data_row[node.id]
            # Prioritas 2: Parent Environment
            if node.id in self.parent_env:
                return self.parent_env[node.id]
            raise NameError(f"Simbol '{node.id}' gagal di-resolve di data mask maupun parent scope.")

        if isinstance(node, ast.Compare):
            left = self.eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.eval_node(comparator)
                if isinstance(op, ast.Gt) and not (left > right): return False
                if isinstance(op, ast.Lt) and not (left < right): return False
                if isinstance(op, ast.GtE