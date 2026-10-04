# BAB 02: Materi Lanjutan
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** arsitektur I/O tingkat kernel (*synchronous blocking*, *non-blocking*, dan *I/O multiplexing*) serta mekanismenya pada runtime backend (*Thread-per-request*, *Event Loop*, dan *M:N Coroutine Scheduler*).
- **Merancang dan mengimplementasikan** manajemen siklus hidup koneksi basis data (*Database Connection Pooling*) dengan penanganan degradasi performa, *leak detection*, dan penyesuaian parameter berdasarkan karakteristik perangkat keras.
- **Mengembangkan** mekanisme pertahanan sistem backend meliputi *Graceful Shutdown*, propagasi pembatalan konteks (*Context Cancellation & Deadlines*), *Backpressure*, serta mitigasi *Cascading Failures*.
- **Mendeteksi dan menyelesaikan** masalah konkurensi, kebocoran soket/koneksi, dan *thread starvation* menggunakan *profiling tools* tingkat sistem dan runtime.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
1. **Dasar Jaringan & HTTP**: Siklus Request-Response, *Three-Way Handshake* TCP, status kode HTTP, dan struktur header.
2. **Dasar Sistem Operasi**: Konsep *Process*, *Thread*, *Virtual Memory*, *User Space* vs *Kernel Space*, serta *File Descriptors* (FD).
3. **Dasar Basis Data**: Operasi CRUD, relasi SQL, transaksi dasar (`BEGIN`, `COMMIT`, `ROLLBACK`), dan pengindeksan dasar.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Kernel I/O Multiplexing & Application Runtimes
Pada sistem operasi berbasis POSIX (Linux/UNIX), setiap koneksi jaringan direpresentasikan sebagai *File Descriptor* (FD). Ketika request HTTP masuk, alur data melewati tingkatan berikut:

```
[Network Interface Card (NIC)]
            │  DMA Transfer
            ▼
[Kernel Ring Buffer (rx_ring)]
            │  Hardware Interrupt (IRQ) -> Software Interrupt (ksoftirqd)
            ▼
[TCP Socket Receive Buffer (sk_buff)]
            │  
   ┌────────┴────────┐
   │  I/O Models     │
   ▼                 ▼
[epoll / kqueue]   [Blocking read()]
   │                 │
   │ O(1) Readiness  │ O(n) Thread context switch cost
   ▼                 ▼
[Non-blocking Worker] [Dedicated OS Thread]
```

1. **Blocking I/O (Sistem Klasik / Thread-per-request)**:
   Satu thread dialokasikan untuk satu FD. Ketika memanggil `read(fd)`, thread diblokir (*sleep state*) sampai kernel menerima paket data lengkap. Jika ada 10.000 koneksi konkuren, dibutuhkan 10.000 OS thread. Setiap thread mengonsumsi alokasi stack (default 1MB–8MB di Linux) dan memicu *overhead* besar pada *Kernel Context Switching* (penyimpanan register CPU, cache invalidation pada TLB).

2. **I/O Multiplexing (`epoll` di Linux, `kqueue` di BSD/macOS)**:
   Aplikasi mendaftarkan ribuan FD ke dalam struktur data berbasis Red-Black Tree di kernel space menggunakan system call `epoll_ctl`. Ketika paket TCP tiba di *socket receive buffer*, NIC dan kernel menandai FD tersebut dalam *Ready List* (Doubly Linked List). Panggilan `epoll_wait` mengembalikan daftar FD yang siap dibaca secara instan dengan kompleksitas waktu $\mathcal{O}(1)$ tanpa melakukan polling traversal $\mathcal{O}(N)$ seperti pada system call `select()` atau `poll()`.

3. **Perbandingan Runtime Backend**:
   - **Node.js (Libuv)**: Menggunakan satu thread utama yang menjalankan *Event Loop* berbasis `epoll`, mengabstraksi I/O operasi disk asinkron melalui *thread pool* internal (default 4 thread).
   - **Go (Go Runtime Network Poller & M:N Scheduler)**: Mengintegrasikan `epoll` langsung ke dalam *runtime scheduler* (GMP Model). Goroutine dialokasikan secara dinamis ke M (OS Threads) melalui P (Logical Processors). Stack goroutine bersifat dinamis, dimulai dari 2KB, memungkinkan jutaan koneksi konkuren dengan jejak memori yang sangat kecil.
   - **Java (JVM Virtual Threads / Project Loom)**: Menggantikan model *one-to-one thread mapping* menjadi model *user-mode thread* (Fiber/Virtual Thread) yang diparkir saat I/O terblokir tanpa memblokir *carrier thread* (OS Thread).

---

#### B. Database Connection Pooling Internal Mechanism
Membuka koneksi TCP ke database memerlukan negosiasi yang mahal:
1. TCP 3-Way Handshake: $1.5 \times \text{RTT}$.
2. TLS Handshake (jika dienkripsi): $1 \text{ hingga } 2 \times \text{RTT}$.
3. PostgreSQL/MySQL Authentication & Handshake: Alokasi backend process/thread baru di server database, pembacaan konfigurasi peran, dan inisialisasi sesi memori.

```
Application                  Pool Manager                      Database Server
    │                             │                                   │
    │─── Acquire Connection ─────>│                                   │
    │    (Pool Lease)             ├─ Available in Idle Ring?          │
    │                             │  ├── YES: Validate & Return       │
    │                             │  └── NO:                          │
    │                             │      ├── Total < MaxOpen: Create ─┼── Open TCP Socket ──>
    │                             │      └── Total = MaxOpen: Block   │
    │                             │          (Wait / Timeout Queue)   │
    │<── Lease Token Granted ─────┤                                   │
    │                             │                                   │
    │─── Execute Query (SQL) ─────┼──────────────────────────────────>│ (Process Query)
    │<── Read Rows / Cursor ──────┼───────────────────────────────────┤
    │                             │                                   │
    │─── Release Connection ─────>│                                   │
    │    (Return to Pool)         ├─ Check Conn Health                │
    │                             ├─ Check Lifetime / Idle Limits     │
    │                             └─ Signal Wait Queue                │
```

##### Komponen Utama Connection Pool:
- **Idle List / Queue**: Struktur data thread-safe (biasanya berbasis ring buffer atau linked list dengan sync primitive) yang menampung koneksi aktif siap pakai.
- **Wait Queue**: Antrean permintaan koneksi yang diblokir ketika jumlah koneksi mencapai `MaxOpenConnections`. Jika batas `WaitTimeout` terlampaui sebelum koneksi tersedia, error `ErrPoolExhausted` atau `Timeout` akan dikembalikan ke *caller*.
- **Reaper / Scavenger Thread**: Background worker yang membersihkan koneksi mati (*stale*), koneksi yang melampaui `MaxLifetime` (untuk mencegah memory leak pada backend database), atau koneksi yang melebihi batas `MaxIdleTime`.

##### Formulasi Sizing Connection Pool (HikariCP / PostgreSQL Formula):
Ukuran pool optimal tidak bersifat linier terhadap jumlah concurrent user, melainkan dibatasi oleh kapasitas pemrosesan fisik server database:

$$\text{Pool Size} = 2 \times \text{Core Count} + \text{Effective Spindle Count}$$

Jika database memiliki 16 vCPU dan menggunakan SSD (di mana rotasi spindle disk bernilai 0, namun memiliki parallel I/O channels sebesar ~1-2):
$$\text{Pool Size} = (2 \times 16) + 1 = 33 \text{ koneksi}.$$
*Catatan*: Mengatur pool aplikasi sebesar 500 koneksi ke database 16-core justru memicu degradasi performa drastis akibat *CPU context switching* dan *disk contention* di level database engine.

---

#### C. Graceful Degradation & Process Lifecycle
Sistem produksi tidak boleh mati secara mendadak saat menerima sinyal terminasi dari orchestrator (seperti Kubernetes, Docker, atau Systemd). 

Proses transisi shutdown mengikuti urutan status deterministik berikut:

```
[SIGTERM / SIGINT Signal Received]
               │
               ▼
[1. Stop Inbound Traffic] 
    └── Deregister from Consul / Close K8s Readiness Probe
    └── Stop accepting new TCP connections (close listener)
               │
               ▼
[2. In-flight Request Drain Loop]
    └── Wait for active HTTP handlers to complete (with timeout context)
    └── Emit 503 Service Unavailable / Connection: Close for edge cases
               │
               ▼
[3. Drain Downstream Dependencies]
    └── Stop background schedulers & worker queues
    └── Flush telemetry, metrics, and structured audit logs
               │
               ▼
[4. Close Persistent Connections]
    └── Close Database Connection Pool (wait for active transactions)
    └── Close Redis / Kafka / gRPC client pools
               │
               ▼
[5. Process Exit (Code 0)]
    └── Kernel cleans up memory space & release remaining FDs
```

---

### 4. Why & What

| Konsep | Pendekatan Naif (Pemula) | Pendekatan Enterprise Produksi | Dampak di Produksi |
| :--- | :--- | :--- | :--- |
| **Koneksi Database** | Membuka koneksi baru per request (`Connect()` lalu `Close()` per endpoint). | Menggunakan Shared Pool dengan batas `MaxOpen`, `MaxIdle`, `Lifetime`, dan validasi idle. | Menghindari exhaust limit FD, menurunkan latency dari ~50ms ke <1ms per query. |
| **Siklus Hidup Server** | `process.exit()` atau membiarkan aplikasi di-kill paksa oleh `SIGKILL`. | Graceful shutdown dengan penundaan (`drain`), context deadline, dan pelepasan resource. | Mencegah transaksi terpotong di tengah jalan (*database corruption*), nol *dropped requests*. |
| **Timeouts & Deadlines**| Tanpa batas waktu (default blocking selamanya). | Context Cancellation & Timeout Budgeting merambat dari gateway hingga database query. | Mencegah *thread exhaustion* massal saat downstream dependency mengalami latensi tinggi (*cascading failure*). |
| **Logging** | `console.log()` / `fmt.Println()` string biasa tanpa metadata. | Structured JSON Logging dengan trace correlation ID, log level dinamis, dan sinkronisasi buffer. | Mampu di-ingest oleh ELK/Datadog/Loki; memangkas waktu Mean Time to Detect (MTTD). |

---

### 5. How (Workflow Detail)

Untuk membangun arsitektur backend yang tangguh, implementasi harus mengikuti pipeline request terstruktur dengan isolasi dependensi yang ketat:

```
[Inbound Request]
       │
       ▼
[Timeout Context Injection] ─── (Deadline: now + 5000ms)
       │
       ▼
[Tracing & Structured Logging Middleware]
       │
       ▼
[Pool Acquisition] ──────────── (Acquire lock with Context timeout)
       │
       ▼
[Transaction Demarcation] ───── (BEGIN TRANSACTION with Isolation Level)
       │
       ▼
[Domain Logic Execution] ────── (Inject context to all external calls)
       │
       ▼
[Commit / Rollback Phase] ──── (Evaluate error tree, execute COMMIT or ROLLBACK)
       │
       ▼
[Release Resource to Pool] ─── (Defer execution guarantees release)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Loket Bank vs Connection Pool
Bayangkan sebuah Bank (Database Engine) yang hanya memiliki 8 Teller (CPU Cores):

- **Model Naif (Tanpa Pool)**: 1.000 nasabah masuk ke dalam gedung bank sekaligus. Semua berteriak ke arah 8 teller. Ruangan menjadi sangat bising, petugas sekuriti sibuk mengatur kerumunan daripada melayani, dan teller kehabisan energi hanya untuk mengidentifikasi siapa yang berbicara (*CPU Thrashing & Context Switching*).
- **Model Enterprise (Dengan Pool Terukur)**: Di luar pintu masuk disediakan ruang tunggu dengan kapasitas tetap (Connection Pool). Tepat 8 atau 16 nasabah dipanggil masuk secara teratur. Sisa nasabah menunggu di antrean berbatas waktu. Setiap teller bekerja dengan kapasitas throughput maksimal tanpa interupsi. Hasilnya: total waktu tunggu sistem turun secara signifikan, dan transaksi diselesaikan lebih cepat.

```
+---------------------------------------------------------------+
|                    OPERATING SYSTEM KERNEL                    |
|                                                               |
|  [Socket Inode 1042]       [Socket Inode 1043]                |
|  rx_buffer: [DATA][DATA]   rx_buffer: [EMPTY]                 |
|         │                          │                          |
|         └──────────────┐           │                          |
|                        ▼           ▼                          |
|                 [ epoll Ready List ]                          |
|                 |  FD 1042 Ready   |                          |
+------------------------│--------------------------------------+
                         │ epoll_wait() returns
                         ▼
+---------------------------------------------------------------+
|                  USER SPACE BACKEND RUNTIME                   |
|                                                               |
|  Goroutine / Worker Pool Scheduler                            |
|       │                                                       |
|       ▼                                                       |
|  [Worker 1] <--- Context: Timeout 3s, TraceID: abc-123        |
|       │                                                       |
|       ├─ Acquire DB Conn (Wait Queue / Idle Ring)             |
|       │         │                                             |
|       │         ▼                                             |
|       │   [DB Pool: 10/10 In Use] ──> Blocks until available  |
|       │                                                       |
|       ├─ Execute Prepared Statement                           |
|       └─ Release DB Conn (Defer Cleanup)                      |
+---------------------------------------------------------------+
```

---

### 7. Implementation: Simple & Practical Examples

Berikut adalah implementasi sistem produksi menggunakan Go yang mendemonstrasikan:
1. Konfigurasi Connection Pool optimal.
2. Structured Context Propagation & Timeout.
3. Transaksi aman dengan Rollback otomatis via defer.
4. Graceful Shutdown multi-layer.

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"sync"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

// Config merepresentasikan konfigurasi infrastruktur backend level enterprise.
type Config struct {
	Port            string
	DBDSN           string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
	ConnMaxIdleTime time.Duration
	RequestTimeout  time.Duration
	ShutdownTimeout time.Duration
}

// Application context dependency injection container.
type Application struct {
	logger *slog.Logger
	db     *sql.DB
	config Config
	wg     sync.WaitGroup
}

// UserAccount merepresentasikan entitas basis data.
type UserAccount struct {
	ID        int64     `json:"id"`
	Email     string    `json:"email"`
	Balance   int64     `json:"balance"`
	CreatedAt time.Time `json:"created_at"`
}

func main() {
	// Inisialisasi Structured Logger (JSON format) untuk konsumsi log collector (ELK/Loki)
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))

	cfg := Config{
		Port:            ":8080",
		DBDSN:           "postgres://postgres:secret@localhost:5432/core_db?sslmode=disable",
		MaxOpenConns:    runtime.NumCPU() * 4, // Tuning adaptif berdasarkan Core CPU
		MaxIdleConns:    runtime.NumCPU() * 2,
		ConnMaxLifetime: 30 * time.Minute,
		ConnMaxIdleTime: 5 * time.Minute,
		RequestTimeout:  5 * time.Second,
		ShutdownTimeout: 15 * time.Second,
	}

	app, err := initApplication(logger, cfg)
	if err != nil {
		logger.Error("Gagal menginisialisasi dependensi aplikasi", "error", err)
		os.Exit(1)
	}
	defer app.db.Close()

	if err := app.run(); err != nil {
		logger.Error("Aplikasi berhenti secara tidak normal", "error", err)
		os.Exit(1)
	}
}

func initApplication(logger *slog.Logger, cfg Config) (*Application, error) {
	db, err := sql.Open("postgres", cfg.DBDSN)
	if err != nil {
		return nil, fmt.Errorf("error membuka pointer database: %w", err)
	}

	// Terapkan batas pertahanan Connection Pool
	db.SetMaxOpenConns(cfg.MaxOpenConns)
	db.SetMaxIdleConns(cfg.MaxIdleConns)
	db.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	db.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)

	// Validasi konektivitas aktual dengan timeout konteks
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("ping awal ke database gagal: %w", err)
	}

	logger.Info("Koneksi database pool berhasil diverifikasi",
		"max_open", cfg.MaxOpenConns,
		"max_idle", cfg.MaxIdleConns,
	)

	return &Application{
		logger: logger,
		db:     db,
		config: cfg,
	}, nil
}

func (app *Application) run() error {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/transfer", app.handleBalanceTransfer)
	mux.HandleFunc("GET /healthz", app.handleHealthCheck)

	// Middleware pipeline wrapping
	handler := app.recoverPanicMiddleware(app.traceContextMiddleware(mux))

	server := &http.Server{
		Addr:         app.config.Port,
		Handler:      handler,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
		BaseContext: func(l net.Listener) context.Context {
			return context.Background()
		},
	}

	shutdownSignal := make(chan os.Signal, 1)
	signal.Notify(shutdownSignal, syscall.SIGINT, syscall.SIGTERM)

	serverError := make(chan error, 1)
	go func() {
		app.logger.Info("Server HTTP aktif mendengarkan koneksi", "port", app.config.Port)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serverError <- err
		}
	}()

	select {
	case err := <-serverError:
		return fmt.Errorf("critical error pada HTTP listener: %w", err)
	case sig := <-shutdownSignal:
		app.logger.Warn("Sinyal terminasi diterima, memulai graceful shutdown", "signal", sig.String())

		// Buat Context penundaan untuk memastikan request aktif selesai
		ctx, cancel := context.WithTimeout(context.Background(), app.config.ShutdownTimeout)
		defer cancel()

		// 1. Berhenti menerima koneksi baru & kuras in-flight requests
		if err := server.Shutdown(ctx); err != nil {
			app.logger.Error("Paksa terminasi HTTP server akibat timeout", "error", err)
			_ = server.Close()
		}

		// 2. Tunggu background worker selesai jika ada
		app.wg.Wait()

		// 3. Tutup connection pool database secara deterministik
		if err := app.db.Close(); err != nil {
			app.logger.Error("Error saat menutup pool database", "error", err)
		}

		app.logger.Info("Graceful shutdown selesai tanpa kehilangan transaksi")
	}

	return nil
}

type TransferRequest struct {
	SourceAccountID int64 `json:"source_account_id"`
	TargetAccountID int64 `json:"target_account_id"`
	Amount          int64 `json:"amount"`
}

// handleBalanceTransfer mengeksekusi transfer uang dengan ACID transaction dan context timeout.
func (app *Application) handleBalanceTransfer(w http.ResponseWriter, r *http.Request) {
	// Propagasi context request dengan deadline ketat
	ctx, cancel := context.WithTimeout(r.Context(), app.config.RequestTimeout)
	defer cancel()

	var req TransferRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		app.writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Payload JSON tidak valid"})
		return
	}

	if req.Amount <= 0 || req.SourceAccountID == req.TargetAccountID {
		app.writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "Parameter transfer tidak valid"})
		return
	}

	// Eksekusi transaksi dengan isolasi level Read Committed / Repeatable Read
	err := app.executeTransferTx(ctx, req)
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) {
			app.logger.Error("Transaksi dibatalkan akibat timeout deadline", "trace_id", ctx.Value("trace_id"))
			app.writeJSON(w, http.StatusGatewayTimeout, map[string]string{"error": "Batas waktu pemrosesan terlampaui"})
			return
		}

		app.logger.Error("Gagal memproses transaksi finansial", "error", err)
		app.writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "Kegagalan internal pemrosesan transfer"})
		return
	}

	app.writeJSON(w, http.StatusOK, map[string]string{"status": "Transfer berhasil diproses"})
}

func (app *Application) executeTransferTx(ctx context.Context, req TransferRequest) error {
	tx, err := app.db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
	})
	if err != nil {
		return fmt.Errorf("inisialisasi transaksi gagal: %w", err)
	}

	// Defer Rollback: Menjamin jika fungsi keluar sebelum COMMIT, transaksi otomatis dibatalkan
	defer tx.Rollback()

	// 1. Kunci baris sumber dengan SELECT FOR UPDATE untuk mencegah Race Condition (Double Spend)
	var sourceBalance int64
	queryLockSource := `SELECT balance FROM accounts WHERE id = $1 FOR UPDATE`
	if err := tx.QueryRowContext(ctx, queryLockSource, req.SourceAccountID).Scan(&sourceBalance); err != nil {
		return fmt.Errorf("gagal mengunci data akun sumber: %w", err)
	}

	if sourceBalance < req.Amount {
		return errors.New("saldo akun pengirim tidak mencukupi")
	}

	// 2. Debet saldo pengirim
	queryDeduct := `UPDATE accounts SET balance = balance - $1 WHERE id = $2`
	if _, err := tx.ExecContext(ctx, queryDeduct, req.Amount, req.SourceAccountID); err != nil {
		return fmt.Errorf("debet akun sumber gagal: %w", err)
	}

	// 3. Kredit saldo penerima
	queryCredit := `UPDATE accounts SET balance = balance + $1 WHERE id = $2`
	if _, err := tx.ExecContext(ctx, queryCredit, req.Amount, req.TargetAccountID); err != nil {
		return fmt.Errorf("kredit akun tujuan gagal: %w", err)
	}

	// 4. Commit transaksi secara eksplisit
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("gagal melakukan commit transaksi: %w", err)
	}

	return nil
}

func (app *Application) handleHealthCheck(w http.ResponseWriter, r *http.Request) {
	// Ping database untuk memverifikasi kesiapan menerima trafik (Readiness Probe)
	ctx, cancel := context.WithTimeout(r.Context(), 1*time.Second)
	defer cancel()

	if err := app.db.PingContext(ctx); err != nil {
		app.writeJSON(w, http.StatusServiceUnavailable, map[string]string{
			"status": "UNHEALTHY",
			"reason": "Database connection pool saturated or unreachable",
		})
		return
	}

	stats := app.db.Stats()
	app.writeJSON(w, http.StatusOK, map[string]interface{}{
		"status": "HEALTHY",
		"pool": map[string]int{
			"open_connections": stats.OpenConnections,
			"in_use":           stats.InUse,
			"idle":             stats.Idle,
			"wait_count":       int(stats.WaitCount),
		},
	})
}

// Middleware: Pemulihan Panic untuk mencegah proses crash total
func (app *Application) recoverPanicMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rvr := recover(); rvr != nil {
				app.logger.Error("Panic tertangkap pada handler thread",
					"error", fmt.Sprintf("%v", rvr),
					"stack", getStackTrace(),
				)
				w.WriteHeader(http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// Middleware: Injeksi context metadata untuk observabilitas
func (app *Application) traceContextMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		traceID := r.Header.Get("X-Trace-ID")
		if traceID == "" {
			traceID = fmt.Sprintf("trace-%d", time.Now().UnixNano())
		}

		ctx := context.WithValue(r.Context(), "trace_id", traceID)
		w.Header().Set("X-Trace-ID", traceID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func (app *Application) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func getStackTrace() string {
	buf := make([]byte, 1024*2)
	n := runtime.Stack(buf, false)
	return string(buf[:n])
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Flash Sale Saturated DB Pool Collapse
- **Profil Perusahaan**: Platform E-Commerce Asia Tenggara.
- **Peristiwa**: Saat kampanye midnight flash sale (11.11), trafik melonjak dari 1.200 RPS menjadi 48.000 RPS dalam 30 detik.
- **Gejala Masalah**:
  1. API Gateway mengembalikan error HTTP 504 Gateway Timeout massal ke pengguna.
  2. Latensi $p99$ melonjak dari 45ms ke 18.000ms.
  3. Server database utama (AWS RDS Aurora PostgreSQL 32 vCPU) mengalami CPU Utilization 100%, load average mencapai 450.
- **Akar Masalah (Root Cause Analysis)**:
  - Developer backend mengonfigurasi pool microservice dengan `MaxOpenConns = 100` pada 80 pod Kubernetes autoscaled.
  - Total kemungkinan koneksi yang menyerbu database: $80 \times 100 = 8.000$ koneksi simultan.
  - Aurora PostgreSQL hanya optimal menangani concurrent query sebanyak $\approx 64-128$.
  - Ribuan backend thread/goroutine memperebutkan lock pada tabel `inventory` (`SELECT FOR UPDATE`), menyebabkan lock tree chain.
  - PostgreSQL menghabiskan 95% siklus CPU hanya untuk context switching dan lock contention audit, bukan mengeksekusi instruksi data.
- **Langkah Remidiasi & Mitigasi**:
  1. **Deployment Connection Proxy (PgBouncer)**: Mengisolasi 8.000 koneksi frontend pod menjadi pool transaksional tetap sebesar 64 koneksi fisik ke engine Aurora.
  2. **Tuning Aplikasi**: `MaxOpenConns` per pod diturunkan dari 100 menjadi 5. Permintaan yang melebihi batas ini diantrekan secara lokal di runtime memory atau ditolak cepat (*Fail-Fast*) dengan HTTP 429 / Backpressure.
  3. **Context Deadline Propagation**: Setiap transaksi query diikat dengan context timeout 800ms. Query yang tersangkut lock secara otomatis di-abort oleh backend sebelum membebani antrean DB.

---

### 9. Trade-offs (Analisis Keputusan Rekayasa)

```
             COMPLEXITY
                 ▲
                 │                           [Go Scheduler / Netpoller]
                 │                                (Sweet Spot)
                 │
                 │          [Node.js Libuv]
                 │          (CPU-bound blocks)
                 │
                 │                                        [C++ Custom epoll/io_uring]
                 │                                        (Extreme throughput, high dev cost)
                 │
                 │   [Classic Thread-per-request]
                 │   (Simple, bad scalability)
                 └────────────────────────────────────────────────────────► PERFORMANCE (CONCURRENCY)
```

| Dimensi Arsitektur | Opsi A: Thread-per-Request (e.g., Spring Boot Default / Apache MPM) | Opsi B: Non-Blocking / Event Multiplexing (e.g., Go, Node.js, Netty) |
| :--- | :--- | :--- |
| **Karakteristik Latensi** | Stabil pada beban rendah; terdegradasi eksponensial saat thread cap tercapai. | Latensi rata-rata sangat konsisten; degradasi halus saat saturation point tercapai. |
| **Konsumsi Memori** | Tinggi (1-2 MB virtual memory per OS thread minimum stack allocation). | Sangat Rendah (~2KB per goroutine / user-space frame buffer). |
| **Beban Debugging** | Deterministik: Stack trace thread menunjukkan alur eksekusi sekuensial yang presisi. | Kompleks: Asynchronous stack traces sering terpecah antarevent loop ticks. |
| **Kesesuaian Workload** | Komputasi intensif CPU (*cryptographic processing*, kompresi video). | Komputasi I/O-bound intensif (*Chat services*, API Gateways, REST/GraphQL aggregators). |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: Connection Leak Akibat Tidak Menutup Row Result Set
```go
// ANTI-PATTERN: rows.Close() terabaikan jika ada return di tengah
rows, err := db.QueryContext(ctx, "SELECT id, email FROM users")
if err != nil {
    return err
}
for rows.Next() {
    if err := rows.Scan(&id, &email); err != nil {
        return err // KESALAHAN FATAL: Koneksi tertahan, pool akan habis (exhausted)!
    }
}
// KOREKSI WAJIB:
// Gunakan: defer rows.Close() tepat setelah pengecekan error query.
```

#### Skenario 2: Deadlock Akibat Urutan Penguncian Row yang Tidak Konsisten
- **Gejala**: Dua transaksi transfer finansial saling memblokir selamanya hingga database membunuh salah satu via *Deadlock Detector*.
- **Penyebab**:
  - Transaksi A mengunci Akun 1, lalu mencoba mengunci Akun 2.
  - Bersamaan dengan itu, Transaksi B mengunci Akun 2, lalu mencoba mengunci Akun 1.
- **Solusi**: Selalu lakukan penguncian berdasarkan urutan deterministik (misal: ID terkecil selalu dikunci lebih dulu):
  ```go
  firstLockID := min(req.SourceAccountID, req.TargetAccountID)
  secondLockID := max(req.SourceAccountID, req.TargetAccountID)
  // Lock firstLockID, kemudian secondLockID
  ```

#### Toolkit Troubleshooting Produksi:
1. **Melihat Soket & Koneksi Aktif Level OS**:
   ```bash
   # Cek koneksi ESTABLISHED, TIME_WAIT, dan LISTEN pada port 8080
   ss -tan state established '( sport = :8080 or dport = :8080 )'
   # Monitoring alokasi File Descriptor proses backend
   lsof -p <PID_PROSES> | wc -l
   ```
2. **Mendeteksi Latensi Kernel I/O via Strace**:
   ```bash
   # Lacak system call epoll_wait dan read pada aplikasi
   strace -e trace=epoll_wait,read,write -c -p <PID_PROSES>
   ```

---

### 11. Best Practices (Production Checklist)

- [ ] **Kernel Tuning (`sysctl.conf`)**:
  - Naikkan batas file descriptor: `fs.file-max = 2097152`.
  - Tingkatkan batas TCP backlog queue: `net.core.somaxconn = 65535`.
  - Aktifkan TCP reuse untuk koneksi TIME_WAIT: `net.ipv4.tcp_tw_reuse = 1`.
- [ ] **Application Pool Tuning**:
  - Tentukan `MaxIdleConns` proporsional ($\approx 50\%-100\%$ dari `MaxOpenConns`) untuk mencegah socket thrashing (buka-tutup koneksi berulang).
  - Berikan batas `ConnMaxLifetime` di bawah idle connection reaper milik firewall atau load balancer (misal AWS ALB memutus idle socket di 350 detik, set lifetime ke 300 detik).
- [ ] **Defensive Timeouts**:
  - Injeksi timeout context ke *setiap* database call, remote HTTP call, dan cache access.
  - Jangan pernah gunakan HTTP client standar tanpa timeout bawaan (`http.Client{}` di Go default-nya `no timeout`).
- [ ] **Shutdown Lifecycle**:
  - Berikan toleransi waktu (*shutdown grace period*) yang cukup pada container spec (`terminationGracePeriodSeconds: 30` di Kubernetes).

---

### 12. Hands-on Practice: Membangun Resilient Micro-Service

Simpan seluruh file berikut di dalam folder workspace: `hands-on/m02/`.

#### Langkah 1: Struktur Proyek
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
go mod init resilient-backend
```

#### Langkah 2: Buat Database Schema Migration Script (`init.sql`)
```sql
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    owner_name VARCHAR(100) NOT NULL,
    balance BIGINT NOT NULL CHECK (balance >= 0)
);

INSERT INTO accounts (owner_name, balance) VALUES 
('Alice', 1000000),
('Bob', 500000);
```

#### Langkah 3: Script Eksekusi Docker & DB Runner
Jalankan instance PostgreSQL lokal via docker:
```bash
docker run --name pg-workshop \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=core_db \
  -p 5432:5432 \
  -v $(pwd)/init.sql:/docker-entrypoint-initdb.d/init.sql \
  -d postgres:16-alpine
```

#### Langkah 4: Simpan & Jalankan Kode Backend
Simpan kode Go pada Bagian 7 di dalam file `main.go`. Jalankan backend:
```bash
go get github.com/lib/pq
go run main.go
```

#### Langkah 5: Simulasi Uji Beban (Benchmarking) & Concurrency Test
Buka terminal baru, gunakan tool benchmarking `hey` atau `ab` (Apache Bench) untuk melihat perilaku connection pool di bawah saturasi:
```bash
# Instal hey jika belum ada: go install github.com/rakyll/hey@latest
hey -n 2000 -c 50 -m POST \
  -H "Content-Type: application/json" \
  -d '{"source_account_id":1,"target_account_id":2,"amount":100}' \
  http://localhost:8080/api/v1/transfer
```

#### Langkah 6: Validasi Graceful Shutdown
Saat load testing sedang berjalan di terminal kedua, tekan `Ctrl+C` pada terminal server backend. Amati log terminal:
1. Server segera berhenti menerima request baru.
2. Request in-flight yang sedang menyelesaikan transfer tetap selesai dengan commit valid.
3. Database pool tertutup sempurna tanpa transaksi `aborted` kotor di PostgreSQL.

---

### 13. Exercises

#### Level Easy
Ubah method `handleHealthCheck` pada contoh kode agar menyertakan status deteksi persentase saturasi pool:
$$\text{Pool Saturation Ratio} = \frac{\text{InUse}}{\text{MaxOpen}} \times 100\%$$
Kembalikan status HTTP 503 jika saturasi melebihi $90\%$.

#### Level Medium
Implementasikan algoritma penataan urutan penguncian (*Lock Ordering Algorithm*) pada fungsi `executeTransferTx` untuk mencegah potensi transaksi *deadlock* saat Alice mentransfer uang ke Bob di waktu yang sama persis ketika Bob mentransfer uang ke Alice.

#### Level Hard
Buat middleware sirkuit pelindung (*In-Memory Token Bucket Rate Limiter*) murni tanpa library eksternal. Jika kapasitas token habis, tolak request seketika dengan status code `HTTP 429 Too Many Requests` beserta header `Retry-After: 1` sebelum request tersebut menyentuh lapisan koneksi database.

---

### 14. Challenge: Arsitektur Pemulihan "Zombie Connections"

**Deskripsi Masalah**:
Sebuah kluster microservice backend terhubung ke Managed Cloud Database. Di antara Pod backend dan Cloud DB terdapat stateful Virtual Private Network (VPN) / NAT Gateway. NAT Gateway memiliki konfigurasi idle connection tracking timeout selama 300 detik.

Aplikasi Anda memiliki pool database dengan konfigurasi:
- `MaxIdleConns = 50`
- `ConnMaxLifetime = 2 Hour`
- `ConnMaxIdleTime = Tanpa batas (disabled)`

Pada malam hari ketika trafik sangat rendah, beberapa koneksi database idle selama lebih dari 300 detik. NAT Gateway secara sepihak memutus state koneksi (*dropped packet without FIN/RST packet*). Akibatnya, baik kernel Linux backend maupun Database Engine tidak mengetahui bahwa koneksi tersebut telah putus (*Half-Open / Zombie Socket*).

Ketika lonjakan trafik fajar tiba, backend mencoba menggunakan kembali koneksi di pool tersebut. Goroutine tersangkut (*hang*) hingga OS TCP Keepalive timeout terlampaui (default Linux: 7200 detik = 2 jam). Seluruh worker pool aplikasi membeku.

**Tugas Arsitektur Anda**:
1. Rancang arsitektur parameter konfigurasi (di tingkat OS kernel, driver TCP backend, dan pool manager) untuk mendeteksi dan mengeliminasi masalah *Zombie Connection* ini dalam waktu maksimal 10 detik.
2. Tuliskan analisis mekanisme apa saja yang harus diubah beserta justifikasi parameter matematika dan konfigurasinya.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level
1. **Apa perbedaan mendasar antara *blocking I/O* dan *I/O multiplexing* di level kernel Linux?**
   - *Jawaban*: Pada *blocking I/O*, satu thread dibekukan (*sleep state*) untuk menunggu data dari satu File Descriptor. Pada *I/O multiplexing* (seperti `epoll`), satu thread kernel dapat memantau ribuan File Descriptor sekaligus melalui struktur data teroptimasi dan hanya merespons FD yang statusnya *ready*.

2. **Mengapa nilai `MaxOpenConns` database tidak boleh dibuat setinggi mungkin (misal: 10.000)?**
   - *Jawaban*: Database engine memiliki limitasi komputasi fisik (CPU core dan I/O disk). Terlalu banyak koneksi simultan menyebabkan *CPU context switching thrashing* dan saturasi antrean lock, menurunkan *throughput* total, serta dapat menyebabkan database kehabisan memori (*OOM-kill*).

3. **Apa fungsi utama dari `defer rows.Close()` setelah pemanggilan `QueryContext`?**
   - *Jawaban*: Menjamin bahwa koneksi TCP database yang memegang kursor pembacaan hasil query dikembalikan ke connection pool, terlepas dari apakah loop iterasi row selesai secara normal atau keluar akibat error.

4. **Sinyal OS apa yang dikirimkan oleh orchestrator (Docker/Kubernetes) untuk meminta aplikasi mematikan diri secara teratur?**
   - *Jawaban*: `SIGTERM` (Signal 15). Jika aplikasi tidak mati setelah batas waktu tertentu (*grace period*), orchestrator akan mengirimkan `SIGKILL` (Signal 9).

5. **Apa yang terjadi pada transaksi database jika koneksi TCP terputus sebelum query `COMMIT` sempat dijalankan?**
   - *Jawaban*: Database engine mendeteksi diskoneksi soket, lalu secara otomatis menjalankan operasi `ROLLBACK` internal untuk memastikan data tetap berada dalam keadaan konsisten (memenuhi sifat *Atomicity* pada ACID).

---

#### Intermediate Level
6. **Bagaimana propagasi `context.Context` deadline mencegah cascading failure pada arsitektur microservices?**
   - *Jawaban*: Context deadline mendistribusikan sisa batas waktu request ke seluruh rantai panggilan internal (misal DB, RPC, cache). Jika batas waktu habis di tengah alur, semua eksekusi downstream dibatalkan secara instan, mencegah resource server terpakai sia-sia untuk memproses request yang hasilnya sudah tidak ditunggu oleh client.

7. **Mengapa kita harus mengonfigurasi `SetConnMaxLifetime` lebih rendah daripada batas idle-timeout pada network infrastructure (seperti AWS ALB atau Firewall NAT)?**
   - *Jawaban*: Mencegah aplikasi menggunakan koneksi yang status fisiknya telah ditutup secara sepihak oleh middle-box/firewall (*half-open connection*), yang dapat menyebabkan error `connection reset by peer` atau socket hang.

8. **Apa perbedaan implementasi concurrency model antara Node.js (Libuv) dan Go (Runtime Netpoller)?**
   - *Jawaban*: Node.js menjalankan Javascript code pada single thread event loop dan melimpahkan I/O tertentu ke thread pool background libuv. Go menggunakan scheduler GMP berbasis *M:N green-threads* (Goroutine) yang mendistribusikan eksekusi kode ke multi-thread OS secara terintegrasi dengan network poller kernel.

9. **Apa risiko menggunakan isolation level `Read Uncommitted` pada database transaksional?**
   - *Jawaban*: Munculnya fenomena *Dirty Read*, di mana sebuah transaksi dapat membaca modifikasi data dari transaksi lain yang sebenarnya belum di-commit dan mungkin saja dibatalkan (*rollback*) di kemudian waktu.

10. **Apa kegunaan klausa `FOR UPDATE` pada query SQL dalam transaksi transfer finansial?**
    - *Jawaban*: Mengunci baris data (*Row-Level Pessimistic Locking*) secara eksklusif agar transaksi paralel lain tidak dapat mengubah atau mengunci baris tersebut sampai transaksi saat ini selesai, mencegah terjadinya anomali *Lost Update* atau *Double Spending*.

---

#### Production Case Scenarios
11. **Skenario Kasus 1**:
    *Insiden*: Aplikasi backend Go Anda di-deploy di Kubernetes. Setiap kali dilakukan deployment versi baru (*rolling update*), pengguna mengalami lonjakan error HTTP 502 Bad Gateway selama 2-5 detik.
    *Pertanyaan*: Jelaskan mengapa hal ini terjadi meski Anda telah menerapkan Graceful Shutdown dengan penanganan sinyal SIGTERM, dan bagaimana arsitektur deployment yang benar untuk mengatasinya?
    - *Analisis Solusi*: Ini adalah *race condition* distribusi rute di Kubernetes. Saat Pod menerima sinyal `SIGTERM`, server aplikasi langsung menutup socket HTTP listener-nya. Namun pada saat bersamaan, kube-proxy dan Ingress Controller membutuhkan waktu beberapa detik untuk memperbarui IP Pod dari tabel `Endpoints`. Request baru yang masih dialihkan ke Pod tersebut akan ditolak (mengakibatkan 502). Solusinya: Tambahkan *preStop hook sleep* (misal: `sleep 5`) pada manifes Kubernetes Pod sebelum proses backend menerima SIGTERM, agar Ingress Controller menyelesaikan pencabutan rute terlebih dahulu sebelum aplikasi menutup soketnya.

12. **Skenario Kasus 2**:
    *Insiden*: Sistem monitoring backend mendeteksi metrik *Go Goroutine Count* meningkat secara linier setiap jam tanpa pernah turun, hingga akhirnya sistem mengalami crash akibat kehabisan memori (*OOM*).
    *Pertanyaan*: Apa langkah teknis sistematis Anda untuk mendiagnosis baris kode spesifik yang menyebabkan kebocoran tersebut di lingkungan produksi?
    - *Analisis Solusi*:
      1. Aktifkan endpoint runtime profiling bawaan (`net/http/pprof`).
      2. Ambil snapshot goroutine dump saat memori naik melalui CLI: `curl -s http://localhost:8080/debug/pprof/goroutine?debug=2 > goroutines.txt`.
      3. Analisis tumpukan panggilan (*stack trace*): cari goroutine yang tersangkut dalam status `chan receive (nil chan)` atau I/O blocking call tanpa batas `timeout/context`.
      4. Verifikasi apakah ada background worker atau channel send yang tidak memiliki consumer atau tidak pernah ditutup saat lifecycle handler selesai.

13. **Skenario Kasus 3**:
    *Insiden*: Database master PostgreSQL mengalami *Connection Pool Saturation* mendadak. Log database menunjukkan ribuan query sederhana `SELECT status FROM orders WHERE id = $1` berjalan sangat lambat (>10 detik) dan memblokir antrean koneksi lain.
    *Pertanyaan*: Apa yang sebenarnya terjadi di level basis data jika query `SELECT` tanpa modifikasi data dapat menyebabkan kemacetan eksekusi transaksional global?
    - *Analisis Solusi*: Kemungkinan besar terjadi fenomena *Lock Contention Escalation* atau disk I/O starvation. Hal ini biasanya dipicu oleh:
      1. Transaksi panjang (*Long-Running Transaction*) lain yang sedang mengunci tabel yang sama dengan *Exclusive Lock* (misal: migrasi DDL `ALTER TABLE` tanpa batas lock timeout).
      2. Saturasi I/O Subsystem (Disk IOPS limit reached) akibat query analitik liar tanpa index yang membaca disk secara masif (*Sequential Scan*), menyebabkan buffer pool ter-flush dan query SELECT sederhana terpaksa menunggu giliran akses disk I/O (*I/O Wait State*).

---

### 16. Summary
- **Mekanisme I/O**: Pemahaman terhadap abstraksi sistem operasi (Kernel Space, File Descriptors, dan `epoll`) adalah pondasi utama dalam memahami efisiensi runtime modern (*Event Loop* maupun *Scheduler M:N*).
- **Efisiensi Sumber Daya**: Database Connection Pool bukanlah sekadar akselerator query, melainkan katup pengaman agar database engine tidak mengalami degradasi performa akibat *CPU Context Switch* dan perebutan lock.
- **Resiliensi Terintegrasi**: Sistem backend enterprise harus dirancang dengan prinsip defensif: membatasi batas tunggu (*Timeout Context*), merilis koneksi secara terjamin (*Defer Mechanism*), dan menghentikan pemrosesan secara anggun (*Graceful Shutdown*).
- **Observabilitas**: Arsitektur tanpa penanganan kesalahan struktural, context tracing, dan metrik kesehatan internal adalah sistem yang rapuh ketika dihadapkan pada skala beban produksi yang sebenarnya.