#!/usr/bin/env python3
"""
Hands-On Lab: Simulasi Fondasi & Arsitektur Internal Bahasa R (BAB-01)
--------------------------------------------------------------------
Modul ini mendemonstrasikan 5 mekanisme fundamental mesin runtime R:
1. Vektor Atomik & Aturan Daur Ulang (Recycling Rule)
2. Mekanisme Memori Copy-on-Modify (tracemem)
3. Hierarki Environment & Lexical Scoping
4. Lazy Evaluation & Promise Mechanism
5. S3 Dynamic Dispatch System
"""

import sys
import copy
import time
from typing import Any, List, Dict, Optional, Callable


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_BLUE = "\033[44m\033[97m"


def print_banner(title: str) -> None:
    width = 68
    print(f"\n{ANSI.CYAN}{'═' * width}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.BG_BLUE}  {title.center(width - 4)}  {ANSI.RESET}")
    print(f"{ANSI.CYAN}{'═' * width}{ANSI.RESET}\n")


def print_step(name: str, desc: str) -> None:
    print(f"{ANSI.YELLOW}❯ [DEMO]{ANSI.RESET} {ANSI.BOLD}{name}{ANSI.RESET}: {desc}")


def print_success(msg: str) -> None:
    print(f"  {ANSI.GREEN}✔ {msg}{ANSI.RESET}")


def print_info(msg: str) -> None:
    print(f"  {ANSI.BLUE}ℹ {msg}{ANSI.RESET}")


def print_warning(msg: str) -> None:
    print(f"  {ANSI.MAGENTA}⚠ {msg}{ANSI.RESET}")


# ------------------------------------------------------------------------------
# 1. SIMULASI VEKTOR & RECYCLING RULE R
# ------------------------------------------------------------------------------
class RVector:
    def __init__(self, elements: List[Any], r_type: str = "numeric"):
        self.elements = elements
        self.r_type = r_type

    def __repr__(self) -> str:
        vals = ", ".join(str(x) for x in self.elements)
        return f"{ANSI.CYAN}c({vals}){ANSI.RESET} [type: {self.r_type}, length: {len(self.elements)}]"

    def add_with_recycling(self, other: "RVector") -> "RVector":
        len_a = len(self.elements)
        len_b = len(other.elements)
        max_len = max(len_a, len_b)

        if max_len % min(len_a, len_b) != 0 and min(len_a, len_b) != 0:
            print_warning(
                f"Recycling warning: panjang objek yang lebih panjang ({max_len}) "
                f"bukan kelipatan dari objek yang lebih pendek ({min(len_a, len_b)})"
            )

        result = []
        for i in range(max_len):
            val_a = self.elements[i % len_a]
            val_b = other.elements[i % len_b]
            result.append(val_a + val_b)

        return RVector(result, self.r_type)


def demo_recycling_rule():
    print_banner("1. VEKTOR ATOMIK & VECTOR RECYCLING RULE")
    print_step(
        "Operasi Vektor",
        "R tidak memiliki skalar riil; skalar hanyalah vektor berpanjang 1.",
    )

    v1 = RVector([10, 20, 30, 40], "numeric")
    v2 = RVector([1, 2], "numeric")
    v3 = RVector([1, 2, 3], "numeric")

    print_info(f"Vektor A (panjang 4) : {v1}")
    print_info(f"Vektor B (panjang 2) : {v2}")
    res1 = v1.add_with_recycling(v2)
    print_success(f"Hasil A + B (kelipatan pas): {res1}")

    print_info(f"\nVektor C (panjang 3) : {v3}")
    res2 = v1.add_with_recycling(v3)
    print_success(f"Hasil A + C (bukan kelipatan): {res2}")


# ------------------------------------------------------------------------------
# 2. SIMULASI MEMORI: COPY-ON-MODIFY (CoM) & TRACEMEM
# ------------------------------------------------------------------------------
class RMemoryObject:
    def __init__(self, name: str, data: List[int]):
        self.name = name
        self.data = list(data)
        self._address = id(self.data)

    def print_ref(self):
        print(f"  {ANSI.BOLD}{self.name}{ANSI.RESET} -> Address: {ANSI.YELLOW}0x{self._address:x}{ANSI.RESET} | Data: {self.data}")

    def mutate(self, index: int, new_val: int):
        print_step("Modifikasi Data", f"Mengubah indeks [{index}] menjadi {new_val}")
        old_addr = self._address
        # Simulasi CoM: Alokasi list baru di memori
        self.data = list(self.data)
        self.data[index] = new_val
        self._address = id(self.data)
        print_warning(f"tracemem trigger: 0x{old_addr:x} -> 0x{self._address:x} (Alokasi Memori Baru!)")


def demo_copy_on_modify():
    print_banner("2. ARSITEKTUR MEMORI: COPY-ON-MODIFY (CoM)")
    print_step("Inisialisasi Objek x", "Objek dialokasikan di heap R")
    x = RMemoryObject("x", [1, 2, 3, 4, 5])
    x.print_ref()

    print_step("Binding Pointer y <- x", "y merujuk pada buffer memori yang persis sama (Zero-copy)")
    y_data = x.data
    print(f"  {ANSI.BOLD}y{ANSI.RESET} -> Address: {ANSI.YELLOW}0x{id(y_data):x}{ANSI.RESET} | Data: {y_data}")
    print_success("x dan y berbagi alamat memori yang sama tanpa duplikasi!")

    print_step("Mutasi x[0] <- 99", "Memicu mekanisme duplikasi Copy-on-Modify R")
    x.mutate(0, 99)
    x.print_ref()
    print(f"  {ANSI.BOLD}y (tidak berubah){ANSI.RESET} -> Address: {ANSI.YELLOW}0x{id(y_data):x}{ANSI.RESET} | Data: {y_data}")


# ------------------------------------------------------------------------------
# 3. SIMULASI ENVIRONMENT & LEXICAL SCOPING
# ------------------------------------------------------------------------------
class REnvironment:
    def __init__(self, name: str, parent: Optional["REnvironment"] = None):
        self.name = name
        self.parent = parent
        self.bindings: Dict[str, Any] = {}

    def assign(self, key: str, value: Any):
        self.bindings[key] = value

    def get(self, key: str) -> Any:
        if key in self.bindings:
            return self.bindings[key], self.name
        if self.parent:
            return self.parent.get(key)
        raise NameError(f"Objek '{key}' tidak ditemukan pada search path environment.")


def demo_lexical_scoping():
    print_banner("3. HIERARKI ENVIRONMENT & LEXICAL SCOPING")
    empty_env = REnvironment("R_EmptyEnv", None)
    base_env = REnvironment("package:base", empty_env)
    base_env.assign("pi", 3.14159)

    global_env = REnvironment("R_GlobalEnv", base_env)
    global_env.assign("alpha", 100)
    global_env.assign("shared_var", "Global Value")

    func_env = REnvironment("ExecutionEnv:f()", global_env)
    func_env.assign("shared_var", "Local Value in f()")
    func_env.assign("beta", 42)

    print_step("Lookup Hierarki", "Mencari variabel di dalam execution frame")
    for var in ["beta", "shared_var", "alpha", "pi"]:
        val, found_in = func_env.get(var)
        print_success(f"Variable '{var}' = {ANSI.BOLD}{val}{ANSI.RESET} (Ditemukan di: {ANSI.CYAN}{found_in}{ANSI.RESET})")


# ------------------------------------------------------------------------------
# 4. SIMULASI LAZY EVALUATION & PROMISE MECHANISM
# ------------------------------------------------------------------------------
class RPromise:
    def __init__(self, expr_repr: str, thunk: Callable[[], Any]):
        self.expr_repr = expr_repr
        self.thunk = thunk
        self.is_evaluated = False
        self.value = None

    def evaluate(self) -> Any:
        if not self.is_evaluated:
            print_warning(f"Promise [{self.expr_repr}] sedang dievaluasi untuk pertama kali...")
            time.sleep(0.3)
            self.value = self.thunk()
            self.is_evaluated = True
        else:
            print_info(f"Promise [{self.expr_repr}] sudah dievaluasi, membaca cache.")
        return self.value


def r_function_simulator(a_promise: RPromise, b_promise: RPromise, use_b: bool = False):
    print_info(f"Memulai eksekusi fungsi simulasi...")
    val_a = a_promise.evaluate()
    print_success(f"Argumen 'a' dievaluasi menghasilkan: {val_a}")

    if use_b:
        val_b = b_promise.evaluate()
        print_success(f"Argumen 'b' dievaluasi menghasilkan: {val_b}")
    else:
        print_info("Argumen 'b' TIDAK pernah dipanggil, ekspresi 'b' tidak pernah dieksekusi!")


def demo_lazy_evaluation():
    print_banner("4. LAZY EVALUATION & PROMISE STRUCTURE")
    print_step("Mendefinisikan Argumen Fungsi", "Argumen R di-pass sebagai unresolved promises")

    p1 = RPromise("10 + 20", lambda: 10 + 20)
    p2 = RPromise("stop('Komputasi Error Berat')", lambda: 1 / 0)

    print_info("Kasus 1: Panggilan fungsi tanpa menggunakan argumen b")
    r_function_simulator(p1, p2, use_b=False)
    print_success("Ekspresi berbahaya pada 'b' tidak meledak karena evaluasi malas (Lazy Eval)!")


# ------------------------------------------------------------------------------
# 5. SIMULASI S3 OBJECT SYSTEM & METHOD DISPATCH
# ------------------------------------------------------------------------------
class S3Object:
    def __init__(self, data: Any, classes: List[str]):
        self.data = data
        self.classes = classes


class S3Generic:
    def __init__(self, name: str):
        self.name = name
        self.registry: Dict[str, Callable[[S3Object], str]] = {}

    def register_method(self, class_name: str, method: Callable[[S3Object], str]):
        self.registry[f"{self.name}.{class_name}"] = method

    def dispatch(self, obj: S3Object) -> str:
        for cls in obj.classes:
            target = f"{self.name}.{cls}"
            if target in self.registry:
                print_info(f"S3 Dispatch: Mengarahkan panggilan ke method -> {ANSI.BOLD}{target}{ANSI.RESET}")
                return self.registry[target](obj)

        default_target = f"{self.name}.default"
        if default_target in self.registry:
            print_info(f"S3 Dispatch: Tidak ada spesifik class, memanggil -> {default_target}")
            return self.registry[default_target](obj)

        raise NotImplementedError(f"Generic '{self.name}' tidak memiliki method untuk class {obj.classes}")


def demo_s3_dispatch():
    print_banner("5. S3 SYSTEM & DYNAMIC METHOD DISPATCH")
    print_step("Membuat Generic Function", "Definisi 'summary' generic di R")

    summary_generic = S3Generic("summary")
    summary_generic.register_method("numeric", lambda obj: f"[Summary Numeric] Mean: {sum(obj.data)/len(obj.data)}, Min: {min(obj.data)}, Max: {max(obj.data)}")
    summary_generic.register_method("factor", lambda obj: f"[Summary Factor] Levels: {set(obj.data)}, Counts: {len(obj.data)}")
    summary_generic.register_method("default", lambda obj: f"[Summary Default] Raw Data: {obj.data}")

    num_obj = S3Object([12, 45, 67, 89], ["numeric"])
    factor_obj = S3Object(["A", "B", "A", "C"], ["factor"])
    custom_obj = S3Object("Simple String", ["unknown_type"])

    print_success(summary_generic.dispatch(num_obj))
    print_success(summary_generic.dispatch(factor_obj))
    print_success(summary_generic.dispatch(custom_obj))


# ------------------------------------------------------------------------------
# INTERACTIVE CLI DISPATCHER
# ------------------------------------------------------------------------------
def run_all():
    demo_recycling_rule()
    demo_copy_on_modify()
    demo_lexical_scoping()
    demo_lazy_evaluation()
    demo_s3_dispatch()
    print_banner("SELURUH SIMULASI SELESAI DENGAN SUKSES")


def interactive_menu():
    while True:
        print_banner("LAB INTERAKTIF: FONDASI & ARSITEKTUR R")
        print(f"  {ANSI.BOLD}1{ANSI.RESET}. Demo Vektor & Vector Recycling Rule")
        print(f"  {ANSI.BOLD}2{ANSI.RESET}. Demo Copy-on-Modify (CoM) & Memory Address")
        print(f"  {ANSI.BOLD}3{ANSI.RESET}. Demo Hierarki Environment & Lexical Scoping")
        print(f"  {ANSI.BOLD}4{ANSI.RESET}. Demo Lazy Evaluation & Promise System")
        print(f"  {ANSI.BOLD}5{ANSI.RESET}. Demo S3 Generic Method Dispatch")
        print(f"  {ANSI.BOLD}A{ANSI.RESET}. Jalankan Semua Demonstrasi")
        print(f"  {ANSI.BOLD}Q{ANSI.RESET}. Keluar")

        choice = input(f"\n{ANSI.YELLOW}Pilih modul simulasi [1-5/A/Q]: {ANSI.RESET}").strip().upper()
        if choice == "1":
            demo_recycling_rule()
        elif choice == "2":
            demo_copy_on_modify()
        elif choice == "3":
            demo_lexical_scoping()
        elif choice == "4":
            demo_lazy_evaluation()
        elif choice == "5":
            demo_s3_dispatch()
        elif choice == "A":
            run_all()
        elif choice == "Q":
            print(f"\n{ANSI.GREEN}Terima kasih telah mempelajari Arsitektur Mesin R!{ANSI.RESET}\n")
            break
        else:
            print_warning("Pilihan tidak valid, silakan masukkan nomor modul yang sesuai.")
        input(f"\n{ANSI.DIM}Tekan [Enter] untuk kembali ke menu...{ANSI.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--all", "-a"]:
        run_all()
    else:
        interactive_menu()
