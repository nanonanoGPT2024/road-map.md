# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Data Wrangling dengan Modern Tidyverse)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai konsep dan mekanika internal **Tidy Evaluation (`rlang`)**, termasuk *data masking*, *injection operator* (`{{ }}` / *embrace*), *quosures*, serta penanganan *environment pollution*.
- Mendesain pipeline data skala enterprise dengan manipulasi struktur kompleks (*nested dataframes*, *list-columns*, `hoist()`, `unnest_wider()`, `unnest_longer()`).
- Mengoptimalkan konsumsi memori dan throughput I/O melalui integrasi **Apache Arrow** bersama engine **`dplyr`** untuk data *larger-than-RAM* (out-of-core processing).
- Menerapkan arsitektur data transformation modular, *fault-tolerant*, dan siap produksi dengan pola fungsional (`purrr`), profiling latensi, dan integrasi pengujian data otomatis.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- Sintaksis dasar Tidyverse (`dplyr`, `tidyr`, `magrittr`/native pipe `|>`).
- Konsep dasar lingkungan (*environments*) dan evaluasi ekspresi pada R dasar (*base R*).
- Pengetahuan mengenai format data tabular, hierarkis (JSON/XML), serta dasar struktur memori R (*Copy-on-Modify semantics*).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Mekanika Tidy Evaluation & Non-Standard Evaluation (NSE)
R secara default mengimplementasikan evaluasi malas (*lazy evaluation*) berbasis objek `promise`. Objek `promise` membungkus ekspresi yang belum dievaluasi beserta *pointer* ke lingkungan tempat ekspresi tersebut dibuat. Tidyverse memanfaatkan sifat ini untuk mengimplementasikan **Non-Standard Evaluation (NSE)** via paket `rlang`.

```
          [ R Script Execution ]
                     |
                     v
             Expression Tree
                     |
            +--------+--------+
            |                 |
     Symbol / Value      Quosure (Expr + Env)
            |                 |
            v                 v
     Data Masking        rlang::eval_tidy()
            |                 |
            +--------+--------+
                     |
                     v
             [ Result Array ]
```

Dalam fungsi manipulasi standar Tidyverse (seperti `dplyr::mutate()` atau `dplyr::filter()`):
1. **Data Masking:** Objek `data.frame` atau `tibble` diubah menjadi prioritas pencarian simbol (*data mask*). Jika sebuah variabel ada di dalam data dan juga ada di dalam *global environment*, Tidyverse memprioritaskan kolom di dalam data mask (`.data`), kecuali secara eksplisit dirujuk via `.env`.
2. **Quosures:** Merupakan fusi antara ekspresi sintaksis (*Abstract Syntax Tree / AST*) dan lingkungan leksikal (*environment*). Quosure memastikan bahwa jika ekspresi mengevaluasi variabel lokal di luar `data.frame`, variabel tersebut di-resolusi dari *scope* pemanggil yang benar tanpa kebocoran (*hygienic macro evaluation*).
3. **AST Defusal & Injection:** Saat menulis wrapper function, ekspresi ditahan (*defused*) dari evaluasi instan. Operator `{{ x }}` (*embrace*) adalah singkatan tingkat tinggi dari `!!enquo(x)` (*unquote-enquote*), yang membuka AST dan menyuntikkannya langsung ke dalam konteks data mask target sebelum *evaluation engine* C++ (`dplyr` internals) mengeksekusinya.

### 3.2 List-Columns dan Representasi Memori
Di R, `data.frame` secara internal adalah sebuah `list` dari vektor-vektor dengan panjang yang identik. Karena elemen `list` generik dapat menampung sembarang objek R, kita dapat membuat **list-columns**, di mana setiap baris berisi vektor arbitrer, list lain, model statistik, atau nested JSON. 

Secara arsitektural:
- `tidyr::nest()` membagi data frame berdasarkan *grouping key* dan mengalokasikan sub-data frames ke dalam pointer list.
- `tidyr::hoist()` mengakses leaf node dari nested list secara langsung melalui pengindeksan internal C, memotong overhead iterasi R yang lambat dibandingkan pendekatan tradisional berbasis `purrr::map()`.
- **Copy-on-Modify (CoM)** dapat menjadi bottleneck performa. Saat melakukan mutasi pada list-columns secara sekuensial tanpa pre-alokasi atau in-place bindings, R menduplikasi wrapper list (shallow copy) atau bahkan seluruh leaf data (deep copy). Modul ini menggunakan idiom bebas alokasi redundan melalui Tidyverse backend.

### 3.3 Out-of-Core Processing: Apache Arrow Engine
Ketika data melebihi kapasitas RAM, `dplyr` bertindak sebagai *frontend interface* (DSL) yang ditautkan ke backend **Apache Arrow C++ Engine**.
- **Acero Execution Engine:** Arrow memetakan query Tidyverse (`filter`, `mutate`, `summarise`) menjadi *compute graphs*.
- **Zero-Copy Memory Sharing:** Dataset dibaca secara streaming dalam bentuk *RecordBatches* berbasis representasi kolom Arrow standar, menghindari konversi ke representasi R SEXP native sampai pemanggilan `collect()` dilakukan secara eksplisit.
- **Pushdown Predicates & Projection:** Filter dieksekusi di level file format (Parquet row-group filtering) sehingga baris dan kolom yang tidak relevan tidak pernah dimuat ke memori fisik host.

---

## 4. Why & What

| Dimensi | Pendekatan Skrip R Konvensional | Enterprise Modern Tidyverse Engine |
| :--- | :--- | :--- |
| **Abstraksi Kode** | Hardcoded column names, fragile terhadap perubahan skema. | Dynamic metaprogramming via `rlang` & tidy evaluation. |
| **Ekspresi Nested Data**| Loop imperatif (`for`), multiple table merges. | First-class list-columns, `hoist`, zero-copy vectorization. |
| **Skalabilitas Memori** | In-memory bound (`size < RAM/3`), OOM saat mutasi besar. | Integrasi Apache Arrow, Lazy query execution via `dbplyr`/`arrow`. |
| **Error Handling** | Skrip berhenti total saat error tunggal (*monolithic crash*). | Functional programming dengan `purrr::safely`/`possibly`, typed outputs. |
| **Arsitektur Validasi**| Inspeksi ad-hoc manual via `str()` atau `summary()`. | Strict assertion pipelines, programmatic schema contracts. |

---

## 5. How (Workflow Detail)

Alur kerja arsitektural pemrosesan data produksi dengan Modern Tidyverse:

```
[Raw Ingestion: Parquet/JSON/DB]
               |
               v
 [Dataset Pointer Engine (arrow/dbplyr)]  <--- Pushdown Optimization
               |
               v
 [Dynamic Wrangling Core (rlang + dplyr)] <--- Programmatic Abstractions
               |
               v
   [Complex Nested Reshaping (tidyr)]    <--- Hoist / Unnest Structural Ops
               |
               v
 [Fault-Tolerant Functional Flow (purrr)]<--- Safe/Type-Stable Executions
               |
               v
    [Materialization / collect()]        <--- In-Memory Enterprise Tibble
```

1. **Lazy Binding Phase:** Inisialisasi pointer dataset menggunakan `arrow::open_dataset()` atau koneksi database.
2. **Dynamic Query Construction:** Gunakan fungsi `rlang` untuk merancang fungsi kustom yang menerima nama kolom parametrik tanpa *hardcoding*.
3. **Filter & Projection Pushdown:** Terapkan operasi filtering awal agar engine C++ memangkas blok data yang tidak dibutuhkan langsung dari disk.
4. **Structured Mutation & Hoisting:** Lakukan flattening atau ekstraksi terhadap atribut nested payload (misal: JSON logs).
5. **Robust Functional Execution:** Petakan fungsi transformasi non-vektor melalui `purrr::safely` untuk mengisolasi kegagalan pada baris korup.
6. **Data Contract Assertion:** Validasi dimensi, tipe data, dan batasan nilai sebelum mengeksekusi pipeline write-back.

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem Tidy Evaluation seperti **Surat Kuasa Notaris**:
- **Standard Evaluation:** Anda memberikan uang tunai kepada agen dan agen langsung membelanjakannya saat itu juga.
- **Non-Standard Evaluation (Lazy):** Anda memberikan *instruksi bertulis* kepada agen: "Beli aset bernama `X`".
- **Tidy Eval / Quosure:** Agen membawa secarik instruksi ("Beli `X`") beserta *stempel notaris* yang mencatat lokasi hukum di mana `X` didefinisikan. Jika di dalam pasar (*data mask*) ada komoditas bernama `X`, ia membeli itu. Jika tidak ada di pasar, ia mencari di brankas pribadi Anda (*enclosing environment*). Operator `{{ }}` bertindak seperti mesin fotokopi dinamis yang mengganti kata `X` dengan nama riil yang Anda inginkan secara aman sebelum instruksi dibacakan di pasar.

```
       Global Environment                Data Frame Environment (.data)
    +-----------------------+              +-----------------------+
    | threshold <- 100      |              | id    val             |
    +-----------------------+              | 1     50              |
                |                          | 2     150             |
                |                          +-----------------------+
                |                                      |
                +-----------------+                    |
                                  |                    |
                                  v                    v
                   Expression: filter(df, val > threshold)
                                      |         |
                              Searched in:      Searched in:
                                [.data]          [.env]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Dynamic Tidy-Eval Aggregator
Penggunaan Tidy Eval dasar untuk memprogram fungsi agregasi dinamis tanpa rentan string injection:

```r
library(dplyr)
library(rlang)

# Enterprise pattern: Dynamic group-by and parameterized summarize
calculate_kpi <- function(data, group_col, metric_col, threshold = 0) {
  data |>
    # Injeksi nama kolom dinamis menggunakan {{ }}
    filter({{ metric_col }} > .env$threshold) |>
    group_by({{ group_col }}) |>
    summarise(
      record_count = n(),
      mean_metric  = mean({{ metric_col }}, na.rm = TRUE),
      iqr_metric   = IQR({{ metric_col }}, na.rm = TRUE),
      .groups      = "drop"
    )
}

# Eksekusi
calculate_kpi(iris, Species, Sepal.Length, threshold = 5.0)
```

### 7.2 Practical Example: Nested Log-Event Processor
Pemrosesan log JSON semi-terstruktur menggunakan kombinasi `tidyr::hoist`, `tidyr::unnest_longer`, dan abstraksi penanganan nilai null tingkat tinggi:

```r
library(tibble)
library(dplyr)
library(tidyr)
library(purrr)

# Data simulasi ingestion microservices (telemetri transaksi)
raw_event_payload <- tibble(
  event_id = c("evt_001", "evt_002", "evt_003"),
  received_at = as.POSIXct(c("2026-03-30 08:00:00", "2026-03-30 08:00:02", "2026-03-30 08:00:05")),
  payload = list(
    list(
      user_id = 9021,
      device = list(os = "iOS", version = "17.4"),
      tags = list("ecommerce", "checkout"),
      metrics = list(latency_ms = 42.1, status = 200)
    ),
    list(
      user_id = 8112,
      device = list(os = "Android", version = "14"),
      tags = list("ecommerce", "retry", "checkout"),
      metrics = list(latency_ms = 156.4, status = 500)
    ),
    list(
      user_id = 4553,
      device = list(os = "iOS", version = "17.2"),
      tags = list("browse"),
      metrics = list(latency_ms = 12.0, status = 200)
    )
  )
)

# Pipeline ekstraksi high-performance: hoist selective path parsing
processed_events <- raw_event_payload |>
  # Hoist langsung ke nested element tanpa mengurai keseluruhan dokumen
  hoist(
    payload,
    user_id = "user_id",
    device_os = list("device", "os"),
    latency = list("metrics", "latency_ms"),
    http_status = list("metrics", "status"),
    raw_tags = "tags"
  ) |>
  # Unnest nested vectors (1-to-many relationship expansion)
  unnest_longer(raw_tags, values_to = "tag") |>
  select(-payload) |>
  mutate(
    http_status = as.integer(http_status),
    is_anomaly = latency > 100 | http_status >= 500
  )

print(processed_events)
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario:
Sistem deteksi anomali finansial real-time core-banking. Memproses jutaan transaksi multi-currency secara streaming dari sink Apache Parquet, memvalidasi integritas metrik, mendeteksi *sliding-window outlier*, dan mengekstraksi atribut metadata dinamis menggunakan Tidyverse + Arrow framework.

```r
library(arrow)
library(dplyr)
library(rlang)
library(purrr)
library(lubridate)

# 1. SETUP ENGINE & PERSISTENCE POINTER
# Simulasikan arsitektur multi-file Parquet partitioned storage
temp_data_dir <- file.path(tempdir(), "banking_store")
dir.create(temp_data_dir, showWarnings = FALSE, recursive = TRUE)

mock_tx_data <- tibble(
  account_id = paste0("ACC_", rep(100:104, each = 2000)),
  tx_timestamp = rep(seq(as.POSIXct("2026-01-01 00:00:00", tz = "UTC"), 
                         by = "15 mins", length.out = 2000), 5),
  amount = c(rlnorm(9900, meanlog = 3, sdlog = 1), runif(100, min = 50000, max = 100000)),
  currency = sample(c("USD", "EUR", "IDR", "SGD"), 10000, replace = TRUE),
  risk_meta = sample(c('{"ip":"192.168.1.1","proxy":false}', 
                       '{"ip":"10.0.0.1","proxy":true}'), 10000, replace = TRUE)
)

# Tulis partitioned Parquet (Out-of-Core ready)
write_dataset(
  dataset = mock_tx_data,
  path = temp_data_dir,
  format = "parquet",
  partitioning = "currency"
)

# 2. FRAMEWORK ENTERPRISE PIPELINE: Dynamic Analytics Engine
generate_anomaly_report <- function(dataset_path, 
                                    target_currencies, 
                                    rolling_window_k = 5,
                                    variance_multiplier = 3.0) {
  
  # A. Lazy Arrow Data Binding
  ds <- open_dataset(dataset_path, format = "parquet")
  
  # B. Filter pushdown: Hanya currency yang ditargetkan yang ditarik dari storage
  filtered_query <- ds |>
    filter(currency %in% target_currencies) |>
    select(account_id, tx_timestamp, amount, currency, risk_meta)
  
  # C. Dynamic Expression Execution: rlang pipeline definition
  # Menghitung mean dan dynamic cutoff via Arrow pushdown aggregate
  global_stats <- filtered_query |>
    group_by(currency) |>
    summarise(
      mu = mean(amount, na.rm = TRUE),
      sigma = sd(amount, na.rm = TRUE),
      .groups = "drop"
    ) |>
    collect() # Materialisasi metrik agregat ringkas ke R RAM
  
  # Inject dynamic boundaries back into lazy stream
  # Memanfaatkan boundary untuk filtering baris tanpa load full data
  threshold_conditions <- global_stats |>
    pmap(function(currency, mu, sigma) {
      expr(currency == !!currency & amount > !!(mu + (variance_multiplier * sigma)))
    })
  
  combined_filter <- reduce(threshold_conditions, function(x, y) expr(!!x | !!y))
  
  # D. Targeted Outlier Extraction
  anomalies <- filtered_query |>
    filter(!!combined_filter) |>
    collect() # Materialisasi hanya data yang lolos threshold outlier
  
  # E. Advanced Transformation on Outlier Subset (Nested JSON Ingest)
  # Gunakan tidyr::hoist untuk parsing cepat string metadata
  final_report <- anomalies |>
    mutate(meta_parsed = purrr::map(risk_meta, ~ jsonlite::fromJSON(.x))) |>
    hoist(meta_parsed, 
          source_ip = "ip", 
          is_proxy = "proxy") |>
    select(-risk_meta, -meta_parsed) |>
    arrange(desc(amount))
  
  return(final_report)
}

# Eksekusi Pipeline
report <- generate_anomaly_report(
  dataset_path = temp_data_dir,
  target_currencies = c("USD", "EUR"),
  variance_multiplier = 2.5
)

head(report)

# Cleanup
unlink(temp_data_dir, recursive = TRUE)
```

---

## 9. Trade-offs

| Aspek | Pendekatan Pure In-Memory `dplyr` | Hybrid `arrow` + `dplyr` | Bare-Metal `data.table` |
| :--- | :--- | :--- | :--- |
| **Max Dataset Size** | Terbatas physical RAM host (idealnya < $0.3 \times$ RAM). | Terbatas kapasitas disk (Terabyte scale, out-of-core). | Terbatas physical RAM ($< 0.8 \times$ RAM). |
| **Latency (Sub-second)** | Cepat untuk $N < 10^6$, degradasi tajam saat Garbage Collection (GC) trigger. | Latensi parse query plan awal ~5-15ms, optimal pada streaming. | Ekstrem cepat (overhead mikrodetik, minimal GC footprint). |
| **Readability & Maintainability** | Sangat tinggi, deklaratif, composable via pipe. | Sangat tinggi, sintaks identik dengan standard dplyr. | Rendah/Menengah, sintaks ringkas berbasis C-style semantics `DT[i, j, by]`. |
| **Data Types Flexibility** | Mendukung seluruh tipe objek R natively (S3, S4, List-cols). | Terbatas pada skema Arrow yang kompatibel dengan C++. | Terbatas pada tipe vektor atomik standar dan list-columns dasar. |
| **Infrastructure Cost** | Tinggi (membutuhkan instance RAM jumbo seperti AWS `r6i` series). | Rendah (cukup instance compute-optimized seperti AWS `c6i` + NVMe). | Menengah (efisiensi alokasi memori in-place). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Evaluasi Dini Variabel Global (Environment Leaks)
*Mistake:* Menulis ekspresi fungsi di mana nama kolom bertabrakan dengan variabel di workspace pengguna.
```r
# BUG
threshold <- 0.5
df <- tibble(threshold = c(0.1, 0.9), value = c(10, 20))
df |> filter(value > threshold) # threshold ambigu: kolom atau variabel?
```
*Troubleshooting:* Secara eksplisit gunakan namespace pronon `.data` dan `.env`.
```r
# PRODUCTION FIX
df |> filter(value > .env$threshold) # Mereferensi global variable
df |> filter(.data$threshold > 0.5)   # Mereferensi kolom tabel
```

### 10.2 Copy-on-Modify Explosion pada Iterasi
*Mistake:* Menggunakan `mutate()` di dalam loop bertingkat atau pipeline sequential yang menghasilkan shallow copies terus-menerus pada tibble berukuran besar.
*Troubleshooting:* Manfaatkan `group_split()` secara bijak atau beralih ke vector-based window functions (`lead()`, `lag()`, `slider::slide_vec`) alih-alih per-row procedural mutation.

### 10.3 Injeksi Simbolik Menggunakan String Tradisional
*Mistake:* Mencoba mengevaluasi nama kolom dari input string dengan `as.name()` atau `parse()` yang rentan keamanan dan error.
*Troubleshooting:* Gunakan operator embrace `{{ col }}` jika argumen dilewatkan tanpa kutip (*symbolic*), atau konstruksi `sym()` / `syms()` dipadu dengan `!!` / `!!!` jika input berasal dari vector string external (misal: JSON payload / API request):
```r
col_name <- "transaction_val"
df |> filter(!!sym(col_name) > 100)
```

---

## 11. Best Practices (Production Checklist)

1. [ ] **Strict Typing:** Selalu tetapkan deklarasi skema tipe data eksplisit pada ingestion boundaries (`read_csv(col_types = ...)` atau Arrow schemas).
2. [ ] **Scope Disambiguation:** Tuliskan `.data$` dan `.env$` secara eksplisit di seluruh *reusable internal functions/packages* untuk mengeliminasi ambigu Tidy Eval.
3. [ ] **Predictable Returns:** Wrapper fungsi manipulasi data harus selalu mengembalikan objek dengan struktur konstan (*type stability*). Hindari return `NULL` jika hasil kosong; kembalikan empty tibble dengan skema yang sama (`slice(0)`).
4. [ ] **Unnest Guard:** Saat mengeksekusi `unnest_longer()` atau `unnest_wider()`, definisikan parameter `names_sep` atau `repair_names` secara eksplisit untuk mencegah kolisi nama kolom secara silent.
5. [ ] **Garbage Collector Hygiene:** Bersihkan objek-objek masif sementara menggunakan `rm(obj); gc()` setelah pemanggilan `collect()` dari pipeline out-of-core.
6. [ ] **AST Defusal Separation:** Pisahkan logika parsing AST (`rlang::enquo`) dari komputasi numerik intensif untuk memfasilitasi modular unit-testing.

---

## 12. Hands-on Practice (hands-on/m02/)

Simpan skrip berikut ke dalam workspace lokal: `hands-on/m02/enterprise_wrangling.R`.

### Langkah 1: Siapkan Environment dan Data Multi-Level
```r
# hands-on/m02/enterprise_wrangling.R
suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(purrr)
  library(rlang)
})

set.seed(42)
n_records <- 1000

audit_db <- tibble(
  audit_id = sprintf("AUD-%04d", 1:n_records),
  region = sample(c("APAC", "EMEA", "LATAM", "NA"), n_records, replace = TRUE),
  logs = replicate(n_records, {
    n_entries <- sample(1:4, 1)
    tibble(
      timestamp = seq.POSIXt(as.POSIXct("2026-03-01"), length.out = n_entries, by = "hour"),
      action = sample(c("LOGIN", "MUTATE", "DELETE", "EXPORT"), n_entries, replace = TRUE),
      duration_ms = runif(n_entries, 10, 500)
    )
  }, simplify = FALSE)
)
```

### Langkah 2: Buat Custom Parametric Tidy-Eval Extractor
```r
# Ekstraktor yang mentransformasi nested structure secara dinamis
extract_audit_metrics <- function(data, filter_action, group_var) {
  action_str <- rlang::enexpr(filter_action) |> as_label()
  
  data |>
    # 1. Unnest logs data
    unnest_longer(logs) |>
    # 2. Hoist log properties
    hoist(logs,
      action = "action",
      duration_ms = "duration_ms"
    ) |>
    # 3. Dynamic Filter menggunakan inject
    filter(action == !!action_str) |>
    # 4. Aggregasi berdasarkan variabel dinamis
    group_by({{ group_var }}) |>
    summarise(
      total_operations = n(),
      avg_latency = mean(duration_ms, na.rm = TRUE),
      p95_latency = quantile(duration_ms, 0.95),
      .groups = "drop"
    )
}
```

### Langkah 3: Eksekusi dan Verifikasi Pipeline
```r
# Jalankan untuk action "MUTATE" di-group berdasarkan region
res_mutate <- extract_audit_metrics(audit_db, "MUTATE", region)
print("--- Hasil Metrik MUTATE ---")
print(res_mutate)

# Jalankan untuk action "EXPORT" di-group berdasarkan region
res_export <- extract_audit_metrics(audit_db, "EXPORT", region)
print("--- Hasil Metrik EXPORT ---")
print(res_export)
```

---

## 13. Exercise

### Level Easy
Tuliskan fungsi bernama `filter_and_count()` yang menerima tiga parameter: `data`, `filter_col`, dan `min_val`. Fungsi tersebut harus menyaring data di mana `filter_col > min_val` dan mengembalikan nilai skalar berupa jumlah baris yang tersisa, menggunakan sintaks *embrace operator* `{{ }}`.

### Level Medium
Diberikan tibble berikut:
```r
orders <- tibble(
  order_id = 101:103,
  items = list(
    list(c(sku = "A", qty = 2), c(sku = "B", qty = 5)),
    list(c(sku = "C", qty = 1)),
    list(c(sku = "A", qty = 1), c(sku = "D", qty = 10))
  )
)
```
Gunakan fungsi-fungsi dari `tidyr` (`unnest_longer`, `hoist`, dsb.) untuk menghasilkan bentuk flat tabel dengan kolom: `order_id` (integer), `sku` (character), dan `qty` (integer).

### Level Hard
Buat fungsi produksi `dynamic_multi_aggregate(data, group_cols, target_cols, aggregations)`.
- `group_cols`: Karakter vektor kolom grouping (misal: `c("region", "department")`).
- `target_cols`: Karakter vektor kolom nilai (misal: `c("salary", "bonus")`).
- `aggregations`: Karakter vektor operasi dasar (misal: `c("mean", "median", "sd")`).
Fungsi harus membangun seluruh ekspresi kalkulasi via `rlang` secara programatik (tanpa loop manual baris-per-baris), menerapkan `across()`, dan memproduksi nama kolom output yang terstandarisasi (`salary_mean`, `salary_median`, dst).

---

## 14. Challenge

**Skenario Tantangan:**
Perusahaan AdTech Anda menangani event tracking klik iklan yang disimpan dalam ribuan berkas log multi-tingkat. Setiap event membawa array dinamis `custom_dimensions` yang berisi key-value pair arbitrer (contoh: `[{"k": "campaign", "v": "promo_ramadhan"}, {"k": "ab_test", "v": "variant_b"}]`).

**Requirement:**
1. Desainlah fungsi pipeline yang mengonsumsi raw streaming list-column berisi pasangan key-value array tersebut.
2. Secara dinamis pivot list tersebut menjadi kolom tabel riil (*wide format*) tanpa mengetahui sebelumnya apa saja nama `key` yang akan muncul.
3. Fungsi harus memiliki batas toleransi kegagalan (*fault-tolerant*): jika suatu baris memiliki struktur korup (misal skalar alih-alih list of pairs), sistem tidak boleh *crash*. Baris tersebut harus diarahkan ke list-column terpisah bernama `failed_payloads` menggunakan pola `purrr::safely`.
4. Seluruh komputasi harus beroperasi tanpa hardcoding nama atribut dan harus melewati assertions performa memori (profiling overhead harus didokumentasikan).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Apa perbedaan mendasar antara evaluasi standar (*Standard Evaluation*) dan *Non-Standard Evaluation* (NSE) dalam R?
2. Mengapa sintaks `.data$col_name` lebih direkomendasikan pada paket R enterprise dibandingkan hanya memanggil `col_name`?
3. Sebutkan perbedaan perilaku fungsional antara `tidyr::unnest_longer()` dan `tidyr::unnest_wider()`.
4. Kapan kita harus menggunakan operator `{{ }}` dibandingkan operator `!!`?
5. Mengapa pipeline Arrow + `dplyr` secara signifikan lebih hemat memori dibandingkan pemrosesan standar native `dplyr`?

### 15.2 Pertanyaan Intermediate
6. Jelaskan bagaimana konsep *quosure* menyelesaikan masalah *lexical scoping leak* saat sebuah fungsi Tidyverse dipanggil di dalam lingkungan lokal modul lain.
7. Apa yang terjadi di balik layar saat kita memanggil fungsi `collect()` pada objek Arrow Dataset / Table di pipeline R?
8. Bandingkan efisiensi komputasi antara `tidyr::hoist()` dan kombinasi `purrr::map()` + `dplyr::mutate()` saat mengurai struktur JSON dengan kedalaman tinggi (*deeply nested*).
9. Bagaimana cara menyuntikkan daftar simbol dinamis (vektor karakter) ke dalam klausul `group_by()` menggunakan `rlang`?
10. Apa risiko penggunaan `eval(parse(text = ...))` dibandingkan pendekatan AST manipulation Tidy Evaluation (`sym()`, `parse_expr()`)?

### 15.3 Skenario Kasus Produksi
11. **Kasus 1:** Sebuah cron-job R harian yang memproses data analitik web sering mengalami crash `Out Of Memory (OOM)` saat volume log bulanan melonjak 300%. Berikan rekomendasi arsitektural konkret untuk restrukturisasi pipeline Tidyverse tersebut tanpa meninggalkan sintaks `dplyr`.
12. **Kasus 2:** Tim data engineering Anda mengeluhkan bahwa fungsi transformasi custom buatan tim data science berjalan 20 kali lebih lambat ketika dijalankan di cluster produksi. Setelah diinspeksi, fungsi tersebut memanggil `mutate()` di dalam perulangan `lapply` pada sub-elemen nested dataframe. Bagaimana solusi refactor berbasis idiom Tidyverse modern?
13. **Kasus 3:** Pipeline ekstraksi event streaming Anda menghadapi schema drift, di mana field numerik `response_time` kadang terisi string `"timeout"` atau array kosong `[]`. Bagaimana menyusun pipeline defensif yang menjamin skema output stabil tanpa menghentikan streaming run?

---

## 16. Summary

- **Tidy Evaluation Runtime:** Mekanisme evaluasi malas `rlang` memungkinkan metaprogramming tingkat tinggi melalui integrasi *data masking* (`.data`), *injection* (`{{ }}`), dan ekspresi quosure yang aman secara leksikal.
- **Nested Structures:** List-columns pada tibble memberikan fleksibilitas struktural hierarkis; gunakan `hoist()` untuk parsing node selektif dengan performa C backend, serta `unnest_longer()`/`unnest_wider()` untuk normalisasi relasional.
- **Enterprise Scalability:** Integrasi engine Apache Arrow memindahkan beban manipulasi berat ke eksekusi berbasis disk/streaming C++ via predicative pushdowns, membatasi alokasi RAM R hanya pada hasil agregat (`collect()`).
- **Production Readiness:** Keandalan pipeline enterprise mensyaratkan penulisan kode fungsional murni (`purrr`), strict namespace disambiguation (`.data$` vs `.env$`), pemisahan evaluasi AST yang terkontrol, dan pertahanan terhadap data malformed.