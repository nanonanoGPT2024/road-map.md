# BAB 04: Quiz, Challenge, & Knowledge Check
**High-Performance Data Wrangling (Tidyverse & data.table)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Alokasi Memori: Copy-on-Write (CoW) vs In-Place Modification
Jelaskan perbedaan fundamental antara paradigma *Copy-on-Write* (CoW) yang digunakan oleh manipulasi objek standar di R (termasuk perilaku dasar pada pipeline `dplyr`) dengan paradigma *modification-by-reference* melalui operator `:=` pada `data.table`. Bagaimana R Runtime mengelola pelacakan alamat memori (`address()` dan `tracemem()`) ketika sebuah kolom dimutasi pada kedua pendekatan tersebut, dan apa implikasi langsungnya terhadap tekanan *Garbage Collector* (GC) saat menangani dataset berukuran gigabyte?

### Soal 1.2: Evaluasi Ekspresi: Tidy Evaluation vs data.table Non-Standard Evaluation (NSE)
Bandingkan arsitektur evaluasi ekspresi antara `rlang`/Tidy Evaluation (yang mendasari `dplyr`) dan *frame-based evaluation* internal milik `data.table`. Bedah bagaimana *quosures* menangkap *environment* leksikal beserta ekspresi pada `dplyr`, dibandingkan dengan bagaimana `data.table` memperlakukan simbol di dalam blok `DT[i, j, by]` melalui representasi C internal (`eval()`). Di mana letak *overhead latency* mikrodetik yang sering muncul pada Tidy Evaluation dalam iterasi skala tinggi?

### Soal 1.3: Mekanisme Pengindeksan: Vector Scan vs Binary Search via Radix Ordering
Dalam `dplyr::filter()`, pencarian baris didasarkan pada *vectorized linear scan* bertipe logika ($O(N)$). Sebaliknya, `data.table` menyediakan mekanisme `setkey()` dan secondary indices (`setindex()`). Jelaskan secara komprehensif bagaimana `data.table` mengimplementasikan *radix sort* untuk membangun index vektor integer 2-pass, dan bagaimana algoritma *binary search* ($O(\log N)$) bekerja saat mengevaluasi argumen `i` pada ekspresi `DT[.(key_value)]`.

### Soal 1.4: Primitive Joins vs Complex Joins: Non-Equi dan Rolling Joins
Operasi *join* tradisional bergantung pada kesamaan nilai antar relasi (*equi-join*). Jelaskan keterbatasan algoritmik dari `dplyr::left_join()` ketika harus menyelesaikan persoalan *nearest-timestamp matching* atau *interval overlapping*, dan bagaimana `data.table` menyelesaikan ini secara native melalui *non-equi joins* (`DT1[DT2, on = .(id, time >= start, time <= end)]`) serta *rolling joins* (`roll = TRUE`, `roll = "nearest"`). Bagaimana struktur data internal mengelola *pointer matching* tanpa melakukan *Cartesian product expansion* terlebih dahulu?

### Soal 1.5: Abstraksi Tipe Data: S3 vctrs vs C-Level Atomic Vectors
`tibble` mengandalkan package `vctrs` untuk menegakkan stabilitas tipe data (*type safety*), penanganan *recycling rules*, dan konsistensi class S3. Di sisi lain, `data.table` beroperasi lebih dekat ke struktur internal R core atomic vectors (`SEXP`). Analisis konsekuensi arsitektural dari desain ini terhadap performa komputasi murni vs keamanan tipe (*type-soundness*), khususnya saat melakukan agregasi *grouped operations* pada kolom heterogen atau tipe *custom* (seperti `POSIXct`, `factor`, atau `blob`).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Invisible Reference Aliasing & Side-Effects Leakage
Perhatikan cuplikan kode berikut:
```r
library(data.table)

clean_features <- function(DT) {
  DT[, log_val := log(value + 1)]
  DT <- DT[log_val > 0]
  return(DT)
}

raw_data <- data.table(id = 1:5, value = c(0, 2, 5, 0, 10))
processed_data <- clean_features(raw_data)
```
Setelah kode ini dijalankan, amati state dari objek `raw_data`. Jelaskan mengapa `raw_data` memiliki kolom `log_val` meskipun fungsi tersebut tampaknya mengembalikan objek baru ke `processed_data`. Mengapa operasi subset `DT <- DT[log_val > 0]` menghasilkan *shallow/deep copy* baru sedangkan mutasi `:=` sebelumnya bocor ke global scope? Bagaimana cara refaktor fungsi ini agar strictly idempotent tanpa side effect jika diinginkan?

### Soal 2.2: Diagnostik Kegagalan Optimasi GForce pada data.table
`data.table` memiliki compiler internal bernama **GForce** yang memetakan operasi R umum (seperti `mean()`, `sum()`, `median()`) ke C primitives berkecepatan tinggi saat proses `by`. Misalkan Anda menjalankan:
```r
options(datatable.verbose = TRUE)
DT[, .(result = mean(val, na.rm = TRUE)), by = grp]
DT[, .(result = my_custom_mean(val)), by = grp]
```
Jelaskan indikator apa yang muncul pada log konsol yang menandakan GForce aktif (`GForce optimized`) atau gagal diaktifkan (*fallback to R interpreter*). Faktor-faktor apa saja yang secara silent mematikan optimasi GForce (misal: penggunaan fungsi wrapper, modifikasi environment argumen, perlakuan terhadap `NaN`), dan berapa besaran degradasi performa yang umumnya terjadi?

### Soal 2.3: Memory Fragmentation dan GC Thrashing pada dplyr Pipelining
Sebuah pipeline analitik memproses 30 juta baris data finansial:
```r
result <- df %>%
  mutate(x_norm = (x - mean(x)) / sd(x)) %>%
  filter(x_norm > 0) %>%
  group_by(category) %>%
  summarise(total = sum(x_norm), .groups = "drop")
```
Saat dipantau via monitoring host, penggunaan RAM sistem melonjak hingga 4x dari ukuran file mentah di disk sebelum akhirnya proses selesai. Analisis siklus hidup alokasi memori pada setiap transisi *pipe* (`%>%` atau `|>`). Apa yang menyebabkan alokasi intermediate copies, bagaimana *heap memory fragmentation* terjadi di R, dan teknik apa yang harus diterapkan pada arsitektur pipeline untuk mencegah *OOM Killer* tanpa meninggalkan ekosistem Tidyverse (misalnya integrasi `arrow` atau chunked processing via `dtplyr`)?

### Soal 2.4: Bottleneck Performa pada Penggunaan .SD Tanpa .SDcols
Banyak developer menulis ekspresi berikut untuk mentransformasi banyak kolom secara bersamaan:
```r
DT[, lapply(.SD, function(x) x / max(x)), by = grp]
```
Jelaskan mengapa penggunaan `.SD` (*Subset of Data*) secara default menciptakan overhead performa yang sangat masif pada dataset dengan jumlah grup (*cardinality*) yang tinggi (misal: 1 juta grup). Apa yang dialokasikan oleh R internal pada setiap iterasi grup untuk membangun objek `.SD`? Bandingkan konsumsi memori dan latensi operasi ini jika dioptimalkan menggunakan `.SDcols` eksplisit versus penulisan ekspresi dinamis yang dievaluasi langsung via C API.

### Soal 2.5: Secondary Index Invalidation dan Perangkap Shallow Copy
Jelaskan kondisi di mana sebuah *secondary index* (`setindex()`) pada `data.table` secara otomatis dibatalkan (*invalidated*) atau diabaikan oleh query optimizer internal. Jika Anda menduplikasi referensi tabel menggunakan `copy_dt <- DT` kemudian memanggil `setattr(DT, ...)` atau memanipulasi atribut indeks secara langsung, bagaimana *shallow copy pointer* di R engine merespons hal tersebut? Apa dampak eksekusi query pada `copy_dt` berikutnya jika secondary index di `DT` korup atau tidak sinkron?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Diagnostik OOM Spike pada Sistem Log Parsing Skala 100M Rows
Sebuah container Docker microservice (resource limit: 16 GB RAM) bertugas memproses log akses web harian (file Apache Arrow/Parquet terkompresi ~8 GB, jika dimuat ke R memory menjadi ~100 juta baris data frame dengan 15 atribut).

Pipeline yang saat ini berjalan:
```r
library(dplyr)
library(arrow)

process_logs <- function(filepath) {
  read_parquet(filepath) %>%
    filter(status_code == 200) %>%
    mutate(
      endpoint = tolower(endpoint),
      response_time_ms = as.numeric(duration) / 1000
    ) %>%
    group_by(endpoint, user_tier) %>%
    summarise(
      p95_latency = quantile(response_time_ms, 0.95),
      req_count = n(),
      .groups = "drop"
    ) %>%
    arrange(desc(req_count))
}
```
**Permasalahan:** Container mengalami exit code `137` (*Killed by Linux OOM Killer*) tepat pada langkah agregasi (`group_by` + `summarise`).
1. **Analisis Akar Masalah:** Jelaskan mengapa eksekusi `quantile()` di dalam `group_by()` pada ratusan ribu grup endpoint menghancurkan budget memori container tersebut.
2. **Mitigasi Arsitektural:** Rancang ulang arsitektur pemrosesan tersebut menggunakan kombinasi streaming/scanning via `arrow::open_dataset()` dan manipulasi in-place `data.table`. Sertakan kode implementasi lengkap yang menjamin alokasi RAM tetap berada di bawah 6 GB sepanjang runtime pipeline.

### Skenario B: Race Condition dan Memory Corruption pada REST API Engine Plumber
Sebuah core model credit-scoring diekspos melalui API REST berbasis package `plumber`. Untuk mengejar throughput tinggi (sub-100ms response time), engineer memuat dataset referensi lookup historis nasabah (10 juta baris) sekali ke dalam Global Memory saat server startup:
```r
# Global Scope
REFERENCE_DT <- fread("/data/nasabah_master.csv")
setkey(REFERENCE_DT, nasabah_id)

#* @post /score
function(req) {
  payload <- jsonlite::fromJSON(req$postBody)
  # Ambil fitur transaksi terkini
  user_id <- payload$nasabah_id
  
  # Update state transaksi terakhir nasabah secara cepat
  REFERENCE_DT[nasabah_id == user_id, `:=`(
    last_tx_amount = payload$amount,
    tx_count = tx_count + 1
  )]
  
  score <- compute_credit_risk(REFERENCE_DT[.(user_id)])
  return(list(status = "OK", score = score))
}
```
**Permasalahan:** Ketika stress-test dijalankan dengan konkurensi 50 requests/sec, terjadi anomali nilai `tx_count` yang tidak akurat, segfault (*core dumped*) sporadis pada R process, dan latency melonjak drastis.
1. **Analisis Concurrency & Integrity:** Mengapa R engine (yang secara default beroperasi secara single-threaded pada execution context-nya) tetap mengalami race condition dan potensi memori segfault pada manipulasi objek via `:=` di memori global saat diakses oleh async web workers (atau multiple forked workers via package seperti `future` / `promises`)?
2. **Desain Perbaikan:** Redesain arsitektur penyimpanan state dan transformasi data tersebut agar *thread-safe*, *concurrency-proof*, dan tetap mempertahankan SLA latensi sub-100ms.

### Skenario C: Trade-off Arsitektur: Native data.table vs Arrow Dataset vs DuckDB
Perusahaan broker saham internasional sedang merancang analytical engine untuk backtesting strategi kuantitatif pada 5 tahun data transaksi tick (total ~250 GB data Parquet terpartisi berdasarkan tanggal dan simbol saham). Tim terpecah menjadi tiga kubu:
*   **Kubu A:** Menggunakan `data.table` murni dengan membagi pemrosesan ke dalam loop chunk/partisi tanggal menggunakan RAM server besar (512 GB).
*   **Kubu B:** Menggunakan integrasi `arrow` + `dplyr` syntax untuk memanfaatkan lazy evaluation dan predicate pushdown.
*   **Kubu C:** Mengintegrasikan `duckdb` via package `duckdb` di R untuk melakukan eksekusi SQL langsung di disk/Parquet tanpa memuat data ke R runtime.

Lakukan audit arsitektural komparatif:
1. **Analisis Profil Kinerja:** Bandingkan ketiga pendekatan dari aspek CPU Cache Locality, SIMD Vectorization, Thread Utilization (OpenMP vs Task-based parallelism), dan Inter-Process Communication (IPC) overhead.
2. **Rekomendasi Teruji:** Berikan rekomendasi arsitektur final jika beban kerja analitik didominasi oleh operasi *as-of rolling joins* (mencocokkan quote terakhir sebelum transaksi terjadi) dan perhitungan *grouped moving window*. Justifikasi pilihan Anda secara rigid.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Financial Order Book Aggregator & Rolling Time-Series Engine

#### Deskripsi Masalah
Dalam perdagangan frekuensi tinggi (High-Frequency Trading), sistem dituntut untuk mengonsolidasikan data *market depth* (tick data) menjadi matriks fitur analitik secara instan. Anda diberikan dua dataset sintetis berskala besar:
1. `Trades`: Berisi 15.000.000 baris transaksi saham individual (`trade_id`, `symbol`, `timestamp_utc`, `price`, `volume`).
2. `Quotes`: Berisi 40.000.000 baris data perubahan penawaran pasar (`quote_id`, `symbol`, `timestamp_utc`, `bid_price`, `ask_price`, `bid_size`, `ask_size`).

Tugas Anda adalah membangun modul transformasi data end-to-end yang mengintegrasikan kedua dataset ini dengan zero-copy principles, mengekstrak fitur mikrostruktur pasar, dan mengembalikan ringkasan analitik per kuantor waktu tertentu.

#### Requirements Teknis
1. **In-Memory Optimization:** 
   * Dilarang keras menggunakan deep copy (`copy()`) kecuali saat duplikasi objek output final.
   * Seluruh modifikasi tipe data, normalisasi, dan penambahan metrik wajib memanfaatkan in-place operators (`:=` dan `set*` functions).
2. **As-Of Time Synchronization (Rolling Join):**
   * Untuk setiap baris transaksi pada `Trades`, pasangkan (*join*) dengan kondisi penawaran pasar terbaik (`Quotes`) yang terjadi **tepat sebelum atau bersamaan** dengan waktu transaksi tersebut berlangsung (`prev prevailing quote`).
   * Transaksi yang terjadi sebelum ada data quote untuk simbol tertentu harus di-impute atau di-drop secara deterministik.
3. **Advanced Microstructure Feature Calculation:**
   Hitung metrik berikut untuk setiap transaksi yang berhasil digabungkan:
   * **Effective Spread:** $2 \times |\ln(price) - \ln(mid\_price)|$, di mana $mid\_price = \frac{bid\_price + ask\_price}{2}$.
   * **Order Imbalance:** $\frac{bid\_size - ask\_size}{bid\_size + ask\_size}$.
   * **Trade Aggressor Indicator:** 1 jika $price \ge ask\_price$, -1 jika $price \le bid\_price$, 0 jika berada di antara keduanya.
4. **Windowed Rolling Metric per Symbol:**
   * Tanpa beralih ke package eksternal non-data.table (seperti `zoo` atau `slider`), hitung moving-average volume tertimbang (VWAP: *Volume Weighted Average Price*) dengan ukuran jendela 50 transaksi terakhir (*trailing 50-trade rolling window*) per simbol saham.
5. **Output Aggregation:**
   * Agregasikan metrik per `symbol` dan per interval bucket 1 menit (`timestamp_utc` truncated to minute): Total Transaksi, Total Volume Transaksi, Mean Effective Spread, dan Final Rolling VWAP dari bucket tersebut.

#### Constraints
* **Batas Memori:** Puncak alokasi memori (*peak memory usage*) R runtime selama keseluruhan proses tantangan ini tidak boleh melebihi **8.0 GB RAM**.
* **Batas Waktu Eksekusi:** Seluruh rangkaian proses (as-of join, mutasi metrik, rolling window, dan ringkasan bucket) harus tuntas di bawah **10 detik** pada mesin dengan 8 vCPU.
* **Tooling:** Wajib menggunakan `data.table` sebagai mesin utama. Dilarang mengonversi tabel menjadi `data.frame` biasa atau `tibble` di tengah pipeline komputasi.

#### Expected Output
1. File skrip R produksi bernama `order_book_engine.R` yang berisi fungsi parametrik:
   ```r
   run_orderbook_pipeline <- function(trades_path, quotes_path) -> data.table
   ```
2. Bukti profiling memori dan waktu eksekusi menggunakan package `bench::mark()` atau `peakRAM::peakRAM()` yang membuktikan bahwa batasan memori (< 8 GB) dan waktu (< 10 detik) terpenuhi.
3. Output validasi integritas struktur: Tidak ada *leakage memory pointer*, secondary index terdefinisi dengan rapi, dan output akhir memiliki skema kolom bertipe data presisi (`double`, `integer`, `POSIXct`).

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengaudit penguasaan teknis mendalam Anda terhadap Bab 04 sebelum melangkah ke topik parallel computing dan komputasi performa tinggi berikutnya.

### Saya harus memahami:
- [ ] Mekanisme internal alokasi memori R: Kapan R melakukan *shallow copy*, *deep copy*, atau mutasi *in-place*.
- [ ] Perbedaan representasi AST (*Abstract Syntax Tree*) antara Tidy Evaluation (`rlang` quosures, injection operator `!!`, data masking) dan C-evaluation pada `data.table` (`substitute`, `parent.frame`).
- [ ] Algoritma Radix Sort yang digunakan `data.table` untuk pengurutan berkecepatan tinggi dan cara pembentukan tabel indeks primer (`key`) serta sekunder (`index`).
- [ ] Arsitektur internal optimizer `data.table`: Bagaimana GForce mengenali dan mentranslasikan fungsi agregasi standar ke instruksi C loop.
- [ ] Konsep dasar ekosistem data modern: Apache Arrow C Data Interface, memory-mapped files (`mmap`), serta pertukaran data zero-copy antara Arrow dan data frames di R.
- [ ] Implikasi cache locality terhadap layout data berbasis kolom (*column-oriented*) vs baris (*row-oriented*) saat memproses ratusan juta elemen skalar di CPU.

### Saya tidak perlu menghafal:
- [ ] Seluruh variasi nama parameter internal fungsi join `merge.data.table` atau `dplyr::join` (cukup pahami semantik relasional dan cara mencari referensi parameter `on`, `by`, `suffix`).
- [ ] Sintaks mikro rlang macros/helpers yang deprecated (seperti `quo_name()`, `enquo()` legacy syntax; cukup pahami mekanisme fundamental injection `{{ }}`).
- [ ] Implementasi C-code internal dari `chmatch()` atau `forder()` di source code R core (cukup pahami karakteristik kompleksitas waktu dan batasan memori algoritmanya).

### Saya harus bisa melakukan:
- [ ] Melakukan profiling konsumsi memori dan eksekusi waktu baris-per-baris menggunakan `profvis`, `bench::mark()`, dan `tracemem()`.
- [ ] Merekayasa ulang pipeline `dplyr` yang lambat atau menyebabkan OOM menjadi pipeline `data.table` dengan kecepatan hingga puluhan kali lipat dan jejak memori mendekati nol *overhead*.
- [ ] Mengimplementasikan *non-equi join*, *rolling join*, dan *range overlap joins* (`foverlaps`) untuk menyelesaikan analisis time-series kompleks tanpa Cartesian explosion.
- [ ] Mengendalikan multi-threading internal `data.table` melalui `setDTthreads()` dan mengelola interaksinya dengan OpenMP untuk mencegah *thread thrashing* pada lingkungan komputasi berkonkurensi tinggi.
- [ ] Melakukan troubleshooting kegagalan GForce menggunakan `options(datatable.verbose = TRUE)` dan memperbaiki struktur sintaks agar kembali teroptimasi pada level C-primitive.
- [ ] Menulis modul pemrosesan data batch yang thread-safe dan terisolasi dari side-effect kebocoran referensi memori global pada lingkungan production API.