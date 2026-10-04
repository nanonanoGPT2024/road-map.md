# Kurikulum Rekayasa Perangkat Lunak Enterprise: Go (Golang)
## Kategori: 02-Programming-Languages
### BAB-07: Microservices Architecture & API Design
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal gRPC dan HTTP/2 multiplexing pada Go Runtime (`google.golang.org/grpc`).
- Mengimplementasikan rantai *Interceptors* (Middleware) enterprise-grade untuk observabilitas (OpenTelemetry), keamanan (mTLS), dan keandalan sistem.
- Menerapkan pola ketahanan terdistribusi (*distributed resiliency patterns*): *Circuit Breaker*, *Adaptive Rate Limiting*, *Retry with Jitter*, dan *Bulkheading* secara murni (*pure Go*) dan melalui integrasi library performa tinggi.
- Mengelola propagasi konteks (*Context & Metadata Propagation*) lintas batas jaringan untuk penelusuran terdistribusi (*distributed tracing*) dan pencegahan *resource leakage*.
- Merancang dan mengeksekusi arsitektur *high-throughput*, *low-latency* microservices yang siap menangani beban skala jutaan RPS dengan *graceful degradation* dan *zero-downtime deployment*.

---

## 2. Prerequisite
Untuk mencerna materi ini secara optimal, peserta wajib memahami:
- Sintaksis lanjut Go: Concurrency primitives (`sync.Pool`, `sync.WaitGroup`, `errgroup`, `chan`), Goroutine runtime scheduling (M:N scheduler).
- Konsep dasar RPC dan Protocol Buffers v3 (`proto3`).
- Dasar jaringan komputer: TCP 3-way handshake, TLS 1.3 handshake, HTTP/1.1 vs HTTP/2 semantics (Frames, Streams, HPACK compression).
- Ekosistem Docker dan Kubernetes dasar (Pods, Services, Lifecycle Probes).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 HTTP/2 Transport Engine pada gRPC Go
Di balik performa tinggi gRPC Go, terdapat implementasi transport layer berbasis HTTP/2 standar RFC 7540 yang dimodifikasi untuk efisiensi transfer data biner:

```
+-----------------------------------------------------------------------+
|                           Application Layer                           |
|                       Generated Protobuf Stubs                        |
+-----------------------------------------------------------------------+
|                    gRPC Core & Interceptor Pipeline                   |
|  [Auth] -> [Tracing] -> [Metrics] -> [RateLimit] -> [Panic Recovery]  |
+-----------------------------------------------------------------------+
|                       HTTP/2 Transport Engine                         |
|  +--------------------+  +--------------------+  +-----------------+  |
|  | Stream ID: 1       |  | Stream ID: 3       |  | Stream ID: 5    |  |
|  | HEADERS/DATA Frame |  | HEADERS/DATA Frame |  | RST_STREAM Frame|  |
|  +--------------------+  +--------------------+  +-----------------+  |
|                         HPACK Dynamic Table                           |
+-----------------------------------------------------------------------+
|                      TCP Layer (Single TCP Conn)                      |
|                  SO_KEEPALIVE, TCP_NODELAY, TLS 1.3                   |
+-----------------------------------------------------------------------+
```

1. **Multiplexing via Streams**: Berbeda dari HTTP/1.1 yang membutuhkan *pool connection* TCP terpisah untuk konkurensi (atau mengalami *Head-of-Line (HoL) Blocking* di level HTTP), gRPC menggunakan satu koneksi TCP tunggal untuk ribuan panggilan RPC secara bersamaan. Setiap panggilan diisolasi ke dalam *Stream* logis independen dengan 31-bit identifier.
2. **HPACK Compression**: Header metadata dikompresi menggunakan algoritma HPACK berbasis Huffman coding dan *dynamic table*. Metadata berulang (seperti token JWT yang sama) tidak dikirim ulang secara utuh, melainkan ditransmisikan sebagai referensi indeks tabel numerik (menghemat bandwidth hingga 85%).
3. **Flow Control Lanjut (Window Updates)**: gRPC mengimplementasikan *credit-based flow control* pada level Stream dan Connection secara simultan via frame `WINDOW_UPDATE`. Hal ini mencegah produser cepat menenggelamkan konsumen lambat (*buffer bloat*) langsung pada tingkat transport, tanpa memerlukan alokasi buffer yang tidak terbatas pada memori Go runtime.

### 3.2 Context & Cancellation Propagation Deep Dive
`context.Context` bukan sekadar pembawa nilai (*key-value bag*), melainkan pohon relasi (*cancellation tree*) yang mengatur masa hidup komputasi terdistribusi.

```
                    Client Root Context
                             |
                     WithTimeout(500ms)
                             |
              gRPC Outgoing Context (Metadata)
                             |
                 [Jaringan: Wire Protocol]
              grpc-timeout: 498m (HTTP/2 Header)
                             |
              gRPC Incoming Context (Server)
                             |
             +---------------+---------------+
             |                               |
     Worker Goroutine 1              Worker Goroutine 2
   (Database Read via I/O)       (Upstream Payment Gateway)
```

Ketika klien menginisiasi gRPC call dengan batas waktu 500ms:
1. gRPC client runtime menghitung sisa deadline dan menginjeksikannya ke dalam header HTTP/2 biner bernama `grpc-timeout`.
2. Klien juga menyematkan metadata W3C TraceContext (`traceparent`) atau B3 header ke frame `HEADERS`.
3. Sisi server menerima frame, membaca `grpc-timeout`, dan secara otomatis membungkus root context server dengan `context.WithDeadline` sesuai sisa waktu transmisi jaringan.
4. Jika waktu habis (*deadline exceeded*) saat server masih memproses I/O, server menerima sinyal melalui channel `ctx.Done()`. Sub-goroutine dapat langsung membatalkan query database dan transaksi upstream seketika, mencegah fenomena **Wasted Work Propagation**.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Monolith/Naive REST) | Pendekatan Advanced Microservices (Go + gRPC) |
| :--- | :--- | :--- |
| **Protokol Wire** | JSON berbasis teks via HTTP/1.1 (Parsing berat, CPU bound) | Protobuf v3 biner via HTTP/2 (Serialisasi zero-overhead, hemat CPU) |
| **Koneksi Jaringan**| Transient TCP connections, re-handshake TLS berulang | Persistent multiplexed TCP, single socket amortized handshake |
| **Penanganan Kegagalan** | Retry tanpa batas (memicu *Retry Storms* & *Thundering Herd*) | Circuit Breaker adaptif + Exponential Backoff + Full Jitter |
| **Tracing System** | Log terisolasi per server dengan ID manual | Otomatisasi Context Traceparent terintegrasi OpenTelemetry SDK |
| **Type Safety** | Lemah (bergantung dokumentasi Swagger yang sering usang) | Kuat dan deterministik via *Strict Schema Contract* (.proto) |

**Mengapa Arsitektur Ini Penting?**
Dalam sistem monolitik, pemanggilan fungsi bersifat in-memory dengan latensi nanodetik dan probabilitas kegagalan nol (kecuali *kernel panic*). Dalam arsitektur *microservices*, setiap fungsi RPC melewati media fisik jaringan yang *unreliable*, memiliki latensi bervariasi (milliseconds), dan rentan *network partition*. Kegagalan mengisolasi kegagalan satu komponen dapat memicu keruntuhan berantai (*cascading failure*) di seluruh sistem enterprise.

---

## 5. How (Workflow Detail)

Alur eksekusi request masuk melalui interceptor chain dan resiliency engine:

```
[Inbound TCP Frame]
        │
        ▼
┌────────────────────────────────────────────────────────┐
│  gRPC Server Interceptor Pipeline                      │
│                                                        │
│  1. Recovery Interceptor     (Menangkap runtime panic) │
│  2. Tracing Interceptor      (Ekstraksi traceparent)   │
│  3. Metrics Interceptor      (Pencatatan Prometheus)   │
│  4. Auth/mTLS Interceptor    (Validasi SPIFFE/JWT)     │
│  5. Adaptive Concurrency Limiter (Cegah CPU Starvation)│
└───────────────────────────────────────┬────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │ Business Logic Service Core │
                         └──────────────┬──────────────┘
                                        │
             Outbound Call              ▼
┌────────────────────────────────────────────────────────┐
│  gRPC Outbound Client Pipeline                         │
│                                                        │
│  1. Circuit Breaker Evaluation (State: Open/Closed?)   │
│  2. Interservice Auth Injection (mTLS/Service Token)   │
│  3. Distributed Tracing Injection                      │
│  4. Retry Engine (Full Jitter Backoff)                 │
└───────────────────────────────────────┬────────────────┘
                                        │
                                        ▼
                             [Outbound Wire Request]
```

1. **Inbound Ingestion**: Request masuk didekode oleh runtime gRPC Go. Interceptor pertama memulihkan goroutine jika terjadi panic (`recover()`), mencegah server crash.
2. **Context Enrichment**: Interceptor tracing mengekstraksi span ID dan trace ID dari metadata HTTP/2, lalu menanamkannya ke dalam `context.Context` Go lokal.
3. **Capacity Protection**: Concurrency limiter memeriksa utilisasi goroutine dan saturasi CPU. Jika beban melebihi ambang batas, request langsung ditolak dengan kode status `codes.ResourceExhausted`.
4. **Resilient Outbound Dispatch**: Saat logika bisnis memerlukan panggilan ke layanan lain, pemanggilan dilewatkan melalui client interceptor yang mengevaluasi status *Circuit Breaker*. Jika sirkuit dalam status `Open`, eksekusi digagalkan seketika tanpa melakukan I/O ke jaringan (*fail-fast*).

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem microservices seperti **Jaringan Rumah Sakit Spesialis Terpadu**:

- **Koneksi HTTP/1.1 vs HTTP/2**: HTTP/1.1 seperti satu lorong sempit di mana setiap pasien (request) harus dikawal satu per satu oleh satu dokter; jika seorang pasien tertahan di pintu, semua pasien di belakangnya macet (*Head-of-Line Blocking*). HTTP/2 gRPC seperti ban berjalan pneumatik multi-tabung di dalam lorong yang sama: ratusan rekam medis, sampel darah, dan obat meluncur bersamaan secara paralel melalui satu terowongan fisik tanpa saling menghalangi.
- **Circuit Breaker**: Sakelar sekring listrik di ruang bedah. Jika terjadi lonjakan arus pendek (database down/lambat), sekring putus secara otomatis (*Open*) agar generator utama rumah sakit tidak terbakar habis. Ketika kondisi stabil, teknisi menguji arus kecil (*Half-Open*) sebelum menyalakan daya penuh kembali (*Closed*).

```
State Machine: Circuit Breaker

      +---------+  Consecutive Failures > Threshold   +------+
      |         |------------------------------------>|      |
      | CLOSED  |                                     | OPEN |
      |         |<------------------------------------|      |
      +---------+      Success Rate > Threshold       +------+
           ^                                             |
           |              Sleep Window Expired           |
           |             +------------------+            |
           +-------------|    HALF-OPEN     |<-----------+
                         +------------------+
                         (Test canary traffic)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Distributed Timeout & Context Propagation
Contoh minimal propagation deadline di sisi klien gRPC:

```go
package main

import (
	"context"
	"log"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

func CallRemoteService(ctx context.Context, target string) error {
	// Menetapkan batas atas waktu hidup eksekusi maksimal 200 milidetik
	ctx, cancel := context.WithTimeout(ctx, 200*time.Millisecond)
	defer cancel()

	conn, err := grpc.NewClient(target, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer conn.Close()

	// Simulasi pemanggilan RPC - metadata timeout otomatis di-encode ke wire format
	err = conn.Invoke(ctx, "/order.OrderService/ProcessOrder", nil, nil)
	if err != nil {
		if status.Code(err) == codes.DeadlineExceeded {
			log.Printf("[Peringatan] Upstream RPC timeout melampaui 200ms: %v", err)
			return err
		}
		log.Printf("[Error] Pemanggilan RPC gagal: %v", err)
		return err
	}

	return nil
}
```

### 7.2 Practical Example: Enterprise-Grade Resiliency & Interceptor Stack
Implementasi nyata interceptor server yang memadukan OpenTelemetry Tracing, Prometheus Metric collection, dan Panic Recovery, disertai Circuit Breaker Client wrapper.

#### Kode Pipeline Interceptor Server Enterprise:
```go
package interceptors

import (
	"context"
	"fmt"
	"runtime/debug"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var (
	grpcRequestCounter = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "grpc_server_handled_total",
			Help: "Jumlah total request RPC yang diselesaikan server",
		},
		[]string{"grpc_service", "grpc_method", "grpc_code"},
	)

	grpcLatencyHistogram = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "grpc_server_handling_seconds",
			Help:    "Distribusi latensi pemrosesan RPC server dalam detik",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"grpc_service", "grpc_method"},
	)
)

// EnterpriseServerUnaryInterceptor merangkai Telemetri, Observabilitas, dan Safety
func EnterpriseServerUnaryInterceptor() grpc.UnaryServerInterceptor {
	tracer := otel.GetTracerProvider().Tracer("enterprise-grpc-core")

	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (resp any, err error) {
		start := time.Now()

		// 1. Integrasi OpenTelemetry Span
		ctx, span := tracer.Start(ctx, info.FullMethod,
			trace.WithSpanKind(trace.SpanKindServer),
		)
		defer span.End()

		// 2. Panic Recovery Interceptor untuk menjamin ketersediaan Goroutine
		defer func() {
			if r := recover(); r != nil {
				stackTrace := string(debug.Stack())
				err = status.Errorf(codes.Internal, "Internal Server Panic Terdeteksi: %v", r)
				span.RecordError(fmt.Errorf("panic: %v", r))
				// Cetak trace lengkap ke log terpusat
				println(fmt.Sprintf("CRITICAL PANIC: %v\n%s", r, stackTrace))
				grpcRequestCounter.WithLabelValues(info.FullMethod, "PANIC", codes.Internal.String()).Inc()
			}
		}()

		// 3. Eksekusi handler utama logika bisnis
		resp, err = handler(ctx, req)

		// 4. Pengumpulan Metrik Prometheus
		statusCode := status.Code(err)
		elapsed := time.Since(start).Seconds()

		grpcRequestCounter.WithLabelValues(info.FullMethod, "", statusCode.String()).Inc()
		grpcLatencyHistogram.WithLabelValues(info.FullMethod, "").Observe(elapsed)

		if err != nil {
			span.RecordError(err)
		}

		return resp, err
	}
}
```

#### Client Resiliency: Circuit Breaker Engine
```go
package client

import (
	"context"
	"errors"
	"math/rand"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var (
	ErrCircuitOpen = errors.New("circuit breaker berstatus OPEN: lalu lintas ditolak sementara")
)

type State int

const (
	StateClosed State = iota
	StateHalfOpen
	StateOpen
)

type CircuitBreaker struct {
	mu           sync.Mutex
	state        State
	failureCount int
	threshold    int
	lastStateRun time.Time
	cooldown     time.Duration
}

func NewCircuitBreaker(failureThreshold int, cooldown time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:     StateClosed,
		threshold: failureThreshold,
		cooldown:  cooldown,
	}
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
	cb.mu.Lock()
	now := time.Now()

	if cb.state == StateOpen {
		if now.Sub(cb.lastStateRun) > cb.cooldown {
			cb.state = StateHalfOpen
		} else {
			cb.mu.Unlock()
			return ErrCircuitOpen
		}
	}
	cb.mu.Unlock()

	err := fn()

	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		cb.failureCount++
		if cb.failureCount >= cb.threshold || cb.state == StateHalfOpen {
			cb.state = StateOpen
			cb.lastStateRun = time.Now()
		}
		return err
	}

	// Sukses: Reset circuit breaker ke Closed
	if cb.state == StateHalfOpen || cb.failureCount > 0 {
		cb.state = StateClosed
		cb.failureCount = 0
	}
	return nil
}

// EnterpriseResilientCaller mengeksekusi RPC gRPC dengan Circuit Breaker dan Full Jitter Backoff
func EnterpriseResilientCaller(
	ctx context.Context,
	cb *CircuitBreaker,
	maxRetries int,
	baseDelay time.Duration,
	call func(ctx context.Context) error,
) error {
	for attempt := 0; attempt <= maxRetries; attempt++ {
		err := cb.Execute(func() error {
			return call(ctx)
		})

		if err == nil {
			return nil
		}

		if errors.Is(err, ErrCircuitOpen) {
			return err // Fail-fast seketika, jangan coba lagi
		}

		// Evaluasi apakah error bernilai transien
		st, ok := status.FromError(err)
		if ok && (st.Code() == codes.Unavailable || st.Code() == codes.DeadlineExceeded) {
			if attempt == maxRetries {
				return err
			}

			// Algoritma Full Jitter: Sleep = rand(0, min(cap, base * 2^attempt))
			multiplier := 1 << attempt
			sleepLimit := baseDelay * time.Duration(multiplier)
			sleepDuration := time.Duration(rand.Int63n(int64(sleepLimit)))

			select {
			case <-time.After(sleepDuration):
				continue
			case <-ctx.Done():
				return ctx.Err()
			}
		}

		// Non-transient error (misal: InvalidArgument, Unauthenticated) - hentikan retry
		return err
	}
	return errors.New("batas percobaan retry terlampaui")
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Tier-1 E-Commerce Core Checkout Engine
- **Skala**: 120.000 Checkout Request per Detik (Peak Flash Sale).
- **Arsitektur Awal**: Sinkronus REST JSON.
- **Titik Kritis Kegagalan (Post-Mortem Insiden)**:
  Layanan Pembayaran (*Payment Service*) mengalami peningkatan latensi dari 40ms menjadi 1800ms karena antrean *lock* database. Karena Checkout Service menggunakan blocking HTTP client standar tanpa bounded limits dan deadline propagation yang ketat, terjadi ledakan Goroutine (*Goroutine leak/explosion*) dari 4.000 menjadi lebih dari 650.000 Goroutine dalam 12 detik. Go runtime memicu alokasi memori linear hingga Linux OOM Killer mematikan Checkout Engine secara paksa.

### Solusi Arsitektural Berbasis Go Microservices:
1. **Migrasi IPC ke gRPC + HTTP/2 Multiplexing**: Mengurangi penggunaan resource TCP socket pada kernel Linux secara dramatis melalui penyatuan koneksi.
2. **Implementasi Deadline Enforcing**: Batas timeout mutlak disetel pada angka 350ms untuk keseluruhan alur orkestrasi via context propagation. Setiap dependensi dialokasikan porsi:
   - Inventory Check: 80ms
   - Payment Hold: 200ms
   - Buffer Jaringan: 70ms
3. **Adaptive Concurrency Limiter (CoDel Algorithm)**: Membatasi antrean request masuk sebelum dieksekusi oleh Go runtime. Jika request mengantre lebih dari 20ms di memory buffer server, request langsung ditolak dengan kode `codes.ResourceExhausted`.
4. **Outbox Pattern + Eventual Fallback**: Jika layanan Notifikasi downstream gagal, eksekusi dialihkan ke Local Outbox table via Postgres transactions, melepaskan ketergantungan panggilan sinkronus.

### Hasil Metrik Produksi:
- Penurunan alokasi memori (RAM) sebesar 68% berkat pooling serialisasi Protobuf dan eliminasi alokasi teks JSON.
- Nilai P99 Latency tertekan dari 2.4 detik menjadi 42 milidetik.
- Total ketersediaan (*availability SLA*) meningkat dari 98.7% menjadi 99.995% saat kampanye promo nasional berlangsung.

---

## 9. Trade-offs

```
                  ARSITEKTUR STRATEGY TRADE-OFF MATRIX

     Low Latency / High Throughput          Operability / Low Complexity
             (gRPC + HTTP/2)                     (JSON over REST)
                  ▲                                    ▲
                  │                                    │
                  │◄────────────[ZONE X]──────────────►│
                  │   Tinggi performa, namun butuh     │   Debugging mudah via Curl,
                  │   Protobuf Tooling & Load Balancer │   namun boros CPU, Bandwidth,
                  │   khusus Layer 7 (Envoy/Traefik)   │   dan rentan HoL Blocking
                  ▼                                    ▼
       Library Resiliency (In-Process)       Service Mesh Offload (Sidecar)
                  ▲                                    ▲
                  │                                    │
                  │◄────────────[ZONE Y]──────────────►│
                  │   Zero network hop (sub-ms),       │   Konsisten multi-bahasa,
                  │   namun menambah code bloat &      │   namun latency proxy naik
                  │   membebani GC Go runtime          │   (+1.5ms - 3ms per sidecar)
```

| Aspek | Pilihan A: gRPC Internal Resiliency (Pure Go) | Pilihan B: Envoy / Service Mesh (Sidecar) |
| :--- | :--- | :--- |
| **Latensi P99** | **Ekstrem Rendah**: Panggilan langsung in-process tanpa hop jaringan tambahan. | **Meningkat**: Menambah overhead 2x hop localhost network namespace per RPC (+2-4ms). |
| **Konsumsi Memori**| **Sangat Hemat**: Terdistribusi dalam heap memori Go aplikasi yang sama. | **Boros**: Membutuhkan alokasi 128MB - 512MB RAM ekstra per Pod untuk proses Sidecar Envoy. |
| **Polyglot Consistency** | **Rendah**: Algoritma backoff dan breaker harus diimplementasi ulang pada tiap stack bahasa. | **Tinggi**: Kebijakan traffic, mTLS, dan retry didefinisikan terpusat melalui Control Plane YAML. |
| **Kompleksitas Debugging**| **Tinggi**: Developer harus memelihara interceptor chain, metrics interceptor, dan pool connection Go. | **Rendah untuk Dev**: Logika ketahanan didelegasikan ke level platform infrastructure engineer. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Goroutine Leak Akibat Unbuffered Context Mismanagement
- **Gejala**: Memori server naik secara linear dan bertahap (*sawtooth pattern failure*), GC runtime Go membutuhkan waktu pause lebih lama.
- **Penyebab**: Goroutine melakukan listen pada channel yang tidak pernah dikirimkan atau pemanggilan RPC remote yang tidak menyertakan batas timeout/deadline, sehingga goroutine menggantung selamanya.
- **Solusi Troubleshooting**:
  Gunakan endpoint internal runtime `net/http/pprof` untuk menganalisis Goroutine Dump:
  ```bash
  go tool pprof http://localhost:6060/debug/pprof/goroutine
  ```
  Pastikan pola kode selalu mengintegrasikan `context.WithTimeout` dan membersihkan resources:
  ```go
  // SALAH: Mengabaikan context cancellation upstream
  go func() {
      data := querySlowDatabase() // Goroutine tertahan selamanya jika DB hang
      resultChan <- data
  }()

  // BENAR: Mengikat lifecycle goroutine dengan context channel
  go func() {
      select {
      case <-ctx.Done():
          return // Menghentikan goroutine seketika saat context timeout
      case resultChan <- querySlowDatabase(ctx):
      }
  }()
  ```

### 10.2 Sub-channel Starvation pada gRPC Client Load Balancing
- **Gejala**: Klien gRPC hanya mengirim request ke satu Pod Kubernetes saja, meskipun Service sudah di-scale menjadi 50 Pods (*imbalanced load*).
- **Penyebab**: Arsitektur HTTP/2 memelihara single persistent TCP connection. DNS default Kubernetes ClusterIP hanya me-resolve IP Service tunggal saat dial awal dilakukan, menyebabkan multiplexing stream hanya mengalir ke satu Pod target.
- **Solusi Troubleshooting**:
  Gunakan DNS Resolver internal gRPC dengan skema `dns:///` dan pasang load balancing policy `round_robin`:
  ```go
  // Gunakan skema headless service DNS
  conn, err := grpc.NewClient(
      "dns:///payment-service-headless.production.svc.cluster.local:50051",
      grpc.WithDefaultServiceConfig(`{"loadBalancingConfig": [{"round_robin":{}}]}`),
      grpc.WithTransportCredentials(insecure.NewCredentials()),
  )
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Deterministic Timeouts**: Setiap RPC keluar (*egress*) WAJIB memiliki context deadline eksplisit. Tidak boleh ada pemanggilan tanpa timeout.
- [ ] **Jittered Backoff**: Jangan pernah melakukan retry murni tanpa jitter. Terapkan variasi acak (*Full Jitter*) untuk mencegah efek *thundering herd*.
- [ ] **Circuit Breaker Boundaries**: Bedakan error transien (`Unavailable`, `ResourceExhausted`) dari error deterministik (`InvalidArgument`, `NotFound`). Hanya error transien yang boleh memicu trip pada circuit breaker.
- [ ] **Stream/Connection Keepalive**: Konfigurasikan gRPC KeepAlive Enforcement Policy untuk mendeteksi TCP connection yang mati (*half-open TCP*) oleh firewall/NAT:
  ```go
  var keepAliveParams = keepalive.ServerParameters{
      MaxConnectionIdle:     15 * time.Minute,
      MaxConnectionAge:      30 * time.Minute,
      MaxConnectionAgeGrace: 5 * time.Minute,
      Time:                  5 * time.Minute,
      Timeout:               1 * time.Second,
  }
  ```
- [ ] **Safe Buffer Allocations**: Hindari alokasi slice atau objek berulang pada request handler gRPC berkepadatan tinggi. Gunakan `sync.Pool` untuk pooling objek serialisasi/deserialisasi.
- [ ] **Graceful Shutdown**: Implementasikan penangkapan sinyal OS (`SIGTERM`, `SIGINT`) untuk menyelesaikan RPC yang sedang berjalan sebelum instance pod dihentikan:
  ```go
  sigCh := make(chan os.Signal, 1)
  signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
  <-sigCh
  server.GracefulStop() // Menolak request baru, menyelesaikan in-flight requests
  ```

---

## 12. Hands-on Practice

Buat struktur direktori praktikum berikut di lingkungan kerja Anda:
`hands-on/m02/`

### File: `hands-on/m02/resilient_server.go`
Kompilasi dan jalankan server gRPC berketahanan tinggi dengan konfigurasi interceptor:

```go
package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/status"
)

// Pipeline interceptor untuk server
func LoggingInterceptor(
	ctx context.Context,
	req any,
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (any, error) {
	start := time.Now()
	resp, err := handler(ctx, req)
	log.Printf("[RPC-CALL] Method: %s | Durasi: %v | Error: %v", info.FullMethod, time.Since(start), err)
	return resp, err
}

func main() {
	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("Gagal membuka port listening: %v", err)
	}

	server := grpc.NewServer(
		grpc.UnaryInterceptor(LoggingInterceptor),
	)

	// Pasang gRPC Health Checking Protocol untuk K8s Liveness/Readiness probes
	healthServer := health.NewServer()
	healthpb.RegisterHealthServer(server, healthServer)
	healthServer.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)

	go func() {
		log.Println("[INFO] Server gRPC Enterprise berjalan pada port :50051")
		if err := server.Serve(lis); err != nil && err != grpc.ErrServerStopped {
			log.Fatalf("Server berhenti tak normal: %v", err)
		}
	}()

	// Graceful Shutdown Handler
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("[INFO] Menerima sinyal terminasi, mematikan server secara graceful...")
	healthServer.SetServingStatus("", healthpb.HealthCheckResponse_NOT_SERVING)
	
	stopped := make(chan struct{})
	go func() {
		server.GracefulStop()
		close(stopped)
	}()

	select {
	case <-stopped:
		log.Println("[INFO] Server berhasil dimatikan secara normal.")
	case <-time.After(10 * time.Second):
		log.Println("[WARN] Waktu shutdown graceful habis, mematikan paksa instance.")
		server.Stop()
	}
}
```

### Instruksi Pengujian:
1. Inisialisasi modul Go:
   ```bash
   cd hands-on/m02
   go mod init enterprise-microservices
   go get google.golang.org/grpc@v1.62.0
   go get google.golang.org/grpc/health/grpc_health_v1
   ```
2. Jalankan aplikasi:
   ```bash
   go run resilient_server.go
   ```
3. Uji graceful shutdown: Tekan `Ctrl + C` pada terminal dan perhatikan bagaimana server mengalihkan status health check ke `NOT_SERVING` sebelum menyelesaikan terminasi proses secara aman.

---

## 13. Exercise

### Level Easy
Modifikasi file `hands-on/m02/resilient_server.go` untuk menambahkan interceptor validasi: Jika request tidak menyertakan metadata HTTP/2 key `x-tenant-id`, interceptor harus membatalkan RPC dan mengembalikan error status `codes.InvalidArgument` secara langsung tanpa memanggil handler inti.

### Level Medium
Implementasikan interceptor client yang menghitung latensi eksekusi pemanggilan downstream. Jika latensi panggilan downstream melebihi threshold 100ms, buat catatan peringatan pada log level `WARN` lengkap dengan trace ID dan nama method RPC terkait.

### Level Hard
Buat implementasi komponen *In-Memory Token Bucket Rate Limiter* dalam bentuk gRPC Server Unary Interceptor murni menggunakan channel Go dan package `time`.
- Batasan: Maksimal 500 RPS dengan burst bucket berkapasitas 50 token.
- Apabila token habis, kembalikan status error `codes.ResourceExhausted` dengan menyertakan trailing metadata `retry-after: 1s` ke frame gRPC response. Pastikan interceptor aman terhadap akses konkuren dari ribuan Goroutine secara simultan (*thread-safe*).

---

## 14. Challenge

### Skenario Kasus: The Cascading Death Spiral Challenge
Sebuah cluster microservices yang terdiri dari 3 service (Layanan A -> Layanan B -> Layanan C) mengalami masalah kritis saat beban transaksi memuncak. Layanan C mulai mengalami latensi tinggi karena saturasi thread pool pada I/O disk. Klien pada Layanan A menginisiasi retry setiap 50 milidetik saat timeout terjadi. Hal ini menggandakan volume traffic masuk ke Layanan B dan C hingga 600%, membuat seluruh ekosistem lumpuh total (*cascading collapse*).

### Tugas Arsitektural:
Rancang dan bangun implementasi arsitektur pertahanan lengkap di Layanan B menggunakan Go murni yang memuat:
1. **Dynamic Deadlines Propagation Filter**: Layanan B harus menghitung sisa waktu konteks dari Layanan A. Jika sisa deadline kurang dari estimasi p95 Layanan C (misal: sisa waktu tersisa hanya 10ms, sedangkan p95 Layanan C adalah 40ms), Layanan B harus **menolak mengeksekusi panggilan ke Layanan C secara dini** (*Fail-Early Optimization*) dengan status `codes.DeadlineExceeded`.
2. **Adaptive Concurrency Limit (Vegas / Little's Law)**: Membatasi pemanggilan konkuren ke Layanan C secara dinamis berdasarkan kalkulasi *Queue Latency Gradient*, bukan nilai hardcoded.
3. **Scatter-Gather Parallel Call**: Layanan B harus memanggil 2 replika independen dari Layanan C secara paralel (hedged requests) jika request pertama tidak merespons dalam p90 waktu standar, mengambil respons tercepat, dan membatalkan stream yang lambat seketika via `context.CancelFunc`.

*Kriteria Keberhasilan*: Tidak boleh ada goroutine leak, seluruh koneksi wajib menggunakan pooled multiplexing gRPC, dan kode harus mampu menahan simulasi kegagalan injeksi chaos latency tanpa penurunan ketersediaan pada Layanan B.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Mengapa gRPC lebih efisien dalam penggunaan resource CPU dan memori dibandingkan protokol REST berbasis JSON?
2. Bagaimana mekanisme HTTP/2 multiplexing mengatasi masalah *Head-of-Line (HoL) Blocking* yang umum terjadi pada HTTP/1.1?
3. Apa implikasi fatal jika kita tidak memanggil fungsi `cancel()` yang dihasilkan oleh `context.WithTimeout()` pada pemanggilan client gRPC?
4. Apa fungsi utama dari header biner `grpc-timeout` yang dikirimkan melalui HTTP/2 frame?
5. Mengapa arsitektur microservices modern memerlukan graceful shutdown terstruktur saat menerima sinyal `SIGTERM` dari Kubernetes kubelet?

### 15.2 Pertanyaan Intermediate
1. Jelaskan siklus transisi status (*State Machine*) dari Circuit Breaker: kapan sirkuit berada pada kondisi `Closed`, `Open`, dan `Half-Open`?
2. Apa bahaya menggunakan algoritma retry standar (*fixed interval retry*) pada lingkungan sistem terdistribusi skala tinggi, dan mengapa *Full Jitter* wajib diterapkan?
3. Bagaimana cara kerja metadata gRPC dalam menyalurkan informasi observabilitas (seperti traceparent OpenTelemetry) lintas batasan mesin jaringan?
4. Kapan kita sebaiknya mengembalikan kode error `codes.ResourceExhausted` dibandingkan `codes.Unavailable`? Jelaskan perbedaannya dari perspektif client.
5. Bagaimana peran algoritma kompresi HPACK pada HTTP/2 dalam mereduksi overhead jaringan saat pengiriman token otentikasi JWT yang berukuran besar?

### 15.3 Skenario Kasus Produksi
1. **Skenario 1**: Tim SRE melaporkan bahwa setelah melakukan deployment versi baru, alokasi memori layanan Order Service melonjak drastis hingga menyentuh batas OOMKilled di Kubernetes, namun CPU utilization terpantau sangat rendah. Setelah diteliti via runtime profiler, terdapat 400.000 goroutine dalam status `chan receive`. Identifikasi akar masalah arsitektural ini dan bagaimana pencegahannya pada tingkat kode!
2. **Skenario 2**: Layanan Checkout memanggil 3 microservice upstream secara berurutan: Keranjang Belanja, Diskon, dan Saldo Poin. Jika SLA total waktu checkout harus di bawah 500ms, rancang strategi propagasi konteks dan eksekusi konkurensi di Go agar kegagalan salah satu layanan downstream tidak menghabiskan seluruh sisa waktu yang dialokasikan!
3. **Skenario 3**: Sebuah upstream service dependensi sering mengalami degradasi sesaat (*flapping failure*) setiap 10 menit sekali selama 30 detik. Klien yang memanggil terus menerus mengalami timeout dan menumpuk antrean request. Rancang konfigurasi dan pola resiliency (kombinasi Circuit Breaker, Timeout, dan Bulkhead) untuk mengisolasi dampak degradasi ini agar tidak merambat ke layer frontend API Gateway!

---

## 16. Summary

- **High-Performance Transport**: gRPC mentransformasi komunikasi antar-microservices melalui pemanfaatan HTTP/2 frames, multiplexing stream tunggal, dan schema biner Protocol Buffers v3, menghasilkan latensi rendah dan konsumsi bandwidth minimal.
- **Context is King**: Context propagation (`context.Context`) adalah fondasi utama arsitektur terdistribusi di Go. Deadline dan cancellation metadata wajib dialirkan menembus batas jaringan untuk memangkas pemborosan komputasi (*wasted execution*) seketika saat timeout tercapai.
- **Resilience by Design**: Membangun microservices enterprise menuntut asumsi bahwa jaringan selalu tidak dapat diandalkan (*unreliable network*). Implementasi *Circuit Breaker*, *Adaptive Rate Limiting*, dan *Exponential Backoff with Full Jitter* adalah benteng pertahanan wajib untuk mencegah *Cascading Failures* dan menjaga ketersediaan sistem secara keseluruhan.
- **Enterprise Observability**: Interceptor pipeline bertindak sebagai tulang punggung arsitektur microservice Go yang modular, memungkinkan integrasi terpusat untuk distributed tracing (OpenTelemetry), metrik operasional (Prometheus), audit logging, dan panic recovery tanpa mencemari kesucian logika domain bisnis.