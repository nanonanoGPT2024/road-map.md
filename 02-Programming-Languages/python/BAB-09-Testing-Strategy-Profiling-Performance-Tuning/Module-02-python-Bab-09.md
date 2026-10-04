# Kurikulum Enterprise: Python Software Engineering
## Kategori: 02-Programming-Languages
## Bab: 09 - Testing Strategy, Profiling, & Performance Tuning
### Modul: Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Engineer/Staff Engineer diharapkan mampu:
1. **Menganalisis Internal Runtime CPython**: Menginspeksi struktur alokasi memori internal (*arenas, pools, blocks* via `pymalloc`), siklus hidup objek (`PyObject`), mekanisme *cyclic garbage collector*, serta implikasi *Global Interpreter Lock* (GIL) dan *Specializing Adaptive Interpreter* (PEP 659) terhadap performa.
2. **Merancang Harness Pengujian Lanjut**: Mengimplementasikan *Property-Based Testing* dengan reduksi kasus uji otomatis (*shrinking*) menggunakan `hypothesis`, mengukur ketahanan test suite melalui *Mutation Testing* (`mutmut`), dan menegakkan verifikasi integrasi berbasis *Consumer-Driven Contracts*.
3. **Mengeksekusi Low-Overhead Profiling di Produksi**: Menerapkan teknik *deterministic profiling* (`cProfile`) dan *statistical/sampling profiling* (`py-spy`, eBPF) pada sistem berbeban tinggi tanpa menurunkan throughput secara katastropik, serta mendeteksi kebocoran memori menggunakan `memray` dan `tracemalloc`.
4. **Mengeliminasi Bottleneck Eksekusi**: Melakukan refaktorisasi jalur kritis (*hot paths*) menggunakan teknik *zero-copy* (`memoryview`, *Buffer Protocol*), optimasi pemanggilan fungsi, mitigasi *contention* GIL, dan integrasi modul natif terkompilasi (Rust melalui `PyO3`).
5. **Membangun Continuous Performance Gate**: Merancang pipeline CI/CD yang menolak regresi performa dan degradasi *mutation score* secara otomatis menggunakan metrik terkuantisasi sebelum rilis produksi.

---

### 2. Prerequisite
Untuk memahami materi secara optimal, Anda wajib menguasai:
*   **CPython Fundamentals**: Memahami kompilasi Python source code menjadi bytecode (`.pyc`), struktur stack evaluation loop (`ceval.c`), dan representasi tipe data dasar di level C.
*   **Testing Basics**: Mahir menggunakan `pytest`, termasuk *fixtures*, *parameterization*, *mocking/stubbing*, dan perhitungan *line/branch coverage*.
*   **Sistem Operasi Lanjut**: Memahami virtual memory, memory-mapped files (`mmap`), sinyal kernel OS (khususnya `SIGPROF`), *context switching*, dan CPU cache lines (L1/L2/L3).
*   **Networking & Concurrency**: Memahami model event-loop `asyncio`, POSIX threads (`pthreads`), dan IPC (*Inter-Process Communication*) via shared memory.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. CPython Memory Allocation Hierarchy (`pymalloc`)
CPython tidak mendelegasikan alokasi memori objek kecil langsung ke `malloc` sistem operasi karena tingginya overhead syscall dan fragmentasi memori. Sebagai gantinya, CPython mengimplementasikan layer `pymalloc` untuk alokasi objek $\le 512$ bytes (pada arsitektur 64-bit modern):

```
+-----------------------------------------------------------------------+
|                             OS Memory                                 |
+-----------------------------------------------------------------------+
                                  | (VirtualAlloc / mmap / malloc)
                                  v
+-----------------------------------------------------------------------+
|                    Arenas (256 KB, aligned to 256 KB)                 |
|  +-----------------------------------------------------------------+  |
|  |                Pools (4 KB, aligned to 4 KB boundary)           |  |
|  |  +-----------------------------------------------------------+  |  |
|  |  | Blocks (Ukuran kelipatan 8/16 bytes: 8, 16, 24, ..., 512) |  |  |
|  |  +-----------------------------------------------------------+  |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

1. **Arenas (256 KB)**: Alokasi chunk memori besar yang diperoleh dari allocator sistem operasi (`malloc`/`mmap`). Arena memuat kumpulan *pool*. Saat seluruh pool dalam satu arena bebas, arena tersebut dapat dikembalikan ke sistem operasi.
2. **Pools (4 KB)**: Setiap pool dipartisi menjadi blok-blok dengan ukuran seragam (*size class*). Suatu pool hanya menangani satu size class spesifik (misal: blok 32-byte). Jika suatu objek membutuhkan 28-byte, objek tersebut dialokasikan pada pool kelas 32-byte (terdapat *internal fragmentation* sebesar 4 byte).
3. **Blocks (8 hingga 512 bytes)**: Unit terkecil alokasi objek Python. Status blok dilacak menggunakan singly-linked list (`freeblock pointer`) di dalam header pool tanpa memerlukan metadata per-blok, menghasilkan densitas memori yang efisien.
4. **Objek > 512 bytes**: Dialokasikan langsung melalui sistem allocator standar platform (`malloc`), melewati `pymalloc`.

#### B. Mekanisme Garbage Collection: Reference Counting & Cyclic GC
CPython mengombinasikan dua arsitektur deteksi siklus hidup:

1. **Reference Counting (Deterministic, Real-time)**:
   Setiap `PyObject` memiliki field header `ob_refcnt`. Ketika reference bertambah (assignment, argument passing), makro `Py_INCREF()` dieksekusi. Ketika reference lepas, makro `Py_DECREF()` dijalankan. Jika `ob_refcnt == 0`, dealokasi memori dipicu secara instan.
   
2. **Generational Cyclic GC (Tracer/Collector)**:
   Reference counting gagal membersihkan *reference cycle* (Objek A mereferensikan Objek B, dan Objek B mereferensikan Objek A).
   CPython mengatasi ini menggunakan *Generational Garbage Collector* yang membagi objek kontainer (`list`, `dict`, `custom class`, dll.) ke dalam 3 generasi:
   *   **Generation 0 (Gen 0)**: Objek kontainer yang baru dialokasikan. Koleksi terjadi paling sering ketika threshold alokasi minus dealokasi tercapai.
   *   **Generation 1 (Gen 1)**: Objek yang bertahan dari siklus GC Gen 0.
   *   **Generation 2 (Gen 2)**: Objek jangka panjang (*long-lived*). Jarang dikoleksi. Koleksi Gen 2 memicu *Full Collection* (Gen 0, 1, dan 2).

   **Algoritma Isolasi Siklus (Cycle Detection Algorithm)**:
   *   Setiap kontainer yang dilacak GC memiliki field `gc_refs` yang diinisialisasi sama dengan `ob_refcnt`.
   *   GC mengiterasi seluruh objek dalam generasi target dan menjalankan fungsi traverse (`tp_traverse`). Untuk setiap referensi internal yang ditunjuk, kurangi nilai `gc_refs` target.
   *   Objek yang memiliki `gc_refs == 0` setelah traversal diisolasi ke dalam himpunan *unreachable candidates*.
   *   Jika objek dalam kandidat tersebut dapat dijangkau dari luar himpunan (objek dengan `gc_refs > 0`), objek tersebut beserta turunannya dikembalikan ke himpunan *reachable*.
   *   Objek yang tersisa di himpunan *unreachable* di-clear dan dimusnahkan.

#### C. Mekanisme Internal GIL & Contention
*Global Interpreter Lock* (GIL) adalah mutex tingkat kernel (`pthread_mutex_t`) yang menjamin hanya satu thread yang mengeksekusi CPython bytecode pada satu waktu di dalam satu proses.

```
Thread 1 (Running)         Thread 2 (Waiting)       GIL State
      |                           |                    |
   Execute Bytecode               |                  LOCKED (Held by T1)
      |                           |                    |
   Interval Timeout (5ms)         |                    |
   sys.check_interval reached     |                    |
      |                           |                    |
   Release GIL ------------------>|                  RELEASED
      |                           v                    |
   Wait on Condition Variable   Acquire GIL --------> LOCKED (Held by T2)
      |                           |                    |
      v                        Execute Bytecode        |
```

*   **Switch Interval (`sys.getswitchinterval()`)**: Secara default adalah 5 milidetik. Setelah 5 ms eksekusi terus-menerus oleh Thread 1, interpreter mengeset flag `gil_drop_request`.
*   Thread 1 melepaskan GIL dan menunda eksekusi melalui *condition variable*, memberikan kesempatan bagi Thread 2 untuk mengakuisisi GIL.
*   Pada beban kerja multithreading CPU-bound di prosesor multi-core, terjadi fenomena **Convoy Effect** dan **Cache Bouncing**: thread yang terbangun memicu perebutan lock di level kernel, memaksa cache CPU L1/L2 sering terinvalidasi (*cache invalidation overhead*), sehingga Python multithreading CPU-bound beroperasi lebih lambat dibanding eksekusi single-threaded.

#### D. Engine Testing Lanjut: Property-Based vs Mutation Testing
1. **Property-Based Testing (Hypothesis Engine)**:
   Berbeda dengan pengujian berbasis contoh (*example-based*), Hypothesis menghasilkan ratusan kombinasi data uji yang memenuhi invarian matematis/domain (*properties*). Jika ditemukan kegagalan (*assertion error*), engine menjalankan proses **Shrinking**: algoritma pencarian biner pada AST input untuk mereduksi kompleksitas payload input ke representasi minimum yang masih memicu kegagalan (*minimal reproducible example*).

2. **Mutation Testing (`mutmut`)**:
   Mengukur kualitas dan ketahanan suite pengujian dengan cara menginjeksi *mutants* (perubahan kode sintaksis artifisial secara otomatis) ke source code, seperti:
   *   Mengubah operator relasional: `>` menjadi `>=`
   *   Mengubah operator logika: `and` menjadi `or`
   *   Mengubah nilai literal/kembalian: `None` menjadi `True`, integer `1` menjadi `2`
   *   Menghapus pemanggilan fungsi (*statement deletion*)
   
   Jika test suite Anda tetap menghasilkan status **PASS** setelah mutasi disuntikkan, mutan tersebut dinyatakan **SURVIVED** (menunjukkan kelemahan test suite/kurangnya assertion spesifik). Jika test suite menjadi **FAIL**, mutan dinyatakan **KILLED** (test suite bekerja efektif).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Production Approach |
| :--- | :--- | :--- |
| **Testing Paradigms** | Mengandalkan *Example-based tests* berbasis asumsi subjektif developer. | Kombinasi *Property-based* (mencakup *edge cases* matematis ekstrem) + *Mutation Testing* (menjamin kualitas test suite). |
| **Profiling Strategy** | `time.time()` manual atau `cProfile` langsung di server produksi. | Sampling Profiler berbasis eBPF / remote stack sampling (`py-spy`) di produksi; `memray` di staging environment. |
| **Memory Management** | Mengabaikan siklus hidup objek; membiarkan GC mengumpulkan sampah secara acak. | Penataan alokasi objek, pencegahan siklus referensi, pemanfaatan *Buffer Protocol* / *Zero-Copy*, kontrol generasi GC. |
| **Critical Hotspots** | Menulis ulang seluruh servis ke bahasa lain secara reaktif. | Identifikasi presisi lewat flamegraphs; optimasi modular menggunakan C-FFI / Rust (`PyO3`) pada hotspot terisolasi. |
| **Performance Assurance**| Pengujian performa ad-hoc di lokal sebelum rilis besar. | Integrasi *Continuous Benchmarking* di CI dengan statistical regression detection (mendeteksi deviasi mean/p99 latency). |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur pengujian dan profiling performa diatur dalam siklus berikut:

```
[ Code Base ] 
      │
      ├──> [ Step 1: Verification Phase ]
      │       ├── Pytest + Coverage Analyzer
      │       ├── Hypothesis (Property-based edge-case generation)
      │       └── Mutmut (Mutation Testing Harness -> Target Mutation Score > 80%)
      │
      ├──> [ Step 2: Local Profiling Phase ]
      │       ├── Deterministic Tracing (cProfile + Snakeviz) -> Hotspot identification
      │       └── Memory Allocation Profile (Memray / Tracemalloc) -> Leak & High Peak detection
      │
      ├──> [ Step 3: Algorithmic & Zero-Copy Tuning ]
      │       ├── Vectorization / Buffer Protocol (memoryview)
      │       └── Native Rewrite (Rust PyO3 / Cython) if CPU Bound
      │
      ├──> [ Step 4: Production Continuous Profiling ]
      │       └── py-spy / Pyroscope Agent (Sampling Profiler @ 100Hz, Overhead < 1%)
      │
      └──> [ Step 5: CI/CD Performance Regression Gate ]
              └── Pytest-benchmark -> Tolak commit jika latency degradasi > 5% (p99)
```

1. **Step 1: Verification**: Jalankan pengujian fungsional unit, integrasi, kontrak, serta ekspansi properti tak terduga via Hypothesis. Terapkan `mutmut` untuk memastikan tidak ada logika cabang yang lolos tanpa asersi valid.
2. **Step 2: Profiling**: Saat latensi atau utilisasi resource melampaui SLA, lakukan pembedahan memori menggunakan `memray` untuk membaca jejak alokasi heap dan deteksi *uncollected cyclic references*. Lakukan profiling CPU menggunakan sampling untuk memetakan *flame graph*.
3. **Step 3: Tuning**: Refaktorisasi data pipeline: ganti serialisasi berulang atau slicing data masif dengan `memoryview` untuk mengeliminasi alokasi intermediate string/bytes. Jika bottleneck berasal dari komputasi murni yang tertahan GIL, buat binding terkompilasi menggunakan Rust (`PyO3`).
4. **Step 4: Continuous Profiling**: Pasang agent non-intrusif di pod produksi untuk merekam data trace panggilan stack berkala via `py-spy` atau integrasi OpenTelemetry/Pyroscope.
5. **Step 5: Regression Gate**: Pasang ambang batas di continuous integration (CI) menggunakan `pytest-benchmark` dengan baseline performa historis.

---

### 6. Analogy & Diagram ASCII

#### Analogi Profiler: Tracing Profiler vs. Sampling Profiler
*   **Tracing Profiler (`cProfile`, `sys.setprofile`)**: Seperti seorang auditor yang mencatat setiap kali seorang pekerja melangkah, duduk, atau mengambil alat tulis. Sangat akurat, namun beban pencatatan tersebut membuat pekerja melambat 300% hingga 1000% dari kecepatan normalnya.
*   **Sampling Profiler (`py-spy`)**: Seperti pengawas yang memotret area kerja setiap 10 milidetik dari kejauhan. Pengawas tidak memperlambat pekerjaan sama sekali (overhead < 1-2%). Foto-foto tersebut dikompilasi menjadi representasi statistik akurat tentang di mana sebagian besar waktu dihabiskan.

#### Perbedaan Memory Copy vs. Zero-Copy Protocol

```
1. Pendekatan Konvensional (Naive Slicing):
   [ Data Buffer Asli: 100 MB ]
               │
               ▼ (Slicing sub_data = buffer[10:50000000])
   [ Data Buffer Baru: 50 MB ]  <-- Duplikasi Alokasi Heap Baru di OS!
   
2. Pendekatan Zero-Copy (Memoryview):
   [ Data Buffer Asli: 100 MB ]
         ▲             ▲
         │             │
   [ memoryview Pointer ]       <-- Hanya membuat view descriptor (PyMemoryViewObject).
      offset: 10                     Alokasi memori heap tambahan: ~200 Bytes!
      length: 49999990
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Zero-Copy String/Bytes Parsing Menggunakan `memoryview` vs Naive Slicing
Menunjukkan optimasi alokasi heap saat membaca header protokol biner terdistribusi.

```python
"""
Benchmark mikro demonstrasi zero-copy menggunakan buffer protocol vs slicing standar.
"""
from __future__ import annotations
import time
import tracemalloc
from typing import Tuple


def naive_parser(payload: bytes, chunk_size: int) -> int:
    """Melakukan slicing konvensional yang memicu duplikasi memori di heap."""
    total_bytes_processed = 0
    num_chunks = len(payload) // chunk_size
    
    for i in range(num_chunks):
        # Operasi slicing ini membuat objek bytes baru setiap iterasi
        chunk = payload[i * chunk_size : (i + 1) * chunk_size]
        total_bytes_processed += chunk[0]
    return total_bytes_processed


def zerocopy_parser(payload: bytes, chunk_size: int) -> int:
    """Menggunakan memoryview untuk memvalidasi buffer tanpa re-alokasi."""
    total_bytes_processed = 0
    # Objek memoryview mengekspos C-level Buffer Protocol
    mv = memoryview(payload)
    num_chunks = len(payload) // chunk_size
    
    for i in range(num_chunks):
        # Slicing pada memoryview menghasilkan slice view baru tanpa menduplikasi buffer dasar
        chunk_view = mv[i * chunk_size : (i + 1) * chunk_size]
        total_bytes_processed += chunk_view[0]
    return total_bytes_processed


def run_demonstration() -> None:
    # Siapkan payload simulasi 100 MB
    payload_size = 100 * 1024 * 1024
    chunk_size = 64 * 1024  # 64 KB
    simulated_payload = b"\x01" * payload_size

    print(f"--- Menjalankan Naive Parser (Ukuran Payload: {payload_size / (1024**2)} MB) ---")
    tracemalloc.start()
    start_time = time.perf_counter()
    naive_res = naive_parser(simulated_payload, chunk_size)
    elapsed_naive = time.perf_counter() - start_time
    current, peak_naive = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Waktu Eksekusi : {elapsed_naive:.4f} detik")
    print(f"Peak Memory    : {peak_naive / 1024:.2f} KB\n")

    print(f"--- Menjalankan Zero-Copy Parser (Ukuran Payload: {payload_size / (1024**2)} MB) ---")
    tracemalloc.start()
    start_time = time.perf_counter()
    zerocopy_res = zerocopy_parser(simulated_payload, chunk_size)
    elapsed_zerocopy = time.perf_counter() - start_time
    current, peak_zerocopy = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Waktu Eksekusi : {elapsed_zerocopy:.4f} detik")
    print(f"Peak Memory    : {peak_zerocopy / 1024:.2f} KB\n")

    assert naive_res == zerocopy_res, "Hasil parsing data tidak identik!"
    print(f"Efisiensi Waktu : {(elapsed_naive / elapsed_zerocopy):.2f}x lebih cepat")
    print(f"Efisiensi Memori: {(peak_naive / peak_zerocopy):.2f}x footprint lebih rendah")


if __name__ == "__main__":
    run_demonstration()
```

---

#### B. Practical Example: Production-Grade Transaction Validator Engine
Contoh arsitektur enterprise: Modul validasi dan kalkulasi transaksi finansial dengan verifikasi *Property-Based Testing* dan pengujian memori/kebocoran via *profiling harness*.

```python
# transaction_engine.py
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from typing import List, Sequence


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    IDR = "IDR"


class ProcessingError(Exception):
    """Domain error untuk anomali eksekusi ledger."""
    pass


@dataclass(frozen=True, slots=True)
class Transaction:
    id: str
    amount: Decimal
    currency: Currency
    fee_rate: Decimal

    def __post_init__(self) -> None:
        if self.amount <= Decimal("0.00"):
            raise ValueError(f"Nilai transaksi harus positif: {self.amount}")
        if not (Decimal("0.00") <= self.fee_rate <= Decimal("1.00")):
            raise ValueError(f"Fee rate di luar boundary [0.0, 1.0]: {self.fee_rate}")


@dataclass(frozen=True, slots=True)
class SettlementBatch:
    batch_id: str
    total_gross: Decimal
    total_fee: Decimal
    total_net: Decimal
    transaction_count: int


class FinancialSettlementEngine:
    """Engine pemroses kliring transaksi dengan optimasi memori dan proteksi presisi numerik."""
    
    __slots__ = ("_precision_cents",)

    def __init__(self) -> None:
        self._precision_cents = Decimal("0.01")

    def process_batch(self, batch_id: str, transactions: Sequence[Transaction]) -> SettlementBatch:
        if not transactions:
            raise ProcessingError("Batch tidak boleh kosong.")

        gross_acc = Decimal("0.00")
        fee_acc = Decimal("0.00")
        count = 0

        # Fast-path processing loop
        for tx in transactions:
            fee = (tx.amount * tx.fee_rate).quantize(self._precision_cents, rounding=ROUND_HALF_EVEN)
            gross_acc += tx.amount
            fee_acc += fee
            count += 1

        net_acc = gross_acc - fee_acc

        return SettlementBatch(
            batch_id=batch_id,
            total_gross=gross_acc,
            total_fee=fee_acc,
            total_net=net_acc,
            transaction_count=count
        )
```

```python
# test_transaction_engine.py
"""
Suite Pengujian Produksi:
Menggabungkan Pytest, Hypothesis (Property-Based), dan Memory Leak Detection.
"""
from __future__ import annotations
from decimal import Decimal
import pytest
from hypothesis import given, strategies as st, settings, Phase
from transaction_engine import FinancialSettlementEngine, Transaction, Currency, ProcessingError


# --- HYPOTHESIS CUSTOM STRATEGIES ---
@st.composite
def transaction_strategy(draw: st.DrawFn) -> Transaction:
    tx_id = draw(st.uuids()).hex
    # Membatasi nilai desimal agar menyerupai rentang transaksi riil sistem finansial
    amount_float = draw(st.floats(min_value=0.01, max_value=1_000_000.00, allow_nan=False, allow_infinity=False))
    amount = Decimal(str(round(amount_float, 2)))
    
    currency = draw(st.sampled_from(Currency))
    fee_rate_float = draw(st.floats(min_value=0.000, max_value=0.200, allow_nan=False, allow_infinity=False))
    fee_rate = Decimal(str(round(fee_rate_float, 4)))
    
    return Transaction(id=tx_id, amount=amount, currency=currency, fee_rate=fee_rate)


# --- PROPERTY-BASED TESTS ---
class TestFinancialSettlementEngineProperties:

    @settings(max_examples=250, phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.shrink])
    @given(transactions=st.lists(transaction_strategy(), min_size=1, max_size=50))
    def test_invariant_conservation_of_money(self, transactions: list[Transaction]) -> None:
        """
        Property Invariant:
        Gross Settlement HARUS TEPAT SAMA dengan Total Net + Total Fee dalam kondisi apa pun.
        """
        engine = FinancialSettlementEngine()
        batch_id = "BAT-TEST-001"
        result = engine.process_batch(batch_id=batch_id, transactions=transactions)

        # Verifikasi Invarian Matematika Finansial
        assert result.total_gross == (result.total_net + result.total_fee), (
            f"Pelanggaran konservasi uang! Gross: {result.total_gross}, "
            f"Net + Fee: {result.total_net + result.total_fee}"
        )
        assert result.transaction_count == len(transactions)

    @settings(max_examples=100)
    @given(transactions=st.lists(transaction_strategy(), min_size=1, max_size=20))
    def test_monotonicity_of_totals(self, transactions: list[Transaction]) -> None:
        """Property Invariant: Akumulasi gross settlement tidak boleh pernah bernilai negatif."""
        engine = FinancialSettlementEngine()
        result = engine.process_batch(batch_id="BAT-TEST-002", transactions=transactions)
        
        assert result.total_gross > Decimal("0.00")
        assert result.total_fee >= Decimal("0.00")
        assert result.total_net > Decimal("0.00")

    def test_empty_batch_rejection(self) -> None:
        """Edge case handling untuk kumpulan batch kosong."""
        engine = FinancialSettlementEngine()
        with pytest.raises(ProcessingError, match="Batch tidak boleh kosong"):
            engine.process_batch(batch_id="ERR-01", transactions=[])


# --- INTEGRATION & PROFILE REGRESSION TEST ---
def test_engine_memory_allocation_stability() -> None:
    """
    Memastikan alokasi objek tidak mengalami kebocoran memori linear 
    selama throughput tinggi menggunakan tracemalloc tracking.
    """
    import tracemalloc
    engine = FinancialSettlementEngine()
    
    sample_txs = [
        Transaction(
            id=f"TX-{i}",
            amount=Decimal("150.50"),
            currency=Currency.USD,
            fee_rate=Decimal("0.015")
        ) for i in range(1000)
    ]
    
    tracemalloc.start()
    
    # Warmup loop
    engine.process_batch("WARMUP", sample_txs)
    snapshot_before = tracemalloc.take_snapshot()
    
    # Execution under test
    for b in range(10):
        engine.process_batch(f"BATCH-{b}", sample_txs)
        
    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()
    
    # Analisis selisih alokasi
    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_leak = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
    
    # Batas toleransi kebocoran memori (harus sangat kecil pada static objects)
    MAX_ALLOWABLE_LEAK_BYTES = 5 * 1024  # 5 KB tolerance
    assert total_leak < MAX_ALLOWABLE_LEAK_BYTES, f"Terdeteksi alokasi memori bocor: {total_leak} bytes"
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Degradasi Latensi P99 Payment Ingestion Engine (Fintech Transaksi Skala Besar)
*   **Konteks Sistem**: Layanan *Payment Clearing Engine* memproses volume puncak 35.000 transaksi per detik (TPS). Arsitektur berjalan pada kluster Kubernetes yang menjalankan pods Python 3.11 berbasis FastAPI dan Gunicorn (Uvicorn workers).
*   **Masalah**: SLA menetapkan batas maksimal latensi P99 $\le 45\text{ ms}$. Di jam sibuk, latensi melonjak tajam (*spikes*) ke $1.850\text{ ms}$, memicu cascade timeout pada upstream payment gateway. Beban CPU berada di kisaran 85%, namun throughput justru stagnan.

#### Metodologi Investigasi:
1. **Sampling Profiling Non-Intrusif via `py-spy`**:
   Karena `cProfile` memberikan overhead lebih dari 200% yang berisiko menumbangkan pod, SRE mengeksekusi `py-spy` secara remote pada pod yang sedang melayani traffic produksi:
   ```bash
   py-spy record --pid $(pgrep -f "gunicorn") --duration 30 --rate 100 --output /tmp/flamegraph.svg
   ```
   *Temuan Flame Graph*: 42% waktu CPU habis pada pemanggilan fungsi `gc.collect()` internal CPython dan penelusuran struktur kamus payload JSON (`pydantic` v1 parse layer).
2. **Memory Profiling via `memray` di Staging Environment**:
   Traffic produksi direkam dan diputar ulang (*replay*) di staging cluster dengan attaching `memray`:
   ```bash
   memray run -m gunicorn app.main:app
   memray flamegraph memray-output.bin
   ```
   *Temuan Alokasi Memori*: Setiap request menghasilkan jutaan temporary cyclic references dari custom logging metadata decorator yang menggunakan dynamic frame inspection (`inspect.currentframe()`). Ini memicu pengisian threshold Generasi 0 CPython hanya dalam hitungan milidetik, memaksa *Full Stop-the-World GC Collection* terus-menerus.

#### Solusi Rekayasa Terstruktur:
1. **Mitigasi Reference Cycle**: Menghapus `inspect.currentframe()`, mendesain ulang logging decorator dengan statically defined attributes, dan menambahkan `__slots__` pada semua class request/response DTO.
2. **Kustomisasi GC Tuning di Runtime**:
   Mengubah ambang batas GC pada saat boot proses worker:
   ```python
   import gc
   # Meningkatkan ambang batas generasi agar frekuensi koleksi menurun drastis
   # Default CPython: (700, 10, 10)
   gc.set_threshold(50000, 500, 200)
   ```
3. **Rust Extension Integration via `PyO3`**:
   Logika verifikasi enkripsi HMAC payload dan deserialisasi yang sebelumnya menyumbang 25% CPU ditransfer ke modul kompilasi native yang dibangun menggunakan Rust dengan melepaskan GIL (`py.allow_threads`):
   ```rust
   // Native validation loop melepaskan GIL sehingga thread pool CPython dapat bekerja paralel murni
   #[pyfunction]
   fn verify_payload_fast(py: Python, payload: &[u8], signature: &str) -> PyResult<bool> {
       py.allow_threads(|| {
           // Komputasi hashing intensif tanpa dependensi runtime Python
           crypto_verification_core(payload, signature)
       })
   }
   ```

#### Hasil Akhir (Metrics Post-Mortem):
*   Latensi P99 turun dari **$1.850\text{ ms}$** menjadi stabil di **$18\text{ ms}$**.
*   Throughput naik dari $35.000\text{ TPS}$ menjadi **$62.000\text{ TPS}$** per node cluster.
*   Frekuensi eksekusi Cyclic GC berkurang sebesar $94\%$.

---

### 9. Trade-offs (Architectural Decisions)

| Dimensi Arsitektural | Opsi A | Opsi B | Trade-off Matrix |
| :--- | :--- | :--- | :--- |
| **Teknik Profiling** | **Deterministic (`cProfile`, `sys.settrace`)** | **Statistical Sampling (`py-spy`, `py-instrument`)** | **Opsi A**: 100% presisi pemanggilan fungsi, namun overhead masif (2x-5x latency degradation). Tabu untuk produksi.<br>**Opsi B**: Overhead amat rendah (<2%), aman untuk produksi, namun ada potensi melewatkan *microsecond spikes* fungsi pendek. |
| **Testing Strategy** | **High Coverage Example-Based Test Suite** | **Property-Based + Mutation Testing** | **Opsi A**: Waktu build CI instan, namun membiarkan edge-cases lolos (*false sense of security*).<br>**Opsi B**: Menjamin keandalan maksimal dan mendeteksi silent-bugs, namun waktu eksekusi pipeline CI meningkat tajam (membutuhkan optimasi caching mutan). |
| **Performance Tuning Layer** | **Algorithmic & Pure Python Tuning (`__slots__`, `itertools`)** | **Native Extensions (Rust via `PyO3` / C-Extensions)** | **Opsi A**: Portabilitas tinggi, zero build dependencies, kemudahan debug, namun akselerasi terbatas pada limitasi GIL.<br>**Opsi B**: Akselerasi CPU maksimum (10x-100x) & lepas GIL, namun kompleksitas CI/CD melonjak (cross-compilation binary wheel target). |
| **Garbage Collector Tuning**| **Default GC Behavior** | **Manual Tuning (`gc.disable()`, threshold shifting)** | **Opsi A**: Aman, terbebas dari OOM risiko kebocoran tersembunyi.<br>**Opsi B**: Latensi konsisten bebas pause GC, namun salah konfigurasi memicu *Out of Memory (OOM) Kill* oleh OS kernel. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Melakukan Benchmarking dengan `time.time()`
*   *Penyebab*: `time.time()` dipengaruhi oleh penyesuaian jam sistem operasi (NTP clock updates) dan resolusinya relatif rendah pada OS non-Linux.
*   *Solusi*: Wajib menggunakan `time.perf_counter()` untuk evaluasi elapsed-time point-to-point, atau modul bawaan `timeit` yang secara otomatis mengisolasi noise dan menonaktifkan GC selama pengujian mikro.

#### 2. False Precision pada Mutation Testing
*   *Gejala*: Menjalankan `mutmut` memakan waktu belasan jam dan menghabiskan resource CI.
*   *Penyebab*: Menjalankan mutasi pada level seluruh codebase termasuk layer I/O, database adapter, dan boilerplate config.
*   *Solusi*: Terapkan Mutation Testing secara selektif (**hanya pada Pure Domain Logic / Business Core Modules**). Gunakan konfigurasi direktori target spesifik:
    ```ini
    # setup.cfg atau pyproject.toml
    [mutmut]
    paths_to_mutate=src/domain/
    tests_dir=tests/unit/domain/
    ```

#### 3. Mengasumsikan Profiler Overhead Bernilai Nol
*   *Gejala*: Optimasi fungsi berdasarkan profil `cProfile` tidak berdampak pada performa riil di produksi.
*   *Penyebab*: Profiling overhead pada fungsi kecil yang dipanggil jutaan kali (*call stack frame construction*) mendistorsi distribusi agregat profiling (*Instrumentation Skew*).
*   *Solusi*: Gunakan *sampling profilers* untuk menentukan hot-path arsitektur sebelum mengeksekusi mikro-optimasi.

#### 4. Kebocoran Memori Akibat Objek yang Terjebak dalam Cache Permanen
*   *Gejala*: Memory footprint pod naik konstan (grafik *sawtooth* linear naik tanpa pernah turun) berujung `OOMKilled`.
*   *Penyebab*: Penggunaan `@functools.lru_cache(maxsize=None)` pada fungsi yang menerima input bervariasi tak terbatas (*unbounded cardianality parameters*).
*   *Solusi*: Jangan pernah gunakan `maxsize=None` di produksi. Tetapkan bound spesifik (misal `maxsize=4096`) dan manfaatkan TTL eviction cache.

---

### 11. Best Practices (Production Checklist)

#### Pre-Commit & Verification:
- [ ] Test suite memiliki kombinasi *Example-based*, *Edge-case boundary testing*, dan *Property-based tests* (Hypothesis) untuk algoritma finansial/kritis.
- [ ] *Mutation Score* pada domain model inti diverifikasi menggunakan `mutmut` dan mencapai batas ambang minimum $\ge 75\%$.
- [ ] Tidak ada penggunaan `inspect` atau evaluasi AST dinamis di *hot path*.

#### Profiling & Runtime Tuning:
- [ ] `slots=True` dideklarasikan pada seluruh `@dataclass` atau `__slots__` pada kelas yang diinstansiasi > 10.000 kali per siklus request.
- [ ] Parsing I/O data stream biner besar (> 1 MB) menggunakan buffer protocol (`memoryview`) guna mencegah alokasi intermediate di heap.
- [ ] *Tracing profiler* (`cProfile`) dilarang aktif di environment produksi umum; verifikasi stack sampling runtime hanya menggunakan tooling eksternal seperti `py-spy` atau agent *continuous profiling* (eBPF).

#### Deployment & Monitoring Gate:
- [ ] CI Pipeline mengeksekusi gate performa berbasis `pytest-benchmark`: commit ditolak otomatis jika terjadi regresi waktu eksekusi $> 5\%$ dari commit baseline di branch utama.
- [ ] Alokasi threshold Cyclic GC disesuaikan dengan arsitektur memori pod jika aplikasi bersifat long-lived microservices.
- [ ] Pod Kubernetes menyertakan probe metrik `process_resident_memory_bytes` dan alert terpicu jika growth memori tidak mendatar pasca-fase warming up.

---

### 12. Hands-on Practice

Buat dan simpan skrip praktikum ini di direktori: `hands-on/m02/`

#### File 1: `hands-on/m02/pipeline_profiler.py`
Instruksi: Jalankan profiling tracing versus sampling, serta deteksi jejak alokasi heap.

```python
"""
hands-on/m02/pipeline_profiler.py
Petunjuk Eksekusi:
1. Jalankan Tracing Profile: python -m cProfile -o trace.prof pipeline_profiler.py
2. Analisis output: python -m pstats trace.prof
3. Jalankan Memray (jika terinstall): memray run pipeline_profiler.py && memray summary memray-*.bin
"""
from __future__ import annotations
import hashlib
import os
import sys
from typing import List


class DataProcessingNode:
    __slots__ = ("node_id", "data_store")

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.data_store: List[bytes] = []

    def ingest_heavy_copy(self, raw_data: bytes, iterations: int) -> None:
        """Simulasi kesalahan: slicing berulang menghasilkan memory pressure."""
        for i in range(iterations):
            chunk = raw_data[i * 10 : (i + 1) * 1000]
            self.data_store.append(chunk)

    def compute_hashes(self) -> List[str]:
        return [hashlib.sha256(item).hexdigest() for item in self.data_store]

    def clear(self) -> None:
        self.data_store.clear()


def execute_pipeline() -> None:
    print(f"[PID: {os.getpid()}] Memulai eksekusi data processing pipeline...")
    node = DataProcessingNode(node_id="WORKER-01")
    
    # 20 MB random payload
    dummy_source = os.urandom(20 * 1024 * 1024)
    
    # Ingestion phase
    print("Menginjeksi data...")
    node.ingest_heavy_copy(dummy_source, iterations=10_000)
    
    # Compute phase
    print("Mengalkulasi hash digests...")
    digests = node.compute_hashes()
    
    print(f"Selesai memproses {len(digests)} blok data.")
    node.clear()


if __name__ == "__main__":
    execute_pipeline()
```

#### File 2: `hands-on/m02/mutation_target.py`
Instruksi: File target yang akan diuji menggunakan pengujian mutasi.

```python
"""
hands-on/m02/mutation_target.py
Domain logic murni yang wajib diuji ketahanannya menggunakan mutmut.
"""
from __future__ import annotations
from typing import Dict, Any


def calculate_discount_tier(customer_tier: str, total_purchases: float) -> float:
    """
    Kalkulasi diskon berbasis hierarki pelanggan dan riwayat transaksi.
    Setiap cabang di bawah memiliki konsekuensi finansial kritis.
    """
    if total_purchases < 0.0:
        raise ValueError("Total purchases tidak boleh negatif.")

    discount_rate = 0.0

    if customer_tier == "PLATINUM":
        if total_purchases >= 5000.0:
            discount_rate = 0.25
        else:
            discount_rate = 0.15
    elif customer_tier == "GOLD":
        if total_purchases >= 2500.0:
            discount_rate = 0.10
        else:
            discount_rate = 0.05
    elif customer_tier == "SILVER":
        discount_rate = 0.02
    else:
        discount_rate = 0.0

    return discount_rate
```

#### File 3: `hands-on/m02/test_mutation.py`
Instruksi: Test harness untuk mengeliminasi mutant pada `mutation_target.py`.

```python
"""
hands-on/m02/test_mutation.py
Eksekusi pengujian mutasi menggunakan perintah:
    mutmut run --paths-to-mutate=mutation_target.py --tests-dir=test_mutation.py
Evaluasi hasil:
    mutmut results
    mutmut show <mutant_id>
"""
from __future__ import annotations
import pytest
from mutation_target import calculate_discount_tier


def test_calculate_discount_tier_platinum_boundary() -> None:
    # Verifikasi tier Platinum batas atas dan bawah
    assert calculate_discount_tier("PLATINUM", 5000.0) == 0.25
    assert calculate_discount_tier("PLATINUM", 5000.01) == 0.25
    assert calculate_discount_tier("PLATINUM", 4999.99) == 0.15


def test_calculate_discount_tier_gold_boundary() -> None:
    # Verifikasi tier Gold batas atas dan bawah
    assert calculate_discount_tier("GOLD", 2500.0) == 0.10
    assert calculate_discount_tier("GOLD", 2500.01) == 0.10
    assert calculate_discount_tier("GOLD", 2499.99) == 0.05


def test_calculate_discount_tier_silver_and_fallback() -> None:
    # Verifikasi tier Silver dan default non-tier
    assert calculate_discount_tier("SILVER", 100.0) == 0.02
    assert calculate_discount_tier("REGULAR", 10000.0) == 0.0
    assert calculate_discount_tier("UNKNOWN_TIER", 0.0) == 0.0


def test_calculate_discount_tier_negative_purchase() -> None:
    # Verifikasi penanganan input invalid
    with pytest.raises(ValueError, match="Total purchases tidak boleh negatif."):
        calculate_discount_tier("PLATINUM", -0.01)
```

---

### 13. Exercise

#### Level: Easy
*   **Problem**: Diberikan sebuah fungsi pencarian string dalam kumpulan log berbasis loop `for` yang melakukan konkatenasi string `log_message = log_message + "[" + str(timestamp) + "] " + record`.
*   **Task**:
    1. Tuliskan ulang fungsi menggunakan format buffer/list accumulation atau string joining yang optimal secara alokasi memori.
    2. Gunakan `timeit` untuk membuktikan peningkatan efisiensi algoritma dari $O(N^2)$ alokasi memori ke $O(N)$.
*   **Acceptance Criteria**: Trace alokasi memori tidak menunjukkan rekursi alokasi baru pada setiap langkah iterasi; waktu eksekusi 100.000 records berkurang minimal 70%.

#### Level: Medium
*   **Problem**: Sebuah pipeline validasi payload telemetry IoT menerima list of dictionary `[{"sensor_id": int, "readings": [float, ...]}]`. Pipeline mengalami issue lonjakan alokasi memori heap saat berhadapan dengan batch berisi 500.000 records.
*   **Task**:
    1. Rancang arsitektur parser data class menggunakan `__slots__` dan tipe array internal (`array.array` / `numpy.ndarray`).
    2. Tulis test suite komprehensif menggunakan `hypothesis` untuk menguji invarian: rentang nilai sensor pembacaan harus selalu berada dalam bounds numerik $(-273.15 \le temp \le 1500.0)$ dengan mengabaikan NaN dan Infinity.
*   **Acceptance Criteria**: Konsumsi memory footprint via `tracemalloc` terbukti turun minimal 60% dibanding baseline dictionary; seluruh invalid property tertangkap oleh Hypothesis shrinking engine.

#### Level: Hard
*   **Problem**: Sistem background task worker menderita dari *memory leak* laten. Setelah diteliti, ditemukan sebuah circular reference yang terjadi antara objek `WorkflowStep` dan `WorkflowContext` yang mengimplementasikan metode `__del__` usang (atau closure context variable) yang menyulitkan Generational Cyclic GC untuk membebaskan pool memory sebelum siklus Gen 2 diaktifkan.
*   **Task**:
    1. Simulasikan skenario reference cycle leak menggunakan modul `gc` dan `weakref` pada unit test.
    2. Tuliskan harness deteksi siklus referensi menggunakan `gc.get_objects()` dan visualisasikan rantai referensi yang tersisa (*uncollectable cycle*).
    3. Refaktorisasi ketergantungan parent-child memanfaatkan `weakref.ref` atau `weakref.proxy` untuk memutus siklus kepemilikan.
*   **Acceptance Criteria**: Pasca-refaktorisasi, pemanggilan `del parent_obj` menghasilkan penghapusan instan objek dari heap (`ob_refcnt == 0`) tanpa intervensi `gc.collect()`; `gc.garbage` tetap bernilai kosong (list berukuran 0).

---

### 14. Challenge

#### Deskripsi Tantangan Arsitektur:
Sebuah perusahaan logistik global memiliki pipeline *Real-time Vehicle Geolocation Anomaly Detection Engine*. Engine menerima stream JSON berisi koordinat kendaraan ($X, Y$), kecepatan, dan status mesin dengan kecepatan $50.000\text{ event/detik}$ per node worker.

#### Persyaratan Teknis:
1. **SLA Latensi**: Waktu parsing, verifikasi invarian geofencing, dan kalkulasi moving average tidak boleh melebihi $1.2\text{ ms}$ pada P99.
2. **Kekebalan Mutasi**: Test suite validasi rute geofencing harus memiliki skor mutasi $100\%$ terverifikasi menggunakan `mutmut`. Mutan apa pun yang mengubah kalkulasi Haversine / Distance metric atau pemotongan batas poligon geofence wajib berujung pada status `FAIL` di unit test.
3. **Continuous Profiling Gate**:
   *   Buat skrip automated CI performance gate berbasis Python yang mengeksekusi sampling benchmark selama 30 detik.
   *   Jika profiler mendeteksi alokasi memori heap bertambah secara persisten melebihi $2\text{ MB/1000 requests}$ atau terjadi *GIL hold contention time* melebihi $20\%$ dari total waktu eksekusi thread, proses pipeline CI otomatis digagalkan dengan return code `1` dan menerbitkan laporan analisis teks diagnostic ke stdout.

#### Pantangan (Constraints):
*   Dilarang menggunakan framework I/O eksternal berskala masif (seperti Apache Spark/Flink); arsitektur harus beroperasi murni pada *Standard Library Python + Test Tools Lanjut* (`pytest`, `hypothesis`, `mutmut`, `memray`).
*   Tidak boleh menonaktifkan GC secara global (`gc.disable()`) tanpa strategi re-enabling terstruktur, untuk menghindari risiko *Node Eviction* di Kubernetes cluster.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual & Dasar (5 Pertanyaan)
1. **Pada level internal CPython `pymalloc`, apakah yang membedakan sebuah *Arena*, *Pool*, dan *Block*?**
   * *Jawaban*: Arena adalah alokasi memori tingkat OS sebesar 256 KB (kelipatan 256 KB). Pool adalah sub-divisi di dalam Arena berukuran 4 KB yang dikhususkan melayani satu *size-class* blok tertentu. Block adalah unit alokasi terkecil (kelipatan 8/16 byte, rentang $\le 512$ bytes) yang dipinjamkan langsung untuk menampung instansiasi `PyObject`.

2. **Mengapa reference counting murni tidak memadai untuk sistem alokasi memori CPython modern?**
   * *Jawaban*: Karena reference counting tidak dapat mendeteksi atau melepaskan *reference cycle* (siklus referensi sirkular), di mana dua atau lebih objek saling mereferensikan satu sama lain sehingga nilai `ob_refcnt` mereka tidak pernah menyentuh angka nol, yang berujung pada kebocoran memori permanen jika tidak diintervensi oleh Generational Cyclic GC.

3. **Bagaimana cara kerja mekanisme *shrinking* pada Property-Based Testing framework seperti `hypothesis`?**
   * *Jawaban*: Ketika sebuah kegagalan (*assertion failure*) ditemukan dari data acak kompleks yang digenerasikan, engine shrinking akan melakukan penelusuran balik terarah (misalnya binary search pada byte/integer sequence, pemangkasan elemen list, penyederhanaan karakter string) untuk mencari payload input dengan representasi paling ringkas yang secara konsisten masih mereproduksi kegagalan tersebut.

4. **Apa bahaya fatal dari mengeksekusi tracing profiler (`cProfile`) di kluster microservice produksi dengan beban traffic padat?**
   * *Jawaban*: `cProfile` menyuntikkan hook deterministic pada setiap event pemanggilan dan pengembalian fungsi via interface runtime interpreter (`sys.setprofile`). Hooking ini menciptakan overhead CPU dan latensi sistem yang masif (hingga membengkakkan response time sebesar 200% - 1000%), yang dapat memicu cascade timeout pada upstream gateway dan memutus ketersediaan layanan (*outage*).

5. **Apa fungsi dari keyword `__slots__` pada class declaration Python dalam konteks efisiensi memori?**
   * *Jawaban*: `__slots__` memberitahu interpreter CPython untuk tidak mengalokasikan kamus dinamis internal (`__dict__`) dan `__weakref__` untuk setiap instansiasi kelas. Sebagai gantinya, interpreter mencadangkan array statis seukuran referensi atribut yang dideklarasikan, mereduksi konsumsi heap per objek hingga lebih dari 60%.

---

#### Bagian B: Intermediate & Mekanisme (5 Pertanyaan)
1. **Mengapa mutan pada *mutation testing* yang berstatus `SURVIVED` mengindikasikan masalah pada arsitektur pengujian Anda?**
   * *Jawaban*: Status `SURVIVED` berarti mutmut berhasil merusak atau mengubah logika bisnis pada kode sumber Anda (misalnya mengubah operator perbandingan atau menghapus suatu baris eksekusi), namun seluruh suite pengujian Anda tetap berstatus `PASS`. Hal ini menunjukkan adanya *coverage blindness*—kode tereksekusi dalam coverage metrik, namun Anda tidak memiliki asersi yang memvalidasi kebenaran semantik dari hasil komputasi tersebut.

2. **Bagaimana parameter `sys.setswitchinterval(interval)` memengaruhi perilaku konkurensi multi-threaded pada program CPU-bound?**
   * *Jawaban*: Parameter ini mengatur seberapa sering CPython interpreter secara proaktif menjatuhkan request pelepasan GIL agar thread lain dapat dieksekusi. Menurunkannya membuat thread berganti lebih sering (meningkatkan responsivitas I/O), namun pada aplikasi CPU-bound, hal ini secara eksponensial memperparah perebutan lock (*mutex contention*), thread-thrashing, dan penurunan kinerja eksekusi akibat hilangnya efisiensi CPU L1/L2 cache.

3. **Jelaskan perbedaan mendasar operasi `memoryview(b"data")[0:10]` vs `b"data"[0:10]` di level sistem alokasi CPython!**
   * *Jawaban*: Operasi `b"data"[0:10]` mengalokasikan objek `bytes` baru di heap memori dan menyalin (*memcopy*) 10 bytes data dari sumber ke lokasi memori baru tersebut. Sedangkan `memoryview(b"data")[0:10]` mengimplementasikan Buffer Protocol di C level; operasi ini tidak menyalin buffer data sama sekali melainkan hanya membuat struct descriptor tipis (`PyMemoryViewObject`) yang menunjuk pada offset dan panjang memori awal yang sama (*Zero-Copy operation*).

4. **Kapan siklus objek container Python dipindahkan dari Generasi 0 ke Generasi 1, dan akhirnya ke Generasi 2 oleh Cyclic GC?**
   * *Jawaban*: Objek kontainer dialokasikan pertama kali di Generasi 0. Jika proses koleksi GC pada Generasi 0 berjalan dan objek tersebut terbukti masih dapat dijangkau (*reachable/survived*), GC akan mempromosikan objek tersebut ke Generasi 1. Mekanisme serupa terjadi pada koleksi Generasi 1: objek yang selamat dipromosikan ke Generasi 2, di mana objek tersebut akan menetap sebagai objek *long-lived*.

5. **Mengapa penggunaan profiling memori berbasis `tracemalloc` terkadang tidak dapat mendeteksi memori yang dialokasikan oleh modul C-Extension pihak ketiga?**
   * *Jawaban*: `tracemalloc` beroperasi dengan melakukan hook pada layer alokasi memori CPython (`PyMem_Malloc`, `PyMem_RawMalloc`). Jika C-Extension pihak ketiga memanggil alokator sistem operasi langsung (seperti `malloc()` libc, `mmap()`, atau jemalloc) tanpa menggunakan Python Memory Allocator API, alokasi tersebut tidak berada di bawah visibilitas pelacakan `tracemalloc`.

---

#### Bagian C: Skenario Kasus Produksi Kompleks (3 Pertanyaan)

1. **Skenario 1**:
   Sebuah worker stream processor memproses event Kafka dengan payload JSON $5\text{ KB}$ per message. Pada 10 menit pertama, service berjalan pada latensi $5\text{ ms}$. Setelah 4 jam beroperasi, memori membengkak hingga $4\text{ GB}$ dan latensi P99 memburuk hingga $3.000\text{ ms}$. Namun, saat seluruh consumer group dihentikan (*idle*), memori **tidak pernah turun kembali ke baseline awal**. 
   *Pertanyaan*: Analisis root-cause internal runtime CPython yang mendasari fenomena ini, dan rancang 2 solusi mitigasinya!
   * *Jawaban*:
     * *Root-cause*: Terjadi fragmentasi memori parah pada `pymalloc`. CPython *Arenas* (256 KB) hanya dapat dilepaskan kembali ke OS jika **setiap pool dan block di dalamnya berstatus 100% kosong**. Jika terdapat 1 objek kecil *long-lived* yang tersisa di dalam suatu arena, seluruh arena 256 KB tersebut terkunci dan tidak dapat dikembalikan ke sistem operasi via `free()`. Ditambah lagi, siklus GC Gen 2 yang terpicu akibat alokasi terus menerus menyebabkan GC pause yang sangat lama seiring membesarnya heap yang harus ditelusuri.
     * *Solusi 1*: Gunakan worker process recycling (misalnya mengatur `--max-requests` atau `max_tasks_per_child` pada Celery/Gunicorn) untuk memusnahkan proses worker secara berkala dan mengembalikan virtual memory sepenuhnya ke OS.
     * *Solusi 2*: Eksternalisasi parsing payload besar ke alokator alternatif, atau lakukan isolasi parsing di level C-Extension/Rust yang menggunakan `jemalloc` yang memiliki arsitektur defragmentasi memori aktif lebih agresif.

2. **Skenario 2**:
   Tim QA menerapkan Mutation Testing menggunakan `mutmut` pada modul checkout e-commerce. Hasil laporan menunjukkan: **Code Coverage = 98%**, tetapi **Mutation Score hanya 41%**. Mutan pada logika perhitungan pajak: `tax = amount * 0.11` dimutasi menjadi `tax = amount * 1.11` dan berstatus `SURVIVED`.
   *Pertanyaan*: Jelaskan anomali antara tingginya angka code coverage dan rendahnya mutation score tersebut! Asersi pengujian seperti apa yang terlewatkan?
   * *Jawaban*:
     * *Analisis Anomali*: Tingginya code coverage (98%) hanya membuktikan bahwa baris kalkulasi pajak tersebut **dieksekusi** oleh interpreter saat test dijalankan, namun sama sekali tidak menjamin bahwa hasil komputasinya diverifikasi. Ini adalah gejala klasik *Assertion-Free Testing* atau *Loose Mocking*, di mana unit test memanggil method checkout namun hanya menegaskan status return code HTTP 200 atau mengecek bahwa method mock `payment_gateway.charge()` dipanggil, tanpa memverifikasi nilai argument nominal uang yang disalurkan.
     * *Perbaikan Asersi*: Unit test harus memvalidasi invariant nilai secara eksplisit (*State & Value Assertion*), seperti: `assert invoice.tax_amount == Decimal("11.00")` dan `assert invoice.total_charge == Decimal("111.00")` pada fixture nominal dasar 100.00.

3. **Skenario 3**:
   Aplikasi backend berbasis asynchronous `asyncio` mengalami *event-loop lag* parah. Metrik menunjukkan utilisasi CPU per-core hanya 12%, namun latensi API P99 membengkak hingga $2.500\text{ ms}$. Profiling via sampling menunjukkan waktu terbanyak dihabiskan pada baris fungsi `jwt.decode()` yang menggunakan enkripsi asymmetric RSA.
   *Pertanyaan*: Jelaskan mengapa CPU rendah namun latensi tetap tinggi pada ekosistem `asyncio`, dan bagaimana arsitektur perbaikannya tanpa beralih ke microservice lain?
   * *Jawaban*:
     * *Penyebab*: Operasi kriptografi asymmetric `jwt.decode()` merupakan komputasi CPU-bound intensif yang bersifat *synchronous/blocking*. Menjalankan fungsi blocking di dalam thread utama `asyncio` akan **membekukan (*starving*) event loop**, mencegah loop tersebut memproses I/O polling, socket handling, dan task coroutine lainnya. Angka CPU terbaca rendah (12% pada 8-core machine) karena hanya 1 core yang bekerja secara sekuensial dan terhambat oleh loop latency.
     * *Arsitektur Perbaikan*: Pindahkan beban komputasi CPU-bound keluar dari Main Event Loop menggunakan `loop.run_in_executor()` dengan backing engine `concurrent.futures.ProcessPoolExecutor` (bukan ThreadPoolExecutor, untuk menghindari perebutan GIL), sehingga operasi verifikasi RSA terdistribusi paralel di level proses OS yang memanfaatkan multi-core secara penuh.

---

### 16. Summary

1. **CPython Runtime Memory**: Pengelolaan performa tingkat lanjut menuntut pemahaman arsitektur alokasi berjenjang CPython (`pymalloc` $\to$ Arenas $\to$ Pools $\to$ Blocks). Pencegahan fragmentasi heap dan mitigasi reference cycle lebih berdampak pada stabilitas sistem skala besar dibanding optimasi sintaksis mikro.
2. **Generational GC Management**: Mengandalkan `ob_refcnt` saja tidak cukup untuk objek dinamis terkoneksi sirkular. Memahami kapan Generasi 0, 1, dan 2 dikoleksi memungkinkan arsitek untuk menata alokasi memori, menerapkan `__slots__`, serta mengatur interval ambang GC untuk mengeliminasi lonjakan latensi (*Stop-the-World pauses*).
3. **Advanced Testing Rigor**: *Line/Branch Coverage* konvensional adalah metrik yang tidak lengkap. Pengujian enterprise modern memadukan *Property-Based Testing* via `hypothesis` untuk mengungkap anomali batasan domain ekstrem, dan *Mutation Testing* via `mutmut` untuk menjamin kualitas asersi test suite.
4. **Low-Overhead Production Profiling**: Penggunaan tracing profiler (`cProfile`) harus dibatasi pada fase development dan staging. Observabilitas sistem berkinerja tinggi di produksi wajib menggunakan *sampling profilers* (seperti `py-spy` atau eBPF tooling) untuk merekam jejak eksekusi tanpa mengorbankan performa aplikasi.
5. **Zero-Copy & Native Scaling**: Hotspot pemrosesan I/O data stream biner diselesaikan menggunakan *Buffer Protocol* (`memoryview`) untuk mengeliminasi alokasi redundan. Komputasi CPU-bound murni yang terhambat oleh GIL diselesaikan melalui delegasi proses (`ProcessPoolExecutor`) atau integrasi ekstensi kompilasi native berbasis Rust (`PyO3`).