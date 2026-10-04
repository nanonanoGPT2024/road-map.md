# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Topik:** AI Data Scientist | **Kategori:** 08-AI-Data-and-Autonomous-Agents | **Bab:** 02 - Modern Data Engineering & Distributed Analytics

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi arsitektur *Lakehouse* modern menggunakan Apache Spark 3.5+, Delta Lake 3.x, dan Apache Iceberg untuk beban kerja data sains dan pelatihan model AI skala petabyte.
- Menganalisis dan mengoptimalkan performa mesin komputasi terdistribusi melalui *Catalyst Optimizer*, *Tungsten Execution Engine*, partisi dinamis, serta eliminasi *data skew*.
- Merancang dan menerapkan *end-to-end streaming ingestion pipeline* dengan Apache Kafka dan Spark Structured Streaming menggunakan semantik *Exactly-Once Processing* (EOP).
- Mengintegrasikan mekanisme *feature store* dan *vector database indexing pipeline* terdistribusi yang tahan banting (*fault-tolerant*) terhadap *schema drift* dan kegagalan node kluster.
- Mendiagnosis dan menyelesaikan degradasi performa pada tingkat JVM, *shuffle spill*, *out-of-memory* (OOM), dan *speculative execution latency*.

---

## 2. Prerequisites
Sebelum memulai modul ini, peserta wajib memiliki pemahaman mendalam tentang:
- **Distributed Computing Fundamentals:** Teorema CAP, PACELC, model konkurensi (Actor vs MapReduce), replikasi terdistribusi.
- **Bahasa Pemrograman:** Python 3.10+ (tingkat lanjut, OOP, threading/asyncio) dan SQL tingkat lanjut (window functions, query plans).
- **Core Spark Concepts:** Resilient Distributed Datasets (RDD), DataFrames, Transformations vs Actions, Lazy Evaluation.
- **Infrastruktur Modern:** Docker, Kubernetes (dasar alokasi pod/volume), format penyimpanan kolumnar (Apache Parquet, ORC).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi Runtime Apache Spark 3.x & Tungsten Engine
Apache Spark mengeksekusi komputasi melalui koordinasi antara **Driver Program** dan kumpulan **Executors** di seluruh *worker node*. Komponen internal Spark bekerja melalui beberapa lapisan abstraksi:

```
[Logical Plan] -> [Analyzed Logical Plan] -> [Optimized Logical Plan] -> [Physical Plans] -> [Cost Model Engine] -> [Selected Physical Plan] -> [Tungsten Code Generation]
```

1. **Catalyst Optimizer:**
   - **Analysis:** Menerjemahkan Abstract Syntax Tree (AST) dari kode SQL/DataFrame menjadi *Unresolved Logical Plan*, kemudian memvalidasi kolom dan tabel terhadap *Catalog*.
   - **Logical Optimization:** Menerapkan aturan deterministik seperti *Constant Folding*, *Predicate Pushdown*, *Projection Pruning*, dan *Null Propagation*.
   - **Physical Planning:** Menghasilkan satu atau lebih rencana fisik komputasi (misal: memilih antara *SortMergeJoinExec* atau *BroadcastHashJoinExec*).
   - **Cost-Based Optimizer (CBO):** Menggunakan statistik tabel (ukuran data, histogram kardinalitas kolom) untuk menentukan urutan *join* dan strategi eksekusi optimal.

2. **Tungsten Engine:**
   - **Memory Management Off-Heap:** Mengabaikan *Garbage Collector* (GC) JVM standar dengan mengelola memori mentah menggunakan `sun.misc.Unsafe`. Mengeliminasi *overhead* objek Java (misal: String 4-byte di Java dapat memakan 48-byte memori).
   - **Cache-Aware Computation:** Mengatur memori dalam format baris yang kompak (Compact Binary Format) untuk memaksimalkan *CPU L1/L2/L3 cache hit ratio*.
   - **Whole-Stage Code Generation (WSCG):** Menggabungkan beberapa operator fisik yang berurutan (misal: Filter -> Project -> Aggregate) ke dalam satu fungsi Java tunggal *in-memory*, mengeliminasi *virtual function dispatch overhead*.

### 3.2. Delta Lake / Lakehouse Storage Internals
Delta Lake menyediakan keandalan ACID di atas *object storage* (S3, GCS, ADLS) dengan memanfaatkan dua komponen inti:
- **Delta Transaction Log (`_delta_log/`):** Direktori urutan file JSON yang mencatat setiap mutasi (*commit*) secara atomik. Setiap 10 commit, Delta membuat file *checkpoint* berbasis Parquet yang mengonsolidasikan seluruh log sebelumnya.
- **Optimistic Concurrency Control (OCC):** Menjamin isolasi *Serializable* atau *WriteSerializable*. Jika dua transaksi menulis ke partisi yang sama, transaksi terakhir akan gagal dan secara otomatis mencoba ulang (*retry*) jika tidak ada konflik data aktual.

```
Lakehouse Table Layout:
warehouse/events/
├── _delta_log/
│   ├── 00000000000000000000.json
│   ├── 00000000000000000001.json
│   └── 00000000000000000001.checkpoint.parquet
├── date=2024-01-01/
│   ├── part-00000-c000.snappy.parquet
│   └── part-00001-c000.snappy.parquet
└── date=2024-01-02/
    └── part-00002-c000.snappy.parquet
```

---

## 4. Why & What
- **Why Traditional Data Warehouses & Pure Data Lakes Fail:**
  *Data Warehouse* tradisional memiliki biaya penyimpanan tinggi, format tertutup (*proprietary*), dan tidak mendukung data tidak terstruktur untuk AI/ML. Sebaliknya, *Data Lake* mentah sering menjadi *Data Swamp* karena minimnya transaksi ACID, ketiadaan penegakan skema (*schema enforcement*), tingginya pembacaan file kecil (*small file problem*), serta ketidakmampuan menangani pembacaan dan penulisan bersamaan secara deterministik.
- **What is a Modern Production Lakehouse:**
  Arsitektur penyimpanan hibrida yang menyematkan mesin transaksi transparan berbasis file terbuka (Parquet + Metadata Log). Arsitektur ini memungkinkan analitik BI, data engineering streaming, serta pengambilan sampel data historis untuk *deep learning* dieksekusi secara bersamaan di atas *single source of truth*.

---

## 5. How (Workflow Detail)

Alur kerja data produksi modern untuk rekayasa fitur AI berskala enterprise mengikuti siklus berikut:

```
[Edge / App Events] 
       │
       ▼
[Apache Kafka Cluster] (Multi-Broker, Replicated Topic)
       │
       ▼ (Spark Structured Streaming - Micro-batching)
[Bronze Layer: Raw Ingestion] (Delta Lake: Append-Only, Exact Payload, Preservation)
       │
       ▼ (Data Cleansing, Validation, Schema Enforcement via PyDeequ/Great Expectations)
[Silver Layer: Enriched & Cleaned] (Delta Lake: De-duplicated, Validated, Compacted)
       │
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[Gold Layer: Business Aggregates]   [Vector & Feature Pipeline]
(Analytical SQL / PowerBI / Trino)  (Chunking, Embedding via Ray/vLLM, Milvus/Qdrant)
```

1. **Ingestion:** Kafka mengonsumsi data mentah JSON/Protobuf dengan throughput tinggi.
2. **Bronze Landing:** Spark Streaming membaca log Kafka, menulis payload mentah dan metadata offset ke Bronze Delta table dengan interval micro-batch rendah (1–5 detik).
3. **Silver Refinement:** Pembersihan data, deduplikasi berbasis watermark (*dropDuplicates*), dan validasi skema ketat.
4. **Gold & AI Serving:** Data diagregasi untuk metrik real-time dan diekstraksi ke pipeline komputasi embedding terdistribusi untuk ingest ke Vector Database.

---

## 6. Analogy & Diagram ASCII

### Analogi: Dapur Restoran Bintang Lima vs Eksekusi Spark
- **Driver:** *Head Chef* yang menerima pesanan (Query SQL), menyusun resep efisien (Catalyst Optimizer), dan membagi langkah kerja ke para koki.
- **Executor:** *Line Cook* independen dengan stasiun kerja dan peralatan sendiri (Core CPU dan Memori Off-Heap).
- **Shuffle:** Proses saling tukar bahan baku antar koki ketika satu hidangan membutuhkan bahan yang dipotong koki lain. Ini adalah tahap paling memakan waktu dan berpotensi menimbulkan tabrakan (*bottleneck*).
- **Tungsten Engine:** Penggunaan pisau bedah standar industri dan wadah terstandarisasi untuk memotong jalur bolak-balik tanpa membuang waktu mengupas ulang bahan baku.

### Diagram: Alur Eksekusi Query Terdistribusi

```
                  +----------------------------------+
                  |           Spark Driver           |
                  |  Catalyst Optimizer & Scheduler  |
                  +-----------------+----------------+
                                    |
            +-----------------------+-----------------------+
            | DAG Scheduling                                | DAG Scheduling
            v                                               v
+-----------------------+                       +-----------------------+
|   Worker Node 1       |                       |   Worker Node 2       |
| +-------------------+ |                       | +-------------------+ |
| |    Executor A     | |                       | |    Executor B     | |
| | [Task 1] [Task 2] | |     Shuffle Stage     | | [Task 3] [Task 4] | |
| |  Memory / Off-Heap| | <===================> | |  Memory / Off-Heap| |
| +-------------------+ |                       | +-------------------+ |
+-----------------------+                       +-----------------------+
            |                                               |
            +-----------------------+-----------------------+
                                    | Output Stream
                                    v
                  +----------------------------------+
                  |     Object Storage (S3/ADLS)     |
                  |  Parquet Files + _delta_log JSON |
                  +----------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Batch Processing dengan Schema Enforcement
Contoh dasar validasi skema ketat menggunakan PySpark murni:

```python
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType

spark = SparkSession.builder \
    .appName("SimpleSchemaEnforcement") \
    .master("local[*]") \
    .getOrCreate()

# Definisi skema eksplisit (mencegah overhead inferSchema)
schema = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("user_id", StringType(), False),
    StructField("amount", DoubleType(), False),
    StructField("timestamp", TimestampType(), False)
])

data = [
    ("tx_101", "usr_a", 150.50, "2024-01-15 10:00:00"),
    ("tx_102", "usr_b", 99.99, "2024-01-15 10:05:00")
]

df = spark.createDataFrame(data, schema=schema)
df.printSchema()
df.show(truncate=False)
```

### 7.2. Practical Example: Production-Grade Kafka-to-Delta Ingestion dengan Watermarking
Pipeline *end-to-end* yang menangani deduplikasi data streaming, *watermarking*, penanganan *late data*, serta penulisan transaksional ke Delta Lake:

```python
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, expr
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType

def init_spark_session() -> SparkSession:
    return SparkSession.builder \
        .appName("ProductionKafkaToDeltaPipeline") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.delta.logStore.class", "org.apache.spark.sql.delta.storage.S3SingleDriverLogStore") \
        .config("spark.sql.shuffle.partitions", "200") \
        .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true") \
        .getOrCreate()

def run_pipeline():
    spark = init_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # 1. Definisi Kontrak Data (Schema Ingestion)
    payload_schema = StructType([
        StructField("event_id", StringType(), False),
        StructField("user_id", StringType(), False),
        StructField("event_type", StringType(), False),
        StructField("amount", DoubleType(), True),
        StructField("timestamp", TimestampType(), False)
    ])

    # 2. Ingest Stream dari Apache Kafka
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_topic = "telemetry.user.events"

    raw_stream_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_bootstrap) \
        .option("subscribe", kafka_topic) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .option("maxOffsetsPerTrigger", 50000) \
        .load()

    # 3. Parsing, Watermarking, dan Deduplikasi
    parsed_stream_df = raw_stream_df \
        .selectExpr("CAST(value AS STRING) as json_payload", "timestamp as kafka_arrival_time") \
        .select(from_json(col("json_payload"), payload_schema).alias("data"), col("kafka_arrival_time")) \
        .select("data.*", "kafka_arrival_time") \
        .filter(col("event_id").isNotNull()) \
        .withWatermark("timestamp", "10 minutes") \
        .dropDuplicates(["event_id", "timestamp"])

    # 4. Sink ke Delta Lake Silver Table dengan Checkpointing
    checkpoint_path = "/tmp/lakehouse/checkpoints/silver_user_events"
    delta_target_path = "/tmp/lakehouse/tables/silver_user_events"

    query = parsed_stream_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", checkpoint_path) \
        .option("mergeSchema", "false") \
        .trigger(processingTime="5 seconds") \
        .start(delta_target_path)

    query.awaitTermination()

if __name__ == "__main__":
    run_pipeline()
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Pipeline Deteksi Fraud Real-Time Financial SuperApp
- **Skala:** 1,2 miliar transaksi harian, *peak throughput* 45.000 transaksi/detik.
- **Masalah:** Latensi inferensi fitur transaksi historis (misal: *“frekuensi transaksi kartu X dalam 1 jam terakhir”*) mencapai >1,5 detik jika mengandalkan database relasional (PostgreSQL read-replicas). Database mengalami *lock contention* dan kegagalan replikasi saat beban puncak.
- **Solusi Arsitektur:**
  1. **Tier 1 (Streaming Ingestion):** Kafka multi-cluster mempartisi data berdasarkan hash `account_id` (128 partisi per topic).
  2. **Tier 2 (Continuous Aggregation):** Spark Structured Streaming dengan *RocksDB StateStore provider* menghitung fitur jendela geser (*sliding window*) 10 menit, 1 jam, dan 24 jam dengan watermark 5 menit.
  3. **Tier 3 (Dual Sink Writing):**
     - **Low-latency Serving:** Menulis state ringkas ke Redis Enterprise Cluster (sub-5ms read latency untuk fraud model scorer).
     - **Historical Storage:** Menulis data terpartisi ke Delta Lake Bronze/Silver setiap 1 menit.
  4. **Tier 4 (Daily Compaction):** Job batch harian menjalankan `OPTIMIZE` dan `Z-ORDER BY (account_id, timestamp)` pada Delta Lake untuk mempercepat *backtesting* data scientist hingga 8x lipat.

---

## 9. Trade-offs

| Parameter | Pendekatan A: Append-Only Raw (Append Log) | Pendekatan B: In-Line Deduplication / Delta MERGE |
| :--- | :--- | :--- |
| **Write Latency** | Sangat Rendah (<2 detik micro-batch) | Tinggi (butuh scanning partition & merge cost) |
| **Storage Cost** | Tinggi (terjadi redudansi data sebelum deduplikasi harian) | Rendah (data unik tersimpan langsung) |
| **Read Complexity**| Membutuhkan query dedup (`ROW_NUMBER() OVER...`) di sisi konsumer | Sangat Sederhana (baca langsung tanpa deduplikasi) |
| **Compute Cost** | Terdistribusi dan dapat dijadwalkan di jam non-sibuk | Menuntut kapasitas komputasi tinggi secara real-time |

| Strategi Shuffle | Kapan Digunakan | Trade-off Utama |
| :--- | :--- | :--- |
| **Broadcast Hash Join (BHJ)** | Satu tabel berukuran kecil (<10–100MB) | Menghilangkan shuffle sepenuhnya, namun berisiko Driver/Executor OOM jika tabel melebihi batas memori siaran. |
| **Sort-Merge Join (SMJ)** | Dua tabel berukuran besar (> beberapa GB) | Sangat stabil dan toleran terhadap dataset besar, tetapi memerlukan network I/O masif untuk shuffle dan pengurutan (*disk-spill*). |

---

## 10. Common Mistakes & Troubleshooting

### 1. Masalah: Executor OOM (`java.lang.OutOfMemoryError: Java heap space`)
- **Penyebab:** Ukuran partisi shuffle terlalu besar, penggunaan fungsi `collect()` pada dataset berskala GB, atau memory overhead container k8s/yarn terlalu kecil dibandingkan buffer off-heap.
- **Solusi:**
  - Tambahkan konfigurasi `spark.sql.shuffle.partitions` (skalakan hingga 1 partisi bernilai 100MB–200MB).
  - Naikkan batas *overhead*: `--conf spark.executor.memoryOverhead=2048m`.

### 2. Masalah: Data Skew (Satu task berjalan berjam-jam saat task lain selesai 100%)
- **Penyebab:** Distribusi data pada kolom *join/group-by* timpang (misal: `user_id = NULL` atau pengguna bot dengan jutaan baris data berada dalam satu partisi).
- **Solusi:**
  - Aktifkan Adaptive Query Execution:
    ```properties
    spark.sql.adaptive.enabled=true
    spark.sql.adaptive.skewJoin.enabled=true
    spark.sql.adaptive.skewJoin.skewedPartitionFactor=5
    ```
  - Lakukan teknik *Salting*: Menambahkan string acak `0..N` pada kunci partisi, lalu melakukan join dengan tabel dimensi yang diekspansi (*replicated*).

### 3. Masalah: Delta Lake Small File Problem
- **Penyebab:** Streaming jobs dengan micro-batch interval pendek (misal: 2 detik) membuat ribuan file Parquet berukuran <1MB per hari, menurunkan performa I/O metadata S3/ADLS.
- **Solusi:**
  - Jadwalkan auto-compaction atau eksekusi rutin:
    ```sql
    OPTIMIZE silver_table ZORDER BY (user_id);
    VACUUM silver_table RETAIN 168 HOURS; -- Hapus file historis > 7 hari
    ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Adaptive Query Execution (AQE):** Konfigurasi `spark.sql.adaptive.enabled = true` aktif di lingkungan produksi.
- [ ] **Strict Checkpointing:** Simpan direktori checkpoint streaming di object storage terdistribusi dengan retensi permanen (bukan direktori temporer node lokal).
- [ ] **Dynamic Partition Pruning (DPP):** Pastikan struktur tabel Delta memanfaatkan kolom partisi bernilai kardinalitas rendah-menengah (seperti `event_date`, `region_id`).
- [ ] **No Raw Ingestion Inference:** Hindari penggunaan `inferSchema=True` pada environment produksi karena memicu *full dataset scan* sebelum pemrosesan dimulai.
- [ ] **Garbage Collection Optimization:** Gunakan *G1GC* untuk JVM executor guna mencegah *long stop-the-world pauses*:
  `-XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=35 -XX:G1ReservePercent=15`.
- [ ] **Statistik Delta:** Batasi komputasi statistik kolom pada Delta Lake hanya untuk 32 kolom pertama guna menghemat pemrosesan metadata JSON:
  `spark.databricks.delta.properties.defaults.dataSkippingNumIndexedCols = 32`.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini dalam direktori: `hands-on/m02/`

### File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
```

### File: `hands-on/m02/producer.py`
```python
import json
import time
import random
from datetime import datetime, timezone
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

event_types = ['CLICK', 'PURCHASE', 'LOGIN', 'LOGOUT']

print("Starting streaming event producer...")
try:
    while True:
        payload = {
            "event_id": f"evt_{random.randint(100000, 999999)}",
            "user_id": f"usr_{random.randint(1, 100)}",
            "event_type": random.choice(event_types),
            "amount": round(random.uniform(5.0, 500.0), 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        producer.send('telemetry.user.events', value=payload)
        time.sleep(0.1) # 10 event per detik
except KeyboardInterrupt:
    print("Producer stopped.")
```

### Langkah Eksekusi Hands-on:
1. Jalankan cluster messaging:
   ```bash
   cd hands-on/m02/
   docker-compose up -d
   ```
2. Siapkan virtual environment dan install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install pyspark==3.5.0 delta-spark==3.1.0 kafka-python
   ```
3. Buka terminal baru dan jalankan event producer:
   ```bash
   python producer.py
   ```
4. Jalankan script ingestion Spark Delta Lake (`Practical Example` dari Seksi 7.2):
   ```bash
   python practical_pipeline.py
   ```
5. Pantau pembuatan file commit di direktori metadata:
   ```bash
   ls -la /tmp/lakehouse/tables/silver_user_events/_delta_log/
   ```

---

## 13. Exercises

### Level: Easy
Diberikan DataFrame log transaksi perbankan dengan kolom `[account_id, amount, status, timestamp]`. Tuliskan kode PySpark untuk:
1. Membaca data Parquet.
2. Memfilter transaksi berstatus `'SUCCESS'`.
3. Menghitung rata-rata nilai transaksi per `account_id` tanpa memicu *disk spill*.

### Level: Medium
Buat Spark job yang melakukan rekonsiliasi data antara dua sumber:
- Sumber A: Delta Lake Bronze Table (data mutasi kartu kredit).
- Sumber B: Snapshot database harian CSV dari core banking.
Lakukan join menggunakan *Broadcast Hash Join* secara eksplisit dengan validasi bahwa dataset dimensi tidak melebihi 50MB, dan tangani perbedaan skema mata uang menggunakan `COALESCE` dan `WHEN...OTHERWISE`.

### Level: Hard
Terapkan arsitektur *Dynamic CDC (Change Data Capture)* ingestion stream:
- Konsumsi stream log CDC dari Debezium Kafka Topic yang berisi payload bertipe:
  `{"op": "c|u|d", "before": {...}, "after": {...}}`.
- Tulis fungsi mikro-batch khusus (`foreachBatch`) yang melakukan operasi `MERGE INTO` (Upsert/Delete) ke Delta Lake Silver Table secara idempotensial, memastikan integritas data tetap terjaga meski terjadi *crash-restart* di tengah proses *batch write*.

---

## 14. Challenges (Real Enterprise Issue)

### Skenario Tantangan: "The Skewed Black-Friday Bottleneck"
Sebuah platform E-Commerce berskala global menghadapi kendala saat memproses event stream Black Friday. Dataset streaming memiliki karakteristik:
- Rata-rata 250.000 event/detik.
- 30% dari total trafik berasal dari 3 akun *flash-sale merchant* agregator yang sangat aktif, sementara 70% sisanya terdistribusi merata di 10 juta akun individual.
- Ketika job agregasi jendela waktu (*windowed aggregation*) 1 jam berjalan pada partisi `merchant_id`, terjadi degradasi performa: 3 task Spark berjalan selama 45 menit, sementara 197 task lainnya selesai dalam 2 detik. Hal ini memicu *backpressure* ekstrem pada Kafka, hingga broker kehabisan ruang disk.

### Tugas Anda:
1. Rancang arsitektur strategi mitigasi skew untuk streaming tanpa mengubah kontrak data masukan Kafka.
2. Jelaskan implementasi algoritma *two-phase aggregated salting* (pre-aggregate dengan kunci terdistribusi acak, diikuti final aggregation) pada structured streaming stateful.
3. Rancang rencana pemulihan otomatis (*failover & backpressure handling*) saat cluster mengalami lonjakan data tak terduga (*burst traffic*).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1. Pertanyaan Basic (Pilihan Ganda)
1. Apa fungsi utama dari Catalyst Optimizer pada Apache Spark?
   - A. Mengalokasikan RAM fisik di setiap Worker Node secara manual.
   - B. Mentransformasikan ekspresi logika data menjadi rencana fisik eksekusi yang optimal.
   - C. Mengonversi bytecode Python ke dalam instruksi assembly C++.
   - D. Menghapus log commit yang sudah usang pada sistem file terdistribusi.

2. Komponen internal Spark yang mengelola memori langsung secara off-heap guna menghindari overhead JVM Garbage Collection adalah...
   - A. Dynamic Allocation Manager
   - B. Tungsten Engine
   - C. RocksDB Engine
   - D. Py4J Gateway

3. Format file standar yang menjadi fondasi penyimpanan data kolumnar pada Delta Lake dan Apache Iceberg adalah...
   - A. CSV terkompresi BZIP2
   - B. Apache Avro
   - C. Apache Parquet
   - D. JSON L-Line

4. Mekanisme apa yang digunakan Delta Lake untuk menangani konflik penulisan konkuren?
   - A. Pessimistic Table Locks
   - B. Two-Phase Commit Protocol
   - C. Optimistic Concurrency Control (OCC)
   - D. Semaphore berbasis Distributed ZooKeeper

5. Dalam Spark Structured Streaming, fungsi utama dari konfigurasi `withWatermark()` adalah...
   - A. Mengurangi kualitas kompresi file output untuk mempercepat penulisan.
   - B. Menentukan batas ambang keterlambatan penerimaan data historis (*late data*) sebelum state dibersihkan dari memori.
   - C. Menyinkronkan waktu sistem operasi executor dengan jam NTP global.
   - D. Menandai checkpoint log dengan hash MD5.

### 15.2. Pertanyaan Intermediate (Pilihan Ganda)
6. Manakah pernyataan yang BENAR mengenai perbedaan mendasar antara *Sort-Merge Join* (SMJ) dan *Broadcast Hash Join* (BHJ)?
   - A. SMJ tidak pernah memicu disk-spill pada executor.
   - B. BHJ tidak memerlukan proses *data shuffle* antar worker node, tetapi membutuhkan alokasi memori yang cukup di Driver dan Executor untuk menampung seluruh tabel dimensi.
   - C. SMJ hanya bisa digunakan pada dataset dengan ukuran data di bawah 10 MB.
   - D. BHJ mewajibkan kedua dataset memiliki kolom partisi yang identik sebelum proses join.

7. Perintah `VACUUM` pada Delta Lake secara default tidak mengizinkan retensi data di bawah 168 jam (7 hari). Alasan teknis di balik pembatasan ini adalah...
   - A. Kapasitas memori Spark tidak mampu membaca file log yang berumur kurang dari 7 hari.
   - B. Menghindari terhapusnya file data yang masih aktif dibaca oleh transaksi query jangka panjang atau job streaming yang sedang berjalan.
   - C. Memastikan integritas lisensi open-source Delta Lake tetap valid.
   - D. Pembatasan teknis dari protokol Amazon S3 Lifecycle API.

8. Pada kasus data skewing saat melakukan grouping berdasarkan kolom berkardinalitas rendah yang timpang, teknik apakah yang paling tepat diterapkan pada data pipeline?
   - A. Menurunkan nilai `spark.sql.shuffle.partitions` menjadi 1.
   - B. Menerapkan *Salting Technique* dengan menambahkan angka acak ke kunci partisi sebelum proses agregasi.
   - C. Mengubah format file penyimpanan dari Parquet ke JSON.
   - D. Mematikan fitur Whole-Stage Code Generation.

9. Apa fungsi file `.checkpoint.parquet` yang terbentuk secara berkala di dalam direktori `_delta_log/`?
   - A. Menyimpan backup data transaksi jika hard disk executor rusak.
   - B. Mengonsolidasikan kumpulan log mutasi transaksi JSON sebelumnya agar status tabel terkini dapat dibaca lebih cepat tanpa membaca seluruh file JSON dari awal.
   - C. Menjadi file penampung data yang gagal divalidasi skemanya.
   - D. Berisi bytecode eksekusi Scala yang siap dipanggil driver.

10. Ketika job Spark Structured Streaming menggunakan sink Delta Lake terhenti mendadak (*crash*), integritas data tetap terjamin (*Exactly-Once*) saat *restart* karena...
    - A. Kafka secara otomatis menghapus record data yang gagal diproses.
    - B. Kombinasi offset Kafka yang tercatat pada direktori *checkpoint* sinkron secara atomik dengan file transaksi di `_delta_log/`.
    - C. Spark akan memutar balik (*rollback*) seluruh sistem operasi ke status satu jam sebelumnya.
    - D. Executor lokal menyimpan image state memori ke dalam swap space.

### 15.3. Skenario Kasus Produksi (Analisis & Esai Singkat)
11. **Skenario 1 (Root Cause Analysis - Production Failure):**
    Sebuah pipeline ekstraksi fitur batch berjalan normal selama 6 bulan. Tiba-tiba, proses komputasi harian gagal dengan pesan error: `org.apache.spark.shuffle.MetadataFetchFailedException: Missing an output location for shuffle`. Saat dilakukan penelusuran pada log Executor, ditemukan entri fatal `Container killed by YARN for exceeding memory limits. 8.2 GB of 8 GB physical memory used`. Analisis akar masalah teknis kegagalan ini dan tentukan 2 konfigurasi terpenting untuk menstabilkan kembali pipeline tersebut.
12. **Skenario 2 (Architectural Design - Vector Indexing Sync):**
    Perusahaan Anda meluncurkan fitur *Semantic Search* berbasis AI di atas katalog produk yang memiliki 50 juta SKU. Setiap kali harga, deskripsi, atau ketersediaan stok berubah di database relasional, *vector embeddings* pada Qdrant Vector DB dan atribut filter pada Delta Lake harus diperbarui dalam batas latensi maksimal 30 detik. Rancang alur arsitektur streaming terdistribusi yang menjamin *eventual consistency* antar sistem ini.
13. **Skenario 3 (Cost Optimization vs SLA):**
    Sebuah pipeline Delta Lake pada AWS EMR menghabiskan biaya komputasi yang tinggi akibat alokasi 100 node `c5.4xlarge` yang aktif 24/7. Monitoring menunjukkan utilisasi CPU rata-rata hanya berada di angka 18%, namun memori sering mengalami lonjakan tajam saat proses agregasi per jam berjalan. Rekomendasikan perubahan arsitektur komputasi, konfigurasi sizing node (*instance family*), dan tuning Spark untuk memangkas biaya cloud minimal 40% tanpa menurunkan SLA latensi data.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### 15.1. Basic
1. **B** — Catalyst Optimizer bertugas mengoptimasi logical plan menjadi physical execution plan berbasis aturan (*rule-based*) dan biaya (*cost-based*).
2. **B** — Tungsten Engine mengelola alokasi memori secara raw binary (off-heap via unsafe memory API) untuk mengeliminasi overhead GC.
3. **C** — Format Parquet menjadi standar kompresi kolumnar yang digunakan Delta Lake maupun Apache Iceberg.
4. **C** — Optimistic Concurrency Control (OCC) memvalidasi transaksi pada saat commit; transaksi akan diulang jika terjadi tumpang tindih mutasi data.
5. **B** — Watermarking membatasi seberapa lama Spark mempertahankan status event lama di memori internal sebelum dibersihkan.

#### 15.2. Intermediate
6. **B** — BHJ menyalin dataset kecil ke setiap executor sehingga menghilangkan proses pertukaran data (shuffle), namun memerlukan memori driver/executor yang memadai untuk menampung dataset tersebut.
7. **B** — Retensi default mencegah penghapusan file aktif yang berpotensi memicu kegagalan pembacaan (*file not found*) pada transaksi query yang masih aktif.
8. **B** — Penambahan *salt* (nilai acak) mendistribusikan kunci bernilai sama ke dalam partisi-partisi yang berbeda, mencegah pembebanan berlebih pada satu task.
9. **B** — File checkpoint Parquet memadatkan riwayat ratusan file log transaksi JSON menjadi satu snapshot metadata siap baca.
10. **B** — Transaksionalitas Delta Lake bersama pencatatan offset stateful pada checkpoint Spark menjamin idempotensi penulisan data stream.

#### 15.3. Panduan Evaluasi Kasus Produksi
11. **Analisis Skenario 1:**
    - *Akar Masalah:* Terjadi *Shuffle Fetch Failure* karena Executor yang bertugas menyajikan data shuffle lokal telah dimatikan secara paksa oleh YARN/Kubernetes akibat alokasi memori fisik melampaui batas batas ambang (`spark.executor.memory` + `spark.executor.memoryOverhead`). Hal ini umumnya dipicu oleh ukuran partisi data yang membengkak seiring waktu (*data growth*) sehingga agregasi membutuhkan alokasi off-heap berlebih.
    - *Solusi Konfigurasi:*
      1. Naikkan alokasi overhead memori: `spark.executor.memoryOverhead = 2048m` (atau 25% dari base memory).
      2. Skalakan jumlah partisi shuffle: Naikkan `spark.sql.shuffle.partitions` dari nilai default 200 menjadi 1000–2000, atau aktifkan `spark.sql.adaptive.enabled=true` dan `spark.sql.adaptive.coalescePartitions.enabled=true`.
12. **Analisis Skenario 2:**
    - Gunakan pola *Transactional Outbox Pattern* pada database relasional yang ditangkap menggunakan Debezium CDC dan diteruskan ke Apache Kafka.
    - Dari Kafka, bagi aliran data menjadi dua arah pemrosesan melalui Spark Structured Streaming:
      1. Menulis data mentah dan data terstruktur langsung ke Delta Lake Silver Table (menggunakan operasi `MERGE INTO`).
      2. Mengarahkan data perubahan teks deskripsi produk ke service *Embedding Generation* berbasis kluster asynchronous (seperti worker Ray/vLLM), yang kemudian memperbarui index embedding pada Vector Database secara batch dengan identik ID produk (`product_id`).
    - Gunakan versioning berbasis `updated_at` timestamp untuk menjaga konsistensi state data pada kedua penyimpanan.
13. **Analisis Skenario 3:**
    - *Perubahan Arsitektur & Compute Sizing:*
      1. Beralih dari compute-optimized instance (`c5.4xlarge`) ke memory-optimized instance (`r5.2xlarge` atau Graviton-based `r6g.2xlarge`). Hal ini menjawab masalah *memory spike* dengan rasio RAM:vCPU yang lebih tinggi per dolar biaya.
      2. Implementasikan *Auto-scaling Spark on Kubernetes* atau EMR Managed Scaling dengan alokasi instance Spot hingga 70% untuk worker node, sementara node master/driver tetap menggunakan instance On-Demand.
      3. Ubah pipeline streaming interval rendah yang idle menjadi *scheduled batch* berkala per 15-30 menit (*Trigger.AvailableNow*) jika SLA latensi bisnis mengizinkan toleransi hingga level menit.

---

## 16. Summary
Modul ini mengupas tuntas arsitektur komputasi terdistribusi tingkat lanjut untuk AI Data Science:
- **Optimasi Mesin Spark:** Melalui pemahaman mendalam atas *Catalyst Optimizer* dan alokasi memori internal *Tungsten*, data engineer dan data scientist dapat mendesain query yang menghindari *shuffle disk spill* dan kegagalan alokasi memori JVM.
- **Arsitektur Lakehouse Modern:** Delta Lake menghadirkan transaksi ACID yang stabil di atas *object storage*, memecahkan problem latensi metadata melalui file transaksi JSON dan *checkpoint compaction*, serta menjamin idempotensi data masukan.
- **Streaming Handal untuk Pipeline AI:** Penggabungan Apache Kafka, pemrosesan berbasis *watermarking*, penanganan *data skew* via *adaptive query execution*, serta integrasi *feature store/vector database* menjadi fondasi penting dalam penerapan sistem AI enterprise berskala petabyte yang tangguh dan efisien.