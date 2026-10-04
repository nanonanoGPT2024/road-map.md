# BAB 03: Quiz, Challenge, & Knowledge Check
**Data Wrangling & Manipulation dengan Modern Tidyverse**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Relasional vs. Vectorized Tidy Data
Jelaskan perbedaan mendasar antara representasi relasional normalisasi ketiga (3NF) dari E.F. Codd dengan konsep *Tidy Data* dari Hadley Wickham. Mengapa struktur *Tidy Data* (setiap variabel adalah kolom, setiap observasi adalah baris, setiap nilai adalah sel) dirancang secara spesifik untuk mengeksploitasi arsitektur komputasi *vectorized execution* pada R, dan bagaimana operasi seperti `tidyr::pivot_longer()` mengubah topologi memori vektor internal R?

### Soal 1.2: Mekanisme Tidy Evaluation: Data Masking vs. Tidy Selection
Tidyverse membedakan secara tegas antara lingkungan evaluasi *Data Masking* dan *Tidy Selection*.
1. Jelaskan perbedaan konseptual dan implementasi internal antara kedua mekanisme tersebut.
2. Mengapa sintaks seperti `df %>% select(starts_with("x"))` bekerja menggunakan aturan seleksi indeks/nama, sementara `df %>% filter(x > 10)` membutuhkan evaluasi ekspresi terhadap konteks data frame?
3. Apa peran dari arsitektur injection operator `{{ }}` (curly-curly / emrace) dalam menjembatani parameterisasi fungsi kustom pada konteks *Data Masking*?

### Soal 1.3: Native Pipe (`|>`) vs. Magrittr Pipe (`%>%`) Internals
Sejak R 4.0.0, native pipe (`|>`) diintegrasikan langsung ke dalam syntax tree parser R. Analisis perbedaan arsitektur internal antara `|>` dan `%>%` dari paket `magrittr`. Fokuskan analisis Anda pada:
1. Waktu evaluasi (compile-time syntactic transformation vs. runtime nested function wrapper evaluation).
2. Mekanisme alokasi call stack dan dampaknya terhadap profil *stack trace* saat terjadi unhandled error.
3. Batasan semantik placeholder (`_` pada native pipe dengan persyaratan *named argument* vs. `.` pada magrittr yang fleksibel).

### Soal 1.4: Dynamic Typing & Evaluasi Sekuensial pada `dplyr::mutate()`
Bagaimana `dplyr::mutate()` mengevaluasi dependensi kolom secara sekuensial dalam satu pemanggilan fungsi yang sama (contoh: `mutate(a = 1, b = a * 2, c = b + 5)`)? Jelaskan mengapa pendekatan ini secara semantik dan alokasi memori berbeda dengan assignment berulang pada Base R (`df$a <- 1; df$b <- df$a * 2; df$c <- df$b + 5`), terutama terkait dengan siklus alokasi *Copy-on-Modify* pada lingkungan eksekusi R.

### Soal 1.5: Paradigma Vectorized Grouping vs. `rowwise()` Overhead
Mengapa operasi `dplyr::rowwise()` secara luas diklasifikasikan sebagai *performance anti-pattern* untuk pemrosesan skala besar jika dibandingkan dengan kombinasi `group_by()` atau operasi berbasis vektorisasi murni? Jelaskan representasi struktur data tibble di balik layar saat berada dalam status `rowwise` dan bagaimana overhead dispatching R function call per baris mendegradasi throughput CPU cache.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi Join Semantics & Mitigasi Cartesian Explosion
Perhatikan snippet eksekusi modern dplyr (>= 1.1.0) berikut:

```r
library(dplyr)

transactions <- tibble(
  trx_id = c(101, 102, 103, 104),
  cust_id = c("C1", "C2", "C1", "C3"),
  amount = c(500, 150, 300, 700)
)

promotions <- tibble(
  cust_id = c("C1", "C1", "C2"),
  promo_code = c("DISC10", "CASHBACK", "FREESHIP")
)

# Eksekusi Join
result <- left_join(transactions, promotions, by = "cust_id", relationship = "many-to-one")
```

1. Apa yang terjadi secara internal ketika parameter `relationship = "many-to-one"` dievaluasi oleh C++ layer dplyr jika data faktual memiliki relasi *many-to-many*?
2. Bagaimana mekanisme hashing hash-join pada dplyr memetakan join keys, dan apa dampak arsitektural jika terjadi silent Cartesian product terhadap RAM exhaustion?

### Soal 2.2: Strict Type System & Rekonstruksi Atribut via `vctrs`
Tidyverse modern mengandalkan package `vctrs` untuk menegakkan *type stability*. Debug dan jelaskan mengapa kode berikut menghasilkan error fatal pada modern tidyverse, sedangkan Base R `rbind()` mengeksekusinya dengan *silent coercion*:

```r
library(vctrs)
library(dplyr)

df1 <- tibble(id = 1:2, status = factor(c("Active", "Pending")))
df2 <- tibble(id = 3:4, status = factor(c("Suspended", "Active")))

# Modern tidyverse
combined_tidy <- bind_rows(df1, df2)

# Bandingkan mekanismenya dengan:
# combined_base <- rbind(as.data.frame(df1), as.data.frame(df2))
```
Jelaskan bagaimana `vctrs::vec_ptype2()` dan `vctrs::vec_cast()` bekerja di balik `bind_rows()` untuk mencegah silent semantic corruption pada level categorical factor levels.

### Soal 2.3: Lifecycle State Leakage pada Grouped Data Frames
Jelaskan lifecycle sebuah data frame ketika dikenakan `dplyr::group_by()`.
1. Data struktur metadata apa (`groups` attribute) yang disuntikkan ke dalam objek data frame?
2. Perhatikan kode di bawah. Mengapa kegagalan pemanggilan `ungroup()` secara eksplisit sebelum melakukan *downstream feature engineering* dapat memicu *memory leak*, mutasi agregasi yang salah (silent calculation bugs), atau kegagalan serialisasi data ke format Apache Parquet?

```r
pipeline_leak <- raw_data %>%
  group_by(tenant_id, region) %>%
  mutate(regional_mean = mean(transaction_val, na.rm = TRUE)) %>%
  filter(transaction_val > regional_mean) %>%
  mutate(normalized_score = (transaction_val - min(transaction_val)) / 
                            (max(transaction_val) - min(transaction_val))) 
  # Missing explicit ungroup()
```

### Soal 2.4: Environmental Collision & Evaluation Scope Masking
Diberikan fungsi pembungkus (wrapper) berikut yang mengalami bug fatal di lingkungan produksi:

```r
filter_records <- function(df, status, threshold) {
  df %>%
    filter(status == status & amount >= threshold)
}

test_df <- tibble(
  status = c("PENDING", "COMPLETED", "FAILED"),
  amount = c(100, 200, 50)
)

# Invocation:
filter_records(test_df, status = "COMPLETED", threshold = 100)
```
1. Mengapa fungsi di atas mengembalikan 2 baris (baris 1 dan 2) dan bukan 1 baris seperti yang diharapkan secara intuitif?
2. Perbaiki kode tersebut menggunakan dua paradigma yang berbeda:
   - Menggunakan scoped pronoun `.data` dan `.env`.
   - Menggunakan rlang metaprogramming injection (`{{ }}` atau `!!`).
Jelaskan resolusi symbol table R untuk masing-masing solusi.

### Soal 2.5: Subsetting Semantics: ALTREP vs. Deep Copy pada Pipeline Tidyverse
Ketika Anda mengeksekusi pipeline transformatif berikut:

```r
processed <- raw_big_data %>%
  select(id, event_type, payload_str) %>%
  filter(event_type == "CHECKOUT") %>%
  slice_head(n = 1000)
```
Bagaimana arsitektur memory R (khususnya representasi ALTREP - *Alternative Representations* dan compact sequences) menangani referensi data frame hasil pemotongan baris dan kolom? Pada titik transformasi mana sistem dipaksa melakukan *deep memory copy*, dan bagaimana Anda membuktikannya menggunakan `lobstr::obj_addr()` dan `tracemem()`?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Pipeline ETL End-of-Month (OOM Killer Invocation)
Anda adalah Data Engineering Lead pada platform payment gateway. Pipeline ETL bulanan memproses data transaksi settlement sebesar **45 juta baris** (berukuran ~14 GB dalam bentuk CSV terkompresi). Pipeline ditulis menggunakan script dplyr konvensional yang berjalan pada single compute engine instance (64 GB RAM).

```r
# Pipeline cuplikan saat crash:
settlement_summary <- raw_transactions %>%
  filter(status %in% c("SETTLED", "RECONCILED")) %>%
  mutate(trx_date = as.Date(created_at),
         fee_normalized = amount * rate_multiplier) %>%
  group_by(merchant_id, trx_date, currency) %>%
  summarise(
    total_volume = sum(amount, na.rm = TRUE),
    net_revenue = sum(fee_normalized, na.rm = TRUE),
    p95_amount = quantile(amount, 0.95, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  left_join(merchant_metadata, by = "merchant_id")
```

**Insiden:** Proses selalu dihentikan paksa oleh Linux kernel (`OOM Killer / exit code 137`) tepat saat mengeksekusi tahapan `summarise()` dengan `quantile()`.

#### Pertanyaan Diagnostik & Solusi Skenario A:
1. Analisis mengapa perhitungan `quantile()` dalam konteks `group_by()` masif menjadi pemicu utama bottleneck memori dan CPU thrashing pada R runtime engine.
2. Rancang ulang arsitektur pemrosesan data tersebut tanpa meninggalkan ekosistem Tidyverse API. Komparasikan dua strategi berikut:
   - **Opsi 1**: Migrasi backend menggunakan `dtplyr` (data.table lazy evaluation interface).
   - **Opsi 2**: Transisi ke *Out-of-Core Processing* menggunakan `arrow::open_dataset()` atau integrasi `duckdb` via `dbplyr`.
   Tentukan pendekatan mana yang paling optimal secara footprint memori dan throughput runtime. Tuliskan kode refactor-nya.

---

### Skenario B: Silent Data Corruption pada IoT Streaming Telemetry (Pivot Instability)
Sistem ingest telemetri pabrik menerima data IoT industri dari ribuan sensor. Data dicatat dalam format semi-long format dan ditransformasi ke format wide untuk analisis anomaly detection real-time:

```r
incoming_sensor_stream <- tibble(
  device_id = c("D1", "D1", "D1", "D2", "D2", "D1"),
  metric_name = c("temp", "pressure", "temp", "temp", "pressure", "voltage"),
  timestamp = as.POSIXct(c("2026-03-30 10:00:00", "2026-03-30 10:00:00", 
                           "2026-03-30 10:00:00", "2026-03-30 10:00:00", 
                           "2026-03-30 10:00:00", "2026-03-30 10:00:00")),
  metric_value = c(85.5, 1.2, 86.1, 72.0, 1.0, 220.0)
)
```

Ketika script transformasi berikut dieksekusi:

```r
wide_telemetry <- incoming_sensor_stream %>%
  pivot_wider(
    names_from = metric_name,
    values_from = metric_value
  )
```

**Insiden:** Sistem machine learning downstream mengalami *type degradation failure* karena kolom `temp` secara tiba-tiba bermutasi dari `double` menjadi *nested list of doubles* (`list<double>`), memicu silent crash pada inferensi model.

#### Pertanyaan Diagnostik & Solusi Skenario B:
1. Bedah mekanisme internal `tidyr::pivot_wider()` yang menyebabkan terbentuknya tipe data list-column tersebut. Mengapa fungsi tidak memunculkan *breaking error* melainkan sekadar *warning*?
2. Bagaimana Anda merancang skema defensif (*production-grade assertion pipeline*) menggunakan parameter `values_fn`, `id_cols`, atau fungsi validasi tipe data sebelum data diteruskan ke downstream model? Tuliskan pipeline mitigasi yang deterministik dan *idempotent*.

---

### Skenario C: Real-Time Scoring Microservice Latency Degradation
Anda membangun REST API microservice menggunakan framework `plumber` di R. Microservice ini menerima request JSON payload dengan batch size kecil (10 hingga 50 transaksi per request) untuk dilakukan real-time enrichment dan validation scoring sebelum disimpan ke database transaksional.

```r
#* @post /score
function(req) {
  payload_df <- jsonlite::fromJSON(req$postBody)
  
  # Pipeline Tidyverse di dalam endpoint API
  scored <- payload_df %>%
    as_tibble() %>%
    mutate(across(where(is.character), stringr::str_trim)) %>%
    filter(!is.na(transaction_id)) %>%
    group_by(account_type) %>%
    mutate(
      weighted_risk = custom_risk_calc(amount, risk_factor),
      scaled_val = scales::rescale(amount)
    ) %>%
    ungroup()
  
  return(scored)
}
```

**Insiden:** Pada saat dilakukan load test konkurensi tinggi (500 concurrent requests/sec), p99 latency meroket hingga > 1.200 ms. Profiling menggunakan `profvis` menunjukkan bahwa > 65% waktu CPU dihabiskan pada overhead dispatch Tidyverse (`rlang` parsing, environment capturing, and generic S3 method resolution) dan bukan pada kalkulasi numerik riil.

#### Pertanyaan Diagnostik & Solusi Skenario C:
1. Evaluasi secara kritis trade-off arsitektural antara penggunaan *Modern Tidyverse High-Level Abstractions* versus *Base R Primitive/Matrix Operations* pada komputasi bertipe ultra-low latency, micro-batch processing.
2. Lakukan optimasi refactor pada kode endpoint di atas agar dapat mempertahankan readability namun secara drastis memangkas overhead pemanggilan function wrapper, ekspresi NSE, dan alokasi memori intermediat.

---

## 4. Chapter Challenge

### Tantangan Praktis: Multi-Tenant Enterprise Audit Ledger Reconciliation Engine

#### Problem Statement
Sebuah institusi perbankan digital membutuhkan *Reconciliation Engine* otomatis untuk memvalidasi jutaan rekonsiliasi mutasi harian lintas tenant dan gateway. Data mentah diekstrak dari berbagai source log yang tidak konsisten, memiliki missing timestamps, record duplikat, skema kolom heterogen, dan transaksi multi-currency yang belum dinormalisasi.

Anda ditugaskan merancang sebuah modul fungsi produksi R berbasis Modern Tidyverse (dplyr >= 1.1.0, tidyr, purrr, vctrs) yang tangguh, *strictly-typed*, vectorized, dan bebas dari imperatif loop (`for`/`while`).

#### Requirements
1. **Dynamic NSE Interface**: Buat fungsi master `reconcile_tenant_ledger(data, tenant_col, amount_col, timestamp_col, group_keys, fx_table)` yang menerima unquoted dynamic column names (Tidy Evaluation / Emrace operator).
2. **Schema & Type Enforcement**: Validasi tipe kolom input secara defensif menggunakan `vctrs`. Jika kolom `amount` berupa string atau mixed-type, lakukan konversi safe cast; jika data corrupted fatal, lempar structured error (`rlang::abort`).
3. **Data Cleaning & Normalization**:
   - Deteksi dan isolasi duplicate records berdasarkan kombinasi dynamic keys.
   - Isi missing value timestamp dengan interpolasi forward/backward fill terikat dalam isolasi partisi per tenant (`tidyr::fill`).
   - Normalisasi currency multi-mata uang ke target *base currency* (USD) menggunakan operasi join dinamis ke `fx_table`.
4. **Windowed Metrics & Anomaly Flagging**:
   - Hitung rolling cumulative balance per tenant tanpa merusak struktur grouping asli.
   - Hitung gap waktu (delta seconds) antar-transaksi per pengguna menggunakan `dplyr::lead()` / `dplyr::lag()`.
   - Berikan flag anomali jika transaksi terjadi < 2 detik dari transaksi sebelumnya dengan nilai > 3 kali median transaksi tenant tersebut.
5. **Multi-Aggregation Reporting Output**:
   Fungsi harus mengembalikan named list berisi 3 data frame:
   - `clean_ledger`: Data transaksi yang telah dinormalisasi dan di-flagging.
   - `discrepancy_records`: Rekaman yang gagal validasi integritas (duplikat, missing values permanen, atau deviasi kurs).
   - `executive_summary`: Data yang di-*pivot wider* berisi matriks per tenant: total volume transaksi settled, total anomali terdeteksi, dan rasio anomali.

#### Constraints
- Dilarang keras menggunakan loop konvensional (`for`, `while`, `repeat`). Seluruh manipulasi data wajib menggunakan paradigma Tidyverse / Functional Vectorization.
- Memory handling harus diperhatikan: Tidak diperbolehkan meninggalkan metadata dangling groups (wajib *zero group-leakage*).
- Pipeline harus deterministik dan kompatibel dengan dplyr 1.1.0+ (menggunakan parameter `.by` pada operasi ad-hoc jika tidak memerlukan state grup permanen).

#### Expected Output Format
File implementasi R script yang modular, terdokumentasi dengan roxygen-style comments, memiliki validasi mock data komprehensif, dan menampilkan hasil print out dari ketiga tibble hasil rekonsiliasi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara Data Masking (contoh: `mutate`, `filter`) dan Tidy Selection (contoh: `select`, `relocate`).
- [ ] Cara kerja injeksi metaprogramming `rlang`: Pronoun `.data` vs `.env`, double curly `{{ }}`, serta splicing `!!!`.
- [ ] Perbedaan arsitektural dan performa memori antara native R pipe (`|>`) dan magrittr pipe (`%>%`).
- [ ] Perilaku internal *Copy-on-Modify* pada objek tibble dan dampaknya terhadap mutasi chaining.
- [ ] Semantik baru dplyr >= 1.1.0: Penggunaan per-operation grouping context via argument `.by` vs persistent grouping `group_by()`.
- [ ] Mekanisme deteksi relationship pada mutating joins (`relationship = "one-to-one" | "many-to-many"`) dan mitigasi Cartesian explosion.
- [ ] Peran framework `vctrs` dalam menjaga *type stability* pada fungsi-fungsi penggabungan data (`bind_rows`, `pivot_longer`).
- [ ] Perbedaan trade-off performa: Eager execution (in-memory tibble) vs Lazy evaluation engines (`dtplyr`, `dbplyr`, `arrow`).

### Saya tidak perlu menghafal:
- [ ] Seluruh varian helper function pada `tidyselect` (cukup pahami fungsi inti seperti `starts_with()`, `where()`, `any_of()`, `all_of()`).
- [ ] Setiap argumen esoteric opsional pada fungsi legacy dplyr (fokus pada interface modern dplyr 1.1.0+).
- [ ] Formula C++ internal hash-table indexing (cukup pahami kompleksitas waktu algoritma $O(N)$ vs $O(N \times M)$ pada non-indexed joins).

### Saya harus bisa melakukan:
- [ ] Menulis fungsi kustom kelas enterprise yang membungkus (wrapping) pipeline Tidyverse menggunakan tidy-eval (`{{ }}`) secara bebas bug.
- [ ] Melakukan troubleshooting dan profiling script Tidyverse yang mengalami degradasi memori dan performa CPU menggunakan profiler (`bench::mark`, `profvis`).
- [ ] Menstrukturkan dataset long-to-wide dan wide-to-long kompleks menggunakan `tidyr::pivot_longer()` dan `pivot_wider()` dengan spesifikasi multi-kolom dan dynamic typing.
- [ ] Merancang pipeline manipulasi data defensif yang mampu menolak silent data type coercion secara otomatis.
- [ ] Mengonversi pipeline analisis data dari data frame in-memory ke database/out-of-core streaming engine tanpa merusak logika Tidyverse.