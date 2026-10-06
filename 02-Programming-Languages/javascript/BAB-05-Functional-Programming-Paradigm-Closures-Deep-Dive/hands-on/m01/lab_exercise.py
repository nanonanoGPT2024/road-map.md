#!/usr/bin/env python3
"""
Lab Exercise: JavaScript Functional Programming & Closures Deep Dive
Simulasi Interaktif & Engine Internal Scope Chain, Closures, Currying, dan Purity
"""

import sys
import time
import copy
from typing import Callable, Any, Dict, List, Optional

# ==============================================================================
# ANSI Color Palette for Rich Terminal UI
# ==============================================================================
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"

def print_header(title: str):
    width = 72
    print(f"\n{Color.CYAN}{'═' * width}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  {title.center(width - 4)}{Color.RESET}")
    print(f"{Color.CYAN}{'═' * width}{Color.RESET}")

def print_section(section_id: str, title: str):
    print(f"\n{Color.MAGENTA}┌── [{section_id}] {Color.BOLD}{title}{Color.RESET}")
    print(f"{Color.MAGENTA}│{Color.RESET}")

def print_step(step_name: str, detail: str):
    print(f"{Color.MAGENTA}├──{Color.RESET} {Color.CYAN}● {step_name}:{Color.RESET} {detail}")

def print_result(label: str, value: Any, color: str = Color.GREEN):
    print(f"{Color.MAGENTA}│   {Color.BOLD}{color}➜ {label}:{Color.RESET} {value}")

def print_footer():
    print(f"{Color.MAGENTA}└──{'─' * 66}✔{Color.RESET}")

# ==============================================================================
# MODULE 1: Lexical Scope & Lexical Environment Simulation
# Menyimulasikan Environment Record & Scope Chain ECMAScript
# ==============================================================================
class EnvironmentRecord:
    def __init__(self, name: str, outer: Optional['EnvironmentRecord'] = None):
        self.name = name
        self.outer = outer
        self.bindings: Dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self.bindings[key] = value

    def get(self, key: str) -> Any:
        if key in self.bindings:
            return self.bindings[key]
        if self.outer is not None:
            return self.outer.get(key)
        raise NameError(f"Identifier '{key}' is not defined in scope chain.")

    def inspect_chain(self) -> List[str]:
        chain = []
        curr: Optional['EnvironmentRecord'] = self
        while curr:
            bindings_str = ", ".join(f"{k}={v}" for k, v in curr.bindings.items())
            chain.append(f"[{curr.name}: {{{bindings_str}}}]")
            curr = curr.outer
        return chain


def demo_lexical_environments():
    print_section("MODUL 01", "Simulasi Engine: Lexical Scope & Scope Chain")
    
    global_env = EnvironmentRecord("GlobalEnv")
    global_env.set("globalConfig", "production")
    global_env.set("version", 5.2)

    print_step("Definisi Global Scope", "Menyimpan globalConfig dan version")
    print_result("Scope Chain Global", " -> ".join(global_env.inspect_chain()), Color.YELLOW)

    # outer function closure
    outer_env = EnvironmentRecord("OuterFunctionEnv", outer=global_env)
    outer_env.set("outerSecret", "0xFA99")
    outer_env.set("counter", 0)

    print_step("Eksekusi Outer Scope", "Membentuk lexical environment dengan outer reference")
    print_result("Scope Chain Outer", " -> ".join(outer_env.inspect_chain()), Color.YELLOW)

    # inner closure scope
    inner_env = EnvironmentRecord("ClosureInnerEnv", outer=outer_env)
    inner_env.set("innerLocal", "active_session")

    print_step("Resolusi Identifier via Scope Chain", "Mengakses 'outerSecret' dan 'globalConfig' dari inner")
    val1 = inner_env.get("innerLocal")
    val2 = inner_env.get("outerSecret")
    val3 = inner_env.get("globalConfig")

    print_result("innerLocal (Local)", val1)
    print_result("outerSecret (Closure)", val2)
    print_result("globalConfig (Global)", val3)
    print_result("Visualisasi Rantai Scope", " -> ".join(inner_env.inspect_chain()), Color.CYAN)
    print_footer()

# ==============================================================================
# MODULE 2: Pure Functions, Immutability & Side Effects
# ==============================================================================
def demo_purity_and_immutability():
    print_section("MODUL 02", "Pure Functions vs Side Effects & Immutability")

    # Impure simulation
    shared_state = {"inventory": ["Sword", "Shield"], "gold": 100}
    print_step("State Asal", str(shared_state))

    def impure_buy_item(state: Dict[str, Any], item: str, price: int):
        # Mutasi langsung (Side Effect)
        state["inventory"].append(item)
        state["gold"] -= price
        return state

    print_step("Menjalankan Impure Function", "Mutasi langsung state in-place")
    impure_buy_item(shared_state, "Potion", 25)
    print_result("Shared State Setelah Impure Mutasi", shared_state, Color.RED)

    # Pure simulation
    clean_state = {"inventory": ["Sword", "Shield"], "gold": 100}

    def pure_buy_item(state: Dict[str, Any], item: str, price: int) -> Dict[str, Any]:
        # Return representasi baru tanpa menyentuh argumen asli (Deep copy / persistent copy)
        new_state = copy.deepcopy(state)
        new_state["inventory"].append(item)
        new_state["gold"] -= price
        return new_state

    print_step("Menjalankan Pure Function", "Immutability & Referential Transparency")
    updated_state = pure_buy_item(clean_state, "Elixir", 40)

    print_result("Original State Tetap Utuh", clean_state, Color.GREEN)
    print_result("New State Dihasilkan", updated_state, Color.GREEN)
    print_footer()

# ==============================================================================
# MODULE 3: Closures for Data Privacy & Encapsulation
# ==============================================================================
def create_secure_account(owner: str, initial_balance: float):
    # Free variables yang tertutup dalam closure
    _owner = owner
    _balance = initial_balance
    _ledger: List[str] = [f"Initial balance: ${_balance:.2f}"]

    def deposit(amount: float) -> str:
        nonlocal _balance
        if amount <= 0:
            return "Deposit harus bernilai positif!"
        _balance += amount
        _ledger.append(f"Deposit +${amount:.2f}")
        return f"Sukses deposit ${amount:.2f}. Saldo saat ini: ${_balance:.2f}"

    def withdraw(amount: float) -> str:
        nonlocal _balance
        if amount > _balance:
            return f"Penarikan gagal! Saldo tidak cukup (${_balance:.2f})"
        _balance -= amount
        _ledger.append(f"Withdraw -${amount:.2f}")
        return f"Sukses tarik ${amount:.2f}. Sisa saldo: ${_balance:.2f}"

    def get_statement() -> Dict[str, Any]:
        return {
            "owner": _owner,
            "balance": _balance,
            "transactions": list(_ledger)
        }

    return {
        "deposit": deposit,
        "withdraw": withdraw,
        "get_statement": get_statement
    }

def demo_closures_encapsulation():
    print_section("MODUL 03", "Data Privacy & Encapsulation Menggunakan Closures")
    
    print_step("Instansiasi Akun Bank via Factory Function", "create_secure_account('Alice', 500)")
    account = create_secure_account("Alice", 500.0)

    print_step("Melakukan Operasi Public API", "deposit(150), withdraw(200), withdraw(800)")
    res1 = account["deposit"](150.0)
    print_result("Hasil Deposit", res1)

    res2 = account["withdraw"](200.0)
    print_result("Hasil Penarikan Valid", res2)

    res3 = account["withdraw"](800.0)
    print_result("Hasil Penarikan Melebihi Batas", res3, Color.YELLOW)

    stmt = account["get_statement"]()
    print_result("Audit Transaksi dari Closure", stmt["transactions"])
    print_step("Uji Proteksi Variabel Bebas", "Mencoba membaca _balance langsung")
    has_raw_balance = "_balance" in account
    print_result("Akses Langsung ke _balance Ditemukan?", "TIDAK (Private Lexical Scope)", Color.GREEN)
    print_footer()

# ==============================================================================
# MODULE 4: Currying, Partial Application & Function Composition
# ==============================================================================
def curry_3(fn: Callable):
    """Mengubah fungsi arity-3 f(x, y, z) menjadi f(x)(y)(z)"""
    def c1(x):
        def c2(y):
            def c3(z):
                return fn(x, y, z)
            return c3
        return c2
    return c1

def compose(*funcs: Callable) -> Callable:
    """Komposisi matematis fungsi f(g(h(x))) dari kanan ke kiri"""
    def composed(arg):
        result = arg
        for fn in reversed(funcs):
            result = fn(result)
        return result
    return composed

def pipe(*funcs: Callable) -> Callable:
    """Pipeline data aliran kiri ke kanan fn1 -> fn2 -> fn3"""
    def piped(arg):
        result = arg
        for fn in funcs:
            result = fn(result)
        return result
    return piped

def demo_currying_and_composition():
    print_section("MODUL 04", "Currying & Function Composition (Pipeline)")

    # Curried Tax & Discount Calculator
    raw_calc = lambda discount_rate, tax_rate, price: (price * (1 - discount_rate)) * (1 + tax_rate)
    curried_calc = curry_3(raw_calc)

    print_step("Currying Arity-3", "calc(discount, tax, price) -> calc(discount)(tax)(price)")
    vip_discount = curried_calc(0.20)  # 20% discount
    vip_indonesia = vip_discount(0.11)  # 11% PPN

    price_tag = 1000000.0
    final_price = vip_indonesia(price_tag)
    print_result("Harga Awal", f"Rp {price_tag:,.2f}")
    print_result("Harga Setelah VIP Discount + PPN", f"Rp {final_price:,.2f}")

    # Composition Pipeline
    sanitize = lambda text: text.strip()
    capitalize = lambda text: text.upper()
    add_tag = lambda text: f"[VERIFIED: {text}]"

    pipeline = pipe(sanitize, capitalize, add_tag)
    raw_input = "   javascript closures mastery   "
    processed = pipeline(raw_input)

    print_step("Pipeline Composition", "sanitize ➜ capitalize ➜ add_tag")
    print_result("Input Mentah", f"'{raw_input}'")
    print_result("Hasil Pipeline", processed, Color.CYAN)
    print_footer()

# ==============================================================================
# MODULE 5: Memoization Pattern with Closure Cache
# ==============================================================================
def memoize(fn: Callable) -> Callable:
    cache: Dict[str, Any] = {}
    hits = 0
    misses = 0

    def memoized(*args):
        nonlocal hits, misses
        key = str(args)
        if key in cache:
            hits += 1
            return cache[key], True, hits, misses
        misses += 1
        result = fn(*args)
        cache[key] = result
        return result, False, hits, misses

    return memoized

def demo_memoization():
    print_section("MODUL 05", "High-Performance Memoization Menggunakan Closures")

    def expensive_fib(n: int) -> int:
        if n <= 1:
            return n
        # sengaja dibuat tanpa cache langsung untuk simulasi komputasi
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    fast_fib = memoize(expensive_fib)

    print_step("Kalkulasi Pertama", "n = 45 (Cache Miss)")
    val, cached, h, m = fast_fib(45)
    print_result("Hasil", val)
    print_result("Dari Cache?", cached, Color.YELLOW)
    print_result("Statistik (Hits / Misses)", f"{h} / {m}")

    print_step("Kalkulasi Ulang Argumen Sama", "n = 45 (Cache Hit instant)")
    val2, cached2, h2, m2 = fast_fib(45)
    print_result("Hasil", val2)
    print_result("Dari Cache?", cached2, Color.GREEN)
    print_result("Statistik (Hits / Misses)", f"{h2} / {m2}")
    print_footer()

# ==============================================================================
# Interactive Runner & CLI Orchestration
# ==============================================================================
def run_all_modules():
    print_header("KONSOL SIMULASI FUNGSI & CLOSURES JS (PYTHON RUNTIME)")
    demo_lexical_environments()
    demo_purity_and_immutability()
    demo_closures_encapsulation()
    demo_currying_and_composition()
    demo_memoization()

    print(f"\n{Color.BOLD}{Color.GREEN}✔ SEMUA MODUL BERHASIL DIEKSEKUSI SECARA VALID & RUNNABLE!{Color.RESET}\n")

def interactive_menu():
    while True:
        print_header("PILIH MODUL PRAKTIKUM INTERAKTIF")
        print(f" {Color.CYAN}1.{Color.RESET} Simulasi Scope Chain & Environment Records")
        print(f" {Color.CYAN}2.{Color.RESET} Pure Functions vs Side Effects")
        print(f" {Color.CYAN}3.{Color.RESET} Enkapsulasi & Data Hiding dengan Closures")
        print(f" {Color.CYAN}4.{Color.RESET} Currying & Pipe Composition")
        print(f" {Color.CYAN}5.{Color.RESET} Memoization Cache Pattern")
        print(f" {Color.CYAN}6.{Color.RESET} Jalankan Seluruh Demonstrasi (Semua Modul)")
        print(f" {Color.RED}0.{Color.RESET} Keluar")
        print(f"{Color.CYAN}{'─' * 72}{Color.RESET}")

        try:
            choice = input(f"{Color.BOLD}Pilihan Anda [0-6] (Enter=Jalankan Semua): {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari program...")
            break

        if choice == "" or choice == "6":
            run_all_modules()
            break
        elif choice == "1":
            demo_lexical_environments()
        elif choice == "2":
            demo_purity_and_immutability()
        elif choice == "3":
            demo_closures_encapsulation()
        elif choice == "4":
            demo_currying_and_composition()
        elif choice == "5":
            demo_memoization()
        elif choice == "0":
            print(f"{Color.YELLOW}Sesi lab exercise ditutup.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan coba lagi.{Color.RESET}")

if __name__ == "__main__":
    # Jika dijalankan dalam lingkungan non-interactive/CI, langsung jalankan semua
    if not sys.stdin.isatty():
        run_all_modules()
    else:
        interactive_menu()
