# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi R, RStudio Environment, & Vectorized Computing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Representasi Internal Memory SEXP
Jelaskan perbedaan mendasar antara *atomic vector* dan *generic vector* (`list`) pada level representasi memori C di dalam R runtime (`SEXPREC`). Mengapa operasi komputasi numerik pada *atomic vector* jauh lebih cepat dibandingkan dengan iterasi elemen-elemen pada `list` yang berisi tipe data seragam?

### Soal 1.2: Mekanisme Implicit Coercion
R mengimplementasikan hierarki koersi implisit (*implicit coercion*): `logical` $\rightarrow$ `integer` $\rightarrow$ `double` $\rightarrow$ `character`. 
Jelaskan konsekuensi komputasional dari aturan ini ketika sebuah vektor numerik berukuran $10^7$ elemen secara tidak sengaja disisipi satu nilai string `"NA"` (bukan konstanta `NA`). Apa yang terjadi pada struktur memori, cache CPU, dan alokasi RAM secara instan?

### Soal 1.3: Vector Recycling Rule & Silent Invalidation
Bagaimana aturan *vector recycling* bekerja ketika R mengevaluasi ekspresi biner antara dua vektor dengan panjang berbeda (misalnya $n$ dan $m$ di mana $n \pmod m \neq 0$ vs $n \pmod m = 0$)? Sebutkan kondisi di mana R memunculkan peringatan (*warning*) dan kondisi di mana R membiarkannya berjalan secara *silent*, serta analisislah potensi bahaya tersembunyi yang ditimbulkannya pada kalkulasi saintifik.

### Soal 1.4: Semantik Copy-on-Write (CoW)
Jelaskan siklus hidup sebuah objek di R saat dikenai modifikasi elemen, ditinjau dari mekanisme *Copy-on-Write* (CoW) dan penghitung referensi internal (`NAMED` atau `REFCNT`). Dalam kondisi apa modifikasi objek dapat terjadi secara *in-place* (tanpa duplikasi memori), dan kapan R terpaksa menduplikasi seluruh vektor ke blok memori baru?

### Soal 1.5: Komputasi Tervektorisasi vs Interpreted Loop
Secara teknis, mengapa instruksi tervektorisasi seperti `x + y` jauh melampaui performa perulangan eksplisit `for (i in seq_along(x)) z[i] <- x[i] + y[i]` di dalam R? Bedah jawaban Anda dari sudut pandang *interpreter overhead*, pemanggilan primitif C (`.Primitive` / `.Internal`), dan pemanfaatan instruksi CPU modern (SIMD).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Diagnostik Duplikasi Memori Menggunakan Tracing
Perhatikan cuplikan kode berikut:
```R
x <- runif(1e7)
tracemem(x)
y <- x
x[1] <- 0.5
y[1] <- 0.5
```
Jelaskan secara presisi langkah demi langkah apa yang dilaporkan oleh `tracemem()`. Mengapa pembaruan pada `x[1]` memicu alokasi baru, sedangkan status duplikasi pada `y[1]` bergantung pada apakah pemanggilan dilakukan di level global environment atau di dalam fungsi terisolasi?

### Soal 2.2: Fenomena ALTREP (Alternative Representations)
Sejak R versi 3.5.0, fitur ALTREP diperkenalkan. Jelaskan bagaimana R merepresentasikan vektor seperti `x <- 1:1e9` di dalam RAM. Apa yang terjadi pada konsumsi memori ketika kita mengeksekusi:
```R
# Kondisi A
length(x)

# Kondisi B
x[5]

# Kondisi C
x[1] <- 42L
```
Sebutkan implikasi performa dari transformasi representasi internal tersebut.

### Soal 2.3: Degradasi Atribut dan Stripping pada Ekstraksi Subset
Mengapa operasi subsetting tertentu seperti `x[1:5]` dapat mempertahankan atribut objek (seperti kelas `Date` atau `factor`), namun pada matriks operasi `m[1, , drop = TRUE]` mendegradasi matriks 2D menjadi vektor 1D? Bagaimana mekanisme atribut `dim` dikelola oleh kernel R selama operasi pengirisan (*slicing*), dan bagaimana cara mencegah efek samping regresi tipe data ini secara konsisten?

### Soal 2.4: Perilaku Tiga Logika (Three-Valued Logic) dan Ekstraksi Menggunakan NA
Perhatikan ekspresi berikut:
```R
vec <- c(10, 20, 30, 40, 50)
mask <- c(TRUE, FALSE, NA, TRUE, FALSE)
res <- vec[mask]
```
Berapakah panjang (`length`) dari `res` dan apa nilai elemen ke-3? Jelaskan mekanisme internal R mengapa indeks bernilai `NA` menghasilkan `NA` pada vektor keluaran, dan bandingkan dengan bagaimana fungsi `which(mask)` memitigasi anomali penyusupan `NA` ini.

### Soal 2.5: Presisi Floating-Point & Subnormal Numbers dalam Vektor Numerik
Seorang data engineer melakukan filter baris dengan kondisi vectorized equality:
```R
val1 <- seq(0, 1, by = 0.1)
val2 <- 0.3
matches <- val1[val1 == val2]
```
Mengapa ekspresi di atas sering kali menghasilkan vektor numerik kosong (`numeric(0)`)? Jelaskan representasi standard IEEE 754 floating-point yang mendasarinya dan tuliskan pendekatan idiomatik R untuk menangani perbandingan numerik pada vektor skala besar tanpa mengorbankan integritas data.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Memori dan Garbage Collection Spikes pada Pipeline ETL
Sebuah skrip R berjalan setiap jam untuk memproses data sensor IoT. Skrip ini membaca file biner berukuran 4 GB, memecahnya menjadi vektor per jam, dan melakukan transformasi nilai:

```R
process_sensor_data <- function(raw_data) {
  cleaned_data <- numeric(0)
  for (i in 1:length(raw_data)) {
    # Transformasi non-linear dan kalibrasi
    calibrated_val <- (raw_data[i] * 1.05) - 0.02
    cleaned_data <- c(cleaned_data, calibrated_val) # Akumulasi dinamis
  }
  return(cleaned_data)
}
```
Skrip ini sering mengalami *crash* akibat *Out-Of-Memory* (OOM) pada mesin server dengan RAM 32 GB, padahal ukuran raw data hanya 4 GB.

**Pertanyaan Diagnostik:**
1. Hitung kompleksitas memori temporal dari pola akumulasi `cleaned_data <- c(cleaned_data, calibrated_val)`. Mengapa konsumsi RAM melonjak hingga melampaui kapasitas mesin?
2. Bagaimana aktivitas Garbage Collector (GC) R terpengaruh oleh pola alokasi di atas, dan bagaimana dampaknya terhadap utilisasi CPU?
3. Refaktor fungsi tersebut menjadi versi yang sepenuhnya tervektorisasi (*fully vectorized*) dengan alokasi memori $O(N)$ instan atau modifikasi *in-place*.

---

### Skenario B: Silent Corruption pada Data Ingestion Rekam Medis Pasien
Sebuah pipeline analitik rumah sakit mengimpor 50 juta catatan rekam medis dari berbagai file CSV terdistribusi. Salah satu kolom kunci adalah `SystolicBP` (tekanan darah sistolik, diharapkan integer). Tim analis menemukan bahwa model regresi menghasilkan output yang salah total tanpa adanya pesan *error* saat *ingestion*. 

Setelah diinvestigasi, salah satu file dari vendor mesin medis mengandung entri teks malformed berupa string `NULL` (alih-alih string kosong atau representasi NA standar):
```R
raw_bp <- c(120, 118, 140, "NULL", 130, 125)
calculated_risk <- raw_bp * 0.12 # Error atau silent coercion?
```

**Pertanyaan Diagnostik:**
1. Ketika fungsi pembacaan data standar R (`read.csv` atau pemindaian berbasis vektor dasar) membaca kolom tersebut, apa tipe akhir vektor `raw_bp`? 
2. Jika fungsi hilir memaksakan konversi tipe menggunakan `as.numeric(raw_bp)`, nilai apa yang dihasilkan pada elemen `"NULL"`, dan bagaimana status atribut peringatan (*warning*) R di lingkungan batch non-interaktif?
3. Rancang sebuah fungsi validasi dan sanitasi vektor yang menjamin *type-safety* tingkat tinggi (menggagalkan proses jika rasio koersi ilegal melebihi ambang tertentu) serta mengisolasi anomali data sebelum tahap komputasi tervektorisasi dijalankan.

---

### Skenario C: Trade-off Arsitektural: Matrix vs Flat Vector vs Data Frame untuk High-Frequency Scoring
Anda ditugaskan mendesain mesin komputasi *in-memory scoring* yang harus melayani perhitungan inferensi matriks bobot model linear terhadap fitur secara berulang:

$$\mathbf{y} = \mathbf{X}\mathbf{w}$$

Ukuran batch input $\mathbf{X}$ adalah $100.000$ baris dengan $50$ variabel numerik. Pipeline ini dieksekusi 100 kali per detik. Tim Anda memperdebatkan 3 struktur data penyimpan $\mathbf{X}$:
* **Opsi 1**: `data.frame` standar R dengan 50 kolom vektor numerik.
* **Opsi 2**: `matrix` numerik 2D ($100.000 \times 50$).
* **Opsi 3**: *Flat atomic vector* 1D berukuran $5.000.000$ elemen dengan kalkulasi indeks berbasis *striding* manual: $\text{index}(i, j) = (j - 1) \times \text{nrows} + i$.

**Pertanyaan Diagnostik:**
1. Bedah representasi memori internal dari ketiga opsi tersebut (apakah *contiguous memory block* atau pointer dereferencing)?
2. Analisis bagaimana CPU cache-miss (L1/L2/L3) dan integrasi library aljabar linier (BLAS/LAPACK) membedakan performa throughput antara Opsi 1 dan Opsi 2.
3. Kapan Opsi 3 memiliki nilai keunggulan teknis dibanding Opsi 2 di dalam runtime R, dan trade-off apa yang harus dibayar dari segi keterbacaan kode (*maintainability*) dan manipulasi dimensi?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Vectorized Rolling Window Winsorizer

#### Problem Statement
Dalam data finansial kuantitatif (kuotasi harga saham berkecepatan tinggi), lonjakan data ekstrem (*anomalous outliers/spikes*) akibat *glitch* jaringan feed data harus dibersihkan secara instan sebelum masuk ke mesin eksekusi algoritma. Anda diminta membangun engine transformasi data vektor tingkat rendah untuk melakukan **Winsorization** berbasis deviasi mutlak median lokal (*Rolling Median Absolute Deviation - MAD*).

#### Requirements
1. Buat fungsi murni R dengan tanda tangan:
   ```R
   fast_rolling_cleaner(x, window_size = 51L, threshold = 3.0)
   ```
2. **Aturan Winsorization**:
   Untuk setiap elemen $x_i$, hitung median lokal ($M_i$) dan dispersi lokal ($MAD_i$) dalam jendela simetris $[i - k, i + k]$ di mana $k = (\text{window\_size} - 1) / 2$.
   $$\text{MAD}_i = \text{median}(|x_{j} - M_i|), \quad \forall j \in [i-k, i+k]$$
   Jika $|x_i - M_i| > \text{threshold} \times 1.4826 \times \text{MAD}_i$, maka gantikan nilai $x_i$ dengan batas atas/bawah yang diizinkan ($M_i \pm \text{threshold} \times 1.4826 \times \text{MAD}_i$).
3. **Penanganan Tepi**: Pada ujung vektor (awal dan akhir), jendela harus menyesuaikan ukurannya secara dinamis (*truncated window*) tanpa menghasilkan nilai `NA`.

#### Constraints
1. **DILARANG MENGGUNAKAN LIBRARY EKSTERNAL**: Tidak boleh mengimpor package apa pun (seperti `zoo`, `data.table`, `Rcpp`, atau `tidyverse`). Hanya gunakan fungsi bawaan *base R*.
2. **NO EXPONENTIAL MEMORY ALLOCATION**: Tidak boleh menggunakan operasi konkatenasi bertahap (`c()`, `cbind()`, atau `rbind()` di dalam loop).
3. **ZERO UNCHECKED RECYCLING**: Fungsi harus memvalidasi input secara defensif. Jika `x` bukan atomic vector bertipe `double` atau `integer`, eksekusi harus dihentikan dengan pesan error informatif (`stop()`).
4. **PERFORMANCE TARGET**: Fungsi harus mampu memproses vektor acak berukuran $100.000$ elemen dengan `window_size = 51L` dalam waktu kurang dari **1.5 detik** pada mesin standar development.

#### Expected Output
Fungsi harus mengembalikan objek `list` terstruktur yang berisi:
* `cleaned_vector`: Vektor numerik bertipe `double` dengan ukuran yang sama persis seperti input, berisi data yang telah dibersihkan.
* `outliers_detected`: Bilangan bulat (*integer*) yang menunjukkan jumlah elemen yang telah dimodifikasi.
* `execution_time`: Durasi eksekusi algoritma (dalam detik) yang diukur menggunakan `proc.time()`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur memori internal R: struktur `SEXPREC`, alokasi heap pointer, dan pemisahan tipe *atomic vector* vs *generic vector/list*.
- [ ] Siklus Copy-on-Write (CoW), peran penghitung referensi internal (`NAMED`/`REFCNT`), dan pemanfaatan `tracemem()` untuk diagnostik mutasi objek.
- [ ] Aturan pasti *vector recycling* R, baik kasus modulo nol maupun non-nol, serta bahaya penurunan akurasi kalkulasi saintifik yang dihasilkannya.
- [ ] Urutan *coercion hierarchy* implisit dan dampaknya terhadap memori serta efisiensi eksekusi saat terjadi percampuran tipe data.
- [ ] Mengapa ALTREP membuat pembuatan deret angka besar menjadi *zero-memory footprint* dan operasi apa yang memaksa ALTREP melakukan materialisasi ke memori riil.
- [ ] Karakteristik *Three-Valued Logic* R (`TRUE`, `FALSE`, `NA`) dan bagaimana propagasi nilai `NA` memengaruhi pengindeksan vektor.
- [ ] Keterbatasan representasi floating-point IEEE 754 pada vektor R numerik dan implementasi perbandingan menggunakan `all.equal()` atau batas toleransi epsilon.

### Saya tidak perlu menghafal:
- [ ] Seluruh kode heksadesimal representasi bit dari setiap `SEXPTYPE` di file header C R (`Rinternals.h`).
- [ ] Nilai numerik presisi tinggi dari konstanta mesin internal seperti `.Machine$double.eps` hingga digit terakhir.
- [ ] Setiap variasi fungsi internal berbasis titik ganda/tiga (`.Internal`, `.Primitive`, `.Call`) yang tidak diperuntukkan bagi konsumsi publik.

### Saya harus bisa melakukan:
- [ ] Memeriksa struktur, tipe alokasi, dan ukuran memori vektor menggunakan `str()`, `typeof()`, dan `pryr::object_size` atau `lobstr::obj_size()`.
- [ ] Mengidentifikasi dan memusnahkan penggunaan *vector-growth anti-pattern* (`x <- c(x, val)`) pada kode warisan (*legacy code*).
- [ ] Melakukan pra-alokasi memori vektor (`vector("numeric", length = N)`) untuk menjamin kompleksitas alokasi ruang $O(N)$ sebelum komputasi iteratif.
- [ ] Mengonversi perulangan imperatif kompleks menjadi operasi vektor atau keluarga matriks teroptimasi yang memanfaatkan primitif internal C R.
- [ ] Menulis kode defensive validation yang secara proaktif mencegat kegagalan koersi tipe data sebelum mengeksekusi pipeline komputasi berskala masif.