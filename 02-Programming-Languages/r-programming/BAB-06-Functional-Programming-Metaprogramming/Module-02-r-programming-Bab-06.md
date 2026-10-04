# Kurikulum Enterprise R-Programming
## Kategori: 02-Programming-Languages
### BAB 06: Functional Programming & Metaprogramming
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah Internal Abstract Syntax Tree (AST)** pada R menggunakan `lobstr` dan `rlang` untuk memahami representasi kode secara hierarkis (Calls, Symbols, Literals, Pairlists).
- **Merancang Higher-Order Functions (HOF), Function Factories, dan Adverbial Pipelines** menggunakan `purrr` secara tangguh (*fault-tolerant*) dan *parallel-ready* (`furrr`) untuk beban komputasi masif.
- **Menguasai Teori & Implementasi Non-Standard Evaluation (NSE) / Tidy Evaluation**, mencakup konsep defusal (`enquo`, `expr`), quasiquotation (`!!`, `!!!`), dynamic dots (`:=`), dan contextual injection (`inject()`, `eval_tidy()`).
- **Memitigasi Variabel Masking dan Ambiguity Collision** antara lingkungan data (`.data`) dan lingkungan eksekusi (`.env`).
- **Membangun Arsitektur Domain-Specific Language (DSL) dan Rule-Engine Dinamis** siap pakai untuk tingkat *enterprise* yang aman dari injeksi kode, dapat diaudit, serta efisien secara alokasi memori.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Base R Fundamentals**: Lingkungan (*environments*), *lexical scoping*, struktur data dasar (vektor, *list*, *data frame*), dan semantik pemanggilan fungsi.
- **BAB 06 Modul 01**: Dasar Functional Programming (pemahaman fungsi murni, *first-class functions*, dan pengenalan fungsi dasar `map()`).
- **Sistem Memori R**: Pemahaman dasar tentang alokasi memori heap, *Garbage Collector* (GC), dan semantik *Copy-on-Modify*.
- **Package Terpasang**: `rlang` (>= 1.1.0), `purrr` (>= 1.0.0), `lobstr` (>= 0.2.0), `dplyr` (>= 1.1.0), `furrr` (>= 0.3.0).

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi Representasi Kode R: AST, Expression, dan Call Objects
Di dalam runtime R, kode program tidak langsung dieksekusi sebagai teks mentah atau bytecode murni, melainkan diurai (*parsed*) menjadi struktur data **Abstract Syntax Tree (AST)**. R adalah bahasa homoikonik (*homoiconic-like*): kode R direpresentasikan menggunakan struktur data internal R itu sendiri.

Komponen-komponen AST R di tingkat internal C-level:
1. **Literals (Constants)**: Nilai skalar atomik (e.g., `1L`, `"hello"`, `TRUE`). Tipe internal C: `INTSXP`, `STRSXP`, `LGLSXP`.
2. **Symbols (Names)**: Pengenal (*identifier*) yang mereferensikan suatu objek di memori. Tipe internal: `SYMSXP`.
3. **Calls**: Pemanggilan fungsi berupa daftar rekursif (*recursive list-like structure*) di mana elemen pertama adalah fungsi yang dipanggil, diikuti oleh argumen-argumennya. Tipe internal: `LANGSXP`.
4. **Pairlists**: Struktur data bertipe *linked list* warisan S klasik yang digunakan untuk menyimpan metadata formal arguments pada fungsi atau atribut objek.

```
       Call: compute(x, y + 2)
              /   \
             /     \
    Symbol: compute  Arguments (Pairlist/LANGSXP)
                     /         \
            Symbol: x       Call: y + 2
                             /   |   \
                            +    y    2
```

#### 3.2 Evaluasi Kode: Scoping, Promises, dan Lazy Evaluation
R mengevaluasi argumen fungsi secara malas (*lazy evaluation*). Ketika sebuah argumen dimasukkan ke dalam fungsi, argumen tersebut dibungkus dalam struktur internal C yang disebut **Promise (`PROMSXP`)**.
Promise terdiri dari tiga komponen utama:
- **Expression**: AST dari argumen yang diteruskan.
- **Environment**: Lingkungan tempat ekspresi tersebut dibuat.
- **Value**: Hasil evaluasi yang awalnya kosong (`R_UnboundValue`) dan akan dicatat (*cached*) setelah dievaluasi pertama kali (*memoized on evaluation*).

Jika argumen tidak pernah diakses di dalam tubuh fungsi, Promise tersebut tidak pernah dievaluasi. Metaprogramming memanfaatkan sifat ini untuk menangkap AST argumen **sebelum** evaluasi dipicu.

#### 3.3 Tidy Evaluation dan Quosures
Dalam evaluasi standar, ekspresi diikat secara ketat pada lingkungan tempat ekspresi tersebut dipanggil. Namun, dalam pemrosesan data analitik (misalnya `dplyr` atau `data.table`), ekspresi harus sering dievaluasi di dalam konteks *data frame* (kolom-kolomnya) terlebih dahulu, baru kemudian mencari ke lingkungan luar (*lexical scope*).

**Quosure** adalah struktur data fundamental dari `rlang` yang merepresentasikan ekspresi yang dibungkus bersama dengan lingkungannya:
$$\text{Quosure} = \text{Expression (AST)} + \text{Environment}$$

Ini mencegah masalah *scope-leakage* yang rentan terjadi pada evaluasi ekspresi berbasis `substitute()` dan `eval()` di Base R, di mana ekspresi kehilangan referensi variabel lokal pembungkusnya saat dilempar melintasi *call stack*.

---

### 4. Why & What

| Fitur | Pendekatan Konvensional (Base R / String Glue) | Tidyverse / Modern Advanced Metaprogramming |
| :--- | :--- | :--- |
| **Metode Pemrograman** | `eval(parse(text = "..."))` | Defusal (`enquo`), Quasiquotation (`!!`, `inject`) |
| **Keamanan Kode** | Rentan terhadap *Code Injection*, rentan parsing error | Tipe data AST murni; bebas dari celah injeksi teks |
| **Pengelolaan Scope** | Manual via `parent.frame()`, berisiko *dynamic scoping bug* | Enkapsulasi otomatis melalui Quosures (`rlang::quo`) |
| **Penanganan Error FP**| Blok `tryCatch()` imperatif, mengotori *pipe chain* | Adverbs (`purrr::safely`, `purrr::quietly`, `purrr::possibly`) |
| **Pemisahan Konteks** | Konflik antara nama kolom tabel dan nama variabel lokal | Penegasan eksplisit menggunakan pronoun `.data` vs `.env` |

#### Mengapa Metaprogramming Dibutuhkan di Skala Enterprise?
1. **Abstraksi Pipeline**: Menghilangkan redundansi logika bisnis. Alih-alih menulis ratusan variasi agregasi manual, Anda membuat generator transformasi data yang aman secara tipe dan *environment-aware*.
2. **Dynamic DSL Creation**: Memungkinkan pembuatan *Domain-Specific Language* berbasis aturan bisnis yang dapat dikonfigurasi melalui konfigurasi YAML atau database tanpa mengorbankan performa eksekusi native.
3. **Decoupling Antara Definisi dan Eksekusi**: Mendefinisikan komputasi analitik sebagai pohon sintaksis yang dapat dioptimasi terlebih dahulu sebelum diserahkan ke backend (misalnya diterjemahkan menjadi SQL via `dbplyr`).

---

### 5. How (Workflow Detail)

Alur kerja evaluasi ekspresi non-standar (Tidy Evaluation Lifecycle) dan Functional Pipes:

```
[User Input: x, factor]
         |
         v
+-----------------------------+
| 1. Defusal (rlang::enquo)   | -> Menangkap ekspresi & lexical env tanpa evaluasi
+-----------------------------+
         |
         v
+-----------------------------+
| 2. Introspection / AST      | -> Memeriksa, memvalidasi node, mencegah injeksi
+-----------------------------+
         |
         v
+-----------------------------+
| 3. Quasiquotation (inject)  | -> Membuka ekspresi (!!), menyematkan dots dynamic (:=)
+-----------------------------+
         |
         v
+-----------------------------+
| 4. Contextual Evaluation    | -> Dievaluasi terhadap data pronoun (.data) + lexical (.env)
+-----------------------------+
         |
         v
+-----------------------------+
| 5. Adverbial Wrapper        | -> Menangkap runtime error via purrr::safely
+-----------------------------+
         |
         v
[Production Safe Output / Logging]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Blueprints, Construction Sites, dan Real Estate Inspector
- **Ekspresi Biasa**: Anda membeli rumah yang sudah jadi langsung di tempat (*Langsung dievaluasi saat itu juga*).
- **Quosure**: Anda membawa **Cetak Biru Desain Bangunan (AST)** bersama dengan **Kontraktor yang Mengetahui Lokasi Lahan Tertentu (Environment)**. Rumah belum dibangun sampai Anda menyerahkan cetak biru itu ke mandor proyek (*Lazy Evaluation*).
- **Quasiquotation (`!!`)**: Anda mengambil cetak biru tersebut, menghapus salah satu ruangan di kertas gambar, lalu menempelkan gambar ruangan lain yang dirancang khusus (*Unquoting/Interpolation*) sebelum konstruksi final dimulai.

#### Representasi AST di Memori
Ekspresi: `total <- sum(.data$revenue, na.rm = TRUE) * 1.1`

```
                      Call [ <- ]
                     /           \
           Symbol [ total ]       Call [ * ]
                                 /          \
                       Call [ sum ]          Literal [ 1.1 ]
                      /            \
             Call [ $ ]             Pairlist arg:
            /          \             [na.rm = TRUE]
   Symbol [.data]   Symbol [revenue]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Membedah AST Menggunakan `lobstr` & `rlang`
```r
library(rlang)
library(lobstr)

# 1. Mengubah kode menjadi ekspresi tanpa mengevaluasinya
raw_expr <- expr(aggregate_metric(sales, weight = 0.75, normalize = TRUE))

# 2. Visualisasi struktur AST
cat("Struktur Pohon AST:\n")
lobstr::ast(aggregate_metric(sales, weight = 0.75, normalize = TRUE))

# 3. Inspeksi komponen Call Object
cat("\nKomponen Call:\n")
print(raw_expr[[1]]) # Fungsi
print(raw_expr[[2]]) # Argumen 1
print(raw_expr$weight) # Argumen bernama
```

#### 7.2 Practical Example: Custom Data Mask Transformer Menggunakan Pronouns & Dynamic Injection
Contoh implementasi industri: Fungsi kalkulasi metrik finansial dinamis yang memproteksi variabel masking dan mendukung dynamic naming.

```r
library(rlang)
library(dplyr)

#' Agregasi Finansial Dinamis yang Aman (Production-Grade)
#' @param df Dataframe sumber
#' @param target_col Simbol kolom target yang akan dihitung
#' @param group_col Simbol kolom pengelompokan
#' @param multiplier Angka pengali dari environment eksekusi
#' @param metric_name Nama string untuk kolom output baru
calculate_risk_exposure <- function(df, target_col, group_col, multiplier = 1.0, metric_name = "metric") {
  # 1. Tangkap input sebagai Quosure (Defusal)
  target_quo <- enquo(target_col)
  group_quo  <- enquo(group_col)
  
  # Validasi tipe input scalar multiplier
  stopifnot(is.numeric(multiplier), length(multiplier) == 1)
  
  # 2. Dynamic injection menggunakan inject(), .data pronoun, dan Walrus operator (:=)
  result <- inject(
    df %>%
      group_by(!!group_quo) %>%
      summarise(
        !!metric_name := sum(.data[[as_name(target_quo)]] * .env$multiplier, na.rm = TRUE),
        .groups = "drop"
      )
  )
  
  return(result)
}

# Verifikasi
mock_data <- tibble(
  portfolio = c("Alpha", "Alpha", "Beta", "Beta"),
  notional  = c(1000, 2500, 4000, 1500)
)

# Test eksekusi
out <- calculate_risk_exposure(
  mock_data, 
  target_col = notional, 
  group_col = portfolio, 
  multiplier = 1.15, 
  metric_name = "adjusted_exposure"
)
print(out)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Risk Engine di bank investasi memproses ratusan konfigurasi audit regulasi harian. Konfigurasi perhitungan disimpan dalam tabel konfigurasi (database/JSON). Data pipeline harus:
1. Mengevaluasi formula dinamis tanpa memakai `eval(parse())` yang tidak aman.
2. Memetakan puluhan ribu partisi portofolio secara terisolasi tanpa merusak *main thread*.
3. Menyimpan detail kegagalan kalkulasi per baris/partisi untuk keperluan audit perbankan.

#### Arsitektur Solusi
```
[Database Config: Rules Table] 
             |
             v
 [Rule Parsing to AST (rlang)] 
             |
             v
[purrr::safely Function Factory]
             |
             +-----> [Thread Pool / furrr Workers]
                            |
           +----------------+----------------+
           |                                 |
   [Success Node]                     [Failure Node]
           |                                 |
           v                                 v
[Clean Analytic Data Lake]       [Dead Letter Auditing Queue]
```

#### Implementasi Kode Produksi
```r
library(rlang)
library(purrr)
library(dplyr)
library(tibble)

# 1. Factory Function untuk membuat Validator Aturan Bisnis Dinamis
create_rule_evaluator <- function(raw_rule_expr) {
  # Parse ekspresi secara aman dari string ke AST
  parsed_expr <- parse_expr(raw_rule_expr)
  
  # Return fungsi yang mengisolasi environment evaluasi
  function(data_chunk) {
    # Evaluasi AST di dalam konteks data mask
    eval_tidy(parsed_expr, data = data_chunk)
  }
}

# 2. Pipeline Eksekusi Enterprise dengan Fault Tolerance Menggunakan Purrr
process_enterprise_risk_stream <- function(transactions, rules_manifest) {
  
  # Validasi integritas manifest
  stopifnot(all(c("rule_id", "logic") %in% names(rules_manifest)))
  
  # Bungkus evaluator dengan adverb 'safely' untuk mencegah fatal crash
  compiled_rules <- rules_manifest %>%
    mutate(
      evaluator = map(logic, ~ safely(create_rule_evaluator(.x)))
    )
  
  execution_log <- list()
  results_accumulator <- transactions
  
  for (i in seq_len(nrow(compiled_rules))) {
    current_rule_id <- compiled_rules$rule_id[i]
    eval_fn <- compiled_rules$evaluator[[i]]
    
    # Eksekusi fungsi aman
    execution_result <- eval_fn(results_accumulator)
    
    if (!is.null(execution_result$error)) {
      # Catat failure ke log audit tanpa menghentikan pipeline
      execution_log[[current_rule_id]] <- list(
        status = "FAILED",
        error_message = conditionMessage(execution_result$error),
        timestamp = Sys.time()
      )
    } else {
      # Injeksi hasil komputasi ke dataset
      results_accumulator <- results_accumulator %>%
        mutate(!!current_rule_id := execution_result$result)
      
      execution_log[[current_rule_id]] <- list(
        status = "SUCCESS",
        timestamp = Sys.time()
      )
    }
  }
  
  return(list(
    processed_data = results_accumulator,
    audit_telemetry = execution_log
  ))
}

# ====================================================================
# Simulasi Data Produksi dan Pengujian Eksekusi
# ====================================================================

mock_transactions <- tibble(
  trx_id = 101:105,
  asset_class = c("EQUITY", "DERIVATIVE", "FIXED_INCOME", "EQUITY", "COMMODITY"),
  market_value = c(500000, 12000000, 3000000, 800000, 4500000),
  counterparty_rating = c("AAA", "BBB", "AA", "CCC", "AA")
)

rules_config <- tibble(
  rule_id = c("is_high_exposure", "invalid_syntax_rule", "is_speculative_grade"),
  logic = c(
    "market_value > 2000000",
    "non_existent_column == TRUE", # Sengaja disuntikkan error untuk tes fault tolerance
    "counterparty_rating %in% c('BBB', 'CCC')"
  )
)

pipeline_output <- process_enterprise_risk_stream(mock_transactions, rules_config)

# Output Data yang sukses diproses:
print(pipeline_output$processed_data)

# Output Audit Log yang mencatat kegagalan runtime:
print(pipeline_output$audit_telemetry)
```

---

### 9. Trade-offs

| Dimensi Arsitektural | Pendekatan Direct Vectorization (Hardcoded) | Metaprogramming / Dynamic Tidy Eval |
| :--- | :--- | :--- |
| **Performance (CPU Time)** | **Sangat Cepat**: Langsung mengakses C internal tanpa overhead traversal. | **Overhead Parsing**: Dynamic parsing dan defusal memakan waktu $\sim 10 - 50 \, \mu s$ per call. |
| **Latency & Compilation** | Nol latensi tambahan. Siap untuk loop berulang skala mikro. | Terasa lambat jika dilakukan di dalam iterasi baris per baris. Harus dilakukan di luar loop. |
| **Memory & Scalability** | **Rendah**: Zero overhead metadata tree. | **Tinggi pada Quosure Leak**: Menahan *environment* referensi yang mencegah alokasi memori GC. |
| **Maintenance Cost** | **Tinggi jika Dinamis**: Melipatgandakan *code duplications* saat parameter analitik bertambah. | **Rendah & Modular**: Mengabstraksi perubahan formula dari core execution engine. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Penggunaan Anti-Pattern `eval(parse(text = ...))`
```r
# SALAH BESAR (Vulnerable, Lambat, Sulit Didebug)
col_name <- "sales; system('rm -rf /')" # Contoh Security Injection
eval(parse(text = paste0("df$", col_name)))

# BENAR (Menggunakan rlang Symbols yang Terisolasi)
col_sym <- sym("sales")
eval_tidy(col_sym, data = df)
```
*Troubleshooting*: Selalu ganti string concatenations untuk evaluasi kode dengan `sym()`, `syms()`, atau pronoun `.data[[var_string]]`.

#### Mistake 2: Masking Ambiguity Collision (`.data` vs `.env`)
```r
# MASALAH: Nama variabel lokal bertabrakan dengan nama kolom tabel
threshold <- 500

df %>% 
  filter(threshold > threshold) # Tidak deterministik jika df memiliki kolom bernama 'threshold'

# BENAR: Deklarasikan pronoun scope secara eksplisit
df %>% 
  filter(.data$threshold > .env$threshold)
```

#### Mistake 3: Memory Leak Akibat Quosure Menyimpan Scope Eksternal
Quosure menangkap seluruh *enclosing environment*. Jika fungsi pembungkus memproses objek perantara yang besar (misal array 2GB) dan kemudian mengembalikan Quosure tanpa isolasi, array 2GB tersebut tidak akan pernah dibersihkan oleh Garbage Collector (`gc()`).

*Troubleshooting*: Gunakan `rlang::as_quosure(expr, env = emptyenv())` jika lingkungan tidak diperlukan lagi, atau hapus objek lokal (`rm()`) sebelum membungkus ke dalam quosure.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Pronoun Declaration**: Selalu gunakan `.data$field` atau `.env$param` di dalam custom verbs Tidyverse untuk menghindari *ambiguous symbol resolution*.
2. [ ] **Injection Vectorization**: Hindari melakukan `parse_expr()` di dalam loop baris/sub-iterasi. Kompilasi/parse ekspresi satu kali di luar loop (menggunakan *Function Factory*), lalu petakan fungsinya.
3. [ ] **Defusal Guard**: Gunakan `enquo()` untuk argumen tunggal dan `enquos(..., .named = TRUE)` jika menerima *dynamic variadic dots*.
4. [ ] **Walrus Operator Integrity**: Selalu gunakan `:=` saat menyematkan nama dinamis yang berasal dari quasiquotation (`!!var_name := calculation`).
5. [ ] **Pure Pipeline Isolation**: Pastikan semua pipe closures terbebas dari modifikasi *global assignment* (`<<-`).
6. [ ] **Fault Protection**: Gunakan `purrr::safely` pada node komputasi yang mengevaluasi ekspresi pengguna dinamis.

---

### 12. Hands-on Practice

Simpan seluruh latihan berikut di bawah folder direktori: `hands-on/m02/`

#### File: `hands-on/m02/dynamic_aggregator.R`

Lakukan langkah-langkah terpandu berikut:
1. Buat direktori dan file:
   ```bash
   mkdir -p hands-on/m02
   touch hands-on/m02/dynamic_aggregator.R
   ```
2. Tuliskan implementasi mesin agregasi bertingkat yang menerima *multiple measures* dan *multiple groups* secara dinamis menggunakan Tidy Evaluation:

```r
# hands-on/m02/dynamic_aggregator.R
library(rlang)
library(dplyr)
library(purrr)

#' Enterprise Dynamic Multi-Aggregator
#' Menghasilkan ringkasan data dinamis dari vektor string kolom tanpa hardcode
execute_dynamic_summary <- function(data, group_vars, target_vars, funcs = c("mean", "sd")) {
  # 1. Defusal & Konversi string ke list of symbols
  group_syms <- syms(group_vars)
  target_syms <- syms(target_vars)
  
  # 2. Bangun ekspresi ringkasan secara komputasional
  # Membuat list pemanggilan agregasi dinamis
  summary_expressions <- list()
  
  for (t_sym in target_syms) {
    for (fn in funcs) {
      fn_sym <- sym(fn)
      col_output_name <- paste0(as_name(t_sym), "_", fn)
      
      # Bangun AST: fn(t_sym, na.rm = TRUE)
      summary_expressions[[col_output_name]] <- expr((!!fn_sym)(!!t_sym, na.rm = TRUE))
    }
  }
  
  # 3. Injeksikan ke dalam dplyr pipeline
  result <- data %>%
    group_by(!!!group_syms) %>%
    summarise(
      !!!summary_expressions,
      .groups = "drop"
    )
  
  return(result)
}

# --- Block Verifikasi Eksekusi ---
if (sys.nframe() == 0) {
  cat("[INFO] Menjalankan pengujian Dynamic Aggregator...\n")
  test_df <- tibble(
    dept = c("IT", "IT", "HR", "HR", "Finance"),
    loc  = c("JKT", "SBY", "JKT", "SBY", "JKT"),
    salary = c(10, 15, 8, 9, 20),
    bonus  = c(2, 3, 1, 1.5, 5)
  )
  
  out <- execute_dynamic_summary(
    test_df, 
    group_vars = c("dept", "loc"), 
    target_vars = c("salary", "bonus"),
    funcs = c("mean", "max")
  )
  
  print(out)
  cat("[SUCCESS] Pipeline berhasil dieksekusi tanpa error parsing.\n")
}
```

3. Jalankan script pada terminal Anda:
   ```bash
   Rscript hands-on/m02/dynamic_aggregator.R
   ```

---

### 13. Exercise

#### Level Easy
Buat fungsi bernama `filter_by_condition(df, column, operator_str, threshold)` di mana `operator_str` dapat berupa `">"`, `"<"`, atau `"=="`. Implementasikan AST construction menggunakan `call2()` dan `eval_tidy()` untuk memfilter data frame tanpa memicu konversi string `paste0`.
- *Input*: `mtcars`, `column = "mpg"`, `operator_str = ">"`, `threshold = 25`
- *Output*: Sub-data frame yang lolos kriteria.

#### Level Medium
Buat sebuah **Adverb Function Factory** bernama `auto_retry(fn, max_retries = 3, backoff_sec = 0.5)`. Adverb ini membungkus fungsi target sehingga jika target melempar *error*, fungsi akan otomatis mencoba kembali (*retry*) hingga batas maksimum tercapai sebelum akhirnya melempar error atau mengembalikan `purrr::safely` dead-record. Terapkan pada simulasi fungsi request data API yang rentan putus.

#### Level Hard
Rancang dan bangun **Rule Transformation Compiler**. Fungsi menerima sebuah data frame dan sebuah *named list* yang berisi string ekspresi matematika (misal: `list(spread = "bid - ask", mid = "(bid + ask) / 2")`). Compiler harus:
1. Memvalidasi bahwa hanya operator matematika yang diizinkan (`+`, `-`, `*`, `/`) yang ada di AST demi keamanan. Jika terdeteksi eksekusi sistem/fungsi berbahaya (misal `system`, `file.remove`), lemparkan error eksepsi.
2. Menyusun pohon eksekusi modular menggunakan `rlang::parse_exprs()`.
3. Menjalankan kalkulasi mutasi tanpa hardcoded dplyr verbs secara *chained*.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Autonomous Data Quality Remediation Engine
Di arsitektur terdistribusi berbasis data streaming, data pipeline Anda menerima anomali skema: nama kolom tidak konsisten, formula rekonsiliasi antar negara bervariasi tergantung negara asal data (*metadata-driven transformation*).

**Tantangan Arsitektur**:
1. Buat package/skrip modul R mandiri yang mengimplementasikan class-like engine (menggunakan *closures* dan *environments*).
2. Engine harus mengonsumsi metadata konfigurasi (misalnya matriks perlakuan: kolom mana yang harus di-*impute*, formula apa yang harus dievaluasi, dan kondisi logika apa yang memicu aturan tersebut).
3. Evaluasi aturan kalkulasi **harus dilakukan sepenuhnya via compiled expressions AST** tanpa dependensi pada sintaks teks evaluatif.
4. Ketika ekspresi mengalami parsing error atau pembagian dengan nol (*zero division / non-finite math*), engine tidak boleh *crash*. Gunakan arsitektur pemrosesan `purrr` berjenjang untuk memisahkan data menjadi dua cabang (*Clean Stream* dan *Quarantine Stream*) yang dilengkapi dengan stack-trace error terperinci.
5. Sediakan benchmark alokasi memori menggunakan `bench::mark()` yang membandingkan performa dynamic injection engine buatan Anda terhadap implementasi konvensional imperatif base R.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa tipe objek dari hasil pemanggilan `expr(x + y)` di Base R / rlang?**
   - A. Character String
   - B. Call Object (`LANGSXP`)
   - C. Environment Object
   - D. Data Frame
   *Kunci*: B. Ekspresi yang menangkap pemanggilan fungsi atau operasi adalah sebuah Call Object.

2. **Apa fungsi utama dari operator Walrus (`:=`) dalam ekosistem Tidyverse?**
   - A. Melakukan assignment global menggantikan `<<-`
   - B. Memungkinkan unquoting dinamis pada sisi kiri (*LHS*) dari sebuah argumen bernama
   - C. Operator perbandingan eksklusif tipe data
   - D. Membatasi evaluasi lingkungan eksekusi
   *Kunci*: B. Digunakan untuk dynamic naming pada LHS, misal: `!!var_name := value`.

3. **Manakah dari fungsi berikut yang mengubah String menjadi Symbol pada `rlang`?**
   - A. `as.name()` atau `rlang::sym()`
   - B. `rlang::enexpr()`
   - C. `purrr::as_mapper()`
   - D. `lobstr::ast()`
   *Kunci*: A. `sym()` atau `as.name()` mengubah representasi teks skalar menjadi simbol AST.

4. **Karakteristik utama dari arsitektur lazy evaluation pada argumen fungsi R adalah:**
   - A. Argumen langsung dihitung sebelum memasuki tubuh fungsi
   - B. Argumen dibungkus dalam Promise dan hanya dievaluasi ketika nilainya pertama kali dibaca
   - C. Argumen selalu disimpan dalam global environment
   - D. Argumen hanya bertipe data teks
   *Kunci*: B. Promise (`PROMSXP`) menunda evaluasi hingga nilai argumen tersebut diakses.

5. **Apa fungsi dari adverb `purrr::safely()`?**
   - A. Mengenkripsi output fungsi dengan kunci privat
   - B. Mengubah fungsi biasa menjadi fungsi yang mengembalikan list berisi `$result` dan `$error`
   - C. Menghentikan program seketika saat terjadi warning
   - D. Menjamin alokasi memori tidak bertambah
   *Kunci*: B. `safely()` memodifikasi fungsi agar tidak melempar fatal exception melainkan mengembalikan hasil terbungkus.

---

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Apa perbedaan mendasar antara Quosure (`quosure`) dan Expression (`expr`) mentah?**
   - A. Quosure hanya bisa memproses string, sedangkan expr memproses angka
   - B. Quosure membungkus AST bersama dengan Lexical Environment tempat ia didefinisikan, sedangkan expr hanya menyimpan AST mentah
   - C. Quosure dibuat oleh Base R, sedangkan expr dibuat oleh rlang
   - D. Tidak ada perbedaan nyata; keduanya hanyalah alias
   *Kunci*: B. Quosure = AST + Environment.

7. **Kapan Anda harus menggunakan operator Big-Bang (`!!!`) alih-alih Single Unquote (`!!`)?**
   - A. Ketika ingin meng-unquote ekspresi tunggal
   - B. Ketika ingin melakukan unquote dan splicing (*membentangkan*) elemen-elemen dari sebuah list/vektor ke dalam multiple arguments
   - C. Ketika ingin mematikan evaluasi lazy
   - D. Ketika mengevaluasi operator logika bertingkat
   *Kunci*: B. `!!!` melakukan *unquote-splicing* dari list of expressions ke dalam *call argument list*.

8. **Pronoun `.data$variable` dalam Tidy Evaluation menjamin bahwa:**
   - A. Variabel akan diambil dari execution/parent environment
   - B. Pencarian simbol hanya akan dilakukan pada kolom-kolom dataset yang bersangkutan, menghindari masking dari variabel lokal
   - C. Data frame diubah secara mutlak di disk storage
   - D. Nilai dikonversi menjadi format skalar otomatis
   *Kunci*: B. Pronoun `.data` secara eksplisit membatasi *symbol lookup* ke dalam konteks data frame.

9. **Jika Anda membuat sebuah Function Factory yang mengembalikan Closure, potensi masalah memori yang paling sering dihadapi adalah:**
   - A. Integer overflow
   - B. Memory leak karena closure menahan parent environment yang berisi dataset besar yang tidak sengaja terbawa
   - C. Crash pada alokasi swap file
   - D. Penurunan performa pada stack register CPU
   *Kunci*: B. Lexical scoping menyebabkan lingkungan pembuatan closure tetap hidup selama fungsi penampung masih eksis di memori.

10. **Apa tujuan penggunaan fungsi `rlang::inject()`?**
    - A. Menyuntikkan DLL C++ ke dalam proses runtime R
    - B. Mengevaluasi ekspresi yang di dalamnya mengandung operator quasiquotation (`!!`, `!!!`) sebelum diteruskan ke fungsi target
    - C. Menggantikan peran pointer C pada alokasi memory heap
    - D. Menghubungkan script R ke remote server
    *Kunci*: B. `inject()` mengevaluasi quasiquotation marks di dalam argumen tanpa memerlukan macro wrapper khusus.

---

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus 1**:
    Sebuah modul analitik harian mengeksekusi puluhan formula filtering dinamis yang dimasukkan oleh tim analis via database. Sistem sering mengalami *silent data corruption* di mana hasil filter menghasilkan 0 baris atau data yang salah karena nama variabel filter analis bertabrakan dengan nama objek internal fungsi (misal nama kolom adalah `status`, dan di dalam fungsi terdapat variabel `status <- "COMPLETED"`).
    **Bagaimana arsitektur filtering yang seharusnya diterapkan menggunakan `rlang`?**
    - A. Meminta analis tidak menggunakan nama variabel yang sama
    - B. Menggunakan `eval(parse(text = ...))` yang dijalankan di `emptyenv()`
    - C. Mengonversi string filter analis menjadi AST melalui `parse_expr()`, lalu mengevaluasinya via `eval_tidy()` dengan penegasan pronoun `.data` atau passing data frame secara langsung pada context data mask
    - D. Menghapus semua variabel lokal di dalam fungsi sebelum eksekusi
    *Kunci*: C. Evaluasi data mask yang terisolasi memprioritaskan kolom data frame dan mencegah intervensi scope lokal secara deterministik.

12. **Skenario Kasus 2**:
    Tim engineering Anda menemukan bahwa pemrosesan batch 10.000 partisi data sangat lambat. Analisis profil kode (`profvis`) menunjukkan bahwa fungsi menggunakan `purrr::map()` yang di dalamnya memanggil `parse_expr()` dan `eval_tidy()` secara berulang untuk setiap baris partisi.
    **Langkah refactoring arsitektur apa yang memberikan optimasi performa paling optimal?**
    - A. Mengganti `purrr::map()` dengan for-loop Base R
    - B. Melakukan kompilasi/parsing ekspresi satu kali di luar loop utama menggunakan *Function Factory*, menghasilkan fungsi closure executable, lalu memetakan closure tersebut ke partisi data
    - C. Mengonversi seluruh dataset ke format raw CSV sebelum kalkulasi
    - D. Mengganti semua tipe numerik menjadi tipe integer
    *Kunci*: B. Parsing string ke AST memiliki computational overhead. Memisahkan fase *Parse Once* dengan fase *Evaluate Many* menghilangkan latensi kompilasi di setiap iterasi.

13. **Skenario Kasus 3**:
    Sebuah worker data processing berbasis `furrr` (multi-process cluster) mengalami crash tanpa pesan error yang jelas (*Process killed silently*) saat mengevaluasi Quosure yang dikirim dari node master.
    **Apa akar penyebab internal arsitektur yang paling mungkin?**
    - A. Node worker kekurangan lisensi R Enterprise
    - B. Quosure membawa *enclosing environment* node master yang berukuran beberapa Gigabyte atau berisi objek pointer eksternal (C/C++ external pointer) yang tidak dapat di-serialize via IPC (*Inter-Process Communication*) socket
    - C. Sintaks AST tidak kompatibel dengan arsitektur CPU x86_64
    - D. Worker tidak mendukung evaluasi lazy
    *Kunci*: B. Quosure membungkus environment. Mengirimkan Quosure melalui soket paralel mencoba melakukan serialisasi lingkungan tersebut. Jika lingkungan berisi pointer C++ atau data masif, serialisasi akan korup atau kehabisan memori. Sebaiknya kirimkan ekspresi mentah (`expr`) dan lingkungan dibangun secara lokal di sisi worker.

---

### 16. Summary

- **Homoikonisitas & AST**: R merepresentasikan program sebagai struktur data pohon (AST) yang tersusun atas *Literals*, *Symbols*, dan *Calls*. Hal ini memungkinkan inspeksi, modifikasi, dan kompilasi kode secara dinamis.
- **Tidy Evaluation Engine**: Framework modern berbasis `rlang` yang menyelesaikan masalah evaluasi non-standar secara deterministik. Melalui konsep **Defusal** (`enquo`), **Quasiquotation** (`!!`, `!!!`), dan **Contextual Injection** (`inject()`, `:=`), pengembang dapat menyusun query analitik yang dinamis namun aman dari *code injection*.
- **Pemisahan Konteks (.data vs .env)**: Menghilangkan kerentanan *symbol collision* dan *masking bug* yang merupakan kelemahan kronis pada fungsi evaluasi Base R konvensional (`eval(parse())`).
- **Resilient Functional Architecture**: Penggabungan teknik Tidy Evaluation dengan higher-order functions dan adverbs dari `purrr` (`safely`, `quietly`) memungkinkan pembangunan data pipeline kelas *enterprise* yang tangguh (*fault-tolerant*), mampu mengisolasi kegagalan per-partisi, serta mudah diaudit secara komprehensif.