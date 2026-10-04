# BAB 07: High Availability Replica Set Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis dan Membedah Internal Konsensus MongoDB**: Menguraikan implementasi varian protokol Raft (ProtocolVersion 1 / PV1), siklus *heartbeat*, mekanisme *leader election*, serta mitigasi fenomena *split-brain*.
2. **Menguasai Oplog Engine & Synchronization Pipeline**: Mengkalkulasi *replication lag*, memproyeksikan ukuran *oplog window*, mengonfigurasi *chained replication*, dan menganalisis tahapan *initial sync* berbasis WiredTiger storage engine.
3. **Mengimplementasikan Causal Consistency & Tunable Guarantees**: Mengonfigurasi matriks kombinasi `Read Concern` (`local`, `majority`, `linearizable`, `snapshot`) dan `Write Concern` (`w:1`, `w:majority`, `j:true`, `wtimeout`) untuk menjamin konsistensi ACID lintas node.
4. **Mendesain Arsitektur Multi-Data Center (Multi-DC)**: Merancang topologi *fault-tolerant* lintas zona/region menggunakan *node specialization* (Priority 0, Hidden, Delayed, Non-Voting) dan Tag Sets untuk routing workload analitik dan Disaster Recovery (DR).
5. **Melakukan Production Hardening & Troubleshooting Kritis**: Menangani skenario *oplog exhaustion*, rolling upgrade tanpa downtime, eksekusi pemulihan data *rollback*, dan mitigasi *unintended elections*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- Arsitektur storage engine WiredTiger (Checkpointing, Write-Ahead Log/Journaling, Cache Eviction, B-Tree vs WiredTiger Row Store).
- Dasar-dasar topologi Replica Set MongoDB (Primary, Secondary, Arbiter) dan administrasi dasar via `mongosh`.
- Konsep dasar sistem terdistribusi: CAP Theorem, PACELC Theorem, Network Partitions, RPC, dan soket TCP/IP.
- Kemampuan dasar Containerization (Docker/Docker Compose) dan Linux System Administration (I/O stats, network emulation via `tc`/`iptables`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Konsensus & Election Protocol (PV1)
MongoDB Replica Set menggunakan protokol konsensus **ProtocolVersion 1 (PV1)**, yang mengadaptasi prinsip dasar algoritma Raft dengan optimasi khusus untuk database operasional.

```
+-------------------------------------------------------------------+
|                         PV1 ELECTION FLOW                         |
+-------------------------------------------------------------------+
  Candidate (Node B)                  Voter (Node A)     Voter (Node C)
        |                                   |                  |
        |--- (1) Dry-Run Election (Pre-Vote)------------------>|
        |<-- (2) Pre-Vote OK (Term check, Oplog fresh)---------|
        |                                   |                  |
        |--- (3) Real Vote Request (Term + 1)----------------->|
        |<-- (4) Vote Granted (Strict Majority Quorum)---------|
        |                                   |                  |
   [BECOMES PRIMARY]                        |                  |
        |--- (5) Heartbeat (I am Leader)---------------------->|
```

- **Heartbeat & Failover Detection**: Setiap anggota replica set mengirimkan paket *heartbeat* (UDP-like ping via TCP connection pool) setiap **2 detik** ke seluruh anggota lainnya. Jika sebuah node tidak merespons dalam window **10 detik** (`electionTimeoutMillis = 10000`), status node tersebut dinyatakan *unreachable*.
- **Pre-Vote Phase (Dry-Run)**: Untuk mencegah disrupsi akibat intermitensi jaringan transien, kandidat menjalankan *dry-run election*. Node hanya akan menaikkan `term` jika node tersebut berhasil memverifikasi bahwa ia dapat memperoleh kuorum mayoritas.
- **Strict Majority Quorum**: Pemilihan Primary membutuhkan suara dari mayoritas anggota yang dapat memilih:
  $$\text{Quorum} = \lfloor \frac{N}{2} \rfloor + 1$$
  Di mana $N$ adalah total node voting yang dikonfigurasi (`votes: 1`). Jika partisi jaringan membuat kuorum tidak tercapai, Primary yang sedang aktif akan otomatis *step down* menjadi Secondary.
- **Log Freshness Comparison**: Node pemilih akan menolak vote jika oplog milik kandidat lebih lama dari oplog miliknya. Komparasi dilakukan secara hierarkis:
  1. Nilai `Term` pada entri oplog terakhir kandidat vs pemilih (yang lebih tinggi menang).
  2. Nilai `Timestamp` entri oplog jika `Term` identik.

#### 3.2. Oplog Internals & Synchronization Pipeline
Oplog (`local.oplog.rs`) adalah *capped collection* khusus yang dikelola langsung oleh WiredTiger. Oplog tidak menyimpan raw command secara mentah, melainkan menyimpan mutasi data yang bersifat **idempoten** (*idempotent*). Misalnya, operasi `$inc` diterjemahkan menjadi operasi `$set` spesifik terhadap field dan nilai mutlaknya di oplog.

```
Write Pipeline:
Client -> Primary WT Cache -> Journal Flush -> local.oplog.rs -> Sync to Secondaries
                                                                        |
Secondaries: Fetch (getMore) -> WT Cache -> Batch Apply -> Journal Flush
```

- **Oplog Fetching Architecture**: Secondary membaca oplog Primary (atau Secondary lain jika *chained replication* aktif) menggunakan kueri *tailable cursor* internal via perintah `getMore`.
- **Parallel Application Batching**: Secondary mengelompokkan entri oplog ke dalam *batch* dan menerapkannya secara paralel menggunakan worker threads yang dipartisi berdasarkan *document hashing* (`_id`) untuk mencegah data hazard (*write-after-read/write-after-write*).
- **Commit Point Progression**: Primary memantau `lastCommittedOpTime` dari seluruh Secondary melalui paket heartbeat balik. Nilai *majority commit point* diperbarui secara dinamis saat entri oplog telah direplikasi ke mayoritas node.

#### 3.3. Deep Dive Read Concern & Write Concern

##### Write Concern Matrix
Mendefinisikan level konfirmasi sebelum Primary mengirimkan respons ACK ke aplikasi:
- `w: 1`: ACK dikirimkan segera setelah operasi ditulis ke memory/cache WiredTiger milik Primary. Berisiko *data loss* jika Primary mengalami hard-crash sebelum commit point direplikasi.
- `w: "majority"`: ACK hanya dikirimkan setelah mutasi tersimpan di memori mayoritas node voting replica set.
- `j: true`: Menjamin mutasi telah diflush secara fisik ke *on-disk Journal* sebelum ACK diberikan.
- `wtimeout`: Menetapkan batas waktu maksimum eksekusi replikasi sebelum mengembalikan network error (mencegah thread client terblokir permanen).

##### Read Concern Spectrum
- `local`: Mengembalikan data terbaru dari instance lokal tanpa cross-node validation. Rentan membaca *dirty reads* data yang berpotensi di-rollback jika terjadi failover.
- `available`: Sama dengan `local` pada Replica Set, namun tidak memeriksa orphan documents pada lingkungan Sharded Cluster.
- `majority`: Mengembalikan data dari snapshot memory yang sudah dikonfirmasi oleh mayoritas anggota replica set. Kebal terhadap failover rollback.
- `linearizable`: Menjamin pembacaan mutlak realtime dengan memaksa Primary melakukan verifikasi *read-time heartbeat* ke mayoritas node untuk membuktikan bahwa dirinya masih merupakan Primary yang sah. Menghindari *stale reads* akibat isolated network partition.
- `snapshot`: Mengisolasi transaksi multi-dokumen dengan point-in-time snapshot WiredTiger engine. Menghindari fenomena *phantom reads* dan *non-repeatable reads*.

---

### 4. Why & What

| Dimensi | Pendekatan Standar (Naive Replication) | Enterprise Replica Set (MongoDB PV1 + Multi-DC) |
| :--- | :--- | :--- |
| **Model Replikasi** | Asynchronous Master-Slave biasa tanpa verifikasi kuorum. | Consensus-driven Majority Replication dengan granularitas `Read/Write Concern`. |
| **Mitigasi Split-Brain** | Manual intervention / VIP failover; rentan split-brain ganda. | Formal voting protocol via PV1; Primary mengisolasi diri jika kuorum $\le N/2$. |
| **Isolasi Workload** | Read-slave pooling acak tanpa awareness topologi latency. | Tag sets, Read Preferences, Hidden Nodes khusus untuk batch reporting/ETL. |
| **Disaster Recovery** | Restore dari cold backup harian (RPO tinggi). | Dedicated Delayed Replica Set member (RPO deterministik, RTO instan). |
| **Durabilitas Data** | Fire-and-forget atau single node journal write. | Strict cross-datacenter disk journaled confirmation (`w: "majority", j: true`). |

---

### 5. How (Workflow Detail)

#### Alur Eksekusi Write Transaksional End-to-End
```
[Client]                [Primary]               [Secondary A]           [Secondary B]
   |                        |                         |                       |
   |--- (1) Write Request ->|                         |                       |
   |    (w:majority,j:true) |                         |                       |
   |                        |--- (2) Write WT Cache   |                       |
   |                        |--- (3) Flush Journal    |                       |
   |                        |--- (4) Append to Oplog  |                       |
   |                        |                         |                       |
   |                        |<-- (5) Fetch Oplog -----|                       |
   |                        |    (getMore Command)    |<-- (5) Fetch Oplog ---|
   |                        |                         |                       |
   |                        |--- (6) Push Oplog ----->|                       |
   |                        |                         |--- (6) Push Oplog --->|
   |                        |                         |--- (7) Batch Apply    |
   |                        |                         |--- (8) Flush Journal  |
   |                        |<-- (9) Heartbeat Ack ---|                       |
   |                        |    (opTime Advanced)    |                       |
   |                        |                         |<-- (9) Heartbeat Ack -|
   |                        |                         |    (opTime Advanced)  |
   |                        |                                                 |
   |                        |-- [Evaluate Majority Quorum: PASSED]            |
   |<-- (10) ACK Response --|                                                 |
```

1. **Client Dispatch**: Driver mengirimkan payload BSON berisi operasi mutasi beserta konfigurasi write concern ke Primary.
2. **Primary In-Memory Processing**: Primary memvalidasi skema, mengunci dokumen via WiredTiger Concurrency Control, menulis ke cache in-memory, dan mencatat mutasi ke *WiredTiger Write-Ahead Log (WAL)*.
3. **Oplog Generation**: Driver WiredTiger menulis perubahan idempoten ke koleksi `local.oplog.rs`.
4. **Replication Polling**: Thread replikasi pada Secondary mengeksekusi operasi `getMore` terhadap kursor oplog Primary.
5. **Data Ingestion & Application**: Secondary menerima batch oplog, menyimpannya ke memori, mendistribusikannya ke thread pool paralel untuk dieksekusi secara idempotent, lalu melakukan flush journal lokal jika `j: true`.
6. **Progress Vector Heartbeat**: Secondary mengirim metadata status kemajuan berupa struktur `OpTime` (Timestamp + Term) kembali ke Primary via heartbeat terkompresi.
7. **Majority Confirmation**: Saat akumulasi node (termasuk Primary) yang telah memproses `OpTime` tersebut mencapai $\lfloor N/2 \rfloor + 1$, Primary mengeksekusi komitmen state dan mengembalikan status *success* ke Client.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sidang Direksi Korporasi Multinasional (Board of Directors)
Bayangkan sebuah dewan direksi yang terdiri dari 5 anggota pemegang hak suara:
- **Primary** adalah Ketua Dewan (Chairman). Segala keputusan bisnis diajukan kepadanya.
- **Oplog** adalah Buku Notulen Resmi Notaris. Notulen tidak mencatat perdebatan, melainkan hasil akhir keputusan ("Kas perusahaan diubah dari \$10M menjadi \$12M").
- **Secondary Nodes** adalah Direktur Anggota. Mereka terus-menerus menyalin lembaran notulen notaris ke buku catatan kerja mereka masing-masing.
- **Heartbeat & Failover**: Setiap 2 menit, para direktur saling menelepon. Jika Chairman terserang serangan jantung mendadak (unreachable > 10 detik), para direktur segera mengadakan rapat darurat (*Election*). Siapa direktur yang memiliki catatan notulen paling lengkap dan paling mutakhir yang berhak mencalonkan diri sebagai Chairman baru. Jika hanya 2 dari 5 orang yang hadir di ruangan rapat darurat, mereka dilarang mengambil keputusan karena tidak memenuhi kuorum mayoritas legal (minimal 3 orang).

#### Arsitektur Fisik Multi-DC Enterprise
```
+-----------------------------------------------------------------------------------+
| REGION 1: Primary Data Center (Production Writes & Reads)                         |
|                                                                                   |
|  +---------------------------+             +---------------------------+          |
|  | Node-01 (Primary)         |             | Node-02 (Secondary)       |          |
|  | Priority: 2               |             | Priority: 1               |          |
|  | Votes: 1                  |             | Votes: 1                  |          |
|  | Tags: {dc:"dc1", use:"tx"}|             | Tags: {dc:"dc1", use:"tx"}|          |
|  +-------------+-------------+             +-------------+-------------+          |
|                |                                         |                        |
+----------------|-----------------------------------------|------------------------+
                 |            INTER-DC LINK (Low Latency)  |
                 |                                         |
+----------------|-----------------------------------------|------------------------+
| REGION 2: Disaster Recovery & Analytics Data Center      |                        |
|                |                                         |                        |
|  +-------------+-------------+             +-------------+-------------+          |
|  | Node-03 (Secondary)       |             | Node-04 (Hidden / Analytics)         |
|  | Priority: 0.5             |             | Priority: 0, Hidden: true |          |
|  | Votes: 1                  |             | Votes: 0                  |          |
|  | Tags: {dc:"dc2", use:"dr"}|             | Tags: {dc:"dc2", use:"an"}|          |
|  +---------------------------+             +---------------------------+          |
|                                                                                   |
|  +---------------------------------------------------------------------+          |
|  | Node-05 (Delayed Secondary - Standby DR)                            |          |
|  | Priority: 0, Hidden: true, Votes: 0, slaveDelay: 3600 (1 Hour)      |          |
|  | Tags: {dc:"dc2", use:"backup"}                                      |          |
|  +---------------------------------------------------------------------+          |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Rekonfigurasi Replica Set via `mongosh`
Berikut adalah inisialisasi skrip rekonfigurasi runtime untuk mengubah replica set 3-node standar menjadi arsitektur berbasis bobot prioritas dan tag metadata.

```javascript
// Dijalankan di mongosh instance Primary
let config = rs.conf();

// Pastikan version dinaikkan
config.members[0].priority = 2; // Node-01 diprioritaskan menjadi Primary
config.members[0].tags = { "dc": "jakarta", "workload": "transactional" };

config.members[1].priority = 1; // Node-02 Secondary failover tier 1
config.members[1].tags = { "dc": "jakarta", "workload": "transactional" };

config.members[2].priority = 0; // Node-03 TIDAK BISA menjadi Primary (Passive/DR)
config.members[2].tags = { "dc": "singapore", "workload": "disaster-recovery" };

// Terapkan rekonfigurasi topologi dengan validasi quorum
let status = rs.reconfig(config, { force: false });
printjson(status);
```

#### 7.2. Practical Example: Enterprise Node.js Service dengan Causal Consistency
Implementasi layer data service menggunakan driver resmi Node.js (`mongodb`) yang menerapkan session terisolasi, causal consistency, explicit write concern, serta read preferences berbasis tag targeting.

```typescript
import { MongoClient, ReadPreference, ClientSession, TransactionOptions } from 'mongodb';

interface LedgerEntry {
    accountId: string;
    amount: number;
    transactionType: 'DEBIT' | 'CREDIT';
    timestamp: Date;
}

class EnterpriseLedgerService {
    private client: MongoClient;
    private readonly dbName = "fintech_core";

    constructor(uri: string) {
        this.client = new MongoClient(uri, {
            // Konfigurasi Connection Pool Enterprise
            maxPoolSize: 100,
            minPoolSize: 20,
            maxIdleTimeMS: 30000,
            serverSelectionTimeoutMS: 5000,
            // Mode Heartbeat Tunable
            heartbeatFrequencyMS: 2000,
            // Write concern default cluster-level
            w: 'majority',
            wtimeoutMS: 5000,
            journal: true,
        });
    }

    public async connect(): Promise<void> {
        await this.client.connect();
        console.log("Connected successfully to Enterprise Replica Set Fabric");
    }

    /**
     * Menjalankan transfer finansial dengan Causal Consistency guarantees
     * Melindungi dari dirty reads, phantom writes, dan stale reads lintas node.
     */
    public async recordFinancialTransaction(entry: LedgerEntry): Promise<void> {
        // Inisialisasi Causal Consistent Session
        const session: ClientSession = this.client.startSession({
            causalConsistency: true,
            defaultTransactionOptions: {
                readConcern: { level: 'snapshot' },
                writeConcern: { w: 'majority', j: true, wtimeoutMS: 4000 }
            }
        });

        try {
            await session.withTransaction(async () => {
                const db = this.client.db(this.dbName);
                const ledgerColl = db.collection<LedgerEntry>('general_ledger');
                const accountColl = db.collection('accounts');

                // 1. Catat Transaksi Finansial
                await ledgerColl.insertOne(entry, { session });

                // 2. Mutasi Saldo Akun dengan kueri berakar sama dalam snapshot isolation
                const balanceAdjustment = entry.transactionType === 'CREDIT' ? entry.amount : -entry.amount;
                const updateRes = await accountColl.updateOne(
                    { accountId: entry.accountId },
                    { 
                        $inc: { balance: balanceAdjustment },
                        $set: { lastUpdated: new Date() }
                    },
                    { session }
                );

                if (updateRes.matchedCount === 0) {
                    throw new Error(`CRITICAL: Akun ${entry.accountId} tidak ditemukan. Membatalkan mutasi.`);
                }
            });
        } catch (error) {
            console.error("Gagal mengeksekusi enterprise ledger transaction:", error);
            throw error;
        } finally {
            await session.endSession();
        }
    }

    /**
     * Membaca ledger khusus untuk reporting ETL tanpa membebani primary
     * Mengarahkan queries secara eksklusif ke analytics node via ReadPreference Tag Sets.
     */
    public async generateAuditReport(accountId: string): Promise<LedgerEntry[]> {
        const db = this.client.db(this.dbName);
        const ledgerColl = db.collection<LedgerEntry>('general_ledger');

        // Preferensikan Secondary di region DR yang dialokasikan khusus analytics
        const customReadPref = new ReadPreference(ReadPreference.SECONDARY, [
            { workload: 'analytics' },
            { dc: 'singapore' }
        ]);

        return await ledgerColl.find(
            { accountId },
            { 
                readPreference: customReadPref,
                readConcern: { level: 'majority' }
            }
        ).toArray();
    }

    public async shutdown(): Promise<void> {
        await this.client.close();
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Payment Gateway Skala Global (50.000 Transaksi / Detik)
- **Konteks**: Platform pemrosesan pembayaran fintech memproses 50.000 TPS pada jam sibuk. Infrastruktur terbagi di antara dua Data Center utama (DC1 - Jakarta, DC2 - Cikarang) dan satu Cloud Region (AWS AP-Southeast-3) sebagai Disaster Recovery.
- **Insiden Kegagalan (P1)**: Terjadi *fiber cut* pada jaringan inter-DC antara Jakarta dan Cikarang selama 120 detik. Beban aplikasi diarahkan ke DC1, namun koneksi TCP transien ke DC2 menghasilkan packet loss 40%. Driver aplikasi mengalami *thread starvation* masif (semua socket pool penuh) yang memicu *cascading outage* di backend microservices.
- **Root Cause Analysis (RCA)**:
  1. Aplikasi mengeksekusi operasi dengan `{ w: "majority" }` tanpa menetapkan `wtimeout`. Saat partisi inter-DC terjadi, Primary menunggu replikasi ke node DC2 yang *unresponsive* hingga socket pool habis.
  2. Aplikasi membaca data transaksi dari Secondary terdekat menggunakan `readPreference: "nearest"` dengan `readConcern: "local"`. Hal ini memicu pembacaan data *stale* (kadaluarsa hingga 45 detik) karena *replication lag* Secondary melonjak tinggi selama degradasi jaringan.
- **Solusi Arsitektural Terapan**:
  1. **Konfigurasi Write Constraint**: Diterapkan `wtimeoutMS: 3000` pada seluruh write operations di level driver. Jika replikasi *majority* terhambat degradasi cross-DC, operasi gagal secara *fast-fail*, sirkuit proteksi (Circuit Breaker) aktif, dan antrean write dialihkan ke buffer Kafka.
  2. **Topologi Priority Tuning**:
     - 2 Node di Jakarta (DC1): Node-01 (Priority 2), Node-02 (Priority 1.5).
     - 2 Node di Cikarang (DC2): Node-03 (Priority 1), Node-04 (Priority 1).
     - 1 Node di Cloud (DC3): Node-05 (Priority 0.5) sebagai *tie-breaker majority arbiter of data* (membawa data penuh, bukan arbiter biasa).
  3. **Read Path Hardening**: Mengubah seluruh aliran transaksi state-sensitive menjadi `readConcern: "majority"` dengan `readPreference: "primary"`, membatasi read preference `secondaryPreferred` hanya pada pipeline pelaporan akhir hari (EOD Report) via Node terisolasi ber-tagging `{ use: "batch" }`.

---

### 9. Trade-offs

| Parameter Desain | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Write Durability** | `w: 1` (Fast Ack) | `w: "majority", j: true` (Safe Ack) | Opsi A menghasilkan latensi write sub-milidetik, namun berisiko kehilangan data permanen (*data loss*) jika terjadi failover mendadak. Opsi B menjamin zero-data-loss, namun latensi dibatasi oleh RTT jaringan lintas node terlama. |
| **Read Scalability** | Secondary Reads (`readPreference: secondary`) | Primary-Only Reads (`readPreference: primary`) | Opsi A memperbesar throughput pembacaan secara horizontal, namun memperkenalkan fenomena *stale reads* (eventual consistency). Opsi B menjamin data selalu mutakhir, namun skala sistem terbatas pada *compute/memory* single primary node. |
| **Oplog Buffer Capacity** | Small Oplog (5% total storage) | Large Oplog (30-50% storage) | Opsi A menghemat biaya disk, namun jika terjadi network downtime singkat, Secondary akan jatuh ke status `RECOVERING` (Oplog exhaustion) dan memerlukan resync total. Opsi B mengonsumsi biaya I/O dan storage besar, namun memberikan toleransi downtime maintenance berjam-jam. |
| **Replication Path** | Direct Replication (`chainingAllowed: false`) | Chained Replication (`chainingAllowed: true`) | Opsi A mengurangi latency replikasi total, tetapi menaikkan saturasi bandwidth network dan CPU thread pada node Primary. Opsi B menghemat bandwidth Primary dengan membiarkan Secondary sync dari Secondary lain, tetapi meningkatkan akumulasi replication lag di ujung rantai. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Fatal (Anti-Patterns)
1. **Menggunakan Arbiter di Lingkungan Produksi**:
   - *Problem*: Menggunakan konfigurasi 2-Data Nodes + 1 Arbiter untuk menghemat biaya lisensi/server.
   - *Dampak*: Arbiter tidak menyimpan data. Jika 1 Data Node mati, data set Anda berjalan dalam mode *single-point-of-failure* tanpa backup fisik replika. Menghilangkan kemampuan menggunakan `readConcern: "majority"` secara reliabel karena jumlah data bearer tidak memenuhi syarat durabilitas mayoritas.
2. **Tidak Menentukan `wtimeout` pada Mode `majority`**:
   - *Problem*: `db.collection.insertOne({ ... }, { writeConcern: { w: "majority" } })`.
   - *Dampak*: Jika replica set kehilangan kuorum replikasi, koneksi client akan terblokir (*hang*) selamanya hingga soket timeout level OS (biasanya puluhan menit), menguras *connection pool* aplikasi dan melumpuhkan sistem secara keseluruhan.
3. **Ketidaksesuaian Ukuran Disk Index Antar Node**:
   - *Problem*: Secondary memiliki memory/disk I/O lebih kecil daripada Primary.
   - *Dampak*: Secondary tidak mampu mengejar laju *apply-oplog batch*, memicu pembesaran *replication lag* tak terbatas hingga Secondary terlempar dari status sinkronisasi.

#### Runbook Troubleshooting Kritis

##### Kasus A: Replication Lag Membengkak
Jalankan perintah berikut di `mongosh`:
```javascript
// Cek status detail replikasi dan lag relative
rs.printSecondaryReplicationInfo();

// Output:
// source: secondary-01:27017
// syncedTo: Mon Oct 23 2023 10:15:20 GMT+0700
// 120 secs behind the primary 
```
*Langkah Remediasi*:
1. Periksa utilisasi disk I/O di Secondary menggunakan `iostat -x 1 10`. Jika disk queue saturation mendekati 100%, optimalkan IOPS storage instance.
2. Periksa parameter chaining: `rs.status().members[n].syncSourceHost`. Jika Secondary melakukan sync ke node yang lambat, paksa ubah *sync source*:
   ```javascript
   db.adminCommand({ replSetSyncFrom: "primary-fast-node:27017" });
   ```

##### Kasus B: Deteksi dan Investigasi Rollback Data
Saat node Secondary yang tertinggal dipromosikan (misal akibat partisi jaringan) lalu Primary lama kembali online, Primary lama tersebut akan mengeksekusi operasi **Rollback** untuk membatalkan mutasi lokal yang belum ter-ack ke mayoritas.
1. Lokasi file rollback: File dokumen yang di-rollback secara otomatis diekstraksi ke direktori data WiredTiger:
   `<dbpath>/rollback/<collection_uuid>/*.bson`
2. Gunakan utility `bsondump` untuk membedah data yang hilang:
   ```bash
   bsondump /data/db/rollback/fintech_core.general_ledger/*.bson > recovered_records.json
   ```
3. Suntikkan kembali data via script reconciliation berbasis `_id`.

---

### 11. Best Practices (Production Checklist)

#### Hardware & OS Layer
- [ ] **Filesystem**: Gunakan format XFS pada Linux OS (WiredTiger bekerja sub-optimal pada ext4 saat beban konkurensi write tinggi karena *allocation lock issues*).
- [ ] **Disable THP (Transparent Huge Pages)**: Wajib mematikan THP (`echo never > /sys/kernel/mm/transparent_hugepage/enabled`) guna mencegah *cache allocation latency spikes* dan memory fragmentation.
- [ ] **Disk Swappiness**: Set `vm.swappiness = 1` pada `/etc/sysctl.conf`.
- [ ] **Dedicated Storage IOPS**: Alokasikan volume SSD Enterprise/NVMe dengan performa minimal 5.000 IOPS untuk storage data directory, dan volume fisik terpisah untuk WiredTiger journal jika TPS $> 10.000$.

#### Configuration Layer (`mongod.conf`)
- [ ] **Oplog Sizing**: Alokasikan ukuran oplog statis yang menjamin window waktu minimal 72 jam:
  ```yaml
  replication:
    replSetName: "prod-cluster-01"
    oplogSizeMB: 102400 # 100 GB Oplog
    enableMajorityReadConcern: true
  ```
- [ ] **Security Authentication**: Aktifkan internal cluster authorization menggunakan X.509 certificates atau minimal Keyfile 1024-bit:
  ```yaml
  security:
    keyFile: /etc/mongodb/pki/cluster-keyfile
    authorization: "enabled"
  ```
- [ ] **Network Binding**: Hindari binding ke `0.0.0.0`. Gunakan CIDR IP Private/Internal VPC:
  ```yaml
  net:
    port: 27017
    bindIp: 10.0.10.15,127.0.0.1
    tls:
      mode: requireTLS
      certificateKeyFile: /etc/ssl/mongodb.pem
      CAFile: /etc/ssl/ca.pem
  ```

---

### 12. Hands-on Practice: Simulasi Multi-Node HA, Partitioning & Failover

Sesi hands-on ini mendemonstrasikan secara langsung cara membangun arsitektur Replica Set multi-node tingkat lanjut, menyuntikkan latensi jaringan, mengonfigurasi node spesialisasi, serta menganalisis mitigasi failover.

Simpan seluruh artefak praktikum ini di direktori: `hands-on/m02/`

#### Langkah 1: Siapkan Orchestration Topology
Buat file `hands-on/m02/docker-compose.yaml` berikut:

```yaml
version: '3.8'

services:
  mongo-primary:
    image: mongo:7.0
    container_name: mongo-primary
    command: ["mongod", "--replSet", "rs-enterprise", "--bind_ip_all"]
    ports:
      - "27017:27017"
    networks:
      enterprise-net:
        ipv4_address: 172.28.0.11

  mongo-secondary:
    image: mongo:7.0
    container_name: mongo-secondary
    command: ["mongod", "--replSet", "rs-enterprise", "--bind_ip_all"]
    ports:
      - "27018:27017"
    networks:
      enterprise-net:
        ipv4_address: 172.28.0.12

  mongo-dr:
    image: mongo:7.0
    container_name: mongo-dr
    command: ["mongod", "--replSet", "rs-enterprise", "--bind_ip_all"]
    ports:
      - "27019:27017"
    networks:
      enterprise-net:
        ipv4_address: 172.28.0.13

networks:
  enterprise-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

Jalankan container:
```bash
docker compose -f hands-on/m02/docker-compose.yaml up -d
```

#### Langkah 2: Inisialisasi & Konfigurasi Specialist Node
Buat file script setup `hands-on/m02/init-cluster.js`:

```javascript
// Sambungkan ke mongo-primary (localhost:27017)
rs.initiate({
  _id: "rs-enterprise",
  members: [
    { _id: 0, host: "172.28.0.11:27017", priority: 2, tags: { zone: "main", role: "transact" } },
    { _id: 1, host: "172.28.0.12:27017", priority: 1, tags: { zone: "main", role: "transact" } },
    { 
      _id: 2, 
      host: "172.28.0.13:27017", 
      priority: 0,          // Tidak boleh terpilih menjadi primary
      secondaryDelaySecs: 60, // Delay 60 detik untuk Disaster Recovery
      hidden: true,         // Tersembunyi dari query client biasa
      tags: { zone: "remote", role: "dr" } 
    }
  ]
});
```

Eksekusi skrip ke cluster:
```bash
docker exec -i mongo-primary mongosh --port 27017 < hands-on/m02/init-cluster.js
```

#### Langkah 3: Verifikasi Oplog Delay & State Durability
1. Masuk ke Primary dan inject data transaksi:
   ```bash
   docker exec -it mongo-primary mongosh --eval '
     use testdb;
     db.critical_data.insertOne({ transactionId: "TX-9901", amount: 5000000, createdAt: new Date() });
   '
   ```
2. Periksa langsung pada node Secondary standar (`mongo-secondary`):
   ```bash
   docker exec -it mongo-secondary mongosh --eval '
     use testdb;
     db.critical_data.findOne({ transactionId: "TX-9901" });
   '
   # Data LANGSUNG TERSEDIA secara near-realtime.
   ```
3. Periksa pada node DR (`mongo-dr`):
   ```bash
   docker exec -it mongo-dr mongosh --eval '
     use testdb;
     db.critical_data.findOne({ transactionId: "TX-9901" });
   '
   # Mengembalikan null (Data tertahan sesuai window delay 60 detik).
   ```
4. Tunggu 60 detik, eksekusi ulang kueri pada node DR. Dokumen sekarang telah berhasil diaplikasikan secara otomatis.

#### Langkah 4: Simulasi Failover & Oplog Window Inspection
1. Pantau status window oplog:
   ```bash
   docker exec -it mongo-primary mongosh --eval 'rs.printReplicationInfo();'
   ```
2. Matikan Primary secara paksa:
   ```bash
   docker stop mongo-primary
   ```
3. Pantau status promosi pada `mongo-secondary`:
   ```bash
   docker exec -it mongo-secondary mongosh --eval 'rs.status().members.forEach(m => print(m.name + ": " + m.stateStr));'
   ```
   *Hasil*: `mongo-secondary` secara otomatis bertransformasi status menjadi `PRIMARY` via voting murni karena kuorum mayoritas tercapai ($\lfloor 3/2 \rfloor + 1 = 2$ node voting tersisa). Node DR yang memiliki `priority: 0` tetap menyumbangkan suaranya untuk pemilihan, namun menolak menjadi primary.

---

### 13. Exercise

#### Level Easy
Konfigurasikan Replica Set lokal yang terdiri dari 3 node. Ubah nilai `electionTimeoutMillis` dari default 10.000 ms menjadi 5.000 ms via `rs.reconfig()`. Lakukan validasi menggunakan `rs.conf()` untuk membuktikan parameter telah persisten.

#### Level Medium
Sebuah sistem database mencatat mutasi data berukuran 8 MB per detik selama jam sibuk (peak). Anda diminta:
1. Menghitung ukuran minimum Oplog (dalam Gigabyte) agar replica set mampu mempertahankan toleransi kegagalan jaringan Secondary selama 48 jam berturut-turut tanpa kehilangan posisi replikasi.
2. Tuliskan syntax MongoDB shell untuk me-resize oplog cluster runtime menjadi ukuran kalkulasi tersebut tanpa melakukan restart service database.

#### Level Hard
Skenario Partisi Jaringan (*Network Split Simulation*):
Terdapat Replica Set 5-Node (Node-01 s/d Node-05). Gunakan utility `iptables` di lingkungan Linux VM / Docker Network untuk membagi cluster menjadi dua partisi terisolasi:
- Komponen Partisi A: Node-01, Node-02.
- Komponen Partisi B: Node-03, Node-04, Node-05.
Simulasikan write serentak ke kedua partisi menggunakan driver dengan kombinasi `{ w: 1 }` dan `{ w: "majority" }`. Buktikan partisi mana yang menolak penulisan majority, partisi mana yang melakukan pemilihan primary baru, dan buktikan mekanisme *reconciliation rollback* yang terjadi saat partisi jaringan disatukan kembali!

---

### 14. Challenge

#### Skenario Arsitektur Misi Kritis (Zero-Downtime Migration & Split-Zone DR)
Anda adalah Lead Database Architect untuk institusi perbankan. Anda memiliki kluster MongoDB 5-node aktif yang berjalan di datacenter on-premise (*Region Jakarta*) dengan total ukuran data 15 TB dan beban transaksi konstan 12.000 Write TPS. 

**Tantangan**:
1. Anda diperintahkan melakukan migrasi zero-downtime dari infrastruktur on-premise tersebut ke Cloud Provider (AWS Region Jakarta dan AWS Region Singapore) tanpa diperbolehkan adanya *maintenance window downtime* sama sekali pada layer aplikasi.
2. Arsitektur akhir harus berupa:
   - 2 Node di AWS Jakarta (AZ-a, AZ-b).
   - 2 Node di AWS Singapore (AZ-a, AZ-b) sebagai hot standby.
   - 1 Voting Witness Node di GCP Jakarta (Multi-Cloud Arbitrage).
3. Seluruh write dari aplikasi perbankan harus dijamin tidak akan pernah mengalami rollback (`linearizable read`, `j: true`, `w: majority`) dengan latensi write di bawah 40 milidetik.
4. Jika link internet trans-nasional Jakarta - Singapore putus total, operasi perbankan di Jakarta dilarang berhenti memproses transaksi baru.

**Rancang blueprint solusi teknis komprehensif yang mencakup**:
- Kalkulasi bandwidth pipa jaringan minimum inter-DC & inter-cloud.
- Skema transisi rekonfigurasi cluster tahap demi tahap (step-by-step rolling reconfiguration).
- Konfigurasi detail dokumen JSON `rs.reconfig()` final.
- Pengaturan Write Concern dan Client Connection String pool settings untuk mitigasi inter-cloud network jitter.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Isian Cepat)
1. Apa fungsi dari tahapan *Pre-Vote Phase* pada protokol replikasi MongoDB PV1?
   - A. Menulis data kandidat ke storage disk sebelum dieksekusi.
   - B. Memverifikasi apakah kandidat bisa memperoleh kuorum tanpa menaikkan nilai Term cluster secara disruptive.
   - C. Menguji apakah koneksi SSL/TLS valid.
   - D. Menghapus data oplog yang kadaluarsa.

2. Secara default, setiap berapa detik heartbeat dikirimkan antar node replica set, dan berapa detik batas waktu *election timeout*-nya?
   - A. Heartbeat 1 detik, timeout 5 detik.
   - B. Heartbeat 2 detik, timeout 10 detik.
   - C. Heartbeat 5 detik, timeout 15 detik.
   - D. Heartbeat 10 detik, timeout 30 detik.

3. Jika sebuah replica set memiliki total 7 voting nodes, berapa jumlah minimum vote yang dibutuhkan untuk memilih Primary baru atau mempertahankan quorum majority?
   - A. 3
   - B. 4
   - C. 5
   - D. 6

4. Apakah operasi replikasi oplog MongoDB bersifat *idempotent*? Mengapa?
   - A. Tidak, karena data terus bertambah.
   - B. Ya, karena setiap operasi mutasi dikonversi ke instruksi deterministik yang aman dieksekusi berulang kali tanpa mengubah state akhir.
   - C. Tergantung apakah kita menggunakan engine WiredTiger atau In-Memory.
   - D. Hanya jika kita menyertakan parameter `j: true`.

5. Karakteristik utama dari node replica set dengan konfigurasi `priority: 0` adalah:
   - A. Tidak dapat menyimpan data oplog.
   - B. Tidak dapat mengirimkan sinyal heartbeat.
   - C. Tidak pernah bisa menjadi Primary, namun tetap bisa memberikan suara voting (jika `votes: 1`).
   - D. Tidak dapat dibaca oleh client sama sekali.

#### Bagian 2: Intermediate (Analisis Kasus Singkat)
6. Sebuah cluster 3-node dikonfigurasi dengan Write Concern `{ w: "majority", wtimeout: 5000 }`. Tiba-tiba dua Secondary mengalami network failure permanen. Apa yang terjadi pada operasi write aplikasi saat mengeksekusi insert baru?
   - Jawaban & Analisis: ...

7. Apa perbedaan mendasar antara Read Concern `majority` versus Read Concern `linearizable`? Jelaskan konsekuensi performanya pada level Primary node!
   - Jawaban & Analisis: ...

8. Mengapa MongoDB sangat melarang penempatan Arbiter pada arsitektur cluster yang mengaktifkan fitur enkripsi storage (Encryption-at-Rest) dan Read Concern majority?
   - Jawaban & Analisis: ...

9. Dalam situasi apa sebuah node Secondary akan terjebak secara permanen pada status `RECOVERING` dan bagaimana mengatasinya tanpa mematikan Primary?
   - Jawaban & Analisis: ...

10. Jika kita mengonfigurasi Secondary node dengan parameter `secondaryDelaySecs: 3600`, mengapa kita WAJIB mengubah nilai `priority` node tersebut menjadi 0 dan `hidden` menjadi true?
    - Jawaban & Analisis: ...

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1**: Tim DevOps Anda menjalankan rolling index creation pada collection seukuran 2 TB di cluster replica set. Tak lama kemudian, aplikasi backend mulai melemparkan exception `WriteConcernFailed` dan user mengalami peningkatan latency transaksi secara global. Telusuri rantai kegagalan internal yang memicu insiden tersebut!
12. **Skenario Kasus 2**: Sebuah Replica Set 3-node mengalami partisi jaringan parsial: Primary (Node A) terputus dari Secondary B, tetapi masih bisa berkomunikasi dengan Secondary C. Namun, Secondary B dan Secondary C masih bisa saling terhubung secara lancar. Bagaimana protokol konsensus PV1 merespons topologi asimetris ini? Apakah akan terjadi *election loop*?
13. **Skenario Kasus 3**: Saat melakukan audit keamanan, tim InfoSec mendeteksi adanya data transaksi yang hilang pasca insiden restart server cluster darurat. Tim database mengklaim mereka selalu menggunakan opsi `{ w: 1, j: false }` karena mengejar target throughput 30.000 TPS. Berikan penjelasan forensik arsitektural mengapa data tersebut bisa hilang dan bagaimana merekayasa ulang konfigurasi sistem tanpa menurunkan throughput secara drastis!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **B** - Memverifikasi apakah kandidat bisa memperoleh kuorum tanpa menaikkan nilai Term cluster secara disruptive. Pre-vote mencegah node yang mengalami temporary network blip memicu pemilu palsu yang menaikkan Term dan mendepak Primary aktif yang valid.
2. **B** - Heartbeat 2 detik, timeout 10 detik (`electionTimeoutMillis = 10000`).
3. **B** - 4 node. Rumus Quorum: $\lfloor 7/2 \rfloor + 1 = 3 + 1 = 4$.
4. **B** - Ya, mutasi dinormalisasi menjadi mutasi statis (misal ekspresi matematik `$inc` diubah menjadi snapshot value `$set: { balance: 150 }`).
5. **C** - Tidak pernah bisa dipromosikan menjadi Primary, namun tetap berpartisipasi dalam pemilihan kuorum voting (kecuali jika dikonfigurasi `votes: 0`).

#### Bagian 2: Intermediate
6. **Analisis**: Dokumen akan berhasil ditulis ke engine storage Primary lokal, namun thread Primary akan terblokir menunggu konfirmasi dari minimal 1 Secondary guna memenuhi kuorum majority (2 dari 3 node). Karena tidak ada Secondary yang merespons, operasi akan terhenti selama 5.000 ms, lalu melemparkan error `WriteConcernError: waiting for replication timed out`. **Penting**: Data *tetap* tersimpan di Primary lokal meskipun error dilemparkan ke client.
7. **Analisis**: Read Concern `majority` membaca data langsung dari snapshot WiredTiger lokal Primary yang berada pada *majority commit point* (tidak memerlukan komunikasi jaringan saat read berlangsung). Sebaliknya, `linearizable` memaksa Primary berkomunikasi secara realtime via round-trip heartbeat ke mayoritas node sebelum merespons client guna memvalidasi bahwa dirinya belum terisolasi oleh split-brain. Konsekuensinya: Latensi `linearizable` meningkat drastis sebanding dengan RTT jaringan cluster.
8. **Analisis**: Arbiter tidak menyimpan katalog data maupun engine WiredTiger. Karena Arbiter tidak menyimpan data oplog, kehadiran Arbiter tidak dapat membantu memajukan *majority commit point* pada sistem storage engine. Ini membuat snapshot data pada node data bearer tertahan lebih lama di memori WiredTiger, yang dapat memicu tekanan cache memory (*cache eviction stall*) masif di node Primary.
9. **Analisis**: Node Secondary masuk ke status `RECOVERING` secara permanen jika posisi entri oplog terakhir miliknya sudah terlewati oleh entri oplog paling awal yang tersedia pada Primary (`oplog window overflow`/exhaustion). Solusi: Jalankan proses *initial sync* ulang dengan menghapus data directory node tersebut, atau lakukan restore physical snapshot backup data terbaru ke direktori Secondary tersebut.
10. **Analisis**: Node delayed memiliki data yang tertinggal sengaja (stale by design). Jika node delayed memiliki `priority > 0`, ia berpotensi terpilih menjadi Primary saat failover, yang akan mengakibatkan sistem rollback masif dan melayani data kadaluarsa ke seluruh traffic produksi. Dibuat `hidden: true` agar driver aplikasi tidak mengirimkan query read traffic operasional ke node yang datanya sengaja dibuat *out-of-date*.

#### Bagian 3: Solusi Kasus Produksi
11. **Rantai Kegagalan Kasus 1**:
    - Build index pada collection 2 TB memakan resource disk I/O bandwith dan CPU processing yang sangat intensif di node Primary dan Secondary.
    - Secondary mengalami saturasi disk I/O, menyebabkan worker thread replikasi oplog Secondary mengalami starvation (*slow oplog application*).
    - *Replication lag* membengkak melebihi toleransi `wtimeout`.
    - Operasi write aplikasi yang mensyaratkan durabilitas `{ w: "majority" }` gagal memenuhi kriteria replikasi tepat waktu, menghasilkan exception `WriteConcernFailed` berantai dan memenuhi socket thread pool backend.
12. **Analisis Topologi Asimetris Kasus 2**:
    - Node A (Primary) masih terhubung ke Node C. Node A melihat 2 node online dari total 3 node (Kuorum tercapai: $\lfloor 3/2 \rfloor + 1 = 2$). Node A **tetap bertahan** sebagai Primary.
    - Node B melihat Node A offline, sehingga Node B mencoba memicu pre-vote election. Namun, Node B hanya dapat berkomunikasi dengan Node C.
    - Node C menolak vote untuk Node B karena Node C melihat Primary (Node A) masih sehat dan terus menerima heartbeat teratur dari Node A.
    - Protokol PV1 secara elegan mencegah *election loop* melalui mekanisme validasi Pre-Vote dan lease term heartbeat dari Node C.
13. **Analisis Forensik Kasus 3**:
    - Konfigurasi `{ w: 1, j: false }` berarti ACK dikirimkan segera setelah mutasi ditulis ke cache memory WiredTiger Primary, TANPA diflush ke on-disk Write-Ahead Log (Journal) dan TANPA menunggu replikasi ke Secondary.
    - Ketika server Primary mengalami pemadaman listrik/crash mendadak, data yang masih berada di memory buffer WiredTiger dan belum diflush ke disk hilang seketika (*lost forever*).
    - **Solusi Arsitektural**:
      1. Ubah konfigurasi durabilitas menjadi `{ w: "majority", j: false, wtimeout: 2000 }`. Durabilitas dijamin oleh memori *dua server fisik yang berbeda* tanpa terblokir oleh lambatnya fsync journal lokal.
      2. Terapkan connection pipelining dan batching write operations (`bulkWrite`) pada driver aplikasi untuk mempertahankan target throughput 30.000 TPS secara aman.

---

### 16. Summary
- **Arsitektur Konsensus**: MongoDB Replica Set mengimplementasikan protokol PV1 berbasis varian Raft. Keputusan status kluster mutlak dipandu oleh hukum mayoritas voting nodes ($\lfloor N/2 \rfloor + 1$).
- **Pipeline Replikasi**: Mengalir dari operasi klien ke memory storage Primary -> WiredTiger WAL/Journal -> koleksi `local.oplog.rs` -> ditarik oleh Secondary via kursor tailable -> dieksekusi secara idempoten dan paralel -> dilaporkan kembali via heartbeat untuk memajukan commit point.
- **Konsistensi Fleksibel (Tunable Consistency)**: Menyeimbangkan trade-off performa dan durabilitas melalui matriks Write Concern (`w: 1` vs `w: majority`) dan Read Concern (`local` vs `majority` vs `linearizable`).
- **Desain Multi-Data Center**: Memerlukan segmentasi node yang presisi. Gunakan `Priority: 0`, `Hidden: true`, dan `SecondaryDelaySecs` untuk mendirikan node analitik dan penangkal *human error* bencana data tanpa mengorbankan integritas kuorum voting utama.