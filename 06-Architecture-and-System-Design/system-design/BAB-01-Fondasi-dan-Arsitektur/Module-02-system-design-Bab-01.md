# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 01: Fondasi dan Arsitektur**  
**Jalur Pembelajaran: 06-Architecture-and-System-Design**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis & Mengatasi Dual-Write Anomaly:** Mengimplementasikan pola *Transactional Outbox* dan *Change Data Capture* (CDC) untuk menjamin konsistensi atomik antara sistem basis data relasional dan *message broker* terdistribusi tanpa bergantung pada 2-Phase Commit (2PC).
2. **Merancang Sistem Partisi Tingkat Lanjut:** Mengimplementasikan algoritma *Consistent Hashing* lengkap dengan *Virtual Nodes* (*vnodes*) untuk meminimalkan redistribusi data saat penskalaan horizontal dinamis pada kluster penyimpanan.
3. **Mengeliminasi Kegagalan Kaskade Caching:** Menerapkan strategi mitigasi *Cache Stampede* menggunakan algoritma probabilistik *XFetch* (*Optimal Probabilistic Early Expiration*) dan *Singleflight Mutex Locking*.
4. **Membangun Pertahanan Layanan Berbasis Toleransi Kesalahan (*Fault Tolerance*):** Mengintegrasikan *Distributed Rate Limiting* berbasis Redis Lua script (*Sliding Window Counter*) dan *Adaptive Concurrency Limiting* untuk mencegah saturasi sumber daya (*resource exhaustion*).
5. **Mengevaluasi Trade-off Arsitektural Skala Produksi:** Memilih kombinasi pola replikasi, isolasi transaksi, dan topologi partisi secara objektif berdasarkan batasan latensi, throughput, konsistensi (*PACELC Theorem*), dan biaya infrastruktur.

---

## 2. Prerequisite

Peserta wajib menguasai:
- **Konsep Jaringan & Protokol:** TCP handshake, connection pooling, HTTP/2, multiplexing, dan gRPC streaming.
- **Internal Basis Data:** Struktur data B-Tree vs. LSM-Tree, WAL (*Write-Ahead Logging*), *Multi-Version Concurrency Control* (MVCC), dan level isolasi transaksi ANSI SQL.
- **Primitif Konkurensi:** Mutex, read/write locks, atomic operations, channels/goroutines, atau thread worker pools.
- **Fondasi Modul 01:** Teorema CAP/PACELC, perbedaan *Scalability vs Elasticity*, dan pembagian layer aplikasi (*Presentation, Application, Data Layer*).

---

## 3. Concept & Internal Architecture

Dalam arsitektur terdistribusi skala produksi (*hyper-scale*), subsistem tidak dapat dipandang sebagai komponen terisolasi. Seluruh layanan harus dirancang dengan asumsi bahwa perangkat keras, jaringan, dan dependensi eksternal **pasti akan gagal** (*Design for Failure*).

```
+-----------------------------------------------------------------------------------+
|                            EDGE TIER (Anycast / Cloudflare)                       |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                        API GATEWAY & TRAFFIC SHAPING                              |
|  - Distributed Rate Limiter (Redis Sliding Window Lua Script)                     |
|  - Adaptive Concurrency Limiter (Vegas / CoDel Algorithm)                         |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                       APPLICATION TIER (Stateless Go/Java)                        |
|  +-----------------------------------------------------------------------------+  |
|  | Request Context & Tracing (W3C TraceContext)                                |  |
|  | +-------------------------------------------------------------------------+ |  |
|  | | Singleflight Engine / XFetch Cache Layer                                | |  |
|  | +-------------------------------------------------------------------------+ |  |
|  | | Core Domain Engine (Idempotency Validator)                              | |  |
|  | +-------------------------------------------------------------------------+ |  |
|  | | Transactional Outbox Writer (Atomic Local Commit)                       | |  |
|  | +-------------------------------------------------------------------------+ |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
                     │                                         │
                     ▼                                         ▼
+------------------------------------+   +------------------------------------------+
|            DATA STORAGE            |   |               CACHE CLUSTER              |
|  - Primary PostgreSQL (WAL)        |   |  - Consistent Hash Ring (Virtual Nodes)  |
|  - Outbox Table                    |   |  - Valkey / Redis Cluster (In-Memory)    |
+------------------------------------+   +------------------------------------------+
                     │
                     ▼
+------------------------------------+
|    CHANGE DATA CAPTURE (DEBEZIUM)  |
+------------------------------------+
                     │
                     ▼
+------------------------------------+
|      EVENT BROKER (APACHE KAFKA)   |
+------------------------------------+
```

### 3.1. Advanced Data Partitioning: Consistent Hashing with Virtual Nodes
Pemberian partisi berbasis modulo konvensional ($hash(key) \pmod N$) menyebabkan perpindahan hampir 100% data ketika jumlah node $N$ berubah. *Consistent Hashing* memetakan data dan node ke dalam *ring* numerik 32-bit atau 64-bit ($[0, 2^{32}-1]$ atau $[0, 2^{64}-1]$).

Masalah utama dari implementasi cincin (*ring*) dasar adalah **Hotspotting** atau ketidakseimbangan alokasi kunci (*non-uniform distribution*). Untuk mengatasi hal ini, diperkenalkan **Virtual Nodes (vnodes)**:
- Sebuah node fisik $Node_A$ direpresentasikan sebagai $k$ buah titik virtual: $Node_A\#1, Node_A\#2, \dots, Node_A\#k$.
- Standar industri menggunakan rentang $k = 100$ hingga $k = 256$ *vnodes* per instans fisik untuk mencapai variansi distribusi data $< 5\%$.
- Pencarian node penanggung jawab kunci dilakukan dalam kompleksitas waktu amortisasi $\mathcal{O}(\log(N \times k))$ menggunakan operasi pencarian biner (*binary search / upper bound*) pada struktur data *Array* terurut atau *Red-Black Tree*.

### 3.2. Cache Stampede Mitigation: Probabilistic Early Expiration (XFetch)
Fenomena *Cache Stampede* (dikenal juga sebagai *thundering herd* atau *dogpiling*) terjadi saat kunci cache yang sangat populer (*hot key*) kedaluwarsa secara mendadak. Ribuan permintaan paralel mendapati *cache miss* bersamaan dan mengeksekusi komputasi/kueri berat ke basis data primer secara simultan, memicu saturasi CPU dan koneksi basis data.

Pola mitigasi standar terbagi dua:
1. **Singleflight (Mutex Locking):** Menekan eksekusi kueri duplikat dalam satu instans komputasi lokal, sehingga hanya 1 proses pekerja yang mengakses DB sementara yang lain menunggu di channel/kondisi memori.
2. **Algoritma XFetch (Optimal Probabilistic Early Expiration):** Menghitung probabilitas penulisan ulang cache *sebelum* waktu kedaluwarsa aktual tiba berdasarkan waktu komputasi basis data ($ComputeTime$).

Formula XFetch:
$$\Delta - \beta \times \delta \times \ln(rand()) > TTL_{remaining}$$
* $\Delta$: Waktu komputasi yang dibutuhkan untuk menghasilkan nilai cache ($ComputeTime$).
* $\beta$: Nilai agresivitas regenerasi cache ($\beta > 0$, default = 1.0).
* $\delta$: Waktu eksekusi aktual kueri terakhir.
* $rand()$: Nilai floating-point acak terdistribusi seragam di rentang $(0, 1]$.
* $TTL_{remaining}$: Waktu sisa sebelum kunci kedaluwarsa secara permanen.

Jika kondisi bernilai benar, satu *worker* secara proaktif melakukan kueri ulang ke basis data dan memperbarui cache tanpa memblokir pembaca lain yang masih membaca data lama (*stale data*).

### 3.3. Dual-Write Problem & Transactional Outbox Pattern
Ketika arsitektur sistem membutuhkan persistensi data ke basis data relasional (misal: PostgreSQL) dan publikasi event ke message streaming (misal: Apache Kafka), pendekatan naif berupa *Dual-Write* berurutan selalu rentan kegagalan parsial:

```
[Service Core] ──(1. Save to DB)──> [PostgreSQL]  (SUCCESS)
      │
      └──(2. Network Partition / Crash)──X──> [Kafka Broker] (FAILED)
```

Hasil: Basis data mencatat data baru, namun sistem terdistribusi lainnya tidak menerima event pembaruan (data hilang dari ekosistem event-driven). Pola 2-Phase Commit (2PC) / XA Transaction dihindari di skala produksi karena latensi tinggi dan ketidakmampuan sebagian besar *broker* modern (seperti Apache Kafka) mendukung protokol XA secara efisien.

**Solusi Arsitektur: Transactional Outbox + CDC Engine**
1. Aplikasi menulis *entity state* dan mencatat *event payload* ke dalam tabel basis data yang sama (`outbox_events`) di dalam **satu transaksi ACID lokal tunggal**.
2. Mesin Change Data Capture (misal: Debezium) membaca Write-Ahead Log (WAL) basis data secara asinkron tanpa membebani performa engine SQL kueri.
3. Debezium mempublikasikan pesan ke Apache Kafka dengan jaminan *at-least-once delivery*.
4. Konsumen menerapkan *Idempotent Consumer Pattern* dengan melacak `event_id` pada *storage* transaksional konsumen.

---

## 4. Why & What

| Dimensi | Pendekatan Monolitik / Naif | Arsitektur Produksi Terdistribusi Lanjutan |
| :--- | :--- | :--- |
| **Cache Expiration** | Fixed TTL dengan *hard invalidation*. Rentan *thundering herd* dan lonjakan latensi P99. | Probabilistic Early Expiration (XFetch) + In-Flight Mutex Coalescing (Singleflight). |
| **Data Partitioning** | Modulo Sharding ($ID \pmod N$). Memerlukan downtime masif saat penambahan kapasitas penyimpanan. | Consistent Hashing Ring dengan Virtual Nodes (100–256 vnodes) untuk redistribusi seragam data tanpa downtime. |
| **Penyimpanan State & Event** | Dual-write langsung dari aplikasi ke DB dan Message Broker. Rentan inkonsistensi saat kegagalan jaringan. | Transactional Outbox via Engine WAL Log-Tailing (Debezium/Kafka Connect). Terjamin konsisten secara eventual. |
| **Perlindungan Beban** | Tidak ada rate limiter atau rate limiter statis berbasis IP memory tunggal. | Multi-tier Rate Limiting: Sliding Window Counter via Redis Cluster + Adaptive Concurrency Limiting di level RPC. |

---

## 5. How (Workflow Detail)

Alur kerja end-to-end pemrosesan permintaan transaksi finansial berskala tinggi:

```
[Client] 
   │ 
   │ 1. HTTP POST /api/v1/orders (Idempotency-Key: UUID)
   ▼
[API Gateway]
   │ 2. Evaluasi Redis Sliding Window Rate Limit (Atomic Lua Script)
   ├─► [Limit Exceeded] ──> Kembalikan HTTP 429 Too Many Requests
   │
   │ 3. Forward request ke Core Service Pod
   ▼
[Order Service Pod]
   │ 4. Validasi Idempotency-Key pada Redis Cluster
   ├─► [Key Exists] ──> Kembalikan Cached HTTP Response langsung
   │
   │ 5. Baca status inventaris (Singleflight + XFetch Cache Layer)
   │    Cache Miss -> Eksekusi kueri read-replica DB -> Simpan ke Valkey Cache
   │
   │ 6. Buka Local DB Transaction (BEGIN TRANSACTION):
   │    a. INSERT INTO orders (...) VALUES (...);
   │    b. UPDATE inventory SET stock = stock - 1 WHERE item_id = ?;
   │    c. INSERT INTO outbox_events (event_id, payload, created_at) VALUES (...);
   │    COMMIT; (ACID transaction guarantees atomicity)
   │
   │ 7. Return HTTP 201 Created ke Client (Latensi P99 < 45ms)
   ▼
[PostgreSQL WAL Log Engine]
   │ 8. Debezium Engine membaca PostgreSQL WAL stream
   ▼
[Debezium CDC]
   │ 9. Ekstraksi event dari WAL dan publish ke Kafka Partition
   ▼
[Apache Kafka: topic 'order-events']
   │ 10. Polling event secara paralel oleh Payment, Fulfillment, dan Analytics Service
   ▼
[Downstream Consumer]
   │ 11. Cek idempotensi lokal (SELECT 1 FROM processed_events WHERE event_id = ?)
   │ 12. Proses mutasi bisnis downstream
   │ 13. Simpan event_id ke processed_events
   │ 14. Commit Kafka Offset
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Sistem Perbankan Fisik Modern vs Tradisional
1. **Consistent Hashing dengan Virtual Nodes:** Seperti sistem antrean bank global. Daripada menugaskan nasabah berdasarkan angka terakhir KTP secara kaku (modulo), nasabah masuk ke sebuah aula sirkular (*ring*). Setiap loket teller memiliki beberapa papan panggilan (*virtual nodes*) yang tersebar rata di sepanjang aula. Jika 1 teller baru ditambahkan, ia hanya mengambil sebagian kecil antrean dari teller-teller terdekatnya, bukan merombak antrean seluruh bank.
2. **Transactional Outbox:** Menyetor uang di teller dan meminta teller mengirimkan surat konfirmasi ke pihak ketiga. Teller tidak menelepon kantor pos saat Anda menunggu. Teller mencatat mutasi rekening Anda dan memasukkan surat instruksi ke dalam kotak fisik "Keluar" (*Outbox*) di mejanya dalam satu gerakan. Petugas kurir (*CDC*) datang secara independen mengambil isi kotak dan membawanya ke kantor pos (*Kafka*).

```
                      CONSISTENT HASHING RING DENGAN VNODES
                                
                                     Node_A#1 (0)
                                 . - ~ ~ ~ - .
                             .                   .
                     Node_C#3                     Node_B#1
                   .                                 .
               Node_B#2                               Node_A#2
              .                                         .
             .             Key "user_98124"              .
            Node_C#1       -----> [Map to Node_B#3]       Node_C#2
             .                                           .
              .                                         .
               Node_A#3                               Node_B#3
                   .                                 .
                     Node_C#4                     Node_A#4
                             .                   .
                                 . - ~ ~ ~ - .
                                     Node_B#4
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Consistent Hashing Ring Sederhana (Go)

```go
package main

import (
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"sort"
	"strconv"
)

type HashRing struct {
	vnodes   int
	ring     []uint32
	nodesMap map[uint32]string
}

func NewHashRing(vnodes int) *HashRing {
	return &HashRing{
		vnodes:   vnodes,
		nodesMap: make(map[uint32]string),
	}
}

func (h *HashRing) hash(key string) uint32 {
	hasher := sha256.New()
	hasher.Write([]byte(key))
	digest := hasher.Sum(nil)
	return binary.BigEndian.Uint32(digest[:4])
}

func (h *HashRing) AddNode(node string) {
	for i := 0; i < h.vnodes; i++ {
		vnodeKey := node + "#" + strconv.Itoa(i)
		hashVal := h.hash(vnodeKey)
		h.ring = append(h.ring, hashVal)
		h.nodesMap[hashVal] = node
	}
	sort.Slice(h.ring, func(i, j int) bool { return h.ring[i] < h.ring[j] })
}

func (h *HashRing) GetNode(key string) string {
	if len(h.ring) == 0 {
		return ""
	}
	hashVal := h.hash(key)
	idx := sort.Search(len(h.ring), func(i int) bool {
		return h.ring[i] >= hashVal
	})
	if idx == len(h.ring) {
		idx = 0
	}
	return h.nodesMap[h.ring[idx]]
}

func main() {
	hr := NewHashRing(3)
	hr.AddNode("192.168.1.10:6379")
	hr.AddNode("192.168.1.11:6379")
	hr.AddNode("192.168.1.12:6379")

	keys := []string{"session_usr_1", "order_idx_99", "payment_payload_772"}
	for _, k := range keys {
		fmt.Printf("Key [%s] dialokasikan ke Node: %s\n", k, hr.GetNode(k))
	}
}
```

---

### 7.2. Practical Example: Production-Ready Rate Limiter & Singleflight Cache Mitigation

Berikut adalah implementasi Go tingkat produksi menggunakan *Distributed Sliding Window Counter* via Redis Lua Script, dipadukan dengan *Singleflight Pattern* untuk mencegah *Cache Stampede*:

```go
package main

import (
	"context"
	"crypto/rand"
	"errors"
	"fmt"
	"math/big"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"golang.org/x/sync/singleflight"
)

// Sliding Window Counter Lua Script (Atomic Execution)
const slidingWindowLua = `
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

local clearBefore = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, clearBefore)

local currentRequests = redis.call('ZCARD', key)
if currentRequests < limit then
    local randVal = ARGV[4]
    redis.call('ZADD', key, now, now .. '-' .. randVal)
    redis.call('PEXPIRE', key, window)
    return 1
else
    return 0
end
`

type ProductionResilienceLayer struct {
	redisClient *redis.Client
	group       singleflight.Group
	luaHash     string
}

func NewProductionResilienceLayer(rdb *redis.Client) (*ProductionResilienceLayer, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	hash, err := rdb.ScriptLoad(ctx, slidingWindowLua).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to pre-load Redis Lua script: %w", err)
	}

	return &ProductionResilienceLayer{
		redisClient: rdb,
		luaHash:     hash,
	}, nil
}

// AllowRequest mengeksekusi rate limiting terdistribusi berbasis sliding window.
func (p *ProductionResilienceLayer) AllowRequest(ctx context.Context, clientID string, limit int64, window time.Duration) (bool, error) {
	now := time.Now().UnixMilli()
	randInt, _ := rand.Int(rand.Reader, big.NewInt(1000000))
	key := fmt.Sprintf("ratelimit:%s", clientID)

	res, err := p.redisClient.EvalSha(ctx, p.luaHash, []string{key}, now, window.Milliseconds(), limit, randInt.String()).Result()
	if err != nil {
		return false, fmt.Errorf("redis execution error: %w", err)
	}

	allowed, ok := res.(int64)
	if !ok {
		return false, errors.New("invalid lua return type assertion")
	}

	return allowed == 1, nil
}

// FetchDataWithStampedeProtection memanfaatkan Singleflight mutex untuk menahan stampede.
func (p *ProductionResilienceLayer) FetchDataWithStampedeProtection(
	ctx context.Context,
	key string,
	ttl time.Duration,
	dbFetchFunc func(context.Context) (string, error),
) (string, error) {
	cacheKey := fmt.Sprintf("data:%s", key)

	// 1. Coba baca dari Cache
	val, err := p.redisClient.Get(ctx, cacheKey).Result()
	if err == nil {
		return val, nil
	} else if !errors.Is(err, redis.Nil) {
		// Log cache error, fallback langsung ke DB
		fmt.Printf("[WARN] Cache read failed: %v. Fallback ke basis data.\n", err)
	}

	// 2. Cache Miss: Terapkan Singleflight Coalescing
	// Semua goroutine dengan key yang sama akan menunggu eksekusi worker pertama
	v, err, _ := p.group.Do(key, func() (interface{}, error) {
		// Worker pertama mengambil data dari basis data primer
		dbData, dbErr := dbFetchFunc(ctx)
		if dbErr != nil {
			return nil, dbErr
		}

		// Set data ke Redis secara asinkron atau sinkron dengan timeout aman
		setCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()

		if errSet := p.redisClient.Set(setCtx, cacheKey, dbData, ttl).Err(); errSet != nil {
			fmt.Printf("[ERROR] Gagal menyimpan data ke cache: %v\n", errSet)
		}

		return dbData, nil
	})

	if err != nil {
		return "", err
	}

	return v.(string), nil
}

func main() {
	rdb := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
	})
	defer rdb.Close()

	layer, err := NewProductionResilienceLayer(rdb)
	if err != nil {
		fmt.Printf("Init resilience layer error: %v\n", err)
		return
	}

	ctx := context.Background()

	// Skenario 1: Evaluasi Rate Limiter
	clientID := "tenant_id_enterprise_abc"
	for i := 1; i <= 5; i++ {
		allowed, _ := layer.AllowRequest(ctx, clientID, 3, 5*time.Second)
		fmt.Printf("Permintaan #%d: Diizinkan? %t\n", i, allowed)
	}

	// Skenario 2: Cache Stampede Simultan (20 goroutine meminta kunci yang sama)
	var wg sync.WaitGroup
	productID := "prod_sku_high_demand_88"

	dbHitCount := 0
	var dbMu sync.Mutex

	mockDBFetch := func(c context.Context) (string, error) {
		dbMu.Lock()
		dbHitCount++
		dbMu.Unlock()
		time.Sleep(100 * time.Millisecond) // Simulasi I/O basis data yang berat
		return `{"sku": "prod_sku_high_demand_88", "stock": 42}`, nil
	}

	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			data, err := layer.FetchDataWithStampedeProtection(ctx, productID, 10*time.Second, mockDBFetch)
			if err != nil {
				fmt.Printf("Worker %d error: %v\n", workerID, err)
				return
			}
			if workerID == 0 {
				fmt.Printf("Worker 0 mendapatkan data: %s\n", data)
			}
		}(i)
	}

	wg.Wait()
	fmt.Printf("Total hit basis data fisik: %d kali (Ekspektasi: 1)\n", dbHitCount)
}
```

---

## 8. Real World Case Study: E-Commerce Flash Sale Engine (500,000 QPS)

### 8.1. Konteks Bisnis & Beban Puncak
Sebuah platform regional menggelar *Midnight Flash Sale* untuk unit smartphone dengan persediaan 1.000 unit. Sistem mengalami lonjakan lalu lintas dari kondisi normal 20.000 QPS menjadi 500.000 QPS dalam rentang waktu 3 detik tepat pada pukul 00:00:00 UTC.

### 8.2. Titik Kegagalan Awal (*Root Causes*)
1. **Database Connection Depletion:** 500.000 koneksi bersamaan mencoba menjalankan `SELECT stock FROM inventory WHERE item_id = 1 FOR UPDATE`. Koneksi PostgreSQL pool (kapasitas maksimal 2.000 koneksi) habis dalam 120 milidetik, memicu error `pq: sorry, too many clients already`.
2. **Dual-Write Inconsistency:** Sistem penanganan order mencatat order ke tabel SQL lalu mengirim event pemotongan saldo ke Kafka. Ketika pod mati akibat *Out-Of-Memory* (OOM), order tercatat di DB tetapi event Kafka tidak pernah terbit, menghasilkan status transaksi menggantung (*orphan transaction*).
3. **Redis Hotspot Saturation:** Kunci Redis `stock:flash_item_1` dialokasikan ke 1 node tunggal pada Redis Cluster. Throughput maksimum jaringan 1 node (sekitar 90.000 QPS per core) terlampaui, menyebabkan pemutusan koneksi TCP secara sporadis.

### 8.3. Solusi Remediasi Arsitektur Produksi
```
                               500,000 QPS
                                    │
                                    ▼
       [Cloudflare Anycast] -> [Envoy Edge Gateways (Rate Limited)]
                                    │
                                    ▼
           [Key Splitter: stock:flash_item_1_{1..16}]
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       ▼                            ▼                            ▼
[Redis Pod 1]                [Redis Pod 2]                [Redis Pod 3]
 (Shard 1-5)                  (Shard 6-10)                 (Shard 11-16)
       │                            │                            │
       └────────────────────────────┼────────────────────────────┘
                                    │ (DECR Atomic)
                                    ▼
                 [Stock Validated: Async Queue (Kafka)]
                                    │
                                    ▼
       [Transactional Outbox Processing Engine (Debezium + PG)]
```

1. **Sub-Key Partitioning (Hot-Key Deconstruction):** Kunci tunggal `stock:flash_item_1` dipecah menjadi 16 sub-kunci: `stock:flash_item_1_shard_{1..16}`. Permintaan dari pengguna didistribusikan secara pseudorandom atau berbasis `hash(user_id) % 16`. Melalui teknik ini, beban 500.000 QPS tersebar merata ke 16 instans Redis terpisah (~31.250 QPS per node), berada di bawah batas jenuh CPU Redis.
2. **Atomic Inventory Decrement via Lua:** Operasi pengurangan stok tidak lagi menggunakan kueri SQL `SELECT FOR UPDATE`, melainkan dieksekusi secara in-memory melalui Redis script:
   ```lua
   local stock = redis.call('GET', KEYS[1])
   if stock and tonumber(stock) > 0 then
       redis.call('DECR', KEYS[1])
       return 1
   end
   return 0
   ```
3. **Transactional Outbox Engine via Debezium:** Pesanan yang lolos reservasi Redis diproses ke PostgreSQL menggunakan *batch insert* lokal dengan Outbox record. Debezium menangkap mutasi WAL secara real-time dan menyalurkannya ke Kafka topic dengan jaminan latensi propagasi $\le 80$ milidetik.
4. **Hasil Pengujian Puncak:** Latensi P99 menurun dari 8.500 ms (timeout) menjadi 32 ms. Kegagalan pesanan akibat *race condition* berkurang menjadi 0%.

---

## 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian & Batasan | Mitigasi / Pertimbangan Biaya |
| :--- | :--- | :--- | :--- |
| **Virtual Nodes (Consistent Hashing)** | Distribusi beban merata ($< 5\%$ deviasi beban antar node); zero-downtime rebalancing. | Jejak memori metadata cincin (*ring lookup*) bertambah di setiap klien; kompleksitas algoritma pencarian biner. | Batasi jumlah *vnode* antara 100–256. Hindari ukuran ring raksasa di memori instans terbatas. |
| **Transactional Outbox + CDC** | Menjamin atomisitas 100% tanpa locking lintas sistem terdistribusi; tidak memerlukan koordinasi 2PC. | Menambah latensi propagasi event (*eventual consistency*); operasional CDC (Debezium/Kafka Connect) kompleks. | Terapkan monitoring lag WAL Postgres dan metrik lag offset Kafka secara ketat. |
| **Singleflight Coalescing** | Mengeliminasi *Cache Stampede* internal satu pod; beban basis data menurun hingga 99% saat lonjakan. | Hanya efektif dalam 1 pod instans. Jika terdapat 100 pod, tetap terdapat 100 kueri ke basis data secara bersamaan. | Kombinasikan dengan layer cache terdistribusi dan *Probabilistic Early Expiration* (XFetch). |
| **Redis Sliding Window Lua** | Presisi rate limiting akurat hingga resolusi milidetik; atomik tanpa *race conditions*. | Konsumsi memori lebih tinggi dibanding *Token Bucket* karena menyimpan timestamp setiap permintaan dalam sorted set. | Gunakan TTL pendek (sesuai window size) dan terapkan *Token Bucket* jika jendela waktu bernilai jam atau hari. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Common Mistakes
1. **Unbounded In-Memory Channels / Buffers:** Menggunakan channel Go tanpa batas (*unbuffered/infinite buffer*) untuk antrean Outbox internal. Ketika basis data melambat, channel menyerap jutaan objek hingga pod mati terkena OOM (*Out Of Memory Killer*).
2. **Cache-Aside Anti-Pattern (TTL Synchronization):** Mengatur TTL cache sama persis untuk jutaan entitas dalam batch yang sama, memicu *Mass Cache Eviction* serentak pada detik ke-N.
3. **Missing Idempotency Key Cleanup:** Menyimpan kunci idempotensi secara permanen di basis data tanpa strategi *TTL-based purging*, mengakibatkan ukuran tabel indeks meledak hingga ratusan gigabyte.
4. **Redis Lua Script Long-Running Execution:** Menulis script Lua yang kompleks dengan iterasi ribuan elemen (`SMEMBERS`, `HGETALL`). Karena Redis bersidat *single-threaded*, seluruh lalu lintas sistem terhenti (*freeze*) selama script berjalan.

### 10.2. Production Troubleshooting Runbook

#### Skenario: Redis Hotkey Degraded & Connection Pool Saturation
```
                       INDIKASI INSIDEN
   P99 Latency Melonjak (> 2000ms) + Redis Command Timeouts
                              │
                              ▼
               [Langkah 1: Identifikasi Kunci]
      Eksekusi: redis-cli --hotkeys atau redis-cli MONITOR
      Temukan apakah ada kunci tunggal mendominasi lalu lintas
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
       [Kunci Ditemukan]              [Beban Merata Tapi QPS Puncak]
             │                                 │
             ▼                                 ▼
 [Langkah 2A: Aktifkan Read-Replica] [Langkah 2B: Circuit Breaker]
  Arahkan pembacaan ke replica node   Buka Circuit Breaker via Envoy/Hystrix
  atau aktifkan local pod caching     Degradasi fitur: sajikan fallback data
             │                                 │
             └────────────────┬────────────────┘
                              ▼
              [Langkah 3: Mitigasi Struktural]
  1. Implementasikan Sub-Key Partitioning (Key_{1..N})
  2. Tambahkan Singleflight pada pod level
  3. Aktifkan Adaptive Rate Limiting di Edge
```

---

## 11. Best Practices (Production Checklist)

### Reliability & Resiliency
- [ ] Terapkan batas *timeout* ketat di setiap layer pemanggilan jaringan: Connection Timeout (maks 500ms), Read/Write Timeout (maks 2s).
- [ ] Terapkan pola *Exponential Backoff with Full Jitter* untuk mekanisme *retry* guna mencegah pembebanan berulang sistem hilir.
- [ ] Pastikan seluruh mutasi basis data memiliki kolom penjamin idempotensi (misal: `idempotency_key` dengan *unique constraint*).
- [ ] Pisahkan connection pool untuk operasi kueri intensif analitik (*Read-Replica*) dan transaksi mutasi utama (*Primary Writer*).

### Observability & Metrics
- [ ] Rekam metrik SLI/SLO: Latensi (P50, P95, P99), Error Rate (HTTP 5xx), Throughput (QPS), dan Saturasi Koneksi Basis Data.
- [ ] Propagasi `traceparent` (W3C Trace Context) di seluruh header protokol HTTP/gRPC dan metadata event Kafka.
- [ ] Aktifkan *Alerting* jika lag WAL replication PostgreSQL > 100MB atau offset lag Kafka > 10.000 records selama 2 menit.

### Storage & Cache Hygiene
- [ ] Tambahkan variasi acak (*jitter*) sebesar 10%–20% pada semua TTL cache untuk mencegah kedaluwarsa serentak.
- [ ] Hindari memanggil perintah berbiaya algoritma $\mathcal{O}(N)$ pada Redis di lingkungan produksi (`KEYS`, `FLUSHALL`, `HGETALL` skala besar).
- [ ] Konfigurasikan alokasi *Maxmemory Policy* Redis secara eksplisit (disarankan: `volatile-lru` atau `allkeys-lru`).

---

## 12. Hands-on Practice

Buat dan jalankan infrastruktur uji ketahanan terdistribusi di folder `hands-on/m02/`.

### Struktur File Direktori
```
hands-on/m02/
├── docker-compose.yml
├── go.mod
├── go.sum
└── main.go
```

### Langkah 1: Siapkan `docker-compose.yml`
```yaml
version: '3.8'

services:
  redis:
    image: redis:7.2-alpine
    container_name: m02-redis
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 2s
      retries: 5

  postgres:
    image: postgres:16-alpine
    container_name: m02-postgres
    environment:
      POSTGRES_USER: engine_user
      POSTGRES_PASSWORD: engine_password
      POSTGRES_DB: core_db
    ports:
      - "5432:5432"
    command: ["postgres", "-c", "wal_level=logical"]
```

### Langkah 2: Inisialisasi Project Go
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init m02-resilience
go get github.com/redis/go-redis/v9
go get golang.org/x/sync/singleflight
```

### Langkah 3: Eksekusi Kode Pengujian Ketahanan
Salin kode dari **Seksi 7.2** ke file `hands-on/m02/main.go`.

### Langkah 4: Jalankan dan Evaluasi
```bash
# 1. Jalankan kontainer
docker-compose up -d

# 2. Pastikan layanan siap
docker-compose ps

# 3. Jalankan stress harness
go run main.go

# 4. Ekspektasi Output:
# Permintaan #1: Diizinkan? true
# Permintaan #2: Diizinkan? true
# Permintaan #3: Diizinkan? true
# Permintaan #4: Diizinkan? false
# Permintaan #5: Diizinkan? false
# Worker 0 mendapatkan data: {"sku": "prod_sku_high_demand_88", "stock": 42}
# Total hit basis data fisik: 1 kali (Ekspektasi: 1)
```

---

## 13. Exercise

### Tingkat 1 - Easy
Modifikasi implementasi `HashRing` pada Seksi 7.1 untuk menambahkan fitur penghapusan node (`RemoveNode(node string)`). Pastikan semua *virtual nodes* yang berasosiasi dengan node tersebut dihapus dari slice `ring` dan map `nodesMap`, serta array tetap terurut.
*Kriteria Penerimaan:* Tidak ada memory leak pada `nodesMap` dan operasi `GetNode()` mengarahkan kunci ke node tersisa secara benar.

### Tingkat 2 - Medium
Implementasikan fungsi verifikasi idempotensi berbasis Redis menggunakan format:
`SetNX(ctx, idempotencyKey, "PROCESSING", 10*time.Second)`
Buat alur penanganan tiga skenario:
1. Kunci baru: Lanjutkan pemrosesan bisnis dan update status ke `"COMPLETED"`.
2. Kunci sedang berjalan (`"PROCESSING"`): Tolak dengan error `409 Conflict / Request in progress`.
3. Kunci telah selesai (`"COMPLETED"`): Ambil payload hasil eksekusi sebelumnya dan kembalikan tanpa eksekusi ulang.

### Tingkat 3 - Hard
Rancang dan implementasikan struktur `AdaptiveRateLimiter` di Go yang mengukur latensi P99 dari downstream service secara dinamis. Jika latensi P99 melewati ambang batas 200 milidetik dalam jendela 10 detik terakhir, batas kapasitas request (*throughput limit*) harus diturunkan secara otomatis sebesar 20%. Jika latensi pulih ke bawah 100 milidetik, batas kapasitas dinaikkan bertahap sebesar 5% (*Additive Increase Multiplicative Decrease / AIMD*).

---

## 14. Challenge: Global Multi-Region Active-Active State Synchronization Engine

### Latar Belakang
Anda bertindak sebagai Principal Systems Architect pada platform pembayaran global yang beroperasi di 3 region: `ap-southeast-1` (Singapura), `us-east-1` (Virginia), dan `eu-central-1` (Frankfurt).

### Batasan Arsitektural & Persyaratan
1. **Zero Data Loss:** Transaksi saldo dompet (*wallet balances*) tidak boleh mengalami inkonsistensi ganda (*double-spending*) meskipun terjadi pemutusan koneksi WAN antar-region (*WAN Partition*).
2. **Latensi Transaksi Lokal:** Operasi *top-up* dan pembayaran reguler harus memiliki latensi commit lokal $\le 50$ milidetik.
3. **Partition Resolution:** Ketika partisi jaringan antar benua pulih, state di ketiga region harus mengalami rekonsiliasi (*reconciliation*) otomatis tanpa intervensi manual database administrator.
4. **Auditability:** Setiap mutasi wajib dapat dilacak secara linear menggunakan konsep *Conflict-Free Replicated Data Types (CRDTs)* atau algoritma konsensus terdistribusi yang dimodifikasi.

### Tugas Desain
Tuliskan dokumen analisis teknis arsitektur yang mendefinisikan:
- Pilihan primitif replikasi (State-based vs Operation-based CRDTs atau Spanner-like TrueTime architecture).
- Mekanisme penanganan anomali penulisan simultan di dua region berbeda pada akun yang sama.
- Desain skema basis data dan metadata pendukung (Vector Clocks / Lamport Timestamps).
- Mitigasi risiko *Split-Brain*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Mengapa modulo sharding ($hash(key) \pmod N$) tidak efisien untuk kluster dinamis?**
   - A. Karena algoritma modulo membutuhkan daya komputasi CPU yang tinggi.
   - B. Karena penambahan 1 node baru memaksa migrasi hampir seluruh kunci data ke node lain.
   - C. Karena operasi modulo hanya mendukung tipe data integer.
   - D. Karena modulo sharding tidak mendukung replikasi asinkron.
   *(Jawaban: B — Mengubah nilai $N$ akan mengubah hasil perhitungan untuk mayoritas kunci, memicu redistribusi data skala masif).*

2. **Apa peran utama Virtual Nodes pada algoritma Consistent Hashing?**
   - A. Meningkatkan kecepatan transfer jaringan data TCP.
   - B. Mengenkripsi identitas node di dalam memori.
   - C. Menghindari ketimpangan alokasi data (*hotspotting*) dan meratakan persebaran beban.
   - D. Menjamin transaksi basis data mematuhi standar ANSI ACID.
   *(Jawaban: C — Virtual nodes memetakan satu node fisik ke ratusan titik cincin untuk pemerataan probabilitas distribusi kunci).*

3. **Anomali apa yang diselesaikan secara langsung oleh Transactional Outbox Pattern?**
   - A. Kehilangan event pada Kafka akibat Dual-Write Failure saat pod aplikasi mengalami *crash*.
   - B. Kueri lambat akibat indeks B-Tree yang terfragmentasi.
   - C. Kegagalan autentikasi OAuth2 token.
   - D. Keterbatasan kapasitas penyimpanan pada disk lokal.
   *(Jawaban: A — Outbox pattern menjamin atomisitas lokal DB write dan event publishing tanpa dual-write naif).*

4. **Bagaimana algoritma Singleflight mencegah terjadinya Cache Stampede?**
   - A. Dengan menghapus kunci cache sebelum masa kedaluwarsa tiba.
   - B. Dengan menahan semua kueri konkuren pada instans yang sama dan hanya mengizinkan satu eksekusi ke sumber data primer.
   - C. Dengan mengubah basis data menjadi mode *Read-Only*.
   - D. Dengan menggandakan seluruh data cache ke memori lokal.
   *(Jawaban: B — Permintaan duplikat digabungkan (*coalesced*) sehingga hanya satu kueri yang dieksekusi ke basis data backend).*

5. **Apa fungsi dari penambahan 'Jitter' pada waktu TTL cache?**
   - A. Mengompresi ukuran payload data di memori.
   - B. Mencegah sejumlah besar kunci cache kedaluwarsa secara bersamaan yang dapat memicu lonjakan beban ke basis data.
   - C. Mempercepat serialisasi JSON ke binary.
   - D. Mengubah protokol HTTP/1.1 menjadi HTTP/2.
   *(Jawaban: B — Variasi acak mendistribusikan waktu kedaluwarsa merata di sepanjang sumbu waktu).*

### Bagian 2: Intermediate (5 Soal)
6. **Pada algoritma probabilistik XFetch, apa arti variabel $\beta$ (beta)?**
   - A. Ukuran memori buffer koneksi TCP.
   - B. Koefisien agresivitas regenerasi cache dini sebelum waktu kedaluwarsa aktual.
   - C. Jumlah virtual node dalam consistent hashing ring.
   - D. Batas toleransi latensi jaringan antar node.
   *(Jawaban: B — Nilai $\beta > 1$ membuat komputasi regenerasi dini terjadi lebih agresif; nilai $\beta < 1$ membuatnya lebih lambat).*

7. **Mengapa Redis Lua Scripting lebih dipilih untuk implementasi Distributed Rate Limiter dibanding serangkaian perintah Redis reguler dari aplikasi?**
   - A. Karena Lua script dieksekusi secara atomik di dalam satu thread Redis tanpa risiko *race condition* antar pembacaan dan penulisan.
   - B. Karena bahasa Lua memiliki performa kompilasi lebih cepat dibanding C.
   - C. Karena Lua script secara otomatis mereplikasi data ke sistem disk sekunder.
   - D. Karena penggunaan Lua mengurangi beban memori RAM Redis sebesar 50%.
   *(Jawaban: A — Eksekusi Lua di Redis bersifat atomik secara isolasi sehingga meniadakan intervensi perintah paralel lainnya selama script berjalan).*

8. **Apa kerugian terbesar penggunaan 2-Phase Commit (2PC) pada arsitektur microservices terdistribusi?**
   - A. Tidak mendukung protokol HTTP.
   - B. Bersifat *blocking*; latensi transaksi meningkat drastis seiring dependensi node terlambat (*coordinator failure & lock contention*).
   - C. Memerlukan skema basis data NoSQL.
   - D. Mengabaikan validasi tipe data payload.
   *(Jawaban: B — Fase prepare-commit menahan lock lokal pada semua partisipan, menurunkan throughput dan rentan terhadap kegagalan node koordinator).*

9. **Debezium memanfaatkan Write-Ahead Logging (WAL) untuk CDC. Apa keunggulan pendekatan ini dibanding *polling* berkala (`SELECT * FROM outbox WHERE processed = false`)?**
   - A. Tidak membutuhkan hak akses database superuser.
   - B. Polling berkala mengunci indeks tabel dan membebani query engine, sementara pembacaan WAL dilakukan secara asinkron tanpa *polling overhead*.
   - C. Polling berkala tidak dapat mendeteksi operasi INSERT.
   - D. WAL CDC hanya bisa memproses 10 event per detik.
   *(Jawaban: B — Log-tailing membaca stream byte disk terurut tanpa memicu beban kueri SQL parser dan locking indeks tabel).*

10. **Kapan implementasi Rate Limiter tipe *Sliding Window Log* mulai tidak efisien dan sebaiknya digantikan oleh *Sliding Window Counter* atau *Token Bucket*?**
    - A. Saat jendela waktu yang dipantau berada pada resolusi mikrodetik.
    - B. Saat volume transaksi per jendela waktu sangat tinggi, karena penyimpanan timestamp individual pada sorted set menghabiskan terlalu banyak memori.
    - C. Saat aplikasi hanya menggunakan satu pod instans.
    - D. Saat protokol komunikasi yang digunakan adalah gRPC.
    *(Jawaban: B — Sorted set menyimpan 1 entri per event permintaan; volume jutaan request akan memicu pemborosan alokasi memori RAM).*

### Bagian 3: Production Scenarios (3 Soal Kasus)

11. **Skenario Kasus 1:**  
    Sebuah pod microservice pembayaran menggunakan Redis Cluster untuk rate limiting. Saat terjadi gangguan jaringan parsial antar pod aplikasi dan Redis, latency p99 melonjak dari 15ms menjadi 2000ms, mengakibatkan seluruh *worker thread* HTTP pool habis (*thread exhaustion*). Langkah mitigasi arsitektur mana yang paling tepat untuk mengisolasi kegagalan ini?
    - A. Menghapus rate limiter dari arsitektur secara permanen.
    - B. Menerapkan *Circuit Breaker* dengan *Fail-Open Policy* yang memiliki batas timeout 50ms untuk operasi Redis Rate Limiter.
    - C. Memperbesar ukuran pool HTTP worker thread pod aplikasi menjadi 100.000 thread.
    - D. Mengubah Redis Cluster menjadi instans database MongoDB.
    *(Analisis Solusi: B — Circuit breaker mendeteksi kegagalan dependensi non-kritis dan mengaktifkan mode Fail-Open dalam batas timeout singkat, mencegah pemblokiran thread aplikasi utama).*

12. **Skenario Kasus 2:**  
    Sistem Anda menggunakan Debezium untuk menerbitkan event dari tabel Outbox PostgreSQL ke Kafka. Suatu hari, tim infrastruktur mendapati bahwa disk PostgreSQL penuh akibat file WAL membengkak puluhan gigabyte (*disk full incident*). Ditemukan bahwa Debezium pod mengalami *crash-loop* dan tidak dapat tersambung kembali. Apa penyebab langsung pembengkakan WAL tersebut?
    - A. PostgreSQL sengaja menahan file segment WAL karena *logical replication slot* milik Debezium belum mengonfirmasi pembacaan (*unacknowledged LSN*).
    - B. Tabel Outbox memiliki terlalu banyak indeks B-Tree.
    - C. Database PostgreSQL secara otomatis menduplikasi partisi saat mendeteksi pod crash.
    - D. Fitur Singleflight memblokir operasi checkpoint disk.
    *(Analisis Solusi: A — PostgreSQL mempertahankan seluruh segmen log WAL fisik selama replication slot aktif belum menandai commit LSN terakhir, guna mencegah hilangnya data bagi replika/CDC).*

13. **Skenario Kasus 3:**  
    Pada peluncuran produk global, sebuah kunci Redis (`global_config_data`) diakses 150.000 kali per detik. Kunci ini hanya berukuran 2KB, namun node Redis hosting kunci tersebut mengalami penggunaan CPU 100% dan *packet dropped*. Node lain pada cluster dalam kondisi idle (CPU < 10%). Pola apa yang harus diterapkan untuk menyeimbangkan beban ini secara instan tanpa rearsitektur basis data total?
    - A. Matikan Redis dan arahkan seluruh pembacaan konfigurasi ke PostgreSQL.
    - B. Terapkan *Local In-Memory Pod Cache* (misal: Ristretto/Go-Cache) dengan TTL sangat pendek (1-5 detik) atau replikasi kunci ke format *Read Shards* (`global_config_data_{1..N}`).
    - C. Naikkan batas memory limit Redis.
    - D. Hapus kunci tersebut dari cache agar dibaca langsung dari hard disk.
    *(Analisis Solusi: B — Hot key terkonsentrasi pada satu vnode/shard fisik. Local in-memory caching pada level pod menyerap pembacaan ekstrem tanpa perlu keluar melalui jaringan ke Redis).*

---

## 16. Summary

1. **Prinsip *Design for Failure*:** Kegagalan parsial pada sistem terdistribusi skala enterprise adalah keniscayaan statistik. Arsitektur tangguh tidak berasumsi komponen eksternal selalu tersedia, melainkan membatasi dampak kegagalan melalui teknik isolasi, limitasi konkurensi, dan degradasi elegan.
2. **Kedaulatan Konsistensi Transaksional:** Mengabaikan pola integrasi atomik seperti *Transactional Outbox* dan beralih ke *Dual-Write* naif dipastikan menimbulkan anomali status data. Integrasi WAL-based CDC dengan Kafka menyediakan fondasi konsistensi eventual yang kuat dan skalabel.
3. **Optimasi Partisi & Cache:** *Consistent Hashing* berbasis *Virtual Nodes* menjamin penskalaan horizontal tanpa anomali redistribusi beban. Perlindungan cache modern mengombinasikan *Singleflight Mutex* di level in-process dan algoritma probabilistik seperti *XFetch* untuk mengeliminasi fenomena *Cache Stampede*.
4. **Pertahanan Bertingkat (*Defense in Depth*):** Keberhasilan sistem menangani lonjakan beban bergantung pada keselarasan proteksi multi-tier: *Edge Rate Limiting*, *Adaptive Concurrency Limiting* internal, *Bounded Concurrency Queues*, serta *Circuit Breaker* dengan isolasi kegagalan yang presisi.