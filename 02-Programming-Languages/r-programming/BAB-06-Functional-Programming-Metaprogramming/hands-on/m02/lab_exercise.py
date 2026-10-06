#!/usr/bin/env python3
"""
Lab Hands-on: R Programming Internals - Functional Programming & Metaprogramming
Bab 06 - Modul 02 Deep Dive

Simulasi Arsitektur Produksi Internal R:
1. Lexical Environment Hierarchy & First-Class Closures
2. Lazy Evaluation & Promise Objects (R PROMSXP Call-by-Need Evaluation Model)
3. AST Introspection & Expression Quoting (mirip base::quote & lobstr::ast)
4. Non-Standard Evaluation (NSE) & Data Masking (mirip rlang::eval_tidy & dplyr::filter)
5. Functional Adverbs & Higher-Order Combinators (mirip purrr::safely, purrr::compose)
"""

import sys
import ast
import time
import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ============================================================================
# ANSI TERMINAL STYLING
# ============================================================================
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Foreground Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background Colors
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[40m"

def print_banner(title: str, subtitle: str = "") -> None:
    width = 76
    print(f"\n{Style.BOLD}{Style.CYAN}╔{'═' * (width - 2)}╗{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}║ {title.center(width - 4)} ║{Style.RESET}")
    if subtitle:
        print(f"{Style.DIM}{Style.CYAN}║ {subtitle.center(width - 4)} ║{Style.RESET}")
    print(f"{Style.BOLD}{Style.CYAN}╚{'═' * (width - 2)}╝{Style.RESET}")

def print_section(section_id: str, title: str) -> None:
    print(f"\n{Style.BOLD}{Style.YELLOW}▶ [{section_id}] {title}{Style.RESET}")
    print(f"{Style.DIM}{'-' * 60}{Style.RESET}")

def print_success(msg: str) -> None:
    print(f"  {Style.GREEN}✓ [SUCCESS]{Style.RESET} {msg}")

def print_info(msg: str) -> None:
    print(f"  {Style.BLUE}ℹ [INFO]{Style.RESET} {msg}")

def print_warn(msg: str) -> None:
    print(f"  {Style.YELLOW}⚠ [WARN]{Style.RESET} {msg}")


# ============================================================================
# 1. LEXICAL ENVIRONMENT & CLOSURES (R LEXICAL SCOPE MODEL)
# ============================================================================
class Environment:
    """
    Simulasi Lexical Scope Frame di R (Pointer ke parent environment).
    Setiap evaluasi fungsi di R menciptakan execution environment baru.
    """
    def __init__(self, name: str, parent: Optional['Environment'] = None):
        self.name = name
        self.parent = parent
        self.bindings: Dict[str, Any] = {}

    def assign(self, name: str, value: Any) -> None:
        self.bindings[name] = value

    def get(self, name: str) -> Any:
        if name in self.bindings:
            return self.bindings[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise NameError(f"Simbol '{name}' tidak ditemukan di rantai lingkungan.")

    def __repr__(self) -> str:
        parent_name = self.parent.name if self.parent else "NULL (Empty Env)"
        return f"<Environment: {self.name} (parent: {parent_name}, bindings: {list(self.bindings.keys())})>"


# ============================================================================
# 2. CALL-BY-NEED & PROMISE EVALUATION (R PROMSXP INTERNAL)
# ============================================================================
class Promise:
    """
    Simulasi representasi internal C-level R: PROMSXP.
    Argumen di R dievaluasi secara malas (lazy evaluation) menggunakan Promise.
    Komponen Promise:
    - expr: AST / ekspresi yang belum dievaluasi
    - env: lexical environment saat pemanggilan fungsi
    - value: hasil cache setelah dievaluasi pertama kali (memoized)
    - evaluated: status apakah promise sudah di-force
    """
    def __init__(self, expr_str: str, thunk: Callable[[], Any], env: Environment):
        self.expr_str = expr_str
        self.thunk = thunk
        self.env = env
        self.evaluated: bool = False
        self.value: Any = None

    def force(self) -> Any:
        """Paksa evaluasi ekspresi (R C-internal: force_promise / Rf_eval)."""
        if not self.evaluated:
            print(f"    {Style.MAGENTA}[Promise FORCE]{Style.RESET} Mengevaluasi `{self.expr_str}` di {self.env.name}...")
            self.value = self.thunk()
            self.evaluated = True
        else:
            print(f"    {Style.DIM}[Promise CACHE]{Style.RESET} Mengambil nilai cached `{self.expr_str}` -> {self.value}")
        return self.value


def simulate_lazy_call(a_prom: Promise, b_prom: Promise, flag: bool) -> Any:
    """
    Simulasi pemanggilan fungsi R:
    f <- function(a, b, flag) {
      if (flag) a else b
    }
    Jika flag=True, b_prom tidak akan pernah dievaluasi (zero computation cost).
    """
    print_info(f"Memasuki eksekusi fungsi dengan flag={flag}")
    if flag:
        return a_prom.force()
    return b_prom.force()


# ============================================================================
# 3. METAPROGRAMMING & AST INTROSPECTION (LOBSTR::AST ANALOGUE)
# ============================================================================
class ASTInspector(ast.NodeVisitor):
    """
    Visitor untuk membedah Abstract Syntax Tree ekspresi R/Python.
    Menggambarkan struktur tree yang setara dengan `lobstr::ast(x + y * 2)`.
    """
    def __init__(self):
        self.depth = 0

    def print_branch(self, label: str, val: str = "") -> None:
        indent = "  " * self.depth
        val_str = f" : {Style.BOLD}{val}{Style.RESET}" if val else ""
        print(f"    {indent}{Style.CYAN}└─[{Style.RESET}{Style.GREEN}{label}{Style.RESET}{Style.CYAN}]{Style.RESET}{val_str}")

    def generic_visit(self, node: ast.AST) -> None:
        name = node.__class__.__name__
        val = ""
        if isinstance(node, ast.Name):
            val = f"Symbol({node.id})"
        elif isinstance(node, ast.Constant):
            val = f"Literal({node.value})"
        elif isinstance(node, ast.BinOp):
            val = f"Op({node.op.__class__.__name__})"
        elif isinstance(node, ast.BoolOp):
            val = f"BoolOp({node.op.__class__.__name__})"
        elif isinstance(node, ast.UnaryOp):
            val = f"UnaryOp({node.op.__class__.__name__})"
        elif isinstance(node, ast.Compare):
            ops = [op.__class__.__name__ for op in node.ops]
            val = f"Comparators({','.join(ops)})"

        self.print_branch(name, val)
        self.depth += 1
        super().generic_visit(node)
        self.depth -= 1


# ============================================================================
# 4. NON-STANDARD EVALUATION (NSE) & DATA MASKING (RLANG/TIDY EVAL)
# ============================================================================
class DataMaskContext:
    """
    Simulasi Data Masking (prinsip tidy evaluation di dplyr / rlang).
    Mengevaluasi ekspresi di mana atribut objek/kolom data frame memiliki preseden
    lebih tinggi dibanding variabel di parent environment.
    """
    def __init__(self, data_record: Dict[str, Any], parent_env: Dict[str, Any]):
        self.data_record = data_record
        self.parent_env = parent_env

    def resolve_symbol(self, symbol_name: str) -> Any:
        # Prioritas 1: Kolom data frame (Data Mask)
        if symbol_name in self.data_record:
            return self.data_record[symbol_name]
        # Prioritas 2: Parent Environment (Pronoun .env)
        if symbol_name in self.parent_env:
            return self.parent_env[symbol_name]
        raise NameError(f"Simbol '{symbol_name}' tidak ditemukan di data mask maupun parent scope.")

    def eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.eval_node(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.resolve_symbol(node.id)
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(self.eval_node(v) for v in node.values)
            if isinstance(node.op, ast.Or):
                return any(self.eval_node(v) for v in node.values)
        if isinstance(node, ast.UnaryOp):
            val = self.eval_node(node.operand)
            if isinstance(node.op, ast.Not): return not val
            if isinstance(node.op, ast.USub): return -val
            if isinstance(node.op, ast.UAdd): return +val
        if isinstance(node, ast.BinOp):
            left = self.eval_node(node.left)
            right = self.eval_node(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div): return left / right
        if isinstance(node, ast.Compare):
            left = self.eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self.eval_node(comparator)
                if isinstance(op, ast.Gt) and not (left > right): return False
                if isinstance(op, ast.Lt) and not (left < right): return False
                if isinstance(op, ast.GtE) and not (left >= right): return False
                if isinstance(op, ast.LtE) and not (left <= right): return False
                if isinstance(op, ast.Eq) and not (left == right): return False
                if isinstance(op, ast.NotEq) and not (left != right): return False
                left = right
            return True
        raise NotImplementedError(f"Evaluator belum mengimplementasikan AST tipe: {node.__class__.__name__}")


def tidy_filter(records: List[Dict[str, Any]], expr_str: str, parent_env: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Simulasi fungsi `dplyr::filter(records, expr)` menggunakan Non-Standard Evaluation."""
    parsed_ast = ast.parse(expr_str, mode="eval")
    filtered = []
    for row in records:
        ctx = DataMaskContext(row, parent_env)
        if ctx.eval_node(parsed_ast):
            filtered.append(row)
    return filtered


# ============================================================================
# 5. FUNCTIONAL OPERATORS & COMBINATORS (PURRR ANALOGUE)
# ============================================================================
@dataclass
class SafelyResult:
    result: Optional[Any]
    error: Optional[str]


def purrr_safely(fn: Callable[..., Any]) -> Callable[..., SafelyResult]:
    """
    Adverb functional mirip purrr::safely(f).
    Mengonversi fungsi yang bisa melempar error menjadi fungsi total
    yang mengembalikan list/struct berformat {result, error}.
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> SafelyResult:
        try:
            res = fn(*args, **kwargs)
            return SafelyResult(result=res, error=None)
        except Exception as e:
            return SafelyResult(result=None, error=f"{type(e).__name__}: {str(e)}")
    return wrapper


def purrr_compose(*functions: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """
    Operator komposisi fungsi kanan-ke-kiri mirip purrr::compose(f, g, h).
    f(g(h(x)))
    """
    return functools.reduce(lambda f, g: lambda x: f(g(x)), functions)


# ============================================================================
# INTERACTIVE DEMO RUNNER
# ============================================================================
def run_interactive_suite() -> None:
    print_banner(
        "R FUNCTIONAL PROGRAMMING & METAPROGRAMMING SIMULATOR",
        "Arsitektur Evaluasi R: Lazy Promises, Quosures, AST, & Functional Adverbs"
    )

    # ------------------------------------------------------------------------
    # DEMO 1: Lexical Scope
    # ------------------------------------------------------------------------
    print_section("MODUL 1", "Lexical Scoping & Environment Resolution")
    global_env = Environment("global_env")
    global_env.assign("tax_rate", 0.11)
    global_env.assign("base_currency", "IDR")

    func_env = Environment("package_core_env", parent=global_env)
    func_env.assign("local_discount", 0.05)

    print_info(f"Mencari 'tax_rate' dari {func_env.name}: {func_env.get('tax_rate')}")
    print_info(f"Mencari 'local_discount' dari {func_env.name}: {func_env.get('local_discount')}")
    print_success("Lexical chaining berhasil memetakan resolusi variabel hingga root environment.")

    # ------------------------------------------------------------------------
    # DEMO 2: Lazy Evaluation & Promise Mechanism
    # ------------------------------------------------------------------------
    print_section("MODUL 2", "Lazy Evaluation (Call-by-Need PROMSXP Simulation)")

    def expensive_computation() -> int:
        print(f"      {Style.RED}[!] Melakukan kalkulasi berat (Heavy I/O Sim)...{Style.RESET}")
        return 42 * 100

    def light_computation() -> int:
        return 10 + 5

    prom_a = Promise("light_computation()", light_computation, global_env)
    prom_b = Promise("expensive_computation()", expensive_computation, global_env)

    print_info("Skenario 1: Flag bernilai True (Hanya butuh prom_a, prom_b tidak pernah di-force):")
    res1 = simulate_lazy_call(prom_a, prom_b, flag=True)
    print_success(f"Hasil Skenario 1 = {res1} (prom_b evaluated: {prom_b.evaluated})")

    print("\n")
    print_info("Skenario 2: Flag bernilai False (prom_b harus di-force untuk pertama kali):")
    res2 = simulate_lazy_call(prom_a, prom_b, flag=False)
    print_success(f"Hasil Skenario 2 = {res2} (prom_b evaluated: {prom_b.evaluated})")

    print("\n")
    print_info("Skenario 3: Memanggil kembali prom_b (Verifikasi memoization cache di PROMSXP):")
    res3 = prom_b.force()
    print_success(f"Hasil Skenario 3 dari Cache = {res3}")

    # ------------------------------------------------------------------------
    # DEMO 3: AST Introspection (lobstr::ast)
    # ------------------------------------------------------------------------
    print_section("MODUL 3", "Metaprogramming & AST Parsing (lobstr::ast Simulation)")
    r_expr = "price * (1 + tax_rate) > threshold"
    print_info(f"Membedah Ekspresi R: {Style.BOLD}{r_expr}{Style.RESET}")
    parsed = ast.parse(r_expr, mode="eval")
    inspector = ASTInspector()
    inspector.visit(parsed)
    print_success("AST berhasil diurai menjadi pohon operator, simbol variabel, dan literal.")

    # ------------------------------------------------------------------------
    # DEMO 4: Non-Standard Evaluation & Data Masking (rlang/dplyr)
    # ------------------------------------------------------------------------
    print_section("MODUL 4", "Non-Standard Evaluation (NSE) & Data Masking")
    dataset = [
        {"id": 101, "dept": "Engineering", "salary": 18000000, "perf_score": 92},
        {"id": 102, "dept": "Marketing",   "salary": 9500000,  "perf_score": 78},
        {"id": 103, "dept": "Engineering", "salary": 25000000, "perf_score": 96},
        {"id": 104, "dept": "Sales",       "salary": 12000000, "perf_score": 88},
        {"id": 105, "dept": "Engineering", "salary": 14000000, "perf_score": 84},
    ]
    query_env = {"min_perf": 85, "dept_target": "Engineering"}
    query_str = "perf_score >= min_perf and salary > 15000000"

    print_info(f"Dataset Input : {len(dataset)} baris")
    print_info(f"Parent Scope  : {query_env}")
    print_info(f"NSE Filter    : {Style.BOLD}`{query_str}`{Style.RESET}")

    filtered_data = tidy_filter(dataset, query_str, query_env)
    print_success(f"Dataframe hasil filter ({len(filtered_data)} baris lolos kriteria):")
    for r in filtered_data:
        print(f"    - ID: {r['id']} | Dept: {r['dept']} | Gaji: Rp{r['salary']:,} | Perf: {r['perf_score']}")

    # ------------------------------------------------------------------------
    # DEMO 5: Functional Adverbs (purrr::safely & purrr::compose)
    # ------------------------------------------------------------------------
    print_section("MODUL 5", "Functional Adverbs & Pipeline Composition (purrr)")

    def parse_and_invert(val: Any) -> float:
        num = float(val)
        return 1.0 / num

    safe_inverter = purrr_safely(parse_and_invert)
    test_inputs = ["10", "4", "0", "invalid_number", "2.5"]

    print_info("Menguji purrr::safely pada berbagai input (termasuk DivisionByZero & ValueError):")
    for item in test_inputs:
        out = safe_inverter(item)
        if out.error:
            print(f"    Input: {item:<15} -> {Style.RED}Error: {out.error}{Style.RESET}")
        else:
            print(f"    Input: {item:<15} -> {Style.GREEN}Hasil: {out.result}{Style.RESET}")

    print("\n")
    print_info("Menguji purrr::compose: compose(round_2, multiply_100, add_tax)")
    add_tax = lambda x: x * 1.11
    to_percentage = lambda x: x * 100
    format_round = lambda x: round(x, 2)

    composed_pipeline = purrr_compose(format_round, to_percentage, add_tax)
    sample_val = 1.25
    pipe_res = composed_pipeline(sample_val)
    print_success(f"Input: {sample_val} -> Pipeline Result: {pipe_res}%")

    print(f"\n{Style.BOLD}{Style.GREEN}✔ SELURUH SUITE SIMULASI ARSITEKTUR R BERJALAN 100% SUKSES.{Style.RESET}\n")


if __name__ == "__main__":
    run_interactive_suite()
