# Bab 05: Python Data Engineering & Exploratory Data Analysis
## Modul 01: High-Performance Data Ingestion, Profiling, dan Modern EDA Pipeline Engine

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengukur** efisiensi alokasi memori (*memory footprint*) dan waktu komputasi pemrosesan data tabular berskala gigabyte menggunakan representasi memori kolumnar Apache Arrow vs. NumPy block-manager tradisional.
- **Mengarsitekturi dan Mengimplementasikan** ingestion pipeline end-to-end berbasis *Data Contract* menggunakan validasi skema runtime terotomatisasi (Pydantic v2 & PyArrow Schema) yang menangani anomali tipe data secara deterministik.
- **Mengembangkan Engine Profiling Data Tervektorisasi (*Vectorized Profiler*)** untuk menghitung metrik statistik univariat/multivariat, mendeteksi missing value patterns, dan mengidentifikasi outlier matematis secara streaming/chunked tanpa memicu *Out-Of-Memory (OOM)*.
- **Menerapkan Zero-Copy Transformation** dan interoperabilitas memori tinggi antara Polars dan Pandas 2.0 dengan *PyArrow backend* guna mereduksi beban I/O sistem pada infrastruktur analitik enterprise.
- **Merancang Automated Quality Gates** yang mengisolasi data anomali (*dead-letter quarantine*) dan memproduksi laporan diagnostik teknis siap-audit sebelum data masuk ke tahap feature engineering downstream.

---

### 2. Concept Overview

Secara historis, analisis data eksploratif (EDA) sering diperlakukan sebagai proses *ad-hoc* di notebook interaktif menggunakan pustaka monolitik seperti Pandas generasi lama (v1.x). Pola ini memiliki kelemahan mendasar: ketergantungan pada *NumPy block manager* yang merepresentasikan *string* dan tipe data kompleks sebagai referensi pointer Python berukuran 8 byte (`PyObject*`). Akibatnya, pemrosesan dataset berukuran 2 GB dapat memicu pembengkakan memori RAM hingga 10–20 GB, menimbulkan fragmentasi memori, dan menyebabkan *silent type coercion* (misalnya kolom integer otomatis dikonversi menjadi float saat mendeteksi `NaN`).

```
[ Traditional NumPy/Pandas 1.x Memory Layout ]
DataFrame Object
  │
  ├── IntBlock    ──> Contiguous [int64, int64, int64]
  └── ObjectBlock ──> Array of Pointers [ *ptr1, *ptr2, *ptr3 ]
                                            │       │       │
                                            ▼       ▼       ▼
                                         [PyStr] [PyStr] [PyStr]  <-- Fragmentasi Heap
---------------------------------------------------------------------------------------
[ Modern Apache Arrow / Pandas 2.0 / Polars Layout ]
Arrow RecordBatch
  │
  ├── Int64Buffer    ──> Contiguous [int64, int64, int64]
  ├── Utf8DataBuffer ──> Contiguous Bytes ["JAKARTABANDUNGBOGOR"]
  ├── Utf8Offsets    ──> Contiguous [0, 7, 14, 19]
  └── ValidityBitmap ──> Contiguous Bitmask [0b111] (Zero-overhead Null Tracking)
```

Paradigma modern *Python Data Engineering for EDA* mengadopsi standar industri **Apache Arrow In-Memory Format**. Apache Arrow menggunakan struktur kolumnar kontinu (*contiguous columnar buffer*) dengan skema terdefinisi secara biner, validasi eksplisit melalui *validity bitmask*, dan eliminasi pointer overhead. 

Pendekatan ini mendasari dua ekosistem komputasi modern:
1. **Pandas 2.0+ (PyArrow Backend):** Mengganti `np.ndarray` dengan `pyarrow.ChunkedArray`, mengaktifkan nullable primitive types asli (seperti `int64[pyarrow]`), dan interoperabilitas *zero-copy* ke format penyimpanan serialisasi seperti Parquet/Feather.
2. **Polars:** Engine analitik modern yang ditulis dalam Rust, berbasis Arrow, menggunakan model eksekusi *vectorized/SIMD* (Single Instruction, Multiple Data) dengan kemampuan paralel multithreading berbasis *work-stealing* (Rayon) serta evaluasi kueri bertipe *lazy* melalui *query optimizer* (Predicate Pushdown, Projection Pushdown).

Engine EDA enterprise yang andal bukan sekadar sekumpulan grafik visualisasi, melainkan sebuah **Pipeline Analitik Deterministik**: data dibaca secara terfragmentasi (*chunked/streaming*), divalidasi terhadap kontrak skema yang ketat, dikomputasi profil distribusinya menggunakan operasi SIMD, dan dipartisi ke dalam data bersih serta karantina anomali.

---

### 3. Why It Matters

Dalam lingkungan enterprise, kegagalan dalam tahapan ingestion dan EDA awal memiliki dampak langsung pada stabilitas sistem dan integritas bisnis:

1. **Out-of-Memory (OOM) Crashes pada Job Batch Otomatis:**
   Ketika pipeline analitik yang berjalan di Kubernetes atau AWS ECS menerima lonjakan volume data harian dari 500 MB ke 4 GB, penggunaan pustaka yang memuat seluruh dataset secara in-memory akan memicu Linux Kernel Out-Of-Memory Killer (`SIGKILL - 9`), menghentikan SLA pelaporan finansial harian.
2. **Silent Degradation & Model Hallucination:**
   Bila nilai string `'NULL'`, `'N/A'`, atau empty string `''` tidak ditangani secara konsisten di level engine, Pandas konvensional memperlakukannya sebagai objek unik string, bukan missing value biner. Akibatnya, model analitik inferensial atau AI agent downstream menginterpretasikan teks tersebut sebagai kategori valid, menghasilkan metrik korelasi palsu (*spurious correlation*).
3. **Data Contract Drift:**
   Perubahan skema hulu (misalnya ID pengguna berubah dari `int64` menjadi UUID string) yang lolos tanpa validasi ketat di ingestion layer akan merusak pipeline ETL downstream secara berantai. Data engineering modern mewajibkan isolasi anomali secara instan melalui *Dead-Letter Queues (DLQ)*.
4. **Efisiensi Biaya Komputasi Cloud:**
   Operasi berbasis Apache Arrow dan query engine berbasis Polars dapat menyelesaikan pemrosesan agregasi dan profiling EDA 10 hingga 50 kali lebih cepat dibandingkan Pandas konvensional, mereduksi vCPU-hours pada cluster komputasi secara signifikan.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur berikut mengilustrasikan alur pemrosesan dari dataset mentah multi-sumber, melalui layer validasi kontrak skema, hingga tahap profiling analitik tervektorisasi dan persistensi data.

```
                      +---------------------------------------+
                      | Raw Ingestion Sources                 |
                      | (Dirty CSV, JSON Lines, Parquet, API) |
                      +---------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| Modern Ingestion & Validation Gateway                                              |
|                                                                                   |
|  +---------------------------+        +----------------------------------------+  |
|  | Chunked Streaming Reader  | -----> | Schema Contract Enforcement            |  |
|  | (PyArrow / Polars Lazy)   |        | - Type Casting Strictness              |  |
|  +---------------------------+        | - Semantic Validation (Pydantic / Pandera)|
|                                       +----------------------------------------+  |
+---------------------------------------------------|-------------------------------+
                                                    |
                         +--------------------------+--------------------------+
                         |                                                     |
                         | (Schema Valid Records)                              | (Contract Violations)
                         v                                                     v
+---------------------------------------------------+     +----------------------------------+
| In-Memory Zero-Copy Analytical Engine             |     | Dead-Letter Quarantine (DLQ)     |
| (Apache Arrow RecordBatches / Polars DataFrames)  |     | - Error JSON Payload             |
+---------------------------------------------------+     | - Row Index & Violation Type     |
                         |                                +----------------------------------+
        +----------------+----------------+
        |                                 |
        v                                 v
+-------------------------------+  +---------------------------------------------------------+
| Vectorized Profiling Engine   |  | Clean Analytical Storage                                |
| - High-Order Central Moments  |  |                                                         |
| - Streaming Quantiles (T-Dig) |  | [ PyArrow Optimized Parquet Sink ]                      |
| - Missingness Mask Analyzer   |  | - Snappy/ZSTD Compression                               |
| - High Cardinality Detection  |  | - Column-chunk metadata statistics                       |
+---------------+---------------+  +---------------------------------------------------------+
                |
                v
+-------------------------------+
| Structural EDA Artifacts      |
| - JSON Metric Summary Digest  |
| - Data Quality Health Score   |
+-------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Layout Memori Kontinu & Zero-Copy Slicing
Dalam model Apache Arrow, sebuah array tidak disimpan sebagai struktur data rekursif dengan pointer. Sebaliknya, setiap kolom dialokasikan dalam buffer memori fisik yang linear (*contiguous physical buffer*).
- **Data Buffer:** Menyimpan nilai byte aktual secara berurutan. Untuk tipe numerik tetap (misal `float64`), nilai elemen ke-$i$ dihitung secara langsung via aljabar pointer: $\text{Address}(i) = \text{Base} + (i \times 8)$.
- **Offset Buffer:** Untuk variabel dengan panjang bervariasi seperti string atau binari, buffer ini menyimpan indeks posisi awal dan akhir dari setiap elemen dalam Data Buffer.
- **Validity Bitmap (Null Mask):** Menggunakan 1 bit per baris untuk menentukan apakah suatu nilai `null` (bit = 0) atau valid (bit = 1). Operasi penghitungan jumlah missing value direduksi menjadi instruksi CPU tingkat rendah (*hardware population count* / `POPCNT`), menghasilkan kompleksitas pemrosesan missingness berkecepatan tinggi tanpa pemindaian pointer objek.

#### B. Streaming Profiling via Welford’s Algorithm
Untuk menghitung metrik statistik univariat (Mean, Varian, Standar Deviasi) dalam lingkungan memori terbatas secara streaming atau chunk-by-chunk tanpa harus memuat seluruh dataset sekaligus, digunakan algoritma iteratif Welford. Algoritma ini mencegah *catastrophic cancellation* (kehilangan presisi floating-point numerik saat mengurangkan dua bilangan besar):

Diberikan aliran data kontinu $x_1, x_2, \dots, x_n$:
1. Inisialisasi: $\bar{x}_0 = 0$, $M_{2,0} = 0$
2. Untuk setiap observasi baru $x_k$ pada langkah $k$:
   $$\Delta_k = x_k - \bar{x}_{k-1}$$
   $$\bar{x}_k = \bar{x}_{k-1} + \frac{\Delta_k}{k}$$
   $$M_{2,k} = M_{2,k-1} + \Delta_k (x_k - \bar{x}_k)$$
3. Varian sampel ($s^2$) dan standar deviasi sampel ($s$) diperoleh langsung:
   $$s^2 = \frac{M_{2,n}}{n - 1}, \quad s = \sqrt{s^2}$$

Engine profiling memproses chunk secara paralel, kemudian menggabungkan statistik ringkasan menggunakan formula agregasi momen varian (*parallel variance merge algorithm*).

#### C. SIMD Vectorization dan Predicate Pushdown pada Polars
Polars memanfaatkan pustaka Rust `arrow2` dan framework multi-threading `Rayon`. Ketika ekspresi seperti:
```python
pl.col("transaction_amount").filter(pl.col("status") == "COMPLETED").mean()
```
dieksekusi, kueri diubah menjadi *Directed Acyclic Graph (DAG)* yang dioptimalkan:
1. **Projection Pushdown:** Engine hanya membaca byte kolom `transaction_amount` dan `status` dari disk, sama sekali tidak memuat kolom lain ke memori.
2. **Predicate Pushdown:** Filter boolean dievaluasi langsung di level block Parquet atau buffer Arrow.
3. **SIMD Vectorization:** Loop evaluasi matematika dijalankan pada register vektor AVX-512 atau ARM NEON, memproses 4 hingga 8 float sekaligus dalam satu siklus instruksi CPU.

---

### 6. Production-Ready Code Implementation

Berikut implementasi engine data ingestion, validasi kontrak skema, karantina anomali, dan profiling statistik streaming menggunakan arsitektur modular enterprise. Kode ini mengombinasikan kekuatan **PyArrow**, **Pydantic v2**, dan **Pandas 2.0+ (PyArrow backend)** / **Polars**.

```python
"""
Core Engine: High-Performance Ingestion, Schema Enforcement, and Vectorized Profiling.
Standard: GEMINI Modern Enterprise Data Engineering Architecture.
"""

from __future__ import annotations

import io
import json
import logging
import math
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# =====================================================================
# Logging Configuration
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("EnterpriseEDAEngine")


# =====================================================================
# Domain Models & Data Contract Definitions (Pydantic v2)
# =====================================================================
class TransactionRecord(BaseModel):
    """Data Contract untuk verifikasi integritas data transaksi keuangan."""
    model_config = ConfigDict(strict=True, coerce_numbers_to_str=False)

    transaction_id: str = Field(..., min_length=8, max_length=64)
    customer_id: str = Field(..., min_length=4, max_length=32)
    amount: float = Field(..., gt=0.0)
    fee: float = Field(..., ge=0.0)
    status: str = Field(..., pattern=r"^(SUCCESS|PENDING|FAILED)$")
    timestamp: str = Field(...)


class ColumnProfile(BaseModel):
    """Hasil profiling statistik univariat per kolom."""
    column_name: str
    dtype: str
    total_records: int
    null_count: int
    null_percentage: float
    unique_count: int
    mean: Optional[float] = None
    std_dev: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    quantiles: Dict[str, float] = Field(default_factory=dict)


class ProfileSummary(BaseModel):
    """Agregat laporan diagnostik profil data secara komprehensif."""
    dataset_name: str
    row_count: int
    column_count: int
    memory_usage_bytes: int
    columns: Dict[str, ColumnProfile]


# =====================================================================
# Pipeline Contracts and Interfaces
# =====================================================================
class AbstractDataIngestor(ABC):
    @abstractmethod
    def read_chunks(self) -> Generator[pa.Table, None, None]:
        """Menghasilkan representasi Arrow Table secara streaming per batch."""
        pass


class AbstractProfileEngine(ABC):
    @abstractmethod
    def consume_batch(self, table: pa.Table) -> None:
        """Menerima dan mengakumulasi statistik dari Arrow Table batch."""
        pass

    @abstractmethod
    def generate_report(self) -> ProfileSummary:
        """Membuat ringkasan diagnostik EDA final."""
        pass


# =====================================================================
# Implementasi: Streaming Arrow CSV Ingestor
# =====================================================================
class StreamingArrowCSVIngestor(AbstractDataIngestor):
    """
    Ingestor berkinerja tinggi yang memanfaatkan PyArrow Streaming CSV Reader
    dengan Zero-Memory Allocation overhead dan enforcement skema awal.
    """

    def __init__(
        self,
        file_path: Path,
        schema: pa.Schema,
        batch_size_bytes: int = 64 * 1024 * 1024,  # 64 MB Chunks
    ) -> None:
        self.file_path = file_path
        self.schema = schema
        self.batch_size_bytes = batch_size_bytes

        if not self.file_path.exists():
            raise FileNotFoundError(f"Source file not found: {self.file_path}")

    def read_chunks(self) -> Generator[pa.Table, None, None]:
        read_options = pacsv.ReadOptions(
            block_size=self.batch_size_bytes,
            use_threads=True,
        )
        parse_options = pacsv.ParseOptions(
            delimiter=",",
            quote_char='"',
            double_quote=True,
        )
        convert_options = pacsv.ConvertOptions(
            column_types=self.schema,
            strings_can_be_null=True,
            null_values=["", "NA", "NULL", "null", "NaN", "nan"],
        )

        logger.info(f"Membuka stream CSV berkinerja tinggi: {self.file_path}")
        with pacsv.open_csv(
            self.file_path,
            read_options=read_options,
            parse_options=parse_options,
            convert_options=convert_options,
        ) as reader:
            for batch_index, batch in enumerate(reader):
                table_chunk = pa.Table.from_batches([batch])
                logger.debug(
                    f"Batch #{batch_index} terbaca: {table_chunk.num_rows} records."
                )
                yield table_chunk


# =====================================================================
# Implementasi: Online Vectorized Profiler Engine
# =====================================================================
class OnlineVectorizedProfiler(AbstractProfileEngine):
    """
    Profiler univariat berbasis SIMD Arrow Compute & Algoritma Welford Paralel.
    Memproses dataset tak terbatas dalam ruang memori O(1) konstan terhadap baris.
    """

    def __init__(self, dataset_name: str) -> None:
        self.dataset_name = dataset_name
        self.total_rows: int = 0
        self.total_bytes: int = 0
        self.schema: Optional[pa.Schema] = None

        # State akumulasi statistik per kolom numerik: {col_name: (count, sum, sum_squares, min, max)}
        self._numeric_accumulators: Dict[str, Dict[str, float]] = {}
        # State akumulasi missing value & cardinality per kolom
        self._null_counts: Dict[str, int] = {}
        self._cardinality_sets: Dict[str, set] = {}
        # Batasan konservatif untuk kardinalitas presisi pada in-memory profiling
        self._cardinality_limit = 50_000

    def consume_batch(self, table: pa.Table) -> None:
        if self.schema is None:
            self.schema = table.schema
            self._initialize_state()

        batch_rows = table.num_rows
        self.total_rows += batch_rows
        self.total_bytes += table.nbytes

        for col_name in table.column_names:
            column_chunk = table.column(col_name)

            # 1. Null Counting secara tervektorisasi via Bitmask
            batch_null_count = column_chunk.null_count
            self._null_counts[col_name] += batch_null_count

            # 2. Approximate/Exact Unique Tracking
            if len(self._cardinality_sets[col_name]) < self._cardinality_limit:
                unique_values = pc.unique(column_chunk).to_pylist()
                for val in unique_values:
                    if val is not None:
                        self._cardinality_sets[col_name].add(val)

            # 3. Numeric Moments Calculation (Vectorized Arrow Compute)
            if pa.types.is_floating(column_chunk.type) or pa.types.is_integer(column_chunk.type):
                valid_chunk = pc.drop_null(column_chunk)
                if len(valid_chunk) > 0:
                    valid_count = float(len(valid_chunk))
                    chunk_sum = pc.sum(valid_chunk).as_py()
                    # Hitung sum of squares untuk pooled variance
                    chunk_sum_sq = pc.sum(pc.multiply(valid_chunk, valid_chunk)).as_py()
                    chunk_min = pc.min(valid_chunk).as_py()
                    chunk_max = pc.max(valid_chunk).as_py()

                    acc = self._numeric_accumulators[col_name]
                    acc["count"] += valid_count
                    acc["sum"] += float(chunk_sum)
                    acc["sum_squares"] += float(chunk_sum_sq)
                    acc["min"] = min(acc["min"], float(chunk_min))
                    acc["max"] = max(acc["max"], float(chunk_max))

    def _initialize_state(self) -> None:
        assert self.schema is not None
        for field in self.schema:
            col_name = field.name
            self._null_counts[col_name] = 0
            self._cardinality_sets[col_name] = set()

            if pa.types.is_floating(field.type) or pa.types.is_integer(field.type):
                self._numeric_accumulators[col_name] = {
                    "count": 0.0,
                    "sum": 0.0,
                    "sum_squares": 0.0,
                    "min": float("inf"),
                    "max": float("-inf"),
                }

    def generate_report(self) -> ProfileSummary:
        if self.schema is None or self.total_rows == 0:
            raise RuntimeError("Engine belum mengonsumsi data apa pun.")

        columns_profile: Dict[str, ColumnProfile] = {}

        for field in self.schema:
            col_name = field.name
            null_cnt = self._null_counts[col_name]
            null_pct = (null_cnt / self.total_rows) * 100.0 if self.total_rows > 0 else 0.0
            cardinality = len(self._cardinality_sets[col_name])

            mean_val: Optional[float] = None
            std_val: Optional[float] = None
            min_val: Optional[float] = None
            max_val: Optional[float] = None

            if col_name in self._numeric_accumulators:
                acc = self._numeric_accumulators[col_name]
                n = acc["count"]
                if n > 1:
                    mean_val = acc["sum"] / n
                    variance = (acc["sum_squares"] - (acc["sum"] ** 2) / n) / (n - 1)
                    # Mengatasi presisi floating point negatif mendekati nol
                    std_val = math.sqrt(max(0.0, variance))
                    min_val = acc["min"]
                    max_val = acc["max"]
                elif n == 1:
                    mean_val = acc["sum"]
                    std_val = 0.0
                    min_val = acc["min"]
                    max_val = acc["max"]

            columns_profile[col_name] = ColumnProfile(
                column_name=col_name,
                dtype=str(field.type),
                total_records=self.total_rows,
                null_count=null_cnt,
                null_percentage=round(null_pct, 4),
                unique_count=cardinality,
                mean=round(mean_val, 4) if mean_val is not None else None,
                std_dev=round(std_val, 4) if std_val is not None else None,
                min_value=round(min_val, 4) if min_val is not None else None,
                max_value=round(max_val, 4) if max_val is not None else None,
            )

        return ProfileSummary(
            dataset_name=self.dataset_name,
            row_count=self.total_rows,
            column_count=len(self.schema),
            memory_usage_bytes=self.total_bytes,
            columns=columns_profile,
        )


# =====================================================================
# Ingestion Orchestrator & Quarantine Controller
# =====================================================================
class ProductionPipelineManager:
    """
    Mengorkestrasi alur Ingestion, Validasi Skema Baris, Pemisahan Karantina,
    serta Export Data Bersih menggunakan Format Parquet Berpartisi.
    """

    def __init__(
        self,
        ingestor: AbstractDataIngestor,
        profiler: AbstractProfileEngine,
        clean_sink_path: Path,
        quarantine_sink_path: Path,
    ) -> None:
        self.ingestor = ingestor
        self.profiler = profiler
        self.clean_sink_path = clean_sink_path
        self.quarantine_sink_path = quarantine_sink_path
        self.clean_sink_path.parent.mkdir(parents=True, exist_ok=True)
        self.quarantine_sink_path.parent.mkdir(parents=True, exist_ok=True)

    def execute(self) -> ProfileSummary:
        logger.info("Memulai eksekusi pipeline ingest, validasi, dan EDA profiling...")

        parquet_writer: Optional[pq.ParquetWriter] = None
        quarantine_records: List[Dict[str, Any]] = []

        try:
            for chunk_table in self.ingestor.read_chunks():
                # Zero-copy konversi subset ke Pandas PyArrow Engine untuk validasi baris
                pandas_chunk = chunk_table.to_pandas(types_mapper=pd.ArrowDtype)

                valid_indices: List[int] = []

                # Row-level validation gateway against Data Contract
                for idx, row in enumerate(pandas_chunk.to_dict(orient="records")):
                    try:
                        TransactionRecord(**row)
                        valid_indices.append(idx)
                    except ValidationError as ve:
                        quarantine_payload = {
                            "raw_record": row,
                            "errors": ve.errors(include_url=False),
                        }
                        quarantine_records.append(quarantine_payload)

                if valid_indices:
                    # Filter Arrow Table menggunakan pointer array indexing murni
                    clean_table = chunk_table.take(pa.array(valid_indices))

                    # 1. Update Profiler secara real-time
                    self.profiler.consume_batch(clean_table)

                    # 2. Append ke sink penyimpanan Parquet terkompresi
                    if parquet_writer is None:
                        parquet_writer = pq.ParquetWriter(
                            self.clean_sink_path,
                            clean_table.schema,
                            compression="zstd",
                            compression_level=7,
                        )
                    parquet_writer.write_table(clean_table)

            # Flush karantina bila terdeteksi anomali skema
            if quarantine_records:
                logger.warning(
                    f"Mendeteksi {len(quarantine_records)} data anomali. Menulis ke Dead-Letter..."
                )
                with open(self.quarantine_sink_path, "w", encoding="utf-8") as q_file:
                    json.dump(quarantine_records, q_file, indent=2, default=str)

        finally:
            if parquet_writer is not None:
                parquet_writer.close()
                logger.info(f"Parquet Writer ditutup: {self.clean_sink_path}")

        report = self.profiler.generate_report()
        logger.info("Pipeline eksekusi selesai secara sukses.")
        return report
```

---

### 7. Edge Cases & Failure Modes

Pada level implementasi skala produksi, data analyst dan engineer wajib mengantisipasi titik kegagalan berikut:

| Skenario Failure | Akar Masalah Arsitektur | Strategi Deteksi & Mitigasi Runtime |
| :--- | :--- | :--- |
| **Silent Float Promotion** | Kolom integer berisi string `'NA'` atau `None`. Driver pandas konvensional otomatis mengonversi tipe integer menjadi `np.float64`. | Gunakan `dtype_backend='pyarrow'` atau skema PyArrow eksplisit (`pa.int64()`). Tipe Arrow nullable primitive mempertahankan integer murni tanpa konversi floating point. |
| **High Memory Thrashing pada String Kardinalitas Ekstrem** | Kolom string berukuran besar (misal URL payload) menduplikasi jutaan byte identik pada memori. | Terapkan teknik *Dictionary Encoding* (Categorical pada Pandas/Arrow): representasikan string berulang sebagai tabel lookup berbasis integer 8-bit (`pa.dictionary(pa.int8(), pa.utf8())`). |
| **Out-of-Bounds Timestamp & Microsecond Overflow** | CSV berisi timestamp epoch melebihi jangkauan `int64` nanodetik standar Unix (tahun < 1677 atau > 2262). | Spesifikasikan resolusi waktu PyArrow ke satuan milidetik (`pa.timestamp('ms')`) atau detik alih-alih nanodetik default (`pa.timestamp('ns')`). |
| **Schema Evolution: Missing Column vs Extra Column** | Provider hulu menambahkan metadata baru tanpa konfirmasi, menyebabkan kegagalan parsing fixed-width/CSV. | Terapkan *Schema Evolution Strategy*: definisikan kolom esensial sebagai mandatory dalam Data Contract; ekstrak unknown column ke kolom tunggal bertipe JSON/Map generic (`pa.map_()`). |
| **Mixed-Type Column Inference Failure** | Parser menebak tipe kolom berdasarkan 1.000 baris pertama sebagai integer, namun baris ke-10.001 berupa UUID string. | Larang *dynamic schema inference* di pipeline produksi. Skema harus didefinisikan secara deklaratif (*explicit contract*) sebelum pembacaan file I/O dimulai. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap framework manipulasi data memiliki trade-off desain arsitektural yang berbeda:

```
                      Latency / Memory Efficiency
                                 ▲
                                 │       [Polars] (Rust, Parallel SIMD)
                                 │
                                 │   [Pandas 2.0 (PyArrow Backend)]
                                 │
     [PySpark Streaming]         │   [DuckDB] (In-Process OLAP)
     (Distributed Scale-Out)     │
                                 │       [Traditional Pandas 1.x (NumPy)]
                                 │
                                 └──────────────────────────────────────► Ecosystem Maturity /
                                                                           Legacy Compatibility
```

#### Komparasi Arsitektural Komputasi:

1. **Pandas 2.0 (PyArrow Backend) vs. Traditional Pandas 1.x:**
   - *Pros:* Kompatibel penuh dengan API warisan (`.loc`, `.iloc`, `.groupby`), eliminasi overhead konversi float pada null integer, konsumsi RAM turun 40–60%.
   - *Cons:* Masih terikat pada evaluasi eksekusi *eager* (tidak ada optimasi query global) dan keterbatasan *Global Interpreter Lock (GIL)* Python.
2. **Polars (Eager & Lazy Engine):**
   - *Pros:* Arsitektur multi-threaded berbasis Rust tanpa intervensi GIL, memory-efficient columnar format asli, evaluasi kueri lazy dengan *predicate pushdown* yang meminimalkan pembacaan disk.
   - *Cons:* API tidak kompatibel 100% dengan ekosistem Scikit-Learn/Pandas; membutuhkan layer transformasi `.to_pandas()` atau `.to_numpy()` saat integrasi ke library downstream tertentu.
3. **DuckDB vs Polars:**
   - *Pros DuckDB:* Engine OLAP in-process berbasis SQL murni yang andal untuk agregasi join berdimensi sangat besar, mendukung persistence disk file `.duckdb` langsung.
   - *Cons DuckDB:* Kurang idiomatik untuk manipulasi pipeline ekspresi data science procedural berbasis method-chaining murni dibandingkan Polars DataFrame API.

---

### 9. Best Practices & Standard Industri

1. **Zero Raw Python Types in Core Transformations:**
   Jangan pernah menggunakan iterasi berbasis baris murni Python (`for index, row in df.iterrows():`). Eksekusi tersebut 100–1000x lebih lambat. Gunakan ekspresi Arrow Compute Engine (`pc.*`) atau Polars vectorized expressions (`pl.col().*`).
2. **Deterministic Data Types Specification:**
   Selalu enforce skema byte-per-byte pada layer boundary sistem. Jangan biarkan fungsi seperti `pd.read_csv()` melakukan *type guessing*. Tentukan mapping tipe secara presisi:
   ```python
   PA_SCHEMA = pa.schema([
       pa.field("id", pa.string(), nullable=False),
       pa.field("val", pa.float64(), nullable=True),
       pa.field("ts", pa.timestamp("ms"), nullable=False),
   ])
   ```
3. **Idempotent Ingestion & Quarantine Dead-Lettering:**
   Setiap batch ingestion harus bersifat idempoten (dapat diulang tanpa menciptakan duplikasi data). Rekord yang gagal divalidasi tidak boleh langsung dilempar sebagai fatal crash yang menghentikan pipeline; rekam data rusak ke lokasi karantina khusus (*dead-letter storage*) disertai payload error detail untuk proses *root-cause analysis* tim downstream.
4. **Columnar Compaction on Rest:**
   Seluruh dataset analitis hasil pembersihan awal wajib disimpan dalam format Parquet berbasis *column chunk dictionary encoding* dan terkompresi menggunakan algoritma modern berlatensi seimbang seperti **ZSTD** atau **Snappy**, bukan CSV mentah atau bzip2.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertindak sebagai Lead Data Analyst di sebuah institusi FinTech. Diberikan streaming log transaksi mentah (`dirty_transactions.csv`) yang terkontaminasi dengan baris rusak, null-values anomali, serta string invalid. Anda ditugaskan membangun pipeline analitik terisolasi yang:
1. Membaca dan memverifikasi data sesuai skema Data Contract secara streaming.
2. Memisahkan data anomali ke sink karantina `quarantine.json`.
3. Menghitung profil statistik komprehensif (distribusi, kardinalitas, missing rate) tanpa risiko lonjakan memori OOM.
4. Menyimpan data bersih ke format Parquet terkompresi Zstandard.

#### Langkah 1: Persiapan Environment
Pastikan dependensi enterprise terinstal pada virtual environment Python 3.11+:
```bash
pip install "pyarrow>=14.0.0" "polars>=0.20.0" "pandas>=2.1.0" "pydantic>=2.5.0"
```

#### Langkah 2: Generator Dataset Anomali (Simulasi Lingkungan Produksi)
Jalankan script generator berikut untuk memproduksi payload pengujian sintetis:

```python
# test_data_generator.py
import csv
import random
from pathlib import Path

DATA_PATH = Path("./dirty_transactions.csv")


def generate_dirty_csv(file_path: Path, num_records: int = 50_000) -> None:
    statuses = ["SUCCESS", "PENDING", "FAILED", "UNKNOWN", ""]
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["transaction_id", "customer_id", "amount", "fee", "status", "timestamp"]
        )

        for i in range(num_records):
            # Injeksi data anomali probabilistik
            is_corrupt = random.random() < 0.05

            tx_id = f"tx_{i:08d}" if not is_corrupt else "short"
            cust_id = f"cust_{random.randint(100, 999)}"
            amount = (
                round(random.uniform(10.0, 5000.0), 2) if not is_corrupt else -100.0
            )
            fee = round(amount * 0.015, 2) if amount > 0 else 0.0
            status = (
                random.choice(["SUCCESS", "PENDING", "FAILED"])
                if not is_corrupt
                else "CORRUPT_STATUS"
            )
            timestamp = "2026-03-30T10:00:00Z"

            # Injeksi baris dengan missing value ekstrem
            if random.random() < 0.02:
                writer.writerow([tx_id, cust_id, "", "", status, timestamp])
            else:
                writer.writerow([tx_id, cust_id, amount, fee, status, timestamp])


if __name__ == "__main__":
    generate_dirty_csv(DATA_PATH)
    print(f"Data pengujian berhasil digenerate di: {DATA_PATH.resolve()}")
```

#### Langkah 3: Eksekusi Pipeline Ingestion dan Profiling
Integrasikan komponen dari bagian 6 ke dalam skrip driver akhir:

```python
# run_pipeline.py
import json
from pathlib import Path
import pyarrow as pa
from main_engine import (
    OnlineVectorizedProfiler,
    ProductionPipelineManager,
    StreamingArrowCSVIngestor,
)

RAW_DATA = Path("./dirty_transactions.csv")
CLEAN_OUTPUT = Path("./storage/clean_transactions.parquet")
QUARANTINE_OUTPUT = Path("./storage/quarantine_records.json")

# Definisi PyArrow Schema Contract Terstruktur
PIPELINE_SCHEMA = pa.schema(
    [
        pa.field("transaction_id", pa.string(), nullable=True),
        pa.field("customer_id", pa.string(), nullable=True),
        pa.field("amount", pa.float64(), nullable=True),
        pa.field("fee", pa.float64(), nullable=True),
        pa.field("status", pa.string(), nullable=True),
        pa.field("timestamp", pa.string(), nullable=True),
    ]
)


def run_lab():
    ingestor = StreamingArrowCSVIngestor(
        file_path=RAW_DATA,
        schema=PIPELINE_SCHEMA,
        batch_size_bytes=1024 * 1024,  # Chunk 1MB untuk simulasi streaming aktif
    )

    profiler = OnlineVectorizedProfiler(dataset_name="fintech_financial_stream")

    manager = ProductionPipelineManager(
        ingestor=ingestor,
        profiler=profiler,
        clean_sink_path=CLEAN_OUTPUT,
        quarantine_sink_path=QUARANTINE_OUTPUT,
    )

    # Eksekusi pipeline end-to-end
    summary_report = manager.execute()

    print("\n" + "=" * 60)
    print("HASIL DIAGNOSTIK EXPLORATORY DATA ANALYSIS (EDA)")
    print("=" * 60)
    print(json.dumps(summary_report.model_dump(), indent=2))


if __name__ == "__main__":
    run_lab()
```

#### Langkah 4: Verifikasi Hasil Analitik
1. Periksa direktori `./storage/` dan konfirmasi terciptanya file `clean_transactions.parquet` dan `quarantine_records.json`.
2. Validasi struktur Parquet clean menggunakan Polars untuk verifikasi zero-copy reading:
   ```python
   import polars as pl

   df_clean = pl.read_parquet("./storage/clean_transactions.parquet")
   print("Total Baris Bersih:", len(df_clean))
   print(df_clean.describe())
   ```
3. Buka file `quarantine_records.json` dan evaluasi tipe pelanggaran skema:
   - Amati bagaimana baris dengan `amount < 0.0` atau `status="CORRUPT_STATUS"` berhasil ditangkap oleh validasi Data Contract tanpa memicu crash pada komputasi statistik profiler utama.

Dengan menyelesaikan pipeline ini, Anda telah mengimplementasikan arsitektur *Exploratory Data Analysis & Ingestion Engine* enterprise yang deterministik, hemat memori, dan memenuhi standar keandalan sistem berskala besar.