# BAB 06: Quiz, Challenge, & Knowledge Check
**Functional Programming & Metaprogramming**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Lexical Scoping dan Arsitektur Closure
Jelaskan secara mendalam bagaimana R mengimplementasikan *lexical scoping* saat sebuah fungsi mengembalikan fungsi lain (*function factory*). Jelaskan lifecycle dari *enclosing environment*, *binding environment*, dan *execution environment* beserta implikasinya terhadap Garbage Collector (GC) jika *execution environment* memuat objek biner berukuran gigabyte yang tidak lagi direferensikan secara eksplisit oleh closure hasil kembalian.

### Soal 1.2: Evaluasi Non-Standard (NSE) vs Standard Evaluation (SE)
Bandingkan arsitektur eksekusi antara *Standard Evaluation* (SE) berbasis evaluasi *promise* R dengan *Non-Standard Evaluation* (NSE). Mengapa fungsi primitif `substitute()` mampu menangkap ekspresi komputasi sebelum evaluasi terjadi, dan bagaimana struktur objek kelas `call` dan `name`/`symbol` dibedakan di memori internal R?

### Soal 1.3: Quasiquotation dan Konsep Quosure pada Tidy Evaluation
Dalam ekosistem `rlang`/`tidy evaluation`, evaluasi ekspresi sering kali menghadapi masalah *hygiene* dan *scope collision*. Definisikan apa itu *quosure* secara struktural (kombinasi ekspresi dan environment). Mengapa quosure mutlak diperlukan untuk menyelesaikan batasan klasik `substitute()` dan `eval()` saat fungsi pembungkus (wrapper) memanggil fungsi ber-NSE lain di stack pemanggilan yang lebih dalam?

### Soal 1.4: Pure Functions dan Referential Transparency dalam R
Sebuah fungsi dikatakan memiliki sifat *referential transparency* jika pemanggilannya dapat digantikan langsung oleh nilai kembaliannya tanpa mengubah perilaku program. Identifikasi 4 mekanisme laten dalam *runtime* R yang dapat merusak *referential transparency* meskipun fungsi tersebut tidak memodifikasi argumen inputnya secara eksplisit (misal: state global, environment mutation, pseudo-randomness, I/O devices).

### Soal 1.5: Functionals vs Imperative Iteration
Secara mekanis, bagaimana functional seperti `vapply()` atau `purrr::map()` mengelola alokasi memori untuk *pre-allocation* vektor hasil dibandingkan dengan *idiom loop* imperatif `for` standar? Apa trade-off performa antara *dispatch overhead* pemanggilan fungsi tingkat tinggi (higher-order function call overhead) dan fragmentasi memori akibat kegagalan pre-alokasi?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Bedah Abstract Syntax Tree (AST) dan Traversal Rekursif
Diberikan ekspresi R kompleks berikut:
```r
expr <- quote(total_sales <- sum(df$sales[df$region == "APAC"], na.rm = TRUE) * 1.1)
```
Jelaskan struktur pohon AST dari ekspresi di atas (urutan node operator, argumen, dan subsetting). Tuliskan algoritma ringkas (pseudocode atau R code konseptual) untuk melakukan traversal rekursif terhadap AST tersebut guna mendeteksi seluruh simbol variabel yang direferensikan tanpa mengevaluasi ekspresi tersebut.

### Soal 2.2: Mitigasi Memory Bloat pada Function Factory
Perhatikan implementasi factory berikut:
```r
build_model_predictor <- function(data) {
  heavy_diagnostic_matrix <- matrix(rnorm(1e8), nrow = 1e4) # ~800MB
  fitted_coefs <- lm.fit(x = as.matrix(data[, -1]), y = data[, 1])$coefficients
  
  function(new_data) {
    as.matrix(new_data) %*% fitted_coefs
  }
}
```
Meskipun closure yang dihasilkan hanya menggunakan `fitted_coefs`, mengapa instance model tersebut menahan `heavy_diagnostic_matrix` di RAM secara permanen? Jelaskan mekanisme internal parent environment retention di R dan berikan solusi rekonstruksi environment yang aman untuk memutus referensi memori yang tidak terpakai (*unbinding* / *pruning* execution environment).

### Soal 2.3: Data Masking Ambiguity: Simbol Masking vs Environment Hijacking
Saat menggunakan data masking (`rlang::eval_tidy` atau fungsi `dplyr::filter`), jelaskan skenario di mana fenomena *shadowing* atau *variable collision* terjadi antara variabel di kolom data frame dan variabel di local environment fungsi. Bagaimana pronoun `.data` dan `.env` menyelesaikan ambiguitas ini secara eksplisit pada level AST resolution?

### Soal 2.4: Operator Quasiquotation: `!!` vs `!!!` vs `{{ }}`
Jelaskan perbedaan mendasar operasi pada level manipulasi AST antara:
1. Unquote tunggal (`!!`)
2. Splice unquote (`!!!`)
3. Curly-Curly syntax (`{{ }}`)

Tunjukkan contoh ekspresi AST sebelum dan sesudah ekspansi ketika `!!!` diterapkan pada named list of expressions di dalam pemanggilan fungsi pembungkus data manipulation.

### Soal 2.5: Promise Invalidation dan Force Evaluation
Jelaskan bahaya laten dari *lazy evaluation* dalam meta-programming saat menggunakan *loop* untuk membuat daftar closure (misal: higher-order functions dalam loop `lapply` atau `for`). Mengapa kode berikut menghasilkan output yang identik, dan bagaimana `force()` secara internal memodifikasi bit status promise untuk mencegah hal tersebut?
```r
funcs <- list()
for (i in 1:3) {
  funcs[[i]] <- function(x) x + i
}
funcs[[1]](10) # Mengapa menghasilkan 13, bukan 11?
```

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Akibat Overhead Quosure/NSE di Pipeline Skala Tinggi
*Konteks*: Sebuah trading engine analitik memproses stream data tick saham dengan volume 50.000 batch/detik. Tim pengembang membungkus logika agregasi menggunakan metaprogramming `rlang` tingkat tinggi dengan evaluasi dinamis (`rlang::eval_tidy` dan quosure capture menggunakan `enquo()`) di dalam fungsi loop mikro per batch data.
*Masalah*: Profiling CPU menunjukkan 75% waktu komputasi terkonsumsi pada `rlang::quo_get_expr`, alokasi environment quosure, dan traversal data mask lookup, bukan pada perhitungan numerik data agregasi.
*Pertanyaan Diagnostik & Arsitektur*:
1. Mengapa fleksibilitas NSE/Tidy Evaluation sangat mahal (*computationally expensive*) jika dieksekusi berulang-ulang di level iterasi mikro (*hot loop*)?
2. Rancang arsitektur refaktorisasi: Bagaimana memisahkan *compilation step* (parsing & injecting AST satu kali di awal) dari *execution step* (evaluasi berulang berkinerja tinggi menggunakan native vectorization atau primitive standard evaluation)?

### Skenario B: Vulnerability Code Injection pada Dinamisasi Query Dashboard Enterprise
*Konteks*: Sebuah portal Business Intelligence (BI) enterprise mengizinkan pengguna menyusun filter analitik secara dinamis melalui UI. Pengembang backend mengimplementasikan fungsi filter R berikut:
```r
execute_user_filter <- function(df, raw_filter_string) {
  filter_expr <- parse(text = raw_filter_string)
  eval(filter_expr, envir = df, enclos = parent.frame())
}
```
*Insiden*: Seorang analis secara sengaja atau tidak sengaja memasukkan input teks: `system('rm -rf /data/prod', intern = TRUE)` atau membaca file credential environment `readLines('.Renviron')`.
*Pertanyaan Diagnostik & Penanganan*:
1. Identifikasi kerentanan fatal dari pola `eval(parse(text = ...))` terhadap integritas proses R runtime.
2. Rancang implementasi *AST parsing & sanitization engine* yang aman: Bagaimana cara melakukan inspeksi dan validasi terhadap pohon ekspresi sebelum dievaluasi, sehingga hanya operator perbandingan (`==`, `!=`, `<`, `>`) dan nama kolom yang valid yang diizinkan untuk dieksekusi?

### Skenario C: Dilema Arsitektur: DSL Berbasis NSE vs Explicit Functional Interface
*Konteks*: Arsitek sistem diminta mendesain library audit risiko kredit internal bank yang akan digunakan oleh dua entitas: (1) Data Scientist interaktif via RStudio/Jupyter, dan (2) Microservice pipeline otomatis via REST API (Plumber) yang menerima konfigurasi filtering dalam format payload JSON.
*Dilema*: Jika library dirancang murni berbasis NSE (`rlang`/`tidy-eval`), integrasi API JSON sangat canggung karena harus mengonversi string JSON menjadi quosures. Sebaliknya, jika murni berbasis SE (string argumen atau functional programming standar), pengguna interaktif mengeluhkan sintaks yang terlalu verbose.
*Pertanyaan Arsitektur*:
1. Bagaimana Anda merancang pola *Dual Interface Architecture* (SE/NSE duality) yang konsisten secara arsitektural tanpa menduplikasi logika domain bisnis di codebase?
2. Bagaimana strategi penanganan error context (backtrace) agar runtime error yang terjadi di deep call stack NSE dapat dipahami secara manusiawi oleh pemanggil API JSON tanpa membocorkan trace internal metaprogramming sistem?

---

## 4. Chapter Challenge

### Tantangan Praktis: Rancang Bangun "Production-Grade Safe Query DSL & AST Compiler Engine"

#### Problem Statement
Dalam infrastruktur analitik terdistribusi, Anda dilarang mengeksekusi kode arbitrary R dari luar sistem, namun Anda harus menyediakan Domain-Specific Language (DSL) berbasis formula/ekspresi fungsional yang deklaratif, aman (*sandboxed*), dan ultra-cepat untuk memproses mutasi dan filtering data frame enterprise tanpa dependency eksternal selain base R dan `rlang`.

#### Requirements
1. **Dynamic Expression Parser & Whitelist AST Inspector**:
   * Buat fungsi `compile_safe_dsl(expr)` yang menerima raw expression R (bukan string evaluable langsung).
   * Lakukan validasi traversal AST: Izinkan *hanya* operator matematika dasar (`+`, `-`, `*`, `/`), operator logika (`&`, `|`, `!`), pembanding (`==`, `!=`, `>`, `<`, `>=`, `<=`), serta safe primitives (`c`, `log`, `exp`, `abs`, `ifelse`).
   * Jika AST memuat pemanggilan fungsi di luar whitelist (misal `system`, `eval`, `file`, `source`, `assign`), compiler harus melempar error struktural spesifik: `"SECURITY_VIOLATION: Unauthorized AST node <nama_fungsi>"`.
2. **Deterministic Data Masking Compiler**:
   * Fungsi harus mengembalikan closure yang teroptimasi: `executor(data_frame)`.
   * Closure ini harus mengunci dependency environment, membuang semua objek asing dari scope kompilasi untuk mencegah memory bloat, dan mengevaluasi ekspresi secara aman terhadap data frame yang diberikan via *tidy evaluation* atau *sandboxed environment*.
   * Tangani dynamic scoping: Jika kolom yang diminta di ekspresi tidak ada di `data_frame`, compile engine harus melempar custom condition error dengan pesan yang mencantumkan nama kolom yang hilang.
3. **Quasiquotation Pipeline Extension**:
   * Sediakan fungsi wrapper `safe_mutate(.data, ...)` yang memanfaatkan `rlang::enquos(...)` dan `rlang::dots_list()`.
   * Mendukung injection operator `{{ }}` dan splice unquote `!!!` dari argumen pemanggil.
   * Setiap ekspresi yang diinjeksi harus otomatis melewati AST Inspector sebelum dievaluasi.

#### Constraints
* **Zero Text-Parsing**: Dilarang keras menggunakan `eval(parse(text = ...))`.
* **Zero Memory Retention**: Environment closure yang dihasilkan tidak boleh menahan data frame sampel kompilasi.
* **Deterministic Behavior**: Evaluasi tidak boleh bergantung pada variabel global di `.GlobalEnv`. Semua simbol harus berasal dari data frame atau local parameters yang diinjeksi via unquoting.

#### Expected Output
1. Script R modular yang berisi:
   * Engine validasi AST rekursif (`inspect_ast(node)`).
   * Compiler pipeline (`compile_safe_dsl`).
   * Safe mutate engine (`safe_mutate`).
2. Test suite minimal yang mendemonstrasikan:
   * **Eksekusi Sukses**: Evaluasi ekspresi aritmatika & logika kompleks menggunakan quasiquotation.
   * **Security Block**: Penggagalan eksekusi saat disuntik ekspresi terlarang (misal: `safe_mutate(df, col = system("whoami"))`).
   * **Scope Isolation**: Penggagalan saat ekspresi mereferensikan variabel bebas di `.GlobalEnv` yang tidak di-unquote secara eksplisit.
   * **Memory Cleanliness**: Uji profiling environment bahwa ukuran memori closure tidak bertambah seiring bertambahnya data sampel yang dikompilasi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi lingkungan R: Lexical scoping, Execution Environment, Enclosing Environment, Binding Environment, dan Calling Environment.
- [ ] Perbedaan fundamental antara objek bahasa R: `symbol` (name), `call` (language objects), `pairlist`, dan constant literals.
- [ ] Konsep Promise: Value, Expression, Environment, dan fase transisi evaluasi (*lazy evaluation mechanics*).
- [ ] Mekanisme kerja Quasiquotation: Parsing AST, unquoting (`!!`), splicing (`!!!`), dan wrapping expression (`quo`, `enquo`).
- [ ] Perbedaan evaluasi data masking antara base R (`eval()`, `substitute()`, `with()`) dan tidyverse architecture (`rlang::eval_tidy`, `.data`, `.env`).
- [ ] Mengapa closure dapat mempertahankan execution environment di RAM dan bagaimana struktur garbage collection R mendeteksi referensi tak terputus.

### Saya tidak perlu menghafal:
- [ ] Seluruh nomor indeks opcode internal R bytecode engine (`BCNODES`).
- [ ] Daftar lengkap ribuan fungsi non-standar base R yang menggunakan NSE secara inkonsisten (`subset`, `transform`, `curve`, dll.).
- [ ] Struktur data pointer internal C (SEXP pointers) secara detail di luar pemahaman konseptual representasi R-level-nya.

### Saya harus bisa melakukan:
- [ ] Mengurai (*dissect*) ekspresi R kompleks ke dalam bentuk pohon (*Abstract Syntax Tree*) menggunakan `lobstr::ast()` atau base recursive inspection.
- [ ] Membangun *function factory* bebas dari memory leak dengan teknik environment sanitization / pruning (`rm()`, parent environment re-assignment).
- [ ] Mengimplementasikan *defensive metaprogramming* untuk mengisolasi evaluasi ekspresi pengguna dari bahaya code injection tanpa string manipulation.
- [ ] Menulis wrapper fungsi tingkat tinggi yang memanfaatkan `{{ }}` (*curly-curly*) untuk meneruskan kolom data masking tanpa merusak backtrace debugging.
- [ ] Mendesain API internal yang mendukung dualitas SE (Standard Evaluation untuk programatik/API backend) dan NSE (Non-Standard Evaluation untuk pengguna interaktif).