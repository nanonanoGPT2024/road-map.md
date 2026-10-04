# BAB 01: Fondasi & Arsitektur
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Query Execution Plan**: Mengidentifikasi bottleneck pada tahap Logical Optimization, Physical Planning, hingga Whole-Stage Code Generation pada distributed execution engine (Apache Spark/Trino).
- **Menguasai Arsitektur Internal Open Table Formats**: Menerapkan protokol ACID transactional metadata logging (Apache Iceberg snapshot tree dan Delta Lake transaction log) untuk menghindari read-write conflicts dan distributed locks.
- **Mengoptimalkan Distributed Compute & Memory Management**: Mengonfigurasi Unified Memory Architecture (Storage vs. Execution memory, Off-heap memory, Tungsten binary format) untuk mengeliminasi Shuffle Spill dan Garbage Collection (GC) pauses.
- **Mendesain Arsitektur Modern Lakehouse Kelas Enterprise**: Mengimplementasikan pola Medallion Architecture terintegrasi dengan compaction strategy, Z-Ordering, partitioning pruning, dan data skipping.
- **Membangun Pipeline Data Produksi Fault-Tolerant**: Mengembangkan kode PySpark/Delta tingkat lanjut yang menangani schema evolution, idempotency, data deduplication, dan late-arriving data.

---

### 2. Prerequisite
Untuk menyerap materi secara optimal, Anda wajib memahami:
- **Distributed Computing Fundamentals**: Konsep shared-nothing architecture, CAP Theorem, RPC, dan distributed consensus.
- **JVM Internals**: Heap vs. Off-heap memory, Garbage Collection algorithms (G1GC), JVM bytecode execution.
- **Advanced SQL & Relational Algebra**: Window functions, query plans (`EXPLAIN ANALYZE`), join algorithms (Broadcast Hash Join, Sort-Merge Join, Shuffle Hash Join).
- **Linux & Storage Systems**: Page cache, POSIX I/O semantics, block storage vs. object storage (S3/GCS consistency models).
- **Python / Scala**: Pengalaman operasional tingkat menengah dengan PySpark atau Scala-Spark API.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Distributed Query Engine: The Catalyst Optimizer & Tungsten Engine
Mesin pemrosesan data modern seperti Apache Spark mengeksekusi komputasi melalui dua subsistem utama:

```
[SQL / DataFrame API]
        │
        ▼
[Unresolved Logical Plan] ─── (Catalog / Metastore Resolution)
        │
        ▼
[Resolved Logical Plan] ───── (Optimization Rules: Pushdown, Pruning)
        │
        ▼
[Optimized Logical Plan] ─── (Physical Planning & Cost-Based Optimizer)
        │
        ▼
[Selected Physical Plan] ──── (Whole-Stage Code Generation via Janino)
        │
        ▼
[Tungsten RDD Bytecode Execution]
```

1. **Analysis & Catalog Resolution**:
   Parser mentransformasi query menjadi Abstract Syntax Tree (AST). Unresolved Logical Plan diverifikasi terhadap data catalog (Hive Metastore, AWS Glue, atau Iceberg Catalog) untuk memvalidasi keberadaan tabel, tipe data kolom, dan fungsi.
2. **Logical Optimization**:
   Catalyst menerapkan rule-based transformations:
   - *Predicate Pushdown*: Memindahkan filter sedekat mungkin ke data source untuk meminimalkan I/O disk/network.
   - *Projection Pruning*: Mengeliminasi kolom yang tidak direferensikan dalam komputasi hilir.
   - *Constant Folding & Boolean Simplification*: Mengevaluasi ekspresi statis saat kompilasi plan.
3. **Physical Planning & Cost-Based Optimizer (CBO)**:
   Menerjemahkan logical operator ke physical operator (misal: `LogicalJoin` diubah menjadi `BroadcastHashJoinExec` atau `SortMergeJoinExec`). CBO memanfaatkan metadata statistik (cardinality, row size, null count, histogram) untuk memilih plan dengan estimasi cost I/O dan jaringan terendah.
4. **Tungsten Engine & Whole-Stage Code Generation**:
   Tungsten mengeliminasi overhead virtual machine (JVM object overhead dan dynamic dispatching) melalui:
   - *Memory Management*: Menggunakan memory biner off-heap (mengakses raw memory via `sun.misc.Unsafe`) dengan format byte-array kustom, meniadakan overhead objek JVM (16-byte object header) dan beban Garbage Collector.
   - *Whole-Stage CodeGen*: Menggabungkan beberapa physical operators dalam satu pipeline eksekusi menjadi satu loop fungsi flat bytecode Java menggunakan compiler *Janino*. Data diproses di register CPU dan L1/L2/L3 cache tanpa materiilasi data intermediate di RAM.

#### 3.2. Unified Memory Management: Storage vs. Execution
JVM Memory pada Apache Spark Executor dialokasikan ke dalam region yang dikontrol ketat:

$$\text{Total Executor Memory} = \text{Reserved Memory (300 MB)} + \text{Usable Memory}$$
$$\text{Usable Memory} = \text{Spark Memory Pool } (\sim 60\%) + \text{User Memory } (\sim 40\%)$$

Spark Memory Pool dibagi secara dinamis menjadi:
- **Execution Memory**: Digunakan untuk buffering data selama shuffle, sort, aggregation, dan join hash tables.
- **Storage Memory**: Digunakan untuk menyimpan cached data (`.cache()`, `.persist()`) dan broadcast variables.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Total JVM Executor Memory                       │
├───────────────────────────────────────┬─────────────────┬──────────────┤
│           Spark Memory Pool           │   User Memory   │   Reserved   │
│                 (60%)                 │      (40%)      │   (300 MB)   │
├───────────────────┬───────────────────┤                 │              │
│ Execution Memory  │  Storage Memory   │ User structures,│ System       │
│ (Shuffle, Sorts,  │  (Cached tables,  │ metadata, UDFs, │ internal     │
│  Hash-Joins)      │   Broadcasts)     │ framework deps  │ processes    │
│◄─────────────────►│◄─────────────────►│                 │              │
│    Dynamic Eviction Boundary          │                 │              │
└───────────────────────────────────────┴─────────────────┴──────────────┘
```

**Mekanisme Dynamic Eviction:**
Execution dan Storage memory saling meminjam ruang (borrowing). Jika Execution membutuhkan memori dan Storage memiliki ruang bebas, Storage akan meminjamkan memorinya. Namun, jika Execution membutuhkan memori yang sedang dipinjam oleh Storage, Execution dapat memaksa (evict) blok Storage untuk dibuang ke disk. Sebaliknya, Storage **tidak dapat** mengejeksi Execution memory yang sedang aktif beroperasi; Storage harus menunggu execution selesai jika terjadi perebutan resource.

#### 3.3. Shuffle Mechanics & Skewness
Shuffle adalah proses all-to-all distributed data redistribution melintasi jaringan.
- **BypassMergeSortShuffleWriter**: Digunakan jika partisi tujuan sedikit ($\le 200$) dan tidak ada map-side aggregation. Menulis file terpisah per partisi lalu menggabungkannya.
- **SortShuffleWriter**: Mensortir data dalam buffer memori berdasarkan target partition ID dan serialization key. Jika memori penuh, buffer tumpah (*spill*) ke disk sebagai file terurut sementara. Di akhir fase map, semua spilled files digabungkan menjadi satu file data shuffle (`.data`) tunggal disertai file indeks (`.index`).
- **Data Skew**: Terjadi ketika distribusi key partisi tidak seragam (misal: 80% transaksi berasal dari `merchant_id = 'UNKNOWN'`). Task yang memproses skew key akan berjalan lambat (*straggler*), menyebabkan executor OOM (*Out Of Memory*), sementara core lainnya idle.

#### 3.4. Open Table Formats: Storage Layer Internals
Object storage standar (Amazon S3, GCS) bersifat immutable dan tidak mendukung file-level atomic multi-file commits atau multi-table ACID transactions. Open Table Formats menyelesaikan masalah ini pada tingkat metadata:

| Dimensi Arsitektur | Apache Parquet Standar | Delta Lake | Apache Iceberg |
| :--- | :--- | :--- | :--- |
| **Transaction Semantics** | Tidak ada (Append-only/Overwrite brute force) | ACID via serializable JSON transaction logs (`_delta_log/`) | ACID via hierarchical immutable Snapshot Tree (Metadata Files -> Manifest Lists -> Manifests) |
| **Concurrency Control** | File locking primitif / External metastore | Optimistic Concurrency Control (OCC) | Optimistic Concurrency Control (OCC) |
| **Partitioning Logic** | Fisik berbasis direktori (`/year=2024/month=05/`) | Fisik berbasis direktori + In-memory partition index | Hidden Partitioning (transformasi logikal tanpa coupling nama folder fisik) |
| **Schema Evolution** | Merge schema expensive scan saat read | Transactional schema tracking via log sequence | In-place schema evolution via unique field-id tracking |
| **Time Travel** | Tidak didukung | Snapshot retention via commit version/timestamp | Snapshot IDs / Timestamps via root metadata pointers |

---

### 4. Why & What
- **Why**: Arsitektur data warisan berbasis Data Warehouse terpisah dari Data Lake (arsitektur dua tingkat/silo) menyebabkan fragmentasi logika, desinkronisasi data, redundansi penyimpanan (storage cost berlipat ganda), serta tidak adanya jaminan ACID pada streaming updates.
- **What**: **Modern Lakehouse Architecture** menyatukan keandalan, struktur, dan ACID transactions dari Data Warehouse dengan biaya rendah dan fleksibilitas format terbuka dari Data Lake. Implementasi enterprise mengandalkan mesin komputasi terdistribusi (Spark, Trino) di atas Open Table Formats (Delta Lake, Apache Iceberg) yang disimpan dalam object storage berbiaya rendah.

---

### 5. How (Workflow Detail)

Alur pipeline produksi end-to-end dengan ACID Lakehouse Storage:

```
[Ingestion Stream/Batch]
         │
         ▼
┌──────────────────┐
│   Bronze Layer   │ Raw Ingestion, Append-only, Exact Schema Preservation
└────────┬─────────┘
         │
         ▼ (Structured Streaming / Micro-batch / Data Cleansing)
┌──────────────────┐
│   Silver Layer   │ Conformed, Cleaned, Deduplicated, Enriched Data
└────────┬─────────┘
         │
         ▼ (Transactional Aggregation, Star Schema, Dimensional Modeling)
┌──────────────────┐
│    Gold Layer    │ High-Performance Aggregations, Z-Ordered, Analytical Views
└──────────────────┘
```

1. **Bronze Ingestion Phase**: Data diekstraksi dari sumber (Kafka, RDBMS, event logs) dan ditulis tanpa modifikasi destruktif ke format Delta/Iceberg. Menggunakan append-only write mode untuk persistensi audit trail lengkap.
2. **Silver Processing Phase**:
   - Schema enforcement memvalidasi tipe data; rekaman invalid dialihkan ke *Dead Letter Queue (DLQ)*.
   - Idempotent deduplication dijalankan menggunakan stateful watermarking atau transactional `MERGE INTO` (upsert).
   - Optimasi layout data melalui *Bin-packing Compaction* dan *Dynamic Partition Pruning*.
3. **Gold Aggregation Phase**:
   - Membangun agregasi analitik tingkat enterprise (mart tables).
   - Menjalankan *Z-Ordering* atau multi-dimensional clustering pada kolom ber-kardinalitas tinggi yang sering digunakan dalam klausa `WHERE` dan `JOIN`.
   - Mengaktifkan data skipping statistics pada file headers untuk mengeliminasi pembacaan data yang tidak relevan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Modern vs. Gudang Dokumen Kuno
- **Data Lake Tanpa Format Terbuka (Gudang Kuno)**: Anda melempar ribuan berkas kertas ke dalam gudang besar. Jika Anda mencari kontrak tertanggal 15 Mei 2023, staf perpustakaan harus membaca setiap halaman satu per satu (*Full Table Scan*). Jika dua orang mengganti isi berkas yang sama secara bersamaan, berkas tersebut rusak atau hilang (*Race Condition*).
- **Modern Lakehouse (Perpustakaan Digital Otomatis)**: Buku disimpan di rak fisik (Parquet data files). Di depan gedung, ada katalog master digital berlapis (*Metadata Snapshots*). Setiap ada penambahan buku, pustakawan mencatat perubahan tersebut ke jurnal audit terpusat (*Transaction Log*). Pembaca hanya melihat versi buku yang valid pada timestamp kedatangan mereka. Pencarian subjek tertentu langsung mengarah ke nomor rak dan baris buku spesifik tanpa melangkahi lorong lain (*Metadata Data Skipping via Min/Max stats*).

#### Diagram Transaksi ACID pada Open Table Format (Snapshot Isolation)
```
          Metadata File: v1.metadata.json
                   │
                   ▼
          Manifest List File: snap-1.avro
         ┌─────────┴─────────┐
         ▼                   ▼
Manifest A.avro         Manifest B.avro
┌────────┴────────┐     ┌────┴────────────┐
│ data_1.parquet  │     │ data_2.parquet  │
│ (id: 1..100)    │     │ (id: 101..200)  │
└─────────────────┘     └─────────────────┘
         ▲
         │ (Transaction: Ingest id: 201..300)
         │ Creates new immutable metadata: NO IN-PLACE MUTATION
         │
          Metadata File: v2.metadata.json
                   │
                   ▼
          Manifest List File: snap-2.avro
         ┌─────────┼─────────────────────┐
         ▼         ▼                     ▼
Manifest A.avro Manifest B.avro   Manifest C.avro (New)
                                         │
                                         ▼
                                  data_3.parquet
                                  (id: 201..300)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Membedah Catalyst Execution Plan
Kode berikut mendemonstrasikan cara membaca dan menganalisis Catalyst execution plan pada Spark.

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder \
    .appName("CatalystPlanInspection") \
    .master("local[*]") \
    .getOrCreate()

# Generate dummy dataframe
df1 = spark.range(1, 1000000).withColumn("val", F.col("id") * 2)
df2 = spark.range(500000, 1500000).withColumn("val_target", F.col("id") * 3)

# Filter dan Join
joined_df = df1.filter(F.col("id") > 600000) \
               .join(df2, on="id", how="inner") \
               .select("id", "val", "val_target")

# Tampilkan representasi Physical Plan
print("=== EXTENDED EXECUTION PLAN ===")
joined_df.explain(extended=True)

spark.stop()
```

Output interpretasi:
- **`== Parsed Logical Plan ==`**: Memetakan AST awal query.
- **`== Analyzed Logical Plan ==`**: Skema kolom dan tipe data telah divalidasi dengan catalog.
- **`== Optimized Logical Plan ==`**: Predicate `id > 600000` telah didorong (*pushed down*) sebelum operasi `Join`.
- **`== Physical Plan ==`**: Terlihat operator `SortMergeJoin` atau `BroadcastHashJoin`, status Whole-Stage CodeGen (`*`), serta alokasi exchange data (`AdaptiveSparkPlan`, `Exchange hashpartitioning`).

#### 7.2. Practical Example: Production-Grade Lakehouse Silver Pipeline
Implementasi batch-micro-batch ingestion pipeline menggunakan PySpark, Delta Lake, pemodelan ACID, deduplikasi idempotent, penanganan schema evolution, dan metadata maintenance.

```python
#!/usr/bin/env python3
"""
Production Data Pipeline: Bronze to Silver Ingestion Engine
Features:
- Schema Enforcement & Controlled Schema Evolution
- Idempotent Merge (Upsert) Semantics
- Data Skipping Optimization (Z-Order)
- Dynamic Resource Configuration & Logging
"""

import sys
import logging
from typing import Dict, Any
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
from delta.tables import DeltaTable

# Setup Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("EnterpriseLakehousePipeline")

def create_spark_session(app_name: str) -> SparkSession:
    """Menginisialisasi SparkSession dengan konfigurasi standar performa enterprise."""
    return SparkSession.builder \
        .appName(app_name) \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.adaptive.skewJoin.enabled", "true") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.databricks.delta.schema.autoMerge.enabled", "false") \
        .getOrCreate()

def get_bronze_schema() -> StructType:
    """Mendefinisikan skema kontrak ingestion bronze secara deterministik."""
    return StructType([
        StructField("transaction_id", StringType(), False),
        StructField("account_id", StringType(), False),
        StructField("amount", DoubleType(), False),
        StructField("currency", StringType(), True),
        StructField("event_timestamp", TimestampType(), False),
        StructField("ingest_timestamp", TimestampType(), True)
    ])

def process_bronze_to_silver(spark: SparkSession, bronze_path: str, silver_table_path: str):
    """
    Mengeksekusi transformasi conformed silver layer dengan Upsert ACID semantics.
    """
    try:
        logger.info(f"Membaca data Bronze dari {bronze_path}")
        schema = get_bronze_schema()
        
        # Baca input data dengan validasi skema ketat
        raw_bronze_df = spark.read \
            .format("parquet") \
            .schema(schema) \
            .load(bronze_path)

        # Transformasi Silver: Pembersihan, filtering nilai abnormal, dan normalisasi
        silver_clean_df = raw_bronze_df \
            .filter(F.col("amount") > 0.0) \
            .withColumn("currency", F.upper(F.coalesce(F.col("currency"), F.lit("USD")))) \
            .withColumn("processing_time", F.current_timestamp())

        # Deduplikasi dalam batch mikro berdasarkan identifier transaksi unik
        window_spec = F.row_number().over(
            __import__("pyspark.sql.window", fromlist=["Window"]).Window.partitionBy("transaction_id")
            .orderBy(F.col("event_timestamp").desc())
        )
        deduplicated_df = silver_clean_df.withColumn("row_num", window_spec) \
            .filter(F.col("row_num") == 1) \
            .drop("row_num")

        # Cek apakah tabel Delta Silver sudah ada
        if not DeltaTable.isDeltaTable(spark, silver_table_path):
            logger.info(f"Target silver table belum terdeteksi. Menginisialisasi Delta Table di {silver_table_path}")
            deduplicated_df.write \
                .format("delta") \
                .mode("overwrite") \
                .partitionBy("currency") \
                .save(silver_table_path)
        else:
            logger.info("Menjalankan transactional ACID MERGE (Upsert)")
            silver_target = DeltaTable.forPath(spark, silver_table_path)
            
            # Idempotent Upsert Logic
            silver_target.alias("target").merge(
                source=deduplicated_df.alias("source"),
                condition="target.transaction_id = source.transaction_id"
            ).whenMatchedUpdate(set={
                "account_id": "source.account_id",
                "amount": "source.amount",
                "currency": "source.currency",
                "event_timestamp": "source.event_timestamp",
                "processing_time": "source.processing_time"
            }).whenNotMatchedInsert(values={
                "transaction_id": "source.transaction_id",
                "account_id": "source.account_id",
                "amount": "source.amount",
                "currency": "source.currency",
                "event_timestamp": "source.event_timestamp",
                "processing_time": "source.processing_time"
            }).execute()

        logger.info("Pipeline Ingestion berhasil dieksekusi secara atomic.")
        
        # Table Maintenance: Compaction & Optimization
        logger.info("Menjalankan optimasi file compaction dan Z-Order.")
        delta_table = DeltaTable.forPath(spark, silver_table_path)
        delta_table.optimize().executeZOrderBy("account_id")

    except Exception as e:
        logger.error(f"Kegagalan fatal pada pipeline: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    spark_session = create_spark_session("BronzeToSilverPipelineEngine")
    
    # Path konfigurasi environment produksi
    BRONZE_INPUT_PATH = "/tmp/lakehouse/bronze/transactions/"
    SILVER_TARGET_PATH = "/tmp/lakehouse/silver/transactions/"

    # Setup dummy directory dan dataset simulasi untuk pengujian lokal
    import os, shutil
    os.makedirs(BRONZE_INPUT_PATH, exist_ok=True)
    
    sample_data = [
        ("tx_001", "acc_10", 150.50, "usd", "2024-05-01 10:00:00", "2024-05-01 10:05:00"),
        ("tx_002", "acc_11", 50.00, "eur", "2024-05-01 10:01:00", "2024-05-01 10:06:00"),
        ("tx_001", "acc_10", 150.50, "usd", "2024-05-01 10:00:00", "2024-05-01 10:07:00") # Duplikat
    ]
    
    temp_df = spark_session.createDataFrame(sample_data, [
        "transaction_id", "account_id", "amount", "currency", "event_timestamp", "ingest_timestamp"
    ])
    temp_df = temp_df.withColumn("event_timestamp", F.to_timestamp("event_timestamp")) \
                     .withColumn("ingest_timestamp", F.to_timestamp("ingest_timestamp"))
    temp_df.write.mode("overwrite").parquet(BRONZE_INPUT_PATH)

    # Eksekusi pipeline
    process_bronze_to_silver(spark_session, BRONZE_INPUT_PATH, SILVER_TARGET_PATH)
    
    # Verifikasi Integritas Data Silver
    result_df = spark_session.read.format("delta").load(SILVER_TARGET_PATH)
    logger.info(f"Total baris unik di Silver: {result_df.count()}")
    result_df.show(truncate=False)

    spark_session.stop()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Skala Data**: Platform E-Commerce Global memproses rata-rata 120.000 events/detik (~8 TB/hari raw JSON payload), dengan peak volume saat promo sebesar 450.000 events/detik.
- **SLA**: Keterlambatan analitik pada Silver/Gold layer tidak boleh melebihi 15 menit dari event occurrence.

#### Permasalahan Produksi (Production Bottlenecks)
1. **The "Small Files" Problem**: Streaming micro-batch menulis puluhan ribu file berukuran 1–5 MB setiap jam ke object storage. Akibatnya, query metadata di S3 mengalami throttling (HTTP 503 Slow Down), dan Spark Driver crash akibat GC Pause berkepanjangan saat mengompilasi Partisi File (`OutOfMemoryError: Java heap space`).
2. **Extreme Data Skew**: Agregasi metrik berdasarkan `merchant_id` mengalami kegagalan. Merchant raksasa (Top 0.01%) memproses jutaan transaksi per jam, menyebabkan 1 task di Spark Executor berjalan selama 4 jam sementara 99% task lainnya selesai dalam 2 menit.
3. **Concurrent Mutation Conflicts**: Batch update reguler untuk reconciliations bertabrakan dengan continuous real-time ingestion, memicu `ConcurrentModificationException` pada Delta transaction log.

#### Solusi Rekayasa Data
1. **Auto-Compaction & Optimized Writes**:
   Mengonfigurasi Spark Structured Streaming dengan *auto-compaction* dan *bin-packing*:
   ```python
   spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")
   spark.conf.set("spark.databricks.delta.autoOptimize.autoCompact.enabled", "true")
   ```
   Menjadwalkan job vacuuming dan compaction off-peak harian:
   ```sql
   OPTIMIZE silver_orders ZORDER BY (merchant_id, event_timestamp);
   VACUUM silver_orders RETAIN 168 HOURS; -- Retensi snapshot 7 hari
   ```
2. **Mitigasi Skew dengan Salting & Adaptive Query Execution (AQE)**:
   Mengaktifkan Spark AQE:
   ```python
   spark.conf.set("spark.sql.adaptive.enabled", "true")
   spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
   spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
   spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256MB")
   ```
   Pada ETL joins deterministik tanpa AQE, diterapkan teknik *Key Salting*:
   ```python
   # Menambahkan nilai salt acak 0-19 ke key transaksi
   salted_df = raw_df.withColumn("salted_merchant_id", 
       F.concat(F.col("merchant_id"), F.lit("_"), F.floor(F.rand() * 20))
   )
   ```
3. **Isolated Partition Merging & OCC Isolation**:
   Isolasi transaksi tulis dengan membatasi cakupan `MERGE` conditions ke partisi aktif (`event_date >= current_date() - 2`), menurunkan collision rate dari 18.4% menjadi 0%.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian & Batasan | Mitigasi / Use-Case Optimal |
| :--- | :--- | :--- | :--- |
| **Compute-Storage Disaggregation** (S3/GCS + EMR/Databricks) | Scaling komputasi dan penyimpanan independen; elastisitas biaya tinggi; zero idle compute cost. | Latensi jaringan lebih tinggi dibanding local NVMe disk; potensi API rate-limits pada storage tier. | Implementasikan aggressive aggressive in-memory caching, read-ahead buffer, dan Parquet dictionary encoding. |
| **High Frequency Compaction** (e.g., tiap 5 menit) | Query latency data consumer sangat cepat; file count rendah; metadata footprint minimal. | Konsumsi resource komputasi membengkak; biaya rewrite storage (write-amplification) sangat tinggi. | Gunakan dual-tier approach: Micro-batch append-only pada buffer table, compact ke silver layer setiap 1-2 jam. |
| **Z-Order Clustering** | Pruning multi-dimensi efisien tanpa ledakan partisi direktori fisik. | Biaya komputasi pemilahan (multidimensional sorting) via Hilbert Space Filling Curve sangat berat saat write. | Batasi Z-Ordering hanya pada 2–4 kolom dengan kueri intensif di gold layer. Hindari Z-Ordering pada bronze layer. |
| **Eager vs. Lazy Schema Evolution** | Eager (rewrite file lama): format konsisten 100%. Lazy: proses tulis instan tanpa rewrite. | Eager: IO overhead masif. Lazy: pembacaan downstream menanggung compute overhead saat reconciliasi skema. | Gunakan Lazy Evolution (metadata-only update) didukung format Apache Iceberg / Delta Lake modern. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Executor OOM: `java.lang.OutOfMemoryError: Java heap space`
- **Root Cause**: Driver mengirim broadcast join melebihi ambang batas (`spark.sql.autoBroadcastJoinThreshold`), atau executor buffer kehabisan memori akibat data skew ekstrem pada join/window function.
- **Tindakan Troubleshooting**:
  1. Periksa Spark UI -> Stage Details -> Task Event Timeline. Jika ada satu task memproses byte 10x lebih besar dari median, data skew terjadi.
  2. Naikkan `spark.executor.memoryOverhead` ke minimal 15-20% dari total executor memory jika log mengindikasikan JVM dibunuh oleh Yarn/K8s NodeManager (OOMKilled).
  3. Matikan broadcast join sementara: `spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")` untuk verifikasi stabilitas.

#### 2. Shuffle Spill to Disk: Performa Degradasi 10x Lipat
- **Gejala**: Spark UI menampilkan metrik **"Spill (Memory)"** dan **"Spill (Disk)"** bernilai puluhan Gigabyte pada stage Shuffle.
- **Root Cause**: Partisi shuffle terlalu sedikit (`spark.sql.shuffle.partitions` default 200 tidak mencukupi untuk volume data multi-gigabyte/terabyte). Data tidak muat di memory pool executor sehingga tumpah ke disk lokal.
- **Solusi**:
  Hitung target partisi optimal:
  $$\text{Partitions} = \frac{\text{Input Stage Shuffle Data Size}}{128 \text{ MB}}$$
  Aktifkan Dynamic Partition Coalescing:
  ```python
  spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
  spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "134217728") # 128 MB
  ```

#### 3. Spark Driver OOM via `.collect()`
- **Anti-Pattern**: Memanggil `df.collect()` atau `df.toPandas()` pada dataset hasil agregasi yang kardinalitasnya masih sangat besar.
- **Solusi**: Simpan ke persistent target layer (`.write.save()`) atau gunakan `.take(n)` / `.limit(n)` jika hanya memerlukan sampling data inspeksi.

---

### 11. Best Practices (Production Checklist)

- [ ] **Alokasi Sumber Daya Executor**: Konfigurasikan maksimal 5 core per executor (`--executor-cores 5`) untuk membatasi overhead thread contention dan GC pauses pada JVM.
- [ ] **Adaptive Query Execution (AQE)**: Pastikan `spark.sql.adaptive.enabled = true` aktif di level cluster global.
- [ ] **Serializer Kryo**: Gunakan Kryo Serializer (`org.apache.spark.serializer.KryoSerializer`) dan daftarkan custom class jika menggunakan strongly-typed Scala Datasets.
- [ ] **Partition Sizing**: Pertahankan ukuran file fisik output di kisaran 128 MB – 512 MB. Hindari partisi direktori bernilai lebih dari 50.000 partisi pada catalog.
- [ ] **Idempotent Writers**: Tulis seluruh state transformatif menggunakan deterministik unique transaction identifier atau atomic write-replace partitions.
- [ ] **Metadata Vacuum Maintenance**: Jadwalkan routine `VACUUM` job dengan safety delay (minimal `spark.databricks.delta.vacuum.parallelDelete.enabled = true` dan rentang retensi $\ge 168$ jam) agar concurrent long-running readers tidak crash.
- [ ] **Dynamic Allocation**: Aktifkan `spark.dynamicAllocation.enabled = true` dengan batas min/max executors yang diuji terhadap batas kapasitas kuota worker platform.

---

### 12. Hands-on Practice (Implementasi Bertahap)

Instruksi praktikum mandiri. Simpan seluruh artefak ke direktori project: `hands-on/m02/`.

#### Langkah 1: Persiapan Environment
Buat file `hands-on/m02/requirements.txt`:
```text
pyspark==3.5.1
delta-spark==3.2.0
```
Instal environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r hands-on/m02/requirements.txt
```

#### Langkah 2: Script Eksekusi & Validasi Engine Plan
Buat script `hands-on/m02/advanced_engine_lab.py`:
```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
import os

def run_lab():
    spark = SparkSession.builder \
        .appName("EngineOptimizationLab") \
        .master("local[4]") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()

    base_dir = "/tmp/hands_on_m02"
    os.makedirs(base_dir, exist_ok=True)
    table_path = f"{base_dir}/delta_metrics"

    # Step A: Ingest Base Skewed Data
    print("[+] Generating Synthetic Data with Skew...")
    df = spark.range(0, 5000000) \
        .withColumn("key", F.when(F.col("id") % 100 == 0, "SKEW_KEY").otherwise(F.concat(F.lit("KEY_"), F.col("id")))) \
        .withColumn("metric_val", F.rand() * 100)

    # Step B: Write as Delta
    print("[+] Writing Base Delta Table...")
    df.write.format("delta").mode("overwrite").save(table_path)

    # Step C: Execute Complex Aggregation & Profile Plan
    print("[+] Executing Analytical Query with Plan Inspection...")
    delta_df = spark.read.format("delta").load(table_path)
    
    agg_df = delta_df.filter(F.col("metric_val") > 50.0) \
                     .groupBy("key") \
                     .agg(F.avg("metric_val").alias("avg_metric"), F.count("id").alias("total_rows"))

    agg_df.explain(mode="cost")
    agg_df.write.format("noop").mode("overwrite").save() # Force trigger execution graph

    print("[SUCCESS] Hands-on pipeline run completed.")
    spark.stop()

if __name__ == "__main__":
    run_lab()
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan script dan simpan log plan output:
```bash
python hands-on/m02/advanced_engine_lab.py > hands-on/m02/execution_plan_output.txt
cat hands-on/m02/execution_plan_output.txt | grep -A 5 "Physical Plan"
```

---

### 13. Exercise (Latihan Terstruktur)

#### Level Easy
1. Modifikasi konfigurasi spark di `hands-on/m02/advanced_engine_lab.py` untuk menonaktifkan Whole-Stage CodeGen (`spark.sql.codegen.wholeStage = false`). Bandingkan durasi runtime eksekusi job menggunakan fungsi timer Python (`time.time()`).
2. Tuliskan query yang mengekstrak metadata version history dari Delta Table menggunakan fungsi `DeltaTable.forPath().history()`.

#### Level Medium
1. Simulasikan insiden *Small File Problem*: Tulis sebuah script yang menyimpan DataFrame 500.000 baris ke dalam 1000 partisi file kecil.
2. Tuliskan logic script kedua menggunakan method `.optimize().executeCompaction()` untuk menggabungkan file-file tersebut menjadi file optimal berukuran $\ge 128\text{ MB}$.

#### Level Hard
1. Buat custom Spark pipeline yang menangani skenario **Late-Arriving Data** pada transaksi finansial. Jika data terlambat datang $> 3$ hari kalender, data tersebut harus diarahkan ke tabel `silver_transactions_quarantine`, tetapi jika data tiba $\le 3$ hari, jalankan `MERGE INTO` langsung ke tabel `silver_transactions_active`. Pipeline harus sepenuhnya idempotent tanpa membaca keseluruhan snapshot partisi lama.

---

### 14. Challenge (Studi Kasus Kompleks)

**Skenario**:
Sebuah platform streaming multimedia memiliki tabel transaksi stream history sebesar 2.5 Petabyte di S3 dalam format Delta Lake (`fact_user_streams`).
Karakteristik:
- Skema: `user_id` (UUID), `media_id` (String), `stream_duration_sec` (Int), `timestamp` (Timestamp), `country_code` (String).
- Beban: 80% analitik memfilter rentang 30 hari terakhir dengan filter spesifik `country_code` dan `media_id`.
- Setiap tengah malam, batch job reconcile masuk untuk mengoreksi agregasi durasi pemutaran berdasarkan log server CDN offline.
- Terjadi bottleneck parah: Job harian mengalami kegagalan *Executor Lost Failure: Heartbeat timed out* dan *Out of Memory Spill (Disk: 1.8 TB)* pada fase join data harian baru dengan riwayat data 3 tahun.

**Tugas Anda (Arsitektural & Implementasi)**:
1. Rancang arsitektur strategi partisi dan data layout (Partition Key vs. Z-Order vs. Bucket IDs) agar query time-travel dan analitik harian tidak men-scan partisi data multi-tahun.
2. Formulasikan pseudocode atau PySpark script yang mengeksekusi merge reconciliation data tanpa memicu Shuffle Join ke seluruh 2.5 PB data, memanfaatkan **Dynamic File Pruning** dan **Partition Slicing**.
3. Buat failure recovery strategy jika driver cluster mengalami terminated status di tengah-tengah atomic commit Delta Lake.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic Concepts
1. Apa fungsi utama dari Catalyst Optimizer dalam Apache Spark?
   - A. Menjaga koneksi pool JDBC tetap hidup.
   - B. Mentransformasikan logical query plan menjadi physical execution plan yang efisien melalui rule-based dan cost-based optimization.
   - C. Mengalokasikan RAM fisik secara langsung di level Linux OS Kernel.
   - D. Menghapus file fisik di storage secara otomatis.
   *Jawaban*: **B**.

2. Apa perbedaan mendasar antara Whole-Stage Code Generation dan execution model berbasis Volcano Iterator klasik?
   - A. Volcano Iterator mengompilasi bytecode ke assembly native, sedangkan Whole-Stage tidak.
   - B. Volcano Iterator mengeksekusi satu baris per interface call function (`next()`), memicu context switching CPU cache tinggi. Whole-Stage CodeGen meratakan loop pemrosesan dalam satu frame stack.
   - C. Whole-Stage CodeGen membutuhkan database relasional eksternal.
   - D. Tidak ada perbedaan performa signifikan antara keduanya.
   *Jawaban*: **B**.

3. Di mana informasi snapshot ACID commit Delta Lake disimpan secara fisik?
   - A. Di memory volatile Driver node saja.
   - B. Pada direktori root tabel di dalam subfolder `_delta_log/` dalam bentuk file commit JSON dan Checkpoint Parquet.
   - C. Pada sistem file lokal di masing-masing worker node.
   - D. Pada service Apache ZooKeeper.
   *Jawaban*: **B**.

4. Apa dampak negatif langsung dari fenomena "Small Files Problem" pada object storage?
   - A. Biaya penyimpanan per GB menjadi 10x lipat lebih mahal.
   - B. Beban metadata scan berlebihan pada Spark Driver dan memicu HTTP 503 throttling API Object Storage.
   - C. Data tersimpan otomatis terhapus setelah 24 jam.
   - D. Enkripsi data tidak dapat diaktifkan.
   *Jawaban*: **B**.

5. Komponen memori Spark apa yang secara spesifik digunakan untuk menampung hash join tables dan buffer sorting shuffle?
   - A. Reserved System Memory.
   - B. User Memory Pool.
   - C. Spark Execution Memory.
   - D. Spark Metadata Cache Pool.
   *Jawaban*: **C**.

#### Bagian B: Intermediate Engineering
6. Manakah konfigurasi Adaptive Query Execution (AQE) yang secara khusus bertugas memecah skewed task yang besar menjadi sub-partisi yang lebih kecil?
   - A. `spark.sql.adaptive.coalescePartitions.enabled`
   - B. `spark.sql.adaptive.skewJoin.enabled`
   - C. `spark.sql.adaptive.localShuffleReader.enabled`
   - D. `spark.sql.files.maxPartitionBytes`
   *Jawaban*: **B**.

7. Mengapa operasi Z-Ordering lebih efektif dibandingkan multi-column direct physical partitioning pada tabel yang memiliki puluhan kolom filter?
   - A. Z-Ordering mengubah format data dari Parquet menjadi teks terkompresi.
   - B. Direct physical partitioning berlebihan memicu ledakan jumlah direktori folder (*over-partitioning*), sedangkan Z-Ordering menata urutan data internal file tanpa memecah direktori.
   - C. Z-Ordering tidak memerlukan resource CPU saat penulisan data.
   - D. Z-Ordering mengizinkan penghapusan primary key.
   *Jawaban*: **B**.

8. Kapan optimasi Broadcast Hash Join **tidak** boleh digunakan dalam skenario produksi?
   - A. Saat salah satu dataset berukuran sangat kecil (< 10 MB).
   - B. Ketika dimensi dataset yang di-join melebihi kapasitas memori driver JVM, yang berpotensi memicu Driver `OutOfMemoryError`.
   - C. Saat query tidak mengandung klausa aggregation.
   - D. Ketika data disimpan dalam storage SSD NVMe.
   *Jawaban*: **B**.

9. Bagaimana protokol Optimistic Concurrency Control (OCC) pada Open Table Formats menangani konflik penulisan antara dua job bersamaan?
   - A. Job pertama mengunci cluster secara eksklusif (*Distributed Lock*) sehingga job kedua langsung dibatalkan (fail immediately).
   - B. Format mengizinkan file ditimpa langsung tanpa validasi.
   - C. Format memeriksa apakah versi commit log telah berubah. Jika ada file konflik yang dimodifikasi oleh job lain, engine me-replay transaksi atau melempar exceptions serializable validation.
   - D. OCC mengarahkan data kedua ke folder sementara dan menghapusnya otomatis.
   *Jawaban*: **C**.

10. Apa kegunaan utama dari metadata column pruning dan predicate pushdown pada storage format Parquet?
    - A. Membaca header dan footers file Parquet untuk melompati (*skip*) block data page tanpa harus men-dekompresi seluruh file ke RAM.
    - B. Mengubah tipe data string menjadi integer secara implisit.
    - C. Memisahkan data null ke server database terpisah.
    - D. Menghindari pembuatan transactional commit log.
    *Jawaban*: **A**.

#### Bagian C: Production Scenarios & Root Cause Analysis
11. **Skenario Kasus 1**:
    Sebuah job Apache Spark mengalami kegagalan dengan pesan error: `Container killed by YARN for exceeding memory limits. 16.5 GB of 16 GB physical memory used. Consider boosting spark.yarn.executor.memoryOverhead.`
    Analisis log menunjukkan bahwa job menggunakan UDF Python non-vektor (`@udf`) untuk deserialisasi string JSON kompleks.
    **Apa akar masalah teknisnya dan solusi permanen yang paling tepat?**
    - A. Root cause: Storage memory default terlalu kecil. Solusi: Naikkan `spark.storage.memoryFraction` menjadi 0.9.
    - B. Root cause: UDF Python berjalan di luar JVM (pada Python worker process tersendiri). Data di-serialize bolak-balik antara JVM dan Python Runtime via socket, melipatgandakan alokasi native memory di luar kalkulasi Heap JVM. Solusi: Gunakan Native Built-in Spark SQL functions (`from_json`) atau Pandas UDF berbasis Apache Arrow untuk meniadakan copy overhead memory.
    - C. Root cause: Driver kehabisan koneksi network pool. Solusi: Ganti driver node instance type.
    - D. Root cause: G1GC Pause time melebihi limit. Solusi: Matikan Garbage Collector.
    *Jawaban*: **B**.

12. **Skenario Kasus 2**:
    Pipeline Delta Lake Silver memproses update transaksi streaming. Setiap kali dilakukan eksekusi perintah SQL `MERGE INTO`, performa pipeline semakin lambat dari hari ke hari: hari ke-1 memakan waktu 40 detik, hari ke-30 memakan waktu 45 menit untuk ukuran batch yang sama.
    **Identifikasi sumber degradasi performa ini.**
    - A. Ukuran RAM server secara fisik menurun performanya akibat overheating hardware.
    - B. Penumpukan file metadata transaksi (`_delta_log/*.json`) yang masif dan ledakan small files di disk karena ketiadaan proses snapshot checkpointing, file compaction, dan `VACUUM`. Engine menghabiskan mayoritas waktu untuk me-listing ribuan file di storage.
    - C. Delta Lake tidak mendukung query merge berkelanjutan.
    - D. Format kompresi snappy kadaluarsa secara runtime.
    *Jawaban*: **B**.

13. **Skenario Kasus 3**:
    Sebuah analytical query Trino/Spark yang membaca tabel Iceberg berukuran 50 TB gagal menyelesaikan tugasnya karena membaca miliaran baris data, padahal query secara eksplisit memfilter event 1 jam tertentu (`WHERE event_timestamp BETWEEN '2024-05-01 01:00:00' AND '2024-05-01 02:00:00'`). Tabel tersebut dipartisi berdasarkan `month(event_timestamp)`.
    **Mengapa partition pruning tidak bekerja efektif dan langkah arsitektural apa yang wajib dilakukan?**
    - A. Partisi bulanan terlalu coarse-grained (kasar), sehingga filter 1 jam tetap memaksa engine memindai seluruh data dalam 1 bulan penuh. Solusi: Desain partisi Iceberg menggunakan hidden identity transform level harian (`day(event_timestamp)`) digabungkan dengan sorting internal file data berdasarkan `event_timestamp`.
    - B. Trino tidak bisa membaca file Iceberg. Solusi: Ganti format tabel kembali ke format text CSV.
    - C. Timestamp pada SQL query harus dikonversi menjadi integer epoch milidetik.
    - D. Query harus menggunakan `SELECT *` tanpa limit.
    *Jawaban*: **A**.

---

### 16. Summary
- Pemahaman siklus internal distributed engine (Catalyst Analyzer, Optimizer, Cost-Based Planning, dan Whole-Stage CodeGen pada Project Tungsten) adalah fondasi mutlak dalam mengeliminasi bottleneck performa eksekusi pipelines data skala besar.
- Modern Lakehouse Architecture menjembatani batasan fungsional object storage melalui Open Table Formats (seperti Delta Lake dan Apache Iceberg) yang menghadirkan kapabilitas ACID transactions, time travel, concurrency control, dan optimasi data skipping.
- Stabilitas arsitektur data produksi sangat bergantung pada mitigasi proaktif terhadap tiga musuh utama distributed systems: Data Skew, Shuffle Memory Spills, dan Small Files Problem.
- Pemilihan partisi direktori yang seimbang dikombinasikan dengan strategi layout internal (Z-Ordering/Clustering) dan jadwal pemeliharaan metadata periodik (Compaction & Vacuuming) merupakan prasyarat non-negosiasi untuk menjaga SLA latensi data enterprise tetap optimal.