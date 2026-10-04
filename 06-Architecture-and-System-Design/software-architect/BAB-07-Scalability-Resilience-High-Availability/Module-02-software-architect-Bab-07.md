# BAB 07: Scalability, Resilience, & High Availability
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengimplementasikan** pola ketahanan terdistribusi tingkat lanjut (*Advanced Resilience Patterns*): *Adaptive Concurrency Limiting*, *Sliding-Window Circuit Breakers*, *Thread-Pool/Semaphore Bulkheads*, dan *Token Bucket Rate Limiting* terdistribusi.
- **Merancang Arsitektur Multi-Region Active-Active**: Mengatasi tantangan *split-brain*, replikasi data asinkron vs sinkron, resolusi konflik (*Conflict-Free Replicated Data Types* / CRDTs, *Last-Write-Wins*), serta routing lalu lintas global berbasis Anycast BGP dan DNS Latency-Based Routing.
- **Mencegah & Mengatasi *Cascading Failures***: Menerapkan mekanisme *load shedding*, *graceful degradation*, *circuit breaking telemetry*, dan *exponential backoff* dengan *full jitter*.
- **Mengukur & Memvalidasi Ketahanan Sistem**: Mendesain eksperimen *Chaos Engineering* otomatis di *production pipeline* untuk membuktikan *Recovery Time Objective* (RTO) $\le 30$ detik dan *Recovery Point Objective* (RPO) $\approx 0$.
- **Mengevaluasi Trade-off Konsistensi dan Ketersediaan**: Menerapkan teorema PACELC dalam pemilihan komponen penyimpanan terdistribusi untuk sistem berkinerja tinggi (*sub-millisecond latency*).

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta diasumsikan telah memiliki pemahaman mendalam tentang:
- Konsep dasar skalabilitas: Skalabilitas Horisontal vs Vertikal, *Stateless vs Stateful Services*.
- Fondasi Jaringan & Komunikasi: Model OSI, protokol TCP/IP, HTTP/2, HTTP/3 (QUIC), gRPC, serta mekanisme *connection pooling*.
- Dasar Teorema Distributed Systems: Teorema CAP, konsistensi eventual (*eventual consistency*), ACID vs BASE.
- Kemampuan membaca dan menulis kode sistem (*systems programming*) menggunakan Go, Java, atau Rust, serta pemahaman tentang konkurensi (*goroutines/threads*, *mutex*, *atomics*, *channels*).
- Pengalaman operasional dasar: Docker, Kubernetes primitives (*Deployments*, *Services*, *Probes*), dan reverse proxy/load balancer (Nginx, Envoy, atau HAProxy).

---

### 3. Concept & Internal Architecture

Membangun arsitektur *enterprise-grade* yang tahan banting membutuhkan pemahaman mendalam tentang bagaimana komponen sistem berinteraksi di bawah tekanan ekstrem (*under load*), kegagalan parsial (*partial failure*), dan degradasi jaringan (*network partitions*).

#### 3.1. Anatomi Kegagalan Kaskade (Cascading Failures)

Kegagalan kaskade terjadi ketika degradasi kecil pada suatu dependensi memicu rentetan kegagalan di seluruh topologi sistem melalui loop umpan balik positif (*positive feedback loop*).

```
[Normal State]
Client ---> Gateway (100 rps) ---> Service A (10ms) ---> Service B (5ms)

[Degradasi Dimulai: Service B mengalami latensi tinggi akibat GC pause / DB lock]
Client ---> Gateway (100 rps) ---> Service A (Menunggu B, latensi melonjak ke 2000ms)
                                     |
                                     +-> Thread Pool Service A Habis (Thread Starvation)
                                     +-> Antrean Memori Membengkak -> OOM Crash!

[Kaskade Berjalan: Gateway kehabisan socket/worker pool]
Gateway kehabisan file descriptors -> 504 Gateway Timeout -> Client me-retry serentak!
(Thundering Herd / Retry Storm memusnahkan sisa infrastruktur yang masih hidup)
```

Faktor pemicu utama kegagalan kaskade:
1. **Resource Saturation**: Kehabisan *threads*, *file descriptors* (FD), *connection pool*, atau memori heap.
2. **Aggressive Retries without Backoff**: Klien membanjiri kluster yang sedang sakit dengan jutaan request duplikat (*Retry Storm*).
3. **Queue Build-up (Bufferbloat)**: Antrean pesan/request yang tidak berbatas (*unbounded queue*) meningkatkan latensi secara eksponensial hingga batas *timeout* terlampaui sebelum request sempat diproses.

#### 3.2. Advanced Circuit Breaker: Sliding-Window Metrics & State Machine

Circuit Breaker modern (misalnya, Envoy Breaker atau Resilience4j) tidak lagi mengandalkan penghitung statis berbasis waktu (*time-bucket counters*) yang rentan terhadap *spikes* palsu, melainkan menggunakan algoritma **Sliding Window Counter** atau **Leaky Bucket Metrics**.

```
State Machine Circuit Breaker:

      +-------------------------------------------------------+
      |                                                       |
      v                                                       |
+-----------+       Failure Rate > Threshold      +----------+ | Health Check OK
|  CLOSED   | ----------------------------------> |   OPEN   | | (atau Probe Success Rate
+-----------+                                     +----------+ |  mencapai threshold)
      ^                                                 |      |
      |             Probe Request Success               |      |
      |          +--------------------------------------+      |
      |          |                                             |
      |          v                                             |
+--------------------+       Probe Request Failed              |
|     HALF-OPEN      | ----------------------------------------+
+--------------------+ (Reset ke OPEN; gandakan backoff duration)
```

- **Sliding-Window Metrics Implementation**: 
  - *Count-based*: Mempertahankan ring buffer berukuran $N$. Mengukur persentase kegagalan pada $N$ request terakhir.
  - *Time-based*: Membagi jendela waktu $T$ menjadi $M$ *buckets*. Metrik diputar secara dinamis untuk menghindari pembersihan metrik secara kasar (*hard reset*) yang menimbulkan jeda pengukuran (*metric blindness*).
- **Failure Types**: Tidak hanya HTTP status code 5xx, tetapi juga *Slow Calls* (panggilan yang memakan waktu melebihi batas persentil $p99$).

#### 3.3. Isolation Primitives: Bulkhead Pattern

Bulkhead mengisolasi sumber daya komputasi agar kegagalan pada domain kritis rendah (*low-tier domain*) tidak melumpuhkan domain kritis tinggi (*mission-critical domain*).

1. **Thread-Pool Isolation**: Setiap downstream target memiliki dedicated thread-pool.
   - *Kelebihan*: Isolasi total, dapat mengelola asynchronous dispatch, kegagalan terisolasi di level OS thread.
   - *Kekurangan*: Overhead *context switching*, alokasi stack memory per thread.
2. **Semaphore / Concurrency Limiting Isolation**: Menggunakan atomic counter tanpa alokasi thread baru.
   - *Kelebihan*: Sangat ringan, alokasi memori minimal, *zero context-switch overhead*.
   - *Kekurangan*: Bersifat sinkron; thread eksekusi utama terblokir jika request lambat, sehingga membutuhkan mekanisme *timeout* non-blocking yang presisi di layer I/O.

#### 3.4. Adaptive Concurrency Limiting (Bukan Rate Limiting Statis)

Batas kapasitas statis (*static rate limits*) sering kali salah: terlalu rendah menyebabkan penolakan request padahal server masih idle; terlalu tinggi menyebabkan *server crash*. *Adaptive Concurrency Limiting* menerapkan teori kendali kemacetan jaringan (seperti TCP Vegas atau BBR) ke tingkat layer aplikasi (RPC/HTTP).

Didasarkan pada **Hukum Little (Little's Law)**:
$$L = \lambda \times W$$
Di mana:
- $L$ = Concurrency (jumlah request yang sedang diproses di dalam sistem)
- $\lambda$ = Throughput (kapasitas pemrosesan server per satuan waktu)
- $W$ = Latency / Round-Trip Time (waktu eksekusi rata-rata per request)

Algoritma adaptif memonitor perubahan nilai $W$ minimum ($RTT_{min}$) dan mengkalkulasi batas konkurensi optimal secara dinamis:
$$\text{Limit}_{t+1} = \text{Limit}_t + \alpha \quad (\text{jika } RTT \le RTT_{min})$$
$$\text{Limit}_{t+1} = \text{Limit}_t \times \beta \quad (\text{jika } RTT > RTT_{min} \cdot \gamma)$$
Di mana $\alpha$ adalah laju penambahan linier (*additive increase*), $\beta$ adalah faktor reduksi multiplikatif (*multiplicative decrease*), dan $\gamma$ adalah toleransi deviasi latensi (biasanya 1.1–1.2).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Pendekatan Enterprise Resilient |
| :--- | :--- | :--- |
| **Penanganan Error** | Retry langsung (Hard retry) secara sinkron | Exponential Backoff dengan Jitter + Circuit Breaker terdistribusi |
| **Kapasitas Beban** | Rate limit statis per endpoint (misal: 100 RPS) | Adaptive Concurrency Limiting berbasis latensi sistem aktual |
| **Isolasi Sumber Daya**| Shared connection pool & default execution pool | Bulkhead per tenant/dependensi dengan Semaphore atomic |
| **Penanganan Kelebihan Beban**| Antrean request tanpa batas (*Unbounded Queue*) | *Load Shedding* agresif & *Queue Time Bounds* (CoDel) |
| **Ketersediaan Wilayah**| Active-Passive (Cold/Warm Standby via DNS Failover) | Active-Active Multi-Region dengan CRDT / Conflict-Resolution |
| **Validasi Arsitektur**| Load test berkala di environment staging | Continuous Chaos Engineering & Automated Fault Injection di Production |

#### Business & Operational Impact
- **Mencegah Kerugian Finansial Masif**: Downtime pada sistem inti perbankan atau platform e-commerce dapat bernilai ribuan dolar per detik.
- **Memenuhi SLA Ekstrem**: Mencapai ketersediaan *Four Nines* (99.99% $\approx 52.6$ menit downtime/tahun) atau *Five Nines* (99.999% $\approx 5.26$ menit downtime/tahun) mustahil dicapai tanpa isolasi kesalahan otomatis dan failover tanpa intervensi manusia (*zero-touch auto-failover*).

---

### 5. How: Workflow Detail

#### 5.1. Alur Penanganan Request dengan Zero-Loss Resilience Pipeline

```
[Incoming Request]
        |
        v
[Layer 1: Distributed Rate Limiter] (Redis Sliding Window / Token Bucket)
  |- Limit Exceeded? ---> [HTTP 429 Too Many Requests] (Tolak di edge)
        | OK
        v
[Layer 2: Adaptive Concurrency Limit & Load Shedder] (TCP Vegas / Little's Law)
  |- In-Flight >= Max Concurrency? ---> [HTTP 503 Overloaded] (Drop request sedini mungkin)
        | OK
        v
[Layer 3: Bulkhead Isolation Unit] (Semaphore Check per Domain)
  |- Semaphore Acquire Failed? ---> [Fallback / Fast Fail]
        | OK
        v
[Layer 4: Sliding-Window Circuit Breaker]
  |- State == OPEN? ---> [Fallback Response / Error Cached]
  |- State == HALF-OPEN / CLOSED?
        |
        v
[Execution: Call Downstream Service via Timeout Context]
  |- Context Timeout Terlampaui? ---> Cancel I/O, Rekam Metrik Latensi Tinggi
  |- Sukses? ---> Rekam Metrik Sukses, Kembalikan Response
  |- Gagal (5xx)? ---> Rekam Metrik Kegagalan
        |
        v
[Post Execution: Evaluasi State Circuit Breaker & Update Limit Konkurensi Adaptif]
```

#### 5.2. Alur Resolusi Multi-Region Active-Active State

1. **Ingress Routing**: Permintaan pengguna diarahkan ke edge node terdekat melalui Anycast BGP. Jika suatu region mati, konvergensi Anycast merutekan paket ke region alternatif dalam hitungan detik.
2. **Replikasi Data Lintas Region**:
   - *Synchronous Multi-Region* (Google Spanner / CockroachDB): Menggunakan protokol konsensus Raft/Paxos. Memberikan jaminan konsistensi ketat (*Linearizability*), namun latensi tulis dibatasi oleh kecepatan cahaya antar-region ($\approx 50-100\text{ms}$).
   - *Asynchronous Replication with Conflict Resolution*: Menggunakan basis data berbasis Dynamo (AWS DynamoDB Global Tables, Apache Cassandra). Latensi tulis lokal instan ($<5\text{ms}$), namun membuka celah inkonsistensi sementara (*eventual consistency*).
3. **Resolusi Konflik Tulis**:
   - Jika terjadi pembaruan bersamaan pada Region A dan Region B untuk entitas yang sama:
     - Pendekatan 1: **CRDTs (Conflict-Free Replicated Data Types)** seperti PN-Counters, LWW-Element-Set, atau RGA (Replicated Growable Array).
     - Pendekatan 2: **Deterministic State Machine / Vector Clocks** untuk mendeteksi divergensi dan memicu logika rekonsiliasi domain level.

---

### 6. Analogy & Diagram ASCII

#### 6.1. Analogi: Sistem Sekat Kapal Laut (The Bulkhead Analogy)

Bayangkan sebuah kapal kargo trans-samudera. Jika lambung kapal dibangun sebagai satu kompartemen raksasa terbuka, satu kebocoran kecil akibat benturan karang akan membanjiri seluruh lambung dan menenggelamkan kapal.
Arsitektur kapal modern membagi lambung menjadi bilik-bilik kedap air (*bulkheads*). Jika kompartemen nomor 3 bocor, air laut tertahan hanya di kompartemen tersebut. Kompartemen 1, 2, 4, dan 5 tetap kering dan kedap udara. Kapal tetap dapat berlayar ke pelabuhan darurat.

Dalam arsitektur mikroservis:
- **Kompartemen Bocor**: Downstream service katalog rekomendasi mengalami memory leak.
- **Bulkhead**: Alokasi pool koneksi/semaphore terpisah untuk rekomendasi vs pembayaran.
- **Hasil**: Sistem rekomendasi mati total, namun transaksi pembayaran *checkout* pelanggan tetap berjalan mulus.

#### 6.2. Diagram Topologi Multi-Region Active-Active

```
                         [Internet User Base]
                                  |
               +------------------+------------------+
               | Anycast IP / Geo-DNS Router         |
               +------------------+------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
  [Region 1: ap-southeast-1]                      [Region 2: ap-northeast-1]
+-----------------------------------+           +-----------------------------------+
|  [Edge Envoy / API Gateway]       |           |  [Edge Envoy / API Gateway]       |
|  - Rate Limiting (Local Envoy)    |           |  - Rate Limiting (Local Envoy)    |
|  - Adaptive Concurrency Limiter   |           |  - Adaptive Concurrency Limiter   |
|                 |                 |           |                 |                 |
|                 v                 |           |                 v                 |
|      [Order Core Services]        |           |      [Order Core Services]        |
|      - Circuit Breaker            |           |      - Circuit Breaker            |
|      - Bulkhead Isolated Pools    |           |      - Bulkhead Isolated Pools    |
|                 |                 |           |                 |                 |
|                 v                 |           |                 v                 |
|  [Local DB Node] (Master-Local)   | <=======> |  [Local DB Node] (Master-Local)   |
|                 |                 |  Cross-   |                 |                 |
|                 v                 |  Region   |                 v                 |
|  [Replication Engine / CRDT / LWW]|  Async    |  [Replication Engine / CRDT / LWW]|
|                                   |  Stream   |                                   |
+-----------------------------------+           +-----------------------------------+
```

---

### 7. Implementation: Simple & Practical Example

Berikut adalah implementasi sistem produksi tingkat lanjut dalam bahasa Go yang menggabungkan:
1. **Adaptive Sliding Window Circuit Breaker** (berbasis ring-buffer mutex-free via atomic).
2. **Backpressure & Semaphore-based Bulkhead**.
3. **Exponential Backoff dengan Full Jitter**.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"math"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"
)

// ============================================================================
// 1. BACKOFF WITH FULL JITTER IMPLEMENTATION
// Formula: Sleep = rand(0, min(cap, base * 2^attempt))
// ============================================================================

type Backoff struct {
	Base time.Duration
	Cap  time.Duration
}

func (b *Backoff) Duration(attempt int) time.Duration {
	if attempt < 0 {
		attempt = 0
	}
	// Mencegah integer overflow pada pergeseran bit (2^attempt)
	mult := math.Pow(2, float64(attempt))
	temp := float64(b.Base) * mult
	if temp > float64(b.Cap) || temp < 0 {
		temp = float64(b.Cap)
	}
	sleep := rand.Float64() * temp
	return time.Duration(sleep)
}

// ============================================================================
// 2. SLIDING-WINDOW METRIC BUCKET (CIRCUIT BREAKER CORE)
// ============================================================================

type State int32

const (
	StateClosed State = iota
	StateHalfOpen
	StateOpen
)

func (s State) String() string {
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

type CallResult struct {
	Success bool
	Latency time.Duration
}

type CircuitBreakerConfig struct {
	WindowSize          int           // Jumlah sampel request di sliding window
	FailureRateThreshold float64       // Ambang batas persentase kegagalan (0.0 - 1.0)
	SlowCallLatency     time.Duration // Latensi yang dikategorikan sebagai lambat
	SlowCallThreshold   float64       // Ambang batas persentase panggilan lambat
	CooldownInterval    time.Duration // Waktu tunggu sebelum pindah dari OPEN ke HALF-OPEN
	HalfOpenMaxRequests int           // Jumlah probe request pada kondisi HALF-OPEN
}

type AdvancedCircuitBreaker struct {
	config CircuitBreakerConfig
	state  int32 // Atomic State

	mu          sync.Mutex
	window      []CallResult
	windowIndex int
	windowFull  bool

	lastStateChange time.Time
	halfOpenProbes  int
}

func NewAdvancedCircuitBreaker(cfg CircuitBreakerConfig) *AdvancedCircuitBreaker {
	return &AdvancedCircuitBreaker{
		config:          cfg,
		state:           int32(StateClosed),
		window:          make([]CallResult, cfg.WindowSize),
		lastStateChange: time.Now(),
	}
}

func (cb *AdvancedCircuitBreaker) GetState() State {
	return State(atomic.LoadInt32(&cb.state))
}

func (cb *AdvancedCircuitBreaker) AllowRequest() bool {
	currentState := cb.GetState()
	now := time.Now()

	if currentState == StateOpen {
		cb.mu.Lock()
		defer cb.mu.Unlock()
		// Recheck setelah lock
		if State(cb.state) == StateOpen {
			if now.Sub(cb.lastStateChange) > cb.config.CooldownInterval {
				atomic.StoreInt32(&cb.state, int32(StateHalfOpen))
				cb.lastStateChange = now
				cb.halfOpenProbes = 0
				return true
			}
			return false
		}
	}

	if currentState == StateHalfOpen {
		cb.mu.Lock()
		defer cb.mu.Unlock()
		if cb.halfOpenProbes < cb.config.HalfOpenMaxRequests {
			cb.halfOpenProbes++
			return true
		}
		return false
	}

	return true
}

func (cb *AdvancedCircuitBreaker) RecordExecution(latency time.Duration, err error) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	currentState := State(cb.state)
	success := (err == nil)

	if currentState == StateHalfOpen {
		if !success {
			// Probe gagal, kembalikan ke OPEN, reset interval pendinginan
			atomic.StoreInt32(&cb.state, int32(StateOpen))
			cb.lastStateChange = time.Now()
			return
		}
		// Jika semua probe sukses pada fase half-open, kembali ke CLOSED
		if cb.halfOpenProbes >= cb.config.HalfOpenMaxRequests {
			atomic.StoreInt32(&cb.state, int32(StateClosed))
			cb.lastStateChange = time.Now()
			cb.resetWindow()
		}
		return
	}

	// Fase CLOSED: Rekam metrik pada Sliding Window Ring Buffer
	cb.window[cb.windowIndex] = CallResult{
		Success: success,
		Latency: latency,
	}
	cb.windowIndex++

	if cb.windowIndex >= cb.config.WindowSize {
		cb.windowIndex = 0
		cb.windowFull = true
	}

	totalSamples := cb.config.WindowSize
	if !cb.windowFull {
		totalSamples = cb.windowIndex
	}

	// Evaluasi metrik hanya jika sampel minimum terpenuhi
	if totalSamples >= (cb.config.WindowSize / 2) {
		var failures, slowCalls int
		for i := 0; i < totalSamples; i++ {
			if !cb.window[i].Success {
				failures++
			} else if cb.window[i].Latency > cb.config.SlowCallLatency {
				slowCalls++
			}
		}

		failureRate := float64(failures) / float64(totalSamples)
		slowRate := float64(slowCalls) / float64(totalSamples)

		if failureRate >= cb.config.FailureRateThreshold || slowRate >= cb.config.SlowCallThreshold {
			atomic.StoreInt32(&cb.state, int32(StateOpen))
			cb.lastStateChange = time.Now()
		}
	}
}

func (cb *AdvancedCircuitBreaker) resetWindow() {
	cb.windowIndex = 0
	cb.windowFull = false
}

// ============================================================================
// 3. SEMAPHORE BULKHEAD PATTERN
// ============================================================================

type Bulkhead struct {
	sem chan struct{}
}

func NewBulkhead(maxConcurrentCalls int) *Bulkhead {
	return &Bulkhead{
		sem: make(chan struct{}, maxConcurrentCalls),
	}
}

var ErrBulkheadFull = errors.New("bulkhead capacity reached: shedding load")
var ErrCircuitBreakerOpen = errors.New("circuit breaker is OPEN: downstream degraded")

func (b *Bulkhead) Execute(ctx context.Context, fn func() error) error {
	select {
	case b.sem <- struct{}{}:
		defer func() { <-b.sem }()
		return fn()
	case <-ctx.Done():
		return ctx.Err()
	default:
		return ErrBulkheadFull
	}
}

// ============================================================================
// 4. RESILIENT SERVICE EXECUTION ENGINE
// ============================================================================

type ResilientExecutor struct {
	breaker  *AdvancedCircuitBreaker
	bulkhead *Bulkhead
	backoff  Backoff
}

func NewResilientExecutor(breaker *AdvancedCircuitBreaker, bulkhead *Bulkhead) *ResilientExecutor {
	return &ResilientExecutor{
		breaker:  breaker,
		bulkhead: bulkhead,
		backoff: Backoff{
			Base: 10 * time.Millisecond,
			Cap:  500 * time.Millisecond,
		},
	}
}

func (r *ResilientExecutor) Run(ctx context.Context, action func(ctx context.Context) error) error {
	if !r.breaker.AllowRequest() {
		return ErrCircuitBreakerOpen
	}

	start := time.Now()
	err := r.bulkhead.Execute(ctx, func() error {
		return action(ctx)
	})

	r.breaker.RecordExecution(time.Since(start), err)
	return err
}

// ============================================================================
// 5. DEMONSTRASI PENGUJIAN PRODUKSI
// ============================================================================

func main() {
	rand.Seed(time.Now().UnixNano())

	// Inisialisasi Breaker: 10 sampel, buka jika gagal >= 40% atau slow call >= 50%
	breakerCfg := CircuitBreakerConfig{
		WindowSize:           10,
		FailureRateThreshold: 0.4,
		SlowCallLatency:      50 * time.Millisecond,
		SlowCallThreshold:    0.5,
		CooldownInterval:     500 * time.Millisecond,
		HalfOpenMaxRequests:  2,
	}
	breaker := NewAdvancedCircuitBreaker(breakerCfg)
	bulkhead := NewBulkhead(5) // Maksimal 5 eksekusi konkuren simultan
	executor := NewResilientExecutor(breaker, bulkhead)

	ctx := context.Background()

	// Simulasi beban downstream dengan kegagalan bertahap
	for i := 1; i <= 30; i++ {
		reqID := i
		go func() {
			err := executor.Run(ctx, func(c context.Context) error {
				// Simulasi error sintetis setelah request ke-10
				if reqID > 10 && reqID < 22 {
					time.Sleep(10 * time.Millisecond)
					return errors.New("rpc error: internal server error")
				}
				time.Sleep(5 * time.Millisecond)
				return nil
			})

			status := "SUCCESS"
			if err != nil {
				status = fmt.Sprintf("FAILED [%v]", err)
			}
			fmt.Printf("Req %02d | State: %-9s | Status: %s\n", reqID, breaker.GetState(), status)
		}()
		time.Sleep(30 * time.Millisecond)
	}

	// Biarkan cooldown interval terlampaui untuk memeriksa transisi ke HALF-OPEN
	time.Sleep(800 * time.Millisecond)
	fmt.Printf("\n--- Cooldown Selesai: Menguji Transisi Half-Open ---\n")

	for i := 31; i <= 35; i++ {
		reqID := i
		err := executor.Run(ctx, func(c context.Context) error {
			time.Sleep(5 * time.Millisecond)
			return nil // Layanan downstream telah sembuh
		})
		status := "SUCCESS"
		if err != nil {
			status = fmt.Sprintf("FAILED [%v]", err)
		}
		fmt.Printf("Req %02d | State: %-9s | Status: %s\n", reqID, breaker.GetState(), status)
		time.Sleep(50 * time.Millisecond)
	}
}
```

---

### 8. Real World Case Study: Payment Processing Platform (AWS AZ Blackhole Incident)

#### Latar Belakang
Sebuah payment unicorn di Asia Tenggara memproses 8.500 transaksi per detik ($tps$) pada peak season. Arsitektur terdiri dari 45 mikroservis terdistribusi yang berjalan di atas Kubernetes (EKS) yang mencakup 3 Availability Zones (`ap-southeast-1a`, `1b`, `1c`).

#### Insiden (The Blackhole Event)
Pada pukul 14:02 UTC, salah satu AZ (`ap-southeast-1b`) mengalami *gray network failure* internal AWS: paket keluar mengalami drop sebesar 70%, namun link fisik tetap berstatus "UP". Health check bawaan Kubernetes L4 TCP tetap lolos karena *handshake* sesekali berhasil, tetapi latensi pemrosesan panggilan HTTP/gRPC internal melonjak dari 15ms menjadi 45.000ms (timeout).

#### Dampak Awal
- Dalam waktu 45 detik, thread pool pada Ingress Gateway terkuras habis menunggu response dari pod di AZ `1b`.
- Terjadi *cascading connection starvation* ke database Postgres backend. Transaksi global anjlok dari 8.500 TPS ke 210 TPS (97.5% drop).

#### Solusi Arsitektural yang Diterapkan
1. **Penerapan Envoy Outlier Detection (Client-Side Breaker)**:
   - Envoy sidecar dikonfigurasi untuk mengevaluasi consecutive 5xx errors ($5$ error beruntun). Pod yang berada di AZ yang sakit secara otomatis dikeluarkan (*ejected*) dari load-balancing pool lokal dalam 100ms.
2. **AZ-Affinity dengan Cross-AZ Spillover**:
   - Komunikasi mikroservis diutamakan dalam AZ yang sama (*same-zone routing*) untuk menghemat biaya latensi.
   - Apabila success-rate di AZ lokal berada di bawah 95%, sistem *spillover* secara deterministik merutekan sisa traffic ke AZ `1a` dan `1c`.
3. **Queue Delay-Based Shedding (CoDel Algorithm)**:
   - Request yang telah menunggu di antrean gateway selama lebih dari 500ms langsung dibatalkan (*dropped*) dengan status HTTP 503 tanpa pernah dikirimkan ke downstream worker.

#### Hasil Validasi
Pada pengujian *Chaos Engineering* berikutnya dengan menginjeksikan latensi acak dan packet drop 80% pada AZ `1b`, sistem secara otomatis mendegradasi kapasitas hanya sebesar 33% selama 1.2 detik, sebelum traffic dialihkan penuh ke AZ `1a` dan `1c`. Ketersediaan global dipertahankan pada **99.98%**.

---

### 9. Trade-offs: Architecture Matrix

| Parameter Desain | Synchronous Strict (Multi-Region Raft/Paxos) | Asynchronous Eventual (Multi-Master / CRDT) | Hybrid (Local Sync + Async Global) |
| :--- | :--- | :--- | :--- |
| **Write Latency** | Tinggi ($60 - 150\text{ms}$) karena dependensi round-trip WAN | Sangat Rendah ($1 - 5\text{ms}$ ke storage lokal) | Rendah lokal, batching teragregasi global |
| **Read Consistency** | *Linearizable* / Strict Serializability | *Eventual Consistency* (resiko membaca *stale data*) | Read-your-own-writes per session |
| **RPO (Recovery Point)** | $\mathbf{0}$ (Data terjamin tidak hilang) | $\mathbf{> 0}$ (Data dalam buffer replikasi WAN dapat hilang) | $\approx \mathbf{0}$ untuk data finansial; $>0$ non-kritis |
| **RTO (Recovery Time)** | Menit ke Sub-detik (Otomatis sesuai algoritma pemilihan leader) | Detik (Otomatis; tidak ada dependensi leader WAN) | Detik ke Menit (Tergantung propagasi DNS/BGP) |
| **Kompleksitas Kode** | Rendah di level aplikasi (ditangani storage engine) | **Sangat Tinggi** (Aplikasi wajib menangani deduplikasi & merge conflict) | Moderat |
| **Biaya Komputasi & Jaringan**| Tinggi (Cross-region inter-node chatters konstan) | Moderat (Event-driven streaming via Kafka/WAN) | Terkendali |

---

### 10. Common Mistakes & Troubleshooting

#### Anti-Pattern 1: The "Retry Amplification" Avalanche
- **Kesalahan**: Menambahkan interceptor retry otomatis pada setiap layer hierarki servis (misal: Frontend $\to$ Gateway $\to$ Service A $\to$ Service B $\to$ Service C). Setiap layer memiliki konfigurasi 3x retry.
- **Gejala Fatal**: Jika Service C mengalami error, 1 panggilan dari Frontend akan menghasilkan $1 \times 3 \times 3 \times 3 = 27$ panggilan ke Service C. Beban backend membengkak secara eksponensial $O(R^D)$ di mana $R$ adalah jumlah retry dan $D$ adalah kedalaman downstream.
- **Remediasi**:
  - Terapkan **Retry Budget**: Klien hanya boleh me-retry maksimal 10% dari total request aktif.
  - Terapkan retry **hanya pada satu layer** (biasanya di edge client atau gateway, bukan di intermediate RPC layers).
  - Sertakan metadata gRPC / HTTP Header `X-Retry-Count` untuk mencegah downstream me-retry ulang.

#### Anti-Pattern 2: Ping-Pong Failover (Split-Brain Oscillation)
- **Kesalahan**: Mengatur ambang batas kegagalan failover terlalu sensitif pada DNS/Health Checker global (misal: 3 request gagal langsung pindahkan traffic seluruh region).
- **Gejala**: Region A terindikasi down sesaat karena lonjakan CPU sementara. Traffic dipindahkan ke Region B. Region B menerima lonjakan traffic mendadak (*thundering herd*), mengalami crash, sehingga sistem memindahkan traffic kembali ke Region A. Terjadi osilasi tanpa henti.
- **Remediasi**:
  - Gunakan **Hysteresis**: Kriteria untuk menyatakan node mati harus lebih longgar daripada kriteria untuk menyatakan node sembuh.
  - Implementasikan *gradual traffic shifting* (Canary Routing: 5% $\to$ 25% $\to$ 100%) alih-alih *hard switchover* 100%.

#### Panduan Troubleshooting Degradasi Sistem Produksi (RCA Runbook)
1. **Langkah 1 (Deteksi Antrean)**: Periksa metrik `Container CPU Throttling` dan `Thread Pool Active Count`. Jika antrean penuh tapi CPU rendah, sistem mengalami *I/O Lock Contention* atau kebuntuan dependensi downstream.
2. **Langkah 2 (Cek Latensi Persentil)**: Bandingkan latensi $p50$ dengan $p99$. Jika $p50$ tetap 5ms tetapi $p99$ melonjak ke 10.000ms, jangan tingkatkan skala pod (*horizontal scaling* tidak akan membantu); ini adalah tanda *Head-of-Line Blocking* atau GC Long Pause. Aktifkan Circuit Breaker *Slow Call Threshold*.
3. **Langkah 3 (Eksekusi Load Shedding Darurat)**: Jika gateway mulai kehabisan memori, instruksikan gateway untuk langsung membuang (*drop*) request yang bersifat sekunder (misal: tracking analitik, background refresh) menggunakan *HTTP 503 Service Unavailable with Retry-After Header*.

---

### 11. Best Practices & Production Checklist

#### Checklist Arsitektur Produksi High-Availability
- [ ] **Batas Timeout Eksplisit**: Tidak ada satupun pemanggilan HTTP/gRPC, Redis, atau SQL client yang menggunakan konfigurasi *infinite/zero timeout*.
- [ ] **Jitter pada Backoff**: Semua algoritma retry mengintegrasikan Full Jitter acak untuk menghindari sinkronisasi gelombang request klien.
- [ ] **Dual-Level Health Checking**:
  - *Liveness Probe*: Ringan, hanya memastikan proses runtime tidak mengalami deadlock (jangan menyertakan pengecekan DB di sini).
  - *Readiness Probe*: Memvalidasi ketersediaan pool koneksi dan dependensi kritis lokal sebelum menerima traffic.
- [ ] **Circuit Breaker Sliding Window**: Menggunakan metrik persentil dan kegagalan terdistribusi; bukan penghitung sederhana berbasis interval waktu global.
- [ ] **Load Shedding Otomatis**: Layanan membuang request di antrean jika waktu tunggu antrean (*queue residency time*) melebihi batas SLA yang ditentukan.
- [ ] **Graceful Degradation Fallbacks**: Setiap integrasi non-kritis memiliki mekanisme fallback statis atau data cache kadaluarsa (*stale-while-revalidate*).
- [ ] **Rate Limiter Multi-Tier**: Rate limit diimplementasikan di level WAF/Edge (IP-based), Gateway (User Token-based), dan Service-to-Service (mTLS Identity-based).

---

### 12. Hands-on Practice: Membangun Resilient Ingress Pipeline

Latihan ini akan memandu Anda membuat pipeline simulasi arsitektur tahan banting secara lokal dengan skenario stress-testing langsung.

#### Struktur Direktori
Simpan seluruh file praktikum di: `hands-on/m02/`

```text
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── go.mod
├── main.go
└── test-resilience.sh
```

#### Langkah 1: Inisialisasi Modul Go
Di dalam direktori `hands-on/m02/`, jalankan:
```bash
go mod init resilience-lab
```

#### Langkah 2: Buat Implementasi Server (`main.go`)
Gunakan kode pada Bagian 7 dari modul ini sebagai `main.go`. Tambahkan HTTP server endpoint:

```go
// Tambahkan di akhir file main.go:
package main

import (
	"encoding/json"
	"net/http"
	"strconv"
)

func runHTTPServer() {
	breakerCfg := CircuitBreakerConfig{
		WindowSize:           20,
		FailureRateThreshold: 0.5,
		SlowCallLatency:      100 * time.Millisecond,
		SlowCallThreshold:    0.5,
		CooldownInterval:     2 * time.Second,
		HalfOpenMaxRequests:  3,
	}
	breaker := NewAdvancedCircuitBreaker(breakerCfg)
	bulkhead := NewBulkhead(10)
	executor := NewResilientExecutor(breaker, bulkhead)

	http.HandleFunc("/api/v1/checkout", func(w http.ResponseWriter, r *http.Request) {
		injectLatency, _ := strconv.Atoi(r.URL.Query().Get("latency_ms"))
		injectFail, _ := strconv.ParseBool(r.URL.Query().Get("fail"))

		err := executor.Run(r.Context(), func(ctx context.Context) error {
			if injectLatency > 0 {
				time.Sleep(time.Duration(injectLatency) * time.Millisecond)
			}
			if injectFail {
				return errors.New("database transaction locked")
			}
			return nil
		})

		w.Header().Set("Content-Type", "application/json")
		if err != nil {
			if errors.Is(err, ErrCircuitBreakerOpen) {
				w.WriteHeader(http.StatusServiceUnavailable)
				json.NewEncoder(w).Encode(map[string]string{"error": "circuit_open", "msg": err.Error()})
				return
			}
			if errors.Is(err, ErrBulkheadFull) {
				w.WriteHeader(http.StatusTooManyRequests)
				json.NewEncoder(w).Encode(map[string]string{"error": "shedding_load", "msg": err.Error()})
				return
			}
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": "execution_failed", "msg": err.Error()})
			return
		}

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "transaction_completed"})
	})

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	println("Resilient Server listening on :8080...")
	http.ListenAndServe(":8080", nil)
}
```
*(Ubah fungsi `main()` agar memanggil `runHTTPServer()`)*

#### Langkah 3: Shell Script Pengujian Beban (`test-resilience.sh`)
Buat script untuk memicu transisi state dari CLOSED $\to$ OPEN $\to$ SHEDDING $\to$ HALF-OPEN $\to$ CLOSED:

```bash
#!/usr/bin/env bash
set -e

ENDPOINT="http://localhost:8080/api/v1/checkout"
echo "=== 1. Mengirim Traffic Normal ==="
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code}\n" "$ENDPOINT"
done

echo "=== 2. Menginjeksi Kegagalan (Memicu Circuit Breaker Buka) ==="
for i in {1..25}; do
  curl -s -o /dev/null -w "%{http_code}\n" "$ENDPOINT?fail=true"
done

echo "=== 3. Memverifikasi Circuit Breaker Mengisolasi Sistem (Expect 503) ==="
curl -s -w "\nHTTP Response Code: %{http_code}\n" "$ENDPOINT"

echo "=== 4. Tunggu Cooldown Interval (2.5 Detik)... ==="
sleep 2.5

echo "=== 5. Mengirim Traffic Sehat (Transisi Half-Open -> Closed) ==="
for i in {1..5}; do
  curl -s -o /dev/null -w "%{http_code}\n" "$ENDPOINT"
  sleep 0.1
done

echo "Pengujian selesai dengan sukses!"
```

---

### 13. Exercises

#### Level 1 (Easy): Inisialisasi Ring Buffer Metrics
- **Tugas**: Tambahkan metrik *Success Rate* ke dalam struktur data Ring Buffer Circuit Breaker yang telah dibangun di atas.
- **Kriteria Keberhasilan**: Program dapat mengekspos persentase keberhasilan secara real-time melalui endpoint `/metrics` dengan format JSON sederhana.

#### Level 2 (Medium): Dynamic Token Bucket Rate Limiter
- **Tugas**: Rancang middleware rate limiting terdistribusi berbasis algoritma Token Bucket yang mengintegrasikan sliding expiration. Middleware harus membaca batas limit dinamis per tenant dari HTTP Header `X-Tenant-ID`.
- **Kriteria Keberhasilan**: Tenant A dengan alokasi 10 RPS dibatasi saat request ke-11 masuk dalam 1 detik yang sama, tanpa mempengaruhi kuota Tenant B (alokasi 100 RPS).

#### Level 3 (Hard): Adaptive Load Shedder dengan Little's Law
- **Tugas**: Modifikasi kode Bulkhead pada Bagian 7. Ubah batas kapasitas dari ukuran fixed integer menjadi dinamis yang dihitung menggunakan *Little's Law Engine*. Engine harus menghitung latensi rata-rata dari 100 request terakhir secara periodik, dan menyesuaikan jumlah channel semaphore yang diperbolehkan secara dinamis saat sistem mendeteksi lonjakan latensi.
- **Kriteria Keberhasilan**: Ketika downstream disimulasikan melambat dari 10ms ke 500ms, sistem secara otomatis mereduksi kapasitas semaphore untuk mempertahankan footprint memori tetap di bawah 100MB tanpa crash OOM.

---

### 14. Architecture Challenge: The Global Flash-Sale Dilemma

#### Deskripsi Kasus Ambigu
Anda adalah Lead Enterprise Architect untuk platform tiket konser global. Bintang pop dunia akan meluncurkan penjualan tiket serentak di 4 benua: London (Region EU-West), Virginia (Region US-East), Singapura (Region AP-Southeast), dan Tokyo (Region AP-Northeast).

#### Aturan & Batasan Bisnis:
1. **Total Kapasitas Kursi**: Tepat 80.000 kursi di satu stadion fisik (Singapura).
2. **Karakteristik Beban**: Diperkirakan 2.000.000 pengguna akan menekan tombol "Bayar Sekarang" pada detik ke-0 secara serentak dari seluruh penjuru dunia.
3. **Persyaratan Inkonsistensi Nol**: *Overselling* (menjual kursi yang sama ke lebih dari 1 orang) adalah pelanggaran hukum berat dan mengakibatkan pembatalan konser oleh regulator.
4. **Latency Budget**: Pengguna di London tidak boleh mengalami latency checkout $>3000\text{ms}$ atau generic HTTP 500/504 error screens.
5. **Kondisi Ekstrem**: Asumsikan kabel bawah laut Pasifik mengalami degradasi pada jam penjualan, menyebabkan packet drop 20% dan latensi antar benua melonjak hingga 400ms antar region.

#### Pertanyaan Arsitektur yang Harus Dijawab:
1. Bagaimana Anda merancang alokasi inventaris tiket di tingkat database multi-region tanpa terkena penalti *distributed locking* (Two-Phase Commit) lintas benua yang lambat?
2. Bagaimana topologi layer ingress dan buffering Anda diorganisir untuk membuang (*shed*) kelebihan beban 1.920.000 request tanpa menumbangkan edge infrastructure?
3. Mekanisme konsistensi apa yang Anda pilih untuk memastikan *inventory decrement* sepenuhnya deterministik di tengah ancaman partisi jaringan trans-Atlantik/Pasifik?

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Apa perbedaan mendasar antara pola *Rate Limiting* dan *Circuit Breaker*?
   - A. Rate Limiting melindungi downstream; Circuit Breaker melindungi upstream.
   - B. Rate Limiting mengontrol kecepatan masuknya traffic berdasarkan kuota; Circuit Breaker menghentikan aliran request ke sistem downstream yang terdeteksi sedang mengalami kegagalan/degradasi.
   - C. Rate Limiting hanya bekerja di layer transport TCP; Circuit Breaker bekerja eksklusif di HTTP/REST.
   - D. Circuit Breaker tidak dapat dikombinasikan dengan Exponential Backoff.
   *Kunci Jawaban: B. Rate limiter mengontrol kuota incoming rate; Circuit breaker menghentikan pemanggilan ke dependensi downstream yang sakit agar memiliki ruang untuk pulih.*

2. Algoritma exponential backoff tanpa jitter memiliki kelemahan kritis berupa:
   - A. Penggunaan alokasi memori yang eksponensial.
   - B. Kegagalan thread untuk di-wake-up oleh scheduler OS.
   - C. Terjadinya fenomena *Thundering Herd* / gelombang retry yang tersinkronisasi di downstream service.
   - D. Penurunan persentil p99 secara artifisial.
   *Kunci Jawaban: C. Tanpa jitter (keacakan waktu), seluruh klien yang gagal serentak akan me-retry pada interval waktu eksponensial yang persis sama, menciptakan lonjakan traffic berulang.*

3. Manakah yang mendeskripsikan isolasi *Bulkhead* berbasis Semaphore dibandingkan Thread Pool?
   - A. Semaphore mengalokasikan OS thread baru untuk setiap request.
   - B. Semaphore mengeksekusi request pada thread pemanggil (*calling thread*) dan hanya membatasi jumlah eksekusi konkuren melalui atomic counter.
   - C. Semaphore memiliki overhead context-switching yang jauh lebih besar dibanding Thread Pool.
   - D. Semaphore secara native mendukung asynchronous request dispatch tanpa blocking.
   *Kunci Jawaban: B. Semaphore tidak membuat thread baru melainkan membatasi konkurensi pada thread yang sedang berjalan, menjadikannya sangat hemat memori.*

4. Formula matematis manakah yang menjadi fondasi *Adaptive Concurrency Limiting* dalam menyeimbangkan latensi dan throughput?
   - A. Teorema Bayes
   - B. Persamaan Navier-Stokes
   - C. Hukum Little ($L = \lambda \times W$)
   - D. Hukum Amdahl
   *Kunci Jawaban: C. Hukum Little menghubungkan konkurensi (L), throughput ($\lambda$), dan response time/latensi (W).*

5. Dalam siklus hidup Circuit Breaker, peran dari state `HALF-OPEN` adalah:
   - A. Menolak seluruh traffic yang masuk dan mematikan pod secara permanen.
   - B. Mengizinkan sejumlah kecil request uji coba (*trial probes*) melewati breaker untuk memvalidasi apakah downstream service telah pulih.
   - C. Mengalihkan semua request ke backup storage secara paralel.
   - D. Membagi antrean menjadi dua zona memori yang berbeda.
   *Kunci Jawaban: B. State HALF-OPEN berfungsi sebagai fase probing terbatas sebelum memutuskan untuk kembali ke state CLOSED atau OPEN.*

---

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Arsitektur)

6. Pada arsitektur Multi-Region Active-Active dengan basis data berbasis *Last-Write-Wins* (LWW), resiko integritas data terbesar muncul akibat:
   - A. Ukuran payload JSON yang terlalu besar pada WAN.
   - B. Perbedaan jam fisik antarsistem (*Clock Drift*) yang dapat menimpa data yang sebenarnya lebih mutakhir dengan data basi yang memiliki timestamp salah.
   - C. Hilangnya koneksi DNS Anycast.
   - D. Ketidakmampuan database mengeksekusi index B-Tree pada cluster multi-node.
   *Kunci Jawaban: B. Clock drift pada server fisik menyebabkan perbandingan timestamp lokal tidak akurat, sehingga pembaruan data yang valid dapat tertimpa secara permanen oleh operasi yang lebih lawas.*

7. Mengapa penggunaan antrean tak terbatas (*unbounded queue*) pada worker thread pool di depan dependensi yang lambat dianggap sebagai anti-pattern fatal?
   - A. Karena dapat memicu *Bufferbloat*, peningkatan latensi drastis di atas batas timeout, dan ancaman crash *Out-of-Memory* (OOM).
   - B. Karena unbounded queue menyebabkan starvation pada prosesor GPU.
   - C. Karena unbounded queue mengharuskan penggunaan algoritma Two-Phase Commit.
   - D. Karena JVM/Go runtime secara otomatis mematikan program jika antrean menampung lebih dari 1024 objek.
   *Kunci Jawaban: A. Antrean tak terbatas menyerap traffic tanpa batas, meningkatkan waktu antre di atas batas timeout klien, dan menghabiskan memori heap server hingga crash.*

8. Di bawah teorema PACELC, jika suatu sistem database terdistribusi diklasifikasikan sebagai **PA/EL**, maka perilakunya adalah:
   - A. Jika terjadi Partition: pilih Availability; Else: pilih Latency rendah dibanding Consistency.
   - B. Jika terjadi Partition: pilih Agreement; Else: pilih Linearizability.
   - C. Jika terjadi Partition: batalkan Availability; Else: abaikan Latency.
   - D. Seluruh transaksi wajib konsisten baik saat ada partisi maupun dalam kondisi normal.
   *Kunci Jawaban: A. Teorema PACELC: If Partition (P) choose Availability (A) or Consistency (C); Else (E) choose Latency (L) or Consistency (C).*

9. Mekanisme *Load Shedding* berbasis CoDel (*Controlled Delay*) mengambil keputusan penolakan request dengan mengevaluasi metrik:
   - A. Status response HTTP dari downstream target.
   - B. Waktu tunggu yang dihabiskan request di dalam antrean lokal sebelum mulai diproses (*Queue Sojourn Time*).
   - C. Utilisasi bandwidth antarmuka ethernet.
   - D. Jumlah baris data yang dihasilkan oleh query SQL.
   *Kunci Jawaban: B. CoDel memantau berapa lama sebuah paket/request terperangkap di dalam antrean; jika waktu tinggal minimum melebihi target, kelebihan request langsung dibuang.*

10. Ketika mengonfigurasi retry dengan interceptor gRPC pada sistem perbankan, operasi manakah yang **TIDAK PERNAH** boleh di-retry secara membabi buta tanpa pengecekan status?
    - A. Panggilan `GetAccountBalance` (Query Idempotent).
    - B. Panggilan `CheckCardStatus` (Query Idempotent).
    - C. Panggilan `DebitTransfer` tanpa passing parameter `Idempotency-Key` unik (Non-Idempotent Mutation).
    - D. Panggilan `ListBranchLocations` (Read-only Operation).
    *Kunci Jawaban: C. Operasi mutasi finansial non-idempotent tanpa Idempotency Key beresiko melakukan debit ganda pada akun nasabah jika terjadi network timeout di fase penerimaan response.*

---

#### Bagian 3: Production Case Scenarios (Analisis & Rekomendasi Solusi)

11. **Skenario Kasus 1: "The Ghost Failover"**
    *Kondisi*: Platform media streaming global menggunakan DNS Failover otomatis untuk dua region (US-East dan US-West). Saat US-East mengalami lonjakan beban singkat selama 40 detik akibat pertandingan final olahraga, health checker global mendeteksi peningkatan failure rate menjadi 15% dan langsung memindahkan 100% DNS record ke US-West. Dua puluh detik kemudian, US-West tumbang total (HTTP 500 menyeluruh), dan health checker memindahkan kembali traffic ke US-East yang belum stabil, menyebabkan *global outage* selama 45 menit.
    *Tugas Analisis*: Sebutkan **dua kesalahan arsitektur** pada setup failover tersebut dan berikan solusi perbaikannya!
    *Solusi yang Diharapkan*:
    - **Kesalahan 1**: *Binary Failover (All-or-Nothing)*. Mengalihkan 100% traffic secara instan ke region lain tanpa mempertimbangkan kapasitas maksimum (*headroom capacity*) region tujuan memicu overload instan (*thundering herd*).
    - **Kesalahan 2**: *Ketiadaan Hysteresis dan Flapping Damping*. Sistem terlalu reaktif terhadap degradasi sesaat (40 detik) dan tidak memiliki mekanisme stabilisasi untuk mencegah osilasi traffic bolak-balik.
    - **Perbaikan**: Implementasikan *Weighted Fractional Routing* (Canary Shifting bertahap 10%, 25%, 50%), kalkulasi kapasitas target sebelum pengalihan, dan terapkan cooldown lock minimum (misal: dilarang failover balik dalam waktu 15 menit).

12. **Skenario Kasus 2: "The Memory Leak Circuit Breaker"**
    *Kondisi*: Tim backend mengimplementasikan custom Sliding Window Circuit Breaker in-memory di service Go mereka. Saat diuji pada environment staging dengan 10 RPS, sistem berjalan sempurna. Namun saat dirilis ke production dengan beban 50.000 RPS, konsumsi memori pod melonjak dari 200MB menjadi 8GB dalam 10 menit, memicu Kubernetes OOMKilled berulang-ulang.
    *Tugas Analisis*: Telusuri akar masalah (*root cause*) struktural pada implementasi metrik circuit breaker tersebut dan bagaimana cara merevisinya!
    *Solusi yang Diharapkan*:
    - **Akar Masalah**: Penggunaan slice atau list dinamis tanpa alokasi tetap yang menyimpan objek request/error secara individual per panggilan. Pada 50.000 RPS, alokasi objek menghasilkan jutaan alokasi heap baru per detik yang membebani garbage collector (GC pressure) dan memicu fragmentasi memori.
    - **Perbaikan**: Ganti struktur data dinamis dengan **Ring Buffer Berukuran Tetap** (*Pre-allocated Fixed-size Circular Array*) atau *Bucketized Counters* (misal: 60 bucket untuk 60 detik) dengan manipulasi nilai primitif secara atomic (`sync/atomic`), menghilangkan alokasi heap baru secara keseluruhan pada hot path eksekusi.

13. **Skenario Kasus 3: "Cascading Deadlock di Microservice Mesh"**
    *Kondisi*: Terdapat relasi dependensi sirkular tersembunyi: Service A memanggil Service B untuk verifikasi checkout; Service B memanggil Service C untuk validasi diskon; Service C memanggil kembali Service A via endpoint internal untuk memverifikasi profil tier pengguna. Ketika beban transaksi meningkat, ketiga service tersebut mengalami kebuntuan (*deadlock*) di mana seluruh connection pool habis, dan request terhenti hingga mencapai global timeout 60 detik.
    *Tugas Analisis*: Bagaimana Anda merestrukturisasi interaksi arsitektur ini untuk menghilangkan potensi kebuntuan permanen tersebut?
    *Solusi yang Diharapkan*:
    - **Akar Masalah**: Keberadaan *Distributed Circular Dependency* (A $\to$ B $\to$ C $\to$ A) yang dieksekusi secara sinkron blocking. Saat throughput tinggi, thread pada Service A terkunci menunggu B, sementara thread pada Service A yang dibutuhkan oleh C untuk menyelesaikan rantai panggilan B tidak tersedia (*resource starvation deadlock*).
    - **Perbaikan Arsitektural**:
      1. **Eliminasi Siklus Sinkron**: Redesain batasan domain. Informasi tier profil pengguna harus dipassing sejak awal di dalam konteks request/token (misal: claim JWT atau Context Propagation Header) dari Service A ke B dan C, menghilangkan kebutuhan Service C untuk memanggil balik ke Service A.
      2. **Asynchronous Read Replicas / Caching**: Jika data tier harus diperbarui secara real-time, Service C harus membaca data tersebut dari shared distributed cache lokal (Redis) atau event log (Kafka CDC), bukan melalui HTTP RPC sinkron membalik ke upstream.

---

### 16. Summary

Membangun arsitektur enterprise dengan ketersediaan dan ketahanan tinggi (*High Availability & Resilience*) bukanlah sekadar menumpuk infrastruktur di banyak server atau region, melainkan seni **mengelola kegagalan secara anggun (*graceful failure management*)**. 

Pilar utama implementasi produksi:
1. **Asumsikan Semua Dependensi Pasti Gagal**: Rancang setiap integrasi sistem dengan batas waktu (*timeouts*), isolasi kapasitas (*bulkheads*), pemutus sirkuit (*circuit breakers*), dan backoff acak (*jittered backoff*).
2. **Kendalikan Beban Berdasarkan Kemampuan Nyata**: Tinggalkan rate limiting statis untuk proteksi internal sistem; gunakan *Adaptive Concurrency Limiting* dan *Load Shedding* agresif untuk membuang beban berlebih sedini mungkin demi menyelamatkan sistem inti.
3. **Pahami Batasan Fisik Distributed Systems**: Dalam topologi Multi-Region Active-Active, tidak ada kompromi gratis terhadap Teorema CAP dan PACELC. Latensi jaringan antar-benua adalah hukum fisika; pilih antara konsistensi data yang ketat dengan penalti latensi tulis, atau ketersediaan tinggi dengan arsitektur resolusi konflik data berbasis CRDT.
4. **Validasi Tanpa Henti**: Sistem yang tidak pernah diuji dengan kegagalan buatan (*Chaos Engineering*) di lingkungan produksi pada dasarnya adalah sistem yang sedang menunggu kegagalan nyata untuk melumpuhkannya. Kesiapan operasional dibuktikan melalui eksperimen, otomatisasi failover, dan observabilitas persentil yang presisi.