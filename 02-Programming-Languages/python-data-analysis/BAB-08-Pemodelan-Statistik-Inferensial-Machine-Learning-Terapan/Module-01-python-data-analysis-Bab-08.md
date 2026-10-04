# Bab 08 Modul 01: High-Performance Data Processing: Polars LazyFrame Architecture, Apache Arrow Memory Layout, dan Out-of-Core Pipeline

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer mampu:
*   Menganalisis dan mengidentifikasi limitasi memori (*RAM ceiling*) serta inefisiensi *single-threaded eager execution* pada Pandas tradisional.
*   Merancang dan mengimplementasikan pipeline analitik berbasis Apache Arrow Columnar Memory Layout dan zero-copy data sharing.
*   Membangun pipeline transformasi data berskala multi-gigabyte menggunakan Polars `LazyFrame`, memanfaatkan *Query Optimizer* (*predicate & projection pushdown*).
*   Mengelola eksekusi streaming *out-of-core* untuk memproses dataset yang ukurannya melampaui kapasitas RAM fisik tanpa memicu *Out-Of-Memory* (OOM) crash.
*   Mengukur dan membandingkan *profiling* performa (CPU utilization, Peak Memory Footprint, dan IO throughput) antara eksekusi Eager vs. Lazy.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
*   **Pemrograman Python Lanjut:** Paham tentang Memory Model Python (GIL, reference counting, pointer overhead), Generatator/Iterators, Context Manager, dan Type Hinting (`typing`).
*   **Analisis Data Fundamental:** Manipulasi DataFrame menggunakan Pandas (operasi `groupby`, `join`, `merge`, `pivot`, agregasi window).
*   **Arsitektur Komputer & OS Dasar:** Konsep Threading vs Multiprocessing, Memory Paging, Cache Locality (L1/L2/L3), dan Disk I/O (Sequential read vs Random read).
*   **Lingkungan Eksekusi:** Terminal/CLI dengan Python $\ge$ 3.10, pustaka `polars>=0.20.0`, `pyarrow>=14.0.0`, `psutil`, dan dataset tabular minimal ribuan baris.

---

### 3. Concept
Komputasi data skala besar dalam Python selama satu dekade terakhir didominasi oleh Pandas, yang mengandalkan arsitektur array NumPy. Namun, pemrosesan data modern menghadapi dua kendala mendasar:

#### 3.1 Memory Layout: Row-Major / NumPy Pointers vs Columnar Apache Arrow
*   **NumPy/Pandas Klasik:** Data string dan objek non-numerik dalam Pandas sering kali disimpan sebagai array pointer Python (`PyObject*`). Ini menyebabkan fragmentasi memori ekstrem (*cache-misses*) dan konsumsi memori tambahan (*memory bloat*) hingga 5-10x lipat dari ukuran representasi biner mentahnya.
*   **Apache Arrow:** Merupakan spesifikasi memori *in-memory columnar format* cross-language. Data disimpan dalam blok memori kontigu per-kolom (Columnar Memory Alignment). Data string dialokasikan ke dalam dua array datar: satu array biner besar untuk karakter, dan satu array integer untuk offset index-nya. Arsitektur ini memungkinkan instruksi SIMD (Single Instruction, Multiple Data) CPU bekerja secara maksimal dan menghilangkan serialisasi/deserialisasi (*Zero-Copy* IPC).

#### 3.2 Eksekusi: Eager vs. Lazy Optimization
*   **Eager Execution (Pandas/Polars Eager):** Setiap operasi yang dipanggil (misal: `.filter()`, `.select()`, `.join()`) langsung mengeksekusi komputasi di memori detik itu juga. Akibatnya:
    1. Membuat salinan data sementara (*intermediate DataFrames*) yang memboroskan RAM.
    2. Tidak memiliki visibilitas terhadap operasi selanjutnya, sehingga tidak dapat mengoptimalkan query plan.
*   **Lazy Execution (Polars LazyFrame):** Pemanggilan fungsi tidak langsung melakukan eksekusi data, melainkan menyusun *Directed Acyclic Graph* (DAG) dari representasi logika query (*Logical Plan*). Ketika pemanggilan `.collect()` dieksekusi:
    1. Polars Query Engine (ditulis dalam Rust) melakukan optimasi logical plan menjadi physical plan.
    2. Menerapkan **Predicate Pushdown**: Filter diterapkan seawal mungkin langsung pada level scanning disk (misal hanya membaca baris yang cocok dari Parquet file metadata).
    3. Menerapkan **Projection Pushdown**: Hanya kolom yang dibutuhkan downstream yang dibaca dari disk ke memori.
    4. Mengotomatiskan komputasi paralel multithreaded tanpa terhambat oleh Python Global Interpreter Lock (GIL).

---

### 4. Why
Dalam lingkungan produksi analitik data modern:
1. **Kegagalan Skalabilitas Pandas:** Pandas berjalan secara *single-core* secara default dan membutuhkan RAM sekitar 3x hingga 5x lipat dari ukuran raw file. Membaca file CSV/Parquet sebesar 10 GB sering kali membutuhkan mesin dengan RAM 64 GB, atau memicu OOM (Error 137 pada Kubernetes/Docker).
2. **Efisiensi Finansial Cloud (Cost Optimization):** Memproses data besar dengan Polars memungkinkan penggunaan instance virtual machine (VM) dengan spesifikasi RAM lebih kecil (misalnya beralih dari AWS EC2 `r5.8xlarge` ke `c5.2xlarge`), menekan tagihan infrastruktur cloud hingga 70-80%.
3. **Pemanfaatan Core CPU Modern:** CPU server modern hadir dengan 16-128 core. Arsitektur Polars berbasis *work-stealing multi-threading* via pustaka Rust `Rayon`, memaksimalkan penggunaan semua core CPU tanpa konfigurasi kluster yang kompleks seperti Apache Spark.

---

### 5. What
Komponen arsitektur utama dalam ekosistem Lazy Out-of-Core Processing:

*   **Apache Arrow Buffer:** Format memori terstandarisasi untuk merepresentasikan array primitif, null-bitmap, dan string buffer secara contiguous.
*   **`polars.LazyFrame`:** Abstraksi representasi deklaratif komputasi yang menunda evaluasi hingga hasil akhir diminta.
*   **Polars Query Optimizer:** Sub-engine yang bertanggung jawab melakukan:
    *   *Type Coercion Optimization*
    *   *Common Subplan Elimination*
    *   *Slice Pushdown*
    *   *Predicate & Projection Pushdown*
*   **Streaming Engine (Out-of-Core Engine):** Engine eksekusi Polars yang membagi alur data ke dalam chunks (*morsels*) berukuran teratur, memprosesnya berurutan di dalam register CPU dan melepaskannya kembali, sehingga dapat memproses dataset lebih besar dari RAM fisik.

---

### 6. How
Alur pemrosesan dari deklarasi logika hingga pemanfaatan hardware:

```
[Raw Storage File: Parquet/CSV]
          │
          ▼
[polars.scan_parquet() / scan_csv()]  ──> Mendaftarkan Metadata & Inisialisasi LazyFrame
          │
          ▼
[Transformasi Deklaratif: filter, with_columns, group_by] ──> Membentuk Unoptimized Logical Plan (DAG)
          │
          ▼
[LazyFrame.explain()]  ──> Validasi Logika Query Optimizer
          │
          ▼
[Polars Query Optimizer (Rust Core)]
   ├─ 1. Predicate Pushdown (Filter sedekat mungkin ke disk)
   ├─ 2. Projection Pushdown (Eliminasi kolom tidak terpakai)
   ├─ 3. Simplify Expressions (Konstanta & aljabar boolean)
          │
          ▼
[Optimized Physical Plan]
          │
          ▼
[Streaming Engine: Streaming=True] ──> Batch Partitioning (Morsels) via Multi-threading (Rayon)
          │
          ▼
[Zero-Copy Materialization: .collect(streaming=True)] ──> Arrow Table / Output File Parquet
```

---

### 7. Analogy
Bayangkan Anda berada di sebuah restoran all-you-can-eat berlantai dua:
*   **Pandas (Eager):** Setiap kali pelayan melihat pesanan satu per satu, ia langsung pergi ke gudang di lantai satu untuk mengambil satu karung penuh sayuran, membawanya ke dapur, mengupas satu wortel, lalu membuang sisanya. Jika meja Anda memesan 10 menu, ia bolak-balik 10 kali membawa seluruh isi gudang ke lantai dua. Meja cepat penuh sesak (RAM habis/OOM).
*   **Polars Lazy:** Pelayan mencatat seluruh pesanan Anda dari awal hingga akhir dalam satu tiket pesanan (*Logical Plan*). Sebelum melangkah ke gudang, koki merevisi catatan (*Query Optimizer*): "Dia butuh 2 wortel dan 1 tomat. Jangan bawa karung sayuran lain, kupas dan potong langsung di gudang (Pushdown), lalu bawa potongan tersebut secukupnya ke atas menggunakan nampan terpisah secara serentak bersama tim pelayan lain (Multithreading Arrow buffers)".

---

### 8. Diagram

```
=== ARSITEKTUR MEMORI: PANDAS OBJECT ARRAY VS POLARS ARROW COLUMN ===

1. Pandas Series of String (Type: Object - Inefisien)
   RAM Memory Addresses (Terfragmentasi):
   [Ptr 0x1A] ──> Heap: "ID-001" (PyObject Wrapper: 48 bytes overhead)
   [Ptr 0x8C] ──> Heap: "ID-002" (PyObject Wrapper)
   [Ptr 0x3F] ──> Heap: "ID-003" (PyObject Wrapper)
   * Mengakibatkan CPU Cache Invalidation & High Pointer-Chasing Overhead.

2. Polars / Apache Arrow Utf8 Array (Kontigu & Cache-Friendly):
   Null-Bitmap Buffer  : [ 1 | 1 | 1 ]   (Bits menandakan non-null)
   Offsets Buffer (i32): [ 0 | 6 | 12 | 18 ]
   Values Buffer (u8)  : ['I','D','-','0','0','1','I','D','-','0','0','2','I','D','-','0','0','3']
   * Eksekusi SIMD langsung pada continuous array buffer.

=== QUERY ENGINE EXECUTION PIPELINE ===

   User Script
       │
       ▼
   polars.scan_parquet("s3://bucket/*.parquet")
       │
       ▼
   .filter(pl.col("status") == "COMPLETED")
       │
       ▼
   .group_by("region").agg(pl.col("amount").sum())
       │
       ▼
 ┌────────────────────────────────────────────────────────┐
 │               POLARS QUERY OPTIMIZER                   │
 │                                                        │
 │  [Raw Plan]                                            │
 │  Scan Parquet -> Filter -> GroupBy -> Agg              │
 │                                                        │
 │  [Optimized Plan Engine (Rust)]                        │
 │  1. Projection Pushdown : Scan HANYA 'status',         │
 │     'region', 'amount'                                 │
 │  2. Predicate Pushdown  : Gunakan Parquet Page Stats,  │
 │     skip row-group yang status != "COMPLETED"          │
 └──────────────────────────┬─────────────────────────────┘
                            │
                            ▼
   Parallel Worker Threads (Rayon Work-Stealing Runtime)
   [Core 0] [Core 1] [Core 2] [Core 3] ... [Core N]
                            │
                            ▼
   Final Output: Arrow RecordBatches / Polars DataFrame
```

---

### 9. Simple Example
Contoh dasar demonstrasi sintaks Eager vs Lazy pada Polars:

```python
import polars as pl

# 1. Konstruksi Mock Data
raw_data = {
    "transaction_id": [101, 102, 103, 104, 105],
    "customer_id": ["C1", "C2", "C1", "C3", "C2"],
    "amount": [150.50, 20.00, 300.00, 75.25, 120.00],
    "status": ["PAID", "FAILED", "PAID", "PAID", "PENDING"]
}

df_eager = pl.DataFrame(raw_data)

# 2. Pendekatan Eager: Eksekusi Langsung
eager_result = df_eager.filter(pl.col("status") == "PAID").group_by("customer_id").agg(
    pl.col("amount").sum().alias("total_paid")
)
print("--- Eager Result ---")
print(eager_result)

# 3. Pendekatan Lazy: Membangun Execution Plan
lazy_query = (
    df_eager.lazy()
    .filter(pl.col("status") == "PAID")
    .group_by("customer_id")
    .agg(
        pl.col("amount").sum().alias("total_paid")
    )
)

print("\n--- Unoptimized / Optimized Logical Plan ---")
print(lazy_query.explain())

# 4. Evaluasi Hasil Lazy
lazy_result = lazy_query.collect()
print("\n--- Lazy Evaluated Result ---")
print(lazy_result)
```

---

### 10. Practical Example
Pipeline analitik praktis skala industri: Membaca dataset log transaksi multi-file, membersihkan missing data, kalkulasi metrik analitik berbasis window, dan eksekusi streaming *out-of-core*.

```python
import time
import logging
from pathlib import Path
import polars as pl
import psutil
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def generate_synthetic_data(file_path: Path, rows: int = 1_000_000) -> None:
    """Helper untuk memproduksi file uji coba berbasis parquet berkala."""
    if file_path.exists():
        logger.info(f"File {file_path} sudah tersedia, melewati generasi data.")
        return

    logger.info(f"Membuat synthetic data: {rows} baris ke {file_path}...")
    df = pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2023, 1, 1),
            end=pl.datetime(2023, 1, 2),
            interval="100ms",
            eager=True
        ).slice(0, rows),
        "user_id": pl.Series(range(1000, 1000 + rows)).sample(fraction=1.0, shuffle=True),
        "device_type": pl.Series(["iOS", "Android", "Web", "API"]).sample(n=rows, with_replacement=True),
        "response_time_ms": pl.Series(range(10, 5000)).sample(n=rows, with_replacement=True),
        "http_status": pl.Series([200, 200, 200, 400, 404, 500]).sample(n=rows, with_replacement=True),
    })
    df.write_parquet(file_path, compression="zstd")
    logger.info("File parquet berhasil disimpan.")

def execute_high_performance_pipeline(source_path: Path, destination_path: Path) -> pl.DataFrame:
    """
    Menjalankan Out-of-Core Transformasi Analitik menggunakan Polars Lazy API.
    Memanfaatkan Projection Pushdown, Predicate Pushdown, dan Streaming Execution Engine.
    """
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()

    logger.info("Inisialisasi Lazy Scan...")
    
    # scan_parquet HANYA membaca metadata header, TIDAK membaca keseluruhan file ke RAM
    lazy_plan = (
        pl.scan_parquet(str(source_path))
        # 1. Predicate Pushdown: Menyaring HTTP Error sedini mungkin
        .filter(pl.col("http_status") >= 400)
        # 2. Window Function: Menghitung persentil respons time per tipe perangkat
        .with_columns([
            pl.col("response_time_ms")
            .quantile(0.95)
            .over("device_type")
            .alias("p95_response_by_device"),
            pl.col("timestamp").dt.hour().alias("hour_of_day")
        ])
        # 3. Filter anomali: Latensi di atas p95 perangkat
        .filter(pl.col("response_time_ms") > pl.col("p95_response_by_device"))
        # 4. Agregasi multi-dimensi
        .group_by(["device_type", "hour_of_day", "http_status"])
        .agg([
            pl.len().alias("error_count"),
            pl.col("response_time_ms").mean().round(2).alias("avg_anomalous_latency"),
            pl.col("response_time_ms").max().alias("max_anomalous_latency")
        ])
        .sort(by=["hour_of_day", "error_count"], descending=[False, True])
    )

    logger.info("Optimized Plan Visualization:")
    logger.info(lazy_plan.explain())

    # Eksekusi streaming: dataset diproses chunk demi chunk
    logger.info("Mengeksekusi query dengan streaming out-of-core engine...")
    materialized_df = lazy_plan.collect(streaming=True)

    # Sinkronisasi ke disk secara atomic
    materialized_df.write_parquet(destination_path)

    mem_after = process.memory_info().rss / (1024 * 1024)
    elapsed = time.perf_counter() - start_time

    logger.info(f"Eksekusi Selesai. Durasi: {elapsed:.3f} detik.")
    logger.info(f"RAM Usage Baseline: {mem_before:.2f} MB | Peak Usage: {mem_after:.2f} MB")
    
    return materialized_df

if __name__ == "__main__":
    parquet_input = Path("./server_logs.parquet")
    parquet_output = Path("./aggregated_metrics.parquet")

    generate_synthetic_data(parquet_input, rows=2_000_000)
    result = execute_high_performance_pipeline(parquet_input, parquet_output)
    print(result.head(10))
```

---

### 11. Real World Example
**Skenario Kasus FinTech: Deteksi Fraud Finansial Skala Besar (Adyen/Stripe Style)**

Sebuah payment gateway memproses 200 juta transaksi per hari dengan format Apache Parquet yang disimpan pada AWS S3. Data harian berukuran ~80 GB. Tim Data Analytics memiliki tugas harian untuk menghasilkan laporan transaksi mencurigakan (*Velocity Check Aggregation*) berbasis kriteria window waktu 1 jam.

*   **Implementasi Sebelumnya (Pandas):**
    Menggunakan EC2 instance `r5.12xlarge` (48 vCPU, 384 GB RAM). Job memicu konsumsi memori hingga 310 GB. Pipeline sering mengalami kegagalan OOM ketika volume transaksi melonjak pada *flash sale*. Biaya komputasi harian mencapai puluhan dolar per run, dengan waktu eksekusi 48 menit.
*   **Implementasi Baru (Polars Lazy + Streaming + S3 API):**
    Arsitektur dialihkan menggunakan `pl.scan_parquet("s3://payment-logs/2023/*/*.parquet")` dengan parameter `streaming=True`.
    *   *Predicate Pushdown* mengeliminasi transaksi yang di-void seketika pada level Parquet metadata decoder.
    *   *Projection Pushdown* hanya mengambil 5 kolom (`timestamp`, `merchant_id`, `card_hash`, `amount`, `cvv_matched`) dari total 45 kolom mentah.
    *   Pekerjaan dipindahkan ke instance `c5.4xlarge` (16 vCPU, 32 GB RAM).
*   **Hasil Evaluasi:**
    *   Peak Memory terkunci stabil di angka 14.2 GB (karena *out-of-core morsel processing*).
    *   Durasi eksekusi terpangkas dari 48 menit menjadi 7.5 menit via *Rust-level multithreading*.
    *   Reduksi biaya infrastruktur cloud mencapai 78%.

---

### 12. Trade-offs

| Dimensi | Pandas (Eager Execution) | Polars (Lazy Execution) |
| :--- | :--- | :--- |
| **Advantages** | Ekosistem sangat matang; integrasi natif dengan pustaka ML klasik (Scikit-Learn). | Konsumsi memori sangat rendah; komputasi otomatis multithreading; optimasi query plan otomatis. |
| **Disadvantages** | Konsumsi RAM masif (3-5x dari disk); *single-threaded bottleneck*; rawan crash OOM. | Operasi modifikasi baris granular (*index-based mutation*) tidak didukung; kurva belajar expression logic. |
| **Complexity** | Kompleksitas arsitektur rendah; debug prosedural line-by-line sangat mudah. | Kompleksitas arsitektur sedang; debugging menuntut pemeriksaan graph (`explain()`). |
| **Performance** | Rendah pada dataset $>1\text{ GB}$; tidak memanfaatkan instruksi modern SIMD secara penuh. | Sangat tinggi (sebanding dengan C++/Rust murni); vektorisasi optimal via Apache Arrow. |
| **Cost** | Menuntut instans server High-Memory (RAM besar), meningkatkan tagihan infrastruktur. | Hemat infrastruktur, cukup menggunakan instans Compute-Optimized (RAM medium). |

---

### 13. When To Use
Gunakan Polars Lazy Execution jika:
*   Dataset berukuran antara $1\text{ GB}$ hingga ratusan Gigabyte pada satu mesin komputasi tunggal.
*   Dataset melebihi kapasitas memori fisik RAM server lokal (*out-of-core pipeline* via `streaming=True`).
*   Pipeline data didominasi oleh operasi terstruktur: filtrasi, penggabungan (*joins*), agregasi (*group-by*), dan kalkulasi *window function*.
*   Anda ingin menghindari kompleksitas operasional kluster terdistribusi (seperti Apache Spark/PySpark) untuk beban data sub-terabyte.

---

### 14. When NOT To Use
Jangan gunakan Polars Lazy Execution jika:
*   Dataset berukuran trivial ($< 50\text{ MB}$), di mana overhead inisialisasi query engine dan thread-pool Polars tidak memberikan dampak performa yang signifikan dibanding Pandas standar.
*   Arsitektur pipeline data sangat bergantung pada **Index Manipulation** (misal: `MultiIndex` hierarkis milik Pandas, slicing `.iloc[]`, atau *in-place cell mutation*). Polars sengaja tidak mengimplementasikan baris berindeks untuk menjaga determinisme relasional.
*   Pipeline terikat ketat dengan framework warisan (*legacy framework*) yang hanya menerima objek `pandas.DataFrame` secara eksklusif tanpa adapter modern.
*   Data berukuran Multi-Petabyte yang memerlukan komputasi terdistribusi massal di ratusan server (gunakan PySpark atau Trino).

---

### 15. Common Mistakes
1. **Memanggil `.collect()` Terlalu Awal (*Premature Materialization*):**
   ```python
   # SALAH: Kehilangan seluruh optimasi pushdown downstream
   df = pl.scan_parquet("data.parquet").collect() # Seluruh data masuk ke RAM!
   result = df.filter(pl.col("age") > 30)

   # BENAR: Rangkai seluruh ekspresi pada LazyFrame sebelum memanggil .collect()
   result = pl.scan_parquet("data.parquet").filter(pl.col("age") > 30).collect()
   ```
2. **Menggunakan Python Loop / `.map_elements()` secara Sembarangan:**
   Memanggil fungsi Python kustom (`lambda`) via `.map_elements()` memaksa Polars keluar dari runtime engine Rust dan kembali ke interpreter Python yang terikat GIL, menghancurkan efisiensi multithreading hingga 95%. Selalu utamakan Polars native expressions (`pl.when().then().otherwise()`).
3. **Mengabaikan Konfigurasi Streaming saat RAM Terbatas:**
   Memanggil `.collect()` alih-alih `.collect(streaming=True)` pada file yang lebih besar dari RAM akan tetap menyebabkan OOM panic jika intermediate buffer membesar.

---

### 16. Best Practices (Production Checklist)
* [ ] Gunakan `pl.scan_parquet()` atau `pl.scan_ipc()` daripada `pl.read_*()` untuk inisialisasi pipeline batch.
* [ ] Selalu lakukan verifikasi *query graph* menggunakan `print(lazy_df.explain())` untuk memastikan *Predicate Pushdown* dan *Projection Pushdown* aktif.
* [ ] Konversi format input mentah dari CSV/JSON ke Apache Parquet menggunakan kompresi Snappy atau Zstandard (ZSTD) dengan statistik row-group aktif.
* [ ] Hindari konversi ke Pandas di tengah pipeline. Lakukan konversi (`.to_pandas()`) hanya di layer paling akhir jika mutlak dibutuhkan oleh modul machine learning.
* [ ] Pasang batas alokasi memori pada container (Docker/K8s) dan uji *fallback memory handling* menggunakan `POLARS_MAX_THREADS` untuk menyesuaikan beban multi-core agar tidak bersaing dengan proses OS.

---

### 17. Troubleshooting

#### Case 1: Panic `ComputeError: Out of Memory` saat Eksekusi Agregasi Besar
*   **Penyebab:** Ukuran hash table untuk operasi `.group_by()` atau `.join()` melebihi batas RAM fisik saat menggunakan engine default.
*   **Solusi:** Aktifkan streaming engine secara eksplisit:
    ```python
    # Force out-of-core algorithm
    result = lazy_plan.collect(streaming=True)
    ```

#### Case 2: Performa Lambat saat Menggunakan Custom Logic String Manipulation
*   **Penyebab:** Penggunaan `pl.col("text").map_elements(lambda x: custom_cleaner(x))` memicu *Python GIL switching overhead*.
*   **Solusi:** Tulis ulang logika menggunakan Polars string expressions tervektorisasi:
    ```python
    # Solusi Vektor: Sepenuhnya berjalan di dalam modul Rust
    lazy_plan = lazy_plan.with_columns(
        pl.col("raw_text")
        .str.to_lowercase()
        .str.replace_all(r"[^a-zA-Z0-9]", "")
        .alias("cleaned_text")
    )
    ```

---

### 18. Exercise
Selesaikan skrip Python di bawah ini untuk memperbaiki inefisiensi pipeline data analitik e-commerce.

**File Starter (`exercise_template.py`):**
```python
import polars as pl

# TARGET:
# 1. Ubah kode eager di bawah menjadi Lazy pipeline.
# 2. Pastikan filter 'completed' dan select kolom dipushdown oleh engine.
# 3. Hitung rasio omzet: (total_sales_per_category / total_global_sales).

def process_sales_eager_bad(csv_path: str):
    # TODO: Perbaiki fungsi ini menggunakan scan_csv dan lazy evaluation
    df = pl.read_csv(csv_path) # Inefisien!
    df_filtered = df.filter(df["status"] == "COMPLETED")
    df_grouped = df_filtered.group_by("category").agg(pl.col("price").sum().alias("category_sales"))
    return df_grouped
```

**Tugas Anda:**
1. Rancang fungsi `process_sales_lazy_optimal(csv_path: str) -> pl.DataFrame`.
2. Gunakan `pl.scan_csv()`.
3. Terapkan kalkulasi rasio kategori terhadap penjualan global dalam satu DAG LazyFrame tunggal.

---

### 19. Challenge
Rancang sebuah pipeline pengujian toleransi stres data (*Stress-testing Pipeline Engine*) yang memenuhi spesifikasi berikut:
1. Buat generator data yang menulis 10 file Parquet terpisah, masing-masing berukuran $\approx 500\text{ MB}$ (Total $\approx 5\text{ GB}$ data sintetis transaksi perbankan).
2. Jalankan sistem pada container/mesin dengan batasan RAM maksimum **2 GB** (Gunakan `resource.setrlimit` pada Linux/macOS atau jalankan via Docker dengan flag `--memory="2g"`).
3. Pipeline harus memproses seluruh 10 file tersebut secara paralel (`scan_parquet(["file_*.parquet"])`), melakukan:
   * *Anti-join* dengan blacklist table yang berisi 100.000 `account_id`.
   * Perhitungan *Rolling 7-day Average Transaction Amount* per pengguna.
   * Ekspor hasil anomali akhir ke Parquet terkompresi.
4. **Kriteria Kelulusan:** Pipeline selesai tanpa crash OOM (Exit code 0), memori residen (RSS) tidak pernah melampaui ambang batas 1.8 GB, dan diagram query optimasi (`.explain()`) membuktikan terjadinya *Projection Pushdown*.

---

### 20. Summary
*   **Apache Arrow Columnar Layout** mentransformasi paradigma performa data pada Python dengan membuang overhead struktur objek berpenunjuk (*pointer-based arrays*) dan menggantikannya dengan struktur data kontigu yang ramah terhadap CPU L1/L2 cache dan SIMD instruction set.
*   **Polars Lazy Engine** memisahkan antara tahapan *deklarasi intensi analitik* dan *realisasi komputasi fisik*.
*   Fitur **Predicate Pushdown** dan **Projection Pushdown** memastikan sistem komputasi hanya membaca baris dan kolom yang mutlak diperlukan langsung dari storage engine, mengurangi disk I/O dan alokasi memori secara signifikan.
*   Dengan kapabilitas **Streaming Out-of-Core Processing**, developer Python modern dapat memproses data berskala puluhan hingga ratusan Gigabyte pada workstation atau instans server standar secara tangguh tanpa ancaman *Out-Of-Memory* (OOM).