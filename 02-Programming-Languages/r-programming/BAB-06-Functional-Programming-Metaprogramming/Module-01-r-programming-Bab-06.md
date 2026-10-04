# Bab 06: Object-Oriented Programming & Extensibility
## Module 01: Sistem Pemrograman Berorientasi Objek S3 dan S4 (Generic Functions, Method Dispatch, dan Formal Class Validation)

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda memiliki kompetensi terukur untuk:
1. Mendiagnosis dan mengonstruksi arsitektur *Functional OOP* menggunakan sistem **S3** dan **S4** pada R runtime engine.
2. Mengimplementasikan mekanisme *Generic Function* dan *Method Dispatch* tingkat rendah menggunakan `UseMethod()` (S3) dan `standardGeneric()` (S4).
3. Membangun sistem validasi tipe data ketat (*strict structural contract*) melalui `setClass()`, *slots*, dan *validity functions* pada S4 untuk pipeline analitik kritis.
4. Mencegah degradasi performa komputasi dan memori yang diakibatkan oleh *copy-on-modify semantics* saat melakukan *slot manipulation* atau *inheritance dispatching*.
5. Menuliskan unit testing dan sistem inspeksi method dispatch menggunakan `sloop` dan perkakas diagnostik internal R.

---

### 2. Prerequisite
Untuk menyerap materi ini secara maksimal, Anda wajib memahami:
* Arsitektur Memori R: Representasi internal objek (SEXP - *S-expression pointers*), alokasi memori heap, dan semantik *Copy-on-Modify*.
* Struktur Data Dasar R: Vectors, Named Lists, Environments, serta manipulasi Metadata melalui R `attributes()`.
* Lingkungan Eksekusi R (Environments): Konsep Call Stack, Enclosing Environment, Execution Environment, dan Parent Frame.
* Functional Programming: First-class functions, closures, dan higher-order functions.

---

### 3. Concept
R menerapkan paradigma **Functional Object-Oriented Programming**, yang secara mendasar berbeda dari paradigma *Encapsulated OOP* (seperti C++, Java, atau Python). Pada Encapsulated OOP, method terikat langsung di dalam definisi class atau objek (`object.method()`). Pada Functional OOP, method dimiliki oleh **Generic Function**, bukan class (`generic(object)`). Keputusan implementasi fungsi mana yang dieksekusi ditentukan oleh argumen objek yang dikirimkan melalui proses yang disebut **Method Dispatch**.

```
Encapsulated OOP:  Object  ---> [ Methods inside Object ]
Functional OOP:    Generic Function ---> [ Inspects Class of Argument ] ---> Dispatches Method
```

#### Arsitektur Internal S3 (*Informal Dynamic System*)
S3 adalah sistem OOP pertama R yang berbasis konvensi, fleksibel, dan ringan:
* **Representasi Kelas:** Objek S3 hanyalah tipe data dasar R (paling sering berupa `list` atau `atomic vector`) yang diberi atribut metadata `"class"`.
* **Method Dispatch:** Mengandalkan fungsi primitif C `UseMethod()`. Konvensi penamaan fungsi adalah `generic.class()`. Ketika `generic(x)` dieksekusi, R membaca string vektor pada `class(x)` dari kiri ke kanan, lalu mencari fungsi bernama `generic.<nama_class>()` di *search path* atau *namespace registry*.
* **Keamanan Tipe:** Nol (*None*). Setiap pengguna dapat mengubah atribut class secara manual (`class(x) <- "arbitrary"`) tanpa validasi struktur internal.

#### Arsitektur Internal S4 (*Formal Static System*)
S4 memperkenalkan rekayasa perangkat lunak yang formal, deterministik, dan berbasis kontrak (*type-safe*):
* **Representasi Kelas:** Didefinisikan secara eksplisit menggunakan `setClass()`. Objek S4 memiliki tipe internal `S4SXP`. Data disimpan dalam variabel bernama khusus yang disebut **Slots**, diakses secara internal menggunakan operator `@`.
* **Method Dispatch:** Menggunakan fungsi `setGeneric()` dan `setMethod()`. S4 mendukung **Multiple Dispatch**, di mana pemilihan method dapat ditentukan berdasarkan tanda tangan (*signature*) tipe kombinasi lebih dari satu argumen.
* **Keamanan Tipe:** Ketat (*Strict*). S4 memvalidasi tipe data setiap slot secara otomatis pada saat instansiasi (`new()`) dan dapat dihubungkan dengan fungsi validasi khusus (`validity function`).

---

### 4. Why
Mengapa arsitektur S3/S4 mutlak diperlukan dalam rekayasa sistem data skala besar?

1. **Integritas Kontrak Antarmuka (API Consistency):** Tanpa generic functions, ekosistem analitik akan terfragmentasi menjadi nama fungsi yang sporadis (contoh: `predict_linear()`, `predict_random_forest()`, `predict_gbm()`). Generic function `predict()` menyediakan satu kontrak komputasi untuk ratusan algoritma backend.
2. **Eliminasi Anti-Pattern Conditional Branching:** Pengembang pemula sering menggunakan blok `if-else` atau `switch` panjang untuk memeriksa tipe objek input. Pola ini memicu *cyclomatic complexity* ekstrem dan melanggar *Open/Closed Principle*. Generic dispatch memecah logika ini secara modular tanpa menyentuh kode inti generic.
3. **Mencegah Pipeline Terhenti di Tahap Produksi:** Pada sistem enterprise (seperti perbankan atau bioinformatika), kegagalan format data di pertengahan eksekusi bernilai sangat mahal. Sistem formal S4 menjamin kegagalan (*fail-fast*) di lapisan *ingestion* sebelum kalkulasi memakan alokasi cluster komputasi.

---

### 5. What
Komponen inti arsitektur OOP R meliputi:

| Komponen | Sistem S3 | Sistem S4 |
| :--- | :--- | :--- |
| **Class Declaration** | Implisit via `attr(x, "class") <- "name"` | Eksplisit via `setClass("name", slots, prototype)` |
| **Data Storage** | Base types (umumnya named `list`) | Typed slots (`@`) di dalam representasi `S4SXP` |
| **Generic Mechanism** | `UseMethod("generic_name")` | `standardGeneric("generic_name")` via `setGeneric()` |
| **Dispatch Basis** | Single dispatch (hanya argumen pertama) | Multiple dispatch (bisa berdasarkan kombinasi argumen) |
| **Method Registry** | Namespace table / Search path (`generic.class`) | S4 Internal Method Tables (`.MTable`) |
| **Type Validation** | Manual via developer-written assertion code | Deklaratif & otomatis via `validity = function(object)` |
| **Performance Overhead** | Sangat rendah (~sub-mikrodetik) | Sedang (validasi slot & multiple-dispatch resolution) |

---

### 6. How
Alur operasional internal R dalam memproses pemanggilan generic function:

#### S3 Dispatch Workflow
1. Generic function dieksekusi dengan argumen `x`.
2. Generic memanggil C-level function `UseMethod("generic", x)`.
3. R mengambil vektor karakter dari `class(x)`. Misalnya: `c("order_service", "base_service")`.
4. R mencari method berurutan:
   * Cari `generic.order_service()`
   * Jika tidak ada, cari `generic.base_service()`
   * Jika tidak ada, cari fallback method: `generic.default()`
5. Jika method ditemukan, frame eksekusi dialihkan ke method tersebut. Jika tidak ditemukan, eksekusi dihentikan dengan error `no applicable method`.

#### S4 Dispatch Workflow
1. Generic function memanggil `standardGeneric("generic")`.
2. S4 dispatcher memeriksa tipe kelas runtime dari semua argumen yang terdaftar di dalam generic signature.
3. Dispatcher mencocokkan signature dengan matriks method registry S4.
4. Jika tidak ada kecocokan eksak, dispatcher mengevaluasi hierarki pewarisan (*inheritance graph*) untuk menemukan method dengan *distance metric* paling terdekat.
5. Method yang paling spesifik dieksekusi. Jika slot bermutasi, integritas divalidasi ulang jika method menyertakan pengecekan tipe.

---

### 7. Analogy
Bayangkan operasional sebuah **Instalasi Gawat Darurat (IGD) Rumah Sakit**:

* **S3 OOP adalah Prosedur Medis Lapangan (Triage Darurat):**
  Setiap pasien diberi gelang bertuliskan label: `"Prioritas-Merah"`. Dokter (Generic Function) melihat label tersebut lalu langsung menerapkan tindakan darurat spesifik (Method). Namun, tidak ada verifikasi rekam medis formal; label tersebut hanya stiker yang ditempel di tangan. Cepat, fleksibel, efisiensi tinggi, tetapi rentan kesalahan identifikasi jika stiker diubah sembarangan.

* **S4 OOP adalah Registrasi Bedah Sentral (Prosedur Terstandarisasi):**
  Pasien harus memiliki rekam medis digital resmi dengan *field* (*Slots*) yang terkunci: Golongan Darah (string), Tekanan Darah (integer), Riwayat Alergi (vector). Sebelum pasien masuk ke meja operasi, sistem secara otomatis menjalankan verifikasi dokumen (*Validity Check*). Jika ada satu *slot* yang tidak sesuai tipe atau bernilai mustahil, akses operasi ditolak total secara otomatis. Aman, deterministik, tidak bisa dipalsukan, tetapi membutuhkan overhead verifikasi administratif.

---

### 8. Diagram

```
                 ALUR ARSITEKTUR METHOD DISPATCH PADA R

     PEMANGGILAN FUNGSI KLIEN: compute_risk(payload)
                           |
                           v
              +-------------------------+
              | Is S3 or S4 Generic?    |
              +-------------------------+
                    /             \
            [S3]   /               \   [S4]
                  v                 v
     +-----------------------+   +------------------------------------+
     | Eksekusi UseMethod()  |   | Eksekusi standardGeneric()         |
     +-----------------------+   +------------------------------------+
                 |                                  |
                 v                                  v
     +-----------------------+   +------------------------------------+
     | Baca class(payload)   |   | Evaluasi Signature Argumen         |
     | [Vector of Strings]   |   | (Bisa > 1 argumen / Multiple)      |
     +-----------------------+   +------------------------------------+
                 |                                  |
                 v                                  v
     +-----------------------+   +------------------------------------+
     | Cari di Namespace/Env |   | Cari Best Match di S4 Method Table |
     | Pattern: func.class   |   | via Inheritance Graph Distance     |
     +-----------------------+   +------------------------------------+
           /           \                           |
     [Found]       [Not Found]                     |
        |               |                          |
        |               v                          |
        |       +---------------+                  v
        |       | func.default? |        +-------------------+
        |       +---------------+        | Eksekusi Method   |
        |         /           \          +-------------------+
     [Found] [Not Found]       \                   |
        |         |             v                  v
        |         v       [Error: No Method]  [Return Result]
        |   [Error: No Method]
        v
  +-------------------------+
  | Eksekusi Method S3      |
  +-------------------------+
        |
        v
  [Return Result]
```

---

### 9. Simple Example

Implementasi minimal untuk memahami mekanika fundamental S3 dan S4.

#### S3 Implementation
```r
# 1. Definisikan Generic
calculate_tax <- function(entity, ...) {
  UseMethod("calculate_tax")
}

# 2. Definisikan Fallback Method
calculate_tax.default <- function(entity, ...) {
  stop("Tipe objek tidak dikenali untuk kalkulasi pajak.")
}

# 3. Definisikan Specific Methods
calculate_tax.individual <- function(entity, ...) {
  return(entity$income * 0.15)
}

calculate_tax.corporate <- function(entity, ...) {
  return(entity$income * 0.22)
}

# 4. Instansiasi Objek S3 (Menggunakan base list + atribut class)
obj_person <- list(name = "Budi Hartono", income = 100000000)
class(obj_person) <- "individual"

obj_company <- list(name = "PT Teknologi Nusantara", income = 5000000000)
class(obj_company) <- "corporate"

# 5. Eksekusi Dispatch
calculate_tax(obj_person)   # Hasil: 15000000
calculate_tax(obj_company)  # Hasil: 1100000000
```

#### S4 Implementation
```r
# 1. Definisikan Formal Class dengan Slots
setClass(
  Class = "SecurityToken",
  slots = c(
    symbol = "character",
    balance = "numeric",
    is_frozen = "logical"
  ),
  prototype = list(
    symbol = "UNKNOWN",
    balance = 0,
    is_frozen = FALSE
  )
)

# 2. Definisikan S4 Generic
setGeneric("transfer", function(token, amount, ...) {
  standardGeneric("transfer")
})

# 3. Definisikan S4 Method dengan Type-Signature
setMethod(
  f = "transfer",
  signature = c(token = "SecurityToken", amount = "numeric"),
  definition = function(token, amount, ...) {
    if (token@is_frozen) {
      stop("Transaksi ditolak: Token dalam kondisi beku.")
    }
    if (token@balance < amount) {
      stop("Transaksi ditolak: Saldo tidak mencukupi.")
    }
    token@balance <- token@balance - amount
    return(token)
  }
)

# 4. Instansiasi dan Eksekusi
my_wallet <- new("SecurityToken", symbol = "IDR_GOV", balance = 500000, is_frozen = FALSE)
my_wallet <- transfer(my_wallet, 150000)
my_wallet@balance # Hasil: 350000
```

---

### 10. Practical Example
Skenario: Sistem Pemrosesan dan Evaluasi Portofolio Risiko Finansial Skala Industri.

```r
suppressPackageStartupMessages({
  library(methods)
})

# ==============================================================================
# S3 SECTION: FORMATTING & LOW-OVERHEAD EVENT LOGGING ENGINE
# ==============================================================================

#' S3 Generic untuk Logging Transaksi
log_execution <- function(event, ...) {
  UseMethod("log_execution")
}

#' Constructor S3: Immutable Event
new_audit_event <- function(event_id, severity, message) {
  stopifnot(is.character(event_id), is.character(severity), is.character(message))
  
  structure(
    list(
      event_id  = event_id,
      severity  = severity,
      message   = message,
      timestamp = Sys.time()
    ),
    class = "audit_event"
  )
}

#' S3 Method Print Override
print.audit_event <- function(x, ...) {
  cat(sprintf("[%s] %s | EVENT_ID: %s -> %s\n", 
              format(x$timestamp, "%Y-%m-%d %H:%M:%S"),
              toupper(x$severity), 
              x$event_id, 
              x$message))
  invisible(x)
}

#' S3 Method Default Dispatch
log_execution.audit_event <- function(event, ...) {
  print(event)
}

# ==============================================================================
# S4 SECTION: TYPE-SAFE RISK ASSESSMENT ENGINE
# ==============================================================================

#' Class Definition: PortfolioInstrument (Abstract Base Model)
setClass(
  Class = "PortfolioInstrument",
  slots = c(
    ticker      = "character",
    exposure    = "numeric",
    volatility  = "numeric"
  ),
  prototype = list(
    ticker      = "DEFAULT",
    exposure    = 0.0,
    volatility  = 0.0
  )
)

#' Class Validity Function
setValidity("PortfolioInstrument", function(object) {
  errors <- character()
  if (length(object@ticker) != 1 || nchar(object@ticker) == 0) {
    errors <- c(errors, "Ticker wajib berupa 1 string non-kosong.")
  }
  if (object@exposure < 0) {
    errors <- c(errors, "Exposure tidak boleh bernilai negatif.")
  }
  if (object@volatility < 0 || object@volatility > 1.0) {
    errors <- c(errors, "Volatility wajib berada pada domain [0.0, 1.0].")
  }
  if (length(errors) == 0) TRUE else errors
})

#' Subclass: DerivativesInstrument (Inheritance)
setClass(
  Class = "DerivativesInstrument",
  contains = "PortfolioInstrument",
  slots = c(
    leverage_multiplier = "numeric"
  ),
  prototype = list(
    leverage_multiplier = 1.0
  ),
  validity = function(object) {
    if (object@leverage_multiplier < 1.0) {
      return("Leverage multiplier pada derivatif minimal 1.0.")
    }
    TRUE
  }
)

#' Generic Function S4: Multiple Signature Dispatch
setGeneric(
  name = "calculate_var",
  def = function(instrument, confidence_level, ...) {
    standardGeneric("calculate_var")
  }
)

#' Method S4: Base Instrument Value-at-Risk (Parametric VaR)
setMethod(
  f = "calculate_var",
  signature = signature(instrument = "PortfolioInstrument", confidence_level = "numeric"),
  definition = function(instrument, confidence_level, ...) {
    if (confidence_level <= 0 || confidence_level >= 1) {
      stop("Confidence level harus di antara 0 dan 1.")
    }
    # Asumsi distribusi normal standar untuk z-score sederhana
    z_score <- qnorm(confidence_level)
    var_estimate <- instrument@exposure * instrument@volatility * z_score
    return(var_estimate)
  }
)

#' Method S4: Derivatives Instrument (Polymorphic Method Resolution)
setMethod(
  f = "calculate_var",
  signature = signature(instrument = "DerivativesInstrument", confidence_level = "numeric"),
  definition = function(instrument, confidence_level, ...) {
    base_var <- callNextMethod()
    adjusted_var <- base_var * instrument@leverage_multiplier
    return(adjusted_var)
  }
)

# ==============================================================================
# INTEGRATED EXECUTION PIPELINE
# ==============================================================================

# Inisialisasi Audit Logging (S3)
evt1 <- new_audit_event("EVT-8801", "info", "Memulai inisialisasi Portofolio Risk Engine")
log_execution(evt1)

# Inisialisasi Portofolio Fisik & Derivatif (S4 Strict)
equity_asset <- new("PortfolioInstrument", 
                    ticker = "BBCA.JK", 
                    exposure = 1000000000, 
                    volatility = 0.15)

derivative_asset <- new("DerivativesInstrument", 
                        ticker = "IDX30-FUT", 
                        exposure = 500000000, 
                        volatility = 0.25, 
                        leverage_multiplier = 3.5)

# Kalkulasi Risiko menggunakan S4 Dispatch
var_equity <- calculate_var(equity_asset, 0.99)
var_derivative <- calculate_var(derivative_asset, 0.99)

evt2 <- new_audit_event("EVT-8802", "warning", 
                        sprintf("VaR BBCA: Rp %s | VaR IDX30-FUT: Rp %s", 
                                format(round(var_equity, 2), big.mark = "."), 
                                format(round(var_derivative, 2), big.mark = ".")))
log_execution(evt2)
```

---

### 11. Real World Example
**Kasus: Bioconductor Core Infrastructure (`GenomicRanges` & `SummarizedExperiment`)**

Dalam platform pemrosesan genomika **Bioconductor**, data mentah terdiri dari miliaran fragmen DNA yang memerlukan pencocokan koordinat kromosom.
* **Tantangan:** Jika representasi data genomik menggunakan format tabular data frame standar atau S3 list murni, kesalahan ketik nama kolom atau inkonsistensi tipe data *start-end positions* (misal float alih-alih integer) akan menyebabkan degradasi analisa biologis fatal atau kegagalan komputasi cluster 40 jam tanpa pesan error yang dapat dilacak.
* **Solusi Arsitektur S4:** Bioconductor membangun seluruh infrastruktur dasarnya di atas S4. Kelas `GRanges` memiliki slot ketat: `seqnames` (faktor kromosom), `ranges` (struktur interval IRanges beranggotakan *start* dan *end* integer positif), serta `strand` (faktor spesifik `+`, `-`, atau `*`).
* **Dampak Produksi:** Puluhan ribu package bioinformatika dapat saling berkomunikasi secara deterministik tanpa risiko parsing data yang rusak. Metode umum seperti `findOverlaps()` menggunakan sistem *Multiple Dispatch S4* yang memilih algoritma binary-search optimal secara dinamis tergantung apakah target data berupa memori internal R atau pointer memori C++ (`HDF5Array`).

---

### 12. Trade-offs

```
               KOMPARASI KOMPLEKSITAS VS JAMINAN TIPE

  Tinggi ^                                   [S4 Framework]
         |                                   - Strict Contract
         |                                   - Formal Validation
         |                                   - Multiple Dispatch
         |                                   - Higher Call Overhead
KONTRAK  |
 & TYPE  |                  [S3 System]
 SAFETY  |                  - Informal Contract
         |                  - High Performance
         |                  - Single Dispatch
  Rendah |                  - Manual Validation
         +---------------------------------------------------->
         Rendah                                         Tinggi
                       DEVELOPMENT COMPLEXITY
```

| Dimensi Arsitektural | S3 System | S4 System | S3 + VCTRS (Alternatif Modern) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Dispatch** | Sangat Tinggi (~sub-mikrodetik) | Rendah ke Menengah (overhead signature scanning) | Sangat Tinggi |
| **Kekuatan Kontrak** | Lemah (hanya berbasis konvensi atribut) | Sangat Kuat (enforced runtime validity) | Menengah-Kuat (menggunakan prototype C) |
| **Mekanisme Dispatch** | Single dispatch (argumen pertama saja) | Multiple dispatch (kombinasi banyak parameter) | Single dispatch (berbasis ptype) |
| **Debugging Complexity** | Mudah, fungsi biasa dapat ditelusuri langsung | Kompleks, method terkubur di internal registry | Mudah hingga Menengah |
| **Development Cost** | Rendah, waktu pembuatan prototipe cepat | Tinggi, butuh boilerplate definisi formal | Menengah |
| **Memory Footprint** | Minimal (menggunakan memory layout native R) | Ada metadata overhead untuk slot registry | Efisien |

---

### 13. When To Use
Gunakan arsitektur OOP berikut sesuai kondisi teknis spesifik:

* **Pilih S3 Jika:**
  1. Anda sedang membangun library fungsi manipulasi data berkecepatan tinggi di mana overhead pemanggilan fungsi harus mendekati nol.
  2. Anda memperluas fungsionalitas paket fundamental R (misalnya: membuat visualisasi baru dengan menyediakan method `plot()`, atau method `print()`, `summary()`).
  3. Struktur data input tidak rentan terhadap anomali mutasi runtime atau telah divalidasi ketat di layer sebelumnya.

* **Pilih S4 Jika:**
  1. Sistem mengelola data saintifik, aktuaria, atau transaksi perbankan dengan integritas struktural mutlak (*zero-tolerance for malformed data*).
  2. Logika bisnis Anda secara fundamental memerlukan **Multiple Dispatch** (misalnya, method `merge_datasets(source, target)` perilakunya berbeda ketika kombinasi tipe adalah `(SQLDatabase, LocalDisk)` vs `(ParquetStream, S3Bucket)`).
  3. Membangun platform dasar atau framework enterprise yang akan diturunkan (*subclassed*) oleh banyak tim developer independen.

---

### 14. When NOT To Use
* **Hindari S3 Jika:** Kode Anda adalah library komersial tertutup yang menerima objek dari pengguna eksternal tanpa validasi. Pengguna dapat merusak sistem hanya dengan mengeksekusi `class(x) <- "broken_type"`.
* **Hindari S4 Jika:** Komputasi Anda berada dalam loop frekuensi ultra-tinggi (misal: 10 juta iterasi per detik). Overhead resolusi generic method S4 dan validasi slot akan mendegradasi performa pemrosesan hingga beberapa magnitudo dibanding kode vektorisasi atau C-bindings.
* **Hindari S3/S4 untuk Stateful In-Memory Mutation:** R secara default menganut *pass-by-value* (*copy-on-modify*). Jika Anda memerlukan representasi stateful entity (seperti koneksi database persisten, UI reactive state, atau WebSocket listener), gunakan sistem **R6** (*Encapsulated OOP dengan reference semantics*), bukan S3 atau S4.

---

### 15. Common Mistakes
Berikut adalah anti-pattern yang sering terjadi di level produksi:

#### 1. Mutasi Objek S4 Menggunakan Akses Slot Langsung (`@<-`)
```r
# SALAH (Anti-Pattern): Memodifikasi slot langsung di luar constructor / method
my_instrument@exposure <- -500000  # Validitas S4 TIDAK dipicu, data korup lolos!

# BENAR: Gunakan validasi eksplisit jika terpaksa memodifikasi secara manual
my_instrument@exposure <- 500000
validObject(my_instrument) # Memicu pemeriksaan kesesuaian nilai slot
```

#### 2. Deklarasi S3 Method Tanpa Mematuhi Signature Generic Asli
```r
# SALAH: Menambahkan argumen wajib yang tidak ada pada generic signature
print.my_class <- function(x, mandatory_arg) { ... }
# Hasil: R CMD check FAIL, error dispatch saat dipanggil oleh print(obj)

# BENAR: Selalu sertakan dots (...) dan samakan signature formal generic
print.my_class <- function(x, ...) { ... }
```

#### 3. Menggunakan `is.vector()` untuk Memeriksa Tipe Objek S3
```r
x <- structure(c(1, 2, 3), class = "custom_numeric")
# SALAH: is.vector(x) akan mengembalikan FALSE karena objek memiliki atribut non-names!
is.vector(x) # [1] FALSE

# BENAR: Periksa tipe dasarnya atau gunakan inherits()
is.numeric(x) && inherits(x, "custom_numeric") # [1] TRUE
```

---

### 16. Best Practices (Production Checklist)

1. [ ] **Selalu Gunakan Constructor, Validator, dan Helper untuk S3:**
   * *Constructor:* `new_classname()` (fokus performa, menggunakan `structure()`).
   * *Validator:* `validate_classname()` (memeriksa integritas isi list/vektor).
   * *Helper:* `classname()` (antarmuka aman yang digunakan pengguna eksternal).
2. [ ] **Terapkan `validObject()` pada Akhir Alur Inisialisasi S4:** Jangan berasumsi konstruktor `new()` cukup jika Anda mengubah slot secara programatik di dalam internal method.
3. [ ] **Export Generic dan Method Secara Benar di `NAMESPACE`:**
   * Untuk S3: `S3method(generic_name, class_name)`.
   * Untuk S4: `exportMethods(generic_name)` dan `exportClasses(class_name)`.
4. [ ] **Gunakan `callNextMethod()` untuk Inheritance S4:** Hindari menulis ulang logika base class saat membuat implementasi method pada subclass.
5. [ ] **Jangan Menggunakan S3 Method Dispatch dengan Titik Tambahan di Nama Generic:**
   * Hindari: `process.user.data.registered_user()` (Dispatcher akan bingung mengidentifikasi mana generic dan mana class).
   * Gunakan konvensi: `snake_case` untuk generic (`process_user_data`), dan titik HANYA untuk pemisah method dispatch (`process_user_data.registered_user`).

---

### 17. Troubleshooting

#### 1. Masalah: Error `error in evaluating the argument 'x' in selecting a method for function '...'`
* **Penyebab:** Terjadi konflik namespace S4 di mana signature dari argumen yang dikirim bertabrakan dengan method inheritance hierarchy yang ambigu.
* **Solusi Diagnostik:**
  ```r
  # Identifikasi urutan method dispatch yang dipilih R
  selectMethod("calculate_var", signature = c("DerivativesInstrument", "numeric"))
  ```

#### 2. Masalah: S3 Method Tidak Terpanggil Meskipun Fungsi Sudah Didefinisikan
* **Penyebab:** Method S3 tidak terdaftar di namespace package runtime (sering terjadi jika package dimuat tanpa `devtools::load_all()` atau file `NAMESPACE` belum di-regenerate menggunakan Roxygen).
* **Solusi Diagnostik:**
  ```r
  # Pasang paket diagnostik OOP R
  # install.packages("sloop")
  sloop::s3_dispatch(print(obj_person))
  
  # Hasil interpretasi sloop:
  # => print.individual  (terpanggil)
  #  * print.default     (tersedia tapi di-bypass)
  ```

#### 3. Masalah: Degradasi Memori Masif saat Memperbarui Slot S4 di Dalam Looping
* **Penyebab:** Eksekusi `@<-` memicu *deep memory copy* dari representasi internal `S4SXP` jika referensi counter objek > 1.
* **Solusi:** Re-arsitektrur algoritma untuk mengumpulkan hasil kalkulasi ke dalam plain list terlebih dahulu, lalu instansiasi objek S4 secara batch di akhir pemrosesan.

---

### 18. Exercise
Implementasikan skema S3 Parser Logging berikut:

**Spesifikasi Kebutuhan:**
1. Bangun constructor function S3 bernama `new_api_response(status_code, body, headers)` yang memverifikasi bahwa `status_code` adalah integer, `body` adalah string/character, dan `headers` adalah named list.
2. Buat fungsi helper `api_response(...)` yang mengubah status code numerik apa pun menjadi integer murni secara aman dan melakukan sanity check.
3. Definisikan Generic S3 baru bernama `extract_payload(x, ...)`.
4. Definisikan method S3 `extract_payload.api_response(x, ...)`:
   * Jika `status_code == 200`, parsing string `body` seolah-olah JSON (cukup ekstrak string character).
   * Jika `status_code >= 400`, hentikan proses (*throw error*) dengan pesan deskriptif sesuai isi `body`.
5. Implementasikan method `print.api_response(x, ...)` yang memformat tampilan objek secara profesional (menyembunyikan headers teknis dan hanya mencetak status dan ringkasan ukuran body).

---

### 19. Challenge
Rancang arsitektur S4 tingkat enterprise untuk **Engine Eksekusi Rule Engine Transaksi Finansial**:

**Syarat & Batasan Kompleksitas:**
1. Buat Abstract Class S4 `RuleDefinition`:
   * Slot: `rule_id` (character), `threshold` (numeric), `action` (character).
   * Slot validity: `action` hanya boleh bernilai salah satu dari: `"ALERT"`, `"BLOCK"`, `"FLAG"`.
2. Buat 2 Subclasses yang mewarisi `RuleDefinition`:
   * `VelocityRule`: Menambahkan slot `time_window_seconds` (integer positif).
   * `AmountRule`: Menambahkan slot `currency` (character dengan panjang tepat 3 huruf kapital, misal `"IDR"`, `"USD"`).
3. Buat Class S4 Transaksi `TransactionPayload`:
   * Slot: `txn_id` (character), `amount` (numeric), `timestamp` (POSIXct), `currency` (character).
4. Buat Multiple-Dispatch Generic `evaluate_rule(rule, transaction)`:
   * Implementasikan method khusus ketika `signature = c("AmountRule", "TransactionPayload")`.
   * Logika: Jika mata uang cocok dan `amount > threshold`, cetak peringatan sesuai isi slot `action` dan kembalikan nilai boolean `FALSE` (transaksi gagal evaluasi). Jika lolos, kembalikan `TRUE`.
   * Method harus memvalidasi kesesuaian mata uang secara ketat (throw error jika mata uang berbeda).
5. Kode harus lolos dari pemanggilan `validObject()` di setiap langkah instansiasi.

---

### 20. Summary

```
================================================================================
                    R OOP SYSTEM ARCHITECTURE MATRIX
================================================================================
FITUR                 S3 SYSTEM                       S4 SYSTEM
--------------------------------------------------------------------------------
Filosofi              Ad-hoc, informal, lightweight   Formal, contract-driven
Struktur Data         Base Object + class attribute   S4SXP Object + typed slots
Method Binding        Generic -> UseMethod()          Generic -> standardGeneric()
Dispatch Engine       Dynamic pattern (func.class)    Type-signature lookup table
Dispatch Complexity   Single (first argument)         Multiple (arbitrary args)
Type Safety           Manual assertions               Declarative validity methods
Performa Pemanggilan  Sub-microsecond (< 1 µs)        Low microsecond (~5-10 µs)
Use Case Ideal        Analitik interaktif & packages  Sistem analitik inti enterprise,
                      manipulasi data umum (tidyverse) bioinformatika, aktuaria
================================================================================
```

Penguasaan sistem S3 dan S4 meletakkan landasan rekayasa perangkat lunak yang kokoh di ekosistem R. Memilih sistem yang tepat bergantung pada titik optimum antara **kebutuhan kecepatan komputasi murni (S3)** dan **kebutuhan jaminan kebenaran struktur data (S4)** pada domain bisnis yang Anda kembangkan.