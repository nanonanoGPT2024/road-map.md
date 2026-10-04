# Bab 07 Module 01: High Availability & Replica Set Architecture

---

## 01: Identitas Modul
* **Track:** Database Engineering & Distributed Systems
* **Kategori:** 04-Backend-and-Database
* **Modul:** Bab 07 Module 01: High Availability & Replica Set Architecture
* **Level:** Advanced (L4/Principal-Track)
* **Prasyarat:** MongoDB Storage Engines (WiredTiger internals), Network Protocols (TCP/IP socket tuning, TLS), Linux System Administration, Distributed Consensus Fundamentals (Raft/Paxos).

---

## 02: Learning Objectives
1. **Menganalisis Internal Konsensus:** Membedah modifikasi algoritma Raft pada MongoDB Consensus Engine, transisi status node (`PRIMARY`, `SECONDARY`, `ARBITER`), serta mekanisme dynamic topology discovery.
2. **Mengevaluasi Replikasi Oplog:** Memahami struktur data, arsitektur bounded circular collection, push/pull pipeline, parallel batch application, dan handling write-conflicts pada WiredTiger engine.
3. **Mendesain Strategi Read & Write Semantics:** Mengimplementasikan kombinasi Write Concerns (`w:1`, `w:majority`, `w:linearizable`, `j:true`) dan Read Concerns (`local`, `available`, `majority`, `linearizable`, `snapshot`) guna mencegah *dirty reads*, *stale reads*, dan *phantom rollbacks*.
4. **Mengotomatisasi Failover & Zero-Loss Recovery:** Mengonfigurasi heartbeats, deteksi network partitioning (split-brain), dynamic election priority, dan prosedur roll-back mitigation.

---

## 03: Concept Map Diagram ASCII
```
+-------------------------------------------------------------------------------+
|                       CLIENT APPLICATION DRIVER TIER                          |
|  Topology Description | SDAM Spec | Connection Pool | Read/Write Concern Routers|
+-------------------------------------------------------------------------------+
                                      |
                       +--------------+--------------+
                       | TLS / Internal Auth (Keyfile)|
                       v                             v
+-----------------------------+               +-----------------------------+
|        PRIMARY NODE         |               |       SECONDARY NODE        |
|  +-----------------------+  | Heartbeat 2s  |  +-----------------------+  |
|  |     WiredTiger        |  |<=============>|  |      WiredTiger       |  |
|  |   Data Engine (RW)    |  |               |  |    Data Engine (RO)   |  |
|  +-----------------------+  |               +-----------------------+  |
|              |              |  Sync Source  |              ^              |
|              v              |   Streaming   |              |              |
|  +-----------------------+  |    (Oplog)    |  +-----------------------+  |
|  |  local.oplog.rs       |==|==============>|  |  Batch Applier Thread |  |
|  |  (Capped Collection)  |  |               |  |  Parallel Execution   |  |
|  +-----------------------+  |               +-----------------------+  |
+-----------------------------+               +-----------------------------+
               ^                                             ^
               |               Heartbeat 2s                  |
               +=============================================+
                                      |
                                      v
                       +-----------------------------+
                       |    SECONDARY NODE (VOTING)  |
                       |  +-----------------------+  |
                       |  | Priority: 1, Votes: 1 |  |
                       |  +-----------------------+  |
                       +-----------------------------+
```

---

## 04: Mengapa Relevan
Dalam arsitektur backend enterprise modern, downtime database berakibat pada kegagalan SLA dan potensi kerugian finansial. MongoDB Replica Set menyediakan mekanisme **High Availability (HA)** terdistribusi otomatis tanpa memerlukan orchestrator eksternal untuk failover. 

Penerapan konsensus terdistribusi yang tepat memastikan integritas data tetap konsisten bahkan saat terjadi kegagalan hardware, network partition (*split-brain*), atau lonjakan latensi replikasi. Pemahaman mendalam mengenai Oplog streaming dan model konsistensi tunabel (tunable consistency models) membedakan sistem database amatir dari infrastruktur tier-1 berskala global.

---

## 05: Anatomi Konsep Inti

### 1. Consensus Engine & Election Protocol (Raft-variant)
MongoDB menerapkan varian dari protokol konsensus Raft:
* **Heartbeats:** Setiap node mengirimkan ping UDP/TCP setiap 2 detik (`heartbeatIntervalMillis`). Jika sebuah node tidak merespons dalam 10 detik (`electionTimeoutMillis`), node lain menandainya sebagai unreachable.
* **Elections:** Node yang mendeteksi matinya Primary akan mencalonkan diri menjadi Candidate jika memenuhi syarat (Priority > 0, memiliki Oplog paling up-to-date di antara anggota quorum). Pemilihan membutuhkan suara mayoritas dari total voting members ($N/2 + 1$).
* **Rollbacks:** Jika node Primary lama terputus dari jaringan secara parsial, menerima penulisan tanpa `w:majority`, lalu turun pangkat (*step-down*), data yang tidak tereplikasi tersebut akan di-rollback ke format file BSON saat node tersebut tersinkronisasi kembali dengan Primary yang baru.

### 2. Oplog Architecture & Replication Mechanics
* **Capped Storage:** `local.oplog.rs` adalah collection berukuran tetap yang menggunakan pointer idempotensi berbasis timestamp dan term (`ts`, `t`).
* **Pull-based Replication:** Secondary melakukan query terus-menerus (*tailable cursor*) ke `local.oplog.rs` milik Sync Source (bisa Primary atau Secondary lain via *Chained Replication*).
* **Parallel Application:** Secondary membagi batch Oplog berdasarkan hash Document ID (`_id`) untuk dieksekusi paralel oleh thread-pool WiredTiger, mencegah bottleneck I/O.

### 3. Read Preference Matrix
* `primary`: Semua operasi baca diarahkan ke Primary (default, read-your-writes consistency).
* `primaryPreferred`: Baca dari Primary; jika down, fallback ke Secondary.
* `secondary`: Operasi baca dialihkan secara eksklusif ke Secondary (evade write lock, toleransi *stale data*).
* `secondaryPreferred`: Baca dari Secondary; jika tidak ada yang available, baca dari Primary.
* `nearest`: Baca dari node dengan network latency terendah (berdasarkan ping round-trip time window).

### 4. Read Concern Levels
* `local`: Mengembalikan data lokal tanpa verifikasi konsensus mayoritas. Berisiko *dirty read* jika node di-rollback.
* `available`: Identik dengan `local`, tetapi di Sharded Cluster tidak memvalidasi chunk metadata migration.
* `majority`: Mengembalikan data yang telah dikomit oleh mayoritas node. Membaca dari storage-engine memory snapshot tanpa risiko rollback.
* `linearizable`: Memaksa Primary melakukan verifikasi kuorum secara *real-time* via read-time heartbeats sebelum mengembalikan respons, menjamin serializability.
* `snapshot`: Digunakan dalam multi-document ACID transactions; membaca point-in-time snapshot dari WiredTiger isolation engine.

---

## 06: Panduan Implementasi Step-by-Step

### Step 1: Konfigurasi Jaringan & Inisialisasi Environment
Buat base directory dan set direktori data untuk arsitektur 3-node pada host terisolasi.

```bash
mkdir -p /data/replica/{node1,node2,node3}
mkdir -p /data/replica/logs
```

### Step 2: Generate Internal Cluster Security Key
Replikasi terautentikasi wajib menggunakan shared keyfile (HMAC-SHA256).

```bash
openssl rand -base64 756 > /data/replica/mongo-keyfile
chmod 400 /data/replica/mongo-keyfile
chown -R $(whoami) /data/replica
```

### Step 3: Deployment Konfigurasi Instance
Buat file konfigurasi YAML untuk masing-masing node.

**Node 1 (`/data/replica/mongod-node1.conf`):**
```yaml
storage:
  dbPath: /data/replica/node1
  journal:
    enabled: true
  wiredTiger:
    engineConfig:
      cacheSizeGB: 1
systemLog:
  destination: file
  path: /data/replica/logs/node1.log
  logAppend: true
net:
  port: 27017
  bindIp: 127.0.0.1
processManagement:
  fork: true
replication:
  replSetName: rsProduction
  oplogSizeMB: 2048
security:
  keyFile: /data/replica/mongo-keyfile
  authorization: enabled
```

*(Ulangi untuk Node 2 pada port `27018` path `/data/replica/node2`, dan Node 3 pada port `27019` path `/data/replica/node3`)*.

### Step 4: Menjalankan Node Daemon
```bash
mongod --config /data/replica/mongod-node1.conf
mongod --config /data/replica/mongod-node2.conf
mongod --config /data/replica/mongod-node3.conf
```

### Step 5: Inisialisasi Replica Set via `mongosh`
Koneksikan shell ke Node 1:
```bash
mongosh --port 27017
```

Eksekusi bootstrap konfigurasi:
```javascript
rs.initiate({
  _id: "rsProduction",
  members: [
    { _id: 0, host: "127.0.0.1:27017", priority: 2 },
    { _id: 1, host: "127.0.0.1:27018", priority: 1 },
    { _id: 2, host: "127.0.0.1:27019", priority: 1 }
  ]
});
```

---

## 07: Contoh Kasus Sederhana: Dynamic Topology Failover Check

Validasi kondisi cluster dan simulasi graceful failover:

```javascript
// Cek status detail topology
rs.status();

// Verifikasi siapa Primary saat ini
db.isMaster().primary;

// Paksa Primary step-down selama 60 detik untuk memicu election
rs.stepDown(60);

// Periksa perubahan status pada node sekunder
rs.status().members.forEach(m => {
  print(`${m.name} -> State: ${m.stateStr} | Health: ${m.health}`);
});
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Aplikasi Node.js enterprise-grade yang mengimplementasikan driver configuration, robust error handling, connection pooling, retryable writes, dan Read/Write concern terisolasi.

```typescript
// File: src/database.ts
import { MongoClient, MongoClientOptions, ReadConcern, ReadPreference, WriteConcern } from 'mongodb';

interface DatabaseConfig {
  hosts: string[];
  replicaSet: string;
  database: string;
  authSource: string;
  username?: string;
  password?: string;
}

export class MongoClusterConnection {
  private client: MongoClient | null = null;
  private readonly config: DatabaseConfig;

  constructor(config: DatabaseConfig) {
    this.config = config;
  }

  public async connect(): Promise<MongoClient> {
    const connectionUri = this.buildUri();
    
    const options: MongoClientOptions = {
      replicaSet: this.config.replicaSet,
      serverSelectionTimeoutMS: 5000,
      heartbeatFrequencyMS: 2000,
      minPoolSize: 10,
      maxPoolSize: 100,
      maxIdleTimeMS: 30000,
      retryWrites: true,
      retryReads: true,
      writeConcern: new WriteConcern('majority', { wtimeout: 5000, j: true }),
      readPreference: ReadPreference.PRIMARY_PREFERRED,
      readConcern: new ReadConcern('majority'),
      directConnection: false
    };

    try {
      this.client = new MongoClient(connectionUri, options);
      await this.client.connect();
      
      this.registerTopologyEvents(this.client);
      console.info('[MongoDB] Connected to ReplicaSet successfully.');
      return this.client;
    } catch (error) {
      console.error('[MongoDB] Connection initialization failed:', error);
      throw error;
    }
  }

  private buildUri(): string {
    const hosts = this.config.hosts.join(',');
    const credentials = this.config.username && this.config.password
      ? `${encodeURIComponent(this.config.username)}:${encodeURIComponent(this.config.password)}@`
      : '';
    return `mongodb://${credentials}${hosts}/${this.config.database}?authSource=${this.config.authSource}`;
  }

  private registerTopologyEvents(client: MongoClient): void {
    client.on('serverDescriptionChanged', (event) => {
      console.debug(`[Topology Event] Server ${event.address} changed type to: ${event.newDescription.type}`);
    });

    client.on('topologyDescriptionChanged', (event) => {
      console.info(`[Topology Event] Replica Set Topology updated. Nodes:`, Object.keys(event.newDescription.servers));
    });

    client.on('serverHeartbeatFailed', (event) => {
      console.warn(`[Topology Warning] Heartbeat failed for ${event.connectionId}. Duration: ${event.duration}ms`);
    });
  }

  public async close(): Promise<void> {
    if (this.client) {
      await this.client.close();
      console.info('[MongoDB] Connection pool terminated gracefully.');
    }
  }
}

// File: src/services/transactionService.ts
import { MongoClient, ClientSession } from 'mongodb';

export class OrderService {
  private client: MongoClient;

  constructor(client: MongoClient) {
    this.client = client;
  }

  public async processOrder(orderId: string, accountId: string, amount: number): Promise<void> {
    const session: ClientSession = this.client.startSession();

    try {
      await session.withTransaction(async () => {
        const db = this.client.db('enterprise_store');
        const ordersCollection = db.collection('orders');
        const accountsCollection = db.collection('accounts');

        // Step 1: Potong saldo
        const accountUpdate = await accountsCollection.updateOne(
          { _id: accountId, balance: { $gte: amount } },
          { $inc: { balance: -amount } },
          { session }
        );

        if (accountUpdate.matchedCount === 0) {
          throw new Error('INSUFFICIENT_FUNDS_OR_ACCOUNT_NOT_FOUND');
        }

        // Step 2: Buat data order
        await ordersCollection.insertOne(
          {
            _id: orderId,
            accountId,
            amount,
            status: 'COMPLETED',
            createdAt: new Date()
          },
          { session }
        );
      }, {
        readPreference: ReadPreference.PRIMARY,
        readConcern: new ReadConcern('snapshot'),
        writeConcern: new WriteConcern('majority', { j: true, wtimeout: 4000 })
      });

      console.info(`[Order] Transaction committed successfully for Order ID: ${orderId}`);
    } catch (error) {
      console.error(`[Order] Transaction aborted. Error:`, error);
      throw error;
    } finally {
      await session.endSession();
    }
  }
}
```

---

## 09: Diagram Alur Kerja ASCII: Raft Failover Execution

```
  PRIMARY (Port 27017)        SECONDARY A (Port 27018)      SECONDARY B (Port 27019)
         |                                |                             |
         X (KILLED / CRASH)               |                             |
         |                                |                             |
         |   -- Heartbeat Failure (10s)-> |   -- Heartbeat Failure -->  |
         |                                |                             |
         |                                +=== Priority & Oplog Check ==+
         |                                | (Secondary A has higher term)
         |                                |                             |
         |                                |-- RequestVote(Term=2, A) -->|
         |                                |                             |
         |                                |<-- VoteGranted(Term=2) -----|
         |                                |                             |
         |                                +===== QUORUM REACHED ========+
         |                                |   (2 out of 3 votes: >50%)  |
         |                                |                             |
         |                                +-- State Transition:         |
         |                                |   SECONDARY -> PRIMARY      |
         |                                |                             |
         |                                |-- Inform Topology Change -->|
         |                                |                             |
+-------------------+                    +-------------------------------+
| OLD PRIMARY (27017)|                   |      NEW PRIMARY (27018)      |
| RECOVERS / REBOOTS|                    +-------------------------------+
+-------------------+                                   |
         |                                              |
         | <--- Sync Heartbeat (Term=2 Detected) -------|
         |                                              |
         |-- Step Down to SECONDARY ------------------->|
         |-- Rollback Uncommitted Oplog to BSON Files ->|
         |-- Resume Oplog Sync Source from Node 27018 ->|
```

---

## 10: Analisis Trade-offs

| Parameter | Konfigurasi Agresif (Low Latency) | Konfigurasi Konservatif (High Durability) |
| :--- | :--- | :--- |
| **Write Concern** | `w: 1` (Acknowledge on memory Primary) | `w: "majority", j: true` (Multi-node fsync disk) |
| **Read Concern** | `local` / `available` | `linearizable` / `snapshot` |
| **Failover Timeout** | `electionTimeoutMillis: 5000` | `electionTimeoutMillis: 15000` |
| **Trade-off Pros** | Throughput IOPS maksimal, response-time < 2ms | Zero data loss guarantee, no phantom reads |
| **Trade-off Cons** | Risiko data hilang saat sudden failover, dirty reads | Latensi RTT meningkat, throughput IOPS tereduksi |
| **Risiko Operasional** | Rollback volume tinggi pada reconnection | Transient election thrashing jika network flapping |

---

## 11: Best Practices & Antipatterns

### Best Practices
1. **Rule of Odd Numbers:** Selalu gunakan jumlah voting members ganjil (3, 5, 7) untuk menghindari split-vote deadlock.
2. **Dedicated Majority Voting Nodes:** Pastikan seluruh voting members terdistribusi minimal di 3 Availability Zones (AZ) terpisah.
3. **Set Realistic wtimeout:** Selalu tentukan parameter `wtimeout` (misal 5000ms) saat menggunakan `w: majority` agar thread pool aplikasi tidak terblokir permanen saat terjadi degradasi kuorum.
4. **Appropriate Oplog Sizing:** Alokasikan minimal 5-10% dari total storage disk untuk Oplog guna mengakomodasi batch ETL atau maintenance downtime yang panjang.

### Antipatterns
1. **Over-reliance on Arbiters:** Menggunakan Arbiter di production enterprise menciptakan *voting imbalance* dan mencegah query snapshot membaca data historis.
2. **Deep Chained Replication:** Membiarkan default chain replication tanpa tuning pada inter-region topology, memicu *replication lag compounding*.
3. **Read Everything from Secondary:** Mengarahkan seluruh query analitik berat ke Secondary tanpa membatasi batch size, menyebabkan *Secondary catch-up degradation* (penumpukan replication lag).

---

## 12: Security Hardening

* **Inter-node TLS 1.3 Strict Mutual Authentication (mTLS):**
```yaml
net:
  tls:
    mode: requireTLS
    certificateKeyFile: /etc/ssl/mongo.pem
    CAFile: /etc/ssl/ca.pem
    clusterFile: /etc/ssl/cluster-internal.pem
    allowConnectionsWithoutCertificates: false
```
* **Enforce Scram-SHA-256 for Cluster Members:**
```bash
mongosh --port 27017 -u "clusterAdmin" -p --authenticationDatabase "admin" --eval '
db.getSiblingDB("admin").createUser({
  user: "clusterAdmin",
  pwd: passwordPrompt(),
  roles: [ { role: "root", db: "admin" } ],
  mechanisms: ["SCRAM-SHA-256"]
})'
```
* **IP Binding Restrictiveness:** Larang mutlak `bindIp: 0.0.0.0` pada infrastructure cluster internal. Wajib bind ke private subnet interface atau loopback bridge.

---

## 13: Observabilitas & Debugging

Gunakan skrip `mongosh` berikut untuk menganalisis replication latency dalam satuan detik (*replication lag*):

```javascript
function checkReplicationLag() {
  const status = rs.status();
  const primary = status.members.find(m => m.state === 1);
  
  if (!primary) {
    print("FATAL: No Primary detected!");
    return;
  }

  const primaryOptime = primary.optimeDate;
  print(`PRIMARY [${primary.name}] Current Optime: ${primaryOptime.toISOString()}`);
  print("------------------------------------------------------------------");

  status.members.filter(m => m.state === 2).forEach(sec => {
    const lagSeconds = (primaryOptime.getTime() - sec.optimeDate.getTime()) / 1000;
    print(`SECONDARY [${sec.name}] Optime: ${sec.optimeDate.toISOString()} | Lag: ${lagSeconds}s | Ping: ${sec.pingMs}ms`);
  });
}

checkReplicationLag();
```

---

## 14: Benchmarking & Performance

Jalankan pengujian benchmarking menggunakan embedded JavaScript profiling loop untuk mengukur overhead konsistensi:

```javascript
// Test 1: Write Concern w:1
console.time("WRITE_CONCERN_1");
for (let i = 0; i < 10000; i++) {
  db.benchmark.insertOne({ metric: i, ts: new Date() }, { writeConcern: { w: 1 } });
}
console.timeEnd("WRITE_CONCERN_1");

// Test 2: Write Concern w:majority with Journal Sync
console.time("WRITE_CONCERN_MAJORITY_SYNC");
for (let i = 0; i < 10000; i++) {
  db.benchmark.insertOne({ metric: i, ts: new Date() }, { writeConcern: { w: "majority", j: true, wtimeout: 5000 } });
}
console.timeEnd("WRITE_CONCERN_MAJORITY_SYNC");
```

---

## 15: Hands-on Lab Mini-Project

### Objective:
Bangun simulasi automasi disaster recovery: deteksi network isolation (split-brain) dan eksekusi recovery script untuk memvalidasi zero-loss data capture.

### Tasks:
1. Jalankan cluster 3-node lokal (Node 1: 27017, Node 2: 27018, Node 3: 27019).
2. Tulis 1000 dokumen dengan `w: "majority"`.
3. Isolasi Node 1 (Primary) menggunakan network blocking via OS firewall atau SIGSTOP (`kill -STOP <PID_NODE1>`).
4. Pantau proses pemilihan (election) Primary baru antara Node 2 dan Node 3.
5. Lanjutkan penulisan 500 dokumen baru ke cluster baru.
6. Hidupkan kembali Node 1 (`kill -CONT <PID_NODE1>`).
7. Amati log sinkronisasi transisi dan verifikasi bahwa seluruh 1500 dokumen terdistribusi merata di ketiga node.

---

## 16: Automated Testing & Verification

Integration Test suite menggunakan TypeScript & Jest untuk memverifikasi write resilience saat failover:

```typescript
import { MongoClient } from 'mongodb';

describe('Replica Set High Availability Suite', () => {
  let client: MongoClient;
  const uri = 'mongodb://127.0.0.1:27017,127.0.0.1:27018,127.0.0.1:27019/test_ha?replicaSet=rsProduction';

  beforeAll(async () => {
    client = new MongoClient(uri, {
      serverSelectionTimeoutMS: 10000,
      retryWrites: true
    });
    await client.connect();
  });

  afterAll(async () => {
    await client.close();
  });

  test('Should maintain write-availability across primary stepDown', async () => {
    const db = client.db('test_ha');
    const col = db.collection('ha_verify');

    // Penulisan awal
    const initRes = await col.insertOne({ status: 'pre-stepdown' }, { writeConcern: { w: 'majority' } });
    expect(initRes.acknowledged).toBe(true);

    // Dapatkan akses ke Admin DB untuk trigger stepDown
    const adminDb = client.db('admin');
    
    // Step down primary asynchronously
    adminDb.command({ replSetStepDown: 10, force: true }).catch(() => {
      // Step down terminates socket connection, ignore expected disconnect error
    });

    // Coba nulis berulang-ulang selama transisi (harus auto-retry via driver)
    const retryWritesPromises: Promise<any>[] = [];
    for (let i = 0; i < 5; i++) {
      const p = col.insertOne({ status: `during-transition-${i}` }, { writeConcern: { w: 'majority' } });
      retryWritesPromises.push(p);
    }

    const results = await Promise.all(retryWritesPromises);
    results.forEach(res => expect(res.acknowledged).toBe(true));
  });
});
```

---

## 17: Troubleshooting Guide

### 1. Masalah: Replication Lag Ekstrem (Secondary Ketinggalan Oplog)
* **Penyebab:** Secondary kehabisan memory, throughput IOPS disk tertahan (throttled), atau adanya single long-running unindexed query yang memblokir write lock.
* **Diagnosis:** Jalankan `db.currentOp({ "active": true, "secs_running": { "$gt": 5 } })` pada secondary dan periksa disk utilization via `iostat -xz 1`.
* **Solusi:** Tingkatkan spesifikasi IOPS storage (misal: AWS gp3 -> io2), isolasi reporting query ke node dedicated read-only (`priority: 0, hidden: true`), resize oplog jika headroom mengecil.

### 2. Masalah: State Node Tersangkut di `ROLLBACK` atau `RECOVERING`
* **Penyebab:** Uncommitted writes terlalu masif untuk di-rollback secara in-memory, atau secondary terputus melebihi retensi waktu Oplog (*Oplog overrun*).
* **Diagnosis:** Cek file log pada direktori logs; cari error `OplogOutOfOrder` atau `ReplicaSetNotFound`.
* **Solusi:** Jika node masuk status stale overrun, hapus direktori data node tersebut dan lakukan *Initial Sync* bersih dari primary.

---

## 18: Checklist Produksi

- [ ] Minimal 3 node fisik / Availability Zones terdistribusi merata (Odd member count).
- [ ] Oplog minimum retention time dikonfigurasi menampung minimal 72 jam aktivitas normal write operations.
- [ ] Internal cluster authentication aktif dengan bit-length min 756-bit Keyfile atau mTLS X.509 Certificate.
- [ ] Network firewall memblokir public ingress ke port DB; inter-node communication terisolasi di VPC Private Subnet.
- [ ] Production connection URI driver selalu menyertakan opsi `replicaSet=<nama_set>` dan parameter `retryWrites=true`.
- [ ] Read preference aplikasi telah dipisahkan: OLTP (`primary`), Dashboard Heavy Analytics (`secondary` dengan tags khusus).
- [ ] Monitoring alert otomatis dikonfigurasi untuk metrics: `ReplicationLag > 10s`, `ElectionOccurredCount > 0`, `NodeState != (1 or 2)`.

---

## 19: Ringkasan Eksekutif
Arsitektur High Availability pada MongoDB didasarkan pada mekanisme Stateful Replica Sets yang mengadopsi protokol konsensus berbasis Raft. Integritas sistem terdistribusi bertumpu pada interaksi langsung antara **Oplog Engine**, **WiredTiger MVCC Snapshot Storage**, dan dynamic topology negotiation. 

Kombinasi optimal antara Write Concern `majority` dan Read Concern `majority`/`snapshot` memberikan jaminan konsistensi data terkuat tanpa mengorbankan fault tolerance. Kepatuhan terhadap standarisasi deployment (zero Arbiters in mission-critical environments, multi-AZ quorum, explicit timeouts) merupakan fondasi utama sistem database modern level enterprise yang tangguh menghadapi anomali infrastruktur jaringan.

---

## 20: Referensi & Bacaan Lanjutan
* MongoDB Inc. (2024). *Server Storage Engine & WiredTiger Internals Manual*.
* Ongaro, D., & Ousterhout, J. (2014). *In Search of an Understandable Consensus Algorithm (Raft)*. USENIX Annual Technical Conference.
* MongoDB Documentation. *Server Discovery and Monitoring (SDAM) Specification*.
* Kleppmann, Martin. (2017). *Designing Data-Intensive Applications: The Big Ideas Behind Reliable, Scalable, and Maintainable Systems*. O'Reilly Media. Chapter 5: Replication.