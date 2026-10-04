# Kurikulum Pemrograman Go (Golang)
## Kategori: 02-Programming-Languages
### Bab 07: Arsitektur Sistem Terdistribusi & Integrasi Layanan
#### Modul 01: Microservices Architecture & API Design

---

### SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** GOL-DIST-0701
* **Nama Modul:** Microservices Architecture & API Design
* **Level Keterampilan:** Advanced (Tingkat Lanjut)
* **Estimasi Waktu Belajar:** 8 Jam (Teori, Analisis Source Code, Praktikum Hands-on)
* **Prasyarat:**
  * Penguasaan mendalam concurrency Go (`goroutine`, `channel`, `sync` primitives, `context.Context`).
  * Pemahaman protokol jaringan (TCP/IP, HTTP/1.1, HTTP/2, TLS).
  * Terbiasa dengan arsitektur RESTful API dan serialisasi data (JSON, Protocol Buffers).
  * Pemahaman dasar Docker dan containerization.
* **Target Ekosistem:** Linux/macOS/Windows, Go 1.22+, Docker Engine, gRPC, Protobuf Compiler (`protoc`).
* **Tags/Keywords:** `microservices`, `api-design`, `idempotency`, `resilience`, `circuit-breaker`, `grpc`, `rest`, `distributed-tracing`, `go-concurrency`.

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendekomposisi Domain:** Mengisolasi *bounded contexts* berdasarkan prinsip Domain-Driven Design (DDD) untuk memetakan batasan layanan microservice secara modular tanpa memicu kopling temporal (*temporal coupling*).
2. **Merancang Kontrak API Resilien:** Mengembangkan spesifikasi antarmuka API (REST dan gRPC) yang backwards-compatible, deterministik, dan terdokumentasi menggunakan pendekatan *Contract-First*.
3. **Menerapkan Pola Ketahanan Jaringan:** Mengimplementasikan pola *Timeout*, *Retry with Exponential Backoff & Jitter*, serta *Circuit Breaker* secara *idiomatic* menggunakan Go runtime dan pustaka standar.
4. **Mengelola State Terdistribusi:** Mengamankan integritas mutasi data lintas batas layanan menggunakan *Distributed Idempotency Keys* dan Pola *Transactional Outbox*.
5. **Menjamin Observabilitas Lintas Layanan:** Menginjeksi dan mengekstraksi W3C Trace Context (`traceparent`) lintas batas protokol (HTTP/gRPC) untuk *distributed tracing*.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

#### Fallacies of Distributed Computing dalam Go

Ketika bertransisi dari monolit ke microservices, ilusi *in-process function call* harus ditinggalkan. Dalam monolit, pemanggilan fungsi bersifat deterministik: fungsi dieksekusi di ruang memori yang sama, CPU yang sama, dan gagal hanya jika sistem mengalami *panic* atau *out-of-memory* (OOM).

Dalam sistem microservice, jaringan adalah komponen yang tidak dapat diandalkan (*unreliable intermediate state*). Komunikasi antarlayanan tunduk pada 8 Falasi Komputasi Terdistribusi:
1. Jaringan itu reliabel.
2. Latensi adalah nol.
3. Bandwidth tidak terbatas.
4. Jaringan itu aman.
5. Topologi tidak pernah berubah.
6. Hanya ada satu administrator.
7. Biaya transportasi data adalah nol.
8. Jaringan bersifat homogen.

```
       Monolith (In-Memory Call)                Microservices (Network RPC)
       
   +------------------------------+         +------------+        Network Boundary
   | Service A                    |         | Service A  |        (Latency, Drops,
   |   |                          |         |            |         Partitions)
   |   v (Pointer dereference,    |         |  [Client]  |               |
   | Service B  ~nanoseconds)     |         +-----+------+               |
   |   |                          |               | (TCP Syn/Ack,        |
   |   +-> Return Result          |               |  TLS Handshake,      v
   +------------------------------+               |  Serialization)  +-------+
                                                  +----------------->| Svc B |
                                                  <-----------------+|(JSON/ |
                                                   (Timeout? Drop?   | Proto)|
                                                    Partial Failure?)+-------+
```

#### Mental Model: The Distributed Finite State Machine

Setiap panggilan RPC/HTTP harus diperlakukan sebagai operasi tri-state:
* **SUCCESS:** Operasi berhasil dieksekusi secara remote dan respon diterima.
* **FAILURE:** Operasi gagal dieksekusi secara remote (misal: validasi ditolak) dan respon error diterima secara eksplisit.
* **UNKNOWN:** Request dikirim, tetapi koneksi terputus sebelum respon diterima. Apakah server memprosesnya? Apakah database remote ter-update? **Kita tidak tahu.**

Arsitektur microservice Go yang tangguh dibangun di atas asumsi bahwa kondisi **UNKNOWN** adalah keniscayaan, bukan anomali. Setiap mutasi data harus idempoten, setiap I/O jaringan harus memiliki batasan waktu (`context.WithTimeout`), dan kegagalan parsial (*partial failures*) harus diisolasi agar tidak melumpuhkan seluruh klaster (*cascading failure*).

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah topologi komunikasi antarlayanan yang mengilustrasikan API Gateway, *Ingress Traffic*, komunikasi sinkron (gRPC/REST), dan propagasi Trace Context.

```
                          [ Client Request ]
                                  |
                                  v
                    +---------------------------+
                    |    API Gateway (Ingress)  |
                    |  - Auth Verification      |
                    |  - Rate Limiting          |
                    |  - Trace ID Generation    |
                    +-------------+-------------+
                                  |
            +---------------------+---------------------+
            | HTTP/1.1 (JSON)                           | gRPC (Protobuf/HTTP2)
            | Traceparent: 00-4bf9-01                   | Traceparent: 00-4bf9-01
            v                                           v
+-----------------------+                   +-----------------------+
|     Order Service     |                   |    Payment Service    |
| (Microservice A)      |                   | (Microservice B)      |
|                       |                   |                       |
|  +-----------------+  |                   |  +-----------------+  |
|  | Context Timeout |  |                   |  | Idempotency Eng |  |
|  +--------+--------+  |                   |  +--------+--------+  |
|           |           |                   |           |           |
|  +--------v--------+  |  gRPC (HTTP/2)    |  +--------v--------+  |
|  | Circuit Breaker +--+------------------>|  | Business Logic  |  |
|  +-----------------+  | (Payment Request) |  +--------+--------+  |
+-----------+-----------+                   +-----------+-----------+
            |                                           |
            v                                           v
      [ Postgres ]                                [ Redis Store ]
     (Orders Table)                             (Idempotency Keys)
```

#### Diagram Alur Eksekusi Inter-Service Call:
```
Client             OrderService (Caller)          PaymentService (Callee)
  |                         |                                |
  |-- POST /orders -------->|                                |
  |                         |-- [Inject Trace Context]       |
  |                         |-- [Check Circuit Breaker]      |
  |                         |                                |
  |                         |-- gRPC ProcessPayment() ------>|
  |                         |   (Deadlines: 2s)              |-- [Extract Trace Context]
  |                         |                                |-- [Check Idempotency]
  |                         |                                |-- [Execute Transaction]
  |                         |                                |
  |                         |<-- Status: OK (TxID: 9988) ----|
  |                         |                                
  |                         |-- [Record Metrics (Duration)]  |
  |<-- HTTP 201 Created ----|                                
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. Mekanisme `http.Transport` Connection Pooling di Go

Di balik kesederhanaan `http.Client`, terdapat runtime layer bernama `http.Transport`. Transport ini mengelola *connection pool* berbasis TCP keep-alive sockets:

* **`MaxIdleConns`:** Total koneksi *idle* (terbuka tapi tidak dipakai) di seluruh host yang disimpan dalam pool.
* **`MaxIdleConnsPerHost`:** Jumlah koneksi *idle* yang dialokasikan khusus untuk satu host target. **Secara default di Go nilainya adalah 2.** Dalam arsitektur microservices di mana Service A membombardir Service B dengan ratusan rps, nilai default ini memicu bencana: koneksi TCP yang selesai dipakai langsung ditutup (TCP FIN/RST) karena batas idle terlampaui, menyebabkan alokasi koneksi baru berulang kali (*TCP Handshake & TLS Overhead*).
* **`IdleConnTimeout`:** Waktu maksimal koneksi idle bertahan di memory sebelum dieksekusi oleh Go runtime.

```
       [ Go Routine 1 ]   [ Go Routine 2 ]   [ Go Routine N ]
              \                  |                  /
               v                 v                 v
            +-----------------------------------------+
            |            http.Transport               |
            |                                         |
            |  Pool: "payment.internal:443"           |
            |  [ Conn 1 (Busy) ]  [ Conn 2 (Idle) ]   |
            |  [ Conn 3 (Idle) ]  ...                 |
            +-----------------------------------------+
                                 |
                          TCP Socket Ring
                                 v
                     [ Network Interface Card ]
```

#### 2. HTTP/2 Multiplexing pada gRPC

Berbeda dari HTTP/1.1 yang membutuhkan banyak koneksi TCP untuk concurrency (karena *head-of-line blocking* di level HTTP), gRPC menggunakan HTTP/2 di atas satu koneksi TCP tunggal:

* **Frames & Streams:** Komunikasi dipecah menjadi frame-frame biner independen. Ratusan RPC konkuren dieksekusi secara simultan di dalam *streams* yang berbeda di atas satu socket TCP fisik.
* **HPACK Compression:** Header dikompresi untuk menghemat alokasi byte pada I/O jaringan.
* **Protobuf Serializer:** Go runtime melakukan serialisasi objek struct menjadi array byte compact berbasis *varint* dan field tag numerik, menghindari overhead scanning string teks dan alokasi memori besar seperti pada `json.Unmarshal`.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### 1. Distributed Idempotency (Kunci Idempotensi)

Ketika terjadi timeout jaringan (kondisi **UNKNOWN**), pemanggil (*client/caller*) wajib melakukan *retry*. Agar *retry* ini aman dan tidak mengeksekusi mutasi ganda (misalnya dua kali penarikan saldo), endpoint harus bersifat idempoten:
$$f(f(x)) = f(x)$$

Pola eksekusi idempotensi di callee:
1. Client mengirim header `X-Idempotency-Key: <UUIDv4>`.
2. Callee menguji keberadaan kunci tersebut di storage atomic (misal: Redis).
3. Menggunakan Redis `SET key value NX EX 120`:
   * Jika gagal (kunci sudah ada): Return respon yang dicache dari eksekusi sebelumnya atau return error `409 Conflict / In-Progress`.
   * Jika berhasil: Eksekusi transaksi, simpan hasil di Redis, return respon ke client.

#### 2. Resiliency Patterns: Timeout, Retry, Circuit Breaker

* **Context Deadlines:** Operasi I/O tanpa batasan deadline adalah *resource leak*. Setiap RPC client harus menetapkan deadline eksplisit:
  $$\text{Deadline} = t_{\text{current}} + \Delta t_{\text{budget}}$$
* **Retry dengan Exponential Backoff & Full Jitter:** Menghindari fenomena *thundering herd* (di mana ribuan client serentak melakukan retry dan membunuh downstream service):
  $$\text{Sleep} = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$
  Di mana $B$ adalah *base backoff*, dan $M$ adalah *maximum backoff*.
* **Circuit Breaker Finite State Machine:**
  * **CLOSED:** Aliran request normal. Metrik kegagalan dihitung dalam kurun waktu $T$.
  * **OPEN:** Jika rasio kegagalan melewati ambang batas ($\text{threshold} \ge X\%$), sirkuit berpindah ke OPEN. Semua request langsung di-reject secara lokal (*fail-fast*) tanpa menyentuh jaringan.
  * **HALF-OPEN:** Setelah masa pendinginan (*sleep window*), sejumlah kecil request percobaan diizinkan lewat. Jika sukses, sirkuit kembali ke CLOSED; jika gagal, kembali ke OPEN.

```
       +---------+   Failure threshold exceeded   +------+
       |         | -----------------------------> |      |
       | CLOSED  |                                | OPEN |
       |         | <----------------------------- |      |
       +---------+      Success threshold met     +------+
            ^                                        |
            |                                        | Sleep window
            |            +-----------+               | expires
            +----------- | HALF-OPEN | <-------------+
                         +-----------+
                          (Canary calls)
```

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi Resilient HTTP Client tingkat produksi di Go menggunakan `net/http`, `context`, Exponential Backoff, dan pengurasan (*draining*) socket yang benar.

```go
package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net"
	"net/http"
	"time"
)

// ResilientClient membungkus http.Client dengan transport yang di-tuning
type ResilientClient struct {
	httpClient *http.Client
	maxRetries int
	baseWait   time.Duration
	maxWait    time.Duration
}

// NewResilientClient menginisialisasi client dengan connection pool yang optimal
func NewResilientClient(maxRetries int, baseWait, maxWait time.Duration) *ResilientClient {
	transport := &http.Transport{
		Proxy: http.ProxyFromEnvironment,
		DialContext: (&net.Dialer{
			Timeout:   5 * time.Second,  // Batas waktu koneksi TCP
			KeepAlive: 30 * time.Second, // Interval TCP keep-alive probe
		}).DialContext,
		MaxIdleConns:        100,              // Total global idle sockets
		MaxIdleConnsPerHost: 25,               // Default Go = 2, dituning agar tidak bottleneck
		IdleConnTimeout:     90 * time.Second, // Durasi socket idle bertahan
		TLSHandshakeTimeout: 5 * time.Second,  // Timeout negosiasi TLS
		ExpectContinueTimeout: 1 * time.Second,
		ForceAttemptHTTP2:   true,
	}

	return &ResilientClient{
		httpClient: &http.Client{
			Transport: transport,
		},
		maxRetries: maxRetries,
		baseWait:   baseWait,
		maxWait:    maxWait,
	}
}

// ExecuteWithRetry mengeksekusi request HTTP dengan context deadline dan backoff
func (c *ResilientClient) ExecuteWithRetry(ctx context.Context, req *http.Request) (*http.Response, error) {
	var resp *http.Response
	var err error

	// Simpan body asli jika perlu dibaca berulang kali saat retry
	var bodyBytes []byte
	if req.Body != nil {
		bodyBytes, err = io.ReadAll(req.Body)
		if err != nil {
			return nil, fmt.Errorf("failed to read request body: %w", err)
		}
		_ = req.Body.Close()
	}

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		// Pasang kembali body reader untuk setiap iterasi attempt
		if bodyBytes != nil {
			req.Body = io.NopCloser(bytes.NewReader(bodyBytes))
		}

		// Kaitkan request dengan konteks eksekusi
		reqWithCtx := req.Clone(ctx)

		resp, err = c.httpClient.Do(reqWithCtx)
		if err == nil && resp.StatusCode < http.StatusInternalServerError {
			// Berhasil atau Client Error (4xx) yang tidak perlu di-retry
			return resp, nil
		}

		// Kuras dan tutup body respon error sebelum retry untuk reuse koneksi
		if resp != nil {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
		}

		// Cek jika error terjadi akibat konteks dibatalkan oleh caller
		if ctx.Err() != nil {
			return nil, fmt.Errorf("client context cancelled: %w", ctx.Err())
		}

		if attempt == c.maxRetries {
			break
		}

		// Hitung Backoff + Full Jitter
		backoff := c.calculateJitter(attempt)
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(backoff):
		}
	}

	if err != nil {
		return nil, fmt.Errorf("request failed after %d retries: %w", c.maxRetries, err)
	}

	return resp, errors.New("upstream service unavailable (HTTP 5xx)")
}

func (c *ResilientClient) calculateJitter(attempt int) time.Duration {
	// Formula: Sleep = rand(0, min(maxWait, baseWait * 2^attempt))
	multiplier := 1 << attempt
	temp := c.baseWait * time.Duration(multiplier)
	if temp > c.maxWait {
		temp = c.maxWait
	}

	n, _ := rand.Int(rand.Reader, big.NewInt(int64(temp)))
	return time.Duration(n.Int64())
}

func main() {
	client := NewResilientClient(3, 100*time.Millisecond, 2*time.Second)

	// Buat context dengan global timeout 5 detik
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	payload := map[string]string{"account_id": "ACC-1092", "amount": "5000"}
	marshaled, _ := json.Marshal(payload)

	req, _ := http.NewRequest(http.MethodPost, "https://httpbin.org/status/503,200", bytes.NewReader(marshaled))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Idempotency-Key", "uuid-a88f-431e")

	resp, err := client.ExecuteWithRetry(ctx, req)
	if err != nil {
		fmt.Printf("Execution failed: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	fmt.Printf("Response received [%d]: %s\n", resp.StatusCode, string(body))
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 29–42 (`NewResilientClient`):** Melakukan modifikasi eksplisit pada `http.Transport`. Kita menaikkan `MaxIdleConnsPerHost` dari default `2` menjadi `25`. Tanpa modifikasi ini, pada beban 100 concurrent goroutine ke target upstream yang sama, Go akan menutup 98 koneksi TCP seketika, memaksa siklus alokasi socket, 3-way handshake, dan TLS setup baru yang menguras *CPU sys time* dan *file descriptors*.
* **Baris 62–71 (`bodyBytes` handling):** Komponen vital. Tipe `req.Body` bertipe `io.ReadCloser` yang hanya bisa dikonsumsi satu kali (*single stream*). Jika attempt pertama gagal, stream sudah kosong. Kode ini membaca data payload ke memori sekali, lalu meregenerasi stream menggunakan `io.NopCloser(bytes.NewReader(bodyBytes))` pada tiap retry attempt.
* **Baris 82–85 (`io.Copy(io.Discard, resp.Body)`):** Penanganan kritis TCP reuse. Di Go, agar koneksi TCP underlying dapat dikembalikan ke pool untuk digunakan kembali, HTTP body harus dibaca hingga selesai (`io.EOF`) sebelum method `.Close()` dipanggil. Memanggil `.Close()` langsung pada body yang belum tuntas dibaca akan memaksa transport menutup koneksi TCP secara prematur.
* **Baris 97–102 (`calculateJitter`):** Mengimplementasikan algoritma *Full Jitter*. Menggunakan `crypto/rand` untuk menghasilkan sebaran pseudorandom uniform di antara rentang 0 hingga limit interval backoff eksponensial. Ini memecah gelombang retry serentak dari ribuan instance microservice.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario: "The Silent Payment Blackout"
Sebuah platform fintech skala regional mengalami masalah cascading outage di mana seluruh instans API Gateway dan Payment Service mengalami *crash* berantai, memicu OOM (Out Of Memory) dan latensi 30 detik pada semua rute API.

#### Akar Masalah (Root Cause):
1. **Unbounded Idle Connections & Slow Upstream:** Layanan Payment Provider eksternal mengalami penurunan performa internal, meningkatkan latensi pemrosesan dari 200ms menjadi 12 detik.
2. **Missing Deadlines:** Payment Service internal memanggil provider eksternal menggunakan `http.DefaultClient` yang tidak memiliki timeout default (`Timeout: 0`).
3. **Goroutine Explosion:** Setiap request client Go menelurkan goroutine baru untuk melayani HTTP request. Karena koneksi menggantung tanpa batas waktu selama 12 detik sementara traffic terus masuk sebesar 500 RPS, jumlah goroutine Payment Service melonjak dari 400 menjadi 65.000 goroutine dalam kurun 3 menit.
4. **Alokasi Memori Meluap:** Tiap goroutine membawa stack minimal 2KB-8KB beserta alokasi buffer I/O. Memori melonjak dari 150MB hingga menabrak cgroup limit Kubernetes di 2GB. Pods mengalami OOM-Killed berulang kali.

#### Solusi Arsitektural:
1. Mengganti `http.DefaultClient` dengan Client terisolasi yang menerapkan `context.WithTimeout` keras (maksimal 2.5 detik).
2. Memasang **Circuit Breaker** (Sony/Gobreaker pattern) di hadapan client pemanggil Payment Provider. Ketika error rate melebihi 20%, sirkuit terbuka langsung dan request ditolak seketika (*fail-fast* dalam <1ms), melindungi sistem dari penumpukan goroutine.
3. Mengadopsi **Idempotency Key Database** untuk mencegah pembayaran tertagih dua kali ketika client Gateway melakukan *failover retry*.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem produksi lengkap yang mencakup:
1. **Circuit Breaker Pattern** state machine terisolasi berbasis atomics dan mutex.
2. **Trace Context Propagation** lintas batas jaringan menggunakan format standar W3C.
3. Handler HTTP yang mengeksekusi logika pemanggilan antarlayanan secara aman.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"
)

// --- BAGIAN 1: RESILIENT CIRCUIT BREAKER ---

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

var ErrCircuitOpen = errors.New("circuit breaker is OPEN: requests blocked")

type CircuitBreaker struct {
	mu           sync.RWMutex
	state        State
	failures     int64
	threshold    int64
	cooldown     time.Duration
	lastStateChg time.Time
}

func NewCircuitBreaker(threshold int64, cooldown time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:        StateClosed,
		threshold:    threshold,
		cooldown:     cooldown,
		lastStateChg: time.Now(),
	}
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
	cb.mu.Lock()
	now := time.Now()

	// Evaluasi transisi dari OPEN ke HALF-OPEN
	if cb.state == StateOpen {
		if now.Sub(cb.lastStateChg) > cb.cooldown {
			cb.state = StateHalfOpen
			cb.lastStateChg = now
		} else {
			cb.mu.Unlock()
			return ErrCircuitOpen
		}
	}
	cb.mu.Unlock()

	// Eksekusi fungsi target
	err := fn()

	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		cb.failures++
		if cb.state == StateHalfOpen || cb.failures >= cb.threshold {
			cb.state = StateOpen
			cb.lastStateChg = time.Now()
		}
		return err
	}

	// Sukses dieksekusi
	if cb.state == StateHalfOpen {
		cb.state = StateClosed
		cb.failures = 0
		cb.lastStateChg = time.Now()
	} else if cb.state == StateClosed {
		cb.failures = 0
	}

	return nil
}

// --- BAGIAN 2: TRACE CONTEXT PROPAGATION (W3C Standard) ---

const TraceParentHeader = "traceparent"

type TraceContext struct {
	TraceID string
	SpanID  string
}

func InjectTraceContext(ctx context.Context, req *http.Request) {
	if val := ctx.Value("trace_ctx"); val != nil {
		if tc, ok := val.(TraceContext); ok {
			headerVal := fmt.Sprintf("00-%s-%s-01", tc.TraceID, tc.SpanID)
			req.Header.Set(TraceParentHeader, headerVal)
		}
	}
}

// --- BAGIAN 3: SERVICE CLIENT WITH INSTRUMENTATION ---

type PaymentServiceClient struct {
	cb     *CircuitBreaker
	client *http.Client
}

func (c *PaymentServiceClient) Charge(ctx context.Context, orderID string, amount int64) error {
	return c.cb.Execute(func() error {
		reqCtx, cancel := context.WithTimeout(ctx, 800*time.Millisecond)
		defer cancel()

		req, err := http.NewRequestWithContext(
			reqCtx,
			http.MethodPost,
			"http://127.0.0.1:8081/v1/charge",
			nil,
		)
		if err != nil {
			return err
		}

		// Inject trace context lintas network boundary
		InjectTraceContext(ctx, req)
		req.Header.Set("X-Order-ID", orderID)

		resp, err := c.client.Do(req)
		if err != nil {
			return err
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 500 {
			return fmt.Errorf("remote server returned status: %d", resp.StatusCode)
		}
		return nil
	})
}

// --- BAGIAN 4: SERVER IMPLEMENTATION (MOCK INFRASTRUCTURE) ---

func startMockPaymentGateway(failureTrigger *int32) *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/charge", func(w http.ResponseWriter, r *http.Request) {
		// Observasi traceparent yang dikirim client
		traceParent := r.Header.Get(TraceParentHeader)
		slog.Info("Downstream received request", "traceparent", traceParent)

		if atomic.LoadInt32(failureTrigger) == 1 {
			// Simulasi degradasi internal downstream (500 Internal Error)
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"SUCCESS"}`))
	})

	srv := &http.Server{
		Addr:    ":8081",
		Handler: mux,
	}

	go func() {
		_ = srv.ListenAndServe()
	}()

	return srv
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	var downstreamFailure int32 = 0
	srv := startMockPaymentGateway(&downstreamFailure)
	defer srv.Close()

	cb := NewCircuitBreaker(3, 2*time.Second)
	client := &PaymentServiceClient{
		cb:     cb,
		client: &http.Client{Timeout: 2 * time.Second},
	}

	ctx := context.WithValue(context.Background(), "trace_ctx", TraceContext{
		TraceID: "4bf92f3577b34da6a3ce929d0e0e4736",
		SpanID:  "00f067aa0ba902b7",
	})

	slog.Info("Menjalankan panggilan normal (Healthy State)...")
	for i := 1; i <= 3; i++ {
		err := client.Charge(ctx, fmt.Sprintf("ORD-%03d", i), 1000)
		slog.Info("Charge Result", "attempt", i, "error", err, "cb_state", cb.state.String())
	}

	slog.Warn("Menginduksi Downstream Failure (Error State)...")
	atomic.StoreInt32(&downstreamFailure, 1)

	for i := 4; i <= 8; i++ {
		err := client.Charge(ctx, fmt.Sprintf("ORD-%03d", i), 1000)
		slog.Error("Charge Result", "attempt", i, "error", err, "cb_state", cb.state.String())
		time.Sleep(100 * time.Millisecond)
	}

	slog.Info("Downstream dipulihkan. Menunggu sirkuit Cooldown...")
	atomic.StoreInt32(&downstreamFailure, 0)
	time.Sleep(2100 * time.Millisecond)

	slog.Info("Mengeksekusi Canary Request pada State Half-Open...")
	for i := 9; i <= 10; i++ {
		err := client.Charge(ctx, fmt.Sprintf("ORD-%03d", i), 1000)
		slog.Info("Canary Result", "attempt", i, "error", err, "cb_state", cb.state.String())
	}
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih protokol integrasi antar-microservice di ekosistem Go memiliki konsekuensi langsung pada arsitektur perangkat keras dan efisiensi throughput:

| Dimensi Evaluasi | REST (HTTP/1.1 + JSON) | gRPC (HTTP/2 + Protobuf) | Async Event-Driven (e.g., NATS/Kafka) |
| :--- | :--- | :--- | :--- |
| **Payload Size & Efficiency** | Boros string parsing; overhead teks JSON tinggi. | Ekstrem compact; serialisasi native binary protobuf via struct Go. | Sangat efisien; bergantung skema data (Avro, Protobuf, JSON). |
| **Throughput / Latency** | Menengah-Rendah (~5k-15k RPS/core); terhambat alokasi string. | Tinggi (~50k-100k RPS/core); multiplexing pada single TCP stream. | Sangat Tinggi (>200k Msg/sec); batch processing decoupled. |
| **Coupling / Dependensi** | Temporal Coupling (Pemanggil menunggu pemrosesan). | Temporal Coupling (Sinkron; callee harus online). | Decoupled penuh secara Temporal dan Spasial. |
| **Kemudahan Debugging** | Mudah (Human-readable plaintext; `curl`, Postman). | Membutuhkan tools khusus (`grpcurl`, reflection). | Membutuhkan tracing queue/event dump khusus. |
| **Contract Enforcement** | Longgar; bergantung OpenAPI spec validator eksternal. | Ketat; *compile-time type generation* (`protoc-gen-go`). | Tergantung Skema Registry (misal: Schema Registry Kafka). |
| **Streaming Support** | Terbatas (Server-Sent Events, Chunked transfer). | Full Duplex Streaming (Client, Server, Bidirectional). | Pure Event Stream via pub-sub broker. |

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. HTTP Body Leak & Connection Exhaustion
* **Anatomi:** Pemanggilan `http.Get()` atau `client.Do()` menghasilkan pointer `*http.Response`. Jika aplikasi mengecek `err != nil`, lalu keluar dari fungsi tanpa membaca seluruh isi `resp.Body` dan memanggil `.Close()`, file descriptor socket TCP sistem operasi akan menggantung pada status `CLOSE_WAIT`.
* **Dampak:** Server kehabisan soket jaringan (`cannot assign requested address` atau `too many open files`), melumpuhkan semua goroutine I/O.
* **Mitigasi:** Selalu gunakan idiom standard:
  ```go
  resp, err := client.Do(req)
  if err != nil {
      return err
  }
  defer resp.Body.Close()
  io.Copy(io.Discard, resp.Body) // Drain body jika payload tidak dikonsumsi
  ```

#### 2. Goroutine Context Cancellation Leak
* **Anatomi:** Menggunakan goroutine background di dalam HTTP handler tanpa memantau channel `ctx.Done()`. Ketika koneksi client terputus di tengah jalan, HTTP server Go membatalkan context handler. Goroutine background yang tidak mendengarkan `ctx.Done()` akan terus memproses data sia-sia (*zombie execution*).
* **Mitigasi:** Pass `ctx` secara eksplisit dan verifikasi pembatalan sebelum operasi berat.

#### 3. Proto3 Default Values Semantic Ambiguity
* **Anatomi:** Pada Protobuf v3, tipe primitif (seperti `int32 = 0`, `string = ""`, `bool = false`) tidak diserialisasi ke dalam wire format jika bernilai default. Pemanggil yang mengirim `{"status": 0}` akan diterima callee sebagai kondisi kosong/unset jika tidak menggunakan wrapper types (`google.protobuf.Int32Value`) atau fitur `optional`.
* **Dampak:** Kehilangan presisi diferensiasi antara nilai bernilai 0 vs data tidak dikirim.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Anti-Pattern 1: Penggunaan `http.DefaultClient` di Microservices

```go
// BURUK: Menggunakan singleton DefaultClient tanpa timeout
func CallRemote(url string) error {
    resp, err := http.Get(url) // DefaultClient.Timeout = 0 (Selamanya!)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    return nil
}
```

```go
// BAIK: Instansiasi Client terisolasi dengan Timeout & Transport spesifik
var sharedClient = &http.Client{
    Timeout: 3 * time.Second, // Timeout global mencakup DNS + Handshake + Body
    Transport: &http.Transport{
        MaxIdleConnsPerHost: 20,
    },
}

func CallRemote(ctx context.Context, url string) error {
    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return err
    }
    resp, err := sharedClient.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    _, _ = io.Copy(io.Discard, resp.Body)
    return nil
}
```

#### Anti-Pattern 2: Dynamic Error String Checking Lintas Layanan

```go
// BURUK: Pengecekan string error jaringan secara manual
if err.Error() == "connection reset by peer" {
    // Retry... Sangat rapuh terhadap perubahan internal library / OS
}
```

```go
// BAIK: Pengecekan berbasis tipe network assertion (net.Error)
var netErr net.Error
if errors.As(err, &netErr) && netErr.Timeout() {
    // Penanganan timeout secara deterministik
}
```

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Explicit Context Parameterization:** Selalu jadikan `ctx context.Context` sebagai argumen pertama di setiap method I/O lintas layanan (`func (s *Service) Call(ctx context.Context, ...)`). Jangan pernah menyematkan `Context` ke dalam sebuah struct data.
2. **Contract-First Development:** Buat file `.proto` (atau OpenAPI 3.0 YAML) sebagai sumber kebenaran tunggal (*Single Source of Truth*). Generate Go struct dan interface client/server menggunakan skrip automasi (`buf.build` atau Makefile). Jangan membuat struct Go manual lalu menggenerasi proto dari kode (*Code-First adalah anti-pattern dalam microservices skala besar*).
3. **Structured Semantic Logging:** Jangan pernah menggunakan `fmt.Println` atau modul `log` standar. Gunakan `log/slog` bawaan Go dengan atribut terstruktur yang secara konsisten mencetak `trace_id`, `span_id`, dan `service_name`.
4. **Graceful Shutdown Inter-Service:** Microservice Go wajib menangkap sinyal OS (`SIGINT`, `SIGTERM`) untuk menghentikan listener jaringan dan menyelesaikan request I/O aktif menggunakan `server.Shutdown(ctx)` sebelum proses terminated.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

#### 1. Menghilangkan Alokasi Heap pada Buffer Serialisasi

Dalam pemrosesan jutaan HTTP/gRPC requests, garbage collector (GC) Go terbebani alokasi buffer byte temporer. Manfaatkan `sync.Pool` untuk pooling memory byte reader/writer:

```go
var bufferPool = sync.Pool{
	New: func() any {
		return new(bytes.Buffer)
	},
}

func MarshalPayloadFast(data any) (*bytes.Buffer, error) {
	buf := bufferPool.Get().(*bytes.Buffer)
	buf.Reset() // Bersihkan buffer sebelum digunakan kembali

	enc := json.NewEncoder(buf)
	if err := enc.Encode(data); err != nil {
		bufferPool.Put(buf)
		return nil, err
	}
	return buf, nil
}

func ReleaseBuffer(buf *bytes.Buffer) {
	bufferPool.Put(buf)
}
```

#### 2. Tuning Kernel Network Parameter untuk Go

Pada skala microservice puluhan ribu RPS per-node, parameter bawaan OS Linux membatasi performa aplikasi Go. Optimasi konfigurasi `/etc/sysctl.conf`:
* `net.core.somaxconn = 65535` (Menaikkan batas antrean TCP backlog connection).
* `net.ipv4.tcp_tw_reuse = 1` (Mengizinkan penggunaan kembali soket dalam state `TIME_WAIT`).
* `net.ipv4.ip_local_port_range = 1024 65535` (Memperluas range port keluar untuk outgoing RPC calls).

---

### SEKSI 16 — KEAMANAN & HARDENING

#### 1. Mutual TLS (mTLS) Zero-Trust Enforcement

Dalam topologi microservice modern, perimeter jaringan private tidak menjamin keamanan. Komunikasi inter-service harus dienkripsi dan diotentikasi timbal balik (mTLS) di level transport Go:

```go
func LoadMutualTLSCredentials(certFile, keyFile, caFile string) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, err
	}

	caCert, err := os.ReadFile(caFile)
	if err != nil {
		return nil, err
	}

	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, errors.New("failed to append root CA cert")
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		ClientCAs:    caCertPool,
		ClientAuth:   tls.RequireAndVerifyClientCert, // Wajibkan cert client terdaftar
		MinVersion:   tls.VersionTLS13,               // Enforce TLS 1.3
	}, nil
}
```

#### 2. Hardening API Ingress
* **Strict Payload Parsing:** Gunakan `json.NewDecoder(r.Body).DisallowUnknownFields()` untuk menolak request payload dengan skema yang tidak terdefinisi (mencegah *mass assignment vulnerability*).
* **Limit Reader Protection:** Bungkus semua pembacaan request stream dengan `http.MaxBytesReader(w, r.Body, maxAllowedBytes)` untuk mencegah Denial of Service berbasis *large memory allocation attack*.

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Terapkan standar **The RED Method** (Rate, Errors, Duration) pada setiap antarmuka layanan microservice Go:

```go
package main

import (
	"log/slog"
	"net/http"
	"time"
)

type StatusRecorder struct {
	http.ResponseWriter
	StatusCode int
}

func (r *StatusRecorder) WriteHeader(code int) {
	r.StatusCode = code
	r.ResponseWriter.WriteHeader(code)
}

// ObserveMiddleware menyuntikkan structured logging dan metrik durasi
func ObserveMiddleware(serviceName string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &StatusRecorder{ResponseWriter: w, StatusCode: http.StatusOK}

		// Ekstrak W3C traceparent jika ada
		traceID := r.Header.Get("traceparent")

		next.ServeHTTP(rec, r)

		duration := time.Since(start)

		// Structured Logging via slog
		slog.Info("Handled Inter-Service HTTP Call",
			"service", serviceName,
			"method", r.Method,
			"path", r.URL.Path,
			"status", rec.StatusCode,
			"duration_ms", duration.Milliseconds(),
			"trace_id", traceID,
			"remote_addr", r.RemoteAddr,
		)
	})
}
```

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

1. **Jaringan Selalu Gagal:** Selalu asumsikan jaringan akan putus, delay, atau packet-loss di sembarang waktu.
2. **Context Adalah Hukum:** Jangan pernah melakukan Network I/O tanpa menyertakan `context.Context` yang memiliki deadline batas waktu.
3. **Kuras Body:** `io.Copy(io.Discard, resp.Body)` dan `resp.Body.Close()` adalah ritual wajib di Go agar socket TCP keep-alive tidak bocor.
4. **Tune MaxIdleConnsPerHost:** Nilai default Go (`2`) terlalu kecil untuk microservices ber-throughput tinggi; naikkan sesuai kapasitas concurrency host.
5. **Fail-Fast via Circuit Breakers:** Jangan biarkan downstream lambat menumpuk puluhan ribu goroutine di service Anda. Gunakan Circuit Breaker untuk menolak request secepat mungkin (<1ms).
6. **Idempotensi adalah Perlindungan Retry:** Client tidak dapat melakukan retry yang aman tanpa callee menyediakan idempotency handling berbasis ID transaksi unik.
7. **Bawa Konteks Jejak (Trace Parent):** Selalu propagasikan header OpenTelemetry / W3C TraceContext ke panggilan turunan agar rantai eksekusi terdistribusi dapat dilacak dari hulu ke hilir.

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Bagian A (Tingkat Basic)

1. **Apa implikasi langsung terhadap performa sistem jika engineer memanggil `http.Get()` menggunakan default setting tanpa memodifikasi `MaxIdleConnsPerHost` pada high load microservice?**
   * *Jawaban:* Nilai defaultnya adalah 2. Ketika ada banyak concurrent request ke host yang sama, hanya 2 koneksi idle yang disimpan ke pool per-host. Sisa koneksi yang selesai digunakan langsung ditutup (FIN), memicu alokasi socket berulang-ulang, lonjakan overhead handshake TCP/TLS, dan kehabisan ephemeral port OS.

2. **Mengapa pemanggilan `defer resp.Body.Close()` saja tidak cukup untuk menjamin koneksi TCP digunakan kembali (keep-alive)?**
   * *Jawaban:* Go runtime mewajibkan data dalam buffer socket HTTP stream dibaca seluruhnya hingga end-of-file (`io.EOF`). Jika body belum dibaca habis, Go terpaksa memutus koneksi underlying TCP alih-alih mengembalikannya ke pool. Pengurasan dilakukan via `io.Copy(io.Discard, resp.Body)`.

3. **Apa perbedaan mendasar antara `context.WithTimeout` dan `http.Client.Timeout`?**
   * *Jawaban:* `http.Client.Timeout` adalah batas waktu global absolut untuk seluruh siklus request (DNS resolution, connection setup, redirection, hingga pembacaan response body selesai). Sedangkan `context.WithTimeout` dapat dikontrol secara dinamis dan dibatalkan (*cancelled*) sewaktu-waktu oleh aplikasi sebelum durasi waktu habis.

4. **Bagaimana format struktur header W3C `traceparent` standar?**
   * *Jawaban:* Terdiri dari 4 segmen terpisah tanda hubung: `version-traceid-parentid-traceflags` (Contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).

5. **Mengapa pola *retry* murni tanpa *jitter* dikategorikan sebagai anti-pattern fatal pada sistem microservice?**
   * *Jawaban:* Tanpa jitter, ratusan/ribuan instans yang gagal akibat downstream glitch akan menghitung interval waktu backoff yang persis sama, lalu menyerang upstream secara serentak pada detik yang sama (*Thundering Herd Problem*).

#### Bagian B (Tingkat Intermediate)

6. **Dalam implementasi Circuit Breaker, jelaskan kondisi tepat yang memicu state bertransisi dari `HALF-OPEN` kembali ke `OPEN` versus kembali ke `CLOSED`!**
   * *Jawaban:* Pada state `HALF-OPEN`, Circuit Breaker melepas sejumlah canary call (misal: 1 atau beberapa request pengujian). Jika salah satu canary call tersebut mengalami kegagalan (failure), circuit breaker langsung kembali ke state `OPEN` untuk mencegah beban lebih lanjut. Jika canary calls berhasil mencapai ambang batas kesuksesan yang ditetapkan, sirkuit bertransisi ke `CLOSED` dan reset metrik kegagalan ke 0.

7. **Jelaskan mengapa pemanggilan `req.Clone(ctx)` krusial dilakukan di dalam loop retry client Go!**
   * *Jawaban:* Method `http.Client.Do` dapat memodifikasi state internal dari request. Selain itu, jika context attempt sebelumnya telah timeout atau di-cancel, membuat clone request dengan context baru atau context terikat memastikan tidak ada pembatalan silang antar iterasi attempt.

8. **Bagaimana Anda menangani isu backward compatibility pada payload Protobuf v3 ketika ada field struct yang deprecated?**
   * *Jawaban:* Nomor tag field pada protobuf tidak boleh digunakan ulang atau diubah tipenya. Field lama harus diberi anotasi `reserved <field_number>, "<field_name>";` untuk mencegah developer lain menggunakan tag tersebut di masa depan yang dapat mengacaukan deserialisasi biner pada sistem lama yang belum diupdate.

9. **Apa risiko arsitektur menggunakan shared database antar dua microservice Go yang berbeda?**
   * *Jawaban:* Pelanggaran batas domain (*Bounded Context*). Ini menciptakan kopling skema basis data implisit, menghilangkan independensi deployment, merusak isolasi kegagalan, dan memicu risiko *database deadlocks* karena concurrency dikendalikan oleh dua aplikasi independen tanpa koordinasi terpadu.

10. **Bagaimana mitigasi race condition pada alokasi Idempotency Key di Redis dalam sistem pemrosesan transaksi Go?**
    * *Jawaban:* Menggunakan perintah atomik `SET key unique_worker_id NX EX <ttl>`. Opsi `NX` (Not Exists) menjamin Redis mengeksekusi operasi simpan hanya jika key belum terdaftar. Jika respon Redis adalah `nil/false`, worker Go langsung tahu bahwa transaksi tersebut sedang/sudah dieksekusi proses lain.

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Deskripsi Tantangan
Rancang dan bangun sistem simulasi microservice pemrosesan pesanan (**Order-to-Fulfillment Pipeline**) yang terdiri dari 2 microservice mandiri berbasis Go:

1. **Order Service (Port :8080):** Menerima order masuk dari user melalui REST endpoint `POST /api/orders`.
2. **Fulfillment Service (Port :8082):** Menerima mutasi alokasi inventaris melalui endpoint internal dengan otentikasi header token.

#### Syarat Fungsional & Non-Fungsional:
1. **Contract-First & Idempotent:** Request `POST /api/orders` harus mewajibkan header `X-Idempotency-Key`. Jika ID yang sama dikirim dua kali dengan status order yang telah diproses, return payload respon yang sama tanpa mengeksekusi ulang alokasi inventaris.
2. **Resilience Pipeline:** Pemanggilan dari Order Service ke Fulfillment Service harus dibungkus oleh custom `ResilientTransport` yang mengintegrasikan:
   * Batasan Timeout context 1 detik.
   * Circuit Breaker (Threshold: 3 failures, Cooldown: 5 detik).
   * Retry with Exponential Backoff & Full Jitter (Max 3 attempt).
3. **Observabilitas Terdistribusi:** Injeksi W3C Trace Context header (`traceparent`) dari Order Service ke Fulfillment Service. Cetak log terstruktur (`log/slog`) di kedua layanan yang memuat `trace_id` yang identik untuk tiap request flow.
4. **Chaos Endpoint:** Implementasikan rute internal di Fulfillment Service: `POST /chaos/inject-latency` dan `POST /chaos/inject-failures` untuk mendemonstrasikan transisi status Circuit Breaker dari `CLOSED` $\to$ `OPEN` $\to$ `HALF-OPEN` $\to$ `CLOSED` secara live di log terminal.

#### Rubrik Penilaian:
* **Zero Leakage:** Tidak ada kebocoran goroutine saat chaos dialirkan (verifikasi via `runtime.NumGoroutine()`).
* **Connection Reusability:** Socket TCP tidak memicu status `CLOSE_WAIT` berlebih saat dites beban (verifikasi via `netstat -an | grep 8082`).
* **Code Idioms:** Pemanfaatan channel, context cancellation, dan error handling Go murni tanpa library circuit-breaker eksternal pihak ketiga (semua logika ketahanan dibangun hands-on).