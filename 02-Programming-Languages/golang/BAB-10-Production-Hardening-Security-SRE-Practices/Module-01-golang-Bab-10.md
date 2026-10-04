# Bab 10 Module 01: Production Hardening, Security & SRE Practices

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Pemrograman Backend & Infrastruktur Skala Besar
* **Kategori**: `02-Programming-Languages`
* **Modul**: Bab 10 Module 01 — Production Hardening, Security & SRE Practices
* **Target Tingkat Kemahiran**: Advanced / Senior Backend Engineer / Site Reliability Engineer (SRE)
* **Prasyarat**: 
  * Pemahaman mendalam tentang *Goroutine*, *Channels*, dan sinkronisasi primitif (`sync.Mutex`, `sync.WaitGroup`).
  * Penguasaan antarmuka `net/http`, penanganan `context.Context`, dan siklus hidup koneksi I/O.
  * Pengalaman operasional dasar dengan Linux OS (sinyal sistem/POSIX, *cgroups*, namespaces, socket networking).
* **Estimasi Waktu Belajar**: 120–180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menerapkan Pola Graceful Shutdown Tingkat Lanjut**: Mengimplementasikan mekanisme intersepsi sinyal OS (`SIGINT`, `SIGTERM`) dengan drain koneksi aktif, timeout deterministik, serta pembersihan dependensi (basis data, broker pesan) tanpa kehilangan data transaksi (*in-flight requests*).
2. **Mengamankan dan Memperkeras HTTP Stack (`net/http`)**: Mengkonfigurasi parameter timeout kernel dan aplikasi (`ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout`, `MaxHeaderBytes`) untuk memitigasi serangan eksploitatif seperti *Slowloris* dan *denial-of-service* berbasis alokasi buffer.
3. **Mengoptimalkan Runtime Go pada Lingkungan Terkontainerisasi (Kubernetes/cgroups)**: Memahami dan mengkonfigurasi `GOMAXPROCS`, `GOMEMLIMIT`, dan `GOGC` untuk mencegah terjadinya *Out-Of-Memory (OOM) Killer* serta perebutan thread CPU di lingkungan virtual.
4. **Membangun Pertahanan Bertingkat (Defense in Depth)**: Menerapkan praktik *least-privilege runtime*, eksekusi biner Go pada image kontainer minimal (*scratch/distroless*), dan mitigasi kebocoran memori sensitif.
5. **Mendesain Observabilitas Terstandarisasi SRE**: Memadukan metrik *Golden Signals* SRE (Latency, Traffic, Errors, Saturation), implementasi *Liveness/Readiness/Startup Probes*, serta penggunaan structured logging berperforma tinggi menggunakan pustaka standar `log/slog`.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam fase pengembangan lokal (*local development*), runtime Go sangat memaafkan kelalaian konfigurasi: `http.ListenAndServe(":8080", nil)` bekerja instan tanpa cela, koneksi jaringan lokal tidak mengalami jitter, dan pembatalan proses secara tiba-tiba (`Ctrl+C`) tidak membawa dampak finansial langsung.

Namun, di lingkungan produksi terdistribusi:
* **Jaringan Selalu Tidak Andal**: Klien dapat memutus koneksi di tengah transmisi data, menahan transmisi header tanpa batas (*Slowloris*), atau mengalami latensi ratusan milidetik. Default Go yang membiarkan timeout bernilai nol (`0 = no timeout`) adalah kerentanan keamanan kritis.
* **Proses Adalah Fana (*Ephemeral*)**: Pod Kubernetes dan container orchestration menjadwalkan ulang, mematikan, dan melakukan deployment baru setiap saat. Aplikasi Go harus memandang kematian proses sebagai kejadian rutin yang harus ditangani secara deterministik, bukan anomali.
* **Runtime Go vs Kernel cgroups**: Go Runtime mengasumsikan ia menguasai seluruh node bare-metal kecuali dikonfigurasi secara eksplisit. Go scheduler (`runtime.NumCPU()`) melihat total core host fisik, bukan kuota cgroup CPU. Tanpa penyelarasan, Go akan menghasilkan ribuan thread OS yang memicu *context switching overhead* tinggi dan penurunan performa drastis.

```
       [ Mindset Lokal ]                     [ Mindset SRE / Produksi ]
┌──────────────────────────────┐       ┌──────────────────────────────────────┐
│  • Default timeout: 0 (OK)   │  vs   │  • Zero-timeout = DoS Vulnerability  │
│  • Kill process = Exit(0)    │       │  • Graceful Drain & Signal Trapping  │
│  • Multi-core = All machine  │       │  • Bound to cgroup quota (GOMAXPROCS)│
│  • Memory = Infinite         │       │  • Bound to hard limits (GOMEMLIMIT) │
└──────────────────────────────┘       └──────────────────────────────────────┘
```

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme shutdown terkontrol dan penanganan request dalam arsitektur HTTP Go yang telah diperkeras:

```
[Klien / Load Balancer]
        │
        │ HTTP Request (TLS/TCP)
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ HTTP Server Network Layer (Hardened net/http)                           │
│  - MaxHeaderBytes: 1MB                                                 │
│  - ReadHeaderTimeout: 2s (Mitigasi Slowloris)                          │
│  - ReadTimeout: 5s                                                     │
│  - WriteTimeout: 10s                                                   │
│  - IdleTimeout: 120s                                                   │
└────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Pipeline Middleware (SRE Reliability Engine)                           │
│  - Rate Limiter (Token Bucket)                                         │
│  - Concurrency Limiter / Circuit Breaker                               │
│  - Tracing & Structured Logging (log/slog)                             │
│  - Metric Collector (Prometheus Latency/Status Histograms)             │
└────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Core Business Logic Handler (Context Bound)                            │
│  - context.WithTimeout(req.Context(), 3s)                              │
│  - DB Pool / Downstream RPC with Circuit Breakers                      │
└────────────────────────────────────────────────────────────────────────┘

========================= SIKLUS HIDUP PENGHENTIAN (SHUTDOWN) =========================

Kernel OS                      Go Runtime Process               Active Request Pool
    │                                  │                                 │
    │ ─── SIGTERM/SIGINT ────────────> │ Intersepsi via signal.NotifyContext
    │                                  │                                 │
    │                                  │ Set State: NOT READY (503)      │
    │                                  │ (Kubernetes Probe Draining)     │
    │                                  │                                 │
    │                                  │ Server.Shutdown(ctxTimeout)     │
    │                                  │ ──────────────────────────────> │
    │                                  │ Tutup Listeners (Stop Accept)   │
    │                                  │ Tunggu Active Goroutines Selesai│
    │                                  │                                 │ <── In-flight Requests OK
    │                                  │                                 │
    │                                  │ Tutup Koneksi DB / Broker       │
    │                                  │ Flush Log Buffers               │
    │                                  │ Exit Code 0                     │
    ▼                                  ▼                                 ▼
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Timeout `http.Server`
Untuk memahami hardening, kita harus membedah batas tanggung jawab setiap field timeout di dalam `http.Server`:

* **`ReadHeaderTimeout`**: Waktu maksimal yang dialokasikan untuk membaca header request sejak koneksi TCP diterima. Ini adalah pertahanan utama terhadap serangan *Slowloris* (penyerang mengirim header byte per byte dengan interval lambat untuk menghabiskan pool goroutine).
* **`ReadTimeout`**: Mencakup seluruh durasi pembacaan request, mulai dari penerimaan koneksi hingga pembacaan request body selesai.
* **`WriteTimeout`**: Mencakup rentang waktu dari akhir pembacaan request header hingga penulisan response body selesai dieksekusi.
* **`IdleTimeout`**: Durasi maksimum koneksi *keep-alive* dibiarkan menganggur sebelum ditutup paksa oleh server.
* **`MaxHeaderBytes`**: Mengontrol jumlah alokasi byte maksimum yang dibaca runtime ke memori sebelum memblokir request yang berlebihan (`431 Request Header Fields Too Large`).

### 2. Pola Penutupan Terstruktur (*Graceful Shutdown Pipeline*)
Fungsi `server.Shutdown(ctx)` internal Go bekerja dengan mekanisme spesifik:
1. Menutup semua listener jaringan aktif (`net.Listener.Close()`), sehingga server menolak koneksi TCP baru.
2. Mengubah status semua koneksi idle menjadi ditutup segera.
3. Menandai semua koneksi aktif ke status koneksi yang menunggu penyelesaian.
4. Menunggu hingga seluruh koneksi aktif menyelesaikan daur siklus HTTP handler-nya atau hingga context pembatalan mencapai batas `ctx.Done()`.

### 3. Sinkronisasi OS Signal dan Trap
Pada POSIX, proses Linux berkomunikasi dengan runtime melalui sinyal integer. Kubernetes mengirimkan `SIGTERM` saat menghentikan Pod, diikuti masa tunggu `terminationGracePeriodSeconds` (default: 30 detik), sebelum menembakkan `SIGKILL` (yang tidak dapat ditangkap dan langsung membunuh proses di tingkat kernel). Handler shutdown Go harus mampu menangkap `syscall.SIGTERM` dan `os.Interrupt` (`syscall.SIGINT`), lalu memfasilitasi pelepasan sumber daya sebelum `SIGKILL` dieksekusi.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Memory Limiter & GC Target: `GOMEMLIMIT` dan `GOGC`
Sebelum Go 1.19, strategi Garbage Collector (GC) dikontrol hampir secara eksklusif oleh variabel lingkungan `GOGC` (default `100`). Rasio ini mendikte bahwa GC akan dipicu ketika heap memory tumbuh sebesar 100% dari ukuran live heap sebelumnya.

**Masalah di Kubernetes (OOMKills)**:
Misalkan sebuah container memiliki kuota RAM cgroup sebesar 1 GiB. 
Jika live heap adalah 400 MiB, dengan `GOGC=100`, GC baru akan dieksekusi saat alokasi mencapai 800 MiB. Jika terdapat lonjakan alokasi transien sebesar 250 MiB, total alokasi memuncak ke 1050 MiB. Kernel Linux cgroup langsung membunuh container secara mendadak melalui event `OOMKilled` (Exit code 137).

**Solusi: `GOMEMLIMIT` (Sejak Go 1.19)**:
`GOMEMLIMIT` menetapkan batas memori *soft target* untuk seluruh runtime Go, termasuk alokasi heap dan memori internal runtime. 
* Ketika alokasi mendekati batas `GOMEMLIMIT`, frekuensi GC dinaikkan secara otomatis oleh runtime untuk mencegah konsumsi memori melewati batas ambang container.
* **Rekomendasi SRE**: Set `GOMEMLIMIT` pada 80-90% dari batas memori cgroup/container Pod. Sisakan 10-20% untuk sistem operasi, thread stacks, dynamic linking, dan alokasi non-Go.

### CPU Quota Synchronization: `GOMAXPROCS` & `automaxprocs`
Go Runtime mendistribusikan komputasi goroutine menggunakan model penjadwalan $M:N$ (Go routines $M$ dipetakan ke OS Threads $N$). Defaultnya, $N$ bernilai `runtime.NumCPU()`.

Pada node Kubernetes dengan 64 physical cores di mana sebuah Pod hanya dialokasikan `limit: 2000m` (2 core):
* `runtime.NumCPU()` tetap membaca angka **64**.
* Go runtime membuat 64 thread OS aktif dan 64 run-queue processor ($P$).
* Karena CFS (*Completely Fair Scheduler*) Linux membatasi eksekusi hanya sebesar 2 core per kuantum waktu, thread-thread tersebut berebut CPU (*thread thrashing*), menghasilkan context-switching masif dan CFS quota throttling (latensi membengkak tajam).
* Menggunakan integrasi `uber-go/automaxprocs` atau mengeset `runtime.GOMAXPROCS` secara eksplisit sesuai alokasi CFS cgroup quota adalah kewajiban mutlak pada lingkungan *cloud-native*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi dasar HTTP Server yang telah di-hardening terhadap serangan jaringan dasar dan dilengkapi graceful shutdown terstruktur.

```go
// Package main menyediakan server HTTP hardened standar industri.
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func run() error {
	// Konfigurasi Structured Logging
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	// Inisialisasi Handler HTTP
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"healthy"}`))
	})

	mux.HandleFunc("/api/v1/work", func(w http.ResponseWriter, r *http.Request) {
		// Simulasikan pemrosesan beban kerja
		select {
		case <-time.After(2 * time.Second):
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte(`{"result":"completed"}`))
		case <-r.Context().Done():
			logger.Warn("Client membatalkan koneksi sebelum selesai", "error", r.Context().Err())
			return
		}
	})

	// Server Hardening Configuration
	srv := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadHeaderTimeout: 2 * time.Second,  // Melindungi dari Slowloris
		ReadTimeout:       5 * time.Second,  // Batas total pembacaan body
		WriteTimeout:      10 * time.Second, // Batas waktu penulisan response
		IdleTimeout:       120 * time.Second,// Keep-alive timeout
		MaxHeaderBytes:    1 << 20,          // 1 MB batas maksimal header
	}

	// Channel untuk menangkap error fatal startup server
	serverErrors := make(chan error, 1)

	// Jalankan server di goroutine terpisah
	go func() {
		logger.Info("Memulai HTTP server", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverErrors <- fmt.Errorf("kesalahan pada listener server: %w", err)
		}
	}()

	// Menangkap sinyal OS untuk Graceful Shutdown
	shutdownCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Menunggu sinyal interupsi atau error internal
	select {
	case err := <-serverErrors:
		return fmt.Errorf("server mengalami kegagalan fatal: %w", err)
	case <-shutdownCtx.Done():
		logger.Info("Sinyal terminasi diterima, memulai graceful shutdown...")
	}

	// Alokasikan deadline maksimum untuk proses draining (misal 15 detik)
	drainCtx, cancelDrain := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancelDrain()

	// Eksekusi shutdown srv
	if err := srv.Shutdown(drainCtx); err != nil {
		// Paksa penutupan jika timeout draining terlampaui
		_ = srv.Close()
		return fmt.Errorf("gagal melakukan shutdown secara bersih: %w", err)
	}

	logger.Info("Server berhasil dimatikan secara elegan tanpa memutus transaksi aktif")
	return nil
}

func main() {
	if err := run(); err != nil {
		slog.Error("Aplikasi berhenti secara tidak normal", "error", err)
		os.Exit(1)
	}
	os.Exit(0)
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode implementasi fundamental di atas:

1. **Baris 24-26 (`slog.NewJSONHandler`)**: Format log terstruktur ke `os.Stdout` dalam format JSON adalah standar mutlak pada kontainer Cloud Native/Kubernetes agar agregator log (seperti Fluentd, Vector, Promtail) dapat mem-parsing field tanpa overhead regex.
2. **Baris 48-54 (`&http.Server{...}`)**:
   * `ReadHeaderTimeout: 2 * time.Second`: Memutus koneksi klien yang mengirimkan header byte per byte secara perlahan. Menolak penyerang sebelum mereka membanjiri pool memori kernel TCP.
   * `MaxHeaderBytes: 1 << 20`: Mengamankan buffer memori Go agar klien tidak dapat mengirim header ratusan megabyte yang memicu alokasi memori berlebih.
   * `IdleTimeout: 120 * time.Second`: Memastikan koneksi idle TCP pada load balancer di-drain secara berkala untuk menjaga akurasi pool koneksi.
3. **Baris 57 (`serverErrors := make(chan error, 1)`)**: Buffered channel berkapasitas 1 mencegah goroutine listener bocor (*goroutine leak*) jika `srv.ListenAndServe()` melempar error sebelum channel sempat didengarkan oleh loop utama.
4. **Baris 67 (`signal.NotifyContext(..., syscall.SIGTERM)`)**: Pola modern Go untuk menangani OS Signals. Mengembalikan child context yang otomatis terbatalkan (`<-ctx.Done()`) ketika sistem menerima interrupt atau `SIGTERM` dari daemon Kubernetes.
5. **Baris 80 (`context.WithTimeout(context.Background(), 15*time.Second)`)**: Batas waktu draining internal yang harus lebih kecil daripada `terminationGracePeriodSeconds` di Kubernetes (umumnya bernilai default 30 detik) agar aplikasi dapat selesai membersihkan resource sebelum dihantam `SIGKILL`.
6. **Baris 84 (`srv.Shutdown(drainCtx)`)**: Menolak request baru di level socket, mendiamkan koneksi keep-alive, dan memblokir thread hingga semua request yang sedang aktif selesai diproses, atau sampai `drainCtx` kedaluwarsa.
7. **Baris 86 (`srv.Close()`)**: Jika proses draining gagal dalam rentang waktu yang diizinkan, eksekusi dipaksa jatuh ke `srv.Close()` untuk memutus paksa socket TCP dan mencegah aplikasi menggantung (*zombie process*).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Insiden: "The Black Friday Cascading Collapse"
* **Perusahaan**: E-Commerce Skala Nasional (Peak load: 85,000 req/sec).
* **Insiden**: Layanan *Payment Orchestration* berbasis Go mengalami crash beruntun (*crash looping*) di cluster Kubernetes saat *flash sale*. Container terbunuh secara acak dengan status `ExitCode: 137` (OOMKilled) dan latensi p99 membengkak dari 45ms ke 12,000ms.
* **Akar Masalah (Root Cause)**:
  1. Default HTTP client tidak memiliki timeout konfigurasi, menahan ratusan ribu TCP connection dalam kondisi unclosed/half-open saat payment gateway pihak ketiga mengalami degradasi performa.
  2. Nilai `GOGC` diset pada angka default (`100`) tanpa keberadaan `GOMEMLIMIT`. Pod yang dibatasi cgroup RAM 2 GiB mengalami lonjakan memory spike sebesar 2.1 GiB sebelum GC terpicu.
  3. Konfigurasi `GOMAXPROCS` tidak dideklarasikan pada pod dengan limit CPU `2 Core` di atas worker node bare-metal 128-core CPU. Go Runtime memicu pembentukan 128 scheduler threads, menghasilkan CFS Throttling mencapai 68% durasi runtime.
* **Dampak Bisnis**: 32% transaksi checkout gagal selama 42 menit, estimasi kerugian $180,000 USD.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur *Resilience Engine* terpadu tingkat lanjut untuk mitigasi skenario kasus nyata tersebut: mencakup integrasi `automaxprocs`, konfigurasi `GOMEMLIMIT`, custom RoundTripper untuk downstream dependency, dan status draining health probe.

```go
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
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Pendekatan / Parameter | Pengaturan Konfigurasi | Keuntungan (Pros) | Kerugian / Risiko (Cons) | Kapan Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| **GC Pacing Default** | `GOGC=100`, `GOMEMLIMIT` non-aktif | CPU overhead minimal; GC hanya dipicu saat heap berlipat ganda. | Risiko tinggi terkena OOMKill pada lonjakan alokasi transien di container ber-RAM terbatas. | Lingkungan bare-metal monolitik dengan RAM melimpah. |
| **Memory Target Limit** | `GOMEMLIMIT=85%`, `GOGC=off/100` | Memaksimalkan utilisasi RAM, proteksi deterministik dari Linux OOM-Killer. | Sedikit peningkatan CPU cost karena GC bekerja lebih sering saat mendekati batas limit. | **Standar Produksi Cloud-Native (Kubernetes Pods).** |
| **Conservative Timeouts** | `Read/WriteTimeout: < 3s` | Mencegah penumpukan goroutine bocor (*leak*); pertahanan kuat atas DoS. | Memutus klien sah dengan koneksi seluler lambat atau request dengan payload besar. | Layanan microservices internal / REST APIs latensi rendah. |
| **Relaxed/Zero Timeouts**| `Timeout = 0` (Default Go) | Mendukung transmisi file raksasa atau *Server-Sent Events (SSE)*. | Kerentanan kritis *Slowloris*; penumpukan thread OS tak terbatas hingga server crash. | Sangat jarang; hanya untuk streaming file khusus dengan validasi terisolasi. |
| **Graceful Sleep Delay** | `Sleep(5s)` sebelum `srv.Shutdown` | Menghilangkan *502 Bad Gateway* di level load balancer/Ingress Kubernetes. | Menambah durasi siklus deployment; rollback/rollout memakan waktu lebih lama. | Wajib pada sistem yang berada di belakang Ingress Controller asynchronous. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Broken WriteTimeout with Hijack / WebSockets
Jika Anda menetapkan `WriteTimeout` pada `http.Server`, durasi tersebut membatasi **seluruh usia koneksi** sejak request header dibaca. 
* *Pitfall*: Jika Anda menggunakan WebSocket atau SSE (*Server-Sent Events*), koneksi akan diputus secara mendadak oleh server saat durasi `WriteTimeout` terlewati, sekalipun transfer data aktif sedang berlangsung.
* *Solusi*: Jangan set `WriteTimeout` global jika server melayani WebSocket/SSE. Gunakan middleware berbasis `http.ResponseController` (Go 1.20+) untuk menyetel timeout per-request atau secara dinamis.

### 2. Leaking Request Body pada Klien
Ketika klien membatalkan koneksi, atau server Anda merespons dengan kode error (misal `400 Bad Request`), kelalaian dalam membaca atau menutup `r.Body` menyebabkan koneksi TCP tidak dapat di-*reuse* (*TCP socket reuse failure*).
* *Mitigasi*: Selalu bungkus manipulasi body dengan pembatasan `http.MaxBytesReader` dan pastikan proses downstream melakukan drain body bila ingin mempertahankan keep-alive.

### 3. File Descriptor Exhaustion
Secara default, Linux membatasi jumlah open file descriptor per proses (biasanya 1024 pada `ulimit -n`). Setiap koneksi socket TCP baru memakan 1 file descriptor. 
* *Pitfall*: Jika server Anda menerima 2000 request bersamaan dengan timeout yang salah dikonfigurasi, OS akan mengembalikan error `accept: too many open files`.
* *Mitigasi*: Konfigurasi `nofile` di level container/OS security limit ke minimal 65535, dan gunakan rate-limiter di depan HTTP handler.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan `http.DefaultClient` di Produksi
```go
// SALAH: http.DefaultClient tidak memiliki batas timeout (Timeout = 0)
resp, err := http.Get("https://api.external.com/data") // Potensi blocking selamanya!

// BENAR: Selalu instansiasi client mandiri dengan timeout ketat
var safeClient = &http.Client{
    Timeout: 5 * time.Second,
}
```

### 2. Mengabaikan Sinyal `SIGTERM` di Kubernetes
```go
// SALAH: Hanya menangani os.Interrupt (Ctrl+C). 
// Kubernetes mengirimkan SIGTERM saat Pod dimatikan, menyebabkan proses mati seketika!
signal.Notify(c, os.Interrupt)

// BENAR: Tangani os.Interrupt dan syscall.SIGTERM secara bersamaan
signal.Notify(c, os.Interrupt, syscall.SIGTERM)
```

### 3. Eksekusi `log.Fatal` di Dalam Handler
```go
// SALAH: log.Fatal() memanggil os.Exit(1) secara internal!
// Ini mematikan SELURUH server seketika tanpa eksekusi defer atau graceful shutdown.
func handler(w http.ResponseWriter, r *http.Request) {
    if err := doSomething(); err != nil {
        log.Fatal(err) // MEMBUNUH CONTAINER!
    }
}

// BENAR: Kembalikan status HTTP yang sesuai dan log error menggunakan slog
func handler(w http.ResponseWriter, r *http.Request) {
    if err := doSomething(); err != nil {
        slog.Error("Gagal memproses request", "error", err)
        http.Error(w, "Internal Error", http.StatusInternalServerError)
        return
    }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

* **Container Scratch / Distroless**: Bangun artefak akhir biner Go ke dalam image Docker `scratch` atau `gcr.io/distroless/static-debian12`. Ini menghilangkan package manager, shell (`/bin/sh`), dan utilitas Linux yang kerap dijadikan vektor pivoting eksploitasi oleh penyerang.
* **Non-Root Execution**: Pastikan biner Go dieksekusi menggunakan UID/GID non-root di dalam file Dockerfile:
  ```dockerfile
  USER 65532:65532
  ```
* **Enforce TLS 1.3**: Nonaktifkan dukungan TLS versi lawas (TLS 1.0, 1.1, dan bila memungkinkan 1.2) untuk menghindari downgrade attack dan cipher suites yang rentan.
* **Bounded Concurrency Semaphore**: Selalu bungkus operasi database I/O atau panggilan API eksternal dengan *bounded worker pool* atau *channel semaphore* untuk mencegah ledakan jutaan goroutine yang membebani memori.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Penggunaan `sync.Pool` untuk Buffer Handler
Dalam sistem bertransaksi jutaan request, alokasi memori berulang untuk encoding JSON atau byte slices akan membebani GC secara ekstrem. Gunakan `sync.Pool` untuk mendaur ulang objek transient.

```go
var bufferPool = sync.Pool{
	New: func() any {
		return new(bytes.Buffer)
	},
}

func optimizedHandler(w http.ResponseWriter, r *http.Request) {
	buf := bufferPool.Get().(*bytes.Buffer)
	buf.Reset()
	defer bufferPool.Put(buf)

	// Gunakan buffer untuk serialisasi data
	_ = json.NewEncoder(buf).Encode(map[string]string{"status": "ok"})
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write(buf.Bytes())
}
```

### 2. Reduksi Alokasi Header
Mengakses dan memanipulasi `http.Header` standar Go memicu alokasi heap karena representasinya berupa `map[string][]string`.
* Gunakan canonical key secara konsisten untuk menghindari pencarian berbasis case-insensitive yang memicu alokasi string baru: `w.Header().Set("Content-Type", ...)` alih-alih `w.Header().Set("content-type", ...)`.

---

## SEKSI 16 — KEAMANAN & HARDENING

### Minimal Production Multi-Stage Dockerfile (Hardened Spec)
Penerapan biner Go pada image kontainer scratch tanpa shell dan dependencies OS yang tidak perlu:

```dockerfile
# BUILD STAGE
FROM golang:1.22-alpine AS builder

# Pasang sertifikat SSL CA terbaru
RUN apk --no-cache add ca-certificates tzdata

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download && go mod verify

COPY . .

# Build flags untuk memangkas debugging symbols dan hardens biner
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -extldflags '-static'" \
    -trimpath \
    -o /bin/hardened-service .

# PRODUCTION RUNTIME STAGE
FROM scratch

# Salin data zona waktu dan sertifikat root TLS
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /bin/hardened-service /hardened-service

# Standar non-root user distroless/scratch
USER 65534:65534

# Metadata Container SRE
EXPOSE 8080

ENTRYPOINT ["/hardened-service"]
```

**Analisis Flags Compiler**:
* `-w`: Menghilangkan DWARF debugging information (memperkecil biner ~20-30%).
* `-s`: Menghilangkan symbol table.
* `-trimpath`: Menghilangkan path direktori lokal server build dari biner (mencegah kebocoran struktur path internal).
* `CGO_ENABLED=0`: Memastikan kompilasi murni statis, independen dari glibc target host.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Implementasi SRE Golden Signals (Traffic, Latency, Errors, Saturation) menggunakan Middleware Native Go dengan `log/slog`:

```go
package main

import (
	"log/slog"
	"net/http"
	"time"
)

// statusTrackingResponseWriter membungkus http.ResponseWriter asli untuk menangkap HTTP Status Code.
type statusTrackingResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (w *statusTrackingResponseWriter) WriteHeader(code int) {
	w.statusCode = code
	w.ResponseWriter.WriteHeader(code)
}

// SREObservabilityMiddleware merekam durasi, payload, error, dan metrik akses setiap request.
func SREObservabilityMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		wrappedWriter := &statusTrackingResponseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK, // default jika WriteHeader tidak dipanggil eksplisit
		}

		// Jalankan handler selanjutnya
		next.ServeHTTP(wrappedWriter, r)

		duration := time.Since(start)

		// Evaluasi Level Log berdasarkan Golden Signal Error
		logLevel := slog.LevelInfo
		if wrappedWriter.statusCode >= 500 {
			logLevel = slog.LevelError
		} else if wrappedWriter.statusCode >= 400 {
			logLevel = slog.LevelWarn
		}

		slog.Log(r.Context(), logLevel, "HTTP Transaction Completed",
			slog.String("method", r.Method),
			slog.String("path", r.URL.Path),
			slog.String("remote_addr", r.RemoteAddr),
			slog.Int("status", wrappedWriter.statusCode),
			slog.Duration("latency_ns", duration),
			slog.Float64("latency_ms", float64(duration.Microseconds())/1000.0),
		)
	})
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Pondasi Timeout HTTP Server**:
  * Set `ReadHeaderTimeout` (rekomendasi: `1s - 2s`) untuk mitigasi DoS Slowloris.
  * Hindari `Timeout: 0` pada instansiasi server dan client apa pun.
* **Go Containerization Tuning**:
  * Set variabel lingkungan `GOMEMLIMIT` pada ambang batas ~80-90% dari kuota container RAM.
  * Gunakan `uber-go/automaxprocs` agar Go scheduler sadar akan limit CPU quota cgroup (CFS).
* **Mekanisme Graceful Shutdown Standard**:
  * Intersepsi `os.Interrupt` dan `syscall.SIGTERM`.
  * Set status *Readiness probe* ke false / 503.
  * Berikan delay singkat (`sleep 5s`) untuk propagasi penghapusan rute jaringan Kubernetes.
  * Panggil `srv.Shutdown(ctx)` dengan context timeout terukur.
* **Binary Hardening**:
  * Kompilasi: `CGO_ENABLED=0 go build -ldflags="-w -s" -trimpath`.
  * Runtime image: `FROM scratch` atau `distroless`, jalankan sebagai non-root UID.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Basic
1. **Apa bahaya terbesar membiarkan `http.Server.ReadHeaderTimeout` bernilai nol pada aplikasi yang terekspos ke internet publik?**
   * A. Klien tidak dapat mengirim data lebih dari 1 MB.
   * B. Kerentanan terhadap serangan Slowloris yang dapat menghabiskan connection pool.
   * C. Garbage Collector Go akan otomatis non-aktif.
   * D. Server melempar panic saat menerima request HTTPS.

2. **Sinyal POSIX default manakah yang dikirim oleh Kubernetes saat memulai proses terminasi Pod?**
   * A. `SIGINT`
   * B. `SIGKILL`
   * C. `SIGTERM`
   * D. `SIGHUP`

3. **Mengapa biner Go untuk deployment kontainer scratch idealnya dikompilasi dengan `CGO_ENABLED=0`?**
   * A. Agar Go dapat menggunakan multithreading secara otomatis.
   * B. Memastikan biner independen dari pustaka dinamis C (glibc) yang tidak ada pada base image scratch.
   * C. Mengaktifkan fitur profiling pprof secara permanen.
   * D. Mengurangi konsumsi memori goroutine dari 2KB menjadi 1KB.

4. **Metode apa pada `http.Server` yang menutup listener jaringan terlebih dahulu dan menunggu semua koneksi aktif selesai?**
   * A. `srv.Close()`
   * B. `srv.Halt()`
   * C. `srv.Shutdown()`
   * D. `srv.Stop()`

5. **Apa fungsi utama dari konfigurasi flag compiler `-trimpath`?**
   * A. Menghapus DWARF debug information dari file biner.
   * B. Mengurangi ukuran biner dengan menghapus string table.
   * C. Menghilangkan informasi direktori lokal sistem build dari stack trace biner.
   * D. Mengoptimalkan performa inlining fungsi runtime.

### Soal Tingkat Intermediate
6. **Di lingkungan Kubernetes, sebuah container dialokasikan CPU limit `1500m` (1.5 core) pada worker node 96 core. Apa akibat jika `automaxprocs` TIDAK digunakan?**
   * A. Go runtime menetapkan `GOMAXPROCS` bernilai 1.
   * B. Go runtime menetapkan `GOMAXPROCS` bernilai 96, memicu context-switching masif dan CFS quota throttling.
   * C. Container akan langsung crash dengan status `OOMKilled`.
   * D. Go runtime membatalkan kompilasi biner secara dinamis.

7. **Bagaimana mekanisme interaksi yang tepat antara `GOMEMLIMIT` dan `GOGC`?**
   * A. `GOMEMLIMIT` menonaktifkan GC Go secara permanen.
   * B. `GOGC` menentukan rasio pertumbuhan heap reguler, namun GC akan terpicu secara preemptive mendahului aturan `GOGC` jika alokasi mendekati batas `GOMEMLIMIT`.
   * C. `GOMEMLIMIT` bertindak sebagai hard barrier yang akan memicu kernel panic jika terlampaui 1 byte.
   * D. Jika `GOMEMLIMIT` aktif, nilai `GOGC` dipaksa bernilai 100 secara statis.

8. **Mengapa pada arsitektur Kubernetes berkinerja tinggi disarankan menyisipkan `time.Sleep(5 * time.Second)` SEBELUM memanggil `srv.Shutdown()` saat menerima `SIGTERM`?**
   * A. Memastikan Garbage Collector Go sempat membersihkan heap.
   * B. Memberi jendela waktu bagi controller Kubernetes untuk mencabut IP Pod dari tabel routing kube-proxy / Ingress controller agar tidak ada traffic baru yang masuk saat draining.
   * C. Membiarkan sistem operasi Linux me-refresh alokasi file descriptor.
   * D. Mengosongkan memori swap yang tersisa di host node.

9. **Jika server melayani koneksi WebSocket jangka panjang, mengapa konfigurasi global `WriteTimeout` pada `http.Server` dapat menjadi masalah?**
   * A. WebSocket tidak mendukung protokol HTTP/1.1.
   * B. `WriteTimeout` mengukur durasi absolut sejak header dibaca, sehingga koneksi WebSocket akan diputus paksa saat timer habis meskipun stream data berjalan lancar.
   * C. `WriteTimeout` menyebabkan deadlock pada mutex internal TCP socket.
   * D. Klien WebSocket akan menolak handshake TLS jika `WriteTimeout` aktif.

10. **Apa dampak langsung dari kegagalan menutup (`Close()`) response body dari `http.Client.Do(req)`?**
    * A. Permintaan akan dieksekusi ulang secara otomatis oleh HTTP client.
    * B. TCP connection yang mendasari tidak dapat digunakan kembali (*reused*) oleh pool keep-alive, memicu kebocoran socket descriptor.
    * C. Goroutine scheduler runtime Go langsung berhenti seketika.
    * D. Terjadi race condition pada paket `net/http`.

---

### Kunci Jawaban Kuis

1. **B** — Ketiadaan `ReadHeaderTimeout` membuka pintu serangan Slowloris di mana klien menahan transmisi header untuk memonopoli pool koneksi.
2. **C** — Kubernetes mengirimkan sinyal POSIX `SIGTERM` untuk memulai masa grace period Pod termination.
3. **B** — Base image `scratch` kosong melompong; dependensi terhadap dynamic linker C (seperti libc/glibc) akan menyebabkan biner gagal dieksekusi (`file not found`).
4. **C** — `srv.Shutdown()` menghentikan listener dan mendrain transaksi aktif, berbeda dengan `srv.Close()` yang memutus soket secara langsung.
5. **C** — `-trimpath` menghapus path absolut komputer developer/CI-CD dari metadata biner untuk hardening keamanan.
6. **B** — Go membaca total core fisik host node (`NumCPU`), yang berujung pada thrashing thread dan pembatasan agresif (*throttling*) oleh Linux CFS scheduler.
7. **B** — `GOMEMLIMIT` menjadi batas lunak (*soft ceiling*) yang memaksa GC bekerja lebih giat ketika memori terancam melewati batas ambang Pod.
8. **B** — Arsitektur endpoint Kubernetes bersifat eventual consistency; jeda waktu memastikan traffic baru berhenti diarahkan ke Pod sebelum socket ditutup.
9. **B** — `WriteTimeout` bersifat kumulatif sejak koneksi dimulai, membatasi durasi maksimal koneksi persisten seperti WebSocket atau SSE.
10. **B** — Response body yang tidak di-drain dan tidak di-close mengunci koneksi underlying TCP socket, mencegahnya dikembalikan ke idle connection pool.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek: "Production Resilience Proxy Engine"
Bangun sebuah HTTP reverse proxy mikro berperforma tinggi yang bertugas sebagai *secure sidecar proxy* di depan sebuah upstream API.

### Kriteria Teknis Wajib:
1. **Hardened HTTP Engine**:
   * Konfigurasikan seluruh timeout HTTP server secara deterministik.
   * Batasi payload request body maksimum ke 256 KB menggunakan `http.MaxBytesReader`.
2. **Dynamic In-Flight Rate Limiter & Concurrency Guard**:
   * Batasi jumlah goroutine konkuren aktif maksimum yang memproses request ke backend secara bersamaan ke angka 50 menggunakan buffered channel semaphore. Jika kapasitas penuh, segera kembalikan status `429 Too Many Requests`.
3. **Observabilitas Berstandar SRE**:
   * Terapkan logging terstruktur berbasis `log/slog` yang merekam Request ID, Client IP, Status Code, Durasi Latensi, dan Memory Allocation footprint (baca via `runtime.ReadMemStats`).
4. **Graceful Draining Pipeline**:
   * Tangani sinyal `SIGTERM` dan `SIGINT`.
   * Implementasikan status *two-phase shutdown* dengan endpoint `/ready` yang mengembalikan kode `503 Service Unavailable` seketika sinyal terminasi dideteksi, sebelum mengeksekusi shutdown pada port utama setelah interval grace period 3 detik.
5. **Multi-Stage Containerization**:
   * Tulis Dockerfile multi-stage berbasis `golang:alpine` ke `scratch` dengan biner non-root statis, stripping debug symbols, dan trimpath.