# Bab 02: Modern Data Engineering & Distributed Analytics
## Modul 01: Lakehouse Storage Engines & Distributed Vectorized Compute for Scalable AI/ML Pipelines

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

*   **Menganalisis dan Memilih Storage Format Modern:** Mengevaluasi perbedaan internal antara format penyimpanan kolumnar (*Apache Parquet*, *ORC*) dan row-oriented (*Avro*) berbasis metrik kompresi, *I/O throughput*, serta kemampuan *predicate pushdown*.
*   **Merancang Metadata Architecture Lakehouse:** Mengimplementasikan spesifikasi tabel modern (*Apache Iceberg*, *Delta Lake*) yang mendukung ACID transactions, time-travel, hidden partitioning, dan snapshot isolation untuk training set reproducibility.
*   **Mengoptimalkan Distributed Execution Engine:** Mengonfigurasi engine komputasi terdistribusi (*Apache Spark*, *DuckDB*, *Apache Arrow*) dengan memanfaatkan *Catalyst Optimizer*, *Adaptive Query Execution (AQE)*, dan eksekusi tervektorisasi berbasis SIMD.
*   **Membangun Pipeline Data Skala Petabyte yang Resilient:** Menulis pipeline fitur AI/ML end-to-end dengan penanganan data skew, OOM (Out Of Memory) prevention, handling dynamic schema evolution, dan idempotency guarantees.

---

### 2. Concept Overview (Mental Model & Teori Inti)

#### Mental Model: The Decoupled Compute-Storage & Metadata Paradigm
Sistem data enterprise modern memisahkan lapisan penyimpanan (*Object Storage* seperti S3, GCS, MinIO) dari lapisan komputasi (*Stateless Compute* seperti Spark, Trino, DuckDB). Paradigma ini mengatasi keterbatasan skalabilitas vertikal pada Data Warehouse tradisional dan mengeliminasi fenomena *Data Swamp* pada Data Lake generasi pertama.

```
+-----------------------------------------------------------------------+
|                         AI / ML Workloads                             |
|         (Feature Store, Training Jobs, Batch Inference, Ray)          |
+-----------------------------------------------------------------------+
                                  │
                  Vectorized In-Memory (Apache Arrow)
                                  │
+-----------------------------------------------------------------------+
|                    Vectorized Compute Engines                         |
|     (Apache Spark AQE / DuckDB / Trino Engine / Polars Engine)       |
+-----------------------------------------------------------------------+
                                  │
                     Metadata & Transaction Layer
              (ACID, Time-Travel, Snapshot Isolation)
             [Apache Iceberg / Delta Lake / Apache Hudi]
                                  │
+-----------------------------------------------------------------------+
|                      Immutable Storage Format                         |
|                  (Apache Parquet, Snappy/ZSTD)                        |
+-----------------------------------------------------------------------+
                                  │
+-----------------------------------------------------------------------+
|                       Physical Storage Layer                          |
|             (AWS S3 / GCS / Azure Data Lake Storage / MinIO)          |
+-----------------------------------------------------------------------+
```

#### Teori Inti:
1.  **Columnar Layout vs. Row-Oriented:**
    *   *Row-oriented (Avro, CSV, JSON):* Menyimpan data berurutan per baris ($R_1C_1, R_1C_2, \dots, R_2C_1, R_2C_2$). Optimal untuk OLTP (*high-frequency single-record inserts/updates*).
    *   *Columnar (Parquet, ORC):* Menyimpan data berurutan per kolom ($C_1R_1, C_1R_2, \dots, C_2R_1, C_2R_2$). Mengizinkan *projection pushdown* (hanya membaca kolom yang diperlukan fitur ML) dan rasio kompresi tinggi (Run-Length Encoding, Dictionary Encoding) karena tipe data seragam dalam satu blok fisik.
2.  **Vectorized In-Memory Execution (Apache Arrow):**
    *   Model pemrosesan tradisional (*Volcano Iterator Model*) mengeksekusi instruksi per tuple/record (`next()` call), memicu tingginya *CPU instruction cache miss*.
    *   Vectorized Execution memproses data dalam representasi *in-memory columnar array batch* menggunakan instruksi SIMD (*Single Instruction, Multiple Data*), meminimalkan latensi CPU dan menghilangkan overhead serialisasi/deserialisasi (*Zero-Copy* memory transfers).
3.  **Lakehouse ACID Layer:**
    *   Menghilangkan ketergantungan pada direktori fisik storage melalui representasi tabel berbasis metadata hierarkis (*manifest files* & *snapshot trees*).
    *   Memungkinkan mutasi data secara konsisten (*Serializability* / *Snapshot Isolation*) menggunakan mekanisme *Copy-on-Write (CoW)* atau *Merge-on-Read (MoR)*.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada level enterprise, machine learning sering kali gagal bukan karena algoritma modelnya, melainkan karena kelemahan infrastruktur data:

*   **Training-Serving Skew & Reproducibility Crisis:** Tanpa time-travel dan snapshot isolation, mustahil mengisolasi dataset yang persis sama dengan dataset yang digunakan untuk melatih model ML 6 bulan lalu saat audit compliance (seperti regulasi perbankan atau GDPR).
*   **The Small Files Problem:** Ingesti data streaming berskala masif menghasilkan jutaan file berukuran beberapa kilobyte di S3/GCS. Hal ini membebani metadata *Object Storage* (API rate limits, list object latency) dan memicu crash *Spark Driver OOM* saat merencanakan *Query Plan*.
*   **High GPU Idle Time:** Pipeline pelatihan PyTorch/TensorFlow terhambat oleh I/O throughput data loader. Membaca data mentah tak teroptimasi dari object store mengakibatkan GPU utilization turun drastis di bawah 30%.
*   **GDPR / Right to be Forgotten Compliance:** Menghapus data spesifik dari immutable object storage tanpa arsitektur Lakehouse mengharuskan penulisan ulang seluruh partisi atau dataset, memakan resource komputasi dan biaya I/O yang sangat masif.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur internal spesifikasi tabel Apache Iceberg yang berinteraksi dengan Distributed Compute Engine (Spark) dan Vectorized Processing (Arrow):

```
                                  CATALOG
               (AWS Glue / Hive Metastore / Nessie / REST)
                                     │
                                     ▼ Points to current metadata pointer
                        +──────────────────────────+
                        |  v3.metadata.json        |
                        +──────────────────────────+
                                     │
                                     ├───────────────────────────────┐
                                     ▼ Snapshot S1                   ▼ Snapshot S0
                        +──────────────────────────+    +──────────────────────────+
                        | Snap-1.avro (ManifestList|    | Snap-0.avro (ManifestList|
                        +──────────────────────────+    +──────────────────────────+
                                     │
                         ┌───────────┴───────────┐
                         ▼                       ▼
            +─────────────────────────+ +─────────────────────────+
            | Manifest-A.avro         | | Manifest-B.avro         |
            | (Data Files Metadata)   | | (Data Files Metadata)   |
            +─────────────────────────+ +─────────────────────────+
                         │                       │
              ┌──────────┴──────────┐            └──────────┐
              ▼                     ▼                       ▼
      +───────────────+     +───────────────+       +───────────────+
      |  part-1.parquet|    |  part-2.parquet|       |  part-3.parquet|
      |  Stats:       |     |  Stats:       |       |  Stats:       |
      |  ts: [t0, t1] |     |  ts: [t2, t3] |       |  ts: [t4, t5] |
      +───────────────+     +───────────────+       +───────────────+

=============================================================================
                      COMPUTE LAYER EXECUTION PATH
=============================================================================

 Client Query: SELECT user_id, AVG(amount) FROM tx WHERE ts >= 't2' AND ts <= 't3'
                                     │
 1. Metadata Pruning ───────────────┘  (Catalog -> Manifest List -> Manifest)
    Result: Only scan part-2.parquet (Eliminate part-1 and part-3 completely!)
                                     │
 2. Parallel Fetch                   ▼
                      +───────────────────────────────+
                      | PySpark Driver (Catalyst AQE) |
                      +───────────────────────────────+
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
+─────────────────────────────────────+   +─────────────────────────────────────+
| Spark Executor 1                    |   | Spark Executor 2                    |
| - Scan: Pushdown Predicate (ts)     |   | - Scan: Pushdown Predicate (ts)     |
| - Projection: Read [user_id, amount]|   | - Projection: Read [user_id, amount]|
| - Parquet -> Arrow RecordBatch      |   | - Parquet -> Arrow RecordBatch      |
| - SIMD Vectorized Aggregation       |   | - SIMD Vectorized Aggregation       |
+─────────────────────────────────────+   +─────────────────────────────────────+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Anatomi Parquet: Dictionary Encoding & Bit-Packing
Struktur fisik Parquet dirancang hierarkis:
1.  **File:** Terdiri atas satu atau lebih *Row Groups*.
2.  **Row Group:** Kumpulan baris data yang dialokasikan ke memori (default: 128MB - 512MB).
3.  **Column Chunk:** Data untuk kolom tertentu dalam suatu Row Group.
4.  **Page:** Unit terkecil untuk kompresi dan encoding (biasanya 1MB).
    *   *Data Page:* Menyimpan nilai terkompresi (misal: ZSTD).
    *   *Dictionary Page:* Memetakan nilai unik integer kecil ke string aktual (mengurangi string redundan menjadi integer 1, 2, 4 bytes).
    *   *Repetition & Definition Levels (Dremel Encoding):* Mengkodekan nullability dan struktur nested/array secara efisien tanpa deserialisasi objek penuh.

#### B. Catalyst Optimizer & Adaptive Query Execution (AQE) di Apache Spark
Siklus kompilasi query Spark:
$$\text{Unresolved Logical Plan} \xrightarrow{\text{Catalog}} \text{Analyzed Logical Plan} \xrightarrow{\text{Rules}} \text{Optimized Logical Plan} \xrightarrow{\text{Physical Planning}} \text{Physical Plans} \xrightarrow{\text{Cost Model}} \text{Selected Physical Plan} \xrightarrow{\text{Tungsten CodeGen}} \text{Java Bytecode}$$

*Adaptive Query Execution (AQE)* mengevaluasi statistik data *secara runtime* di antara tahapan *Shuffle*:
*   **Dynamically Coalescing Shuffle Partitions:** Menggabungkan partisi-partisi kecil paska shuffle untuk menghindari overhead scheduling task.
*   **Dynamically Converting Sort-Merge Join to Broadcast Join:** Jika salah satu sisi join paska filter terbukti berukuran di bawah ambang batas (default 10MB), Spark mengubah algoritma join runtime ke *Broadcast Hash Join*, menghilangkan transfer data jaringan yang mahal.
*   **Dynamically Handling Skew Join:** Memecah partisi yang mengalami skew (data outlier terpusat pada satu key) menjadi sub-partisi yang lebih kecil dan mereplikasi pasangan join-nya.

#### C. Apache Arrow Memory Layout
Apache Arrow merepresentasikan struktur in-memory secara kontinu dan terstandarisasi antar bahasa (C++, Python, Java, Rust).
*   **Contiguous Memory Allocation:** Array numerik diletakkan berdampingan di RAM tanpa pointer indirection. Membaca array sepanjang $N$ elemen diakses secara sequential melalui register CPU cache ($L1/L2$).
*   **Validity Bitmaps:** Menyimpan status null/not-null per elemen dalam bentuk bitmask (1 bit per nilai), menghemat memori dibanding menggunakan boxing object (*pointer to null*).
*   **Zero-Copy Serialization:** Mengirim dataset antar proses (misalnya: dari Spark Executor JVM ke PyTorch C++ Runtime via Arrow Flight) tidak memerlukan alokasi memori tambahan atau rekonstruksi objek. Alamat pointer memori dilewatkan secara langsung melalui IPC shared memory.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul pemrosesan data lakehouse enterprise menggunakan **PySpark** dengan backend **Delta/Iceberg-ready architectural patterns**. Kode ini mengabstraksi ingestion, snapshot retention, handling schema evolution, serta optimasi write-path.

```python
"""
Module: lakehouse_feature_pipeline.py
Author: Principal Data Architect & AI Engineer
Description: Production-ready Lakehouse extraction, transformation, and ingestion 
pipeline with ACID compliance, dynamic partitioning, and data validation.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.window import Window
from pyspark.errors import PySparkException

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LakehouseFeaturePipeline")


# ---------------------------------------------------------------------------
# Configurations & Data Classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LakehouseConfig:
    table_name: str
    base_uri: str
    checkpoint_location: str
    partition_keys: List[str]
    zorder_columns: List[str]
    enable_aqe: bool = True
    shuffle_partitions: int = 200


# ---------------------------------------------------------------------------
# Spark Session Factory
# ---------------------------------------------------------------------------
class SparkSessionFactory:
    """Menginisialisasi SparkSession dengan konfigurasi Lakehouse & Adaptive Query Execution."""

    @staticmethod
    def create_session(app_name: str, config: LakehouseConfig) -> SparkSession:
        try:
            builder = (
                SparkSession.builder.appName(app_name)
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config(
                    "spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog",
                )
                # Adaptive Query Execution Tuning
                .config("spark.sql.adaptive.enabled", str(config.enable_aqe).lower())
                .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
                .config("spark.sql.adaptive.skewJoin.enabled", "true")
                .config("spark.sql.shuffle.partitions", str(config.shuffle_partitions))
                # Parquet & Arrow Optimizations
                .config("spark.sql.execution.arrow.pyspark.enabled", "true")
                .config("spark.sql.parquet.filterPushdown", "true")
                .config("spark.sql.parquet.enableVectorizedReader", "true")
            )
            spark = builder.getOrCreate()
            spark.sparkContext.setLogLevel("WARN")
            logger.info("SparkSession berhasil diinisialisasi dengan AQE & Vectorized Reader.")
            return spark
        except Exception as e:
            logger.critical(f"Gagal menginisialisasi SparkSession: {str(e)}", exc_info=True)
            raise RuntimeError(f"Spark Initialization Error: {e}") from e


# ---------------------------------------------------------------------------
# Feature Pipeline Pipeline Processor
# ---------------------------------------------------------------------------
class LakehousePipeline:
    """Mengelola transformasi, penjaminan kualitas data, dan ingestion idempotensi."""

    def __init__(self, spark: SparkSession, config: LakehouseConfig) -> None:
        self.spark = spark
        self.config = config

    def extract_bronze(self, source_path: str, format_type: str = "parquet") -> DataFrame:
        """Ekstraksi data mentah dengan dynamic error handling."""
        logger.info(f"Mengekstraksi data dari {source_path} format {format_type}")
        try:
            df = self.spark.read.format(format_type).load(source_path)
            if df.rdd.isEmpty():
                logger.warning(f"Data source di {source_path} kosong.")
            return df
        except PySparkException as p_err:
            logger.error(f"PySpark error saat ekstraksi: {p_err.getMessage()}")
            raise
        except Exception as e:
            logger.error(f"System I/O error saat mengakses storage: {str(e)}")
            raise

    def transform_features(self, raw_df: DataFrame) -> DataFrame:
        """
        Transformasi Silver Layer:
        - Penanganan Deduplikasi berbasis event_time
        - Ekstraksi Temporal Feature untuk ML
        - Imputasi dan deteksi anomali skala terdistribusi
        """
        logger.info("Memulai transformasi data Silver Layer...")

        # Validasi schema minimum
        required_columns = {"transaction_id", "user_id", "timestamp", "amount"}
        missing_cols = required_columns - set(raw_df.columns)
        if missing_cols:
            raise ValueError(f"Schema drift error: Kolom hilang: {missing_cols}")

        # Window Specification untuk deduplikasi (Deduplication pattern)
        dedup_window = Window.partitionBy("transaction_id").orderBy(
            F.col("timestamp").desc()
        )

        cleaned_df = (
            raw_df.withColumn("row_num", F.row_number().over(dedup_window))
            .filter(F.col("row_num") == 1)
            .drop("row_num")
            .filter(F.col("amount") >= 0.0)  # Filter invalid records
            .filter(F.col("user_id").isNotNull())
        )

        # Feature Extraction: Vectorized Native Spark Operations
        transformed_df = (
            cleaned_df.withColumn("event_timestamp", F.to_timestamp(F.col("timestamp")))
            .withColumn("date_key", F.to_date(F.col("event_timestamp")))
            .withColumn("log_amount", F.log1p(F.col("amount")))
            .withColumn(
                "is_high_value",
                F.when(F.col("amount") > 10000.0, 1.0).otherwise(0.0),
            )
        )

        return transformed_df

    def write_silver_layer_acid(self, df: DataFrame, mode: str = "append") -> None:
        """
        Menulis output terstruktur ke Lakehouse Table dengan ACID Merge / Append.
        Memanfaatkan schema merging dan partisi teroptimasi.
        """
        target_path = os.path.join(self.config.base_uri, self.config.table_name)
        logger.info(f"Menulis data ke Lakehouse path: {target_path} (Mode: {mode})")

        try:
            writer = (
                df.write.format("delta")
                .mode(mode)
                .option("mergeSchema", "true")
                .option("checkpointLocation", self.config.checkpoint_location)
                .partitionBy(*self.config.partition_keys)
            )

            writer.save(target_path)
            logger.info("Write transaction berhasil dicatat ke snapshot metadata.")

            # Optimasi file pasca penulisan (Compaction & Layout Clustering)
            self._optimize_table(target_path)

        except PySparkException as pse:
            logger.critical(f"Transaksi gagal saat write ke Delta Lake: {pse.getMessage()}")
            raise
        except Exception as e:
            logger.critical(f"Kesalahan fatal selama persistence: {str(e)}")
            raise

    def _optimize_table(self, table_path: str) -> None:
        """Menjalankan file compaction dan Z-Ordering untuk read path pruning."""
        try:
            from delta.tables import DeltaTable

            if DeltaTable.isDeltaTable(self.spark, table_path):
                logger.info("Menjalankan compaction dan Z-Ordering layout...")
                delta_table = DeltaTable.forPath(self.spark, table_path)

                # Jalankan Bin-Packing Optimization & Z-Order pada kolom filtering
                zorder_cols = ", ".join(self.config.zorder_columns)
                self.spark.sql(
                    f"OPTIMIZE delta.`{table_path}` ZORDER BY ({zorder_cols})"
                )
                logger.info("Optimasi tabel selesai.")
        except Exception as err:
            logger.warning(f"Gagal menjalankan optimize (non-fatal): {str(err)}")

    def read_time_travel_snapshot(
        self, version_as_of: Optional[int] = None, timestamp_as_of: Optional[str] = None
    ) -> DataFrame:
        """Ekstraksi dataset deterministik berbasis versi snapshot untuk reproducibility audit."""
        target_path = os.path.join(self.config.base_uri, self.config.table_name)
        reader = self.spark.read.format("delta")

        if version_as_of is not None:
            logger.info(f"Membaca snapshot historis versi: {version_as_of}")
            reader = reader.option("versionAsOf", version_as_of)
        elif timestamp_as_of is not None:
            logger.info(f"Membaca snapshot historis timestamp: {timestamp_as_of}")
            reader = reader.option("timestampAsOf", timestamp_as_of)

        return reader.load(target_path)


# ---------------------------------------------------------------------------
# Execution Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app_config = LakehouseConfig(
        table_name="customer_features_silver",
        base_uri="/tmp/lakehouse/silver",
        checkpoint_location="/tmp/lakehouse/checkpoints/silver",
        partition_keys=["date_key"],
        zorder_columns=["user_id"],
        enable_aqe=True,
        shuffle_partitions=4,  # Skala lokal untuk contoh
    )

    spark_instance = SparkSessionFactory.create_session("LakehousePipelineProd", app_config)
    pipeline = LakehousePipeline(spark_instance, app_config)

    # 1. Simulasi Data Mentah (Bronze In-Memory Data)
    sample_data = [
        ("tx_001", "usr_A", "2023-10-01 10:00:00", 1500.50),
        ("tx_002", "usr_B", "2023-10-01 10:05:00", 450.00),
        ("tx_001", "usr_A", "2023-10-01 10:00:00", 1500.50),  # Duplikat eksplisit
        ("tx_003", "usr_C", "2023-10-01 11:20:00", -50.00),    # Anomali data kotor (amount negatif)
        ("tx_004", "usr_A", "2023-10-02 08:30:00", 12500.00),  # High value transaction
    ]

    schema = T.StructType([
        T.StructField("transaction_id", T.StringType(), False),
        T.StructField("user_id", T.StringType(), False),
        T.StructField("timestamp", T.StringType(), False),
        T.StructField("amount", T.DoubleType(), False),
    ])

    raw_data_df = spark_instance.createDataFrame(sample_data, schema=schema)
    raw_staging_path = "/tmp/lakehouse/bronze/transactions"
    raw_data_df.write.mode("overwrite").parquet(raw_staging_path)

    # 2. Pipeline Execution
    try:
        # Step A: Ingestion dari Bronze
        bronze_df = pipeline.extract_bronze(raw_staging_path)

        # Step B: Transformasi & Validasi Fitur
        silver_features = pipeline.transform_features(bronze_df)

        # Step C: ACID Upsert ke Silver Layer
        pipeline.write_silver_layer_acid(silver_features, mode="append")

        # Step D: Verifikasi Hasil Transformasi
        logger.info("Menampilkan hasil pembacaan tabel Silver:")
        result_df = spark_instance.read.format("delta").load(
            os.path.join(app_config.base_uri, app_config.table_name)
        )
        result_df.show(truncate=False)

        # Step E: Validasi Time-Travel Capability
        historical_df = pipeline.read_time_travel_snapshot(version_as_of=0)
        logger.info(f"Total row pada snapshot versi 0: {historical_df.count()}")

    except Exception as pipeline_error:
        logger.fatal(f"Pipeline eksekusi terminated abnormally: {pipeline_error}")
        sys.exit(1)
    finally:
        spark_instance.stop()
        logger.info("Spark context stopped gracefully.")
```

---

### 7. Edge Cases & Failure Modes (Error Recovery & Resilience)

1.  **Small File Problem & File Amplification:**
    *   *Gejala:* Driver OOM, metadata query planning memakan waktu bermenit-menit sebelum job mulai mengeksekusi data.
    *   *Mitigasi:*
        *   Terapkan teknik *Bin-Packing* otomatis (misal: Delta `optimize` atau Iceberg `rewrite_data_files`).
        *   Gunakan auto-tuning partition size dengan mengatur `spark.sql.files.maxPartitionBytes` (default 128MB).
2.  **Data Skew pada Shuffle Phase:**
    *   *Gejala:* 99% task Spark selesai dalam 10 detik, namun 1 task menggantung selama 2 jam (*Straggler Task*), menyebabkan *Executor Lost / Heartbeat Timeout*.
    *   *Mitigasi:*
        *   Aktifkan `spark.sql.adaptive.skewJoin.enabled=true`.
        *   *Salting Technique:* Tambahkan integer acak (0 hingga $K-1$) pada key join untuk mendistribusikan skew key ke beberapa executor berbeda, lalu join dengan data sisi kanan yang telah direplikasi (*exploded*) sebanyak $K$.
3.  **Schema Drift & Poison Pills:**
    *   *Gejala:* Job pipeline gagal mendadak akibat *Column Type Mismatch* (misalnya upstream mengubah tipe `user_id` dari Integer ke String), atau payload JSON mengandung baris malformed.
    *   *Mitigasi:*
        *   Gunakan mode schema enforcement ketat (`mergeSchema=false`) pada Gold Layer untuk melindungi model ingestion interface.
        *   Gunakan dead-letter queue (DLQ) untuk record corrupt menggunakan opsi pembacaan `columnNameOfCorruptRecord`.
4.  **Concurrent Write Conflicts:**
    *   *Gejala:* Beberapa job bersamaan menulis ke tabel yang sama menghasilkan `ConcurrentAppendException` atau `CommitFailedException`.
    *   *Mitigasi:*
        *   Rancang partisi independen antar job konkuren.
        *   Ubah isolasi transaksi ke *Serializable* atau *WriteSerializable*, dan terapkan *Exponential Backoff Retry Strategy* pada level client scheduler (misal: Airflow/Prefect).

---

### 8. Trade-offs & Alternatif Solusi

Setiap teknologi penyimpanan dan eksekusi Lakehouse memiliki karakteristik operasional yang berbeda:

#### Storage Format Layer: Apache Iceberg vs. Delta Lake vs. Apache Hudi

| Fitur / Karakteristik | Apache Iceberg | Delta Lake | Apache Hudi |
| :--- | :--- | :--- | :--- |
| **Catalog Independence** | Sangat Tinggi (Bebas catalog lock-in, didukung REST, Nessie, Glue, Hive) | Sedang (Terkoneksi kuat ke Databricks Workspace & Hive/Unity Catalog) | Rendah ke Sedang (Evolusi lambat di luar ekosistem Spark) |
| **Partitioning Strategy**| **Hidden Partitioning** (Query user tidak perlu tahu format transformasi partisi) | Explicit Partitioning (Mirip Hive, rentan human error jika query lupa filter partisi) | Explicit Partitioning |
| **Update/Delete Primary Use-Case** | Analitik analitis reguler, read-heavy, batch writes terisolasi | General Analytics, ML Pipelines, integrasi native Spark | **Near-Real-Time Streaming** (Latency rendah, ultra-fast Row-level Index upsert) |
| **Format Overhead** | Sangat rendah (Metadata murni snapshot tree JSON & Avro) | Rendah (JSON Transaction log commit + periodic checkpoint Parquet) | Cukup Tinggi (Banyak file avro log tambahan pada mode Merge-on-Read) |

#### Compute Engine Layer: Spark vs. DuckDB vs. Polars vs. Ray

| Engine | Ideal Workload Scope | Batasan Arsitektural |
| :--- | :--- | :--- |
| **Apache Spark** | Skala multi-terabyte hingga petabyte terdistribusi (*Horizontal Scale-Out*). | Overhead cluster orchestration, JVM garbage collection latency, startup cost tinggi. |
| **DuckDB** | Single-node in-process analytics (*Vertical Scale-Up*), ideal untuk unit testing, edge computing, & preprocessing cepat. | Terbatas pada memory (RAM) & swap space 1 mesin server saja. |
| **Polars (Rust Engine)**| Single-node batch feature extraction berkecepatan tinggi dengan memory safety ketat. | Tidak memiliki coordinator terdistribusi native layaknya Spark. |
| **Ray (Ray Data)** | Streaming data loader terdistribusi untuk melayani GPU nodes saat training LLM / deep learning. | Ekosistem SQL analytics dan manajemen transaksi metadata ACID belum selengkap Spark. |

---

### 9. Best Practices & Standard Industri

*   **Penerapan Medallion Architecture:**
    *   *Bronze (Raw):* Immutability murni, simpan data asli tanpa konversi format (biasanya raw json/csv/parquet dari stream atau CDC).
    *   *Silver (Cleansed/Enriched):* Deduplikasi dilakukan, schema distandarkan, missing value diimputasi, filtering dasar. Target format: Iceberg/Delta.
    *   *Gold (Feature/Aggregated):* Data siap saji untuk Model Training dan Dashboard OLAP. Nilai telah dihitung dalam format fitur numerik, terdenormalisasi, dan dioptimalkan dengan Z-Ordering.
*   **Z-Ordering & Liquid Clustering:**
    Gunakan Z-Ordering pada kolom dengan kardinalitas tinggi yang sering digunakan dalam klausa `WHERE` pada filter training set (misal: `user_id`, `merchant_id`). Hindari partisi klasik berlebihan (*over-partitioning*) seperti mempartisi data per jam atau per ID individual.
*   **Idempotency & Deterministic Backfilling:**
    Setiap write operation harus bersifat idempoten. Jika sebuah batch job dijalankan ulang dengan window waktu yang sama, state akhir data di lakehouse tidak boleh berubah atau menduplikasi record (`INSERT OVERWRITE` spesifik partisi atau `MERGE INTO`).
*   **OpenLineage & Data Observability:**
    Integrasikan emit metadata lineage (seperti standard OpenLineage) di dalam Spark listener untuk memetakan asal-usul (*provenance*) sebuah fitur model ML sampai ke tabel Bronze asalnya.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Staff AI Data Engineer di platform Fintech. Anda diminta membangun pipeline ekstraksi fitur untuk model deteksi *Fraud Transaction*. Pipeline harus:
1. Menelan data transaksi mentah berkecepatan tinggi.
2. Melakukan skema dedup dan feature enrichment (Arrow-accelerated).
3. Melakukan update ACID dan time-travel validation untuk membuktikan bahwa dataset training ML dapat di-snapshot secara deterministik.

#### Langkah-langkah Praktikum:

##### Langkah 1: Persiapan Environment
Pastikan dependensi Python terpasang di environment Anda:
```bash
pip install pyspark==3.5.0 delta-spark==3.0.0 pyarrow==14.0.1 duckdb==0.9.2
```

##### Langkah 2: Buat Pipeline Skrip Python (`lab_lakehouse_fraud.py`)
Simpan script di bawah ini:
```python
import os
import shutil
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from delta import configure_spark_with_delta_pip

def setup_spark() -> SparkSession:
    builder = (
        SparkSession.builder.appName("Lab-Fraud-Lakehouse")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()

def run_lab():
    # Setup working dir
    lakehouse_dir = "/tmp/lab_lakehouse_fraud"
    if os.path.exists(lakehouse_dir):
        shutil.rmtree(lakehouse_dir)

    spark = setup_spark()
    spark.sparkContext.setLogLevel("ERROR")
    print("\n[+] Step 1: Spark & Delta Engine Siap.")

    # 1. Ingest Batch 1 (Baseline Data)
    batch_1 = [
        ("T101", "U01", 50.0, "2024-01-01 10:00:00"),
        ("T102", "U02", 12000.0, "2024-01-01 10:05:00"),
        ("T103", "U01", 30.0, "2024-01-01 10:10:00"),
    ]
    df1 = spark.createDataFrame(batch_1, ["tx_id", "user_id", "amount", "event_time"])
    
    # Feature Engineering Sederhana
    df1_features = df1.withColumn("is_anomalous", F.when(F.col("amount") > 10000, 1).otherwise(0)) \
                      .withColumn("date_part", F.to_date(F.col("event_time")))

    print("\n[+] Step 2: Menulis Versi 0 (Snapshot 0) ke Delta Lake...")
    df1_features.write.format("delta").mode("overwrite").partitionBy("date_part").save(lakehouse_dir)

    # 2. Ingest Batch 2 (Mutasi Data: Fraud update & New Transaction)
    # T101 ternyata di-chargeback (koreksi amount), dan ada transaksi baru T104
    from delta.tables import DeltaTable
    delta_table = DeltaTable.forPath(spark, lakehouse_dir)

    batch_2 = [
        ("T101", "U01", 50.0, "2024-01-01 10:00:00", 1), # diupdate jadi anomalous flag = 1
        ("T104", "U03", 950.0, "2024-01-01 12:00:00", 0), # transaksi baru
    ]
    df2 = spark.createDataFrame(batch_2, ["tx_id", "user_id", "amount", "event_time", "is_anomalous"]) \
               .withColumn("date_part", F.to_date(F.col("event_time")))

    print("\n[+] Step 3: Melakukan ACID MERGE (Upsert) - Menciptakan Snapshot Versi 1...")
    (
        delta_table.alias("target")
        .merge(df2.alias("source"), "target.tx_id = source.tx_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )

    # 3. Verifikasi Time-Travel untuk Audit Machine Learning
    print("\n[+] Step 4: Audit Reproducibility Model Training...")
    
    # Membaca data state saat model dilatih pertama kali (Version 0)
    df_v0 = spark.read.format("delta").option("versionAsOf", 0).load(lakehouse_dir)
    print("--- DATASET TRAINING VERSI 0 (Model v1 Baseline) ---")
    df_v0.select("tx_id", "user_id", "amount", "is_anomalous").show()

    # Membaca data state terkini (Version 1)
    df_v1 = spark.read.format("delta").option("versionAsOf", 1).load(lakehouse_dir)
    print("--- DATASET AUDIT VERSI 1 (Current State Paska Fraud Retagging) ---")
    df_v1.select("tx_id", "user_id", "amount", "is_anomalous").show()

    # 4. Zero-Copy Interop: Transfer Hasil Lakehouse ke DuckDB untuk Local Analytics
    import duckdb
    print("\n[+] Step 5: Eksekusi DuckDB Vectorized Query langsung di atas Parquet Delta:")
    duckdb_conn = duckdb.connect()
    # Baca physical parquet files yang dihasilkan Delta
    duckdb_res = duckdb_conn.execute(
        f"SELECT is_anomalous, count(*), AVG(amount) as avg_amt FROM parquet_scan('{lakehouse_dir}/**/*.parquet') GROUP BY is_anomalous"
    ).df()
    print(duckdb_res)

    spark.stop()
    print("\n[SUCCESS] Lab selesai: Deterministic time-travel & Lakehouse compute terverifikasi.")

if __name__ == "__main__":
    run_lab()
```

##### Langkah 3: Eksekusi dan Verifikasi Lab
Jalankan file script tersebut:
```bash
python lab_lakehouse_fraud.py
```

##### Kriteria Keberhasilan:
1. Folder `/tmp/lab_lakehouse_fraud/_delta_log/` terisi commit file JSON (`00000000000000000000.json` dan `00000000000000000001.json`).
2. Script berhasil mencetak state data Versi 0 (di mana `T101` bernilai `is_anomalous = 0`) dan state Versi 1 (di mana `T101` bernilai `is_anomalous = 1`).
3. DuckDB mampu memindai partisi Parquet lakehouse secara native tanpa memicu read-write locking error.