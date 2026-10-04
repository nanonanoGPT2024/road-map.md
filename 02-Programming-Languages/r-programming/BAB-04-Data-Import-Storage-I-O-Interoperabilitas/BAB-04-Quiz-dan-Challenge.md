# BAB 04: Quiz, Challenge, & Knowledge Check
**Data Import, Storage I/O, & Interoperabilitas**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme Parsing & Alokasi Memori
Jelaskan perbedaan mendasar antara mekanisme pembacaan file teks (CSV/TSV) pada fungsi bawaan Base R (`read.csv`) dengan implementasi modern pada `data.table::fread`. Tinjau dari sudut pandang:
1. Pemanfaatan *memory-mapped files* (`mmap`).
2. Strategi inferensi tipe data (*type sampling heuristics* vs *two-pass parsing*).
3. Pola alokasi memori heap (vektor atomik vs *in-place pre-allocation*).

### Soal 1.2: Serialisasi R: `.RData` vs `.rds` vs Columnar Formats
Secara arsitektural, apa perbedaan antara serialisasi menggunakan `save()` (`.RData`), `saveRDS()` (`.rds`), dan format kolumnar modern seperti Apache Parquet (`arrow::write_parquet`)? Mengapa format Parquet jauh lebih direkomendasikan untuk arsitektur *data lakehouse* dan analitik lintas bahasa (*cross-language interoperability*) dibandingkan format biner native R?

### Soal 1.3: Abstraksi Database DBI dan Evaluasi Malas (*Lazy Evaluation*)
Ketika mengeksekusi pipeline berikut menggunakan `DBI` dan `dbplyr`:
```r
tbl_remote <- tbl(con, "large_transactions") |>
  filter(year == 2023) |>
  select(customer_id, amount)
```
Jelaskan daur hidup (*lifecycle*) eksekusi data tersebut di memori R. Kapan koneksi jaringan dimanfaatkan, bagaimana *query translation* bekerja di balik layar, dan apa perbedaan konsumsi sumber daya komputasi lokal antara operasi di atas dengan memanggil `collect()`?

### Soal 1.4: Multiplier Rasio Memori pada Format Tekstual
Sebuah file CSV berukuran 5 GB di disk sering kali membutuhkan alokasi RAM sebesar 15 GB hingga 25 GB ketika diimpor seluruhnya menggunakan fungsi parser standar ke dalam session R. Jelaskan faktor struktural internal R yang menyebabkan fenomena inflasi ukuran memori ini (hubungkan dengan representasi pointer `SEXP`, *string interning / global character cache*, dan fragmentasi heap).

### Soal 1.5: Landasan Zero-Copy Architecture pada `reticulate`
Bagaimana paket `reticulate` memfasilitasi interoperabilitas objek antara runtime R dan Python? Jelaskan konsep *zero-copy memory sharing* saat mentransfer struktur data numerik (seperti `NumPy ndarray` ke matriks R) versus objek yang memerlukan serialisasi/konversi penuh (seperti *nested Python dictionary* ke `R list`).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Debugging Inferensi Tipe Parsial pada `fread`
Anda mengimpor file log 20 GB menggunakan `data.table::fread("server_logs.csv")`. Pada baris ke-15.000.000, terdapat anomali di mana kolom `transaction_id`—yang diinferensikan sebagai `integer64` pada 10.000 baris pertama—mengandung nilai alfanumerik (misalnya `"TX_999482A"`). 
1. Apa perilaku standar `fread` ketika menghadapi pelanggaran tipe ini di tengah-tengah pembacaan?
2. Bagaimana strategi teknis paling deterministik untuk mengatasi hal ini tanpa membaca seluruh file berulang kali (*re-read penalty*)?

### Soal 2.2: Race Condition & Socket Exhaustion pada Forking I/O Paralel
Perhatikan snippet pemrosesan data paralel berikut:
```r
library(parallel)
library(DBI)
con <- dbConnect(RPostgres::Postgres(), dbname = "prod_db")

results <- mclapply(1:100, function(i) {
  dbGetQuery(con, sprintf("SELECT * FROM events WHERE partition_id = %d", i))
}, mc.cores = 8)
```
Kode di atas mengalami *crash*, hang, atau menghasilkan *corrupted sockets*. Identifikasi akar permasalahan OS-level terkait pemanggilan `fork()` terhadap *file descriptors* aktif, dan rekonstruksi arsitektur koneksi tersebut menggunakan paradigma *connection pooling* (`pool::dbPool`) atau worker-level initialization.

### Soal 2.3: Memory-Mapped I/O vs Virtual Memory Thrashing pada `arrow`
Ketika Anda membuka dataset Parquet sebesar 100 GB pada mesin dengan RAM 16 GB menggunakan `arrow::open_dataset()`, R tidak mengalami Out-Of-Memory (OOM). Namun, saat Anda menjalankan agregasi yang salah:
```r
ds |> 
  mutate(x = expensive_r_function(payload)) |> 
  collect()
```
Sistem langsung mengalami pembekuan (*freeze*) dan proses di-kill oleh OS (*OOM Killer*). Jelaskan perbedaan mendasar antara representasi tabel Arrow di *virtual address space* via `mmap` dengan materialisasi data ke dalam *R garbage-collected heap space*.

### Soal 2.4: Kerusakan Encoding Lintas Platform (UTF-8 vs Latin-1/CP1252)
Sebuah pipeline I/O membaca file teks multibyte yang diekspor dari database sistem legacy Windows menggunakan `readLines()`, kemudian menulisnya kembali ke AWS S3 via *streaming buffer*. Saat diakses di container Linux, karakter non-ASCII (seperti huruf beraksen atau karakter Asia) mengalami *mojibake*. 
1. Bagaimana R mengelola metadata encoding pada vektor string (`CHARSXP`) melalui flag `getCharCE()`?
2. Tuliskan mekanisme perbaikan I/O stream menggunakan *raw connection* atau argumen `encoding` pada `readr::read_lines()` agar byte sequence tetap valid.

### Soal 2.5: Isolasi Memory Leak Lintas Runtime pada `reticulate`
Sebuah model machine learning inferensi tinggi memanggil library Python via `reticulate` dalam loop R:
```r
predict_batch <- function(df_batch) {
  py_batch <- r_to_py(df_batch)
  preds <- py_model$predict(py_batch)
  return(py_to_r(preds))
}
```
Meskipun garbage collector R (`gc()`) dipanggil secara berkala, penggunaan RSS (*Resident Set Size*) proses R terus meningkat hingga crash. 
1. Di mana letak potensi *memory leak* antara R Garbage Collector dan Python Cyclic GC / Reference Counting?
2. Bagaimana teknik pelepasan referensi PyObject pointer secara eksplisit di R?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck I/O dan Out-Of-Memory (OOM) pada Batch Ingestion Skala Besar
Anda adalah Lead Data Engineer yang mengelola ingest harian. Perusahaan Anda menerima arsip tar.gz berisi 500 file CSV harian (total ukuran tidak terkompresi: ~85 GB). Infrastruktur pemrosesan adalah single node AWS EC2 instance berukuran `m5.xlarge` (4 vCPU, 16 GB RAM). Upaya awal menggunakan script R berbasis `lapply` dan `readr::read_csv` selalu terhenti dengan status exit code 137 (OOM Killer).
* **Pertanyaan Diagnostik & Solusi:**
  1. Rancang arsitektur pipeline I/O end-to-end yang memungkinkan pemrosesan 85 GB data tersebut menggunakan limitasi 16 GB RAM tanpa crash.
  2. Bandingkan dua pendekatan arsitektur: (a) *Chunked Streaming Ingestion via DuckDB* dan (b) *Partitioned Parquet Conversion via Apache Arrow*. Tentukan trade-off latency vs disk write overhead dari kedua strategi tersebut.

### Skenario B: Race Condition dan State Inconsistency pada Concurrent File-Based Writes
Pada sistem komputasi paralel berkinerja tinggi (Slurm HPC cluster), 32 node worker R menulis hasil analitik intermediate secara simultan ke dalam shared network directory (NFS/EFS) menggunakan format Apache Parquet yang dipartisi berdasarkan waktu: `output_dir/year=2023/month=10/part-*.parquet`. Secara berkala, ditemukan bahwa beberapa file Parquet mengalami *zero-byte truncation* atau korupsi metadata *footer*, menyebabkan proses downstream agregasi gagal total.
* **Pertanyaan Diagnostik & Solusi:**
  1. Analisis mengapa penulisan konkuren langsung ke shared storage berbasis NFS rentan terhadap kondisi *file lock contention* dan *metadata cache inconsistency*.
  2. Implementasikan pola arsitektur penulisan file yang menjamin sifat *ACID-like properties* (misalnya: *atomic write pattern* melalui penulisan temporary file acak pada lokal disk `/tmp` diikuti operasi `file.rename()` atomik / two-phase commit file movement).

### Skenario C: High-Latency Bottleneck pada Interoperabilitas R-Python-Database
Sebuah arsitektur platform kuantitatif menggunakan R untuk terhubung ke database time-series (ClickHouse), menarik 20 juta baris data tick pasar modal, kemudian meneruskannya ke script Python untuk pelatihan model Deep Learning berbasis PyTorch, dan mengembalikan matriks estimasi risiko kembali ke R untuk visualisasi Shiny. 
Saat ini, pertukaran data dilakukan dengan:
1. R menarik data dari DB via ODBC -> disimpan sebagai `data.frame`.
2. R menulis data tersebut ke file temporary CSV (`fwrite`).
3. Python membaca CSV via `pandas.read_csv`.
4. Python inferensi -> simpan output ke CSV.
5. R membaca kembali CSV ke memori.
Pipeline ini membutuhkan waktu 380 detik (6,3 menit), dengan 70% waktu terbuang pada disk serialization/deserialization.
* **Pertanyaan Diagnostik & Solusi:**
  1. Rekonstruksi arsitektur interoperabilitas data ini menjadi pipeline zero-copy in-memory memanfaatkan *Apache Arrow C Data Interface* / *Arrow IPC Stream* dan `reticulate`.
  2. Identifikasi bagaimana alokasi shared memory antar proses dapat memangkas latensi transfer data hingga mendekati 0 detik.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Out-Of-Core Ingestion & Cross-Language Bridge Pipeline

#### Deskripsi Permasalahan
Tim Data Analytics membutuhkan ETL engine lokal berkinerja tinggi di R untuk memproses dataset transaksi retail berukuran masif yang tidak muat di dalam memori utama, mengekstrak metrik agregasi, dan mengekspos pointer memori secara langsung ke model PyTorch di Python tanpa serialisasi disk.

#### Requirements
1. **Mock Data Generator:**
   * Buat skrip R yang secara efisien menghasilkan file data dummy terfragmentasi: minimal 10 file CSV terpisah, masing-masing berukuran ~200 MB (total ~2 GB data sintetis), berisikan kolom: `timestamp` (POSIXct), `store_id` (integer), `sku_id` (character/UUID), `quantity` (integer), `unit_price` (numeric), dan `discount` (numeric).
2. **Out-of-Core Processing & Transcoding:**
   * Jangan gunakan `read.csv` atau `read.table`.
   * Gunakan `arrow` atau `duckdb` untuk membaca 10 file CSV tersebut secara *streaming/lazy*.
   * Lakukan filtering data: hanya ambil transaksi dengan `quantity > 0` dan `unit_price > 5.0`.
   * Lakukan komputasi kolom terderivasi: `net_revenue = quantity * unit_price * (1 - discount)`.
   * Tuliskan (*transcode*) dataset yang telah dibersihkan ke dalam direktori Parquet yang terpartisi secara fisik berdasarkan `store_id` (`partitioning = "store_id"`), menggunakan algoritma kompresi `zstd`.
3. **In-Memory Analytical Querying:**
   * Eksekusi query analitik agregasi menggunakan `duckdb` langsung di atas folder partitioned Parquet tersebut (tanpa memuat file ke dalam R data.frame memory): hitung total `net_revenue` dan rata-rata `discount` per `store_id` per bulan.
4. **Zero-Copy Cross-Language Bridge:**
   * Ambil subset data fitur dari file Parquet tersebut dalam format Arrow RecordBatchReader.
   * Gunakan `reticulate` dan Arrow Python bindings (`pyarrow`) untuk menyerahkan pointer tabel Arrow tersebut ke runtime Python tanpa melakukan penulisan ke disk (Zero-Copy Transfer).
   * Pada runtime Python, konversi Arrow Table tersebut langsung menjadi `torch.Tensor` (atau `numpy.ndarray`) dan hitung matriks kovariansi dari fitur numerik. Kembalikan matriks hasil estimasi ke environment R.

#### Constraints
* Total alokasi RAM R session tidak boleh melebihi 1,5 GB selama proses ETL dan konversi berlangsung (Pantau via `pryr::mem_used()` atau fungsi diagnostik OS).
* Kode harus murni berbasis modular enterprise script, memiliki error handling (`tryCatch`), dan logging terstruktur.

#### Expected Output
* Direktori berisikan dataset Parquet terpartisi yang valid.
* Objek R session yang menyimpan matriks kovariansi akhir yang dihitung oleh Python, diverifikasi identik dengan perhitungan matriks R native `cov()`.
* Log metrik eksekusi yang menampilkan waktu eksekusi (benchmarking via `bench::mark` atau `tictoc`) dan puncak konsumsi memori (*peak memory usage*).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal representasi data di R (bagaimana `SEXP`, `VECSXP`, dan `STRSXP` dialokasikan di dalam R heap).
- [ ] Perbedaan fundamental paradigma eksekusi I/O: *In-memory bulk loading* vs *Streaming/Chunked loading* vs *Memory-mapped I/O (`mmap`)*.
- [ ] Perbedaan kapabilitas, efisiensi kompresi, dan skalabilitas antara format file: CSV, RDS, RData, Feather, dan Apache Parquet.
- [ ] Cara kerja abstraksi database tingkat enterprise di R (`DBI`, `dbplyr`, `pool`) serta optimalisasi *pushdown predicates* ke backend database.
- [ ] Arsitektur transfer data lintas runtime (`reticulate`, C ABI, Python PyCapsule, Apache Arrow C Data Interface) dan kapan sebuah operasi bersifat *zero-copy* versus *deep memory copy*.
- [ ] Penyebab umum dan mitigasi *I/O race condition* serta kegagalan integritas data pada komputasi terdistribusi/paralel multi-thread dan multi-process.

### Saya tidak perlu menghafal:
- [ ] Seluruh variasi argumen konfigurasi parser pada fungsi `data.table::fread()` atau `readr::read_delim()` (cukup memahami cara mengontrol tipe data dan encoding).
- [ ] Struktur internal byte header dari binary format Apache Parquet atau Thrift metadata schema secara mendalam.
- [ ] Sintaks spesifik query SQL vendor-spesifik saat menggunakan `dbplyr` (karena diterjemahkan secara otomatis oleh database dialect translation layer).

### Saya harus bisa melakukan:
- [ ] Melakukan profiling dan mitigasi konsumsi memori saat proses data ingestion berukuran multi-gigabyte menggunakan alat seperti `profmem`, `pryr`, atau monitor sistem Linux.
- [ ] Menulis pipeline pemrosesan data berbasis out-of-core streaming menggunakan kombinasi `arrow` dan `duckdb` di R.
- [ ] Mengonfigurasi arsitektur koneksi database yang aman untuk lingkungan paralel atau multi-threaded menggunakan `pool` dan `DBI`.
- [ ] Mentransfer struktur data bervolume besar secara instan antara session R dan engine Python via pointer memory (`reticulate` + `pyarrow`) tanpa overhead penulisan disk.
- [ ] Menangani anomali parsing data mentah (karakter rusak, multi-encoding, embedded delimiters, baris malformasi) dengan deterministik tanpa menyebabkan pipeline crash di level produksi.