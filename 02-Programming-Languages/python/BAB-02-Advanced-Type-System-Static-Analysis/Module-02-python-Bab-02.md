# Kurikulum Enterprise: Python Advanced Type System & Static Analysis

**Kategori:** 02-Programming-Languages  
**Bab:** 02 - Advanced Type System & Static Analysis  
**Modul:** Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi  

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedakan** sistem tipe nominal (*Nominal Subtyping*) dan struktural (*Structural Subtyping / Protocols*) pada CPython.
- **Mengimplementasikan** relasi variansi lanjutan (*Covariance*, *Contravariance*, dan *Invariance*) menggunakan `TypeVar` modern dan sintaks generics Python 3.12+ (PEP 695).
- **Merekayasa Meta-typing Dinamis** berbasis `ParamSpec`, `Concatenate`, `TypeVarTuple`, dan `Unpack` untuk membangun decorator dan wrapper produksi yang mempertahankan metadata tipe secara deterministik.
- **Mencegah Kerentanan Injeksi** pada level kompilasi/analisis statis dengan menerapkan `typing.LiteralString` (PEP 675).
- **Merancang dan Mengintegrasikan** pipeline static analysis enterprise multi-layer (MyPy Daemon, Pyright, Ruff AST) ke dalam alur kerja CI/CD berkinerja tinggi.
- **Mengeliminasi Runtime Performance Overhead** yang ditimbulkan oleh abstraksi tipe melalui penerapan zero-cost type checking patterns (`typing.TYPE_CHECKING`, lazy evaluation PEP 563/649).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
1. **Object-Oriented Python Lanjutan:** Metaclasses, dunder methods (`__init_subclass__`, `__class_getitem__`), dan dynamic attribute dispatching (`__getattr__`, `__getattribute__`).
2. **Dasar Sistem Pengetikan Statis:** Sintaks dasar type hints PEP 484 (`Optional`, `Union`, `List`, `Dict`, `Callable`, `Generic`).
3. **Internal Eksekusi CPython:** Alur kerja Lexer -> Parser -> Abstract Syntax Tree (AST) -> Bytecode compilation.
4. **CI/CD & Tooling Dasar:** Penggunaan shell script, pre-commit hooks, dan Docker.

---

## 3. Concept & Internal Architecture

### 3.1 CPython Type Erasure & Runtime Footprint

Python adalah bahasa bertipe dinamis murni (*dynamically typed language*). Seluruh anotasi tipe (PEP 484) tunduk pada prinsip **Type Erasure**: mesin virtual CPython (`ceval.c`) tidak memvalidasi tipe saat runtime execution loop berlangsung. 

```
Kode Sumber (.py) 
       │
       ▼
 [ Lexer / Tokenizer ]
       │
       ▼
 [ AST Generator ] ──> Node Annotations tersimpan dalam AST (arg->annotation)
       │
       ▼
[ Bytecode Compiler ] ──> Emisi bytecode: LOAD_CONST, STORE_NAME
       │
       ▼
[ CPython VM / ceval.c ] ──> Runtime: Anotasi diabaikan, hanya dieksekusi 
                             sebagai dictionary (__annotations__)
```

Secara historis, penulisan type hints dievaluasi pada saat modul diimpor:
```python
def process_data(items: list[int]) -> None:
    pass
```
Pada runtime, CPython mengeksekusi ekspresi `list[int]`, membuat instance `types.GenericAlias`, dan memasukkannya ke dalam dictionary `process_data.__annotations__`. Proses ini memakan alokasi memori dan siklus CPU saat *cold boot*.

Melalui **PEP 563** (`from __future__ import annotations`) dan revisi arsitektur pada **PEP 649** (Python 3.14+ deferred evaluation via annotation scopes), anotasi disimpan sebagai *string literals* atau *lazy evaluation code objects*, menekan import-time overhead ke angka nol (*zero runtime overhead*).

### 3.2 Sistem Subtyping: Nominal vs. Structural

CPython mendukung dua model subtyping utama:

```
                  ┌──────────────────────────────┐
                  │    Subtyping Architecture    │
                  └──────────────┬───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│   Nominal Subtyping (ABC)    │   │  Structural Subtyping (PEP)  │
│         Base/Derived         │   │       typing.Protocol        │
├──────────────────────────────┤   ├──────────────────────────────┤
│- Relasi eksplisit (MRO)      │   │- Berbasis bentuk (Shape/API) │
│- Inheritance coupling tinggi │   │- Static duck typing          │
│- Verifikasi hierarki kaku    │   │- Zero coupling antar modul   │
└──────────────────────────────┘   └──────────────────────────────┘
```

1. **Nominal Subtyping:** Objek $A$ adalah subtype dari $B$ *hanya jika* kelas $A$ secara eksplisit mewarisi (*inherits*) kelas $B$. Verifikasi bertumpu pada `__mro__` (Method Resolution Order).
2. **Structural Subtyping (`typing.Protocol` - PEP 544):** Objek $A$ adalah subtype dari $B$ jika struktur/shape (metode dan atribut) dari $A$ kompatibel dengan interface $B$, tanpa perlu deklarasi inheritance langsung (*Static Duck Typing*).

### 3.3 Matematika Variansi: Invariance, Covariance, Contravariance

Variansi mendeskripsikan bagaimana relasi subtyping antara tipe-tipe komponen berkorelasi dengan tipe-tipe kompleks yang dibangun di atasnya.

Didefinisikan:
- $S <: T$ menyatakan $S$ adalah subtype dari $T$.
- $F[T]$ adalah tipe generic kontainer atau fungsi.

```
Subtyping Type Lattice:
          object (Top Type: ⊤)
             │
           Animal
             │
            Dog
             │
          Never / NoReturn (Bottom Type: ⊥)
```

| Tipe Variansi | Formulasi Formal | Aturan Praktis | Kasus Penggunaan Ideal |
|---|---|---|---|
| **Invariance** | $F[S] <: F[T] \iff S = T$ | Wadah dapat dibaca (*Read*) dan ditulis (*Write*). | `list[T]`, `dict[K, V]`, Mutable containers. |
| **Covariance** | $S <: T \implies F[S] <: F[T]$ | Data hanya dihasilkan (*Read-only / Producer*). | `Sequence[+T]`, `Iterable[+T]`, Immutable collections. |
| **Contravariance** | $S <: T \implies F[T] <: F[S]$ | Data hanya dikonsumsi (*Write-only / Consumer*). | `Callable[[-T], None]`, Consumer sinks, Serializers. |

Secara matematis, untuk fungsi:
$$\text{Func} : (Arg) \to Ret$$
Aturan variansi fungsi dalam static typing adalah: **Contravariant pada tipe Argumen**, dan **Covariant pada tipe Return Value**:
$$(A \to B) <: (C \to D) \iff C <: A \quad \text{dan} \quad B <: D$$

### 3.4 Static Analysis Inference Engines

Mesin seperti **MyPy** dan **Pyright** menggunakan algoritma *Bi-directional Type Inference*. Mesin melakukan traversal pada AST dan memecahkan batasan tipe (*type constraints*) menggunakan *Constraint Satisfaction Problems (CSP)*.

```
Kode Sumber (.py)
       │
       ▼
 [ AST Parser ]
       │
       ▼
[ Symbol Table & Scope Resolution ]
       │
       ▼
[ Bi-directional Type Inference ] ──> Synthesizes types bottom-up
       │                              Checks constraints top-down
       ▼
[ Constraint Solver / Type Lattice ]
       │
       ▼
[ Issue Diagnostic & Error Emission ]
```

---

## 4. Why & What

### Mengapa Dynamic Typing Gagal di Skala Enterprise?
1. **Implicit Contracts:** Dynamic duck typing menyembunyikan ekspektasi runtime. Perubahan API pada core module memicu kegagalan runtime (*runtime attribute errors*) di modul hilir tanpa peringatan kompilasi.
2. **Refactoring Hazard:** Tanpa sistem tipe yang ketat, refactoring multi-repositori atau microservice SDK menjadi spekulatif dan memicu *regression bug*.
3. **Security Blindspots:** Dynamic string manipulation membuka celah SQL injection, shell command execution, dan SSRF.

### Solusi Modern: Static Analysis & Advanced Typing
- **Determinisme Pra-Produksi:** Seluruh verifikasi interface, null-safety (`Optional` exhaustiveness check), dan type bounds dieksekusi statis via CI/CD.
- **Contract Enforcement:** `Protocol` memisahkan implementasi concrete dari kontrak arsitektur layer atas (Clean Architecture / Hexagonal Architecture).
- **Zero Cost Runtime:** Penerapan static typing di Python tidak mengorbankan karakteristik dinamis bahasa saat aplikasi di-deploy di cloud runtime.

---

## 5. How (Workflow Detail)

Alur kerja enterprise terbagi ke dalam **Development Loop** dan **CI/CD Static Gating Pipeline**:

```
+-------------------------------------------------------------------------+
| Local Development Loop                                                  |
|                                                                         |
|  [ Developer Writes Code ]                                              |
|            │                                                            |
|            ▼                                                            |
|  [ LSP / Pyright in IDE ] ──────────────> Visual Feedback Realtime     |
|            │                                                            |
|            ▼                                                            |
|  [ Git Pre-commit Hook ]                                                |
|       ├─> Ruff (Lint AST & Format)                                      |
|       └─> MyPy Daemon (Local Cache Verification)                        |
+------------│------------------------------------------------------------+
             │ Push to Git Remote
             ▼
+-------------------------------------------------------------------------+
| Enterprise CI/CD Strict Gate Pipeline                                   |
|                                                                         |
|  [ Stage 1: Fast AST Linting ] ─────────> Ruff (Syntax & PEP violations)|
|            │                                                            |
|            ▼                                                            |
|  [ Stage 2: Deep Type Checking ] ───────> MyPy --strict                 |
|            │                              Pyright --level error         |
|            ▼                                                            |
|  [ Stage 3: Static Taint Analysis ] ────> Semgrep / Bandit / MyPy       |
|            │                              (LiteralString validations)   |
|            ▼                                                            |
|  [ Stage 4: Bytecode Smoke Test ] ──────> python -m compileall          |
|            │                                                            |
|            ▼                                                            |
|  [ Stage 5: Enterprise Test Suite ] ────> Pytest (Unit & Integration)   |
|            │                                                            |
|            ▼                                                            |
|  [ Artefak Lolos Verifikasi Statis ]                                    |
+-------------------------------------------------------------------------+
```

---

## 6. Analogy & Diagram ASCII

### Analogi Variansi: Mesin Pemroses Organik

Bayangkan hierarki biologis: `Organisme -> Hewan -> Kucing`.

- **Covariance (Output/Producer):**
  Kotak `Kandang[+T]` adalah *penghasil* hewan. Jika Anda memesan `Kandang[Hewan]`, dan kontraktor mengirimkan `Kandang[Kucing]`, pesanan tetap aman: apapun yang dikeluarkan dari kandang tersebut dijamin adalah seekor `Hewan`. (Subtyping searah).
- **Contravariance (Input/Consumer):**
  Pusat `Vaksinasi[-T]` adalah *konsumen* hewan. Jika Anda butuh fasilitas untuk memvaksinasi kucing (`Vaksinasi[Kucing]`), Anda bisa menggunakan pusat `Vaksinasi[Hewan]`. Fasilitas tersebut mampu menangani sembarang hewan, sehingga pasti dapat menangani kucing. (Subtyping berbalik arah).
- **Invariance (Read-Write):**
  Klinik rawat inap `Klinik[T]` menerima hewan sekaligus mengeluarkannya kembali. Jika klinik `Kucing` diperlakukan sebagai klinik `Hewan`, seorang dokter bisa memasukkan anjing ke dalamnya. Ketika anjing dikeluarkan oleh staf yang mengekspektasi kucing, runtime akan *crash*. Maka wadah read-write harus strictly invariant!

### Diagram: Subtyping Structural Compatibility Matrix

```
       Interface Protocol (Transactor)
       +-------------------------------+
       | + execute(id: UUID) -> Status |
       | + rollback() -> bool          |
       +-------------------------------+
                      ▲
                      │  (No explicit inheritance needed!)
                      │  Static Structural Match
         ┌────────────┴────────────┐
         │                         │
+─────────────────+       +─────────────────+
| PostgresEngine  |       | KafkaEventStore |
+─────────────────+       +─────────────────+
| + execute(...)  |       | + execute(...)  |
| + rollback(...) |       | + rollback(...) |
| + vacuum()      |       | + rebalance()   |
+─────────────────+       +─────────────────+
```

---

## 7. Simple & Practical Implementation

### 7.1 Simple Example: Variance & Generic Invariance Pitfalls

```python
"""
Demonstrasi matematis Variansi pada Generic Containers.
Kompatibel dengan Python 3.12+ (PEP 695 syntax) dan legacy TypeVar.
"""
from typing import TypeVar, Generic, Sequence

class Entity: 
    def identify(self) -> str: return "Entity"

class User(Entity): 
    def identify(self) -> str: return "User"

class Admin(User): 
    def identify(self) -> str: return "Admin"

# 1. INVARIANT CONTAINER (Default)
T_inv = TypeVar("T_inv")  # Invariant

class MutableBox(Generic[T_inv]):
    def __init__(self, value: T_inv) -> None:
        self.value: T_inv = value

    def set(self, val: T_inv) -> None:
        self.value = val

    def get(self) -> T_inv:
        return self.value

def mutate_box(box: MutableBox[User]) -> None:
    # Jika mutable box covariant, baris berikut akan merusak safety:
    box.set(User())

admin_box: MutableBox[Admin] = MutableBox(Admin())
# mutate_box(admin_box) 
# TYPE ERROR: Argument 1 to "mutate_box" has incompatible type "MutableBox[Admin]"; 
# expected "MutableBox[User]" (Invariant!)

# 2. COVARIANT CONTAINER (Producer Only)
T_co = TypeVar("T_co", covariant=True)

class ReadOnlyStream(Generic[T_co]):
    def __init__(self, items: list[T_co]) -> None:
        self._items = items

    def read_all(self) -> Sequence[T_co]:
        return self._items

def consume_entity_stream(stream: ReadOnlyStream[Entity]) -> None:
    for item in stream.read_all():
        print(item.identify())

user_stream: ReadOnlyStream[User] = ReadOnlyStream([User(), Admin()])
# VALID: ReadOnlyStream[User] adalah subtype dari ReadOnlyStream[Entity]
consume_entity_stream(user_stream)
```

### 7.2 Practical Example: Enterprise Zero-Allocation Event Bus & Safe Query Execution

Contoh produksi berikut menggabungkan:
1. `Protocol` untuk structural event handling.
2. `ParamSpec` & `Concatenate` untuk dynamic auditing decorator.
3. `LiteralString` untuk kompilasi aman terhadap SQL Injection.
4. Python 3.12 `type` statement & Generics.

```python
from __future__ import annotations

import functools
import logging
import sqlite3
from collections.abc import Callable
from typing import (
    Any,
    Concatenate,
    LiteralString,
    ParamSpec,
    Protocol,
    Self,
    TypeVar,
    runtime_checkable,
)

logger = logging.getLogger("EnterpriseSecurity")

# ============================================================================
# Core Types & Protocols
# ============================================================================

class DomainEvent(Protocol):
    """Event schema struktural; event apapun dengan event_id cocok."""
    @property
    def event_id(self) -> str: ...
    @property
    def payload(self) -> dict[str, Any]: ...

@runtime_checkable
class EventHandler(Protocol):
    """Protocol consumer event contravariant secara semantik."""
    def handle(self, event: DomainEvent) -> bool: ...

# ============================================================================
# Advanced Meta-typing: Decorator Preservasi Tipe Tingkat Tinggi
# ============================================================================

P = ParamSpec("P")
R = TypeVar("R")

class AuditContext:
    def __init__(self, actor: str) -> None:
        self.actor = actor

def audited(
    audit_message: str,
) -> Callable[[Callable[Concatenate[AuditContext, P], R]], Callable[P, R]]:
    """
    Decorator enterprise yang menyuntikkan AuditContext secara transparan
    sambil mengekspos tipe parameter 'P' dan return 'R' asli secara akurat.
    """
    def decorator(func: Callable[Concatenate[AuditContext, P], R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            ctx = AuditContext(actor="system_authenticated_worker")
            logger.info("Executing %s | Audit: %s", func.__name__, audit_message)
            return func(ctx, *args, **kwargs)
        return wrapper
    return decorator

# ============================================================================
# Type-Safe Data Layer: Enforcing Compile-time Anti-SQLi
# ============================================================================

class SafeDatabaseClient:
    def __init__(self, dsn: str) -> None:
        self._connection = sqlite3.connect(dsn)

    def execute_strictly_safe(
        self,
        query: LiteralString,  # HANYA menerima raw string literal, bukan variable string dinamis!
        parameters: tuple[Any, ...],
    ) -> list[tuple[Any, ...]]:
        """
        Mengeksekusi query database. Menggunakan LiteralString memastikan parameter
        hanya berasal dari kode sumber langsung, mematikan SQL Injection pada tipe level.
        """
        cursor = self._connection.cursor()
        cursor.execute(query, parameters)
        return cursor.fetchall()

# ============================================================================
# Modern Python 3.12+ Generic Builder Pattern using Self
# ============================================================================

class CommandBuilder:
    def __init__(self) -> None:
        self._commands: list[str] = []

    def add_command(self, cmd: str) -> Self:
        self._commands.append(cmd)
        return self

    def build(self) -> list[str]:
        return list(self._commands)

# ============================================================================
# Orchestrator & Business Implementation
# ============================================================================

class OrderPlacedEvent:
    def __init__(self, order_id: str, total_amount: float) -> None:
        self.order_id = order_id
        self.total_amount = total_amount

    @property
    def event_id(self) -> str:
        return self.order_id

    @property
    def payload(self) -> dict[str, Any]:
        return {"amount": self.total_amount}

@audited("Transaction Order Pipeline Execution")
def process_order_event(
    ctx: AuditContext,
    event: DomainEvent,
    db: SafeDatabaseClient,
) -> bool:
    print(f"[{ctx.actor}] Mengonsumsi event: {event.event_id}")
    
    # KODE INI LOLOS STATIC CHECK: String adalah literal murni
    safe_query: LiteralString = "SELECT status FROM transactions WHERE id = ?"
    db.execute_strictly_safe(safe_query, (event.event_id,))
    
    # JIKA ANDA MEMBUKA KOMEN INI, STATIC ANALYZER (MyPy/Pyright) AKAN REJECT DENGAN KERAS:
    # dynamic_input = f"SELECT status FROM transactions WHERE id = '{event.event_id}'"
    # db.execute_strictly_safe(dynamic_input, ())
    # Error: Argument 1 to "execute_strictly_safe" has incompatible type "str";
    # expected "LiteralString"
    
    return True

if __name__ == "__main__":
    db_client = SafeDatabaseClient(":memory:")
    # Buat schema sementara
    db_client.execute_strictly_safe(
        "CREATE TABLE transactions (id TEXT, status TEXT)", ()
    )
    
    evt = OrderPlacedEvent(order_id="ORD-9981-TX", total_amount=450000.0)
    
    # Type check mengonfirmasi OrderPlacedEvent memenuhi kontrak DomainEvent
    result = process_order_event(evt, db_client)
    print(f"Eksekusi pipeline sukses: {result}")
```

---

## 8. Real World Case Study: FinTech Ledger Core Transaction Engine

### Masalah Arsitektural
Sebuah bank digital memproses miliaran rupiah per jam melalui sistem ledger transaksinya. Bug pada rilis sebelumnya menyebabkan dua masalah fatal:
1. Mutasi status tidak valid: Transaksi pending bisa langsung berubah menjadi `Settled` melompati status `Authorized`, memicu *unreconciled funds*.
2. Kerentanan SQL Injection: Pembuatan query rekonsiliasi yang menggabungkan string filter dinamis tanpa preparasi statement.

### Solusi Desain
Penerapan sistem tipe berbasis:
- **Phantom Types & Type States:** Merepresentasikan status state machine di level compile time untuk memblokir mutasi ilegal.
- **`LiteralString` Enforcement:** Memvalidasi seluruh engine query ORM/Core.
- **Custom Typed Data Structures:** Mencegah mutasi concurrency dan memory overhead via slots dan type enforcement.

```python
"""
FinTech Enterprise Type-Safe Ledger State Transition Engine.
Menerapkan Type-State Pattern menggunakan Generics dan Phantom Types.
"""
from __future__ import annotations

import decimal
from dataclasses import dataclass
from typing import Generic, LiteralString, NoReturn, TypeVar

# Type states (Phantom Types)
class PendingState: ...
class AuthorizedState: ...
class SettledState: ...
class ReversedState: ...

StateT = TypeVar("StateT")
NextStateT = TypeVar("NextStateT")

class LedgerError(Exception): ...

@dataclass(frozen=True, slots=True)
class Money:
    amount: decimal.Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < decimal.Decimal("0.00"):
            raise LedgerError("Amount cannot be negative.")

@dataclass(frozen=True, slots=True)
class LedgerEntry(Generic[StateT]):
    transaction_id: str
    account_id: str
    money: Money
    # Field state murni ada di domain type system untuk compile-time check

class LedgerTransactionManager:
    @staticmethod
    def create_pending(tx_id: str, account_id: str, money: Money) -> LedgerEntry[PendingState]:
        return LedgerEntry[PendingState](
            transaction_id=tx_id,
            account_id=account_id,
            money=money
        )

    @staticmethod
    def authorize(
        entry: LedgerEntry[PendingState]
    ) -> LedgerEntry[AuthorizedState]:
        """HANYA LedgerEntry[PendingState] yang diizinkan masuk ke method ini."""
        return LedgerEntry[AuthorizedState](
            transaction_id=entry.transaction_id,
            account_id=entry.account_id,
            money=entry.money
        )

    @staticmethod
    def settle(
        entry: LedgerEntry[AuthorizedState]
    ) -> LedgerEntry[SettledState]:
        """HANYA LedgerEntry[AuthorizedState] yang diizinkan untuk di-settle."""
        return LedgerEntry[SettledState](
            transaction_id=entry.transaction_id,
            account_id=entry.account_id,
            money=entry.money
        )

    @staticmethod
    def reverse(
        entry: LedgerEntry[AuthorizedState] | LedgerEntry[PendingState]
    ) -> LedgerEntry[ReversedState]:
        return LedgerEntry[ReversedState](
            transaction_id=entry.transaction_id,
            account_id=entry.account_id,
            money=entry.money
        )

# ============================================================================
# Runtime Verification vs Compile-time Verification Demo
# ============================================================================

def run_ledger_pipeline() -> None:
    tx = LedgerTransactionManager.create_pending(
        tx_id="TXN-001",
        account_id="ACC-ID-8812",
        money=Money(decimal.Decimal("15000000.00"), "IDR")
    )
    
    # 1. State Flow Normal: Pending -> Authorized -> Settled
    auth_tx = LedgerTransactionManager.authorize(tx)
    settled_tx = LedgerTransactionManager.settle(auth_tx)
    print(f"Transaction Finalized: {settled_tx.transaction_id}")

    # 2. State Bypass Ilegal: Pending -> Settled Langsung
    # JIKA BARIS BERIKUT DIBUKA, STATIC TYPE CHECKER AKAN LANGSUNG GAGAL:
    # LedgerTransactionManager.settle(tx)
    # ---------------------------------------------------------------------
    # ERROR TYPE CHECKER:
    # Argument 1 to "settle" of "LedgerTransactionManager" has incompatible 
    # type "LedgerEntry[PendingState]"; expected "LedgerEntry[AuthorizedState]"
    # ---------------------------------------------------------------------

if __name__ == "__main__":
    run_ledger_pipeline()
```

---

## 9. Trade-offs: Architecture Matrix

| Strategi / Metrik | Performa Runtime (Latency/Memory) | Developer Velocity (Waktu Build/Coding) | Strictness Safety Level | Rekomendasi Penggunaan Enterprise |
|---|---|---|---|---|
| **Pydantic V2 Models** | Rendah-Sedang (C-core parsing via Rust, alokasi objek runtime ada). | Sangat Tinggi (Validasi runtime otomatis, parsing JSON instan). | Tinggi (Runtime + Static typing). | Domain Boundaries, Ingress HTTP payloads, Microservice I/O. |
| **Dataclasses (`slots=True`)** | Sangat Tinggi (Alokasi memory minimal, no overhead validation). | Tinggi (Cepat dibuat, standar library native). | Sedang-Tinggi (Static typing via IDE/MyPy, no runtime check). | Domain Core Business Logic, Internal Services, High-throughput Compute. |
| **`typing.TypedDict`** | Maksimal (Zero overhead, murni standard Python dictionary). | Rendah-Sedang (Manipulasi verbose, tidak ada method class). | Sedang (Static check only). | Parsing data JSON mentah berukuran besar tanpa modifikasi schema. |
| **`typing.Protocol`** | Maksimal (Zero cost, kecuali dipakai dengan `@runtime_checkable`). | Tinggi (Decoupled modules, no common ancestors needed). | Sangat Tinggi (Static Duck Typing murni). | Plugin architecture, SDK interfaces, dependency injection boundary. |
| **Nominal ABC (`abc.ABC`)** | Sedang (Overhead traversal pada dynamic subclass checks). | Rendah (Kopling inheritance tinggi, brittle base class). | Sedang (Terkekang hierarki pewarisan kaku). | Legacy frameworks, driver inheritance tunggal. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Invariant Generic Assignment Failure
```python
# SALAH
def process_numbers(data: list[object]) -> None:
    data.append("injected_string")

numbers: list[int] = [1, 2, 3]
process_numbers(numbers) # MyPy Error! list[int] bukan list[object]
```
- **Penyebab:** `list[T]` bersifat *invariant*. Mengizinkan `list[int]` diperlakukan sebagai `list[object]` akan merusak integritas `list[int]` ketika objek non-integer disisipkan.
- **Solusi:** Gunakan read-only generic interface jika tidak ada operasi mutasi penambahan:
```python
# BENAR
from collections.abc import Sequence

def process_numbers(data: Sequence[object]) -> None:
    for item in data:
        print(item)

numbers: list[int] = [1, 2, 3]
process_numbers(numbers) # Lolos! Sequence[+T] bersifat covariant.
```

### 10.2 Circular Import Hell Akibat Type Hinting
- **Gejala:** `ImportError: cannot import name 'X' from partially initialized module`
- **Troubleshooting & Remediasi:**
  1. Pisahkan dependensi tipe menggunakan blok `typing.TYPE_CHECKING`.
  2. Gunakan `from __future__ import annotations` untuk mencegah evaluasi tipe runtime.

```python
# BENAR (user_service.py)
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.order_service import OrderService

class UserService:
    def __init__(self, order_service: OrderService) -> None:
        self.order_service = order_service
```

### 10.3 Performa Rusak Akibat `@runtime_checkable`
- **Gejala:** Drop throughput transaksi drastis pada loop berskala jutaan iterasi saat menggunakan `isinstance(obj, MyProtocol)`.
- **Akar Masalah:** `@runtime_checkable` memeriksa kehadiran setiap metode dan atribut via `getattr()` dan `inspect` pada setiap pemanggilan `isinstance()`, yang berkali-kali lipat lebih lambat dibanding *type check* native C.
- **Solusi:** Batasi `@runtime_checkable` hanya pada *boundary ingress initialization* atau *dependency wiring lifecycle*. Jangan panggil di dalam hot execution loop!

---

## 11. Best Practices (Production Checklist)

| No | Kategori | Checklist Action Item | Tooling Enforcer |
|:---|:---|:---|:---|
| 1 | Konfigurasi | Pasang flag `--strict` pada MyPy secara default di seluruh repositori. | `mypy.ini` |
| 2 | Zero Any | Dilarang keras menggunakan `Any` tanpa review arsitektur; gunakan `unknown` (Pyright) atau bounded `TypeVar`. | `disallow_any_explicit = true` |
| 3 | Immutability | Prioritaskan `Mapping` dan `Sequence` dibanding `dict` dan `list` pada function parameters. | `Ruff / MyPy` |
| 4 | Optimization | Aktifkan `from __future__ import annotations` di seluruh modul baru untuk menghemat startup cost. | `Ruff (FA100)` |
| 5 | Security | Bungkus seluruh eksekusi raw SQL, Process Subprocess, dan Eval API menggunakan `LiteralString`. | `MyPy PEP 675` |
| 6 | Decorator Type | Jangan gunakan `Callable[..., Any]`; gunakan `ParamSpec` dan `Concatenate` untuk decorator signature preservation. | Code Review / MyPy |
| 7 | Static CI Gate | Blokir merge PR jika terdapat error tipe atau warning dari static analyzer. | GitHub Actions / GitLab CI |

---

## 12. Hands-on Practice: Membangun Production-Grade Typing Gate

Struktur direktori kerja:
```
hands-on/m02/
├── pyproject.toml
├── mypy.ini
└── src/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   └── engine.py
    └── main.py
```

### Langkah 1: Inisialisasi Environment & Konfigurasi Ekstrem
Buat file `hands-on/m02/mypy.ini`:
```ini
[mypy]
python_version = 3.12
strict = True
disallow_any_generics = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_return_any = True
warn_unreachable = True
show_error_codes = True
```

### Langkah 2: Buat Type-Safe Context Engine
Tulis di `hands-on/m02/src/core/engine.py`:
```python
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Concatenate, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

class ExecutionContext:
    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id

def traced(
    func: Callable[Concatenate[ExecutionContext, P], R]
) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        ctx = ExecutionContext(trace_id=f"tx-{int(time.time())}")
        return func(ctx, *args, **kwargs)
    return wrapper
```

### Langkah 3: Implementasi Konsumen
Tulis di `hands-on/m02/src/main.py`:
```python
from __future__ import annotations

from src.core.engine import ExecutionContext, traced

@traced
def calculate_payout(ctx: ExecutionContext, base_val: float, multiplier: float) -> float:
    print(f"Running Trace: {ctx.trace_id}")
    return base_val * multiplier

if __name__ == "__main__":
    result = calculate_payout(1000.0, 1.25)
    print(f"Payout Result: {result}")
```

### Langkah 4: Validasi Statis Komprehensif
Jalankan validasi via shell terminal Anda:
```bash
cd hands-on/m02
mypy --config-file mypy.ini src/
```
Output yang harus muncul:
```text
Success: no issues found in 3 source files
```

---

## 13. Exercises

### Level Easy
Modifikasi kelas kontainer antrian berikut agar bersifat **Covariant**. Pastikan data hanya dapat dibaca dan MyPy tidak mengeluarkan error saat instance `ImmutableQueue[int]` di-pass ke variabel beranotasi `ImmutableQueue[object]`.
```python
# Task: Modifikasi definisi kelas dan type parameter di bawah!
class ImmutableQueue:
    def __init__(self, items):
        self._items = tuple(items)
        
    def dequeue_all(self):
        return self._items
```
*Solusi Konseptual:* Buat `T = TypeVar("T", covariant=True)`, definisikan `class ImmutableQueue(Generic[T])`, dan berikan tipe anotasi kembalian `tuple[T, ...]`.

### Level Medium
Buatlah custom decorator `@retry_with_fallback(fallback_value: R)` yang menerima fallback bernilai generic `R`. Decorator ini harus menjaga metadata tanda tangan fungsi asli secara persis (`ParamSpec`), tetapi jika pemanggilan fungsi memicu exception, decorator akan mengembalikan `fallback_value`. Anotasikan fungsi wrapper sehingga type checker tahu bahwa nilai return wrapper identik dengan return value target fungsi.

### Level Hard
Rancang modul Mini-ORM query builder yang memiliki satu fungsi:
```python
def select(table: LiteralString, *columns: LiteralString) -> QueryBuilder: ...
```
Dan implementasikan chaining method `.where(condition: LiteralString, *params: Any)`.
Query builder ini harus:
1. Menolak penggabungan format string dinamis (`f"SELECT * FROM {user_input}"`) di static analysis check.
2. Memanfaatkan `TypeVarTuple` / `Unpack` (PEP 646) untuk mendefinisikan skema tuple tipe data yang dikembalikan oleh kueri secara statis.

---

## 14. Challenge: Zero-Drift Type-Safe Dynamic RPC Engine

### Skenario Kasus Arsitektural
Perusahaan Anda memiliki kebutuhan komunikasi RPC internal. Saat ini pertukaran payload menggunakan dictionary rentan typo, serialization deserialization lambat, dan tidak memiliki penjaminan kontrak.

### Spesifikasi Kebutuhan Teknis
1. **Zero-Drift RPC Contract:** Buat sistem routing RPC berbasis class di mana client dan server menggunakan satu deklarasi `Protocol` tunggal.
2. **Signature Reflection & Validation:** Client proxy RPC tidak boleh mendefinisikan method secara manual satu per satu. Anda wajib membuat factory function generic `create_rpc_client[TProtocol](endpoint: str) -> TProtocol` yang menggunakan meta-typing dinamis.
3. **Full Type Inference:** Setiap method yang dipanggil via client proxy harus otomatis memunculkan auto-complete tipe parameter dan return types di IDE (Pyright/VS Code & MyPy) tanpa kode client di-generate via file proto.
4. **Compile-time Security:** URL method RPC hanya boleh dibentuk via `LiteralString` untuk mencegah dispatch route injection.

*Tantangan:* Selesaikan requirement di atas tanpa menggunakan `eval()`, tanpa auto-generated stub `.pyi` files eksternal, dan kode harus lolos inspeksi `mypy --strict`.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Dasar (Basic)
1. **Apa implikasi utama dari *Type Erasure* pada runtime CPython?**
   - *Jawaban:* CPython Virtual Machine (`ceval.c`) tidak memvalidasi kecocokan anotasi tipe saat eksekusi bytecode; seluruh anotasi hanya disimpan di namespace atribut tanpa memblokir runtime bila terjadi mismatch, kecuali dievaluasi manual oleh developer/library pihak ketiga.

2. **Apa perbedaan fungsional antara `Nominal Subtyping` dan `Structural Subtyping`?**
   - *Jawaban:* Nominal subtyping mewajibkan subkelas mewarisi superkelasnya secara eksplisit dalam hierarki inheritance (`class A(B)`), sedangkan Structural subtyping (`typing.Protocol`) hanya mensyaratkan kesesuaian atribut dan metode tanpa keterikatan hierarki inheritance.

3. **Mengapa `list[T]` dideklarasikan secara *Invariant* dalam standard library Python?**
   - *Jawaban:* Karena `list` adalah mutable container yang mendukung operasi baca dan tulis. Jika dibuat covariant, tipe yang salah dapat disuntikkan ke dalam list; jika contravariant, tipe yang diekstrak tidak dapat dijamin keabsahan tipenya.

4. **Kapan Anda wajib menggunakan `typing.LiteralString` (PEP 675)?**
   - *Jawaban:* Saat menerima argumen string sensitif yang akan diteruskan ke execution sink (seperti database SQL query, command line sub-process, atau evaluasi regex), demi menjamin string tersebut dibuat secara statis oleh developer dan bebas dari injeksi data dinamis.

5. **Apa fungsi dari konstanta `typing.TYPE_CHECKING`?**
   - *Jawaban:* Nilai boolean yang bernilai `False` saat aplikasi berjalan normal di runtime, namun bernilai `True` bagi static type checker (MyPy/Pyright), memungkinkan impor modul hanya untuk kebutuhan anotasi tipe tanpa memicu overhead sirkular import runtime.

### Bagian B: Menengah (Intermediate)
6. **Jelaskan perbedaan mendasar antara `TypeVar` biasa dan `ParamSpec` (PEP 612).**
   - *Jawaban:* `TypeVar` merepresentasikan satu tipe data spesifik (atau relasi subtyping tunggal), sedangkan `ParamSpec` merepresentasikan seluruh parameter signature (kombinasi args dan kwargs) dari sebuah callable secara utuh.

7. **Bagaimana relasi subtyping yang benar untuk parameter fungsi dan return value fungsi (Higher Order Functions)?**
   - *Jawaban:* Parameter fungsi bersifat *Contravariant* terhadap argument yang diterima, sedangkan Return value fungsi bersifat *Covariant* terhadap tipe kembaliannya.

8. **Apa kerugian arsitektural menggunakan `typing.Any` secara berulang dalam repositori enterprise?**
   - *Jawaban:* `Any` mematikan algoritma static inference (*type blindness*), menular (*infectious*) ke seluruh variabel yang berinteraksi dengannya, dan meniadakan jaminan keamanan tipe statis yang semestinya disediakan oleh CI gate.

9. **Apa kegunaan dari `typing.Self` yang diperkenalkan pada PEP 673?**
   - *Jawaban:* Memudahkan anotasi method fluent-interface atau method chaining yang mengembalikan instance dari kelas turunannya sendiri, tanpa perlu mendefinisikan boilerplate `TypeVar` terikat (bounded `TypeVar`).

10. **Kapan runtime error dapat terjadi saat menggunakan `from __future__ import annotations`?**
    - *Jawaban:* Saat library runtime (seperti Pydantic V1 atau Dependency Injector lawas) mencoba mengevaluasi dictionary string annotations menggunakan `eval()` atau `typeguard` pada scope lokal di mana tipe tersebut belum diimpor atau tidak ada di namespace eksekusi.

### Bagian C: Skenario Kasus Produksi
11. **Skenario 1:** Sebuah tim engineering mendapati deployment container mereka memakan waktu startup 20 detik lebih lama setelah menambahkan ratusan definisi schema Pydantic/dataclass yang kompleks di core internal modules. Setelah ditelusuri, seluruh schema saling diimpor di `__init__.py`. Bagaimana memitigasi startup latency ini tanpa menghapus type safety?
    - *Solusi:*
      1. Terapkan `from __future__ import annotations` pada seluruh modul untuk menonaktifkan parsing anotasi saat cold import module.
      2. Terapkan *lazy-loading* pattern untuk schema dan pisahkan type-only dependencies ke dalam blok `if TYPE_CHECKING:`.
      3. Hindari circular imports dan barrel re-export (`__all__` masif di root packages) yang memaksa CPython meng-compile seluruh AST generic models pada cold boot.

12. **Skenario 2:** Pada microservice berorientasi event, sebuah handler function sering crash dengan `AttributeError: 'NoneType' object has no attribute 'x'`, meskipun static checking sebelumnya dinyatakan passed. Di mana kemungkinan celah pipeline validasi statis mereka?
    - *Solusi:*
      1. Konfigurasi MyPy belum menyertakan `no_implicit_optional = True` dan `strict_optional = True`, sehingga variabel bertipe `Optional[T]` diizinkan mengakses properti tanpa pengecekan exhaustiveness `if obj is not None:`.
      2. Adanya cast eksplisit menggunakan `typing.cast()` atau data mentah dari deserializer `json.loads()` yang langsung diberi type annotation tanpa melalui parser schema (seperti Pydantic atau dynamic TypeGuard PEP 647).

13. **Skenario 3:** CI/CD pipeline memakan waktu 15 menit hanya untuk langkah `mypy .`. Tim mengeluh kecepatan deployment melambat. Rekomendasikan perubahan arsitektur pipeline pengetikan!
    - *Solusi:*
      1. Terapkan **MyPy Daemon (`dmypy`)** yang menggunakan caching dependency tracking berbasis in-memory daemon.
      2. Pisahkan pipeline: Gunakan **Pyright** untuk analisis super cepat di pre-commit dan pull-request feedback loop (berbasis multithreaded architecture), dan jalankan MyPy strict check hanya pada build image pipeline akhir.
      3. Aktifkan cache directory `--cache-dir` di CI runner (misalnya GitHub Actions Cache) agar MyPy tidak menganalisis ulang AST package yang tidak bermutasi.

---

## 16. Summary

- **Static Type Safety di Python adalah Zero-Cost Abstraction:** CPython mengeksekusi aplikasi secara dinamis; seluruh enforcement pengetikan statis terjadi di fase linting dan kompilasi CI/CD, menghapus runtime tax saat arsitektur disusun dengan benar.
- **Variansi adalah Aturan Main Arsitektur Data:** Invariance untuk wadah mutabel (Read/Write), Covariance untuk aliran produsen (Read-Only), dan Contravariance untuk konsumen fungsional (Write-Only). Pelanggaran terhadap variansi adalah sumber utama bug runtime tersembunyi.
- **Structural Typing (`Protocol`) Memutus Tight Coupling:** Enterprise code harus mengadopsi interface yang ramping berbasis behavior, bukan inheritance kaku. `Protocol` memungkinkan testing mock dan decoupled microservice libraries bekerja selaras tanpa inheritance dependencies.
- **LiteralString Memblokir Injeksi di Level Kompilasi:** Keamanan kode modern menggeser audit kerentanan injeksi (SQLi, Command Injection) dari runtime WAF ke static analysis layer menggunakan PEP 675.
- **Tooling Rigor:** Ekosistem enterprise wajib mengunci kualitas kode menggunakan multi-layer checks: Pyright untuk feedback instan, MyPy Strict Mode untuk validasi formal dalam CI, dan Ruff untuk penegakan standar AST/PEP secara instan.