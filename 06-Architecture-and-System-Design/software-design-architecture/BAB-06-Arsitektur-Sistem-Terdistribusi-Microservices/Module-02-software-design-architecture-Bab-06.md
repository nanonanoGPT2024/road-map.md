# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Kategori:** 06-Architecture-and-System-Design  
**Bab 06:** Arsitektur Sistem Terdistribusi & Microservices  
**File Target:** `hands-on/m02/`

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengimplementasikan Transaksi Terdistribusi**: Menguasai arsitektur *Saga Pattern* (Orchestration vs Choreography) dan menyelesaikan *Dual-Write Problem* menggunakan *Transactional Outbox Pattern* berbasis *Change Data Capture* (CDC).
2. **Membangun Sistem Resilien Tingkat Lanjut**: Mengimplementasikan *Circuit Breaker*, *Bulkhead Isolation*, *Adaptive Rate Limiting*, serta *Retry with Exponential Backoff and Full Jitter* untuk mencegah *cascading failure*.
3. **Mengoperasikan Service Mesh & Observabilitas Terdistribusi**: Mengonfigurasi arsitektur *data plane* (Envoy) dan *control plane*, serta menginstrumentasikan *Distributed Tracing* berbasis OpenTelemetry dan spesifikasi W3C TraceContext.
4. **Mengelola Konsistensi Data & State**: Mengidentifikasi trade-off PACELC/CAP theorem, menerapkan model konsistensi *Eventual Consistency* dan mitigasi anomali data konkuren pada microservices stateful.

---

## 2. Prerequisite

Peserta wajib memahami:
*   Konsep dasar microservices: dekomposisi *bounded context* (Domain-Driven Design), arsitektur RESTful API & gRPC dasar.
*   Pemrograman konkuren (Go goroutine/channel, Java virtual threads, atau async/await Node.js).
*   Dasar-dasar Relational Database (ACID guarantees, Transaction Isolation Levels: Read Committed, Repeatable Read, Serializable).
*   Dasar-dasar Message Broker: Apache Kafka (Topics, Partitions, Consumer Groups, Offsets) atau RabbitMQ (Exchanges, Queues, Routing Keys).
*   Containerization dasar: Docker, Docker Compose, dan konsep jaringan container.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Dual-Write Problem & Transactional Outbox
Dalam sistem terdistribusi, kebutuhan untuk memodifikasi basis data lokal dan mengirimkan event/pesan ke message broker secara atomik adalah kebutuhan fundamental. Eksekusi naif:
```text
1. db.Save(order)
2. kafka.Publish(orderCreatedEvent)
```
menghadapi kegagalan fatal: jika broker *down* atau jaringan terputus setelah langkah 1, data tersimpan di database tetapi event hilang (*inconsistency*). Sebaliknya, jika urutan dibalik dan database gagal setelah event dikirim, downstream service memproses data hantu.

```
+-------------------------------------------------------------------------+
|                           MICROSERVICE RUNTIME                          |
|                                                                         |
|  [ HTTP/gRPC Request ]                                                  |
|          |                                                              |
|          v                                                              |
|  +--------------------+   BEGIN TX                                      |
|  | Application Logic  |------------+                                    |
|  +--------------------+            |                                    |
|          |                         v                                    |
|          | Insert Entity   +--------------------+                       |
|          +---------------->|    orders Table    |                       |
|          |                 +--------------------+                       |
|          | Insert Event    +--------------------+                       |
|          +---------------->|    outbox Table    |                       |
|                            +--------------------+                       |
|                                    | COMMIT TX                          |
|                                    +------------------------------+     |
+-------------------------------------------------------------------|-----+
                                                                    |
+-------------------------------------+                             |
|        TRANSACTION LOG (WAL)        |<----------------------------+
+-------------------------------------+
                   |
                   | CDC Engine (Debezium / Tailer)
                   v
+-------------------------------------+
|        CDC Outbox Connector         |
+-------------------------------------+
                   |
                   | At-least-once Delivery
                   v
+-------------------------------------+
|      Apache Kafka / Event Mesh      |
+-------------------------------------+
```

*Transactional Outbox Pattern* memecahkan ini dengan menyimpan event ke dalam tabel relasional `outbox` di dalam transaksi database yang sama dengan entitas bisnis (`BEGIN TX ... COMMIT`). Komponen independen (*Transaction Log Miner* seperti Debezium via CDC atau background poller) membaca log transaksi basis data (*Write-Ahead Logging* / WAL pada PostgreSQL, Binlog pada MySQL) dan meneruskannya ke message broker dengan jaminan *at-least-once*.

### 3.2 Saga Pattern: Orchestration vs Choreography
Ketika transaksi melintasi batasan beberapa microservice, protokol *Two-Phase Commit* (2PC) dihindari karena sifatnya yang memblokir (*blocking protocol*), memiliki latensi tinggi, dan rentan terhadap *single point of failure* (koordinator 2PC). Alternatifnya adalah *Saga Pattern*—rangkaian transaksi lokal berurutan di mana setiap transaksi memperbarui data dalam satu service dan menerbitkan pesan/event.

*   **Choreography**: Layanan saling mendengarkan event dan menentukan tindakan mandiri.
    *   *Kelebihan*: Sederhana, loose coupling untuk alur pendek (2-3 langkah).
    *   *Kekurangan*: Siklus dependensi berbelit (*spaghetti architecture*), sulit dimonitor secara terpusat, rawan *deadlock*.
*   **Orchestration**: Komponen sentral (*Orchestrator*) mengarahkan alur kerja melalui RPC/messaging eksplisit dan menangani kompensasi jika terjadi kegagalan.
    *   *Kelebihan*: Alur proses eksplisit, state machine tersentralisasi, mudah diaudit dan di-trace.
    *   *Kekurangan*: Potensi *point of failure* jika orchestrator tidak stateless/resilien; risiko memusatkan logika domain bisnis secara berlebihan ke dalam orchestrator (*anemic services*).

### 3.3 Fault Tolerance & Resilience Topology
Sistem terdistribusi harus didesain dengan asumsi bahwa kegagalan parsial (*partial failure*) adalah kepastian.
1.  **Circuit Breaker**: Mengisolasi kegagalan downstream agar thread/resource upstream tidak habis menunggu timeout.
    *   `CLOSED`: Request diteruskan normal. Error rate dihitung menggunakan *sliding window*.
    *   `OPEN`: Error rate melampaui ambang batas (*threshold*). Request langsung di-reject secara instan (*fast-fail*).
    *   `HALF-OPEN`: Setelah waktu *cooldown*, sejumlah *probe request* diizinkan lolos. Jika sukses, kembali ke `CLOSED`; jika gagal, kembali ke `OPEN`.
2.  **Bulkhead Pattern**: Partisi resource pool (connection pool, worker thread pool) per-downstream target sehingga kegagalan satu downstream lambat tidak menguras kapasitas keseluruhan sistem.
3.  **Adaptive Rate Limiting & Backoff**: Retries tanpa *jitter* memicu *thundering herd problem*. Formulasi *Full Jitter*:
    $$T_{\text{sleep}} = \text{random}(0, \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}))$$

---

## 4. Why & What

| Dimensi | Monolit / Naive Distributed | Production-Grade Microservices |
| :--- | :--- | :--- |
| **Transaksi** | Single ACID DB Transaction | Saga Pattern + Transactional Outbox + Idempotent Consumer |
| **Fail-Mode** | Fatal process crash | Partial failure, graceful degradation via Circuit Breaker |
| **Komunikasi** | Direct synchronous REST over HTTP/1.1 | gRPC via HTTP/2 (Multiplexed) + Asynchronous Event Spine |
| **Traceability** | Monolithic central logs | Distributed Context Propagation (W3C TraceContext: `traceparent`) |
| **Routing & Mesh** | Hardcoded endpoint / Basic Reverse Proxy | Envoy Sidecar, Service Discovery, mTLS, Traffic Shifting |

---

## 5. How (Workflow Detail)

### Alur Eksekusi Saga Orchestration Terkompensasi
Skenario: Pemesanan E-Commerce (`OrderService` $\to$ `PaymentService` $\to$ `InventoryService`).

```
[Client] -> [OrderService (Orchestrator)]
                 |
                 +-- 1. CreatePendingOrder() (Local DB)
                 |
                 +-- 2. Call PaymentService.Debit()
                 |        |
                 |        +--> SUCCESS
                 |
                 +-- 3. Call InventoryService.ReserveStock()
                          |
                          +--> FAIL (Out of Stock!)
                          |
                 +<-------+
                 |
                 +-- 4. Compensating Action Triggered:
                 |      Call PaymentService.Refund()
                 |        |
                 |        +--> SUCCESS
                 |
                 +-- 5. MarkOrderAsFailed() (Local DB)
                 |
[Client] <-------+ (Return 409 Conflict: Out of Stock)
```

1.  **State Initialization**: Orchestrator menerima request, membuat record Saga State Machine di database lokal dengan status `STARTED`.
2.  **Step Forwarding**: Orchestrator mengeksekusi step $N$ secara synchronous atau asynchronous (idempotency key disertakan).
3.  **Failure Detection**: Step $N+1$ gagal (misal: Insufficient Balance atau Stock Expired).
4.  **Compensating Execution**: Orchestrator membalik urutan, mengeksekusi aksi kompensasi dari step $N$ turun ke step $1$ (`RefundPayment`, `CancelReservation`).
5.  **State Terminal**: Saga ditandai `FAILED_COMPENSATED`. Jika kompensasi gagal, Saga masuk status `MANUAL_INTERVENTION_REQUIRED` dan memicu alert PagerDuty.

---

## 6. Analogy & Diagram ASCII

### Analogi Nyata: Pengiriman Barang Ekspedisi Internasional
Bayangkan proses pengiriman paket internasional: Anda tidak bisa menahan (*lock*) kapal kontainer dan kurir di seluruh dunia dalam satu transaksi instan. 
*   **Transaksi Lokal**: Gudang lokal mengemas barang dan mencatatnya di buku ekspedisi lokal.
*   **Outbox Pattern**: Petugas mencatat manifest keberangkatan di papan fisik (outbox); truk pengangkut membaca papan tersebut lalu membawanya ke pelabuhan.
*   **Saga Orchestrator**: Manajer logistik memantau tahapan: jika paket tertolak di bea cukai negara tujuan, manajer menginstruksikan kompensasi (kirim balik barang ke gudang asal dan kembalikan dana importir).
*   **Circuit Breaker**: Jika pelabuhan tujuan mogok kerja, manajer logistik langsung menolak pengiriman baru ke pelabuhan tersebut (*fast fail*) alih-alih membiarkan kapal mengapung berhari-hari membakar bahan bakar (*thread exhaustion*).

### State Machine Circuit Breaker

```
         +-------------------------------------------------------+
         |                                                       |
         v                                                       | Success threshold
    +----------+              Fail threshold exceeded            | reached
    |  CLOSED  | ------------------------------------> +-------------------+
    +----------+                                       |       OPEN        |
         ^                                             +-------------------+
         |                                                       |
         |                                                       | Sleep window
         |                     Test Request                      | elapsed
         |                     Success                           v
         |                 +---------------+             +---------------+
         +---------------- |   HALF-OPEN   | <---------- |  SLEEPING     |
                           +---------------+             +---------------+
                                   |
                                   | Test Request Fail
                                   v
                             +-----------+
                             |   OPEN    |
                             +-----------+
```

---

## 7. Simple & Practical Code Examples

### Implementasi Lengkap: Transactional Outbox + Background Publisher & Circuit Breaker (Go)

Direktori kerja: `hands-on/m02/`

#### 7.1 Database Schema (`hands-on/m02/schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outbox_events (
    id VARCHAR(36) PRIMARY KEY,
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL, -- PENDING, PUBLISHED, FAILED
    retry_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_outbox_pending ON outbox_events(status, created_at) WHERE status = 'PENDING';
```

#### 7.2 Core Domain & Transactional Outbox Logic (`hands-on/m02/order_service.go`)
```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
)

type Order struct {
	ID         string  `json:"id"`
	CustomerID string  `json:"customer_id"`
	Amount     float64 `json:"amount"`
	Status     string  `json:"status"`
}

type OrderCreatedEvent struct {
	OrderID    string  `json:"order_id"`
	CustomerID string  `json:"customer_id"`
	Amount     float64 `json:"amount"`
	OccurredAt string  `json:"occurred_at"`
}

type OrderRepository struct {
	db *sql.DB
}

func NewOrderRepository(db *sql.DB) *OrderRepository {
	return &OrderRepository{db: db}
}

// CreateOrderWithOutbox mengeksekusi penyimpanan entitas dan event outbox dalam satu transaksi ACID lokal
func (r *OrderRepository) CreateOrderWithOutbox(ctx context.Context, order Order) error {
	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to begin tx: %w", err)
	}
	defer tx.Rollback()

	// 1. Insert ke tabel orders
	queryOrder := `INSERT INTO orders (id, customer_id, amount, status, created_at) VALUES ($1, $2, $3, $4, $5)`
	_, err = tx.ExecContext(ctx, queryOrder, order.ID, order.CustomerID, order.Amount, order.Status, time.Now())
	if err != nil {
		return fmt.Errorf("failed to insert order: %w", err)
	}

	// 2. Marshalling event payload
	eventPayload := OrderCreatedEvent{
		OrderID:    order.ID,
		CustomerID: order.CustomerID,
		Amount:     order.Amount,
		OccurredAt: time.Now().UTC().Format(time.RFC3339),
	}
	payloadBytes, err := json.Marshal(eventPayload)
	if err != nil {
		return fmt.Errorf("failed to serialize event: %w", err)
	}

	// 3. Insert ke tabel outbox
	queryOutbox := `INSERT INTO outbox_events (id, aggregate_type, aggregate_id, event_type, payload, status, retry_count, created_at)
	                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`
	_, err = tx.ExecContext(ctx, queryOutbox,
		uuid.New().String(),
		"ORDER",
		order.ID,
		"ORDER_CREATED",
		payloadBytes,
		"PENDING",
		0,
		time.Now().UTC(),
	)
	if err != nil {
		return fmt.Errorf("failed to insert outbox event: %w", err)
	}

	// 4. Commit transaksi
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit tx: %w", err)
	}

	return nil
}
```

#### 7.3 Outbox Processor Engine (`hands-on/m02/outbox_publisher.go`)
```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"time"
)

type MessageProducer interface {
	Publish(ctx context.Context, topic string, key string, payload []byte) error
}

type MockKafkaProducer struct{}

func (m *MockKafkaProducer) Publish(ctx context.Context, topic string, key string, payload []byte) error {
	// Simulasi pengiriman kafka
	log.Printf("[KAFKA] Emitted -> Topic: %s | Key: %s | Payload: %s", topic, key, string(payload))
	return nil
}

type OutboxPublisher struct {
	db       *sql.DB
	producer MessageProducer
	batch    int
}

func NewOutboxPublisher(db *sql.DB, producer MessageProducer, batchSize int) *OutboxPublisher {
	return &OutboxPublisher{
		db:       db,
		producer: producer,
		batch:    batchSize,
	}
}

// StartPoller membaca outbox secara periodik menggunakan SELECT FOR UPDATE SKIP LOCKED
func (p *OutboxPublisher) StartPoller(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("Stopping outbox publisher...")
			return
		case <-ticker.C:
			if err := p.processBatch(ctx); err != nil {
				log.Printf("Error processing outbox batch: %v", err)
			}
		}
	}
}

func (p *OutboxPublisher) processBatch(ctx context.Context) error {
	tx, err := p.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// SKIP LOCKED memastikan multi-instance worker tidak memproses record yang sama
	query := `SELECT id, aggregate_id, event_type, payload 
	          FROM outbox_events 
	          WHERE status = 'PENDING' 
	          ORDER BY created_at ASC 
	          LIMIT $1 FOR UPDATE SKIP LOCKED`

	rows, err := tx.QueryContext(ctx, query, p.batch)
	if err != nil {
		return err
	}
	defer rows.Close()

	type record struct {
		id          string
		aggregateID string
		eventType   string
		payload     []byte
	}

	var batchRecords []record
	for rows.Next() {
		var r record
		if err := rows.Scan(&r.id, &r.aggregateID, &r.eventType, &r.payload); err != nil {
			return err
		}
		batchRecords = append(batchRecords, r)
	}

	if len(batchRecords) == 0 {
		return nil
	}

	stmtUpdate, err := tx.PrepareContext(ctx, `UPDATE outbox_events SET status = 'PUBLISHED', processed_at = $1 WHERE id = $2`)
	if err != nil {
		return err
	}
	defer stmtUpdate.Close()

	for _, rec := range batchRecords {
		// Kirim ke broker
		err := p.producer.Publish(ctx, rec.eventType, rec.aggregateID, rec.payload)
		if err != nil {
			log.Printf("Failed to publish record %s: %v", rec.id, err)
			// Dalam produksi, update retry_count dan status = 'FAILED' jika melampaui ambang batas
			continue
		}

		_, err = stmtUpdate.ExecContext(ctx, time.Now().UTC(), rec.id)
		if err != nil {
			return fmt.Errorf("failed to update outbox status: %w", err)
		}
	}

	return tx.Commit()
}
```

#### 7.4 Thread-Safe Circuit Breaker (`hands-on/m02/circuit_breaker.go`)
```go
package main

import (
	"errors"
	"sync"
	"time"
)

type State int

const (
	StateClosed State = iota
	StateHalfOpen
	StateOpen
)

var (
	ErrCircuitOpen = errors.New("circuit breaker is open; fast-failing request")
)

type CircuitBreaker struct {
	mu           sync.Mutex
	state        State
	failureCount int
	threshold    int
	cooldown     time.Duration
	lastStateChg time.Time
}

func NewCircuitBreaker(threshold int, cooldown time.Duration) *CircuitBreaker {
	return &CircuitBreaker{
		state:        StateClosed,
		threshold:    threshold,
		cooldown:     cooldown,
		lastStateChg: time.Now(),
	}
}

func (cb *CircuitBreaker) Execute(action func() error) error {
	cb.mu.Lock()
	now := time.Now()

	if cb.state == StateOpen {
		if now.Sub(cb.lastStateChg) > cb.cooldown {
			cb.state = StateHalfOpen
			cb.lastStateChg = now
		} else {
			cb.mu.Unlock()
			return ErrCircuitOpen
		}
	}
	cb.mu.Unlock()

	err := action()

	cb.mu.Lock()
	defer cb.mu.Unlock()

	if err != nil {
		cb.failureCount++
		if cb.failureCount >= cb.threshold || cb.state == StateHalfOpen {
			cb.state = StateOpen
			cb.lastStateChg = time.Now()
		}
		return err
	}

	// Request berhasil
	if cb.state == StateHalfOpen {
		cb.state = StateClosed
		cb.failureCount = 0
	} else if cb.state == StateClosed {
		cb.failureCount = 0
	}

	return nil
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Arsitektur Transaksi Settlement Dompet Digital (Skala 50.000 TPS)

#### Konteks & Skala
Platform dompet digital nasional menangani volume transaksi puncak saat festival belanja daring: 50.000 TPS, latensi p99 < 300 ms, dengan nilai transaksi miliaran rupiah per jam.

#### Masalah Arsitektur
Awalnya sistem menggunakan REST synchronous calls antar service (`Core-Wallet` $\to$ `Ledger` $\to$ `Notification`). 
1.  **Cascading Latency**: Ketika latency `Ledger` naik dari 20ms menjadi 1200ms akibat lock contention, connection pool di `Core-Wallet` habis dalam waktu 4 detik.
2.  **Phantom Balances (Inconsistency)**: Jaringan timeout antara Wallet dan Ledger menyebabkan debit saldo customer terjadi di wallet, tetapi top-up di merchant gagal tanpa mekanisme kompensasi otomatis.

#### Solusi yang Diterapkan
1.  **Transactional Outbox + Debezium CDC**:
    *   Tabel `wallet_balance` dan `outbox_log` dimodifikasi dalam satu commit ACID database PostgreSQL (di-sharding ke 16 instance).
    *   Debezium membaca native PostgreSQL WAL (*Logical Replication via `pgoutput`*) dan mengalirkan event perubahan state ke cluster Kafka dengan latensi end-to-end < 15ms tanpa membebani pool database produksi dengan query polling.
2.  **Saga Orchestration via Temporal.io**:
    *   State machine transaksi kompleks (Split Bill, Multi-Merchant Checkouts) dieksekusi sebagai workflow terdistribusi yang *durable*. Jika downstream payment gateway timeout, Temporal secara otomatis menjalankan kompensasi reversi saldo.
3.  **Resilience Layer (Envoy Mesh)**:
    *   Setiap instance disandingkan dengan *Envoy sidecar proxy*. Envoy mengelola mTLS, *active health checking*, *outlier detection* (otomatis melepaskan pod yang mengembalikan HTTP 5xx lebih dari 5 kali berturut-turut), dan *local adaptive rate limiting*.

#### Hasil
*   Zero missing financial records (*RPO = 0*).
*   Penurunan error rate transaksi terdistribusi dari 0.8% menjadi 0.0001%.
*   Kapasitas throughput naik 4x lipat tanpa penambahan node database berkat eliminasi synchronous locks lintas batas service.

---

## 9. Trade-offs

| Aspek | Pilihan A | Pilihan B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Saga Coordination** | **Choreography** (Event-Driven via Kafka) | **Orchestration** (Dedicated Coordinator Engine) | **Choreography** menawarkan decoupling tinggi dan latensi lebih rendah, namun debugging menjadi luar biasa rumit (*blind spots*) saat transaksi melibatkan >4 service. **Orchestration** memberikan visibilitas dan kemudahan audit terpusat, namun menambah dependensi infrastruktur orchestrator dan sedikit overhead latensi RPC. |
| **Outbox Extraction** | **Polling Publisher** (`SELECT ... SKIP LOCKED`) | **Transaction Log Tailing (CDC)** (Debezium / Kafka Connect) | **Polling** sangat mudah diimplementasikan tanpa infrastruktur tambahan, namun membebani I/O DB dan memiliki polling lag (latency > 500ms). **CDC** membaca langsung storage layer (WAL/Binlog) dengan latency near real-time (< 20ms) dan beban DB minimal, namun membutuhkan keahlian operasional tinggi untuk mengelola replication slots dan schema evolutions. |
| **Microservice Transport** | **gRPC (HTTP/2 Protocol Buffers)** | **REST (JSON over HTTP/1.1)** | **gRPC** memangkas bandwidth hingga 70% dan latensi serialisasi, mendukung streaming native dan multiplexing satu koneksi TCP. Namun, memerlukan contract tooling kaku (Protobuf compiling) dan inspeksi traffic secara visual (*human-readable*) lebih sulit dibanding REST JSON. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Dual-Write Anti-Pattern
*   **Gejala**: Customer didebit, tetapi record pesanan tidak ada, atau sebaliknya. Log server menunjukkan `Database commit success`, diikuti `Broker network timeout`.
*   **Root Cause**: Aplikasi melakukan *two-phase write* manual ke dua resource berbeda tanpa *two-phase commit* atau *outbox pattern*.
*   **Mitigasi**: Hentikan pemanggilan broker di dalam *business transaction*. Gunakan *Transactional Outbox*.

### 2. Missing Idempotency Key pada Consumer
*   **Gejala**: Kompensasi terdistribusi atau konsumsi pesan memicu double-refund atau double-inventory-deduction.
*   **Root Cause**: Di sistem terdistribusi, pengiriman event dijamin *at-least-once*, bukan *exactly-once*. Consumer menerima delivery ulang akibat transient ACK timeout.
*   **Mitigasi**: Simpan `event_id` atau `idempotency_key` di Consumer DB menggunakan skema `INSERT ON CONFLICT DO NOTHING` / unique constraint sebelum memproses muatan event.

### 3. Cascading Retry Thundering Herd
*   **Gejala**: Ketika service B mulai lambat, traffic masuk ke service B justru melonjak 10x lipat, menyebabkan crash permanen.
*   **Root Cause**: Service A mengonfigurasi retry linear tanpa jeda dan tanpa batasan (*tight-loop retry*).
*   **Mitigasi**: Wajibkan *Exponential Backoff with Full Jitter*, batasi *max retries* (maksimum 3 kali), dan hentikan proses jika *Circuit Breaker* memasuki state `OPEN`.

### 4. Distributed Tracing Context Leakage
*   **Gejala**: Trace di Jaeger / Datadog terputus menjadi span-span tunggal yang tidak terhubung antar service.
*   **Root Cause**: Goroutine baru atau asynchronous consumer tidak mengekstrak atau menyuntikkan (*inject/extract*) header `traceparent` dari incoming message/request.
*   **Mitigasi**: Pastikan propagator W3C dieksekusi pada setiap layer network boundary (gRPC metadata, HTTP headers, Kafka record headers).

---

## 11. Best Practices (Production Checklist)

- [ ] **Database Integrity**:
  - [ ] Polling Outbox menggunakan `SELECT ... FOR UPDATE SKIP LOCKED` untuk mencegah race condition antar-worker.
  - [ ] Indeks yang sesuai pada kolom query Outbox (`status`, `created_at`).
  - [ ] Strategi pembersihan tabel outbox berkala (*Partition Pruning* harian/mingguan).
- [ ] **Network & Resiliency**:
  - [ ] Semua synchronous network call dibungkus dengan context timeout yang ketat (maksimal 2-3 detik).
  - [ ] Circuit Breaker terpasang di semua outbound integration point (downstream API, 3rd party payment).
  - [ ] Retry hanya diterapkan pada *Idempotent operations* dan *Transient errors* (HTTP 502, 503, 504; bukan 400 Bad Request atau 404 Not Found).
- [ ] **Observability**:
  - [ ] W3C `traceparent` diinjeksi ke setiap pesan Kafka dan request gRPC/HTTP.
  - [ ] Metrik p95/p99 latency, RPS, dan error-rate diekspos melalui endpoint Prometheus.
  - [ ] Circuit Breaker state change (`CLOSED` -> `OPEN`) memicu alert tingkat *Warning* ke Slack/Opsgenie.

---

## 12. Hands-on Practice

Target Direktori: `hands-on/m02/`

### Skenario
Membangun microservice pemrosesan pesanan yang mengimplementasikan *Transactional Outbox Pattern* dan memvalidasi ketahanan sistem menggunakan *Circuit Breaker*.

### Langkah-langkah
1.  **Inisialisasi Project**:
    ```bash
    mkdir -p hands-on/m02
    cd hands-on/m02
    go mod init enterprise-dist-sys
    go get github.com/google/uuid github.com/lib/pq
    ```
2.  **Setup Database (Docker)**:
    Jalankan PostgreSQL lokal:
    ```bash
    docker run -d --name pg-dist-sys \
      -e POSTGRES_USER=postgres \
      -e POSTGRES_PASSWORD=postgres \
      -e POSTGRES_DB=orders_db \
      -p 5432:5432 postgres:15-alpine
    ```
3.  **Terapkan Skema Database**:
    Simpan file SQL dari Bab 7.1 ke `hands-on/m02/schema.sql`, lalu jalankan:
    ```bash
    docker exec -i pg-dist-sys psql -U postgres -d orders_db < schema.sql
    ```
4.  **Implementasikan Kode Service**:
    Simpan kode dari Bab 7.2, 7.3, dan 7.4 ke dalam file masing-masing di direktori `hands-on/m02/`.
5.  **Buat Driver Pengujian (`hands-on/m02/main.go`)**:
    ```go
    package main

    import (
    	"context"
    	"database/sql"
    	"fmt"
    	"log"
    	"time"

    	"github.com/google/uuid"
    	_ "github.com/lib/pq"
    )

    func main() {
    	connStr := "postgres://postgres:postgres@localhost:5432/orders_db?sslmode=disable"
    	db, err := sql.Open("postgres", connStr)
    	if err != nil {
    		log.Fatalf("Cannot connect to db: %v", err)
    	}
    	defer db.Close()

    	repo := NewOrderRepository(db)
    	producer := &MockKafkaProducer{}
    	publisher := NewOutboxPublisher(db, producer, 10)

    	ctx, cancel := context.WithCancel(context.Background())
    	defer cancel()

    	// Jalankan outbox background publisher
    	go publisher.StartPoller(ctx, 500*time.Millisecond)

    	// Simulasi pembuatan order
    	log.Println("Creating orders...")
    	for i := 1; i <= 3; i++ {
    		order := Order{
    			ID:         uuid.New().String(),
    			CustomerID: fmt.Sprintf("CUST-%03d", i),
    			Amount:     float64(i * 150000),
    			Status:     "CREATED",
    		}
    		if err := repo.CreateOrderWithOutbox(ctx, order); err != nil {
    			log.Printf("Failed to create order: %v", err)
    		}
    	}

    	// Uji Circuit Breaker
    	cb := NewCircuitBreaker(2, 2*time.Second)
    	log.Println("Testing Circuit Breaker...")

    	unstableService := func() error {
    		return fmt.Errorf("downstream timeout")
    	}

    	for i := 1; i <= 4; i++ {
    		err := cb.Execute(unstableService)
    		log.Printf("Execution #%d: %v", i, err)
    		time.Sleep(200 * time.Millisecond)
    	}

    	// Tunggu cooldown breaker
    	time.Sleep(2500 * time.Millisecond)
    	log.Println("After cooldown, attempting half-open recovery test...")
    	err = cb.Execute(func() error {
    		log.Println("Downstream recovered!")
    		return nil
    	})
    	log.Printf("Execution Post-Cooldown: %v", err)

    	time.Sleep(2 * time.Second) // Biarkan publisher selesai
    }
    ```
6.  **Eksekusi Program**:
    ```bash
    go run .
    ```

---

## 13. Exercises

### Level Easy
Modifikasi implementasi Circuit Breaker di `circuit_breaker.go` agar mendukung metrics counter: catat jumlah total request yang ditolak oleh circuit breaker saat status `OPEN`.

### Level Medium
Tambahkan mekanisme *Exponential Backoff* pada method `Execute` di caller side sehingga jika circuit breaker mengembalikan error sementara atau downstream gagal, caller mencoba melakukan retry maksimal 3 kali sebelum menyerah.

### Level Hard
Ubah polling loop pada `outbox_publisher.go` untuk menangani skenario di mana koneksi broker terputus. Tambahkan *dead-letter strategy*: jika sebuah event outbox gagal dikirim sebanyak 5 kali berturut-turut, tandai statusnya menjadi `FAILED_DEADLETTER` dan tulis rincian error ke kolom `last_error` (buat migration tambahan pada skema).

---

## 14. Challenge

**Skenario**: Sistem Pembayaran Multi-Tenant Rentan terhadap Distributed Deadlock.  
Anda adalah Staff Software Architect di sebuah platform FinTech B2B. Terjadi insiden produksi: saat dua transaksi transfer peer-to-peer terjadi secara bersamaan antara dua akun yang sama dengan arah berlawanan (Akun X transfer ke Akun Y, dan Akun Y transfer ke Akun X), sistem mengalami *Distributed Deadlock* pada level saga execution dan database row-level locking.

**Tugas Arsitektur**:
1.  Rancang mekanisme pencegahan deadlock (*Deadlock Prevention Protocol*) tanpa mengorbankan performa konkurensi transfer secara global.
2.  Desain arsitektur *Idempotent Distributed Compensation Engine* yang mampu menyelesaikan saga ketika satu sisi transaksi transfer mengalami crash tepat di tengah proses *in-flight*.
3.  Tuliskan dokumen RFC singkat (arsitektur state machine, pengurutan akuisisi lock, deteksi siklus, mitigasi out-of-order events).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Konseptual)
1. **Mengapa *Two-Phase Commit* (2PC) umumnya dihindari pada arsitektur microservices skala besar?**
   * A. Karena tidak mendukung database relasional.
   * B. Karena merupakan protokol blocking yang meningkatkan latency dan mengurangi ketersediaan sistem (*availability*).
   * C. Karena data yang dikirim selalu tidak konsisten.
   * D. Karena 2PC hanya bisa bekerja di jaringan localhost.
2. **Apa peran utama dari query `SKIP LOCKED` pada database relasional dalam implementasi Outbox Poller?**
   * A. Mengabaikan record yang memiliki primary key ganda.
   * B. Mengizinkan multi-worker membaca batch data outbox secara paralel tanpa saling memblokir atau memproses baris yang sama.
   * C. Memaksa database untuk tidak menulis WAL log.
   * D. Menghapus data outbox secara otomatis setelah dibaca.
3. **Pada Circuit Breaker, status apa yang memungkinkan sejumlah kecil request diteruskan untuk menguji apakah dependensi downstream sudah pulih?**
   * A. OPEN
   * B. CLOSED
   * C. HALF-OPEN
   * D. PASSIVE
4. **Apa yang dimaksud dengan *At-Least-Once Delivery* dalam pengiriman pesan via Message Broker?**
   * A. Pesan dipastikan terkirim tepat satu kali tanpa duplikasi.
   * B. Pesan dijamin sampai setidaknya satu kali, namun terdapat kemungkinan duplikasi pesan jika ACK jaringan hilang.
   * C. Pesan hanya dikirim jika downstream consumer sedang online.
   * D. Pesan langsung dihapus dari broker sebelum dikonsumsi.
5. **W3C TraceContext mendefinisikan header standar untuk context propagation terdistribusi. Header manakah yang memuat ID trace dan span induk?**
   * A. `x-correlation-id`
   * B. `traceparent`
   * C. `authorization`
   * D. `x-request-id`

### Bagian 2: Intermediate (Analisis Arsitektur)
1. Jelaskan bagaimana *Change Data Capture* (CDC) berbasis Debezium dapat menyelesaikan masalah degradasi performa I/O yang umum dialami oleh metode *Polling Outbox Worker*!
2. Dalam *Saga Pattern*, apa perbedaan fundamental antara *Forward Recovery* dan *Backward Recovery*? Berikan contoh skenario penggunaan untuk masing-masing tipe recovery.
3. Mengapa penambahan parameter *Full Jitter* sangat krusial saat mengimplementasikan *Exponential Backoff* pada sistem dengan ribuan client serentak?
4. Bagaimana sebuah consumer microservice menangani *out-of-order events* (event yang tiba tidak berurutan, misal: `OrderCancelled` tiba sebelum `OrderCreated`)?
5. Jelaskan risiko arsitektur jika sebuah *Saga Orchestrator* menyimpan state-nya di dalam memory instance aplikasi alih-alih di media penyimpanan persisten (*durable execution*)!

### Bagian 3: Skenario Kasus Produksi
1. **Kasus 1: Kafka Broker Outage**:  
   Sistem Anda menggunakan Transactional Outbox. Tiba-tiba seluruh cluster Kafka mengalami *outage* total selama 45 menit selama jam sibuk. Jelaskan apa yang terjadi pada aplikasi Order Service, tabel outbox di database PostgreSQL, dan bagaimana strategi mitigasi agar database utama tidak kehabisan *disk space* akibat lonjakan record outbox.
2. **Kasus 2: Partial Compensation Failure**:  
   Dalam sebuah transaksi pemesanan tiket pesawat (Flight Service, Hotel Service, Payment Service), Hotel Service mengalami kegagalan reservasi. Orchestrator memicu kompensasi ke Flight Service untuk membatalkan tiket yang sudah terbit. Namun, Flight Service mengembalikan HTTP 500 terus menerus karena API maskapai pihak ketiga sedang down. Bagaimana arsitektur Anda menangani kegagalan pada tahap kompensasi ini tanpa merusak integritas finansial?
3. **Kasus 3: Cascading Timeout Discovery**:  
   Berdasarkan grafik OpenTelemetry, API Gateway Anda melaporkan lonjakan latensi p99 dari 100ms menjadi 15.000ms, diikuti kegagalan massal HTTP 504 Gateway Timeout. Log menunjukkan service hilir `Inventory-Service` lambat, tetapi utilisasi CPU/Memory `Inventory-Service` sangat rendah (<15%). Langkah investigasi apa yang akan Anda lakukan untuk menemukan *root cause* dan mekanisme apa yang seharusnya mencegah degradasi ini merambat ke API Gateway?

---

## 16. Kunci Jawaban & Panduan Solusi Quiz

### Bagian 1: Basic
1. **B**. 2PC mengharuskan semua resource menahan kunci (*lock*) hingga koordinator selesai. Kegagalan satu node menahan resource lain, melanggar prinsip ketersediaan dan latensi rendah sistem terdistribusi.
2. **B**. `SKIP LOCKED` menginstruksikan DB untuk melompati baris yang sedang dikunci oleh worker transaksi lain, memungkinkan konkurensi worker tanpa collision.
3. **C**. State `HALF-OPEN` adalah fase *probing* untuk menguji kesehatan downstream.
4. **B**. Jaminan pengiriman di mana pesan dijamin terkirim, namun kegagalan jaringan pada pengiriman ACK dapat menyebabkan pengiriman ulang (duplikasi).
5. **B**. Standar W3C menetapkan header `traceparent` (format: `version-trace_id-parent_id-trace_flags`).

### Bagian 2: Intermediate
1. **CDC vs Polling**: Polling menjalankan query SQL `SELECT` berkala yang membebani CPU, buffer pool, dan disk I/O database produksi. CDC membaca langsung binary log / WAL di level file storage secara asynchronous tanpa melalui SQL query parser engine, menghasilkan overhead mendekati nol terhadap transaksi transaksional database.
2. **Forward vs Backward Recovery**:
   *   *Backward Recovery*: Mengembalikan state ke kondisi awal menggunakan transaksi kompensasi saat kegagalan terjadi (contoh: Membatalkan pesanan dan mengembalikan limit kartu kredit saat stok barang habis).
   *   *Forward Recovery*: Tidak membatalkan langkah sebelumnya, melainkan terus mencoba memperbaiki atau melanjutkan ke langkah alternatif hingga berhasil (contoh: Jika pengiriman email invoice gagal, sistem tidak membatalkan pembayaran melainkan melakukan retry ke provider email sekunder).
3. **Pentingnya Full Jitter**: Tanpa jitter, ribuan client yang gagal pada detik $T$ akan melakukan retry pada interval yang persis sama (misal $T+2$, $T+4$, $T+8$), menciptakan siklus lonjakan beban (*thundering herd / retry storm*) berkala yang mencegah downstream pulih. Jitter meratakan distribusi retry secara acak melintasi rentang waktu.
4. **Menangani Out-of-Order Events**: Menggunakan pendekatan *Optimistic State Versioning* (menyertakan versi sequence/timestamp pada event) atau menyimpan event yang datang lebih awal ke dalam *Pending Buffer Store* sampai event pendahulunya selesai diproses.
5. **State di Memory Orchestrator**: Jika instance orchestrator mengalami *restart* (OOM kill, redeployment, host failover), semua state transaksi yang sedang *in-flight* akan hilang seketika, menyebabkan *orphaned sagas* di mana downstream services menggantung tanpa instruksi kompensasi maupun kelanjutan.

### Bagian 3: Skenario Kasus Produksi
1. **Solusi Kasus 1**:
   *   Aplikasi `Order Service` tetap berjalan normal menerima pesanan dari pengguna, karena hanya menulis ke DB lokal dan tabel outbox lokal (decoupled).
   *   Tabel outbox akan membengkak. Mitigasi: Terapkan *Backpressure Rate Limiting* di API Gateway jika sisa storage DB menyentuh ambang kritis (misal: 80%). Poller outbox dihentikan sementara atau dikonfigurasi untuk mengeksekusi exponential backoff agar tidak membuang resource mencoba koneksi Kafka yang mati. Tambahkan disk auto-scaling pada database volume.
2. **Solusi Kasus 2**:
   *   Saga Orchestrator tidak boleh menyerah jika kompensasi gagal. Status kompensasi harus dipersistenkan sebagai `COMPENSATION_PENDING`.
   *   Gunakan *Durable Retry Queue* (asynchronous retry worker) dengan delay bertingkat untuk terus mencoba kompensasi Flight Service.
   *   Jika batas maksimal percobaan tercapai (misal: 24 jam), transaksi dialihkan ke status `MANUAL_INTERVENTION_REQUIRED`, memicu alert kritis (*dead-letter alert*) ke tim operasional finansial untuk rekonsiliasi manual via portal support maskapai.
3. **Solusi Kasus 3**:
   *   *Root cause*: Database connection pool exhaustion, downstream third-party lock contention, atau thread-pool starvation pada `Inventory-Service` (resource sistem terlihat rendah karena thread dalam kondisi *blocked/waiting* I/O, bukan *busy CPU*).
   *   *Mekanisme pencegah*:
       1. Set *Connection & Read Timeout* ketat pada pemanggil (upstream) ke `Inventory-Service` (misal 500ms).
       2. Terapkan *Circuit Breaker* di caller: ketika p99 melampaui SLA, buka sirkuit untuk langsung memutus request (*fast-fail*).
       3. Terapkan *Bulkhead Pattern* untuk membatasi jumlah *concurrent requests* ke `Inventory-Service` sehingga degradasi tersebut tidak menguras thread pool di API Gateway.

---

## 17. Summary

1. **Transactional Outbox Pattern** menyelesaikan dilema klasik *Dual-Write* dengan menjamin atomisitas penyimpanan data lokal dan penerbitan event melalui pemanfaatan transaksi lokal ACID yang dipadukan dengan CDC (*Change Data Capture*) atau Polling Publisher.
2. **Saga Orchestration** merupakan pendekatan standar enterprise untuk mengelola alur bisnis lintas microservices yang kompleks; memisahkan alur eksekusi sukses (*forward recovery*) dan skenario kegagalan melalui transaksi kompensasi (*backward recovery*).
3. **Resilience Engineering** bukan sekadar menangani error, melainkan mencegah *cascading failures*. Kombinasi terukur antara **Circuit Breaker**, **Bulkhead Isolation**, serta **Exponential Backoff with Full Jitter** adalah fondasi mutlak untuk mempertahankan ketersediaan sistem di tingkat produksi.
4. **Context Propagation** berbasis standar W3C TraceContext memastikan setiap hop jaringan (synchronous RPC maupun asynchronous event queue) dapat dilacak secara end-to-end, memberikan visibilitas penuh terhadap latensi dan anomali sistem terdistribusi.