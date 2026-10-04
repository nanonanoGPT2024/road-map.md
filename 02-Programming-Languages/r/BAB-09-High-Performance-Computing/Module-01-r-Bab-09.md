# Bab 09 Module 01: Metaprogramming, Abstract Syntax Tree (AST), dan Tidy Evaluation

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan memiliki kemampuan praktis terukur untuk:
* Menginspeksi dan membedah struktur internal kode R menjadi node-node *Abstract Syntax Tree* (AST) menggunakan representasi tipe data dasar R (`call`, `symbol`, `pairlist`, dan konstanta).
* Mengimplementasikan teknik *Non-Standard Evaluation* (NSE) secara aman tanpa menyebabkan kebocoran lingkungan eksekusi (*environment leakage*) atau *evaluation bugs*.
* Memanfaatkan pustaka `rlang` untuk menangkap (*quoting* via `enexpr`, `enquo`), memanipulasi (*unquoting* via `!!`, `!!!`), dan menyuntikkan ekspresi (*injection* via `inject()`).
* Mengonstruksi *quosures* untuk mengemas kode bersama lingkungan leksikal asalnya guna mencegah tabrakan nama (*name masking*) antara data mask dan global variables.
* Merancang fungsi data pipeline modular setara standar paket industri (seperti `dplyr` dan `ggplot2`) yang menerima nama kolom tanpa tanda kutip (*unquoted variable names*) secara deterministik dan *type-safe*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
* **Struktur Data Internal R**: Pemahaman mendalam tentang vektor atomik, list, atribut, dan representasi pointer `SEXP` pada C-level R.
* **Environments & Lexical Scoping**: Mekanisme hierarki *frame*, *parent environment*, pencarian simbol (*symbol lookup*), serta siklus hidup closure.
* **Lazy Evaluation**: Cara kerja *promises*, komponen ekspresi tunda (`PRMSXP`), dan titik evaluasi nilai (*force evaluation*).
* **Functional Programming**: Manipulasi fungsi tingkat tinggi (*higher-order functions*), `lapply`/`purrr::map`, dan penanganan argumen dinamis `...` (*dots*).

---

### 3. Concept
Metaprogramming dalam R adalah paradigma di mana kode diperlakukan sebagai data kelas satu (*code-as-data*). Komputasi dalam R tidak langsung mengeksekusi instruksi dari teks sumber; interpreter R terlebih dahulu mem-parsing teks menjadi struktur hierarki pohon yang dikenal sebagai **Abstract Syntax Tree (AST)**.

Secara internal, setiap node pada AST di R direpresentasikan oleh salah satu dari empat tipe objek:
1. **Constants (Konstanta)**: Nilai literal dasar seperti bilangan (`1L`, `3.14`), string (`"production"`), atau nilai logika (`TRUE`). Tipe-tipe ini dievaluasi langsung ke dirinya sendiri.
2. **Symbols / Names (`SYMSXP`)**: Pengidentifikasi yang merujuk pada objek tertentu dalam suatu *environment* (misalnya `x`, `total_revenue`, `mean`). Dibuat dengan fungsi `as.symbol()` atau `rlang::sym()`.
3. **Calls (`LANGSXP`)**: Representasi pemanggilan fungsi yang terstruktur sebagai *pairlist* rekursif di mana elemen pertama adalah fungsi yang dipanggil, diikuti oleh argumen-argumennya (misalnya `f(x, 1)`).
4. **Pairlists (`LISTSXP`)**: Struktur data *linked-list* internal R yang utamanya digunakan untuk menyimpan metadata argumen pada pemanggilan fungsi (*formal arguments*).

```
                      +-------------------+
                      | Call: `+`         |
                      +---------+---------+
                                |
             +------------------+------------------+
             |                                     |
    +--------v--------+                   +--------v--------+
    | Symbol: `x`     |                   | Call: `*`       |
    +-----------------+                   +--------+--------+
                                                   |
                                +------------------+------------------+
                                |                                     |
                       +--------v--------+                   +--------v--------+
                       | Symbol: `y`     |                   | Constant: `2`   |
                       +-----------------+                   +-----------------+
```

Evaluasi standar (*Standard Evaluation / SE*) mengevaluasi ekspresi segera berdasarkan *lexical scoping*. Sebaliknya, **Non-Standard Evaluation (NSE)** menunda evaluasi ekspresi tersebut, mengintersepsi AST-nya, memodifikasi strukturnya, atau mengevaluasinya terhadap konteks data buatan (*Data Mask* / `data.frame`) dan bukan terhadap *environment* eksekusi biasa. 

Untuk menyelesaikan masalah hilangnya konteks leksikal saat ekspresi diteruskan antar fungsi, sistem modern R mengadopsi **Tidy Evaluation**. Fondasi dari Tidy Evaluation adalah **Quosure**: struktur data yang menggabungkan ekspresi AST (*quoted code*) dengan *lexical environment* tempat ekspresi itu pertama kali didefinisikan.

---

### 4. Why
Pendekatan evaluasi standar mengharuskan argumen diteruskan sebagai string atau vektor indeks, yang menimbulkan masalah pada skala produksi:
* **Redundansi Kode (Boilerplate Bloat)**: Penggunaan string literal berulang kali (`df[["column_name"]]`) menghalangi optimasi kode, refaktorisasi statis, dan memicu risiko *runtime string typos*.
* **Expressiveness**: Domain-Specific Languages (DSL) seperti pipeline `tidyverse` atau `data.table` mengizinkan developer menulis query deklaratif yang bersih (`filter(status == "ACTIVE")` alih-alih `df[df$status == "ACTIVE", ]`).
* **Dynamic Pipeline Compilation**: Metaprogramming memungkinkan penyusunan query data secara programatis sebelum dieksekusi. Ini fundamental dalam interface database seperti `dbplyr`, di mana AST R ditranslasikan secara deterministik menjadi SQL AST sebelum dieksekusi di database engine remote.
* **Mencegah Evaluasi Dini (Premature Execution)**: NSE menahan evaluasi ekspresi yang berat secara komputasi hingga seluruh filter, transformasi, dan agregasi dirangkai menjadi satu rencana eksekusi (*execution plan*).

---

### 5. What
Komponen kunci dalam arsitektur Metaprogramming modern R berbasis `rlang`:

| Komponen | Deskripsi Teknis | Contoh Sintaks |
| :--- | :--- | :--- |
| **AST Node** | Objek fundamental representasi kode: konstanta, simbol, atau call. | `lobstr::ast(x + f(y))` |
| **Quoting (`expr` / `enexpr`)** | Menahan evaluasi ekspresi yang diberikan langsung (`expr`) atau yang diberikan oleh pemanggil via argumen promise (`enexpr`). | `rlang::expr(x + 1)`<br>`rlang::enexpr(arg)` |
| **Quosure (`quo` / `enquo`)** | Pasangan atomik antara AST ekspresi dan pointer *lexical environment*-nya. Mencegah bug evaluasi salah scope. | `rlang::quo(x + 1)`<br>`rlang::enquo(arg)` |
| **Unquoting (`!!` / Bang-Bang)** | Operator penyuntikan (*injection operator*) untuk menyisipkan nilai atau sub-pohon AST ke dalam ekspresi yang di-*quote*. | `rlang::expr(f(!!my_sym))` |
| **Big Bang (`!!!`)** | Operator penyuntikan untuk membongkar (*splice*) elemen-elemen list menjadi serangkaian argumen terpisah. | `rlang::expr(f(!!!my_list))` |
| **Data Mask** | Lingkungan sementara yang memetakan kolom-kolom `data.frame` sebagai variabel lokal, berada di depan rantai pencarian leksikal. | `eval_tidy(expr, data = df)` |
| **Pronouns (`.data`, `.env`)** | Pengidentifikasi eksplisit untuk mendisambiguasi variabel milik kolom dataset (`.data$x`) atau variabel environment lokal (`.env$x`). | `.data$val > .env$threshold` |

---

### 6. How
Alur kerja pemrosesan AST dan Tidy Evaluation dari kode mentah hingga evaluasi akhir:

```
[User Input: unquoted expression]
              |
              v
[Capture Phase: rlang::enquo()]
  --> Membekukan ekspresi (mencegah evaluasi promise)
  --> Mengemas AST bersama Environment pemanggil menjadi Quosure
              |
              v
[Inspection & Transformation: AST Manipulation]
  --> Validasi tipe node (symbol, call, constant)
  --> Substitusi / Penyuntikan sub-pohon via inject() dan `!!`
              |
              v
[Data Masking Construction]
  --> Membuat data mask dari target data frame
  --> Mengikat pronoun `.data` dan `.env`
              |
              v
[Evaluation Phase: rlang::eval_tidy()]
  --> Lookup 1: Pencarian nama simbol dalam data mask
  --> Lookup 2: Fallback ke quosure environment jika tidak ditemukan di data mask
  --> Menghasilkan output nilai komputasi
```

1. **Capture Phase**: Argumen fungsi ditangkap menggunakan `rlang::enquo(arg)`. R menahan evaluasi ekspresi pada promise frame dan membungkus ekspresi bersama environment-nya menjadi quosure.
2. **Transformation Phase**: Menggunakan `rlang::inject()`, quosure dibuka kembali untuk menerima injeksi variabel dinamis (misalnya variabel dinamis yang dibungkus `sym()` atau list argumen yang dibungkus `syms()`).
3. **Evaluation Phase**: Fungsi `rlang::eval_tidy()` menerima quosure yang telah ditransformasi bersama argumen dataset sebagai `data`. Kolom-kolom dataset diprioritaskan dalam pencarian simbol via data mask; jika simbol tidak ada di kolom dataset, pencarian otomatis jatuh ke lexical scope yang disimpan di dalam quosure.

---

### 7. Analogy
Bayangkan **Metaprogramming** seperti **arsitektur bangunan dan cetak biru (blueprint)**:
* **Standard Evaluation**: Anda memesan rumah jadi kepada kontraktor. Kontraktor langsung mendatangkan batu bata, semen, dan membangunnya saat itu juga. Anda menerima produk jadi berupa fisik bangunan.
* **Quoting (AST)**: Alih-alih mendatangkan semen, Anda meminta arsitek menggambarkan **cetak biru struktural** di atas kertas kalkir. Pada tahap ini, tidak ada batu bata yang diangkat; semuanya hanya representasi simbolis tata letak ruangan.
* **Unquoting / Injection (`!!`)**: Anda memiliki cetak biru generik untuk kamar tidur. Anda mengambil gambar spesifik sistem ventilasi AC dari lembar lain, memotongnya dengan gunting, dan menempelkannya tepat di ruang AC pada cetak biru generik tersebut.
* **Quosure**: Cetak biru yang ditempeli catatan legal berisi daftar spesifikasi material dan koordinat GPS tanah tempat rumah itu diizinkan untuk dibangun (lingkungan asalnya).
* **Evaluation against Data Mask**: Anda menyerahkan cetak biru modifikasi beserta sertifikat tanah ke mandor proyek yang membawa bahan bangunan (kolom dataset). Rumah baru dibangun secara fisik tepat di atas lahan yang ditentukan.

---

### 8. Diagram
Berikut adalah visualisasi arsitektur evaluasi *Data Masking* dengan Quosure dan pencegahan tabrakan simbol leksikal:

```
+-----------------------------------------------------------------------------------+
| EKSEKUSI TIDY EVALUATION: eval_tidy(quo, data = df)                              |
+-----------------------------------------------------------------------------------+
                                          |
            +-----------------------------+-----------------------------+
            |                                                           |
            v                                                           v
  +--------------------+                                      +--------------------+
  |      DATA MASK     |                                      |      QUOSURE       |
  |  (Priority Level 1)|                                      |  (Priority Level 2)|
  +--------------------+                                      +--------------------+
  | Kolom dataframe    |                                      | - Ekspresi AST     |
  | df$x: [10, 20, 30] |                                      |   expr: x + cutoff |
  | df$y: [ 1,  2,  3] |                                      | - Lexical Env:     |
  | Pronoun: .data     |                                      |   cutoff <- 5      |
  +---------+----------+                                      |   Pronoun: .env    |
            |                                                 +---------+----------+
            |                                                           |
            | 1. Simbol 'x' dicari                                      |
            +----------------------> [ DITEMUKAN DI DATA MASK ]         |
            |                        Ambil df$x                         |
            |                                                           |
            | 2. Simbol 'cutoff' dicari                                 |
            +----------------------> [ TIDAK ADA DI DATA MASK ]         |
                                     Fallback ke Quosure Env            |
                                                                        v
                                     [ DITEMUKAN DI QUOSURE ENV ] <-----+
                                     Ambil cutoff = 5
                                          |
                                          v
                   +-----------------------------------------------+
                   | HASIL EVALUASI:                               |
                   | df$x + 5 = [15, 25, 35]                       |
                   +-----------------------------------------------+
```

---

### 9. Simple Example
Menangkap ekspresi, membedah struktur AST-nya secara manual menggunakan paket `lobstr`, lalu menyusun dan mengevaluasi kembali ekspresi tersebut via `rlang`.

```r
# Pastikan library terisolasi
suppressPackageStartupMessages({
  library(rlang)
  library(lobstr)
})

# 1. Inspeksi AST dari operasi matematika sederhana
target_code <- expr(result <- sum(base_val * 1.10) + offset)
cat("--- Struktur Pohon AST ---\n")
lobstr::ast(!!target_code)

# 2. Bedah elemen Call secara manual
cat("\n--- Dekonstruksi Node Call ---\n")
cat("Tipe Node      :", typeof(target_code), "\n")
cat("Operator Root  :", as_string(target_code[[1]]), "\n")
cat("Sisi Kiri (LHS):", as_string(target_code[[2]]), "\n")
cat("Sisi Kanan(RHS):", deparse(target_code[[3]]), "\n")

# 3. Dynamic Symbol Injection via rlang
variable_name <- "measured_latency"
metric_sym <- sym(variable_name)

# Buat ekspresi baru dengan menginjeksi simbol dinamis
dynamic_expr <- expr(mean(!!metric_sym, na.rm = TRUE))
cat("\n--- Ekspresi Terinjeksi ---\n")
print(dynamic_expr)

# 4. Evaluasi terhadap data konteks
mock_telemetry <- list(measured_latency = c(120, 145, 110, 300, 95))
calculated_metric <- eval_tidy(dynamic_expr, data = mock_telemetry)
cat("\nHasil Evaluasi :", calculated_metric, "\n")
```

---

### 10. Practical Example
Implementasi data quality filter engine tingkat produksi yang menerima filtering rule dinamis, parameter threshold aman, dan daftar metrik agregasi dinamis tanpa hardcoded variables.

```r
suppressPackageStartupMessages({
  library(rlang)
  library(dplyr)
})

#' Eksekusi Agregasi Data Dinamis Berbasis Tidy Evaluation
#'
#' @param data Data frame input transaksi
#' @param group_var Simbol kolom pengelompokan (unquoted)
#' @param metric_var Simbol kolom metrik yang dihitung (unquoted)
#' @param min_threshold Nilai filter batas bawah (skalar numerik)
#' @param custom_filter Ekspresi filter arbitrer tambahan (quosure opsional)
#' @return Aggregated data.frame
execute_secure_aggregation <- function(data,
                                       group_var,
                                       metric_var,
                                       min_threshold = 0,
                                       custom_filter = NULL) {
  # 1. Enquote input menjadi Quosure untuk mengunci konteks ekspresi dan env pemanggil
  group_var_quo   <- enquo(group_var)
  metric_var_quo  <- enquo(metric_var)
  custom_filt_quo <- enquo(custom_filter)

  # Validasi integritas argumen dasar
  stopifnot(is.data.frame(data))
  stopifnot(is.numeric(min_threshold) && length(min_threshold) == 1)

  # 2. Definisikan ekspresi filter dasar menggunakan pronoun .data dan .env
  # Mencegah tabrakan antara nama kolom 'min_threshold' dan argumen fungsi
  base_filter_expr <- expr(.data[[!!quo_name(metric_var_quo)]] >= .env$min_threshold)

  # 3. Rakit pipeline dinamis menggunakan rlang::inject
  result <- inject({
    pipeline <- data %>%
      filter(!!base_filter_expr)

    # Terapkan custom filter hanya jika dioperasikan oleh user
    if (!quo_is_null(custom_filt_quo)) {
      pipeline <- pipeline %>%
        filter(!!custom_filt_quo)
    }

    # Bangun nama dinamis kolom kalkulasi menggunakan dynamic dots ':='
    mean_col_name <- paste0("mean_", quo_name(metric_var_quo))
    p95_col_name  <- paste0("p95_", quo_name(metric_var_quo))

    pipeline %>%
      group_by(!!group_var_quo) %>%
      summarise(
        row_count       = n(),
        !!mean_col_name := mean(!!metric_var_quo, na.rm = TRUE),
        !!p95_col_name  := stats::quantile(!!metric_var_quo, probs = 0.95, na.rm = TRUE),
        .groups         = "drop"
      )
  })

  return(result)
}

# --- Eksekusi Pembuktian Produksi ---
set.seed(42)
financial_ledger <- data.frame(
  datacenter_id = rep(c("DC-SG1", "DC-US1", "DC-EU1"), each = 100),
  latency_ms    = c(rnorm(100, 45, 5), rnorm(100, 180, 20), rnorm(100, 90, 10)),
  tx_status     = sample(c("SUCCESS", "FAILED"), 300, replace = TRUE, prob = c(0.9, 0.1))
)

# Pemanggilan aman dengan unquoted variables & custom expression
latency_summary <- execute_secure_aggregation(
  data           = financial_ledger,
  group_var      = datacenter_id,
  metric_var     = latency_ms,
  min_threshold  = 40.0,
  custom_filter  = tx_status == "SUCCESS"
)

print(latency_summary)
```

---

### 11. Real World Example
**Skenario**: Sistem Risk Analytics pada Platform FinTech Skala Besar.  
**Masalah**: Tim *Credit Risk Modeling* membutuhkan framework pembuatan profil risiko peminjam yang dapat menerima daftar aturan (*rulebook*) berformat konfigurasi eksternal (JSON/YAML) yang diterjemahkan menjadi ratusan agregasi sub-dimensi. Pendekatan standard evaluation lambat dan rentan runtime parsing error jika menggunakan `eval(parse(text = ...))`. Pendekatan Tidy Evaluation berikut mengubah definisi DSL analitik menjadi pipeline komputasi AST yang sepenuhnya tervalidasi.

```r
suppressPackageStartupMessages({
  library(rlang)
  library(dplyr)
  library(purrr)
})

#' Risk Engine: Mengonversi Aturan Deklaratif Menjadi AST Execution Plan
#'
#' @param ledger_data Dataframe transaksi nasabah
#' @param rule_definitions Representasi terurai dari file konfigurasi eksternal
#' @return Data frame dengan skor risiko yang telah teragregasi
compile_risk_engine <- function(ledger_data, rule_definitions) {
  stopifnot(is.data.frame(ledger_data))
  
  # 1. Parsing konfigurasi string menjadi list of calls secara deterministik
  # Menghindari eval(parse(text=...)) yang tidak aman terhadap injection
  filter_expressions <- map(rule_definitions$global_filters, function(f_str) {
    parse_expr(f_str)
  })
  
  # 2. Transformasikan metric rules menjadi dynamic naming injection pairs
  # Format target: name := agg_function(target_column)
  aggregation_quosures <- map(rule_definitions$aggregations, function(agg_item) {
    target_sym <- sym(agg_item$target_field)
    agg_fn_sym <- sym(agg_item$aggregator)
    
    # Konstruksi AST Call: agg_fn(target_field, na.rm = TRUE)
    call_expr <- call2(agg_fn_sym, target_sym, na.rm = TRUE)
    return(call_expr)
  }) %>% set_names(map_chr(rule_definitions$aggregations, ~ .x$output_alias))

  grouping_syms <- syms(rule_definitions$dimensions)

  # 3. Evaluasi Pipeline dengan Dynamic Splicing (!!!)
  engine_output <- inject({
    pipeline <- ledger_data
    
    # Reduksi seluruh filter AST secara berantai
    for (f_expr in filter_expressions) {
      pipeline <- pipeline %>% filter(!!f_expr)
    }
    
    # Terapkan pengelompokan dan agregasi dinamis
    pipeline %>%
      group_by(!!!grouping_syms) %>%
      summarise(
        !!!aggregation_quosures,
        .groups = "drop"
      )
  })

  return(engine_output)
}

# --- Eksekusi Engine di Lingkungan Mock FinTech ---
customer_transactions <- data.frame(
  account_id   = c("ACC-01", "ACC-01", "ACC-02", "ACC-02", "ACC-03", "ACC-03"),
  risk_bracket = c("TIER_A", "TIER_A", "TIER_B", "TIER_B", "TIER_A", "TIER_A"),
  amount_usd   = c(500, 12000, 300, 450, 8000, 9500),
  is_flagged   = c(FALSE, FALSE, FALSE, TRUE, FALSE, FALSE)
)

# Konfigurasi yang dibaca dari YAML/JSON sistem manajemen risiko
risk_rules_json_payload <- list(
  dimensions = c("risk_bracket"),
  global_filters = list(
    "is_flagged == FALSE",
    "amount_usd > 400"
  ),
  aggregations = list(
    list(output_alias = "total_exposure", aggregator = "sum",  target_field = "amount_usd"),
    list(output_alias = "average_ticket", aggregator = "mean", target_field = "amount_usd"),
    list(output_alias = "peak_single_tx", aggregator = "max",  target_field = "amount_usd")
  )
)

# Eksekusi engine analitik
risk_summary <- compile_risk_engine(customer_transactions, risk_rules_json_payload)
print(risk_summary)
```

---

### 12. Trade-offs

| Parameter | Metaprogramming & Tidy Eval (`rlang`) | Standard Evaluation / Direct Character Passing | Base R NSE (`substitute` + `eval`) |
| :--- | :--- | :--- | :--- |
| **Advantages** | Robust terhadap environment leakage, modular, mendukung syntax injection ekspresif (`!!`, `!!!`), integrasi native ekosistem modern. | Implementasi sangat sederhana, performa tercepat tanpa overhead parsing/quoting, transparan terhadap profiling. | Bawaan bahasa R tanpa dependency library pihak ketiga, fleksibel untuk modifikasi tingkat rendah. |
| **Disadvantages** | *Learning curve* curam, kompleksitas mental tinggi terkait perbedaan tipe node AST, dependensi pada paket `rlang`. | Kode pemanggil menjadi repetitif, tidak dapat membangun DSL yang bersih dan deklaratif. | Rentan terhadap *scoping bugs* fatal; ekspresi dapat mengevaluasi objek lokal alih-alih data frame secara silent. |
| **Complexity** | **Tinggi**: Membutuhkan pemisahan tegas antara Quote-time, Injection-time, dan Evaluation-time. | **Rendah**: Memanipulasi string standar atau data frame indexing (`df[[var]]`). | **Tinggi-Ekstrem**: Pengelolaan *parent.frame()* manual yang sangat rawan memicu heisenbugs. |
| **Performance** | **Moderat**: Penambahan overhead mikrodetik per pemanggilan fungsi akibat pembuatan Quosure dan Data Masking. | **Maksimal**: Hampir nol alokasi overhead tambahan di luar eksekusi algoritma data processing. | **Moderat**: Mirip `rlang`, namun berisiko alokasi memori berlebih jika scope duplikasi tidak terkendali. |
| **Cost** | Biaya pemeliharaan rendah untuk arsitektur library/framework skala besar; stabil dan testable. | Biaya refaktorisasi tinggi ketika spesifikasi pipeline analitik berkembang menjadi dinamis. | Biaya debugging sangat mahal di produksi ketika terjadi tabrakan nama variabel pada caller environment. |

---

### 13. When To Use
* **Library/Package Development**: Anda membangun modul atau framework analitik internal yang digunakan oleh engineer/data scientist lain dengan antarmuka yang setara dengan standard R packages.
* **Dynamic Pipeline Composition**: Parameter filter, variabel target regresi, atau kolom partisi baru diketahui saat *runtime* (misalnya dari request HTTP API atau antrean Redis).
* **Domain Specific Language (DSL)**: Membangun abstraksi deklaratif di atas R, seperti penerjemah query data ke dialect tertentu (misal: R ke Elasticsearch query DSL atau SQL).
* **Disambiguasi Konteks Data**: Menjamin secara matematis bahwa variabel kolom tabel tidak akan pernah terdistorsi oleh variabel lokal yang memiliki nama yang identik di dalam workspace pengguna.

---

### 14. When NOT To Use
* **Tight Micro-iteration Loops**: Di dalam blok loop kritis (misalnya iterasi optimisasi MCMC atau algoritma numerik tingkat jutaan iterasi) di mana overhead nanodetik dari pembuatan environment mask dan AST wrapping akan mengorbankan performa sistem secara agregat.
* **Penggunaan Vektor Kolom Sederhana**: Ketika Anda hanya perlu mengakses kolom statis yang sudah ditentukan; gunakan standard index operator `[[` atau `.subset2`.
* **Proyek Scripting Linier Ad-Hoc**: Script analisis sekali pakai berukuran kecil di mana kesederhanaan pembacaan kode linier lebih berharga daripada fleksibilitas arsitektural AST.

---

### 15. Common Mistakes
* **Menggunakan `eval(parse(text = ...))`**: Pola ini merupakan celah keamanan fatal (*code injection vulnerability*) dan menonaktifkan kemampuan parser internal R untuk mengoptimalkan memori AST.
* **Kebingungan antara `!!` (Bang-Bang) dan `!!!` (Big Bang)**: Menggunakan `!!` pada list argumen, yang menyebabkan list disuntikkan sebagai satu objek nested alih-alih diurai menjadi pasangan argumen-argumen individual.
* **Name Masking Confusion**: Lupa menggunakan prefix pronoun `.data$` atau `.env$`, sehingga ketika pengguna memiliki variabel lokal bernama `x` dan data frame juga memiliki kolom bernama `x`, interpreter mengevaluasi variabel yang salah tanpa peringatan (*silent logical bug*).
* **Double Evaluation**: Mengevaluasi ekspresi tunda lebih dari sekali, yang dapat memicu efek samping (*side effects*) yang fatal jika ekspresi tersebut memuat mutasi state atau panggilan generator acak.

---

### 16. Best Practices (Production Checklist)
* [ ] **Wajib Quosure untuk Eksternal Parameter**: Selalu tangkap argumen yang berpotensi memuat ekspresi kontekstual menggunakan `rlang::enquo()` atau `rlang::enquos()`.
* [ ] **Gunakan Pronoun `.data` dan `.env`**: Di dalam ekspresi komputasi internal, selalu rujuk kolom secara eksplisit via `.data[[var_name]]` atau `.data$var` dan variabel luar via `.env$var`.
* [ ] **Isolasi Unquoting ke Titik Penyuntikan Tunggal**: Jangan menyebarkan pemanggilan `!!` secara liar; batasi injeksi hanya di dalam blok `rlang::inject()` yang terisolasi dan mudah dibaca.
* [ ] **Validasi Tipe Node AST**: Saat menerima formula atau ekspresi dari client, periksa apakah node bertipe `is_symbol()`, `is_call()`, atau `is_syntactic_literal()` sebelum dieksekusi.
* [ ] **Hindari Base NSE di Produksi**: Gantikan fungsi-fungsi warisan seperti `substitute()`, `eval()`, `as.name()` dengan padanan `rlang` yang deterministik (`expr()`, `eval_tidy()`, `sym()`).
* [ ] **Unit-Test AST Output**: Tulis unit test yang memeriksa hasil representasi string AST (`rlang::expr_text()`) dari fungsi pembangun query sebelum menguji hasil evaluasi datanya.

---

### 17. Troubleshooting

#### 1. Kesalahan "Object not found" Saat Evaluasi Kolom Dinamis
* **Penyebab**: Simbol diteruskan sebagai string biasa, namun dievaluasi langsung oleh engine tanpa diubah menjadi symbol node terlebih dahulu.
* **Investigasi**:
  ```r
  col_str <- "total_amount"
  # Salah: expr(sum(col_str)) -> menghasilkan mean("total_amount") -> Error
  ```
* **Solusi**:
  ```r
  # Benar: Konversi string menjadi symbol AST node terlebih dahulu
  col_sym <- rlang::sym(col_str)
  valid_expr <- rlang::expr(sum(!!col_sym, na.rm = TRUE))
  ```

#### 2. Debugging Struktur Ekspresi dengan `qq_show`
Jika hasil penyuntikan AST menggunakan operator `!!` atau `!!!` menghasilkan komputasi aneh, inspeksi ekspresi yang dihasilkan sebelum evaluasi dilakukan:
```r
library(rlang)
filter_col <- sym("latency")
limit_val  <- 200

# qq_show menampilkan representasi tepat bagaimana R melihat ekspresi setelah unquoting
rlang::qq_show(
  df %>% filter(!!filter_col > !!limit_val)
)
# Output terverifikasi: df %>% filter(latency > 200)
```

#### 3. Kebocoran Variabel Lingkungan (*Scope Leakage*)
* **Masalah**: Fungsi membaca nilai variabel dari Global Environment alih-alih variabel yang diteruskan di argumen fungsi.
* **Solusi**: Gunakan quosures (`enquo`) untuk mengunci leksikal scope pemanggil, lalu evaluasi menggunakan `eval_tidy()` dengan data mask yang didefinisikan secara eksplisit.

---

### 18. Exercise
Selesaikan 3 tugas pemrograman di bawah ini menggunakan paradigma Metaprogramming & Tidy Evaluation berbasis `rlang`:

1. **Exercise 1: Safe Variable Selector**  
   Tulis fungsi `safe_select(df, ...)` yang menerima sembarang simbol nama kolom tanpa tanda kutip menggunakan dynamic dots (`...`), memvalidasi bahwa setiap simbol benar-benar ada di dalam `colnames(df)`, lalu mengembalikan subset dataset tersebut. Jika ada kolom yang tidak ditemukan, lemparkan error terstruktur (`rlang::abort`).

2. **Exercise 2: AST Mutation Engine**  
   Buat fungsi `flip_arithmetic_operators(call_expr)` yang menerima sebuah AST Call matematika sederhana (hanya memuat operator biner `+` dan `-`), lalu membalik semua operasi: ubah setiap node pemanggilan `+` menjadi `-` dan sebaliknya secara rekursif ke seluruh sub-tree AST.

3. **Exercise 3: Dynamic Multi-Condition Filter**  
   Bangun fungsi `build_threshold_filter(column_names, thresholds, operators)` di mana ketiganya adalah vektor atomik berukuran sama. Fungsi harus menghasilkan satu AST call tunggal yang menggabungkan seluruh kondisi tersebut dengan operator logika `&`. Contoh input: `column_names = c("age", "salary")`, `thresholds = c(21, 50000)`, `operators = c(">=", ">")` harus menghasilkan ekspresi AST: `age >= 21 & salary > 50000`.

---

### 19. Challenge
Rancang dan bangun sebuah **Mini Query Engine** bernama `ast_sql_transpiler` yang membedah ekspresi filtering R berbasis data-masking dan mentranslasikannya menjadi string klausa SQL `WHERE` secara deterministik tanpa mengevaluasi data secara lokal di memori R.

**Spesifikasi Teknis:**
* Fungsi menerima ekspresi filter R tunggal melalui `enexpr()`, contoh: `transpile_where(latency <= 100 & (status == "TIMEOUT" | retries > 3))`.
* Fungsi harus menelusuri pohon AST secara rekursif.
* Mapping operator R ke SQL:
  * `==` diterjemahkan menjadi `=`
  * `!=` diterjemahkan menjadi `<>`
  * `&` diterjemahkan menjadi `AND`
  * `|` diterjemahkan menjadi `OR`
  * Call perkalian, pembagian, penambahan, dan pengurangan dipertahankan format infix-nya.
* Simbol R harus dikonversi menjadi identitas kolom SQL (misal: `latency`).
* Literal string harus dibungkus dengan single quotes SQL (`'TIMEOUT'`).
* Literal numerik harus dikonversi presisi menjadi teks.
* Fungsi harus melempar error via `rlang::abort()` jika ekspresi memuat pemanggilan fungsi yang tidak diizinkan (misalnya fungsi arbitrary R seperti `system("ls")` atau `mean(x)`).

Pastikan implementasi menangani nested grouping (tanda kurung di AST) dengan memetakan call `(` secara benar ke sintaks kurung SQL. Uji fungsi Anda dengan skenario filter kompleks.

---

### 20. Summary
* **Code as Data**: R memperlakukan kode sebagai pohon ekspresi (AST) yang tersusun atas konstanta, simbol, calls, dan pairlists yang dapat dimanipulasi sebelum dieksekusi.
* **Tidy Evaluation Paradigm**: Memecahkan dualitas penelusuran simbol pada data science—membedakan antara variabel yang merupakan kolom dari dataset (*data context*) dan variabel yang merupakan objek di workspace/closure (*lexical context*).
* **Quosures Menjamin Skope**: Quosure adalah enkapsulasi formal antara ekspresi AST mentah dengan lingkungan leksikal asalnya, mencegah terjadinya evaluasi salah lingkup (*wrong context evaluation*).
* **Quoting vs Unquoting**: `expr()` dan `enquo()` menahan evaluasi ekspresi; operator `!!` dan `!!!` di dalam `inject()` membuka ekspresi tersebut untuk menyisipkan sub-pohon atau parameter dinamis.
* **Standard Produksi**: Metaprogramming modern R meninggalkan metode base `eval(parse(...))` dan `substitute()` yang rentan bug, beralih penuh ke framework `rlang` untuk menghasilkan kode yang aman, modular, dan berperforma tinggi.