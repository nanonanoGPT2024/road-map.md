## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: API-ARCH-0701
* **Jalur Pembelajaran**: API Design, Architecture, & Enterprise Resiliency
* **Kategori**: 06-Architecture-and-System-Design
* **Tingkat Kesulitan**: Advanced / Senior Level
* **Prasyarat**: 
  * Pemahaman mendalam mengenai protokol HTTP/1.1, HTTP/2, dan gRPC.
  * Penguasaan arsitektur microservices terdistribusi dan jaringan berbasis TCP/IP.
  * Pengalaman operasional dengan *in-memory data store* (Redis/KeyDB) dan pemahaman eksekusi script atomik (Lua scripting).
  * Familiaritas dengan konsep multithreading, concurrency primitives (mutex, CAS/Compare-And-Swap), dan asynchronous I/O.
* **Estimasi Waktu Penyelesaian**: 8 – 10 Jam Pembelajaran Mandiri & Implementasi Lab
* **Versi Modul**: v2.4.0
* **Author**: Senior Technical Curriculum Architect

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara tuntas, peserta didik diharapkan mampu:

1. **Menganalisis & Mengimplementasikan Algoritma Rate Limiting Terdistribusi**
   * Membedakan karakteristik matematis, kompleksitas memori, serta runtime CPU dari *Token Bucket*, *Leaky Bucket*, *Fixed Window*, *Sliding Window Log*, dan *Sliding Window Counter*.
   * Mengimplementasikan algoritma *Sliding Window Counter* dan *Token Bucket* yang thread-safe dan atomik pada kluster terdistribusi menggunakan Redis dan Lua Scripting untuk mencegah race condition (*check-then-act*).

2. **Merancang Pola Ketahanan Sistem Tingkat Lanjut (Resiliency Patterns)**
   * Membangun *Circuit Breaker* adaptif berbasis rolling metrics (menggunakan model *State Machine*: Closed, Open, Half-Open) yang mencegah *cascading failures* lintas mikroservis.
   * Menghitung dan mengonfigurasi mekanisme *Adaptive Retries* dengan algoritma *Exponential Backoff* dan *Jitter* (Full Jitter, Equal Jitter, dan Decorrelated Jitter) guna meniadakan risiko *thundering herd problem*.

3. **Mengevaluasi & Menerapkan Strategi Backpressure**
   * Mengintegrasikan mekanisme mitigasi beban berbasis *push/pull stream backpressure* pada transport layer maupun application layer untuk mencegah degradasi performa akibat *buffer saturation* dan *Out-Of-Memory* (OOM) crash.
   * Menerapkan standar respons HTTP berbasis IETF (`429 Too Many Requests`, `503 Service Unavailable`, serta header `Retry-After`, `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            TRAFFIC CONTROL & SYSTEM RESILIENCY
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      │                                      │                                      │
┌─────▼──────────────┐             ┌─────────▼──────────┐                 ┌─────────▼──────────┐
│   TRAFFIC SHAPING  │             │  CIRCUIT BREAKING  │                 │ FAULT TOLERANCE &  │
│   & RATE LIMITING  │             │   (State Machine)  │                 │    BACKPRESSURE    │
└─────┬──────────────┘             └─────────┬──────────┘                 └─────────┬──────────┘
      │                                      │                                      │
      ├─ Token Bucket                        ├─ Closed (Normal Traffic)             ├─ Exponential Backoff
      ├─ Leaky Bucket                        ├─ Open (Fast-Fail, Drop)              ├─ Jitter Algorithms
      ├─ Sliding Window Log                  └─ Half-Open (Canary Probing)          │  ├─ Full Jitter
      ├─ Sliding Window Counter                                                     │  ├─ Equal Jitter
      │                                                                             │  └─ Decorrelated Jitter
      └─ Distributed Synchronization                                                └─ Reactive Backpressure
         ├─ Redis + Lua Atomicity                                                      ├─ TCP Window Flow Control
         └─ Concurrency Limits (Little's Law)                                          ├─ Reactive Streams (Pull)
                                                                                       └─ Client Throttling & 429
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

### 1. Anatomi Kegagalan Kaskade (Cascading Failures)
Dalam arsitektur *distributed microservices*, latensi adalah parasit laten yang jauh lebih mematikan dibandingkan *hard crash*. Ketika sebuah dependensi *downstream* (misal: Payment Gateway atau Database RDBMS) mengalami degradasi dan latensi responsnya naik dari $20\text{ ms}$ menjadi $5000\text{ ms}$, sistem pemanggil (*upstream*) akan menahan alokasi *thread/goroutine* serta koneksi soket HTTP/TCP lebih lama. 

Hal ini memicu:
* Habisnya alokasi *connection pool* dan *worker thread pool* pada *upstream service*.
* Penumpukan antrean memori internal (RAM) yang berujung pada *garbage collection pauses* yang ekstrem atau terminasi OS via *OOM Killer*.
* Dampak domino yang merambat ke edge API Gateway, menumbangkan seluruh platform digital (*total system outage*).

### 2. The Thundering Herd Problem
Kegagalan menangani *traffic spike* pasca-insiden (misal: restart serentak ribuan instance klien atau pemulihan *cache cluster*) memicu badai permintaan (*thundering herd*). Tanpa desinkronisasi berbasis *jitter* dan perlindungan *rate limiting*, kapasitas puncak sistem akan terlampaui seketika sebelum sistem sempat menghangatkan koneksi internal (*cache warming* atau JIT compile).

### 3. Keamanan Finansial dan Keadilan Multi-Tenant
API modern sering kali dihadapkan pada ancaman *resource starvation* oleh *noisy neighbors* (satu penyewa menguras kuota komputasi tenant lain), serangan DoS/DDoS pada level aplikasi (Layer 7), serta pembengkakan biaya infrastruktur tak terkontrol (*cloud bill explosion*) akibat *unbounded auto-scaling*. Kontrol lalu lintas deterministik adalah garis pertahanan pertama bagi operasional enterprise.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Definisi Formal Komponen Ketahanan Sistem

* **Rate Limiting**: Kebijakan restriktif untuk membatasi jumlah operasi yang diizinkan dilakukan oleh suatu entitas (berdasarkan API Key, IP, User ID, Client ID) dalam satuan waktu tertentu. Tujuannya adalah melindungi stabilitas ketersediaan layanan (*high availability*).
* **Traffic Shaping**: Mekanisme yang memodifikasi aliran paket/request agar sesuai dengan batas kapasitas target, sering kali dengan menunda (*buffering/smoothing*) request yang meluap daripada langsung menolaknya.
* **Circuit Breaker**: Pola proteksi proaktif yang membungkus pemanggilan fungsi jarak jauh (*remote calls*). Pola ini memonitor rasio kegagalan. Jika kegagalan menembus ambang batas (*threshold*), *circuit* berpindah ke status **Open**, langsung memutus pemanggilan ke dependensi yang rusak (*fail-fast*), dan mencegah sistem kehabisan sumber daya lokal.
* **Exponential Backoff & Jitter**: Algoritma komputasi durasi jeda retry di mana durasi tunggu digandakan secara eksponensial pada setiap iterasi kegagalan, dan ditambahkan derau stokastik (*random noise/jitter*) untuk mendiversifikasi waktu tembak antrean klien.
* **Backpressure**: Respon pertahanan sistem downstream yang mengisyaratkan kepada produsen pesan (upstream) bahwa laju transmisi data melebihi laju kapasitas pemrosesan data, memaksa produsen menurunkan kecepatan atau menghentikan alirannya sementara.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Perbandingan Matematis Algoritma Rate Limiting

| Algoritma | Kompleksitas Waktu | Kompleksitas Ruang | Kelebihan | Kekurangan |
| :--- | :--- | :--- | :--- | :--- |
| **Token Bucket** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ per user | Mendukung *traffic burst* terkontrol; efisien secara komputasi | Rentan terhadap *burst* yang dapat membebani dependensi rapuh |
| **Leaky Bucket** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ atau $\mathcal{O}(N)$ queue | Menghasilkan laju pemrosesan yang mulus (*smooth output rate*) | Menimbulkan latensi tambahan karena request harus mengantre |
| **Fixed Window** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ per window | Implementasi sangat mudah pada Redis (`INCR` & `EXPIRE`) | *Traffic spike* hingga 2x batas di batas pergantian window (*boundary issue*) |
| **Sliding Window Log** | $\mathcal{O}(\log N)$ | $\mathcal{O}(N)$ | Akurasi 100% presisi; tidak memiliki limit boundary issue | Memori boros; jejak data membesar sesuai volume request |
| **Sliding Window Counter** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | Rendah memori; akurasi statistik mendekati 99% | Asumsi distribusi trafik merata pada jendela waktu sebelumnya |

#### Formula Sliding Window Counter:
Estimasi jumlah request dihitung dengan menginterpolasi bobot dari jendela sebelumnya:

$$\text{Count} = C_{\text{current}} + C_{\text{previous}} \times \left(1 - \frac{t - t_{\text{current\_window\_start}}}{\text{WindowSize}}\right)$$

Jika $\text{Count} > \text{Limit}$, request ditolak.

---

### 2. Algoritma Jitter: Menghentikan Thundering Herd

Ketika ratusan worker/klien gagal serentak, melakukan retry dengan formula deterministik $T = 2^i \times B$ (di mana $i$ adalah *attempt* dan $B$ adalah *base duration*) akan menciptakan lonjakan interval retry berkala yang selaras secara fasa (*synchronized spikes*). Solusinya adalah menyuntikkan derau acak (*stochastic jitter*).

```
Waktu Deterministic (No Jitter):
Iterasi 1: [---2s---] (Semua Klien Kirim Serentak) ────────────────> Lonjakan Spike
Iterasi 2: [--------4s--------] (Semua Klien Kirim Serentak) ──────> Lonjakan Spike

Waktu dengan Full Jitter:
Klien A:   [--1.2s--] (Kirim)
Klien B:   [----1.8s----] (Kirim)
Klien C:   [-0.4s-] (Kirim)
```

Tiga formulasi utama jitter (AWS Research):
1. **Full Jitter**: 
   $$T_{\text{sleep}} = \text{random}(0, \min(M, B \times 2^i))$$
2. **Equal Jitter**:
   $$\text{half} = \frac{\min(M, B \times 2^i)}{2}; \quad T_{\text{sleep}} = \text{half} + \text{random}(0, \text{half})$$
3. **Decorrelated Jitter**:
   $$T_{\text{sleep}} = \min(M, \text{random}(B, T_{\text{previous}} \times 3))$$

*(di mana $M$ = durasi backoff maksimum, $B$ = durasi base backoff).*

---

### 3. State Machine: Circuit Breaker

```
               ┌───────────────────────────────┐
               │                               │
               │         CLOSED STATE          │
               │   (Semua Request Diteruskan)   │
               │                               │
               └───────────────┬───────────────┘
                               │
            Rasio Error Melebihi Threshold (%)
            Dan Minimum Request Terpenuhi
                               │
                               ▼
               ┌───────────────────────────────┐
               │                               │
               │          OPEN STATE           │
               │     (Fast-Fail: Error 503     │
               │    Tanpa Eksekusi Backend)    │
               │                               │
               └───────────────┬───────────────┘
                               │
                 Timer Sleep Window Kadaluwarsa
                               │
                               ▼
               ┌───────────────────────────────┐
               │                               │
               │       HALF-OPEN STATE         │
               │  (Uji Coba Sebanyak N Canary) │
               │                               │
               └───────┬───────────────┬───────┘
                       │               │
       Semua Sukses    │               │ Ada Request Gagal
                       │               │
                       ▼               ▼
                  Kembali ke       Kembali ke
                 CLOSED STATE      OPEN STATE
```

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Arsitektur Distributed Rate Limiting & Resilient Edge Gateway

```
[ Klien API: Mobile / Web / Mitra B2B ]
                  │
                  │ HTTPS (Keep-Alive, HTTP/2 multiplexing)
                  ▼
┌────────────────────────────────────────────────────────┐
│               ENTERPRISE API GATEWAY                   │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 1. RATE LIMITING ENGINE (Distributed)            │  │
│  │    Eksekusi Script Redis Lua secara Atomik       │  │
│  │    Terapkan Token Bucket / Sliding Window        │  │
│  └──────────────┬───────────────────┬───────────────┘  │
│                 │                   │                  │
│        Reject   │ (Exceeded)        │ (Allowed)        │
│                 ▼                   ▼                  │
│       ┌─────────────────┐ ┌─────────────────────────┐  │
│       │ Return HTTP 429 │ │ 2. ADAPTIVE CONCURRENCY │  │
│       │ Retry-After: 30 │ │    LIMITER (Little's L) │  │
│       └─────────────────┘ └─────────┬───────────────┘  │
│                                     │                  │
│                                     ▼                  │
│                           ┌─────────────────────────┐  │
│                           │ 3. CIRCUIT BREAKER      │  │
│                           │    State Engine         │  │
│                           └─────────┬───────────────┘  │
└─────────────────────────────────────┼──────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │ State = CLOSED                          │ State = OPEN
                 ▼                                         ▼
   ┌───────────────────────────┐                 ┌──────────────────┐
   │ INTERNAL MICROSERVICE (X) │                 │ Return HTTP 503  │
   │ Eksekusi Logic/SQL/RPC    │                 │ (Fast-Fail)      │
   └─────────────┬─────────────┘                 └──────────────────┘
                 │
                 │ Degraded / Timeout / 5xx
                 ▼
   ┌───────────────────────────┐
   │ CLIENT-SIDE RETRY POLICY  │
   │ (Exp-Backoff + Jitter)    │
   └───────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi fundamental *Sliding Window Counter* murni berbasis memori lokal (*in-memory*) dalam bahasa Go, menggunakan proteksi *sync.Mutex* untuk mendemonstrasikan kalkulasi matematika secara presisi tanpa ketergantungan infrastruktur eksternal.

```go
package main

import (
	"fmt"
	"sync"
	"time"
)

type SlidingWindowCounter struct {
	mu           sync.Mutex
	windowSize   time.Duration
	limit        int64
	currentWin   int64
	previousWin  int64
	lastRotatedAt time.Time
}

func NewSlidingWindowCounter(limit int64, windowSize time.Duration) *SlidingWindowCounter {
	return &SlidingWindowCounter{
		limit:         limit,
		windowSize:    windowSize,
		lastRotatedAt: time.Now(),
	}
}

func (s *SlidingWindowCounter) Allow() bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(s.lastRotatedAt)

	// Rotasi jendela jika durasi jendela telah lewat
	if elapsed >= s.windowSize {
		windowsPassed := elapsed / s.windowSize
		if windowsPassed == 1 {
			s.previousWin = s.currentWin
		} else {
			s.previousWin = 0
		}
		s.currentWin = 0
		s.lastRotatedAt = s.lastRotatedAt.Add(windowsPassed * s.windowSize)
		elapsed = now.Sub(s.lastRotatedAt)
	}

	// Hitung bobot jendela sebelumnya
	weight := 1.0 - (float64(elapsed) / float64(s.windowSize))
	estimatedCount := float64(s.previousWin)*weight + float64(s.currentWin)

	if estimatedCount+1.0 > float64(s.limit) {
		return false // Rate limit terlampaui
	}

	s.currentWin++
	return true
}

func main() {
	limiter := NewSlidingWindowCounter(5, 1*time.Second) // Limit: 5 req/detik

	for i := 1; i <= 10; i++ {
		allowed := limiter.Allow()
		fmt.Printf("Request #%02d: Diterima = %t\n", i, allowed)
		time.Sleep(100 * time.Millisecond)
	}
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Pada skenario enterprise nyata, *rate limiter* harus beroperasi secara terdistribusi melintasi lusinan instans API Gateway. Pendekatan naive `GET` dan `SET` pada Redis memicu *race condition* parah. Kita wajib mengeksekusi logika *Token Bucket* secara atomik langsung di memori Redis menggunakan **Lua Scripting**, dipadukan dengan implementasi *Circuit Breaker* berbasis state-machine di sisi aplikasi client/gateway.

### 1. Script Lua: Redis Distributed Token Bucket Engine (`token_bucket.lua`)

```lua
-- KUNCI: KEYS[1] = Key Identifier (e.g. rate:user:1001)
-- ARGUMEN: 
-- ARGV[1] = Kapasitas Maksimum Bucket (Capacity)
-- ARGV[2] = Laju Refill per Detik (Refill Rate)
-- ARGV[3] = Unix Epoch Time Sekarang (dalam detik)
-- ARGV[4] = Jumlah Token yang Diminta (Requested Tokens)

local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

-- Ambil status bucket sebelumnya [tokens, last_updated]
local data = redis.call("HMGET", key, "tokens", "last_updated")
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil then
    -- Inisialisasi awal
    tokens = capacity
    last_updated = now
else
    -- Hitung penambahan token berdasarkan waktu delta
    local delta = math.max(0, now - last_updated)
    local generated_tokens = delta * refill_rate
    tokens = math.min(capacity, tokens + generated_tokens)
    last_updated = now
end

-- Evaluasi ketersediaan token
if tokens >= requested then
    tokens = tokens - requested
    redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
    -- Pasang TTL agar memori otomatis bersih jika idle
    local ttl = math.ceil(capacity / refill_rate) * 2
    redis.call("EXPIRE", key, ttl)
    return {1, tokens} -- 1 = Allowed, token tersisa
else
    redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
    return {0, tokens} -- 0 = Denied, token tersisa
end
```

### 2. Implementasi Terintegrasi di Go: Gateway Handler & Circuit Breaker

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"math"
	"math/rand"
	"net/http"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// --- STRUKTUR DAN LOGIKA CIRCUIT BREAKER ---

type State int

const (
	StateClosed State = iota
	StateOpen
	StateHalfOpen
)

type CircuitBreaker struct {
	mu           sync.Mutex
	state        State
	failureCount int
	threshold    int
	lastFailTime time.Time
	timeout      time.Duration
}

func NewCircuitBreaker(threshold int, timeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:     StateClosed,
		threshold: threshold,
		timeout:   timeout,
	}
}

func (cb *CircuitBreaker) Execute(action func() error) error {
	cb.mu.Lock()
	now := time.Now()

	switch cb.state {
	case StateOpen:
		if now.Sub(cb.lastFailTime) > cb.timeout {
			cb.state = StateHalfOpen
		} else {
			cb.mu.Unlock()
			return errors.New("circuit breaker is OPEN: fast-fail triggered")
		}
	}
	cb.mu.Unlock()

	err := action()

	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		cb.failureCount++
		cb.lastFailTime = time.Now()
		if cb.state == StateHalfOpen || cb.failureCount >= cb.threshold {
			cb.state = StateOpen
		}
		return err
	}

	if cb.state == StateHalfOpen {
		cb.state = StateClosed
		cb.failureCount = 0
	}
	return nil
}

// --- FULL JITTER EXPONENTIAL BACKOFF CLIENT ---

func CallDependencyWithRetry(ctx context.Context, cb *CircuitBreaker, operation func() error) error {
	base := 100 * time.Millisecond
	maxBackoff := 2 * time.Second
	maxRetries := 3

	r := rand.New(rand.NewSource(time.Now().UnixNano()))

	for attempt := 0; attempt < maxRetries; attempt++ {
		err := cb.Execute(operation)
		if err == nil {
			return nil
		}

		if errors.Is(err, context.Canceled) {
			return err
		}

		// Hitung Full Jitter: Sleep = rand(0, min(maxBackoff, base * 2^attempt))
		backoffLimit := float64(base) * math.Pow(2, float64(attempt))
		if backoffLimit > float64(maxBackoff) {
			backoffLimit = float64(maxBackoff)
		}
		sleepDuration := time.Duration(r.Float64() * backoffLimit)

		select {
		case <-time.After(sleepDuration):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	return errors.New("eksekusi gagal: batas maksimum retry tercapai")
}

// --- DISTRIBUTED RATE LIMITER DENGAN GO-REDIS ---

var tokenBucketLua = redis.NewScript(`
	local key = KEYS[1]
	local capacity = tonumber(ARGV[1])
	local refill_rate = tonumber(ARGV[2])
	local now = tonumber(ARGV[3])
	local requested = tonumber(ARGV[4])

	local data = redis.call("HMGET", key, "tokens", "last_updated")
	local tokens = tonumber(data[1])
	local last_updated = tonumber(data[2])

	if tokens == nil then
		tokens = capacity
		last_updated = now
	else
		local delta = math.max(0, now - last_updated)
		tokens = math.min(capacity, tokens + (delta * refill_rate))
		last_updated = now
	end

	if tokens >= requested then
		tokens = tokens - requested
		redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
		redis.call("EXPIRE", key, math.ceil(capacity / refill_rate) * 2)
		return {1, math.floor(tokens)}
	else
		redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
		return {0, math.floor(tokens)}
	end
`)

type ResilientGateway struct {
	rdb *redis.Client
	cb  *CircuitBreaker
}

func (gw *ResilientGateway) RateLimitMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		apiKey := r.Header.Get("X-API-KEY")
		if apiKey == "" {
			apiKey = "anonymous"
		}

		ctx := r.Context()
		nowSec := time.Now().Unix()
		key := fmt.Sprintf("ratelimit:%s", apiKey)

		// Kapasitas = 10, Refill = 2 token/detik, Konsumsi = 1
		result, err := tokenBucketLua.Run(ctx, gw.rdb, []string{key}, 10, 2, nowSec, 1).Result()
		if err != nil {
			// Fail-open jika redis cluster unreachable (pilihan arsitektural availability > consistency)
			next.ServeHTTP(w, r)
			return
		}

		resSlice := result.([]interface{})
		allowed := resSlice[0].(int64) == 1
		remaining := resSlice[1].(int64)

		w.Header().Set("RateLimit-Limit", "10")
		w.Header().Set("RateLimit-Remaining", fmt.Sprintf("%d", remaining))

		if !allowed {
			w.Header().Set("Retry-After", "1")
			http.Error(w, `{"error": "Too Many Requests", "code": 429}`, http.StatusTooManyRequests)
			return
		}

		next.ServeHTTP(w, r)
	})
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

```
             Konsistensi Mutlak (Strict Precision)
                         ▲
                        / \
                       /   \
                      /     \
   Sliding Window Log/       \ Centralized Redis Lock
   Redis Lua                  \ (Tinggi Latensi & Bottleneck)
                    /         \
                   /           \
                  /             \
Latency Rendah   ┌───────────────┐ Ketersediaan Tinggi (High Availability)
(Local Memory    │ Trade-off     │ (Fail-Open / Token Bucket Lokal)
 Bucket/Counter) └───────────────┘
```

### 1. Centralized Rate Limiting vs Local In-Memory Rate Limiting
* **Centralized (Redis/Memcached)**: Menjamin batasan kuota berlaku presisi di 100 node Gateway. Kelemahannya: Menambahkan 1 *network hop* ekstra ($\approx 1-3\text{ ms}$) per request; Redis menjadi *Single Point of Failure* (SPOF) bila kluster gagal.
* **Local In-Memory (Node-level)**: Sangat kencang ($\le 1\text{ mikrodetik}$), namun jika beban load balancer tidak terdistribusi secara seimbang (*uneven round-robin*), sebuah node dapat membatasi klien sementara node lain masih memiliki kuota kosong.

### 2. Fail-Open vs Fail-Closed
Jika kluster Redis *down*:
* **Fail-Open (Default pada Consumer Tech)**: Lewatkan request. Memprioritaskan *Customer Experience* daripada proteksi kuota absolut.
* **Fail-Closed (Default pada Financial Ledger / Core Banking)**: Tolak request HTTP 500/429. Mencegah risiko kerugian finansial akibat transaksi ganda yang membobol limit kredit.

### 3. sliding Window Log vs Sliding Window Counter
* **Sliding Window Log**: Menggunakan Redis ZSET. Presisi mikrodetik mutlak, tetapi jika limit 10.000 req/menit untuk 1.000.000 user, kebutuhan RAM Redis melonjak hingga ratusan Gigabyte.
* **Sliding Window Counter**: Menggunakan struktur data HASH sederhana berbobot matematis. Menghemat memori hingga 99%, dengan deviasi statistik galat hanya $\approx 0.05\%$.

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Format Header Standar IETF**:
   Gunakan header standar industri untuk memberi visibilitas transparan kepada klien:
   * `RateLimit-Limit`: Jumlah request maksimal dalam jendela.
   * `RateLimit-Remaining`: Sisa request yang dapat dilakukan.
   * `RateLimit-Reset`: Jumlah detik tersisa hingga jendela direset.
   * `Retry-After`: Waktu wajib (dalam detik) bagi klien untuk menunda sebelum request berikutnya (standar pada status `429` dan `503`).

2. **Diferensiasi Rate Limit Sesuai Lapisan Kunci (Multi-Tier Keying)**:
   Jangan hanya bergantung pada IP Address (rentan akibat proxy/NAT perusahaan di mana ribuan user berbagi satu IP publik). Kombinasikan:
   * Tier 1: `API_KEY` atau `User_ID` (Autentikasi).
   * Tier 2: `IP_Address` (Unauthenticated routes seperti `/login`, `/register`).
   * Tier 3: Endpoint Criticality (misal: `/checkout` diberi kuota lebih ketat dibanding `/products`).

3. **Circuit Breaker Minimum Throughput Requirement**:
   Konfigurasikan sirkuit agar **tidak trip** hanya karena 2 dari 2 request gagal (error rate 100%). Tetapkan parameter `VolumeThreshold` minimum (contoh: minimal harus ada 50 request dalam 10 detik terakhir sebelum kalkulasi error rate dieksekusi).

4. **Kombinasikan Circuit Breaker dengan Deadline / Hard Timeout**:
   Circuit breaker tidak akan berfungsi jika pemanggilan downstream menggantung selamanya tanpa batasan. Pasang timeout agresif (contoh: 800ms) sehingga pemanggilan yang lambat langsung dicatat sebagai *failure*.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. Retries Tanpa Jitter (Thundering Herd Trigger)
Menggunakan *static retry* (misal: coba lagi setiap 500ms) atau *pure exponential backoff* tanpa desinkronisasi stokastik. Ketika database pulih dari failover, jutaan request klien yang mengantre akan menembak serentak di milidetik yang sama, merobohkan database kembali ke status *crashed*.

### 2. Check-Then-Act Anti-Pattern pada Redis
Mengeksekusi:
```python
# KESALAHAN FATAL: Non-Atomic Race Condition
count = redis.get("rate:" + user_id)
if count < 100:
    redis.incr("rate:" + user_id) # Celah race condition antar concurrent threads!
```
Dua thread bersamaan dapat membaca `count = 99`, dan keduanya menjalankan `INCR`, meloloskan 101 request. **Solusi mutlak**: Bungkus dalam transaksi *Redis Lua script* yang menjamin eksekusi *single-threaded atomic*.

### 3. Mengabaikan Error Types dalam Policy Retry
Melakukan retry pada sembarang error. Request berstatus `HTTP 400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, atau `422 Unprocessable Entity` adalah error deterministik dari sisi klien. Melakukan retry terhadap error ini adalah pemborosan komputasi backend. Hanya lakukan retry pada error transien: `HTTP 429`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`, atau *network I/O reset*.

### 4. Memory Leak pada Sliding Window Logs
Mengabaikan pembersihan (*pruning*) elemen lama pada Redis ZSET. ZSET akan terus membesar jika elemen lama tidak dibuang dengan `ZREMRANGEBYSCORE` secara berkala dalam transaksi yang sama.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario 1 (Tingkat Dasar) — Fixed Window Flaw Demonstrator
* **Tugas**: Tulis program kecil yang mengekspos kelemahan *Fixed Window Counter*. Konfigurasi window = 1 detik, limit = 10 request.
* **Instruksi**: Kirim 10 request di $t = 950\text{ ms}$, lalu kirim 10 request lagi di $t = 1050\text{ ms}$. Buktikan bahwa sistem memproses 20 request dalam interval rentang $100\text{ ms}$ tanpa memicu HTTP 429.

### Skenario 2 (Tingkat Menengah) — Redis Sliding Window Log Pruning Engine
* **Tugas**: Rancang script Redis Lua yang mengimplementasikan *Sliding Window Log* menggunakan sorted set (`ZSET`).
* **Instruksi**:
  1. Hapus nilai timestamp yang lebih tua dari $now - window\_size$ menggunakan `ZREMRANGEBYSCORE`.
  2. Hitung jumlah elemen tersisa dengan `ZCARD`.
  3. Jika masih di bawah ambang limit, tambahkan timestamp saat ini dengan `ZADD` dan set TTL kunci.
  4. Lakukan benchmarking eksekusi dan catat jejak alokasi memori Redis.

### Skenario 3 (Tingkat Lanjut) — Resilient Client Simulator dengan Decorrelated Jitter
* **Tugas**: Buat simulator HTTP Client yang menangani server dependensi tiruan yang sengaja dibuat rusak (*flaky server* yang memuntahkan 80% error HTTP 500 selama 10 detik pertama, lalu sembuh).
* **Instruksi**:
  1. Terapkan client dengan algoritma *Decorrelated Jitter*: 
     $$T_{\text{sleep}} = \min(M, \text{random}(B, T_{\text{previous}} \times 3))$$
  2. Bandingkan profil traffic histogram kedatangan request di server antara: *No Jitter*, *Full Jitter*, dan *Decorrelated Jitter*.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Kelemahan matematis paling fundamental dari algoritma Fixed Window Counter yang diatasi oleh Sliding Window Log adalah:**
   * A. Tingginya kompleksitas memori penyimpanan pada backend.
   * B. Boundary issue yang memungkinkan lonjakan beban trafik hingga 2x limit di persimpangan window waktu.
   * C. Ketidakmampuan menangani traffic burst secara natural.
   * D. Adanya keharusan mengeksekusi komputasi float yang berat pada CPU Redis.

2. **Mengapa eksekusi rate limiting terdistribusi di Redis wajib menggunakan script Lua atau fitur Functions bawaan?**
   * A. Karena Lua mengeksekusi komputasi paralel pada multithreaded engine Redis.
   * B. Karena Redis menjamin eksekusi Lua bersifat atomik dan non-preemptive, mengeliminasi race condition tanpa explicit distributed locking.
   * C. Karena sintaks Lua otomatis mengompresi payload transmisi TCP data store.
   * D. Karena Lua langsung mengubah memory layout dari Redis strings menjadi bit arrays.

3. **Status Circuit Breaker berpindah dari OPEN menuju HALF-OPEN ketika:**
   * A. Semua error downstream telah berkurang hingga 0% secara instan.
   * B. Parameter `SleepWindow` durasi waktu tunggu fast-fail telah kadaluwarsa.
   * C. Operator jaringan melakukan manual trigger reset melalui command line.
   * D. Kapasitas worker thread local telah mencapai utilitas 100%.

4. **Formula Full Jitter yang dirilis oleh AWS Engineering Research didefinisikan sebagai:**
   * A. $T = B \times 2^i$
   * B. $T = \text{random}(0, \min(M, B \times 2^i))$
   * C. $T = \frac{B \times 2^i}{2} + \text{random}(0, B)$
   * D. $T = \text{random}(B, T_{\text{previous}} \times 3)$

5. **Kode status HTTP manakah yang paling semantik untuk memberitahu klien bahwa mereka melanggar kuota frekuensi transmisi, serta header pendamping apa yang wajib dikirimkan?**
   * A. HTTP 503 dengan header `Connection: close`
   * B. HTTP 500 dengan header `X-Rate-Exceeded: true`
   * C. HTTP 429 dengan header `Retry-After`
   * D. HTTP 400 dengan header `Clear-Backlog: true`

*(Kunci Jawaban: 1-B, 2-B, 3-B, 4-B, 5-C)*

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Buku & Standar Industri**:
   * Nygard, Michael T. (2018). *Release It!: Design and Deploy Production-Ready Software (2nd Edition)*. Pragmatic Bookshelf. (Rujukan kanonikal pola Circuit Breaker).
   * Beyer, B., Jones, C., Petoff, J., & Murphy, N. R. (2016). *Site Reliability Engineering: How Google Runs Production Systems*. O'Reilly Media. (Bab 21: *Addressing Cascading Failures*).
   * IETF RFC 6585: *Additional HTTP Status Codes* (Status Code 429 Too Many Requests).
   * IETF Draft: *RateLimit Header Fields for HTTP* (`draft-ietf-httpapi-ratelimit-headers-07`).

2. **Technical Papers & Engineering Blogs**:
   * Brooker, Marc (AWS Architecture Blog). *Exponential Backoff And Jitter*. 
   * Netflix Technology Blog. *Performance Under Load: Adaptive Concurrency Limits*.
   * Redis Documentation. *Programmability with Lua Scripts and Transaction Atomicity*.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Traffic Shaping & Rate Limiting** berfungsi sebagai katup pengaman sistem terdistribusi. Tanpa rate limiter, kapasitas puncak infrastruktur selalu rentan terhadap degradasi mendadak akibat lonjakan trafik tak terkendali.
2. **Karakteristik Algoritma**: *Token Bucket* unggul untuk mendukung burst terkontrol; *Leaky Bucket* ideal untuk menghaluskan fluktuasi output stream; *Sliding Window Counter* menawarkan efisiensi ruang $\mathcal{O}(1)$ dan presisi tinggi untuk arsitektur multi-node modern.
3. **Eksekusi Terdistribusi Mutlak Atomik**: Penggunaan kombinasi Redis dan Lua memastikan pengecekan kuota dan mutasi data dilakukan dalam satu siklus isolasi instruksi, meniadakan celah eksploitasi *concurrency race condition*.
4. **Resiliency Pola Ganda**: *Circuit Breaker* memangkas waktu pemulihan sistem dengan melakukan *fail-fast* saat dependensi rusak. Bersamaan dengan itu, *Client-side Retries* wajib dipasangkan dengan formula *Exponential Backoff* dan *Stochastic Jitter* agar lonjakan retry tidak memicu *thundering herd*.
5. **Backpressure Terpadu**: Memberikan sinyal perlindungan upstream secara bertingkat lewat header standar `429 Too Many Requests` dan `Retry-After`, membiarkan klien mengatur laju transmisi sesuai kemampuan konsumsi downstream.

---

## SEKSI 17 — GLOSARIUM

* **Cascading Failure**: Rangkaian kegagalan beruntun pada sistem terdistribusi di mana matinya satu komponen membebani komponen lain hingga memicu kehancuran sistem secara total.
* **Circuit Breaker**: Mekanisme isolasi kegagalan piranti lunak yang memutus jalur komunikasi ke layanan yang terindikasi rusak guna mencegah alokasi sumber daya sia-sia.
* **Fail-Fast**: Filosofi perancangan sistem yang langsung mengembalikan respon kegagalan tanpa mengeksekusi operasi mahal saat kondisi lingkungan sistem tidak memungkinkan.
* **Fail-Open**: Karakteristik fallback arsitektur di mana ketika komponen proteksi (seperti Rate Limiter atau WAF) mengalami kerusakan internal, request tetap diizinkan lewat demi ketersediaan layanan (*availability*).
* **Jitter**: Derau stokastik atau variasi latensi acak yang diinjeksikan secara sengaja ke dalam algoritma waktu jeda untuk memecah sinkronisasi koneksi antrean klien.
* **Leaky Bucket**: Algoritma traffic shaping berbasis antrean (FIFO) yang menahan request dalam buffer dan mengalirkannya ke backend dengan kecepatan konstan.
* **Race Condition**: Anomali perangkat lunak ketika luaran eksekusi bergantung pada urutan atau waktu pergantian thread/proses konkuren yang tidak terkontrol.
* **Thundering Herd Problem**: Fenomena di mana sejumlah besar proses, thread, atau klien independen terbangun atau menembak target dependensi secara serempak pasca-insiden, melumpuhkan kapasitas penanganan sistem target.
* **Token Bucket**: Algoritma rate limiting di mana token diisi ke dalam penampung dengan laju konstan hingga batas kapasitas maksimum; request hanya diloloskan jika tersedia cukup token untuk dikonsumsi.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Pedoman Pengajaran Kelas & Workshop

1. **Penekanan Konseptual Lab**:
   * Saat memandu hands-on Redis Lua, pastikan peserta didik menyadari bahwa *Lua script pada Redis berjalan secara atomik dan memblokir eksekusi thread Redis lainnya*. Oleh karena itu, jangan pernah mengeksekusi operasi Lua kompleks berskala $\mathcal{O}(N)$ pada dataset besar karena akan melumpuhkan performa server Redis secara global.
2. **Visualisasi Kasus Lapangan**:
   * Gunakan visualisator diagram jaringan interaktif untuk mendemonstrasikan bagaimana kurva error rate pada *Circuit Breaker* melesat tajam saat dependency downstream di-kill via `docker stop`, dan perhatikan bagaimana throughput server upstream stabil di response time $< 1\text{ ms}$ (akibat mekanisme *fail-fast* HTTP 503).
3. **Peringatan Penting Mengenai Jitter**:
   * Tunjukkan grafik distribusi request: Tanpa jitter, trafik membentuk pola sisir (*comb pattern*) dengan lonjakan periodik yang tajam. Dengan *Full Jitter*, trafik terdistribusi merata menjadi kurva landai yang mudah ditangani oleh autoscaler infrastruktur.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 2.4.0 (Current)**:
  * Pembaruan script atomik Redis Token Bucket ke implementasi Lua standar production-grade dengan TTL otomatis.
  * Penambahan bab matematis eksplisit mengenai 3 formula stokastik Jitter (Full, Equal, Decorrelated Jitter).
  * Penyesuaian standarisasi respon API terhadap IETF draft headers (`RateLimit-*`).
* **Versi 2.0.0**:
  * Migrasi materi dari monolithic rate limiting menuju arsitektur distributed edge gateway.
  * Penambahan implementasi Go Circuit Breaker State Machine berbasis struct pointer.
* **Versi 1.0.0**:
  * Inisialisasi silabus: Fixed window, naive token bucket, dan basic retry mechanism.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `API-ARCH-0603` — Caching Strategies, Invalidation Patterns, & Cache Topologies (Write-Through, Write-Behind, Cache-Aside)
* **Modul Saat Ini**: `API-ARCH-0701` — Traffic Shaping, Rate Limiting, & Resiliency: Distributed Algorithms, Circuit Breaking, Adaptive Retries, Jitter, & Backpressure
* **Modul Berikutnya**: `API-ARCH-0702` — Service Meshes, Zero-Trust API Communication, mTLS Handshakes, & Distributed Tracing Telemetry (OpenTelemetry)