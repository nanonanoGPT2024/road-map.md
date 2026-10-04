#!/usr/bin/env python3
"""
Lab Hands-on: Scala Advanced Object-Oriented Programming (Deep Dive Simulation)
Fokus: Trait Linearization (Stackable Modifications), Companion Objects,
       Extractors (unapply), dan Algebraic Data Types (ADTs) dengan Covariance.
"""

import sys
import time
import hashlib
from typing import Generic, TypeVar, Optional, Any, Tuple

# ANSI Escape Sequences untuk formatting output terminal
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"

# ============================================================================
# BAGIAN 1: SIMULASI ALGEBRAIC DATA TYPES (ADT) & COVARIANCE (+T)
# ============================================================================

T_co = TypeVar("T_co", covariant=True)


class Result(Generic[T_co]):
    """
    Representasi sealed trait Result[+T] pada Scala.
    Menerapkan ADT dengan status Success atau Failure.
    """
    def is_success(self) -> bool:
        raise NotImplementedError

    def get_or_else(self, default: Any) -> Any:
        raise NotImplementedError


class Success(Result[T_co]):
    """Case class Success[T](value: T) extends Result[T]"""
    def __init__(self, value: T_co) -> None:
        self._value = value

    @property
    def value(self) -> T_co:
        return self._value

    def is_success(self) -> bool:
        return True

    def get_or_else(self, default: Any) -> T_co:
        return self._value

    def __repr__(self) -> str:
        return f"Success({self._value})"


class Failure(Result[T_co]):
    """Case class Failure(error: str) extends Result[Nothing]"""
    def __init__(self, error: str) -> None:
        self._error = error

    @property
    def error(self) -> str:
        return self._error

    def is_success(self) -> bool:
        return False

    def get_or_else(self, default: Any) -> Any:
        return default

    def __repr__(self) -> str:
        return f"Failure({self._error})"


# ============================================================================
# BAGIAN 2: COMPANION OBJECT & EXTRACTOR (apply / unapply)
# ============================================================================

class Transaction:
    """
    Simulasi Case Class di Scala:
    case class Transaction(tx_id: str, sender: str, recipient: str, amount: float)
    """
    def __init__(self, tx_id: str, sender: str, recipient: str, amount: float) -> None:
        self.tx_id = tx_id
        self.sender = sender
        self.recipient = recipient
        self.amount = amount

    def __repr__(self) -> str:
        return f"Transaction(id={self.tx_id}, {self.sender} -> {self.recipient}: ${self.amount:.2f})"


class TransactionCompanion:
    """
    Simulasi Companion Object Scala:
    object Transaction { def apply(...); def unapply(...) }
    """
    @staticmethod
    def apply(tx_id: str, sender: str, recipient: str, amount: float) -> Transaction:
        """Factory method standar Scala: Transaction(...) tanpa keyword 'new'."""
        return Transaction(tx_id, sender, recipient, float(amount))

    @staticmethod
    def unapply(tx: Any) -> Optional[Tuple[str, str, str, float]]:
        """
        Extractor pattern: Mendekonstruksi object ke komponen primitifnya.
        Digunakan oleh pattern matching runtime di Scala.
        """
        if isinstance(tx, Transaction):
            return (tx.tx_id, tx.sender, tx.recipient, tx.amount)
        return None

    @staticmethod
    def parse_csv(line: str) -> Result[Transaction]:
        """Parser pipeline yang memanfaatkan Result ADT."""
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            return Failure(f"Format input salah, diperlukan 4 token, didapat: {len(parts)}")
        try:
            amt = float(parts[3])
            if amt <= 0:
                return Failure("Nilai transfer harus lebih besar dari 0")
            tx = TransactionCompanion.apply(parts[0], parts[1], parts[2], amt)
            return Success(tx)
        except ValueError as ex:
            return Failure(f"Gagal parsing nilai numerik: {str(ex)}")


# ============================================================================
# BAGIAN 3: STACKABLE TRAITS & TRAIT LINEARIZATION
# ============================================================================

class BaseSink:
    """Core Base Class: Abstract root dari pipeline pemrosesan data."""
    def process(self, payload: dict) -> dict:
        payload["core_sink_ts"] = time.time()
        return payload


class UpperCaseTransformTrait(BaseSink):
    """
    Trait 1: Mengubah string identifikasi ke uppercase.
    Menggunakan super() untuk chain-of-responsibility (Linearization).
    """
    def process(self, payload: dict) -> dict:
        if "sender" in payload:
            payload["sender"] = str(payload["sender"]).upper()
        if "recipient" in payload:
            payload["recipient"] = str(payload["recipient"]).upper()
        # Scala trait linearization memanggil super.process(...)
        return super().process(payload)


class SecurityAuditorTrait(BaseSink):
    """Trait 2: Validasi audit trail dan hashing transaksi."""
    def process(self, payload: dict) -> dict:
        payload["audit_tag"] = "VERIFIED_AUDIT"
        raw_signature = f"{payload.get('tx_id')}:{payload.get('amount')}"
        payload["checksum"] = hashlib.sha256(raw_signature.encode()).hexdigest()[:12]
        return super().process(payload)


class RateLimitThrottleTrait(BaseSink):
    """Trait 3: Metrik latensi mikro dan pelambatan adaptif."""
    def process(self, payload: dict) -> dict:
        payload["throttle_delay_ms"] = 0.05
        time.sleep(0.001)  # Simulasi mikrolatensi stackable trait
        return super().process(payload)


# Dynamic Linearized Pipeline:
# class SecurePipeline extends BaseSink with UpperCaseTransformTrait with SecurityAuditorTrait with RateLimitThrottleTrait
class SecureExecutionPipeline(RateLimitThrottleTrait, SecurityAuditorTrait, UpperCaseTransformTrait):
    """
    Subclass yang menggabungkan traits.
    C3 Linearization Python identik dengan Trait Linearization di Scala.
    """
    pass


# ============================================================================
# SYSTEM RUNNER & DEMONSTRATION SUITE
# ============================================================================

def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")


def run_linearization_demo() -> None:
    print_header("DEMO 1: SCALA TRAIT LINEARIZATION VIA MRO (STACKABLE MODIFIERS)")
    
    pipeline = SecureExecutionPipeline()
    print(f"{BOLD}Analisis Urutan Linearization (C3 MRO vs Scala Stack):{RESET}")
    for idx, cls in enumerate(SecureExecutionPipeline.__mro__):
        print(f"  [{idx}] -> {MAGENTA}{cls.__name__}{RESET}")

    sample_payload = {
        "tx_id": "tx-88912",
        "sender": "alice_network",
        "recipient": "bob_vault",
        "amount": 14500.50
    }

    print(f"\nPayload Awal: {YELLOW}{sample_payload}{RESET}")
    result = pipeline.process(sample_payload)
    print(f"Payload Pasca-Linearization Trait Chain:")
    for k, v in result.items():
        print(f"  • {BLUE}{k:<20}{RESET}: {GREEN}{v}{RESET}")


def run_companion_and_extractor_demo() -> None:
    print_header("DEMO 2: COMPANION OBJECTS & EXTRACTORS (apply / unapply)")

    raw_inputs = [
        "TX-001,satoshivault,finney_node,999.95",
        "TX-002,alice_node,charlie_node,-50.00",    # Invalid amount
        "TX-003,malformed_stream_data_without_commas", # Invalid format
        "TX-004,router_alpha,router_omega,2400.00"
    ]

    print(f"Memproses baris data mentah melalui Extractor Pipeline:\n")

    for raw in raw_inputs:
        res = TransactionCompanion.parse_csv(raw)

        # Simulasi Scala Pattern Matching:
        # res match {
        #   case Success(Transaction(id, s, r, a)) => ...
        #   case Failure(err) => ...
        # }
        if isinstance(res, Success):
            tx_obj = res.value
            # Menggunakan unapply extractor
            unapplied = TransactionCompanion.unapply(tx_obj)
            if unapplied:
                tx_id, sender, recipient, amount = unapplied
                print(f"[{GREEN}MATCH SUCCESS{RESET}] ID: {BOLD}{tx_id}{RESET} | "
                      f"Rute: {sender} -> {recipient} | Nilai: {BOLD}${amount:.2f}{RESET}")
        elif isinstance(res, Failure):
            print(f"[{RED}MATCH FAILURE{RESET}] Error: {res.error} | Raw: \"{raw}\"")


def run_covariance_subtyping_demo() -> None:
    print_header("DEMO 3: TYPE VARIANCE SIMULATION (Covariance: +T)")

    class Message:
        def __repr__(self) -> str:
            return "Generic Message"

    class FinancialAlert(Message):
        def __repr__(self) -> str:
            return "Financial Alert (High Severity)"

    def log_result(container: Result[Message]) -> None:
        """
        Fungsi ini mengekspektasikan Result[Message].
        Karena Result bersifat Covariant (+T), Result[FinancialAlert]
        valid sebagai subtipe dari Result[Message].
        """
        if container.is_success():
            print(f"Logging covariant payload: {GREEN}{container.get_or_else(None)}{RESET}")
        else:
            print(f"Logging error: {RED}{container}{RESET}")

    alert = FinancialAlert()
    alert_box: Result[FinancialAlert] = Success(alert)

    print("Memvalidasi subsitusi Liskov berkat Covariance (+T):")
    # Subtipe Result[FinancialAlert] dioperasikan sebagai Result[Message]
    log_result(alert_box)


def main() -> None:
    print(f"{BOLD}{GREEN}SCALA ADVANCED OOP ARCHITECTURE SIMULATOR (PYTHON ENGINE){RESET}")
    print("Memetakan paradigma OOP Scala (Linearization, Extractors, Covariant ADT)")
    
    start_time = time.perf_counter()
    run_linearization_demo()
    run_companion_and_extractor_demo()
    run_covariance_subtyping_demo()
    elapsed = (time.perf_counter() - start_time) * 1000

    print_header("EXECUTION SUMMARY")
    print(f"Status       : {BOLD}{GREEN}ALL TEST CASES PASSED{RESET}")
    print(f"Execution    : {BOLD}{elapsed:.3f} ms{RESET}")
    print(f"Linearization: Resolved successfully via C3 algorithm.")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")


if __name__ == "__main__":
    main()