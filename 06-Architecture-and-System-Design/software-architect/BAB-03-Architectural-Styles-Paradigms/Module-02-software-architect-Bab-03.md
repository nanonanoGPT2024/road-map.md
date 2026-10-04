# Kurikulum Rekayasa Perangkat Lunak Tingkat Enterprise
## Kategori: 06 - Architecture and System Design
### BAB 03: Architectural Styles & Paradigms
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Memilih Paradigma Arsitektur**: Mengidentifikasi trade-off teknis antara *Event-Driven Architecture (EDA)*, *CQRS/Event Sourcing*, *Hexagonal/Clean Architecture*, dan *Space-Based Architecture* untuk domain bisnis skala enterprise berkonkurensi tinggi.
2. **Mengimplementasikan Pola Konsistensi Terdistribusi**: Merancang dan mengeksekusi mekanisme *Distributed Transactions* menggunakan pola *Saga (Choreography & Orchestration)* serta *Transactional Outbox Pattern* dengan jaminan *at-least-once delivery* dan *idempotent processing*.
3. **Membangun Sistem Resilien Anti-Fragile**: Mengimplementasikan *fault tolerance patterns* (*Circuit Breaker*, *Bulkhead*, *Rate Limiting*, dan *Backpressure*) pada komunikasi sinkron dan asinkron.
4. **Menerapkan Prinsip Observabilitas End-to-End**: Menyusun konfigurasi telemetri terdistribusi (*distributed tracing*, korelasi log dengan W3C Trace Context) untuk memvalidasi interaksi lintas batas paradigma arsitektural.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam pada domain berikut:
* **Fundamental Desain Perangkat Lunak**: Pemahaman tingkat lanjut terhadap OOP, Functional Programming, Domain-Driven Design (Strategic & Tactical Design: *Bounded Context*, *Aggregate Root*, *Value Object*, *Domain Event*).
* **Jaringan & Sistem Terdistribusi**: Pemahaman protokol TCP/IP, HTTP/2, gRPC, enkapsulasi data (JSON, Protocol Buffers), serta teorema CAP dan PACELC.
* **Database & Messaging Systems**: Kemahiran menggunakan RDBMS (PostgreSQL) termasuk level isolasi transaksi (*ACID*, *Read Committed*, *Serializable*), serta Message Broker berlatensi rendah (Apache Kafka atau RabbitMQ).
* **Bahasa Pemrograman**: Kemahiran membaca dan menulis kode berbasis tipe data statis (contoh implementasi modul ini menggunakan **Go 1.22+**).

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi arsitektur enterprise modern jarang bertumpu pada satu gaya arsitektur tunggal (*pure architectural style*). Dalam sistem berskala besar, kita menggabungkan berbagai paradigma: **Hexagonal Architecture** di level mikro (komponen/layanan internal), **CQRS & Event Sourcing** di level agregat transaksi kompleks, dan **Event-Driven Architecture (EDA)** di level komunikasi lintas *Bounded Context*.

```
+---------------------------------------------------------------------------------------+
|                                    BOUNDED CONTEXT                                    |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                         Hexagonal (Ports & Adapters)                          |   |
|   |                                                                               |   |
|   |   [Primary Adapter]            [Application Core]         [Secondary Adapter] |   |
|   |   - gRPC Server       ----->   - Command Handlers   -----> - Outbox Relay     |   |
|   |   - REST API                   - Domain Aggregates         - Postgres Repo    |   |
|   |   - Kafka Consumer             - Domain Events             - Redis Cache      |   |
|   +-------------------------------------------------------------------------------+   |
|                                            |                                          |
|                                            v (Emit Domain Event via Transactional Outbox)
+---------------------------------------------------------------------------------------+
                                             |
                                    [Apache Kafka Event Bus]
                                             |
         +-----------------------------------+-----------------------------------+
         | (Asynchronous Integration)                                            |
         v                                                                       v
+----------------------------------+                   +----------------------------------+
|      ORDER READ-MODEL (CQRS)     |                   |      INVENTORY RESERVATION       |
|  - Materialized View (Elastic)   |                   |  - Saga Choreography Step        |
|  - Low Latency Query Engine      |                   |  - Idempotent Event Consumer     |
+----------------------------------+                   +----------------------------------+
```

#### Komponen Internal Inti:
1. **Hexagonal Core (Ports and Adapters)**:
   - **Domain Core**: Berisi *pure business logic*, entitas, dan *invariants*. Tidak memiliki dependensi ke pustaka eksternal, framework, atau basis data.
   - **Inbound Ports**: Antarmuka (*interfaces*) yang mengekspos use-case domain ke dunia luar (misal: `CreateOrderUseCase`).
   - **Inbound Adapters**: Pemicu eksekusi domain (misal: HTTP Controller, gRPC Service Handler, Kafka Message Consumer).
   - **Outbound Ports**: Antarmuka yang dibutuhkan domain untuk berinteraksi dengan infrastruktur eksternal (misal: `OrderRepository`, `EventPublisher`).
   - **Outbound Adapters**: Implementasi konkret port keluar (misal: SQL Repository dengan Gorm/pgx, Redis Cache Adapter, Kafka Producer Adapter).

2. **Command Query Responsibility Segregation (CQRS)**:
   - **Command Side (Write)**: Mengoptimalkan integritas data transaksi (*ACID*). Menerima mutasi data, memvalidasi aturan bisnis melalui *Aggregate Root*, dan menuliskan event/state ke *primary database*.
   - **Query Side (Read)**: Mengoptimalkan kecepatan pembacaan (*high-throughput, low-latency*). Menggunakan denormalisasi model (misal: Elasticsearch, ClickHouse, atau PostgreSQL Read Replica berindeks khusus) yang diperbarui secara asinkron via *event streams*.

3. **Transactional Outbox & Dual-Write Prevention**:
   Masalah terbesar dalam arsitektur terdistribusi adalah *dual-write problem*: menulis ke basis data lokal dan mengirim event ke message broker tidak dapat dilakukan dalam satu transaksi atomik tanpa *Two-Phase Commit (2PC)* yang lambat dan rapuh.
   - **Solusi Outbox**: State domain dan pesan event disimpan dalam satu transaksi atomik RDBMS lokal ke tabel `outbox`.
   - **Outbox Worker/CDC (Change Data Capture)**: Membaca tabel outbox (menggunakan Debezium engine atau *polling log miner*) lalu mempublikasikan pesan ke broker (Kafka). Setelah konfirmasi *acknowledgement* (ack) dari broker diterima, status pesan ditandai terkirim.

4. **Saga Pattern untuk Konsistensi Transaksi Terdistribusi**:
   Menggantikan distributed locking dengan urutan transaksi lokal:
   - **Choreography**: Setiap layanan mendengarkan domain event dari layanan lain dan secara mandiri memutuskan langkah transaksi berikutnya tanpa koordinator sentral. Sangat fleksibel namun rawan *spaghetti dependency* jika alur melebihi 4-5 langkah.
   - **Orchestration**: Komponen orchestrator terpusat mendikte langkah-langkah kerja melalui command spesifik, menunggu balasan event, dan mengeksekusi *compensating transactions* jika terjadi kegagalan sistemik.

---

### 4. Why & What

| Dimensi | Monolith Tradisional (Layered/N-Tier) | Arsitektur Enterprise Modern (Hexagonal + EDA + CQRS) |
| :--- | :--- | :--- |
| **Coupling** | *Tight Coupling* antar modul melalui pemanggilan metode dalam satu memori (*in-process*). | *Loose Coupling* via isolasi antarmuka domain dan *asynchronous event contracts*. |
| **Scalability** | Skalabilitas vertikal atau replikasi seluruh instance aplikasi secara monolitik. | Skalabilitas independen per komponen beban (Write Service, Read Service, Worker) secara granular. |
| **Maintainability** | Perubahan skema database sering membocorkan dependensi ke layer UI/Presentation. | Layer domain terlindungi penuh dari perubahan framework, database, atau broker eksternal. |
| **Fault Isolation** | Kegagalan thread pada satu modul berpotensi merusak *runtime context* seluruh aplikasi. | Kegagalan dipagari (*bulkheaded*); sistem mengalami degradasi performa bertahap (*graceful degradation*). |
| **Complexity** | Kompleksitas operasional rendah, kompleksitas kode tinggi saat membesar (*spaghetti*). | Kompleksitas arsitektur & operasional tinggi, kompleksitas domain terdistribusi terkendali. |

---

### 5. How (Workflow Detail)

Berikut adalah alur data lengkap implementasi produksi: Transaksi Pembuatan Pesanan (*Order Creation*) menggunakan **Hexagonal Core**, **Transactional Outbox**, dan **Asynchronous Materialized View Sync**.

```
[Client]              [Order Controller]     [Order Service]      [PostgreSQL]        [Outbox Relay]     [Kafka]         [Read Model Worker]   [Elastic/Read DB]
   |                         |                     |                   |                     |               |                    |                    |
   |--- 1. POST /orders ---->|                     |                   |                     |               |                    |                    |
   |                         |-- 2. Execute Cmd -->|                   |                     |               |                    |                    |
   |                         |   (Validate Auth)   |-- 3. Mutate Domain|                     |               |                    |                    |
   |                         |                     |   (Check Rules)   |                     |               |                    |                    |
   |                         |                     |-- 4. Begin Tx --->|                     |               |                    |                    |
   |                         |                     |   Insert Order    |                     |               |                    |                    |
   |                         |                     |   Insert Outbox --|                     |               |                    |                    |
   |                         |                     |-- 5. Commit Tx -->|                     |               |                    |                    |
   |                         |<-- 6. Success (201)-|                   |                     |               |                    |                    |
   |<-- 7. Response (UUID) --|                     |                   |                     |               |                    |                    |
   |                         |                     |                   |                     |               |                    |                    |
   |                         |                     |                   |-- 8. Poll/Stream -->|               |                    |                    |
   |                         |                     |                   |   Unprocessed Event |               |                    |                    |
   |                         |                     |                   |                     |-- 9. Publish >|                    |                    |
   |                         |                     |                   |                     |    Ack OK     |                    |                    |
   |                         |                     |                   |<- 10. Mark Sent ----|               |                    |                    |
   |                         |                     |                   |                     |               |-- 11. Consume ---->|                    |
   |                         |                     |                   |                     |               |   Event Stream     |-- 12. Upsert Read->|
   |                         |                     |                   |                     |               |                    |    Materialized    |
```

1. **Inbound Processing**: Klien mengirim payload pembuatan order. Inbound adapter (Controller) mendekode HTTP request menjadi *domain command* (`CreateOrderCommand`).
2. **Domain Evaluation**: Application Service memuat agregat yang relevan, mengeksekusi logika bisnis (misal: validasi batas kredit, validasi kuota).
3. **Atomic Persistence**: Secondary database adapter membuka koneksi transaksi database lokal (`BEGIN TRANSACTION`). Data pesanan disimpan ke tabel `orders`, dan payload domain event disimpan ke tabel `order_outbox`. Keduanya di-commit serentak (`COMMIT`).
4. **Immediate Client Response**: Client menerima respon `HTTP 201 Created` beserta referensi UUID. Tidak ada dependensi latensi ke antrean pesan Kafka.
5. **Change Relay**: Background worker (Outbox Relay) membaca data `order_outbox` yang berstatus `PENDING`, mengirimkan event ke topik Kafka dengan partisi berbasis `order_id` (menjaga *ordering*), lalu mengubah status outbox menjadi `PROCESSED`.
6. **Consumer Read-Model Sync**: Layanan pembaca (CQRS Read Service) mengonsumsi event dari Kafka secara idempoten, memperbarui indeks pembacaan (*Materialized View*) di Elasticsearch atau Read DB.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Kantor Notaris & Sistem Kliring Bank
Bayangkan arsitektur tradisional seperti seorang pedagang yang menandatangani kontrak jual beli properti, lalu harus berlari sendiri ke kantor pajak, bank penjual, kantor pertanahan, dan dinas utilitas sebelum transaksi dinyatakan sah. Jika pelari tersebut pingsan di tengah jalan, transaksi menggantung (*Dual-Write failure*).

Pola **Hexagonal + Outbox + EDA** setara dengan:
1. **Hexagonal**: Ruang kerja notaris kedap suara (*Domain Core*). Notaris tidak peduli klien datang naik helikopter (*gRPC*) atau sepeda (*REST HTTP*). Notaris hanya memproses berkas kontrak (*Command*).
2. **Transactional Outbox**: Dokumen sah yang ditandatangani dimasukkan ke dalam brankas fisik kantor notaris bersamaan dengan buku ekspedisi pengiriman (*Atomic DB Transaction*).
3. **Event-Driven Broker**: Kurir profesional (*Outbox Relay*) mengambil berkas dari brankas secara berkala dan menyerahkannya ke kantor pos sentral (*Message Broker*).
4. **CQRS**: Papan display di depan kantor notaris langsung menampilkan ringkasan status berkas tanpa ada orang asing yang diizinkan menggeledah brankas internal notaris.

```
       [ HTTP Adapter ]     [ gRPC Adapter ]     [ Message Adapter ]
              \                    |                    /
               \                   |                   /
         +---------------------------------------------------+
         |             APPLICATION INBOUND PORTS             |
         |  +---------------------------------------------+  |
         |  |             HEXAGONAL DOMAIN CORE           |  |
         |  |                                             |  |
         |  |   - Aggregates        - Business Invariants |  |
         |  |   - Value Objects     - Domain Services     |  |
         |  +---------------------------------------------+  |
         |             APPLICATION OUTBOUND PORTS            |
         +---------------------------------------------------+
               /                   |                   \
              /                    |                    \
       [ SQL Adapter ]     [ Outbox Adapter ]    [ Broker Adapter ]
              |                    |                    |
              v                    v                    v
      [(Postgres DB)]      [(Outbox Table)]       [Kafka Cluster]
```

---

### 7. Simple Example & Practical Example

Berikut implementasi produksi standar industri menggunakan **Go** dengan arsitektur Hexagonal, Transactional Outbox, dan Idempotent Consumer.

#### A. Inbound Port, Outbound Port & Domain Model
```go
package domain

import (
	"context"
	"errors"
	"time"
)

var (
	ErrInvalidOrderAmount = errors.New("order total must be greater than zero")
	ErrOrderAlreadyPaid   = errors.New("cannot cancel an already paid order")
)

type OrderID string
type OrderStatus string

const (
	StatusPending   OrderStatus = "PENDING"
	StatusCompleted OrderStatus = "COMPLETED"
	StatusCancelled OrderStatus = "CANCELLED"
)

type Order struct {
	ID        OrderID
	CustomerID string
	Amount    float64
	Status    OrderStatus
	CreatedAt time.Time
}

func NewOrder(id OrderID, customerID string, amount float64) (*Order, error) {
	if amount <= 0 {
		return nil, ErrInvalidOrderAmount
	}
	return &Order{
		ID:         id,
		CustomerID: customerID,
		Amount:     amount,
		Status:     StatusPending,
		CreatedAt:  time.Now().UTC(),
	}, nil
}

// Inbound Port
type OrderUseCase interface {
	CreateOrder(ctx context.Context, cmd CreateOrderCommand) (*Order, error)
}

type CreateOrderCommand struct {
	OrderID    string
	CustomerID string
	Amount     float64
}

// Outbound Ports
type OrderRepository interface {
	SaveOrderWithOutbox(ctx context.Context, order *Order, outboxEvent *OutboxRecord) error
}

type OutboxRecord struct {
	ID           string
	AggregateID  string
	EventType    string
	PayloadJSON  []byte
	CreatedAt    time.Time
}
```

#### B. Implementation: Secondary Adapter (PostgreSQL Transactional Outbox)
```go
package postgres

import (
	"context"
	"database/sql"
	"fmt"
	"domain"
)

type SQLOrderRepository struct {
	db *sql.DB
}

func NewSQLOrderRepository(db *sql.DB) *SQLOrderRepository {
	return &SQLOrderRepository{db: db}
}

func (r *SQLOrderRepository) SaveOrderWithOutbox(ctx context.Context, order *domain.Order, event *domain.OutboxRecord) error {
	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// 1. Simpan State Domain
	orderQuery := `INSERT INTO orders (id, customer_id, amount, status, created_at) 
	               VALUES ($1, $2, $3, $4, $5)`
	_, err = tx.ExecContext(ctx, orderQuery, order.ID, order.CustomerID, order.Amount, order.Status, order.CreatedAt)
	if err != nil {
		return fmt.Errorf("failed to insert order: %w", err)
	}

	// 2. Simpan Outbox Event dalam Transaksi yang Sama (Anti Dual-Write Bug)
	outboxQuery := `INSERT INTO transactional_outbox (id, aggregate_id, event_type, payload, status, created_at) 
	                VALUES ($1, $2, $3, $4, 'PENDING', $5)`
	_, err = tx.ExecContext(ctx, outboxQuery, event.ID, event.AggregateID, event.EventType, event.PayloadJSON, event.CreatedAt)
	if err != nil {
		return fmt.Errorf("failed to insert outbox record: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}
```

#### C. Outbox Publisher Worker (At-Least-Once Delivery Relay)
```go
package worker

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"time"
)

type KafkaPublisher interface {
	Publish(ctx context.Context, topic string, key string, value []byte) error
}

type OutboxWorker struct {
	db        *sql.DB
	publisher KafkaPublisher
}

func NewOutboxWorker(db *sql.DB, pub KafkaPublisher) *OutboxWorker {
	return &OutboxWorker{db: db, publisher: pub}
}

func (w *OutboxWorker) Start(ctx context.Context, pollInterval time.Duration) {
	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("Stopping outbox worker gracefully...")
			return
		case <-ticker.C:
			w.processOutboxBatch(ctx)
		}
	}
}

func (w *OutboxWorker) processOutboxBatch(ctx context.Context) {
	// SELECT FOR UPDATE SKIP LOCKED untuk menghindari konkurensi antar multiple worker instances
	query := `SELECT id, aggregate_id, event_type, payload 
	          FROM transactional_outbox 
	          WHERE status = 'PENDING' 
	          ORDER BY created_at ASC LIMIT 50 FOR UPDATE SKIP LOCKED`

	tx, err := w.db.BeginTx(ctx, nil)
	if err != nil {
		log.Printf("Worker tx begin err: %v\n", err)
		return
	}
	defer tx.Rollback()

	rows, err := tx.QueryContext(ctx, query)
	if err != nil {
		log.Printf("Worker query err: %v\n", err)
		return
	}
	defer rows.Close()

	type item struct {
		id, aggID, eventType string
		payload              []byte
	}
	var batch []item

	for rows.Next() {
		var it item
		if err := rows.Scan(&it.id, &it.aggID, &it.eventType, &it.payload); err != nil {
			continue
		}
		batch = append(batch, it)
	}

	for _, it := range batch {
		err := w.publisher.Publish(ctx, "order-events", it.aggID, it.payload)
		if err != nil {
			log.Printf("Failed to emit event %s to kafka: %v\n", it.id, err)
			return // Hentikan batch agar konsistensi urutan per aggregate terjaga
		}

		_, err = tx.ExecContext(ctx, `UPDATE transactional_outbox SET status = 'PUBLISHED' WHERE id = $1`, it.id)
		if err != nil {
			log.Printf("Failed to update status for %s: %v\n", it.id, err)
			return
		}
	}

	if err := tx.Commit(); err != nil {
		log.Printf("Worker commit error: %v\n", err)
	}
}
```

#### D. Idempotent Consumer Adapter (Inbound Message Adapter)
```go
package consumer

import (
	"context"
	"database/sql"
	"fmt"
)

type IdempotentConsumer struct {
	db *sql.DB
}

func NewIdempotentConsumer(db *sql.DB) *IdempotentConsumer {
	return &IdempotentConsumer{db: db}
}

// ProcessWithDeduplication menjamin pemrosesan pesan persis satu kali (effectively-once) di layer aplikasi
func (c *IdempotentConsumer) ProcessWithDeduplication(ctx context.Context, messageID string, processFn func() error) error {
	tx, err := c.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// 1. Cek apakah message sudah pernah diproses
	var exists bool
	checkQuery := `SELECT EXISTS(SELECT 1 FROM processed_messages WHERE message_id = $1)`
	if err := tx.QueryRowContext(ctx, checkQuery, messageID).Scan(&exists); err != nil {
		return fmt.Errorf("idempotency check failed: %w", err)
	}

	if exists {
		// Pesan duplikat terdeteksi, abaikan tanpa melempar error sistem
		return nil
	}

	// 2. Eksekusi domain business logic
	if err := processFn(); err != nil {
		return fmt.Errorf("business logic processing failed: %w", err)
	}

	// 3. Simpan ID pesan ke daftar deduplikasi
	insertLog := `INSERT INTO processed_messages (message_id, processed_at) VALUES ($1, NOW())`
	if _, err := tx.ExecContext(ctx, insertLog, messageID); err != nil {
		return fmt.Errorf("failed to record message deduplication: %w", err)
	}

	return tx.Commit()
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Pemrosesan Pembayaran Global Multi-Tenant (Skala FinTech)
* **Konteks**: Platform pemrosesan pembayaran menangani volume transaksi puncak sebesar 45.000 Transaksi Per Detik (TPS) di 12 negara dengan regulasi kedaulatan data finansial (*data residency requirements*).
* **Masalah**:
  - Arsitektur berbasis synchronous REST antar microservices (*Order Service* -> *Payment Service* -> *Risk Engine* -> *Ledger Service*) menyebabkan latensi P99 membengkak hingga 4.800 ms.
  - Sering terjadi kegagalan jaringan parsial di penyedia pihak ketiga (Payment Gateway Bank) yang memicu status *orphan transaction*: uang terpotong dari akun pengguna namun order ditandai gagal.
  - Rekonsiliasi akuntansi manual di akhir hari membutuhkan waktu 6 jam karena inkonsistensi pencatatan *dual-write* antara database operasional dan stream pelaporan.
* **Solusi Arsitektur**:
  1. **Migrasi ke Event-Driven Choreography & Saga Pattern**: Transaksi pemesanan dan pembayaran dipecah menjadi saga independen. Alur reservasi dana dilakukan via *asynchronous events* dengan *state machine engine* (Temporal.io) untuk langkah yang memerlukan batas waktu (*timeout* kompensasi).
  2. **Transactional Outbox Engine dengan Change Data Capture (CDC)**: Menghapus implementasi poller manual berbasis cron; menggantinya dengan Debezium yang membaca *write-ahead log* (WAL) PostgreSQL, menurunkan latensi streaming event dari 1.200 ms menjadi sub-50 ms.
  3. **Double-Entry Bookkeeping CQRS Read-Side**: Menulis mutasi buku besar (*ledger*) secara append-only di Write Node (Postgres), lalu mendistribusikan proyeksi balance ke database in-memory read-only (Redis Clustered + RocksDB) untuk kalkulasi saldo real-time.
* **Hasil**:
  - Latensi respons awal ke pengguna berkurang dari 4.800 ms menjadi 180 ms (*client polling/websocket* untuk resolusi akhir).
  - Status transaksi menggantung berkurang hingga 99,997%.
  - Sistem rekonsiliasi bergeser dari *batch harian* menjadi rekonsiliasi berkelanjutan (*continuous streaming reconciliation*) dengan gap audit di bawah 5 detik.

---

### 9. Trade-offs

```
                  [ COMPLEXITY / OPERATIONAL COST ]
                                  ^
                                  |                 * Event-Driven Saga + CQRS
                                  |                   (High Scalability, High Complexity)
                                  |
                                  |       * Hexagonal + Modular Monolith
                                  |         (Balanced Maintainability)
                                  |
    * Traditional Layered Monolith|
      (Low Ops Cost, Bottleneck)  |
  +-------------------------------+---------------------------------------->
  0                                                              [ THROUGHPUT / AGILITY ]
```

| Gaya / Pola Arsitektur | Keuntungan (Pros) | Biaya & Kompromi (Cons / Trade-offs) |
| :--- | :--- | :--- |
| **Hexagonal Architecture** | Isolasi dependensi total; kemudahan unit testing tanpa mock database eksternal; fleksibilitas migrasi driver infrastruktur. | Overhead penulisan kode antarmuka (*boilerplate DTO, mapper, port interface*); penambahan kurva belajar tim. |
| **CQRS (Segregated Storage)**| Write throughput optimal tanpa indeks pembacaan yang memberatkan; Query model terdenormalisasi berlatensi sangat rendah. | Kompleksitas sinkronisasi data; timbul fenomena *Eventual Consistency* di layer read; duplikasi konsumsi ruang penyimpanan. |
| **Transactional Outbox via CDC** | Konsistensi absolut data lokal dan event (*zero dual-write bug*); tidak memerlukan distributed locking 2PC. | Membutuhkan dependensi infrastruktur tambahan (Kafka Connect, Debezium, engine database WAL access privileges). |
| **Saga Orchestration** | Alur transaksi kompleks mudah dipantau (*central visibility*); menghindari dependensi siklik antar service. | Orchestrator berpotensi menjadi *single point of failure* (jika tidak dirancang resilient); rawan mengarah ke *anemic domain model*. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. "Event-Carried State Transfer" yang Membengkak (Fat Events)
* **Gejala**: Payload pesan event Kafka berisi seluruh histori data objek (lebih dari 1MB per event), memicu saturasi bandwidth broker dan degradasi performa I/O.
* **Troubleshooting**: Pecah event menjadi dua kategori:
  - *Domain Event / Thin Event*: Hanya memuat ID entitas dan atribut yang berubah (misal: `OrderPaidEvent { OrderID, PaidAt }`).
  - *Data Enrichment*: Layanan hilir yang membutuhkan histori lengkap dapat melakukan kueri balik via gRPC atau menggunakan Read Model lokal yang telah diproyeksikan sebelumnya.

#### 2. Mengabaikan *Out-of-Order Message Processing*
* **Gejala**: Status order berubah menjadi `CANCELLED` terlebih dahulu sebelum event `CREATED` selesai diproses, menyebabkan data agregat rusak (*corrupted state*).
* **Penyebab**: Partisi broker Kafka tidak menggunakan entitas ID sebagai *Partition Key*, atau consumer service memiliki *multi-threading pool* yang memproses partisi yang sama secara tidak teratur.
* **Solusi**: Pastikan *Partition Key* selalu menggunakan ID Agregat utama (misal: `order_id`). Gunakan *Sequence Number* atau *Logical Timestamp* di payload domain event untuk memvalidasi urutan mutasi pada agregat penerima.

#### 3. Kebocoran Abstraksi di Hexagonal Architecture
* **Gejala**: Tipe data bawaan basis data (misal: `sql.NullString`, anotasi tag JSON framework Gorm, atau entitas JPA/Hibernate) digunakan di dalam entitas domain inti.
* **Solusi**: Terapkan *Strict Layering Rule*. Domain core hanya boleh menggunakan *native primitive types* atau domain *Value Objects*. Lakukan pemetaan (*mapping*) eksplisit di layer Adapter.

---

### 11. Best Practices (Production Checklist)

Gunakan daftar periksa ini sebelum merilis sistem arsitektur terdistribusi ke lingkungan produksi:

- [ ] **Idempotency Key Guaranteed**: Seluruh consumer event dan endpoint API mutasi memiliki validasi duplikasi berbasis unique key yang disimpan di database transaksional.
- [ ] **Zero Dual-Write Pattern**: Tidak ada kode yang melakukan persistensi database `tx.Commit()` dan `kafka.Produce()` secara berurutan dalam blok instruksi yang sama tanpa Transactional Outbox.
- [ ] **Dead Letter Queue (DLQ) & Poison Pill Handling**: Consumer dikonfigurasi dengan limit *retry backoff*. Pesan rusak (*poison message*) otomatis dialihkan ke DLQ setelah $N$ kali percobaan gagal tanpa memblokir partisi stream.
- [ ] **Observability Trace Propagation**: Setiap pesan di Kafka menyertakan metadata header W3C TraceContext (`traceparent`, `tracestate`) untuk memastikan kesinambungan Distributed Tracing di OpenTelemetry/Jaeger.
- [ ] **Database Connection Pool Sizing**: Rasio pool database diperhitungkan dengan cermat terhadap jumlah worker konkurensi Outbox poller untuk mencegah *connection starvation*.
- [ ] **Saga Compensation Reversibility**: Setiap kompensasi pembatalan di Saga dirancang agar *idempotent* dan *commutative* (dapat dieksekusi berulang kali tanpa mengubah hasil akhir).

---

### 12. Hands-on Practice

Buat workspace lokal pada folder `hands-on/m02/` untuk membangun arsitektur Hexagonal dengan Transactional Outbox dan Kafka secara end-to-end.

#### Langkah 1: Siapkan Lingkungan (Docker Compose)
Simpan file ini di `hands-on/m02/docker-compose.yaml`:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: appsecretpassword
      POSTGRES_DB: enterprise_db
    ports:
      - "5432:5432"
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
```

#### Langkah 2: Skema Basis Data DDL
Simpan file ini di `hands-on/m02/init.sql`:
```sql
CREATE TABLE orders (
    id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactional_outbox (
    id VARCHAR(64) PRIMARY KEY,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE processed_messages (
    message_id VARCHAR(64) PRIMARY KEY,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_outbox_pending ON transactional_outbox(status, created_at) WHERE status = 'PENDING';
```

#### Langkah 3: Eksekusi Eksperimen
1. Jalankan cluster infrastruktur:
   ```bash
   cd hands-on/m02/
   docker compose up -d
   ```
2. Buat file `main.go` yang mengintegrasikan kode di Seksi 7.
3. Simulasikan pengiriman order dan hentikan broker Kafka secara sengaja (`docker compose stop kafka`).
4. Amati bahwa transaksi lokal basis data di tabel `orders` dan `transactional_outbox` tetap berhasil 100% tanpa error (*high resilience*).
5. Nyalakan kembali Kafka (`docker compose start kafka`) dan amati Outbox Worker secara otomatis mempublikasikan seluruh event yang tertunda tanpa kehilangan data (*zero data loss*).

---

### 13. Exercise

#### Level: Easy
Ubah implementasi `Order` domain model agar menambahkan validasi bisnis: Batas transaksi pemesanan tidak boleh melebihi nilai plafon `$50,000` per transaksi tunggal. Buat unit test murni (*zero dependency*) untuk memvalidasi *invariant* tersebut.

#### Level: Medium
Implementasikan skema *Dead Letter Queue (DLQ)* pada adapter `IdempotentConsumer`. Jika prosesor callback melempar error non-transient sebanyak 3 kali berturut-turut, pindahkan rekod pesan ke tabel basis data `consumer_dlq` lengkap dengan stack trace error dan payload aslinya.

#### Level: Hard
Tulis implementasi **Saga Orchestrator** berbasis Go Channel / State Machine untuk alur: `OrderCreated` -> `ReserveInventoryCommand` -> `ProcessPaymentCommand`. Jika langkah `ProcessPaymentCommand` gagal (misal: saldo tidak cukup), Orchestrator harus memicu *Compensating Command* `ReleaseInventoryCommand` secara otomatis dan menandai agregat `Order` menjadi `CANCELLED`.

---

### 14. Challenge

**Skenario Sistem Ticketing Flash Sale Skala Masif**  
Sebuah platform penjualan tiket konser internasional harus menangani perebutan 100.000 kursi dalam waktu kurang dari 60 detik. Beban akses puncak mencapai 800.000 request per detik.

**Target Tugas**:
1. Buat dokumen desain teknis komprehensif yang memadukan arsitektur **Space-Based Architecture (In-Memory Data Grid)** untuk *seat reservation*, **Hexagonal Architecture** untuk inti bisnis per tiket, serta **Choreographed Event Sourcing** untuk ledger pembayaran.
2. Identifikasi potensi *split-brain scenario* pada cluster in-memory state saat partisi jaringan terjadi.
3. Rancang strategi pemulihan sistem jika salah satu node in-memory terbakar (*crash-recovery strategy*) tanpa menyebabkan alokasi tiket ganda (*double allocation/over-selling*).

*Catatan: Kerjakan tanpa menggunakan solusi instan pihak ketiga berbasis managed cloud lock; fokus pada algoritma konsensus dan isolasi state.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pertanyaan Konseptual (Basic)
1. Apa definisi dari *inbound port* dalam konteks Arsitektur Hexagonal?
2. Mengapa manipulasi data langsung pada tabel Read Model dilarang dalam arsitektur CQRS murni?
3. Sebutkan bahaya teknis utama dari fenomena *Dual-Write* dalam sistem terdistribusi!
4. Apa fungsi dari klausa SQL `FOR UPDATE SKIP LOCKED` pada implementasi polling transactional outbox?
5. Mengapa arsitektur Event-Driven secara default menghasilkan model konsistensi *Eventual Consistency* dan bukan *Immediate Consistency*?

#### Bagian B: Pertanyaan Analisis Arsitektur (Intermediate)
1. Dalam skenario apa pola arsitektur *Saga Orchestration* lebih direkomendasikan dibanding *Saga Choreography*?
2. Bagaimana mekanisme *Idempotent Consumer* mencegah eksekusi transaksi finansial ganda saat message broker mengirimkan pesan ulang akibat *timeout acknowledgement*?
3. Mengapa *Two-Phase Commit (2PC)* umumnya dihindari pada sistem komputasi awan (*cloud-native*) skala besar dan digantikan oleh Saga?
4. Apa dampak negatif terhadap throughput sistem jika partisi Kafka untuk domain event hanya diset ke nilai `1` demi menjaga urutan data global?
5. Bagaimana cara arsitektur Hexagonal menjamin bahwa kode logika bisnis domain dapat diuji secara terisolasi tanpa memerlukan koneksi jaringan ke basis data?

#### Bagian C: Skenario Kasus Produksi
1. **Kasus 1: Poison Pill pada Stream Processing**  
   Sebuah pesan corrupt (format JSON cacat) masuk ke antrean utama Kafka. Consumer thread mengalami *panic* terus-menerus dan consumer group macet (*stuck partition offset*). Bagaimana strategi arsitektural untuk mendeteksi dan mengisolasi pesan tersebut secara otomatis tanpa intervensi manual manusia?
2. **Kasus 2: Outbox Table Scalability Bottleneck**  
   Tabel `transactional_outbox` di PostgreSQL mencapai ukuran 200 juta baris karena trafik transaksi yang masif. Polling query `SELECT` menjadi sangat lambat dan membebani IOPS CPU database operasional. Solusi perbaikan arsitektural apa yang harus diterapkan tanpa mengorbankan integritas data ACID?
3. **Kasus 3: CQRS Read-Side Lag Spike**  
   Pada saat kampanye belanja bulanan, jeda sinkronisasi (*replication lag*) antara command side dan read model mencapai 45 detik. Pengguna mengeluh bahwa pesanan yang baru mereka bayar tidak muncul di dashboard riwayat transaksi. Pola arsitektur mitigasi apa yang dapat menjamin UX tetap konsisten (*Read-Your-Own-Writes Consistency*)?

---

### 16. Summary

1. **Unifikasi Paradigma**: Arsitektur enterprise modern yang tangguh mengintegrasikan isolasi domain internal (**Hexagonal Ports & Adapters**), pemisahan beban baca/tulis (**CQRS**), serta komunikasi lintas batas yang decoupling (**Event-Driven Architecture**).
2. **Eliminasi Dual-Write**: Integritas data pada distributed systems hanya dapat dijamin apabila mutasi state agregat lokal dan rekod event terjadi dalam batas transaksi atomik tunggal melalui **Transactional Outbox Pattern**.
3. **Ketahanan Jaringan Asinkron**: Karena pesan broker mengadopsi prinsip pengiriman *at-least-once*, implementasi **Idempotency** dan penanganan **Out-of-Order Messages** pada layer consumer adalah kewajiban mutlak arsitektur, bukan fitur opsional.
4. **Pragmatisme Transaksional Terdistribusi**: Hindari ketergantungan pada ACID terdistribusi atau 2PC yang rapuh. Rancang model konsistensi data bisnis dengan kesadaran penuh terhadap prinsip **Eventual Consistency** menggunakan **Saga Pattern** beserta mekanisme kompensasi otomatis.