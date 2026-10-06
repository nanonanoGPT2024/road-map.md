#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Teknis Konsep Fondasi Inti Java
BAB-02: Object-Oriented Engineering & Functional Core
-------------------------------------------------------
Modul ini mensimulasikan mekanisme runtime, paradigma OOP modern,
Functional Interfaces, Stream Pipeline, dan Monad Optional ala Java
secara mandiri dan interaktif.
"""

from __future__ import annotations
import sys
import time
from typing import Callable, Generic, TypeVar, List, Optional as PyOptional
from dataclasses import dataclass

# ANSI Color Escape Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

T = TypeVar("T")
R = TypeVar("R")


def banner(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{YELLOW} [JAVA CORE LAB] :: {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")


def step(label: str, desc: str) -> None:
    print(f"\n{BOLD}{GREEN}[STEP] {label}:{RESET} {desc}")


# ==============================================================================
# 1. OOP Modern: Sealed Hierarchy & Record Pattern (Java 17+)
# ==============================================================================

@dataclass(frozen=True)
class PaymentResult:
    """Simulasi Java Record: Immutable data carrier dengan value equality."""
    transaction_id: str
    amount: float
    status: str


class PaymentMethod:
    """Simulasi Java Sealed Interface: Hierarki kelas tertutup."""
    def process_payment(self, amount: float) -> PaymentResult:
        raise NotImplementedError("Sealed hierarchy member must implement process_payment")


class CreditCardPayment(PaymentMethod):
    def __init__(self, card_number: str, card_holder: str):
        self._card_number = card_number
        self.card_holder = card_holder

    def process_payment(self, amount: float) -> PaymentResult:
        masked = f"****-****-****-{self._card_number[-4:]}"
        print(f"  {BLUE}→ Validasi Kartu Kredit {masked} milik {self.card_holder}...{RESET}")
        return PaymentResult(f"TX-CC-{int(time.time())}", amount, "SUCCESS_SETTLED")


class QrisPayment(PaymentMethod):
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    def process_payment(self, amount: float) -> PaymentResult:
        print(f"  {BLUE}→ Menghasilkan dynamic QRIS Payload untuk Merchant {self.merchant_id}...{RESET}")
        return PaymentResult(f"TX-QR-{int(time.time())}", amount, "SUCCESS_INSTANT")


# ==============================================================================
# 2. Functional Core: Functional Interfaces & Optional Monad
# ==============================================================================

class JavaOptional(Generic[T]):
    """Simulasi java.util.Optional container monad."""
    def __init__(self, value: PyOptional[T]):
        self._value = value

    @staticmethod
    def of(value: T) -> JavaOptional[T]:
        if value is None:
            raise ValueError("NullPointerException simulation: value cannot be None")
        return JavaOptional(value)

    @staticmethod
    def of_nullable(value: PyOptional[T]) -> JavaOptional[T]:
        return JavaOptional(value)

    @staticmethod
    def empty() -> JavaOptional[T]:
        return JavaOptional(None)

    def is_present(self) -> bool:
        return self._value is not None

    def map(self, mapper: Callable[[T], R]) -> JavaOptional[R]:
        if not self.is_present():
            return JavaOptional.empty()
        return JavaOptional.of_nullable(mapper(self._value))  # type: ignore

    def or_else(self, other: T) -> T:
        return self._value if self._value is not None else other


# ==============================================================================
# 3. Stream API Pipeline Simulation (Lazy Evaluation & Immutability)
# ==============================================================================

class JavaStream(Generic[T]):
    """Simulasi lazy evaluation dan intermediate-terminal operations Java Stream."""
    def __init__(self, source: List[T]):
        self._source = list(source)
        self._operations: List[Callable[[list], list]] = []

    @staticmethod
    def of(*items: T) -> JavaStream[T]:
        return JavaStream(list(items))

    def filter(self, predicate: Callable[[T], bool]) -> JavaStream[T]:
        def op(data: list) -> list:
            return [x for x in data if predicate(x)]
        self._operations.append(op)
        return self

    def map(self, mapper: Callable[[T], R]) -> JavaStream[R]:
        def op(data: list) -> list:
            return [mapper(x) for x in data]
        self._operations.append(op)
        return self  # type: ignore

    def collect(self) -> List[T]:
        """Terminal operation yang mengeksekusi pipeline lazy evaluation."""
        result = self._source
        for op in self._operations:
            result = op(result)
        return result

    def reduce(self, identity: T, accumulator: Callable[[T, T], T]) -> T:
        """Terminal operation reduce ala Stream.reduce."""
        items = self.collect()
        current = identity
        for item in items:
            current = accumulator(current, item)
        return current


# ==============================================================================
# Skenario Interaktif & Eksekusi Lab
# ==============================================================================

def run_oop_simulation() -> None:
    banner("1. OOP ENCAPSULATION & POLYMORPHISM DEMO")
    step("Polymorphic Dispatch", "Mengeksekusi runtime polymorphism via Sealed-like Types")

    payments: List[PaymentMethod] = [
        CreditCardPayment("4111222233334567", "Alice Pratama"),
        QrisPayment("MERCHANT-ID-88219"),
    ]

    for p in payments:
        res = p.process_payment(250_000.0)
        print(f"    {GREEN}✔ Record Output:{RESET} ID={res.transaction_id}, "
              f"Amount=Rp {res.amount:,.2f}, Status={BOLD}{res.status}{RESET}")


def run_stream_simulation() -> None:
    banner("2. FUNCTIONAL CORE & STREAM API PIPELINE")
    step("Stream Pipeline", "Filter transaksi > 100k, transform ke label string, dan aggregate sum")

    amounts = [50_000, 150_000, 25_000, 300_000, 75_000, 500_000]
    print(f"  {YELLOW}Dataset input transaksi: {amounts}{RESET}")

    # Java: amounts.stream().filter(a -> a >= 100_000).map(a -> a * 1.11).collect(...)
    taxed_high_val = (
        JavaStream(amounts)
        .filter(lambda a: a >= 100_000)
        .map(lambda a: a * 1.11)
        .collect()
    )

    total_with_tax = (
        JavaStream(amounts)
        .filter(lambda a: a >= 100_000)
        .map(lambda a: a * 1.11)
        .reduce(0.0, lambda acc, val: acc + val)
    )

    print(f"    {GREEN}✔ Hasil Filter & Map (PPN 11%):{RESET} {taxed_high_val}")
    print(f"    {GREEN}✔ Total Transaksi (Terminal Reduce):{RESET} Rp {total_with_tax:,.2f}")


def run_optional_monad_simulation() -> None:
    banner("3. DEFENSIVE CODING: OPTIONAL MONAD PATTERN")
    step("Null-Safety Pipeline", "Menghindari NullPointerException dengan Java Optional pattern")

    def find_account_email(user_id: int) -> JavaOptional[str]:
        database = {101: "developer@corp.local", 102: None}
        return JavaOptional.of_nullable(database.get(user_id))

    for uid in [101, 102, 999]:
        sanitized = (
            find_account_email(uid)
            .map(lambda email: email.strip().lower())
            .or_else("default-noreply@system.local")
        )
        print(f"  User ID {uid:3d} -> Email: {MAGENTA}{sanitized}{RESET}")


def interactive_menu() -> None:
    while True:
        banner("PILIHAN MENU SIMULASI JAVA CORE (BAB-02)")
        print(f"  {BOLD}1.{RESET} Jalankan Simulasi OOP Modern (Record & Sealed Hierarchy)")
        print(f"  {BOLD}2.{RESET} Jalankan Simulasi Stream API & Functional Pipeline")
        print(f"  {BOLD}3.{RESET} Jalankan Simulasi Optional Monad (Defensive Null-Safety)")
        print(f"  {BOLD}4.{RESET} Jalankan Semua Modul Simulasi Sekaligus")
        print(f"  {BOLD}5.{RESET} Keluar")
        print(f"{CYAN}{'-' * 65}{RESET}")

        try:
            choice = input(f"{BOLD}Pilih opsi [1-5]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            run_oop_simulation()
        elif choice == "2":
            run_stream_simulation()
        elif choice == "3":
            run_optional_monad_simulation()
        elif choice == "4":
            run_oop_simulation()
            run_stream_simulation()
            run_optional_monad_simulation()
            print(f"\n{BOLD}{GREEN}Semua modul berhasil disimulasikan 100%!{RESET}\n")
        elif choice == "5" or choice.lower() in ("q", "exit"):
            print(f"\n{BOLD}{BLUE}Terima kasih telah menjalankan Java Core Technical Lab.{RESET}\n")
            break
        else:
            print(f"{RED}Opsi tidak valid. Masukkan angka 1 sampai 5.{RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan argument '--all', jalankan non-interaktif
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_oop_simulation()
        run_stream_simulation()
        run_optional_monad_simulation()
        print(f"\n{BOLD}{GREEN}Eksekusi otomatis selesai dengan sukses.{RESET}")
    else:
        interactive_menu()
