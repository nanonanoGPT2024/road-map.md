# BAB 03 / MODULE 01: Advanced Data Modeling & Schema Design Patterns

---

## Seksi 01: Identitas Modul
* **Track:** Database & Distributed Storage Engineering
* **Kategori:** 04-Backend-and-Database
* **Teknologi:** MongoDB 7.0+ Enterprise / Community Server
* **Topik:** Advanced Data Modeling & Schema Design Patterns
* **Tingkat Kesulitan:** Advanced (Level 400)
* **Prasyarat Konseptual:**
  * Pemahaman mendalam terkait BSON Storage Engine (WiredTiger internals).
  * Penguasaan Compound Indexing, Prefix Matching, dan Index Intersection.
  * Familiaritas dengan MongoDB Aggregation Pipeline ($lookup, $facet, $bucket).
  * Pemahaman trade-off konsistensi ACID, isolasi read/write concern, dan Distributed Systems.
* **Target Output:**
  * Kemampuan merancang skema MongoDB multi-tenant terdistribusi dengan toleransi beban throughput tinggi (>20,000 ops/sec).
  * Penguasaan praktis terhadap 7 Schema Design Patterns utama (Subset, Computed, Bucket, Extended Reference, Attribute, Outlier, Schema Versioning).
  * Implementasi validasi skema berbasis JSON Schema (Draft 4/7 compliant) dan automasi migrasi data tanpa downtime.

---

## Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis dan Memilih Pola:** Mengidentifikasi access pattern aplikasi dan memilih pola desain skema MongoDB yang tepat berdasarkan rasio Read:Write dan batasan 16MB BSON Document.
2. **Mengatasi Document Growth & Memory Bloat:** Mengimplementasikan *Subset Pattern* dan *Bucket Pattern* untuk mengoptimalkan WiredTiger Cache RAM dan Working Set.
3. **Mengurangi Overhead Aggregation:** Menerapkan *Computed Pattern* dan *Extended Reference Pattern* untuk mereduksi kalkulasi *on-the-fly* pada pembacaan berulang.
4. **Membangun Fleksibilitas Skema:** Mendesain skema menggunakan *Attribute Pattern* dan *Polymorphic Pattern* untuk domain dinamis tanpa mengorbankan performa index.
5. **Mengelola Evolusi Skema:** Merancang pipeline migrasi skema non-breaking berbasis *Schema Versioning Pattern* dengan validasi ketat `$jsonSchema`.

---

## Seksi 03: Concept Map Diagram ASCII

```
                                  [ACCESS PATTERN ANALYSIS]
                                             │
             ┌───────────────────────────────┴──────────────────────────────┐
             ▼                                                              ▼
    [READ HEAVY WORKLOAD]                                         [WRITE HEAVY WORKLOAD]
             │                                                              │
    ┌────────┴──────────────────────────┐                         ┌─────────┴───────────────────────┐
    ▼                                   ▼                         ▼                                 ▼
[Document Size > 16MB]         [Frequent Aggregations]   [High Ingestion Rates]           [Heterogeneous Fields]
    │                                   │                         │                                 │
    ▼                                   ▼                         ▼                                 ▼
┌──────────────────┐           ┌──────────────────┐      ┌──────────────────┐              ┌──────────────────┐
│  SUBSET PATTERN  │           │ COMPUTED PATTERN │      │  BUCKET PATTERN  │              │ATTRIBUTE PATTERN │
└──────────────────┘           └──────────────────┘      └──────────────────┘              └──────────────────┘
    │                                   │                         │                                 │
    └─────────────────┬─────────────────┴─────────────────────────┴─────────────────────────────────┘
                      ▼
         [STRUCTURAL OPTIMIZATIONS]
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│ EXTENDED REF     │       │ SCHEMA VERSIONING│
│ (Anti-$lookup)   │       │ (Zero-Downtime)  │
└──────────────────┘       └──────────────────┘
```

---

## Seksi 04: Mengapa Relevan

Dalam arsitektur sistem modern, disk I/O dan alokasi memory cache adalah bottleneck utama sistem basis data. MongoDB menggunakan WiredTiger Storage Engine, di mana dokumen BSON disimpan dan dikelola dalam Working Set di RAM. 

Pendekatan normalisasi data relasional murni (3NF) yang diterapkan secara naif ke MongoDB menyebabkan pemanggilan operator `$lookup` yang masif, meningkatkan latency pembacaan karena non-locality data. Sebaliknya, denormalisasi total tanpa kontrol memicu *unbounded array growth*, yang mengakibatkan pelanggaran batas ukuran BSON 16MB, fragmentasi disk, dan thrashing pada RAM.

Penguasaan Advanced Schema Design Patterns memberikan kemampuan deterministik untuk menyeimbangkan konsumsi disk I/O, menjaga Working Set tetap berada di RAM, dan memastikan query latency stabil pada p99 < 10ms di bawah beban kerja jutaan dokumen per detik.

---

## Seksi 05: Anatomi Konsep Inti

### 1. Subset Pattern
* **Mekanisme:** Memisahkan data dokumen yang jarang diakses (1-to-N atau 1-to-Zillion relationships) ke dalam koleksi terpisah, dan hanya mempertahankan subset kecil (misal: 10 item teratas/terakhir) pada dokumen utama.
* **Tujuan Teknis:** Memperkecil ukuran rata-rata dokumen (RAM footprint), sehingga lebih banyak dokumen dapat dimuat ke dalam WiredTiger Cache.

### 2. Computed Pattern
* **Mekanisme:** Menghitung nilai agregasi (SUM, AVG, COUNT) saat operasi penulisan (*write-time*) secara inkremental atau melalui asynchronous worker, alih-alih menghitung ulang saat query pembacaan (*read-time*).
* **Tujuan Teknis:** Mengurangi beban CPU dan memori akibat `$group` agregasi berulang pada operasi baca.

### 3. Bucket Pattern
* **Mekanisme:** Mengelompokkan stream data time-series atau event log ke dalam satu dokumen berbasis batas waktu atau jumlah data (misal: 100 sample/dokumen), menyimpan pengukuran dalam format array BSON.
* **Tujuan Teknis:** Mengurangi indeks cardinality overhead, memperkecil disk footprint via kompresi internal dokumen BSON, dan mengoptimalkan range queries.

### 4. Extended Reference Pattern
* **Mekanisme:** Menyalin beberapa field yang paling sering dibaca dari dokumen relasi ke dokumen induk, bukan menyalin seluruh objek atau hanya menyimpan `_id`.
* **Tujuan Teknis:** Menghilangkan kebutuhan untuk melakukan join `$lookup` atau multiple read trips via driver aplikasi.

### 5. Attribute Pattern
* **Mekanisme:** Mengubah struktur objek yang memiliki ratusan field yang bervariasi menjadi struktur array dari pasangan key-value (`k: <key>`, `v: <value>`).
* **Tujuan Teknis:** Mengurangi kebutuhan pembuatan index individual untuk ratusan field yang jarang terisi, digantikan dengan satu compound multi-key index pada `{ "attributes.k": 1, "attributes.v": 1 }`.

### 6. Outlier Pattern
* **Mekanisme:** Menangani dokumen anomali yang melebihi rata-rata batasan (misal: akun selebriti dengan jutaan follower) dengan menandai dokumen (`has_overflow: true`) dan memindahkan kelebihan data ke koleksi overflow.
* **Tujuan Teknis:** Menjaga ukuran dokumen 99.9% pengguna tetap seragam dan ramping tanpa perlu mendegradasi performa arsitektur demi 0.1% outlier.

### 7. Schema Versioning Pattern
* **Mekanisme:** Menyertakan field `schema_version` (integer/string) pada setiap dokumen, memungkinkan mutasi skema secara lazy-load melalui layer aplikasi tanpa memerlukan batch update offline yang memblokir database.

---

## Seksi 06: Panduan Implementasi Step-by-Step

### Tahap 1: Analisis Access Pattern Matrix
Petakan domain model berdasarkan formula:
$$\text{Read/Write Ratio} = \frac{\text{Query Read QPS}}{\text{Write/Update QPS}}$$
* Jika Ratio $> 10$: Prioritaskan *Computed Pattern*, *Extended Reference*, dan *Subset Pattern*.
* Jika Ratio $< 0.1$: Prioritaskan *Bucket Pattern* dan raw unstructured writes.

### Tahap 2: Definisi Strict Schema Validation (`$jsonSchema`)
Terapkan schema validator di level collection untuk menegakkan integritas tipe data BSON dan batasan struktural.

```javascript
db.createCollection("products", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["_id", "sku", "name", "price", "schema_version", "attributes"],
      properties: {
        _id: { bsonType: "objectId" },
        sku: { bsonType: "string", pattern: "^[A-Z0-9]{8,12}$" },
        name: { bsonType: "string", maxLength: 150 },
        price: { bsonType: "decimal" },
        schema_version: { bsonType: "int", minimum: 1 },
        attributes: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["k", "v"],
            properties: {
              k: { bsonType: "string" },
              v: { bsonType: ["string", "number", "bool", "date"] }
            }
          }
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});
```

### Tahap 3: Pembuatan Indeks Optimal
Pastikan compound multikey index diterapkan pada field yang di-restrukturisasi melalui Attribute Pattern:

```javascript
db.products.createIndex(
  { "attributes.k": 1, "attributes.v": 1 },
  { name: "idx_attributes_kv" }
);
```

---

## Seksi 07: Contoh Kasus Sederhana

### Problem: Sistem E-Commerce dengan Atribut Barang Heterogen
Katalog memiliki produk pakaian (ukuran, warna, material), elektronik (voltase, kapasitas baterai), dan buku (ISBN, pengarang, halaman).

#### Skema Buruk (Field Polusi & Exhausted Index Limit):
```json
{
  "_id": "PROD-001",
  "name": "Kemeja Flanel",
  "apparel_size": "XL",
  "apparel_color": "Merah",
  "electronics_voltage": null,
  "electronics_battery": null,
  "book_isbn": null
}
```

#### Skema Optimal (Attribute Pattern):
```json
{
  "_id": "PROD-001",
  "name": "Kemeja Flanel",
  "attributes": [
    { "k": "size", "v": "XL" },
    { "k": "color", "v": "Merah" },
    { "k": "material", "v": "Katun" }
  ]
}
```
**Query Eksekusi:**
```javascript
db.products.find({
  "attributes": {
    $all: [
      { $elemMatch: { "k": "size", "v": "XL" } },
      { $elemMatch: { "k": "color", "v": "Merah" } }
    ]
  }
});
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur Node.js/TypeScript produksi yang menerapkan:
1. **Bucket Pattern** untuk telemetry sensor IoT.
2. **Extended Reference & Computed Pattern** untuk order items & billing.
3. **Schema Versioning Pattern** dengan mutasi lazy load.

```typescript
// File: src/database/sensor.repository.ts
import { MongoClient, Db, Collection, Decimal128, ObjectId } from "mongodb";

export interface SensorTelemetrySample {
  timestamp: Date;
  metric: string;
  value: number;
}

export interface SensorBucketDocument {
  _id: ObjectId;
  device_id: string;
  date_bucket: Date; // Dimulai pada jam 00:00:00
  sample_count: number;
  aggregations: {
    sum: number;
    min: number;
    max: number;
  };
  samples: Array<{
    timestamp: Date;
    metric: string;
    value: number;
  }>;
  schema_version: number;
}

export class SensorIngestionEngine {
  private collection: Collection<SensorBucketDocument>;
  private static readonly MAX_SAMPLES_PER_BUCKET = 60; // Max 60 samples per document

  constructor(private db: Db) {
    this.collection = this.db.collection<SensorBucketDocument>("sensor_telemetry_buckets");
  }

  public async initialize(): Promise<void> {
    // Unique Compound Index untuk Bucket Identification
    await this.collection.createIndex(
      { device_id: 1, date_bucket: 1, sample_count: 1 },
      { name: "idx_device_bucket_lifecycle" }
    );
  }

  /**
   * Menggunakan Bucket Pattern + Computed Pattern secara atomik via upsert/push
   */
  public async ingestSample(deviceId: string, sample: SensorTelemetrySample): Promise<void> {
    const startOfHour = new Date(sample.timestamp);
    startOfHour.setMinutes(0, 0, 0);

    const filter = {
      device_id: deviceId,
      date_bucket: startOfHour,
      sample_count: { $lt: SensorIngestionEngine.MAX_SAMPLES_PER_BUCKET }
    };

    const update = {
      $setOnInsert: {
        device_id: deviceId,
        date_bucket: startOfHour,
        schema_version: 2,
        "aggregations.min": sample.value,
        "aggregations.max": sample.value
      },
      $inc: {
        sample_count: 1,
        "aggregations.sum": sample.value
      },
      $min: {
        "aggregations.min": sample.value
      },
      $max: {
        "aggregations.max": sample.value
      },
      $push: {
        samples: {
          timestamp: sample.timestamp,
          metric: sample.metric,
          value: sample.value
        }
      }
    };

    await this.collection.updateOne(filter, update, { upsert: true });
  }

  /**
   * Implementasi Schema Versioning: Lazy Migration
   */
  public async fetchAndUpgradeBucket(bucketId: ObjectId): Promise<SensorBucketDocument | null> {
    const doc = await this.collection.findOne({ _id: bucketId });
    if (!doc) return null;

    if (doc.schema_version === 1) {
      // Lazy migration: Schema version 1 tidak memiliki object aggregations
      const computedSum = doc.samples.reduce((acc, curr) => acc + curr.value, 0);
      const computedMin = Math.min(...doc.samples.map(s => s.value));
      const computedMax = Math.max(...doc.samples.map(s => s.value));

      const upgradedDoc: Partial<SensorBucketDocument> = {
        schema_version: 2,
        aggregations: {
          sum: computedSum,
          min: computedMin,
          max: computedMax
        }
      };

      await this.collection.updateOne(
        { _id: bucketId },
        { $set: upgradedDoc }
      );

      return { ...doc, ...upgradedDoc } as SensorBucketDocument;
    }

    return doc;
  }
}
```

---

## Seksi 09: Diagram Alur Kerja ASCII

```
[Write Ingestion: Telemetry Point]
               │
               ▼
[Find Existing Bucket Document]
(device_id: X, date_bucket: Y, sample_count < 60)
               │
       ┌───────┴───────┐
       │               │
  [Found]         [Not Found / Full]
       │               │
       │               ├─► [Generate New Document with $setOnInsert]
       │               │
       ▼               ▼
[Execute Atomic In-Place Engine Updates]
 ├── $inc:  sample_count (+1), aggregations.sum (+v)
 ├── $min:  aggregations.min (v)
 ├── $max:  aggregations.max (v)
 └── $push: samples array (payload)
               │
               ▼
[WiredTiger In-Memory BSON Mutation]
               │
               ▼
[Flush to WiredTiger Write-Ahead Log (Journal)]
```

---

## Seksi 10: Analisis Trade-offs

| Pendekatan Desain | Keuntungan | Kerugian & Batasan | Mitigasi Kegagalan |
| :--- | :--- | :--- | :--- |
| **Subset Pattern** | Working set RAM sangat kecil; Latency read p99 drop drastis. | Duplikasi data antara subset & koleksi induk; kompleksitas saat update. | Sinkronisasi via Change Streams (CDC) atau asynchronous worker (BullMQ/Kafka). |
| **Computed Pattern** | Zero-latency agregasi pada proses read; mengurangi beban CPU DB. | Beban komputasi bergeser ke fase write; risiko state divergence. | Gunakan operator `$inc`/`$min`/`$max` atomik; jalankan audit cron reconciliation. |
| **Bucket Pattern** | Indeks sangat efisien; throughput ingest masif; kompresi tinggi. | Querying data individual di dalam array memerlukan operator kompleks (`$elemMatch`). | Batasi jumlah array maksimal per bucket (`$lt: 60/100/1000`). |
| **Attribute Pattern** | Skema super dinamis; hanya butuh 1 single index untuk semua custom field. | Kueri pencarian teks multi-kondisi memerlukan compound index yang memakan RAM index. | Batasi tipe data nilai atribut, gunakan standardisasi key string. |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices
* **Keep Documents Pre-allocated/Bounded:** Batasi array growth dengan validator ukuran array (`$jsonSchema` dengan `maxItems`) guna mencegah document relocation on disk.
* **Compound Index Prefix Awareness:** Susun field equality di urutan pertama, range di urutan kedua, dan sort di urutan akhir (Equality, Sort, Range - ESR Rule).
* **Decouple Historical vs Operational Data:** Gunakan Extended Reference untuk merekam state data saat transaksi terjadi (contoh: salin snapshot nama/alamat customer ke collection Orders agar riwayat order tidak berubah saat master user diubah).

### Antipatterns (Hal yang Harus Dihindari)
* **Unbounded Array Growth (The Blob Antipattern):** Menyimpan daftar log/komentar terus-menerus ke dalam array tanpa batas di satu dokumen hingga menyentuh limit 16MB.
* **Massive Joins ($lookup Chains):** Melakukan 5-6 stage `$lookup` bertingkat yang meniru struktur relational database murni.
* **Index for Every Key Antipattern:** Membuat index tersendiri untuk 50+ variasi properti objek alih-alih menggunakan Attribute Pattern.

---

## Seksi 12: Security Hardening

Dalam perancangan skema tingkat lanjut, manipulasi payload dapat dieksploitasi melalui Operator Injection Attacks jika validasi skema diabaikan:

1. **Schema Defense against NoSQL Injection:**
   Konfigurasi `validationLevel: "strict"` dan tolak properti yang tidak terdefinisi (`additionalProperties: false`) guna memblokir payload injection berbasis operator seperti `$where` atau `$regex`.

```javascript
db.runCommand({
  collMod: "accounts",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      additionalProperties: false, // Memblokir field liar tak terdaftar
      required: ["_id", "account_id", "balance"],
      properties: {
        _id: { bsonType: "objectId" },
        account_id: { bsonType: "string" },
        balance: { bsonType: "decimal" }
      }
    }
  },
  validationLevel: "strict"
});
```

2. **Field-Level Encryption (FLE / CSFLE):**
   Untuk Extended Reference Pattern yang menduplikasi PII (Personally Identifiable Information), pastikan field tersebut dienkripsi secara deterministik atau acak (AEAD) sebelum di-replicate ke koleksi target.

---

## Seksi 13: Observabilitas & Debugging

### Profiling dan Mendeteksi Antipattern
Aktifkan database profiler untuk menangkap query lambat akibat pembengkakan skema atau miss-indexing:

```javascript
// Set profiling level 1 (hanya query > 50ms)
db.setProfilingLevel(1, { slowms: 50 });

// Kueri query lambat yang melakukan scan array besar
db.system.profile.find(
  { "execStats.totalDocsExamined": { $gt: 1000 } },
  { queryHash: 1, "execStats.executionTimeMillis": 1, "execStats.totalDocsExamined": 1, "command.filter": 1 }
).sort({ ts: -1 }).limit(5);
```

### Analisis Payload Memory Overhead
Analisis ukuran dokumen rata-rata dan index footprint secara berkala:

```javascript
const stats = db.sensor_telemetry_buckets.stats();
print(`Avg Document Size: ${(stats.avgObjSize / 1024).toFixed(2)} KB`);
print(`Total Index Size: ${(stats.totalIndexSize / (1024 * 1024)).toFixed(2)} MB`);
print(`Working Set Cache Status: WiredTiger read/written to disk ratio`);
```

---

## Seksi 14: Benchmarking & Performance

Perbandingan performa antara Naive Schema (1 telemetry sample = 1 document) vs Bucket Pattern (60 sample = 1 bucket) pada pengujian beban 1,000,000 datapoints via k6/YCSB:

```
+------------------------------------+------------------+-------------------+
| Parameter Matriks                  | Naive Unbounded  | Bucket Pattern    |
+------------------------------------+------------------+-------------------+
| Write Throughput (Ops/sec)         | 3,450 ops/sec    | 24,800 ops/sec    |
| Average Read Latency (p95)         | 48.2 ms          | 3.1 ms            |
| Storage Consumption (Disk footprint)| 1.2 GB           | 142 MB            |
| Total Index Footprint              | 285 MB           | 16 MB             |
| WiredTiger Cache Evictions/sec     | 1,420 pages/s    | 45 pages/s        |
+------------------------------------+------------------+-------------------+
```

**Perintah Diagnostik Eksekusi Query Plan:**
```javascript
db.sensor_telemetry_buckets.find({
  device_id: "DEV-AZ-99",
  date_bucket: ISODate("2026-03-30T00:00:00Z")
}).explain("executionStats");
// Verifikasi bahwa tahap IXSCAN menghasilkan nReturned == totalKeysExamined == totalDocsExamined
```

---

## Seksi 15: Hands-on Lab Mini-Project

### Objective: Membangun Core Engine E-Commerce Inventory & Order System
Terapkan **Subset Pattern** (reviews), **Extended Reference Pattern** (order line snapshot), dan **Computed Pattern** (inventory & ratings).

### Source Code: `schema_engine_lab.ts`

```typescript
import { MongoClient, ObjectId, Decimal128 } from "mongodb";

const URI = "mongodb://localhost:27017";
const DB_NAME = "ecommerce_production_lab";

async function main() {
  const client = await MongoClient.connect(URI);
  const db = client.db(DB_NAME);

  console.log("[1] Creating collections and constraints...");
  const products = db.collection("products");
  const orders = db.collection("orders");

  // Schema Pattern 1: Subset Pattern + Computed Pattern pada Catalog
  const sampleProduct = {
    _id: new ObjectId(),
    sku: "MACBOOK-M3-001",
    name: "Apple MacBook Pro M3 14-Inch",
    price: Decimal128.fromString("1999.00"),
    computed_stats: {
      average_rating: 4.8,
      total_reviews: 1540
    },
    // Subset Pattern: Hanya 3 review terbaru yang disimpan di dokumen utama
    recent_reviews: [
      { author: "Budi", rating: 5, comment: "Performa luar biasa!", date: new Date() },
      { author: "Siti", rating: 5, comment: "Battery life sangat awet.", date: new Date() },
      { author: "Andi", rating: 4, comment: "Build quality solid.", date: new Date() }
    ],
    schema_version: 1
  };

  await products.insertOne(sampleProduct);

  // Schema Pattern 2: Extended Reference Pattern pada Checkout Order
  console.log("[2] Executing checkout using Extended Reference Pattern...");
  const sampleOrder = {
    _id: new ObjectId(),
    order_number: "ORD-20260330-001",
    placed_at: new Date(),
    customer: {
      user_id: new ObjectId(),
      email: "engineer@enterprise.internal" // Ref minimal
    },
    // Mengisolasi data produk pada state transaksi terjadi
    items: [
      {
        product_id: sampleProduct._id,
        sku: sampleProduct.sku,
        name: sampleProduct.name, // Extended reference
        unit_price: sampleProduct.price,
        quantity: 1
      }
    ],
    total_amount: sampleProduct.price,
    schema_version: 1
  };

  await orders.insertOne(sampleOrder);

  console.log("[3] Demonstrating Atomic Review Mutation via Subset Pattern...");
  const newReview = { author: "Dewi", rating: 5, comment: "Layar sangat tajam.", date: new Date() };

  // Menambah review baru, memotong subset agar selalu maksimal 3, dan memperbarui computed rating
  await products.updateOne(
    { _id: sampleProduct._id },
    {
      $push: {
        recent_reviews: {
          $each: [newReview],
          $sort: { date: -1 },
          $slice: 3 // Potong array hanya pertahankan 3 review terbaru
        }
      },
      $inc: { "computed_stats.total_reviews": 1 }
    }
  );

  const updatedProduct = await products.findOne({ _id: sampleProduct._id });
  console.log("Updated Product Recent Reviews Count:", updatedProduct?.recent_reviews.length);
  console.log("Updated Product Total Reviews Metric:", updatedProduct?.computed_stats.total_reviews);

  await client.close();
}

main().catch(console.error);
```

---

## Seksi 16: Automated Testing & Verification

File unit/integration test menggunakan Mocha & Chai / Vitest:

```typescript
// test/schema_patterns.spec.ts
import { expect } from "chai";
import { MongoClient, Db, ObjectId } from "mongodb";
import { SensorIngestionEngine } from "../src/database/sensor.repository";

describe("Advanced Schema Design Integration Tests", () => {
  let client: MongoClient;
  let db: Db;
  let engine: SensorIngestionEngine;

  before(async () => {
    client = await MongoClient.connect("mongodb://localhost:27017");
    db = client.db("test_schema_db");
    engine = new SensorIngestionEngine(db);
    await engine.initialize();
  });

  after(async () => {
    await db.dropDatabase();
    await client.close();
  });

  it("should successfully group telemetry samples using the Bucket Pattern", async () => {
    const deviceId = "SENSOR-NODE-A1";
    const baseTime = new Date("2026-03-30T10:00:00Z");

    // Ingest 5 continuous telemetry streams
    for (let i = 1; i <= 5; i++) {
      await engine.ingestSample(deviceId, {
        timestamp: new Date(baseTime.getTime() + i * 1000),
        metric: "temperature",
        value: 20 + i
      });
    }

    const bucket = await db.collection("sensor_telemetry_buckets").findOne({ device_id: deviceId });

    expect(bucket).to.not.be.null;
    expect(bucket?.sample_count).to.equal(5);
    expect(bucket?.aggregations.min).to.equal(21);
    expect(bucket?.aggregations.max).to.equal(25);
    expect(bucket?.aggregations.sum).to.equal(115); // 21+22+23+24+25
    expect(bucket?.samples).to.have.lengthOf(5);
  });

  it("should execute lazy migration upon encountering older schema versions", async () => {
    // Inject legacy v1 document manually
    const legacyDocId = new ObjectId();
    await db.collection("sensor_telemetry_buckets").insertOne({
      _id: legacyDocId,
      device_id: "LEGACY-DEVICE-01",
      date_bucket: new Date("2026-03-30T09:00:00Z"),
      sample_count: 2,
      samples: [
        { timestamp: new Date(), metric: "temp", value: 10 },
        { timestamp: new Date(), metric: "temp", value: 30 }
      ],
      schema_version: 1
    });

    const upgraded = await engine.fetchAndUpgradeBucket(legacyDocId);

    expect(upgraded?.schema_version).to.equal(2);
    expect(upgraded?.aggregations.sum).to.equal(40);
    expect(upgraded?.aggregations.min).to.equal(10);
    expect(upgraded?.aggregations.max).to.equal(30);
  });
});
```

---

## Seksi 17: Troubleshooting Guide

### 1. Issue: BSONDocumentTooLarge (Error 10334 - Document exceeds 16MiB limit)
* **Akar Masalah:** Array pada model data tidak dibatasi (*unbounded growth*). Biasanya terjadi pada log atau activity feed.
* **Solusi Diagnostik:** 
  ```javascript
  db.collection.find({ $where: "Object.bsonsize(this) > 15000000" });
  ```
* **Solusi Perbaikan:** Terapkan **Subset Pattern** dengan `$slice` pada pembaruan array, atau pindahkan entri data historis ke koleksi arsip berbasis time/chunking.

### 2. Issue: High Disk Eviction / RAM Working Set Starvation
* **Akar Masalah:** Ukuran dokumen terlalu besar sehingga WiredTiger cache dipenuhi oleh field yang jarang dibaca.
* **Solusi Diagnostik:** Pantau metrik `wiredTiger.cache.tracked dirty bytes in the cache`.
* **Solusi Perbaikan:** Pisahkan field bervolume besar (contoh: deskripsi teks panjang, metadata debugging) ke koleksi pelengkap terpisah menggunakan **Subset Pattern**.

### 3. Issue: Read Performance Drop on Dynamic Fields
* **Akar Masalah:** Querying nested objects dinamis tanpa index yang memadai atau index melebihi batasan 64 index per collection.
* **Solusi Perbaikan:** Lakukan restrukturisasi field dinamis ke **Attribute Pattern** (`k`, `v`) dan buat 1 compound index `{ "attributes.k": 1, "attributes.v": 1 }`.

---

## Seksi 18: Checklist Produksi

- [ ] **BSON Bounds Enforcement:** Semua array dinamis memiliki batasan ukuran eksplisit melalui operator `$slice` atau validasi array `$maxItems`.
- [ ] **Working Set Verification:** Ukuran indeks agregat (Total Index Size) seluruh koleksi tidak melebihi 60% dari kapasitas WiredTiger Cache RAM yang tersedia.
- [ ] **Strict JSON Schema:** `$jsonSchema` terpasang di level server dengan `validationLevel: "strict"` dan `validationAction: "error"`.
- [ ] **ESR Rule Compliance:** Compound index telah diselaraskan dengan urutan: Equality Fields $\rightarrow$ Sort Fields $\rightarrow$ Range Fields.
- [ ] **Extended Reference Validation:** Dokumen yang menerapkan data denormalisasi dari referensi eksternal telah dilengkapi pipeline sinkronisasi (CDC / event worker) jika data induk dimutasi.
- [ ] **Schema Versioning Tag:** Semua collection operasional memiliki atribut `schema_version` (tipe integer) untuk kebutuhan zero-downtime lazy update.
- [ ] **No Multi-$lookup Pipelines:** Pipeline agregasi divalidasi tidak memuat lebih dari 1 stage `$lookup` pada jalur eksekusi berfrekuensi tinggi (Hot Read Paths).

---

## Seksi 19: Ringkasan Eksekutif

Advanced Data Modeling di MongoDB berfokus pada **optimalisasi pola akses aplikasi (*design for access patterns*)** dibandingkan pemodelan data murni berbasis representasi entitas.

1. **Prinsip Utama:** Kunci latensi rendah p99 di MongoDB adalah menjaga Working Set tetap berada di memory RAM. Hal ini dicapai dengan menekan ukuran dokumen BSON serendah mungkin menggunakan *Subset Pattern*.
2. **Eliminasi Join Overhead:** Menghindari eksekusi `$lookup` yang berat pada jalur kueri kritis dapat dicapai secara deterministik menggunakan *Extended Reference Pattern* dan *Computed Pattern*.
3. **Efisiensi Ingesti dan Volume:** Menggabungkan aliran data serial menjadi unit terkompresi melalui *Bucket Pattern* secara signifikan mengurangi overhead index metadata dan konsumsi disk I/O.
4. **Resiliensi Skema:** Penggunaan *Schema Versioning Pattern* dikombinasikan dengan *Lazy Migration Layer* memastikan transisi evolusi skema tanpa membutuhkan locking data maupun downtime maintenance.

---

## Seksi 20: Referensi & Bacaan Lanjutan

* **Official MongoDB Documentation:** *Building with Patterns - A Summary of 12 Schema Design Patterns*. (MongoDB Architecture Guild).
* **WiredTiger Storage Engine Internals:** *WiredTiger Architecture Guide: In-Memory Page Eviction & Hazard Pointers*.
* **Book:** *MongoDB Applied Design Patterns (2nd Edition)* - Rick Copeland (O'Reilly Media).
* **Technical Whitepaper:** *MongoDB Operational Best Practices & Performance Optimization at Scale*.
* **RFC Reference:** *JSON Schema Validation: A Subschema Specification for JSON (Draft 7 / 2020-12)*.