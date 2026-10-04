#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Pemrograman Fungsional ala Scala (Deep Dive)
Topik: 02-Programming-Languages / Scala (Bab 03 - Modul 02)

Script ini mengimplementasikan konsep inti FP Scala di atas Python:
1. Algebraic Data Types (ADTs) & Sealed Hierarchy (`Option`, `Either`, `Try`)
2. Monadic Composition (`map`, `flat_map`, `fold`) sebagai For-Comprehension engine
3. Currying & Partial Application
4. Verifikasi Matematis Monad Laws (Left Identity, Right Identity, Associativity)
5. Robust Industrial Pipeline: Pure Financial Transaction Engine tanpa side-effect
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TypeVar, Generic, Callable, Any
import time
import sys

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"

A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")
E = TypeVar("E")

# ==============================================================================
# 1. ALGEBRAIC DATA TYPES (ADTs) & MONADIC ABSTRACTIONS
# ==============================================================================

class Either(Generic[E, A]):
    """
    Simulasi Scala 'sealed trait Either[+E, +A]'
    Mewakili komputasi yang dapat gagal dengan nilai Left[E] atau sukses dengan Right[A].
    """
    def is_right(self) -> bool:
        raise NotImplementedError

    def is_left(self) -> bool:
        return not self.is_right()

    def map(self, f: Callable[[A], B]) -> Either[E, B]:
        if isinstance(self, Right):
            return Right(f(self.value))
        return Left(self.value)  # type: ignore

    def flat_map(self, f: Callable[[A], Either[E, B]]) -> Either[E, B]:
        if isinstance(self, Right):
            return f(self.value)
        return Left(self.value)  # type: ignore

    def fold(self, fa: Callable[[E], C], fb: Callable[[A], C]) -> C:
        if isinstance(self, Right):
            return fb(self.value)
        return fa(self.value)

    @staticmethod
    def pure(value: A) -> Either[E, A]:
        return Right(value)


@dataclass(frozen=True)
class Left(Either[E, Any]):
    value: E
    def is_right(self) -> bool:
        return False
    def __repr__(self) -> str:
        return f"{CLR_RED}Left({self.value}){CLR_RESET}"


@dataclass(frozen=True)
class Right(Either[Any, A]):
    value: A
    def is_right(self) -> bool:
        return True
    def __repr__(self) -> str:
        return f"{CLR_GREEN}Right({self.value}){CLR_RESET}"


class Try(Generic[A]):
    """Simulasi Scala 'scala.util.Try[T]' untuk boundary interop kode imperatif/throwing."""
    @staticmethod
    def run(f: Callable[[], A]) -> Either[str, A]:
        try:
            return Right(f())
        except Exception as ex:
            return Left(f"{type(ex).__name__}: {str(ex)}")


# ==============================================================================
# 2. DOMAIN MODELS & IMMUTABILITY (Case Classes Representation)
# ==============================================================================

@dataclass(frozen=True)
class Account:
    id: str
    owner: str
    balance: float
    currency: str


@dataclass(frozen=True)
class TransactionIntent:
    sender_id: str
    recipient_id: str
    amount: float
    currency: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class LedgerEntry:
    tx_id: str
    from_acc: str
    to_acc: str
    net_amount: float
    fee_deducted: float
    timestamp: float


# ==============================================================================
# 3. HIGHER ORDER FUNCTIONS & CURRYING (SCALA PATTERNS)
# ==============================================================================

def curried_fee_calculator(base_rate: float) -> Callable[[str], Callable[[float], float]]:
    """
    Currying ala Scala: (baseRate: Double)(tier: String)(amount: Double): Double
    Mendemonstrasikan fungsi ordo tinggi dan partial application.
    """
    def with_tier(tier: str) -> Callable[[float], float]:
        multipliers = {"STANDARD": 1.0, "VIP": 0.5, "INSTITUTIONAL": 0.2}
        mult = multipliers.get(tier.upper(), 1.0)
        def with_amount(amount: float) -> float:
            fee = amount * base_rate * mult
            return round(max(fee, 0.50), 2)  # minimum fee 0.50
        return with_amount
    return with_tier


# ==============================================================================
# 4. PURE FUNCTIONAL ENGINE (COMPOSABLE VALIDATION & EXECUTION)
# ==============================================================================

class BankingEngine:
    def __init__(self, accounts: dict[str, Account]):
        self._accounts = dict(accounts)

    def find_account(self, acc_id: str) -> Either[str, Account]:
        acc = self._accounts.get(acc_id)
        if acc is not None:
            return Right(acc)
        return Left(f"Akun [{acc_id}] tidak ditemukan di sistem")

    def validate_amount(self, intent: TransactionIntent) -> Either[str, TransactionIntent]:
        if intent.amount <= 0:
            return Left(f"Nominal transaksi invalid: {intent.amount}. Harus > 0")
        if intent.amount > 1_000_000:
            return Left(f"Transaksi {intent.amount} melebihi batas regulasi AML")
        return Right(intent)

    def validate_currencies(self, sender: Account, recipient: Account, intent: TransactionIntent) -> Either[str, None]:
        if sender.currency != intent.currency or recipient.currency != intent.currency:
            return Left(f"Cross-currency tidak didukung: {sender.currency} -> {recipient.currency}")
        return Right(None)

    def process_transaction(
        self,
        intent: TransactionIntent,
        fee_calculator: Callable[[float], float]
    ) -> Either[str, tuple[Account, Account, LedgerEntry]]:
        """
        Simulasi For-Comprehension monadic pipeline:
        for {
          valid_tx <- validate_amount(intent)
          sender   <- find_account(valid_tx.sender_id)
          recv     <- find_account(valid_tx.recipient_id)
          _        <- validate_currencies(sender, recv, valid_tx)
          fee      =  fee_calculator(valid_tx.amount)
          result   <- verify_and_apply(sender, recv, valid_tx, fee)
        } yield result
        """
        return (
            self.validate_amount(intent)
            .flat_map(lambda valid_intent: 
                self.find_account(valid_intent.sender_id).flat_map(lambda sender:
                    self.find_account(valid_intent.recipient_id).flat_map(lambda recv:
                        self.validate_currencies(sender, recv, valid_intent).flat_map(lambda _:
                            self._execute_transfer(sender, recv, valid_intent, fee_calculator(valid_intent.amount))
                        )
                    )
                )
            )
        )

    def _execute_transfer(
        self,
        sender: Account,
        recv: Account,
        intent: TransactionIntent,
        fee: float
    ) -> Either[str, tuple[Account, Account, LedgerEntry]]:
        total_debit = intent.amount + fee
        if sender.balance < total_debit:
            return Left(
                f"Saldo tidak cukup pada akun {sender.id}. "
                f"Dibutuhkan: {total_debit} (Termasuk fee {fee}), Saldo saat ini: {sender.balance}"
            )

        # Immutability: Mengembalikan objek akun baru (Copy on Write ala case class .copy)
        updated_sender = Account(
            id=sender.id,
            owner=sender.owner,
            balance=round(sender.balance - total_debit, 2),
            currency=sender.currency
        )
        updated_recv = Account(
            id=recv.id,
            owner=recv.owner,
            balance=round(recv.balance + intent.amount, 2),
            currency=recv.currency
        )
        entry = LedgerEntry(
            tx_id=f"TXN-{int(time.time()*1000)}",
            from_acc=sender.id,
            to_acc=recv.id,
            net_amount=intent.amount,
            fee_deducted=fee,
            timestamp=time.time()
        )
        return Right((updated_sender, updated_recv, entry))


# ==============================================================================
# 5. VERIFIKASI MONAD LAWS (MATHEMATICAL RIGOR CHECK)
# ==============================================================================

def verify_monad_laws() -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}[VERIFIKASI FP FOUNDATION: HUKUM-HUKUM MONAD]{CLR_RESET}")

    f: Callable[[int], Either[str, int]] = lambda x: Right(x * 3)
    g: Callable[[int], Either[str, int]] = lambda x: Right(x + 10)
    val = 42

    # Hukum 1: Left Identity -> pure(x).flatMap(f) == f(x)
    left_id_1 = Either.pure(val).flat_map(f)
    left_id_2 = f(val)
    assert left_id_1 == left_id_2, "Left Identity Failed"
    print(f"  {CLR_GREEN}✔ Law 1: Left Identity Terpenuhi{CLR_RESET}  -> pure(a).flatMap(f) ≡ f(a)")

    # Hukum 2: Right Identity -> m.flatMap(pure) == m
    monad_m = Right(val)
    right_id = monad_m.flat_map(Either.pure)
    assert right_id == monad_m, "Right Identity Failed"
    print(f"  {CLR_GREEN}✔ Law 2: Right Identity Terpenuhi{CLR_RESET} -> m.flatMap(pure) ≡ m")

    # Hukum 3: Associativity -> m.flatMap(f).flatMap(g) == m.flatMap(x => f(x).flatMap(g))
    assoc_lhs = monad_m.flat_map(f).flat_map(g)
    assoc_rhs = monad_m.flat_map(lambda x: f(x).flat_map(g))
    assert assoc_lhs == assoc_rhs, "Associativity Failed"
    print(f"  {CLR_GREEN}✔ Law 3: Associativity Terpenuhi{CLR_RESET}  -> (m.flatMap(f)).flatMap(g) ≡ m.flatMap(x => f(x).flatMap(g))")


# ==============================================================================
# 6. RUNNER / TEST SUITE DENGAN INSTRUMENTASI TERMINAL
# ==============================================================================

def main() -> None:
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}  SCALA FP LAB DEEP DIVE: MONADS, ADTs & PURE COMPOSITION PIPELINES  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================{CLR_RESET}")

    verify_monad_laws()

    # Inisialisasi Database In-Memory Immutable
    initial_accounts = {
        "ACC-001": Account("ACC-001", "Alice Pratama", 1500.0, "IDR"),
        "ACC-002": Account("ACC-002", "Budi Santoso", 250.0, "IDR"),
        "ACC-003": Account("ACC-003", "Charlie Global", 5000.0, "USD"),
    }

    engine = BankingEngine(initial_accounts)
    calc_fee = curried_fee_calculator(base_rate=0.01)("STANDARD")

    # Test Cases: Menguji determinisme dan penanganan error tanpa exceptions
    test_cases: list[tuple[str, TransactionIntent]] = [
        (
            "Transaksi Valid Normal",
            TransactionIntent("ACC-001", "ACC-002", 300.0, "IDR", {"ref": "INV-01"})
        ),
        (
            "Gagal Validasi Nominal (Negatif)",
            TransactionIntent("ACC-001", "ACC-002", -50.0, "IDR", {"ref": "INV-02"})
        ),
        (
            "Akun Penerima Tidak Ditemukan",
            TransactionIntent("ACC-001", "ACC-999", 100.0, "IDR", {"ref": "INV-03"})
        ),
        (
            "Ketidakcocokan Mata Uang (Cross-Currency)",
            TransactionIntent("ACC-001", "ACC-003", 100.0, "IDR", {"ref": "INV-04"})
        ),
        (
            "Kegagalan Bisnis (Saldo Kurang)",
            TransactionIntent("ACC-002", "ACC-001", 5000.0, "IDR", {"ref": "INV-05"})
        ),
    ]

    print(f"\n{CLR_BOLD}{CLR_CYAN}[EKSEKUSI PIPELINE MONADIC PURE PROCESSING]{CLR_RESET}")
    print(f"{'-'*70}")

    for idx, (label, tx) in enumerate(test_cases, start=1):
        print(f"\n{CLR_BOLD}Case {idx}: {label}{CLR_RESET}")
        print(f"  Intended: {tx.sender_id} -> {tx.recipient_id} | Jumlah: {tx.amount} {tx.currency}")

        result = engine.process_transaction(tx, calc_fee)

        # Scala-style Pattern Matching / Fold
        def on_failure(err: str) -> None:
            print(f"  {CLR_RED}✖ Pipeline Stopped:{CLR_RESET} {err}")

        def on_success(res: tuple[Account, Account, LedgerEntry]) -> None:
            sender_upd, recv_upd, ledger = res
            print(f"  {CLR_GREEN}✔ Pipeline Berhasil:{CLR_RESET}")
            print(f"    TxID: {ledger.tx_id} | Fee: {ledger.fee_deducted} | Net: {ledger.net_amount}")
            print(f"    Saldo Baru {sender_upd.id} ({sender_upd.owner}): {sender_upd.balance} {sender_upd.currency}")
            print(f"    Saldo Baru {recv_upd.id} ({recv_upd.owner}): {recv_upd.balance} {recv_upd.currency}")

        result.fold(on_failure, on_success)

    # Uji Interoperabilitas Exception Handling dengan Try Monad
    print(f"\n{CLR_BOLD}{CLR_CYAN}[UJI COBA BOUNDARY TRY/EXCEPT MONAD (Scala Try -> Either)]{CLR_RESET}")
    risky_operation = lambda: 100 / 0
    safe_result = Try.run(risky_operation)
    print(f"  Operasi Berisiko (Divide by Zero) Dikonversi ke Monad: {safe_result}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}Semua evaluasi fondasi FP Scala selesai secara deterministik.{CLR_RESET}\n")


if __name__ == "__main__":
    main()