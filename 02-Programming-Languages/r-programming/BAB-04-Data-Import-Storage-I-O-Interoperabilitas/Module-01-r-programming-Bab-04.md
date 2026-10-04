# Bab 04 Module 01: Manipulasi Data Performa Tinggi: Semantik Memori dan Optimasi Arsitektur `data.table`

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis mekanisme alokasi memori internal GNU R (*Copy-on-Modify* vs *In-Place Modification*) menggunakan utilitas diagnostik memori C-level (`tracemem`, `lobstr::ref`, `address`).
- Mengimplementasikan manipulasi data berskala gigabyte hingga multi-juta baris menggunakan arsitektur `data.table` dengan paradigma sintaksis terpadu `[i, j, by]`.
- Mengeliminasi alokasi memori redundan melalui pemanfaatan operator mutasi referensi *walrus* (`:=`) dan fungsi keluarga `set*()`.
- Mengonfigurasi *secondary indices* dan *primary keys* untuk mereduksi kompleksitas pencarian data dari linear time scanning $O(N)$ menjadi binary search logarithmic time $O(\log N)$.
- Mengoptimasi komputasi agregasi multi-grup frekuensi tinggi memanfaatkan *GForce optimization* dan *fast vector subsetting* terparalelisasi OpenMP.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda harus memahami:
- Struktur internal vektor dan atribut R dasar (*atomic vectors*, *attributes*, *generic vectors/lists*).
- Konsep dasar representasi struktur data tabular di R (`base::data.frame` sebagai list of equal-length vectors).
- Konsep kompleksitas komputasi dasar (Big-O notation: $O(1)$, $O(N)$, $O(\log N)$).
- Pemahaman dasar mengenai pengelolaan memori: pointer, heap memory, dan *stack frames*.

---

### 3. Concept
Secara default, bahasa R beroperasi di bawah filosofi fungsional murni di mana objek bersifat *immutable* (tidak dapat diubah secara langsung). Ketika sebuah objek dimodifikasi, GNU R menerapkan strategi **Copy-on-Modify (CoM)**. 

Di balik layar, setiap objek R direpresentasikan oleh struktur C yang disebut `SEXP` (*S-Expression Pointer*). Di dalam header `SEXP`, terdapat *bit field* pelacak referensi (dikenal sebagai mekanisme `NAMED` pada versi R lama, atau `REFCNT` / reference counting pada GNU R modern $\ge 3.1.0$). 
1. Jika `REFCNT > 1`, R menolak melakukan modifikasi langsung pada buffer memori yang ada. Sebaliknya, R mengalokasikan blok memori baru di heap, menduplikasi seluruh data (*deep copy*), memperbarui nilai pada salinan baru, dan mengarahkan pointer variabel ke lokasi baru tersebut.
2. Proses duplikasi ini memiliki kompleksitas ruang dan waktu sebesar $O(N \times M)$ untuk tabel berukuran $N$ baris dan $M$ kolom.

```
+------------------------------------------------------------------+
| Mekanisme Copy-on-Modify (CoM) Tradisional R                     |
+------------------------------------------------------------------+
[Variabel df1] ----> [ SEXP Header: 0x1A00 ] ----> [ Memory Slab A ]
                                                         |
Penugasan: df2 <- df1                                    |
[Variabel df2] ------------------------------------------+ (REFCNT = 2)
                                                         |
Modifikasi: df2$x[1] <- 99                               |
Duplikasi Penuh Dijalankan!                               v
[Variabel df2] ----> [ SEXP Header: 0x2B00 ] ----> [ Memory Slab B (Salinan Baru) ]
                                                   (Nilai diubah di sini)
```

Paket `data.table` mendisrupsi arsitektur ini dengan memperkenalkan **Reference Semantics** (semantik referensi) yang dieksekusi langsung pada layer C. `data.table` membungkus struktur list R standar namun menambahkan layer kontrol memori internal:
- **`alloc.col` (Over-allocation):** Saat sebuah `data.table` diinisialisasi, C-level engine tidak hanya mengalokasikan pointer sejumlah kolom yang ada, melainkan memesan ruang kapasitas ekstra (secara default 1024 slot pointer kolom) dalam bentuk array of pointers. Hal ini memungkinkan penambahan kolom baru seketika tanpa perlu merealokasi array list penampung.
- **In-Place Modification (`:=`):** Operator mutasi langsung memodifikasi nilai pada array memori yang ditunjuk oleh pointer kolom tanpa menaikkan *reference count* yang memicu penggandaan objek R. Mutasi ini terjadi langsung pada C `DATAPTR`.
- **Fast Radix / Binary Search Indexing:** `data.table` mengimplementasikan algoritma pengurutan *radix sort* performa tinggi yang ditulis dalam C murni. Ketika *key* atau *index* ditetapkan, `data.table` membuat integer vector yang merepresentasikan urutan terurut secara permanen atau *on-the-fly*, mengubah pemindaian linier menjadi penelusuran biner instan.

---

### 4. Why
Kebutuhan komputasi data skala enterprise sering kali menuntut pemrosesan tabel berdimensi puluhan juta baris dengan puluhan atribut (misalnya: data transaksi perbankan, telemetri IoT, log sistem). Menggunakan manipulasi standar R (`base` atau pendekatan mutasi konvensional) pada skala ini memicu kegagalan sistematis:

1. **Memory Exhaustion (OOM - Out of Memory):** Jika Anda memiliki dataset berukuran 8 GB pada mesin dengan RAM 16 GB, memodifikasi satu nilai atau menambah satu kolom menggunakan `df$new_col <- df$old_col * 2` pada implementasi `data.frame` standar dapat memicu duplikasi memori penuh. Penggunaan RAM melonjak dari 8 GB menjadi 16 GB, menyebabkan swapping agresif ke disk atau crash akibat *Linux OOM Killer*.
2. **Garbage Collection (GC) Thrashing:** Duplikasi data yang berulang-ulang menciptakan jutaan objek sementara (*ephemeral objects*) di heap. Garbage Collector R dipaksa berjalan secara konstan untuk membersihkan objek yatim piatu (*orphaned pointers*), membekukan proses komputasi (*stop-the-world latency*).
3. **Kompleksitas Subsetting Linear:** Melakukan filtering berbasis scanning bertahap $O(N)$ pada tabel dengan $10^8$ baris secara berulang di dalam pipeline analitik memakan waktu menit hingga jam. `data.table` memangkas waktu pencarian ke tingkat milidetik melalui *binary search indexation*.

---

### 5. What
Komponen inti pembangun arsitektur pemrosesan `data.table` mencakup:

- **Sintaksis Terpadu `DT[i, j, by]`:** 
  - `i`: Memfilter baris (*subsetting*), melakukan *join*, atau mendefinisikan indeks baris yang ditargetkan.
  - `j`: Mengalkulasi ekspresi kolom (*projection*), memilih kolom, atau melakukan mutasi *in-place* menggunakan `:=`.
  - `by`: Mengelompokkan komputasi (*split-apply-combine*) berdasarkan variabel kategorikal tertentu, langsung dioptimasi di tingkat C engine.
- **Operator Walrus (`:=`):** Operator penugasan referensi yang memutasi memori kolom secara langsung tanpa duplikasi tabel.
- **Utilitas Modifikasi Struktur In-Place (`set*`):**
  - `setDT()`: Mengonversi `data.frame` menjadi `data.table` langsung pada heap yang sama tanpa alokasi memori tambahan.
  - `setnames()`: Mengubah nama kolom dengan merealokasi string vector atribut tanpa menyentuh data vektor kolom.
  - `setorder()` / `setcolorder()`: Mengatur urutan baris atau kolom secara *in-place*.
- **Mekanisme Pengindeksan (`setkey()`, `setindex()`):** Membuat indeks radix sorting fisik (*key*) atau virtual (*secondary index*) untuk eksekusi join dan filter ultra-cepat.
- **Simbol-Simbol Khusus Engine:**
  - `.SD`: *Subset of Data.table*, memuat potongan data per grup untuk komputasi terdistribusi lokal.
  - `.SDcols`: Menentukan vektor kolom yang dimuat ke dalam `.SD`, krusial untuk mencegah overhead pemuatan data.
  - `.N`: Menyimpan total observasi dalam grup saat ini.
  - `.I`: Vektor integer yang memetakan indeks baris global terhadap subset yang sedang dievaluasi.
  - `.BY`: List beranggotakan satu nilai per variabel grup saat komputasi berlangsung.

---

### 6. How
Alur kerja komputasi pada arsitektur `data.table` beroperasi secara internal sebagai berikut:

```
[ Input Query: DT[i_expr, j_expr, by_expr] ]
                     |
                     v
 [ Step 1: Query Pre-Processing & AST Parsing ]
                     |
                     +---> Evaluasi apakah `i` menggunakan Binary Search Key/Index?
                     |        |-- Ya: Jalankan C-level binary search (O(log N))
                     |        +-- Tidak: Jalankan Vectorized evaluation (O(N))
                     v
 [ Step 2: Optimasi Internal (GForce Engine) ]
                     |
                     +---> Apakah fungsi agregasi di `j` didukung GForce?
                              (e.g., mean, sum, min, max, median)
                              |-- Ya: Bypass pembuatan R environment per grup;
                              |       eksekusi C-level loop langsung pada memory slabs.
                              +-- Tidak: Fallback ke evaluasi R standard loop.
                     v
 [ Step 3: Grup Alokasi (Chappeau Grouping) ]
                     |
                     +---> Eksekusi High-speed Radix Sort pada kolom `by`.
                     +---> Hitung panjang dan offset posisi setiap grup.
                     v
 [ Step 4: Eksekusi Proyeksi `j` ]
                     |
                     +---> Jika operator `:=` terdeteksi:
                              Tulis langsung ke pointer memory kolom target (In-Place).
                     +---> Jika tidak:
                              Alokasikan buffer hasil agregasi minimal dan kembalikan output.
```

1. **AST Inspection:** Ekspresi di dalam `[...]` ditangkap oleh R interpreter tanpa langsung dievaluasi (*non-standard evaluation*). `data.table` memeriksa apakah pemfilteran `i` cocok dengan urutan atribut terindeks (*keyed* atau *secondary index*).
2. **Binary Search Filter:** Jika `i` adalah nilai konstan dan target kolom adalah *Key*, pencarian offset memori diselesaikan via C library `bsearch` dalam waktu $O(\log N)$.
3. **GForce Optimization:** Engine memindai fungsi di dalam `j`. Jika terdapat fungsi analitik bawaan yang didukung (seperti `sum()`, `mean()`, `first()`, `last()`), `data.table` mengabaikan pemanggilan interpreter R standar dan langsung memproses perhitungan menggunakan loop internal C yang tervektorisasi penuh dan diakselerasi multithreading via OpenMP.
4. **Zero-Copy Column Extension:** Ketika kolom baru ditambahkan melalui `DT[, new_col := values]`, engine memeriksa apakah kapasitas slot kolom yang dialokasikan di `alloc.col` mencukupi. Jika ya, pointer vektor baru langsung ditautkan ke slot yang tersedia tanpa menyalin kolom-kolom lain yang telah ada di memori.

---

### 7. Analogy
Bayangkan Anda memiliki sebuah buku ensiklopedia fisik setebal 5.000 halaman (**DataFrame R Standar**). 

- **Pendekatan Copy-on-Modify R Standar:**
  Jika Anda ingin merevisi satu kata salah eja pada halaman 1.250, aturan perpustakaan mengharuskan Anda memfotokopi seluruh buku setebal 5.000 halaman tersebut dari awal hingga akhir, mengganti satu kata tersebut pada lembar fotokopi yang baru, lalu membuang buku lama ke tempat sampah daur ulang (*Garbage Collector*). Proses ini sangat lambat, menghabiskan rim kertas, dan membebani ruang kantor Anda.
  
- **Pendekatan `data.table` (In-Place Modification):**
  Anda membawa pulpen langsung ke lemari arsip, membuka halaman 1.250 pada buku asli, menghapus kata tersebut dengan tip-ex, menuliskan kata yang benar langsung di atas kertas dokumen asli (**`:=`**), dan selesai dalam waktu 1 detik. Tidak ada kertas yang terbuang, tidak ada fotokopi yang dibuat, dan ruang kantor Anda tetap bersih.
  
- **Pengindeksan (`setkey`):**
  Jika Anda mencari bab tertentu, daripada membaca halaman demi halaman dari halaman 1 sampai 5.000 (*Linear Scan*), Anda memasang pembatas buku indeks bertab alfabetik (*Binary Index*), sehingga Anda langsung membuka halaman target secara instan dalam satu gerakan.

---

### 8. Diagram
Diagram arsitektur memori di heap: membandingkan representasi `base::data.frame` versus optimasi memory slab `data.table`.

```
================================================================================
                      BASE R DATA.FRAME MODIFIKASI (CoM)
================================================================================
Heap Memory Awal:
Var: df1 ---> [ List SEXP: 0x001 ]
                 |---> Col1 (Int) : [ 0x00A | Ptr -> | 10 | 20 | 30 | ]
                 |---> Col2 (Real): [ 0x00B | Ptr -> | 1.1| 2.2| 3.3| ]

Eksekusi: df1$Col1[1] <- 99L (Jika REFCNT > 1)
Heap Memory Baru (Terjadi Duplikasi Massal):
Var: df1 ---> [ List SEXP: 0x002 ]  <-- SEXP Baru
                 |---> Col1 (Int) : [ 0x00C | Ptr -> | 99 | 20 | 30 | ] <-- Di-copy penuh!
                 |---> Col2 (Real): [ 0x00B ] (Shallow copy ptr jika aman)
                 *0x00A menunggu Garbage Collector.


================================================================================
                      DATA.TABLE REFERENCE SEMANTICS (:=)
================================================================================
Heap Memory Awal:
Var: dt1 ---> [ VECSXP Header: 0x900 ] (Over-allocated: misal 1024 pointer slots)
                 Slot [0]: Col1 (Int)  [ 0x700 | Ptr -> | 10 | 20 | 30 | ]
                 Slot [1]: Col2 (Real) [ 0x800 | Ptr -> | 1.1| 2.2| 3.3| ]
                 Slot [2..1023]: Pointers kosong (Tersedia untuk ekspansi)

Eksekusi: dt1[1, Col1 := 99L]
Heap Memory Pasca Modifikasi:
Var: dt1 ---> [ VECSXP Header: 0x900 ] (Pointer Identitas Sama: 0x900)
                 Slot [0]: Col1 (Int)  [ 0x700 | Ptr -> | 99 | 20 | 30 | ] <-- Nilai ditulis langsung!
                 Slot [1]: Col2 (Real) [ 0x800 | Ptr -> | 1.1| 2.2| 3.3| ]
                 *TIDAK ADA memori baru yang dibuat. Beban Garbage Collector = 0.
```

---

### 9. Simple Example
Kode demonstrasi di bawah membuktikan terjadinya penggandaan memori pada `data.frame` versus stabilitas referensi pada `data.table`.

```r
library(data.table)

# -------------------------------------------------------------
# 1. PENGUJIAN COPY-ON-MODIFY PADA BASE DATA.FRAME
# -------------------------------------------------------------
cat("=== PENGUJIAN BASE DATA.FRAME ===\n")
df_base <- data.frame(
  id = 1:5,
  metrik = c(10.5, 20.2, 30.1, 40.8, 50.4)
)

# Tangkap alamat memori awal
alamat_awal_df <- tracemem(df_base)
cat("Alamat memori awal df_base :", alamat_awal_df, "\n")

# Lakukan modifikasi satu elemen
df_base$metrik[1] <- 99.9

# Output konsol akan memperlihatkan pesan pelacakan:
# "tracemem[0x... -> 0x...]:" membuktikan duplikasi memori terjadi!
untracemem(df_base)

# -------------------------------------------------------------
# 2. PENGUJIAN SEMANTIK REFERENSI PADA DATA.TABLE
# -------------------------------------------------------------
cat("\n=== PENGUJIAN DATA.TABLE ===\n")
dt_fast <- data.table(
  id = 1:5,
  metrik = c(10.5, 20.2, 30.1, 40.8, 50.4)
)

# Catat pointer internal menggunakan address() dari data.table
alamat_awal_dt <- address(dt_fast)
cat("Alamat memori awal dt_fast :", alamat_awal_dt, "\n")

# Lakukan mutasi in-place menggunakan operator :=
dt_fast[1, metrik := 99.9]

alamat_akhir_dt <- address(dt_fast)
cat("Alamat memori akhir dt_fast:", alamat_akhir_dt, "\n")

# Verifikasi identitas pointer
if (alamat_awal_dt == alamat_akhir_dt) {
  cat("[VALIDASI SUKSES]: Mutasi terjadi in-place. Zero memory reallocation!\n")
} else {
  stop("[ERROR]: Duplikasi memori terdeteksi!")
}

print(dt_fast)
```

---

### 10. Practical Example
Berikut adalah implementasi modul analitik data transaksi finansial: memproses jutaan baris data, deduplikasi baris, mutasi multikolom berbasis kondisi, agregasi grup, dan implementasi secondary index untuk querying latensi rendah.

```r
library(data.table)

# Set seed untuk determinisme pengujian
set.seed(42)

# Konfigurasi thread OpenMP maksimal untuk data.table
setDTthreads(threads = 0) # Menggunakan seluruh core fisik yang tersedia
cat("Thread aktif data.table:", getDTthreads(), "\n\n")

# Generasi data sintetis transaksi sebesar 2.000.000 baris
n_rows <- 2e6
tabel_transaksi <- data.table(
  tx_id = paste0("TX-", seq_len(n_rows)),
  user_id = sample(10000:99999, n_rows, replace = TRUE),
  kategori = sample(c("Retail", "FnB", "Travel", "Utility", "Tech"), n_rows, replace = TRUE),
  nominal = round(runif(n_rows, min = 5000, max = 5000000), 2),
  status = sample(c("SUCCESS", "PENDING", "FAILED"), n_rows, replace = TRUE, prob = c(0.85, 0.10, 0.05)),
  timestamp = as.POSIXct("2026-01-01 00:00:00", tz = "UTC") + runif(n_rows, 0, 86400 * 30)
)

# 1. PENGGUNAAN SETKEY DAN SECONDARY INDEX
# Menetapkan user_id sebagai primary key (mengurutkan tabel secara fisik)
# Menetapkan kategori sebagai secondary index (virtual index tanpa reordering fisik)
setkey(tabel_transaksi, user_id)
setindex(tabel_transaksi, kategori)

# 2. MUTASI REFERENSI IN-PLACE MULTIKOLOM MENGGUNAKAN :=
# Menghitung fee transaksi dan flag anomali nominal tanpa duplikasi objek
tabel_transaksi[, `:=`(
  fee_transaksi = fifelse(kategori == "Travel", nominal * 0.02, nominal * 0.005),
  flag_high_value = fifelse(nominal > 4500000, 1L, 0L)
)]

# 3. FAST FILTERING MENGGUNAKAN INDEXING (Binary Search vs Scan)
cat("Menguji kecepatan query menggunakan secondary index (kategori = 'Travel')...\n")
benchmark_search <- system.time({
  hasil_travel <- tabel_transaksi[.( "Travel" ), on = "kategori", nomatch = NULL]
})
cat("Pencarian selesai dalam:", benchmark_search["elapsed"], "detik. Baris didapatkan:", nrow(hasil_travel), "\n\n")

# 4. AGREGASI DATA LANJUTAN DENGAN .SD DAN GFORCE ENGINE
# Menghitung ringkasan finansial per kategori untuk transaksi berstatus SUCCESS
ringkasan_kategori <- tabel_transaksi[
  status == "SUCCESS",
  .(
    total_volume   = sum(nominal),
    rata_rata      = mean(nominal),
    median_nominal = as.numeric(median(nominal)),
    frekuensi_tx   = .N,
    tx_anomali     = sum(flag_high_value)
  ),
  by = kategori
]

# Urutkan ringkasan in-place berdasarkan total_volume secara descending
setorder(ringkasan_kategori, -total_volume)

cat("=== RINGKASAN TRANSAKSI STATUS SUCCESS PER KATEGORI ===\n")
print(ringkasan_kategori)

# 5. PEMBERSIHAN MEMORI SISTEM SECARA DEFENSIVE
# Hapus objek turunan yang tidak lagi dipakai
rm(hasil_travel)
invisible(gc(verbose = FALSE))
```

---

### 11. Real World Example
**Studi Kasus:** Sistem Rekonsiliasi Deteksi Penipuan Kartu Kredit Skala Enterprise (*FinTech Payment Gateway*).

- **Konteks:** Sebuah gateway pembayaran memproses 50 juta log transaksi harian dari berbagai *merchant*. Sistem analitik risiko harus mencocokkan setiap transaksi baru terhadap riwayat transaksi 30 hari terakhir untuk mendeteksi *velocity fraud* (misal: lebih dari 3 transaksi bernilai tinggi dari IP/User yang sama dalam interval 10 menit).
- **Arsitektur Masalah:**
  Penggunaan `dplyr` atau `base::merge` standar gagal menyelesaikan beban kerja dalam target Service Level Agreement (SLA) harian:
  - Eksekusi join non-equi berbasis waktu membutuhkan waktu komputasi > 4 jam karena kehabisan memori (*thrashing memory* di heap swap).
  - Skrip analitik terhenti karena `Error: cannot allocate vector of size 14.2 Gb`.
- **Implementasi Solusi dengan `data.table`:**
  Engineering team mendesain ulang *engine ingestion* menggunakan teknik:
  1. `setkeyv(dt_log, c("user_id", "timestamp"))` untuk mengaktifkan memory layout berbasis pencarian terurut.
  2. Implementasi **Non-Equi Join** dan **Rolling Join** menggunakan operator bawaan `data.table` tanpa pembuatan tabel intermediat:
     ```r
     # Contoh Eksekusi Rolling Join 10 Menit untuk Deteksi Anomali
     dt_fraud_alerts <- dt_transaksi_baru[
       dt_historical_log,
       on = .(user_id, timestamp >= timestamp - 600, timestamp <= timestamp),
       .(user_id, x.tx_id, x.nominal, count_prior_tx = .N),
       by = .EACHI
     ][count_prior_tx > 3]
     ```
- **Dampak Metrik Produksi:**
  - Waktu eksekusi batch berkurang dari **4 jam 12 menit** menjadi **3 menit 45 detik**.
  - Puncak penggunaan memori (*Peak RAM utilization*) terpangkas drastis dari **68 GB** menjadi **11 GB** pada server pemrosesan berkat eliminasi *intermediate copy objects*.
  - Menghindari migrasi infrastruktur yang mahal ke cluster Apache Spark terdistribusi, menjaga seluruh pipeline tetap berjalan di satu instance server bare-metal berspesifikasi sedang.

---

### 12. Trade-offs

| Dimensi | Pendekatan `base::data.frame` / `dplyr` | Pendekatan `data.table` |
| :--- | :--- | :--- |
| **Keuntungan (Advantages)** | Syntactic sugar mudah dibaca (`%>%`), filosofi fungsional murni meminimalkan efek samping tak disengaja (*side-effects*). | Performa superior, alokasi memori minimal (*zero-copy*), kaya fitur tingkat lanjut (*non-equi joins*, *rolling joins*, *overlap joins*). |
| **Kerugian (Disadvantages)** | Duplikasi memori intensif (*Copy-on-Modify*), performa lambat pada data multi-juta baris, GC overhead masif. | Kurva pembelajaran lebih curam, semantik referensi dapat menimbulkan *silent bug* jika programmer tidak memahami pointer. |
| **Kompleksitas Kode** | Rendah: Struktur deklaratif linear dan modular. | Menengah ke Tinggi: Kueri terkonsentrasi di dalam blok `[i, j, by]` menuntut pemahaman internal R AST parsing. |
| **Karakteristik Performa** | Eksekusi single-threaded secara umum, alokasi RAM $O(N \times M)$ pada setiap rantai mutasi pipeline. | Eksekusi multi-threaded via OpenMP bawaan C, komputasi $O(1)$ untuk mutasi kolom, $O(\log N)$ untuk searching berindeks. |
| **Biaya Infrastruktur** | Membutuhkan RAM server 3x–5x lebih besar dari ukuran dataset riil untuk mencegah crash sistem (*OOM*). | Efisiensi RAM maksimal (cukup $\sim 1.1\text{x}-1.5\text{x}$ ukuran data), memangkas biaya penyewaan instance cloud VM. |

---

### 13. When To Use
Gunakan arsitektur `data.table` ketika:
- Memproses dataset berdimensi $\ge 1.000.000$ baris atau dataset berukuran mendekati batas RAM mesin lokal ($\ge 20\%$ kapasitas fisik memori).
- Membangun pipeline analitik batch produksi yang beroperasi di dalam container Docker/Kubernetes dengan resource limit ketat (*hard memory limit*).
- Membutuhkan operasi *rolling aggregation*, *lead/lag* join berbasis rentang waktu (*non-equi join*), atau pemrosesan data berbasis sekuensial yang presisi.
- Mengembangkan paket R performa tinggi yang tidak boleh menambah dependensi eksternal yang membengkak (*data.table* tidak memiliki dependensi paket pihak ketiga selain library C dasar).

---

### 14. When NOT To Use
Hindari `data.table` (atau gunakan abstraksi lain) ketika:
- Bekerja dengan dataset kecil ($< 10.000$ baris) di mana latensi eksekusi sudah berada di bawah 5 milidetik; optimasi performa mikro tidak sebanding dengan kompleksitas sintaksis.
- Tim Anda didominasi oleh analis junior non-rekayasawan yang tidak memahami mutasi memori (*in-place assignment*), berpotensi menyebabkan bug korupsi state data secara laten.
- Aplikasi Anda sangat bergantung pada ekosistem tidyverse yang membutuhkan kompatibilitas ketat dengan antarmuka `tibble` dan metapemrograman `rlang` tanpa adapter konversi.

---

### 15. Common Mistakes
Berikut adalah jebakan teknis yang sering memicu kegagalan sistemik di lingkungan produksi:

#### 1. Mutasi Objek Melalui Salinan Dangkal (*Shallow Copy Pitfall*)
```r
# SALAH: Mengira bahwa penugasan biasa menduplikasi data
DT_asli <- data.table(a = 1:3, b = 4:6)
DT_salinan <- DT_asli  # Pointer hanya dialokasikan ulang, menunjuk heap yang sama!

DT_salinan[, a := 999L]

# BENCANA: DT_asli ikut berubah tanpa disengaja!
print(DT_asli$a) # Menghasilkan 999 999 999

# BENAR: Lakukan deep copy secara eksplisit jika isolasi data dibutuhkan
DT_asli <- data.table(a = 1:3, b = 4:6)
DT_salinan <- copy(DT_asli) # Alokasi memori independen di layer C
DT_salinan[, a := 999L]
print(DT_asli$a) # Tetap aman: 1 2 3
```

#### 2. Konversi Memori Tidak Efisien Menggunakan `as.data.table()`
```r
# SALAH: Memicu duplikasi memori penuh dari data.frame yang ada
df_besar <- data.frame(matrix(runif(1e7), ncol = 10))
dt_besar <- as.data.table(df_besar) # Menduplikasi seluruh heap memory

# BENAR: Gunakan setDT() untuk mengonversi pointer in-place tanpa alokasi baru
df_besar <- data.frame(matrix(runif(1e7), ncol = 10))
setDT(df_besar) # Mengubah kelas objek langsung pada RAM yang sama (Zero Overhead)
```

#### 3. Pemanggilan `.SD` Tanpa Menggunakan `.SDcols`
```r
# SALAH: Memuat seluruh kolom ke dalam memory slab .SD per grup
# Menyebabkan overhead alokasi list R yang sangat masif dan mematikan optimasi GForce
DT[, lapply(.SD, mean), by = group]

# BENAR: Spesifikasikan kolom yang ingin diproses saja
DT[, lapply(.SD, mean), by = group, .SDcols = c("target_col1", "target_col2")]
```

---

### 16. Best Practices
Daftar periksa teknis standar produksi:
- [ ] **Gunakan `setDT()` dan Hindari `as.data.table()`:** Jangan pernah menduplikasi struktur `data.frame` saat transisi ke `data.table`.
- [ ] **Alokasikan Operator Walrus `:=` untuk Penambahan Variabel:** Pastikan tidak ada sintaks `DT <- DT[, ...]` saat hanya menambah atau mengupdate kolom.
- [ ] **Manfaatkan Fungsi `set*` Khusus:** Gunakan `setnames()`, `setorder()`, `setcolorder()` untuk mutasi metadata tabel tanpa *overhead*.
- [ ] **Gunakan `fifelse()` Menggantikan `base::ifelse()`:** Fungsi kondisional bawaan `data.table::fifelse()` sepenuhnya tervektorisasi pada layer C murni, mengabaikan konversi tipe R yang lambat dan bebas *memory allocation*.
- [ ] **Spesifikasikan `setDTthreads()` di Awal Pipeline:** Hindari perebutan CPU core di server multiprosesor dengan mengatur alokasi thread secara eksplisit sesuai konfigurasi environment batch.
- [ ] **Kunci Tabel dengan `setkey()` untuk Operasi Berulang:** Jika pipeline melakukan filtering atau join berulang pada satu dimensi pengelompokan yang sama, urutkan tabel secara fisik satu kali di awal proses.

---

### 17. Troubleshooting
Panduan penanganan galat dan edge cases teknis:

#### 1. Masalah: "Internal structure of data.table has been corrupted"
- **Penyebab:** Terjadi ketika fungsi C-level pihak ketiga atau kode R eksternal memodifikasi atribut tabel secara paksa tanpa memperbarui tracking over-allocation kolom dari `data.table`.
- **Diagnostik & Solusi:** Jalankan pemeriksaan pointer dan paksa tabel kembali ke konfigurasi memori yang valid menggunakan `alloc.col()`:
  ```r
  if (!truelength(DT)) {
    # Alokasi pointer kolom rusak, lakukan over-allocation ulang
    alloc.col(DT)
  }
  ```

#### 2. Masalah: OpenMP Multithreading Lockup di Lingkungan Forked Process
- **Penyebab:** Ketika menggunakan pustaka paralelisasi seperti `parallel::mclapply` (yang melakukan POSIX system call `fork()`), thread OpenMP dari `data.table` yang aktif sebelum forking dapat menyebabkan race condition atau *deadlock* permanen di worker node anak.
- **Solusi Rekayasa:** Setel jumlah thread ke 1 sebelum forking dijalankan, lalu kembalikan ke nilai optimal di dalam worker:
  ```r
  setDTthreads(1) # Matikan multithreading sebelum forking
  hasil <- parallel::mclapply(list_of_tasks, function(task) {
    setDTthreads(2) # Alokasikan thread di dalam subprocess mandiri
    # Eksekusi pipeline data.table di sini
  })
  setDTthreads(0) # Kembalikan thread utama
  ```

---

### 18. Exercise
Lakukan instruksi berikut secara mandiri menggunakan sesi R konsol Anda:

1. **Inisialisasi Tabel:** Buat sebuah objek `data.frame` bernama `df_sensor` dengan 5.000.000 baris yang memuat:
   - `sensor_id`: integer acak antara 1 sampai 100.
   - `temperature`: angka desimal acak berkisar 20.0 hingga 85.0.
   - `error_code`: karakter acak dari vektor `c("E00", "E01", "E02", "OK")`.
2. **Transformasi In-Place:** Ubah `df_sensor` menjadi `data.table` **tanpa** mengalokasikan memori baru (verifikasi dengan `address()`).
3. **Optimasi Kolom:**
   - Tambahkan kolom baru bernama `temp_kelvin` yang nilainya adalah `temperature + 273.15` menggunakan semantik referensi.
   - Perbarui seluruh nilai `temp_kelvin` menjadi `NA` jika `error_code != "OK"` langsung di tempat (*in-place conditional modification*).
4. **Agregasi Multi-Grup:** Gunakan operator agregasi untuk menghasilkan tabel baru berisikan `rata_rata_suhu` dan `total_error` (dihitung dari banyaknya `error_code != "OK"`) per `sensor_id`.

---

### 19. Challenge
**Skenario Rekayasa Lanjutan:**
Anda diberikan dataset log server jaringan sebesar 10.000.000 baris dengan atribut `session_id`, `ip_address`, `request_epoch` (numeric integer waktu dalam detik), dan `bytes_sent`.

**Spesifikasi Persyaratan:**
1. Anda dilarang keras menduplikasi tabel dasar atau menggunakan fungsi keluarga `tidyverse` atau `base::lapply`.
2. Lakukan deduplikasi baris berbasis `session_id` terurut berdasarkan `request_epoch` terkini (ambil rekaman log paling akhir per session).
3. Hitung metrik **Rolling Cumulative Bandwidth** (`bytes_sent`) untuk setiap `ip_address` dalam jendela bergerak observasi secara terurut waktu, menggunakan fitur referensi.
4. Keseluruhan skrip harus berjalan dalam waktu **$<$ 1.5 detik** dengan *memory footprint peak* di bawah 1.5x ukuran file awal.

**Solusi Template Teknis:**
```r
library(data.table)

# Inisialisasi Data Uji Skala 10 Juta Baris
n <- 1e7
set.seed(101)
log_server <- data.table(
  session_id   = sample(1:2e6, n, replace = TRUE),
  ip_address   = sample(paste0("192.168.1.", 1:254), n, replace = TRUE),
  request_epoch = sample(1700000000:1700086400, n, replace = TRUE),
  bytes_sent   = sample(100:50000, n, replace = TRUE)
)

# --- MULAI SOLUSI TANTANGAN DI SINI ---
# 1. Mengatur urutan fisik untuk reduksi latensi deduplikasi
setorder(log_server, session_id, -request_epoch)

# 2. Ambil baris terakhir per session_id (sudah terurut descending) secara zero-copy
log_dedup <- log_server[log_server[, .I[1L], by = session_id]$V1]

# 3. Urutkan data hasil deduplikasi berdasarkan ip_address dan waktu maju
setorder(log_dedup, ip_address, request_epoch)

# 4. In-Place Cumulative Sum per grup IP
log_dedup[, cumulative_bytes := cumsum(bytes_sent), by = ip_address]

# Validasi output konsol
cat("Pemrosesan selesai. Total data terverifikasi:", nrow(log_dedup), "\n")
print(head(log_dedup, 5))
```

---

### 20. Summary
- Konsep dasar GNU R menerapkan strategi **Copy-on-Modify (CoM)** yang merealokasi seluruh data di memori heap saat objek bermutasi jika reference count (`REFCNT`) $> 1$.
- `data.table` menghindari duplikasi ini melalui implementasi **Semantik Referensi** pada C level pointer, memanfaatkan **`alloc.col`** untuk ekspansi dinamis dan **`:=`** untuk mutasi langsung pada blok array kolom yang ada.
- Arsitektur sintaks terpadu `[i, j, by]` memfasilitasi integrasi antara penyaringan baris via C *binary search*, komputasi proyeksi via *GForce vectorized engine*, dan pengelompokan frekuensi tinggi via *radix sort*.
- Menghindari konversi shallow/deep copy yang salah dan memilih `setDT()` daripada `as.data.table()` adalah prinsip fundamental dalam merancang pipeline data skala besar yang stabil, efisien biaya infrastruktur, dan bebas dari bahaya *Out-of-Memory (OOM)*.