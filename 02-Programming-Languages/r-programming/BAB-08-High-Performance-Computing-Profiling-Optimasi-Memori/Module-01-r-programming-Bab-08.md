# Kurikulum: R Programming (02-Programming-Languages)
## Bab 08: High-Performance Computing & Memory Internals
### Module 01: Deep Memory Management: SEXP Internals, Copy-on-Modify, ALTREP, dan Garbage Collection Architecture

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mendiagnosis alokasi memori internal R pada level C-API (`SEXP`, `SEXPREC`) menggunakan instrumentasi diagnostik runtime (`lobstr`, `tracemem`).
- Mengeliminasi overhead duplikasi *deep-copy* memori dengan mengendalikan *Copy-on-Modify* (CoM) semantics dan memvalidasi refcount objek (`REFCNT`).
- Mengimplementasikan pola komputasi berbasis ALTREP (*Alternative Representations*) untuk menghemat footprint memori hingga skala gigabyte.
- Mengonfigurasi parameter *Garbage Collector* (GC) level generasi (*generational mark-and-sweep*) guna memitigasi *latency spikes* pada sistem pemrosesan batch dan microservices R berbasis Plumber.

---

### 2. Prerequisite
- Pemahaman mendalam tentang tipe data dasar R (vektor atomik, list, atribut, environment).
- Penguasaan konsep manipulasi data terstruktur (`data.frame`, `data.table`).
- Pemahaman dasar arsitektur memori sistem operasi (stack vs heap, pointer, paging).
- Familiaritas dasar dengan sistem penulisan fungsi R fungsional dan leksikal scoping.

---

### 3. Concept
R secara fundamental dibangun di atas bahasa pemrograman C. Setiap objek yang dibuat di level R direpresentasikan di level C sebagai sebuah pointer menuju struktur data `SEXPREC` (S-Expression Record), dengan tipe pointer generik bernama `SEXP`.

```c
/* Representasi simplifikasi SEXPREC di GNU R core */
struct SEXPREC {
    SEXPREC_HEADER header;
    union {
        struct primsxp_struct primsxp;
        struct symsxp_struct symsxp;
        struct listsxp_struct listsxp;
        struct envsxp_struct envsxp;
        struct vecsxp_struct vecsxp;
    } u;
};
```

Pada struktur `header`, R menyimpan informasi metadata krusial:
1. **Tipe Objek (TYPEOF)**: Mendefinisikan apakah data merupakan `INTSXP` (integer vector), `REALSXP` (double), `VECSXP` (generic vector/list), atau `ENVSXP` (environment).
2. **Mark Bits**: Digunakan oleh Garbage Collector untuk fase penandaan (*marking phase*).
3. **Reference Counter (`REFCNT`)**: Sejak R 3.1.0, R beralih dari mekanisme `NAMED` ke tracking reference counting penuh. Ketika sebuah objek di-bind ke simbol baru, nilai `REFCNT` di-inkremen.

#### Copy-on-Modify (CoM) & Modify-in-Place
R secara default mempertahankan paradigma *pure functional programming*: objek bersifat *immutable* secara semantik. Namun, demi efisiensi, R tidak menyalin data secara fisik saat terjadi penugasan variabel (*assignment*). Sebaliknya, R hanya membuat referensi pointer baru ke blok memori yang sama (*shallow reference*).

Ketika mutasi dilakukan pada objek tersebut:
- Jika `REFCNT <= 1`, R melakukan mutasi langsung di alamat memori asli (*Modify-in-Place*).
- Jika `REFCNT > 1`, R mengalokasikan blok memori baru, menduplikasi seluruh payload data (*Deep Copy*), mendereferensikan objek target, lalu menerapkan mutasi pada memori baru tersebut.

#### ALTREP (Alternative Representations)
Diperkenalkan pada R 3.5.0, ALTREP merevolusi arsitektur memori R. Alih-alih mengalokasikan array C tradisional secara berurutan di heap untuk semua data (misal: `1:1e9` yang secara historis mengonsumsi 4GB RAM), ALTREP mengizinkan pembuatan vektor virtual yang hanya menyimpan metadata batas bawah, batas atas, dan fungsi generator. Data aktual diakses secara *lazy* atau dipetakan (*memory-mapped*) tanpa alokasi linear di muka.

#### Generational Garbage Collection
Manajemen memori dinamis diatur oleh GC tri-color generational:
- **Node Memory (Ncells)**: Mengatur struktur heap tetap untuk pointer dan header objek (`SEXPREC`).
- **Vector Memory (Vcells)**: Mengatur payload data dinamis (misalnya float dan integer array).
- Objek dibagi ke dalam **Generasi 0, 1, dan 2**. Objek baru masuk Generasi 0. Jika bertahan dari satu siklus pembersihan, objek dipromosikan ke generasi yang lebih tua, yang memiliki frekuensi sweep lebih jarang, mengurangi throughput pause latency.

---

### 4. Why
1. **Eliminasi OOM (Out of Memory) Fatal**: Kegagalan memahami CoM adalah penyebab utama *crash* pemrosesan dataset berskala besar di server produksi. Mengubah satu elemen dalam dataframe berukuran 16GB saat `REFCNT > 1` akan menduplikasi alokasi menjadi 32GB secara instan.
2. **Penurunan Latensi Latent**: *Garbage collector pause* pada heap berukuran puluhan gigabyte dapat membekukan *R execution thread* selama ratusan milidetik hingga beberapa detik. Menjaga refcount dan menggunakan ALTREP meminimalkan tekanan (*pressure*) pada GC cycle.
3. **Optimasi Pipeline Skala Besar**: Memungkinkan ingestion dan transformasi data real-time mendekati kecepatan native C tanpa meninggalkan ekosistem R.

---

### 5. What
Komponen arsitektural internal yang beroperasi:
- **`SEXP`**: Abstraksi pointer dasar dari semua entitas R.
- **`lobstr::obj_addr()` & `tracemem()`**: Tool diagnostik untuk melacak alamat memori C runtime dan mendeteksi pemicu kloning memori.
- **`REFCNT` Field**: Penghitung jumlah simbol yang menunjuk ke memori terkait untuk menentukan percabangan logika copy-vs-modify.
- **ALTREP Framework**: Antarmuka C internal yang menggantikan *underlying storage* vektor dengan wrapper fungsional atau I/O mmap.
- **GC Heaps (Vcells & Ncells)**: Ruang alokasi internal R yang diatur secara otomatis berdasarkan ambang batas memori (*trigger thresholds*).

---

### 6. How
Alur kerja mutasi memori dan siklus hidup objek di R:

```
[Inisialisasi Data] 
       │
       ▼
[Alokasi SEXP di Heap (Ncell Header + Vcell Payload)]
       │
       ▼
[Assignment ke Simbol Baru (b <- a)] ───► Increment REFCNT (REFCNT > 1)
       │
       ▼
[Operasi Mutasi (b[1] <- new_val)]
       │
       ├────► Cek REFCNT:
       │         │
       │         ├─► REFCNT == 1: Modify-in-Place (Alamat memori tetap sama)
       │         │
       │         └─► REFCNT > 1: Copy-on-Modify (CoM Triggered)
       │                              │
       │                              ├─► Alokasi SEXP baru di Heap
       │                              ├─► Duplikasi payload (Deep Copy)
       │                              ├─► Terapkan mutasi pada buffer baru
       │                              └─► Turunkan REFCNT buffer lama
       │
       ▼
[Simbol di Luar Scope / Dereferenced] ───► REFCNT = 0 (Unreachable)
       │
       ▼
[Generational Garbage Collector Triggered] ───► Mark and Sweep (Reclaim Vcells/Ncells)
```

---

### 7. Analogy
Bayangkan sebuah dokumen teknis master yang disimpan di meja arsip (*Heap Memory*). 
- **Shallow Reference**: Ketika Anda memberikan dokumen itu kepada rekan kerja Anda, Anda tidak memfotokopinya; Anda hanya memberikan kartu indeks bertuliskan nomor rak arsip yang sama (*Pointer assignment*). Sekarang dokumen memiliki dua pemegang kartu (*REFCNT = 2*).
- **Copy-on-Modify**: Jika rekan Anda ingin menambahkan coretan revisi pada dokumen tersebut, petugas arsip melarang mencoret dokumen asli. Petugas secara paksa memfotokopi seluruh isi dokumen (*Deep Copy*), menyerahkan dokumen fotokopi tersebut kepadanya untuk dicoret-coret, sementara dokumen asli tetap bersih. Namun, jika hanya dia satu-satunya orang yang memiliki kartu akses (*REFCNT = 1*), ia diizinkan langsung mencoret dokumen asli tanpa fotokopi (*Modify-in-place*).
- **ALTREP**: Alih-alih mencetak dokumen setebal 1.000.000 halaman berisi angka urut 1 sampai 1.000.000, arsiparis hanya memberikan kartu kecil bertuliskan: *"Dokumen ini berisi angka kontinu dari 1 hingga 1.000.000; tanyakan halaman mana yang Anda butuhkan, akan saya hitung saat itu juga."* Footprint dokumen menyusut dari satu gudang menjadi secarik kertas.

---

### 8. Diagram

```
Kondisi Awal: Inisialisasi Objek
Simbol 'x' ───────► [ SEXP: REALSXP | REFCNT: 1 ]
                           │
                           ▼
                    [ Payload: 1.0, 2.0, 3.0, 4.0 ] (0x7ffee1)

Assignment Baru: y <- x (Shallow Copy)
Simbol 'x' ───────┐
                  ├─► [ SEXP: REALSXP | REFCNT: 2 ]
Simbol 'y' ───────┘        │
                           ▼
                    [ Payload: 1.0, 2.0, 3.0, 4.0 ] (0x7ffee1)

Mutasi: y[1] <- 99.0 (Copy-on-Modify Terjadi)
Simbol 'x' ───────► [ SEXP: REALSXP | REFCNT: 1 ]
                           │
                           ▼
                    [ Payload: 1.0, 2.0, 3.0, 4.0 ] (0x7ffee1)

Simbol 'y' ───────► [ SEXP: REALSXP | REFCNT: 1 ] (SEXP Baru Dialokasikan)
                           │
                           ▼
                    [ Payload: 99.0, 2.0, 3.0, 4.0 ] (0x7ffee9 - Alamat Baru)
```

---

### 9. Simple Example
Melihat mekanisme Copy-on-Modify dan deteksi ALTREP secara langsung:

```r
# Membutuhkan R >= 3.5.0
# Diagnostik memori internal
x <- c(1.5, 2.5, 3.5, 4.5)
cat("Alamat memori awal x:", lobstr::obj_addr(x), "\n")

# Lacak duplikasi memori interaktif menggunakan tracemem
tracemem(x)

# 1. Assignment (Hanya menyalin pointer/referensi)
y <- x
cat("Alamat y setelah assignment:", lobstr::obj_addr(y), "\n")
cat("Sama persis? ", identical(lobstr::obj_addr(x), lobstr::obj_addr(y)), "\n")

# 2. Mutasi pada y memicu Copy-on-Modify
y[1] <- 99.9
cat("Alamat y setelah modifikasi:", lobstr::obj_addr(y), "\n")
cat("Alamat x tetap stabil:      ", lobstr::obj_addr(x), "\n")

# Hentikan pelacakan
untracemem(x)

# 3. Demonstrasi ALTREP
altrep_vector <- 1:1e8
cat("Ukuran ALTREP vector (100M integer):", lobstr::obj_size(altrep_vector), "bytes\n")

# Paksa alokasi materialisasi memori non-ALTREP
real_vector <- c(altrep_vector, 1L)
cat("Ukuran Materialized vector:         ", lobstr::obj_size(real_vector), "bytes\n")
```

---

### 10. Practical Example
Optimasi pipeline transformasi matriks analitik data point processing dengan mencegah kebocoran alokasi CoM:

```r
# Memuat pustaka untuk analisis struktural
suppressPackageStartupMessages({
  library(lobstr)
})

# Implementasi pola Anti-Pattern (Naif: Menginduksi CoM di setiap iterasi)
process_naive <- function(n_rows, n_cols) {
  # Mengalokasikan data frame
  df <- as.data.frame(matrix(runif(n_rows * n_cols), nrow = n_rows, ncol = n_cols))
  
  # Memodifikasi kolom secara berulang (anti-pattern)
  # Di setiap iterasi, seluruh data frame disalin karena atribut dimensi diperbarui
  for (j in 1:n_cols) {
    df[, j] <- df[, j] * 2.0
  }
  return(df)
}

# Implementasi High-Performance Production Standard
# Menggunakan direct list mutation & memory pre-allocation
process_optimized <- function(n_rows, n_cols) {
  # Data frame internal adalah sebuah list of vectors (VECSXP berisi REALSXP)
  # Buat list mentah terlebih dahulu untuk meminimalkan modifikasi metadata S3
  raw_list <- vector("list", n_cols)
  
  for (j in 1:n_cols) {
    # Generate data langsung ke slot tanpa intermediate reference (REFCNT = 1)
    raw_list[[j]] <- runif(n_rows)
  }
  
  # Lakukan in-place mutation pada list sebelum dipromosikan ke S3 data.frame
  for (j in 1:n_cols) {
    # Vectorized scalar multiplication pada single-referenced SEXP
    raw_list[[j]] <- raw_list[[j]] * 2.0
  }
  
  # Set class dan attributes sekaligus di akhir untuk menghindari triggering CoM berulang
  attr(raw_list, "row.names") <- .set_row_names(n_rows)
  attr(raw_list, "names") <- paste0("V", seq_len(n_cols))
  class(raw_list) <- "data.frame"
  
  return(raw_list)
}

# Verifikasi Memory Profiling
cat("--- Profiling Naive Allocation ---\n")
bench_naive <- bench::mark(
  naive = process_naive(10000, 50),
  iterations = 5,
  check = FALSE
)
print(bench_naive[, c("expression", "min", "median", "mem_alloc", "n_gc")])

cat("\n--- Profiling Optimized Allocation ---\n")
bench_opt <- bench::mark(
  optimized = process_optimized(10000, 50),
  iterations = 5,
  check = FALSE
)
print(bench_opt[, c("expression", "min", "median", "mem_alloc", "n_gc")])
```

---

### 11. Real World Example
**Kasus**: Sistem Engine Kalkulasi Value-at-Risk (VaR) Finansial Skala Besar pada Trading Desk Global.

**Masalah**: 
Sebuah arsitektur analitik perbankan memproses simulasi Monte Carlo 100.000 skenario harga untuk 5.000 portofolio aset derivatif setiap jam. Script batch R berjalan pada instance compute AWS EC2 memory-optimized (`r5.4xlarge` - 128GB RAM). 

Meskipun ukuran murni data skenario hanya ~4GB, proses R secara mendadak mengalami *OOM Termination (Exit Code 137)* oleh Linux OOM Killer. Analisis log mengidentifikasi bahwa loop agregasi risiko memicu siklus CoM pada list hasil skenario bertingkat (`nested lists`). Setiap kali elemen skenario di-update:
```r
portfolios[[i]]$simulations[j, ] <- calculated_vector
```
R membuat salinan bertingkat (*cascading deep copy*) dari objek `portfolios`, melipatgandakan footprint memori hingga melampaui 128GB, yang menyebabkan Garbage Collector melakukan *thrashing* (GC memakan waktu 82% dari total compute time) sebelum akhirnya crash.

**Solusi Arsitektural**:
1. Menghilangkan struktur nested data frame dan beralih ke struktur flat memory buffer menggunakan environment berbasis address-pointer atau `data.table` by-reference (`:=`) operator yang beroperasi langsung pada C-level vector memory.
2. Memanfaatkan memory-mapped vectors (`bigstatsr` / ALTREP backend) untuk mengalirkan simulasi Monte Carlo dari shared memory tanpa meletakkannya di heap GC.

**Hasil**:
- Penggunaan memory puncak (*peak RAM consumption*) turun dari **>128 GB** menjadi **6.2 GB** stabil.
- Waktu komputasi total berkurang dari **48 menit** (sebelum crash) menjadi **3 menit 12 detik**.
- Beban Garbage Collector berkurang dari **82%** dari siklus eksekusi menjadi **kurang dari 2%**.
- Biaya infrastruktur server berkurang hingga 75% karena migrasi ke tipe instans compute yang lebih kecil.

---

### 12. Trade-offs

| Dimensi | Mutasi Murni Fungsional (Standard R CoM) | Mutasi In-Place / Reference Semantics (`data.table` / Environments / R6) |
| :--- | :--- | :--- |
| **Kelebihan (Advantages)** | Sangat aman (*pure functional*), bebas efek samping (*no side-effects*), referensial transparan, mudah diuji secara modular. | Memori sangat efisien, footprint minimal, eksekusi cepat pada ukuran data skala gigabyte. |
| **Kekurangan (Disadvantages)** | Duplikasi memori intensif jika refcount > 1; GC thrashing pada array berukuran besar. | Mengorbankan functional safety; mutasi suatu variabel dapat mengubah data di variabel lain yang menunjuk pointer sama. |
| **Kompleksitas (Complexity)** | Rendah; developer tidak perlu memikirkan pointer lifecycle. | Tinggi; developer harus mengelola state mutability dan menghindari silent state corruption. |
| **Performa (Performance)** | Degradasi eksponensial seiring bertambahnya modifikasi pada struktur berukuran besar. | Mendekati kecepatan bare-metal C; latensi alokasi $O(1)$. |
| **Biaya Memori (Cost)** | Overhead memori temporer mencapai $2\times$ hingga $N\times$ dari ukuran objek saat terjadi CoM. | Memori konstan $1\times$ dari payload ukuran objek; alokasi heap terkontrol ketat. |

---

### 13. When To Use
- Gunakan kontrol eksplisit CoM ketika memproses dataset yang ukurannya memakan **>20% dari total RAM fisik sistem**.
- Gunakan teknik in-place buffer modification ketika mengeksekusi algoritma iteratif numerik (misal: Iteratively Reweighted Least Squares, MCMC Sampling, iterasi konvergensi optimasi non-linear).
- Gunakan ALTREP representations saat mengonsumsi file data flat besar (seperti CSV menggunakan `vroom`) atau memory-mapped file, di mana parsing instan diperlukan tanpa membanjiri RAM.

---

### 14. When NOT To Use
- Jangan gunakan teknik memori in-place reference jika Anda menulis library analytical modular yang mengharuskan sifat *idempotent* dan bebas *side-effects*.
- Jangan mengorbankan keterbacaan kode (misalnya beralih ke pointer low-level C API) pada dataset kecil (<100MB) di mana performa salinan memori R terjadi dalam skala sub-milidetik.
- Hindari bypass referensi standar jika tim Anda tidak memiliki mekanisme unit test yang memvalidasi *immutability guarantees*.

---

### 15. Common Mistakes
1. **Mengembangkan Vektor Secara Dinamis di Dalam Loop**:
   ```r
   # FATAL: Menyebabkan O(N^2) memory reallocation dan copying
   vec <- c()
   for(i in 1:1e5) {
     vec <- c(vec, i) # Memicu CoM dan deep-copy di SETIAP iterasi tunggal!
   }
   ```
2. **Duplikasi Pointer Tak Sengaja Sebelum Mutasi**:
   ```r
   df_main <- large_df
   # Membaca kolom ke variabel sementara menaikkan REFCNT
   temp <- df_main$col_a 
   # Mutasi berikutnya pada df_main memicu deep copy total karena REFCNT > 1!
   df_main$col_a[1] <- 999 
   ```
3. **Memanggil `gc()` Secara Manual Terlalu Sering**:
   Banyak pengembang memanggil `gc()` di dalam loop analitik. Ini adalah anti-pattern berat; `gc()` menyapu Generasi 0, 1, dan 2 secara penuh, yang memakan waktu ratusan siklus CPU dan justru mendegradasi throughput komputasi. Biarkan GC engine bekerja berdasarkan heuristik ambang batas alokasinya sendiri.

---

### 16. Best Practices (Production Checklist)
- [ ] **Alokasikan Memori di Muka (Pre-allocate)**: Selalu inisialisasi vektor/matriks dengan panjang final (`vector("numeric", length = N)`) sebelum loop komputasi dijalankan.
- [ ] **Pertahankan REFCNT = 1**: Jika mutasi in-place diperlukan, pastikan tidak ada alias atau referensi kedua yang terikat pada objek tersebut.
- [ ] **Validasi ALTREP Status**: Pastikan vektor deret tidak termaterialisasi sebelum diproses oleh fungsi C backend (`.Internal(inspect(vec))` atau `lobstr::ref()`).
- [ ] **Gunakan `data.table` untuk Mutasi Skala Gigabyte**: Manfaatkan operator `:=` untuk bypass sistem CoM R melalui memory pointers mutation di level C.
- [ ] **Atur Batas Memori R Environment**: Konfigurasikan file `.Renviron` dengan flag alokasi yang tepat (`R_MAX_VSIZE`) untuk mencegah crash sistem operasi yang tidak terkendali di container Docker.
- [ ] **Hindari Operasi S3 Replacement Method pada Dataframe Besar**: Pola `names(df)[1] <- "id"` menyalin seluruh dataframe; gunakan `setattr()` atau manipulasi list internal.

---

### 17. Troubleshooting

#### Issue: Terjadi Spike Alokasi Memori Misterius saat Update Sebagian Kolom Data Frame
- **Penyebab**: Class `data.frame` adalah list ber-atribut. Jika Anda mengubah satu elemen kolom, namun atribut `names` atau `row.names` memiliki pointer duplikat di tempat lain, R menduplikasi seluruh kontainer list beserta komponen yang tidak tersentuh.
- **Deteksi**:
  ```r
  tracemem(my_df)
  my_df$target_col[1] <- 0 # Periksa log trace memory trace stack
  ```
- **Solusi**: Isolasi modifikasi hanya pada vektor kolom individual, atau gunakan direct slot address mutation via C-interface.

#### Issue: Garbage Collection Pause yang Sangat Tinggi pada Container Docker
- **Penyebab**: Secara default, GC R mengasumsikan memori bebas sistem operasi sama dengan host fisik, bukan batas (*limit*) cgroups Docker, memicu paging/swapping sebelum GC sempat berjalan.
- **Solusi**: Berikan instruksi alokasi memori eksplisit di runtime:
  ```r
  # Konfigurasi batas memori eksplisit di awal R script
  mem.limits(vsize = 8000) # Membatasi vector heap hingga 8GB
  ```

---

### 18. Exercise
Analisis dan perbaiki fungsi di bawah ini. Fungsi ini bertugas mengisi matriks kovarians simulasi berukuran $5.000 \times 5.000$, tetapi kehabisan memori dan memakan waktu >30 detik karena kesalahan implementasi pointer dan alokasi.

```r
# Kode Masalah (Broken Code)
generate_simulated_cov <- function(dim_size) {
  result <- NULL
  for (i in 1:dim_size) {
    row_data <- c()
    for (j in 1:dim_size) {
      val <- exp(-abs(i - j) / 100.0)
      row_data <- c(row_data, val) # Masalah: dynamic vector growth
    }
    result <- rbind(result, row_data) # Masalah: massive cascading CoM copy
  }
  return(as.data.frame(result))
}
```

**Instruksi**:
1. Tulis ulang fungsi tersebut dengan nama `generate_simulated_cov_optimized(dim_size)`.
2. Gunakan pre-allocation penuh pada level native continuous vector/matrix.
3. Pastikan waktu eksekusi berada di bawah 0.5 detik untuk `dim_size = 5000` dengan alokasi memori puncak tidak lebih dari 250MB.

---

### 19. Challenge
Rancang sebuah prototipe **Zero-Copy In-Place Matrix Column Scaler** menggunakan environment R internal.
- Fungsi harus menerima input sebuah `environment` yang memegang sebuah matriks double berukuran $10.000 \times 1.000$.
- Skalakan setiap kolom (bagi dengan nilai mean kolom tersebut).
- **Syarat Ketat**: Buktikan melalui `lobstr::obj_addr()` bahwa alamat memori matriks dasar **sebelum** dan **sesudah** normalisasi adalah **100% IDENTIK**, membuktikan bahwa tidak ada duplikasi data (0 bytes deep-copied) yang terjadi selama seluruh proses siklus hidup eksekusi.

---

### 20. Summary

| Komponen | Peran Arsitektural | Dampak Produksi |
| :--- | :--- | :--- |
| **`SEXP` & Header** | Struktur C fundamental pembungkus seluruh tipe data di R. | Membawa metadata tipe data dan `REFCNT` untuk keputusan alokasi memori. |
| **Copy-on-Modify (CoM)** | Mekanisme penjaga immutabilitas fungsional R. | Menjamin kode fungsional aman dari *side-effects*, namun dapat melipatgandakan footprint RAM jika mutasi dilakukan saat `REFCNT > 1`. |
| **ALTREP** | Abstraksi kompresi komputasional untuk vektor native. | Mengeliminasi alokasi memori fisik untuk deret teratur atau streaming data besar (*zero-memory overhead*). |
| **Generational GC** | Engine otomatis pengelolaan siklus hidup Ncells & Vcells. | Menyapu heap berdasarkan generasi umur objek; pemanggilan manual yang tidak tepat mendegradasi throughput sistem secara drastis. |