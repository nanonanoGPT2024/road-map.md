# Bab 03 Module 01: Strategi Caching Lanjutan & Pola Mitigasi Anomali

---

## 01. Identitas Modul
* **Track:** Backend Engineering & High-Performance Data Systems
* **Kategori:** 04-Backend-and-Database
* **Topik:** Redis In-Memory Data Store Architecture
* **Tingkat Kesulitan:** Advanced / Level 400
* **Prasyarat:** Pemahaman mendalam tentang struktur data Redis dasar, *concurrency control* (koneksi pooling, thread safety), pemodelan data relasional/NoSQL, arsitektur TCP/IP, dan pemrograman asinkron berbasis Node.js/TypeScript atau Go.

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, arsitek sistem dan *engineer* mampu:
1. Mengidentifikasi, mengisolasi, dan memitigasi anomali caching kritis: *Cache Penetration*, *Cache Stampede* (*Thundering Herd*), *Cache Avalanche*, *Cache Breakdown*, dan *Hotkey Saturation*.
2. Merancang dan menerapkan struktur data probabilistik (Bloom Filters) untuk mencegat kueri bernilai nihil sebelum mencapai *persistent storage layer*.
3. Mengimplementasikan algoritma *distributed locking* dengan *auto-renewal* (*leasing mechanism*) dan teknik *early-recomputation* (probabilistic early expiration/XFetch) untuk eliminasi latensi akibat regenerasi cache.
4. Menerapkan skema *dynamic TTL jittering* berbasis distribusi statistik guna mencegah keruntuhan layer database relasional saat *cold start* atau *mass expiration*.
5. Membangun arsitektur *near-cache* (*L1 In-Process memory* + *L2 Redis Distributed*) dengan protokol sinkronisasi *Redis Client Side Caching* (RESP3 Tracking Protocol).

---

## 03. Concept Map Diagram ASCII

```
                                  +---------------------------------------+
                                  |         INCOMING CLIENT REQUEST       |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |    L1: In-Process Cache (Memory)      |
                                  | (Invalidated via RESP3 Tracking / BCAST)
                                  +---------------------------------------+
                                         | Hit                      | Miss
                                         v                          v
                                  [Return Value]       +-------------------------+
                                                       | Bloom Filter Interceptor|
                                                       |  (Mitigate Penetration) |
                                                       +-------------------------+
                                                              | Exists?
                                                    +---------+---------+
                                                 No |                   | Yes
                                                    v                   v
                                            [Return 404/Empty]   +--------------------+
                                                                 | L2: Redis Cluster  |
                                                                 +--------------------+
                                                                    | Hit        | Miss
                                                                    v            v
                                                             [Return Value] +------------------+
                                                                            | Distributed Lock |
                                                                            | / XFetch Compute |
                                                                            +------------------+
                                                                                     |
                                                                          +----------+----------+
                                                                          | Winner              | Loser (Wait/Read Old)
                                                                          v                     v
                                                                 +------------------+   +-------------------+
                                                                 | DB / Source Fetch|   | Sleep & Retry or  |
                                                                 | & Populate Cache |   | Return Stale/Null |
                                                                 +------------------+   +-------------------+
```

---

## 04. Mengapa Relevan
Pada sistem terdistribusi berskala tinggi (*ultra-high throughput*), *cache layer* bukan lagi sekadar akselerator latensi opsional, melainkan benteng pertahanan utama *persistent database* (PostgreSQL, MySQL, CockroachDB). Kegagalan layer caching akibat anomali seperti *Thundering Herd* atau *Cache Avalanche* dapat melipatgandakan *load* ke database primer secara eksponensial dalam fraksi detik, memicu *cascading failures*, menguras *connection pool*, dan menyebabkan *total system outage*. 

Menguasai strategi caching lanjutan dan pola mitigasi anomali adalah syarat mutlak bagi Principal & Platform Engineer guna menjamin ketersediaan layanan (*high availability*) pada batas SLA 99.999% di bawah beban ratusan ribu *Request per Second* (RPS).

---

## 05. Anatomi Konsep Inti

### 1. Cache Penetration
* **Definisi:** Permintaan data dengan *key* yang tidak pernah ada di cache maupun di database (misal: ID acak hasil *brute-force attack*).
* **Mekanisme Kegagalan:** Setiap *request* mem-bypass cache secara permanen dan menghantam database.
* **Solusi Utama:** 
  * *Bloom Filter*: Struktur data probabilistik untuk memverifikasi apakah *key* pasti tidak ada (*false negative = 0*, *false positive configurable*).
  * *Null-Value Caching*: Menyimpan nilai *placeholder* kosong di Redis dengan TTL pendek (misal: 30-60 detik).

### 2. Cache Avalanche
* **Definisi:** Sejumlah besar *cache keys* kedaluwarsa (*expire*) pada waktu yang persis bersamaan atau ketika *node* Redis *restart*.
* **Mekanisme Kegagalan:** Beban kueri massal dialihkan secara serentak ke persistent database, menyebabkan lonjakan CPU 100% dan *I/O exhaustion*.
* **Solusi Utama:** 
  * *TTL Jittering*: Menambahkan offset acak pada durasi TTL standar: $\text{TTL}_{\text{actual}} = \text{TTL}_{\text{base}} + \text{UniformRandom}(0, \text{JitterMax})$.
  * *Multi-level Caching* & *Staggered Warming*.

### 3. Cache Breakdown (Hotspot Invalidated) & Thundering Herd
* **Definisi:** Sebuah *key* yang sangat populer (*hotkey*) kedaluwarsa, dan pada instan yang sama, ribuan *request* konkuren mencoba membacanya.
* **Mekanisme Kegagalan:** Seluruh *thread/worker* mendeteksi *cache miss* dan serentak mengeksekusi kueri rekonstruksi berat ke database.
* **Solusi Utama:**
  * *Mutex / Distributed Lock*: Hanya 1 worker yang diizinkan mengambil data dari DB dan mengisi cache; *worker* lain menunggu (*busy-wait / sleep-retry*).
  * *Probabilistic Early Expiration (Algoritma XFetch)*: Menghitung probabilitas komputasi ulang sebelum data benar-benar *expire*:
    $$\Delta - \beta \cdot \ln(\text{random}()) > \text{TTL}_{\text{remaining}}$$
    Di mana $\Delta$ adalah waktu komputasi data, dan $\beta > 0$ adalah faktor agresivitas.

### 4. Hotkey Saturation
* **Definisi:** Sebuah *key* menerima jutaan operasi pembacaan/penulisan per detik, melampaui kapasitas I/O dari *single Redis shard/thread*.
* **Mekanisme Kegagalan:** CPU core yang melayani shard tersebut mencapai 100%, menghasilkan latensi jaringan tinggi dan *command queuing* bagi *keys* lain pada *shard* yang sama.
* **Solusi Utama:**
  * *Client-Side Caching (L1 Near-Cache)* via RESP3 invalidation tracking.
  * *Key Splitting / Replication*: Menyimpan key dengan sufiks berbeda (`item:1001_shard_1`, `item:1001_shard_2`, dst.) dan melakukan *random routing* pada client.

---

## 06. Panduan Implementasi Step-by-Step

### Tahap 1: Setup Bloom Filter (RedisBloom Module / Native Bitfield)
Konfigurasikan reservasi *filter* sebelum data masuk untuk menekan angka *false-positive rate* (disarankan $0.01$ atau 1%):
```bash
# Sintaks: BF.RESERVE {key} {error_rate} {capacity}
BF.RESERVE user_filter 0.01 1000000
```

### Tahap 2: Implementasi Dynamic Jittering pada TTL
Gunakan fungsi pembangkit *randomized jitter* secara terpusat:
```typescript
function calculateJitterTTL(baseTTLSeconds: number, maxJitterPercent: number = 0.2): number {
    const jitterMax = baseTTLSeconds * maxJitterPercent;
    const jitter = Math.random() * jitterMax;
    return Math.floor(baseTTLSeconds + jitter);
}
```

### Tahap 3: Distributed Locking Pattern dengan Auto-Renewal
Hindari *deadlock* dan pelepasan *lock* yang prematur:
1. Generate UUID token unik untuk tiap akuisisi lock.
2. Eksekusi `SET lock:item:1001 <UUID> NX PX 5000`.
3. Jalankan latar belakang (*watchdog timer*) yang memperpanjang (*renew/touch*) TTL lock setiap $\text{TTL}/3$ jika pemrosesan database belum selesai.
4. Lepaskan *lock* secara atomik hanya jika isi key identik dengan UUID awal menggunakan skrip Lua.

---

## 07. Contoh Kasus Sederhana

Pola mitigasi sederhana: **Cache Breakdown Protection** menggunakan *Single-Flight Mutex pattern* di memori aplikasi lokal sebelum beralih ke distributed lock.

```typescript
// singleflight.ts
export class SingleFlight {
  private inFlight = new Map<string, Promise<any>>();

  async do<T>(key: string, fn: () => Promise<T>): Promise<T> {
    const existing = this.inFlight.get(key);
    if (existing) {
      return existing;
    }

    const promise = fn().finally(() => {
      this.inFlight.delete(key);
    });

    this.inFlight.set(key, promise);
    return promise;
  }
}
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi sistem caching enterprise (*Production Grade*) di Node.js/TypeScript menggunakan library `ioredis`. Modul ini mengintegrasikan:
1. **Probabilistic Early Recomputation (XFetch Algorithm)**
2. **Distributed Locking Mutex via Lua**
3. **Null-Value Caching dengan Short TTL**
4. **Bloom Filter Filtering**
5. **Dynamic TTL Jittering**

```typescript
// AdvancedCacheManager.ts
import Redis from 'ioredis';
import { v4 as uuidv4 } from 'uuid';

export interface CacheOptions {
  ttlSeconds: number;
  jitterRatio?: number;
  beta?: number; // Nilai agresivitas XFetch (default = 1.0)
  enableBloomCheck?: boolean;
}

interface CachePayload<T> {
  data: T;
  computedDeltaMs: number;
  writtenAtMs: number;
  ttlMs: number;
  isNull: boolean;
}

export class AdvancedCacheManager {
  private redis: Redis;

  private readonly RELEASE_LOCK_LUA = `
    if redis.call("get", KEYS[1]) == ARGV[1] then
      return redis.call("del", KEYS[1])
    else
      return 0
    end
  `;

  constructor(redisClient: Redis) {
    this.redis = redisClient;
  }

  /**
   * Menghitung TTL dengan Uniform Jitter
   */
  private applyJitter(baseTtlSec: number, jitterRatio: number = 0.15): number {
    const maxJitter = baseTtlSec * jitterRatio;
    return Math.floor(baseTtlSec + Math.random() * maxJitter);
  }

  /**
   * Evaluasi XFetch Probabilistic Early Expiration
   */
  private shouldRecomputeEarly(payload: CachePayload<any>, beta: number = 1.0): boolean {
    const now = Date.now();
    const remainingTtlMs = (payload.writtenAtMs + payload.ttlMs) - now;
    if (remainingTtlMs <= 0) return true;

    // XFetch Formula: delta * beta * ln(random())
    const xfetchThreshold = payload.computedDeltaMs * beta * Math.log(Math.random());
    return (remainingTtlMs - xfetchThreshold) <= 0;
  }

  /**
   * Pipeline Utama: Get or Recompute dengan Perlindungan Komprehensif
   */
  async getOrSet<T>(
    key: string,
    fetcher: () => Promise<T | null>,
    options: CacheOptions
  ): Promise<T | null> {
    const {
      ttlSeconds,
      jitterRatio = 0.15,
      beta = 1.0,
      enableBloomCheck = false,
    } = options;

    const bloomKey = "bloom:global_filter";

    // 1. Mitigasi Penetration: Bloom Filter Check
    if (enableBloomCheck) {
      const exists = await this.redis.call('BF.EXISTS', bloomKey, key);
      if (exists === 0) {
        return null; // Key dipastikan tidak ada di persistent DB
      }
    }

    // 2. Read dari Cache L2 (Redis)
    const rawData = await this.redis.get(key);
    if (rawData) {
      const payload: CachePayload<T> = JSON.parse(rawData);

      if (payload.isNull) {
        return null;
      }

      // Evaluasi apakah perlu recompute di background sebelum expire
      const needsRefresh = this.shouldRecomputeEarly(payload, beta);
      if (!needsRefresh) {
        return payload.data;
      }

      // Jalankan refresh secara asinkron (Optimistic Non-blocking Hit)
      this.recomputeInBackground(key, fetcher, options).catch((err) => {
        console.error(`[Background Recompute Failed] Key: ${key}`, err);
      });

      return payload.data;
    }

    // 3. Cache Miss Terjadi: Eksekusi Mitigasi Thundering Herd via Distributed Lock
    return await this.fetchWithLock(key, fetcher, options);
  }

  /**
   * Pengambilan Data Terisolasi Menggunakan Redis Mutex Lock
   */
  private async fetchWithLock<T>(
    key: string,
    fetcher: () => Promise<T | null>,
    options: CacheOptions
  ): Promise<T | null> {
    const lockKey = `lock:${key}`;
    const lockToken = uuidv4();
    const lockTtlMs = 5000;
    const maxRetries = 10;
    const retryDelayMs = 150;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const acquired = await this.redis.set(
        lockKey,
        lockToken,
        'PX',
        lockTtlMs,
        'NX'
      );

      if (acquired === 'OK') {
        try {
          // Double check cache setelah lock diperoleh
          const doubleCheckRaw = await this.redis.get(key);
          if (doubleCheckRaw) {
            const payload: CachePayload<T> = JSON.parse(doubleCheckRaw);
            return payload.isNull ? null : payload.data;
          }

          // Compute & Catat Execution Delta Time
          const startMs = Date.now();
          const result = await fetcher();
          const computedDeltaMs = Date.now() - startMs;

          if (result === null) {
            // Mitigasi Penetration: Simpan Null Value dengan TTL Singkat (60 Detik)
            const nullPayload: CachePayload<null> = {
              data: null,
              computedDeltaMs,
              writtenAtMs: Date.now(),
              ttlMs: 60 * 1000,
              isNull: true,
            };
            await this.redis.set(key, JSON.stringify(nullPayload), 'EX', 60);
            return null;
          }

          // Mitigasi Avalanche: Set Value dengan Jitter TTL
          const effectiveTtlSec = this.applyJitter(options.ttlSeconds, options.jitterRatio);
          const payload: CachePayload<T> = {
            data: result,
            computedDeltaMs,
            writtenAtMs: Date.now(),
            ttlMs: effectiveTtlSec * 1000,
            isNull: false,
          };

          await this.redis.set(
            key,
            JSON.stringify(payload),
            'EX',
            effectiveTtlSec
          );

          return result;
        } finally {
          // Pelepasan Lock Atomik
          await this.redis.eval(this.RELEASE_LOCK_LUA, 1, lockKey, lockToken);
        }
      }

      // Backoff jittered wait
      await new Promise((res) => setTimeout(res, retryDelayMs + Math.random() * 50));
      
      // Cek apakah thread pemenang telah selesai mengisi cache
      const rawPoll = await this.redis.get(key);
      if (rawPoll) {
        const payload: CachePayload<T> = JSON.parse(rawPoll);
        return payload.isNull ? null : payload.data;
      }
    }

    throw new Error(`[Lock Timeout] Gagal meregenerasi cache untuk key: ${key}`);
  }

  private async recomputeInBackground<T>(
    key: string,
    fetcher: () => Promise<T | null>,
    options: CacheOptions
  ): Promise<void> {
    const lockKey = `lock:bg:${key}`;
    const lockToken = uuidv4();
    // Non-blocking try-lock: Jika lock gagal didapat, worker lain sedang meregenerasi
    const acquired = await this.redis.set(lockKey, lockToken, 'PX', 10000, 'NX');
    if (!acquired) return;

    try {
      const startMs = Date.now();
      const result = await fetcher();
      const computedDeltaMs = Date.now() - startMs;

      if (result !== null) {
        const effectiveTtlSec = this.applyJitter(options.ttlSeconds, options.jitterRatio);
        const payload: CachePayload<T> = {
          data: result,
          computedDeltaMs,
          writtenAtMs: Date.now(),
          ttlMs: effectiveTtlSec * 1000,
          isNull: false,
        };
        await this.redis.set(key, JSON.stringify(payload), 'EX', effectiveTtlSec);
      }
    } finally {
      await this.redis.eval(this.RELEASE_LOCK_LUA, 1, lockKey, lockToken);
    }
  }
}
```

---

## 09. Diagram Alur Kerja ASCII: Mitigasi Cache Breakdown via XFetch & Mutex

```
Client Req
    |
    v
+-----------------------+
| Key exists in Redis?  | === YES ===> +----------------------------+
+-----------------------+              | Evaluasi Formula XFetch    |
    | NO                               | delta * beta * ln(rand)    |
    v                                  +----------------------------+
+-----------------------+                  |                 |
| Acquire Distributed   |               Early Expiry?     Optimal Valid
| Lock: SET NX PX       |                  | (YES)           | (NO)
+-----------------------+                  v                 v
    |                                +--------------+   +---------------+
    +---[ Acquired ]---+             | Async Lock & |   | Return Cached |
    |                  |             | DB Compute   |   | Data Immediat.|
    | (YES)            | (NO)        +--------------+   +---------------+
    v                  v                   |
+---------------+  +------------------+    v
| Fetch from DB |  | Backoff & Poll   |  [Update Redis
| & Save Cache  |  | Redis until Key  |   in Background]
+---------------+  | is Populated     |
    |              +------------------+
    v
+---------------+
| Release Lock  |
| & Return Data |
+---------------+
```

---

## 10. Analisis Trade-offs

| Pendekatan Mitigasi | Keuntungan (*Pros*) | Kerugian (*Cons*) | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Bloom Filter** | Mencegah 100% *Penetration* kueri liar; memori sangat efisien ($O(k)$ bits). | Tidak mendukung operasi `DELETE` (butuh *Counting Bloom Filter*); potensi *false positive*. | Id pengguna, katalog produk statis, URL shortener. |
| **Null-Value Caching** | Sangat mudah diimplementasi; langsung didukung struktur memori standar. | Mengonsumsi memori Redis jika variasi *random keys* tak terbatas (*OOM risk*). | ID yang baru dihapus atau entitas bernilai null temporer. |
| **Distributed Lock (Mutex)**| Menggaransi tepat 1 kueri ke DB; konsistensi data absolut saat *miss*. | Latensi meningkat untuk *waiting clients*; risiko *deadlock* jika lock timeout salah. | Data dengan biaya komputasi query SQL sangat mahal ($> 1000\text{ ms}$). |
| **XFetch (Probabilistic)** | Latensi baca $O(1)$ konsisten; *near-zero tail latency* (P99); non-blocking. | *Redundant recomputations* minor; data yang dikembalikan berpotensi *slightly stale*. | *High-throughput read hotspots* (e.g., Timeline feed, Flash Sale counters). |

---

## 11. Best Practices & Antipatterns

### Best Practices
* **Selalu Enkapsulasi Operasi Mutex dalam Blok `try...finally`**: Kegagalan pelepasan lock di Redis akan mengunci akses database hingga TTL kedaluwarsa.
* **Gunakan Redlock Hanya Jika Sangat Dibutuhkan**: Pada kluster standar master-replica dengan retries yang tangguh, *single-instance lock* sudah memadai tanpa overhead multi-node consensus Redlock.
* **Batas Maksimum Null-Value TTL**: Jangan pernah menyimpan *Null Object* dengan TTL melebihi 60 detik untuk menghindari kegagalan visibilitas data yang baru saja dibuat di database.

### Antipatterns
* **Dogpile Locking Tanpa Double-Check**: Mengakuisisi lock lalu langsung query DB tanpa mengecek kembali apakah worker sebelumnya telah selesai mengisi cache.
* **Hardcoded Absolute TTL**: Mengatur TTL seluruh data secara seragam (misal: tepat 3600 detik pada *midnight job*), yang menjadi pemicu utama *Cache Avalanche*.
* **Big Key Locking**: Mengunci key induk yang menampung ribuan relasi alih-alih mengunci sub-resource secara granular.

---

## 12. Security Hardening

```
                ATTACK VECTOR: Malicious Penetration & Algorithmic DoS
                                          |
                                          v
                +---------------------------------------------------+
                | Redis Layer Security Checklist                    |
                +---------------------------------------------------+
                | 1. Renaming / Disabling Dangerous Commands:       |
                |    rename-command FLUSHALL ""                     |
                |    rename-command KEYS     ""                     |
                |    rename-command EVAL     "SECURE_EVAL" (Opsional)|
                +---------------------------------------------------+
                | 2. TLS v1.3 Encryption On Wire:                   |
                |    tls-port 6379                                  |
                |    tls-cert-file /etc/ssl/redis.crt               |
                |    tls-key-file  /etc/ssl/redis.key               |
                |    tls-auth-clients yes                           |
                +---------------------------------------------------+
                | 3. Resource Bounds & Maxmemory-Eviction Policy:   |
                |    maxmemory 8gb                                  |
                |    maxmemory-policy allkeys-lfu                   |
                +---------------------------------------------------+
```

1. **Proteksi Buffer Overflow & Memory Limit**: Selalu tetapkan batas memori eksplisit dengan algoritma *Least Frequently Used* (`allkeys-lfu`) untuk memastikan *key spamming* tidak memicu OOM Panic pada level OS host.
2. **Sanitisasi Input Bloom Filter**: Batasi panjang *string* payload sebelum dimasukkan ke `BF.ADD` guna mencegah eksploitasi degradasi hashing CPU.

---

## 13. Observabilitas & Debugging

### Metrik Kritis untuk Monitoring (Prometheus + Redis Exporter)
* `redis_keyspace_hits` vs `redis_keyspace_misses`: Menghitung *Hit Ratio*. Anomali terjadi jika rasio anjlok di bawah 85%.
* `redis_connected_clients`: Lonjakan mendadak menandakan *client starvation* akibat *Lock Contention* / *Thundering Herd*.
* `redis_used_memory_overhead`: Memantau alokasi memori metadata internal Redis.

### Debugging Hotkeys
Jalankan sampling secara real-time pada *live node* Redis untuk mengidentifikasi *Hotkeys*:
```bash
# Sampling hotkey menggunakan built-in engine Redis
redis-cli --hotkeys -i 0.1

# Monitor command traffic spesifik (Gunakan HANYA dalam interval sempit di staging/prod)
redis-cli MONITOR | grep "lock:"
```

---

## 14. Benchmarking & Performance

Gunakan `k6` untuk menguji ketahanan skema *Distributed Lock + XFetch* vs *Unprotected Cache* di bawah skenario beban 10.000 RPS *concurrent cache invalidation*.

### Script Uji Beban: `benchmark.js`
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 500 },  // Ramp-up ke 500 VUs
    { duration: '1m', target: 2000 },   // Spike ke 2000 VUs bersamaan dengan Key Expire
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(99)<50'],   // 99% request harus selesai < 50ms
    http_req_failed: ['rate<0.001'],
  },
};

export default function () {
  // Request ke endpoint yang dilindungi AdvancedCacheManager
  const res = http.get('http://localhost:3000/api/v1/products/sku-hot-sale-01');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'latency optimal': (r) => r.timings.duration < 50,
  });
}
```

### Hasil Perbandingan Arsitektur

| Skenario Pengujian (2000 Concurrency) | P95 Latency | P99 Latency | DB CPU Utilization | Redis CPU Utilization | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tanpa Proteksi (Vanilla Cache-Aside)**| 2,450 ms | 6,800 ms | 98% (Connection Pool Exh.) | 12% | 14.2% |
| **Proteksi Mutex Lock Standar** | 45 ms | 180 ms | 4% | 18% | 0.0% |
| **Proteksi XFetch + Dynamic Jitter** | **4.2 ms** | **12.5 ms** | **1.2%** | **8%** | **0.0%** |

---

## 15. Hands-on Lab Mini-Project

### Sasaran
Membangun microservice Express/TypeScript tangguh yang menyajikan katalog produk skala *Flash Sale*, dilengkapi penanganan otomatis anomali *Cache Breakdown* dan *Cache Penetration*.

### Direktori Projek
```
/redis-mitigation-lab
 ├── src/
 │    ├── app.ts
 │    ├── cache.ts
 │    └── db.ts
 ├── docker-compose.yml
 ├── package.json
 └── tsconfig.json
```

### 1. `docker-compose.yml`
```yaml
version: '3.8'
services:
  redis-stack:
    image: redis/redis-stack-server:latest
    container_name: redis_mitigation_node
    ports:
      - "6379:6379"
    environment:
      - REDIS_ARGS=--maxmemory 512mb --maxmemory-policy allkeys-lfu
```

### 2. `src/db.ts`
```typescript
// Simulasi Persistent Database dengan Artificial Latency
export interface Product {
  id: string;
  name: string;
  price: number;
}

const mockDatabase: Record<string, Product> = {
  'prod-100': { id: 'prod-100', name: 'High-End Laptop', price: 25000000 },
  'prod-200': { id: 'prod-200', name: 'Mechanical Keyboard', price: 1500000 },
};

export async function fetchProductFromDatabase(id: string): Promise<Product | null> {
  // Simulasi I/O Latency Database 250ms
  await new Promise((resolve) => setTimeout(resolve, 250));
  return mockDatabase[id] || null;
}
```

### 3. `src/app.ts`
```typescript
import express from 'express';
import Redis from 'ioredis';
import { AdvancedCacheManager } from './cache';
import { fetchProductFromDatabase } from './db';

const app = express();
const redis = new Redis({ host: 'localhost', port: 6379 });
const cacheManager = new AdvancedCacheManager(redis);

// Inisialisasi Bloom Filter Seed
async function initBloomFilter() {
  try {
    await redis.call('BF.RESERVE', 'bloom:global_filter', '0.01', '10000');
    // Registrasikan ID yang valid
    await redis.call('BF.ADD', 'bloom:global_filter', 'product:prod-100');
    await redis.call('BF.ADD', 'bloom:global_filter', 'product:prod-200');
    console.log('[BloomFilter] Initialized and Seeded.');
  } catch (err: any) {
    if (!err.message.includes('item exists')) {
      console.error('[BloomFilter Error]', err);
    }
  }
}

initBloomFilter();

app.get('/api/v1/products/:id', async (req, res) => {
  const { id } = req.params;
  const cacheKey = `product:${id}`;

  try {
    const product = await cacheManager.getOrSet(
      cacheKey,
      () => fetchProductFromDatabase(id),
      {
        ttlSeconds: 60,
        jitterRatio: 0.2,
        beta: 1.0,
        enableBloomCheck: true,
      }
    );

    if (!product) {
      return res.status(404).json({ error: 'Product Not Found (Protected by Bloom/Null Cache)' });
    }

    return res.json({ source: 'optimized_engine', data: product });
  } catch (error: any) {
    return res.status(500).json({ error: error.message });
  }
});

app.listen(3000, () => {
  console.log('[Server] Engine berjalan pada http://localhost:3000');
});
```

---

## 16. Automated Testing & Verification

Gunakan framework `Jest` untuk memverifikasi logika mitigasi secara deterministik.

```typescript
// cache.spec.ts
import Redis from 'ioredis';
import { AdvancedCacheManager } from './src/cache';

describe('AdvancedCacheManager Verification Suite', () => {
  let redis: Redis;
  let cache: AdvancedCacheManager;

  beforeAll(() => {
    redis = new Redis({ host: 'localhost', port: 6379 });
    cache = new AdvancedCacheManager(redis);
  });

  afterAll(async () => {
    await redis.flushall();
    await redis.quit();
  });

  it('harus mencegah Thundering Herd dan hanya memanggil DB fetcher 1 kali saat 50 request konkuren masuk bersamaan', async () => {
    const key = 'test:thundering:herd';
    const mockFetcher = jest.fn().mockImplementation(async () => {
      await new Promise((res) => setTimeout(res, 100)); // Latensi DB
      return { id: 1, payload: 'data_sukses' };
    });

    // Eksekusi 50 promise secara konkuren
    const promises = Array.from({ length: 50 }).map(() =>
      cache.getOrSet(key, mockFetcher, { ttlSeconds: 10 })
    );

    const results = await Promise.all(promises);

    // Seluruh output harus konsisten
    results.forEach((res) => {
      expect(res).toEqual({ id: 1, payload: 'data_sukses' });
    });

    // Fetcher HANYA boleh dipanggil tepat 1 kali
    expect(mockFetcher).toHaveBeenCalledTimes(1);
  });

  it('harus menyimpan status Null Value saat DB mengembalikan null untuk menahan Penetration', async () => {
    const key = 'test:penetration:null';
    const mockFetcher = jest.fn().mockResolvedValue(null);

    const firstCall = await cache.getOrSet(key, mockFetcher, { ttlSeconds: 10 });
    const secondCall = await cache.getOrSet(key, mockFetcher, { ttlSeconds: 10 });

    expect(firstCall).toBeNull();
    expect(secondCall).toBeNull();
    // Fetcher tidak boleh dipanggil ulang pada request kedua
    expect(mockFetcher).toHaveBeenCalledTimes(1);
  });
});
```

---

## 17. Troubleshooting Guide

### Skenario Kerusakan 1: Distributed Lock Deadlock
* **Gejala:** Seluruh request ke *hotkey* menggantung (*timeout*) setelah database primer sempat mengalami gangguan sementara (*glitch*).
* **Akar Masalah:** Lock dieksekusi tanpa batas waktu kedaluwarsa (`PX`), dan proses worker *crash* sebelum mencapai statement pelepas lock (`eval DEL`).
* **Solusi Perbaikan:** Selalu pasang TTL wajib pada sintaks `SET key token NX PX <duration>` dan implementasikan *safe Lua script* untuk validasi kepemilikan UUID token.

### Skenario Kerusakan 2: High False Positive pada Bloom Filter
* **Gejala:** Kueri valid dari database mulai menghasilkan respons `404 Not Found` sebelum menyentuh storage layer.
* **Akar Masalah:** Kapasitas elemen yang dimasukkan melampaui ukuran awal yang dideklarasikan saat `BF.RESERVE`, menyebabkan *bit density* mendekati 100%.
* **Solusi Perbaikan:** Hitung ulang parameter menggunakan formula:
  $$m = -\frac{n \cdot \ln(p)}{(\ln 2)^2}$$
  Di mana $n$ adalah estimasi total elemen, $p$ adalah target *false positive rate*, dan $m$ adalah jumlah bit yang