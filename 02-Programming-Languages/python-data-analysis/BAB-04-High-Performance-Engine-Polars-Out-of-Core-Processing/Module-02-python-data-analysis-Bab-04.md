# Kurikulum Enterprise: Python Data Analysis
## BAB 04: High-Performance Engine: Polars & Out-of-Core Processing
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Software Engineer / Data Platform Architect diharapkan mampu:
- **Menganalisis Internal Engine Polars**: Membedah interaksi antara Apache Arrow Columnar Format, Morsel-Driven Parallelism, dan memori off-heap secara presisi pada level instruksi CPU (SIMD/AVX-512).
- **Membangun Query Optimization Pipeline**: Memanfaatkan *Predicate Pushdown*, *Projection Pushdown*, *Slice Pushdown*, dan *Common Subplan Elimination (CSE)* pada query analitik kompleks.
- **Menguasai Out-of-Core & Streaming Processing**: Menjalankan pemrosesan dataset berukuran ratusan gigabyte melampaui kapasitas RAM fisik (*out-of-core*) menggunakan Polars Streaming Engine tanpa memicu `Out-Of-Memory (OOM) Killer`.
- **Menerapkan Advanced Expressions & Window Functions**: Mengimplementasikan manipulasi data bersarang (*List* dan *Struct*), *rolling/dynamic aggregations*, serta *temporal windowing* dengan kompleksitas waktu optimal $O(N)$ tanpa beralih ke Python UDF.
- **Menata Arsitektur Produksi Skala Enterprise**: Menerapkan arsitektur analitik deterministik dengan alokator memori tingkat lanjut (`jemalloc`/`mimalloc`), isolasi resource CPU via Cgroups pada container Kubernetes, dan partisi *Data Lakehouse* (Delta/Parquet).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
1. **Dasar Polars & Pandas**: Memahami perbedaan API dasar `polars.DataFrame` vs `pandas.DataFrame`.
2. **Arsitektur Komputer & Memori**: Memahami konsep *L1/L2/L3 Cache Locality*, alokasi memori stack vs heap, *Memory Alignment*, dan *Virtual Memory Paging*.
3. **Format Data Kolumnar**: Struktur dasar Apache Parquet (Metadata, Row Groups, Page Layout, Dictionary Encoding, Snappy/ZSTD compression).
4. **Konkurensi & Paralelisme**: Perbedaan antara Multithreading berbasis OS, Green Threads, Thread Pool, dan batasan Python GIL (*Global Interpreter Lock*).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Fondasi Memori: Apache Arrow In-Memory Layout
Polars tidak menggunakan representasi array objek pointer bergaya Python standar atau blok NumPy contiguous 2D yang kaku. Polars dibangun di atas implementasi native Rust dari spesifikasi **Apache Arrow**.

```
Array Representasi Kolom Int64: [12, NULL, 42, 99]

1. Validity Bitmap Buffer (1 bit per nilai):
   Bit Index:  0  1  2  3
   Bit Value:  1  0  1  1  -> 0b1101 (Hex: 0x0D) -> Ukuran: ceil(N/8) bytes

2. Value Buffer (64-bit / 8-byte aligned contiguous memory):
   Offset:  0x00       0x08       0x10       0x18
   Bytes:   [12, 0..]  [??, ??]   [42, 0..]  [99, 0..]  (Nilai index 1 diabaikan via bitmap)
```

- **Bitmaps Validity**: Nilai `null` tidak direpresentasikan oleh sentinel values (`NaN` atau pointer `None`) melainkan oleh bitmap bit terisolasi. Hal ini menghemat penggunaan cache data pada core CPU dan memungkinkan eksekusi instruksi branching yang minimal.
- **Zero-Copy Slicing**: Operasi *slice* array hanya membuat instance baru dari pointer metadata buffer (`offset`, `length`) tanpa menyalin buffer byte underlying di heap.
- **Chunked Arrays**: Setiap Series dalam Polars direpresentasikan oleh `ChunkedArray<T>`. Jika dua array digabungkan (concatenated), Polars tidak perlu mengalokasikan contiguous buffer baru; Polars cukup menyimpan referensi array potongan (*chunks*) tersebut.

#### B. Query Engine: Morsel-Driven Parallelism
Polars mengabaikan model pemrosesan thread-per-task tradisional dan menerapkan model **Morsel-Driven Engine** (terinspirasi dari Hyper Database System):

```
                   [Logical/Physical Plan]
                             |
                   [Morsel Scheduler]
         /                   |                   \
[Core 0: Task]        [Core 1: Task]        [Core 2: Task]
  Morsel 0..64K         Morsel 64K..128K      Morsel 128K..192K
         \                   |                   /
          --- Work Stealing Dispatcher Engine ---
```

- **Morsel**: Kumpulan record data berukuran relatif kecil (biasanya $64\text{K} - 128\text{K}$ baris) yang dirancang agar muat dalam L2/L3 cache core CPU.
- **Work-Stealing Scheduler**: Setiap thread hardware OS dikaitkan dengan satu worker. Jika worker pada Core 0 menyelesaikan morsel-nya lebih cepat karena data sparse/terfilter, worker tersebut akan mencuri (*steal*) morsel berikutnya dari antrean global tanpa menunggu thread lain selesai (*no pipeline barrier*).

#### C. Lifecycle Query: LazyFrame Compiler & Optimizer
Siklus hidup evaluasi pada Polars Lazy Engine:

```
[DSL: pl.scan_parquet() -> .filter() -> .select()]
                        |
            [Abstract Syntax Tree (AST)]
                        |
            [Unoptimized Logical Plan]
                        |
        === Optimization Passes (Rust AST Rewriter) ===
        1. Predicate Pushdown (Scan Level Filter)
        2. Projection Pushdown (Column Pruning)
        3. Slice Pushdown (Early LIMIT injection)
        4. Common Subplan Elimination (CSE)
        5. Simplify Expressions & Constant Folding
                        |
             [Optimized Logical Plan]
                        |
         [Physical Plan Compiler (Morsel/Streaming)]
                        |
         [Parallel Pipeline Execution on Hardware]
```

- **Predicate Pushdown**: Mendorong predikat seleksi (contoh: `.filter(pl.col("timestamp") >= t0)`) sedalam mungkin hingga ke tingkat pembacaan storage engine (Parquet Row Group Statistics: `min`/`max`). Data yang tidak relevan dilewati tanpa dibaca dari disk ke RAM.
- **Projection Pushdown**: Menghilangkan pembacaan kolom yang tidak digunakan dalam aggregasi atau output akhir. Kolom tidak dibaca secara parsial dari disk, menghemat I/O throughput.

---

### 4. Why & What

| Fitur / Parameter | Python Pandas | Apache Spark (Single Node) | DuckDB | Polars |
| :--- | :--- | :--- | :--- | :--- |
| **Bahasa Engine** | C / Python | Scala / Java (JVM) | C++ | Rust |
| **Model Memori** | NumPy pointer arrays | JVM Objects / Tungsten | Arrow Columnar | Native Apache Arrow |
| **GIL Dependency** | Terikat GIL secara ketat | Terisolasi via Worker JVM | Bebas GIL | 100% Bebas GIL di level Engine |
| **Paralelisasi** | Single-threaded (default) | Multi-threaded via stage partitions | Vectorized Morsel-Driven | Vectorized Morsel-Driven |
| **Out-of-Core Execution** | Tidak Didukung (Crash OOM) | Didukung (Spill-to-disk via partitions) | Didukung secara native | Didukung via Streaming Sink/Engine |
| **Cache Locality** | Rendah (Pointer chasing) | Moderat (Tungsten Off-heap) | Sangat Tinggi (SIMD) | Sangat Tinggi (SIMD + Rust Safety) |

#### Alasan Menggunakan Polars di Enterprise:
1. **CPU & RAM Efficiency**: Menghilangkan *garbage collection pause* JVM dan memory footprint berlebihan (2-10x lebih hemat dibanding PySpark lokal).
2. **Deterministic Scaling**: Transisi mulus dari komputasi memori (*in-core*) ke komputasi berbasis streaming disk (*out-of-core*) hanya dengan mengganti parameter `.collect()` ke `.collect(streaming=True)` atau menggunakan `.sink_parquet()`.
3. **Expression Purity**: Tidak mengizinkan modifikasi data inplace yang *mutable*, mencegah kondisi *race condition* dan *hidden side effects* pada distributed pipeline.

---

### 5. How (Workflow Detail)

Alur kerja implementasi pemrosesan dataset besar berbasis Polars:

```
[Sumber Data: Parquet Lakehouse / S3 Object Storage]
                        │
                        ▼
   1. Inisiasi Scan Lazy (`pl.scan_parquet`)
      - Jangan pernah gunakan `read_parquet` untuk data > RAM
                        │
                        ▼
   2. Konstruksi Query Expressions (Lazy DSL)
      - Join, Windowing, Aggregation menggunakan native expressions
                        │
                        ▼
   3. Analisis Query Plan (`print(q.explain())`)
      - Validasi apakah Predicate & Projection Pushdown aktif
                        │
                        ▼
   4. Tentukan Mode Eksekusi Berdasarkan Skala Data:
      ├── Ukuran Data < 60% RAM: `df = q.collect()`
      └── Ukuran Data > RAM: `q.sink_parquet()` ATAU `q.collect(streaming=True)`
                        │
                        ▼
   5. Sinkronisasi Output ke Format Terstruktur
      - Partisi dinamis berbasis Hive-Partitioning
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Modern vs Perpustakaan Kuno
- **Pandas (Perpustakaan Kuno)**: Meminta 1 lembar informasi dari sebuah ensiklopedia mewajibkan pustakawan membawa *seluruh* 100 volume buku ensiklopedia ke meja pengunjung, menyita seluruh ruang meja (RAM Habis/OOM).
- **Polars Lazy Engine (Perpustakaan Modern Berotomasi Penuh)**: Anda menulis formulir permintaan: *"Tolong ambilkan rata-rata nilai dari Kolom A di Bab 5"*. Operator melihat catatan indeks (*metadata pushdown*), hanya mengambil rak lemari nomor 5, memindai halaman tersebut menggunakan scanner multi-lensa berkecepatan tinggi (*vectorized SIMD*), lalu hanya mengirimkan selembar angka akhir ke meja Anda.

#### Diagram: Perbandingan Pola Memori di Hardware Cache

```
Pandas DataFrame (Memori Terfragmentasi, Pointer Chasing):
[Series Pointer] 
      │
      ├──> [Ptr 0] ──> [Python Int Object (28 Bytes)] (Cache Line Miss!)
      ├──> [Ptr 1] ──> [Python Int Object (28 Bytes)] (Cache Line Miss!)
      └──> [Ptr 2] ──> [Python Int Object (28 Bytes)]

Polars Arrow Array (Contiguous, 64-Byte Aligned, SIMD Ready):
[Cache Line: 64 Bytes] = [Int64][Int64][Int64][Int64][Int64][Int64][Int64][Int64]
 └─────────────────────── 1 Siklus Baca CPU (Semua Data Siap Masuk Register SIMD) ─┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Performa Native Expression vs Python UDF
File: `benchmark_udf_vs_expr.py`

```python
import time
import polars as pl

# Inisialisasi dataset sintetis: 10 Juta Baris
n_rows = 10_000_000
df = pl.DataFrame({
    "id": range(n_rows),
    "val_a": [i * 1.5 for i in range(n_rows)],
    "val_b": [i * 2.5 for i in range(n_rows)],
})

# Pendekatan 1: Anti-pattern Python UDF (Memicu context switch Rust -> Python GIL)
start_time = time.perf_counter()
res_udf = df.select([
    pl.struct(["val_a", "val_b"]).map_elements(
        lambda cols: cols["val_a"] + cols["val_b"],
        return_dtype=pl.Float64
    ).alias("total")
])
udf_duration = time.perf_counter() - start_time
print(f"[Anti-Pattern] UDF Map Elements Duration: {udf_duration:.4f} detik")

# Pendekatan 2: Polars Native Vectorized Expression (C-Speed / SIMD)
start_time = time.perf_counter()
res_native = df.select([
    (pl.col("val_a") + pl.col("val_b")).alias("total")
])
native_duration = time.perf_counter() - start_time
print(f"[Best Practice] Native Expression Duration: {native_duration:.4f} detik")
print(f"Percepatan: {udf_duration / native_duration:.2f}x lipat lebih cepat.")
```

#### B. Practical Example: Streaming Out-of-Core Aggregation dengan Windowing
File: `enterprise_telemetry_pipeline.py`

```python
import polars as pl
from pathlib import Path
import tempfile

def create_mock_parquet_data(base_path: Path, num_files: int = 5):
    """Membuat beberapa file parquet untuk simulasi telemetry out-of-core."""
    base_path.mkdir(parents=True, exist_ok=True)
    rows_per_file = 1_000_000
    for i in range(num_files):
        df = pl.DataFrame({
            "device_id": [f"sensor-{(j % 500):04d}" for j in range(rows_per_file)],
            "timestamp": pl.datetime_range(
                start=pl.datetime(2026, 1, 1),
                end=pl.datetime(2026, 1, 10),
                interval="1s",
                eager=True
            ).slice(i * rows_per_file, rows_per_file),
            "cpu_utilization": [(j % 100) * 1.05 for j in range(rows_per_file)],
            "memory_pressure": [(j % 10) * 0.1 for j in range(rows_per_file)]
        })
        df.write_parquet(base_path / f"telemetry_part_{i}.parquet")
    print(f"Berhasil menghasilkan {num_files} partisi Parquet di: {base_path}")

def execute_streaming_pipeline(input_dir: Path, output_file: Path):
    """
    Mengeksekusi pipeline query analitik kompleks secara out-of-core (Streaming).
    Menggabungkan multi-file parquet, projection, dynamic filtering,
    rolling aggregations, dan langsung sinkronisasi ke Parquet tujuan.
    """
    # 1. Scanning Lazy
    lazy_plan = pl.scan_parquet(input_dir / "*.parquet")

    # 2. Pipeline Transformasi
    processed_plan = (
        lazy_plan
        # Predicate pushdown awal
        .filter(pl.col("cpu_utilization") > 15.0)
        # Sort untuk rolling dynamic windowing
        .sort(["device_id", "timestamp"])
        # Window & Grouping computation
        .group_by_dynamic(
            "timestamp",
            every="1h",
            period="2h",
            by="device_id"
        )
        .agg([
            pl.col("cpu_utilization").mean().alias("avg_cpu_2h"),
            pl.col("cpu_utilization").max().alias("peak_cpu_2h"),
            pl.col("memory_pressure").quantile(0.95).alias("p95_mem_pressure"),
            pl.len().alias("sample_count")
        ])
        # Filtering pasca agregasi
        .filter(pl.col("peak_cpu_2h") >= 80.0)
    )

    # 3. Print Execution Plan
    print("\n=== Optimized Logical Plan ===")
    print(processed_plan.explain(optimized=True))

    # 4. Out-of-Core Execution via sink_parquet (RAM konstan)
    print(f"\nMengeksekusi Streaming Sink langsung ke: {output_file} ...")
    processed_plan.sink_parquet(
        output_file,
        compression="zstd",
        compression_level=6,
        maintain_order=False
    )
    print("Pemrosesan Streaming Selesai Tanpa Melebihi Batas RAM.")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        source_data_dir = tmp_path / "telemetry_lake"
        sink_target_file = tmp_path / "aggregated_telemetry.parquet"

        create_mock_parquet_data(source_data_dir, num_files=4)
        execute_streaming_pipeline(source_data_dir, sink_target_file)
        
        # Validasi output
        result_df = pl.read_parquet(sink_target_file)
        print(f"Hasil Eksekusi: {result_df.shape[0]} baris aggregasi dihasilkan.")
        print(result_df.head(5))
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Deteksi Fraud FinTech Real-Time Batch Ingestion
- **Konteks**: Sebuah payment gateway memproses 150 juta data transaksi per hari (~120 GB raw JSON/CSV format). Sistem lama menggunakan pipeline PySpark single-cluster yang membutuhkan waktu 4.5 jam dan biaya cloud compute AWS EC2 m5.4xlarge ($0.768/jam x multi-nodes).
- **Bottleneck**: Biaya operasional tinggi, latency pengenalan fraud terlambat masuk ke Feature Store, serta error OOM sporadis saat JVM Garbage Collector gagal melepaskan memori pada saat join data berukuran tidak seragam (*data skew*).
- **Solusi Polars Out-of-Core**:
  1. Pipeline diubah sepenuhnya menggunakan Polars Rust-backed Engine.
  2. Data mentah di-*stream* langsung dari bucket Object Storage S3 menggunakan `scan_parquet` dengan batasan memori OS (`jemalloc`).
  3. Menggunakan operasi *As-Of Join* (`join_asof`) untuk memadankan timestamp transaksi dengan pergerakan limit saldo kartu kredit pengguna secara efisien tanpa *full cartesian product cross-join*.
  4. Agregasi statistik fitur (Z-Score frekuensi transaksi dalam 10 menit terakhir) menggunakan fungsi `pl.col().rolling_mean()`.

```python
# Cuplikan Implementasi Arsitektur Feature Extraction
import polars as pl

def build_fraud_features(transactions_path: str, ledger_path: str, output_path: str):
    tx_plan = pl.scan_parquet(transactions_path)
    ledger_plan = pl.scan_parquet(ledger_path)

    # Menyiapkan data join temporal (As-Of Join)
    # Mencari status saldo terakhir sebelum atau bertepatan dengan waktu transaksi
    enriched_tx = tx_plan.sort("timestamp").join_asof(
        ledger_plan.sort("timestamp"),
        on="timestamp",
        by="account_id",
        strategy="backward"
    )

    feature_plan = (
        enriched_tx
        .with_columns([
            # Menghitung rasio transaksi terhadap saldo saat itu
            (pl.col("amount") / (pl.col("available_balance") + 1.0)).alias("spend_to_balance_ratio")
        ])
        .group_by("account_id")
        .agg([
            pl.col("amount").count().alias("tx_count_total"),
            pl.col("amount").sum().alias("tx_sum_total"),
            (pl.col("spend_to_balance_ratio") > 0.8).sum().alias("critical_spend_count")
        ])
        .filter(pl.col("critical_spend_count") > 3)
    )

    # Streaming write langsung ke Lakehouse storage
    feature_plan.sink_parquet(output_path, compression="zstd")
```
- **Dampak Arsitektur**:
  - Waktu eksekusi turun dari 4.5 jam menjadi **18 menit** pada 1 instance mesin bare-metal/EC2 c6i.4xlarge (16 vCPU, 32 GB RAM).
  - Penghematan biaya komputasi cloud sebesar **78%**.
  - OOM lenyap secara definitif karena alokasi memori dipatok pada streaming buffer berukuran $256\text{ MB}$.

---

### 9. Trade-offs

| Parameter | Pendekatan Eager (`pl.DataFrame`) | Pendekatan Streaming (`pl.LazyFrame.collect(streaming=True)`) | Native Disk Sink (`pl.LazyFrame.sink_parquet()`) |
| :--- | :--- | :--- | :--- |
| **Throughput Kecepatan** | Tertinggi (Semua data di RAM) | Tinggi (Ada sedikit overhead batch dispatching) | Moderat hingga Tinggi (Tergantung I/O disk) |
| **Konsumsi RAM** | Sangat Tinggi ($O(N)$ data size) | Terkendali ($O(K)$ ukuran morsel batch) | Paling Rendah (Buffer terbatas pada page Parquet) |
| **Dukungan Operator** | 100% Fungsi Polars | Sebagian besar (Filter, Project, GroupBy, Join) | Terbatas pada alur tanpa backward-looping global sort |
| **Kebutuhan Disk I/O** | Tidak Ada (RAM-only) | Spill-to-disk jika morsel melebihi buffer | Kontinu menulis ke persistent storage |
| **Resiko Crash OOM** | Sangat Rentan jika Data > RAM | Sangat Rendah | Nol (Determinasi I/O murni) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Memanggil `.to_pandas()` atau `.to_numpy()` Terlalu Dini
- **Gejala**: Penggunaan memori melonjak 3x lipat secara tiba-tiba dan pipeline terhenti (*freezing*).
- **Penyebab**: Konversi Arrow memory layout ke format pointer Pandas memicu duplikasi data di user space dan inisialisasi jutaan objek Python wrapper.
- **Solusi**: Pertahankan data dalam bentuk Polars `LazyFrame` atau `DataFrame`. Bila terpaksa berinteraksi dengan Scikit-Learn/PyTorch, gunakan integrasi Zero-Copy Tensor atau ekspor ke Apache Arrow Table (`df.to_arrow()`).

#### 2. Thread-Thrashing pada Lingkungan Container (Kubernetes/Docker)
- **Gejala**: CPU usage 100% pada semua core host server, performa aplikasi menurun drastis (*high context switching*).
- **Penyebab**: Secara default, Polars membaca total core hardware host fisik, bukan batasan *CPU Quota* Cgroups Kubernetes container.
- **Solusi**: Atur environment variable secara eksplisit di entrypoint container:
  ```bash
  export POLARS_MAX_THREADS=4
  ```

#### 3. Ketidaksengajaan Membawa Query ke Execution Mode Eager
- **Gejala**: Error `polars.exceptions.ComputeError: out of memory` saat membaca puluhan file Parquet.
- **Penyebab**: Menggunakan fungsi:
  ```python
  # SALAH
  dfs = [pl.read_parquet(f) for f in files]
  df = pl.concat(dfs)
  ```
- **Solusi**: Gunakan lazy wildcard scanning:
  ```python
  # BENAR
  df = pl.scan_parquet("data/*.parquet").collect(streaming=True)
  ```

#### 4. Memory Allocator Leakage pada Linux Kernel
- **Gejala**: Memori tidak segera dikembalikan ke sistem operasi setelah `.collect()` selesai dieksekusi.
- **Penyebab**: Standard C library allocator (`glibc malloc`) lambat melepaskan fragmented virtual memory kembali ke OS kernel.
- **Solusi**: Pasang alokator memori tingkat lanjut seperti **jemalloc** atau **mimalloc** dalam environment sistem:
  ```bash
  export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so
  ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Selalu Gunakan Scan**: Gantikan seluruh pemanggilan `read_csv`, `read_parquet`, `read_ipc` dengan `scan_*` untuk memanfaatkan optimizer AST.
- [ ] **Hindari Lambda & UDF**: Ganti seluruh Python UDF dengan native Polars DSL (`pl.when().then().otherwise()`, `pl.col().str.*`, `pl.col().list.*`).
- [ ] **Batasi Jumlah Thread di Microservices**: Jika Polars dijalankan di belakang web server (FastAPI/Gunicorn), tetapkan `POLARS_MAX_THREADS=1` atau `2` untuk mencegah kehabisan thread pool (*thread starvation*).
- [ ] **Row Group Parquet Sizing**: Saat menulis file Parquet tujuan, pastikan ukuran row group berada pada rentang $64\text{MB}$ hingga $128\text{MB}$ (jangan menulis per 1000 baris) agar pembacaan vektor berikutnya efisien.
- [ ] **Explicit Schema Definition**: Selalu deklarasikan skema data (`schema={...}`) saat memindai CSV mentah untuk menghindari dua kali pembacaan file (*type-inference scan pass*).
- [ ] **Gunakan Parquet Statistics**: Jangan pernah menonaktifkan fitur statistik Parquet saat menyimpan data di storage lakehouse.

---

### 12. Hands-on Practice

Ikuti instruksi praktikum bertahap ini. Simpan seluruh file di direktori: `hands-on/m02/`.

#### Langkah 1: Persiapan Environment
```bash
mkdir -p hands-on/m02/data
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install polars pyarrow memory-profiler
```

#### Langkah 2: Pembuatan Skrip Generator Dataset Transaksi Skala Besar
Simpan sebagai `hands-on/m02/01_generate_raw_data.py`:

```python
import polars as pl
import numpy as np
from datetime import datetime, timedelta

def generate_partition(file_idx: int, rows: int = 2_000_000):
    print(f"Membuat Partisi {file_idx}...")
    np.random.seed(file_idx)
    base_time = datetime(2026, 1, 1) + timedelta(days=file_idx)
    
    df = pl.DataFrame({
        "tx_id": [f"TX-{file_idx}-{k:08d}" for k in range(rows)],
        "user_id": np.random.randint(1_000, 50_000, size=rows),
        "amount": np.random.exponential(scale=50.0, size=rows).round(2),
        "payment_method": np.random.choice(["QRIS", "CREDIT_CARD", "VA", "E_WALLET"], size=rows),
        "timestamp": [base_time + timedelta(seconds=int(s)) for s in np.random.randint(0, 86400, size=rows)]
    })
    
    df.write_parquet(f"data/transactions_part_{file_idx}.parquet")
    print(f"Selesai menulis partisi data/transactions_part_{file_idx}.parquet")

if __name__ == "__main__":
    for p in range(3): # Menghasilkan total 6 juta baris data
        generate_partition(p)
```

#### Langkah 3: Eksekusi Advanced Pipeline & Memory Profiling
Simpan sebagai `hands-on/m02/02_production_pipeline.py`:

```python
import polars as pl
import os

def run_analytics_pipeline():
    # Set limit threads secara terkendali
    os.environ["POLARS_MAX_THREADS"] = "4"
    
    input_pattern = "data/transactions_part_*.parquet"
    output_sink = "data/final_user_daily_summary.parquet"
    
    print("Mempersiapkan Lazy Query Plan...")
    query = (
        pl.scan_parquet(input_pattern)
        # 1. Filter transaksi valid
        .filter(pl.col("amount") > 5.0)
        # 2. Ekstraksi tanggal
        .with_columns(pl.col("timestamp").dt.date().alias("tx_date"))
        # 3. Aggregasi Analitik
        .group_by(["tx_date", "user_id"])
        .agg([
            pl.len().alias("daily_tx_volume"),
            pl.col("amount").sum().alias("daily_total_spend"),
            pl.col("amount").mean().alias("daily_avg_spend"),
            pl.col("payment_method").filter(pl.col("payment_method") == "CREDIT_CARD").count().alias("cc_tx_count")
        ])
        # 4. Filter pengguna bervolume tinggi
        .filter(pl.col("daily_tx_volume") >= 5)
        .sort(["daily_total_spend"], descending=True)
    )
    
    print("\nExecuting Streaming Engine...")
    # Menjalankan pemrosesan streaming tanpa menahan keseluruhan data di memori
    query.sink_parquet(output_sink, compression="snappy")
    print(f"Data pipeline berhasil diselesaikan secara efisien ke {output_sink}")

if __name__ == "__main__":
    run_analytics_pipeline()
    # Tampilkan 5 data teratas hasil komputasi
    print(pl.read_parquet("data/final_user_daily_summary.parquet").head(5))
```

Jalankan perintah pengujian:
```bash
python 01_generate_raw_data.py
python 02_production_pipeline.py
```

---

### 13. Exercise

#### Level Easy
Tulis skrip Polars Lazy yang memindai file `data/transactions_part_0.parquet`, lalu hitung jumlah frekuensi transaksi per `payment_method` dengan menyaring transaksi yang nilainya di bawah `$10.0`. Validasi plan optimizer menggunakan `.explain()` untuk membuktikan bahwa filter pushdown aktif.

#### Level Medium
Buat pipeline yang menghitung selisih waktu antar transaksi berturut-turut untuk setiap `user_id`.
- Gunakan window expression: `pl.col("timestamp").diff().over("user_id")`.
- Ambil nilai median durasi jeda antar transaksi per user dan simpan hasilnya hanya untuk user yang memiliki rata-rata jeda waktu di bawah 120 detik. Seluruh kalkulasi harus dilakukan via satu rantai *Lazy Plan*.

#### Level Hard
Rancang arsitektur sinkronisasi data *out-of-core*:
- Terdapat dua stream data: Transaksi (`tx_id`, `user_id`, `amount`, `timestamp`) dan Log Interaksi Web (`session_id`, `user_id`, `ip_address`, `timestamp`).
- Lakukan `join_asof` untuk memadankan setiap transaksi dengan IP Address terakhir yang digunakan user dari data Web Log dalam rentang waktu toleransi maksimal 15 menit ke belakang.
- Tulis hasilnya secara streaming ke disk yang terpartisi secara fisik berdasarkan format direktori: `output/tx_date=YYYY-MM-DD/data.parquet` tanpa memicu pemuatan seluruh data gabungan ke RAM.

---

### 14. Challenge

**Studi Kasus Ekstrem: High-Frequency Market Order Book Reconstructor**
- **Kondisi**: Anda diberikan file parquet berukuran 80 GB yang berisi raw tick-level event: `[timestamp_ns, symbol, event_type (BID/ASK/CANCEL/TRADE), price, quantity]`.
- **Target Masalah**: Anda hanya diberikan single container dengan resource constraint RAM sebesar **4 GB** dan batas virtual swap disk dinonaktifkan (`swap=0`).
- **Spesifikasi Tantangan**:
  1. Hitung *Volume-Weighted Average Price (VWAP)* untuk interval per 1 detik dan per 1 menit untuk setiap ticker saham.
  2. Identifikasi adanya anomali *Spoofing Order*: Pola pembatalan order (CANCEL) bernilai volume $\ge 10.000$ unit yang terjadi dalam rentang waktu $\le 5\text{ milidetik}$ setelah pemesanan dilakukan (BID/ASK).
  3. Format data hasil akhir harus ditulis langsung ke storage output dengan partisi `symbol` tanpa pernah memicu `SIGKILL (Exit Code 137 / Out of Memory)`.
  4. Seluruh logika dilarang menggunakan loops `for row in df.iter_rows()` dan dilarang menggunakan registrasi modul Python eksternal selain native Polars expressions.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Konseptual (Basic)
1. Mengapa alokasi memori Polars (Apache Arrow) jauh lebih efisien dibanding Pandas yang berbasis NumPy array of pointers saat memproses string?
2. Apa tujuan utama dari tahapan *Projection Pushdown* pada Polars LazyFrame?
3. Sebutkan perbedaan mekanis antara pemanggilan `.collect()` dan `.sink_parquet()` pada LazyFrame!
4. Mengapa operasi modifikasi inplace (seperti `df['a'] = df['a'] + 1` ala Pandas) ditiadakan dalam desain arsitektur Polars?
5. Apa kegunaan bitmap validity pada skema memori Apache Arrow?

#### B. Pertanyaan Analisis & Logika (Intermediate)
6. Jelaskan bagaimana *Morsel-Driven Parallelism* menghindari fenomena *straggler thread* (kondisi di mana satu thread tertinggal menyelesaikan task berat sementara thread lain menganggur)!
7. Kapan evaluasi ekspresi `.filter()` Polars **gagal** didorong (*pushdown*) ke level pembacaan storage Parquet?
8. Bagaimana Polars mengeksekusi operasi `join_asof` tanpa harus melakukan komputasi full cross-product Cartesian join?
9. Apa dampak teknis terhadap OS Page Cache dan Kernel jika Anda menjalankan Polars pada Kubernetes Pod tanpa mendefinisikan environment variable `POLARS_MAX_THREADS`?
10. Mengapa ekspresi Polars `pl.col("a").shift(1).over("group")` jauh lebih cepat dibanding `df.groupby("group")["a"].shift(1)` pada Pandas?

#### C. Skenario Kasus Produksi (Enterprise Architecture)
11. **Skenario 1**: Sebuah microservice berbasis FastAPI menggunakan Polars untuk menyajikan analitik real-time. Pada saat load testing dengan 200 concurrent request per detik, CPU host mencapai 100% dan latency request merosot dari 20ms menjadi 4.5 detik, meskipun ukuran data per request hanya 10.000 baris. Diagnosis akar masalah arsitektur tersebut dan berikan solusi konfigurasinya!
12. **Skenario 2**: Pipeline ETL Polars Anda memproses file Parquet mentah 150 GB menggunakan flag `streaming=True`. Namun proses tetap terkena status OOM Killer (`Killed: 9`) saat masuk ke tahap `.group_by("long_tail_identifier").agg(...)`. Mengapa hal ini bisa terjadi meskipun streaming engine aktif, dan bagaimana mitigasinya?
13. **Skenario 3**: Tim data ingin menggabungkan pipeline analitik Polars dengan algoritma Machine Learning Scikit-Learn. Jelaskan arsitektur bridging data yang paling efisien tanpa menduplikasi data di heap memory (Zero-Copy) dan hindari degradasi performa!

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian A (Basic)
1. **Penyimpanan String Arrow vs Pandas**: Pandas menyimpan string sebagai array pointer Python Object di mana setiap entri mengarah ke alokasi memori heap terpisah (28+ bytes overhead per string + pointer). Arrow menyimpan seluruh karakter string dalam satu buffer byte berkelanjutan (*contiguous buffer*) tunggal dengan buffer integer terpisah yang menyimpan nilai *offset*. Hal ini meningkatkan cache locality secara drastis dan meniadakan pointer overhead.
2. **Projection Pushdown**: Membaca hanya kolom data yang benar-benar diminta dalam tahapan akhir query dari media penyimpanan (misal Parquet), dan mengabaikan pembacaan kolom lain sejak level disk I/O.
3. **Collect vs Sink**: `.collect()` menarik seluruh hasil komputasi ke dalam bentuk `DataFrame` di RAM fisik. `.sink_parquet()` menyalurkan hasil evaluasi pipeline secara streaming blok demi blok langsung ke media penyimpanan disk tanpa pernah memuat keseluruhan dataset di memori secara simultan.
4. **Alasan Peniadaan Inplace Mutation**: Immutable design menjamin *thread safety* mutlak, mencegah kondisi *race-condition* saat query dieksekusi secara paralel di berbagai core CPU via work-stealing scheduler, serta memungkinkan optimasi compiler AST yang bebas dari *side effects*.
5. **Kegunaan Bitmap Validity**: Bitmap menyimpan status eksistensi nilai data (apakah bernilai valid atau NULL) dalam skala representasi 1 bit per baris data, sehingga CPU dapat memeriksa status nullability data secara cepat tanpa sentinel value checking dan hemat ruang memori.

#### Bagian B (Intermediate)
6. **Morsel-driven & Stragglers**: Menggunakan sistem antrean morsel dinamis (chunk 64k-128k baris) dengan teknik *work-stealing*. Jika Core 1 memproses chunk yang lebih cepat (misal banyak data terfilter), ia segera mengambil (*steals*) morsel data baru berikutnya dari antrean global, alih-alih terdiam menunggu Core 2 yang sedang memproses data padat.
7. **Kegagalan Filter Pushdown**: Terjadi jika predikat filter bergantung pada hasil komputasi dinamis pasca-agregasi (misal: `.filter(pl.col("val") > pl.col("val").mean())`), ekspresi nondeterministik/Python UDF, atau jika format data sumber tidak memiliki metadata min/max statistics (misal membaca unindexed raw text CSV).
8. **Mekanisme As-Of Join**: Mengasumsikan kedua dataset telah terurut (*ordered*) berdasarkan kolom kunci temporal. Polars menggunakan algoritma *two-pointer linear scan* $O(N + M)$ untuk mencocokkan record terdekat, tanpa membangun tabel hash raksasa atau nested loop cartesian product.
9. **Dampak Tanpa Konfigurasi Thread Pod**: Polars mendeteksi total logical CPU host mesin fisik (misal 64 vCPU) bukan batas kuota container (misal Pod di-limit 4 CPU). Akibatnya, Polars membuat 64 OS threads yang berebut kuota CPU terbatas, memicu *CPU throttling*, *thrashing*, dan ribuan *context switches* per detik yang merusak throughput aplikasi.
10. **Window Expression Over vs GroupBy Pandas**: Pandas memecah dataframe ke dalam ratusan objek dictionary terpisah, mengiterasi per grup menggunakan Python interpreter, lalu menggabungkannya kembali (Split-Apply-Combine overhead). Polars menggunakan operasi *sorting-index partitioning* native Rust dengan alokasi buffer output tunggal yang telah ditentukan ukurannya di awal, dieksekusi secara paralel tanpa Python context-switching.

#### Bagian C (Kasus Produksi)
11. **Analisis Masalah Web Service**: Setiap request memicu Polars untuk membuat Thread Pool baru yang mencoba memanfaatkan seluruh core CPU server secara paralel. Dengan 200 concurrent request, terjadi *thread oversubscription* (ratusan/ribuan thread aktif saling berebut resource CPU host). **Solusi**: Setel `export POLARS_MAX_THREADS=1` atau `2` pada environment container Gunicorn/FastAPI agar setiap request hanya menggunakan single thread, sehingga konkurensi ditangani oleh worker pool web server.
12. **Analisis Streaming OOM GroupBy**: Kolom `long_tail_identifier` memiliki kardinalitas unik yang sangat masif (*high-cardinality aggregation*). Streaming Engine Polars tetap harus memelihara hash state table di memori untuk setiap kunci unik agregasi. Jika jumlah kunci unik mencapai puluhan juta, hash table tersebut meluap dan menghabiskan sisa RAM. **Solusi**: Lakukan pre-sorting pada data berdasarkan kolom identifier tersebut dan gunakan algoritma sinkronisasi berbasis partisi atau perbesar alokasi swap spill-to-disk buffer.
13. **Solusi Zero-Copy Polars ke ML**: Jangan pernah mengonversi ke Pandas DataFrame atau me-looping baris. Konversi Polars DataFrame langsung ke Apache Arrow Table (`df.to_arrow()`), lalu gunakan antarmuka native buffer Scikit-Learn/PyTorch (seperti format C-Contiguous NumPy array via PyArrow Buffer pointer) atau manfaatkan fitur zero-copy Tensor construction: `torch.from_numpy(df[col].to_numpy())` (pada data numerik tanpa null) yang langsung membaca pointer memory address yang dialokasikan oleh Rust engine Polars.

---

### 16. Summary

```
                      ARUS EVALUASI EFISIEN POLARS
                      
    Raw Storage (Parquet / Object Store S3)
                       │
             [Predicate Pushdown] ── (Eliminasi Row Group via Metadata)
                       │
             [Projection Pushdown] ── (Hanya membaca kolom relevan)
                       │
            Morsel Engine Execution ── (SIMD / Multi-threaded Work-stealing)
                       │
      ┌────────────────┴────────────────┐
      ▼                                 ▼
In-Core Processing              Out-of-Core Processing
(Data < RAM)                     (Data > RAM)
.collect()                       .collect(streaming=True) ATAU .sink_parquet()
```

- Polars mentransformasi paradigma komputasi data single-node melalui kombinasi **Rust Safety**, **Spesifikasi Kolumnar Apache Arrow**, dan arsitektur eksekusi **Morsel-Driven Parallelism**.
- Optimalisasi performa Polars yang sesungguhnya hanya tercapai dengan mengadopsi pola pikir **Lazy-First**: menunda eksekusi sedekat mungkin ke tahap akhir dan membiarkan query compiler Polars melakukan penataan ulang AST (*Abstract Syntax Tree*).
- Menghindari Python UDF dan mempercayakan manipulasi logika pada Polars Native Expressions merupakan pembeda krusial antara pipeline data performa tinggi tingkat enterprise dengan pipeline yang mengalami kegagalan skalabilitas (*bottlenecking*).