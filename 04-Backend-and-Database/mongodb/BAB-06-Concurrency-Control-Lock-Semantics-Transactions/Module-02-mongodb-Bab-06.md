# BAB 06: Concurrency Control, Lock Semantics, & Transactions
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis hierarki penguncian internal MongoDB (*Global*, *Database*, *Collection*) dan bagaimana WiredTiger mengeksekusi *concurrency control* berbasis dokumen (*document-level concurrency*) menggunakan *Multi-Version Concurrency Control* (MVCC).
- Mengidentifikasi dan memitigasi *WiredTiger read/write ticket exhaustion* serta memahami dinamika *checkpointing* versus *snapshot isolation*.
- Mengimplementasikan transaksi terdistribusi multi-dokumen dan multi-shard menggunakan *Two-Phase Commit* (2PC) internal MongoDB dengan penanganan kegagalan atomis (*transient transaction errors* & *unknown commit results*).
- Merancang matriks kombinasi *Read Concern* (`local`, `majority`, `linearizable`, `snapshot`) dan *Write Concern* (`w:1`, `w:majority`, `j:true`) yang menjamin konsistensi data tanpa mengorbankan performa sistem secara katastropik.
- Mendiagnosis dan mengurai insiden *deadlock*, *write conflict loops*, dan *head-of-line blocking* pada kluster produksi berskala masif.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, peserta wajib memiliki:
- Pemahaman mendalam tentang arsitektur replikasi MongoDB (*Replica Sets*, Raft-like consensus engine/raft-based election, Oplog mechanics).
- Pemahaman konsep ACID (*Atomicity, Consistency, Isolation, Durability*) dalam sistem terdistribusi.
- Kemahiran bahasa pemrograman TypeScript/Node.js atau Go untuk berinteraksi dengan MongoDB Driver resmi.
- Akses terminal dengan Docker/Docker Compose terpasang untuk menjalankan kluster Replica Set lokal multi-node.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Hierarki Lock Manager MongoDB
Meskipun MongoDB mengandalkan WiredTiger untuk penanganan dokumen, layer *mongod* (server layer) tetap mempertahankan sistem penguncian hierarkis (*Intent Locks*) untuk mencegah operasi DDL (*Data Definition Language*) merusak operasi DML (*Data Manipulation Language*).

```
                      +-------------------+
                      |    Global (R/W)   |
                      +---------+---------+
                                |
                      +---------v---------+
                      |   Database (r/w)  |
                      +---------+---------+
                                |
                      +---------v---------+
                      |  Collection (r/w) |
                      +---------+---------+
                                |
                      +---------v---------+
                      | Document (WiredTiger MVCC)
                      +-------------------+
```

Tipe lock server layer MongoDB meliputi:
- **IS (*Intent Shared*)**: Menandakan niat membaca data pada granularitas lebih rendah.
- **IX (*Intent Exclusive*)**: Menandakan niat memodifikasi data pada granularitas lebih rendah.
- **S (*Shared*)**: Penguncian baca eksplisit pada level database/koleksi (kompatibel dengan IS/S lain).
- **X (*Exclusive*)**: Penguncian eksklusif mutlak, memblokir seluruh operasi lain (digunakan operasi DDL seperti `drop()`, `repairDatabase`, atau `collMod`).

#### 3.2 WiredTiger Engine: MVCC, Tickets, and Cache Eviction
WiredTiger mengimplementasikan *optimistic concurrency control* via MVCC:
1. **Tiket Konkurensi (*WiredTiger Tickets*)**: Secara default, WiredTiger mengalokasikan 128 tiket baca (*read*) dan 128 tiket tulis (*write*) konkuren. Operasi yang melampaui kuota ini akan masuk ke antrean *wait-queue*.
2. **Snapshot Allocation**: Setiap transaksi dialokasikan ID sekuensial logis. Transaksi membaca versi data yang valid pada saat snapshot dibuat, mengabaikan perubahan *uncommitted* dari transaksi lain (*Snapshot Isolation*).
3. **Write Conflicts**: Jika dua transaksi konkuren mencoba memodifikasi dokumen fisik yang sama (atau halaman B-Tree yang sama dalam kasus DDL/indeks), transaksi yang melakukan *commit* belakangan akan mendeteksi *Write Conflict* (`WriteConflictException`). Server layer MongoDB akan secara otomatis melakukan *retry* secara internal, atau melempar kode eror `TransientTransactionError` ke sisi klien jika berada di dalam transaksi multi-dokumen.
4. **WiredTiger Cache & Eviction Server**: Transaksi yang berjalan terlalu lama (*long-running transactions*) akan menahan pin pada halaman cache memory WiredTiger lama. Hal ini mencegah *eviction server* membersihkan halaman kotor (*dirty pages*), memicu *cache pressure*, degradasi latensi global, hingga *out-of-memory (OOM) kill*.

#### 3.3 Distributed Transactions Architecture (Two-Phase Commit)
Pada kluster *Sharded Cluster*, transaksi multi-shard dikoordinasikan secara otomatis oleh komponen internal:
- **Transaction Coordinator**: Salah satu router `mongos` bertindak sebagai koordinator transaksi.
- **Participants**: Node primary dari setiap shard yang terlibat dalam operasi tulis.
- **Two-Phase Commit Protocol**:
  1. *Prepare Phase*: Koordinator mengirimkan perintah `prepareTransaction` ke semua shard partisipan. Shard partisipan menulis status *prepare* ke oplog lokal mereka dan mengunci dokumen secara durabel.
  2. *Commit Phase*: Jika seluruh partisipan merespons sukses, koordinator menulis entri keputusan commit ke koleksi internal `config.transaction_coordinators` dan menginstruksikan `commitTransaction` ke seluruh partisipan.

```
       Client
         │
         │ (1) Start Transaction & Writes
         ▼
   ┌───────────┐
   │  mongos   │ (Transaction Coordinator)
   └─────┬─────┘
         │
    ┌────┴──────────────────────────┐
    │ (2) prepareTransaction        │ (2) prepareTransaction
    ▼                               ▼
┌──────────────┐             ┌──────────────┐
│ Shard A (Pri)│             │ Shard B (Pri)│
│ State: PREP  │             │ State: PREP  │
└──────┬───────┘             └──────┬───────┘
       │                            │
       └──── (3) Prepare OK ────────┘
                     │
         ┌───────────┴───────────┐
         │ (4) Persist Commit Dec│
         │ (config.trans_coord)  │
         └───────────┬───────────┘
                     │
    ┌────────────────┴──────────────┐
    │ (5) commitTransaction         │ (5) commitTransaction
    ▼                               ▼
┌──────────────┐             ┌──────────────┐
│ Shard A (Pri)│             │ Shard B (Pri)│
│ State: COMM  │             │ State: COMM  │
└──────────────┘             └──────────────┘
```

---

### 4. Why & What

#### Mengapa Tidak Cukup Menggunakan Operasi Dokumen Tunggal?
Operasi atomis level dokumen tunggal (`$inc`, `$set`, `findOneAndUpdate`) adalah pendekatan paling efisien di MongoDB. Namun, pada domain keuangan, logistik pergudangan, dan alokasi kuota, terdapat kondisi absolut di mana beberapa mutasi data harus bersifat atomis lintas batas dokumen dan koleksi (*all-or-nothing*).

#### Apa Itu Snapshot Isolation pada MongoDB?
MongoDB Transaction mengimplementasikan isolasi berbasis snapshot:
- Data yang dibaca oleh transaksi merefleksikan keadaan data saat transaksi dimulai atau saat operasi baca pertama dieksekusi.
- Mencegah fenomena anomali baca: *Dirty Reads*, *Non-repeatable Reads*, dan *Phantom Reads*.
- Tidak menjamin pencegahan *Write Skew* secara otomatis tanpa strategi validasi predikat optimistik (*versioning checking*).

---

### 5. How (Workflow Detail)

Alur eksekusi transaksi terdistribusi enterprise-grade:

1. **Inisialisasi Client Session**:
   Client meminta session logis (`ClientSession`) dari `MongoClient`. Driver mengalokasikan UUID unik yang disertakan pada setiap frame wire-protocol.
2. **Definisi Transaction Options**:
   - `readConcern`: `snapshot` (wajib untuk isolasi konsisten).
   - `writeConcern`: `majority` (wajib untuk mencegah *rollback* pasca-failover).
   - `readPreference`: `primary` (default dan wajib untuk transaksi yang melibatkan penulisan).
   - `maxCommitTimeMS`: Timeout batas waktu fase commit (mencegah koordinator menggantung tanpa batas).
3. **Eksekusi Operasi DML**:
   Query dan pembaruan dijalankan secara berurutan dalam scope session. Driver melacak state sequence number (`txnNumber`).
4. **Transient Error Catching & Commit Retrying**:
   - Tangani `TransientTransactionError`: Seluruh blok transaksi harus diulang dari awal.
   - Tangani `UnknownTransactionCommitResult`: Fase commit harus diulang (`commitTransaction()`) tanpa mengulang operasi logika penulisan, karena keputusan commit mungkin telah berhasil di server tetapi koneksi jaringan terputus sebelum respons diterima klien.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Notaris dan Reservasi Ruang Rapat
Bayangkan sebuah jaringan hotel (*WiredTiger Engine*) dengan ruang rapat (*Dokumen*). 
- **Server Lock (Intent Lock)** adalah resepsionis hotel: Jika Anda ingin merenovasi seluruh lantai (*Drop Collection*), resepsionis memasang tanda palang di pintu masuk lantai (*Exclusive Lock*). Jika Anda hanya menyewa salah satu ruang rapat, resepsionis mencatat niat Anda (*Intent Exclusive*) sehingga renovasi seluruh lantai ditunda, tetapi penyewa ruang lain tetap bisa masuk.
- **WiredTiger MVCC**: Notaris menduplikasi denah ruangan saat Anda masuk (*Snapshot*). Anda mendekorasi denah duplikat tersebut. Jika ada orang lain mencoba mendekorasi ruangan fisik yang sama secara bersamaan, orang yang menyerahkan berkas paling akhir ke notaris akan ditolak (*Write Conflict*) dan diminta mengulang dekorasi dari denah terbaru.

```
       [ REQUEST 1: UPDATE User A ]           [ REQUEST 2: DROP Collection ]
                   │                                        │
                   ▼                                        ▼
         [ Lock: IX Global ]                       [ Lock: X Global ]
                   │                                        │
                   ▼                                        ▼
        [ Lock: IX Database ]                               │
                   │                                        │
                   ▼                                        │
       [ Lock: IX Collection ]                              │
                   │                                        │
                   ▼                                        │
       [ WiredTiger Ticket (Write) ]                        │
                   │                                        │
                   ▼                                        │
   [ MVCC Document In-Memory Buffer ]                       │
                   │                                        │
   [ Write Conflict Detection ]                             │
                   │                                        │
                   │ <------------- BLOCKED BY -------------┘
                   ▼
               [ Commit ]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example (Standard Session Execution)
```typescript
import { MongoClient } from 'mongodb';

async function executeSimpleTx(client: MongoClient) {
  const session = client.startSession();
  try {
    session.startTransaction({
      readConcern: { level: 'snapshot' },
      writeConcern: { w: 'majority' },
    });

    const db = client.db('bank');
    await db.collection('accounts').updateOne(
      { accountId: 'ACC_01' },
      { $inc: { balance: -100 } },
      { session }
    );
    await db.collection('accounts').updateOne(
      { accountId: 'ACC_02' },
      { $inc: { balance: 100 } },
      { session }
    );

    await session.commitTransaction();
  } catch (error) {
    await session.abortTransaction();
    throw error;
  } finally {
    await session.endSession();
  }
}
```

#### 7.2 Practical Example (Enterprise Production-Ready Implementation)
Contoh berikut menggunakan mekanisme *manual retry loop* yang menangani `TransientTransactionError` dan `UnknownTransactionCommitResult` secara deterministik tanpa bergantung penuh pada abstraksi blackbox `withTransaction`.

```typescript
import {
  MongoClient,
  ClientSession,
  MongoError,
  ReadConcernLevel,
  TransactionOptions,
} from 'mongodb';

interface TransferPayload {
  sourceAccountId: string;
  targetAccountId: string;
  amount: number;
  referenceId: string;
}

export class EnterpriseLedgerService {
  constructor(private readonly client: MongoClient) {}

  public async executeFundsTransfer(payload: TransferPayload): Promise<void> {
    const { sourceAccountId, targetAccountId, amount, referenceId } = payload;
    const maxRetries = 5;
    let attempt = 0;

    const txOptions: TransactionOptions = {
      readConcern: { level: ReadConcernLevel.snapshot },
      writeConcern: { w: 'majority', j: true },
      readPreference: 'primary',
      maxCommitTimeMS: 5000,
    };

    while (true) {
      attempt++;
      const session: ClientSession = this.client.startSession();
      try {
        session.startTransaction(txOptions);

        const db = this.client.db('core_ledger');
        const accountsColl = db.collection('accounts');
        const transactionsColl = db.collection('transactions');

        // 1. Cek Idempotensi melalui Reference Log
        const existingTx = await transactionsColl.findOne(
          { referenceId },
          { session }
        );
        if (existingTx) {
          await session.abortTransaction();
          return; // Operasi idempotent, transaksi sudah diproses sebelumnya
        }

        // 2. Potong Saldo Akun Sumber dengan Guard Predikat Saldo
        const sourceUpdate = await accountsColl.updateOne(
          { accountId: sourceAccountId, balance: { $gte: amount } },
          {
            $inc: { balance: -amount },
            $set: { updatedAt: new Date() },
          },
          { session }
        );

        if (sourceUpdate.matchedCount === 0) {
          throw new Error('INSUFFICIENT_FUNDS_OR_SOURCE_NOT_FOUND');
        }

        // 3. Tambah Saldo Akun Tujuan
        const targetUpdate = await accountsColl.updateOne(
          { accountId: targetAccountId },
          {
            $inc: { balance: amount },
            $set: { updatedAt: new Date() },
          },
          { session }
        );

        if (targetUpdate.matchedCount === 0) {
          throw new Error('TARGET_ACCOUNT_NOT_FOUND');
        }

        // 4. Catat Mutasi
        await transactionsColl.insertOne(
          {
            referenceId,
            sourceAccountId,
            targetAccountId,
            amount,
            status: 'COMPLETED',
            timestamp: new Date(),
          },
          { session }
        );

        // 5. Commit dengan Resiliency Loop
        await this.commitWithRetry(session);
        break; // Transaksi sukses
      } catch (error) {
        await session.abortTransaction().catch(() => {});

        if (
          error instanceof MongoError &&
          error.hasErrorLabel('TransientTransactionError') &&
          attempt < maxRetries
        ) {
          const backoff = Math.min(Math.pow(2, attempt) * 100, 2000);
          await new Promise((res) => setTimeout(res, backoff));
          continue; // Retry seluruh transaksi
        }
        throw error;
      } finally {
        await session.endSession();
      }
    }
  }

  private async commitWithRetry(session: ClientSession): Promise<void> {
    const maxCommitRetries = 3;
    let commitAttempt = 0;

    while (true) {
      try {
        await session.commitTransaction();
        return;
      } catch (error) {
        commitAttempt++;
        if (
          error instanceof MongoError &&
          error.hasErrorLabel('UnknownTransactionCommitResult') &&
          commitAttempt < maxCommitRetries
        ) {
          await new Promise((res) => setTimeout(res, 200 * commitAttempt));
          continue; // Retry hanya fase commit
        }
        throw error;
      }
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks
Sebuah platform Neobank memproses 12.000 transaksi pembayaran peer-to-peer per detik pada jam sibuk. MongoDB diatur dalam konfigurasi Sharded Cluster (3 Shard, masing-masing 3-member Replica Set).

#### Permasalahan
Setelah migrasi ke multi-document transactions untuk mutasi saldo, performa anjlok drastis:
1. P99 Latensi melonjak dari 15ms menjadi 2.800ms.
2. Mongod nodes mengalami lonjakan `WiredTiger concurrent read/write tickets available` yang drop mendekati nol (Ticket Exhaustion).
3. Terjadi ratusan eksepsi `WriteConflictException` per detik pada koleksi `accounts`.

#### Root Cause Analysis (RCA)
1. **Hotspotting Transaksi**: Sebagian besar transaksi melibatkan akun merchant pusat yang sama (akibat skema double-entry transfer biaya platform). Ratusan thread mencoba memodifikasi dokumen merchant yang sama di shard yang sama.
2. **Kombinasi Read Concern `snapshot` dan Operasi Lambat**: Transaksi membaca dokumen profil, notifikasi, dan data analytics dalam session yang sama. Hal ini memperpanjang masa aktif transaksi (*long-lived transactions*), menyebabkan WiredTiger menahan snapshot terlalu lama dan memblokir *cache eviction*.

#### Solusi Rekayasa
1. **Split-Transaction Pattern**: Memecah transaksi ACID murni hanya untuk pemotongan saldo pengguna dan pencatatan ledger. Operasi notifikasi, audit analytics, dan agregasi data dipindahkan ke arsitektur asinkron berbasis *Outbox Pattern* + Apache Kafka.
2. **Pecah Hotspot Dokumen (Bucket Sharding / Account Sharding)**: Dokumen saldo merchant dipecah menjadi 10 sub-saldo acak (*sub-balances* `merchant_id#1`, ..., `merchant_id#10`). Pembaruan saldo dilakukan ke salah satu bucket secara acak menggunakan hashing, mengeliminasi perebutan *row-level lock* pada MVCC.
3. **Pemberlakuan `maxTransactionLifetimeLimitSeconds`**: Diturunkan dari 60 detik (default) menjadi 5 detik untuk mencegah *stale snapshots* membebani *cache engine*.

---

### 9. Trade-offs (Arsitektur & Konfigurasi)

| Aspek | Transaksi Multi-Dokumen | Atomic Single-Document Updates (`$inc`, `$set`) |
| :--- | :--- | :--- |
| **Konsistensi Data** | Kuat lintas batas entitas (Snapshot Isolation). | Kuat hanya dalam batas dokumen tunggal. |
| **Throughput (IOPS)** | Rendah - Menengah (~1k - 5k TPS per shard pair). | Sangat Tinggi (>50k TPS per shard pair). |
| **Latensi Eksekusi** | Tinggi (Memerlukan 2-phase coordination, round-trips). | Rendah (Operasi single network round-trip). |
| **Dampak Cache Memory**| Menahan halaman dirty di cache WiredTiger selama sesi. | Eviction dapat langsung berjalan segera pasca operasi. |
| **Resiliensi Jaringan** | Butuh penanganan eksplisit retry commit vs rollback. | Idempoten jika dikombinasikan dengan modifier deterministik. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Common Mistakes
1. **Melakukan Operasi DDL di Dalam Transaksi**: Mengeksekusi pembuatan index (`createIndex`) atau pembuatan koleksi eksplisit di dalam blok transaksi akan memicu kegagalan fatal: `OperationNotSupportedInTransaction`.
2. **Mengabaikan `UnknownTransactionCommitResult`**: Menangkap semua error dan langsung melakukan rollback ketika `commitTransaction()` melempar error koneksi. Hal ini dapat menyebabkan **double spending**, karena transaksi mungkin sebenarnya sudah berhasil di-*commit* di server.
3. **Mengatur Ukuran Transaksi Terlalu Besar**: Batas mutasi Oplog per transaksi adalah 16MB. Memasukkan pembaruan batch ribuan dokumen ke dalam satu transaksi akan melempar error `TransactionTooLargeForCache`.

#### 10.2 Troubleshooting Step-by-Step: Ticket Exhaustion
Saat aplikasi membeku (*hang*) dan throughput MongoDB drop ke 0:

1. **Inspeksi Antrean Tiket**:
   Jalankan perintah berikut di `mongosh`:
   ```javascript
   db.serverStatus().wiredTiger.concurrentTransactions
   ```
   *Output Analysis*: Jika `read.available` atau `write.available` bernilai 0, berarti terjadi *Ticket Starvation*.

2. **Identifikasi Operasi Penyebab Bottleneck**:
   ```javascript
   db.currentOp({
     "active": true,
     "secs_running": { "$gt": 2 }
   })
   ```
   Cari query dengan `waitingForLock: true` atau operasi yang memiliki `transaction.open: true` dengan durasi lama.

3. **Terminasi Sesi Macet**:
   ```javascript
   db.killOp(<opid_dari_currentOp>);
   ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Transaction Duration**: Pastikan durasi transaksi tidak melebihi 2 detik (default MongoDB abort adalah 60 detik; jangan pernah bergantung pada batas maksimum ini).
- [ ] **Read/Write Concern Pairing**: Selalu gunakan `readConcern: 'snapshot'` dan `writeConcern: { w: 'majority' }` untuk transaksi finansial/kritis.
- [ ] **Data Model Alignment**: Desain schema agar 95% mutasi selesai di level dokumen tunggal melalui embedded documents; gunakan transaksi terdistribusi hanya untuk 5% kasus kritis.
- [ ] **Index Coverage**: Pastikan SEMUA query pembacaan dan pembaruan di dalam transaksi menggunakan indeks tertutup (*covered index* / *index scan*). Kegagalan indeks memicu *collection scan* (`COLLSCAN`) yang menahan tiket WiredTiger dan memblokir dokumen lain.
- [ ] **Sharding Alignment**: Usahakan transaksi menyasar shard yang sama (*single-shard transactions*) jika memungkinkan, untuk menghindari overhead *Two-Phase Commit* router.

---

### 12. Hands-on Practice

Simulasi mendalam tentang *Write Conflict* dan *Transaction Retries* secara lokal.

#### Direktori Kerja: `hands-on/m02/`

#### Langkah 1: Siapkan Kluster Replica Set Lokal
Buat file `docker-compose.yml`:
```yaml
version: '3.8'
services:
  mongo-node:
    image: mongo:7.0
    container_name: mongo-tx-lab
    command: ["--replSet", "rs0", "--bind_ip_all"]
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db

volumes:
  mongo-data:
```

Jalankan container dan inisialisasi Replica Set:
```bash
docker compose up -d
sleep 3
docker exec -it mongo-tx-lab mongosh --eval "rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'localhost:27017'}]})"
```

#### Langkah 2: Persiapkan Project Node.js
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
npm init -y
npm install mongodb
```

#### Langkah 3: Eksekusi Simulasi Write Conflict Konkuren
Buat script `simulate_conflict.js`:
```javascript
const { MongoClient } = require('mongodb');

const uri = 'mongodb://localhost:27017/?replicaSet=rs0';
const client = new MongoClient(uri);

async function setupData() {
  await client.connect();
  const db = client.db('tx_lab');
  await db.collection('inventory').drop().catch(() => {});
  await db.collection('inventory').insertOne({ _id: 'ITEM_01', stock: 10 });
  console.log('[Setup] Data initialized: ITEM_01 with stock: 10');
}

async function runWorker(workerId, delayMs) {
  const session = client.startSession();
  try {
    session.startTransaction({
      readConcern: { level: 'snapshot' },
      writeConcern: { w: 'majority' }
    });

    const db = client.db('tx_lab');
    const item = await db.collection('inventory').findOne({ _id: 'ITEM_01' }, { session });
    
    console.log(`[Worker ${workerId}] Read item, current stock: ${item.stock}`);
    
    // Beri jeda untuk memaksa race condition
    await new Promise(r => setTimeout(r, delayMs));

    await db.collection('inventory').updateOne(
      { _id: 'ITEM_01' },
      { $inc: { stock: -1 } },
      { session }
    );

    console.log(`[Worker ${workerId}] Attempting commit...`);
    await session.commitTransaction();
    console.log(`[Worker ${workerId}] Commit SUCCESS!`);
  } catch (error) {
    console.error(`[Worker ${workerId}] Commit FAILED: ${error.message}`);
    if (error.hasErrorLabel && error.hasErrorLabel('TransientTransactionError')) {
      console.error(`[Worker ${workerId}] Detected: TransientTransactionError -> Needs Retry`);
    }
    await session.abortTransaction();
  } finally {
    await session.endSession();
  }
}

async function main() {
  await setupData();
  console.log('[Main] Running two concurrent conflicting transactions...');
  // Worker 1 berjalan dengan delay 1000ms, Worker 2 berjalan dengan delay 500ms
  // Worker 2 akan commit lebih dahulu, menyebabkan Worker 1 mendeteksi Write Conflict
  await Promise.all([
    runWorker('WORKER_1', 1000),
    runWorker('WORKER_2', 500)
  ]);
  
  const finalDoc = await client.db('tx_lab').collection('inventory').findOne({ _id: 'ITEM_01' });
  console.log(`[Main] Final Stock state: ${finalDoc.stock}`);
  await client.close();
}

main().catch(console.error);
```

Jalankan script:
```bash
node simulate_conflict.js
```

Amati log: Worker 1 akan menghasilkan error `WriteConflict` dan melempar label `TransientTransactionError`.

---

### 13. Exercise

#### Level Easy
Buat sebuah script migrasi sederhana yang memindahkan entitas user yang statusnya `INACTIVE` dari koleksi `users` ke koleksi `users_archived` dalam batas satu transaksi ACID. Pastikan jika proses penyimpanan ke `users_archived` gagal, user tidak terhapus dari `users`.

#### Level Medium
Implementasikan fungsi reservasi tiket konser:
- Koleksi `seats` menyimpan dokumen `{ seatNumber: string, status: "AVAILABLE" | "RESERVED", price: number }`.
- Sistem harus mengizinkan pengguna memesan maksimal 4 kursi sekaligus.
- Implementasikan logic menggunakan `client.startSession()` dengan penanganan `WriteConflictException` manual (implementasikan *exponential backoff retry* dengan batas maksimal 3 kali iterasi).

#### Level Hard
Rancang engine *two-phase atomic balance checkout* menggunakan kluster MongoDB dengan Replica Set:
- Sistem mendebit akun pembeli, mengkredit akun penjual, dan memotong *stock* item gudang.
- Jika terjadi kegagalan jaringan acak di tengah eksekusi commit (`simulate socket hang-up`), kode driver harus mengevaluasi status commit menggunakan token session (`txnNumber`) tanpa melakukan duplikasi mutasi saldo.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Database Architect untuk platform Gaming Global. Sistem Anda menangani lelang item virtual langka (*Real-Time Flash Auction*).
- Terdapat 1 buah *Mythic Sword* yang diperebutkan oleh 100.000 pemain dalam jendela waktu 3 detik.
- Setiap penawaran (*bid*) mengharuskan validasi:
  1. Penawaran harus lebih tinggi dari penawaran tertinggi saat ini (`highestBid`).
  2. Saldo koin pemain harus mencukupi dan langsung di-hold.
  3. Saldo pemain yang tersalip (*outbid user*) harus langsung dikembalikan secara real-time.
- MongoDB mengalami lonjakan CPU 100% dan ribuan transaksi dibatalkan akibat Write Conflict masif pada dokumen item yang sama.

**Tugas Arsitektur**:
Rancang arsitektur sistem konkurensi (kombinasi skema data, transaksi MongoDB, dan layer cache/antrean) yang mampu menangani beban lelang ini dengan ketentuan:
1. Data saldo akhir dan pemenang lelang 100% konsisten (zero duplicate deduction).
2. WiredTiger cache tidak mengalami starvation.
3. Tuliskan analisis teknis dan diagram alur sistem mitigasinya, disertai mitigasi anomali transaksi yang mungkin terjadi.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa tingkat isolasi default transaksi multi-dokumen di MongoDB?
   - A. Read Uncommitted
   - B. Read Committed
   - C. Snapshot Isolation
   - D. Serializable
2. Apa yang terjadi jika dua transaksi mencoba menulis pada dokumen yang sama secara bersamaan di WiredTiger?
   - A. Transaksi kedua memblokir hingga transaksi pertama commit tanpa batas waktu
   - B. Salah satu transaksi akan memicu WriteConflictException
   - C. Server MongoDB crash
   - D. Data ditimpa secara otomatis berdasarkan timestamp terbaru (Last-Write-Wins)
3. Berapa batas default ukuran log Oplog untuk satu transaksi di MongoDB?
   - A. Tidak terbatas
   - B. 16 MB
   - C. 32 MB
   - D. 64 MB
4. Operasi mana di bawah ini yang DILARANG di dalam transaksi multi-dokumen MongoDB?
   - A. `collection.updateOne()`
   - B. `collection.createIndex()`
   - C. `collection.find()`
   - D. `collection.insertOne()`
5. Error label apa yang disertakan oleh MongoDB driver jika transaksi gagal akibat konflik sementara dan aman untuk diulang seluruhnya?
   - A. `UnknownTransactionCommitResult`
   - B. `CriticalTransactionFailure`
   - C. `TransientTransactionError`
   - D. `WriteConflictFatalException`

#### Bagian 2: Intermediate (Pilihan Ganda)
6. Kapan label error `UnknownTransactionCommitResult` dilempar oleh driver MongoDB?
   - A. Saat validasi schema dokumen gagal
   - B. Saat terjadi timeout pada pembacaan snapshot
   - C. Saat perintah `commitTransaction` gagal mendapatkan respons dari node database akibat gangguan jaringan
   - D. Saat dokumen yang dicari tidak ditemukan dalam database
7. Jika WiredTiger read tickets tersedia bernilai 0 pada metrik database, apa implikasinya terhadap aplikasi?
   - A. Memori RAM server rusak
   - B. Seluruh operasi baca baru akan masuk antrean tunggu, memicu lonjakan latensi pembacaan
   - C. Transaksi otomatis beralih menggunakan disk swap
   - D. Koleksi otomatis berubah menjadi read-only
8. Peran router `mongos` pada transaksi terdistribusi multi-shard adalah sebagai:
   - A. Storage node
   - B. Arbiter
   - C. Transaction Coordinator
   - D. Replication Master
9. Apa fungsi parameter `maxCommitTimeMS` pada sesi transaksi?
   - A. Membatasi waktu pembacaan query pertama
   - B. Membatasi jendela waktu yang dialokasikan koordinator untuk menyelesaikan fase Two-Phase Commit
   - C. Membatasi waktu pemulihan Replica Set
   - D. Menentukan interval snapshot cache WiredTiger
10. Mengapa operasi DML biasa dianjurkan dibanding transaksi multi-dokumen jika pembaruan dapat dilakukan dalam 1 dokumen?
    - A. Transaksi multi-dokumen tidak aman di Replica Set
    - B. Pembaruan dokumen tunggal sudah atomis secara default dan tidak membebani WiredTiger transaction cache
    - C. Transaksi multi-dokumen tidak mendukung Write Concern `majority`
    - D. Pembaruan dokumen tunggal tidak menggunakan Oplog

#### Bagian 3: Skenario Kasus Produksi
11. **Kasus 1**: Sistem payment gateway Anda menerima lonjakan transaksi saat kampanye diskon. Aplikasi melempar exception:
    `MongoServerError: WriteConflict error: ... please retry your operation or renegotiate concurrency control`.
    Jelaskan langkah mitigasi sistemis yang harus Anda terapkan pada level arsitektur kode aplikasi dan database.
12. **Kasus 2**: DBA Anda mendeteksi bahwa *dirty cache* WiredTiger terus naik hingga menyentuh 95% dan tidak kunjung turun, yang mengakibatkan aplikasi mengalami *read/write stalls*. Setelah diinvestigasi, ada sebuah cron job analitik yang membuka transaksi multi-dokumen dengan `readConcern: 'snapshot'` yang memproses ribuan data selama 15 menit. Jelaskan korelasi teknis antara cron job tersebut dengan fenomena *dirty cache stall*.
13. **Kasus 3**: Pada kluster Sharded Cluster, terjadi *network partition* antara router `mongos` (selaku Transaction Coordinator) dan salah satu shard partisipan persis setelah fase *prepareTransaction* disetujui. Apa kondisi internal yang dialami oleh shard partisipan tersebut, dan apa dampaknya terhadap dokumen yang sedang dikunci pada shard tersebut?

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **C** (Snapshot Isolation).
2. **B** (Salah satu transaksi mendeteksi konflik melalui mekanisme MVCC dan melempar `WriteConflictException`).
3. **B** (16 MB, batas ukuran BSON Oplog entry per transaksi).
4. **B** (Operasi DDL seperti pembuatan index tidak didukung di dalam transaksi).
5. **C** (`TransientTransactionError`).

#### Bagian 2: Intermediate
6. **C** (Ketika status commit tidak dapat dipastikan karena respons jaringan hilang; transaksi mungkin sudah commit atau belum).
7. **B** (Operasi baca tertahan di antrean *wait-queue*, menurunkan throughput dan meningkatkan latensi secara eksponensial).
8. **C** (Sebagai Transaction Coordinator yang mengelola protokol Two-Phase Commit lintas shard).
9. **B** (Menentukan batas waktu maksimal bagi koordinator dan partisipan untuk merampungkan proses commit).
10. **B** (Pembaruan level dokumen tunggal sudah ACID secara atomis dan tidak memerlukan pemeliharaan snapshot session yang memakan cache memori).

#### Bagian 3: Skenario Kasus Produksi
11. **Solusi Kasus 1**:
    - Terapkan retry mechanism dengan *jittered exponential backoff* pada klien saat menangkap `TransientTransactionError`.
    - Lakukan restrukturisasi skema: Gunakan agregasi atau pembagian (*sharding*) counter/saldo ke beberapa dokumen terpisah untuk mendistribusikan penulisan.
    - Kurangi waktu tunggu transaksi dengan memastikan seluruh validasi non-database (misal: validasi format, otentikasi) diselesaikan *sebelum* transaksi dimulai.
12. **Solusi Kasus 2**:
    - WiredTiger mempertahankan snapshot tertua yang masih dibutuhkan oleh transaksi aktif. Cron job analitik yang berjalan 15 menit menahan *oldest snapshot*.
    - Eviction server tidak dapat membersihkan halaman cache yang dimodifikasi setelah titik snapshot tersebut dibuat, karena cron job mungkin masih membutuhkan visibilitas terhadap versi halaman lama.
    - Akibatnya, halaman kotor (*dirty pages*) menumpuk di memori hingga batas ambang kritis (default 20% kotor memicu background eviction, 95% memicu thread throttling / application stall).
    - Mitigasi: Pisahkan job analitik ke node sekunder menggunakan `readPreference: 'secondary'` tanpa transaksi snapshot, atau pecah operasi analitik menjadi batch-batch kecil independen.
13. **Solusi Kasus 3**:
    - Shard partisipan berada dalam state `PREPARED`.
    - Dokumen yang terlibat dalam transaksi pada shard tersebut tetap mengunci *WiredTiger row-level locks* secara persisten di memori.
    - Pembacaan atau penulisan lain dari luar transaksi yang mencoba mengakses dokumen-dokumen yang terkunci tersebut akan terblokir (*blocked*) hingga koordinator pulih dan mengirimkan instruksi resolusi commit atau abort.

---

### 16. Summary
- Konkurensi MongoDB beroperasi pada dua tingkat hierarki: Intent Locks di level server (*mongod*) untuk koordinasi DDL/DML, dan MVCC di level engine (*WiredTiger*) untuk pembacaan dan penulisan konkuren bebas kunci (*lock-free reads*).
- Transaksi terdistribusi multi-dokumen MongoDB menjamin ACID dengan tingkat isolasi Snapshot, dikoordinasikan melalui Two-Phase Commit (2PC) internal.
- Penanganan kegagalan transaksi skala produksi mewajibkan pemisahan antara `TransientTransactionError` (retry seluruh transaksi) dan `UnknownTransactionCommitResult` (retry hanya pemanggilan commit).
- Transaksi yang panjang (*long-running transactions*) adalah anti-pattern utama pada WiredTiger; transaksi harus dirancang sesingkat mungkin untuk menghindari kehabisan tiket (*ticket starvation*) dan penumpukan *cache pressure*.