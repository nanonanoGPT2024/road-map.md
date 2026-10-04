#!/usr/bin/env python3
"""
Lab Exercise: Kotlin Concepts Simulation in Python 3
Materi: Koleksi, Ekstensi, Serialization & Modern Backend Clean Architecture
Dirancang untuk demonstrasi interaktif dan hands-on mandiri dengan terminal ANSI styling.
"""

import sys
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Any
from enum import Enum


# ==============================================================================
# Terminal Color & Styling Utilities (ANSI)
# ==============================================================================
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


def banner(title: str) -> None:
    border = "=" * 68
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f"  {title.center(64)}")
    print(f"{border}{Color.RESET}\n")


def section_header(title: str) -> None:
    print(f"\n{Color.YELLOW}{Color.BOLD}[+] {title}{Color.RESET}")
    print(f"{Color.DIM}{'-' * 60}{Color.RESET}")


def log_success(msg: str) -> None:
    print(f"  {Color.GREEN}✔ {msg}{Color.RESET}")


def log_info(msg: str) -> None:
    print(f"  {Color.BLUE}ℹ {msg}{Color.RESET}")


def log_warn(msg: str) -> None:
    print(f"  {Color.YELLOW}⚠ {msg}{Color.RESET}")


def log_error(msg: str) -> None:
    print(f"  {Color.RED}✖ {msg}{Color.RESET}")


# ==============================================================================
# Bagian 1: Simulasi Kotlin Collections & Sequences (Lazy Evaluation)
# ==============================================================================
class KotlinSequence:
    """Simulasi Sequence di Kotlin (Evaluasi malas / Lazy streams)."""
    def __init__(self, iterable):
        self.iterable = iterable
        self.operations: List[Callable] = []

    def map(self, transform: Callable[[Any], Any]) -> 'KotlinSequence':
        seq = KotlinSequence(self.iterable)
        seq.operations = self.operations + [('map', transform)]
        return seq

    def filter(self, predicate: Callable[[Any], bool]) -> 'KotlinSequence':
        seq = KotlinSequence(self.iterable)
        seq.operations = self.operations + [('filter', predicate)]
        return seq

    def to_list(self) -> List[Any]:
        results = []
        for item in self.iterable:
            current = item
            keep = True
            for op_type, func in self.operations:
                if op_type == 'filter':
                    if not func(current):
                        keep = False
                        break
                elif op_type == 'map':
                    current = func(current)
            if keep:
                results.append(current)
        return results


def demo_collections():
    section_header("1. Kotlin Collections & Lazy Sequence Processing")
    
    raw_data = [10, 25, 30, 45, 50, 65, 80, 95, 100]
    log_info(f"Dataset Mentah: {raw_data}")

    # Standard Eager Operations (List transformation)
    evens = [x for x in raw_data if x % 2 == 0]
    doubled = [x * 2 for x in evens]
    log_success(f"Eager List Processing (filter Genap -> map x2): {doubled}")

    # Sequence Lazy Processing
    seq = (
        KotlinSequence(raw_data)
        .filter(lambda x: x > 30)
        .map(lambda x: f"VAL-{x:03d}")
    )
    result_seq = seq.to_list()
    log_success(f"Kotlin-style Sequence result (filter > 30 -> map formatted): {result_seq}")


# ==============================================================================
# Bagian 2: Simulasi Extension Functions (Kotlin Style)
# ==============================================================================
class StringExtensions:
    """Wrapper untuk mensimulasikan sintaks Kotlin extension functions."""
    @staticmethod
    def to_slug(target: str) -> str:
        return target.strip().lower().replace(" ", "-")

    @staticmethod
    def mask_email(email: str) -> str:
        if "@" not in email:
            return email
        name, domain = email.split("@", 1)
        masked_name = name[:2] + "***" if len(name) > 2 else name + "***"
        return f"{masked_name}@{domain}"


def demo_extensions():
    section_header("2. Kotlin Extension Functions Simulation")
    
    title = "Modern Backend Clean Architecture Kotlin"
    slug = StringExtensions.to_slug(title)
    log_info(f"Original Text : '{title}'")
    log_success(f"Extension call: 'title.toSlug()' -> '{slug}'")

    email = "engineer.backend@cleanarchitecture.internal"
    masked = StringExtensions.mask_email(email)
    log_info(f"Original Email: '{email}'")
    log_success(f"Extension call: 'email.maskEmail()' -> '{masked}'")


# ==============================================================================
# Bagian 3: Simulasi Data Class & Kotlinx Serialization
# ==============================================================================
class AccountRole(str, Enum):
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    USER = "USER"


@dataclass
class UserDto:
    """Simulasi Kotlin @Serializable data class."""
    id: str
    username: str
    role: AccountRole
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        # Simulasi Json.encodeToString()
        data = asdict(self)
        data['role'] = self.role.value
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'UserDto':
        # Simulasi Json.decodeFromString()
        payload = json.loads(json_str)
        payload['role'] = AccountRole(payload['role'])
        return cls(**payload)


def demo_serialization():
    section_header("3. Kotlin Data Class & Serialization (@Serializable)")
    
    user = UserDto(
        id="usr-7701",
        username="dev_kotlin",
        role=AccountRole.DEVELOPER,
        metadata={"framework": "Ktor", "clean_arch": True}
    )
    
    log_info(f"Kotlin Data Class Instance: {user}")
    json_output = user.to_json()
    print(f"{Color.CYAN}{json_output}{Color.RESET}")
    log_success("Json.encodeToString() serialization berhasil!")

    # Round-trip deserialization
    recovered = UserDto.from_json(json_output)
    assert recovered.id == user.id
    log_success(f"Json.decodeFromString() berhasil dipulihkan: ID={recovered.id}, Role={recovered.role.value}")


# ==============================================================================
# Bagian 4: Clean Architecture Backend Simulation
# ==============================================================================
# 4.1 Domain Layer: Entities & Result Monad
@dataclass
class Transaction:
    id: str
    account_id: str
    amount: float
    description: str
    status: str = "PENDING"


class Result:
    """Simulasi Kotlin Result<T> monad."""
    def __init__(self, value=None, error=None, is_success=True):
        self.value = value
        self.error = error
        self.is_success = is_success

    @classmethod
    def success(cls, value):
        return cls(value=value, is_success=True)

    @classmethod
    def failure(cls, error_msg: str):
        return cls(error=error_msg, is_success=False)


# 4.2 Domain Layer: Repository Interface (Port)
class ITransactionRepository:
    def save(self, tx: Transaction) -> Result:
        raise NotImplementedError

    def find_by_id(self, tx_id: str) -> Optional[Transaction]:
        raise NotImplementedError


# 4.3 Use Case Layer: Interactor
class CreateTransactionUseCase:
    def __init__(self, repo: ITransactionRepository):
        self.repo = repo

    def execute(self, tx_id: str, account_id: str, amount: float, description: str) -> Result:
        # Domain Business Rule
        if amount <= 0:
            return Result.failure("Jumlah transaksi harus lebih besar dari 0.")
        if not account_id.strip():
            return Result.failure("Account ID tidak boleh kosong.")

        tx = Transaction(
            id=tx_id,
            account_id=account_id,
            amount=amount,
            description=description,
            status="SETTLED"
        )
        return self.repo.save(tx)


# 4.4 Infrastructure Layer: In-Memory Adapter
class InMemoryTransactionRepository(ITransactionRepository):
    def __init__(self):
        self._db: Dict[str, Transaction] = {}

    def save(self, tx: Transaction) -> Result:
        self._db[tx.id] = tx
        return Result.success(tx)

    def find_by_id(self, tx_id: str) -> Optional[Transaction]:
        return self._db.get(tx_id)


def demo_clean_architecture():
    section_header("4. Modern Backend Clean Architecture Workflow")
    
    repo = InMemoryTransactionRepository()
    use_case = CreateTransactionUseCase(repo)

    # Valid Transaction
    log_info("Memproses Use Case: Valid Transaction...")
    res1 = use_case.execute(
        tx_id="tx-9901",
        account_id="acc-indonesia-01",
        amount=500_000.0,
        description="Pembayaran Subscription Cloud"
    )
    if res1.is_success:
        tx = res1.value
        log_success(f"Domain Transaction Saved: ID={tx.id}, Status={tx.status}, Amount=Rp {tx.amount:,.2f}")
    else:
        log_error(f"Gagal: {res1.error}")

    # Invalid Transaction (Negative Amount)
    log_info("Memproses Use Case: Invalid Transaction (amount <= 0)...")
    res2 = use_case.execute(
        tx_id="tx-9902",
        account_id="acc-indonesia-01",
        amount=-15_000.0,
        description="Pengujian Rule Validasi"
    )
    if not res2.is_success:
        log_warn(f"Validasi Domain Berhasil Menggagalkan Request: '{res2.error}'")


# ==============================================================================
# Bagian 5: Interactive Menu & Verification CLI
# ==============================================================================
def interactive_menu():
    banner("SIMULASI KOTLIN: KOLEKSI, SERIALIZATION & CLEAN ARCHITECTURE")
    
    options = {
        "1": ("Demo Koleksi & Sequence Processing", demo_collections),
        "2": ("Demo Extension Functions", demo_extensions),
        "3": ("Demo Serialization & Data Class", demo_serialization),
        "4": ("Demo Clean Architecture Backend", demo_clean_architecture),
        "5": ("Jalankan Seluruh Suite / Evaluasi Otomatis", run_all_suites),
        "0": ("Keluar", None)
    }

    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}Menu Pilihan Modul Lab:{Color.RESET}")
        for key, (desc, _) in options.items():
            print(f"  {Color.MAGENTA}[{key}]{Color.RESET} {desc}")
            
        choice = input(f"\n{Color.CYAN}Masukkan nomor modul [0-5]: {Color.RESET}").strip()
        
        if choice == "0":
            print(f"{Color.GREEN}Terima kasih telah menjalankan lab exercise! Selesai.{Color.RESET}")
            break
        elif choice in options and options[choice][1] is not None:
            time.sleep(0.2)
            options[choice][1]()
        else:
            log_error("Pilihan tidak valid, silakan ulangi.")


def run_all_suites():
    log_info("Memulai verifikasi menyeluruh seluruh konsep...")
    demo_collections()
    demo_extensions()
    demo_serialization()
    demo_clean_architecture()
    banner("SEMUA SIMULASI BERHASIL DIJALANKAN DENGAN SUKSES (100% PASS)")


if __name__ == "__main__":
    # Jika dipanggil dengan flag non-interaktif seperti --all
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        run_all_suites()
    else:
        # Jalankan secara interaktif sesuai instruksi
        interactive_menu()
