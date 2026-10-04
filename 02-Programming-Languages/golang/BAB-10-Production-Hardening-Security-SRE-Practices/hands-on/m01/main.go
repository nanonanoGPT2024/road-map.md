package main

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"runtime/debug"
	"sync/atomic"
	"syscall"
	"time"
)

// StateServer menyimpan status operasional sistem untuk integrasi readiness probe Kubernetes.
type StateServer struct {
	isReady atomic.Bool
}

func initSREEnvironment(logger *slog.Logger) {
	// 1. Terapkan Soft Memory Limit Programatik jika tidak disediakan melalui environment variable
	// Set ambang batas ke 900 MiB (asumsi cgroup limit container = 1 GiB)
	if os.Getenv("GOMEMLIMIT") == "" {
		const defaultMemLimit = 900 * 1024 * 1024
		debug.SetMemoryLimit(defaultMemLimit)
		logger.Info("GOMEMLIMIT secara dinamis diatur oleh aplikasi", "bytes", defaultMemLimit)
	}

	// 2. Modifikasi garbage collection target jika diperlukan
	if os.Getenv("GOGC") == "" {
		debug.SetGCPercent(80) // GC lebih agresif untuk mengurangi puncak penggunaan heap
	}
}

// createHardenedHTTPClient memproduksi HTTP client dengan timeout deterministik dan connection pooling optimal.
func createHardenedHTTPClient() *http.Client {
	return &http.Client{
		Timeout: 5 * time.Second, // Hard deadline total operasi request-response
		Transport: &http.Transport{
			Proxy: http.ProxyFromEnvironment,
			DialContext: (&net.Dialer{
				Timeout:   2 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			ForceAttemptHTTP2:     true,
			MaxIdleConns:          1000,
			MaxIdleConnsPerHost:   100,
			MaxConnsPerHost:       200,
			IdleConnTimeout:       90 * time.Second,
			TLSHandshakeTimeout:   2 * time.Second,
			ExpectContinueTimeout: 1 * time.Second,
			TLSClientConfig: &tls.Config{
				MinVersion: tls.VersionTLS13, // Force TLS 1.3
			},
		},
	}
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	initSREEnvironment(logger)

	state := &StateServer{}
	state.isReady.Store(true) // Server siap menerima traffic saat startup selesai

	httpClient := createHardenedHTTPClient()

	mux := http.NewServeMux()

	// Kubernetes Liveness Probe: Memvalidasi apakah proses masih berjalan (tidak deadlock)
	mux.HandleFunc("/healthz/liveness", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"alive"}`))
	})

	// Kubernetes Readiness Probe: Memvalidasi apakah server siap menerima traffic dari load balancer
	mux.HandleFunc("/healthz/readiness", func(w http.ResponseWriter, r *http.Request) {
		if !state.isReady.Load() {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`{"status":"draining"}`))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ready"}`))
	})

	// Endpoint Transaksi Pembayaran dengan Hardened Resilience Logic
	mux.HandleFunc("/api/v1/checkout", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, `{"error":"Method not allowed"}`, http.StatusMethodNotAllowed)
			return
		}

		// Batasi ukuran request body maksimum (misal 64 KB) untuk memitigasi exhaustion attack
		r.Body = http.MaxBytesReader(w, r.Body, 64*1024)

		// Context chaining dengan downstream timeout
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://httpbin.org/delay/1", nil)
		if err != nil {
			http.Error(w, `{"error":"Failed to build request"}`, http.StatusInternalServerError)
			return
		}

		resp, err := httpClient.Do(req)
		if err != nil {
			logger.Error("Downstream gateway gagal merespons", "error", err)
			w.WriteHeader(http.StatusBadGateway)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "Upstream timeout"})
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"payment_confirmed"}`))
	})

	srv := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadHeaderTimeout: 2 * time.Second,
		ReadTimeout:       5 * time.Second,
		WriteTimeout:      8 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}

	serverError := make(chan error, 1)
	go func() {
		logger.Info("Hardened Server berjalan", "port", 8080)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverError <- err
		}
	}()

	shutdownSig := make(chan os.Signal, 1)
	signal.Notify(shutdownSig, os.Interrupt, syscall.SIGTERM)

	select {
	case err := <-serverError:
		logger.Error("Server runtime failure", "error", err)
		return
	case sig := <-shutdownSig:
		logger.Info("Menerima shutdown signal", "signal", sig.String())
	}

	// STEP 1 GRACEFUL SHUTDOWN SRE:
	// Lepas status readiness agar Kube-Proxy/Ingress mencopot pod dari endpoint upstream
	logger.Info("Menonaktifkan Readiness probe (Draining stage 1)...")
	state.isReady.Store(false)

	// Beri jeda sleep 5-10 detik untuk propagasi pembaruan iptables/endpoints di cluster Kubernetes
	time.Sleep(5 * time.Second)

	// STEP 2: Drain koneksi aktif HTTP Server
	logger.Info("Menghentikan Listener HTTP Server (Draining stage 2)...")
	drainCtx, cancelDrain := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancelDrain()

	if err := srv.Shutdown(drainCtx); err != nil {
		logger.Error("Gagal gracefully shutdown, memaksa socket close", "error", err)
		_ = srv.Close()
	}

	logger.Info("Graceful termination selesai secara aman.")
}
