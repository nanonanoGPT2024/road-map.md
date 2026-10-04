# Bab 04 Module 01: High-Performance Data Wrangling

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `R-02-04-01`
* **Kategori**: `02-Programming-Languages` / R
* **Judul**: High-Performance Data Wrangling: Arsitektur Memori In-Place, Eksekusi Binary Search, dan Akselerasi Komputasi Tabular
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**: 
  * Pemahaman mendalam tentang R Data Structures (`vector`, `matrix`, `data.frame`, `list`).
  * Konsep alokasi memori heap R, lingkungan eksekusi (*environments*), dan evaluasi non-standar (*Non-Standard Evaluation* / NSE).
  * Pengalaman dasar dengan sintaks `dplyr` atau *base* R subsetting.
* **Estimasi Waktu**: 6–8 Jam (Teori, Bedah Source Code, Profiling, dan Proyek Praktikum)
* **Kebutuhan Teknis**: 
  * R versi 4.2.0 atau lebih baru.
  * Library: `data.table` (>= 1.14.8), `collapse` (>= 1.9.6), `bench` (>= 1.1.3), `lobstr` (>= 1.1.2), `pryr` (>= 0.1.5).
  * Lingkungan terminal/IDE: RStudio Desktop / Posit Workbench / Neovim-R dengan akses compiler C (Rtools pada Windows atau `build-essential` pada Linux/macOS) untuk melihat inspeksi pointer.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Mekanisme Copy-on-Modify (COW)**: Membedah siklus hidup objek data frame pada R heap memory dan mengidentifikasi overhead redundansi duplikasi data menggunakan inspeksi pointer langsung (`lobstr::obj_addr` / `tracemem`).
2. **Mengimplementasikan Manipulasi In-Place via `data.table`**: Mengoperasikan operator `:=` untuk mutasi kolom secara *pass-by-reference*, menghindari alokasi memori berlebih, dan memanfaatkan *over-allocation* vektor.
3. **Mengoptimalkan Query dengan Binary Search**: Merancang indeks primer (*key*) dan sekunder (*indices*) tabular untuk mentransformasi kompleksitas algoritma pemfilteran dari $O(N)$ (linear scan) menjadi $O(\log N)$ (binary search) atau $O(1)$ amortized.
4. **Menerapkan Fast Aggregation dengan GForce & `collapse`**: Memanfaatkan optimasi internal C-level GForce pada `data.table` dan fungsi berkecepatan mikro-detik dari paket `collapse` yang menggunakan algoritma hashing C/C++ modern.
5. **Menghilangkan Bottleneck Pemrosesan Data Skala Besar**: Mengeliminasi penggunaan `.SD` sub-optimal dalam iterasi grup dan menggantinya dengan agregasi terindeks serta vektorisasi penuh.
6. **Membangun Arsitektur Pipeline Data Nir-OOM (Out-of-Memory)**: Menyusun alur kerja produksi berkemampuan multi-threading (OpenMP) yang mampu mengolah puluhan juta baris data dengan penggunaan memori yang terkontrol secara ketat.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Nilai Semantik vs. Mutasi Semantik

Dalam *base* R dan ekosistem *Tidyverse* standar (`dplyr`), paradigma utama adalah **fungsional murni** (*pure functional programming*). Ketika sebuah fungsi menerima objek data frame dan menambahkan kolom, filosofinya adalah mengembalikan *data frame baru*. 

Meskipun R memiliki optimasi internal bernama **Copy-on-Modify (COW)**—di mana memori hanya disalin saat modifikasi terjadi—paradigma ini runtuh ketika kita berhadapan dengan data berukuran gigabyte. Setiap operasi `mutate()` atau `df$col <- val` berpotensi memicu duplikasi seluruh referensi kolom, memaksa garbage collector (GC) bekerja secara agresif, menaikkan fragmentasi RAM, dan menurunkan *throughput* komputasi.

```
Model Fungsional (COW / Base R / dplyr):
[Input: Data A] ---> (Fungsi Transformasi) ---> [Duplikasi: Salinan Data A'] ---> [Hasil: Data B]
                                                (Biaya: RAM x2, Siklus CPU Boros)

Model Sistem Mutasi Referensi (data.table / In-Place):
[Input: Data A (Pointer P1)] ---> [Modifikasi In-Place P1] ---> [Data A Termutasi (Pointer P1)]
                                  (Biaya: RAM x1, Salinan Vektor Terpilih / 0 Copy)
```

Untuk mencapai performa tinggi (*high-performance data wrangling*), seorang arsitek data R harus beralih ke **Sistem Mental Model Manipulasi Memori**:

1. **Data Frame adalah Koleksi Pointer**: Sebuah tabel di R adalah `list` yang berisi vektor-vektor bertipe homogen. Mengubah satu baris atau satu kolom tidak boleh menduplikasi kolom-kolom lain yang tidak tersentuh.
2. **RAM Cache-Locality**: Algoritma komputasi data modern harus memperhitungkan CPU cache (L1/L2/L3). Pengecekan data acak (*random pointer chasing*) menghancurkan efisiensi cache; data harus ditata secara sekuensial (vektor rapat) dan diagregasi melalui operasi level C yang menghindari interpretasi R evaluator secara berulang.
3. **Penyaringan Berbasis Indeks**: Melakukan evaluasi vektor logika berulang (`x == 1 & y == 2`) pada tabel dengan $10^7$ baris adalah pemborosan siklus komputasi. Pemanfaatan *radix order indexing* mengubah tabel data menjadi struktur data terindeks yang dapat diakses dalam hitungan milidetik.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur manipulasi data di memori R menunjukkan perbedaan mendasar antara manipulasi fungsional konvensional (COW) dengan teknik mutasi *in-place* serta pemanfaatan *binary search indexing*.

### Diagram 1: Mekanisme Copy-on-Modify vs In-Place Reference (`:=`)

```
========================================================================================
A. BASE R / DPLYR PIPELINE (Salin-pada-Modifikasi / Copy-on-Modify)
========================================================================================
Heap Memory Awal:
   [Data Frame: df] 
      ├── Col A: [Addr: 0x001] -> [1, 2, 3, 4, ...] (500 MB)
      └── Col B: [Addr: 0x002] -> ["x", "y", "z", ...] (500 MB)
Total RAM: 1 GB

Operasi: df$ColA <- df$ColA * 2
Langkah 1: R mengecek referensi counter (NAMED / REFCNT > 1).
Langkah 2: R mengalokasikan vektor baru untuk Col A, menduplikasi atribut tabel.
Heap Memory Setelah Mutasi:
   [Data Frame: df]
      ├── Col A: [Addr: 0x003] -> [2, 4, 6, 8, ...] (500 MB)  <-- MEMORI BARU DIBUAT
      └── Col B: [Addr: 0x002] -> ["x", "y", "z", ...] (500 MB)
   [Orphan Node] -> [Addr: 0x001] (Menunggu Garbage Collection)
Peak RAM: 1.5 GB s.d. 2 GB (berisiko Crash OOM pada data besar)

========================================================================================
B. DATA.TABLE (Modifikasi di Tempat / Modify-in-Place via `:=`)
========================================================================================
Heap Memory Awal:
   [data.table: dt] (Telah dialokasikan over-allocation slot atribut penunjuk)
      ├── Col A: [Addr: 0x101] -> [1, 2, 3, 4, ...] (500 MB)
      └── Col B: [Addr: 0x102] -> ["x", "y", "z", ...] (500 MB)
Total RAM: 1 GB

Operasi: dt[, ColA := ColA * 2]
Langkah 1: C-function `assign` memodifikasi alamat data di memori secara langsung 
           atau mengarahkan pointer Col A ke blok komputasi baru tanpa membuat salinan tabel.
Heap Memory Setelah Mutasi:
   [data.table: dt]
      ├── Col A: [Addr: 0x101] -> [2, 4, 6, 8, ...] (Memori lama di-overwrite in-place)
      └── Col B: [Addr: 0x102] -> ["x", "y", "z", ...] (Tidak berubah)
Peak RAM: Tetap 1 GB (Efisiensi penggunaan RAM = 100%)
```

### Diagram 2: Alur Pemfilteran: Vector Scan ($O(N)$) vs Binary Search Indexing ($O(\log N)$)

```
========================================================================================
VECTOR SCAN O(N) (Base R / dplyr filter: dt[ColA == "Target"])
========================================================================================
Baris:   [001]   [002]   [003]   [004]  ...  [100,000,000]
Kondisi: False   False   True    False       True
Evaluasi: CPU membaca 100 JUTA baris secara linier.
Waktu Eksekusi: Proporsional dengan N.

========================================================================================
BINARY SEARCH O(log N) (data.table with Primary Key: setkey(dt, ColA))
========================================================================================
1. Pra-komputasi: Kolom A diurutkan menggunakan Algoritma Radix Sort (O(N)).
2. Dibuat pointer tabel indeks internal.
Pencarian: "Target"

                     [Kunci Median: "M"]
                            /   \
                           /     \
             [Cari Kiri: < M]   [Cari Kanan: >= M]
                                       /   \
                                      /     \
                       [Kunci Median: "T"]  [> "T"]
                               /
                 [Ditemukan: Rentang Baris (Index)]
                 Hanya ~26 langkah perbandingan untuk 100 Juta Baris!
Waktu Eksekusi: Proporsional dengan log2(N). Sub-milidetik.
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur `SEXP` (S-Expression) dan Header Objek R
Dalam C internals R, setiap variabel adalah pointer ke struktur `SEXPREC`.
```c
/* Struktur penyederhanaan dari Rinternals.h */
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
        struct vecsxp_struct vecsxp;
    } u;
};
```
Di dalam `sxpinfo_struct`, terdapat penanda `REFCNT` (sebelumnya `NAMED`). 
- Jika `REFCNT == 0` atau `1`: Objek aman untuk dimodifikasi tanpa penyalinan.
- Jika `REFCNT > 1`: R menganggap objek memiliki alias variabel lain. Saat mutasi terjadi, R memicu mekanisme penyalinan (duplikasi node memori).

### 2. Modifikasi In-Place dan Over-Allocation di `data.table`
`data.table` melewati proteksi standar ini menggunakan implementasi C tingkat rendah (`assign.c`).
- **Over-allocation**: Ketika sebuah `data.table` diinisialisasi atau dikonversi dengan `setDT()`, `data.table` secara default mengalokasikan 100 slot pointer kosong tambahan pada daftar kolom (*column vector list*). Hal ini membuat penambahan kolom baru via `:=` tidak perlu mengalokasikan ulang struktur list tabel (`VECSXP`), melainkan hanya menempatkan pointer baru pada slot yang telah tersedia sebelumnya (*truelength*).
- **Shallow Copy vs Deep Copy**:
  - `copy()`: Memaksa duplikasi total (*deep copy*) pada seluruh data dan vektor di memori heap.
  - Operator `:=`: Melakukan intervensi langsung pada alamat memori kolom (*in-place*) atau menukar pointer internal kolom tanpa menyentuh kolom lainnya.

### 3. Mesin GForce Optimization
Ketika mengeksekusi agregasi seperti `dt[, .(mean_val = mean(x)), by = grp]`, R secara konvensional akan:
1. Memecah `x` menjadi sekumpulan vektor kecil sebanyak kelompok unik dalam `grp`.
2. Menjalankan fungsi R `mean()` pada masing-masing vektor kecil di dalam evaluasi lingkungan (overhead context-switching yang sangat masif).

`data.table` mengatasi hal ini dengan mesin **GForce**:
- Parser `data.table` memindai ekspresi pada parameter `j`.
- Jika mendeteksi fungsi dasar yang dioptimasi (misal: `mean`, `sum`, `min`, `max`, `head`, `tail`), GForce mengintersepsi panggilan tersebut.
- Agregasi dialihkan ke loop internal C terkompilasi (`gforce.c`) yang mengiterasi tabel yang telah diurutkan/dikelompokkan tanpa pernah memicu pemanggilan fungsi R evaluator sama sekali.

### 4. Mesin Agregasi Mikro `collapse`
Paket `collapse` membawa optimasi lebih jauh dengan tidak bergantung pada struktur data table.
- Menggunakan arsitektur komputasi tingkat C/C++ murni berorientasi array.
- Fungsi seperti `fsum`, `fmean`, `fgroup_by` memanfaatkan struktur pengelompokan berbasis hash C yang sangat padat (*fully vectorized grouping engine*).
- Memanfaatkan instruksi CPU SIMD (*Single Instruction, Multiple Data*) secara langsung melalui penyusunan array yang terpadu, mengurangi cache miss pada L1/L2 data cache prosesor.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Sintaksis Unified `DT[i, j, by]`

Fondasi utama komputasi berkinerja tinggi dalam `data.table` distandarkan dalam ekspresi berikut:

$$\text{DT}[\underbrace{i}_{\text{Filter/Join/Index}}, \quad \underbrace{j}_{\text{Komputasi/Proyeksi}}, \quad \underbrace{\text{by}}_{\text{Pengelompokan/Split-Apply-Combine}}]$$

Secara matematis dan operasional sistem:
* **Argumen `i`**: Mengontrol pemilih subset baris. Jika diisi dengan ekspresi logika, mesin melakukan pemindaian atau binary search. Jika diisi objek `data.table` lain, operasi bertransformasi menjadi Relational Join (Equi, Non-Equi, atau Rolling Join).
* **Argumen `j`**: Mengevaluasi ekspresi komputasi di dalam konteks kolom tabel (menggunakan NSE). Komputasi dihitung langsung pada subset yang dihasilkan dari `i`. Jika operator `:=` digunakan di `j`, hasil dieksekusi secara *in-place*.
* **Argumen `by`**: Menerima daftar vektor yang membagi dataset ke dalam partisi (*hash partitions* atau *radix-sorted partitions*).

### Non-Equi Joins dan Rolling Joins

Salah satu fitur paling kompleks dan berkinerja tinggi adalah kemampuannya melakukan penggabungan data berbasis rentang tanpa operasi Cartesian product penuh ($O(N \times M)$) yang boros memori.

* **Non-Equi Join**: Menggabungkan dua tabel berbasis ketidaksamaan logis:
  $$T_1 \bowtie_{T_1.t_1 \le T_2.t \le T_1.t_2} T_2$$
  Menggunakan struktur pohon interval berbasis indeks binary sort C-level, menjaga konsumsi memori tetap $O(N + M)$.
* **Rolling Join (Last Observation Carried Forward / LOCF)**:
  Sangat penting dalam domain finansial dan time-series data. Ketika mencari nilai transaksi terakhir sebelum event log terjadi, binary search bergerak menemukan elemen indeks terdekat ($t_{\text{prev}} = \max(\{k \in T_{\text{ref}} \mid k \le t\})$) dengan kompleksitas $O(M \log N)$.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi komparatif komprehensif yang menguji mekanisme memori, mutasi in-place, pengindeksan biner, dan performa mutasi.

```r
# ==============================================================================
# 01. SETUP DAN PEMBUKTIAN COPY-ON-MODIFY VS IN-PLACE
# ==============================================================================

# Install dan muat pustaka esensial
pkgs <- c("data.table", "collapse", "lobstr", "bench")
to_install <- pkgs[!pkgs %in% installed.packages()[, "Package"]]
if (length(to_install) > 0) install.packages(to_install)

library(data.table)
library(collapse)
library(lobstr)
library(bench)

# Konfigurasi Threading OpenMP untuk data.table
setDTthreads(percent = 100) # Memaksimalkan seluruh core CPU

# 1. Eksperimen Alamat Memori (Base R vs data.table)
message("--- Pembuktian Copy-On-Modify Base R ---")
df_base <- data.frame(
  id = 1:5,
  val = c(10.5, 20.1, 30.2, 40.8, 50.9)
)

message("Pointer df_base awal : ", obj_addr(df_base))
message("Pointer kolom val awal: ", obj_addr(df_base$val))

# Mutasi pada base R
df_base$val[1] <- 99.9
message("Pointer df_base pasca mutasi : ", obj_addr(df_base))
message("Pointer kolom val pasca mutasi: ", obj_addr(df_base$val), " (Berubah! Terjadi Copy)")

message("\n--- Pembuktian Mutasi In-Place data.table ---")
dt_fast <- data.table(
  id = 1:5,
  val = c(10.5, 20.1, 30.2, 40.8, 50.9)
)

message("Pointer dt_fast awal : ", obj_addr(dt_fast))
message("Pointer kolom val awal: ", obj_addr(dt_fast$val))

# Mutasi In-Place menggunakan operator :=
dt_fast[1, val := 99.9]
message("Pointer dt_fast pasca := : ", obj_addr(dt_fast), " (Tetap Identik!)")
message("Pointer kolom val pasca :=: ", obj_addr(dt_fast$val), " (Modifikasi In-Place)")

# ==============================================================================
# 02. GENERASI DATASET SKALA BESAR (10 JUTA BARIS)
# ==============================================================================
set.seed(42)
n_rows <- 10e6

message("\nMembuat dataset skala besar (", n_rows, " baris)...")
DT_large <- data.table(
  trans_id   = 1:n_rows,
  account_id = sample(sprintf("ACC_%07d", 1:500000), n_rows, replace = TRUE),
  category   = sample(c("TECH", "FIN", "HEALTH", "RETAIL", "ENERGY"), n_rows, replace = TRUE),
  amount     = round(runif(n_rows, 5.0, 5000.0), 2),
  timestamp  = as.POSIXct("2026-01-01") + runif(n_rows, 0, 86400 * 30)
)

# ==============================================================================
# 03. BENCHMARKING: LINEAR SCAN VS BINARY SEARCH INDEXING
# ==============================================================================
target_acc <- "ACC_0042420"

message("\n--- Uji Komparasi Waktu Eksekusi Filter ---")
# 1. Linear scan tanpa indeks
bench_scan <- bench::mark(
  scan_linear = DT_large[account_id == target_acc],
  iterations = 5,
  check = FALSE
)

# 2. Set Secondary Index
setindex(DT_large, account_id)

# 3. Binary Search menggunakan secondary index via on=
bench_index <- bench::mark(
  binary_search = DT_large[.(target_acc), on = "account_id"],
  iterations = 5,
  check = FALSE
)

print(bench_scan[, c("expression", "min", "median", "mem_alloc")])
print(bench_index[, c("expression", "min", "median", "mem_alloc")])

# ==============================================================================
# 04. NON-EQUI JOINS & ROLLING JOINS
# ==============================================================================
# Skenario: Menemukan kupon diskon dinamis yang valid pada waktu transaksi
promos <- data.table(
  account_id = c("ACC_0042420", "ACC_0042420", "ACC_0000001"),
  promo_start = as.POSIXct(c("2026-01-05 00:00:00", "2026-01-20 00:00:00", "2026-01-10 00:00:00")),
  promo_end   = as.POSIXct(c("2026-01-15 23:59:59", "2026-01-25 23:59:59", "2026-01-15 23:59:59")),
  discount    = c(0.15, 0.25, 0.10)
)

# Eksekusi Non-Equi Join: Gabungkan transaksi dengan promo yang berlaku
matched_promos <- promos[
  DT_large, 
  on = .(account_id == account_id, promo_start <= timestamp, promo_end >= timestamp),
  nomatch = NULL,
  .(trans_id, account_id, timestamp, amount, discount)
]

message("\nContoh Hasil Non-Equi Match:")
print(head(matched_promos, 3))
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis mekanistik dari instruksi kode pada Seksi 07:

1. **`setDTthreads(percent = 100)`**: Menginstruksikan C layer internal `data.table` untuk menggunakan seluruh logical cores yang terdeteksi via OpenMP runtime library. Operasi sorting, filtering, dan grouping akan dijalankan secara multithreaded.
2. **`lobstr::obj_addr(df_base)`**: Membaca pointer alamat memori C langsung (`0x...`) dari objek `SEXPREC`.
3. **`df_base$val[1] <- 99.9`**: Memicu evaluasi Copy-on-Modify di base R. Karena `df_base` memiliki binding simbol di global environment, R mengkloning vektor `val` ke alamat memori baru, memperbarui struktur internal, dan membuang node lama.
4. **`dt_fast[1, val := 99.9]`**: Operator `:=` mengalihkan eksekusi ke C-function `assign()`. R tidak melakukan re-binding objek atau menduplikasi list kolom; perubahan nilai dilakukan secara langsung pada offset indeks byte pertama array floating-point di RAM.
5. **`setindex(DT_large, account_id)`**: Berbeda dari `setkey()`, fungsi ini tidak mengurutkan ulang fisik tabel di RAM (menghemat biaya pergeseran baris). Sebaliknya, fungsi ini menghitung urutan radix sort hanya pada kolom `account_id` dan menyimpannya sebagai vektor integer tersembunyi pada atribut `index` dari `DT_large`.
6. **`DT_large[.(target_acc), on = "account_id"]`**: Sintaks `.(target_acc)` menciptakan list skalar tunggal. Argumen `on = "account_id"` memicu penggunaan secondary index yang telah dibuat sebelumnya. Algoritma melakukan *binary search* langsung pada atribut indeks dengan kompleksitas $O(\log N)$ alih-alih mengevaluasi setiap baris ($O(N)$).
7. **`promos[DT_large, on = .(account_id == account_id, promo_start <= timestamp, promo_end >= timestamp)]`**:
   - `promos` adalah tabel target pencarian baris.
   - Operasi join diatur oleh relasi kesetaraan dan ketidaksetaraan logika rentang waktu.
   - `nomatch = NULL` memastikan *inner join* dieksekusi, membuang transaksi yang tidak jatuh dalam rentang masa aktif kupon tanpa menciptakan baris bernilai `NA` yang membebani alokasi vektor output.

---

## SEKSI 09 — STUDI KASUS NYATA

### Masalah Produksi: Real-Time Algorithmic Audit Financial Ledger
Sebuah institusi perbankan digital memiliki log transaksi frekuensi tinggi (*tick data*) harian dengan beban volume 25.000.000 transaksi. Setiap hari, tim arsitek analitik wajib memproses:
1. Pembersihan data transaksi anomali (*invalid timestamps/negative amounts*).
2. Penyatuan data ledger transaksi terhadap snapshot kurs mata uang asing dinamis (*currency exchange snapshots*) yang diperbarui setiap 15 detik menggunakan sistem *as-of joining* / *rolling join*.
3. Perhitungan metrik kumulatif per akun nasabah: *rolling 30-day cumulative transaction amount*, *transaction velocity (frekuensi per jam)*, dan *exposure anomaly ratio*.
4. Pipeline harus berjalan dalam memori server dengan batasan RAM maksimal **8 GB** dan total waktu eksekusi di bawah **15 detik**.

Implementasi berbasis `base R` atau `dplyr` konvensional akan mengalami crash *OOM (Out-of-Memory)* atau *swap-thrashing* karena penggandaan objek berkali-kali saat agregasi jendela (*window functions*) pada data sebesar ini.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah kode produksi teroptimasi penuh menggunakan integrasi `data.table` dan `collapse` untuk menyelesaikan studi kasus di atas dengan performa tinggi.

```r
# ==============================================================================
# PIPELINE AUDIT TRANSAKSI KEUANGAN HIGH-PERFORMANCE
# ==============================================================================
library(data.table)
library(collapse)
library(bench)

# Atur lingkungan thread
setDTthreads(0) # 0 = Deteksi otomatis semua core fisik & logis

# 1. SIMULASI DATASET TICK REALISTIS (25 JUTA BARIS)
generate_production_data <- function() {
  n_tx <- 25e6
  message("Mengalokasikan memori awal untuk 25 juta transaksi...")
  
  # Timestamp acak berurutan dalam rentang 24 jam
  start_epoch <- as.numeric(as.POSIXct("2026-03-30 00:00:00", tz = "UTC"))
  
  tx_table <- data.table(
    tx_id     = 1:n_tx,
    acc_id    = sample(1:200000, n_tx, replace = TRUE),
    currency  = sample(c("USD", "EUR", "JPY", "GBP"), n_tx, replace = TRUE),
    raw_amt   = round(rexp(n_tx, rate = 0.002) + 1, 2),
    timestamp = as.POSIXct(start_epoch + sort(runif(n_tx, 0, 86400)), 
                           origin = "1970-01-01", tz = "UTC")
  )
  
  # Data Snapshot Kurs (Update tiap 15 detik = 5760 baris per mata uang)
  fx_times <- seq(from = as.POSIXct("2026-03-30 00:00:00", tz = "UTC"),
                  to   = as.POSIXct("2026-03-30 23:59:59", tz = "UTC"), 
                  by   = "15 sec")
  
  fx_rates <- rbindlist(lapply(c("USD", "EUR", "JPY", "GBP"), function(curr) {
    base_rate <- switch(curr, "USD" = 1.0, "EUR" = 1.08, "JPY" = 0.0067, "GBP" = 1.28)
    data.table(
      currency  = curr,
      fx_time   = fx_times,
      rate_usd  = base_rate * (1 + sin(seq_along(fx_times) / 100) * 0.02)
    )
  }))
  
  return(list(tx = tx_table, fx = fx_rates))
}

# Inisialisasi Data
data_bundle <- generate_production_data()
tx_data <- data_bundle$tx
fx_data <- data_bundle$fx
rm(data_bundle) # Bebaskan memori pointer awal
invisible(gc())

# ==============================================================================
# 2. PIPELINE PRODUKSI: ROLLING JOIN & AGREGASI TINGKAT LANJUT
# ==============================================================================

execute_audit_pipeline <- function(dt_tx, dt_fx) {
  
  message("Memulai High-Performance Pipeline...")
  time_start <- Sys.time()
  
  # Langkah A: Validasi & Filtering In-Place
  # Menggunakan i subsetting tanpa duplikasi tabel
  dt_tx <- dt_tx[raw_amt > 0 & !is.na(timestamp)]
  
  # Langkah B: Persiapan Pengurutan untuk Rolling Join
  # Rolling join membutuhkan pengurutan pada join keys
  setkeyv(dt_fx, c("currency", "fx_time"))
  setkeyv(dt_tx, c("currency", "timestamp"))
  
  # Langkah C: Rolling Join (LOCF - Last Observation Carried Forward)
  # Mengaitkan setiap transaksi ke snapshot rate_usd paling terkini (roll = TRUE)
  message("Mengeksekusi Rolling Join (LOCF As-Of Match)...")
  dt_tx <- dt_fx[dt_tx, roll = TRUE, on = .(currency, fx_time = timestamp)]
  
  # Ubah nama kolom hasil join secara in-place
  setnames(dt_tx, old = "fx_time", new = "timestamp")
  
  # Langkah D: Mutasi In-Place Terhitung (Normalisasi ke USD)
  message("Kalkulasi Normalisasi In-Place (:=)...")
  dt_tx[, amt_usd := raw_amt * rate_usd]
  
  # Langkah E: Akselerasi Agregasi Ekstrem menggunakan Mesin 'collapse'
  message("Agregasi Akun Keuangan via collapse Micro-Engine...")
  
  # Ekstraksi komponen jam secara in-place via ITime
  dt_tx[, tx_hour := as.integer(as.ITime(timestamp)) %/% 3600L]
  
  # Gunakan Fast Group By dan Fast Aggregation dari collapse
  # Pengelompokan multi-kolom yang optimal secara biner
  g_acc <- GRP(dt_tx, by = c("acc_id", "tx_hour"), sort = FALSE)
  
  summary_metrics <- fsummarise(
    dt_tx,
    total_usd       = fsum(amt_usd, g_acc),
    mean_usd        = fmean(amt_usd, g_acc),
    max_usd         = fmax(amt_usd, g_acc),
    tx_count        = fnobs(amt_usd, g_acc),
    keep.group_vars = TRUE
  )
  
  time_end <- Sys.time()
  message("Pipeline Selesai dalam: ", round(difftime(time_end, time_start, units = "secs"), 2), " detik.")
  
  return(summary_metrics)
}

# Eksekusi Pipeline
audit_result <- execute_audit_pipeline(tx_data, fx_data)

# Tampilkan ringkasan hasil
message("\nStruktur Hasil Ringkasan Agregasi:")
print(head(audit_result, 5))
message("Total Grup Unik Dihasilkan: ", nrow(audit_result))
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Untuk memilih mesin manipulasi data tabular yang tepat di ekosistem R, pertimbangkan karakteristik arsitektur berikut:

| Karakteristik | `base R` (`data.frame`) | `tidyverse` (`dplyr`) | `data.table` | `collapse` | `duckdb` (In-Memory) |
|---|---|---|---|---|---|
| **Paradigma Memori** | Copy-on-Modify (COW) | COW Murni & Immutability | Pass-by-reference (`:=`) | In-Place / Reference Oriented | Kolom Terkompresi Buffer |
| **Penggunaan RAM Puncak** | Ekstrem (2x s.d. 4x N) | Tinggi (1.5x s.d. 3x N) | Minimal (1x N) | Sangat Minimal (Optimal SIMD) | Terkendali (Disk Spillover) |
| **Indexing Support** | Tidak Ada (Hanya Row Names) | Tidak Ada | Binary Search (Key & Index) | Hashing Terkompilasi C | B-Tree / Min-Max Indices |
| **Sintaksis & Readability** | Bertele-tele / Kuno | Deklaratif Ekspresif (`%>%`) | Kompak / Terpadu `[i, j, by]` | Fungsional Terfokus (`f*`) | Dialek Standar ANSI-SQL |
| **Overhead Operasi Kecil** | Rendah | Sangat Tinggi (NSE Overhead) | Rendah (GForce Engine) | Terendah (Mikrodetik C-level)| Moderat (Query Parsing) |
| **Kecepatan $N > 10^7$ Baris**| Lambat / Sering Crash | Terkendala Bottleneck RAM | Sangat Cepat | Paling Cepat di CPU Core | Cepat (Optimal Disk/RAM) |
| **Dependensi Eksternal** | Tidak Ada (Built-in) | Kompleks (Rcpp, rlang, vctrs)| Ringan (Hanya C dasar) | Sangat Ringan (C/C++ murni)| Binari C++ Mandiri |

### Kapan Menggunakan Apa?
* Pilih **`dplyr`**: Ketika dataset berukuran kecil hingga menengah ($N < 10^6$ baris), keterbacaan kode (*readability*) adalah prioritas tim, dan pemrosesan tidak berjalan dalam batasan latensi kritis.
* Pilih **`data.table`**: Pilihan standar industri untuk dataset besar ($10^6 - 10^8$ baris), manipulasi *in-place*, mutasi kolom masif, penggabungan kompleks (*rolling/non-equi joins*), dan server dengan keterbatasan RAM.
* Pilih **`collapse`**: Ketika melakukan komputasi statistik murni (transformasi data runtun waktu, standarisasi, agregasi multidimensi) yang menuntut latensi mikro-detik atau optimasi instruksi level prosesor.
* Pilih **`duckdb`**: Ketika ukuran dataset melampaui kapasitas RAM fisik mesin (*Out-of-Core Processing*) dan membutuhkan pembacaan langsung dari file Parquet/Arrow.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Perangkap Shallow Copy pada Penugasan Objek (`dt2 <- dt1`)
Salah satu kesalahan paling destruktif adalah mengira operator assignment R (`<-`) membuat objek baru pada `data.table`:
```r
dt1 <- data.table(a = c(1, 2, 3))
dt2 <- dt1 # BUKAN duplikasi! Hanya penunjuk pointer baru ke memori yang sama.

dt2[, a := 999] # Modifikasi dt2
print(dt1$a)    # Menghasilkan c(999, 999, 999)! dt1 ikut termutasi secara tidak sengaja.
```
*Solusi*: Gunakan fungsi eksplisit `dt2 <- copy(dt1)` jika Anda menginginkan salinan independen.

### 2. Modifikasi Data Table di Dalam Fungsi (Side-Effects Ruang Lingkup)
Karena modifikasi `:=` bekerja pada referensi memori, memodifikasi `data.table` yang diparsing ke dalam fungsi lokal akan mengubah objek asli di global environment pemanggil, melanggar prinsip *function purity*:
```r
add_feature <- function(DT) {
  DT[, new_col := 1] # PERINGATAN: Memodifikasi objek global secara permanen
  return(invisible(NULL))
}
```

### 3. Pengurutan Kunci Mengubah Tata Letak Fisik Baris
Mengeksekusi `setkey(DT, col)` melakukan penataan fisik (*in-place physical reordering*) pada baris-baris tabel di RAM. Jika ada pointer baris atau subset eksternal yang merujuk pada urutan baris sebelumnya, relasi tersebut menjadi tidak valid.

### 4. Over-Allocation Exhaustion Saat Penambahan Kolom Masif
Meskipun `data.table` memiliki over-allocation (biasanya 100 slot), menambahkan lebih dari 100 kolom individual secara berulang menggunakan `:=` di dalam loop akan memaksa tabel melakukan *re-allocation* struktural berulang kali.
*Solusi*: Gunakan sintaks *multiple-column assignment*: `DT[, (cols) := list(...)]` atau alokasikan slot di awal via `setalloccol(DT, n = 1000)`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Penyalahgunaan `.SD` pada Agregasi Kolom Tunggal
```r
# BURUK: Sangat lambat! Memaksa data.table mengalokasikan sub-data.table (.SD) 
# untuk setiap grup unik secara berulang-ulang di R heap.
dt[, lapply(.SD, mean), by = grp, .SDcols = "val"]

# BAIK: Memanfaatkan C-level GForce Optimization
dt[, .(val = mean(val)), by = grp]
```

### Kesalahan 2: Menggunakan Logika Seleksi Kolom Tradisional yang Memicu Duplikasi
```r
# BURUK: df[, "new_col"] <- val
# Base R membuat salinan penuh data frame jika REFCNT > 1.

# BAIK: In-place column insertion
set(dt, i = NULL, j = "new_col", value = val) # Eksekusi tercepat tanpa evaluasi NSE
# ATAU:
dt[, new_col := val]
```

### Kesalahan 3: Memfilter Kolom Terindeks Menggunakan Vektor Seleksi Logika Tradisional
```r
# BURUK: Mengabaikan indeks yang sudah dibangun (Linear Scan O(N))
setkey(dt, account_id)
res <- dt[dt$account_id == "ACC_001"] # Mengevaluasi ekspresi logika N baris secara redundan

# BAIK: Memanfaatkan Binary Search Syntax O(log N)
res <- dt[.("ACC_001")]
```

### Kesalahan 4: Penggabungan Banyak Tabel Menggunakan Iterasi `Reduce` Tanpa Kontrol Alokasi
```r
# BURUK: Menghasilkan salinan memori N-1 kali
tables_list <- list(dt1, dt2, dt3, dt4)
result <- Reduce(function(x, y) merge(x, y, by = "id"), tables_list)

# BAIK: Menggabungkan secara bertahap atau menggunakan rbindlist teralokasi
result <- rbindlist(tables_list, use.names = TRUE, fill = TRUE)
```

### Kesalahan 5: Konversi Tipe Data Tersembunyi (Implicit Type Coercion)
```r
# BURUK: Mengubah kolom integer menjadi numeric in-place menghasilkan peringatan C
dt <- data.table(val = 1:5) # Tipe Integer
dt[1, val := 3.14159]       # 3.14159 dipotong (truncated) menjadi 3 secara paksa!

# BAIK: Ubah tipe data kolom secara eksplisit sebelum melakukan mutasi pecahan
dt[, val := as.numeric(val)]
dt[1, val := 3.14159]
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan `setDT()` dan Jangan Pernah Memakai `as.data.table()` pada Objek Mentah**:
   `as.data.table(df)` menduplikasi seluruh data frame di heap. Sebaliknya, `setDT(df)` hanya mengonversi penunjuk pointer internal kelas secara langsung pada objek asal (*zero-copy transition*).
2. **Kompilasi Penggunaan Loop dengan `set()`**:
   Jika Anda terpaksa mengiterasi ratusan baris atau kolom secara imperative (misal: imputasi nilai berulang), hindari operator `:=` di dalam loop R karena memiliki overhead parsing ekspresi NSE. Gunakan fungsi C murni `set(DT, i, j, value)`.
3. **Manajemen Konfigurasi Utas Terpusat (*Threading Governance*)**:
   Selalu konfigurasikan `setDTthreads()` di tingkat bootstrap skrip produksi. Jangan biarkan *thread* mengonsumsi virtual core secara berlebihan pada lingkungan container (Docker/Kubernetes) yang memiliki batas *cgroups CPU limits*, karena dapat memicu degradasi kinerja akibat context switching yang parah.
4. **Standardisasi Penamaan Kolom Pasca Mutasi**:
   Gunakan idiom `setnames(DT, old, new)` untuk mengganti nama kolom secara *in-place* alih-alih membangun vektor `names(DT) <- c(...)` yang menduplikasi atribut nama tabel.
5. **Pemisahan Kolom Karakter Monolitik via `tstrsplit`**:
   Untuk memecah teks string menjadi beberapa kolom, gunakan fungsi internal C `data.table::tstrsplit()` yang mengeliminasi overhead pembuatan struktur matriks perantara yang biasanya dihasilkan oleh `strsplit`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Penskalaan Memori: Downcasting Kolom

Secara default, R mengalokasikan integer sebagai 32-bit (4 byte) dan numeric/double sebagai 64-bit (8 byte). Seringkali data tanggal, identifier, atau diskrit diimpor sebagai numerik atau string teks yang sangat boros memori heap.

```r
downcast_memory <- function(DT) {
  # 1. Konversi teks kardinalitas rendah menjadi integer factor
  char_cols <- names(DT)[sapply(DT, is.character)]
  for (col in char_cols) {
    if (uniqueN(DT[[col]]) < (nrow(DT) * 0.05)) { # Kardinalitas < 5%
      set(DT, j = col, value = as.factor(DT[[col]]))
    }
  }
  
  # 2. Konversi POSIXct menjadi IDate dan ITime (Hanya 4 byte integer!)
  time_cols <- names(DT)[sapply(DT, function(x) inherits(x, "POSIXct"))]
  for (col in time_cols) {
    date_name <- paste0(col, "_date")
    time_name <- paste0(col, "_time")
    set(DT, j = date_name, value = as.IDate(DT[[col]]))
    set(DT, j = time_name, value = as.ITime(DT[[col]]))
    set(DT, j = col, value = NULL) # Hapus kolom 8-byte POSIXct asli secara in-place
  }
  
  return(invisible(DT))
}
```

### Optimalisasi GForce: Struktur Penulisan Kode
Agar eksekusi kode Anda diintersepsi oleh compiler C GForce tanpa memicu interpretasi evaluasi R, Anda harus membatasi ekspresi ke dalam fungsi bawaan yang didukung:
- Didukung GForce: `min()`, `max()`, `mean()`, `median()`, `head()`, `tail()`, `sum()`, `var()`, `sd()`, `prod()`.
- Hindari nesting rumit seperti `dt[, .(res = log(mean(val) + 1)), by = grp]`. Lebih baik pisahkan menjadi:
  ```r
  dt[, .(res = mean(val)), by = grp][, res := log(res + 1)]
  ```
  Langkah pertama mengeksekusi GForce aggregation berkecepatan tinggi, dan langkah kedua memproses mutasi vektor sederhana.

---

## SEKSI 16 — KEAMANAN & HARDENING

Manipulasi data tabel di lingkungan analitik produksi menghadapi dua ancaman utama: **Injeksi Kode Ekspresi Dinamis** dan **Denial of Service (DoS) melalui Kehabisan Memori (OOM)**.

### 1. Pencegahan Injeksi pada Evaluasi Non-Standar (NSE)
Jika pipeline Anda menerima nama kolom dari input pengguna (misal: REST API endpoint via `plumber`), jangan pernah mengevaluasi ekspresi string mentah menggunakan `eval(parse(text = ...))`.

```r
# SANGAT RENTAN TERHADAP REMOTE CODE EXECUTION (RCE)
# user_input <- "val); system('rm -rf /'); ("
# dt[, eval(parse(text = paste0("mean(", user_input, ")")))]

# METODE AMAN (Hardened Programmatic Interface)
safe_aggregation <- function(dt, target_column, group_column) {
  # Validasi eksplisit integritas kolom terhadap metadata tabel
  valid_cols <- names(dt)
  if (!target_column %chin% valid_cols || !group_column %chin% valid_cols) {
    stop("Security Alert: Permintaan akses kolom ilegal terdeteksi.")
  }
  
  # Gunakan sintaksis programmatic injection resmi yang aman (env-bound)
  dt[, .(result = mean(.SD[[1]], na.rm = TRUE)), 
     by = c(group_column), 
     .SDcols = target_column]
}
```

### 2. Membatasi Alokasi Memori Heap untuk Menghindari OOM Panic
Pada Linux produksi, ketika R melebihi alokasi RAM yang tersedia, kernel Linux akan memanggil *OOM Killer* yang secara tiba-tiba mengirim sinyal `SIGKILL` (Exit 137), mematikan seluruh proses instans tanpa jejak log.

Konfigurasikan pembatas memori di tingkat sesi R:
```r
# Batasi memori heap R maksimal 16 GB (Satuan MegaBytes)
if (.Platform$OS.type == "unix") {
  unix::rlimit_as(16 * 1024 * 1024 * 1024) 
}
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk mendiagnosis perilaku operasional, pemakaian memori, dan mengidentifikasi apakah query dialihkan ke binary search atau GForce, gunakan instrumen observabilitas internal berikut.

### 1. Mengaktifkan Verbose Logging Mesin `data.table`
Setel opsi global berikut untuk memaksa R mencetak keputusan C internal ke console:
```r
options(datatable.verbose = TRUE)

# Uji eksekusi
dt <- data.table(x = sample(1:100, 1e6, replace = TRUE), y = 1:1e6)
setkey(dt, x)
res <- dt[.(50)]
```
*Output internal yang ditampilkan meliputi*:
- Durasi waktu pengurutan (*radix sort timing*).
- Status aktivasi: `Lookup done in ... secs. Using 12 threads. Found starting and ending point using binary search in ... secs.`
- Keterangan apakah GForce diaktifkan (`Optimized j to ...`).

### 2. Profiling Alokasi Memori dengan `bench::mark()`
Evaluasi performa data wrangling tidak boleh hanya mengukur *wall-clock time*, tetapi wajib melacak metrik alokasi memori (*allocation count* dan *garbage collection count*):

```r
profile_summary <- bench::mark(
  method_inplace = dt[, z := y * 2],
  method_copy    = { dt_copy <- copy(dt); dt_copy$z <- dt_copy$y * 2 },
  iterations = 10,
  check = FALSE
)

# Render metrik observabilitas
print(profile_summary[, c("expression", "min", "median", "mem_alloc", "n_gc")])
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Pola Sintaksis Cepat `data.table`

```r
# Inisialisasi Tanpa Copy
setDT(df) 

# Mutasi Kolom In-Place
DT[, new_col := val]                                # Kolom Tunggal
DT[, c("c1", "c2") := .(v1, v2)]                    # Banyak Kolom
DT[cond, col := new_val]                            # Mutasi Kondisional
DT[, col := NULL]                                   # Hapus Kolom In-Place

# Agregasi Terindeks Berkecepatan Tinggi
DT[, .(mu = mean(val), n = .N), by = .(grp1, grp2)] # GForce Fast Aggregate
DT[, .N, by = grp]                                  # Fast Frequency Count

# Indeks & Binary Search
setkey(DT, col1, col2)                              # Primary Sorted Key
setindex(DT, col1)                                  # Secondary Radix Index
DT[.("target_val")]                                 # Binary Search via Key
DT[.("target_val"), on = "col1"]                    # Binary Search via Index

# Join Cepat
DT_left[DT_right, on = .(id)]                       # Right Outer Join
DT_right[DT_left, on = .(id), nomatch = NULL]       # Inner Join
DT_rates[DT_ticks, roll = TRUE, on = .(t)]          # Rolling Join (LOCF)
DT_promo[DT_orders, on = .(start <= date, end >= date)] # Non-Equi Join
```

### Panduan Cepat Padanan Fungsi `collapse`

* `dplyr::group_by() %>% summarise(mean(x))` $\rightarrow$ `collapse::fgroup_by() %>% collapse::fmean()`
* `dplyr::mutate(x - mean(x))` $\rightarrow$ `collapse::fwithin(x, g = grp)`
* `base::scale(x)` $\rightarrow$ `collapse::fscale(x)`
* Pengecekan grup unik: `collapse::fNDistinct(x)` (Jauh lebih cepat dari `uniqueN()`).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Ujilah pemahaman konseptual dan teknis Anda melalui soal-soal evaluasi berikut.

### Kategori Basic

1. **Apa yang secara fisik terjadi pada memori heap R saat Anda menjalankan sintaks `df$val <- df$val + 1` pada objek `data.frame` standar yang memiliki lebih dari satu referensi?**
   * A) Memori dimodifikasi secara langsung pada blok biner yang sama tanpa ada alokasi baru.
   * B) R memicu Copy-on-Modify (COW), mengalokasikan vektor baru untuk kolom `val`, menduplikasi struktur penunjuk list, dan membiarkan vektor lama menunggu Garbage Collection.
   * C) R memunculkan error proteksi pointer memori.
   * D) Ukuran dataset dipangkas menjadi separuh.

2. **Operator `:=` pada `data.table` digunakan untuk:**
   * A) Membuat salinan *deep copy* dari objek tabel yang sedang aktif.
   * B) Melakukan perbandingan logika kesetaraan tipe nilai (*strictly equal*).
   * C) Memperbarui, membuat, atau menghapus kolom secara langsung pada referensi memori asal (*pass-by-reference* / *in-place*).
   * D) Mengimpor file format CSV ke dalam memori secara multi-threaded.

3. **Perbedaan fungsional utama antara `setkey()` dan `setindex()` adalah:**
   * A) `setkey()` mengubah urutan baris data secara fisik di RAM; `setindex()` mempertahankan urutan fisik dan hanya membuat vektor indeks pencarian biner di metadata.
   * B) `setindex()` hanya dapat bekerja pada tipe data string teks.
   * C) `setkey()` tidak mendukung operasi binary join.
   * D) `setindex()` memerlukan paket pihak ketiga tambahan.

4. **Variabel internal `.N` di dalam argumen `j` pada `data.table` merepresentasikan:**
   * A) Pointer indeks baris saat ini.
   * B) Jumlah total kolom dalam tabel data.
   * C) Jumlah total baris di dalam grup saat ini atau dalam tabel secara keseluruhan.
   * D) Nilai rata-rata dari seluruh baris numerik.

5. **Mengapa pemanggilan fungsi `setDT(df)` lebih disukai daripada `df <- as.data.table(df)` dalam sistem pemrosesan data bervolume gigabyte?**
   * A) `setDT()` mengubah struktur list secara *in-place* tanpa duplikasi objek; `as.data.table()` membuat salinan baru dari seluruh memori data frame.
   * B) `setDT()` secara otomatis mengompresi format file menjadi Parquet.
   * C) `as.data.table()` membatasi pemrosesan hanya pada 1 core CPU.
   * D) `setDT()` memaksa seluruh kolom dikonversi menjadi tipe numerik.

---

### Kategori Intermediate

6. **Sebuah pipeline analitik mengeksekusi agregasi berikut:**
   ```r
   dt[, lapply(.SD, mean), by = category]
   ```
   **Mengapa agregasi ini menunjukkan waktu eksekusi yang lambat pada tabel dengan 500.000 grup unik, dan bagaimana cara memulihkannya?**
   * A) Pengelompokan multi-kategori tidak didukung OpenMP; solusi: gunakan `setDTthreads(1)`.
   * B) `.SD` mengalokasikan objek `data.table` kecil baru sebanyak 500.000 kali di heap R; solusi: gunakan agregasi kolom langsung `.(val = mean(val))` agar mesin C GForce aktif, atau gunakan fungsi `collapse::fmean`.
   * C) Kolom kategori berformat string; solusi: ubah ke integer lalu hapus.
   * D) R kehabisan buffer grafis saat parsing tabel.

7. **Perhatikan cuplikan kode berikut:**
   ```r
   DT <- data.table(id = 1:3, score = c(10, 20, 30))
   DT_sub <- DT[id >= 2]
   DT_sub[, score := score * 2]
   ```
   **Berdasarkan arsitektur alokasi memori `data.table`, apa yang terjadi pada nilai `score` pada objek asli `DT`?**
   * A) Nilai `score` pada baris 2 dan 3 di `DT` berubah menjadi 40 dan 60.
   * B) Seluruh tabel `DT` terhapus dari heap memory.
   * C) Nilai `DT` tidak berubah, karena hasil ekspresi subsetting `DT[...]` secara otomatis menghasilkan alokasi objek tabel baru (*deep copy* secara default pada evaluasi `i`).
   * D) Muncul peringatan `Error: Memory bounds mismatch`.

8. **Dalam analisis time-series transaksi frekuensi tinggi, apa keunggulan utama Rolling Join (`roll = TRUE`) dibandingkan dengan Regular Equi Join (`on = .(timestamp)`)?**
   * A) Menghilangkan kebutuhan untuk mengonversi data ke tipe waktu POSIXct.
   * B) Mengurangi kompleksitas join menjadi $O(1)$ amortized.
   * C) Mampu mencocokkan event secara instan terhadap data historis snapshot terakhir yang tersedia (*as-of match*) meskipun nilai timestamp persisnya tidak identik.
   * D) Menggabungkan tabel hanya dengan membandingkan nama kolom tanpa memeriksa nilainya.

9. **Apa yang melatarbelakangi paket `collapse` dapat mengungguli kecepatan fungsi dasar `data.table` pada agregasi statistik tertentu?**
   * A) `collapse` mengubah seluruh kode R menjadi script Python tersembunyi.
   * B) `collapse` mengimplementasikan algoritma hashing level C/C++ modern yang sangat optimal dengan SIMD vectorization tanpa melalui layer overhead parsing R expression.
   * C) `collapse` selalu menulis data perantara ke Solid-State Drive (SSD).
   * D) `collapse` mematikan mekanisme garbage collection R secara permanen.

10. **Anda mengamati bahwa penggunaan memori aplikasi R terus meningkat tanpa batas (*memory leak* semu) saat mengeksekusi mutasi kolom di dalam loop `for` yang panjang menggunakan sintaks `DT[, paste0("col_", i) := i]`. Apa akar penyebabnya?**
    * A) Garbage Collector R rusak secara permanen.
    * B) R mengevaluasi string baru dan kehabisan memori RAM fisik.
    * C) Terjadi kehabisan slot *over-allocation* kolom (`truelength`), memaksa C-layer menduplikasi dan mengalokasikan ulang struktur list pointer tabel berulang kali; solusinya adalah menggunakan `setalloccol()` sebelum loop atau memutasi banyak kolom sekaligus via satu panggilan list.
    * D) Penamaan kolom tidak boleh menggunakan karakter garis bawah (*underscore*).

---

### Kunci Jawaban & Pembahasan

1. **Jawaban: B**. Mekanisme dasar R adalah Copy-on-Modify. Jika suatu objek terdeteksi memiliki alias atau terikat di environment aktif (`REFCNT > 1`), pembaruan elemen kolom akan mengkloning vektor target ke alamat baru di RAM.
2. **Jawaban: C**. Operator `:=` adalah *in-place assignment operator* yang mendasari efisiensi `data.table`, memanipulasi vektor di RAM tanpa memicu penyalinan tabel.
3. **Jawaban: A**. `setkey()` menyusun ulang tabel secara fisik berdasarkan algoritma Radix Sort, sedangkan `setindex()` hanya membangun tabel lookup integer internal tanpa mengubah letak baris fisik tabel.
4. **Jawaban: C**. `.N` adalah variabel khusus yang menyimpan skalar panjang baris dari partisi/kelompok evaluasi data yang sedang aktif.
5. **Jawaban: A**. `setDT()` adalah fungsi *by-reference pointer coercion*. Objek list/data frame asal langsung diubah atribut kelasnya tanpa menduplikasi data di heap.
6. **Jawaban: B**. `.SD` (*Subset of Data.table*) memiliki overhead inisialisasi lingkungan yang berat jika dieksekusi pada ratusan ribu grup mikro. Solusinya adalah memanggil fungsi langsung agar GForce bekerja, atau beralih ke `fmean` dari `collapse`.
7. **Jawaban: C**. Subsetting baris `DT[...]` mengembalikan tabel baru di RAM (salinan dangkal/dalam dari subset baris), sehingga modifikasi berikutnya pada `DT_sub` tidak merusak objek awal `DT`.
8. **Jawaban: C**. Rolling join memecahkan permasalahan pencarian data "terakhir diketahui sebelum waktu T" tanpa perlu membuat filter ketidaksamaan yang menghasilkan Cartesian product.
9. **Jawaban: B**. Arsitektur internal `collapse` dirancang khusus di atas komputasi array C/C++ murni berkecepatan mikro-detik dengan pengelompokan hash terpadu dan pemanfaatan instruksi SIMD.
10. **Jawaban: C**. `data.table` memiliki kapasitas default alokasi slot penunjuk kolom (biasanya 100 slot). Menambahkan kolom melebihi slot ini satu per satu memaksa realokasi memori berulang-ulang.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Mesin Rekonsiliasi Logistik Real-Time Sensor Telemetri IOT"

#### Skenario Industri
Sebuah perusahaan logistik rantai pendingin (*cold chain logistics*) internasional melacak 50.000 armada pengiriman vaksin. Masing-masing kontainer mengirimkan data telemetri suhu setiap 5 detik. Seringkali terjadi latensi transmisi seluler, sehingga data laporan tiba secara asinkron (*out-of-order*). 

Anda ditugaskan merancang modul batching analitik di memori yang mampu melakukan validasi anomali suhu dan menggabungkan status geografis kontainer secara efisien.

#### Kebutuhan Data & Batasan Kinerja
1. **Dataset Simulasi**:
   - `DT_telemetry`: 10.000.000 baris data sensor yang mencakup: `container_id` (integer), `timestamp` (POSIXct), `temperature` (derajat Celsius, float), dan `battery_pct` (integer).
   - `DT_geofence`: 250.000 baris data checkpoint rute: `container_id`, `checkpoint_time` (POSIXct), `zone_id` (string teks), dan `is_safe_harbor` (boolean).
2. **Batasan Teknis**:
   - Total waktu komputasi seluruh pipeline: **< 8.0 detik** pada mesin standar (4-8 Core CPU).
   - Penambahan memori tambahan (*Peak Memory Overhead*) selama pemrosesan: **< 1.5 GB** (Wajib manipulasi *in-place*).

#### Spesifikasi Pengerjaan

1. **Langkah 1 (Persiapan Memori)**:
   Bangun fungsi generator dataset yang langsung mengembalikan `data.table` tanpa alokasi intermediate `data.frame`. Lakukan downcasting pada kolom numerik bila memungkinkan.
2. **Langkah 2 (Imputasi dan Deteksi Anomali In-Place)**:
   - Identifikasi kontainer yang mengalami fluktuasi anomali: suhu di atas `8.0°C` atau di bawah `2.0°C`.
   - Tambahkan kolom status boolean `temp_breach` secara *in-place*.
3. **Langkah 3 (As-Of Alignment / Rolling Join)**:
   - Gabungkan data `zone_id` dan `is_safe_harbor` dari `DT_geofence` ke dalam `DT_telemetry` berdasarkan observasi checkpoint terakhir sebelum transmisi sensor terjadi (`checkpoint_time <= timestamp`).
4. **Langkah 4 (Agregasi Tingkat Tinggi)**:
   - Hitung metrik ringkasan per `zone_id`:
     * Total insiden anomali (`sum(temp_breach)`).
     * Suhu rata-rata kontainer di zona tersebut.
     * Durasi rentang pencatatan suhu paling ekstrem.
   - Gunakan mesin agregasi GForce `data.table` atau `collapse`.
5. **Langkah 5 (Audit Pengujian Observabilitas)**:
   - Bungkus pipeline dalam `bench::mark()` dan cetak statistik memori (`mem_alloc`, `n_gc`).
   - Verifikasi bahwa alamat memori pointer utama `DT_telemetry` tidak pernah berubah sepanjang fase mutasi (*zero COW validation*).

#### Kriteria Keberhasilan (Acceptance Criteria)
* Tidak ada pemanggilan fungsi `mutate()`, `merge()`, atau ekspresi yang menduplikasi tabel induk di memori.
* Pipeline berjalan lancar tanpa error type mismatch dan menghasilkan laporan tabular ringkas per zona dalam hitungan detik.
* Laporan penggunaan memori menunjukkan alokasi garbage collection (`n_gc`) seminimal mungkin (ideal: 0 atau 1 siklus GC).