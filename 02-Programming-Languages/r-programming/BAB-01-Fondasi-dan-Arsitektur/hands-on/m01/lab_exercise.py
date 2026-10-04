#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Simulasi Fondasi & Arsitektur Internal R Programming
BAB-01: Fondasi dan Arsitektur (R-Programming Engine & Runtime Simulator)

Modul ini mengimplementasikan simulasi interaktif arsitektur internal runtime R:
1. Atomic Vectors & Recycling Rule
2. Copy-on-Write (CoW) Memory Semantics
3. Lexical Scoping & Hierarchical Environments
4. Lazy Evaluation & Argument Promises
5. S3 Object System & Method Dispatch
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class ANSI:
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
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{ANSI.BOLD}{ANSI.BG_BLUE}{ANSI.WHITE} === {title} === {ANSI.RESET}\n")


def subheader(title: str) -> None:
    print(f"{ANSI.BOLD}{ANSI.CYAN}--- {title} ---{ANSI.RESET}")


def success(msg: str) -> None:
    print(f"{ANSI.GREEN}✓ {msg}{ANSI.RESET}")


def info(msg: str) -> None:
    print(f"{ANSI.YELLOW}ℹ {msg}{ANSI.RESET}")


def detail(label: str, val: Any) -> None:
    print(f"  {ANSI.BOLD}{label}:{ANSI.RESET} {ANSI.WHITE}{val}{ANSI.RESET}")


class RVector:
    """Simulasi R Atomic Vector dengan type coercion dan Recycling Rule."""

    TYPES_HIERARCHY = ["logical", "integer", "double", "character"]

    def __init__(self, data: List[Any], r_type: Optional[str] = None):
        self.raw_data = data
        self.r_type = r_type or self._infer_and_coerce()

    def _infer_and_coerce(self) -> str:
        if not self.raw_data:
            return "logical"
        has_str = any(isinstance(x, str) for x in self.raw_data)
        has_float = any(isinstance(x, float) for x in self.raw_data)
        has_int = any(isinstance(x, int) and not isinstance(x, bool) for x in self.raw_data)

        if has_str:
            self.raw_data = [str(x) for x in self.raw_data]
            return "character"
        elif has_float:
            self.raw_data = [float(x) for x in self.raw_data]
            return "double"
        elif has_int:
            self.raw_data = [int(x) for x in self.raw_data]
            return "integer"
        else:
            self.raw_data = [bool(x) for x in self.raw_data]
            return "logical"

    def __repr__(self) -> str:
        vals = ", ".join(repr(x) for x in self.raw_data)
        return f"{ANSI.MAGENTA}[{self.r_type}]{ANSI.RESET} c({vals})"

    def add_with_recycling(self, other: "RVector") -> "RVector":
        len1 = len(self.raw_data)
        len2 = len(other.raw_data)
        if len1 == 0 or len2 == 0:
            return RVector([])

        max_len = max(len1, len2)
        if max_len % min(len1, len2) != 0:
            print(f"{ANSI.RED}Warning: longer object length is not a multiple of shorter object length!{ANSI.RESET}")

        result: List[Any] = []
        for i in range(max_len):
            v1 = self.raw_data[i % len1]
            v2 = other.raw_data[i % len2]
            result.append(v1 + v2)
        return RVector(result)


class REnvironment:
    """Simulasi R Environment dengan enclosing scope (lexical scoping)."""

    def __init__(self, name: str, parent: Optional["REnvironment"] = None):
        self.name = name
        self.parent = parent
        self.frame: Dict[str, Any] = {}

    def assign(self, key: str, value: Any) -> None:
        self.frame[key] = value

    def get(self, key: str) -> Tuple[Any, str]:
        if key in self.frame:
            return self.frame[key], self.name
        if self.parent is not None:
            return self.parent.get(key)
        raise KeyError(f"object '{key}' not found in environment tree")


class RPromise:
    """Simulasi R Lazy Evaluation Promise (expr + env + evaluated value)."""

    def __init__(self, expr_repr: str, evaluator: Callable[[], Any]):
        self.expr_repr = expr_repr
        self.evaluator = evaluator
        self._evaluated = False
        self._value: Any = None

    def evaluate(self) -> Any:
        if not self._evaluated:
            info(f"Triggering lazy evaluation for promise: {ANSI.BOLD}{self.expr_repr}{ANSI.RESET}")
            self._value = self.evaluator()
            self._evaluated = True
        else:
            print(f"  {ANSI.DIM}(Value cached in promise, no re-evaluation required){ANSI.RESET}")
        return self._value


class RS3Dispatcher:
    """Simulasi R S3 Generic Method Dispatch System."""

    def __init__(self, generic_name: str):
        self.generic_name = generic_name
        self.methods: Dict[str, Callable[[Any], str]] = {}

    def register(self, class_name: str, fn: Callable[[Any], str]) -> None:
        self.methods[class_name] = fn

    def dispatch(self, obj: Any) -> str:
        cls = getattr(obj, "s3_class", "default")
        method = self.methods.get(cls) or self.methods.get("default")
        if not method:
            raise NotImplementedError(f"No method for generic '{self.generic_name}' on class '{cls}'")
        detail(f"Dispatching to S3 method", f"{self.generic_name}.{cls}()")
        return method(obj)


def demo_vectors_and_recycling() -> None:
    header("1. ATOMIC VECTORS & RECYCLING RULE")
    info("Di R, semua skalar adalah vector berpanjang 1. Coercion otomatis terjadi secara hierarkis:")
    print(f"  logical -> integer -> double -> character\n")

    v1 = RVector([1, 2, 3, 4, 5, 6])
    v2 = RVector([10, 20])
    v_coerced = RVector([1, 2.5, "R-core", True])

    detail("Vector 1 (len=6)", v1)
    detail("Vector 2 (len=2)", v2)
    detail("Heterogeneous Input Auto-Coerced", v_coerced)

    print(f"\n{ANSI.BOLD}Melakukan Operasi: v1 + v2 (Recycling Rule){ANSI.RESET}")
    result = v1.add_with_recycling(v2)
    detail("Hasil Penjumlahan", result)
    success("Vector 2 otomatis direcycle: [10, 20, 10, 20, 10, 20]")


def demo_copy_on_write() -> None:
    header("2. MEMORY MODEL: COPY-ON-WRITE (CoW) SEMANTICS")
    info("R menghemat memori dengan shared address hingga elemen dimodifikasi.")

    base_list = [10, 20, 30, 40]
    ref_x = base_list
    addr_x = id(ref_x)
    ref_y = ref_x
    addr_y = id(ref_y)

    detail("x <- c(10, 20, 30, 40) | Address", hex(addr_x))
    detail("y <- x                 | Address", hex(addr_y))

    if addr_x == addr_y:
        success("x dan y menunjuk ke alamat memori yang sama (Zero-copy pass-by-value)")

    print(f"\n{ANSI.BOLD}Modifikasi elemen y: y[1] <- 999 (Mutasi dipicu){ANSI.RESET}")
    ref_y = list(ref_x)
    ref_y[0] = 999
    new_addr_y = id(ref_y)

    detail("x data", ref_x)
    detail("y data", ref_y)
    detail("x Address", hex(id(ref_x)))
    detail("y New Address (Duplicated via CoW)", hex(new_addr_y))
    success("CoW terpicu: Objek digandakan hanya saat terjadi penulisan (write/mutation).")


def demo_environments_and_scoping() -> None:
    header("3. LEXICAL SCOPING & ENVIRONMENT CHAIN")
    info("Pencarian variabel di R bergerak ke atas melalui parent environment.")

    global_env = REnvironment("R_GlobalEnv")
    global_env.assign("x", 100)
    global_env.assign("app_name", "DataEngine")

    package_env = REnvironment("package:stats", parent=global_env)
    package_env.assign("alpha", 0.05)

    exec_env = REnvironment("execution:my_fn()", parent=package_env)
    exec_env.assign("x", 999)
    exec_env.assign("local_var", "scratchpad")

    detail("Mencari 'local_var'", exec_env.get("local_var"))
    detail("Mencari 'x' (Shadowing Global)", exec_env.get("x"))
    detail("Mencari 'alpha' (Upchain lookup)", exec_env.get("alpha"))
    detail("Mencari 'app_name' (Top ancestor)", exec_env.get("app_name"))

    try:
        exec_env.get("undefined_var")
    except KeyError as err:
        success(f"Lookup failure tertangkap dengan benar: {err}")


def demo_lazy_evaluation() -> None:
    header("4. LAZY EVALUATION (PROMISES)")
    info("Argumen fungsi R dibungkus sebagai promise dan HANYA dievaluasi saat dibaca.")

    def expensive_calc() -> int:
        print(f"    {ANSI.RED}-> [COMPUTE] Menjalankan kalkulasi berat...{ANSI.RESET}")
        time.sleep(0.3)
        return 42 * 100

    promise_a = RPromise("expensive_calc()", expensive_calc)
    promise_b = RPromise("never_called()", lambda: 1 / 0)

    print("Memanggil fungsi simulasi: `calc_summary(a, b, flag=False)`")
    detail("Promise A status", "UNTOUCHED")
    detail("Promise B status", "UNTOUCHED (error division by zero terlindungi)")

    info("Membaca argumen 'a'...")
    val_a = promise_a.evaluate()
    detail("Hasil pembacaan 'a'", val_a)

    info("Membaca kembali argumen 'a' (Cache hit)...")
    val_a_cached = promise_a.evaluate()
    detail("Nilai didapat", val_a_cached)
    success("Lazy evaluation terbukti: Promise B tidak pernah meledak karena tidak disentuh.")


def demo_s3_system() -> None:
    header("5. S3 OBJECT SYSTEM & GENERIC DISPATCH")
    info("S3 mendasarkan polymorphisme pada class attribute dan penamaan method generic.class()")

    class ModelResult:
        def __init__(self, name: str, r2: float, s3_class: str):
            self.name = name
            self.r2 = r2
            self.s3_class = s3_class

    summary_generic = RS3Dispatcher("summary")

    summary_generic.register("lm", lambda obj: f"Linear Model: {obj.name} | R² = {obj.r2:.4f}")
    summary_generic.register("glm", lambda obj: f"Generalized Linear Model: {obj.name} | Deviance R² = {obj.r2:.4f}")
    summary_generic.register("default", lambda obj: f"Default Object Summary: {repr(obj)}")

    m1 = ModelResult("ols_sales", 0.8842, "lm")
    m2 = ModelResult("logistic_churn", 0.7410, "glm")
    m3 = ModelResult("unknown_metric", 0.0, "custom_struct")

    detail("summary(m1)", summary_generic.dispatch(m1))
    detail("summary(m2)", summary_generic.dispatch(m2))
    detail("summary(m3)", summary_generic.dispatch(m3))
    success("S3 generic dispatch berhasil memetakan tipe objek secara dinamis.")


def interactive_menu() -> None:
    while True:
        print(f"\n{ANSI.BOLD}{ANSI.WHITE}=== LAB FONDASI R PROGRAMMING - MENU UTAMA ==={ANSI.RESET}")
        print("1. Atomic Vectors & Recycling Rule")
        print("2. Memory Model: Copy-on-Write (CoW)")
        print("3. Lexical Scoping & Hierarchical Environments")
        print("4. Lazy Evaluation & Argument Promises")
        print("5. S3 Object System & Method Dispatch")
        print("6. Jalankan Semua Demonstrasi Sekaligus")
        print("7. Keluar")

        try:
            choice = input(f"\n{ANSI.BOLD}Pilih modul simulasi [1-7]: {ANSI.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{ANSI.YELLOW}Keluar dari program...{ANSI.RESET}")
            break

        if choice == "1":
            demo_vectors_and_recycling()
        elif choice == "2":
            demo_copy_on_write()
        elif choice == "3":
            demo_environments_and_scoping()
        elif choice == "4":
            demo_lazy_evaluation()
        elif choice == "5":
            demo_s3_system()
        elif choice == "6":
            demo_vectors_and_recycling()
            demo_copy_on_write()
            demo_environments_and_scoping()
            demo_lazy_evaluation()
            demo_s3_system()
        elif choice == "7":
            print(f"{ANSI.GREEN}Lab simulasi selesai. Sampai jumpa!{ANSI.RESET}")
            break
        else:
            print(f"{ANSI.RED}Pilihan tidak valid. Silakan masukkan angka 1 sampai 7.{ANSI.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_vectors_and_recycling()
        demo_copy_on_write()
        demo_environments_and_scoping()
        demo_lazy_evaluation()
        demo_s3_system()
    else:
        interactive_menu()
