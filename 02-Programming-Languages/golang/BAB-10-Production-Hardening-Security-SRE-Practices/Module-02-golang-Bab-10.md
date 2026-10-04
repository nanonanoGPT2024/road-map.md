# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Production Hardening, Security & SRE Practices — Golang Enterprise Curriculum**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengonfigurasi Go Runtime** pada containerized environment (Kubernetes) menggunakan mekanisme `GOMEMLIMIT`, `GOMAXPROCS`, dan GC tuning (`GOGC`) untuk mengeliminasi risiko OOM (*Out-Of-Memory*) kills tanpa mengorbankan latensi p99.
- **Mengimplementasikan Arsitektur Zero-Trust Transport Security** berbasis Mutual TLS (mTLS) dengan TLS 1.3 strict cipher suites, custom certificate verification, dan dynamic cert rotation tanpa service restart.
- **Membangun Resiliency & Defensive Engineering Patterns** menggunakan concurrency-safe token-bucket rate limiters, distributed circuit breakers, adaptive concurrency limiters, dan graceful drain/shutdown pipeline.
- **Merancang Secure Supply Chain & Hardened Runtime Container** dengan multi-stage builds, Distroless/scratch images, reproducible builds (CGO disabled, build-id strip, trimpath), serta pemindaian dependensi runtime via `govulncheck`.
- **Mengintegrasikan Observability Tingkat Lanjut (SRE Core)** menggunakan continuous profiling (`net/http/pprof` aman/terproteksi), OpenTelemetry tracing context propagation, dan metrik RED (*Rate, Errors, Duration*) terstandarisasi Prometheus.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Go Concurrency Primitives**: Mutex, Channels, Sync Pools, Context cancellation, Goroutine leak detection.
- **Go Memory Model**: Stack vs. Heap allocation, pointer escapes, basic garbage collector lifecycle.
- **Networking Fundamentals**: TCP 3-way handshake, TLS handshake, HTTP/1.1 vs HTTP/2 multiplexing.
- **Linux & Containerization**: Linux cgroups v1/v2, CFS (*Completely Fair Scheduler*) quota, namespaces, dan Docker build mechanics.

---

## 3. Concept & Internal Architecture

Implementasi Go pada skala enterprise menuntut pemahaman mendalam tentang interaksi antara **Go Runtime Engine**, **Linux Kernel (cgroups)**, dan **Security Boundaries**.

```
+-----------------------------------------------------------------------------------+
|                               Linux cgroup v2 Namespace                           |
|  Memory Limit: 1024 MiB                       CPU Quota: 2000m (CFS Bandwidth)     |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                             Go Runtime Layer                                |  |
|  |                                                                             |  |
|  |  +---------------------+  +------------------------+  +------------------+  |  |
|  |  |    Go Scheduler     |  |       Memory/GC        |  |  Network Poller  |  |  |
|  |  | GOMAXPROCS = 2      |  | GOMEMLIMIT = 900MiB    |  | epoll / kqueue   |  |  |
|  |  | (automaxprocs)      |  | GOGC = 100 (adaptive)  |  | Non-blocking I/O |  |  |
|  |  +----------+----------+  +-----------+------------+  +--------+---------+  |  |
|  +-------------|-------------------------|------------------------|------------+  |
|                v                         v                        v               |
|  +-----------------------------------------------------------------------------+  |
|  |                           Application Logic Domain                          |  |
|  |  +-----------------------+ +---------------------+ +---------------------+  |  |
|  |  |  Strict TLS 1.3 mTLS  | | Adaptive Concurrency| | Continuous Profiler |  |  |
|  |  |  & In-Memory Keystore | | & Circuit Breaker   | | /debug/pprof (Auth) |  |  |
|  |  +-----------------------+ +---------------------+ +---------------------+  |  |
+--+-----------------------------------------------------------------------------+--+
```

### 3.1 Go Runtime Memory Limits & GC Pacing (`GOMEMLIMIT`)
Secara default, Go GC menentukan waktu eksekusi cycle berikutnya berbasis persentase pertumbuhan heap menggunakan `GOGC` (default: 100, artinya heap dapat tumbuh 100% dari live heap sebelum GC terpicu). 

Dalam container berkendala memori (misal: 1 GiB), jika live heap sebesar 600 MiB, target heap berikutnya menjadi 1.2 GiB. Linux kernel OOM killer akan menghentikan proses (`SIGKILL`) sebelum GC cycle berjalan karena batas cgroup terlampaui.

Mulai Go 1.19, diperkenalkan mekanisme **Soft Memory Limit** via `runtime/debug.SetMemoryLimit` atau environment variable `GOMEMLIMIT`. Controller GC menggunakan pendekatan target ganda:
$$\text{Trigger} = \min(\text{Target}_{GOGC}, \text{Target}_{GOMEMLIMIT})$$
Ketika memori mendekati `GOMEMLIMIT`, GC akan berjalan lebih agresif. Jika alokasi berlebih berlanjut, Go runtime mengorbankan CPU footprint (hingga batas throttling maksimum 50% CPU untuk GC) demi mencegah OOM kill.

### 3.2 CFS Quotas dan Goroutine Scheduling Throttling
Go scheduler mengalokasikan threads OS ($M$) berdasarkan nilai $P$ (`GOMAXPROCS`), yang secara default membaca jumlah hardware CPU core yang terlihat oleh kernel. Pada container yang dialokasikan `limit: 2000m` pada node 64-core, runtime Go secara default menginisialisasi `GOMAXPROCS = 64`. 
Hal ini mengakibatkan fenomena **CFS Throttling**:
1. 64 logical thread mengeksekusi goroutines secara paralel.
2. Jatah CPU quota 2 core (200ms per periode 100ms CFS) habis dalam waktu $200\text{ms} / 64 \approx 3.125\text{ms}$.
3. Kernel menangguhkan (*throttle*) seluruh thread selama $96.875\text{ms}$ tersisa dari periode CFS, memicu spike latensi drastis pada p99.
Solusi arsitektur: Penggunaan dynamic cgroup detection (`go.uber.org/automaxprocs`) untuk menyelaraskan $P$ dengan Linux CFS limits.

### 3.3 Zero-Trust mTLS Internal Mechanics
Dalam model Zero-Trust, otentikasi perimeter tidak lagi memadai. Setiap microservice wajib mengotentikasi dan mengotorisasi setiap request masuk. Go runtime `crypto/tls` menyediakan implementasi native TLS 1.3 yang memory-safe (kebal buffer overflow OpenSSL). 

Arsitektur handshake mTLS:
1. Client Hello + Supported Ciphers (`TLS_AES_128_GCM_SHA256`, `TLS_AES_256_GCM_SHA384`, `TLS_CHACHA20_POLY1305_SHA256`).
2. Server Hello + Server Certificate.
3. Server mengirim `CertificateRequest` (memeriksa CA root spesifik).
4. Client mengirim Client Certificate + `CertificateVerify` (tanda tangan digital payload handshake).
5. Kedua belah pihak memverifikasi Subject Alternative Name (SAN) atau SPIFFE ID (`spiffe://cluster.local/ns/prod/sa/payment-svc`) via custom callback `VerifyPeerCertificate`.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Production-Hardened Go |
| :--- | :--- | :--- |
| **GC Management** | Bergantung sepenuhnya pada default `GOGC=100`, sering terjadi transient spike OOM. | Integrasi `GOMEMLIMIT` (90% cgroup) + dynamic `GOGC` adjustment untuk stabilitas latency. |
| **Concurrency Scaling** | Menggunakan raw goroutines tanpa batas (`go handler()`). Rentan leak memori & CPU exhaustion. | Concurrency throttling, Dynamic Token Bucket, Worker Pool bounded, Adaptive In-flight Limits. |
| **Service Identity** | Static API Keys / Basic Auth, cleartext HTTP via internal overlay network. | Strict TLS 1.3 mTLS, ephemeral cert dynamic rotation, SPIFFE ID parsing, sanitasi error TLS. |
| **Profiling & Metrics** | Port profiling terbuka ke publik tanpa autentikasi, ekspos detail infrastruktur. | Dedicated isolated loopback/Unix Domain Socket pprof, basic-auth/mTLS protected, scrubbed metrics. |
| **Artifact Packaging** | Docker build berbasis Ubuntu/Alpine dengan dynamic linked binaries (`glibc`). | Multi-stage distroless/scratch builds, statically compiled (`CGO_ENABLED=0`), non-root UID 65532. |

---

## 5. How (Workflow Detail)

Alur pipeline pengamanan dan operasionalisasi microservice Go produksi:

```
+----------------------------------------------------------------------------------------+
|                                BUILD & PACKAGING PIPELINE                              |
+----------------------------------------------------------------------------------------+
 [Source Code] 
       │
       ▼
 [govulncheck] ──(Detects CVEs)──► [Fail Build if High/Crit]
       │
       ▼
 [CGO_ENABLED=0 go build -trimpath -ldflags="-s -w"]
       │
       ▼
 [Scratch / Distroless Base Image] ──► [Non-Root User Configuration (UID 65534)]
       │
       ▼
+----------------------------------------------------------------------------------------+
|                              BOOTSTRAP & RUNTIME LIFECYCLE                             |
+----------------------------------------------------------------------------------------+
 [Container Starts]
       │
       ▼
 [automaxprocs.Set()] ──► Menyelaraskan GOMAXPROCS dengan Linux CFS Quota
       │
       ▼
 [GOMEMLIMIT Configuration] ──► Membaca cgroup mem limit & set headroom (90%)
       │
       ▼
 [mTLS Server Initialization] ──► Load KeyPair, Attach Custom Peer Verifier
       │
       ▼
 [HTTP Server with Timeouts] ──► Set ReadHeader, Read, Write, and Idle Timeouts
       │
       ▼
 [Listen for OS Signals] (SIGTERM, SIGINT) ──► Trigger Graceful Drain (Context Deadline)
```

1. **Static Analysis & Supply Chain**: Menggunakan `govulncheck` pada AST level (bukan hanya text-based lock scanning) untuk mengeliminasi false positive dan memverifikasi keterpanggilan kode rentan.
2. **Deterministic Binary Compilation**: Flags `-trimpath` membersihkan absolut local path dari binary untuk mencegah information leak saat runtime panic. Flags `-ldflags="-s -w"` memangkas debug symbol table dan DWARF signature guna mengecilkan ukuran attack surface.
3. **Adaptive Initialization**: Binary saat inisialisasi mendeteksi environment cgroup, mengonfigurasi kuota thread Go, dan mendaftarkan health probes terpisah dari network ingress utama.
4. **Resilient Request Execution**: Setiap request masuk melalui rangkaian interceptor: TLS Handshake Verifier $\to$ Adaptive Rate Limiter $\to$ Circuit Breaker $\to$ Business Logic with Deadlines $\to$ Distributed Tracer Context.
5. **Deterministic Tear-down**: Signal handler menghentikan penerimaan trafik baru, menyelesaikan proses inflight request dalam rentang SLA grace period, dan melepaskan shared connection pool secara tertib.

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Pengendalian Bendungan (GC & Rate Limiting)
Bayangkan container Go Anda adalah waduk buatan:
- **Kapasitas Waduk**: Batas memori cgroup (misal 1 GiB).
- **GOGC**: Protokol pembuangan air berkala. Jika air naik 100%, pintu dibuka. Namun jika air mengalir terlalu deras, air bisa meluap sebelum pintu terbuka (OOM).
- **GOMEMLIMIT**: Sensor darurat pada ketinggian 900 MiB. Segera setelah air mencapai batas ini, turbin dibuka secara maksimal tanpa menunggu siklus reguler, menjaga air tidak melewati bibir bendungan (menghindari kernel `SIGKILL`).
- **Circuit Breaker & Rate Limiter**: Pintu air di hulu sungai yang membatasi volume air masuk ketika bendungan di hilir mengalami turbulensi ekstrem.

```
cgroup Hard Limit: [==================================================] 1024 MiB (OOM KILL)
GOMEMLIMIT Safety: [==========================================] 920 MiB (GC Aggressive Trigger)
Normal Heap Range: [=====================] 500 MiB (Standard GOGC Pacing)
                   ^                     ^
                   Live Objects          Burst In-Flight Data
```

---

## 7. Simple & Practical Implementation Examples

### 7.1 Simple Example: Dynamic Runtime Limiter & CFS Aware Initializer

Contoh inisialisasi minimal production baseline pada Go service:

```go
// bootstrap.go
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"runtime/debug"
	"syscall"
	"time"

	_ "go.uber.org/automaxprocs" // Otomatis menyesuaikan GOMAXPROCS dengan CFS Quota
)

func initRuntimeLimits(cgroupMemLimitBytes int64) {
	// Sisakan 10% memory headroom untuk OS, network buffers, dan off-heap allocation
	headroom := float64(cgroupMemLimitBytes) * 0.10
	goMemLimit := int64(float64(cgroupMemLimitBytes) - headroom)

	debug.SetMemoryLimit(goMemLimit)
	slog.Info("runtime boundaries initialized",
		"gomemlimit_bytes", goMemLimit,
		"headroom_bytes", int64(headroom),
	)
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	// Asumsikan cgroup limit 512 MiB
	const mockCgroupLimit = 512 * 1024 * 1024
	initRuntimeLimits(mockCgroupLimit)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	slog.Info("service worker started successfully")
	<-ctx.Done()

	slog.Info("shutdown signal intercepted, starting termination...")
	time.Sleep(1 * time.Second) // Drain simulasikan
	slog.Info("graceful exit completed")
}
```

---

### 7.2 Practical Example: Enterprise Hardened Production Server

Contoh implementasi komprehensif mengintegrasikan:
- HTTP Server dengan Timeouts Terproteksi dari Serangan Slowloris.
- Zero-Trust TLS 1.3 Configuration dengan SAN Verification.
- Concurrency-safe Token-Bucket Rate Limiter tanpa dependensi pihak ketiga.
- Dedicated Internal Instrumentation Engine (pprof / health checks) pada Network Port Terpisah.
- Deterministic Graceful Drain.

```go
// server_production.go
package main

import (
	"context"
	"crypto/subtle"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"net/http/pprof"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// Config merepresentasikan parameter konfigurasi operational server
type Config struct {
	PublicAddr        string
	AdminAddr         string
	ClientCACertPath  string
	ServerCertPath    string
	ServerKeyPath     string
	RateLimitTokensPerSec float64
	RateLimitBurst    int
	DrainTimeout      time.Duration
}

// TokenBucketRateLimiter mengimplementasikan token bucket berbasis atomic sync
type TokenBucketRateLimiter struct {
	mu         sync.Mutex
	rate       float64
	capacity   float64
	tokens     float64
	lastRefill time.Time
}

func NewTokenBucketRateLimiter(rate float64, burst int) *TokenBucketRateLimiter {
	return &TokenBucketRateLimiter{
		rate:       rate,
		capacity:   float64(burst),
		tokens:     float64(burst),
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucketRateLimiter) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.lastRefill = now

	tb.tokens += elapsed * tb.rate
	if tb.tokens > tb.capacity {
		tb.tokens = tb.capacity
	}

	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}

// EnterpriseSecurityMiddleware menerapkan rate-limiting dan security response headers
func EnterpriseSecurityMiddleware(limiter *TokenBucketRateLimiter, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Defensive Headers
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
		w.Header().Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")

		if !limiter.Allow() {
			http.Error(w, `{"error":"TOO_MANY_REQUESTS","retry_after_ms":500}`, http.StatusTooManyRequests)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// SetupAdminMux membuat isolated HTTP mux untuk observability & profiling
func SetupAdminMux(adminUsername, adminPassword string) *http.ServeMux {
	mux := http.NewServeMux()

	// Guard admin routes dengan basic auth (Constant-time comparison)
	basicAuth := func(next http.HandlerFunc) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			user, pass, ok := r.BasicAuth()
			if !ok || subtle.ConstantTimeCompare([]byte(user), []byte(adminUsername)) != 1 ||
				subtle.ConstantTimeCompare([]byte(pass), []byte(adminPassword)) != 1 {
				w.Header().Set("WWW-Authenticate", `Basic realm="Restricted Instrumentation"`)
				http.Error(w, "Unauthorized", http.StatusUnauthorized)
				return
			}
			next(w, r)
		}
	}

	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"HEALTHY"}`))
	})

	// Secure pprof handlers
	mux.HandleFunc("/debug/pprof/", basicAuth(pprof.Index))
	mux.HandleFunc("/debug/pprof/cmdline", basicAuth(pprof.Cmdline))
	mux.HandleFunc("/debug/pprof/profile", basicAuth(pprof.Profile))
	mux.HandleFunc("/debug/pprof/symbol", basicAuth(pprof.Symbol))
	mux.HandleFunc("/debug/pprof/trace", basicAuth(pprof.Trace))

	return mux
}

// BuildStrictTLSConfig menyusun konfigurasi TLS 1.3 mTLS yang diperketat
func BuildStrictTLSConfig(caCertPEM, serverCertFile, serverKeyFile string) (*tls.Config, error) {
	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM([]byte(caCertPEM)) {
		return nil, errors.New("failed to append CA certificate to cert pool")
	}

	cert, err := tls.LoadX509KeyPair(serverCertFile, serverKeyFile)
	if err != nil {
		return nil, fmt.Errorf("unable to load server keypair: %w", err)
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		ClientCAs:    caCertPool,
		ClientAuth:   tls.RequireAndVerifyClientCert,
		MinVersion:   tls.VersionTLS13,
		CurvePreferences: []tls.CurveID{
			tls.X25519,
			tls.CurveP256,
		},
		CipherSuites: []uint16{
			tls.TLS_AES_128_GCM_SHA256,
			tls.TLS_AES_256_GCM_SHA384,
			tls.TLS_CHACHA20_POLY1305_SHA256,
		},
		VerifyPeerCertificate: func(rawCerts [][]byte, verifiedChains [][]*x509.Certificate) error {
			if len(verifiedChains) == 0 {
				return errors.New("no verified chains found")
			}
			peerCert := verifiedChains[0][0]
			// Strict Subject Alternative Name enforcement
			expectedSAN := "internal-worker.cluster.local"
			found := false
			for _, san := range peerCert.DNSNames {
				if san == expectedSAN {
					found = true
					break
				}
			}
			if !found {
				return fmt.Errorf("peer identity invalid: SAN '%s' not present", expectedSAN)
			}
			return nil
		},
	}, nil
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	// Public Router
	publicMux := http.NewServeMux()
	publicMux.HandleFunc("/api/v1/settlement", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"PROCESSED"}`))
	})

	rateLimiter := NewTokenBucketRateLimiter(5000, 10000) // 5000 RPS, burst 10000
	secureHandler := EnterpriseSecurityMiddleware(rateLimiter, publicMux)

	// Inisialisasi HTTP Server Produksi dengan Timeouts Eksplisit
	publicServer := &http.Server{
		Addr:              ":8443",
		Handler:           secureHandler,
		ReadHeaderTimeout: 2 * time.Second,  // Mencegah mitigasi Slowloris attack
		ReadTimeout:       5 * time.Second,  // Batas transfer body client
		WriteTimeout:      10 * time.Second, // Batas respons terkirim penuh
		IdleTimeout:       60 * time.Second, // Keep-alive connection idle boundary
		MaxHeaderBytes:    1 << 20,          // 1 MiB Header protection
	}

	// Observability Server (Admin internal - Bind ke localhost / Private NIC)
	adminServer := &http.Server{
		Addr:              "127.0.0.1:8081",
		Handler:           SetupAdminMux("admin_ops", "SuperSecretSREKey!"),
		ReadHeaderTimeout: 2 * time.Second,
		ReadTimeout:       3 * time.Second,
		WriteTimeout:      5 * time.Second,
	}

	// Channel untuk mengontrol error saat server binding
	serverErrors := make(chan error, 2)

	go func() {
		slog.Info("Starting admin profiling/health server", "addr", adminServer.Addr)
		if err := adminServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverErrors <- fmt.Errorf("admin server fatal failure: %w", err)
		}
	}()

	go func() {
		slog.Info("Starting hardened public server (Plain-HTTP fallback demonstration)", "addr", publicServer.Addr)
		// Pada arsitektur mTLS, gunakan publicServer.ListenAndServeTLS(cert, key)
		if err := publicServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverErrors <- fmt.Errorf("public server fatal failure: %w", err)
		}
	}()

	// Orchestrasi Graceful Shutdown
	shutdownSignal := make(chan os.Signal, 1)
	signal.Notify(shutdownSignal, syscall.SIGINT, syscall.SIGTERM)

	select {
	case err := <-serverErrors:
		slog.Error("Premature termination occurred", "error", err)
	case sig := <-shutdownSignal:
		slog.Warn("Termination signal received, launching deterministic drain pipeline", "signal", sig.String())

		// Grace Period Context (30 detik untuk drain requests aktif)
		drainCtx, cancelDrain := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancelDrain()

		var shutdownGroup sync.WaitGroup
		shutdownGroup.Add(2)

		go func() {
			defer shutdownGroup.Done()
			if err := publicServer.Shutdown(drainCtx); err != nil {
				slog.Error("Public server forced closure during drain", "error", err)
			}
		}()

		go func() {
			defer shutdownGroup.Done()
			if err := adminServer.Shutdown(drainCtx); err != nil {
				slog.Error("Admin server forced closure during drain", "error", err)
			}
		}()

		shutdownGroup.Wait()
		slog.Info("All servers drained safely. Process exited.")
	}
}
```

---

## 8. Real World Case Study: High-Throughput Payment Ingress (100K RPS)

### Latar Belakang Masalah
Sebuah gateway pembayaran memproses 100.000 RPS pada peak event Flash Sale. Service di-deploy pada Kubernetes (Node EKS: 64 Core, Container Limit: 4 CPU, 4 GiB Memori).

### Gejala Masalah di Produksi
1. **Latensi p99 Meledak**: Dari normal 15ms menjadi 2.400ms.
2. **Periodic OOM Kills**: Rata-rata 12 pod dihentikan kernel (`ExitCode 137`) setiap 10 menit.
3. **CPU Throttling**: Metrik `container_cpu_cfs_throttled_periods_total` mencapai 48%.

### Investigasi Mendalam (Root Cause Analysis)
- Go runtime melihat 64 Core hardware node. Default $P$ bernilai 64 (`GOMAXPROCS=64`), padahal CFS quota dibatasi sebesar 4 Core. Thread scheduling context switches saling berkompetisi menghabiskan jatah CPU periode CFS dalam fraksi mikrodetik pertama.
- Objek transient alokasi JSON unmarshaling menumpuk pada live heap. Sebelum `GOGC=100` mencapai trigger berikutnya, memori riil telah melampaui limit container 4 GiB, memicu OOM Killer.
- Profiling via endpoint `/debug/pprof` terbuka ke publik dan diakses oleh load balancer health checks, menambah GC lock overhead.

### Solusi Arsitektural & Perbaikan
1. **Dynamic CFS Adaptation**: Menginjeksi `go.uber.org/automaxprocs` pada initialization sequence. Scheduler Go runtime turun dari $P=64$ ke $P=4$.
2. **GC Bounds Hardening**: 
   ```bash
   GOMEMLIMIT=3600MiB # 90% dari 4GiB limit
   GOGC=80            # Agresif mentrigger GC lebih awal
   ```
3. **Zero-Allocation Deserialization**: Mengganti dynamic unmarshaling polymorphic payloads dengan static JSON streaming parsers atau deserialisasi menggunakan `easyjson`.
4. **Isolasi Network Observability**: Memindahkan `pprof` dan `/healthz` ke port loopback terpisah dengan proteksi mTLS/BasicAuth.

### Hasil (Post-Mortem Metrics)
- **CFS Throttling**: Turun drastis dari 48% menjadi 0.2%.
- **OOM Kills**: 0 incidents selama 48 jam masa flash sale.
- **Latency p99**: Stabil di 18.2ms pada 120.000 RPS.
- **Biaya Infrastruktur**: Node footprint berkurang 35% karena eliminasi overprovisioning CPU buffer.

---

## 9. Trade-offs Architecture Analysis

| Parameter Arsitektural | Keuntungan (Pros) | Biaya / Trade-off (Cons) | Dampak Latensi / Resource |
| :--- | :--- | :--- | :--- |
| **Penyetelan `GOMEMLIMIT` Agresif (<80% cgroup)** | Menjamin keamanan absolut dari kernel OOM kills. | CPU thrashing dapat terjadi jika live heap mendekati batas bawah secara berkelanjutan. | CPU spike hingga 50% kapasitas untuk siklus garbage collector. |
| **Strict mTLS Per Request (TLS 1.3)** | Mengamankan transmisi data end-to-end (Zero-Trust) & integritas mutual identity. | Handshake overhead kriptografi asymmetric (ECDH computation) & pertukaran sertifikat. | Penambahan latensi 1.5ms - 4ms pada handshake baru (dapat dimitigasi via Session Resumption). |
| **Bounded Worker Pools vs Goroutines-Per-Request** | Menjamin memori footprint terprediksi (*predictable memory usage*), mencegah exhaust CPU. | Membutuhkan buffering antrean; risiko request rejection saat pool jenuh (*backpressure*). | Penambahan queue latency saat burst, namun p99/p999 tetap terkontrol secara deterministik. |
| **Distroless Container vs Standard Alpine Base** | Menghilangkan package manager (`apk`), shell (`sh`), dan CVE tools (Serangan RCE tumpul). | Debugging interaktif di staging/prod menjadi kompleks (tidak ada tool shell built-in). | Tidak ada runtime latency overhead; ukuran container turun hingga 90%. |

---

## 10. Common Mistakes & Troubleshooting

### Skenario 1: Goroutine Leak pada Resiliency Network Client
* **Kode Buruk**:
  ```go
  func executeCall(ctx context.Context) error {
      ch := make(chan error) // Unbuffered channel!
      go func() {
          ch <- client.DoCall() // Jika context timeout tercapai, tidak ada yang membaca ch!
      }()
      select {
      case <-ctx.Done():
          return ctx.Err() // Goroutine di atas tertahan selamanya di memory (Leak)
      case err := <-ch:
          return err
      }
  }
  ```
* **Koreksi**: Gunakan buffer channel berukuran 1 (`make(chan error, 1)`), sehingga background goroutine dapat meletakkan error dan di-garbage collect secara normal meskipun `ctx.Done()` lebih dulu dieksekusi.

### Skenario 2: HTTP Default Client Tanpa Explicit Timeout
* **Masalah**: Penggunaan `http.Get()` atau `&http.Client{}` tanpa konfigurasi timeout menyebabkan koneksi menggantung tanpa batas (*infinite hang*) saat remote gateway mengalami packet drop tingkat TCP.
* **Koreksi**: Wajib mengonfigurasi Transport timeouts:
  ```go
  var secureClient = &http.Client{
      Timeout: 10 * time.Second,
      Transport: &http.Transport{
          DialContext: (&net.Dialer{
              Timeout:   2 * time.Second,
              KeepAlive: 30 * time.Second,
          }).DialContext,
          TLSHandshakeTimeout:   2 * time.Second,
          ResponseHeaderTimeout: 3 * time.Second,
          ExpectContinueTimeout: 1 * time.Second,
          MaxIdleConns:          1000,
          MaxIdleConnsPerHost:   100,
          IdleConnTimeout:       90 * time.Second,
      },
  }
  ```

### Skenario 3: Missing ReadHeaderTimeout Memicu Serangan Slowloris
* **Masalah**: `http.Server{ReadTimeout: 5 * time.Second}` mulai menghitung waktu setelah request header pertama dibaca secara tuntas. Penyerang dapat mengirimkan header 1 byte per 4 detik secara berkelanjutan tanpa pernah menyelesaikan header block, menguras connection pool webserver.
* **Koreksi**: Set `ReadHeaderTimeout` secara spesifik (misal: 2 detik).

---

## 11. Best Practices (Production Checklist)

### Security Hardening
- [ ] Non-root execution: Container berjalan dengan UID default 65534 atau 65532 (bukan root).
- [ ] Binary dibangun dengan: `CGO_ENABLED=0 go build -trimpath -ldflags="-s -w"`.
- [ ] Static CVE scanning terjadwal via pipeline menggunakan `govulncheck ./...`.
- [ ] Seluruh endpoint TLS mengaktifkan `MinVersion: tls.VersionTLS13`.
- [ ] Sensitive headers dibersihkan dari structured logs (misal: `Authorization`, `Cookie`, `X-Api-Key`).

### Runtime & System Reliability
- [ ] Library `go.uber.org/automaxprocs` di-import pada `main.go`.
- [ ] Parameter `GOMEMLIMIT` terkonfigurasi pada 85-90% batas limit cgroup container.
- [ ] HTTP server mendefinisikan `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, dan `IdleTimeout`.
- [ ] Graceful shutdown mendengarkan signal `SIGTERM` dan `SIGINT` dengan context timeout eksplisit.
- [ ] Profiling runtime (`net/http/pprof`) diisolasi pada port internal/loopback dengan proteksi BasicAuth atau mTLS.

---

## 12. Hands-on Practice: Building a Hardened Microservice

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`.

### Struktur Direktori:
```
hands-on/m02/
├── Dockerfile.hardened
├── Makefile
├── go.mod
├── go.sum
└── main.go
```

### Langkah 1: Inisialisasi Modul
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init enterprise-hardened-svc
go get go.uber.org/automaxprocs
```

### Langkah 2: Buat File `main.go`
Salin kode dari **Seksi 7.2 (Practical Example)** ke file `hands-on/m02/main.go`.

### Langkah 3: Siapkan `Dockerfile.hardened` (Multi-stage Distroless)
```dockerfile
# Multi-stage hardened build pipeline
# Stage 1: Build binary
FROM golang:1.22-alpine AS builder

WORKDIR /build

RUN apk add --no-cache ca-certificates tzdata

COPY go.mod go.sum ./
RUN go mod download && go mod verify

COPY . .

# Compile binary secara statis, hilangkan debug symbols & path trace
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -trimpath \
    -ldflags="-s -w -extldflags '-static'" \
    -o hardened-svc main.go

# Stage 2: Minimal Distroless Run Container
FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

# Ambil binary dari builder stage
COPY --from=builder /build/hardened-svc /app/hardened-svc
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Jalankan menggunakan non-root user bawaan distroless (UID 65532)
USER nonroot:nonroot

EXPOSE 8443 8081

ENTRYPOINT ["/app/hardened-svc"]
```

### Langkah 4: Siapkan `Makefile` untuk Otomatisasi
```makefile
.PHONY: audit build run test-load clean

audit:
	go vet ./...
	@which govulncheck > /dev/null || go install golang.org/x/vuln/cmd/govulncheck@latest
	govulncheck ./...

build: audit
	docker build -t enterprise-hardened-svc:v1 -f Dockerfile.hardened .

run: build
	docker run --rm \
		--name hardened-svc-instance \
		-p 8443:8443 -p 8081:8081 \
		-m 512m --cpus 1.5 \
		-e GOMEMLIMIT=460MiB \
		enterprise-hardened-svc:v1

test-load:
	@echo "Testing Rate Limiting Defense..."
	for i in {1..20}; do curl -i -k http://localhost:8443/api/v1/settlement; done

test-admin:
	@echo "Testing Authenticated Metrics Endpoint..."
	curl -u admin_ops:SuperSecretSREKey! http://localhost:8081/debug/pprof/heap
```

### Langkah 5: Eksekusi dan Pengujian
Jalankan instruksi berikut pada terminal Anda:
```bash
make audit
make run
```
Pada terminal lain:
```bash
make test-load
make test-admin
```

---

## 13. Exercises

### Level Easy
1. Modifikasi file `main.go` pada praktikum untuk menambahkan metrik penghitung (*counter*) sederhana menggunakan `sync/atomic` yang melacak berapa kali request ditolak (*HTTP 429 Too Many Requests*) oleh middleware rate limiter.
2. Paparkan metrik atomic counter tersebut pada endpoint `/healthz` internal di admin server.

### Level Medium
1. Kembangkan dynamic configuration loader: Jika file konfigurasi sertifikat TLS di-update di sistem file, server harus secara mulus memuat ulang (*reload*) sertifikat baru melalui fungsi `tls.Config.GetCertificate` tanpa merestart proses service atau memutuskan koneksi TCP yang sedang aktif.

### Level Hard
1. Buat mekanisme **Adaptive Concurrency Limiter (Vegas Algorithm)** sebagai pengganti Token-Bucket rate limiter:
   - Hitung moving average latency per 100 request.
   - Jika latensi p90 meningkat melewati limit toleransi (misal 50ms), turunkan jumlah alokasi worker concurrent request yang diperbolehkan secara dinamis untuk melindungi resource database dari degradasi bertingkat (*cascading failure*).

---

## 14. Challenge

### Studi Kasus: The Multi-Tenant Poison Pill Profiler Incident

**Deskripsi Kasus:**
Sebuah platform Core Banking microservice berbasis Go mengalami crash misterius setiap hari Selasa pukul 03.00 pagi. Pada log container hanya tertulis pesan singkat:
`fatal error: runtime: out of memory` / `signal: killed`.

Karakteristik Environment:
- Cluster: Kubernetes v1.28 di atas AWS EKS.
- Pod Limit: Memory 2 GiB, Request 2 GiB. CPU Limit 4, Request 4.
- CronJob internal mengeksekusi continuous automated dynamic load test sebesar 20.000 RPS tepat pada jam tersebut.
- SRE mengaktifkan profiling remote yang mengambil heap dump secara berkala setiap 5 menit menggunakan skrip internal yang memanggil `curl http://service:8081/debug/pprof/heap?debug=1`.

**Misi Anda:**
1. Desain eksperimen untuk mereplikasi penyebab runtuhnya memory space ini secara lokal (Hint: Hubungan antara profiling alloc/heap serialization overhead, live objects memory, dan OOM Killer threshold).
2. Tuliskan patch arsitektur Go yang:
   - Menerapkan *Memory Circuit Breaker*: Jika memori alokasi mencapai 85% dari container boundary, endpoint pprof profiling otomatis memutus koneksi dan mengembalikan HTTP 503 agar proses profiling tidak menjadi pemicu akhir OOM kill.
   - Mengalihkan dumping memory profil dari endpoint HTTP ke streaming terkompresi lokal atau disk-buffered chunks yang aman dari overhead buffer alokasi runtime heap.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Apa tujuan utama runtime Go memperkenalkan mekanisme `GOMEMLIMIT`?**
   - A. Menghapus kebutuhan pengembang untuk membersihkan pointer secara manual.
   - B. Membatasi memory leak akibat Goroutine tak tertutup.
   - C. Mencegah kernel Linux menghentikan proses container (OOM Kill) melalui peningkatan pacing Garbage Collector secara adaptif.
   - D. Mempercepat kompilasi binary pada build pipeline.

2. **Mengapa library `automaxprocs` sangat krusial saat mendeploy aplikasi Go di container Kubernetes?**
   - A. Mencegah race conditions pada channel.
   - B. Menyesuaikan jumlah thread Go runtime ($P$) dengan CFS CPU quota container guna mengeliminasi kernel CPU throttling.
   - C. Mengurangi footprint ukuran file binary.
   - D. Mengubah Go runtime menjadi asynchronous event loop seperti Node.js.

3. **Apa kegunaan flag `-trimpath` pada proses kompilasi binary Go produksi?**
   - A. Mengoptimasi kecepatan eksekusi algoritma loop.
   - B. Menghilangkan metadata filesystem internal/lokal mesin pengembang dari binary untuk mencegah kebocoran informasi arsitektur direktori.
   - C. Mengaktifkan optimasi CGO dynamic linking.
   - D. Menghapus baris kode komentar.

4. **Apa risiko keamanan mendasar jika mengekspos endpoint `/debug/pprof/` tanpa otentikasi ke public network?**
   - A. Database otomatis drop koneksi.
   - B. Penyerang dapat melihat dump heap memori yang berpotensi berisi API keys, data PII pengguna, serta memicu serangan Denial-of-Service via CPU profiling overhead.
   - C. Container langsung kehilangan IP address.
   - D. Kompiler Go mengubah source code menjadi insecure.

5. **Apa fungsi dari parameter `ReadHeaderTimeout` pada struct `http.Server`?**
   - A. Membatasi waktu pembacaan body request.
   - B. Mengatur batas koneksi TCP idle sebelum ditutup.
   - C. Memitigasi serangan Slowloris dengan menetapkan batas waktu maksimal bagi client untuk mengirim seluruh HTTP header request.
   - D. Mengoptimasi decoding compression GZIP.

---

### Bagian 2: Intermediate (5 Pertanyaan)

6. **Pada konfigurasi TLS 1.3 di Go, mengapa kita tidak perlu mengonfigurasi parameter `CipherSuites` seperti pada TLS 1.2?**
   - A. Karena TLS 1.3 tidak menggunakan cipher encryption.
   - B. Di Go runtime, konfigurasi `CipherSuites` pada TLS 1.3 telah didefinisikan secara internal dengan standar algoritma modern yang aman dan urutannya tidak dapat dimanipulasi oleh konfigurasi manual demi alasan keamanan.
   - C. Cipher suite TLS 1.3 sepenuhnya didelegasikan kepada OS kernel tanpa campur tangan Go runtime.
   - D. TLS 1.3 hanya mendukung algoritma RSA murni.

7. **Perhatikan skenario alokasi: Live heap aplikasi adalah 600 MiB, `GOMEMLIMIT` diset ke 800 MiB, dan `GOGC=100`. Kapan GC cycle berikutnya akan dieksekusi oleh Go runtime?**
   - A. Saat alokasi mencapai 1200 MiB.
   - B. Saat alokasi mencapai 800 MiB secara ketat.
   - C. GC akan terpicu sebelum mencapai batas 800 MiB (GOMEMLIMIT), mengabaikan target GOGC 100 (1200 MiB) karena soft memory limit lebih diprioritaskan untuk menghindari OOM.
   - D. Tepat pada saat memori mencapai 601 MiB.

8. **Mengapa pemanggilan fungsi `subtle.ConstantTimeCompare` wajib digunakan untuk memvalidasi token otentikasi atau kredensial?**
   - A. Memiliki performa algoritma $O(1)$ paling kencang dibandingkan operator string `==`.
   - B. Mengeliminasi celah kerentanan *Timing Attacks*, di mana penyerang dapat menebak isi token karakter per karakter berdasarkan durasi eksekusi perbandingan string biasa.
   - C. Mengompresi ukuran token di memori.
   - D. Mencegah string ter-escape ke heap memory.

9. **Apa konsekuensi fatal dari kegagalan menutup resource response body (`resp.Body.Close()`) pada HTTP client client Go?**
   - A. Compiler mengeluarkan warning saat build.
   - B. Terjadi socket file descriptor leak dan underlying TCP connection tidak dapat digunakan kembali (*reused*) oleh `http.Transport` connection pool.
   - C. Request secara otomatis dibatalkan oleh DNS resolver.
   - D. Port 80 otomatis tertutup secara global.

10. **Apa perbedaan fungsional antara `distroless` image dan `alpine` image pada stage runtime container Go?**
    - A. Distroless memiliki package manager `apt`, sedangkan Alpine menggunakan `apk`.
    - B. Distroless hanya memuat binary aplikasi beserta runtime dependency minimal tanpa shell, OS package manager, atau utilitas Unix standar, memperkecil attack surface jika terjadi eksploitasi remote code injection.
    - C. Alpine berukuran lebih kecil daripada Distroless.
    - D. Distroless memaksa binary dijalankan menggunakan root user.

---

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario A:**
    Sebuah sistem payment menerima spike request 50.000 RPS secara mendadak. CPU container melonjak menjadi 100%, dan pod mulai unresponsive. Metrik pprof menunjukkan goroutine scheduler menghabiskan 65% waktu CPU pada siklus `runtime.gcBgMarkWorker`. Parameter yang terpasang saat ini adalah:
    Container RAM: 1 GiB.
    `GOMEMLIMIT=980MiB`.
    `GOGC=100`.
    *Apa analisis masalah dan tindakan mitigasi instan yang wajib dilakukan?*

12. **Skenario B:**
    Microservice `Auth-Svc` memvalidasi identitas caller microservice `Payment-Svc` menggunakan TLS 1.3 mTLS. Suatu hari, attacker berhasil mencuri Private Key dan Certificate milik `Report-Svc` (yang dikeluarkan oleh CA internal yang sama). Attacker memalsukan request ke `Auth-Svc` menggunakan cert tersebut dan request berhasil diproses.
    *Celah arsitektur apa yang terlewatkan pada implementasi `crypto/tls` di server, dan bagaimana cara memperbaikinya menggunakan callback Go runtime?*

13. **Skenario C:**
    Aplikasi microservice Go menerapkan Graceful Shutdown dengan timeout 30 detik. Namun saat Kubernetes mengirimkan event rolling upgrade (mengirim `SIGTERM`), pod langsung dimatikan paksa setelah 2 detik, menyebabkan ratusan koneksi transaksi drop dan menghasilkan error HTTP 502 Bad Gateway pada layer Ingress/Load Balancer. Log aplikasi menunjukkan bahwa proses shutdown Go sudah berjalan sesuai skenario.
    *Di mana letak ketidaksesuaian (*mismatch*) konfigurasi antara Go runtime lifecycle dan spesifikasi Pod Kubernetes?*

---

### Kunci Jawaban & Evaluasi

#### Bagian 1 & 2
1. **C** — Mencegah kernel OOM killer melalui GC pacing adaptif berdasarkan batas memori yang ditentukan.
2. **B** — Menghindari alokasi thread Go scheduler berlebih yang melampaui Linux cgroup CFS bandwidth limit.
3. **B** — Menghilangkan path direktori lokal mesin pengembang agar tidak terekspos di stack traces panic.
4. **B** — Mencegah kebocoran data sensitif (PII/Token) yang ada di heap memori dan mencegah DoS profiling.
5. **C** — Menghentikan client jahat yang sengaja menahan proses transfer HTTP headers secara lambat (Slowloris).
6. **B** — TLS 1.3 mengotomasi cipher modern demi keamanan; cipher suites konfigurasi manual diprioritaskan untuk backward compatibility TLS 1.2.
7. **C** — GC pacing akan memprioritaskan trigger terendah antara persentase `GOGC` dan ambang batas `GOMEMLIMIT`.
8. **B** — Menghindari serangan side-channel analisis waktu respon (*timing side-channel attacks*).
9. **B** — Leak socket file descriptor dan koneksi TCP pool tidak bisa didaur ulang.
10. **B** — Distroless memangkas attack surface secara drastis dengan mengeliminasi shell dan paket utilitas Unix lainnya.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis Skenario A:**
    Aplikasi mengalami fenomena **GC Thrashing**. Selisih antara `GOMEMLIMIT` (980 MiB) dan batas cgroup (1 GiB) terlalu tipis (hanya sisa 20 MiB / ~2%). Ketika live memori berada di atas 900 MiB, Go runtime secara agresif mengerahkan worker goroutine (`runtime.gcBgMarkWorker`) hingga batas maksimal 50% CPU untuk membersihkan memori setiap mikrodetik demi mencegah crash OOM.
    *Tindakan*: 
    1. Naikkan container memory limit atau turunkan `GOMEMLIMIT` ke nilai konservatif (misal: 800 MiB / 80%).
    2. Turunkan nilai `GOGC` secara adaptif atau perbaiki memory pooling menggunakan `sync.Pool` untuk transient unmarshal structs.
12. **Analisis Skenario B:**
    Server mTLS hanya memverifikasi keabsahan sertifikat terhadap root CA (`tls.RequireAndVerifyClientCert`), namun gagal memvalidasi **Otorisasi Identitas Peer**.
    *Tindakan*:
    Wajib menerapkan custom verification callback pada `tls.Config.VerifyPeerCertificate`. Pada callback ini, baca x509 SAN (*Subject Alternative Name*) atau Common Name peer dan pastikan cert yang memanggil memang memiliki identitas service name yang diizinkan (misal: `payment-svc.cluster.local`), tolak (*return error*) jika cert milik service lain seperti `report-svc`.
13. **Analisis Skenario C:**
    Terjadi dua kemungkinan mismatch:
    1. Konfigurasi `terminationGracePeriodSeconds` di manifest Pod Kubernetes lebih kecil (default: 30s) atau Ingress controller masih merutekan paket ke pod karena endpoint termination lifecycle belum sinkron.
    2. Saat container Go menerima `SIGTERM`, server langsung menutup HTTP Listener (`server.Shutdown`), padahal Ingress controller butuh jeda beberapa detik untuk mencabut IP Pod dari target backends.
    *Solusi*: Sisipkan *pre-stop sleep* atau `time.Sleep(3-5 * time.Second)` sebelum memanggil `server.Shutdown()` pada Go signal handler, atau gunakan lifecycle hook `preStop: exec: command: ["sleep", "5"]` pada manifest Kubernetes agar ingress berhenti mengirim trafik baru sebelum listener ditutup.

---

## 16. Summary

Mengoperasikan Go pada arsitektur produksi kelas enterprise membutuhkan integrasi holistik antara runtime tuning, security primitives, dan operational observability:
1. **Runtime Alignment**: Go tidak beroperasi di ruang hampa. Di dalam container Linux, runtime scheduler dan garbage collector harus diselaraskan secara eksplisit melalui `GOMEMLIMIT` dan `automaxprocs` guna menjamin kestabilan p99 dan mencegah OOM kills.
2. **Defensive Zero-Trust**: Tidak ada internal network yang aman. Implementasi TLS 1.3 mTLS dengan otentikasi identitas berbasis SAN, timeout koneksi menyeluruh untuk memitigasi serangan Slowloris, serta constant-time comparison adalah standar wajib arsitektur modern.
3. **Resiliency by Design**: Menerapkan rate limiting mandiri dan isolasi port antara public ingress dengan internal administrative tools memastikan sistem mampu bertahan menghadapi lonjakan trafik abnormal tanpa mengorbankan stabilitas node.
4. **Supply Chain Hardening**: Binary statis tanpa CGO yang dibungkus dalam container distroless non-root meminimalkan celah eksploitasi keamanan dari fase build hingga runtime eksekusi.