#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Paradigma Pemrograman Fungsional & Kontrol Eksekusi R
Modul: BAB-03-Pemrograman-Fungsional-Kontrol-Eksekusi

Simulasi teknis konsep internal R:
1. First-Class Functions, Lexical Scoping & Closures (Environment Enclosure)
2. Lazy Evaluation & Promises (R Expression Delay & Forcing)
3. R Apply Family Simulation (lapply, sapply, vapply dengan Strict Type Invariant)
4. Vectorized Execution vs Scalar Control Flow (ifelse vs if/else)
5. Functional Pipe & Error Monad (Purrr safely / pipe |>)
"""

import sys
import time
from typing import Any, Callable, Dict, List, Tuple, Type, Union

# ANSI Colors for Terminal Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== [R-FP SIMULATOR] {title} ==={CLR_RESET}")


def badge(label: str, text: str, color: str = CLR_GREEN) -> None:
    print(f"  {color}[{label}]{CLR_RESET} {text}")


# ------------------------------------------------------------------------------
# 1. SIMULASI R PROMISE & LAZY EVALUATION
# ------------------------------------------------------------------------------
class RPromise:
    """
    Simulasi R Promise Object.
    Di R, argumen fungsi tidak dievaluasi saat pemanggilan, melainkan
    dibungkus dalam promise yang berisi: (expr, env, value).
    Evaluasi hanya terjadi saat nilai di-'force'.
    """

    def __init__(self, expr_func: Callable[[], Any], name: str = "arg"):
        self.expr_func = expr_func
        self.name = name
        self.evaluated = False
        self.value = None

    def force(self) -> Any:
        if not self.evaluated:
            badge("LAZY-EVAL", f"Forcing promise arg '{self.name}'...", CLR_YELLOW)
            self.value = self.expr_func()
            self.evaluated = True
        else:
            badge("CACHE-HIT", f"Promise arg '{self.name}' sudah terevaluasi.", CLR_MAGENTA)
        return self.value


def simulate_lazy_evaluation() -> None:
    header("1. R Lazy Evaluation & Promises")

    def heavy_computation() -> int:
        print(f"      {CLR_RED}>> [Computation] Menjalankan kalkulasi matriks berat (simulasi)...{CLR_RESET}")
        time.sleep(0.3)
        return 42

    def r_function_demo(a_val: int, b_promise: RPromise, condition: bool) -> int:
        print(f"  Executing function with condition={condition}...")
        if condition:
            # b_promise tidak pernah dipanggil/diforce jika condition True
            return a_val * 2
        return a_val + b_promise.force()

    p = RPromise(heavy_computation, name="matrix_result")
    badge("BRANCH-1", "Memanggil fungsi dengan condition=True (Promise TIDAK dievaluasi):", CLR_BLUE)
    res1 = r_function_demo(10, p, condition=True)
    print(f"    Hasil Branch 1: {CLR_BOLD}{res1}{CLR_RESET} (evaluated={p.evaluated})")

    badge("BRANCH-2", "Memanggil fungsi dengan condition=False (Promise DIPAKSA dievaluasi):", CLR_BLUE)
    res2 = r_function_demo(10, p, condition=False)
    print(f"    Hasil Branch 2: {CLR_BOLD}{res2}{CLR_RESET} (evaluated={p.evaluated})")


# ------------------------------------------------------------------------------
# 2. SIMULASI R ENVIRONMENT & CLOSURES (LEXICAL SCOPING)
# ------------------------------------------------------------------------------
class REnvironment:
    """Simulasi rantai lexical environment di R (parent/enclosing env)."""

    def __init__(self, parent: Union["REnvironment", None] = None, name: str = "env"):
        self.bindings: Dict[str, Any] = {}
        self.parent = parent
        self.name = name

    def assign(self, var: str, val: Any) -> None:
        self.bindings[var] = val

    def get(self, var: str) -> Any:
        if var in self.bindings:
            return self.bindings[var]
        if self.parent is not None:
            return self.parent.get(var)
        raise NameError(f"Object '{var}' not found in environment chain.")


def make_power_generator(exponent: float) -> Callable[[float], float]:
    """Mengembalikan closure dengan enclosing lexical environment."""
    env = REnvironment(name=f"closure_env(exp={exponent})")
    env.assign("exponent", exponent)

    def power_fn(x: float) -> float:
        stored_exp = env.get("exponent")
        return x ** stored_exp

    return power_fn


def simulate_closures() -> None:
    header("2. Lexical Scoping & Function Factories (Closures)")
    square = make_power_generator(2.0)
    cube = make_power_generator(3.0)

    val = 4.0
    print(f"  Nilai input: {CLR_BOLD}{val}{CLR_RESET}")
    print(f"  square({val}) -> {CLR_GREEN}{square(val)}{CLR_RESET} (Enclosed exp=2)")
    print(f"  cube({val})   -> {CLR_GREEN}{cube(val)}{CLR_RESET} (Enclosed exp=3)")


# ------------------------------------------------------------------------------
# 3. SIMULASI THE APPLY FAMILY (lapply, sapply, vapply)
# ------------------------------------------------------------------------------
def r_lapply(x: List[Any], fun: Callable[[Any], Any]) -> List[Any]:
    """lapply selalu mengembalikan list (di Python: list)."""
    return [fun(item) for item in x]


def r_sapply(x: List[Any], fun: Callable[[Any], Any]) -> Union[List[Any], Any]:
    """sapply menyederhanakan hasil jika memungkinkan (vector/array simplification)."""
    res = [fun(item) for item in x]
    # Jika semua elemen skalar bertipe sama, simplified
    types = {type(elem) for elem in res}
    if len(types) == 1 and list(types)[0] in (int, float, str, bool):
        return tuple(res)
    return res


def r_vapply(x: List[Any], fun: Callable[[Any], Any], fun_value_type: Type) -> Tuple[Any, ...]:
    """
    vapply mewajibkan type invariant FUN.VALUE untuk safety.
    Akan melempar TypeError jika ada return value yang tidak sesuai type template.
    """
    results: List[Any] = []
    for idx, item in enumerate(x):
        val = fun(item)
        if not isinstance(val, fun_value_type):
            raise TypeError(
                f"[vapply error] Nilai indeks {idx} bertipe '{type(val).__name__}', "
                f"ekspektasi '{fun_value_type.__name__}'."
            )
        results.append(val)
    return tuple(results)


def simulate_apply_family() -> None:
    header("3. The Apply Family: lapply, sapply, vapply")
    data = [1, 4, 9, 16, 25]
    print(f"  Dataset: {CLR_BOLD}{data}{CLR_RESET}")

    # lapply
    res_l = r_lapply(data, lambda x: x ** 0.5)
    badge("lapply", f"Return: {res_l} (tipe: list)", CLR_CYAN)

    # sapply
    res_s = r_sapply(data, lambda x: f"root_{int(x**0.5)}")
    badge("sapply", f"Return: {res_s} (tipe: simplified tuple/vector)", CLR_GREEN)

    # vapply (Strict Type Safety)
    badge("vapply", "Menjalankan vapply dengan FUN.VALUE = float...", CLR_BLUE)
    try:
        res_v = r_vapply(data, lambda x: float(x ** 0.5), float)
        print(f"    vapply sukses: {CLR_BOLD}{res_v}{CLR_RESET}")
    except TypeError as e:
        print(f"    {CLR_RED}{e}{CLR_RESET}")

    badge("vapply-GUARD", "Uji coba invariant failure pada vapply (memicu type mismatch):", CLR_YELLOW)
    try:
        # Sengaja mengembalikan tipe campuran untuk memicu safety guard
        r_vapply([1, 2, "error_item"], lambda x: float(x) if isinstance(x, (int, float)) else str(x), float)
    except TypeError as err:
        print(f"    {CLR_RED}Expected Catch:{CLR_RESET} {err}")


# ------------------------------------------------------------------------------
# 4. VECTORIZED EXECUTION (ifelse vs scalar if/else)
# ------------------------------------------------------------------------------
def r_ifelse(condition_vec: List[bool], yes_vec: List[Any], no_vec: List[Any]) -> List[Any]:
    """
    Simulasi fungsi ifelse(test, yes, no) R.
    Mengevaluasi kondisi secara elemen-demi-elemen dengan recycling rule sederhana.
    """
    n = len(condition_vec)
    result = []
    for i in range(n):
        cond = condition_vec[i]
        val_yes = yes_vec[i % len(yes_vec)]
        val_no = no_vec[i % len(no_vec)]
        result.append(val_yes if cond else val_no)
    return result


def simulate_vectorized_control() -> None:
    header("4. Vectorized Control: ifelse() vs Scalar if-else")
    numbers = [-10, 15, -3, 0, 42, -8]
    cond = [x > 0 for x in numbers]
    labels_pos = ["Positif"]
    labels_nonpos = ["Negatif/Nol"]

    badge("VECTOR", f"Input data: {numbers}", CLR_CYAN)
    badge("COND", f"Vector logic condition: {cond}", CLR_BLUE)

    vect_res = r_ifelse(cond, labels_pos, labels_nonpos)
    print(f"  {CLR_BOLD}Hasil ifelse() vektorisasi:{CLR_RESET}")
    for num, label in zip(numbers, vect_res):
        color = CLR_GREEN if label == "Positif" else CLR_RED
        print(f"    {num:4d} -> {color}{label}{CLR_RESET}")


# ------------------------------------------------------------------------------
# 5. PIPELINE & FUNCTIONAL MONAD (R |> dan Purrr safely)
# ------------------------------------------------------------------------------
class SafelyResult:
    def __init__(self, result: Any = None, error: Union[Exception, None] = None):
        self.result = result
        self.error = error

    def __repr__(self) -> str:
        if self.error:
            return f"SafelyResult(error='{self.error}')"
        return f"SafelyResult(result={self.result})"


def safely(fn: Callable[[Any], Any]) -> Callable[[Any], SafelyResult]:
    """Decorator simulasi purrr::safely di R untuk functional exception safety."""
    def wrapper(x: Any) -> SafelyResult:
        try:
            return SafelyResult(result=fn(x), error=None)
        except Exception as e:
            return SafelyResult(result=None, error=e)
    return wrapper


def simulate_pipeline_safely() -> None:
    header("5. Functional Pipelines (|>) & purrr::safely Monad")

    # Pipeline operasi: filter -> transform -> aggregate
    raw_data = ["10", "20", "invalid_num", "40", "zero_div"]
    badge("INPUT", f"Raw Stream: {raw_data}", CLR_MAGENTA)

    @safely
    def parse_and_reciprocal(item: str) -> float:
        num = float(item)
        if num == 0:
            raise ZeroDivisionError("Nilai nol!")
        return 100.0 / num

    results = [parse_and_reciprocal(item) for item in raw_data]

    print(f"\n  {CLR_BOLD}Evaluasi Elemen Melalui Safely Wrapper:{CLR_RESET}")
    valid_values: List[float] = []
    for item, res in zip(raw_data, results):
        if res.error is None:
            print(f"    Item '{item:12s}' -> {CLR_GREEN}SUCCESS{CLR_RESET}: {res.result:.2f}")
            valid_values.append(res.result)
        else:
            print(f"    Item '{item:12s}' -> {CLR_RED}CAPTURED ERROR{CLR_RESET}: {type(res.error).__name__}")

    mean_val = sum(valid_values) / len(valid_values) if valid_values else 0
    badge("REDUCE", f"Rata-rata elemen valid (|> pipeline): {mean_val:.3f}", CLR_CYAN)


# ------------------------------------------------------------------------------
# INTERACTIVE CLI DISPATCHER
# ------------------------------------------------------------------------------
def run_all_simulations() -> None:
    simulate_lazy_evaluation()
    simulate_closures()
    simulate_apply_family()
    simulate_vectorized_control()
    simulate_pipeline_safely()


def interactive_menu() -> None:
    menu = f"""
{CLR_BOLD}{CLR_MAGENTA}====================================================
  R FUNCTIONAL PROGRAMMING & CONTROL FLOW SIMULATOR
===================================================={CLR_RESET}
1. Simulasi R Promises & Lazy Evaluation
2. Simulasi Lexical Scoping, Environment & Closures
3. Simulasi Apply Family (lapply, sapply, vapply)
4. Simulasi Vectorized Flow: ifelse()
5. Simulasi purrr::safely & Pipeline Monad
6. Jalankan Semua Modul Simulasi
0. Keluar
"""
    while True:
        print(menu)
        try:
            choice = input(f"{CLR_BOLD}Pilih nomor menu (0-6): {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            simulate_lazy_evaluation()
        elif choice == "2":
            simulate_closures()
        elif choice == "3":
            simulate_apply_family()
        elif choice == "4":
            simulate_vectorized_control()
        elif choice == "5":
            simulate_pipeline_safely()
        elif choice == "6":
            run_all_simulations()
        elif choice == "0":
            print(f"{CLR_GREEN}Selesai. Terimakasih!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan ulangi.{CLR_RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_all_simulations()
    else:
        # Jalankan demonstrasi lengkap saat startup
        print(f"{CLR_BOLD}{CLR_GREEN}[STATUS] Menjalankan demonstrasi teknis terpadu...{CLR_RESET}")
        run_all_simulations()
        # Jika terminal interaktif, buka menu
        if sys.stdin.isatty():
            interactive_menu()
