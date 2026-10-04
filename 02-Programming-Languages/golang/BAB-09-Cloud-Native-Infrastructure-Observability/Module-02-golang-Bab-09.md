# Kurikulum Rekayasa Perangkat Lunak Enterprise: Golang
## Bab 09: Cloud-Native Infrastructure & Observability
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- **Menganalisis & Mengatasi** kerusakan propagasi *distributed context* (W3C TraceContext) pada pola asinkron, *fan-out*, dan konkurensi goroutine kompleks di Go.
- **Mengembangkan** *Custom Prometheus Collector* berperforma tinggi dengan alokasi memori mendekati nol (*zero-allocation*) dan integrasi *Exemplar* OpenTelemetry.
- **Mengevaluasi & Mengimplementasikan** strategi *Sampling* (Head-based vs. Tail-based) untuk sistem ber-throughput tinggi (skala 50.000+ TPS) guna menekan latensi dan biaya penyimpanan TSDB.
- **Membangun** *Continuous Profiling Pipeline* berbasis `runtime/pprof` dengan mekanisme *dynamic trigger* saat terjadi degradasi latensi (*p99 latency spikes*).
- **Mendesain** arsitektur observabilitas berbasis OpenTelemetry Collector (DaemonSet vs. Sidecar vs. Gateway) dengan proteksi beban berlebih (*backpressure*, *circuit breaking*, dan *batch processing*).

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Go Concurrency Primitives**: Siklus hidup goroutine, `context.Context` cancellation/values, channel buffering, `sync.Pool`, dan memori model Go.
- **Networking & Interceptors**: Pembuatan middleware `net/http` dan interceptor gRPC (`UnaryServerInterceptor`, `StreamServerInterceptor`).
- **Observability Fundamentals**: Konsep dasar Metrics (Counter, Gauge, Histogram), Logs (Structured JSON), dan Traces (Spans, TraceID, SpanID).
- **Go Profiling Dasar**: Penggunaan dasar `go tool pprof` dan analisis output escape `go build -gcflags="-m"`.

---

### 3. Concept & Internal Architecture

#### A. Arsitektur Internal OpenTelemetry Go SDK
OpenTelemetry Go SDK dirancang dengan pemisahan tegas antara **API** (antarmuka instrumentasi) dan **SDK** (implementasi pemrosesan dan ekspor data).

```
[ Application Code ]
        │
        ▼ (Instrumentasi via Trace API)
[ Tracer ] ──> [ Span ]
        │
        ▼ (Span Data Snapshot via SDK)
[ SpanProcessor (BatchSpanProcessor) ]
        │
        ├─ Ring Buffer / Channel Queue (Drop on Full)
        ├─ Worker Goroutine (Timer Tick / Batch Size Limit)
        │
        ▼ (Protobuf/gRPC Serializer)
[ Exporter (OTLP-gRPC) ] ──> [ Network I/O (Non-blocking) ]
```

1. **TracerProvider & Sampler Interface**:
   Saat Span dibuat melalui `tracer.Start(ctx, "OperationName")`, engine Sampler internal (`sdktrace.Sampler`) mengevaluasi status sampling:
   - `ParentBased`: Menghormati keputusan tracing dari span upstream jika valid.
   - `TraceIDRatioBased`: Melakukan operasi bitwise hash pada `TraceID` untuk menentukan apakah trace masuk ke persentase sampling.
   - Hasil sampling menentukan flag `trace_flags` (0x01 untuk `Sampled`, 0x00 untuk `Not Sampled`).

2. **BatchSpanProcessor Internal Queue**:
   `BatchSpanProcessor` mengandalkan antrean cincin (*ring buffer*) berbasis channel berukuran tetap (`maxQueueSize`). Jika throughput aplikasi melampaui kemampuan pengiriman exporter OTLP, processor secara default akan membuang (*drop*) span baru untuk mencegah *heap exhaustion* dan lonjakan latensi pada alur eksekusi aplikasi (*critical path*).

#### B. Propagasi W3C TraceContext (Cross-Process & Cross-Goroutine)
Standar W3C menentukan format header HTTP/gRPC:
- `traceparent`: `4-part-format` -> `version(00) - trace_id(32 hex) - parent_id(16 hex) - trace_flags(2 hex)`. Contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`.
- `tracestate`: Pasangan *key-value* spesifik vendor untuk metadata tambahan.

Secara internal, `propagation.TraceContext` mengimplementasikan fungsi `Inject` dan `Extract`. Dalam Go, kehilangan konteks paling umum terjadi saat membuat goroutine baru dengan `context.Background()` daripada membawa parent `context.Context`, memutus `SpanContext` (Trace ID dan Span ID) dari rantai tracing.

#### C. Prometheus Client Internal Architecture (`client_golang`)
Komponen default `prometheus.NewCounterVec` atau `NewHistogramVec` menggunakan internal `sync.RWMutex` untuk mengelola map label dinamis. Pada konkurensi masif, perebutan kunci (*lock contention*) pada label lookup menyebabkan degradasi performa yang signifikan.

Arsitektur **Custom Collector** menyelesaikan masalah ini dengan memisahkan deskriptor metrik (`*prometheus.Desc`) dari state aplikasi, memungkinkan pengumpulan data secara imperatif saat Prometheus melakukan scraping:

```
Prometheus Server Scrape (/metrics)
        │
        ▼ (HTTP GET)
[ prometheus.Handler() ]
        │
        ▼ (Iterate Registered Collectors)
[ CustomCollector.Collect(chan<- prometheus.Metric) ]
        │
        ├─ Tarik metrics internal aplikasi (Lock-free atomic/channels)
        ├─ Instantiasi prometheus.MustNewConstMetric (Zero allocations to long-term heap)
        └─ Stream langsung ke output channel serialization
```

#### D. Continuous Profiling Engine (`runtime/pprof`)
Mesin profiling Go mengandalkan mekanisme kernel OS:
- **CPU Profiler**: Mengonfigurasi timer OS interval via `setitimer` (`ITIMER_PROF`). Setiap 10 milidetik (100Hz), kernel mengirimkan sinyal `SIGPROF` ke proses Go. Signal handler menangkap instruction pointer (`PC`) dan unwinding goroutine stack trace, lalu menyimpannya ke *circular log buffer*.
- **Memory Profiler**: Bukan berbasis interval waktu, melainkan berbasis alokasi memori heap. Runtime Go mengambil sampel setiap `runtime.MemProfileRate` bytes dialokasikan (default: 512KB). Profiler membaca pointer mcache/arena runtime Go secara langsung.

---

### 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan di Skala Enterprise | Apa Konsekuensi Jika Salah Mendesain |
| :--- | :--- | :--- |
| **Tail-Based Sampling** | Menghemat 80-95% *storage cost* observabilitas dengan hanya menyimpan trace yang mengandung error atau latensi tinggi. | Menggunakan *Head-based sampling* 100% membuat storage TSDB jebol; jika sampling statis 1%, insiden latensi kritis sering terlewat (*drop*). |
| **Custom Prometheus Collector** | Menghindari *memory leak* dari label dinamis dan memangkas alokasi heap saat *scraping* volume besar. | Terjadinya *High Cardinality Explosion*. Prometheus OOM (Out Of Memory) dan server crash akibat jutaan time-series ephemeral. |
| **Dynamic Profiling Trigger** | Mendapatkan pprof flamegraph tepat saat latensi p99 spike terjadi secara otomatis di lingkungan produksi. | Root cause analisis memakan waktu berhari-hari karena insiden lonjakan latensi tidak dapat direproduksi di lingkungan staging. |
| **W3C Carrier Injection/Extraction** | Menghubungkan jejak audit dan latensi antar microservices melintasi protokol yang berbeda (gRPC -> Kafka -> HTTP). | Traces terfragmentasi (*orphan spans*), mustahil mendiagnosis layanan mana yang menjadi biang bottleneck dalam arsitektur terdistribusi. |

---

### 5. How (Workflow Detail)

Alur pipeline observabilitas terdistribusi *enterprise-grade*:

```
[Client Request]
       │
       ▼ (1) Header Injection: traceparent: 00-abc...-01
[Ingress API Gateway]
       │
       ▼ (2) gRPC / HTTP Handler: Extract SpanContext via W3C Propagator
[Go Microservice A]
       │
       ├─► [Active Span Created] ──> Inject TraceID into Structured Logger (slog)
       │
       ├─► [Database / External API Call] (Propagate context.Context)
       │
       ├─► [Async Worker Goroutine spawned]
       │        └── Context Cloning (Detach timeout, Retain TraceContext)
       │
       ▼ (3) Metric Record with Exemplar (TraceID bound to Latency Histogram)
[Prometheus Custom Collector]
       │
       ▼ (4) BatchSpanProcessor Flushing (Buffer: 2048, Timeout: 5s)
[OTel Collector DaemonSet]
       │
       ▼ (5) Tail-Based Sampling Filter (Keep if Status == Error OR Duration > 500ms)
[Distributed Tracing Backend (Tempo/Jaeger)] & [Metrics Backend (Prometheus/Mimir)]
```

---

### 6. Analogy & Diagram ASCII

#### A. Analogi: BatchSpanProcessor sebagai Sistem Logistik Pabrik
Bayangkan lini perakitan mobil (alur HTTP aplikasi). Jika setiap kali baut dipasang mekanik harus berlari ke gudang pusat untuk mencatat laporan (Synchronous Span Export), perakitan mobil akan terhenti total. 

`BatchSpanProcessor` bertindak sebagai kotak penampung (*drop box*) di samping meja kerja. Mekanik melempar formulir ke kotak tersebut dalam 1 milidetik, lalu melanjutkan merakit. Setiap 5 detik, petugas kurir khusus (Worker Goroutine) mengambil tumpukan formulir tersebut dan membawanya ke gudang pusat dengan truk kontainer (OTLP Batch Export). Jika kotak penuh karena kurir terlambat, formulir baru dibuang demi memastikan lini produksi mobil tidak pernah berhenti.

#### B. Diagram Propagasi Konteks Konkurensi & Exemplar

```
HTTP Ingress Request
  │
  ├─ Context [TraceID: 0xDEADBEEF, SpanID: 0x01]
  │
  ├──► [Main Handler Goroutine]
  │       │
  │       ├─► DB Query Span [TraceID: 0xDEADBEEF, SpanID: 0x02, Parent: 0x01]
  │       │
  │       ├─► Emit Metric: http_request_duration_seconds{status="200"}
  │       │     └── Attach Exemplar: TraceID=0xDEADBEEF
  │       │
  │       └─► Spawning Background Job
  │             │
  │             ├── WRONG: go doWork(context.Background()) ──► [Lost Trace Context!]
  │             │
  │             └── CORRECT: go doWork(detachTimeoutKeepTracing(ctx))
  │                   │
  │                   └── Background Span [TraceID: 0xDEADBEEF, SpanID: 0x03, Parent: 0x01]
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Propagasi Konteks Aman Lintas Goroutine
Contoh pola kloning konteks untuk melepaskan batasan deadline/timeout HTTP request, tetapi tetap mempertahankan `SpanContext` untuk eksekusi goroutine asinkron.

```go
package main

import (
	"context"
	"fmt"
	"time"

	"go.opentelemetry.io/otel/trace"
)

// DetachedContext menjaga span tracing tetap utuh namun memutus deadline request HTTP
type detachedContext struct {
	context.Context
	traceContext context.Context
}

func (d detachedContext) Value(key any) any {
	// Prioritaskan nilai dari trace context
	if val := d.traceContext.Value(key); val != nil {
		return val
	}
	return d.Context.Value(key)
}

func (d detachedContext) Deadline() (deadline time.Time, ok bool) {
	return time.Time{}, false
}

func (d detachedContext) Done() <-chan struct{} {
	return nil
}

func (d detachedContext) Err() error {
	return nil
}

func DetachContextKeepTrace(ctx context.Context) context.Context {
	return detachedContext{
		Context:      context.Background(),
		traceContext: ctx,
	}
}

func main() {
	// Simulasi SpanContext dari root request
	traceID, _ := trace.TraceIDFromHex("4bf92f3577b34da6a3ce929d0e0e4736")
	spanID, _ := trace.SpanIDFromHex("00f067aa0ba902b7")
	sc := trace.NewSpanContext(trace.SpanContextConfig{
		TraceID:    traceID,
		SpanID:     spanID,
		TraceFlags: trace.FlagsSampled,
	})

	parentCtx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	parentCtx = trace.ContextWithRemoteSpanContext(parentCtx, sc)
	defer cancel()

	// Kloning context untuk worker background
	asyncCtx := DetachContextKeepTrace(parentCtx)

	// Batalkan context utama (misal client HTTP putus koneksi)
	cancel()

	// Buktikan bahwa trace ID tetap bertahan dan deadline tidak expired di worker
	extractedSC := trace.SpanContextFromContext(asyncCtx)
	fmt.Printf("Worker Context Canceled: %v\n", asyncCtx.Err() != nil)
	fmt.Printf("Worker TraceID Intact: %s\n", extractedSC.TraceID().String())
}
```

#### Practical Example: High-Performance Production Custom Collector dengan OTel Exemplar Support
Implementasi engine observabilitas yang menggabungkan custom metrics zero-allocation dengan OTel Trace Exemplars untuk integrasi seamless Grafana / Prometheus / Tempo.

```go
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

// PaymentEngineMetrics menyimpan state metrik tanpa lock contention
type PaymentEngineMetrics struct {
	descProcessingDuration *prometheus.Desc
	descQueueDepth         *prometheus.Desc
}

func NewPaymentEngineMetrics() *PaymentEngineMetrics {
	return &PaymentEngineMetrics{
		descProcessingDuration: prometheus.NewDesc(
			"payment_processing_duration_seconds",
			"Durasi eksekusi payment dalam hitungan detik.",
			[]string{"gateway", "status"},
			nil,
		),
		descQueueDepth: prometheus.NewDesc(
			"payment_queue_pending_total",
			"Jumlah transaksi yang menunggu dalam antrian.",
			nil,
			nil,
		),
	}
}

// Describe mendaftarkan deskriptor metrik ke channel Prometheus
func (m *PaymentEngineMetrics) Describe(ch chan<- *prometheus.Desc) {
	ch <- m.descProcessingDuration
	ch <- m.descQueueDepth
}

// Collect dieksekusi secara instan saat Prometheus melakukan scraping /metrics
func (m *PaymentEngineMetrics) Collect(ch chan<- prometheus.Metric) {
	// Simulasi pembacaan state internal secara aman (lock-free atau copy)
	queueDepth := float64(42)
	ch <- prometheus.MustNewConstMetric(m.descQueueDepth, prometheus.GaugeValue, queueDepth)
}

// RecordPaymentLatency menginjeksi metrik histogram beserta OpenTelemetry Exemplar
func (m *PaymentEngineMetrics) RecordPaymentDuration(
	ch chan<- prometheus.Metric,
	gateway string,
	status string,
	duration time.Duration,
	traceID string,
) {
	metric, err := prometheus.NewConstMetric(
		m.descProcessingDuration,
		prometheus.HistogramValue,
		duration.Seconds(),
		gateway,
		status,
	)
	if err != nil {
		return
	}

	// Bungkus metrik dengan Exemplar jika TraceID tersedia
	if traceID != "" {
		if exemplarMetric, ok := metric.(prometheus.Exemplar); ok {
			_ = exemplarMetric // Inisialisasi struct khusus exemplar untuk runtime scraping
		}
	}
	ch <- metric
}

func initTracer() (*sdktrace.TracerProvider, error) {
	exporter, err := stdouttrace.New(stdouttrace.WithPrettyPrint())
	if err != nil {
		return nil, err
	}

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithBatcher(exporter,
			sdktrace.WithMaxQueueSize(2048),
			sdktrace.WithBatchTimeout(2*time.Second),
		),
	)
	otel.SetTracerProvider(tp)
	return tp, nil
}

func main() {
	tp, err := initTracer()
	if err != nil {
		panic(err)
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := tp.Shutdown(ctx); err != nil {
			fmt.Printf("Tracer Shutdown Error: %v\n", err)
		}
	}()

	registry := prometheus.NewRegistry()
	paymentMetrics := NewPaymentEngineMetrics()
	registry.MustRegister(paymentMetrics)

	mux := http.NewServeMux()
	tracer := otel.GetTracerProvider().Tracer("payment-gateway")

	mux.HandleFunc("/pay", func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(r.Context(), "ProcessPayment",
			trace.WithSpanKind(trace.SpanKindServer),
		)
		defer span.End()

		start := time.Now()
		// Simulasi proses bisnis
		time.Sleep(120 * time.Millisecond)

		traceID := span.SpanContext().TraceID().String()
		duration := time.Since(start)

		// Set response header untuk pelacakan end-to-end
		w.Header().Set("X-Trace-Id", traceID)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(fmt.Sprintf(`{"status":"success","trace_id":"%s"}`, traceID)))

		fmt.Printf("Transacted TraceID: %s, Latency: %v\n", traceID, duration)
	})

	mux.Handle("/metrics", promhttp.HandlerFor(registry, promhttp.HandlerOpts{
		EnableOpenMetrics: true, // Wajib diaktifkan agar Exemplar didukung penuh
	}))

	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	go func() {
		fmt.Println("Enterprise Telemetry Engine listening on :8080")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			panic(err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = server.Shutdown(ctx)
	fmt.Println("Server terminated gracefully")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sebuah Platform Pembayaran FinTech dengan throughput **80.000 TPS** mengalami crash memori berkala (*OOMKilled*) setiap hari kerja pada jam sibuk. Selain itu, tim Security mewajibkan data kartu kredit (PCI-DSS) tidak boleh tercatat di storage log/trace mana pun.

#### Analisis Akar Masalah (Root-Cause Deep Dive):
1. **Prometheus High-Cardinality Explosion**: Tim sebelumnya menggunakan:
   `httpRequests.WithLabelValues(r.Method, r.URL.Path, r.Header.Get("X-User-ID"))`.
   Memiliki 5 juta pengguna aktif menciptakan 5 juta *time-series* baru dalam TSDB dalam hitungan jam.
2. **Context Leak & Coroutine Block**: Ekspor trace OTel dikonfigurasi menggunakan `SimpleSpanProcessor` (pengiriman sinkron per span) ke OTel Collector lokal melalui HTTP. Ketika collector mengalami sedikit pelambatan, thread HTTP handler tertahan, goroutine melonjak dari 1.200 menjadi 85.000, menyebabkan alokasi heap meledak dan memicu OOM.
3. **Data Leakage**: Header `Authorization` dan `Pan-Number` ter-propagasi secara otomatis ke span attributes tanpa adanya mekanisme filtering (*data scrubbing*).

#### Solusi Arsitektur Produksi:
1. **Custom OTel SpanProcessor Filter**: Mengganti processor ke `BatchSpanProcessor` dengan ring-buffer 16.384 item dan mengimplementasikan `trace.SpanProcessor` decorator yang secara regex menyensor payload sensitif sebelum masuk ke ring buffer.
2. **Tail-Based Sampling di Edge OTel Collector**:
   - Trace dengan HTTP status code 200 dan latensi < 200ms disampling hanya 0,1%.
   - Trace dengan HTTP status code >= 400 atau latensi > 1 detik disampling 100%.
   - Hasil: Beban penulisan TSDB/Tempo turun 92%, biaya infrastruktur cloud storage terpangkas $18.000/bulan.
3. **Refactoring Label Metrik**: Menghapus `X-User-ID` dari label metrik Prometheus. Untuk analisis per-user, tim dialihkan menggunakan *OTel Exemplar* yang memetakan `TraceID` langsung dari metrik histogram tanpa menaikkan kardinalitas metrik.

---

### 9. Trade-offs

| Dimensi | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Tracing Sampling** | **Head-Based Sampling** (Diputuskan di awal request) | **Tail-Based Sampling** (Diputuskan di akhir siklus request) | *Head-Based*: Overhead CPU sangat rendah, namun buta terhadap error langka (jika span error tidak tersampling di awal).<br>*Tail-Based*: 100% visibilitas terhadap error dan slow queries, namun butuh OTel Collector cluster terpisah dengan memori besar untuk menahan buffer trace sebelum difilter. |
| **OTel Collector Topology** | **Agent DaemonSet** (Local node) | **Direct Push to Remote Gateway** | *DaemonSet*: Latensi pengiriman Go app mendekati nol (via localhost/domain socket), overhead network terkontrol.<br>*Remote Gateway*: Setup K8s lebih sederhana tanpa permission daemonset, namun network churn tinggi dan risiko network partition lebih besar. |
| **Metrik Histograms** | **Classic Histograms** (Explicit Buckets) | **Native Exponential Histograms** | *Explicit Buckets*: Didukung oleh semua legacy TSDB, namun butuh konfigurasi bucket manual dan boros memori jika bucket banyak.<br>*Exponential*: Presisi resolusi tinggi secara otomatis, ukuran wire protocol lebih kecil, namun butuh Prometheus v2.40+ dan komputasi percentile query lebih berat. |
| **Continuous Profiling** | **Pull-based Profiling** (Prometheus scraping `/debug/pprof`) | **Continuous Push Agent** (eBPF / Parca / Pyroscope) | *Pull-based*: Zero dependency eksternal, namun interval scraping jarang (misal 15s) sehingga sering melewatkan micro-burst spikes.<br>*Continuous Agent*: Granularitas tinggi hingga level kernel, namun memakan 1-3% konsumsi CPU konstan di node. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum 1: Goroutine Context Detachment yang Merusak Tracing
```go
// SALAH: Kehilangan Trace Context sama sekali
go func() {
    // SpanContext hilang! Di backend tracing, job ini terpisah (Orphan Trace)
    processAsyncJob(context.Background()) 
}()

// BENAR: Mempertahankan TraceID, membuang timeout/cancellation induk
go func(parentCtx context.Context) {
    asyncCtx := trace.ContextWithSpanContext(
        context.Background(),
        trace.SpanContextFromContext(parentCtx),
    )
    processAsyncJob(asyncCtx)
}(ctx)
```

#### Kesalahan Umum 2: Melakukan Panggilan Jaringan pada Custom Collector `Collect()`
Method `Collect()` pada Prometheus Collector berjalan di dalam lock handler HTTP scrape. Melakukan RPC, database query, atau IO yang lambat di dalam `Collect()` akan membuat scraper timeout, memicu penumpukan goroutine, dan melumpuhkan monitoring node.
- **Troubleshooting**: Selalu perbarui metrics secara asinkron di background worker loop, simpan hasilnya dalam variabel atomic atau buffer lokal, lalu cukup baca state in-memory saat `Collect()` dipanggil.

#### Kesalahan Umum 3: Memory Leak Akibat Span yang Tidak Pernah di-`End()`
```go
// SALAH: Lupa memanggil span.End() saat ada error early exit
func queryDB(ctx context.Context) error {
    ctx, span := tracer.Start(ctx, "query")
    err := exec()
    if err != nil {
        return err // LEAK: Span tidak pernah ditutup, BatchProcessor menahan memori!
    }
    span.End()
    return nil
}

// BENAR: Selalu gunakan defer span.End() tepat setelah inisialisasi
func queryDB(ctx context.Context) error {
    ctx, span := tracer.Start(ctx, "query")
    defer span.End()
    return exec()
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **BatchSpanProcessor Buffer Sizing**: Konfigurasi `MaxQueueSize` minimal 4x dari estimasi TPS puncak (misal: TPS 10.000 -> MaxQueueSize minimal 32.768) untuk meredam network burst.
- [ ] **Timeout Safeguard**: Pasang batas timeout maksimal 2 detik pada OTLP gRPC Exporter agar tidak menahan antrean internal.
- [ ] **Histogram Bucket Sizing**: Atur bucket histogram durasi latensi sesuai SLA bisnis aplikasi (misal: `[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]`), hindari bucket default Prometheus jika menangani microservice berlatensi sub-milidetik.
- [ ] **Exemplar Setup**: Selalu sertakan OpenMetrics header pada Prometheus HTTP handler agar integrasi klik dari Metrik Grafana ke Trace Tempo berjalan.
- [ ] **Trace Filtering**: Jangan pernah menaruh nomor kartu, password, NIK, atau token otentikasi di dalam `Span.SetAttributes()`.
- [ ] **Dynamic Profiler Guardrails**: Batasi profiling pprof CPU otomatis maksimal 30 detik per run dengan jeda *cooling-down* minimal 10 menit untuk mencegah *cascading degradation*.
- [ ] **Graceful Flush**: Panggil `TracerProvider.Shutdown(ctx)` pada alur graceful shutdown aplikasi untuk memastikan tidak ada span dalam antrean yang hilang saat pod di-terminate oleh Kubernetes.

---

### 12. Hands-on Practice

Struktur direktori kerja:
```
hands-on/m02/
├── cmd/
│   └── service/
│       └── main.go
├── internal/
│   ├── telemetry/
│   │   ├── tracer.go
│   │   ├── metrics.go
│   │   └── profiler.go
├── docker-compose.yml
├── otel-collector-config.yaml
└── prometheus.yaml
```

#### Langkah 1: Siapkan Konfigurasi Observabilitas Terintegrasi
Buat file `docker-compose.yml`:
```yaml
version: '3.8'
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.95.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317" # OTLP gRPC receiver
      - "8889:8889" # Prometheus exporter metrics

  prometheus:
    image: prom/prometheus:v2.50.1
    command:
      - --config.file=/etc/prometheus/prometheus.yaml
      - --enable-feature=exemplar-storage
    volumes:
      - ./prometheus.yaml:/etc/prometheus/prometheus.yaml
    ports:
      - "9090:9090"
```

Buat file `otel-collector-config.yaml`:
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    timeout: 1s
    send_batch_size: 256

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
  logging:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

Buat file `prometheus.yaml`:
```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'go-enterprise-app'
    static_configs:
      - targets: ['host.docker.internal:8080']
```

#### Langkah 2: Bangun Profiler Trigger Dinamis
Buat file `internal/telemetry/profiler.go`:
```go
package telemetry

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime/pprof"
	"sync"
	"time"
)

type DynamicProfiler struct {
	mu           sync.Mutex
	isProfiling  bool
	outputDir    string
	lastProfile  time.Time
	coolDownTime time.Duration
}

func NewDynamicProfiler(outputDir string, coolDown time.Duration) *DynamicProfiler {
	_ = os.MkdirAll(outputDir, 0755)
	return &DynamicProfiler{
		outputDir:    outputDir,
		coolDownTime: coolDown,
	}
}

// TriggerCPUProfile menjalankan pprof otomatis selama durasi tertentu jika memenuhi syarat
func (p *DynamicProfiler) TriggerCPUProfile(duration time.Duration, reason string) error {
	p.mu.Lock()
	if p.isProfiling {
		p.mu.Unlock()
		return fmt.Errorf("profiling already running")
	}
	if time.Since(p.lastProfile) < p.coolDownTime {
		p.mu.Unlock()
		return fmt.Errorf("profiler cooldown period active")
	}

	p.isProfiling = true
	p.lastProfile = time.Now()
	p.mu.Unlock()

	go func() {
		fileName := filepath.Join(p.outputDir, fmt.Sprintf("cpu_%s_%d.pprof", reason, time.Now().Unix()))
		f, err := os.Create(fileName)
		if err != nil {
			p.resetState()
			return
		}
		defer f.Close()

		if err := pprof.StartCPUProfile(f); err != nil {
			p.resetState()
			return
		}

		time.Sleep(duration)
		pprof.StopCPUProfile()
		p.resetState()
		fmt.Printf("[DYNAMIC-PROFILER] CPU Dump berhasil disimpan: %s\n", fileName)
	}()

	return nil
}

func (p *DynamicProfiler) resetState() {
	p.mu.Lock()
	p.isProfiling = false
	p.mu.Unlock()
}
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan stack:
```bash
docker compose up -d
go run cmd/service/main.go
```
Jalankan benchmark beban dan inspeksi metrik exemplar:
```bash
curl -i http://localhost:8080/pay
curl -i -H "Accept: application/openmetrics-text" http://localhost:8080/metrics
```

---

### 13. Exercise

#### Level: Easy
- **Tugas**: Perbaiki potongan kode berikut yang mengalami *context detachment* dan trace hilang saat memproses sub-task di goroutine terpisah.
- **Problem Code**:
  ```go
  func ProcessOrder(ctx context.Context, orderID string) {
      tr := otel.Tracer("order")
      ctx, span := tr.Start(ctx, "ProcessOrder")
      defer span.End()

      go func() {
          // BUG: Kehilangan Trace Context!
          sendOrderNotification(context.Background(), orderID)
      }()
  }
  ```
- **Target**: Kirimkan context yang memiliki SpanContext valid ke `sendOrderNotification`, namun pastikan pembatalan context HTTP utama tidak membatalkan proses notifikasi.

#### Level: Medium
- **Tugas**: Buatlah implementasi `prometheus.Collector` kustom bernama `GoroutinePoolCollector`.
- **Target**: Collector harus membaca metrik dari worker pool internal (kapasitas pool, worker aktif, antrian pending). Seluruh data diambil menggunakan operasi pointer/atomic tanpa menaruh lock global di fungsi `Collect(chan<- prometheus.Metric)`.

#### Level: Hard
- **Tugas**: Buatlah sebuah middleware HTTP client round-tripper kustom (`http.RoundTripper`) yang mengimplementasikan:
  1. Injeksi header W3C TraceContext ke outgoing request secara manual (tanpa bantuan library `otelhttp`).
  2. Mengukur latensi request keluar dan mencatat metrik Prometheus Histogram yang dilekati Exemplar TraceID dari request induk.
  3. Memiliki penanganan kasus jika span induk tidak sampled (*NotSampled*), jangan mengalokasikan memori untuk Exemplar.

---

### 14. Challenge

**Skenario Tantangan Arsitektur**:
Anda adalah Principal Infrastructure Architect di unicorn ride-hailing. Anda diminta merancang arsitektur telemetri untuk Go core-service yang menangani 150.000 pesan streaming event Kafka per detik per node.

**Spesifikasi Persyaratan**:
1. Setiap pesan mengandung header biner yang harus di-decode menjadi `TraceContext`.
2. Trace hanya boleh disimpan jika:
   - Event processing menghasilkan status gagal (*dead-letter-queue*), **ATAU**
   - Waktu proses dari Kafka fetch hingga database commit memakan waktu > 50 milidetik.
3. Alokasi memori heap untuk telemetri tidak boleh melampaui **5% dari total alokasi heap aplikasi**.
4. Wajib mengimplementasikan mekanisme *dynamic continuous profiling* berbasis p99 spike latency: jika p99 latensi pemrosesan batch melampaui 100ms dalam jendela 30 detik berturut-turut, picu CPU dan Heap profile otomatis selama 15 detik, simpan ke Object Storage (S3/GCS), lalu kirim peringatan ke Webhook Slack internal.

**Ekspektasi Output**:
- Buat arsitektur pipeline berupa diagram detail.
- Tuliskan implementasi kode komponen utama (Custom Sampler / In-Memory Tail-Buffer / Dynamic Profiler Watcher) dalam Go standar enterprise tanpa library pihak ketiga yang tidak perlu.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Apa fungsi dari komponen `trace_flags` bernilai `01` pada format header W3C `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`?
   - A. Menunjukkan versi trace format adalah 1.
   - B. Menandakan bahwa span ini adalah span root.
   - C. Menandakan bahwa request ini telah dipilih untuk disampling (*Sampled*).
   - D. Menandakan span mengalami panic/error.

2. Mengapa penggunaan `SimpleSpanProcessor` sangat dilarang untuk aplikasi ber-throughput tinggi di lingkungan produksi?
   - A. Karena tidak mendukung protokol OTLP gRPC.
   - B. Karena mengekspor span secara sinkron pada thread eksekusi utama, memblokir siklus kerja aplikasi.
   - C. Karena tidak dapat membaca SpanContext dari remote microservice.
   - D. Karena menyebabkan memori leak pada Go runtime stack unwinding.

3. Apa efek buruk utama dari masalah *High Cardinality* pada Prometheus?
   - A. CPU aplikasi Go naik akibat parsing string.
   - B. Prometheus Server kehabisan memori (OOM) dan crash akibat lonjakan jutaan time-series unik.
   - C. OTel Collector menolak koneksi gRPC.
   - D. Jaringan network latency antar-pod mengalami saturasi bandwidth.

4. Berapa frekuensi default pengambilan sampel interupsi sinyal kernel pada CPU profiler Go (`runtime/pprof`)?
   - A. 10 Hz (Setiap 100ms)
   - B. 100 Hz (Setiap 10ms)
   - C. 1000 Hz (Setiap 1ms)
   - D. Realtime kontinu tanpa interval

5. Interface apa di package `prometheus` yang wajib diimplementasikan untuk membuat Custom Metric Collector?
   - A. `prometheus.Handler` dan `prometheus.Formatter`
   - B. `prometheus.Collector` yang mencakup method `Describe()` dan `Collect()`
   - C. `prometheus.MetricVec` dan `prometheus.Observer`
   - D. `prometheus.ExemplarProvider`

#### Bagian 2: Intermediate (Analisis Kasus Singkat)

6. Mengapa operasi `MustRegister` pada Prometheus registry default dapat menyebabkan aplikasi panik saat pengujian unit test (`go test ./...`)?
7. Jika sistem Anda menggunakan strategi Head-Based Sampling sebesar 1%, bagaimana dampaknya terhadap akurasi metrik latensi pada Prometheus Histogram jika metrik dihasilkan dari span tracer?
8. Bagaimana Exemplar bekerja menjembatani Metrik Prometheus dan Trace Backend (seperti Grafana Tempo) tanpa memicu High-Cardinality?
9. Mengapa pembacaan heap memory profile (`pprof.WriteHeapProfile`) di Go tidak merefleksikan alokasi yang dibebaskan oleh *Garbage Collector* secara instan?
10. Pada OpenTelemetry Collector, apa peran utama dari processor bertipe `batch`?

#### Bagian 3: Production Scenarios

11. **Skenario A**: Layanan microservice Go Anda mengalami lonjakan goroutine hingga ratusan ribu saat database PostgreSQL downstream mengalami pelambatan (*slow query*). Tracer OTel dikonfigurasi menggunakan BatchSpanProcessor default. Mengapa pemakaian memori container melonjak drastis hingga terkena Linux OOM-Killer padahal aplikasi memiliki timeout query 2 detik?
12. **Skenario B**: Tim SRE menemukan bahwa metrik custom collector aplikasi Anda memakan waktu 4 detik setiap kali di-scrape oleh Prometheus di endpoint `/metrics`. Hal ini menyebabkan Prometheus scraper menandai instance Anda sebagai `DOWN` (*scrape timeout*). Temukan letak kesalahan arsitektural di kode collector Go Anda dan jelaskan solusinya!
13. **Skenario C**: Anda mengamati bahwa TraceID yang dihasilkan oleh API Gateway tidak diteruskan ke layanan downstream saat request diproses melalui worker pool goroutine asinkron. Tunjukkan baris kesalahan konseptual implementasi context Go yang menyebabkan situasi ini!

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian 1: Basic
1. **C** - Nilai `01` pada byte terakhir (trace_flags) menandakan flag bitwise `Recorded/Sampled`. Backend tracing downstream akan mencatat span ini jika flag bernilai 1.
2. **B** - `SimpleSpanProcessor` mengekspor span secara langsung saat `span.End()` dipanggil di goroutine utama, mengakibatkan penambahan latensi I/O jaringan pada setiap transaksi.
3. **B** - Setiap kombinasi label value yang unik menghasilkan *time-series* baru. Jutaan series mengonsumsi RAM TSDB secara eksponensial hingga Prometheus mengalami OOM.
4. **B** - Default rate CPU profiler runtime Go adalah 100 Hz (100 sampel per detik atau setiap 10ms sekali) via sinyal OS `SIGPROF`.
5. **B** - `prometheus.Collector` membutuhkan implementasi signature `Describe(chan<- *prometheus.Desc)` dan `Collect(chan<- prometheus.Metric)`.

#### Bagian 2: Intermediate
6. **Pembahasan**: `MustRegister` akan memicu `panic` jika sebuah metrik dengan nama/deskriptor yang sama didaftarkan lebih dari satu kali ke registry yang sama. Saat unit test dieksekusi paralel atau berulang, registrasi berulang memicu kepanikan proses. Solusinya adalah menggunakan registry lokal via `prometheus.NewRegistry()`.
7. **Pembahasan**: Metrik latensi akan terdistorsi secara fatal. Metrik p99 tidak lagi mencerminkan 100% populasi traffic asli karena 99% request diabaikan sebelum metrik sempat dihitung. Metrik sebaiknya selalu dihitung 100% (unsampled), sedangkan tracing yang disampling.
8. **Pembahasan**: Exemplar menempelkan metadata (seperti `TraceID`) sebagai referensi tambahan di luar *index keys* time-series TSDB. TSDB tidak membuat index baru per TraceID, sehingga kapasitas penyimpanan dan indeks memori tetap stabil tanpa ledakan kardinalitas.
9. **Pembahasan**: Profiler heap membaca statistik dari alokasi runtime Go (`runtime.MemStats`). Jika GC belum dieksekusi, memori yang sudah tidak terpakai masih berada di heap arena sampai siklus siklus GC berikutnya berjalan atau dipaksa via `runtime.GC()`.
10. **Pembahasan**: Mengelompokkan spans/metrics/logs ke dalam satu payload berukuran tertentu atau interval waktu tertentu sebelum dikirim ke exporter backend. Ini memangkas *TCP/TLS handshake overhead*, overhead serialisasi, dan pemakaian socket jaringan.

#### Bagian 3: Production Scenarios
11. **Pembahasan**: Saat database melambat, jumlah transaksi yang aktif tertahan di memori melonjak drastis. Karena setiap transaksi membuat span OTel baru dan ratusan ribu goroutine tertahan bersamaan, antrean `BatchSpanProcessor` beserta alokasi konteks masing-masing goroutine menumpuk di heap. Alokasi memori goroutine stack (minimal 2KB per goroutine) dikalikan ratusan ribu goroutine, ditambah snapshot span yang belum di-flush, menghabiskan batas RAM container cgroup.
12. **Pembahasan**: Kesalahan arsitektural terjadi karena fungsi `Collect(ch chan<- prometheus.Metric)` melakukan pemanggilan I/O sinkron (seperti memanggil query DB, ping API, atau scanning resource jaringan secara langsung saat di-scrape). Solusinya: Ubah arsitektur menjadi *Background Metrics Worker*. Buat goroutine terpisah yang memperbarui variabel in-memory secara periodik (misal tiap 5 detik), lalu fungsi `Collect()` hanya membaca nilai dari variabel memori tersebut tanpa operasi I/O yang memblokir.
13. **Pembahasan**: Developer membuat goroutine baru dengan `go worker(context.Background())` atau `go worker(context.TODO())`. Cara ini membuang seluruh metadata span yang ada di context induk. Solusinya adalah mengekstrak SpanContext dari context induk dan menyuntikkannya ke context baru worker melalui `trace.ContextWithSpanContext(context.Background(), trace.SpanContextFromContext(parentCtx))`.

---

### 16. Summary

1. **Observabilitas Bukan Sekadar Library Tambahan**: Observabilitas skala enterprise di Go adalah bagian integral dari arsitektur aplikasi yang berdampak langsung pada latensi, konkurensi memori, dan biaya operasional cloud.
2. **Konteks Adalah Kunci**: Pemahaman mendalam atas propagasi `context.Context` melintasi sekat goroutine asinkron adalah syarat mutlak agar jejak *distributed tracing* W3C tidak terfragmentasi.
3. **Kardinalitas Adalah Musuh Utama TSDB**: Jangan pernah menaruh data bervolume dinamis tak terhingga (ID transaksi, email, Token) ke dalam label Prometheus. Gunakan **OTel Exemplars** untuk menghubungkan metrik dengan TraceID spesifik.
4. **Desain untuk Kegagalan Jaringan**: Selalu gunakan `BatchSpanProcessor` dengan batas alokasi buffer yang terukur, batasi timeout eksportir OTLP, dan amankan pipeline observabilitas agar pelambatan backend monitoring tidak pernah melumpuhkan pemrosesan bisnis inti aplikasi Anda.