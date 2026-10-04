# Bab 05 Module 01: Indexing Strategies, B-Tree Internals & Query Tuning

---

## 01. Identitas Modul
* **Kurikulum:** Database Architecture & Engineering
* **Kategori:** 04-Backend-and-Database
* **Topik:** MongoDB
* **Kode Modul:** DB-MNG-0501
* **Tingkat Kesulitan:** Advanced / Senior Engineering Level
* **Prasyarat Teknis:** MongoDB CRUD Operations, Storage Engines (WiredTiger Basics), Concurrency & Locking Models, JSON/BSON Data Representation.

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Menganalisis cara kerja internal struktur B-Tree WiredTiger dan alokasinya pada disk/memory cache.
2. Menerapkan metodologi desain indeks tingkat lanjut: Compound Index, Equality-Sort-Range (ESR) Rule, Partial Index, Sparse Index, TTL, dan Multikey Index.
3. Membedah tahapan eksekusi query planner MongoDB menggunakan profiler dan visualisasi `explain("executionStats")`.
4. Mendiagnosis dan mengeliminasi degradasi performa yang diakibatkan oleh *in-memory sorting*, *index intersection overhead*, dan *unbounded multikey indexing*.
5. Merancang serta memelihara indeks pada skala *terabyte* di kluster produksi tanpa memicu *locking contention* atau lonjakan I/O (Input/Output).

---

## 03. Concept Map Diagram (ASCII)

```
========================================================================================
                                 MONGODB INDEXING PIPELINE
========================================================================================

  [ Client Query ] 
         │
         ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ Query Planner & Optimizer                                              │
  │  - Cache Plan Check                                                    │
  │  - Multi-Plan Execution (Candidate Index Scoring)                      │
  │  - Win Plan Selection                                                  │
  └───────────────────┬────────────────────────────────────────────────────┘
                      │
                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ WiredTiger Storage Engine Index Resolution Layer                       │
  │                                                                        │
  │      ┌─────────────────────────┐             ┌──────────────────────┐  │
  │      │ B-Tree Root Page        │             │ WiredTiger Cache     │  │
  │      └────────────┬────────────┘             │ (LRU Eviction / Evict│  │
  │                   │                          │  Server Threads)     │  │
  │         ┌─────────┴─────────┐                └──────────┬───────────┘  │
  │         ▼                   ▼                           │              │
  │   ┌───────────┐       ┌───────────┐                     │ (Fast Hit)   │
  │   │ Int. Page │       │ Int. Page │                     │              │
  │   └─────┬─────┘       └─────┬─────┘                     │              │
  │         │                   │                           │              │
  │   ┌─────┴─────┐       ┌─────┴─────┐                     ▼              │
  │   ▼           ▼       ▼           ▼            ┌─────────────────┐     │
  │ [Leaf]      [Leaf]  [Leaf]      [Leaf] ◄───────┤ Index Blocks    │     │
  │ (Key:RecordID Index Entries)                   │ (Compressed)    │     │
  └───────────────────┬────────────────────────────┴────────┬────────┴─────┘
                      │ (RecordID Pointer)                  │ (Page Fault)
                      ▼                                     ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ Disk File System (WiredTiger .wt Collection Data Files)                │
  │ [ Block Read: Fetch Document into WiredTiger Cache Buffer ]            │
  └────────────────────────────────────────────────────────────────────────┘
========================================================================================
```

---

## 04. Mengapa Relevan

Tanpa pemahaman indexing yang tepat, query MongoDB akan melakukan **COLLSCAN** (Collection Scan) yang memuat seluruh dokumen dari disk ke WiredTiger Cache. Pada volume jutaan record, operasi ini memicu tingginya page fault, memory thrashing, degradasi throughput sistem, dan latensi query spike (P99 > 5000ms).

Indeks yang tidak terstruktur dengan baik (misalnya melanggar aturan ESR atau memiliki *unindexed sort*) memaksa MongoDB mengeksekusi operasi in-memory sort yang dibatasi plafon 100MB. Jika ambang batas ini terlampaui tanpa proteksi, query akan gagal (`SortExceededMemoryLimitExceededException`). Oleh karena itu, penguasaan B-Tree internals dan strategi indexing adaptif merupakan syarat fundamental untuk menjaga latensi query p99 tetap rendah (misal: `< 10ms`) pada skala volume data masif.

---

## 05. Anatomi Konsep Inti

### 1. WiredTiger B-Tree Internals
WiredTiger mengorganisasikan indeks dalam struktur **B-Tree** (Balanced Tree). Struktur ini terdiri dari:
* **Root Page:** Titik awal traversal.
* **Internal Pages:** Menyimpan boundary keys dan pointer ke halaman anak (*child pages*).
* **Leaf Pages:** Menyimpan pasangan kunci yang diindeks (*index keys*) dan referensi internal ke lokasi data actual berbentuk **RecordID** (posisi 64-bit integer dokumen di dalam file koleksi).

Halaman-halaman B-Tree ini dikompresi (secara default menggunakan Prefix Compression) saat berada di disk. Ketika diakses, halaman didekompresi ke dalam WiredTiger Cache. Index lookup memiliki kompleksitas waktu $\mathcal{O}(\log N)$, berbeda dari scan linier $\mathcal{O}(N)$.

### 2. Equality, Sort, Range (ESR) Rule
Urutan field dalam Compound Index memegang peran krusial terhadap efisiensi eksekusi query. Aturan emas penyusunan indeks gabungan adalah:
1. **[E] Equality:** Letakkan field yang menggunakan exact matching (`$eq`, string/numeric scalar match) di posisi paling kiri (*leading fields*). Hal ini memangkas ruang pencarian B-Tree secara eksponensial.
2. **[S] Sort:** Letakkan field yang digunakan untuk operasi sorting (`sort()`) di posisi berikutnya. Indeks telah tersortir secara natural, sehingga engine langsung membaca dokumen secara berurutan (*index-provided sort*) dan mengeliminasi proses sorting in-memory (`SORT` stage).
3. **[R] Range:** Letakkan field yang menggunakan perbandingan rentang (`$gt`, `$gte`, `$lt`, `$lte`, `$in`) di posisi paling belakang. Sekali evaluasi rentang dieksekusi pada B-Tree, scanning transversal akan menyebar, sehingga field berikutnya tidak bisa dimanfaatkan untuk sorting terarah.

### 3. Covered Query
Sebuah query berstatus **Covered** ketika:
* Semua field dalam filter query terdapat dalam indeks.
* Semua field yang dikembalikan di projection eksplisit (`projection: { field: 1, _id: 0 }`) ada dalam indeks.
* Engine tidak perlu membaca data aktual melalui *RecordID resolution* (`FETCH` stage). Tahap eksekusi hanya terdiri dari `IXSCAN` $\rightarrow$ `PROJECTION_COVERED`.

### 4. Index Types & Constraints
* **Compound Index:** Indeks gabungan beberapa field. Urutan field sangat menentukan fungsionalitas (*Prefix matching rule*).
* **Multikey Index:** Terbentuk saat mengindeks field bertipe `Array`. MongoDB secara otomatis membuat entry indeks terpisah untuk setiap elemen dalam array. 
  * *Batasan:* Sebuah compound multikey index tidak boleh memiliki lebih dari satu field bertipe array untuk mencegah ledakan kombinasi kartesian (*Cartesian product explosive entry count*).
* **Partial Index:** Hanya mengindeks dokumen yang memenuhi ekspresi filter tertentu (`partialFilterExpression`). Menghemat ruang disk dan memori secara signifikan.
* **Sparse Index:** Hanya mengindeks dokumen yang benar-benar memiliki field yang dituju, melewati dokumen yang tidak memiliki field tersebut.
* **TTL (Time To Live) Index:** Indeks pada single field bertipe date dengan parameter `expireAfterSeconds`. Thread background WiredTiger akan menghapus dokumen kadaluwarsa secara berkala (interval ~60 detik).

---

## 06. Panduan Implementasi Step-by-Step

### Fase 1: Identifikasi Lambatnya Query & Review Index yang Tersedia
Periksa query lambat dan tinjau indeks eksisting pada koleksi target.

```javascript
// Hubungkan ke mongosh
use financial_ledger;

// 1. Tinjau indeks yang ada
db.transactions.getIndexes();

// 2. Evaluasi ukuran footprint index di memory/disk
db.transactions.stats().indexSizes;
```

### Fase 2: Analisis Query Execution Plan Mentah
Gunakan explain mode `executionStats` untuk memetakan bottlenecks.

```javascript
db.transactions.find({
  merchantId: "MCH-88231",
  status: "SETTLED",
  createdAt: { 
    $gte: ISODate("2023-01-01T00:00:00Z"), 
    $lte: ISODate("2023-03-31T23:59:59Z") 
  }
}).sort({ amount: -1 }).explain("executionStats");
```
*Identifikasi output:* Jika terdapat tahapan `COLLSCAN` atau `SORT` (in-memory sort), indeks baru mutlak diperlukan.

### Fase 3: Desain dan Konstruksi Indeks Sesuai ESR
Susun indeks dengan format:
- **E (Equality):** `merchantId`, `status`
- **S (Sort):** `amount` (Arah sorting: -1 atau 1)
- **R (Range):** `createdAt`

```javascript
// Pembuatan indeks secara background / non-blocking (MongoDB >= 4.2 otomatis hybrid index build)
db.transactions.createIndex(
  { 
    merchantId: 1, 
    status: 1, 
    amount: -1, 
    createdAt: 1 
  },
  { 
    name: "idx_merchant_status_amount_created",
    background: true 
  }
);
```

### Fase 4: Validasi Performa Pasca-Indeksasi
Jalankan kembali query explain dan amati metrik kunci:

```javascript
const exp = db.transactions.find({
  merchantId: "MCH-88231",
  status: "SETTLED",
  createdAt: { 
    $gte: ISODate("2023-01-01T00:00:00Z"), 
    $lte: ISODate("2023-03-31T23:59:59Z") 
  }
}).sort({ amount: -1 }).explain("executionStats");

print("Execution Time (ms): " + exp.executionStats.executionTimeMillis);
print("Total Keys Examined: " + exp.executionStats.totalKeysExamined);
print("Total Docs Examined: " + exp.executionStats.totalDocsExamined);
print("nReturned: " + exp.executionStats.nReturned);
```

Target rasio efisiensi query ideal:
$$\text{Efficiency Ratio} = \frac{\text{totalDocsExamined}}{\text{nReturned}} \approx 1$$
$$\text{Key Scan Ratio} = \frac{\text{totalKeysExamined}}{\text{nReturned}} \approx 1$$

---

## 07. Contoh Kasus Sederhana: Optimasi In-Memory Sorting E-Commerce

### Skenario
Sebuah marketplace memiliki 2.000.000 dokumen produk. Pengguna mencari produk berkategori `"electronics"`, dengan range harga antara `100` hingga `1000`, diurutkan berdasarkan `rating` tertinggi.

### Model Dokumen
```json
{
  "_id": ObjectId("64f1a2b3c4d5e6f7a8b9c0d1"),
  "category": "electronics",
  "price": 450,
  "rating": 4.8,
  "title": "Noise Cancelling Headphones"
}
```

### Query Tanpa Indeks Optimal
```javascript
// Query
db.products.find({
  category: "electronics",
  price: { $gte: 100, $lte: 1000 }
}).sort({ rating: -1 });
```

### Analisis Problem (Tanpa Indeks)
- Stage: `COLLSCAN` $\rightarrow$ Membaca 2.000.000 dokumen.
- Stage: `SORT` $\rightarrow$ MongoServerError: Executor error during find command :: caused by :: Sort memory limit exceeded (104857600 bytes).

### Solusi Penerapan Aturan ESR
- Equality: `category`
- Sort: `rating`
- Range: `price`

```javascript
// Eksekusi Pembuatan Indeks
db.products.createIndex({ category: 1, rating: -1, price: 1 });

// Hasil verifikasi Explain Plan
// Stage: IXSCAN (idx_category_1_rating_-1_price_1) -> FETCH
// totalKeysExamined: 1500, totalDocsExamined: 1500, nReturned: 1500
// in-memory sort stage dieliminasi sepenuhnya.
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi modul repository production-grade menggunakan **TypeScript** dan **MongoDB Node.js Driver**, yang dilengkapi dengan verifikasi performa runtime, index guard initializer, dan instrumentasi explain plan.

```typescript
// File: src/infrastructure/database/TransactionRepository.ts

import { 
  MongoClient, 
  Db, 
  Collection, 
  Document, 
  CreateIndexesOptions, 
  IndexSpecification,
  ExplainVerbosity
} from 'mongodb';

export interface TransactionDocument {
  _id?: string;
  transactionId: string;
  merchantId: string;
  status: 'PENDING' | 'SETTLED' | 'FAILED' | 'REFUNDED';
  amount: number;
  currency: string;
  paymentMethod: string;
  createdAt: Date;
  metadata?: Record<string, unknown>;
}

export interface QueryFilter {
  merchantId: string;
  status: 'PENDING' | 'SETTLED' | 'FAILED' | 'REFUNDED';
  from: Date;
  to: Date;
  minAmount?: number;
}

export class TransactionRepository {
  private collection: Collection<TransactionDocument>;

  constructor(private readonly db: Db) {
    this.collection = this.db.collection<TransactionDocument>('transactions');
  }

  /**
   * Menginisialisasi indeks koleksi secara idempoten dan terstruktur
   */
  public async ensureIndexes(): Promise<void> {
    const indexes: { spec: IndexSpecification; options: CreateIndexesOptions }[] = [
      // ESR Optimized Compound Index untuk analitik per merchant
      {
        spec: { merchantId: 1, status: 1, amount: -1, createdAt: 1 },
        options: { 
          name: 'idx_esr_merchant_status_amount_created',
          background: true 
        }
      },
      // Unique Sparse Partial Index untuk tracking ID eksternal
      {
        spec: { transactionId: 1 },
        options: { 
          name: 'idx_unique_transaction_id',
          unique: true,
          sparse: true 
        }
      },
      // Partial Index khusus untuk query monitoring status PENDING
      {
        spec: { createdAt: 1 },
        options: {
          name: 'idx_partial_pending_monitoring',
          partialFilterExpression: { status: 'PENDING' }
        }
      }
    ];

    for (const idx of indexes) {
      try {
        await this.collection.createIndex(idx.spec, idx.options);
      } catch (error: any) {
        if (error.codeName === 'IndexOptionsConflict' || error.code === 85) {
          console.warn(`[WARN] Index ${idx.options.name} exists with different options. Review migration path.`);
        } else {
          throw error;
        }
      }
    }
  }

  /**
   * Mengambil data transaksi dengan sorting optimal dan proteksi in-memory sort
   */
  public async getTransactionsForSettlement(
    filter: QueryFilter, 
    limit: number = 50
  ): Promise<TransactionDocument[]> {
    const mongoQuery = {
      merchantId: filter.merchantId,
      status: filter.status,
      createdAt: { 
        $gte: filter.from, 
        $lte: filter.to 
      },
      ...(filter.minAmount ? { amount: { $gte: filter.minAmount } } : {})
    };

    return await this.collection
      .find(mongoQuery)
      .sort({ amount: -1 })
      .limit(limit)
      .toArray();
  }

  /**
   * Menjalankan analisis performa query (Query Profiling Diagnostic)
   */
  public async explainSettlementQuery(
    filter: QueryFilter, 
    limit: number = 50
  ): Promise<Document> {
    const mongoQuery = {
      merchantId: filter.merchantId,
      status: filter.status,
      createdAt: { 
        $gte: filter.from, 
        $lte: filter.to 
      }
    };

    return await this.collection
      .find(mongoQuery)
      .sort({ amount: -1 })
      .limit(limit)
      .explain(ExplainVerbosity.ExecutionStats);
  }
}

// Bootstrap dan Verifikasi Runtime
export async function runVerification(): Promise<void> {
  const uri = process.env.MONGO_URI || 'mongodb://localhost:27017';
  const client = new MongoClient(uri, { maxPoolSize: 20 });

  try {
    await client.connect();
    const db = client.db('payment_gateway_prod');
    const repo = new TransactionRepository(db);

    console.log('Ensuring production indexes...');
    await repo.ensureIndexes();

    console.log('Executing query explain stats verification...');
    const explainPlan = await repo.explainSettlementQuery({
      merchantId: 'MCH-00912',
      status: 'SETTLED',
      from: new Date('2023-01-01T00:00:00Z'),
      to: new Date('2023-12-31T23:59:59Z')
    });

    const executionStats = explainPlan.executionStats;
    console.log('--- Execution Analysis ---');
    console.log(`Execution Time (ms): ${executionStats.executionTimeMillis}`);
    console.log(`Total Keys Examined: ${executionStats.totalKeysExamined}`);
    console.log(`Total Docs Examined: ${executionStats.totalDocsExamined}`);
    console.log(`Returned Docs: ${executionStats.nReturned}`);
    console.log(`Execution Stages: ${JSON.stringify(executionStats.executionStages, null, 2)}`);

  } catch (err) {
    console.error('Fatal Database Operation Error:', err);
  } finally {
    await client.close();
  }
}
```

---

## 09. Diagram Alur Kerja Query Tuning (ASCII)

```
                       [ Incoming Production Query ]
                                     │
                                     ▼
                    [ Run explain("executionStats") ]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
       { stage: "COLLSCAN" }                    { stage: "IXSCAN" }
                 │                                       │
                 ▼                                       ▼
      [ Create Index Base ]               [ Check Sort In-Memory Stage? ]
                 │                               ┌───────┴───────┐
                 │                               ▼               ▼
                 │                          { "SORT" }       No "SORT" Stage
                 │                               │         (Index-Sorted)
                 │                               ▼               │
                 │                     [ Refactor Index Order ]  │
                 │                     [ Apply ESR Guidelines ]  │
                 │                               │               │
                 └───────────────────────┬───────┘               │
                                         │                       │
                                         ▼                       ▼
                            [ Verify Ratio Diagnostics ] ◄───────┘
                            - totalDocsExamined / nReturned ≈ 1
                            - totalKeysExamined / nReturned ≈ 1
                                         │
                        ┌────────────────┴────────────────┐
                        │ Is Target Ratio Met?            │
                        ├────────────────┬────────────────┤
                        ▼ (No)           ▼ (Yes)
           [ Evaluate Partial Index ]   [ Production Index Validated ]
           [ or Covered Query Opt ]     [ Integrate into Migration ]
```

---

## 10. Analisis Trade-offs

| Pendekatan Indexing | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **Banyak Single Field Indexes** | Memberikan fleksibilitas query ad-hoc yang luas. | Overhead write amplification masif; konsumsi RAM WiredTiger sangat tinggi. | *Read-only archival systems* dengan variasi query tak terprediksi. |
| **Comprehensive Compound Indexes (ESR)** | Performa pembacaan optimal ($\mathcal{O}(\log N)$); latensi stabil; zero in-memory sort. | Hanya efektif untuk query yang mematuhi *prefix order*; write footprint meningkat. | Sistem OLTP, Core Ledger, Checkout Transaction Processing. |
| **Partial Indexes** | Menghemat kapasitas disk dan memori; performa tinggi pada subset data aktif. | Query planner mengabaikan indeks jika filter query tidak mencakup `partialFilterExpression`. | Antrean tugas pending, dokumen non-archived, validasi flag spesifik. |
| **Covered Indexes** | Menghilangkan I/O document fetching secara total; performa read ekstrem. | Dokumen projection harus dibatasi ketat; index payload menjadi lebih lebar (larger keys). | High-frequency lookups, auto-complete, endpoint verifikasi otentikasi. |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Adhere to the ESR Rule:** Susun compound index berurutan: Equality $\rightarrow$ Sort $\rightarrow$ Range.
* **Cover High-Traffic Queries:** Buat indeks yang memuat seluruh field yang dibutuhkan agar database terhindar dari `FETCH` stage.
* **Monitor Index Cardinality:** Letakkan field dengan kardinalitas tinggi di posisi awal Equality jika query mengizinkan, guna meminimalkan evaluasi leaf page.
* **Utilize Rolling Index Builds:** Pada environment replika set skala besar, gunakan rolling index build jika perlu membatasi load CPU di Primary node.

### Antipatterns
* **Over-indexing (Index Sprawl):** Memiliki lebih dari 5-8 indeks pada koleksi dengan volume write tinggi. Setiap penulisan (write) memaksa pembaruan B-Tree synchronous untuk setiap index.
* **Unbounded Multikey Indexing:** Mengindeks array yang berisi ratusan atau ribuan sub-dokumen, menyebabkan satu dokumen menghasilkan ribuan entri B-Tree.
* **Regex Lookups Without Anchors:** Query dengan ekspresi reguler non-prefix (`/.*pattern.*/`) tidak dapat memanfaatkan B-Tree traversal secara efisien, menghasilkan index scan menyeluruh (`IXSCAN` full scan). Gunakan prefix regex (`/^pattern/`).
* **Inconsistent Index Directions in Multi-Field Sorting:** Mengindeks `{ a: 1, b: 1 }` tetapi mengeksekusi sorting `{ a: 1, b: -1 }`. Arah index wajib simetris (`{ a: 1, b: 1 }` melayani sort `{ a: 1, b: 1 }` atau `{ a: -1, b: -1 }`).

---

## 12. Security Hardening & Isolation

1. **RBAC Index Administration:** Batasi hak akses pembuatan indeks di produksi. Pengguna aplikasi reguler tidak boleh memiliki role `dbAdmin` atau `clusterAdmin`.
   ```javascript
   // Role khusus untuk App Service (Least Privilege)
   use admin;
   db.createRole({
     role: "appWriteReadRestricted",
     privileges: [
       { resource: { db: "financial_ledger", collection: "transactions" }, actions: [ "find", "insert", "update" ] }
     ],
     roles: []
   });
   ```
2. **Encrypted Storage Engine (WiredTiger Encryption at Rest):** Pastikan file indeks `.wt` terenkripsi menggunakan algoritma AES256-CBC/AES256-GCM pada level storage engine agar leak fisik disk tidak membuka isi index key:
   ```yaml
   # mongod.conf
   security:
     enableEncryption: true
     encryptionKeyFile: /etc/mongodb/wt-encryption.key
     cipherMode: AES256-CBC
   ```
3. **Query Injection Defense:** Lakukan validasi skema runtime (menggunakan Zod / Joi) pada backend API untuk mencegah injeksi filter query seperti `{$ne: null}` yang memicu index traversal bypassing.

---

## 13. Observabilitas & Debugging

### 1. Database Profiler Activation
Aktifkan database profiler untuk menangkap operasi yang berjalan melebihi batas toleransi:

```javascript
// Set profiling level 1 (Slow operations only) dengan threshold 50ms
db.setProfilingLevel(1, { slowms: 50 });

// Query profiling log system
db.system.profile.find({ 
  op: "query", 
  ns: "financial_ledger.transactions" 
}).sort({ ts: -1 }).limit(5).pretty();
```

### 2. Membedah Output `explain("executionStats")`
Tahapan-tahapan penting yang perlu diwaspadai dalam execution stages:

* **COLLSCAN:** Pembacaan tabel penuh. Identifikasi apakah indeks hilang.
* **IXSCAN:** Scanning pada leaf B-Tree. Pantau metrik `totalKeysExamined`.
* **FETCH:** Pengambilan dokumen aktual berdasarkan RecordID.
* **SORT:** Operasi in-memory sorting. Indikasi pelanggaran aturan ESR.
* **OR:** Eksekusi union scan. Pastikan setiap cabang query klausa `$or` memiliki indeks pendukung yang relevan.

---

## 14. Benchmarking & Performance Validation

Uji beban indeks sintetis untuk membandingkan eksekusi query unindexed vs ESR-indexed:

```bash
# Benchmark Script menggunakan mtools / custom k6 engine
# Skenario 1: Query tanpa ESR Index (Hanya index pada field Equality)
# Target: 5,000 req/sec

Metrics Target:
- Unindexed: P99 Latency = 1,420ms | CPU Usage = 98% | Cache Eviction Spikes
- ESR Indexed: P99 Latency = 3.2ms | CPU Usage = 14% | Stable Memory Utilization
```

### Script Autopopulate & Benchmark Node.js
```typescript
// Script verifikasi beban lokal
import { MongoClient } from 'mongodb';

async function benchmark() {
  const client = await MongoClient.connect('mongodb://localhost:27017');
  const coll = client.db('perf_test').collection('audit_logs');
  
  console.time('Execution: 50,000 Lookups with ESR Index');
  const promises = [];
  for (let i = 0; i < 50000; i++) {
    promises.push(
      coll.find({ orgId: "ORG_99", severity: "ERROR", timestamp: { $gte: new Date("2023-01-01") } })
          .sort({ timestamp: -1 })
          .limit(10)
          .toArray()
    );
  }
  await Promise.all(promises);
  console.timeEnd('Execution: 50,000 Lookups with ESR Index');
  await client.close();
}
```

---

## 15. Hands-on Lab Mini-Project

### Objektif
Anda diberikan koleksi `flight_reservations` dengan 10.000 dokumen dummy. Anda diminta mengoptimasi query multi-parameter yang mengalami throttling latensi.

### 1. Inisialisasi Data Uji
Salin dan jalankan script ini di `mongosh`:

```javascript
use aviation_db;
db.flight_reservations.drop();

// Seed 10,000 dokumen
const sampleAirlines = ["GA", "SQ", "QZ", "EK"];
const sampleClasses = ["ECONOMY", "BUSINESS", "FIRST"];
const docs = [];

for (let i = 0; i < 10000; i++) {
  docs.push({
    bookingRef: "BK-" + i,
    airline: sampleAirlines[i % sampleAirlines.length],
    cabinClass: sampleClasses[i % sampleClasses.length],
    fare: Math.floor(Math.random() * 5000) + 100,
    bookingDate: new Date(Date.now() - Math.floor(Math.random() * 10000000000)),
    passengers: ["Pax_" + i]
  });
}
db.flight_reservations.insertMany(docs);
```

### 2. Tantangan Query
Optimalkan query pencarian tiket berikut:

```javascript
db.flight_reservations.find({
  airline: "GA",
  cabinClass: "ECONOMY",
  fare: { $gte: 500, $lte: 2500 }
}).sort({ bookingDate: -1 });
```

### 3. Solusi Lab
Terapkan Aturan ESR:
- **E:** `airline`, `cabinClass`
- **S:** `bookingDate` (-1)
- **R:** `fare`

```javascript
// Buat index
db.flight_reservations.createIndex({
  airline: 1,
  cabinClass: 1,
  bookingDate: -1,
  fare: 1
}, { name: "idx_esr_airline_cabin_date_fare" });

// Jalankan verifikasi explain
db.flight_reservations.find({
  airline: "GA",
  cabinClass: "ECONOMY",
  fare: { $gte: 500, $lte: 2500 }
}).sort({ bookingDate: -1 }).explain("executionStats");
```

---

## 16. Automated Testing & Verification

Gunakan framework pengujian (contoh: **Jest** / **Vitest**) untuk memvalidasi bahwa indeks beroperasi sesuai ekspektasi dan tidak ada developer yang membuat query regression yang menyebabkan `COLLSCAN`.

```typescript
// File: test/index_optimization.spec.ts

import { MongoClient, Db } from 'mongodb';

describe('Database Indexing Regression Test Suite', () => {
  let client: MongoClient;
  let db: Db;

  beforeAll(async () => {
    client = await MongoClient.connect(process.env.MONGO_URI || 'mongodb://localhost:27017');
    db = client.db('test_verification_db');
  });

  afterAll(async () => {
    await client.close();
  });

  it('should execute flight queries using IXSCAN without in-memory SORT stage', async () => {
    const coll = db.collection('flight_reservations');

    const explainResult = await coll.find({
      airline: "GA",
      cabinClass: "ECONOMY",
      fare: { $gte: 500, $lte: 2500 }
    })
    .sort({ bookingDate: -1 })
    .explain('executionStats');

    const stats = explainResult.executionStats;
    const stages = stats.executionStages;

    // Pastikan tidak ada in-memory sort stage
    expect(stages.stage).not.toBe('SORT');
    
    // Pastikan query menggunakan stage index scan
    const isIxscanUsed = JSON.stringify(stages).includes('"stage":"IXSCAN"');
    expect(isIxscanUsed).toBe(true);

    // Rasio totalDocsExamined terhadap nReturned harus mendekati 1:1
    const efficiency = stats.totalDocsExamined / (stats.nReturned || 1);
    expect(efficiency).toBeLessThanOrEqual(1.2);
  });
});
```

---

## 17. Troubleshooting Guide

| Gejala / Error String | Akar Masalah (Root Cause) | Langkah Remediasi / Perbaikan |
| :--- | :--- | :--- |
| `Executor error ... Sort memory limit exceeded` | Query melakukan in-memory sort melebihi alokasi 100MB RAM default. | Tambahkan sort key ke dalam compound index sesuai kaidah ESR, atau gunakan projection index matching. |
| `totalKeysExamined` $\gg$ `nReturned` | Range field diletakkan sebelum equality/sort field pada index, atau index memiliki kardinalitas buruk. | Desain ulang susunan compound index: pindahkan field range ke bagian paling kanan index definition. |
| `writeConflicts` tinggi di WiredTiger Engine | Terlalu banyak index aktif pada collection dengan volume write/update tinggi, memicu commit contention. | Audit dan drop index yang tidak digunakan (`db.collection.aggregate([{$indexStats: {}}])`). |
| Index Build memblokir operasional aplikasi | Menjalankan pembuatan index tanpa opsi background pada MongoDB versi lama (< 4.2). | Gunakan MongoDB modern (hybrid build) atau jadwalkan maintenance window melalui rolling index build. |

---

## 18. Checklist Kesiapan Produksi (Production Readiness)

- [ ] Seluruh query analitik dan transaksional core telah divalidasi via `explain("executionStats")`.
- [ ] Aturan ESR (Equality, Sort, Range) diterapkan secara konsisten pada semua Compound Index.
- [ ] Tidak ada query yang memicu tahapan `COLLSCAN` pada koleksi dengan $> 10.000$ dokumen.
- [ ] Ukuran working set index telah dihitung dan dipastikan muat di dalam alokasi WiredTiger RAM Cache (`db.stats().indexSize < RAM Available`).
- [ ] Indeks redundan dan indeks dengan nilai usage 0 (`$indexStats`) telah dieliminasi.
- [ ] Multi-key index dibatasi pada field array yang terikat secara ukuran (bounded arrays).
- [ ] Database Profiling (`slowms`) telah dikonfigurasi untuk menangkap latensi anomali.
- [ ] Automasi integrasi pengujian indexing (Index regression testing) diintegrasikan ke dalam CI/CD pipeline.

---

## 19. Ringkasan Eksekutif

Indexing di MongoDB bukan sekadar menambahkan `createIndex()` pada sembarang field query. Efisiensi sistem database berakar pada pemahaman traversal struktur **B-Tree WiredTiger** dan optimasi alokasi RAM. 

Prinsip **ESR (Equality, Sort, Range)** merupakan metodologi fundamental dalam merancang compound index untuk memastikan eksekusi single-pass index lookup tanpa in-memory sort overhead. Dengan menerapkan validasi terstruktur melalui metrik `explain()`, partial indexing pada dataset sparse, serta pengawasan indeks yang ketat, arsitektur database dapat mempertahankan throughput tinggi, menekan penggunaan CPU, dan menjaga SLA latensi P99 tetap stabil di skala enterprise.

---

## 20. Referensi & Bacaan Lanjutan

1. MongoDB Inc. *WiredTiger Storage Engine Architecture Guide*. MongoDB Documentation.
2. Norberto, K. *MongoDB Applied Design Patterns: Practical Use Cases with the Leading NoSQL Database*. O'Reilly Media.
3. MongoDB Architecture Center. *Indexing Strategies and Query Optimization Reference*.
4. Goetz, B. *Database Indexing and B-Tree Performance Analysis*. ACM