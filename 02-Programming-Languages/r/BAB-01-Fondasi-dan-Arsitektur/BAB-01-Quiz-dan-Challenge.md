# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Sistem & Arsitektur Runtime R**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Struktur Data Internal `SEXPREC`:**
   Di dalam *source code* GNU R (C core), semua objek R direpresentasikan oleh pointer bertipe `SEXP` yang menunjuk ke struct `SEXPREC`. Jelaskan anatomi dari struct `SEXPREC`, termasuk komponen `sxpinfo` (header bits: tipe data, garbage collection mark bit, reference count level), pointer atribut (`ATTRIB`), serta pointer objek pengikat (`CAR`/`CDR` atau data payload). Mengapa abstraksi univariat ini memungkinkan dynamic typing namun memperkenalkan memory overhead per-objek?

2. **Evolusi Semantik Memory: `NAMED` vs Reference Counting (`REFCNT`):**
   R beralih dari mekanisme heuristik `NAMED` (skala 0, 1, 2) ke *true reference counting* (`REFCNT`) sejak R 3.1+. Jelaskan bagaimana runtime R mengevaluasi apakah sebuah vektor harus diduplikasi (*Copy-on-Write*) atau dapat dimodifikasi langsung di memori (*modify-in-place* / *mutation*) saat pemanggilan operator assignment subsetting (contoh: `x[1] <- 42`). Apa kondisi pasti di mana CoW tidak dapat dihindari?

3. **Arsitektur Dual-Heap Garbage Collector (Vcells vs Ncells):**
   Garbage Collector (GC) pada runtime R mengelola memori melalui dua pool terpisah: *Cons Cells* (`Ncells`) dan *Vector Cells* (`Vcells`). Jelaskan perbedaan peruntukan alokasi memori antara `Ncells` dan `Vcells`. Bagaimana algoritma *generational mark-and-sweep* (Generasi 0, 1, dan 2) R memanfaatkan struktur ini untuk menyeimbangkan *latency* eksekusi dengan *throughput* pembersihan memori?

4. **Framework ALTREP (Alternative Representations):**
   Diperkenalkan pada R 3.5, bagaimana arsitektur ALTREP mengubah interaksi runtime R dengan koleksi data masif? Analisis bagaimana operasi seperti `1:1e9` dapat diinisialisasi secara instan dengan jejak memori mendekati $O(1)$ byte, dan bagaimana integrasi ALTREP dengan memori terpetakan (*memory-mapped files* via `mmap`) merevolusi *zero-copy data ingestion*.

5. **Siklus Hidup Eksekusi: Dari R Code ke Byte-Code Engine:**
   Jelaskan transformasi kode R mulai dari *Lexing/Parsing* (pembentukan AST dalam bentuk Pairlist/Language Object), tahapan kompilasi via package `compiler` ke *Byte-code Object*, hingga interpretasi oleh *Virtual Machine* berbasis stack internal R. Apa peran *JIT compilation levels* (0 hingga 3) dalam menentukan kapan AST dievaluasi secara langsung (*AST-walking interpreter*) versus dieksekusi melalui VM byte-code?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Mutasi Heap Menggunakan `.Internal(inspect())` dan `tracemem()`:**
   Diberikan cuplikan kode berikut:
   ```r
   x <- 1:5
   tracemem(x)
   y <- x
   y[1] <- 10L
   ```
   Gunakan pemahaman internal engine untuk menjelaskan transisi nilai `REFCNT` dan alamat heksadesimal pointer `x` dan `y` di setiap baris. Kapan tepatnya duplikasi terjadi, dan mengapa jika `x <- 1:5` diganti dengan `x <- c(1L, 2L, 3L, 4L, 5L)` perilaku duplikasi awal pada baris pertama dapat berbeda akibat ALTREP compact sequence vs uncompressed integer vector?

2. **C API Memory Safety: Diagnostik `protection stack overflow`:**
   Pada integrasi native C via `.Call`, pengembang sering menemui error fatal: `Error: protection stack overflow`.
   * Jelaskan mekanisme kerja pointer *Protection Stack* (`PROTECT` dan `UNPROTECT`) di R C API.
   * Apa konsekuensi struktural jika pengembang memanggil `PROTECT` berulang kali dalam sebuah *loop* iterasi 1.000.000 elemen tanpa melepaskannya?
   * Kapan teknik `PROTECT_WITH_INDEX` atau `UNPROTECT_PTR` harus digunakan dibandingkan `UNPROTECT(n)` standar?

3. **Memory Leaks Akibat Closure & Enclosing Environment (`ENVSXP`):**
   Sebuah fungsi generator memuat dataset berukuran 4 GB, memfilter datanya, dan mengembalikan fungsi prediksi kecil:
   ```r
   train_model <- function() {
     large_df <- data.frame(matrix(rnorm(1e8), ncol = 10))
     model_param <- mean(large_df$X1)
     function(new_data) { new_data * model_param }
   }
   predict_fn <- train_model()
   ```
   Meskipun `large_df` tidak lagi dibutuhkan setelah `train_model()` selesai dieksekusi, memori 4 GB tidak pernah dibebaskan oleh Garbage Collector R. Bedah arsitektur `ENVSXP` (Environment SEXP) dan *lexical scoping rules* yang menyebabkan dependensi memori ini, serta tunjukkan solusi deterministik untuk mengisolasi environment closure tanpa menduplikasi objek runtime.

4. **Byte-code Deoptimization & Dynamic Lookup Hazards:**
   R VM byte-code compiler mengasumsikan stabilitas binding global pada runtime. Namun, operasi non-standar tertentu dapat membatalkan (*deoptimize*) instruksi byte-code secara instan dan memaksa fallback ke *slow-path dynamic lookup*. Jelaskan bagaimana instruksi seperti `eval()`, `assign()`, manipulasi `parent.frame()`, atau pemanggilan fungsi S3 generic dengan *unregistered methods* merusak performa *compiled loops* di R VM.

5. **Anatomi Promise Object (`PROMSXP`) dan Lazy Evaluation Edge-Cases:**
   Argumen fungsi di R tidak langsung dievaluasi, melainkan dibungkus dalam `PROMSXP` yang memuat tiga slot: *Value*, *Expression*, dan *Environment*.
   * Jelaskan apa yang terjadi pada memori ketika sebuah promise dievaluasi untuk pertama kalinya (*forcing the promise*).
   * Debug skenario klasik *promise leakage*: Apa bahaya laten mengevaluasi argumen default yang saling merujuk secara siklikal (contoh: `f <- function(a = b, b = a) a`), dan bagaimana engine R mendeteksi serta memutus rekursi tak berhingga (*promise cycle detection*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM pada Pipeline Data Skala Besar
Sebuah microservice R terjadwal di Kubernetes (Resource Limit: 32 GB RAM) mengalami crash *Out-Of-Memory* (OOMKilled) secara acak saat memproses data log berukuran 12 GB. Pipeline tersebut mengeksekusi operasi:
```r
data <- read.csv("access_log.csv") # Menghasilkan dataframe ~12GB di RAM
data$status_group <- ifelse(data$status >= 400, "ERROR", "SUCCESS")
data <- data[data$status_group == "ERROR", ]
```
Metrik pod menunjukkan konsumsi memori melonjak hingga melampaui 32 GB tepat saat pemanggilan `ifelse()`.
* **Pertanyaan Diagnostik:**
  1. Bedah alokasi memori internal: Mengapa kombinasi pemanggilan `data$status_group <- ...` dan fungsi `ifelse()` vektor memicu lonjakan penggunaan memori hingga 3x lipat dari ukuran asli objek dataframe?
  2. Bagaimana modifikasi arsitektural berbasis *in-place vector assignment*, optimalisasi struktur data via package berbasis C (`data.table` atau Arrow/DuckDB), dan intervensi GC manual (`gc(verbose = FALSE)`) dapat menekan footprint memori stabil di bawah 15 GB?

### Skenario B: Degradasi Fork-Safe Concurrency pada `parallel::mclapply`
Sebuah sistem *scoring* risiko kredit memproses jutaan transaksi per jam di Linux bare-metal (64 core) menggunakan `parallel::mclapply(data_splits, score_function, mc.cores = 32)`. Berdasarkan prinsip kernel POSIX `fork()`, semua *child processes* seharusnya berbagi *page table* memori yang sama (*Copy-on-Write* transparan) dari *parent process* yang menyimpan matriks referensi 16 GB. Namun, sesaat setelah pemrosesan berjalan, *swap space* server langsung penuh, utilisasi CPU anjlok ke I/O wait, dan server mengalami *thrashing*.
* **Pertanyaan Diagnostik:**
  1. Mekanisme internal R apa yang secara diam-diam memodifikasi objek di memori parent meskipun kode fungsi scoring hanya melakukan operasi "read-only"? (Petunjuk: Analisis operasi GC mark phase, reference count updating saat pembacaan objek, dan lazy promise evaluation di dalam child process).
  2. Bagaimana Anda mendesain ulang arsitektur komputasi konkuren ini—misalnya beralih ke *shared-memory matrix pointer* (`bigmemory`), *socket clusters* terisolasi, atau offloading scoring engine ke native dynamic shared library (C++)—untuk menjamin *true zero-copy parallel processing*?

### Skenario C: Latency Spikes Akibat GC Pauses pada Real-Time API
Sebuah API berbasis R Plumber melayani inferensi model Machine Learning dengan target SLA $P_{99} < 50\text{ ms}$. Secara historis, $P_{50}$ berjalan sangat cepat (8 ms), namun grafik latency menunjukkan *spike* periodik setiap beberapa menit di mana respons melonjak hingga 450 ms. Investigasi metrik memverifikasi bahwa lonjakan latensi berkorelasi langsung dengan fase eksekusi *Full Garbage Collection* (Generasi 2) oleh R runtime.
* **Pertanyaan Diagnostik:**
  1. Apa pemicu struktural yang menyebabkan R GC memutuskan untuk melakukan *Full Collection* alih-alih *Incremental Collection*, dan bagaimana alokasi *short-lived intermediate vectors* di dalam endpoint JSON deserializer memperparah masalah ini?
  2. Bagaimana Anda mengonfigurasi parameter environment engine R (seperti `R_GC_MEM_INIT`, flag heap limits), teknik *object pre-allocation*, serta arsitektur memory pool recycling untuk mengeliminasi GC pause latency spikes pada layer produksi?

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Copy Structural Diagnostic Harness & Heap Allocator Tracker
**Deskripsi Masalah:**
Dalam sistem pemrosesan batch berperforma tinggi, duplikasi data tak terlihat (*hidden allocations*) adalah musuh utama performa. Anda ditugaskan membangun harness instrumentasi internal di R yang mampu melacak siklus hidup memori objek secara *real-time* tanpa mengganggu kestabilan runtime.

**Requirements:**
1. Bangun fungsi R murni atau hybrid C API (menggunakan `inline` atau `Rcpp`) bernama `inspect_lifecycle(expr)`:
   * Mampu menangkap ekspresi R arbitrer.
   * Menghitung delta alokasi `Ncells` dan `Vcells` sebelum dan sesudah eksekusi tanpa memicu *full GC*.
   * Mengaudit apakah objek target mengalami *in-place mutation* atau *copy-on-write* (evaluasi alamat pointer C asli dari `DATAPTR(x)`).
2. Buat custom wrapper class berbasis ALTREP sederhana (atau demonstrasikan via `tracemem` low-level binding) yang memvalidasi bahwa sub-setting slicing data 10 juta integer (`x[1:1000]`) tidak mengalokasikan vektor baru di heap `Vcells`.
3. Deteksi potensi memory leak pada closure: Buat validator `audit_closure_env(fn)` yang mengekstrak environment fungsi closure, mendaftar semua simbol yang terikat, serta memperingatkan jika ada simbol dengan alokasi memori di atas ambang batas (threshold) yang tidak pernah dipanggil di dalam fungsi body AST.

**Constraints:**
* Dilarang menggunakan package profiling eksternal level tinggi (seperti `profvis` atau `bench`) untuk core profiler engine—manfaatkan direktif base R: `gc(reset = TRUE)`, `.Internal()`, `tracemem()`, serta native pointer extraction via `pryr` atau C helper sederhana.
* Memory overhead dari *diagnostic harness* tidak boleh melebihi $5\%$ dari total footprint ekspresi yang diuji.

**Expected Output:**
Output cetak terstruktur dari profiler:
```text
=== R RUNTIME MEMORY AUDIT REPORT ===
Target Expression : data[idx] <- data[idx] * 2L
Memory Strategy   : MODIFY-IN-PLACE (Refcnt: 1 -> 1)
Pointer Hex Addr  : [PRE: 0x55a9c8f12040] -> [POST: 0x55a9c8f12040]
GC Pressure Delta : Ncells: +12 | Vcells: 0
Execution Status  : ZERO-COPY CONFIRMED
ALTREP Active     : FALSE
Closure Leak Risk : PASSED (No unbounded symbols in enclosing scope)
=====================================
```

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi struktur data C internal R (`SEXPREC`, `sxpinfo`, dan variasi tipe SEXP seperti `INTSXP`, `REALSXP`, `VECSXP`, `ENVSXP`).
- [ ] Mekanisme deteksi duplikasi memori: evolusi dari sistem `NAMED` ke Reference Counting (`REFCNT`) dan implementasi Copy-on-Write (CoW).
- [ ] Arsitektur Garbage Collector R: perbedaan fungsi serta alokasi `Ncells` (node) dan `Vcells` (vector heap), serta hirarki Generasi GC 0, 1, dan 2.
- [ ] Peran dan mekanisme ALTREP (Alternative Representations) dalam eliminasi alokasi data memori masif dan abstraksi pointer I/O.
- [ ] Mekanisme kerja promise (`PROMSXP`), lazy evaluation, dan konsekuensinya terhadap eksekusi fungsi serta call stack.
- [ ] Alur kerja lexical scoping R di level pointer: bagaimana frame environment saling terikat secara hierarkis melalui `ENVSXP` parent links.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik konstanta enum tipe SEXP di C source header R (misal: `INTSXP = 13`, `REALSXP = 14`, dst.).
- [ ] Formula matematis pasti internal kernel R untuk ambang batas *GC trigger dynamic growth factor*.
- [ ] Ratusan macro internal helper C API R yang usang atau deprecated (cukup kuasai pola modern: `PROTECT`, `UNPROTECT`, `DATAPTR`, `allocVector`).

### Saya harus bisa melakukan:
- [ ] Menelusuri mutasi dan duplikasi objek secara empiris menggunakan instrumen debugging low-level seperti `tracemem()`, `untracemem()`, dan inspeksi pointer memori.
- [ ] Mengidentifikasi dan memitigasi memory leak yang disebabkan oleh closure yang menahan pointer ke enclosing environment masif.
- [ ] Menulis integrasi dasar R C API menggunakan pola proteksi pointer yang bebas dari *protection stack overflow* dan *dangling pointers*.
- [ ] Mendiagnosis penyebab bottleneck memory footprint pada eksekusi kode paralel berbasis `fork()` (`mclapply`) di sistem operasi berbasis Unix/Linux.
- [ ] Mengoptimalkan kode R idiomatik agar mengeksekusi *modify-in-place* alih-alih memicu CoW yang merusak throughput komputasi.