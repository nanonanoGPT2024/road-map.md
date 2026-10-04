# Bab 02: Struktur Data Inti & Arsitektur Memori R
## Modul 01: Vektor Atomik (*Atomic Vectors*), Koersi Tipe Data, dan Arsitektur Internal SEXP

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis dan membedakan representasi internal 6 tipe vektor atomik R pada tingkat memori C (*underlying C structs*).
- Mengaudit dan mengeliminasi latensi performa akibat *implicit type coercion* dan alokasi memori redundan menggunakan pustaka diagnostik sistem (`lobstr`).
- Memprediksi serta mengontrol mekanisme *Copy-on-Modify* (CoM) dan pemanfaatan kerangka kerja ALTREP (*Alternative Representations*) guna mencegah *Garbage Collection (GC) thrashing* pada manipulasi data skala gigabyte.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah memahami:
- Konsep dasar pointer, alokasi memori *heap* vs *stack*, dan representasi *contiguous memory array* dalam bahasa C.
- Arsitektur eksekusi skrip R dasar dan manipulasi objek via R console/RStudio.
- Paket R `lobstr` terpasang di sistem (`install.packages("lobstr")`).

---

### 3. Concept
R pada dasarnya adalah *interface* tingkat tinggi yang ditulis di atas bahasa C dan Fortran. Seluruh objek di dalam runtime R dibungkus dalam sebuah struktur data C yang seragam bernama **SEXP** (*S-Expression Pointer*). 

SEXP adalah pointer menuju sebuah *struct* C bernama `SEXPREC` (S-expression record). Struktur internal `SEXPREC` memiliki header standar yang memuat:
1. **`sxpinfo`**: Bitfield 64-bit yang menyimpan metadata objek, termasuk tipe SEXP (*SEXPTYPE*, misal `INTSXP`, `REALSXP`), bendera *garbage collector* (`gc_mark`), dan status referensi penanda siklus hidup objek (`REFCNT` atau `NAMED`).
2. **Pointer atribut (`attrib`)**: Pointer ke SEXP lain yang menyimpan daftar atribut objek (seperti `names`, `dim`, atau `class`).
3. **Pointer navigasi memori**: Pointer ke objek SEXP sebelum dan sesudahnya dalam alokator heap R.

```
       Struktur SEXPREC di Level C (Rinternals.h)
+--------------------------------------------------------+
| sxpinfo (64-bit: tipe objek, GC flag, ref count/NAMED) |
+--------------------------------------------------------+
| attrib (Pointer SEXP ke daftar atribut pasangan/pairlist)|
+--------------------------------------------------------+
| gc_next / gc_prev (Pointer doubly linked list milik GC)|
+--------------------------------------------------------+
| Payload Data Array (Pointer ke blok memori kontigu)    |
+--------------------------------------------------------+
```

Vektor atomik adalah struktur fundamental R yang merepresentasikan blok memori contiguous (berurutan) yang menyimpan elemen bertipe seragam (*homogeneous*). R tidak mengenal konsep nilai skalar primitif; angka tunggal seperti `42` secara internal dialokasikan sebagai sebuah vektor atomik dengan panjang 1 (`REALSXP` dengan 1 elemen).

---

### 4. Why
Memahami struktur internal SEXP dan sifat atomik vektor sangat krusial bagi arsitek perangkat lunak dan insinyur data karena:
- **Biaya Overhead Memori**: Setiap vektor R memiliki overhead header minimum sebesar 32 hingga 64 byte terlepas dari berapa banyak data yang disimpannya. Mengalokasikan jutaan vektor berukuran skalar akan memicu fragmentasi memori ekstrem dan beban berat pada Garbage Collector (GC).
- **Penalti Kinerja Akibat Koersi Implisit**: Saat operasi penggabungan atau manipulasi matriks/vektor dilakukan tanpa presisi tipe, R akan melakukan koersi secara diam-diam (*silent coercion*). Proses ini menduplikasi seluruh *payload* array ke blok memori baru bertipe target yang lebih luas, mengubah operasi berkategori $\mathcal{O}(1)$ atau in-place menjadi operasi memori $\mathcal{O}(n)$ yang lambat.
- **Efisiensi Cache CPU**: Karena vektor atomik disimpan secara kontigu di heap, iterasi vektoris sangat ramah terhadap *L1/L2 cache prefetching*. Mempertahankan sifat atomik murni (alih-alih menggunakan linked-list atau generic list SEXP) memaksimalkan SIMD (*Single Instruction, Multiple Data*) throughput pada level prosesor.

---

### 5. What
R mengimplementasikan 6 tipe dasar vektor atomik (*SEXPTYPE*):

| Tipe Vektor Atomik R | Simbol C Internal (`SEXPTYPE`) | Ukuran Per Elemen (Byte) | Deskripsi Representasi Internal |
|---|---|---|---|
| `raw` | `RAWSXP` | 1 | Byte mentah heksadesimal (*unsigned 8-bit char*). |
| `logical` | `LGLSXP` | 4 | Boolean 32-bit (mendukung nilai `TRUE`, `FALSE`, dan `NA_integer_`). |
| `integer` | `INTSXP` | 4 | Signed 32-bit integer (-$2 \times 10^9$ s.d. $2 \times 10^9$). Diakhiri sufiks `L`. |
| `double` | `REALSXP` | 8 | IEEE 754 double precision floating point (64-bit). |
| `complex` | `CPLXSXP` | 16 | Pasangan dua bilangan IEEE 754 (bagian real dan imaginary). |
| `character` | `STRSXP` | 8 (Pointer) | Array pointer ke pool memori global R (*Global String Cache*). |

#### Hirarki Koersi (*Type Coercion Hierarchy*)
Jika Anda mencoba menggabungkan elemen dengan tipe berbeda ke dalam satu vektor atomik tunggal, R memberlakukan aturan *lowest common denominator* tanpa melempar peringatan:

$$\text{raw} \longrightarrow \text{logical} \longrightarrow \text{integer} \longrightarrow \text{double} \longrightarrow \text{complex} \longrightarrow \text{character}$$

Jika terdapat satu elemen bertipe `character`, seluruh elemen lain di dalam vektor tersebut akan dipaksa (*coerced*) menjadi `character`.

---

### 6. How
Berikut adalah alur eksekusi ketika vektor atomik dialokasikan dan dimutasi di dalam memori:

```
[Inisialisasi Objek A]
        |
        v
[Evaluasi Ukuran & Tipe] 
        |
        v
[Heap Allocation: Buat SEXPREC header + Buffer Array Kontigu]
        |
        v
[Penugasan Simbol: Objek A diarahkan ke Alamat Pointer SEXP] (REFCNT = 1)
        |
        v
[Penugasan Objek B <- A] (REFCNT = 2, Shallow Copy: B menunjuk pointer SEXP yang sama)
        |
        v
[Instruksi Modifikasi Elemen B[1] <- Nilai Baru]
        |
        +---> Evaluasi REFCNT:
                 |
                 +---> Jika REFCNT == 1 (In-Place Mutation: Modifikasi buffer langsung)
                 |
                 +---> Jika REFCNT > 1 (Copy-on-Modify):
                          |
                          v
                       [Alokasikan SEXPREC + Array baru di Heap]
                          |
                          v
                       [Salin seluruh elemen lama + terapkan mutasi]
                          |
                          v
                       [Objek B diarahkan ke pointer SEXP baru]
                          |
                          v
                       [Dekremen REFCNT pada objek A menjadi 1]
```

Sejak R versi 3.5.0, kerangka kerja **ALTREP** (*Alternative Representations*) diterapkan untuk deret vektor integer seperti `1:1e9`. R tidak lagi mengalokasikan memori fisik sebesar $\approx 4\text{ GB}$ untuk menyimpan satu miliar bilangan bulat, melainkan hanya menyimpan *metadata batas awal dan akhir* (kompresi representasi metadata konstan $\mathcal{O}(1)$). Namun, jika ada operasi mutasi C-level yang tidak mendukung ALTREP menulis ke vektor tersebut, R akan melakukan *materialization* paksa ke memori fisik secara penuh.

---

### 7. Analogy
Bayangkan sebuah kotak pensil kayu kompartemen khusus (*Atomic Vector*):
- Setiap slot dirancang dengan dimensi yang presisi sama persis; misal, hanya muat tabung silinder logam berdiameter 4mm (*integers*).
- Semua tabung tertata berjajar rapat bersentuhan tanpa ada ruang kosong (*contiguous memory*).
- Jika Anda ingin memasukkan sebuah buku catatan tebal (*character*) ke dalam kotak pensil tersebut, sistem tidak akan memperluas satu slot saja. Sistem akan **membuang kotak pensil tersebut**, mengambil koper besar (*character array*), lalu membungkus setiap tabung silinder kecil tadi ke dalam bentuk buku cetak berlabel angka, sebelum menyimpannya bersama buku catatan baru Anda.

---

### 8. Diagram
Diagram arsitektur memori antara *Shallow Copy* vs *Copy-on-Modify*:

```
1. Keadaan Awal (Binding x)
x ----> [ SEXPREC Header: INTSXP | REFCNT: 1 ]
        [ Data Pointer ] ---------------------> [ 10L | 20L | 30L ] (Heap Buffer)

2. Shallow Copy (Binding y <- x)
x ----> [ SEXPREC Header: INTSXP | REFCNT: 2 ]
y ----' [ Data Pointer ] ---------------------> [ 10L | 20L | 30L ] (Buffer yang sama)

3. Modifikasi (y[1] <- 99L) memicu Deep Copy karena REFCNT > 1:
x ----> [ SEXPREC Header: INTSXP | REFCNT: 1 ]
        [ Data Pointer ] ---------------------> [ 10L | 20L | 30L ] (Data asli)

y ----> [ SEXPREC Header: INTSXP | REFCNT: 1 ]
        [ Data Pointer ] ---------------------> [ 99L | 20L | 30L ] (Buffer alokasi baru)
```

---

### 9. Simple Example
Kode berikut membedah alamat memori objek sebelum dan sesudah mutasi untuk memverifikasi mekanisme *Copy-on-Modify* serta *Silent Coercion*:

```R
library(lobstr)

# 1. Alokasi Integer Vector
x <- c(10L, 20L, 30L)
cat("Tipe data asli x:", typeof(x), "\n")
cat("Alamat memori awal x:", obj_addr(x), "\n")

# 2. Binding baru (Shallow Copy)
y <- x
cat("Alamat memori y (Shallow binding):", obj_addr(y), "\n")
# Alamat x dan y identik

# 3. Mutasi memicu Copy-on-Modify
y[1] <- 99L
cat("Alamat memori y setelah modifikasi:", obj_addr(y), "\n")
# Alamat y berubah (Deep Copy dilakukan)

# 4. Silent Coercion: Memasukkan tipe double ke integer vector
cat("Tipe data x sebelum insersi:", typeof(x), "\n")
x[2] <- 3.14159
cat("Tipe data x setelah insersi double:", typeof(x), "\n")
# Seluruh elemen x berubah menjadi REALSXP (double)
print(x)
```

---

### 10. Practical Example
Berikut adalah implementasi fungsi ekstraksi dan normalisasi performa tinggi untuk memproses telemetri numerik sensor mentah tanpa memicu *memory-leak* atau *silent coercion* di loop komputasi:

```R
library(lobstr)

normalize_sensor_stream <- function(raw_readings, scale_factor = 1.0) {
  # Validasi defensif tipe dasar pada level SEXP
  if (!is.integer(raw_readings) && !is.double(raw_readings)) {
    stop("Input harus berupa vektor atomik numerik homogen (INTSXP/REALSXP)")
  }
  
  len <- length(raw_readings)
  if (len == 0L) return(numeric(0L))
  
  # Pre-alokasi buffer keluaran untuk mencegah reallocation amortized overhead
  # numeric() mengalokasikan REALSXP kontigu yang bersih
  normalized_buffer <- vector(mode = "double", length = len)
  
  # Lakukan tracking memori untuk memastikan in-place loop
  cat("Memory address of target buffer:", obj_addr(normalized_buffer), "\n")
  
  # Operasi tervektorisasi: Eksekusi langsung di C-level array looping
  # Hindari loop R implisit: normalized_buffer <- raw_readings * scale_factor
  # Menggunakan pemanggilan primitif untuk efisiensi
  normalized_buffer <- raw_readings * as.double(scale_factor)
  
  cat("Memory address post-vectorization:", obj_addr(normalized_buffer), "\n")
  return(normalized_buffer)
}

# Simulasi data mentah (1 juta observasi tipe integer)
sensor_data <- as.integer(rpois(n = 1e6, lambda = 50))

# Eksekusi pipeline
mem_before <- mem_used()
clean_data <- normalize_sensor_stream(sensor_data, scale_factor = 0.001)
mem_after <- mem_used()

cat("Delta Memori Heap:", (mem_after - mem_before) / (1024^2), "MB\n")
```

---

### 11. Real World Example
**Skenario**: Sistem Rekonsiliasi Transaksi Keuangan *High-Frequency Trading* (HFT).
Perusahaan memproses puluhan juta log transaksi per jam. Log transaksi memiliki kolom *trade volume* (integer), *order price* (floating point double), dan *flag routing* (logical). Masalah kritis muncul ketika script R lama melakukan pengelompokan menggunakan `c()` yang secara tidak sengaja menggabungkan *order ID* bertipe teks ke dalam matriks numerik, atau memasukkan nilai string `"NULL"` ke dalam array volume.

**Dampak Lapangan**:
1. Seluruh dataset numerik sebesar 15 GB berubah menjadi `STRSXP` (vektor karakter).
2. Memori server membengkak dari 15 GB menjadi lebih dari 85 GB akibat overhead alokasi pointer string pada Global String Pool.
3. Garbage collector R macet (*GC freeze*) selama 45 detik, menyebabkan timeout pada sistem monitoring kepatuhan pasar (*regulatory latency breach*).

**Solusi Arsitektural**:
Sistem dirombak dengan memastikan *strict type-enforcement* sebelum alokasi array, menjaga agar metrik harga dan volume tetap murni pada tingkat `INTSXP` dan `REALSXP`, serta mengisolasi string metadata pada struktur terpisah (*data.frame* atau representasi berbasis C/C++ via `Rcpp`).

---

### 12. Trade-offs

| Aspek Arsitektur | Keuntungan | Kerugian | Kompleksitas | Dampak Performa | Biaya Komputasi / Memori |
|---|---|---|---|---|---|
| **Vektor Atomik Kontigu** | Sangat cepat diakses secara sekuensial, CPU *cache locality* tinggi, kompatibel dengan pustaka BLAS/LAPACK. | Ukuran dan tipe bersifat kaku (*homogeneous*). Operasi *insert* di tengah array bernilai $\mathcal{O}(n)$. | Rendah | Maksimal untuk komputasi numerik. | Minimal per elemen (4-8 byte), optimal untuk data masif. |
| **Generik Objek (List SEXP)** | Mampu menampung tipe data heterogen dan struktur hierarkis bertingkat. | Indireksi pointer ganda, alokasi memori tersebar (*poor cache locality*). | Sedang | Penurunan kecepatan drastis pada pemrosesan larik numerik murni. | Overhead 8 byte per pointer + header SEXP per elemen anak. |
| **Mutasi In-Place vs Copy-on-Modify** | Memastikan *functional purity* dan referential transparency (aman dari *side-effects*). | Duplikasi memori mendadak saat memodifikasi objek bersama (*shared references*). | Rendah secara abstraksi developer; Tinggi di tingkat VM R. | Berpotensi memicu *GC spikes* jika mutable operations tidak terkontrol. | Konsumsi RAM dapat melonjak $2\times$ lipat selama alokasi buffer baru. |

---

### 13. When To Use
- Gunakan **vektor atomik integer (`INTSXP`)** untuk indeks ID, cacah diskrit, dan variabel kategorikal ordinal (faktor) untuk memotong penggunaan memori hingga 50% dibanding `double`.
- Gunakan **vektor atomik double (`REALSXP`)** secara eksklusif untuk seluruh komputasi analitik, statistik matematis, koordinat kontinu, dan model machine learning.
- Gunakan **vektor atomik raw (`RAWSXP`)** untuk penanganan serialisasi protokol jaringan (misalnya buffer gRPC, raw network sockets, atau pembacaan stream biner file parq/feather) demi menghindari overhead string encoding UTF-8.

---

### 14. When NOT To Use
- Jangan gunakan vektor atomik jika data bersifat heterogen (memiliki campuran string, angka, dan boolean secara konseptual dalam satu baris entitas). Gunakan `list` atau pustaka berbasis kolom seperti `data.table` / `tibble`.
- Jangan gunakan manipulasi vektor atomik manual untuk struktur data dinamis yang sering menyisipkan atau menghapus elemen di tengah antrean (antrean FIFO/LIFO). Gunakan lingkungan berpointer khusus (*Environments*) atau representasi struktur data C++ lewat `Rcpp`.
- Hindari penggunaan vektor atomik bertipe `character` masif untuk melakukan pencarian berbasis kunci (*hash lookups*); R harus melintasi hashing string table yang memiliki batas throughput.

---

### 15. Common Mistakes
1. **Mengembangkan Vektor Secara Bertahap di Dalam Loop (*Dynamic Vector Growth*)**:
   ```R
   # BURUK: Mengalokasikan ulang memori O(n^2)
   vec <- c()
   for(i in 1:100000) {
     vec <- c(vec, i) # Memicu duplikasi memori di setiap iterasi
   }
   
   # BAIK: Pre-allocation O(n)
   vec <- vector("integer", 100000L)
   for(i in 1:100000) {
     vec[i] <- i
   }
   ```
2. **Koersi Ambigu dari Bilangan Bulat**:
   Secara *default*, angka yang diketikkan di R seperti `x <- 1` adalah bertipe `double` (`REALSXP`), bukan `integer` (`INTSXP`). Penulisan `1` alih-alih `1L` memaksa konversi tak perlu jika berinteraksi dengan API C yang menuntut integer sejati.
3. **Mengabaikan Tipikal NA**:
   `NA` bawaan di R sebenarnya adalah sebuah vektor berjenis `logical` dengan panjang 1 (`NA_logical_`). Memasukkan `NA` ke dalam vektor integer dapat mengubah konteks tipe jika dilakukan secara ceroboh dalam beberapa modul wrapper C internals. Gunakan nilai spesifik: `NA_integer_`, `NA_real_`, atau `NA_character_`.

---

### 16. Best Practices (Production Checklist)
- [ ] Selalu definisikan tipe bilangan bulat secara eksplisit menggunakan sufiks `L` (contoh: `target_size <- 500000L`).
- [ ] Deklarasikan buffer array dengan ukuran pasti sebelum menjalankan loop komputasi menggunakan `vector(mode = "...", length = n)`.
- [ ] Manfaatkan `typeof()` untuk memeriksa representasi level C SEXP, bukan hanya mengandalkan `class()` atau `mode()`.
- [ ] Pastikan input numerik bebas dari tipe `character` sebelum dimasukkan ke dalam pipeline aljabar linier menggunakan `is.numeric()` dan penegasan `stopifnot()`.
- [ ] Pantau perilaku duplikasi memori pada modul kritis menggunakan `tracemem(x)` selama fase integrasi pengujian performa.

---

### 17. Troubleshooting

#### Masalah: *Silent Coercion* Mengakibatkan Output Salah pada Ekstraksi Data
- **Gejala**: Perhitungan agregasi statistik (`mean`, `sum`) mengembalikan `NA` atau melempar *error*: `Error in sum(x): invalid 'type' (character) of argument`.
- **Investigasi**:
  Jalankan pelacakan tipe dengan fungsi `lobstr::sxp()`:
  ```R
  x <- c(1L, 2L, "3")
  lobstr::sxp(x)
  # Menunjukkan SEXPTYPE: STRSXP alih-alih INTSXP
  ```
- **Solusi**: Terapkan *type guard* dan isolasi parsir string:
  ```R
  safe_int_conversion <- function(vec) {
    if (is.character(vec)) {
      parsed <- as.integer(vec)
      if (any(is.na(parsed) & !is.na(vec))) {
        stop("Data corruption detected: Silent coercion failure during character parsing")
      }
      return(parsed)
    }
    return(as.integer(vec))
  }
  ```

#### Masalah: Ledakan Alokasi Memori Akibat *Broken ALTREP*
- **Gejala**: Kode `x <- 1:1e9` berjalan instan, namun pemanggilan `x[1] <- 1L` langsung membekukan sistem dan R crash dengan pesan: `vector memory exhausted (limit reached?)`.
- **Investigasi**: Objek `1:1e9` adalah *compact ALTREP integer vector* (0 byte data fisik). Operasi modifikasi elemen `x[1] <- 1L` memaksa sistem mengubah representasi kompak metadata menjadi representasi array datar utuh (*materialization*) yang memerlukan $10^9 \times 4 \text{ byte} \approx 4\text{ GB}$ memori secara instan.
- **Solusi**: Jangan pernah melakukan modifikasi in-place parsial pada ALTREP sequences berskala besar. Gunakan pustaka berbasis partisi streaming atau pemetaan memori (*memory mapped files*) seperti `bigmemory` atau `arrow`.

---

### 18. Exercise
Selesaikan 3 tugas berikut secara presisi:

1. **Investigasi SEXP Header**: Buat vektor logika `c(TRUE, FALSE, TRUE)`. Gunakan fungsi `lobstr::sxp()` untuk mencatat tipe C (*SEXPTYPE*), panjang objek, dan status atributnya.
2. **Eksperimen Pemutusan Shallow Copy**: 
   - Buat vektor double `a <- runif(1e5)`.
   - Lakukan assignment `b <- a`.
   - Gunakan `lobstr::obj_addr()` untuk memverifikasi bahwa alamat memori `a` dan `b` identik.
   - Modifikasi satu elemen `b[500] <- 0.0`.
   - Tunjukkan bahwa alamat memori `b` telah berpindah ke heap address baru sementara `a` tetap utuh.
3. **Optimasi Buffer Pre-allocation**: Tulis skrip komparasi waktu eksekusi (menggunakan `system.time()`) antara:
   - Pendekatan A: Membuat vektor integer 1 hingga $500.000$ menggunakan penggabungan loop bertahap `vec <- c(vec, i)`.
   - Pendekatan B: Pre-alokasi buffer dengan `integer(500000L)` dan pengisian indeks secara terisolasi.

---

### 19. Challenge
Rancang sebuah fungsi R murni bernama `matrix_vector_coercion_guard(vec_list)` yang menerima input sebuah `list` yang berisi 100 vektor atomik dengan panjang yang bervariasi:
1. Fungsi harus mengevaluasi seluruh SEXP dari sub-vektor tersebut tanpa menduplikasi data di heap (*zero-copy validation*).
2. Jika ada satu atau lebih sub-vektor yang berjenis selain numerik (`INTSXP` atau `REALSXP`), fungsi harus menggugurkan operasi dan melempar *exception* yang merinci indeks vektor yang tidak patuh beserta tipe internal C aslinya.
3. Jika seluruhnya valid, fungsi harus mengidentifikasi apakah terdapat potensi *silent coercion* (jika ada campuran `integer` dan `double`) dan secara otomatis menstandarkan tipe data ke `double` menggunakan alokasi sekuensial yang menjamin memori tetap kontigu tanpa fragmentasi GC, mengembalikan matriks dua dimensi terpadu. Sertakan pengukuran jejak memori via `tracemem` untuk memvalidasi efisiensi alokasi Anda.

---

### 20. Summary
- **SEXP (`SEXPREC`)** adalah pondasi utama runtime R; semua objek, termasuk skalar, sebenarnya adalah ekspresi pointer berorientasi objek C dengan metadata yang substansial.
- **Vektor Atomik** menjamin alokasi kontigu seragam (*homogeneous*), memfasilitasi operasi vektorisasi yang dioptimalkan untuk perangkat keras modern (*cache hits* dan SIMD).
- **Aturan Koersi Implisit** R bekerja berjenjang menuju tipe yang paling ekspresif (`character`). Ketidaktahuan atas mekanisme ini berpotensi memicu lonjakan alokasi heap dan memperlambat latensi komputasi dari level microsecond ke level second.
- **Copy-on-Modify (CoM)** menjaga integritas fungsional objek R dengan menunda duplikasi fisik data hingga terjadi modifikasi destruktif pada objek yang memiliki banyak referensi (*multiple references*). Mengelola pre-alokasi buffer dan struktur ALTREP secara benar adalah kunci mencapai kode komputasi berperforma tinggi di skala produksi.