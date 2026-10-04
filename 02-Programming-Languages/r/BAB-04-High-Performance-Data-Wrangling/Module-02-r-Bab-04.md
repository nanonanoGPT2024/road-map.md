# Kurikulum Enterprise R: High-Performance Data Wrangling
## Bab 04: High-Performance Data Wrangling
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, *Data Engineer* dan *Production R Developer* diharapkan mampu:

1. **Menganalisis dan Memanipulasi Alokasi Memori R Runtime**: Memahami implementasi C internal dari objek R (*SEXP*), mekanisme *Copy-on-Modify* vs *Modify-in-Place*, sistem ALTREP (*Alternative Representations*), serta mengaudit konsumsi RAM menggunakan utilitas internal (`tracemem`, `.Internal(inspect())`).
2. **Menguasai Semantik C-Level `data.table`**: Mengimplementasikan *in-place mutation* via operator `:=` dan fungsi `set*`, memanfaatkan *secondary indices*, *binary search joins*, *rolling joins*, serta mengoptimalkan *multithreading parallel execution* berbasis OpenMP.
3. **Membangun Arsitektur *Out-of-Core Processing* dengan Apache Arrow**: Mengintegrasikan `arrow` untuk pemrosesan dataset berskala ratusan gigabyte melampaui batas RAM fisik (*zero-copy memory mapping*, *streaming RecordBatches*, dan format kolumnar Apache Parquet).
4. **Menerapkan Standar Produksi Enterprise**: Merancang *pipeline* transformasi data yang deterministik, *fault-tolerant*, aman terhadap konkurensi memori (*thread-safety*), dan terintegrasi ke dalam orkestrator produksi modern.

---

### 2. Prerequisite

Sebelum menempuh modul ini, praktisi wajib menguasai:

*   **Sintaks Dasar & Ekosistem R**: Pemahaman struktur data dasar (`vector`, `list`, `data.frame`), manipulasi fungsi vektor, dan lingkungan eksekusi paket (`renv`).
*   **Fundamental `data.table` & `dplyr`**: Memahami sintaks dasar `DT[i, j, by]` dan relasi logika SQL standard (*select, filter, group by, join*).
*   **Arsitektur Sistem Komputer**: Konsep dasar *CPU caching* (L1/L2/L3), *paging*, memori virtual (*virtual memory swap*), *pointers*, dan komputasi paralel *multi-core* (posix threads/OpenMP).
*   **Tooling**: R versi $\ge 4.2.0$, RStudio IDE / VSCode R Extension, kompilator C++ (`Rtools` di Windows, `build-essential` di Linux), dan pustaka sistem `libarrow`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 R Runtime Memory Model: SEXP, NAMED, dan ALTREP
Di tingkat internal R runtime (C core), semua objek direpresentasikan sebagai pointer ke struktur `SEXPREC` (*S-Expression Record*). Struktur ini mencakup *header* meta-informasi 64-bit dan *payload data*.

```
   Struct SEXPREC (32-48 Bytes Header)
+-------------------------------------------------------+
|  sxpinfo_struct  (GC info, type, refcnt/NAMED, mark)  |
|  struct SEXPREC* attrib                               |
|  struct SEXPREC* gengc_next / gengc_prev              |
+-------------------------------------------------------+
|  Payload Pointer / Data Vector Struct                 |
+-------------------------------------------------------+
```

R mengelola siklus hidup memori menggunakan mekanisme pelacakan referensi. Pada R versi lama, nilai bit `NAMED` (0, 1, atau 2) mengontrol *Copy-on-Modify*. Sejak R 3.5+, sistem `REFCNT` (Reference Counting) murni diadopsi. 
* Ketika sebuah objek memiliki `REFCNT == 1`, mutasi tertentu dapat berjalan *in-place*.
* Jika `REFCNT > 1`, modifikasi apa pun pada `data.frame` standar akan memicu alokasi memori baru melalui duplikasi mendalam (*deep copy*), menggandakan kebutuhan memori dan memicu latensi *Garbage Collection* (GC).

**ALTREP (Alternative Representations)**:
Diperkenalkan pada R 3.5, ALTREP memungkinkan R membungkus struktur data eksternal (seperti pointer memori mmap dari Apache Arrow atau deret bilangan kontinu `1:1e9`) tanpa mengalokasikan memori R secara langsung di heap. ALTREP menunda evaluasi (*lazy loading*) dan mengeliminasi proses materialisasi data hingga elemen spesifik diakses.

#### 3.2 Arsitektur Internal `data.table`
`data.table` mengabaikan mekanisme duplikasi memori standar R melalui implementasi tingkat rendah langsung di layer C:
*   **Over-allocation**: Secara *default*, saat membuat atau mengonversi objek ke `data.table`, alokasi vektor pointer kolom diberikan cadangan (*truelength* lebih besar daripada *length*, default 1024 slot ekstra). Hal ini memungkinkan operasi penambahan kolom via `:=` berjalan secara instan $O(1)$ tanpa perlu realokasi tabel pointer.
*   **Address Mutation (`:=` dan `set*`)**: Operator `:=` langsung memodifikasi pointer kolom pada struktur internal C tanpa menaikkan `REFCNT` dari tabel induk, mencapai komputasi $O(1)$ untuk modifikasi skalar dan $O(N)$ untuk mutasi vektor tanpa overhead GC.
*   **Secondary Indices & Fast Radix Sort**: `data.table` mengimplementasikan algoritma pengurutan *radix sort* berbasis C yang berjalan secara multithreaded. Indeks sekunder tidak menduplikasi data, melainkan hanya menyimpan vektor integer berisi urutan baris (`order vector`) di atribut `.Index`, memungkinkan binary search join berjalan dalam kompleksitas waktu $O(\log N)$.

#### 3.3 Apache Arrow C++ Engine & Apache Parquet
Apache Arrow menyediakan standar memori kolumnar *in-memory* yang identik lintas bahasa (C++, Python, R, Rust).
*   **Zero-Copy Sharing**: Arrow mengalokasikan *shared buffer* di luar heap R (*off-heap memory*). Melalui C Data Interface, data dapat dibaca langsung oleh R tanpa deserialisasi.
*   **RecordBatches**: Arrow memecah tabel menjadi *RecordBatches* diskrit. Eksekusi query (melalui Acero query engine) dilakukan secara *streaming* per-batch, menjaga penggunaan RAM tetap konstan meskipun memproses dataset terabyte.

---

### 4. Why & What

| Dimensi | Pendekatan Base R (`data.frame`) | Tidyverse (`dplyr` / `tibble`) | `data.table` Engine | Apache Arrow (`arrow`) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Single-threaded | Single-threaded | Multi-threaded (OpenMP) | Multi-threaded (C++ SIMD) |
| **Perilaku Memori** | Deep-copy pada hampir semua mutasi | Deep-copy terkontrol (*shallow copy* parsial) | *In-place mutation* mutlak via pointer C | Off-heap memory, zero-copy, streaming |
| **Skala Data Efisien** | $< 1 \text{ GB}$ | $1 - 5 \text{ GB}$ | $5 - 50 \text{ GB}$ (bergantung RAM) | $> 100 \text{ GB}$ hingga multi-TB (*out-of-core*) |
| **Pencarian / Join** | Scan Sekuensial: $O(N \cdot M)$ | Hash Join: $O(N + M)$ | Radix Sort / Binary Join: $O(N \log N + M \log N)$ | Scan Kolumnar Terkompresi & Pushdown Predicate |
| **I/O Bottleneck** | Sangat lambat (`read.csv`) | Moderat (`readr::read_csv`) | Sangat Cepat (`data.table::fread`) | Ultra Cepat via Parquet Memory-Mapped File |

**Why?**
Dalam sistem analitik finansial, telekomunikasi, dan bioinformatika tingkat enterprise, waktu jeda akibat GC (*stop-the-world GC pause*) dan kegagalan alokasi memori (*out-of-memory crash*) pada dataset 20-50GB adalah risiko operasional kritis. Pemahaman mendalam mengenai arsitektur ini memungkinkan perancangan sistem backend data wrangling yang tangguh, deterministik, dan efisien dari segi biaya infrastruktur (*compute cost*).

---

### 5. How (Workflow Detail)

Alur kerja arsitektur pemrosesan data performa tinggi dibagi menjadi tiga tahap isolasi:

```
[Tahap 1: Data Ingestion & Storage Out-of-Core]
   Partitioned Parquet Files / Cloud Storage (S3 / GCS)
                           |
                           v
   Arrow Multi-File Dataset Engine (arrow::open_dataset)
                           |
   [Predicate Pushdown (Filter) & Column Projection (Select)]
                           |
[Tahap 2: Lazy Streaming Execution Engine]
                           |
                           v
   Acero Stream Aggregator / RecordBatchReader
                           |
[Tahap 3: High-Speed In-Memory Wrangling]
                           | (Materialisasi subset < RAM threshold)
                           v
   data.table Engine (setkey, in-place update :=, rolling joins)
                           |
                           v
              Hasil Analisis / Aggregated Mart
```

1.  **Ingestion & Projection Filtering**: Dataset besar dibaca menggunakan `arrow::open_dataset()`. Gunakan *predicate pushdown* agar pemindaian hanya membaca blok Parquet yang relevan dan hanya memuat kolom (*column projection*) yang didefinisikan.
2.  **Streaming Pipeline**: Operasi agregasi dasar dilakukan di layer C++ Arrow sebelum data dimaterialisasi ke dalam memori R.
3.  **In-Memory Optimization via `data.table`**: Setelah dataset menyusut menjadi ukuran kerja aman ($\le \text{tersedia } 25\% \text{ RAM}$), konversikan ke `data.table` via `as.data.table()`.
4.  **In-place Computation**: Terapkan seluruh transformasi baris, pembuatan metrik, dan pengurutan menggunakan operator *reference* (`setkey`, `:=`, `setnames`, `setorder`) untuk menghentikan mutasi memori sekunder.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Manual vs. Terminal Kargo Terotomasi
*   **Base R / Deep Copy**: Anda meminjam buku ensiklopedia dari perpustakaan. Untuk menggarisbawahi satu kalimat di halaman 500, Anda menyalin seluruh 1000 halaman buku tersebut ke kertas baru dengan tulisan tangan, baru kemudian membuat garis bawah tersebut.
*   **`data.table` In-Place**: Anda memiliki akses khusus ke lemari arsip. Anda membuka halaman 500 dan langsung membubuhkan catatan tinta di tempatnya tanpa menyalin halaman lain.
*   **Apache Arrow**: Alih-alih membawa buku fisik ke meja kerja Anda, Anda menggunakan proyektor berkecepatan tinggi yang menampilkan data langsung dari rak kontainer logistik di luar gedung (*zero-copy off-heap*). Anda hanya mencatat hasil sintesis akhirnya.

#### Diagram: Perbandingan Mutasi Memori di Heap

```
Pendekatan Base R (Copy-on-Modify):
[Var: df1] ---> [SEXPREC df1: Addr 0x001A] (Ukuran: 10 GB)
                       |
  df1$colA <- df1$colA * 2  (Deep Copy terjadi!)
                       |
                       v
[Var: df1] ---> [SEXPREC df1_baru: Addr 0x009F] (Ukuran: 10 GB)
                [SEXPREC df1: Addr 0x001A] (Menunggu GC membebaskan RAM)
                Total Peak RAM: 20 GB!

-------------------------------------------------------------------------

Pendekatan data.table (In-Place Mutation via C pointers):
[Var: dt1] ---> [SEXPREC dt1: Addr 0x001A] (Ukuran: 10 GB)
                       |
  dt1[, colA := colA * 2]   (Modifikasi memori langsung via C pointer)
                       |
                       v
[Var: dt1] ---> [SEXPREC dt1: Addr 0x001A] (Ukuran: 10 GB tetap)
                Total Peak RAM: 10 GB! (Zero GC pressure)
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Membedah Alokasi Memori dengan `tracemem`

Contoh berikut menunjukkan bagaimana R standar menduplikasi memori dibandingkan dengan semantik referensi `data.table`.

```r
library(data.table)

# 1. Base R Copy-on-Modify
cat("=== Uji Base R data.frame ===\n")
df <- data.frame(id = 1:5, val = c(10, 20, 30, 40, 50))
tracemem(df)
# Modifikasi kolom
df$val <- df$val * 2 
# Output konsol akan memperlihatkan: 'tracemem[0x... -> 0x...]:' menandakan copy terjadi!
untracemem(df)

# 2. data.table Reference Semantics
cat("\n=== Uji data.table In-Place ===\n")
dt <- data.table(id = 1:5, val = c(10, 20, 30, 40, 50))
tracemem(dt)
# Mutasi in-place
dt[, val := val * 2]
# Tidak ada print trace alokasi baru, alamat memori tetap identik!
untracemem(dt)
```

#### 7.2 Practical Example: High-Throughput Batch Processing & Rolling Join

Skenario: Memadankan eksekusi transaksi keuangan (*trade*) ke kuotasi harga bid/ask pasar (*quote*) yang valid beberapa milidetik sebelum transaksi terjadi (*as-of join / rolling join*).

```r
library(data.table)

set.seed(42)
n_quotes <- 1e6
n_trades <- 2e5

# Generate Mock Quotes Data
quotes <- data.table(
  ticker = sample(c("AAPL", "GOOG", "MSFT", "AMZN"), n_quotes, replace = TRUE),
  timestamp = as.POSIXct("2026-03-30 09:30:00", tz = "UTC") + runif(n_quotes, 0, 23400),
  bid = round(runif(n_quotes, 100, 200), 2),
  ask = round(runif(n_quotes, 201, 300), 2)
)

# Generate Mock Trades Data
trades <- data.table(
  ticker = sample(c("AAPL", "GOOG", "MSFT", "AMZN"), n_trades, replace = TRUE),
  timestamp = as.POSIXct("2026-03-30 09:30:00", tz = "UTC") + runif(n_trades, 0, 23400),
  trade_size = sample(10:500, n_trades, replace = TRUE)
)

# Benchmark dan Optimasi:
# Set Multithreading OpenMP
setDTthreads(threads = 4)

# 1. Sort dan Indexing In-Place via setkeyv (Radix Sort C-Level)
setkeyv(quotes, c("ticker", "timestamp"))
setkeyv(trades, c("ticker", "timestamp"))

# 2. Eksekusi Fast Rolling Join (roll = TRUE -> mencari quote terakhir <= trade timestamp)
system.time({
  matched_trades <- quotes[trades, roll = TRUE, on = .(ticker, timestamp)]
})

# 3. Hitung Slippage / Spread In-Place tanpa alokasi vektor baru
matched_trades[, `:=`(
  spread = ask - bid,
  notional_value = bid * trade_size
)]

# Validasi output
print(head(matched_trades))
cat("Total alokasi thread aktif:", getDTthreads(), "\n")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus Produksi
Platform Financial Risk Management memproses data log klik dan transaksi deteksi fraud harian sebesar **120 Gigabyte Parquet files** di cloud storage. Mesin worker virtual di kubernetes hanya memiliki **16 GB RAM** dan 8 vCPU. 

#### Tantangan
*   Melakukan agregasi metrik fraud per pengguna (*window aggregation*) dan mendeteksi anomali transfer lintas rekening dalam rentang waktu $\Delta t \le 180 \text{ detik}$.
*   Mencegah container *OOM-Killed* (Out-Of-Memory) oleh kernel Linux.

#### Implementasi Solusi Arsitektur
Solusi menggabungkan streaming out-of-core via `arrow`, translasi subset ke `data.table`, pemanfaatan non-equi join, dan eksekusi bertahap (*chunked micro-batch pipeline*).

```r
library(arrow)
library(data.table)
library(dplyr)

# Simulasi Path Dataset Parquet
dataset_dir <- tempfile(pattern = "fraud_dataset_")
dir.create(dataset_dir)

# Membuat partisi data contoh (Representasi sebagian data produksi)
for (day in 1:3) {
  partition_dir <- file.path(dataset_dir, paste0("day=", day))
  dir.create(partition_dir)
  df_dummy <- data.frame(
    user_id = sample(10001:15000, 100000, replace = TRUE),
    txn_amount = rlnorm(100000, meanlog = 4, sdlog = 1.5),
    txn_time = as.POSIXct("2026-03-01 00:00:00", tz = "UTC") + runif(100000, 0, 86400),
    device_risk_score = runif(100000, 0, 1)
  )
  write_parquet(df_dummy, file.path(partition_dir, "data.parquet"))
}

# --- PRODUCTION PIPELINE WORKER ---

process_fraud_pipeline <- function(base_dir) {
  cat("[INFO] Membuka koneksi dataset Arrow...\n")
  ds <- open_dataset(base_dir, partitioning = "day")
  
  # Step 1: Pushdown filtering & Kolumnar projection
  # Ambil hanya transaksi mencurigakan dan kolom esensial tanpa load semua data ke RAM
  query <- ds %>%
    filter(device_risk_score > 0.70) %>%
    select(user_id, txn_time, txn_amount, device_risk_score)
  
  cat("[INFO] Membaca RecordBatch stream dan transformasi ke data.table...\n")
  # Menggunakan Scanner Arrow untuk streaming
  scanner <- Scanner$create(query)
  reader <- scanner$ToRecordBatchReader()
  
  results <- list()
  batch_idx <- 1
  
  # Stream processing: memory usage tetap rendah secara deterministik
  while (!is.null(batch <- reader$read_next_batch())) {
    dt_batch <- as.data.table(as.data.frame(batch))
    
    # Lewati batch jika kosong
    if (nrow(dt_batch) == 0) next
    
    # Set key untuk pencarian biner cepat
    setkey(dt_batch, user_id, txn_time)
    
    # In-place sliding non-equi self-join:
    # Mendeteksi apakah ada transaksi sebelumnya oleh user yang sama dalam window 180 detik
    dt_batch[, `:=`(
      time_lower = txn_time - 180,
      time_upper = txn_time
    )]
    
    # Non-equi join untuk menghitung frekuensi transaksi berulang dalam window
    rapid_txns <- dt_batch[
      dt_batch,
      on = .(user_id == user_id, txn_time >= time_lower, txn_time <= time_upper),
      .(user_id = x.user_id, 
        base_txn_time = x.txn_time, 
        prior_txn_time = i.txn_time, 
        prior_amount = i.txn_amount),
      allow.cartesian = FALSE
    ]
    
    # Agregasi anomali
    fraud_flags <- rapid_txns[, .(
      txn_count_3m = .N,
      total_vol_3m = sum(prior_amount)
    ), by = .(user_id, base_txn_time)][txn_count_3m >= 3] # Flag jika >= 3 transaksi dalam 3 menit
    
    results[[batch_idx]] <- fraud_flags
    batch_idx <- batch_idx + 1
  }
  
  cat("[INFO] Menggabungkan metrik anomali final...\n")
  final_flags <- rbindlist(results, use.names = TRUE)
  return(final_flags)
}

# Eksekusi sistem produksi
detected_fraud <- process_fraud_pipeline(dataset_dir)
cat("[DONE] Total transaksi anomali terdeteksi:", nrow(detected_fraud), "\n")
print(head(detected_fraud))

# Clean up
unlink(dataset_dir, recursive = TRUE)
```

---

### 9. Trade-offs

Menggunakan teknik *high-performance data wrangling* di R menuntut pertukaran arsitektural yang terukur:

| Dimensi | Pendekatan Deklaratif Tingkat Tinggi (`dplyr`/`dbplyr`) | Pendekatan Mutasi In-Place (`data.table`) | Pendekatan Direct Engine (`arrow` / Parquet) |
| :--- | :--- | :--- | :--- |
| **Throughput / Latency** | Lebih lambat. Latensi tinggi akibat alokasi memori GC dan deep-copy struktur data. | Ekstrem cepat. Latensi rendah, algoritma Radix Sort & binary search berbasis C murni. | Tercepat untuk I/O dan analitik agregasi skan besar; overhead kompilasi query minim. |
| **Memory Footprint** | Kebutuhan memori $2\times - 4\times$ ukuran dataset aktual saat manipulasi. | Kebutuhan memori hanya $1.05\times - 1.2\times$ ukuran dataset aktual berkat semantik `:=`. | Mendukung pemrosesan data melebihi ukuran memori fisik (*out-of-core*). |
| **Maintainability & Readability** | Sangat ekspresif, intuitif, mudah diuji (*unit testing*), kurva belajar rendah. | Sintaks padat (`DT[i, j, by]`), rentan *side-effects* yang tidak diinginkan jika pointer termutasi. | Sintaks terikat pada subset fitur yang didukung oleh Acero Engine C++. |
| **Concurreny & Safety** | Aman terhadap multi-threading (karena sifat immutability). | Bahaya konkurensi: mutasi via reference antar-lingkungan (*shared environment*) dapat merusak integritas state. | *Thread-safe* di layer C++, isolasi proses memori terjamin. |
| **Infrastructure Cost** | Memerlukan instance komputasi berkapasitas RAM tinggi (biaya VM mahal). | Memangkas kebutuhan RAM server hingga 50-70%. | Mengeliminasi kebutuhan node komputasi besar; cukup instance mikro dengan *ephemeral NVMe*. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Objek Tanpa Disengaja Akibat Shallow Copy (Reference Aliasing)
*   **Gejala**: Mengubah `dt_sub` menyebabkan `dt_asli` ikut berubah secara misterius.
*   **Akar Masalah**: Penugasan `dt_sub <- dt_asli` di R tidak menyalin data; keduanya merujuk ke pointer C yang sama.
*   **Solusi**: Gunakan fungsi eksplisit `copy()` dari `data.table`.
    ```r
    dt_asli <- data.table(a = 1:3)
    # SALAH: Shallow copy
    dt_sub <- dt_asli
    dt_sub[, a := 99L] # dt_asli$a ikut berubah menjadi 99!
    
    # BENAR: Alokasikan memori independen
    dt_sub <- copy(dt_asli)
    dt_sub[, a := 100L] # dt_asli tetap aman
    ```

#### 2. Thread Over-subscription pada Virtual Container
*   **Gejala**: Eksekusi `data.table` atau `arrow` menjadi luar biasa lambat di Docker / Kubernetes pod meskipun CPU core dialokasikan banyak.
*   **Akar Masalah**: R membaca total core fisik dari host hardware, bukan batas cgroups container CPU (*CPU quota*), memicu *context-switching thrashing* ribuan OS threads.
*   **Solusi**: Batasi jumlah thread eksplisit pada initialization script:
    ```r
    # Mendeteksi cgroup quota secara presisi
    limit <- as.integer(Sys.getenv("CONTAINER_CORE_LIMIT", unset = 4))
    data.table::setDTthreads(threads = limit)
    arrow::set_cpu_count(threads = limit)
    ```

#### 3. Error Cartesian Product Join Tidak Terkontrol
*   **Gejala**: Muncul pesan error fatal: `Execution halted: Subscript resulted in overly large join without 'allow.cartesian=TRUE'`.
*   **Akar Masalah**: Terjadi relasi *many-to-many* eksplosif pada kondisi join non-unik.
*   **Solusi**: Jangan langsung menyematkan `allow.cartesian=TRUE`. Audit integritas data dengan menghitung frekuensi key gabungan:
    ```r
    stopifnot(dt_right[, .N, by = .(join_key)][N > 1] == 0)
    ```

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa teknis ini sebelum merilis skrip komputasi R ke lingkungan produksi:

- [ ] **Alokasi Thread**: Fungsi `setDTthreads()` dan `arrow::set_cpu_count()` telah disetel sesuai batasan resource CPU cgroups container, bukan host bare-metal.
- [ ] **Penanganan Reference**: Setiap fungsi publik yang menerima dan mengembalikan `data.table` harus memanggil `copy()` di awal jika tidak dimaksudkan untuk memodifikasi argumen input caller secara *in-place*.
- [ ] **Manajemen Indeks**: Gunakan `setkey()` atau `setindex()` pada kolom yang sering digunakan untuk filtering atau join. Hapus indeks temporer jika tabel terus dimutasi secara masif untuk menghindari re-indexing penalty.
- [ ] **Type Coercion Prevention**: Pastikan tipe data pada operasi join identik secara mutlak (misalnya, hindari join antara `integer` dan `numeric/double`). Gunakan `setcolorder()` dan `setattr()` secara langsung untuk standarisasi tipe.
- [ ] **Garbage Collection Cadence**: Hindari memanggil `gc()` di dalam perulangan intensif (*inner loop*). Biarkan heuristik memori internal R mengelola GC; hanya picu `gc()` eksplisit setelah membersihkan objek masif via `rm()`.
- [ ] **Storage Layout**: Simpan dataset masif dalam format Apache Parquet yang terpartisi secara logis (*Hive-style partitioning*, e.g., `/year=2026/month=03/`), terkompresi dengan codec `SNAPPY` atau `ZSTD`.

---

### 12. Hands-on Practice

Buat skrip pengujian performa mandiri dengan struktur direktori berikut:

```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
```

Buat file `pipeline_benchmark.R` di direktori `hands-on/m02/` dengan isi instruksi langkah demi langkah:

```r
# hands-on/m02/pipeline_benchmark.R
# Modul 02: Hands-on High Performance Data Wrangling

suppressPackageStartupMessages({
  library(data.table)
  library(arrow)
})

cat("[Tahap 1] Setup environment dan simulasi payload...\n")
setDTthreads(2)
n_rows <- 5e6

# Generate payload 5 juta baris
dt <- data.table(
  transaction_id = 1:n_rows,
  customer_id = sample(1:50000, n_rows, replace = TRUE),
  amount = round(rnorm(n_rows, mean = 250, sd = 50), 2),
  status = sample(c("PENDING", "SETTLED", "REJECTED"), n_rows, replace = TRUE)
)

cat("[Tahap 2] Memverifikasi efisiensi in-place update vs copy...\n")
mem_sebelum <- address(dt)
# Mutasi in-place: update status dan tambahkan komisi
dt[status == "SETTLED", fee := amount * 0.015]
mem_sesudah <- address(dt)

stopifnot(mem_sebelum == mem_sesudah)
cat("[STATUS] Reference address terverifikasi tidak berubah:", mem_sebelum, "\n")

cat("[Tahap 3] Ekspor ke Parquet dan analisis Out-of-Core...\n")
parquet_file <- "hands-on/m02/transactions.parquet"
write_parquet(dt, parquet_file, compression = "snappy")

# Hapus data dari RAM
rm(dt)
invisible(gc())

# Baca kembali menggunakan engine Arrow Dataset
ds <- open_dataset(parquet_file)
hasil_agregasi <- ds %>%
  filter(status == "SETTLED") %>%
  group_by(customer_id) %>%
  summarize(
    total_spend = sum(amount),
    avg_spend = mean(amount)
  ) %>%
  collect() %>%
  as.data.table()

cat("[Tahap 4] Menguji Indexing Cepat data.table...\n")
setkey(hasil_agregasi, customer_id)
cat("Waktu pencarian biner customer_id = 45210:\n")
print(system.time({
  lookup <- hasil_agregasi[.(45210)]
}))
print(lookup)

cat("\n[BERHASIL] Hands-on Modul 02 selesai dieksekusi secara optimal.\n")
```

Jalankan skrip praktikum dari terminal:
```bash
Rscript hands-on/m02/pipeline_benchmark.R
```

---

### 13. Exercise

#### Level Easy
Konversikan kode Base R berikut menjadi bentuk idiomatis `data.table` yang memanfaatkan mutasi in-place secara penuh tanpa deep copy:
```r
# KODE AWAL (BASE R):
df <- data.frame(id = 1:1e6, category = sample(letters[1:5], 1e6, replace = TRUE), score = runif(1e6))
df$score_adjusted <- ifelse(df$category == "a", df$score * 1.5, df$score)
```
*Solusi Verifikasi*: Pastikan menggunakan `setDT(df)` dan `df[, score_adjusted := score][category == "a", score_adjusted := score * 1.5]`.

#### Level Medium
Diberikan tabel data sensor temperatur mesin pabrik `sensor_dt`:
```r
sensor_dt <- data.table(
  machine_id = rep(1:50, each = 1000),
  timestamp = rep(Sys.time() + 1:1000, 50),
  temp = rnorm(50000, 75, 5)
)
```
Tuliskan blok kode performa tinggi untuk menghitung nilai *Exponential Moving Average* (EMA) atau rolling average 5-periode dari `temp` untuk tiap-tiap `machine_id` menggunakan fitur bawaan `data.table::frollmean` secara *in-place*.
*Solusi Verifikasi*: Memanfaatkan `sensor_dt[, temp_ma5 := frollmean(temp, n = 5, align = "right"), by = machine_id]`.

#### Level Hard
Buat fungsi R produksi yang melakukan *Full Outer Rolling Join* dua arah (*bidirectional nearest timestamp match*) antara tabel eksekusi order dan tabel sinyal analitik dengan toleransi maksimal perbedaan waktu $\Delta t \le 500 \text{ milidetik}$. Jika tidak ada sinyal dalam batas window tersebut, kolom sinyal diisi `NA`. Solusi harus bebas alokasi memori berlebih dan tidak menghasilkan *cartesian explode*.

---

### 14. Challenge

**Skenario Rekayasa Sistem Finansial**:
Sebuah bursa komoditas mendistribusikan berkas log transaksi *tick-by-tick* harian dalam bentuk *gzip-compressed flat files* sebesar 40GB per hari. Format baris bersifat semi-terstruktur dengan panjang kolom yang dapat bervariasi bergantung tipe pesan:
* `MSG_TYPE 1` (Order Book Update): ID, Timestamp, Symbol, BidPrice, BidSize, AskPrice, AskSize
* `MSG_TYPE 2` (Trade Execution): ID, Timestamp, Symbol, ExecPrice, ExecSize, AggressorSide

**Tantangan**:
Rancang arsitektur sistem berbasis R (`Rscript` pipeline) yang:
1. Membaca stream tanpa mendekompresi seluruh 40GB file ke media disk lokal terlebih dahulu.
2. Memisahkan *message type* secara sekuensial atau paralel ke dalam struktur kolumnar Arrow.
3. Melakukan rekonstruksi *microsecond-level VWAP* (*Volume Weighted Average Price*) 10-menit bergerak untuk tiap simbol secara *out-of-core*.
4. Menjaga batas penggunaan RAM server tetap di bawah **4 Gigabyte** secara konstan sepanjang runtime eksekusi.
5. Mendokumentasikan estimasi penggunaan memori dan skema partisi penyimpanan output.

*(Tantangan ini tidak memiliki solusi instan tunggal; peserta dituntut merancang arsitektur I/O pipe C/R, integrasi `fifo` atau streaming reader Arrow, serta eksekusi low-level `data.table` mutation).*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Apa implikasi memori dari pemanggilan fungsi `as.data.table(df)` terhadap objek `data.frame` asal?**
   * *Kunci Jawaban*: `as.data.table(df)` secara umum melakukan alokasi dan duplikasi memori jika objek input berupa native `data.frame`. Untuk mencegah duplikasi dan mengubahnya langsung di tempat (*by-reference*), harus digunakan fungsi `setDT(df)`.
2. **Kapan operator `:=` memicu *warning* atau kegagalan modifikasi in-place?**
   * *Kunci Jawaban*: Ketika tabel referensi memiliki pointer hasil subseting yang tidak lengkap atau terkunci (*locked*), atau saat indeks alokasi kolom melebihi kapasitas *truelength* over-allocation tabel C.
3. **Apa perbedaan fungsional mendasar antara `key(dt)` dan `indices(dt)` pada `data.table`?**
   * *Kunci Jawaban*: `key(dt)` mengurutkan data secara fisik di memori melalui Radix Sort (hanya bisa 1 susunan primary key fisik), sedangkan `indices(dt)` membuat vektor pemetaan indeks sekunder tanpa mengubah tata letak fisik baris data.
4. **Apa fungsi utama dari paket `arrow` jika dibandingkan langsung dengan `data.table`?**
   * *Kunci Jawaban*: Arrow berfokus pada format penyimpanan kolumnar *zero-copy memory mapping*, eksekusi komputasi *out-of-core* untuk dataset yang melebihi kapasitas RAM, serta interoperabilitas antar-bahasa tanpa serialisasi.
5. **Mengapa penugasan `dt2 <- dt1` berbahaya jika dilanjutkan dengan operasi `dt2[, status := "PROCESSED"]`?**
   * *Kunci Jawaban*: Karena `dt2` dan `dt1` memegang referensi pointer memori C yang sama. Mutasi in-place pada `dt2` akan langsung memodifikasi data di `dt1`.

#### Intermediate (5 Pertanyaan)
1. **Bagaimana mekanisme *Garbage Collector* R merespons pemakaian memori dari Apache Arrow?**
   * *Kunci Jawaban*: Objek tabel Arrow dialokasikan pada memori *off-heap* (C++ runtime memory pool). Garbage Collector internal R tidak melacak memori off-heap ini secara langsung, sehingga metrik `gc()` di R tidak menampilkan ukuran alokasi Arrow yang sebenarnya.
2. **Jelaskan peran algoritma Radix Sort yang tertanam pada C-level `data.table` dibandingkan *QuickSort* bawaan Base R!**
   * *Kunci Jawaban*: Radix Sort pada `data.table` memiliki kompleksitas linier terhadap volume data $O(N \cdot K)$ di mana $K$ adalah panjang bit elemen, terotomasi *multithreading*, dan tidak melakukan perbandingan pairwise lambat seperti QuickSort ($O(N \log N)$), membuatnya jauh lebih cepat untuk kardinalitas tinggi.
3. **Mengapa fungsi `rbindlist(list_of_dts)` jauh lebih efisien dibandingkan loop `do.call(rbind, list_of_dfs)`?**
   * *Kunci Jawaban*: `do.call(rbind, ...)` melakukan rekursi alokasi memori bertingkat dengan kompleksitas kuadratik $O(N^2)$ alokasi memory. Sebaliknya, `rbindlist` diimplementasikan langsung di C, mengalokasikan total blok memori output hanya sekali, lalu melakukan *memory copy* (memcpy) secara paralel.
4. **Bagaimana parameter `nomatch = NULL` bekerja pada sintaks `dt1[dt2, on = .(id), nomatch = NULL]`?**
   * *Kunci Jawaban*: Berfungsi sebagai filter *Inner Join*. Baris pada `dt2` yang tidak menemukan pasangan kecocokan di `dt1` akan langsung didrop dari output tanpa menghasilkan baris berisi nilai `NA` (default behavior `nomatch = NA` merepresentasikan *Right Outer Join*).
5. **Jelaskan batasan utama arsitektur ALTREP saat berinteraksi dengan native C code pihak ketiga yang tidak ramah ALTREP!**
   * *Kunci Jawaban*: Jika fungsi C pihak ketiga mengakses pointer array data ALTREP secara primitif melalui makro lama seperti `DATAPTR()`, R terpaksa melakukan materialisasi data penuh secara mendadak ke dalam memori fisik (*fallback forced allocation*), meniadakan efisiensi *lazy evaluation* ALTREP.

#### Skenario Kasus Produksi (3 Pertanyaan Analitis)
1. **Kasus 1: Memory Leak pada Long-Running Process**
   * *Masalah*: Sebuah backend microservice analitik berbasis R menjalankan perulangan *consumer* Kafka. Meskipun selalu menggunakan `:=` untuk kalkulasi, konsumsi memori container naik perlahan hingga akhirnya crash OOM setelah 48 jam.
   * *Analisis & Solusi*: Periksa apakah skrip membuat kolom baru dengan nama unik secara dinamis. Penambahan kolom dinamis terus-menerus akan memicu realokasi vektor *truelength* atribut header berkali-kali. Solusi: Pertahankan struktur skema tabel statis, atau gunakan `rm()` eksplisit pada tabel batch temporer dan sinkronkan siklus hidup pointer.
2. **Kasus 2: Deadlock Konkurensi OpenMP**
   * *Masalah*: Saat mengeksekusi pipeline `data.table` di dalam worker proses paralel R (`parallel::mclapply` pada sistem Linux), sesi R sering mengalami kondisi *freeze / hang* tanpa utilisasi CPU.
   * *Analisis & Solusi*: Terjadi *fork-safety conflict*. Memanggil `mclapply` (yang menggunakan syscall `fork()`) bersamaan dengan library yang menjalankan threading OpenMP aktif memicu deadlock thread pool. Solusi: Matikan threading `data.table` sebelum melakukan forking (`setDTthreads(1)`), lalu aktifkan kembali thread di dalam masing-masing child process.
3. **Kasus 3: Regresi Performa Parquet Pushdown**
   * *Masalah*: Query `arrow::open_dataset()` berjalan lambat dan menguras I/O disk tinggi saat mengeksekusi query filter `filter(tolower(country_code) == "id")`.
   * *Analisis & Solusi*: Penerapan fungsi R seperti `tolower()` secara inline memutus kemampuan *predicate pushdown* ke Parquet metadata reader. Acero Engine C++ terpaksa membaca seluruh data kolom mentah ke memory sebelum menerapkan filter. Solusi: Simpan data Parquet dalam format string yang dinormalisasi sejak awal (lowercase murni), dan lakukan filter langsung pada nilai konstan `filter(country_code == "ID")`.

---

### 16. Summary

1. **Efisiensi Memori R Core**: Pemahaman terhadap struktur `SEXPREC`, referensi memori (`address()`, `tracemem()`), dan subsistem ALTREP adalah fondasi eliminasi *bottleneck* komputasi di ekosistem R enterprise.
2. **Keunggulan `data.table`**: Mengandalkan *in-place mutation* berbasis semantik C pointer (`:=`, `set*`), alokasi memori cerdas (*over-allocation*), multithreading OpenMP native, dan struktur Radix Sort untuk kecepatan eksekusi $O(1)$ dan $O(\log N)$.
3. **Komputasi Out-of-Core dengan Apache Arrow**: Mengeliminasi keterbatasan kapasitas RAM fisik melalui pemetaan memori *zero-copy*, *predicate pushdown*, *column projection*, dan streaming *RecordBatches* berbasis format Apache Parquet.
4. **Pola Desain Arsitektur Modern**: Kombinasikan kemampuan pemindaian *out-of-core* Apache Arrow pada tahap *ingestion* skala besar, dan turunkan ke pemrosesan analitik *in-memory* mikro berkecepatan tinggi menggunakan `data.table` untuk mencapai throughput data pipeline enterprise yang maksimal dan hemat infrastruktur.