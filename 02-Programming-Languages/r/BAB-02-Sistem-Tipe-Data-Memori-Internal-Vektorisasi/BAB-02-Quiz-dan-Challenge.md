# BAB 02: Quiz, Challenge, & Knowledge Check
**Sistem Tipe Data, Memori Internal, & Vektorisasi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi SEXP dan Alokasi Memori Vektor Kontigu
Jelaskan secara struktural bagaimana R merepresentasikan *atomic vector* (seperti `INTSXP` atau `REALSXP`) dibandingkan dengan *generic vector* / `list` (`VECSXP`) pada level implementasi C internal (`SEXPREC`). Mengapa struktur internal ini menghasilkan perbedaan drastis pada *cache locality* dan efisiensi memori ketika dilakukan iterasi komputasi skala besar?

### Soal 1.2: Rantai Koersi Implisit (Implicit Coercion Hierarchy)
R memiliki aturan koersi hierarkis: `raw` $\rightarrow$ `logical` $\rightarrow$ `integer` $\rightarrow$ `double` $\rightarrow$ `complex` $\rightarrow$ `character`. 
1. Apa mekanisme internal yang terjadi pada buffer memori saat sebuah elemen bertipe `character` disisipkan ke dalam sebuah `REALSXP` berukuran 10 juta elemen?
2. Mengapa koersi implisit dari `integer` ke `double` umumnya bersifat *lossless*, sedangkan koersi dari `double` ke `integer` tidak hanya berisiko *truncation* tetapi dapat memicu nilai `NA`?

### Soal 1.3: Arsitektur Nilai Khusus: Representasi Internal `NA` vs `NaN`
R membedakan missing value (`NA`) berdasarkan tipe datanya (`NA_integer_`, `NA_real_`, `NA_character_`). 
1. Bagaimana R merepresentasikan `NA_integer_` pada tingkat representasi biner 32-bit (kaitkan dengan batasan representasi `INT_MIN`)?
2. Bagaimana standar IEEE 754 *floating-point* dimanipulasi oleh R untuk membedakan antara nilai aritmatika `NaN` (*Not a Number*) dan missing value `NA_real_`?

### Soal 1.4: Esensi Kompilasi Primitif vs Vektorisasi Sintaktis
Banyak pemrogram pemula menganggap fungsi keluarga `apply` (`lapply`, `sapply`, `vapply`) adalah "vektorisasi sejati". 
1. Mengapa `lapply` secara teknis tetap merupakan *interpreted loop* pada level byte-code R dan bukan vektorisasi level perangkat keras?
2. Bandingkan arsitektur eksekusi `lapply` tersebut dengan fungsi primitif C berstatus `.Internal` atau `.Primitive` (seperti operator `+` atau fungsi `colSums`) dalam kaitannya dengan *Single Instruction, Multiple Data* (SIMD) dan *loop unrolling*.

### Soal 1.5: Arsitektur ALTREP (Alternative Representations)
Sejak R versi 3.5.0, mekanisme ALTREP diperkenalkan untuk mengoptimalkan representasi objek di memori.
1. Bagaimana ALTREP mengalokasikan objek ekspresi sekuensial seperti `x <- 1:1e9` sehingga hanya mengonsumsi beberapa byte memori alih-alih ~4 GB?
2. Sebutkan dua kondisi atau operasi mutasi yang dapat memaksa objek ALTREP mengalami *materialization* (alokasi memori riil secara penuh ke dalam heap R).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Pelacakan Modifikasi In-Place dan Mekanisme `REFCNT`
Perhatikan cuplikan kode eksekusi berikut:
```r
library(lobstr)
x <- runif(1e7) # ~80 MB REALSXP
tracemem(x)
ref_x <- obj_addr(x)

# Kasus A
x[1] <- 42.0

# Kasus B
y <- x
x[2] <- 84.0
```
Analisis status *reference count* (`REFCNT` / penanda kepemilikan memori) pada Kasus A dan Kasus B. Pada kasus mana R melakukan mutasi *in-place* ($O(1)$ overhead memori tambahan) dan pada kasus mana R terpaksa memicu *Copy-on-Write* (CoW) penuh ($O(N)$ alokasi buffer baru)? Sertakan verifikasi perubahan alamat memori menggunakan konsep `tracemem()`.

### Soal 2.2: Degradasi Performa Akibat Atribut dan "Dimension Dropping"
Diberikan sebuah matriks numerik besar `M` berukuran $10000 \times 10000$.
```r
M <- matrix(rnorm(1e8), nrow = 10000, ncol = 10000)
row_means <- numeric(10000)
for (i in 1:10000) {
  row_means[i] <- mean(M[i, ]) # Evaluasi baris ini
}
```
1. Jelaskan secara memori mengapa slicing `M[i, ]` tanpa argumen `drop = FALSE` memicu alokasi memori berulang untuk pembuatan vektor `REALSXP` baru di setiap iterasi.
2. Mengapa akses data baris pada matriks R berbasis *column-major order* (Fortran-style) mengakibatkan *cache miss* (L1/L2/L3) yang jauh lebih tinggi dibandingkan akses per kolom `M[, j]`?

### Soal 2.3: Intersepsi Batas Presisi Integer 32-bit dan Eskalasi Tipe
Jelaskan output dari urutan operasi berikut secara presisi:
```r
int_val <- .Machine$integer.max # 2147483647L
typeof(int_val)                 # [1] "integer"

res1 <- int_val + 1L
typeof(res1)                    # Apa outputnya? Mengapa?

res2 <- int_val + 1
typeof(res2)                    # Apa outputnya? Mengapa?
```
Bagaimana sistem runtime R mendeteksi *integer overflow* dan mengapa perilakunya berbeda antara penambahan dengan literal `1L` vs literal numerik default `1`?

### Soal 2.4: Shallow Copy vs Deep Copy pada Struktur Data Campuran
Diberikan sebuah `list` kompleks:
```r
large_vec <- rnorm(1e7)
my_list <- list(a = large_vec, b = 1:1000)
modified_list <- my_list
modified_list$b[1] <- 999L
```
1. Apakah modifikasi terhadap `modified_list$b` menyebabkan seluruh `large_vec` pada `modified_list$a` diduplikasi di memori fisik? Buktikan dengan konsep *shallow copy* pada representasi array pointer `VECSXP`.
2. Apa yang terjadi jika kita mengeksekusi `modified_list$a[1] <- 0.0`? Objek mana yang terisolasi dan bagaimana pemisahan alamat memori dilakukan?

### Soal 2.5: Identifikasi Bottleneck dan Memory Leak Semu pada String Pool
R menggunakan arsitektur *Global String Pool* (`CHARSXP`) untuk menyimpan semua elemen karakter secara *immutable* dan *deduplicated*.
Jelaskan bagaimana pemrosesan jutaan string unik yang dibaca dari parsing log file (misalnya GUID/UUID acak) dapat menyebabkan memori R (`Vsize` dan `Nsize`) membengkak drastis dan tidak kunjung turun meskipun fungsi Garbage Collector (`gc()`) telah dieksekusi secara manual.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Garbage Collection Thrashing pada Batch Data Pipelines
Sebuah pipeline ingest data finansial memproses 500 file CSV berukuran masing-masing ~200 MB per batch. Rekayasawan data menulis fungsi pemrosesan dengan pendekatan iteratif akumulatif menggunakan `data.frame` standar:

```r
master_data <- data.frame()
for (file in file_list) {
  chunk <- read.csv(file)
  chunk_clean <- chunk[chunk$volume > 0, ]
  chunk_clean$processed_time <- Sys.time()
  
  # Agregasi ke master data frame
  master_data <- rbind(master_data, chunk_clean)
}
```

*Gejala Produksi:*
Pada 10 file pertama, proses berjalan secepat ~1 detik per file. Namun, ketika mencapai file ke-100, pemrosesan melambat menjadi ~45 detik per file. Monitor sistem menunjukkan utilisasi CPU 100% pada satu core, alokasi RAM melonjak eksponensial hingga 64 GB OOM (*Out of Memory*), dan waktu eksekusi didominasi oleh operasi *Garbage Collection* (`gc()` thrashing).

*Pertanyaan Diagnostik:*
1. Bedah secara mekanistis mengapa operasi `rbind()` berulang memicu kompleksitas waktu kuadratik $O(N^2)$ dan alokasi memori beruntun terkait aturan *Copy-on-Write* (CoW) dan fragmentasi heap SEXP!
2. Bagaimana Anda merancang ulang arsitektur pipeline pemrosesan ini dari sudut pandang *memory allocation footprint* dengan tetap memanfaatkan kapabilitas alokasi berbasis tipe data dasar atau struktur vektor kontigu berdimensi tetap?

---

### Skenario B: Silent Coercion & Financial Precision Hazard
Sebuah sistem audit transaksi kliring memproses file transaksi multivaluta harian. Salah satu data mentah memiliki anomali di mana beberapa record nominal transaksi memuat simbol pemisah desimal berupa koma atau teks status:

```r
raw_transactions <- c("10500.50", "9400.25", "ERR_INVALID", "125000.00")
```

Junior engineer mengeksekusi pipeline pembersihan dan perhitungan agregat:
```r
rates <- c(USD = 1.0, EUR = 1.08, JPY = 0.0067) # Named atomic vector
cleaned_tx <- ifelse(raw_transactions == "ERR_INVALID", 0, raw_transactions)
final_val <- cleaned_tx * rates["USD"]
```

*Gejala Produksi:*
Sistem tidak mengeluarkan *error* atau *warning* fatal, tetapi hasil mutasi pada unit pengujian menghasilkan `final_val` yang seluruhnya bernilai numerik salah, atau pada sub-sistem lain menghasilkan *runtime error*: `Error in cleaned_tx * rates["USD"] : non-numeric argument to binary operator`. Pada modul lain yang menggunakan `cbind()` dengan data numerik lain, sebuah data bernilai miliaran rupiah tiba-tiba berubah menjadi string tanpa peringatan.

*Pertanyaan Diagnostik:*
1. Mengapa fungsi `ifelse()` mengembalikan vektor bertipe `character` alih-alih `numeric` pada ekspresi `cleaned_tx <- ifelse(...)` di atas? Jelaskan berdasarkan *signature* dan mekanisme evaluasi nilai balik `ifelse()`.
2. Jelaskan risiko *silent coercion* saat matriks atau vektor atomik tercemar oleh 1 elemen string, dan susun pola validasi tipe data berbasis *fail-fast principle* menggunakan *type predicates* internal R (`is.double`, `is.integer`, `is.character`) yang deterministik sebelum vektorisasi diterapkan.

---

### Skenario C: Algorithmic Backtesting & L1/L2 Cache Invalidation
Sebuah sistem *algorithmic high-frequency trading* menghitung moving average eksponensial (EMA) terhadap 50 juta titik tick data transaksi per detik. Tim kuantitatif membandingkan tiga implementasi:

1. **Implementasi A:** Menggunakan native R for-loop dengan inisialisasi vektor target di awal (`numeric(5e7)`).
2. **Implementasi B:** Menggunakan `Reduce()` dengan argumen `accumulate = TRUE`.
3. **Implementasi C:** Operasi transformasi vektorisasi murni berbasis *lagged vectorized array arithmetic* menggunakan fungsi kompilasi C internal (`filter()` atau transformasi konvolusi C-level).

*Gejala Produksi:*
Implementasi A memakan waktu 4.5 detik. Implementasi B berjalan sangat lambat (>30 detik) dan menghabiskan memori berkali-kali lipat dari ukuran dataset. Implementasi C berjalan dalam 0.35 detik.

*Pertanyaan Diagnostik:*
1. Mengapa `Reduce(..., accumulate = TRUE)` memiliki jejak alokasi memori yang sangat buruk dibandingkan for-loop yang diinisialisasi secara tepat pada tipe data R? Jelaskan dari sisi alokasi linked-list intermediate SEXP.
2. Mengapa Implementasi C mampu mengeksploitasi kecepatan perangkat keras secara drastis? Kaitkan jawaban Anda dengan *CPU instruction pipelining*, penghindaran overhead evaluasi *promise/evaluator environment* R, dan kontinuitas buffer data di memori fisik (*contiguous memory stride*).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Zero-Copy Rolling Aggregator Engine
**Problem:**
Anda diminta membangun sebuah fungsi mesin agregasi data *rolling window* berukuran dinamis (misalnya window size $k = 1000$ baris) untuk data *tick* time-series sebesar 20.000.000 (20 juta) observasi bertipe `double` murni. Mesin ini harus menghitung metrik statistik (*Rolling Mean* dan *Rolling Sum*) dengan constraint performa level enterprise tanpa memanfaatkan paket pihak ketiga seperti `Rcpp`, `data.table`, atau `zoo`. Anda diwajibkan menggunakan kapabilitas intrinsik **Base R**.

**Requirements:**
1. **Zero-Allocation Loop:** Anda tidak boleh mengalokasikan memori baru di dalam siklus loop/iterasi. Semua buffer output harus dialokasikan di awal (*pre-allocated vector* bertipe `REALSXP`).
2. **Deterministic Mutation:** Modifikasi nilai output harus dilakukan langsung pada buffer target. Anda harus memverifikasi bahwa `tracemem()` tidak mencatat duplikasi objek (*copying*) selama loop berjalan.
3. **Vectorized Prefix-Sum Algorithm:** Algoritma internal harus mengimplementasikan pendekatan *cumulative sum / prefix sum* (menggunakan fungsi primitif C internal `cumsum()`) untuk mencapai kompleksitas waktu teoritis $O(N)$ secara keseluruhan, bukan $O(N \times k)$.
4. **Boundary & NA Handling:** Nilai dari indeks 1 hingga $k-1$ harus diisi secara deterministik dengan `NA_real_` (bukan tipe `NA` generik), dan penanganan batas array harus presisi.

**Constraints:**
- Runtime maksimal: **< 1.0 detik** untuk 20 juta baris data pada sistem single-core standar.
- Memory footprint maksimal: Penambahan alokasi RAM aktif tidak boleh melebihi **$1.1 \times$** ukuran vektor input (terverifikasi via `lobstr::mem_used()` atau pelacakan delta `gc()`).
- Dilarang memicu koersi tipe implisit sekecil apa pun (`integer` $\leftrightarrow$ `double`).

**Expected Output:**
Sebuah script R mandiri yang berisi:
1. Implementasi fungsi `fast_rolling_agg(x, k)`.
2. Blok validasi tipe data dan integritas argumen (*type safety check*).
3. Profiling benchmark menggunakan `system.time()` atau `bench::mark()` yang mencakup alokasi memori (`memory allocation`) dan pemanggilan Garbage Collector (`gc count`).
4. Output verifikasi visual yang membuktikan alamat memori vektor output tetap konstan sepanjang algoritma beroperasi.

---

## 5. Knowledge Check & Checklist

Pastikan Anda menguasai poin-poin krusial berikut sebelum melanjutkan ke modul berikutnya:

### Saya harus memahami:
- [ ] Struktur memori `SEXPREC` pada internal C R dan pemetaan tipe data atomik (`INTSXP`, `REALSXP`, `LGLSXP`, `STRSXP`, `RAWSXP`).
- [ ] Aturan presisi dan urutan koersi implisit serta biaya komputasional dari degradasi tipe data.
- [ ] Perbedaan fundamental antara nilai IEEE 754 `NaN`, `NA_real_`, dan representasi biner `INT_MIN` pada `NA_integer_`.
- [ ] Mekanisme kerja *Copy-on-Write* (CoW) dan cara kerja penanda referensi (`REFCNT` / `NAMED` tracking).
- [ ] Mengapa *vectorization* berbasis fungsi C-internal/primitif jauh mengungguli loop interpreter R dari sudut pandang *cache locality* dan instruksi CPU.
- [ ] Konsep ALTREP (*Alternative Representations*) dan implikasinya terhadap efisiensi memori runtime.

### Saya tidak perlu menghafal:
- [ ] Representasi exact bit mask IEEE 754 64-bit untuk floating point payloads di luar pemahaman konsep `NaN` vs `NA_real_`.
- [ ] Seluruh tabel C macro untuk manipulasi header SEXP (seperti `SET_VECTOR_ELT`, `DATAPTR`) kecuali berencana menulis R-extensions C murni.
- [ ] Nilai numerik integer internal dari enumerasi SEXP (`SEXPTYPE` numeric IDs seperti `REALSXP = 14`).

### Saya harus bisa melakukan:
- [ ] Memeriksa alamat memori aktual sebuah objek R dan mendeteksi penggandaan buffer menggunakan `tracemem()` dan `lobstr::obj_addr()`.
- [ ] Menganalisis alokasi memori sebuah pipeline data menggunakan `lobstr::mem_used()`, `lobstr::obj_size()`, atau `gc()`.
- [ ] Melakukan pra-alokasi (*pre-allocation*) buffer memori dengan tipe data yang tepat (`vector("double", n)`, `numeric(n)`, dsb.) untuk mencegah $O(N^2)$ CoW thrashing.
- [ ] Mengidentifikasi dan memitigasi anomali *silent coercion* dalam struktur data multidimensi atau pemrosesan batch data mentah.
- [ ] Mengonversi loop R berbasis iterasi skalar menjadi eksekusi vektorisasi murni berkinerja tinggi yang mengeksploitasi arsitektur perangkat keras modern.