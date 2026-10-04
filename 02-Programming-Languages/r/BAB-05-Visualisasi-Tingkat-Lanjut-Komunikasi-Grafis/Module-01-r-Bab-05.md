# Bab 05 Module 01: Arsitektur Manipulasi Data Kinerja Tinggi: Evaluasi Non-Standar, Indexing Radix B-Tree, dan Mutasi In-Place Menggunakan `data.table`

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda memiliki kemampuan praktis dan terukur untuk:
*   Mendiagnosis dan mengeliminasi alokasi memori redundan $O(N)$ yang disebabkan oleh semantik *Copy-on-Write* (COW) bawaan R menggunakan operator mutasi referensial (`:=`).
*   Mengimplementasikan operasi pengindeksan sekunder dan *binary search join* berbasis algoritma *radix sort* untuk mereduksi kompleksitas pencarian dari $O(N)$ ke $O(\log N)$ pada dataset berukuran puluhan juta baris.
*   Mengoptimalkan agregasi data skala multi-gigabyte menggunakan internal idiom `.SD` (*Subset of Data*) dan `.I` yang digabungkan dengan fungsi C-level yang ter-vektorisasi penuh tanpa overhead alokasi *heap*.
*   Mendesain arsitektur transformasi data yang deterministik, aman terhadap *pointer aliasing*, dan memenuhi *Service Level Agreement* (SLA) waktu komputasi di lingkungan produksi dengan sumber daya memori terbatas.

---

### 2. Prerequisite
Untuk memahami materi ini secara mendalam, Anda wajib menguasai:
*   **Internal Memori R:** Pemahaman tentang representasi struktur data C di R (`SEXPREC`, `VECSXP`), penanda referensi (`NAMED` / `REFCNT`), dan mekanisme kerja *Garbage Collector* (GC).
*   **Pemrograman R Tingkat Menengah:** Penggunaan `environment`, penanganan *closure*, serta vektorisasi dasar.
*   **Algoritma & Struktur Data:** Konsep *hash map*, *radix sorting*, kompleksitas asimptotik Big-O, serta konsep pointer memori.
*   **Tooling Profiling:** Penggunaan `tracemem()` bawaan R atau paket `lobstr` untuk inspeksi alamat memori secara langsung.

---

### 3. Concept
Dalam implementasi standar R (`base::data.frame`), struktur tabular direpresentasikan sebagai *named list* yang berisi vektor-vektor dengan panjang yang sama (`VECSXP`). Ketika modifikasi dilakukan pada salah satu kolom data frame, arsitektur dasar R mengevaluasi nilai hitungan referensi (`REFCNT`). Jika objek dibagikan atau dipanggil dalam cakupan fungsi, mekanisme *Copy-on-Write* (COW) terpicu:

$$\text{data.frame Modifikasi: } \text{Memory Allocation} = O(N \times K)$$
di mana $N$ adalah jumlah baris dan $K$ adalah jumlah kolom yang terdokumentasi dalam tabel simbolik.

`data.table` memutus keterbatasan struktural ini dengan mengintervensi langsung tabel alokasi vektor pada C-level. Konsep fundamental yang menopang arsitektur ini meliputi:

1.  **Over-allocation Kolom (`truelength`):** Saat `data.table` diinisialisasi, sistem mengalokasikan slot pointer kolom ekstra (secara *default* 1024 slot penunjuk kosong di luar ukuran aslinya). Hal ini memungkinkan penambahan kolom baru secara langsung ke dalam array pointer `VECSXP` tanpa perlu merealokasi seluruh list pembungkus.
2.  **Mutasi In-Place (Modifikasi Melalui Referensi):** Melalui operator `:=` dan fungsi primitif `set()`, `data.table` mengeksekusi manipulasi data dengan menulis langsung ke segmen memori fisik yang dialokasikan untuk vektor target, memotong *evaluation graph* R standar dan mengabaikan batas duplikasi objek.
3.  **Algoritma Radix Sorting dan Binary Search:** Saat menggunakan `setkey()` atau indeks sekunder (`setindex()`), `data.table` tidak membuat hash index yang boros memori. Sebagai gantinya, ia membangun indeks terurut menggunakan *two-pass radix sort* ($O(N)$ linear time). Query data terfilter selanjutnya dievaluasi menggunakan *binary search* berkecepatan tinggi ($O(\log N)$), menggantikan operasi *vector scan* standar ($O(N)$).

---

### 4. Why
Dalam rekayasa data produksi (misalnya pemrosesan log transaksi perbankan, telemetri IoT, atau data pasar modal), dataset sering kali berukuran antara 5 GB hingga 100 GB. Penggunaan `base::data.frame` atau framework yang murni berbasis *immutable paradigm* seperti `dplyr` standar (tanpa backend database) menimbulkan masalah operasional kritis:

*   **Memory Spikes & OOM (Out Of Memory):** Duplikasi implisit saat transformasi kolom memaksa sistem membutuhkan RAM 2 hingga 4 kali lipat dari ukuran dataset aktual. Hal ini memicu *crash* OOM pada container cloud (misalnya AWS ECS/Kubernetes pods).
*   **Overhead Garbage Collection:** Alokasi dan dealokasi objek sementara secara masif membebani GC R yang berjalan secara *single-threaded*, menyebabkan jeda eksekusi (*GC pauses*) yang tidak dapat diprediksi.
*   **Cache Locality:** Vektor yang dialokasikan ulang secara konstan kehilangan keuntungan *CPU L1/L2/L3 cache locality*, yang secara drastis memperlambat throughput manipulasi data numerik.

`data.table` mengatasi persoalan ini dengan menyediakan waktu eksekusi deterministik, jejak memori yang stabil (flat RAM consumption profile), dan pemrosesan multi-threading otomatis berbasis OpenMP.

---

### 5. What
Komponen inti pembentuk sintaksis dan arsitektur `data.table` terangkum dalam ekspresi kanonikal:

$$\mathbf{DT}[i, \, j, \, by]$$

*   **Argument $i$ (Query Engine):** Menangani pemfilteran baris (*row slicing*) atau penggabungan (*join*). Jika argumen $i$ mendeteksi kunci yang diindeks, ia beralih dari pemindaian vektor skalar ke *binary search match*.
*   **Argument $j$ (Projection & Modification Engine):** Menentukan apa yang harus dilakukan terhadap data terpilih. Mendukung evaluasi non-standar (*Non-Standard Evaluation* / NSE). Melalui operator `:=`, $j$ melakukan mutasi in-place atau kalkulasi teragregasi.
*   **Argument $by$ (Split-Apply-Combine Engine):** Melakukan agregasi data per kelompok. Menghindari pembagian fisik tabel menjadi list sub-tabel terpisah, melainkan menghitung offset indeks baris secara langsung menggunakan radix sorting.
*   **Simbol Khusus (.SD, .BY, .N, .I, .GRP):**
    *   `.SD` (*Subset of Data*): Objek `data.table` dinamis yang merepresentasikan data dari kelompok saat ini untuk kolom-kolom yang tidak termasuk dalam argumen $by$.
    *   `.I`: Vektor integer yang memetakan indeks baris global dari tabel induk.
    *   `.N`: Skalar integer yang merepresentasikan jumlah baris dalam grup target.
    *   `.BY`: List nilai penentu grup saat ini.

---

### 6. How
Alur pemrosesan data internal `data.table` berlangsung melalui tahapan sistematis berikut:

```
[Input Data] 
    │
    ▼
[Inisialisasi Tabel & Over-Allocation: alloc.col()]
    │  (Menyiapkan truelength = length + 1024 slots)
    ▼
[Parsing Ekspresi DT[i, j, by]]
    ├── 1. Parsing Evaluasi Non-Standar (NSE) via substitute()
    ├── 2. Deteksi Indeks pada argumen 'i'
    │       ├── Jika Key/Index ditemukan -> Binary Search Engine
    │       └── Jika Polos -> Vectorized Vector Scan
    ├── 3. Pengelompokan baris pada argumen 'by'
    │       └── Penghitungan vektor order via Radix Sort C-routine
    └── 4. Evaluasi j (Proyeksi / Assignment)
            ├── Jika Menggunakan ':='
            │     └── Mutasi In-Place via Pointer Manipulation (Zero Copy)
            └── Jika Menggunakan List Agregasi
                  └── Eksekusi loop C-level pada sub-vektor yang dialokasikan
    │
    ▼
[Hasil Termutasi / Output Objek Baru]
```

Langkah operasional:
1.  **Ekspresi `DT[i, j, by]` Diterima:** Interpreter R meneruskan argumen tanpa evaluasi awal berkat *lazy evaluation*.
2.  **Resolusi Indeks:** Argumen $i$ dievaluasi dalam cakupan *environment* tabel. Jika kondisi melibatkan kolom yang terdaftar di `setkey()`, pointer b-tree lookup memotong traversal memori.
3.  **Partisi Grup:** Jika argumen $by$ diisi, C-level routine `forder()` menghasilkan vektor integer posisi offset unik tanpa menduplikasi data payload.
4.  **Eksekusi Mutasi/Kalkulasi:** 
    *   Apabila operator `:=` dideteksi pada $j$, C-level function `assign()` memodifikasi array buffer memori secara atomik.
    *   Apabila agregasi dipanggil, kompilasi sub-query dieksekusi secara berurutan atau paralel via OpenMP threads.

---

### 7. Analogy
Bayangkan **Base R (`data.frame`)** sebagai sebuah **Buku Ensiklopedia Fisik Berjilid**:
Ketika Anda ingin merevisi satu angka pada halaman 400, aturan mewajibkan juru tulis menyalin ulang seluruh bab atau mencetak edisi buku baru secara utuh di lembar kertas baru, lalu membakar buku lama. Proses ini sangat memakan waktu, menghabiskan banyak stok kertas (RAM), dan membuang energi juru tulis (*CPU & Garbage Collector*).

Sebaliknya, **`data.table`** adalah **Papan Tulis Whiteboard Interaktif dengan Daftar Indeks**:
Whiteboard memiliki slot-slot penunjuk yang telah dipersiapkan sebelumnya (*over-allocated slots*). Saat Anda ingin mengubah nilai pada posisi tertentu, teknisi langsung menghapus angka pada koordinat memori tersebut menggunakan spidol dan menuliskan angka baru secara instan (*in-place update*). Tidak ada papan tulis baru yang dibuat; posisi dan fisik papan tulis tetap identik.

---

### 8. Diagram
Diagram alokasi memori berikut menunjukkan perbedaan absolut antara modifikasi Base R COW dengan `data.table` *Reference Modification*:

#### Base R: Copy-on-Write (COW)
```
Sebelum Modifikasi:
Symbol 'df' ───> [ VECSXP Header: 0x001A ] ───> Col1: [ 0x002A | Data: 1, 2, 3 ]
                                            ───> Col2: [ 0x003A | Data: A, B, C ]

Modifikasi: df$Col1[1] <- 99
Sesudah Modifikasi:
Symbol 'df' ───> [ VECSXP Header: 0x009F ] (ALOKASI BARU)
                 ├───> Col1: [ 0x008F | Data: 99, 2, 3 ] (DUPLIKASI TOTAL)
                 └───> Col2: [ 0x003A | Data: A, B, C ] (Shared / Shallow Copy)
*Memori membengkak seketika, pointer root berubah.
```

#### `data.table`: In-Place Pointer Update via `:=`
```
Sebelum Mutasi:
Symbol 'DT' ───> [ VECSXP Header: 0x001A ] (truelength: 1028)
                 ├───> Col1: [ 0x002A | Data: 1, 2, 3 ]
                 └───> Col2: [ 0x003A | Data: A, B, C ]

Mutasi: DT[1, Col1 := 99]
Sesudah Mutasi:
Symbol 'DT' ───> [ VECSXP Header: 0x001A ] (TIDAK BERUBAH)
                 ├───> Col1: [ 0x002A | Data: 99, 2, 3 ] (NILAI DIUBAH IN-PLACE)
                 └───> Col2: [ 0x003A | Data: A, B, C ] (TIDAK BERUBAH)
*Alokasi memori = 0 bytes, pointer root dan vektor tetap sama.
```

---

### 9. Simple Example
Kode demonstrasi di bawah membuktikan mutasi memori in-place via verifikasi pointer alamat heksadesimal:

```R
library(data.table)

# Inisialisasi data.table
dt <- data.table(
  id = 1:5,
  metrik = c(10.5, 20.1, 15.3, 40.2, 50.8)
)

# Tangkap alamat memori awal
addr_awal_objek <- address(dt)
addr_awal_kolom <- address(dt$metrik)

message(sprintf("Alamat Awal Objek: %s", addr_awal_objek))
message(sprintf("Alamat Awal Kolom 'metrik': %s", addr_awal_kolom))

# Mutasi In-Place: Menambahkan nilai skalar ke baris tertentu tanpa alokasi baru
dt[id > 2, metrik := metrik * 1.10]

# Tangkap alamat memori pasca mutasi
addr_akhir_objek <- address(dt)
addr_akhir_kolom <- address(dt$metrik)

message(sprintf("Alamat Akhir Objek: %s", addr_akhir_objek))
message(sprintf("Alamat Akhir Kolom 'metrik': %s", addr_akhir_kolom))

# Verifikasi Deterministik
stopifnot(addr_awal_objek == addr_akhir_objek)
stopifnot(addr_awal_kolom == addr_akhir_kolom)
# Terbukti: Struktur data dimodifikasi langsung pada segmen memori yang sama.
```

---

### 10. Practical Example
Berikut adalah modul transformasi data produksi: pembersihan log transaksi e-commerce, kalkulasi metrik analitik agregasi, dan pengayaan data via *binary search join*.

```R
library(data.table)

# Konfigurasi Threads Engine untuk Skalabilitas Multicore
setDTthreads(threads = 0) # 0 menginstruksikan penggunaan semua core fisik yang tersedia

transformasi_transaksi_fintech <- function() {
  # 1. Bangun Data Simulasi Transaksi (5 Juta Data Points)
  n_records <- 5e6
  set.seed(42)
  
  transaksi_dt <- data.table(
    trx_id = 1:n_records,
    user_id = sample(1:50000, n_records, replace = TRUE),
    nominal = round(runif(n_records, 1000, 5000000), 2),
    status = sample(c("SUCCESS", "PENDING", "FAILED"), n_records, replace = TRUE, prob = c(0.85, 0.10, 0.05)),
    timestamp = as.POSIXct("2026-01-01 00:00:00", tz = "UTC") + sample(1:2592000, n_records, replace = TRUE)
  )

  # 2. Metadata Pengguna untuk Enrichment
  user_metadata <- data.table(
    user_id = 1:50000,
    segment = sample(c("PLATINUM", "GOLD", "REGULAR"), 50000, replace = TRUE, prob = c(0.05, 0.25, 0.70)),
    risk_level = sample(c("LOW", "MEDIUM", "HIGH"), 50000, replace = TRUE)
  )

  # 3. Optimasi Indexing: Mengaktifkan Radix Sort Primary Key
  setkeyv(transaksi_dt, c("user_id", "status"))
  setkey(user_metadata, user_id)

  # 4. Filter, Mutasi In-Place, dan Operasi Waktu
  # Tambahkan kolom flag transaksi abnormal (> 4.5 juta) secara in-place
  transaksi_dt[, is_high_value := (nominal > 4500000.00)]
  
  # Ekstraksi komponen tanggal secara vectorized via IDate (Optimasi C-Int Internal)
  transaksi_dt[, trx_date := as.IDate(timestamp)]

  # 5. Agregasi Kinerja Tinggi: Menghitung Metrik Konsolidasi per Segmen
  # Menggunakan Fast Radix Aggregation
  agregasi_metrik <- transaksi_dt[
    status == "SUCCESS", 
    .(
      total_volume = sum(nominal),
      avg_volume   = mean(nominal),
      trx_count    = .N,
      high_val_cnt = sum(is_high_value)
    ), 
    by = .(user_id)
  ]

  # 6. Binary Search Equi-Join Menggunakan Sintaks Penunjuk On-The-Fly
  # Menggabungkan ringkasan transaksi dengan metadata profil pengguna
  hasil_final <- user_metadata[agregasi_metrik, on = .(user_id), nomatch = NULL]

  # 7. Mutasi Turunan Lanjutan: Rasio Transaksi High-Value
  hasil_final[, ratio_high_value := high_val_cnt / trx_count]

  return(hasil_final)
}

# Eksekusi Pipeline Berstandar Industri
pipeline_output <- transformasi_transaksi_fintech()
print(head(pipeline_output, 5))
```

---

### 11. Real World Example
**Studi Kasus: Sistem Deteksi Fraud Real-Time Ad-Tech (Pemrosesan 60 Juta Klik/Hari)**

*   **Masalah Arsitektural:** Sebuah platform monetisasi digital menerima *click-stream payload* sebesar 12 GB per jam. Pipeline berbasis `base R / pandas` mengalami latensi komputasi parah: proses pembersihan, join dengan profil *blacklisted-IP*, dan rolling aggregation 5-menit memakan waktu 48 menit, menyisakan margin waktu yang sangat sempit sebelum batch jam berikutnya tiba. Kegagalan memori (OOM) terjadi rata-rata 3 kali sehari ketika memori heap container melonjak di atas 64 GB akibat kloning implisit.
*   **Solusi Rekayasa:** Seluruh stack transformasi diprogram ulang menggunakan arsitektur `data.table` murni:
    1. Parsing streaming menggunakan `fread()` dengan parameter `colClasses` terdefinisi ketat, mengeliminasi inspeksi tipe dinamis.
    2. Pendefinisian `setkeyv(dt, c("ip_address", "timestamp"))` untuk mengaktifkan *binary search* instan.
    3. Evaluasi *rolling join* (`roll = "nearest"`) untuk mencocokkan latensi klik dengan database penayangan iklan tanpa alokasi cartesian join.
    4. Seluruh fitur agregasi perilaku pengguna (misalnya jumlah klik dalam 60 detik terakhir) dikalkulasi secara *in-place* menggunakan operator `:=` dan penandaan internal `.I`.
*   **Hasil Teknis Terukur:**
    *   Waktu siklus *end-to-end* berkurang secara drastis dari **48 menit** menjadi **3 menit 12 detik** (peningkatan kecepatan $\sim 15\times$).
    *   Alokasi puncak RAM (*peak RAM usage*) turun dari puncaknya **58 GB** menjadi konstan di level **14 GB** (reduksi footprint $\sim 75\%$), mengeliminasi kegagalan OOM secara permanen.

---

### 12. Trade-offs
Berikut perbandingan arsitektural antara `data.table`, `base::data.frame`, dan `dplyr` (dengan backend in-memory standar):

| Karakteristik | `data.table` | `base::data.frame` | `dplyr` (Tibble Engine) |
| :--- | :--- | :--- | :--- |
| **Model Evaluasi Memori** | Mutasi In-Place via Reference (`:=`) | Strict Copy-on-Write (COW) | Modifikasi COW dengan Shallow Copying C++ |
| **Footprint Memori (RAM)** | Minimal (Hampir $1\times$ ukuran data) | Sangat Boros ($2\times$ hingga $4\times$ ukuran data) | Menengah ($1.5\times$ hingga $2.5\times$ ukuran data) |
| **Algoritma Pencarian** | Binary Search via Fast Radix ($O(\log N)$) | Linear Vector Scan ($O(N)$) | Hashing / Linear Scan ($O(1)$ amortized / $O(N)$) |
| **Multithreading** | Terintegrasi via OpenMP (Native C) | Tidak Ada (Single-Threaded murni) | Parsial / Bergantung eksternal (*multidplyr*) |
| **Sintaksis & Readability** | Sangat ringkas, kurva belajar curam | Panjang, bertele-tele | Ekspresif, deklaratif, mudah dipelajari |
| **Side Effects Hazard** | Tinggi (Memerlukan `copy()` eksplisit) | Nol (Objek fungsional aman dari modifikasi tak disengaja) | Nol (Paradigma murni fungsional imutabel) |

---

### 13. When To Use
Gunakan arsitektur `data.table` ketika:
*   Dataset yang diproses di memori melebihi $1 \times 10^6$ baris atau mendekati batasan RAM fisik mesin ($\ge 30\%$ kapasitas RAM).
*   Membangun pipeline komputasi ETL berulang atau microservice analitik yang sensitif terhadap batas *latency* (SLA sub-detik hingga hitungan menit).
*   Melakukan operasi penggabungan (*join*) data non-ekivalen (*non-equi joins*), penggabungan interval (*overlapping range joins*), atau *rolling joins*.
*   Diperlukan determinisme alokasi RAM pada *environment container* berkapasitas rendah (misalnya AWS Lambda atau fargate container berbiaya rendah).

---

### 14. When NOT To Use
Hindari penggunaan `data.table` jika:
*   Dataset berukuran mikro (misalnya $< 10.000$ baris); latensi *overhead* kompilasi query `data.table` dapat melebihi kecepatan pemrosesan langsung vektor primitif R.
*   Anda memprioritaskan keterbacaan kode bagi analis junior atau tim multidisiplin yang terbiasa dengan filosofi *tidy syntax* tanpa latar belakang sistem rekayasa perangkat lunak.
*   Pipeline arsitektur Anda bergantung secara mutlak pada paradigma *pure functional programming*, di mana *referential transparency* tidak boleh dikompromikan oleh modifikasi in-place.
*   Objek tabular didesain untuk menyimpan list heterogen yang berisi model kompleks atau struktur hierarkis non-tabular yang dalam.

---

### 15. Common Mistakes
Di bawah ini adalah kesalahan fatal yang sering muncul dalam implementasi `data.table`:

#### 1. Shallow Copy Hazard (Pointer Aliasing Unintended Mutation)
```R
# KESALAHAN FATAL:
dt_asli <- data.table(a = 1:3, b = 4:6)
dt_turunan <- dt_asli # dt_turunan hanya menyalin pointer memori!

dt_turunan[, a := 99L] # IN-PLACE MUTATION
# Petaka: Nilai 'dt_asli' sekarang ikut berubah menjadi 99!

# PERBAIKAN:
dt_turunan <- copy(dt_asli) # Alokasi salinan independen secara eksplisit
dt_turunan[, a := 100L]     # dt_asli tetap aman
```

#### 2. Overhead `.SD` di dalam Looping Grup Kecil
```R
# KESALAHAN KINERJA:
# Menggunakan .SD untuk operasi skalar sederhana pada jutaan grup kecil
dt[, .SD[which.max(nilai)], by = group_id] # Memaksa alokasi data.table overhead di setiap iterasi!

# PERBAIKAN (Gunakan .I atau vektorisasi langsung):
dt[dt[, .I[which.max(nilai)], by = group_id]$V1]
```

#### 3. Mengombinasikan Assignment Standar `<-` dengan `:=`
```R
# KESALAHAN:
dt <- dt[, col_baru := runif(nrow(dt))] # Redundan dan berpotensi memicu locking/shallow memory leaks.

# PERBAIKAN:
dt[, col_baru := runif(.N)] # Mutasi langsung tanpa re-assignment pointer.
```

---

### 16. Best Practices
Checklist produksi untuk insinyur perangkat lunak:
*   [ ] **Set Threading Context:** Tetapkan nilai `setDTthreads()` di titik masuk aplikasi untuk menghindari perebutan sumber daya CPU di lingkungan virtual.
*   [ ] **Gunakan `.N` daripada `nrow(DT)`:** Gunakan simbol internal `.N` di dalam query $j$ atau $i$; pemanggilan `nrow()` memiliki overhead resolusi eksternal.
*   [ ] **Defensif dengan `copy()`:** Gunakan fungsi `copy()` secara eksplisit pada parameter fungsi modular untuk mencegah mutasi state tak terduga (*side effects*) pada *calling environment*.
*   [ ] **Pra-alokasi Kolom (`setalloccol`):** Jika berencana menambahkan puluhan kolom dinamis di dalam loop sistematis, perluas ukuran alokasi kolom sejak awal melalui `setalloccol(DT, n)`.
*   [ ] **Optimalkan Performa Assign Menggunakan `set()`:** Jika melakukan manipulasi seluler atau pemutakhiran berbasis loop baris per baris, gunakan fungsi primitif `set()` alih-alih `:=` untuk mengeliminasi overhead evaluasi parser NSE.
*   [ ] **Manfaatkan Tipe Waktu Teroptimasi:** Gunakan `IDate` dan `ITime` bawaan `data.table` yang menyimpan representasi integer murni daripada tipe POSIXct standar yang boros memori.

---

### 17. Troubleshooting
Panduan penanganan kegagalan sistem umum:

*   **Gejala: Error `Internal structure doesn't seem to be a data.table...`**
    *   *Penyebab:* Objek mengalami korupsi pointer atribut akibat manipulasi C-API level rendah secara langsung atau serialisasi objek cross-process yang rusak.
    *   *Solusi:* Panggil fungsi perbaikan pointer: `setDT(objek)` untuk merestrukturisasi atribut internal secara paksa.
*   **Gejala: Error `cannot change value of locked binding for '...'`**
    *   *Penyebab:* Mencoba menggunakan `:=` pada objek data.table yang berada di dalam package namespace yang berstatus *locked environment*.
    *   *Solusi:* Ekstrak objek ke level `.GlobalEnv` atau buat deep copy lokal via `copy()` sebelum menjalankan mutasi.
*   **Gejala: Memory Leak Terindikasi Meski Sudah Menggunakan `:=`**
    *   *Penyebab:* Penambahan kolom bertipe `character` yang terus-menerus tanpa pembersihan R string pool global (*R's Global String Cache* mempertahankan referensi string unik).
    *   *Solusi:* Konversi kolom teks statis menjadi `factor` atau gunakan integer hashing representation untuk merepresentasikan kategori berulang.

---

### 18. Exercise
**Instruksi:** Selesaikan skenario perbaikan kode di bawah ini.

Diberikan kode *legacy* pipeline kalkulasi metrik yang menyebabkan crash OOM pada server produksi:

```R
# KODE BERMASALAH (BASE R PARADIGM):
proses_data_kredit <- function(df) {
  # df memiliki 15 juta baris data
  df$skor_tertimbang <- df$skor_dasar * 1.5
  df$status_risiko <- "NORMAL"
  df$status_risiko[df$skor_tertimbang > 80] <- "HIGH"
  df$status_risiko[df$skor_tertimbang <= 30] <- "LOW"
  
  hasil <- aggregate(skor_tertimbang ~ cabang_id + status_risiko, data = df, FUN = mean)
  return(hasil)
}
```

**Tugas Anda:**
1.  Tulis ulang seluruh fungsi menjadi `proses_data_kredit_v2` menggunakan framework `data.table`.
2.  Pastikan tidak ada pembuatan salinan penuh tabel identik di memori (wajib mempertahankan arsitektur in-place update).
3.  Optimalkan agregasi menggunakan algoritma *radix group-by* internal.
4.  Lakukan validasi bahwa data masukan terlindungi dari efek samping (*side-effects*) di luar fungsi melalui defensive copying terencana.

---

### 19. Challenge
Rancang sebuah fungsi mesin kalkulasi modular: **`fast_rolling_zscore(dt, target_col, window_size, group_col)`** dengan batasan ketat berikut:
*   Fungsi menerima `data.table` dengan ukuran minimal $2 \times 10^7$ baris.
*   Menghitung *rolling mean*, *rolling standard deviation*, dan *rolling z-score* untuk kolom `target_col` yang dikelompokkan berdasarkan `group_col` dengan jendela observasi sepanjang `window_size`.
*   **Batasan Waktu & Memori:**
    *   Dilarang menggunakan perulangan `for` tingkat tinggi di R.
    *   Dilarang menggunakan paket eksternal lain (misalnya `zoo`, `RcppRoll`, dsb); murni memanfaatkan idiom C-level `data.table` (`frollmean`, `frollapply`, dsb).
    *   Penggunaan memori tambahan (*overhead*) tidak boleh melebihi ukuran memori kolom kalkulasi itu sendiri.
    *   Mutasi kolom hasil akhir (`zscore`) wajib diinjeksikan secara langsung ke tabel masukan menggunakan operator referensi.

---

### 20. Summary
Modul ini mengupas arsitektur inti dari performa tinggi manipulasi data dalam bahasa pemrograman R:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      DATA.TABLE ARCHITECTURE SUMMARY                   │
├───────────────────┬────────────────────────────────────────────────────┤
│ In-Place Update   │ Menggunakan `:=` dan `set()` untuk memintas R Copy-│
│                   │ on-Write, menjaga alokasi memori $O(1)$ overhead.  │
├───────────────────┼────────────────────────────────────────────────────┤
│ Over-Allocation   │ Mempersiapkan 1024 pointer kolom kosong di memori  │
│                   │ untuk penambahan kolom instan via `truelength`.    │
├───────────────────┼────────────────────────────────────────────────────┤
│ Radix Indexing    │ Mengganti full vector scan $O(N)$ dengan binary   │
│                   │ search $O(\log N)$ berkecepatan tinggi.           │
├───────────────────┼────────────────────────────────────────────────────┤
│ Idiom Terpadu     │ Sintaks kanonikal `DT[i, j, by]` menyatukan filter,│
│                   │ transformasi, dan agregasi dalam siklus tunggal.   │
└───────────────────┴────────────────────────────────────────────────────┘
```

Dengan menguasai mekanika internal ini, Anda beralih dari sekadar pengguna analisis data menjadi perancang sistem pemrosesan data bervolume tinggi yang andal, efisien, dan siap pakai untuk kebutuhan produksi tingkat enterprise.