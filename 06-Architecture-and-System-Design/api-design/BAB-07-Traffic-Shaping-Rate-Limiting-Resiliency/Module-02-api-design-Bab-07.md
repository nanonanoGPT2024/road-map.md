# BAB 07: Traffic Shaping, Rate Limiting & Resiliency
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *distributed rate limiting* berlatensi rendah (<2ms p99 overhead) yang tahan terhadap *clock drift*, *race condition*, dan kegagalan parsial pada kluster cache/database.
- Membangun mekanisme *adaptive concurrency limits* berbasis algoritma antrean (*Little's Law*, CoDel, TCP Vegas) untuk mencegah *cascading failure* tanpa memerlukan ambang batas statis (*static thresholds*).
- Mengorkestrasi pola *resiliency* multi-tier (*Token Bucket*, *Leaky Bucket*, *Distributed Circuit Breaker*, *Bulkhead*, dan *Load Shedding*) menggunakan kombinasi *edge proxy* (Envoy/API Gateway) dan pustaka aplikasi *in-process*.
- Menyusun *graceful degradation contract* yang patuh pada standar IETF (*draft-ietf-httpapi-ratelimit-headers*) dan RFC 6585/7231, lengkap dengan skema *exponential backoff* dan *jitter*.
- Menganalisis *trade-off* mendalam antara akurasi limitasi vs latensi I/O jaringan serta mendiagnosis anomali *thundering herd* dan *retry storm* pada skala jutaan *Requests Per Second* (RPS).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Konsep Dasar Jaringan & HTTP**: Pemahaman protokol TCP/IP, HTTP/1.1, HTTP/2, alur *handshake* TLS, status code HTTP (429 Too Many Requests, 503 Service Unavailable, 504 Gateway Timeout).
- **Struktur Data & Algoritma Concurrency**: Mutex, atomic primitives, *sliding window*, *circular buffer*, *leaky bucket*, serta penyelesaian *race condition* menggunakan *Compare-And-Swap* (CAS).
- **Sistem Terdistribusi**: Karakteristik konsistensi eventual (CAP Theorem), *quorum consensus*, arsitektur Redis Cluster (sharding, hash slots), dan komunikasi asinkron berbasis *event-loop*.
- **Bahasa Pemrograman**: Kemampuan membaca dan menulis kode Go (Golang) tingkat menengah-lanjut (Goroutine, Channels, Context, Sync primitives) serta skrip Redis Lua.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi produksi untuk *traffic shaping* dan *resiliency* melampaui proteksi sederhana berupa penghitung numerik di memori lokal. Pada skala sistem terdistribusi multi-region, sistem menghadapi tantangan sinkronisasi status, divergensi latensi, dan ketidakpastian kapasitas downstream.

```
                           INTERNET / CLIENTS
                                   │
                      ┌────────────▼────────────┐
                      │    Edge Cloudflare /    │ (L4/L7 Volumetric Rate Limit,
                      │      Anycast CDN        │  DDoS mitigation)
                      └────────────┬────────────┘
                                   │
                   ┌───────────────▼───────────────┐
                   │    Ingress API Gateway        │ (Token Bucket per Identity,
                   │      (Envoy / Kong)           │  Global Quotas, WAF)
                   └───────┬───────────────┬───────┘
                           │               │
       ┌───────────────────┘               └───────────────────┐
       ▼                                                       ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│ Service A (Order Service)     │               │ Service B (Payment Service)   │
│ ┌───────────────────────────┐ │               │ ┌───────────────────────────┐ │
│ │ Adaptive Concurrency Limit│ │               │ │ Bulkhead Isolation Pool   │ │
│ └─────────────┬─────────────┘ │               │ └─────────────┬─────────────┘ │
│ ┌─────────────▼─────────────┐ │               │ ┌─────────────▼─────────────┐ │
│ │ In-Process Circuit Breaker│ │               │ │ Distributed Rate Limiter  │ │
│ └─────────────┬─────────────┘ │               │ └─────────────┬─────────────┘ │
└───────────────┼───────────────┘               └───────────────┼───────────────┘
                │                                               │
                └───────────────────────┬───────────────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │ Redis Cluster (State Store) │
                         │ Sliding Window Log/Counter  │
                         │ Hash-tagged Keys: {tenant}  │
                         └─────────────────────────────┘
```

#### A. Distributed Sliding Window Counter: Algoritma & Mitigasi Race Condition
Algoritma *Fixed Window* rentan terhadap lonjakan *traffic burst* 2x limit di batas antar-jendela waktu (boundary limit). Sebaliknya, *Sliding Log* murni membutuhkan alokasi memori $O(N)$ (menyimpan timestamp per request) yang menyebabkan *memory exhaustion* saat diserang *traffic* masif.

Solusi standar enterprise adalah **Sliding Window Counter** hibrida yang mengaproksimasi perhitungan dengan memori konstan $O(1)$:

$$\text{Estimated Count} = \text{Count}_{\text{current}} + \left( \text{Count}_{\text{previous}} \times \frac{\text{Window Size} - \text{Time Elapsed in Current}}{\text{Window Size}} \right)$$

Untuk mengeksekusi ini tanpa *race condition* (read-modify-write) di Redis, kalkulasi wajib didelegasikan ke *Redis Lua Scripting* yang bersifat atomik, atau menggunakan tipe data *Redis Sorted Set* (ZSET) yang dipadukan dengan pembersihan otomatis via pipeline.

#### B. Dynamic / Adaptive Concurrency Limiting (Beyond Static Thresholds)
Menentukan batas statis (misal: "Service X maksimal 500 RPS") selalu berujung pada dua masalah:
1. Limit terlalu rendah $\rightarrow$ *False positive drops* saat resource sistem sebenarnya masih menganggur.
2. Limit terlalu tinggi $\rightarrow$ Terjadi degradasi performa (*queue bloat*) saat database mengalami *lock contention*, menyebabkan latensi meroket hingga terjadi *cascading failure*.

Sistem modern menerapkan prinsip **Little’s Law**:

$$L = \lambda \times W$$

Di mana:
- $L$ = *Concurrency* (jumlah request dalam pemrosesan bersamaan / *In-Flight Requests*).
- $\lambda$ = *Throughput* (jumlah request selesai per satuan waktu).
- $W$ = *Average Latency* (waktu respons rata-rata).

Melalui algoritma turunan TCP Congestion Control (seperti **TCP Vegas** atau **Gradient2** yang diadopsi oleh Netflix):
- Sistem secara periodik mengukur $RTT_{\text{no-load}}$ (latensi minimum ideal saat beban rendah).
- Sistem memantau $RTT_{\text{actual}}$ saat ini.
- Jika $RTT_{\text{actual}} \approx RTT_{\text{no-load}}$, sistem meningkatkan *concurrency limit* secara aditif ($Limit = Limit + 1$).
- Jika $RTT_{\text{actual}} > RTT_{\text{no-load}} \times \text{tolerance}$, sistem mengurangi *concurrency limit* secara multiplikatif ($Limit = Limit \times \beta$).

#### C. Circuit Breaking Topologies & State Machine
Circuit Breaker beroperasi sebagai *finite-state machine* (FSM) yang memutus jalur komunikasi ke dependensi rapuh demi mengamankan ketersediaan sistem induk:

```
          [ Failure Rate > Threshold ]
   ┌────────────────────────────────────────┐
   │                                        │
┌──▼──────────┐   Probe Timeout       ┌─────┴────────┐
│             ├──────────────────────►│              │
│    OPEN     │                       │  HALF-OPEN   │
│             │◄──────────────────────┤              │
└──▲──────────┘   Probe Failed        └─────┬────────┘
   │                                        │
   │                                        │ Probe Success
   │                                        │ (Success Rate >= Threshold)
   │                                        │
   │            [ Normal Flow ]             ▼
   └───────────────────────────────────┌─────────────┐
                                       │   CLOSED    │
                                       │             │
                                       └─────────────┘
```

Karakteristik penting implementasi tingkat lanjut:
1. **Half-Open Probing Strategy**: Menggunakan isolasi *canary probe* (misalnya hanya 1-5% request uji coba yang diteruskan) alih-alih membuka banjir request secara mendadak.
2. **Out-of-band Telemetry**: Memisahkan metrik kesehatan downstream via background worker ketimbang bergantung penuh pada latency *critical path*.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive) | Pendekatan Lanjutan (Enterprise-Grade) |
| :--- | :--- | :--- |
| **Penyimpanan State** | In-memory lokal (Node/Instance spesifik). | Kluster Redis terdistribusi dengan *hash-tagging* + *Local Fallback In-memory cache*. |
| **Ambang Batas (Threshold)** | Nilai statis hardcoded via Environment Variable (misal: 100 RPS). | *Dynamic / Adaptive Concurrency Limit* adaptif terhadap latensi & degradasi database. |
| **Mitigasi Kluster Down** | Sistem gagal total (*fail-close*) atau batas hilang (*fail-open unmetered*). | *Graceful local degradation* (Fail-open terkontrol dengan limitasi lokal darurat). |
| **Penanganan Error** | Mengembalikan `500 Internal Server Error` generik. | Mengembalikan `429 Too Many Requests` / `503 Service Unavailable` + standar RFC headers. |
| **Retry Strategy** | Immediate Retry atau Fixed Interval Retry. | Truncated Exponential Backoff dipadukan dengan **Full/Decorrelated Jitter**. |

---

### 5. How (Workflow Detail)

Alur eksekusi request melewati sistem *traffic shaping* dan *resilience engine*:

1. **Ingress Phase**: Request mencapai API Gateway. 
   - Gateway mengekstrak identitas client (API Key, JWT Subject, atau IP Mask).
   - Menghasilkan *composite key* untuk isolasi limit (contoh: `rate:{tenant_id}:{route_id}`).
2. **Distributed Gate Check (Sliding Window)**:
   - Request memicu evaluasi skrip Redis Lua atomik.
   - Jika kuota habis: Gateway langsung menghentikan request, menyusun header `Retry-After` dan payload RFC 7807 (Problem Details), lalu melepaskan koneksi (HTTP 429).
3. **Adaptive Concurrency & Bulkhead Phase (Application Level)**:
   - Request lolos ke target pod/service.
   - Pustaka *In-Process Concurrency Limiter* memverifikasi apakah batas in-flight request telah tercapai berdasarkan pengukuran RTT terkini.
   - Jika limit tercapai: Request ditolak via *Load Shedding* (HTTP 503) demi mempertahankan integritas pemrosesan request lain yang sedang berjalan.
4. **Circuit Breaker Evaluation**:
   - Jika sirkuit dalam status `OPEN`: Request diarahkan ke mekanisme *fallback* (ambil dari cache statis, default payload, atau langsung throw exception).
   - Jika sirkuit `CLOSED` atau `HALF-OPEN`: Request diproses dan waktu eksekusi dicatat.
5. **Egress & Feedback Phase**:
   - RTT diukur presisi ($T_{\text{end}} - T_{\text{start}}$).
   - Telemetri RTT dikirim ke modul *Adaptive Limit Calculator* untuk memperbarui batas konkurensi jendela waktu berikutnya.
   - Header standar dikomputasi dan disematkan pada response.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bendungan Cerdas, Pintu Air Otomatis, dan Sistem Evakuasi Darurat
- **Distributed Rate Limiting (Token Bucket di Redis)**: Mirip loket karcis masuk bendungan wisata. Sebanyak apa pun mobil yang mengantre di jalan raya, loket hanya mengeluarkan karcis sesuai kapasitas jalan di dalam area wisata.
- **Adaptive Concurrency Limiting**: Seperti sensor tekanan air di dalam pipa turbin bendungan. Saat turbin mendeteksi getaran berlebih (latensi naik/database lambat), pintu intake otomatis menyempit tanpa menunggu komando manual dari operator, menghindari pipa meledak (*system crash*).
- **Circuit Breaker**: Sakelar sekring listrik otomatis. Jika terjadi korsleting di salah satu instalasi kabel (misal dependensi Third-Party Payment Gateway mati), sekring memutus aliran ke ruangan tersebut secara instan agar seluruh gedung tidak terbakar.
- **Jitter pada Retry**: Saat pemadaman listrik selesai, jika seluruh penghuni kota menyalakan AC secara bersamaan pada detik ke-0, trafo listrik pusat akan meledak kembali (*thundering herd*). Jitter memaksa setiap rumah menyalakan AC secara acak antara 0 hingga 30 detik.

#### Diagram Transisi Eksekusi Request Terproteksi

```
[Incoming Request]
        │
        ▼
┌─────────────────────────┐      Limit Exceeded
│  Redis Distributed      ├─────────────────────────┐
│  Rate Limiter (Lua)     │                         │
└───────────┬─────────────┘                         │
            │ Allowed                               │
            ▼                                       ▼
┌─────────────────────────┐   Limit Exceeded  ┌──────────────────────┐
│  In-Process Adaptive    ├──────────────────►│  429 Too Many Req /  │
│  Concurrency Limiter    │                   │  503 Overloaded      │
└───────────┬─────────────┘                   │  (With Retry-After)  │
            │ Allowed                         └──────────────────────┘
            ▼                                       ▲
┌─────────────────────────┐     Circuit OPEN        │
│  Circuit Breaker        ├─────────────────────────┘
│  State Inspection       │
└───────────┬─────────────┘
            │ CLOSED / HALF-OPEN (Canary)
            ▼
┌─────────────────────────┐
│  Execute Downstream /   │
│  Target Logic           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Record Latency & RTT   │ ──► [Update Limits & Circuit Metrics]
│  Return 200 OK Response │
└─────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Practical Component 1: Redis Lua Script Sliding Window Counter Terdistribusi
Implementasi skrip Lua atomik yang mengelola *sliding window counter* dengan toleransi latensi nol dan memori efisien.

Simpan file logika Redis: `rate_limiter.lua`

```lua
-- KEYS[1]: Identifier Key (e.g., rate:{tenant}:route)
-- ARGV[1]: Current Timestamp (Unix Epoch Milliseconds)
-- ARGV[2]: Window Size in Milliseconds (e.g., 60000 for 1 minute)
-- ARGV[3]: Max Allowed Requests in Window

local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

local clearBefore = now - window

-- 1. Hapus request timestamp yang berada di luar jendela waktu
redis.call('ZREMRANGEBYSCORE', key, 0, clearBefore)

-- 2. Ambil total request yang tersisa di dalam window
local currentRequests = redis.call('ZCARD', key)

-- 3. Evaluasi kuota
if currentRequests < limit then
    -- Tambahkan request unik saat ini menggunakan timestamp dan UUID/random suffix
    redis.call('ZADD', key, now, now .. '-' .. redis.call('INCR', key .. ':seq'))
    -- Set TTL dinamis sedikit lebih panjang dari window untuk efisiensi GC Redis
    redis.call('PEXPIRE', key, window + 1000)
    return {1, limit - currentRequests - 1, math.floor(window / 1000)}
else
    -- Ambil timestamp terlama dalam window untuk kalkulasi Retry-After presisi
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retryAfter = 0
    if #oldest > 0 then
        retryAfter = math.ceil((tonumber(oldest[2]) + window - now) / 1000)
    end
    if retryAfter <= 0 then retryAfter = 1 end
    return {0, 0, retryAfter}
end
```

#### B. Practical Component 2: Go Implementation - Resilience Engine Terintegrasi
Kode berikut menerapkan proteksi multi-tier: distributed rate limiter via Redis, *Circuit Breaker* (FSM), dan *Exponential Backoff with Full Jitter*.

```go
package main

import (
	"context"
	"crypto/rand"
	_ "embed"
	"errors"
	"fmt"
	"math"
	"math/big"
	"net/http"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

//go:embed rate_limiter.lua
var slidingWindowLuaScript string

var (
	ErrRateLimitExceeded = errors.New("rate limit exceeded")
	ErrCircuitOpen       = errors.New("circuit breaker is OPEN")
)

// --- CIRCUIT BREAKER ARCHITECTURE ---

type CircuitState int32

const (
	StateClosed CircuitState = iota
	StateHalfOpen
	StateOpen
)

func (s CircuitState) String() string {
	switch s {
	case StateClosed:
		return "CLOSED"
	case StateHalfOpen:
		return "HALF-OPEN"
	case StateOpen:
		return "OPEN"
	default:
		return "UNKNOWN"
	}
}

type CircuitBreaker struct {
	state          int32 // atomic CircuitState
	failureCount   int64
	successCount   int64
	threshold      int64
	timeout        time.Duration
	lastStateShift int64 // unix nano
	mu             sync.Mutex
}

func NewCircuitBreaker(failureThreshold int64, openTimeout time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:          int32(StateClosed),
		threshold:      failureThreshold,
		timeout:        openTimeout,
		lastStateShift: time.Now().UnixNano(),
	}
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
	currentState := CircuitState(atomic.LoadInt32(&cb.state))
	now := time.Now().UnixNano()

	if currentState == StateOpen {
		lastShift := atomic.LoadInt64(&cb.lastStateShift)
		if now-lastShift > cb.timeout.Nanoseconds() {
			// Mencoba transisi ke Half-Open
			if atomic.CompareAndSwapInt32(&cb.state, int32(StateOpen), int32(StateHalfOpen)) {
				atomic.StoreInt64(&cb.lastStateShift, now)
				atomic.StoreInt64(&cb.successCount, 0)
			} else {
				return ErrCircuitOpen
			}
		} else {
			return ErrCircuitOpen
		}
	}

	err := fn()

	if err != nil {
		cb.onFailure()
		return err
	}

	cb.onSuccess()
	return nil
}

func (cb *CircuitBreaker) onFailure() {
	currentState := CircuitState(atomic.LoadInt32(&cb.state))
	if currentState == StateHalfOpen {
		// Single failure saat probing langsung mengembalikan ke Open
		atomic.StoreInt32(&cb.state, int32(StateOpen))
		atomic.StoreInt64(&cb.lastStateShift, time.Now().UnixNano())
		return
	}

	failures := atomic.AddInt64(&cb.failureCount, 1)
	if failures >= cb.threshold {
		if atomic.CompareAndSwapInt32(&cb.state, int32(StateClosed), int32(StateOpen)) {
			atomic.StoreInt64(&cb.lastStateShift, time.Now().UnixNano())
		}
	}
}

func (cb *CircuitBreaker) onSuccess() {
	currentState := CircuitState(atomic.LoadInt32(&cb.state))
	if currentState == StateHalfOpen {
		successes := atomic.AddInt64(&cb.successCount, 1)
		// Membutuhkan 3 probe sukses konsekutif untuk kembali ke status Closed
		if successes >= 3 {
			atomic.StoreInt32(&cb.state, int32(StateClosed))
			atomic.StoreInt64(&cb.failureCount, 0)
			atomic.StoreInt64(&cb.lastStateShift, time.Now().UnixNano())
		}
	} else if currentState == StateClosed {
		// Reset counter secara berkala jika sukses
		atomic.StoreInt64(&cb.failureCount, 0)
	}
}

// --- RATE LIMITER INFRASTRUCTURE ---

type Limiter struct {
	rdb        *redis.Client
	scriptSHA1 string
}

func NewLimiter(rdb *redis.Client) (*Limiter, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	sha, err := rdb.ScriptLoad(ctx, slidingWindowLuaScript).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to pre-load Lua script: %w", err)
	}
	return &Limiter{rdb: rdb, scriptSHA1: sha}, nil
}

type LimitResult struct {
	Allowed   bool
	Remaining int64
	ResetTTL  int64 // seconds
}

func (l *Limiter) CheckLimit(ctx context.Context, key string, window time.Duration, limit int) (LimitResult, error) {
	now := time.Now().UnixMilli()
	windowMillis := window.Milliseconds()

	res, err := l.rdb.EvalSha(ctx, l.scriptSHA1, []string{key}, now, windowMillis, limit).Result()
	if err != nil {
		return LimitResult{}, err
	}

	slice, ok := res.([]interface{})
	if !ok || len(slice) < 3 {
		return LimitResult{}, errors.New("malformed redis response")
	}

	allowed := slice[0].(int64) == 1
	remaining := slice[1].(int64)
	resetSec := slice[2].(int64)

	return LimitResult{
		Allowed:   allowed,
		Remaining: remaining,
		ResetTTL:  resetSec,
	}, nil
}

// --- FULL JITTER EXPONENTIAL BACKOFF UTILITY ---

func CalculateFullJitterBackoff(attempt int, base time.Duration, max time.Duration) time.Duration {
	if attempt < 0 {
		attempt = 0
	}
	// Exp = base * 2^attempt
	multiplier := math.Pow(2, float64(attempt))
	temp := float64(base) * multiplier

	if temp > float64(max) {
		temp = float64(max)
	}

	n, _ := rand.Int(rand.Reader, big.NewInt(int64(temp)))
	return time.Duration(n.Int64())
}

// --- HTTP MIDDLEWARE PRODUCTION-READY ---

func ResilienceMiddleware(limiter *Limiter, cb *CircuitBreaker) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			tenantID := r.Header.Get("X-Tenant-ID")
			if tenantID == "" {
				tenantID = "anonymous"
			}
			rateKey := fmt.Sprintf("{tenant:%s}:http_req", tenantID)

			// 1. Evaluasi Distributed Rate Limit
			result, err := limiter.CheckLimit(r.Context(), rateKey, 1*time.Minute, 100)
			if err != nil {
				// Fail-Open Policy: jika Redis down, log error dan biarkan request lanjut dengan warning header
				w.Header().Set("X-RateLimit-Fallback", "true")
			} else {
				// Standar IETF RateLimit Headers
				w.Header().Set("RateLimit-Limit", "100")
				w.Header().Set("RateLimit-Remaining", strconv.FormatInt(result.Remaining, 10))
				w.Header().Set("RateLimit-Reset", strconv.FormatInt(result.ResetTTL, 10))

				if !result.Allowed {
					w.Header().Set("Retry-After", strconv.FormatInt(result.ResetTTL, 10))
					w.WriteHeader(http.StatusTooManyRequests)
					w.Write([]byte(`{"error":"Too Many Requests","message":"Rate limit exceeded. Please back off."}`))
					return
				}
			}

			// 2. Evaluasi Circuit Breaker untuk isolasi Downstream
			err = cb.Execute(func() error {
				rec := &statusRecorder{ResponseWriter: w, statusCode: http.StatusOK}
				next.ServeHTTP(rec, r)
				if rec.statusCode >= 500 {
					return fmt.Errorf("downstream error: %d", rec.statusCode)
				}
				return nil
			})

			if errors.Is(err, ErrCircuitOpen) {
				w.Header().Set("Retry-After", "30")
				w.WriteHeader(http.StatusServiceUnavailable)
				w.Write([]byte(`{"error":"Service Unavailable","message":"Circuit open. Upstream system degraded."}`))
				return
			}
		})
	}
}

type statusRecorder struct {
	http.ResponseWriter
	statusCode int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.statusCode = code
	r.ResponseWriter.WriteHeader(code)
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Studi Kasus: Mitigasi Cascading Failure pada Flash Sale Multi-Tenant Tier-1
- **Konteks**: Platform e-commerce dengan arsitektur microservices mengalami *traffic surge* dari rata-rata 25.000 RPS melonjak seketika menjadi 450.000 RPS selama periode diskon *midnight flash sale*.
- **Insiden**: Layanan *Payment Orchestration* memanggil 3 gateway eksternal perbankan. Salah satu core banking gateway mengalami kenaikan p99 latency dari 250ms menjadi 18 detik karena antrean database di sisi mereka.
- **Dampak Awal Tanpa Resiliency Engine**:
  1. Goroutine thread pool di Payment Service habis (*thread exhaustion*) karena tertahan menunggu I/O gateway yang macet.
  2. Latensi merambat ke *Checkout Service*, lalu menjalar ke *Cart Service* dan *Product API*.
  3. Load balancer menandai pod lokal tidak sehat (*liveness probe fails* akibat CPU saturation menahan context-switching puluhan ribu thread).
  4. Seluruh platform mengalami mati total (*cascading blackout*).

#### Solusi Rekayasa yang Diimplementasikan:
1. **Penerapan Hash-Tagged Redis Cluster Sliding Window**:
   Limitasi per tenant/IP dilakukan di layer API Gateway Envoy menggunakan integrasi Redis Cluster. Penggunaan hash tag `{tenant_id}` memastikan seluruh mutasi kunci limitasi pengguna berada pada *slot shard* Redis yang sama tanpa *cross-node network hops*.
2. **Adaptive Concurrency Limit (Gradient Algorithm)**:
   Payment service memonitor batas in-flight request secara matematis. Ketika dependensi perbankan memperlambat respons, kapasitas konkurensi payment otomatis diturunkan dari 2000 in-flight requests ke 40 in-flight requests. Request selebihnya dipotong di awal (*fail-fast load shedding*) dengan kode `HTTP 503` terstruktur.
3. **Partitioned Bulkheading**:
   Memisahkan thread/connection pool untuk setiap gateway perbankan secara independen. Kemacetan Bank A tidak memengaruhi ketersediaan Bank B dan Bank C.
4. **Outlier Detection & Circuit Breaker**:
   Pola pemutus sirkuit mendeteksi Bank A menghasilkan error rate > 50% dalam window 10 detik. Sirkuit beralih ke `OPEN`, dan transaksi yang memilih Bank A otomatis dialihkan ke antrean asinkron (Kafka) dengan notifikasi status pesanan *pending processing*, menyelamatkan integritas sistem secara menyeluruh.

---

### 9. Trade-offs

```
                  [ Consistency & Accuracy ]
                             ▲
                            / \
                           /   \
                          /     \
                         /       \
  (Distributed Locks)   /         \   (Distributed Counters /
  High Latency Overhead/           \   Strict Redis Calls)
                      /             \
                     /               \
                    ▼─────────────────▼
[Low Latency / Performance] ◄─────────► [High Availability / Partition Tolerance]
 (Local In-Memory Buckets,               (Fail-Open, Probabilistic Counting,
  Asynchronous Sync)                      Eventual Consistency Sync)
```

| Opsi Arsitektur | Keuntungan | Kerugian & Konsekuensi |
| :--- | :--- | :--- |
| **Strict Distributed Limit (Redis Lua per Request)** | Akurasi mutlak (100% konsisten antar seluruh edge node). | Menambah 1-3ms latensi jaringan pada *critical path*. Bergantung sepenuhnya pada kesehatan cluster cache (titik kegagalan terpusat). |
| **Local In-Memory Token Bucket + Batch Asynchronous Sync** | Sangat cepat (< 0.05ms overhead); beban kerja CPU & Redis sangat minim. | Kurang akurat. Berpotensi *burst leak* hingga 10-20% melampaui limit global sebelum sinkronisasi status selesai dieksekusi antar instance. |
| **Static Thresholds vs Dynamic Adaptive Limits** | Sederhana, mudah di-audit, tidak memakan resource kalkulasi CPU runtime. | Rentan terhadap *false drops* saat utilisasi server rendah, atau sistem jebol saat dependensi downstream melambat. |
| **Fail-Closed vs Fail-Open pada Infrastruktur Redis** | **Fail-Closed**: Melindungi infrastruktur dari *overload* jika limit service mati. **Fail-Open**: Menjamin ketersediaan bisnis (*availability*) bagi pengguna akhir. | **Fail-Closed**: Request pengguna sah drop saat cache bermasalah. **Fail-Open**: Membuka potensi sistem backend jebol oleh serangan DoS. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Thundering Herd Akibat Retry Storm Synchronous
- **Anti-Pattern**: Klien mobile/frontend menerima HTTP 503 lalu mengulang request secara konstan setiap 1 detik tanpa delay acak. Jutaan request gagal kembali menabrak server tepat pada waktu yang identik.
- **Troubleshooting & Fix**: Terapkan header `Retry-After` dengan algoritma **Full Jitter**:
  $$Sleep = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$
  Paksa *jitter injection* pada SDK klien dan tolak request dari klien yang mengabaikan `Retry-After`.

#### 2. Redis Hotkey Saturation pada Cluster
- **Anti-Pattern**: Menggunakan satu kunci global statis seperti `rate:global:api` untuk membatasi traffic platform di kluster Redis.
- **Troubleshooting**: Seluruh throughput menabrak satu node master Redis (*hot shard*). Pisahkan kunci dengan skema sub-bucket berbasis hashing, misalnya `rate:global:api:{hash(ip) % 16}` dan agregasikan di sisi gateway, atau terapkan *Local In-Memory Pre-aggregation* sebelum flush ke Redis.

#### 3. Circuit Breaker Half-Open Flooding
- **Anti-Pattern**: Saat durasi timeout sirkuit habis, state bertransisi dari `OPEN` ke `HALF-OPEN`, namun sistem membiarkan seluruh ratusan request paralel yang datang langsung menerobos ke upstream.
- **Troubleshooting**: Batasi eksekusi probe saat status `HALF-OPEN` hanya untuk tepat 1 request tunggal (*canary probing*). Request lain harus tetap ditolak atau diarahkan ke skema *fallback* hingga status sirkuit terbukti sembuh (`CLOSED`).

#### 4. Clock Skew / Clock Drift pada Multi-Node Rate Limiting
- **Anti-Pattern**: Mengirimkan timestamp dari node aplikasi lokal ke skrip Redis untuk mengevaluasi window. Jika clock NTP server app berbeda 2 detik saja, sliding window rusak.
- **Troubleshooting**: Selalu gunakan fungsi internal Redis `redis.call('TIME')` di dalam skrip Lua atau pastikan daemon `chrony`/NTP terkonfigurasi dengan deviasi sub-milidetik di seluruh kluster komputasi.

---

### 11. Best Practices (Production Checklist)

- [ ] **IETF Compliant Headers**: Pastikan gateway menyematkan `RateLimit-Limit`, `RateLimit-Remaining`, dan `RateLimit-Reset` (atau `Retry-After` saat mengembalikan status code 429).
- [ ] **RFC 7807 Implementation**: Format body response error saat terkena rate limit harus menggunakan format terstandarisasi:
  ```json
  {
    "type": "https://api.example.com/errors/rate-limit-exceeded",
    "title": "Too Many Requests",
    "status": 429,
    "detail": "Quota of 100 requests per minute has been exhausted.",
    "instance": "/v1/orders/ORD-12345"
  }
  ```
- [ ] **Graceful Degradation Contract**: Siapkan payload fallback statis yang valid untuk degradasi fungsional (misal: data rekomendasi produk kosong ketimbang mengembalikan status HTTP 500).
- [ ] **Hash Tagging di Redis**: Selalu bungkus namespace pengelompokan kunci Redis dengan kurung kurawal `{...}` (contoh: `{user:891}:rate`) untuk menjaga pemrosesan multi-key Lua tetap berada dalam satu slot konsisten.
- [ ] **Fail-Open Strategy dengan Local Safe Limits**: Jika engine rate limiter terdistribusi mengalami kegagalan koneksi total, turunkan ke mekanisme cadangan *In-Memory Token Bucket* lokal per instance pod untuk mitigasi ledakan beban tanpa memutus alur bisnis.
- [ ] **Adaptive Deadlines / Context Propagation**: Lewatkan durasi timeout request melalui header konteks (`X-Request-Timeout` / gRPC context metadata). Jika timeout klien sisa 50ms sedangkan downstream butuh 200ms, segera lakukan *drop request* di awal (*Load Shedding*).

---

### 12. Hands-on Practice

Buatlah implementasi lengkap arsitektur resiliency pada path: `hands-on/m02/`

#### Struktur Proyek:
```
hands-on/m02/
├── go.mod
├── go.sum
├── main.go
├── ratelimiter/
│   ├── limiter.go
│   └── script.lua
└── circuitbreaker/
    └── breaker.go
```

#### Langkah 1: Inisialisasi Environment
Jalankan container Redis Cluster atau Redis Standalone lokal menggunakan Docker:
```bash
mkdir -p hands-on/m02/ratelimiter hands-on/m02/circuitbreaker
cd hands-on/m02
go mod init resiliency-demo
go get github.com/redis/go-redis/v9

# Jalankan Redis lokal via Docker
docker run -d --name redis-resiliency -p 6379:6379 redis:7.2-alpine
```

#### Langkah 2: Buat Skrip Lua Sliding Window
Simpan kode Lua yang ada pada seksi 7A ke dalam file `hands-on/m02/ratelimiter/script.lua`.

#### Langkah 3: Implementasikan Modul Limiter & Breaker
Salin arsitektur kode dari seksi 7B ke dalam masing-masing file paket terkait (`circuitbreaker/breaker.go` dan `ratelimiter/limiter.go`).

#### Langkah 4: Rangkai Server dan Skenario Uji Beban
Buat driver pengujian di `hands-on/m02/main.go` yang menjalankan endpoint HTTP `/api/checkout`, kemudian simulasikan *traffic spike* menggunakan utilitas benchmarking seperti `hey` atau `vegeta`:

```bash
# Install tool benchmark (contoh: hey)
go install github.com/rakyll/hey@latest

# Jalankan server
go run main.go

# Buka terminal lain: Kirim 500 request dalam konkurensi 50 worker
hey -n 500 -c 50 -H "X-Tenant-ID: client-vip" http://localhost:8080/api/checkout
```

Verifikasi bahwa response header `RateLimit-*` bergerak dinamis dan mengembalikan kode status 429 saat kuota tercapai, serta kode status 503 saat downstream buatan di-trigger untuk mengalami error/timeout.

---

### 13. Exercise

#### Level Easy
Ubah implementasi *Sliding Window Lua Script* agar mendukung batasan berjenjang (tiered limits):
- Izinkan limit 10 RPS untuk request *Read* (GET).
- Terapkan limit ketat 2 RPS untuk request *Write* (POST/PUT/DELETE) pada tenant key yang sama.
- *Petunjuk*: Modifikasi script Lua untuk menerima argumen *weight* (bobot request).

#### Level Medium
Tambahkan mekanisme **Dynamic Weighting** pada *Adaptive Concurrency Limiter*:
- Implementasikan sebuah *middleware* pengukur beban memori runtime (`runtime.ReadMemStats`).
- Jika alokasi heap memori server melampaui ambang batas 85%, sistem harus secara dinamis mengalikan waktu kalkulasi latensi rata-rata ($W$) sebesar 1.5x, sehingga memicu pemangkasan kapasitas in-flight request lebih cepat sebelum memicu *Out-Of-Memory (OOM) Killer*.

#### Level Hard
Rancang dan bangun sistem **Distributed Quota Synchronization**:
- Hilangkan panggilan Redis per request. Implementasikan *local token bucket* di dalam instance aplikasi Go.
- Instance lokal mengambil kuota (*lease batch*) sebesar 100 token dari Redis setiap interval 1 detik.
- Jika instance berjalan melebihi alokasi sebelum waktu sewa berakhir, instance meminta *burst expansion* ke Redis.
- Atasi kondisi *node crash*: token yang telah di-lease oleh node yang mati harus otomatis hangus (*expire via TTL*) tanpa menyebabkan kebocoran alokasi global permanen.

---

### 14. Challenge

**Skenario Tantangan Produksi (Zero-Downtime Multi-Region Failover Storm):**

Sebuah sistem perbankan multi-region aktif-aktif (Region AP-Southeast-1 dan Region AP-East-1) terhubung melalui *WAN replication link* dengan latensi antar-region 60ms.

Anda ditugaskan merancang arsitektur rate limiting dan traffic shaping dengan kriteria ketat berikut:
1. **Zero Global Drift**: Kuota transaksi penarikan dana nasabah dipatok maksimal 5 transaksi per menit secara global lintas region untuk mencegah penipuan *double withdrawal*.
2. **WAN Link Severance (Partition Isolation)**: Jika jalur koneksi antar-region putus total (Split-Brain scenario):
   - Sistem **dilarang keras** mengizinkan lebih dari kuota asal (5 transaksi/menit).
   - Sistem tidak boleh mati (*remain highly available* untuk operasi read non-moneter).
3. **Overhead Latency Constraint**: P99 pemrosesan transaksi normal saat region terhubung sehat tidak boleh bertambah lebih dari 5 milidetik.

**Instruksi Deliverable:**
Rancang arsitektur data layer, mekanisme sinkronisasi state rate limiter, state machine konsensus, dan skema mitigasi request fallback. Sajikan detail analisis trade-off matematis dan operasional Anda tanpa mengorbankan konsistensi finansial.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic Concepts
1. Mengapa algoritma *Fixed Window Counter* berpotensi meloloskan traffic hingga 2x dari batas kuota yang ditentukan?
2. Sebutkan status HTTP yang tepat menurut RFC 6585 untuk mengabarkan bahwa batas kuota pengguna telah habis, dan header apa yang wajib disertakan untuk memberitahu durasi jeda yang harus diambil klien?
3. Apa perbedaan esensial dari cara kerja algoritma *Token Bucket* dibandingkan dengan *Leaky Bucket*?
4. Dalam arsitektur Circuit Breaker, apa yang memicu transisi status dari `OPEN` ke `HALF-OPEN`?
5. Mengapa penambahan *Jitter* pada formula *Exponential Backoff* sangat krusial saat menangani kegagalan sistem downstream berskala masif?

#### Bagian B: Intermediate Architecture
6. Bagaimana cara kerja perhitungan estimasi request pada algoritma *Sliding Window Counter* yang menggunakan representasi memori konstan $O(1)$?
7. Jelaskan bagaimana Little's Law ($L = \lambda \times W$) dimanfaatkan dalam sistem *Adaptive Concurrency Limiting* untuk menentukan batas kelebihan beban tanpa metrik ambang statis.
8. Mengapa pada kluster Redis kita wajib menggunakan format *Hash Tag* (contoh: `{tenant_A}:metric`) saat mengeksekusi skrip Lua yang memanipulasi lebih dari satu key?
9. Apa bahaya arsitektur yang muncul jika kita menerapkan kebijakan *Fail-Closed* pada distributed rate limiter API publik skala besar ketika kluster Redis mengalami *out-of-memory crash*?
10. Dalam kondisi apa teknik isolasi *Bulkhead* lebih unggul dalam menjaga ketersediaan aplikasi dibandingkan dengan *Rate Limiting* biasa?

#### Bagian C: Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice mengalami peningkatan p99 latency secara dramatis dari 100ms menjadi 5 detik sesaat setelah circuit breaker ditutup (`CLOSED`) dari masa pemulihan (`HALF-OPEN`). Seluruh resource pod langsung terkuras. Identifikasi kesalahan konfigurasi pada state machine sirkuit tersebut dan bagaimana solusi arsitekturnya.
12. **Skenario 2**: Sistem Anda menerapkan Redis terpusat untuk rate limiting di 5 region global. Pengguna di region terjauh mengeluhkan API terasa lambat meskipun backend server di region lokal memiliki response time 10ms. Profiling menunjukkan ada penambahan delay 150ms pada setiap request API. Bagaimana Anda merestrukturisasi topologi rate limiting tersebut?
13. **Skenario 3**: Sebuah API Gateway mengembalikan HTTP 429 ke ribuan bot scraper. Namun, tim SRE melaporkan penggunaan CPU API Gateway justru melonjak hingga 98% dan memori server menipis drastis, hingga gateway tumbang. Analisis apa yang terjadi di layer socket/TCP/in-memory gateway dan bagaimana mengatasinya.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A
1. **Fixed Window Vulnerability**: Karena traffic dapat terkonsentrasi penuh di paruh akhir window 1 (misal 100 request di detik ke-59) dan dilanjutkan di paruh awal window 2 (100 request di detik ke-60). Secara fixed window per menit keduanya legal, namun dalam interval rentang 2 detik sebenarnya terjadi lonjakan 200 request (2x limit).
2. **Status & Header**: Status code `HTTP 429 Too Many Requests`. Header wajib: `Retry-After` (menunjukkan jumlah detik atau format HTTP-date kapan request berikutnya boleh dicoba kembali).
3. **Token Bucket vs Leaky Bucket**: Token bucket mengakumulasi token sehingga memungkinkan pemrosesan burst traffic jangka pendek hingga batas kapasitas bucket. Leaky bucket menampung request dalam antrean dan mengeluarkannya ke downstream pada laju kecepatan yang konstan (*smooth output rate*), memotong/membuang burst seketika jika buffer penuh.
4. **Transisi OPEN ke HALF-OPEN**: Terpicunya batas waktu tunggu (sleep timeout window) sejak sirkuit pertama kali trip/open, menandakan saatnya sistem memberikan izin sementara (*canary probe*) untuk menguji apakah dependensi hilir sudah pulih.
5. **Urgensi Jitter**: Mencegah fenomena *Thundering Herd* atau *Retry Storm*. Tanpa jitter, ribuan klien yang gagal di detik yang sama akan menghitung durasi backoff eksponensial yang persis identik, lalu menyerang backend server secara serentak di waktu yang sama berulang-ulang.

#### Bagian B
6. **Sliding Window Counter O(1)**: Menggabungkan nilai absolut hitungan request di jendela waktu berjalan dengan fraksi proporsional bobot hitungan di jendela waktu sebelumnya berdasarkan sisa offset waktu berjalan:
   $$\text{Count} = \text{Current} + \left( \text{Previous} \times \frac{\text{Window} - \text{Offset}}{\text{Window}} \right)$$
7. **Little's Law pada Concurrency**: Kapasitas beban stabil sistem terikat pada laju throughput dikalikan rata-rata waktu pemrosesan. Saat downstream terdegradasi, latensi ($W$) melonjak naik. Untuk menjaga throughput tetap optimal tanpa membebani antrean memori, kapasitas in-flight request ($L$) harus segera dipangkas secara proporsional.
8. **Hash Tag Redis Cluster**: Redis Cluster mengalokasikan data ke dalam 16.384 *hash slots*. Eksekusi atomik skrip Lua yang melibatkan banyak key mengharuskan seluruh key tersebut berada pada slot node fisik yang identik. Hash tag `{...}` memastikan Redis hanya menghitung nilai hashing dari string di dalam tanda kurung kurawal.
9. **Dampak Bahaya Fail-Closed**: Ketika kluster Redis down, policy *Fail-Closed* akan menganggap ketiadaan respons Redis sebagai kondisi limit habis. Akibatnya, seluruh request dari pengguna valid di seluruh dunia akan langsung ditolak mentah-mentah (100% outage pada API bisnis), mengubah masalah cache menjadi downtime platform total.
10. **Keunggulan Bulkhead**: Rate limiting membatasi frekuensi request masuk secara agregat atau identitas, tetapi tidak melindungi penggunaan resource thread/koneksi saat salah satu dependensi internal macet. Bulkhead mempartisi resource pool (misal thread/connection) secara terisolasi, sehingga kerusakan pada resource dependensi A tidak akan menghabiskan resource pool dependensi B.

#### Bagian C (Kasus Produksi)
11. **Analisis Skenario 1**: 
    - *Penyebab*: Ambang transisi *Half-Open* membiarkan banjir request (*unmetered load*) langsung masuk sebelum kesehatan dependensi terbukti stabil, atau tidak ada batasan kuota probe (tidak ada *canary stage*). Akibatnya, dependensi hilir yang baru bangun langsung dihantam beban normal dan kembali ambruk seketika.
    - *Solusi Arsitektur*: Terapkan *Single-Probe Canary Gating* saat Half-Open (hanya 1 request diuji coba). Implementasikan *gradual traffic ramp-up* (mengalirkan traffic secara bertahap mulai dari 5%, 10%, hingga 100% kapasitas secara linear dalam durasi observasi pemulihan).
12. **Analisis Skenario 2**:
    - *Penyebab*: Terjadi penalti latensi fisik akibat *cross-region WAN hop*. Instance backend di region lokal dipaksa melakukan sinkronisasi I/O synchronous ke instance Redis terpusat yang berada di benua lain pada setiap request.
    - *Solusi Arsitektur*: Pindahkan arsitektur rate limiter ke model *Local In-Memory Rate Limiting* di masing-masing region menggunakan algoritma *Token Lease/Batch Quota*. Alokasikan pecahan kuota global ke server lokal per region secara asinkron. Evaluasi request lokal berjalan dengan waktu < 1ms menggunakan memory internal node.
13. **Analisis Skenario 3**:
    - *Penyebab*: API Gateway menolak request dengan HTTP 429 di level aplikasi namun tetap membiarkan koneksi TCP/TLS terbuka (*connection keep-alive*) serta mengalokasikan buffer memory untuk payload respons lengkap JSON RFC 7807 ke puluhan ribu koneksi penyerang. Hal ini memicu kelaparan memori (*file descriptor & socket buffer exhaustion*).
    - *Solusi Arsitektur*: Integrasikan rate limiting di layer paling depan (L4/L7 Reverse Proxy edge / eBPF / iptables / Envoy network filter). Jika IP terdeteksi melakukan penyerangan masif berulang, langsung lakukan *TCP Connection Drop* atau kirim status HTTP 429 dengan header `Connection: close` tanpa menyertakan body verbose untuk segera menutup soket kernel.

---

### 16. Summary

Penerapan *traffic shaping* dan *resiliency* di level enterprise bukan sekadar memasang batas numerik RPS statis pada middleware. Arsitektur produksi modern membutuhkan pendekatan multi-tier yang terkoordinasi:

1. **Layer Edge (Gateway/Mesh)** melindungi platform dari serangan volumetrik melalui limitasi terdistribusi atomik berbasis skrip Lua Redis dengan pola *Sliding Window Counter* yang efisien memori.
2. **Layer Komputasi Internal (Microservices)** memanfaatkan *Adaptive Concurrency Limiting* berlandaskan prinsip Little's Law, menggeser batas konkurensi secara dinamis untuk mencegah penumpukan beban (*queue bloat*) dan bahaya *cascading failures*.
3. **Layer Klien dan Integrasi Downstream** diisolasi dengan ketat menggunakan *Bulkhead Pools*, *Circuit Breakers* berbasis FSM kanari, serta peredaman *retry storm* melalui skema *Truncated Exponential Backoff with Full Jitter*.

Ketahanan sistem yang tangguh (*high resiliency*) diperoleh dari penerimaan fakta bahwa kegagalan parsial (*partial failure*) dan lonjakan beban ekstrem adalah keniscayaan dalam sistem terdistribusi. Keberhasilan arsitektur diukur dari kemampuannya untuk mendegradasi fungsionalitas secara teratur (*graceful degradation*) tanpa pernah mengalami *total platform collapse*.