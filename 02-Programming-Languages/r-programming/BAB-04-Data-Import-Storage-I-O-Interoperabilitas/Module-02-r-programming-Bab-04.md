# Bab 04: Data Import, Storage, I/O & Interoperabilitas
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Out-of-Core Data Processing**: Menangani dataset berukuran multi-gigabyte hingga terabyte melebihi kapasitas RAM host menggunakan Apache Arrow IPC, DuckDB, dan ALTREP (*Alternative Representations*).
- **Membangun Pipeline Interoperabilitas Polyglot Zero-Copy**: Mengintegrasikan R runtime dengan ekosistem Python (`reticulate`) dan C++ (`cpp11`/`Rcpp`) menggunakan *Arrow C Data Interface* untuk eliminasi *serialization overhead*.
- **Merancang Enterprise Data Lake I/O Layer**: Mengimplementasikan *partitioned columnar storage* (Parquet/ZSTD) yang terintegrasi secara aman dengan *Cloud Object Storage* (AWS S3/GCS/MinIO) dengan enkripsi *in-transit/at-rest* dan *schema evolution handling*.
- **Mengoptimalkan Resiliensi & Pooling Database Relasional**: Mengonfigurasi arsitektur *production-grade database connectivity* berbasis DBI/pool dengan penanganan koneksi transaksional ACID, failover, dan observabilitas metrik I/O.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Arsitektur Internal R**: Pemahaman struktur `SEXP` (*S-Expression pointer*), *garbage collection* (R GC mark-and-sweep), dan *call-by-value semantics*.
- **Sistem Operasi & Storage I/O**: Konsep POSIX file descriptor, `mmap` (*memory-mapped files*), *virtual memory paging*, dan *page fault*.
- **Format Data Kolom**: Prinsip kerja data columnar (*row-oriented* vs *columnar layout*, Dictionary Encoding, Run-Length Encoding).
- **Tooling**: R versi $\ge 4.2.0$, Apache Arrow C++ engine runtime, DuckDB CLI/engine, serta compiler C++ (GCC $\ge 11$ atau Clang $\ge 13$).

---

### 3. Concept & Internal Architecture

#### 3.1 ALTREP (Alternative Representations) & Zero-Copy Memory Mapping
Dalam arsitektur komputasi tradisional R (< 3.5.0), setiap pembacaan data disk ke memori mengalokasikan vektor native R secara penuh di RAM. Jika file Parquet berukuran 10 GB dimuat, engine membutuhkan alokasi memori heap sebesar 10 GB ditambah overhead representasi string jika terdapat data karakter.

Mulai R 3.5.0, subsistem **ALTREP** merevolusi arsitektur I/O. ALTREP memungkinkan sebuah objek R bertindak sebagai pointer virtual ke payload data eksternal tanpa langsung melakukan alokasi dan duplikasi memori secara instan (*lazy materialization*).

```
   Traditional R Vector:
   +-------------------+-----------------------------------------+
   | SEXP Header (40B) | Continuous In-Memory Array (Payload)   |
   +-------------------+-----------------------------------------+
                                      ^
                                      | Deep Copy from Disk
                                 [ Disk File ]

   ALTREP Vector Architecture:
   +-------------------+-----------------------+
   | SEXP Header (40B) | ALTREP Class Pointers |
   +-------------------+-----------------------+
            |                     |
            v                     v
   [ Custom Methods ]      [ Data Pointer: mmap / Arrow Buffer ]
   - Length()              (Data tetap berada di Page Cache OS
   - Dataptr()              atau shared memory; dimuat hanya saat diakses)
```

Ketika Apache Arrow atau DuckDB membaca file Parquet atau Feather, keduanya memanfaatkan `mmap(2)` POSIX call. Engine memetakan blok alamat disk langsung ke *virtual address space* proses R. R engine tidak memindahkan byte dari disk ke heap sampai operasi matematika atau subsetting spesifik dijalankan.

#### 3.2 Apache Arrow C Data Interface
Interoperabilitas tradisional antar-bahasa pemrograman (misal: R ke Python melalui `reticulate`, atau R ke C++ melalui serialization JSON/Protocol Buffers) memicu penalti performa masif akibat siklus:

$$\text{R Object} \xrightarrow{\text{Serialize}} \text{Intermediate Buffer} \xrightarrow{\text{Socket/IPC}} \text{Target Runtime} \xrightarrow{\text{Deserialize}} \text{Target Object}$$

**Arrow C Data Interface** mengeliminasi overhead ini menjadi $O(1)$ kompleksitas transfer dengan menyediakan dua struktur C murni standar ABI (*Application Binary Interface*):
- `ArrowSchema`: Mendeskripsikan layout metadata tipe data (logical type, format string, metadata dictionary).
- `ArrowArray`: Menyimpan metadata buffer data, *null bitmaps*, panjang array, serta pointer 64-bit mentah (`const void** buffers`) yang langsung mengarah ke alokasi memori fisik array.

R dan Python/C++ cukup bertukar pointer ke `ArrowArray` dan `ArrowSchema`. Tidak ada konversi representasi, tidak ada penyalinan data (*zero-copy memory handoff*).

#### 3.3 Vectorized Execution Engine: DuckDB & Pushdown Predicates
DuckDB mengintegrasikan model eksekusi *Vectorized Relational Query Engine* (Morsel-Driven Parallelism). Alih-alih memproses satu baris data (*tuple-at-a-time* seperti model Volcano tradisional) atau seluruh dataset (*vector-at-a-time* yang menuntut RAM raksasa), DuckDB memproses blok data kolom dalam *morsels* vektor berukuran 1024 atau 2048 nilai yang pas masuk ke cache CPU L1/L2.

Fitur kritis dalam data engine modern adalah **Predicate & Projection Pushdown**:
1. **Projection Pushdown**: Hanya kolom yang terdaftar dalam klausa `SELECT` yang dibaca dari disk. Jika Parquet memiliki 200 kolom dan query membutuhkan 3 kolom, maka I/O disk terpangkas 98.5%.
2. **Predicate Pushdown**: Klausa `WHERE` dievaluasi langsung pada metadata Parquet (*Row Group statistics: min/max/null count*) sebelum membaca payload. Jika baris target berada di luar batas `[min, max]`, seluruh *Row Group* (jutaan baris) dilewati (*skipped*) tanpa I/O fisik disk.

---

### 4. Why & What

| Dimensi | Pendekatan Enterprise Modern | Pendekatan Konvensional (Naive R) |
| :--- | :--- | :--- |
| **I/O Engine** | Chunked/mmap via Arrow IPC & DuckDB | `read.csv()`, `readRDS()`, `write.csv()` |
| **Batas Memori** | Mengolah dataset $10\times$ lebih besar dari RAM (Out-of-Core) | Dibatasi secara kaku oleh sisa alokasi RAM fisik |
| **Interoperabilitas Polyglot** | Arrow C Data Interface (Zero-Copy) | Disk dump (CSV/JSON) atau IPC base socket |
| **Penyimpanan Objek** | Snappy/ZSTD Partitioned Parquet | Monolithic Flat Files / Binary RDS Blob |
| **Database Access** | Thread-safe Connection Pooling (`pool` + `DBI`) | Singleton Ad-hoc `dbConnect()` per fungsi |
| **Skalabilitas Concurrency** | Non-blocking streaming and pushdown execution | Blocking full table scan, CPU core tunggal |

- **Why**: Dataset modern bergerak dari megabyte ke petabyte. Format monolitik (`.csv`, `.RData`) menimbulkan fragmentasi alokasi RAM proses R, meningkatkan frekuensi R GC *stop-the-world*, dan menimbulkan *I/O bottleneck* pada storage disk.
- **What**: Arsitektur I/O modern R berbasis pemisahan *compute* dan *storage*, memanfaatkan memory layout terstandarisasi industri (Apache Arrow), kompresi efisien (Parquet/Zstandard), dan query engine tertanam (*embedded vectorized engine*) seperti DuckDB.

---

### 5. How (Workflow Detail)

Arsitektur siklus data I/O enterprise dari sumber mentah hingga analitik terdistribusi mengikuti alur terarah:

```
[ Data Source: S3 / Lakehouse / Event Stream ]
                     │
                     ▼
[ Transport: Arrow S3 FileSystem / Streaming IPC ]
                     │
                     ├───────────────────────────────┐
                     ▼                               ▼
     [ Predicate & Projection Pushdown ]     [ Schema Enforcement ]
                     │                               │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
                      [ In-Memory Zero-Copy Layer ]
                       (DuckDB / Apache Arrow mmap)
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
         [ Interop via C Data Interface ]     [ Push to R ALTREP ]
         - Python (reticulate: PyTorch/Polars) - Native R dplyr verbs
         - C++ (cpp11 SIMD computation)        - Microbenchmark & model
                                     │
                                     ▼
           [ Export Layer: ACID Parquet Partitioning ]
                      (Target Data Warehouse / S3)
```

1. **Inisialisasi Filesystem Abstraction**: Mengonfigurasi layer konektivitas terisolasi (misal: S3 / MinIO) via `arrow::s3_bucket()` dengan konfigurasi kredensial non-eksplisit.
2. **Schema Definition**: Mendeklarasikan tipe data ketat (*strict schema*) menggunakan `arrow::schema()` untuk mencegah inferensi tipe otomatis (*type guessing*) yang boros memori dan rentan *coercion errors*.
3. **Execution Plan Construction**: Menggunakan fungsi lazy pipeline (`arrow::open_dataset()` atau DuckDB relation API) untuk merakit DAG (*Directed Acyclic Graph*) query execution.
4. **Pushdown Optimizations**: Engine mengeksekusi *metadata scanning* untuk mengeliminasi partition directory dan row group yang tidak relevan.
5. **Consumption via ALTREP / Interop**: Engine mengalirkan data ke R runtime sebagai chunk vektor atau membagi pointer Arrow ke runtime Python/C++.
6. **Persistence**: Menulis hasil akhir kembali ke disk/lakehouse dengan partisi berbasis Hive (*Hive-style partitioning*) dengan kompresi Zstandard (ZSTD) rasio tinggi.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Modern vs Perpustakaan Kuno
- **Pendekatan Naive (Perpustakaan Kuno)**: Anda ingin merangkum Bab 3 Buku X. Pustakawan menyalin seluruh isi buku 1000 halaman ke kertas baru dengan tulisan tangan, membawanya ke meja Anda, baru Anda membaca Bab 3. (Boros kertas/RAM, lambat/High I/O latency).
- **Pendekatan ALTREP & Vectorized Columnar (Perpustakaan Modern)**: Pustakawan memberikan katalog berindeks (*Metadata*). Anda hanya membuka lemari pada laci spesifik Bab 3, membaca langsung dari lembar aslinya tanpa memfotokopi (*Zero-copy*), dan hanya membaca kolom kata yang Anda cari (*Columnar pushdown*).

#### Diagram Arsitektur Interoperabilitas R-Arrow-DuckDB-Python

```
+---------------------------------------------------------------------------------+
|                                HOST OPERATING SYSTEM                            |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   |                       Unified Arrow Shared Memory                       |   |
|   |                 (Arrow C Data Interface: ArrowArray / Schema)           |   |
|   +-------------------------------------------------------------------------+   |
|         ^                               ^                         ^             |
|         | Zero-Copy Pointer             | Zero-Copy Pointer       | Zero-Copy   |
|         v                               v                         v Pointer     |
|   +---------------+             +---------------+         +-----------------+   |
|   |   R Runtime   |             | Python Runtime|         |  DuckDB Engine  |   |
|   |   (ALTREP)    |             |  (reticulate) |         |  (Vectorized)   |   |
|   +---------------+             +---------------+         +-----------------+   |
|         ^                                                         ^             |
|         |                  Scan Pushdown (Filter / Project)       |             |
|         +---------------------------------------------------------+             |
|                                         ^                                       |
|                                         | mmap / Vectorized I/O                 |
|                                         v                                       |
|               +---------------------------------------------------+             |
|               | Storage Layer (Local Parquet / S3 Hive Partition) |             |
|               +---------------------------------------------------+             |
+---------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Memory Mapping via Arrow Dataset
Contoh dasar demonstrasi out-of-core: Membuka dataset multi-file tanpa membebani RAM R.

```r
library(arrow, quietly = TRUE)
library(dplyr, quietly = TRUE)

# Buat dataset temporary tabular berukuran representatif
tmp_dir <- tempfile(pattern = "arrow_demo_")
dir.create(tmp_dir)
on.exit(unlink(tmp_dir, recursive = TRUE))

df_mock <- data.frame(
  id = 1:1e6,
  kategori = sample(c("ALPHA", "BETA", "GAMMA"), 1e6, replace = TRUE),
  nilai = rnorm(1e6)
)

# Tulis dalam format partitioned parquet
write_dataset(
  dataset = df_mock,
  path = tmp_dir,
  format = "parquet",
  partitioning = "kategori",
  compression = "snappy"
)

# Buka dataset secara lazily (RAM footprint mendekati 0 byte)
ds <- open_dataset(tmp_dir)

# Query dengan pushdown predicates
hasil <- ds %>%
  filter(kategori == "ALPHA", nilai > 2.0) %>%
  select(id, nilai) %>%
  collect() # Hanya baris yang lolos filter yang ditarik ke memory heap R

print(head(hasil))
print(lobstr::obj_size(hasil))
```

#### 7.2 Practical Example: Enterprise Multi-Tier I/O Engine
Implementasi produksi yang mencakup:
1. Pool koneksi database PostgreSQL yang thread-safe dengan `pool`.
2. Pushdown query stream ke DuckDB.
3. Serialisasi analitik terkompresi Parquet ke S3-compliant target.
4. Python zero-copy data handoff via Arrow C Data Interface.

```r
suppressPackageStartupMessages({
  library(DBI)
  library(duckdb)
  library(arrow)
  library(dplyr)
  library(reticulate)
})

# ------------------------------------------------------------------------------
# 1. Thread-Safe Connection Management & DuckDB In-Memory Integration
# ------------------------------------------------------------------------------
con <- dbConnect(duckdb::duckdb(), dbdir = ":memory:")
on.exit(dbDisconnect(con, shutdown = TRUE), add = TRUE)

# Konfigurasi Thread & Memory Limit Engine DuckDB untuk Skala Produksi
dbExecute(con, "SET threads TO 4;")
dbExecute(con, "SET max_memory TO '4GB';")

# ------------------------------------------------------------------------------
# 2. Strict Schema Definition (Arrow Schema)
# ------------------------------------------------------------------------------
tx_schema <- schema(
  transaction_id = int64(),
  account_id     = utf8(),
  amount         = float64(),
  timestamp      = timestamp(unit = "us", timezone = "UTC"),
  status         = utf8()
)

# Menghasilkan Mock Data dalam Storage Parquet Terkompresi Zstandard
lake_path <- file.path(tempdir(), "financial_lake")
dir.create(lake_path, showWarnings = FALSE)
on.exit(unlink(lake_path, recursive = TRUE), add = TRUE)

mock_data <- tibble::tibble(
  transaction_id = 100001:101000,
  account_id = paste0("ACC-", sample(100:999, 1000, replace = TRUE)),
  amount = runif(1000, 10.0, 50000.0),
  timestamp = as.POSIXct("2024-01-01 00:00:00", tz = "UTC") + 1:1000,
  status = sample(c("COMPLETED", "FAILED", "PENDING"), 1000, replace = TRUE)
)

write_parquet(
  x = mock_data,
  sink = file.path(lake_path, "tx_2024_01.parquet"),
  compression = "zstd",
  compression_level = 7
)

# ------------------------------------------------------------------------------
# 3. Vectorized Pushdown via DuckDB Virtual Table (Zero-Copy Link)
# ------------------------------------------------------------------------------
# Mendaftarkan direktori dataset Parquet langsung ke dalam DuckDB catalog
duckdb::duckdb_register_arrow(con, "lake_transactions", open_dataset(lake_path, schema = tx_schema))

# Eksekusi Query menggunakan Pushdown Aggregation
sql_query <- "
  SELECT 
    account_id,
    COUNT(transaction_id) AS total_tx,
    ROUND(SUM(amount), 2) AS total_volume,
    ROUND(AVG(amount), 2) AS avg_ticket_size
  FROM lake_transactions
  WHERE status = 'COMPLETED'
  GROUP BY account_id
  HAVING SUM(amount) > 25000
  ORDER BY total_volume DESC;
"

res_arrow_table <- dbGetQuery(con, sql_query, arrow = TRUE)

# ------------------------------------------------------------------------------
# 4. Zero-Copy Polyglot Hand-off ke Python via Arrow C Data Interface
# ------------------------------------------------------------------------------
py_run_string("
import pyarrow as pa

def analyze_records(arrow_table):
    # Verifikasi zero-copy transfer tanpa memory overhead
    num_rows = arrow_table.num_rows
    schema_names = arrow_table.column_names
    total_acc = len(arrow_table['account_id'].unique())
    return f'Python processing: {num_rows} records successfully processed for {total_acc} unique high-value accounts.'
")

# Mengonversi Arrow Table R ke Pointer PyArrow Table secara Zero-Copy
py_table <- reticulate::r_to_py(res_arrow_table)
py_result <- py$analyze_records(py_table)
message(py_result)

# Inspeksi Struktur Metadata Hasil
print(res_arrow_table$schema)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sistem Algorithmic Trading pada Multi-Asset Hedge Fund menerima data pergerakan orderbook (*Level 2 Tick Data*) dengan volume harian 300 juta baris (~35 GB Parquet terkompresi per hari). Sistem analitik risiko berbasis R perlu menghitung agregasi *Volume-Weighted Average Price* (VWAP), volatilitas terealisasi (*Realized Volatility*), dan mendeteksi anomali *latency slippage* lintas broker dalam rentang 30 hari data historis (~1 Terabyte). Server analitik memiliki spesifikasi: 64 Core vCPU, 128 GB RAM. Memuat seluruh data secara in-memory akan menyebabkan *Out-Of-Memory (OOM) Crash*.

#### Solusi Arsitektur Produksi:
Penerapan arsitektur pipeline terdistribusi modular:
1. **Penyimpanan**: Hive-partitioned S3 storage (`/year=YYYY/month=MM/broker=XYZ/*.parquet`) dengan dictionary encoding untuk kolom string (`broker`, `symbol`, `exchange`) dan Zstandard level 5.
2. **Execution Engine**: DuckDB embedded engine dieksekusi dari R, mengarahkan scan langsung ke Parquet filesystem dengan multi-threading (64 core).
3. **Optimasi Buffer**: Memanfaatkan streaming batch chunking via `arrow::RecordBatchReader` untuk pipeline pemodelan machine learning di Python.

```r
library(arrow)
library(duckdb)
library(DBI)

setup_tick_analytics_pipeline <- function(lake_root_uri) {
  # 1. Konfigurasi Client Arrow S3
  # Arrow mendeteksi kredensial dari standard AWS env vars (AWS_ACCESS_KEY_ID, dsb)
  bucket <- open_dataset(
    sources = lake_root_uri,
    format = "parquet",
    partitioning = c("year", "month", "broker")
  )
  
  # 2. Inisialisasi In-Process Embedded Engine
  con <- dbConnect(duckdb::duckdb())
  dbExecute(con, "PRAGMA threads=64;")
  dbExecute(con, "PRAGMA memory_limit='96GB';")
  
  # Mendaftarkan dataset arrow sebagai relational view
  duckdb_register_arrow(con, "ticks_view", bucket)
  
  return(con)
}

calculate_daily_vwap <- function(con, target_symbol, start_ts, end_ts) {
  # 3. Eksekusi Predicate Pushdown di Level Storage Parquet
  query <- sprintf("
    SELECT 
      CAST(timestamp AS DATE) AS trade_date,
      broker,
      symbol,
      ROUND(SUM(price * volume) / SUM(volume), 5) AS vwap,
      SUM(volume) AS cumulative_volume,
      SQRT(AVG(price * price) - AVG(price) * AVG(price)) AS realized_volatility
    FROM ticks_view
    WHERE symbol = '%s'
      AND timestamp >= '%s'::TIMESTAMP
      AND timestamp <= '%s'::TIMESTAMP
    GROUP BY 1, 2, 3
    ORDER BY trade_date ASC, cumulative_volume DESC;
  ", target_symbol, start_ts, end_ts)
  
  # Fetch data stream langsung ke R Arrow Table
  vwap_arrow <- dbGetQuery(con, query, arrow = TRUE)
  return(as.data.frame(vwap_arrow))
}

# Contoh eksekusi (Simulasi antarmuka produksi)
# con <- setup_tick_analytics_pipeline("s3://prod-fin-lakehouse/ticks/")
# df_vwap <- calculate_daily_vwap(con, "EURUSD", "2024-01-01 00:00:00", "2024-01-31 23:59:59")
```

---

### 9. Trade-offs

| Pendekatan I/O & Interop | Keunggulan Utama | Limitasi / Trade-off | Resource Profile | Skenario Penggunaan Ideal |
| :--- | :--- | :--- | :--- | :--- |
| **Apache Arrow IPC / ALTREP** | - Zero-copy memory footprint<br>- Interoperabilitas polyglot tanpa parsing<br>- Standar global format data kolom | - Kurang optimal untuk transformasi berbasis *row-level mutation* serial (misal loop imperatif) | - RAM: Rendah ($O(1)$ transfer)<br>- CPU: Ekstrem Rendah | Pipeline ETL berskala data besar, streaming data lake, integrasi R-Python-C++. |
| **DuckDB Embedded Engine** | - Kemampuan SQL lengkap (ACID, Window functions)<br>- Optimasi predikat & join engine tingkat lanjut<br>- Otomatisasi morsel multi-core parallelism | - Write throughput untuk single row latency tinggi (bukan OLTP engine) | - RAM: Terukur (dibatasi PRAGMA)<br>- CPU: Saturasi penuh core | Analitik SQL out-of-core lokal/cluster pada Parquet/CSV tanpa arsitektur Spark yang berat. |
| **DBI + Pool (Relational DB)** | - Integritas referensial dan transaksional konsisten<br>- Thread-safe connection lifecycle | - Overhead jaringan TCP/IP<br>- Parsing baris ke kolom membebani CPU | - RAM: Proporsional terhadap fetch size<br>- Jaringan: Tinggi | Operasi metadata terstruktur, state machine, registrasi status pipeline. |
| **Direct Binary I/O (Rcpp/C++)** | - Kontrol penuh pada alokasi level byte<br>- Eksekusi instruksi CPU SIMD kustom | - Rentan *segmentation faults* jika pointer management gagal<br>- Kode rentan OS non-portable | - RAM: Sangat efisien<br>- Dev Cost: Tinggi | Deserialisasi format custom proprietary proprietary (misal format biner raw sensor/pabrik). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Mengubah Objek ALTREP Secara Tidak Sengaja Menjadi Regular Vector (*Materialization Trap*)
- **Mistake**: Menjalankan fungsi native R tertentu yang tidak mengimplementasikan ALTREP interface (misal: modifikasi in-place atau beberapa wrapper `apply`), yang memaksa seluruh memori dialokasikan seketika (*force materialization*), memicu crash OOM.
- **Deteksi**: Gunakan `.Internal(inspect(x))` untuk memantau apakah representasi masih bertipe `ALTREP` atau telah bermutasi ke vektor heap standar.
- **Remediasi**: Jaga manipulasi kolom dalam boundary pipeline `dplyr` yang terhubung ke Arrow/DuckDB. Jangan memanggil `as.vector()` atau `as.data.frame()` sebelum operasi agregasi selesai disaring.

#### 10.2 Memory Leak pada Interoperabilitas C++ via Direct Pointer (`Rcpp`)
- **Mistake**: Mengalokasikan array C++ native (`new double[]` atau `malloc`) untuk dikembalikan ke R tanpa membungkus pointer dalam `Rcpp::XPtr` atau tanpa mekanisme finalizer `R_MakeExternalPtr`.
- **Troubleshooting**: Deteksi alokasi zombie menggunakan AddressSanitizer (ASan) dengan menambahkan flags `-fsanitize=address` pada `~/.R/Makevars`.
- **Remediasi**: Gunakan `cpp11` modern dengan alokator tipe RAII (*Resource Acquisition Is Initialization*) yang melepaskan memori otomatis ketika objek R terkena Garbage Collector.

#### 10.3 Koneksi Menggantung (*Leaked Connection Handlers*)
- **Mistake**: Melakukan `dbConnect()` di dalam loop atau pemanggilan API tanpa pembungkus blok penanganan error, sehingga kegagalan eksekusi query menyebabkan *idle in transaction* connection pool exhaustion.
- **Remediasi**: Wajib menggunakan idiom `on.exit(dbDisconnect(con), add = TRUE)` sesaat setelah fungsi `dbConnect()` berhasil diinisialisasi.

```r
# Anti-pattern
get_data_leaky <- function(id) {
  con <- dbConnect(RPostgres::Postgres(), dbname = "analytics")
  res <- dbGetQuery(con, sprintf("SELECT * FROM tbl WHERE id = %d", id)) # Jika ini error, koneksi bocor
  dbDisconnect(con)
  return(res)
}

# Defensive Production Pattern
get_data_safe <- function(id) {
  con <- dbConnect(RPostgres::Postgres(), dbname = "analytics")
  on.exit(dbDisconnect(con), add = TRUE) # Dijamin dieksekusi walau query throw error
  
  res <- dbGetQuery(con, "SELECT * FROM tbl WHERE id = $1", params = list(id))
  return(res)
}
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Enforce Explicit Schema**: Selalu deklarasikan schema Arrow/Parquet eksplisit saat impor; jangan biarkan engine melakukan *type sniffing* pada production pipeline.
2. [ ] **Storage Partition Strategy**: Terapkan partisi data berbasis frekuensi query (misal: rentang waktu `/year=YYYY/month=MM/`). Hindari *small files problem* (ukuran ideal tiap chunk file Parquet: $128\text{ MB} - 1\text{ GB}$).
3. [ ] **Zstandard Compression**: Gunakan kompresi `zstd` (level 3 s.d. 7) untuk cold/warm storage. Snappy hanya digunakan jika fokus utama murni kompresi latensi rendah tanpa memperhitungkan throughput bandwidth I/O disk.
4. [ ] **Resource Limits Configuration**: Pada DuckDB dan Arrow, pasang batas eksplisit `max_memory` dan `threads` agar proses komputasi R tidak terbunuh oleh Linux OS *OOM Killer*.
5. [ ] **Zero-Copy Polyglot Protocol**: Gunakan Arrow C Data Interface untuk setiap alur data lintas bahasa (R $\leftrightarrow$ Python $\leftrightarrow$ C++). Jangan gunakan perantara CSV/JSON di lingkungan produksi.
6. [ ] **Idempotent I/O Writes**: Penulisan dataset besar harus diarahkan ke temporary target directory terlebih dahulu sebelum operasi atomic filesystem rename (`mv`) untuk mencegah downstream pipeline membaca data corrupt hasil *partial write*.
7. [ ] **Connection Pooling**: Akses ke RDBMS multithreaded wajib melalui paket `pool` alih-alih koneksi raw `DBI::dbConnect`.

---

### 12. Hands-on Practice
Simpan seluruh script praktikum pada struktur path: `hands-on/m02/`

#### File: `hands-on/m02/01_large_scale_io_arrow_duckdb.R`
Skenario: Membangun pipeline out-of-core analitik telemetri IoT (10 juta events) dengan efisiensi memori maksimum.

```r
# ==============================================================================
# Enterprise Lab: High-Performance Ingestion & Pushdown Analysis
# Path: hands-on/m02/01_large_scale_io_arrow_duckdb.R
# ==============================================================================

suppressPackageStartupMessages({
  library(arrow)
  library(duckdb)
  library(dplyr)
  library(lobstr)
})

base_dir <- file.path("hands-on", "m02", "telemetry_data")
dir.create(base_dir, recursive = TRUE, showWarnings = FALSE)

message("Step 1: Generating 10 Million Records of Synthetic Telemetry Data...")
set.seed(42)
n_records <- 10e6
n_devices <- 500

batch_size <- 2e6
n_batches <- n_records / batch_size

# Schema Definition
telemetry_schema <- schema(
  timestamp = timestamp("ms", timezone = "UTC"),
  device_id = utf8(),
  region    = utf8(),
  cpu_temp  = float32(),
  power_kw  = float32()
)

start_time <- as.POSIXct("2024-01-01 00:00:00", tz = "UTC")

for (i in seq_len(n_batches)) {
  message(sprintf("Writing batch %d of %d...", i, n_batches))
  batch_df <- tibble::tibble(
    timestamp = start_time + seq((i - 1) * batch_size + 1, i * batch_size),
    device_id = sprintf("DEV-%04d", sample.int(n_devices, batch_size, replace = TRUE)),
    region = sample(c("us-east", "us-west", "eu-central", "ap-southeast"), batch_size, replace = TRUE),
    cpu_temp = runif(batch_size, 45.0, 95.0),
    power_kw = runif(batch_size, 0.5, 12.5)
  )
  
  write_dataset(
    dataset = batch_df,
    path = base_dir,
    format = "parquet",
    partitioning = c("region"),
    schema = telemetry_schema,
    compression = "zstd",
    compression_level = 3
  )
  rm(batch_df)
  gc(verbose = FALSE)
}

message("Data Generation Complete.")

# ==============================================================================
# Step 2: Out-Of-Core Querying with DuckDB Engine
# ==============================================================================
message("Step 2: Performing Out-of-Core Aggregations via Pushdown Queries...")

con <- dbConnect(duckdb::duckdb())
on.exit(dbDisconnect(con, shutdown = TRUE), add = TRUE)

dbExecute(con, "PRAGMA threads=4;")
dbExecute(con, "PRAGMA memory_limit='1GB';") # Batasi ketat RAM hanya 1GB

# Register Arrow Dataset ke DuckDB Engine
ds <- open_dataset(base_dir)
duckdb_register_arrow(con, "iot_telemetry", ds)

# Ukur Penggunaan Memori Heap R Sebelum Query
mem_before <- lobstr::mem_used()

# Eksekusi Query Kompleks (Heavy Group-By & Window Functions)
bench_start <- Sys.time()
query <- "
  SELECT 
    region,
    device_id,
    COUNT(*) as total_events,
    ROUND(AVG(cpu_temp), 2) as mean_temp,
    ROUND(MAX(cpu_temp), 2) as peak_temp,
    ROUND(SUM(power_kw), 2) as total_power
  FROM iot_telemetry
  WHERE cpu_temp > 85.0
  GROUP BY region, device_id
  HAVING COUNT(*) > 100
  ORDER BY peak_temp DESC
  LIMIT 20;
"

top_stress_devices <- dbGetQuery(con, query)
bench_end <- Sys.time()

mem_after <- lobstr::mem_used()

message(sprintf("Query Duration: %.3f seconds", as.numeric(bench_end - bench_start, units = "secs")))
message(sprintf("Memory allocated by R Heap: %.2f MB", (as.numeric(mem_after - mem_before) / 1024^2)))
print(top_stress_devices)

# ==============================================================================
# Step 3: Zero-Copy Handshake Verification
# ==============================================================================
message("Step 3: Validating Arrow IPC zero-memory allocation...")
arrow_table_result <- dbGetQuery(con, "SELECT region, cpu_temp FROM iot_telemetry WHERE cpu_temp > 94.0", arrow = TRUE)
message(sprintf("Arrow Table Record Count: %d rows", arrow_table_result$num_rows))
message(sprintf("Underlying C Structure Size in R Heap: %s", format(lobstr::obj_size(arrow_table_result))))
```

---

### 13. Exercises

#### Level Easy
Tuliskan skrip R yang mengonversi direktori berisi 10 file CSV berukuran masing-masing 50 MB menjadi file partisi Apache Parquet dengan format kompresi `snappy`. Pastikan skrip tidak membaca seluruh CSV ke memori sekaligus, melainkan melakukan pemrosesan streaming batch dengan `arrow::open_dataset` dan `arrow::write_dataset`.

#### Level Medium
Buat sebuah kelas R (menggunakan framework `R6`) bernama `ResilientDbPool`. Kelas ini harus:
1. Membuka koneksi pool PostgreSQL dengan `pool::dbPool()`.
2. Menyediakan fungsi `execute_with_retry(query, max_retries = 3)` yang secara transparan menangani *intermittent network drops* atau *deadlock exception*, melakukan *exponential backoff*, dan mencatat metrik kegagalan koneksi.
3. Menjamin pembersihan pool secara otomatis saat garbage collector menghancurkan instans kelas R6 tersebut.

#### Level Hard
Rancang modul I/O berbasis C++ (`cpp11` atau `Rcpp`) yang membaca custom binary record format dari disk (struk record: 8-byte unix timestamp, 4-byte sensor ID integer, 4-byte float reading value). Modul harus mengembalikan objek R data frame menggunakan mekanisme `ALTREP` kustom, sehingga array data numerik menunjuk langsung ke *memory-mapped file* (`mmap`) tanpa menduplikasi buffer data ke heap R.

---

### 14. Challenges

#### Arsitektur Lakehouse Real-time Ingestion & Compaction System
**Deskripsi Masalah**:
Perusahaan perbankan digital memiliki puluhan microservices yang mengunggah audit log transaksi keuangan setiap 5 menit ke object storage (AWS S3) dalam format Parquet mikro (~100 KB per file). Dalam sebulan, arsitektur ini menciptakan *Small Files Problem* dengan lebih dari 200.000 file individual, menurunkan performa analitik reporting hingga 80% akibat overhead HTTP metadata scanning pada S3 API.

**Persyaratan Sistem yang Harus Anda Bangun**:
1. Buat pipeline terjadwal di R yang mendeteksi mikro-file Parquet baru secara bertahap (*incremental processing*).
2. Terapkan strategi *In-Memory Compaction Engine*: Gabungkan puluhan ribu file kecil menjadi file berukuran standar (~256 MB) yang terpartisi secara Hive-partitioned (`/year/month/day/`), dengan skema yang tervalidasi penuh.
3. Pipeline harus bersifat **ACID-compliant / Idempotent**: Jika pipeline crash di tengah proses kompresi, storage tidak boleh berada dalam kondisi data ganda (*duplicate rows*) atau file rusak (*corrupted files*).
4. Sediakan layer interoperabilitas langsung ke model PyTorch di Python melalui zero-copy IPC streaming untuk deteksi *fraud* tanpa menyentuh disk fisik kedua kali.
5. Sediakan dokumentasi arsitektur berupa diagram sequence dan pembuktian matematis efisiensi memory foot-print.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa fungsi utama dari arsitektur ALTREP yang diperkenalkan pada R 3.5.0?
   - A. Menambah algoritma kompresi data string menjadi format biner.
   - B. Memungkinkan vektor R menjadi wrapper virtual ke data eksternal tanpa duplikasi instan ke heap RAM.
   - C. Menggantikan pustaka multithreading OpenMP di lingkungan UNIX.
   - D. Menghapus alokasi pointer `SEXP` pada runtime R.
   *Jawaban*: B. ALTREP memungkinkan data dibaca secara lazy (misal via memory mapping) tanpa alokasi langsung seluruh isi array ke heap R.

2. Mengapa format columnar seperti Apache Parquet jauh lebih efisien dibanding CSV untuk query analitik agregasi?
   - A. Karena Parquet tidak mendukung tipe data string sehingga ukurannya kecil.
   - B. Karena Parquet mendukung *Projection Pushdown* (hanya membaca kolom relevan) dan kompresi kolom efisien.
   - C. Karena CSV selalu membatasi pemrosesan pada 1 thread CPU saja.
   - D. Karena Parquet mengabaikan proses deserialisasi data.
   *Jawaban*: B. Parquet membaca data per-kolom, memangkas I/O disk untuk kolom yang tidak dipanggil, serta memiliki encoding yang efisien.

3. Apa algoritma kompresi default yang direkomendasikan pada Apache Arrow/Parquet untuk rasio kompresi tinggi dengan decompression speed yang tetap kencang pada data analitik dingin (*cold storage*)?
   - A. Gzip level 9.
   - B. Snappy.
   - C. Zstandard (ZSTD).
   - D. Bzip2.
   *Jawaban*: C. Zstandard menawarkan throughput dekompresi sangat tinggi dengan rasio kompresi mendekati Gzip.

4. Manakah fungsi R DBI yang menjamin pelepasan file descriptor koneksi database database secara aman saat terjadi runtime error di dalam fungsi?
   - A. `close()`
   - B. `dbDisconnect()` di dalam hook `on.exit(..., add = TRUE)`
   - C. `gc()`
   - D. `dbClearResult()`
   *Jawaban*: B. Hook `on.exit(..., add = TRUE)` memastikan instruksi pemutusan koneksi dieksekusi terlepas dari apakah fungsi selesai sukses atau berhenti karena error.

5. Ketika membaca file Parquet 50 GB menggunakan `arrow::open_dataset()`, berapakah rata-rata RAM fisik host yang dikonsumsi seketika oleh sesi R?
   - A. Tepat 50 GB.
   - B. Setengah kapasitas file (~25 GB).
   - C. Hanya beberapa Megabyte (overhead penampung metadata).
   - D. 100 GB (akibat duplikasi internal R SEXP).
   *Jawaban*: C. `open_dataset` hanya melakukan scan metadata header Parquet; data fisik aktual tidak ditarik ke RAM sampai instruksi `collect()` dijalankan.

#### Intermediate (5 Pertanyaan)
1. Bagaimana cara kerja Arrow C Data Interface dalam membagikan data antara proses R dan Python tanpa serialization cost?
   - A. Mentransfer data melalui TCP local loopback socket 127.0.0.1.
   - B. Menyimpan data sementara ke `/tmp/` dalam format CSV lalu dibaca kembali.
   - C. Melewatkan alamat pointer memori 64-bit dari struktur C `ArrowArray` dan `ArrowSchema` antar runtime.
   - D. Mengubah memori R menjadi format JSON base64.
   *Jawaban*: C. Interface ini berbasis standar layout memori C yang kompatibel di level ABI binary, cukup bertukar pointer array memory address.

2. Apa perbedaan mendasar antara *Predicate Pushdown* dan *Projection Pushdown*?
   - A. Predicate memfilter baris via statistik metadata; Projection memfilter kolom yang dibaca dari storage.
   - B. Predicate memilah tipe data; Projection mengubah nama tabel.
   - C. Predicate diterapkan pada database relasional; Projection hanya pada Flat CSV file.
   - D. Keduanya adalah istilah identik untuk indexing memori B-Tree.
   *Jawaban*: A. Projection memilih subset kolom; Predicate mengeliminasi pembacaan subset row group data berdasarkan kondisi filter (misal: `WHERE x > 10`).

3. Dalam skenario concurrency tinggi, mengapa menggunakan library `pool` lebih unggul dibandingkan membuat koneksi `DBI::dbConnect()` secara ad-hoc pada setiap request?
   - A. Karena `pool` mengabaikan otentikasi kata sandi database.
   - B. Mengeliminasi latensi negosiasi TLS/TCP handshake berulang dan mencegah saturasi connection limit pada RDBMS server.
   - C. Menjamin semua query di-cache secara otomatis di memori lokal.
   - D. Mengurangi ukuran query SQL menjadi bytecode terkompresi.
   *Jawaban*: B. Connection pooling mengelola daur hidup koneksi yang sudah terbuka (*warm connections*) untuk digunakan ulang oleh berbagai request, menghindari bottleneck inisialisasi socket baru.

4. Apa dampak penggunaan string native R secara masif pada dataset besar (puluhan juta entri) terhadap mekanisme R Garbage Collection (GC)?
   - A. Tidak ada dampak sama sekali, R memperlakukan string sebagai primitive array biasa.
   - B. R Global String Hash Table mengalami kepenuhan alokasi, memicu peningkatan overhead penelusuran pointer pada tahap GC Mark-and-Sweep dan memperlambat komputasi.
   - C. String otomatis dikonversi menjadi integer bitmask.
   - D. Sesi R langsung menghentikan proses evaluasi.
   *Jawaban*: B. Setiap string baru di-interning pada global pool R. Jutaan string unik menciptakan jutaan pointer terpisah yang harus diverifikasi oleh GC setiap siklus sweep, menyebabkan lag performa parah.

5. Pada DuckDB, bagaimana query engine-nya dapat mengeksekusi pipeline agregasi data yang total ukurannya melampaui alokasi RAM yang tersedia tanpa memicu OS Out-of-Memory (OOM)?
   - A. DuckDB mengonversi semua data menjadi swap string.
   - B. DuckDB mengimplementasikan *external aggregation & out-of-core sorting*, men-spill chunk data sementara yang terkompresi ke secondary disk storage saat melewati ambang batas `max_memory`.
   - C. DuckDB membatalkan baris data yang melebihi batas kapasitas memori.
   - D. DuckDB otomatis membagi komputasi ke komputer lain dalam jaringan.
   *Jawaban*: B. Buffer manager DuckDB mampu men-spill data intermediate hash table ke disk secara efisien ketika ambang batas memori tercapai.

#### Production Scenarios (3 Pertanyaan)

1. **Skenario Kasus Produksi A**:
   Sebuah pipeline data di server produksi gagal secara berkala dengan log: `vector memory exhausted (limit reached?)`. Kode pipeline menggunakan:
   ```r
   ds <- arrow::open_dataset("s3://logs-bucket/", format = "parquet")
   res <- ds %>% filter(year == 2023) %>% collect() %>% group_by(service) %>% summarise(err = sum(is_error))
   ```
   Data tahun 2023 memiliki ukuran 120 GB uncompressed, sementara server R memiliki RAM 64 GB.
   **Pertanyaan**: Identifikasi titik kegagalan arsitektur kode di atas dan tuliskan perbaikan kodenya agar pipeline dapat berjalan dengan alokasi RAM stabil di bawah 2 GB!
   *Analisis & Solusi*:
   - Titik kegagalan fatal terletak pada pemanggilan fungsi `collect()` sebelum eksekusi agregasi `group_by()` dan `summarise()`. Fungsi `collect()` memaksa materialisasi instan seluruh data 120 GB ke dalam heap memory R yang hanya berkapasitas 64 GB, melampaui batas alokasi memori fisik dan memicu OOM crash.
   - Solusi: Pindahkan pemanggilan `collect()` ke ujung pipeline setelah proses reduksi agregasi selesai di level Arrow/DuckDB streaming engine, sehingga hanya ringkasan baris akhir yang ditarik ke memory R.
   ```r
   res <- ds %>% 
     filter(year == 2023) %>% 
     group_by(service) %>% 
     summarise(err = sum(is_error, na.rm = TRUE)) %>% 
     collect() # Materialisasi hanya beberapa kilobyte data agregasi
   ```

2. **Skenario Kasus Produksi B**:
   Sebuah sistem ingestion API perbankan berbasis R (Plumber API) mengeksekusi penulisan ribuan audit log per detik ke database PostgreSQL analitik. Database DBA melaporkan bahwa terjadi `connection exhaustion` (mencapai `max_connections = 500`), dan latensi respons API melonjak dari 15ms menjadi 5000ms. Setelah audit kode, ditemukan setiap endpoint controller membuat koneksi baru menggunakan:
   ```r
   con <- dbConnect(RPostgres::Postgres(), host = "db.internal", user = "app")
   # ... write operations ...
   dbDisconnect(con)
   ```
   **Pertanyaan**: Bagaimana Anda mendesain ulang arsitektur connection layer pada microservice R tersebut agar performa stabil pada 5000 req/sec dengan connection pool terkendali?
   *Analisis & Solusi*:
   - Inisialisasi TCP socket + TLS Handshake + Postgres Backend Process forking pada setiap request HTTP menimbulkan latensi I/O raksasa dan saturasi pool connection database backend.
   - Solusi: 
     1. Buat Singleton global pool object menggunakan paket `pool` di level bootstrapping aplikasi (luar request handler context), misal dengan limit kapasitas maksimal 20-30 koneksi.
     2. Ganti operasi per-baris `INSERT` diskrit menjadi micro-batching atau buffer I/O dengan memanfaatkan command bulk copy POSIX native Postgres via `RPostgres::dbWriteTable(..., append = TRUE)`.
     3. Terapkan validasi koneksi otomatis (*heartbeat keep-alive*).

3. **Skenario Kasus Produksi C**:
   Anda membangun sistem deteksi fraud di mana pipeline rekayasa fitur ditulis dalam R, sedangkan model inference machine learning berbasis deep neural network dijalankan oleh engine PyTorch dalam Python pada node server yang sama. Volume streaming mencapai 500.000 transaksi per menit. Arsitektur awal mengekspor data fitur dari R ke disk lokal sebagai `/tmp/features.csv`, lalu Python membaca file tersebut. Sistem mengalami I/O disk bottleneck parah (SSD disk queue length > 50, SSD latency > 200ms).
   **Pertanyaan**: Rancang arsitektur I/O baru tanpa penulisan disk fisik (*diskless*) dengan memanfaatkan konsep yang telah dipelajari di modul ini!
   *Analisis & Solusi*:
   - Eliminasi sepenuhnya interaksi disk storage fisik (`/tmp/features.csv`) yang menjadi *bottleneck latency*.
   - Gunakan **Apache Arrow C Data Interface** via pustaka `reticulate`. Data frame hasil rekayasa fitur di R dikonversi menjadi objek `arrow::arrow_table()` in-memory.
   - Alirkan referensi pointer C memory interface secara langsung ke runtime Python menggunakan `reticulate::r_to_py(arrow_table)`. Di sisi Python, pointer ini langsung dibaca sebagai PyArrow Table atau PyTorch Tensor melalui memory sharing `torch.as_tensor()` melalui buffer CUDA/CPU pointer tanpa ada proses serialization/deserialization sama sekali. Latensi I/O terpangkas dari ratusan milidetik menjadi sub-milidetik ($O(1)$ kompleksitas transfer pointer).

---

### 16. Summary
- **Arsitektur I/O Modern R** telah bertransformasi dari pendekatan monolitik *in-memory eager evaluation* menuju komputasi terdistribusi dan *out-of-core vectorized streaming*.
- Fitur **ALTREP** menyediakan jembatan fundamental di level internal C R yang memungkinkan struktur array menunjuk langsung ke data yang dipetakan oleh sistem operasi (*memory-mapped I/O*), mencegah alokasi memori heap yang tidak perlu.
- **Apache Arrow** dan **DuckDB** membentuk kombinasi fondasi data lakehouse lokal maupun cloud yang memungkinkan eksekusi analitik berskala Terabyte langsung dari R runtime melalui penerapan teknik *Predicate Pushdown* dan *Projection Pushdown*.
- Pemanfaatan **Arrow C Data Interface** memungkinkan interoperabilitas zero-copy antara ekosistem R, Python, dan C++, mengeliminasi overhead serialisasi socket/disk, serta memungkinkan integrasi mulus antara manipulasi data analitik di R dan deep learning pipeline di Python.
- Standar rekayasa produksi menuntut manajemen konektivitas database yang thread-safe melalui *connection pooling*, format penyimpanan berorientasi kolom yang terpartisi secara hierarkis (Parquet/Zstandard), serta penanganan skema data yang ketat dan deterministik.