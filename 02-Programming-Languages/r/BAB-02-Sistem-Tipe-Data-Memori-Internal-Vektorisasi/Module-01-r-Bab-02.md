# Modul Pembelajaran: Sistem Tipe Data, Memori Internal, & Vektorisasi di R

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** `02-Programming-Languages`
*   **Mata Kuliah / Bahasa:** R Runtime & Core Systems
*   **Bab / Modul:** Bab 02 Module 01
*   **Judul Modul:** Sistem Tipe Data, Memori Internal, & Vektorisasi
*   **Tingkat Kesulitan:** Tingkat Lanjut (Advanced Core)
*   **Prasyarat Pengetahuan:** Dasar-dasar sintaks R, konsep pointer/alokasi memori secara umum di arsitektur von Neumann, serta struktur data primitif.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Mendiagnosis Arsitektur Data R:** Membedakan 6 tipe atomic vector primitif beserta hierarki koersi implisit dan representasi C underlying (`SEXPREC`).
2.  **Menganalisis Pola Memori Internal:** Melacak mekanisme *Copy-on-Write* (CoW), *Reference Counting* (`REFCNT`), dan *Alternative Representation* (`ALTREP`) menggunakan *low-level inspect tools*.
3.  **Mengeliminasi Alokasi Memori Kuadratik ($O(N^2)$):** Mengidentifikasi dan merefaktor kode non-vektor yang menyebabkan *memory duplication* menjadi algoritma alokasi deterministik $O(N)$ atau in-place.
4.  **Menerapkan Paradigma Vektorisasi Ekstrinsik & Intrinsik:** Mengonstruksi komputasi berkinerja tinggi yang memanfaatkan loop tingkat C dan arsitektur SIMD (*Single Instruction, Multiple Data*) bawaan interpreter.
5.  **Mendeteksi & Memitigasi Degradasi Kinerja Skala Besar:** Mengukur konsumsi memori aktual (*shallow* vs *deep size*) serta overhead garbage collector (`gc()`) dalam manipulasi data berskala gigabyte.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Ilusi Skalar vs Realitas Vektor
Bagi programmer yang bermigrasi dari C, Java, atau Python, insting pertama adalah memperlakukan variabel tunggal seperti `x <- 5` sebagai skalar primitif 64-bit yang tersimpan langsung di stack frame. **Di R, skalar tidak pernah ada.**
Pernyataan `x <- 5` mengalokasikan atomic vector bertipe `double` dengan panjang ($N=1$) di atas heap, lengkap dengan header C-struct berukuran minimal 48–64 byte.

```
Mental Model Salah:  [ 5 ] (8-byte integer/double di CPU register/stack)
Mental Model Benar:  [ SEXP Header (48B) | Data Pointer | Cap: 1 | Val: 5.0 ]
```

### Paradigma *Copy-on-Write* (CoW)
R menggunakan semantik *pass-by-value* murni secara konseptual. Namun, agar efisien, runtime R menerapkan optimasi *Copy-on-Write*:
1. Dua variabel dapat merujuk ke memori fisik yang sama selama keduanya hanya membaca data (*read-only* alias *shared reference*).
2. Duplikasi data (*deep copy*) baru dipicu tepat sebelum salah satu variabel memodifikasi nilainya, **kecuali** referensi objek tersebut berstatus unik (`REFCNT == 1`), di mana modifikasi dapat dieksekusi secara *in-place* (mutasi langsung).

### Hakikat Komputasi Vektor
Looping eksplisit (`for`, `while`) di R lambat bukan karena CPU lambat mengeksekusi instruksi, melainkan karena interpreter R harus mengevaluasi tipe data, *method dispatch*, isolasi *scope environment*, dan verifikasi sinyal interupsi pada **setiap siklus iterasi**.
Vektorisasi bukan sekadar menyembunyikan loop di balik fungsi tingkat tinggi; vektorisasi berarti mendelegasikan iterasi langsung ke kompilasi C/Fortran native yang beroperasi contiguous di memori, memaksimalkan *CPU L1/L2 cache hit*, serta membuka peluang optimasi SIMD.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Struktur Internal `SEXPREC` dan Node Memori R

```
+------------------------------------------------------------------------+
|                          SEXPREC (C Struct)                            |
+------------------------------------------------------------------------+
| sxpinfo_struct (4 bytes / 32-bit):                                     |
|   - TYPE      : 5 bit (tipe: INTSXP, REALSXP, STRSXP, VECSXP, dll.)   |
|   - OBJ       : 1 bit (apakah objek S3/S4 beratribut class)            |
|   - MARK      : 1 bit (digunakan oleh Mark-Sweep Garbage Collector)    |
|   - REFCNT    : 16 bit (penghitung referensi CoW: 0, 1, 2, ...)       |
|   - GC_GEN    : 2 bit (generasi memori GC: 0, 1, 2)                    |
|   - ATTRIB    : Pointer ke atribut metadata (dim, names, class)        |
+------------------------------------------------------------------------+
| Pointer: *attrib (8 bytes) -> R_NilValue atau Pairlist of Attributes   |
+------------------------------------------------------------------------+
| Pointer: *next (8 bytes)   -> R Gc-Chain Vector List                   |
+------------------------------------------------------------------------+
| Data Payload (Union):                                                  |
|   - Vector Data Pointer: void* (array nilai: int[], double[], dll.)    |
|   - Length (R_xlen_t): 8 bytes (panjang elemen)                        |
|   - Truelength: 8 bytes (alokasi buffer kapasitas berlebih)            |
+------------------------------------------------------------------------+
```

### Alur Mutasi Memori: In-Place vs Duplicate (Copy-on-Write)

```
Skenario A: Mutasi In-Place (REFCNT == 1)
 [x] --------> [ SEXPREC Header: REFCNT = 1 ] ---> [ Buffer: 1, 2, 3 ]
                      |
                 Mutasi: x[1] <- 9L
                      v
 [x] --------> [ SEXPREC Header: REFCNT = 1 ] ---> [ Buffer: 9, 2, 3 ]
                      (Tidak ada alokasi baru)

Skenario B: Copy-on-Write (REFCNT > 1)
 [x] -----\
           +-> [ SEXPREC Header: REFCNT = 2 ] ---> [ Buffer: 1, 2, 3 ]
 [y] -----/           |
                 Mutasi: y[1] <- 9L
                      v
 [x] --------> [ SEXPREC Header: REFCNT = 1 ] ---> [ Buffer: 1, 2, 3 ]
 [y] --------> [ SEXPREC Header: REFCNT = 1 ] ---> [ Buffer: 9, 2, 3 ]
                      (Memori diduplikasi secara eksplisit!)
```

### Pipelining Vektorisasi vs Interpreter Overhead

```
FOR-LOOP TERINTERPRETASI (Lambat):
[Iterasi i] -> [Fetch AST Node] -> [Type Resolution] -> [Env Lookup] -> [Exec + Store] -> [Cek GC/Signal]
      ^                                                                                           |
      +---------------------------------- Loop Overhead (xN) -------------------------------------+

VEKTORISASI C-LEVEL (Cepat):
[R Function Call] -> [Direct C Entrypoint] -> [Contiguous Memory Chunk]
                                                      |
                                                      v
                                        [SIMD Register Vectorized Loop]
                                          (4x-8x Operasi paralel / clock)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur `SEXPREC` di Source Code R (`Rinternals.h`)
Dalam implementasi GNU R, semua objek dibungkus dalam tipe abstrak `SEXP` (pointer ke `SEXPREC`).

```c
/* Cuplikan konseptual dari arsitektur representasi internal R */
struct sxpinfo_struct {
    SEXPTYPE type : 5;
    unsigned int scalar : 1;
    unsigned int alt : 1;
    unsigned int obj : 1;
    unsigned int gp : 16;
    unsigned int mark : 1;
    unsigned int debug : 1;
    unsigned int trace : 1;
    unsigned int spare : 1;
    unsigned int gcgen : 1;
    unsigned int gccls : 3;
    unsigned int named : 16; /* Menjadi REFCNT pada R modern */
};

struct SEXPREC {
    struct sxpinfo_struct sxpinfo;
    struct SEXPREC *attrib;
    struct SEXPREC *gengc_next_node;
    struct SEXPREC *gengc_prev_node;
    union {
        struct primsxp_struct primsxp;
        struct symsxp_struct symsxp;
        struct listsxp_struct listsxp;
        struct envsxp_struct envsxp;
        struct closxp_struct closxp;
        struct promsxp_struct promsxp;
    } u;
};
```

### 2. Tipe Atomic Vector Primitif
Di tingkat hardware, array atomic dialokasikan berurutan (*contiguous block*):
*   **LGLSXP (Logical):** Array bertipe `int` C (4 byte per elemen). Nilai: `0` (FALSE), `1` (TRUE), dan `INT_MIN` (-2147483648) merepresentasikan `NA`.
*   **INTSXP (Integer):** Array bertipe `int32_t` C (4 byte per elemen).
*   **REALSXP (Double):** Array bertipe IEEE 754 `double` (8 byte per elemen).
*   **CPLXSXP (Complex):** Array dari struct dua `double` (16 byte per elemen: real & imaginary).
*   **STRSXP (Character):** Array dari pointer `CHARSXP` (8 byte per pointer di arsitektur 64-bit). Nilai string aktual disimpan di *Global String Pool* untuk *string deduplication*.
*   **RAWSXP (Raw):** Array `uint8_t` (1 byte per elemen), tanpa representasi `NA`.

### 3. Alternative Representations (ALTREP)
Sejak R 3.5.0, mekanisme ALTREP memungkinkan R merepresentasikan pola data terstruktur tanpa mengalokasikannya secara material di memori fisik. 
Sebagai contoh, ekspresi `1:1e9` tidak mengalokasikan memori sebesar $\approx 4\text{ GB}$, melainkan sebuah struct ALTREP berukuran $\approx 64\text{ byte}$ yang hanya mencatat *start value* (`1`), *step* (`1`), dan *length* (`1000000000`). Data hanya dimaterialisasi jika pointer native-nya diakses oleh pustaka C eksternal yang tidak mendukung ALTREP.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Aturan Koersi Implisit (Implicit Coercion Hierarchy)
R menganut sistem *strongly-typed dynamic dispatch* pada atomic vector. Karena atomic vector harus bersifat homogen, penggabungan elemen berbeda tipe akan memicu koersi otomatis mengikuti jalur non-destruktif terkecil:

$$\text{raw} \longrightarrow \text{logical} \longrightarrow \text{integer} \longrightarrow \text{double} \longrightarrow \text{complex} \longrightarrow \text{character}$$

Jika konversi mengalami kegagalan struktural (misal, string non-numerik diubah ke double), R tidak melempar eksepsi fatal melainkan mengembalikan *sentinel value* `NA` disertai `warning: NAs introduced by coercion`.

### Memori: Cache Locality & SIMD
Prosesor modern mengambil data dari RAM menuju CPU Cache (L1, L2, L3) dalam satuan *Cache Lines* (umumnya 64 byte). 
1. **Contiguous Memory:** Atomic vector bertipe `double` (8 byte) menempatkan 8 elemen dalam satu cache line. Akses sekuensial berjalan sangat optimal karena algoritma *hardware prefetcher* CPU membaca blok berikutnya sebelum instruksi meminta data tersebut.
2. **Generic Vector (List / `VECSXP`):** `list` di R hanyalah array yang berisi kumpulan pointer `SEXP` ke node memori lain. Akibatnya, iterasi terhadap list menyebabkan fenomena *pointer chasing*, memicu lonjakan *Cache Misses* yang mendegradasi performa CPU hingga satu orde magnitudo.

### Analisis Asimptotik Alokasi Memori
Menambahkan data ke vektor secara bertahap menggunakan loop konvensional:
```r
x <- integer(0)
for (i in 1:N) {
  x <- c(x, i) # BENCANA PERFORMA
}
```
Setiap operasi `c(x, i)` mengeksekusi alokasi baru dan menyalin $k$ elemen sebelumnya. Kompleksitas ruang dan waktu akumulatif:

$$\sum_{k=1}^{N} k = \frac{N(N + 1)}{2} = \mathcal{O}(N^2)$$

Jika $N = 100.000$, alih-alih mengeksekusi $10^5$ siklus, interpreter menyalin data sebanyak $5 \times 10^9$ elemen, memicu *Garbage Collection thrashing* dan penurunan performa drastis.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah skrip diagnostik untuk mengeksplorasi hierarki tipe, mekanisme CoW, dan ALTREP.

```r
# Prasyarat: Pastikan package 'lobstr' terpasang
if (!requireNamespace("lobstr", quietly = TRUE)) {
  install.packages("lobstr")
}
library(lobstr)

# 1. Verifikasi Ukuran Minimal Objek Kosong (Overhead SEXPREC)
empty_double <- numeric(0)
cat("Ukuran base SEXPREC numeric(0):", obj_size(empty_double), "bytes\n")

# 2. Investigasi Hierarki Koersi Implisit
v_mixed <- c(TRUE, 42L, 3.14, "production")
cat("Tipe data hasil koersi gabungan:", typeof(v_mixed), "\n")
print(v_mixed)

# 3. Observasi Alamat Memori dan Copy-on-Write (CoW)
vec_a <- c(10.5, 20.2, 30.7, 40.9)
cat("Alamat awal vec_a :", obj_addr(vec_a), "\n")

# Salin referensi (Shared Reference)
vec_b <- vec_a
cat("Alamat awal vec_b :", obj_addr(vec_b), "(Harus identik dengan vec_a)\n")

# Mutasi data pada vec_b (Memicu CoW)
vec_b[1] <- 99.9
cat("Alamat vec_b pasca modifikasi:", obj_addr(vec_b), "(Alamat berubah!)\n")
cat("Alamat vec_a pasca modifikasi:", obj_addr(vec_a), "(Tetap tidak berubah)\n")

# 4. Observasi ALTREP (Alternative Representation)
altrep_seq <- 1:1e8
cat("Ukuran representasi ALTREP 100 juta integer:", obj_size(altrep_seq), "bytes\n")
cat("Tipe internal objek ALTREP:\n")
.Internal(inspect(altrep_seq))
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

*   **Baris 9–10:** `numeric(0)` dievaluasi. Meskipun memiliki panjang nol elemen, ukuran memorinya mencapai 48 byte (atau 56 byte tergantung platform). Ini adalah representasi konkret dari C struct `SEXPREC` yang menampung bit flag, pointer atribut, dan *bookkeeping* memori.
*   **Baris 13–14:** `c(TRUE, 42L, 3.14, "production")` menggabungkan `logical`, `integer`, `double`, dan `character`. Berdasarkan rantai koersi implisit, seluruh elemen dinaikkan derajatnya ke kasta tertinggi: `character`. Operasi ini mentransformasikan angka internal menjadi representasi string di *Global String Pool*.
*   **Baris 17–18:** `vec_a` dialokasikan pada alamat heap tertentu. `lobstr::obj_addr()` mengekstraksi alamat pointer 64-bit langsung dari node `SEXP`.
*   **Baris 21–22:** `vec_b <- vec_a` tidak menduplikasi array di RAM. Kedua pointer variabel (`vec_a` dan `vec_b`) menunjuk ke blok memori yang sama. Flag internal `REFCNT` pada `SEXPREC` dinaikkan menjadi 2.
*   **Baris 25–27:** Mutasi `vec_b[1] <- 99.9` mendeteksi bahwa data dibagi bersama (`REFCNT > 1`). Runtime R segera mengeksekusi operasi kloning buffer memori, mengubah nilai indeks ke-1 pada buffer baru, dan memetakan simbol `vec_b` ke alamat baru. Nilai dan alamat `vec_a` terlindungi secara utuh.
*   **Baris 30–33:** `1:1e8` menginstansiasi *compact integer sequence* berbasis ALTREP class `compact_intseq`. Alih-alih membutuhkan $\approx 400\text{ MB}$, objek ini hanya memakan 680 byte untuk struct pembungkusnya. Fungsi internal `.Internal(inspect())` membuktikan bahwa data belum dimaterialisasi dalam bentuk array konvensional.

---

## SEKSI 09 — STUDI KASUS NYATA

### Pipeline Agregasi Sinyal Sensor Finansial (Tick-Data Stream)
Sebuah sistem High-Frequency Trading (HFT) menerima rata-rata 1.000.000 record harga bid-ask per detik. Data yang masuk harus diproses secara sliding-window untuk menghitung rasio volatilitas menggunakan formula:

$$Z_t = \frac{P_t - \mu_{window}}{\sigma_{window}}$$

**Masalah di Lingkungan Produksi:**
Pipeline awal yang ditulis oleh tim analitik mengalami *memory leak* semu dan *latency spikes* ekstrem hingga 15 detik per batch processing. Garbage collector sistem R membekukan proses utama (*stop-the-world GC pause*).

**Akar Penyebab (Root Cause Analysis):**
1. Data streaming diakumulasikan ke vektor dinamis menggunakan pola `x <- c(x, new_tick)`, memicu $O(N^2)$ alokasi ulang dan CoW berkelanjutan.
2. Filter logika ditulis menggunakan conditional looping skalar `for` dan percabangan `if ()` alih-alih operasi vektor.
3. Objek `Date` dan `POSIXct` secara konstan dikonversi bolak-balik dari/ke `character`, memicu pencarian berulang pada *Global String Pool*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut solusi komprehensif: membandingkan pendekatan naif yang mendegradasi sistem dengan arsitektur vektor teroptimasi yang memanfaatkan *pre-allocation* dan vektorisasi murni.

```r
# ==============================================================================
# PIPELINE PEMROSESAN HIGH-FREQUENCY TICK-DATA
# ==============================================================================

# Simulasi data mentah tick sensor (100.000 data point)
set.seed(42)
n_ticks <- 1e5
raw_prices <- 100 + cumsum(rnorm(n_ticks, mean = 0.01, sd = 0.5))

# ------------------------------------------------------------------------------
# PENDEKATAN 1: NAIF & NON-VEKTORISASI (Bencana Performa & Memori)
# ------------------------------------------------------------------------------
process_naive <- function(prices) {
  transformed_data <- numeric(0) # Inisialisasi kosong
  
  for (i in seq_along(prices)) {
    # CoW & Re-alokasi kuadratik pada setiap langkah!
    if (prices[i] > 100) {
      val <- log(prices[i]) * 1.5
    } else {
      val <- log(prices[i]) * 0.5
    }
    transformed_data <- c(transformed_data, val)
  }
  return(transformed_data)
}

# ------------------------------------------------------------------------------
# PENDEKATAN 2: ARSITEKTUR VEKTORISASI & PRE-ALLOCATION (Standar Produksi)
# ------------------------------------------------------------------------------
process_optimized <- function(prices) {
  len <- length(prices)
  
  # Strategi Vektorisasi Penuh: Menghilangkan Loop Interpreter
  # 1. Alokasi mask kondisi berbasis Boolean Vector (C-Speed)
  condition_mask <- prices > 100
  
  # 2. Vektorisasi transformasi logaritma (SIMD-enabled C backend)
  log_prices <- log(prices)
  
  # 3. Operasi vektor inplace via seleksi indeks (Zero Duplication Spikes)
  result <- numeric(len)
  result[condition_mask]  <- log_prices[condition_mask] * 1.5
  result[!condition_mask] <- log_prices[!condition_mask] * 0.5
  
  return(result)
}

# ------------------------------------------------------------------------------
# BENCHMARKING & OBSERVASI MEMORI/WAKTU
# ------------------------------------------------------------------------------
# Catatan: Jumlah iterasi pendekatan naif dibatasi agar benchmark selesai rasional
n_sub <- 20000
cat(sprintf("--- Memulai Benchmark pada %d elemen ---\n", n_sub))

# Uji Pendekatan Naif
gc(full = TRUE, verbose = FALSE)
time_naive_start <- Sys.time()
res_naive <- process_naive(raw_prices[1:n_sub])
time_naive_end <- Sys.time()
dur_naive <- as.numeric(difftime(time_naive_end, time_naive_start, units = "secs"))
cat(sprintf("Pendekatan Naif      : %f detik\n", dur_naive))

# Uji Pendekatan Teroptimasi
gc(full = TRUE, verbose = FALSE)
time_opt_start <- Sys.time()
res_opt <- process_optimized(raw_prices[1:n_sub])
time_opt_end <- Sys.time()
dur_opt <- as.numeric(difftime(time_opt_end, time_opt_start, units = "secs"))
cat(sprintf("Pendekatan Teroptimasi: %f detik\n", dur_opt))

cat(sprintf("Speedup Factor       : %.2fx lipat lebih cepat!\n", dur_naive / dur_opt))

# Validasi Identitas Hasil Komputasi
stopifnot(isTRUE(all.equal(res_naive, res_opt)))
cat("Validasi: Output kedua implementasi identik 100% secara numerik.\n")
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Di bawah ini adalah matriks komparasi struktural implementasi data dan looping di ekosistem runtime R.

| Paradigma | Kompleksitas Memori | Kompleksitas Waktu | Cache Locality | Kapan Digunakan | Kapan Dihindari |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dynamic Growth (`c()`)** | $\mathcal{O}(N^2)$ | $\mathcal{O}(N^2)$ | Buruk (Fragmentasi Heap) | **Jangan pernah digunakan** di produksi | Data dinamis berukuran $N > 100$ |
| **Pre-allocated `for` loop** | $\mathcal{O}(N)$ | $\mathcal{O}(N)$ (Tinggi di overhead interpreter) | Sedang | State-dependent loop (misal: simulasi AR(1), MCMC) | Operasi independen element-wise |
| **Vektorisasi Murni (C)** | $\mathcal{O}(N)$ | $\mathcal{O}(N)$ (Mendekati bare-metal C) | Optimal (Contiguous, SIMD vectorization) | Transformasi data masif, operasi matematika, filtering | Algoritma yang membawa dependensi state rekursif |
| **List Mapping (`lapply`)** | $\mathcal{O}(N)$ | $\mathcal{O}(N)$ + pointer lookup | Rendah (Pointer chasing, memory scattered) | Data heterogen, operasi per-model, struktur hierarkis | Operasi komputasi numerik primitif |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. `NA` vs `NaN` vs `NULL`
*   `NA` (*Not Available*): Sentinel value untuk missing data; memiliki tipe data bawaan (`NA_integer_`, `NA_real_`, `NA_character_`). Ukuran panjangnya tetap $1$.
*   `NaN` (*Not a Number*): Standar IEEE 754 floating-point, selalu bertipe `double`. Operasi `is.na(NaN)` mengembalikan `TRUE`, namun `is.nan(NA)` bernilai `FALSE`.
*   `NULL`: Objek kosong berukuran panjang $0$ (`length(NULL) == 0`) dari tipe data `NULSXP`. Menggunakan `NULL` di dalam atomic vector akan mengabaikannya secara senyap (`c(1, NULL, 3)` menjadi `c(1, 3)`).

### 2. Evaluasi Vektor Boolean Kosong dalam Kondisional
Pernyataan `if (x > 0)` akan melemparkan kesalahan fatal:
`Error in if (x > 0) {: argument is of length zero` jika `x` adalah `numeric(0)`. Pastikan selalu mengevaluasi panjang atau menggunakan `all()` / `any()` dengan pertimbangan defensif:
```r
if (length(x) > 0 && !is.na(x[1]) && x[1] > 0) { ... }
```

### 3. Materialisasi ALTREP Secara Tidak Disengaja
Meneruskan rentang integer besar berbasis ALTREP langsung ke fungsi C-API lama yang memanggil `INTEGER(x)` alih-alih fungsi modern `DATAPTR_OR_NULL(x)` akan memaksa runtime mengalokasikan array fisik di background, mengubah konsumsi memori seketika dari 680 byte ke ratusan megabyte tanpa peringatan.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Penggunaan `1:length(x)` pada Objek Kosong
```r
# SALAH: Jika items bernilai NULL atau list(), loop mengeksekusi 1:0 (2 iterasi!)
items <- character(0)
for (i in 1:length(items)) {
  print(items[i]) # Mengakses items[1] (NA) dan items[0] (numeric(0))
}

# BENAR: seq_along selalu aman terhadap objek berdimensi nol
for (i in seq_along(items)) {
  print(items[i]) # Tidak dieksekusi sama sekali
}
```

### Kesalahan 2: Kehilangan Tipe Data Objek Karena `ifelse()`
Fungsi `base::ifelse()` melakukan koersi agresif dan menghilangkan atribut objek (seperti class `Date` atau `POSIXct` menjadi representasi numeric mentah).
```r
# SALAH
dates <- as.Date(c("2023-01-01", "2023-01-02"))
res <- ifelse(dates > as.Date("2023-01-01"), dates, dates - 1)
class(res) # [1] "numeric" -> Metadata Class Date Rusak!

# BENAR
res <- dates
mask <- dates <= as.Date("2023-01-01")
res[mask] <- dates[mask] - 1
class(res) # [1] "Date" -> Tetap Terjaga
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Suffix Eksplisit untuk Tipe Literal:** Selalu gunakan `100L` untuk integer dan `100.0` (atau `100`) untuk double. Hal ini mencegah overhead auto-coercion saat berinteraksi dengan API internal C atau library native.
2.  **Manfaatkan Matriks Bersebelahan untuk Operasi Numerik:** Jika data homogen 2-dimensi diproses, gunakan `matrix` murni alih-alih `data.frame`. `data.frame` secara internal adalah sebuah `list` of vectors; pemrosesan baris/kolomnya memicu *overhead pointer chasing*.
3.  **Audit Alokasi Memori Melalui `tracemem()`:** Pada modul kritis, gunakan built-in R diagnostic `tracemem(x)` untuk memastikan bahwa algoritma Anda tidak menduplikasi objek secara tersembunyi.
4.  **Terapkan Paradigma Deterministic Vector Typing:** Jangan biarkan tipe vektor berubah di tengah eksekusi fungsi. Biasakan menggunakan `vapply()` daripada `sapply()` guna menjamin proteksi tipe runtime (*type-safety contracts*).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Eksploitasi Mutasi In-Place
Untuk memastikan modifikasi vektor dilakukan secara *in-place* (tanpa alokasi memori tambahan), pastikan objek tidak memiliki alias referensi lain sebelum operasi:
```r
x <- numeric(1e7) # Alokasi 80 MB
lobstr::obj_addr(x)

# Mengurangi referensi ganda agar REFCNT bernilai 1
# Mutasi berikut dijamin in-place tanpa CoW
x[1] <- 9.5
lobstr::obj_addr(x) # Alamat identik, tidak ada overhead duplikasi memori
```

### 2. Pre-allocation Matrix / Vector
Hindari pertumbuhan dinamis array. Alokasikan struktur memori akhir terlebih dahulu:
```r
# Inefisien
out <- NULL
for (i in 1:1000) out <- rbind(out, compute_chunk(i))

# Optimal
out <- vector("list", 1000) # Pre-allocate 1000 pointer slots
for (i in 1:1000) out[[i]] <- compute_chunk(i)
final_mat <- do.call(rbind, out) # Single-pass binding
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### Validasi Boundary dan Type-Safety Assertion
Interpreter R secara otomatis mendaur ulang (*recycle*) vektor yang lebih pendek jika panjang operasi tidak seimbang. Pola ini berbahaya dalam komputasi finansial atau kriptografi:
```r
# KASUS BERBAHAYA: Silent Vector Recycling
balances <- c(100, 200, 300, 400)
deductions <- c(10, 20) # Terpotong, R otomatis me-recycle deductions menjadi c(10, 20, 10, 20)
res <- balances - deductions # Tidak ada error!

# IMPLEMENTASI AMAN (Hardened Safety Check)
safe_vector_subtract <- function(a, b) {
  if (!is.numeric(a) || !is.numeric(b)) {
    stop("TypeValidationError: Parameter harus berjenis numeric.")
  }
  if (length(a) != length(b)) {
    stop(sprintf(
      "DimensionMismatchError: Panjang vektor tidak identik (%d vs %d). Recycling dicegah.",
      length(a), length(b)
    ))
  }
  return(a - b)
}
```

### Mitigasi Komparasi Floating-Point
Jangan pernah menggunakan kesetaraan mutlak `==` untuk tipe data `double` karena batasan aproksimasi fraksional IEEE 754:
```r
# SALAH
(0.1 + 0.2) == 0.3 # FALSE!

# BENAR
isTRUE(all.equal(0.1 + 0.2, 0.3, tolerance = 1e-9))
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk mendeteksi duplikasi memori secara langsung di production/testing debugging session:

```r
# Aktifkan pelacakan alokasi memori
vec <- runif(5)
cat("Memulai pelacakan memori untuk objek 'vec':\n")
tracemem_tracker <- tracemem(vec)

# Memicu duplikasi memori melalui alias
alias_vec <- vec
alias_vec[1] <- 100 # Cetak log duplikasi otomatis dari engine C

# Nonaktifkan pelacakan
untracemem(vec)

# Menghitung jejak Garbage Collector
gc_stats <- gc(full = FALSE)
cat(sprintf("Node Memory GC Trigger: %.1f Mb, Vcells GC Trigger: %.1f Mb\n",
            gc_stats[1, 2], gc_stats[2, 2]))
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Atomic Vector:** Struktur array homogen contiguous; Logical (4B), Integer (4B), Double (8B), Character (8B ptr).
*   **Generic Vector (List):** Struktur pointer `SEXP` heterogen, rentan terhadap cache miss.
*   **Hierarki Koersi:** `logical` $\to$ `integer` $\to$ `double` $\to$ `character`.
*   **Copy-on-Write:** Duplikasi hanya terjadi saat mutasi nilai jika `REFCNT > 1`. Mutasi bersifat in-place jika `REFCNT == 1`.
*   **ALTREP:** Representasi abstrak sekuensial/berpola tanpa alokasi memori fisik sebelum dimaterialisasi.
*   **Golden Rule Performa R:** *Pre-allocate* seluruh objek target; hindari fungsi pertumbuhan array `c()`, `rbind()`, `cbind()` di dalam loop; andalkan loop native tingkat C via ekspresi tervektorisasi.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Berapa ukuran elemen individual dalam memori untuk tipe data integer primitif di R (`L` suffix), dan berapa elemen yang dialokasikan jika sebuah skalar diinisialisasi?**  
   *Jawaban:* 4 byte per elemen. Interpreter mengalokasikan atomic vector berdimensi $N=1$ yang dibungkus oleh struct `SEXPREC` (total memori $\approx 48-56$ byte, bukan 4 byte).

2. **Diberikan ekspresi `val <- c(TRUE, 10L, 0)`. Apakah tipe data akhir (`typeof`) dari `val`?**  
   *Jawaban:* `double` (`REALSXP`). Berdasarkan hierarki koersi: `logical` (TRUE) dan `integer` (10L) dinaikkan derajatnya ke kasta `double` mengikuti elemen `0` (yang secara default bertipe real/double).

3. **Mengapa penulisan `1:length(vec)` berisiko tinggi memicu logical bug dibanding `seq_along(vec)`?**  
   *Jawaban:* Jika `vec` kosong (`length == 0`), `1:length(vec)` menghasilkan sekuens `c(1, 0)` yang mengeksekusi loop sebanyak dua iterasi tak terduga. Sebaliknya, `seq_along(vec)` menghasilkan integer kosong berpanjang 0.

4. **Kapan tepatnya runtime R menyalin data secara fisik saat objek variabel diduplikasi (`y <- x`)?**  
   *Jawaban:* Duplikasi fisik tidak terjadi pada baris assignment, melainkan ditunda (*lazy evaluation*) sampai salah satu variabel (`x` atau `y`) memicu mutasi nilai sementara jumlah referensi (`REFCNT`) masih $> 1$.

5. **Apa fungsi utama dari fitur ALTREP yang diperkenalkan pada R versi 3.5.0?**  
   *Jawaban:* Menghindari alokasi buffer array fisik di RAM untuk data yang dapat diproyeksikan secara algoritmik (seperti deret matematika `1:1e9`), menghemat memori hingga gigabyte.

---

### Soal Tingkat Menengah (Intermediate)

6. **Secara arsitektural, mengapa komputasi berbasis `list` jauh lebih lambat dibanding komputasi `atomic vector` homogen ketika mengeksekusi kalkulasi matematis?**  
   *Jawaban:* Atomic vector menempati blok memori kontigu (*contiguous chunk*) yang ramah terhadap CPU cache lines dan memungkinkan optimasi SIMD. `list` hanyalah kumpulan pointer yang tersebar di heap (*scattered nodes*), memaksa CPU melakukan *pointer chasing* yang memicu lonjakan *L1/L2 cache misses*.

7. **Apa dampak pemanggilan `unclass()` terhadap konsumsi memori suatu S3 object besar di R? Apakah memori diduplikasi?**  
   *Jawaban:* Pemanggilan `unclass()` tidak menduplikasi data payload memori. Ini hanya memodifikasi atau mengabaikan atribut `class` yang tersimpan dalam pointer `*attrib` pada header `SEXPREC`, mempertahankan data array asli secara *zero-copy*.

8. **Mengapa pemanggilan fungsi `base::ifelse(cond, yes, no)` dapat merusak struktur objek berbasis class `Date` atau `POSIXct`?**  
   *Jawaban:* `ifelse()` secara internal membangun vektor baru menggunakan indexing atomic primitif tanpa memetakan atribut S3 (`class`) dari argumen input ke array keluaran, mengubah representasi tanggal menjadi angka integer/double epoch mentah.

9. **Jelaskan mekanisme bagaimana mutasi in-place dapat gagal dan kembali ke Copy-on-Write saat kita memodifikasi dataframe kolom-per-kolom!**  
   *Jawaban:* Sebuah dataframe adalah list of vectors. Jika dataframe tersebut atau vektor kolom di dalamnya memiliki alias lain (misal dievaluasi di dalam fungsi atau disimpan sementara ke variabel lokal), referensi kolom memiliki `REFCNT > 1`. Akibatnya, pembaruan satu kolom memicu penggandaan seluruh vektor kolom tersebut.

10. **Bagaimana cara interpreter merepresentasikan nilai `NA` secara fisik pada vektor `integer` di balik layar?**  
    *Jawaban:* Interpreter R memetakan `NA` integer ke konstanta integer 32-bit terkecil yang valid di arsitektur two's complement, yaitu `INT_MIN` (-2.147.483.648). Setiap komputasi integer memverifikasi nilai ini sebagai sentinel missing value.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek:
Rancang dan bangun modul R berkinerja tinggi: **"Zero-Copy Rolling Window Moving Average Engine"**.

### Kebutuhan Fungsional & Spesifikasi Sistem:
1.  **Engine:** Bangun fungsi `rolling_mean_engine(x, window_size)` dari *scratch* tanpa pustaka pihak ketiga (seperti `Rcpp`, `zoo`, `TTR`, atau `data.table`).
2.  **Efisiensi Memori (Constraint):** 
    *   Panjang input vektor data: $N = 10.000.000$ (10 juta elemen `double`).
    *   Engine **DILARANG KERAS** menggunakan manipulasi `c()`, `append()`, atau sub-setting window dinamis seperti `x[i:(i+window-1)]` di dalam loop (karena slicing memicu alokasi memori berulang $\mathcal{O}(W)$ pada setiap langkah).
3.  **Algoritma:** Terapkan teknik akumulasi selisih inkremental (Welford / sliding delta) dengan kompleksitas waktu $\mathcal{O}(N)$ linier murni:

$$S_k = S_{k-1} + X_k - X_{k-W}$$

4.  **Batas Memori Alokasi Tambahan:** Maksimum alokasi memori baru tidak boleh melampaui **1 kali alokasi vektor output** ($N - W + 1 \times 8\text{ byte} \approx 80\text{ MB}$).
5.  **Verifikasi Observabilitas:** Gunakan `tracemem()` dan `lobstr::obj_addr()` untuk membuktikan bahwa tidak terjadi lonjakan duplikasi memori sementara selama siklus kalkulasi berjalan. Bandingkan latensi eksekusinya melawan implementasi naive looping windowing!