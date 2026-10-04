# BAB 02: High-Performance CRUD Operations & Bulk Execution
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis siklus hidup eksekusi I/O pada storage engine WiredTiger, termasuk alokasi read/write tickets, checkpointing, memory page eviction, dan Write-Ahead Logging (journaling).
*   Merancang dan mengimplementasikan operasi mutasi data massal berkinerja tinggi menggunakan `bulkWrite` API (ordered vs. unordered) dengan penanganan parsial failure yang deterministik dan idempoten.
*   Mengonfigurasi dan mengoptimalkan primitif konsistensi terdistribusi: *Write Concern* (`w`, `j`, `wtimeout`) dan *Read Concern* (`local`, `available`, `majority`, `linearizable`, `snapshot`) sesuai teorema CAP.
*   Menghilangkan bottleneck *network round-trip time* (RTT) dan *lock contention* pada ingestion pipeline throughput tinggi (>50.000 ops/sec).
*   Mengimplementasikan strategi cursor streaming, batch sizing, dan backpressure handling pada dataset berukuran terabyte tanpa memicu degradasi memori heap pada aplikasi maupun storage engine WiredTiger.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
*   Topologi dasar MongoDB Replica Set (Primary, Secondary, Arbiter) dan mekanisme pemilihan leader (Raft-variant consensus).
*   Struktur format data BSON dan batasan dokumen 16 MB.
*   Pemrograman backend asinkron tingkat lanjut (Node.js/TypeScript, Go, atau Java) serta pengelolaan socket pool.
*   Konsep isolasi transaksi ACID dan pemahaman dasar *concurrency control* (Multi-Version Concurrency Control / MVCC, two-phase locking).

---

### 3. Concept & Internal Architecture (Mendalam)

Performa operasi CRUD MongoDB tidak ditentukan semata oleh query BSON, melainkan oleh interaksi antara Mongo Driver, layer routing/eksekusi `mongod`, concurrency control tickets, dan storage engine WiredTiger.

```
+-------------------------------------------------------------------------------+
|                               APPLICATION TIER                                |
|  Node.js / Go Driver (Connection Pool, BSON Serializer, Command Batcher)      |
+---------------------------------------+---------------------------------------+
                                        | Socket Stream (OP_MSG Protocol)
                                        v
+-------------------------------------------------------------------------------+
|                           MONGOD INSTANCE LAYER                               |
|  +-------------------------------------------------------------------------+  |
|  | Network Interface & Worker Threads (ServiceExecutor: Synchronous/Kqueue)|  |
|  +------------------------------------+------------------------------------+  |
|                                       |                                       |
|  +------------------------------------v------------------------------------+  |
|  | Ticket Allocation Subsystem (Default: 128 Read / 128 Write Tickets)     |  |
|  +------------------------------------+------------------------------------+  |
|                                       |                                       |
|  +------------------------------------v------------------------------------+  |
|  | Concurrency Control & Lock Manager (Global, DB, Coll, Document-level IX)|  |
|  +------------------------------------+------------------------------------+  |
+---------------------------------------|---------------------------------------+
                                        v
+-------------------------------------------------------------------------------+
|                         WIREDTIGER STORAGE ENGINE                             |
|  +-------------------------------------------------------------------------+  |
|  | WiredTiger Cache Pool (RAM)                                             |  |
|  | - MVCC Memory Pages (Clean Pages & Dirty Pages)                         |  |
|  | - Eviction Server (Threads target: Clean/Evict when dirty > 5% or 20%)  |  |
|  +--------------------+------------------------------+---------------------+  |
|                       |                              |                        |
|        Checkpoint     | (Every 60s                   | Journal Flush          |
|        Snapshot Engine|  or 2GB log)                 | (WAL - Every 100ms     |
|                       |                              |  or j:true)            |
|                       v                              v                        |
|  +--------------------+-------+              +-------+---------------------+  |
|  | OS File System Cache       |              | OS File System Cache        |  |
|  | (Data Files: collection*.wt|              | (WiredTigerLog.*)           |  |
|  +--------------------+-------+              +-------+---------------------+  |
|                       | fdatasync                    | fdatasync              |
|                       v                              v                        |
|  +--------------------+------------------------------+---------------------+  |
|  |              NVMe SSD / Persistent Block Storage                        |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
```

#### 3.1. WiredTiger Concurrency & Execution Flow
Ketika client mengirimkan operasi mutasi dokumen:
1. **Connection & Serialization**: Driver mengemas dokumen ke dalam wire protocol `OP_MSG`. Driver melakukan serialisasi representasi objek internal ke stream raw binary BSON.
2. **Ticket Allocation**: Operasi memasuki antrean eksekusi `mongod`. WiredTiger menerapkan sistem semafor berbasis tiket (secara default 128 *read tickets* dan 128 *write tickets*). Jika kapasitas tiket habis akibat query/mutasi yang lambat, request baru akan dialihkan ke status antrean (*ticket starvation*), meningkatkan latensi secara eksponensial.
3. **Lock Acquisition**: Operasi meminta Intent Locks (`IX` untuk writes, `IS` untuk reads) pada level Global, Database, dan Collection. Karena WiredTiger menggunakan konkurensi tingkat dokumen (*document-level concurrency*), lock eksklusif (`X`) pada level dokumen dikelola via MVCC di internal storage engine.
4. **Memory Mutation (Dirty Page Allocation)**: Data diubah dalam WiredTiger Cache. Operasi ini tidak langsung menyentuh disk fisik. Halaman memori B-Tree yang dimodifikasi ditandai sebagai *Dirty Page*.
5. **Write-Ahead Logging (Journaling)**: Modifikasi dicatat pada struktur data in-memory journal buffer. Bergantung pada konfigurasi `j` (Journal) pada *Write Concern*, buffer ini disinkronkan ke file `WiredTigerLog` di disk menggunakan system call `fdatasync`.
6. **Checkpoints & Eviction**:
   * **Eviction Server**: Thread latar belakang bertugas menjaga utilisasi cache WiredTiger (default: 50% RAM fisik minus 1 GB). Jika persentase dirty page melebihi threshold tertentu (misal: 20%), thread client akan dipaksa ikut melakukan eviksi memori, menyebabkan fenomena *application stalls*.
   * **Checkpoint Engine**: Setiap 60 detik (default) atau saat ukuran log mencapai 2 GB, WiredTiger membuat snapshot konsisten dari seluruh database ke disk, mengubah dirty pages menjadi checkpoint yang persisten dan memotong (*truncate*) log journal lama.

#### 3.2. Bulk Execution Architecture
Eksekusi operasi tunggal (`insertOne`, `updateOne`) menimbulkan overhead jaringan round-trip berulang kali. `bulkWrite` mengeliminasi overhead ini melalui batching pada level protokol.
* **Driver-side Packetization**: Driver secara transparan memecah array operasi menjadi batch-batch dengan ukuran maksimal $N = 100.000$ operasi atau total payload maksimal 48 MB per pesan jaringan `OP_MSG`.
* **Ordered vs. Unordered Processing Pipeline**:
  * **Ordered (`ordered: true`)**: `mongod` mengeksekusi operasi secara sekuensial sesuai urutan array. Jika terjadi kegagalan (misalnya, duplikasi indeks unik pada item ke-42), engine **menghentikan seketika** eksekusi sisa operasi. Operasi ke-43 hingga $N$ dibatalkan (*short-circuiting*).
  * **Unordered (`ordered: false`)**: `mongod` bebas mereorganisasi urutan operasi, membaginya ke beberapa worker thread internal secara paralel. Jika terjadi kegagalan pada salah satu item, engine mencatat error tersebut dalam array `writeErrors` dan **tetap melanjutkan eksekusi** seluruh operasi yang tersisa hingga selesai.

---

### 4. Why & What

| Dimensi | Pendekatan Individual CRUD Tradisional | High-Performance Bulk Operations (`bulkWrite`) |
| :--- | :--- | :--- |
| **Network Overhead** | $O(N)$ Round-Trip Times (RTT). 1.000 insert = 1.000 network round-trips. | $O(\lceil N / 100.000 \rceil)$ RTT. 1.000 insert = 1 network message round-trip. |
| **Ticket Contention** | Alokasi dan pelepasan tiket WiredTiger terjadi $N$ kali berturut-turut. | Tiket dialokasikan dan dioptimalkan dalam eksekusi batch terpusat. |
| **Journal Flush Amplification** | Jika `j: true`, disk storage dipaksa melakukan $N$ kali sinkronisasi `fdatasync`. | Operasi batch dapat diagregasi dalam satu kali sinkronisasi I/O log (`fdatasync`). |
| **Throughput Degradation** | Dibatasi oleh latensi jaringan (*network-bound*), rata-rata 500 - 2.000 ops/sec. | Dibatasi oleh kapasitas CPU dan disk I/O (*resource-bound*), mampu mencapai >50.000 - 150.000 ops/sec. |

#### Kapan Menggunakan Primitif Konsistensi Khusus:
* **Write Concern**:
  * `w: 1`: Ack hanya dari Primary node (default). Resiko kehilangan data jika Primary mengalami crash sebelum replikasi oplog.
  * `w: "majority"`: Ack dikirimkan setelah data tertulis pada kuorum replica set. Esensial untuk integritas finansial dan sistem ledger.
  * `j: true`: Menjamin data tertulis di non-volatile storage (disk journal) sebelum mengembalikan respon ack ke driver.
* **Read Concern**:
  * `local` / `available`: Mengembalikan data terkini dari node target tanpa jaminan apakah data telah direplikasi ke kuorum. Resiko *dirty reads* jika terjadi rollback.
  * `majority`: Hanya membaca data yang telah dikonfirmasi oleh kuorum replica set. Menjamin data tidak akan mengalami rollback.
  * `snapshot`: Membaca data berdasarkan snapshot checkpoint transaksi tertentu. Wajib digunakan dalam *Multi-Document Transactions*.

---

### 5. How: Workflow Detail

Workflow eksekusi produksi yang optimal untuk high-throughput ingestion pipeline:

```
[Incoming Payload Stream]
          |
          v
[1. Application Ingestion Buffer]
          |
          +--> Accumulate until: Size >= 2.000 docs OR Time >= 50ms
          |
          v
[2. Payload Normalization & Idempotency Generation]
          |
          +--> Inject deterministic deterministic `_id` / idempotent update operators ($set, $setOnInsert)
          |
          v
[3. Driver Bulk Command Assembly]
          |
          +--> bulkWrite(operations, { ordered: false, writeConcern: { w: "majority", wtimeout: 5000 } })
          |
          v
[4. Transport via Connection Pool]
          |
          +--> Wire Protocol OP_MSG -> mongod Primary Node
          |
          v
[5. WiredTiger Execution Engine]
          |
          +--> Parallel Document Mutation -> WiredTiger Cache
          +--> Write to In-Memory Journal -> Oplog Generation
          |
          v
[6. Response Parsing & Partial Failure Interception]
          |
         / \
   Error?   Success?
    /         \
   v           v
[Extract]     [Commit Metric]
writeErrors
   |
   +--> Filter: Duplicate Keys (E11000) -> Log as idempotent bypass
   +--> Filter: Transient Errors (WriteConflict) -> Route to Exponential Backoff Dead-Letter Queue
```

---

### 6. Analogy & ASCII Diagram

Bayangkan sebuah pelabuhan logistik internasional.

* **Individual CRUD**: Sebuah truk kontainer dikirim melintasi jembatan tol (jaringan/RTT) hanya untuk membawa satu paket parsel kecil. Petugas loket pelabuhan (WiredTiger Ticket) harus memeriksa paspor pengemudi untuk setiap parsel. Jika ada 10.000 parsel, jembatan tol macet total dan petugas loket kelelahan (*ticket exhaustion*).
* **High-Performance Bulk Operations**: 10.000 paket dikemas rapi ke dalam satu peti kemas raksasa di pusat distribusi. Satu truk membawanya melintasi jembatan tol dalam satu kali perjalanan. Petugas loket pelabuhan cukup memvalidasi dokumen manifes peti kemas satu kali, lalu crane pelabuhan membongkar dan mendistribusikan isi kontainer secara paralel ke dermaga.

```
Individual CRUD Pattern:
Client -------- [Doc 1] --------> mongod (Lock -> Ticket -> Write -> Ack)
Client <------- [Ack 1] --------- mongod
Client -------- [Doc 2] --------> mongod (Lock -> Ticket -> Write -> Ack)
Client <------- [Ack 2] --------- mongod
(Total Latency = N * (Network RTT + Server Time))

Bulk Ingestion Pattern:
Client -------- [Doc 1, Doc 2, ... Doc N] --------> mongod
                                                    |-- Worker 1: Mutate Doc 1..K
                                                    |-- Worker 2: Mutate Doc K+1..M
                                                    |-- Worker 3: Mutate Doc M+1..N
Client <--- [Summary: N Success, Errors[]] ------- mongod
(Total Latency = 1 * Network RTT + Batch Engine Time)
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Ordered vs. Unordered Behavior
Contoh dasar demonstrasi determinisme error pada Node.js/TypeScript driver.

```typescript
import { MongoClient } from 'mongodb';

async function demonstrateBulkMechanics() {
  const client = new MongoClient('mongodb://localhost:27017');
  await client.connect();
  const db = client.db('test_db');
  const collection = db.collection('bulk_demo');

  await collection.drop().catch(() => {});
  await collection.createIndex({ sku: 1 }, { unique: true });

  // Dataset uji dengan intentional duplicate key pada elemen index ke-1
  const operations = [
    { insertOne: { document: { sku: 'PROD-A', price: 100 } } },
    { insertOne: { document: { sku: 'PROD-A', price: 200 } } }, // Duplicate Key Error
    { insertOne: { document: { sku: 'PROD-B', price: 300 } } }
  ];

  // 1. Eksekusi ORDERED
  console.log('--- Menjalankan Ordered Bulk Write ---');
  try {
    await collection.bulkWrite(operations, { ordered: true });
  } catch (error: any) {
    console.error('Ordered failed at operation index:', error.result?.getWriteErrors()[0]?.index);
    // Hasil: Index ke-1 gagal, PROD-B (index 2) TIDAK PERNAH diproses
  }
  const countAfterOrdered = await collection.countDocuments();
  console.log('Jumlah dokumen tersimpan (Ordered):', countAfterOrdered); // Output: 1

  // Cleanup
  await collection.deleteMany({});

  // 2. Eksekusi UNORDERED
  console.log('\n--- Menjalankan Unordered Bulk Write ---');
  try {
    await collection.bulkWrite(operations, { ordered: false });
  } catch (error: any) {
    console.error('Unordered caught errors total:', error.result?.getWriteErrors().length);
    // Hasil: Index ke-1 gagal, namun PROD-B (index 2) TETAP diproses dan berhasil disimpan
  }
  const countAfterUnordered = await collection.countDocuments();
  console.log('Jumlah dokumen tersimpan (Unordered):', countAfterUnordered); // Output: 2

  await client.close();
}

demonstrateBulkMechanics().catch(console.error);
```

#### 7.2. Practical Example: Enterprise Ingestion Pipeline dengan Idempotensi & Backpressure
Implementasi pipeline konsumsi data berskala enterprise menggunakan streaming chunks, error handling spesifik, rate limiting adaptif, dan konfigurasi *Write Concern* berketahanan tinggi.

```typescript
import { MongoClient, AnyBulkWriteOperation, MongoBulkWriteError } from 'mongodb';
import { EventEmitter } from 'events';

interface TelemetryPayload {
  deviceId: string;
  timestamp: Date;
  metrics: {
    cpuTemperature: number;
    voltage: number;
  };
}

interface IngestionStats {
  processed: number;
  successful: number;
  duplicatesBypassed: number;
  failedFatal: number;
}

export class ResilientBulkIngestionEngine extends EventEmitter {
  private client: MongoClient;
  private isRunning: boolean = false;

  constructor(mongoUri: string) {
    super();
    this.client = new MongoClient(mongoUri, {
      maxPoolSize: 50,
      minPoolSize: 10,
      retryWrites: true,
      w: 'majority',
      wtimeoutMS: 5000,
    });
  }

  public async init(): Promise<void> {
    await this.client.connect();
    const db = this.client.db('telemetry_core');
    // Compound Unique Index untuk menjamin idempotensi
    await db.collection('device_events').createIndex(
      { deviceId: 1, timestamp: 1 },
      { unique: true, background: true }
    );
  }

  public async processBatch(
    payloads: TelemetryPayload[],
    batchSize: number = 2000
  ): Promise<IngestionStats> {
    const db = this.client.db('telemetry_core');
    const collection = db.collection('device_events');
    const stats: IngestionStats = { processed: 0, successful: 0, duplicatesBypassed: 0, failedFatal: 0 };

    for (let i = 0; i < payloads.length; i += batchSize) {
      const chunk = payloads.slice(i, i + batchSize);
      
      // Transform data mentah menjadi operasi Update Upsert Idempoten
      const operations: AnyBulkWriteOperation<any>[] = chunk.map((payload) => ({
        updateOne: {
          filter: {
            deviceId: payload.deviceId,
            timestamp: payload.timestamp,
          },
          update: {
            $setOnInsert: {
              deviceId: payload.deviceId,
              timestamp: payload.timestamp,
            },
            $set: {
              metrics: payload.metrics,
              ingestedAt: new Date(),
            },
          },
          upsert: true,
        },
      }));

      stats.processed += operations.length;

      try {
        const result = await collection.bulkWrite(operations, {
          ordered: false, // Eksekusi konkuren di internal storage engine
          writeConcern: {
            w: 'majority',
            wtimeout: 5000,
          },
        });

        stats.successful += (result.upsertedCount + result.modifiedCount);
      } catch (error: any) {
        if (error instanceof MongoBulkWriteError) {
          const writeErrors = error.writeErrors;
          let unhandledErrors = 0;

          for (const writeError of writeErrors) {
            // E11000: Duplicate key error (terjadi jika ada race condition pada upsert)
            if (writeError.code === 11000) {
              stats.duplicatesBypassed++;
            } else {
              unhandledErrors++;
              this.emit('error:record', {
                index: writeError.index,
                code: writeError.code,
                message: writeError.errmsg,
              });
            }
          }

          stats.failedFatal += unhandledErrors;
          // Kalkulasi mutasi yang tetap berhasil di luar batch error
          if (error.result) {
            stats.successful += (error.result.nUpserted + error.result.nModified);
          }
        } else {
          // Tangani driver error atau failover cluster (network drop / election)
          this.emit('error:fatal', error);
          throw error;
        }
      }
    }

    return stats;
  }

  public async close(): Promise<void> {
    await this.client.close();
  }
}
```

---

### 8. Real World Case Study: E-Commerce Flash Sale Financial Ledger Reconciliation

#### Skenario Arsitektur Produksi
Platform e-commerce tier-1 menyelenggarakan flash sale berskala masif. Sistem checkout menghasilkan 300.000 mutasi transaksi per menit yang ditampung sementara pada Apache Kafka. Service akuntansi bertugas melakukan sinkronisasi dan rekonsiliasi data dari Kafka ke cluster MongoDB Replica Set (3 node: 1 Primary, 2 Secondary; node spec: 32 vCPU, 128 GB RAM, NVMe SSD).

#### Bottleneck Awal yang Ditemukan
Arsitektur awal mengeksekusi mutasi menggunakan `updateOne({ orderId }, { $set: updateData }, { upsert: true })` secara individual per thread event listener Kafka. 
Akibatnya:
1. **Ticket Exhaustion**: Server MongoDB mengalami lonjakan koneksi hingga mencapai limit 128 Write Tickets WiredTiger secara kontinu. Metrik `db.serverStatus().wiredTiger.concurrentTransactions.write.out` mencapai nilai 128 konstan.
2. **Latensi Melambung**: Rata-rata response latency melonjak dari 4 ms menjadi 1.450 ms per transaksi.
3. **Queue Bloat**: Kafka Consumer lag menembus 2,5 juta pesan yang belum diproses, mengancam status konsistensi pembukuan finansial perusahaan.

#### Analisis Akar Masalah (Root Cause Analysis)
* Tingginya Network RTT akibat model komputasi diskrit ($300.000 \times \text{RTT per menit}$).
* WiredTiger Cache dipenuhi oleh thread context yang tertahan menunggu pelepasan tiket transaksi lama yang belum memperoleh alokasi commit log I/O disk.
* Oplog processing pada node Secondary tertinggal jauh (*replication lag* menembus 450 detik) karena Primary membombardir jutaan entri oplog individual berukuran kecil.

#### Solusi Implementasi
1. **Refaktor ke Unordered Bulk API**:
   Merestrukturisasi consumer Kafka untuk mengumpulkan pesan ke buffer in-memory berukuran $2.500$ item atau toleransi interval windowing maksimum $100\text{ ms}$ (mana yang tercapai lebih dulu). Seluruh buffer dikirimkan menggunakan `bulkWrite` dengan opsi `ordered: false`.
2. **Optimalisasi Write Concern & Read Concern**:
   Pipa penulisan dikonfigurasi menggunakan Write Concern `w: "majority", wtimeoutMS: 3000`. Penggunaan majority memastikan transaksi ledger tidak hilang saat failover terjadi, sedangkan `wtimeoutMS` mencegah thread tertahan selamanya apabila secondary node sedang mengalami resinkronisasi.
3. **Penyelarasan Chunk Size dengan Kapasitas Cache**:
   Ukuran batch 2.500 dokumen (~1,2 MB total data BSON per batch) dipilih untuk mencegah alokasi memori berlebih yang dapat memicu thread eviksi agresif di storage engine WiredTiger.

#### Hasil Evaluasi Kinerja Pasca Implementasi
* **Throughput Write**: Meningkat dari 2.100 ops/sec menjadi 58.000 ops/sec.
* **Penggunaan Tiket WiredTiger**: Rata-rata utilisasi tiket turun drastis ke angka 15–25 tiket aktif secara konsisten.
* **Waktu Rekonsiliasi**: Kafka consumer lag tereliminasi sepenuhnya; waktu pemrosesan backlog dari 2,5 juta pesan terpangkas dari estimasi 4 jam menjadi hanya 43 detik.
* **Replication Lag**: Stabil di bawah 500 ms di kedua node Secondary karena Secondary dapat melakukan replikasi batch secara efisien via batch application threads pada oplog buffer.

---

### 9. Trade-offs

| Parameter/Arsitektur | Pendekatan Terpilih | Keuntungan (Pros) | Konsekuensi & Kerugian (Cons) | Rekomendasi Beban Kerja |
| :--- | :--- | :--- | :--- | :--- |
| **Execution Order** | `ordered: true` | Menjamin integritas urutan mutasi data secara sekuensial. Pemrosesan deterministik. | Performa rendah. Gagal instan pada error pertama (*short-circuiting*); sisa batch terbuang. | State Machine transitions, log audit berbasis sequence. |
| | `ordered: false` | Throughput maksimal. Eksekusi paralel multi-thread internal WiredTiger. Tetap memproses item lain walau ada record error. | Urutan mutasi acak. Tidak cocok untuk transaksi yang bergantung pada urutan operasi sebelumnya. | Event streaming, log analytics, data hydration batch, IoT telemetry. |
| **Write Concern** | `w: 1, j: false` | Latensi penulisan terendah (<1 ms). CPU dan disk overhead minimal. | Resiko kehilangan data (*data loss*) jika node Primary crash sebelum sync disk atau replikasi oplog. | Telemetry mentah, data tracking clickstream, cache sementara. |
| | `w: "majority", j: true` | *Strict Durability*. Data dijamin selamat dari node crash maupun partition event. Rollback zero-risk. | Latensi meningkat signifikan karena menunggu flush I/O SSD dan replikasi jaringan antar-node. | Transaksi finansial, order processing, data kepemilikan aset. |
| **Batch Chunk Sizing** | Kecil (100–500 docs) | Latensi respons individual batch cepat. Alokasi memori aplikasi sangat kecil. | Total throughput agregat lebih rendah akibat tingginya overhead network packet framing. | Sistem interaktif real-time dengan volume fluktuatif rendah. |
| | Besar (>10.000 docs) | Throughput per detik tinggi. Pemanfaatan buffer jaringan optimal. | Resiko memicu lonjakan dirty pages di WiredTiger Cache yang menyebabkan *application freeze* akibat eviksi darurat. | Offline data loading, database migrations, nightly sync ETL. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal Umum dalam Produksi
1. **Unbounded Batch Payload (Melanggar Limit 16 MB/48 MB)**:
   * *Kesalahan*: Memasukkan 100.000 dokumen besar ke dalam satu array tanpa memperhatikan batasan paket MongoDB. Meskipun driver modern membagi batch secara otomatis, array raksasa pada level runtime dapat menyebabkan *Out of Memory (OOM)* pada heap aplikasi Node.js/Java.
   * *Solusi*: Terapkan chunking adaptif pada level aplikasi dengan batas maksimal 2.000–5.000 dokumen per eksekusi `bulkWrite`.
2. **Mengabaikan Parameter `wtimeoutMS` pada Write Concern `w: "majority"`**:
   * *Kesalahan*: Mengirim operasi majority write tanpa timeout. Jika salah satu secondary down dan kourum terganggu, request client akan menggantung tanpa batas (*infinite hang*), memakan connection pool hingga exhaust.
   * *Solusi*: Wajib menyematkan opsi `wtimeoutMS` (misal: 3000–5000 ms) di setiap mutasi mayoritas.
3. **Unindexed Field pada Bulk Update/Delete**:
   * *Kesalahan*: Menjalankan `bulkWrite` berisi ribuan instruksi `updateOne` di mana query `filter` tidak didukung oleh indeks yang tepat.
   * *Solusi*: Akibatnya terjadi *Collection Scan (COLLSCAN)* pada setiap item di dalam batch, melumpuhkan seluruh tiket CPU WiredTiger secara instan. Pastikan field kriteria filter memiliki indeks spesifik (*Covered Index* atau *Point Lookup*).

#### 10.2. Troubleshooting Runbook: WiredTiger Ticket Saturation & High Latency

##### Gejala:
Aplikasi melaporkan `MongoServerSelectionError` atau `MongoTimeoutException`. Latensi operasi database meningkat tajam dari 5 ms menjadi ribuan ms.

##### Investigasi Langkah demi Langkah:
1. **Periksa Ketersediaan Tiket WiredTiger**:
   Jalankan perintah ini di `mongosh`:
   ```javascript
   db.serverStatus().wiredTiger.concurrentTransactions
   ```
   *Output diagnostik*:
   ```json
   {
     "write": {
       "out": 128,          // Tiket yang sedang digunakan (habis jika mencapai nilai max)
       "available": 0,      // Tiket tersisa
       "totalTickets": 128  // Kapasitas default tiket
     },
     "read": {
       "out": 4,
       "available": 124,
       "totalTickets": 128
     }
   }
   ```
   Jika `write.available` bernilai `0`, server sedang mengalami *Write Ticket Exhaustion*.

2. **Deteksi Operasi yang Memonopoli Tiket**:
   Jalankan profiling `currentOp` untuk mendeteksi query yang menahan lock dalam durasi abnormal:
   ```javascript
   db.currentOp({
     "active": true,
     "secs_running": { "$gt": 2 },
     "waitingForLock": false
   })
   ```
   Identifikasi apakah terdapat operasi `update` atau `remove` masif tanpa indeks (`planSummary: "COLLSCAN"`).

3. **Periksa Status Dirty Memory pada WiredTiger Cache**:
   ```javascript
   db.serverStatus().wiredTiger.cache["tracked dirty bytes in the cache"]
   ```
   Jika angka ini melebihi 20% dari total WiredTiger memory, WiredTiger mengaktifkan mode *client-assisted eviction*, di mana thread client dipaksa menulis dirty page ke disk sebelum request-nya diproses.

##### Tindakan Mitigasi Darurat:
* Matikan operasi pembuat bottleneck secara selektif menggunakan `db.killOp(<opId>)`.
* Turunkan ukuran chunk batch ingestion pada service client dari 5.000 menjadi 1.000 record.
* Tingkatkan batas write tickets secara dinamis jika spesifikasi CPU dan sistem IOPS disk storage masih memiliki headroom:
  ```javascript
  db.adminCommand({ setParameter: 1, wiredTigerConcurrentWriteTransactions: 256 })
  ```

---

### 11. Best Practices (Production Checklist)

* [ ] **Batch Sizing**: Batasi ukuran array `bulkWrite` antara 1.000 hingga 5.000 operasi per batch untuk mengoptimalkan efisiensi memory transfer vs latensi per proses.
* [ ] **Terapkan Unordered Execution**: Gunakan `{ ordered: false }` kecuali sistem secara mutlak membutuhkan integritas urutan sekuensial antar operasi.
* [ ] **Konfigurasi `wtimeoutMS`**: Jangan pernah mendefinisikan Write Concern `w: "majority"` tanpa menyertakan `wtimeoutMS` eksplisit (rekomendasi: 3.000–5.000 ms).
* [ ] **Idempotensi Dokumen Mutasi**: Gunakan operator `$set`, `$setOnInsert`, dan pastikan terdapat indeks unik (`unique index`) yang mendasari kriteria upsert filter untuk mencegah dokumen ganda.
* [ ] **Indeks Sebelum Ingest**: Pastikan semua indeks yang diperlukan sudah ada sebelum memulai load data masif. Jika melakukan initial data load berskala miliaran record, buat indeks *setelah* load data selesai.
* [ ] **Monitoring Ticket & Dirty Cache**: Pasang alerting metrik Datadog/Prometheus untuk parameter `wiredTiger.concurrentTransactions.write.out > 100` dan `wiredTiger.cache.tracked dirty bytes > 20%`.
* [ ] **Hindari Long-Running Cursor**: Set batasan pagination atau gunakan tailable cursors secara berhati-hati; atur `batchSize(1000)` pada cursor baca berskala besar untuk menghindari *socket read timeouts*.
* [ ] **Connection Pool Scaling**: Sesuaikan `maxPoolSize` pada driver aplikasi. Mengatur `maxPoolSize` terlalu tinggi (misal: >500) pada banyak instance microservice dapat mempercepat terjadinya *ticket starvation* di node `mongod`.

---

### 12. Hands-on Practice: Simulasi & Penanganan High-Throughput Bulk Ingest

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Environment Reproduksi
Siapkan replica set lokal menggunakan Docker Compose.

```yaml
# hands-on/m02/docker-compose.yaml
version: '3.8'
services:
  mongo-primary:
    image: mongo:7.0
    container_name: mongo-primary
    command: ["--replSet", "rs0", "--bind_ip_all", "--oplogSize", "1024"]
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db

volumes:
  mongo-data:
```

Jalankan container dan inisialisasi replica set:
```bash
docker compose up -d
docker exec -it mongo-primary mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'localhost:27017'}]})"
```

#### Langkah 2: Setup Project TypeScript
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install mongodb typescript @types/node tsx
npx tsc --init
```

#### Langkah 3: Implementasi Script Benchmark Performa
Buat file `hands-on/m02/benchmark.ts` untuk membandingkan performa Individual Writes vs. Ordered BulkWrite vs. Unordered BulkWrite.

```typescript
// hands-on/m02/benchmark.ts
import { MongoClient, AnyBulkWriteOperation } from 'mongodb';

const URI = 'mongodb://localhost:27017/?replicaSet=rs0';
const TOTAL_RECORDS = 20_000;
const BATCH_SIZE = 2_000;

async function runBenchmark() {
  const client = new MongoClient(URI);
  await client.connect();
  const db = client.db('benchmark_db');
  const collection = db.collection('transactions');

  console.log(`=== Memulai Benchmark: Ingestion ${TOTAL_RECORDS} Rekod ===\n`);

  // 1. Benchmark Individual Writes (Sampel 2.000 rekod agar tidak memakan waktu terlalu lama)
  await collection.drop().catch(() => {});
  const sampleCount = 2000;
  console.log(`1. Menjalankan Individual insertOne (${sampleCount} records)...`);
  const startIndividual = Date.now();
  for (let i = 0; i < sampleCount; i++) {
    await collection.insertOne({
      txnId: `TXN-IND-${i}`,
      amount: Math.random() * 1000,
      timestamp: new Date()
    });
  }
  const timeIndividual = (Date.now() - startIndividual) / 1000;
  const tpsIndividual = (sampleCount / timeIndividual).toFixed(2);
  console.log(`Hasil: Waktu = ${timeIndividual}s | TPS = ${tpsIndividual} ops/sec\n`);

  // 2. Benchmark Ordered BulkWrite
  await collection.drop().catch(() => {});
  console.log(`2. Menjalankan Ordered bulkWrite (${TOTAL_RECORDS} records, Batch Size: ${BATCH_SIZE})...`);
  const startOrdered = Date.now();
  for (let i = 0; i < TOTAL_RECORDS; i += BATCH_SIZE) {
    const ops: AnyBulkWriteOperation<any>[] = [];
    for (let j = 0; j < BATCH_SIZE; j++) {
      const idx = i + j;
      ops.push({
        insertOne: {
          document: { txnId: `TXN-ORD-${idx}`, amount: Math.random() * 1000, timestamp: new Date() }
        }
      });
    }
    await collection.bulkWrite(ops, { ordered: true });
  }
  const timeOrdered = (Date.now() - startOrdered) / 1000;
  const tpsOrdered = (TOTAL_RECORDS / timeOrdered).toFixed(2);
  console.log(`Hasil: Waktu = ${timeOrdered}s | TPS = ${tpsOrdered} ops/sec\n`);

  // 3. Benchmark Unordered BulkWrite
  await collection.drop().catch(() => {});
  console.log(`3. Menjalankan Unordered bulkWrite (${TOTAL_RECORDS} records, Batch Size: ${BATCH_SIZE})...`);
  const startUnordered = Date.now();
  for (let i = 0; i < TOTAL_RECORDS; i += BATCH_SIZE) {
    const ops: AnyBulkWriteOperation<any>[] = [];
    for (let j = 0; j < BATCH_SIZE; j++) {
      const idx = i + j;
      ops.push({
        insertOne: {
          document: { txnId: `TXN-UNORD-${idx}`, amount: Math.random() * 1000, timestamp: new Date() }
        }
      });
    }
    await collection.bulkWrite(ops, { ordered: false });
  }
  const timeUnordered = (Date.now() - startUnordered) / 1000;
  const tpsUnordered = (TOTAL_RECORDS / timeUnordered).toFixed(2);
  console.log(`Hasil: Waktu = ${timeUnordered}s | TPS = ${tpsUnordered} ops/sec\n`);

  await client.close();
}

runBenchmark().catch(console.error);
```

Jalankan pengujian:
```bash
npx tsx benchmark.ts
```

---

### 13. Exercises

#### 13.1. Level Easy: Filtered Batch Purge
* **Tantangan**: Buat script yang membersihkan entri log yang berumur lebih dari 30 hari secara batch menggunakan `bulkWrite` delete operations dengan chunking maksimum 5.000 dokumen per eksekusi untuk mencegah penguncian resource database secara tiba-tiba.
* **Kriteria Keberhasilan**: Script tidak menggunakan `deleteMany({})` secara langsung, melainkan menggunakan cursor looping dengan chunked deletions via `bulkWrite` untuk menjaga ketersediaan tiket engine.

#### 13.2. Level Medium: Mixed Bulk Operations dengan Upsert Tracking
* **Tantangan**: Buat pipeline sinkronisasi profil pengguna e-commerce. Input data berupa array JSON yang berisi gabungan antara data registrasi baru (`insertOne`), pembaruan profil status (`updateOne`), dan penghapusan akun (`deleteOne`). 
* **Kriteria Keberhasilan**: Eksekusi dilakukan dalam satu pemanggilan `bulkWrite(..., { ordered: false })`. Ekstrak dan cetak secara terpisah: total inserted, total updated, total upserted, total deleted, dan mapping index array terhadap data yang gagal tanpa menghentikan eksekusi batch.

#### 13.3. Level Hard: Real-Time Stream Ingestion dengan Sliding Window Flush
* **Tantangan**: Rancang sebuah class `StreamBufferAggregator` yang menerima mutasi data continuous (misal: 10.000 event/detik). Class harus melakukan buffering dan mengeksekusi `bulkWrite` secara adaptif berdasarkan salah satu dari dua kondisi:
  1. Jumlah buffer mencapai batas `MAX_BUFFER_SIZE = 3000`.
  2. Waktu tunggu sejak event pertama dalam buffer mencapai `FLUSH_INTERVAL_MS = 100ms`.
  Sistem harus menangani error `WriteConflict` dan secara otomatis melakukan *retry* dengan exponential backoff pada record yang terisolasi tanpa memblokir stream event baru yang masuk.
* **Kriteria Keberhasilan**: Class menggunakan mekanisme locking non-blocking (seperti swap-pointer array buffer) untuk memastikan zero-latency-stall pada thread event producer.

---

### 14. Challenges

**Arsitektur Sinkronisasi Multitenant Transaksi Global Tanpa Out-of-Order Corruption**

Sebuah core banking fintech melayani 500 bank partner (multitenant) dalam satu database MongoDB cluster. Setiap bank mengirimkan feed mutasi rekening melalui webhook secara asinkron.
* Masalah: Jaringan internet mitra sering mengalami instabilitas, menyebabkan event saldo akun sering kali terkirim secara *out-of-order* (event transaksi versi 3 tiba lebih dulu daripada event versi 2).
* Instruksi Tantangan:
  1. Rancang skema dokumen akun yang mendukung *Optimistic Version Check*.
  2. Implementasikan modul ingestion `bulkWrite` terisolasi per tenant.
  3. Skema mutasi harus menjamin bahwa event dengan versi yang lebih rendah dari versi yang sudah tersimpan di database **ditolak secara idempoten** (tidak boleh menimpa saldo terkini), namun mutasi yang valid tetap dieksekusi secara atomic.
  4. Seluruh flow eksekusi harus tahan terhadap failure skenario: jika 10 node aplikasi klien mati secara bersamaan (*graceful shutdown abort*), tidak boleh ada mutasi data yang berstatus *half-baked* atau data inconsistency antara primary balance dan transaction ledger.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konsep Dasar (5 Soal)
1. Apa fungsi utama semafor tiket (read/write tickets) pada storage engine WiredTiger?
   * A. Membatasi ukuran maksimal memori RAM yang boleh dipakai oleh mongod.
   * B. Mengontrol jumlah konkurensi operasi pembacaan dan penulisan yang diproses secara simultan di storage engine.
   * C. Menentukan jumlah replica node yang harus memberikan acknowledgment.
   * D. Menghitung jumlah koneksi maksimal client pool.

2. Secara default, berapa interval checkpoint reguler dilakukan oleh WiredTiger ke media penyimpanan disk?
   * A. 100 milidetik.
   * B. 1 detik.
   * C. 60 detik.
   * D. 15 menit.

3. Apa yang terjadi jika operasi pada urutan ke-5 dalam array `bulkWrite` mengalami kegagalan pada mode `ordered: true`?
   * A. Operasi ke-5 di-rollback, operasi ke-6 hingga selesai tetap dilanjutkan.
   * B. Seluruh operasi dari awal di-rollback secara otomatis.
   * C. Eksekusi langsung dihentikan; operasi ke-6 hingga selesai dibatalkan (short-circuit).
   * D. Operasi ke-5 dicatat dalam error log, lalu server mencoba ulang 3 kali sebelum lanjut ke item ke-6.

4. Konfigurasi Write Concern `j: true` memastikan bahwa:
   * A. Data telah berhasil direplikasi ke minimal 3 secondary node.
   * B. Data telah dituliskan ke disk journaling log secara persisten (fdatasync).
   * C. Dokumen yang di-insert langsung dimasukkan ke index in-memory.
   * D. Seluruh transaksi diisolasi dengan level Serializability.

5. Manakah Read Concern yang menjamin bahwa data yang dibaca berasal dari snapshot yang tidak akan pernah di-rollback akibat pergantian Primary node?
   * A. `local`
   * B. `available`
   * C. `majority`
   * D. `uncommitted`

#### Bagian B: Analisis Tingkat Menengah (5 Soal)
6. Kapan storage engine WiredTiger mulai memicu mode eviksi darurat (*client-assisted eviction*)?
   * A. Ketika dirty data pada cache WiredTiger melampaui batas ambang batas eviksi (misal: >20%).
   * B. Ketika Read Tickets habis sepenuhnya.
   * C. Ketika replication lag secondary melebihi 1 jam.
   * D. Ketika ukuran disk journal mencapai batas 16 MB.

7. Mengapa array operasi berukuran 100.000 elemen pada `bulkWrite` tidak melanggar limit ukuran BSON MongoDB (16 MB) ketika dikirimkan oleh driver?
   * A. Karena engine MongoDB otomatis mengompresi payload BSON menggunakan algoritma Snappy.
   * B. Karena driver memecah array tersebut menjadi beberapa batch OP_MSG internal secara otomatis (maksimal 100.000 dokumen atau 48 MB per batch jaringan).
   * C. Karena dokumen BSON hanya dihitung ukurannya saat sudah tertulis di disk.
   * D. Karena limit 16 MB hanya berlaku untuk file GridFS.

8. Jika sebuah instance replica set dijalankan dengan 3 node (1 Primary, 2 Secondary), namun 2 Secondary mengalami network partition dan disconnected dari Primary. Apa yang terjadi jika client mengeksekusi `bulkWrite` dengan `w: "majority"` dan `wtimeout: 3000`?
   * A. Operasi langsung sukses karena Primary mencatat transaksi secara lokal.
   * B. Operasi hang tanpa batas waktu (*infinite freeze*).
   * C. Primary mengeksekusi operasi secara lokal, namun melempar `WriteConcernError` setelah 3.000 ms karena kourum replikasi gagal tercapai.
   * D. Primary seketika step-down dan membatalkan semua koneksi yang masuk.

9. Apa implikasi performa penggunaan operator `$unset` dan `$push` masif di dalam `bulkWrite` dibandingkan dengan overwrite `$set` tetap?
   * A. Tidak ada perbedaan karena MongoDB adalah database schema-less.
   * B. Memodifikasi ukuran dokumen secara dinamis menyebabkan page allocation ulang dan document fragmentation pada storage disk WiredTiger.
   * C. `$unset` membutuhkan alokasi exclusive database lock (`X Lock`).
   * D. Driver menolak operator `$unset` dalam eksekusi batch.

10. Apa kegunaan utama parameter cursor `batchSize` pada operasi pembacaan data bervolume masif?
    * A. Menentukan limit query secara permanen.
    * B. Mengontrol jumlah dokumen BSON yang dikembalikan oleh server ke client dalam satu network round-trip packet (perintah `getMore`).
    * C. Memaksa server menjalankan index scan secara parallel.
    * D. Menjamin dokumen yang dibaca terkunci secara otomatis (*Pessimistic Locking*).

#### Bagian C: Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Sebuah service audit logging mencatat 10.000 events/detik menggunakan `bulkWrite(..., { ordered: false, w: 1 })`. Pada suatu hari, terjadi lonjakan latensi di mana aplikasi sering mengalami crash akibat `E11000 duplicate key error`. Setelah diinvestigasi, metrik CPU MongoDB normal (25%), namun client heap memory OOM. Apa akar masalah dan solusinya?
    * A. Driver mengalokasikan error object yang sangat besar pada array `writeErrors` ketika jutaan dokumen duplikat gagal; solusinya tangani validasi filter upsert dengan deterministic index atau pecah chunk lebih kecil dan abaikan error code 11000 di level streaming.
    * B. MongoDB kehabisan disk space; solusinya jalankan operasi `compact`.
    * C. Mode `ordered: false` tidak aman untuk konkurensi; ubah menjadi `ordered: true`.
    * D. Switch storage engine WiredTiger ke InMemory engine.

12. **Skenario 2**: DBA Anda mendeteksi bahwa metrik `wiredTiger.concurrentTransactions.write.available` turun ke angka `0` selama proses batch update data pelanggan malam hari. Laporan profiler menunjukkan bahwa update query hanya memodifikasi 1 field sederhana, namun latency rata-rata menembus 8 detik per batch. Tindakan apa yang paling tepat untuk mendiagnosa dan memperbaiki kondisi ini?
    * A. Segera restart service `mongod` untuk me-reset ticket pool.
    * B. Periksa `planSummary` pada system profile log; jika bernilai `COLLSCAN`, buat indeks pada kriteria filter update tersebut untuk mencegah penahanan tiket akibat pemindaian full table.
    * C. Tambah RAM fisik pada cluster Primary.
    * D. Ubah konfigurasi journaling dari default menjadi `j: false`.

13. **Skenario 3**: Sebuah marketplace menerapkan transaksi transfer saldo point antar-user. Developer menggunakan `bulkWrite` untuk mengurangi point User A dan menambah point User B secara simultan. Terkadang muncul error `WriteConflictError` saat event flash-sale berlangsung. Mengapa error ini muncul dan bagaimana mitigasinya?
    * A. Error ini terjadi karena WiredTiger mendeteksi dua operasi concurrent mencoba memodifikasi dokumen/halaman memori MVCC yang sama secara bersamaan; solusinya terapkan retry logic dengan randomized exponential backoff pada level client.
    * B. Driver MongoDB bermasalah; harus di-downgrade ke versi sebelumnya.
    * C. User A dan User B berada pada shard yang berbeda, sehingga bulkWrite dilarang.
    * D. WiredTiger kehabisan Write-Ahead Log memory.

---

### Kunci Jawaban Quiz

#### Bagian A
1. **B** — Semafor tiket mengatur konkurensi throughput engine internal WiredTiger untuk mencegah CPU & cache thrashing.
2. **C** — Default checkpoint interval WiredTiger adalah 60 detik atau ketika journal log mencapai batas 2 GB.
3. **C** — Mode `ordered: true` melakukan short-circuiting saat terjadi kegagalan pertama.
4. **B** — `j: true` memaksa sinkronisasi perubahan buffer journal ke disk fisik (`fdatasync`).
5. **C** — Read concern `majority` membaca data yang telah dikonfirmasi oleh kuorum replica set, sehingga kebal terhadap rollback pasca failover.

#### Bagian B
6. **A** — Eviksi darurat dipicu saat persentase dirty pages di cache melebihi threshold tertentu (default: 20%).
7. **B** — Driver secara otomatis memecah payload menjadi sub-batch jaringan (`OP_MSG`) sesuai batas aturan wire protocol (maksimal 100.000 docs atau 48 MB).
8. **C** — Karena kehilangan kourum majority, Primary menahan request sampai batas `wtimeout` berakhir, lalu menghasilkan error write concern timeout.
9. **B** — Mengubah ukuran BSON dokumen yang sudah tersimpan memicu alokasi ulang disk block memory dan fragmentasi.
10. **B** — `batchSize` menentukan ukuran window paket jaringan per instruksi `getMore`.

#### Bagian C
11. **A** — Array `writeErrors` yang menampung ribuan error object BSON pada operasi masif memicu lonjakan memory heap client. Solusinya adalah membatasi chunking size dan merancang filter upsert yang idempoten.
12. **B** — COLLSCAN pada instruksi update menahan Intent Lock dan tiket WiredTiger dalam durasi yang sangat lama, memicu starvation bagi seluruh operasi lain.
13. **A** — `WriteConflictError` adalah karakteristik MVCC WiredTiger saat terjadi write-write race condition pada dokumen yang sama. Mitigasi standarnya adalah retry dengan exponential backoff.

---

### 16. Summary

1. Performa penulisan masif MongoDB dibatasi oleh Network RTT, alokasi Concurrency Tickets (128 read/write), dan mekanisme eviksi dirty page pada WiredTiger Cache.
2. `bulkWrite` memangkas latency overhead jaringan secara signifikan melalui pengelompokan operasi ke dalam protokol wire-batching (`OP_MSG`).
3. Penggunaan opsi `ordered: false` sangat krusial untuk ingestion pipeline modern guna mengeksploitasi multi-threading internal storage engine dan mencegah pembatalan eksekusi (*short-circuit*) saat terjadi error individual.
4. Kombinasi *Write Concern* (`w: "majority"`, `j: true`, `wtimeoutMS`) dan *Read Concern* (`majority`, `snapshot`) adalah penentu absolut terhadap keseimbangan teorema CAP antara konsistensi data vs write latency.
5. Indeks yang tepat, pembatasan ukuran chunk batch aplikasi (1.000–5.000 records), dan idempotensi update adalah pondasi utama dalam menjaga kestabilan storage engine dari fenomena mematikan: *WiredTiger Ticket Starvation* dan *Memory Cache Eviction Stalls*.