# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**BAB 09: Ketahanan Sistem & Observabilitas (System Resilience & Observability)**
**Jalur Pembelajaran: Software Design & Architecture (Tingkat Enterprise)**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Architect, Staff Engineer, dan Lead Developer diharapkan mampu:
- **Menganalisis dan Mendesain Sistem Self-Healing:** Mengimplementasikan pola ketahanan tingkat lanjut (*Adaptive Concurrency Limits*, *Dynamic Circuit Breaking*, *Thread/Semaphore Bulkhead*, *Hedged Requests*) untuk memitigasi kegagalan kaskade (*cascading failures*) dan *tail latency amplification*.
- **Mengarsitekturi Pipeline Observabilitas Skala Terdistribusi:** Mengonfigurasi dan mengoperasikan OpenTelemetry (OTel) Collector dengan strategi *tail-based sampling*, *context propagation* lintas batas asinkron (*message broker*), dan integrasi *exemplars* yang menghubungkan metrik, jejak (*trace*), dan log terstruktur.
- **Menguasai Mitigasi Masalah Kardinalitas Tinggi (*High Cardinality*):** Merancang skema penamaan metrik, agregasi dinamis, dan strategi *drop-filter* pada layer telemetri untuk mencegah *Out-of-Memory* (OOM) dan lonjakan biaya infrastruktur analitik telemetri.
- **Mengotomatisasi Validasi Ketahanan (*Chaos Engineering*):** Merancang eksperimen injeksi kegagalan otomatis (*latency injection*, *packet loss*, *partitioning*) pada *pipeline* CI/CD dan lingkungan *staging/production* untuk memverifikasi *Service Level Objectives* (SLO).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta harus menguasai:
1. **Dasar Ketahanan Sistem:** Pemahaman konsep *fail-fast*, *timeout*, *exponential backoff with full jitter*, dan *idempotency keys*.
2. **Dasar Observabilitas Tiga Pilar:** Memahami perbedaan mendasar antara *Log* terstruktur, *Metric* (Counter, Gauge, Histogram), dan *Distributed Tracing* (Trace ID, Span ID).
3. **Jaringan & Konkurensi Sistem Terdistribusi:** Model konkurensi berbasis *goroutine/thread pool*, protokol HTTP/2, gRPC (*multiplexing*), TCP *handshake*, serta W3C *Trace Context specification*.
4. **Bahasa Pemrograman:** Kemampuan membaca dan menulis kode idiomatik Go (*concurrency primitives, channels, atomic operations, context cancellation*).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Adaptive Concurrency Limits vs Static Rate Limiting

Kebanyakan sistem produksi gagal bukan karena ketiadaan *rate limiter*, melainkan karena penggunaan batas statis (*static thresholds*). Batas statis (misal: "maksimum 500 RPS") mengabaikan variasi latensi dependen internal:
- Jika downstream database melambat dari 5ms menjadi 50ms, *in-flight requests* bertambah 10 kali lipat untuk volume RPS yang sama.
- Hal ini menyebabkan kehabisan memori, *thread exhaustion*, dan kegagalan kaskade.

```
Hukum Little (Little's Law): L = λ × W
Dimana:
  L = Rata-rata konkurensi (Concurrency / In-Flight Requests)
  λ = Throughput (RPS)
  W = Rata-rata Latensi (Response Time)
```

Arsitektur produksi modern menggunakan algoritma kontrol kemacetan adaptif berbasis latensi (diadaptasi dari TCP Vegas atau CoDel), seperti **Additive Increase Multiplicative Decrease (AIMD)** atau **Gradient Concurrency Limit**:

$$\text{Gradient} = \frac{\text{RTT}_{\text{noload}}}{\text{RTT}_{\text{actual}}}$$

$$\text{Limit}_{t+1} = \text{Limit}_t \times \text{Gradient} + \text{QueueSize}$$

Jika latensi aktual naik melebihi baseline ($\text{RTT}_{\text{noload}}$), *Gradient* bernilai $< 1.0$, secara otomatis menurunkan batas kapasitas konkurensi sebelum buffer jaringan atau antrean memori mengalami saturasi (*bufferbloat*).

```
   Downstream Service Latency Profiler
                  │
                  ▼
         [RTT Actual Measure]
                  │
                  ├─── RTT <= RTT_noload ──► ConcurrencyLimit += AdditiveStep
                  │
                  └─── RTT > RTT_noload  ──► ConcurrencyLimit = ConcurrencyLimit * (RTT_noload / RTT)
                                                                 + Margin
```

### 3.2 Dynamic Circuit Breaker State Machine Internals

Circuit breaker tingkat produksi tidak sekadar menghitung rasio error HTTP 5xx sederhana. Implementasi enterprise menggunakan *rolling time-bucket ring buffer* dengan evaluasi berbasis minimum volume request dan ambang batas pelambatan (*slow-call percentage*).

```
                 ┌────────────────────────────────────────┐
                 │                                        │
                 ▼                                        │ Success Rate >= Threshold
         ┌───────────────┐   Trip Condition Met          ┌┴──────────────┐
         │               ├──────────────────────────────►│               │
  Init ─►│    CLOSED     │   (Error% / Latency%)         │     OPEN      │
         │               │                               │               │
         └───────▲───────┘                               └───┬───────────┘
                 │                                           │
                 │                                           │ Sleep Window
                 │                                           │ Expired
                 │                                           ▼
                 │       Probe Requests Pass           ┌───────────────┐
                 └─────────────────────────────────────┤               │
                         Probe Requests Fail           │   HALF-OPEN   │
                         ─────────────────────────────►│               │
                                                       └───────────────┘
```

Mekanisme Internal State Machine:
1. **CLOSED:** Permintaan dilewatkan secara penuh. Hasil eksekusi dicatat ke dalam *Circular Ring Buffer of Buckets* (misal: 10 bucket berdurasi 1 detik per window).
2. **OPEN:** Permintaan langsung di-reject secara instan (*fail-fast*) tanpa membuka koneksi jaringan, menghasilkan `ErrCircuitOpen`. Fallback dieksekusi jika disediakan.
3. **HALF-OPEN:** Setelah `SleepWindow` berakhir, sistem mengizinkan sejumlah terbatas kuota permintaan pengujian (*trial requests*). Jika tingkat keberhasilan memenuhi kuorum, status kembali ke `CLOSED`. Jika satu saja pengujian kritis gagal atau timeout terlampaui, breaker kembali ke `OPEN` untuk durasi cooldown berikutnya.

### 3.3 OpenTelemetry Context Propagation & Distributed Baggage Lifecycle

Trace propagation lintas batas proses bergantung pada injeksi dan ekstraksi metadata HTTP/gRPC headers berdasarkan standar W3C:
- `traceparent`: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01` (`version-trace_id-parent_id-trace_flags`)
- `tracestate`: Menyimpan informasi vendor-specific (*routing keys, tenant details*).
- `baggage`: Key-value pairs non-telemetri yang merambat ke seluruh dependensi downstream (contoh: `tenant_id=enterprise_corp_1;tier=premium`).

```
[Service A (Edge Gateway)]
   │
   ├─► Inject Trace Context into HTTP Header (`traceparent`, `baggage`)
   │
   ▼
[Message Broker (Kafka / RabbitMQ)]
   │
   ├─► Trace Context tersimpan di Message Metadata / Record Headers
   │
   ▼
[Service B (Async Consumer)]
   │
   ├─► Extract Trace Context from Record Headers
   ├─► Buat Span Baru dengan Parent Span ID dari Service A
   └─► Eksekusi proses bisnis (Konteks Trace tetap sinkron)
```

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Lingkungan Enterprise?
- **Pola Static Timeout Mengakibatkan Cascading Failure:** Jika Service A memiliki timeout 2 detik untuk Service B, dan Service B memiliki timeout 2 detik untuk Service C, maka akumulasi tail latency ditambah network transit time menyebabkan Service A melakukan timeout dan me-retry, sementara Service B dan C masih sibuk memproses request awal. Ini memicu lonjakan beban ganda (*thundering herd* dan *wasted work*).
- **Tail Latency Amplification:** Dalam sistem microservice dengan kedalaman graph pemanggilan $N=10$, jika komponen downstream memiliki 99th percentile ($P_{99}$) latensi sebesar 1 detik (1% lambat), maka probabilitas request pengguna akhir terkena dampak lambat adalah:
  
$$P(\text{at least one slow call}) = 1 - (1 - 0.01)^{10} = 1 - 0.904 = 9.56\%$$

Hampir 10% pengguna mengalami tail latency!
- **Blind Degradation:** Tanpa korelasi metrik dan jejak melalui distributed baggage dan exemplars, insinyur SRE menghabiskan waktu berjam-jam saat insiden hanya untuk mencari tahu mikroservis mana yang pertama kali mengalami degradasi performa.

### Apa Solusinya?
Menggabungkan mekanisme **Hedging / Speculative Retries**, **Context-Aware Deadline Propagation**, dan **Exemplar-Linked Observability Pipelines** yang memotong latensi ekstrem dan memberikan visibilitas instan ke akar masalah sistemik.

---

## 5. How (Workflow Detail)

Alur penanganan request resilient dan observable:

```
[Client Request]
       │
       ▼
[Dynamic Concurrency Gatekeeper] ─── (Rejected if Overloaded) ──► Return HTTP 429 / Fallback
       │
       ├─ (Accepted: Slot Allocated)
       ▼
[Distributed Context Propagation (Extract/Inject)]
       │
       ├─ Assign Root/Child Span + Attach Exemplar Metrics
       ▼
[Circuit Breaker Execution Wrapper] ─── (State: OPEN) ──────────► Return Circuit Breaker Error
       │
       ├─ (State: CLOSED / HALF-OPEN)
       ▼
[Hedged Request Engine]
       │
       ├─── Dispatch Primary Request ──────────────► [Downstream Dependency]
       │                                                      │
       └─── If (t > P95) & (Hedging Token Available)          │
                 │                                            │
                 ├── Dispatch Hedged Duplicate Request ───────┤
                 │                                            │
                 ▼                                            ▼
           [Race: Evaluasi Hasil Tercepat] ◄──────────────────┘
                 │
                 ├── Cancel Request yang Kalah via Context Cancellation
                 ├── Record RTT to Adaptive Concurrency Model
                 └── Emit Traces + Metrics + Baggage to OpenTelemetry Collector
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Sistem Kendali Pesawat Tempur Otomatis
Bayangkan sebuah pesawat tempur supersonik. Pilot manusia tidak dapat menyesuaikan ratusan sirip aerodinamis setiap milidetik secara manual (*Static Configuration*). Pesawat menggunakan sistem kendali *Fly-by-Wire* (*Adaptive Concurrency & Circuit Breaker*). 
- Jika sensor hidrolik mendeteksi getaran turbulensi ekstrem (*elevated latency/errors*), komputer pesawat secara dinamis membatasi sudut manuver (*shedding load*) guna mencegah kerusakan struktural (*system crash*).
- Black Box penerbangan (*OpenTelemetry*) merekam posisi tuas, arus listrik, dan kecepatan secara simultan dengan tanda waktu sinkron (*Trace Context*), sehingga ketika ada kejanggalan, teknisi tahu tuas mana yang memicu deviasi tanpa perlu menebak-nebak.

### Diagram Alur: Tail Latency Mitigation via Hedged Requests

```
Client         Hedged Engine                  Replica A (Slow)          Replica B (Fast)
  │                  │                                │                        │
  │──Invoke(Req)────►│                                │                        │
  │                  │──── Send Primary Req ─────────►│ (Stuck in GC Pause)    │
  │                  │                                │                        │
  │                  │  [Timer: P95 threshold met]    │                        │
  │                  │  [Check: Retry Token Valid]    │                        │
  │                  │                                │                        │
  │                  │──── Send Speculative Copy ─────────────────────────────►│
  │                  │                                │                        │
  │                  │◄─── Fast Response Received ─────────────────────────────│
  │                  │                                │                        │
  │                  │──── Cancel Context ───────────►│ (Abort Processing)     │
  │◄──Return Fast────│                                │                        │
  │   Response       │                                │                        │
```

---

## 7. Simple Example & Practical Example

Berikut implementasi produksi menggunakan bahasa **Go**. Kode mencakup integrasi **Resilience Engine (Adaptive Circuit Breaker + Concurrency Limiter)** dan **Distributed Telemetry Engine (OpenTelemetry Manual Tracing & Metric Exemplars)**.

### Implementasi: `resilience/engine.go`

```go
package resilience

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

var (
	ErrCircuitBreakerOpen = errors.New("circuit breaker is open; call rejected")
	ErrConcurrencyLimitExceeded = errors.New("concurrency limit saturated; call shed")
)

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

// EnterpriseResilienceEngine menggabungkan Adaptive Concurrency dan Circuit Breaker
type EnterpriseResilienceEngine struct {
	mu sync.RWMutex

	// Config
	failureThreshold float64
	recoveryTimeout  time.Duration
	minRequests      int64

	// Concurrency Limits (Adaptive TCP-Vegas-like model)
	currentConcurrency int64
	concurrencyLimit   int64

	// Breaker State
	state            CircuitState
	lastStateChange  time.Time
	successCount     int64
	failureCount     int64
	halfOpenSuccesses int64
	halfOpenMaxTrials int64
}

func NewEnterpriseResilienceEngine(failureThreshold float64, recoveryTimeout time.Duration, initialConcurrencyLimit int64) *EnterpriseResilienceEngine {
	return &EnterpriseResilienceEngine{
		failureThreshold:   failureThreshold,
		recoveryTimeout:    recoveryTimeout,
		concurrencyLimit:   initialConcurrencyLimit,
		state:              StateClosed,
		lastStateChange:    time.Now(),
		minRequests:        10,
		halfOpenMaxTrials:  5,
	}
}

// Execute mengeksekusi operasi terlindung dengan integrasi OTel Span
func (ere *EnterpriseResilienceEngine) Execute(ctx context.Context, span trace.Span, operation func(ctx context.Context) error) error {
	// 1. Pemeriksaan Concurrency Limiter
	curr := atomic.AddInt64(&ere.currentConcurrency, 1)
	defer atomic.AddInt64(&ere.currentConcurrency, -1)

	limit := atomic.LoadInt64(&ere.concurrencyLimit)
	span.SetAttributes(
		attribute.Int64("concurrency.current", curr),
		attribute.Int64("concurrency.limit", limit),
	)

	if curr > limit {
		span.RecordError(ErrConcurrencyLimitExceeded)
		span.SetAttributes(attribute.String("resilience.rejection_reason", "concurrency_limit_exceeded"))
		return ErrConcurrencyLimitExceeded
	}

	// 2. Evaluasi Kondisi Circuit Breaker
	if err := ere.beforeExecution(); err != nil {
		span.RecordError(err)
		span.SetAttributes(attribute.String("resilience.rejection_reason", "circuit_breaker_open"))
		return err
	}

	startTime := time.Now()
	err := operation(ctx)
	duration := time.Since(startTime)

	// 3. Catat feedback metrik ke state engine
	ere.afterExecution(err, duration)

	return err
}

func (ere *EnterpriseResilienceEngine) beforeExecution() error {
	ere.mu.Lock()
	defer ere.mu.Unlock()

	now := time.Now()
	if ere.state == StateOpen {
		if now.Sub(ere.lastStateChange) > ere.recoveryTimeout {
			ere.state = StateHalfOpen
			ere.lastStateChange = now
			ere.halfOpenSuccesses = 0
		} else {
			return ErrCircuitBreakerOpen
		}
	}
	return nil
}

func (ere *EnterpriseResilienceEngine) afterExecution(err error, duration time.Duration) {
	ere.mu.Lock()
	defer ere.mu.Unlock()

	now := time.Now()

	if ere.state == StateHalfOpen {
		if err == nil {
			ere.halfOpenSuccesses++
			if ere.halfOpenSuccesses >= ere.halfOpenMaxTrials {
				ere.state = StateClosed
				ere.lastStateChange = now
				ere.failureCount = 0
				ere.successCount = 0
				// Adaptively restore limits
				atomic.AddInt64(&ere.concurrencyLimit, 2)
			}
		} else {
			ere.state = StateOpen
			ere.lastStateChange = now
			// Adaptively penalize limits on failure
			newLimit := atomic.LoadInt64(&ere.concurrencyLimit) / 2
			if newLimit < 1 {
				newLimit = 1
			}
			atomic.StoreInt64(&ere.concurrencyLimit, newLimit)
		}
		return
	}

	if ere.state == StateClosed {
		if err != nil {
			ere.failureCount++
		} else {
			ere.successCount++
		}

		total := ere.failureCount + ere.successCount
		if total >= ere.minRequests {
			rate := float64(ere.failureCount) / float64(total)
			if rate >= ere.failureThreshold {
				ere.state = StateOpen
				ere.lastStateChange = now
			} else {
				// Rotasi window sederhana
				if total >= 100 {
					ere.failureCount = 0
					ere.successCount = 0
				}
			}
		}
	}
}

func (ere *EnterpriseResilienceEngine) GetState() string {
	ere.mu.RLock()
	defer ere.mu.RUnlock()
	return ere.state.String()
}
```

### Implementasi: Service Consumer dengan OpenTelemetry Context & Hedging

```go
package main

import (
	"context"
	"fmt"
	"math/rand"
	"net/http"
	"time"

	"resilience"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

var tracer trace.Tracer

func initTracer() (*sdktrace.TracerProvider, error) {
	exporter, err := stdouttrace.New(stdouttrace.WithPrettyPrint())
	if err != nil {
		return nil, err
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithBatcher(exporter),
	)
	otel.SetTracerProvider(tp)
	tracer = tp.Tracer("payment-gateway-resilience")
	return tp, nil
}

// Simulasi downstream microservice dengan latency tidak stabil (Long-Tail Latency)
func simulatedDownstreamCall(ctx context.Context) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(time.Duration(rand.Intn(200)) * time.Millisecond):
		// Simulasi probabilitas error 15%
		if rand.Float64() < 0.15 {
			return errors.New("HTTP 503: Service Unavailable")
		}
		return nil
	}
}

// HedgedExecution menjalankan speculative execution jika batas latency tertentu terlampaui
func HedgedExecution(ctx context.Context, tr trace.Tracer, operation func(ctx context.Context) error, hedgeDelay time.Duration) error {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	resChan := make(chan error, 2)

	// Primary call
	go func() {
		_, span := tr.Start(ctx, "Primary-Execution")
		defer span.End()
		resChan <- operation(ctx)
	}()

	// Hedged / Secondary call timer
	timer := time.NewTimer(hedgeDelay)
	defer timer.Stop()

	select {
	case err := <-resChan:
		return err
	case <-timer.C:
		// Primary terlalu lambat, jalankan hedged secondary invocation
		_, span := tr.Start(ctx, "Hedged-Speculative-Execution")
		defer span.End()
		span.AddEvent("Hedged call dispatched due to SLA breach")

		go func() {
			resChan <- operation(ctx)
		}()

		// Ambil respon pertama yang selesai (antara primary atau secondary)
		err := <-resChan
		return err
	case <-ctx.Done():
		return ctx.Err()
	}
}

func main() {
	tp, err := initTracer()
	if err != nil {
		panic(err)
	}
	defer func() { _ = tp.Shutdown(context.Background()) }()

	engine := resilience.NewEnterpriseResilienceEngine(0.3, 2*time.Second, 5)

	// Simulasi load test beruntun
	for i := 1; i <= 20; i++ {
		ctx, parentSpan := tracer.Start(context.Background(), fmt.Sprintf("Transaction-Job-%d", i))
		
		err := engine.Execute(ctx, parentSpan, func(execCtx context.Context) error {
			return HedgedExecution(execCtx, tracer, simulatedDownstreamCall, 80*time.Millisecond)
		})

		if err != nil {
			parentSpan.RecordError(err)
			fmt.Printf("[Req #%02d] FAILED: %v (State: %s)\n", i, err, engine.GetState())
		} else {
			parentSpan.SetAttributes(attribute.String("payment.status", "SUCCESS"))
			fmt.Printf("[Req #%02d] SUCCESS (State: %s)\n", i, engine.GetState())
		}

		parentSpan.End()
		time.Sleep(50 * time.Millisecond)
	}
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash Sale Payment Gateway Core Banking Degradation

#### Profil Sistem:
- **Throughput:** 120.000 Transaksi per Detik (TPS) pada *Peak Sale*.
- **Topologi:** Edge Gateway $\to$ Order Orchestrator $\to$ Payment Processing Core $\to$ External 3rd-Party Bank Consortia.

#### Insiden (Root Cause Failure):
Pada promo 11.11, salah satu sistem perbankan mitra mengalami saturasi thread pool internal. Latensi pemrosesan naik dari 80ms menjadi 12.000ms. 
1. Payment Processing Core tetap menahan koneksi TCP HTTP/1.1 yang terbuka.
2. Pool worker Payment Processing Core (kapasitas 8.000 thread) habis dalam waktu 700 milidetik.
3. Order Orchestrator mendeteksi connection timeout, lalu memicu fitur *retry* otomatis 3 kali secara serentak tanpa *jitter*.
4. Akibatnya, beban ke Payment Core melonjak menjadi 360.000 RPS (3x lipat). Terjadi kegagalan kaskade total: Payment Core OOM-Killed oleh Linux Kernel OS.

```
[Edge Gateway] 
      │ 
      ▼ (120k TPS)
[Order Orchestrator] ──(Blind Retries x3)──► [Payment Core (OOM Crash)]
                                                    │
                                                    ▼ (Latency 80ms -> 12,000ms)
                                             [Bank Consortia]
```

#### Solusi Arsitektural yang Diimplementasikan:
1. **Adaptive Deadlines & Distributed Cancellation:** 
   - Gateway menetapkan `Request-Timeout: 1500ms`.
   - Timeout disalurkan melalui context header (`X-Envoy-Expected-Rq-Timeout-Ms`). Jika sisa batas waktu tinggal < 200ms sebelum memanggil layer core banking, eksekusi downstream dibatalkan segera (*short-circuit cancellation*).
2. **Dynamic Concurrency Limits (Vegas Based) pada Orchestrator:**
   - Kapasitas thread pool diganti dengan Semaphore berbatas adaptif. Ketika median RTT bertambah, limit in-flight mengecil drastis, melempar respons cepat HTTP 429 dengan *Retry-After* header yang bervariasi.
3. **Speculative Hedging Terisolasi:**
   - Khusus metode pembayaran dengan multi-akuisisi, request paralel kedua (*hedged call*) dilepas hanya ke payment acquirer alternatif jika akuisisi utama belum merespon pada $P_{95}$ (150ms), dibatasi maksimal 2% dari total traffic menggunakan *hedging token bucket*.
4. **Tail-Based Sampling Observability:**
   - OTel Collector mengesampingkan trace HTTP 200 normal (disampling hanya 1%), tetapi **100% trace berlatensi > 1000ms atau berstatus HTTP 5xx direkam secara utuh beserta Log Exemplars**, memungkinkan tim insinyur mendeteksi bank acquirer mana yang bermasalah dalam 30 detik pertama.

---

## 9. Trade-offs (Arsitektur Komparatif)

Setiap mekanisme ketahanan dan observabilitas membawa kompromi sistemik (*architectural cost*).

| Pola Arsitektur | Keuntungan Utama | Biaya / Trade-off | Dampak Latensi | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- | :--- |
| **Static Rate Limiter (Token Bucket)** | Komputasi murah ($O(1)$), konsumsi memori sangat kecil. | Tidak responsif terhadap pelambatan dependensi internal; penentuan batas hardcoded rawan salah. | Minimal (< 1ms). | Edge API Gateway (North-South Traffic) anti DoS publik. |
| **Adaptive Concurrency Limit** | Otomatis menyesuaikan beban berdasarkan kapasitas downstream; mencegah *bufferbloat*. | Algoritma kompleks, butuh fase pemanasan (*cold start profiling*); metrik jittery di awal. | Marginal overhead evaluasi lock (~2-5µs). | Komunikasi antar-mikroservis internal (East-West Traffic). |
| **Hedged Requests (Speculative Retry)** | Memangkas *tail latency* ($P_{99}$, $P_{99.9}$) secara signifikan. | Menambah beban konsumsi downstream (duplikasi request); rawan komplikasi pada operasi non-idempoten. | Menurunkan $P_{99}$, sedikit menaikkan beban throughput total. | Operasi pembacaan database terdistribusi idempoten (*Read Intensive*). |
| **Head-Based Sampling (OTel)** | Keputusan sampling instan di client; konsumsi memori collector sangat rendah. | Rentan membuang trace kegagalan langka jika sampling rate rendah (misal 5%). | Nol latency pada jaringan telemetri. | Sistem bervolume homogen stabil dengan kapasitas storage trace terbatas. |
| **Tail-Based Sampling (OTel)** | 100% error dan transaksi anomali tersimpan utuh; visibilitas insiden maksimal. | Membutuhkan OTel Collector Cluster dengan RAM besar; data harus dibuffer sebelum di-flush. | Network collector buffer retention overhead. | Sistem finansial, transaksi mission-critical, dan e-commerce berskala tinggi. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Fatal 1: Broken Context Propagation pada Asynchronous Boundary
- **Gejala:** Trace terputus menjadi beberapa Trace ID baru ketika memproses event dari Kafka atau RabbitMQ.
- **Penyebab:** Developer hanya mem-passing payload domain struct tanpa mengekstraksi metadata OTel dari Kafka Message Headers ke `context.Context` sebelum memanggil `tracer.Start()`.
- **Solusi:** Gunakan OpenTelemetry `TextMapPropagator` secara eksplisit pada Consumer dan Producer.

### Kesalahan Fatal 2: Metrik High Cardinality Explosion
- **Gejala:** Prometheus atau Datadog mengalami lonjakan konsumsi memori eksponensial (OOM) dan biaya *cloud observability* membengkak drastis.
- **Penyebab:** Memasukkan parameter unik dinamis (seperti `user_id`, `order_id`, atau `credit_card_number`) sebagai label/tag pada Metrik Histogram/Counter.
- **Solusi:** Label metrik **hanya boleh berisi data diskrit terbatas** (misal: `status_code`, `http_method`, `region`). Nilai unik tak terbatas (`order_id`) **wajib diletakkan di Distributed Trace Baggage atau Log Fields**, bukan di Metrik.

### Kesalahan Fatal 3: Thundering Herd pada Recovery Circuit Breaker
- **Gejala:** Ketika Circuit Breaker berpindah dari `OPEN` ke `HALF-OPEN`, ribuan request tertahan langsung menyerbu secara bersamaan, menyebabkan downstream langsung down seketika dan breaker kembali `OPEN` secara permanen (*flapping*).
- **Solusi:** Terapkan kuota ketat (*Trial Limit*) pada fase `HALF-OPEN` (hanya loloskan 1-5 request pengujian) dan terapkan *exponential backoff* pada durasi `SleepWindow` jika pengujian berulang kali gagal.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis sistem ke lingkungan Production:

- [ ] **Context Timeouts Wajib Ada:** Tidak ada pemanggilan I/O jaringan (HTTP, gRPC, Database, Cache) tanpa parameter `context.WithTimeout` atau `context.WithDeadline`.
- [ ] **Jitter pada Retry Logic:** Seluruh retry logic wajib menggunakan formula *Full Jitter*:
  
  $$\text{Sleep} = \text{random}(0, \min(\text{MaxWait}, \text{BaseWait} \times 2^{\text{attempt}}))$$
  
- [ ] **Idempotency Safeguard:** Pola Hedging dan Retry agresif **hanya boleh** dieksekusi pada endpoint yang memiliki mekanisme deduplikasi / Idempotency Key unik di sisi server penerima.
- [ ] **Baggage Sanitation:** Cegah kebocoran data sensitif (PII/Secret) di header HTTP terbuka; bersihkan (*sanitize*) *Baggage* sebelum request diteruskan ke domain eksternal.
- [ ] **Structured Logging Terhubung Exemplar:** Log engine menginjeksi atribut `trace_id` dan `span_id` secara otomatis menggunakan format JSON standar OpenTelemetry.
- [ ] **Graceful Degradation Fallback:** Setiap Circuit Breaker wajib memiliki jalur penyelamat cadangan: *Serve from Stale Cache*, *Degraded Static Response*, atau *Asynchronous Dead-Letter Queue (DLQ)*.

---

## 12. Hands-on Practice: Membangun Resilient & Observable Pipeline

Folder praktikum: `hands-on/m02/`

### Struktur Direktori:
```
hands-on/m02/
├── docker-compose.yml
├── otel-collector-config.yaml
├── go.mod
├── go.sum
└── main.go
```

### Langkah 1: Siapkan Konfigurasi `docker-compose.yml`
File ini menyediakan infrastruktur observability terpadu: **Jaeger** (Distributed Tracing UI) dan **OpenTelemetry Collector**.

```yaml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:1.52
    ports:
      - "16686:16686" # Web UI
      - "4317:4317"   # OTLP gRPC default

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.91.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4318:4318"   # OTLP HTTP receiver
    depends_on:
      - jaeger
```

### Langkah 2: Konfigurasi `otel-collector-config.yaml`

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 256

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  logging:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/jaeger, logging]
```

### Langkah 3: Eksekusi Kode dan Jalankan Verifikasi
Jalankan stack infrastruktur:
```bash
cd hands-on/m02/
docker compose up -d
```

Inisialisasi Go Module dan jalankan aplikasi:
```bash
go mod init enterprise-resilience-demo
go get go.opentelemetry.io/otel \
       go.opentelemetry.io/otel/trace \
       go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp \
       go.opentelemetry.io/otel/sdk
go run main.go
```

Buka browser Anda di `http://localhost:16686` untuk melihat bagaimana span terdistribusi dan trace context berhasil dihubungkan saat kondisi circuit tripping terjadi.

---

## 13. Exercises

### Tingkat Easy
Modifikasi implementasi Circuit Breaker pada Seksi 7 agar mendukung konfigurasi waktu pemulihan adaptif: Jika breaker terbuka lebih dari 3 kali berturut-turut dalam 10 menit terakhir, durasi `recoveryTimeout` secara dinamis bertambah 2 kali lipat (*exponential backoff cooldown*).
- **Kriteria Penerimaan:** Breaker tidak menggunakan hardcoded interval saat mengalami kegagalan berulang.

### Tingkat Medium
Buatlah sebuah HTTP Client Middleware di Go yang mengekstraksi W3C Baggage header `x-user-tier` (contoh: `vip` vs `standard`). Terapkan strategi prioritas antrean (*Priority Shedding*):
Jika Concurrency Limit mencapai kapasitas 80%, tolak seluruh request bertipe `standard` dengan status HTTP 429, namun tetap izinkan request bertipe `vip` lewat sampai batas konkurensi mencapai 100%.
- **Kriteria Penerimaan:** Integrasikan dengan OpenTelemetry span attributes untuk mencatat event dropping berdasarkan user tier.

### Tingkat Hard
Bangun sebuah mekanisme **Zero-Allocation Ring-Buffer Metrics Bucket** untuk mencatat latensi rolling window 60 detik tanpa memicu alokasi heap berlebih yang membebani Garbage Collector Go. Integrasikan metrik tersebut ke algoritma Adaptive Concurrency Limits untuk menghitung nilai $P_{99}$ secara real-time.
- **Kriteria Penerimaan:** Jalankan pengujian memori dengan `go test -benchmem`; alokasi per kalkulasi metrik harus 0 B/op.

---

## 14. Challenge (Tantangan Kompleks Arsitektur)

### Konteks Skenario:
Sebuah perusahaan logistik global memiliki sistem routing terdistribusi yang tersebar di 3 multi-region (*US-East*, *EU-Central*, *AP-Southeast*). Sistem mengalami insiden berkala bernama *"Gray Failure"*: Sebuah data center regional tidak sepenuhnya mati, namun salah satu switch jaringan mengalami intermiten packet-loss sebesar 4%, yang menyebabkan peningkatan latensi non-deterministik dan terjadinya *split-brain race condition* pada data pergudangan.

### Misi Arsitek:
Rancang arsitektur ketahanan dan observabilitas komprehensif tanpa solusi instan:
1. **Adaptive Routing Engine:** Rancang skema Client-Side Service Mesh yang mampu mendeteksi pelambatan anomali region (*gray failure*) dalam waktu $< 2$ detik dan mengalihkan 90% traffic transit ke region terdekat tanpa restart service.
2. **Context Leak & Trace Preservation:** Bagaimana Anda memastikan Distributed Tracing Context dan Baggage ID tidak hilang atau corrupt ketika paket jaringan mengalami *re-ordering*, enkripsi ulang mTLS, dan konversi format protokol dari gRPC ke WebSockets pada worker asynchronous edge?
3. **Observability Cost Capping:** Jika volume request mencapai 500.000 RPS, rancang arsitektur pipeline telemetri yang menjamin sistem observability tidak mengonsumsi resource CPU/Storage lebih dari 5% total resource sistem, sembari mempertahankan 100% data kegagalan sistematis.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Pertanyaan)
1. Apa perbedaan mendasar antara *Fail-Fast* dan *Graceful Degradation*?
2. Mengapa algoritma Exponential Backoff wajib disertai dengan *Full Jitter*?
3. Sebutkan dua komponen utama yang membentuk W3C `traceparent` header!
4. Apa arti status `HALF-OPEN` pada Circuit Breaker?
5. Mengapa metrik histogram latensi biasanya dihitung pada persentil ($P_{95}, P_{99}$) bukan menggunakan rata-rata aritmatika (*average*)?

### Bagian B: Intermediate (5 Pertanyaan)
6. Bagaimana Hukum Little ($L = \lambda \times W$) membuktikan bahwa pelambatan downstream service dapat meruntuhkan upstream service yang menggunakan static thread pool?
7. Mengapa *Head-Based Sampling* pada OpenTelemetry kurang efektif untuk menangkap insiden langka yang memicu error HTTP 500?
8. Bagaimana korelasi metrik dan trace dapat dilakukan tanpa menimbulkan masalah *High Cardinality* pada sistem time-series database? Jelaskan peran *Exemplars*!
9. Apa perbedaan mekanisme isolasi dependensi antara *Thread Pool Bulkhead* dan *Semaphore Bulkhead*?
10. Kapan pola *Hedged Requests* justru berbahaya jika diterapkan dalam microservices?

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan Analisis)
11. **Skenario 1:** Sebuah mikroservis inventaris memiliki Circuit Breaker yang terhubung ke database. Saat database down selama 15 menit, konsumsi memori aplikasi justru melonjak hingga crash OOM, meskipun koneksi ke database telah diputus oleh status breaker `OPEN`. Analisis apa akar masalah internal aplikasi ini!
12. **Skenario 2:** Tim SRE mendeteksi lonjakan tajam pada latensi $P_{99}$ dari 50ms menjadi 3000ms pada Service Checkout. Namun, dashboard OpenTelemetry Trace menunjukkan bahwa eksekusi seluruh downstream Span mikroservis normal (< 20ms). Di layer arsitektur manakah letak akar masalah tersebut?
13. **Skenario 3:** Setelah menerapkan distributed tracing pada arsitektur berbasis Kafka event-driven, tim mendapati bahwa seluruh jejak consumer event muncul sebagai *Root Trace* baru yang terisolasi dan kehilangan jejak producer asalnya. Langkah mitigasi arsitektur apa yang harus dilakukan?

---

### Kunci Jawaban & Panduan Evaluasi

#### Bagian A: Basic
1. *Fail-Fast* memutus eksekusi dan mengembalikan error secepat mungkin tanpa membuang resource komputasi saat terjadi kegagalan. *Graceful Degradation* merespon kegagalan dengan mengembalikan hasil alternatif fungsional yang terbatas (seperti stale data dari cache).
2. Tanpa *Jitter*, ribuan client yang gagal akan me-retry secara serentak pada interval waktu yang sama persis, menciptakan gelombang tabrakan traffic berulang (*thundering herd problem*).
3. Trace ID (16-byte unique identifier) dan Parent Span ID (8-byte identifier), disertai Trace Flags.
4. Status transisi di mana sistem mengizinkan sejumlah kecil request percobaan masuk untuk menguji apakah dependensi downstream telah pulih sepenuhnya sebelum memulihkan sistem ke status `CLOSED`.
5. Rata-rata (*average*) mengaburkan nilai ekstrem (*skewed distribution*). Tail latency terburuk yang dirasakan oleh sebagian kecil pengguna bernilai tinggi (misal 5% pengguna) akan tertutupi oleh 95% request yang cepat.

#### Bagian B: Intermediate
6. Jika latensi ($W$) meningkat drastis sementara request rate downstream ($\lambda$) tetap konstan, maka jumlah in-flight request ($L$) yang tertahan di memori akan melonjak proporsional hingga menguras seluruh buffer antrean dan thread sistem.
7. *Head-Based Sampling* mengambil keputusan apakah suatu request di-trace atau di-drop pada awal lifecycle request (sebelum request selesai dieksekusi), sehingga trace yang mengalami error tak terduga di tengah jalan berpotensi besar terbuang karena tidak terpilih di awal.
8. Metrik disimpan dengan dimensi label ber-kardinalitas rendah. *Exemplar* melampirkan referensi `TraceID` spesifik secara langsung ke sampel titik data di memori histogram, sehingga engineer bisa melompat dari metrik ke trace individual tanpa membuat label baru di database metrik.
9. *Thread Pool Bulkhead* mengalokasikan pool thread terpisah untuk setiap dependensi downstream (isolasi penuh termasuk context switching & asynchronous boundary, namun boros CPU overhead). *Semaphore Bulkhead* hanya membatasi jumlah eksekusi konkurensi pada thread yang memanggil secara langsung (ringan, overhead minimal, namun tidak bisa membatalkan blocking execution secara asinkron).
10. Pola *Hedged Requests* berbahaya jika diterapkan pada operasi yang tidak idempoten (*non-idempotent writes*), atau ketika dependensi downstream sedang mengalami saturasi CPU/Memory murni; menduplikasi request justru akan mempercepat kematian layanan hilir tersebut.

#### Bagian C: Skenario Kasus Produksi
11. **Analisis Skenario 1:** Fallback logic dari Circuit Breaker kemungkinan menampung request yang gagal ke dalam in-memory buffer tak terbatas (*unbounded in-memory queue*) tanpa *backpressure* atau *rejection policy*. Akibatnya, request masuk yang menumpuk selama 15 menit menguras alokasi heap memory hingga memicu OOM-Killed.
12. **Analisis Skenario 2:** Kemungkinan besar terjadi **Queue Delay / Saturation Latency** di layer web server atau container worker pool (misal: antrean socket TCP atau saturasi connection pool reverse proxy). Request menghabiskan waktu 2980ms hanya untuk menunggu giliran dieksekusi di antrean sebelum handler Go/aplikasi mulai berjalan dan Span tracing pertama diciptakan.
13. **Analisis Skenario 3:** Tim belum mengimplementasikan W3C Trace Context Injection/Extraction pada Kafka Record Headers. Solusinya: Producer harus menginjeksi trace context saat ini ke dalam header pesan Kafka menggunakan `otel.GetTextMapPropagator().Inject()`, dan Consumer harus mengekstrak konteks tersebut menggunakan `Extract()` sebelum membungkus logika pemrosesan ke dalam child span.

---

## 16. Summary

1. **Ketahanan Berkelanjutan Bukan Sekadar Retry & Timeout:** Pola statis terbukti rapuh di skala enterprise. Sistem harus mengadopsi kontrol kemacetan adaptif berbasis latensi (*Adaptive Concurrency Limits*) yang secara proaktif menahan laju masuk sebelum downstream mengalami degradasi total.
2. **Observabilitas Sebagai Pilar Pengambilan Keputusan Runtime:** Observabilitas modern bukan sekadar dashboard pasif, melainkan data real-time yang dapat diakses oleh sistem untuk memicu degradasi terisolasi (*Dynamic Shedding*).
3. **Korelasi Adalah Kunci:** Metrik mendeteksi anomali (*Symptom*), Tracing mengisolasi batas degradasi (*Location*), dan Log terstruktur mendiagnosis penyebab fatal (*Root Cause*). Ketiganya harus terikat melalui *Exemplars* dan W3C *Distributed Baggage* tanpa memicu ledakan kardinalitas data.