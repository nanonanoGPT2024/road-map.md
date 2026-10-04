# Bab 09 Module 01: Cloud-Native Infrastructure & Observability

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Topik Inti:** Go (Golang)
* **Modul:** Bab 09 Modul 01 — Cloud-Native Infrastructure & Observability
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** Pemahaman mendalam tentang Go Concurrency (`sync`, goroutines, channels), HTTP primitives (`net/http`), Context lifecycle (`context.Context`), serta dasar-dasar arsitektur kontainer (Docker/OCI) dan orkestrasi (Kubernetes).
* **Alokasi Waktu:** 8 - 12 Jam Belajar Terstruktur

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mengonfigurasi dan Mengimplementasikan OpenTelemetry (OTel) SDK secara Mandiri:** Membangun pipeline telemetri terpadu untuk Tracing terdistribusi dan Metrics berbasis OpenTelemetry v1.x di dalam aplikasi Go.
2. **Menguasai Structured Logging dengan `log/slog`:** Menerapkan logging terstruktur dengan contextual attributes, integrasi Span ID/Trace ID secara dinamis, dan kustomisasi handler untuk JSON output berperforma tinggi.
3. **Mendesain Sistem Health & Lifecycle Cloud-Native:** Mengimplementasikan endpoint `/livez` dan `/readyz` yang akurat serta pola Graceful Shutdown multi-tahap dengan koordinasi sinyal OS (`SIGINT`, `SIGTERM`).
4. **Mengoptimalkan Go Runtime pada Lingkungan Terkontainerisasi:** Mengendalikan GC overhead dan thread multiplexing menggunakan `GOMEMLIMIT` dan `uber-go/automaxprocs` guna mencegah pembunuhan pod oleh Kubernetes OOM Killer dan CPU throttling.
5. **Memitigasi Resiko Observabilitas Skala Besar:** Mengidentifikasi dan memecahkan masalah high-cardinality metrics, tracing overhead, dan resource leak pada background trace flushers.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam ekosistem cloud-native monolitik dan mikroservis terdistribusi, aplikasi tidak lagi beroperasi di atas server fisik statis dengan kapasitas prediktif. Aplikasi Anda hidup di lingkungan yang efemeral: pod dapat dimatikan, dipindahkan, dibatasi (throttled), atau kehabisan memori (OOMKilled) dalam hitungan milidetik.

### Tiga Pilar Observabilitas: Mental Model Terpadu

Observabilitas bukanlah tentang mengumpulkan sebanyak mungkin data log atau metrik, melainkan kemampuan untuk menyimpulkan kondisi internal sistem hanya berdasarkan output eksternalnya (*telemetry data*).

```
   +-----------------------------------------------------------+
   |                        SYSTEM STATE                       |
   +-----------------------------------------------------------+
             |                       |                       |
             v                       v                       v
      +--------------+        +--------------+        +--------------+
      |    METRICS   |        |    TRACES    |        |     LOGS     |
      +--------------+        +--------------+        +--------------+
      | "Kapan &     |        | "Di mana     |        | "Apa yang    |
      | seberapa     |        | latensi      |        | terjadi      |
      | buruk?"      |        | terjadi?"    |        | detailnya?"  |
      +--------------+        +--------------+        +--------------+
             |                       |                       |
             +-----------------------+-----------------------+
                                     |
                                     v
                       [ CONTEXT CORRELATION ]
            TraceID & SpanID mengikat Metrics dan Logs
```

1. **Metrics (Agregasi Numerik):** Memberikan sinyal awal degradasi sistem (misal: *Error rate 5xx naik ke 2%*). Metrik menjawab "Ada masalah apa dan seberapa parah?".
2. **Traces (Perjalanan Request):** Menunjukkan dependensi kausal antar-komponen dan lokasi bottleneck (misal: *Query ke PostgreSQL di Span X memakan waktu 4.2 detik*). Tracing menjawab "Di mana latensi terjadi?".
3. **Logs (Peristiwa Diskrit):** Memberikan konteks kontekstual paling mendalam pada satu titik waktu (misal: *Connection timeout ke host db-replica-1 dengan IP 10.244.1.15*). Logging menjawab "Mengapa peristiwa tersebut gagal?".

**Korelasi adalah Kunci:** Tanpa korelasi TraceID yang ditanamkan ke dalam Structured Log dan Metrics, Anda hanya memiliki tumpukan data terisolasi yang memperlambat investigasi *Mean Time to Resolution* (MTTR).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data telemetri dan integrasi lifecycle pod aplikasi Go di dalam kluster Kubernetes:

```
                          KUBERNETES CONTROL PLANE / INGRESS
                                       |
                   +-------------------+-------------------+
                   | [HTTP Request]                        | [Kubelet Probes]
                   v                                       v
         +------------------------------------------------------------+
         |                        POD RUNTIME                         |
         |                                                            |
         |   +-----------------------+    +-----------------------+   |
         |   |    HTTP Middleware    |    |  /livez  |   /readyz  |   |
         |   | - Extract TraceCtx    |    |  (Ping)  | (DB Check) |   |
         |   | - Start Server Span   |    +-----------------------+   |
         |   +-----------+-----------+                                |
         |               |                                            |
         |               v                                            |
         |   +-----------------------+                                |
         |   |    Business Logic     |                                |
         |   | - Context Propagation |                                |
         |   | - slog.With(trace_id) |                                |
         |   +-----------+-----------+                                |
         |               |                                            |
         |       +-------+-------+                                    |
         |       v               v                                    |
         |   [Database]    [External API]                             |
         |   (Child Span)   (Child Span)                              |
         |                                                            |
         | - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  |
         | OTel SDK Pipeline (BatchSpanProcessor / MetricReader)      |
         +-----------------------------+------------------------------+
                                       | (gRPC / OTLP)
                                       v
                       +-------------------------------+
                       |     OPENTELEMETRY COLLECTOR   |
                       +---------------+---------------+
                                       |
                  +--------------------+--------------------+
                  |                                         |
                  v                                         v
       +---------------------+                   +---------------------+
       |   Tracing Backend   |                   |   Metrics Backend   |
       |  (Tempo / Jaeger)   |                   |    (Prometheus)     |
       +---------------------+                   +---------------------+
```

### Alur Eksekusi Runtime:
1. **Request Masuk:** Ingress memicu request dengan header tracing (misal: `traceparent`).
2. **Context Ingestion:** Middleware mengekstrak context tersebut, menginisialisasi root/server span, lalu menyuntikkan trace ID ke `context.Context`.
3. **Execution & Logging:** Service logic mengeksekusi operasi. Jika terjadi logging via `slog`, TraceID diekstrak dari context dan disematkan ke payload JSON log secara otomatis.
4. **SDK Exporting:** OTel SDK mengumpulkan span dan metrik dalam memori buffer (batching queue) dan mengekspornya secara asinkron ke OpenTelemetry Collector melalui gRPC (OTLP).
5. **Kubelet Lifecycle:** Secara independen, kubelet memvalidasi `/livez` (apakah runtime deadlock?) dan `/readyz` (apakah dependensi siap menerima traffic?).

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Context Propagation di Go
OpenTelemetry bekerja dengan mengikat metadata tracing ke dalam `context.Context` Go. Objek `trace.Span` disimpan dalam context melalui `trace.ContextWithSpan(ctx, span)`. Mekanisme transfer konteks lintas batas jaringan bergantung pada *TextMapPropagator* (standar W3C Trace Context). Header `traceparent` memuat representasi string:
```
version - trace_id (16-byte) - parent_id/span_id (8-byte) - trace_flags (1-byte)
Contoh: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

### 2. GOMAXPROCS dan Penjadwal Go pada Kontainer
Secara default, Go runtime membaca jumlah CPU logis dari mesin host tempat ia berjalan melalui syscall OS (`sysconf(_SC_NPROCESSORS_ONLN)` pada Linux). Jika host memiliki 64 Core CPU dan container dibatasi kuota CFS (*Completely Fair Scheduler*) menjadi 2 Core di Kubernetes:
* Go runtime tanpa konfigurasi akan menginisialisasi 64 runtime threads (`P` - Processor dalam model GMP Go).
* Akibatnya: 64 Goroutine thread context switching mencoba berjalan pada 2 Core nyata yang dialokasikan CFS. CFS akan menghentikan alokasi CPU pod Anda (*CPU throttling* parah) karena kuota waktu CPU habis sebelum periode selesai.
* Solusi: Library seperti `go.uber.org/automaxprocs` membaca CFS quota dari `/sys/fs/cgroup/cpu` dan memanggil `runtime.GOMAXPROCS()` secara dinamis sesuai batas container.

### 3. GOMEMLIMIT dan Garbage Collector (GC)
Go GC adalah *concurrent tri-color mark-and-sweep GC*. Target eksekusi GC dipicu oleh rasio `GOGC` (default 100, berarti GC terpicu saat heap bertumbuh 100% dari heap pasca-GC sebelumnya).
* Di dalam container dengan memori dibatasi (misal 512MiB), jika aplikasi menggunakan 200MiB heap dan lonjakan traffic sementara mengalokasikan 150MiB, `GOGC=100` tidak akan memicu GC sampai heap mencapai 400MiB.
* Total memory usage (Heap + Stack + Go Runtime OS Overhead) dapat melebihi 512MiB sebelum GC berjalan.
* Hasil: Linux Kernel cgroup OOM killer mengirim sinyal `SIGKILL` tanpa peringatan.
* Sejak Go 1.19, `GOMEMLIMIT` menyediakan *soft memory limit*. Jika memory usage mendekati limit (misal: 90% dari 512MiB = 460MiB), runtime akan memicu GC lebih agresif untuk mencegah OOM.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Structured Logging: `log/slog` Architecture
Paket standar `log/slog` (sejak Go 1.21) memisahkan logging ke dalam dua layer:
1. **Front-End (`*slog.Logger`):** Menyediakan API bagi developer (`Info`, `Error`, `Debug`) untuk mencatat key-value attributes.
2. **Back-End (`slog.Handler`):** Bertanggung jawab memproses record (formatting, filtering, writing). Setiap record mencakup timestamp, level, pesan, PC (*program counter* untuk deteksi source file/line), dan daftar atribut `slog.Attr`.

Untuk menyatukan korelasi Tracing dan Logging, kita dapat membuat Custom Handler yang mengintersepsi pembuatan record: mengambil `trace.SpanFromContext(ctx)`, mengekstrak TraceID dan SpanID yang valid, lalu menyuntikkannya ke dalam field JSON log sebelum dialirkan ke `io.Writer`.

### Batch Span Processing
Mengirim span langsung ke jaringan pada saat transaksi selesai (*SimpleSpanProcessor*) adalah anti-pattern performa: setiap span akan memblokir goroutine dengan I/O gRPC.
OpenTelemetry SDK menyediakan `BatchSpanProcessor`:
* Menampung span yang selesai ke dalam antrean cincin (*ring buffer*) di memori.
* Menjalankan goroutine background terpisah untuk mengekspor batch span berdasarkan interval waktu (`BatchTimeout`) atau ukuran antrean (`MaxExportBatchSize`).
* Memerlukan mekanisme graceful shutdown: saat aplikasi berhenti, method `Shutdown(ctx)` pada `TracerProvider` harus dipanggil untuk melakukan *flush* seluruh span yang tersisa di memory buffer ke collector.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental: Server HTTP dengan OpenTelemetry Tracer, Structured Logging terintegrasi Context, dan Endpoint Health Check.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"log/slog"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

// TraceContextHandler adalah slog.Handler dekorator untuk injeksi TraceID/SpanID
type TraceContextHandler struct {
	slog.Handler
}

func (h *TraceContextHandler) Handle(ctx context.Context, r slog.Record) error {
	if ctx != nil {
		span := trace.SpanFromContext(ctx)
		if span.SpanContext().IsValid() {
			r.AddAttrs(
				slog.String("trace_id", span.SpanContext().TraceID().String()),
				slog.String("span_id", span.SpanContext().SpanID().String()),
			)
		}
	}
	return h.Handler.Handle(ctx, r)
}

func initTracer() (*sdktrace.TracerProvider, error) {
	exporter, err := stdouttrace.New(stdouttrace.WithPrettyPrint())
	if err != nil {
		return nil, fmt.Errorf("failed to create stdout exporter: %w", err)
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

func main() {
	// 1. Setup Structured Logger dengan Trace Correlation
	baseHandler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})
	logger := slog.New(&TraceContextHandler{Handler: baseHandler})
	slog.SetDefault(logger)

	// 2. Setup OTel Tracer Provider
	tp, err := initTracer()
	if err != nil {
		slog.Error("Failed to init tracer", slog.String("error", err.Error()))
		os.Exit(1)
	}

	tracer := otel.Tracer("cloud-native-demo")

	// 3. Router & Handlers
	mux := http.NewServeMux()

	// Probes
	mux.HandleFunc("/livez", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("OK"))
	})

	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		// Validasi kesiapan resource (misal: cek pool db)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("READY"))
	})

	// Business Route
	mux.HandleFunc("/api/process", func(w http.ResponseWriter, r *http.Request) {
		// Ekstraksi konteks W3C dari HTTP Headers
		ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))
		ctx, span := tracer.Start(ctx, "ProcessOrder")
		defer span.End()

		slog.InfoContext(ctx, "Processing order started", slog.String("user_id", "usr-8891"))

		select {
		case <-time.After(150 * time.Millisecond):
			slog.InfoContext(ctx, "Order processed successfully")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"status":"success"}`))
		case <-ctx.Done():
			slog.WarnContext(ctx, "Client aborted request")
			w.WriteHeader(http.StatusRequestTimeout)
		}
	})

	// 4. Server Initialization
	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// 5. Graceful Shutdown Engine
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		slog.Info("Server listening on :8080")
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("HTTP server failure", slog.String("error", err.Error()))
			os.Exit(1)
		}
	}()

	<-stopChan
	slog.Info("Shutdown signal received, initiating teardown...")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// Stop accepting new connections & drain existing
	if err := server.Shutdown(shutdownCtx); err != nil {
		slog.Error("Server forced to shutdown", slog.String("error", err.Error()))
	}

	// Flush remaining spans to exporter
	if err := tp.Shutdown(shutdownCtx); err != nil {
		slog.Error("Failed to flush tracer", slog.String("error", err.Error()))
	}

	slog.Info("Service gracefully stopped")
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis komponen fundamental di atas:

* **Baris 24–36 (`TraceContextHandler`):** Menerapkan pola *Decorator* pada `slog.Handler`. Fungsi `Handle` mengekstrak span aktif dari context via `trace.SpanFromContext(ctx)`. Jika span valid (`span.SpanContext().IsValid()`), field `trace_id` dan `span_id` disuntikkan secara programmatic langsung ke dalam objek `slog.Record` sebelum diteruskan ke handler dasar.
* **Baris 38–54 (`initTracer`):** Mengonfigurasi engine OpenTelemetry. `sdktrace.WithBatcher(exporter)` membungkus stream span dengan worker antrean asynchronous terpisah. `otel.SetTextMapPropagator` mendaftarkan propagasi standar `traceparent` (W3C standard) agar context tracing dapat melompat antar-layanan melalui HTTP headers.
* **Baris 78–86 (`/livez` & `/readyz`):** Memisahkan verifikasi liveness (apakah proses go hidup?) dari readiness (apakah sistem siap melayani query eksternal?). `/livez` tidak boleh mengecek database; `/readyz` wajib memvalidasi koneksi dependensi kritis.
* **Baris 90–93 (`Trace Extraction & Start`):** `Extract()` membaca header HTTP yang masuk (jika ada distributed tracing dari API Gateway) dan menyatukannya ke dalam Go context. `tracer.Start(ctx, "ProcessOrder")` memproduksi span baru yang secara otomatis menjadi child span dari trace ID yang diterima.
* **Baris 95 (`slog.InfoContext`):** Logging menggunakan varian `*Context`. Ini menjamin `TraceContextHandler` menerima context yang memiliki span aktif, menghasilkan structured JSON yang memiliki korelasi tracing instan.
* **Baris 120–136 (`Signal Handling & Lifecycle Execution`):** Mendaftarkan `SIGINT` dan `SIGTERM`. Saat container dihentikan oleh Kubernetes (`kubectl delete pod`), kernel mengirim `SIGTERM`. Listener membaca channel, lalu mengeksekusi `server.Shutdown()` untuk menolak request baru sambil menyelesaikan request yang berjalan, diikuti oleh `tp.Shutdown()` untuk mem-flush traces yang masih ada di memori SDK.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Insiden "The Silent OOMKilled & Deadlock Cascade"
**Konteks Perusahaan:** Platform FinTech Gateway Pembayaran.
**Gejala:** Pada event promosi kilat (*flash sale*), kluster Kubernetes mendadak me-restart 35% pod aplikasi backend Go secara berulang tanpa adanya panic log di stdout/stderr. Latensi P99 melesat dari 45ms ke 18 detik, menyebabkan transaksi drop signifikan.

### Akar Masalah (Root Cause Analysis):
1. **CPU Throttling & Go Scheduler Mismatch:** Pod dialokasikan `resources.limits.cpu = 2`, namun node Kubernetes menggunakan mesin c5.9xlarge (36 CPU). Go runtime menginisialisasi 36 `P` (GOMAXPROCS). Terjadi context switching goroutine berlebih, menghabiskan kuota CFS dalam 20ms pertama dari tiap periode 100ms CFS. Pod mengalami pembekuan (freezing) selama 80ms pada setiap siklus.
2. **Missing GOMEMLIMIT:** Memori kontainer dibatasi `limits.memory = 1Gi`. Go runtime tidak menyadari batas ini, mengalokasikan heap hingga 800MB sebelum GC terpicu oleh `GOGC=100`. Akibat alokasi buffers concurrency tinggi, total footprint menyentuh 1025MB, memicu Kernel Linux mengirim `SIGKILL` (Exit Code 137). Karena `SIGKILL` mematikan proses seketika, proses logging gagal mem-flush pesan error ke stdout.
3. **Improper Liveness Probe:** Tim DevOps mengarahkan Liveness Probe Kubernetes langsung ke endpoint yang menjalankan query `SELECT 1` ke PostgreSQL. Ketika pool database jenuh akibat throttling, endpoint mengembalikan HTTP 500. Kubernetes mengira pod mengalami deadlock dan langsung membunuhnya, memperburuk cascade failure karena pod baru yang baru booting harus melakukan koneksi ulang ke database yang sudah sekarat.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah solusi arsitektur lengkap kelas produksi yang mengintegrasikan OpenTelemetry Collector via gRPC, Prometheus Metric Exporter, Auto-GOMAXPROCS, Memory Limit Safeguard, dan Healthchecks independen.

```go
package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"runtime/debug"
	"sync/atomic"
	"syscall"
	"time"

	"log/slog"

	_ "go.uber.org/automaxprocs" // Otomatis mengonfigurasi GOMAXPROCS sesuai CFS quota

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"go.opentelemetry.io/otel/trace"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Definisikan Custom Metrics Prometheus
var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Jumlah total incoming HTTP requests.",
		},
		[]string{"method", "endpoint", "status"},
	)
	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "Durasi HTTP requests dalam detik.",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "endpoint"},
	)
)

func init() {
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
}

type TraceLogHandler struct {
	slog.Handler
}

func (h *TraceLogHandler) Handle(ctx context.Context, r slog.Record) error {
	if ctx != nil {
		span := trace.SpanFromContext(ctx)
		if span.SpanContext().IsValid() {
			r.AddAttrs(
				slog.String("trace_id", span.SpanContext().TraceID().String()),
				slog.String("span_id", span.SpanContext().SpanID().String()),
			)
		}
	}
	return h.Handler.Handle(ctx, r)
}

func setupOTel(ctx context.Context, serviceName, collectorAddr string) (*sdktrace.TracerProvider, error) {
	res, err := sdkresource.New(ctx,
		sdkresource.WithAttributes(
			semconv.ServiceNameKey.String(serviceName),
			semconv.ServiceVersionKey.String("1.0.0"),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	// Inisialisasi gRPC OTLP Exporter
	traceExporter, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithInsecure(),
		otlptracegrpc.WithEndpoint(collectorAddr),
		otlptracegrpc.WithDialOption(grpc.WithBlock()),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create trace exporter: %w", err)
	}

	bsp := sdktrace.NewBatchSpanProcessor(traceExporter,
		sdktrace.WithBatchTimeout(5*time.Second),
		sdktrace.WithMaxExportBatchSize(512),
	)

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.2))), // Sample 20% traffic
		sdktrace.WithResource(res),
		sdktrace.WithSpanProcessor(bsp),
	)

	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	return tp, nil
}

type ServerState struct {
	isReady atomic.Bool
	db      *sql.DB
}

func (s *ServerState) metricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rw := &responseWriterInterceptor{ResponseWriter: w, statusCode: http.StatusOK}

		next.ServeHTTP(rw, r)

		duration := time.Since(start).Seconds()
		httpRequestsTotal.WithLabelValues(r.Method, r.URL.Path, fmt.Sprintf("%d", rw.statusCode)).Inc()
		httpRequestDuration.WithLabelValues(r.Method, r.URL.Path).Observe(duration)
	})
}

type responseWriterInterceptor struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriterInterceptor) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func main() {
	// 1. Inisialisasi logging terstruktur
	baseHandler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			if a.Key == slog.TimeKey {
				return slog.String("timestamp", a.Value.Time().Format(time.RFC3339Nano))
			}
			return a
		},
	})
	slog.SetDefault(slog.New(&TraceLogHandler{Handler: baseHandler}))

	// 2. Proteksi Memori Runtime (GOMEMLIMIT safeguard manual jika env tidak diatur)
	if os.Getenv("GOMEMLIMIT") == "" {
		// Set soft limit 90% dari batas memori kontainer jika diketahui
		debug.SetMemoryLimit(450 * 1024 * 1024) // 450 MiB fallback
		slog.Info("Explicit soft memory limit configured", slog.Int64("limit_bytes", 450*1024*1024))
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// 3. OpenTelemetry Setup
	collectorAddr := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if collectorAddr == "" {
		collectorAddr = "localhost:4317"
	}
	tp, err := setupOTel(ctx, "payment-service", collectorAddr)
	if err != nil {
		slog.Warn("Failed to connect to OTel collector, tracing disabled", slog.String("err", err.Error()))
	}

	state := &ServerState{}
	state.isReady.Store(false)

	// Mock DB initialization
	go func() {
		slog.Info("Warming up database connections...")
		time.Sleep(3 * time.Second) // Simulasi bootstrap koneksi DB
		state.isReady.Store(true)
		slog.Info("Service dependencies are healthy and ready")
	}()

	mux := http.NewServeMux()

	// Liveness: Sangat ringan, membuktikan scheduler Go tidak terkunci (deadlock)
	mux.HandleFunc("/livez", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("healthy"))
	})

	// Readiness: Memastikan traffic tidak diarahkan jika komponen belum siap
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		if !state.isReady.Load() {
			http.Error(w, "Service Unavailable - Initializing Dependencies", http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ready"))
	})

	// Metrics endpoint
	mux.Handle("/metrics", promhttp.Handler())

	// Business Domain Endpoint
	mux.HandleFunc("/api/v1/charge", func(w http.ResponseWriter, r *http.Request) {
		ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))
		tracer := otel.Tracer("payment-gateway")
		ctx, span := tracer.Start(ctx, "ChargeExecution")
		defer span.End()

		slog.InfoContext(ctx, "Processing charge transaction", slog.String("transaction_id", "tx-99412"))

		// Simulasi proses
		time.Sleep(50 * time.Millisecond)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte(`{"status":"queued"}`))
	})

	// Wrap router with metric interceptor
	loggedAndMetricRouter := state.metricsMiddleware(mux)

	server := &http.Server{
		Addr:              ":8080",
		Handler:           loggedAndMetricRouter,
		ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout:       5 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		slog.Info("Application successfully running on :8080")
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("Fatal server error", slog.String("error", err.Error()))
			os.Exit(1)
		}
	}()

	// Menunggu Sinyal Shutdown
	<-stopChan
	slog.Info("SIGTERM intercepted. Initiating safe graceful shutdown...")

	// 1. Segera tandai diri tidak ready agar kubelet menghapus pod dari endpoints/ingress
	state.isReady.Store(false)

	// Kubernetes Network Rule Propagation Delay (memberikan waktu kube-proxy sinkronisasi)
	time.Sleep(5 * time.Second)

	shutdownTimeoutCtx, shutdownCancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer shutdownCancel()

	// 2. Stop Server HTTP
	if err := server.Shutdown(shutdownTimeoutCtx); err != nil {
		slog.Error("Forceful HTTP server termination triggered", slog.String("err", err.Error()))
	}

	// 3. Flush Traces
	if tp != nil {
		if err := tp.Shutdown(shutdownTimeoutCtx); err != nil {
			slog.Error("Failed to cleanly flush OpenTelemetry pipeline", slog.String("err", err.Error()))
		}
	}

	slog.Info("All background workers drained, application terminated cleanly")
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Trace Sampling: Head-based vs Tail-based Sampling

| Parameter | Head-based Sampling (Di SDK Go) | Tail-based Sampling (Di OTel Collector) |
| :--- | :--- | :--- |
| **Lokasi Keputusan** | Di awal request saat root span dibuat. | Di backend/collector setelah request selesai sepenuhnya. |
| **Overhead Komputasi Go** | Sangat Rendah. Jika tidak disampel, trace ID di-drop seketika tanpa tracing cost. | Sedang ke Tinggi. Seluruh spans tetap diekspor keluar container menuju collector. |
| **Kualitas Data** | Rendah. Transaksi error atau slow queries berpeluang tidak tercatat jika persentase sampling rendah. | Sempurna. Collector dapat membuat aturan: simpan 100% trace error & latensi tinggi, simpan 1% trace sukses biasa. |
| **Beban Bandwidth Jaringan** | Minimal. Menghemat I/O gRPC jaringan container. | Sangat Tinggi antar-pod ke Collector. |

### Metrics Model: Push (OTLP/StatsD) vs Pull (Prometheus Scraping)

| Karakteristik | Push Model (OTLP / OpenTelemetry) | Pull Model (Prometheus Scrape via `/metrics`) |
| :--- | :--- | :--- |
| **Arsitektur Pod** | Pod secara aktif membuka koneksi jaringan ke collector. | Pod menyediakan server HTTP pasif untuk dikunjungi scraper. |
| **Stateful Lifecycle** | Baik untuk short-lived job (AWS Lambda, K8s CronJob). | Buruk untuk short-lived job; ideal untuk long-running services. |
| **Skalabilitas Scraping** | Tidak membebani single scraper, tapi collector rawan bottleneck. | Prometheus server mengendalikan laju scraping; mencegah server terbebani flood metrics. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Context Leaks via Background Goroutine:**
   * *Masalah:* Meneruskan `r.Context()` HTTP server langsung ke goroutine background:
     ```go
     go func(ctx context.Context) {
         // Saat HTTP handler selesai, ctx dibatalkan otomatis oleh server!
         processAsync(ctx) // Error: context canceled
     }(r.Context())
     ```
   * *Mitigasi:* Gunakan `context.WithoutCancel(r.Context())` (tersedia sejak Go 1.21) untuk mempertahankan tracing context dan value tags tanpa membawa status deadline/cancellation dari HTTP request asal.

2. **File Descriptor Leak pada Broken OTLP Connection:**
   Jika OpenTelemetry Collector mati (*down*), konfigurasi gRPC exporter default tanpa backoff limit atau reconnect timeout yang tepat dapat menahan socket OS terbuka terus-menerus, menyebabkan konsumsi berlebih pada file descriptors (`/proc/sys/fs/file-nr`).

3. **High-Cardinality Metric Explosion:**
   * *Masalah:* Memasukkan `user_id`, `email`, atau `order_id` ke dalam Prometheus label:
     ```go
     httpRequestsTotal.WithLabelValues(r.Method, r.URL.Path, userID).Inc() // Fatal!
     ```
   * *Dampak:* Setiap kombinasi label menciptakan satu timeseries baru di memori Prometheus. Satu juta user ID unik akan melipatgandakan data memori server Prometheus hingga terjadi crash (*OOM Crash Loop*).
   * *Solusi:* Label hanya boleh berisi variabel terukur dengan batas (*bounded cardinality*), seperti HTTP status code, method, atau predefined error code.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Memanggil Database atau Deep Check di Liveness Probe
* *Salah:*
  ```go
  mux.HandleFunc("/livez", func(w http.ResponseWriter, r *http.Request) {
      if err := db.Ping(); err != nil { // BAHAYA!
          w.WriteHeader(500)
          return
      }
  })
  ```
* *Mengapa Salah:* Jika database sedang restart periodik atau jenuh sementara, Kubernetes akan menganggap container aplikasi crash dan membunuhnya berulang kali. Ini menciptakan badai restart pod (*CrashLoopBackOff* masal).
* *Solusi:* Liveness probe hanya boleh mengecek alokasi thread lokal dan event loop Go. Tempatkan pengecekan database pada `/readyz`.

### 2. Mengabaikan Propagation Ingestion pada Internal Microservice calls
* *Salah:* Memanggil downstream API dengan `http.NewRequestWithContext(ctx, ...)` standar tanpa menyuntikkan tracer propagator headers.
* *Solusi:* Gunakan wrapper `otelhttp.NewTransport(http.DefaultTransport)` atau secara eksplisit panggil:
  ```go
  otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))
  ```
  Tanpa ini, rantai distributed tracing akan putus dan layanan downstream akan dianggap sebagai root trace baru yang sama sekali tidak berhubungan.

### 3. Graceful Shutdown Tanpa Drain Period di Kubernetes
* *Salah:* Langsung memanggil `server.Shutdown()` seketika saat `SIGTERM` diterima.
* *Mengapa Salah:* Kubernetes membutuhkan waktu beberapa detik untuk menghapus IP pod dari Endpoints controller dan iptables/IPVS proxy di seluruh node. Jika aplikasi langsung menolak koneksi baru, client yang masih diarahkan ke pod tersebut akan mengalami `TCP connection refused` (HTTP 502/504).
* *Solusi:* Berikan `time.Sleep(5 * time.Second)` (atau jeda yang terukur) setelah mengubah flag kesiapan readiness probe sebelum mematikan server socket HTTP.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Semantic Conventions Resmi:** Patuhi standar atribut OpenTelemetry (`semconv`). Gunakan `semconv.HTTPRouteKey`, `semconv.DBSystemKey`, jangan menciptakan kunci metadata sendiri seperti `"url_path"` atau `"db_type"`.
2. **Log Record Formatting:**
   * Selalu gunakan format JSON di lingkungan staging & produksi.
   * Sertakan standard field: `timestamp`, `level`, `message`, `trace_id`, `span_id`.
   * Hindari string interpolation dalam log message (`slog.Info(fmt.Sprintf("user %s logged in", id))`). Gunakan structured attributes: `slog.Info("user logged in", slog.String("user_id", id))`.
3. **Penyelarasan Pod Lifecycle Limits:**
   * Tetapkan `GOMEMLIMIT` pada 85-90% dari `resources.limits.memory` Kubernetes pod spec.
   * Selalu import `_ "go.uber.org/automaxprocs"` di root file `main.go`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Benchmarking Log Allocations: String Interpolation vs `slog.Attr`
Penggunaan `slog.Attr` yang dipasangkan dengan strongly typed constructors (seperti `slog.Int64`, `slog.String`) menghindari alokasi heap ekstra akibat escape analysis yang terjadi pada generic `interface{}`/`any`.

```go
// Tidak Optimal: Menyebabkan alokasi memory heap untuk boxing interface{}
slog.InfoContext(ctx, "Processed transaction", "id", txID, "amount", amount)

// Optimal: Nol alokasi tambahan (Zero-Allocation Attribute Building)
slog.LogAttrs(ctx, slog.LevelInfo, "Processed transaction",
    slog.String("id", txID),
    slog.Float64("amount", amount),
)
```

### Tuning BatchSpanProcessor
Default OTel SDK terkadang terlalu konservatif atau boros tergantung beban:
* `MaxQueueSize`: Default 2048. Jika RPS Anda mencapai 20,000, tingkatkan queue size menjadi 8192 untuk mencegah drop span.
* Hindari `AlwaysSample()` di lingkungan high-throughput. Gunakan sampling probabilistik:
  ```go
  sdktrace.WithSampler(sdktrace.ParentBased(sdktrace.TraceIDRatioBased(0.05))) // 5% sample
  ```
  Ini menghemat CPU cycle aplikasi Go dan menghemat gigabyte data transfer per jam menuju collector.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Sanitasi Data Telemetri (PII Leakage Prevention):**
   * Metrik dan Tracing Span tidak boleh memuat Personally Identifiable Information (PII) seperti nomor kartu kredit, password, atau nomor identitas (NIK/SSN).
   * Gunakan interceptor/processor pada `slog` dan OTel SDK untuk melakukan masking nilai string berdasarkan regular expression sebelum data keluar dari proses memory:
     ```go
     func sanitizeAttr(a slog.Attr) slog.Attr {
         if a.Key == "password" || a.Key == "authorization" {
             return slog.String(a.Key, "[REDACTED]")
         }
         return a
     }
     ```
2. **Keamanan Endpoint Health dan Metrik:**
   * Jangan mengekspos endpoint `/metrics` ke publik internet tanpa autentikasi. Di Kubernetes, batasi akses `/metrics` hanya untuk scraping internal Prometheus pod network menggunakan Kubernetes `NetworkPolicy`.
   * Hindari menampilkan stacktrace mentah atau internal database error string di response payload `/readyz`.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Jika data telemetri tidak muncul di visualizer (Jaeger/Grafana/Prometheus):

1. **Inspeksi Internal OTel Errors:**
   OpenTelemetry SDK Go menyediakan interface error internal global. Pasang error handler untuk menangkap failure pipeline gRPC/OTLP:
   ```go
   otel.SetErrorHandler(otel.ErrorHandlerFunc(func(err error) {
       slog.Error("OpenTelemetry internal system error", slog.String("err", err.Error()))
   }))
   ```
2. **Testing Span Exporting Secara Lokal Tanpa Collector:**
   Ubah exporter ke stdout (`stdouttrace.New(stdouttrace.WithPrettyPrint())`) untuk memvalidasi bahwa span context benar-benar terbentuk dan context propagation berjalan antar service method.
3. **Memeriksa Cgroups Mapping pada Kontainer Runtime:**
   Masuk ke dalam pod via `kubectl exec -it <pod-name> -- sh` dan eksekusi:
   ```sh
   # Periksa kuota CPU aktual yang dideteksi OS
   cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us
   cat /sys/fs/cgroup/cpu/cpu.cfs_period_us

   # Periksa memori limit kontainer
   cat /sys/fs/cgroup/memory/memory.limit_in_bytes
   ```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **`GOMAXPROCS` Tuning:** Wajib pakai `go.uber.org/automaxprocs` agar runtime mengenali CFS limits CPU container dan menghindari throttling performa.
* **`GOMEMLIMIT` Enforcement:** Tetapkan ke 90% dari batas memori Kubernetes pod untuk menghindari silent killing (`Exit Code 137`).
* **Health Probes Split:**
  * `/livez` -> Cek ketersediaan runtime Go lokal. Jangan lakukan I/O ke eksternal dependensi.
  * `/readyz` -> Cek kesiapan dependensi eksternal (Database, Cache, dsb).
* **Correlation Pipeline:** Pasang Custom Handler pada `slog` yang membaca `trace.SpanFromContext(ctx)` untuk menyematkan `trace_id` dan `span_id` ke dalam JSON output log.
* **Graceful Lifecycle:** Tangkap `SIGTERM`, ubah state `/readyz` menjadi false, tunggu (drain period), tutup HTTP server via `Shutdown(ctx)`, lalu tutup OpenTelemetry TracerProvider via `Shutdown(ctx)`.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1 - 5)
1. **Apa perbedaan mendasar antara endpoint `/livez` dan `/readyz` dalam konteks orkestrasi pod Kubernetes?**
   * *Jawaban Singkat:* `/livez` memverifikasi apakah proses aplikasi hidup dan thread Go tidak deadlock. `/readyz` menentukan apakah pod siap menerima traffic (misal: koneksi DB stabil); kegagalan `/readyz` hanya mencabut traffic masuk tanpa me-restart container, berbeda dengan `/livez` yang memicu pod restart.

2. **Mengapa menambahkan `userID` dinamis ke dalam Prometheus metrics labels merupakan anti-pattern fatal?**
   * *Jawaban Singkat:* Menyebabkan *high-cardinality explosion*, di mana Prometheus harus menyimpan jutaan timeseries unik di memori RAM hingga server mengalami Out-Of-Memory.

3. **Format context propagation standar apakah yang digunakan secara default oleh OpenTelemetry untuk menyebarkan trace context via HTTP?**
   * *Jawaban Singkat:* W3C Trace Context Specification (header `traceparent` dan `tracestate`).

4. **Kapan sebaiknya kita menggunakan `slog.LogAttrs()` dibanding `slog.Info()` biasa?**
   * *Jawaban Singkat:* Ketika membutuhkan efisiensi memori tingkat tinggi (zero heap allocation) karena `LogAttrs` menghindari alokasi array dan interface conversion (`any`).

5. **Apa fungsi dari `BatchSpanProcessor` pada arsitektur OpenTelemetry Go SDK?**
   * *Jawaban Singkat:* Mengumpulkan spans ke dalam buffer memori dan mengekspornya secara asinkron dalam batch ke collector untuk mencegah blocking pada alur eksekusi aplikasi utama.

### Soal Intermediate (6 - 10)
6. **Jika pod Go Anda sering mati mendadak dengan Exit Code 137 tanpa log error, apa penyebab paling mungkin dan bagaimana cara memperbaikinya di Go 1.19+?**
   * *Jawaban Singkat:* Pod dimatikan oleh Linux OOM Killer karena melebihi resource memory limits. Solusinya adalah mengatur soft target limit `GOMEMLIMIT` (melalui env var atau `runtime/debug.SetMemoryLimit`) pada ~90% dari kuota container.

7. **Mengapa aplikasi Go yang berjalan pada container berkartu 64 CPU host dengan batas kuota `limits.cpu = 2` sering mengalami degradasi performa/latency spike jika tidak dikonfigurasi khusus?**
   * *Jawaban Singkat:* Go menginisialisasi 64 processor (`P`), menciptakan persaingan context-switch threads OS yang dengan cepat menghabiskan kuota waktu CFS Linux (throttling). Gunakan library `automaxprocs` untuk membatasi `GOMAXPROCS=2`.

8. **Bagaimana cara mencegah goroutine background kehilangan tracing metadata ketika HTTP request utama sudah selesai diproses?**
   * *Jawaban Singkat:* Bungkus context menggunakan `context.WithoutCancel(parentCtx)`. Ini mempertahankan nilai trace metadata tetapi melepaskan ikatan timeout/cancellation dari context HTTP induk.

9. **Mengapa eksekusi `tp.Shutdown(ctx)` pada TracerProvider wajib dipanggil saat proses graceful shutdown berlangsung?**
   * *Jawaban Singkat:* Karena spans yang baru selesai dieksekusi masih berada di dalam buffer antrean in-memory `BatchSpanProcessor`; pemanggilan `Shutdown()` memastikan seluruh data buffer di-flush secara tuntas ke jaringan sebelum proses mati.

10. **Apa bahaya melakukan Head-based Sampling 100% pada aplikasi dengan volume 50,000 Request per Detik?**
    * *Jawaban Singkat:* Menghabiskan CPU, alokasi memori berlebih untuk pembuatan span, membanjiri jaringan pod dengan data telemetri, serta berpotensi menumbangkan OpenTelemetry collector backend.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Objective Proyek
Bangun microservice bernama **"Resilient Order Service"** dalam Go murni dengan kriteria cloud-native berstandar produksi:

### Spesifikasi Teknis:
1. **Container Alignment:**
   * Aplikasi harus mengimpor `automaxprocs` dan mengonfigurasi `GOMEMLIMIT` fallback dinamis.
2. **Instrumentation:**
   * Setup OpenTelemetry pipeline menggunakan OTLP gRPC Exporter.
   * Instrumentasikan endpoint `/order/checkout` dengan Child Span:
     * `ValidateStock` (simulasikan delay 40ms)
     * `ProcessPayment` (simulasikan delay 80ms)
   * Buat counter metrik `orders_failed_total` dan `orders_success_total`.
3. **Structured Context Logging:**
   * Buat Custom `slog.Handler` yang menyuntikkan `trace_id` dan `span_id` ke setiap baris log.
4. **Resilient Lifecycle:**
   * Sediakan `/livez` dan `/readyz`.
   * Sediakan endpoint dummy `/toggle-db-failure` yang dapat mengubah status konektivitas mock DB menjadi putus untuk menguji apakah `/readyz` mengembalikan HTTP 503 sementara `/livez` tetap HTTP 200.
   * Implementasikan shutdown pipeline dengan buffer drain 5 detik sebelum menutup socket server dan flushing tracer spans.

### Langkah Validasi Mandiri:
1. Jalankan OpenTelemetry Collector dan Jaeger via `docker-compose`.
2. Lakukan load testing sederhana menggunakan `hey` atau `wrk` ke endpoint `/order/checkout`.
3. Buka visualizer Jaeger UI dan pastikan span hierarchy terbentuk sempurna:
   ```
   [CheckoutHandler] (Total: 125ms)
       |-- [ValidateStock] (40ms)
       \-- [ProcessPayment] (80ms)
   ```
4. Verifikasi bahwa file log JSON di terminal mencetak nilai `trace_id` yang identik dengan ID yang terlihat di UI Jaeger.
5. Kirim sinyal `kill -SIGTERM <PID>` ke aplikasi dan pastikan log `"All background workers drained, application terminated cleanly"` tercetak tanpa adanya data trace yang hilang (*zero dropped spans*).