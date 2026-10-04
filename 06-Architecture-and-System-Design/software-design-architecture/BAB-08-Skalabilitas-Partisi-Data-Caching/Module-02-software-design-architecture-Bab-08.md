# BAB 08: Skalabilitas, Partisi Data, dan Caching
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Algoritma *Consistent Hashing* Tingkat Lanjut**: Mengembangkan router partisi data kustom yang menggunakan *virtual nodes* untuk mendistribusikan beban secara merata dan meminimalkan relokasi data saat terjadi *scaling* node ($\mathcal{O}(K/N)$ data movement).
2. **Membangun Arsitektur *Multi-Tier Caching* Berkinerja Tinggi**: Mengintegrasikan L1 (In-Memory/Process Heap) dan L2 (Distributed Cache seperti Redis/Memcached) lengkap dengan sinkronisasi berbasis *Change Data Capture* (CDC) dan protokol *event-driven invalidation*.
3. **Mengeliminasi Anomali Akses Data Skala Masif**: Mengimplementasikan algoritma probabilistik seperti **XFetch** dan konkurensi terkontrol (*single-flight mutual exclusion*) untuk memitigasi *Cache Stampede*, *Cache Avalanche*, serta *Cache Penetration*.
4. **Mengeksekusi Strategi Sharding Data Relasional**: Mengonfigurasi arsitektur *sharding* horizontal berbasis *range* dan *hash*, serta memitigasi permasalahan *cross-shard transaction* menggunakan pola *Saga* dan *Two-Phase Commit* (2PC) selektif.
5. **Menerapkan Observabilitas Partisi dan Metrik Latensi**: Melakukan profiling distribusi beban shard dan performa hit-ratio cache secara real-time pada lingkungan multi-region.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus telah menguasai:
- **Konsep Fondasi Modul 01**: Dasar skalabilitas vertikal vs horizontal, terminologi replikasi data (*Leader-Follower*, *Multi-Leader*), dan teorema CAP/PACELC.
- **Sistem Penyimpanan Data Internal**: Struktur data B-Tree vs Log-Structured Merge-tree (LSM-Tree), mekanisme Write-Ahead Logging (WAL).
- **Protokol Jaringan & Konkurensi**: TCP/IP, connection pooling, thread safety, race conditions, atomic operations, dan implementasi mutex/channel pada bahasa tingkat sistem (Go/Java/Rust).
- **Peralatan Teknis Minimal**:
  - Docker & Docker Compose v2.20+.
  - Go 1.22+ atau Java 21 LTS runtime.
  - Redis v7.2+ (Standalone & Cluster mode).
  - PostgreSQL 16+ (minimal 2 instance terpisah untuk simulasi shard).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Consistent Hashing dengan Virtual Nodes (V-Nodes)

Pada sistem terdistribusi, memetakan kunci data $K$ ke $N$ node fisik dengan operasi modulus standar ($Hash(K) \pmod N$) bersifat katastropik saat $N$ berubah: hampir seluruh data ($N / (N+1)$) harus berpindah posisi. 

*Consistent Hashing* memetakan kunci data dan node fisik ke dalam cincin logis berukuran $2^{32}-1$ atau $2^{64}-1$ (menggunakan algoritma hashing terdistribusi seperti MurmurHash3, CityHash, atau xxHash).

```
                      Hash Space: [0, 2^32 - 1]
                            0 / 2^32
                         .---' '---.
                      .-'           '-.
                   .-'                 '-.
       Node_C_V2  *                         * Node_A_V1
                /                             \
               /                               \
     Node_B_V1 *                                 * [Data Key: "user:902"]
              |                                   |  (Routes clockwise
              |                                   |   to Node_B_V2)
     Node_A_V2 *                                 * Node_B_V2
               \                               /
                \                             /
        Node_C_V1 *                         * Node_A_V3
                   '-.                 .-'
                      '-.           .-'
                         '---. .---'
```

##### Masalah Non-Uniformity & Skewness
Jika hanya node fisik yang ditempatkan di cincin, variansi jarak antar node akan sangat tinggi, menyebabkan *data skewness* (satu node menampung proporsi data jauh lebih tinggi daripada kapasitasnya).

##### Solusi Virtual Nodes
Setiap node fisik $P_i$ direpresentasikan oleh $V$ titik virtual di cincin:
$$V_{i,j} = \text{Hash}(\text{NodeID}_i \parallel \text{"#"} \parallel j), \quad \text{dimana } j \in [1, V]$$

Semakin besar nilai $V$, deviasi standar alokasi beban data antar node fisik mendekati nol:
$$\sigma \approx \frac{1}{\sqrt{V}}$$
Dalam standar industri (misal: Apache Cassandra, Amazon Dynamo), nilai $V \approx 200 - 500$ node virtual per node fisik.

---

#### 3.2 Dynamic Partitioning & Resharding Internals

Ketika volume partisi data melampaui batas ambang batas komputasi atau disk I/O, sistem harus melakukan pemecahan partisi (*partition split*). Terdapat dua paradigma partisi:

```
[Range-Based Partitioning]
Keyspace: [A - Z]
+-------------------+-------------------+-------------------+
| Shard 1: [A - H)  | Shard 2: [H - P)  | Shard 3: [P - Z]  |
+-------------------+-------------------+-------------------+
Keuntungan: Query range scanning (BETWEEN x AND y) sangat efisien.
Kerugian   : Rawan Write Hotspot jika key monoton (misal: ID auto-increment, timestamp).

[Hash-Based Partitioning]
Keyspace: MurmurHash3(Key) -> [0x00000000 - 0xFFFFFFFF]
+-------------------+-------------------+-------------------+
| Shard 1: Ring Seg | Shard 2: Ring Seg | Shard 3: Ring Seg |
+-------------------+-------------------+-------------------+
Keuntungan: Distribusi beban merata di seluruh keyspace.
Kerugian   : Range query harus dibroadcast ke seluruh shard (Scatter-Gather Overhead).
```

##### Routing Tier
Arsitektur produksi menggunakan *Router Proxy Stateless* (misal: Vitess untuk MySQL, Citus untuk PostgreSQL, atau custom Go Router) yang mengonsumsi metadata topologi dari consensus store terpusat (etcd atau Apache ZooKeeper).

---

#### 3.3 Multi-Tier Caching Architecture & Coherence Protocols

Mengandalkan satu distributed cache terpusat (Redis) dapat menciptakan *bottleneck* jaringan saat throughput mencapai jutaan RPS. Arsitektur enterprise menerapkan **Two-Tier (L1/L2) Caching Topology**:

```
 [ Client Request ]
         │
         ▼
 ┌───────────────┐
 │ API Gateway   │
 └───────┬───────┘
         │
         ▼
 ┌────────────────────────────────────────────────────────┐
 │ Microservice Pod                                       │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │ L1: Process Memory Cache (e.g., Ristretto/Caffeine) │  │  Latency: ~50-100 ns
 │  └────────────────────────┬─────────────────────────┘  │
 └───────────────────────────┼────────────────────────────┘
                             │ (L1 Miss)
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ L2: Distributed Cache Cluster (Redis Sentinel/Cluster) │  Latency: ~1-3 ms
 └───────────────────────────┬────────────────────────────┘
                             │ (L2 Miss)
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ Primary Database (Partitioned Shards / Read Replicas)  │  Latency: ~10-50 ms
 └────────────────────────────────────────────────────────┘
```

##### Coherence Protocol via Change Data Capture (CDC)
Untuk menghindari *stale data* pada L1 tanpa overhead polling:
1. Operasi mutasi menulis langsung ke Database Primary.
2. WAL (Write-Ahead Log) database ditangkap oleh engine CDC (seperti Debezium).
3. CDC mempublikasikan event `InvalidateKey(entity_id)` ke Kafka broker.
4. Seluruh instance aplikasi mengonsumsi Kafka event melalui listener lokal dan mengeksekusi invalidasi pada L1 memory masing-masing secara real-time.
5. Key pada L2 di-*evict* atau di-*update* secara atomik.

---

### 4. Why & What

| Dimensi | Mengapa Diperlukan (Why) | Apa Karakteristiknya (What) |
| :--- | :--- | :--- |
| **Consistent Hashing** | Naive modular hashing menyebabkan kegagalan kaskade (*cascading failure*) dan *cache wipeout* massal jika 1 node offline. | Membatasi migrasi data hanya ke segmen node tetangga, menjamin ketersediaan tinggi secara deterministik. |
| **Multi-Tier Caching** | Jaringan (NIC) Redis terpusat mengalami saturasi bandwidth saat flash sale (*hotkeys*). | Memindahkan subset data terpanas langsung ke memory heap aplikasi lokal (L1), memotong latensi ke ranah sub-mikrodetik. |
| **Probabilistic Expiration (XFetch)** | TTL konvensional memicu lonjakan query serentak ke DB saat key expired (*Cache Stampede/Dogpiling*). | Algoritma yang menghitung probabilitas *early refresh* berdasarkan latensi komputasi data dan sisa waktu hidup key. |
| **Database Sharding** | Batasan ukuran disk vertikal, saturasi IOPS, dan durasi snapshot/vacuuming yang tidak realistis pada tabel >10 TB. | Membagi dataset besar menjadi database-database independen (*shared-nothing architecture*). |

---

### 5. How (Workflow detail)

#### 5.1 Siklus Hidup Pembacaan Data: Probabilistic Read & Single-Flight Coalescing

```
Client Get(Key)
      │
      ├─► 1. Cek L1 In-Memory Cache
      │      ├─► [Hit & Valid] ──► Return Data
      │      └─► [Miss atau Expired]
      │
      ├─► 2. Cek L2 Distributed Cache (Redis)
      │      ├─► [Hit] ──► Evaluasi Probabilistik XFetch:
      │      │            Delta = Waktu kalkulasi data
      │      │            Beta  = Koefisien agresivitas (> 0)
      │      │            Jika: -(Delta * Beta * ln(rand())) > (TTL_Remaining):
      │      │                  Async Refresh L2 via Single-Flight
      │      │            Simpan Data ke L1 ──► Return Data
      │      └─► [Miss]
      │
      └─► 3. Single-Flight Execution Engine (Mutex Guard per Key)
             ├─► Pemenang Lock:
             │     a. Query database shard target via Shard Router.
             │     b. Simpan nilai ke L2 (dengan TTL + jitter).
             │     c. Simpan nilai ke L1.
             │     d. Broadcast hasil ke seluruh goroutine/thread yang menunggu.
             │     e. Release Lock.
             └─► Peminjam (Waiting Callers):
                   Menunggu eksekusi pemenang selesai, langsung menerima data tanpa menyentuh DB.
```

#### 5.2 Alur Mutasi Partisi & Invalidation Ring

```
Client Write(Key, Value)
      │
      ├─► 1. Resolve Shard ID: TargetShard = ConsistentHashRing.GetNode(Key)
      ├─► 2. Execute Transaction pada TargetShard (Commit to DB WAL)
      ├─► 3. DB WAL Engine menghasilkan binlog/WAL events
      ├─► 4. CDC Processor (Debezium) mendeteksi perubahan:
      │      └─► Publish message ke Pub/Sub Channel "cache-invalidation"
      ├─► 5. L2 Cache Processor menerima pesan:
      │      └─► Invalidate / Delete Key di L2 Redis
      └─► 6. Seluruh Consumer Pod menerima pesan:
             └─► Purge Key dari L1 Memory Cache lokal
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Perpustakaan Kota Terdistribusi

- **Range Sharding**: Buku diatur berdasarkan rentang alfabet penulis: Rak 1 (A-F), Rak 2 (G-M). Jika ada penulis baru sangat populer berawalan "J", Rak 2 akan runtuh karena antrean pembaca yang membeludak (*Hotspot*).
- **Hash Sharding**: Buku dipindai kodenya, di-hash, lalu ditempatkan di nomor rak tertentu. Penyebaran buku rata, tetapi untuk membaca seluruh serial novel (*range query*), Anda harus berkeliling ke semua rak.
- **Consistent Hashing**: Meja pustakawan diletakkan melingkar. Jika satu pustakawan pulang, buku di mejanya hanya dialihkan ke pustakawan terdekat di sebelah kanannya, bukan merombak seisi perpustakaan.
- **Multi-Tier Cache**: 
  - **L1**: Buku saku yang ada di saku baju Anda (akses instan, kapasitas sangat terbatas).
  - **L2**: Rak buku cadangan di ruang kerja pustakawan (kapasitas menengah, perlu jalan kaki sedikit).
  - **Primary DB**: Gudang arsip bawah tanah kota (kapasitas tidak terbatas, proses birokrasi lama).

#### Diagram Arsitektur Produksi End-to-End

```
                           ┌────────────────────────┐
                           │    Edge / Ingress      │
                           └───────────┬────────────┘
                                       │
                   ┌───────────────────┴───────────────────┐
                   ▼                                       ▼
        ┌─────────────────────┐                 ┌─────────────────────┐
        │   App Instance 1    │                 │   App Instance 2    │
        │ ┌─────────────────┐ │                 │ ┌─────────────────┐ │
        │ │ L1 Cache (Heap) │ │                 │ │ L1 Cache (Heap) │ │
        │ └────────┬────────┘ │                 │ └────────┬────────┘ │
        │          │          │                 │          │          │
        │ ┌────────┴────────┐ │                 │ ┌────────┴────────┐ │
        │ │  Single-Flight  │ │                 │ │  Single-Flight  │ │
        │ └────────┬────────┘ │                 │ └────────┬────────┘ │
        │          │          │                 │          │          │
        │ ┌────────┴────────┐ │                 │ ┌────────┴────────┐ │
        │ │ Hash Ring Router│ │                 │ │ Hash Ring Router│ │
        └───┬─────────────┬───┘                 └───┬─────────────┬───┘
            │             │                         │             │
            │             └───────────┐ ┌───────────┘             │
            ▼                         ▼ ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      L2 Redis Cluster (Distributed)                     │
│  [Node A: Slots 0-5460]   [Node B: Slots 5461-10922]   [Node C: ...]    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (On Cache Miss)
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Database Shard 0│         │ Database Shard 1│         │ Database Shard 2│
│ (Keys: A-H)     │         │ (Keys: I-Q)     │         │ (Keys: R-Z)     │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │ (WAL Engine)              │ (WAL Engine)              │ (WAL Engine)
         └───────────────────────────┼───────────────────────────┘
                                     ▼
                        ┌────────────────────────┐
                        │ Debezium CDC Pipeline  │
                        └────────────┬───────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │   Apache Kafka Topic   │
                        │ ("cache-invalidations")│
                        └────────────┬───────────┘
                                     │
               ┌─────────────────────┴─────────────────────┐
               ▼ (Async Invalidation)                      ▼ (Async Invalidation)
      [App 1 - Invalidate L1]                     [App 2 - Invalidate L1]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: High-Performance Consistent Hash Ring (Go)

Implementasi cincin hashing dengan dukungan virtual node dan pencarian biner ($\mathcal{O}(\log(N \cdot V))$).

```go
package main

import (
	"fmt"
	"hash/fnv"
	"sort"
	"strconv"
	"sync"
)

type HashRing struct {
	sync.RWMutex
	vnodes   int               // Jumlah virtual node per physical node
	ring     []uint32          // Cincin hash terurut berisi hash key dari vnodes
	nodeMap  map[uint32]string // Pemetaan hash vnode ke ID node fisik
	nodes    map[string]bool   // Set penampung node fisik yang aktif
}

func NewHashRing(vnodes int) *HashRing {
	return &HashRing{
		vnodes:  vnodes,
		nodeMap: make(map[uint32]string),
		nodes:   make(map[string]bool),
	}
}

func (h *HashRing) hash(val string) uint32 {
	hasher := fnv.New32a()
	hasher.Write([]byte(val))
	return hasher.Sum32()
}

func (h *HashRing) AddNode(node string) {
	h.Lock()
	defer h.Unlock()

	if h.nodes[node] {
		return
	}
	h.nodes[node] = true

	for i := 0; i < h.vnodes; i++ {
		vnodeKey := node + "#" + strconv.Itoa(i)
		vhash := h.hash(vnodeKey)
		h.ring = append(h.ring, vhash)
		h.nodeMap[vhash] = node
	}
	sort.Slice(h.ring, func(i, j int) bool { return h.ring[i] < h.ring[j] })
}

func (h *HashRing) RemoveNode(node string) {
	h.Lock()
	defer h.Unlock()

	if !h.nodes[node] {
		return
	}
	delete(h.nodes, node)

	newRing := make([]uint32, 0, len(h.ring)-(h.vnodes))
	for _, vhash := range h.ring {
		if h.nodeMap[vhash] == node {
			delete(h.nodeMap, vhash)
		} else {
			newRing = append(newRing, vhash)
		}
	}
	h.ring = newRing
}

func (h *HashRing) GetNode(key string) (string, error) {
	h.RLock()
	defer h.RUnlock()

	if len(h.ring) == 0 {
		return "", fmt.Errorf("hash ring kosong: tidak ada node aktif")
	}

	keyHash := h.hash(key)
	idx := sort.Search(len(h.ring), func(i int) bool {
		return h.ring[i] >= keyHash
	})

	// Wrap around cincin jika hash melebihi elemen terbesar
	if idx == len(h.ring) {
		idx = 0
	}

	return h.nodeMap[h.ring[idx]], nil
}

func main() {
	ring := NewHashRing(3) // 3 virtual node per physical node untuk demonstrasi

	ring.AddNode("db-shard-1.internal")
	ring.AddNode("db-shard-2.internal")
	ring.AddNode("db-shard-3.internal")

	sampleKeys := []string{"user:101", "order:8823", "session:abc-xyz", "payment:9901"}
	for _, k := range sampleKeys {
		node, _ := ring.GetNode(k)
		fmt.Printf("Key [%s] dialokasikan ke -> %s\n", k, node)
	}
}
```

---

#### 7.2 Practical Example: Enterprise Multi-Tier Caching Engine dengan Algoritma XFetch & Single-Flight

Kode produksi berikut mengimplementasikan mitigasi Cache Stampede menggunakan kombinasi:
1. Probabilistic Early Refresh (**XFetch**).
2. Concurrency Coalescing via **SingleFlight pattern**.
3. Fallback database loader.

```go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"math/rand"
	"sync"
	"time"
)

// Record pembungkus data cache yang mencatat metadata durasi komputasi
type CacheEnvelope struct {
	Value     string        `json:"val"`
	TTL       time.Duration `json:"ttl"`
	Delta     time.Duration `json:"delta"`     // Durasi komputasi query database
	CreatedAt time.Time     `json:"created_at"`
}

type SingleFlightGroup struct {
	mu sync.Mutex
	m  map[string]*call
}

type call struct {
	wg  sync.WaitGroup
	val interface{}
	err error
}

func (g *SingleFlightGroup) Do(key string, fn func() (interface{}, error)) (interface{}, error) {
	g.mu.Lock()
	if g.m == nil {
		g.m = make(map[string]*call)
	}
	if c, ok := g.m[key]; ok {
		g.mu.Unlock()
		c.wg.Wait()
		return c.val, c.err
	}
	c := new(call)
	c.wg.Add(1)
	g.m[key] = c
	g.mu.Unlock()

	c.val, c.err = fn()
	c.wg.Done()

	g.mu.Lock()
	delete(g.m, key)
	g.mu.Unlock()

	return c.val, c.err
}

// EnterpriseCacheManager mengelola orkestrasi caching multi-tier
type EnterpriseCacheManager struct {
	l1Cache      sync.Map // In-Memory L1 (Thread-safe)
	l2Storage    sync.Map // Mock Distributed L2 (Redis simulation)
	sf           SingleFlightGroup
	betaCoeff    float64  // Parameter agresivitas XFetch (rekomendasi: 1.0)
}

func NewEnterpriseCacheManager(beta float64) *EnterpriseCacheManager {
	return &EnterpriseCacheManager{
		betaCoeff: beta,
	}
}

// xfetchShouldRefresh mengeksekusi logika: -(delta * beta * ln(rand())) > remaining_ttl
func (m *EnterpriseCacheManager) xfetchShouldRefresh(env CacheEnvelope) bool {
	elapsed := time.Since(env.CreatedAt)
	remaining := env.TTL - elapsed

	if remaining <= 0 {
		return true
	}

	// Menghindari ln(0)
	r := rand.Float64()
	for r == 0 {
		r = rand.Float64()
	}

	// Formulasi Asli XFetch (Vattani et al.)
	// Probabilistic early expiration
	probabilisticThreshold := -float64(env.Delta.Milliseconds()) * m.betaCoeff * math.Log(r)
	return probabilisticThreshold > float64(remaining.Milliseconds())
}

func (m *EnterpriseCacheManager) GetOrFetch(
	ctx context.Context, 
	key string, 
	ttl time.Duration, 
	dbFallback func() (string, error),
) (string, error) {
	now := time.Now()

	// 1. Periksa L1 Cache
	if rawL1, ok := m.l1Cache.Load(key); ok {
		env := rawL1.(CacheEnvelope)
		if time.Since(env.CreatedAt) < env.TTL {
			// Early evaluation via XFetch
			if m.xfetchShouldRefresh(env) {
				go m.triggerAsyncRecompute(key, ttl, dbFallback)
			}
			return env.Value, nil
		}
	}

	// 2. Periksa L2 Cache (Simulasi Redis)
	if rawL2, ok := m.l2Storage.Load(key); ok {
		var env CacheEnvelope
		_ = json.Unmarshal(rawL2.([]byte), &env)

		if time.Since(env.CreatedAt) < env.TTL {
			// Backfill L1
			m.l1Cache.Store(key, env)

			if m.xfetchShouldRefresh(env) {
				go m.triggerAsyncRecompute(key, ttl, dbFallback)
			}
			return env.Value, nil
		}
	}

	// 3. Cache Miss Total: Eksekusi perlindungan SingleFlight
	res, err := m.sf.Do(key, func() (interface{}, error) {
		start := time.Now()
		computedVal, fetchErr := dbFallback()
		if fetchErr != nil {
			return nil, fetchErr
		}
		duration := time.Since(start)

		env := CacheEnvelope{
			Value:     computedVal,
			TTL:       ttl,
			Delta:     duration,
			CreatedAt: now,
		}

		// Update L1
		m.l1Cache.Store(key, env)

		// Update L2 (Serialize to bytes)
		payload, _ := json.Marshal(env)
		m.l2Storage.Store(key, payload)

		return computedVal, nil
	})

	if err != nil {
		return "", err
	}
	return res.(string), nil
}

func (m *EnterpriseCacheManager) triggerAsyncRecompute(
	key string, 
	ttl time.Duration, 
	fallback func() (string, error),
) {
	_, _ = m.sf.Do("async:"+key, func() (interface{}, error) {
		start := time.Now()
		val, err := fallback()
		if err != nil {
			return nil, err
		}
		duration := time.Since(start)

		env := CacheEnvelope{
			Value:     val,
			TTL:       ttl,
			Delta:     duration,
			CreatedAt: time.Now(),
		}

		m.l1Cache.Store(key, env)
		payload, _ := json.Marshal(env)
		m.l2Storage.Store(key, payload)
		return val, nil
	})
}

func main() {
	cache := NewEnterpriseCacheManager(1.0)
	key := "product:sku-90021"

	// Mock Slow Database Loader
	dbLoadCount := 0
	slowDbLoader := func() (string, error) {
		dbLoadCount++
		time.Sleep(200 * time.Millisecond) // Mensimulasikan query latency tinggi
		return fmt.Sprintf(`{"id": 90021, "name": "Enterprise Server", "price": 45000000}`), nil
	}

	// Simulasi 50 concurrent requests mengeksekusi key yang sama serentak
	var wg sync.WaitGroup
	requests := 50
	wg.Add(requests)

	startTime := time.Now()
	for i := 0; i < requests; i++ {
		go func(id int) {
			defer wg.Done()
			ctx := context.Background()
			val, err := cache.GetOrFetch(ctx, key, 2*time.Second, slowDbLoader)
			if err != nil {
				fmt.Printf("Worker %d failed: %v\n", id, err)
				return
			}
			if id == 0 {
				fmt.Printf("Worker 0 mendapatkan respon: %s\n", val)
			}
		}(i)
	}

	wg.Wait()
	fmt.Printf("Semua request selesai dalam: %v\n", time.Since(startTime))
	fmt.Printf("Total DB Calls yang terealisasi: %d (Harus bernilai 1 karena SingleFlight)\n", dbLoadCount)
}
```

---

### 8. Real World Case Study: E-Commerce Flash Sale Architecture

#### 8.1 Konteks Masalah
Sebuah platform e-commerce nasional menyelenggarakan program *Flash Sale*. Satu SKU produk diskon ekstrem ("iPhone Flagship 90% Off") diserbu oleh **500.000 Request Per Second (RPS)** tepat pada pukul 00:00:00.

#### 8.2 Titik Kegagalan Awal (The Bottleneck Incident)
1. **Redis NIC Saturation**: Key `inventory:iphone-flagship` terdistribusi di satu Redis node. Bandwidth jaringan 10Gbps pada instance Redis tersebut mengalami saturasi dalam 400 milidetik pertama, menolak 80% koneksi (*TCP connection dropped*).
2. **Cache Stampede ke Shard Database**: Ribuan request yang gagal mendapatkan respons dari Redis langsung melakukan *fallback query* ke Postgres Order Database Shard.
3. **Connection Pool Exhaustion**: Connection pool database habis (max connection 5.000 tercapai), CPU utilitas database mencapai 100%, disk IOPS antre, menyebabkan *cascading crash* di seluruh sistem checkout.

```
[Arsitektur Lama - Gagal]
500k RPS ──► [App Pods] ──(Semua akses 1 key)──► [Redis Node 4] ──(Saturasi NIC!)
                                                       │
                                                 (Cache Miss)
                                                       ▼
                                             [PostgreSQL Shard 1] (DB CRASH!)
```

#### 8.3 Solusi Arsitektur Produksi

```
[Arsitektur Baru - Bertahan Tanpa Gangguan]
500k RPS
   │
   ▼
[App Pods (100 Nodes)]
   │
   ├─► 1. L1 In-Memory Hotkey Cache (Local Ristretto Cache)
   │      - Menggunakan Probabilistic Early Refresh.
   │      - Menahan 95% traffic (475.000 RPS diselesaikan secara lokal di RAM).
   │
   └─► 2. L2 Key Splitting & Salt Replication (Menangani sisa 25.000 RPS)
          - Kunci Redis disebar menjadi N replika acak:
            `inventory:iphone-flagship_replica_1`
            `inventory:iphone-flagship_replica_2`
            ...
            `inventory:iphone-flagship_replica_16`
          - Konsumen membaca menggunakan algoritma:
            `ReadKey = "inventory:iphone-flagship_replica_" + rand(1, 16)`
          - Beban terdistribusi secara seimbang ke seluruh 16 node Redis Cluster.

   3. SingleFlight Coalescing Engine
      - Menahan database query maksimum 1 eksekusi konkuren per service pod.

   4. CDC-Driven Event Invalidation
      - Setiap mutasi pengurangan stok menulis ke DB.
      - Debezium membaca PostgreSQL WAL, memicu asynchronous purge ke seluruh L1.
```

#### 8.4 Hasil Implementasi
- **Latensi p99**: Menurun dari $> 15.000 \text{ ms}$ (disertai 504 Timeout) menjadi **$4.2 \text{ ms}$**.
- **Database Load**: Query ke PostgreSQL Shard turun dari $40.000 \text{ QPS}$ menjadi **$< 15 \text{ QPS}$**.
- **Ketersediaan (Availability)**: 99.999% sukses selama fase transaksi puncak flash sale.

---

### 9. Trade-offs

| Dimensi Arsitektur | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Partisi Data** | **Hash Sharding** (MurmurHash3) | **Range Sharding** (ID/Date-based) | Hash menjamin penyebaran data merata dan mencegah hotspot, tetapi mengorbankan performa range query ($\mathcal{O}(N)$ scatter-gather). Range sangat cepat untuk interval data sequential, namun rawan disk read/write contention pada node partisi aktif terbaru. |
| **Konsistensi Partisi** | **Two-Phase Commit (2PC)** | **Saga Pattern (Choreography/Orch)** | 2PC menyediakan konsistensi ACID langsung (*Strong Consistency*), tetapi blocking dan menyebabkan latensi tinggi serta rentan deadlocks. Saga mengadopsi *Eventual Consistency*, performa sangat tinggi dan resilient, namun membutuhkan kode kompensasi (*rollback*) yang kompleks secara aplikatif. |
| **Caching Tier** | **Single Tier (Distributed L2)** | **Two-Tier (Local L1 + Dist L2)** | L2 terpusat menjamin konsistensi pembacaan data antar pods tanpa delay replikasi internal, namun berisiko saturasi bandwidth jaringan. Two-Tier mengeliminasi network latency dan Redis bottleneck, namun membutuhkan koordinasi invalidasi (CDC/PubSub) yang memperbesar konsumsi memory pod. |
| **Write Strategy** | **Write-Through** | **Write-Behind (Write-Back)** | Write-Through menjamin data pada cache dan backing store selalu konsisten saat operasi tulis selesai (latensi tulis lebih tinggi). Write-Behind menawarkan latensi tulis super cepat (asynchronous batched writes ke DB), tetapi memiliki risiko *data loss* permanen jika cache instance crash sebelum flush. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Cache Penetration (Querying Non-Existent Keys)
- **Gejala**: Penyerang/klien secara masif meminta ID data acak yang tidak pernah ada di database (`GET /users/uuid-tidak-valid`). Seluruh layer cache miss, lalu membombardir database dengan query kosong secara berulang.
- **Deteksi**: Periksa metrik perbandingan antara `Cache Miss Ratio` dengan `DB Empty Query Result Rate`.
- **Mitigasi**:
  1. **Bloom Filter**: Pasang Bloom Filter di depan layer L1/L2. Jika Bloom Filter menyatakan *key definitely does not exist*, tolak request tanpa menyentuh cache ataupun DB.
  2. **Null Value Caching**: Simpan penanda kosong (`{"status": "NOT_FOUND"}`) pada cache dengan TTL pendek (misal: 30-60 detik).

#### 10.2 Cache Avalanche (Expiration Synchronization Collapse)
- **Gejala**: Seluruh cache key expire secara bersamaan (sering terjadi pasca batch import atau restart terjadwal), menyebabkan lonjakan seketika beban CPU dan memory pada database.
- **Deteksi**: Metrik `Eviction / Expired Key Count` menunjukkan lonjakan curam vertikal pada dashboard Redis.
- **Mitigasi**:
  Gunakan **TTL Jitter Algorithm**:
  $$\text{TargetTTL} = \text{BaseTTL} + \text{UniformRandom}(0, \text{JitterRange})$$

```go
func CalculateJitteredTTL(baseTTL time.Duration, jitterPercent float64) time.Duration {
    jitterMax := float64(baseTTL) * jitterPercent
    jitter := rand.Float64() * jitterMax
    return baseTTL + time.Duration(jitter)
}
```

#### 10.3 Hotspot Shard Skewness
- **Gejala**: Satu shard database mengalami utilisasi disk/CPU 95%, sementara shard lain menganggur pada kisaran 5-10%.
- **Troubleshooting Runbook**:
  1. Eksekusi analisis frekuensi kunci: identifikasi apakah sharding key memiliki kardinalitas rendah (misal: sharding berdasarkan `CountryCode` di mana 90% user berasal dari satu negara).
  2. Migrasi skema: Terapkan **Composite Sharding Key** (misal: `TenantID + Murmur3(UserID) % ShardBuckets`).
  3. Periksa distribusi Hash Ring: tingkatkan rasio Virtual Nodes dari default menjadi minimal 256 vnodes per node fisik.

---

### 11. Best Practices (Production Checklist)

#### Pre-Production & Sizing
- [ ] **Capacity Planning**: Pastikan ukuran payload L2 cache tidak melebihi 10KB per key. Untuk data besar, gunakan kompresi Zstandard (zstd) atau Snappy.
- [ ] **Virtual Nodes Configuration**: Tetapkan virtual nodes antara 200 hingga 384 vnodes per instance pada router consistent hashing.
- [ ] **Connection Pooling**: Batasi `MaxOpenConns` aplikasi ke database shard agar tidak melebihi formula kapasitas database:
  $$\text{MaxConnections} = (\text{CoreCount} \times 2) + \text{EffectiveSpindleCount}$$

#### Resilience & Reliability
- [ ] **Circuit Breaker di Cache Layer**: Jika latensi L2 (Redis) melonjak melampaui ambang batas ($> 50 \text{ ms}$), buka circuit breaker dan langsung sajikan data *stale* L1 atau fallback bertingkat dengan degradasi fitur graceful.
- [ ] **TTL Mandatory**: Larang keras konfigurasi key dengan status persistensi tanpa masa kadaluarsa (`TTL = -1`) kecuali untuk metadata statis konfigurasi global.
- [ ] **SingleFlight Implementasi**: Wajibkan seluruh pengambilan data dari storage engine utama dibungkus oleh pola konkurensi single-flight.

#### Observabilitas & Telemetri
- [ ] Export metrik performa:
  - `cache_hits_total{tier="l1"}`, `cache_misses_total{tier="l1"}`.
  - `cache_hits_total{tier="l2"}`, `cache_misses_total{tier="l2"}`.
  - `db_shard_query_duration_seconds{shard_id="X"}`.
- [ ] Pasang alert Prometheus ketika rasio *L1 + L2 Cache Hit Ratio* secara agregat turun di bawah 90%.

---

### 12. Hands-on Practice

Buat direktori dan berkas implementasi untuk menguji mitigasi Cache Stampede dengan SingleFlight dan simulasi routing shard data.

#### Struktur Direktori
```text
hands-on/m02/
├── docker-compose.yml
├── go.mod
├── main.go
└── simulation_test.go
```

#### Langkah 1: Siapkan `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  redis-l2:
    image: redis:7.2-alpine
    container_name: redis-l2-practice
    ports:
      - "6379:6379"
    command: redis-server --appendonly no --maxmemory 256mb --maxmemory-policy allkeys-lru

  shard1-db:
    image: postgres:16-alpine
    container_name: postgres-shard-1
    environment:
      POSTGRES_DB: shard_1
      POSTGRES_USER: engine
      POSTGRES_PASSWORD: secretpassword
    ports:
      - "5433:5432"

  shard2-db:
    image: postgres:16-alpine
    container_name: postgres-shard-2
    environment:
      POSTGRES_DB: shard_2
      POSTGRES_USER: engine
      POSTGRES_PASSWORD: secretpassword
    ports:
      - "5434:5432"
```

Jalankan environment penunjang:
```bash
cd hands-on/m02
docker compose up -d
```

#### Langkah 2: Inisialisasi Modul & Kode Pengujian

Inisialisasi modul Go:
```bash
go mod init enterprise/scalability
```

Tulis file implementasi praktikum `hands-on/m02/main.go`:
```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"hash/fnv"
	"log"
	"sort"
	"sync"
	"time"

	_ "github.com/lib/pq"
)

type ShardMap struct {
	ring    []uint32
	nodes   map[uint32]*sql.DB
	vnodes  int
	sync.RWMutex
}

func NewShardMap(vnodes int) *ShardMap {
	return &ShardMap{
		nodes:  make(map[uint32]*sql.DB),
		vnodes: vnodes,
	}
}

func (s *ShardMap) hash(key string) uint32 {
	h := fnv.New32a()
	h.Write([]byte(key))
	return h.Sum32()
}

func (s *ShardMap) RegisterShard(shardID string, db *sql.DB) {
	s.Lock()
	defer s.Unlock()

	for i := 0; i < s.vnodes; i++ {
		vnodeName := fmt.Sprintf("%s#%d", shardID, i)
		hVal := s.hash(vnodeName)
		s.ring = append(s.ring, hVal)
		s.nodes[hVal] = db
	}
	sort.Slice(s.ring, func(i, j int) bool { return s.ring[i] < s.ring[j] })
}

func (s *ShardMap) GetShard(key string) *sql.DB {
	s.RLock()
	defer s.RUnlock()

	hVal := s.hash(key)
	idx := sort.Search(len(s.ring), func(i int) bool {
		return s.ring[i] >= hVal
	})
	if idx == len(s.ring) {
		idx = 0
	}
	return s.nodes[s.ring[idx]]
}

func main() {
	// Koneksi ke dua PostgreSQL Shard
	connStr1 := "postgres://engine:secretpassword@localhost:5433/shard_1?sslmode=disable"
	connStr2 := "postgres://engine:secretpassword@localhost:5434/shard_2?sslmode=disable"

	db1, err := sql.Open("postgres", connStr1)
	if err != nil {
		log.Fatalf("Gagal inisialisasi shard 1: %v", err)
	}
	defer db1.Close()

	db2, err := sql.Open("postgres", connStr2)
	if err != nil {
		log.Fatalf("Gagal inisialisasi shard 2: %v", err)
	}
	defer db2.Close()

	// Inisialisasi skema tabel mini pada kedua shard
	setupQuery := `CREATE TABLE IF NOT EXISTS customer_profiles (
		account_id VARCHAR(64) PRIMARY KEY,
		balance BIGINT NOT NULL,
		updated_at TIMESTAMP NOT NULL
	);`

	for _, db := range []*sql.DB{db1, db2} {
		if _, err := db.Exec(setupQuery); err != nil {
			log.Fatalf("Gagal create table: %v", err)
		}
	}

	router := NewShardMap(50)
	router.RegisterShard("shard-1", db1)
	router.RegisterShard("shard-2", db2)

	// Uji distribusi write ke shard yang sesuai
	sampleAccounts := []string{"ACC-ID-001", "ACC-ID-002", "ACC-ID-003", "ACC-ID-004", "ACC-ID-005"}

	for _, acc := range sampleAccounts {
		targetDB := router.GetShard(acc)
		_, err := targetDB.ExecContext(
			context.Background(),
			"INSERT INTO customer_profiles (account_id, balance, updated_at) VALUES ($1, $2, $3) ON CONFLICT (account_id) DO UPDATE SET balance = customer_profiles.balance + 100",
			acc, 50000, time.Now(),
		)
		if err != nil {
			log.Printf("Gagal eksekusi insert key %s: %v", acc, err)
		} else {
			fmt.Printf("Akun [%s] berhasil dirouting dan dipersist ke Shard yang tepat.\n", acc)
		}
	}

	// Validasi isolasi data shard
	var count1, count2 int
	_ = db1.QueryRow("SELECT COUNT(*) FROM customer_profiles").Scan(&count1)
	_ = db2.QueryRow("SELECT COUNT(*) FROM customer_profiles").Scan(&count2)

	fmt.Printf("\n--- Ringkasan Distribusi Data Sharding ---\n")
	fmt.Printf("Shard 1 Record Count: %d\n", count1)
	fmt.Printf("Shard 2 Record Count: %d\n", count2)
	fmt.Printf("Total Record        : %d\n", count1+count2)
}
```

Jalankan praktikum:
```bash
go run main.go
```

---

### 13. Exercise

#### Level Easy
Buat fungsi algoritma penghitung TTL dengan **Jitter** menggunakan library standar. Fungsi menerima `baseTTL time.Duration` dan nilai `jitterFraction float64` (rentang $0.0 - 0.5$). Buktikan lewat unit test bahwa 1000 iterasi pemanggilan menghasilkan nilai yang terdistribusi secara seragam di dalam rentang $[ \text{baseTTL}, \text{baseTTL} \times (1 + \text{jitterFraction}) ]$.

#### Level Medium
Kembangkan micro-engine in-memory L1 cache yang mendukung kapasitas batas elemen (*Bounded Capacity*) menggunakan algoritma penggusuran **LRU (Least Recently Used)**. Engine harus thread-safe dengan implementasi pembacaan konkuren (`sync.RWMutex`), dan mendukung fitur callback invalidasi ketika elemen digusur keluar dari antrean akibat saturasi memori.

#### Level Hard
Rancang dan implementasikan layer **Multi-Shard Two-Phase Commit (2PC) Coordinator** sederhana di Go. Koordinator harus mengeksekusi transfer saldo balance atomik antar dua pengguna (`User A` pada Shard 1 mentransfer dana ke `User B` pada Shard 2).
- **Fase 1 (Prepare)**: Lakukan locking dan pengecekan dana pada Shard 1 serta kesiapan penampungan pada Shard 2.
- **Fase 2 (Commit/Abort)**: Jika salah satu shard merespons `Failure` (misal: saldo tidak cukup atau query timeout), jalankan perintah `Abort` dan lakukan *compensating rollback* secara deterministik pada shard lawan tanpa meninggalkan kondisi *dangling transaction*.

---

### 14. Challenge

#### Skenario: Arsitektur Partisi Buku Besar Finansial Skala Global (Cross-Continent Multi-Region Sharding)

Sebuah bank digital beroperasi di tiga wilayah geografis utama: **APAC (Singapore)**, **EU (Frankfurt)**, dan **US (Virginia)**. Sistem memproses transaksi finansial multi-mata uang dengan regulasi ketat:
1. Data residensi perbankan (*Data Sovereignty Laws*) mewajibkan profil pengguna negara tertentu disimpan secara lokal pada region domisili akun tersebut.
2. Latensi transfer dana lintas region antar pengguna (contoh: Klien Frankfurt mengirim uang ke Klien Singapura) harus memiliki waktu respons $p99 < 800 \text{ ms}$ dengan jaminan **Strict Serializability** (tidak boleh ada kemungkinan *double-spending* atau *phantom balance*).
3. Terjadi *Split-Brain Network Partition* intermiten di mana kabel optik bawah laut lintas benua mengalami pemutusan (*inter-region network disconnect*) hingga durasi 15 menit.

#### Tugas Arsitektural Anda:
- Rancang topologi partisi database, *routing ring*, dan *consensus protocol* yang digunakan.
- Formulasikan arsitektur multi-tier caching yang tetap konsisten terhadap aturan residensi data.
- Definisikan protokol resolusi anomali saat mitigasi transaksi berjalan di tengah skenario *network partition* tanpa mengorbankan integritas saldo rekening.
- Buat dokumentasi arsitektur dalam bentuk dokumen teknis komprehensif, dilengkapi diagram state-machine alur transaksi serta diagram sekuens transaksional lintas wilayah.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. **Mengapa algoritma modulasi tradisional ($K \pmod N$) tidak dapat digunakan pada distributed cache cluster yang bersifat elastis?**
   - A. Karena hash function modulus memakan siklus komputasi CPU 10x lebih besar.
   - B. Karena penambahan atau pengurangan 1 node mengubah nilai penyebut pembagian, memicu perpindahan hampir seluruh key di cluster.
   - C. Karena tidak kompatibel dengan protokol TCP/IP.
   - D. Karena modulus hanya bisa menerima tipe data integer positif.

2. **Apa fungsi utama dari Virtual Nodes (V-Nodes) pada cincin Consistent Hashing?**
   - A. Menggandakan data ke banyak node sebagai mekanisme backup.
   - B. Menghilangkan kebutuhan alokasi IP Address pada server fisik.
   - C. Menyeimbangkan variansi jarak segmen hash sehingga distribusi data merata di seluruh node fisik.
   - D. Mempercepat koneksi throughput kartu jaringan (NIC).

3. **Peristiwa apakah yang terjadi saat sebuah cache key yang sangat populer (*hotkey*) habis masa berlakunya (expired), lalu ratusan ribu request mendadak menyerbu backing database secara bersamaan?**
   - A. Cache Penetration
   - B. Cache Stampede (Dogpiling)
   - C. Dirty Reads
   - D. Phantom Partitioning

4. **Bagaimana cara Bloom Filter mencegah anomali Cache Penetration?**
   - A. Dengan mengenkripsi key menggunakan hashing satu arah.
   - B. Menjamin 100% kepastian bahwa suatu data pasti ada di database.
   - C. Memfilter request di depan cache: jika Bloom Filter menyatakan *key pasti tidak ada*, request langsung ditolak tanpa menyentuh cache/database.
   - D. Menghapus key yang jarang digunakan secara berkala.

5. **Di antara strategi penulisan cache berikut, manakah yang memiliki latensi operasi tulis paling rendah dari perspektif aplikasi klien?**
   - A. Write-Through
   - B. Write-Around
   - C. Write-Behind (Write-Back)
   - D. Refresh-Ahead

---

#### Bagian 2: Intermediate (Analisis Arsitektur)
6. **Jelaskan cara kerja parameter probabilistik pada algoritma XFetch:**
   $$-( \text{Delta} \times \text{Beta} \times \ln(\text{rand}()) ) > \text{RemainingTTL}$$
   Apa dampak arsitektural jika nilai parameter `Beta` disetel ke angka `0`?
7. **Dalam arsitektur Sharding Berbasis Hash, mengapa eksekusi query SQL dengan klausa `ORDER BY created_at LIMIT 50` jauh lebih mahal secara komputasi dibandingkan arsitektur Monolitik tunggal?**
8. **Jelaskan perbedaan mendasar antara mekanisme mitigasi Cache Stampede menggunakan pendekatan *Single-Flight (Mutual Exclusion)* vs pendekatan *Probabilistic Early Expiration (XFetch)* dari aspek latensi pembacaan klien!**
9. **Kapan Anda sebaiknya TIDAK menggunakan strategi Caching L1 (In-Memory Heap) dan hanya mengandalkan L2 (Distributed Store)? Sebutkan 2 skenario konkretnya.**
10. **Bagaimana CDC (Change Data Capture) menyelesaikan persoalan *Race Condition* yang timbul pada implementasi invalidasi cache berbasis aplikasi (*Application-Level Dual-Writing*)?**

---

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: Sebuah platform media sosial mengalami insiden: Ketika selebriti dengan 80 juta follower memposting update status, L1 cache pada service pod mengalami Out Of Memory (OOM), dan pod mengalami restart berkali-kali (*CrashLoopBackOff*). Identifikasi akar masalahnya dan berikan langkah penanganan arsitekturalnya!
12. **Skenario 2**: Anda memiliki database yang di-shard menjadi 8 node independen menggunakan MurmurHash3 dari `account_id`. Bisnis mengharuskan pembuatan fitur pencarian: "Tampilkan seluruh akun yang terdaftar antara tanggal 1 Januari hingga 7 Januari yang memiliki status 'Active'". Evaluasi kelemahan pola kueri ini pada topologi yang ada, dan berikan arsitektur alternatif yang tepat tanpa mengubah sharding key database utama!
13. **Skenario 3**: Sebuah distributed lock berbasis Redis digunakan untuk membatasi akses refresh database pada kondisi cache miss. Suatu hari, Redis mengalami lonjakan latency jaringan (network stall) selama 5 detik, menyebabkan TTL lock terlampaui sebelum proses komputasi DB selesai. Akibatnya, terjadi eksekusi query ganda yang merusak konsistensi data. Rancang mekanisme *Fencing Token* atau alternatif pengamanan untuk mengatasi masalah konkurensi ini.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Bagian 1
1. **B**: Operasi modulus $K \pmod N$ sangat sensitif terhadap perubahan $N$. Penambahan/pengurangan satu node mengubah drastis indeks target untuk mayoritas data.
2. **C**: V-Nodes memetakan satu node fisik ke ratusan titik cincin hash logis, mengurangi deviasi standar pembagian partisi data dan mencegah ketimpangan beban.
3. **B**: Cache Stampede / Dogpiling / Cache Breakdown.
4. **C**: Bloom Filter bersifat *no false negatives*. Jika filter menyatakan *Not Present*, data dipastikan tidak ada di persistent store.
5. **C**: Write-Behind (Write-Back) mengembalikan respons sukses segera setelah data tercatat di cache memory, dan operasi tulis ke database sekunder dieksekusi secara asinkron dalam bentuk batch.

#### Panduan Jawaban Bagian 2
6. Nilai $\ln(\text{rand}())$ menghasilkan angka negatif acak. Jika `Beta = 0`, hasil perkalian probabilistic threshold akan selalu bernilai $0$. Akibatnya, early refresh tidak pernah terpicu sebelum sisa waktu hidup key habis secara mutlak ($\text{RemainingTTL} < 0$), mengembalikan sistem ke perilaku TTL naif yang rentan cache stampede.
7. Sharded DB tidak menyimpan indeks global terpadu. Proxy router harus mendistribusikan query ke seluruh shard (*Scatter-Gather*), menarik 50 baris teratas dari *masing-masing* shard ke memory proxy, melakukan sorting ulang secara agregat terhadap ($50 \times N$ baris), baru mengembalikan 50 data teratas final ke user. Ini mengonsumsi bandwidth jaringan dan CPU router.
8. **Single-Flight** memblokir caller lain hingga 1 proses komputasi query selesai; caller pertama menanggung latensi lambat query database, sementara caller yang mengantre mengalami lonjakan waktu tunggu (*wait latency*). **XFetch** menyegarkan cache di latar belakang (*asynchronous background thread*) sebelum cache kedaluwarsa secara riil, sehingga klien yang meminta data hampir selalu mendapatkan respon instan ($\mathcal{O}(1)$ cache hit latency) tanpa pernah terblokir oleh pembaruan data.
9. Kasus di mana L1 Caching harus dihindari:
   - Nilai data sangat sering berubah (write-heavy workload) di mana frekuensi mutasi > frekuensi baca, memicu banjir invalidation event yang membebani CPU service pod.
   - Ukuran entitas data sangat besar dan tidak terprediksi, yang dapat memicu Garbage Collection (GC) pauses panjang pada heap aplikasi runtime (misal: Java/Go).
10. Pada Dual-Writing, jika terjadi kegagalan jaringan setelah pod menulis ke database tetapi sebelum sempat menghapus cache, cache akan terus menyimpan data basi (*stale*). Melalui CDC, penangkapan event terjadi langsung pada level commit WAL engine database secara transaksional; cache invalidation hanya dipicu jika dan hanya jika database sudah sukses memvalidasi commit transaksi, menghilangkan anomali split-state akibat kegagalan parsial aplikasi.

#### Panduan Jawaban Bagian 3
11. **Akar Masalah**: Pola *Hotspot Entity Caching*. Data status selebriti tersebut memiliki ukuran respons/komentar besar yang di-*load* ke dalam heap pod lokal tanpa batas ukuran (*unbounded caching*). Ketika pod kehabisan alokasi RAM, Go runtime / JVM mengalami saturasi GC hingga di-*kill* oleh Linux OOM Killer.  
    **Solusi**:
    - Terapkan hard-limit memory pada library L1 cache (gunakan cache allocator berbasis off-heap atau *bounded memory footprint* seperti Ristretto).
    - Lakukan segmentasi data: simpan konten status selebriti hanya pada distributed L2, sedangkan L1 hanya menyimpan penanda referensi ID atau metadata ringkas.
12. **Analisis Masalah**: Query berbasis rentang tanggal pada arsitektur hash sharding `account_id` memicu *Full Cluster Scatter-Gather*, membebani seluruh node shard untuk membaca data yang bukan domain spesialisasi partisi mereka.  
    **Solusi Arsitektural**: Implementasikan pola **CQRS (Command Query Responsibility Segregation)**. Jadikan database sharded sebagai Write-Optimized Primary Store. Gunakan CDC (Debezium/Kafka) untuk memproyeksikan seluruh perubahan data akun secara asinkron ke **Search Index Platform** terpusat (seperti Elasticsearch/OpenSearch) atau Database Analitikal Kolumnar (ClickHouse). Eksekusi query pencarian rentang tanggal langsung ke index engine tersebut.
13. **Solusi Fencing Token**:
    - Setiap kali distributed lock diakuisisi di Redis, kembalikan nilai nomor urut transaksi monotonik yang selalu bertambah (*monotonically increasing integer*), misal: Token `v104`.
    - Saat melakukan penulisan ke database shard, sertakan fencing token dalam query:
      `UPDATE balances SET amount = 500, last_token = 104 WHERE account_id = 'A' AND last_token < 104;`
    - Jika thread lama yang mengalami latency mencoba melakukan penulisan menggunakan token basi (misal: Token `v103`), database akan menolak eksekusi karena nilai token tidak lagi valid, menjaga integritas data secara mutlak.

---

### 16. Summary

1. **Skalabilitas Data Tingkat Lanjut** menuntut eliminasi ketergantungan pada skala vertikal dengan beralih ke partisi horisontal (*sharding*). Pendekatan hashing deterministik berbasis cincin (*Consistent Hashing*) yang dipadukan dengan *Virtual Nodes* merupakan standar mutlak dalam mendistribusikan beban data secara seragam ke banyak node penyimpanan.
2. **Arsitektur Multi-Tier Caching** memecahkan dilema saturasi jaringan pada distributed cache tersentralisasi. Menggabungkan L1 in-process caching dengan distributed L2 caching memangkas latensi data ke ranah nanodetik, dengan syarat diimbangi protokol invalidasi berbasis CDC (Change Data Capture) untuk menjamin kekonsistenan state data di seluruh replika pod aplikasi.
3. **Mitigasi Anomali Beban Puncak (Thundering Herd / Stampede)** membutuhkan pendekatan berlapis: penggunaan algoritma probabilistik seperti **XFetch** yang memicu refresh data sebelum TTL habis, serta pemanfaatan pola konkurensi **SingleFlight** untuk memastikan hanya satu koneksi komputasi yang diizinkan membebani primary backing database.
4. **Tidak Ada Solusi Universal**: Setiap keputusan rekayasa data partisi dan caching membawa trade-off nyata antara konsistensi data (*Consistency*), ketersediaan (*Availability*), latensi komputasi, dan kompleksitas operasional infrastruktur. Implementasi skala enterprise selalu dibangun di atas pengamatan telemetri metrik yang terukur, pola fallback yang defensif, serta mitigasi kegagalan node secara otomatis.