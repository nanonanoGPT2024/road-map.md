# Bab 10 Module 01: Arsitektur Columnar Memory, Apache Arrow, dan High-Performance Data Processing dengan Polars

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
*   Menganalisis inefisiensi alokasi memori baris (*row-oriented*) dan fragmentasi pointer objek Python pada beban kerja analisis data skala gigabyte.
*   Mengimplementasikan struktur data *in-memory columnar* berbasis spesifikasi **Apache Arrow** untuk mengeliminasi latensi *serialization/deserialization* antar-sistem (*zero-copy interchange*).
*   Menyusun dan mengoptimalkan pipeline analitik performa tinggi menggunakan antarmuka **Polars LazyFrame** dengan memanfaatkan optimasi kueri internal (*Predicate Pushdown*, *Projection Pushdown*).
*   Mengelola eksekusi paralel bebas GIL (*Global Interpreter Lock*) dan komputasi SIMD (*Single Instruction, Multiple Data*) pada pemrosesan data *out-of-core* (melebihi kapasitas RAM fisik) menggunakan mesin streaming Polars.

---

### 2. Prerequisite
Untuk memahami materi ini secara komprehensif, Anda diharapkan telah menguasai:
*   **Pemrograman Python Lanjutan**: Konsep memori internal Python (alokasi heap, *reference counting*, CPython *object headers* `PyObject`).
*   **Fundamental NumPy**: *Strides*, *C-contiguous* vs *Fortran-contiguous arrays*, dan batasan tipe data primitif seragam.
*   **Arsitektur Komputer Dasar**: Hirarki *cache* CPU (L1, L2, L3), *cache line* (64 bytes), *cache miss*, dan instruksi vektor SIMD (AVX-256 / AVX-512).
*   **Sistem I/O & Format File**: Konsep biner Parquet, IPC (*Inter-Process Communication*), dan operasi *memory-mapped files* (`mmap`).

---

### 3. Concept
Komputasi analitik tradisional di Python (seperti Pandas berbasis NumPy v1) dirancang dengan pendekatan *row-major array* atau kumpulan *pointer-based objects*. Ketika sebuah tabel data memuat kolom string atau nilai kosong (*null values*), representasi internal Python membungkus setiap elemen ke dalam struktur `PyObject` terpisah (berukuran minimum 28–56 byte per nilai primitif). Hal ini memicu dereferensi pointer masif (*pointer chasing*) yang melompati alamat memori fisik secara acak, menghancurkan lokalitas spasial *CPU cache* (*L1/L2 cache misses*), dan memperlambat throughput pemrosesan data.

```
Pendekatan Tradisional (Pandas / Row-Adjacent Reference Array):
[Pointer 0] ---> PyObject (Header 16B + TypePtr 8B + Data 8B)
[Pointer 1] ---> PyObject (Header 16B + TypePtr 8B + Data 8B)  <-- Tidak kontigu di RAM!

Pendekatan Apache Arrow (Columnar Memory Format):
Validity Bitmap: [1, 1, 0, 1] (1 bit per nilai)
Offsets Buffer : [0, 4, 9, 9, 13] (Menyimpan indeks slice byte)
Values Buffer  : ['K','U','R','S','D','O','L','A','R','E','U','R','O'] (Kontigu murni)
```

**Apache Arrow** mendefinisikan format memori biner standar terbuka (*in-memory columnar format*) yang dirancang khusus untuk CPU dan GPU modern:
1.  **Format Kolom Kontigu (*Contiguous Columnar Layout*)**: Data disimpan per kolom, bukan per baris. Operasi analitik seperti agregasi `SUM(transaksi_nilai)` hanya memuat data dari *buffer* kolom yang bersangkutan langsung ke *cache* CPU tanpa membaca kolom lain.
2.  **Representasi Null Tanpa Penanda Sentinal (*Null Bitmaps*)**: Arrow tidak menggunakan representasi *hacky* seperti nilai *floating-point* `NaN` untuk menandakan integer kosong. Arrow memisahkan status null ke dalam *validity bitmap* terkompresi (1 bit merepresentasikan status null sebuah baris).
3.  **Zero-Copy Interchange**: Berbagai bahasa pemrograman (Rust, C++, Go, Python, Java) dapat membaca *buffer* memori yang sama via penunjuk alamat pointer (*pointer sharing*) menggunakan Arrow C Data Interface tanpa operasi konversi atau penyalinan memori (*zero serialization overhead*).

**Polars** adalah mesin kueri OLAP berkecepatan tinggi yang dibangun di atas bahasa pemrograman Rust dengan fondasi Apache Arrow. Polars menghindari batasan CPython GIL secara penuh dengan memanfaatkan pustaka konkurensi berbasis *work-stealing* (Rayon) dan menerapkan optimasi kueri deklaratif melalui *Logical* dan *Physical Execution Plan*.

---

### 4. Why
Mengapa transisi dari ekosistem analitik lawas ke Apache Arrow dan Polars menjadi kebutuhan kritis rekayasa sistem data modern?

1.  **Eliminasi Overhead Memori Pandas (2x–10x RAM Inflasi)**:
    Pandas versi klasik umumnya membutuhkan RAM 5x hingga 10x dari ukuran dataset aktual di *disk*. File CSV 2GB sering kali memicu *Out Of Memory* (OOM) pada mesin dengan RAM 8GB–16GB karena konversi tipe data implisit dan fragmentasi memori. Polars mengonsumsi memori mendekati rasio 1:1 terhadap ukuran data terdekompresi berkat struktur *Arrow Array*.
2.  **Eksploitasi Penuh Arsitektur CPU Modern**:
    Pandas beroperasi secara *single-threaded* untuk sebagian besar operasinya karena terkunci oleh GIL. Polars secara otomatis membagi eksekusi analitik ke semua *core* CPU yang tersedia tanpa memerlukan konfigurasi manual seperti *multiprocessing pool*, serta mengeksekusi operasi menggunakan set instruksi vektor SIMD (AVX2/AVX-512).
3.  **Optimasi Kueri Kompilasi (*Lazy Evaluation*)**:
    Alih-alih mengeksekusi operasi secara instan (*eager execution*), Polars menyediakan antarmuka `LazyFrame`. Kompilator Polars memeriksa pohon ekspresi logika (*Logical Plan*) dan melakukan:
    *   *Predicate Pushdown*: Menyaring baris langsung pada layer pembacaan file (misal: hanya membaca blok Parquet yang memenuhi syarat `WHERE`).
    *   *Projection Pushdown*: Hanya memuat kolom-kolom yang secara eksplisit digunakan dalam kalkulasi ke memori kerja.

---

### 5. What
Komponen arsitektur inti dalam ekosistem Arrow dan Polars mencakup:

*   **Arrow Array & ChunkedArray**: Struktur data 1D fundamental yang memuat *contiguous buffer* data mentah, *offset buffer* (untuk data berukuran dinamis seperti string/binary), dan *validity bitmap* (untuk melacak nullability).
*   **Arrow Schema & Field**: Metadata penentu tipe data berbasis sistem tipe Arrow yang ketat (misal: `pa.int64()`, `pa.utf8()`, `pa.decimal128()`).
*   **RecordBatch**: Sekumpulan *Arrow Array* dengan panjang baris identik yang membentuk struktur tabel 2 dimensi. Merupakan unit atomik pemrosesan I/O pada Arrow.
*   **Polars Expr (Expression)**: Blok pembangun operasi fungsional di Polars. Bersifat *pure function*, lazily-evaluated, dan dapat diparalelkan secara bebas (misal: `pl.col("a").filter(pl.col("b") > 10).sum()`).
*   **Polars DataFrame & LazyFrame**:
    *   `DataFrame`: Representasi tabel dua dimensi *in-memory* yang dieksekusi secara instan (*eager*).
    *   `LazyFrame`: Rencana komputasi deklaratif yang menahan eksekusi hingga metode `.collect()` dipanggil, membuka ruang bagi kompilator kueri untuk mengoptimalkan rute eksekusi.
*   **Polars Streaming Engine**: Sub-sistem eksekusi yang memproses data dalam unit *batch* berukuran kecil (*chunks*) dari *disk*, memungkinkan pemrosesan dataset ratusan gigabyte pada sistem dengan RAM terbatas.

---

### 6. How
Alur kerja integrasi Apache Arrow dan siklus eksekusi Polars Lazy Engine berjalan melalui tahapan sistematis berikut:

```
[Parquet / CSV / Database / S3]
               │
               ▼  (I/O Scan via mmap)
   [Polars Query Optimizer]
         ├── 1. Predicate Pushdown (Filter data pada level file I/O)
         ├── 2. Projection Pushdown (Baca hanya kolom yang dibutuhkan)
         └── 3. Common Subexpression Elimination
               │
               ▼  (Generate Physical Plan)
    [Rayon Multi-Threaded Engine]
         ├── Core 0: Batch 0..N   (SIMD Vectorized Ops)
         ├── Core 1: Batch N..2N  (SIMD Vectorized Ops)
         └── Core M: Batch M..XM  (SIMD Vectorized Ops)
               │
               ▼  (Zero-Copy / Off-Heap Memory Buffers)
    [Apache Arrow RecordBatches]
               │
               ▼
[Materialized DataFrame / Inter-Process Zero-Copy Export]
```

1.  **Deklarasi Skema dan File Scan**: Pipeline menginisialisasi pembacaan sumber data via `pl.scan_parquet()` atau `pl.scan_csv()`. Pada fase ini, data belum dibaca ke RAM. Polars hanya membaca metadata *footer* file untuk mengekstrak skema dan statistik statistik per-blok (*row groups*).
2.  **Penyusunan Expression Graph**: Transformasi (filter, agregasi, mutasi, join) didaftarkan sebagai rangkaian ekspresi matematika berbasis `pl.col()`.
3.  **Kompilasi dan Optimasi Rencana**: Kompilator Polars menghasilkan graf kueri, memangkas kolom yang tidak terpakai dari I/O (*Projection Pushdown*), dan memindahkan filter seleksi sedekat mungkin ke sumber data (*Predicate Pushdown*).
4.  **Eksekusi Terparalelisasi**: Rust runtime mendistribusikan *RecordBatches* ke seluruh *core* CPU menggunakan Rayon thread-pool. Setiap *worker thread* memproses alokasi memori Arrow yang terisolasi secara *lock-free*.
5.  **Output atau Zero-Copy Handover**: Hasil kueri dapat diekspor langsung ke sistem lain (seperti PyTorch tensor, DuckDB, atau berkas Parquet) melalui implementasi protokol Python PyCapsule Arrow tanpa menduplikasi alokasi memori.

---

### 7. Analogy
Bayangkan sebuah perpustakaan nasional yang melayani analisis statistik kata pada 1.000.000 buku:

*   **Pendekatan Tradisional (Pandas / Row-Oriented)**:
    Setiap halaman buku dijilid dalam folder terpisah bersama dengan tebal sampul, indeks perpustakaan, dan catatan pustakawan (mirip `PyObject` wrapper). Jika Anda hanya butuh menghitung rata-rata tahun terbit semua buku, asisten perpustakaan harus mengambil seluruh tumpukan buku, membuka setiap lembar halaman dari buku ke-1 sampai buku ke-1.000.000, lalu mencatat tahun terbitnya satu demi satu. Meja kerja (RAM) penuh sesak dengan kertas-kertas yang tidak relevan.
*   **Pendekatan Apache Arrow & Polars (Columnar & Lazy)**:
    Perpustakaan merobek semua halaman sampul dan menyusun data ke dalam lajur khusus: semua judul buku disimpan dalam satu kontainer pipa panjang yang terhubung, semua tahun terbit dijejerkan secara rapat dalam pita magnetik kontigu (Arrow Columnar). Ketika Anda meminta analisis tahun terbit, sistem langsung mengirim instruksi ke lengan robotik (SIMD) untuk menarik pita tahun terbit saja. Pita judul tidak pernah disentuh atau dipindahkan ke meja kerja (*Projection Pushdown*).

---

### 8. Diagram
Struktur fisik alokasi memori pada Apache Arrow Array dan integrasi pipeline eksekusinya:

```
===================================================================================
                STRUKTUR INTERNAL APACHE ARROW STRING ARRAY
===================================================================================

Array Data: ["PROD_A", NULL, "PROD_B_EXT"]

1. Validity Bitmap Buffer (Menentukan status null, 1 bit per baris):
   ┌───┬───┬───┐
   │ 1 │ 0 │ 1 │   (Baris indeks 1 bernilai NULL)
   └───┴───┴───┘
     0   1   2

2. Offsets Buffer (Indeks posisi byte pada Values Buffer, int32):
   ┌───┬───┬───┬────┐
   │ 0 │ 6 │ 6 │ 16 │  (Panjang: idx[0]=6B, idx[1]=0B, idx[2]=10B)
   └───┴───┴───┴────┘
     0   1   2   3

3. Values Buffer (Kontigu Raw UTF-8 Bytes, tanpa pembungkus objek):
   ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
   │ P │ R │ O │ D │ _ │ A │ P │ R │ O │ D │ _ │ B │ _ │ E │ X │ T │
   └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
     0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15

===================================================================================
               POLARS LAZY EXECUTION ENGINE vs PANDAS MEMORY
===================================================================================

PANDAS (Eager Loading):
CSV File (Disk) ──> [Parse Entire File] ──> [Allocate Full RAM (OOM Risk)] ──> [Filter]

POLARS (Lazy Optimization):
CSV/Parquet File ──> [Scan Schema Only]
                           │
                           ▼
                  [Logical Query Plan]
                           │  (Optimization Pass: Pushdown Predicates)
                           ▼
                  [Optimized Plan]
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
      [Worker Thread 1]           [Worker Thread 2]      (Multi-threading)
      (Scan Chunk A & Filter)     (Scan Chunk B & Filter)
             │                           │
             └─────────────┬─────────────┘
                           ▼
                   [Arrow Result Table]
```

---

### 9. Simple Example
Kode demonstrasi alokasi manual Apache Arrow RecordBatch dan konversi *Zero-Copy* ke Polars DataFrame.

```python
import pyarrow as pa
import polars as pl

# 1. Alokasi Apache Arrow Array dengan Validity Bitmap eksplisit
item_names = pa.array(["Server-Alpha", None, "Edge-Gateway-01"], type=pa.string())
cpu_usage_pct = pa.array([84.5, 92.1, None], type=pa.float32())
active_connections = pa.array([1250, 0, 412], type=pa.int32())

# 2. Konstruksi Arrow Schema dengan metadata tipe ketat
schema = pa.schema([
    pa.field("hostname", pa.string(), nullable=True),
    pa.field("cpu_usage", pa.float32(), nullable=True),
    pa.field("connections", pa.int32(), nullable=False)
])

# 3. Bentuk RecordBatch (Representasi tabular columnar murni di memori)
record_batch = pa.RecordBatch.from_arrays(
    [item_names, cpu_usage_pct, active_connections],
    schema=schema
)

# 4. Zero-Copy transfer ke Polars DataFrame via PyCapsule Interface
polars_df = pl.from_arrow(record_batch)

# Cetak hasil dan tipe data
print("=== Polars DataFrame (Dibangun langsung dari Arrow Buffers) ===")
print(polars_df)
print("\n=== Polars Schema Information ===")
print(polars_df.schema)
```

---

### 10. Practical Example
Pipeline analitik industri: Memproses dataset log transaksi keuangan berskala besar (~5.000.000 baris) menggunakan Polars Lazy API, ekspresi analitik kompleks (*window functions*, *conditional updates*), inspeksi rencana optimasi kueri (*explain plan*), dan materialisasi memori terkelola.

```python
from __future__ import annotations

import os
import time
import tempfile
import polars as pl
import numpy as np

def generate_synthetic_transactions_parquet(file_path: str, n_rows: int = 5_000_000) -> None:
    """Membuat mock dataset Parquet transaksi finansial berukuran besar."""
    print(f"Generating {n_rows:,} records to {file_path}...")
    np.random.seed(42)
    
    # Batch chunking untuk meminimalkan alokasi memori saat generasi dummy data
    chunk_size = 1_000_000
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    for i in range(0, n_rows, chunk_size):
        current_chunk = min(chunk_size, n_rows - i)
        df_chunk = pl.DataFrame({
            "transaction_id": [f"TX-{j:010d}" for j in range(i, i + current_chunk)],
            "account_id": np.random.randint(1000, 50000, size=current_chunk, dtype=np.int32),
            "merchant_category": np.random.choice(["GROCERY", "ELECTRONICS", "TRAVEL", "GAMING", "UTILITY"], size=current_chunk),
            "amount_usd": np.random.exponential(scale=75.0, size=current_chunk).astype(np.float64),
            "is_flagged": np.random.choice([True, False], size=current_chunk, p=[0.01, 0.99]),
            "timestamp": pl.datetime_range(
                start=pl.datetime(2023, 1, 1),
                end=pl.datetime(2023, 12, 31, 23, 59, 59),
                interval="1s",
                eager=True
            ).sample(n=current_chunk, with_replacement=True)
        })
        
        mode = "write" if i == 0 else "append"
        if i == 0:
            df_chunk.write_parquet(file_path, compression="snappy")
        else:
            # Polars Parquet writer native append support via PyArrow/native logic
            existing = pl.read_parquet(file_path)
            pl.concat([existing, df_chunk]).write_parquet(file_path, compression="snappy")

def run_high_performance_pipeline(source_path: str) -> pl.DataFrame:
    """Mengeksekusi pipeline optimasi analitik menggunakan Polars Lazy Engine."""
    print("\n--- Menginisialisasi Polars LazyFrame Plan ---")
    
    # Inisialisasi LazyFrame: TIDAK ADA pembacaan I/O payload data di tahap ini
    lazy_plan = pl.scan_parquet(source_path)
    
    # Susun ekspresi analitik kompleks
    analytics_query = (
        lazy_plan
        # 1. PREDICATE: Filter awal untuk pushdown ke Parquet reader
        .filter(
            (pl.col("amount_usd") > 10.0) & 
            (pl.col("merchant_category").is_in(["ELECTRONICS", "TRAVEL"]))
        )
        # 2. PROJECTION: Hitung fitur agregat dan window functions
        .with_columns([
            # Menghitung Z-Score amount_usd per account_id via Window Expression
            (
                (pl.col("amount_usd") - pl.col("amount_usd").mean().over("account_id")) /
                (pl.col("amount_usd").std().over("account_id") + 1e-6)
            ).alias("account_amount_zscore"),
            
            # Ekstraksi komponen waktu
            pl.col("timestamp").dt.month().alias("tx_month"),
            
            # Klasifikasi risiko transaksi menggunakan ekspresi when-then-otherwise
            pl.when(pl.col("amount_usd") > 2500.0)
              .then(pl.lit("CRITICAL"))
              .when(pl.col("is_flagged"))
              .then(pl.lit("HIGH"))
              .otherwise(pl.lit("NORMAL"))
              .alias("risk_tier")
        ])
        # 3. AGREGASI TINGKAT LANJUT
        .group_by(["account_id", "merchant_category"])
        .agg([
            pl.len().alias("total_tx_count"),
            pl.col("amount_usd").sum().alias("total_volume_usd"),
            pl.col("amount_usd").max().alias("max_single_tx"),
            (pl.col("risk_tier") == "CRITICAL").sum().alias("critical_risk_count")
        ])
        # 4. FILTER PASCA-AGREGASI
        .filter(pl.col("total_tx_count") >= 3)
        .sort(by="total_volume_usd", descending=True)
    )
    
    # Inspeksi Rencana Eksekusi Teroptimasi (Execution Graph Optimization)
    print("\n=== Optimized Logical Plan (Explain) ===")
    print(analytics_query.explain(optimized=True))
    
    # Eksekusi kalkulasi secara paralel menggunakan Rayon engine
    start_time = time.perf_counter()
    result_dataframe: pl.DataFrame = analytics_query.collect(streaming=True)
    duration = time.perf_counter() - start_time
    
    print(f"\nPipeline selesai dalam: {duration:.4f} detik")
    return result_dataframe

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp_dir:
        parquet_file = os.path.join(tmp_dir, "transactions_large.parquet")
        
        # 1. Generate 2 juta baris data untuk demonstrasi
        generate_synthetic_transactions_parquet(parquet_file, n_rows=2_000_000)
        
        # 2. Jalankan komputasi berkecepatan tinggi
        final_result = run_high_performance_pipeline(parquet_file)
        
        print("\n=== Top 5 Agregasi Risiko Akun ===")
        print(final_result.head(5))
```

---

### 11. Real World Example
**Skenario Kasus: Platform Periklanan Digital Real-Time (AdTech Clickstream Attribution)**

Sebuah perusahaan media digital global memproses 120 juta metrik tayangan iklan (*ad impressions*) dan klik (*clicks*) setiap jam dari log Amazon S3. Arsitektur lama berbasis AWS Lambda yang menjalankan **Pandas** mengalami kendala sistemik:
1.  **Kegagalan OOM Sistemik**: *Worker node* dengan RAM 32 GB kehabisan memori saat mencoba menggabungkan (*join*) file log *hourly* sebesar 6 GB (CSV mentah), karena alokasi memori internal Pandas melonjak melebihi 35 GB.
2.  **Cost Overrun**: Perusahaan terpaksa menggunakan instans EC2 memori tinggi (`r5.4xlarge` seharga \$1.008/jam per worker) hanya untuk menangani *overhead* memori Pandas yang tidak efisien.
3.  **Waktu Siklus Lambat**: Proses kueri atribusi membutuhkan waktu 24 menit per *batch*, menunda sinkronisasi metrik konversi ke *dashboard* pelanggan.

**Penyelesaian Arsitektural Menggunakan Polars dan Arrow**:
*   Pipeline diganti menggunakan container Python berbasis `polars` dengan mesin *Streaming Execution*.
*   Log harian diubah menjadi format Parquet berbasis skema **Apache Arrow**.
*   Dengan *Predicate Pushdown* dan paralelisasi CPU Rust, memori puncak (*peak memory*) terpangkas dari **38 GB menjadi 3.2 GB** (penghematan 91.5%).
*   Waktu komputasi terpangkas dari **24 menit menjadi 54 detik**.
*   Infrastruktur diturunkan ke kelas komputasi yang lebih hemat (`c6i.2xlarge`), mengurangi biaya operasional *compute cluster* AWS bulanan dari \$45.000 menjadi \$4.200 per bulan.

---

### 12. Trade-offs

| Parameter | Arsitektur Tradisional (Pandas / NumPy v1) | Arsitektur Arrow-Native (Polars Engine) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Eager execution secara default (evaluasi instan baris-demi-baris). | Pilihan Eager dan Lazy Execution (optimasi pohon kueri sebelum runtime). |
| **Utilisasi Hardware** | Terbatas oleh Python GIL (Single-threaded pada operasi umum). | Multi-threaded native via Rust (100% pemanfaatan CPU Cores + SIMD). |
| **Footprint Memori** | Tinggi (Overhead `PyObject`, fragmentasi pointer, inflasi 5x–10x). | Minimal (Format data biner kontigu terkompresi, rasio mendekati 1:1). |
| **Ekosistem & Kompatibilitas**| Sangat matang; integrasi *native* dengan hampir semua modul *Machine Learning* lawas. | Membutuhkan jembatan PyCapsule/NumPy Array untuk beberapa pustaka warisan (Scikit-Learn/SciPy). |
| **Kurva Pembelajaran** | Familiar bagi analis data berbasis Excel/SQL dasar; sintaks longgar. | Memerlukan disiplin tinggi dalam pemahaman tipe data, skema ketat, dan paradigma ekspresi. |
| **Biaya Komputasi (Cloud)**| Tinggi; membutuhkan instans *High-Memory* (AWS seri `r` atau `x`). | Rendah; optimal pada instans *Compute-Optimized* biasa (AWS seri `c`). |

---

### 13. When To Use
Gunakan arsitektur Apache Arrow dan Polars ketika:
*   Dataset Anda berukuran antara **1 GB hingga 250 GB** pada satu mesin fisik (*single node*), di mana Pandas mulai mengalami OOM namun penggunaan Spark/Hadoop terlalu berlebihan (*overkill* secara latensi dan biaya).
*   Pipeline data Anda membaca data langsung dari format kolom modern seperti **Apache Parquet**, **Feather**, atau **IPC Stream**.
*   Aplikasi membutuhkan interoperabilitas data berkecepatan tinggi antar berbagai bahasa (misal: mengambil data di Rust/C++, menganalisis di Python, lalu melatih model di PyTorch) menggunakan prinsip *Zero-Copy*.
*   Beban kerja melibatkan transformasi analitik kompleks: Window Functions, Rolling Aggregations, Group-By berskala besar, dan penyaringan logika multi-kondisi.

---

### 14. When NOT To Use
Hindari atau tangguhkan adopsi Arrow/Polars jika:
*   Dataset Anda berukuran **Multi-Terabyte (> 1 TB)** yang didistribusikan secara fisik di ratusan server (Gunakan komputasi terdistribusi sejati seperti Apache Spark, Trino, atau Ray).
*   Anda membangun aplikasi OLTP (*Online Transaction Processing*) mikro yang melakukan mutasi baris individual secara konstan (`INSERT INTO ... VALUES (...)` satu baris per detik). Mesin berbasis Arrow dioptimalkan untuk analitik *batch* (OLAP), bukan manipulasi transaksional baris tunggal.
*   Basis kode Anda memiliki dependensi mutlak pada pustaka warisan yang hanya menerima referensi eksplisit `pandas.core.frame.DataFrame` dan memanipulasi *internal state* berbasis pointer Pandas index secara non-standar.

---

### 15. Common Mistakes
1.  **Memanggil `.collect()` Terlalu Dini pada LazyFrame**:
    Memanggil `.collect()` di tengah-tengah rantai ekspresi memaksa Polars melakukan materialisasi data instan ke RAM, membatalkan semua potensi *Predicate/Projection Pushdown* yang seharusnya dilakukan pada tahapan berikutnya.
2.  **Melakukan Iterasi Baris Manual (`for row in df.iter_rows()`)**:
    Iterasi baris memaksa Rust mengekstrak struktur biner Arrow kembali menjadi objek Python terpisah satu demi satu. Hal ini membunuh keunggulan performa hingga 100x lebih lambat. Gunakan ekspresi vektor Polars (`pl.when().then()`, `.map_batches()`, atau fungsi bawaan).
3.  **Konversi Balik ke Pandas Tanpa Apache Arrow Backend**:
    Mengeksekusi `df.to_pandas()` tanpa argumen akan menginisialisasi konversi ke format NumPy lama, menduplikasi seluruh alokasi RAM dan memicu OOM seketika. Jika integrasi Pandas tak terhindarkan, gunakan `df.to_pandas(use_pyarrow_extension_array=True)`.
4.  **Mengabaikan Ketidaksamaan Skema (*Schema Drift*)**:
    Arrow menuntut integritas tipe data yang kaku. Kolom yang memiliki tipe campuran (misal: angka dan string di kolom yang sama) akan menyebabkan kegagalan parse (*panic/error*), berbeda dengan Pandas yang secara diam-diam mengubahnya menjadi tipe lambat `object`.

---

### 16. Best Practices (Production Checklist)
Gunakan daftar periksa teknis ini sebelum merilis pipeline Polars/Arrow ke tahap produksi:

*   [ ] **Inisialisasi Lazy**: Selalu gunakan `pl.scan_parquet()` / `pl.scan_csv()` alih-alih `read_*` saat memproses berkas eksternal.
*   [ ] **Validasi Execution Plan**: Eksekusi perintah `print(lazy_df.explain())` dan pastikan filter Anda muncul di blok terbawah (*PUSHED DOWN PREDICATE*) dari rencana eksekusi.
*   [ ] **Aktifkan Mode Streaming**: Gunakan parameter `lazy_df.collect(streaming=True)` untuk memproses dataset yang berpotensi melampaui sisa RAM sistem (*Out-Of-Core Processing*).
*   [ ] **Tipe Data Optimal**: Hindari alokasi berlebih. Konversi tipe default `int64` atau `float64` ke tipe yang lebih efisien jika rentang data memungkinkan (misal: `pl.Int32`, `pl.UInt16`, `pl.Categorical`).
*   [ ] **Bebaskan Alokasi Manual**: Ketika mengintegrasikan PyArrow Table, lepaskan referensi variabel lama dan panggil `del table` jika sistem mendekati batas memori kontainer untuk memicu pembersihan *off-heap buffers*.
*   [ ] **Limit Thread Overhead**: Pada lingkungan kontainer (misal: Kubernetes Pods dengan batasan CPU limits), setel variabel lingkungan `POLARS_MAX_THREADS` agar sesuai dengan alokasi vCPU kontainer guna mencegah *context-switching thrashing*.

---

### 17. Troubleshooting
Panduan mitigasi kesalahan umum di tingkat produksi:

*   **Error: `ComputeError: could not append... schema mismatch`**:
    *   *Penyebab*: Operasi penggabungan (`pl.concat`) mendeteksi bahwa tipe kolom pada satu *batch* tidak sesuai dengan *batch* lainnya (misal: `Int64` vs `Float64`).
    *   *Solusi*: Terapkan *casting* eksplisit pada ekspresi kueri Lazy: `.with_columns(pl.col("target_col").cast(pl.Float64))`.
*   **Error: `Polars panicked: OutOfMemory`**:
    *   *Penyebab*: Operasi *in-memory join* atau agregasi kardinalitas tinggi melampaui RAM fisik saat materialisasi non-streaming.
    *   *Solusi*: 
        1. Aktifkan *streaming engine*: `.collect(streaming=True)`.
        2. Periksa apakah operasi `.join()` menghasilkan *Cartesian Product* akibat *join key* yang tidak unik.
*   **Performa Lambat pada Data String**:
    *   *Penyebab*: String berulang berskala jutaan baris dialokasikan sebagai *Utf8 String Buffer* biasa, memakan ratusan megabyte alokasi offset byte.
    *   *Solusi*: Konversikan tipe kolom string kategorikal berulang menggunakan `.cast(pl.Categorical)`.

---

### 18. Exercise
**Instruksi Laboratorium Praktis:**
Diberikan serangkaian log server web mentah dalam format CSV virtual dengan struktur kolom: `[ip_address (str), response_code (int), response_time_ms (float), endpoint (str)]`.

Tulis skrip Python menggunakan Polars Lazy API untuk:
1.  Menyaring hanya respons HTTP dengan kode status `500` ke atas (server error).
2.  Menghitung *95th percentile* (`quantile(0.95)`) dari `response_time_ms` per masing-masing `endpoint`.
3.  Menghitung total kemunculan error per *endpoint*.
4.  Menyimpan hasil ke dalam format Parquet dengan kompresi `ZSTD`.

*Format Template*:
```python
import polars as pl

def process_web_logs(csv_path: str, output_parquet_path: str) -> None:
    # Tulis implementasi LazyFrame pipeline Anda di sini
    pass
```

---

### 19. Challenge
**Tantangan Arsitektur: Zero-Copy Inter-Process Inference Engine**

Bangun sebuah modul data interchange performa tinggi dengan spesifikasi teknis berikut:
1.  Gunakan pustaka `pyarrow` untuk membuat *shared memory IPC buffer* (`pyarrow.ipc.RecordBatchFileWriter` menggunakan `pa.BufferOutputStream` atau memory-mapped file).
2.  Simulasikan data sensor *high-frequency* sebesar **10.000.000 baris float64**.
3.  Baca *shared memory buffer* tersebut secara bersamaan dari proses Polars terpisah tanpa melakukan duplikasi alokasi byte data di sistem (*Zero-Copy Memory Verification* via pengecekan alamat pointer data menggunakan `ctypes` atau inspeksi `arrow buffer pointer`).
4.  Terapkan kalkulasi *Exponential Moving Average (EMA)* pada deret waktu tersebut menggunakan Polars Lazy Expression dan kembalikan array prediksi akhir tanpa menyentuh format DataFrame Pandas sedikit pun.
5.  Ukur penggunaan memori puncak menggunakan modul `tracemalloc` untuk membuktikan tidak ada penggandaan memori selama proses berlangsung.

---

### 20. Summary
*   **Apache Arrow** merevolusi komputasi data in-memory modern melalui standarisasi format memori *columnar* kontigu yang kompatibel di berbagai bahasa, mengeliminasi biaya serialisasi via *Zero-Copy*, dan memisahkan status *nullability* menggunakan *validity bitmaps*.
*   **Polars Engine** mengeksploitasi format Arrow secara maksimal dengan mengombinasikan optimasi kueri deklaratif tingkat lanjut (*LazyFrame Pushdowns*), eksekusi paralel bebas GIL berbasis Rust Rayon, komputasi SIMD hardware, serta mesin *streaming* untuk dataset *out-of-core*.
*   Peralihan arsitektural dari tumpukan teknologi lawas (Pandas/NumPy v1) ke Arrow/Polars bukan sekadar peningkatan sintaksis, melainkan transformasi struktural dalam efisiensi hardware—menghasilkan throughput pengolahan data analitik yang 10x hingga 100x lebih cepat dengan penurunan konsumsi RAM hingga 90% pada skala industri.