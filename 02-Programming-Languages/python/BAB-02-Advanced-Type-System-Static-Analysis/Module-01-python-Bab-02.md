# SEKSI 01 — IDENTITAS MODUL

| Atribut | Nilai |
| :--- | :--- |
| **Kategori** | 02-Programming-Languages |
| **Kurikulum** | Python Software Engineering & Systems Architecture |
| **Bab / Modul** | Bab 02 Module 01 |
| **Topik** | Advanced Type System & Static Analysis |
| **Tingkat Kesulitan** | Advanced / Production-Grade |
| **Prasyarat Konseptual** | Object-Oriented Python, First-class Functions, Decorator Internals, Basic Type Hinting (`int`, `str`, `List`, `Dict`) |
| **Target Runtime / Toolchain** | Python 3.10 – 3.12+, Mypy (Strict Mode), Pyright, Ruff |

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis & Mengonfigurasi Subtyping Formal**: Menguraikan perbedaan matematis dan praktis antara *Nominal Subtyping* (`abc.ABCMeta`) dan *Structural Subtyping* (`typing.Protocol`), serta menerapkannya sesuai batas arsitektur sistem.
2. **Menguasai Kalkulus Variansi (Variance Calculus)**: Mengidentifikasi dan memecahkan masalah subtyping generics melalui aturan *Invariance*, *Covariance* ($+T$), dan *Contravariant* ($-T$) berdasarkan Liskov Substitution Principle (LSP).
3. **Membangun Abstraksi Higher-Order Type-Safe**: Mengonstruksi decorator dan wrapper fungsi yang mempreservasi signature parameter dan return type secara sempurna menggunakan `ParamSpec` dan `Concatenate` (PEP 612).
4. **Menerapkan Custom Type Narrowing**: Merancang mekanisme type discrimination menggunakan `TypeGuard` (PEP 647) dan `TypeIs` (PEP 742) untuk memvalidasi payload dinamis pada *runtime boundary*.
5. **Mengintegrasikan Pipeline Static Analysis CI/CD**: Menyusun konfigurasi deterministik untuk Mypy dan Pyright pada *codebase* skala enterprise tanpa menggunakan *type escapism* (`Any`, `# type: ignore`).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Gradual Typing Bukan Dynamic Casting
Python mengadopsi model *gradual typing*. Type hints tidak dieksekusi oleh Python Virtual Machine (C-API) sebagai instruksi *type enforcement* saat runtime secara default. Type hints adalah metadata deklaratif (*first-class runtime objects*) yang dikonsumsi oleh mesin pembuktian matematis eksternal (*static type checkers*).

```
          [ Static Analysis Phase (Mypy / Pyright) ]
         Compile-time / Pre-commit / CI Verification
                           │
       Tipe Salah? ───> Tolak Build (Type Error)
                           │ Lolos
                           ▼
              [ Runtime Phase (CPython VM) ]
         Annotations Stripped / Lazily Evaluated
                           │
             Dynamic Duck-Typing Execution
```

### Mental Model: Dualitas Tipe vs Objek
1. **Objek Runtime:** Struktur C-struct (`PyObject`) dengan pointer ke `ob_type`. Tidak mengetahui konteks generik (e.g., `list[str]` hanya berupa `list` di memori CPython).
2. **Tipe Statis:** Konstruk teoritis tipe himpunan (*set-theoretic types*). Subtipe $S <: T$ berarti himpunan nilai $S$ adalah subset dari nilai $T$.
3. **Soundness vs Ergonomics:** Type system Python bersifat *unsound by design* untuk mempertahankan fleksibilitas meta-programming, namun dapat diubah menjadi *strictly sound* pada domain logic inti melalui penerapan static analysis ketat.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur hidup anotasi tipe dari kode sumber, AST, verifikasi statis, hingga evaluasi bytecode runtime:

```
[Source Code: .py]
       │
       ▼
 [CPython Parser] ──────> [AST Generation] (ast.FunctionDef, ast.AnnAssign)
       │                         │
       │                         ├────────────────────────────────────────┐
       │ (Static Check Path)     │                                        │ (Runtime Path)
       ▼                         ▼                                        ▼
[Static Type Checker]      [PEP 563 / PEP 649]                      [Bytecode Compiler]
(Mypy / Pyright Engine)    Inspect __annotations__                  (compile to PyCodeObject)
       │                         │                                        │
  [Symbol Table]                 ├─ Real Object: type                     ▼
       │                         └─ Stringized: "Union[T, int]"     [CPython VM Execution]
  [Constraint Solver]                                                     │
       │                                                                  ├─ Evaluasi Logic
  [Liskov/Variance Check]                                                 └─ Runtime Overhead
       │                                                                     HANYA terjadi jika
 ┌─────┴──────────────┐                                                      __annotations__
 │                    │                                                      diakses reflektif
[PASS]             [FAIL]
 (CI Green)     (CI Exit Code 1)
```

### Type Inference Pipeline pada Static Checker

```
Expression Input ──> Unification Algorithm ──> Type Constraint Generation
                                                      │
                                                      ▼
Narrowed Type   <── Conditional Branching  <── Constraint Resolution
(via TypeGuard)      (Type Narrowing)
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Representasi Internal Anotasi (`__annotations__`)
Setiap modul, kelas, dan fungsi memiliki dictionary `__annotations__`. Sejak PEP 563 (`from __future__ import annotations`), anotasi disimpan secara literal sebagai `str` untuk mencegah runtime overhead dan circular dependency. PEP 649 (Python 3.14+) memperkenalkan evaluasi *deferred on demand* via descriptors.

```python
# Demo Internal Runtime Anotasi
def process_data(payload: dict[str, int]) -> bool:
    return bool(payload)

# CPython menyimpan anotasi sebagai dictionary objek:
print(process_data.__annotations__)
# Output jika tanpa future annotations: {'payload': dict[str, int], 'return': <class 'bool'>}
# Output dengan `from __future__ import annotations`: {'payload': 'dict[str, int]', 'return': 'bool'}
```

### 2. Generics Metaclass (`_GenericAlias` & `Generic`)
Saat membuat kelas generik, kelas tersebut mewarisi `typing.Generic`. Subscripting (misal `Container[T]`) memanggil metode kelas internal `__class_getitem__`. Objek yang dihasilkan bukan kelas baru, melainkan instance dari `typing._GenericAlias`.

```
                    ┌─────────────────────────┐
                    │      typing.Generic     │
                    └────────────┬────────────┘
                                 │ subclass
                    ┌────────────▼────────────┐
                    │     BaseContainer[T]    │
                    └────────────┬────────────┘
                                 │ __class_getitem__(int)
                    ┌────────────▼────────────┐
                    │   _GenericAlias Object  │
                    │   (__origin__ = Base)   │
                    │   (__args__   = (int,)) │
                    └─────────────────────────┘
```

### 3. Syntax Python 3.12 (PEP 695) vs Legasi (PEP 484)
Python 3.12 mengeliminasi keharusan deklarasi manual `TypeVar`, `ParamSpec`, dan `TypeVarTuple` melalui keyword baru:

*   **PEP 484 (Legacy):**
    ```python
    from typing import TypeVar, Generic
    T = TypeVar('T', covariant=True)
    class Node(Generic[T]): ...
    ```
*   **PEP 695 (Modern 3.12+):**
    ```python
    class Node[T]: ...  # T secara default Invariant, infer otomatis
    type Point[T] = tuple[T, T]  # Statement type alias formal
    ```

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Structural Subtyping vs Nominal Subtyping
*   **Nominal Subtyping:** Relasi subtipe harus dinyatakan secara eksplisit melalui inheritance tree (`class Dog(Animal)`). Jika kelas $A$ tidak mewarisi $B$, maka $A$ bukan subtipe dari $B$, meskipun atribut dan metodenya identik.
*   **Structural Subtyping (Duck Typing Statis / `typing.Protocol`):** Didasarkan pada relasi bentuk (*shape*). Sebuah tipe $S$ adalah subtipe dari $T$ jika $S$ mengimplementasikan seluruh atribut dan signature metode yang didefinisikan pada $T$, tanpa perlu pewarisan formal.

### 2. Variansi Generik (Generic Variance)
Variansi mendefinisikan bagaimana relasi subtipe antara tipe-tipe komponen mempengaruhi relasi subtipe antara tipe generik kompleks yang membungkusnya.

Misalkan $Cat <: Animal$ ($Cat$ adalah subtipe dari $Animal$):

| Variansi | Definisi Matematis | Contoh Penggunaan | Aturan Desain (LSP) |
| :--- | :--- | :--- | :--- |
| **Invariance** | $G[Cat]$ dan $G[Animal]$ tidak memiliki hubungan subtipe. | `list[T]`, `dict[K, V]` | Digunakan saat container bersifat *read-write* (dapat membaca dan menambahkan elemen). |
| **Covariance** | $Cat <: Animal \implies G[Cat] <: G[Animal]$ | `Sequence[T]`, `Iterable[T]`, Immutable collections | Digunakan saat generic **hanya memproduksi/mengeluarkan** data ($T$ hanya sebagai return value). |
| **Contravariance** | $Cat <: Animal \implies G[Animal] <: G[Cat]$ | `Callable[[T], None]`, Consumer/Sink | Digunakan saat generic **hanya mengonsumsi/menerima** data ($T$ hanya sebagai argumen fungsi). |

### 3. Preservasi Call Signature: `ParamSpec` & `Concatenate`
Sebelum PEP 612, decorator yang membungkus fungsi dinamis akan menghancurkan informasi type safety signature pemanggil (mengharuskan penggunaan `Callable[..., T]`). `ParamSpec` menangkap variabel parameter signature (`*args`, `**kwargs`) sebagai satu kesatuan variabel tipe, sedangkan `Concatenate` memungkinkan mutasi parameter (misal: dependency injection) secara statically sound.

### 4. Custom Type Narrowing: `TypeGuard` vs `TypeIs`
*   `TypeGuard[T]` (PEP 647): Menyatakan jika fungsi mengembalikan `True`, maka tipe variabel dipersempit (*narrowed*) menjadi $T$. Namun, jika `False`, static checker **tidak** mempersempit tipe fallback secara ketat (asimetris).
*   `TypeIs[T]` (PEP 742, Python 3.13): Memberikan semantik penyempitan dua arah yang ketat (simetris). Jika evaluasi mengembalikan `False`, checker memotong $T$ dari tipe Union yang mungkin.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL (Step-by-step)

Skrip berikut mendemonstrasikan implementasi Structural Subtyping (`Protocol`), Variansi Generik (Covariance & Contravariance), serta Decorator Higher-Order yang aman via `ParamSpec` dan `Concatenate`.

```python
#!/usr/bin/env python3
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any, Concatenate, Generic, ParamSpec, Protocol, TypeVar

# ==========================================
# 1. VARIANCE: COVARIANCE & CONTRAVARIANCE
# ==========================================

class Entity:
    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id

class User(Entity):
    def __init__(self, entity_id: str, username: str) -> None:
        super().__init__(entity_id)
        self.username = username

# T_co bersifat COVARIANT: Hanya boleh menjadi output (read-only)
T_co = TypeVar("T_co", covariant=True)

class ReadOnlyRepository(Protocol[T_co]):
    def get_by_id(self, entity_id: str) -> T_co: ...
    def list_all(self) -> Sequence[T_co]: ...

# T_contra bersifat CONTRAVARIANT: Hanya boleh menjadi input (write-only)
T_contra = TypeVar("T_contra", contravariant=True)

class Sink(Protocol[T_contra]):
    def consume(self, item: T_contra) -> None: ...

# ==========================================
# 2. STRUCTURAL SUBTYPING: PROTOCOLS
# ==========================================

class MetricPayload(Protocol):
    timestamp: float
    name: str
    def serialize(self) -> dict[str, Any]: ...

class APILatencyMetric:
    """Implementasi tanpa inheritance formal dari MetricPayload."""
    def __init__(self, name: str, latency_ms: float) -> None:
        self.name = name
        self.latency_ms = latency_ms
        self.timestamp = time.time()

    def serialize(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "latency": self.latency_ms,
            "timestamp": self.timestamp,
        }

# ==========================================
# 3. HIGHER-ORDER TYPING: PARAMSPEC & CONCATENATE
# ==========================================

P = ParamSpec("P")
R = TypeVar("R")

class SecurityContext:
    def __init__(self, auth_token: str) -> None:
        self.auth_token = auth_token

def inject_security_context(
    fn: Callable[Concatenate[SecurityContext, P], R]
) -> Callable[P, R]:
    """
    Decorator yang menginjeksi SecurityContext sebagai argumen pertama.
    Signature fungsi hasil dekorasi kehilangan argumen SecurityContext dari perspektif caller.
    """
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        ctx = SecurityContext(auth_token="system-secure-token-xyz")
        return fn(ctx, *args, **kwargs)
    return wrapper

# Fungsi target yang membutuhkan security context
@inject_security_context
def create_user_profile(ctx: SecurityContext, username: str, email: str) -> User:
    print(f"[AUTH LOG] Running with token: {ctx.auth_token}")
    return User(entity_id="usr-1234", username=username)

# ==========================================
# 4. EXECUTION DRIVER
# ==========================================

def dispatch_metric(metric: MetricPayload) -> None:
    payload = metric.serialize()
    print(f"[METRIC DISPATCH] {payload}")

if __name__ == "__main__":
    # 1. Structural Subtyping Check
    latency_event = APILatencyMetric("db_query_time", 42.8)
    dispatch_metric(latency_event)

    # 2. ParamSpec/Concatenate Check
    # Caller tidak perlu mengirimkan 'ctx' karena sudah dikupas oleh dekorator
    new_user = create_user_profile("adrian_dev", "adrian@production.internal")
    print(f"[USER CREATED] ID: {new_user.entity_id}, Name: {new_user.username}")
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 2:** `from __future__ import annotations` mengaktifkan penundaan evaluasi type hint runtime (PEP 563), mengubah tipe menjadi string terisolasi untuk menghindari loop import sirkular dan memangkas overhead pemanggilan objek tipe.
*   **Baris 20:** `T_co = TypeVar("T_co", covariant=True)`. Menandai parameter generic `T_co` sebagai covariant. Dengan ini, instance bertipe `ReadOnlyRepository[User]` secara absah dapat digunakan di tempat yang membutuhkan `ReadOnlyRepository[Entity]` karena `User` adalah turunan dari `Entity`.
*   **Baris 22–24:** `ReadOnlyRepository(Protocol[T_co])`. Protokol mendefinisikan interface generik *read-only*. Penggunaan `T_co` sebagai return type fungsi diizinkan. Jika `T_co` ditempatkan sebagai argumen input (e.g., `def save(self, item: T_co)`), static checker akan melempar error variansi karena melanggar subtyping invariants.
*   **Baris 27:** `T_contra = TypeVar("T_contra", contravariant=True)`. Menandai tipe ini sebagai contravariant. Membalikkan relasi: consumer untuk `Entity` dapat bertindak sebagai consumer untuk `User`, karena `Sink[Entity]` sanggup memproses semua subtipe dari `Entity`.
*   **Baris 35–38:** `class MetricPayload(Protocol)`. Definisi structural subtyping. Menghilangkan coupling hierarki class. Kelas `APILatencyMetric` (Baris 40) tidak perlu secara eksplisit mewarisi `MetricPayload` (`class APILatencyMetric(MetricPayload)`). Static analyzer memvalidasi kecocokan atribut dan metode secara struktural pada waktu analisis.
*   **Baris 54–55:** `P = ParamSpec("P")` dan `R = TypeVar("R")`. Mendefinisikan penampung signature parameter penuh dan return type generic.
*   **Baris 62–64:** `Callable[Concatenate[SecurityContext, P], R] -> Callable[P, R]`. Inti dari PEP 612: Menyatakan bahwa fungsi input menerima `SecurityContext` diikuti oleh parameter arbitrary `P`. Namun return value fungsi wrapper mengekspos signature murni `Callable[P, R]`. Parameter `SecurityContext` dihilangkan dari surface interface luar.
*   **Baris 68:** `def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:`. Menjaga tuple positional args dan dictionary keyword args terikat identik secara statis ke caller asli.
*   **Baris 89:** Pemanggilan `create_user_profile("adrian_dev", ...)` lulus pemeriksaan statis Pyright/Mypy tanpa memerlukan argumen pertama `ctx`. Jika tipe parameter salah (misal: mengirimkan `int` ke `username`), static checker memicu failure sebelum eksekusi.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Kasus
Sebuah platform Financial Processing Engine berbasis microservices menangani event transaksi dengan struktur data heterogen dari berbagai gateway pembayaran (Stripe, Adyen, ISO8583 Banking Switch).

### Problem Arsitektur
1. Pipeline pemrosesan menggunakan event bus asinkron internal. Payload event seringkali dioperasikan menggunakan tipe `dict[str, Any]`, yang menyebabkan tingginya insiden *runtime bugs* (`KeyError`, `AttributeError`) di level production.
2. Handler event membutuhkan state contextual (misal: database session, correlation ID, tracing spans) tanpa mencemari representasi data event itu sendiri.
3. Validator payload harus memvalidasi data dinamis yang masuk dari serialisasi JSON sebelum dialirkan ke safe-domain pipeline, tanpa mengorbankan performa decoding serial runtime.

### Solusi Teknis
Membangun **Type-Safe In-Memory Event Streaming Engine**:
*   Mendefinisikan Protokol Event Struktural (`EventStream`).
*   Menggunakan `TypeGuard` / `TypeIs` untuk narrowing runtime payload parsing dari payload mentah.
*   Menggunakan Generic Event Handlers dengan batasan type bounds (`T_co`).
*   Menjamin type soundness via compile-time verification tanpa overhead parsing runtime Pydantic di internal core looping.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```python
#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeGuard, TypeVar

# ============================================================================
# 1. CORE DOMAIN TYPES & STRUCTURAL PROTOCOLS
# ============================================================================

@dataclass(frozen=True)
class TransactionAuthorizedEvent:
    transaction_id: str
    account_id: str
    amount_cents: int
    currency: str

@dataclass(frozen=True)
class FraudSuspectedEvent:
    transaction_id: str
    risk_score: float
    flag_reasons: tuple[str, ...]

T_Event = TypeVar("T_Event", covariant=True)

class EventEnvelope(Generic[T_Event]):
    """Immutable envelope dengan covariant event data."""
    def __init__(self, trace_id: str, event_data: T_Event) -> None:
        self._trace_id = trace_id
        self._event_data = event_data

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def payload(self) -> T_Event:
        return self._event_data

# ============================================================================
# 2. TYPE NARROWING GUARDS (RUNTIME-TO-STATIC BOUNDARY)
# ============================================================================

def is_authorized_event_dict(payload: dict[str, Any]) -> TypeGuard[dict[str, Any]]:
    """
    Validasi runtime untuk memastikan data mentah memiliki
    skema kunci yang benar untuk TransactionAuthorizedEvent.
    """
    required_keys = {"transaction_id", "account_id", "amount_cents", "currency"}
    if not required_keys.issubset(payload.keys()):
        return False
    return (
        isinstance(payload["transaction_id"], str)
        and isinstance(payload["account_id"], str)
        and isinstance(payload["amount_cents"], int)
        and isinstance(payload["currency"], str)
    )

def parse_authorized_event(raw_data: dict[str, Any]) -> TransactionAuthorizedEvent:
    if not is_authorized_event_dict(raw_data):
        raise ValueError(f"Schema violation for raw payload: {raw_data}")
    
    # Static Analyzer mengetahui data sudah tervalidasi
    return TransactionAuthorizedEvent(
        transaction_id=raw_data["transaction_id"],
        account_id=raw_data["account_id"],
        amount_cents=raw_data["amount_cents"],
        currency=raw_data["currency"]
    )

# ============================================================================
# 3. HIGH-PERFORMANCE TYPE-SAFE EVENT BUS
# ============================================================================

E_contra = TypeVar("E_contra", contravariant=True)

class EventHandler(Generic[E_contra]):
    """Handler contravariant: siap menerima event atau supertipe event tersebut."""
    async def handle(self, envelope: EventEnvelope[E_contra]) -> None:
        raise NotImplementedError

class LedgerPostingHandler(EventHandler[TransactionAuthorizedEvent]):
    async def handle(self, envelope: EventEnvelope[TransactionAuthorizedEvent]) -> None:
        txn = envelope.payload
        print(
            f"[LEDGER] [Trace: {envelope.trace_id}] Posting {txn.amount_cents} {txn.currency} "
            f"to Account: {txn.account_id} for Txn: {txn.transaction_id}"
        )

class UniversalAuditHandler(EventHandler[object]):
    """Handler universal: Menerima sembarang object event via contravariance."""
    async def handle(self, envelope: EventEnvelope[object]) -> None:
        print(f"[AUDIT LOG] [Trace: {envelope.trace_id}] Type: {type(envelope.payload).__name__}")

# ============================================================================
# 4. DISPATCH ENGINE PIPELINE
# ============================================================================

class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Any], list[Callable[[EventEnvelope[Any]], Awaitable[None]]]] = {}

    def register_handler(
        self,
        event_type: type[T_Event],
        handler: Callable[[EventEnvelope[T_Event]], Awaitable[None]]
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, envelope: EventEnvelope[Any]) -> None:
        event_cls = type(envelope.payload)
        registered = self._handlers.get(event_cls, [])
        if not registered:
            print(f"[BUS] Warning: No direct handler registered for {event_cls.__name__}")
            return
        
        # Eksekusi konkurensi aman
        await asyncio.gather(*(h(envelope) for h in registered))

# ============================================================================
# 5. INTEGRATION TEST EXECUTION
# ============================================================================

async def main() -> None:
    bus = EventBus()
    ledger_handler = LedgerPostingHandler()
    audit_handler = UniversalAuditHandler()

    # Registrasi Type-Safe
    bus.register_handler(TransactionAuthorizedEvent, ledger_handler.handle)
    bus.register_handler(TransactionAuthorizedEvent, audit_handler.handle)

    # Ingestion Payload mentah dari Gateway Eksternal
    raw_incoming_network_payload: dict[str, Any] = {
        "transaction_id": "tx_99824219",
        "account_id": "acc_corporate_01",
        "amount_cents": 5000000,
        "currency": "EUR"
    }

    # Transformasi boundary melalui TypeGuard
    clean_event = parse_authorized_event(raw_incoming_network_payload)
    envelope = EventEnvelope(trace_id="req-trace-uuid-8899", event_data=clean_event)

    # Pipeline Processing
    await bus.publish(envelope)

if __name__ == "__main__":
    asyncio.run(main())
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### 1. Nominal (ABC) vs Structural (Protocol) Typing

| Parameter | Nominal Typing (`abc.ABC`) | Structural Typing (`typing.Protocol`) |
| :--- | :--- | :--- |
| **Kopling Arsitektur** | Sangat Tinggi. Subkelas harus mengimpor dan mewarisi base class secara eksplisit. | Nol / Decoupled. Dependensi murni berbasis signature atribut/metode. |
| **Runtime Enforcement** | Kuat via `abc.abstractmethod` saat inisialisasi instance (`TypeError` langsung). | Lemah secara runtime tanpa `@runtime_checkable` (membutuhkan biaya `isinstance` tinggi). |
| **Kesesuaian Third-Party** | Rendah. Tidak bisa membuat library eksternal mewarisi ABC internal kita. | Sangat Tinggi. Bisa memvalidasi class eksternal tanpa mengubah definisinya. |
| **Kecepatan Static Analysis** | Sangat cepat (hanya traversal class MRO). | Membutuhkan resolusi structural matching oleh type checker (sedikit lebih lambat). |

### 2. Runtime Validation vs Static Analysis Validation

| Dimensi | Static Analysis (Mypy / Pyright) | Runtime Metaprogramming (`pydantic` / `beartype`) |
| :--- | :--- | :--- |
| **Overhead CPU** | **0.00 ns** saat runtime production. | 100ns – 25µs per instansiasi objek / parsing payload. |
| **Waktu Deteksi** | Pre-commit, linting time, CI pipeline. | Saat runtime (bergantung pada edge case eksekusi nyata). |
| **Lingkup Perlindungan** | Menjamin tipe internal antar modul Python. | Menjamin integritas payload I/O tak terpercaya (JSON API, DB). |
| **Rekomendasi Arsitektur** | Gunakan Mypy Strict di 100% domain logic internal. | Pasang batas runtime check **hanya** di pintu masuk I/O (API boundaries). |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Mutasi Variansi pada Koleksi Generik
Kesalahan krusial dalam kalkulus variansi terjadi ketika koleksi mutable diasumsikan covariant.

```python
# CONTOH BUG: Jika list diasumsikan Covariant
def append_evil(items: list[object]) -> None:
    items.append("INTRUDER_STRING")

int_list: list[int] = [1, 2, 3]

# JIKA Mypy mengizinkan ini (untungnya DITOLAK karena list[T] adalah INVARIANT):
# append_evil(int_list)
# int_list.append(...) -> Sekarang int_list berisi string, runtime selanjutnya crash!
```
*Aturan Mutlak:* Semua struktur data yang mutable **harus invariant**. Koleksi immutable (seperti `Sequence[T]`, `Mapping[K, V]`, atau custom frozen classes) dapat dijadikan **covariant**.

### 2. Evaluasi Sirkular dengan `typing.TYPE_CHECKING`
Ketika Module A mengimpor Module B hanya untuk anotasi tipe, dan sebaliknya:
```python
# module_a.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from module_b import ServiceB

class ServiceA:
    def __init__(self, b: ServiceB) -> None:
        self.b = b
```
*Solusi & Pitfall:* Variabel `TYPE_CHECKING` selalu bernilai `False` saat runtime Python dieksekusi, sehingga import sirkular terhindar. Namun, jika ada kode runtime yang mencoba memanggil `get_type_hints(ServiceA)` tanpa penanganan exception, interpreter akan melempar `NameError: name 'ServiceB' is not defined`. Gunakan `typing.get_type_hints(ServiceA, localns=...)` untuk mitigasi.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Rusaknya Call Signature pada Decorator
*Praktek Buruk:*
```python
def bad_logger(fn: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)
    return wrapper

@bad_logger
def compute(x: int, y: str) -> bool: ...

# IDE dan Static Checker sekarang menganggap compute(...) menerima (...args) dan return Any!
# Semua type safety hilang total setelah dekorasi.
```

*Pencegahan (Modern Type Preservation):*
```python
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

def good_logger(fn: Callable[P, R]) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(*args, **kwargs)
    return wrapper
```

### 2. Mengabaikan Sifat Asimetris dari `TypeGuard`
*Praktek Buruk:* Mengasumsikan `TypeGuard` menyempitkan tipe pada blok `else`.
```python
def is_str(val: object) -> TypeGuard[str]:
    return isinstance(val, str)

def process(val: int | str) -> None:
    if is_str(val):
        print(val.upper())
    else:
        # PADA TYPEGUARD: Mypy TIDAK otomatis mempersempit val menjadi 'int' di sini secara aman!
        # val masih dianggap 'int | str' pada beberapa kondisi percabangan kompleks.
        pass
```
*Pencegahan:* Gunakan `TypeIs[T]` (PEP 742, Python 3.13 / via `typing_extensions`) jika Anda membutuhkan pengecekan dua arah (*bidirectional narrowing*) yang matematis sound.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

### 1. Konfigurasi CI Mypy Tingkat Enterprise
Simpan konfigurasi berikut pada `pyproject.toml` untuk mencegah degradasi type quality:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_unused_configs = true
disallow_any_generics = true
disallow_subclassing_any = true
disallow_untyped_calls = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_return_any = true
no_implicit_reexport = true
strict_equality = true
extra_checks = true

# Izinkan modul eksternal legacy tanpa tipe secara terisolasi:
[[tool.mypy.overrides]]
module = "untyped_vendor_lib.*"
ignore_missing_imports = true
```

### 2. Prinsip "Strict Boundary, Clean Core"
*   **Batas Eksternal (Boundary):** Validasi setiap HTTP Request, Kafka Event, atau Database Query menggunakan runtime checking seperti Pydantic atau TypeGuard.
*   **Core Domain:** Gunakan dataclass beku (*frozen dataclasses*) murni atau typed objects. Jangan pernah melewatkan `dict[str, Any]` di dalam core business logic.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Analisis Beban Import Submodul `typing`
Submodul `typing` menginstansiasi banyak kelas internal saat pertama kali diimpor.

```python
# Benchmark profiling evaluasi import:
# python3 -X importtime -c "import typing"
```
Di Python 3.10+, penggunaan sintaks native union (`int | str` menggantikan `typing.Union[int, str]`) dan built-in generic collections (`list[str]` menggantikan `typing.List[str]`) menghemat **~15-25%** waktu startup modul dibanding sintaks legacy Python 3.7/3.8.

### 2. Mencegah Overhead String Annotations pada Runtime Critical Loop
Hindari mengevaluasi tipe menggunakan `typing.get_type_hints` di dalam hot execution loop:

```python
# CRITICAL PERFORMANCE BUG:
for item in millions_of_records:
    # MENYEBABKAN RUNTIME SLOWDOWN EKSTRIM:
    # get_type_hints melakukan parse string dan MRO resolution setiap iterasi!
    hints = typing.get_type_hints(process_func)
```
*Solusi:* Evaluasi metadata refleksi **hanya sekali** saat fase bootstrapping modul / aplikasi, dan simpan hasilnya pada global *cache table*.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Type Escapism sebagai Vulnerability Gateway
Penggunaan `# type: ignore` dan `Any` sering menyembunyikan eksploitasi tipe berbahaya seperti deserialisasi objek sembarangan (*untrusted deserialization*).

```python
# BAHAYA: Blind Type Bypass
def execute_query(raw_data: Any) -> None:
    # Penyerang mengirim payload tipe tak terduga yang lolos dari pemindaian statis
    cursor.execute(raw_data["query"])
```

### 2. Mitigasi via Tainted Control Flow & Protocol Narrowing
Gunakan tipe statis khusus untuk data sensitif guna mencegah eksploitasi seperti Injeksi SQL atau SSRF:

```python
from typing import NewType

# Tipe nominal unik yang tidak dapat diisi string sembarangan secara tidak sengaja
SanitizedQuery = NewType("SanitizedQuery", str)

def run_database_sanitized(query: SanitizedQuery) -> None:
    # Terjamin secara statis hanya data yang melewati fungsi sanitizer yang bisa masuk ke sini
    ...

def sanitize_input(untrusted_user_input: str) -> SanitizedQuery:
    # Logika escaping dan sanitasi
    cleaned = untrusted_user_input.replace("'", "''")
    return SanitizedQuery(cleaned)
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Instruksi Debug Khusus Static Checker: `reveal_type`
Static type checker memiliki mekanisme intrinsik khusus untuk inspeksi tipe interaktif tanpa perlu menjalankan program (`python -m mypy file.py`):

```python
from typing import reveal_type, reveal_locals

def calculate_ratio(numerator: int, denominator: int | None) -> float:
    reveal_type(denominator)  # Output Mypy: Revealed type is "Union[builtins.int, None]"
    
    if denominator is None:
        return 0.0
        
    reveal_type(denominator)  # Output Mypy: Revealed type is "builtins.int" (Narrowed!)
    reveal_locals()           # Output Mypy: Dictionary berisi seluruh tipe variabel lokal saat ini
    return numerator / denominator
```

### 2. Debugging Kesalahan Resolusi Generic Mypy
Jika terjadi error: `error: Incompatible types in assignment (expression has type "List[Dog]", variable has type "List[Animal]")`
*   **Akar Masalah:** `list` adalah invariant.
*   **Langkah Resolusi:** Ubah signature fungsi penerima dari `list[Animal]` menjadi koleksi covariant: `Sequence[Animal]`.

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Matriks Penentu Variansi

```
               ┌────────────────────────────────────────────────────────┐
               │    Apakah Generic bertindak sebagai Producer/Consumer? │
               └───────────────────────────┬────────────────────────────┘
                                           │
             ┌─────────────────────────────┼─────────────────────────────┐
             ▼                             ▼                             ▼
       [PRODUCER ONLY]              [CONSUMER ONLY]               [KEDUA-DUANYA]
      (Hanya Read/Return)           (Hanya Write/Args)          (Read dan Write/Mutasi)
             │                             │                             │
             ▼                             ▼                             ▼
       COVARIANT (+T)              CONTRAVARIANT (-T)              INVARIANT (T)
     `Sequence[T_co]`             `Callable[[T_contra], None]`       `list[T]`, `dict[K, V]`
```

### 2. Quick Syntax Reference (Python 3.12+ Modern vs Legacy)

| Fitur | Legacy (Python 3.8 - 3.11) | Modern (Python 3.12+ / PEP 695) |
| :--- | :--- | :--- |
| **Generic Function** | `def f(x: T) -> T:` | `def f[T](x: T) -> T:` |
| **Generic Class** | `class Box(Generic[T]):` | `class Box[T]:` |
| **Bound TypeVar** | `T = TypeVar('T', bound=Animal)` | `class Box[T: Animal]:` |
| **Type Alias** | `Vector = list[float]` | `type Vector = list[float]` |
| **Covariant Marker** | `T_co = TypeVar('T_co', covariant=True)` | `type SubtypeProducer[out T] = ...` |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5)

1. **Mengapa kode `items: list[object] = [1, 2, 3]` menghasilkan error pada static type checker strict meskipun `int` adalah turunan dari `object`?**
   * *Jawaban:* Karena `list[T]` bersifat invariant. Memperbolehkan assignment tersebut membuka celah di mana elemen non-integer (misal: string) dapat ditambahkan ke list melalui referensi `items`, yang merusak konsistensi tipe underlying `[1, 2, 3]`.
2. **Kapan Anda sebaiknya menggunakan `typing.Protocol` dibanding `abc.ABC`?**
   * *Jawaban:* Gunakan `Protocol` saat menginginkan *loose coupling* via structural subtyping (duck typing statis), terutama saat membuat interface untuk kode pihak ketiga (*third-party*) yang strukturnya tidak dapat kita ubah secara langsung.
3. **Apa dampak performa eksekusi runtime jika kita menambahkan anotasi tipe lengkap pada fungsi tanpa mengakses `__annotations__`?**
   * *Jawaban:* Nol. CPython bytecode compiler mengabaikan anotasi tipe saat eksekusi runtime biasa.
4. **Apa fungsi dari directive `from __future__ import annotations`?**
   * *Jawaban:* Mengubah evaluasi type hints runtime menjadi lazy string literal (*stringized annotations*), mengeliminasi runtime name evaluation cost dan mengatasi masalah deklarasi sirkular.
5. **Apakah `Any` dan `object` identik dalam type system Python?**
   * *Jawaban:* Tidak. `object` adalah root dari hierarki tipe Python (semua operasi pada `object` divalidasi statis dan dibatasi). Sebaliknya, `Any` adalah *type-system escape hatch* dinamis yang menonaktifkan seluruh pemeriksaan statis pada nilai tersebut.

### Soal Intermediate (6–10)

6. **Bagaimana cara Anda memvalidasi tipe generic dari decorator yang menerima parameter argumen tambahan selain fungsi target?**
   * *Jawaban:* Gunakan kombinasi `ParamSpec` untuk parameter fungsi target, dan `TypeVar` untuk return value fungsi, lalu bungkus decorator luar dengan argumen spesifiknya mengembalikan `Callable[[Callable[P, R]], Callable[P, R]]`.
7. **Jelaskan mengapa `Callable[[Animal], None]` adalah subtipe dari `Callable[[Dog], None]` (dengan asumsi `Dog <: Animal`)!**
   * *Jawaban:* Berdasarkan prinsip *Contravariance* pada argumen fungsi: Sebuah fungsi yang mampu memproses sembarang `Animal` dijamin aman saat menerima `Dog`, sehingga relasi subtipe berbalik arah dibanding relasi kelas dasarnya.
8. **Apa perbedaan mendasar antara `TypeGuard[T]` dan `TypeIs[T]` dalam hal narrowing logic?**
   * *Jawaban:* `TypeGuard[T]` hanya mempersempit tipe pada branch `True` secara longgar (unilateral). `TypeIs[T]` mempersempit tipe secara presisi di kedua sisi cabang (`True` menyempitkan ke $T$, `False` mengeliminasi $T$ dari Union).
9. **Mengapa `Sequence[T]` aman dideklarasikan sebagai Covariant sedangkan `MutableSequence[T]` tidak?**
   * *Jawaban:* `Sequence[T]` adalah interface *read-only* (hanya mengeluarkan data bertipe $T$), mematuhi aturan Covariance. `MutableSequence[T]` memiliki metode mutasi (seperti `append`, `__setitem__`) yang memasukkan data $T$, sehingga harus Invariant untuk mencegah kontaminasi tipe.
10. **Bagaimana cara menangani `TypeVar` yang bergantung pada tipe Tuple arbitrary panjangnya pada Python modern?**
    * *Jawaban:* Menggunakan `TypeVarTuple` (PEP 646) yang diekspresikan dengan sintaks pembongkaran (*unpacking*) `*Ts` (contoh: `tuple[*Ts]`).

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek: Compile-Time Type-Safe Dependency Injection Container
Bangun sebuah dependency injection container mini yang sepenuhnya divalidasi statis oleh Pyright/Mypy Strict tanpa ada `Any` atau bypass tipe runtime.

### Persyaratan Arsitektur
1. **Factory Registration Safe Typing:**
   Buat class `Container` yang memiliki method `register_factory(interface: type[T], factory: Callable[[], T]) -> None`.
2. **Resolution Enforcement:**
   Method `resolve(interface: type[T]) -> T` harus mengembalikan instance yang secara otomatis dipahami tipenya oleh IDE/Mypy sesuai dengan parameter kelas yang dikirimkan.
3. **Protocol Service Verification:**
   Definisikan service `DatabaseConnection` dan `Logger` menggunakan `Protocol`.
4. **Custom Linter Verification Script:**
   Buat skrip kecil memanfaatkan module `ast` bawaan Python untuk memeriksa seluruh file kode praktikum Anda: Skrip harus gagal (*exit code 1*) jika menemukan penggunaan kata kunci `Any` atau comment `# type: ignore`.

### Kerangka Awal Kode (Scaffolding)
Lengkapi blok kode berikut hingga lolos eksekusi Mypy strict (`mypy --strict main.py`):

```python
from collections.abc import Callable
from typing import Protocol, TypeVar

T = TypeVar("T")

class Container:
    def __init__(self) -> None:
        self._registry: dict[type[object], Callable[[], object]] = {}

    def register_factory(self, interface: type[T], factory: Callable[[], T]) -> None:
        # IMPLEMENTASIKAN DI SINI
        pass

    def resolve(self, interface: type[T]) -> T:
        # IMPLEMENTASIKAN DI SINI (Cast runtime secara aman dengan verifikasi tipe)
        raise NotImplementedError

# Definisikan Protocols dan buktikan Container berjalan dengan Type Safety 100%!
```

### Kriteria Kelulusan Proyek
* Menjalankan `mypy --strict` menghasilkan pesan: `Success: no issues found in 1 source file`.
* Tidak ada satupun pemanggilan tipe fallback `Any`.
* Skrip CLI AST linter custom Anda berjalan sukses memvalidasi ketiadaan *type debt*.