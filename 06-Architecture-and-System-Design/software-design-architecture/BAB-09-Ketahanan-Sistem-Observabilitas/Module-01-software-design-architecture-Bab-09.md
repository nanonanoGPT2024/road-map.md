# KURIKULUM: SOFTWARE DESIGN & ARCHITECTURE
## Kategori: 06-Architecture-and-System-Design
### Bab 09 — Module 01: Ketahanan Sistem (Resilience), Keandalan, & Observabilitas

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** SDA-06-09-01
* **Nama Modul:** Ketahanan Sistem (Resilience), Keandalan, & Observabilitas: Pola Arsitektur Pertahanan Terdistribusi dan Telemetri Lanjutan
* **Kategori:** 06-Architecture-and-System-Design
* **Tingkat Kesulitan:** Advanced (Tingkat Lanjut)
* **Prasyarat:**
  * Pemahaman mendalam arsitektur Microservices, RPC (gRPC), dan RESTful API.
  * Pemahaman model konkurensi (goroutines/threads, non-blocking I/O, event loops).
  * Pemahaman jaringan dasar: TCP/IP, HTTP/1.1 vs HTTP/2, DNS resolution, connection pooling.
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam (Teori, Eksplorasi Kode, dan Hands-On Labs)
* **Target Pembaca:** Principal Software Engineers, System Architects, SREs (Site Reliability Engineers), Technical Leads.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis & Mencegah Kegagalan Berjenjang (Cascading Failures):** Menjelaskan mekanika keruntuhan sistem terdistribusi akibat coupling dependensi dan latensi laten.
2. **Merancang & Mengimplementasikan Finite State Machine (FSM) Circuit Breaker:** Mengonstruksi pola *Circuit Breaker* adaptif berbasis ambang batas kegagalan, jendela waktu sliding, dan pemulihan *half-open*.
3. **Mengimplementasikan Algoritma Rate Limiting Terdistribusi:** Mengintegrasikan *Token Bucket*, *Leaky Bucket*, dan *Sliding Window Log/Counter* untuk perlindungan kapasitas ingress/egress.
4. **Memitigasi Badai Percobaan Ulang (Retry Storm Mitigation):** Memformulasikan algoritma *Exponential Backoff* yang digabungkan dengan teknik *Full Jitter* dan *Decorrelated Jitter*.
5. **Mendesain Health Checks Berlapis (Liveness, Readiness, Startup):** Mengonfigurasi probe siklus hidup aplikasi terisolasi dari dependensi eksternal untuk mencegah *thundering herd* dan *flapping*.
6. **Menerapkan Distributed Tracing Sesuai Standar W3C TraceContext:** Menginjeksi, mempropagasi, dan mengekstrak metadata konteks penelusuran (Trace ID, Span ID, Baggage) melintasi batas jaringan sinkron dan asinkron.
7. **Membangun Arsitektur Structured Logging Terkorelasi:** Mengompilasi format log berbasis JSON yang menyematkan metadata kontekstual (Correlation ID, Tenant ID, Trace ID) secara zero-allocation.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                           +-------------------------------------------------------+
                           |       SISTEM TERDISTRIBUSI TAHAN BANTING (RESILIENT)   |
                           +-------------------------------------------------------+
                                      |                                  |
                 +--------------------+                                  +--------------------+
                 |                                                                            |
                 v                                                                            v
  +-------------------------------+                                            +-------------------------------+
  |   POLA PERTAHANAN (DEFENSE)   |                                            |      OBSERVABILITAS (O11Y)    |
  +-------------------------------+                                            +-------------------------------+
     |            |             |                                                 |             |             |
     |            |             +--> Mitigasi Retry                               |             |             |
     |            |                  * Exponential Backoff                        |             |             |
     |            |                  * Full & Decorrelated Jitter                 |             |             |
     |            |                  * Retry Budgets                              |             |             |
     |            |                                                               |             |             |
     |            +--> Rate Limiting                                              |             |             |
     |                 * Token Bucket (Traffic Burst)                             |             |             v
     |                 * Leaky Bucket (Traffic Shaping)                           |             |      Health Checks
     |                 * Sliding Window Counter (Distributed/Redis)               |             |       * Startup Probe
     |                                                                            |             |       * Liveness Probe
     v                                                                            v             |       * Readiness Probe
  Circuit Breaker (FSM)                                                    Distributed Tracing  v
   * Closed (Pass-Through)                                                  * W3C TraceContext  Structured Logging
   * Open (Fail-Fast / Fallback)                                            * Spans & Context     * JSON Format
   * Half-Open (Canary Probing)                                               Propagation         * Contextual Correlation
   * Sliding Error Metrics                                                  * OpenTelemetry       * Log Aggregation
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Dalam arsitektur monolitik terpusat, kegagalan fungsi umumnya termanifestasi sebagai *exception* lokal yang dapat ditangani dalam siklus hidup *stack trace* yang sama. Namun, dalam sistem terdistribusi, **kegagalan adalah keniscayaan stokastik**. Jaringan bersifat tidak andal (*fallacies of distributed computing*), latensi bersifat non-deterministik, dan layanan pihak ketiga dapat melambat secara parsial (*brownout*) alih-alih mati sepenuhnya (*blackout*).

### Masalah Brownout vs Blackout
Kegagalan paling berbahaya dalam sistem terdistribusi bukan ketika suatu dependensi langsung mati dan mengembalikan error `ECONNREFUSED` dalam rentang sub-milidetik. Masalah paling fatal muncul saat layanan mengalami degradasi latensi: sebuah dependensi yang biasanya merespons dalam 20ms mendadak membutuhkan waktu 8000ms akibat kelelahan koneksi database (*pool exhaustion*) atau *garbage collection pause*.

Ketika latensi ini merembet ke layanan pemanggil:
1. *Thread pool* atau *worker pool* pada pemanggil terblokir menunggu respons jaringan.
2. Alokasi memori untuk *in-flight requests* melonjak tajam.
3. Sumber daya komputasi (CPU, thread OS, memory limits) habis.
4. Pemanggil mulai gagal memproses request baru dari hulu (*upstream*).
5. Kegagalan berantai (*cascading failure*) meruntuhkan seluruh platform dalam hitungan detik.

### Biaya Kegagalan
Downtime sistem berskala besar tidak hanya mengakibatkan hilangnya pendapatan finansial secara langsung, tetapi juga melanggar SLA/SLO kontraktual, memicu penalti regulasi, dan mendevaluasi kepercayaan konsumen. Pola ketahanan (*resilience*) dan observabilitas (*observability*) adalah dua sisi dari satu mata uang: **Ketahanan menjaga sistem tetap berdiri di bawah tekanan ekstrim, sementara observabilitas memberi transparansi penuh untuk mendiagnosis dan memitigasi kegagalan sebelum dampaknya meluas.**

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Circuit Breaker
Pola desain stabilitas yang membungkus pemanggilan fungsi yang berisiko gagal. Mirip dengan sakelar pemutus sirkuit listrik rumah, pola ini mendeteksi anomali kegagalan secara berkelanjutan. Jika tingkat kegagalan (*error rate*) melampaui ambang batas tertentu, sirkuit "terbuka" (*trips open*), dan seluruh panggilan berikutnya langsung digagalkan secara instan (*fail-fast*) tanpa menyentuh dependensi hilir yang sedang sekarat, atau langsung mengembalikan respons degradasi alternatif (*graceful fallback*).

### 2. Rate Limiting
Mekanisme pertahanan kapasitas yang mengontrol laju konsumsi sumber daya sistem dengan membatasi jumlah permintaan yang diizinkan dalam suatu interval waktu. Rate limiting melindungi sistem dari serangan DoS/DDoS, *scraping* agresif, ketidakseimbangan alokasi *multi-tenant*, dan lonjakan beban tak terduga (*spiky traffic*).

### 3. Retry Storm Mitigation
Strategi pemulihan kegagalan sementara (*transient failures*) yang mencegah efek samping destruktif dari percobaan ulang yang tidak terkontrol. Ketika ratusan klien mencoba ulang permintaan yang gagal secara simultan pada interval tetap, mereka menciptakan fenomena *Thundering Herd* yang secara efektif melipatgandakan beban ke sistem hilir yang sedang berjuang untuk pulih. Mitigasi ini menggunakan *Exponential Backoff* ditambah keacakan matematis (*Jitter*).

### 4. Health Checks
Mekanisme introspeksi internal yang diekspos oleh layanan agar orkestrator (misalnya Kubernetes, Nomad, atau Load Balancer) dapat memverifikasi integritas operasional aplikasi. Ini terbagi menjadi:
* **Startup Probe:** Memastikan proses inisialisasi awal selesai sebelum probe lain dievaluasi.
* **Liveness Probe:** Mendeteksi kondisi jalan buntu (*deadlock*) di mana proses berjalan tetapi tidak dapat lagi memproses instruksi. Jika gagal, kontainer harus di-restart.
* **Readiness Probe:** Memverifikasi apakah aplikasi siap menerima *traffic* komputasi. Jika gagal, aplikasi dikeluarkan dari *routing table load balancer* tanpa mematikan proses.

### 5. Distributed Tracing
Metode observabilitas untuk melacak siklus hidup komputasi dan aliran kontrol data saat suatu permintaan melintasi berbagai proses, kontainer, dan batas jaringan. Tracing memecah operasi menjadi *Trace* (keseluruhan pohon eksekusi) dan *Spans* (unit kerja individual yang terikat durasi, status, dan metadata).

### 6. Structured Logging
Pendekatan pencatatan telemetri di mana muatan log ditulis dalam format terstruktur mesin (umumnya JSON) dengan skema kunci-nilai yang konsisten, alih-alih teks bebas (*unstructured plain text*). Hal ini memungkinkan agregasi, pemfilteran, dan korelasi skala petabyte di platform analitik log (misalnya ClickHouse, Elasticsearch, Grafana Loki).

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### Mekanisme Finite State Machine Circuit Breaker
Circuit Breaker beroperasi berdasarkan tiga status diskrit:
1. **CLOSED:** 
   * Aliran permintaan diteruskan ke sistem tujuan secara normal.
   * Internal counter mengumpulkan metrik metrik keberhasilan dan kegagalan dalam jendela geser (*sliding window*, berbasis waktu atau berbasis hitungan permintaan).
   * Jika rasio kegagalan melewati ambang batas ($\text{failure\_rate} \ge \text{threshold}$), sirkuit bertransisi ke status **OPEN**.
2. **OPEN:**
   * Permintaan masuk langsung digagalkan secara instan (*fail-fast*) dengan mengembalikan error khusus (misal `ErrCircuitOpen`) atau dialihkan ke mekanisme *fallback*.
   * Dependensi hilir sama sekali tidak dihubungi, memberikan waktu bagi sistem hilir untuk melepaskan beban dan memulihkan diri.
   * Timer masa tenang (*sleep window* / *cooldown period*) dijalankan. Ketika timer habis, sirkuit bertransisi ke **HALF-OPEN**.
3. **HALF-OPEN:**
   * Sirkuit mengizinkan sejumlah kecil permintaan uji coba (*canary requests*) untuk menembus dependensi hilir.
   * Jika seluruh (atau mayoritas) permintaan uji coba ini berhasil, sirkuit mengasumsikan dependensi telah normal dan bertransisi kembali ke status **CLOSED**. Metrik kegagalan di-reset.
   * Jika satu saja permintaan uji coba gagal, sirkuit mengasumsikan masalah belum terselesaikan dan langsung kembali ke status **OPEN**, me-reset kembali timer *cooldown*.

### Matematika Retry: Exponential Backoff & Jitter
Rumus dasar backoff eksponensial murni:
$$T_{\text{backoff}} = \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}})$$

Kelemahan pendekatan deterministik ini adalah sinkronisasi periodik klien: jika 1000 klien gagal pada $t=0$, seluruh 1000 klien akan mencoba ulang secara bersamaan pada $t=T_{\text{base}}$, lalu kembali bersamaan pada $t=2 \cdot T_{\text{base}}$.

Untuk memecahkan koherensi ini, kita menerapkan **Full Jitter**:
$$T_{\text{sleep}} = \text{random}(0, \; T_{\text{backoff}})$$

Atau **Decorrelated Jitter** (pendekatan variatif yang memperhitungkan durasi interval sebelumnya):
$$T_{\text{sleep}} = \min(T_{\text{max}}, \; \text{random}(T_{\text{base}}, \; T_{\text{previous}} \times 3))$$

### Algoritma Rate Limiting Terdistribusi: Sliding Window Counter
Dibandingkan *Fixed Window* (yang rentan terhadap lonjakan lalu lintas $2\times$ kapasitas pada perbatasan jendela) dan *Sliding Window Log* (yang memakan memori sangat tinggi karena menyimpan *timestamp* setiap request), **Sliding Window Counter** mengombinasikan efisiensi memori dan akurasi tinggi:
$$\text{Weight} = \frac{\text{WindowSize} - (\text{CurrentTime} - \text{CurrentWindowStart})}{\text{WindowSize}}$$
$$\text{EstimatedRequests} = (\text{RequestsInPreviousWindow} \times \text{Weight}) + \text{RequestsInCurrentWindow}$$

Jika $\text{EstimatedRequests} + 1 > \text{Limit}$, tolak permintaan (HTTP 429 Too Many Requests).

### Propagasi Konteks Distributed Tracing (W3C TraceContext)
Tracer menginjeksi metadata penelusuran ke dalam header transport jaringan protokol (misalnya HTTP Header atau gRPC Metadata) menggunakan spesifikasi W3C:
* `traceparent`: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
  * `00`: Format versi spesifikasi.
  * `4bf92f3577b34da6a3ce929d0e0e4736`: Trace ID unik global (16 bytes / 32 hex chars).
  * `00f067aa0ba902b7`: Parent Span ID unik lokal (8 bytes / 16 hex chars).
  * `01`: Trace flags (bitmask, `01` menandakan *sampled* / direkam).
* `tracestate`: Pasangan *key-value* spesifik vendor/sistem untuk perutean internal telemetri.

Ketika permintaan diterima oleh microservice downstream:
1. Konteks diekstrak (*deserialized*) dari header.
2. Span baru dibuat dengan Parent ID yang merujuk pada Span pemanggil.
3. Span baru diikat ke konteks eksekusi thread/goroutine runtime.
4. Setiap pemanggilan berikutnya meneruskan Trace ID yang sama dan Span ID yang diperbarui.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. FSM Circuit Breaker State Transition

```
                    +-----------------------------+
                    |                             |
                    |           CLOSED            | <-----------------------+
                    |  (Normal Traffic Passthrough)|                         |
                    |                             |                         |
                    +-----------------------------+                         |
                                   |                                        |
                 Failure Rate >= Threshold                                  |
                                   |                                        |
                                   v                                        |
                    +-----------------------------+                         |
                    |                             |                         |
       +----------> |            OPEN             |                         |
       |            |   (Immediate Fail-Fast)     |                         |
       |            |                             |                         |
       |            +-----------------------------+                         |
       |                           |                                        |
       |                  Sleep Window Expired                              |
  Canary Probe                     |                                        |
     Failed                        v                                        |
       |            +-----------------------------+                         |
       |            |                             |                         |
       +----------- |          HALF-OPEN          |                         |
                    |    (Canary Probing Pass)    |                         |
                    |                             |                         |
                    +-----------------------------+                         |
                                   |                                        |
                                   +--- Canary Probes Succeed Completely ---+
```

### 2. Distributed Tracing Propagation & Correlation Map

```
CLIENT REQUEST
      |
      | HTTP GET /checkout
      | Inject: traceparent: 00-traceABC-span001-01
      v
+---------------------------------------------------------------------------------+
| SERVICE A: API Gateway (Trace ID: traceABC)                                     |
| [Span: span001 - Ingress Handler]                                               |
|   |--> Structured Log: {"trace_id": "traceABC", "span_id": "span001", "msg": "incoming checkout"}
|   |
|   |-- Call Service B over HTTP
|   |   Inject: traceparent: 00-traceABC-span002-01
|   |   +-------------------------------------------------------------------------+
|   |   | SERVICE B: Order Service (Trace ID: traceABC)                           |
|   |   | [Span: span002 - Process Order]                                         |
|   |   |   |--> Log: {"trace_id": "traceABC", "span_id": "span002", "step": 1}   |
|   |   |   |                                                                     |
|   |   |   |-- Call Service C over gRPC                                          |
|   |   |   |   Metadata: traceparent: 00-traceABC-span003-01                     |
|   |   |   |   +-----------------------------------------------------------------+
|   |   |   |   | SERVICE C: Payment Engine (Trace ID: traceABC)                  |
|   |   |   |   | [Span: span003 - Execute Charge]                                |
|   |   |   |   |   |--> Log: {"trace_id": "traceABC", "span_id": "span003", ...} |
|   |   |   |   |   +-------------------------------------------------------------+
|   |   |   |   <-- Response gRPC OK
|   |   |   <-- Response HTTP 200 OK
|   <-- Response HTTP 200 OK
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah perbandingan antara HTTP client primitif tanpa ketahanan vs HTTP client dengan mitigasi **Exponential Backoff dan Full Jitter** sederhana menggunakan bahasa Go.

### Implementasi Primitif (Anti-Pattern)
```go
// BURUK: Retry agresif tanpa interval dan pembatasan yang berpotensi memicu retry storm
func BadFetchUserData(url string) ([]byte, error) {
    var lastErr error
    for i := 0; i < 5; i++ {
        resp, err := http.Get(url)
        if err == nil && resp.StatusCode == http.StatusOK {
            defer resp.Body.Close()
            return io.ReadAll(resp.Body)
        }
        lastErr = err
        // Tidak ada jeda: memukul server secepat mungkin dalam loop tertutup
    }
    return nil, fmt.Errorf("gagal setelah 5 kali percobaan: %w", lastErr)
}
```

### Implementasi Resilient (Exponential Backoff + Full Jitter)
```go
package main

import (
	"context"
	"crypto/rand"
	"errors"
	"fmt"
	"io"
	"math"
	"math/big"
	"net/http"
	"time"
)

type BackoffConfig struct {
	MaxRetries int
	BaseDelay  time.Duration
	MaxDelay   time.Duration
}

// ResilientFetch mendemonstrasikan pemanggilan HTTP dengan retry backoff + full jitter
func ResilientFetch(ctx context.Context, client *http.Client, url string, cfg BackoffConfig) ([]byte, error) {
	var lastErr error

	for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
		// Evaluasi pembatalan context upstream sebelum memulai eksekusi
		if err := ctx.Err(); err != nil {
			return nil, fmt.Errorf("operasi dibatalkan oleh context: %w", err)
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return nil, fmt.Errorf("gagal membangun request: %w", err)
		}

		resp, err := client.Do(req)
		if err == nil {
			if resp.StatusCode < 500 && resp.StatusCode != http.StatusTooManyRequests {
				// Status 2xx, 3xx, atau 4xx (non-retriable client errors) tidak diulang
				defer resp.Body.Close()
				if resp.StatusCode >= 200 && resp.StatusCode < 300 {
					return io.ReadAll(resp.Body)
				}
				return nil, fmt.Errorf("kesalahan HTTP deterministik: %d", resp.StatusCode)
			}
			// Status 5xx atau 429 adalah kandidat retry
			resp.Body.Close()
			lastErr = fmt.Errorf("server error dengan status HTTP: %d", resp.StatusCode)
		} else {
			lastErr = err
		}

		if attempt == cfg.MaxRetries {
			break
		}

		// Hitung Exponential Backoff murni: Base * 2^attempt
		multiplier := math.Pow(2, float64(attempt))
		backoffLimit := float64(cfg.BaseDelay) * multiplier
		if backoffLimit > float64(cfg.MaxDelay) {
			backoffLimit = float64(cfg.MaxDelay)
		}

		// Terapkan Full Jitter: Sleep = Random(0, backoffLimit)
		nBig, _ := rand.Int(rand.Reader, big.NewInt(int64(backoffLimit)))
		jitteredSleep := time.Duration(nBig.Int64())

		select {
		case <-time.After(jitteredSleep):
			// Melanjutkan ke percobaan berikutnya
		case <-ctx.Done():
			return nil, fmt.Errorf("context timeout selama backoff: %w", ctx.Err())
		}
	}

	return nil, fmt.Errorf("eksekusi habis setelah %d retries: %w", cfg.MaxRetries, lastErr)
}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi sistem produksi lengkap: **Sliding Window In-Memory Circuit Breaker Terkonkurensi Tinggi** yang terintegrasi dengan **W3C TraceContext Propagation** dan **Structured JSON Logging Zero-Dependency**.

```go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

// ==========================================
// 1. OBSERVABILITAS: STRUCTURED LOGGING & TRACING
// ==========================================

type TraceContext struct {
	TraceID string
	SpanID  string
	Sampled bool
}

type contextKey string

const traceCtxKey contextKey = "w3c_trace_context"

type StructuredLogger struct {
	writer io.Writer
}

func NewStructuredLogger(w io.Writer) *StructuredLogger {
	return &StructuredLogger{writer: w}
}

func (l *StructuredLogger) Log(ctx context.Context, level, message string, extra map[string]interface{}) {
	payload := map[string]interface{}{
		"timestamp": time.Now().UTC().Format(time.RFC3339Nano),
		"level":     level,
		"message":   message,
	}

	if tc, ok := ctx.Value(traceCtxKey).(TraceContext); ok {
		payload["trace_id"] = tc.TraceID
		payload["span_id"] = tc.SpanID
	}

	for k, v := range extra {
		payload[k] = v
	}

	data, _ := json.Marshal(payload)
	_, _ = l.writer.Write(append(data, '\n'))
}

// ==========================================
// 2. RESILIENCE: CIRCUIT BREAKER FSM
// ==========================================

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

var (
	ErrCircuitOpen = errors.New("circuit breaker is OPEN: call denied")
)

type CircuitBreakerSettings struct {
	FailureThreshold float64       // Persentase kegagalan (0.0 - 1.0) untuk membuka sirkuit
	MinimumRequests  uint32        // Jumlah minimal request dalam window untuk mulai menghitung
	CooldownDuration time.Duration // Lama waktu di state OPEN sebelum pindah ke HALF-OPEN
	WindowDuration   time.Duration // Durasi rotasi metric sliding window
}

type metricBucket struct {
	success uint32
	failure uint32
}

type CircuitBreaker struct {
	state          int32 // Dioperasikan via sync/atomic (StateClosed, StateHalfOpen, StateOpen)
	settings       CircuitBreakerSettings
	logger         *StructuredLogger
	mu             sync.RWMutex
	lastStateShift time.Time
	bucket         metricBucket
	lastBucketSwap time.Time
}

func NewCircuitBreaker(settings CircuitBreakerSettings, logger *StructuredLogger) *CircuitBreaker {
	return &CircuitBreaker{
		state:          int32(StateClosed),
		settings:       settings,
		logger:         logger,
		lastStateShift: time.Now(),
		lastBucketSwap: time.Now(),
	}
}

func (cb *CircuitBreaker) Execute(ctx context.Context, operation func(ctx context.Context) error) error {
	if err := cb.beforeExecution(ctx); err != nil {
		return err
	}

	err := operation(ctx)
	cb.afterExecution(ctx, err)
	return err
}

func (cb *CircuitBreaker) beforeExecution(ctx context.Context) error {
	currentState := State(atomic.LoadInt32(&cb.state))

	if currentState == StateOpen {
		cb.mu.Lock()
		if State(cb.state) == StateOpen && time.Since(cb.lastStateShift) > cb.settings.CooldownDuration {
			// Cooldown expired: Transisi atomik ke HALF-OPEN
			atomic.StoreInt32(&cb.state, int32(StateHalfOpen))
			cb.lastStateShift = time.Now()
			cb.logger.Log(ctx, "WARN", "Circuit breaker transitioning to HALF-OPEN", map[string]interface{}{
				"previous_state": "OPEN",
				"new_state":      "HALF-OPEN",
			})
			cb.mu.Unlock()
			return nil
		}
		cb.mu.Unlock()

		cb.logger.Log(ctx, "ERROR", "Call rejected by circuit breaker", map[string]interface{}{
			"circuit_state": "OPEN",
		})
		return ErrCircuitOpen
	}

	return nil
}

func (cb *CircuitBreaker) afterExecution(ctx context.Context, opErr error) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	currentState := State(atomic.LoadInt32(&cb.state))

	// Periksa rotasi bucket metric berdasarkan waktu
	if time.Since(cb.lastBucketSwap) > cb.settings.WindowDuration {
		cb.bucket = metricBucket{}
		cb.lastBucketSwap = time.Now()
	}

	if opErr != nil {
		cb.bucket.failure++
	} else {
		cb.bucket.success++
	}

	total := cb.bucket.success + cb.bucket.failure

	if currentState == StateHalfOpen {
		if opErr != nil {
			// Satu kegagalan di HALF-OPEN langsung memicu kembali ke OPEN
			atomic.StoreInt32(&cb.state, int32(StateOpen))
			cb.lastStateShift = time.Now()
			cb.logger.Log(ctx, "CRITICAL", "Canary failed in HALF-OPEN. Re-tripping to OPEN", map[string]interface{}{
				"error": opErr.Error(),
			})
		} else {
			// Sukses pada canary: Kembalikan sirkuit ke CLOSED
			atomic.StoreInt32(&cb.state, int32(StateClosed))
			cb.lastStateShift = time.Now()
			cb.bucket = metricBucket{} // Reset metrik
			cb.logger.Log(ctx, "INFO", "Canary succeeded. Restoring circuit to CLOSED", nil)
		}
		return
	}

	if currentState == StateClosed {
		if total >= cb.settings.MinimumRequests {
			rate := float64(cb.bucket.failure) / float64(total)
			if rate >= cb.settings.FailureThreshold {
				atomic.StoreInt32(&cb.state, int32(StateOpen))
				cb.lastStateShift = time.Now()
				cb.logger.Log(ctx, "WARN", "Trip threshold breached. Opening circuit!", map[string]interface{}{
					"failure_rate": rate,
					"threshold":    cb.settings.FailureThreshold,
					"total_calls":  total,
				})
			}
		}
	}
}

// ==========================================
// 3. TESTING PIPELINE & DEMONSTRASI INTEGRASI
// ==========================================

func main() {
	logger := NewStructuredLogger(os.Stdout)
	cb := NewCircuitBreaker(CircuitBreakerSettings{
		FailureThreshold: 0.50, // 50% failures trip the breaker
		MinimumRequests:  4,
		CooldownDuration: 2 * time.Second,
		WindowDuration:   10 * time.Second,
	}, logger)

	// Simulasi Trace Context W3C
	baseCtx := context.WithValue(context.Background(), traceCtxKey, TraceContext{
		TraceID: "4bf92f3577b34da6a3ce929d0e0e4736",
		SpanID:  "00f067aa0ba902b7",
		Sampled: true,
	})

	simulateCall := func(id int, fail bool) {
		err := cb.Execute(baseCtx, func(ctx context.Context) error {
			if fail {
				return errors.New("connection timeout ke payment-gateway")
			}
			return nil
		})

		if err != nil {
			logger.Log(baseCtx, "WARN", fmt.Sprintf("Req #%d Result: FAILED", id), map[string]interface{}{"err": err.Error()})
		} else {
			logger.Log(baseCtx, "INFO", fmt.Sprintf("Req #%d Result: SUCCESS", id), nil)
		}
	}

	fmt.Println("--- PHASE 1: Normal Traffic (CLOSED) ---")
	simulateCall(1, false)
	simulateCall(2, false)

	fmt.Println("\n--- PHASE 2: Upstream Outage (Triggering Trip) ---")
	simulateCall(3, true)
	simulateCall(4, true)
	simulateCall(5, true) // Threshold tercapai -> OPEN

	fmt.Println("\n--- PHASE 3: Immediate Fail-Fast (Circuit OPEN) ---")
	simulateCall(6, false) // Harus langsung ditolak tanpa eksekusi

	fmt.Println("\n--- PHASE 4: Sleep for Cooldown (Waiting for HALF-OPEN) ---")
	time.Sleep(2100 * time.Millisecond)

	fmt.Println("\n--- PHASE 5: Canary Probing (Transition to CLOSED) ---")
	simulateCall(7, false) // Sukses memicu sirkuit kembali CLOSED
	simulateCall(8, false) // Sudah berjalan normal kembali
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Menerapkan mekanisme ketahanan bukan tanpa konsekuensi sistemik. Tabel berikut merinci *engineering trade-offs* yang wajib diperhitungkan:

| Pola / Komponen | Keuntungan Desain | Potensi Biaya / Kelemahan (*Drawbacks*) | Rekomendasi Titik Impas (*Sweet Spot*) |
| :--- | :--- | :--- | :--- |
| **Circuit Breaker** | Mencegah keruntuhan total akibat cascading failures; melepaskan beban dependensi hilir. | Latensi overhead evaluasi state mutex/atomic; risiko *false-positive* sirkuit terbuka akibat lonjakan error acak. | Gunakan sliding metrics berbasis volume minimum ($N \ge 50$ request), jangan hanya rasio persentase murni. |
| **Distributed Rate Limiting (Redis)** | Sinkronisasi global akurat antar puluhan node microservice; perlindungan resource absolut. | Menambah *hop* latensi jaringan (1-3ms) per inbound call; Redis menjadi *Single Point of Failure* (SPOF). | Gunakan arsitektur *Local In-Memory Token Bucket* dengan sinkronisasi asinkron agregat batch ke Redis. |
| **Retry with Jitter** | Mengatasi error transien jaringan secara transparan tanpa intervensi pengguna. | Menambah latensi akhir bagi pengguna jika sistem tujuan benar-benar lumpuh; memboroskan komputasi. | Tetapkan *Retry Budget* (maksimal 10-20% dari total bandwidth traffic); jangan pernah me-retry status 4xx. |
| **Readiness Probe Agresif** | Menghapus instance sakit dari *load balancer* seketika. | Jika seluruh instance bergantung pada database yang sama dan database melambat, seluruh instance akan serempak unready (*Cascading Drop*). | Pisahkan pengecekan konektivitas dependensi eksternal dari Readiness Probe internal; gunakan status degradasi. |
| **Distributed Tracing (100%)** | Visibilitas mutlak; root-cause analysis sub-detik untuk anomali latensi p99. | Overhead memori, CPU serialisasi W3C header, dan biaya penyimpanan telemetri disk yang kolosal. | Terapkan *Head-based* (misal 1-5% sampling rate) atau *Tail-based Sampling* (hanya rekam trace jika ada error/latensi > p95). |

---

## SEKSI 11 — BEST PRACTICES

### Ketahanan (Resilience)
* **Kombinasikan Circuit Breaker dengan Bulkheading:** Pisahkan *connection pool* dan thread worker antar domain bisnis. Kegagalan subsistem Analytics tidak boleh menghabiskan *thread pool* Checkout.
* **Terapkan Deadline Propagation:** Gunakan pembatalan konteks eksplisit (`context.WithTimeout`). Jika klien hulu membatalkan pemanggilan dalam 3 detik, seluruh rantai pemanggilan microservice hilir harus berhenti memproses request tersebut sesegera mungkin.
* **Hormati Header `Retry-After`:** Saat menerima respons HTTP 429 atau 503, gunakan nilai durasi yang dikirimkan oleh server hulu alih-alih algoritma backoff internal.

### Observabilitas (Observability)
* **Patuhi *The Four Golden Signals* (Google SRE):**
  1. **Latency:** Durasi waktu penyelesaian permintaan (pisahkan antara latency permintaan sukses dan gagal).
  2. **Traffic:** Pengukuran permintaan sistem (misal HTTP requests/second).
  3. **Errors:** Rasio kegagalan permintaan eksplisit atau implisit.
  4. **Saturation:** Derajat kepenuhan sumber daya paling terbatas (CPU, Memory, IOPS, DB Pool).
* **Correlation ID Di Setiap Batas Jaringan:** Jika klien tidak mengirimkan W3C TraceContext atau correlation ID, buat *Universally Unique Identifier* (UUIDv4 atau ULID) di layer Ingress API Gateway terluar dan pasang pada header respons (`X-Correlation-ID`).
* **Zero-Allocation Logging:** Pada jalur kode throughput tinggi (*hot path*), gunakan pustaka logging berbasis penulisan biner atau minim alokasi heap (seperti Uber `zap` atau `zerolog` dalam ekosistem Go).

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

### 1. The Retries-of-Death Cascade
* **Anti-Pattern:** Microservice A memanggil Service B dengan 3x retry. Service B memanggil Service C dengan 3x retry. Service C memanggil Service D dengan 3x retry. Jika Service D mengalami gangguan sementara:
  $$\text{Total Calls ke D} = 3 \times 3 \times 3 = 27\times \text{ lipat beban semula!}$$
* **Solusi:** Hanya lakukan retry pada layer paling dekat dengan sumber kegagalan, atau terapkan *Retry Budgeting* di mana klien menolak melakukan retry jika rasio retry dalam 1 menit melampaui 10% dari total request.

### 2. Coupling Readiness Probe dengan Dependensi Eksternal
* **Anti-Pattern:** Probe `/ready` microservice `order-service` menjalankan query `SELECT 1 FROM database;` dan `PING payment-service`. Ketika database mengalami *lock contention* periodik, seluruh pod `order-service` ditandai *Not Ready* oleh Kubernetes, mematikan total ingress aplikasi.
* **Solusi:** Probe `/ready` harus memvalidasi kesiapan internal proses sendiri (apakah worker threads sudah hidup, cache lokal sudah hangat). Kegagalan komunikasi ke luar harus dimitigasi oleh Circuit Breaker lokal, bukan dengan mematikan pod dari load balancer.

### 3. Log PII (Personally Identifiable Information) Leaks
* **Anti-Pattern:** Memasukkan seluruh `req.Body` atau variabel authorization ke dalam structured log JSON:
  ```json
  {"level":"info","body":{"password":"secret","credit_card":"4111..."}}
  ```
* **Solusi:** Buat lapisan sanitasi/masking ketat sebelum pesan di-marshal ke JSON stream. Pisahkan payload log bisnis dari audit payload telemetri.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1 (Beginner): Menghitung Jitter Backoff
* **Tugas:** Buat fungsi dalam bahasa pemrograman pilihan Anda yang menerima parameter `attempt`, `baseDelay`, dan `maxDelay`.
* **Kebutuhan:**
  1. Hitung nilai exponential backoff murni.
  2. Implementasikan *Full Jitter* matematis menggunakan secure/pseudo-random number generator.
  3. Cetak 10 simulasi iterasi berturut-turut untuk membuktikan bahwa tidak ada dua nilai delay yang identik.

### Latihan 2 (Intermediate): Distributed Sliding Window Rate Limiter
* **Tugas:** Rancang middleware HTTP yang menerapkan algoritma *Sliding Window Counter* menggunakan Redis (atau simulasi *in-memory mutex map*).
* **Kebutuhan:**
  1. Batasi permintaan ke `100 requests per 1 menit` per IP Address / API Key.
  2. Kembalikan header HTTP standar:
     * `X-RateLimit-Limit: 100`
     * `X-RateLimit-Remaining: <sisa>`
     * `Retry-After: <detik>` (jika terblokir)
  3. Kembalikan kode status HTTP 429 jika kuota terlampaui.

### Latihan 3 (Advanced): Distributed Traced Service Mesh Emulator
* **Tugas:** Bangun tiga layanan mandiri (Gateway $\to$ Auth $\to$ Database Service).
* **Kebutuhan:**
  1. Gateway menerima permintaan HTTP GET tanpa header trace dan menghasilkan `traceparent` W3C standar baru.
  2. Gateway meneruskan `traceparent` ke Auth Service via HTTP header.
  3. Auth Service membaca header tersebut, membuat child Span baru, dan melakukan log terstruktur dalam format JSON yang memuat `trace_id` yang sama persis.
  4. Simulasikan error sintetis pada Database Service; buktikan bahwa seluruh log trace dari ketiga layer dapat di-query menggunakan `trace_id` tunggal tersebut.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Apa perbedaan status OPEN dan HALF-OPEN pada pola Circuit Breaker?**
   * A. Status OPEN membiarkan traffic lewat untuk tes sistem, HALF-OPEN mematikan server.
   * B. Status OPEN langsung menolak request tanpa memanggil dependensi; HALF-OPEN mengizinkan sebagian kecil request untuk memvalidasi apakah sistem hilir sudah pulih.
   * C. Status OPEN berarti sistem sehat, HALF-OPEN berarti sistem kelebihan beban.
   * D. Tidak ada perbedaan fungsional, keduanya menolak request masuk.

2. **Mengapa implementasi Retry tanpa Jitter dianggap sangat berbahaya dalam arsitektur berskala besar?**
   * A. Karena memakan bandwidth jaringan dua kali lipat lebih banyak daripada request normal.
   * B. Karena menyebabkan kegagalan decoding JSON pada layer penerima.
   * C. Karena memicu sinkronisasi periodik klien (*thundering herd*) yang menghantam sistem downstream secara simultan berulang kali.
   * D. Karena memperlambat eksekusi garbage collection pada bahasa ber-runtime VM.

3. **Manakah dari skenario berikut yang merupakan tanggung jawab Readiness Probe (bukan Liveness Probe)?**
   * A. Membunuh dan me-restart kontainer yang mengalami thread deadlock permanen.
   * B. Menghentikan perutean lalu lintas sementara dari load balancer ke pod yang sedang sibuk memproses *in-memory batch warming*.
   * C. Memastikan proses instalasi binary aplikasi selesai saat deployment.
   * D. Menghapus log aplikasi dari filesystem host.

4. **Dalam format W3C TraceContext `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`, komponen `00f067aa0ba902b7` merepresentasikan:**
   * A. Trace ID global.
   * B. Status Sampling Flag.
   * C. Parent Span ID.
   * D. HTTP Status Code.

---

### Kunci Jawaban & Evaluasi

* **Jawaban Soal 1:** **B**. Status OPEN adalah mode *fail-fast* absolut. HALF-OPEN adalah status evaluasi berkala dengan traffic kecil (*canary*) untuk menguji stabilitas dependensi sebelum sirkuit ditutup kembali.
* **Jawaban Soal 2:** **C**. Tanpa keacakan (*jitter*), retry yang dihitung secara eksponensial murni tetap akan terkonsentrasi pada *timestamp* gelombang yang sama, memperparah fenomena *thundering herd*.
* **Jawaban Soal 3:** **B**. Readiness probe bertugas mengatur apakah pod boleh menerima traffic dari load balancer atau tidak. Jika liveness probe yang dipicu untuk skenario pemanasan cache, pod justru akan di-restart secara terus-menerus (*crash-looping*).
* **Jawaban Soal 4:** **C**. Berdasarkan spesifikasi W3C TraceContext: Field 1 adalah versi (`00`), Field 2 adalah Trace ID (16 bytes), Field 3 adalah Parent Span ID (8 bytes), dan Field 4 adalah Trace Flags (`01`).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1. **Buku & Standar Industri:**
   * Nygard, Michael T. (2018). *Release It!: Design and Deploy Production-Ready Software (2nd Edition)*. Pragmatic Bookshelf. (Fondasi utama konsep Circuit Breaker, Bulkhead, dan Timeout).
   * Beyer, B., Jones, C., Petoff, J., & Murphy, N. R. (2016). *Site Reliability Engineering: How Google Runs Production Systems*. O'Reilly Media.
   * W3C Recommendation (2021). *Trace Context: W3C Recommendation 23 November 2021*. https://www.w3.org/TR/trace-context/

2. **Spesifikasi Open Source & Engine:**
   * OpenTelemetry Specification: Core Concepts, Context Propagation, and Semantic Conventions. https://opentelemetry.io/docs/specs/
   * Sony / Gobreaker: Circuit Breaker implementation in Go.
   * Envoy Proxy: Architecture & Resilience Filter Documentation (Advanced Rate Limiting & Outlier Detection).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Ketahanan Bukan Aksesori Tambahan:** Pola ketahanan harus dirancang di awal arsitektur terdistribusi untuk mengantisipasi jaringan yang tidak dapat diandalkan dan fenomena *brownout*.
2. **Circuit Breaker Menghentikan Keruntuhan Berantai:** Dengan mengisolasi dependensi bermasalah menggunakan Finite State Machine (CLOSED $\to$ OPEN $\to$ HALF-OPEN), sistem melepaskan tekanan komputasi dan memberikan ruang pemulihan bagi downstream.
3. **Retry Wajib Dipadukan dengan Jitter:** Retry buta memperparah degradasi sistem; *Exponential Backoff* yang dipadukan dengan *Full Jitter* memecah gelombang *thundering herd*.
4. **Isolasi Probe Health Check:** Jangan mengaitkan *Readiness Probe* dengan dependensi eksternal secara naif agar kegagalan parsial pihak ketiga tidak melumpuhkan seluruh armada pod Anda.
5. **Observabilitas Adalah Pondasi Kendali:** *Structured Logging* (JSON), *Correlation IDs*, dan *Distributed Tracing* (W3C TraceContext) memberikan pandangan komprehensif untuk menavigasi, mendiagnosis, dan memvalidasi keandalan sistem berskala besar.

---

## SEKSI 17 — GLOSARIUM

* **Brownout:** Kondisi degradasi parsial di mana layanan masih berjalan namun merespons dengan latensi yang sangat tinggi atau tingkat error sporadis.
* **Cascading Failure:** Kegagalan pada satu node atau dependensi yang memicu kelebihan beban berantai pada node-node lain hingga melumpuhkan seluruh platform.
* **Context Propagation:** Mekanisme serialisasi dan deserialisasi metadata penelusuran (Trace ID, Span ID) di sepanjang jalur jaringan atau eksekusi thread.
* **Fail-Fast:** Pendekatan sistem yang langsung menolak atau menghentikan eksekusi operasi yang diprediksi gagal tanpa membuang sumber daya komputasi.
* **Jitter:** Keacakan variatif yang diinjeksikan secara sengaja ke dalam interval durasi percobaan ulang untuk mencegah sinkronisasi beban antar klien.
* **Span:** Unit kerja terkecil yang memiliki label nama, waktu mulai, dan waktu selesai dalam distributed tracing.
* **Thundering Herd:** Kondisi di mana sejumlah besar klien atau proses secara simultan mencoba mengakses satu sumber daya yang terbatas, membebani kapasitas sistem seketika.
* **W3C TraceContext:** Standar format header terpadu global yang digunakan untuk merepresentasikan dan mempropagasi distributed trace lintas sistem heterogen.

---

## SEKSI 18 — CATATAN INSTRUKTUR

### Pacing & Alur Pengajaran
* **Fokus Konseptual (Jam 1-4):** Bedah anatomi *Cascading Failures*. Jelaskan mengapa latensi lambat jauh lebih mematikan daripada error instan.
* **Bedah Kode (Jam 5-8):** Analisis FSM Circuit Breaker pada Seksi 09. Ajak siswa memodifikasi variabel `Threshold` dan `Cooldown` untuk melihat dampaknya langsung pada throughput pengujian.
* **Hands-On & Debugging (Jam 9-14):** Tugaskan Latihan 2 atau 3. Pastikan peserta melihat secara visual bagaimana sebuah `trace_id` mengikat puluhan baris log dari container yang terpisah secara fisik.

### Jebakan Diskusi di Kelas
* *Pertanyaan Siswa:* "Apakah kita harus memasang Circuit Breaker di seluruh endpoint pemanggilan fungsi internal?"
  * *Jawaban Instruktur:* Tidak. Circuit breaker didesain untuk isolasi batas IO jaringan (*network boundaries*), IPC, atau pemanggilan I/O yang bersifat non-deterministik. Memasang circuit breaker pada pemanggilan in-memory lokal hanya menambah overhead CPU latency dan kompleksitas yang sia-sia.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Oktober 2023):**
  * Rilis inisial kurikulum arsitektur terdistribusi: Circuit Breaker, Rate Limiting, Health Checks, Distributed Tracing, Structured Logging.
* **Versi 1.1.0 (Februari 2024):**
  * Standardisasi propagasi konteks distributed tracing mengacu pada *W3C TraceContext Recommendation*.
  * Penambahan implementasi komprehensif konkurensi aman Go Circuit Breaker FSM dengan *atomic operations*.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** Bab 08 — Module 02: *Event-Driven Architecture: Event Sourcing, CQRS, & Message Brokers*
* **Modul Saat Ini:** Bab 09 — Module 01: *Ketahanan Sistem (Resilience), Keandalan, & Observabilitas*
* **Modul Berikutnya:** Bab 09 — Module 02: *High Availability & Disaster Recovery: Multi-Region Deployment, Database Replication, & Failover Automation*