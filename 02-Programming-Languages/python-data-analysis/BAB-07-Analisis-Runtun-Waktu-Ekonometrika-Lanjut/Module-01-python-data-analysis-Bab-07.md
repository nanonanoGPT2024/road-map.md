# Bab 07: Performa Tinggi & Skalabilitas Data
## Modul 01: Pemrosesan Data Kolumnar dengan Polars dan Apache Arrow

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta mampu:
*   Menganalisis inefisiensi alokasi memori pada representasi baris (*row-oriented*) dan model berbasis pointer Python (*NumPy/Pandas 1.x object overhead*).
*   Mengimplementasikan pipeline analitik berperforma tinggi menggunakan antarmuka **Polars LazyFrame** dengan optimasi eksekusi kueri terkompilasi (*Predicate & Projection Pushdown*).
*   Mengeksploitasi arsitektur **Apache Arrow Columnar Format** untuk integrasi interoperabilitas *zero-copy memory sharing* antar-*engine*.
*   Mendesain strategi agregasi dan transformasi data berskala puluhan gigabyte (*out-of-core streaming*) pada mesin berdaya komputasi terbatas tanpa memicu *Out-Of-Memory* (OOM) crash.

---

### 2. Prerequisite
*   Pemahaman tingkat lanjut tentang arsitektur memori Python (CPython heap allocation, reference counting, GIL).
*   Penguasaan manipulasi data tabular dasar (*Pandas DataFrame, split-apply-combine, window functions*).
*   Pemahaman mendasar mengenai format penyimpanan terkompresi berbasis kolom (*Apache Parquet metadata, row groups, dictionary encoding*).
*   Familiaritas dengan konsep konkurensi hardware: CPU cache line (L1/L2/L3), branch prediction, serta vektorisasi SIMD (*Single Instruction, Multiple Data*).

---

### 3. Concept
Secara fundamental, transisi dari *engine* analitik generasi lama (seperti Pandas berbasis NumPy array 1D) ke generasi modern (Polars dan Apache Arrow) didorong oleh dua prinsip rekayasa perangkat lunak sistem: **Columnar Memory Layout** dan **Vectorized Execution Engine**.

#### A. In-Memory Columnar Format (Apache Arrow)
Pada format baris tradisional (*row-oriented*), rekaman data dialokasikan berurutan: `[R1_C1, R1_C2, R1_C3], [R2_C1, R2_C2, R2_C3]`. Ketika operasi analitik mengeksekusi kalkulasi rata-rata pada `C1`, CPU dipaksa memuat seluruh baris ke dalam CPU cache line (biasanya 64 byte), yang membuang kapasitas transfer memori (*memory bandwidth*) untuk membaca data yang tidak relevan (`C2`, `C3`).

Apache Arrow menyusun data secara kolumnar dan terstandarisasi secara biner (*contiguous buffer*):
*   Nilai primitif disimpan dalam buffer memori kontinu yang saling berdekatan.
*   Data *null/missing* ditangani menggunakan *Validity Bitmap* terpisah (1 bit per nilai), meniadakan penggunaan sentinel value (seperti `NaN` float yang merusak integritas tipe data integer).
*   Format ini didesain agar data dapat ditransmisikan antar-proses (IPC - *Inter-Process Communication*) atau lintas bahasa (C++, Rust, Python, R, Java) tanpa serialisasi/deserialisasi (*Zero-Copy*).

#### B. Rust-Powered Multithreaded Engine (Polars)
Polars dibangun dari dasar menggunakan bahasa pemrograman Rust di atas spesifikasi memori Apache Arrow. Keunggulan arsitekturalnya meliputi:
1.  **Work-Stealing Concurrency:** Memanfaatkan *scheduler* paralel (Rayon) untuk mendistribusikan beban kerja secara merata ke seluruh core CPU tanpa hambatan Python GIL (*Global Interpreter Lock*).
2.  **Expression Engine:** Manipulasi data dipandang sebagai *Abstract Syntax Tree* (AST) dari ekspresi yang dapat diparalelkan secara otomatis.
3.  **Lazy Evaluation & Query Optimizer:** Polars membedakan fase deklarasi kueri (`LazyFrame`) dan fase eksekusi (`DataFrame`). Kueri dioptimalkan melalui compiler internal sebelum satu byte pun data dibaca dari disk.

---

### 4. Why
*   **Hambatan Memori Pandas 1.x:** Pandas mengalokasikan objek Python individual atau wrapper NumPy. Untuk tipe data string non-PyArrow, Pandas menyimpan pointer ke objek CPython `PyObject`, di mana satu string membutuhkan minimal 48–56 byte overhead di luar ukuran karakter sebenarnya. Ini menghasilkan konsumsi memori 3x hingga 10x lebih besar daripada ukuran dataset di disk.
*   **Skalabilitas Single-Core vs Multi-Core:** Operasi seperti `df.groupby().agg()` pada Pandas secara inheren berjalan pada satu core CPU. Pada server modern dengan 32–128 vCPU, Pandas membiarkan 97% kapasitas komputasi menganggur. Polars memanfaatkan seluruh core secara native.
*   **Batas Memori Fisik (Out-of-Core Processing):** Dataset yang sedikit melampaui RAM sistem akan menyebabkan Pandas melempar `MemoryError` atau memaksa sistem operasi melakukan *swap thrashing*, menurunkan *throughput* hingga 1.000x lipat. Polars mengatasi ini lewat kapabilitas *streaming engine* yang mengeksekusi data per *batch*.

---

### 5. What
Komponen arsitektural inti dalam ekosistem Polars & Arrow:

*   **Arrow Array:** Struktur data tingkat rendah yang terdiri dari satu atau lebih buffer memori (data buffer, validity buffer, offset buffer untuk tipe variabel seperti teks).
*   **Polars Series & DataFrame (Eager):** Struktur data yang menyimpan data teralokasi langsung di memori, dieksekusi seketika saat kode dipanggil.
*   **Polars LazyFrame:** Representasi deklaratif dari rencana komputasi (*Unoptimized Logical Plan*). Tidak ada data yang dimuat ke RAM saat deklarasi.
*   **Query Optimizer:** Subsistem yang mentransformasi *Logical Plan* menjadi *Optimized Physical Plan* menggunakan aturan optimasi:
    *   *Predicate Pushdown:* Memindahkan operasi pemfilteran (`filter`) sedekat mungkin dengan sumber data (misalnya tingkat pembacaan Parquet row-group) untuk meminimalkan data yang dibaca.
    *   *Projection Pushdown:* Hanya membaca kolom-kolom yang secara eksplisit dibutuhkan dalam kueri hilir.
    *   *Slice Pushdown:* Mengoptimalkan pemotongan baris (`limit`, `slice`).
    *   *Common Sub-plan Elimination:* Menggabungkan komputasi duplikat dalam satu pohon kueri.
*   **Polars Expressions (`pl.col`, `pl.when`, dll.):** Spesifikasi deklaratif yang mendefinisikan transformasi fungsi murni (*pure functions*) yang aman dieksekusi secara paralel.

---

### 6. How
Alur kerja pemrosesan data berbasis Polars LazyFrame:

```
[Raw Parquet/CSV on Disk/S3]
              │
              ▼
   pl.scan_parquet() / pl.scan_csv()
              │
              ▼
    [Unoptimized Logical Plan]
  (Tree of relational operations)
              │
              ▼
    Polars Query Optimizer
    ├── Predicate Pushdown (Filter data directly at scan)
    ├── Projection Pushdown (Read only required columns)
    └── Simplify Expressions (Constant folding, etc.)
              │
              ▼
    [Optimized Logical Plan]
              │
              ▼
    Physical Plan Generator
              │
              ▼
    Rayon Multithreaded Execution Engine (Streaming/Batched chunks)
              │
              ▼
       .collect() / .sink_parquet()
```

1.  **Inisiasi Pemindaian (*Scan*):** Menggunakan `pl.scan_parquet()` alih-alih `read_parquet()`. Metadata file dibaca; skema diverifikasi tanpa membaca data aktual.
2.  **Penyusunan Ekspresi:** Rangkaian transformasi (`filter`, `with_columns`, `group_by`) dirangkai ke dalam objek `LazyFrame`.
3.  **Kompilasi & Optimasi:** Pemanggilan metode `.collect()` memicu compiler internal Polars untuk menghasilkan *Logical Plan*, menerapkan teknik *Pushdown*, dan mereduksi I/O yang tidak diperlukan.
4.  **Eksekusi Terparalelisasi:** Task didistribusikan ke *thread pool* Rayon, mengeksekusi kalkulasi vektor berbasis *chunk* secara langsung di level memori register dan cache CPU.
5.  **Materialisasi atau Streaming:** Hasil diekstraksi ke RAM sebagai `DataFrame` utuh atau langsung dialirkan kembali ke disk melalui `.sink_parquet()` tanpa membebani memori utama secara berlebihan.

---

### 7. Analogy
Bayangkan sebuah restoran berskala industri:

*   **Pendekatan Pandas (Row/Eager):** Pelayan mendatangi gudang bahan makanan, mengambil seluruh stok makanan (misal: 1 truk berisi daging, sayur, buah, bumbu) ke atas meja dapur (*RAM exhaustion*), meskipun koki hanya butuh 1 wortel. Pemotongan dilakukan oleh satu orang koki secara berurutan (*single thread*), membuang bahan yang tidak digunakan satu per satu setelah selesai dimasak.
*   **Pendekatan Polars Lazy + Arrow (Columnar/Optimized):** Koki menuliskan daftar spesifik pesanan pada sebuah papan tiket (*LazyFrame*). Manajer dapur (*Query Optimizer*) menganalisis tiket, memotong langkah yang tidak perlu, dan menginstruksikan tim logistik di gudang untuk *hanya* mengirimkan sekeranjang wortel (*Projection & Predicate Pushdown*). Di dapur, 16 koki (*Multi-core Rayon*) memotong wortel tersebut secara serentak di stasiun kerja masing-masing menggunakan alat pemotong mekanis seragam (*SIMD Vectorization*), langsung mengemasnya ke wadah siap saji tanpa mengotori meja utama dapur.

---

### 8. Diagram

```
ARSITEKTUR MEMORI: PANDAS (NUMPY OBJECT) VS POLARS (APACHE ARROW)

[PANDAS / NUMPY 1.x STRING REPRESENTATION]
DataFrame Memory
┌──────────────┐      Heap Allocations (Fragmented Cache Invalidation)
│ Pointer 0    ├────► ┌───────────────────────────┐
├──────────────┤      │ PyObject (String: "ID_A") │ (Overhead 50+ bytes)
│ Pointer 1    ├────┐ └───────────────────────────┘
├──────────────┤    │ ┌───────────────────────────┐
│ Pointer 2    ├─┐  └►│ PyObject (String: "ID_B") │
└──────────────┘ │    └───────────────────────────┘
                 │    ┌───────────────────────────┐
                 └───►│ PyObject (String: "ID_C") │
                      └───────────────────────────┘
                 (Non-contiguous, High Cache Miss Rate)

──────────────────────────────────────────────────────────────────────────

[POLARS / APACHE ARROW COLUMNAR LAYOUT]
Polars Utf8 ChunkedArray
1. Offsets Buffer   : [ 0, 4, 8, 12 ]       (Contiguous int32/int64)
2. Data Buffer      : [ I, D, _, A, I, D, _, B, I, D, _, C ] (Contiguous bytes)
3. Validity Bitmap  : [ 1, 1, 1 ]           (1-bit per element, Bitpacked)

   Data dialokasikan rapat dalam blok memori tunggal (Contiguous memory).
   Cache line CPU (64-byte) memuat banyak nilai sekaligus -> Cache Hit Tinggi.

──────────────────────────────────────────────────────────────────────────

EKSEKUSI LAZY EVALUATION (OPTIMIZATION PASS)

User Code:
scan_parquet("data.parquet") -> filter(col("val") > 10) -> select("id", "val")

           Raw Logical Plan                      Optimized Physical Plan
       ┌──────────────────────┐                  ┌──────────────────────┐
       │   Select (id, val)   │                  │   Parquet Scanner    │
       └──────────▲───────────┘                  │  - Read Cols: id, val│
                  │                              │  - Filter: val > 10  │
       ┌──────────┴───────────┐                  └──────────────────────┘
       │  Filter (val > 10)   │                  (Projection & Predicate
       └──────────▲───────────┘                     pushed into storage I/O)
                  │
       ┌──────────┴───────────┐
       │ Parquet Scan (ALL)   │
       └──────────────────────┘
```

---

### 9. Simple Example
Perbandingan deklarasi pemrosesan dasar antara Pandas dan Polars.

```python
import polars as pl

# 1. Deklarasi Data Kolumnar In-Memory
data = {
    "transaction_id": ["TX1001", "TX1002", "TX1003", "TX1004"],
    "customer_id": [101, 102, 101, 103],
    "amount": [150.50, 23.00, 99.90, 450.00],
    "status": ["COMPLETED", "FAILED", "COMPLETED", "PENDING"]
}

# Membuat Polars DataFrame
df = pl.DataFrame(data)

# 2. Ekspresi Terstruktur Polars (Columnar Native)
# Menghitung agregasi amount untuk transaksi yang sukses secara eager
result = (
    df.lazy()
    .filter(pl.col("status") == "COMPLETED")
    .group_by("customer_id")
    .agg(
        total_spent=pl.col("amount").sum(),
        tx_count=pl.col("transaction_id").count()
    )
    .sort("total_spent", descending=True)
    .collect()
)

print(result)
```

---

### 10. Practical Example
Pipeline analitik bertaraf produksi yang memproses data log server berskala besar dengan validasi skema, ekspresi agregasi kompleks, *window functions*, dan penanganan memori streaming.

```python
from pathlib import Path
import tempfile
import polars as pl
import numpy as np

def generate_mock_log_data(file_path: Path, num_rows: int = 1_000_000) -> None:
    """Menghasilkan dataset representatif dalam format Apache Parquet."""
    np.random.seed(42)
    service_names = ["auth-service", "payment-service", "order-engine", "api-gateway"]
    http_methods = ["GET", "POST", "PUT", "DELETE"]
    status_codes = [200, 201, 400, 401, 404, 500, 503]
    
    df = pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2026, 1, 1),
            end=pl.datetime(2026, 1, 2),
            interval="100ms",
            eager=True
        ).slice(0, num_rows),
        "service": np.random.choice(service_names, size=num_rows),
        "method": np.random.choice(http_methods, size=num_rows),
        "status_code": np.random.choice(status_codes, size=num_rows, p=[0.7, 0.1, 0.05, 0.05, 0.05, 0.03, 0.02]),
        "latency_ms": np.random.exponential(scale=50.0, size=num_rows) + 5.0,
        "bytes_sent": np.random.lognormal(mean=8.0, sigma=1.0, size=num_rows).astype(np.int64)
    })
    df.write_parquet(file_path, compression="snappy", statistics=True)

def process_service_metrics(source_path: Path, output_path: Path) -> pl.DataFrame:
    """
    Mengeksekusi query plan teroptimasi menggunakan Polars Lazy API:
    - Projection & Predicate Pushdown
    - Rolling window percentile calculation
    - Out-of-core aggregate sinks
    """
    # Inisiasi Lazy Scan (I/O disk belum terjadi di sini)
    lazy_plan = (
        pl.scan_parquet(source_path)
        # 1. Predicate Pushdown: Menyaring data langsung pada tingkat I/O Parquet
        .filter(
            (pl.col("timestamp") >= pl.datetime(2026, 1, 1, 0, 0, 0)) &
            (pl.col("status_code") != 404)
        )
        # 2. Window Function & Mutasi Kolom (In-Engine, No Python Loop)
        .with_columns(
            is_error=pl.col("status_code").is_in([500, 503]),
            traffic_bucket=pl.col("bytes_sent") / 1024  # Konversi ke KiB
        )
        # 3. Aggregation Engine berbasis Multithreaded Hash Group-By
        .group_by(["service", "method"])
        .agg(
            total_requests=pl.len(),
            error_count=pl.col("is_error").sum(),
            mean_latency=pl.col("latency_ms").mean(),
            p95_latency=pl.col("latency_ms").quantile(0.95, interpolation="linear"),
            p99_latency=pl.col("latency_ms").quantile(0.99, interpolation="linear"),
            total_bandwidth_kib=pl.col("traffic_bucket").sum()
        )
        # 4. Derivasi Metrik Tambahan
        .with_columns(
            error_rate_percentage=(pl.col("error_count") / pl.col("total_requests")) * 100.0
        )
        .sort(by=["error_rate_percentage", "p99_latency"], descending=[True, True])
    )

    # Menampilkan Rencana Eksekusi Teroptimasi (EXPLAIN)
    print("=== OPTIMIZED LOGICAL PLAN ===")
    print(lazy_plan.explain())

    # Eksekusi kueri teroptimasi
    result_df = lazy_plan.collect(engine="streaming")
    
    # Simpan hasil agregasi ke disk
    result_df.write_parquet(output_path)
    return result_df

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_file = Path(tmp_dir) / "raw_logs.parquet"
        output_file = Path(tmp_dir) / "aggregated_metrics.parquet"

        print("Generating mock telemetry data...")
        generate_mock_log_data(input_file, num_rows=500_000)

        print("Processing logs via Polars Lazy Engine...")
        metrics = process_service_metrics(input_file, output_file)
        
        print("\n=== TOP 5 BOTTLENECK SERVICES ===")
        print(metrics.head(5))
```

---

### 11. Real World Example
**Domain:** FinTech / Real-time Fraud Detection & Analytics.
**Problem Statement:** Sebuah platform pembayaran memproses sekitar 120 juta transaksi per hari. Tim risiko harus menghitung *rolling metrics* (misalnya: rasio transaksi terhadap *historical moving average*, lonjakan volume per *merchant* dalam jendela 5 menit) untuk mendeteksi anomali. Solusi berbasis Pandas mengalami kegagalan OOM pada mesin berkapasitas 64 GB RAM ketika memproses 10 jam data log transaksi mentah (~35 GB Parquet), dengan waktu eksekusi melebihi 48 menit.

**Solusi Arsitektural Polars & Arrow:**
1.  **Arsitektur Lazy + Streaming:** Mengonversi alur data dari `pandas.read_parquet()` ke `pl.scan_parquet()`.
2.  **Partisi Waktu & Sorting Paralel:** Memanfaatkan *non-blocking multithreaded sort* dari Polars untuk mengatur data berdasarkan `[merchant_id, timestamp]`.
3.  **Dynamic Over Expressions:** Mengganti loop iteratif dan pemanggilan `df.groupby().rolling()` lambat pada Pandas dengan ekspresi kolumnar murni Polars:
    ```python
    pl.col("amount").mean().over(
        partition_by="merchant_id",
        order_by="timestamp",
        mapping_strategy="join"
    )
    ```
4.  **Zero-Copy Handover ke Mesin Inferensi C++:** Menggunakan protokol Apache Arrow C Data Interface (`df.to_arrow()`) untuk mempassing data langsung ke model skoring inferensi C++ tanpa serialisasi data ke JSON/CSV/Python dict.

**Hasil Terukur:**
*   Penggunaan Memori Puncak (*Peak RAM*): Turun dari **>64 GB (Crash/OOM)** menjadi **11.4 GB**.
*   Waktu Komputasi: Berkurang dari **48 menit** menjadi **3 menit 12 detik** (Peningkatan efisiensi komputasi ~15x lipat).
*   Biaya Infrastruktur: Mengeliminasi kebutuhan node komputasi berdaya memori masif (*high-memory cloud instances*), memotong biaya server harian hingga 60%.

---

### 12. Trade-offs

| Aspek Komparasi | Pandas (v1.x / NumPy Array) | Polars (Lazy / Apache Arrow) |
| :--- | :--- | :--- |
| **Kelebihan (Advantages)** | Kompatibilitas universal dengan library ML lama (Scikit-Learn native API); fleksibilitas mutasi baris individual. | Pemanfaatan CPU multi-core native (100% core saturation); arsitektur memori Arrow yang hemat ruang; lazy query optimization otomatis. |
| **Kekurangan (Disadvantages)** | Single-threaded GIL bound; inefisiensi memori pointer; rawan bug mutasi sampingan (*SettingWithCopyWarning*). | Paradigma deklaratif menolak mutasi baris acak (*in-place assignment* dilarang); sintaks ekspresi baru membutuhkan adaptasi tim. |
| **Kompleksitas (Complexity)** | Sederhana di awal (*procedural code*), namun sulit dioptimalkan saat menangani data di atas ukuran memori (*OOM handling* manual). | Memerlukan pemahaman deklaratif/relasional (*Logical Plan vs Physical Plan*); penanganan custom schema data bertingkat lebih ketat. |
| **Performa (Performance)** | Rendah pada dataset besar; latensi I/O tinggi karena membaca seluruh kolom dan baris. | Sangat tinggi (SIMD-enabled, Cache-aware, zero serialization I/O via Arrow). |
| **Biaya Komputasi (Cost)** | Tinggi; membutuhkan *compute node* dengan RAM minimal 3-5x dari ukuran dataset aktual. | Rendah; dapat mengeksekusi puluhan gigabyte data pada laptop komoditas atau instans cloud hemat biaya. |

---

### 13. When To Use
*   Ketika dataset berukuran antara **1 GB hingga 500 GB** dan harus diproses pada mesin tunggal (*single-node workstation/server*).
*   Ketika pipeline didominasi oleh operasi analitik: *Filtering*, *Aggregations*, *Window functions*, dan *Joins*.
*   Ketika data disimpan dalam format modern berbasis kolom seperti **Apache Parquet**, **Feather**, atau **IPC Arrow Stream**.
*   Ketika sistem membutuhkan interoperabilitas lintas bahasa (Python $\leftrightarrow$ Rust $\leftrightarrow$ Go $\leftrightarrow$ C++) dengan zero-copy overhead.

---

### 14. When NOT To Use
*   Ketika ukuran data melebihi batas *terabyte* di mana arsitektur terdistribusi multi-node wajib digunakan (lebih tepat menggunakan **Apache Spark**, **Ray**, atau **Trino**).
*   Aplikasi transaksional OLTP tingkat rendah yang membutuhkan manipulasi baris individual secara kontinu (*single-cell update/insert/delete* secara real-time).
*   Kode dasar terintegrasi erat dengan library lama yang hanya menerima objek `pandas.DataFrame` dan tidak mendukung Arrow interface, di mana *casting overhead* `to_pandas()` akan meniadakan manfaat latensi.

---

### 15. Common Mistakes

#### 1. Memanggil `.collect()` Terlalu Awal
*Anti-pattern:*
```python
# Salah: Memaksa materialisasi ke RAM sebelum optimasi pushdown bekerja
df = pl.scan_parquet("large_data.parquet").collect()
filtered_df = df.filter(pl.col("user_id") == 12345)
```
*Solusi:*
Pertahankan pipeline dalam bentuk `LazyFrame` hingga akhir, biarkan engine memotong baris pada level disk reading:
```python
# Benar: Predicate pushdown dikirim langsung ke pembaca Parquet
df = (
    pl.scan_parquet("large_data.parquet")
    .filter(pl.col("user_id") == 12345)
    .collect()
)
```

#### 2. Menggunakan Custom Python UDF di Dalam Polars
*Anti-pattern:*
```python
# Salah: Memaksa eksekusi keluar dari Rust ke CPython VM (memicu overhead GIL)
def complex_calc(val):
    return val * 2 if val > 10 else val / 2

df.with_columns(result=pl.col("value").map_elements(complex_calc, return_dtype=pl.Float64))
```
*Solusi:*
Tulis seluruh kalkulasi menggunakan ekspresi native Polars yang berjalan pada kode biner Rust:
```python
# Benar: Diproses secara vectorized di level register CPU
df.with_columns(
    result=pl.when(pl.col("value") > 10)
    .then(pl.col("value") * 2)
    .otherwise(pl.col("value") / 2)
)
```

#### 3. Mengasumsikan Index Kolom Pandas Eksis di Polars
Polars secara sadar **meniadakan konsep `Index`** yang ada di Pandas. Mengandalkan `reset_index()`, multi-index hierarkis, atau pencarian via label index akan memicu kebingungan struktural. Identitas baris harus selalu diperlakukan sebagai kolom eksplisit.

---

### 16. Best Practices

*   [ ] **Utamakan `pl.scan_parquet` daripada `pl.read_parquet`:** Selalu mulai pembangunan alur kerja menggunakan lazy context untuk membuka potensi *query optimizer*.
*   [ ] **Gunakan Skema Eksplisit:** Saat memindai file CSV atau JSON, berikan parameter `schema` untuk menghindari pemindaian inferensi ganda pada file mentah.
*   [ ] **Minimalkan Alih Ragam Bahasa (CPython Bridge):** Hindari penggunaan `map_elements()`, `apply()`, atau integrasi library Python eksternal di tengah proses ekspresi transformasi.
*   [ ] **Terapkan `streaming=True`:** Untuk beban kerja yang volumenya berdekatan atau melebihi kapasitas memori sistem, gunakan `.collect(engine="streaming")` atau `.sink_parquet()`.
*   [ ] **Pilih Encoding & Compression yang Tepat:** Simpan output Parquet menggunakan kompresi `zstd` (keseimbangan rasio kompresi tinggi dan dekompresi cepat) atau `snappy` (latensi terendah).

---

### 17. Troubleshooting

#### Masalah 1: `PolarsError: SchemaMismatch` Saat Memindai Multi-File
*Penyebab:* Pembacaan glob pattern (`pl.scan_parquet("data/*.parquet")`) gagal karena beberapa file memiliki skema kolom yang berbeda (misalnya: file A bertipe data `Int32`, file B bertipe data `Int64`).
*Solusi:* Normalisasi skema data menggunakan argumen `schema` atau standarisasi casting tipe data pada tahap penulisan file hulu.

#### Masalah 2: Out-Of-Memory Saat Melakukan GroupBy Kardinalitas Ekstrem
*Penyebab:* Mengelompokkan data berdasarkan string berkardinalitas sangat tinggi (jutaan unique keys) pada RAM terbatas dapat membebani *Hash Table allocation*.
*Solusi:* 
1. Konversi tipe data string ke `pl.Categorical` sebelum group-by untuk menghemat alokasi tabel hash.
2. Paksa streaming engine:
```python
q = df.lazy().group_by("high_cardinality_col").agg(pl.col("metric").sum())
q.collect(engine="streaming")
```

#### Masalah 3: Konversi Zero-Copy Gagal Saat Interoperabilitas dengan NumPy
*Penyebab:* Kolom memiliki *null values* (missing values). Format Apache Arrow menggunakan *Validity Bitmap*, sedangkan NumPy tradisional tidak memiliki konsep bitmap sehingga terpaksa menduplikasi/mengalokasikan ulang memori (membuat salinan *copy* alih-alih *zero-copy view*).
*Solusi:* Tangani data kosong terlebih dahulu menggunakan `.fill_null(strategy=...)` sebelum memanggil `.to_numpy()`.

---

### 18. Exercise
Sebuah dataset e-commerce tersimpan dalam format Parquet (`transactions.parquet`) dengan kolom: `transaction_id` (str), `customer_id` (int), `category` (str), `price` (float), dan `timestamp` (datetime).

Tulis skrip berbasis Polars LazyFrame yang:
1.  Menyaring transaksi yang terjadi hanya pada kuartal pertama tahun 2026.
2.  Menyaring transaksi dengan nilai `price` di atas 0.
3.  Menghitung metrik berikut per `category`:
    *   Total nilai penjualan (`gross_revenue`).
    *   Rata-rata pengeluaran per transaksi (`aov`).
    *   Jumlah pelanggan unik (`unique_customers`).
4.  Cetak rencana eksekusi teroptimasi (*optimized logical plan*) ke konsol sebelum mengeksekusinya ke dalam sebuah `pl.DataFrame`.

---

### 19. Challenge
Rancang sebuah pipeline analisis logs berkapasitas besar tanpa materialisasi penuh ke RAM:

**Skenario:** Terdapat 50 file CSV terpisah di direktori `./raw_sensor_data/`, masing-masing berukuran ~500 MB (Total: 25 GB). Mesin yang Anda gunakan hanya memiliki **4 GB RAM**.
Setiap baris mencatat: `device_id` (UUID string), `sensor_type` (str), `reading` (float), `is_error` (bool), `recorded_at` (str format ISO).

**Tugas Anda:**
Bangun kode produksi menggunakan Polars yang:
1.  Melakukan *lazy scan* terhadap seluruh 50 file secara sekaligus menggunakan pattern matching.
2.  Mem-parsing `recorded_at` ke tipe `pl.Datetime` secara efisien.
3.  Menyingkirkan data di mana `is_error == True`.
4.  Menghitung *rolling average* pembacaan sensor selama jendela 10 menit untuk tiap `device_id`.
5.  Mengalirkan (*sink*) hasil transformasi langsung ke sebuah file Parquet tunggal terkompresi `zstd` tanpa pernah mengonsumsi RAM lebih dari 2 GB. Pastikan alur data diverifikasi menggunakan engine streaming out-of-core Polars (`sink_parquet`).

---

### 20. Summary
*   **Paradigma Arsitektur:** Polars merevolusi pemrosesan data berbasis Python dengan meninggalkan representasi berbasis baris dan pointer CPython yang tidak efisien, berpindah sepenuhnya ke representasi memori kolumnar terstandardisasi **Apache Arrow**.
*   **Paralelisasi Bebas GIL:** Dengan mesin komputasi inti yang dibangun menggunakan Rust dan Rayon, Polars mengeksekusi beban kerja komputasi secara multi-threaded murni, mengeksploitasi seluruh core CPU dan kapabilitas instruksi SIMD.
*   **Optimalisasi Deklaratif:** Polars LazyFrame memisahkan definisi logika dari eksekusi fisik. Melalui mekanisme *Predicate & Projection Pushdown*, sistem hanya membaca data yang mutlak diperlukan langsung dari tingkat disk storage.
*   **Skalabilitas Produksi:** Melalui format Arrow dan kapabilitas out-of-core streaming, rekayasa data modern dapat menangani volume data analitik yang masif pada infrastruktur komputasi standar dengan efisiensi memori dan kecepatan tinggi.