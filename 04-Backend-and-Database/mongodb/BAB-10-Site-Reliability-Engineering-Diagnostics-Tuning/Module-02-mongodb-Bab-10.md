# Bab 10: Site Reliability Engineering, Diagnostics & Tuning
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengonfigurasi dan mengoptimalkan subsistem internal storage engine WiredTiger (eviction server, thread queues, transaction commit pipelines, memory footprint) pada beban konkurensi ekstrem.
- Menganalisis metrik Full-Time Diagnostic Data Capture (FTDC) dan log server secara sistematis untuk mengidentifikasi bottleneck CPU, Disk I/O, Page Faults, dan Lock/Latch contention.
- Mendesain arsitektur koneksi dan thread pool produksi (Driver Connection Pool, `mongos`/`mongod` incoming connections, task executors) untuk mencegah degradasi performa akibat *connection storm* dan *context-switching thrashing*.
- Mengimplementasikan pipeline diagnostik otomatis untuk profiling query lambat, query plan instability, dan anomali throughput berbasis batas ambang Service Level Objective (SLO).
- Menerapkan parameter kernel Linux, memory management (NUMA, Transparent Huge Pages), dan filesystem storage profile yang divalidasi untuk kluster MongoDB enterprise.

---

### 2. Prerequisite
- Pemahaman mendalam tentang replikasi (*Raft-like election*, *Oplog processing*) dan *sharding internals* (`mongos`, `configsvr`, chunk balancing).
- Penguasaan administrasi sistem Linux tingkat lanjut: utilitas CLI Linux (`vmstat`, `iostat`, `perf`, `sysctl`, `numactl`).
- Pengetahuan solid mengenai query execution plans (`explain("executionStats")`), locking models (Global, Database, Collection, Document-level intents), serta arsitektur storage block-level NVMe/SSD.

---

### 3. Concept & Internal Architecture (Mendalam)

Operasional MongoDB pada skala enterprise menuntut pemahaman arsitektur mesin runtime hingga ke layer kernel. Di bawah beban produksi masif, bottleneck jarang berasal dari sintaks query semata, melainkan dari interaksi antara alokasi memori WiredTiger, penjadwalan kernel Linux, dan sistem storage I/O.

```
+-------------------------------------------------------------------------------+
|                                Linux User Space                               |
|  +-------------------------------------------------------------------------+  |
|  |                           mongod Process                                |  |
|  |  +-------------------------------------------------------------------+  |  |
|  |  | Connection Layer: epoll() -> Service Worker Threads              |  |  |
|  |  +-------------------------------------------------------------------+  |  |
|  |  | Execution Engine: Query Planner -> Index Scan -> Document Fetch   |  |  |
|  |  +-------------------------------------------------------------------+  |  |
|  |  | WiredTiger Storage Engine:                                        |  |  |
|  |  |   - Thread Pool: Worker Threads, Checkpoint Thread, Eviction Svc  |  |  |
|  |  |   - Cache: Clean Pages vs Dirty Pages                             |  |  |
|  |  |     [ Dirty Trackers ]  <->  [ Concurrent Hazard Pointers ]       |  |  |
|  |  +-------------------------------------------------------------------+  |  |
|  +-------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------+
|                                Linux Kernel Space                             |
|  - Virtual Memory: Page Allocator (No THP), Page Cache, Buddy Allocator      |
|  - IO Scheduler: mq-deadline / none -> Block Device Driver                   |
|  - Inter-Process Sched: CFS (Completely Fair Scheduler), NUMA Interleave     |
+-------------------------------------------------------------------------------+
|                                Physical Hardware                              |
|  - Multiple NUMA Nodes (CPU Sockets + Local RAM)                              |
|  - NVMe Arrays (PCIe Lanes, Low-Latency IOPS)                                |
+-------------------------------------------------------------------------------+
```

#### A. WiredTiger Cache, Dirty Pages, dan Eviction Pipeline
WiredTiger mengalokasikan memori terpisah dari buffer cache sistem operasi. Secara default, ukuran cache diatur melalui:
$$\text{WT Cache Size} = 0.5 \times (\text{Total RAM} - 1\text{ GB})$$

Siklus hidup cache dimonitor melalui tiga *threshold* penting:
1. **Eviction Target (Default 80%)**: Saat persentase penggunaan cache melebihi batas ini, thread background eviction WiredTiger mulai menulis clean pages yang tidak terpakai ke disk atau menghapusnya dari RAM.
2. **Dirty Trigger (Default 5% - 20%)**: Saat persentase *dirty pages* (halaman data termodifikasi yang belum tercatat pada checkpoint disk) melewati ambang ini, eviction server memprioritaskan pembersihan dirty data ke storage.
3. **Eviction Hard Stop / App Eviction (Default 95% total cache atau 20% dirty)**: Jika thread background tidak mampu mengimbangi laju mutasi (misalnya saat terjadi lonjakan write masif), *client worker threads* (thread yang memproses request client) dipaksa membantu proses eviction. Akibatnya, latensi query melonjak drastis (*application stall*).

#### B. Mekanisme Checkpoint dan Journaling
- **Journaling**: Menjamin ketahanan crash (*crash resilience*) dengan mencatat log mutasi *in-memory* ke file disk journal setiap 100 ms (atau 50 ms tergantung konfigurasi) atau saat write concern `j: true` diminta.
- **Checkpointing**: Secara default dieksekusi setiap 60 detik atau setelah data mencapai 2 GB. Checkpoint membuat snapshot konsisten dari data tree WiredTiger ke disk, memungkinkan recovery sistem dengan memutar ulang journal dari titik checkpoint terakhir. Jika I/O storage lambat, proses checkpoint memicu *lock contention* dan lonjakan latensi I/O (*checkpoint stalls*).

#### C. Full-Time Diagnostic Data Capture (FTDC)
FTDC merekam metrik kinerja internal secara berkala (default per 1 detik) ke file terkompresi di direktori `diagnostic.data/`. Formatnya berbasis kompresi varian zlib/snappy dari metrik BSON ter-delta:
- Server metrics (`serverStatus`)
- Latency & Replication metrics (`replSetGetStatus`)
- Host resource utilization (`systemInfo`, OS stats)
FTDC tidak merekam query payload mentah atau data sensitif pengguna, melainkan *time-series counters* sistem.

---

### 4. Why & What

| Komponen / Masalah | Apa Itu? (What) | Mengapa Krusial? (Why) |
| :--- | :--- | :--- |
| **WiredTiger Eviction Stalls** | Kondisi di mana client thread dipaksa melakukan background eviction. | Memicu lonjakan latensi dari sub-milidetik ke detik atau menit, merusak SLA API mikroservis backend. |
| **NUMA Architecture Trap** | Alokasi memori node lokal habis, memicu swap ke disk padahal node NUMA lain masih memiliki free RAM. | Penurunan throughput dramatis (*zone-reclaim penalty*), memicu crash atau failover tak terduga. |
| **Transparent Huge Pages (THP)** | Fitur alokasi memory block Linux sebesar 2MB menggantikan 4KB standar. | Menghasilkan fragmentasi memori, latensi tinggi pada read random, dan memory thrashing di runtime database. |
| **Connection Storms** | Ribuan koneksi client baru dibuka bersamaan ke node database tanpa throttling. | Overload alokasi thread stack OS (1MB per thread), memory exhaustion, dan CPU thrashing pada syscall `clone()`. |
| **Checkpoint Spikes** | Proses penulisan snapshot WiredTiger ke filesystem block layer. | Jika disk IOPS saturated, checkpoint memperlambat disk throughput untuk proses read/write operasional normal. |

---

### 5. How (Workflow Detail)

Alur penanganan degradasi performa (*triage & tuning workflow*) pada insiden produksi:

```
[Alarm SLO Terpicu: Latensi P99 > Target]
                  │
                  ▼
[Langkah 1: Identifikasi Scope Insiden]
       ├─ Apakah terjadi di Primary saja atau merata di Secondary?
       └─ Cek replSetGetStatus: Repl lag, health, sync source.
                  │
                  ▼
[Langkah 2: Analisis Latensi Mesin (FTDC + serverStatus)]
       ├─ WiredTiger Cache Usage (Clean vs Dirty %)
       ├─ WiredTiger Concurrent Read/Write Tickets Remaining
       └─ Lock Wait Time & Latches Contention
                  │
                  ▼
[Langkah 3: Periksa Host / Kernel Degradation]
       ├─ CPU: %user, %system (context switching), %iowait
       ├─ Memory: Paging activity (si/so), Page allocation stalls
       └─ Storage: %util, await, r_await, w_await via iostat
                  │
                  ▼
[Langkah 4: Root Cause Mitigation]
       ├─ Eviction Stalls? -> Tuning eviction threads & wiredTiger cache sizing.
       ├─ Slow Queries? -> Kill via db.killOp(), extract explain plan, add index.
       ├─ Connection Spike? -> Scale down client maxPoolSize, set maxIncomingConnections.
       └─ Disk IOPS Bottleneck? -> Throttling rate, scale IOPS volume EBS/NVMe.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional & WiredTiger Engine
Bayangkan memori MongoDB sebagai bandara:
- **RAM / Cache**: Ruang tunggu keberangkatan (*departure lounge*).
- **Client Threads**: Penumpang yang masuk membawa bagasi (operasi penulisan/pembacaan).
- **Eviction Workers**: Petugas boarding pass yang memindahkan penumpang ke pesawat (Storage/Disk).
- **Eviction Target (80%)**: Alarm ketika ruang tunggu mulai padat; petugas boarding bekerja lebih cepat.
- **Application Eviction (95%)**: Ruang tunggu penuh sesak. Pintu gerbang ditutup, dan seluruh calon penumpang yang baru tiba dipaksa membantu mengangkat koper penumpang lain ke bagasi pesawat sebelum mereka sendiri diizinkan masuk. Seluruh proses antrean bandara lumpuh (*application stall*).

```
   Normal Cache Flow (< 80% Full)
   [Client App] ──Write──> [ WT Cache (Memory) ] ──Async Boarding──> [ Disk (NVMe) ]
                                 ▲
                          [Eviction Server]

   Overload Flow (> 95% Full - App Eviction Panic)
   [Client App] ──────────┐
        │                 ▼
        │ (Forced) ──> [ WT Cache Memory ] ────STALL────> [ Disk Saturated ]
        └─────────────> Handled directly by App Thread!
                        (Latensi Melonjak Masif)
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Produksi Linux OS Kernel (`/etc/sysctl.d/99-mongodb.conf`)
Konfigurasi OS yang wajib diterapkan untuk menghindari swap thrashing dan network socket exhaustion:

```ini
# Menghindari disk swapping agresif tetapi membiarkan swap darurat
vm.swappiness = 1

# Memastikan write dirty pages kernel di-flush lebih awal ke disk
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# Meningkatkan kapasitas antrean socket koneksi network
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# Menghindari resource exhaustion pada file descriptor
fs.file-max = 2097152

# Mematikan dynamic memory allocation zone-reclaim
vm.zone_reclaim_mode = 0
```

Terapkan dengan:
```bash
sudo sysctl -p /etc/sysctl.d/99-mongodb.conf
```

#### B. Systemd Service Unit Overrides (`/etc/systemd/system/mongod.service.d/override.conf`)
Menjamin limit resource proses Linux telah dinaikkan dan NUMA interleave diaktifkan:

```ini
[Service]
# Nonaktifkan NUMA locality preference agar RAM dialokasikan merata di seluruh CPU node
ExecStart=
ExecStart=/usr/bin/numactl --interleave=all /usr/bin/mongod --config /etc/mongod.conf

# Resource Limits
LimitFSIZE=infinity
LimitCPU=infinity
LimitAS=infinity
LimitNOFILE=64000
LimitNPROC=64000
LimitMEMLOCK=infinity
```

Muat ulang systemd:
```bash
sudo systemctl daemon-reload
sudo systemctl restart mongod
```

#### C. Diagnostik Real-Time Menggunakan Engine Metrics Pipeline (Node.js Enterprise Implementation)
Script pemantau metrik internal WiredTiger untuk mendeteksi *ticket starvation* dan *cache pressure*:

```typescript
import { MongoClient } from 'mongodb';

interface WiredTigerDiagnostics {
  cacheUsedBytes: number;
  cacheMaxBytes: number;
  dirtyBytes: number;
  readTicketsAvailable: number;
  writeTicketsAvailable: number;
  checkpointRunning: boolean;
}

export class MongoSREDiagnostics {
  private client: MongoClient;

  constructor(uri: string) {
    this.client = new MongoClient(uri, {
      maxPoolSize: 5,
      minPoolSize: 1,
      serverSelectionTimeoutMS: 3000,
    });
  }

  public async connect(): Promise<void> {
    await this.client.connect();
  }

  public async captureDiagnostics(): Promise<WiredTigerDiagnostics> {
    const adminDb = this.client.db('admin');
    const status = await adminDb.command({ serverStatus: 1 });

    const wt = status.wiredTiger;
    const concurrentTransactions = status.concurrentTransactions;

    const diagnostics: WiredTigerDiagnostics = {
      cacheUsedBytes: wt.cache['bytes currently in the cache'],
      cacheMaxBytes: wt.cache['maximum bytes configured'],
      dirtyBytes: wt.cache['tracked dirty bytes in the cache'],
      readTicketsAvailable: concurrentTransactions.read.available,
      writeTicketsAvailable: concurrentTransactions.write.available,
      checkpointRunning: wt.checkpoint['checkpoint running'] === 1,
    };

    return diagnostics;
  }

  public evaluateReliabilityHealth(diag: WiredTigerDiagnostics): void {
    const cacheUsagePercent = (diag.cacheUsedBytes / diag.cacheMaxBytes) * 100;
    const dirtyPercent = (diag.dirtyBytes / diag.cacheMaxBytes) * 100;

    console.log(`[Diagnostic Info] Cache: ${cacheUsagePercent.toFixed(2)}%, Dirty: ${dirtyPercent.toFixed(2)}%`);
    console.log(`[Tickets] Read: ${diag.readTicketsAvailable}, Write: ${diag.writeTicketsAvailable}`);

    if (cacheUsagePercent >= 90 || dirtyPercent >= 15) {
      console.error('CRITICAL: WiredTiger Cache Contention! Eviction stalling is imminent.');
    }
    if (diag.readTicketsAvailable === 0 || diag.writeTicketsAvailable === 0) {
      console.error('CRITICAL: Concurrency Ticket Starvation! Client commands are queuing.');
    }
    if (diag.checkpointRunning) {
      console.warn('WARN: Long-running checkpoint active. Expect minor latency perturbations.');
    }
  }

  public async close(): Promise<void> {
    await this.client.close();
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Platform**: FinTech Payment Gateway Processing Engine.
- **Beban Kerja**: 120.000 mutasi ledger per detik (*write-heavy*) tersebar di Sharded Cluster (8 shards, masing-masing 3-node Replica Set).
- **Spesifikasi Node**: AWS `r5b.8xlarge` (32 vCPU, 256 GB RAM, 60.000 Provisioned IOPS io2 EBS).

#### Gejala Masalah (Incident)
Pukul 02:00 saat *batch reconciliation* dijalankan oleh legacy analytics service, latensi pemrosesan transaksi API gateway melonjak dari `P99: 12ms` menjadi `P99: 8.400ms`. Sejumlah besar koneksi client me-reconnect, memicu *cascading connection pool saturation* dan *circuit-breaker trips*.

#### Investigasi Diagnostik (RCA Pipeline)
1. **Analisis Log Engine**:
   Log mencatat banyak pesan:
   `WiredTiger thread wait: Waited 1420ms for checkpoint lock`
   `WiredTiger cache eviction: application thread helped with eviction`
2. **Analisis FTDC**:
   - `wiredTiger.cache.tracked dirty bytes in the cache` mencapai 22% dari total cache size.
   - `concurrentTransactions.write.available` turun ke angka `0`.
   - `iostat` menunjukkan `r_await` normal (0.4ms), tetapi `w_await` melompat ke 45ms akibat checkpoint menulis volume dirty pages raksasa bersamaan dengan log stream.
3. **Penyebab Utama**:
   Proses analitik menjalankan full-collection aggregation dengan parameter `{ allowDiskUse: true }` tanpa index memadai, memicu swap out memory cache dan memaksa engine membuang dirty buffer mutasi real-time. Pada saat bersamaan, Transparent Huge Pages (THP) masih berstatus `[always]`, menyebabkan latency penalty akibat memory compaction kernel.

#### Remediasi & Resolusi
1. **Immediate Action**:
   - Mengidentifikasi dan membunuh query analitik via:
     ```javascript
     db.currentOp({ "command.aggregate": { $exists: true }, "secs_running": { $gt: 30 } })
       .inprog.forEach(op => db.killOp(op.opid));
     ```
   - Mengisolasi analytic workload menggunakan Dedicated Read-Only Analytical Secondary (menggunakan tag sets `{ role: "analytics" }` dan read preference `secondary`).
2. **Permanent Kernel & Configuration Tuning**:
   - Mematikan THP secara permanen via init script.
   - Menyetel konfigurasi WiredTiger cache and eviction triggers pada `/etc/mongod.conf`:
     ```yaml
     storage:
       wiredTiger:
         engineConfig:
           cacheSizeGB: 180
           configString: "eviction=(threads_min=4,threads_max=8),eviction_dirty_trigger=5,eviction_dirty_target=2"
     ```
   - Hasil implementasi: Latensi P99 pasca-tuning turun stabil di `9ms` bahkan saat proses reconcilation berjalan simultan.

---

### 9. Trade-offs

```
                  Memory Sizing Trade-off Triangle
                             [Latency]
                              ▲     ▲
                             /       \
                            /         \
   (Larger WT Cache:       /           \  (Smaller WT Cache:
    Less IOPS reads,      /             \  More OS Page Cache,
    Higher Checkpoint     ▼             ▼  Faster Checkpoints,
    Overhead)   [Throughput] ◄─────────► [Crash Recovery Time]
```

| Parameter / Arsitektur | Opsi A | Opsi B | Trade-off / Analisis Konsekuensi |
| :--- | :--- | :--- | :--- |
| **WiredTiger Cache Size** | **Besar (e.g., 85% Host RAM)** | **Moderat (e.g., 50% Host RAM - Default)** | Cache besar memaksimalkan working set index/data in-memory, tetapi membatasi OS Filesystem Cache. Akibatnya, operasi checkpoint dan file read disk direct mengalami degradasi, serta risiko OOM killer Linux meningkat tajam. |
| **Journal Commit Interval** | **Sangat Singkat (`commitIntervalMs: 10`)** | **Default (`commitIntervalMs: 100`)** | Menurunkan recovery point objective (RPO) jika power loss terjadi, tetapi memakan write bandwidth NVMe secara konstan; mengurangi performa *write throughput* maksimum. |
| **WiredTiger Eviction Threads** | **Agresif (Min 4, Max 12)** | **Konservatif (Min 1, Max 4)** | Thread agresif mencegah *application eviction stalls*, tetapi mengonsumsi core CPU tambahan secara background yang dapat merebut jatah CPU query worker normal. |
| **Index Prefixing vs Coverage** | **Compound Covered Indexes** | **Index Tipis (Hanya Lookup Key)** | Covered indexes meniadakan tahapan document retrieval di disk/cache, tetapi meningkatkan memori RAM yang dibutuhkan WiredTiger untuk menyimpan index footprint. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum Produksi
1. **Membiarkan Transparent Huge Pages (THP) Aktif**: Memicu latensi read/write tidak stabil akibat latensi alokasi halaman 2MB kernel Linux.
2. **Mengabaikan Driver Connection Pool Sizing**: Menetapkan `maxPoolSize=200` pada 50 container mikroservis menghasilkan $50 \times 200 = 10.000$ koneksi ke satu replica set. Server database menghabiskan resource hanya untuk thread context switching.
3. **Write Tanpa Read Preference Aware pada Replikasi**: Membaca seluruh data dari Primary menyebabkan eviction cache tertekan, padahal operational reads dapat didelegasikan ke Secondary jika latensi replikasi terjaga.
4. **Tidak Mengatur Log Rotation**: File `mongod.log` membengkak ratusan gigabyte, menyebabkan I/O contention saat log writing.

#### Diagnostic Matrix & Troubleshooting Commands

| Gejala Masalah | Penyebab Potensial | Perintah Investigasi / Diagnostik | Solusi Cepat |
| :--- | :--- | :--- | :--- |
| `readTicketsAvailable` = 0 | Query slow unindexed menahan reader thread slots. | `db.serverStatus().concurrentTransactions` dan `db.currentOp({"waitingForLock": true})` | Hentikan query lambat via `db.killOp()`, tambahkan missing index. |
| Memory ballooning & process dibunuh `SIGKILL` | Linux OOM (Out Of Memory) Killer membunuh `mongod`. | `dmesg -T \| grep -i oom-killer` dan periksa metrik swap. | Batasi `cacheSizeGB` di konfigurasi, pastikan `vm.swappiness=1`. |
| P99 spikes berulang per interval 60 detik | Checkpoint volume terlalu masif menekan I/O subsystem. | `db.serverStatus().wiredTiger.checkpoint` & `iostat -xz 1` | Tingkatkan IOPS storage, atau turunkan `eviction_dirty_target` WiredTiger. |
| Replikasi lagging signifikan | Secondary write saturation atau CPU imbalance. | `rs.printSecondaryReplicationInfo()` dan `rs.status()` | Tingkatkan kapasitas I/O storage secondary, cek multithreaded oplog applier stats. |

---

### 11. Best Practices (Production Checklist)

#### OS & Kernel Configuration
- [ ] Nonaktifkan Transparent Huge Pages (THP) via systemd startup service unit (`/sys/kernel/mm/transparent_hugepage/enabled` = `never`).
- [ ] Atur NUMA memory interleaving policy menggunakan `numactl --interleave=all`.
- [ ] Set `vm.swappiness = 1` pada `/etc/sysctl.conf`.
- [ ] Format storage volume data menggunakan filesystem **XFS** dengan mount option: `noatime,nodiratime,logbufs=8,logbsize=256k`.
- [ ] Naikkan ulimits minimum: `nofile: 64000`, `nproc: 64000`.

#### Database Configuration (`mongod.conf`)
- [ ] Konfigurasi `storage.wiredTiger.engineConfig.cacheSizeGB` secara eksplisit sesuai kalkulasi kapasitas container/host.
- [ ] Aktifkan `operationProfiling.mode: "slowOp"` dengan `slowOpThresholdMs` terdefinisi (misal `50ms`).
- [ ] Konfigurasi log redaction jika menangani data sensitif (`security.redactClientLogData: true`).
- [ ] Konfigurasi rotasi log runtime menggunakan parameter `systemLog.logRotate: reopen` dikombinasikan dengan sistem utilitas `logrotate`.

#### Connection Pool Tuning (Application Client)
- [ ] Pasang batas `minPoolSize` (10-20% dari pool) dan `maxPoolSize` (umumnya 20-50 per instance app, bukan 200+).
- [ ] Set `maxIdleTimeMS` untuk membersihkan socket zombie.
- [ ] Gunakan `serverSelectionTimeoutMS: 5000` dan `connectTimeoutMS: 10000` untuk *fast-failing*.

---

### 12. Hands-on Practice

Simulasi menyeluruh diagnostik bottleneck performa, identifikasi query unindexed yang menekan eviction cache, dan profiling mendalam.

File praktikum disimpan pada: `hands-on/m02/`

#### Struktur Direktori
```
hands-on/m02/
├── docker-compose.yml
├── init-kernel.sh
├── workload-generator.js
└── diagnostic-inspector.js
```

#### Langkah 1: Siapkan Lingkungan Simulasi (`docker-compose.yml`)
```yaml
version: '3.8'
services:
  mongodb-sre:
    image: mongo:7.0
    container_name: mongodb-sre-lab
    command: >
      mongod --wiredTigerCacheSizeGB 0.5
             --profile 1
             --slowms 20
             --oplogSize 512
             --bind_ip_all
    ports:
      - "27017:27017"
    volumes:
      - mongo-sre-data:/data/db
    ulimits:
      nofile:
        soft: 64000
        hard: 64000
      nproc: 64000

volumes:
  mongo-sre-data:
```

Jalankan container:
```bash
docker compose up -d
```

#### Langkah 2: Script Pembangkit Beban Konkurensi & Memory Pressure (`workload-generator.js`)
Script ini mensimulasikan mutasi data intensif bersamaan dengan query aggregasi tidak efisien yang membanjiri WiredTiger cache:

```javascript
// hands-on/m02/workload-generator.js
const { MongoClient } = require('mongodb');

const URI = 'mongodb://localhost:27017';
const DB_NAME = 'telemetry_db';
const COLL_NAME = 'device_metrics';

async function seedData(client) {
  const coll = client.db(DB_NAME).collection(COLL_NAME);
  console.log('Seeding baseline 100,000 documents...');
  const docs = [];
  for (let i = 0; i < 100000; i++) {
    docs.push({
      deviceId: `DEV-${i % 500}`,
      tenantId: `TNT-${i % 20}`,
      metricValue: Math.random() * 1000,
      timestamp: new Date(Date.now() - Math.floor(Math.random() * 10000000)),
      payload: 'X'.repeat(512) // String padding untuk menekan cache
    });
  }
  await coll.insertMany(docs);
  console.log('Baseline seeded.');
}

async function runContentionWorkload() {
  const client = new MongoClient(URI, { maxPoolSize: 50 });
  await client.connect();
  const coll = client.db(DB_NAME).collection(COLL_NAME);

  await seedData(client);

  console.log('Triggering concurrency traffic with heavy unindexed queries...');

  // Worker 1: Mutasi write konstan (Dirty data generator)
  const writeWorker = async () => {
    while (true) {
      const batch = [];
      for (let i = 0; i < 50; i++) {
        batch.push({
          deviceId: `DEV-NEW-${Math.floor(Math.random() * 1000)}`,
          tenantId: 'TNT-STORM',
          metricValue: Math.random() * 5000,
          timestamp: new Date(),
          payload: 'D'.repeat(1024)
        });
      }
      await coll.insertMany(batch);
      await new Promise(r => setTimeout(r, 10));
    }
  };

  // Worker 2: Unindexed aggregation scanning (Cache eviction trigger)
  const readWorker = async () => {
    while (true) {
      try {
        await coll.find({
          tenantId: 'TNT-STORM',
          metricValue: { $gt: 4500 }
        }).sort({ timestamp: -1 }).toArray();
      } catch (err) {
        console.error('Query error:', err.message);
      }
      await new Promise(r => setTimeout(r, 50));
    }
  };

  // Jalankan worker simultan
  Promise.all([
    writeWorker(),
    readWorker(),
    readWorker(),
    readWorker()
  ]).catch(console.error);
}

runContentionWorkload();
```

Jalankan script generator di terminal 1:
```bash
node hands-on/m02/workload-generator.js
```

#### Langkah 3: Script Diagnostik & Analisis Bottleneck (`diagnostic-inspector.js`)
Jalankan script ini di terminal 2 untuk memantau eviksi cache, latency degradasi, dan profile query:

```javascript
// hands-on/m02/diagnostic-inspector.js
const { MongoClient } = require('mongodb');

async function inspectRuntime() {
  const client = new MongoClient('mongodb://localhost:27017');
  await client.connect();
  const admin = client.db('admin');
  const db = client.db('telemetry_db');

  console.log('Collecting SRE Diagnostics (Sampling interval: 2s)...');

  setInterval(async () => {
    const sStatus = await admin.command({ serverStatus: 1 });
    const wtCache = sStatus.wiredTiger.cache;
    const currentOps = await admin.command({ currentOp: 1, "secs_running": { $gte: 1 } });

    const maxBytes = wtCache['maximum bytes configured'];
    const currentBytes = wtCache['bytes currently in the cache'];
    const dirtyBytes = wtCache['tracked dirty bytes in the cache'];
    const appEvictionWorkerCount = wtCache['application threads page write hours to evict'];

    console.clear();
    console.log('================ MONGO SRE DIAGNOSTIC CONSOLE ================');
    console.log(`Cache Utilization : ${((currentBytes / maxBytes) * 100).toFixed(2)}% (${(currentBytes / 1024 / 1024).toFixed(1)}MB / ${(maxBytes / 1024 / 1024).toFixed(1)}MB)`);
    console.log(`Dirty Cache Ratio : ${((dirtyBytes / maxBytes) * 100).toFixed(2)}%`);
    console.log(`Read Tickets Left : ${sStatus.concurrentTransactions.read.available}`);
    console.log(`Write Tickets Left: ${sStatus.concurrentTransactions.write.available}`);
    console.log(`Slow Ops (>1s)    : ${currentOps.inprog.length} active queries`);
    
    // Check slow queries via Profiler Collection
    const slowQueries = await db.collection('system.profile')
      .find({})
      .sort({ ts: -1 })
      .limit(3)
      .toArray();

    console.log('\n--- Top Recent Slow Queries (Profile Collection) ---');
    slowQueries.forEach(q => {
      console.log(`[${q.millis}ms] Op: ${q.op} | Docs Examined: ${q.docsExamined} | Returned: ${q.nreturned} | Plan: ${q.planSummary}`);
    });
    console.log('==============================================================');
  }, 2000);
}

inspectRuntime().catch(console.error);
```

Jalankan script inspeksi:
```bash
node hands-on/m02/diagnostic-inspector.js
```

#### Langkah 4: Terapkan Optimasi dan Buktikan Recovery
Buka terminal 3 dan terapkan indeks majemuk (*compound index*) untuk menghentikan full-scan memory thrasher:
```bash
mongosh "mongodb://localhost:27017/telemetry_db" --eval '
  db.device_metrics.createIndex({ tenantId: 1, metricValue: 1, timestamp: -1 });
'
```
Amati terminal 2:
- Nilai `Docs Examined` akan turun menyamai nilai `Returned`.
- `Dirty Cache Ratio` stabil turun kembali ke batas aman.
- Slow operations (>1s) hilang.

---

### 13. Exercise

#### Level: Easy
Analisis log berikut dan tentukan anomali engine yang terjadi:
```text
{"t":{"$date":"2026-03-30T10:15:20.120+00:00"},"s":"I", "c":"COMMAND", "id":51803, "ctx":"conn42","msg":"Slow query","attr":{"type":"command","ns":"store.orders","command":{"find":"orders","filter":{"status":"PENDING"}},"planSummary":"COLLSCAN","docsExamined":850000,"nreturned":12,"millis":4230}}
```
- **Tugas**: Sebutkan 2 parameter yang mengonfirmasi bahwa operasi ini membebani disk & memory cache, lalu tuliskan perintah index untuk menyelesaikannya.

#### Level: Medium
Diberikan server database Linux Ubuntu 22.04 LTS host MongoDB mandiri dengan memori fisik 64 GB RAM. 
- **Tugas**:
  1. Hitung alokasi default WiredTiger Cache Size.
  2. Tuliskan blok konfigurasi `storage.wiredTiger.engineConfig` di `/etc/mongod.conf` jika server ini berbagi peran dengan node monitoring Prometheus exporter lokal dan membutuhkan reserved OS memory 16 GB.
  3. Konfigurasikan batas *dirty eviction trigger* menjadi 8% dan target dirty cache ke 3%.

#### Level: Hard
Koneksi antara mikroservis cluster Kubernetes dan replica set MongoDB tiba-tiba mengalami lonjakan error timeout: `MongoNetworkTimeoutException: socketTimeoutMS expired on waiting for connection`. 
- Metrik VM MongoDB menunjukkan CPU 98% (dengan 60% waktu dihabiskan pada `sy` / kernel system space).
- Jumlah koneksi client di `serverStatus.connections.current` adalah 8.500 koneksi.
- Memory swap bertambah perlahan.
- **Tugas**: 
  1. Jelaskan rantai peristiwa internal sistem yang menyebabkan CPU system space mendominasi utilisasi core CPU.
  2. Rancang rencana mitigasi arsitektur jaringan, modifikasi konfigurasi mongod, dan setting client driver SDK untuk mengamankan koneksi tanpa menolak traffic pengguna.

---

### 14. Challenge

**Skenario Sistem Finansial Multinasional (Tantangan Tanpa Panduan Instan):**
Bank Digital bersiap menghadapi event flash sale berskala masif. Sistem berjalan di atas MongoDB Replica Set (3 data nodes + 1 hidden analytics node). Target SLO: P99.9 latency transaksi mutasi kredit/debit harus di bawah 15ms pada beban 40.000 request per detik.

Spesifikasi Server:
- Node: Bare-metal Supermicro, Dual AMD EPYC (Total 128 vCPU), 512 GB DDR4 RAM, 2x Enterprise NVMe (U.2) Software RAID 1.
- OS: RHEL 9 Kernel 5.14.

**Tantangan Engineering:**
1. Rancang dokumen arsitektur komprehensif sistem level reliability:
   - Buat skrip konfigurasi kernel Linux `/etc/sysctl.d/99-mongodb-sre.conf` lengkap yang mencakup parameter memory management (NUMA policy, dirty writeback control, page cache reclaiming) dan networking tuning.
   - Buat skrip Bash validasi otomatis (`pre-flight-check.sh`) yang dijalankan via pipeline CI/CD untuk memverifikasi kesiapan lingkungan (THP status, disk IO scheduler, filesystem mount options, ulimits).
2. Tentukan kalkulasi formula WiredTiger cache sizing yang memperhitungkan alokasi kernel page cache agar read traffic yang mengakses file cold storage lama tidak menyebabkan dirty cache evictions pada primary transaction cache.
3. Rancang strategi monitoring FTDC otomatis yang dapat mengekstrak metrik internal `diagnostic.data`, mendeteksi anomali *WiredTiger ticket saturation* sebelum mencapai angka 0, dan memicu proteksi *traffic shedding* via API Gateway rate limiter.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Berapa alokasi memori default yang digunakan WiredTiger Cache dari total physical RAM host?
   - A. 80% dari Total RAM
   - B. $0.5 \times (\text{Total RAM} - 1\text{ GB})$
   - C. $0.75 \times \text{Total RAM}$
   - D. 100% Total RAM dikurangi alokasi 4GB OS

2. Apa efek utama dari mengaktifkan Transparent Huge Pages (THP) pada server host MongoDB?
   - A. Mempercepat throughput transaksi in-memory hingga 2 kali lipat.
   - B. Menghemat konsumsi memori disk journal WiredTiger.
   - C. Memicu memory fragmentation, lock contention, dan latensi query yang mendadak melonjak.
   - D. Mencegah Linux mematikan database melalui mekanisme Out-Of-Memory (OOM) Killer.

3. Apa arti dari metrik `planSummary: "COLLSCAN"` pada data profiling MongoDB?
   - A. Query berjalan optimal menggunakan Index Filter.
   - B. Query memindai seluruh dokumen dalam koleksi secara linier tanpa memanfaatkan index.
   - C. Operasi query membaca data langsung dari memory cache WiredTiger tanpa I/O disk.
   - D. Query mengalami crash akibat memory over-allocation.

4. Direktori manakah yang menyimpan rekaman metrik time-series diagnostik default MongoDB (FTDC)?
   - A. `/var/log/mongodb/audit.log`
   - B. `/var/lib/mongodb/journal/`
   - C. Direktori database di dalam folder `diagnostic.data/`
   - D. `/etc/mongod/diagnostic.bin`

5. Berapakah nilai ideal dari `vm.swappiness` pada Linux Kernel untuk database MongoDB?
   - A. 60
   - B. 100
   - C. 1
   - D. -1

#### B. Pertanyaan Intermediate
6. Apa yang terjadi pada level sistem jika metrik WiredTiger cache mencapai ambang *Application Eviction* (>95%)?
   - A. MongoDB server akan seketika melakukan graceful shutdown.
   - B. Client thread yang mengeksekusi query akan dipaksa membantu menulis dirty pages ke storage, menyebabkan throughput drop drastis dan latensi melonjak tajam.
   - C. Storage engine langsung menghapus dirty pages tanpa menyimpannya ke disk journal.
   - D. Node otomatis melepaskan peran Primary dan memicu *step down*.

7. Mengapa setting `numactl --interleave=all` direkomendasikan pada hardware dual-socket CPU yang menjalankan MongoDB?
   - A. Untuk mematikan hyperthreading core CPU agar lebih hemat daya.
   - B. Mencegah situasi di mana salah satu node memori NUMA lokal kehabisan alokasi dan memicu kernel paging/swapping lambat, padahal node NUMA lainnya masih kosong.
   - C. Menghubungkan MongoDB secara eksklusif ke kartu jaringan fisik (NIC) primer.
   - D. Memaksa data disimpan pada swap memory terlebih dahulu sebelum dieksekusi CPU.

8. Bila metrik `serverStatus.concurrentTransactions.write.available` bernilai 0, dampaknya terhadap operasi write baru adalah:
   - A. Request write baru akan langsung ditolak dengan return code HTTP 500.
   - B. Request write baru akan masuk ke antrean (*queued*), menunggu tiket kosong, dan menaikkan latency client.
   - C. MongoDB beralih ke in-memory mode dan mengabaikan ACID transactions.
   - D. Operasi diarahkan secara otomatis ke node Secondary terdekat.

9. Apa perbedaan esensial antara filesystem **XFS** dan **EXT4** dalam konteks operasional WiredTiger storage engine berskala I/O intensif?
   - A. EXT4 tidak mendukung transaksi ACID.
   - B. XFS mengelola alokasi konkurensi write secara paralel lebih baik (*allocation groups*) dan menghindari bottleneck *file allocation lock* yang kerap muncul pada EXT4 di bawah write load masif.
   - C. XFS mengompresi data sebelum sampai ke storage engine WiredTiger.
   - D. EXT4 tidak mengizinkan ukuran journal file melebihi 2 GB.

10. Apa indikator metrik yang paling tepat untuk mendeteksi bahwa disk I/O subsistem telah jenuh (*saturated*) pada saat WiredTiger checkpoint berjalan?
    - A. Utilisasi memory cache WiredTiger mencapai 10%.
    - B. Nilai `%util` pada utilitas `iostat` mendekati 100% dibarengi dengan kenaikan metrik `w_await` yang tinggi.
    - C. Penurunan jumlah koleksi database pada `serverStatus`.
    - D. Nilai `network.bytesIn` mendadak menjadi 0.

#### C. Skenario Kasus Produksi
11. **Kasus 1**: Pada cluster replikasi MongoDB, Primary mengalami utilisasi CPU sebesar 30%, namun Secondary konsisten mengalami utilisasi CPU 100% dan replication lag terus membengkak (RPO terancam). Diketahui tidak ada read traffic yang diarahkan ke Secondary sama sekali. Apa penyebab paling logis dari degradasi performa Secondary ini?
    - A. Secondary secara otomatis menjalankan disk defragmentation background setiap 1 jam.
    - B. Operasi write pada Primary diproses secara multithreaded paralel, sedangkan operasi penulisan pada Secondary terhambat oleh keterbatasan paralelisme thread replay oplog atau Secondary menggunakan disk dengan IOPS jauh lebih lambat dibanding Primary.
    - C. Oplog buffer Secondary otomatis mematikan cache WiredTiger.
    - D. Secondary kehilangan koneksi jaringan heartbeat dengan Primary.

12. **Kasus 2**: Sebuah aplikasi e-commerce mendadak menerima status `504 Gateway Timeout`. Saat diperiksa via MongoDB Profiler, ditemukan ribuan query find sederhana berbasis `id` pembayaran yang biasanya selesai dalam 1ms, kini membutuhkan waktu 3.500ms. Metrik `serverStatus.locks.Global.acquireWaitCount` dan `acquireTimeAcquisitions` sangat tinggi. Apa langkah mitigasi diagnostik pertama yang wajib dieksekusi engineer?
    - A. Memformat ulang disk volume MongoDB dan restore dari cold backup.
    - B. Memeriksa `db.currentOp()` untuk mencari operasi metadata lock eksklusif berdurasi panjang (seperti pembuatan indeks latar depan (`foreground index build`), drop collection, atau operasi checkpoint/collMod yang menahan antrean lock global).
    - C. Mengurangi alokasi memory cache WiredTiger menjadi setengahnya.
    - D. Menghapus koneksi SSL/TLS pada layer database.

13. **Kasus 3**: Tim SRE mendapati metrik host Linux MongoDB melaporkan swap usage sebesar 12 GB, padahal parameter `wiredTiger.engineConfig.cacheSizeGB` telah disetel ke 50% RAM server. Server mengalami lonjakan `si` (swap-in) dan `so` (swap-out) pada `vmstat`. Komponen mana di luar cache WiredTiger yang paling mungkin mengonsumsi sisa RAM fisik host hingga memicu swap memory?
    - A. In-memory Oplog metadata collection.
    - B. Konsumsi memori per-koneksi client (thread stack ~1MB + buffer koneksi) dari ribuan connection sockets yang tidak dibatasi, digabung dengan alokasi heap memori agregasi (`allowDiskUse: false`) dan alokasi Linux OS page cache.
    - C. Log journal WiredTiger secara default memakan seluruh sisa memori OS.
    - D. Driver internal MongoDB me-mirror seluruh isi SSD ke RAM.

---

### Kunci Jawaban Quiz

#### A. Pertanyaan Basic
1. **B** — Default cache size WiredTiger adalah $0.5 \times (\text{Total RAM} - 1\text{ GB})$.
2. **C** — THP memicu memory fragmentation, latch/lock stalls, dan latensi query yang melompat tak terduga pada database engine.
3. **B** — `COLLSCAN` mengindikasikan full collection scan (seluruh dokumen dipindai karena tidak ada index yang cocok).
4. **C** — File diagnostik FTDC disimpan di direktori database di folder `diagnostic.data/`.
5. **C** — Nilai `vm.swappiness = 1` mencegah OS melakukan swapping agresif, tetapi tidak mematikan swap sepenuhnya untuk mencegah OOM panics.

#### B. Pertanyaan Intermediate
6. **B** — Application thread eviction aktif saat ambang kritis terlampaui; thread client dipaksa menulis dirty pages ke storage engine, membekukan pemrosesan query normal.
7. **B** — Policy interleaved meratakan alokasi memori antar-node NUMA fisik, mencegah starvation pada satu socket memori lokal.
8. **B** — Tiket ketersediaan transaksi WiredTiger membatasi konkurensi concurrent engine; jika tiket habis (0), operasi client berikutnya harus mengantre.
9. **B** — XFS menangani alokasi block konkurensi skala enterprise jauh lebih stabil dibanding EXT4 berkat arsitektur alokasi paralelnya (*allocation groups*).
10. **B** — Nilai disk saturation `%util` mendekati 100% dan latensi penulisan disk (`w_await`) yang tinggi adalah tanda pasti subsistem storage I/O mengalami bottleneck saat checkpointing.

#### C. Skenario Kasus Produksi
11. **B** — Secondary harus menerapkan log mutasi (*oplog replay*). Jika secondary memiliki spek storage/IOPS lebih rendah, atau write lock terhambat oleh pembacaan internal, Secondary akan tertinggal dan memicu lag replikasi tinggi.
12. **B** — Lonjakan acquire wait time pada global locks menunjukkan adanya operasi DDL atau lock eksklusif (seperti DDL schema modification atau index unoptimized) yang menahan antrean operasi lain di belakangnya.
13. **B** — Koneksi client memakan memori OS thread stack (~1MB per koneksi), sehingga 10.000 koneksi menghabiskan ~10GB RAM di luar WiredTiger cache. Agregasi memory buffers yang besar juga turut menghabiskan free memory host.

---

### 16. Summary

1. **WiredTiger Memory Management Lifecycle**: Memori MongoDB terbagi antara WiredTiger internal cache dan OS Filesystem Page Cache. Menjaga keseimbangan *clean vs dirty pages* serta mencegah terjadinya *application eviction* adalah kunci menjaga kestabilan latensi P99.
2. **Linux Kernel Alignment**: MongoDB tidak dapat bekerja optimal tanpa penyesuaian OS level. Menonaktifkan Transparent Huge Pages (THP), mengonfigurasi NUMA interleaving (`numactl --interleave=all`), serta membatasi `vm.swappiness=1` adalah fondasi mutlak keandalan database enterprise.
3. **I/O Subsystem & Checkpointing**: Lonjakan latensi periodik sering kali berakar dari bottleneck I/O saat checkpointing data kotor ke disk. Pemilihan sistem berkas (XFS) dan penyediaan IOPS NVMe yang mencukupi merupakan penentu performa throughput *write-heavy*.
4. **Operational Diagnostics First**: Pemanfaatan FTDC (`diagnostic.data`), query profiler internal, serta metrik `serverStatus` (`concurrentTransactions`, `locks`, `cache`) memberikan data telemetri komprehensif untuk mendeteksi dan memitigasi bottleneck database sebelum berdampak pada SLO sistem.