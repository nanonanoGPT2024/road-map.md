# BAB 02: Quiz, Challenge, & Knowledge Check
**Data Structures, Control Flows, & Functional Semantics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Topologi Memori Vektor Atomik vs. Generic Vectors (Lists)
Secara internal pada runtime GNU R (C-level `SEXP`), jelaskan perbedaan mendasar alokasi memori antara sebuah *atomic vector* (misalnya `INTSXP` atau `REALSXP`) dan sebuah *generic vector* (`VECSXP` / `list`). Apa implikasinya terhadap *cache locality* saat melakukan iterasi sekuensial pada data berukuran 100 juta elemen?

### Soal 1.2: Anatomi S3 Factor dan Bahaya Implicit Coercion
Sebuah `factor` di R diimplementasikan sebagai integer vector dengan atribut `levels` bertipe character. 
1. Mengapa eksekusi `as.numeric(f)` pada sebuah factor `f <- factor(c("100", "20", "5"))` menghasilkan `c(2, 3, 1)` dan bukan nilai nominalnya?
2. Bagaimana mekanisme runtime R saat mengeksekusi operasi rekonsiliasi vektor `c(factor_a, factor_b)`? Mengapa operasi tersebut merusak struktur metadata kelasnya secara diam-diam (*silent degradation*)?

### Soal 1.3: Column-Major Layout & Memory Striding pada Matriks
R mengalokasikan matriks (`matrix`) dalam format *column-major order* contiguous memory block. Jika Anda memiliki matriks $M \in \mathbb{R}^{10000 \times 10000}$:
1. Tuliskan formula pemetaan linear address $Index_{1D}(i, j)$ untuk mengakses elemen baris ke-$i$ dan kolom ke-$j$ (berbasis 1-based indexing).
2. Dari perspektif arsitektur CPU L1/L2 data cache, jelaskan mengapa operasi komputasi per-kolom (`colSums(M)`) secara signifikan lebih cepat daripada komputasi per-baris (`rowSums(M)`) jika keduanya diimplementasikan via naive loop di level C.

### Soal 1.4: Semantika Evaluasi: `if` vs. `ifelse()` vs. `dplyr::if_else()`
Analisis perbedaan semantik eksekusi dan efisiensi memori antara konstruksi kontrol alur skalar `if (cond) a else b`, fungsi tervektorisasi base R `ifelse(test, yes, no)`, dan implementasi type-strict `dplyr::if_else(condition, true, false)`:
1. Mengapa `ifelse()` mengevaluasi kedua cabang (`yes` dan `no`) secara penuh terlepas dari kondisi boolean pada `test` (*eager dual-branch evaluation*)?
2. Apa dampak fenomena tersebut jika cabang `yes` atau `no` melibatkan komputasi berat atau operasi ber-side effect?

### Soal 1.5: Dekonstruksi S3 Data Frame: List-of-Vectors Contract
`data.frame` secara fundamental adalah sebuah `list` dengan atribut kelas `"data.frame"` dan atribut khusus `"row.names"`.
1. Jelaskan aturan invariansi (*invariant rules*) yang harus dipenuhi oleh setiap elemen di dalam list tersebut agar integritas struktur data frame tetap valid.
2. Jelaskan bahaya operasi pengindeksan `df[, 1]` pada base R vs. `tibble[, 1]` dalam konteks *dimension dropping* (`drop = TRUE` default behavior) dan bagaimana hal ini dapat menyebabkan *runtime crash* pada pipeline produksi downstream yang mengasumsikan input 2-dimensi.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Copy-on-Write (CoW), REFCNT, dan Memory Duplication
Perhatikan cuplikan kode R 4.0+ berikut:

```R
library(lobstr)

x <- runif(1e7) # ~80 MB
obj_addr(x)

tracemem(x)
y <- x
x[1] <- 42.0
untracemem(x)
```

1. Jelaskan bagaimana mekanisme tracking referensi internal R (`NAMED` vs `REFCNT` tracking mechanism yang diperkenalkan pada R modern) menentukan kapan memori harus diduplikasi via *deep copy*.
2. Pada baris ke berapa memori baru dialokasikan? Jika sebelum modifikasi dilakukan eksekusi `rm(y); gc()`, apakah operasi `x[1] <- 42.0` tetap memicu CoW? Jelaskan kondisi internal yang menentukan keputusan runtime tersebut.

### Soal 2.2: The Mechanics of Lazy Evaluation & Promise Objects
Argumen fungsi dalam R tidak dievaluasi saat pemanggilan (*call-time*), melainkan dibungkus dalam struktur internal `PROMSXP` (*Promise*).
1. Sebutkan tiga komponen utama penyusun sebuah objek `PROMSXP`.
2. Jelaskan *edge-case* berikut: Apa yang dicetak oleh fungsi di bawah ini, dan mengapa pemanggilan tersebut tidak melempar error *object not found*?

```R
f <- function(a = b, b = 2) {
  b <- 10
  return(a * b)
}
f()
```

### Soal 2.3: Structural Scoping: List vs. Environment Memory Traversal
Secara konseptual, baik `list` maupun `environment` dapat bertindak sebagai *key-value associative store*.
1. Jelaskan perbedaan topologi keduanya di memori: Mengapa modifikasi nilai di dalam `environment` memiliki *reference semantics* (in-place modification tanpa CoW), sedangkan modifikasi elemen `list` tunduk pada batasan *value semantics*?
2. Bagaimana struktur algoritma pencarian key (*lookup time complexity*) pada sebuah environment jika dibandingkan dengan list dengan $N$ elemen ($N > 10^5$)?

### Soal 2.4: Closure Memory Leaks via Lexical Enclosures
Fungsi di R mengikat *enclosing environment*-nya saat didefinisikan (*closure*). Analisis potongan kode berikut:

```R
create_accumulator <- function() {
  large_blob <- readBin(raw(), n = 5e8) # ~500 MB Raw Vector
  counter <- 0
  
  function(inc = 1) {
    counter <<- counter + inc
    counter
  }
}

acc <- create_accumulator()
```

Meskipun fungsi anonim yang dikembalikan tidak pernah mengakses `large_blob`, objek `large_blob` tidak dapat dibersihkan oleh Garbage Collector (`gc()`). Mengapa hal ini terjadi di level *environment binding*, dan bagaimana cara merefaktor fungsi `create_accumulator` agar memori `large_blob` dapat langsung direklamasi setelah factory function selesai dieksekusi tanpa merusak fungsionalitas `counter`?

### Soal 2.5: Functional Dispatch: `lapply` vs. `sapply` vs. `vapply`
Dalam arsitektur pipeline data enterprise:
1. Mengapa penggunaan `sapply()` dilarang keras pada kode produksi misi-kritis (*mission-critical systems*)?
2. Dari segi *type safety*, *memory pre-allocation*, dan interaksi dengan R Byte-code Compiler (`compiler::cmpfun`), jelaskan keunggulan komparatif implementasi internal `vapply()` dibandingkan dengan `lapply()` yang diikuti oleh `do.call(rbind, ...)` atau `unlist()`.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Out-Of-Memory Death Spiral via Iterative Binding
Sebuah microservice batch processing R dijalankan di container Kubernetes (Memory Limit: 16 GB). Service ini bertugas mengonsumsi 5 juta record log transaksi per jam via REST API, memprosesnya dalam chunk per 10.000 row, dan mengakumulasikannya ke dalam satu data frame analitik.

Kode yang ditulis oleh developer sebelumnya:

```R
process_stream <- function(chunks) {
  master_df <- data.frame()
  
  for (i in seq_along(chunks)) {
    chunk_df <- fetch_and_clean_chunk(chunks[[i]]) # Mengembalikan data.frame 10,000 x 20
    master_df <- rbind(master_df, chunk_df)
    message(sprintf("Processed chunk %d", i))
  }
  
  return(master_df)
}
```

**Insiden:** Pada iterasi ke-250, CPU utilitas melonjak ke 100%, throughput anjlok dari 50 chunk/detik menjadi < 1 chunk/detik, dan container akhirnya mengalami termination akibat *OOMKilled* (Exit Code 137), meskipun total ukuran data bersih sebenarnya hanya ~1.2 GB.

**Tugas Diagnostik Anda:**
1. **Root Cause Analysis:** Jelaskan patologi alokasi memori internal R yang menyebabkan fenomena ini. Analisis kompleksitas waktu $O(?)$ dan kompleksitas ruang $O(?)$ dari loop `rbind` tersebut seiring bertambahnya $N$ data.
2. **Remediation Strategy:** Tuliskan pseudocode/implementasi idiomatik fungsional menggunakan Base R atau low-overhead primitives (alokasi memori $O(N)$ linear) yang mengeliminasi CoW secara total dan menjamin stabilnya pemakaian memory headroom di bawah 3 GB.

---

### Skenario B: The Ghost State Bug (Lazy Evaluation Loop Capture)
Tim kuantitatif (*algorithmic trading*) mengimplementasikan parallel backtesting engine menggunakan arsitektur dynamic model generator. Setiap model dikonfigurasi dengan threshold stop-loss yang berbeda menggunakan loop generasi fungsi sederhana:

```R
thresholds <- c(0.01, 0.02, 0.05, 0.10)
risk_filters <- list()

for (i in seq_along(thresholds)) {
  risk_filters[[i]] <- function(loss_ratio) {
    if (loss_ratio > thresholds[i]) {
      return("LIQUIDATE")
    }
    return("HOLD")
  }
}

# Verifikasi Unit Test:
results <- c(
  risk_filters[[1]](0.03), # Ekspektasi: 0.03 > 0.01 -> "LIQUIDATE"
  risk_filters[[2]](0.03)  # Ekspektasi: 0.03 <= 0.02 -> FALSE ??? (0.03 > 0.02 -> "LIQUIDATE")
)
```

**Insiden:** Di production, saat loop dijalankan dan dieksekusi di fase evaluasi runtime, seluruh fungsi `risk_filters[[1]]` hingga `risk_filters[[4]]` menghasilkan output yang identik seolah-olah semuanya menggunakan threshold terakhir (`thresholds[4]` yaitu `0.10`). Sebagai akibatnya, posisi portofolio yang harusnya terlikuidasi pada threshold ketat (`0.01`) tetap ditahan, menyebabkan catastrophic trading loss.

**Tugas Diagnostik Anda:**
1. **Bug Decompilation:** Mengapa lazy evaluation dari symbol `i` di level lexical scope menyebabkan *deferred binding trap* ini? Kapan tepatnya nilai `i` dievaluasi oleh runtime?
2. **Zero-Side-Effect Fix:** Perbaiki implementasi pembuatan fungsi tersebut dengan menerapkan teknik *force evaluation* eksplisit (`force()`) atau functional factory closure. Berikan penjelasan mengapa solusi Anda memutus dynamic link ke parent loop frame.

---

### Skenario C: The In-Memory Caching Architecture Bottleneck
Sebuah web service berkinerja tinggi dibangun di atas package `plumber` untuk melayani prediksi latency-sensitive (< 5ms SLA per request). Service ini membutuhkan referensi ke sebuah *Feature Lookup Table* berukuran 2 GB yang diperbarui setiap 10 menit secara asinkronus di latar belakang tanpa me-restart service.

Dua opsi arsitektur diusulkan oleh tim:
* **Opsi 1 (Functional S3 Immutable State):** State disimpan sebagai `data.frame` S3 di global environment, setiap fungsi worker menerima argumen state secara murni (`predict(req_data, state)`). Saat pembaruan terjadi, referensi global diganti (`GLOBAL_STATE <<- fetch_new_state()`).
* **Opsi 2 (Reference Class / Environment Store):** State disimpan di dalam dedicated `environment` terisolasi atau encapsulation `R6` class dengan *active binding*.

**Tugas Evaluasi Anda:**
1. **Trade-Off Analysis:** Evaluasi kedua opsi tersebut terhadap aspek:
   - Concurrency & Thread-safety (R single-threaded event loop vs forked processes jika menggunakan cluster workers).
   - Risiko involuntery memory cloning (akibat Copy-on-Write) saat request payload digabungkan dengan state data.
2. **Production Recommendation:** Tentukan arsitektur mana yang wajib dipilih untuk memenuhi target SLA latency < 5ms secara konsisten (mengurangi jitter Garbage Collection). Berikan justifikasi teknis arsitektural berbasis *memory address reference*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Vectorized Circular Buffer & Stream Aggregator

#### Problem Statement
Anda ditugaskan merancang modul internal analitik *Order Book* frekuensi tinggi (*High-Frequency Trading*) di R. Modul ini menerima *infinite stream* data limit order per millisecond dalam bentuk vektor raw, dan harus mempertahankan sliding window dari $K$ transaksi terakhir ($K = 100.000$) untuk menghitung metrics moving average dan weighted volatility secara real-time. 

Jika Anda menggunakan data.frame atau list biasa, Garbage Collector (GC) R akan memicu latensi tinggi (GC pauses) akibat duplikasi CoW terus-menerus, melanggar execution SLA.

#### Requirements
1. **Zero-Allocation Circular Buffer:**
   - Implementasikan sistem circular buffer berbasis S3 class bernama `FastCircularBuffer`.
   - Menggunakan flat memory contiguous array (`numeric` vector) berukuran tetap $K$. Modifikasi elemen data baru tidak boleh memicu alokasi memori baru (terbukti via zero footprint overhead).
   - Implementasikan metode constructor `new_circular_buffer(capacity)`.
   - Implementasikan generic method `push_item(buf, val)` dan `get_snapshot(buf)` yang beroperasi menggunakan *reference semantics* (hint: leverage dedicated environments).
2. **Pure Vectorized Window Statistics:**
   - Buat fungsi `compute_stats(buf)` yang menghitung:
     * Arithmetic Mean.
     * Exponentially Weighted Moving Average (EWMA) dengan decay factor $\alpha = 0.95$.
   - Seluruh operasi komputasi harus murni tervektorisasi, bebas dari pemanggilan `for`, `while`, atau `repeat` loops di level user-code.
3. **Strict Type Safety & Contract Enforcement:**
   - Gunakan `vapply()` atau custom C-level assertion wrapper untuk validasi input. Tolak nilai non-numeric, `NA`, `NaN`, atau `Inf` seketika (*fail-fast*) tanpa merusak buffer state.

#### Constraints
- **Dilarang** menggunakan library eksternal (wajib Base R murni: tidak boleh menggunakan `Rcpp`, `data.table`, `tidyverse`, atau `dequer`).
- Validasi status CoW: Saat 100.000 data baru dimasukkan via `push_item`, address memori dari underlying storage vector (`tracemem` atau `lobstr::obj_addr`) harus tetap konstan sejak inisialisasi hingga streaming berakhir.
- Waktu pemrosesan per 100.000 push & stats cycle harus berada di bawah 250 millisecond pada CPU modern standar.

#### Expected Output
Skrip R mandiri (*self-contained script*) yang:
1. Mendefinisikan class, methods, dan fungsi komputasi.
2. Menjalankan verification benchmark menggunakan `tracemem()` untuk membuktikan ketiadaan memory copy.
3. Menampilkan microbenchmark latensi execution time per-chunk.
4. Menunjukkan determinasi numerik hasil kalkulasi statistik yang akurat.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Topologi memori representasi internal C dari Base R (`SEXP` types: `INTSXP`, `REALSXP`, `VECSXP`, `ENVSXP`, `PROMSXP`).
- [ ] Aturan implicit type coercion hierarchy di R (`logical` $\rightarrow$ `integer` $\rightarrow$ `double` $\rightarrow$ `character`) dan performa penalti yang menyertainya.
- [ ] Mekanisme Copy-on-Write (CoW), implementasi reference counting R 4.0+ (`REFCNT`), serta cara tracing mutasi via `tracemem()`.
- [ ] Perilaku internal evaluasi fungsi R: promise object, 3-point binding (expression, environment, value), dan fenomena *lazy evaluation*.
- [ ] Perbedaan semantik mendasar antara lexical scoping berbasis *Value Semantics* (List/Vector) dan *Reference Semantics* (Environment).
- [ ] Implikasi cache locality terhadap format *column-major storage* pada array/matriks 2-dimensi.
- [ ] Mengapa S3 dispatching bergantung pada atribut eksplisit, dan bagaimana modifikasi subsetting primitive dapat merusak atribut objek (seperti class, dim, dan names).

### Saya tidak perlu menghafal:
- [ ] Alamat heksadesimal representasi memori pointer internal runtime R.
- [ ] Urutan enumerasi integer representasi numerik jenis C-level SEXP (misal: apakah `LGLSXP` adalah enum 10 atau 11 di `Rinternals.h`).
- [ ] Kode implementasi internal C dari fungsi primitive/internal base R (seperti source code implementasi C `do_subset`).
- [ ] Nama algoritma pengurutan internal non-deterministik yang digunakan pada varian platform OS lawas.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan mengeliminasi $O(N^2)$ memory copying bottleneck akibat pemanggilan berulang `rbind`, `cbind`, atau modifikasi vector in-loop.
- [ ] Memanfaatkan `force()` untuk mencegah *lazy evaluation bug* / *deferred evaluation trap* pada functional factories atau loop-generated closures.
- [ ] Mengimplementasikan *type-safe functional pipelines* menggunakan `vapply()` dengan spesifikasi output signature yang kokoh.
- [ ] Memanipulasi objek environment sebagai high-performance mutable state/hash table untuk bypass CoW pada komputasi throughput tinggi.
- [ ] Membaca output profiling sistem seperti `gc()`, `lobstr::obj_addr()`, `tracemem()`, dan Rprof untuk memecahkan issue degradasi memori dan latency spikes di production.