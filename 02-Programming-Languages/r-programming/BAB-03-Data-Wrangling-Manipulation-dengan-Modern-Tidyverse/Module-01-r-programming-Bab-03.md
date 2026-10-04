# Kurikulum: Rekayasa Pemrograman R (02-Programming-Languages)
## Bab 03: Arsitektur Memori dan Sistem Berorientasi Objek
### Modul 01: Arsitektur Memori Vektor, S3 Object System, dan Semantik Copy-on-Modify

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mendiagnosis dan melacak konsumsi alokasi memori internal R (`SEXPREC`, *node overhead*, dan *data payload*) menggunakan perangkat diagnostik tingkat rendah (`tracemem`, `lobstr`).
- Mengontrol perilaku *Copy-on-Modify* untuk mengeliminasi overhead duplikasi memori bernilai kuadratik ($O(N^2)$) pada pipeline pengolahan data volume tinggi.
- Mengarsitekturkan dan mengimplementasikan sistem objek berbasis S3 secara modular, mencakup konstruktor berkinerja tinggi, validator invariansi data, dan *helper function*.
- Membangun mekanisme *method dispatch* polimorfik kustom menggunakan `UseMethod()` dan `NextMethod()` sesuai standar paket produksi CRAN/Bioconductor.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
- Penulisan fungsi modular, *closures*, dan fungsi tingkat tinggi (*higher-order functions*) di R.
- Tipe data dasar R: `logical`, `integer`, `double`, `character`, `complex`, dan `raw`.
- Pemahaman dasar arsitektur komputer: representasi pointer, *stack vs heap*, alokasi memori dinamis, dan kompleksitas asimtotik waktu/ruang (Big-O).

---

### 3. Concept
R secara fundamental ditulis di atas bahasa C dan mengoperasikan setiap objek sebagai representasi *S-expression pointer* (`SEXP`), yang menunjuk ke struktur data C internal bernama `SEXPREC` (S-Expression Record).

```
                      Struktur Internal SEXPREC (C Level)
+-------------------------------------------------------------------------+
| SXPOBJH (Header):                                                       |
|   - Tipe Objek (INTSXP, REALSXP, VECSXP, CLOSXP, dll)                   |
|   - Garbage Collection (GC) Attribute Bits                              |
|   - Reference Count / NAMED Flags (Ref count: 0, 1, atau >1)            |
+-------------------------------------------------------------------------+
| S3 Attributes Pointer (Menunjuk ke Pairlist atribut/Metadata)           |
+-------------------------------------------------------------------------+
| Data Payload (Pointer ke array kontinu C: C-array data aktual)          |
+-------------------------------------------------------------------------+
```

#### Mekanisme Alokasi Memori
- **Atomic Vectors (`INTSXP`, `REALSXP`, dll):** Dialokasikan sebagai blok memori kontigu (berurutan) di C heap. Header `SEXPREC` berukuran fixed (48 byte pada arsitektur 64-bit), ditambah buffer data aktual.
- **Generic Vectors / Lists (`VECSXP`):** Tidak menyimpan nilai secara langsung di dalam kontigu array list itu sendiri, melainkan menyimpan array pointer berukuran 8-byte yang menunjuk ke `SEXPREC` objek lain.
- **Reference Counting (`REFCNT`):** R runtime melacak berapa banyak simbol yang menunjuk ke satu alamat memori `SEXPREC`.
  - Jika `REFCNT == 1`: Modifikasi objek dapat dilakukan langsung secara in-place (*Modify-in-Place*).
  - Jika `REFCNT > 1`: Mutasi nilai memicu kloning memori penuh (*Copy-on-Modify*) untuk menjamin *functional immutability*.

#### Arsitektur Sistem S3
S3 adalah sistem pemrograman berorientasi objek (*Object-Oriented Programming* / OOP) tipe *single-dispatch dynamic polymorphism*. 
- Sebuah objek S3 secara struktural hanyalah vektor dasar (atomic atau list) yang memiliki atribut metadata `class`.
- Tidak ada validasi skema tipe data ketat pada level C runtime; penegakan invariansi data sepenuhnya menjadi tanggung jawab lapisan kode R melalui perancangan:
  1. *Constructor* (`new_*`): Konstruksi primitif cepat.
  2. *Validator* (`validate_*`): Validasi state internal.
  3. *Helper* (*user-facing constructor*): API publik untuk inisialisasi.
- **Dynamic Dispatch:** Ketika sebuah fungsi *generic* dipanggil, runtime memanggil `UseMethod("nama_generic")`. R akan mencari fungsi implementasi dengan konvensi penamaan: `nama_generic.nama_kelas()`. Jika tidak ditemukan, resolusi diturunkan ke kelas pewaris berikutnya, atau berakhir di `nama_generic.default()`.

---

### 4. Why
1. **Pencegahan Out-of-Memory (OOM) di Pipeline Produksi:** Kegagalan memahami *Copy-on-Modify* menyebabkan kode R menduplikasi dataset 10 GB menjadi 20 GB atau 30 GB saat melakukan operasi sederhana di dalam loop, memicu OOM killer pada container Kubernetes/Docker.
2. **Kinerja Waktu Eksekusi Skala Eksponensial:** Mutasi objek di dalam perulangan tanpa alokasi awal (*pre-allocation*) mengubah algoritma linear $O(N)$ menjadi kuadratik $O(N^2)$ karena runtime terpaksa mengalokasikan dan menyalin ulang memori pada setiap iterasi.
3. **Ekstensibilitas Sistem Enterprise:** Sistem S3 memungkinkan integrasi *decoupled design*. Anda dapat menambahkan tipe data baru ke dalam sistem analisis yang sudah ada tanpa perlu mengubah kode sumber fungsi generik inti.

---

### 5. What
Komponen inti yang menyusun manajemen memori dan sistem S3:

| Komponen | Definisi Teknis | Tanggung Jawab Utama |
| :--- | :--- | :--- |
| `SEXPREC` | Struktur data C dasar representasi R | Menyimpan metadata objek, reference counter, dan pointer data payload. |
| `REFCNT` (NAMED) | Integer flag (0, 1, 2) pada header objek | Menentukan apakah mutasi data harus di-*clone* atau bisa diubah *in-place*. |
| Generic Function | Fungsi dengan panggilan `UseMethod()` | Titik masuk polimorfisme; meneruskan eksekusi ke metode spesifik kelas. |
| S3 Method | Fungsi reguler dengan format `generic.class` | Menjalankan logika komputasi khusus untuk kelas terkait. |
| `NextMethod()` | Primitif dispatch warisan | Meneruskan argumen ke metode kelas induk berikutnya dalam hierarki vektor kelas. |

---

### 6. How
Alur operasional internal saat generic method dipanggil pada objek dengan hierarki kelas `c("financial_ts", "ts", "matrix")`:

```
[Pemanggilan: analyze(x)]
         |
         v
+-------------------------+
| analyze() memanggil     |
| UseMethod("analyze", x) |
+-------------------------+
         |
         v
+-------------------------------------------------------------+
| R Engine mengekstrak attr(x, "class"):                      |
| c("financial_ts", "ts", "matrix")                           |
+-------------------------------------------------------------+
         |
         |---> 1. Cek: Apakah `analyze.financial_ts` ada?
         |       |-- YES --> Eksekusi `analyze.financial_ts(x)`
         |       +-- NO  --> Lanjut ke tahap 2
         |
         |---> 2. Cek: Apakah `analyze.ts` ada?
         |       |-- YES --> Eksekusi `analyze.ts(x)`
         |       +-- NO  --> Lanjut ke tahap 3
         |
         |---> 3. Cek: Apakah `analyze.matrix` ada?
         |       |-- YES --> Eksekusi `analyze.matrix(x)`
         |       +-- NO  --> Lanjut ke tahap 4
         |
         +---> 4. Cek: Apakah `analyze.default` ada?
                 |-- YES --> Eksekusi `analyze.default(x)`
                 +-- NO  --> Throw error: "no applicable method"
```

Jika di dalam method `analyze.financial_ts` terdapat panggilan `NextMethod()`, runtime R memajukan *internal class pointer* ke kelas berikutnya (`ts`) tanpa memulai evaluasi ulang dari awal kelas turunan.

---

### 7. Analogy
Bayangkan **Copy-on-Modify** seperti dokumen laporan fisik di kantor:
- Anda memiliki map fisik dokumen asli.
- Tiga manajer berbeda meminta referensi dokumen tersebut. Alih-alih membuat tiga fotokopi tebal, Anda hanya memberikan kartu indeks berisi alamat lemari map asli kepada ketiga manajer tersebut (`REFCNT = 3`).
- Selama para manajer hanya membaca dokumen, efisiensi terjaga dan tidak ada kertas tambahan yang terbuang.
- Namun, saat Manajer A ingin mencoret-coret lembar ke-5, aturan kantor melarang pengubahan berkas yang sedang dibagikan. Sistem otomatis memfotokopi seluruh berkas tebal tersebut ke map baru khusus untuk Manajer A (`Copy-on-Modify`). Manajer A mencoret berkas barunya, sedangkan Manajer B dan C tetap membaca berkas asli.

---

### 8. Diagram

```
                        Transisi Copy-on-Modify

Kondisi Awal: Inisialisasi Pointer Bersama
  
  Symbol 'x' ---> [ SEXPREC A ] <--- Symbol 'y'
                  | REFCNT: 2  |
                  | Payload:   |
                  | [1, 2, 3]  |
                  +------------+

Operasi: y[1] <- 99L (Pemicu Copy-on-Modify)

  Symbol 'x' ---> [ SEXPREC A ] (Memori Asli Tetap Aman)
                  | REFCNT: 1  |
                  | Payload:   |
                  | [1, 2, 3]  |
                  +------------+
  
  Symbol 'y' ---> [ SEXPREC B ] (Alokasi Baru di C Heap)
                  | REFCNT: 1  |
                  | Payload:   |
                  | [99, 2, 3] |
                  +------------+
```

---

### 9. Simple Example

```r
# Diagnostik Alokasi dan Copy-on-Modify
# Menggunakan base::tracemem untuk melacak perpindahan pointer memori C

x <- c(10L, 20L, 30L)
cat("Alamat memori awal:", tracemem(x), "\n")

# Penugasan referensi (Shared Memory, TIDAK ADA duplikasi data)
y <- x
# Alamat x dan y identik pada titik ini

# Mutasi pada 'y' memicu Copy-on-Modify
y[1] <- 99L
# Output terminal akan menampilkan peringatan pelacakan: 
# 'tracemem[0x... -> 0x...]:' yang mengindikasikan alokasi heap baru

untracemem(x)

# Implementasi S3 Sederhana
# 1. Generic
render <- function(object, ...) {
  UseMethod("render")
}

# 2. Method Default
render.default <- function(object, ...) {
  stop(sprintf("Method 'render' tidak terdefinisi untuk kelas: %s", class(object)[1]))
}

# 3. Method Kelas Konkret
render.json_payload <- function(object, ...) {
  cat(sprintf("{\"type\": \"json\", \"size\": %d}\n", length(object)))
}

# 4. Instansiasi Objek S3
my_data <- structure(c(1, 2, 3), class = "json_payload")
render(my_data)
```

---

### 10. Practical Example

Penerapan arsitektur S3 standar industri untuk modul representasi aset finansial kuantitatif dengan validasi ketat dan penanganan memori aman.

```r
# ==============================================================================
# Domain: Financial Risk Analytics - High-Performance Asset Instrument Class
# ==============================================================================

# --- 1. Low-level Constructor ---
# Prinsip: Efisien, minimal komputasi, hanya memeriksa tipe primitif dasar.
new_financial_series <- function(values = double(), timestamps = double(), ticker = character()) {
  stopifnot(is.double(values))
  stopifnot(is.double(timestamps))
  stopifnot(is.character(ticker) && length(ticker) == 1L)
  
  structure(
    values,
    timestamps = timestamps,
    ticker = ticker,
    class = c("financial_series", "numeric")
  )
}

# --- 2. Validator ---
# Prinsip: Verifikasi dependensi, invariansi data, dan constraint domain.
validate_financial_series <- function(x) {
  values <- unclass(x)
  timestamps <- attr(x, "timestamps")
  ticker <- attr(x, "ticker")
  
  if (length(values) != length(timestamps)) {
    stop(
      sprintf(
        "Inkonsistensi dimensi: panjang values (%d) tidak sesuai dengan timestamps (%d).",
        length(values),
        length(timestamps)
      ),
      call. = FALSE
    )
  }
  
  if (is.unsorted(timestamps)) {
    stop("Invariansi gagal: 'timestamps' harus terurut monotonik naik.", call. = FALSE)
  }
  
  if (anyNA(values) || anyNA(timestamps)) {
    stop("Invariansi gagal: Nilai NA/NaN tidak diizinkan dalam audit finansial.", call. = FALSE)
  }
  
  return(x)
}

# --- 3. Helper (User-facing Constructor) ---
# Prinsip: Konversi tipe otomatis, sanitasi argumen, dan memanggil constructor + validator.
financial_series <- function(values, timestamps, ticker) {
  val_dbl <- as.double(values)
  ts_dbl  <- as.double(as.POSIXct(timestamps))
  tck_chr <- as.character(ticker)
  
  obj <- new_financial_series(val_dbl, ts_dbl, tck_chr)
  validate_financial_series(obj)
}

# --- 4. Generic Definitions & Method Dispatches ---
calculate_drawdown <- function(x, ...) {
  UseMethod("calculate_drawdown")
}

calculate_drawdown.default <- function(x, ...) {
  stop(sprintf("Panggilan method 'calculate_drawdown' tidak valid untuk kelas: %s", class(x)[1]))
}

calculate_drawdown.financial_series <- function(x, ...) {
  vals <- unclass(x)
  # Operasi vektor teroptimasi C tanpa alokasi objek duplikat yang berlebihan
  cum_max <- cummax(vals)
  drawdown <- (vals - cum_max) / cum_max
  
  # Rekonstruksi objek baru dengan metadata tetap dipertahankan
  new_financial_series(
    values = drawdown,
    timestamps = attr(x, "timestamps"),
    ticker = attr(x, "ticker")
  )
}

# --- 5. Override Base Subsetting Method: '[' ---
# Memastikan slicing vector tidak menghilangkan atribut custom (masalah umum S3)
`[.financial_series` <- function(x, i, ...) {
  # Ekstraksi payload melalui slicing C-level
  new_vals <- NextMethod("[")
  orig_ts  <- attr(x, "timestamps")
  
  # Pertahankan atribut waktu pada indeks yang sama
  new_ts <- orig_ts[i]
  
  new_financial_series(
    values = new_vals,
    timestamps = new_ts,
    ticker = attr(x, "ticker")
  )
}

# --- 6. Formatter Method ---
print.financial_series <- function(x, ...) {
  cat(sprintf("=== Financial Series: %s ===\n", attr(x, "ticker")))
  cat(sprintf("Ukuran Sampel : %d observasi\n", length(x)))
  if (length(x) > 0) {
    cat(sprintf("Rentang Waktu : %s s.d. %s\n", 
                as.POSIXct(attr(x, "timestamps")[1], origin = "1970-01-01"),
                as.POSIXct(attr(x, "timestamps")[length(x)], origin = "1970-01-01")))
    cat("Head Data     : ", paste(head(as.vector(x), 5), collapse = ", "), "\n")
  }
  invisible(x)
}

# --- Eksekusi Pembuktian ---
raw_dates <- as.POSIXct(c("2026-03-01 09:00:00", "2026-03-01 10:00:00", "2026-03-01 11:00:00", "2026-03-01 12:00:00"))
raw_prices <- c(100.5, 102.3, 98.1, 99.4)

ts_obj <- financial_series(raw_prices, raw_dates, "BBCA.JK")
print(ts_obj)

dd_obj <- calculate_drawdown(ts_obj)
print(dd_obj)

# Uji Subsetting Preservation
sliced_obj <- ts_obj[1:2]
print(sliced_obj)
```

---

### 11. Real World Example

#### Skenario: Pipeline Ingesti Sensor IoT Skala Besar (Smart Grid Telemetry)
Pada arsitektur ingest data Smart Grid, 1.000.000 pembacaan telemetri per batch masuk ke R-worker dalam format chunk streams. Masalah klasik terjadi: engineer melakukan penggabungan data menggunakan pendekatan naif `rbind()` atau appending vector di dalam perulangan `for`.

#### Pendekatan Buruk: Ledakan Alokasi Memori $O(N^2)$
```r
# ANTI-PATTERN: Pemborosan Memori dan CPU
naive_sensor_collector <- function(batch_count) {
  results <- numeric(0) # Inisialisasi kosong
  for (i in seq_len(batch_count)) {
    # Memicu Copy-on-Modify pada SETIAP iterasi!
    # Objek lama disalin penuh ke alamat baru bersama tambahan 1 elemen.
    results <- c(results, runif(1))
  }
  return(results)
}
# Pada 100.000 iterasi, alokasi kumulatif mencapai gigabytes di RAM.
```

#### Pendekatan Industri: Pra-alokasi RAM dan Penulisan Langsung (*Pre-allocated Buffer*)
Pendekatan berkinerja tinggi mengeliminasi *Copy-on-Modify* berulang dengan mengunci alamat memori sejak awal:

```r
# PATTERN INDUSTRI: O(N) Waktu, O(1) Overhead Memori Dinamis
production_sensor_collector <- function(batch_count) {
  # Alokasi langsung sebesar kapasitas absolut di C Heap
  buffer <- vector(mode = "double", length = batch_count)
  
  # Operasi assign index in-place (tanpa duplikasi heap baru selama REFCNT == 1)
  for (i in seq_len(batch_count)) {
    buffer[i] <- runif(1)
  }
  
  # Bungkus langsung sebagai S3 object untuk lapisan downstream
  structure(
    buffer,
    unit = "kWh",
    collected_at = Sys.time(),
    class = c("sensor_batch", "numeric")
  )
}

# Eksekusi terukur
system.time({
  batch_data <- production_sensor_collector(1e6)
})
# Eksekusi selesai dalam sub-detik dengan isolasi alokasi RAM flat konstan.
```

---

### 12. Trade-offs

| Dimensi | Desain OOP S3 & Vektor Dasar | Desain OOP S4 / R6 |
| :--- | :--- | :--- |
| **Kelebihan (*Advantages*)** | Overhead komputasi mendekati nol; pemanggilan metode (*dispatch*) sangat cepat; kompatibilitas universal dengan seluruh basis kode R base. | Menjamin integritas tipe data ketat di level runtime (S4); mendukung mutasi *by-reference* sejati (R6) tanpa *Copy-on-Modify*. |
| **Kekurangan (*Disadvantages*)** | Integritas data tidak ditegakkan oleh C runtime (atribut dapat diubah secara ilegal oleh pengguna jahat); tidak ada *encapsulation* sejati. | S4: *Dispatch overhead* lebih lambat dan sintaks kompleks. R6: Rawan masalah *thread-safety* dan merusak prinsip *functional purity*. |
| **Kompleksitas Kode** | Rendah secara sintaks, namun membutuhkan disiplin rekayasa tinggi dalam pembuatan validator manual. | Tinggi; memerlukan deklarasi formal menggunakan `setClass` atau `R6Class`. |
| **Performa Eksekusi** | Ekstrem cepat untuk pengolahan array kontinu skalar dan vektor. | Lebih lambat saat pemanggilan fungsi berulang (*dispatch latency* tinggi pada S4). |
| **Overhead Memori** | Minimal: Hanya 1 pointer `SEXPREC` dasar + payload array kontinu. | Tinggi: Objek S4/R6 memiliki metadata *environment* atau *slot overhead* yang signifikan. |

---

### 13. When To Use
- Mengembangkan paket komputasi kuantitatif atau library pengolahan data yang memprioritaskan latensi rendah (*low execution latency*).
- Menstandarkan respons output API/pipeline data yang harus terintegrasi secara mulus dengan ekosistem R standar (misal: method `print`, `summary`, `plot`, `predict`).
- Merancang abstraksi data di mana kecepatan alokasi skalar atau vektor adalah batasan utama komputasi (*bottleneck*).

---

### 14. When NOT To Use
- Jangan gunakan **S3 murni** jika Anda membutuhkan proteksi ketat tingkat enterprise terhadap modifikasi atribut (*state immutability invariants*) tanpa izin pengguna; gunakan **S4** yang memiliki registrasi kelas formal.
- Jangan gunakan representasi struktur data ini untuk manajemen state dinamis Stateful Transactional (seperti antrean pesan/Message Broker, koneksi pool TCP/Database); gunakan **R6 Classes** yang mengimplementasikan semantik *pass-by-reference* melalui R Environments.

---

### 15. Common Mistakes

#### 1. Mutasi Objek Mengakibatkan *Silent Attribute Dropping*
```r
x <- structure(c(1, 2, 3), class = "metric_series", status = "valid")
# Kesalahan: Modifikasi primitif membuang seluruh atribut non-standar
x[1] <- 100
class(x) # Masih "metric_series"
attr(x, "status") # Output: NULL! (Atribut hilang karena method `[<-` dasar tidak melestarikannya)
```

#### 2. Kloning Tak Disengaja Karena Reference Leak ke Function Arguments
```r
# Memicu kloning memori penuh pada objek besar
mutate_naively <- function(big_vector) {
  # big_vector memiliki REFCNT > 1 di sini karena diteruskan sebagai argumen
  big_vector[1] <- 999 
  # Kloning penuh terjadi seketika, menggandakan jejak memori pada container!
  return(big_vector)
}
```

#### 3. Resolusi Dispatch Ambigius Menggunakan Titik pada Nama Fungsi Non-S3
```r
# Kesalahan Fatal Perancangan:
read.csv.data.table <- function(x) { ... }
# R runtime menganggap fungsi ini sebagai implementasi method generic 'read.csv' 
# untuk kelas objek bernama 'data.table', bukan fungsi mandiri!
```

---

### 16. Best Practices

#### Production Checklist
- [ ] Pisahkan arsitektur kelas S3 menjadi tiga serangkai: `new_class` (alokasi memori cepat), `validate_class` (asersi kondisi), dan `class` (sanitasi input pengguna).
- [ ] Hindari konvensi penamaan fungsi internal dengan tanda titik (`.`); gunakan pola *snake_case* (`execute_process`) guna menghindari benturan parsing pada `UseMethod()`.
- [ ] Terapkan `NextMethod()` pada method subsetting (`[`, `[[`) dan pastikan seluruh atribut metadata kritis dikonstruksi ulang sebelum dikembalikan ke caller.
- [ ] Lakukan *profiling* jejak memori menggunakan library diagnostik produksi `bench::mark()` atau `lobstr::mem_used()` sebelum merilis algoritma ke klaster komputasi.
- [ ] Selalu definisikan implementasi method `.default` pada setiap generic baru untuk mencegah eksekusi *silent fallback* yang menghasilkan output tak menentu.

---

### 17. Troubleshooting

#### Penanganan Error Kasus Ekstrem
1. **Kasus: "vector memory exhausted (subscript table limit?)"**
   - *Akar Penyebab:* Terjadi fragmentasi memori akibat alokasi berulang dan duplikasi beruntun (*Copy-on-Modify*) pada atomic vector yang melebihi batas heap OS atau batas R (`R_MAX_VSIZE`).
   - *Solusi:* Ubah skema appending dinamis menjadi pra-alokasi array (`vector("numeric", N)`). Jika data melebihi RAM fisik, pindahkan penyimpanan ke disk-backed array (`bigstatsr` atau `arrow::RecordBatch`).

2. **Kasus: "Error in UseMethod(...) : no applicable method for ... applied to an object of class ..."**
   - *Akar Penyebab:* Dynamic dispatch gagal menemukan implementasi method spesifik untuk hirarki kelas objek yang diproses, dan method `.default` belum didefinisikan.
   - *Solusi:* Lakukan audit hierarki kelas runtime menggunakan `class(obj)` dan daftarkan metode penanganan kegagalan:
     ```r
     generic_name.default <- function(x, ...) {
       stop(sprintf("Tipe objek '%s' tidak didukung oleh pipeline %s.", 
                    paste(class(x), collapse = "/"), 
                    deparse(sys.call())), 
            call. = FALSE)
     }
     ```

---

### 18. Exercise
Tuliskan implementasi sistem S3 lengkap untuk memodelkan struktur metrik performa server:

1. Buat constructor `new_server_metric(cpu_load, memory_usage, timestamp)`:
   - `cpu_load`: vektor tipe data `double` (0.0 s.d. 100.0).
   - `memory_usage`: vektor tipe data `double` (dalam Gigabytes).
   - `timestamp`: vektor integer epoch time.
2. Buat validator `validate_server_metric(x)`:
   - Memastikan panjang ketiga vektor bernilai sama.
   - Memastikan tidak ada metrik `cpu_load` yang berada di luar rentang `[0.0, 100.0]`.
3. Buat implementasi polimorfik method S3 `summary.server_metric(object)`:
   - Mengembalikan sebuah `named list` berisi rata-rata CPU load dan rasio utilisasi memori maksimum.

---

### 19. Challenge

#### Problem Statement
Di dalam engine pemrosesan kuantitatif frekuensi tinggi (High-Frequency Trading), fungsi subsetting bawaan R `[.data.frame` menghabiskan 65% waktu siklus CPU karena mengekstraksi atribut baris dan kolom secara berulang (*heavy overhead metadata copying*).

#### Tugas Rekayasa
Bangun kelas turunan berbasis S3 bernama `fast_matrix`:
1. Berbasis tipe data dasar `numeric matrix`.
2. Implementasikan method `[.fast_matrix` kustom yang:
   - Melakukan *slice* data secara langsung menggunakan primitif subsetting C tanpa menduplikasi data matrix yang tidak dipilih.
   - Mempertahankan kelas `fast_matrix` pada hasil kembalian tanpa memicu alokasi atribut yang tidak perlu.
   - Mengimplementasikan bypass validasi yang menghasilkan penambahan performa minimum **3x lebih cepat** dibandingkan `[.matrix` standar saat dieksekusi 100.000 kali.

#### Uji Asersi Kinerja
Buktikan efisiensi kode Anda dengan menyertakan pengujian performa menggunakan `bench::mark()` terhadap fungsi subset bawaan base R.

---

### 20. Summary
- **Arsitektur `SEXPREC`** adalah representasi dasar seluruh objek R di C-level, membedakan secara tegas antara metadata (header, atribut) dan data payload.
- **Copy-on-Modify** adalah pilar integritas fungsional R yang mencegah *side-effects*, namun dapat menjadi *computational bottleneck* fatal ($O(N^2)$ alokasi waktu dan OOM) jika pola manipulasi in-place tidak dioptimalkan melalui pra-alokasi (*pre-allocation*).
- **Sistem S3** adalah fondasi OOP dominan dalam ekosistem R yang bekerja melalui mekanisme *dynamic single-dispatch* berbasis atribut `class` dan fungsi delegasi `UseMethod()`.
- Penulisan S3 siap produksi menuntut penerapan pola arsitektur: **Constructor** (alokasi memori mentah), **Validator** (penegakan invariansi domain data), dan **Helper** (antarmuka validasi pengguna akhir). Mutasi subsetting wajib dikawal ketat agar tidak menghilangkan identitas kelas polimorfik secara *silent*.