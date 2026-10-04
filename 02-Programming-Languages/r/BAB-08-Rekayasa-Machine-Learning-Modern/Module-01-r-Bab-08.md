# Bab 08 Module 01: Metaprogramming & Tidy Evaluation (`rlang`, AST, dan Quasiquotation)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengonstruksi dan membedah struktur internal *Abstract Syntax Tree* (AST) dari ekspresi R menggunakan perangkat inspeksi visual dan representasi data tingkat rendah.
- Mengimplementasikan konsep *Non-Standard Evaluation* (NSE) dan *Tidy Evaluation* secara aman (*robust*) untuk membungkus fungsi-fungsi *data-masking* (seperti `dplyr` dan `tidyr`) ke dalam API produksi yang dapat digunakan kembali (*reusable*).
- Menavigasi dan memanipulasi ekspresi tertunda (*defused expressions*) serta *quosures* menggunakan kerangka kerja `rlang` tanpa menimbulkan kebocoran lingkungan (*environment leakage*) atau *scoping ambiguity*.
- Menerapkan mekanisme injeksi ekspresi (*quasiquotation*) dengan operator *embrace* (`{{ }}`), unquote (`!!`), dan unquote-splice (`!!!`) untuk menyusun kueri analitik dinamis berskala enterprise.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta didik wajib menguasai:
- **Arsitektur Objek R**: Pemahaman mendalam tentang tipe data dasar (*atomic vectors*, *lists*, *pairlists*, dan *environments*).
- **Lexical Scoping & Closures**: Mekanisme pencarian simbol, *binding* lingkungan, dan siklus hidup variabel dalam pemanggilan fungsi (*frame* dan *call stack*).
- **Paradigma Functional Programming**: Manipulasi fungsi tingkat tinggi (*higher-order functions*) serta abstraksi fungsi menggunakan paket `purrr`.
- **Ekosistem Tidyverse**: Pengalaman praktis menggunakan `dplyr` untuk manipulasi data tabular, khususnya ketergantungan sintaksis terhadap nama kolom tanpa tanda petik (*bare column names*).

---

### 3. Concept
R merupakan bahasa pemrograman yang bersifat *homoiconic* (sebagian besar diturunkan dari LISP), artinya representasi kode program di dalam memori disimpan menggunakan struktur data yang sama dengan data biasa. Ketika sebuah perintah dimasukkan ke dalam R, interpreter tidak langsung mengeksekusinya secara linear, melainkan melakukan proses parsing teks menjadi struktur data pohon yang disebut **Abstract Syntax Tree (AST)**.

Tiga tipe data inti yang menyusun ekspresi kode di R adalah:
1. **Constants**: Nilai literal skalar seperti numerik, string, atau logika (contoh: `10`, `"prod"`, `TRUE`).
2. **Symbols (Names)**: Representasi identitas variabel yang merujuk pada objek tertentu dalam sebuah *environment* (contoh: `x`, `mean`).
3. **Calls**: Ekspresi pemanggilan fungsi yang direpresentasikan secara internal sebagai *pairlist*, di mana elemen pertama adalah fungsi yang dipanggil, dan elemen-elemen berikutnya adalah argumen yang dipasok (contoh: `f(x, y = 1)`).

R secara fundamental menerapkan *lazy evaluation* (evaluasi malas): argumen fungsi tidak dievaluasi sebelum nilainya benar-benar dibutuhkan di dalam tubuh fungsi. Karakteristik ini dimanfaatkan oleh **Non-Standard Evaluation (NSE)**, di mana fungsi menangkap ekspresi kode mentah (*defused code*) dari argumen pemanggil sebelum dihitung, lalu mengubah konteks evaluasinya ke struktur data internal (seperti baris-baris pada *data frame*).

Namun, NSE murni pada basis R rentan terhadap isu referensial (*ambiguity* dan *hygiene*). **Tidy Evaluation** (dikelola melalui pustaka `rlang`) menyelesaikan masalah ini dengan memperkenalkan struktur data **Quosure**: gabungan (*closure*) antara sebuah ekspresi (*code*) dengan lingkungan leksikal asalnya (*environment*). Quosure menjamin bahwa simbol-simbol di luar data mask tetap dievaluasi pada *environment* tempat kode itu ditulis, mencegah *name collision* antara nama kolom data frame dan variabel global.

---

### 4. Why
Dalam rekayasa perangkat lunak modern menggunakan R, menulis skrip analitik ad-hoc berbeda signifikan dengan membangun pustaka (*package*) atau layanan mikro (*production service*).

1. **Eliminasi Kerapuhan Kode (*Fragile Code*)**:
   Jika Anda menulis fungsi pembungkus (*wrapper*) untuk `dplyr::filter` atau `dplyr::mutate` dengan pendekatan evaluasi standar (*Standard Evaluation* / string manipulation), kode akan rentan terhadap kegagalan runtime akibat perubahan konteks lingkungan atau *injection vulnerabilities*.
2. **Ambiguitas Kolom vs Variabel (*Data Masking Ambiguity*)**:
   Ketika nama kolom pada data frame identik dengan variabel lokal di lingkungan fungsi (misal kolom `df$user_id` dan parameter fungsi `user_id`), interpreter R tanpa tidy evaluation berisiko mengambil nilai yang salah secara senyap (*silent bug*). Tidy evaluation menyediakan kepastian deterministik melalui pronomina (*pronouns*) `.data` dan `.env`.
3. **Kebutuhan Automasi Dinamis di Tingkat Enterprise**:
   Sistem pelaporan otomatis atau pipeline data sering kali menerima input berupa daftar variabel target, formula dinamis, atau konfigurasi metrik via JSON/YAML. Metaprogramming memungkinkan penyusunan kueri data pipelines secara dinamis di tingkat sintaksis sebelum dieksekusi, menghemat jutaan komputasi redundan dan menghindari pembuatan duplikasi fungsi.

---

### 5. What
Komponen arsitektural utama dalam ekosistem `rlang` dan Tidy Evaluation meliputi:

- **`rlang::expr()`**: Menangkap ekspresi R literal tanpa mengevaluasinya.
- **`rlang::enquo()` / `rlang::enquos()`**: Menangkap argumen yang dipasok pengguna dari pemanggil fungsi ke dalam format *quosure* (tunggal atau jamak), mengunci ekspresi beserta lingkungan asalnya.
- **Operator Embrace `{{ }}` (Curly-Curly)**: Gula sintaksis (*syntactic sugar*) untuk kombinasi `enquo()` dan unquote (`!!`). Digunakan untuk meneruskan argumen kolom dari satu fungsi ke fungsi *data-masking* lainnya secara langsung.
- **Unquoting (`!!` / Bang-Bang)**: Menginjeksi nilai atau ekspresi lain ke dalam sebuah ekspresi yang ditangkap, menggantikan simbol dengan representasi pohon sintaksisnya sebelum evaluasi.
- **Unquote-Splice (`!!!` / Triple Bang)**: Menginjeksi sebuah list ekspresi/simbol ke dalam pemanggilan fungsi sebagai beberapa argumen individual terpisah.
- **Pronomina `.data` dan `.env`**: Penanda eksplisit lingkup pencarian variabel di dalam fungsi *data-masking*. `.data$var` memaksa R mencari `var` di dalam kolom data frame, sedangkan `.env$var` memaksanya mencari di lingkungan pemanggil/lokal.

---

### 6. How
Alur kerja pemrosesan Tidy Evaluation diilustrasikan dalam tahapan operasional berikut:

```
[Kode Pengguna: my_func(df, target_col)]
                   │
                   ▼ (Capture / Defusal)
[enquo(target_col) / {{ target_col }}] ─── Mengunci: Ekspresi + Calling Env
                   │
                   ▼ (AST Reconstruction / Quasiquotation)
[Injeksi Simbol ke Pipeline dplyr/data.table] ─── Modifikasi AST sebelum runtime
                   │
                   ▼ (Data Mask Evaluation)
[eval_tidy() / Internal Tidy Engine]
   ├─ 1. Cari simbol di dalam Data Frame (.data)
   └─ 2. Jika tidak ditemukan, cari di Lingkungan Asal Quosure (.env)
                   │
                   ▼
           [Hasil Komputasi]
```

1. **Defusal (Penundaan)**: Ketika fungsi menerima argumen tanpa tanda petik, sistem menangkap ekspresi tersebut menggunakan mekanisme *promise reflection* R, membentuk objek `quosure`.
2. **Inspection & Mutation**: Pengembang dapat memeriksa token AST, memvalidasi tipe AST, atau merekonstruksi *call* secara terprogram.
3. **Injection**: Menggunakan unquote (`!!` atau `{{ }}`), ekspresi yang telah ditangkap dilekatkan ke dalam ekspresi induk (misalnya ekspresi kalkulasi agregasi).
4. **Resumed Evaluation**: Pustaka eksekusi (seperti `dplyr::summarise`) memetakan baris-baris data frame ke lingkungan sementara (*mask environment*) yang menimpa rantai pencarian leksikal biasa secara terkendali.

---

### 7. Analogy
Bayangkan Anda memesan makanan di sebuah restoran menggunakan formulir pesanan khusus:
- **Standard Evaluation**: Anda memberikan makanan jadi kepada pelayan. Variabel sudah harus memiliki nilai konkret di awal.
- **Metaprogramming (Tidy Evaluation)**: Anda menuliskan *resep atau instruksi* di atas kertas: `"Tambahkan garam secukupnya dari toples meja"`. Tulisan tersebut adalah **Defused Expression (AST)**.
- **Quosure**: Selain menuliskan resep, Anda melampirkan informasi geografis: `"Toples meja ini merujuk ke meja nomor 4 tempat saya duduk saat menulis, bukan toples meja dapur"`. Quosure menjaga agar bumbu tidak tertukar dengan bumbu dapur restoran.
- **Embrace (`{{ }}`)**: Amplop transparan tempat Anda menyelipkan resep pelanggan Anda langsung ke koki utama tanpa membuka atau mengubah isinya di tengah jalan.
- **Data Mask**: Koki membawa bahan makanan Anda ke meja kerja. Di meja kerja, kata `"garam"` pertama-tama dicocokkan dengan bahan yang ada di mangkuk kerja (kolom data frame). Jika di mangkuk tidak ada garam, koki mencari garam di saku kemeja Anda (lingkungan luar / `.env`).

---

### 8. Diagram
Berikut adalah representasi topologi bagaimana sebuah ekspresi bertingkat dipecah menjadi AST dan diintegrasikan ke dalam Quosure:

```
Ekspresi: total = sum(revenue * (1 - tax_rate))

                  Call: [ = ]
                 /           \
           Symbol: total      Call: [ sum ]
                                   │
                              Argument: [ * ]
                               /            \
                       Symbol: revenue       Call: [ - ]
                                             /         \
                                        Constant: 1   Symbol: tax_rate

┌─────────────────────────────────────────────────────────────┐
│                       QUOSURE                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Expr: sum(revenue * (1 - tax_rate))                   │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Env:  <environment: 0x7fa2b84c8a20> (Caller Frame)   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                               │
               Diinjeksikan via Data Masking
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    EVALUATION MASK                          │
│  Top Frame:    [revenue = c(100, 200, 300)] (From Data)    │
│  Enclosing:    [tax_rate = 0.11]            (From Quosure)  │
└─────────────────────────────────────────────────────────────┘
```

---

### 9. Simple Example
Berikut demonstrasi dasar membedah ekspresi, melihat pohon AST, dan menyuntikkan variabel menggunakan paket `rlang` dan `lobstr`:

```r
# Pastikan library terpasang
library(rlang)
library(lobstr)

# 1. Menginspeksi Pohon Sintaksis Abstrak (AST)
ast(total_sales <- sum(units * price, na.rm = TRUE))

# 2. Defusing Ekspresi Manual
my_expr <- expr(x + y * 2)
print(class(my_expr)) # [1] "call"
print(my_expr[[1]])   # `+`
print(my_expr[[2]])   # x
print(my_expr[[3]])   # y * 2 (sub-call)

# 3. Quasiquotation: Unquoting Sederhana
target_var <- sym("revenue")
multiplier <- 1.15

# Rakit ekspresi secara dinamis
injected_call <- expr(adjusted_val <- !!target_var * !!multiplier)
print(injected_call)
# Output: adjusted_val <- revenue * 1.15
```

---

### 10. Practical Example
Berikut adalah implementasi modul analitik industri: membuat fungsi dinamis yang melakukan standarisasi data (*z-score normalization*) dan agregasi modular dengan validasi parameter yang ketat, mengamankan pipeline dari ambiguitas data masking.

```r
library(rlang)
library(dplyr)

#' Menghitung metrik performa grup secara dinamis
#' @param data Data frame input
#' @param group_col Kolom kategorikal untuk pengelompokan (bare name)
#' @param target_col Kolom numerik yang akan diagregasi (bare name)
#' @param weight_col Kolom bobot numerik opsional (bare name atau NULL)
compute_grouped_metric <- function(data, group_col, target_col, weight_col = NULL) {
  # Validasi integritas input dasar
  if (!is.data.frame(data)) {
    abort("Argumen `data` wajib bertipe data.frame atau tibble.")
  }

  # Defuse ekspresi argumen menggunakan embrace dan enquo
  weight_quo <- enquo(weight_col)

  # Bangun pipeline dengan data-masking aman menggunakan .data
  res <- data %>%
    group_by({{ group_col }})

  if (quo_is_null(weight_quo)) {
    # Agregasi unweighted standar
    res <- res %>%
      summarise(
        mean_value = mean({{ target_col }}, na.rm = TRUE),
        median_value = median({{ target_col }}, na.rm = TRUE),
        record_count = dplyr::n(),
        .groups = "drop"
      )
  } else {
    # Agregasi berbobot dinamis via quasiquotation manual
    res <- res %>%
      summarise(
        mean_value = weighted.mean({{ target_col }}, w = !!weight_quo, na.rm = TRUE),
        record_count = dplyr::n(),
        .groups = "drop"
      )
  }

  return(res)
}

# Simulasi Penggunaan Produksi
sales_data <- tibble(
  region = c("APAC", "APAC", "EMEA", "EMEA", "LATAM"),
  sales = c(1500, 2300, 3100, 1800, 950),
  volume = c(10, 15, 20, 12, 8)
)

# 1. Eksekusi tanpa parameter opsional
report_unweighted <- compute_grouped_metric(
  data = sales_data,
  group_col = region,
  target_col = sales
)
print(report_unweighted)

# 2. Eksekusi dengan parameter opsional
report_weighted <- compute_grouped_metric(
  data = sales_data,
  group_col = region,
  target_col = sales,
  weight_col = volume
)
print(report_weighted)
```

---

### 11. Real World Example
**Skenario**: Sistem *Risk Engine* FinTech Multi-Tenant.
Platform analitik kredit skala besar menerima konfigurasi kalkulasi rasio risiko via antarmuka REST API dalam format metadata dinamis. Pipeline harus mengubah daftar parameter konfigurasi menjadi serangkaian komputasi transformasi data frame bernilai miliaran baris tanpa menulis kode redundan untuk setiap metrik.

```r
library(rlang)
library(dplyr)
library(purrr)

# Konfigurasi transformasi metrik dari database konfigurasi (contoh output parsing JSON)
metric_configs <- list(
  list(
    metric_name = "debt_to_income_ratio",
    numerator = "total_debt",
    denominator = "total_income"
  ),
  list(
    metric_name = "credit_utilization_ratio",
    numerator = "revolving_balance",
    denominator = "credit_limit"
  )
)

# Generator kueri dinamis tingkat enterprise
build_feature_pipeline <- function(data, configs) {
  # Ekstraksi dan konstruksi daftar ekspresi secara dinamis
  mutation_expressions <- map(configs, function(cfg) {
    # Buat simbol aman
    target_sym <- sym(cfg$metric_name)
    num_sym <- sym(cfg$numerator)
    den_sym <- sym(cfg$denominator)

    # Konstruksi ekspresi formula: target = (num / (den + 1e-6))
    expr(!!target_sym := .data[[as_string(num_sym)]] / (.data[[as_string(den_sym)]] + 1e-6))
  })

  # Suntikkan semua ekspresi secara bersamaan menggunakan splicing (!!!)
  transformed_data <- data %>%
    mutate(!!!mutation_expressions)

  return(transformed_data)
}

# Data mentah portofolio kredit
portfolio_df <- tibble(
  borrower_id = 101:103,
  total_debt = c(50000, 120000, 0),
  total_income = c(75000, 100000, 45000),
  revolving_balance = c(1200, 8500, 300),
  credit_limit = c(5000, 10000, 2000)
)

# Eksekusi pipeline otomatis
engineered_features <- build_feature_pipeline(portfolio_df, metric_configs)
print(glimpse(engineered_features))
```

---

### 12. Trade-offs

| Dimensi | Pendekatan Standard Evaluation (String / Indices) | Pendekatan Tidy Evaluation (`rlang` / Quasiquotation) |
| :--- | :--- | :--- |
| **Kelebihan (Advantages)** | Sangat transparan, dependensi eksternal nol (Base R), mudah di-unit test oleh programmer pemula. | Sintaksis konsisten dengan Tidyverse, higienitas lingkungan terjamin, sintaksis bersih tanpa kutip ganda berlebih. |
| **Kekurangan (Disadvantages)** | Sangat verbose, rentan *name collision*, sulit membangun abstraksi logika DSL (*Domain Specific Language*). | Kurva pembelajaran curam (*steep learning curve*), inferensi statis (*linter*) lebih sulit membaca variabel tak berwujud. |
| **Kompleksitas (Complexity)** | Logika parsing teks manual sering berujung pada percabangan kode yang berantakan (*spaghetti regex*). | Kompleksitas konseptual tinggi: developer wajib memahami AST, *promises*, dan struktur *quosures*. |
| **Performa (Performance)** | Overhead pemanggilan sangat kecil; eksekusi operasi vektor langsung berbasis indeks numerik. | Terdapat *micro-overhead* saat konversi token string menjadi AST dan pembuatan lingkungan *quosure* (nanodetik). |
| **Biaya Rekayasa (Cost)** | Biaya debugging runtime tinggi karena potensi silent bug terkait scoping leksikal. | Biaya arsitektur di awal tinggi, namun menekan biaya pemeliharaan (*maintenance cost*) pipeline analitik jangka panjang. |

---

### 13. When To Use
- Saat membangun paket internal organisasi (*internal R packages*) yang membungkus fungsi `dplyr`, `ggplot2`, atau `tidyr`.
- Ketika Anda perlu menyediakan DSL internal untuk analisis data domain spesifik.
- Saat membuat fungsi dengan parameter kolom variabel bebas di mana pengguna mengharapkan perilaku antarmuka deklaratif tanpa kutip (*bare variable names*).
- Pada pipeline *feature engineering* dinamis berbasis file konfigurasi metadata (misalnya YAML/JSON-driven dynamic pipelines).

---

### 14. When NOT To Use
- Komputasi berulang dalam loop *low-latency* ekstrim (>100.000 iterasi mikro per detik); gunakan `data.table` sintaks standar atau antarmuka C++ (`Rcpp`).
- Prosedur transformasi berbasis indeks matriks linier sederhana di mana posisi kolom tetap (*static array index*).
- Ketika seluruh komponen kode dikembangkan murni menggunakan dependensi nol (*Base R strict compliance*) untuk sistem embedded atau infrastruktur dengan isolasi paket mutlak.
- Fungsi yang menerima vektor string sebagai parameter eksplisit (`char_vector`); gunakan pendekatan `.data[[var_name]]` alih-alih metaprogramming penuh.

---

### 15. Common Mistakes
1. **Menggunakan `eval(parse(text = ...))`**:
   Pola anti-arsitektur klasik. Menyusun string kode lalu memparsingnya membatalkan semua optimasi bytecode R dan menciptakan kerentanan eksekusi kode sembarangan (*code injection*).
2. **Lupa Menerapkan Operator Walrus (`:=`) saat Unquoting Nama Kolom**:
   Sintaksis R standar menolak ekspresi di sisi kiri operator `=` biasa. Penulisan `mutate(!!sym_name = val)` akan memicu sintaksis error; wajib menggunakan `mutate(!!sym_name := val)`.
3. **Mengabaikan Pronomina `.data` dalam Pembuatan Paket R**:
   Memanggil nama kolom langsung di dalam kode paket tanpa mekanisme `{{ }}` atau `.data$` akan menghasilkan peringatan `R CMD check`: *"no visible binding for global variable"*.
4. **Salah Membedakan `sym()` dan `expr()`**:
   Menerapkan `sym()` pada string formula ekspresi majemuk (seperti `"x + y"`) akan menghasilkan error simbol tidak valid. `sym()` hanya untuk satu nama token variabel; gunakan `parse_expr()` untuk ekspresi gabungan.

---

### 16. Best Practices (Production Checklist)
- [ ] Gunakan sintaksis modern embrace (`{{ col }}`) sebagai pilihan utama untuk delegasi argumen; hindari kombinasi verbose `enquo()` + `!!` kecuali Anda harus memodifikasi AST di dalamnya.
- [ ] Terapkan pronomina `.data[[var_string]]` jika parameter yang masuk ke fungsi sudah berwujud string (`character`), alih-alih mengubah string menjadi simbol via `sym()` lalu menginjeksinya.
- [ ] Pasang deklarasi `#' @importFrom rlang .data` pada dokumentasi roxygen2 untuk membungkam peringatan *unbound variable* di CRAN checklist.
- [ ] Gunakan `rlang::qq_show()` saat fase debugging untuk mencetak bentuk konkret pohon ekspresi setelah proses *unquoting* sebelum dieksekusi.
- [ ] Validasi tipe quosure di awal fungsi menggunakan `quo_is_null()`, `quo_is_symbol()`, atau pemeriksaan defensif via pustaka `checkmate` / `rlang::abort`.

---

### 17. Troubleshooting

#### Issue 1: `object 'col_name' not found` saat evaluasi
- **Gejala**: Fungsi berhenti saat mengeksekusi pipeline tidyverse di dalam sub-lingkungan.
- **Akar Masalah**: Evaluator mencari variabel pada *global environment* karena argumen dievaluasi secara eager sebelum mencapai data mask, atau fungsi wrapper tidak menangkap argumen sebagai ekspresi tertunda.
- **Solusi**: Pastikan argumen fungsi dibungkus dengan `{{ }}` atau ditangkap eksplisit dengan `enquo()`:
  ```r
  # SALAH
  my_summary <- function(df, var) { df %>% summarise(m = mean(var)) }
  # BENAR
  my_summary <- function(df, var) { df %>% summarise(m = mean({{ var }})) }
  ```

#### Issue 2: Masalah referensi variabel ganda (Data vs Local Variable Ambiguity)
- **Gejala**: Nilai filter tidak berubah meskipun parameter lokal fungsi dimodifikasi.
- **Akar Masalah**: Nama argumen fungsi menimpa atau tertimpa oleh nama kolom di dalam data frame (*data-mask shadowing*).
- **Solusi**: Gunakan pemisahan pronomina eksplisit:
  ```r
  filter_users <- function(df, status) {
    # .data$status = kolom dalam df; .env$status = nilai parameter dari function frame
    df %>% filter(.data$status == .env$status)
  }
  ```

---

### 18. Exercise
**Instruksi Praktik Mandiri**:
Buatlah sebuah fungsi bernama `safe_top_n()` dengan spesifikasi berikut:
1. Menerima empat parameter: `data` (data.frame), `group_var` (bare name), `rank_var` (bare name), dan `n` (bilangan bulat, default = 5).
2. Melakukan validasi bahwa nilai `n` harus berupa integer positif skalar. Jika tidak, lemparkan error terstruktur menggunakan `rlang::abort()`.
3. Mengembalikan `n` baris teratas per kelompok berdasarkan urutan menurun (*descending*) dari kolom `rank_var`.
4. Seluruh delegasi ekspresi harus mengimplementasikan operator *embrace* (`{{ }}`).

---

### 19. Challenge
**Rancang dan Bangun: Dynamic SQL/AST Query Validator Engine**
Bangun sebuah fungsi arsitektural bernama `compile_safe_filter(allowed_columns, condition_expr)`:
- **Tuntutan Sistem**: Fungsi harus menerima vektor karakter `allowed_columns` (daftar kolom yang diizinkan untuk di-query) dan sebuah ekspresi logika tak terevaluasi (*defused expression*) pada argumen `condition_expr`.
- **Mekanisme AST Walk**: Tulis algoritma rekursif yang menelusuri Abstract Syntax Tree dari `condition_expr`. Verifikasi setiap node `Symbol`:
  - Jika simbol yang ditemukan bukan merupakan operator dasar (`+`, `-`, `*`, `/`, `==`, `!=`, `>`, `<`, `>=`, `<=`, `&`, `|`, `%in%`) DAN tidak ada di dalam daftar `allowed_columns`, tolak eksekusi dengan melempar exception: `"Unauthorized column access: [nama_simbol]"`.
- **Eksekusi**: Uji fungsi ini terhadap data frame tiruan dengan ekspresi legal (misal: `age > 21 & region == "APAC"`) dan ekspresi ilegal yang mencoba menyusupkan pemanggilan kolom terlarang (misal: `salary > 50000 | ssn == "12345"`).

---

### 20. Summary
Metaprogramming dan Tidy Evaluation mentransformasi R dari sekadar bahasa skrip komputasi statistik menjadi lingkungan pengembangan perangkat lunak dinamis tingkat lanjut. 

Dengan memperlakukan kode sebagai data melalui **Abstract Syntax Tree (AST)**, pengembang dapat mengendalikan siklus hidup eksekusi (*evaluation life cycle*). Kerangka kerja `rlang` menyediakan primitives formal: **Quosures** untuk menyelesaikan keterikatan leksikal secara deterministik, **Quasiquotation** (`!!`, `!!!`, `{{ }}`) untuk menyusun pohon kode secara programatik, dan **Pronouns** (`.data`, `.env`) untuk menghapus ketidakjelasan referensi dalam teknik *data-masking*. Penguasaan materi ini merupakan fondasi wajib dalam arsitektur paket R modern berskala enterprise.