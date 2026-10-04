# Kurikulum Enterprise: MongoDB Internals & Production Architecture
**Kategori:** 04-Backend-and-Database  
**Bab 05:** BAB-05-Indexing-Strategies-B-Tree-Internals-Query-Tuning  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Software Engineer / Lead Database Engineer diharapkan mampu:

1. **Menganalisis dan Membedah Arsitektur WiredTiger B-Tree:** Menjelaskan siklus hidup halaman data (*in-memory* vs *on-disk*), interaksi *hazard pointers*, algoritma *eviction server*, serta dampaknya terhadap latensi p99.
2. **Menguasai Formulasi Compound Index Tingkat Lanjut:** Mengimplementasikan aturan **ESR (Equality, Sort, Range)** secara presisi untuk mengeliminasi pemrosesan in-memory sort (`SORT` stage) dan meminimalkan rasio `totalKeysExamined` terhadap `nReturned`.
3. **Mendiagnosis dan Mengoptimasi Query Execution Plan:** Menafsirkan output `explain("allPlansExecution")`, mengidentifikasi de-optimasi akibat *Plan Cache mutation*, serta memitigasi anomali *Index Filter*.
4. **Mendesain Arsitektur Special Index Enterprise:** Mengimplementasikan *Partial*, *TTL*, *Wildcard*, dan *Collation-aware Indexes* tanpa memicu lonjakan degradasi performa I/O write amplification.
5. **Mengelola Strategi Zero-Downtime Indexing:** Melakukan *rolling index builds* pada multi-node Replica Sets dan Sharded Clusters di lingkungan produksi bertransaksi tinggi (>50.000 write ops/sec).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- Pengetahuan fundamental arsitektur MongoDB (Replica Set, Oplog, WiredTiger basics).
- Konsep dasar algoritma struktur data: Binary Search Tree, B-Tree, dan Kompleksitas Asimptotik Big-O.
- Pemahaman sistem operasi Linux: *Virtual Memory Subsystem*, *Page Cache*, *Dirty Pages*, *I/O Scheduler*, serta utilitas diagnostik (`iostat`, `vmstat`).
- Kemampuan membaca dan mengoperasikan sintaks query agregasi MongoDB melalui Shell (`mongosh`) dan Driver Enterprise (Node.js/TypeScript atau Go).

---

## 3. Concept & Internal Architecture

### 3.1 WiredTiger Storage Engine: Struktur B-Tree & Page Lifecycle

MongoDB menggunakan WiredTiger sebagai default storage engine. Berbeda dengan implementasi relasional klasik yang menyimpan data dan indeks dalam struktur file seragam, WiredTiger memperlakukan *collections* dan *indexes* sebagai B-Tree terpisah yang direpresentasikan oleh tabel individual di disk (`collection-*.wt` dan `index-*.wt`).

```
+------------------------------------------------------------------------------------+
|                               WiredTiger Cache                                     |
|                                                                                    |
|  +--------------------+    Hazard Pointers    +---------------------------------+  |
|  |   Root Page        |---------------------> | Internal Pages (WT_PAGE_INDEX)  |  |
|  |  (WT_PAGE_INDEX)   |                       | (Routing / Search Keys)         |  |
|  +--------------------+                       +---------------------------------+  |
|                                                              |                     |
|                                                              v                     |
|                                               +---------------------------------+  |
|                                               | Leaf Pages (WT_PAGE_ROW_LEAF)   |  |
|                                               | Keys + RecordIDs (Disk Pointers)|  |
|                                               +---------------------------------+  |
+----------------------------------------------------------------|-------------------+
                               Reconciliation & Eviction         |
                               (Compression: Snappy/ZSTD)        v
+------------------------------------------------------------------------------------+
|                         Operating System Page Cache & Disk                         |
|  +-------------------------------------------------------------------------------+ |
|  | Physical Blocks (4KB - 64KB) on Disk: index-xxx-xxx.wt                         | |
|  +-------------------------------------------------------------------------------+ |
+------------------------------------------------------------------------------------+
```

#### Struktur Halaman (Pages)
WiredTiger B-Tree terdiri dari tiga tingkatan halaman:
1. **Root Page:** Titik masuk traversal indeks.
2. **Internal Pages (`WT_PAGE_INDEX`):** Menyimpan router keys dan pointer memori ke child page. Internal page tidak pernah menyimpan data payload ataupun `RecordID`.
3. **Leaf Pages (`WT_PAGE_ROW_LEAF`):** Menyimpan pasangan *Index Key* dan *RecordID* (int64 integer 64-bit yang memetakan posisi dokumen di storage collection).

#### Hazard Pointers (Lock-Free In-Memory Concurrency)
Untuk membaca dan memodifikasi halaman memori secara konkuren tanpa menggunakan spinlock atau mutex berat pada level pembacaan, WiredTiger mengimplementasikan **Hazard Pointers**.
- Ketika thread query menavigasi B-Tree, thread tersebut mendaftarkan pointer halaman yang sedang diakses ke dalam *hazard pointer table*.
- Eviction server tidak dapat membersihkan (*evict*) atau memodifikasi tata letak memori halaman yang sedang diproteksi oleh hazard pointer aktif. Ini menjamin referensi memori tetap valid tanpa memerlukan global read lock.

#### Eviction Server & Cache Pressure
WiredTiger mengalokasikan RAM untuk *cache* sebesar `max(50% of (RAM - 1 GB), 256 MB)` secara default. Siklus hidup halaman melibatkan:
- **Clean Pages:** Halaman di memori yang identik dengan blok di disk. Jika batas *eviction trigger* tercapai (default 80% dari ukuran cache), clean page akan dibuang (*dropped*) tanpa I/O disk.
- **Dirty Pages:** Halaman yang termodifikasi oleh operasi *insert*, *update*, atau *delete*. Jika dirty pages melebihi ambang batas (default 5% hingga 20%), **Reconciliation Thread** mengompresi halaman tersebut (menggunakan Snappy atau ZSTD) dan menulisnya ke disk. Jika dirty cache melampaui 20%, client worker threads akan dipaksa melakukan *in-client eviction*, yang menyebabkan lonjakan tajam pada *write latency* (latency stalls).

### 3.2 Query Optimization Engine & Plan Cache Internals

Query execution MongoDB dieksekusi melalui beberapa tahapan internal:

```
 Incoming Query
       │
       ▼
┌──────────────┐      Hit      ┌────────────────────────────────┐
│ Plan Cache?  ├──────────────►│ Execute Cached Candidate       │
└──────┬───────┘               └──────────────┬─────────────────┘
       │ Miss / Evicted                       │
       ▼                                      │ Fail (Re-plan)
┌─────────────────────────────────┐           │
│ Multi-Plan Execution (The Race) │◄──────────┘
│  - Candidate A: IXSCAN (idx_1)  │
│  - Candidate B: IXSCAN (idx_2)  │
│  - Candidate C: COLLSCAN        │
└──────────────┬──────────────────┘
       │
       │ Evaluasi: Plan mana yang menghasilkan N dokumen
       │ pertama dengan work units / disk reads terendah?
       ▼
┌─────────────────────────────────┐
│ Winner Selection                │
│  - Menghasilkan PlanCacheEntry  │
│  - Write to Plan Cache          │
└──────────────┬──────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│ Execution Engine (Pull-based)   │
│  IXSCAN ──► FETCH ──► SORT ──►  │
└─────────────────────────────────┘
```

1. **Query Parsing & Normalization:** Query dikonversi menjadi canonical query tree.
2. **Plan Cache Lookup:** Engine memeriksa apakah canonical shape query telah memiliki entri di *Plan Cache*.
3. **Multi-Plan Execution (The Trial Race):** Jika terjadi *cache miss*, Query Optimizer membuat beberapa kandidat rencana eksekusi dan mengeksekusinya secara paralel selama sejumlah *works units* (biasanya iterasi pembacaan dokumen pertama, default 101 dokumen atau seluruh koleksi jika <101).
4. **Plan Evaluation Metric:** Rencana yang paling cepat menyelesaikan scanning tanpa disk-fetch berlebih atau yang menyelesaikan pengembalian seluruh hasil batch pertama dinyatakan sebagai **Winning Plan**.
5. **Plan Cache Invalidation:** Entri cache akan gugur jika:
   - Terjadi perubahan indeks (create/drop index).
   - Ambang batas mutasi data tercapai (rasio perubahan volume collection).
   - Terjadi pemanggilan `mongod` restart atau flushing eksplisit.
   - Evaluasi cached plan gagal memenuhi performa awal (misal membaca terlalu banyak docs tanpa return data).

---

## 4. Why & What: Mengapa Desain Indeks Menentukan Skalabilitas

### The Problem: False Sense of Security dengan Default Indexes
Banyak sistem enterprise mengalami penurunan performa drastis saat koleksi bertumbuh dari jutaan menjadi ratusan juta dokumen. Hal ini terjadi karena:
- Pembuatan indeks parsial atau un-optimized indeks sering kali menghasilkan `IXSCAN` semu, di mana `totalKeysExamined` hampir sama besarnya dengan `totalDocsExamined`.
- **Working Set Spilling:** Ukuran indeks gabungan (*index working set*) melebihi kapasitas WiredTiger Cache RAM, memicu pembacaan random I/O ke SSD/NVMe secara konstan.
- **Write Amplification:** Penambahan satu indeks pada koleksi dengan *write rate* 20.000 ops/sec berarti menambahkan puluhan ribu operasi mutasi B-tree per detik, memicu *checkpoint stalls* dan *cache dirty fill*.

### The Solution: Surgical Indexing
Dengan memahami mekanika *WiredTiger B-Tree* dan mendesain indeks berdasarkan pola akses hardware dan computational stages, latensi eksekusi ditekan dari satuan detik (`O(N)`) ke satuan milidetik/sub-milidetik (`O(log K) + O(M)`), serta meminimalkan footprint memori RAM secara signifikan.

---

## 5. How: Workflow Detail & Implementasi Formula ESR

Aturan **ESR (Equality, Sort, Range)** adalah metodologi deterministik dalam merancang *Compound Index* multivariat untuk memastikan efisiensi pencarian tingkat tertinggi.

```
          Indeks: { tenantId: 1, status: 1, createdAt: 1, amount: 1 }
                     ▲            ▲            ▲            ▲
                     │            │            │            │
                     └─────┬──────┘            │            │
                           │                   │            │
                    [E] EQUALITY          [S] SORT     [R] RANGE
```

### Algoritma Perancangan ESR:
1. **[E] Equality First:** Letakkan field dengan operator presisi (`$eq`, scalar match) di urutan terdepan. Hal ini secara langsung mempersempit pencarian ke subtree B-Tree spesifik, memangkas ruang pencarian dokumen secara instan.
2. **[S] Sort Next:** Letakkan field yang digunakan dalam operator `.sort()` langsung setelah equality fields. Ini memastikan dokumen yang diakses sudah tersusun dalam urutan memori yang tepat sesuai kebutuhan query, meniadakan stage `SORT` (Blocking In-Memory Sort).
3. **[R] Range Last:** Field dengan operator jangkauan (`$gt`, `$gte`, `$lt`, `$lte`, `$in`) harus ditempatkan di posisi paling akhir dari compound index. Sekali B-Tree menavigasi field range, pointer traversal harus memindai (*scan*) daun-daun B-Tree berikutnya, sehingga properti sort dari field setelah range akan hilang.

> **Catatan Arsitektural untuk `$in`:** Operator `$in` secara internal diperlakukan sebagai serangkaian perbandingan *equality* berulang. Namun, jika digunakan bersama dengan `.sort()`, MongoDB sering kali tidak dapat menjamin urutan traversing global, yang menyebabkan engine tetap memerlukan stage in-memory `SORT` kecuali index didesain sangat presisi.

---

## 6. Analogy & Diagram ASCII

### Analogi: Katalog Buku Perpustakaan Nasional Multi-Lantai
Bayangkan sebuah arsip nasional dengan jutaan berkas transaksi:
- **COLLSCAN:** Anda mencari satu map spesifik dengan berjalan menyusuri setiap lorong, membuka setiap laci, dari lantai 1 sampai lantai 10.
- **Sub-optimal Index:** Anda punya indeks berdasarkan `Tanggal Pinjam` (Range), baru kemudian `ID Pengguna` (Equality). Anda harus mengambil semua map dari 1 Januari sampai 31 Desember, membukanya satu per satu, hanya untuk membuang map yang bukan milik pengguna yang dimaksud.
- **Optimal ESR Index:** Anda langsung pergi ke rak `ID Pengguna` (Equality), membuka folder yang sudah berurutan berdasarkan `Waktu Transaksi` (Sort), dan hanya menarik dokumen yang berada di dalam jendela waktu yang diinginkan (Range). Anda tidak menyentuh map lain, dan tidak perlu menyusun ulang berkas di meja baca Anda.

### Diagram B-Tree Index Traversal (ESR Applied)

```
Query: { companyId: "C100", status: "COMPLETED", transactionDate: { $gte: ISODate("2024-01-01") } }
Sort:  { transactionDate: 1 }
Index: { companyId: 1, status: 1, transactionDate: 1 }

                     [ Root Node: Internal Page ]
                     /                          \
       ["C050", ...]                              ["C100", "ACTIVE", ...]
                                                  /
             +-----------------------------------+
             |
             v
 [ Leaf Page: Keys & RecordIDs ]
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ Key: ("C100", "COMPLETED", 2023-12-31) -> RecordID: 10452  (Discard: Range)│
 │ Key: ("C100", "COMPLETED", 2024-01-01) -> RecordID: 10459  [MATCH 1]       │
 │ Key: ("C100", "COMPLETED", 2024-01-02) -> RecordID: 10488  [MATCH 2]       │
 │ Key: ("C100", "COMPLETED", 2024-01-03) -> RecordID: 10512  [MATCH 3]       │
 │ Key: ("C100", "FAILED",    2024-01-01) -> RecordID: 10599  (Out of Boundary│
 └─────────────────────────────────────────────────────────────────────────────┘
  Pipeline: IXSCAN -> FETCH -> Client (No Memory Sorting Stage Required)
```

---

## 7. Practical Implementation (Standar Industri)

### 7.1 Setup Data & Diagnostic Tuning Menggunakan TypeScript Driver

Berikut adalah implementasi class monitoring dan query execution analyzer menggunakan Node.js/TypeScript resmi dari MongoDB Driver:

```typescript
// query-tuner.service.ts
import { MongoClient, Db, Document, ExplainVerbosity } from 'mongodb';

export interface ExecutionMetrics {
  stage: string;
  nReturned: number;
  totalKeysExamined: number;
  totalDocsExamined: number;
  executionTimeMillis: number;
  isCovered: boolean;
  inMemorySort: boolean;
}

export class MongoQueryTuner {
  private db: Db;

  constructor(client: MongoClient, dbName: string) {
    this.db = client.db(dbName);
  }

  /**
   * Menjalankan kueri dengan explain level executionStats
   * dan mengekstrak metrik bottleneck secara otomatis.
   */
  async analyzeQueryExecution(
    collectionName: string,
    filter: Document,
    sort: Document = {},
    projection: Document = {}
  ): Promise<ExecutionMetrics> {
    const collection = this.db.collection(collectionName);

    const explainResult = await collection
      .find(filter, { projection })
      .sort(sort)
      .explain('executionStats');

    const executionStats = explainResult.executionStats;
    const winningPlan = executionStats.executionStages;

    // Evaluasi apakah sort dilakukan di memori
    const hasSortStage = this.findStageRecursively(winningPlan, 'SORT');
    
    // Evaluasi apakah query tercover penuh oleh index
    const hasFetchStage = this.findStageRecursively(winningPlan, 'FETCH');
    const isCovered = !hasFetchStage && this.findStageRecursively(winningPlan, 'IXSCAN') !== null;

    return {
      stage: winningPlan.stage,
      nReturned: executionStats.nReturned,
      totalKeysExamined: executionStats.totalKeysExamined,
      totalDocsExamined: executionStats.totalDocsExamined,
      executionTimeMillis: executionStats.executionTimeMillis,
      isCovered: isCovered,
      inMemorySort: hasSortStage !== null,
    };
  }

  private findStageRecursively(stage: any, targetStageName: string): any {
    if (!stage) return null;
    if (stage.stage === targetStageName) return stage;

    if (stage.inputStage) {
      const found = this.findStageRecursively(stage.inputStage, targetStageName);
      if (found) return found;
    }

    if (stage.inputStages && Array.isArray(stage.inputStages)) {
      for (const input of stage.inputStages) {
        const found = this.findStageRecursively(input, targetStageName);
        if (found) return found;
      }
    }

    return null;
  }
}
```

### 7.2 Implementasi Advanced Index Types via Script `mongosh`

```javascript
// migrations/001_create_production_indexes.js

db = db.getSiblingDB('enterprise_ledger');

// 1. COMPOUND INDEX DENGAN FORMULA ESR
// Mengoptimalkan filter multi-tenant dengan pengurutan berdasarkan tanggal dan jangkauan nominal
db.transactions.createIndex(
  {
    organizationId: 1, // [E] Equality
    settlementStatus: 1, // [E] Equality
    createdAt: -1,       // [S] Sort
    amount: 1            // [R] Range
  },
  {
    name: "idx_trx_org_status_date_amount",
    background: true // legacy flag, MongoDB 4.2+ menggunakan engine-managed optimized builds
  }
);

// 2. COVERED QUERY OPTIMIZATION
// Menghilangkan stage FETCH sepenuhnya untuk endpoint throughput tinggi
db.transactions.createIndex(
  {
    referenceId: 1,
    organizationId: 1,
    amount: 1,
    settlementStatus: 1
  },
  {
    name: "idx_trx_reference_covered"
  }
);

// 3. PARTIAL INDEX
// Hanya mengindeks transaksi yang berstatus 'UNSETTLED' atau 'DISPUTED'.
// Menghemat hingga 80% RAM dan kapasitas B-Tree dibanding mengindeks seluruh history.
db.transactions.createIndex(
  {
    organizationId: 1,
    dueDate: 1
  },
  {
    name: "idx_trx_unsettled_partial",
    partialFilterExpression: {
      settlementStatus: { $in: ["UNSETTLED", "DISPUTED"] }
    }
  }
);

// 4. WILDCARD INDEX UNTUK DYNAMIC METADATA (JSON PAYLOAD KONSUMEN)
// Hanya mengindeks path sub-dokumen metadata tanpa mengorbankan root document
db.transactions.createIndex(
  { "customMetadata.$**": 1 },
  {
    name: "idx_trx_custom_metadata_wildcard",
    wildcardProjection: {
      "customMetadata.billingId": 1,
      "customMetadata.trackingCode": 1
    }
  }
);
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: High-Throughput Fintech Payment Engine (Payment Gateway)

* **Skala Sistem:** 450 Juta Dokumen Koleksi Transaksi.
* **Workload:** 12.000 Write QPS (mutasi transaksi baru), 8.000 Read QPS (dasbor analitik & callback settlement).
* **Insiden:** Terjadi *CPU utilization spike* (99%), WiredTiger dirty cache menyentuh 24%, memicu latency stall hingga query p99 naik dari 18ms menjadi 4.200ms.

#### Investigasi Query Bottleneck
Dasbor merchant memanggil query berikut:
```javascript
db.transactions.find({
  merchantId: "MCH_982312",
  createdAt: { $gte: ISODate("2024-03-01T00:00:00Z"), $lte: ISODate("2024-03-07T23:59:59Z") },
  currency: "IDR"
}).sort({ createdAt: -1 }).limit(50);
```

Indeks yang ada sebelumnya:
```javascript
{ merchantId: 1, createdAt: -1, currency: 1 }
```

Analisis `executionStats`:
```json
{
  "executionStages": {
    "stage": "FETCH",
    "nReturned": 50,
    "executionTimeMillis": 3810,
    "totalKeysExamined": 450120,
    "totalDocsExamined": 450120,
    "inputStage": {
      "stage": "IXSCAN",
      "indexName": "merchantId_1_createdAt_-1_currency_1"
    }
  }
}
```

#### Akar Masalah:
Aturan ESR dilanggar. Indeks menempatkan field `createdAt` (Range) **sebelum** `currency` (Equality). Akibatnya:
- Engine menggunakan `merchantId`, lalu memindai seluruh *range* `createdAt` (sebanyak 450.120 keys).
- Karena `currency` berada setelah range, B-Tree tidak bisa memanfaatkan filter index untuk `currency` secara efisien; setiap dokumen harus di-*fetch* ke memori untuk mengevaluasi apakah `currency === "IDR"`.
- Ratio: $\frac{\text{totalKeysExamined}}{\text{nReturned}} = \frac{450.120}{50} \approx 9.002$. Sistem membaca 9.000 halaman B-tree hanya untuk mengembalikan 50 dokumen.

#### Solusi Implementasi:
Merekonstruksi indeks sesuai formulasi ESR:
- Equality: `merchantId`, `currency`
- Sort & Range gabungan: `createdAt` (memenuhi sort descending dan range filter)

```javascript
// Indeks Baru yang Dioptimasi
db.transactions.createIndex(
  { merchantId: 1, currency: 1, createdAt: -1 },
  { name: "idx_opt_merchant_curr_created" }
);
```

#### Hasil Metrik Pasca Rekonstruksi:
- `executionTimeMillis`: **1.4 ms** (turun 99.96%).
- `totalKeysExamined`: **50**.
- `totalDocsExamined`: **50**.
- `in-memory sort`: **false**.
- CPU Load MongoDB Cluster turun dari 99% ke 12%. Dirty cache stabil pada <3%.

---

## 9. Trade-offs: Architectural Cost Analysis

Setiap indeks dalam arsitektur MongoDB membawa konsekuensi operasional yang saling berlawanan:

| Dimensi | Keuntungan Indeks Maksimal | Biaya & Dampak Negatif |
| :--- | :--- | :--- |
| **Latensi Baca (Read)** | Menekan kompleksitas waktu dari $O(N)$ ke $O(\log K + M)$. | Nol, pembacaan terakselerasi drastis. |
| **Latensi Tulis (Write)** | Tidak ada. | Setiap operasi insert/delete/update pada field terindeks memaksa modifikasi branch/leaf B-Tree dan penulisan Oplog tambahan. |
| **Kebutuhan Memori (RAM)** | Kueri terlindungi (Covered) tidak menyentuh collection files. | Indeks harus muat di *WiredTiger Cache*. Jika Index Size > RAM, terjadi *page fault thrashing* dan disk read saturation. |
| **Storage Overhead** | Struktur terkompresi leaf/internal nodes. | Index amplification: Total ukuran indeks sering kali melampaui ukuran data fisik dokumen asli (*uncompressed data*). |
| **WiredTiger Eviction** | Query traversal cepat membersihkan hazard pointers. | Dirty page accumulation dari indeks mempercepat batas 20% dirty eviction, memicu client throttling. |

---

## 10. Common Mistakes & Production Troubleshooting

### Kesalahan Fatal Umum:

1. **Inverted ESR Order:** Menempatkan Range sebelum Equality/Sort. Hal ini merusak struktur ordering B-Tree turunan berikutnya.
2. **Regex Query Prefix Trap:** Menjalankan query regex tanpa leading anchor (`/pattern/` vs `/^pattern/`). Regex tanpa anchor (`^`) memaksa engine melakukan pemindaian index penuh (`IXSCAN` dengan `totalKeysExamined = totalKeysInIndex`).
3. **Multikey Index Cartesian Bloat:** Membuat compound index yang melibatkan **lebih dari satu array field**. MongoDB akan menolak pembuatan index jika dua field bernilai array karena akan menghasilkan kombinasi Cartesius yang merusak B-Tree memory bounds.
4. **Index Explosion:** Memiliki >20 indeks pada satu koleksi aktif. Hal ini membunuh write performance dan memicu memory starvation di WiredTiger.

### Panduan Diagnostik & Triage:

#### Masalah: Query Planner Menggunakan Indeks yang Salah (Plan Cache Pollution)
**Gejala:** Kueri yang biasanya berjalan 5ms mendadak naik ke 2.000ms tanpa perubahan skema.  
**Diagnostik:**
```javascript
// 1. Cek entri plan cache aktif untuk kueri terkait
db.transactions.getPlanCache().list([
  { $match: { "createdAfter": { $exists: true } } }
]);

// 2. Evaluasi winning plan vs rejected plans
db.transactions.find({ merchantId: "MCH_1", amount: { $gt: 1000 } })
  .explain("allPlansExecution");
```
**Remediasi Cepat di Produksi:**
```javascript
// Bersihkan Plan Cache khusus canonical query shape tersebut
db.transactions.getPlanCache().clearPlansByQuery({
  merchantId: "MCH_1",
  amount: { $gt: 1000 }
});
```

---

## 11. Best Practices & Production Checklist

### Pre-Deployment Checklist (Index Engineering):
- [ ] **Validasi Formula ESR:** Apakah semua filter query telah memposisikan Equality di depan, Sort di tengah, dan Range di akhir?
- [ ] **Verifikasi Covered Query:** Untuk query read-intensive berfrekuensi tinggi, pastikan proyeksi data mengembalikan field yang ada di dalam indeks saja (`_id: 0` jika `_id` tidak ada di compound index).
- [ ] **Gunakan Partial Index:** Jangan mengindeks data statis historis atau dokumen dengan status terminal (`status: "ARCHIVED"`) kecuali secara eksplisit dibutuhkan.
- [ ] **Hindari Implicit Coercion:** Pastikan tipe data pada filter sesuai dengan tipe data pada index (misal: String vs Int32/Int64). Type mismatch menyebabkan MongoDB melakukan full scanning.

### Zero-Downtime Index Creation Strategy (Replica Set):
Mulai MongoDB 4.2+, implementasi `createIndexes` dilakukan secara *hybrid* tanpa memblokir pembacaan dan penulisan global. Namun, untuk koleksi mission-critical dengan ratusan juta data, gunakan **Rolling Index Build**:

1. Ambil satu Secondary node offline (atau isolasi dari routing load balancer).
2. Restart instance `mongod` secara standalone pada port terpisah tanpa argumen `--replSet`.
3. Buat indeks secara langsung di standalone node tersebut:
   ```javascript
   db.transactions.createIndex({ organizationId: 1, createdAt: -1 }, { name: "idx_rolling_1" });
   ```
4. Setelah build selesai, restart kembali node dengan argumen `--replSet` dan biarkan mengejar ketertinggalan *oplog*.
5. Ulangi proses pada setiap Secondary.
6. Lakukan `stepDown()` pada Primary node, lalu ulangi proses pembuatan indeks pada mantan Primary tersebut.

---

## 12. Hands-on Practice: Reproduksi, Analisis & Tuning

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File: `hands-on/m02/setup_environment.js`
```javascript
// Setup dummy data sebanyak 200,000 dokumen untuk pengujian
db = db.getSiblingDB('tuning_lab');
db.audit_logs.drop();

print("Generating 200,000 log records...");
const bulk = db.audit_logs.initializeUnorderedBulkOp();
const services = ["auth-service", "payment-service", "gateway-api", "notification"];
const statuses = ["SUCCESS", "FAILED", "PENDING", "RETRY"];

for (let i = 0; i < 200000; i++) {
  bulk.insert({
    traceId: "TRX-" + i,
    serviceName: services[i % services.length],
    status: statuses[i % statuses.length],
    responseCode: (i % statuses.length === 1) ? 500 : 200,
    durationMs: Math.floor(Math.random() * 2000),
    timestamp: new Date(Date.now() - (i * 60000)),
    metadata: {
      clientIp: "192.168.1." + (i % 255),
      retryCount: i % 3
    }
  });
  if (i % 10000 === 0 && i > 0) {
    bulk.execute();
    print("Inserted " + i + " records");
  }
}
bulk.execute();
print("Data seeding completed.");
```

### Langkah Praktikum:

#### Langkah 1: Eksekusi Baseline Unindexed Query
Jalankan query tanpa indeks komparatif dan perhatikan metrics:
```javascript
// hands-on/m02/test_collscan.js
db = db.getSiblingDB('tuning_lab');

const exp = db.audit_logs.find({
  serviceName: "payment-service",
  status: "FAILED",
  durationMs: { $gt: 500 }
}).sort({ timestamp: -1 }).explain("executionStats");

print("--- BASELINE COLLSCAN ---");
print("Execution Stage: " + exp.executionStats.executionStages.stage);
print("Keys Examined: " + exp.executionStats.totalKeysExamined);
print("Docs Examined: " + exp.executionStats.totalDocsExamined);
print("Execution Time: " + exp.executionStats.executionTimeMillis + "ms");
```

#### Langkah 2: Buat Indeks Non-ESR (Anti-Pattern)
```javascript
// Range ditaruh sebelum Equality
db.audit_logs.createIndex({ durationMs: 1, serviceName: 1, status: 1, timestamp: -1 }, { name: "idx_bad" });

// Uji kembali kueri
const expBad = db.audit_logs.find({
  serviceName: "payment-service",
  status: "FAILED",
  durationMs: { $gt: 500 }
}).sort({ timestamp: -1 }).explain("executionStats");

print("--- BAD INDEX PERFORMANCE ---");
print("Execution Stage: " + expBad.executionStats.executionStages.stage);
print("Keys Examined: " + expBad.executionStats.totalKeysExamined);
print("Docs Examined: " + expBad.executionStats.totalDocsExamined);
print("In-Memory Sort Stage: " + (expBad.executionStats.executionStages.stage === "SORT" || !!expBad.executionStats.executionStages.inputStage?.stage?.includes("SORT")));
print("Execution Time: " + expBad.executionStats.executionTimeMillis + "ms");
```

#### Langkah 3: Implementasikan Optimal ESR Index
```javascript
db.audit_logs.dropIndex("idx_bad");

// Formula ESR: Equality (serviceName, status) -> Sort (timestamp) -> Range (durationMs)
db.audit_logs.createIndex(
  { serviceName: 1, status: 1, timestamp: -1, durationMs: 1 },
  { name: "idx_optimal_esr" }
);

const expOptimal = db.audit_logs.find({
  serviceName: "payment-service",
  status: "FAILED",
  durationMs: { $gt: 500 }
}).sort({ timestamp: -1 }).explain("executionStats");

print("--- OPTIMAL ESR PERFORMANCE ---");
print("Execution Stage: " + expOptimal.executionStats.executionStages.stage);
print("Keys Examined: " + expOptimal.executionStats.totalKeysExamined);
print("Docs Examined: " + expOptimal.executionStats.totalDocsExamined);
print("Execution Time: " + expOptimal.executionStats.executionTimeMillis + "ms");
```

---

## 13. Exercises

### Level Easy
Diberikan query berikut:
```javascript
db.users.find({ country: "ID", age: { $gte: 18 } }).sort({ signupDate: 1 });
```
Rancang spesifikasi compound index terbaik berdasarkan aturan ESR.
* **Jawaban:** `{ country: 1, signupDate: 1, age: 1 }`
  - Equality: `country`
  - Sort: `signupDate`
  - Range: `age`

### Level Medium
Sebuah endpoint pencarian memiliki query pattern:
```javascript
db.products.find(
  { category: "ELECTRONICS", brand: { $in: ["SONY", "APPLE"] }, price: { $lte: 15000000 } },
  { _id: 0, category: 1, brand: 1, price: 1, modelName: 1 }
).sort({ price: 1 });
```
Optimalkan query di atas agar menjadi **Covered Query** sepenuhnya tanpa stage `FETCH` dan tanpa memory sort. Rancang skema index dan tuliskan query string pembuatannya!

### Level Hard
Sistem mencatat latensi tinggi pada operasi write pada koleksi `sensor_telemetry` yang memiliki 15 indeks. Dari audit log, 80% query telemetry hanya memfilter data 24 jam terakhir yang statusnya bernilai `ALERT`. Sementara data historis (> 24 jam) hanya diakses oleh proses batch night reporting bulanan.
* Rancang arsitektur strategi index baru (manfaatkan *Partial Indexes*, *TTL*, dan konsolidasi index) untuk menurunkan write amplification dan cache pressure sebesar minimal 40%.

---

## 14. Challenge: High-Frequency Sharded Invalidation Bottleneck

Anda adalah Principal Data Architect di platform ride-hailing global.
- Koleksi `active_driver_locations` menerima 80.000 location pings per detik (Update & Upsert).
- Skema dokumen mencakup:
  ```json
  {
    "_id": ObjectId("..."),
    "driverId": "DRV_89231",
    "cityId": "JKT",
    "location": { "type": "Point", "coordinates": [106.8456, -6.2088] },
    "status": "ON_TRIP", // Enums: IDLE, ON_TRIP, OFFLINE
    "rating": 4.98,
    "lastPing": ISODate("2024-03-24T10:00:00Z")
  }
  ```
- Aplikasi dispatch membutuhkan kueri geospatial untuk mencocokkan pengemudi terdekat:
  - Radius: 3KM
  - Filter: `cityId == "JKT"`, `status == "IDLE"`, `rating >= 4.5`
  - Sorting: Jarak geografis terdekat.

**Tantangan Arsitektur:**
1. Desain spesifikasi indexing yang meminimalkan write overhead akibat frekuensi mutasi koordinat GPS yang sangat tinggi tanpa menyebabkan *checkpoint locking*.
2. Pecahkan kontradiksi antara penggunaan indeks Geospatial (`2dsphere`) dengan aturan pemfilteran multi-field (Equality & Range) agar throughput update tetap stabil di atas 75.000 ops/sec.
3. Rancang rencana mitigasi bagaimana replikasi data ke secondary nodes terhindar dari *replication lag* yang disebabkan oleh secondary index application.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konseptual Fundamental (5 Pertanyaan)
1. **Apa fungsi utama dari Hazard Pointers dalam WiredTiger Storage Engine?**
   - A. Menulis data dirty page ke disk secara sekuensial.
   - B. Menyediakan mekanisme lock-free concurrency untuk membaca B-Tree memory page tanpa global lock.
   - C. Mengompresi index blocks menggunakan algoritma Snappy.
   - D. Menghubungkan node Primary ke node Secondary pada Replica Set.
2. **Kapan engine query MongoDB memutuskan untuk menjalankan Multi-Plan Execution (The Race)?**
   - A. Setiap kali ada query baru yang masuk ke database.
   - B. Hanya jika query mengandung operator `$where` atau MapReduce.
   - C. Ketika canonical query shape tidak ditemukan dalam Plan Cache atau entri cache sebelumnya di-invalidasi.
   - D. Setiap 10 menit sekali secara otomatis.
3. **Mengapa stage `SORT` (In-Memory Sort) sangat dihindari dalam query pipeline berkapasitas enterprise?**
   - A. Karena in-memory sort dibatasi oleh limit memori (default 100MB / 32MB tergantung versi) dan memakan CPU cycle yang tinggi.
   - B. Karena in-memory sort mengubah urutan data secara permanen di storage disk.
   - C. Karena in-memory sort memblokir koneksi jaringan client secara sinkron.
   - D. Karena in-memory sort memaksa engine melakukan restart pada node Secondary.
4. **Apa indikator utama dari `executionStats` yang menunjukkan sebuah query berhasil menjadi "Covered Query"?**
   - A. `totalKeysExamined` bernilai 0.
   - B. `stage` bernilai `FETCH` dengan `nReturned` sama dengan `totalDocsExamined`.
   - C. Tidak adanya stage `FETCH` dalam pipeline tree dan `totalDocsExamined` bernilai 0.
   - D. Query memiliki flag `"isCovered": true` secara eksplisit pada root objek explain.
5. **Bagaimana operator Range (`$gt`, `$lt`) mempengaruhi evaluasi field berikutnya pada compound index?**
   - A. Meningkatkan kecepatan traversal field setelahnya secara eksponensial.
   - B. Field setelah operator range tidak dapat lagi digunakan untuk proses sorting berbasis B-Tree index ordering.
   - C. Mengubah index menjadi multikey index secara otomatis.
   - D. Menghapus kebutuhan validasi equality.

### Bagian B: Analisis Tingkat Lanjut (5 Pertanyaan)
6. **Diberikan indeks `{ status: 1, age: 1, name: 1 }` dan query `find({ status: "ACTIVE" }).sort({ name: 1 })`. Mengapa query ini tetap melakukan in-memory sort?**
   - A. Karena `name` berurutan setelah `age` yang tidak disertakan dalam predikat equality kueri, memutus urutan traversal index prefix.
   - B. Karena operator sort bernilai ascending (1).
   - C. Karena `status` bertipe data string.
   - D. Karena koleksi belum di-sharding.
7. **Apa dampak utama jika rasio WiredTiger dirty pages melampaui batas 20% dari total alokasi cache?**
   - A. MongoDB server akan langsung melakukan failover otomatis.
   - B. Semua koneksi baca (*read operations*) akan ditutup secara sepihak.
   - C. Thread aplikasi pemanggil (*client threads*) dipaksa membantu proses penulisan halaman ke disk (*in-client eviction*), memicu latensi tinggi.
   - D. Oplog replica set berhenti mencatat perubahan data.
8. **Kapan penggunaan Partial Index jauh lebih superior dibanding Sparse Index?**
   - A. Ketika field yang diindeks bertipe data array.
   - B. Ketika filter indexing membutuhkan kriteria ekspresi logis yang kompleks (misal: `$gt`, kriteria multi-field, atau nilai spesifik) bukan hanya sekadar pengecekan keberadaan field.
   - C. Hanya jika ukuran collection lebih kecil dari 1GB.
   - D. Saat menggunakan Text search.
9. **Apa yang terjadi pada struktur internal B-Tree jika kita membuat compound multikey index pada dua array field sekaligus: `{ tags: 1, categories: 1 }`?**
   - A. Engine membatasi array hanya hingga 10 elemen.
   - B. MongoDB menolak pembuatan index tersebut dan melempar error pembatasan komputasi kombinatorial Cartesian.
   - C. Index akan berhasil dibuat, tetapi performa baca turun 50%.
   - D. Index secara otomatis diubah menjadi Wildcard Index.
10. **Bagaimana parameter `hidden: true` pada sebuah indeks membantu proses pemeliharaan di lingkungan produksi?**
    - A. Membakar indeks langsung dari disk tanpa mengubah metadata.
    - B. Menyembunyikan indeks dari hacker atau unauthorized users.
    - C. Mengevaluasi dampak performa penghapusan indeks pada query planner tanpa harus benar-benar menghapus struktur data fisiknya di disk.
    - D. Mengompresi ukuran file indeks menjadi 0 bytes.

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: The OOM Incident
Sebuah klaster MongoDB mengalami crash berulang akibat *Out Of Memory (OOM)* pada node Linux. Hasil metrik menunjukkan:
- WiredTiger Cache diset pada 30GB (Server RAM: 64GB).
- Koleksi utama memiliki total ukuran data dokumen 120GB, namun memiliki 18 indeks compound dengan total ukuran index mencapai 75GB.
- Metrik OS: Swap terpakai 100%, IOPS disk berada pada utilisasi 98% (Wait I/O tinggi).

**Pertanyaan:** Jelaskan mekanisme kegagalan sistem ini secara internal dan tindakan korektif arsitektural apa yang harus diambil segera!

#### Skenario 2: The Regex Regression
Sebuah microservice catalog mengalami lonjakan response time dari 20ms menjadi 3.500ms saat memanggil endpoint autocomplete:
```javascript
db.items.find({ sku: /ABC1234/i, storeId: "STR_01" }).limit(10);
```
Indeks yang terpasang pada collection:
```javascript
{ storeId: 1, sku: 1 }
```

**Pertanyaan:** Mengapa indeks yang mengandung `storeId` di awal tetap mengalami degradasi parah pada query tersebut, dan bagaimana perbaikan query atau index pattern-nya?

#### Skenario 3: Wildcard Index Abuse
Tim pengembang mengimplementasikan Wildcard Index `$**` pada root koleksi `user_profiles` berukuran 50 Juta dokumen untuk mendukung field dinamis tanpa migrasi skema. Dua pekan pasca rilis, waktu eksekusi operasi penulisan (*insert/update*) melambat hingga 400%, dan WiredTiger checkpoint latency melonjak drastis.

**Pertanyaan:** Mengapa Wildcard Index global pada root level memicu degradasi tulis masif, dan bagaimana mendesain ulang skema index tanpa kehilangan fleksibilitas atribut dinamis dokumen?

---

### Kunci Jawaban & Technical Justification

#### Bagian A: Konseptual Fundamental
1. **B** — Hazard Pointers memungkinkan pembacaan in-memory B-Tree page secara paralel tanpa write lock, mencegah eviction thread menghapus halaman yang sedang aktif dibaca.
2. **C** — Multi-Plan execution dijalankan ketika query shape belum terdaftar di Plan Cache atau saat plan cache yang ada sudah usang/di-flush.
3. **A** — In-memory sort menghabiskan memori RAM dan komputasi CPU intensif. Jika melampaui ambang batas default (100MB/32MB), query akan gagal (*abort*) kecuali mengizinkan disk spill yang sangat lambat.
4. **C** — Covered query mengembalikan data langsung dari daun B-Tree indeks tanpa perlu mengunjungi lokasi data asli di disk/memory (`totalDocsExamined: 0` dan tidak ada stage `FETCH`).
5. **B** — Operator range mengubah urutan penelusuran traversal B-Tree menjadi non-sekuensial untuk field selanjutnya, sehingga field setelah range tidak dapat mengeksploitasi index order untuk sorting.

#### Bagian B: Analisis Tingkat Lanjut
6. **A** — Compound index menuntut pemenuhan index prefix secara konsisten. Melewatkan field `age` di tengah-tengah membuat engine tidak dapat melompat langsung ke urutan `name` tanpa menyortir ulang di memori.
7. **C** — Ambang batas 20% dirty page memicu mekanisme pertahanan diri WiredTiger: thread aplikasi pembawa request ditahan untuk ikut menulis dirty buffer ke disk, menyebabkan spike latency pada level API.
8. **B** — Partial Index memungkinkan filtering presisi menggunakan operator predikat ekspresi (`$exists`, `$gt`, kondisi majemuk), sedangkan Sparse Index hanya memeriksa eksistensi field semata.
9. **B** — MongoDB secara arsitektural melarang compound multikey index dengan lebih dari satu field bertipe array untuk mencegah ledakan kombinatorik entry B-Tree (*index entry explosion*).
10. **C** — Fitur Hidden Index membuat query optimizer mengabaikan indeks tersebut saat pemilihan rencana eksekusi, memungkinkan engineer menguji apakah ada query yang terdampak sebelum indeks benar-benar di-drop permanen.

#### Bagian C: Skenario Kasus Produksi

##### Solusi Skenario 1:
- **Mekanisme Kegagalan:** Total ukuran indeks (75GB) melampaui total memori fisik yang dialokasikan untuk WiredTiger Cache (30GB). Ketika query mengakses indeks secara acak, terjadi *Index Working Set Thrashing*: WiredTiger secara konstan me-reconcile, meng-evict, dan membaca ulang index pages dari disk via page faults. Akibatnya, I/O disk saturated, Linux kernel kehabisan memori buffer, mulai menggunakan swap, dan memicu OOM Killer untuk menembak proses `mongod`.
- **Tindakan Korektif:**
  1. Hapus redundant/unused indexes dengan menganalisis metrik `$indexStats`.
  2. Ubah full indexes menjadi *Partial Indexes* untuk subset data aktif.
  3. Perbesar RAM host server atau lakukan *sharding* horizontal untuk mendistribusikan index working set ke beberapa shard nodes sehingga total index per node muat di dalam RAM.

##### Solusi Skenario 2:
- **Akar Masalah:** Penggunaan *case-insensitive regex* tanpa prefix anchor (`/ABC1234/i`) memaksa query engine memindai seluruh keys pada branch `storeId: "STR_01"`. Pilihan `i` (case-insensitive) menonaktifkan pencarian binary sekuensial B-Tree reguler karena karakter huruf kecil dan besar memiliki nilai byte yang berbeda dalam struktur index leaf.
- **Tindakan Perbaikan:**
  1. Normalisasi data: Simpan SKU selalu dalam format huruf kapital saat ingress (`skuUpper: "ABC1234"`).
  2. Gunakan query equality standar atau leading regex: `{ storeId: "STR_01", sku: /^ABC1234/ }`.
  3. Jika memerlukan pencarian case-insensitive alami, buat index dengan opsi **Collation** khusus (`strength: 2`).

##### Solusi Skenario 3:
- **Akar Masalah:** Mengindeks `$**` pada root level dokumen memaksa WiredTiger mengekstrak setiap path JSON tunggal, sub-dokumen, dan elemen skalar ke dalam entri B-Tree terpisah. Untuk dokumen dengan 50 field dinamis, satu operasi `insert` memicu 50 penulisan struktur index simultan, menghancurkan write throughput dan membanjiri checkpoint engine.
- **Tindakan Perbaikan:**
  1. Jangan buat wildcard pada root level. Pindahkan atribut dinamis ke sub-dokumen terisolasi (misal: sub-dokumen `attributes: { ... }`).
  2. Pasang Wildcard Index secara terisolasi pada namespace sub-dokumen tersebut:
     ```javascript
     db.user_profiles.createIndex({ "attributes.$**": 1 });
     ```
  3. Batasi jangkauan field wildcard menggunakan `wildcardProjection` untuk hanya mencakup field-field yang benar-benar difilter oleh kueri bisnis.

---

## 16. Summary

Performa kueri berskala enterprise pada MongoDB bukanlah hasil dari komputasi CPU murni, melainkan efisiensi pemanfaatan struktur data di dalam memori. Menguasai arsitektur B-Tree WiredTiger, Hazard Pointers, serta siklus hidup Cache Pages memungkinkan perancangan sistem yang kebal terhadap lonjakan traffic. 

Formulasi **ESR (Equality, Sort, Range)** merupakan landasan utama pembuatan compound index:
- **Equality** memotong ruang pencarian secara presisi.
- **Sort** menjamin ordering tanpa membebani RAM compute.
- **Range** mengeksekusi scanning boundary di tahap akhir.

Pencegahan memory thrashing, eliminasi write amplification akibat over-indexing, pemanfaatan Partial/Covered Indexes, serta penerapan protokol rolling deployment saat index creation adalah standar profesional mutlak dalam mengoperasikan basis data MongoDB berkeandalan tinggi di lingkungan produksi.