# KURIKULUM FORWARD-DEPLOYED ENGINEER (FDE)
## TRACK: 06-Architecture-and-System-Design
### BAB 03: Data Engineering Lapangan & Data Mesh Skala Besar
#### MODUL 01: Real-time & Batch Pipelines di Infrastruktur Klien, Schema Drift Handling, Big Data Federation, dan Data Quality Validation

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: `FDE-ARCH-0301`
* **Nama Modul**: Data Engineering Lapangan & Data Mesh Skala Besar: Real-time & Batch Pipelines di Infrastruktur Klien, Schema Drift Handling, Big Data Federation, Data Quality Validation
* **Track**: `06-Architecture-and-System-Design`
* **Target Role**: Forward-Deployed Engineer (FDE), Lead Data Architect, Field Solutions Architect
* **Tingkat Kesulitan**: Tingkat Lanjut (Advanced)
* **Estimasi Waktu Belajar**: 12 Jam (Teori, Arsitektur Sistem, Analisis Kode, Lab Mandiri)
* **Prasyarat**:
  * Penguasaan mendalam terhadap Apache Spark (PySpark/Scala) dan Apache Kafka.
  * Pemahaman tentang penyimpanan berbasis objek dan format file kolumnar (*Parquet*, *ORC*), serta teknologi open table (*Delta Lake*, *Apache Iceberg*).
  * Pemahaman arsitektur terdistribusi (*distributed consensus*, partitioning, network topologies).
  * Pengalaman kerja dengan SQL tingkat lanjut dan arsitektur basis data relasional serta NoSQL.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Merancang dan Menggelar Arsitektur Pipeline Data Hibrida**: Mengonstruksi pipeline *batch* dan *real-time streaming* terpadu (Lambda/Kappa/Delta Engine) langsung di atas infrastruktur klien yang bervariasi (on-premise bare-metal, air-gapped, sovereign cloud, atau multi-cloud) dengan memperhitungkan keterbatasan komputasi dan isolasi jaringan.
2. **Mitigasi *Schema Drift* Secara Otonom**: Mengimplementasikan mekanisme deteksi, adaptasi, dan karantina perubahan skema (*backward*, *forward*, dan *full compatibility*) menggunakan schema registries, Open Table Formats (*mergeSchema* pada Delta Lake/Iceberg), serta *Dead Letter Queues* (DLQ) tanpa menghentikan pemrosesan data real-time.
3. **Mengoperasikan Big Data Federation Antar-Silo**: Mengonfigurasi engine federasi query (*Trino/Presto*) untuk mengeksekusi analisis terdistribusi berlatensi rendah melintasi silo data heterogen klien (RDBMS warisan, data lake berbasis S3/MinIO, Elasticsearch, dan data warehouse) tanpa memindahkan data mentah secara prematur (*zero-copy architecture*).
4. **Menerapkan *Data Quality Gates* & Kontrak Data**: Membangun sistem validasi kualitas data berbasis sirkuit pemutus (*circuit breaker*) dan gerbang validasi deterministik (*Great Expectations*, *Soda Core*) guna menegakkan Service Level Objectives (SLO) serta Service Level Indicators (SLI) data langsung di lapisan penyerapan (*ingestion layer*).
5. **Mengadopsi Prinsip Data Mesh di Lapangan**: Mentranslasikan paradigma data terpusat klien yang kaku menjadi arsitektur domain-driven terdesentralisasi, memperlakukan data sebagai produk (*Data-as-a-Product*), dan mengonfigurasi tata kelola komputasi terfederasi (*Federated Computational Governance*).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
[Infrastruktur Klien Heterogen & Air-Gapped]
       │
       ├── CDC & Ingestion Layer
       │     ├── Debezium / Kafka Connect
       │     └── Confluent Schema Registry (Schema Compatibility Modes)
       │
       ├── Processing Engine (Hybrid Batch & Streaming)
       │     ├── Apache Spark Structured Streaming (Micro-batch / Continuous)
       │     └── State Management & Checkpointing (RocksDB, HDFS/S3-compatible)
       │
       ├── Schema Evolution & Drift Isolation
       │     ├── Delta Lake / Apache Iceberg (ACID, Time-travel, Schema Merging)
       │     └── Quarantine / Dead-Letter-Queue (DLQ) Pattern
       │
       ├── Data Quality Circuit Breakers
       │     ├── In-line Assertion Engine (Soda Core / Great Expectations)
       │     └── Anomaly Detection & Auto-Triage Quarantine
       │
       └── Distributed Consumption & Federation (Data Mesh)
             ├── Trino / Starburst Enterprise (Federated Catalogs: Hive, Postgres, Mongo)
             └── Domain Data Products & Federated Computational Governance
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Sebagai seorang *Forward-Deployed Engineer* (FDE), Anda jarang mendesain sistem dari nol di atas infrastruktur *cloud-native* yang bersih dan seragam. Anda dikirim langsung ke garis depan sistem klien: bank multinasional dengan mainframe warisan dan kluster Hadoop era 2012, operator telekomunikasi dengan regulasi residensi data yang ketat, atau instansi pertahanan dengan lingkungan *air-gapped* tanpa koneksi internet sama sekali.

Masalah mendasar yang dihadapi di lapangan:
1. **Gravitasi Data (*Data Gravity*)**: Klien memiliki petabyte data yang terjebak dalam puluhan silo terisolasi. Mengunggah atau memindahkan semua data ini ke satu data lake/warehouse terpusat sering kali dilarang oleh regulasi, memakan bandwidth, atau memakan waktu bertahun-tahun.
2. **Kerapuhan Pipeline (*Pipeline Fragility*) Akibat Schema Drift**: Di sistem monolitik klien, tim internal mereka dapat mengubah tipe data kolom, mengganti nama field, atau menyisipkan *nested array* baru ke basis data transaksional tanpa pemberitahuan. Pipeline tradisional akan langsung mengalami kegagalan *runtime* fatal (*crash*), menyebabkan *pipeline downtime* berhari-hari.
3. **Ketiadaan Validasi Kualitas Data Aktif**: Pola pikir lama mengandalkan pengujian data downstream setelah laporan BI rusak. FDE harus menerapkan validasi aktif pada ingress: menghentikan data busuk sebelum mencemari model operasional downstream (*shift-left data quality*).
4. **Tuntutan Operasional Real-Time vs Realitas Batch**: Klien sering kali menuntut kapabilitas analitik dan inferensi ML real-time, namun sistem pencatat (*systems of record*) mereka hanya mengekspor dump flat-file harian melalui SFTP batch.

Menguasai arsitektur federasi, penanganan skema elastis, dan validasi data skala enterprise adalah pembeda antara instalasi software lapangan yang gagal total dan deployment mission-critical yang stabil di lingkungan paling menantang.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Data Mesh Lapangan
Data Mesh adalah paradigma sosio-teknikal terdesentralisasi yang mengubah orientasi arsitektur data dari data lake monolitik terpusat menjadi ekosistem berorientasi domain. Dalam konteks FDE:
* **Domain Ownership**: Tim bisnis klien memiliki tanggung jawab penuh atas data transaksional mereka.
* **Data as a Product (DaaP)**: Data disajikan bukan sebagai file mentah, melainkan sebagai produk terkurasi yang dilengkapi metadata, dokumentasi, *access control*, dan jaminan SLO/SLA.
* **Self-serve Data Platform**: FDE menyediakan platform komputasi dan penyimpanan agnostik infrastruktur yang memungkinkan tim domain mendaftarkan, mengeksekusi, dan melayani data produk mereka sendiri.
* **Federated Computational Governance**: Tata kelola otomatis (akses, masking, enkripsi, dan validasi kualitas) dieksekusi secara global oleh platform, bukan manual oleh panitia tata kelola.

### 2. Schema Drift Handling
Perubahan struktur data sumber secara sepihak seiring berjalannya waktu. Penanganan drift mencakup:
* **Schema Evolution**: Penambahan kolom baru secara transparan tanpa merusak skema yang sudah tersimpan (*additive evolution*).
* **Schema Enforcement**: Pencegahan mutasi skema ilegal (seperti perubahan tipe data string menjadi integer, atau penghapusan kolom wajib) agar tidak merusak downstream jobs.
* **Quarantine Pipeline**: Pemisahan otomatis record yang tidak kompatibel ke dalam tabel karantina untuk rekonsiliasi asinkron, sementara record yang valid terus diproses.

### 3. Big Data Federation
Mekanisme abstraksi komputasi kueri yang mengeksekusi kueri terdistribusi (Distributed ANSI SQL) di berbagai sumber data heterogen tanpa melakukan relokasi data fisik. Engine seperti Trino memisahkan lapisan komputasi (*stateless query workers*) dari lapisan penyimpanan (*storage connectors*), mendorong predikat (*predicate pushdown*) sedekat mungkin ke sumber data fisik.

### 4. Data Quality Validation (Circuit Breakers)
Pendekatan deterministik dalam rekayasa data di mana setiap batch atau micro-batch divalidasi terhadap kontrak data (*Data Contracts*). Jika ambang batas pelanggaran kualitas data (*error threshold*) terlampaui, pemutus sirkuit (*circuit breaker*) memutus pemrosesan aliran data, membunyikan alarm peringatan, dan memblokir materialisasi ke downstream lakehouse.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Alur Kerja Pemrosesan Pipeline Lapangan Terpadu

```text
[CDC: Debezium Engine] ──(Kafka Topic)──> [Spark Structured Streaming]
                                                    │
                   ┌────────────────────────────────┴────────────────────────────────┐
                   ▼                                                                 ▼
      [Schema Drift Validator]                                         [Data Quality Engine]
   (Registry Compatibility Check)                                      (Great Expectations)
                   │                                                                 │
    ┌──────────────┴──────────────┐                                   ┌──────────────┴──────────────┐
    ▼                             ▼                                   ▼                             ▼
[Valid Payload]            [Schema Mutated]                    [Passed Assertions]         [Failed Assertions]
    │                             │                                   │                             │
    │                      [DLQ / Quarantine]                         ▼                             ▼
    └──────────────┬──────────────┘                             [Delta Lake Engine]          [DLQ / Alerting]
                   │                                             (Bronze -> Silver)
                   ▼                                                  │
         [Dynamic Merge Engine]                                       ▼
        (.option("mergeSchema"))                             [Trino Query Federation]
                   │                                          (Cross-domain Access)
                   ▼
         [Delta Lake / Iceberg]
```

#### Langkah 1: Penangkapan Perubahan Data (Change Data Capture / CDC)
Data diekstrak langsung dari transaction log basis data klien (seperti Oracle Redo Log, PostgreSQL WAL, MySQL Binlog) menggunakan Debezium. Pesan dikonversi menjadi payload biner berformat Apache Avro atau Protobuf, yang dikaitkan dengan Schema Registry ID unik pada header pesan Kafka.

#### Langkah 2: Evaluasi Kompatibilitas Skema (Schema Compatibility Policy)
Sebelum diurai, consumer Spark memeriksa integritas skema:
* **BACKWARD**: Konsumen dengan skema baru dapat membaca data yang diproduksi oleh skema lama.
* **FORWARD**: Konsumen dengan skema lama dapat membaca data yang diproduksi oleh skema baru.
* **FULL**: Mendukung kedua arah kompatibilitas di atas.
Jika ada pesan Kafka yang melanggar kontrak skema, pesan tersebut secara transparan dialihkan ke *Dead Letter Queue* (DLQ) bersama dengan metadata stack trace dan payload aslinya.

#### Langkah 3: Eksekusi Ingesti Streaming & Adaptive Schema Merging
Spark Structured Streaming membaca micro-batch dari Kafka. Jika kolom baru ditambahkan pada sumber (dan memenuhi kompatibilitas evolusi), Delta Lake mengaktifkan fitur `mergeSchema = true`:
$$\text{Schema}_{\text{Final}} = \text{Schema}_{\text{Existing}} \cup \text{Schema}_{\text{Incoming}}$$
Format penyimpanan akan menulis file Parquet baru dengan footer skema terkini tanpa menulis ulang (*rewriting*) file Parquet historis yang sudah ada di penyimpanan objek.

#### Langkah 4: Validasi Kualitas Data Lapangan (In-line Quality Gate)
Sebelum data dinaikkan statusnya dari lapisan *Bronze* (mentah) ke lapisan *Silver* (tervalidasi dan terstandarisasi), mesin validasi (Great Expectations / Soda Core / Native Spark Assertions) mengevaluasi metrik kontraktual:
* Kelengkapan (*Completeness*): $\text{Null Count}(C_i) == 0$ untuk kunci utama.
* Ketepatan Rentang Nilai (*Validity*): $\text{Value}(C_j) \in [\text{Min}, \text{Max}]$.
* Keunikan (*Uniqueness*): $\text{Count Distinct}(K) == \text{Total Rows}$.

Bila rasio anomali melebihi ambang batas toleransi (misalnya $> 0.01\%$), *pipeline circuit breaker* trip: batch dihentikan, data buruk dipindahkan ke tabel karantina (`quarantine_silver_table`), dan laporan diagnostik dikirim ke Slack/PagerDuty.

#### Langkah 5: Federasi Kueri Melalui Trino
Di atas lapisan penyimpanan fisik, Trino dikonfigurasi dengan beberapa *Connector*:
* `connector.name=delta` untuk mengakses lakehouse internal.
* `connector.name=postgresql` untuk basis data transaksional cabang lokal.
* `connector.name=oracle` untuk sistem pembukuan legacy kantor pusat.

Koordinator Trino mengurai query terfederasi, menghasilkan *Abstract Syntax Tree* (AST), mengoptimalkan eksekusi dengan *cost-based optimizer* (CBO), lalu mendistribusikan *splits* tugas komputasi secara paralel ke worker node di seluruh jaringan klien.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

Berikut adalah topologi arsitektur sistem federasi data terdistribusi dan *resilient streaming pipeline* yang dirancang untuk infrastruktur klien hibrida/air-gapped:

```text
+----------------------------------------------------------------------------------------------------+
|                                    INFRASTRUKTUR SISTEM KLIEN                                      |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [Transaksional On-Premise]            [Legacy Core Banking]          [Third-party API / File SFTP] |
|   PostgreSQL / MySQL                    Oracle RAC Enterprise          CSV / JSON Unggahan Harian   |
|         │                                       │                                   │              |
|         ▼ (Write Ahead Log)                     ▼ (Redo Logs)                       ▼ (Inotify)    |
|   +───────────────+                      +───────────────+                  +───────────────+      |
|   | Debezium CDC  |                      | Debezium CDC  |                  | File Ingestion|      |
|   | Connect Node  |                      | Connect Node  |                  | Daemon / Pod  |      |
|   +───────┬───────+                      +───────┬───────+                  +───────┬───────+      |
|           │                                      │                                  │              |
|           └───────────────────┐                  │                                  │              |
|                               ▼                  ▼                                  ▼              |
|                     +───────────────────────────────────────────────+                              |
|                     |        APACHE KAFKA CLUSTER / EVENT LOG       |                              |
|                     |        (Penyimpanan Log Data Terdistribusi)   |                              |
|                     +───────────────────────┬───────────────────────+                              |
|                                             │                                                      |
|                                             │ Membaca Schema Metadata                              |
|                                             ▼                                                      |
|                             +───────────────────────────────+                                      |
|                             |   APACHE AVRO / SCHEMA REGISTRY|                                     |
|                             |   (Kompatibilitas: FULL/BACKWARD) |                                  |
|                             +───────────────┬───────────────+                                      |
|                                             │                                                      |
|                                             ▼                                                      |
|                     +───────────────────────────────────────────────+                              |
|                     |        APACHE SPARK STREAMING ENGINE          |                              |
|                     |        (Workers Terdistribusi di Lapangan)    |                              |
|                     +───────────────────────┬───────────────────────+                              |
|                                             │                                                      |
|                   Pemeriksaan Skema & Evaluasi Mutasi Kolom                                        |
|                                             │                                                      |
|                         ┌───────────────────┴───────────────────┐                                  |
|                         │                                       │                                  |
|            [Skema Rusak / Melanggar]               [Skema Valid / Berevolusi]                      |
|                         │                                       │                                  |
|                         ▼                                       ▼                                  |
|               +───────────────────+                   +───────────────────+                        |
|               |  DEAD LETTER QUEUE|                   | In-Memory Engine  |                        |
|               |  (DLQ / Kafka Top)|                   | Quality Assertions|                        |
|               +─────────┬─────────+                   +─────────┬─────────+                        |
|                         │                                       │                                  |
|                         ▼                               ┌───────┴───────┐                          |
|               +───────────────────+                     │               │                          |
|               |  Karantina S3/HDFS|            [Pelanggaran SLO]   [Lolos Uji]                     |
|               |  (Analisis Manual)|                     │               │                          |
|               +───────────────────+                     ▼               ▼                          |
|                                               +───────────────────+ +───────────────────+          |
|                                               | Quarantine Table  | | Delta Lake Bronze |          |
|                                               | (Circuit Tripped) | | (mergeSchema=true)|          |
|                                               +───────────────────+ +─────────┬─────────+          |
|                                                                               │                    |
|                                                                               ▼                    |
|                                                                     +───────────────────+          |
|                                                                     | Delta Lake Silver |          |
|                                                                     | (Clean Domain DaaP)|         |
|                                                                     +─────────┬─────────+          |
|                                                                               │                    |
|                                                                               ▼                    |
| +─────────────────────────────────────────────────────────────────────────────┴──────────────────+ |
| |                                TRINO DISTRIBUTED QUERY ENGINE                                    | |
| |                                                                                                 | |
| |   +──────────────────+      +──────────────────+      +──────────────────+     +──────────────+ | |
| |   | Connector: Delta |      | Connector: Oracle|      | Connector: Mongo |     |Connector: PG | | |
| |   +────────┬─────────+      +────────┬─────────+      +────────┬─────────+     +──────┬───────+ | |
| +────────────┼─────────────────────────┼─────────────────────────┼──────────────────────┼─────────+ |
|              │                         │                         │                      │           |
|              ▼                         ▼                         ▼                      ▼           |
|     [Penyimpanan Lakehouse]   [Core Banking System]       [NoSQL Catalogs]       [Metadata Store]   |
|     MinIO / Ceph S3 Bucket     Oracle Database On-Prem     MongoDB Log Store       PostgreSQL DB    |
+----------------------------------------------------------------------------------------------------+
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi validasi kontrak data menggunakan PySpark DataFrame assertions untuk mendeteksi *schema drift* dan memisahkan data kotor ke partisi karantina secara sederhana:

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

spark = SparkSession.builder \
    .appName("SimpleDataQualityAndSchemaGuard") \
    .master("local[*]") \
    .getOrCreate()

# 1. Definisi Kontrak Skema Ekspektasi
expected_schema = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("account_id", StringType(), False),
    StructField("amount", DoubleType(), False),
    StructField("currency", StringType(), False)
])

# 2. Simulasi Data Masuk (Data mentah mengandung drift dan anomaly)
raw_incoming_data = [
    ("tx101", "acc_a", 1500.50, "USD"),
    ("tx102", "acc_b", -50.00, "USD"),        # Anomali: Nilai amount negatif
    ("tx103", None, 300.00, "EUR"),            # Anomali: Kunci account_id NULL
    ("tx104", "acc_d", 12000.00, "INVALID_CUR") # Anomali: Mata uang tidak valid
]

df_raw = spark.createDataFrame(raw_incoming_data, ["transaction_id", "account_id", "amount", "currency"])

# 3. Filter Validasi Sederhana (Rule-based Data Contract)
VALID_CURRENCIES = ["USD", "EUR", "IDR", "SGD"]

validated_df = df_raw.withColumn(
    "rejection_reason",
    when(col("transaction_id").isNull(), "NULL_TRANSACTION_ID")
    .when(col("account_id").isNull(), "NULL_ACCOUNT_ID")
    .when(col("amount") <= 0.0, "INVALID_TRANSACTION_AMOUNT")
    .when(~col("currency").isin(VALID_CURRENCIES), "UNSUPPORTED_CURRENCY")
    .otherwise(None)
)

# 4. Percabangan Jalur: Data Bersih vs Data Karantina
clean_data = validated_df.filter(col("rejection_reason").isNull()).drop("rejection_reason")
quarantine_data = validated_df.filter(col("rejection_reason").isNotNull()) \
    .withColumn("quarantined_at", current_timestamp())

print("=== DATA VALID (SIAP UNTUK LAKEHOUSE) ===")
clean_data.show(truncate=False)

print("=== DATA KARANTINA (DEAD LETTER QUEUE / REVIEW) ===")
quarantine_data.show(truncate=False)
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Kasus Produksi Lapangan: Implementasi *Real-time Streaming Ingestion* dengan PySpark, Delta Lake, penanganan mutasi skema (*Schema Evolution*), dan pemeriksaan mutu data berbasis *Circuit Breaker*.

### 1. Ingestion Pipeline & Schema Drift Handling (`pipeline_engine.py`)

```python
import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, expr, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, TimestampType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FieldDataEngine")

def create_spark_session(warehouse_path: str) -> SparkSession:
    """
    Konfigurasi Spark Engine dengan dependensi Delta Lake untuk lingkungan on-premise/hybrid.
    """
    return SparkSession.builder \
        .appName("FDE-Resilient-Field-Pipeline") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.delta.logStore.class", "org.apache.spark.sql.delta.storage.HDFSLogStore") \
        .config("spark.sql.streaming.schemaInference", "true") \
        .getOrCreate()

def run_streaming_pipeline():
    spark = create_spark_session("hdfs://nn1:8020/lakehouse")
    
    # Skema dasar (Base Schema)
    base_event_schema = StructType([
        StructField("event_id", StringType(), False),
        StructField("client_code", StringType(), False),
        StructField("action", StringType(), False),
        StructField("transaction_value", DoubleType(), True),
        StructField("timestamp", StringType(), False)
    ])

    kafka_bootstrap = "kafka-broker1.internal.corp:9092,kafka-broker2.internal.corp:9092"
    source_topic = "telemetry-raw-events"
    checkpoint_dir = "hdfs://nn1:8020/checkpoints/telemetry_pipeline"
    delta_bronze_target = "hdfs://nn1:8020/lakehouse/bronze/events"
    delta_quarantine_target = "hdfs://nn1:8020/lakehouse/quarantine/events"

    # Penyerapan dari Kafka
    raw_kafka_stream = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_bootstrap) \
        .option("subscribe", source_topic) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    # Ekstraksi Data JSON Mentah
    parsed_stream = raw_kafka_stream.select(
        col("key").cast("string").alias("message_key"),
        from_json(col("value").cast("string"), base_event_schema).alias("payload"),
        col("timestamp").alias("kafka_received_timestamp")
    ).select("message_key", "payload.*", "kafka_received_timestamp")

    def process_micro_batch(micro_batch_df, batch_id):
        logger.info(f"Memproses Micro-batch: {batch_id}, Total Record: {micro_batch_df.count()}")
        
        if micro_batch_df.rdd.isEmpty():
            logger.info("Batch kosong. Melewati proses.")
            return

        micro_batch_df.persist()

        # Quality Assertion Logic (Circuit Breaker Check)
        total_records = micro_batch_df.count()
        corrupted_records = micro_batch_df.filter(
            col("event_id").isNull() | 
            col("client_code").isNull() | 
            (col("transaction_value") < 0.0)
        )
        
        corrupted_count = corrupted_records.count()
        corruption_ratio = (corrupted_count / float(total_records)) if total_records > 0 else 0.0

        logger.info(f"Batch {batch_id} - Tingkat Anomali: {corruption_ratio * 100:.2f}% ({corrupted_count}/{total_records})")

        # Threshold Kritis: Jika anomali > 15%, aktifkan Circuit Breaker
        CRITICAL_ERROR_THRESHOLD = 0.15
        if corruption_ratio > CRITICAL_ERROR_THRESHOLD:
            logger.error(f"CIRCUIT BREAKER TRIP! Anomali ({corruption_ratio * 100:.2f}%) melampaui batas kritis ({CRITICAL_ERROR_THRESHOLD * 100:.2f}%). Mengarahkan batch ke Karantina...")
            micro_batch_df.withColumn("quarantined_reason", expr("'CIRCUIT_BREAKER_TRIPPED_HIGH_ANOMALY'")) \
                .withColumn("batch_id", expr(f"'{batch_id}'")) \
                .write \
                .format("delta") \
                .mode("append") \
                .save(delta_quarantine_target)
            micro_batch_df.unpersist()
            return

        # Pisahkan data valid dan data cacat minor
        clean_batch_df = micro_batch_df.filter(
            col("event_id").isNotNull() & 
            col("client_code").isNotNull() & 
            ((col("transaction_value") >= 0.0) | col("transaction_value").isNull())
        )

        bad_batch_df = micro_batch_df.subtract(clean_batch_df)

        # 1. Tulis Data Bersih dengan Schema Evolution (mergeSchema)
        clean_batch_df.write \
            .format("delta") \
            .mode("append") \
            .option("mergeSchema", "true") \
            .save(delta_bronze_target)

        # 2. Tulis Data Cacat Minor ke Karantina Khusus
        if not bad_batch_df.rdd.isEmpty():
            bad_batch_df.withColumn("quarantined_reason", expr("'FIELD_VALIDATION_ERROR'")) \
                .withColumn("batch_id", expr(f"'{batch_id}'")) \
                .write \
                .format("delta") \
                .mode("append") \
                .option("mergeSchema", "true") \
                .save(delta_quarantine_target)

        micro_batch_df.unpersist()
        logger.info(f"Micro-batch {batch_id} berhasil diproses.")

    # Menjalankan Streaming Query
    query = parsed_stream.writeStream \
        .foreachBatch(process_micro_batch) \
        .option("checkpointLocation", checkpoint_dir) \
        .start()

    query.awaitTermination()

if __name__ == "__main__":
    run_streaming_pipeline()
```

### 2. Trino Catalog Setup untuk Federasi Multi-Silo

Konfigurasi konektor Trino agar dapat menjalankan kueri lintas silo data tanpa duplikasi fisik.

#### Konfigurasi Delta Lake Connector (`/etc/trino/catalog/lakehouse.properties`)
```properties
connector.name=delta-lake
hive.metastore.uri=thrift://hive-metastore.internal.corp:9083
delta.register-table-procedure.enabled=true
fs.native-s3.enabled=false
fs.native-hdfs.enabled=true
```

#### Konfigurasi PostgreSQL Core Banking Connector (`/etc/trino/catalog/core_pg.properties`)
```properties
connector.name=postgresql
connection-url=jdbc:postgresql://pg-db-prod.internal.corp:5432/core_banking
connection-user=fde_federation_user
connection-password=SecureProductionCredentialsToken!
```

#### Federated Cross-Domain Query Script (`query_federation.sql`)
Kueri ini menggabungkan data produk lakehouse yang tersimpan di Delta Lake dengan sistem database relasional transaksional klien secara *zero-copy*:

```sql
-- Analisis Rekonsiliasi Real-time antara Lapisan Lakehouse Silver dan Database PostgreSQL Klien
SELECT 
    lake.client_code,
    pg.organization_name,
    COUNT(lake.event_id) AS total_lake_events,
    SUM(lake.transaction_value) AS aggregate_processed_amount,
    pg.current_credit_limit,
    (pg.current_credit_limit - COALESCE(SUM(lake.transaction_value), 0)) AS remaining_liquidity
FROM 
    lakehouse.silver.events lake
JOIN 
    core_pg.public.clients pg 
    ON lake.client_code = pg.client_id
WHERE 
    CAST(lake.timestamp AS TIMESTAMP) >= CURRENT_TIMESTAMP - INTERVAL '7' DAY
    AND pg.status = 'ACTIVE'
GROUP BY 
    lake.client_code,
    pg.organization_name,
    pg.current_credit_limit
HAVING 
    SUM(lake.transaction_value) > (pg.current_credit_limit * 0.8)
ORDER BY 
    remaining_liquidity ASC;
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan | Keuntungan | Kerugian / Risiko | Skenario Pemilihan di Lapangan |
| :--- | :--- | :--- | :--- |
| **Big Data Federation (Trino/Presto)** | *Zero-copy*, tidak membutuhkan penyimpanan ganda, *time-to-insight* sangat cepat, menjunjung kedaulatan data klien. | Latensi kueri bergantung pada performa basis data sumber; rentan membebani database operasional klien jika optimasi predicate pushdown gagal. | Silo tersebar lintas departemen; regulasi melarang data diekspor ke satu tempat; kueri bersifat ad-hoc / analisis diagnostik. |
| **Centralized ETL/ELT Ingestion** | Performa analitik optimal (terindeks, terkompresi di satu kluster cepat), pemisahan total dari beban operasional database klien. | Biaya penyimpanan ganda tinggi; pipeline rapuh jika terjadi perubahan skema hulu; keterlambatan data (*data staleness*). | Laporan agregasi eksekutif berskala besar; pelatihan model machine learning yang membutuhkan scan masif di storage lokal. |
| **Schema Evolution (`mergeSchema = true`)** | Pipeline streaming tidak pernah mati (*crash-free*) ketika ada penambahan atribut/kolom baru dari sistem hulu. | Skema Parquet berisiko membengkak (*wide-column explosion*); tipe data ambigu dapat mengakibatkan nilai menjadi `NULL` permanen. | Sistem sumber sering melakukan *A/B testing* atau deployment fitur baru mikroservis tanpa sinkronisasi tim data. |
| **Strict Schema Enforcement** | Menjaga kualitas dan integritas metadata data lakehouse downstream tetap terproteksi secara deterministik. | Membutuhkan intervensi rekayasa data manual; pipeline terhenti seketika (*fail-stop*) jika tipe data diubah. | Modul pelaporan finansial wajib, audit kepatuhan regulasi perbankan, data ledger akuntansi. |
| **In-line DLQ & Quarantine** | Pemrosesan data yang baik tetap berjalan lancar (*fail-safe*); data rusak terdokumentasi untuk audit dan investigasi forensik. | Membutuhkan mekanisme rekonsiliasi sekunder; ukuran tabel karantina dapat melonjak tajam tanpa kebijakan retensi yang ketat. | Wajib diterapkan pada semua arsitektur penyerapan real-time berskala kritis (*mission-critical*). |

---

## SEKSI 11 — BEST PRACTICES

1. **Terapkan Data Contracts di Boundary Service**: Jangan memproses payload JSON mentah secara bebas tanpa kontrak. Terapkan Protobuf atau Avro Schema Registry dengan mode `BACKWARD_TRANSITIVE` atau `FULL` sebagai gerbang komunikasi antara tim aplikasi klien dan platform data.
2. **Pushdown Filtering Maksimal pada Federasi**: Saat menulis query federasi pada Trino, pastikan selalu menyertakan kolom yang terindeks dan terpartisi pada basis data sumber (`WHERE timestamp > ...`) untuk memastikan optimizer mengeksekusi *Predicate Pushdown* dan tidak melakukan *Full Table Scan* pada sistem transaksional klien.
3. **Isolasi Checkpoint Spark Streaming**: Letakkan direktori checkpoint Spark pada penyimpanan terdistribusi dengan garansi konsistensi kuat (*strong consistency*), seperti HDFS atau S3 dengan locking mechanism aktif. Jangan pernah berbagi direktori checkpoint antar-job.
4. **Strategi Partisi Open Table Format**: Jangan membuat partisi berdasarkan kolom dengan kardinalitas sangat tinggi (seperti `timestamp` detik atau `transaction_id`). Buat partisi berdasarkan format waktu stabil (`year-month-day` atau `event_date`) digabungkan dengan teknik optimasi seperti Z-Ordering / Liquid Clustering pada Delta Lake atau Partition Evolution pada Apache Iceberg.
5. **Circuit Breaker Multi-Level**: Terapkan deteksi anomali bertingkat:
   * *Level 1 (Batch-level failure)*: Data dialihkan ke DLQ lokal jika format serialisasi rusak.
   * *Level 2 (Statistical anomaly)*: Pipeline berhenti otomatis jika rasio data invalid melampaui batas toleransi (misalnya > 5% record gagal validasi).
   * *Level 3 (Infrastructure fault)*: Failover ke kluster cadangan jika latensi Kafka consumer melampaui batas SLO (misal consumer lag > 1.000.000 pesan).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Membiarkan Tipe Data Kolom Berubah Tanpa Validasi Tipe (*Type Mismatch Drift*)
* **Anti-Pattern**: Mengaktifkan `mergeSchema = true` saat sumber mengubah tipe data dari `integer` ke `string` secara inkonsisten. Delta Lake akan memblokir perubahan atau mengubah nilai menjadi `NULL` secara tersembunyi.
* **Solusi**: Tangkap skema di layer perantara (CDC / Spark Transformer) menggunakan skema perantara bertipe *safe-variant* (seperti JSON String) sebelum di-*cast* secara eksplisit dengan validasi regex/skema deterministik.

### 2. Kueri Lintas Silo (*Cross-Database Join*) Tanpa Memperhatikan Volume Data
* **Anti-Pattern**: Melakukan `JOIN` antara tabel 500 juta baris di Delta Lake dengan tabel 100 juta baris di PostgreSQL langsung via Trino tanpa filter. Worker node Trino akan kehabisan memori (*OOM - Out of Memory*) akibat mentransfer data mentah lewat jaringan.
* **Solusi**: Pastikan tabel transaksional diposisikan sebagai dimensi kecil (*broadcast join*) atau lakukan agregasi lokal di sumbernya (*Trino dynamic pushdown*) sebelum dihubungkan dengan tabel fakta besar di data lakehouse.

### 3. Mengabaikan Compaction pada Streaming Delta Lake
* **Anti-Pattern**: Menjalankan Structured Streaming dengan interval trigger singkat (misal: 1 detik) langsung menulis ke Delta Lake tanpa strategi penggabungan file (*file compaction*). Ini memicu masalah *Small Files Problem* (jutaan file berukuran beberapa kilobyte) yang melumpuhkan performa query kueri federasi Trino.
* **Solusi**: Aktifkan fitur *Auto-Compaction* dan *Optimized Writes* pada Delta Lake:
  ```sql
  SET spark.databricks.delta.optimizeWrite.enabled = true;
  SET spark.databricks.delta.autoCompact.enabled = true;
  ```
  Serta jadwalkan proses reguler `OPTIMIZE [table] ZORDER BY (key)` di luar jam sibuk.

### 4. Tidak Membatasi Akses Akun Komputasi Federasi
* **Anti-Pattern**: Memberikan kredensial user `postgres` / `DBA` sistem klien ke konektor Trino. Analis data secara tidak sengaja dapat mengeksekusi kueri `JOIN` berat yang mengunci tabel (*table lock*) di basis data inti operasional klien.
* **Solusi**: Berikan akun JDBC khusus dengan hak akses baca-saja (*READ-ONLY*), batasi *statement execution timeout*, dan terapkan alokasi resource pool terisolasi pada database klien.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan Terbimbing (Guided Lab): Mengonfigurasi Data Quality Circuit Breaker di Apache Spark

**Skenario**: Anda dipanggil oleh klien perbankan di mana sistem ingest mereka terus mengalami *crash* karena tim aplikasi mobile sering mengubah skema JSON event transaksi tanpa koordinasi.

#### Langkah Pelaksanaan:

1. **Inisialisasi Project**: Buat skrip Python bernama `circuit_breaker_lab.py`.
2. **Definisikan Generator Data Sintetis**: Buat stream mikro yang menghasilkan kombinasi data valid dan data cacat (mengandung payload dengan field `amount` bertipe string acak dan missing primary key).
3. **Bangun Kriteria Kontrak Data**:
   * Kunci utama `transfer_id` tidak boleh `NULL`.
   * Nilai `transfer_amount` harus bertipe numeric positif.
4. **Implementasikan Logika Circuit Breaker**:
   * Jika lebih dari 20% baris data dalam satu micro-batch rusak, batch harus dialihkan ke Delta Table `quarantined_transfers` dan eksekusi downstream dihentikan dengan log peringatan darurat.
   * Jika kurang dari 20% baris rusak, pisahkan baris valid ke `silver_transfers`, dan buang baris rusak ke `dlq_transfers`.

#### Rubrik Penilaian:
* [ ] Menggunakan API Structured Streaming atau Micro-batch DataFrame secara benar.
* [ ] Perhitungan rasio anomali dilakukan tanpa memicu *multiple action computation* (menggunakan `persist()`).
* [ ] Memisahkan jalur penyimpanan data secara deterministik menggunakan Delta Lake format.
* [ ] Menangani pembersihan cache memori Spark (`unpersist()`) untuk mencegah kebocoran memori (*memory leak*).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

Jawablah pertanyaan berikut untuk menguji pemahaman Anda:

1. **Apa yang terjadi secara internal pada Delta Lake ketika data baru memiliki kolom tambahan yang tidak ada di skema tabel target, dan opsi `mergeSchema` disetel ke `true`?**
   * A. Spark membatalkan seluruh operasi tulis dan melempar `AnalysisException`.
   * B. Spark membuat file Parquet baru yang menyertakan kolom baru tersebut, memperbarui schema log JSON di `_delta_log/`, dan membiarkan data lama bernilai `NULL` saat dikueri.
   * C. Seluruh file Parquet lama ditulis ulang (*full table rewrite*) agar sesuai dengan skema baru.
   * D. Kolom baru diabaikan dan dibuang (*dropped*) tanpa memicu error.

2. **Manakah dari pola berikut yang PALING efektif untuk mencegah kueri federasi Trino melumpuhkan basis data operasional klien (RDBMS OLTP)?**
   * A. Mengonfigurasi Trino workers agar membaca data langsung dari hard disk server database klien melalui NFS.
   * B. Mematikan fitur cost-based optimizer di Trino coordinator.
   * C. Menerapkan koneksi ke read-replica sekunder dengan limit timeout ketat serta mengoptimalkan *predicate pushdown*.
   * D. Mengimpor seluruh basis data OLTP ke format CSV setiap 5 menit.

3. **Dalam implementasi Data Mesh, apa arti dari prinsip "Data as a Product" (DaaP)?**
   * A. Data domain dikemas dan dijual dalam bentuk file spreadsheet kepada publik.
   * B. Data lakehouse harus dikelola secara terpusat oleh tim TI inti tanpa campur tangan tim bisnis.
   * C. Domain data diperlakukan memiliki siklus hidup sendiri, disertai garansi SLO/SLA, metadata yang mudah dicari (*discoverable*), serta kontrak data yang jelas bagi konsumen internal.
   * D. Seluruh data disimpan dalam satu server basis data monolitik agar lisensi komersialnya efisien.

4. **Kapan kondisi yang mengharuskan arsitektur pipeline menerapkan Circuit Breaker Pattern daripada sekadar mengalirkan data cacat ke Dead Letter Queue (DLQ)?**
   * A. Ketika data cacat hanya mencakup 0,001% dari keseluruhan batch.
   * B. Ketika anomali data melonjak tajam secara masif (misal: > 50%), yang mengindikasikan adanya kerusakan fatal di sisi sistem hulu (upstream outage/corrupted release).
   * C. Ketika format penyimpanan downstream menggunakan Delta Lake bukan Apache Iceberg.
   * D. Ketika kueri Trino dijalankan di atas jaringan berkecepatan 10 Gbps.

5. **Apa risiko arsitektur dari membiarkan `mergeSchema = true` aktif secara permanen tanpa adanya validasi registri skema (Schema Registry) di lapisan penyerapan (ingestion layer)?**
   * A. Kecepatan CPU Spark akan turun sebesar 90% secara permanen.
   * B. Terjadinya fenomena *wide-column explosion* dan kemungkinan perubahan tipe data implisit yang merusak kompatibilitas historis.
   * C. Checkpoint log Kafka akan langsung terhapus.
   * D. Format file Delta Lake otomatis berubah menjadi format format teks biasa (plain text).

---

### Kunci Jawaban & Rasional Singkat

1. **B**: Delta Lake mendukung evolusi skema berbasis metadata di transactional log (`_delta_log`). Parquet baru ditulis dengan kolom baru, sedangkan Parquet lama dibaca sebagai `NULL` untuk kolom tersebut tanpa penulisan ulang historis.
2. **C**: Mengarahkan federasi ke Read Replica melindungi *master instance* OLTP klien dari beban komputasi analitik, dan *predicate pushdown* memastikan pemfilteran data terjadi langsung di RDBMS sebelum transit ke network.
3. **C**: Prinsip DaaP memosisikan data bukan sekadar efek samping sistem operasional, tetapi artefak bernilai tinggi dengan kepemilikan jelas (*domain ownership*), metadata standar, keamanan, dan kepatuhan SLA.
4. **B**: DLQ cocok untuk kegagalan sporadis skala kecil. Namun jika lonjakan anomali terjadi masif (> 50%), ini menandakan kegagalan struktural; pemrosesan harus segera diputus (*circuit breaker trip*) agar storage karantina tidak meledak dan downstream tidak menerima data yang tidak bermakna.
5. **B**: Tanpa kontrol registri, kesalahan serialisasi produser (misal: typo pada nama field JSON `user_id` menjadi `usr_id`, `userId`, `ID`) akan terus menghasilkan kolom baru secara terus menerus, mengakibatkan degradasi performa drastis dan kekacauan tata kelola data.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* Dehghani, Zhamak. *Data Mesh: Delivering Data-Driven Value at Scale*. O'Reilly Media, 2022.
* Armbrust, Michael, et al. *Delta Lake: High-Performance ACID Table Storage over Cloud Object Stores*. Proceedings of the VLDB Endowment, 2020.
* Traverso, Martin, Sundstrom, Dain, Phillips, David. *Trino: The Definitive Guide: SQL at Any Scale, on Any Storage, in Any Cloud*. O'Reilly Media, 2021.
* Kleppmann, Martin. *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems*. O'Reilly Media, 2017.
* Apache Spark Documentation: *Structured Streaming Programming Guide*. [spark.apache.org](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html).
* Great Expectations Core Documentation: *Data Quality Declarative Framework*. [docs.greatexpectations.io](https://docs.greatexpectations.io/).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Rekayasa data di lapangan menuntut adaptabilitas tinggi terhadap infrastruktur klien yang heterogen, lingkungan terisolasi (*air-gapped*), dan data yang terfragmentasi.
2. *Data Mesh* mendesentralisasi kepemilikan data ke domain fungsional, memanfaatkan *Data as a Product* dan *Federated Computational Governance* guna memecahkan bottleneck arsitektur terpusat lama.
3. *Schema drift* di lapangan adalah kepastian. Arsitektur data modern harus memadukan penegakan skema berbasis registri (*Schema Registry*), evolusi skema otomatis (*Delta Lake schema evolution*), serta isolasi record menyimpang melalui *Dead Letter Queues* (DLQ).
4. *Big Data Federation* (misalnya via Trino) memungkinkan analisis multi-silo secara *zero-copy*, menjaga kedaulatan data klien dan mempercepat pembuktian nilai teknis (*time-to-value*) solusi FDE di fase implementasi awal.
5. *Data Quality Validation* yang aktif—didukung oleh mekanisme *Circuit Breaker*—memastikan bahwa data berkualitas rendah dicegah secara dini di lapisan penyerapan (*shift-left validation*), melindungi stabilitas operasional seluruh sistem analitik downstream.

---

## SEKSI 17 — GLOSARIUM

* **Change Data Capture (CDC)**: Pola integrasi sistem di mana setiap perubahan data tingkat baris (INSERT, UPDATE, DELETE) pada transaction log basis data ditangkap dan dialirkan sebagai event stream secara real-time.
* **Dead Letter Queue (DLQ)**: Antrean atau lokasi penyimpanan khusus yang menampung pesan atau baris data yang gagal diproses oleh sistem konsumen karena error parsing, validasi tipe, atau pelanggaran kontrak data.
* **Schema Drift**: Kondisi dinamis di mana skema atau struktur format data yang dikirim oleh sistem produser mengalami perubahan tanpa pemberitahuan formal sebelumnya ke sistem hilir.
* **Circuit Breaker (Data Engineering)**: Pola ketahanan arsitektur di mana aliran eksekusi pipeline data dihentikan secara otomatis apabila parameter error/anomali melampaui batas toleransi risiko yang telah ditentukan.
* **Predicate Pushdown**: Mekanisme optimasi komputasi query engine terdistribusi di mana klausa filter kueri (`WHERE`) dieksekusi sedekat mungkin pada lapisan penyimpanan fisik sumber data guna mengurangi transfer data jaringan.
* **Open Table Format**: Lapisan abstraksi penyimpanan di atas file penyimpanan objek (seperti Parquet) yang menyediakan kapabilitas transaksi ACID, metadata time-travel, serta partisi dinamis (contoh: Delta Lake, Apache Iceberg, Apache Hudi).

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fokus Pelatihan**: Tekankan kepada para calon FDE bahwa masalah terbesar di infrastruktur klien bukanlah menulis kode Spark yang rumit, melainkan menangani inkonsistensi data mentah, keterbatasan jaringan internal klien, dan birokrasi akses ke database operasional.
* **Troubleshooting Tip**: Saat mendemonstrasikan Trino di lingkungan on-premise klien, pastikan alokasi *JVM Garbage Collection* (G1GC) dan batas memori per-query (`query.max-memory-per-node`) dikonfigurasi dengan aman agar worker tidak dibunuh oleh *OOM Killer* Linux.
* **Poin Penekanan**: Selalu tekankan prinsip kedaulatan data klien: *"Jangan pernah memindahkan data keluar dari lingkungan klien kecuali benar-benar diwajibkan oleh Use Case dan telah divalidasi oleh Tim Keamanan Informasi Klien."*

---

## SEKSI 19 — CHANGELOG & VERSI

| Versi | Tanggal | Penulis | Deskripsi Perubahan |
| :--- | :--- | :--- | :--- |
| `1.0.0` | 2026-03-30 | Lead Technical Curriculum Architect | Rilis draf materi modul awal sesuai kurikulum FDE standar. |
| `1.1.0` | 2026-03-31 | Field Architecture Review Board | Penambahan arsitektur Circuit Breaker produksi dan skrip Trino federated pushdown. |

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `06-Architecture-and-System-Design / Bab 02: Arsitektur Air-Gapped, Sovereign Cloud, dan Komputasi Tepi`
* **Modul Berikutnya**: `06-Architecture-and-System-Design / Bab 03 Module 02: Arsitektur Model Serving & Inferensi Rendah Latensi di Lingkungan On-Premise Terbatas`
* **Repositori Kode Modul**: `fde-core-curriculum/06-arch/lab-03-data-federation-and-quality/`