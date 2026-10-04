# BAB 10: Quiz, Challenge, & Knowledge Check
**Data Contracts, Quality Automation, & Pipeline Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Paradigma Kontrak Data (Data Contracts):**  
   Jelaskan secara fundamental perbedaan antara kendala integritas skema database relasional tradisional (misal: *DDL Constraints* seperti `FOREIGN KEY`, `NOT NULL`, `CHECK`) dengan implementasi modern **Data Contracts** yang didefinisikan antara tim produser (*software engineering*) dan konsumen (*data engineering/analytics*). Mengapa DDL saja terbukti gagal mencegah *silent data corruption* dan *schema drift* pada arsitektur data modern?

2. **Strategi Pengujian "Shift-Left" dalam Pipeline Data:**  
   Dalam konteks rekayasa data analitik, jelaskan perbedaan arsitektural dan operasional antara pengujian berbasis logika kode (*Unit Testing* transformasi analitik menggunakan mock data) dengan pengujian kualitas data saat *runtime* (*Data Quality Assertion* seperti Pandera/Great Expectations). Bagaimana prinsip *Shift-Left* diterapkan untuk mendeteksi anomali sebelum data masuk ke lapisan *staging*?

3. **Prinsip Idempoten (*Idempotency*) dan Determinisme Pipeline:**  
   Definisikan apa yang dimaksud dengan pipeline data yang idempoten (*idempotent pipeline*) dan deterministik (*deterministic pipeline*). Berikan analisis teknis mengapa pola penulisan *append-only* tanpa mekanisme partisi atau *upsert* berbasis kunci deterministik (*surrogate/natural key*) merupakan pelanggaran fatal terhadap prinsip reliabilitas pipeline ketika terjadi *job failure* dan *backfilling*.

4. **Pola Desain Write-Audit-Publish (WAP):**  
   Jelaskan siklus hidup dan mekanisme teknis dari pola desain arsitektur **Write-Audit-Publish (WAP)**. Bagaimana pola ini mengisolasi data kotor dari konsumsi hilir (*downstream consumption*) menggunakan teknik *branching* metadata (seperti pada Apache Iceberg) atau partisi *staging*, dibandingkan dengan pendekatan naif konvensional (*in-place overwriting*)?

5. **Observabilitas Data (*Data Observability*) vs Monitoring Aplikasi:**  
   Monitoring aplikasi tradisional umumnya berfokus pada metrik infrastruktur (CPU, memori, I/O, *network latency*, HTTP status code). Mengapa metrik tersebut tidak mencukupi untuk menjamin kesehatan pipeline analitik? Uraikan 5 pilar utama dalam Observabilitas Data (*Freshness*, *Volume*, *Schema*, *Lineage*, dan *Quality*) beserta contoh metrik kegagalan konkret untuk masing-masing pilar.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Analisis Komparasi Kinerja: Pandera vs Pydantic dalam Pemrosesan Tabular:**  
   Ketika memvalidasi dataset tabular berukuran jutaan baris pada memori, mengapa penggunaan `pydantic.BaseModel` yang diterapkan secara iteratif per baris (*row-by-row iteration* atau `.apply()`) menyebabkan *catastrophic performance drop*? Jelaskan bagaimana arsitektur internal Pandera mengeksekusi validasi secara tervektorisasi (*vectorized validation*) langsung di atas memori Apache Arrow/Pandas series, dan bagaimana ini berdampak pada alokasi *garbage collector* Python.

2. **Mekanisme Penanganan Kegagalan: Karantina Data & Dead-Letter Queue (DLQ):**  
   Rancang arsitektur internal mekanisme *Dead-Letter Queue (DLQ)* dan partisi karantina (*quarantine table*) untuk pipeline batch tabular. Jika 5% dari 10 juta baris transaksi melanggar kontrak data (misal: nilai `price` negatif atau format ISO-8601 tidak valid), bagaimana Anda merancang pemisahan data valid vs invalid secara atomik tanpa mematikan seluruh eksekusi batch dan tanpa menyebabkan degradasi performa I/O?

3. **Kompatibilitas Evolusi Skema (*Schema Evolution Rules*):**  
   Dalam format serialisasi modern (seperti Avro/Parquet) dan integrasi Schema Registry, jelaskan perbedaan teknis antara kompatibilitas:
   * **Backward Compatibility**
   * **Forward Compatibility**
   * **Full Compatibility**  
   Identifikasi skenario mutasi skema (misal: penambahan kolom opsional, penggantian tipe data dari `INT32` ke `INT64`, atau penghapusan kolom wajib) yang dapat memicu *breaking changes* fatal pada *downstream analytical query engine* (seperti DuckDB, Trino, atau Spark).

4. **Debugging Memory Leaks & OOM pada Validasi Skema Skala Besar:**  
   Sebuah *worker* pipeline Python mengalami *Out-Of-Memory (OOM) Killed* oleh OS saat memvalidasi dataset sebesar 40 GB menggunakan *framework* assertions data. Berdasarkan analisis internal memory footprint:
   * Apa saja penyebab internal memory blowup pada operasi *in-memory assertions* saat memproses *string/object datatypes*?
   * Langkah diagnostik dan refaktorisasi arsitektur apa yang harus diambil (misal: *chunk-based processing*, konversi zero-copy Arrow, atau proyeksi kolom/pushdown predicate) untuk menjaga konsumsi memori tetap konstan (*flat memory profile*)?

5. **Arsitektur Distributed Circuit Breaker pada Orchestration DAG:**  
   Bagaimana cara mendesain dan mengimplementasikan mekanisme *Circuit Breaker* otomatis di dalam orchestrator data (seperti Airflow atau Dagster)? Jika uji statistik mendeteksi adanya *drift* distribusi data drastis (misal: Jensen-Shannon Divergence melampaui *threshold* kritis pada fitur prediksi *churn*), bagaimana state mesin pipeline memutus eksekusi tugas hilir secara aman (*fail-safe halt*), memperbarui *state store*, dan memicu *graceful alert* tanpa meninggalkan *state lock* atau *dangling temporary partitions*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Degradasi Performa & Bottleneck Validasi Batch
* **Konteks:** Sebuah pipeline analitik memproses 150 juta baris data klik log (*clickstream*) setiap tengah malam. Tim data menambahkan suite validasi kualitas data berbasis Pandera/Great Expectations dengan 30 assertion rules (termasuk regex parsing untuk URL, pengecekan keunikan *composite key*, dan pengujian *range* temporal). Waktu eksekusi pipeline melonjak secara dramatis dari 45 menit menjadi 6 jam, melanggar SLA pelaporan eksekutif pada pukul 06:00 pagi.
* **Pertanyaan Diagnostik:**
  1. Identifikasi *bottleneck* komputasi yang paling mungkin terjadi di antara 30 assertion rules tersebut, khususnya terkait validasi berbasis regex dan pengecekan keunikan (*uniqueness*) pada skala 150 juta baris.
  2. Susun strategi optimasi teknis konkret (termasuk paralelisasi, pengubahan algoritma validasi, dan penggunaan *sampling-based probabilistic data structures* seperti HyperLogLog) untuk memangkas waktu validasi kembali ke batas toleransi (<30 menit) tanpa mengorbankan integritas data secara signifikan.

### Skenario B: Race Condition dan Kerusakan State pada Backfill Paralel
* **Konteks:** Seorang data engineer menjalankan eksekusi *backfill* manual untuk memproses ulang data historis bulan Januari hingga Maret menggunakan 10 worker paralel. Pada saat yang bersamaan, pipeline produksi harian *real-time* terus menulis data ke tabel target analitik yang sama (tabel SCD Type 2 - *Slowly Changing Dimensions*). Akibat ketiadaan isolasi konkurensi, tabel target mengalami korupsi data masif: terdapat rekaman tumpang tindih (*overlapping effective dates*), duplikasi *natural keys*, dan flag `is_current = True` ganda untuk entitas yang sama.
* **Pertanyaan Diagnostik:**
  1. Analisis *root cause* dari kegagalan konkurensi ini ditinjau dari level isolasi transaksi (*transaction isolation levels*) dan mekanisme mutasi state SCD Type 2.
  2. Rancang solusi arsitektur pertahanan (*concurrency control pattern*) untuk mencegah insiden ini terulang, dengan mempertimbangkan penggunaan *optimistic concurrency control* (OCC), partisi berbasis waktu yang terisolasi secara atomik, dan mekanisme *distributed lock*.

### Skenario C: Trade-off Arsitektur Validasi: In-Line Blocking vs Asynchronous Audit
* **Konteks:** Anda adalah Principal Data Architect untuk sistem pemrosesan transaksi finansial berkecepatan tinggi. Tim bisnis menuntut agar data dapat diakses di data warehouse analitik dalam waktu maksimal 60 detik setelah transaksi terjadi di Core Banking (*near real-time requirement*). Tim *Risk & Compliance* menuntut nol toleransi (*zero tolerance*) terhadap pelanggaran integritas finansial dan ketidakcocokan skema.
* **Pertanyaan Diagnostik:**
  1. Lakukan analisis *trade-off* mendalam antara dua pola implementasi:
     * **Pola 1 (In-Line Blocking Validation):** Validasi ketat dilakukan langsung di jalur kritis (*critical path* ingestion). Pelanggaran langsung menahan batch/aliran.
     * **Pola 2 (Out-of-Band / Asynchronous Audit & Quarantine):** Data ditulis langsung dengan latensi ultra-rendah; proses validasi berjalan secara asinkron di latar belakang yang menandai dan mengkarantina data kotor secara retrospektif.
  2. Pola mana yang akan Anda pilih untuk memenuhi kedua kebutuhan yang saling bertolak belakang tersebut? Rancang arsitektur hibrida (*hybrid approach*) yang meminimalkan *latency penalty* di jalur kritis namun tetap menjamin garansi integritas laporan keuangan.

---

## 4. Chapter Challenge

### Tantangan Praktis: Pembangunan Production-Grade Resilient Data Pipeline dengan Pandera, Write-Audit-Publish (WAP), dan Automated Circuit Breaker

#### Deskripsi Masalah
Anda ditugaskan membangun pipeline penyerapan data transaksi harian (*Daily Financial Ledger*) yang tangguh untuk platform e-commerce skala besar. Sering kali file data mentah yang dikirim oleh sistem pihak ketiga mengandung anomali kritis: tipe data yang melenceng (*schema drift*), nilai moneter negatif, transaksi tanpa `merchant_id` (*orphan records*), dan duplikasi ID transaksi. Data kotor ini tidak boleh mencemari tabel analitik utama (*Gold Layer*), namun batch tidak boleh langsung gagal sepenuhnya jika persentase baris rusak berada di bawah ambang batas toleransi (karantina otomatis).

#### Spesifikasi Kebutuhan Teknis (Requirements)
1. **Definisi Kontrak Data (Data Contract Layer):**
   * Bangun skema validasi deklaratif menggunakan **Pandera** (`DataFrameModel`) yang mencakup:
     * `transaction_id` (String, Non-Nullable, Unique, format: UUIDv4).
     * `timestamp` (DateTime64, Non-Nullable, rentang: tidak boleh di masa depan dan tidak boleh lebih tua dari 7 hari lalu).
     * `merchant_id` (String, Non-Nullable, regex: `^MCH-[0-9]{5}$`).
     * `amount` (Float64, Non-Nullable, nilai > 0.0, pembulatan 2 desimal).
     * `currency` (String, Non-Nullable, diizinkan: `['IDR', 'USD', 'SGD']`).
     * `status` (String, Non-Nullable, diizinkan: `['PENDING', 'SETTLED', 'REFUNDED']`).
2. **Implementasi Pola Write-Audit-Publish (WAP):**
   * **Write:** Tulis data mentah ke zona *Staging/Shadow* (format Parquet partitioned by `ingestion_date`).
   * **Audit:** Jalankan validasi skema dan assertion statistika secara tervektorisasi.
   * **Publish:** Jika audit lolos, lakukan *atomic promotion* (swap partisi atau *metadata update*) ke zona *Production/Gold*.
3. **Mekanisme Karantina (Dead-Letter Queue - DLQ):**
   * Baris yang melanggar kontrak data harus secara otomatis dialirkan ke zona *Quarantine/DLQ* (format Parquet) lengkap dengan kolom metadata tambahan: `violation_reason`, `violation_column`, dan `failed_at_timestamp`.
4. **Automated Circuit Breaker:**
   * Jika rasio baris yang invalid melampaui **Ambang Batas Kritis (Failure Threshold > 2.0% dari total baris)**, pipeline harus memutus eksekusi (*abort*), membatalkan seluruh proses *publish* ke zona *Gold*, menghapus data di zona *Staging*, mencatat insiden ke sistem log audit terstruktur (JSON), dan melempar *custom exception* (`CircuitBreakerTriggeredException`).

#### Batasan Teknis (Constraints)
* **Zero Row-by-Row Iteration:** Dilarang keras menggunakan `df.iterrows()`, `df.apply()`, atau loop Python murni untuk validasi dan filtering baris. Gunakan operasi *vectorized* dari Pandas/Pandera/Polars/PyArrow.
* **Idempotency Guarantee:** Menjalankan script berulang kali pada input partisi tanggal yang sama harus menghasilkan *state* akhir yang identik tanpa duplikasi data di zona Gold maupun Quarantine.
* **Structured Logging:** Seluruh aktivitas pipeline (total row, valid row, quarantined row, error rate, durasi validasi) wajib dicetak dalam format JSON-structured log yang kompatibel dengan agregator log (seperti Datadog/ELK).

#### Expected Output
1. Script Python arsitektural tunggal atau modular yang bersih, terstruktur, *type-hinted*, dan siap produksi (*production-ready*).
2. Simulasi pengujian dengan dataset *mock* (terdiri dari 100.000+ baris) yang mendemonstrasikan dua skenario:
   * **Skenario Berhasil Sebagian:** Data kotor < 2% dialirkan ke DLQ, data valid dipromosikan ke zona Gold.
   * **Skenario Circuit Breaker Terpicu:** Data kotor > 2% memicu terminasi pipeline, tidak ada data yang masuk ke Gold, dan log error terstruktur dicetak dengan benar.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kesiapan teknis Anda dalam mengimplementasikan pipeline data tingkat lanjut di lingkungan produksi.

### Saya harus memahami:
- [ ] Perbedaan fundamental antara validasi skema statis (*compile/ingestion time*), validasi semantik (*runtime assertion*), dan monitoring distribusi (*data drift*).
- [ ] Dampak komputasi dan manajemen memori dari validasi tervektorisasi (*vectorized validation*) vs iterasi per baris pada dataset analitik skala gigabyte/terabyte.
- [ ] Mekanisme isolasi transaksi (ACID), prinsip atomisitas penggantian partisi, dan pola desain *Write-Audit-Publish* (WAP).
- [ ] Cara kerja *Dead-Letter Queue* (DLQ) dan pemisahan *stream/batch* data kotor tanpa memicu kegagalan parsial yang tak terdeteksi (*silent partial failure*).
- [ ] Konsep *Schema Evolution* (Backward, Forward, Full) dan implikasi perubahan skema terhadap query hilir dan format penyimpanan kolumnar (Parquet/Arrow).
- [ ] Metrik observabilitas data modern: *Freshness*, *Distributional Drift*, *Volume Anomalies*, dan *Lineage Graph Traversal*.

### Saya tidak perlu menghafal:
- [ ] Seluruh sintaks fungsi assertion bawaan dari library pihak ketiga (Great Expectations, Pandera, Soda Core) secara spesifik; cukup pahami paradigma deklaratif dan cara merekayasa *custom check*.
- [ ] Implementasi internal level kernel dari sistem penyimpanan file sistem terdistribusi (seperti HDFS block allocation atau S3 internal multi-part upload protocols).
- [ ] Perintah CLI spesifik dari seluruh orchestrator data (Airflow, Dagster, Prefect); cukup pahami konsep DAG, idempotency tokens, dan retry mechanisms.

### Saya harus bisa melakukan:
- [ ] Merancang dan mengimplementasikan skema kontrak data ketat (*Data Contracts*) menggunakan pustaka validasi Python modern (seperti Pandera atau Pydantic) dengan operasi zero-copy/vectorized.
- [ ] Mengonfigurasi pipeline data yang idempoten secara absolut, di mana proses re-run data historis (*backfill*) tidak merusak atau menduplikasi *state* data analitik.
- [ ] Mengisolasi anomali data tabular ke dalam tabel karantina (DLQ) dengan metadata audit terperinci tanpa menjatuhkan proses batch utama.
- [ ] Membangun mekanisme *Automated Circuit Breaker* berbasis ambang batas statistika untuk menghentikan propagasi korupsi data ke lapisan konsumsi bisnis.
- [ ] Mendiagnosis dan mengeliminasi *memory leak* atau degradasi performa I/O yang timbul akibat rutinitas validasi kualitas data pada dataset berukuran masif.