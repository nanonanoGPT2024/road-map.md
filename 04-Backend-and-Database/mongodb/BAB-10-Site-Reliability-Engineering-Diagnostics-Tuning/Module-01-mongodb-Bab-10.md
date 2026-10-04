# Modul MongoDB: Site Reliability Engineering, Diagnostics & Tuning

---

## 01: Identitas Modul
* **Track:** Database Engineering & Architecture
* **Kategori:** 04-Backend-and-Database
* **Topik:** MongoDB
* **Tingkat Kesulitan:** Advanced / Production-Grade (Level 400)
* **Prasyarat:** Pemahaman mendalam tentang Replicaset Internals, WiredTiger Storage Engine, Profiling, Linux Kernel Subsystems (Virtual Memory, I/O Subsystem, Page Cache).

---

## 02: Learning Objectives
1. Mengimplementasikan metrik Service Level Objective (SLO), Service Level Indicator (SLI), dan Error Budget berbasis observabilitas MongoDB (FTDC, Profiler, ServerStatus).
2. Mendiagnosis degradasi performa internal WiredTiger Storage Engine, meliputi Ticket Exhaustion, Cache Dirty Fill Rate, Eviction Latency, dan Checkpoint Locks.
3. Melakukan kernel, storage, dan network tuning pada sistem operasi Linux khusus untuk beban kerja MongoDB throughput tinggi.
4. Menerapkan instrumentasi diagnostik real-time, Automated Slow Query Remediation, dan Dynamic Capacity Planning berbasis telemetri.

---

## 03: Concept Map Diagram ASCII
```
+-------------------------------------------------------------------------------+
|                       MONGODB SRE & PERFORMANCE ECOSYSTEM                    |
+-------------------------------------------------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+-----------------------------+                           +-----------------------------+
|    LINUX KERNEL TUNING      |                           |   WIREDTIGER INTERNALS      |
|  - THP: Disabled            |                           |  - Read/Write Tickets (128) |
|  - vm.swappiness = 1        |                           |  - Eviction Workers (Dirty) |
|  - vm.dirty_ratio = 10      |                           |  - Checkpointing Interval   |
|  - NVMe / Noop Scheduler    |                           |  - Page Cache vs WT Cache   |
+-----------------------------+                           +-----------------------------+
         |                                                         |
         +----------------------------+----------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                           DIAGNOSTIC & OBSERVABILITY                          |
|  - FTDC (Diagnostic Data Capture)   - Slow Query Profiler (P99 Latency)       |
|  - serverStatus().wiredTiger        - Lock Analysis (Global, DB, Collection)  |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                       SRE RELIABILITY & REMEDIATION                           |
|  - SLI/SLO Monitoring               - Automated Index Injection               |
|  - Dynamic Query Throttling         - Kill Op Long-running Worker             |
+-------------------------------------------------------------------------------+
```

---

## 04: Mengapa Relevan
Dalam skala enterprise, sebagian besar downtime dan degradasi performa MongoDB tidak disebabkan oleh bug perangkat lunak aplikasi, melainkan oleh ketidaksesuaian antara konfigurasi OS, konkurensi internal WiredTiger Storage Engine, dan kueri yang tidak terindeks yang menguras sumber daya sistem.

Tanpa pemahaman mendalam tentang metrik internal (seperti *concurrentTransactions tickets* dan *dirty cache ratio*), tim rekayasa sering salah mengidentifikasi masalah sebagai "kebutuhan scaling horizontal" yang berbiaya tinggi, padahal akar masalahnya adalah *eviction stalls* atau *checkpoint lock contention*. Modul ini menyajikan metodologi deterministik berbasis SRE untuk menjaga latensi P99 tetap rendah dan ketersediaan sistem melampaui 99.99%.

---

## 05: Anatomi Konsep Inti

### 1. WiredTiger Concurrency & Queue Execution
WiredTiger mengalokasikan 128 *read tickets* dan 128 *write tickets* secara default. Ketika kueri memicu pembacaan disk besar-besaran atau eksekusi kueri yang lambat, tiket ini tertahan, memicu *Ticket Exhaustion*. Akibatnya, koneksi aplikasi baru akan mengantre pada tahap `globalLock.currentQueue`, menyebabkan lonjakan latensi dramatis (*cliff edge performance degradation*).

### 2. WiredTiger Cache Eviction Dynamics
Ukuran cache WiredTiger default diatur ke:
$$\text{WT Cache Size} = 0.5 \times (\text{RAM Total} - 1\text{ GB})$$
Proses *eviction* data dari cache ke disk dilakukan secara bertahap:
* **Eviction Trigger (Dirty):** Dimulai ketika persentase dirty data mencapai ambang batas `eviction_dirty_trigger` (default: 5% - 20%).
* **Application Thread Eviction (Stall Condition):** Jika *dirty data* melebihi ambang batas kritis (default: 20%), thread aplikasi yang melakukan penulisan akan dipaksa ikut serta melakukan *eviction* ke disk, membekukan eksekusi kueri aplikasi normal.

### 3. Linux Kernel & Subsystem Mismatch
* **Transparent Huge Pages (THP):** Menyebabkan fragmentasi memori, latensi alokasi mendadak (*compaction stalls*), dan agresifitas memori yang berlebihan. Harus dinonaktifkan (`never`).
* **Swappiness:** MongoDB memerlukan pemanfaatan disk buffer cache secara optimal. `vm.swappiness` wajib diatur ke `1` (atau `0` pada kernel lama) untuk mencegah alokasi memori aktif dipindahkan ke disk swap.
* **Dirty Page Flushes:** `vm.dirty_background_ratio` dan `vm.dirty_ratio` harus diatur rendah agar OS mem-flush data secara teratur dan menghindari *I/O spikes* besar yang memblokir WiredTiger checkpointing.

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Konfigurasi Kernel Linux dan Systemd Unit File

Buat skrip inisialisasi kernel tuning di `/etc/sysctl.d/99-mongodb-sre.conf`:

```ini
# Virtual Memory Configuration
vm.swappiness = 1
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
vm.max_map_count = 1600000
vm.zone_reclaim_mode = 0

# Network Backlog & TCP Tuning
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 120
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 4
```

Terapkan konfigurasi:
```bash
sudo sysctl -p /etc/sysctl.d/99-mongodb-sre.conf
```

### Langkah 2: Nonaktifkan Transparent Huge Pages (THP) Secara Permanen

Buat systemd service `/etc/systemd/system/disable-thp.service`:

```ini
[Unit]
Description=Disable Transparent Huge Pages (THP) for MongoDB
DefaultDependencies=no
After=sysinit.target local-fs.target
Before=mongod.service

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled && echo never > /sys/kernel/mm/transparent_hugepage/defrag'

[Install]
WantedBy=basic.target
```

Aktifkan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now disable-thp.service
```

### Langkah 3: Konfigurasi `mongod.conf` Berbasis Kinerja Lanjut

```yaml
systemLog:
  destination: file
  path: /var/log/mongodb/mongod.log
  logAppend: true
  logRotate: reopen
  verbosity: 1
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true
  wiredTiger:
    engineConfig:
      cacheSizeGB: 15 # Disesuaikan: 50% RAM pada node 32GB
      journalCompressor: snappy
      directoryForIndexes: true
    collectionConfig:
      blockCompressor: snappy
    indexConfig:
      prefixCompression: true
processManagement:
  fork: false
  timeZoneInfo: /usr/share/zoneinfo
net:
  port: 27017
  bindIp: 0.0.0.0
  maxIncomingConnections: 30000
operationProfiling:
  mode: slowOp
  slowOpThresholdMs: 50
  slowOpSampleRate: 1.0
```

---

## 07: Contoh Kasus Sederhana

Mendiagnosis ketersediaan ticket WiredTiger saat terjadi lonjakan traffic menggunakan mongosh:

```javascript
// Diagnostik Tiket Konkurensi WiredTiger
function checkWiredTigerHealth() {
  const serverStatus = db.serverStatus();
  
  const wt = serverStatus.wiredTiger;
  const readTickets = wt.concurrentTransactions.read.available;
  const writeTickets = wt.concurrentTransactions.write.available;
  const totalRead = wt.concurrentTransactions.read.totalTickets;
  const totalWrite = wt.concurrentTransactions.write.totalTickets;
  
  const dirtyBytes = wt.cache["tracked dirty bytes in the cache"];
  const maxBytes = wt.cache["maximum bytes configured"];
  const dirtyPercentage = (dirtyBytes / maxBytes) * 100;
  
  print("=== WIREDTIGER INTERNALS SNAPSHOT ===");
  print(`Read Tickets Available  : ${readTickets} / ${totalRead}`);
  print(`Write Tickets Available : ${writeTickets} / ${totalWrite}`);
  print(`Cache Dirty Percentage  : ${dirtyPercentage.toFixed(2)}%`);
  
  if (readTickets < 10 || writeTickets < 10) {
    print("[CRITICAL] Ticket exhaustion detected! Pipeline bottleneck imminent.");
  }
  if (dirtyPercentage > 15.0) {
    print("[WARNING] Dirty cache exceeds safe threshold (>15%). Application eviction likely.");
  }
}

checkWiredTigerHealth();
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah skrip kontrol daemon diagnostik otonom berbasis Node.js yang memantau performa MongoDB, mendeteksi *ticket starvation*, mendeteksi *unindexed operations*, dan secara otomatis membatalkan (*kill*) operasi runaway jika melampaui ambang batas latensi kritis.

```typescript
// diagnostic_daemon.ts
import { MongoClient, Document } from "mongodb";
import * as fs from "fs";

interface SREMetrics {
  timestamp: string;
  readTicketsAvailable: number;
  writeTicketsAvailable: number;
  cacheDirtyPercentage: number;
  currentQueueReaders: number;
  currentQueueWriters: number;
  activeConnections: number;
  p99LatencyMs: number;
}

class MongoSREDiagnostics {
  private client: MongoClient;
  private isRunning: boolean = true;
  private readonly URI: string;
  private readonly CHECK_INTERVAL_MS = 2000;
  private readonly DIRTY_CACHE_KILL_THRESHOLD = 20.0; // 20%
  private readonly MAX_ALLOWED_LATENCY_MS = 5000; // 5 seconds

  constructor(connectionUri: string) {
    this.URI = connectionUri;
    this.client = new MongoClient(this.URI, {
      maxPoolSize: 10,
      connectTimeoutMS: 5000,
      socketTimeoutMS: 10000,
    });
  }

  public async start(): Promise<void> {
    await this.client.connect();
    console.log("[INIT] SRE Diagnostic Daemon connected to MongoDB cluster.");

    process.on("SIGINT", async () => {
      console.log("[STOP] Terminating SRE Diagnostic Daemon...");
      this.isRunning = false;
      await this.client.close();
      process.exit(0);
    });

    while (this.isRunning) {
      try {
        await this.runDiagnosticsCycle();
      } catch (err) {
        console.error("[ERROR] Failure in diagnostic evaluation cycle:", err);
      }
      await new Promise((resolve) => setTimeout(resolve, this.CHECK_INTERVAL_MS));
    }
  }

  private async runDiagnosticsCycle(): Promise<void> {
    const adminDb = this.client.db("admin");
    const serverStatus: Document = await adminDb.command({ serverStatus: 1 });

    const wt = serverStatus.wiredTiger;
    const connections = serverStatus.connections;
    const globalLock = serverStatus.globalLock;

    const readTickets = wt.concurrentTransactions.read.available;
    const writeTickets = wt.concurrentTransactions.write.available;
    const dirtyBytes = wt.cache["tracked dirty bytes in the cache"];
    const maxCacheBytes = wt.cache["maximum bytes configured"];
    const dirtyRatio = (dirtyBytes / maxCacheBytes) * 100;

    const metrics: SREMetrics = {
      timestamp: new Date().toISOString(),
      readTicketsAvailable: readTickets,
      writeTicketsAvailable: writeTickets,
      cacheDirtyPercentage: parseFloat(dirtyRatio.toFixed(2)),
      currentQueueReaders: globalLock.currentQueue.readers,
      currentQueueWriters: globalLock.currentQueue.writers,
      activeConnections: connections.current,
      p99LatencyMs: serverStatus.opLatencies?.reads?.latency || 0,
    };

    this.evaluateSLOHealth(metrics);

    if (dirtyRatio >= this.DIRTY_CACHE_KILL_THRESHOLD || readTickets === 0 || writeTickets === 0) {
      await this.remediateRunawayOperations(adminDb);
    }
  }

  private evaluateSLOHealth(metrics: SREMetrics): void {
    const logPayload = JSON.stringify(metrics);
    fs.appendFileSync("/var/log/mongodb/sre-metrics.log", logPayload + "\n");

    if (metrics.readTicketsAvailable < 10 || metrics.writeTicketsAvailable < 10) {
      console.warn(`[ALERT][SLO_BREACH_RISK] Tickets depleted: Read=${metrics.readTicketsAvailable}, Write=${metrics.writeTicketsAvailable}. Queue Readers=${metrics.currentQueueReaders}`);
    }

    if (metrics.cacheDirtyPercentage > 15.0) {
      console.warn(`[ALERT][DEGRADATION] High WiredTiger Dirty Cache: ${metrics.cacheDirtyPercentage}%. Imminent storage eviction stalls.`);
    }
  }

  private async remediateRunawayOperations(adminDb: any): Promise<void> {
    console.warn("[REMEDIATION] Remediation triggered: Analyzing `currentOp` for unbounded long-running operations...");

    const operations: Document = await adminDb.command({
      currentOp: 1,
      active: true,
      secs_running: { $gt: 5 },
      op: { $in: ["query", "aggregate", "update"] },
    });

    for (const inprog of operations.inprog) {
      // Abaikan sistem operasi internal dan replikasi
      if (inprog.ns && (inprog.ns.startsWith("local.") || inprog.ns.startsWith("admin."))) {
        continue;
      }

      console.error(`[ACTION_REQUIRED] Killing OpID ${inprog.opid} | Running: ${inprog.secs_running}s | Client: ${inprog.client} | Query: ${JSON.stringify(inprog.command)}`);
      
      try {
        await adminDb.command({ killOp: 1, op: inprog.opid });
        console.log(`[REMEDIATED] Successfully terminated OpID ${inprog.opid}`);
      } catch (killErr) {
        console.error(`[FAILED] Could not kill OpID ${inprog.opid}:`, killErr);
      }
    }
  }
}

// Eksekusi jika dijalankan langsung
const URI = process.env.MONGODB_URI || "mongodb://admin:secret@127.0.0.1:27017/admin?authSource=admin";
const daemon = new MongoSREDiagnostics(URI);
daemon.start().catch((err) => {
  console.error("[FATAL] Fatal error starting SRE Diagnostic Daemon:", err);
  process.exit(1);
});
```

---

## 09: Diagram Alur Kerja Diagnostik Otomatis ASCII

```
           +---------------------------------------------+
           |       Setiap Interval Pemantauan (2s)       |
           +---------------------------------------------+
                                  |
                                  v
           +---------------------------------------------+
           |        Jalankan `db.serverStatus()`         |
           +---------------------------------------------+
                                  |
                   +--------------+--------------+
                   |                             |
                   v                             v
     +---------------------------+ +---------------------------+
     |  WiredTiger Cache State   | | Concurrency & Tickets     |
     |  - Dirty Ratio >= 20%?    | | - Available Tickets <= 0? |
     +---------------------------+ +---------------------------+
                   |                             |
                   +--------------+--------------+
                                  |
                        [Kondisi Kritis Terpenuhi?]
                                  |
                    +-------------+-------------+
                    |                           |
                 [Ya]                         [Tidak]
                    |                           |
                    v                           v
     +-----------------------------+     +-------------------+
     | Jalankan `db.currentOp()`   |     | Append Log Metrik |
     | Scan Running Time > 5 Detik |     | Lanjutkan Siklus  |
     +-----------------------------+     +-------------------+
                    |
                    v
     +-----------------------------+
     | Filter Non-System Op        |
     +-----------------------------+
                    |
                    v
     +-----------------------------+
     | Eksekusi `db.killOp(opid)`  |
     | Emit Alert ke SRE Telemetry |
     +-----------------------------+
```

---

## 10: Analisis Trade-offs

| Parameter/Keputusan Desain | Alternatif Pilihan | Keuntungan | Kerugian/Risiko |
| :--- | :--- | :--- | :--- |
| **WiredTiger Cache Size** | Alokasi 80% RAM vs Alokasi Default (50%) | Meningkatkan *In-Memory Working Set Hit Ratio*, mengurangi Disk I/O. | Risiko terjadinya OOM (*Out Of Memory Killer*) jika OS membutuhkan Page Cache besar atau proses kompresi berjalan. |
| **Profiler Sample Rate** | `sampleRate: 1.0` (100%) vs `sampleRate: 0.05` (5%) | Menangkap setiap latensi anomali tanpa bias statistik. | Penurunan throughput penulisan sistem (*overhead write lock* ke database `system.profile`). |
| **WiredTiger Checkpoint Interval** | Interval Rendah (15s) vs Interval Standar (60s) | Recovery time saat Crash (MTTR) menjadi jauh lebih cepat. | Peningkatan Write Amplification pada NVMe/SSD, mempercepat keausan drive storage (*wear level*). |
| **THP Disabling Mode** | Runtime Disable vs Grub OS Level Boot Configuration | Fleksibel dieksekusi tanpa restart node. | Dapat tereset kembali ke mode *always* apabila server direstart tanpa systemd target statis. |

---

## 11: Best Practices & Antipatterns

### Best Practices
* Gunakan filesystem **XFS** alih-alih EXT4 untuk partisi data MongoDB, karena fragmentasi alokasi ruang disk EXT4 dapat memicu latensi *block zeroing*.
* Pasang volume NVMe terpisah untuk direktori Journaling (`storage.wiredTiger.engineConfig.directoryForIndexes: true`).
* Konfigurasikan batas sistem `ulimit` minimum: `nofile: 64000`, `nproc: 64000`, `memlock: unlimited`.
* Jalankan periodic health assessment pada **FTDC (Full Time Diagnostic Capture)** menggunakan tools parser bawaan.

### Antipatterns
* **Antipattern Swap Diaktifkan Secara Agresif:** Mengizinkan `vm.swappiness = 60` pada host database. Ini menyebabkan memory pages WiredTiger di-swap ke disk, memicu pembekuan respons sistem (*unresponsive lock*).
* **Regex Queries Tanpa Prefix Anchor:** Penggunaan regex tanpa index prefix anchor (`/^prefix/`) memicu *COLLSCAN* massal, menguras WiredTiger *read tickets*.
* **Mengabaikan Storage Stall Checkpoint:** Membiarkan dirty page bertambah tanpa throttling, yang mengakibatkan penguncian IO saat checkpoint berkala ditulis ke storage block.

---

## 12: Security Hardening

```bash
# 1. Konfigurasi Batasan Akses File Konfigurasi dan Data
sudo chown -R mongodb:mongodb /var/lib/mongodb
sudo chown -R mongodb:mongodb /var/log/mongodb
sudo chmod 700 /var/lib/mongodb
sudo chmod 600 /etc/mongod.conf

# 2. Hardening User SRE Diagnostik (Least Privilege Principle)
mongosh -u admin -p --authenticationDatabase admin <<EOF
use admin;
db.createRole({
  role: "SREDiagnosticRole",
  privileges: [
    { resource: { cluster: true }, actions: [ "serverStatus", "connPoolStats", "top", "netstat" ] },
    { resource: { db: "admin", collection: "system.profile" }, actions: [ "find" ] },
    { resource: { db: "", collection: "" }, actions: [ "killOp", "inprog" ] }
  ],
  roles: []
});

db.createUser({
  user: "sre_diagnostic_agent",
  pwd: "SecureStrongPassword987#$",
  roles: [ { role: "SREDiagnosticRole", db: "admin" } ]
});
EOF
```

---

## 13: Observabilitas & Debugging

### Mengidentifikasi Bottleneck Melalui `db.serverStatus()`
```javascript
// Analisis Contention Lock dan Latensi WiredTiger Checkpoint
const status = db.serverStatus();

print("--- GLOBAL LOCK STATS ---");
printjson(status.globalLock);

print("--- WIREDTIGER TRANSACTION CHECKPOINTS ---");
print(`Checkpoint Time Max (ms): ${status.wiredTiger.checkpoint["checkpoint time max processing time (msecs)"]}`);
print(`Checkpoint Time Total (ms): ${status.wiredTiger.checkpoint["checkpoint time total processing time (msecs)"]}`);

print("--- CONNECTION CONCURRENCY ---");
print(`Current Connections: ${status.connections.current}`);
print(`Available Connections: ${status.connections.available}`);
```

### Parsing Diagnostic Data Capture (FTDC)
MongoDB secara default mencatat metrik internal ke dalam path `/var/lib/mongodb/diagnostic.data/metrics.*`.
Gunakan alat visualisasi diagnostik berbasis terminal:
```bash
# Mengonversi FTDC binary menjadi JSON stream untuk debugging offline
bsondump /var/lib/mongodb/diagnostic.data/metrics.2026-03-30T00-00-00Z-00000 | head -n 100 > ftdc_sample.json
```

---

## 14: Benchmarking & Performance

Jalankan pengujian benchmarking menggunakan engine `sysbench` atau `ycsb` (Yahoo! Cloud Serving Benchmark) untuk mengukur performa latency envelope terhadap read/write ticket saturation.

### Pengujian Beban Kerja Agresif (Simulasi Kehabisan Tiket)
```bash
# Eksekusi stress testing benchmarking via mgeneratejs & mongoimport/k6
# Menghasilkan 1,000,000 dokumen dummy
cat <<EOF > schema.json
{
  "name": "{{name()}}",
  "email": "{{email()}}",
  "payload": "{{string({length: 1024})}}",
  "created_at": "{{date()}}"
}
EOF

# Jalankan simulasi stress konkurensi tinggi
mgeneratejs schema.json -n 100000 | mongoimport --uri="mongodb://127.0.0.1:27017/benchmark" --collection=stress_test --numInsertionWorkers=32
```

---

## 15: Hands-on Lab Mini-Project

### Skenario:
Sistem produksi Anda mengalami lonjakan latensi P99 dari 20ms menjadi 12.000ms. SRE ditugaskan merekonstruksi kejadian di lab, menganalisis status internal cache, lalu menerapkan mitigasi optimasi secara deterministik.

### Tahap 1: Rekonstruksi Masalah (Membuat Query Berat Tanpa Index)
```javascript
// Hubungkan ke mongosh
use benchmark;

// Buat koleksi 500,000 dokumen
const bulk = db.unindexed_orders.initializeUnorderedBulkOp();
for (let i = 0; i < 500000; i++) {
  bulk.insert({
    order_id: i,
    user_id: "user_" + (i % 1000),
    amount: Math.random() * 1000,
    status: (i % 2 === 0) ? "PENDING" : "SETTLED",
    description: "Sample order transaction data payload simulation"
  });
}
bulk.execute();

// Jalankan unindexed pattern query
db.unindexed_orders.find({ user_id: "user_500", status: "PENDING" }).sort({ amount: -1 });
```

### Tahap 2: Mendiagnosis Menggunakan Execution Stats
```javascript
db.unindexed_orders.find({ user_id: "user_500", status: "PENDING" })
  .sort({ amount: -1 })
  .explain("executionStats");
```
*Output Diagnostik:* Mengidentifikasi `stage: "COLLSCAN"` dan `totalDocsExamined: 500000` dengan `executionStages.memUsage` yang tinggi.

### Tahap 3: Mitigasi SRE Indexing Compound
```javascript
// Terapkan teknik Equality-Sort-Range (ESR) Rule
db.unindexed_orders.createIndex(
  { status: 1, user_id: 1, amount: -1 },
  { name: "idx_orders_status_user_amount", background: true }
);

// Verifikasi ulang eksekusi
db.unindexed_orders.find({ user_id: "user_500", status: "PENDING" })
  .sort({ amount: -1 })
  .explain("executionStats");
```
*Hasil:* `stage: "IXSCAN"`, `totalDocsExamined: 250`, latensi kembali ke < 1ms.

---

## 16: Automated Testing & Verification

Gunakan script validasi assertions berikut untuk memverifikasi kesiapan lingkungan host:

```python
# test_sre_readiness.py
import unittest
import os
from pymongo import MongoClient

class TestMongoSREReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)

    def test_thp_disabled(self):
        """Memverifikasi Transparent Huge Pages bernilai 'never'."""
        with open("/sys/kernel/mm/transparent_hugepage/enabled", "r") as f:
            content = f.read()
            self.assertIn("[never]", content, "THP must be set to [never]")

    def test_swappiness_value(self):
        """Memverifikasi kernel swappiness diatur ke 1."""
        with open("/proc/sys/vm/swappiness", "r") as f:
            val = int(f.read().strip())
            self.assertEqual(val, 1, "vm.swappiness must be set to 1")

    def test_mongodb_tickets_healthy(self):
        """Memverifikasi tiket pembacaan/penulisan WiredTiger tidak terdegradasi."""
        status = cls.client.admin.command({"serverStatus": 1})
        wt = status["wiredTiger"]
        read_avail = wt["concurrentTransactions"]["read"]["available"]
        write_avail = wt["concurrentTransactions"]["write"]["available"]
        
        self.assertGreater(read_avail, 50, f"Critical read ticket starvation: {read_avail} remaining")
        self.assertGreater(write_avail, 50, f"Critical write ticket starvation: {write_avail} remaining")

if __name__ == "__main__":
    unittest.main()
```

Jalankan pengujian:
```bash
python3 test_sre_readiness.py
```

---

## 17: Troubleshooting Guide

### 1. Masalah: WiredTiger Ticket Exhaustion (`available: 0`)
* **Gejala:** Latensi melonjak ribuan ms, thread pooling aplikasi membengkak, koneksi `active` mendekati `maxIncomingConnections`.
* **Root Cause:** Long-running unindexed query, CPU saturation, atau disk write throttling.
* **Tindakan Pemulihan:**
  1. Identifikasi OpID query penyebab:
     ```javascript
     db.currentOp({ "secs_running": { $gt: 10 } });
     ```
  2. Kill OpID yang menyebabkan antrean:
     ```javascript
     db.killOp(<opid>);
     ```

### 2. Masalah: Eviction Stalls & Cache Pressure
* **Gejala:** CPU I/O wait melonjak, persentase dirty data `> 20%`.
* **Root Cause:** Throughput disk NVMe/SSD mencapai batas IOPS maksimum (IOPS saturation).
* **Tindakan Pemulihan:**
  1. Aktifkan *dynamic dirty eviction rate override* via mongosh:
     ```javascript
     db.adminCommand({
       setParameter: 1,
       "wiredTigerEngineRuntimeConfig": "eviction_dirty_target=5,eviction_dirty_trigger=15"
     });
     ```

---

## 18: Checklist Produksi

- [ ] **Kernel Tuning:** `vm.swappiness` diatur ke `1`.
- [ ] **THP Management:** Transparent Huge Pages `disabled` (`[never]`).
- [ ] **Disk Optimization:** Mount data path menggunakan filesystem **XFS** dengan opsi `noatime`.
- [ ] **Capacity Limits:** `ulimit -n` (open files) diset $\ge 64000$.
- [ ] **Profiler Strategy:** Profiling mode diatur ke `slowOp` dengan threshold $\le 50\text{ ms}$.
- [ ] **Monitoring Setup:** FTDC data retention dikonfigurasi, alerting metrik tickets WiredTiger aktif di sistem visualisasi (misal: Grafana/Prometheus).
- [ ] **Security Enforcement:** User diagnostik SRE dibatasi menggunakan least privilege role.

---

## 19: Ringkasan Eksekutif

Keandalan tingkat tinggi pada MongoDB menuntut orkestrasi yang presisi antara parameter kernel sistem operasi Linux dan subsistem penyimpanan WiredTiger. Latensi P99 seringkali terdegradasi bukan akibat keterbatasan fungsional MongoDB, melainkan karena *ticket exhaustion*, alokasi memori yang keliru akibat Transparent Huge Pages, atau *eviction stalls* saat dirty cache meluap. 

Dengan menerapkan kernel tuning (`vm.swappiness=1`, disabled THP), mendesain index berdasarkan aturan Equality-Sort-Range (ESR), serta menjalankan pemantauan preventif terhadap ketersediaan tiket dan rasio dirty cache WiredTiger, arsitektur database dapat mempertahankan throughput tinggi, menekan latensi ekstrem, dan mencapai SLA 99.99% ketersediaan pada lingkungan produksi skala besar.

---

## 20: Referensi & Bacaan Lanjutan

1. MongoDB Documentation: *WiredTiger Storage Engine Tuning Reference*. https://www.mongodb.com/docs/manual/core/wiredtiger/
2. MongoDB Technical Papers: *Diagnosing MongoDB Performance with FTDC (Full Time Diagnostic Capture)*.
3. Gregg, Brendan. *Systems Performance: Enterprise and the Cloud, 2nd Edition*. Addison-Wesley, 2020.
4. Linux Kernel Documentation: *Memory Management Subsystem & Transparent Huge Pages (THP)*. https://www.kernel.org/doc/Documentation/vm/transhuge.txt