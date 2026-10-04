# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Spark Architecture & Execution Plan Deep Dive**  
**Jalur Pembelajaran: Data Engineer (Kategori: 08-AI-Data-and-Autonomous-Agents)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik pada tingkat Enterprise Data Engineer diharapkan mampu:
- Membedah dan menganalisis mekanisme internal **Catalyst Optimizer** (Analysis, Logical Optimization, Physical Planning, dan Cost-Based Optimization) serta membaca representasi AST (*Abstract Syntax Tree*).
- Menguasai arsitektur memori **Project Tungsten**, termasuk *UnsafeRow binary format*, manipulasi memori *Off-Heap*, dan *Whole-Stage Code Generation* berbasis Janino compiler.
- Menjelaskan siklus hidup partisi data dan mekanisme **Shuffle Service Internals** (SortShuffleManager, spill to disk, merge sort, buffer management, dan shuffle file consolidation).
- Mengonfigurasi dan mengoptimalkan **Adaptive Query Execution (AQE)** untuk menangani dynamic coalescing, skew join mitigation, dan dynamic partition pruning secara otomatis di lingkungan produksi.
- Mendiagnosis dan menyelesaikan kegagalan beban kerja skala enterprise (*Out-of-Memory / OOM*, *Driver/Executor memory exhaustion*, *GC pauses*, dan *Shuffle FetchFailedException*).

---

## 2. Prerequisite
Untuk memahami modul ini secara komprehensif, peserta wajib memiliki:
- Pemahaman mendalam tentang ekosistem Apache Spark dasar (Transformasi RDD, DataFrame API, Action, Lazy Evaluation).
- Kemahiran dalam bahasa pemrograman Python (PySpark) atau Scala pada level intermediate hingga advanced.
- Penguasaan konsep struktur data dan algoritma dasar: B-Trees, Hash Tables, Binary Encoding, External Merge Sort.
- Pengetahuan dasar tentang JVM (Java Virtual Machine) internals: Java Heap, Garbage Collection (G1GC/ParallelGC), JVM profiling, dan memory allocation.
- Pengalaman mengoperasikan kluster terdistribusi (YARN, Kubernetes, atau standalone Spark cluster) dan membaca metrik Spark UI.

---

## 3. Concept & Internal Architecture

Arsitektur eksekusi Apache Spark modern didorong oleh dua mesin utama: **Catalyst Optimizer** untuk optimasi rencana query deklaratif dan **Project Tungsten** untuk optimasi efisiensi komputasi bare-metal serta manajemen memori berbasis perangkat keras modern.

### 3.1 Pipeline Catalyst Optimizer

Proses transformasi dari query deklaratif (SQL/DataFrame API) menjadi bytecode JVM terkompilasi melewati empat fase utama:

```
[ Unresolved Logical Plan ]
            |
            v  <-- Catalog / Metastore (Analysis: Name Resolution, Type Checking)
[ Analyzed Logical Plan ]
            |
            v  <-- Rule-Based Optimizations (Predicate Pushdown, Constant Folding, Projection Pruning)
[ Optimized Logical Plan ]
            |
            v  <-- Cost-Based Optimizer (CBO via Table/Column Statistics)
[ Physical Plans (List) ]
            |
            v  <-- Cost Model Selection (Minimizing Network & IO Overhead)
[ Selected Physical Plan ]
            |
            v  <-- Whole-Stage Code Generation (Janino Compiler)
[ Java Bytecode Execution ]
```

1. **Analysis Stage**:
   Spark DataFrame engine membuat *Unresolved Logical Plan*. Pada fase ini, nama relasi tabel atau kolom belum divalidasi. Komponen **Analyzer** memanfaatkan metadata dari `Catalog` (Hive Metastore, In-Memory Catalog, atau Catalog Plugin seperti Apache Iceberg/Delta Lake) untuk me-resolve identitas kolom, tipe data, dan fungsi bawaan sehingga menghasilkan **Analyzed Logical Plan**.

2. **Logical Optimization Stage**:
   Kumpulan aturan berbasis ekspresi deterministik (*rule-based optimization*) dieksekusi secara iteratif melalui mekanisme `RuleExecutor` hingga mencapai titik *fixed point*. Aturan ini mencakup:
   - **Predicate Pushdown**: Memindahkan filter ke tingkat sedekat mungkin dengan sumber data (misal: storage parquet/orc).
   - **Projection Pruning**: Menghilangkan kolom yang tidak diperlukan dari pemindaian data.
   - **Constant Folding**: Mengevaluasi ekspresi konstanta pada waktu kompilasi (misal: `1 + 1` diubah langsung menjadi `2`).
   - **Boolean Simplification**: Mengoptimasi klausul boolean seperti `true AND x` menjadi `x`.

3. **Physical Planning Stage**:
   Dari *Optimized Logical Plan*, satu atau lebih rencana fisik dihasilkan. Logical operators dipetakan ke physical operators (misalnya, `Join` logis dapat dipetakan ke `BroadcastHashJoinExec`, `ShuffledHashJoinExec`, atau `SortMergeJoinExec`).
   - **Cost-Based Optimizer (CBO)**: Jika statistik tabel tersedia (`ANALYZE TABLE COMPUTE STATISTICS`), CBO menghitung biaya komputasi, ukuran data intermediate, dan memilih strategi join atau urutan multi-way join yang paling efisien.

4. **Code Generation (CodeGen) Stage**:
   Rencana fisik terpilih diubah menjadi kode sumber Java monolitik via runtime compiler **Janino**, meruntuhkan batasan *Volcano Iterator Model* klasik.

---

### 3.2 Project Tungsten: Hardware-Aware Computation

Tungsten mengatasi hambatan performa yang bergeser dari I/O jaringan/disk ke utilisasi CPU dan memori (CPU/Memory bound).

#### A. Memory Management: Off-Heap & UnsafeRow
Secara default, objek Java di-heap memiliki overhead memori signifikan:
- Header objek JVM membutuhkan 12–16 byte.
- `java.lang.String` membutuhkan referensi terpisah, array byte, dan metadata encoding.
- Masalah utama: Tekanan berat pada JVM Garbage Collector (GC) ketika menampung miliaran baris objek.

Tungsten mengimplementasikan **UnsafeRow**, yaitu format representasi data biner beralignment 8-byte (64-bit words) yang dapat disimpan di memori *On-Heap* (melalui `long[]`) maupun *Off-Heap* (melalui native `sun.misc.Unsafe` memory allocation).

Struktur *UnsafeRow*:
- **Null Bitmask**: Melacak kolom mana yang bernilai null (1 bit per field, dibulatkan ke kelipatan 8 byte).
- **Fixed-length Field Area**: Field bertipe primitif (int, long, double) atau pointer (offset dan ukuran) untuk tipe variabel.
- **Variable-length Field Area**: Menyimpan data berukuran dinamis seperti String, Binary, Array, Map, atau Struct.

```
+-------------------+---------------------------------------+-----------------------------+
| Null Bitmask      | Fixed-length Fields Area (8 bytes ea) | Variable-length Data Area   |
| (Ceil(N/64) words)| Field 0 (Long) | Field 1 (Offset+Len) | Field 1 Raw UTF-8 Bytes ... |
+-------------------+---------------------------------------+-----------------------------+
```

Data dibaca langsung dari pointer memori via operasi CPU tanpa perlu deserialisasi menjadi Java Object reguler, meminimalisir footprint memori dan mengeliminasi GC pause.

#### B. Unified Memory Manager
Semenjak Spark 1.6+, memori Executor diatur melalui `UnifiedMemoryManager` yang membagi alokasi heap menjadi dua domain fleksibel:

```
Total Executor JVM Memory
+-----------------------------------------------------------------------------------+
| Reserved Memory (300 MB fixed)                                                    |
+-----------------------------------------------------------------------------------+
| User Memory: (JVM - 300MB) * (1.0 - spark.memory.fraction)                        |
| - Custom data structures, Spark internal metadata, UDF variables                   |
+-----------------------------------------------------------------------------------+
| Spark Memory: (JVM - 300MB) * spark.memory.fraction (Default: 0.6)                |
| +---------------------------------------+---------------------------------------+ |
| | Storage Memory (Default: 50% pool)    | Execution Memory (Default: 50% pool)  | |
| | - Cached RDDs, DataFrames, Broadcast  | - Shuffles, Joins, Sorts, Aggregates  | |
| +---------------------------------------+---------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

- **Mekanisme Dynamic Borrowing**: 
  - Execution Memory dapat meminjam ruang Storage Memory jika kosong.
  - Storage Memory dapat meminjam ruang Execution Memory jika kosong.
  - Jika Execution membutuhkan memori yang sedang dipinjam oleh Storage, Storage akan diejeksi (*evicted*) ke disk. Sebaliknya, Storage **tidak dapat** mengejeksi Execution Memory yang sedang aktif digunakan karena kompleksitas penanganan state sort/aggregate terfragmentasi.

#### C. Whole-Stage Code Generation (WSCG)
Model iterasi tradisional (Volcano iterator model) memanggil metode virtual `.next()` untuk setiap baris data di setiap operator. Ini mengakibatkan:
1. Lonjakan pemanggilan instruksi CPU (*instruction cache miss*).
2. Kegagalan optimasi register compiler karena loop terputus di batasan antarmuka.

WSCG mengubah rantai operator fisik (misal: Scan -> Filter -> Project -> Aggregate) menjadi satu fungsi `while` loop tunggal dalam bahasa Java, menjaga data tetap berada di dalam register CPU L1/L2 cache sesering mungkin.

---

### 3.3 Shuffle Architecture Internals

Shuffle adalah proses redistribusi data antar partisi di seluruh cluster yang memicu I/O disk, serialisasi data, dan transmisi jaringan.

```
Executor A (Map Phase)                            Executor B (Reduce Phase)
+------------------------------------+            +-----------------------------------+
| Task 1 -> In-Memory Append Buffer  |            | Shuffle Fetch Request             |
|        -> Spill to Disk (.spill)   |            | -> Fetch Remote Blocks (Netty)    |
| Task 2 -> Partition-based Sort     |            | -> Decompress & Read into Memory  |
+------------------------------------+            +-----------------------------------+
                  |                                                 ^
                  v                                                 |
+------------------------------------+                              |
| Write Data File: data.shuffle      | -----------------------------+
| Write Index File: index.shuffle    |   (Reads byte offsets per partition)
+------------------------------------+
```

1. **Map Task Side**:
   - `SortShuffleWriter` menampung data ke dalam buffer in-memory (`PartitionedAppendOnlyMap` atau `PartitionedPairBuffer`).
   - Ketika ambang batas memori tercapai, data di-sort in-memory berdasarkan `(Partition ID, Key)` lalu di-*spill* ke disk dalam bentuk file temporary terenkripsi/terkompresi.
   - Pada akhir tugas map, semua spilled files digabungkan (*external merge sort*) menjadi satu file data shuffle biner tunggal: `shuffle_{shuffleId}_{mapId}_0.data`.
   - File index pendamping dibuat: `shuffle_{shuffleId}_{mapId}_0.index`, yang memetakan offset byte dan panjang segmen data untuk setiap target reducer partition ID.

2. **Reduce Task Side**:
   - Reducer membuka koneksi socket non-blocking IO (menggunakan framework Netty) ke `ExternalShuffleService` atau executor host pemilik data.
   - Reducer meminta byte range spesifik dari index shuffle.
   - Data dialirkan ke buffer reducer, didekompresi, dan digabungkan secara dinamis ke pipeline komputasi lokal.

---

## 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Permasalahan Nyata) | Apa Fungsinya (Mekanisme Teknis) |
|---|---|---|
| **Catalyst Optimizer** | Query deklaratif manual rawan suboptimal; pengembang tidak boleh dibebani optimasi hardware/relasional manual. | Menyusun rencana eksekusi matematis teroptimal via analisis AST, CBO, dan perataan predikat otomatis. |
| **Project Tungsten** | JVM Garbage Collection overhead, cache-locality buruk, dan biaya dereferensi pointer Java Object. | Menggunakan memori native off-heap / unsafe, binari serialisasi packed 8-byte, dan WSCG via Janino bytecode. |
| **Adaptive Query Execution (AQE)** | Ukuran dan distribusi data di runtime sering kali sangat berbeda drastis dari estimasi metadata katalog statis. | Mengubah rencana eksekusi fisik secara dinamis *di tengah query runtime* berdasarkan statistik intermediate shuffle stage. |
| **Dynamic Partition Pruning (DPP)** | Fact-dimension join memindai seluruh partisi tabel fakta besar meski dimensi terfilter ketat. | Menyuntikkan hasil filter dari tabel dimensi langsung ke pemindaian file partisi tabel fakta pada runtime fisik. |
| **External Shuffle Service** | Jika executor dinamis mati atau di-scale down, intermediate shuffle data miliknya hilang dan memicu re-compute. | Menyimpan dan melayani file shuffle di luar siklus hidup proses executor menggunakan daemon mandiri pada node worker. |

---

## 5. How (Workflow Detail)

Berikut alur kerja Adaptive Query Execution (AQE) dalam menangani variasi data di runtime:

```
[ Stage 1: Map Phase ] -> Menghasilkan data shuffle
           |
           v
[ Shuffle Exchange Materialization ]
           |
           +---> (Registrasi Statistik Runtime: Ukuran Partisi, Row Counts)
           |
           v
[ AQE Re-optimization Engine ]
     |-- 1. Coalesce Partitions: Menggabungkan partisi kecil (< spark.sql.adaptive.advisoryPartitionSizeInBytes)
     |-- 2. Sort-Merge to Broadcast Join: Konversi SMJ ke BHJ jika ukuran realita < broadcast threshold
     |-- 3. Skew Join Mitigation: Memecah partisi skew raksasa menjadi N sub-partisi
           |
           v
[ Modified Physical Stage 2 ] -> Eksekusi Reducer Stage dengan beban kerja yang terdistribusi merata
```

### Prosedur Implementasi Skew Join Handling:
1. **Identifikasi Skew**: Partisi dianggap mengalami skew jika:
   $$\text{Ukuran Partisi} > \text{Median Partisi} \times \text{skewedPartitionFactor}$$
   DAN
   $$\text{Ukuran Partisi} > \text{skewedPartitionThresholdInBytes}$$
2. **Pemecahan Partisi**: Partisi skew pada sisi kiri dipecah menjadi beberapa chunk.
3. **Replikasi Pasangan**: Partisi pasangan pada sisi kanan di-broadcast atau diduplikasi untuk membaca chunk yang sesuai, mengeliminasi executor bottleneck (straggler).

---

## 6. Analogy & Diagram ASCII

### Analogi Pabrik Mobil Terdistribusi
- **Logical Plan**: Cetak biru fungsional ("Buat mobil warna biru, 4 pintu, bertenaga turbo").
- **Optimized Logical Plan**: Efisiensi proses desain ("Cat pintu mobil sebelum dipasang ke rangka agar tidak perlu mengecat ulang interior").
- **Physical Plan**: Petunjuk manual mekanik ("Ambil rangka menggunakan forklift hidrolik, pasang mesin V6 dengan 4 baut baja").
- **Tungsten (Off-Heap / UnsafeRow)**: Alih-alih membongkar onderdil satu per satu dari kardus berlabel (Java Objects dengan heap overhead), onderdil ditata padat langsung dalam kontainer kargo bernomor register presisi tanpa pembungkus tambahan.
- **Whole-Stage Code Generation**: Alih-alih ban berjalan berhenti di setiap pos teknisi (Volcano model: `next() -> next()`), satu robot mekanik super merakit seluruh mesin dalam satu gerakan terpadu kontinu tanpa henti.

### Diagram Arsitektur Interaksi Catalyst, Tungsten, dan Shuffle

```
DataFrame API / Spark SQL
         |
         v
+-------------------------------------------------------------+
|                      CATALYST OPTIMIZER                     |
|  [Analysis] -> [Logical Opt] -> [Physical Plan Selection]   |
+-------------------------------------------------------------+
         |
         v
+-------------------------------------------------------------+
|                     PROJECT TUNGSTEN                        |
|  +--------------------+  +--------------------------------+ |
|  | UnsafeRow Encoders |  | Whole-Stage CodeGen (Janino)    | |
|  +--------------------+  +--------------------------------+ |
|  +--------------------------------------------------------+ |
|  | Unified Memory Manager (Off-Heap / Execution Memory)   | |
|  +--------------------------------------------------------+ |
+-------------------------------------------------------------+
         |
         v (Tasks executed on CPU cores)
+-------------------------------------------------------------+
|                      SHUFFLE PIPELINE                       |
| Map Tasks -> Sort & Spill -> Data/Index File consolidation  |
|                                       |                     |
| Reducer Tasks <- Netty Block Transfer |                     |
+-------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membedah `.explain(mode="extended")` di PySpark

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# Inisialisasi SparkSession
spark = SparkSession.builder \
    .appName("Catalyst-Plan-Inspection") \
    .master("local[2]") \
    .config("spark.sql.adaptive.enabled", "false") \
    .getOrCreate()

# Membuat dummy DataFrame
data_users = [(1, "Alice", 25), (2, "Bob", 30), (3, "Charlie", 35)]
columns_users = ["id", "name", "age"]
df_users = spark.createDataFrame(data_users, columns_users)

# Transformasi: Filter & Projection
df_transformed = df_users.filter(col("age") > 28).select("name")

# Menampilkan seluruh tahapan eksekusi Catalyst
df_transformed.explain(mode="extended")
```

**Output Penjelasan Rencana Eksekusi:**
```text
== Parsed Logical Plan ==
'Project ['name]
+- 'Filter ('age > 28)
   +- LogicalRDD [id#0L, name#1, age#2L], false

== Analyzed Logical Plan ==
name: string
Project [name#1]
+- Filter (age#2L > cast(28 as bigint))
   +- LogicalRDD [id#0L, name#1, age#2L], false

== Optimized Logical Plan ==
Project [name#1]
+- Filter (isnotnull(age#2L) AND (age#2L > 28))
   +- LogicalRDD [id#0L, name#1, age#2L], false

== Physical Plan ==
*(1) Project [name#1]
+- *(1) Filter (isnotnull(age#2L) AND (age#2L > 28))
   +- *(1) Scan ExistingRDD[id#0L, name#1, age#2L]
```
*Catatan*: Simbol `*(1)` mengindikasikan bahwa operator `Project`, `Filter`, dan `Scan` digabungkan ke dalam sub-rutin **Whole-Stage Code Generation ID #1**.

---

### 7.2 Practical Example: Enterprise Join Tuning, Skew Mitigation & Memory Inspection

Berikut adalah script production-ready yang mendemonstrasikan mitigasi data skew secara eksplisit, pemanfaatan hint, inspeksi format memori, dan penyetelan AQE.

```python
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, broadcast, rand, floor, when, concat, lit

def init_enterprise_spark_session() -> SparkSession:
    """Menginisialisasi SparkSession dengan konfigurasi memori Tungsten dan AQE tingkat produksi."""
    return SparkSession.builder \
        .appName("Enterprise-Execution-Optimization") \
        .master("local[*]") \
        .config("spark.memory.fraction", "0.7") \
        .config("spark.memory.storageFraction", "0.3") \
        .config("spark.memory.offHeap.enabled", "true") \
        .config("spark.memory.offHeap.size", "536870912") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.sql.adaptive.skewJoin.enabled", "true") \
        .config("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "3.0") \
        .config("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "67108864") \
        .config("spark.sql.shuffle.partitions", "200") \
        .getOrCreate()

def main():
    spark = init_enterprise_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("[*] Mengompilasi dan menggenerasi synthetic skewed dataset...")
    
    # 1. Dataset Transaksi Skewed: 80% transaksi mengarah pada merchant ID 999 (Skew Key)
    base_df = spark.range(0, 1000000)
    transactions = base_df.withColumn(
        "merchant_id",
        when(rand(seed=42) < 0.8, 999).otherwise(floor(rand(seed=42) * 100).cast("int"))
    ).withColumn("amount", rand() * 1000.0)

    # 2. Dataset Metadata Merchant (Dimensi Kecil)
    merchants = spark.range(0, 100).withColumnRenamed("id", "merchant_id") \
        .withColumn("merchant_name", concat(lit("Merchant_"), col("merchant_id")))

    # Skenario A: Broadcast Hash Join dipaksakan melalui hint pada tabel kecil
    print("[*] Eksekusi Skenario A: Broadcast Hash Join Teroptimasi")
    bhj_joined = transactions.join(
        broadcast(merchants),
        on="merchant_id",
        how="inner"
    )
    
    print("--- Execution Plan Skenario A (Broadcast) ---")
    bhj_joined.explain(mode="simple")
    bhj_joined.write.mode("overwrite").format("noop").save()

    # Skenario B: Sort Merge Join dengan Skew Key Mitigation via AQE
    print("\n[*] Eksekusi Skenario B: Sort-Merge Join Skew Mitigation via AQE")
    
    # Matikan auto-broadcast sementara untuk memicu alur SortMergeJoin
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    
    smj_joined = transactions.join(
        merchants,
        on="merchant_id",
        how="inner"
    )

    print("--- Execution Plan Skenario B (Sort Merge & AQE Adaptive Check) ---")
    smj_joined.explain(mode="cost")
    
    # Trigger action untuk mengamati efek AQE pada Spark UI / Metrik
    smj_joined.write.mode("overwrite").format("noop").save()

    print("[+] Eksekusi selesai. Evaluasi metrik shuffle & AQE di Spark UI (port 4040).")
    spark.stop()

if __name__ == "__main__":
    main()
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Masalah Produksi
Sebuah platform E-Commerce FinTech memproses pemindaian transaksi harian sebesar **50 TB/hari**. Pipeline agregasi bulanan mengalami kegagalan terus-menerus:
- **Gejala**: Pipeline tertahan pada Stage 14 (99% selesai, 199/200 task berhasil, 1 task tersisa berjalan selama 4 jam hingga akhirnya crash dengan pesan error `ExecutorLostFailure (exit code 137: Out of Memory Killer by OS)`).
- **Akar Masalah**: Terdapat anomali transaksi dari *flash sale bot* yang menghasilkan 450 juta transaksi dengan `user_id = 0` (Guest User). Ketika dilakukan join antara `transactions` dan tabel profil `users`, terjadi *extreme data skew* yang mendarat di satu reducer executor tunggal. Hal ini menyebabkan heap memory kehabisan ruang dan memicu disk spill sebesar 1.2 TB pada satu node.

### Solusi Rekayasa Berbasis Arsitektur Spark

```
                        [Input Transaksi Skewed]
                                   |
         +-------------------------+-------------------------+
         |                                                   |
 (Key != Skew Key)                                   (Key == Skew Key: ID 0)
         |                                                   |
   Normal Path                                        Salt Key Phase:
         |                                    Concat(Key, "_", Floor(Rand()*10))
         |                                                   |
         v                                                   v
[Normal Join Execution]                             [Salting Distributed Join]
         |                                                   |
         +-------------------------+-------------------------+
                                   |
                                   v
                          [Union All Aggregation]
```

1. **Aplikasi Teknik Key Salting**:
   Untuk data non-AQE atau kasus skew yang sangat ekstrem: Menambahkan nilai acak (*salt*) dari `0` hingga `N-1` pada skew key di tabel fakta, dan mereplikasi (*exploding*) baris kunci terkait pada tabel dimensi sebanyak `N` kali.

2. **Implementasi AQE Skew Join & Fine-Tuning Parameter Engine**:
   Mengaktifkan mitigasi dinamis runtime:
   ```properties
   spark.sql.adaptive.enabled=true
   spark.sql.adaptive.skewJoin.enabled=true
   spark.sql.adaptive.skewJoin.skewedPartitionFactor=2.0
   spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=134217728
   spark.sql.adaptive.advisoryPartitionSizeInBytes=134217728
   ```

3. **Optimasi Buffer & Shuffle IO**:
   ```properties
   spark.shuffle.file.buffer=1m
   spark.reducer.maxSizeInFlight=128m
   spark.memory.offHeap.enabled=true
   spark.memory.offHeap.size=8g
   ```

### Hasil Dampak Produksi:
- **Waktu Eksekusi**: Berkurang dari 4.5 jam (gagal OOM) menjadi **18 menit** (sukses).
- **Disk Spill**: Menurun drastis dari 1.2 TB ke **0 byte** karena partisi dipecah secara seragam dan ditangani sepenuhnya dalam alokasi Execution Memory.
- **Biaya Komputasi Cluster**: Menghemat alokasi compute time sebesar 65% pada armada EMR/Databricks.

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan (+)| Kerugian / Trade-off (-) |
|---|---|---|
| **Broadcast Hash Join (BHJ)** | Mengeliminasi biaya shuffle, disk I/O, dan network sync secara absolut. Performa eksekusi instan. | Rawan memicu **Driver OOM** jika tabel broadcast lebih besar dari estimasi atau melebihi alokasi memori driver. |
| **Sort-Merge Join (SMJ)** | Sangat stabil untuk volume data raksasa; mampu menangani ukuran tabel yang melampaui total memori fisik cluster melalui teknik spilling. | Memerlukan fase exchange network shuffle penuh dan partisi data terurut yang memicu penulisan file intermediate ke disk. |
| **Tungsten Off-Heap Memory** | Mengeliminasi GC pause time sepenuhnya; data layout sangat terkompresi dan cache-aligned. | Konfigurasi rumit; tidak dapat didiagnosis dengan tool heap dump Java standar (seperti jmap/VisualVM); risiko memory leak native jika Spark framework crash tak terkendali. |
| **Aggressive AQE Dynamic Coalescing** | Mengurangi beban driver metadata dan menghilangkan overhead ribuan task kecil (*small tasks overhead*). | Sedikit latensi tambahan pada fase koordinasi stage barrier saat Spark Driver mengumpulkan metrik runtime exchange. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Driver OOM: `java.lang.OutOfMemoryError: Java heap space` saat Broadcast
- **Penyebab**: Pengembang memanggil `broadcast(df)` pada DataFrame yang ukurannya melebihi batas konfigurasi driver atau melebihi alokasi `spark.driver.memory`. Ingat bahwa tabel yang di-broadcast akan di-koleksi terlebih dahulu ke Spark Driver sebelum disebar ke seluruh Executor.
- **Solusi**: Jangan pernah melakukan broadcast pada DataFrame yang ukuran fisiknya tidak dapat diprediksi secara absolut. Pantau `spark.sql.autoBroadcastJoinThreshold` (default 10 MB, tingkatkan maksimal ke 50–100 MB jika driver memadai).

### 10.2 Shuffle FetchFailedException
- **Penyebab**: Executor tujuan gagal mengambil blok shuffle dari node worker asal karena:
  1. GC pause pada host target terlalu lama sehingga terjadi timeout socket Netty.
  2. Node worker mengalami crash akibat OOM di level sistem operasi (*Linux OOM Killer kill process*).
- **Solusi**: 
  - Tingkatkan timeout jaringan: `spark.network.timeout = 800s`.
  - Tingkatkan jumlah percobaan: `spark.shuffle.io.maxRetries = 10` dan `spark.shuffle.io.retryWait = 30s`.
  - Pasang **External Shuffle Service** mandiri agar ketersediaan file shuffle independen dari siklus hidup JVM executor.

### 10.3 High Memory Spill (Spill Memory vs Spill Disk)
- **Deteksi Spark UI**: Metrik menampilkan angka signifikan pada kolom `Spill (Memory)` dan `Spill (Disk)`.
- **Interpretasi**: Ukuran data in-memory sebelum di-spill jauh lebih besar daripada saat di disk karena deserialisasi objek ke heap.
- **Solusi**: Tingkatkan rasio `spark.memory.fraction`, alokasikan off-heap memory, atau perbanyak jumlah partisi shuffle (`spark.sql.shuffle.partitions` atau turunkan `spark.sql.adaptive.advisoryPartitionSizeInBytes`).

---

## 11. Best Practices (Production Checklist)

- [ ] **G1GC Tuning**: Gunakan JVM Garbage Collector modern:  
  `-XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=35 -XX:G1ReservePercent=15`.
- [ ] **Off-Heap Allocation**: Pastikan alokasi off-heap diaktifkan (`spark.memory.offHeap.enabled = true`) untuk pipeline analitik dengan beban aggregasi tinggi.
- [ ] **Adaptive Query Execution**: AQE wajib diaktifkan (`spark.sql.adaptive.enabled = true`) pada Spark 3.x ke atas.
- [ ] **Column Pruning & Filter Pushdown**: Hindari `SELECT *`. Selalu filter data seawal mungkin sebelum melakukan operasi join atau windowing.
- [ ] **Hindari Objek UDF Python Reguler**: Jangan gunakan UDF Python standar (`@udf`). Gunakan **Pandas UDF (Vectorized UDFs via Apache Arrow)** atau ekspresi native SQL bawaan agar optimasi Whole-Stage CodeGen Catalyst tidak terputus.
- [ ] **Kapasitas Disk Shuffle**: Pastikan disk lokal worker (scratch directory `spark.local.dir`) menggunakan drive NVMe SSD berkapasitas minimal 3x dari estimasi volume data harian.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`

### File 1: `hands-on/m02/spark_plan_analyzer.py`
Skrip otomatis untuk menganalisis dan membandingkan dampak optimasi Catalyst terhadap rencana eksekusi.

```python
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr

def create_session() -> SparkSession:
    return SparkSession.builder \
        .appName("HandsOn-PlanAnalyzer") \
        .master("local[2]") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()

def run_experiment():
    spark = create_session()
    
    # 1. Generate Data Parquet Dummy
    base_path = "hands-on/m02/data"
    os.makedirs(base_path, exist_ok=True)
    
    print("[+] Membuat file sample data...")
    df_source = spark.range(1, 100000).withColumn("value", expr("id * 10"))
    df_source.write.mode("overwrite").parquet(f"{base_path}/source_data")

    # 2. Query Tanpa Optimasi Pruning vs Dengan Pruning
    df_read = spark.read.parquet(f"{base_path}/source_data")
    
    # Query kompleks: Terapkan filter yang dapat dipushdown dan kolom yang dipangkas
    df_optimized = df_read.filter(col("id") > 50000).select("value")

    print("\n[+] Menginspeksi Parsed, Analyzed, Optimized, dan Physical Plans:")
    df_optimized.explain(mode="formatted")

    # 3. Validasi Keberadaan Whole-Stage CodeGen
    physical_plan = df_optimized._jdf.queryExecution().executedPlan().toString()
    has_codegen = "WholeStageCodegen" in physical_plan
    print(f"\n[+] Apakah Whole-Stage Code Generation aktif? {has_codegen}")

    spark.stop()

if __name__ == "__main__":
    run_experiment()
```

### File 2: `hands-on/m02/run_analysis.sh`
Skrip bash untuk menjalankan pipeline analisis memori dan shuffle profile.

```bash
#!/usr/bin/env bash
set -e

echo "=== Menjalankan Spark Architecture Deep Dive Suite ==="
export SPARK_LOCAL_IP="127.0.0.1"

# Menjalankan Python Analyzer
python3 hands-on/m02/spark_plan_analyzer.py

echo "=== Selesai. Periksa log eksekusi di atas ==="
```

---

## 13. Exercise

### Level Easy
1. Dari output `.explain(mode="extended")`, jelaskan perbedaan peran spesifik antara `Analyzed Logical Plan` dan `Optimized Logical Plan`!
2. Jika sebuah query menghasilkan string plan `*(2) HashAggregate(...)`, apa arti angka `(2)` dan tanda asterisk `*` tersebut?

### Level Medium
1. Diberikan kasus join antara tabel log transaksi (10 GB) dan tabel master mata uang (500 KB). Mengapa Spark memilih `SortMergeJoin` alih-alih `BroadcastHashJoin` jika Anda mengeksekusi operasi tersebut menggunakan RDD API primitif versus DataFrame API?
2. Bagaimana cara membuktikan secara empiris melalui Spark UI bahwa sebuah stage mengalami data skew? Metrik apa saja yang menunjukkan anomali tersebut?

### Level Hard
1. Rancang algoritma salting kustom menggunakan PySpark untuk mengatasi data skew pada operasi multi-column join yang melibatkan dua skew key dominan, tanpa mengandalkan fitur otomatis AQE! Tuliskan representasi matematis kalkulasi salt factor-nya!

---

## 14. Challenge

**Studi Kasus Arsitektur Tanpa Solusi Instan:**

Anda menjabat sebagai Principal Data Platform Architect di sebuah bank multinasional. Sistem Core Banking Anda mengalirkan log transaksi mutasi rekening secara streaming mikro-batch ke Delta Lake/Iceberg dengan throughput puncak **300.000 transaksi/detik**.

**Karakteristik Masalah:**
- 70% dari seluruh volume transaksi terikat pada 3 rekening *virtual account payment gateway* raksasa (kondisi extreme skew).
- Pipeline agregasi 15-menitan yang menggabungkan stream ini dengan tabel ledger historis (berukuran 120 TB) selalu mengalami *Task Deserialization Pause* dan kegagalan bertingkat `FetchFailedException: Connection reset by peer` di cluster Kubernetes spot-instances.
- Tim infrastruktur membatasi ukuran memory pod executor maksimal **16 GB RAM** (tidak boleh ada node raksasa).

**Instruksi Tantangan:**
Rancang proposal desain arsitektur data engineering komprehensif yang mencakup:
1. Skema manajemen memori Spark (konfigurasi heap, off-heap, overhead, dan buffer tuning).
2. Strategi shuffle dan isolasi key skew sebelum stage aggregasi/join.
3. Desain mekanisme fallback resiliency saat Kubernetes mereklamasi spot node di tengah proses shuffle exchange.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Pertanyaan)
1. Komponen Spark manakah yang bertugas mengompilasi representasi physical plan menjadi Java bytecode saat runtime?
   - A. Analyzer
   - B. Janino Compiler
   - C. Netty Shuffle Client
   - D. YARN Resource Manager

2. Berapa ukuran alignment word memory yang digunakan oleh Project Tungsten dalam format biner `UnsafeRow`?
   - A. 4-byte (32-bit)
   - B. 8-byte (64-bit)
   - C. 16-byte (128-bit)
   - D. 32-byte (256-bit)

3. Apa fungsi dari file berakhiran `.index` yang dihasilkan pada tahap shuffle map phase?
   - A. Menyimpan primary key dari data yang di-shuffle
   - B. Menyimpan metadata schema DataFrame
   - C. Menyimpan offset byte dan panjang blok data untuk setiap target partisi reducer
   - D. Menyimpan riwayat GC pause dari worker node

4. Parameter manakah yang mengatur ambang batas ukuran tabel untuk dilakukan Broadcast Join secara otomatis?
   - A. `spark.sql.broadcastExchange.maxSize`
   - B. `spark.sql.autoBroadcastJoinThreshold`
   - C. `spark.memory.storageFraction`
   - D. `spark.sql.shuffle.partitions`

5. Di pool memori manakah data cached DataFrame disimpan dalam arsitektur Unified Memory Manager?
   - A. User Memory
   - B. Execution Memory
   - C. Storage Memory
   - D. Reserved Memory

### Bagian B: Intermediate (5 Pertanyaan)
6. Jika Execution Memory membutuhkan ruang tambahan sementara Storage Memory sedang menggunakan 80% dari pool total, apa yang terjadi?
   - A. Task Spark akan langsung crash dengan status `OutOfMemoryError`.
   - B. Execution Memory akan memaksa eviksi data pada Storage Memory ke disk secara preemptif.
   - C. Storage Memory menolak permintaan Execution Memory dan query ditahan (*blocked*).
   - D. Spark Driver akan mematikan executor tersebut dan meluncurkan executor baru.

7. Mengapa Whole-Stage Code Generation menghasilkan peningkatan performa drastis dibandingkan Volcano Iterator Model?
   - A. Menghilangkan instruksi CPU virtual function dispatch dan menjaga data tetap berada dalam CPU register/cache.
   - B. Mengompresi data menggunakan algoritma Snappy di dalam CPU register.
   - C. Mengubah proses eksekusi dari multi-threaded menjadi single-threaded synchronous.
   - D. Memindahkan eksekusi loop dari CPU ke GPU secara otomatis.

8. Manakah pernyataan yang BENAR mengenai Dynamic Partition Pruning (DPP)?
   - A. DPP hanya bekerja pada join berbasis Cartesian Cross Join.
   - B. DPP memindai tabel fakta terlebih dahulu sebelum membaca tabel dimensi.
   - C. DPP menyaring partisi yang tidak relevan pada tabel fakta menggunakan hasil filter dari tabel dimensi di fase runtime.
   - D. DPP membutuhkan indeks B-Tree fisik di atas storage Parquet.

9. Apa konsekuensi teknis jika parameter `spark.sql.shuffle.partitions` dibiarkan pada nilai default (200) saat memproses data berukuran 5 TB?
   - A. Terjadi pembuatan partisi shuffle berukuran sangat masif (~25 GB per partisi) yang memicu OOM dan extreme disk spill.
   - B. Driver Spark akan crash karena kehabisan memory socket descriptor.
   - C. Spark akan otomatis membaginya menjadi 2000 partisi tanpa mempedulikan konfigurasi.
   - D. Waktu eksekusi menjadi instan karena partisi sedikit mengurangi network overhead.

10. Apa keuntungan utama arsitektur External Shuffle Service pada lingkungan dengan Dynamic Allocation?
    - A. Mempercepat deserialisasi UnsafeRow menjadi Java Object.
    - B. Memungkinkan executor yang sedang idle di-decommission tanpa kehilangan file data shuffle intermediate yang telah ditulisnya.
    - C. Mengurangi penggunaan memori off-heap hingga 0%.
    - D. Mengubah SortMergeJoin menjadi Broadcast Hash Join pada runtime.

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan)

**Skenario 1:**
Sebuah query join antar dua tabel besar (fakta transaksi dan fakta log klik) berjalan sangat lambat. Di Spark UI terlihat bahwa 199 partisi selesai dalam waktu 5 detik per partisi, namun partisi nomor 72 berjalan selama 58 menit pada tahap `SortMergeJoinExec`.
- **Pertanyaan 11**: Analisislah apa anomali yang terjadi pada partisi 72, dan konfigurasi AQE spesifik apa yang harus diaktifkan untuk mengatasi masalah tersebut tanpa mengubah source code aplikasi?

**Skenario 2:**
Sebuah pipeline batch ETL malam hari gagal total dengan error log:
`org.apache.spark.shuffle.FetchFailedException: Failed to connect to worker-node-04/10.0.4.12:7337`
Ketika diperiksa, proses executor pada `worker-node-04` hilang tiba-tiba dari cluster manager tanpa melempar Java exception di log Spark Executor.
- **Pertanyaan 12**: Apa akar masalah yang paling mungkin terjadi pada level sistem operasi worker node tersebut, dan bagaimana langkah mitigasi arsitekturalnya?

**Skenario 3:**
Data Engineer mengimplementasikan custom Python UDF untuk mem-parsing payload JSON kompleks di dalam transformasi DataFrame dengan volume 500 juta baris:
```python
@udf(returnType=StringType())
def parse_payload(raw_json):
    # custom parsing logic
    return result
```
Pipeline tersebut mengalami penurunan performa sebesar 800% dibandingkan pipeline lama yang berbasis SQL expressions.
- **Pertanyaan 13**: Jelaskan mengapa custom Python UDF mematikan efisiensi Project Tungsten dan Catalyst Optimizer, serta berikan solusi arsitektur penggantinya!

---

### Kunci Jawaban Quiz

#### Bagian A & B
1. **B** (Janino Compiler mengompilasi Java AST code ke bytecode JVM saat runtime).
2. **B** (UnsafeRow menggunakan memory alignment berbasis 8-byte / 64-bit words).
3. **C** (File `.index` berisi penanda offset dan panjang segmen data byte untuk tiap reducer partisi).
4. **B** (`spark.sql.autoBroadcastJoinThreshold`).
5. **C** (Storage Memory dialokasikan untuk cache, persistensi DataFrame, dan broadcast block).
6. **B** (Execution Memory memiliki prioritas mutlak atas Storage Memory; data Storage akan di-evict ke disk jika Execution membutuhkan ruang).
7. **A** (WSCG meruntuhkan abstraksi iterator Volcano, mengeliminasi virtual dispatch, dan memaksimalkan CPU cache locality).
8. **C** (DPP mengevaluasi filter tabel dimensi dan menyuntikkannya langsung ke filter scan partisi tabel fakta pada runtime).
9. **A** (Ukuran tiap partisi akan membengkak drastis melebihi batas memori tugas, menyebabkan tumpahan data masif ke disk atau Executor OOM).
10. **B** (Data shuffle di-serve oleh service eksternal, sehingga node executor dapat di-scale down secara aman).

#### Bagian C (Analisis Kasus)
11. **Analisis**: Partisi 72 mengalami **Data Skew** ekstrem (akumulasi volume key identik dalam jumlah masif pada satu reducer partition).
    **Solusi Konfigurasi**: Aktifkan mitigasi skew AQE:
    `spark.sql.adaptive.enabled=true`,
    `spark.sql.adaptive.skewJoin.enabled=true`,
    `spark.sql.adaptive.skewJoin.skewedPartitionFactor=3.0`, dan
    `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes=67108864` (64MB).
12. **Analisis**: Executor dimatikan secara paksa oleh **Linux OS OOM Killer** (Out-of-Memory Killer, Exit Code 137). Penyebabnya adalah total pemakaian memori (JVM Heap + Off-Heap + Memory Overhead JVM runtime) melampaui batas resource memory cgroup/container yang dialokasikan YARN/Kubernetes.
    **Mitigasi**: Tingkatkan overhead container via `spark.executor.memoryOverhead` (minimal 15-20% dari total heap), alokasikan off-heap secara terukur (`spark.memory.offHeap.size`), atau kurangi konkurensi core per executor (`spark.executor.cores = 4` alih-alih 8 atau 16) untuk mengurangi perebutan alokasi memory buffer off-heap secara simultan.
13. **Analisis**: Python UDF konvensional memutus pipeline eksekusi Catalyst dan Tungsten:
    - Spark harus melakukan context switching dan serialisasi data bolak-balik via socket IPC dari JVM ke proses daemon Python (Py4J worker).
    - Data diubah dari format padat biner `UnsafeRow` menjadi representasi objek Python standar (boxing overhead).
    - Mematikan fitur Whole-Stage Code Generation karena Janino tidak dapat mengompilasi kode Python ke dalam satu fungsi Java loop tunggal.
    **Solusi Pengganti**: Gunakan fungsi parser built-in native Spark SQL (`from_json` dipadukan dengan struct schema) yang 100% berjalan native di Tungsten, atau gunakan **Vectorized Pandas UDF (`@pandas_udf`)** berbasis Apache Arrow jika manipulasi Python tingkat rendah mutlak diperlukan.

---

## 16. Summary

- **Catalyst Optimizer** bertindak sebagai perencana kecerdasan query Spark, mentranslasikan kode deklaratif pengguna menjadi rencana eksekusi fisik terpilih yang optimal melalui fase *Analysis*, *Logical Optimization*, *Physical Planning*, dan *Cost-Based Optimization*.
- **Project Tungsten** mendefinisikan ulang efisiensi komputasi modern dengan mengabaikan representasi Java Object standar demi format biner kompak berkecepatan tinggi (**UnsafeRow**), pemanfaatan alokasi native **Off-Heap Memory**, serta kompilasi runtime terpadu melalui **Whole-Stage Code Generation**.
- **Shuffle Pipeline** adalah tulang punggung skalabilitas terdistribusi sekaligus titik rawan latensi utama. Pemahaman mendalam mengenai file data/index shuffle, buffer memory spilling, dan peran external shuffle service sangat krusial dalam rekayasa data skala petabyte.
- **Adaptive Query Execution (AQE)** pada Spark 3.x mentransformasikan model komputasi statis menjadi dinamis. AQE mampu mengatasi data skew, mengonversi strategi join secara real-time, dan menggabungkan partisi kecil secara adaptif untuk stabilitas pipeline tingkat enterprise.