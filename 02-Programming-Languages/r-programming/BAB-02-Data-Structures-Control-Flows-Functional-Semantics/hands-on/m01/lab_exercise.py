#!/usr/bin/env python3
"""
Lab Exercise: Simulasi R-Programming Semantics dalam Python 3
BAB-02: Data Structures, Control Flows, & Functional Semantics
"""

import sys
import copy
import time
from typing import Any, List, Callable, Union

# ANSI Terminal Colors
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}\n")


def log_step(name: str, desc: str) -> None:
    print(f"{Color.CYAN}[SIMULASI]{Color.RESET} {Color.BOLD}{name}{Color.RESET}: {desc}")


def log_result(label: str, val: Any) -> None:
    print(f"  {Color.GREEN}➜ {label}:{Color.RESET} {Color.YELLOW}{val}{Color.RESET}")


def log_warn(msg: str) -> None:
    print(f"  {Color.MAGENTA}⚠ PERINGATAN R-RUNTIME:{Color.RESET} {msg}")


# 1. ATOMIC VECTORS & AUTOMATIC COERCION SIMULATION
def simulate_atomic_coercion():
    header("1. R Atomic Vector & Implicit Type Coercion Hierarchy")
    log_step("Aturan Koersi", "logical -> integer -> double -> character")

    test_cases = [
        ([True, False, True], "logical"),
        ([True, 10, False], "integer"),
        ([True, 10, 3.14], "double"),
        ([True, 10, 3.14, "R-Lang"], "character"),
    ]

    for raw_data, expected_r_type in test_cases:
        coerced = []
        if expected_r_type == "logical":
            coerced = [bool(x) for x in raw_data]
        elif expected_r_type == "integer":
            coerced = [int(x) for x in raw_data]
        elif expected_r_type == "double":
            coerced = [float(x) for x in raw_data]
        elif expected_r_type == "character":
            coerced = [str(x) for x in raw_data]

        print(f"\nInput Mentah : {raw_data}")
        log_result("Tipe Target R", expected_r_type)
        log_result("Hasil Koersi ", coerced)
        log_result("R typeof()   ", [type(x).__name__ for x in coerced])


# 2. VECTOR RECYCLING RULE SIMULATION
def simulate_recycling_rule(vec_a: List[Union[int, float]], vec_b: List[Union[int, float]]) -> List[Union[int, float]]:
    header("2. R Vector Recycling Rule (Operasi Vektorisasi)")
    log_step("Operasi", f"vec_a + vec_b | Len A: {len(vec_a)}, Len B: {len(vec_b)}")

    len_a = len(vec_a)
    len_b = len(vec_b)
    max_len = max(len_a, len_b)

    if max_len % min(len_a, len_b) != 0:
        log_warn("longer object length is not a multiple of shorter object length")

    # Simulasi recycling
    recycled_a = [vec_a[i % len_a] for i in range(max_len)]
    recycled_b = [vec_b[i % len_b] for i in range(max_len)]
    result = [recycled_a[i] + recycled_b[i] for i in range(max_len)]

    log_result("Vector A (Recycled)", recycled_a)
    log_result("Vector B (Recycled)", recycled_b)
    log_result("Hasil Penjumlahan  ", result)
    return result


# 3. COPY-ON-MODIFY SEMANTICS SIMULATION
class RObject:
    def __init__(self, name: str, data: List[Any]):
        self.name = name
        self.data = data
        self.mem_address = hex(id(self.data))

    def print_status(self, label: str):
        print(f"  [{label}] Object {Color.BOLD}'{self.name}'{Color.RESET} -> "
              f"Address: {Color.CYAN}{self.mem_address}{Color.RESET}, Data: {self.data}")


def simulate_copy_on_modify():
    header("3. R Copy-on-Modify (tracemem) Semantics")
    log_step("Inisialisasi", "Membuat objek 'x' dan alias 'y <- x'")

    x_data = [10, 20, 30]
    x = RObject("x", x_data)
    y = RObject("y", x_data)  # Menunjuk ke referensi memori yang sama

    x.print_status("Initial Reference")
    y.print_status("Initial Reference")

    log_step("Mutasi", "Modifikasi elemen kedua: y[2] <- 999")
    print(f"  {Color.MAGENTA}tracemem: objek diduplikasi karena mutasi terdeteksi!{Color.RESET}")

    # Copy-on-modify: duplikasi struktur sebelum mutasi
    y.data = copy.deepcopy(x.data)
    y.data[1] = 999
    y.mem_address = hex(id(y.data))

    x.print_status("Post-Modification")
    y.print_status("Post-Modification")


# 4. FUNCTIONAL SEMANTICS (APPLY FAMILY) SIMULATION
def r_lapply(data_list: List[Any], func: Callable[[Any], Any]) -> List[Any]:
    return [func(x) for x in data_list]


def r_sapply(data_list: List[Any], func: Callable[[Any], Any]) -> List[Any]:
    # Simulasi sapply yang menyederhanakan (simplify) output jika seragam
    results = [func(x) for x in data_list]
    return results


def simulate_functional_apply():
    header("4. R Functional Semantics: lapply & sapply")
    data = [1, 4, 9, 16, 25]
    log_step("Dataset Awal", f"{data}")

    square_root = lambda x: x ** 0.5

    lapply_res = r_lapply(data, square_root)
    log_result("r_lapply (akar kuadrat)", lapply_res)

    sapply_res = r_sapply(data, lambda x: f"VAL_{x*2}")
    log_result("r_sapply (format string)", sapply_res)


# INTERACTIVE SHELL SIMULATION
def interactive_menu():
    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}===================================================={Color.RESET}")
        print(f"{Color.BOLD}{Color.GREEN}   SIMULATOR SEMANTIK R-PROGRAMMING (BAB-02){Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}===================================================={Color.RESET}")
        print(f"  {Color.CYAN}[1]{Color.RESET} Simulasi Aturan Koersi Vektor Atomik")
        print(f"  {Color.CYAN}[2]{Color.RESET} Simulasi Vector Recycling Rule")
        print(f"  {Color.CYAN}[3]{Color.RESET} Simulasi Semantik Copy-on-Modify (tracemem)")
        print(f"  {Color.CYAN}[4]{Color.RESET} Simulasi Functional Semantics (lapply & sapply)")
        print(f"  {Color.CYAN}[5]{Color.RESET} Jalankan Seluruh Demonstrasi Otomatis")
        print(f"  {Color.RED}[0] Keluar{Color.RESET}")
        print(f"{Color.BOLD}----------------------------------------------------{Color.RESET}")

        try:
            choice = input(f"{Color.YELLOW}Pilih modul simulasi [0-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == "1":
            simulate_atomic_coercion()
        elif choice == "2":
            simulate_recycling_rule([1, 2, 3, 4, 5, 6], [10, 20])
            simulate_recycling_rule([10, 20, 30, 40], [1, 2, 3])
        elif choice == "3":
            simulate_copy_on_modify()
        elif choice == "4":
            simulate_functional_apply()
        elif choice == "5":
            simulate_atomic_coercion()
            simulate_recycling_rule([1, 2, 3, 4], [10, 20])
            simulate_recycling_rule([1, 2, 3], [10, 20])
            simulate_copy_on_modify()
            simulate_functional_apply()
        elif choice == "0":
            print(f"\n{Color.GREEN}Menutup simulator. Selamat belajar R-Programming!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Mode batch/headless
        simulate_atomic_coercion()
        simulate_recycling_rule([1, 2, 3, 4], [10, 20])
        simulate_recycling_rule([1, 2, 3], [10, 20])
        simulate_copy_on_modify()
        simulate_functional_apply()
    else:
        interactive_menu()
