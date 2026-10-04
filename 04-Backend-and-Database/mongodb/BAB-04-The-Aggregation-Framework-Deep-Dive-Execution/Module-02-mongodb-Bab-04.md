# BAB 04: The Aggregation Framework Deep Dive & Execution
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonstruksi pipeline agregasi multi-tahap kompleks menggunakan operator tingkat lanjut (`$lookup` correlated subquery, `$facet`, `$graphLookup`, `$bucketAuto`, dan `$setWindowFields`).
- Menganalisis dan membedah internal query engine MongoDB (Slot-Based Execution Engine/SBE vs Classic Engine) dalam konteks optimasi tahapan agregasi (*pipeline optimization & stage coalescing*).
- Menavigasi batasan memori eksekusi (100MB RAM limit per stage), mengonfigurasi `allowDiskUse`, serta mengevaluasi dampaknya terhadap latency, I/O disk, dan CPU throttling.
- Mendesain arsitektur agregasi terdistribusi pada Sharded Cluster dengan memitigasi bottleneck fase *merge* pada `mongos` atau *primary shard*.
- Mengimplementasikan pola materialisasi data asinkronus skala enterprise menggunakan `$merge` dan `$out` dengan jaminan konsistensi data dan zero-downtime deployment.
- Mendiagnosis degradasi performa pipeline agregasi secara mendalam menggunakan output `explain("executionStats")`.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta diwajibkan telah menguasai:
- Konsep dasar Aggregation Framework: `$match`, `$project`, `$group`, `$sort`, `$unwind`, dan `$limit`.
- Desain skema dokumen MongoDB (1-to-N, N-to-N, Embedded Documents vs Normalized References).
- Mekanisme pengindeksan dasar: Compound Index, Multikey Index, Partial Index, dan Index Prefix matching rules.
- Pemahaman dasar arsitektur terdistribusi MongoDB: Konfigurasi Replica Set, Sharded Cluster (`mongos`, Config Servers, Shard Pods).
- Runtime Node.js/TypeScript dengan MongoDB Native Driver atau Mongoose ODM tingkat intermediate.

---

### 3. Concept & Internal Architecture

#### 3.1 Slot-Based Execution (SBE) Engine vs Classic Engine
Dimulai dari MongoDB 5.0 dan disempurnakan di versi 6.0+, MongoDB memperkenalkan Slot-Based Execution (SBE) engine untuk menggantikan Classic Execution Engine secara bertahap. 

```
+-----------------------------------------------------------------------+
|                       Aggregation Pipeline String                     |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                        Pipeline Optimizer                             |
|  - Stage Coalescing ($sort + $limit -> top-k sort)                   |
|  - Pushdown Predicates ($match early execution)                       |
|  - Projection Pruning (membuang field yang tidak dibutuhkan)         |
+-----------------------------------------------------------------------+
                                   |
                  +----------------+----------------+
                  | SBE Capable?                    |
                 YES                                NO
                  v                                 v
+------------------------------------+ +--------------------------------+
|       Slot-Based Engine (SBE)      | |     Classic Engine (Document)  |
| - Typed, vectorized-like slots     | | - BSON object allocations      |
| - JIT-like C++ compiled primitives | | - Iterator model (getMore())   |
| - Cache-locality optimized         | | - Overhead copy BSON tinggi    |
+------------------------------------+ +--------------------------------+
```

Pada Classic Engine, pemrosesan dokumen dilakukan melalui iterator model: dokumen diekstrak sebagai objek BSON penuh, lalu dilewatkan antar-tahap (stage) agregasi. Hal ini menyebabkan overhead alokasi memori heap, GC pressure (pada bahasa host), dan *cache misses* yang masif pada CPU L1/L2/L3.

SBE mengubah paradigma ini:
- **Slot Array**: Data direpresentasikan dalam slot memori skalar primitif berukuran tetap (fixed-size array of slots).
- Dokumen BSON diuraikan (*flattened*) ke dalam slot memori ini hanya untuk field yang dibutuhkan dalam kalkulasi.
- Eksekusi instruksi beroperasi pada representasi *native assembly/C++ fast paths*, meminimalkan dereferensi pointer dinamis dan meningkatkan performa hingga 2-4x lipat pada agregasi filtering, sorting, dan grouping numerik.

#### 3.2 Pipeline Optimizer Engine: Coalescing & Reordering
Sebelum eksekusi fisik dilakukan, query planner menjalankan serangkaian *rewriting rules*:

1. **Stage Coalescing**:
   - `$sort` diikuti oleh `$limit` dikonsolidasi menjadi satu algoritma *Top-K Sort*, mencegah pengurutan seluruh dataset di memori.
   - Berturut-turut `$match` digabungkan menjadi single `$match` dengan operator `$and`.
   - `$project` berturut-turut dilebur menjadi satu transformasi proyektif.
2. **Predicate Pushdown**:
   - Jika `$match` ditempatkan setelah operator yang tidak mengubah kardinalitas atau tipe field (misal `$sort`), query optimizer secara otomatis memajukan (push down) `$match` tersebut ke posisi paling awal untuk memanfaatkan indeks.
3. **Projection Pushdown**:
   - Optimizer menganalisis field apa saja yang benar-benar dibutuhkan oleh tahapan akhir (downstream stages). Field yang tidak terpakai akan dieliminasi sejak tahapan `$lookup` atau `$project` pertama untuk menghemat footprint RAM.

#### 3.3 Sharded Cluster Aggregation Mechanics
Pada lingkungan sharded, eksekusi agregasi dipecah menjadi dua fase utama:

```
[Client Application]
         |
         | (1) Run Aggregation Pipeline
         v
    [ mongos Router ]
      /            \
     / (2) Split    \ (2) Split
    v     Pipeline   v     Pipeline
+-------------+  +-------------+
| Shard A     |  | Shard B     |
| [Filter]    |  | [Filter]    |
| [Group-Part]|  | [Group-Part]|
+-------------+  +-------------+
     \              /
      \ (3) Stream / Results
       v          v
   +------------------+
   |  Merge Node      | (Bisa pada 'mongos' atau
   |  [Final Reduce]  |  salah satu Shard terpilih /
   |  [Sort Merging]  |  Primary Shard via $mergeCursors)
   +------------------+
            |
            v (4) Unified Result Cursor
    [Client Application]
```

- **Split Pipeline**: MongoDB membagi pipeline menjadi dua bagian: tahapan yang dapat dijalankan secara independen paralel pada masing-masing shard (*Shard Pipeline*), dan tahapan konsolidasi (*Merge Pipeline*).
- Jika tahapan pertama dimulai dengan `$match` pada Shard Key, query hanya dikirim ke shard target (*targeted routing*). Jika tidak, terjadi *scatter-gather* ke seluruh shard.
- **Merge Point**: Secara default, `mongos` bertindak sebagai titik penggabungan. Namun, jika pipeline memerlukan sorting berat atau terdapat tahapan `$group` yang membutuhkan komputasi memori besar, MongoDB otomatis mengalihkan tugas penggabungan ke salah satu data shard secara acak atau ke *Primary Shard* database tersebut guna mencegah `mongos` mengalami out-of-memory (OOM).

#### 3.4 Dynamic Memory Management & Disk Spillover
- **Limit Memori 100MB**: Setiap tahapan agregasi internal dibatasi menggunakan maksimal 100MB RAM (pada MongoDB < 6.0 mutlak memicu error; pada 6.0+ SBE dapat menggunakan alokasi dinamis tergantung konfigurasi `internalQueryMaxBlockingSortMemoryUsageBytes`, default 100MB).
- **`allowDiskUse: true`**: Menulis struktur data sementara (*temporary spilling files*) ke direktori `dbPath/_tmp` saat batas 100MB terlampaui. Operasi disk I/O ini bersifat sinkronus dan terenkripsi jika *encryption-at-rest* diaktifkan, memicu degradasi performa (*I/O wait spike*).
- **Stage yang Tidak Mendukung Disk Spilling Penuh**: Beberapa tahapan tertentu, seperti `$facet` (sebelum MongoDB 7.0), memiliki limitasi ketat dalam hal disk-spilling dan berisiko langsung melempar exception:
  `Command failed with error 40300 (Location40300): PlanExecutor error during aggregation :: caused by :: $facet stage has a memory limit of 100 megabytes`.

---

### 4. Why & What

| Pendekatan | Latency (P99) | Footprint Memori | Network Overhead | Skalabilitas Horizontal | Kompleksitas Kode |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Client-Side Transformation** | Tinggi (Detik/Menit) | Sangat Tinggi di App Server | Masif (Semua raw data ditransfer via TCP) | Buruk (App server jadi bottleneck) | Rendah (Imperatif JS/Python) |
| **MongoDB Aggregation (SBE)** | Sangat Rendah (Milidetik) | Terisolasi di Database Engine (Optimal via Indexes) | Sangat Rendah (Hanya aggregat data yang dikirim) | Sangat Tinggi (Paralelisasi Shard) | Menengah - Tinggi (Deklaratif Pipeline) |
| **Hadoop/Spark Batch Job** | Sangat Tinggi (Batch window menit-jam) | Terdistribusi di Cluster Terpisah | Masif (ETL pull over network) | Sangat Tinggi (Compute Engine terpisah) | Sangat Tinggi (Infrastruktur terpisah) |

#### Kapan Menggunakan Aggregation Framework Lanjutan?
- **Pola Analytics Real-Time**: Dashboard multidimensi yang membutuhkan komputasi analitik langsung terhadap *live operational data* tanpa latensi pipeline ETL.
- **Relational Joins Terfilter**: Menggabungkan data master dan transaksional menggunakan `$lookup` berkorelasi (correlated subqueries) tanpa memindahkan jutaan dokumen unindexed ke layer aplikasi.
- **Hierarchical/Graph Querying**: Menelusuri relasi berulang (*bill of materials*, *organizational structure*, *fraud detection paths*) via `$graphLookup`.

#### Kapan Menghindarinya?
- **Global Data Warehousing Kompleks**: Ketika melibatkan multi-terabyte analytical queries lintas puluhan domain bounded-context. Gunakan Data Lakehouse (Snowflake, ClickHouse, Databricks).
- **Tulis Agregat Frekuensi Ekstrem Tinggi**: Jika pipeline dijalankan setiap kali ada write tunggal di high-throughput OLTP (ribuan TPS). Dalam kasus ini, gunakan pola *Incremental Counter Embedded Pattern*.

---

### 5. How (Workflow Detail)

Alur eksekusi internal aggregation pipeline dari client hingga data layer:

```
[Client] ---> Driver bson compile ---> Wire Protocol (OP_MSG)
                                                |
                                                v
                                         [mongod Engine]
                                                |
                                     (Parse Query AST)
                                                |
                                                v
                                    [Pipeline Optimizer]
                                                |
                       +------------------------+------------------------+
                       |                                                 |
             [Rule-Based Optimizer]                            [Cost-Based Decisions]
             - Pushdown $match                                 - Choose optimal Index
             - Coalesce $sort + $limit                         - Determine SBE compatibility
             - Inline $project transformations                 - Memory buffer estimations
                       |                                                 |
                       +------------------------+------------------------+
                                                |
                                                v
                                    [Query Execution Plan]
                                                |
                                 +--------------+--------------+
                                 |                             |
                          (Memory <= 100MB)             (Memory > 100MB)
                                 |                             |
                                 v                             v
                        [Direct In-Memory]            [Check allowDiskUse]
                        [SBE Slot Execution]           |                 |
                                 |                    YES                NO
                                 |                     |                 |
                                 |                     v                 v
                                 |              [Spill to _tmp]    [Throw Error 40300]
                                 |                     |
                                 +--------------+------+
                                                |
                                                v
                                      [Streaming BSON Batch]
                                                |
                                                v
                                   [Wire Protocol Response]
```

1. **Compilation & Parsing**: MongoDB menerima dokumen pipeline BSON, membentuk Abstract Syntax Tree (AST), dan memvalidasi tipe schema argumen operator.
2. **Optimization Phase**: Evaluasi *rewriting rules*. Jika tahapan awal mendukung index (`$match` atau `$sort`), indeks akan di-lock pada stage pertama (Query Plan Cache dicek).
3. **Execution Execution Tree Generation**:
   - Jika mendukung SBE, dibangun bytecode representation untuk micro-execution.
   - Jika tidak, dibuat pipeline Classic Plan Stages (`DocumentSourceMatch`, `DocumentSourceLookup`, dll).
4. **Buffer Allocations & Disk Fallback**: Engine mengalokasikan slot array memori. Jika tahapan non-streaming (seperti `$sort` blocking tanpa indeks, atau `$group`) melampaui ambang batas 100MB dan flag `allowDiskUse: true` aktif, blok data diurutkan secara parsial, lalu di-*flush* ke file sementara terenkripsi di disk.
5. **Streaming Return Cursor**: Hasil dibungkus dalam representasi cursor batch (default batch size 101 dokumen awal atau 16MB limit wire protocol), dialirkan kembali ke client via iterator cursor stream.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Perakitan Otomotif Terdistribusi
Bayangkan sebuah perakitan mobil:
- **Classic Engine**: Pekerja mengangkat seluruh mobil utuh (rangka, ban, mesin, interior) dari meja ke meja, sekalipun pekerja tersebut hanya bertugas mengencangkan satu baut di spion.
- **Slot-Based Engine (SBE)**: Komponen dilepas dan diletakkan di nampan beralur cepat (*slots*). Hanya nampan berisi baut dan obeng yang bergerak cepat di rel berkecepatan tinggi menuju stasiun perakitan.
- **Stage Coalescing**: Alih-alih mobil dicat dasar di stasiun A lalu dibawa ke stasiun B untuk cat warna, stasiun A dan B digabung sehingga mobil langsung dicat dasar dan warna dalam satu siklus mesin.
- **Disk Spillover (`allowDiskUse`)**: Jika nampan komponen menumpuk melebihi kapasitas lantai kerja (100MB), pekerja terpaksa menyewa forklift untuk mengangkut kotak-kotak komponen keluar ke halaman parkir (*disk spill*), memperlambat laju kerja secara signifikan.

```
Classic Engine Pipeline (BSON Bloat)
[Doc: {_id, meta, audit, deep_data, val}] ---> [Transform] ---> [Doc: {_id, meta, audit, deep_data, val}]
          (Seluruh dokumen BSON disalin berulang kali antar-iterator)

SBE Execution Pipeline (Slot-Based Vectorized Processing)
[Doc] ---> Extract to Slots ---> Slot 0: val (Int32)
                                 Slot 1: id  (ObjectId)
                                    |
                            [SIMD / SBE Kernels] -> Operasi langsung pada registers / cache
                                    |
[Emisi Hasil] <---------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Correlated Subquery `$lookup`
Sering kali kita tidak hanya membutuhkan *simple left outer join*, tetapi *filtered join* di mana relasi anak harus difilter secara independen berdasarkan kondisi dinamis dari dokumen induk (correlated conditions) tanpa mencemari memori dengan seluruh array anak.

```javascript
// Mengambil data pelanggan dengan transaksi sukses dalam 30 hari terakhir dengan total > 500.000
db.customers.aggregate([
  {
    $match: { status: "ACTIVE" }
  },
  {
    $lookup: {
      from: "orders",
      let: { customerId: "$_id" }, // Mendefinisikan variabel dari dokumen customers
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$customer_id", "$$customerId"] }, // Correlated variable
                { $eq: ["$status", "COMPLETED"] },
                { $gte: ["$created_at", new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)] },
                { $gt: ["$total_amount", 500000] }
              ]
            }
          }
        },
        { $project: { _id: 1, total_amount: 1, created_at: 1 } }
      ],
      as: "qualifying_orders"
    }
  },
  {
    $match: {
      "qualifying_orders.0": { $exists: true } // Hanya kembalikan customer yang punya minimal 1 order valid
    }
  }
]);
```

#### 7.2 Practical Example: Multi-Faceted Analytics Dashboard (Production-Grade Node.js/TypeScript)
Berikut implementasi arsitektur modul analitik portofolio e-commerce menggunakan `$facet`, `$bucketAuto`, dan `$setWindowFields` dengan penanganan error produksi dan execution plan inspection.

```typescript
import { MongoClient, Db, Document } from 'mongodb';

export interface AnalyticsReport {
  priceDistribution: Document[];
  categoryPerformance: Document[];
  topRevenueContributors: Document[];
  executionTimeMs: number;
}

export class OrderAnalyticsRepository {
  constructor(private readonly db: Db) {}

  public async generateDashboardMetrics(tenantId: string): Promise<AnalyticsReport> {
    const startTime = performance.now();
    const collection = this.db.collection('orders');

    const pipeline: Document[] = [
      // Stage 1: Filter ketat di awal menggunakan indeks majemuk { tenant_id: 1, created_at: -1 }
      {
        $match: {
          tenant_id: tenantId,
          created_at: {
            $gte: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) // 90 hari terakhir
          },
          status: { $in: ['SETTLED', 'DELIVERED'] }
        }
      },
      // Stage 2: Hitung metrics running cumulative per sub-tenant menggunakan Window Functions
      {
        $setWindowFields: {
          partitionBy: "$category_id",
          sortBy: { created_at: 1 },
          output: {
            cumulativeCategoryRevenue: {
              $sum: "$total_amount",
              window: { documents: ["unbounded", "current"] }
            }
          }
        }
      },
      // Stage 3: Split pipeline menjadi multi-analisis paralel via $facet
      {
        $facet: {
          // Facet 1: Distribusi rentang harga secara otomatis (Histogram Dinamis)
          priceDistribution: [
            {
              $bucketAuto: {
                groupBy: "$total_amount",
                buckets: 5,
                output: {
                  count: { $sum: 1 },
                  averageRevenue: { $avg: "$total_amount" }
                }
              }
            }
          ],
          // Facet 2: Performa kategori produk
          categoryPerformance: [
            {
              $group: {
                _id: "$category_id",
                totalOrders: { $sum: 1 },
                grossMerchandiseValue: { $sum: "$total_amount" },
                avgOrderValue: { $avg: "$total_amount" }
              }
            },
            { $sort: { grossMerchandiseValue: -1 } },
            { $limit: 10 }
          ],
          // Facet 3: Kontributor pendapatan tertinggi
          topRevenueContributors: [
            {
              $group: {
                _id: "$customer_id",
                lifetimeSpend: { $sum: "$total_amount" }
              }
            },
            { $sort: { lifetimeSpend: -1 } },
            { $limit: 5 },
            {
              $lookup: {
                from: "customers",
                localField: "_id",
                foreignField: "_id",
                as: "profile"
              }
            },
            { $unwind: "$profile" },
            {
              $project: {
                customerId: "$_id",
                customerName: "$profile.name",
                customerEmail: "$profile.email",
                lifetimeSpend: 1,
                _id: 0
              }
            }
          ]
        }
      }
    ];

    try {
      const results = await collection
        .aggregate(pipeline, {
          allowDiskUse: true, // Wajib pada multi-facet analytics berskala besar
          maxTimeMS: 15000,    // Hard timeout circuit breaker
          readPreference: 'secondaryPreferred' // Mengurangi beban pada primary replika
        })
        .toArray();

      const duration = performance.now() - startTime;

      if (!results || results.length === 0) {
        throw new Error('Analytics aggregation returned empty result set.');
      }

      return {
        priceDistribution: results[0].priceDistribution,
        categoryPerformance: results[0].categoryPerformance,
        topRevenueContributors: results[0].topRevenueContributors,
        executionTimeMs: Math.round(duration)
      };
    } catch (error: any) {
      // Enterprise Error Logging Pattern
      console.error('FATAL: Aggregation Pipeline Failure', {
        error: error.message,
        errorCode: error.code,
        tenantId,
        stack: error.stack
      });
      throw error;
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Arsitektur FinTech Core Ledger: Sistem memproses rata-rata 120.000 transaksi/menit. Dibutuhkan sistem audit dan rekonsiliasi harian (*Daily End-of-Day Ledger Reconciliation*) yang mencocokkan saldo pembukuan (*double-entry balancing*) di seluruh akun perantara dan meng-update saldo agregat harian ke dalam koleksi `daily_account_snapshots` secara atomik tanpa menghentikan operasi OLTP transaksi.

#### Arsitektur Desain
- Dataset: Koleksi `journal_entries` berukuran ~800GB per bulan, di-shard berdasarkan `{ account_id: "hashed" }`.
- Target: Mengonsolidasikan jutaan baris entri mutasi (`DEBIT` & `CREDIT`) per akun, memastikan $\sum Debit - \sum Credit = 0$, dan menuliskan hasilnya ke koleksi analitik.

```
[journal_entries Sharded Cluster]
(Shard 1)          (Shard 2)          (Shard 3)
   |                  |                  |
   +--- $match (Rentang Waktu 24 Jam) ---+
   |                  |                  |
   +--- $group (Local Shard Aggregation) +
   |                  |                  |
   \                  |                  /
    \                 |                 /
     v                v                v
[Primary Shard (Merge Execution Engine)]
   - Final $group consolidations
   - Double-entry mathematical assertion ($cond)
   - Pipeline phase: $merge directly into 'daily_account_snapshots'
```

#### Pipeline Implementasi Produksi

```javascript
db.journal_entries.aggregate([
  // 1. Eksekusi filter berbasis range index waktu transaksi
  {
    $match: {
      posted_at: {
        $gte: ISODate("2023-10-01T00:00:00.000Z"),
        $lt: ISODate("2023-10-02T00:00:00.000Z")
      }
    }
  },
  // 2. Proyeksi selektif (SBE optimization: slotting numeric values)
  {
    $project: {
      account_id: 1,
      currency: 1,
      entry_type: 1, // 'DEBIT' atau 'CREDIT'
      amount: 1
    }
  },
  // 3. Agregasi bertingkat per Akun dan Mata Uang
  {
    $group: {
      _id: {
        account_id: "$account_id",
        currency: "$currency"
      },
      totalDebit: {
        $sum: {
          $cond: [{ $eq: ["$entry_type", "DEBIT"] }, "$amount", NumberDecimal("0.00")]
        }
      },
      totalCredit: {
        $sum: {
          $cond: [{ $eq: ["$entry_type", "CREDIT"] }, "$amount", NumberDecimal("0.00")]
        }
      },
      transactionCount: { $sum: 1 }
    }
  },
  // 4. Kalkulasi Delta Bersih
  {
    $project: {
      _id: 0,
      accountId: "$_id.account_id",
      currency: "$_id.currency",
      date: ISODate("2023-10-01T00:00:00.000Z"),
      totalDebit: 1,
      totalCredit: 1,
      netChange: { $subtract: ["$totalDebit", "$totalCredit"] },
      transactionCount: 1,
      reconciledAt: "$$NOW"
    }
  },
  // 5. Zero-downtime Continuous Materialization via $merge
  {
    $merge: {
      into: "daily_account_snapshots",
      on: ["accountId", "currency", "date"], // Unique Compound Index di koleksi target
      whenMatched: [
        {
          $set: {
            totalDebit: "$$new.totalDebit",
            totalCredit: "$$new.totalCredit",
            netChange: "$$new.netChange",
            transactionCount: "$$new.transactionCount",
            reconciledAt: "$$new.reconciledAt",
            version: { $add: [{ $ifNull: ["$version", 0] }, 1] }
          }
        }
      ],
      whenNotMatched: "insert"
    }
  }
], {
  allowDiskUse: true,
  readConcern: { level: "majority" },
  writeConcern: { w: "majority", j: true }
});
```

---

### 9. Trade-offs

```
                       LATENCY CRITICAL
                             ^
                             |       * Point Lookups / Client Transformations
                             |         (Low throughput scalability)
                             |
                             |       * In-Memory Aggregations (Indexed, SBE)
                             |         (Fast, but strict 100MB RAM cap)
                             |
                             +----------------------------------------> DATA VOLUME
                             |
                             |       * Spill to Disk (allowDiskUse: true)
                             |         (Heavy I/O, resilient to OOM)
                             |
                             |       * Materialized Views ($merge / ETL)
                             |         (Async latency, zero-read overhead)
                             v
                       RESOURCE INTENSIVE
```

#### 1. In-Memory Processing vs. `allowDiskUse` (Disk Spilling)
- **Trade-off**: Kecepatan throughput vs Kehandalan eksekusi.
- **Konsekuensi**: Mengandalkan disk spillover menurunkan kecepatan agregasi hingga 10-100x lipat karena latensi I/O disk NVMe/SSD dan lock context-switching pada level OS. Namun, menghindari error crash fatal `ExceededMemoryLimit`.

#### 2. Pipeline `$facet` vs Multi-Query Paralel Client
- **Trade-off**: Single round-trip network vs Footprint memori isolasi stage.
- **Konsekuensi**: Operator `$facet` menjalankan sub-pipeline di dalam satu thread pool yang sama secara berurutan atau terbatas. Seluruh data sub-tree facet harus ditampung di memori sebelum serialisasi akhir. Mengirim 3 query agregasi independen paralel secara terpisah dari client sering kali memberikan throughput lebih tinggi karena memanfaatkan multi-core thread pool database secara optimal.

#### 3. Materialized Pipeline (`$merge`) vs Real-time On-demand Aggregation
- **Trade-off**: Storage cost & data freshness vs Read Latency.
- **Konsekuensi**: `$merge` menciptakan duplikasi data teragregasi yang butuh strategi sinkronisasi (event-driven atau polling cron). Namun, ia mengubah query kompleks P99 8.000ms menjadi single-indexed read P99 2ms bagi end user.

---

### 10. Common Mistakes & Troubleshooting

#### Kasus Kesalahan 1: Cartographic Explosion akibat `$lookup` tanpa Unwind/Filter
- **Gejala**: Database Node tiba-tiba mengalami crash OOM, CPU memuncak 100%, log menampilkan error alokasi memory heap.
- **Root Cause**: Melakukan `$lookup` relasi 1-to-N di mana foreign collection berisi puluhan ribu dokumen per id, menghasilkan array raksasa yang melanggar batas 16MB document size limit atau menghabiskan 100MB aggregation limit.
- **Deteksi**: Periksa execution plan:
  ```javascript
  db.orders.explain("executionStats").aggregate([...]);
  ```
  Perhatikan metrik `totalDocsExamined` vs `nReturned`.
- **Solusi**: Terapkan correlated pipeline `$lookup` dengan limitasi eksplisit `$limit`, atau gunakan pagination pattern di dalam pipeline join.

#### Kasus Kesalahan 2: "Unindexed `$sort`" di Tengah Pipeline
- **Gejala**: Pipeline berjalan cepat pada 10.000 data pertama, namun melambat secara eksponensial seiring bertambahnya data operasional.
- **Root Cause**: Menempatkan `$sort` setelah tahapan yang merusak indeks referensial (misalnya setelah `$project` baru yang me-rename field, atau setelah `$group`). Sorting menjadi **blocking memory sort**.
- **Solusi**: Susun urutan pipeline agar sorting bertumpu pada index coverage awal. Jika komputasi sorting harus dilakukan post-aggregation, manfaatkan `$setWindowFields` atau batasi jumlah record dengan `$limit` seketat mungkin sebelum `$sort`.

#### Panduan Troubleshooting Diagnostik
Jika pipeline agregasi lambat di lingkungan produksi:
1. Ambil query profiling via Database Profiler:
   ```javascript
   db.system.profile.find({ millis: { $gt: 500 } }).sort({ ts: -1 }).pretty();
   ```
2. Analisis tahapan eksekusi:
   Cari keberadaan node plan `SORT` tanpa memanfaatkan index scans (`IXSCAN`). Pastikan tahapan awal menunjukkan `stage: "IXSCAN"` dan bukan `stage: "COLLSCAN"`.
3. Verifikasi apakah engine beralih ke SBE atau Classic:
   Cari field `slots` pada dokumen explain plan. Keberadaan atribut `slots` menandakan pipeline berjalan di Slot-Based Execution Engine baru yang optimal.

---

### 11. Best Practices (Production Checklist)

#### Pre-Deployment Aggregation Rules:
- [ ] **Push $match to the Root**: Pastikan tahap pertama pipeline adalah `$match` yang secara penuh menggunakan indeks majemuk terdaftar (*Indexed Predicate*).
- [ ] **Field Projection Stripping**: Jangan pernah melewatkan field BSON berukuran masif (seperti unstructured metadata/logs) melewati pipeline jika hanya 2 kolom numerik yang dianalisis. Potong di awal via `$project`.
- [ ] **Avoid `$unwind` on Massive Arrays**: Jika hanya ingin menghitung ukuran array atau mengekstrak elemen pertama, gunakan operator ekspresi `$size`, `$filter`, atau `$arrayElemAt` daripada mendekomposisi dokumen via `$unwind`.
- [ ] **Index All Foreign Keys in `$lookup`**: Pastikan atribut target pada `foreignField` memiliki indeks B-Tree yang identik tipe datanya (Strict Type Match: hindari perbandingan string vs ObjectId).
- [ ] **Explicit Timeout Setting**: Selalu passing `maxTimeMS` di level options cursor driver untuk mencegah unindexed long-running aggregation menggantung koneksi thread pool database.
- [ ] **Monitor Primary Shard Merging Pressure**: Pada Sharded Cluster, pastikan merge stage tidak terkonsentrasi pada Primary Shard jika dokumen yang ditransfer melewati batasan network router.

---

### 12. Hands-on Practice

Terapkan skenario berikut pada workspace hands-on lokal Anda. Simpan seluruh artefak ke direktori `hands-on/m02/`.

#### Langkah 1: Siapkan Environment (Docker Compose)
Simpan file konfigurasi pada `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'
services:
  mongodb:
    image: mongo:7.0
    container_name: mongo_adv_agg
    restart: always
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_DATABASE: enterprise_db
    command: ["--wiredTigerCacheSizeGB", "1"]
```

Jalankan container:
```bash
docker compose -f hands-on/m02/docker-compose.yml up -d
```

#### Langkah 2: Setup Schema & Seeding Dataset Besar
Jalankan file Node.js seeder `hands-on/m02/seed.js` untuk menginjeksikan 50.000 dokumen transaksi dan 5.000 user:

```javascript
// hands-on/m02/seed.js
const { MongoClient, ObjectId } = require('mongodb');

async function seed() {
  const client = new MongoClient('mongodb://localhost:27017');
  await client.connect();
  const db = client.db('enterprise_db');

  console.log('Clearing existing collections...');
  await db.collection('users').drop().catch(() => {});
  await db.collection('transactions').drop().catch(() => {});

  console.log('Seeding Users...');
  const users = [];
  for (let i = 0; i < 5000; i++) {
    users.push({
      _id: new ObjectId(),
      username: `user_${i}`,
      tier: i % 3 === 0 ? 'PLATINUM' : i % 2 === 0 ? 'GOLD' : 'SILVER',
      region: ['APAC', 'EMEA', 'AMER'][i % 3],
      createdAt: new Date(Date.now() - Math.floor(Math.random() * 10000000000))
    });
  }
  const insertedUsers = await db.collection('users').insertMany(users);
  const userIds = Object.values(insertedUsers.insertedIds);

  console.log('Seeding Transactions...');
  const transactions = [];
  for (let i = 0; i < 50000; i++) {
    const randomUserId = userIds[Math.floor(Math.random() * userIds.length)];
    transactions.push({
      userId: randomUserId,
      amount: parseFloat((Math.random() * 1000 + 10).toFixed(2)),
      status: ['SUCCESS', 'PENDING', 'FAILED'][i % 10 === 0 ? 2 : 0], // 90% success/pending
      category: ['ELECTRONICS', 'GROCERIES', 'TRAVEL', 'UTILITIES'][i % 4],
      timestamp: new Date(Date.now() - Math.floor(Math.random() * 5000000000))
    });
  }
  await db.collection('transactions').insertMany(transactions);

  // Buat indeks penting
  await db.collection('transactions').createIndex({ status: 1, timestamp: -1 });
  await db.collection('transactions').createIndex({ userId: 1 });

  console.log('Database successfully seeded.');
  await client.close();
}

seed().catch(console.error);
```

Eksekusi:
```bash
node hands-on/m02/seed.js
```

#### Langkah 3: Eksekusi Pipeline Kompleks dengan Profiling Explain Plan
Simpan skrip verifikasi `hands-on/m02/run_pipeline.js`:

```javascript
// hands-on/m02/run_pipeline.js
const { MongoClient } = require('mongodb');

async function execute() {
  const client = new MongoClient('mongodb://localhost:27017');
  await client.connect();
  const db = client.db('enterprise_db');

  const pipeline = [
    {
      $match: {
        status: 'SUCCESS'
      }
    },
    {
      $lookup: {
        from: 'users',
        localField: 'userId',
        foreignField: '_id',
        as: 'user'
      }
    },
    { $unwind: '$user' },
    {
      $group: {
        _id: { region: '$user.region', tier: '$user.tier' },
        grossVolume: { $sum: '$amount' },
        avgTransaction: { $avg: '$amount' },
        count: { $sum: 1 }
      }
    },
    {
      $sort: { grossVolume: -1 }
    }
  ];

  console.log('Fetching Explain Execution Stats Plan...');
  const explain = await db.collection('transactions').explain('executionStats').aggregate(pipeline);
  
  console.log('=== EXECUTION METRICS ===');
  console.log('Stages Summary:', JSON.stringify(explain.stages ? explain.stages : explain.executionStats, null, 2));

  await client.close();
}

execute().catch(console.error);
```

Jalankan dan amati arsitektur plan yang dieksekusi:
```bash
node hands-on/m02/run_pipeline.js
```

---

### 13. Exercises

#### Level Easy
Tuliskan aggregation stage tunggal untuk mengelompokkan koleksi transaksi berdasarkan `category` dan menghitung:
1. Total amount per category.
2. Jumlah transaksi per category.
Urutkan hasilnya dari nilai total amount terbesar.

*Petunjuk Solusi*: Gunakan operator `$group` standar dengan akumulator `$sum`, dilanjutkan oleh operator `$sort: { totalAmount: -1 }`.

#### Level Medium
Buat aggregation pipeline yang menghitung "Average Transaction Value" per pengguna, namun hanya sertakan pengguna yang memiliki total transaksi sukses lebih dari 5 kali. Optimalkan urutan eksekusi agar tidak melakukan komputasi rata-rata pada pengguna yang tidak memenuhi syarat filter.

*Petunjuk Solusi*: 
1. `$match` status success.
2. `$group` by `userId`, gunakan akumulator `$sum: 1` untuk total hitungan dan `$avg: "$amount"`.
3. Pasang `$match` kedua segera setelah `$group` untuk menyaring dokumen di mana `count > 5`.

#### Level Hard
Buat recursive query menggunakan operator `$graphLookup` pada koleksi hierarki karyawan (`employees`) untuk menemukan seluruh jalur struktur manajemen bawahan langsung dan tidak langsung (reporting chain) dari seorang Chief Executive Officer (CEO), batasi kedalaman penelusuran hierarki maksimal 3 level (`maxDepth: 2`), dan tambahkan kedalaman kedudukan hierarki tersebut pada output dokumen.

*Petunjuk Solusi*:
Gunakan `startWith: "$_id"`, `connectFromField: "_id"`, `connectToField: "reportsTo"`, `as: "subordinateChain"`, dan `depthField: "hierarchyLevel"`.

---

### 14. Challenges

#### Skenario Kasus Kompleks: Real-time Multi-Currency AML (Anti-Money Laundering) Pattern Detector
Sebuah Bank Internasional membutuhkan sistem deteksi anomali transfer dana instan.
Diberikan koleksi `money_transfers`:
```typescript
interface MoneyTransfer {
  _id: ObjectId;
  sourceAccount: string;
  destinationAccount: string;
  amount: number;
  currency: 'USD' | 'EUR' | 'IDR' | 'SGD';
  timestamp: Date;
}
```

Diberikan koleksi nilai tukar mata uang terbaru `fx_rates`:
```typescript
interface FxRate {
  baseCurrency: string; // e.g., 'EUR', 'IDR', 'SGD'
  targetCurrency: 'USD';
  exchangeRate: number; // Pengali untuk mengubah baseCurrency ke USD
}
```

**Spesifikasi Tantangan**:
1. Buat pipeline agregasi yang menormalisasi seluruh nilai transfer ke mata uang seragam (`USD`) secara dinamis dengan melakukan correlated `$lookup` ke tabel `fx_rates`.
2. Gunakan `$setWindowFields` untuk mendeteksi anomali transfer cepat berulang: Temukan setiap akun pengirim (`sourceAccount`) yang mentransfer dana kumulatif melebihi ambang batas equivalent `$10,000 USD` dalam jendela geser waktu (*rolling window duration*) 10 menit.
3. Arsitektur pipeline harus sepenuhnya *leak-proof* terhadap memori: Wajib berjalan tanpa memicu fatal disk spill pada volume transaksi 2 juta record per jam.
4. Output akhir harus langsung dituliskan ke dalam koleksi pengawasan `aml_flagged_accounts` dengan menyertakan array seluruh `_id` transfer yang menjadi pemicu pelanggaran tersebut menggunakan pola `$merge`.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa batasan default alokasi RAM per tahapan (*stage*) agregasi di MongoDB sebelum melempar error out-of-memory jika disk spill dinonaktifkan?
2. Apakah peletakan `$match` di tengah atau akhir pipeline agregasi akan selalu menghasilkan *full collection scan*? Jelaskan mekanisme internalnya!
3. Apa perbedaan mendasar antara operator agregasi `$out` dan `$merge` terkait retensi koleksi target yang sudah ada?
4. Mengapa penggunaan `$lookup` dengan kondisi operator `$expr` dan sub-pipeline (correlated lookup) lebih unggul daripada sekadar menggunakan parameter `localField` dan `foreignField` standar?
5. Operator windowing apa yang diperkenalkan pada MongoDB 5.0+ untuk menghitung running totals tanpa perlu melakukan `$unwind` atau `$group` ulang?

#### Pertanyaan Intermediate
6. Jelaskan bagaimana Slot-Based Execution (SBE) engine mengoptimasi konsumsi CPU dan cache L1/L2 memory dibandingkan dengan Classic Engine pada tahapan agregasi numerik!
7. Pada Sharded Cluster, kapan pipeline agregasi akan dieksekusi secara *Targeted Routing* dibandingkan secara *Scatter-Gather*?
8. Mengapa operator `$facet` sering kali menjadi titik kegagalan performa (*bottleneck*) dalam pipeline yang mengolah jutaan baris dokumen, dan bagaimana solusinya?
9. Apa perbedaan teknis antara stage optimasi *Top-K Sort* dengan standar sorting eksternal menggunakan temporary files di disk?
10. Sebutkan kondisi di mana flag `allowDiskUse: true` tetap tidak dapat menyelamatkan eksekusi pipeline agregasi dari kegagalan crash!

#### Skenario Kasus Produksi
11. **Skenario A**: Query agregasi analitik dashboard Anda tiba-tiba mengalami error `16436: Object is too large to qualify for aggregate stage`. Analisis tahapan apa yang paling mungkin menyebabkan error ini dan bagaimana cara mengatasinya secara terstruktur!
12. **Skenario B**: Database administrator melaporkan lonjakan tajam pada I/O Wait dan penurunan Storage Disk IOPS secara drastis setiap jam 00:00 saat pipeline agregasi rekonsiliasi harian dijalankan, padahal alokasi CPU database hanya terpakai 25%. Di mana letak potensi masalah arsitekturnya?
13. **Skenario C**: Anda memiliki cluster sharded dengan 10 shard. Anda menjalankan query agregasi kompleks dengan `$group` dan `$sort` di akhir pipeline. Anda mengamati bahwa 9 shard menyelesaikan pekerjaannya dalam 500ms, namun query keseluruhan membutuhkan waktu 18 detik untuk kembali ke client. Identifikasi komponen cluster yang menjadi bottleneck dan jelaskan alur remediasinya!

---

#### Jawaban Quiz

##### Kunci Jawaban Basic
1. Batasan default adalah **100 Megabytes (MB)** per stage. Jika stage non-streaming melebihi batas ini tanpa `allowDiskUse: true`, engine agregasi melempar error pengecualian.
2. Tidak selalu. Pipeline Optimizer memiliki aturan optimasi *Predicate Pushdown*. Jika stage di antara awal pipeline dan stage `$match` tidak mengubah bentuk dokumen atau kardinalitas baris secara mendasar (misalnya hanya ada `$sort`), MongoDB akan secara otomatis memajukan stage `$match` ke posisi paling awal untuk memanfaatkan indeks. Namun, jika didahului oleh `$group` atau `$project` komputasi baru, *Predicate Pushdown* tidak dapat dilakukan dan memicu proses unindexed filter.
3. `$out` bersifat destruktif dan menggantikan (*atomic replace*) seluruh koleksi tujuan secara total (koleksi lama dihapus dan ditimpa baru). `$merge` bersifat non-destruktif dan inkremental: ia dapat melakukan operasi update, insert, replace, merge fields, atau fail langsung pada level individual dokumen yang cocok tanpa menghapus data historis lain di koleksi target.
4. Format correlated pipeline memungkinkan evaluasi ekspresi kondisi yang sangat fleksibel (misal menggabungkan multiple predicates `$and`, `$or`, filter temporal rentang waktu, hingga nested projections) sebelum dokumen relasi dikembalikan, sehingga memotong ribuan dokumen foreign collection yang tidak relevan langsung di tingkat database engine sebelum diubah menjadi BSON array.
5. Operator `$setWindowFields`.

##### Kunci Jawaban Intermediate
6. SBE mengubah pemrosesan dari iterator berbasis dokumen BSON dinamis menjadi arsitektur berbasis *typed slot array* dengan *vectorized-like execution model*. Komputasi numerik dilakukan langsung di slot memori kontinu primitif C++, menghindari alokasi heap pointer dokumen BSON, meniadakan dereferensi objek berulang, dan memaksimalkan *CPU L1/L2 instruction cache locality*.
7. Targeted routing terjadi jika tahap pertama dari pipeline adalah operator `$match` yang mendefinisikan equality atau range predicate secara eksplisit pada **Shard Key** koleksi tersebut. Jika tidak memuat Shard Key pada kondisi filter awal, query router (`mongos`) wajib mengirim perintah ke seluruh shard (*scatter-gather*).
8. Karena operator `$facet` mengeksekusi multiple sub-pipelines secara independen dan menyatukan outputnya ke dalam satu dokumen BSON array per facet. Seluruh hasil dari setiap cabang facet harus disimpan di memori hingga tahapan selesai. Selain itu, sebelum MongoDB versi 7.0, `$facet` memiliki keterbatasan integrasi terhadap disk spillover, sehingga memproses data masif di dalam facet hampir dipastikan memicu OOM memory error limit.
9. *Top-K Sort* menggabungkan `$sort` dan `$limit` menjadi satu algoritma heap sort internal yang hanya mempertahankan sejumlah `K` dokumen berbobot tertinggi di memori (memory bound: $O(K)$ alih-alih $O(N)$). Sedangkan standar disk sorting memaksa seluruh $N$ dokumen ditulis ke file sementara partisi disk, diurutkan via merge-sort multi-phase, baru kemudian diambil sejumlah limit yang diinginkan.
10. Skenario di mana dokumen individual keluaran dari suatu tahapan (misalnya hasil akumulasi `$push` pada `$group` atau hasil array penggabungan `$lookup`) melampaui batas absolut BSON Document Size yaitu **16MB**, atau jika memori melampaui batas pada tahapan internal yang tidak mendukung disk-spillover sepenuhnya (misal implementasi legacy `$facet`).

##### Kunci Jawaban Skenario Kasus Produksi
11. **Skenario A**: Error disebabkan oleh penggunaan operator akumulator `$group` seperti `$push` atau `$addToSet` yang mengonsolidasi terlalu banyak data ke dalam satu array dokumen tunggal, sehingga dokumen tunggal hasil agregasi tersebut menembus batas maksimal BSON limit 16MB. **Solusi**: Hindari pengelompokan array masif via `$push`. Ubah arsitektur menggunakan pendekatan relasional atau stream output menggunakan `$merge` secara flat per baris tanpa mengonsolidasikannya ke dalam nested single array.
12. **Skenario B**: Terjadi peristiwa masif *Disk Spilling to Storage* akibat pipeline agregasi harian melampaui batas memori 100MB RAM per stage, dan dipaksa menggunakan disk (`allowDiskUse: true`). CPU idle (hanya 25%) karena thread database mengalami *I/O blocking wait* saat membaca dan menulis jutaan temporary files terenkripsi di swap storage database engine. **Solusi**: Buat Compound Index penutup (*Covered Index*) yang sesuai dengan urutan `$match` dan `$sort`, perbaiki pipeline untuk membuang field besar via early `$project`, dan ubah filter agregasi menjadi batch time-window yang lebih kecil.
13. **Skenario C**: Bottleneck terletak pada **Merge Node** (biasanya adalah Primary Shard database atau instance `mongos`). Shard 1 hingga 10 berhasil memfilter data secara cepat secara lokal, namun jutaan unreduced/unsorted stream data dikirim bersamaan melalui jaringan internal ke satu merge node tunggal untuk proses `$group` final atau sorting global. Ini memicu *single-thread CPU bottleneck* dan *network saturation* pada merge node tersebut. **Solusi**: Pindahkan tahapan agregasi parsial ke local shard, manfaatkan stage `$merge` langsung ke sharded collection output untuk mendistribusikan fase penulisan, atau pastikan shard key dilibatkan dalam `$group` partition key sehingga penggabungan terdistribusi merata antar shard.

---

### 16. Summary
- Aggregation Pipeline modern di MongoDB beroperasi menggunakan **Slot-Based Execution Engine (SBE)** yang secara dramatis mereduksi alokasi BSON heap, memanfaatkan optimasi CPU tingkat rendah, dan secara otomatis melakukan *stage coalescing* serta *predicate pushdown*.
- Desain eksekusi pipeline berskala enterprise menuntut peletakan `$match` berbasis indeks majemuk di posisi awal, eliminasi payload field berlebih sedini mungkin via `$project`, dan penggunaan correlated sub-pipeline pada `$lookup` guna menghindari ledakan data memori.
- Limitasi komputasi memori 100MB per stage mengharuskan evaluasi mendalam sebelum mengaktifkan flag `allowDiskUse: true`, karena disk spilling memicu degradasi latensi I/O disk yang signifikan.
- Untuk analitik berulang dan pemrosesan data bervolume terabyte pada Sharded Cluster, operator `$merge` menyediakan kemampuan pembaruan materialisasi inkremental terdistribusi yang aman secara zero-downtime, atomik, dan tahan terhadap kegagalan beban OLTP.