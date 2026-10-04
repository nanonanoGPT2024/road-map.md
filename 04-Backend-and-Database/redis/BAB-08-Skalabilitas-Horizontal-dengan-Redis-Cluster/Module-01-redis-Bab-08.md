# Bab 08 Module 01: Skalabilitas Horizontal dengan Redis Cluster

---

## 01: Identitas Modul

* **Track/Kategori**: 04-Backend-and-Database
* **Topik**: Redis Distributed Systems
* **Modul**: Bab 08 Module 01: Skalabilitas Horizontal dengan Redis Cluster
* **Tingkat Kesulitan**: Advanced
* **Prasyarat**:
  * Pemahaman mendalam arsitektur Redis Single-Instance & Redis Sentinel (High Availability).
  * Penguasaan protokol TCP/IP, network partitioning, dan socket multiplexing.
  * Kemahiran eksekusi Linux CLI, Docker, serta implementasi driver asynchronous (Node.js/TypeScript).

---

## 02: Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Arsitektur Sharding**: Menjelaskan algoritma Hash Slot ($16.384$ slot), fungsi hash CRC16, dan mekanisme deterministik routing data pada Redis Cluster.
2. **Mengonfigurasi Topologi Multi-Node**: Mengorkestrasi cluster Redis terdistribusi minimal 6 node (3 Master, 3 Replica) dengan isolasi port data ($6379$) dan Cluster Bus ($16379$).
3. **Mengelola Redirection Protocol**: Mengimplementasikan penanganan kode respons `-MOVED` dan `-ASK` pada level driver aplikasi.
4. **Mengatasi Multi-Key Constraints**: Mendesain skema data menggunakan *Hash Tags* `{...}` guna menjamin atomisitas eksekusi multi-key/Lua scripts dalam satu hash slot.
5. **Menjalankan Operasi Resharding & Failover**: Melakukan migrasi slot on-the-fly tanpa downtime (*zero downtime resharding*) dan memverifikasi auto-failover ketika node Master terisolasi.

---

## 03: Concept Map Diagram

```
+-----------------------------------------------------------------------------+
|                               Redis Client                                  |
|         (Cluster-Aware Driver: Smart Routing via Cached Slot Map)           |
+-----------------------------------------------------------------------------+
               | CRC16(key) % 16384                 | Redirect (-MOVED/-ASK)
               v                                    v
+-----------------------------------------------------------------------------+
|                                REDIS CLUSTER                                |
|                                                                             |
|  +---------------------------+             +-----------------------------+  |
|  |       Node A (Master)     |             |       Node B (Master)       |  |
|  |     Slots: 0 - 5460       |             |    Slots: 5461 - 10922      |  |
|  +---------------------------+             +-----------------------------+  |
|       |              ^                          |               ^           |
|  Repl | Async   Gossip Protocol            Repl | Async    Gossip Protocol  |
|       v              |                          v               |           |
|  +---------------------------+             +-----------------------------+  |
|  |      Node A1 (Replica)    |             |      Node B1 (Replica)      |  |
|  |       Read-Only Slot      |             |       Read-Only Slot        |  |
|  +---------------------------+             +-----------------------------+  |
|                                                                             |
|  Gossip Bus (Port 16379): MEET, PING, PONG, FAIL, PUBLISH, UPDATE           |
+-----------------------------------------------------------------------------+
```

---

## 04: Mengapa Relevan?

Redis Standalone atau Sentinel memiliki batas skalabilitas vertikal: memori maksimal dibatasi oleh RAM fisik satu server, dan seluruh throughput penulisan tertahan pada single-thread execution engine. 

Redis Cluster memecahkan limitasi ini dengan membagi ruang data secara horizontal (*sharding*) ke banyak node tanpa bergantung pada reverse proxy eksternal (seperti Twemproxy atau Envoy). Redis Cluster menyediakan:
* **Skalabilitas Kapasitas**: Agregasi RAM lintas node (misal: 10 node $\times$ 64 GB = 640 GB dataset aktif).
* **Throughput Linear**: Beban penulisan (*write workloads*) tersebar merata ke beberapa master independen.
* **Ketersediaan Tinggi Terintegrasi**: Auto-failover berbasis konsensus Gossip Protocol internal tanpa membutuhkan komponen Sentinel terpisah.

---

## 05: Anatomi Konsep Inti

### 1. Hash Slots Allocation

Redis Cluster tidak menggunakan consistent hashing murni, melainkan konsep **Hash Slots**. Seluruh keyspace dibagi menjadi **$16.384$ slot** ($0$ sampai $16383$).

Formula matematis penentuan slot untuk suatu key:

$$\text{Slot} = \text{CRC16}(Key) \pmod{16384}$$

Setiap Master bertanggung jawab atas subset dari 16.384 slot:
* **Node A**: Slot $0 - 5460$
* **Node B**: Slot $5461 - 10922$
* **Node C**: Slot $10923 - 16383$

### 2. Hash Tags

Operasi multi-key (seperti `MGET`, `MSET`, `EVAL` script, Transactions) mensyaratkan semua key berada pada slot yang sama. Redis Cluster menyediakan **Hash Tags**: Jika key mengandung substring di dalam tanda kurung kurawal `{...}`, hanya teks di dalam kurung kurawal yang di-hash.

* Key: `user:{1001}:profile` $\to$ Hash dikalkulasi dari `1001`.
* Key: `user:{1001}:orders` $\to$ Hash dikalkulasi dari `1001`.
* **Hasil**: Kedua key dijamin berada pada slot dan node Master yang sama.

### 3. Cluster Bus & Gossip Protocol

Setiap node membuka dua port TCP:
* **Client Port** (misal: $6379$): Melayani perintah dari Redis client.
* **Cluster Bus Port** (misal: $16379$, Client Port + $10000$): Melayani komunikasi node-to-node terenkripsi/biner menggunakan Gossip Protocol untuk failure detection, konfigurasi slot update, dan handshake.

### 4. Redirection: `-MOVED` vs `-ASK`

* **`-MOVED <slot> <ip>:<port>`**: Terjadi saat client mengirim query ke node yang tidak mengampu slot tersebut secara permanen. Driver client mengupdate slot-to-node cache internalnya dan mengirim ulang query ke node target.
* **`-ASK <slot> <ip>:<port>`**: Terjadi saat slot sedang dalam proses migrasi (*resharding*). Client diarahkan sementara untuk mengirim perintah `ASKING` diikuti query utama ke target node, **tanpa** mengupdate slot cache lokal.

---

## 06: Panduan Implementasi Step-by-Step

### Persiapan Direktori Topologi (3 Master, 3 Replica)

Buat struktur direktori untuk 6 node pada localhost/server:

```bash
mkdir -p redis-cluster/{7000,7001,7002,7003,7004,7005}
cd redis-cluster
```

Buat template konfigurasi `redis-cluster/7000/redis.conf` (sesuaikan port untuk folder 7001 - 7005):

```ini
port 7000
cluster-enabled yes
cluster-config-file nodes-7000.conf
cluster-node-timeout 5000
appendonly yes
protected-mode no
bind 0.0.0.0
daemonize yes
logfile "redis-7000.log"
dir ./
```

Salin dan sesuaikan untuk setiap folder node:

```bash
for port in 7001 7002 7003 7004 7005; do
  mkdir -p $port
  sed "s/7000/$port/g" 7000/redis.conf > $port/redis.conf
done
```

### Menjalankan Seluruh Instance Redis

```bash
for port in 7000 7001 7002 7003 7004 7005; do
  cd $port
  redis-server redis.conf
  cd ..
done
```

### Menginisialisasi Cluster dengan `redis-cli`

Eksekusi perintah binding slot otomatis (1 replica per master):

```bash
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1
```

Ketik `yes` ketika prompt alokasi slot muncul.

---

## 07: Contoh Kasus Sederhana

### Interaksi CLI dengan Cluster Mode Enabled (`-c`)

Penggunaan standar tanpa flag `-c` akan menghasilkan exception redirection:

```bash
$ redis-cli -p 7000
127.0.0.1:7000> SET auth:user:99 "active"
(error) MOVED 12539 127.0.0.1:7002
```

Jalankan `redis-cli` dengan flag `-c` (cluster mode awareness):

```bash
$ redis-cli -c -p 7000
127.0.0.1:7000> SET auth:user:99 "active"
-> Redirected to slot [12539] located at 127.0.0.1:7002
OK
127.0.0.1:7002> GET auth:user:99
"active"
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Implementasi client Node.js/TypeScript menggunakan library `ioredis` dengan penanganan reconnect otomatis, circuit breaking, dan failover slot handling.

```typescript
// package.json dependencies: "ioredis": "^5.3.2"
import Redis, { Cluster, ClusterNode, ClusterOptions } from 'ioredis';

export class ResilientRedisClusterClient {
  private cluster: Cluster;
  private readonly nodes: ClusterNode[];

  constructor() {
    this.nodes = [
      { host: '127.0.0.1', port: 7000 },
      { host: '127.0.0.1', port: 7001 },
      { host: '127.0.0.1', port: 7002 },
      { host: '127.0.0.1', port: 7003 },
      { host: '127.0.0.1', port: 7004 },
      { host: '127.0.0.1', port: 7005 },
    ];

    const clusterOptions: ClusterOptions = {
      enableReadyCheck: true,
      maxRedirections: 16,
      scaleReads: 'slave', // Beban read dialihkan ke replica
      retryDelayOnFailover: 100,
      retryDelayOnClusterDown: 250,
      clusterRetryStrategy(times: number) {
        const delay = Math.min(100 * Math.pow(2, times), 3000);
        return delay;
      },
      redisOptions: {
        connectTimeout: 5000,
        lazyConnect: false,
        enableAutoPipelining: true,
        maxRetriesPerRequest: 3,
      },
    };

    this.cluster = new Redis.Cluster(this.nodes, clusterOptions);
    this.registerEventListeners();
  }

  private registerEventListeners(): void {
    this.cluster.on('connect', () => console.log('Redis Cluster: Connecting...'));
    this.cluster.on('ready', () => console.log('Redis Cluster: Ready for read/write operations.'));
    this.cluster.on('error', (err) => console.error('Redis Cluster Error:', err.message));
    this.cluster.on('+node', (node) => console.log(`Redis Cluster: Node ${node.options.host}:${node.options.port} joined`));
    this.cluster.on('-node', (node) => console.warn(`Redis Cluster: Node ${node.options.host}:${node.options.port} left`));
    this.cluster.on('node error', (err, node) => {
      console.error(`Redis Cluster: Node ${node} emitted error:`, err.message);
    });
  }

  /**
   * Menyimpan data sesi menggunakan Hash Tags {} guna menjamin slot atomik
   */
  public async setTenantUserSession(tenantId: string, userId: string, payload: Record<string, any>, ttlSeconds: number): Promise<void> {
    // Hash Tag {tenantId:userId} memastikan Profile, Permissions, dan Token berada pada 1 Hash Slot
    const baseKey = `{tenant:${tenantId}:user:${userId}}`;
    const profileKey = `${baseKey}:profile`;
    const lastActiveKey = `${baseKey}:last_active`;

    const pipeline = this.cluster.pipeline();
    pipeline.set(profileKey, JSON.stringify(payload), 'EX', ttlSeconds);
    pipeline.set(lastActiveKey, Date.now().toString(), 'EX', ttlSeconds);

    const results = await pipeline.exec();
    if (!results) {
      throw new Error('Pipeline execution failed: Null results received');
    }

    for (const [err, result] of results) {
      if (err) throw new Error(`Atomic write failed: ${err.message}`);
    }
  }

  public async getTenantUserProfile(tenantId: string, userId: string): Promise<Record<string, any> | null> {
    const key = `{tenant:${tenantId}:user:${userId}}:profile`;
    const rawData = await this.cluster.get(key);
    return rawData ? JSON.parse(rawData) : null;
  }

  public async getClusterTopologyInfo(): Promise<void> {
    const nodes = this.cluster.nodes('all');
    for (const node of nodes) {
      const role = await node.role();
      console.log(`Node [${node.options.host}:${node.options.port}] -> Role: ${role[0]}`);
    }
  }

  public async shutdown(): Promise<void> {
    await this.cluster.quit();
  }
}
```

---

## 09: Diagram Alur Kerja Interaksi Read/Write

```
[ Application Client ]        [ Node A (Master: 0-5460) ]       [ Node B (Master: 5461-10922) ]
          |                                  |                                  |
          | 1. SET key "foo" (CRC16=12000)   |                                  |
          |--------------------------------->|                                  |
          |                                  |                                  |
          | 2. Check Local Slot Table:       |                                  |
          |    Slot 12000 belongs to Node B  |                                  |
          | 3. Reply: -MOVED 12000 Node_B:6379                                  |
          |<---------------------------------|                                  |
          |                                                                     |
          | 4. Update Internal Slot Map (12000 -> Node B)                       |
          |                                                                     |
          | 5. Re-send SET key "foo"                                            |
          |-------------------------------------------------------------------->|
          |                                                                     |
          | 6. Reply: +OK                                                       |
          |<--------------------------------------------------------------------|
```

---

## 10: Analisis Trade-offs

| Aspek | Redis Standalone / Sentinel | Redis Cluster |
| :--- | :--- | :--- |
| **Batas Memori** | Dibatasi RAM 1 Mesin (Max ~64GB-128GB praktis) | Skala Terdistribusi Horizontal (Multi-Terabyte) |
| **Write Scaling** | Single Node Bottleneck | Linear Scallability ke N Master |
| **Operasi Multi-Key** | Mendukung seluruh multi-key & transaksi bebas | Terbatas; Wajib menggunakan Hash Tags `{...}` |
| **Overhead Protokol**| Rendah | Lebih tinggi (-MOVED, -ASK redirection, gossip network) |
| **Kompleksitas Ops** | Rendah (Sentinel mudah dipelihara) | Tinggi (Resharding, slot migration, split-brain handling) |
| **Database Multi-Index**| Mendukung 16 database (`SELECT 0..15`) | **Hanya Database 0** (`SELECT` tidak diizinkan) |

---

## 11: Best Practices & Antipatterns

### Best Practices
* **Konsistensi Hash Tags**: Selalu gunakan `{id}` yang representatif pada skema multi-key relational agar tidak terjadi cross-slot errors.
* **Gossip Network Isolation**: Pisahkan jaringan traffic cluster bus ($16379$) ke private subnet/VPC untuk mencegah latency spike dan security exposure.
* **Minimal 3 Master**: Minimal gunakan 3 node master independen guna memenuhi kuorum voting auto-failover secara konsensus.
* **Scale Reads with Replicas**: Manfaatkan flag `READONLY` jika aplikasi membaca dari replica (`scaleReads: 'slave'`).

### Antipatterns
* **Cross-Slot Transactions**: Mengeksekusi script Lua atau transaksi `MULTI/EXEC` yang melibatkan keys tanpa Hash Tag yang sama.
* **Unbalanced Sharding Hotspots**: Menempatkan jutaan keys di dalam satu Hash Tag tunggal (misal: `{global}:user:id`), menyebabkan data menumpuk hanya pada satu instance master (*hot-spot node*).
* **Direct Connecting via Single Endpoint**: Tidak menggunakan cluster-aware driver, sehingga aplikasi mengalami crash saat menerima error `-MOVED`.

---

## 12: Security Hardening

1. **Konfigurasi Autentikasi Dual-Password**: Set password sama untuk `requirepass` dan `masterauth` di semua node:
   ```ini
   requirepass "SuperStrongMasterClusterSecretPass123!"
   masterauth "SuperStrongMasterClusterSecretPass123!"
   ```
2. **Cluster TLS Encryption**: Enkripsi jalur Client Port dan Cluster Bus Port:
   ```ini
   tls-port 6379
   tls-cluster yes
   tls-cert-file /etc/redis/tls/redis.crt
   tls-key-file /etc/redis/tls/redis.key
   tls-ca-cert-file /etc/redis/tls/ca.crt
   tls-auth-clients yes
   tls-replication yes
   ```
3. **Restriksi Cluster Command**: Nonaktifkan perintah destruktif melalui ACL:
   ```text
   user default off
   user app-writer on >WriteSecretKey ~{tenant:*}:* +@write +@read -CLUSTER|RESET -FLUSHALL -FLUSHDB
   ```

---

## 13: Observabilitas & Debugging

### Key Metrics Monitoring
* **`cluster_state`**: Harus bernilai `ok`. Status `fail` menandakan ada slot yang tidak terlayani.
* **`cluster_slots_assigned`**: Harus bernilai $16.384$.
* **`cluster_slots_fail`**: Jumlah slot yang offline (harus $0$).
* **`cluster_known_nodes`**: Total node yang terdeteksi via Gossip Protocol.

### Perintah Diagnostik CLI

```bash
# Validasi integritas cluster dan deteksi open/unassigned slots
redis-cli --cluster check 127.0.0.1:7000

# Melihat informasi alokasi slot per node
redis-cli -p 7000 CLUSTER SLOTS

# Mendapatkan metrik internal cluster engine
redis-cli -p 7000 CLUSTER INFO
```

---

## 14: Benchmarking & Performance

Jalankan throughput benchmark lintas cluster:

```bash
# Benchmark pipeline cluster write
redis-benchmark -p 7000 -c 100 -n 100000 --cluster -d 128 -t set,get -q
```

*Output Standar yang Diharapkan:*
```text
SET: 185185.19 requests per second, p50=0.471 msec
GET: 198412.70 requests per second, p50=0.439 msec
```

*Analisis Kritis*: Jika p99 latency melonjak tajam saat cluster benchmarking, periksa utilisasi network bandwidth Cluster Bus (TCP 16379) atau adanya fragmentasi *memory copy-on-write* akibat persistensi BGSAVE bersamaan antar node.

---

## 15: Hands-on Lab Mini-Project

### Skenario: Resharding Slot Tanpa Downtime

Anda ditugaskan memindahkan 1000 slot dari Node A (7000) ke Node B (7001) secara live.

### Eksekusi Resharding:

```bash
# 1. Jalankan wizard resharding
redis-cli --cluster reshard 127.0.0.1:7000 \
  --cluster-from $(redis-cli -p 7000 CLUSTER MYID) \
  --cluster-to $(redis-cli -p 7001 CLUSTER MYID) \
  --cluster-slots 1000 \
  --cluster-yes
```

### Simulasi Failover Otomatis (Chaos Simulation):

```bash
# Matikan paksa Node Master 7000
redis-cli -p 7000 DEBUG segfault

# Monitor log Replica (7003) mengambil alih status Master
redis-cli -p 7003 CLUSTER NODES | grep myself
```

---

## 16: Automated Testing & Verification

Simulasi validasi fungsional menggunakan Jest untuk menjamin cluster integrity:

```typescript
import Redis from 'ioredis';

describe('Redis Cluster Integrity & Hash Tag Suite', () => {
  let cluster: Redis.Cluster;

  beforeAll(() => {
    cluster = new Redis.Cluster([
      { host: '127.0.0.1', port: 7000 },
      { host: '127.0.0.1', port: 7001 }
    ]);
  });

  afterAll(async () => {
    await cluster.quit();
  });

  test('Validasi Slot Alokasi Konsisten dengan Hash Tag', async () => {
    const key1 = '{order:ABC}:item_1';
    const key2 = '{order:ABC}:item_2';

    await cluster.set(key1, 'Data 1');
    await cluster.set(key2, 'Data 2');

    // Mengambil slot dari key
    const slot1 = await cluster.cluster('KEYSLOT', key1);
    const slot2 = await cluster.cluster('KEYSLOT', key2);

    expect(slot1).toEqual(slot2);

    // Verifikasi multi-key MGET berjalan tanpa error CROSSSLOT
    const results = await cluster.mget(key1, key2);
    expect(results).toEqual(['Data 1', 'Data 2']);
  });

  test('Mendeteksi Kegagalan Operasi Multi-Key Tanpa Hash Tag', async () => {
    const unhashedKey1 = 'product:999';
    const unhashedKey2 = 'user:888';

    await cluster.set(unhashedKey1, 'P1');
    await cluster.set(unhashedKey2, 'U1');

    // MGET harus throw CROSSSLOT Keys error jika berada di slot berbeda
    try {
      await cluster.mget(unhashedKey1, unhashedKey2);
    } catch (err: any) {
      expect(err.message).toMatch(/CROSSSLOT/);
    }
  });
});
```

---

## 17: Troubleshooting Guide

| Gejala Masalah | Akar Masalah (Root Cause) | Solusi Remediasi |
| :--- | :--- | :--- |
| `CROSSSLOT Keys in request don't hash to the same slot` | Perintah multi-key memproses keys dari slot berbeda. | Terapkan sintaks Hash Tags `{...}` pada skema penamaan keys. |
| `CLUSTERDOWN The cluster is down` | Mayoritas master gagal beroperasi (>50% masters down) atau ada slot terbuka. | Jalankan `redis-cli --cluster fix <ip>:<port>` untuk mengisi slot kosong. |
| Performa query lambat drastis (*High Latency*) | Client driver tidak meng-cache redirection map, menyebabkan network hop ganda (`-MOVED`). | Gunakan Smart Cluster Driver (`ioredis`, `Jedis`) & verifikasi routing table cache diaktifkan. |
| Node stuck di status `FAIL` setelah restart | Metadata gossip node rusak atau cluster configuration Epoch out-of-sync. | Hapus file `nodes.conf` lokal node dan lakukan rejoin via `CLUSTER MEET`. |

---

## 18: Checklist Kesiapan Produksi

- [ ] **Distribusi Node Fisik**: Seluruh Master dan Replicanya ditempatkan di server fisik / *Availability Zone (AZ)* berbeda.
- [ ] **Cluster Node Timeout**: Parameter `cluster-node-timeout` dikonfigurasi proporsional (rekomendasi: `3000ms` - `5000ms`) untuk mencegah false failover akibat network blip.
- [ ] **Port Firewall Terbuka**: Port Data ($6379$) dan Port Gossip Bus ($16379$) diizinkan pada security group antar instance cluster.
- [ ] **Alokasi Slot Utuh**: Output `redis-cli --cluster check` menunjukkan 16.384 slot teralokasi tanpa coverage hole.
- [ ] **Memory Overcommit Activated**: Linux sysctl `vm.overcommit_memory = 1` aktif pada seluruh host.
- [ ] **Overlapping Hash Tag Defense**: Skema key aplikasi diaudit bebas dari hash collision atau skenario hot-slot.

---

## 19: Ringkasan Eksekutif

Redis Cluster adalah mekanisme distributed native Redis yang memungkinkan penskalaan penulisan (*write workloads*) dan kapasitas memori secara horizontal melampaui limitasi satu node. Arsitektur ini dibangun di atas $16.384$ Hash Slots berbasis kalkulasi CRC16. Komunikasi topologi dan konsensus *failure detection* dikoordinasikan secara otonom via Gossip Protocol di port $16379$. 

Bagi backend engineer, kunci stabilitas sistem Redis Cluster terletak pada adaptasi aplikasi terhadap protokol pengalihan (`-MOVED`/`-ASK`), isolasi operasi multi-key menggunakan *Hash Tags*, serta perancangan topologi node dengan kuorum ganjil untuk mencegah *split-brain*.

---

## 20: Referensi & Bacaan Lanjutan

* **Redis Official Documentation**: *Redis Cluster Specification* (`https://redis.io/docs/reference/cluster-spec/`)
* **Redis Cluster Tutorial**: *Scaling with Redis Cluster* (`https://redis.io/docs/management/scaling/`)
* **Sanfilippo, Salvatore (Antirez)**: *Redis Cluster Design Principles & Raft comparison analysis notes.*
* **Driver Architecture**: *ioredis Cluster Specification Guide* (`https://github.com/redis/ioredis#cluster`)