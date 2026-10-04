# Bab 09 Module 01: Testing Strategy, Profiling & Performance Tuning

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `PY-B09-M01`
* **Jalur Kurikulum**: Advanced Python Software Engineering & Systems Programming
* **Kategori**: `02-Programming-Languages`
* **Tingkat Kesulitan**: Tingkat Mahir (*Advanced*)
* **Prasyarat**: 
  * Pemahaman mendalam tentang Object-Oriented Programming (OOP) dan Functional Programming di Python.
  * Penguasaan decorators, generators, context managers, dan asynchronous programming (`asyncio`).
  * Pengetahuan dasar tentang CPython runtime, call stack, dan memory management model.
* **Perkiraan Waktu Penyelesaian**: 8 – 10 Jam Pembelajaran Mandiri / Praktikum Terpandu
* **Target Stack & Ekosistem**:
  * Python `>= 3.11` (CPython)
  * Framework Pengujian: `pytest`, `pytest-mock`, `pytest-asyncio`, `hypothesis`
  * Instrumen Profiling & Analisis: `cProfile`, `pstats`, `line_profiler`, `tracemalloc`, `py-spy`

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kemampuan terukur untuk:

1. **Merancang Strategi Pengujian Komprehensif**: Mengimplementasikan arsitektur piramida pengujian modular menggunakan `pytest`, memanfaatkan *fixtures injection*, *mocking strategies* berbasis antarmuka, dan *property-based testing* dengan `hypothesis` untuk mengekspos *edge cases* matematis/struktural.
2. **Mendiagnosis Karakteristik Runtime CPython**: Mengidentifikasi hambatan eksekusi (*bottlenecks*) pada siklus CPU dan lonjakan konsumsi memori (*memory leaks/bloat*) menggunakan kombinasi *deterministic profilers* (`cProfile`, `line_profiler`) dan *statistical/sampling profilers* (`py-spy`).
3. **Menganalisis Alokasi Memori Tingkat Rendah**: Memetakan footprint memori CPython menggunakan `tracemalloc`, menganalisis pemanfaatan heap, referensi objek melingkar (*circular references*), dan overhead dari representasi objek Python.
4. **Menerapkan Tuning Performa Terarah (*Targeted Performance Tuning*)**: Mengeliminasi inefisiensi komputasi melalui optimasi algoritma, pemanfaatan struktur data bawaan yang optimal (`collections`, `array`), optimalisasi struktur memori kelas (`__slots__`), dan mitigasi overhead Python bytecode.
5. **Mengintegrasikan Tolok Ukur Kinerja (*Performance Benchmarking*) dalam CI/CD**: Membangun pengujian regresi performa berbasis kuantitatif yang menghentikan deployment (*build breaking*) ketika deviasi latensi atau konsumsi memori melebihi toleransi Service Level Objective (SLO).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### 1. Hukum Knuth & Observabilitas-First
> *"Premature optimization is the root of all evil (or at least most of it) in programming."* — Donald Knuth.

Optimasi performa tanpa data empiris bukanlah rekayasa perangkat lunak; itu adalah tebak-tebakan spekulatif. Model mental yang benar menuntut bahwa siklus rekayasa harus selalu mengikuti postulat:
$$\text{Make it Work} \longrightarrow \text{Make it Right (Tested)} \longrightarrow \text{Measure (Profile)} \longrightarrow \text{Make it Fast}$$

### 2. Dikotomi Deterministik vs. Probabilistik dalam Pengujian
* **Example-based Testing (Konvensional)**: Menguji hipotesis yang sudah diantisipasi oleh pengembang ($f(x) \to y$). Rentan terhadap bias konfirmasi (*confirmation bias*).
* **Property-Based Testing**: Menentukan invarian sistem (hukum formal yang harus selalu berlaku) dan membiarkan mesin secara agresif membangkitkan ribuan input pseudo-acak terstruktur untuk meruntuhkan invarian tersebut melalui proses *shrinkage*.

### 3. Profiling: Efek Pengamat (*Observer Effect*)
Instrumen pengukur selalu mengubah karakteristik sistem yang diukur.
* **Deterministic Profiling (`cProfile`, `line_profiler`)**: Mengaitkan (*hooking*) fungsi runtime ke setiap *call/return*. Memberikan akurasi totalitas panggilan fungsi tetapi mendistorsi metrik waktu aktual karena overhead instrumen (*profiler overhead*).
* **Statistical / Sampling Profiling (`py-spy`)**: Memeriksa call stack dari luar ruang memori proses pada interval waktu tertentu (sampling). Overhead minimal ($<1-3\%$), sangat ideal untuk beban kerja produksi, namun kehilangan visibilitas terhadap pemanggilan fungsi berdurasi sangat mikro (*sub-microsecond calls*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Pengujian dan Pipeline Diagnostik Performa

```
+-----------------------------------------------------------------------------------+
|                           FASE 1: VERIFIKASI KEANDALAN                             |
+-----------------------------------------------------------------------------------+
|  [Source Code]                                                                    |
|         │                                                                         |
|         ▼                                                                         |
|  [pytest Engine] ───► [Fixtures Dependency Graph] ───► [Mock/Patch Sandbox]       |
|         │                                                                         |
|         ├─────────────► Example-Based Tests (Unit, Integration)                   |
|         │                                                                         |
|         └─────────────► Hypothesis Engine (Stateful & Property Invariant Testing)  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
                                          │ (Code Validated)
                                          ▼
+-----------------------------------------------------------------------------------+
|                           FASE 2: PROFILING & DETEKSI                             |
+-----------------------------------------------------------------------------------+
|  Target Execution Profiler Matrix:                                                |
|                                                                                   |
|  CPU Bound Analysis                   Memory Footprint Analysis                   |
|  ┌──────────────────────────────┐     ┌────────────────────────────────────────┐  |
|  │ cProfile (Global Deterministic)│    │ tracemalloc (Heap Allocation Tracing)  │  |
|  └──────────────┬───────────────┘     └───────────────────┬────────────────────┘  |
|                 │ Call Tree Hotspot                       │ Snapshot Diff         |
|                 ▼                                         ▼                       |
|  ┌──────────────────────────────┐     ┌────────────────────────────────────────┐  |
|  │ line_profiler (Line-by-Line) │     │ Memray / memory_profiler (Leak Hunting)│  |
|  └──────────────────────────────┘     └────────────────────────────────────────┘  |
+-----------------------------------------------------------------------------------+
                                          │ (Bottleneck Identified)
                                          ▼
+-----------------------------------------------------------------------------------+
|                           FASE 3: TUNING & VERIFIKASI                             |
+-----------------------------------------------------------------------------------+
|  Tuning Strategy Execution:                                                       |
|  [ Algorithmic Refactor / __slots__ / Zero-Copy Views / C-Extensions / Caching ]  |
|         │                                                                         |
|         ▼                                                                         |
|  [Regression Benchmarking (pytest-benchmark)] ──► PASS/FAIL (Threshold Guard)    |
+-----------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Pytest Discovery & Fixture Dependency Injection Graph
Pytest tidak menggunakan inheritance model dari `unittest.TestCase`. Pytest membangun Directed Acyclic Graph (DAG) resolusi dependensi fixture:
* **Discovery Phase**: Pemindaian file bernama `test_*.py` atau `*_test.py`. AST (*Abstract Syntax Tree*) diurai untuk mengekstrak definisi kelas, fungsi berawalan `test_`, dan argumen fixture.
* **Scope Hierarchy Execution**: Evaluasi siklus hidup fixture:
  $$\text{session} \longrightarrow \text{package} \longrightarrow \text{module} \longrightarrow \text{class} \longrightarrow \text{function}$$
* **Fixture Teardown via Generators**: Ketika fixture menggunakan `yield`, pytest mengeksekusi kode sebelum `yield` saat setup, menyimpan konteks, menjalankan test runner, dan kembali mengeksekusi kode setelah `yield` saat teardown terlepas dari status eksepsi tes.

```
       [Session Scope Setup]
                 │
                 ▼
       [Module Scope Setup]
                 │
                 ▼
      [Function Scope Setup]
                 │
          [TEST EXECUTION]
                 │
     [Function Scope Teardown]
                 │
                 ▼
      [Module Scope Teardown]
                 │
                 ▼
       [Session Scope Teardown]
```

### 2. CPython Profiler Engine (`sys.setprofile` vs Sampling)
* **`cProfile` Mechanics**: Ditulis dalam C (`_lsprof`). Menggunakan internal hook CPython `PyEval_SetProfile`. Setiap kali CPython bytecode dispatcher mengeksekusi instruksi `CALL_FUNCTION` atau `RETURN_VALUE`, C callback ditembakkan. Callback ini membaca time stamp resolusi tinggi OS (`CLOCK_MONOTONIC`) dan memperbarui struktur data pemanggilan fungsi (*call count, cumulative time, inline time*).
* **Distorsi Akumulasi Waktu**: Overhead pemanggilan callback C pada setiap transisi frame menambahkan latency tetap ($\epsilon$) per panggilan fungsi. Jika sebuah fungsi memanggil jutaan fungsi mikro (*leaf functions*), $\sum \epsilon$ akan mendominasi cumulative time, membiaskan interpretasi metrik.

### 3. CPython Memory Allocation Architecture & `tracemalloc`
Alokasi memori CPython bertingkat:
* **Small Objects ($\le 512$ bytes)**: Ditangani oleh **PyMalloc**. PyMalloc mengambil blok besar memori dari OS (menggunakan `malloc`) yang disebut *Arenas* (256 KB), dibagi menjadi *Pools* (4 KB), dan dipecah lagi menjadi *Blocks* ukuran tetap. Alokasi ini tidak langsung dikembalikan ke OS saat di-`free`.
* **Large Objects ($> 512$ bytes)**: Langsung dialokasikan menggunakan system allocator (`malloc`/`mmap`).
* **`tracemalloc` Hook**: Berada di lapisan C-API alokator (`PyMem_SetAllocator`). Saat diaktifkan, `tracemalloc` mencatat setiap alokasi memori yang dilakukan interpreter, menyimpan pointer ke alamat memori, ukuran byte, dan memetakan Python traceback yang memicu alokasi tersebut.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Test Double Taxonomy: Mocks, Stubs, Fakes, Spies
Kesalahan arsitektural fatal sering terjadi akibat salah memilih *Test Double*:
* **Dummy**: Objek yang diteruskan ke fungsi namun tidak pernah digunakan; hanya ada untuk mengisi daftar parameter metode.
* **Stub**: Menyediakan data tetap yang sudah ditentukan sebelumnya (*canned data*) saat dipanggil. Tidak memvalidasi interaksi.
* **Spy**: Membungkus dependensi riil untuk mencatat histori panggilan (argumen, frekuensi) tanpa mengubah perilaku aslinya.
* **Mock**: Objek yang diprogram sebelumnya dengan ekspektasi spesifik terhadap panggilan yang akan diterimanya. Verifikasi gagal jika ekspektasi tidak terpenuhi.
* **Fake**: Memiliki implementasi fungsional nyata namun mengambil jalan pintas yang tidak cocok untuk produksi (contoh: `InMemoryDatabaseRepository` menggunakan `dict` internal alih-alih koneksi PostgreSQL).

### 2. Property-Based Testing & Shrinkage Mechanics (Hypothesis)
Alih-alih mendefinisikan kasus individual ($x=1$, $x=2$), pengembang mendefinisikan struktur input:
$$\forall x \in \mathbb{Z}, \quad \text{abs}(x) \ge 0$$
Ketika Hypothesis menemukan nilai input yang melanggar invarian (misalnya overflow atau NaN), mesin tidak langsung berhenti. Hypothesis menjalankan algoritma **Shrinkage**:
1. Menemukan kegagalan pada input masif/kompleks (misalnya string acak berisi 1000 karakter Unicode acak).
2. Melakukan pencarian biner dan transformasi penyederhanaan secara sistematis (menghapus karakter, mereduksi integer mendekati 0).
3. Melaporkan *Minimal Reproducible Example* terkecil yang memicu bug (misalnya string kosong `""` atau nilai integer `-1`).

### 3. Karakteristik Profiling: Deterministic vs Statistical
| Dimensi Evaluasi | Deterministic (`cProfile`) | Statistical (`py-spy`) |
| :--- | :--- | :--- |
| **Mekanisme** | Event-driven hook (`PyEval_SetProfile`) | Memory scraping via OS debugging primitives |
| **Overhead** | Signifikan (20% – 200%) | Rendah (< 3%) |
| **Akurasi Panggilan** | 100% tepat pada jumlah hit | Sampel probabilistik (berdasarkan frekuensi Hertz) |
| **Kesesuaian Produksi** | DILARANG di Production High-Load | AMAN untuk Production Ad-hoc Tracing |
| **Analisis Garis** | Terbatas (perlu `line_profiler`) | Mendukung flamegraph detail secara real-time |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi skenario pengujian komprehensif: implementasi modul pengujian fixtures, mocks, async testing, invariants property-based testing, dan instrumentasi profiling internal.

```python
# test_portfolio_engine.py
import cProfile
import pstats
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO
from typing import Protocol
from unittest.mock import create_autospec

import pytest
from hypothesis import given, strategies as st


# ==========================================
# 1. CORE DOMAIN LOGIC UNDER TEST
# ==========================================
class FXRateService(Protocol):
    """Port interface untuk layanan nilai tukar mata uang."""
    def get_rate(self, base: str, target: str) -> Decimal:
        ...


@dataclass(frozen=True, slots=True)
class AssetPosition:
    symbol: str
    quantity: Decimal
    base_currency: str


class PortfolioEvaluator:
    def __init__(self, fx_service: FXRateService) -> None:
        self._fx_service = fx_service

    def calculate_total_value(
        self, positions: list[AssetPosition], target_currency: str
    ) -> Decimal:
        if not positions:
            return Decimal("0.0")

        total = Decimal("0.0")
        for pos in positions:
            if pos.quantity < Decimal("0.0"):
                raise ValueError(f"Kuantitas posisi tidak boleh negatif: {pos.quantity}")
            
            rate = Decimal("1.0")
            if pos.base_currency != target_currency:
                rate = self._fx_service.get_rate(pos.base_currency, target_currency)
            
            total += pos.quantity * rate
        return total


# ==========================================
# 2. TESTING SUITE (FIXTURES, MOCKS, HYPOTHESIS)
# ==========================================

@pytest.fixture
def mock_fx_service() -> FXRateService:
    """Fixture untuk menyediakan interface mock terspesifikasi."""
    mock = create_autospec(FXRateService, instance=True)
    # Default behavior: 1 USD = 15000 IDR
    mock.get_rate.return_value = Decimal("15000.00")
    return mock


@pytest.fixture
def sample_positions() -> list[AssetPosition]:
    """Fixture penyedia data posisi portofolio acuan."""
    return [
        AssetPosition(symbol="AAPL", quantity=Decimal("10"), base_currency="USD"),
        AssetPosition(symbol="BBCA", quantity=Decimal("100"), base_currency="IDR"),
    ]


def test_calculate_total_value_with_fx_conversion(
    mock_fx_service: FXRateService, sample_positions: list[AssetPosition]
) -> None:
    """Menguji konversi valuta menggunakan mock FX service."""
    # Setup
    evaluator = PortfolioEvaluator(fx_service=mock_fx_service)

    # Execution
    total_in_idr = evaluator.calculate_total_value(sample_positions, target_currency="IDR")

    # Assertions
    # 10 AAPL * 15000 = 150,000 IDR
    # 100 BBCA = 100 IDR
    # Total = 150,100 IDR
    assert total_in_idr == Decimal("150100.00")
    mock_fx_service.get_rate.assert_called_once_with("USD", "IDR")


def test_negative_quantity_raises_value_error(mock_fx_service: FXRateService) -> None:
    """Memastikan invarian error tervalidasi saat input kuantitas invalid."""
    evaluator = PortfolioEvaluator(fx_service=mock_fx_service)
    invalid_positions = [
        AssetPosition(symbol="FRAUD", quantity=Decimal("-5"), base_currency="USD")
    ]

    with pytest.raises(ValueError, match="Kuantitas posisi tidak boleh negatif"):
        evaluator.calculate_total_value(invalid_positions, target_currency="USD")


# Property-Based Testing Invariant
@given(
    quantities=st.lists(
        st.decimals(min_value=Decimal("0.0"), max_value=Decimal("1000000.0"), places=2),
        min_size=1,
        max_size=50,
    )
)
def test_portfolio_monotonicity_property(quantities: list[Decimal]) -> None:
    """Invarian: Menambahkan kuantitas positif tidak boleh mengurangi total nilai."""
    mock_service = create_autospec(FXRateService, instance=True)
    mock_service.get_rate.return_value = Decimal("1.0")
    evaluator = PortfolioEvaluator(fx_service=mock_service)

    positions = [
        AssetPosition(symbol=f"ASSET_{i}", quantity=q, base_currency="USD")
        for i, q in enumerate(quantities)
    ]

    total_base = evaluator.calculate_total_value(positions, target_currency="USD")

    # Modifikasi: Tambahkan satu aset dengan quantity > 0
    additional_position = AssetPosition(
        symbol="ADDON", quantity=Decimal("10.0"), base_currency="USD"
    )
    total_extended = evaluator.calculate_total_value(
        positions + [additional_position], target_currency="USD"
    )

    # Invarian Monotonik
    assert total_extended > total_base


# ==========================================
# 3. RUNTIME PROFILING INSTRUMENTATION
# ==========================================
def profile_portfolio_calculation() -> None:
    """Instrumentasi Profiling terintegrasi menggunakan cProfile."""
    mock_service = create_autospec(FXRateService, instance=True)
    mock_service.get_rate.return_value = Decimal("1.5")
    evaluator = PortfolioEvaluator(fx_service=mock_service)

    # Simulasi 100,000 posisi aset untuk memicu beban komputasi
    large_dataset = [
        AssetPosition(symbol=f"SYM_{i}", quantity=Decimal(f"{i}.5"), base_currency="USD")
        for i in range(100_000)
    ]

    profiler = cProfile.Profile()
    profiler.enable()

    # Eksekusi fungsi target
    evaluator.calculate_total_value(large_dataset, target_currency="EUR")

    profiler.disable()

    # Ekstraksi dan pemformatan metrik profiling
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(10)  # Cetak top 10 baris termahal
    print(stream.getvalue())


if __name__ == "__main__":
    profile_portfolio_calculation()
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari implementasi kode di Seksi 07:

1. **Baris 14–17 (`FXRateService(Protocol)`)**: Mendefinisikan kontrak antarmuka struktural via *Structural Subtyping* (`typing.Protocol`). Hal ini memungkinkan substitusi mock atau alternatif implementasi konkret tanpa coupling melalui inheritance eksplisit.
2. **Baris 20–24 (`@dataclass(frozen=True, slots=True)`)**:
   * `slots=True`: Mengeliminasi atribut internal `__dict__` pada tiap instance dan menggantinya dengan deskriptor array berukuran tetap. Ini mereduksi konsumsi memori hingga ~60% per instance dan mempercepat akses atribut.
   * `frozen=True`: Memastikan objek berstatus *immutable*, mencegah mutasi status secara tak sengaja dalam alur komputasi.
3. **Baris 49–54 (`@pytest.fixture def mock_fx_service()`)**:
   * Penggunaan `create_autospec(FXRateService, instance=True)`: Menghasilkan mock yang melakukan introspeksi terhadap interface asli. Jika kode mencoba memanggil metode yang tidak ada pada `FXRateService` (misal: `mock.fetch_rate()`), mock akan langsung melempar error `AttributeError` saat runtime pengetesan. Mencegah *stale/invalid mock specifications*.
4. **Baris 78–84 (`mock_fx_service.get_rate.assert_called_once_with(...)`)**: Memverifikasi interaksi sistem; memastikan bahwa isolasi unit berjalan sempurna dan komponen hanya berinteraksi sesuai batasan arsitektur (hanya aset berbasis non-target currency yang memicu RPC FX service).
5. **Baris 97–103 (`@given(...)`)**: Konfigurasi strategi Hypothesis.
   * `st.decimals(...)`: Membangkitkan bilangan desimal acak dalam rentang spesifik, menangani representasi presisi tinggi.
   * Hypothesis mengontrol siklus eksekusi: fungsi tes dipanggil berulang kali (default: 100 iterasi) dengan variasi input ekstrem (misalnya `0.00`, float tak hingga mikro, nilai batas atas).
6. **Baris 136–138 (`profiler.enable()` & `profiler.disable()`)**: Mengisolasi pengukuran performa tepat pada titik kritis. Membatasi ruang observasi hanya pada algoritma `calculate_total_value` dan membuang overhead inisialisasi dataset masif (`large_dataset`) dari metrik kalkulasi.
7. **Baris 141–143 (`pstats.Stats(..., stream=stream).sort_stats(...)`)**: Mengurai data run profiling biner internal C, menyusun hirarki waktu kumulatif (`SortKey.CUMULATIVE`), dan memformat laporan teks untuk dianalisis oleh developer.

---

## SEKSI 09 — STUDI KASUS NYATA (High-Throughput Ingestion Engine)

### Deskripsi Masalah Produksi
Sebuah sistem agregasi transaksi finansial memproses 500,000 rekaman transaksi per batch dari message bus. Sistem mengalami degradasi performa akut:
1. Waktu pemrosesan batch melonjak dari batas SLA 1.5 detik menjadi 42 detik.
2. Konsumsi memori melonjak hingga 3.2 GB per worker, memicu eksekutor Linux Out-Of-Memory (OOM) Killer.
3. Arsitektur lama menyembunyikan bottleneck di balik kompleksitas validasi nested loop, string manipulation dinamis, dan deserialisasi yang tidak efisien.

### Analisis Akar Masalah (Root Cause Identification)
Melalui analisis sampling menggunakan `tracemalloc` dan `line_profiler`, ditemukan tiga anomali fatal:
* Instansiasi berulang kelas standar berbasis `class Transaction` menggunakan `__dict__` memori standar.
* Melakukan string parsing dan komparasi regex redundan di dalam iterasi data.
* Lookup ID pedagang (*merchant ID*) menggunakan struktur data `list` ($O(N)$ lookup) alih-alih `set` atau hash map ($O(1)$ amortized lookup).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah rekonstruksi sistem dari kode bermasalah (*Legacy Naive*) menuju kode optimal (*Optimized High-Performance Engine*), disertai suite benchmark pengujian regresi.

```python
# transaction_engine.py
import csv
import io
import time
import tracemalloc
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple


# =====================================================================
# VERSI 1: KODE BERMASALAH (NAIVE IMPLEMENTATION - BOTTLENECK PROFILE)
# =====================================================================
class NaiveTransaction:
    """Implementasi konvensional: Memori boros dan lambat."""
    def __init__(self, tx_id: str, merchant_id: str, amount: str, status: str):
        self.tx_id = tx_id
        self.merchant_id = merchant_id
        self.amount = Decimal(amount)
        self.status = status

    def is_valid(self, blacklisted_merchants: list[str]) -> bool:
        # BOTTLENECK 1: O(N) linear search pada list hitam
        if self.merchant_id in blacklisted_merchants:
            return False
        # BOTTLENECK 2: String matching berulang
        if self.status.strip().upper() != "COMPLETED":
            return False
        return True


def process_transactions_naive(
    raw_data: list[dict], blacklist: list[str]
) -> Decimal:
    transactions = [
        NaiveTransaction(
            tx_id=row["tx_id"],
            merchant_id=row["merchant_id"],
            amount=row["amount"],
            status=row["status"],
        )
        for row in raw_data
    ]
    
    total_volume = Decimal("0.0")
    for tx in transactions:
        if tx.is_valid(blacklist):
            total_volume += tx.amount
    return total_volume


# =====================================================================
# VERSI 2: KODE OPTIMAL (OPTIMIZED ENGINE - LOW MEMORY, HIGH THROUGHPUT)
# =====================================================================
# OPTIMIZATION 1: Menggunakan slots untuk memotong memori object hingga ~65%
@dataclass(slots=True, frozen=True)
class OptimizedTransaction:
    tx_id: str
    merchant_id: str
    amount: Decimal
    status: str


def process_transactions_optimized(
    raw_data: list[dict], blacklist_set: set[str]
) -> Decimal:
    """
    Optimasi:
    1. Zero-dict allocations via __slots__.
    2. Lookup O(1) via Hash Set.
    3. Generator streaming untuk akumulasi nilai tanpa alokasi list perantara.
    """
    valid_status = "COMPLETED"
    
    # Inlining dan eliminasi intermediate object instantiation jika tidak diperlukan
    total_volume = sum(
        Decimal(row["amount"])
        for row in raw_data
        if row["status"] == valid_status and row["merchant_id"] not in blacklist_set
    )
    return total_volume


# =====================================================================
# REGRESSION BENCHMARKING & VALIDATION HARNESS
# =====================================================================
def generate_synthetic_data(num_records: int) -> tuple[list[dict], list[str], set[str]]:
    data = []
    for i in range(num_records):
        data.append({
            "tx_id": f"TX_{i}",
            "merchant_id": f"MERCHANT_{i % 500}",
            "amount": f"{ (i % 100) + 1 }.50",
            "status": "COMPLETED" if i % 4 != 0 else "FAILED",
        })
    blacklist_list = [f"MERCHANT_{j}" for j in range(50, 100)]
    blacklist_set = set(blacklist_list)
    return data, blacklist_list, blacklist_set


def execute_profiling_audit():
    records_count = 200_000
    print(f"[*] Menghasilkan {records_count} rekaman data simulasi...")
    raw_data, bl_list, bl_set = generate_synthetic_data(records_count)

    print("\n" + "=" * 60)
    print("AUDIT 1: EKSEKUSI NAIVE IMPLEMENTATION")
    print("=" * 60)
    
    tracemalloc.start()
    t_start = time.perf_counter()
    
    res_naive = process_transactions_naive(raw_data, bl_list)
    
    t_duration_naive = time.perf_counter() - t_start
    current, peak_naive = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Hasil Kalkulasi     : {res_naive}")
    print(f"Durasi Eksekusi     : {t_duration_naive:.4f} detik")
    print(f"Puncak Memori Heap  : {peak_naive / (1024 * 1024):.2f} MB")

    print("\n" + "=" * 60)
    print("AUDIT 2: EKSEKUSI OPTIMIZED ENGINE")
    print("=" * 60)

    tracemalloc.start()
    t_start = time.perf_counter()

    res_opt = process_transactions_optimized(raw_data, bl_set)

    t_duration_opt = time.perf_counter() - t_start
    current, peak_opt = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Hasil Kalkulasi     : {res_opt}")
    print(f"Durasi Eksekusi     : {t_duration_opt:.4f} detik")
    print(f"Puncak Memori Heap  : {peak_opt / (1024 * 1024):.2f} MB")

    # Kalkulasi Metrik Komparasi
    speedup = t_duration_naive / t_duration_opt
    mem_reduction = ((peak_naive - peak_opt) / peak_naive) * 100

    print("\n" + "=" * 60)
    print("HASIL COMPARATIVE PROFILING")
    print("=" * 60)
    print(f"Performa Akselerasi (Speedup) : {speedup:.2f}x lebih cepat")
    print(f"Reduksi Konsumsi Memori       : {mem_reduction:.2f}% hemat memori")
    assert res_naive == res_opt, "Output integritas kalkulasi tidak cocok!"


if __name__ == "__main__":
    execute_profiling_audit()
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih strategi pengujian dan perkakas analisis memerlukan pertimbangan cermat antara akurasi, waktu eksekusi, dan overhead sistem.

```
                    ANALISIS MATRIX: PERFORMA vs BIAYA PENGUJIAN
                    
           Tinggi ▲
                  │                                  ● End-to-End System Tests
                  │                           (High Fidelity, Extremely Slow)
                  │
                  │                 ● Integration & Contract Tests
   REALISME /     │            (Medium Speed, High Infrastructure Cost)
   CONFIDENCE     │
                  │       ● Property-Based Testing (Hypothesis)
                  │   (Deep Bug Hunting, Moderate CPU Cost)
                  │
                  │  ● Unit Tests with Mocks
                  │ (Microsecond Feedback, Fast, Low Fidelity)
           Rendah ┼──────────────────────────────────────────────────────────►
                  Cepat                                                  Lambat
                                       WAKTU EKSEKUSI
```

### Matriks Komparasi Instrumen Pengujian & Profiling

| Instrumen | Lingkup Analisis | Overhead Runtime | Kelebihan Utama | Kelemahan Fatal | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`pytest` + Mock** | Unit Isolation | Sangat Rendah | Feedback instan, eksekusi paralel via `pytest-xdist`. | Tidak mendeteksi kegagalan integrasi antar-komponen riil. | Jalur CI/CD commit stage primer. |
| **`Hypothesis`** | Domain Invariants | Menengah - Tinggi | Menemukan bug tak terpikirkan via autogenerated input & shrinking. | Waktu tes non-deterministik jika rentang input terlalu luas. | Logika finansial, parser, algoritma kriptografi. |
| **`cProfile`** | Global Application Call Stack | Signifikan (~30-80%) | Bawaan standard library, pemetaan call-tree komprehensif. | Waktu terdistorsi akibat overhead profiling instrumen; non-line-level. | Mendiagnosis fungsi mana yang lambat secara makro. |
| **`line_profiler`** | Line-by-Line Execution | Sangat Tinggi (~200-500%) | Memberikan visualisasi baris kode individual paling mahal. | Harus menambahkan decorator manual (`@profile`); merusak performa runtime. | Bedah mikro pada fungsi hotspot yang telah ditemukan `cProfile`. |
| **`py-spy`** | Out-of-Process Sampling Profiler | Ekstrim Rendah (< 3%) | Dapat di-attach ke *live production process* tanpa restart; flamegraphs. | Kehilangan pemanggilan fungsi berdurasi sangat mikro (*sub-millisecond*). | Deteksi deadlocks, live production diagnostics. |
| **`tracemalloc`** | Heap Allocations Traceback | Rendah - Menengah | Integrasi native Python, melacak file dan baris penyebab alokasi memori. | Tidak melacak memori yang dialokasikan di dalam C-Extensions langsung. | Deteksi memory leak dan bloat alokasi objek. |

---

## SEKSI 12 — EDGE CASES, PITFALLS & GAGAL TERSELUBUNG

### 1. Mock Leakage dan Global State Pollution
Ketika menggunakan `unittest.mock.patch`, kegagalan melakukan unpatch (teardown) akan merusak modul pengujian lain yang berjalan setelahnya dalam proses yang sama.
* **Mekanisme Kegagalan**: Memanggil `patch()` manual tanpa context manager atau fixture pytest. Objek target tetap termutasi secara global.
* **Mitigasi**: Selalu gunakan fixture `mocker` dari library `pytest-mock`, yang secara deterministik menjamin pemulihan state asli objek segera setelah ruang lingkup tes berakhir.

### 2. Time Skewing pada Profiler Overhead
Jika Anda menganalisis kode yang memiliki jutaan pemanggilan method getter/setter berukuran 2 nanodetik, `cProfile` akan menginjeksi overhead sekitar 100 nanodetik pada tiap pemanggilan.
* **Dampak**: Laporan profiling akan menyatakan bahwa program menghabiskan 90% waktu pada getter/setter tersebut, padahal dalam kondisi produksi tanpa profiler, waktu yang dihabiskan pada fungsi tersebut dapat diabaikan.
* **Mitigasi**: Gunakan sampling profiler (`py-spy`) untuk validasi silang metrik waktu makro.

### 3. False Confidence pada Property-Based Testing
Hypothesis membatasi jumlah generasi input default hingga 100 iterasi (`max_examples=100`). Jika domain data memiliki *sparse failure state* (misalnya bug hanya terjadi pada integer `0xDEADBEEF`), probabilitas input generator acak memicu state tersebut adalah $\approx 0$.
* **Mitigasi**: Gabungkan Hypothesis dengan *Explicit Example Targeting* menggunakan fungsi `.example()` untuk menyematkan batas kritis domain yang telah diketahui secara deterministik.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Menguji Implementasi Internal, Bukan Perilaku (*Testing Implementation Details*)
```python
# BURUK: Sangat rapuh (brittle), gagal saat refactoring internal
def test_user_service(mocker):
    service = UserService()
    mock_repo = mocker.patch.object(service, "_internal_cache_dict")
    service.get_user(1)
    mock_repo.__getitem__.assert_called_once_with(1)  # Menguji implementasi internal


# BAIK: Black-box verification terhadap kontrak perilaku
def test_user_service_behavior(mocker):
    mock_db = mocker.create_autospec(DatabaseGateway)
    service = UserService(repository=mock_db)
    user = service.get_user(1)
    assert user.id == 1  # Menguji output aktual yang diekspos
```

### Anti-Pattern 2: Profiling pada Mode Debug atau Tanpa Representasi Beban Produksi
Menjalankan profiling pada dataset lokal berukuran 10 baris dengan `DEBUG=True` atau logging level `DEBUG` aktif.
* **Dampak**: Logging I/O akan mendominasi 80% run time profiling, menyamarkan algoritma kompleks yang sebenarnya merupakan bottleneck utama pada volume data produksi.
* **Perbaikan**: Selalu lakukan profiling dengan logging level `WARNING`, matangkan data dummy hingga mendekati skala produksi, dan jalankan interpreter dengan optimasi byte-code (`python -O`).

### Anti-Pattern 3: Mutable Fixtures yang Membocorkan State Antar-Tes
```python
# BURUK: Mengembalikan object mutable yang dimodifikasi oleh tes individual
@pytest.fixture(scope="module")
def shared_user_list():
    return [{"id": 1, "balance": 100}]


def test_deduct_balance(shared_user_list):
    shared_user_list[0]["balance"] -= 50
    assert shared_user_list[0]["balance"] == 50


def test_initial_balance(shared_user_list):
    # AKAN GAGAL jika dijalankan setelah test_deduct_balance!
    assert shared_user_list[0]["balance"] == 100
```
* **Perbaikan**: Pastikan fixture yang memuat status mutable memiliki `scope="function"` (default), atau kembalikan immutable snapshot (misal via `deepcopy` atau `tuple`).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Pola Struktur Arrange-Act-Assert (AAA)**: Pisahkan blok persiapan data (*Arrange*), pemanggilan fungsi target (*Act*), dan pengecekan invarian/ekspektasi (*Assert*) secara visual menggunakan pemisahan satu baris kosong yang konsisten.
2. **Karantina Flaky Tests dengan Strict Policies**: Tes yang gagal secara sporadis harus segera ditandai dengan `@pytest.mark.xfail(strict=False)` atau diisolasi ke issue tracker. Dilarang menggunakan *retry loops* tanpa batas waktu pada test runner CI karena ini menutupi masalah *concurrency race conditions*.
3. **Pemberian Nama Tes Berbasis Konteks-Aksi-Hasil**:
   * Format Standar: `test_<unit_yang_diuji>_<kondisi_skenario>_<hasil_ekspektasi>()`
   * Contoh: `test_transfer_funds_insufficient_balance_raises_overdraft_error()`
4. **Isolasi Alokasi Objek Melalui Desain Stateless**: Dalam kalkulasi data pipeline, bangun fungsi *pure* tanpa *side-effects* untuk memaksimalkan peluang interpreter menggunakan register CPU secara optimal dan mempermudah pengujian modular.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Panduan Taktis Optimasi Python

```
                    ALUR DIAGNOSTIK KINERJA SISTEM
                                  │
                                  ▼
                    [Identifikasi Hotspot Profiling]
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        ▼                                                   ▼
 [CPU Bound Hotspot]                               [Memory Bound Hotspot]
        │                                                   │
        ├─► Pindah O(N) ke O(1) via Sets/Dicts             ├─► Terapkan __slots__ pada Data Class
        ├─► Gunakan Local Variable Caching                 ├─► Ganti List Comp dengan Generator
        ├─► Hindari Panggilan Fungsi di Loop Ketat         ├─► Gunakan array / memoryview untuk Buffers
        └─► Eksternalisasi Loop ke NumPy / C-Extension     └─► Paksa Garbage Collection (gc.collect)
```

1. **Local Variable Lookup Optimization**:
   Di CPython, memuat variabel global menggunakan bytecode `LOAD_GLOBAL` yang harus mencari pada hash map modul dan built-in. Sebaliknya, memuat variabel lokal menggunakan bytecode `LOAD_FAST` yang membaca langsung dari pointer array C tingkat register.
   ```python
   # Lebih lambat
   def process_all(items):
       import math
       return [math.sqrt(x) for x in items]

   # Lebih cepat (Micro-optimization)
   def process_all_optimized(items):
       import math
       sqrt = math.sqrt  # Local binding
       return [sqrt(x) for x in items]
   ```
2. **Memory Footprint: `__slots__` vs Dictionaries**:
   Penggunaan `__slots__` mengeliminasi overhead `__dict__` dinamis ($150-400\text{ bytes}$ per objek menjadi hanya ukuran pointer variabel primitif C). Pada skala $10^6$ objek, ini memangkas gigabytes konsumsi RAM secara langsung.
3. **Zero-Copy Serialization dengan `memoryview`**:
   Saat menangani byte stream, slicing string biner (`data[10:100]`) menduplikasi memori heap. Gunakan `memoryview(data)[10:100]` untuk membuat slice referensial tingkat rendah tanpa menyalin buffer byte data asli.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitasi Data Fixture & Mencegah Secret Spillage**:
   * Jangan pernah menuliskan API Key, private certificate, atau koneksi basis data produksi secara hardcoded di dalam fixture `conftest.py`.
   * Gunakan integrasi library `pytest-dotenv` atau *dummy test credentials* yang dikunci pada memori lokal test suite.
2. **Mitigasi Fuzzing Injection pada Property-Based Testing**:
   * Saat melakukan stress testing menggunakan strategi teks terbuka (`st.text()`), pastikan sistem menangani *null bytes* (`\x00`), injeksi ANSI escape codes, dan variasi Unicode normalization (misal: homoglyphs pada formasi URL).
3. **Dynamic Execution Warning**:
   * Hindari penggunaan profiling tool yang membutuhkan injeksi kode dinamis seperti `eval()` atau `exec()` dalam evaluasi target runtime pengujian.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Pytest Failure Debugging Primitives
Eksekusi pengujian deterministik dengan flag CLI esensial saat terjadi anomali:
* `pytest -vv --showlocals`: Menampilkan seluruh variabel lokal yang tersimpan dalam stack frame saat terjadi kegagalan (`AssertionError`).
* `pytest --pdb`: Menghentikan eksekusi tes tepat pada baris yang melempar exception dan langsung mengaktifkan Python Interactive Debugger (`pdb`).
* `pytest --durations=10`: Menampilkan 10 pengujian paling lambat dalam suite, mendeteksi regresi kecepatan pipeline tes secara proaktif.

### 2. Perekaman Flamegraph Produksi Menggunakan `py-spy`
Jalankan profiling langsung pada server produksi atau *staging container* tanpa mematikan aplikasi:
```bash
# Record stack trace selama 30 detik pada frekuensi 100Hz ke format SVG Flamegraph
py-spy record --pid <PYTHON_APP_PID> --output profile_flamegraph.svg --duration 30 --rate 100

# Live top-like interactive view per-fungsi
py-spy top --pid <PYTHON_APP_PID>
```

Flamegraph merepresentasikan call stack secara vertikal: semakin lebar blok fungsi secara horizontal, semakin lama waktu CPU yang dihabiskan oleh fungsi tersebut (beserta anak-anak panggilannya).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Quick CLI Reference
```bash
# Menjalankan suite pengujian dengan paralelisme 4 core
pytest -n 4 --dist=loadscope

# Menjalankan subset pengujian berdasarkan penanda ekspresi kustom
pytest -m "integration and not slow"

# Profiling script mandiri dengan output terurut akumulasi waktu
python -m cProfile -s cumulative application.py > profile_report.txt

# Menjalankan line-by-line profiler pada script yang dihias @profile
kernprof -l -v script_to_profile.py
```

### Pytest & Profiling Idiom Snippet
```python
# conftest.py - Pattern teardown fixture via generator
@pytest.fixture
def managed_resource():
    resource = acquire_expensive_resource()  # SETUP
    yield resource
    resource.release()  # TEARDOWN GUARANTEED

# Performance threshold assert pattern
import time


def test_performance_sla():
    start = time.perf_counter()
    critical_computation()
    duration = time.perf_counter() - start
    assert duration < 0.05, f"Komputasi melanggar SLA 50ms: {duration:.4f}s"
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat untuk setiap pertanyaan berikut:

### Bagian 1: Tingkat Dasar (5 Soal)

**Soal 1:** Apa perbedaan mendasar antara implementasi `unittest.TestCase` standar dan `pytest` dalam hal pengelolaan status pengujian?
* A. Pytest mewajibkan semua tes diwarisi dari class `PytestBaseCase`.
* B. Pytest menggunakan *dependency injection* berbasis fixture fungsional yang deklaratif, sedangkan `unittest` berbasis pewarisan kelas (*class inheritance*) imperatif.
* C. Pytest tidak mengizinkan pengetesan fungsi async.
* D. Pytest hanya bisa mengevaluasi exception dengan blok `try...except` manual.

**Soal 2:** Fitur apakah pada Python class yang dapat digunakan untuk mengeliminasi pembuatan atribut internal `__dict__` sehingga menghemat alokasi memori secara signifikan?
* A. `__slots__`
* B. `__init_subclass__`
* C. `@property`
* D. `__repr__`

**Soal 3:** Apa fungsi dari parameter `instance=True` pada saat memanggil `create_autospec(TargetClass, instance=True)`?
* A. Membuat instance riil dari class tanpa mocking.
* B. Menginstruksikan mock agar berperilaku seperti sebuah instance dari target class (bukan class object itu sendiri), menolak pemanggilan atribut yang tidak terdefinisi pada instance.
* C. Memastikan mock tersimpan di memori secara permanen (*singleton*).
* D. Menjalankan garbage collection segera setelah mock dipanggil.

**Soal 4:** Manakah tipe profiler berikut yang menambahkan overhead waktu paling minimal terhadap aplikasi Python saat dijalankan?
* A. `line_profiler`
* B. `cProfile`
* C. Statistical sampling profiler (`py-spy`)
* D. `profile` (pure Python standard profiler)

**Soal 5:** Kapan teardown code pada sebuah pytest fixture dieksekusi jika fixture tersebut menggunakan keyword `yield`?
* A. Segera sebelum pengujian dimulai.
* B. Tepat setelah kode pengujian yang mengonsumsi fixture tersebut selesai dijalankan, baik sukses maupun memicu unhandled exception.
* C. Hanya jika tes tidak menghasilkan exception sama sekali.
* D. Ketika modul Python dihapus oleh sistem operasi.

---

### Bagian 2: Tingkat Lanjut (5 Soal Skenario)

**Soal 6:** Sebuah tes berbasis `hypothesis` mendeteksi sebuah bug tersembunyi pada komputasi serialisasi ketika menerima list berisi 1,500 string Unicode. Namun, pada laporan akhir, hypothesis hanya melaporkan string tunggal `"\x00"` sebagai penyebab kegagalan. Fenomena ini disebut:
* A. Code Mutation.
* B. Fuzz Elimination.
* C. Test Shrinkage.
* D. Memory Corruption Truncation.

**Soal 7:** Anda menemukan bahwa hasil eksekusi `cProfile` menunjukkan waktu fungsi `get_val()` adalah 80% dari total waktu eksekusi program. Namun, ketika dicek dengan `py-spy`, fungsi tersebut hampir tidak tampak pada grafik sampling (< 1%). Apa penjelasan teknis yang paling rasional atas deviasi ini?
* A. `py-spy` mengalami bug internal dalam parsing symbol.
* B. Fungsi `get_val()` dipanggil jutaan kali dengan durasi komputasi yang sangat mikro (*sub-microsecond*); overhead deterministic hook dari `cProfile` melipatgandakan akumulasi waktu secara artifisial.
* C. CPython mengompilasi `get_val()` menjadi kode C secara otomatis saat menggunakan `py-spy`.
* D. Memory allocator menunda alokasi memori saat `cProfile` aktif.

**Soal 8:** Perhatikan potongan kode berikut:
```python
@pytest.fixture(scope="session")
def db_session():
    engine = create_engine()
    conn = engine.connect()
    yield conn
    conn.close()
```
Jika Anda menjalankan rangkaian tes yang memodifikasi data secara bersamaan menggunakan plugin `pytest-xdist` (`pytest -n 4`), masalah konkurensi apa yang akan terjadi?
* A. Session fixture akan dibagikan secara aman melintasi proses OS via shared memory.
* B. Masing-masing dari 4 worker process akan membuat session fixture-nya sendiri secara independen, berpotensi memicu race conditions pada state database fisik bersama jika tidak diisolasi secara transaksional.
* C. `pytest-xdist` menolak eksekusi jika ada fixture dengan scope session.
* D. Modul `tracemalloc` akan otomatis memblokir koneksi database.

**Soal 9:** Mengapa penggunaan `mocker.patch('os.remove')` terkadang gagal mengintersepsi pemanggilan saat target module mengimpor fungsi tersebut menggunakan sintaks `from os import remove`?
* A. Modul `os` kebal terhadap dynamic introspection di runtime.
* B. Mock diterapkan pada namespace global modul `os`, sedangkan modul target memegang referensi langsung ke fungsi `remove` di namespace lokalnya sendiri sebelum patch dieksekusi.
* C. CPython memblokir patching pada C-Extension modules secara otomatis.
* D. `mocker.patch` hanya mendukung manipulasi kelas kustom, bukan fungsi pustaka standar.

**Soal 10:** Modul `tracemalloc` melaporkan konsumsi memori puncak terus merangkak naik (memory leak), namun modul `gc.collect()` mengembalikan angka 0 (tidak ada unreachable circular references). Di manakah kemungkinan besar lokasi kebocoran memori terjadi dalam konteks Python murni?
* A. Terjadi kebocoran memori pada alokasi C level OS yang tidak dapat dideteksi interpreter.
* B. Objek-objek baru terus ditambahkan ke dalam struktur data global yang masih memiliki referensi aktif yang valid (seperti dictionary cache atau static list) sehingga GC menganggapnya masih berstatus *reachable*.
* C. GIL (*Global Interpreter Lock*) mematikan tracing memori secara sepihak.
* D. Variabel lokal di dalam fungsi rekursif gagal dibersihkan oleh OS.

---

### Kunci Jawaban & Pembahasan Evaluasi

1. **Jawaban: B** — Pytest memisahkan dependensi status melalui injeksi dependensi fixture yang bersih dan fleksibel, meninggalkan model warisan kelas yang kaku pada `unittest`.
2. **Jawaban: A** — `__slots__` secara eksplisit mendefinisikan atribut instance yang diizinkan dan menonaktifkan pembentukan `__dict__` dinamis, menghasilkan penghematan memori masif.
3. **Jawaban: B** — `create_autospec` dengan `instance=True` meniru instance nyata dari kelas target, mencegah pemanggilan atribut yang hanya ada pada level kelas atau tidak didefinisikan sama sekali pada kontrak aslinya.
4. **Jawaban: C** — Sampling profiler seperti `py-spy` membaca memori proses Python dari luar secara periodik (*sampling*), sehingga overhead eksekusi sangat rendah (< 1-3%) dibanding deterministic profilers.
5. **Jawaban: B** — Mekanisme generator fixture pada pytest memastikan kode setelah `yield` selalu dijalankan saat tahap penutupan (*teardown*), bahkan jika terjadi exception pada test target (mirip blok `finally`).
6. **Jawaban: C** — *Shrinkage* adalah algoritma formal dari Hypothesis untuk memangkas dan menyederhanakan data masif yang gagal menjadi contoh kegagalan terkecil yang dapat direproduksi (*minimal reproducible input*).
7. **Jawaban: B** — Overhead instrumen profiling deterministik (`cProfile`) menambahkan waktu tetap pada setiap event fungsi. Jika fungsi mikro dipanggil jutaan kali, akumulasi overhead instrumen mendistorsi metrik durasi riil.
8. **Jawaban: B** — `pytest-xdist` menjalankan pengujian pada proses sistem operasi terpisah. Scope `session` hanya berlaku per-proses; antar-worker process tidak berbagi instance fixture in-memory, sehingga operasi database lintas proses dapat saling bertabrakan (*data clash*).
9. **Jawaban: B** — Prinsip dasar patching: Anda harus mem-patch objek di namespace tempat objek tersebut diimpor dan digunakan (*patch where it's used*), bukan di modul tempat objek tersebut awalnya didefinisikan.
10. **Jawaban: B** — Siklus Garbage Collector (`gc`) CPython hanya mengurus pembersihan objek siklik yang terisolasi (*unreachable*). Jika objek tersimpan dalam global collection (misal cache tak terbatas), statusnya tetap *reachable*, sehingga tidak dibersihkan oleh GC kendati alokasinya terus membesar.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: High-Performance In-Memory Time-Series Metric Aggregator

#### Skenario Masalah
Anda ditugaskan merancang modul analitik internal yang bertugas memvalidasi, mengagregasi, dan mendeteksi anomali pada time-series metrik infrastruktur (CPU, Memori, Latensi Jaringan). Modul ini menerima payload biner/kamus dalam frekuensi tinggi (hingga $10^5$ events/detik). 

Arsitektur sistem lama gagal karena:
1. Memakan memori lebih dari 2 GB untuk mempertahankan jendela data 60 detik.
2. Waktu pemrosesan agregasi melanggar batas interval pembacaan metrik.
3. Rangkaian tes rapuh dan sering gagal saat urutan data dibalik.

#### Spesifikasi Fungsional & Kriteria Penerimaan
1. **Model Domain Teroptimasi**:
   * Bangun kelas `MetricPoint` yang divalidasi ketat menggunakan `__slots__`.
   * Komponen: `timestamp` (integer POSIX epoch), `metric_name` (string termemori/interned), `value` (float).
2. **Komponen Aggregator Engine**:
   * Implementasikan kelas `WindowedAggregator` yang memiliki metode `.ingest(point: MetricPoint) -> None` dan `.get_percentile(p: float) -> float`.
   * Aggregator harus mempertahankan rentang waktu konstan (sliding window 60 detik) dan membuang data kadaluwarsa secara otomatis.
   * Pencarian persentil harus dioptimasi agar tidak melakukan pengurutan ulang (*resorting*) penuh jika data baru yang masuk tidak signifikan.
3. **Suite Pengujian Tingkat Mahir**:
   * **Unit Tests**: Menguji logika validasi dan agregasi dengan isolasi 100%.
   * **Property-Based Testing (Hypothesis)**: Uji invarian formal: Persentil 50th ($P_{50}$) tidak pernah boleh lebih besar dari Persentil 99th ($P_{99}$) untuk sebaran dataset acak apa pun.
   * **Stateful Mocking**: Buat mock terisolasi untuk layanan notifikasi anomali eksternal, validasi interaksi jika nilai persentil melampaui ambang batas tertentu.
4. **Audit Performa & Profiling**:
   * Tulis modul pengujian profiling mandiri menggunakan `tracemalloc` dan `cProfile`.
   * **SLA Target Kinerja**: Ingest 500,000 titik metrik harus selesai dalam waktu $< 1.0\text{ detik}$, dengan konsumsi heap memori puncak $< 80\text{ MB}$.
   * Sisipkan benchmark test berbasis pytest yang akan menggagalkan pipeline pengujian (*assertion failure*) jika metrik throughput turun di bawah $300,000\text{ events/detik}$.