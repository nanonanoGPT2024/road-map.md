# Bab 07 Module 01: Metaprogramming, Abstract Syntax Trees (AST), dan Tidy Evaluation Engine (`rlang`)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Membedah dan memanipulasi struktur internal *Abstract Syntax Tree* (AST) pada R tingkat C-level (`LANGSXP`, `SYMSXP`) menggunakan paket modern (`rlang`, `lobstr`).
- Mendiagnosis dan mengeliminasi bug *variable capture* serta kebocoran leksikal (*hygiene issues*) yang timbul dari Non-Standard Evaluation (NSE) berbasis base R (`substitute()`, `eval()`).
- Mengimplementasikan pola *defusal*, *injection*, dan *data masking* menggunakan primitives `rlang` (`enquo()`, `inject()`, dynamic dots `...`, operator embrace `{{ }}`) untuk membangun antarmuka analitik yang *type-safe*, fleksibel, dan siap produksi.
- Mendesain Domain-Specific Language (DSL) mini yang aman untuk query dinamis tanpa mengekspos sistem terhadap celah injeksi kode dari `eval(parse(text = ...))`.

---

### 2. Prerequisite
Untuk memahami materi ini secara komprehensif, Anda wajib menguasai:
- **Lexical Scoping & Environments**: Mekanisme pencarian pointer environment R (parent, enclosing, binding, execution frames).
- **Function Closures & Promises**: Struktur internal argumen R yang terdiri dari ekspresi (*expression*), pointer environment, dan evaluasi tertunda (*delayed evaluation/forcing*).
- **Manipulasi Struktur Data Rekursif**: Pengalaman bekerja dengan *recursive lists* dan *pairlists*.

---

### 3. Concept
R adalah implementasi modern dari bahasa S yang berakar langsung pada dialek Lisp (khususnya Scheme). Karakteristik fundamental ini menjadikan R sebagai bahasa *homoikonik*: **kode R direpresentasikan sebagai struktur data R tingkat satu (*first-class citizens*) yang dapat diinspeksi, dimodifikasi, dan dievaluasi secara terprogram.**

Secara internal pada runtime C API R:
1. **Parsing**: Interpreter membaca string kode mentah dan mengonversinya menjadi pohon sintaksis: *Abstract Syntax Tree* (AST). Node dalam AST direpresentasikan oleh tipe data C internal (`SEXPTYPE`):
   - `SYMSXP` (*Symbols / Names*): Identifier yang merujuk pada objek di dalam environment.
   - `LANGSXP` (*Calls*): Pohon ekspresi yang merepresentasikan pemanggilan fungsi, di mana elemen pertama adalah fungsi yang dipanggil, diikuti oleh argumen-argumennya sebagai struktur *pairlist*.
   - Objek Literal / Atomic Vectors: Nilai skalar konstan (`REALSXP`, `STRSXP`, dll).
2. **Evaluation**: AST kemudian dievaluasi terhadap *environment* tertentu menggunakan fungsi internal `eval()`.

Dalam komputasi interaktif, **Non-Standard Evaluation (NSE)** memungkinkan fungsi menangkap ekspresi yang diketik oleh pengguna sebelum dievaluasi menjadi nilai riil (*defusal*). Namun, metode NSE klasik pada base R memiliki kelemahan arsitektural: hilangnya konteks *lexical scope* dari pemanggil aslinya (*hygiene problem*).

Framework **Tidy Evaluation** (`rlang`) memecahkan ambiguitas ini secara matematis melalui pengenalan **Quosure** ($\text{Quosure} = \text{Expression} + \text{Environment}$). Quosure mengunci AST bersama dengan environment eksak tempat AST tersebut dibuat, mencegah terjadinya *name masking collision* antara kolom data (*data frame attributes*) dan variabel lokal lingkungan eksekusi (*environment variables*).

---

### 4. Why
Dalam rekayasa data dan pengembangan paket R skala enterprise, penulisan fungsi pembungkus (*wrapper functions*) di atas ekosistem modern (seperti `dplyr`, `dbplyr`, `ggplot2`) tidak dapat dilakukan hanya dengan evaluasi standar (evaluasi nilai):

1. **Eliminasi String-based Insecurity**: Pola lama mengandalkan `eval(parse(text = paste(...)))`. Pola ini lambat (karena overhead string parsing berulang), sulit di-debug, dan rentan terhadap *code injection* jika menerima input eksternal yang tidak divalidasi.
2. **Ambiguitas Kolom vs Variabel**: Tanpa pelacakan environment eksplisit, fungsi yang merujuk ke nama kolom `x` dapat secara tidak sengaja membaca variabel global `x` jika kolom tersebut tidak sengaja terhapus atau berubah nama di hulu pipeline (*unhygienic evaluation*).
3. **Pemberdayaan Dynamic Pipelines**: Kebutuhan untuk membuat pipeline analitik yang kolom agregasinya ditentukan secara *runtime* (misalnya dari payload konfigurasi JSON atau REST API) menuntut manipulasi AST tingkat lanjut sebelum dieksekusi secara native di database atau in-memory engine.

---

### 5. What
Komponen arsitektural utama dalam ekosistem metaprogramming R meliputi:

- **Expression**: Kode R yang belum dievaluasi.
- **Symbol / Name**: Representasi sintaktis dari variabel (dibuat via `rlang::sym()` atau `as.name()`).
- **Call Object**: Representasi pemanggilan fungsi yang berakar pada list berpasangan rekursif (dibuat via `rlang::call2()`).
- **Defusal (Quoting)**: Tindakan menangkap kode tanpa mengevaluasinya (`rlang::expr()` untuk ekspresi statis, `rlang::enquo()` untuk menangkap argumen fungsi beserta environment eksekusinya).
- **Quosure**: Objek terenkapsulasi yang menyimpan ekspresi (`expr`) dan pointer environment (`env`).
- **Injection (Unquoting)**: Teknik menyisipkan ekspresi atau nilai lain ke dalam AST sebelum dievaluasi (`!!` untuk satu elemen / *bang-bang*, `!!!` untuk penyisipan list elemen / *splice*, `{{ }}` / *embrace* untuk penyederhanaan defusal + injection).
- **Data Mask**: Environment buatan di mana kolom-kolom `data.frame` diposisikan sebagai layer prioritas pencarian pertama, dengan environment induk sebagai *fallback*.

---

### 6. How
Alur kerja komputasi Tidy Evaluation berjalan melalui tahapan berikut:

```
+-------------------------------------------------------------------------------+
| User Code: my_summary(df, var = sales, by = region)                           |
+-------------------------------------------------------------------------------+
                                      |
                                      v
  1. DEFUSE (Capture Expression + Calling Environment without evaluation)
     - var_quo <- enquo(var)  => <quosure: expr = `sales`, env = <caller_env>>
     - by_quo  <- enquo(by)   => <quosure: expr = `region`, env = <caller_env>>
                                      |
                                      v
  2. AST MANIPULATION / INJECTION (Reconstruct syntax tree)
     - inject(df %>% summarize(mean = mean(!!var_quo), .by = !!by_quo))
                                      |
                                      v
  3. DATA MASK CREATION
     - Mask layer 1: Kolom `sales` dan `region` dari `df`
     - Mask layer 2: Environment pemanggil (jika ada variabel non-kolom)
                                      |
                                      v
  4. EVALUATION
     - Eksekusi ekspresi terinjeksi di dalam Data Masking Scope
     - Return nilai agregasi aman secara deterministik
```

1. Interpreter R menerima argumen fungsi sebagai *Promise*. Nilai belum dihitung.
2. Primitive `rlang::enquo()` mengekstrak komponen ekspresi dan pointer *caller environment* dari promise tersebut tanpa memicu *forcing*.
3. Operator injeksi (`!!`, `!!!`, atau `{{ }}`) memodifikasi AST target pada memori sementara.
4. Engine evaluasi (`rlang::eval_tidy()`) menyusun *Data Mask* di mana vektor kolom data frame disajikan sebagai simbol yang dapat dicari terlebih dahulu sebelum leksikal global.
5. Pohon ekspresi yang sudah disusun ulang dievaluasi secara native.

---

### 7. Analogy
Bayangkan Anda memesan rumah modular.

- **Evaluasi Standar**: Anda memberikan rumah fisik yang sudah jadi ke pabrik. Setiap kali Anda ingin variasi, Anda harus membangun rumah lengkap terlebih dahulu dari awal.
- **Base NSE (`substitute`)**: Anda memberikan cetak biru (*blueprint*) pensil tanpa catatan lisensi arsitek. Kontraktor lokal mencoba membacanya, tetapi jika simbol "Pintu A" diartikan berbeda di kota tersebut, konstruksi akan salah total atau runtuh (*unhygienic*).
- **Tidy Evaluation (`rlang`)**: Anda memberikan cetak biru stempel resmi (**Quosure**). Cetak biru tersebut mengunci gambar teknis (**Expression**) sekaligus menyertakan buku referensi spesifikasi arsitek aslinya (**Environment**). Kontraktor menggunakan segel dinamis (**Injection `!!`**) untuk menukar material tertentu sesuai rancangan Anda secara terisolasi tanpa ada risiko salah tafsir simbol lokal.

---

### 8. Diagram

```
                 STRUKTUR AST (ABSTRACT SYNTAX TREE)
                 ----------------------------------
                 Ekspresi: total = sum(revenue * tax, na.rm = TRUE)

                                  Call: `=`
                                 /         \
                       Symbol: total     Call: `sum`
                                        /     \     \
                                       /       \     \
                              Call: `*`         \     Literal: TRUE
                             /         \         \    (Arg name: na.rm)
                     Symbol: revenue  Symbol: tax \
                                                   \
                                       (Arg name: unnamed)


                 MEKANISME DATA MASKING EVALUATION
                 ---------------------------------
               Scope Chain Lookup Resolusi Variabel:
 
    +-------------------------------------------------------+
    | 1. DATA MASK: df                                      |
    |    Bindings: revenue = c(100, 200), tax = c(0.1, 0.2) |
    +-------------------------------------------------------+
                               | (Fallback jika tidak ditemukan)
                               v
    +-------------------------------------------------------+
    | 2. CALLING ENVIRONMENT: parent.frame()                |
    |    Bindings: default_multiplier = 1.05                |
    +-------------------------------------------------------+
                               | (Fallback)
                               v
    +-------------------------------------------------------+
    | 3. GLOBAL ENVIRONMENT & ATTACHED PACKAGES             |
    |    Bindings: sum = base::sum                          |
    +-------------------------------------------------------+
```

---

### 9. Simple Example
Kode berikut menunjukkan perbedaan antara parsing AST, inspeksi struktur internal, dan injeksi dasar:

```r
library(rlang)
library(lobstr)

# 1. Menampilkan struktur node AST
raw_expr <- expr(y <- x * 10 + base_offset)
lobstr::ast(y <- x * 10 + base_offset)
# Menghasilkan visualisasi Call tree secara eksplisit

# 2. Manipulasi komponen AST
# Ekstrak fungsi call terluar
print(raw_expr[[1]]) # `<-`
# Modifikasi node variabel di dalam pohon secara manual
raw_expr[[2]] <- sym("target_variable")
print(raw_expr)      # target_variable <- x * 10 + base_offset

# 3. Simple Injection (Unquoting) menggunakan bang-bang (!!)
var_name <- sym("dynamic_metric")
multiplier <- 2.5

injected_expr <- expr(df %>% dplyr::mutate(!!var_name := raw_value * !!multiplier))
print(injected_expr)
# dplyr::mutate(df, dynamic_metric = raw_value * 2.5)
```

---

### 10. Practical Example
Implementasi fungsi analisis produksi yang membungkus `dplyr` dengan kemampuan menerima:
- Kolom target fleksibel (*quosure injection*).
- Filtering condition dinamis.
- List variabel grouping dinamis (*splice injection*).
- Prefix nama output secara dinamis menggunakan operator Walrus (`:=`).

```r
library(dplyr)
library(rlang)

compute_grouped_metrics <- function(data, 
                                    group_cols, 
                                    measure_col, 
                                    filter_predicate = NULL,
                                    metric_prefix = "metric") {
  # Validasi defensif
  if (!is.data.frame(data)) {
    abort("Parameter 'data' harus berupa data.frame atau tibble.")
  }

  # Defuse arguments
  measure_quo <- enquo(measure_col)
  predicate_quo <- enquo(filter_predicate)
  
  # Group cols dapat diterima sebagai character vector, atau list of symbols
  # Normalisasi group_cols menjadi list of symbols/calls
  if (is.character(group_cols)) {
    group_symbols <- syms(group_cols)
  } else {
    group_symbols <- enquos(group_cols)
  }

  # Dinamis generate nama kolom output
  col_mean_name <- paste0(metric_prefix, "_mean")
  col_sd_name   <- paste0(metric_prefix, "_sd")

  # Bangun pipeline menggunakan injection
  pipeline <- data
  
  # Aplikasikan conditional filtering jika disediakan (cek apakah ekspresi ada)
  if (!quo_is_null(predicate_quo)) {
    pipeline <- pipeline %>% 
      filter(!!predicate_quo)
  }

  # Eksekusi agregasi dengan dynamic splicing (!!!) dan dynamic LHS (:=)
  result <- pipeline %>%
    group_by(!!!group_symbols) %>%
    summarise(
      !!col_mean_name := mean(!!measure_quo, na.rm = TRUE),
      !!col_sd_name   := sd(!!measure_quo, na.rm = TRUE),
      n_obs           = n(),
      .groups         = "drop"
    )

  return(result)
}

# Demonstrasi Eksekusi
df_test <- tibble(
  dept = c("Eng", "Eng", "Ops", "Ops", "Ops", "HR"),
  level = c("Senior", "Junior", "Senior", "Junior", "Mid", "Senior"),
  salary = c(120, 80, 95, 60, 75, 85)
)

# Pemanggilan aman tanpa string, leksikal hygiene terjaga
summary_res <- compute_grouped_metrics(
  data = df_test,
  group_cols = c("dept", "level"),
  measure_col = salary,
  filter_predicate = salary > 65,
  metric_prefix = "net_compensation"
)

print(summary_res)
```

---

### 11. Real World Example: Dynamic Financial Risk Engine
**Skenario**: Sistem *core risk platform* perbankan menerima spesifikasi metrik risiko agregat dari engine rules dalam format runtime meta-object. Engine harus mengompilasi formula secara dinamis, mengisolasi referensi data finansial historis tanpa mengorbankan integritas scope atau mengorbankan performa SQL backend (`dbplyr`).

```r
library(rlang)
library(dplyr)

compile_risk_pipeline <- function(portfolio_data, 
                                  exposure_var, 
                                  collateral_var, 
                                  haircut_rate = 0.20,
                                  custom_risk_formula = NULL) {
  
  exp_quo <- enquo(exposure_var)
  col_quo <- enquo(collateral_var)
  custom_formula_quo <- enquo(custom_risk_formula)

  # Default rule: Exposure at Default minus haircutted collateral
  # Jika ada custom formula, lakukan injeksi ekspresi custom tersebut
  base_lgd_expr <- if (quo_is_null(custom_formula_quo)) {
    expr(pmax(0, !!exp_quo - (!!col_quo * (1 - !!haircut_rate))))
  } else {
    custom_formula_quo
  }

  # Build dynamic call pipeline
  computed_data <- portfolio_data %>%
    mutate(
      loss_given_default = !!base_lgd_expr,
      risk_weighted_exposure = loss_given_default * 1.25
    ) %>%
    filter(risk_weighted_exposure > 0)

  return(computed_data)
}

# Mock dataset risiko
portfolio <- tibble(
  account_id = sprintf("ACC-%04d", 1:5),
  exposure = c(1000000, 500000, 250000, 100000, 50000),
  collateral = c(800000, 600000, 100000, 50000, 80000)
)

# 1. Menjalankan skenario standar
standard_risk <- compile_risk_pipeline(portfolio, exposure, collateral)
print(standard_risk)

# 2. Menginjeksi formula kustom dari business logic layer yang berbeda
# Formula dapat menggunakan variabel lingkungan pemanggil (contoh: stressed_multiplier)
stressed_multiplier <- 1.45
stress_scenario <- compile_risk_pipeline(
  portfolio, 
  exposure, 
  collateral, 
  custom_risk_formula = (exposure * stressed_multiplier) - collateral
)
print(stress_scenario)
```

---

### 12. Trade-offs

| Dimensi | Non-Standard Evaluation (`rlang` / Tidy Eval) | Standard Evaluation (SE) / Primitives Murni |
| :--- | :--- | :--- |
| **Keterbacaan Kode Call** | **Sangat Tinggi**: Sintaksis deklaratif, ringkas, menyerupai domain logic. | **Rendah**: Penuh karakter kutip string, sintaks subsetting verbose (`df[[var]]`). |
| **Kompleksitas Debugging** | **Tinggi**: Traceback melibatkan multi-layer lexical scopes, data masks, dan promise generation. | **Rendah**: Call stack linear, eksekusi procedural langsung tanpa delayed resolution. |
| **Overhead Komputasi** | **Mikro-overhead**: Wrapping AST dalam quosure dan resolusi environment memakan waktu beberapa mikrodetik per call. | **Nol Overhead**: Direct primitive access, tidak ada parsing AST di runtime. |
| **Keamanan (Hygiene)** | **Tinggi**: Menghindari problem name-masking melalui eksplisit referensi `.data` vs `.env`. | **Tergantung**: Sangat rentan jika developer menggunakan jalan pintas `eval(parse())`. |
| **Kompatibilitas Backend** | **Tinggi**: AST dapat ditranslasi ke SQL (`dbplyr`) tanpa mengevaluasi data lokal. | **Rendah**: Sulit ditranslasikan langsung menjadi *Abstract Syntax* backend lain secara otomatis. |

---

### 13. When To Use
- Anda sedang membangun package infrastruktur analitik atau library data internal perusahaan yang berinteraksi dengan tabel tabular (`tibble`, `data.frame`, database via `dbplyr`).
- Fungsi membutuhkan kemampuan menyusun formula dinamis berdasarkan input parameter dari API, JSON konfigurasi, atau argumen pengguna.
- Anda mendesain Domain Specific Language (DSL) untuk mempermudah pemodel matematika/analis mengekspresikan variabel tanpa sintaks teknis berulang.

---

### 14. When NOT To Use
- **Tight Inner Loops**: Komputasi numerik intensif yang dieksekusi jutaan kali per detik (misalnya dalam optimasi MCMC numerik). Overhead pembentukan quosure dan parsing tree `rlang` (~50-100 microseconds/call) akan mengakumulasi latency besar. Gunakan base matrix vectorization atau C++ via `Rcpp`.
- **Fungsi Utility Standar**: Script ETL sederhana di mana nama kolom bersifat statis dan tidak ada kebutuhan pembungkusan modular.
- Ketika interface fungsi murni cukup menerima input string atau integer indices secara langsung tanpa abstraksi simbolik.

---

### 15. Common Mistakes
1. **Menggunakan `eval(parse(text = ...))`**:
   ```r
   # SANGAT BURUK & RENTAN KEAMANAN:
   eval(parse(text = paste0("data$", col_name)))
   
   # BENAR (Tidy Evaluation):
   data %>% dplyr::pull({{ col_name }})
   ```
2. **Lupa Operator Walrus (`:=`) saat Dynamic LHS**:
   ```r
   # ERROR SINTAKSIS / SALAH HASIL:
   var <- "metric"
   data %>% summarise(var = mean(value)) # Menghasilkan kolom bernama literal 'var'
   
   # BENAR:
   data %>% summarise(!!var := mean(value))
   ```
3. **Double Evaluation of Defused Arguments**: Mengevaluasi argumen yang sama dua kali (misalnya di fungsi filter kemudian di summarise) tanpa menyadari bahwa ekspresi tersebut mengandung efek samping (*side-effects* seperti pembacaan socket streaming atau generator acak).
4. **Kebingungan Identitas `.data` vs `.env`**: Gagal menggunakan pronoun eksplisit saat terdapat tabrakan nama antara variabel pipeline lokal dengan nama kolom data frame.

---

### 16. Best Practices (Production Checklist)
- [ ] **Gunakan Embracing (`{{ }}`)**: Untuk kasus umum pemusan argumen input fungsi tunggal, utamakan operator `{{ var }}` dibandingkan kombinasi eksplisit `enquo()` + `!!`.
- [ ] **Gunakan Pronoun `.data` dan `.env`**: Selalu gunakan `.data$col_name` dan `.env$local_var` dalam library production untuk menghindari warning saat `R CMD check` dan menjamin determinisme.
- [ ] **Cek Validitas Ekspresi**: Validasi keberadaan node menggunakan `quo_is_null()` atau `quo_is_symbol()` sebelum menyuntikkannya ke pipeline inti.
- [ ] **Batasi Metaprogramming di Batas Interface**: Tangkap dan defuse ekspresi di layer terluar (*boundary layer*), konversikan menjadi struktur data terstandar secepat mungkin di lapisan domain dalam.

---

### 17. Troubleshooting

#### Masalah 1: `object '...' not found` padahal kolom ada di Data Frame
*Penyebab*: Terjadi *unquote leak* atau evaluasi dilakukan pada environment pemanggil yang tidak memiliki akses ke layer data mask.
*Solusi*: Periksa apakah ekspresi di-evaluasi menggunakan `eval()` standar, bukan `rlang::eval_tidy(expr, data = data_mask)`.

#### Masalah 2: Debugging kegagalan substitusi AST
*Penyebab*: Operator unquote `!!` tidak bekerja di tempat yang diharapkan karena fungsi target tidak mendukung Tidy Evaluation.
*Solusi*: Gunakan `rlang::qq_show()` untuk menginspeksi hasil akhir pohon AST sebelum diteruskan ke fungsi target:
```r
target_col <- sym("mpg")
rlang::qq_show(df %>% select(!!target_col))
# Output memperlihatkan rekonstruksi tepat dari ekspresi:
# df %>% select(mpg)
```

#### Masalah 3: Error `The dynamic LHS operator := is required`
*Penyebab*: Menggunakan `=` standar saat sisi kiri ekspresi adalah hasil injeksi AST.
*Solusi*: Ganti assignment `=` dengan `:=` saat mendefinisikan nama variabel dinamis di dalam fungsi-fungsi `tidyverse`.

---

### 18. Exercise
**Tugas**:
Implementasikan fungsi bernama `safe_conditional_aggregate()` dengan spesifikasi berikut:
1. Menerima argumen: `df`, `group_var`, `agg_var`, `threshold_val`.
2. Menggunakan mekanisme Tidy Evaluation untuk mengelompokkan data berdasarkan `group_var`.
3. Menghitung rata-rata dari `agg_var` hanya untuk baris di mana `agg_var > threshold_val`.
4. Menyimpan hasil dalam nama kolom dinamis: `avg_<nama_agg_var>`.
5. Kode dilarang menggunakan manipulasi string via `eval(parse())`.

**Draft Template Pengujian**:
```r
# Data test
test_df <- tibble(
  category = c("A", "A", "B", "B", "B"),
  val = c(10, 50, 20, 5, 80)
)

# Output yang diharapkan dari: safe_conditional_aggregate(test_df, category, val, 15)
# category  avg_val
# <chr>       <dbl>
# A              50
# B              50
```

---

### 19. Challenge
**Tantangan Arsitektur**: Bangun mini DSL execution engine independen bernama `eval_secure_dsl()`:
- Input: Objek `data.frame` dan formula ekspresi `user_expr` yang belum dievaluasi.
- Persyaratan:
  1. Engine harus mengevaluasi ekspresi hanya mengizinkan operator matematika dasar: `+`, `-`, `*`, `/` dan fungsi vektor `c()`.
  2. Jika user mencoba memanggil fungsi sistemik berbahaya seperti `system()`, `file.remove()`, atau bahkan fungsi dasar tak berizin seperti `q()`, engine harus membedah AST, mendeteksi node fungsi yang dilarang (*blacklisted call nodes*), membatalkan eksekusi, dan melempar error struktural via `rlang::abort()`.
  3. Validasi harus terjadi secara rekursif murni pada node AST sebelum `eval_tidy()` dipanggil.

---

### 20. Summary
- Kode R adalah data. R memproses sintaks melalui konversi kode mentah menjadi **Abstract Syntax Tree (AST)** yang terdiri atas calls (`LANGSXP`), symbols (`SYMSXP`), dan literals.
- **NSE Klasik** via `substitute()` dan `eval()` memiliki kelemahan struktural pada isolasi leksikal (*hygiene*), rentan terhadap *scope collisions*.
- **Tidy Evaluation Engine** (`rlang`) menyediakan paradigma terpadu melalui **Quosure** (AST + Environment), memisahkan context data mask (`.data`) dengan lexical scope (`.env`).
- Manipulasi AST modern didorong oleh tiga pola utama: **Defusal** (`enquo()`), **Injection** (`!!`, `!!!`, `{{ }}`), dan **Data Masking** (`eval_tidy()`), menyediakan basis yang aman dan deklaratif untuk membangun sistem pipeline analitik enterprise skala besar.