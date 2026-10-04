#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Functional Programming & Lambdas ala Kotlin
Materi: BAB-03 - Functional Programming & Lambdas (Kotlin Core Concept Simulator)

Topik yang disimulasikan:
1. Higher-Order Functions (HOF) & Function Types ((T) -> R)
2. Kotlin Scope Functions Matrix: let, run, with, apply, also
3. Lambda with Receiver (T.() -> R) & Type-Safe Builder DSL
4. Inline Functions, Noinline, dan Non-Local Returns
5. Collections vs Sequence (Eager vs Lazy Pipeline Evaluation)
"""

import sys
import time
from typing import Callable, TypeVar, Generic, Any, List, Optional, Generator

T = TypeVar("T")
R = TypeVar("R")

# ==============================================================================
# ANSI Color Palette & Formatting Helpers
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === [ {title} ] === {Color.RESET}")


def subheader(text: str) -> None:
    print(f"{Color.CYAN}{Color.BOLD}>>> {text}{Color.RESET}")


def success(msg: str) -> None:
    print(f"  {Color.GREEN}✔ [OK]{Color.RESET} {msg}")


def info(label: str, val: Any) -> None:
    print(f"  {Color.YELLOW}● {label}:{Color.RESET} {Color.WHITE}{val}{Color.RESET}")


def code_trace(step: str, detail: str) -> None:
    print(f"    {Color.MAGENTA}↳ [{step}]{Color.RESET} {Color.DIM}{detail}{Color.RESET}")


# ==============================================================================
# 1. Higher-Order Functions (HOF) & Currying
# ==============================================================================
def kotlin_transformer(items: List[T], transform: Callable[[T], R]) -> List[R]:
    """Simulasi HOF Kotlin: fun <T, R> List<T>.customTransform(transform: (T) -> R): List<R>"""
    result: List[R] = []
    for item in items:
        mapped = transform(item)
        code_trace("HOF Exec", f"Input: {item} -> Output: {mapped}")
        result.append(mapped)
    return result


def make_multiplier(factor: int) -> Callable[[int], int]:
    """Simulasi returning a function: fun makeMultiplier(factor: Int): (Int) -> Int"""
    return lambda x: x * factor


# ==============================================================================
# 2. Kotlin Scope Functions Simulator
# ==============================================================================
class ScopeWrapper(Generic[T]):
    """
    Wrapper untuk mengemulasikan 5 Scope Functions utama Kotlin pada sembarang object:
    - let   : pass `it` (argument), return result lambda
    - also  : pass `it` (argument), return object ini (this)
    - apply : execute lambda with `this`, return object ini (this)
    - run   : execute lambda with `this`, return result lambda
    """
    def __init__(self, value: T):
        self._value = value

    @property
    def value(self) -> T:
        return self._value

    def let(self, block: Callable[[T], R]) -> R:
        """Kotlin: inline fun <T, R> T.let(block: (T) -> R): R"""
        return block(self._value)

    def also(self, block: Callable[[T], None]) -> "ScopeWrapper[T]":
        """Kotlin: inline fun <T> T.also(block: (T) -> Unit): T"""
        block(self._value)
        return self

    def apply(self, block: Callable[[T], None]) -> "ScopeWrapper[T]":
        """Kotlin: inline fun <T> T.apply(block: T.() -> Unit): T"""
        block(self._value)
        return self

    def run(self, block: Callable[[T], R]) -> R:
        """Kotlin: inline fun <T, R> T.run(block: T.() -> R): R"""
        return block(self._value)


def kotlin_with(receiver: T, block: Callable[[T], R]) -> R:
    """Kotlin: inline fun <T, R> with(receiver: T, block: T.() -> R): R"""
    return block(receiver)


class UserProfile:
    def __init__(self, username: str = "", email: str = "", active: bool = False):
        self.username = username
        self.email = email
        self.active = active

    def __repr__(self) -> str:
        return f"UserProfile(username='{self.username}', email='{self.email}', active={self.active})"


# ==============================================================================
# 3. Lambda with Receiver (T.() -> Unit) & Type-Safe Builder DSL
# ==============================================================================
class SqlQueryBuilder:
    """Emulasi Kotlin Type-Safe Query Builder DSL"""
    def __init__(self):
        self._table: str = ""
        self._columns: List[str] = []
        self._conditions: List[str] = []
        self._limit: Optional[int] = None

    def from_table(self, table: str) -> None:
        self._table = table

    def select(self, *columns: str) -> None:
        self._columns.extend(columns)

    def where(self, condition: str) -> None:
        self._conditions.append(condition)

    def limit(self, count: int) -> None:
        self._limit = count

    def build(self) -> str:
        cols = ", ".join(self._columns) if self._columns else "*"
        query = f"SELECT {cols} FROM {self._table}"
        if self._conditions:
            query += " WHERE " + " AND ".join(self._conditions)
        if self._limit is not None:
            query += f" LIMIT {self._limit}"
        return query


def build_sql(block: Callable[[SqlQueryBuilder], None]) -> str:
    """Kotlin: fun buildSql(init: SqlQueryBuilder.() -> Unit): String"""
    builder = SqlQueryBuilder()
    block(builder)  # In Kotlin, inside block, methods are invoked on 'this'
    return builder.build()


# ==============================================================================
# 4. Inline Functions & Non-Local Return Simulation
# ==============================================================================
class NonLocalReturn(Exception):
    """Exception khusus untuk merepresentasikan non-local return dari lambda inline"""
    def __init__(self, return_value: Any):
        self.return_value = return_value


def inline_for_each(items: List[T], action: Callable[[T], None]) -> None:
    """
    Kotlin inline function: body di-inline langsung ke caller site.
    Mendukung non-local return yang keluar dari enclosing function.
    """
    for item in items:
        action(item)


def search_with_non_local_return(items: List[int], target: int) -> str:
    """Simulasi fungsi Kotlin yang melakukan early return langsung dari lambda"""
    try:
        def lambda_body(x: int):
            code_trace("Inline Loop", f"Mengecek nilai: {x}")
            if x == target:
                code_trace("Non-Local Return Triggered", f"Menemukan target {target}!")
                raise NonLocalReturn(f"FOUND_{target}")

        inline_for_each(items, lambda_body)
    except NonLocalReturn as ret:
        return ret.return_value
    return "NOT_FOUND"


# ==============================================================================
# 5. Eager Collections vs Lazy Sequence Simulator
# ==============================================================================
class KotlinSequence(Generic[T]):
    """Simulasi Kotlin Sequence (Lazy Pipeline) vs List (Eager)"""
    def __init__(self, generator_factory: Callable[[], Generator[T, None, None]]):
        self._factory = generator_factory

    @classmethod
    def of(cls, items: List[T]) -> "KotlinSequence[T]":
        def gen():
            for item in items:
                yield item
        return cls(gen)

    def filter(self, predicate: Callable[[T], bool]) -> "KotlinSequence[T]":
        parent_gen = self._factory
        def gen():
            for item in parent_gen():
                code_trace("Sequence.filter", f"Evaluasi predikat untuk: {item}")
                if predicate(item):
                    yield item
        return KotlinSequence(gen)

    def map(self, transform: Callable[[T], R]) -> "KotlinSequence[R]":
        parent_gen = self._factory
        def gen():
            for item in parent_gen():
                code_trace("Sequence.map", f"Transformasi nilai: {item}")
                yield transform(item)
        return KotlinSequence(gen)

    def take(self, n: int) -> "KotlinSequence[T]":
        parent_gen = self._factory
        def gen():
            count = 0
            for item in parent_gen():
                if count >= n:
                    break
                count += 1
                yield item
        return KotlinSequence(gen)

    def to_list(self) -> List[T]:
        code_trace("Sequence Terminal Op", "toList() memicu pipeline streaming")
        return list(self._factory())


# ==============================================================================
# Demo Runner & Interactive CLI Menu
# ==============================================================================
def demo_higher_order_functions():
    header("1. HIGHER-ORDER FUNCTIONS (HOF) & FIRST-CLASS FUNCTIONS")
    subheader("Simulasi passing lambda sebagai parameter dan returning function:")
    
    numbers = [1, 2, 3, 4, 5]
    info("Input Awal", numbers)
    
    # Lambda kuadrat
    squared = kotlin_transformer(numbers, lambda x: x * x)
    success(f"Hasil transformer (x * x): {squared}")
    
    # Returning closure
    times_ten = make_multiplier(10)
    scaled = kotlin_transformer(numbers, times_ten)
    success(f"Hasil multiplier closure (x * 10): {scaled}")


def demo_scope_functions():
    header("2. KOTLIN SCOPE FUNCTIONS MATRIX (let, also, apply, run, with)")
    subheader("Membedakan Receiver ('this') vs Argument ('it') dan Return Value")

    # 1. apply: inisialisasi object, mengembalikan object itu sendiri ('this')
    user = ScopeWrapper(UserProfile()).apply(lambda it: (
        setattr(it, "username", "alex_kotlin"),
        setattr(it, "email", "alex@kotlinlang.org"),
        setattr(it, "active", True)
    )).value
    success(f"apply() inisialisasi: {user}")

    # 2. also: side-effect logging/validasi, mengembalikan object ('this')
    ScopeWrapper(user).also(lambda it: info("also() Logging Side Effect", f"User registered with email: {it.email}"))

    # 3. let: scoping null-safety / transformasi, return lambda result
    formatted_card = ScopeWrapper(user).let(lambda it: f"ID_CARD: {it.username.upper()} <{it.email}>")
    success(f"let() return transformasi: '{formatted_card}'")

    # 4. run: eksekusi blok kode dengan context, return lambda result
    summary = ScopeWrapper(user).run(lambda it: f"Status: {'ACTIVE' if it.active else 'INACTIVE'}")
    success(f"run() return hasil kalkulasi: {summary}")

    # 5. with: receiver dioper sebagai argumen fungsi
    intro = kotlin_with(user, lambda it: f"Halo, saya {it.username}!")
    success(f"with() return: '{intro}'")


def demo_type_safe_dsl():
    header("3. LAMBDA WITH RECEIVER & TYPE-SAFE BUILDER DSL")
    subheader("Simulasi konstruksi DSL Kotlin: buildSql { ... }")

    # Emulasi DSL di mana method dipanggil langsung pada builder
    query = build_sql(lambda b: (
        b.from_table("users"),
        b.select("id", "username", "status"),
        b.where("status = 'ACTIVE'"),
        b.where("score >= 80"),
        b.limit(10)
    ))
    
    info("Generated SQL Query via DSL", query)
    assert "SELECT id, username, status FROM users WHERE status = 'ACTIVE' AND score >= 80 LIMIT 10" == query
    success("Type-safe builder DSL query berhasil divalidasi!")


def demo_inline_and_non_local_return():
    header("4. INLINE FUNCTIONS & NON-LOCAL RETURNS")
    subheader("Simulasi early return dari dalam loop lambda menggunakan inline concept")

    dataset = [12, 45, 78, 99, 130, 250]
    info("Dataset Angka", dataset)
    
    res1 = search_with_non_local_return(dataset, 99)
    success(f"Pencarian target 99: {res1}")

    res2 = search_with_non_local_return(dataset, 999)
    success(f"Pencarian target 999: {res2}")


def demo_eager_vs_lazy_pipeline():
    header("5. EAGER (COLLECTIONS) VS LAZY (SEQUENCE) PIPELINE")
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    info("Input Elements", data)

    print(f"\n{Color.YELLOW}[A] EAGER (List Processing) - Tiap tahap memproses seluruh item:{Color.RESET}")
    # Eager approach
    t0 = time.perf_counter()
    step1 = [x for x in data if x % 2 != 0]
    step2 = [x * 2 for x in step1]
    eager_result = step2[:2]
    t1 = time.perf_counter()
    info("Eager Output", eager_result)

    print(f"\n{Color.CYAN}[B] LAZY (Kotlin Sequence) - On-demand streaming per item:{Color.RESET}")
    seq = (
        KotlinSequence.of(data)
        .filter(lambda x: x % 2 != 0)
        .map(lambda x: x * 2)
        .take(2)
    )
    lazy_result = seq.to_list()
    info("Lazy Output", lazy_result)
    assert eager_result == lazy_result
    success(f"Hasil Eager dan Lazy Identik: {lazy_result}")


def run_full_suite():
    print(f"{Color.BOLD}{Color.MAGENTA}" + "=" * 68)
    print(" KOTLIN BAB-03: FUNCTIONAL PROGRAMMING & LAMBDAS LAB EXERCISE")
    print("=" * 68 + f"{Color.RESET}")
    
    demo_higher_order_functions()
    demo_scope_functions()
    demo_type_safe_dsl()
    demo_inline_and_non_local_return()
    demo_eager_vs_lazy_pipeline()

    print(f"\n{Color.BG_MAGENTA}{Color.WHITE}{Color.BOLD} SEMUA SIMULASI TEKNIS KOTLIN FP SELESAI DENGAN SUKSES! {Color.RESET}\n")


def interactive_menu():
    while True:
        print(f"\n{Color.CYAN}{Color.BOLD}=== PILIHAN SIMULASI INTERAKTIF ==={Color.RESET}")
        print("1. Higher-Order Functions (HOF)")
        print("2. Scope Functions Matrix (let, also, apply, run, with)")
        print("3. Lambda with Receiver (Type-Safe Builder DSL)")
        print("4. Inline Functions & Non-Local Returns")
        print("5. Eager Collections vs Lazy Sequence")
        print("6. Jalankan Semua Modul (Full Suite)")
        print("0. Keluar")
        
        try:
            choice = input(f"{Color.GREEN}Pilih menu [0-6]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            demo_higher_order_functions()
        elif choice == "2":
            demo_scope_functions()
        elif choice == "3":
            demo_type_safe_dsl()
        elif choice == "4":
            demo_inline_and_non_local_return()
        elif choice == "5":
            demo_eager_vs_lazy_pipeline()
        elif choice == "6":
            run_full_suite()
        elif choice == "0":
            print(f"{Color.YELLOW}Selesai. Sampai jumpa!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_menu()
    else:
        run_full_suite()
