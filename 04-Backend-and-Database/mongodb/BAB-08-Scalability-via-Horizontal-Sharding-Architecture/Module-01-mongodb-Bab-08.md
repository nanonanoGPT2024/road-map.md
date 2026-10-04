# Bab 08 Module 01: Scalability via Horizontal Sharding Architecture

---

## Seksi 01: Identitas Modul
* **Mata Pelajaran:** Backend Engineering & Distributed Database Architecture
* **Kategori:** 04-Backend-and-Database
* **Topik:** MongoDB Horizontal Scalability & Sharded Cluster Architecture
* **Tingkat Kesulitan:** Advanced / Principal Engineer
* **Prasyarat:** MongoDB Replica Sets, B-Tree Indexing Internals, Distributed Systems Basics (CAP/PACELC Theorem), Docker & Bash Scripting.

---

## Seksi 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda akan mampu:
1. Membedakan secara mendalam trade-offs mekanis antara Ranged Sharding dan Hashed Sharding.
2. Mengonfigurasi, menginisialisasi, dan mengoperasikan topologi MongoDB Sharded Cluster lengkap (`mongos`, Config Server Replica Set, dan Shard Replica Sets).
3. Menganalisis dan memilih Shard Key yang optimal menggunakan matriks kardinalitas, frekuensi tulis/baca, dan kriteria isolasi query.
4. Mengendalikan proses internal balancing, chunk migrations, chunk split, dan mitigasi jumbo chunks tanpa downtime aplikasi.
5. Membangun pipeline backend Node.js production-grade yang resilient terhadap cluster re-topology dan latensi transient pada routed queries.

---

## Seksi 03: Concept Map Diagram
```
+-------------------------------------------------------------------------------+
|                             CLIENT APPLICATION                                |
+-------------------------------------------------------------------------------+
                                     |
                          [Mongo Driver Connection]
                                     v
+-------------------------------------------------------------------------------+
|                            QUERY ROUTERS (mongos)                             |
|  - Stateless query routing engine                                             |
|  - Metadata cache synchronizer                                                |
|  - Scatter-gather vs. Targeted Query dispatcher                               |
+-------------------------------------------------------------------------------+
          |                                                    |
          | [Metadata Fetch & Sync]                            | [Data Dispatch]
          v                                                    v
+------------------------------------+   +--------------------------------------+
|    CONFIG SERVER REPLICA SET       |   |             DATA SHARDS              |
|          (CSRS - 3 nodes)          |   |                                      |
|                                    |   |  +--------------------------------+  |
| - Menyimpan metadata routing table |   |  | Shard 01 (Replica Set: P-S-A/S)|  |
| - Mengelola Chunk Distribution Map |   |  | - Chunk [MinKey -> 0]          |  |
| - Koordinasi Lock Distributed Bal. |   |  +--------------------------------+  |
| - Mengawasi FCV & Auth Catalog     |   |  +--------------------------------+  |
|                                    |   |  | Shard 02 (Replica Set: P-S-A/S)|  |
|                                    |   |  | - Chunk [0 -> MaxKey]          |  |
+------------------------------------+   +--------------------------------------+
                                                           ^
                                                           | (Chunk Migration via
                                                           |  Internal Balancer)
                                                           v
                                         +--------------------------------------+
                                         | Shard 03 (Replica Set: P-S-A/S)      |
                                         | - Receiving new Chunks               |
                                         +--------------------------------------+
```

---

## Seksi 04: Mengapa Relevan
Ketika sebuah aplikasi monolitik atau microservice mengalami ledakan data melampaui batas throughput I/O disk tunggal, batasan RAM untuk *Working Set*, atau batas saturasi CPU pada single replica set, *Vertical Scaling* (menambah vCPU/RAM) mencapai titik *diminishing returns* dan *cost-prohibitive*.

Horizontal Sharding adalah mekanisme skalabilitas terdistribusi untuk mempartisi data set besar ke beberapa *Replica Sets* independen. Dengan memahami arsitektur sharding:
* Data didistribusikan secara dinamis sehingga kapasitas write throughput meningkat secara linear seiring bertambahnya shard node.
* Working set dibagi ke RAM masing-masing host shard, mengeliminasi bottleneck *page evictions* pada storage engine WiredTiger.
* Ketersediaan sistem tetap terjaga meski salah satu shard sedang memproses migrasi data skala terabyte.

---

## Seksi 05: Anatomi Konsep Inti

### 1. Komponen Utama Cluster Sharding
* **`mongos` (Query Router):** Router stateless yang menerima query dari klien, membaca metadata dari Config Database, menentukan shard mana yang memiliki data yang diminta, meneruskan query, dan menggabungkan hasilnya (*Scatter-Gather* atau *Targeted*).
* **Config Database (Config Server Replica Set / CSRS):** Replica set khusus yang menyimpan metadata pemetaan chunk ke shard, lock balancer, dan konfigurasi cluster. Harus berupa Replica Set dengan konsistensi tinggi (WiredTiger Engine).
* **Shard (Data Node):** Setiap shard adalah Replica Set mandiri untuk menjamin *High Availability* (HA). Shard mengeksekusi operasi baca/tulis terhadap partisi data (chunks) yang dialokasikan padanya.

### 2. Chunk Architecture dan Mekanisme Balancer
* **Chunks:** Kumpulan dokumen logis yang dibatasi oleh rentang Shard Key: $[\text{lowerBound}, \text{upperBound})$. Default ukuran chunk pada MongoDB modern adalah 64MB (dapat dikonfigurasi).
* **Chunk Split:** Terjadi saat sebuah chunk mencapai ukuran maksimum atau batasan jumlah dokumen; split hanya memodifikasi metadata pada CSRS, bukan memindahkan dokumen fisik.
* **Balancer:** Proses terdistribusi yang berjalan di CSRS Primary (sejak MongoDB 3.4+). Jika perbedaan jumlah chunk antar-shard melebihi ambang batas (*migration threshold*), Balancer memulai *Chunk Migration* asinkron dari *donor shard* ke *recipient shard*.

### 3. Hashed Sharding vs Ranged Sharding

```
RANGED SHARDING (Berdasarkan Nilai Monotonik / Range):
[Shard 1: "A" -> "M"] <---- Chunk Boundary ----> [Shard 2: "N" -> "Z"]
- Keuntungan: Query Range ($gte, $lte) bersifat terisolasi (Targeted Query).
- Masalah: Insert berbasis ObjectId/Timestamp memicu "Hotspotting" pada Shard terakhir.

HASHED SHARDING (Berdasarkan MD5-based 64-bit Hash):
[Shard 1: Hash(Val) % 2 == 0] <-----------------> [Shard 2: Hash(Val) % 2 != 0]
- Keuntungan: Distribusi Write merata secara matematis, mengeliminasi write hotspots.
- Masalah: Query Range ($gte, $lte) memaksa Router melakukan Scatter-Gather (Broadcast).
```

### 4. Strategi Pemilihan Shard Key
Shard Key bersifat **immutable** (pada versi sebelum 4.4, dan dapat diubah dengan `refineCollectionShardKey` di MongoDB 4.4+). Pemilihan harus menyeimbangkan tiga faktor:
1. **Kardinalitas Tinggi:** Rentang nilai unik harus sangat banyak untuk mencegah terbentuknya *Jumbo Chunks* (chunk yang tidak bisa di-split).
2. **Frekuensi Tulis Rendah per Key:** Mencegah konsentrasi write pada satu boundary point.
3. **Isolasi Query Terbanyak:** Mengizinkan `mongos` merutekan query baca ke shard spesifik (*Single-Shard Targeted Query*) bukan broadcast (*Scatter-Gather Query*).

---

## Seksi 06: Panduan Implementasi Step-by-Step

Berikut adalah langkah deklaratif deployment Sharded Cluster skala minimal (1 CSRS, 2 Shards, 1 Mongos) pada local runtime.

### Step 1: Membuat Network dan Storage Terisolasi
```bash
docker network create mongo-sharded-net

mkdir -p /tmp/mongo/config01 /tmp/mongo/shard01a /tmp/mongo/shard02a
```

### Step 2: Menjalankan Config Server Replica Set (CSRS)
```bash
docker run -d --name cfg01 --net mongo-sharded-net -p 27019:27019 \
  mongodb/mongodb-community-server:7.0-ubuntu2204 \
  mongod --configsvr --replSet rs-config --port 27019 --bind_ip_all
```

Inisialisasi CSRS via `mongosh`:
```bash
docker exec -it cfg01 mongosh --port 27019 --eval '
rs.initiate({
  _id: "rs-config",
  configsvr: true,
  members: [{ _id: 0, host: "cfg01:27019" }]
})
'
```

### Step 3: Menjalankan Node Shard 1 & Shard 2
```bash
# Shard 01 Node
docker run -d --name shard01 --net mongo-sharded-net -p 27018:27018 \
  mongodb/mongodb-community-server:7.0-ubuntu2204 \
  mongod --shardsvr --replSet rs-shard-01 --port 27018 --bind_ip_all

# Shard 02 Node
docker run -d --name shard02 --net mongo-sharded-net -p 27028:27028 \
  mongodb/mongodb-community-server:7.0-ubuntu2204 \
  mongod --shardsvr --replSet rs-shard-02 --port 27028 --bind_ip_all
```

Inisialisasi Replica Set pada masing-masing Shard:
```bash
docker exec -it shard01 mongosh --port 27018 --eval '
rs.initiate({
  _id: "rs-shard-01",
  members: [{ _id: 0, host: "shard01:27018" }]
})
'

docker exec -it shard02 mongosh --port 27028 --eval '
rs.initiate({
  _id: "rs-shard-02",
  members: [{ _id: 0, host: "shard02:27028" }]
})
'
```

### Step 4: Menjalankan Query Router (`mongos`)
```bash
docker run -d --name mongos-router --net mongo-sharded-net -p 27017:27017 \
  mongodb/mongodb-community-server:7.0-ubuntu2204 \
  mongos --configdb rs-config/cfg01:27019 --port 27017 --bind_ip_all
```

### Step 5: Menambahkan Shards ke Cluster via `mongos`
Hubungkan ke `mongos` pada port 27017:
```bash
docker exec -it mongos-router mongosh --port 27017 --eval '
sh.addShard("rs-shard-01/shard01:27018");
sh.addShard("rs-shard-02/shard02:27028");
sh.status();
'
```

---

## Seksi 07: Contoh Kasus Sederhana

Skenario: Mempartisi database `ecommerce` pada collection `orders` menggunakan strategi **Hashed Shard Key** pada atribut `order_id`.

```javascript
// Jalankan langsung di dalam mongosh (terkoneksi ke mongos:27017)

// 1. Pindah ke database target
use ecommerce;

// 2. Buat index hashed pada Shard Key
db.orders.createIndex({ order_id: "hashed" });

// 3. Aktifkan Sharding pada Database
sh.enableSharding("ecommerce");

// 4. Lakukan Sharding pada Collection menggunakan Hashed Shard Key
sh.shardCollection("ecommerce.orders", { order_id: "hashed" });

// 5. Injeksi Data Dummy untuk Verifikasi Distribusi
const ordersBatch = [];
for (let i = 1; i <= 10000; i++) {
  ordersBatch.push({
    order_id: "ORD-" + i + "-" + Math.random().toString(36).substring(7),
    customer_id: "CUST-" + (i % 100),
    amount: (Math.random() * 500).toFixed(2),
    created_at: new Date()
  });
}
db.orders.insertMany(ordersBatch);

// 6. Verifikasi Distribusi Dokumen per Shard
db.orders.getShardDistribution();
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi connection pooling, handling sharded retries, dan distributed operations menggunakan Node.js TypeScript driver yang siap produksi.

### File: `package.json`
```json
{
  "name": "mongodb-sharding-production",
  "version": "1.0.0",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js"
  },
  "dependencies": {
    "mongodb": "^6.5.0"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "typescript": "^5.3.3"
  }
}
```

### File: `src/ClusterManager.ts`
```typescript
import { MongoClient, Db, Collection, ReadPreference, WriteConcern } from 'mongodb';

export interface OrderDocument {
  tenantId: string;
  orderId: string;
  userId: string;
  items: Array<{ itemId: string; price: number; quantity: number }>;
  totalAmount: number;
  status: 'PENDING' | 'PAID' | 'SHIPPED';
  createdAt: Date;
}

export class DistributedDatabaseClient {
  private client: MongoClient;
  private dbName: string = 'enterprise_commerce';

  constructor(connectionUri: string) {
    // Production tuning untuk Sharded Cluster Connection Pool
    this.client = new MongoClient(connectionUri, {
      maxPoolSize: 100,
      minPoolSize: 20,
      maxIdleTimeMS: 30000,
      waitQueueTimeoutMS: 5000,
      // targeted replica read preference
      readPreference: ReadPreference.SECONDARY_PREFERRED,
      // Majority write concern demi konsistensi lintas shards
      writeConcern: new WriteConcern('majority', 5000),
      retryWrites: true,
      retryReads: true,
      // Heartbeat tuning untuk mendeteksi perubahan topology router/shard
      heartbeatFrequencyMS: 10000,
    });
  }

  public async connect(): Promise<void> {
    await this.client.connect();
    console.log('[CLUSTER] Connected successfully to Mongos Routers');
  }

  public async getDatabase(): Promise<Db> {
    return this.client.db(this.dbName);
  }

  public getOrdersCollection(): Collection<OrderDocument> {
    return this.client.db(this.dbName).collection<OrderDocument>('orders');
  }

  public async initializeShardingSchema(): Promise<void> {
    const adminDb = this.client.db('admin');
    const db = this.client.db(this.dbName);

    // 1. Pastikan database terdaftar untuk sharding
    await adminDb.command({ enableSharding: this.dbName });

    // 2. Buat Compound Compound Shard Key Index: { tenantId: 1, orderId: "hashed" }
    // Memastikan isolasi Multi-tenant (Ranged) + Distribusi Uniform per tenant (Hashed)
    await db.collection('orders').createIndex({ tenantId: 1, orderId: 'hashed' });

    // 3. Shard Collection berdasarkan compound key
    try {
      await adminDb.command({
        shardCollection: `${this.dbName}.orders`,
        key: { tenantId: 1, orderId: 'hashed' }
      });
      console.log('[SCHEMA] Collection partitioned successfully with Compound Shard Key');
    } catch (err: any) {
      if (err.codeName === 'AlreadySharded') {
        console.log('[SCHEMA] Collection already sharded. Skipping.');
      } else {
        throw err;
      }
    }
  }

  public async insertOrder(order: OrderDocument): Promise<void> {
    const collection = this.getOrdersCollection();
    // Insert dieksekusi via mongos langsung diarahkan ke shard yang tepat (Targeted Write)
    await collection.insertOne(order);
  }

  public async findOrdersByTenant(tenantId: string, limit: number = 50): Promise<OrderDocument[]> {
    const collection = this.getOrdersCollection();
    // Query ini berisi Shard Key Prefix (`tenantId`), sehingga HANYA mengenai Shard penyimpan Tenant tsb
    return await collection
      .find({ tenantId })
      .sort({ createdAt: -1 })
      .limit(limit)
      .toArray();
  }

  public async close(): Promise<void> {
    await this.client.close();
  }
}
```

### File: `src/index.ts`
```typescript
import { DistributedDatabaseClient, OrderDocument } from './ClusterManager';

async function main() {
  const uri = 'mongodb://localhost:27017/?appName=ShardingAppService';
  const cluster = new DistributedDatabaseClient(uri);

  try {
    await cluster.connect();
    await cluster.initializeShardingSchema();

    console.log('[LOAD] Inisialisasi Data Multi-Tenant...');
    const tenantIds = ['TENANT_CORP_ALPHA', 'TENANT_CORP_BETA', 'TENANT_CORP_GAMMA'];

    for (let i = 0; i < 300; i++) {
      const selectedTenant = tenantIds[i % tenantIds.length];
      const payload: OrderDocument = {
        tenantId: selectedTenant,
        orderId: `ORD-${Date.now()}-${i}`,
        userId: `USER-${Math.floor(Math.random() * 1000)}`,
        items: [
          { itemId: 'SKU-001', price: 100.5, quantity: 2 },
          { itemId: 'SKU-002', price: 49.9, quantity: 1 }
        ],
        totalAmount: 250.9,
        status: 'PAID',
        createdAt: new Date()
      };

      await cluster.insertOrder(payload);
    }

    console.log('[QUERY] Mengeksekusi Targeted Query...');
    const results = await cluster.findOrdersByTenant('TENANT_CORP_ALPHA', 5);
    console.log(`[QUERY SUCCESS] Ditemukan ${results.length} order untuk TENANT_CORP_ALPHA`);
  } catch (error) {
    console.error('[ERROR] Cluster operation failed:', error);
  } finally {
    await cluster.close();
  }
}

main();
```

---

## Seksi 09: Diagram Alur Kerja

### Eksekusi Query: Targeted vs Scatter-Gather

```
                                [ CLIENT QUERY ]
                                       |
                                       v
                                [ mongos ROUTER ]
                                       |
                   +-------------------+-------------------+
                   | Apakah query memiliki Shard Key?     |
                   +-------------------+-------------------+
                                       |
                   +-------------------+-------------------+
                   | YES                                   | NO
                   v                                       v
      [ TARGETED QUERY ]                         [ SCATTER-GATHER ]
   (Direct to Specific Shard)                 (Broadcast ke Seluruh Shard)
            |                                              |
            v                                              v
    +---------------+                             +---------------+---------------+
    | Shard 01 Only |                             | Shard 01      | Shard 02      |
    +---------------+                             +---------------+---------------+
            |                                              \             /
            | Fetch Data                                    \ Fetch Data/
            v                                                v         v
      [ Send Result ]                             [ Aggregasi/Sort di mongos ]
            |                                              |
            +----------------------+-----------------------+
                                   |
                                   v
                           [ RETURN TO CLIENT ]
```

---

## Seksi 10: Analisis Trade-offs

| Dimensi | Single Replica Set | Ranged Sharding | Hashed Sharding | Compound Sharding (Prefix Ranged + Hashed) |
| :--- | :--- | :--- | :--- | :--- |
| **Write Throughput** | Terbatas pada 1 Primary Node | Rentan bottleneck jika monotonik | Sangat Terdistribusi merata | Sangat Terdistribusi & Scalable |
| **Range Query Read** | Efisien via standard Index Scan | Sangat Optimal (Targeted ke 1-2 shard) | Buruk (Scatter-Gather ke semua shard) | Optimal jika menyertakan Prefix Key |
| **Complexity Ops** | Rendah | Tinggi (Perlu mitigasi Jumbo Chunks) | Sedang (Distribusi merata otomatis) | Sangat Tinggi (Perancangan index cermat) |
| **Max Database Size**| Terbatas kapasitas Disk Shard tunggal | Terdistribusi secara tak terbatas | Terdistribusi secara tak terbatas | Terdistribusi secara tak terbatas |

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices
* **Sertakan Shard Key pada Read Operations:** Selalu pastikan query analytical/transaksional kritis menyertakan Shard Key untuk mencegah degradasi performa akibat *Scatter-Gather*.
* **Manfaatkan Compound Shard Key:** Kombinasikan field dengan kardinalitas rendah/menengah (misal: `tenant_id`) dengan field kardinalitas tinggi yang di-hash (misal: `order_id: "hashed"`).
* **Jadwalkan Balancer Window:** Jalankan proses balancer saat low-traffic window untuk menghindari overhead transmisi I/O disk di jam sibuk produksi:
  ```javascript
  // Jalankan di mongos
  use config;
  db.settings.updateOne(
    { _id: "balancer" },
    { $set: { activeWindow: { start: "01:00", stop: "05:00" } } },
    { upsert: true }
  );
  ```

### Antipatterns
* **Monotonically Increasing Shard Key pada Ranged Sharding:** Menggunakan `ObjectId` atau `createdAt` murni sebagai Ranged Shard Key menyebabkan 100% traffic insert masuk ke chunk paling kanan (*MaxKey*) pada satu shard saja (*hot-spotting*).
* **Shard Key dengan Kardinalitas Rendah:** Melakukan sharding pada field seperti `status: "ACTIVE" | "INACTIVE"` atau `gender`. Hal ini menyebabkan chunk tumbuh melampaui limit tanpa bisa di-split (*Jumbo Chunks*).
* **Mengabaikan Shard Key Immutability Rules:** Mengasumsikan Shard Key bisa diganti dengan mudah tanpa perencanaan data patching/re-sharding pipeline.

---

## Seksi 12: Security Hardening

Dalam MongoDB Sharded Cluster, otentikasi internal antar-komponen (`mongos`, `mongod`, CSRS) adalah parameter paling rentan. Wajib digunakan otentikasi internal berbasis Keyfile atau X.509 Certificate.

### Generasi Keyfile Otentikasi Internal
```bash
# 1. Buat cryptographic keyfile
openssl rand -base64 756 > /tmp/mongo-cluster-keyfile.key
chmod 400 /tmp/mongo-cluster-keyfile.key
chown 999:999 /tmp/mongo-cluster-keyfile.key # UID MongoDB Docker Container
```

### Konfigurasi mongod.conf Shard/CSRS (Enforcing Auth)
```yaml
security:
  keyFile: /etc/mongodb-keyfile.key
  authorization: enabled

net:
  port: 27018
  bindIp: 0.0.0.0

sharding:
  clusterRole: shardsvr
```

### Konfigurasi mongos.conf (Router Security)
```yaml
security:
  keyFile: /etc/mongodb-keyfile.key

net:
  port: 27017
  bindIp: 0.0.0.0

sharding:
  configDB: rs-config/cfg01:27019
```

---

## Seksi 13: Observabilitas & Debugging

### Command Analisis Distribusi dan Query Router Diagnostics

```javascript
// 1. Eksekusi ringkasan topologi sharding
sh.status({ verbose: true });

// 2. Analisis eksekusi query (Apakah Scatter-Gather atau Targeted?)
// Hubungkan ke mongos, jalankan explain plan:
use enterprise_commerce;
db.orders.find({ tenantId: "TENANT_CORP_ALPHA" }).explain("executionStats");
// Periksa nilai output:
// Jika "SINGLE_SHARD", query bersifat TARGETED (Sangat Bagus).
// Jika "SHARD_MERGE" dengan banyak Shard Execution Stages, query bersifat SCATTER-GATHER.

// 3. Inspeksi status Balancer
sh.isBalancerRunning();
use config;
db.locks.find({ _id: "balancer" });

// 4. Monitoring riwayat migrasi chunk yang gagal atau sukses
db.changelog.find({ what: "moveChunk.commit" }).sort({ time: -1 }).limit(10);
```

---

## Seksi 14: Benchmarking & Performance

Untuk menguji skalabilitas linear dan throughput dari Sharded Cluster versus Single Instance, gunakan *MongoDB Cluster Benchmark Tool* (misalnya `YCSB` atau script load generator internal).

### Script Benchmark Sintetis (Concurrent Write Engine)
Eksekusi pengujian stres konkurensi menggunakan utilitas internal JavaScript:

```bash
docker exec -it mongos-router mongosh --port 27017 --eval '
const iterations = 50000;
const start = performance.now();

const bulk = db.getSiblingDB("benchmark_db").bench_coll.initializeUnorderedBulkOp();
for (let i = 0; i < iterations; i++) {
  bulk.insert({
    uuid: crypto.randomUUID(),
    sensor_id: (i % 1000),
    data_payload: "V1-READING-DATA-PAYLOAD-STREAM",
    timestamp: performance.now()
  });
}
bulk.execute();

const end = performance.now();
const latencySec = (end - start) / 1000;
const opsPerSec = iterations / latencySec;

print("==================================================");
print(`Total Operasi: ${iterations} records`);
print(`Waktu Eksekusi: ${latencySec.toFixed(2)} detik`);
print(`Throughput Write: ${opsPerSec.toFixed(2)} ops/sec`);
print("==================================================");
'
```

---

## Seksi 15: Hands-on Lab Mini-Project

### Skenario Proyek
Anda ditugaskan mendesain sistem ingest *IoT Fleet Telemetry* yang menerima jutaan data metrik GPS kendaraan per jam. Desain skema partisi yang menghindari hotspot pada node penerima dan memvalidasi isolasi query berdasarkan armada (`fleet_id`).

### Langkah-langkah Praktik

1. **Deploy Cluster Minimal:** Gunakan konfigurasi Docker dari Seksi 06.
2. **Desain Shard Key:**
   Kita pilih Compound Shard Key `{ fleet_id: 1, vin: "hashed" }`.
3. **Eksekusi Provisioning:**
```javascript
// Hubungkan ke mongos (Port 27017)
use telemetry_system;
sh.enableSharding("telemetry_system");

db.vehicle_metrics.createIndex({ fleet_id: 1, vin: "hashed" });
sh.shardCollection("telemetry_system.vehicle_metrics", { fleet_id: 1, vin: "hashed" });
```

4. **Injeksi Data Skala Besar:**
```javascript
use telemetry_system;
const sampleFleets = ["FLEET_AMAZON_US", "FLEET_DHL_EU", "FLEET_GOJEK_ID"];
const writeBatches = [];

for (let i = 0; i < 20000; i++) {
  writeBatches.push({
    fleet_id: sampleFleets[i % sampleFleets.length],
    vin: "VIN-XYZ-" + (i % 500),
    lat: -6.200000 + (Math.random() * 0.1),
    lng: 106.816666 + (Math.random() * 0.1),
    speed: Math.floor(Math.random() * 120),
    timestamp: new Date()
  });

  if (writeBatches.length === 1000) {
    db.vehicle_metrics.insertMany(writeBatches);
    writeBatches.length = 0;
  }
}
```

5. **Verifikasi Targeted Routing Execution:**
```javascript
const explainOutput = db.vehicle_metrics.find({
  fleet_id: "FLEET_GOJEK_ID",
  vin: "VIN-XYZ-10"
}).explain("executionStats");

print("Tipe Routing Query (stages): " + explainOutput.queryPlanner.winningPlan.stage);
// Validasi tidak adanya tahapan SHARD_MERGE multi-shard jika query sukses tertarget ke 1 shard
```

---

## Seksi 16: Automated Testing & Verification

Automated suite menggunakan standard Node.js assertions untuk menguji cluster routing behavior.

### File: `verify-cluster.test.ts`
```typescript
import { MongoClient } from 'mongodb';
import assert from 'node:assert/strict';
import { test, before, after } from 'node:test';

const ROUTER_URI = 'mongodb://localhost:27017';

test('Sharded Cluster Integrity & Targeted Routing Test Suite', async (t) => {
  let client: MongoClient;

  before(async () => {
    client = new MongoClient(ROUTER_URI);
    await client.connect();
  });

  after(async () => {
    await client.close();
  });

  await t.test('CSRS & Shards Detection Verification', async () => {
    const adminDb = client.db('admin');
    const result = await adminDb.command({ listShards: 1 });

    assert.ok(result.ok === 1, 'Command listShards must return ok: 1');
    assert.ok(result.shards.length >= 2, 'Cluster must contain at least 2 active shards');
  });

  await t.test('Verify Targeted vs Scatter-Gather Query Optimizer Plans', async () => {
    const db = client.db('telemetry_system');
    const collection = db.collection('vehicle_metrics');

    // 1. Query dengan Full Shard Key (Harus Targeted)
    const targetedExplain = await collection
      .find({ fleet_id: 'FLEET_GOJEK_ID', vin: 'VIN-XYZ-10' })
      .explain('executionStats');

    assert.strictEqual(
      targetedExplain.queryPlanner.winningPlan.stage === 'SHARD_MERGE' &&
      targetedExplain.queryPlanner.winningPlan.shards.length === 1 ||
      targetedExplain.queryPlanner.winningPlan.stage === 'SINGLE_SHARD',
      true,
      'Query with shard key prefix should only target a single shard'
    );

    // 2. Query tanpa Shard Key (Akan memicu Scatter-Gather ke multi-shard)
    const broadcastExplain = await collection
      .find({ speed: { $gt: 80 } })
      .explain('executionStats');

    assert.strictEqual(
      broadcastExplain.queryPlanner.winningPlan.stage,
      'SHARD_MERGE',
      'Query missing shard key must trigger SHARD_MERGE (Scatter-Gather)'
    );
  });
});
```

Jalankan pengujian via terminal:
```bash
npx ts-node verify-cluster.test.ts
```

---

## Seksi 17: Troubleshooting Guide

| Gejala Masalah | Investigasi Root Cause | Langkah Remediasi |
| :--- | :--- | :--- |
| **Hotspotting pada Shard Tertentu** (Satu Shard disk-nya penuh & I/O 100%) | Shard Key bernilai monoton (misal: auto-incrementing id atau ISODate murni). | Gunakan Compound Shard Key dengan komponen Hash atau lakukan `refineCollectionShardKey` di MongoDB 4.4+ untuk menambah prefix entropy. |
| **Peringatan *Jumbo Chunk*** pada log mongos | Kardinalitas nilai Shard Key sangat rendah, sehingga Balancer gagal memecah chunk (> 64MB). | 1. Naikkan chunk size sementara via `db.settings.updateOne()`.<br>2. Gunakan `refineCollectionShardKey` untuk menambahkan field unik ke shard key. |
| **Latensi Query Melonjak Tajam** | Aplikasi sering mengeksekusi query tanpa menyertakan Shard Key, memaksa *Scatter-Gather* ke puluhan shard. | 1. Tinjau *Slow Query Log* pada `mongos`.<br>2. Wajibkan query predikat menyertakan minimal prefix dari Shard Key. |
| **Koneksi `mongos` "HostUnreachable"** | Metadata CSRS desinkronisasi atau router kehilangan akses quorum ke Config Server. | 1. Periksa status Config Server Replica Set: `rs.status()` pada port 27019.<br>2. Pastikan CSRS memiliki anggota ganjil (minimal 3) untuk mempertahankan election quorum. |

---

## Seksi 18: Checklist Produksi

- [ ] Minimal 3 Node Config Server terdistribusi secara redundan dalam mode Replica Set (CSRS).
- [ ] Minimal 2 Shards, di mana masing-masing Shard merupakan Replica Set independen (1 Primary, 2 Secondaries).
- [ ] Aplikasi terhubung melalui minimal 2 Query Routers (`mongos`) di belakang Load Balancer TCP layer (misal: HAProxy/AWS NLB).
- [ ] Shard Key telah dianalisis: Memiliki Kardinalitas Tinggi, Frekuensi Tulis Merata, dan Mendukung Isolasi Query.
- [ ] Internal Authentication menggunakan **Keyfile** atau **x.509 certificates** terkonfigurasi di seluruh node cluster.
- [ ] Konfigurasi Balancer Window aktif hanya pada jam non-peak operasional sistem.
- [ ] Limit `maxPoolSize` pada client driver disesuaikan agar tidak membebani connection allocation pool `mongos` ke background shards.
- [ ] Alerting aktif untuk metrik *Jumbo Chunk count*, *Chunk Migration Failure rate*, dan *CSRS Replication Lag*.

---

## Seksi 19: Ringkasan Eksekutif
Horizontal Sharding adalah fondasi skalabilitas tanpa batas pada MongoDB. Keberhasilan implementasi sharding tidak terletak pada penambahan hardware, melainkan pada **pemilihan Shard Key yang tepat**. 

* **Hashed Sharding** menyelesaikan masalah write saturation secara merata ke semua shard, namun mengorbankan performa range query.
* **Ranged Sharding** memberikan optimasi luar biasa pada query rentang, tetapi rentan terhadap hotspotting data jika nilai key monoton.
* Pend