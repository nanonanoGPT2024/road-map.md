# Module 01: Spark Architecture & Execution Plan Deep Dive

## 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendekonstruksi Lifecycle Query Execution Spark Engine**: Memetakan transformasi kode dari *Unresolved Logical Plan*, *Analyzed Logical Plan*, *Optimized Logical Plan*, hingga *Physical Plan* dan *Tungsten Code Generation*.
- **Mendiagnosis Execution Plan**: Menganalisis output `.explain(extended=True)` dan Spark UI SQL DAG untuk mendeteksi *bottleneck* performa (*Shuffle*, *Spill*, *Exchange*, dan *Cartesian Product*).
- **Mengoptimalkan Tungsten Memory & Execution Engine**: Mengonfigurasi parameter memori *On-heap* dan *Off-heap* guna meminimalkan *Garbage Collection (GC) pauses* dan memaksimalkan *CPU cache locality*.
- **Memitigasi Masalah Performa Terdistribusi**: Mengidentifikasi dan menyelesaikan *Data Skew*, *Shuffle Fetch Failed Exceptions*, dan *OOM (Out-Of-Memory)* pada Driver maupun Executor secara terprogram.
- **Mengontrol Adaptive Query Execution (AQE)**: Mengonfigurasi dan memvalidasi *Dynamic Partition Coalescing*, *Dynamic Join Switching*, serta *Skew Join Optimization* pada beban kerja produksi.

---

## 2. Concept Overview (Mental Model & Teori Inti)

Apache Spark bukan sekadar abstraksi *MapReduce* di dalam memori; Spark adalah sebuah **Distributed Query Compiler & Runtime Execution Engine**.

```
+-----------------------------------------------------------------------------------+
|                                Spark Core Engine                                  |
|                                                                                   |
|  [ User Code: Python/Scala/SQL ]                                                  |
|               |                                                                   |
|               v                                                                   |
|     +--------------------+                                                        |
|     |  Catalyst Engine   | ---> Query Optimization Pipeline                       |
|     +--------------------+      (Rule-based & Cost-based Transformations)         |
|               |                                                                   |
|               v                                                                   |
|     +--------------------+                                                        |
|     |  Tungsten Engine   | ---> Hardware-level Code Generation                    |
|     +--------------------+      (Cache-aware computation, Unsafe off-heap memory) |
|               |                                                                   |
|               v                                                                   |
|  [ Distributed Task DAG ]  ---> Cluster Scheduling & Multi-core Execution         |
+-----------------------------------------------------------------------------------+
```

### Mental Model Spark Engine

1. **Lazy Evaluation sebagai Optimization Window**: Spark tidak mengeksekusi *transformations* (seperti `map`, `filter`, `join`) secara imperatif per baris. Spark mencatat deklarasi logika ini ke dalam **Directed Acyclic Graph (DAG)**. Eksekusi ditunda sampai sebuah *action* (seperti `count`, `collect`, `write`) dipanggil. Periode penundaan ini menyediakan jendela optimasi (*optimization window*) bagi optimizer internal untuk menyusun ulang pohon relasional demi efisiensi I/O dan memori.
2. **Kompilasi Deklaratif ke Imperatif (Catalyst)**: Kode relasional (SQL atau DataFrame API) ditransformasikan melalui pohon sintaks abstrak (*Abstract Syntax Tree / AST*). Catalyst Optimizer menginterpretasikan aturan logika relasional formal untuk memangkas partisi (*partition pruning*), mendorong predikat sedekat mungkin ke sumber data (*predicate pushdown*), dan memproyeksikan hanya kolom yang diperlukan (*column pruning*).
3. **Hardware-Aware Execution (Tungsten)**: Tungsten menjembatani batasan JVM (*Java Virtual Machine*). Alih-alih merepresentasikan data sebagai objek JVM yang boros *overhead* memori dan rentan terhadap *Garbage Collection overhead*, Tungsten mengelola memori secara biner murni (*raw bytes* via `sun.misc.Unsafe`), menyusun data agar muat dalam *CPU L1/L2/L3 Cache lines*, dan menghasilkan *bytecode* terkompilasi secara dinamis (*Whole-Stage Java Code Generation*).

---

## 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada lingkungan *enterprise*, inefisiensi arsitektur Spark tidak hanya memperlambat waktu pemrosesan, tetapi juga meningkatkan biaya infrastruktur komputasi *cloud* (seperti Databricks DBU, AWS EMR EC2, atau GCP Dataproc) secara eksponensial.

- **Kegagalan Akibat "Silent Spill"**: Ketika partisi data melebihi alokasi `spark.executor.memory`, Spark melakukan *spill* data ke *disk*. Performa I/O turun dari *memory-speed* (~10-20 GB/s) ke *disk-speed* (~200-500 MB/s untuk NVMe, atau lebih lambat jika menggunakan EBS). Pipeline data yang seharusnya selesai dalam hitungan menit bisa tersendat berjam-jam tanpa memunculkan status *failed*.
- **The "Straggler Task" Dilemma (Data Skew)**: Jika 99 dari 100 task selesai dalam waktu 5 detik, namun 1 task tersisa memakan waktu 45 menit, masalahnya hampir dipastikan berasal dari partisi data yang tidak seimbang (*skewed key*). Tanpa pemahaman mendalam tentang eksekusi *hash-partitioning* dan *shuffle*, *engineer* umumnya salah mendiagnosis masalah ini dengan menaikkan spesifikasi kluster (*vertical over-provisioning*), yang memicu pemborosan *cost* tanpa mengatasi akar masalah.
- **OOM pada Driver vs Executor**: 
  - *Driver OOM*: Disebabkan oleh pengambilan data besar tanpa limitasi (`.collect()`), siaran (*broadcast join*) tabel yang melebihi memori driver, atau grafik DAG yang terlalu kompleks sehingga membanjiri JVM Metaspace.
  - *Executor OOM*: Terjadi akibat ukuran buffer shuffle yang tidak mencukupi, ledakan ukuran partisi individual (*oversized single partition*), atau alokasi *memory overhead* yang tidak seimbang saat menjalankan library non-JVM (misal: Pandas/NumPy di worker).

---

## 4. Arsitektur & Diagram Komponen

### Distributed Runtime Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                         SPARK DRIVER                                               |
|                                                                                                    |
|  +--------------------+     +---------------------+     +--------------------+                     |
|  |    SparkSession    | --> |  Catalyst Optimizer | --> |   TaskScheduler    |                     |
|  |  (Logical Plan)    |     |   (Physical Plan)   |     |    (DAGScheduler)  |                     |
|  +--------------------+     +---------------------+     +--------------------+                     |
+------------------------------------------|---------------------------------------------------------+
                                           |
                                           v Cluster Manager (K8s, YARN, Standalone)
                     +---------------------+---------------------+
                     |                                           |
                     v                                           v
+-----------------------------------------+ +-----------------------------------------+
|             SPARK EXECUTOR 1            | |             SPARK EXECUTOR 2            |
|                                         | |                                         |
|  +-----------------------------------+  | |  +-----------------------------------+  |
|  | Executor JVM Memory Allocation    |  | |  | Executor JVM Memory Allocation    |  |
|  |                                   |  | |  |                                   |  |
|  |  [Reserved Memory: 300 MB]        |  | |  |  [Reserved Memory: 300 MB]        |  |
|  |  +-----------------------------+  | | |  +-----------------------------+  | |
|  |  | Spark Memory (Pool: 60%)    |  | | |  | Spark Memory (Pool: 60%)    |  | |
|  |  | - Storage (Cache/Broadcast) |  | | |  | - Storage (Cache/Broadcast) |  | |
|  |  | - Execution (Shuffle/Sort)  |  | | |  | - Execution (Shuffle/Sort)  |  | |
|  |  +-----------------------------+  | | |  +-----------------------------+  | |
|  |  | User Memory (Pool: 40%)     |  | | |  | User Memory (Pool: 40%)     |  | |
|  |  | (Custom Data Structures)    |  | | |  | (Custom Data Structures)    |  | |
|  |  +-----------------------------+  | | |  +-----------------------------+  | |
|  +-----------------------------------+  | |  +-----------------------------------+  |
|  | BlockManager (Disk & Memory Store)|  | |  | BlockManager (Disk & Memory Store)|  |
|  +-----------------------------------+  | |  +-----------------------------------+  |
|  | Off-Heap Memory (Unsafe Engine)   |  | |  | Off-Heap Memory (Unsafe Engine)   |  |
|  +-----------------------------------+  | |  +-----------------------------------+  |
|                                         | |                                         |
|   [Core 1: Task]     [Core 2: Task]     | |   [Core 1: Task]     [Core 2: Task]     |
+-----------------------------------------+ +-----------------------------------------+
```

### The Catalyst & Tungsten Compilation Pipeline

```
 [SQL Query / DataFrame Code]
              |
              v
    +-------------------+
    | Unresolved Logical | ---> Belum divalidasi dengan Catalog/Metastore
    |       Plan        |      (Skema tabel dan nama kolom belum terverifikasi)
    +-------------------+
              |
              v [Analyzer + Catalog Rules]
    +-------------------+
    |  Resolved Logical | ---> Kolom, tipe data, dan tabel terikat dengan skema resmi
    |       Plan        |
    +-------------------+
              |
              v [Optimizer Rules (Logical Optimization)]
    +-------------------+
    | Optimized Logical | ---> Pushdown predicates, prune columns, 
    |       Plan        |      constant folding, boolean simplifications
    +-------------------+
              |
              v [Spark Planner (Cost-Based Model + Strategies)]
    +-------------------+
    |   Physical Plans  | ---> Generate kandidat: HashJoin vs SortMergeJoin dsb.
    |    (Multiple)     |
    +-------------------+
              |
              v [Cost-Based Optimizer (CBO) Selection]
    +-------------------+
    | Selected Physical | ---> Memilih rencana dengan estimasi biaya I/O 
    |       Plan        |      dan memori terendah
    +-------------------+
              |
              v [Tungsten Whole-Stage Code Generation]
    +-------------------+
    | RDDs of Bytecode  | ---> Kompilasi JVM Bytecode langsung di runtime
    | (Native Execution)|      (Menghapus interpretasi virtual function call)
    +-------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### Catalyst Optimizer: Empat Fase Inti

Catalyst mengonversi relasi deklaratif menggunakan pohon sintaks abstrak (*tree data structures*) dan mengeksekusi serangkaian aturan (*rules*) hingga mencapai titik *fixpoint* (kondisi di mana aturan tidak lagi mengubah bentuk pohon).

1. **Analysis**: Menerima *Unresolved Logical Plan*. Engine mencocokkan relasi against `SessionCatalog` untuk memverifikasi eksistensi database, tabel, view, dan atribut kolom. Mengonversi tipe data implisit jika diperlukan.
2. **Logical Optimization**: Menerapkan transformasi deterministik independen terhadap lingkungan komputasi:
   - *PushdownPredicates*: Memindahkan ekspresi pemfilteran mendekati sumber data (misal: membaca langsung dari Parquet row group metadata).
   - *ColumnPruning*: Menghilangkan kolom yang tidak dirujuk dari pemindaian fisik.
   - *ConstantFolding*: Menyederhanakan operasi konstan seperti `1 + 1` langsung menjadi literal `2` saat kompilasi.
3. **Physical Planning**: Mengubah model logika murni menjadi operasi eksekusi fisik. Fase ini memetakan operasi abstrak seperti `Join` menjadi algoritma konkret:
   - *Broadcast Hash Join (BHJ)*: Diterapkan jika salah satu tabel berukuran di bawah threshold (`spark.sql.autoBroadcastJoinThreshold`, default: 10MB). Menghindari proses *shuffle*.
   - *Sort Merge Join (SMJ)*: Digunakan saat dataset berukuran besar. Melibatkan *Shuffle Exchange* berbasis hashing kunci join, diikuti dengan *sorting* pada setiap partisi sebelum digabungkan.
   - *Shuffled Hash Join (SHJ)*: Membagi data ke partisi-partisi, membangun hash table di salah satu sisi, lalu memindai sisi lainnya tanpa melakukan sorting penuh.
4. **Code Generation (CodeGen)**: Menggunakan pustaka *Janino* untuk menghasilkan *Java bytecode* dinamis saat runtime, meratakan rantai operator fisik ke dalam satu loop datar (*single flat loop*) guna meminimalkan *instruction cache misses*.

### Tungsten Engine & Memory Management

Tungsten membagi alokasi memori Executor (diatur oleh `spark.executor.memory`) melalui formulasi matematika internal:

$$\text{Usable Memory} = (\text{spark.executor.memory} - 300\text{ MB})$$

Total memori kerja yang dapat dikelola dibagi menjadi:
- **Spark Memory Pool** (`Usable Memory` $\times$ `spark.memory.fraction`, default 0.60):
  - **Storage Memory**: Digunakan untuk menyimpan data `.persist()`, DataFrame yang di-*cache*, dan replikasi blok siaran (*broadcast blocks*).
  - **Execution Memory**: Digunakan untuk komputasi internal, buffer *shuffle*, agregasi berbasis *hash table*, serta *sorting*.
  - *Dynamic Borrowing*: Storage dan Execution meminjam memori satu sama lain secara dinamis. Namun, jika Execution membutuhkan memori dan Storage sedang meminjamnya, Storage akan dievakuasi paksa (*evicted*) ke disk. Sebaliknya, Storage **tidak dapat** mengevaluasi Execution memory yang sedang aktif digunakan.
- **User Memory Pool** (`Usable Memory` $\times$ $(1.0 - \text{spark.memory.fraction})$, default 0.40):
  - Dialokasikan untuk struktur data kustom pengguna, metadata Spark internal, serta pencegahan lonjakan beban array.

### DAG Decomposition: Stages, Tasks, and Boundaries

Spark membagi siklus hidup sebuah job menjadi unit-unit berikut:
- **Job**: Dipicu oleh pemanggilan fungsi *Action* (contoh: `.write()`, `.count()`).
- **Stage**: Dibatasi oleh operasi yang memerlukan pertukaran data lintas node (**Wide Transformation / Shuffle Boundary**). Contoh: `groupByKey`, `reduceByKey`, `join`, `distinct`. Operasi yang bersifat *Narrow Transformation* (contoh: `map`, `filter`) digabungkan (*pipelined*) ke dalam satu Stage tanpa menimbulkan *Shuffle*.
- **Task**: Unit komputasi terkecil yang dieksekusi secara paralel pada sebuah *thread* JVM di dalam executor. Satu Task mengeksekusi logika satu Stage pada **satu partisi data**.

---

## 6. Production-Ready Code Implementation

Berikut adalah modul utilitas operasional Spark tingkat enterprise. Modul ini menyediakan:
- Inisialisasi `SparkSession` berstandar produksi dengan konfigurasi memori defensif dan AQE aktif.
- Mesin inspeksi metrik rencana fisik (*Physical Plan Diagnostics*).
- Deteksi anomali join strategy (*Cartesian Product / Sort Merge Join Fallbacks*).

```python
"""
spark_plan_analyzer.py
Engine diagnosa rencana eksekusi Spark tingkat produksi.
"""

from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

# Konfigurasi Logging Terstruktur
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SparkOptimizerEngine")


@dataclass(frozen=True)
class SparkClusterConfig:
    app_name: str
    master: str = "local[*]"
    driver_memory: str = "4g"
    executor_memory: str = "4g"
    memory_fraction: str = "0.7"
    memory_overhead: str = "1024m"
    offheap_enabled: bool = True
    offheap_size: str = "2g"
    shuffle_partitions: int = 200


class ProductionSparkContextManager:
    """Mengelola inisialisasi SparkSession dengan baseline performa industri."""

    @staticmethod
    def get_optimized_session(config: SparkClusterConfig) -> SparkSession:
        builder = (
            SparkSession.builder.appName(config.app_name)
            .master(config.master)
            .config("spark.driver.memory", config.driver_memory)
            .config("spark.executor.memory", config.executor_memory)
            .config("spark.memory.fraction", config.memory_fraction)
            .config("spark.driver.memoryOverhead", config.memory_overhead)
            .config("spark.executor.memoryOverhead", config.memory_overhead)
            # Optimasi Off-Heap Tungsten
            .config("spark.memory.offHeap.enabled", str(config.offheap_enabled).lower())
            .config("spark.memory.offHeap.size", config.offheap_size)
            # Baseline Partisi dan AQE
            .config("spark.sql.shuffle.partitions", str(config.shuffle_partitions))
            .config("spark.sql.adaptive.enabled", "true")
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
            .config("spark.sql.adaptive.skewJoin.enabled", "true")
            .config("spark.sql.adaptive.localShuffleReader.enabled", "true")
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        )

        spark = builder.getOrCreate()
        # Nonaktifkan logging root JVM yang terlalu berisik
        spark.sparkContext.setLogLevel("WARN")
        logger.info("SparkSession berhasil diinisialisasi dengan konfigurasi teroptimasi.")
        return spark


class ExecutionPlanAuditor:
    """Audit statis dan inspeksi performa pada Spark Execution Plans."""

    def __init__(self, df: DataFrame):
        self.df = df
        self._parsed_plan: Optional[str] = None

    def capture_physical_plan(self) -> str:
        """Mengambil physical plan secara deterministik via Java underlying methods."""
        if not self._parsed_plan:
            # Menggunakan representasi internal Catalyst String
            self._parsed_plan = self.df._jdf.queryExecution().executedPlan().toString()
        return self._parsed_plan

    def audit_performance_risks(self) -> Dict[str, Any]:
        """
        Memeriksa tanda-tanda degradasi performa pada Execution Plan:
        - Deteksi Cartesian Product (Nested Loop Join).
        - Keberadaan Exchange SortMergeJoin pada tabel kecil.
        - Deteksi pembacaan tanpa proteksi Filter Pushdown.
        """
        plan = self.capture_physical_plan()

        audit_results: Dict[str, Any] = {
            "has_cartesian_product": False,
            "has_sort_merge_join": False,
            "has_broadcast_join": False,
            "has_whole_stage_codegen": False,
            "exchange_count": plan.count("Exchange"),
            "risk_severity": "LOW",
            "warnings": [],
        }

        # Analisis Pola Plan
        if "CartesianProduct" in plan or "BroadcastNestedLoopJoin" in plan:
            audit_results["has_cartesian_product"] = True
            audit_results["warnings"].append(
                "CRITICAL: Terdeteksi Cartesian Product / BNLJ. Operasi berpotensi OOM atau timeout!"
            )
            audit_results["risk_severity"] = "CRITICAL"

        if "SortMergeJoin" in plan:
            audit_results["has_sort_merge_join"] = True
            audit_results["warnings"].append(
                "INFO: Menggunakan SortMergeJoin. Pastikan key terdistribusi merata untuk menghindari skew."
            )

        if "BroadcastHashJoin" in plan:
            audit_results["has_broadcast_join"] = True

        if "WholeStageCodegen" in plan:
            audit_results["has_whole_stage_codegen"] = True
        else:
            audit_results["warnings"].append(
                "WARNING: Tungsten WholeStageCodegen dinonaktifkan atau fallback terjadi pada beberapa node."
            )

        return audit_results


# --- Pipeline Eksekusi Uji & Profiling ---
if __name__ == "__main__":
    cluster_cfg = SparkClusterConfig(app_name="SparkArchitectureDeepDive")
    spark = ProductionSparkContextManager.get_optimized_session(cluster_cfg)

    try:
        # 1. Bangun Skema dan Dataframe Sintetis (Mocking Customer Transactions)
        logger.info("Membangun dataset pengujian...")
        customers_df = (
            spark.range(1, 100000)
            .withColumnRenamed("id", "customer_id")
            .withColumn("segment", F.when(F.col("customer_id") % 2 == 0, "Enterprise").otherwise("Retail"))
        )

        transactions_df = (
            spark.range(1, 1000000)
            .withColumnRenamed("id", "txn_id")
            .withColumn("customer_id", (F.rand() * 100000).cast("long"))
            .withColumn("amount", F.round(F.rand() * 5000, 2))
        )

        # 2. Definisikan Operasi Relasional (Memaksa terjadinya Broadcast Join)
        joined_df = (
            transactions_df.join(customers_df, on="customer_id", how="inner")
            .filter(F.col("amount") > 1000.0)
            .groupBy("segment")
            .agg(F.sum("amount").alias("total_revenue"), F.count("txn_id").alias("transaction_count"))
        )

        # 3. Lakukan Audit Rencana Eksekusi Sebelum Aksi Write/Collect
        auditor = ExecutionPlanAuditor(joined_df)
        audit_report = auditor.audit_performance_risks()

        print("\n================ RENCANA FISIK (PHYSICAL PLAN) ================")
        print(auditor.capture_physical_plan()[:2000])  # Print potongan 2000 karakter
        print("=================================================================\n")

        print("=== LAPORAN AUDIT PERFORMA ===")
        for key, value in audit_report.items():
            print(f"{key}: {value}")
        print("===============================\n")

        # 4. Trigger Action Deterministik
        result = joined_df.collect()
        for row in result:
            logger.info("Hasil Agregasi: %s", row.asDict())

    finally:
        logger.info("Menghentikan SparkSession...")
        spark.stop()
```

---

## 7. Edge Cases & Failure Modes (Penyebab, Dampak, dan Mitigasi)

| Failure Mode | Mekanisme Penyebab | Indikasi Error Log / UI | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **Driver Out of Memory (OOM)** | Terjadi ketika driver JVM kehabisan heap karena pemanggilan `.collect()` pada dataset besar, atau ukuran tabel broadcast melebihi alokasi memori driver. | `java.lang.OutOfMemoryError: Java heap space` pada `SparkSubmit` process. | 1. Hindari pemanggilan `.collect()`, gunakan `.take(n)` atau simpan langsung ke *sink*.<br>2. Periksa `spark.driver.maxResultSize` (batasi misal `4g`).<br>3. Kurangi nilai `spark.sql.autoBroadcastJoinThreshold`. |
| **Executor Memory Overhead Breached** | Memory non-heap yang dialokasikan melampaui `spark.executor.memoryOverhead`. Kerap dipicu transformasi berat Python (PyArrow/Pandas UDF) atau struktur off-heap allocator native C. | Node manager / Kubernetes Pod melempar sinyal: `Container killed by YARN for exceeding memory limits. X GB of Y GB used.` | Naikkan batas memori overhead:<br>`spark.executor.memoryOverhead = max(384MB, executorMemory * 0.15)`. Untuk workload Python, naikkan overhead hingga 20-30%. |
| **Shuffle Fetch Failed Exception** | Executor target gagal mengambil blok data shuffle dari Executor asal karena target node crash, GC pause yang terlampau lama (>60 detik), atau network timeout. | `org.apache.spark.shuffle.FetchFailedException: Failed to connect to /...` | 1. Naikkan heartbeat timeout: `spark.network.timeout = 800s`.<br>2. Terapkan Push-Based Shuffle (jika menggunakan cluster modern).<br>3. Aktifkan External Shuffle Service (ESS). |
| **Data Skew / Straggler Stage** | Distribusi nilai join key/grouping key terpusat pada satu hash partition (misal: nilai `NULL` berlebih atau key default `"UNKNOWN"`). | Spark UI Task Duration Graph menunjukkan 1 Task berjalan ekstrem lama sementara 99% task lainnya selesai seketika. Metrik *Shuffle Read Size* tidak seimbang. | 1. Gunakan Adaptive Query Execution: `spark.sql.adaptive.skewJoin.enabled = true`.<br>2. Tambahkan *Salt Key* sintetis (misal: menggabungkan key dengan angka random `0-N`).<br>3. Pisahkan join untuk baris dengan `NULL` atau isolasi prosesnya. |
| **Shuffle Spill (Memory & Disk)** | Execution pool tidak mampu menampung buffer sort/hash dari satu partisi saat eksekusi stage. Data dipindahkan sementara ke disk lokal worker. | Spark UI menunjukkan metrik: `Spill (Memory)` dan `Spill (Disk)` bernilai > 0 Bytes pada tab Stage Details. | 1. Naikkan nilai `spark.sql.shuffle.partitions`.<br>2. Alokasikan lebih banyak memori untuk executor atau kurangi jumlah `spark.executor.cores` per executor agar memory-per-core meningkat. |

---

## 8. Trade-offs & Alternatif Solusi

### 1. Komparasi Karakteristik Join Strategy

| Strategi Join | Shuffle? | Sort? | Prasyarat Memori | Skenario Terbaik | Skenario Terburuk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Broadcast Hash Join (BHJ)** | **Tidak** | **Tidak** | Salah satu sisi relasi harus muat sepenuhnya di memori Driver & Executor. | Menggabungkan *Fact Table* masif dengan *Dimension Table* kecil (<10-100MB). | Mengakibatkan OOM Driver/Executor jika estimasi ukuran tabel dimensi meleset (*underestimated*). |
| **Sort Merge Join (SMJ)** | **Ya** (Keduanya) | **Ya** (Keduanya) | Skalabilitas tinggi. Hanya butuh memori untuk buffer stream per partisi. Algoritma paling stabil untuk Big Data. | Dua tabel sama-sama berukuran masif tanpa batasan kapasitas memori executor. | Menghasilkan overhead disk spill dan komputasi CPU intensif akibat sorting di seluruh node. |
| **Shuffled Hash Join (SHJ)** | **Ya** (Keduanya) | **Tidak** | Satu partisi dari salah satu tabel harus muat dalam *Execution Memory Pool*. | Dataset berukuran menengah-besar di mana biaya komputasi *sorting* lebih mahal daripada *hashing*. | Berisiko OOM jika salah satu partisi dataset hasil hash melebihi batas alokasi memori execution worker. |
| **Broadcast Nested Loop (BNLJ)** | **Tidak** (Driver broadcast) | **Tidak** | Memori driver besar. Eksekusi loop kuadratik $\mathcal{O}(M \times N)$. | Operasi non-ekuivalen (misal: `df1.join(df2, df1.val != df2.val)`). | Mengunci komputasi secara permanen (*CPU lock/straggler*) pada dataset riil berukuran >10k baris. |

### 2. High-Level DataFrame API vs Low-Level RDD

- **DataFrame / Dataset API**: Mengharuskan eksekusi melalui Catalyst Optimizer dan Tungsten Engine. Keuntungan berupa optimasi otomatis lintas bahasa pemrograman (Python, Scala, R mengeksekusi logical bytecode yang sama). Kerugiannya adalah terbatasnya fleksibilitas kontrol mutasi objek JVM langsung.
- **Resilient Distributed Dataset (RDD)**: Memberikan kontrol imperatif absolut terhadap alokasi objek JVM dan partisi kustom. Kerugiannya sangat tinggi: Spark engine menjadi "buta" terhadap logika relasional pengguna (tidak ada pushdown predicates, pruning kolom, atau pengompresian off-heap), serta memicu serialisasi mahal antar-layer Python dan JVM jika menggunakan PySpark.

---

## 9. Best Practices & Standard Industri

### Perhitungan Sizing Executor Standar Industri (The "Magic Five" Rule)

Jangan pernah mengalokasikan 1 Executor raksasa per Worker Node (*Fat Executor*), atau 1 Core per Executor (*Tiny Executor*). Gunakan formulasi berikut:

1. **Alokasi Core per Executor**:
   Tetapkan **5 vCPU Cores** per Executor. Pengujian benchmark industri menunjukkan bahwa lebih dari 5 core per executor memicu bottleneck performa I/O HDFS/Cloud Storage throughput dan memperpanjang jeda waktu *Garbage Collection (GC)*.
2. **Formula Alokasi Memori Node**:
   Jika satu server memiliki 16 vCPU dan 64 GB RAM:
   - Cadangkan 1 Core dan 2-4 GB RAM untuk daemon OS dan Cluster Manager (NodeManager/Kubelet).
   - Sisa Core: 15 Cores $\rightarrow$ Bagi rata: $15 / 5 = 3$ Executor per node.
   - Sisa Memori: $60 \text{ GB} / 3 \text{ Executor} = 20\text{ GB per Executor}$.
   - Pisahkan alokasi overhead (10%):
     $$\text{spark.executor.memoryOverhead} = 20\text{ GB} \times 0.10 = 2\text{ GB}$$
     $$\text{spark.executor.memory} = 20\text{ GB} - 2\text{ GB} = 18\text{ GB}$$

### Baseline Konfigurasi Adaptive Query Execution (AQE)

Aktifkan konfigurasi AQE berikut secara default di tingkat cluster produksi:

```properties
# Mengaktifkan engine adaptif
spark.sql.adaptive.enabled=true

# Penyesuaian otomatis jumlah partisi shuffle pasca-stage map
spark.sql.adaptive.coalescePartitions.enabled=true
spark.sql.adaptive.advisoryPartitionSizeInBytes=134217728  # Target ideal: 128 MB per partisi

# Konversi dinamis SortMergeJoin ke BroadcastHashJoin di runtime
spark.sql.adaptive.autoBroadcastJoinThreshold=20971520      # Dynamic threshold: 20 MB

# Penanganan otomatis task yang terdampak data skew
spark.sql.adaptive.skewJoin.enabled=true
spark.sql.adaptive.skewJoin.skewedPartitionFactor=5
spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=268435456 # 256 MB
```

---

## 10. Hands-on Lab Exercise: Mendiagnosis & Mengeliminasi Skew & Spill

### Skenario Lab
Anda adalah Lead Data Engineer yang mewarisi query pelaporan finansial harian. Query tersebut mengalami penurunan performa parah (memerlukan waktu eksekusi >15 menit untuk volume data yang relatif moderat). Anda ditugaskan untuk mengaudit execution plan, menemukan bottleneck fisik, merefaktor kode, dan membuktikan peningkatan efisiensi komputasi melalui Spark UI/Plan Inspection.

### Step 1: Membuat Baseline Script Bermasalah (Simulasi Data Skew & Disk Spill)

Simpan script berikut sebagai `lab_spark_skew_reproduce.py`. Script ini sengaja menginjeksikan bias partisi untuk menghasilkan efek skew task:

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# Bangun sesi terisolasi dengan memori terbatas untuk memicu disk spill terukur
spark = (
    SparkSession.builder.appName("Lab-ExecutionPlan-Diagnostics")
    .master("local[4]")
    .config("spark.executor.memory", "1g")
    .config("spark.sql.shuffle.partitions", "8")
    # Nonaktifkan AQE secara eksplisit untuk melihat masalah arsitektur murni
    .config("spark.sql.adaptive.enabled", "false")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

print("--- Menghasilkan Dataset Transaksi dengan Kunci Skewed ---")
# 90% data terkonsentrasi pada customer_id = 9999 (Data Skew)
skewed_records = spark.range(1, 1500000).withColumn("customer_id", F.lit(9999))
normal_records = spark.range(1, 500000).withColumn(
    "customer_id", (F.rand() * 500).cast("int")
)

transactions = skewed_records.union(normal_records).withColumn(
    "billing_amount", F.rand() * 1000
)

# Dataset referensi profil customer (Metadata kecil)
customers = (
    spark.range(1, 10000)
    .withColumnRenamed("id", "customer_id")
    .withColumn("tier", F.when(F.col("customer_id") == 9999, "VIP-SKEWED").otherwise("STANDARD"))
)

# QUERY LAMBAT (Memicu SortMergeJoin pada data skew tanpa filter efisien)
slow_query = transactions.join(customers, on="customer_id", how="inner").groupBy(
    "tier"
).agg(F.sum("billing_amount").alias("gross_revenue"))

print("\n--- CETAK PLAN AWAL (UNOPTIMIZED) ---")
slow_query.explain(True)

# Eksekusi Action dan catat durasi
import time

start_time = time.time()
slow_query.show()
print(f"Durasi Eksekusi Query Awal: {time.time() - start_time:.2f} detik")

spark.stop()
```

### Step 2: Analisis Rencana Eksekusi Awal
Jalankan script dan amati bagian `== Physical Plan ==`:
1. Temukan operator `Exchange hashpartitioning(customer_id#X, 8)`. Hal ini membuktikan seluruh dataset ditransformasi menggunakan metode *Wide Shuffle*.
2. Temukan operator `SortMergeJoin [customer_id#X], [customer_id#Y]`.
3. Buka Spark UI lokal Anda (`http://localhost:4040` saat script berjalan) pada tab **Stages**. Perhatikan bahwa 1 task memerlukan waktu jauh lebih lama dibandingkan task lainnya akibat memproses nilai agregasi dari kunci `9999`.

### Step 3: Rekayasa Ulang Menggunakan Broadcast Hint & Partisi Adaptif

Buat file perbaikan dengan nama `lab_spark_skew_resolved.py`. Terapkan optimasi:
- Paksa penggunaan **Broadcast Hash Join** untuk mematikan Shuffle Exchange sepenuhnya.
- Terapkan teknik **Salting** untuk mengatasi bottleneck partisi jika relasi tabel kedua terlalu besar untuk dibroadcast.
- Aktifkan **Adaptive Query Execution (AQE)**.

```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# Konfigurasi Ulang Sesi dengan Adaptive Engine Aktif
spark = (
    SparkSession.builder.appName("Lab-ExecutionPlan-Resolved")
    .master("local[4]")
    .config("spark.executor.memory", "1g")
    .config("spark.sql.shuffle.partitions", "8")
    # Aktifkan AQE Skew Join Handling
    .config("spark.sql.adaptive.enabled", "true")
    .config("spark.sql.adaptive.skewJoin.enabled", "true")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")

# Replikasi dataset
skewed_records = spark.range(1, 1500000).withColumn("customer_id", F.lit(9999))
normal_records = spark.range(1, 500000).withColumn(
    "customer_id", (F.rand() * 500).cast("int")
)
transactions = skewed_records.union(normal_records).withColumn(
    "billing_amount", F.rand() * 1000
)

customers = (
    spark.range(1, 10000)
    .withColumnRenamed("id", "customer_id")
    .withColumn("tier", F.when(F.col("customer_id") == 9999, "VIP-SKEWED").otherwise("STANDARD"))
)

# QUERY OPTIMAL: Gunakan broadcast hint eksplisit untuk mematikan Shuffle Sort
optimized_query = transactions.join(
    F.broadcast(customers), on="customer_id", how="inner"
).groupBy("tier").agg(F.sum("billing_amount").alias("gross_revenue"))

print("\n--- CETAK PLAN TEROPTIMASI (OPTIMIZED PLAN) ---")
optimized_query.explain(True)

import time

start_time = time.time()
optimized_query.show()
print(f"Durasi Eksekusi Query Teroptimasi: {time.time() - start_time:.2f} detik")

spark.stop()
```

### Step 4: Parameter Evaluasi & Hasil Validasi

Periksa perbedaan mendasar pada rencana fisik (*Physical Plan*) antara kedua pendekatan:

1. **Eliminasi Exchange**: Operator `Exchange hashpartitioning(...)` menghilang sepenuhnya dari rencana fisik pada implementasi kedua. Hal ini menunjukkan bahwa **Shuffle I/O berhasil direduksi hingga 0 bytes** antar-worker node.
2. **Transformasi Operator**: Node `SortMergeJoin` digantikan oleh `BroadcastHashJoin [customer_id#X], [customer_id#Y], BuildRight`.
3. **Peningkatan Durasi Eksekusi**: Terjadi akselerasi pemrosesan (biasanya 3x hingga 10x lebih cepat tergantung spesifikasi hardware lokal), serta zero-risk terhadap kejadian *shuffle fetch failed* di cluster produksi. Memori executor tetap stabil tanpa indikasi disk spill.