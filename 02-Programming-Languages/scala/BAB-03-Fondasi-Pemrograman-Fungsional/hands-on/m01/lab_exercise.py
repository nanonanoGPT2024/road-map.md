#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Pemrograman Fungsional (Scala Paradigm)
Modul: BAB-03 - Fondasi Pemrograman Fungsional
Deskripsi:
    Simulasi teknis konsep-konsep inti Functional Programming (FP) yang
    menjadi pilar bahasa Scala, meliputi:
    1. Pure Functions & Referential Transparency
    2. Higher-Order Functions (HOF: map, filter, foldLeft, flatMap)
    3. Currying & Partial Application
    4. Algebraic Data Types (ADT) & Pattern Matching (Option: Some / None)
    5. Tail Recursion Simulation dengan Accumulator
"""

import sys
import time
from typing import Callable, TypeVar, Generic, Optional, Any, List

# ANSI Color Codes untuk visualisasi terminal
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

T = TypeVar("T")
U = TypeVar("U")


# ============================================================================
# 1. Algebraic Data Types (ADT) & Pattern Matching: Scala Option[T]
# ============================================================================
class Option(Generic[T]):
    """Simulasi Scala sealed trait Option[+A]"""

    def is_defined(self) -> bool:
        raise NotImplementedError

    def get_or_else(self, default: T) -> T:
        raise NotImplementedError

    def map(self, f: Callable[[T], U]) -> "Option[U]":
        raise NotImplementedError

    def flat_map(self, f: Callable[[T], "Option[U]"]) -> "Option[U]":
        raise NotImplementedError


class Some(Option[T]):
    """Simulasi Scala case class Some[A](value: A)"""
    __match_args__ = ("value",)

    def __init__(self, value: T) -> None:
        self.value = value

    def is_defined(self) -> bool:
        return True

    def get_or_else(self, default: T) -> T:
        return self.value

    def map(self, f: Callable[[T], U]) -> Option[U]:
        return Some(f(self.value))

    def flat_map(self, f: Callable[[T], Option[U]]) -> Option[U]:
        return f(self.value)

    def __repr__(self) -> str:
        return f"Some({self.value})"


class NoneVal(Option[Any]):
    """Simulasi Scala case object None"""

    def is_defined(self) -> bool:
        return False

    def get_or_else(self, default: T) -> T:
        return default

    def map(self, f: Callable[[Any], U]) -> Option[U]:
        return NONE

    def flat_map(self, f: Callable[[Any], Option[U]]) -> Option[U]:
        return NONE

    def __repr__(self) -> str:
        return "None"


NONE = NoneVal()


def pattern_match_option(opt: Option[T]) -> str:
    """Simulasi Scala: opt match { case Some(v) => ...; case None => ... }"""
    match opt:
        case Some(val):
            return f"{GREEN}[MATCH: Some]{RESET} Nilai ditemukan: {BOLD}{val}{RESET}"
        case NoneVal():
            return f"{YELLOW}[MATCH: None]{RESET} Nilai kosong / safe missing value"
        case _:
            return f"{RED}[MATCH: Unknown]{RESET}"


# ============================================================================
# 2. Pure Functions & Referential Transparency
# ============================================================================
def pure_transform(data: List[int], factor: int) -> List[int]:
    """Pure Function: Tidak mengubah input (immutable), deterministik."""
    return [x * factor for x in data]


global_counter = 0


def impure_transform(data: List[int], factor: int) -> List[int]:
    """Impure Function: Memiliki efek samping (side effect) mutasi variabel global."""
    global global_counter
    global_counter += 1
    return [x * factor + global_counter for x in data]


# ============================================================================
# 3. Higher-Order Functions (HOF) & Combinators
# ============================================================================
def scala_fold_left(lst: List[T], zero: U, op: Callable[[U, T], U]) -> U:
    """Simulasi Scala: List.foldLeft(zero)(op)"""
    acc = zero
    for elem in lst:
        acc = op(acc, elem)
    return acc


def scala_filter(lst: List[T], predicate: Callable[[T], bool]) -> List[T]:
    """Simulasi Scala: List.filter(p)"""
    return [x for x in lst if predicate(x)]


def scala_map(lst: List[T], f: Callable[[T], U]) -> List[U]:
    """Simulasi Scala: List.map(f)"""
    return [f(x) for x in lst]


# ============================================================================
# 4. Currying & Partial Application
# ============================================================================
def curried_discount(rate: float) -> Callable[[float], float]:
    """Simulasi Scala: def applyDiscount(rate: Double)(price: Double): Double"""
    def apply_price(price: float) -> float:
        return price * (1.0 - rate)
    return apply_price


# ============================================================================
# 5. Tail Recursion Simulation
# ============================================================================
def tail_rec_factorial(n: int, accumulator: int = 1) -> int:
    """Simulasi Scala @annotation.tailrec def factorial(n: Int, acc: BigInt): BigInt"""
    if n <= 1:
        return accumulator
    return tail_rec_factorial(n - 1, n * accumulator)


# ============================================================================
# Interactive CLI Showcase
# ============================================================================
def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{BLUE}>>> {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def demo_pure_vs_impure() -> None:
    print_header("1. Pure Functions & Referential Transparency")
    sample = [1, 2, 3]
    print(f"Data Awal: {sample}")

    print(f"\n{MAGENTA}[Uji Pure Function]{RESET}")
    res1 = pure_transform(sample, 2)
    res2 = pure_transform(sample, 2)
    print(f"Panggilan ke-1: {res1}")
    print(f"Panggilan ke-2: {res2}")
    print(f"Status: {GREEN}Referential Transparency Terpenuhi (Hasil Identik Tanpa Side-Effect){RESET}")

    print(f"\n{MAGENTA}[Uji Impure Function]{RESET}")
    res_imp1 = impure_transform(sample, 2)
    res_imp2 = impure_transform(sample, 2)
    print(f"Panggilan ke-1: {res_imp1}")
    print(f"Panggilan ke-2: {res_imp2}")
    print(f"Status: {RED}Gagal Referential Transparency (Output Berubah Karena Mutasi Global){RESET}")


def demo_hof_combinators() -> None:
    print_header("2. Higher-Order Functions: map, filter, foldLeft")
    numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    print(f"List input: {numbers}")

    evens = scala_filter(numbers, lambda x: x % 2 == 0)
    print(f"1. {YELLOW}filter(_ % 2 == 0){RESET}   -> {evens}")

    squared = scala_map(evens, lambda x: x ** 2)
    print(f"2. {YELLOW}map(_ ^ 2){RESET}            -> {squared}")

    total = scala_fold_left(squared, 0, lambda acc, x: acc + x)
    print(f"3. {YELLOW}foldLeft(0)(_ + _){RESET}     -> Total: {BOLD}{GREEN}{total}{RESET}")


def demo_currying() -> None:
    print_header("3. Currying & Partial Application")
    print("Mendefinisikan curried discount function: def discount(rate)(price)")

    vip_discount = curried_discount(0.20)      # Diskon 20%
    regular_discount = curried_discount(0.05)  # Diskon 5%

    item_price = 100_000.0
    print(f"Harga Dasar: Rp {item_price:,.2f}")
    print(f"VIP Member (-20%)    : Rp {BOLD}{GREEN}{vip_discount(item_price):,.2f}{RESET}")
    print(f"Regular Member (-5%) : Rp {BOLD}{CYAN}{regular_discount(item_price):,.2f}{RESET}")


def demo_adt_pattern_matching() -> None:
    print_header("4. ADT (Option[T]) & Pattern Matching")
    database = {"usr_101": "Budi Santoso", "usr_102": "Siti Nurhaliza"}

    def find_user(user_id: str) -> Option[str]:
        if user_id in database:
            return Some(database[user_id])
        return NONE

    queries = ["usr_101", "usr_999"]
    for q in queries:
        result = find_user(q)
        print(f"Pencarian ID '{q}':")
        print(f"  Tipe Monad : {result}")
        print(f"  Evaluasi   : {pattern_match_option(result)}")

        # Monadic transformation: map
        uppercase_result = result.map(lambda name: name.upper())
        print(f"  After map  : {uppercase_result.get_or_else('N/A (TIDAK DITEMUKAN)')}\n")


def demo_tail_recursion() -> None:
    print_header("5. Tail Recursion Simulation")
    test_values = [5, 10, 15]
    for val in test_values:
        res = tail_rec_factorial(val)
        print(f"Factorial({val}) via Tail-Rec Accumulator: {BOLD}{GREEN}{res}{RESET}")


def run_all_demos() -> None:
    print(f"{BOLD}{GREEN}=== SIMULASI KONSEP FONDASI PEMROGRAMAN FUNGSIONAL (SCALA) ==={RESET}")
    demo_pure_vs_impure()
    demo_hof_combinators()
    demo_currying()
    demo_adt_pattern_matching()
    demo_tail_recursion()
    print(f"\n{BOLD}{GREEN}=== SEMUA DEMO SELESAI DIEKSEKUSI SECARA VALID ==={RESET}\n")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "--auto"):
        run_all_demos()
        return

    while True:
        print(f"\n{BOLD}Pilih Modul Simulasi FP Scala:{RESET}")
        print("1. Pure Functions & Referential Transparency")
        print("2. Higher-Order Functions (map, filter, foldLeft)")
        print("3. Currying & Partial Application")
        print("4. ADT & Pattern Matching (Option: Some/None)")
        print("5. Tail Recursion (Factorial Accumulator)")
        print("6. Jalankan Semua Simulasi")
        print("0. Keluar")

        try:
            choice = input(f"{CYAN}Pilihan [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break

        if choice == "1":
            demo_pure_vs_impure()
        elif choice == "2":
            demo_hof_combinators()
        elif choice == "3":
            demo_currying()
        elif choice == "4":
            demo_adt_pattern_matching()
        elif choice == "5":
            demo_tail_recursion()
        elif choice == "6":
            run_all_demos()
        elif choice == "0":
            print(f"{GREEN}Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Masukkan angka 0-6.{RESET}")


if __name__ == "__main__":
    main()
