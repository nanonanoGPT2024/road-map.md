# Bab 06 Module 01: Concurrency Control, Lock Semantics & Transactions

---

## 01. Identitas Modul
* **Track:** Database & Backend Engineering
* **Kategori:** 04-Backend-and-Database
* **Sub-Kategori:** MongoDB Core Internals & Advanced Data Integrity
* **Modul:** Bab 06 Module 01
* **Topik:** Concurrency Control, Lock Semantics & Multi-Document Distributed Transactions
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** MongoDB Architecture Basics, WiredTiger Storage Engine Fundamentals, Replica Set Internals, Read/Write Concerns, Node.js/TypeScript Development.

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Menganalisis hierarki penguncian (*locking hierarchy*) MongoDB dan membedakannya dari *concurrency control* berbasis *Multi-Version Concurrency Control* (MVCC) pada storage engine WiredTiger.
2. Membedakan secara granular semantik lock `R`, `W`, `r`, `w` pada level Global, Database, dan Collection, serta dampaknya terhadap throughput operasional.
3. Mengonfigurasi dan mengeksekusi *Multi-Document Distributed Transactions* dengan jaminan ACID penuh menggunakan MongoDB Node.js Driver.
4. Menganalisis dan memitigasi anomali konkurensi (Dirty Reads, Non-repeatable Reads, Phantom Reads, dan Write Skew) melalui pemilihan `readConcern` dan `writeConcern` yang tepat.
5. Mendiagnosis lock contention, latch contention, transaction aborts, dan deadlocks menggunakan engine diagnostics (`serverStatus`, `currentOp`, diagnostic lock logs).
6. Mengimplementasikan transaksi terdistribusi production-grade dengan handling *transient transaction errors*, *commit uncertainty*, retry mechanics, dan boundary validation.

---

## 03. Concept Map Diagram ASCII

```
+-------------------------------------------------------------------------------+
|                       MONGODB CONCURRENCY ARCHITECTURE                        |
+-------------------------------------------------------------------------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
                 v                                             v
+---------------------------------+           +---------------------------------+
|      MONGOD METADATA LOCKS      |           |     WIREDTIGER STORAGE ENGINE   |
|   (Intent & Exclusive Locks)    |           |     (Optimistic Concurrency)    |
+---------------------------------+           +---------------------------------+
| • Global    (IS, IX, S, X)      |           | • Multi-Version Concurrency     |
| • Database  (IS, IX, S, X)      |           |   Control (MVCC)                |
| • Collection(IS, IX, S, X)      |           | • Optimistic Lock-Free Reads    |
| • Protects: DDL, Catalogs,      |           | • Document-Level Lock-Free Con- |
|   Namespace Routing             |           |   flict Detection at Commit     |
+---------------------------------+           +---------------------------------+
                 |                                             |
                 +----------------------+----------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                      MULTI-DOCUMENT TRANSACTIONS (ACID)                       |
+-------------------------------------------------------------------------------+
| • Snapshot Isolation via WiredTiger History Store / Checkpoints               |
| • Global Logical Clock via Cluster Time & Hybrid Logical Clock (HLC)          |
| • Read Concern: "snapshot" (Linearizable across replica set/shards)           |
| • Write Concern: "majority" (Durability via Raft-like Oplog Consensus)       |
| • Two-Phase Commit (2PC) Orchestrated by mongos / primary for distributed txn |
+-------------------------------------------------------------------------------+
```

---

## 04. Mengapa Relevan
Dalam arsitektur backend modern berskala tinggi (*high-throughput distributed systems*), pemahaman mengenai isolasi dan integritas data sering kali tereduksi oleh asumsi simplistik bahwa "MongoDB tidak memiliki transaksi" atau "MongoDB mengunci seluruh database saat penulisan". Asumsi ini keliru dan berisiko fatal pada perancangan sistem enterprise.

MongoDB memisahkan proteksi metadata struktural (menggunakan MongoD Intent Locks) dari konkurensi data dokumen mentah (menggunakan WiredTiger MVCC). Tanpa pemahaman mendalam tentang:
- Perbedaan antara MongoD lock contention dan WiredTiger write-conflict rollbacks,
- Biaya performa dari *Multi-Document Transactions* akibat pemeliharaan snapshot dan retensi cache WiredTiger,
- Mekanika *Two-Phase Commit* (2PC) pada Sharded Cluster,

sistem Anda rentan terhadap *deadlocks*, *latency spikes* (P99/P99.9), kehabisan WiredTiger *cache eviction capacity*, serta inkonsistensi saldo finansial/inventaris dalam beban kerja konkuren tinggi.

---

## 05. Anatomi Konsep Inti

### 1. Hierarki Penguncian MongoDB (MongoD Layer Locks)
MongoDB menggunakan *Hierarchical Intent Locking* untuk membatasi operasi metadata dan DDL. Terdapat empat mode dasar:
- **`IS` (Intent Shared):** Menandakan niat membaca data di sub-node hierarki (misal: dokumen dalam koleksi).
- **`IX` (Intent Exclusive):** Menandakan niat memodifikasi data di sub-node hierarki.
- **`S` (Shared):** Akses baca eksklusif pada level target; mencegah penulisan (`X` dan `IX`).
- **`X` (Exclusive):** Akses modifikasi eksklusif pada level target; memblokir semua operasi lain.

#### Matriks Kompatibilitas Lock:
| Diminta \ Eksis | `IS` | `IX` | `S` | `X` |
| :--- | :--- | :--- | :--- | :--- |
| **`IS`** | Ya | Ya | Ya | **Tidak** |
| **`IX`** | Ya | Ya | **Tidak** | **Tidak** |
| **`S`** | Ya | **Tidak** | Ya | **Tidak** |
| **`X`** | **Tidak**| **Tidak** | **Tidak** | **Tidak** |

### 2. Concurrency Control WiredTiger: MVCC & Document-Level Locking
WiredTiger tidak menggunakan penguncian pesimistis baris/dokumen bergaya engine lawas. WiredTiger menggunakan **Multi-Version Concurrency Control (MVCC)**:
- **Reads:** Pembacaan dialokasikan pointer ke *in-memory transaction snapshot*. Operasi baca bersifat non-blocking terhadap operasi tulis dan tidak menghasilkan lock.
- **Writes:** Modifikasi dialokasikan pada *uncommitted transaction buffer*. Ketika dua transaksi konkuren mencoba memodifikasi dokumen yang sama, operasi yang pertama kali melakukan commit akan berhasil; operasi kedua mendeteksi *Write Conflict*, dibatalkan (*aborted*), dan dipaksa melakukan *retry*.

### 3. Read Isolation Levels & Read Concerns
- **`local`:** Mengembalikan data terkini dari node lokal tanpa konsensus replikasi. Rentan terhadap *dirty reads* jika node mengalami *rollback*.
- **`majority`:** Mengembalikan data yang telah dikomit ke mayoritas node replica set via Oplog. Menghindari *dirty reads* dan *rollback*.
- **`linearizable`:** Menjamin pembacaan selalu membaca penulisan mayoritas paling mutakhir secara realtime (menghindari split-brain stale reads dengan memverifikasi kepemimpinan primary secara realtime).
- **`snapshot`:** Menyediakan isolasi snapshot monolitik. Semua pembacaan dalam transaksi melihat titik waktu konsisten yang sama (*point-in-time snapshot*), mencegah *Non-repeatable Read* dan *Phantom Read*.

### 4. Distributed Multi-Document ACID Transactions
Transaksi MongoDB beroperasi dengan mengombinasikan:
- **Atomicity:** Semua modifikasi dokumen multi-koleksi/multi-database berhasil dikomit atau di-rollback secara penuh.
- **Consistency:** Validasi skema (JSON Schema validation) dan invariant indeks diverifikasi pada fase commit.
- **Isolation:** Snapshot isolation default; transaksi lain tidak dapat melihat perubahan uncommitted.
- **Durability:** Dijamin jika transaksi dikomit menggunakan `writeConcern: { w: "majority", j: true }`.

---

## 06. Panduan Implementasi Step-by-Step

### Alur Konfigurasi Transaksi di Node.js / TypeScript
1. **Inisialisasi Client:** Pastikan terhubung ke Replica Set atau Sharded Cluster (Standalone mongod tidak mendukung multi-document transactions).
2. **Mulai ClientSession:** Alokasikan session eksplisit dari `MongoClient`.
3. **Definisikan Opsi Transaksi:**
   - `readPreference: ReadPreference.primary` (Wajib untuk write operations).
   - `readConcern: ReadConcern.fromOptions({ level: 'snapshot' })`.
   - `writeConcern: WriteConcern.fromOptions({ w: 'majority', j: true })`.
   - `maxCommitTimeMS`: Batas waktu timeout fase commit.
4. **Eksekusi via `withTransaction` Helper:** Mengotomatisasi penanganan `TransientTransactionError` dan `UnknownTransactionCommitResult`.
5. **Penutupan Resource:** Tutup session di dalam blok `finally`.

---

## 07. Contoh Kasus Sederhana: Bank Account Transfer
Berikut skenario transfer saldo antar akun perbankan untuk mendemonstrasikan ACID transfer sederhana.

```typescript
import { MongoClient, ClientSession, TransactionOptions, ReadConcern, WriteConcern } from 'mongodb';

async function executeSimpleTransfer(
  client: MongoClient,
  fromAccountId: string,
  toAccountId: string,
  amount: number
): Promise<void> {
  const session: ClientSession = client.startSession();

  const transactionOptions: TransactionOptions = {
    readConcern: new ReadConcern('snapshot'),
    writeConcern: new WriteConcern('majority'),
    maxCommitTimeMS: 5000,
  };

  try {
    await session.withTransaction(async () => {
      const accountsColl = client.db('core_banking').collection('accounts');

      // 1. Potong Saldo Akun Pengirim (dengan pengecekan saldo mencukupi)
      const debitResult = await accountsColl.updateOne(
        { accountId: fromAccountId, balance: { $gte: amount } },
        { $inc: { balance: -amount }, $set: { updatedAt: new Date() } },
        { session }
      );

      if (debitResult.matchedCount === 0) {
        throw new Error(`Transfer failed: Insufficient balance or invalid account ${fromAccountId}`);
      }

      // 2. Tambah Saldo Akun Penerima
      const creditResult = await accountsColl.updateOne(
        { accountId: toAccountId },
        { $inc: { balance: amount }, $set: { updatedAt: new Date() } },
        { session }
      );

      if (creditResult.matchedCount === 0) {
        throw new Error(`Transfer failed: Destination account ${toAccountId} not found`);
      }
    }, transactionOptions);

    console.log(`Transfer of ${amount} from ${fromAccountId} to ${toAccountId} succeeded.`);
  } finally {
    await session.endSession();
  }
}
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Di bawah ini adalah sistem pemrosesan pesanan enterprise (*E-Commerce Checkout Ledger*) dengan mitigasi Write Conflicts manual, Circuit Breaking, Idempotency Token, Transaction Metrics, dan Distributed Lock Emulation.

```typescript
import {
  MongoClient,
  ClientSession,
  ReadConcern,
  WriteConcern,
  MongoError,
  MongoDriverError,
  ObjectId,
  ClientSessionOptions,
  TransactionOptions
} from 'mongodb';

export interface OrderItem {
  sku: string;
  quantity: number;
  unitPrice: number;
}

export interface CheckoutPayload {
  orderId: string;
  idempotencyKey: string;
  customerId: string;
  items: OrderItem[];
  totalAmount: number;
}

export interface ExecutionResult {
  success: boolean;
  orderId: string;
  transactionAttempts: number;
  error?: string;
}

export class OrderCheckoutProcessor {
  private client: MongoClient;
  private maxRetries: number;
  private baseBackoffMs: number;

  constructor(client: MongoClient, maxRetries = 5, baseBackoffMs = 100) {
    this.client = client;
    this.maxRetries = maxRetries;
    this.baseBackoffMs = baseBackoffMs;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private isTransientError(error: unknown): boolean {
    if (error instanceof MongoError) {
      return (
        error.hasErrorLabel('TransientTransactionError') ||
        error.hasErrorLabel('UnknownTransactionCommitResult') ||
        error.code === 112 // WriteConflict code
      );
    }
    return false;
  }

  public async processCheckout(payload: CheckoutPayload): Promise<ExecutionResult> {
    const sessionOptions: ClientSessionOptions = {
      causalConsistency: true,
    };

    const transactionOptions: TransactionOptions = {
      readConcern: new ReadConcern('snapshot'),
      writeConcern: new WriteConcern('majority', undefined, 10000), // w: majority, timeout 10s
      maxCommitTimeMS: 5000,
    };

    let attempt = 0;

    while (attempt < this.maxRetries) {
      attempt++;
      const session: ClientSession = this.client.startSession(sessionOptions);

      try {
        session.startTransaction(transactionOptions);

        const db = this.client.db('enterprise_store');
        const idempotencyColl = db.collection('idempotency_keys');
        const inventoryColl = db.collection('inventory');
        const ordersColl = db.collection('orders');
        const ledgerColl = db.collection('financial_ledger');

        // 1. Idempotency Check: Cegah double processing
        const idempotencyRecord = await idempotencyColl.findOne(
          { key: payload.idempotencyKey },
          { session }
        );

        if (idempotencyRecord) {
          await session.abortTransaction();
          return {
            success: true,
            orderId: idempotencyRecord.orderId,
            transactionAttempts: attempt,
          };
        }

        // 2. Lock & Deduct Inventory (Optimistic Check via WiredTiger)
        for (const item of payload.items) {
          const invUpdate = await inventoryColl.updateOne(
            {
              sku: item.sku,
              stock: { $gte: item.quantity },
            },
            {
              $inc: { stock: -item.quantity },
              $set: { lastModified: new Date() },
            },
            { session }
          );

          if (invUpdate.matchedCount === 0) {
            throw new Error(`ERR_INSUFFICIENT_STOCK: SKU ${item.sku}`);
          }
        }

        // 3. Create Immutable Order Record
        const orderDoc = {
          _id: new ObjectId(),
          orderId: payload.orderId,
          customerId: payload.customerId,
          items: payload.items,
          totalAmount: payload.totalAmount,
          status: 'COMPLETED',
          createdAt: new Date(),
        };
        await ordersColl.insertOne(orderDoc, { session });

        // 4. Financial Ledger Double-Entry
        const ledgerDoc = {
          _id: new ObjectId(),
          orderId: payload.orderId,
          customerId: payload.customerId,
          debit: payload.totalAmount,
          credit: 0,
          type: 'ORDER_PAYMENT',
          timestamp: new Date(),
        };
        await ledgerColl.insertOne(ledgerDoc, { session });

        // 5. Register Idempotency Key
        await idempotencyColl.insertOne(
          {
            key: payload.idempotencyKey,
            orderId: payload.orderId,
            createdAt: new Date(),
          },
          { session }
        );

        // 6. Commit Transaction with custom Retry Logic
        await this.commitWithRetry(session);

        return {
          success: true,
          orderId: payload.orderId,
          transactionAttempts: attempt,
        };
      } catch (error: unknown) {
        if (session.inTransaction()) {
          try {
            await session.abortTransaction();
          } catch (abortError) {
            // Suppress abort errors to prioritize original error
          }
        }

        if (this.isTransientError(error) && attempt < this.maxRetries) {
          const jitter = Math.random() * 50;
          const backoff = this.baseBackoffMs * Math.pow(2, attempt - 1) + jitter;
          await this.sleep(backoff);
          continue; // Retry loop
        }

        return {
          success: false,
          orderId: payload.orderId,
          transactionAttempts: attempt,
          error: error instanceof Error ? error.message : String(error),
        };
      } finally {
        await session.endSession();
      }
    }

    return {
      success: false,
      orderId: payload.orderId,
      transactionAttempts: attempt,
      error: 'ERR_MAX_RETRIES_EXCEEDED: Transaction aborted due to persistent contention',
    };
  }

  private async commitWithRetry(session: ClientSession): Promise<void> {
    while (true) {
      try {
        await session.commitTransaction();
        break;
      } catch (error: unknown) {
        if (error instanceof MongoError && error.hasErrorLabel('UnknownTransactionCommitResult')) {
          // Re-attempt commit because outcome is unknown
          continue;
        }
        throw error;
      }
    }
  }
}
```

---

## 09. Diagram Alur Kerja ASCII: Transaction Execution Lifecycle

```
Client App                      Driver (Session)                   WiredTiger (Primary Node)
    |                                   |                                     |
    |---- startSession() -------------->|                                     |
    |---- startTransaction() ---------->|                                     |
    |                                   |--- Open In-Memory Snapshot -------->|
    |                                   |    (Set Read Timestamp via HLC)     |
    |                                   |                                     |
    |---- updateOne(Inventory) -------->|--- Check Doc Version in Cache ----->|
    |                                   |<-- Version Valid (No Conflict) -----|
    |                                   |--- Write Uncommitted Delta Buffer ->|
    |                                   |                                     |
    |---- insertOne(Order) ------------>|--- Write Uncommitted Delta Buffer ->|
    |                                   |                                     |
    |---- commitTransaction() --------->|                                     |
    |                                   |--- Two-Phase Commit / Prepare ----->|
    |                                   |    (Validate Write Conflicts)       |
    |                                   |                                     |
    |                                   |    [Conflict Detected?]             |
    |                                   |    |-- YES: Return WriteConflict    |
    |                                   |    +-- NO:  Apply to Oplog          |
    |                                   |                                     |
    |                                   |--- Write Concern (w: majority) ---->|
    |                                   |    (Replicate to Secondaries)       |
    |                                   |<-- Quorum ACKs Received ------------|
    |                                   |--- Release WiredTiger Snapshot ---->|
    |<--- Transaction Committed --------|                                     |
```

---

## 10. Analisis Trade-offs

| Pendekatan / Pola | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Multi-Document ACID Transactions** | Jaminan konsistensi absolut (ACID), abstraksi level database memudahkan logika bisnis kompleks. | Overhead latensi tinggi (fase koordinasi commit), beban memori WiredTiger cache meningkat drastis, membatasi *maximum write throughput*. |
| **Optimistic Concurrency Control (Version Field)** | *Zero-locking overhead* pada engine, throughput skala horizontal tinggi, tanpa penahanan snapshot memori. | Membutuhkan penanganan logika retry manual di level aplikasi; rentan kelaparan transaksi (*starvation*) jika kontensi sangat tinggi. |
| **Embedded Document Patterns (Single-Doc Atomicity)** | Latensi ultra-rendah (<1ms), zero transaction overhead, *native atomic updates* via `$inc`, `$push`, `$set`. | Terbatas pada batas dokumen 16MB; dapat menyebabkan *unbounded document growth* dan fragmentasi memori. |
| **Two-Phase Commit Manual (App-Level Saga Pattern)** | Menghilangkan batasan durasi transaksi 60 detik MongoDB, mendukung transaksi heterogen multi-database. | Kompleksitas penanganan kompensasi kegagalan (*compensating transactions*), inkonsistensi sementara (*eventual consistency*). |

---

## 11. Best Practices & Antipatterns

### Best Practices:
1. **Minimalkan Durasi Transaksi:** Jaga siklus hidup transaksi di bawah 1 detik (default hard limit WiredTiger adalah 60 detik sebelum snapshot di-evict).
2. **Kueri Tepat Sasaran:** Selalu modifikasi dokumen menggunakan predikat query yang terindeks (`_id` atau indeks spesifik) untuk mencegah full collection scan yang menahan lock intent terlalu luas.
3. **Urutan Operasi Konsisten:** Modifikasi dokumen lintas koleksi dalam urutan deterministik (misal: alfabetis berdasarkan Collection Name atau ID) untuk meminimalisasi *deadlock*.
4. **Ukuran Transaksi Ringan:** Batasi operasi transaksi maksimal < 1000 modifikasi dokumen per transaksi untuk menghindari lonjakan Oplog dan WiredTiger *pinned dirty bytes*.

### Antipatterns:
1. **Melakukan Network I/O di dalam Transaksi:** Melakukan pemanggilan REST API pembayaran eksternal di antara `startTransaction` dan `commitTransaction`. Ini akan menahan snapshot WiredTiger dan menyebabkan *cache eviction stalls*.
2. **DDL Operations di dalam Transaksi:** Menjalankan `createIndex`, `dropDatabase`, atau `createCollection` di dalam blok transaksi. Tindakan ini memicu Exclusive (X) Metadata Lock yang membekukan operasi database.
3. **Mengabaikan Error Labels:** Menangani rollback secara manual tanpa memeriksa `TransientTransactionError` dan `UnknownTransactionCommitResult`.

---

## 12. Security Hardening & Isolation Constraints
1. **Enforce Role-Based Access Control (RBAC):** Transaksi tidak mengabaikan RBAC. Akun aplikasi harus memiliki hak presisi (`find`, `insert`, `update`) pada seluruh namespace koleksi target:
   ```javascript
   db.createRole({
     role: "checkoutProcessorRole",
     privileges: [
       { resource: { db: "enterprise_store", collection: "orders" }, actions: [ "find", "insert" ] },
       { resource: { db: "enterprise_store", collection: "inventory" }, actions: [ "find", "update" ] },
       { resource: { db: "enterprise_store", collection: "financial_ledger" }, actions: [ "insert" ] },
       { resource: { db: "enterprise_store", collection: "idempotency_keys" }, actions: [ "find", "insert" ] }
     ],
     roles: []
   });
   ```
2. **Encryption-in-Transit & At-Rest:** Transaksi multi-dokumen mereplikasi payload melalui Oplog. Pastikan replikasi dienkripsi menggunakan TLS 1.3 dan penyimpanan data/oplog dienkripsi dengan WiredTiger Cryptographic Encryption Engine (AES-256-CBC).

---

## 13. Observabilitas & Debugging

### 1. Deteksi Operasi Penguncian Aktif (`currentOp`)
Jalankan perintah ini di mongosh untuk melihat transaksi yang sedang berjalan lebih dari 2 detik atau terblokir:
```javascript
db.currentOp({
  "active": true,
  "secs_running": { "$gt": 2 },
  "transaction": { "$exists": true }
});
```

### 2. Menganalisis WiredTiger Concurrency Counters via `serverStatus`
```javascript
db.serverStatus().wiredTiger.concurrentTransactions;
// Menghasilkan status read/write ticketing system:
// {
//   write: { out: 12, available: 116, totalTickets: 128 },
//   read:  { out: 4,  available: 124, totalTickets: 128 }
// }
```
*Jika `available` mendekati 0, engine mengalami bottleneck transaksi parah (queue saturation).*

### 3. Log Penganalisis Lock Contention
Aktifkan profiling pada namespace spesifik untuk mendeteksi transaksi lambat:
```javascript
db.setProfilingLevel(1, { slowms: 100, sampleRate: 1.0 });
// Filter profiler untuk lock waiting:
db.system.profile.find({ "locks.Collection.acquireWaitCount.w": { $gt: 0 } }).pretty();
```

---

## 14. Benchmarking & Performance Simulation
Gunakan script Node.js ini untuk menguji throughput dan mendeteksi laju Write Conflict pada transaksi konkuren tinggi:

```typescript
import { MongoClient } from 'mongodb';

async function runConcurrencyBenchmark() {
  const uri = 'mongodb://localhost:27017/?replicaSet=rs0';
  const client = new MongoClient(uri, { maxPoolSize: 100 });
  await client.connect();

  const db = client.db('benchmark_db');
  await db.collection('hot_counter').drop().catch(() => {});
  await db.collection('hot_counter').insertOne({ _id: 'counter', value: 0 });

  const totalWorkers = 50;
  const incrementsPerWorker = 20;
  let writeConflicts = 0;
  let successfulCommits = 0;

  console.time('Benchmark-Execution');

  const executeWorker = async () => {
    for (let i = 0; i < incrementsPerWorker; i++) {
      const session = client.startSession();
      try {
        await session.withTransaction(async () => {
          const doc = await db.collection('hot_counter').findOne({ _id: 'counter' }, { session });
          await db.collection('hot_counter').updateOne(
            { _id: 'counter' },
            { $set: { value: doc!.value + 1 } },
            { session }
          );
        });
        successfulCommits++;
      } catch (err: any) {
        if (err.hasErrorLabel && err.hasErrorLabel('TransientTransactionError')) {
          writeConflicts++;
        }
      } finally {
        await session.endSession();
      }
    }
  };

  await Promise.all(Array.from({ length: totalWorkers }, () => executeWorker()));

  console.timeEnd('Benchmark-Execution');
  console.log(`Summary: Successful: ${successfulCommits}, Write Conflicts Aborted: ${writeConflicts}`);
  
  const finalDoc = await db.collection('hot_counter').findOne({ _id: 'counter' });
  console.log(`Final Counter Value: ${finalDoc?.value}`);
  
  await client.close();
}

runConcurrencyBenchmark().catch(console.error);
```

---

## 15. Hands-on Lab Mini-Project

### Skenario Proyek: Tiket Konser Flash Sale Engine (Concurrency Protected)
Bangun sistem backend transaksi untuk reservasi tiket kursi bioskop/konser di mana 100 pengguna mencoba membeli 1 tiket yang tersisa secara bersamaan tanpa terjadi *overselling*.

#### Direktori Setup:
```bash
mkdir mongo-concurrency-lab && cd mongo-concurrency-lab
npm init -y
npm install mongodb typescript @types/node ts-node
npx tsc --init
```

#### Struktur Skema Koleksi:
1. `seats`: `{ _id: string, isReserved: boolean, reservedBy: string | null }`
2. `tickets`: `{ _id: ObjectId, seatId: string, userId: string, purchasedAt: Date }`

#### Tugas Eksekusi Mahasiswa:
1. Inisialisasi koleksi `seats` dengan 5 kursi: `SEAT_A1` sampai `SEAT_A5`.
2. Simulasikan 100 worker asynchronous secara simultan yang mencoba memesan `SEAT_A1`.
3. Terapkan Transaksi MongoDB dengan `readConcern: 'snapshot'` dan `writeConcern: 'majority'`.
4. Pastikan hanya **tepat 1 worker** yang berhasil mengamankan `SEAT_A1` dan sisa 99 worker mendapatkan status penolakan yang ter-handle rapi tanpa *uncaught promise rejections*.

---

## 16. Automated Testing & Verification

Gunakan test suite berbasis `Jest` untuk memverifikasi isolasi snapshot dan rollback atomik transaksi.

```typescript
import { MongoClient, ClientSession } from 'mongodb';

describe('MongoDB Concurrency & Transaction Test Suite', () => {
  let client: MongoClient;

  beforeAll(async () => {
    client = new MongoClient('mongodb://localhost:27017/?replicaSet=rs0');
    await client.connect();
  });

  afterAll(async () => {
    await client.close();
  });

  beforeEach(async () => {
    const db = client.db('test_isolation');
    await db.collection('wallets').deleteMany({});
    await db.collection('wallets').insertOne({ userId: 'USR_01', balance: 1000 });
  });

  test('Rollback Integrity: Gagal di tengah transaksi tidak mengubah state awal', async () => {
    const session: ClientSession = client.startSession();
    const db = client.db('test_isolation');

    expect.assertions(2);

    try {
      await session.withTransaction(async () => {
        // Step 1: Potong dana
        await db.collection('wallets').updateOne(
          { userId: 'USR_01' },
          { $inc: { balance: -500 } },
          { session }
        );

        // Step 2: Picu force failure
        throw new Error('SIMULATED_NETWORK_FAILURE');
      });
    } catch (err: any) {
      expect(err.message).toBe('SIMULATED_NETWORK_FAILURE');
    } finally {
      await session.endSession();
    }

    // Verifikasi saldo tidak berubah di luar session
    const doc = await db.collection('wallets').findOne({ userId: 'USR_01' });
    expect(doc?.balance).toBe(1000);
  });

  test('Snapshot Isolation: Transaksi luar tidak melihat dirty write sebelum commit', async () => {
    const session: ClientSession = client.startSession();
    const db = client.db('test_isolation');

    session.startTransaction();

    await db.collection('wallets').updateOne(
      { userId: 'USR_01' },
      { $inc: { balance: -200 } },
      { session }
    );

    // Baca dari luar sesi transaksi (Uncommitted state)
    const readOutsideTxn = await db.collection('wallets').findOne({ userId: 'USR_01' });
    expect(readOutsideTxn?.balance).toBe(1000); // Harus tetap nilai lama (Clean Read)

    await session.commitTransaction();
    await session.endSession();

    // Baca setelah commit
    const readAfterCommit = await db.collection('wallets').findOne({ userId: 'USR_01' });
    expect(readAfterCommit?.balance).toBe(800);
  });
});
```

---

## 17. Troubleshooting Guide

| Gejala Masalah | Investigasi Root Cause | Resolusi Tindakan Korektif |
| :--- | :--- | :--- |
| `WriteConflict` (Error Code 112) | Dua transaksi memodifikasi dokumen/indeks yang sama secara konkuren pada storage engine WiredTiger. | Terapkan exponential backoff retry loop; optimalkan struktur dokumen agar operasi pembaruan bersifat spesifik dan menyebar (de-normalize/partitioning). |
| `TransactionExceededLifetimeLimitSeconds` | Transaksi berjalan melebihi batas waktu default MongoDB (60 detik). | Hapus pemanggilan synchronous I/O lambat dari dalam blok transaksi; naikkan nilai server `transactionLifetimeLimitSeconds` hanya jika absolut diperlukan. |
| `LockWaitOutsideTransactionTimeout` | Operasi DDL (seperti pembuatan indeks foreground) sedang menahan Exclusive (`X`) lock pada database/koleksi. | Pastikan pembangunan indeks dilakukan secara background/hybrid default; tunda operasi migration DDL di luar jam operasional puncak. |
| `NoSuchTransaction` | Sesi transaksi telah kedaluwarsa di sisi server karena inaktivitas klien melebihi `maxTransactionLockRequestTimeoutMillis`. | Pastikan seluruh sequence operasi dalam session dieksekusi secara terangkai tanpa delay jeda eksternal yang panjang. |

---

## 18. Checklist Produksi

- [ ] **Topologi:** MongoDB berjalan pada minimal 3-Node Replica Set (Cluster Standalone tidak mendukung Multi-Document Transactions).
- [ ] **Storage Engine:** Memastikan WiredTiger aktif sebagai storage engine default.
- [ ] **Read/Write Concern:** Mengonfigurasi `readConcern: "snapshot"` dan `writeConcern: { w: "majority", j: true }` untuk konsistensi transaksi absolut.
- [ ] **Execution Limits:** Memverifikasi `maxCommitTimeMS` dikonfigurasi pada transaksi untuk membatasi hang coordinator commit.
- [ ] **Retry Engine:** Menggunakan driver helper `withTransaction()` atau custom exponential jitter backoff yang memvalidasi `TransientTransactionError` dan `UnknownTransactionCommitResult`.
- [ ] **Index Coverage:** Semua query di dalam blok transaksi ter-cover 100% oleh B-Tree Index untuk menghindari penahanan range locks luas di WiredTiger.
- [ ] **Transaction Sizing:** Memastikan ukuran payload transaksi tidak melebihi 16MB per batasan Oplog Entry size.
- [ ] **Monitoring Alert:** Mengonfigurasi alert Prometheus/CloudWatch untuk metrik `wiredTiger.concurrentTransactions.write.out` > 80% kapasitas total.

---

## 19. Ringkasan Eksekutif
MongoDB mengimplementasikan arsitektur konkurensi dua lapis yang memisahkan **MongoD Metadata Hierarchical Locks** (IS, IX, S, X) dari **WiredTiger MVCC Document-Level Engine**. Pembacaan bersifat *lock-free* dan tidak memblokir penulisan. 

Transaksi multi-dokumen menyediakan jaminan ACID terdistribusi penuh menggunakan *Snapshot Isolation* dan *Raft-based Majority Consensus*. Meskipun memberikan jaminan data absolut, transaksi memiliki biaya komputasi dan memori yang signifikan (WiredTiger ticketing and cache pressure). Prioritaskan pemodelan data atomik dokumen tunggal (*embedded schema*) dan gunakan transaksi multi-dokumen secara terukur untuk operasi kritis finansial, ledgering, atau state transitions mutlak.

---

## 20. Referensi & Bacaan Lanjutan
1. **MongoDB Manual:** *WiredTiger Storage Engine Concurrency and Lock Modes*
2. **MongoDB Specification:** *Driver Transaction Specification and Error Handling Guidelines*
3. **VLDB Research Paper:** *MongoDB: A Scalable, Document-Oriented Database Engine (Schema & MVCC Deep Dive)*
4. **WiredTiger Architecture Manual:** *Multi-Version Concurrency Control, History Store & Checkpoints Architecture*