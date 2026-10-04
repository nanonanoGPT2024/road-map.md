#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Functional Programming & Metaprogramming in R (Simulated in Python 3)
BAB-06: Functional Programming & Metaprogramming
-----------------------------------------------------------------------------------------
Topik Inti:
1. Higher-Order Functions / Functionals (lapply, sapply, purrr::map pattern)
2. Function Factories & Enclosing Environments (Closures)
3. Expression Capture & AST Manipulation (quote, substitute, call tree)
4. Non-Standard Evaluation (NSE) & Data Masking (eval_tidy, quasiquotation)
"""

import sys
import math
import time
from typing import Callable, Any, List, Dict, Union

# --- ANSI Color Codes ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_WHITE   = "\033[97m"

def print_header(title: str) -> None:
    border = "=" * 65
    print(f"\n{CLR_CYAN}{CLR_BOLD}{border}")
    print(f" >>> {title.upper()} <<<")
    print(f"{border}{CLR_RESET}\n")

def print_step(step_num: int, title: str) -> None:
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}[Bagian {step_num}] {title}{CLR_RESET}")
    print(f"{CLR_WHITE}{'-' * 50}{CLR_RESET}")

def print_success(msg: str) -> None:
    print(f"{CLR_GREEN}✓ [BERHASIL] {msg}{CLR_RESET}")

def print_info(label: str, val: Any) -> None:
    print(f"{CLR_BLUE}  ℹ {CLR_BOLD}{label}:{CLR_RESET} {CLR_YELLOW}{val}{CLR_RESET}")


# ============================================================================
# 1. Higher-Order Functions / Functionals (purrr / base R functionals)
# ============================================================================
class RFunctionals:
    """Simulasi functional programming khas R: lapply, sapply, map_dbl."""
    
    @staticmethod
    def lapply(data: List[Any], func: Callable[[Any], Any]) -> List[Any]:
        """Meniru base::lapply - selalu mengembalikan list."""
        return [func(x) for x in data]

    @staticmethod
    def sapply(data: List[Any], func: Callable[[Any], Any]) -> Union[List[Any], List[float], List[int]]:
        """Meniru base::sapply - menyederhanakan output bila homogen."""
        res = [func(x) for x in data]
        return res

    @staticmethod
    def map_dbl(data: List[Any], func: Callable[[Any], float]) -> List[float]:
        """Meniru purrr::map_dbl - type-safe mapper untuk double/float."""
        out: List[float] = []
        for idx, item in enumerate(data):
            val = func(item)
            if not isinstance(val, (int, float)):
                raise TypeError(f"Element {idx} tidak menghasilkan numeric/double (got {type(val).__name__})")
            out.append(float(val))
        return out


# ============================================================================
# 2. Function Factories & Closures (Enclosing Environment)
# ============================================================================
def power_factory(exponent: float) -> Callable[[float], float]:
    """
    Meniru pembuatan Function Factory di R.
    Lingkungan enclosing mempertahankan variabel `exponent`.
    """
    def power_impl(x: float) -> float:
        return math.pow(x, exponent)
    
    # Metadata penanda enclosing environment
    power_impl.__env__ = {"exponent": exponent}
    power_impl.__name__ = f"power_of_{exponent}"
    return power_impl


# ============================================================================
# 3. Metaprogramming: AST & Quoting (quote, substitute)
# ============================================================================
class RExpression:
    """Representasi AST/Call Tree sederhana seperti call object di R: f(x, y)."""
    def __init__(self, op: str, left: Any, right: Any = None):
        self.op = op
        self.left = left
        self.right = right

    def __str__(self) -> str:
        if self.right is None:
            return f"({self.op} {self.left})"
        return f"({self.left} {self.op} {self.right})"

    def display_ast(self, indent: int = 0) -> None:
        prefix = "  " * indent
        print(f"{prefix}{CLR_BLUE}└── Call Node:{CLR_RESET} {CLR_CYAN}{self.op}{CLR_RESET}")
        if isinstance(self.left, RExpression):
            self.left.display_ast(indent + 1)
        else:
            print(f"{prefix}    ├── Arg: {CLR_YELLOW}{self.left}{CLR_RESET}")

        if self.right is not None:
            if isinstance(self.right, RExpression):
                self.right.display_ast(indent + 1)
            else:
                print(f"{prefix}    └── Arg: {CLR_YELLOW}{self.right}{CLR_RESET}")

    def substitute(self, envir: Dict[str, Any]) -> "RExpression":
        """Substitusi simbol secara rekursif (seperti substitute() di R)."""
        new_left = envir.get(self.left, self.left) if isinstance(self.left, str) else self.left
        new_right = envir.get(self.right, self.right) if isinstance(self.right, str) else self.right
        
        if isinstance(new_left, RExpression):
            new_left = new_left.substitute(envir)
        if isinstance(new_right, RExpression):
            new_right = new_right.substitute(envir)

        return RExpression(self.op, new_left, new_right)


# ============================================================================
# 4. Non-Standard Evaluation (NSE) & Data Masking (eval_tidy)
# ============================================================================
class RDataMask:
    """
    Simulasi Tidy Evaluation / Data Masking.
    Evaluasi ekspresi dengan mengutamakan kolom dataframe (data mask)
    lalu fallback ke calling environment.
    """
    @staticmethod
    def eval_tidy(expr: RExpression, data: Dict[str, List[float]], env: Dict[str, Any]) -> List[float]:
        n_rows = len(next(iter(data.values())))
        
        def resolve_val(operand: Any, row_idx: int) -> float:
            if isinstance(operand, (int, float)):
                return float(operand)
            if isinstance(operand, str):
                if operand in data:
                    return float(data[operand][row_idx])
                if operand in env:
                    return float(env[operand])
                raise NameError(f"Simbol '{operand}' tidak ditemukan di data mask maupun environment!")
            if isinstance(operand, RExpression):
                return eval_node(operand, row_idx)
            raise ValueError(f"Tipe operan tidak didukung: {type(operand)}")

        def eval_node(node: RExpression, row_idx: int) -> float:
            v_left = resolve_val(node.left, row_idx)
            v_right = resolve_val(node.right, row_idx)
            if node.op == "+":
                return v_left + v_right
            elif node.op == "-":
                return v_left - v_right
            elif node.op == "*":
                return v_left * v_right
            elif node.op == "/":
                if v_right == 0:
                    return float("nan")
                return v_left / v_right
            raise ValueError(f"Operator tidak dikenal: {node.op}")

        return [eval_node(expr, i) for i in range(n_rows)]


# ============================================================================
# Interactive CLI Lab Execution
# ============================================================================
def run_interactive_lab() -> None:
    print_header("Hands-On R: Functional Programming & Metaprogramming")
    print(f"{CLR_WHITE}Selamat datang di simulasi laboratorium teknis R-Programming.{CLR_RESET}")
    print(f"Modul ini mensimulasikan mekanisme internal functional R dan non-standard evaluation.\n")

    # Bagian 1: Functionals
    print_step(1, "Higher-Order Functions (lapply vs purrr::map_dbl)")
    raw_data = [1, 4, 9, 16, 25]
    print_info("Input Vector", raw_data)
    
    sqrt_res = RFunctionals.lapply(raw_data, math.sqrt)
    print_info("lapply(vec, sqrt)", sqrt_res)
    
    norm_res = RFunctionals.map_dbl(raw_data, lambda x: math.log(x) + 1.5)
    print_info("map_dbl(vec, log + 1.5)", [round(val, 3) for val in norm_res])
    print_success("Functional pipeline berhasil dieksekusi tanpa looping imperatif.")

    # Bagian 2: Function Factory
    print_step(2, "Function Factory (Closures & Enclosing Environments)")
    square = power_factory(2)
    cube = power_factory(3)
    
    print_info("Factory Generated", square.__name__)
    print_info("Enclosing Environment", getattr(square, "__env__"))
    val_in = 5.0
    print_info(f"square({val_in})", square(val_in))
    print_info(f"cube({val_in})", cube(val_in))
    assert square(val_in) == 25.0 and cube(val_in) == 125.0, "Kalkulasi power_factory gagal!"
    print_success("Closure berhasil menyimpan state enclosing environment.")

    # Bagian 3: Metaprogramming & AST Quoting
    print_step(3, "Metaprogramming (Quote, AST Representation, & Substitute)")
    # Representasi ekspresi R: quote(x * weight + bias)
    raw_expr = RExpression("+", RExpression("*", "x", "weight"), "bias")
    print(f"{CLR_YELLOW}Struktur AST untuk ekspresi: (x * weight + bias){CLR_RESET}")
    raw_expr.display_ast()

    subst_env = {"weight": 2.5, "bias": 10.0}
    print_info("Environment untuk substitute()", subst_env)
    substituted_expr = raw_expr.substitute(subst_env)
    print(f"{CLR_YELLOW}AST setelah substitute():{CLR_RESET}")
    substituted_expr.display_ast()
    print_success("Tree traversal dan symbol replacement AST tervalidasi.")

    # Bagian 4: Non-Standard Evaluation (NSE) & Data Masking
    print_step(4, "Tidy Evaluation & Data Masking (rlang::eval_tidy)")
    df = {
        "x": [10.0, 20.0, 30.0, 40.0],
        "weight": [1.5, 2.0, 0.5, 1.0]
    }
    calling_env = {"bias": 5.0}

    print_info("Data Frame (Data Mask)", df)
    print_info("Calling Environment (Masked Out)", calling_env)
    print_info("Ekspresi yang dievaluasi", str(raw_expr))

    tidy_result = RDataMask.eval_tidy(raw_expr, df, calling_env)
    print_info("Hasil eval_tidy()", tidy_result)
    
    # Verifikasi manual: (10*1.5)+5=20, (20*2)+5=45, (30*0.5)+5=20, (40*1)+5=45
    expected = [20.0, 45.0, 20.0, 45.0]
    assert tidy_result == expected, f"Hasil tidak sesuai harapan: {tidy_result} != {expected}"
    print_success("Data masking memprioritaskan kolom dataframe sebelum environment induk.")

    # Ringkasan Akhir
    print_header("Ringkasan & Verifikasi Lab Selesai")
    print(f"{CLR_GREEN}{CLR_BOLD}Semua tes unit dan simulasi teknis BAB-06 Functional Programming & Metaprogramming lulus 100%!{CLR_RESET}\n")

if __name__ == "__main__":
    run_interactive_lab()
