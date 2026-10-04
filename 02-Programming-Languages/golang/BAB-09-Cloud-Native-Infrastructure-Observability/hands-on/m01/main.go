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
