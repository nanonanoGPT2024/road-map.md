#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif C# Modern Type System & OOP Kontemporer
Topik Bahasan C# Modern:
 1. Record & Non-Destructive Mutation (with-expressions & value equality)
 2. Pattern Matching C# Modern (Relational, Property, & Type Patterns)
 3. Nullable Reference Types (NRT) & Null-Safety Lifecycle
 4. Value vs Reference Semantics (Struct vs Class Stack/Heap Emulation)
 5. Primary Constructors & Init-Only Properties
"""

import sys
import copy
from dataclasses import dataclass
from typing import Any, Optional, Union


# --- ANSI Color Utilities ---
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


def header(text: str):
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === [C# SIM] {text} === {Color.RESET}\n")


def subheader(text: str):
    print(f"{Color.CYAN}{Color.BOLD}>>> {text}{Color.RESET}")


def info(msg: str):
    print(f" {Color.BLUE}i{Color.RESET} {msg}")


def success(msg: str):
    print(f" {Color.GREEN}✓{Color.RESET} {Color.GREEN}{msg}{Color.RESET}")


def warning(msg: str):
    print(f" {Color.YELLOW}▲{Color.RESET} {Color.YELLOW}{msg}{Color.RESET}")


def code_box(code: str, label: str = "C# Equivalent Code"):
    print(f"{Color.DIM}┌── {label} " + "─" * (55 - len(label)) + "┐")
    for line in code.strip().split("\n"):
        print(f"│  {Color.WHITE}{line:<53}{Color.DIM}│")
    print("└" + "─" * 60 + f"┘{Color.RESET}")


# ==============================================================================
# 1. EMULASI RECORD & NON-DESTRUCTIVE MUTATION ('with' expression)
# ==============================================================================
@dataclass(frozen=True)
class CustomerRecord:
    id: int
    name: str
    tier: str
    balance: float

    def with_mutation(self, **kwargs) -> "CustomerRecord":
        """Simulasi C# 'record with { Prop = newVal }'"""
        current_data = {
            "id": self.id,
            "name": self.name,
            "tier": self.tier,
            "balance": self.balance
        }
        current_data.update(kwargs)
        return CustomerRecord(**current_data)


def demo_records():
    header("1. C# RECORD & VALUE EQUALITY VS CLASS REFERENCE EQUALITY")
    code_box("""public record Customer(int Id, string Name, string Tier, decimal Balance);
var c1 = new Customer(1, "Alice", "Gold", 1500m);
var c2 = c1 with { Balance = 2000m };
bool same = (c1 == c2); // Value-based equality""", "C# Record Syntax")

    c1 = CustomerRecord(1, "Alice", "Gold", 1500.0)
    c2 = CustomerRecord(1, "Alice", "Gold", 1500.0)
    c3 = c1.with_mutation(balance=2000.0)

    info(f"Instance c1: {Color.MAGENTA}{c1}{Color.RESET}")
    info(f"Instance c2: {Color.MAGENTA}{c2}{Color.RESET} (Data identik dengan c1)")
    info(f"Instance c3: {Color.MAGENTA}{c3}{Color.RESET} (Hasil mutasi 'with')")

    print()
    if c1 == c2:
        success("c1 == c2 bernilai TRUE! (Value Equality: properti bernilai identik)")
    else:
        warning("c1 != c2")

    info(f"Identity memori c1 vs c2 (id(c1) == id(c2)): {Color.YELLOW}{id(c1) == id(c2)}{Color.RESET}")
    info(f"Verifikasi immutability: atribut c1 tidak berubah setelah c3 dibuat.")


# ==============================================================================
# 2. EMULASI MODERN PATTERN MATCHING & SWITCH EXPRESSION
# ==============================================================================
@dataclass
class Transaction:
    amount: float
    is_international: bool
    user_status: str  # "Vip", "Standard", "Suspended"


def evaluate_transaction_fee(tx: Transaction) -> tuple[float, str]:
    """
    Simulasi C# Switch Expression dengan Relational & Property Pattern:
    fee = tx switch {
        { user_status: "Suspended" } => throw SecurityException(),
        { is_international: true, amount: > 1000 } => tx.amount * 0.05m,
        { is_international: true } => tx.amount * 0.03m,
        { user_status: "Vip" } => 0m,
        { amount: <= 100 } => 1.5m,
        _ => tx.amount * 0.015m
    };
    """
    match tx:
        case Transaction(user_status="Suspended"):
            return -1.0, "REJECTED (Account Suspended - Guard Clause Pattern)"
        case Transaction(is_international=True, amount=amt) if amt > 1000:
            return amt * 0.05, "5.0% (International High Value > $1,000)"
        case Transaction(is_international=True, amount=amt):
            return amt * 0.03, "3.0% (International Standard)"
        case Transaction(user_status="Vip", amount=_):
            return 0.0, "0.0% (VIP Tier Waived Fee)"
        case Transaction(amount=amt) if amt <= 100:
            return 1.5, "$1.50 Flat Fee (Micro-transaction <= $100)"
        case Transaction(amount=amt):
            return amt * 0.015, "1.5% (Domestic Standard Default)"
        case _:
            return 0.0, "Unmatched pattern"


def demo_pattern_matching():
    header("2. C# PATTERN MATCHING & SWITCH EXPRESSIONS")
    code_box("""decimal fee = tx switch {
    { user_status: "Suspended" } => throw new BlockedException(),
    { is_international: true, amount: > 1000 } => tx.amount * 0.05m,
    { user_status: "Vip" } => 0m,
    _ => tx.amount * 0.015m
};""", "C# Relational & Property Pattern")

    test_cases = [
        Transaction(1500.0, True, "Standard"),
        Transaction(50.0, False, "Standard"),
        Transaction(800.0, False, "Vip"),
        Transaction(250.0, False, "Suspended"),
        Transaction(500.0, False, "Standard"),
    ]

    for idx, tx in enumerate(test_cases, 1):
        fee, reason = evaluate_transaction_fee(tx)
        color = Color.RED if fee < 0 else Color.GREEN
        fee_str = f"${fee:,.2f}" if fee >= 0 else "N/A"
        print(f" {Color.BOLD}[Kasus {idx}]{Color.RESET} Tx(Amount=${tx.amount}, Int'l={tx.is_international}, Status={tx.user_status})")
        print(f"   └──> Fee: {color}{fee_str:<8}{Color.RESET} | Rule: {Color.CYAN}{reason}{Color.RESET}")


# ==============================================================================
# 3. NULLABLE REFERENCE TYPES (NRT) & DEFENSIVE LIFECYCLE
# ==============================================================================
class SafeUserRepository:
    def __init__(self):
        self._db = {101: "Budi Santoso", 102: "Dewi Lestari"}

    # Simulasi return type: string? (Nullable Reference Type)
    def find_user_by_id(self, uid: int) -> Optional[str]:
        return self._db.get(uid, None)


def demo_nullable_reference_types():
    header("3. NULLABLE REFERENCE TYPES (NRT) & OPERATOR ?.")
    code_box("""#nullable enable
string? name = repo.FindUserById(id);
// Null-conditional operator (?.) & null-coalescing (??)
int length = name?.Length ?? 0;
Console.WriteLine(name?.ToUpper() ?? "[USER NOT FOUND]");""", "C# NRT & Operators (?., ??)")

    repo = SafeUserRepository()

    for uid in [101, 999]:
        user_opt: Optional[str] = repo.find_user_by_id(uid)
        info(f"Query User ID {uid}...")

        # Safe navigation (?.) and Null Coalescing (??)
        display_name = user_opt.upper() if user_opt is not None else "[USER NOT FOUND]"
        str_len = len(user_opt) if user_opt is not None else 0

        if user_opt is not None:
            success(f"Ditemukan: {Color.BOLD}{display_name}{Color.RESET} (Panjang: {str_len} char)")
        else:
            warning(f"Null Terdeteksi! Fallback aman: {Color.RED}{display_name}{Color.RESET} (Panjang: {str_len})")


# ==============================================================================
# 4. VALUE TYPE (STRUCT) VS REFERENCE TYPE (CLASS) MEMORY SEMANTICS
# ==============================================================================
class ReferenceTypeClass:
    """Emulasi C# Class (Alokasi Heap, passing by reference pointer)"""
    def __init__(self, val: int):
        self.val = val


@dataclass
class ValueTypeStruct:
    """Emulasi C# Struct (Alokasi Stack, passing by value-copy)"""
    val: int


def mutate_class(obj: ReferenceTypeClass):
    obj.val += 100


def mutate_struct_simulation(st: ValueTypeStruct):
    # Simulasi passing struct di C# tanpa keyword 'ref'/'in'
    local_copy = copy.deepcopy(st)
    local_copy.val += 100
    return local_copy


def demo_value_vs_reference():
    header("4. VALUE TYPE (STRUCT) VS REFERENCE TYPE (CLASS) SEMANTICS")
    code_box("""// C# struct (Value Type di Stack) vs class (Reference Type di Heap)
struct PointStruct { public int Val; }
class PointClass { public int Val; }

void Modify(PointStruct s, PointClass c) {
    s.Val += 100; // Hanya mengubah local copy!
    c.Val += 100; // Mengubah instance di heap asli!
}""", "C# Memory Model")

    c = ReferenceTypeClass(10)
    s = ValueTypeStruct(10)

    info(f"Nilai Awal Class (Heap Ref)  : val = {c.val}")
    info(f"Nilai Awal Struct (Stack Val): val = {s.val}")

    print(f"\n{Color.DIM}--- Mengeksekusi fungsi modifikasi tanpa keyword 'ref' ---{Color.RESET}")
    mutate_class(c)
    _ = mutate_struct_simulation(s)

    print()
    if c.val == 110:
        success(f"Class (Reference Type) BERUBAH menjadi: {Color.BOLD}{c.val}{Color.RESET} (Caller terdampak)")
    if s.val == 10:
        success(f"Struct (Value Type) TETAP bernilai     : {Color.BOLD}{s.val}{Color.RESET} (Caller aman, copy-on-pass)")


# ==============================================================================
# 5. MENU INTERAKTIF
# ==============================================================================
def run_interactive():
    menu_text = f"""
{Color.BOLD}{Color.WHITE}Pilih Simulasi Konsep C# Modern (BAB 02):{Color.RESET}
  {Color.CYAN}1{Color.RESET}. Record & Non-Destructive Mutation (with-expression)
  {Color.CYAN}2{Color.RESET}. Modern Pattern Matching & Switch Expression
  {Color.CYAN}3{Color.RESET}. Nullable Reference Types & Safe Navigation
  {Color.CYAN}4{Color.RESET}. Struct vs Class (Value Type vs Reference Type Semantics)
  {Color.CYAN}5{Color.RESET}. Jalankan Semua Simulasi Berurutan
  {Color.RED}0{Color.RESET}. Keluar
"""
    while True:
        print(menu_text)
        try:
            choice = input(f"{Color.YELLOW}Masukkan pilihan (0-5) [Enter untuk run all]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari lab.")
            break

        if choice in ("", "5"):
            demo_records()
            demo_pattern_matching()
            demo_nullable_reference_types()
            demo_value_vs_reference()
            print(f"\n{Color.BG_GREEN}{Color.WHITE}{Color.BOLD} SEMUA DEMO SELESAI DIEKSEKUSI! {Color.RESET}\n")
            break
        elif choice == "1":
            demo_records()
        elif choice == "2":
            demo_pattern_matching()
        elif choice == "3":
            demo_nullable_reference_types()
        elif choice == "4":
            demo_value_vs_reference()
        elif choice == "0":
            print("Keluar dari lab.")
            break
        else:
            warning("Pilihan tidak valid, silakan ulangi.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_records()
        demo_pattern_matching()
        demo_nullable_reference_types()
        demo_value_vs_reference()
    else:
        # Jalankan default interaktif atau auto jika non-interactive terminal
        if not sys.stdin.isatty():
            demo_records()
            demo_pattern_matching()
            demo_nullable_reference_types()
            demo_value_vs_reference()
        else:
            run_interactive()
