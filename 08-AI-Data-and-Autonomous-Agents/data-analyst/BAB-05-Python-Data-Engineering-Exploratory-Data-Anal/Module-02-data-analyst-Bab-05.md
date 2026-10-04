# Kurikulum Enterprise: Data Analyst & Engineering
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-05: Python Data Engineering & Exploratory Data Analysis (EDA)
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta mampu:
1. **Mengonseptualisasikan Arsitektur Memori Data:** Menganalisis alokasi memori internal CPython, NumPy *strided arrays*, Pandas `BlockManager`, serta format Apache Arrow columnar layout untuk mengeliminasi *overhead* CPU dan RAM.
2. **Merancang Pipeline Data Skala Besar:** Mengimplementasikan pola pemrosesan data berbasis *chunking*, *generator pipelines*, dan *zero-copy memory mapping* (`mmap`) untuk memproses dataset yang melebihi kapasitas RAM (*out-of-core processing*).
3. **Mengotomatisasi Advanced EDA & Data Quality Verification:** Membangun *automated exploratory engine* yang menghitung matrik statistik multivariat, mendeteksi *data drift* (menggunakan *Population Stability Index* dan uji *Kolmogorov-Smirnov*), serta memvalidasi anomali data dengan *schema enforcement* berbasis tipe ketat.
4. **Mencegah & Memitigasi Degradasi Performa Produksi:** Mengeliminasi operasi *anti-pattern* seperti komputasi iteratif berbasis baris (`iterrows`), *hidden copies*, dan *fragmentasi memori*, serta menggantinya dengan vektorisasi SIMD (*Single Instruction, Multiple Data*) dan *PyArrow backend*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta harus menguasai:
*   **Python Programming Lanjutan:** Pemahaman mendalam mengenai Python Data Model (`__dunder__` methods), *generator*, *decorator*, *context manager*, dan *concurrency model* (GIL, `multiprocessing`).
*   **Dasar NumPy & Pandas:** Operasi dasar `ndarray`, DataFrame indexing, manipulasi bentuk (`reshape`, `pivot`), dan fungsi agregasi bawaan.
*   **Struktur Data & Kompleksitas Algoritma:** Big-O notation untuk alokasi memori dan waktu komputasi, struktur cache CPU (L1/L2/L3), dan *spatial/temporal locality*.
*   **Aljabar Linier & Statistika Inferensial:** Vektor, matriks, distribusi probabilitas, pengujian hipotesis, dan kovarians/korelasi.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 CPython Memory Layout vs. NumPy Strided Arrays vs. Apache Arrow
Secara default, objek Python murni adalah wrapper di atas tipe data primitif C (`PyObject`). Sebagai contoh, sebuah `int` 64-bit standar tidak hanya berukuran 8 byte:
```text
PyObject header (16 bytes) + ob_refcnt (8 bytes) + ob_type (8 bytes) + value (8 bytes) = 28 bytes minimum!
```
Ketika menyimpan 10 juta integer dalam `list` Python biasa, sistem membuat 10 juta pointer terpisah ke 10 juta instance `PyObject` yang tersebar secara acak di heap memory (*pointer chasing*). Hal ini menyebabkan *cache misses* parah pada CPU L1/L2/L3.

```
CPython List:
+---------------+    +---------------+    +---------------+
| Pointer 0     |--->| PyObject (Int)|    | PyObject (Int)|
+---------------+    +---------------+    +---------------+
| Pointer 1     |------------------------>| (Heap acak)   |
+---------------+                         +---------------+

NumPy Contiguous ndarray (C-order):
[ Buffer Memori Kontigu ] -> [8 bytes][8 bytes][8 bytes][8 bytes] (L1/L2 Cache hit optimal)
```

NumPy mengatasi masalah ini dengan mengalokasikan satu blok memori C yang kontigu (*contiguous memory buffer*). Atribut `strides` mendikte berapa byte yang harus dilompati dalam memori untuk berpindah ke baris atau kolom berikutnya:
$$\text{Offset}(i, j) = (i \times \text{stride}_0) + (j \times \text{stride}_1)$$

Pandas historis (< 2.0) membangun abstraksi di atas NumPy menggunakan `BlockManager`. `BlockManager` mengelompokkan kolom-kolom dengan tipe data yang sama ke dalam array 2D terpisah. Konsekuensinya:
* Konsolidasi blok memicu penyalinan data (*deep copy*) yang tidak terduga.
* Nilai hilang (*nullability*) ditangani dengan mengubah integer menjadi `float64` untuk mengakomodasi `NaN`, yang melipatgandakan kebutuhan memori dan memperkenalkan *floating-point rounding error*.

Pandas 2.0+ dan sistem data modern beralih ke **Apache Arrow**:
* **Columnar Format:** Kolom disimpan sebagai array mandiri dengan *null bitmap* terpisah (1 bit per baris untuk status null).
* **Zero-Copy Reads:** IPC (*Inter-Process Communication*) atau pembacaan dari format Parquet dapat dipetakan langsung ke memori proses tanpa deserialisasi.
* **SIMD Alignment:** Data dialokasikan dengan perataan memori 64-byte, memungkinkan instruksi CPU modern (AVX-512) memproses 8 data float 64-bit dalam satu siklus clock mesin.

```
Apache Arrow Columnar Layout (Integer Array dengan Null Bitmap):
Validity Bitmap:  [1][1][0][1] (Bitmask: Baris 2 adalah NULL)
Offsets Buffer:   Tidak diperlukan untuk primitive tetap
Value Buffer:     [1024][2048][----][4096] (Memori kontigu 64-byte aligned)
```

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Vanilla Pandas) | Pendekatan Enterprise (Arrow/Vectorized Engine) |
| :--- | :--- | :--- |
| **Penyimpanan Tipe Data** | Menggunakan tipe CPython `object` untuk teks (overhead pointer besar). | String disimpan sebagai Arrow Dictionary atau LargeUtf8 kontigu. |
| **Eksekusi Komputasi** | Perulangan eksplisit (`iterrows`, `apply(lambda)`) memicu overhead interpreter. | Vektor SIMD via NumPy/PyArrow C-kernels. |
| **Skalabilitas Memori** | Membutuhkan RAM 3x hingga 5x ukuran dataset di disk saat transformasi. | *Out-of-core chunking* dan *zero-copy memory projection* (RAM konstan). |
| **Integritas Skema** | *Duck typing*; skema bermutasi secara diam-diam (*silent downcasting*). | Enforced Data Contract (validasi run-time berbasis skema ketat). |

#### Mengapa Perlu Arsitektur Lanjutan?
1. **Cost-to-Compute Efficiency:** Pada lingkungan cloud (AWS ECS/EKS), instans dialokasikan berdasarkan RAM. Kegagalan optimasi tipe data melipatgandakan *billable footprint* infrastruktur.
2. **Reliability (Eliminasi OOM):** Kesalahan `Exit Code 137 (Out Of Memory Killer)` pada pipeline batch produksi terjadi akibat lonjakan memori sementara (*peak allocation*) selama manipulasi DataFrame.
3. **Reproducibility & Drift Awareness:** Data ingestion yang tidak memvalidasi kestabilan distribusi probabilitas fitur (*statistical drift*) akan merusak performa model inferensi downstream.

---

### 5. How (Workflow Detail)

Arsitektur produksi membagi pemrosesan data analitik ke dalam 5 fase ketat:

```
[ Ingestion Layer ] -> [ Data Contract Validation ] -> [ Memory Optimization Engine ]
         |
         v
[ Out-of-Core Processing ] -> [ Statistical Profiling & Drift Detection ] -> [ Export Layer ]
```

1. **Ingestion & Metadata Interrogation:** Membaca metadata file mentah (Parquet footer / CSV head) tanpa memuat payload data ke RAM. Menentukan tipe data target secara apriori.
2. **Schema Enforcement & Type Casting:** Menginstansiasi schema contract menggunakan library validasi (*Pandera* / *Pydantic*). Mengalokasikan array Arrow native.
3. **Partitioned / Chunked Streaming:** Memproses data dalam bentuk generator iterator. Menetapkan batasan buffer memori per-pekerja (*memory budget limit*).
4. **Vectorized Mathematical Transforms:** Melakukan komputasi *windowing*, *aggregations*, dan normalisasi menggunakan kernel terkompilasi (C/Rust).
5. **Continuous Profiling & Statistical Baseline Comparison:** Menghitung drift metrik (*PSI*, *Wasserstein Distance*) secara streaming sebelum persistensi data.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Inspeksi Pabrik Konvensional vs. Scanning Konveyor Cerdas
*   **Vanilla Pandas (`iterrows` / `object` type):** Anda membongkar muatan truk palet demi palet, membuka kotak kayu individual, mengambil satu barang, membawanya ke meja uji, mencatat hasilnya di kertas, lalu mengembalikannya ke kotak. Sangat lambat dan memakan ruang gudang.
*   **Apache Arrow & Vectorized Processing:** Barang berjalan di atas sabuk konveyor berkecepatan tinggi dengan posisi yang sangat teratur. Rangkaian sensor sinar-X (SIMD) memindai 64 barang sekaligus dalam satu jepretan mikrodetik tanpa perlu membuka atau menyentuh fisik kemasan (*Zero-Copy*).

#### Diagram Arsitektur Pemrosesan Memori
```text
+-----------------------------------------------------------------------------------------+
|                                    CPYTHON HEAP MEMORY                                  |
|                                                                                         |
|   +------------------------------------+      +-------------------------------------+   |
|   |         PANDAS LEGACY              |      |         ARROW-BACKED ENGINE         |   |
|   |  +------------------------------+  |      |  +-------------------------------+  |   |
|   |  | DataFrame                    |  |      |  | DataFrame                     |  |   |
|   |  |  +------------------------+  |  |      |  |  +-------------------------+  |  |   |
|   |  |  | BlockManager           |  |  |      |  |  | ArrowExtensionArray      |  |  |   |
|   |  |  |  [FloatBlock: 2D array]|  |  |      |  |  |  [Arrow RecordBatch]    |  |  |   |
|   |  |  |  [IntBlock:   2D array]|  |  |      |  |  +-------------------------+  |  |   |
|   |  |  |  [ObjectBlock: Pointers|  |  |      +-------------------------------------+   |
|   |  |  +------------------------+  |  |                     | (Zero-Copy Pointers)     |
|   |  +------------------------------+  |                     v                          |
+-----------------------------------------------------------------------------------------+
                                                +-----------------------------------------+
                                                | OFF-HEAP MEMORY / SHARED MEMORY         |
                                                |                                         |
                                                |  [Contiguous C-Data Buffer: 64B Align]  |
                                                |  [Null Bitmaps: 1-bit per cell]         |
                                                +-----------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Alokasi Memori Objek vs. Categorical/Arrow
Contoh di bawah mengilustrasikan perbedaan drastis penggunaan memori antara representasi default `object` dan `string[pyarrow]`.

```python
import sys
import pandas as pd
import numpy as np

# Buat dataset sederhana dengan nilai berulang (khas data analitik)
n_rows = 1_000_000
raw_categories = ["SUCCESS", "FAILED", "PENDING", "RETRY"]

# Pendekatan Naif: Objek String CPython
df_naive = pd.DataFrame({
    "status": np.random.choice(raw_categories, size=n_rows)
})

# Pendekatan Modern: Arrow Engine
df_arrow = pd.DataFrame({
    "status": pd.Series(np.random.choice(raw_categories, size=n_rows), dtype="string[pyarrow]")
})

# Pendekatan Modern: Categorical Encoding
df_cat = pd.DataFrame({
    "status": pd.Series(np.random.choice(raw_categories, size=n_rows), dtype="category")
})

print(f"Memory Naive (Object)     : {df_naive['status'].memory_usage(deep=True) / 1024**2:.2f} MB")
print(f"Memory Arrow (PyArrow)    : {df_arrow['status'].memory_usage(deep=True) / 1024**2:.2f} MB")
print(f"Memory Categorical        : {df_cat['status'].memory_usage(deep=True) / 1024**2:.2f} MB")
```

#### 7.2 Practical Example: Enterprise-Grade Data Processing Pipeline
Implementasi pipeline batch produksi dengan validasi data ketat via Pandera, alokasi memori berorientasi Arrow, dan komputasi vektor.

```python
from typing import Generator, Dict, Any
import logging
import numpy as np
import pandas as pd
import pandera as pa
from pandera.typing import Series

# Setup Enterprise Logging Standard
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("DataEngineeringPipeline")

# 1. Definisikan Data Contract Menggunakan Pandera
class TransactionSchema(pa.DataFrameModel):
    transaction_id: Series[str] = pa.Field(unique=True, coerce=True)
    customer_id: Series[int] = pa.Field(ge=1, coerce=True)
    amount: Series[float] = pa.Field(ge=0.0, coerce=True)
    status: Series[str] = pa.Field(isin=["COMPLETED", "FAILED", "DISPUTED"], coerce=True)
    timestamp: Series[pd.Timestamp] = pa.Field(coerce=True)

    class Config:
        strict = True  # Tolak kolom yang tidak terdefinisi (menjaga determinisme)

class EnterpriseStreamingProcessor:
    def __init__(self, chunk_size: int = 100_000) -> None:
        self.chunk_size = chunk_size

    def generate_mock_data(self, total_rows: int) -> Generator[pd.DataFrame, None, None]:
        """Menghasilkan stream data dalam format chunked DataFrame simulasi."""
        categories = ["COMPLETED", "FAILED", "DISPUTED"]
        for i in range(0, total_rows, self.chunk_size):
            size = min(self.chunk_size, total_rows - i)
            yield pd.DataFrame({
                "transaction_id": [f"TX-{j}" for j in range(i, i + size)],
                "customer_id": np.random.randint(1000, 9999, size=size),
                "amount": np.random.exponential(scale=150.0, size=size),
                "status": np.random.choice(categories, size=size),
                "timestamp": pd.date_range(start="2023-01-01", periods=size, freq="S")
            })

    def process_stream(self, data_stream: Generator[pd.DataFrame, None, None]) -> Dict[str, Any]:
        total_records = 0
        total_amount_running = 0.0
        disputed_tx_count = 0

        logger.info("Memulai pemrosesan stream data berkinerja tinggi...")

        for chunk_idx, raw_chunk in enumerate(data_stream):
            # Optimasi Tipe Data Instan ke PyArrow Backend
            arrow_chunk = raw_chunk.convert_dtypes(dtype_backend="pyarrow")

            # Validasi Data Contract
            try:
                validated_chunk = TransactionSchema.validate(arrow_chunk)
            except pa.errors.SchemaErrors as err:
                logger.error(f"Schema violation terdeteksi pada chunk {chunk_idx}: {err.failure_cases}")
                raise

            # Vectorized Analytics Transformation (SIMD Optimized via NumPy/Arrow)
            amounts = validated_chunk["amount"].to_numpy()
            statuses = validated_chunk["status"].to_numpy()

            # Bitwise vector operations
            is_disputed = (statuses == "DISPUTED")
            
            # Agregasi stream tanpa akumulasi memori DataFrame
            total_records += len(validated_chunk)
            total_amount_running += np.sum(amounts)
            disputed_tx_count += np.sum(is_disputed)

            logger.info(
                f"Chunk {chunk_idx} sukses diproses. "
                f"Memory footprint chunk: {validated_chunk.memory_usage(deep=True).sum() / 1024**2:.2f} MB"
            )

        mean_amount = total_amount_running / total_records if total_records > 0 else 0.0

        return {
            "total_records": total_records,
            "aggregate_amount": total_amount_running,
            "mean_amount": mean_amount,
            "disputed_percentage": (disputed_tx_count / total_records) * 100 if total_records > 0 else 0.0
        }

if __name__ == "__main__":
    processor = EnterpriseStreamingProcessor(chunk_size=250_000)
    stream = processor.generate_mock_data(total_rows=1_000_000)
    metrics = processor.process_stream(stream)
    logger.info(f"Metrik Pipeline Berhasil Dihitung: {metrics}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform perbankan digital memproses 150 juta transaksi harian (~45 GB file mentah terkompresi GZIP). Worker pod Kubernetes (`c5.xlarge`, 4 vCPU, 8 GB RAM) mengalami kegagalan berkala dengan status OOMKilled (`Exit Code 137`) saat menjalankan job agregasi dan kalkulasi anomali harian.

#### Investigasi Akar Masalah (Root Cause Analysis)
1. Tim analitik menggunakan `pd.read_csv("s3://...", engine="c")` secara langsung, menyebabkan ekspansi dataset menjadi 130 GB dalam memori akibat CPython `object` casting.
2. Anomali dihitung menggunakan `apply(lambda row: calculate_score(row), axis=1)`. Operasi ini memanggil interpreter Python sebanyak 150 juta kali, menciptakan jutaan objek sementara dan saturasi RAM.
3. Ketiadaan deteksi *Data Drift* membuat skema yang tiba-tiba bergeser (perubahan representasi field tanggal) lolos ke data lake warehouse.

#### Solusi Arsitektur
1. **Pola Chunked Read dengan Zero-Copy Memory Projection:** Membaca data dalam batch 500.000 baris menggunakan PyArrow C-Engine.
2. **Transformasi Vektor Terbuka:** Mengubah kalkulasi skor menjadi perkalian dot-product skalar matriks menggunakan BLAS terakselerasi CPU.
3. **Statistical Drift Monitor:** Mengintegrasikan kalkulasi *Population Stability Index* (PSI) secara streaming untuk mendeteksi deviasi distribusi `amount`.

```python
import numpy as np

def calculate_psi(expected: np.ndarray, actual: np.ndarray, num_buckets: int = 10) -> float:
    """
    Menghitung Population Stability Index (PSI) antara baseline (expected)
    dan batch saat ini (actual) dengan efisiensi O(N log N).
    """
    # Tentukan quantile cutoff dari data baseline
    percentiles = np.linspace(0, 100, num_buckets + 1)
    buckets = np.percentile(expected, percentiles)
    buckets[0] = -np.inf
    buckets[-1] = np.inf

    # Hitung frekuensi observasi pada masing-masing bucket
    expected_counts, _ = np.histogram(expected, bins=buckets)
    actual_counts, _ = np.histogram(actual, bins=buckets)

    # Konversi ke fraksi dengan koreksi epsilon (mencegah pembagian 0)
    eps = 1e-4
    expected_pct = (expected_counts / len(expected)) + eps
    actual_pct = (actual_counts / len(actual)) + eps

    # Formula PSI: sum((Actual% - Expected%) * ln(Actual% / Expected%))
    psi_value = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi_value)

# Penerapan Validasi Drift di Produksi
baseline_transactions = np.random.normal(loc=100.0, scale=20.0, size=500_000)
current_transactions = np.random.normal(loc=115.0, scale=25.0, size=500_000) # Drift terjadi

psi_metric = calculate_psi(baseline_transactions, current_transactions)
if psi_metric > 0.2:
    # PSI > 0.2 mengindikasikan Data Drift Signifikan: picu alert PagerDuty
    print(f"CRITICAL: Data drift terdeteksi! Nilai PSI: {psi_metric:.4f}")
```

---

### 9. Trade-offs (Arsitektur & Desain)

```
                    KOMPLEKSITAS ARSITEKTURAL
                              ^
                              |      [Polars / DuckDB Engine]
                              |      (Streaming Out-of-Core, Latency Rendah)
                              |
                              |   [Pandas 2.0 + PyArrow]
                              |   (Memory C-Aligned, Moderate Complexity)
                              |
   [Vanilla Pandas In-Memory] |
   (Tinggi Latency, RAM O(N)) |
   ------------------------------------------------------------> SKALABILITAS DATA
```

| Pendekatan | Latency | Memory Footprint | Batasan Kapasitas | Biaya Komputasi |
| :--- | :--- | :--- | :--- | :--- |
| **Vanilla Pandas Eager** | Sangat Rendah untuk dataset kecil; Eksponensial saat swap disk. | Sangat Tinggi ($5\times - 10\times$ ukuran CSV). | Terbatas pada $\approx 25\%$ total sistem RAM. | Tinggi (Banyak idle thread & VM memory bloat). |
| **Pandas + PyArrow Backend** | Rendah (SIMD vectorization support). | Rendah (Penyimpanan bitmask, dictionary-encoded). | Dibatasi oleh single-node total memory. | Optimal untuk integrasi ekosistem Python yang sudah ada. |
| **Out-of-Core Chunking** | Sedang (I/O disk berulang per chunk). | Konstan (Dibatasi secara ketat oleh `chunksize`). | Tidak terbatas (mampu memproses ratusan GB pada single node). | Sangat Rendah; efisien untuk pipeline batching. |
| **Engine Terkompilasi (Polars/DuckDB)** | Ekstrem Rendah (Multithreaded Rust/C++ pipelining). | Sangat Rendah (Lazy memory mapping & predicate pushdown). | Menangani dataset hingga skala Multi-Terabyte. | Paling Rendah per gigabyte data terproses. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Silent Downcasting & The `inplace=True` Illusion
*   **Kesalahan:** Menggunakan `df.replace(..., inplace=True)` dengan asumsi menghemat memori.
*   **Fakta Mesin:** Di bawah kap mesin CPython/Pandas, `inplace=True` hampir selalu membuat alokasi *shallow* atau *deep copy* baru secara implisit, lalu menunjuk ulang referensi internal. Fitur ini bahkan didepresiasi di Pandas 2.0+.
*   **Solusi:** Gunakan assignment eksplisit dengan re-alokasi tipe terarah: `df = df.assign(col=...)`.

#### 2. Hidden Fragmentation via Iterative Column Insertion
*   **Kesalahan:** Menambahkan kolom satu per satu di dalam loop:
    ```python
    # ANTI-PATTERN: Memicu PerformanceWarning: DataFrame is highly fragmented.
    for i in range(100):
        df[f"col_{i}"] = ...
    ```
*   **Mekanisme Kegagalan:** Setiap penambahan kolom memaksa `BlockManager` mengalokasikan array 2D baru dan menyalin seluruh referensi kolom lama.
*   **Solusi:** Kumpulkan transformasi ke dalam Python `dict`, lalu satukan dengan `pd.concat(axis=1)`.

#### 3. Chained Indexing (`SettingWithCopyWarning`)
*   **Kesalahan:** `df[df['amount'] > 100]['status'] = 'FLAGGED'`.
*   **Mekanisme Kegagalan:** Operasi `__getitem__` pertama mengembalikan pointer berupa view atau copy tergantung internal memory stride. Modifikasi pada objek sementara bisa gagal diperbarui pada DataFrame induk secara diam-diam (*silent data corruption*).
*   **Solusi:** Selalu gunakan accessor berbasis indeks deterministik: `df.loc[df['amount'] > 100, 'status'] = 'FLAGGED'`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Data Contracts:** Definisikan skema input/output eksplisit (menggunakan `pandera.DataFrameModel`) sebelum data menyentuh lapisan transformasi bisnis.
- [ ] **Standardisasi PyArrow Strings:** Hindari dtype `object`. Gunakan `string[pyarrow]` atau `pd.ArrowDtype(pa.string())` untuk seluruh tipe tekstual.
- [ ] **Categorical Optimization:** Konversi kolom string kardinalitas rendah (< 5% nilai unik dari total baris) menjadi `category` atau `dictionary-encoded Arrow`.
- [ ] **Vektorisasi Murni Tanpa Interpreter Overhead:** Larang keras penggunaan `.apply()`, `.iterrows()`, atau `.itertuples()` pada computational hot-path. Gunakan ekspresi Boolean NumPy atau fungsi ufunc terkompilasi.
- [ ] **Bounded Memory Chunks:** Jika memproses file CSV/JSON mentah berskala gigabyte, tetapkan batas maksimum `chunksize` (rekomendasi: rentang $50.000 - 250.000$ baris per partisi).
- [ ] **Stream Agregasi:** Hindari menyimpan seluruh intermediate chunk ke dalam list memory (`pd.concat(chunks)`) jika hanya bertujuan menghitung metrik summary. Lakukan update akumulator skalar.
- [ ] **Telemetry Profiling Terintegrasi:** Log metrik latensi I/O, waktu komputasi, dan perubahan alokasi RAM per chunk (`tracemalloc` atau `psutil`).
- [ ] **Statistical Drift Hooks:** Pasang validasi statistik *Kolmogorov-Smirnov (KS-test)* atau *PSI* pada data inference kontinu terhadap baseline latihan.

---

### 12. Hands-on Practice

Buat dan simpan file implementasi berikut di direktori `hands-on/m02/`.

#### Struktur Direktori
```text
hands-on/m02/
├── config.py
├── generator.py
├── pipeline.py
└── test_pipeline.py
```

#### File: `hands-on/m02/config.py`
```python
import dataclasses

@dataclasses.dataclass(frozen=True)
class PipelineConfig:
    CHUNK_SIZE: int = 100_000
    TOTAL_ROWS: int = 500_000
    DRIFT_PSI_THRESHOLD: float = 0.25
    OUTPUT_FILE: str = "hands-on/m02/optimized_transactions.parquet"
```

#### File: `hands-on/m02/generator.py`
```python
import numpy as np
import pandas as pd
from typing import Generator

def generate_enterprise_events(total_rows: int, chunk_size: int) -> Generator[pd.DataFrame, None, None]:
    """Menghasilkan mock transaction logs berskala besar dengan memory streaming."""
    np.random.seed(42)
    categories = ["CREDIT", "DEBIT", "TRANSFER", "PAYMENT"]
    
    for i in range(0, total_rows, chunk_size):
        size = min(chunk_size, total_rows - i)
        yield pd.DataFrame({
            "event_id": [f"EV-{idx:08d}" for idx in range(i, i + size)],
            "account_id": np.random.randint(100_000, 999_999, size=size),
            "amount": np.random.exponential(scale=200.0, size=size),
            "type": np.random.choice(categories, size=size),
            "timestamp": pd.date_range("2024-01-01", periods=size, freq="ms")
        })
```

#### File: `hands-on/m02/pipeline.py`
```python
import os
import logging
import psutil
import pandas as pd
import numpy as np
from hands-on.m02.config import PipelineConfig
from hands-on.m02.generator import generate_enterprise_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("StreamingPipeline")

def get_current_process_memory_mb() -> float:
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def run_production_pipeline(config: PipelineConfig) -> None:
    logger.info(f"Memulai pipeline. Awal RAM: {get_current_process_memory_mb():.2f} MB")
    
    stream = generate_enterprise_events(config.TOTAL_ROWS, config.CHUNK_SIZE)
    baseline_sample = None
    processed_chunks = []

    for idx, chunk in enumerate(stream):
        # 1. Konversi ke memory-efficient types
        optimized_chunk = chunk.astype({
            "event_id": "string[pyarrow]",
            "account_id": "int32",
            "amount": "float32",
            "type": "category"
        })

        # 2. Vectorized Outlier Flagging (IQR via NumPy)
        amounts = optimized_chunk["amount"].to_numpy()
        q75, q25 = np.percentile(amounts, [75, 25])
        iqr = q75 - q25
        upper_bound = q75 + (1.5 * iqr)
        
        # Injeksi boolean array hasil komputasi SIMD
        optimized_chunk["is_outlier"] = amounts > upper_bound

        # 3. Retain sample baseline untuk drift detection
        if baseline_sample is None:
            baseline_sample = amounts
        
        processed_chunks.append(optimized_chunk)
        logger.info(
            f"Chunk {idx + 1} diproses. "
            f"Ukuran Chunk: {optimized_chunk.memory_usage(deep=True).sum() / 1024**2:.2f} MB | "
            f"Total Process RAM: {get_current_process_memory_mb():.2f} MB"
        )

    # 4. Konsolidasi output akhir ke Apache Parquet dengan Snappy Compression
    final_df = pd.concat(processed_chunks, ignore_index=True)
    os.makedirs(os.path.dirname(config.OUTPUT_FILE), exist_ok=True)
    final_df.to_parquet(config.OUTPUT_FILE, engine="pyarrow", compression="snappy", index=False)
    
    logger.info(f"Data tersimpan sukses di {config.OUTPUT_FILE}")
    logger.info(f"RAM Akhir: {get_current_process_memory_mb():.2f} MB")

if __name__ == "__main__":
    cfg = PipelineConfig()
    run_production_pipeline(cfg)
```

---

### 13. Exercise

#### Level 1 (Easy): Type Downcasting Profiler
Tulis sebuah fungsi Python bernama `optimize_numeric_dtypes(df: pd.DataFrame) -> pd.DataFrame` yang melakukan inspeksi tipe integer dan float pada setiap kolom. Lakukan downcasting ke tipe integer/float terkecil (`int8`, `int16`, `int32`, `float32`) yang aman terhadap batas `np.iinfo` dan `np.finfo` tanpa terjadinya truncation atau data loss.

#### Level 2 (Medium): Zero-Copy Parquet Predicate Pushdown
Gunakan library `pyarrow.dataset` untuk membaca dataset Parquet berukuran > 1 GB tanpa memuat kolom yang tidak relevan ke memori. Buat fungsi yang menerapkan filtering (*predicate pushdown*) langsung di level file I/O: hanya baris dengan `status == 'CRITICAL'` dan `timestamp >= '2024-01-01'` yang diinstansiasi ke dalam memori proses sebagai DataFrame.

#### Level 3 (Hard): Vectorized Exponential Smoothing Engine
Rancang kelas analitik `OnlineExponentialMovingAverage` yang memproses ribuan data time-series multivariat secara streaming. Algoritma harus menghitung metrik Exponential Moving Average (EMA) dengan smoothing factor $\alpha$:
$$S_t = \alpha \cdot Y_t + (1 - \alpha) \cdot S_{t-1}$$
Implementasi tidak boleh menggunakan `for` loops eksplisit di level baris atau fungsi internal Pandas (`.ewm()`), melainkan harus dikompilasi ke operasi vektor murni berbasis kernel NumPy atau ekspresi konvolusi linear 1D (`scipy.signal.lfilter` atau `np.convolve`).

---

### 14. Challenge

**Skenario Kasus:** Anda adalah Lead Data Engineer pada platform e-Commerce Tier-1. Sistem mendeteksi adanya fraud attack terdistribusi yang menyuntikkan ribuan pesanan anomali per detik ke dalam clickstream log. 

**Objektif:** Bangun modul analitik mandiri bernama `StreamingAnomalyDriftEngine` dengan batasan arsitektur sebagai berikut:
1. **Memory Ceiling:** Worker process dialokasikan batasan memori mutlak maksimum **512 MB RAM**. Kegagalan mempertahankan footprint di bawah 512 MB akan memicu terminasi paksa oleh host OS.
2. **Skala Beban Data:** Dataset uji memiliki volume 20.000.000 baris record JSON stream.
3. **Persyaratan Pemrosesan:**
   - Membaca file data terkompresi secara streaming berkesinambungan.
   - Melakukan validasi struktur schema data secara non-blocking.
   - Menghitung rolling correlation matrix (korelasi Pearson) antar 5 fitur numerik secara real-time.
   - Menghitung nilai uji *Two-Sample Kolmogorov-Smirnov (KS-Test)* antara window 100.000 baris terbaru dengan baseline historis. Jika p-value $< 0.01$, engine harus menembakkan trigger alert disk.
   - Hasil yang telah divalidasi dan dianotasi harus ditulis ulang ke dalam partisi Parquet bertingkat (`year=YYYY/month=MM/day=DD`) di disk lokal.

*Tantangan ini tidak memiliki solusi instan; efisiensi buffer ring, garbage collector invocations (`gc.collect()`), dan pemilihan tipe data bit-level menentukan keberhasilan kode Anda.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Konseptual Singkat)
1. Berapa ukuran byte minimum dari satu objek CPython `PyObject` untuk tipe integer 64-bit pada arsitektur sistem operasi 64-bit modern?
   - A. 8 bytes
   - B. 16 bytes
   - C. 28 bytes
   - D. 64 bytes
   *Jawaban:* C. (16 bytes header + 8 bytes reference count/type pointer + 8 bytes value/digit array).

2. Apa fungsi utama dari *Null Bitmap* pada Apache Arrow array layout?
   - A. Menyimpan indeks nilai yang terduplikasi.
   - B. Menyimpan representasi 1-bit boolean per elemen yang mengindikasikan apakah nilai tersebut NULL, tanpa merusak tipe data numerik native.
   - C. Mengenkripsi isi data agar tidak dapat dibaca oleh proses lain.
   - D. Mengurutkan data secara leksikografis.
   *Jawaban:* B.

3. Mengapa metode `df.iterrows()` dianggap sebagai anti-pattern utama dalam ekosistem analitik Python berkinerja tinggi?
   - A. Karena tidak mendukung tipe data string.
   - B. Karena mengonversi setiap baris data menjadi objek `pd.Series` baru di setiap iterasi, menghasilkan jutaan alokasi objek kecil di heap memory dan overhead interpreter yang sangat masif.
   - C. Karena mengubah urutan index asli secara acak.
   - D. Karena `iterrows()` selalu memicu kebocoran memori (memory leak).
   *Jawaban:* B.

4. Perilaku apa yang terjadi pada Pandas versi lama (<2.0) jika kolom integer memiliki satu saja nilai yang hilang (`None` atau `np.nan`)?
   - A. Kolom tersebut otomatis dihapus.
   - B. Terjadi `TypeError` saat runtime.
   - C. Seluruh kolom secara implisit dikonversi (*upcasted*) menjadi tipe `float64`.
   - D. Nilai hilang otomatis diganti dengan nilai default `0`.
   *Jawaban:* C.

5. Atribut apa pada NumPy `ndarray` yang mendikte jumlah byte yang harus dilompati dalam buffer memori fisik untuk mengakses elemen pada dimensi berikutnya?
   - A. `shape`
   - B. `dtype`
   - C. `strides`
   - D. `ndim`
   *Jawaban:* C.

#### Bagian 2: Intermediate (Analisis Kinerja & Mekanika Sistem)
6. Manakah yang menawarkan efisiensi eksekusi instruksi CPU tertinggi pada operasi pemrosesan array numerik 10 juta baris?
   - A. `[math.sqrt(x) for x in data_list]`
   - B. `data_series.apply(np.sqrt)`
   - C. `np.sqrt(data_array)`
   - D. `data_series.map(lambda x: x**0.5)`
   *Jawaban:* C. (Pemanggilan langsung universal function C-kernel NumPy mengeliminasi intervensi stack frame interpreter Python dan mendukung instruksi SIMD hardware).

7. Bagaimana teknik *Zero-Copy Deserialization* pada format Apache Arrow/Parquet mengoptimalkan alokasi memori saat proses *Inter-Process Communication* (IPC)?
   *Jawaban:* Arrow menyusun representasi data dalam memori yang identik dengan format serialisasi disk/wire. Oleh karena itu, proses penerima dapat langsung memetakan pointer alamat memori (`mmap`) ke buffer shared memory tanpa melakukan decoding byte, unpacking, atau alokasi buffer baru di heap.

8. Apa implikasi struktural dari peringatan `PerformanceWarning: DataFrame is highly fragmented` pada eksekusi Pandas?
   *Jawaban:* DataFrame terdiri dari terlalu banyak array blok independen (biasanya akibat modifikasi kolom secara berulang). Hal ini menyebabkan penurunan drastis pada lokalisasi cache CPU dan meningkatkan latensi komputasi karena operasi harus melompat ke ratusan lokasi memori terpisah.

9. Dalam pengujian *Data Drift*, jika nilai metrik *Population Stability Index* (PSI) berada pada rentang $0.1 \le \text{PSI} \le 0.25$, tindakan apa yang secara teknis harus diambil dalam pipeline enterprise?
   *Jawaban:* Rentang ini mengindikasikan terjadinya pergeseran moderat (*moderate drift*). Pipeline harus mengirimkan notifikasi *warning* pada monitoring system, menandai batch untuk inspeksi lanjutan, dan mempersiapkan penjadwalan ulang retraining model tanpa perlu menghentikan sistem secara fatal.

10. Mengapa `inplace=True` sering kali tidak memberikan keuntungan reduksi memori pada lingkungan Pandas produksi?
    *Jawaban:* Secara internal, sebagian besar fungsi Pandas tetap membuat salinan array data untuk menjamin isolasi referensi sebelum menunjuk pointer lama ke blok baru. `inplace=True` hanyalah ilusi sintaktis yang tidak menjamin in-place memory mutation di level buffer C.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1:** Sebuah microservice Python batch processing membaca file CSV 10 GB pada pod container dengan limit memori 4 GB. Aplikasi mengalami crash mendadak tanpa log error traceback (`Exit Code 137`). Setelah dilakukan investigasi, kode menggunakan `pd.read_csv("data.csv")`. Jelaskan mekanisme teknis penyebab crash dan tuliskan perbaikan baris kode intake-nya!
    *Solusi Analisis:*
    - **Penyebab:** CSV 10 GB di disk membesar menjadi 30-40 GB di RAM saat diparsing menjadi tipe data CPython default. Konsumsi RAM melampaui batas container cgroups (4 GB), sehingga Linux OOM-Killer mematikan proses via sinyal `SIGKILL`.
    - **Perbaikan Kode:**
      ```python
      # Gunakan streaming chunking dengan Arrow backend
      chunks = pd.read_csv("data.csv", chunksize=100_000, engine="pyarrow", dtype_backend="pyarrow")
      for chunk in chunks:
          # Proses data secara parsial
          process_chunk(chunk)
      ```

12. **Skenario 2:** Anda menemukan kode ETL analitik warisan (*legacy*) yang ditulis sebagai berikut:
    ```python
    for idx, row in df.iterrows():
        df.at[idx, 'risk_score'] = (row['age'] * 0.1) + (row['debt'] / (row['income'] + 1e-5))
    ```
    Jika `df` memiliki 5.000.000 baris, perbaiki kode tersebut ke standar efisiensi industri tier-1!
    *Solusi Kode:*
    ```python
    # Vektorisasi murni menggunakan representasi NumPy array
    ages = df['age'].to_numpy()
    debts = df['debt'].to_numpy()
    incomes = df['income'].to_numpy()

    # Eksekusi SIMD matematis langsung di level register CPU
    df['risk_score'] = (ages * 0.1) + (debts / (incomes + 1e-5))
    ```

13. **Skenario 3:** Tim BI Anda mengeluhkan query data analitik yang lambat saat membaca ribuan file Parquet historis yang berukuran masing-masing hanya 2 MB (*small files problem*). Apa dampak fenomena ini pada performa read pipeline berbasis Python, dan arsitektur perbaikan apa yang harus diterapkan?
    *Solusi Analisis:*
    - **Dampak:** *High I/O Overhead*. Membaca ribuan file kecil membebani metadata lookup (listing object storage S3/GCS), inefisiensi decoding footer Parquet, dan tingginya network handshake latencies.
    - **Solusi Arsitektur:** Terapkan proses *Compaction Batching*. Gunakan engine PyArrow/DuckDB untuk menggabungkan file-file 2 MB tersebut menjadi file target berukuran optimal ($128\text{ MB} - 512\text{ MB}$) dengan alignment row-group terdistribusi dan kompresi Snappy/ZSTD.

---

### 16. Summary

1. **CPython Memory Overhead:** Objek Python native memperkenalkan pembengkakan alokasi memori yang signifikan. Lingkungan analitik enterprise wajib menggunakan buffer kontigu (NumPy) atau columnar bit-aligned storage (Apache Arrow).
2. **Columnar Orientation & SIMD:** Format columnar memungkinkan paralelisasi di level instruksi prosesor (SIMD), isolasi data null via bitmap, dan pemanfaatan instruksi CPU modern tanpa overhead perulangan baris.
3. **Out-of-Core Processing Paradigm:** Skalabilitas komputasi data tidak selalu memerlukan penambahan kapasitas RAM (*vertical scaling*). Pola *chunking*, generator streaming, dan representasi tipe data yang tepat memungkinkan pengolahan data berskala gigabyte pada mesin komputasi terbatas.
4. **Data Reliability & Contracts:** Pipeline analitik produksi harus menerapkan penegakan skema yang ketat (*data contracts*) dan observabilitas statistik kontinu (*drift detection*) untuk mendeteksi silent data corruption sebelum data masuk ke tahap persistensi atau inferensi.