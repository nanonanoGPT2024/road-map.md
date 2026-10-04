# Bab 01 Module 01: Arsitektur Sistem, Model Dokumen BSON, dan Fondasi NoSQL MongoDB

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis (C4)** perbedaan mendasar arsitektur internal MongoDB dengan Relational Database Management Systems (RDBMS), khususnya pada layer penyimpanan (*storage engine*) dan representasi data.
- **Mengurai (C4)** struktur biner BSON (*Binary JSON*), termasuk layout memori, tipe data primitif, dan mekanisme deserialisasi field.
- **Mengimplementasikan (C3)** koneksi *production-grade* ke MongoDB menggunakan driver resmi dengan konfigurasi *connection pooling*, *write concern*, *read concern*, dan skema validasi berbasis *JSON Schema*.
- **Mengevaluasi (C5)** trade-off antara embedding dan referencing dokumen berdasarkan pola akses I/O memori dan karakteristik *eviction* engine WiredTiger.
- **Mendiagnosis (C4)** kegagalan operasional terkait *document growth*, overhead fragmentasi memori, dan limitasi ukuran dokumen 16 MB.

---

### 2. Concept Overview

MongoDB adalah sistem database non-relasional berorientasi dokumen (*document-oriented NoSQL*) yang dirancang untuk mengatasi hambatan skalabilitas horizontal, fleksibilitas skema, dan performa I/O tinggi. Inti dari representasi data MongoDB terletak pada **BSON** (*Binary JSON*), sebuah format serialisasi biner yang memperluas model data JSON dengan tipe data tambahan (seperti `ObjectId`, `Decimal128`, `Date`, dan raw binary data) yang disusun sedemikian rupa agar dapat diproses (*traversed*) secara efisien tanpa harus mem-parse seluruh dokumen ke memori teks.

Secara arsitektur, MongoDB memisahkan layer antarmuka query (*Query Execution & Optimization Layer*) dari layer manipulasi disk fisik melalui **Storage Engine SPI (Service Provider Interface)**. Sejak versi 3.2, storage engine default yang digunakan adalah **WiredTiger**. WiredTiger menyediakan konkurensi tingkat dokumen (*document-level concurrency control* via multi-version concurrency control/MVCC), kompresi data berbasis *prefix* dan algoritma (Snappy, Zstandard), serta manajemen *in-memory cache* adaptif.

```
+-----------------------------------------------------------------------+
|                            Client Application                         |
+-----------------------------------------------------------------------+
                                   | (MongoDB Wire Protocol via TCP/TLS)
                                   v
+-----------------------------------------------------------------------+
|                     mongod (Database Instance)                        |
|  +-----------------------------------------------------------------+  |
|  | Network Layer (Connection Pool, Thread-per-Client / Task-Based)|  |
|  +-----------------------------------------------------------------+  |
|                                  |                                    |
|  +-----------------------------------------------------------------+  |
|  | Query Engine (Parser, Planner, Optimizer, Execution Stage Tree) |  |
|  +-----------------------------------------------------------------+  |
|                                  | (Internal Record Store Interface)  |
|  +-----------------------------------------------------------------+  |
|  | Storage Engine: WiredTiger                                      |  |
|  |  +----------------------+      +-----------------------------+  |  |
|  |  | WiredTiger Cache     |<---->| Eviction Servers            |  |  |
|  |  | (B-Tree Pages, MVCC) |      | (Reconcile dirty pages)     |  |  |
|  |  +----------------------+      +-----------------------------+  |  |
|  |             |                                 |                 |  |
|  |             v (Write-Ahead Logging)           v (Checkpoints)   |  |
|  |     +---------------+                 +---------------+         |  |
|  |     | Journal Files |                 |  Data Files   |         |  |
|  |     +---------------+                 +---------------+         |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

Pondasi komputasi dokumen ini menghilangkan konsep *impedance mismatch*—ketidaksesuaian representasi data antara objek di kode aplikasi (OOP) dengan relasi baris/kolom tabel relasional. Dokumen MongoDB merepresentasikan sebuah entitas lengkap secara agregat.

---

### 3. Business / Real-World Context

Pada sistem terdistribusi modern, data jarang bersifat tabular secara homogen. Ambil contoh sistem **Manajemen Katalog Multi-Kategori E-Commerce**. Sebuah platform e-commerce menjual pakaian, suku cadang otomotif, dan perangkat elektronik.
- Pakaian memiliki atribut: `size`, `color`, `fabric_composition`.
- Suku cadang otomotif memiliki: `vehicle_compatibility_matrix`, `oem_number`, `warranty_terms`.
- Elektronik memiliki: `voltage`, `power_consumption`, `regulatory_certifications`.

Jika model ini dipaksakan ke RDBMS:
1. **Pola Entity-Attribute-Value (EAV):** Menghasilkan *join* kompleks ke tabel atribut hingga puluhan baris per query, merusak performa *read* pada konkurensi tinggi.
2. **Wide Table with Nullable Columns:** Menghasilkan tabel dengan ratusan kolom yang sebagian besar bernilai `NULL`, membuang ruang penyimpanan (meskipun ada sparseness di DB tertentu) dan menyulitkan pemeliharaan integritas skema via migrasi DDL.
3. **Table-per-Type Inheritance:** Membutuhkan multi-table JOIN di setiap query agregat, yang membebani disk IOPS secara masif.

MongoDB menyelesaikan masalah ini melalui penyimpanan dokumen polimorfik. Dokumen produk yang berbeda dapat memiliki struktur field yang bervariasi dalam koleksi yang sama, sementara atribut umum seperti `sku`, `title`, dan `pricing` tetap terindeks secara terpadu. Model agregat ini menyelaraskan partisi data dengan batasan domain bisnis (*Domain-Driven Design Aggregate Root*), meminimalkan distribusi I/O acak pada disk.

---

### 4. Why This Exists & Why It Matters

MongoDB dibangun untuk memecahkan tiga kebuntuan mendasar dari database relasional tradisional:

1. **Object-Relational Impedance Mismatch:** 
   Developer harus menulis translation layer (ORM/ODM) untuk mengubah pohon objek memory (struktur nested/array) menjadi baris-baris datar (*normalized rows*). Operasi baca memerlukan relasional JOIN yang mahal; operasi tulis memerlukan multitable transactions dengan locking overhead.
2. **Kerapuhan Operasional Migrasi Skema (DDL Locks):**
   Pada skala ratusan juta baris, menjalankan `ALTER TABLE ADD COLUMN` pada RDBMS klasik dapat mengunci tabel secara eksklusif atau meningkatkan utilisasi CPU/Disk I/O ke titik kritis. Format dokumen fleksibel MongoDB memungkinkan evolusi skema berbasis aplikasi tanpa *table lock*.
3. **Skalabilitas Horizontal dari Desain Awal (*Scale-Out by Design*):**
   RDBMS dibangun dengan paradigma *vertical scaling* (mesin tunggal dengan CPU/RAM besar). Replikasi sharding di MongoDB diintegrasikan secara natif ke dalam arsitektur sistem (via router `mongos` dan cluster metadata `config server`), bukan sebagai solusi tambahan (*add-on*).

---

### 5. What It Is & What It Is NOT

| Karakteristik | MongoDB (Document Store) | RDBMS (PostgreSQL / MySQL) | Key-Value (Redis) |
|---|---|---|---|
| **Struktur Data** | BSON (Hierarkis / Dokumen) | Baris & Kolom (Tabel Relasional) | Unstructured Blob / Strings / Primitive |
| **Akses Data** | MQL (Rich Ad-hoc Query, Aggregation) | SQL (Relational Algebra) | Key lookup, Hash scanning |
| **Normalisasi Data** | Denormalisasi & Agregasi diutamakan | Normalisasi (3NF / BCNF) diutamakan | Tergantung pola key hashing |
| **Integritas Relasi**| Manual / Skema Aplikasi / `$lookup` | Foreign Key Constraints (Enforced Engine) | Tidak ada |
| **Skalabilitas** | Horisontal natif via Sharding | Vertikal (Read replica untuk scaling read) | Partisi Cluster Natif |

**What it is NOT:**
- **Bukan pengganti Graph Database:** Meskipun MongoDB mendukung lookup rekursif (`$graphLookup`), ia tidak dioptimalkan untuk penelusuran relasi jaringan yang sangat dalam (*deep interconnected traversals*) seperti Neo4j.
- **Bukan Flat JSON Store murni:** MongoDB tidak menyimpan file teks string JSON murni. Menyimpan text JSON secara raw (seperti kolom `text` di DB lama) memerlukan parsing runtime O(N). MongoDB menggunakan BSON binary format yang terstruktur dengan panjang byte eksplisit.
- **Bukan "No-Schema/No-Rules System":** Ketiadaan skema ketat di tingkat storage engine bukan izin untuk mengabaikan perancangan model data. Ketidakdisiplinan memodelkan dokumen memicu anomali *unbounded array*, fragmentasi memori, dan kegagalan query planning.

---

### 6. How It Works Under the Hood

#### 6.1 Anatomi Format BSON
BSON adalah representasi serial biner dokumen mirip JSON. Format ini memberikan dua keunggulan teknis:
1. **Traversal Cepat:** Setiap elemen dalam BSON diawali dengan tipe tipe data (1 byte), nama field (diakhiri null-byte `\x00`), dan ukuran total nilai data (*payload length*). Parser dapat melakukan *seek* (melompati) suatu field ke field berikutnya dengan menjumlahkan offset ukuran tanpa membaca seluruh struktur data internalnya.
2. **Presisi Tipe Data Ekstensif:** JSON tidak membedakan integer vs float (hanya mengenal `number`). BSON menyediakan:
   - `0x01` Double (64-bit IEEE 754)
   - `0x02` String (UTF-8, didahului panjang string)
   - `0x03` Embedded Document
   - `0x04` Array
   - `0x05` Binary data
   - `0x07` ObjectId (12-byte: 4-byte timestamp, 5-byte random value, 3-byte incrementing counter)
   - `0x10` 32-bit Integer
   - `0x12` 64-bit Integer
   - `0x13` 128-bit Decimal (IEEE 754-2008, untuk data finansial)

Layout biner sebuah dokumen BSON `{"name": "App", "qty": 5}`:
```
[Total Document Size: 4 bytes (int32)]
  [Type: 0x02 (String)] [Field Name: "name\x00"] [Length: 4 (int32)] ["App\x00"]
  [Type: 0x10 (Int32)]  [Field Name: "qty\x00"]  [Value: 5 (int32)]
[\x00 (Document Terminator)]
```

#### 6.2 Storage Engine WiredTiger: Cache, Checkpoint, dan WAL
WiredTiger mengelola data pada disk dalam bentuk halaman B-Tree (*B-Tree pages*). Ukuran halaman target default adalah 32 KB untuk data leaf page.

```
       [ Client Write Request ]
                  │
                  ▼
   +──────────────────────────────+
   │ WiredTiger In-Memory Cache   │
   │ ┌──────────────────────────┐ │
   │ │ In-Memory Page (B-Tree)  │ │
   │ │ - Read unmodified data   │ │
   │ │ - Modified dirty updates │ │
   │ └──────────────────────────┘ │
   +──────────────────────────────+
            │             │
   (Direct Append)  (Flush every 60s / 2GB)
            │             │
            ▼             ▼
      +───────────+ +───────────+
      │  Journal  │ │ Data File │
      │   (WAL)   │ │  (Disk)   │
      +───────────+ +───────────+
```

1. **In-Memory Cache Allocation:**
   Secara default, MongoDB mengalokasikan WiredTiger Cache sebesar:
   $$\text{WT Cache Size} = \max\left(0.5 \times (\text{RAM Total} - 1\text{ GB}),\ 256\text{ MB}\right)$$
   Sisa RAM dialokasikan untuk OS page cache, pemrosesan aggregasi runtime, dan koneksi client.
2. **Siklus Hidup Tulis (Write Path):**
   - Transaksi menulis update ke WiredTiger Cache. Halaman tersebut ditandai sebagai *dirty page*.
   - Operasi tulis secara bersamaan dicatat ke **Journal** (Write-Ahead Log) di disk sesuai dengan *Write Concern* (`w: "majority"`, `j: true`). Journal menggunakan buffer sekuensial cepat untuk memastikan durabilitas (*crash recovery*).
3. **Checkpointing:**
   - Setiap 60 detik (default) atau jika ukuran data log journal mencapai 2 GB, WiredTiger mengambil *checkpoint*.
   - Checkpoint menyajikan snapshot konsisten data pada disk. Seluruh dirty page di WiredTiger Cache ditulis ke file data disk dalam bentuk snapshot baru tanpa menimpa snapshot sebelumnya (*copy-on-write mechanism*).
   - Setelah checkpoint selesai ditulis sepenuhnya, pointer metadata dialihkan, dan log journal lama yang merekam transaksi sebelum checkpoint dibersihkan.
4. **Eviction Server:**
   Ketika *dirty data* dalam WiredTiger Cache melebihi threshold (default: 5% dari alokasi cache), thread *eviction* mulai bekerja di latar belakang. Jika cache terisi hingga 80%, eviction thread akan membuang halaman bersih (*clean pages*) dan menulis dirty pages ke disk untuk mempertahankan ketersediaan ruang memori bagi operasi baca/tulis baru.

---

### 7. Architectural / Flow Diagram (ASCII)

Diagram berikut menunjukkan aliran eksekusi ketika Client melakukan operasi tulis dengan Write Concern `w: 1, j: true` dan dilanjutkan dengan operasi baca:

```
[Client]                [mongod Network]         [WiredTiger Engine]       [Disk Subsystem]
   │                           │                          │                       │
   │─── 1. OP_MSG (Insert) ───>│                          │                       │
   │    (BSON over TCP)        │─── 2. Parse & Validate ─>│                       │
   │                           │    (Evaluate Schema)     │                       │
   │                           │                          │── 3. Mutate Cache ───>│
   │                           │                          │   (Mark Page Dirty)   │
   │                           │                          │                       │
   │                           │                          │── 4. Write Journal ──>│
   │                           │                          │   (Append to WAL)     │
   │                           │                          │<── 5. fsync ACK ──────│
   │                           │<── 6. Operation Complete─│                       │
   │<── 7. Insert OK ──────────│                          │                       │
   │                           │                          │                       │
   │   ... (Background Checkpoint Interval: Every 60s / Cache Threshold) ...      │
   │                                                      │                       │
   │                                                      │── 8. Reconcile Pages ─│
   │                                                      │   (Evict/Write Data)──> [Data Files]
   │                                                      │                       │
   │─── 9. OP_MSG (Find) ─────>│                          │                       │
   │                           │── 10. Check WT Cache ───>│                       │
   │                           │       (Page Hit?)        │                       │
   │                           │       [NO: Cache Miss]   │── 11. Read Block ────>│
   │                           │                          │<── 12. Decompress ────│
   │                           │<─ 13. Return Document ───│                       │
   │<── 14. Query Result ──────│                          │                       │
```

---

### 8. Simple, Isolated Code Example

Contoh eksekusi langsung manipulasi BSON dan pembacaan tipe data spesifik menggunakan `mongosh` (MongoDB Shell):

```javascript
// Switch ke database isolasi
use catalog_sandbox;

// 1. Definisikan dokumen dengan presisi tipe data BSON eksplisit
const productDocument = {
  _id: new ObjectId(), // 12-byte unique identifier
  sku: "PROD-TECH-9921",
  title: "Industrial Grade Sensor Hub",
  metadata: {
    firmware_version: "2.4.1",
    attributes: [
      { key: "voltage", value: "24V" },
      { key: "ip_rating", value: "IP68" }
    ]
  },
  inventory_count: NumberInt(450),             // 32-bit Integer (BSON 0x10)
  unit_price: NumberDecimal("1299.99"),         // 128-bit Decimal (BSON 0x13)
  last_maintenance: new Date("2024-03-15T08:00:00Z"), // UTC Date (BSON 0x09)
  payload_signature: new BinData(0, "aGVsbG8gd29ybGQ=") // Raw Binary (BSON 0x05)
};

// 2. Insert dokumen ke dalam collection
db.products.insertOne(productDocument);

// 3. Inspeksi representasi internal menggunakan bsonType operator
const inspectTypes = db.products.aggregate([
  { $match: { sku: "PROD-TECH-9921" } },
  {
    $project: {
      sku_type: { $type: "$sku" },
      inventory_count_type: { $type: "$inventory_count" },
      unit_price_type: { $type: "$unit_price" },
      maintenance_date_type: { $type: "$last_maintenance" }
    }
  }
]).toArray();

printjson(inspectTypes);
```

**Output Terminal:**
```json
[
  {
    "_id": ObjectId("65f4019a86e921b794101e4a"),
    "sku_type": "string",
    "inventory_count_type": "int",
    "unit_price_type": "decimal",
    "maintenance_date_type": "date"
  }
]
```

---

### 9. Production-Grade Practical Implementation

Implementasi koneksi layer repository menggunakan **Node.js (TypeScript)** dan driver native `mongodb`. Pola ini mengimplementasikan koneksi thread-safe, circuit-level retry policies, connection pooling terkontrol, dan inisialisasi skema validasi berbasis *JSON Schema Validator*.

```typescript
// src/database.ts
import { MongoClient, Db, MongoClientOptions, MongoServerError } from 'mongodb';

export interface DatabaseConfig {
  uri: string;
  dbName: string;
  minPoolSize: number;
  maxPoolSize: number;
  maxIdleTimeMS: number;
  connectTimeoutMS: number;
}

export class MongoDatabaseConnection {
  private static instance: MongoDatabaseConnection;
  private client: MongoClient | null = null;
  private db: Db | null = null;
  private readonly config: DatabaseConfig;

  private constructor(config: DatabaseConfig) {
    this.config = config;
  }

  public static getInstance(config: DatabaseConfig): MongoDatabaseConnection {
    if (!MongoDatabaseConnection.instance) {
      MongoDatabaseConnection.instance = new MongoDatabaseConnection(config);
    }
    return MongoDatabaseConnection.instance;
  }

  public async connect(): Promise<Db> {
    if (this.db && this.client) {
      return this.db;
    }

    const options: MongoClientOptions = {
      minPoolSize: this.config.minPoolSize,
      maxPoolSize: this.config.maxPoolSize,
      maxIdleTimeMS: this.config.maxIdleTimeMS,
      connectTimeoutMS: this.config.connectTimeoutMS,
      retryWrites: true,
      retryReads: true,
      writeConcern: {
        w: 'majority',
        wtimeoutMS: 5000,
      },
      readPreference: 'primaryPreferred',
    };

    try {
      this.client = new MongoClient(this.config.uri, options);
      await this.client.connect();
      
      // Ping database untuk memverifikasi kesiapan I/O layer
      this.db = this.client.db(this.config.dbName);
      await this.db.command({ ping: 1 });
      
      await this.applySchemaValidation(this.db);
      return this.db;
    } catch (error) {
      await this.disconnect();
      throw new Error(`Critical MongoDB initialization failure: ${(error as Error).message}`);
    }
  }

  private async applySchemaValidation(db: Db): Promise<void> {
    const collections = await db.listCollections({ name: 'orders' }).toArray();
    
    const schemaValidator = {
      $jsonSchema: {
        bsonType: 'object',
        required: ['order_id', 'customer_id', 'items', 'total_amount', 'created_at'],
        properties: {
          order_id: { bsonType: 'string', pattern: '^ORD-[0-9]{8}$' },
          customer_id: { bsonType: 'objectId' },
          items: {
            bsonType: 'array',
            minItems: 1,
            items: {
              bsonType: 'object',
              required: ['sku', 'quantity', 'unit_price'],
              properties: {
                sku: { bsonType: 'string' },
                quantity: { bsonType: 'int', minimum: 1 },
                unit_price: { bsonType: 'decimal' }
              }
            }
          },
          total_amount: { bsonType: 'decimal' },
          created_at: { bsonType: 'date' }
        }
      }
    };

    if (collections.length === 0) {
      await db.createCollection('orders', {
        validator: schemaValidator,
        validationLevel: 'strict',
        validationAction: 'error',
      });
      // Buat indeks pendukung
      await db.collection('orders').createIndex({ order_id: 1 }, { unique: true });
    } else {
      await db.command({
        collMod: 'orders',
        validator: schemaValidator,
        validationLevel: 'strict',
        validationAction: 'error',
      });
    }
  }

  public async getDb(): Promise<Db> {
    if (!this.db) {
      return this.connect();
    }
    return this.db;
  }

  public async disconnect(): Promise<void> {
    if (this.client) {
      await this.client.close(false);
      this.client = null;
      this.db = null;
    }
  }
}

// src/repository.ts
import { Collection, Decimal128, ObjectId } from 'mongodb';

export interface OrderItem {
  sku: string;
  quantity: number;
  unit_price: Decimal128;
}

export interface OrderDocument {
  _id?: ObjectId;
  order_id: string;
  customer_id: ObjectId;
  items: OrderItem[];
  total_amount: Decimal128;
  created_at: Date;
}

export class OrderRepository {
  private collection!: Collection<OrderDocument>;

  constructor(private readonly db: Db) {
    this.collection = this.db.collection<OrderDocument>('orders');
  }

  public async persistOrder(order: OrderDocument): Promise<ObjectId> {
    try {
      const result = await this.collection.insertOne(order);
      return result.insertedId;
    } catch (err) {
      if (err instanceof MongoServerError && err.code === 121) {
        // Document failed validation error
        throw new Error(`Schema Violation: Payload does not conform to orders collection schema: ${JSON.stringify(err.errInfo)}`);
      }
      if (err instanceof MongoServerError && err.code === 11000) {
        // Duplicate key error
        throw new Error(`Conflict: Order ID ${order.order_id} already exists`);
      }
      throw err;
    }
  }
}
```

---

### 10. Deep-Dive Edge Cases & Failure Modes

#### 10.1 Limitasi BSON 16 MB dan Masalah Relasional
Ukuran maksimum sebuah dokumen BSON tunggal adalah **16 Megabytes**.
- **Mekanisme Kegagalan:** Jika Anda mendesain skema log, histori obrolan (*chat logs*), atau sensor IoT di mana setiap pembacaan data di-*push* menggunakan `$push` ke array di dalam satu dokumen, dokumen tersebut pada akhirnya akan menabrak limit 16 MB. Operasi tulis berikutnya akan melempar error: `BSONObjectTooLarge (code 10334)`.
- **Dampak Storage Engine:** Mendekati batas ini, dokumen yang terus membesar menyebabkan realokasi memori berulang di WiredTiger. Proses ini memaksa engine menyalin seluruh isi memori dokumen lama ke blok baru yang contiguous, menciptakan fragmentasi disk dan lonjakan latensi (*I/O spikes*).

#### 10.2 Presisi Tipe Data: JSON Parser Lossy Conversion
JavaScript runtime secara default memetakan semua angka sebagai Double 64-bit IEEE 754.
- **Kasus Kerusakan Data:**
  ```javascript
  // Berbahaya: Konversi otomatis JSON desimal ke float driver JS
  const price = 0.1 + 0.2; // 0.30000000000000004
  await db.collection('accounts').updateOne(
    { _id: accId },
    { $set: { balance: price } } // Disimpan sebagai double di BSON
  );
  ```
- **Solusi Mutlak:** Gunakan selalu tipe eksplisit `Decimal128` untuk representasi mata uang guna menghindari hilangnya bit akurasi pada operasi pembagian dan penambahan.

#### 10.3 Unbounded In-Place Array Updates
Melakukan update berulang ke array bersarang tanpa pre-allocation memicu fragmentasi halaman internal WiredTiger. Halaman B-Tree yang terpecah (*page split*) menurunkan *cache hit ratio* karena disk space yang dialokasikan diisi oleh padding byte yang tidak efisien.

---

### 11. Trade-Off Analysis

| Dimensi Keputusan | Pola Embedding (Denormalized) | Pola Referencing (Normalized) |
|---|---|---|
| **Pola Akses Read** | **Sangat Cepat (O(1) seek).** Semua data terambil dalam single network roundtrip. | **Lebih Lambat (O(N) network hops/lookups).** Perlu `$lookup` atau multiple query dari client. |
| **Karakteristik Write** | **Kompleks / Rentan Duplikasi.** Update pada data yang di-embed menuntut multi-document updates. | **Atomic & Terisolasi.** Update data induk hanya dieksekusi pada 1 record/dokumen. |
| **Beban WiredTiger Cache**| Menghabiskan cache lebih cepat jika hanya sebagian kecil data embed yang benar-benar dibaca. | Efisien. Hanya data relasi spesifik yang ditarik masuk ke cache pages. |
| **Batas Dokumen 16MB** | Rentan terkena batasan jika relasi bersifat *one-to-many* tak terhingga ($1:N$ unbounded). | Kebal dari batasan 16 MB karena data historis dipecah per baris dokumen terpisah. |

**Kaidah Desain:**
- Pilih **Embedding** jika relasi bersifat $1:1$ atau $1:\text{Few}$ (misal: alamat pengiriman pesanan) di mana data anak selalu dikonsumsi bersama data induk dan tidak tumbuh secara independen.
- Pilih **Referencing** jika relasi bersifat $1:\text{Many}$ atau $1:\text{Squillions}$ (misal: log log-in pengguna, sensor telemetry) atau jika data anak sering diperbarui terpisah dari data induk.

---

### 12. Security & Compliance Implications

#### 12.1 Kontrol Akses dan Komunikasi Jaringan
- **Enkripsi Transit (TLS 1.3):** Komunikasi antara driver aplikasi dan cluster `mongod` wajib menggunakan enkripsi TLS dengan sertifikat X.509 terverifikasi.
- **Autentikasi SCRAM-SHA-256:** Jangan pernah menggunakan sistem autentikasi legacy (MONGODB-CR). Gunakan `SCRAM-SHA-256` yang mengimplementasikan derivasi kunci berbasis PBKDF2 untuk mitigasi serangan *rainbow table*.

#### 12.2 Prinsip Hak Akses Terendah (Least Privilege via RBAC)
Hindari pemakaian role bawaan `readWriteAnyDatabase` di level aplikasi. Definisikan role granular:
```javascript
use admin;
db.createRole({
  role: "orderServiceRole",
  privileges: [
    {
      resource: { db: "ecommerce", collection: "orders" },
      actions: [ "find", "insert", "update" ] // Cegah action "dropCollection" atau "remove" sembarangan
    }
  ],
  roles: []
});
```

#### 12.3 Enkripsi Tingkat Lapangan (CSFLE / Queryable Encryption)
Untuk data PII (Personally Identifiable Information) yang tunduk pada GDPR/HIPAA/UU PDP, enkripsi level disk (*LUKS / Storage Encryption at Rest*) tidak melindungi kebocoran memori saat data di-dump oleh hacker berizin DBA. Gunakan Client-Side Field Level Encryption (CSFLE): driver mengenkripsi field tertentu (misal: `credit_card_number`) di sisi memori aplikasi menggunakan master key dari KMS (AWS KMS, GCP KMS, Vault) *sebelum* dikirimkan melalui jaringan ke database.

---

### 13. Performance & Resource Characteristics

#### 13.1 Metrik Penggunaan Memori WiredTiger
Ukuran *dirty memory* WiredTiger cache harus diperhatikan:
- Jika $\text{Dirty Pages} \ge 5\%$, eviction thread latar belakang mulai menyapu cache.
- Jika $\text{Dirty Pages} \ge 20\%$, MongoDB akan memblokir thread client aplikasi dan memaksa koneksi client tersebut membantu proses *eviction* data ke disk. Ini memicu lonjakan latensi dramatis (*latency spike stalling*).

#### 13.2 Overhead Alokasi Dokumen BSON
Field name BSON disimpan berulang di setiap dokumen. Jika Anda memiliki dokumen dengan field berkarakter panjang:
```json
{"transaction_identification_reference_number": "TX-01"}
```
Dikalikan 500 juta dokumen, overhead penamaan field ini dapat menyita puluhan Gigabyte RAM dan Disk. 
*Mitigasi:* Gunakan penamaan field yang ringkas namun representatif pada skema dokumen bervolume ekstrem (contoh: `tx_ref_id`).

#### 13.3 Karakteristik I/O Disk
WiredTiger menuntut performa IOPS tinggi. Penulisan Journal membutuhkan storage dengan latensi *fsync* rendah. Menjalankan MongoDB di volume EBS/Cloud Disk dengan batasan burst I/O (seperti AWS gp2 standar) dapat menyebabkan *exhaustion I/O credits* yang membekukan operasi cluster saat checkpoint berjalan. Rekomendasi minimum production: IOPS dedicated (AWS gp3 dengan minimal 3000 IOPS atau io2).

---

### 14. Anti-Patterns & Code Smells

#### 14.1 Anti-Pattern 1: The Relational Mirror (Normalization Paralyzation)
- **Kode Buruk:**
  ```javascript
  // Disimpan dalam 4 collection terpisah: orders, order_lines, products, taxes
  // Aplikasi melakukan 3x $lookup secara berantai
  db.orders.aggregate([
    { $lookup: { from: "order_lines", localField: "_id", foreignField: "order_id", as: "lines" } },
    { $unwind: "$lines" },
    { $lookup: { from: "products", localField: "lines.product_id", foreignField: "_id", as: "prod" } }
  ]);
  ```
- **Koreksi:** Denormalisasikan detail item produk (nama, SKU, harga saat transaksi) langsung di dalam array dokumen `orders`. Transaksi masa lalu tidak boleh terpengaruh oleh perubahan harga produk masa kini di master katalog.

#### 14.2 Anti-Pattern 2: Unbounded Array Growth
- **Kode Buruk:**
  ```javascript
  // Model user audit trail
  db.users.updateOne(
    { _id: userId },
    { $push: { audit_logs: { action: "LOGIN", timestamp: new Date() } } } // Terus tumbuh selamanya!
  );
  ```
- **Koreksi:** Pisahkan audit log ke koleksi independen (`user_audit_logs`) di mana setiap log adalah 1 dokumen terpisah, atau gunakan pola *Bucket Pattern* (mengelompokkan per 100 log per dokumen).

#### 14.3 Anti-Pattern 3: Obscure Type Polling
- **Kode Buruk:** Menggunakan field bertipe data campuran (misal: field `age` kadang bernilai `String` `"25"`, kadang bernilai `NumberInt` `25`).
- **Koreksi:** Aktifkan skema validasi `collMod` dengan aturan tipe data ketat di tingkat collection engine.

---

### 15. Concrete Migration or Adoption Scenario

#### Skenario: Migrasi Skema Katalog Produk Polymorphic dari PostgreSQL ke MongoDB
**Kondisi Awal (Postgres):** Skema EAV (*Entity-Attribute-Value*) yang rapuh dengan 3 tabel (`products`, `attribute_definitions`, `product_attribute_values`) berisi 20 juta baris atribut yang menyebabkan query rendering halaman katalog memakan waktu > 1.2 detik karena multi-table join lock.

#### Fase 1: Pemetaan Skema Transformasi
Konversi relasi flat normalization menjadi dokumen tunggal teragregasi secara denormalized.

```
PostgreSQL:
[products] 1 ──── N [product_attribute_values] N ──── 1 [attribute_definitions]

                │ (ETL Pipeline: Debezium / CDC / Script)
                ▼

MongoDB:
Collection: "products"
{
  "_id": ObjectId("..."),
  "sku": "...",
  "attributes": {
    "screen_size": "6.1 inch",
    "battery_capacity": 4000
  }
}
```

#### Fase 2: Skrip Migrasi Pipeline (Node.js Stream Batched)
```typescript
import { Client as PgClient } from 'pg';
import { MongoClient, Decimal128 } from 'mongodb';

async function migrateData() {
  const pg = new PgClient({ connectionString: 'postgres://user:pass@localhost:5432/legacy_shop' });
  const mongo = new MongoClient('mongodb://localhost:27017');
  
  await pg.connect();
  await mongo.connect();
  
  const mongoCollection = mongo.db('catalog_v2').collection('products');
  
  // Mengambil data teragregasi dari Postgres via JSON building native
  const query = `
    SELECT 
      p.sku, 
      p.title, 
      p.price::text as price,
      json_object_agg(ad.name, pav.value_string) AS dynamic_attributes
    FROM products p
    JOIN product_attribute_values pav ON p.id = pav.product_id
    JOIN attribute_definitions ad ON pav.attribute_id = ad.id
    GROUP BY p.sku, p.title, p.price;
  `;

  const cursor = pg.query(query); // Menggunakan internal streaming
  let batch: any[] = [];
  
  // Proses batch insertion 1000 docs/chunk
  // Mengurangi load memori runtime nodejs
  // ... implementasi streaming batch insert via mongoCollection.insertMany(batch)
}
```

#### Fase 3: Strategi Verifikasi & Dual-Run Cutover
1. **Shadow Writing:** Setiap transaksi update di layer service ditulis secara asinkron ke PostgreSQL dan MongoDB.
2. **Data Consistency Audit:** Jalankan background job yang menghitung cryptographic hash antar record di Postgres vs dokumen di MongoDB secara berkala.
3. **Read Canary Testing:** Alihkan 5% traffic read katalog ke MongoDB, pantau p99 latency dan error rate. Tingkatkan bertahap ke 100%.

---

### 16. Testing, Automation & Verification

Pengujian integrasi MongoDB modern memanfaatkan **Testcontainers** untuk menjalankan instance database murni di dalam Docker container secara otomatis saat unit test dijalankan, menghilangkan mock database yang rapuh.

```typescript
// test/catalog.integration.test.ts
import { GenericContainer, StartedTestContainer } from 'testcontainers';
import { MongoClient, Db, Decimal128 } from 'mongodb';
import { OrderRepository, OrderDocument } from '../src/repository';

describe('MongoDB Production Integration Test', () => {
  let container: StartedTestContainer;
  let client: MongoClient;
  let db: Db;
  let repository: OrderRepository;

  beforeAll(async () => {
    // Spin up container MongoDB resmi secara transien
    container = await new GenericContainer('mongo:7.0')
      .withExposedPorts(27017)
      .start();

    const uri = `mongodb://${container.getHost()}:${container.getMappedPort(27017)}`;
    client = new MongoClient(uri);
    await client.connect();
    db = client.db('test_db');

    // Inisialisasi index dan repository
    await db.collection('orders').createIndex({ order_id: 1 }, { unique: true });
    repository = new OrderRepository(db);
  }, 30000);

  afterAll(async () => {
    await client.close();
    await container.stop();
  });

  afterEach(async () => {
    // Bersihkan collection antar test case
    await db.collection('orders').deleteMany({});
  });

  it('harus berhasil memvalidasi penulisan order valid', async () => {
    const validOrder: OrderDocument = {
      order_id: 'ORD-12345678',
      customer_id: new (await import('mongodb')).ObjectId(),
      items: [
        { sku: 'SKU-01', quantity: 2, unit_price: Decimal128.fromString('49.99') }
      ],
      total_amount: Decimal128.fromString('99.98'),
      created_at: new Date()
    };

    const insertedId = await repository.persistOrder(validOrder);
    expect(insertedId).toBeDefined();

    const record = await db.collection('orders').findOne({ order_id: 'ORD-12345678' });
    expect(record).not.toBeNull();
    expect(record?.items[0].sku).toBe('SKU-01');
  });

  it('harus menolak duplikasi order_id dengan melempar error konflik', async () => {
    const doc: OrderDocument = {
      order_id: 'ORD-99999999',
      customer_id: new (await import('mongodb')).ObjectId(),
      items: [{ sku: 'SKU-A', quantity: 1, unit_price: Decimal128.fromString('10.00') }],
      total_amount: Decimal128.fromString('10.00'),
      created_at: new Date()
    };

    await repository.persistOrder(doc);

    // Write kedua dengan order_id yang sama harus ditolak
    await expect(repository.persistOrder(doc)).rejects.toThrow(/Conflict: Order ID ORD-99999999 already exists/);
  });
});
```

---

### 17. Operational Runbook & Troubleshooting

#### Masalah: Cache Pressure Tinggi dan Latensi Read/Write Melonjak
**Kondisi:** Metrik latensi operasi MongoDB tiba-tiba naik dari 2ms ke 800ms. CPU utilisasi 95%.

```
                             [ DIAGNOSIS FLOW ]
                                     │
                 Jalankan db.serverStatus().wiredTiger.cache
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
     "tracked dirty bytes in cache"     "tracked dirty bytes in cache"
         > 20% total cache size              < 5% total cache size
                    │                                 │
                    ▼                                 ▼
   [ Aplikasi terblokir eviction! ]      [ Cek Slow Queries & Locks ]
   - Jalankan db.currentOp()             - Jalankan db.currentOp({secs_running: {$gt: 3}})
   - Filter thread write masif           - Identifikasi index miss (COLLSCAN)
   - Cari dokumen mendekati 16MB         - Jalankan db.killOp(opid) untuk query zombie
```

**Langkah Mitigasi Insiden:**
1. **Analisis Status Cache WiredTiger:**
   ```javascript
   // Jalankan pada mongosh
   db.serverStatus().wiredTiger.cache["tracked dirty bytes in the cache"]
   db.serverStatus().wiredTiger.cache["bytes currently in the cache"]
   db.serverStatus().wiredTiger.cache["maximum bytes configured"]
   ```
2. **Inspeksi Operasi yang Berjalan Lambat (Active Locking Operations):**
   ```javascript
   db.currentOp({
     "active": true,
     "secs_running": { "$gt": 5 }
   });
   ```
3. **Terminasi Paksa Operasi Liar (Rogue Query):**
   Ambil nilai `opid` dari output `currentOp` di atas, lalu eksekusi:
   ```javascript
   db.killOp(1234567); // Ganti dengan opid spesifik
   ```
4. **Analisis Fragmentasi Koleksi dan Penggunaan Disk:**
   ```javascript
   db.orders.stats().wiredTiger.block-manager
   // Perhatikan rasio: "file size in bytes" vs "size in bytes of the allocated blocks"
   ```
   Jika terjadi fragmentasi masif akibat operasi update bertubi-tubi pada embedded array, jadwalkan compacting:
   ```javascript
   db.runCommand({ compact: 'orders' }); // Membutuhkan lock, jalankan hanya di node sekunder atau maintenance window!
   ```

---

### 18. Best Practices Checklist

#### Skema & Format Data
- [ ] Batasi dokumen BSON maksimal berada dalam batas aman: idealnya < 2 MB (jauh di bawah batas 16 MB).
- [ ] Jangan gunakan tipe `Double` untuk data moneter; gunakan secara eksklusif `Decimal128`.
- [ ] Representasikan tanggal selalu dalam native `ISODate` (UTC), bukan string numerik timestamp Unix atau formatted string.
- [ ] Terapkan skema validasi deklaratif via `$jsonSchema` di level koleksi database untuk mencegah *data drift*.

#### Driver & Koneksi Jaringan
- [ ] Konfigurasikan `minPoolSize` (misal: 10) dan `maxPoolSize` (misal: 100) proporsional terhadap kapasitas thread CPU dan limit file descriptor server.
- [ ] Terapkan secara eksplisit `w: "majority"` dan `wtimeoutMS: 5000` pada seluruh alur transaksi vital.
- [ ] Selalu manfaatkan reusable singleton instance untuk MongoClient, jangan buat connection instance baru per HTTP request!

#### Performa Engine & Hardware
- [ ] Pastikan alokasi WiredTiger Cache tidak melebihi 50-60% kapasitas total physical RAM mesin, menyisakan ruang bagi OS Page Cache.
- [ ] Nonaktifkan Linux transparent huge pages (THP) pada environment production OS:
  ```bash
  echo never > /sys/kernel/mm/transparent_hugepage/enabled
  echo never > /sys/kernel/mm/transparent_hugepage/defrag
  ```
- [ ] Simpan direktori data MongoDB pada volume mount berbasis filesystem `XFS` (bukan ext4) untuk throughput konkurensi I/O yang optimal.

---

### 19. Alternative Approaches & When to Use Them

| Kebutuhan Sistem | Solusi Rekomendasi | Mengapa Tidak Menggunakan MongoDB? |
|---|---|---|
| **Data Relasional Kompleks (Ketat ACID Multitabel)** | **PostgreSQL** | Jika integritas referensial dan foreign key lintas 50+ relasi entitas adalah persyaratan utama bisnis, normalisasi relasional Postgres jauh lebih andal dan menghemat data duplication overhead. |
| **High Frequency Transient Key-Value (Microsecond Access)** | **Redis / Dragonfly** | MongoDB memiliki overhead layer komputasi dokumen BSON dan persistensi disk. Redis bekerja in-memory penuh untuk lookup $O(1)$ dengan latensi sub-milidetik. |
| **Pencarian Logika Teks Penuh Skala Besar (Full-Text Search & Log Analytics)** | **Elasticsearch / OpenSearch** | Fitur text-index dan regex MongoDB tidak dirancang untuk menangani analisis linguistik mendalam, tokenization rumit, scoring TF-IDF dinamis, dan agregasi log terbalik pada triliunan baris. |
| **Write-Heavy Ultra Scale Time-Series Tanpa Modifikasi** | **ClickHouse / Cassandra** | Untuk jutaan write per detik yang bersifat write-only (append-only telemetry), arsitektur LSM-Tree (Cassandra) atau Columnar (ClickHouse) mengungguli B-Tree WiredTiger dalam kompresi dan kapasitas throughput tulis mentah. |

---

### 20. Open Questions, Challenges & Exercises

#### Conceptual & Diagnostic Questions
1. **Analisis Mekanisme Eviction:** Dalam skenario di mana utilisasi RAM sistem mencapai 99%, namun metrik `wiredTiger.cache["bytes currently in the cache"]` baru mencapai 30% dari batas maksimalnya, jelaskan komponen sistem operasi apa yang mengonsumsi sisa RAM tersebut, dan bagaimana interaksinya dengan OS Page Cache saat MongoDB melayani query yang tidak terindeks!
2. **Dekonstruksi BSON:** Mengapa operasi pengubahan tipe data field dari `Int32` menjadi `Int64` (misal dari `5` ke `5000000000`) di dalam dokumen yang tersimpan pada blok disk padat berpotensi memicu degradasi performa I/O WiredTiger lebih tinggi daripada sekadar mengupdate field string dengan panjang karakter yang sama?

#### Architectural Design Challenge
Rancang arsitektur model dokumen skema database untuk sistem pelacakan paket kargo internasional (Fleet Tracking System). 
- Sistem menangani 10 juta pengiriman aktif per bulan.
- Setiap pengiriman memiliki riwayat lokasi checkpoints status (bisa berkisar antara 5 lokasi hingga 2.500 pembacaan ping GPS per pengiriman).
- Pengguna aplikasi mobile sering memantau "Status Terakhir" pengiriman.
- Laporan audit historis memerlukan data seluruh checkpoints secara kronologis.

*Tugas Anda:* 
Buat skema dokumen BSON JSON untuk kasus di atas yang:
1. Menghindari batasan BSON 16 MB.
2. Memastikan query untuk halaman pelacakan status terakhir dieksekusi dalam kompleksitas $O(1)$ memori/seek time.
3. Mencegah fragmentasi dokumen berulang di WiredTiger engine saat ada lokasi baru yang masuk. Jelaskan pola desain yang Anda terapkan!