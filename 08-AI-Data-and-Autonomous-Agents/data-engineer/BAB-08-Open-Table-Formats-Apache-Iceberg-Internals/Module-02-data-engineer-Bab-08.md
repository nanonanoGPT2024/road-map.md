# BAB 08: Open Table Formats - Apache Iceberg Internals
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Anatomi Metadata Iceberg**: Membedah struktur tree metadata Apache Iceberg secara granular (`vN.metadata.json`, `Manifest List`, `Manifest File`, `Data File`, dan `Delete File`).
- **Menguasai Mekanisme Row-Level Deletes**: Mengimplementasikan dan membandingkan karakteristik performa serta *I/O cost* antara *Copy-on-Write* (COW) dan *Merge-on-Read* (MOR) dengan *Position Deletes* dan *Equality Deletes*.
- **Mendesain Pola Ingesti Zero-Downtime**: Mengonfigurasi pola *Write-Audit-Publish* (WAP) menggunakan native branching dan tagging Apache Iceberg pada pipeline produksi.
- **Mengorkestrasi Maintenance Engine**: Membangun pipeline otomatisasi pembersihan snapshot, rewrite manifest, bin-packing, dan data clustering (Z-Order/Hilbert curve).
- **Menangani Concurrency Conflict**: Mengatasi *Optimistic Concurrency Control* (OCC) commit failure pada skala streaming dan batch tingkat tinggi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- Arsitektur storage objek terdistribusi (Amazon S3, Google Cloud Storage, atau MinIO) beserta sifat *eventual consistency* dan atomic operation limit-nya.
- Format file kolumnar: Apache Parquet internals (Row Groups, Column Chunks, Dictionary Encoding, Bloom Filters, Statistics).
- Fundamental Apache Spark/Trino: Execution plan, memory management, shuffle partitioning, dan Catalog interface.
- Konsep dasar ACID transaction, isolation level (khususnya *Snapshot Isolation* dan *Serializable*).

---

### 3. Concept & Internal Architecture

Apache Iceberg memisahkan abstraksi physical layout dari logical dataset. Berbeda dari format tradisional bergaya Apache Hive yang mendefinisikan tabel berdasarkan direktori penyimpanan, Iceberg melacak setiap file data secara eksplisit menggunakan pohon metadata bertingkat (*hierarchical metadata tree*).

```
                        +----------------------+
                        |   Iceberg Catalog    |
                        | (REST/Nessie/Glue)   |
                        +----------+-----------+
                                   |
                  points to current metadata pointer
                                   |
                                   v
                      +--------------------------+
                      |    v3.metadata.json      |
                      |  - Table UUID, Schema    |
                      |  - Partition Specs       |
                      |  - Current Snapshot ID   |
                      |  - Snapshot History Log  |
                      +------------+-------------+
                                   |
                   current-snapshot-id references
                                   |
                                   v
                      +--------------------------+
                      | snap-89234.avro          |  (Manifest List)
                      |  - Manifest Path A       |
                      |  - Added/Deleted Counts  |
                      |  - Partition Field Range |
                      +----+----------------+----+
                           |                |
             +-------------+                +-------------+
             v                                            v
+--------------------------+                +--------------------------+
| manifest-a1.avro         |                | manifest-a2.avro         |
| (Manifest File - Data)   |                | (Manifest File - Delete) |
| - file_path (Parquet)    |                | - file_path (Pos Delete) |
| - file_format, row_count |                | - referenced_data_file   |
| - lower/upper column bounds               | - pos (row offset)       |
+------------+-------------+                +-------------+------------+
             |                                            |
             v                                            v
+--------------------------+                +--------------------------+
| s3://.../part-001.parquet|                | s3://.../del-001.parquet |
| (Immutable Data File)    |                | (Position Delete File)   |
+--------------------------+                +--------------------------+
```

#### Komponen Utama Metadata Tree:
1. **Catalog Layer**: Menyimpan referensi atomic ke metadata file terbaru (`vN.metadata.json`). Contoh backend: Iceberg REST Catalog, Project Nessie, AWS Glue, Hive Metastore (HMS).
2. **Metadata File (`vN.metadata.json`)**:
   - Mendefinisikan schema table historis dan schema saat ini (dengan assign unique integer field ID permanen).
   - Menyimpan *Partition Spec Evolution*.
   - Menyimpan daftar snapshot historis dan snapshot log.
3. **Manifest List File (`snap-{snapshot_id}-{attempt}.avro`)**:
   - Berkorespondensi 1:1 terhadap setiap snapshot state.
   - Menyimpan daftar `Manifest File` yang membentuk snapshot tersebut.
   - Mengandung statistik tingkat tinggi: partition boundaries/ranges dari setiap manifest file untuk evaluasi *Manifest Pruning* sebelum manifest dibaca.
4. **Manifest File (`{guid}.avro`)**:
   - Melacak kumpulan `Data File` dan `Delete File`.
   - Mengandung column-level metrics per-data-file: *Null counts*, *Value counts*, *Lower bounds*, *Upper bounds*, dan status file (`ADDED`, `EXISTING`, `DELETED`).
5. **Data File & Delete File**:
   - File fisik aktual (Parquet, ORC, atau Avro) yang bersifat *immutable*.

#### Row-Level Deletes: Copy-On-Write (COW) vs Merge-On-Read (MOR)
- **Copy-On-Write (COW)**: Setiap mutasi baris data (UPDATE/DELETE) memicu penulisan ulang seluruh file Parquet yang terdampak.
  - *Kelebihan*: Zero-overhead read latency, scan membaca full Parquet secara sequential.
  - *Kekurangan*: High write amplification, I/O footprint masif untuk operasi update sporadis.
- **Merge-On-Read (MOR)**: Mutasi baris dituliskan ke dalam *Delete File* terpisah.
  - **Position Deletes**: File yang mencatat URI dari Data File target beserta offset barisnya (`pos`).
  - **Equality Deletes**: File yang mencatat nilai kolom penentu (misal `id = 'USR-902'`).
  - *Kelebihan*: Write amplification minimal, sangat cocok untuk throughput streaming ingesti tinggi.
  - *Kekurangan*: Read amplification saat engine (Spark/Trino) harus melakukan anti-join atau dynamic bitmasking antara data file dan delete file secara on-the-fly.

---

### 4. Why & What

| Dimensi Tradisional (Hive Partitioning) | Pendekatan Apache Iceberg | Dampak Arsitektural Enterprise |
| :--- | :--- | :--- |
| **Penyimpanan Status Direktori** | Status disimpan per-file di Metadata Tree | Menghilangkan O(N) `listStatus` filesystem calls ke object storage; scan query konstan terlepas dari jumlah file. |
| **Partisi Eksplisit** (`/dt=2026-03-30/hr=12`) | **Hidden Partitioning** via transform function | Mencegah user melakukan query anti-pattern; user memfilter timestamp asli, Iceberg otomatis melakukan partition pruning. |
| **Evolusi Skema Rapuh** | Field IDs tetap identik dan immutable | Aman menambah, menghapus, mengubah nama (*rename*), atau menyusun ulang kolom tanpa data corruption. |
| **Transaksi Parsial** | ACID Atomic Commit via Catalog | Tidak ada "dirty reads" saat job write gagal di tengah jalan; rollback terjadi secara otomatis dan instan. |
| **Multi-Engine Isolation** | File lock berbasis sistem metastore rawan desinkronisasi | Optimistic Concurrency Control (OCC) menjamin integritas data lintas Spark, Flink, Trino, dan StarRocks. |

---

### 5. How (Workflow Detail)

#### A. Read Planning Pipeline
1. **Catalog Lookup**: Engine meminta metadata pointer aktif dari catalog (`vN.metadata.json`).
2. **Snapshot Resolution**: Engine memilih snapshot aktif (atau snapshot masa lalu jika melakukan *Time Travel*).
3. **Manifest Pruning**: Engine membaca `Manifest List`, mengevaluasi partisi predicate pushdown terhadap range partisi manifest. Manifest yang tidak sesuai diabaikan tanpa dibaca.
4. **Data File & Row Group Pruning**: Engine membaca Manifest File yang lolos seleksi, mengevaluasi lower/upper bounds kolom terhadap predicate query. Data file yang berada di luar range di-skip.
5. **Execution Plan Generation**: Engine mengelompokkan data file (dan mendampingkan delete file jika mode MOR aktif) ke dalam partisi eksekusi (Spark tasks / Trino splits).

#### B. Optimistic Concurrency Control (OCC) Commit Workflow
```
Client Worker                     Catalog Layer                Object Storage
     |                                 |                             |
     | 1. Read Base Metadata (v1)      |                             |
     |-------------------------------->|                             |
     |                                 |                             |
     | 2. Write Data & Manifest Files  |                             |
     |-------------------------------------------------------------->|
     |                                 |                             |
     | 3. Generate New Metadata (v2)   |                             |
     |-------------------------------------------------------------->|
     |                                 |                             |
     | 4. Commit: Swap Pointer(v1->v2) |                             |
     |-------------------------------->|                             |
     |    (Atomic Compare-and-Swap)    |                             |
     |                                 |                             |
     |    [IF SUCCESS]                 |                             |
     |    Commit Selesai               |                             |
     |                                 |                             |
     |    [IF CONFLICT DETECTED]       |                             |
     |    Catalog rejects swap         |                             |
     |    Client re-reads v2           |                             |
     |    Re-evaluates if conflicting  |                             |
     |    Retries commit or aborts     |                             |
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem perpustakaan nasional:
- **Hive Style**: Arsip diletakkan di lemari bernama "Tahun 2026/Bulan 03". Untuk mencari buku, kurator harus berjalan membuka lemari dan memindai satu per satu buku fisik di dalamnya. Jika lemari diganti namanya, semua isi harus dipindahkan manual.
- **Apache Iceberg**: Sebuah buku katalog digital berantai (*Ledger*).
  - `vN.metadata.json` adalah buku induk registri.
  - `Manifest List` adalah bab indeks yang mencatat: "Halaman 10-20 berisi dokumen bertanggal 1 hingga 5 Maret".
  - `Manifest File` mencatat detail: "Dokumen ID 109 disimpan di Rak 4 Baris 2, memiliki nilai transaksi terkecil Rp100.000 dan terbesar Rp5.000.000".
  - Pembaca tidak pernah menyentuh rak buku sebelum tahu persis koordinat baris dan nomor dokumennya dari katalog digital.

```
Metadata Evolution:
Snapshot 1 (Base Write)
v1.metadata.json 
   └── snap-1.avro (Manifest List)
         └── m1.avro ──> [file_A.parquet, file_B.parquet]

Snapshot 2 (Fast Append)
v2.metadata.json
   └── snap-2.avro (Manifest List)
         ├── m1.avro ──> [file_A.parquet, file_B.parquet] (Reused!)
         └── m2.avro ──> [file_C.parquet] (New Added)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: PyIceberg Metadata Inspection

Skrip berikut melakukan inspeksi metadata Apache Iceberg secara programatik langsung dari Python:

```python
# pip install pyiceberg[pyarrow]
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    "production_rest",
    **{
        "type": "rest",
        "uri": "http://iceberg-catalog.internal:8181",
        "s3.endpoint": "https://s3.ap-southeast-1.amazonaws.com",
    }
)

table = catalog.load_table("core_banking.ledger_entries")

print(f"Current Snapshot ID: {table.current_snapshot().snapshot_id}")
print("Manifest List Path:", table.current_snapshot().manifest_list)

# Analisis struktur manifest list
for manifest in table.current_snapshot().manifests(table.io):
    print(f"Manifest Path: {manifest.manifest_path}")
    print(f"  Added Files: {manifest.added_files_count}")
    print(f"  Existing Files: {manifest.existing_files_count}")
    print(f"  Deleted Files: {manifest.deleted_files_count}")
    for partition_summary in manifest.partitions:
        print(f"    Partition Range: lower={partition_summary.lower_bound}, upper={partition_summary.upper_bound}")
```

#### Practical Example: Production PySpark Pipeline (WAP Pattern & MOR Config)

Contoh pipeline Spark kelas enterprise yang menerapkan Write-Audit-Publish (WAP) menggunakan native Iceberg Branching, konfigurasi Merge-on-Read, dan evaluasi metrik:

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, to_date

# 1. Inisialisasi Spark Session dengan Iceberg Extensions
spark = SparkSession.builder \
    .appName("IcebergEnterpriseIngestion") \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.prod", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.prod.type", "rest") \
    .config("spark.sql.catalog.prod.uri", "http://catalog.internal.net:8181") \
    .config("spark.sql.catalog.prod.warehouse", "s3a://enterprise-datalake/warehouse/") \
    .config("spark.sql.defaultCatalog", "prod") \
    .getOrCreate()

# 2. Pembuatan Tabel Transaksi Produksi dengan MOR dan Hidden Partitioning
spark.sql("""
CREATE TABLE IF NOT EXISTS prod.fintech.transactions (
    transaction_id STRING,
    account_id STRING,
    amount DECIMAL(18, 4),
    status STRING,
    event_timestamp TIMESTAMP
)
USING iceberg
PARTITIONED BY (days(event_timestamp), bucket(16, account_id))
TBLPROPERTIES (
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.parquet.compression-level' = '7',
    'write.delete.mode' = 'merge-on-read',
    'write.update.mode' = 'merge-on-read',
    'write.merge.mode' = 'merge-on-read',
    'write.wap.enabled' = 'true',
    'history.expire.max-snapshot-age-ms' = '604800000' -- 7 hari
)
""")

# 3. Step Ingesti ke Audit Branch menggunakan WAP pattern
branch_name = "audit_staging_batch_992"

# Buat branch dari state MAIN terkini
spark.sql(f"""
ALTER TABLE prod.fintech.transactions 
CREATE BRANCH IF NOT EXISTS {branch_name}
""")

# Menulis data baru langsung ke branch tanpa mempengaruhi pembaca MAIN
raw_records = [
    ("tx-1001", "acc-881", 12500.50, "COMPLETED", "2026-03-30 10:15:30"),
    ("tx-1002", "acc-442", 50000.00, "PENDING", "2026-03-30 10:16:00"),
    ("tx-1003", "acc-881", 300.00, "FAILED", "2026-03-30 10:17:15")
]

schema = "transaction_id STRING, account_id STRING, amount DECIMAL(18,4), status STRING, event_timestamp STRING"
df = spark.createDataFrame(raw_records, schema=schema) \
    .withColumn("event_timestamp", col("event_timestamp").cast("timestamp"))

# Tulis ke branch secara atomic
df.writeTo(f"prod.fintech.transactions.branch_{branch_name}").append()

# 4. Audit Step: Validasi Kualitas Data pada Branch
audit_failed_count = spark.sql(f"""
SELECT COUNT(*) as anomaly_count 
FROM prod.fintech.transactions.branch_{branch_name}
WHERE amount <= 0 OR account_id IS NULL
""").collect()[0]["anomaly_count"]

if audit_failed_count > 0:
    # Audit gagal, hancurkan branch tanpa menyentuh data produksi
    spark.sql(f"ALTER TABLE prod.fintech.transactions DROP BRANCH {branch_name}")
    raise ValueError(f"CRITICAL: Integrity audit failed with {audit_failed_count} anomalies. Write rejected.")

# 5. Publish Step: Fast-Forward Branch Audit ke Main Branch
spark.sql(f"""
CALL prod.system.fast_forward(
    table => 'fintech.transactions',
    branch => 'main',
    to => '{branch_name}'
)
""")

# Hapus branch audit setelah publish berhasil
spark.sql(f"ALTER TABLE prod.fintech.transactions DROP BRANCH {branch_name}")

print("WAP Pipeline executed successfully.")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Global FinTech Tier-1 Payment Processing
- **Volume**: 2,5 miliar event/hari (~15 TB data/hari).
- **Latency Requirement**: Data harus queryable dalam waktu < 2 menit setelah event terjadi.
- **Critical Requirement**: Pembatalan/koreksi transaksi (GDPR Right to Be Forgotten & Retraction) dapat terjadi kapan saja pada data 90 hari terakhir.

#### Masalah Pada Arsitektur Lama (Hive Metastore + Parquet COW)
1. **Catalog Bottleneck**: Melakukan partisi per-jam. Eksekusi `MSCK REPAIR TABLE` atau registrasi partisi ke Hive Metastore (HMS) memakan waktu 45 menit karena lock database RDBMS pada metastore.
2. **Write Amplification Ekstrem**: Ketika ada request penghapusan 10 baris transaksi pada data kemarin, Spark membaca dan menulis ulang 400 GB file Parquet.
3. **Small File Problem**: Ingesti streaming Flink 1 menit sekali menghasilkan ribuan file berukuran 2 MB, melumpuhkan storage node namenode/S3 IOPS.

#### Solusi Arsitektur Menggunakan Apache Iceberg:
1. **Adopsi REST Catalog**: Mengganti HMS dengan decoupled High-Availability REST Catalog berbasis DynamoDB/Postgres clustering.
2. **Switch ke Merge-On-Read dengan Position Deletes**: Flink menulis data streaming secara langsung; jika terjadi penghapusan atau pembaruan status, Flink menulis position delete file berukuran kecil (beberapa KB).
3. **Multi-tier Maintenance Daemon**:
   - Tiap 10 menit: Ingesti stream menulis via fast-append.
   - Tiap 1 jam: Engine eksekusi (Spark) menjalankan rewrite data files menggunakan strategi Bin-Packing untuk file streaming kecil.
   - Tiap 24 jam: Sorting ulang data menggunakan Z-Order (berdasarkan kolom `account_id` dan `event_timestamp`) serta konversi delete files menjadi baseline data murni (COW merge catch-up).

#### Hasil Pengukuran:
- Ingestion SLA turun drastis dari 45 menit menjadi **45 detik**.
- Write amplification turun **92%** saat menangani pembaruan data historis.
- Query p95 Trino analytical scans meningkat **4.2x lebih cepat** berkat Min/Max pruning dan Z-Order file clustering.

---

### 9. Trade-offs

| Aspek Arsitektural | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Row Mutation Strategy** | **Copy-on-Write (COW)** | **Merge-on-Read (MOR)** | **COW** mengoptimalkan performa pembacaan analytics (*zero merge overhead*), namun membebani I/O write saat ada mutasi acak. **MOR** sangat hemat I/O write pada streaming ingestion, namun mengorbankan performa query latensi rendah jika delete files menumpuk belum di-compact. |
| **Delete Type** | **Position Delete** | **Equality Delete** | **Position Delete** membutuhkan index mapping file terlebih dahulu namun merge read-nya murah (*O(log N)* via bitmask). **Equality Delete** sangat murah ditulis saat streaming tanpa metadata lookahead, tetapi membebankan hash join/broadcast join yang sangat berat bagi query engine saat runtime scan. |
| **Data Clustering** | **Bin-Packing** | **Z-Order Clustering** | **Bin-Packing** mengeksekusi penggabungan file kecil dengan cepat tanpa shuffle data (I/O bounded). **Z-Order** memaksimalkan predicate pushdown multi-kolom secara drastis, tetapi proses rewrite-nya memicu global distributed shuffle yang memakan resource compute besar. |
| **Catalog Architecture** | **AWS Glue / HMS** | **REST Catalog Standalone** | **Glue/HMS** mudah diintegrasikan dengan managed services lama, namun terikat vendor dan memiliki batasan scale rate-limiting. **REST Catalog** independen, portable, mendukung spec paling mutakhir (Branching/V3 format), namun membutuhkan operasional service infra mandiri. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Snapshot Bloat & Manifest Explosion
- **Gejala**: Performa read planning melambat; Spark/Trino menghabiskan puluhan detik hanya pada tahapan `Query Planning`.
- **Penyebab**: Flink/Spark Streaming menulis commit setiap 30 detik tanpa pernah menjalankan pembersihan metadata, menyebabkan ribuan snapshot dan jutaan manifest file usang tetap tersimpan.
- **Solusi**:
  Jalankan maintenance `rewrite_manifests` dan `expire_snapshots` secara terjadwal:
  ```sql
  -- Mengoptimalkan metadata manifest tree
  CALL prod.system.rewrite_manifests('fintech.transactions');

  -- Memangkas snapshot usang dan menghapus data orphan
  CALL prod.system.expire_snapshots(
      table => 'fintech.transactions',
      older_than => TIMESTAMP '2026-03-23 00:00:00',
      retain_last => 24
  );
  ```

#### 2. CommitFailedException: Validation Exception (OCC Collision)
- **Gejala**: Job streaming crash dengan pesan:
  `org.apache.iceberg.exceptions.CommitFailedException: Requirement failed: branch main was modified concurrently`.
- **Penyebab**: Dua pipeline batch/streaming mencoba melakukan commit ke snapshot yang sama secara bersamaan (misal: pipeline backfill berjalan paralel dengan pipeline stream real-time).
- **Solusi**:
  1. Tingkatkan batas retry OCC pada konfigurasi catalog:
     ```properties
     commit.retry.num-retries=10
     commit.retry.min-wait-ms=100
     commit.retry.max-wait-ms=5000
     ```
  2. Pisahkan job penulisan data ke dalam branch audit/staging yang terisolasi, kemudian gabungkan (*fast-forward*) secara berurutan (*serialized*).

#### 3. Parquet Bounds Truncation Failure
- **Gejala**: Predicate pruning tidak berfungsi pada kolom tipe `STRING`, query selalu melakukan full scan pada semua file.
- **Penyebab**: Default konfigurasi Iceberg membatasi panjang evaluasi lower/upper bounds string (biasanya 16 byte). String yang memiliki prefix identik panjang gagal dipruning.
- **Solusi**:
  Sesuaikan panjang karakter batas statistik kolom:
  ```sql
  ALTER TABLE prod.fintech.transactions 
  SET TBLPROPERTIES ('write.metadata.metrics.column.transaction_id.length' = '64');
  ```

---

### 11. Best Practices (Production Checklist)

1. **Gunakan Partisi Tersembunyi (Hidden Partitioning)**: Jangan pernah membuat kolom partisi derivasi manual (misal: membuat kolom baru `transaction_date` dari `transaction_timestamp`). Gunakan selalu transform functions: `days(timestamp)`, `hours(timestamp)`, `bucket(N, id)`.
2. **Karantina Metadata Deletes**:
   - Jika write stream tinggi, gunakan `write.delete.mode = 'merge-on-read'`.
   - Jalankan proses `rewrite_data_files` berkala untuk mengonversi delete files kembali menjadi 100% data file Parquet murni.
3. **Pilih Ukuran Target File yang Tepat**:
   - Atur `write.target-file-size-bytes = 536870912` (512 MB) untuk analitik data lakehouse skala besar.
4. **Distribusi Shuffle Sebelum Write**:
   - Selalu atur `write.distribution-mode = 'hash'` untuk tabel berpartisi atau `write.distribution-mode = 'range'` untuk cluster sorting guna mencegah small files creation saat distributed write.
5. **Jadwalkan Maintenance Trio**:
   - **Tingkat 1 (Per-Jam)**: `rewrite_data_files` dengan binpack filter file < 64MB.
   - **Tingkat 2 (Harian)**: `rewrite_manifests` dan `expire_snapshots`.
   - **Tingkat 3 (Mingguan)**: `remove_orphan_files` untuk membersihkan partial uncommitted file di cloud storage.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

#### Step 1: Menyusun Lingkungan Produksi via Docker Compose
Buat file `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'

services:
  rest-catalog:
    image: tabulario/iceberg-rest:1.5.0
    container_name: iceberg-rest-catalog
    ports:
      - "8181:8181"
    environment:
      - AWS_ACCESS_KEY_ID=admin
      - AWS_SECRET_ACCESS_KEY=password
      - AWS_REGION=us-east-1
      - CATALOG_WAREHOUSE=s3a://iceberg-bucket/warehouse/
      - CATALOG_IO__IMPL=org.apache.iceberg.aws.s3.S3FileIO
      - CATALOG_S3_ENDPOINT=http://minio:9000

  minio:
    image: minio/minio:RELEASE.2024-03-15T01-07-19Z
    container_name: iceberg-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=admin
      - MINIO_ROOT_PASSWORD=password
    command: server /data --console-address ":9001"

  mc:
    image: minio/mc:latest
    depends_on:
      - minio
    entrypoint: >
      /bin/sh -c "
      until (/usr/bin/mc alias set minio http://minio:9000 admin password) do echo '...waiting...' && sleep 1; done;
      /usr/bin/mc mb minio/iceberg-bucket;
      exit 0;
      "

  spark-iceberg:
    image: tabulario/spark-iceberg:3.5.0_1.5.0
    container_name: iceberg-spark
    depends_on:
      - rest-catalog
      - minio
    environment:
      - AWS_ACCESS_KEY_ID=admin
      - AWS_SECRET_ACCESS_KEY=password
      - AWS_REGION=us-east-1
    ports:
      - "8888:8888"
      - "4040:4040"
```

Jalankan container:
```bash
docker compose -f hands-on/m02/docker-compose.yml up -d
```

#### Step 2: Eksekusi Advanced Pipeline & Maintenance Script
Buat skrip `hands-on/m02/advanced_iceberg_pipeline.py`:

```python
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import expr

spark = SparkSession.builder \
    .appName("HandsOnIcebergDeepDive") \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.demo", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.demo.type", "rest") \
    .config("spark.sql.catalog.demo.uri", "http://rest-catalog:8181") \
    .config("spark.sql.catalog.demo.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .config("spark.sql.catalog.demo.s3.endpoint", "http://minio:9000") \
    .config("spark.sql.catalog.demo.s3.path-style-access", "true") \
    .config("spark.sql.defaultCatalog", "demo") \
    .getOrCreate()

# 1. Buat Tabel berpartisi dinamis
spark.sql("CREATE NAMESPACE IF NOT EXISTS demo.ecommerce;")

spark.sql("""
CREATE TABLE IF NOT EXISTS demo.ecommerce.orders (
    order_id STRING,
    customer_id STRING,
    total_amount DOUBLE,
    order_time TIMESTAMP
)
USING iceberg
PARTITIONED BY (hours(order_time))
TBLPROPERTIES (
    'write.delete.mode'='merge-on-read',
    'write.update.mode'='merge-on-read',
    'write.target-file-size-bytes'='1048576' -- 1MB untuk tujuan demonstrasi
);
""")

print("Membuat 5 snapshot data kecil untuk mensimulasikan fragmentasi...")
for i in range(5):
    spark.sql(f"""
    INSERT INTO demo.ecommerce.orders VALUES 
    ('ord-{i}a', 'cust-{i}', {100.0 * (i+1)}, TIMESTAMP '2026-03-30 08:{i*10}:00'),
    ('ord-{i}b', 'cust-{i}', {150.0 * (i+1)}, TIMESTAMP '2026-03-30 09:{i*10}:00')
    """)

# 2. Hapus sebuah row menggunakan Merge-on-Read (Menghasilkan Delete File)
spark.sql("DELETE FROM demo.ecommerce.orders WHERE order_id = 'ord-1a'")

print("Daftar files sebelum maintenance:")
spark.sql("SELECT file_path, file_format, record_count, content FROM demo.ecommerce.orders.files").show(truncate=False)

# 3. Jalankan Compaction: Rewrite Data Files dengan Z-Order
print("Menjalankan rewrite_data_files Z-Order...")
spark.sql("""
CALL demo.system.rewrite_data_files(
    table => 'ecommerce.orders',
    strategy => 'sort',
    sort_order => 'zorder(customer_id, order_time)',
    options => map('max-file-size-bytes','2097152')
)
""")

print("Daftar files setelah Z-Order compaction (Delete file ter-merge ke data murni):")
spark.sql("SELECT file_path, file_format, record_count, content FROM demo.ecommerce.orders.files").show(truncate=False)

# 4. Validasi Time-Travel ke Snapshot Pertama
first_snapshot = spark.sql("SELECT snapshot_id FROM demo.ecommerce.orders.snapshots ORDER BY committed_at ASC LIMIT 1").collect()[0]["snapshot_id"]
print(f"Data pada Snapshot Pertama ({first_snapshot}):")
spark.sql(f"SELECT * FROM demo.ecommerce.orders VERSION AS OF {first_snapshot}").show()

spark.stop()
```

Jalankan skrip di dalam container Spark:
```bash
docker cp hands-on/m02/advanced_iceberg_pipeline.py iceberg-spark:/home/iceberg/
docker exec -it iceberg-spark spark-submit /home/iceberg/advanced_iceberg_pipeline.py
```

---

### 13. Exercise

#### Level: Easy
Buat DDL tabel Iceberg `demo.ecommerce.customers` dengan skema:
- `customer_id` (STRING)
- `email` (STRING)
- `signup_date` (DATE)
- Partisikan berdasarkan `years(signup_date)`.
- Jalankan satu instruksi evolusi skema untuk mengganti nama kolom `email` menjadi `primary_email` tanpa memicu data rewrite.

#### Level: Medium
Tulis skrip PySpark yang melakukan:
1. Membaca tabel transaksi MOR yang memiliki akumulasi *Position Delete Files*.
2. Membaca metadata inspection table `.snapshots` dan `.history`.
3. Menjalankan stored procedure `demo.system.rewrite_manifests` dan menganalisis perbandingan jumlah file manifest sebelum dan sesudah prosedur dijalankan.

#### Level: Hard
Rancang script PySpark yang mensimulasikan *Concurrent Write Race Condition*:
1. Thread-A dan Thread-B membaca baseline snapshot yang sama.
2. Keduanya memicu operasi `UPDATE` pada partition bucket yang sama secara bersamaan.
3. Tangkap `CommitFailedException` pada salah satu thread.
4. Terapkan algoritma *Exponential Backoff with Jitter* secara programatik agar worker yang gagal secara otomatis me-refresh metadata snapshot dan mengulang mutasi data tanpa menyebabkan integritas rusak.

---

### 14. Challenge

**Skenario Kasus**:
Anda adalah Principal Data Platform Architect di platform Media Streaming dengan skala **100.000 events/detik** yang disimpan ke Iceberg table `user_playback_telemetry`.
1. Data masuk terus-menerus melalui Apache Flink dengan interval micro-checkpoint 30 detik.
2. Tim Compliance mengharuskan pembersihan data PII pengguna (berdasarkan `user_id`) dalam waktu maksimum 3 jam setelah adanya permohonan (*Right to Be Forgotten*).
3. Tim BI menjalankan analitik real-time pada tabel yang sama dengan SLA latency query dashboard p99 < 5 detik.

**Tugas Anda**:
Rancang dokumen arsitektur dan topologi komprehensif yang memecahkan konflik antara:
- Ingesti kontinu (Flink streaming).
- Penghapusan baris berkala (Compliance GDPR/MOR deletion).
- Query analitik beban tinggi tanpa terkena dampak performa pemindaian ratusan *Delete Files*.

Dokumen arsitektur harus mencakup:
- Strategi penataan partisi & sort strategy.
- Orquestrasi micro-compaction vs major-compaction (kapan COW dieksekusi vs kapan MOR dieksekusi).
- Konfigurasi parameter isolasi transaksi tabel dan sistem snapshot retention policy.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. **Di manakah letak pointer aktif terkini dari sebuah Apache Iceberg table disimpan secara definitif?**
   - A. Di dalam blok header Parquet pertama
   - B. Di dalam file `vN.metadata.json` terakhir yang diregistrasikan pada Catalog
   - C. Di dalam storage local disk worker node
   - D. Di dalam direktori `_delta_log`

2. **Apa fungsi utama dari `Manifest List File` dalam arsitektur Iceberg?**
   - A. Menyimpan payload data mentah dalam format biner
   - B. Mengindeks manifest file yang tergabung dalam sebuah snapshot beserta rentang partisinya
   - C. Menggantikan peran catalog eksternal secara keseluruhan
   - D. Menyimpan log query audit dari end-user

3. **Operasi mana di bawah ini yang dapat dilakukan pada Apache Iceberg secara instan tanpa perlu membaca dan menulis ulang seluruh Data File fisik?**
   - A. Melakukan hashing terhadap isi seluruh record
   - B. Mengubah algoritma enkripsi disk storage
   - C. Mengganti nama kolom (*Rename Column*) pada skema tabel
   - D. Menghapus 50% data menggunakan mode Copy-on-Write

4. **Karakteristik utama dari konsep *Hidden Partitioning* pada Apache Iceberg adalah:**
   - A. Direktori partisi dienkripsi menggunakan kunci KMS
   - B. Engine mengonsumsi fungsi partisi dari field asli; pemanggil query tidak perlu memfilter kolom turunan partisi secara eksplisit
   - C. File disimpan di luar struktur warehouse folder
   - D. Partisi hanya disimpan di memori RAM catalog

5. **Format metadata default yang digunakan Iceberg untuk Manifest List dan Manifest File adalah:**
   - A. CSV
   - B. JSON
   - C. Apache Thrift
   - D. Apache Avro

#### B. Pertanyaan Intermediate (5 Soal)
6. **Dalam mekanisme Merge-On-Read (MOR), apakah perbedaan teknis mendasar antara *Position Delete* dan *Equality Delete*?**
   - A. Position Delete menghapus kolom, Equality Delete menghapus file
   - B. Position Delete merujuk URI file data spesifik dan posisi nomor barisnya; Equality Delete merujuk nilai dari suatu field predikat
   - C. Position Delete hanya berlaku untuk storage lokal; Equality Delete berlaku untuk cloud
   - D. Position Delete tidak mendukung format file Parquet

7. **Ketika query engine mengeksekusi scanning pada tabel Iceberg, urutan evaluasi pemangkasan (*pruning*) yang tepat adalah:**
   - A. File Data -> Manifest List -> Manifest File
   - B. Manifest List -> Manifest File -> Data File / Row Group
   - C. Catalog -> File Data -> Manifest List
   - D. Row Group -> Manifest List -> Catalog

8. **Apa yang terjadi ketika dua proses paralel mencoba meng-commit perubahan snapshot baru secara bersamaan ke tabel yang sama menggunakan REST Catalog?**
   - A. Keduanya crash dan seluruh data tabel terhapus
   - B. Catalog menerapkan atomic Compare-And-Swap (CAS); satu proses berhasil, proses lain menerima error `CommitFailedException` dan harus mengevaluasi ulang perubahannya
   - C. Terjadi overwrite data tanpa peringatan (data loss)
   - D. File metadata digabungkan secara otomatis oleh S3 storage backend

9. **Apa konsekuensi arsitektural jika sebuah tabel MOR memiliki rasio Delete File yang sangat tinggi terhadap Data File yang belum sempat terkompaksi?**
   - A. File Parquet menjadi corrupt
   - B. Write latency meningkat pesat
   - C. Query read amplification meningkat drastis akibat overhead engine saat mencocokkan baris yang terhapus pada memory runtime
   - D. Snapshot history terhapus secara otomatis

10. **Prosedur sistem manakah yang harus dijalankan untuk membersihkan file fisik pada Cloud Storage yang tidak lagi terikat pada snapshot mana pun akibat failure di tengah operasi write?**
    - A. `system.rewrite_manifests`
    - B. `system.expire_snapshots`
    - C. `system.remove_orphan_files`
    - D. `system.fast_forward`

#### C. Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**: Sebuah tim analytics melaporkan bahwa query scan harian pada tabel transaksi berukuran 100 TB melambat secara signifikan selama 3 bulan terakhir, meskipun volume data harian yang di-query stabil (hanya 1 hari terakhir). Hasil diagnosa menunjukkan tahap "Query Planning" memakan waktu 40 detik sebelum eksekusi Parquet scan dimulai. Langkah remediasi apa yang harus dilakukan?
    - A. Mengubah format storage data dari Parquet ke ORC
    - B. Mengurangi ukuran partisi dari harian menjadi menitan
    - C. Menjalankan maintenance rutin `system.expire_snapshots` dan `system.rewrite_manifests` untuk memangkas pohon manifest yang menumpuk jutaan record usang
    - D. Membesarkan ukuran RAM driver node Spark menjadi 1 TB tanpa mengubah konfigurasi tabel

12. **Skenario 2**: Pipeline streaming Flink menulis data transaksi keuangan menggunakan mode Merge-On-Read dengan interval commit setiap 10 detik. Setelah 48 jam, query read latency pada engine Trino anjlok secara signifikan. Tim engineer memutuskan menjadwalkan stored procedure `system.rewrite_data_files` dengan opsi filter file kecil. Namun ketika proses berjalan, tim data streaming mengeluhkan pipeline Flink mereka mengalami kegagalan commit (*OCC Failure*). Konfigurasi apa yang harus disesuaikan?
    - A. Matikan pipeline streaming Flink selama proses rewrite data berlangsung (downtime 2 jam)
    - B. Ubah Write Isolation level tabel menjadi Non-ACID
    - C. Konfigurasi `rewrite_data_files` menggunakan partial commit isolation dan tingkatkan nilai `commit.retry.num-retries` pada Flink sink connector
    - D. Ubah tabel menjadi Hive format biasa

13. **Skenario 3**: Sebuah bank digital mengimplementasikan pola Write-Audit-Publish (WAP). Job Spark ETL menulis 5 juta baris mutasi rekening ke dalam branch `wap_batch_nov`. Selama proses audit, ditemukan kejanggalan di mana 0.1% mutasi tidak memiliki header audit validation. Bagaimana tim data engineer menangani insiden ini agar tabel produksi utama (`main`) sama sekali tidak tercemar data rusak dan storage tidak mengalami kebocoran data?
    - A. Melakukan `DELETE FROM main WHERE validation_header IS NULL`
    - B. Cukup hapus audit branch (`ALTER TABLE ... DROP BRANCH wap_batch_nov`) lalu jalankan `system.expire_snapshots` untuk memusnahkan staged files
    - C. Menjalankan `RESTORE TABLE TO SNAPSHOT` secara manual di branch `main`
    - D. Menulis ulang seluruh tabel produksi dari cold backup storage

---

### Kunci Jawaban Quiz

#### A. Pertanyaan Basic
1. **B** - Referensi metadata aktif Iceberg selalu ditunjuk oleh Catalog melalui metadata JSON terbaru.
2. **B** - Manifest List bertindak sebagai indeks tingkat tinggi yang merangkum manifest file dan boundary partisinya.
3. **C** - Operasi modifikasi skema seperti rename kolom murni merupakan modifikasi metadata JSON melalui Field ID mapping permanen tanpa menulis ulang Parquet.
4. **B** - Hidden Partitioning mengisolasi user dari logika pembagian partisi fisik; filter query cukup merujuk pada nilai kolom asli.
5. **D** - Manifest List dan Manifest File disimpan dalam format file Apache Avro karena efisiensi serialisasi row-based metadata.

#### B. Pertanyaan Intermediate
6. **B** - Position delete merujuk secara kaku koordinat file dan baris, sedangkan Equality delete mendefinisikan kriteria logis nilai field.
7. **B** - Hierarki pembacaan: Manifest List dibaca dan dipruning lebih dahulu, lalu Manifest File, kemudian menyaring Data File dan Row Groups spesifik.
8. **B** - Iceberg mengimplementasikan OCC. Jika target commit snapshot sudah bergeser oleh writer lain, writer saat ini menerima exception dan harus mencoba ulang (retry) validasi state.
9. **C** - Read amplification terjadi karena engine analytics terpaksa memproses anti-join/filtering memory yang intensif antara Data Files dan tumpukan Delete Files.
10. **C** - `remove_orphan_files` memindai physical storage dan menghapus file data yang tidak lagi berindeks di dalam metadata manapun.

#### C. Skenario Kasus Produksi
11. **C** - Planning time yang tinggi disebabkan oleh snapshot bloat dan manifest explosion; solusinya adalah mengeksekusi snapshot expiration dan penggabungan file manifest via rewrite manifests.
12. **C** - Optimistic Concurrency Control membutuhkan retry budget saat rewrite data files bersaing commit dengan streaming writer; isolasi commit parsial memungkinkan merge berjalan bertahap tanpa memblokir stream.
13. **B** - Karena isolasi WAP menggunakan branching Iceberg murni berada di luar `main`, cukup hapus branch audit tersebut; commit tidak pernah menyentuh `main`, dan physical data dihapus via snapshot expiration.

---

### 16. Summary

Apache Iceberg memecahkan batasan kritis arsitektur data lake tradisional dengan mengalihkan dependensi sistem dari struktur direktori fisik ke **Pohon Metadata ACID Hierarkis**. 

Poin-poin arsitektural penting:
1. **Metadata Layers**: Pemisahan `Catalog -> Metadata File -> Manifest List -> Manifest File -> Data/Delete File` memberikan kapabilitas atomic commits, instant schema evolution, dan efisiensi pruning tanpa listStatus filesystem calls.
2. **Mutasi Data Modern**: Mendukung model **Merge-on-Read (MOR)** untuk ingesti latensi rendah serta **Copy-on-Write (COW)** untuk read performance tinggi, yang dapat diseimbangkan melalui automated compaction jobs.
3. **Enterprise Operational Patterns**: Penerapan native **Branching & Tagging** memfasilitasi pola **Write-Audit-Publish (WAP)**, menghadirkan level isolasi transaksi tingkat database operasional ke skala analitik ribuan terabyte.
4. **Evolusi & Pemeliharaan Mandiri**: Health-check rutin menggunakan stored procedures (`rewrite_data_files` dengan Z-Order, `rewrite_manifests`, `expire_snapshots`) adalah kunci utama mempertahankan skalabilitas dan performa data platform kelas enterprise jangka panjang.