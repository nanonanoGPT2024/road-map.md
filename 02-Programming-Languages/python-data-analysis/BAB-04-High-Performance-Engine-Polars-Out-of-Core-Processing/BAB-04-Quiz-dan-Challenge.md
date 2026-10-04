# BAB 04: Quiz, Challenge, & Knowledge Check
**High-Performance Engine: Polars & Out-of-Core Processing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Arsitektur Memori Apache Arrow vs. NumPy/Pandas Block Manager**  
   Jelaskan secara struktural bagaimana model *in-memory columnar* Apache Arrow yang diimplementasikan pada Polars memitigasi masalah fragmentasi memori, *cache misses*, dan *overhead* tipe data dibandingkan dengan arsitektur `BlockManager` pada Pandas berbasis NumPy (khususnya penanganan *missing values* via *validity bitmap* versus *sentinel values* seperti `NaN`).

2. **Siklus Hidup Eksekusi: Eager vs. Lazy Execution**  
   Uraikan tahap demi tahap apa yang terjadi di balik layar ketika sebuah ekspresi Polars didefinisikan menggunakan `LazyFrame` hingga fungsi `.collect()` dieksekusi. Apa peran representasi *Abstract Syntax Tree* (AST) dan *Logical Plan* sebelum diterjemahkan menjadi *Physical Plan* oleh *query engine*?

3. **Mekanisme Predicate Pushdown dan Projection Pushdown**  
   Bagaimana mesin optimasi Polars memanfaatkan metadata pada format file Parquet (seperti *file metadata*, *row group metadata*, dan *dictionary page*) saat menerapkan optimasi *Predicate Pushdown* dan *Projection Pushdown*? Mengapa hal ini secara drastis mengurangi I/O disk dan konsumsi memori *bandwidth*?

4. **Vectorization dan Pemanfaatan SIMD pada Level CPU**  
   Jelaskan bagaimana Polars memanfaatkan instruksi SIMD (*Single Instruction, Multiple Data*) pada arsitektur CPU modern (AVX-512, AVX2, atau ARM NEON) melalui implementasi Rust. Mengapa komputasi berbasis ekspresi Polars (misal: perkalian dua kolom) jauh lebih cepat daripada iterasi baris Python konvensional bahkan jika keduanya dijalankan secara paralel?

5. **Prinsip Dasar Out-of-Core Processing dan Chunked Streaming**  
   Definisikan paradigma *out-of-core processing* dalam konteks Polars. Bagaimana cara kerja parameter `streaming=True` pada operasi `.collect()`, dan bagaimana mesin eksekusi mengelola *buffer pool* serta *batch chunking* agar dataset yang ukurannya jauh melampaui kapasitas RAM fisik tetap dapat diproses tanpa mengalami terminasi akibat *Out-Of-Memory* (OOM)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Stateful vs. Stateless Operations pada Streaming Engine**  
   Dalam pemrosesan *out-of-core* dengan `collect(streaming=True)`, beberapa operasi dapat diproses secara *stateless* (streaming murni per-*chunk*), sedangkan operasi lain bersifat *stateful* (membutuhkan akumulasi parsial atau global). Jelaskan mengapa operasi seperti `sort()`, `unique()`, dan `join()` tertentu dapat memicu *memory spike* atau bahkan *fallback* ke eksekusi non-streaming jika kardinalitas kunci sangat tinggi. Bagaimana strategi mitigasi internal Polars terhadap batasan ini?

2. **Dampak Pemanggilan Python UDFs dan GIL Re-entry**  
   Analisis konsekuensi performa saat seorang *data engineer* menggunakan `.map_elements()` dibandingkan dengan kombinasi ekspresi native Polars atau `.map_batches()`. Jelaskan mekanisme interupsi pada *Rayon thread pool* milik Polars ketika eksekusi terpaksa merebut kembali *Global Interpreter Lock* (GIL) Python, dan bagaimana hal tersebut menghancurkan efisiensi paralelisasi multi-core.

3. **Schema Evolution dan Inference Mismatch pada Lazy Multi-File Scans**  
   Ketika Anda mengeksekusi `pl.scan_parquet("data/*.parquet")` pada ribuan partisi yang memiliki sedikit evolusi skema (misal: kolom integer berubah menjadi float di partisi kuartal baru), Polars dapat melempar `ComputeError` atau menghasilkan data korup. Bagaimana cara kerja *schema inference* pada tahap *plan building*, dan bagaimana Anda secara eksplisit mengonfigurasi skema serta menangani divergensi tipe data tanpa membaca seluruh isi file terlebih dahulu?

4. **Zero-Copy Interoperability vs. Data Cloning via PyArrow**  
   Jelaskan kondisi di mana konversi data dari Polars ke format lain (atau sebaliknya) benar-benar bersifat *zero-copy* menggunakan antarmuka *Arrow C Data Interface*, dan kapan konversi tersebut terpaksa melakukan alokasi ulang dan penyalinan memori (*deep copy*). Apa dampak dari *string/binary view memory layout* terhadap interoperabilitas ini?

5. **Contention pada Threadpool Rayon dan Dynamic Work-Stealing**  
   Polars mengandalkan pustaka Rust `rayon` untuk paralelisasi *data-parallel*. Dalam skenario lingkungan *containerized* (seperti Docker di Kubernetes dengan limit CPU kuota, misal `resources.limits.cpu = 2`), mengapa alokasi *thread* default Polars yang mendeteksi *host physical cores* dapat menyebabkan *CPU throttling* ekstrem dan degradasi latensi? Bagaimana variabel lingkungan `POLARS_MAX_THREADS` berinteraksi dengan penjadwal *work-stealing*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOMKilled pada Pipeline Agregasi Skala 250 GB
Sebuah pipeline analitik harian memproses dataset transaksi sebesar 250 GB (format Parquet terkompresi Snappy) pada sebuah worker node Kubernetes dengan spesifikasi RAM 32 GB dan 8 vCPU. Pipeline dibangun menggunakan kode berikut:

```python
import polars as pl

q = (
    pl.scan_parquet("s3://lakehouse/transactions/*/*.parquet")
    .filter(pl.col("status") == "COMPLETED")
    .group_by(["merchant_id", "user_id"])
    .agg(
        [
            pl.col("amount").sum().alias("total_spend"),
            pl.col("amount").mean().alias("avg_spend"),
            pl.col("transaction_id").n_unique().alias("unique_tx_count"),
        ]
    )
    .sort("total_spend", descending=True)
)

df = q.collect(streaming=True)
```

**Permasalahan:**  
Pod secara konsisten mati dengan status `OOMKilled` (Exit Code 137) tepat di tengah proses agregasi. Monitor sistem menunjukkan penggunaan memori melonjak drastis hingga menyentuh batas cgroup (32 GB) sesaat setelah pembacaan selesai.

**Pertanyaan Diagnostik:**
1. Bedah titik kegagalan (*bottleneck*) spesifik pada ekspresi *query plan* di atas yang menjadi penyebab utama konsumsi memori tak terbatas, meskipun parameter `streaming=True` telah diaktifkan.
2. Jelaskan mengapa metrik kardinalitas pada kombinasi `["merchant_id", "user_id"]` dan penggunaan `pl.col("transaction_id").n_unique()` melumpuhkan efisiensi agregator streaming.
3. Rancang arsitektur kueri alternatif yang teroptimasi secara penuh agar kueri tersebut dapat selesai dalam batas RAM 32 GB tanpa mengorbankan integritas data analitik.

---

### Skenario B: Categorical Type Inconsistency dan Silent Corruption pada Multi-Worker Processing
Sebuah sistem *microservice* ingestion memproses *chunk* data transaksi secara paralel menggunakan beberapa proses pekerja independen (misal via Celery atau `multiprocessing`). Masing-masing pekerja membaca partisi data, mengonversi kolom string kategori berulang (`country_code`, `device_type`) menjadi `pl.Categorical`, melakukan agregasi parsial, lalu menyimpannya ke IPC Feather file untuk digabungkan oleh *master process*.

**Permasalahan:**  
Saat *master process* membaca dan menggabungkan semua file hasil menggunakan `pl.concat()`, nilai-nilai pada kolom kategori tertukar secara acak (misal: baris yang seharusnya bertuliskan "ID" berubah menjadi "US", atau "Desktop" tertukar menjadi "Mobile"). Tidak ada pesan *error* atau *exception* yang dilempar oleh Polars.

**Pertanyaan Diagnostik:**
1. Jelaskan mekanisme *global string cache* versus *local string dictionary encoding* pada Polars yang menyebabkan disinkronisasi pemetaan ID numerik ke string saat beberapa proses terisolasi memproses tipe `pl.Categorical`.
2. Mengapa format `pl.Enum` memitigasi risiko integritas data ini dibandingkan `pl.Categorical` yang bersifat dinamis?
3. Tuliskan pola perbaikan implementasi (*remediation pattern*) yang menjamin konsistensi decoding string antarchunk, baik dengan pendekatan `StringCache` terpusat maupun transisi ke tipe data alternatif yang deterministik.

---

### Skenario C: Migrasi Arsitektur dari Apache Spark ke Polars Single-Node
Sebuah platform perbankan digital memiliki cluster Apache Spark (1 Master + 8 Workers, total 128 vCPU, 512 GB RAM) yang didedikasikan untuk menjalankan satu *pipeline* *nightly reconciliation* berukuran dataset mentah 400 GB. Biaya infrastruktur bulanan dinilai terlampau mahal untuk beban kerja tersebut, dan latensi pekerjaan saat ini memakan waktu 45 menit karena *shuffle overhead* dan konkurensi JVM. Tim arsitektur data mengusulkan migrasi total ke sebuah mesin *bare-metal* tunggal berbasis AMD EPYC (64 core, 128 GB RAM, NVMe SSD) menggunakan Polars.

**Permasalahan:**  
Sebagian *stakeholder* meragukan kemampuan Polars untuk memproses data 400 GB pada mesin 128 GB RAM tanpa *distributed storage*, serta mengkhawatirkan hilangnya toleransi kesalahan bawaan (*fault tolerance/checkpointing*) yang dimiliki Spark.

**Pertanyaan Diagnostik:**
1. Lakukan analisis kelayakan teknis: Bagaimana Polars dapat secara realistis mengeksekusi pipeline 400 GB pada mesin 128 GB RAM dengan memanfaatkan *memory-mapped I/O* (mmap), *disk spilling*, dan kompresi Arrow?
2. Identifikasi batasan kritis (*critical trade-offs*) yang harus dikorbankan sistem ketika beralih dari arsitektur *distributed horizontal scaling* (Spark) ke *vertical scale-up processing* (Polars).
3. Jika pipeline tersebut melibatkan *heavy joins* (misal: *fuzzy matching* 100 juta baris rekening terhadap 500 juta baris transaksi log), bagaimana Anda merancang strategi pemrosesan bertahap (*staging/chunking strategy*) di Polars agar stabilitas sistem tetap terjamin tanpa risiko kegagalan fatal di tengah jalan?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Financial Tick Aggregator & Feature Pipeline (Out-of-Core)

#### Deskripsi Permasalahan
Anda ditugaskan membangun mesin pemroses data pasar keuangan (*high-frequency trading feature engineering engine*). Sistem harus mampu membaca arsip rekaman transaksi harian (*tick data*) berukuran 50 GB dalam format Parquet terkompresi ZSTD, menghitung serangkaian indikator mikrostruktur pasar berbasis jendela waktu (*time-window*), dan menghasilkan dataset fitur berformat Parquet dengan partisi partisi per tanggal dan simbol saham.

#### Requirements
1. **Lazy Evaluation & Streaming Constraints:**  
   Seluruh alur kerja wajib menggunakan API `pl.scan_parquet()` dan dieksekusi menggunakan konfigurasi streaming. Memori fisik (RAM) aplikasi tidak boleh melebihi batas **8 GB** selama seluruh siklus hidup eksekusi script.
2. **Kalkulasi Fitur Finansial Murni Tanpa UDF:**  
   Tidak diperbolehkan menggunakan `.map_elements()` atau Python UDF sama sekali. Semua metrik berikut harus dikomputasi menggunakan ekspresi analitis native Polars:
   * **VWAP (Volume-Weighted Average Price):** Dihitung per interval bergulir (*rolling window*) 5 menit per simbol saham.
   * **Realized Volatility:** Dihitung sebagai standar deviasi dari *log returns* harga transaksi pada *rolling window* 15 menit.
   * **Order Book Imbalance Proxy:** Dihitung dari delta volume beli versus jual dinormalisasi terhadap total volume dalam interval berjalan.
3. **Optimasi Rencana Kueri (Query Plan):**  
   Skrip harus mencetak output dari `.explain(optimized=True)` ke berkas log audit untuk membuktikan bahwa *Projection Pushdown* dan *Predicate Pushdown* telah aktif secara optimal.
4. **Partitioned Sink Execution:**  
   Hasil akhir harus ditulis langsung ke *disk* menggunakan metode *streaming sink* (`sink_parquet()`) dengan kompresi ZSTD level 3, dipartisi secara modular tanpa memuat dataset akhir ke RAM sebelum penulisan.

#### Constraints
* **Lingkungan Eksekusi:** Single node, dibatasi secara artifisial menggunakan modul `resource` (Linux) atau batasan kontainer pada **8 GB Resident Set Size (RSS)**.
* **Volume Data:** 50 GB file transaksi mentah (minimal 100 juta baris simulasi tick).
* **Dependensi:** Hanya diperbolehkan menggunakan pustaka `polars` (>= 0.20.x) dan pustaka standar Python (tanpa `pandas`, `dask`, atau `pyspark`).

#### Expected Output
1. File skrip Python fungsional: `market_feature_pipeline.py`.
2. Log eksekusi yang menunjukkan:
   * Profil penggunaan memori puncak (*peak RSS memory footprint*) yang divalidasi tidak melampaui 8 GB.
   * Representasi grafis atau teks dari *Optimized Physical Plan*.
   * Durasi eksekusi total (throughput metrik: baris/detik).
3. Direktori dataset hasil partisi yang valid dan dapat dibaca kembali oleh Polars secara instan dengan verifikasi integritas tipe data (schema check).

---

## 5. Knowledge Check & Checklist

Gunakan daftar centang mandiri ini untuk mengaudit penguasaan teknis Anda terhadap materi Bab 04 sebelum melanjutkan ke topik berikutnya.

### Saya harus memahami:
- [ ] Perbedaan fundamental antara arsitektur array Apache Arrow (termasuk *validity masks* dan *offset buffers*) dengan model blok NumPy.
- [ ] Anatomi siklus kerja Polars: parsing kode ke *Logical Plan*, transformasi oleh mesin pengoptimal (*optimizer passes*), penerjemahan ke *Physical Plan*, dan eksekusi pada *Rayon threadpool*.
- [ ] Cara kerja *Predicate Pushdown*, *Projection Pushdown*, *Slice Pushdown*, dan *Common Subexpression Elimination* (CSE).
- [ ] Mekanisme internal eksekusi *streaming* Polars: bagaimana *chunks* diproses melalui *pipeline operators* (Morsel-driven parallelism) dan batasan memori operator stateful.
- [ ] Biaya performa dari *thread contention*, GIL re-entry, dan alokasi memori berlebih saat mencampur kode native Rust Polars dengan fungsi Python murni.
- [ ] Dampak tipe data `pl.Categorical` terhadap paralelisasi dan kapan wajib menggunakan `pl.Enum` atau `StringCache`.

### Saya tidak perlu menghafal:
- [ ] Daftar lengkap kode sumber Rust internal yang membangun engine Polars (misal: implementasi spesifik *trait* pada kernel Arrow Rust).
- [ ] Nilai byte-level biner presisi dari format file Parquet *page header* dan *thrift definition*.
- [ ] Sintaks mikro dari seluruh argumen eksperimental yang belum stabil pada fungsi internal Polars.
- [ ] Algoritma kompresi internal ZSTD/Snappy hingga ke level transformasi matematika Huffman coding.

### Saya harus bisa melakukan:
- [ ] Mengonversi kode analitik berbasis Pandas lambat ke ekspresi Polars terparalelisasi penuh tanpa menggunakan satu pun *looping* atau `.apply()`.
- [ ] Membaca dan menginterpretasikan output diagram dari `.explain()` untuk mengidentifikasi inefisiensi kueri atau kegagalan *pushdown optimization*.
- [ ] Menulis pipeline pemrosesan *end-to-end* yang menangani file sebesar ratusan gigabyte pada mesin dengan RAM terbatas menggunakan `pl.scan_*()` dan `sink_parquet()`.
- [ ] Melakukan *profiling* konsumsi memori dan penggunaan thread CPU pada aplikasi Polars di lingkungan kontainer (Docker/Kubernetes).
- [ ] Mengonfigurasi strategi interop *zero-copy* data antara Polars, PyArrow, dan format penyimpanan berbasis kolom secara efisien.