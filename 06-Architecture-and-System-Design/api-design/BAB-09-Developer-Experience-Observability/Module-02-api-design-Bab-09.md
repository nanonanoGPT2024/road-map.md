# Kurikulum Enterprise: Arsitektur API & Rekayasa Sistem
## Kategori: 06-Architecture-and-System-Design
### BAB 09: Developer Experience (DX) & Observability Lanjutan
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Arsitektur Observabilitas Terdistribusi Mutakhir**: Mengimplementasikan telemetri terpadu (Distributed Tracing, High-Cardinality Metrics, Structured Contextual Logging) menggunakan OpenTelemetry (OTel) standard pada topologi microservices skala enterprise.
- **Menguasai Mekanisme Context Propagation**: Menganalisis dan merekayasa injeksi serta ekstraksi metadata konteks transaksional lintas batas jaringan asinkron dan sinkron berbasis spesifikasi W3C Trace Context (`traceparent`, `tracestate`) dan Baggage API.
- **Mengoptimalkan Sampling Strategies**: Merancang pipeline telemetri dengan *Tail-Based Sampling* pada OpenTelemetry Collector untuk menekan biaya penyimpanan (storage egress) hingga 70% tanpa kehilangan trace anomali/error.
- **Mencegah Degradasi Performa akibat Metric Cardinality Explosion**: Mendiagnosis dan memitigasi ledakan kardinalitas pada metrik Prometheus/Mimir melalui sanitasi label dinamis, exemplars, dan relabeling rules.
- **Membangun Ekosistem Developer Experience (DX) Berbasis Kontrak**: Mengotomatisasi siklus hidup API menggunakan pipeline OpenAPI Contract-First, deteksi *API Drift* pada CI/CD, dynamic mock injection, dan pipeline distribusi SDK enterprise.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Protokol Jaringan & HTTP Internals**: Pemahaman mendalam tentang HTTP/1.1, HTTP/2 multiplexing, gRPC/Protobuf framing, dan HTTP headers lifecycle.
- **Dasar Konkurensi & Goroutine/Async**: Pemahaman model konkurensi (Go Goroutines/Java Virtual Threads/Node.js Event Loop) dan propagasi `context.Context` (Go) atau `ThreadLocal` / `AsyncLocalStorage`.
- **Dasar-Dasar Telemetri**: Pemahaman konsep dasar Three Pillars of Observability (Logs, Metrics, Traces).
- **Infrastruktur Modern**: Pengoperasian Docker, Kubernetes primitives (DaemonSet, Deployment, Sidecar pattern), serta arsitektur reverse proxy/API Gateway (Envoy/Traefik).

---

### 3. Concept & Internal Architecture

Observabilitas modern bukan sekadar agregasi data log atau visualisasi dashboard; ia adalah instrumen matematis dan runtime untuk membedah *unknown-unknowns* pada sistem terdistribusi skala besar. Di sisi lain, Developer Experience (DX) modern memastikan antarmuka teknis API dapat dikonsumsi, diuji, dan dipelihara tanpa friksi kognitif.

```
+---------------------------------------------------------------------------------------+
|                                API OBSERVABILITY & DX ENGINE                          |
+---------------------------------------------------------------------------------------+
|  [ INGRESS: Envoy / Kong API Gateway ]                                                |
|    |--> Injeksi W3C Trace Context (traceparent, tracestate)                           |
|    |--> Ekstraksi API Key / Client ID -> Disimpan ke OTel Baggage                     |
+---------------------------------------------------------------------------------------+
        |
        v HTTP/gRPC (Propagasi Carrier Header)
+---------------------------------------------------------------------------------------+
|  [ CORE SERVICES: Go / Java Services ]                                                |
|    +-------------------------------------------------------------------------------+  |
|    | OpenTelemetry In-Process SDK                                                  |  |
|    |   |-- Context Engine: Span Processor -> Sampler (ParentBased/AlwaysOn)        |  |
|    |   |-- Metrics Engine: Cumulative Meter -> Prometheus Exporter/Exemplars       |  |
|    |   |-- Logging Engine: JSON Structural Logger (Zap/ZeroLog) + TraceID Link     |  |
|    +-------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
        | OTLP (gRPC / Port 4317)
        v
+---------------------------------------------------------------------------------------+
|  [ OPENTELEMETRY COLLECTOR PIPELINE ]                                                 |
|    +--------------------+    +-----------------------+    +-----------------------+   |
|    | Receivers (OTLP)   |--->| Processors            |--->| Exporters             |   |
|    |                    |    | - Memory Limiter      |    | - ClickHouse/Jaeger   |   |
|    |                    |    | - Batch Processor     |    | - Prometheus / Mimir  |   |
|    |                    |    | - Tail-Based Sampler  |    | - Loki / OpenSearch   |   |
|    +--------------------+    +-----------------------+    +-----------------------+   |
+---------------------------------------------------------------------------------------+
```

#### A. Anatomi W3C Trace Context Specification
Propagasi konteks terdistribusi distandarisasi oleh W3C melalui header:
1. `traceparent`: Format 4 segmen: `version-trace_id-parent_id-trace_flags`
   - `version` (2 Hex): Saat ini `00`.
   - `trace_id` (32 Hex): Entitas unik global yang merepresentasikan 1 siklus transaksi end-to-end (16 bytes).
   - `parent_id` / `span_id` (16 Hex): Entitas unik yang merepresentasikan sub-operasi pemanggil (8 bytes).
   - `trace_flags` (2 Hex): Konfigurasi runtime bitmask (misal: `01` menandakan *Sampled*).
2. `tracestate`: Pasangan key-value opaque khusus vendor untuk membawa routing metadata internal tracing vendor tanpa merusak interoperabilitas (`rojo=123,congo=456`).
3. `baggage`: Metadata non-telemetri lintas proses (misal: `tenant_id=us-east-1,user_tier=enterprise`) yang otomatis terbawa ke seluruh hop komunikasi downstream.

#### B. Internal Sampling Engine: Head-Based vs Tail-Based
- **Head-Based Sampling**: Keputusan apakah suatu trace akan disimpan atau dibuang dibuat di **titik awal request (Ingress)** sebelum transaksi selesai.
  - *Kelemahan*: Gagal menangkap kasus anomali (misal: trace yang menghasilkan HTTP 500 atau transaksi dengan latensi > 2 detik tidak dapat diprioritaskan jika saat sampling di awal ia terpilih untuk dibuang).
- **Tail-Based Sampling**: Keputusan sampling ditunda hingga **seluruh rentang span terkumpul** di memory OpenTelemetry Collector. Collector menganalisis seluruh siklus trace: jika trace mengandung span berstatus `Error` atau durasi total melebihi ambang batas SLA (misal: > 1500ms), maka trace dipertahankan 100%; sisanya disampling dengan persentase sangat kecil (misal: 1%).

#### C. High Cardinality & The Mechanics of Metrics Storage
Penyimpanan metrik time-series (TSDB) seperti Prometheus mengalokasikan alur data berdasarkan identitas unik:
$$\text{TimeSeries ID} = \text{MetricName} + \{\text{Sorted Label Pairs}\}$$
Jika sebuah service memiliki 10.000 users dan label `user_id` dimasukkan secara langsung ke dalam metrik `http_requests_total`, TSDB akan menghasilkan 10.000 time-series baru. Fenomena ini disebut **Cardinality Explosion**, yang menyebabkan alokasi memori heap TSDB meningkat secara eksponensial ($O(N)$ terhadap entitas label unik), memicu Out-Of-Memory (OOMKilled) crash pada Prometheus.

---

### 4. Why & What

| Dimensi | Pendekatan Observabilitas Tradisional | Arsitektur Enterprise Observability Terpadu |
| :--- | :--- | :--- |
| **Korelasi Data** | Terfragmentasi: Log file terpisah, metrik agregat di Cacti/Graphite, trace tidak ada. | Terpadu: Trace ID diinjeksi ke Log JSON; Metrik Prometheus mereferensikan Exemplar Trace ID. |
| **Context Propagation** | Header kustom yang rapuh (`X-Request-ID`), hilang saat berpindah protokol (HTTP -> Kafka -> gRPC). | W3C Trace Context & OpenTelemetry Propagation API standar IETF, tembus lintas transport protocol. |
| **Sampling Mechanism** | 100% logging mentah lokal (beban disk) atau sampling acak di ingress (kehilangan bug kritis). | Tail-Based Sampling cerdas di OTel Collector cluster; 100% error & high-latency traces tersimpan. |
| **Developer Experience** | Manual SDK writing, dokumentasi PDF/Wiki kadaluarsa, runtime debugging via trial-error. | OpenAPI-driven, automated mock service, generated typesafe SDKs, dan deteksi drift pada pipeline CI/CD. |
| **Storage & Cost** | Eksponensial: Storage jebol oleh log duplikat dan metrik high-cardinality yang tidak terfilter. | Terkendali: Deduplikasi span, filtering di edge/collector, dynamic log level tanpa restart pod. |

---

### 5. How (Workflow Detail)

Berikut alur eksekusi request sinkron dan asinkron melalui sistem dengan propagasi konteks penuh:

```
[Client] 
   │
   ▼ HTTP GET /api/v1/orders/ORD-9921
[Ingress Gateway (Envoy)]
   │ 1. Parse/Generate W3C traceparent (TraceID: a4f8..., SpanID: 01ab...)
   │ 2. Rekam Latensi Ingress -> Metric + Exemplar
   ▼ (HTTP Forward with Traceparent)
[Order Service (Go API)]
   │ 3. Extract Context dari HTTP Header via otel.GetTextMapPropagator()
   │ 4. Start Root Server Span: "HandleGetOrder"
   │ 5. Inject TraceID & SpanID ke Structured Logger Mapped Diagnostic Context (MDC)
   │ 6. Query DB (PostgreSQL) -> Start Child Client Span: "pg_query: orders"
   │ 7. Publish Event ke Kafka: "order.read" -> Inject Traceparent ke Kafka Record Header
   ▼
[Kafka Message Broker]
   │ Topic: order-events (Metadata membawa carrier headers)
   ▼
[Audit Service (Consumer)]
   │ 8. Extract Traceparent dari Kafka Message Headers
   │ 9. Start Child Consumer Span: "ProcessAuditLog" (ParentID: SpanID dari Order Service)
   │ 10. Finish Spans -> Flush via gRPC (OTLP) ke OpenTelemetry Collector
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengiriman Logistik Internasional Bersegel Digital
Bayangkan pengiriman kargo lintas negara.
- **Trace ID**: Nomor Resi Internasional tunggal pada paket terluar. Dari negara asal hingga tujuan akhir, nomor ini tidak pernah berubah.
- **Span ID**: Segel perantara di setiap pos pergantian transportasi (Segel Truk -> Segel Kontainer Kapal -> Segel Kurir Lokal). Setiap segel baru mencatat nomor segel sebelumnya (*Parent ID*).
- **Baggage**: Formulir bea cukai yang ditempel pada paket, menyatakan bahwa isi paket bertipe *Diplomatic Cargo* (Tenant Tier Enterprise). Semua pos pemeriksaan membaca formulir ini tanpa membuka isi paket.
- **Tail-Based Collector**: Satpam di gudang akhir. Jika paket tiba dalam kondisi rusak (*Error*) atau memakan waktu perjalanan melebihi estimasi (*High Latency*), seluruh riwayat rute pos dibukukan ke lemari arsip permanen. Jika paket tiba selamat tepat waktu, hanya 1 dari 1.000 riwayat paket yang disimpan sebagai statistik.

```
Trace Architecture:
-------------------------------------------------------------------------------------------
TRACE ID: 4bf92f3577b34da6a3ce929d0e0e4736
-------------------------------------------------------------------------------------------
[Span A] Ingress: GET /orders/ORD-9921 -----------------------------------------> [120ms]
    |
    +--- [Span B] Auth Middleware: ValidateJWT ----------------> [15ms]
    |
    +--- [Span C] Database: SELECT FROM orders WHERE id=? -----> [45ms]
    |
    +--- [Span D] Event Publish: Kafka PRODUCE order.read -----> [10ms]
             |
             +--- [Span E] Async Worker: ProcessAuditRecord ---------> [30ms]
-------------------------------------------------------------------------------------------
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Injeksi dan Ekstraksi Manual W3C Trace Context
Contoh mendasar cara memformat dan membedah header W3C `traceparent` secara deterministik.

```go
package main

import (
	"fmt"
	"strings"
)

type TraceParent struct {
	Version string
	TraceID string
	SpanID  string
	Flags   string
}

func ParseTraceParent(header string) (*TraceParent, error) {
	parts := strings.Split(header, "-")
	if len(parts) != 4 {
		return nil, fmt.Errorf("invalid traceparent format: %s", header)
	}
	if parts[0] != "00" {
		return nil, fmt.Errorf("unsupported traceparent version: %s", parts[0])
	}
	return &TraceParent{
		Version: parts[0],
		TraceID: parts[1],
		SpanID:  parts[2],
		Flags:   parts[3],
	}, nil
}

func (t *TraceParent) String() string {
	return fmt.Sprintf("%s-%s-%s-%s", t.Version, t.TraceID, t.SpanID, t.Flags)
}

func main() {
	rawHeader := "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
	tp, err := ParseTraceParent(rawHeader)
	if err != nil {
		panic(err)
	}
	fmt.Printf("Parsed Trace ID: %s\nParent Span ID: %s\nIs Sampled: %t\n",
		tp.TraceID, tp.SpanID, tp.Flags == "01")
}
```

#### B. Practical Example: Production-Grade Telemetry Middleware & Contextual Logger
Berikut adalah implementasi level produksi menggunakan Go 1.22+, OpenTelemetry SDK, Prometheus Client, dan Structured Logging dengan korelasi trace otomatis.

```go
package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
	stdouttrace "go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

// Global Telemetry Metrics
var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests processed, partitioned by status code and method.",
		},
		[]string{"method", "path", "status"},
	)
	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "Latency distributions of HTTP requests handled.",
			Buckets: []float64{0.005, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5},
		},
		[]string{"method", "path"},
	)
)

func init() {
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
}

// SetupTracerProvider menginisialisasi tracer pipeline OTel
func SetupTracerProvider() (*sdktrace.TracerProvider, error) {
	exporter, err := stdouttrace.New(stdouttrace.WithPrettyPrint())
	if err != nil {
		return nil, err
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithBatcher(exporter),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	return tp, nil
}

// StatusRecorder membungkus http.ResponseWriter untuk menginspeksi status HTTP downstream
type StatusRecorder struct {
	http.ResponseWriter
	StatusCode int
}

func (r *StatusRecorder) WriteHeader(code int) {
	r.StatusCode = code
	r.ResponseWriter.WriteHeader(code)
}

// TelemetryMiddleware menangani W3C propagation, distributed tracing, metrics, dan structured logging
func TelemetryMiddleware(next http.Handler, routePattern string) http.Handler {
	tracer := otel.GetTracerProvider().Tracer("enterprise-api-gateway")

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// 1. Ekstrak W3C context dari request headers
		ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))
		ctx, span := tracer.Start(ctx, fmt.Sprintf("%s %s", r.Method, routePattern),
			trace.WithSpanKind(trace.SpanKindServer),
		)
		defer span.End()

		recorder := &StatusRecorder{ResponseWriter: w, StatusCode: http.StatusOK}

		// 2. Logging terstruktur berkorelasi Trace ID & Span ID
		traceID := span.SpanContext().TraceID().String()
		spanID := span.SpanContext().SpanID().String()

		logger := slog.With(
			slog.String("trace_id", traceID),
			slog.String("span_id", spanID),
			slog.String("path", routePattern),
			slog.String("method", r.Method),
		)

		// Inject logger dan span context ke context request downstream
		reqWithCtx := r.WithContext(ctx)

		// Eksekusi downstream handler
		next.ServeHTTP(recorder, reqWithCtx)

		// 3. Rekam Metrik (Sanitasi path menggunakan static route pattern, cegah Cardinality Explosion)
		duration := time.Since(start).Seconds()
		httpRequestsTotal.WithLabelValues(r.Method, routePattern, fmt.Sprintf("%d", recorder.StatusCode)).Inc()
		httpRequestDuration.WithLabelValues(r.Method, routePattern).Observe(duration)

		logger.Info("Request completed",
			slog.Int("status", recorder.StatusCode),
			slog.Float64("duration_ms", duration*1000),
		)
	})
}

func OrderHandler(w http.ResponseWriter, r *http.Request) {
	// Ambil span aktif
	span := trace.SpanFromContext(r.Context())
	span.AddEvent("Retrieving database entity")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"order_id": "ORD-9921", "status": "CONFIRMED"}`))
}

func main() {
	tp, err := SetupTracerProvider()
	if err != nil {
		panic(err)
	}
	defer func() { _ = tp.Shutdown(context.Background()) }()

	mux := http.NewServeMux()
	
	// Daftarkan route dengan dynamic parameterized identifier yang dimapping ke format path baku
	mux.Handle("GET /api/v1/orders/{id}", TelemetryMiddleware(http.HandlerFunc(OrderHandler), "/api/v1/orders/{id}"))
	mux.Handle("/metrics", promhttp.Handler())

	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	slog.Info("Enterprise Server running on :8080")
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		slog.Error("Server terminated", slog.String("error", err.Error()))
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Kasus FinTech Gateway (150.000 Request/Detik)
- **Konteks**: Sebuah payment gateway memproses transaksi global. Arsitektur terdiri dari 45 microservices di Kubernetes.
- **Insiden Krisis**:
  1. *Telemetry Storm*: Tracing 100% (AlwaysOn) menghasilkan 30 TB data per hari ke Elasticsearch cluster, menyebabkan storage cluster crash berulang kali.
  2. *Cardinality Explosion*: Tim engineering menambahkan dynamic header `merchant_id` dan path mentah URL `/v1/payments/{payment_id}` sebagai label di Prometheus counter. Hasilnya: 45 juta time-series aktif tercipta dalam 3 jam, menyebabkan Prometheus menelan 64GB RAM hingga OOMKilled berulang kali.
  3. *Latency Blind-Spot*: Trace yang tersisa disampling 1% secara acak (Head-Based Sampling). Transaksi gateway yang mengalami timeout (p99.9 > 5 detik) tidak tertangkap di trace collector karena tereliminasi acak di Edge.

#### Solusi Arsitektur Skala Penuh:
1. **Penerapan OTel Collector Tail-Based Sampling**:
   - Mengalihkan sampling dari Edge ke cluster OTel Collector.
   - Kebijakan sampling: 100% trace yang memiliki tag `http.status_code >= 400` atau durasi total `> 1200ms` dipertahankan permanen. Trace sukses di bawah 1200ms disampling dengan persentase 0.05%.
2. **Mitigasi Ledakan Kardinalitas Metrik**:
   - Menghapus label dinamis `merchant_id` dan `payment_id` dari Metrik Counter/Histogram Prometheus.
   - Memanfaatkan **Prometheus Exemplars**: ID Merchant dan Trace ID dikaitkan ke histogram bucket tanpa membentuk time-series baru.
   - Melakukan canonical URL pattern normalization pada layer Reverse Proxy/Router Middleware (`/v1/payments/{id}`).
3. **Hasil Terukur**:
   - Biaya infrastruktur penyimpanan trace turun sebesar 78%.
   - Latency debugging MTTR (Mean Time to Resolution) untuk p99.9 turun drastis dari 4 jam menjadi 8 menit karena setiap kegagalan transaksi memiliki trace lengkap end-to-end.
   - Penggunaan memori Prometheus stabil pada kisaran 8 GB secara flat.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Kerugian & Batasan Sistem | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **Head-Based Sampling (5%)** | Beban komputasi & memori di collector sangat minimal; span dibuang di sumbernya langsung. | Melewatkan edge-case anomali, latensi p99, dan spike error sporadis. | Gunakan hanya untuk servis non-kritis berbeban sangat seragam (misal: read-only catalog). |
| **Tail-Based Sampling (OTel Collector)** | Observabilitas 100% terhadap seluruh request lambat, transient error, dan failure paths. | Collector membutuhkan kapasitas RAM masif untuk mem-buffer seluruh spans sebelum commit. | Gunakan routing load-balancing traceID di collector layer dan memory limiter processor. |
| **OpenTelemetry Baggage Propagation** | Metadata bisnis dapat diakses secara transparan di seluruh downstream services. | Overhead bandwidth jaringan meningkat karena data metadata menempel di setiap HTTP/gRPC header. | Batasi maksimal ukuran baggage (< 512 bytes) dan whitelist keys yang dizinkan. |
| **Zero-Code Instrumentation (Auto-instrument)** | Adopsi cepat tanpa modifikasi source code aplikasi (via eBPF atau Java Agent). | Visibilitas internal logic rendah; overhead CPU/latensi terkadang lebih tinggi dari instrumen manual. | Kombinasikan: Auto-instrumentation untuk boundary transport, manual SDK untuk business domain core. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Context Leaks dalam Pemanggilan Goroutine Asinkron
- **Kesalahan**: Mengirim `r.Context()` langsung ke goroutine yang hidup lebih lama daripada HTTP request lifecycle. Saat request selesai, HTTP engine membatalkan context tersebut (`ctx.Done()`), memicu error `context canceled` pada database write di background.
- **Troubleshooting**: Buat detached context baru dengan menyalin Trace Context aktif:
```go
// SALAH:
go func() {
    db.SaveAudit(r.Context(), auditData) // Gagal jika request selesai!
}()

// BENAR:
detachedCtx := trace.ContextWithSpan(context.Background(), trace.SpanFromContext(r.Context()))
go func(ctx context.Context) {
    db.SaveAudit(ctx, auditData)
}(detachedCtx)
```

#### 2. Metrik High Cardinality akibat Format Route Dinamis
- **Kesalahan**: Menggunakan path mentah `r.URL.Path` pada label Prometheus:
  `httpRequestsTotal.WithLabelValues(r.Method, r.URL.Path).Inc()` (Menghasilkan jutaan series untuk path `/orders/1`, `/orders/2`).
- **Solusi**: Gunakan template routing framework terdaftar seperti `/orders/{id}` atau lakukan normalisasi URL regex sebelum mengekspos data ke prometheus counter.

#### 3. Log Formatting Tanpa Structured Context Injection
- **Kesalahan**: Menulis trace ID secara manual ke dalam string format pesan (`log.Printf("TraceID: %s - User created", traceId)`). Ini menghancurkan kapabilitas parsing pengindeksan Elasticsearch/Loki.
- **Solusi**: Gunakan Structured Logger (misal: `slog` atau `zap`) yang menginjeksi Trace ID dan Span ID sebagai field key-value level root JSON.

---

### 11. Best Practices (Production Checklist)

1. **[ ] W3C Trace Context Enforcement**: Semua internal API Gateway dan Service Mesh harus meneruskan dan mengekstraksi header `traceparent` dan `tracestate`.
2. **[ ] Metric Normalization Policy**: Larang keras pencantuman UUID, Email, Timestamp, Token, atau Client Payload Arbitrer pada label metrik time-series.
3. **[ ] Tail-Sampling Collector Cluster**: Gunakan OTel Collector dengan konfigurasi minimal:
   - `memory_limiter`: Hard-limit memori 80%, soft-limit 60%.
   - `batch`: Timeout 1 detik, buffer batch size 8192 spans.
   - `tail_sampling`: Kebijakan error (status != OK) dan latency (> SLA).
4. **[ ] JSON Log Structure Baseline**: Log level produksi wajib mengeluarkan field standar: `timestamp`, `level`, `trace_id`, `span_id`, `service.name`, `environment`, `message`.
5. **[ ] Contract First Validation via CI/CD**: Verifikasi skema request/response OpenAPI specification menggunakan tooling *spectral linter* dan *contract tests* (Dredd/Prism) sebelum merging pull request.
6. **[ ] Automated SDK Generation**: Gunakan generator berbasis AST (seperti OpenAPI Generator atau Fern) dengan pipeline semantic versioning terotomatisasi untuk meminimalkan human error pada integrasi API client.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun pipeline observabilitas lengkap menggunakan Go, OpenTelemetry Collector, Prometheus, dan Jaeger.

#### Struktur Direktori:
```
hands-on/m02/
├── docker-compose.yml
├── otel-collector-config.yaml
├── prometheus.yml
├── main.go
└── go.mod
```

#### File: `hands-on/m02/otel-collector-config.yaml`
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20
  batch:
    send_batch_size: 1024
    timeout: 1s
  tail_sampling:
    decision_wait: 5s
    num_traces: 10000
    expected_new_traces_per_sec: 2000
    policies:
      [
        {
          name: error-policy,
          type: status_code,
          status_code: { status_codes: [ ERROR ] }
        },
        {
          name: latency-policy,
          type: numeric_attribute,
          numeric_attribute: { key: "http.status_code", value_condition: { greater_than_or_equal: 500 } }
        },
        {
          name: probabilistic-sample,
          type: probabilistic,
          probabilistic: { sampling_percentage: 10.0 }
        }
      ]

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: "otel"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, tail_sampling, batch]
      exporters: [otlp/jaeger]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
```

#### File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:1.54
    ports:
      - "16686:16686" # Web UI
      - "14250:14250"

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.95.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317" # OTLP gRPC
      - "4318:4318" # OTLP HTTP
      - "8889:8889" # Prometheus metrics exporter
    depends_on:
      - jaeger

  prometheus:
    image: prom/prometheus:v2.50.0
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    depends_on:
      - otel-collector
```

#### File: `hands-on/m02/prometheus.yml`
```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
  - job_name: 'api-service'
    static_configs:
      - targets: ['host.docker.internal:8080']
```

#### Eksekusi Hands-on:
1. Jalankan `docker compose up -d`.
2. Jalankan service Go dari seksi 7.B (`go run main.go`).
3. Kirim beberapa request:
   ```bash
   curl -i http://localhost:8080/api/v1/orders/ORD-101
   curl -i -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" http://localhost:8080/api/v1/orders/ORD-102
   ```
4. Buka Jaeger UI di `http://localhost:16686` dan Prometheus di `http://localhost:9090`.
5. Amati propagasi Trace ID yang disuntikkan secara eksplisit melalui header kustom W3C.

---

### 13. Exercise

#### Level Easy
Ubah implementasi `StatusRecorder` pada seksi 7.B agar turut menangkap jumlah *bytes written* (`Content-Length`) dan buat metrik Prometheus baru bernama `http_response_bytes_total` (Counter) yang merekam ukuran response berdasarkan `route` dan `status`.

#### Level Medium
Buatlah transport middleware HTTP client (`http.RoundTripper`) di Go yang menginjeksi context trace dan W3C propagation header secara otomatis ke setiap request downstream yang dikirimkan oleh service internal ke vendor payment eksternal, lengkap dengan span kind `SpanKindClient`.

#### Level Hard
Konstruksikan pipeline deteksi **API Schema Drift** pada GitHub Actions CI/CD:
1. Menjalankan mock server via Prism berdasarkan OpenAPI spec (`openapi.yaml`).
2. Menjalankan test skenario interaktif yang mencocokkan payload output controller aktual terhadap output schema spec.
3. Gagalkan build pipeline jika controller menghasilkan field JSON baru yang belum terdokumentasi di file spesifikasi OpenAPI (`additionalProperties: false` violation).

---

### 14. Challenge

**Skenario**: Anda memimpin tim arsitektur pada platform logistik On-Demand berkapasitas 500.000 transaksi/menit. Seluruh driver mengirimkan data GPS koordinat secara streaming tiap 3 detik via WebSocket/HTTP ke backend.
- **Permasalahan**:
  1. Pipeline traces saat ini memicu bottleneck jaringan (bandwidth outbound tembus 10 Gbps hanya untuk data telemetri).
  2. Database APM mengalami degradasi penulisan IOPS karena triliunan span pendek dengan informasi seragam ("Heartbeat GPS").
  3. Namun, ketika kurir mengalami crash aplikasi saat tombol "Selesaikan Pesanan" ditekan, tim produk menuntut trace lengkap data perjalanan 10 menit terakhir sebelum error tersebut terjadi.
- **Misi Desain**:
  Rancang rancang bangun observabilitas terdistribusi (arsitektur layer collector, buffer ring in-memory lokal, sampling policy, data retention, dan propagasi) yang sanggup:
  - Mengabaikan 99.99% transaksi koordinat normal tanpa membakar bandwidth egress.
  - Secara retroaktif mengunggah 10 menit riwayat span historis kurir yang bersangkutan HANYA jika terjadi status Error pada request penyelesaian pesanan.
  - Rancang solusi dalam format spesifikasi arsitektur teknis lengkap dengan topologi diagram dan strategi sinkronisasi ring buffer context.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Komponen apa saja yang membentuk header W3C `traceparent` standar?**
   - A. Version, Domain, UserID, SessionID
   - B. Version, TraceID, ParentID/SpanID, TraceFlags
   - C. AppID, IPAddress, Timestamp, Checksum
   - D. Protocol, RoutePath, Latency, Flags

2. **Apa fungsi utama dari OpenTelemetry Baggage API?**
   - A. Menyimpan payload data database secara terdistribusi.
   - B. Membawa metadata bisnis lintas hop service yang tidak otomatis menjadi span attribute.
   - C. Mengurangi beban kapasitas kompresi OTel Collector.
   - D. Menghasilkan format visualisasi pada Grafana.

3. **Apa bahaya arsitektural dari memasukkan nilai ID Pesanan (`order_id`) acak ke dalam label Prometheus metrics?**
   - A. Payload HTTP menjadi terlalu besar.
   - B. Cardinality explosion yang menyebabkan konsumsi memori Prometheus TSDB meledak (OOM).
   - C. Tracer provider akan membatalkan trace secara otomatis.
   - D. Nilai metrik akan dibulatkan ke nilai terdekat secara acak.

4. **Bagaimana format logging yang wajib diimplementasikan untuk memudahkan parsing dan korelasi log di level enterprise?**
   - A. Plain Text berformat custom delimiters.
   - B. Log berkas binary Protobuf mentah.
   - C. JSON Terstruktur dengan field `trace_id` dan `span_id` level root.
   - D. File teks CSV terkompresi.

5. **Kapan keputusan sampling dievaluasi pada metode Head-Based Sampling?**
   - A. Setelah seluruh response lifecycle downstream service selesai.
   - B. Di titik awal request pertama kali diterima oleh sistem.
   - C. Saat query database menghasilkan error diskonfirmasi.
   - D. Saat cronjob maintenance dijalankan pada malam hari.

#### Intermediate (5 Soal)
6. **Apa perbedaan mendasar antara span berjenis `SpanKindServer` dan `SpanKindClient`?**
   - A. `Server` span mengukur pemanggilan eksternal, `Client` span menangani synchronous worker.
   - B. `Server` span menangani incoming RPC/HTTP request, sedangkan `Client` span mengukur outgoing network calls ke downstream component.
   - C. `Server` span tidak memiliki trace ID, sedangkan `Client` span memiliki trace ID.
   - D. `Client` span hanya boleh dijalankan di browser web/mobile client.

7. **Mengapa Prometheus Exemplars dianggap solusi superior dibanding membuat label metrik baru untuk Trace ID?**
   - A. Exemplar tidak membuat time-series baru; ia menempelkan Trace ID sebagai metadata referensi pada histogram bucket sample yang sudah ada.
   - B. Exemplar memodifikasi tipe data metrik menjadi dynamic floating array.
   - C. Exemplar menghapus data trace historis dari memory secara otomatis.
   - D. Exemplar menyimpan seluruh payload body request secara permanen di database TSDB.

8. **Pada Tail-Based Sampling di OpenTelemetry Collector, apa fungsi konfigurasi parameter `decision_wait`?**
   - A. Menunda inisialisasi aplikasi saat container start up.
   - B. Waktu jeda tunggu toleransi untuk mengumpulkan seluruh fragmentasi spans dari trace yang sama sebelum algoritma sampling dieksekusi.
   - C. Mengatur batas koneksi socket timeout ke Jaeger storage.
   - D. Mengontrol interval scraping Prometheus exporter.

9. **Jika suatu request melewati Service A (Go) -> Kafka -> Service B (Java), bagaimana cara trace context diteruskan secara benar melalui Kafka broker?**
   - A. Menyisipkan trace parent ke dalam JSON payload body message.
   - B. Mengirim data trace melalui socket terpisah langsung dari Service A ke Service B.
   - C. Menyuntikkan W3C trace context bytes ke dalam native record headers Kafka.
   - D. Mengubah partition key Kafka menjadi TraceID.

10. **Apa kegunaan dari OpenAPI Linter seperti Spectral dalam siklus Developer Experience (DX)?**
    - A. Meng-compile source code API menjadi binary machine code.
    - B. Menerapkan tata kelola standar (governance), konvensi penamaan endpoint, dan validasi struktur skema API secara otomatis pada pipeline CI/CD.
    - C. Melakukan load test performa server secara otomatis.
    - D. Menghasilkan unit test database secara sintesis.

#### Skenario Kasus Produksi (3 Soal)

11. **Skenario Kasus 1**:
    Tim Anda meluncurkan service baru. Beberapa jam kemudian, Jaeger menunjukkan bahwa banyak trace tampak terputus (child span membentuk root trace baru, terpisah dari trace induk API Gateway). Investigasi menunjukkan tracing bekerja normal pada synchronous HTTP, tetapi terputus ketika request masuk ke worker pool internal via Go Channels.
    **Apa akar masalah teknis dan langkah perbaikannya?**
    - A. Saluran (Channel) Go tidak kompatibel dengan library network OTel; gunakan shared memory.
    - B. Worker mengambil data payload saja tanpa mengoper `context.Context` yang memuat `trace.SpanContext` ke dalam channel payload struct, sehingga child span di dalam worker dibuat menggunakan `context.Background()`. Perbaikannya adalah menyertakan struct envelope yang membungkus `context.Context` asli ke channel.
    - C. Tracer provider belum memanggil method `tp.ForceFlush()`.
    - D. OTel Collector kehabisan memory sehingga memotong parent trace secara deterministik.

12. **Skenario Kasus 2**:
    Di lingkungan staging berskala masif, metrik Prometheus untuk latency API menampilkan nilai p99 sebesar 50ms, namun pengguna di lapangan melaporkan respons time aktual mencapai 3000ms. Setelah dianalisis, sistem menggunakan Envoy Gateway di depan microservices.
    **Di mana letak kekeliruan arsitektural pengukuran metrik tersebut?**
    - A. Metrik latency hanya direkam di internal service handler dan tidak memperhitungkan queuing time, network transmission delay, TLS handshake, dan proxy routing time di layer Envoy Gateway.
    - B. Histogram Prometheus tidak mampu menghitung angka di atas 100ms.
    - C. Envoy membuang header latency sebelum diteruskan ke Prometheus.
    - D. Terjadi kegagalan penulisan disk pada storage server Prometheus.

13. **Skenario Kasus 3**:
    Sebuah arsitektur microservices menggunakan dynamic SDK generator untuk mengekspos client library ke 20 tim internal. Tim integrasi sering mengeluhkan aplikasi downstream sering mengalami runtime crash (`NullPointerException` / `Panic`) setelah service upstream melakukan deployment, meskipun upstream tidak mengubah nama endpoint API.
    **Praktik DX apa yang absen dari pipeline rilis dan bagaimana mengatasinya secara sistemik?**
    - A. Upstream service lupa memperbarui dokumentasi PDF internal.
    - B. Tidak diterapkannya *Contract Testing* dan *Breaking Change Detection* berbasis AST/OpenAPI Diff pada CI upstream untuk mencegah mutasi skema (seperti mengubah field required menjadi optional atau menghapus enum properties), serta tiadanya automated semantic versioning release pada pipeline SDK.
    - C. Downstream services tidak mematikan validasi JSON parsing runtime.
    - D. Upstream service seharusnya tidak menggunakan JSON dan beralih sepenuhnya ke plain-text SOAP.

---

### Kunci Jawaban Quiz

#### Basic
1. **B** — Format standar W3C `traceparent` adalah `version-trace_id-parent_id-trace_flags`.
2. **B** — Baggage mentransportasikan metadata bisnis (misal tenant id) lintas proses tanpa mengubah schema span secara manual.
3. **B** — Dynamic payload values menciptakan deret dimensi time-series unik tak terbatas (Cardinality Explosion), merusak index memori TSDB.
4. **C** — Structured JSON log dengan trace correlation key memungkinkan ingestion dan pencarian query otomatis yang cepat di search engine telemetri.
5. **B** — Head-based sampling mengevaluasi sampling tepat di titik terdepan sistem (ingress) sebelum trace berakhir.

#### Intermediate
6. **B** — `SpanKindServer` merepresentasikan penerimaan request (inbound), `SpanKindClient` mengukur pemanggilan keluar (outbound).
7. **A** — Exemplars menautkan TraceID langsung ke specific raw bucket data tanpa mengalokasikan memori series baru di TSDB.
8. **B** — Collector membutuhkan buffer window (`decision_wait`) untuk menerima semua span yang terpencar dari berbagai service sebelum mengambil keputusan sampling kolektif.
9. **C** — Header native Kafka adalah mekanisme canonical transport context carrier tanpa mengotori domain payload.
10. **B** — Linter OpenAPI seperti Spectral menegakkan architectural design rules & schema constraints secara terotomatisasi di level build pipeline.

#### Skenario Kasus Produksi
11. **B** — Hilangnya korelasi context akibat instansiasi context baru (`context.Background()`) di dalam consumer goroutine tanpa mengoper context yang mengikat span aktif.
12. **A** — Metrik observabilitas harus diukur sedekat mungkin dengan pengguna (Edge/Gateway) untuk menangkap network serialization, proxy overhead, dan backlog queuing.
13. **B** — Schema drift tak terdeteksi karena ketiadaan contract validation tool (seperti openapi-diff) di pipeline CI/CD yang bertugas memblokir breaking changes sebelum client SDK di-generate.

---

### 16. Summary

1. **Observabilitas Berbasis Standar**: Penggunaan standar terbuka seperti OpenTelemetry dan W3C Trace Context menghilangkan dependensi vendor lock-in dan menjamin metadata transaksi dapat melintasi batas bahasa pemrograman dan protokol transport.
2. **Korelasi Data Trinitas**: Kekuatan sistem pemantauan modern bertumpu pada korelasi mutlak: Log terstruktur memuat Trace ID; Metrik melampirkan Exemplar Trace ID; dan Trace mengisolasi durasi pemrosesan terkecil hingga ke statement basis data.
3. **Efisiensi Skala Enterprise**: Mitigasi ledakan kardinalitas metrik via Exemplars serta penerapan Tail-Based Sampling di OTel Collector terbukti menghemat biaya komputasi dan penyimpanan secara signifikan tanpa mengorbankan visibilitas terhadap anomali p99 dan system errors.
4. **DX Berbasis Kontrak (Contract-Driven DX)**: Developer Experience kelas enterprise dibangun di atas OpenAPI Specification yang menjadi sumber kebenaran tunggal (*single source of truth*) untuk dokumentasi, mock testing, validasi drift di CI/CD, hingga otomasi rilis Client SDK.