#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Arsitektur R - Pemrograman Fungsional & Kontrol Eksekusi
Memodelkan runtime R: Promises (Lazy Evaluation), Lexical Environments,
Vector Recycling Rules, serta Higher-Order Functions (Lapply/Sapply/Reduce).
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Union

# ANSI Terminal Color Definitions
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_DARK = "\033[48;5;236m"


class Promise:
    """
    Simulasi R Promise: Mekanisme evaluasi malas (Lazy Evaluation).
    Ekspresi tidak dievaluasi hingga nilainya benar-benar diakses di runtime.
    """
    def __init__(self, expr: Callable[[], Any], name: str = "arg"):
        self.expr = expr
        self.name = name
        self._evaluated = False
        self._value = None

    def eval(self) -> Any:
        if not self._evaluated:
            print(f"  {Color.YELLOW}[PROMISE EVAL]{Color.RESET} Menghitung argumen malas '{self.name}'...")
            self._value = self.expr()
            self._evaluated = True
        else:
            print(f"  {Color.BLUE}[PROMISE CACHE]{Color.RESET} Mengambil nilai ter-cache untuk '{self.name}'.")
        return self._value

    @property
    def is_evaluated(self) -> bool:
        return self._evaluated


class REnvironment:
    """
    Simulasi R Lexical Environment: Mendukung rantai lingkup (parent-enclosing chain).
    """
    def __init__(self, parent: Optional['REnvironment'] = None, name: str = "R_GlobalEnv"):
        self.parent = parent
        self.name = name
        self.bindings: Dict[str, Any] = {}

    def assign(self, key: str, value: Any) -> None:
        self.bindings[key] = value

    def get(self, key: str) -> Any:
        if key in self.bindings:
            return self.bindings[key]
        if self.parent is not None:
            return self.parent.get(key)
        raise NameError(f"Objek '{key}' tidak ditemukan dalam rantai environment.")


class RVector:
    """
    Simulasi Vektor R dengan implementasi aturan daur ulang (Vector Recycling Rules).
    """
    def __init__(self, data: List[Union[int, float]]):
        self.data = list(data)

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        return f"c({', '.join(map(str, self.data))})"

    def __add__(self, other: 'RVector') -> 'RVector':
        l1, l2 = len(self.data), len(other.data)
        if l1 == 0 or l2 == 0:
            return RVector([])
        
        target_len = max(l1, l2)
        if (target_len % min(l1, l2)) != 0:
            print(f"  {Color.RED}[WARNING]{Color.RESET} Panjang objek yang lebih panjang bukan kelipatan dari yang lebih pendek.")

        # Aturan Daur Ulang Vektor (Vector Recycling)
        res = []
        for i in range(target_len):
            val1 = self.data[i % l1]
            val2 = other.data[i % l2]
            res.append(val1 + val2)
        return RVector(res)


# Implementasi Higher-Order Functions / Keluarga Apply
def r_lapply(vector: RVector, func: Callable[[Any], Any]) -> List[Any]:
    """Ekivalen dengan lapply() di R: Mengembalikan List objek."""
    return [func(x) for x in vector.data]


def r_sapply(vector: RVector, func: Callable[[Any], Any]) -> RVector:
    """Ekivalen dengan sapply() di R: Menyederhanakan output menjadi RVector jika homogen."""
    raw_results = [func(x) for x in vector.data]
    if all(isinstance(x, (int, float)) for x in raw_results):
        return RVector(raw_results)
    raise TypeError("Gagal menyederhanakan sapply ke RVector; tipe elemen tidak numerik.")


def r_reduce(func: Callable[[Any, Any], Any], vector: RVector, init: Optional[Any] = None) -> Any:
    """Ekivalen dengan Reduce() di R."""
    iterator = iter(vector.data)
    if init is None:
        try:
            acc = next(iterator)
        except StopIteration:
            raise ValueError("Reduce() pada vektor kosong tanpa nilai awal.")
    else:
        acc = init

    for item in iterator:
        acc = func(acc, item)
    return acc


def r_closure_factory(exponent: int, env: REnvironment) -> Callable[[int], int]:
    """Simulasi R Function Closure yang menyimpan enclosing lexical environment."""
    closure_env = REnvironment(parent=env, name=f"Closure_Exp{exponent}")
    closure_env.assign("exponent", exponent)

    def power_function(x: int) -> int:
        exp_val = closure_env.get("exponent")
        return x ** exp_val

    return power_function


def run_benchmark_lazy_evaluation():
    """Simulasi uji kontrol eksekusi: Lazy Evaluation & Pembuangan Komputasi Sia-sia."""
    print(f"\n{Color.CYAN}{Color.BOLD}=== Modul 1: Simulasi Lazy Evaluation (Call-by-Need Promises) ==={Color.RESET}")

    def expensive_io_operation() -> int:
        print(f"    {Color.MAGENTA}[EXEC-LOG]{Color.RESET} Menjalankan kalkulasi berat berdurasi 0.5 detik...")
        time.sleep(0.5)
        return 999

    def test_r_func(condition: bool, lazy_arg: Promise):
        print(f"  Memeriksa kondisi cabang: {condition}")
        if condition:
            # lazy_arg tidak disentuh sama sekali
            print(f"  {Color.GREEN}[OPTIMISASI]{Color.RESET} Kondisi True: Cabang 'lazy_arg' diabaikan.")
            return 42
        else:
            # lazy_arg dipaksa dievaluasi
            print(f"  {Color.YELLOW}[TRIGGER]{Color.RESET} Membutuhkan nilai lazy_arg...")
            val = lazy_arg.eval()
            # Pemanggilan kedua harus mengambil dari cache promise
            cached_val = lazy_arg.eval()
            return val + cached_val

    # Case A: Argumen tidak pernah diakses
    p1 = Promise(expensive_io_operation, name="heavy_calculation_1")
    t0 = time.time()
    res1 = test_r_func(condition=True, lazy_arg=p1)
    dur1 = time.time() - t0
    print(f"  Hasil Case A: {res1} (Waktu: {dur1:.4f}s, Dievaluasi: {p1.is_evaluated})")

    # Case B: Argumen harus diakses
    p2 = Promise(expensive_io_operation, name="heavy_calculation_2")
    t0 = time.time()
    res2 = test_r_func(condition=False, lazy_arg=p2)
    dur2 = time.time() - t0
    print(f"  Hasil Case B: {res2} (Waktu: {dur2:.4f}s, Dievaluasi: {p2.is_evaluated})")


def run_vector_recycling():
    """Simulasi aturan Vector Recycling di R Engine."""
    print(f"\n{Color.CYAN}{Color.BOLD}=== Modul 2: Vector Recycling Rules ==={Color.RESET}")
    v1 = RVector([1, 2, 3, 4, 5, 6])
    v2 = RVector([10, 20])
    v3 = RVector([100, 200, 300, 400])

    print(f"  Vector A : {v1} (Panjang {len(v1)})")
    print(f"  Vector B : {v2} (Panjang {len(v2)})")
    res_ab = v1 + v2
    print(f"  Vektor A + B (Kelipatan pas)  : {Color.GREEN}{res_ab}{Color.RESET}")

    print(f"\n  Vector C : {v3} (Panjang {len(v3)})")
    res_ac = v1 + v3
    print(f"  Vektor A + C (Bukan kelipatan): {Color.YELLOW}{res_ac}{Color.RESET}")


def run_functional_pipeline():
    """Simulasi ekosistem Apply Family, Scoping, & Function Pipeline."""
    print(f"\n{Color.CYAN}{Color.BOLD}=== Modul 3: Higher-Order Functions & Lexical Closures ==={Color.RESET}")

    global_env = REnvironment(name="Global_Context")
    global_env.assign("base_multiplier", 10)

    # Inisialisasi Function Factory (Closure)
    square_fn = r_closure_factory(exponent=2, env=global_env)
    cube_fn = r_closure_factory(exponent=3, env=global_env)

    raw_data = RVector([2, 3, 4, 5])
    print(f"  Dataset Vektor Dasar : {raw_data}")

    # Lapply
    list_result = r_lapply(raw_data, square_fn)
    print(f"  r_lapply (square_fn) -> {Color.WHITE}{list_result}{Color.RESET} (Type: list)")

    # Sapply
    vec_result = r_sapply(raw_data, cube_fn)
    print(f"  r_sapply (cube_fn)   -> {Color.GREEN}{vec_result}{Color.RESET} (Type: RVector)")

    # Reduce (Fold Operation)
    sum_cubes = r_reduce(lambda acc, x: acc + x, vec_result, init=0)
    print(f"  r_reduce (Sum of cubes) -> {Color.MAGENTA}{sum_cubes}{Color.RESET}")

    # Kombinasi Filter & Reduce Pipeline
    def is_even(n: int) -> bool:
        return n % 2 == 0

    even_cubes = RVector([x for x in vec_result.data if is_even(x)])
    product_even_cubes = r_reduce(lambda acc, x: acc * x, even_cubes, init=1)
    print(f"  Pipeline Filter(is_even) -> Reduce(*) : {Color.BOLD}{product_even_cubes}{Color.RESET}")


def main():
    print(f"{Color.BG_DARK}{Color.WHITE}{Color.BOLD} LAB ENGINE SIMULATOR: R FUNCTIONAL PARADIGM & EXECUTION CONTROL {Color.RESET}")
    print(f"Arsitektur Target: R 4.x Runtime Semantics (Interpreter Layer)\n" + ("=" * 70))

    try:
        run_benchmark_lazy_evaluation()
        run_vector_recycling()
        run_functional_pipeline()
        print(f"\n{Color.GREEN}{Color.BOLD}[SUKSES]{Color.RESET} Semua modul eksekusi simulasi R selesai tanpa anomali.")
    except Exception as err:
        print(f"\n{Color.RED}{Color.BOLD}[FATAL ERROR]{Color.RESET} Kegagalan interpretasi: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()