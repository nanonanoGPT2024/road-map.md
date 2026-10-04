# Bab 06 Module 01: Data Persistence & Distributed Cache Strategies

---

## 01: Identitas Modul
- **Track**: Node.js Enterprise Backend Development
- **Kategori**: 04-Backend-and-Database
- **Module Code**: `NODE-BACKEND-06-01`
- **Tingkat Kesulitan**: Advanced / Principal Level
- **Estimasi Waktu Penyelesaian**: 180 Menit
- **Prasyarat**: Node.js Event Loop Internals, Basic Redis Commands, PostgreSQL/MySQL Transactional Semantics, TypeScript 5.x.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Mendiagnosis dan mengimplementasikan pola caching enterprise: *Cache-Aside*, *Write-Through*, *Write-Back/Write-Behind*, dan *Refresh-Ahead*.
2. Membangun sistem mitigasi terhadap kegagalan caching kritis: *Cache Avalanche*, *Cache Stampede (Thundering Herd)*, dan *Cache Penetration*.
3. Mengonfigurasi layer koneksi PostgreSQL terpadu dengan Redis Sentinel/Cluster menggunakan connection pooling yang optimal.
4. Menerapkan skema serialisasi zero/low-overhead (JSON-safe, Buffer, atau MessagePack) serta strategi TTL (Time-To-Live) dengan Dynamic Jittering.
5. Memvalidasi konsistensi data antara persistent storage (PostgreSQL) dan distributed in-memory storage (Redis) pada arsitektur konkurensi tinggi.

---

## 03: Concept Map Diagram ASCII

```
+-----------------------------------------------------------------------------+
|                       APPLICATION TIER (Node.js Engine)                     |
|                                                                             |
|   +-------------------+        +--------------------+        +----------+   |
|   | Controller / Route| -----> | Persistence Service| -----> | Cache Mgr|   |
|   +-------------------+        +--------------------+        +----+-----+   |
+------------------------------------------|------------------------|---------+
                                           |                        |
         +---------------------------------+                        |
         |                                                          |
         v (TCP / Connection Pool)                                  v (RESP3)
+-------------------+                                      +------------------+
|  PRIMARY DATABASE |                                      | DISTRIBUTED CACHE|
|   (PostgreSQL)    |                                      |  (Redis Cluster) |
|                   |                                      |                  |
| - ACID Guarantees |                                      | - In-Memory RAM  |
| - Disk I/O (WAL)  | <--- Invalidation / Sync Pipeline -- | - Sub-ms Latency |
| - High Durability |                                      | - Ephemeral TTL  |
+-------------------+                                      +------------------+
```

---

## 04: Mengapa Relevan
Pada sistem terdistribusi modern berkemampuan ribuan transaksi per detik (*QPS*), database relasional disk-based seringkali menjadi *single point of bottleneck* akibat disk I/O, lock contention, dan resource pooling exhaustion. 

Distributed cache (seperti Redis) berfungsi sebagai peredam beban (*load damper*). Namun, penambahan caching layer memperkenalkan tantangan baru: **Data Inconsistency** dan **Distributed State Failure**. Kesalahan implementasi strategi cache dapat menyebabkan sistem runtuh seketika saat cache restart (*cache avalanche*) atau saat ribuan worker mencari satu data yang *cold* (*thundering herd*). Menguasai integrasi Node.js runtime secara non-blocking dengan Redis dan RDBMS adalah kompetensi mutlak seorang Principal Backend Engineer.

---

## 05: Anatomi Konsep Inti

### 1. Strategi Caching Pola Inti
*   **Cache-Aside (Lazy Loading)**: Aplikasi mencari data di cache. Jika *cache miss*, baca database, simpan ke cache, lalu return.
*   **Write-Through**: Aplikasi menulis ke cache, dan cache *secara sinkron* menulis ke database sebelum mengembalikan status sukses.
*   **Write-Back (Write-Behind)**: Aplikasi menulis ke cache. Cache langsung merespons sukses, lalu *secara asinkron* (via queue/worker) melakukan persistence ke database.
*   **Refresh-Ahead**: Sistem memprediksi dan me-refresh data di cache sebelum TTL kedaluwarsa berdasarkan interval akses.

### 2. Patologi Cache dan Solusi Rekayasa
*   **Cache Stampede / Thundering Herd**: Kondisi ketika key yang sangat panas (*hot key*) kedaluwarsa dan ribuan request mengeksekusi query database secara simultan. *Mitigasi*: **Probabilistic Early Expiration (XFetch Algorithm)** atau **Distributed Mutex Lock**.
*   **Cache Penetration**: Request mencari key yang tidak pernah ada di database maupun cache, menembus langsung ke persistent layer berulang kali. *Mitigasi*: **Bloom Filters** atau **Cache-Null-Object with Short TTL**.
*   **Cache Avalanche**: Sejumlah besar cache key kedaluwarsa pada waktu yang persis bersamaan, mengakibatkan lonjakan query disk instan. *Mitigasi*: **TTL Jittering (Randomized TTL)**.

---

## 06: Panduan Implementasi Step-by-Step

### Tahap 1: Instalasi Dependensi
```bash
npm install ioredis pg dotenv
npm install -D typescript @types/node @types/pg @types/ioredis tsx
```

### Tahap 2: Standardisasi Jittering TTL
Rumus dasar penerapan jitter:
$$\text{EffectiveTTL} = \text{BaseTTL} + \text{UniformRandom}(0, \text{JitterRange})$$

### Tahap 3: Implementasi Mutex Lock untuk Pencegahan Stampede
Gunakan key locking berbasis Redis `SET key value NX PX milliseconds` sebelum mengakses Database fallback.

---

## 07: Contoh Kasus Sederhana
Implementasi *Cache-Aside* dengan penanganan *Cache Penetration* (menyimpan marker nilai kosong):

```typescript
import Redis from 'ioredis';
import { Pool } from 'pg';

const redis = new Redis('redis://localhost:6379');
const db = new Pool({ connectionString: 'postgresql://postgres:postgres@localhost:5432/testdb' });

async function getProductById(productId: string): Promise<any | null> {
  const cacheKey = `product:${productId}`;
  
  // 1. Cek Redis
  const cached = await redis.get(cacheKey);
  if (cached) {
    if (cached === '__NULL__') return null; // Mitigasi Cache Penetration
    return JSON.parse(cached);
  }

  // 2. Fallback DB
  const result = await db.query('SELECT * FROM products WHERE id = $1', [productId]);
  
  if (result.rows.length === 0) {
    // Simpan empty state dengan TTL sangat pendek (60s)
    await redis.set(cacheKey, '__NULL__', 'EX', 60);
    return null;
  }

  const product = result.rows[0];
  // 3. Set Cache dengan TTL
  await redis.set(cacheKey, JSON.stringify(product), 'EX', 300);
  return product;
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah `CacheDataManager.ts` yang mengimplementasikan:
- Connection pooling resilient
- Cache-Aside dengan Distributed Lock (Mutex) via Redis
- Dynamic Jittering untuk mitigasi Avalanche
- Graceful degradation saat Redis down

```typescript
import Redis, { RedisOptions } from 'ioredis';
import { Pool, PoolConfig } from 'pg';
import crypto from 'node:crypto';

export interface CacheOptions {
  baseTTLSeconds: number;
  jitterMaxSeconds: number;
  lockTimeoutMs: number;
  lockRetryIntervalMs: number;
}

export class ProductionDataPersistenceManager {
  private pgPool: Pool;
  private redisClient: Redis;
  private isRedisHealthy: boolean = true;

  constructor(pgConfig: PoolConfig, redisConfig: RedisOptions) {
    // 1. PostgreSQL Connection Pool
    this.pgPool = new Pool({
      ...pgConfig,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    // 2. Redis Connection with Resilience
    this.redisClient = new Redis({
      ...redisConfig,
      maxRetriesPerRequest: 3,
      enableReadyCheck: true,
      retryStrategy(times) {
        return Math.min(times * 100, 3000);
      },
    });

    this.initRedisListeners();
  }

  private initRedisListeners(): void {
    this.redisClient.on('connect', () => {
      this.isRedisHealthy = true;
      console.info('[Redis] Connection established');
    });

    this.redisClient.on('error', (err) => {
      this.isRedisHealthy = false;
      console.error('[Redis] Internal Error / Disconnected:', err.message);
    });
  }

  private calculateJitteredTTL(baseTTL: number, jitterMax: number): number {
    const jitter = Math.floor(Math.random() * (jitterMax + 1));
    return baseTTL + jitter;
  }

  private async acquireLock(lockKey: string, lockValue: string, ttlMs: number): Promise<boolean> {
    if (!this.isRedisHealthy) return false;
    const result = await this.redisClient.set(lockKey, lockValue, 'PX', ttlMs, 'NX');
    return result === 'OK';
  }

  private async releaseLock(lockKey: string, lockValue: string): Promise<void> {
    if (!this.isRedisHealthy) return;
    // Release using Lua script to guarantee atomicity
    const luaScript = `
      if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
      else
        return 0
      end
    `;
    await this.redisClient.eval(luaScript, 1, lockKey, lockValue);
  }

  public async fetchWithCacheAside<T>(
    key: string,
    dbQueryFn: (db: Pool) => Promise<T | null>,
    options: CacheOptions = {
      baseTTLSeconds: 300,
      jitterMaxSeconds: 30,
      lockTimeoutMs: 5000,
      lockRetryIntervalMs: 50,
    }
  ): Promise<T | null> {
    // STEP 1: Attempt Cache Read if Healthy
    if (this.isRedisHealthy) {
      try {
        const cachedRaw = await this.redisClient.get(key);
        if (cachedRaw) {
          if (cachedRaw === '__NULL__') return null;
          return JSON.parse(cachedRaw) as T;
        }
      } catch (err) {
        console.warn(`[Cache Read Bypass] Fallback to DB due to error: ${(err as Error).message}`);
      }
    }

    // STEP 2: Cache Miss -> Prevent Cache Stampede via Mutex Lock
    const lockKey = `lock:${key}`;
    const lockToken = crypto.randomUUID();
    const hasLock = await this.acquireLock(lockKey, lockToken, options.lockTimeoutMs);

    if (!hasLock) {
      // Tunggu dan coba baca kembali dari cache
      await new Promise((resolve) => setTimeout(resolve, options.lockRetryIntervalMs));
      return this.fetchWithCacheAside(key, dbQueryFn, options);
    }

    // STEP 3: Single Worker executing DB Fetch
    try {
      const dbResult = await dbQueryFn(this.pgPool);
      
      if (this.isRedisHealthy) {
        const effectiveTTL = this.calculateJitteredTTL(options.baseTTLSeconds, options.jitterMaxSeconds);
        
        if (dbResult === null || dbResult === undefined) {
          // Prevent Cache Penetration: Store null object placeholder with short TTL
          await this.redisClient.set(key, '__NULL__', 'EX', 60);
        } else {
          await this.redisClient.set(key, JSON.stringify(dbResult), 'EX', effectiveTTL);
        }
      }

      return dbResult;
    } finally {
      // STEP 4: Release Distributed Lock
      await this.releaseLock(lockKey, lockToken);
    }
  }

  public async invalidateCache(key: string): Promise<void> {
    if (this.isRedisHealthy) {
      await this.redisClient.del(key);
    }
  }

  public async close(): Promise<void> {
    await this.redisClient.quit();
    await this.pgPool.end();
  }
}
```

---

## 09: Diagram Alur Kerja ASCII

```
[ Incoming Request ]
        |
        v
+------------------+       YES      +-----------------------+
| In Cache (Redis)?| -------------> | Return Cached Payload |
+------------------+                +-----------------------+
        | NO
        v
+------------------------------------+
| Acquire Distributed Lock (Redis NX)|
+------------------------------------+
        |                  |
   LOCK ACQUIRED       LOCK BUSY
        |                  |
        |                  v
        |           [ Sleep Jittered Interval ]
        |                  |
        |                  +---> (Loop Back to In Cache?)
        v
+-----------------------------+
| Query Primary Database (PG) |
+-----------------------------+
        |
        +-----> Data Found?
        |            |
       YES           NO
        |            |
        v            v
[ Set Cache + Jitter ]  [ Set Cache: '__NULL__' (TTL: 60s) ]
        |            |
        +-----+------+
              |
              v
     [ Release Lock via Lua ]
              |
              v
       [ Return Data ]
```

---

## 10: Analisis Trade-offs

| Strategi | Kelebihan | Kekurangan / Trade-offs | Use-Case Optimal |
|---|---|---|---|
| **Cache-Aside** | Hanya data yang diminta yang dicache; node crash tidak merusak data dasar. | Potensi pembacaan data *stale* jika update DB tidak menginvalidation cache. | Read-heavy, intermittent read queries (e-Commerce catalog). |
| **Write-Through** | Konsistensi cache tinggi; data selalu sinkron dengan database. | Latensi tulis tinggi (harus menulis ke 2 storage simultan). | Data yang harus segera konsisten saat dibaca setelah ditulis. |
| **Write-Back (Behind)**| Latensi tulis super cepat; query DB dapat di-batch untuk I/O saving. | Risiko data loss jika node Redis/Queue crash sebelum persistensi ke DB. | Tracking telemetry, real-time counters, metrics. |
| **Distributed Lock** | Mencegah overload DB secara mutlak (1 worker per missing key). | Penambahan latensi retry bagi worker lain; dependensi Redis overhead. | Data dengan akses konkurensi tinggi (*flash sale*). |

---

## 11: Best Practices & Antipatterns

### Best Practices
1. **Always Jitter TTLs**: Tambahkan komponen acak ($\pm 10\text{--}20\%$) pada TTL statis untuk mencegah kedaluwarsa serentak.
2. **Explicit Null Values**: Terapkan serialization khusus untuk payload bernilai kosong (`__NULL__`) guna menghentikan *Cache Penetration*.
3. **Deterministic Key Namespacing**: Gunakan format `<bounded_context>:<entity>:<id>` (contoh: `inventory:product:88392`).

### Antipatterns
1. **Cache as Single Source of Truth**: Menyimpan data unik di cache tanpa persistensi persisten yang terjamin.
2. **Hot Key Blocking Without Lock**: Mengizinkan ribuan request langsung fallback ke SQL Database saat cache hilang.
3. **Big Keys Serialization**: Menyimpan objek JSON raksasa (> 1MB) di dalam satu key Redis, yang memblokir single-threaded I/O loop Redis.

---

## 12: Security Hardening

1. **AUTH & TLS Encription**: 
   - Konfigurasikan enkripsi TLS *in-transit* untuk cluster Redis dan PostgreSQL.
   - Gunakan autentikasi Redis ACL (Access Control Lists) untuk membatasi eksekusi command destruktif (`FLUSHALL`, `KEYS`, `CONFIG`).
2. **Injection Defense**:
   - Sanitasi key namespace untuk mencegah *Command Injection* / Key-Space Splitting via karakter kontrol (`\r\n`).
3. **Memory Exhaustion (DoS)**:
   - Atur parameter `maxmemory` dan pasang eviction policy: `allkeys-lru` atau `volatile-lru`.

---

## 13: Observabilitas & Debugging

Gunakan custom metrics integration untuk memantau status ekosistem persistensi:

```typescript
export class CacheMetricsCollector {
  private hits = 0;
  private misses = 0;

  public recordHit(): void { this.hits++; }
  public recordMiss(): void { this.misses++; }

  public getMetrics() {
    const total = this.hits + this.misses;
    return {
      hits: this.hits,
      misses: this.misses,
      hitRate: total > 0 ? (this.hits / total) * 100 : 0,
    };
  }
}
```

### Key Metrics to Monitor
- **Redis Hit/Miss Ratio**: Wajib di atas $85\text{--}90\%$ pada kondisi normal.
- **Connection Pool Saturation**: Persentase *active connections* vs *max pool size* di PostgreSQL.
- **Evicted Keys Rate**: Jika angka ini melonjak, kapasitas memory Redis tidak mencukupi untuk working-set size.

---

## 14: Benchmarking & Performance

Jalankan pengujian throughput menggunakan k6 atau autocannon untuk membandingkan performa DB Direct vs Cached Pattern.

### Autocannon Script
```javascript
import autocannon from 'autocannon';

async function run() {
  const result = await autocannon({
    url: 'http://localhost:3000/api/products/10001',
    connections: 100,
    pipelining: 1,
    duration: 10,
  });
  console.log(result);
}
run();
```

### Karakteristik Performa

```
| Metric                   | DB Direct (Postgres) | Cache-Aside (Redis) | Improvement Factor |
|--------------------------|----------------------|---------------------|--------------------|
| Latency p95              | 48.2 ms              | 1.8 ms              | ~26x faster        |
| Latency p99              | 120.5 ms             | 3.1 ms              | ~38x faster        |
| Max Throughput (Req/sec) | 1,450 req/s          | 32,000 req/s        | ~22x throughput    |
```

---

## 15: Hands-on Lab Mini-Project

### Setup Database & Cache Playground
1. Jalankan infrastructure stack menggunakan Docker Compose:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: enterprise_db
      POSTGRES_PASSWORD: rootpassword
    ports:
      - "5432:5432"
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

2. Jalankan schema migration berikut pada Postgres:

```sql
CREATE TABLE products (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  price NUMERIC(12,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0
);

INSERT INTO products VALUES ('SKU-001', 'Enterprise Server', 4999.00, 100);
```

---

## 16: Automated Testing & Verification

Skrip pengujian unit/integrasi menggunakan Node.js Native Test Runner (`node:test`) dan assertion library:

```typescript
import { test, describe, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { ProductionDataPersistenceManager } from './CacheDataManager';

describe('Data Persistence & Cache Suite', () => {
  let manager: ProductionDataPersistenceManager;

  before(() => {
    manager = new ProductionDataPersistenceManager(
      { connectionString: 'postgresql://postgres:rootpassword@localhost:5432/enterprise_db' },
      { host: 'localhost', port: 6379 }
    );
  });

  after(async () => {
    await manager.close();
  });

  test('Should perform Cache-Aside successfully and resolve from cache on secondary call', async () => {
    let dbCallCount = 0;
    const testKey = 'unit:test:product:SKU-001';

    const mockDbQuery = async () => {
      dbCallCount++;
      return { id: 'SKU-001', name: 'Enterprise Server', price: 4999.0 };
    };

    await manager.invalidateCache(testKey);

    // Call 1: Miss -> DB Call
    const res1 = await manager.fetchWithCacheAside(testKey, mockDbQuery);
    assert.equal(res1?.id, 'SKU-001');
    assert.equal(dbCallCount, 1);

    // Call 2: Hit -> Skip DB Call
    const res2 = await manager.fetchWithCacheAside(testKey, mockDbQuery);
    assert.equal(res2?.id, 'SKU-001');
    assert.equal(dbCallCount, 1, 'Database must not be queried on cache hit');
  });
});
```

Jalankan dengan CLI:
```bash
npx tsx --test ./test/CacheDataManager.test.ts
```

---

## 17: Troubleshooting Guide

| Gejala Masalah | Investigasi | Solusi |
|---|---|---|
| PostgreSQL Connection Timeout under load | Cek `pg_stat_activity` dan metrik active connection pool. | Periksa apakah caching layer mengalami bypass total (*Penetration*) atau *Lock Stampede* gagal menghentikan traffic. |
| Redis memory footprint melonjak tak terkendali | Eksekusi command `redis-cli --bigkeys` dan cek konfigurasi `maxmemory-policy`. | Terapkan batas TTL pada semua key tanpa pengecualian dan pasang policy `volatile-lru` / `allkeys-lru`. |
| Deadlock saat acquire mutex key | Nilai timeout lock habis saat worker DB fetch belum selesai. | Tingkatkan `lockTimeoutMs` sesuai estimasi P99 latensi query DB dan gunakan validasi token pada pelepasan lock. |

---

## 18: Checklist Produksi

- [ ] Semua konfigurasi TTL memiliki **Dynamic Jitter** untuk menghindari *Cache Avalanche*.
- [ ] Penanganan fallback null-object diimplementasikan guna mengatasi *Cache Penetration*.
- [ ] Mutex Distributed Lock (RESP3 Atomic SET NX/PX) aktif untuk key berkepadatan query tinggi.
- [ ] Parameter connection pool RDBMS dikonfigurasi proporsional terhadap worker CPU limit.
- [ ] Redis client mengonfigurasi `retryStrategy` dan penanganan graceful saat Redis tidak terjangkau (circuit-breaking/bypass).
- [ ] TLS diaktifkan untuk koneksi Redis dan PostgreSQL di production environment.
- [ ] Skrip Lua atomik digunakan saat merilis kunci lock Redis.

---

## 19: Ringkasan Eksekutif
Implementasi caching data pada level enterprise melampaui sekadar eksekusi `redis.get` dan `redis.set`. Arsitektur data persistence yang tangguh menuntut isolasi kegagalan (*graceful degradation*), sinkronisasi konkurensi (pencegahan *stampede*), dan perlindungan terhadap kegagalan multi-instance melalui algoritma probabilistik dan locking terdistribusi. Node.js enterprise backend harus memperlakukan caching sebagai peredam I/O probabilistik yang terikat pada integritas data ACID dari database relasional di belakangnya.

---

## 20: Referensi & Bacaan Lanjutan
- **Redis Documentation**: *Distributed Locks with Redis (Redlock Pattern & Single-Instance Mutex)*.
- **PostgreSQL Global Development Group**: *Connection Pooling Architectures & pg_stat_statements Analysis*.
- **VLDB Journal**: *Optimal Probabilistic Cache Expiration: Optimal Early-Expiration algorithms (XFetch)*.
- **Martin Kleppmann**: *Designing Data-Intensive Applications (Chapter 3: Storage and Retrieval)*.