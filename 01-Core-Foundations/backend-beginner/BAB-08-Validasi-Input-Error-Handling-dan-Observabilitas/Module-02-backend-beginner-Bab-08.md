# BAB 08: Materi Lanjutan
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Arsitektur Heksagonal (Ports & Adapters)** secara idiomatik untuk memisahkan domain logika bisnis murni dari infrastruktur eksternal (*database*, *broker*, protokol HTTP/gRPC).
- **Mengelola Siklus Hidup Proses (*Process Lifecycle*) & Graceful Shutdown** dengan menangani sinyal OS (`SIGINT`, `SIGTERM`), membersihkan *connection pools*, dan menguras (*draining*) *in-flight requests* tanpa kehilangan data.
- **Mengonfigurasi dan Mengoptimasi Connection Pooling Tingkat Lanjut** pada layer basis data relasional (PostgreSQL) dan caching (Redis), memitigasi risiko *connection starvation*, serta memahami *TCP keep-alive* dan *socket buffer*.
- **Menerapkan Pola Ketahanan Sistem (*Resilience Patterns*)**: *Circuit Breaker*, *Retries with Exponential Backoff and Jitter*, serta *Distributed Rate Limiting* menggunakan algoritma *Token Bucket*/*Leaky Bucket*.
- **Membangun Pola Pemrosesan Asinkron yang Idempoten** menggunakan arsitektur *Transactional Outbox* dan *Background Worker Pool* berbasis *worker-queue pattern*.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- Sintaksis dasar dan pemrograman konkuren (Go goroutine/channel, Node.js Event Loop, atau Java Virtual Threads).
- Operasi dasar SQL (ACID transactions, isolasi level `READ COMMITTED` vs `SERIALIZABLE`).
- Protokol dasar HTTP/1.1 dan HTTP/2 (Headers, Status Codes, Persistent Connection/Keep-Alive).
- Dasar-dasar Git, Docker, dan penggunaan terminal Unix/Linux.

---

### 3. Concept & Internal Architecture

Memindahkan aplikasi dari lingkungan pengembangan lokal ke skala produksi enterprise menuntut perubahan paradigma: dari "kode yang berjalan" menjadi "sistem yang tahan banting (*fault-tolerant*), dapat diobservasi (*observable*), dan dapat diskalakan (*scalable*)".

```
               [ INCOMING TRAFFIC: Client Apps / API Gateway ]
                                      │
                                      ▼
             ┌─────────────────────────────────────────────────┐
             │       REVERSE PROXY / LOAD BALANCER (Nginx)     │
             │   - TLS Termination   - Rate Limiting (Edge)    │
             └────────────────────────┬────────────────────────┘
                                      │ TCP (Keep-Alive)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ APPLICATION RUNTIME INSTANCE (Go / Linux Container)                     │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ PRIMARY ADAPTERS (DRIVING)                                        │  │
│  │  - HTTP Handlers (chi/gin)       - gRPC Server Handlers           │  │
│  │  - Context Injection (TraceID, Deadlines, Cancellation)           │  │
│  └─────────────────────────────────┬─────────────────────────────────┘  │
│                                    │ invokes methods via Ports          │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ APPLICATION CORE / USE CASES (Pure Logic)                         │  │
│  │  - Domain Entities               - Business Invariant Rules       │  │
│  │  - Orchestration Engine          - Transaction Boundaries         │  │
│  └─────────────────────────────────┬─────────────────────────────────┘  │
│                                    │ defines interfaces                 │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ SECONDARY ADAPTERS (DRIVEN)                                       │  │
│  │  - Resilience Layer: Circuit Breaker, Retries with Jitter         │  │
│  │  - Outbox Publisher              - Metrics/Telemetry Exporters    │  │
│  └────────────────┬───────────────────────────────┬──────────────────┘  │
└───────────────────┼───────────────────────────────┼─────────────────────┘
                    │ pgxpool                       │ go-redis pool
                    ▼                               ▼
       ┌─────────────────────────┐     ┌─────────────────────────┐
       │   PostgreSQL Database   │     │      Redis Cluster      │
       │  (Stateful Storage &    │     │  (Distributed Locks,    │
       │   Outbox Table)         │     │   Cache, Rate Limits)   │
       └─────────────────────────┘     └─────────────────────────┘
```

#### A. Arsitektur Heksagonal (Ports and Adapters)
Dalam arsitektur enterprise, kode bisnis (*domain core*) tidak boleh memiliki dependensi terhadap *library* eksternal seperti ORM, HTTP *framework*, atau driver SDK.
- **Port**: Interface abstrak yang mendefinisikan apa yang dibutuhkan oleh use-case (*driven port*) atau apa yang disediakan oleh use-case (*driving port*).
- **Adapter**: Implementasi konkret dari port tersebut. Contoh: PostgreSQL repository mengimplementasikan `OrderRepository` port. Jika database diganti dari PostgreSQL ke DynamoDB, lapisan domain sama sekali tidak tersentuh.

#### B. Anatomi Connection Pool & Socket Lifecycle
Koneksi TCP bersifat mahal: melibatkan 3-Way Handshake (`SYN` -> `SYN-ACK` -> `ACK`), autentikasi TLS, dan alokasi memori pada kernel OS (*socket buffer* `SO_RCVBUF`, `SO_SNDBUF`).
- **Connection Pool** mempertahankan sekumpulan socket TCP terbuka yang dapat digunakan kembali (*reused*).
- Status pool mencakup: `Idle` (siap digunakan), `Active` (sedang memproses query), `MaxLifetime` (menghindari memory leak/stale DNS pada server), dan `MaxIdleTime` (membersihkan koneksi yang menganggur terlalu lama).
- Jika beban aplikasi melebihi `MaxOpenConns`, *goroutine/thread* pemanggil akan masuk ke antrean *waiters*. Jika waktu tunggu melebihi timeout, *application runtime* melempar `ErrConnectionPoolExhausted`.

#### C. Mekanisme Graceful Shutdown
Ketika orkestrator (seperti Kubernetes) mengirim sinyal `SIGTERM`, alur internal proses wajib:
1. Menutup penerimaan *incoming connection* baru pada port HTTP/gRPC.
2. Membiarkan *in-flight requests* (yang sedang berjalan) selesai diproses hingga batas waktu toleransi (`context.WithTimeout`).
3. Menguras (*drain*) antrean pemrosesan latar belakang (*background workers*).
4. Melakukan commit/rollback pada transaksi basis data aktif.
5. Menutup koneksi database dan cache pool secara eksplisit.
6. Keluar (*exit*) dengan kode status 0.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Beginner) | Pendekatan Enterprise (Production-Ready) | Dampak Bisnis / Operasional |
| :--- | :--- | :--- | :--- |
| **Kopling Dependensi** | Handler HTTP langsung memanggil query SQL mentah / ORM global. | Inversi kontrol (*Dependency Injection*) via Hexagonal Ports & Adapters. | Modularitas tinggi; *unit testing* 100% terisolasi tanpa butuh DB hidup; migrasi infra mudah. |
| **Lifecycle Manajemen** | Proses dihentikan paksa via `SIGKILL` atau `os.Exit(0)`. | Penanganan *OS Signal* (`SIGTERM`/`SIGINT`) dengan batas *drain timeout*. | Menghindari data korup, transaksi menggantung (*orphan locks*), dan *HTTP 502 Bad Gateway* saat rolling update. |
| **Pengelolaan Koneksi** | Membuka koneksi per request atau pool default tanpa limitasi. | Tuning granular: `MaxOpenConns`, `MaxIdleConns`, `ConnMaxLifetime`, `HealthCheck`. | Menghindari *crash* pada DB akibat *max client connection exceeded* saat *traffic spike*. |
| **Penanganan Error Eksternal** | *Looping retry* instan tanpa jeda saat downstream API error. | *Circuit Breaker* (State: Closed, Open, Half-Open) + Backoff Eksponensial & Jitter. | Mencegah *Thundering Herd Problem* dan keruntuhan berantai (*cascading failure*). |
| **Pengiriman Event/Pesan** | Tulis ke DB, lalu panggil Kafka/RabbitMQ dalam blok terpisah. | *Transactional Outbox Pattern* dieksekusi dalam satu transaksi atomik DB. | Jaminan pengiriman *At-Least-Once*, mencegah inkonsistensi jika proses mati di tengah jalan. |

---

### 5. How (Workflow Detail)

Alur eksekusi request enterprise mengikuti siklus ketat:

```
[Inbound TCP] 
      │
      ▼
1. Transport Layer (Router/Middleware)
      ├─ Generate UUIDv4 / X-Request-ID (Tracing)
      ├─ Pasang Context Deadline / Timeout (e.g., 3000ms)
      └─ Rate Limiter Check (Token Bucket via Redis)
      │
      ▼
2. Primary Adapter (HTTP Controller)
      ├─ Payload Deserialization & Strict Schema Validation
      ├─ Mapping Request DTO ke Domain Command Object
      └─ Memanggil Port Use Case
      │
      ▼
3. Application Core (Use Case / Domain Service)
      ├─ Eksekusi Business Invariant Logic
      ├─ Membuka Unit-of-Work (Database Transaction)
      ├─ Memanggil Secondary Ports (Repository Interface)
      ├─ Menyimpan Event Domain ke Outbox Table
      └─ Commit Transaksi Database
      │
      ▼
4. Secondary Adapter (Database & Resilience Layer)
      ├─ Akuisisi koneksi dari Pool (dengan context timeout)
      ├─ Eksekusi query dengan parameterized SQL
      └─ Jika third-party: Bungkus dalam Circuit Breaker Execution
      │
      ▼
5. Background Worker (Asynchronous Outbox Processor)
      ├─ Polling / CDC membaca Outbox Table
      ├─ Publikasi event ke Broker Eksternal
      └─ Tandai Outbox Record sebagai 'PROCESSED'
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Bintang Lima

Bayangkan sebuah restoran bintang lima berstandar tinggi:
- **Primary Adapter (Pelayan)**: Berhadapan langsung dengan tamu. Mengambil pesanan dalam bahasa tamu (Inggris, Jepang, Indonesia) dan menerjemahkannya ke format standar dapur (*Order Slip*).
- **Domain Core (Kepala Koki / Chef)**: Hanya fokus pada satu hal: memasak resep autentik sesuai standar kualitas terbaik. Koki tidak peduli dari mana bahan didatangkan atau meja mana yang memesan.
- **Secondary Adapter (Pemasok / Logistik)**: Mengambil bahan makanan dari gudang pendingin (Database) atau pemasok luar (Third-Party API). Jika pasokan ikan salmon habis atau pemasok mengalami kebakaran, sistem pelindung (*Circuit Breaker*) menolak pesanan salmon sementara waktu tanpa menutup operasional restoran.
- **Graceful Shutdown**: Ketika jam operasional selesai, pintu restoran ditutup untuk pelanggan baru, tetapi pelanggan yang sedang makan diizinkan menyelesaikan makanan mereka hingga tuntas sebelum dapur dimatikan total.

#### State Machine Diagram: Circuit Breaker Pattern

```
                 Success Rate >= Threshold
                 ┌───────────────────────┐
                 │                       │
                 ▼                       │
         ┌───────────────┐        ┌──────────────┐
         │               │ Failure│              │
         │    CLOSED     ├───────►│     OPEN     │
         │ (Normal Ops)  │ Exceed │ (Fail Fast)  │
         │               │ Thresh.│              │
         └───────▲───────┘        └──────┬───────┘
                 │                       │
                 │ Success               │ Sleep Window
                 │ Exec.                 │ Expires
                 │                       ▼
         ┌───────┴───────────────────────────────┐
         │               HALF-OPEN               │
         │    (Canary Test: Limited Traffic)     │
         └───────────────────────────────────────┘
                 │
                 │ Single Failure Occurs
                 └────────────────────────────────► [ Kembali ke OPEN ]
```

---

### 7. Code Implementation: Simple vs Practical

#### A. Kode Naif (Anti-Pattern: Monolithic, tightly-coupled, no graceful shutdown)

```go
// ANTI-PATTERN: JANGAN DITIRU DI PRODUKSI
package main

import (
	"database/sql"
	"encoding/json"
	"net/http"
	_ "github.com/lib/pq"
)

var db *sql.DB

func main() {
	var err error
	// Anti-pattern: Hardcoded string, pool default tanpa batasan, koneksi global
	db, err = sql.Open("postgres", "postgres://user:pass@localhost:5432/orders?sslmode=disable")
	if err != nil {
		panic(err)
	}

	http.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) {
		// Anti-pattern: Logic, context, DB mixed in presentation layer
		var payload struct {
			UserID int     `json:"user_id"`
			Amount float64 `json:"amount"`
		}
		_ = json.NewDecoder(r.Body).Decode(&payload)

		// Anti-pattern: No timeout, raw SQL injection prone jika digabungkan manual
		_, err := db.Exec("INSERT INTO orders (user_id, amount) VALUES ($1, $2)", payload.UserID, payload.Amount)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		w.WriteHeader(201)
	})

	// Anti-pattern: os.Exit mendadak saat di-kill, request terputus di tengah jalan
	http.ListenAndServe(":8080", nil)
}
```

#### B. Kode Praktis Enterprise (Hexagonal, Resilient, Graceful Shutdown, Safe Concurrency)

Berikut adalah struktur kode yang modular dan menerapkan standar produksi:

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// ============================================================================
// 1. DOMAIN LAYER (Pure Enterprise Logic & Models)
// ============================================================================

type Order struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	CreatedAt time.Time `json:"created_at"`
}

var (
	ErrInvalidAmount = errors.New("domain: order amount must be greater than zero")
	ErrOrderNotFound = errors.New("domain: order not found")
)

// OrderRepository adalah Driven Port (Outbound)
type OrderRepository interface {
	Save(ctx context.Context, order *Order) error
	FindByID(ctx context.Context, id string) (*Order, error)
}

// OrderService adalah Driving Port (Inbound Interface)
type OrderService interface {
	CreateOrder(ctx context.Context, userID string, amount float64) (*Order, error)
}

type orderServiceImpl struct {
	repo           OrderRepository
	paymentBreaker *SimpleCircuitBreaker
}

func NewOrderService(repo OrderRepository, breaker *SimpleCircuitBreaker) OrderService {
	return &orderServiceImpl{
		repo:           repo,
		paymentBreaker: breaker,
	}
}

func (s *orderServiceImpl) CreateOrder(ctx context.Context, userID string, amount float64) (*Order, error) {
	if amount <= 0 {
		return nil, ErrInvalidAmount
	}

	order := &Order{
		ID:        fmt.Sprintf("ord-%d", time.Now().UnixNano()),
		UserID:    userID,
		Amount:    amount,
		CreatedAt: time.Now().UTC(),
	}

	// Eksekusi via Circuit Breaker (contoh interaksi dengan layanan pihak ketiga)
	err := s.paymentBreaker.Execute(func() error {
		// Mensimulasikan pemanggilan gateway pembayaran downstream
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("payment gateway unavailable: %w", err)
	}

	if err := s.repo.Save(ctx, order); err != nil {
		return nil, fmt.Errorf("failed to persist order: %w", err)
	}

	return order, nil
}

// ============================================================================
// 2. RESILIENCE: CIRCUIT BREAKER PATTERN (State Machine Engine)
// ============================================================================

type BreakerState int32

const (
	StateClosed BreakerState = iota
	StateHalfOpen
	StateOpen
)

type SimpleCircuitBreaker struct {
	state          int32
	failureCount   int32
	threshold      int32
	resetTimeout   time.Duration
	lastStateChange time.Time
	mu             sync.Mutex
}

func NewCircuitBreaker(threshold int32, resetTimeout time.Duration) *SimpleCircuitBreaker {
	return &SimpleCircuitBreaker{
		state:        int32(StateClosed),
		threshold:    threshold,
		resetTimeout: resetTimeout,
	}
}

func (cb *SimpleCircuitBreaker) Execute(operation func() error) error {
	cb.mu.Lock()
	state := BreakerState(atomic.LoadInt32(&cb.state))

	if state == StateOpen {
		if time.Since(cb.lastStateChange) > cb.resetTimeout {
			atomic.StoreInt32(&cb.state, int32(StateHalfOpen))
			cb.lastStateChange = time.Now()
		} else {
			cb.mu.Unlock()
			return errors.New("circuit breaker is OPEN: fast failure triggered")
		}
	}
	cb.mu.Unlock()

	err := operation()

	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		atomic.AddInt32(&cb.failureCount, 1)
		if atomic.LoadInt32(&cb.failureCount) >= cb.threshold {
			atomic.StoreInt32(&cb.state, int32(StateOpen))
			cb.lastStateChange = time.Now()
		}
		return err
	}

	// Jika sukses di fase Half-Open, reset ke Closed
	if BreakerState(atomic.LoadInt32(&cb.state)) == StateHalfOpen {
		atomic.StoreInt32(&cb.state, int32(StateClosed))
		atomic.StoreInt32(&cb.failureCount, 0)
	}
	return nil
}

// ============================================================================
// 3. SECONDARY ADAPTER: DATABASE INFRASTRUCTURE
// ============================================================================

type PostgresOrderRepository struct {
	db *sql.DB
}

func NewPostgresOrderRepository(db *sql.DB) *PostgresOrderRepository {
	return &PostgresOrderRepository{db: db}
}

func (r *PostgresOrderRepository) Save(ctx context.Context, o *Order) error {
	query := `INSERT INTO orders (id, user_id, amount, created_at) VALUES ($1, $2, $3, $4)`
	
	// Timeout enforcement context
	_, err := r.db.ExecContext(ctx, query, o.ID, o.UserID, o.Amount, o.CreatedAt)
	if err != nil {
		return err
	}
	return nil
}

func (r *PostgresOrderRepository) FindByID(ctx context.Context, id string) (*Order, error) {
	query := `SELECT id, user_id, amount, created_at FROM orders WHERE id = $1`
	row := r.db.QueryRowContext(ctx, query, id)

	var o Order
	if err := row.Scan(&o.ID, &o.UserID, &o.Amount, &o.CreatedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrOrderNotFound
		}
		return nil, err
	}
	return &o, nil
}

// ============================================================================
// 4. PRIMARY ADAPTER: HTTP TRANSPORT LAYER
// ============================================================================

type OrderHandler struct {
	service OrderService
}

func NewOrderHandler(s OrderService) *OrderHandler {
	return &OrderHandler{service: s}
}

type CreateOrderRequest struct {
	UserID string  `json:"user_id"`
	Amount float64 `json:"amount"`
}

func (h *OrderHandler) CreateOrderHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
		return
	}

	// Set context timeout per-request (SLA: Max 2 Detik)
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	var req CreateOrderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Malformed Request Body", http.StatusBadRequest)
		return
	}

	order, err := h.service.CreateOrder(ctx, req.UserID, req.Amount)
	if err != nil {
		if errors.Is(err, ErrInvalidAmount) {
			http.Error(w, err.Error(), http.StatusUnprocessableEntity)
			return
		}
		http.Error(w, "Internal Server Error: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(order)
}

// ============================================================================
// 5. INFRASTRUCTURE SETUP, RUNTIME CONFIG & GRACEFUL SHUTDOWN
// ============================================================================

func main() {
	log.Println("[BOOT] Memulai inisialisasi Enterprise Server...")

	// 1. Connection Pool Optimization
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://postgres:postgres@localhost:5432/app_db?sslmode=disable"
	}

	db, err := sql.Open("pgx", dsn)
	if err != nil {
		log.Fatalf("[FATAL] Gagal membuka koneksi DB: %v", err)
	}

	// Setting Pool Production Standard
	db.SetMaxOpenConns(50)                  // Maksimum koneksi aktif simultan
	db.SetMaxIdleConns(25)                  // Menjaga koneksi hangat tetap tersedia
	db.SetConnMaxLifetime(15 * time.Minute) // Mencegah memory leak & stale connection
	db.SetConnMaxIdleTime(5 * time.Minute)  // Recycle idle connection

	ctxPing, cancelPing := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancelPing()
	if err := db.PingContext(ctxPing); err != nil {
		log.Printf("[WARN] DB ping gagal (pastikan DB jalan saat run penuh): %v", err)
	}

	// 2. Wire Dependencies (Hexagonal Composition Root)
	breaker := NewCircuitBreaker(5, 10*time.Second)
	orderRepo := NewPostgresOrderRepository(db)
	orderSvc := NewOrderService(orderRepo, breaker)
	orderHandler := NewOrderHandler(orderSvc)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/orders", orderHandler.CreateOrderHTTP)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"UP"}`))
	})

	server := &http.Server{
		Addr:         ":8080",
		Handler:      mux,
		ReadTimeout:  5 * time.Second,  // Mencegah Slowloris attacks
		WriteTimeout: 10 * time.Second, // Timeout eksekusi response
		IdleTimeout:  120 * time.Second,
	}

	// 3. Graceful Shutdown Engine
	serverErrors := make(chan error, 1)
	go func() {
		log.Printf("[HTTP] Server berjalan mendengarkan port %s\n", server.Addr)
		serverErrors <- server.ListenAndServe()
	}()

	shutdownSig := make(chan os.Signal, 1)
	signal.Notify(shutdownSig, os.Interrupt, syscall.SIGTERM)

	select {
	case err := <-serverErrors:
		log.Fatalf("[FATAL] Server listener error: %v", err)

	case sig := <-shutdownSig:
		log.Printf("[SHUTDOWN] Sinyal penutupan diterima (%v). Menguras in-flight requests...", sig)

		// Berikan toleransi shutdown 20 detik
		ctxShutdown, cancelShutdown := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancelShutdown()

		// Stop listener, biarkan ongoing request selesai
		if err := server.Shutdown(ctxShutdown); err != nil {
			log.Printf("[ERROR] Gagal mematikan server secara normal: %v", err)
			_ = server.Close()
		}

		log.Println("[CLEANUP] Menutup koneksi database pool...")
		if err := db.Close(); err != nil {
			log.Printf("[ERROR] Error saat menutup database pool: %v", err)
		}

		log.Println("[EXIT] Semua resource dibersihkan. Server berhenti normal.")
	}
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Flash-Sale Ticketing Engine (100.000 Request/Detik)
- **Konteks**: Platform pemesanan tiket konser tingkat internasional menghadapi lonjakan trafik dari 200 RPS menjadi 100.000 RPS dalam 3 detik pertama saat penjualan tiket dibuka.
- **Masalah Utama**:
  1. *Database Connection Saturation*: PostgreSQL kolaps dalam 400ms pertama karena lonjakan 50.000 koneksi bersamaan meledakkan memori kernel (OOM Killed).
  2. *Cascading Failure*: Antrean request HTTP yang menumpuk membuat Nginx melempar `504 Gateway Timeout`, memicu ribuan pengguna menekan refresh berulang-ulang (*Thundering Herd*).
- **Arsitektur Solusi**:
  1. **Distributed Rate Limiting di Edge Layer**: Memasang Redis Token Bucket Cluster di depan Application Service. Hanya 5.000 request/detik yang diizinkan masuk ke *core processing*, sisanya menerima HTTP `429 Too Many Requests` secara instan tanpa menyentuh database.
  2. **Transactional Outbox & Asynchronous Queue**: Order dibuat dalam status `PENDING` di DB dalam transaksi atomik mini, kemudian di-push ke Apache Kafka melalui worker lokal Outbox CDC (*Change Data Capture* via Debezium).
  3. **Connection Pooling Hard Cap**: Membatasi `MaxOpenConns = 80` per instance backend dengan routing via PgBouncer dalam mode *Transaction Pooling*. Utilisasi resource server DB stabil pada 45% CPU, tanpa ada koneksi yang terputus.

---

### 9. Trade-offs Analysis

```
                              [ ARCHITECTURE DECISIONS ]
                                          │
                 ┌────────────────────────┴────────────────────────┐
                 ▼                                                 ▼
        [ HEXAGONAL ARCHITECTURE ]                       [ ACTIVE-WAIT POOLING ]
        Pros:                                            Pros:
        - Pemisahan domain murni                         - Utilisasi DB terkendali
        - Unit test tanpa DB container                   - Perlindungan terhadap crash OOM
        Cons:                                            Cons:
        - Boilerplate tinggi (banyak DTO & interface)    - Menambah antrean latency jika pool jenuh
        - Learning curve curam bagi junior               - Memerlukan tuning adaptif rumit
```

| Pendekatan / Pola | Parameter | Nilai Positif (Gains) | Biaya / Konsekuensi (Costs) |
| :--- | :--- | :--- | :--- |
| **Hexagonal Architecture** | Maintainability & Testing | Unit test decoupling 100%, domain logic bersih dari framework. | Memerlukan mapping berulang antara DTO, Domain Entities, dan SQL models (Memory allocation overhead). |
| **Circuit Breaker** | Fault Tolerance | Mencegah resource exhaustion downstream dan memotong rantai kegagalan. | Data menjadi *eventually consistent*; memunculkan kegagalan eksplisit yang harus ditangani UI/Client. |
| **Transactional Outbox** | Reliability (At-Least-Once) | Konsistensi data 100% tanpa dual-write HTTP/Kafka yang rentan gagal. | Latensi asinkron: event tidak langsung tersedia; tabel Outbox memerlukan background pruning/vacuum rutin. |
| **Strict Connection Caps** | Infrastructure Stability | PostgreSQL aman dari ancaman starvation dan OOM. | Request pada saat jam sibuk akan mengalami lonjakan *p99 latency* karena harus mengantre slot pool. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Goroutine / Thread Leakage pada Background Task
- **Penyebab**: Menjalankan goroutine tanpa propagasi `context.Context` atau channel pembatalan saat shutdown.
- **Dampak**: Memory leak linier hingga OS mengeksekusi OOM Killer terhadap container.
- **Solusi**: Gunakan pola `sync.WaitGroup` terintegrasi dengan penutupan `ctx.Done()`.

#### 2. Konfigurasi `MaxIdleConns` Terlalu Kecil
- **Penyebab**: Menetapkan `MaxOpenConns = 100` tetapi membiarkan `MaxIdleConns = 2` (nilai default di banyak driver).
- **Dampak**: Setiap kali lonjakan trafik turun naik tipis, pool akan membuka dan menutup koneksi TCP secara agresif (*TCP Handshake Churn*), menyebabkan utilisasi CPU tinggi pada database engine.
- **Solusi**: Tetapkan `MaxIdleConns` setidaknya setara dengan 50% hingga 100% dari `MaxOpenConns`.

#### 3. SQL Prepared Statement Leak
- **Penyebab**: Memanggil `db.Prepare()` di dalam scope handler HTTP tanpa pernah memanggil `stmt.Close()`.
- **Dampak**: Batas limit open files pada sistem operasi terlampaui (`too many open files` error).
- **Solusi**: Gunakan `db.QueryContext` langsung (yang mengelola deallokasi otomatis) atau pastikan `defer stmt.Close()` dieksekusi secara ketat.

---

### 11. Best Practices (Production Checklist)

- [ ] **Context Propagation**: Setiap method I/O (Database, Cache, HTTP call) wajib menerima `ctx context.Context` sebagai argumen pertama.
- [ ] **Fail Fast with Deadlines**: Terapkan batas waktu maksimal pada setiap koneksi keluar (*downstream SLA*).
- [ ] **Explicit Schema Migration**: Gunakan migrasi terkontrol versioning (seperti `golang-migrate`, `Flyway`, atau `Liquibase`). Jangan pernah mengandalkan skema Auto-DDL ORM di production.
- [ ] **Liveness & Readiness Separation**:
  - `/healthz/live`: Mengembalikan 200 selama proses runtime hidup.
  - `/healthz/ready`: Mengembalikan 200 hanya jika connection pool DB dan broker siap menerima trafik.
- [ ] **Structured Logging & Tracing**: Keluarkan log berformat JSON terstruktur yang memuat atribut `trace_id`, `span_id`, `environment`, dan `user_id`.

---

### 12. Hands-on Practice

Buat dan uji modul produksi mandiri di dalam direktori `hands-on/m02/`.

#### Langkah 1: Persiapan Lingkungan
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
go mod init enterprise-core
go get github.com/jackc/pgx/v5/stdlib
```

#### Langkah 2: Setup Database Lokal via Docker
Jalankan PostgreSQL container dengan limitasi koneksi rendah untuk simulasi beban:
```bash
docker run --name pg-test -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=app_db -p 5432:5432 -d postgres:16-alpine -N 50
```

Buat tabel pesanan:
```bash
docker exec -i pg-test psql -U postgres -d app_db <<EOF
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
EOF
```

#### Langkah 3: Eksekusi File Utama
Salin implementasi kode pada **Seksi 7.B** ke dalam file `main.go`. Jalankan service:
```bash
go run main.go
```

#### Langkah 4: Pengujian Graceful Shutdown
1. Buka terminal baru dan kirim request simultan berulang menggunakan curl:
   ```bash
   curl -X POST http://localhost:8080/api/v1/orders \
     -H "Content-Type: application/json" \
     -d '{"user_id": "usr-101", "amount": 250000}'
   ```
2. Kembali ke terminal server, tekan `CTRL+C` (`SIGINT`).
3. Amati log: Listener langsung berhenti menerima koneksi baru, namun koneksi yang sedang dieksekusi diselesaikan secara tuntas sebelum koneksi DB di-close.

---

### 13. Exercises

#### Level Easy
Tulis sebuah middleware HTTP di Go yang mengekstrak HTTP header `X-Request-ID`. Jika header tersebut tidak dikirim oleh client, middleware harus menginisiasi ID acak baru (UUID/ULID) dan menyimpannya ke dalam `r.Context()` sehingga dapat dibaca oleh domain log downstream.

#### Level Medium
Tambahkan mekanisme *Exponential Backoff with Full Jitter* pada implementasi `PostgresOrderRepository.Save`. Jika query gagal akibat transaksi bentrok (*serialization failure* / Deadlock code `40P01`), lakukan percobaan ulang maksimal 3 kali dengan formula jeda:  
`Sleep = rand(0, Min(MaxJitter, BaseBackoff * 2^attempt))`

#### Level Hard
Rancang dan implementasikan abstraksi *Transactional Outbox Pattern*:
1. Saat pesanan disimpan di DB, simpan juga payload JSON event ke dalam tabel `outbox_events` dalam **satu transaksi database atomik yang sama**.
2. Buat background worker terpisah berbasis goroutine yang berjalan setiap 500ms, mengambil event yang berstatus `UNPROCESSED`, mencetaknya ke konsol (*mock broker publish*), dan memperbarui status event menjadi `PROCESSED`.
3. Pastikan worker berhenti secara anggun (*gracefully*) saat `SIGTERM` diterima tanpa memotong pemrosesan event yang sedang berjalan.

---

### 14. Architecture Challenge

**Skenario**: Anda memimpin tim arsitektur backend untuk dompet digital (*e-wallet*). Sistem Anda harus memproses pencairan dana (*disbursement*) ke 15 bank mitra yang berbeda. 

**Kondisi Nyata**:
- API bank mitra sering mengalami waktu henti (*downtime*) mendadak atau *slow response* hingga 60 detik per panggilan.
- Kegagalan sistemik downstream tidak boleh menyebabkan saldo pengguna terpotong ganda (*double spending*) atau sistem backend kehabisan thread worker.
- Sistem harus mampu memproses antrean jutaan transaksi secara idempoten saat bank mitra pulih kembali.

**Tugas Arsitektur**:
Rancang blueprint arsitektur sistem backend lengkap tanpa menggunakan framework instan. Buat dokumentasi teknis yang memuat:
1. Diagram alur data pemrosesan pembayaran dari API Gateway hingga integrasi mitra.
2. Penjelasan mekanisme State Machine transaksi (dari `INITIATED`, `PENDING_PARTNER`, hingga status akhir).
3. Strategi partisi database, distributed locking (menggunakan Redis Redlock atau PostgreSQL Advisory Lock), serta mitigasi *split-brain*.
4. Solusi idempotesi jika mitra bank mengirim respons HTTP `500 Internal Error` namun sebenarnya transfer di sistem perbankan mereka berhasil dieksekusi.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa pada Arsitektur Heksagonal kode lapisan domain inti (*core domain*) tidak boleh mengimpor package infrastruktur database?
2. Apa bahaya utama langsung mematikan proses backend Linux menggunakan perintah sinyal `kill -9` (`SIGKILL`) di lingkungan produksi?
3. Sebutkan perbedaan fungsi konfigurasi `SetMaxOpenConns` dan `SetMaxIdleConns` pada koneksi basis data!
4. Apa yang dimaksud dengan status *Half-Open* pada pola ketahanan *Circuit Breaker*?
5. Mengapa context deadline/timeout wajib diinjeksikan pada setiap request SQL?

#### B. Pertanyaan Intermediate
1. Bagaimana cara kerja algoritma *Exponential Backoff with Full Jitter* mencegah *Thundering Herd Problem* pada sistem terdistribusi?
2. Pada skenario apa isolasi transaksi basis data `SERIALIZABLE` lebih dipilih dibandingkan `READ COMMITTED`, dan apa trade-off performa yang harus dibayar?
3. Mengapa *Dual-Write* (menulis ke PostgreSQL kemudian langsung memanggil method publish ke RabbitMQ secara berurutan) adalah sebuah *anti-pattern* fatal dalam sistem perbankan?
4. Bagaimana mekanisme kernel OS Linux menangani soket koneksi aplikasi saat terjadi status *TCP TIME_WAIT*?
5. Mengapa kita harus membatasi batas pembacaan body pada request HTTP menggunakan utilitas semacam `http.MaxBytesReader`?

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Sebuah aplikasi backend e-commerce menggunakan Kubernetes. Setiap kali dilakukan deployment versi baru (*rolling update*), pengguna melaporkan adanya spike error `HTTP 502 Bad Gateway` selama rentang waktu 5 detik. Dari perspektif lifecycle proses dan networking load balancer, apa akar masalahnya dan bagaimana memperbaikinya?
2. **Skenario 2**: Metrik PostgreSQL menunjukkan lonjakan koneksi hingga mencapai limit `max_connections = 100`, sementara utilisasi CPU DB mendekati 100%. Namun, throughput aplikasi (RPS) justru turun drastis ke titik terendah. Analisis fenomena apa yang sedang terjadi dan bagaimana rencana mitigasi arsitekturalnya!
3. **Skenario 3**: Worker background Outbox Pattern Anda mengalami kegagalan crash mendadak tepat setelah mempublikasikan pesan ke Apache Kafka, tetapi sebelum sempat memperbarui baris status di database dari `UNPROCESSED` ke `PROCESSED`. Apa akibatnya pada sistem konsumen downstream, dan prinsip teknis apa yang wajib diterapkan pada sisi consumer untuk menanggulanginya?

---

### Kunci Jawaban & Evaluasi

#### Jawaban Basic
1. Agar domain logika bisnis murni tidak terikat (*tightly coupled*) pada vendor atau driver tertentu. Ini memungkinkan unit testing cepat menggunakan *mock object* tanpa infrastruktur asli dan mencegah perubahan library luar merusak aturan bisnis inti.
2. `SIGKILL` menghentikan proses secara instan di level kernel OS tanpa memberi kesempatan aplikasi menutup transaksi database, menghapus temporary files, menguras request aktif, atau melepaskan lock distributed. Hal ini berisiko tinggi memicu korupsi data.
3. `SetMaxOpenConns` membatasi jumlah total soket koneksi aktif fisik yang dapat dibuka ke database untuk mencegah server kehabisan memori. `SetMaxIdleConns` mengatur jumlah soket koneksi tidak aktif yang tetap dibiarkan hidup di dalam pool agar request berikutnya tidak perlu membayar biaya latency *TCP Handshake*.
4. *Half-Open* adalah fase uji coba di mana sirkuit breaker mengizinkan sebagian kecil trafik percobaan (*canary request*) melewati sistem downstream setelah masa *sleep window* berakhir. Tujuannya adalah menguji secara aman apakah upstream service sudah benar-benar pulih sebelum membuka lalu lintas secara penuh.
5. Context timeout memastikan bahwa jika query database mengalami locking atau query lambat (*slow query*), query tersebut akan dibatalkan secara otomatis setelah batas SLA terlampaui. Ini membebaskan thread backend dan mencegah terjadinya antrean request yang membekukan seluruh sistem.

#### Jawaban Intermediate
1. Exponential backoff melipatgandakan waktu tunggu pada setiap kegagalan berulang. Full Jitter menyisipkan faktor random (acak) dari interval 0 hingga batas maksimum backoff. Variasi waktu tunggu acak ini memecah gelombang request klien agar tidak menyerang downstream service pada milidetik yang sama secara serentak.
2. `SERIALIZABLE` mencegah anomali *phantom reads* dan *write skew* dengan menjamin transaksi dieksekusi seolah-olah berjalan secara serial murni. Trade-off: Menurunkan throughput secara tajam karena frekuensi transaction abort/rollback meningkat pesat saat terjadi bentrokan konkurensi data yang sama.
3. Operasi tersebut tidak bersifat atomik (*Non-Atomic*). Jika operasi tulis ke database berhasil namun server mati atau koneksi jaringan ke broker putus sebelum pesan terkirim ke RabbitMQ, sistem akan mengalami inkonsistensi status (*phantom state*) yang tidak bisa di-rollback secara otomatis.
4. Status `TIME_WAIT` dikelola oleh kernel untuk memastikan paket TCP data yang terlambat (*delayed/duplicate segments*) di internet tidak salah diterima oleh koneksi baru yang menggunakan nomor port yang sama. Soket akan ditahan selama durasi `2 * MSL` (Maximum Segment Lifetime) sebelum kernel mendaur ulang port tersebut.
5. Untuk memitigasi serangan *Denial of Service (DoS)* berbasis memory exhaustion. Tanpa limitasi pembacaan body, penyerang dapat mengirim payload berukuran gigabyte yang memaksa memory allocator backend mengalokasikan RAM hingga terjadi crash (*Out-of-Memory*).

#### Jawaban Skenario Kasus Produksi
1. **Akar Masalah**: Pod lama langsung dimatikan oleh Kubernetes sebelum Nginx/Ingress Controller mencabut IP Pod tersebut dari routing endpoint-nya, atau aplikasi langsung berhenti tanpa menguras *in-flight requests*.  
   **Solusi**: Terapkan implementasi *Graceful Shutdown* di aplikasi backend dengan delay penutupan soket, gunakan lifecycle hook `preStop` (misal sleep 5 detik) di konfigurasi Kubernetes Pod spec agar Ingress sempat memperbarui endpoint table sebelum aplikasi mematikan socket listener, serta pastikan `readinessProbe` dikonfigurasi dengan benar.
2. **Akar Masalah**: Fenomena *Connection Saturation & CPU Thrashing*. Terlalu banyak koneksi aktif yang berebut core CPU database menyebabkan OS context switching overhead melumpuhkan komputasi sebenarnya, diperparah oleh kemungkinan *lock contention* antar transaksi lambat.  
   **Solusi**: Segera turunkan `MaxOpenConns` di backend pool. Pasang connection pooler perantara seperti PgBouncer dengan *Transaction Pooling mode*. Identifikasi query yang mengalami bottleneck via `pg_stat_activity` dan pasang kill timeout (`statement_timeout = 3000ms`) pada PostgreSQL engine.
3. **Konsekuensi**: Saat worker Outbox hidup kembali, ia akan membaca ulang baris yang masih berstatus `UNPROCESSED` tersebut dan mengirimkannya kembali ke Kafka. Konsumen akan menerima pesan yang sama sebanyak dua kali (*Duplicate Delivery*).  
   **Solusi**: Sesuai dengan jaminan distribusi *At-Least-Once Delivery*, sistem consumer downstream wajib bersifat **Idempoten**. Consumer harus menggunakan pola *Idempotent Consumer* (misal memeriksa tabel `processed_messages` menggunakan unique `message_id` dalam transaksi bisnisnya) sehingga event duplikat yang masuk akan diabaikan tanpa merusak state data.

---

### 16. Summary

1. **Hexagonal Architecture** memisahkan dependensi infrastruktur dari domain bisnis inti, menjamin kode mudah diuji (*testable*) dan mudah dimodernisasi tanpa merusak logika aplikasi utama.
2. **Connection Pooling** bukanlah konfigurasi bebas batas; pool harus dibatasi secara ketat untuk melindungi infrastruktur basis data dari *saturation crash* dan *context-switching thrashing*.
3. **Graceful Shutdown** adalah prasyarat mutlak arsitektur cloud-native/enterprise untuk menjamin zero-downtime rolling update dan integritas data saat proses runtime dihentikan.
4. **Resilience Engineering** (Circuit Breakers, Retries with Jitter, Deadlines) adalah mekanisme pertahanan utama untuk menahan kegagalan downstream agar tidak merembet menjadi pemadaman sistem total (*cascading failure*).
5. **Transactional Outbox Pattern** menyelesaikan dilema klasik konsistensi data terdistribusi antara database dan message broker, memberikan jaminan keandalan pengiriman pesan berbasis *At-Least-Once*.