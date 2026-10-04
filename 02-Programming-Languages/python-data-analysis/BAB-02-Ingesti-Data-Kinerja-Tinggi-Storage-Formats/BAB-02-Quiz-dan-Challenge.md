# BAB 02: Quiz, Challenge, & Knowledge Check
**Ingesti Data Kinerja Tinggi & Storage Formats**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Row-Oriented vs Columnar Storage Engine Internals**  
   Jelaskan secara mendalam mengapa format kolumnar (seperti Apache Parquet atau ORC) secara signifikan mengungguli format baris (seperti CSV atau JSON) dalam query analitis OLAP (*Online Analytical Processing*), khususnya terkait utilisasi CPU cache hierarchy (L1/L2/L3), *instruction pipelining*, dan *I/O bus bandwidth* saat eksekusi operasi agregasi kolom spesifik.

2. **The "Serialization & Deserialization Tax" pada Teks vs Biner**  
   Ketika mengeksekusi `pd.read_csv()` atau fungsi *parser* teks sejenis pada berkas berukuran 10 GB, jelaskan komponen komputasi apa saja yang membebani CPU secara ekstrem (*string parsing, type inference, pointer chasing, memory allocations*) dibandingkan jika data tersebut dibaca langsung dari representasi biner *in-memory* berbasis columnar seperti Apache Arrow IPC.

3. **Anatomi Metadata dan Mekanisme *Predicate Pushdown***  
   Bagaimana struktur internal metadata Parquet (Header, Data Pages, Dictionary Pages, Row Groups, dan File Footer) memungkinkan mesin eksekusi query melakukan *Predicate Pushdown* (*min/max pruning* dan *dictionary filtering*) tanpa harus membaca dan men-dekompresi seluruh blok data dari media penyimpanan?

4. **Karakteristik & Trade-Off Algoritma Kompresi (Snappy vs Zstandard vs Gzip)**  
   Bandingkan algoritma kompresi Snappy, Zstandard (zstd), dan Gzip dalam konteks *data warehousing* dan *high-throughput ingestion*. Pada titik mana rasio kompresi yang lebih tinggi menjadi kontraproduktif terhadap throughput sistem akibat *decompression CPU latency*?

5. **Memory-Mapped I/O (`mmap`) dan Paradigma *Zero-Copy Reading***  
   Jelaskan bagaimana konsep `mmap` (Memory-Mapped Files) bekerja pada level sistem operasi (interaksi antara *Virtual Memory Manager*, *Page Faults*, dan *Kernel Page Cache*). Bagaimana format Apache Arrow mengeksploitasi mekanisme ini untuk mencapai *zero-copy reads* dalam pemrosesan data lintas proses?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Parquet "Small Files Problem" dan Patologi Row Group Sizing**  
   Sebuah *pipeline* streaming menulis data langsung ke Parquet setiap 10 detik, menghasilkan jutaan berkas berukuran ~2 MB dengan *Row Group* yang sangat kecil. Jelaskan degradasi performa yang terjadi pada query engine dari perspektif *metadata lookup overhead*, inefisiensi *dictionary encoding*, pembengkakan *HTTP GET requests* ke object storage (S3/GCS), dan tingginya penggunaan memori pada query coordinator.

2. **Arrow Memory Layout, Pointer Swizzling, dan Eliminasi GIL**  
   Bagaimana arsitektur *memory layout* Apache Arrow (terdiri dari *Validity/Null Bitmap*, *Value Buffer*, dan *Offset Buffer*) memungkinkan operasi komputasi vektor berbasis SIMD (*Single Instruction, Multiple Data*) dieksekusi oleh C++/Rust kernel di belakang Python tanpa terhambat oleh CPython *Global Interpreter Lock* (GIL) dan *Python Object overhead*?

3. **Debugging Memory Bloat pada Chunked Parsing Pandas vs Polars Streaming**  
   Saat memproses berkas CSV 50 GB menggunakan `pd.read_csv(..., chunksize=100_000)`, konsumsi memori *Resident Set Size* (RSS) proses Python tetap merangkak naik hingga menyentuh batas RAM dan memicu OS OOM Killer. Mengapa chunking konvensional di Pandas rentan terhadap fragmentasi memori CPython dan akumulasi *garbage collection*, dan bagaimana arsitektur *chunked streaming engine* Polars/Arrow mengatasi masalah alokasi memori ini via *memory arena pooling*?

4. **Schema Evolution Conflicts dan Semantic Inconsistencies**  
   Anda membaca *dataset* Parquet yang dipartisi dan ditulis selama 2 tahun terakhir. Query gagal atau mengembalikan data terkorupsi dengan error konversi tipe data. Jelaskan perbedaan mendasar antara *physical type* dan *logical type* dalam spesifikasi Parquet, serta analisis dampak buruk jika terjadi evolusi skema berupa perubahan tipe data primitif (misalnya `INT32` ke `INT64`, atau penambahan *nested struct field*) tanpa *schema migration policy* yang ketat.

5. **Dictionary Encoding Thrashing & Fallback Penalty**  
   Parquet secara default mencoba mengompresi data string menggunakan *Dictionary Encoding*. Jelaskan mekanisme internal yang terjadi ketika sebuah kolom string memiliki *cardinality* yang sangat tinggi (*high-cardinality columns*, e.g., UUIDs atau log message timestamps). Mengapa *fallback* dari *dictionary encoding* ke *plain encoding* saat proses penulisan dapat memicu lonjakan komputasi CPU dan fragmentasi blok data?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Production Ingestion Pipeline OOM (Out-of-Memory) Crash
* **Konteks:** Sistem *batch ingestion* harian mengeksekusi *job* Python di dalam Kubernetes Pod dengan spesifikasi 4 vCPU dan 16 GB RAM Limits. Job ini mengonsumsi satu berkas raw dump data transaksi harian berformat CSV sebesar 35 GB dari vendor.
* **Insiden:** Script Python mengeksekusi `df = pd.read_csv("transactions.csv")`, lalu melakukan sorting dan transformasi sebelum diekspor ke Parquet. Pod langsung terbunuh dengan status `OOMKilled` (Exit Code 137) sebelum baris pertama transformasi berhasil dieksekusi. Percobaan beralih ke `chunksize=500_000` berhasil membaca berkas, namun Pod kembali `OOMKilled` saat mencoba menggabungkan (*concatenating*) chunks untuk melakukan operasi `df.sort_values("timestamp")`.
* **Pertanyaan Diagnostik:**
  1. Hitung perkiraan ekspansi memori (*memory footprint multiplier*) representasi *in-memory* Pandas DataFrame (tipe data teks/`object`) terhadap ukuran mentah CSV di disk. Mengapa rasio ini bisa mencapai 3x hingga 5x lipat?
  2. Rancang arsitektur pipeline alternatif menggunakan PyArrow atau Polars yang memanfaatkan *disk-spilling sorting* atau *chunked streaming to Parquet*, sehingga keseluruhan proses dapat berjalan stabil di bawah limit memori 8 GB tanpa mengorbankan performa kecepatan.

### Skenario B: Silent Data Inconsistency & Atomicity Race Condition
* **Konteks:** Tim Data Platform mengoperasikan pipeline *hourly micro-batch* yang memproses data event klik pengguna dan menuliskannya ke Amazon S3 dalam format Parquet dengan partisi berbasis tanggal dan jam: `s3://data-lake/clickstream/year=2024/month=10/day=15/hour=14/*.parquet`.
* **Insiden:** Lima worker instance menulis ke prefix partisi yang sama secara paralel. Pada kondisi *network retry* (akibat *transient S3 503 Slow Down error*), worker mencoba menulis ulang *file part* yang gagal. Akibatnya, query analitis harian yang dijalankan via DuckDB/Trino menghasilkan total metrics yang *flaky* (berfluktuasi antara 10% lebih tinggi karena duplikasi data sebagian baris, atau baris hilang karena pembacaan *partial/half-written file*).
* **Pertanyaan Diagnostik:**
  1. Mengapa penulisan langsung berkas Parquet murni secara *multi-writer* ke Object Storage tanpa *transaction layer* bersifat rentan terhadap *non-atomic visibility* dan *race condition*?
  2. Bagaimana Anda mendesain ulang mekanisme *safe-writing* pada level file system / object store (misalnya: penulisan berbasis *atomic swap / commit*, isolasi idempotensi via UUID naming, atau migrasi ke table format seperti Apache Iceberg/Delta Lake) untuk menjamin garansi *ACID append* dan *zero duplicate data*?

### Skenario C: Sub-optimal OLAP Latency: Compaction vs Partitioning Trade-off
* **Konteks:** Sebuah data lake telemetri IoT menerima data dari 500.000 sensor kendaraan. Arsitek sebelumnya menerapkan partisi Parquet yang sangat agresif: `/device_id=XYZ/year=YYYY/month=MM/day=DD/hour=HH/data.parquet`. Total terdapat 20 juta berkas Parquet dengan ukuran rata-rata 50 KB hingga 200 KB per file.
* **Insiden:** Query analitis agregasi bulanan untuk 100 armada kendaraan tertentu membutuhkan waktu 45 menit untuk selesai, padahal volume data aktual yang relevan hanya 2 GB. Profiling menunjukkan 92% waktu query dihabiskan pada fase `ListObjects`, `Opening S3 HTTP connection`, dan `Reading Parquet Footer`, bukan pada eksekusi komputasi data.
* **Pertanyaan Diagnostik:**
  1. Identifikasi penyakit arsitektural yang terjadi pada data lake tersebut dan jelaskan dampak *high HTTP metadata latency* pada query planning.
  2. Formulasikan strategi *Compaction Service* (penggabungan file) dan rekomendasikan skema partisi/sorting alternatif (*e.g., Z-Order clustering*, *bucketed partitioning*, atau *composite primary key sorting* di dalam Parquet berukuran 128 MB–512 MB) untuk mereduksi waktu query dari 45 menit menjadi < 10 detik.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Streaming Ingestion & Parquet Compaction Engine

#### Problem Statement
Anda bertindak sebagai Lead Data Platform Engineer yang ditugaskan membangun engine ingesti data mandiri berbasis Python tanpa dependensi Spark. Sistem Anda harus membaca *stream* log akses server web semi-terstruktur berukuran masif (simulasi 20 GB CSV terkompresi Gzip atau ratusan berkas NDJSON), memvalidasi skema secara ketat, mengoptimalkan tipe data, dan menulisnya ke dalam partisi Parquet berperforma tinggi yang siap dikonsumsi oleh data warehouse/query engine (DuckDB/Trino).

#### Requirements
1. **Low-Memory Streaming Ingestion:**
   * Script tidak boleh memuat seluruh dataset sekaligus ke dalam memori.
   * Gunakan `pyarrow.dataset`, `pyarrow.csv`, atau `polars.scan_csv/scan_ndjson` untuk memproses data secara *chunked streaming*.
2. **Strict Schema & Type Enforcement:**
   * Tentukan skema eksplisit (*explicit schema*). Tolak parsing otomatis (*no heuristic type inference*).
   * Kolom tanggal/waktu harus di-cast ke tipe biner presisi tinggi (`timestamp[us]`).
   * Kolom string dengan kardinalitas rendah (< 500 nilai unik, e.g., `http_status_code`, `request_method`, `device_category`) wajib di-cast menjadi `Dictionary/Categorical Array` untuk efisiensi ruang dan pembacaan.
   * Kolom numerik harus memakai tipe data integer/float sekecil mungkin yang aman (`int16`, `int32`, bukan fallback ke `int64` default).
3. **Optimized Parquet Generation:**
   * Tulis output dalam partisi direktori berdasarkan format tanggal: `partition_date=YYYY-MM-DD`.
   * Konfigurasikan penulisan Parquet:
     * `Row Group Size`: Tepat 128 MB per *row group* (atau ~1.000.000 baris per row group).
     * `Compression Codec`: `ZSTD` dengan compression level 3, atau `Snappy`.
     * `Statistics Collection`: Wajib mengaktifkan penulisan *page-level* and *row-group-level statistics* (min, max, null_count) untuk memastikan kompatibilitas *predicate pushdown*.
4. **Benchmarking & Validation Suite:**
   * Buat skrip audit yang membaca dataset hasil konversi menggunakan `DuckDB` atau `PyArrow`.
   * Buktikan efektivitas *predicate pushdown* dengan mengeksekusi query filter spesifik dan mencatat rasio data yang di-skip (*pruned row groups*) via pembacaan Parquet Metadata.

#### Constraints
* **Memory Limit:** Alokasi memori proses Python dibatasi maksimal **1.5 GB RSS** selama seluruh proses ingesti berlangsung (verifikasi via `tracemalloc`, `memory_profiler`, atau `memray`).
* **Framework:** Wajib menggunakan Python 3.10+ dengan `PyArrow` (>= 14.0) dan/atau `Polars` (>= 0.20). Dilarang keras menggunakan `pandas.read_csv()` standar tanpa chunking, dan dilarang menggunakan Apache Spark.

#### Expected Output
1. Script Python modular: `ingestion_engine.py` yang memuat logika streaming, transformasi skema, dan partisi Parquet.
2. File output log/laporan benchmark eksekusi yang menunjukkan:
   * Puncak alokasi memori (*Peak Memory Usage*).
   * Throughput ingesti (MB/s dan baris/detik).
   * Inspeksi metadata Parquet yang dihasilkan: jumlah *Row Groups*, ukuran rata-rata per Row Group, dictionary encoding flags, dan statistik min/max tiap kolom.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental arsitektur fisik penyusunan data antara *Row-Oriented* (CSV/JSON/Avro) dan *Columnar-Oriented* (Parquet/ORC).
- [ ] Arsitektur internal format Apache Parquet: peranan *File Header*, *Data Pages*, *Dictionary Pages*, *Row Groups*, dan *File Footer Metadata*.
- [ ] Cara kerja mekanis *Predicate Pushdown* (*Min/Max Pruning*) dan *Column Projection* dalam mereduksi I/O disk dan jaringan.
- [ ] Spesifikasi *in-memory* Apache Arrow (IPC format, layout buffer, bitmasks) dan bagaimana format ini menghilangkan *serialization overhead*.
- [ ] Perbedaan kinerja dan karakteristik *trade-off* kompresi data: Snappy (kecepatan dekompresi maksimal) vs Zstandard (keseimbangan rasio kompresi dan kecepatan) vs Gzip (arsip dingin).
- [ ] Bahaya arsitektural *Small Files Problem* pada Object Storage dan bagaimana siklus hidup *Compaction* menyelesaikan inefisiensi tersebut.
- [ ] Konsep sistem operasi terkait *Page Cache*, *Memory-Mapped I/O* (`mmap`), dan *Zero-Copy architecture*.

### Saya tidak perlu menghafal:
- [ ] Nilai bit-offset biner spesifik dari header/magic bytes Parquet (`PAR1`).
- [ ] Rumus matematika internal algoritma kompresi Snappy atau Zstandard.
- [ ] Seluruh parameter opsional dan variasi konfigurasi pada low-level API C++ Apache Arrow.
- [ ] Sintaksis eksak dari setiap *flag* pembacaan CSV usang di pustaka Pandas lawas.

### Saya harus bisa melakukan:
- [ ] Menganalisis *memory profile* proses parsing data menggunakan `memray` atau `tracemalloc` untuk mengisolasi *memory leaks* atau *memory bloat*.
- [ ] Menulis pipeline ingesti data berukuran puluhan gigabyte secara *streaming/chunked* menggunakan PyArrow atau Polars dengan konsumsi memori konstan di bawah 2 GB.
- [ ] Memeriksa dan membedah metadata berkas Parquet (*Row Group schema, Column Chunk metadata, Encoded Statistics*) secara terprogram via `pyarrow.parquet.ParquetFile`.
- [ ] Menerapkan *type coercion* yang tepat (mengubah tipe `object` CPython ke tipe data biner primitif berukuran presisi atau *Dictionary Array*) untuk meminimalkan *memory footprint*.
- [ ] Mendesain skema partisi dan layout penyimpanan Parquet yang seimbang (menghindari partisi terlalu dalam yang memicu jutaan berkas kecil).
- [ ] Menguji validitas *predicate pushdown* pada query engine modern (DuckDB/PyArrow Dataset API) menggunakan metrik waktu eksekusi dan volume data yang dibaca.