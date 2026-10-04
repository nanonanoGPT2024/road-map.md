# BAB 03: STRATEGI CACHING LANJUTAN & POLA MITIGASI ANOMALI
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Mendiagnosis dan Memitigasi Anomali Caching Skala Besar:** Mengidentifikasi akar masalah, pola kegagalan, dan solusi rekayasa untuk tiga anomali utama: *Cache Penetration*, *Cache Breakdown (Thundering Herd)*, dan *Cache Avalanche*.
- **Mengimplementasikan Pola Caching Lanjutan:** Membangun pipeline arsitektural *Write-Behind (Write-Back)*, *Refresh-Ahead*, dan *Probabilistic Early Expiration (Algoritma XFetch)* untuk menjaga konsistensi data dan latensi P99 tetap rendah.
- **Mendesain Arsitektur Caching Multi-Tier (L1/L2):** Menggabungkan cache lokal dalam memori aplikasi (*In-Process/L1*) dengan Redis terdistribusi (*L2*) menggunakan mekanisme *Redis Pub/Sub Invalidation* atau *Client Side Caching (RESP3 Tracking)*.
- **Mengintegrasikan Struktur Data Probabilistik:** Mengimplementasikan *Bloom Filter* dan *Cuckoo Filter* menggunakan modul RedisBloom untuk mengeliminasi beban query dari request non-existent ke database primer.
- **Mengeksekusi Strategi Konkurensi Kritis:** Mencegah degradasi performa pada *Hot Keys* menggunakan abstraksi *Singleflight* dan *Distributed Locks (Redlock/SETNX with TTL)* secara atomik.

---

### 2. Prerequisites

Sebelum mendalami modul ini, Anda wajib menguasai:
- **Arsitektur Internal Redis Dasar:** Pemahaman model *single-threaded event loop* (ae event loop), protokol RESP (RESP2 & RESP3), dan memori internal (jemalloc, SDS, zip list/listpack).
- **Dasar Pola Caching:** Implementasi konseptual *Cache-Aside (Lazy Loading)* dan *Read/Write-Through*.
- **Rekayasa Sistem Konkuren:** Pemahaman mendalam tentang *race conditions*, *mutex/semaphore*, non-blocking I/O, serta *context cancellation/deadlines* pada bahasa backend tingkat lanjut (Go, Rust, atau Node.js enterprise).
- **Tooling:** Docker Engine, Docker Compose, Redis CLI, dan tool benchmarking seperti `k6` atau `hey`.

---

### 3. Concept & Internal Architecture

Dalam sistem enterprise berkecepatan tinggi, kegagalan caching bukan sekadar masalah fungsional ("data tidak ditemukan"), melainkan ancaman sistemik yang dapat meruntuhkan database relasional downstream dalam hitungan detik.

```
+---------------------------------------------------------------------------------------+
|                                ARSITEKTUR KONTROL CACHE L1/L2                          |
+---------------------------------------------------------------------------------------+

  Client Request
        |
        v
+---------------+      Hit       +-------------------------+
|  App Instance | -------------> | L1: In-Process Memory   |
|  (Node/Go)    |                | (e.g., Ristretto/GoCache)|
+---------------+                +-------------------------+
        | Miss                                |
        v                                     | Eviction via
+---------------+      Hit                    | Redis Tracking
|  App Instance | -------------> +-------------------------+ (RESP3 Invalidate)
|  Engine Layer |                | L2: Distributed Redis   | <----------------+
+---------------+                +-------------------------+                  |
        | Miss                                |                               |
        |                                     v Check Existance               |
        |                            +-------------------------+              |
        |                            | RedisBloom (Bloom/Cuckoo)|             |
        |                            +-------------------------+              |
        |                                     | Negative: Fast Return 404     |
        v Positive (May Exist)                v                               |
+------------------------------------------------------+                      |
| Singleflight Coordinator / Distributed Mutex Guard   |                      |
+------------------------------------------------------+                      |
        | Exactly 1 Request Allowed                                           |
        v                                                                     |
+-------------------------+       Async Write / Read-Through Update           |
| Primary SQL Database    | --------------------------------------------------+
| (PostgreSQL / Aurora)   |
+-------------------------+
```

#### 3.1. Anatomi Anomali Caching

##### A. Cache Penetration
Kondisi di mana request masuk mencari key yang **tidak pernah ada** baik di cache maupun di database primer (misal: scan exploit dengan ID acak `GET /users/-999999` atau scanning UUID palsu). Akibatnya, cache selalu *miss*, dan setiap request diteruskan langsung ke disk I/O database.
- **Internal Mechanics:** Bypass total terhadap lapisan caching. Peningkatan tajam IOPS database, degradasi thread pool DB.
- **Mitigasi:**
  1. *Bloom Filter*: Bit vector berukuran tetap dengan $k$ hashing functions. Mengembalikan status deterministik: *"Pasti tidak ada"* vs *"Mungkin ada"*.
  2. *Cache Null Object with Short TTL*: Menyimpan placeholder value (misal: `"{}"` atau `NULL`) dengan TTL singkat (30–60 detik).

##### B. Cache Avalanche
Kondisi di mana sejumlah besar key pada cache **kedaluwarsa (expire) secara bersamaan** atau instance Redis mengalami restart/crash mendadak. Seluruh traffic client jatuh sekaligus ke database primer secara bersamaan.
- **Internal Mechanics:** Redis mengeksekusi passive/active expire cycle. Ketika expire serempak terjadi di bawah beban tinggi, read queries memicu kueri paralel masif ke database downstream. Database mengalami CPU 100%, exhaustion connection pool, dan cascade failure ke seluruh microservices.
- **Mitigasi:**
  1. *Jitter (Randomized TTL)*: $TTL_{final} = TTL_{base} + \text{random}(0, J)$ di mana $J$ adalah rentang jitter (misal: 10%–20% dari base).
  2. *Multi-Cluster/HA Architecture*: Master-Replica dengan Redis Sentinel atau Redis Cluster, persistent store via dual-write.

##### C. Cache Breakdown (Thundering Herd)
Kondisi di mana satu key yang berstatus **Hot Key** (memiliki frekuensi request sangat tinggi, misal: banner promosi flash sale, detail produk terlaris) tiba-tiba expired atau terevinsi. Pada milidetik tersebut, ribuan concurrent worker mendapati cache miss dan secara simultan menjalankan query berat yang sama ke database.
- **Internal Mechanics:** Read contention spike pada layer penyimpanan. $N$ thread/goroutine mengeksekusi blocking I/O identik.
- **Mitigasi:**
  1. *Distributed Mutex*: Hanya thread pemegang kunci pertama yang diizinkan memuat data dari DB; thread lain menunggu dan membaca dari cache setelah lock dirilis.
  2. *Singleflight Pattern*: Di level proses aplikasi, menekan *in-flight requests* dengan key identik sehingga hanya satu eksekusi yang berjalan, lalu hasilnya di-broadcast ke seluruh caller.
  3. *Probabilistic Early Expiration (XFetch)*: Menghitung secara probabilistik apakah worker harus me-refresh cache **sebelum** waktu kedaluwarsa tiba, berdasarkan waktu komputasi data dan probabilitas akses.

#### 3.2. Formulasi Matematis Mitigasi

##### Bloom Filter Optimization
Untuk kapasitas $n$ item dan toleransi false positive probability $p$:
- Ukuran bit array optimal ($m$ bits):
  $$m = -\frac{n \ln p}{(\ln 2)^2}$$
- Jumlah fungsi hash optimal ($k$):
  $$k = \frac{m}{n} \ln 2$$

##### Algoritma XFetch (Probabilistic Early Expiration)
Mencegah cache breakdown secara asinkron tanpa locking. Key di-refresh lebih awal jika:
$$-\beta \cdot \delta \cdot \ln(\text{rand}()) > \text{expiry} - \text{now}$$
- $\beta > 0$: Nilai pengali agresivitas refresh (biasanya $\beta = 1$).
- $\delta$: Waktu (durasi) yang dibutuhkan untuk mengeksekusi kueri kalkulasi/database (dalam detik).
- $\text{rand}()$: Angka acak pseudo-uniform dari interval $(0, 1]$.
- $\text{expiry} - \text{now}$: Sisa umur key dalam hitungan detik.

Ketika key semakin mendekati masa kadaluwarsa, nilai $-\ln(\text{rand}())$ yang bernilai positif akan memperbesar peluang bahwa kondisi di atas bernilai `true`, sehingga memicu *background refresh* sebelum key kedaluwarsa secara absolut.

---

### 4. Why & What

| Pendekatan / Pola | Keunggulan Utama | Risiko / Biaya Operasional | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Cache-Aside + Jitter** | Sederhana diimplementasikan, resource-efficient, mengeliminasi synchronized eviction. | Data inkonsisten jangka pendek jika ada update; masih rentan Hot Key breakdown. | Default baseline untuk semua entity read-heavy umum. |
| **Singleflight + Mutex** | Mengeliminasi 100% thundering herd pada key individual; proteksi total ke database. | Menambah latensi untuk request yang menunggu lock; kompleksitas deadlock handling. | Read path pada data yang sangat mahal di-generate (laporan agregasi, katalog home). |
| **Bloom Filters (RedisBloom)** | O(k) fast rejection untuk key non-existent; overhead memori sangat minim vs Hash. | False positive inherent (tidak bisa 0%); delete operasi sulit (memerlukan Cuckoo Filter). | Menangkal malicious bot traffic & ID traversal scanning. |
| **Two-Tier (L1 In-Memory + L2 Redis)** | Latensi sub-mikrodetik (L1); reduksi traffic network I/O ke Redis cluster hingga 90%. | Kompleksitas sinkronisasi cache coherence antar instance; konsumsi heap memori lokal. | Hot key bervolume ekstrem (>100k RPS per instance) seperti auth tokens, global configs. |
| **Probabilistic (XFetch)** | Zero blocking I/O; refresh berjalan transparan tanpa latency penalty pada client. | Membutuhkan penyimpanan metadata durasi eksekusi ($\delta$) di dalam cache value. | Read-intensive workloads dengan runtime kalkulasi DB yang tinggi dan stabil. |

---

### 5. How: Workflow Detail

#### 5.1. Alur Penanganan Request dengan Mutex & Singleflight (Mitigasi Breakdown)

```
[Client Call]
     |
     v
[Check Redis L2] -----------------(Hit)------------------> [Return Data]
     |
   (Miss)
     v
[In-Process Singleflight (Mutex Group)]
     |
     +-----> [Follower Callers: Wait on Channel/Cond] ---> [Await Leader -> Read Cache]
     |
 [Leader Caller]
     |
     v
 [Acquire Redis Distributed Mutex (SET resource_key token NX PX 5000)]
     |
     +---(Failed to acquire)---------> [Sleep 50ms & Retry L2 Read]
     |
 (Acquired)
     |
     v
 [Query Primary SQL Database]
     |
     v
 [Calculate Jittered TTL: TTL = BaseTTL + rand(Jitter)]
     |
     v
 [Write to Redis L2 with TTL]
     |
     v
 [Release Distributed Mutex (via Lua Script: check token then DEL)]
     |
     v
 [Broadcast result to Singleflight Followers]
     |
     v
 [Return Data to Client]
```

#### 5.2. Alur Invalidation L1 via Redis Pub/Sub (Cache Synchronization)

```
Service Instance A                    Redis Cluster                    Service Instance B
    (Mutator)                                                              (Replica Reader)
        |                                   |                                     |
[Write to SQL DB]                           |                                     |
        |                                   |                                     |
[Update/Del Redis L2]                       |                                     |
        |                                   |                                     |
[Publish "cache:invalid": Key] ------------>|                                     |
                                            |------(Broadcast invalidation)------>|
                                            |                                     |
                                            |                          [Evict Key from L1 Memory]
                                            |                                     |
                                     (Channel Delivers)                 (Local Cache Cleared)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Thundering Herd dan Mutex
Bayangkan sebuah kantor administrasi (Database) yang hanya memiliki satu petugas arsip. Dokumen yang sering diminta ditaruh di papan pengumuman lobi (*Cache*). 
- **Normal:** 10.000 pengunjung lobi membaca salinan dokumen di papan pengumuman.
- **Cache Breakdown:** Tepat pukul 12:00, dokumen di papan pengumuman robek/dilepas karena expired. Sebanyak 10.000 pengunjung yang panik secara bersamaan merangsek masuk ke pintu sempit ruang arsip untuk meminta salinan baru. Petugas arsip terinjak-injak, pingsan, dan kantor kolaps.
- **Penerapan Mutex / Singleflight:** Begitu dokumen di papan lepas, pintu ruang arsip dipasangi sistem giliran atomik: hanya **1 orang perwakilan** yang diizinkan masuk mengambil dokumen. Sisanya diinstruksikan tertib menunggu di lobi. Setelah perwakilan menempelkan salinan baru di papan pengumuman, seluruh pengunjung langsung membacanya dari lobi tanpa menyentuh ruang arsip.

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Probabilistic Expiration (XFetch) Implementation (Go)

```go
package main

import (
	"context"
	"encoding/json"
	"math"
	"math/rand"
	"time"

	"github.com/redis/go-redis/v9"
)

type CachedRecord struct {
	Payload   string        `json:"payload"`
	Delta     time.Duration `json:"delta"`     // Durasi komputasi fetching DB
	CreatedAt time.Time     `json:"created_at"`
	TTL       time.Duration `json:"ttl"`
}

// XFetch: Mengembalikan true jika worker harus me-refresh data lebih awal
func ShouldRefreshEarly(rec CachedRecord, beta float64) bool {
	timeRemaining := rec.TTL - time.Since(rec.CreatedAt)
	if timeRemaining <= 0 {
		return true
	}
	
	// -beta * delta * ln(rand())
	// rand.Float64() mengembalikan interval (0, 1]
	randomVal := rand.Float64()
	if randomVal == 0 {
		randomVal = 0.00001
	}
	
	pEarly := -beta * rec.Delta.Seconds() * math.Log(randomVal)
	return pEarly > timeRemaining.Seconds()
}
```

#### 7.2. Practical Example: Enterprise Anti-Anomaly Cache Orchestrator

Berikut adalah implementasi *production-ready* yang menggabungkan:
1. **Cache Null Object** (Mitigasi Penetration).
2. **Jittered TTL** (Mitigasi Avalanche).
3. **Singleflight** (Mitigasi Breakdown lokal).
4. **Distributed Lock dengan Lua Script** (Mitigasi Breakdown lintas cluster).

```go
package cache

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"math/big"
	"time"

	"github.com/redis/go-redis/v9"
	"golang.org/x/sync/singleflight"
)

const (
	NullPlaceholder = "__CACHE_NULL__"
	NullTTL         = 45 * time.Second
)

var (
	ErrLockNotAcquired = errors.New("failed to acquire distributed lock")
	luaReleaseLock     = redis.NewScript(`
		if redis.call("get", KEYS[1]) == ARGV[1] then
			return redis.call("del", KEYS[1])
		else
			return 0
		end
	`)
)

type DatabaseFetcher func(ctx context.Context, key string) (string, error)

type EnterpriseCacheManager struct {
	client *redis.Client
	group  singleflight.Group
}

func NewEnterpriseCacheManager(client *redis.Client) *EnterpriseCacheManager {
	return &EnterpriseCacheManager{
		client: client,
	}
}

// GetOrSet mengorkestrasi pembacaan cache dengan mitigasi anomali penuh
func (m *EnterpriseCacheManager) GetOrSet(
	ctx context.Context,
	key string,
	baseTTL time.Duration,
	jitterMax time.Duration,
	fetcher DatabaseFetcher,
) (string, error) {
	// 1. Coba baca dari L2 Cache
	val, err := m.client.Get(ctx, key).Result()
	if err == nil {
		if val == NullPlaceholder {
			return "", errors.New("resource not found (cached)")
		}
		return val, nil
	} else if !errors.Is(err, redis.Nil) {
		// Degradasi graceful jika Redis error: bypass langsung ke fetcher
		return fetcher(ctx, key)
	}

	// 2. Cache Miss: Gunakan Singleflight untuk deduplikasi lokal
	data, err, _ := m.group.Do(key, func() (interface{}, error) {
		// Re-check Redis (double-checked locking pattern di level singleflight)
		v, err := m.client.Get(ctx, key).Result()
		if err == nil {
			if v == NullPlaceholder {
				return "", errors.New("resource not found (cached)")
			}
			return v, nil
		}

		// 3. Mitigasi Thundering Herd Lintas Server: Distributed Lock
		lockKey := fmt.Sprintf("lock:%s", key)
		lockToken, err := generateRandomToken()
		if err != nil {
			return nil, err
		}

		acquired, err := m.client.SetNX(ctx, lockKey, lockToken, 5*time.Second).Result()
		if err != nil || !acquired {
			// Backoff singkat, biarkan pemegang lock me-refresh cache
			time.Sleep(100 * time.Millisecond)
			vRetry, errRetry := m.client.Get(ctx, key).Result()
			if errRetry == nil {
				if vRetry == NullPlaceholder {
					return "", errors.New("resource not found (cached)")
				}
				return vRetry, nil
			}
			// Fallback paksa jika pemegang lock gagal/timeout
			return fetcher(ctx, key)
		}

		defer func() {
			// Release distributed lock atomik via Lua script
			_ = luaReleaseLock.Run(ctx, m.client, []string{lockKey}, lockToken).Err()
		}()

		// 4. Eksekusi pemanggilan database primer
		dbResult, dbErr := fetcher(ctx, key)
		if dbErr != nil {
			// Cache Penetration Mitigation: Simpan Null Object jika data tidak ada
			if errors.Is(dbErr, errors.New("not_found")) {
				_ = m.client.Set(ctx, key, NullPlaceholder, NullTTL).Err()
			}
			return nil, dbErr
		}

		// 5. Cache Avalanche Mitigation: Hitung Jitter
		finalTTL := calculateJitter(baseTTL, jitterMax)

		// 6. Tulis kembali ke Redis
		if errSet := m.client.Set(ctx, key, dbResult, finalTTL).Err(); errSet != nil {
			// Log error, namun return dbResult agar flow bisnis tidak gagal
			return dbResult, nil
		}

		return dbResult, nil
	})

	if err != nil {
		return "", err
	}
	return data.(string), nil
}

func calculateJitter(baseTTL time.Duration, maxJitter time.Duration) time.Duration {
	if maxJitter <= 0 {
		return baseTTL
	}
	n, _ := rand.Int(rand.Reader, big.NewInt(maxJitter.Nanoseconds()))
	return baseTTL + time.Duration(n.Int64())
}

func generateRandomToken() (string, error) {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Caching Flash Sale E-Commerce Tier-1
- **Kondisi Beban:** Flash sale produk edisi terbatas menghasilkan lonjakan request sebesar **450.000 RPS** pada satu SKU produk secara serentak pada detik 00:00:00.
- **Titik Kritis Kegagalan Awal:**
  - SKU Key `product:sku:998124` memiliki TTL default 5 menit.
  - Tepat saat flash sale dibuka, TTL key habis. Sebanyak 450k koneksi serentak mencoba membaca PostgreSQL instance.
  - Postgres Max Connections (2.000) terisi penuh dalam 4 milidetik; thread starvation terjadi, CPU database menyentuh 100%, dan seluruh payment gateway down akibat connection pooling exhaust.
- **Implementasi Solusi Terpadu:**
  1. **Tingkat 1 (Edge/API Gateway):** Pasang Nginx/OpenResty dengan cache `proxy_cache_use_stale updating` selama 1 detik.
  2. **Tingkat 2 (Application Service Layer - L1 Cache):** Implementasi in-memory Ristretto cache pada tiap pod Kubernetes dengan TTL 2 detik. 50 pod me-reduce 450.000 RPS menjadi maksimal 25 RPS per pod yang mencapai layer L2 (Redis).
  3. **Tingkat 3 (Redis Layer - L2 Cache):**
     - Memasang modul `RedisBloom` di depan lookup SKU untuk menolak bot yang melakukan brute-force ID produk acak (mengeliminasi 35.000 RPS scraping traffic).
     - Mengubah TTL key SKU dari statis menjadi formula: $TTL = 3600s + \text{rand}(0, 600s)$.
  4. **Tingkat 4 (Concurrency Lock):** Go singleflight group diterapkan di level service instance untuk menjamin hanya **satu goroutine per pod** yang dapat mengeksekusi request ke Redis bila L1 miss.
- **Hasil:**
  - Query ke PostgreSQL turun dari 450.000 QPS menjadi **1 QPS** (hanya 1 query pembaruan status inventori per interval refresh).
  - P99 Latency turun dari 8.500 ms (timeout) ke **4.2 ms**.
  - Pemanfaatan CPU Database turun dari 100% konstan menjadi rata-rata 18%.

---

### 9. Trade-offs

```
              Akurasi Konsistensi Data (Consistency)
                           /\
                          /  \
                         /    \
                        /      \
                       /        \
                      /   Trade  \
                     /    Space   \
                    /              \
                   /________________\
Latency Minimum                     Throughput & Efisiensi Biaya
(L1 Local Caching)                  (Probabilistic & Asynchronous)
```

| Parameter | Cache-Aside Sederhana | Two-Tier (L1 In-Memory + L2) | Distributed Locking (Redlock) | Probabilistic (XFetch) |
| :--- | :--- | :--- | :--- | :--- |
| **P99 Read Latency** | Rendah (~1-3 ms via network I/O) | Sangat Rendah (<100 µs via RAM lokal) | Menengah-Tinggi (menunggu lock acquisition) | Rendah (~1 ms, konsisten tanpa spike) |
| **Throughput (RPS)** | Menengah (~50k/node) | Sangat Tinggi (>500k/node) | Terbatas oleh kecepatan lock cycle | Tinggi |
| **Data Freshness** | Eventual (sesuai TTL/Write) | Memiliki jeda sinkronisasi antar-pod | Sangat Akurat (Strong Consistency) | Eventual Consistency |
| **Memory Footprint**| Terpusat di Redis | Terduplikasi di Heap RAM tiap pod aplikasi + Redis | Terpusat di Redis + Lock keys metadata | Terpusat di Redis + metadata footprint |
| **Complexity Cost** | O(1) - Sangat rendah | O(N) - Memerlukan pub/sub bus invalidation | O(N) - Rentan deadlock, clock-drift issues | O(log N) - Perlu komputasi probabilitas |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1. **Unbounded Cache Null Object:** Menyimpan key null/kosong dengan TTL yang setara dengan valid data TTL. Mengakibatkan database tidak dapat merefleksikan resource yang baru saja dibuat oleh user karena terhalang record null di cache yang berumur panjang.
2. **Missing Atomic Lock Release:** Melepaskan lock hanya dengan perintah `redis.Del(ctx, lockKey)`. Jika eksekusi fetcher memakan waktu lebih lama dari TTL lock, lock lama kedaluwarsa dan diakuisisi oleh process lain; pemanggilan `Del` yang terlambat akan menghapus lock milik worker lain (*lock identity theft*). Wajib menggunakan **Lua Script** untuk mencocokkan UUID pemegang kunci sebelum `DEL`.
3. **L1 Memory Leak & Missing Eviction Policy:** Membangun L1 cache menggunakan *unbounded raw map/dictionary* dalam aplikasi. Ketika request key unik bertambah terus-menerus, memory heap aplikasi membengkak hingga terkena *OOMKilled* oleh kernel. Gunakan L1 store yang memiliki algoritma TinyLFU atau segmented LRU dengan batasan memori yang ketat.
4. **Synchronized Cron Warming:** Melakukan cache warming terjadwal (misal: setiap jam 00:00:00) yang menulis puluhan ribu key dengan durasi kedaluwarsa seragam persis 1 jam. Pola ini memicu buatan manusia untuk bencana *Cache Avalanche*.

#### 10.2. Troubleshooting Playbook

```
[Problem Identified: Spike Latensi Database & Koneksi Penuh]
                       |
                       v
        [Cek Metrik Redis Hit Rate]
          /                    \
    (Hit Rate Rendah)      (Hit Rate 0% / Normal)
        /                        \
       v                          v
[Amati Pola Key Miss]       [Cek Karakteristik Key]
  /              \                    |
 v                v                   v
(Key Acak)   (Key Tunggal)      (Expire Berkelompok)
 |                |                   |
 v                v                   v
[Penetration] [Breakdown]         [Avalanche]
 |                |                   |
 |-- Aktifkan     |-- Pasang single-  |-- Inject jitter
 |   RedisBloom   |   flight pattern  |   random TTL
 |-- Cache Null   |-- Pasang Lock     |-- Review warming
     Object           Distributed         scripts
```

1. **Investigasi Kejadian:** Jalankan `redis-cli --hotkeys` dan `redis-cli --bigkeys` untuk mendeteksi key anomali.
2. **Lacak Operasi Lambat:** Jalankan `SLOWLOG GET 20`. Jika perintah kompleks seperti `KEYS *`, `HGETALL` pada data besar, atau script Lua berjalan >10ms, thread utama Redis terblokir dan mengakibatkan cache miss sistemik.
3. **Monitor Evictions:** Cek `INFO stats` parameter `evicted_keys`. Jika angkanya terus naik drastis, memori Redis telah melewati batas `maxmemory`, menyebabkan data penting terdepak sebelum waktu expired yang sebenarnya.

---

### 11. Best Practices (Production Checklist)

- [ ] **Jitter Injected:** Setiap pemanggilan `SETEX` atau setting TTL wajib menyertakan nilai acak minimum 10%–20% dari total TTL dasar.
- [ ] **Null Object Protection:** Entity not found harus dicache dengan durasi pendek (30–60 detik).
- [ ] **Bloom/Cuckoo Protection:** Khusus resource ID publik, terapkan pre-filtering probabilistik di depan Redis Cache-Aside.
- [ ] **Singleflight Local Layer:** Service layer aplikasi wajib mengintegrasikan de-duplikasi konkurensi (misal: `singleflight` di Go) sebelum menyentuh I/O distributed lock.
- [ ] **Deterministic Lock Expiration:** Distributed lock harus menggunakan TTL pengaman yang realistis dan auto-renewal (heartbeat/watchdog thread) jika pemrosesan membutuhkan durasi dinamis.
- [ ] **Atomic Lock Safe Release:** Pembebasan lock terdistribusi wajib mengeksekusi pemeriksaan identitas via Lua Script.
- [ ] **Connection Pooling Resiliency:** Konfigurasi Redis Pool: Aktifkan `MinIdleConns`, set `PoolTimeout` lebih kecil dari HTTP context deadline, dan isolasi thread pool Redis dari thread pool Database.
- [ ] **Circuit Breaker di Lapisan Cache:** Pasang circuit breaker (misal: Sony/gobreaker). Jika Redis cluster timeout berturut-turut, sistem harus beralih ke degraded mode alih-alih membanjiri database secara instan.

---

### 12. Hands-on Practice

Buat dan jalankan lab mitigasi caching multi-pattern berikut ini.

#### Struktur Direktori
```text
hands-on/m02/
├── docker-compose.yml
├── go.mod
├── go.sum
└── main.go
```

#### Langkah 1: Siapkan Environment (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  redis:
    image: redis/redis-stack-server:latest
    container_name: redis-m02
    ports:
      - "6379:6379"
    environment:
      - REDIS_ARGS=--maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 2s
      retries: 5
```

Jalankan container:
```bash
docker compose -f hands-on/m02/docker-compose.yml up -d
```

#### Langkah 2: Inisialisasi Modul Go
```bash
cd hands-on/m02
go mod init redis-resilience-lab
go get github.com/redis/go-redis/v9
go get golang.org/x/sync/singleflight
```

#### Langkah 3: Tulis Kode Pengujian Beban Konkurensi (`main.go`)
```go
package main

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
	"golang.org/x/sync/singleflight"
)

var (
	dbQueryCount int64
	rdb          *redis.Client
	sfGroup      singleflight.Group
)

func mockDatabaseAccess(ctx context.Context, id string) (string, error) {
	// Menghitung berapa kali database benar-benar dipukul
	atomic.AddInt64(&dbQueryCount, 1)
	// Simulasi latensi komputasi SQL Database yang lambat (150ms)
	time.Sleep(150 * time.Millisecond)

	if id == "non-existent" {
		return "", errors.New("record_not_found")
	}
	return fmt.Sprintf("payload-for-%s", id), nil
}

func getWithMitigation(ctx context.Context, key string) (string, error) {
	// 1. Cek Redis
	val, err := rdb.Get(ctx, key).Result()
	if err == nil {
		if val == "__NULL__" {
			return "", errors.New("record_not_found")
		}
		return val, nil
	}

	// 2. Gunakan singleflight untuk mitigasi thundering herd di satu instance
	res, err, _ := sfGroup.Do(key, func() (interface{}, error) {
		// Fetch ke DB
		data, dbErr := mockDatabaseAccess(ctx, key)
		if dbErr != nil {
			// Mitigasi Penetration: Cache status negatif
			rdb.Set(ctx, key, "__NULL__", 15*time.Second)
			return "", dbErr
		}

		// Mitigasi Avalanche: TTL + Jitter
		baseTTL := 10 * time.Second
		jitter := time.Duration(rand.Intn(3000)) * time.Millisecond
		rdb.Set(ctx, key, data, baseTTL+jitter)

		return data, nil
	})

	if err != nil {
		return "", err
	}
	return res.(string), nil
}

func main() {
	ctx := context.Background()
	rdb = redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})

	if err := rdb.Ping(ctx).Err(); err != nil {
		panic(fmt.Sprintf("Failed to connect to Redis: %v", err))
	}
	rdb.FlushAll(ctx)

	fmt.Println("=== TEST 1: THUNDERING HERD MITIGATION ===")
	atomic.StoreInt64(&dbQueryCount, 0)
	var wg sync.WaitGroup
	concurrentRequests := 100

	start := time.Now()
	for i := 0; i < concurrentRequests; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			_, _ = getWithMitigation(ctx, "sku:item-12345")
		}(i)
	}
	wg.Wait()
	duration := time.Since(start)

	fmt.Printf("Workers Selesai: %d\n", concurrentRequests)
	fmt.Printf("Total DB Hits  : %d (Harus bernilai 1 jika mitigasi bekerja)\n", atomic.LoadInt64(&dbQueryCount))
	fmt.Printf("Elapsed Time   : %v\n\n", duration)

	fmt.Println("=== TEST 2: CACHE PENETRATION MITIGATION ===")
	atomic.StoreInt64(&dbQueryCount, 0)
	
	// Panggilan pertama untuk invalid ID
	_, _ = getWithMitigation(ctx, "non-existent")
	// Panggilan berulang ke invalid ID yang sama
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = getWithMitigation(ctx, "non-existent")
		}()
	}
	wg.Wait()

	fmt.Printf("Invalid Requests: 51 calls\n")
	fmt.Printf("Total DB Hits   : %d (Harus bernilai 1 karena setelahnya tertahan oleh null cache)\n", atomic.LoadInt64(&dbQueryCount))
}
```

#### Langkah 4: Jalankan dan Amati Hasil Uji
```bash
go run main.go
```
Ekspektasi Output:
```text
=== TEST 1: THUNDERING HERD MITIGATION ===
Workers Selesai: 100
Total DB Hits  : 1 (Harus bernilai 1 jika mitigasi bekerja)
Elapsed Time   : ~155ms

=== TEST 2: CACHE PENETRATION MITIGATION ===
Invalid Requests: 51 calls
Total DB Hits   : 1 (Harus bernilai 1 karena setelahnya tertahan oleh null cache)
```

---

### 13. Exercises

#### 13.1. Level Easy
1. Modifikasi script `main.go` di atas untuk menambahkan pembacaan metrik waktu eksekusi individual (latency percentiles: P50, P95, P99).
2. Tulis fungsi validasi format key Regex sebelum melakukan request ke Redis untuk memblokir malicious pattern tanpa menyentuh cache server.

#### 13.2. Level Medium
1. Implementasikan mekanisme background refresh berbasis **Algoritma XFetch** di Go. Simulasikan traffic continue; buktikan secara visual/log bahwa key di-refresh sebelum expired secara absolut tanpa ada caller yang mengalami latency blocking sebesar 150ms.
2. Tambahkan layer RedisBloom (`BF.ADD` dan `BF.EXISTS`) menggunakan Redis-Stack untuk menangkal ribuan ID palsu acak sebelum dievaluasi ke logic cache null-object.

#### 13.3. Level Hard
1. Buat arsitektur L1/L2 Cache Coherency Engine:
   - Gunakan `sync.Map` atau `Ristretto` sebagai L1 memory dalam aplikasi.
   - Buat channel Redis Pub/Sub `cache:events:invalidate`.
   - Jalankan dua instance server Go pada port berbeda. Ketika Instance 1 mengupdate nilai suatu key melalui method `Update(key, val)`, kirimkan message invalidation ke Redis Pub/Sub sehingga Instance 2 membersihkan memory L1 lokal miliknya seketika.
   - Tangani skenario edge: Jika koneksi Pub/Sub terputus, paksa fallback L1 eviction berbasis short-TTL (e.g., TTL 5s max).

---

### 14. Challenge

**Skenario Kasus:** Anda adalah Lead Architect di sebuah platform ticketing konser global. Tiket konser band legendaris akan dibuka serentak. Terdapat 2.000.000 concurrent user aktif yang merefresh halaman ketersediaan seat layout konser (`GET /concerts/{id}/availability`) setiap 2 detik.

**Batasan Masalah & Kendala:**
1. Database relasional inventori hanya mampu menerima maksimal 50 query/detik sebelum mengalami koneksi timeout.
2. Ketersediaan tiket berubah dinamis setiap kali ada user yang melakukan *hold* kursi (seat locking berlangsung maksimal 5 menit).
3. Anda **dilarang keras** menyajikan data status ketersediaan yang *stale* (kadaluwarsa) lebih dari 3 detik kepada end-user.
4. Instance Redis L2 memiliki bandwidth jaringan terbatas; jika 2 juta user membaca Redis secara langsung, network interface card (NIC) Redis instance akan mengalami packet drop karena saturation.

**Tugas Arsitektur:**
Desain cetak biru (blueprint) arsitektur sistem secara menyeluruh:
- Bagaimana Anda menyusun topologi L1/L2 caching, edge distribution, dan invalidation pipeline?
- Pola konkurensi apa yang diterapkan di edge gateway dan microservices backend?
- Bagaimana skema penanganan anomali diterapkan jika node master Redis tiba-tiba mengalami crash/failover di detik ke-10 pembukaan tiket?

*(Rancang spesifikasi teknis, alur data komponen, serta format kontrol metadata tanpa menyalin template yang sudah ada).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. Apa perbedaan mendasar antara anomali *Cache Breakdown* dan *Cache Avalanche*?
2. Mengapa menambahkan nilai acak (jitter) pada parameter TTL dapat mencegah terjadinya Cache Avalanche?
3. Apa implikasi dari mengembalikan nilai `false` pada operasi pemanggilan Bloom Filter (`BF.EXISTS` bernilai 0)?
4. Bagaimana pola *Cache Null Object* melindungi sistem dari serangan *Cache Penetration*?
5. Mengapa algoritma pembacaan cache sederhana *Read-Through* rentan terhadap masalah *Thundering Herd* jika dijalankan di sistem multi-thread tanpa kontrol lock?

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. Jelaskan risiko keamanan sistem (*race condition*) yang terjadi jika distributed mutex dirilis hanya menggunakan perintah `DEL lock:resource` tanpa memverifikasi value/token pemegang kunci!
7. Dalam arsitektur caching multi-tier (L1 In-Process + L2 Redis Terdistribusi), jelaskan bagaimana skenario *stale read* dapat terjadi antar instance aplikasi dan bagaimana pola invalidation memitigasinya!
8. Pada algoritma Probabilistic Early Expiration (XFetch), jelaskan pengaruh variabel $\beta$ (beta) terhadap beban kerja server database dan latensi read client!
9. Mengapa struktur data *Cuckoo Filter* sering kali lebih diutamakan dibandingkan standar *Bloom Filter* pada skenario sistem yang sering melakukan operasi penghapusan atau pembaruan entity data?
10. Sebutkan kelemahan utama penggunaan in-memory L1 cache lokal di dalam aplikasi yang dijalankan di platform berbasis autoscaling dinamis (seperti Kubernetes HPA)!

#### Bagian 3: Production Case Troubleshooting
11. **Kasus 1:** Setelah deployment rilis baru, sebuah platform berita online mengalami lonjakan CPU PostgreSQL hingga 100% setiap tepat pergantian jam (01:00, 02:00, dst). Log Redis menunjukkan CPU Redis normal (<10%) dan memory stabil. Berdasarkan karakteristiknya, anomali apa yang terjadi dan bagaimana perbaikan konfigurasi pada source code caching-nya?
12. **Kasus 2:** Sebuah microservice Node.js menggunakan pola distributed lock Redis untuk mitigasi Thundering Herd saat cache miss. Pada jam sibuk, P99 request HTTP timeout secara masif, padahal Database downstream memiliki utilisasi CPU yang sangat rendah (15%). Investigasi internal menemukan jutaan goroutine/worker thread tertahan di status lock wait. Identifikasi celah desain apa yang memicu kondisi bottleneck ini!
13. **Kasus 3:** Tim security mendeteksi botnet melakukan HTTP GET ke endpoint API profil user dengan pola ID numerik increment negatif dan string hash acak (`/api/v1/users/-12093`, `/api/v1/users/x8a7f...`). Cache hit rate anjlok dari 98% ke 12%, dan database relasional kolaps. Solusi mitigasi bertahap apa yang harus dieksekusi secara instan (hotfix) dan jangka panjang (arsitektur)?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Jawaban Bagian 1 (Basic)
1. **Perbedaan Breakdown vs Avalanche:** Cache Breakdown terjadi pada **satu** key spesifik (*Hot Key*) yang kedaluwarsa dan diakses serentak oleh trafik masif. Cache Avalanche terjadi ketika **banyak key/seluruh cache** kedaluwarsa bersamaan atau instance Redis down, sehingga membanjiri database dengan multi-query yang beragam secara serentak.
2. **Fungsi Jitter:** Mencegah titik kedaluwarsa massal yang tersinkronisasi. Dengan menambahkan angka acak, proses peremajaan cache terdistribusi merata sepanjang kurva waktu, mendistribusikan beban DB I/O menjadi rata dan stabil.
3. **Implikasi Nilai Negatif Bloom Filter:** Secara matematis dijamin bahwa data tersebut **100% pasti tidak ada** di database. Request dapat langsung ditolak/dikembalikan dengan status 404 tanpa perlu melanjutkan eksekusi query ke DB.
4. **Proteksi Cache Null Object:** Dengan menyimpan penanda kosong (`NULL` string) dengan TTL pendek untuk ID yang tidak ditemukan, request lanjutan dengan ID identik akan langsung dilayani dari cache sebagai cache-hit kosong, mencegah lookup berulang ke disk database.
5. **Kelemahan Read-Through Tanpa Lock:** Ketika data hilang dari cache, tidak ada koordinasi antar-thread. Jika 1.000 thread mendeteksi miss pada mikrodetik yang sama, 1.000 thread tersebut akan mengeksekusi query database yang identik secara paralel (*duplicate in-flight queries*).

#### Kunci Jawaban Bagian 2 (Intermediate)
6. **Risiko Pola DEL Lock Non-Atomik:** Jika Proses A memegang lock dengan TTL 2 detik, namun eksekusi DB memakan waktu 3 detik, lock akan expired otomatis. Proses B kemudian sukses mengambil lock. Pada detik ke-3, Proses A selesai dan mengeksekusi `DEL`. Jika tanpa validasi token kepemilikan, Proses A akan menghapus lock milik Proses B, memicu proses konkuren liar lain masuk ke critical section.
7. **Stale Read Multi-Tier L1/L2:** Ketika Pod A mengupdate data di Database dan L2 Redis, memory RAM Pod B masih menyimpan salinan data lama di memori L1 miliknya hingga batas TTL L1-nya habis. Mitigasi: Pod A harus mem-broadcast pesan via Redis Pub/Sub agar Pod B segera mengeksekusi lokal eviction pada memori L1-nya begitu terjadi mutasi data.
8. **Pengaruh Nilai $\beta$ pada XFetch:** Nilai $\beta > 1$ membuat probabilitas refresh dini lebih agresif; cache akan diperbarui jauh lebih awal sebelum expired, menjaga latensi client tetap rendah namun menaikkan beban frekuensi kueri ke DB. Jika $\beta < 1$, refresh dini melambat, menghemat pemanggilan ke DB namun meningkatkan risiko breakdown jika beban mendadak melonjak mendekati waktu expiry.
9. **Cuckoo Filter vs Bloom Filter untuk Deletion:** Bloom filter standar menggunakan operasi bitwise OR hash yang tidak dapat di-decrement (menghapus bit 1 dapat merusak key lain yang berbagi bit yang sama). Cuckoo Filter menggunakan array bucket berisikan fingerprint dan mendukung penghapusan entri (*deletion*) serta penyesuaian dinamis tanpa harus membangun ulang seluruh struktur data dari nol.
10. **Kelemahan L1 pada Kubernetes Auto-scaling:** Setiap pod baru yang scale-up memulai siklus hidupnya dengan L1 cache yang kosong (*cold cache*). Autoscaling spike yang memicu kelahiran puluhan pod baru sekaligus dapat memicu replikasi pembacaan data identik ke L2 Redis atau DB secara serentak (*cold start storm*), serta meningkatkan fragmentasi sinkronisasi invalidation.

#### Kunci Jawaban Bagian 3 (Skenario Kasus Produksi)
11. **Analisis Kasus 1 (Avalanche Terjadwal):**
    - *Akar Masalah:* Terjadi *Cache Avalanche* yang disebabkan oleh script *cache warming* atau query write dengan setting TTL bulat statis (misal: tepat 3.600 detik). Pada pergantian jam, semua cache kedaluwarsa serentak.
    - *Solusi:* Ubah logic penentuan TTL menjadi: `TTL = 3600 + rand(0, 300)`. Lakukan staggered warming (penghangatan data bertahap) secara terjadwal menggunakan interval antrean acak.
12. **Analisis Kasus 2 (Distributed Lock Bottleneck / Lock Contention):**
    - *Akar Masalah:* Sistem memaksakan *distributed lock* Redis yang tersinkronisasi global untuk seluruh thread. Ratusan ribu request tertahan melakukan spin-lock wait/polling ke Redis, menghabiskan network overhead dan connection pooling pool microservice.
    - *Solusi:* Terapkan pola **Singleflight lokal** di dalam memori Node.js terlebih dahulu. Jika terdapat 1.000 request masuk ke satu instance Pod, reduksi di level thread/event loop menjadi tepat 1 request saja yang mencoba mengakuisisi Distributed Lock Redis. Terapkan pula fail-safe fallback: jika lock gagal diakuisisi setelah 100ms, baca nilai stale cache yang lama (*stale-while-revalidate*) daripada menahan thread/request user dalam antrean blocking.
13. **Analisis Kasus 3 (Serangan Cache Penetration Masif):**
    - *Mitigasi Instan (Hotfix):*
      1. Tambahkan middleware validasi regex ketat pada ID di API Gateway; tolak langsung request yang tidak memenuhi skema identifier (seperti ID bertanda minus `-`).
      2. Aktifkan penulisan *Cache Null Object* berdurasi 30 detik untuk setiap entity yang mengembalikan return not found dari DB.
    - *Mitigasi Jangka Panjang (Arsitektural):* Pasang modul **RedisBloom** di lapisan API boundary. Sinkronisasikan daftar valid ID secara asinkron ke dalam Bloom filter. Request yang dievaluasi negatif oleh Bloom filter langsung di-short-circuit dengan HTTP 404 dari Edge tanpa pernah menyentuh Redis L2 data layer maupun primary database.

---

### 16. Summary

1. **Anomali Skala Besar Bersifat Sistemik:** Penanganan anomali caching bukan sekadar tuning infrastruktur, melainkan membutuhkan desain defensif di level kode (*Singleflight*, *Jitter*, *XFetch*, dan *Cache Null Object*).
2. **Pemberian Jitter Bukan Opsional:** Tidak ada key produksi yang boleh memiliki nilai TTL konstan mutlak; variasi acak deterministik adalah pertahanan lini pertama mutlak terhadap bencana *Cache Avalanche*.
3. **Koordinasi Konkurensi Berlapis:** Cegah *Thundering Herd* dengan koordinasi dua tingkat: selesaikan konkurensi lokal di dalam heap memori aplikasi terlebih dahulu (*In-Process Singleflight*), baru kemudian gunakan *Distributed Mutex* di tingkat cluster Redis jika diperlukan.
4. **Struktur Data Probabilistik untuk Skala Ekstrem:** Ketika traffic mencapai ratusan ribu RPS, *Bloom Filter* atau *Cuckoo Filter* adalah mekanisme paling optimal secara komputasi untuk menangkal *Cache Penetration* sebelum membebani storage primer.
5. **Keseimbangan Konsistensi vs Latensi:** Desain arsitektur *Two-Tier (L1/L2)* memberikan kecepatan ekstrem sub-milidetik, namun mewajibkan adanya strategi invalidasi yang tangguh (seperti Pub/Sub atau Redis Tracking Engine) guna mencegah terjadinya *data anomaly* pada aplikasi hilir.