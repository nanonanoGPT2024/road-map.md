# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 04-Backend-and-Database | **Bab 01:** Fondasi dan Arsitektur

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengisolasi Core Domain:** Mengimplementasikan pola *Hexagonal Architecture (Ports and Adapters)* dan *Domain-Driven Design (DDD) Tactical Patterns* untuk memisahkan aturan bisnis murni dari dependensi infrastruktur dan framework.
- **Membangun Resiliensi Transaksional:** Mengimplementasikan *Transactional Outbox Pattern* dan *Idempotency Keys* guna menjamin konsistensi data (*Eventual Consistency*) tanpa *distributed two-phase commit (2PC)*.
- **Mengoptimalkan Concurrency & Resource Management:** Mengelola konkurensi tingkat lanjut menggunakan Go runtime primitives (*Worker Pools*, *Context Propagation*, *Non-blocking Channel Operations*) serta mencegah *resource starvation* dan *goroutine leaks*.
- **Menerapkan Production-Grade Lifecycle:** Mengonfigurasi *Graceful Shutdown*, *Health Check Probes (Liveness/Readiness)*, serta *Circuit Breaker* untuk integrasi upstream/downstream berlatensi tinggi.

---

## 2. Prerequisite
Untuk memahami materi ini secara optimal, peserta wajib menguasai:
- **Dasar Rekayasa Perangkat Lunak Backend:** Pemahaman HTTP/2, RESTful API, TCP/IP handshake, dan relasional database (ACID properties, isolation levels).
- **Bahasa Pemrograman Go (Golang):** Sintaks dasar, *struct*, *interface*, *pointers*, *goroutine*, dan *channels* (versi Go 1.21+).
- **Tooling:** Docker & Docker Compose, PostgreSQL 15+, Make/Taskfile, dan Git.
- **Mental Model:** Pemahaman bahwa arsitektur monolitik modular mendahului microservices; kegagalan jaringan (*network partition*) adalah kepastian, bukan anomali.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Hexagonal Architecture (Ports & Adapters) & Clean Architecture
Arsitektur Hexagonal menempatkan domain bisnis di pusat sistem, terisolasi dari protokol pengiriman (HTTP, gRPC, CLI) dan media penyimpanan (PostgreSQL, Redis, Kafka).

```
+--------------------------------------------------------------------------+
|                        INFRASTRUCTURE LAYER                              |
|                                                                          |
|   +-----------------------+              +---------------------------+   |
|   |   Driving Adapters    |              |     Driven Adapters       |   |
|   |  (HTTP, gRPC, Cron)   |              |  (Postgres, Redis, Kafka) |   |
|   +-----------+-----------+              +-------------^-------------+   |
|               |                                        |                 |
+---------------|----------------------------------------|-----------------+
| APPLICATION   |                                        |                 |
|               v                                        |                 |
|        +--------------+                        +-------+-------+         |
|        | Driving Port |                        |  Driven Port  |         |
|        | (Use Cases)  |                        | (Repositories)|         |
|        +-------+------+                        +-------^-------+         |
|                |                                       |                 |
+----------------|---------------------------------------|-----------------+
| DOMAIN         v                                       |                 |
|        +-----------------------------------------------+-----+           |
|        |  Domain Services, Entities, Aggregates, Value Obj   |           |
|        +-----------------------------------------------------+           |
+--------------------------------------------------------------------------+
```

1. **The Domain Core:** Berisi entitas bisnis murni. Tidak boleh mengimpor package eksternal seperti `database/sql`, `net/http`, atau library pihak ketiga. Domain hanya memvalidasi *invariants* (aturan bisnis mutlak).
2. **Ports:** Merupakan interface Go.
   - **Driving Port (Inbound):** Kontrak yang diekspos domain untuk dieksekusi oleh dunia luar (misal: `CreateOrderUseCase`).
   - **Driven Port (Outbound):** Kontrak yang dibutuhkan domain untuk berinteraksi dengan dunia luar (misal: `OrderRepository`, `PaymentGatewayPort`).
3. **Adapters:** Implementasi konkret dari Ports.
   - **Driving Adapter:** Menerima input dari luar, mengonversinya menjadi format domain, lalu memanggil Inbound Port (misal: HTTP Handler, gRPC Handler).
   - **Driven Adapter:** Mengimplementasikan Outbound Port menggunakan teknologi spesifik (misal: `PostgresOrderRepository` yang mengimplementasikan `OrderRepository`).

### 3.2 Transactional Outbox Pattern
Komunikasi asynchronous antar-layanan sering kali mengalami *dual-write problem*: data tersimpan di DB, namun aplikasi crash sebelum event terkirim ke Message Broker (Kafka/RabbitMQ), mengakibatkan desinkronisasi data.

```
+----------------------------------------------------------------------------+
|                          DATABASE TRANSACTION BOUNDARY                     |
|                                                                            |
|  BEGIN TRANSACTION;                                                        |
|    INSERT INTO orders (id, customer_id, total, status) VALUES (...);       |
|    INSERT INTO outbox_events (id, aggregate_type, payload, status)         |
|         VALUES ('evt-1', 'Order', '{"id": "...", ...}', 'PENDING');        |
|  COMMIT;                                                                   |
+-------------------------------------+--------------------------------------+
                                      |
                                      v Polling / WAL CDC (Debezium)
                       +-------------------------------+
                       |   Outbox Processor / Worker   |
                       +---------------+---------------+
                                       |
                                       v Publish
                       +-------------------------------+
                       |  Message Broker (Kafka/NATS)  |
                       +-------------------------------+
```

Dengan mengeksekusi mutasi domain dan pencatatan event dalam **satu transaksi database lokal (ACID)**, kita menjamin garansi *at-least-once delivery*. Message Relay Worker kemudian membaca tabel `outbox_events` dan mempublikasikannya ke Message Broker.

### 3.3 Concurrency Control & Memory Footprint di Go Runtime
Go menggunakan M:N scheduler (GMP Model: Goroutine, Machine/OS Thread, Processor). 
- Setiap goroutine dialokasikan memori awal sebesar 2 KB pada execution stack, yang tumbuh dan menyusut secara dinamis di heap.
- Pembuatan goroutine yang tidak dibatasi (*unbounded concurrency*) pada traffic tinggi (100k+ RPS) akan memicu lonjakan alokasi memori heap, menyebabkan latensi *Stop-The-World (STW)* Garbage Collector (GC) melonjak.
- **Solusi Produksi:** Gunakan *bounded worker pool* dengan buffered channels atau semaphore pattern untuk mengontrol penggunaan resource OS dan database connection pool saturation.

---

## 4. Why & What

| Dimensi | Pendekatan Naif / Tradisional (Anemic CRUD) | Pendekatan Enterprise Produksi (Hexagonal + DDD + Outbox) |
| :--- | :--- | :--- |
| **Pemisahan Modul** | Controller langsung memanggil ORM/ActiveRecord; business logic tersebar di handler. | Business logic terisolasi murni di Core Domain; framework dan DB bersifat pluggable. |
| **Ketergantungan DB** | Terikat erat pada skema database; refaktor DB merusak API contract. | Domain tidak tahu apakah datanya disimpan di PostgreSQL, MongoDB, atau Memory. |
| **Integritas Distribusi** | Dual-write langsung ke DB dan Message Broker (rawan *silent failure* saat network drop). | *Transactional Outbox*: Menjamin pengiriman event 100% konsisten terhadap state DB. |
| **Skalabilitas Concurrency**| Membuat `go func()` secara bebas di dalam handler API tanpa batas pool. | *Bounded Worker Pools* dengan *context cancellation* dan *backpressure signaling*. |
| **Testabilitas** | Harus menyalakan database container atau mock query SQL rumit untuk unit test. | Unit test berjalan murni di memori (in-memory adapter mock), eksekusi instan dalam milidetik. |

---

## 5. How (Workflow Detail)

Alur eksekusi request pembayaran pada arsitektur produksi:

1. **Ingestion & Inbound Translation:**
   - Klien mengirim payload `POST /v1/orders/checkout` dengan header `Idempotency-Key`.
   - Driving Adapter (HTTP Middleware) memvalidasi `Idempotency-Key`. Jika sudah diproses, langsung kembalikan cached response dari Redis.
   - HTTP Handler mendeserialisasi JSON, memvalidasi format primitif, dan memetakan DTO ke Domain Command.
2. **Domain Execution:**
   - Use Case (Inbound Port) mengambil Aggregates melalui Outbound Port (Repository).
   - Domain Aggregate mengeksekusi logika bisnis: memvalidasi status, menghitung total, memeriksa invariant, dan menghasilkan `OrderCreatedDomainEvent`.
3. **Transactional Persistence:**
   - Repository membungkus mutasi Aggregate dan serialisasi Domain Event ke dalam tabel `outbox` dalam **satu transaksi DB**.
   - Transaksi di-commit. Jika gagal, seluruh operasi di-rollback.
4. **Asynchronous Dispatching:**
   - Outbox Processor (Background Worker terpisah) membaca event bertatus `PENDING` dengan locking (`SELECT ... FOR UPDATE SKIP LOCKED`).
   - Worker mengirim event ke Kafka.
   - Setelah mendapatkan ACK dari Kafka, worker memperbarui status event menjadi `PUBLISHED`.
5. **Observability & Response:**
   - Metrik Prometheus dicatat (durasi request, counter transaksi).
   - HTTP status `202 Accepted` atau `201 Created` dikembalikan ke klien dengan payload DTO.

---

## 6. Analogy & Diagram ASCII

### Analogi Real-World: Bandara Internasional
- **The Core Domain:** Ruang Kendali Lalu Lintas Udara (Air Traffic Control / ATC). Aturan ATC murni mengatur keselamatan jarak terbang, kuota runway, dan jadwal bahan bakar. ATC tidak peduli penumpang datang ke bandara naik bus, kereta, atau mobil pribadi.
- **Driving Adapters:** Gerbang kedatangan penumpang (stasiun kereta bandara, terminal bus, drop-off taksi). Mereka memeriksa tiket, memvalidasi paspor fisik, lalu mentransfer penumpang ke antrean keberangkatan.
- **Driven Adapters:** Truk pengisi bahan bakar, staf bagasi, katering. Mereka adalah vendor eksternal yang dihubungi ATC via radio/telekomunikasi (Ports/Interfaces). Vendor bisa diganti kapan saja tanpa mengubah tata kelola penerbangan ATC.

### Arsitektur Data Flow & Transaksi Outbox
```
Client Request
     |
     v
[HTTP Handler (Driving Adapter)]
     |
     | Translates HTTP Payload -> Domain Command
     v
[OrderUseCase (Inbound Port)]
     |
     | 1. Loads Aggregate
     v
[OrderAggregate (Domain Core)] <---> Enforces Business Invariants
     |
     | 2. Appends Domain Event
     v
[OrderRepository (Driven Adapter)]
     |
     +--- BEGIN DB TX ------------------------------------------+
     |                                                          |
     |   INSERT INTO orders (...) VALUES (...);                 |
     |   INSERT INTO outbox (event_id, payload) VALUES (...);   |
     |                                                          |
     +--- COMMIT DB TX -----------------------------------------+
     |
     v
Response 201 Created -> Client

                               --- ASYNCHRONOUS WORKER ---

[Background Outbox Processor]
     |
     | 1. SELECT * FROM outbox WHERE status = 'PENDING' FOR UPDATE SKIP LOCKED;
     v
[Publish to Message Broker (Kafka)]
     |
     | 2. ACK received from Kafka
     v
[UPDATE outbox SET status = 'PUBLISHED' WHERE event_id = ...]
```

---

## 7. Simple Example & Practical Example

Struktur direktori modul backend enterprise:
```text
m02-backend/
├── cmd/
│   └── api/
│       └── main.go
├── internal/
│   ├── core/
│   │   ├── domain/
│   │   │   ├── order.go
│   │   │   └── errors.go
│   │   └── ports/
│   │       ├── repositories.go
│   │       └── usecases.go
│   └── adapters/
│       ├── handlers/
│       │   └── http_order.go
│       └── storage/
│           └── postgres_order.go
└── pkg/
    └── workerpool/
        └── pool.go
```

### 7.1 Core Domain Layer (Tanpa Dependensi Framework/DB)
File: `internal/core/domain/order.go`
```go
package domain

import (
	"errors"
	"time"
)

var (
	ErrInvalidAmount    = errors.New("order amount must be greater than zero")
	ErrOrderAlreadyPaid = errors.New("cannot pay an order that is already paid or cancelled")
)

type OrderID string
type CustomerID string
type OrderStatus string

const (
	StatusPending   OrderStatus = "PENDING"
	StatusPaid      OrderStatus = "PAID"
	StatusCancelled OrderStatus = "CANCELLED"
)

type OrderItem struct {
	ProductID string
	Quantity  int
	Price     float64
}

// Order adalah Root Aggregate
type Order struct {
	ID        OrderID
	CustomerID CustomerID
	Items     []OrderItem
	Total     float64
	Status    OrderStatus
	CreatedAt time.Time
	UpdatedAt time.Time
}

// Invariant Enforcement
func NewOrder(id OrderID, customerID CustomerID, items []OrderItem) (*Order, error) {
	if len(items) == 0 {
		return nil, errors.New("order must contain at least one item")
	}

	var total float64
	for _, item := range items {
		if item.Quantity <= 0 || item.Price <= 0 {
			return nil, ErrInvalidAmount
		}
		total += float64(item.Quantity) * item.Price
	}

	now := time.Now().UTC()
	return &Order{
		ID:         id,
		CustomerID: customerID,
		Items:      items,
		Total:      total,
		Status:     StatusPending,
		CreatedAt:  now,
		UpdatedAt:  now,
	}, nil
}

func (o *Order) MarkAsPaid() error {
	if o.Status != StatusPending {
		return ErrOrderAlreadyPaid
	}
	o.Status = StatusPaid
	o.UpdatedAt = time.Now().UTC()
	return nil
}
```

### 7.2 Outbound Ports (Interfaces)
File: `internal/core/ports/repositories.go`
```go
package ports

import (
	"context"
	"m02-backend/internal/core/domain"
)

type OutboxEvent struct {
	ID            string
	AggregateType string
	AggregateID   string
	Payload       []byte
	CreatedAt     int64
}

// OrderRepository mendefinisikan Driven Port untuk persistensi
type OrderRepository interface {
	SaveOrderWithOutbox(ctx context.Context, order *domain.Order, event *OutboxEvent) error
	FindByID(ctx context.Context, id domain.OrderID) (*domain.Order, error)
}
```

### 7.3 Driven Adapter: PostgreSQL Repository dengan Transactional Outbox
File: `internal/adapters/storage/postgres_order.go`
```go
package storage

import (
	"context"
	"database/sql"
	"fmt"
	"m02-backend/internal/core/domain"
	"m02-backend/internal/core/ports"
)

type PostgresOrderRepository struct {
	db *sql.DB
}

func NewPostgresOrderRepository(db *sql.DB) *PostgresOrderRepository {
	return &PostgresOrderRepository{db: db}
}

func (r *PostgresOrderRepository) SaveOrderWithOutbox(ctx context.Context, order *domain.Order, event *ports.OutboxEvent) error {
	// Membuka database transaction ACID
	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to begin tx: %w", err)
	}
	defer tx.Rollback() // Rollback otomatis jika tidak di-commit

	// 1. Simpan Domain Aggregate
	orderQuery := `
		INSERT INTO orders (id, customer_id, total, status, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6)
	`
	_, err = tx.ExecContext(ctx, orderQuery,
		order.ID, order.CustomerID, order.Total, order.Status, order.CreatedAt, order.UpdatedAt)
	if err != nil {
		return fmt.Errorf("failed to insert order: %w", err)
	}

	// 2. Simpan Outbox Event dalam transaksi yang sama
	outboxQuery := `
		INSERT INTO outbox_events (id, aggregate_type, aggregate_id, payload, created_at, status)
		VALUES ($1, $2, $3, $4, $5, 'PENDING')
	`
	_, err = tx.ExecContext(ctx, outboxQuery,
		event.ID, event.AggregateType, event.AggregateID, event.Payload, event.CreatedAt)
	if err != nil {
		return fmt.Errorf("failed to insert outbox event: %w", err)
	}

	// Commit Transaksi
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit tx: %w", err)
	}

	return nil
}

func (r *PostgresOrderRepository) FindByID(ctx context.Context, id domain.OrderID) (*domain.Order, error) {
	// Implementasi query baca
	return nil, nil // disederhanakan untuk ringkasan contoh
}
```

### 7.4 Production Resilient Entry Point: Graceful Shutdown & Context Propagation
File: `cmd/api/main.go`
```go
package main

import (
	"context"
	"database/sql"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	// Root Context dengan lifecycle tracking
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Inisialisasi Database Connection Pool
	db, err := sql.Open("postgres", "postgres://user:pass@localhost:5432/db?sslmode=disable")
	if err != nil {
		log.Fatalf("Critical: failed to init DB: %v", err)
	}
	db.SetMaxOpenConns(50)
	db.SetMaxIdleConns(25)
	db.SetConnMaxLifetime(15 * time.Minute)

	router := http.NewServeMux()
	router.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("UP"))
	})

	server := &http.Server{
		Addr:         ":8080",
		Handler:      router,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Jalankan server di background goroutine
	go func() {
		log.Printf("Server listening on %s", server.Addr)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("HTTP server fatal error: %v", err)
		}
	}()

	// Menunggu sinyal termination (SIGINT / SIGTERM)
	<-ctx.Done()
	log.Println("Shutdown signal received, draining active connections...")

	// Beri alokasi waktu grace period 15 detik untuk menyelesaikan transaksi aktif
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Printf("Forced shutdown executed: %v", err)
	}

	if err := db.Close(); err != nil {
		log.Printf("Error closing DB pool: %v", err)
	}

	log.Println("Process terminated cleanly.")
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Ledger & Payment Gateway Flash Sale (50,000 RPS)
* **Masalah:** Sebuah platform e-commerce menyelenggarakan *Flash Sale* dengan lonjakan transaksi pembayaran mencapai 50,000 RPS. Pada implementasi lama, sistem langsung memanggil payment vendor API dan menulis event ke Kafka secara inline di dalam HTTP handler.
* **Insiden:**
  1. Vendor API mengalami degradasi latensi (dari 200ms melonjak menjadi 4.5 detik).
  2. Akibat koneksi lambat, Goroutine di HTTP server menumpuk secara liar (tembus 180,000 goroutines).
  3. Memori backend melompat dari 1.5 GB ke 14 GB hingga memicu Linux kernel OOM Killer.
  4. Database connection pool habis (*exhausted*), mengakibatkan deadlock sistem secara total.
* **Solusi Arsitektur Produksi:**
  1. **Inbound Rate Limiting & Bounded Worker Pool:** Handler HTTP dibatasi hanya menerima input dan memasukannya ke antrean berkapasitas tetap (*bounded channel*). Kelebihan traffic langsung ditolak dengan status HTTP `429 Too Many Requests` secara elegan tanpa membebani memory stack.
  2. **Transactional Outbox via WAL (Change Data Capture/CDC):** Modul checkout memvalidasi kuota dan menyimpan transaksi lokal beserta status outbox. Pemindahan data ke Kafka diambil alih oleh **Debezium CDC Engine** yang membaca PostgreSQL Write-Ahead Log (WAL) secara asinkron tanpa membebani I/O query aplikasi.
  3. **Circuit Breaker pada Payment Gateway:** Menerapkan algoritma *Circuit Breaker* (Sony/gobreaker). Jika downstream vendor gagal sebanyak 15% dalam window 10 detik, sirkuit membuka (*OPEN state*), dan request langsung dialihkan ke metode pembayaran alternatif secara deterministik.
* **Hasil:**
  - P99 Latensi stabil di bawah 45ms untuk fase checkout ingestion.
  - Zero OOM crash; konsumsi memori stabil di rentang 800 MB - 1.2 GB meski load mencapai 65,000 RPS.

---

## 9. Trade-offs

| Pendekatan / Komponen | Keuntungan (Pros) | Konsekuensi & Kerugian (Cons) | Biaya / Resource Impact |
| :--- | :--- | :--- | :--- |
| **Hexagonal Architecture** | Kode independen dari vendor/DB; tingkat testabilitas unit test mendekati 100%. | Kompleksitas layer mapping tinggi; *boilerplate code* meningkat (banyak interface & DTO mappers). | Latensi negligible (<1ms); Biaya *cognitive overhead* engineer awal meningkat. |
| **Transactional Outbox (Polling)** | Jaminan konsistensi tinggi (*At-least-once delivery*); tidak membutuhkan 2PC / XA Transaction. | Menambah beban read I/O pada tabel outbox di database utama jika interval polling terlalu agresif. | CPU & I/O DB meningkat 5-10%; potensi latensi pesan bertambah ratusan milidetik. |
| **Transactional Outbox (CDC/Debezium)** | Nol overhead query database utama; latensi streaming mendekati real-time (<50ms). | Kompleksitas infrastruktur meningkat (perlu Apache Kafka Connect, ZooKeeper/KRaft, Debezium agent). | Biaya server infrastruktur & maintenance DevOps melonjak signifikan. |
| **Pessimistic Locking (`SELECT FOR UPDATE`)** | Mencegah race condition secara mutlak pada stock/ledger level. | Mematikan konkurensi pada baris data yang sama; rawan query queue timeout dan deadlock. | Latensi P99 naik drastis di bawah kontensi tinggi; throughput turun. |
| **Optimistic Locking (`version column`)** | Skalabilitas pembacaan data tinggi; tidak ada lock database yang ditahan lama. | Transaksi sering dibatalkan (*conflict aborts*) saat traffic terkonsentrasi pada satu baris data. | Membutuhkan retry-mechanism di layer aplikasi; CPU spikes saat collision tinggi. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Goroutine Leaks Akibat Channel Tanpa Receiver/Timeout
* **Gejala:** Memori server naik secara kontinu (*linear stair-step memory leak*) dan tidak pernah turun meskipun traffic mereda.
* **Penyebab:**
```go
// KODE BERBAHAYA
func executeTask() {
    ch := make(chan error) // Unbuffered channel
    go func() {
        err := callExternalAPI()
        ch <- err // BLOCKED SELAMANYA jika context induk timeout duluan
    }()
    
    select {
    case err := <-ch:
        // handle
    case <-time.After(100 * time.Millisecond):
        return // Goroutine di atas tertahan selamanya di memory heap
    }
}
```
* **Solusi Produksi:** Gunakan *buffered channel* berukuran 1 (`make(chan error, 1)`) agar goroutine pekerja tetap bisa melakukan emit nilai dan selesai tanpa harus menunggu receiver aktif.

### 10.2 Connection Pool Starvation & Unclosed Rows
* **Gejala:** Backend macet total; log menunjukkan `database/sql: connection timed out` setelah beberapa jam berjalan.
* **Investigasi:**
```bash
# Debug via Go pprof tool
go tool pprof http://localhost:8080/debug/pprof/goroutine
```
* **Penyebab:** Lupa memanggil `rows.Close()` setelah scanning database. Driver SQL mempertahankan koneksi pool terbuka sampai ditutup secara eksplisit.
* **Solusi:** Selalu pasang idiom `defer rows.Close()` segera setelah `err != nil` validation pada `db.Query()`.

### 10.3 Failure Matrix Transaksional Outbox
```
+------------------------------------+-------------------------------------------+
| Tipe Kegagalan                     | Aksi Mitigasi                             |
+------------------------------------+-------------------------------------------+
| Worker crash setelah kirim Kafka,  | Konsumen Kafka wajib Idempoten            |
| sebelum update status Outbox.      | (gunakan Deduplication Key di downstream) |
+------------------------------------+-------------------------------------------+
| Outbox table bloat                 | Buat Cron Job partisi tabel bulanan &     |
| (Jutaan row tersimpan).            | purge event PUBLISHED > 7 hari.           |
+------------------------------------+-------------------------------------------+
```

---

## 11. Best Practices (Production Checklist)

### Security Checklist
- [ ] Konfigurasi TLS 1.3 murni pada *ingress layer*; nonaktifkan cipher suite lama yang rentan.
- [ ] Sanitasi seluruh header input; setel HTTP Security Headers: `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Content-Security-Policy`.
- [ ] Tidak memasukkan secrets, auth token, atau PII ke dalam payload tabel Outbox.

### Performance & Resilience Checklist
- [ ] Tentukan `SetMaxOpenConns`, `SetMaxIdleConns`, dan `SetConnMaxLifetime` pada database pool sesuai kapasitas RAM DB server.
- [ ] Setel *HTTP Client Timeouts* global: jangan pernah menggunakan `http.DefaultClient` tanpa batas timeout eksplisit.
- [ ] Terapkan *Context-Driven Execution*: Teruskan `context.Context` dari HTTP Request hingga ke query DB dan network calls.

### Observability Checklist
- [ ] Inject distributed tracing `trace_id` dan `span_id` (OpenTelemetry standard) ke setiap log output dan event payload.
- [ ] Ekspor endpoint metrik Prometheus: Durasi eksekusi handler, jumlah connection pool aktif, kapasitas antrean buffer.

---

## 12. Hands-on Practice

Buatlah direktori `hands-on/m02/` dan ikuti langkah berikut untuk mengimplementasikan Bounded Worker Pool Engine yang tahan uji.

### Langkah 1: Setup Workspace & Direktori
```bash
mkdir -p hands-on/m02/workerpool
cd hands-on/m02/workerpool
go mod init workerpool
```

### Langkah 2: Buat Implementasi Worker Pool
Buat file `pool.go`:
```go
package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type Job func(ctx context.Context)

type Pool struct {
	jobQueue chan Job
	wg       sync.WaitGroup
	ctx      context.Context
	cancel   context.CancelFunc
}

func NewPool(ctx context.Context, numWorkers int, queueCapacity int) *Pool {
	childCtx, cancel := context.WithCancel(ctx)
	p := &Pool{
		jobQueue: make(chan Job, queueCapacity),
		ctx:      childCtx,
		cancel:   cancel,
	}

	for i := 0; i < numWorkers; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}

	return p
}

func (p *Pool) worker(id int) {
	defer p.wg.Done()
	for {
		select {
		case <-p.ctx.Done():
			return
		case job, ok := <-p.jobQueue:
			if !ok {
				return
			}
			job(p.ctx)
		}
	}
}

func (p *Pool) Submit(job Job) error {
	select {
	case <-p.ctx.Done():
		return fmt.Errorf("worker pool is stopped")
	case p.jobQueue <- job:
		return nil
	default:
		return fmt.Errorf("worker pool is saturated (backpressure)")
	}
}

func (p *Pool) Shutdown() {
	p.cancel()
	close(p.jobQueue)
	p.wg.Wait()
}
```

### Langkah 3: Verifikasi Pengujian & Race Detector
Buat file `main.go`:
```go
package main

import (
	"context"
	"fmt"
	"math/rand"
	"time"
)

func main() {
	ctx := context.Background()
	// Inisialisasi pool: 4 workers, buffer kapasitas 10
	pool := NewPool(ctx, 4, 10)

	for i := 1; i <= 20; i++ {
		jobID := i
		err := pool.Submit(func(ctx context.Context) {
			select {
			case <-ctx.Done():
				return
			case <-time.After(time.Duration(rand.Intn(50)) * time.Millisecond):
				fmt.Printf("Job %d completed successfully\n", jobID)
			}
		})

		if err != nil {
			fmt.Printf("Job %d rejected: %v\n", jobID, err)
		}
	}

	time.Sleep(300 * time.Millisecond)
	fmt.Println("Triggering pool graceful shutdown...")
	pool.Shutdown()
	fmt.Println("Worker pool stopped safely.")
}
```

Jalankan dengan pendeteksi race condition:
```bash
go run -race main.go
```

---

## 13. Exercise

### Tingkat 1: Easy
Tambahkan middleware recovery panic di HTTP handler standard library Go. Jika handler mengalami panic (misal dereferensi *nil pointer*), tangkap menggunakan `recover()`, cetak error stack trace ke stderr, dan kembalikan response JSON dengan format:
`{"error": "Internal Server Error", "code": 500}` tanpa memutus koneksi server.
- **Kriteria Penerimaan:** Server tidak crash saat endpoint di-request dengan payload malformed; return header `Content-Type: application/json`.

### Tingkat 2: Medium
Kembangkan implementasi `OrderRepository` pada PostgreSQL. Tulis fungsi `GetOutboxEvents(ctx context.Context, batchSize int) ([]OutboxEvent, error)` dengan query `SELECT ... FROM outbox_events WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT $1 FOR UPDATE SKIP LOCKED`.
- **Kriteria Penerimaan:** Query menggunakan klausa `SKIP LOCKED` agar beberapa worker paralel dapat membaca batch yang berbeda tanpa memblokir baris data satu sama lain.

### Tingkat 3: Hard
Bangun Idempotency Middleware menggunakan Redis. Setiap request mutasi yang membawa header `Idempotency-Key` harus mengeksekusi operasi Redis atomik:
1. Jika key belum ada: Set key dengan status `PROCESSING` dan TTL 120 detik. Jalankan handler berikutnya.
2. Jika handler selesai sukses: Update nilai Redis key dengan status `COMPLETED` beserta body response-nya.
3. Jika request kedua datang dengan key yang sama saat status `PROCESSING`: Kembalikan status HTTP `409 Conflict`.
4. Jika request datang dengan key yang sama dan status `COMPLETED`: Langsung kembalikan cached body response tanpa mengeksekusi domain logic.
- **Kriteria Penerimaan:** Aman terhadap konkurensi (lulus pengujian apache benchmark `ab -n 100 -c 10` pada key yang sama).

---

## 14. Challenge

### Studi Kasus: Ledger Anti-Double Spend & Network Partition Resiliency
Anda diminta merancang subsistem Core Banking Ledger untuk transaksi transfer dana saldo dompet digital (*balance transfer*):
- **Spesifikasi Beban:** Sistem melayani transfer saldo antar user hingga 15,000 TPS pada jam sibuk.
- **Batasan Mutlak:**
  1. *Negative Balance Anomaly:* Saldo pengirim tidak boleh pernah bernilai minus dalam kondisi konkurensi seintensif apa pun.
  2. *Partial Network Failure:* Bila koneksi jaringan antara Core Banking dengan Database terputus di tengah proses pemotongan saldo, saldo pengirim tidak boleh hilang (*phantom deduction*) dan saldo penerima tidak boleh bertambah sebelum ada kepastian.
  3. Sistem tidak diizinkan menggunakan global mutex di memori karena server aplikasi dideploy multi-instance (*horizontal auto-scaling* di Kubernetes).

**Tantangan Arsitektur Anda:**
1. Rancang skema database table mutasi (buku besar double-entry) yang mengisolasi lock saldo tanpa mematikan performa throughput akun populer (misal: akun merchant yang menerima ribuan transfer paralel).
2. Tentukan mekanisme konkurensi pada database engine (Pessimistic Locking vs Optimistic Locking vs Event Sourcing Ledger).
3. Buat rancangan dokumen mitigasi penanganan `in-doubt transactions` ketika database mengalami failover master-slave.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic (Pilihan Ganda)

1. Apa peran utama dari *Driving Adapter* dalam Hexagonal Architecture?
   - A. Menulis data langsung ke tabel storage SQL
   - B. Menerima input eksternal, mengonversinya, lalu memanggil Inbound Port
   - C. Menyimpan state transient di Redis cache
   - D. Menghubungkan database engine ke message broker
   *Jawaban yang benar: B. Driving adapter bertindak sebagai penerjemah input dari dunia luar (HTTP, CLI, gRPC) ke antarmuka Use Case Domain.*

2. Di mana letak batas transaksi database ACID seharusnya ditempatkan pada Clean Architecture?
   - A. Di dalam Domain Aggregate Entities murni
   - B. Di Driven Adapter (Repository Implementation)
   - C. Di HTTP Handler Controller
   - D. Di HTTP Client Middleware
   *Jawaban yang benar: B. Transaksi teknis database merupakan detail infrastruktur dan diimplementasikan pada Driven Adapter.*

3. Mengapa `SELECT ... FOR UPDATE SKIP LOCKED` lebih disukai dalam pemrosesan antrean tabel database daripada `SELECT ... FOR UPDATE` biasa?
   - A. Menjamin pengurutan FIFO absolut untuk semua baris
   - B. Mengabaikan constraint foreign key
   - C. Mencegah worker terblokir oleh baris data yang sedang dikunci worker lain
   - D. Mempercepat eksekusi query hingga 100x lipat
   *Jawaban yang benar: C. `SKIP LOCKED` memungkinkan konkurensi paralel tinggi antar worker tanpa harus menunggu lock baris sebelumnya terlepas.*

4. Default ukuran alokasi memori execution stack awal goroutine di Go runtime modern adalah:
   - A. 1 MB
   - B. 2 KB
   - C. 64 KB
   - D. 8 MB
   *Jawaban yang benar: B. Sekitar 2 KB, yang membuat pembuatan puluhan ribu goroutine jauh lebih ringan dibanding OS thread biasa.*

5. Apa dampak tidak memanggil `rows.Close()` setelah menjalankan query `db.Query()` di Go?
   - A. Data yang dibaca menjadi corrupted
   - B. Koneksi database pool tidak dilepas, menyebabkan *connection pool starvation*
   - C. Tabel database otomatis terhapus
   - D. Menghasilkan error kompilasi runtime
   *Jawaban yang benar: B. Driver database menahan koneksi tersebut tetap terbuka hingga memicu limit MaxOpenConns.*

---

### 15.2 Intermediate (Pilihan Ganda)

6. Masalah utama apa yang diselesaikan oleh *Transactional Outbox Pattern* dalam sistem backend terdistribusi?
   - A. Menurunkan latensi read HTTP request
   - B. Mengeliminasi dual-write failure antara database lokal dan message broker
   - C. Menggantikan peran Redis sebagai sistem caching
   - D. Menghapus kebutuhan validasi input di controller
   *Jawaban yang benar: B. Memastikan data state dan event tercatat atomik dalam satu transaksi DB lokal untuk mencegah desinkronisasi data.*

7. Manakah teknik penanganan backpressure yang tepat jika kapasitas queue worker pool penuh di level backend API?
   - A. Membuat goroutine baru tanpa batas secara instan
   - B. Mengembalikan status HTTP 429 atau 503 secara deterministik kepada pemanggil
   - C. Menghapus request terlama dari memori secara diam-diam
   - D. Mematikan proses server dengan `os.Exit(1)`
   *Jawaban yang benar: B. Memberi sinyal backpressure terukur (HTTP 429 Too Many Requests / 503 Service Unavailable) menjaga ketersediaan sistem dari kehancuran total.*

8. Apa perbedaan fundamental antara Pessimistic Locking dan Optimistic Locking dalam penanganan race condition?
   - A. Pessimistic mengunci baris data di level database saat pembacaan; Optimistic memvalidasi versi data saat penulisan
   - B. Optimistic hanya bisa digunakan di database NoSQL
   - C. Pessimistic tidak pernah mengalami deadlock
   - D. Optimistic menjamin transaksi tidak akan pernah dibatalkan
   *Jawaban yang benar: A. Pessimistic mengamankan data via DB locks (`FOR UPDATE`), sedangkan Optimistic menggunakan pengecekan version/timestamp di klausul WHERE.*

9. Mengapa *Bounded Channel* wajib digunakan saat memproduksi log atau event secara asinkron di dalam aplikasi berlatensi rendah?
   - A. Menjamin kecepatan penulisan disk nol milidetik
   - B. Menghindari kebocoran memori tak terkendali (*OOM crash*) jika konsumsi lebih lambat dari produksi
   - C. Menghilangkan kebutuhan alokasi heap pointer
   - D. Memaksa channel dieksekusi secara sinkron
   *Jawaban yang benar: B. Unbounded channel akan menampung data tanpa batas di memory heap hingga memicu out-of-memory crash jika downstream macet.*

10. Apa fungsi dari implementasi `context.WithTimeout` pada panggilan network database?
    - A. Mempercepat eksekusi query SQL secara otomatis
    - B. Membatalkan eksekusi di sisi driver dan server jika melebihi SLA durasi yang ditentukan
    - C. Mengonversi query relational menjadi format in-memory
    - D. Menjamin query tidak menghasilkan error
    *Jawaban yang benar: B. Mencegah connection thread tertahan selamanya saat terjadi degradasi I/O atau network hanging.*

---

### 15.3 Skenario Kasus Produksi (Analisis & Solusi)

#### Skenario 1
Layanan autentikasi Anda mengalami lonjakan traffic saat event peluncuran produk. Metrik pemantauan menunjukkan penggunaan memori melonjak tajam dari 500 MB ke 8 GB dalam 3 menit, disertai lonjakan goroutine dari 200 menjadi 90,000. Beberapa detik kemudian proses mati mendadak dengan status exit code 137 (OOM Killed). Analisis kode menemukan: setiap ada request masuk, handler membuat `go func()` tanpa batasan untuk mencatat aktivitas log ke database audit.
* **Pertanyaan:** Identifikasi akar penyebab masalah arsitektur ini dan berikan 2 langkah perbaikan konkret untuk arsitektur produksi!
* **Solusi & Analisis:**
  1. *Akar Masalah:* Unbounded Concurrency. Alokasi goroutine yang tidak dibatasi menciptakan ribuan objek heap dan goroutine stack yang membanjiri memory runtime hingga OS melempar SIGKILL.
  2. *Langkah Perbaikan 1:* Terapkan Bounded Worker Pool (misal: pool dengan 50 worker konstan) yang menerima log job via buffered channel berkapasitas tetap.
  3. *Langkah Perbaikan 2:* Terapkan *Non-blocking drop / sampling policy* atau fallback ke stdout log jika buffer penuh, sehingga proses autentikasi utama tidak terpengaruh oleh subsystem auditing.

#### Skenario 2
Sebuah sistem transfer perbankan menggunakan skema Outbox table. Worker penarik event mengambil 100 row event `PENDING` setiap 100ms dan mengirimkannya ke Apache Kafka. Pada suatu malam, koneksi jaringan ke Kafka mengalami timeout intermiten selama 15 detik. Akibatnya, worker mempublikasikan event yang sama ke Kafka sebanyak dua kali sebelum berhasil mengupdate status event menjadi `PUBLISHED` di database.
* **Pertanyaan:** Anomali apa yang terjadi di layer consumer dan bagaimana standar enterprise mengatasi konsekuensi kegagalan ini?
* **Solusi & Analisis:**
  1. *Anomali:* Duplicate Message Delivery (At-Least-Once Delivery side-effect). Downstream consumer berpotensi mengeksekusi top-up/pembayaran ganda jika membaca event yang sama dua kali.
  2. *Solusi Enterprise:* Consumer wajib bersifat **Idempoten**. Consumer harus mencatat ID event unik yang diproses ke dalam database menggunakan transaksi atomik atau Redis key (`SETNX event_id PROCESSED EX 86400`). Jika ID sudah terdaftar, konsumen langsung mengakui (ACK) pesan tersebut tanpa memproses ulang mutasi saldo.

#### Skenario 3
Sistem e-commerce Anda dideploy menggunakan Kubernetes. Setiap kali dilakukan deployment versi baru (*Rolling Update*), sekitar 0.8% request pengguna mengalami error `502 Bad Gateway` atau `Connection Refused` selama rentang waktu 10 hingga 20 detik saat container lama diterminasi.
* **Pertanyaan:** Mengapa hal ini terjadi pada HTTP layer dan bagaimana arsitektur graceful shutdown yang benar untuk menghilangkannya hingga 0% error?
* **Solusi & Analisis:**
  1. *Akar Masalah:* Kubernetes mengirim sinyal `SIGTERM` ke pod dan secara paralel memperbarui endpoint iptables/kube-proxy. Jika container aplikasi langsung mati tanpa menunggu penyebaran routing tabel jaringan tuntas, traffic baru masih diarahkan ke pod yang sekarat tersebut.
  2. *Solusi Enterprise:*
     - Pasang `preStop` hook sleep di Kubernetes deployment specification (misal: `sleep 5`) untuk memberikan waktu sinkronisasi iptables sebelum aplikasi menerima `SIGTERM`.
     - Implementasikan `httpServer.Shutdown(ctx)` yang menghentikan penerimaan koneksi TCP baru, namun memberikan grace period (misal 15-30 detik) untuk menyelesaikan request aktif yang sedang berjalan.

---

## 16. Summary
- **Arsitektur Hexagonal** bukan sekadar pemisahan folder, melainkan disiplin isolasi dependensi: Core Domain tidak boleh mengetahui teknologi database, broker, maupun framework transport.
- **Transactional Outbox Pattern** menyelesaikan problem *dual-write* tanpa memerlukan distributed locking yang rapuh, memberikan jaminan keandalan data berbasis konsistensi eventual (*eventual consistency*).
- **Concurrency di Produksi** harus selalu memiliki batas (*bounded*). Setiap alokasi goroutine atau thread wajib dikendalikan melalui pool dan terikat pada *context cancellation* serta *timeout propagation*.
- **Resiliensi Sistem Modern** dibangun atas dasar kesiapan menghadapi kegagalan: implementasi *graceful shutdown*, *circuit breaking*, *backpressure*, dan *idempotency* adalah fondasi mutlak agar sistem berskala enterprise bertahan di bawah beban ekstrem.