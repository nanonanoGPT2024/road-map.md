# BAB 01: Fondasi & Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (R Programming)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Engineer/Architect diharapkan mampu:
- Mengurai secara komprehensif arsitektur internal runtime R (*GNU R Engine*), representasi memori berbasis `SEXP` (*S-Expression*), *Cons-cell*, dan *Pointer Protection Stack*.
- Menguasai semantik *Copy-on-Modify*, mekanisme *Reference Counting* modern (`REFCNT`), serta arsitektur zero-copy berbasis **ALTREP** (*Alternative Representations*).
- Mengidentifikasi karakteristik dan mengontrol *Generational Tracing Garbage Collector* (Gen 0, 1, 2) untuk mengeliminasi latensi *GC pause* pada sistem produksi.
- Mengembangkan subsistem komputasi berperforma tinggi mengintegrasikan R dengan C++ (*Rcpp*) tanpa alokasi memori berlebih (*zero-allocation wrappers*).
- Menerapkan arsitektur konkurensi, paralelisasi berbasis memori terdistribusi/bersama (*shared-memory inter-process communication* via memory-mapped files), serta pola desain berorientasi objek yang tepat (*S3 vs S4 vs R6*).
- Mendesain pipeline pemrosesan data berskala enterprise (*terabyte-scale batch/streaming*) menggunakan R dengan SLA latensi dan reliabilitas ketat.

---

### 2. Prerequisite

Sebelum menempuh modul lanjutan ini, praktisi wajib memiliki prasyarat:
- Pemahaman mendalam tentang eksekusi program tingkat rendah, tata letak memori OS (*Stack vs Heap*, *Virtual Memory*, *Paging*, *L1/L2/L3 Cache Locality*).
- Kemahiran bahasa pemrograman C/C++ (minimal standar C++11, manajemen *raw pointer*, *smart pointers*, dan ABI interoperability).
- Telah menyelesaikan **Modul 01: Dasar Sintaksis, Ekosistem, dan Runtime Primitives R**.
- Terbiasa menggunakan *profiler* sistem seperti `valgrind`, `gdb`, dan tooling profiler internal R (`profvis`, `tracemem`, `lobstr`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Runtime R & Struktur Data SEXP
Runtime R (GNU R) ditulis secara fundamental menggunakan ANSI C. Semua entitas di dalam R—mulai dari integer tunggal, fungsi closure, *environment*, hingga *abstract syntax tree* (AST)—disimpan sebagai pointer ke struktur C bertipe `SEXPREC` (*S-Expression Record*), yang dialias sebagai `SEXP`.

```c
/* Representasi Sederhana Definisi Tipe SEXPREC pada R Internals (src/include/Rinternals.h) */
typedef struct SEXPREC {
    struct sxpinfo_struct sxpinfo; /* Metadatata 32-bit: tipe objek, mark GC, status REFCNT */
    struct SEXPREC *attrib;        /* Linked-list atribut (names, class, dim, dll) */
    struct SEXPREC *gengc_next_node; /* Pointer untuk linked list generational GC */
    struct SEXPREC *gengc_prev_node;
    union {
        struct primsxp_struct primsxp;
        struct symsxp_struct symsxp;
        struct listsxp_struct listsxp;   /* Pairlist / Cons-cell */
        struct envsxp_struct envsxp;     /* Frame & enclosing environment */
        struct closxp_struct closxp;     /* Formal args, body, environment closure */
        struct promargsxp_struct promargsxp; /* Lazy evaluation promises */
    } u;
} SEXPREC;

typedef SEXPREC* SEXP;
```

Ukuran *header* `SEXPREC` standar pada arsitektur 64-bit adalah 40 byte. Header ini membungkus struktur data riil:
1. **Node Heap (Cons-cell Heap)**: Mengalokasikan objek berukuran tetap (tipe `LISTSXP`, `ENVSXP`, `CLOSXP`, simbol, dan ekspresi bahasa).
2. **Vector Heap**: Mengalokasikan blok memori kontigu untuk tipe data vektor numerik, integer, raw, dan karakter (`REALSXP`, `INTSXP`, `RAWSXP`, `STRSXP`).

#### 3.2. Evolusi Mekanisme Copy-on-Modify: NAMED vs REFCNT
Secara historis (R < 3.1.0), R menggunakan sistem `NAMED` (skala 0, 1, 2) untuk melacak kepemilikan referensi. Nilai `NAMED=2` memicu duplikasi memori secara agresif bahkan saat objek tidak lagi dibagi (*shared*).

Mulai R 4.0.0+, GNU R mengadopsi sistem pelacakan referensi murni (**Reference Counting** atau `REFCNT`):
- Saat objek baru dialokasikan via C API atau parser: `REFCNT = 0` (unbound) atau `REFCNT = 1` (terikat pada satu simbol).
- Jika simbol baru menunjuk pada SEXP yang sama: `REFCNT` di-inkremen.
- Modifikasi in-place (*mutation in-place*) hanya terjadi jika dan hanya jika `REFCNT <= 1`.
- Jika `REFCNT > 1` dan modifikasi dipicu, R menduplikasi vektor kontigu tersebut (*deep copy* data payload, namun *shallow copy* atribut jika tidak dimodifikasi), lalu menurunkan nilai `REFCNT` pada objek asal.

```
       Simbol: x                          Simbol: y
           │                                  │
           └───────────────┐  ┌───────────────┘
                           ▼  ▼
                  ┌────────────────────┐
                  │ SEXP (INTSXP)      │
                  │ REFCNT = 2         │
                  │ Data: [1, 2, 3, 4] │
                  └────────────────────┘
                           │
       y[1] <- 99L (Copy-on-Modify Terpicu Karena REFCNT > 1)
                           │
           ┌───────────────┴──────────────────┐
           ▼                                  ▼
┌────────────────────┐             ┌────────────────────┐
│ SEXP (INTSXP) [x]  │             │ SEXP (INTSXP) [y]  │
│ REFCNT = 1         │             │ REFCNT = 1         │
│ Data: [1, 2, 3, 4] │             │ Data: [99, 2, 3, 4]│
└────────────────────┘             └────────────────────┘
```

#### 3.3. Pointer Protection Stack
Karena Garbage Collector (GC) R bersifat *precise* dan *tracing*, setiap kali alokasi baru terjadi pada heap R via C API (`allocVector`, `cons`, dll.), GC berpotensi terpicu. Jika objek `SEXP` baru belum ditautkan ke *Root Set* (lingkungan aktif R) dan terjadi GC sweep, pointer tersebut akan dianggap sebagai *dead memory* dan dibebaskan seketika, menyebabkan *dangling pointer* atau *Segmentation Fault*.

Untuk mengamankannya, runtime menyediakan array pointer internal bernama **Protection Stack**:
- `PROTECT(SEXP s)`: Memasukkan pointer ke stack proteksi R (menaikkan indeks stack proteksi).
- `UNPROTECT(int n)`: Mengeluarkan `n` elemen teratas dari stack proteksi.
- Batas default ukuran stack proteksi adalah puluhan ribu pointer (`R_PPStackSize`). *Stack overflow* pada layer ini akan melempar fatal error: `protect(): protection stack overflow`.

#### 3.4. ALTREP (Alternative Representations)
Diperkenalkan pada R 3.5.0, ALTREP adalah abstraksi tingkat rendah yang memungkinkan SEXP menyembunyikan implementasi data kustom di balik tipe data vektor standar R. 

Alih-alih mengalokasikan array data kontigu pada Vector Heap, objek ALTREP mengimplementasikan *virtual method table* (vtable) C untuk:
- Mengakses elemen secara komputasi malas (*lazy evaluation*), contoh: `1:1e9` tidak mengalokasikan 4 GB RAM, melainkan membuat objek berukuran 40 byte yang mengkalkulasi nilai via fungsi iterasi.
- Menghubungkan array data langsung ke file terpetakan memori (*memory-mapped files* / `mmap`), menghindari siklus I/O alokasi memori ke dalam R heap.
- Membungkus struktur kolumnar Arrow atau array non-R tanpa serialisasi/deserialisasi (*Zero-Copy IPC*).

#### 3.5. Generational Garbage Collector (GC)
Garbage Collector R berbasis algoritma *Tracing Sweep*:
- **Gen 0 (Ephemeral)**: Menampung objek-objek alokasi baru dengan masa hidup sangat singkat (variabel lokal dalam fungsi, temporary vectors). GC frekuensi tinggi dengan pause time mikrodetik.
- **Gen 1**: Menampung objek yang selamat dari *sweep* Gen 0.
- **Gen 2 (Old/Tenured)**: Objek yang selamat dari sweeps Gen 1 (library code, persistent datasets, cache). Sweep dilakukan jarang, tetapi jika terjadi, waktu jeda (*stop-the-world*) meningkat signifikan seiring volume heap.

---

### 4. Why & What

| Dimensi | Scripting R Naif | Enterprise Production R |
| :--- | :--- | :--- |
| **Paradigma Objek** | Dominan *dynamic copy-on-write* tanpa kontrol referensi. | Pemanfaatan *Reference Class/R6* & memory mapping untuk memitigasi mutasi redundan. |
| **Manajemen Memori** | Mengandalkan alokasi otomatis; rentan thrashing GC saat loop besar. | Pre-alokasi deterministik, eksploitasi ALTREP, dan manual calling C API/Rcpp zero-copy. |
| **Eksekusi Komputasi** | Interpretasi interpreted AST lambat dengan overhead dispatch. | Kompilasi bytecode (`compiler::cmpfun`), vectorization C-level, multi-threading SIMD. |
| **Konkurensi** | *Single-threaded blocking execution loop*. | Forking process pools (`parallel`), Shared memory via `/dev/shm`, thread worker non-blocking. |
| **Interoperabilitas** | I/O berbasis flat file disk (CSV, TSV) lambat. | Format kolumnar berkinerja tinggi (Parquet via Apache Arrow) dengan pointer passing. |

**Mengapa ini penting?** 
Kritik bahwa "R lambat dan memakan banyak memori" hampir selalu disebabkan oleh pengembang yang memperlakukan R seperti Python atau C, mengabaikan struktur *cons-cell*, memicu rekursi duplikasi vektor (`x <- c(x, new_val)`), serta menyebabkan *GC lockup*. Memahami representasi internal adalah garis pemisah antara skrip laboratorium dan sistem inferensi latensi rendah berskala institusional.

---

### 5. How (Workflow Detail)

Alur eksekusi internal R dari string source-code hingga eksekusi memori tingkat rendah:

```
[R Source Code (Plain Text)]
            │
            ▼
[Lexer & Parser (src/main/gram.y)] ────────► AST (Abstract Syntax Tree sebagai PAIRSXP / Cons-cell)
            │
            ▼
[Bytecode Compiler (compiler package)] ────► SEXP (BCODESXP / Bytecode Array & Constant Pool)
            │
            ▼
[Bytecode Interpreter (eval.c)] ───────────► Evaluasi Loop
            │
    ┌───────┴──────────────────────────┐
    ▼                                  ▼
[Base Vector Execution Engine]     [.Call Interface]
    │                                  │
    ▼                                  ▼
[Allocation in Vector/Node Heap]   [C++ Extension (Rcpp/Native C)]
    │                                  │ Direct Pointer Manipulation
    ▼                                  ▼
[Generational GC Tracing Engine]   [OS Direct System Calls (mmap, SIMD)]
```

Langkah operasional optimasi pada arsitektur produksi:
1. **Fase Parsing & Kompilasi Bytecode**: R membaca AST. Gunakan `compiler::enableJIT(3)` untuk memastikan JIT compiler mengubah fungsi dan loop menjadi instruksi bytecode secara agresif.
2. **Evaluasi Argumentasi (Lazy Promises)**: Parameter fungsi dibungkus dalam `PROMSXP`. Nilai tidak dievaluasi sebelum diakses. Hindari mengevaluasi *promise* di dalam critical loop jika variabel tersebut tidak berubah nilainya.
3. **Eksekusi Native**: Operasi komputasi intensif dipetakan ke C/C++ menggunakan mekanisme `.Call("simbol_c", ..., PACKAGE = "nama_pkg")`. Menggunakan `.Call` melewati konversi tipe data yang terjadi pada modul legasi `.C` atau `.Fortran`.
4. **Memory Guard**: Variabel internal C++ di-wrap menggunakan template Rcpp (`Rcpp::NumericVector`) yang mengelola `PROTECT`/`UNPROTECT` secara deterministik via prinsip RAII (*Resource Acquisition Is Initialization*).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Manual vs Sistem Indeks ALTREP
- **Pendekatan Naif**: Anda meminta buku ensiklopedia 1000 halaman (`1:1000000`). Pustakawan memfotokopi 1.000.000 halaman, menumpuknya di atas meja Anda (Vector Heap alokasi 4MB/4GB), menghabiskan tempat, lalu membakar fotokopi tersebut ketika selesai dibaca (GC Sweep).
- **Pendekatan ALTREP**: Pustakawan hanya memberikan Anda selembar kartu indeks bertuliskan aturan: *"Jika Anda meminta halaman $i$, halaman tersebut bernilai $i$"*. Nol alokasi kertas. Kartu indeks hanya menghabiskan 40 byte, terlepas apakah Anda meminta rentang 10 halaman atau 10 triliun halaman.

#### Diagram: Perbandingan Siklus Hidup Alokasi Memori
```
Alokasi Tradisional (Modifikasi Elemen Tunggal pada Vector Besar):
---------------------------------------------------------------------------------
Heap Awal:      [Data Array 100M Reals (~800MB)] <--- Pointer: data_v1 (REFCNT=2)
                                                <--- Pointer: data_v2
Aksi: data_v1[1] <- 3.14
1. Runtime memeriksa REFCNT: Terdeteksi REFCNT = 2.
2. Vector Heap Baru dialokasikan: [Alokasi Baru 800MB].
3. Memori 800MB disalin blok demi blok (memcpy).
4. Indeks 1 diubah.
5. Pointer data_v1 diubah ke blok baru.
Hasil: 1.6 GB memori terpakai seketika, bandwidth cache RAM terkuras.
---------------------------------------------------------------------------------

Alokasi Berorientasi In-Place / Reference Object (R6 atau Pointer C++):
---------------------------------------------------------------------------------
Heap Terkelola: [Data Array 100M Reals (~800MB)] <--- R6 Object Ref / Raw Pointer
Aksi: obj$update_element(1, 3.14)
1. Pointer langsung ke alamat memori dieksekusi: *(ptr + 0) = 3.14
Hasil: 800MB total alokasi konstan, latensi sub-mikrodetik, 0 overhead GC.
---------------------------------------------------------------------------------
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Investigasi Copy-on-Modify Menggunakan Address Tracing
Membuktikan secara empiris kapan memory address berubah dan bagaimana `REFCNT` beroperasi.

```r
# Jalankan pada instalasi standar R (R >= 4.0.0)
suppressPackageStartupMessages(library(lobstr))

# Inisialisasi vektor bilangan bulat
v_source <- c(10L, 20L, 30L, 40L, 50L)

cat("--- Kondisi Awal ---\n")
cat("Alamat Memori Awal:", obj_addr(v_source), "\n")
cat("Representasi Ref Internals:\n")
.Internal(inspect(v_source))

cat("\n--- Aliasing Simbol Baru ---\n")
v_alias <- v_source
cat("Alamat Memori v_alias (Sama dengan v_source):", obj_addr(v_alias), "\n")
# REFCNT akan naik menjadi 2
.Internal(inspect(v_source))

cat("\n--- Mutasi Memori (Copy-on-Modify Terpicu) ---\n")
# Modifikasi elemen memicu deep-copy karena REFCNT > 1
v_alias[1] <- 999L

cat("Alamat Memori v_source (Tetap):", obj_addr(v_source), "\n")
cat("Alamat Memori v_alias (Berubah/Baru):", obj_addr(v_alias), "\n")
.Internal(inspect(v_alias))
```

#### 7.2. Practical Example: Engine Transformasi Berperforma Tinggi dengan Rcpp & Pointer Casting
Mengimplementasikan kernel moving average multithreaded yang melewati *R abstraction boundary* menggunakan implementasi C++ tingkat rendah via pointer eksplisit.

Buat file kernel C++:
```cpp
// [[Rcpp::plugins(cpp11)]]
// [[Rcpp::depends(RcppArmadillo)]]
#include <RcppArmadillo.h>

//' @title Rolling Sum Engine Tanpa Memory Allocation Berlebih
//' @param x NumericVector input data
//' @param window_size Integer besar window
//' @return NumericVector hasil rolling sum
// [[Rcpp::export]]
Rcpp::NumericVector fast_rolling_sum_cpp(const Rcpp::NumericVector& x, int window_size) {
    int n = x.size();
    if (window_size > n || window_size <= 0) {
        Rcpp::stop("Window size invalid relatif terhadap panjang vektor input.");
    }

    // Alokasi tepat SATU kali untuk output vector
    Rcpp::NumericVector result(n - window_size + 1);

    // Ambil raw pointers untuk melewati bounds-checking Rcpp operator[]
    const double* __restrict__ p_x = x.begin();
    double* __restrict__ p_res = result.begin();

    // Hitung jendela pertama secara sekuensial
    double current_sum = 0.0;
    for (int i = 0; i < window_size; ++i) {
        current_sum += p_x[i];
    }
    p_res[0] = current_sum;

    // Optimasi Sliding Window: O(N) komputasi total
    for (int i = 1; i <= n - window_size; ++i) {
        current_sum = current_sum - p_x[i - 1] + p_x[i + window_size - 1];
        p_res[i] = current_sum;
    }

    return result;
}
```

Script R Harness untuk Benchmark Produksi:
```r
library(Rcpp)
library(microbenchmark)

# Compile C++ kernel secara on-the-fly
sourceCpp(code = '
#include <Rcpp.h>
using namespace Rcpp;

// [[Rcpp::export]]
NumericVector fast_rolling_sum_cpp(const NumericVector& x, int window_size) {
    int n = x.size();
    if (window_size > n || window_size <= 0) stop("Invalid window size");
    NumericVector result(n - window_size + 1);
    const double* __restrict__ p_x = x.begin();
    double* __restrict__ p_res = result.begin();
    
    double current_sum = 0.0;
    for (int i = 0; i < window_size; ++i) current_sum += p_x[i];
    p_res[0] = current_sum;
    
    for (int i = 1; i <= n - window_size; ++i) {
        current_sum = current_sum - p_x[i - 1] + p_x[i + window_size - 1];
        p_res[i] = current_sum;
    }
    return result;
}
')

# Implementasi Naif Pure R
naive_rolling_sum_r <- function(x, window_size) {
    n <- length(x)
    res <- numeric(n - window_size + 1)
    for (i in 1:(n - window_size + 1)) {
        res[i] <- sum(x[i:(i + window_size - 1)]) # Trashing heap dengan alokasi slice berulang
    }
    return(res)
}

# Setup Payload Besar (1 Juta Observasi)
set.seed(42)
test_payload <- rnorm(1e6)
w_size <- 500L

# Eksekusi Validasi Kebenaran Numerik
res_cpp <- fast_rolling_sum_cpp(test_payload, w_size)
# Bandingkan sebagian elemen pertama
cat("Validasi: cpp[1:3] =", head(res_cpp, 3), "\n")

# Benchmark Latensi
bm <- microbenchmark(
    cpp_impl = fast_rolling_sum_cpp(test_payload, w_size),
    times = 20L
)
print(bm)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Engine Kliring Risiko Finansial Real-time (High-Throughput Tick Ingestion)
- **Konteks**: Institusi Perbankan Investasi memproses rata-rata 10 juta ticks valuta asing per menit, menghitung parameter *Value at Risk* (VaR) dan *Limit Breach Analysis* dengan SLA inferensi $< 150 \text{ ms}$ per batch tick.
- **Masalah pada Sistem Eksisting**: 
  Implementasi lama berbasis S4 Object Model di R menimbulkan latensi p99 mencapai $4.2 \text{ detik}$. Analisis `profvis` mengungkap:
  1. Penggunaan struktur data `data.frame` standar menduplikasi memori penuh setiap kali kolom risiko ditambahkan (*dynamic re-allocation*).
  2. S4 dispatch (`standardGeneric`) memiliki *method-lookup overhead* yang signifikan jika dieksekusi 100.000 kali per iterasi.
  3. Garbage collector terpicu setiap 1.5 detik (terutama Gen 1 dan Gen 2) akibat pembuatan jutaan objek kecil per transaksi.
- **Solusi Arsitektural**:
  1. **Refactoring Data Model**: Mengganti `data.frame` dan model S4 dengan **R6 Class** yang membungkus *pointer struct* C++ atau matriks kontigu tunggal, memanfaatkan modifikasi state in-place (*pass-by-reference*).
  2. **Inter-Process Memory Pipeline**: Membaca streaming tick langsung dari shared-memory segment via *Memory Mapped Files* (`bigstatsr::FBM` atau paket `mmap`), menghindari copy data dari disk/kernel space ke R heap.
  3. **Tuning GC Runtime**: Menyetel variabel lingkungan `R_GC_MEM_GROW=3` untuk mencegah R mengecilkan vector heap secara agresif, mengurangi frekuensi *GC compaction cycle*.

Arsitektur Implementasi State Controller berbasis R6:

```r
library(R6)

#' @title FinancialTickEngine
#' @description Arsitektur stateful processor in-place memitigasi memory churn
RiskEngine <- R6Class("RiskEngine",
    public = list(
        capacity = NULL,
        cursor = 0L,
        ticks_storage = NULL, # Contiguous raw numeric matrix
        var_threshold = NULL,

        initialize = function(capacity = 1e6, var_threshold = 2.58) {
            self$capacity <- as.integer(capacity)
            self$var_threshold <- var_threshold
            # Pre-alokasi Matrix 2D Contiguous (Cols: Price, Volume, Spread, Score)
            # Dilakukan 1 kali, zero allocation subsequent
            self$ticks_storage <- matrix(0.0, nrow = self$capacity, ncol = 4L)
            colnames(self$ticks_storage) <- c("Price", "Volume", "Spread", "Breached")
        },

        ingest_batch = function(prices, volumes, spreads) {
            batch_sz <- length(prices)
            if (self$cursor + batch_sz > self$capacity) {
                # Sirkular buffer wrap-around
                self$cursor <- 0L
            }

            idx_start <- self$cursor + 1L
            idx_end <- self$cursor + batch_sz

            # Direct in-place slicing assignation tanpa re-alokasi struktur tabel
            self$ticks_storage[idx_start:idx_end, 1L] <- prices
            self$ticks_storage[idx_start:idx_end, 2L] <- volumes
            self$ticks_storage[idx_start:idx_end, 3L] <- spreads

            # Vektor komputasi vectorized level C
            # Z-Score sederhana: (Price * Volume) / Spread
            z_scores <- (prices * volumes) / (spreads + 1e-6)
            breaches <- as.numeric(z_scores > self$var_threshold)
            self$ticks_storage[idx_start:idx_end, 4L] <- breaches

            self$cursor <- idx_end
            invisible(sum(breaches))
        },

        get_active_data = function() {
            # Mengembalikan shallow view
            if (self$cursor == 0L) return(matrix(numeric(0), nrow = 0, ncol = 4))
            return(self$ticks_storage[1L:self$cursor, , drop = FALSE])
        }
    )
)

# Benchmark Simulasi Streaming Ingestion
engine <- RiskEngine$new(capacity = 2e6, var_threshold = 5000.0)

# Uji Ingesti 500,000 baris dalam batch 50,000
batch_size <- 50000L
for (step in 1:10) {
    p <- runif(batch_size, 100, 200)
    v <- runif(batch_size, 10, 50)
    s <- runif(batch_size, 0.01, 0.05)
    
    breach_count <- engine$ingest_batch(p, v, s)
    cat(sprintf("Batch %d diproses. Anomali Breaches terdeteksi: %d\n", step, breach_count))
}
```
- **Hasil Metrik Produksi**:
  - Latensi Ingestion: Menurun dari $4.2 \text{ detik}$ menjadi $38 \text{ milidetik}$ (turun ~99%).
  - Footprint Memory: Stabil pada ~64 MB flat, eliminasi penuh terhadap lonjakan GC.

---

### 9. Trade-offs

Ketika merancang arsitektur sistem berbasis R, trade-off berikut harus dievaluasi:

| Keputusan Desain | Keuntungan | Kerugian & Konsekuensi | Skenario Pemilihan |
| :--- | :--- | :--- | :--- |
| **S3 vs R6 (Object Systems)** | **S3**: Sangat ringan (*minimal overhead*), pemanggilan fungsi cepat.<br>**R6**: Mutasi in-place, semantic encapsulation murni, tanpa *copy-on-modify*. | **S3**: Memperbanyak alokasi deep-copy saat memodifikasi atribut kompleks.<br>**R6**: Tidak aman untuk fungsi murni fungsional, rentan *thread race condition*. | Gunakan S3 untuk abstraksi analitik data immutability. Gunakan R6 untuk runtime koneksi, state engine, dan circular buffers. |
| **Vectorization vs C++ (Rcpp)** | **Vectorization**: Idiomatik, mudah dipelihara oleh Data Scientist umum.<br>**Rcpp**: Kontrol manual layout memori, eksekusi SIMD, latensi terendah. | **Vectorization**: Masih menimbulkan alokasi vektor temporer intermediat.<br>**Rcpp**: Menambah kompleksitas build pipeline, risiko segfault mematikan proses R runtime. | Gunakan pure vectorization untuk transformasi data standar. Gunakan Rcpp untuk algoritma iteratif beruntun (*Markov chain*, *stateful filters*). |
| **Multiprocessing (fork) vs Threading (OpenMP)** | **Forking**: Memisahkan memory space antar worker secara aman, copy-on-write Linux.<br>**OpenMP**: Latensi ultra-rendah, nol overhead IPC, penggunaan shared RAM efisien. | **Forking**: Konsumsi RAM tinggi saat modifikasi terjadi; tidak kompatibel dengan Windows.<br>**OpenMP**: R API *bukan thread-safe*; memanggil ekspresi R dalam loop OpenMP memicu instant crash. | Gunakan Forking (`parallel::mclapply`) untuk isolasi job batch besar. Gunakan OpenMP strictly di dalam layer C++ (Rcpp) untuk numeric-only crunching. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Dynamic Memory Allocation dalam Loop
```r
# SALAH FATAL: Menumbuhkan vector secara dinamis (O(N^2) complexity & GC Trashing)
data_out <- numeric(0)
for (i in 1:100000) {
    data_out <- c(data_out, i * 2.5) # Realokasi memori 100,000 kali!
}

# BENAR: Pre-alokasi deterministik
data_out <- numeric(100000) # Dialokasikan persis SATU kali
for (i in 1:100000) {
    data_out[i] <- i * 2.5
}
```

#### 10.2. Pointer Protection Stack Overflow pada Ekstensi C
```c
/* SALAH: Akumulasi proteksi tanpa pembersihan stack */
SEXP create_garbage_list(int n) {
    SEXP list = PROTECT(allocVector(VECSXP, n));
    for (int i = 0; i < n; i++) {
        SEXP val = PROTECT(allocVector(REALSXP, 1)); // Proteksi menumpuk di loop!
        REAL(val)[0] = i;
        SET_VECTOR_ELT(list, i, val);
    }
    UNPROTECT(n + 1); // Rawan stack overflow jika n > R_PPStackSize
    return list;
}

/* BENAR: Menggunakan perlindungan konstan (UNPROTECT berkala) */
SEXP create_optimized_list(int n) {
    SEXP list;
    PROTECT(list = allocVector(VECSXP, n));
    for (int i = 0; i < n; i++) {
        SEXP val = allocVector(REALSXP, 1);
        SET_VECTOR_ELT(list, i, val); // SET_VECTOR_ELT otomatis menjaga referensi di list
    }
    UNPROTECT(1);
    return list;
}
```

#### 10.3. Panduan Debugging Engine R Tingkat Lanjut
1. **Mendeteksi Memory Allocation & Churn**:
   - Gunakan `tracemem(x)` untuk menandai objek. Setiap kali objek tersebut di-copy pada memori fisik, runtime akan mencetak *call stack* dan alamat memori baru ke konsol. Hentikan tracking via `untracemem(x)`.
2. **Crash Analysis (Segfaults pada Native Code)**:
   - Jalankan R melalui GDB debugger:
     ```bash
     R -d gdb
     (gdb) run
     # Trigger crash pada script Anda...
     (gdb) bt # Menampilkan complete C/C++ backtrace
     ```
3. **Menguji Ketahanan GC (GC Torture)**:
   - Gunakan `gctorture(TRUE)`. Ini memaksa engine R untuk menjalankan *Full Garbage Collection* pada **setiap** alokasi memori sekecil apa pun.
   - *Peringatan*: Eksekusi akan melambat drastis ratusan kali, tetapi jika native C/C++ code Anda memiliki masalah pointer protection yang terlewat, fungsi ini akan langsung memicu *crash* di titik presisi kesalahan terjadi.

---

### 11. Best Practices (Production Checklist)

#### Kode dan Arsitektur
- [ ] Hindari penambahan elemen dinamis menggunakan operator `c()`, `cbind()`, atau `rbind()` di dalam loop iteratif apa pun.
- [ ] Pastikan seluruh iterasi intensif di-vectorize menggunakan primitives R (C-level) atau di-offload ke C++ via `Rcpp`.
- [ ] Konversi struktur data tabel besar dari `data.frame` standar ke `data.table` atau Arrow IPC Dataset untuk memaksa modifikasi referensial (*update-by-reference* `:=`).
- [ ] Enkapsulasi status operasional (*stateful logic*) menggunakan **R6 Classes**, bukan S4 atau Environment murni.

#### Runtime Memori & GC
- [ ] Atur environment variable `R_GC_MEM_GROW` pada server produksi (skala: 1-3) untuk membatasi fragmentasi pembebasan memori.
- [ ] Hindari pemanggilan manual `gc()` di dalam loop fungsional. Pemanggilan `gc()` manual memicu penundaan *full mark-and-sweep* (Gen 2) yang mematikan latensi p99.
- [ ] Manfaatkan profiling berkala via `profvis` dan pastikan alokasi memory line-by-line bernilai mendekati nol pada loop komputasi.

#### Paralelisasi & Interoperabilitas
- [ ] Jangan pernah memanggil API R internal (`Rcpp::Function`, `Rf_eval`, evaluasi environment) di dalam thread OpenMP.
- [ ] Batasi konsumsi core worker saat menggunakan `mclapply` agar tidak melampaui alokasi core fisik CPU (*Hyperthreading overhead elimination*).
- [ ] Terapkan serialization modern: Tinggalkan `saveRDS()` lambat untuk payload data raksasa; gunakan paket `qs` (*quick serialization*) atau `arrow::write_feather` untuk performa read/write sub-second berkecepatan multi-gigabyte.

---

### 12. Hands-on Practice

Struktur direktori kerja praktikum:
```text
hands-on/m02/
├── 01_memory_profiling.R
├── 02_rcpp_engine.cpp
├── 02_rcpp_runner.R
└── 03_altrep_simulation.R
```

#### Langkah 1: Investigasi Mutasi Memori & Profiling
Buat file `hands-on/m02/01_memory_profiling.R`:
```r
# hands-on/m02/01_memory_profiling.R
library(lobstr)

cat("=== Skenario 1: Copy-on-Modify Tracking ===\n")
large_vector <- rnorm(1e7) # ~80 MB RAM
cat("Alamat Awal:", obj_addr(large_vector), "\n")

# Aktifkan trace memory
tracemem(large_vector)

# Tindakan: Shallow Read (Harusnya TIDAK terjadi copy)
dummy_val <- large_vector[5]
cat("Setelah read, alamat:", obj_addr(large_vector), "\n")

# Tindakan: Duplikasi referensi
vec_copy <- large_vector
cat("vec_copy terikat. Alamat vec_copy:", obj_addr(vec_copy), "\n")

# Tindakan: Mutasi (Akan memicu output TRACEMEM ke stderr)
cat("Memulai mutasi indeks tunggal...\n")
vec_copy[1] <- 999.0
cat("Alamat vec_copy pasca mutasi:", obj_addr(vec_copy), "\n")

untracemem(large_vector)
cat("=== Skenario 1 Selesai ===\n")
```

#### Langkah 2: Kernel Alokasi C++ Deterministik
Buat file `hands-on/m02/02_rcpp_engine.cpp`:
```cpp
// hands-on/m02/02_rcpp_engine.cpp
#include <Rcpp.h>
using namespace Rcpp;

// [[Rcpp::export]]
NumericVector in_place_transform(NumericVector target, double multiplier) {
    // Memodifikasi langsung data array tanpa memicu alokasi copy R
    // PERINGATAN PRODUKSI: Ini melanggar semantik fungsionalitas R murni!
    // Hanya gunakan jika Anda sepenuhnya mengontrol daur hidup objek.
    double* p_data = target.begin();
    size_t n = target.size();

    for(size_t i = 0; i < n; ++i) {
        p_data[i] = p_data[i] * multiplier;
    }

    return target;
}
```

Buat runner file `hands-on/m02/02_rcpp_runner.R`:
```r
# hands-on/m02/02_rcpp_runner.R
library(Rcpp)
library(lobstr)

sourceCpp("hands-on/m02/02_rcpp_engine.cpp")

original_data <- c(1.0, 2.0, 3.0, 4.0, 5.0)
cat("Alamat Sebelum Eksekusi C++:", obj_addr(original_data), "\n")
cat("Nilai Sebelum:", original_data, "\n")

# Eksekusi fungsi C++ yang memutasi raw pointer
transformed_data <- in_place_transform(original_data, 10.0)

cat("Alamat Output C++:", obj_addr(transformed_data), "\n")
cat("Alamat Asal (Harus Sama persis):", obj_addr(original_data), "\n")
cat("Nilai Setelah:", original_data, "\n")
```

#### Langkah 3: Eksplorasi Performa Kompresi ALTREP
Buat file `hands-on/m02/03_altrep_simulation.R`:
```r
# hands-on/m02/03_altrep_simulation.R
library(lobstr)

cat("=== Menguji Karakteristik Memori ALTREP ===\n")

# Rentang sekuensial (ALTREP compact sequence integer)
altrep_seq <- 1:1e8

cat("Ukuran Objek ALTREP (100 Juta Elemen):", obj_size(altrep_seq), "bytes\n")
.Internal(inspect(altrep_seq))

# Transformasikan vektor kompak ALTREP menjadi Vector Heap Nyata
# Mutasi sederhana memaksa runtime untuk mengekspansi vektor ke memori riil
cat("\nMemaksa Materialisasi ALTREP ke RAM Vector Heap...\n")
altrep_seq[1] <- 999L

cat("Ukuran Objek Pasca Materialisasi:", obj_size(altrep_seq), "bytes (~400MB)\n")
.Internal(inspect(altrep_seq))
```

Jalankan skrip-skrip ini melalui CLI shell terminal:
```bash
Rscript hands-on/m02/01_memory_profiling.R
Rscript hands-on/m02/02_rcpp_runner.R
Rscript hands-on/m02/03_altrep_simulation.R
```

---

### 13. Exercise

#### Level Easy
Tulis skrip R yang mengalokasikan vektor integer $10^7$ elemen. Buktikan menggunakan fungsi `lobstr::obj_addr()` bahwa sub-setting sederhana `x[1:100]` menghasilkan deep-copy instan pada Vector Heap baru, dan hitung delta konsumsi memori sebelum dan sesudah subsetting.

#### Level Medium
Buat class berbasis **R6** bernama `CircularDataBuffer` yang mengalokasikan matriks numerik `1000 x 50`. Implementasikan method `push_row(vector_50)` yang menyisipkan data secara FIFO (First-In, First-Out) menggantikan baris paling lama tanpa pernah memanggil alokasi memori baru atau memodifikasi address internal matriks (`obj_addr` tetap identik sepanjang siklus operasi).

#### Level Hard
Kembangkan paket minimal via `Rcpp` yang mengimplementasikan fungsi filtering matriks sparse:
- Fungsi menerima matriks numerik densitas rendah ($10^6$ baris).
- Komputasi dilakukan multi-threaded menggunakan OpenMP C++ loop.
- **Batasan Ketat**: Nol alokasi memory di dalam thread worker; Anda dilarang keras menginstansiasi objek `Rcpp::NumericVector` atau berinteraksi dengan API R internals di dalam loop OpenMP. Output harus ditulis ke matriks terprealokasi di master thread.

---

### 14. Challenge

**Judul Tantangan**: Zero-Copy Shared-Memory IPC Ring-Buffer Engine  
**Deskripsi Skenario**:  
Anda ditugaskan merancang modul analitik real-time yang menerima input dari proses eksternal (misal: feed daemon C++ tingkat OS). 
- Anda tidak boleh menggunakan soket TCP/HTTP karena batas latency overhead.
- Anda harus mengimplementasikan solusi berbasis *memory-mapped files* (`mmap` via POSIX shm `/dev/shm`).
- Tulis satu layer pembaca R yang membungkus blok memori terpetakan tersebut menggunakan konsep **ALTREP** kustom (atau integrasi paket `mmap` / `bigstatsr`) sehingga R dapat membaca dan memproses array metrik finansial tanpa pernah menyalin blok data mentah tersebut ke dalam R Vector Heap.
- Modul Anda harus mencakup mekanisme *lock-free read barrier* sederhana (misal memanfaatkan *atomic monotonic sequence counter* di header memori) untuk memastikan bahwa thread R tidak membaca record parsial yang sedang ditulis oleh feed eksternal.
- Uji dan laporkan performa latensi agregasi (*mean*, *variance*) terhadap 50 juta records, dengan target latensi inferensi di bawah **10 milidetik**.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa tipe representasi C internal fundamental yang digunakan oleh GNU R Engine untuk membungkus hampir seluruh objek runtime?
2. Mengapa sintaks `x <- 1:1e9` dapat dieksekusi secara instan dengan konsumsi RAM di bawah 1 KB pada R modern?
3. Sebutkan perbedaan perilaku antara sistem `NAMED` legasi dan sistem `REFCNT` yang diperkenalkan pada R 4.0.0.
4. Apa fungsi dari array `PROTECT` stack pada C API R?
5. Di antara model objek S3, S4, dan R6, model manakah yang natively menggunakan semantik *pass-by-reference*?

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Mengapa mengeksekusi operasi `x[i] <- val` di dalam loop bersarang pada sebuah `data.frame` menghasilkan performa yang jauh lebih lambat dibandingkan pada objek `matrix`?
7. Apa yang terjadi secara internal pada struktur memori SEXP ketika Anda memodifikasi satu elemen dari objek yang memiliki `REFCNT > 1`?
8. Mengapa memanggil fungsi C API R di dalam blok loop C++ yang diparalelisasi dengan `#pragma omp parallel` hampir selalu berakhir dengan *Fatal Crash/Segmentation Fault*?
9. Bagaimana cara kerja Tracing Generational Garbage Collector R dalam membedakan penanganan objek di Gen 0 vs Gen 2?
10. Apa kegunaan utama dari compiler flag `__restrict__` pada pointer C/C++ ketika memproses array data numerik yang diekstraksi dari Rcpp?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Analitis)
11. **Skenario A**: Sebuah microservice R berbasis REST API (`Plumber`) mengalami peningkatan konsumsi RAM linier (*memory leak*) hingga server kehabisan memori (OOM) setiap 24 jam, padahal semua variabel fungsi telah diisolasi di dalam local functions. Setelah dianalisis, service tersebut sering menggunakan fungsi *closure* (higher-order function returning functions). Di mana letak akar permasalahan memori tersebut?
12. **Skenario B**: Tim engineer Anda mendapati proses batch malam berbasis R mengalami lonjakan waktu komputasi dari 30 menit menjadi 6 jam ketika volume data meningkat dua kali lipat. Hasil profile menunjukkan sebagian besar waktu CPU dihabiskan pada routine fungsi C `gc()`. Langkah konfigurasi sistem dan arsitektural kode apa yang harus segera diambil?
13. **Skenario C**: Anda membangun library inferensi real-time. Anda mengeksekusi integrasi model C++ via `Rcpp`. Pada skenario testing beban tinggi (1.000 request/detik), sesekali terjadi `Segmentation Fault` acak tanpa error log jelas. `gctorture(TRUE)` langsung membuat kode tersebut crash seketika pada fungsi pembentukan vektor output. Mengapa ini terjadi dan bagaimana solusinya?

---

#### Kunci Jawaban & Evaluasi Teknis

1. **SEXP** (Pointer ke struktur `SEXPREC`).
2. Karena diimplementasikan melalui **ALTREP** (`compact_intseq`), hanya menyimpan batas awal dan akhir alih-alih mengalokasikan array angka riil pada Vector Heap.
3. `NAMED` hanya bernilai 0, 1, atau 2 (di mana jika mencapai 2, objek dicap sebagai shared secara permanen dan memicu duplikasi selamanya). `REFCNT` melacak jumlah referensi secara presisi naik dan turun, memungkinkan mutasi in-place jika referensi turun kembali ke 1.
4. Mencegah objek yang baru dialokasikan pada heap dibersihkan oleh Garbage Collector saat alokasi memori lain dipicu sebelum objek tersebut ditautkan pada environment aktif R.
5. **R6** (dan *Reference Classes* / RC).
6. `data.frame` adalah *pairlist* bertipe list of vectors dengan metadata kompleks. Modifikasi satu elemen menyebabkan duplikasi list, modifikasi struktur atribut, dan shallow/deep copy dari vektor kolom terkait. Matriks adalah satu vektor primitif kontigu di memory heap dengan atribut `dim`.
7. Runtime R mengalokasikan blok memori kontigu baru pada Vector Heap, melakukan *memcpy* data lama ke blok baru, memodifikasi elemen target pada blok baru, mengarahkan simbol pemanggil ke blok baru, dan menurunkan `REFCNT` pada blok lama.
8. Runtime GNU R bersifat *single-threaded non-reentrant*. Struktur data internal R, proteksi stack, dan thread global state tidak dilindungi oleh mutex/lock, sehingga concurrent access dari thread OpenMP memicu *race condition* instan pada memory manager.
9. Gen 0 di-sweep pada frekuensi tinggi dengan asumsi objek berumur pendek (ephemeral) dan menggunakan algoritma cepat. Objek yang selamat dipromosikan ke Gen 1 lalu Gen 2. Gen 2 mengasumsikan data statis/panjang; ia hanya di-sweep saat heap batas atas terlampaui atau terjadi alokasi masif, melakukan traversal ke seluruh graph node memory yang memakan siklus CPU signifikan.
10. Memberitahu compiler C++ bahwa pointer tersebut adalah satu-satunya penunjuk ke blok memori tersebut (*no aliasing*), memungkinkan compiler menerapkan auto-vectorization SIMD secara maksimal tanpa kekhawatiran memory overlap.
11. **Analisis Akar Masalah**: Fungsi closure di R menahan referensi implisit ke **enclosing environment** tempat fungsi tersebut diciptakan. Jika fungsi pembuat closure menyimpan objek lokal besar (misal: data training mentah atau dataframe sementara), seluruh environment tersebut tetap hidup di memori dan tidak akan pernah dibebaskan oleh GC selama fungsi closure tersebut masih memiliki referensi aktif. Solusi: Kosongkan variabel besar (`rm(large_var)`) sebelum mengembalikan closure atau atur parent environment secara eksplisit.
12. **Solusi Crash GC Churn**: 
    - Kode: Hilangkan pembentukan vektor dinamis di loop; ganti `rbind`/`cbind` berulang dengan pre-alokasi list lalu gabungkan 1 kali via `data.table::rbindlist()`.
    - Konfigurasi: Tingkatkan batas pertumbuhan heap dengan mengatur environment variable OS: `R_GC_MEM_GROW=3` dan naikkan min-heap size menggunakan argumen CLI R `--min-vsize` dan `--min-nsize` saat menjalankan script untuk mencegah R memicu GC saat ekspansi heap awal.
13. **Solusi Segfault Acak**: Pointer memory yang dialokasikan via C API R tidak di-proteksi secara benar atau terlambat di-proteksi setelah alokasi sekunder terjadi di bawahnya. Ketika beban tinggi, alokasi internal R memicu GC sweep mikrodetik yang menyapu SEXP yatim tersebut. Menggunakan template RAII seperti `Rcpp::NumericVector` secara konsisten tanpa mencampur aduk manipulasi raw pointer `Rf_allocVector` telanjang tanpa `PROTECT()`, atau pastikan pasangan `UNPROTECT` seimbang secara deterministik.

---

### 16. Summary

1. **Struktur Fundamental**: Segala sesuatu di dalam memori R adalah `SEXP`, yang dialokasikan di antara **Node Heap** (cons-cells, metadata, environments) dan **Vector Heap** (payload numerik kontigu).
2. **Semantik Memori Modern**: Sejak R 4.0.0, **Reference Counting (`REFCNT`)** dan **ALTREP** menyediakan landasan performa tinggi, mengeliminasi penyalinan memori yang tidak perlu jika kode dirancang sesuai dengan aturan mutasi in-place dan representasi lazy.
3. **Optimasi Berbasis C++ (Rcpp)**: Batas performa komputasi R dapat diatasi dengan mendelegasikan iterasi berat ke C++. Penggunaan *raw pointer* C++ melewati bounds-checking dan memampukan optimasi compiler tingkat lanjut (SIMD/AVX).
4. **Pola Desain Produksi**: Sistem enterprise skala terabyte harus meninggalkan manipulasi `data.frame` naif dan beralih ke **R6 Classes**, **Arrow Feather/Parquet IPC**, format in-memory **Memory-Mapped Files**, serta pre-alokasi deterministik untuk menjaga latensi p99 dan stabilitas GC.