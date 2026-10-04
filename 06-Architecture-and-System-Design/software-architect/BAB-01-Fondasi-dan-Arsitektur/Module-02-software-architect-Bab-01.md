# Bab 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengisolasi Core Domain**: Menerapkan arsitektur heksagonal (*Ports & Adapters*) dan *Domain-Driven Design* (DDD) taktis untuk memisahkan logika bisnis dari dependensi infrastruktur dan protokol I/O secara deterministik.
- **Mengeliminasi Masalah Dual-Write**: Mengimplementasikan pola *Transactional Outbox* dan *Idempotent Consumer* untuk menjamin konsistensi data *eventual* lintas batas layanan tanpa *Two-Phase Commit* (2PC).
- **Merancang Fault Tolerance & Resiliency**: Mengonfigurasi strategi mitigasi kegagalan kaskade (*Cascading Failures*) melalui *Circuit Breaker*, *Bulkhead*, dan *Adaptive Concurrency Limiting*.
- **Mengevaluasi Trade-off Konsistensi dan Performa**: Menimbang dampak performa, latensi, throughput, dan kompleksitas operasional antara sinkronisasi data konsistensi kuat (*Strong Consistency*) vs konsistensi akhir (*Eventual Consistency*).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
- **Fondasi Konseptual**: Modul 01 (Karakteristik Arsitektur, CAP Theorem, Fallacies of Distributed Computing, Konsep ACID).
- **Bahasa Pemrograman**: Pemahaman tingkat lanjut tentang Golang (goroutine, channel, interface, pointer, context) atau Java/Kotlin (thread model, memory model, concurrency primitives). Kode acuan pada modul ini menggunakan **Go 1.22+**.
- **Infrastruktur & Tooling**: 
  - PostgreSQL 15+ (Transaction isolation levels, WAL, row-locking).
  - Apache Kafka atau RabbitMQ (Partitioning, consumer groups, offset management).
  - Docker & Docker Compose untuk orkestrasi lingkungan pengujian lokal.

---

### 3. Concept & Internal Architecture

Pembangunan arsitektur kelas *enterprise* menuntut pemisahan mutlak antara *State*, *Business Logic*, dan *Transport Mechanism*. Kesalahan fatal pada sistem monolitik terdistribusi (*distributed monolith*) umumnya berakar dari *tight coupling* antara skema basis data dan representasi domain.

```
       +--------------------------------------------------------------+
       |                     DRIVING / PRIMARY ADAPTERS               |
       |             [gRPC Transport]      [HTTP / REST Handler]       |
       +------------------------------+-------------------------------+
                                      | calls
                                      v
       +--------------------------------------------------------------+
       |               PORTS (Driving / Inbound Interfaces)           |
       |  +--------------------------------------------------------+  |
       |  |                    APPLICATION CORE                    |  |
       |  |                                                        |  |
       |  |   [Command/Query Handlers]     [Application Services]  |  |
       |  |                 |                        |             |  |
       |  |                 v                        v             |  |
       |  |            +-------------------------+                 |  |
       |  |            |     DOMAIN MODEL        |                 |  |
       |  |            | Entities, Value Objects |                 |  |
       |  |            | Aggregates, Domain Logic|                 |  |
       |  |            +-------------------------+                 |  |
       |  |                                                        |  |
       |  |   [Domain Event Dispatcher]                            |  |
       |  +--------------------------------------------------------+  |
       |               PORTS (Driven / Outbound Interfaces)           |
       +------------------------------+-------------------------------+
                                      | implements
                                      v
       +--------------------------------------------------------------+
       |                    DRIVEN / SECONDARY ADAPTERS               |
       | [PostgreSQL Engine]   [Kafka Publisher]   [External Payment] |
       +--------------------------------------------------------------+
```

#### Arsitektur Heksagonal (Ports & Adapters)
Prinsip dasar arsitektur ini adalah *Inversion of Control* (IoC) di batas sistem:
1. **Domain Layer**: Murni berisi entitas, *aggregate roots*, dan aturan bisnis murni. Tidak boleh mengimpor paket dari layer luar (misal: package `database/sql`, `net/http`, atau library pihak ketiga).
2. **Ports**: Berupa interface/kontrak abstrak.
   - *Driving/Inbound Port*: Mendefinisikan apa yang bisa dieksekusi dari luar ke dalam core (misal: `ProcessPaymentUseCase`).
   - *Driven/Outbound Port*: Mendefinisikan kontrak apa yang dibutuhkan oleh core ke infrastruktur (misal: `AccountRepository`, `EventPublisher`).
3. **Adapters**: Implementasi konkret dari port.
   - *Driving Adapter*: Menerjemahkan protokol luar ke pemanggilan domain (misal: Gin/Fiber HTTP handler, gRPC service).
   - *Driven Adapter*: Menerjemahkan kebutuhan domain ke teknologi eksternal (misal: Repository berbasis `pgx`, Kafka Producer).

#### Transactional Outbox Pattern
Ketika state domain berubah dan sistem harus memancarkan event ke *message broker*, memanggil database commit dan mempublikasikan event secara terpisah merupakan anti-pattern yang memicu **Dual-Write Problem**:
- Jika DB commit sukses, tapi broker crash sebelum publish -> Event hilang (*Ghost Write*).
- Jika publish sukses, tapi DB rollback akibat transient error -> Event palsu terdistribusi (*Phantom Event*).

Pola **Transactional Outbox** menyelesaikan persoalan ini melalui pemanfaatan transaksi lokal atomik di database:
1. State entitas dan event outbox ditulis ke dalam transaksi database lokal yang sama (`BEGIN ... COMMIT`).
2. Proses asinkron (*Outbox Processor/Relay*) membaca tabel outbox secara berulang (*polling*) atau mengonsumsi Change Data Capture (CDC via Debezium/Postgres WAL).
3. Record outbox dipublikasikan ke broker. Setelah broker memberikan *acknowledgement* (ACK), status baris outbox diperbarui menjadi `PROCESSED` atau baris dihapus.

---

### 4. Why & What

| Dimensi | Pendekatan Monolit Tradisional / Naif | Arsitektur Enterprise Modern |
| :--- | :--- | :--- |
| **Batas Domain** | Domain logic bercampur dengan query SQL dan validasi HTTP. | Domain steril. Seluruh dependensi eksternal divalidasi via *ports*. |
| **Penyimpanan Event** | Dual-write: DB Write dilanjutkan HTTP/AMQP RPC call. | Transactional Outbox Pattern menjamin *At-Least-Once Delivery*. |
| **Resiliensi Jaringan** | Memanggil dependensi eksternal tanpa batas waktu atau fallback. | Circuit Breaker, Exponential Backoff, dan Timeout Budgeting terisolasi. |
| **Audit Jejak Data** | Log imperatif tak terstruktur, rentan hilang jika server crash. | Immutable Event Log dan *Append-Only Outbox Table*. |

- **Why**: Sistem skala produksi beroperasi di lingkungan terdistribusi di mana kegagalan jaringan, timeout, dan split-brain adalah kepastian (*unreliable network*). Mengandalkan dependensi langsung tanpa isolasi transaksi berisiko merusak konsistensi data finansial/operasional dan memicu *downtime* kaskade.
- **What**: Modul ini mengonstruksi sebuah modul transaksi finansial nir-kegagalan (*zero-loss transaction pipeline*) yang menerapkan DDD Taktis, isolasi I/O murni berbasis *Ports & Adapters*, dan penjaminan emisi pesan via *Transactional Outbox*.

---

### 5. How (Workflow Detail)

Alur eksekusi mutasi domain dengan penjaminan konsistensi atomik:

```
[Client] -> (HTTP POST /transfers)
   |
   v
[Driving Adapter: REST Controller]
   | (1) Parse DTO & Validasi Sintaks
   v
[Inbound Port: Execute Transfer]
   | (2) Context Timeout Injection & Orchestration
   v
[Application Service]
   | (3) BEGIN Transaction (Database Isolation Level: Read Committed / Repeatable Read)
   | (4) Load Aggregate: AccountRepository.FindByID(FromAccountID) [SELECT ... FOR UPDATE]
   | (5) Load Aggregate: AccountRepository.FindByID(ToAccountID)   [SELECT ... FOR UPDATE]
   |
   +---> [Domain Aggregate: Account]
   |        | (6) Execute Debit & Credit logic
   |        | (7) Generate Domain Event: "TransferCompleted"
   |        v
   |<------- Return Mutated Aggregates & Outbox Entity
   |
   | (8) Save Aggregates: AccountRepository.Update(FromAccount, ToAccount)
   | (9) Save Event: OutboxRepository.Create(EventRecord)
   | (10) COMMIT Transaction
   v
[Application Service] -> Return Success Response ke Client
   :
   : (Async Process via separate background routine / Debezium)
   :
[Outbox Relay Worker]
   | (11) Polling / Stream event dari outbox (WHERE status = 'PENDING')
   | (12) Kirim ke Broker (Kafka/RabbitMQ) dengan Delivery Semantic: At-Least-Once
   | (13) Terima ACK dari Broker
   | (14) UPDATE outbox SET status = 'PROCESSED', processed_at = NOW()
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kantor Notaris dan Kurir Bersegel
Bayangkan Anda melakukan transaksi jual beli tanah. 
- **Pendekatan Naif**: Anda menyerahkan sertifikat ke pembeli, lalu berharap pembeli mengirim uang via transfer bank. Jika transfer bank gagal saat sertifikat sudah berpindah tangan, Anda rugi total.
- **Arsitektur Heksagonal & Outbox**: Anda dan pembeli datang ke Notaris (**Transactional Context**). Notaris menandatangani akta pemindahan hak dan sekaligus memasukkan berkas pengumuman negara ke dalam kotak pos keluar di ruang kantornya (**Tabel Outbox**). Semua dicap dalam satu sesi hukum (**DB Commit**). Jika kurir pos pingsan di jalan, berkas tetap aman di kotak keluar notaris. Kurir pengganti akan mengambil berkas tersebut dan mengantarkannya kembali sampai ada tanda terima resmi (**Broker ACK**).

#### Diagram Transaksi dan Relasi Komponen

```
                  APPLICATION BOUNDARY
+------------------------------------------------------------------------+
|                                                                        |
|  [Driving Port]                                                        |
|  +--------------------+                                                |
|  | TransferMoneyUseCase|                                                |
|  +---------+----------+                                                |
|            ^                                                           |
|            | invokes                                                   |
|  +---------+----------+                                                |
|  | TransferService    |                                                |
|  | (App Orchestrator) |                                                |
|  +----+----+----+-----+                                                |
|       |    |    |                                                      |
|       |    |    +------------------------+                             |
|       |    v calls                        | emits                       |
|       |  +---------------------+          v                            |
|       |  | Account Aggregate   |  +---------------+                    |
|       |  | [Debit / Credit]    |  | Domain Event  |                    |
|       |  +---------------------+  +-------+-------+                    |
|       |                                   |                            |
|       v persists via                      v persists via               |
|  [Driven Port: Repo]                 [Driven Port: Outbox]             |
|  +---------------------+             +--------------------+            |
|  | AccountRepository   |             | OutboxRepository   |            |
|  +----------+----------+             +----------+---------+            |
|             |                                   |                      |
+-------------|-----------------------------------|----------------------+
              |                                   |
              +-----------------+                 |
                                |                 |
                       Same DB Transaction (BEGIN | COMMIT)
                                v                 v
                      +-----------------------------------+
                      |       PostgreSQL Database         |
                      |  +-------------+ +-------------+  |
                      |  |  accounts   | |   outbox    |  |
                      |  +-------------+ +------+------+  |
                      +-------------------------|---------+
                                                |
                                                | Poll / WAL stream
                                                v
                                     +--------------------+
                                     | Outbox Worker      |
                                     +----------+---------+
                                                | Publish with Retry
                                                v
                                     +--------------------+
                                     | Message Broker     |
                                     | (Kafka/RabbitMQ)   |
                                     +--------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Modul & Struktur Direktori
Inisialisasi modul Go dan pasang pustaka eksternal yang dibutuhkan:
```bash
go mod init enterprise-arch
go get github.com/google/uuid
go get github.com/jackc/pgx/v5
```

```
enterprise-arch/
├── domain/
│   ├── account.go
│   └── events.go
├── ports/
│   ├── repositories.go
│   └── services.go
└── adapters/
    ├── postgres/
    │   ├── account_repository.go
    │   └── outbox_repository.go
    └── worker/
        └── outbox_worker.go
```

#### B. Domain Layer: Aggregate & Domain Events (`domain/account.go`)
Domain logic harus murni dari tag infrastruktur dan dependensi pihak ketiga (hanya gunakan pustaka standar atau utilitas penunjang seperti UUID primitif).

```go
package domain

import (
	"errors"
	"time"

	"github.com/google/uuid"
)

var (
	ErrInsufficientFunds = errors.New("insufficient funds for transaction")
	ErrInvalidAmount     = errors.New("amount must be greater than zero")
	ErrSameAccount       = errors.New("source and destination account cannot be the same")
)

type Money int64 // Representasi dalam unit sen (cents) untuk mencegah floating-point rounding issue

type Account struct {
	ID        uuid.UUID
	Balance   Money
	UpdatedAt time.Time
}

func NewAccount(id uuid.UUID, initialBalance Money) (*Account, error) {
	if initialBalance < 0 {
		return nil, errors.New("initial balance cannot be negative")
	}
	return &Account{
		ID:        id,
		Balance:   initialBalance,
		UpdatedAt: time.Now().UTC(),
	}, nil
}

func (a *Account) Debit(amount Money) error {
	if amount <= 0 {
		return ErrInvalidAmount
	}
	if a.Balance < amount {
		return ErrInsufficientFunds
	}
	a.Balance -= amount
	a.UpdatedAt = time.Now().UTC()
	return nil
}

func (a *Account) Credit(amount Money) error {
	if amount <= 0 {
		return ErrInvalidAmount
	}
	a.Balance += amount
	a.UpdatedAt = time.Now().UTC()
	return nil
}
```

Definisi Event dan Outbox Record (`domain/events.go`):

```go
package domain

import (
	"time"

	"github.com/google/uuid"
)

type TransferCompletedEvent struct {
	EventID         uuid.UUID `json:"event_id"`
	SourceAccount   uuid.UUID `json:"source_account"`
	TargetAccount   uuid.UUID `json:"target_account"`
	Amount          Money     `json:"amount"`
	Timestamp       time.Time `json:"timestamp"`
}

type OutboxStatus string

const (
	OutboxStatusPending   OutboxStatus = "PENDING"
	OutboxStatusProcessed OutboxStatus = "PROCESSED"
	OutboxStatusFailed    OutboxStatus = "FAILED"
)

type OutboxRecord struct {
	ID           uuid.UUID
	AggregateType string
	AggregateID   string
	EventType     string
	Payload       []byte
	Status        OutboxStatus
	CreatedAt     time.Time
	ProcessedAt   *time.Time
}
```

#### C. Ports Layer: Definisi Abstraksi Sistem (`ports/repositories.go`)

```go
package ports

import (
	"context"
	"enterprise-arch/domain"
	"github.com/google/uuid"
)

type AccountRepository interface {
	GetForUpdate(ctx context.Context, tx interface{}, id uuid.UUID) (*domain.Account, error)
	Update(ctx context.Context, tx interface{}, account *domain.Account) error
}

type OutboxRepository interface {
	Save(ctx context.Context, tx interface{}, record *domain.OutboxRecord) error
	FetchPending(ctx context.Context, batchSize int) ([]*domain.OutboxRecord, error)
	MarkAsProcessed(ctx context.Context, id uuid.UUID) error
}

type UnitOfWork interface {
	ExecuteTransactional(ctx context.Context, fn func(tx interface{}) error) error
}

type MessagePublisher interface {
	Publish(ctx context.Context, topic string, key string, payload []byte) error
}
```

Use Case Interface (`ports/services.go`):

```go
package ports

import (
	"context"
	"enterprise-arch/domain"
	"github.com/google/uuid"
)

type TransferMoneyUseCase interface {
	Execute(ctx context.Context, fromID, toID uuid.UUID, amount domain.Money) error
}
```

#### D. Application Core: Service Orchestrator
Implementasi use case yang menjamin transaksi atomik antara domain mutation dan outbox logging.

```go
package app

import (
	"context"
	"encoding/json"
	"time"

	"enterprise-arch/domain"
	"enterprise-arch/ports"
	"github.com/google/uuid"
)

type TransferService struct {
	uow         ports.UnitOfWork
	accountRepo ports.AccountRepository
	outboxRepo  ports.OutboxRepository
}

func NewTransferService(
	uow ports.UnitOfWork,
	accountRepo ports.AccountRepository,
	outboxRepo ports.OutboxRepository,
) *TransferService {
	return &TransferService{
		uow:         uow,
		accountRepo: accountRepo,
		outboxRepo:  outboxRepo,
	}
}

func (s *TransferService) Execute(ctx context.Context, fromID, toID uuid.UUID, amount domain.Money) error {
	if fromID == toID {
		return domain.ErrSameAccount
	}

	return s.uow.ExecuteTransactional(ctx, func(tx interface{}) error {
		// 1. Acquire pessimistic locks in deterministic order to prevent deadlocks
		firstID, secondID := fromID, toID
		if fromID.String() > toID.String() {
			firstID, secondID = toID, fromID
		}

		acc1, err := s.accountRepo.GetForUpdate(ctx, tx, firstID)
		if err != nil {
			return err
		}
		acc2, err := s.accountRepo.GetForUpdate(ctx, tx, secondID)
		if err != nil {
			return err
		}

		var fromAcc, toAcc *domain.Account
		if acc1.ID == fromID {
			fromAcc, toAcc = acc1, acc2
		} else {
			fromAcc, toAcc = acc2, acc1
		}

		// 2. Mutate domain state
		if err := fromAcc.Debit(amount); err != nil {
			return err
		}
		if err := toAcc.Credit(amount); err != nil {
			return err
		}

		// 3. Persist state changes
		if err := s.accountRepo.Update(ctx, tx, fromAcc); err != nil {
			return err
		}
		if err := s.accountRepo.Update(ctx, tx, toAcc); err != nil {
			return err
		}

		// 4. Construct and serialize domain event
		event := domain.TransferCompletedEvent{
			EventID:       uuid.New(),
			SourceAccount: fromAcc.ID,
			TargetAccount: toAcc.ID,
			Amount:        amount,
			Timestamp:     time.Now().UTC(),
		}
		payload, err := json.Marshal(event)
		if err != nil {
			return err
		}

		// 5. Append to Outbox within the SAME transaction
		outboxEntry := &domain.OutboxRecord{
			ID:            uuid.New(),
			AggregateType: "Account",
			AggregateID:   fromAcc.ID.String(),
			EventType:     "TransferCompleted",
			Payload:       payload,
			Status:        domain.OutboxStatusPending,
			CreatedAt:     time.Now().UTC(),
		}

		return s.outboxRepo.Save(ctx, tx, outboxEntry)
	})
}
```

#### E. Driven Adapters: Postgres Repositories (`adapters/postgres/`)
Implementasi adapter penyimpanan menggunakan native SQL queries pada PostgreSQL.

```go
package postgres

import (
	"context"
	"database/sql"
	"enterprise-arch/domain"
	"fmt"

	"github.com/google/uuid"
)

type PgxAccountRepo struct{}

func NewPgxAccountRepo() *PgxAccountRepo {
	return &PgxAccountRepo{}
}

func (r *PgxAccountRepo) GetForUpdate(ctx context.Context, tx interface{}, id uuid.UUID) (*domain.Account, error) {
	dbtx, ok := tx.(*sql.Tx)
	if !ok {
		return nil, fmt.Errorf("invalid transaction context")
	}

	query := `SELECT id, balance, updated_at FROM accounts WHERE id = $1 FOR UPDATE`
	row := dbtx.QueryRowContext(ctx, query, id)

	var acc domain.Account
	var balance int64
	if err := row.Scan(&acc.ID, &balance, &acc.UpdatedAt); err != nil {
		return nil, err
	}
	acc.Balance = domain.Money(balance)
	return &acc, nil
}

func (r *PgxAccountRepo) Update(ctx context.Context, tx interface{}, account *domain.Account) error {
	dbtx, ok := tx.(*sql.Tx)
	if !ok {
		return fmt.Errorf("invalid transaction context")
	}

	query := `UPDATE accounts SET balance = $1, updated_at = $2 WHERE id = $3`
	_, err := dbtx.ExecContext(ctx, query, int64(account.Balance), account.UpdatedAt, account.ID)
	return err
}

type PgxOutboxRepo struct {
	db *sql.DB
}

func NewPgxOutboxRepo(db *sql.DB) *PgxOutboxRepo {
	return &PgxOutboxRepo{db: db}
}

func (r *PgxOutboxRepo) Save(ctx context.Context, tx interface{}, record *domain.OutboxRecord) error {
	dbtx, ok := tx.(*sql.Tx)
	if !ok {
		return fmt.Errorf("invalid transaction context")
	}

	query := `
		INSERT INTO outbox_events (id, aggregate_type, aggregate_id, event_type, payload, status, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`
	_, err := dbtx.ExecContext(ctx, query,
		record.ID,
		record.AggregateType,
		record.AggregateID,
		record.EventType,
		record.Payload,
		record.Status,
		record.CreatedAt,
	)
	return err
}

func (r *PgxOutboxRepo) FetchPending(ctx context.Context, batchSize int) ([]*domain.OutboxRecord, error) {
	// Skip locked rows to allow multiple outbox relay instances to scale concurrently
	query := `
		SELECT id, aggregate_type, aggregate_id, event_type, payload, status, created_at
		FROM outbox_events
		WHERE status = 'PENDING'
		ORDER BY created_at ASC
		LIMIT $1
		FOR UPDATE SKIP LOCKED
	`
	rows, err := r.db.QueryContext(ctx, query, batchSize)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var records []*domain.OutboxRecord
	for rows.Next() {
		var rec domain.OutboxRecord
		if err := rows.Scan(
			&rec.ID,
			&rec.AggregateType,
			&rec.AggregateID,
			&rec.EventType,
			&rec.Payload,
			&rec.Status,
			&rec.CreatedAt,
		); err != nil {
			return nil, err
		}
		records = append(records, &rec)
	}
	return records, nil
}

func (r *PgxOutboxRepo) MarkAsProcessed(ctx context.Context, id uuid.UUID) error {
	query := `UPDATE outbox_events SET status = 'PROCESSED', processed_at = NOW() WHERE id = $1`
	_, err := r.db.ExecContext(ctx, query, id)
	return err
}
```

#### F. Outbox Polling Relay Worker (`adapters/worker/outbox_worker.go`)
Daemon latar belakang yang mengalirkan event ke broker.

```go
package worker

import (
	"context"
	"enterprise-arch/ports"
	"log"
	"time"
)

type OutboxRelayWorker struct {
	outboxRepo ports.OutboxRepository
	publisher  ports.MessagePublisher
	interval   time.Duration
	batchSize  int
}

func NewOutboxRelayWorker(
	repo ports.OutboxRepository,
	pub ports.MessagePublisher,
	interval time.Duration,
	batchSize int,
) *OutboxRelayWorker {
	return &OutboxRelayWorker{
		outboxRepo: repo,
		publisher:  pub,
		interval:   interval,
		batchSize:  batchSize,
	}
}

func (w *OutboxRelayWorker) Start(ctx context.Context) {
	ticker := time.NewTicker(w.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("Stopping outbox relay worker...")
			return
		case <-ticker.C:
			w.processBatch(ctx)
		}
	}
}

func (w *OutboxRelayWorker) processBatch(ctx context.Context) {
	events, err := w.outboxRepo.FetchPending(ctx, w.batchSize)
	if err != nil {
		log.Printf("Error fetching outbox records: %v\n", err)
		return
	}

	for _, event := range events {
		// Topic diatur berdasarkan domain entity/event type
		topic := "domain-events." + event.AggregateType

		err := w.publisher.Publish(ctx, topic, event.AggregateID, event.Payload)
		if err != nil {
			log.Printf("Failed to publish event ID %s: %v. Retrying next cycle.\n", event.ID, err)
			continue
		}

		if err := w.outboxRepo.MarkAsProcessed(ctx, event.ID); err != nil {
			log.Printf("Failed to mark event %s as PROCESSED: %v\n", event.ID, err)
		}
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Arsitektur Sistem Finansial Pembayaran Instan (Tier-1 FinTech) memproses **45.000 transaksi transfer per detik (TPS)** pada jam sibuk, dengan SLA ketersediaan 99,999% (*five-nines*) dan *zero financial discrepancy allowance*.

#### Titik Masalah (*Failure Point*)
Pada arsitektur sebelumnya:
1. Layanan API mengeksekusi transfer di PostgreSQL, lalu memanggil REST API Notification Engine dan mem-publish event ke Kafka.
2. Ketika Kafka mengalami *Leader Re-election transient spike* selama 1,8 detik:
   - 81.000 transaksi mutasi rekening berhasil di-*commit* di basis data.
   - Namun, Kafka producer mengalami koneksi putus (*network timeout*).
   - Akibatnya, instruksi *settlement* pihak ketiga hilang, saldo pengguna berkurang tanpa pengiriman dana, dan saldo sistem *out-of-balance* sebesar Rp 14,2 Miliar. Audit investigasi memakan waktu 48 jam kerja teknis manual.

#### Solusi Transformasi Arsitektur
1. **Penerapan Transactional Outbox + Debezium CDC**:
   - Menghapus pemanggilan Kafka langsung dari *critical execution path* API transfer.
   - Menulis status ledger dan outbox event ke partisi PostgreSQL yang sama.
   - Mengintegrasikan Debezium untuk membaca *Write-Ahead Log* (WAL) PostgreSQL via *Logical Decoding Output plugin* (`pgoutput`).
   - Latensi p99 HTTP API turun dari **320ms menjadi 42ms** karena penghapusan sinkronisasi I/O network Kafka dari request-response cycle.
2. **Deterministic Pessimistic Locking**:
   - Pengurutan kunci akun berdasarkan representasi biner UUID (`string compare` atau lexicographical sorting) sebelum perintah SQL `SELECT ... FOR UPDATE` dieksekusi. Ini mengeliminasi fenomena **Deadlock 40P01** di PostgreSQL hingga 0%.

---

### 9. Trade-offs

| Strategi / Pilihan | Keuntungan Utama | Kerugian / Titik Kritis | Dampak Latensi & Throughput | Biaya Infrastruktur |
| :--- | :--- | :--- | :--- | :--- |
| **Transactional Outbox (Polling SQL via `FOR UPDATE SKIP LOCKED`)** | Implementasi sederhana, tidak membutuhkan software platform tambahan selain DB SQL. | Beban IOPS konstan pada database SQL utama akibat polling periodik. | Latensi publish event: 500ms - 2s. Throughput database inti tereduksi ~15%. | Rendah (tidak butuh infrastruktur baru). |
| **Transactional Outbox via CDC Engine (Debezium + Kafka Connect)** | Emisi event sub-detik tanpa membebani IOPS database query engine (membaca file WAL). | Mengelola cluster Kafka Connect, Zookeeper/KRaft, risiko WAL disk bloat jika CDC macet. | Latensi publish: < 50ms. Throughput database inti tidak terganggu. | Tinggi (biaya cluster Kafka Connect + disk space WAL). |
| **Two-Phase Commit (2PC / XA Transactions)** | Konsistensi kuat secara langsung (*Immediate Consistency*) lintas sistem database. | Mengunci resource lintas jaringan (*blocking protocol*), rentan SPOF jika coordinator crash. | Latensi sangat tinggi (p99 > 1500ms). Skalabilitas horizontal sistem anjlok drastis. | Sangat Tinggi (kebutuhan lisensi coordinator dan resource overhead). |
| **Direct Async Broker Publish (Naif / Dual-Write)** | Arsitektur sangat sederhana, latensi endpoint sangat rendah secara lokal. | Integritas data tidak terjamin; risiko kehilangan pesan (*data loss*) jika terjadi kegagalan jaringan. | Latensi rendah, throughput semu tinggi. | Rendah di awal, namun biaya rekonsiliasi insiden sangat mahal. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Deadlock pada Transfer Dua Arah (*Cross-Transfer Locking Deadlock*)
- **Gejala**: Database PostgreSQL melempar pesan error: `ERROR: deadlock detected (SQLSTATE 40P01)`.
- **Akar Masalah**: Sesi A mentransfer dari Akun 1 ke Akun 2 (`Lock(1)` lalu `Lock(2)`). Bersamaan dengan itu, Sesi B mentransfer dari Akun 2 ke Akun 1 (`Lock(2)` lalu `Lock(1)`). Kedua transaksi saling menunggu pelepasan kunci satu sama lain.
- **Solusi**: Normalisasi urutan akuisisi kunci aggregate ID.
  ```go
  // Terapkan selalu pengurutan ID sebelum mengakuisisi resource lock
  if accountIDA.String() > accountIDB.String() {
      lock(accountIDB)
      lock(accountIDA)
  } else {
      lock(accountIDA)
      lock(accountIDB)
  }
  ```

#### 2. Outbox Table Bloat & Degradasi Disk
- **Gejala**: Ukuran tabel `outbox_events` membengkak hingga puluhan gigabyte, menurunkan performa query lain dan menghabiskan ruang disk.
- **Akar Masalah**: Baris event yang sudah berstatus `PROCESSED` tidak pernah dibersihkan. Autovacuum PostgreSQL bekerja lambat pada tabel mutasi tinggi.
- **Solusi**:
  - Terapkan skema partisi tabel (*Table Partitioning*) berdasarkan waktu (harian/mingguan).
  - Buat cron job untuk melakukan `DROP TABLE` pada partisi lama yang sudah terproses.
  - Alternatif: Hapus baris secara langsung (`DELETE`) segera setelah ACK broker didapatkan, bukan sekadar menandai statusnya `PROCESSED`.

#### 3. Poison Pill Message Loop pada Consumer
- **Gejala**: Consumer memproses pesan yang rusak, panik/crash, restart, lalu mengambil pesan yang sama berulang kali (*infinite crash loop*).
- **Solusi**: Terapkan header counter retry (`x-retry-count`). Jika mencapai batas maksimal (misal: 3 kali percobaan gagal), alihkan pesan ke **Dead Letter Queue (DLQ)** dan kirim alert ke tim SRE/Operations.

---

### 11. Best Practices (Production Checklist)

#### Domain & Architecture
- [ ] Core Domain tidak mengimpor library HTTP handler, ORM, basis data, atau broker SDK.
- [ ] Penggunaan tipe data keuangan tidak boleh menggunakan float64 atau float32 (gunakan Integer mikro/sen atau `shopspring/decimal`).
- [ ] Seluruh dependensi infrastruktur dihubungkan ke application layer via *Dependency Injection* melalui Port interface.

#### Data Integrity & Reliability
- [ ] Database Isolation Level diverifikasi (minimal *Read Committed* dengan *Pessimistic Locking* atau *Repeatable Read*).
- [ ] Pola Dual-Write dieliminasi sepenuhnya di seluruh mutasi data lintas batas sistem menggunakan Outbox Pattern atau Saga Orchestration.
- [ ] Consumer pesan wajib dirancang **Idempotent** (menggunakan ID deduplikasi unik yang disimpan pada database consumer).

#### Operasional & Monitoring
- [ ] Alerting metrik kustom diaktifkan untuk: *Outbox Table Lag* (jumlah baris pending > ambang batas tertentu selama > 5 menit).
- [ ] Set `context.WithTimeout` pada seluruh Driving Adapters untuk mencegah goroutine leakage saat database mengalami thread exhaustion.
- [ ] Pasang distributed tracing OpenTelemetry span pada batasan: HTTP Transport -> Domain Execution -> Outbox Persist -> Worker Publish.

---

### 12. Hands-on Practice

Ikuti langkah-langkah praktikum berikut untuk menguji sistem di lingkungan lokal. Simpan semua file di direktori `hands-on/m02/`.

#### Langkah 1: Persiapan Environment
Buat file `docker-compose.yml` di dalam direktori `hands-on/m02/`:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: secretpassword
      POSTGRES_DB: enterprise_db
    ports:
      - "5432:5432"
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

#### Langkah 2: Inisialisasi Skema Database
Buat file `init.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE accounts (
    id UUID PRIMARY KEY,
    balance BIGINT NOT NULL CHECK (balance >= 0),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE outbox_events (
    id UUID PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE NULL
);

CREATE INDEX idx_outbox_pending ON outbox_events (created_at) WHERE status = 'PENDING';

-- Insert dummy data
INSERT INTO accounts (id, balance) VALUES 
('a0000000-0000-0000-0000-000000000001', 1000000), -- Rp 10.000,00
('a0000000-0000-0000-0000-000000000002', 500000);  -- Rp 5.000,00
```

#### Langkah 3: Menjalankan Infrastruktur dan Pengujian Mutasi
Jalankan perintah berikut pada terminal:

```bash
cd hands-on/m02/
docker compose up -d

# Verifikasi koneksi dan data
docker compose exec postgres psql -U appuser -d enterprise_db -c "SELECT * FROM accounts;"
```

#### Langkah 4: Implementasi Runner Test Atomisitas
Buat file `main.go` yang memvalidasi transfer dana: jika transfer berhasil, baris mutasi rekening dan event outbox harus terisi secara atomik di dalam database.

```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"time"

	"enterprise-arch/adapters/postgres"
	appService "enterprise-arch/app"
	"enterprise-arch/domain"

	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

type PgUnitOfWork struct {
	db *sql.DB
}

func (u *PgUnitOfWork) ExecuteTransactional(ctx context.Context, fn func(tx interface{}) error) error {
	tx, err := u.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return err
	}

	if err := fn(tx); err != nil {
		if rbErr := tx.Rollback(); rbErr != nil {
			return fmt.Errorf("err: %v, rbErr: %v", err, rbErr)
		}
		return err
	}

	return tx.Commit()
}

func main() {
	dsn := "postgres://appuser:secretpassword@localhost:5432/enterprise_db?sslmode=disable"
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		log.Fatalf("Database connection error: %v", err)
	}
	defer db.Close()

	uow := &PgUnitOfWork{db: db}
	accRepo := postgres.NewPgxAccountRepo()
	outboxRepo := postgres.NewPgxOutboxRepo(db)

	service := appService.NewTransferService(uow, accRepo, outboxRepo)

	fromID := uuid.MustParse("a0000000-0000-0000-0000-000000000001")
	toID := uuid.MustParse("a0000000-0000-0000-0000-000000000002")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	transferAmount := domain.Money(250000) // Rp 2.500,00
	log.Println("Executing atomic transfer...")
	if err := service.Execute(ctx, fromID, toID, transferAmount); err != nil {
		log.Fatalf("Transfer failed: %v", err)
	}

	log.Println("Transfer executed successfully! Verifying outbox events in database...")
}
```

Jalankan pengujian eksekusi:
```bash
go run main.go
docker compose exec postgres psql -U appuser -d enterprise_db -c "SELECT id, aggregate_id, event_type, status FROM outbox_events;"
```

---

### 13. Exercise

#### Latihan 1 (Tingkat: Easy)
Perluas entitas `domain/account.go` dengan menambahkan validasi limit transaksi: sebuah akun tidak diperbolehkan melakukan transfer tunggal melebihi Rp 10.000.000 (1.000.000.000 sen). Buat *unit test* terisolasi tanpa dependensi database untuk memvalidasi skenario batas ini (*edge case*).

#### Latihan 2 (Tingkat: Medium)
Modifikasi implementasi `adapters/postgres/outbox_repository.go` agar mendukung mekanisme **Dead-Letter State**. Jika suatu record outbox gagal dipublikasikan sebanyak 5 kali, statusnya berubah menjadi `FAILED` dan catat riwayat kegagalan di kolom `last_error_message` (TEXT). Modifikasi skema SQL tabel sesuai kebutuhan.

#### Latihan 3 (Tingkat: Hard)
Kembangkan sistem deduplikasi pesan di sisi *Consumer* (*Idempotent Consumer Pattern*). 
- Buat sebuah database consumer terpisah yang menerima event `TransferCompleted`.
- Gunakan tabel `processed_messages (message_id UUID PRIMARY KEY, processed_at TIMESTAMP)`.
- Bungkus pemrosesan payload consumer dan penyisipan data ke tabel `processed_messages` dalam satu transaksi atomik. Uji coba dengan mengirim payload yang sama sebanyak 3 kali secara paralel (uji ketahanan *race condition*).

---

### 14. Challenge

**Skenario Sistem Finansial Lintas Wilayah (*Multi-Region Disaster Recovery*)**:
Anda diminta merancang arsitektur sistem inti perbankan (*Core Banking Transaction Engine*) yang tersebar di dua region cloud aktif (*Active-Active Multi-Region Deployment*): `Region-A (Jakarta)` dan `Region-B (Singapura)`. 

**Batasan Masalah**:
1. Kedua region menerima request mutasi rekening untuk akun nasabah yang sama secara paralel.
2. Latensi inter-region (antar-region) rata-rata adalah 65ms, namun sewaktu-waktu dapat terjadi degradasi koneksi (*network split-brain* / isolasi partisi total selama beberapa jam).
3. Saldo nasabah tidak boleh menjadi negatif akibat *race condition* penarikan ganda di kedua region (*no double spending*).
4. Kepatuhan regulasi perbankan melarang penggunaan 2PC (*Two-Phase Commit*) lintas region karena faktor risiko *blocking latency* yang melanggar SLA 99,999%.

**Tugas Arsitektur**:
Rancang dokumen arsitektur komprehensif yang mencakup:
- Strategi penentuan kepemilikan data (*Single Source of Truth / Sharded Region Affinity*).
- Pola perutean trafik transaksi (*Geographic Routing & Dynamic Ingress*).
- Penanganan konflik rekonsiliasi data jika partisi jaringan pulih (*Conflict Resolution Mechanics* / CRDTs vs Orchestrated Ledger Reconciliation).
- Desain arsitektur dalam bentuk diagram ASCII detail beserta penanganan skenario kegagalannya.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (5 Soal)
1. **Apa tujuan utama penerapan Arsitektur Heksagonal (Ports & Adapters)?**
   - *Jawaban*: Mengisolasi domain logic inti dari detail infrastruktur, protokol I/O luar, dan framework, sehingga logika bisnis bersifat deterministik, mudah diuji, dan independen terhadap perubahan teknologi eksternal.
2. **Mengapa tipe data desimal pecahan seperti `float64` dilarang digunakan untuk merepresentasikan nilai saldo moneter?**
   - *Jawaban*: Karena representasi binary floating-point IEEE-754 tidak dapat merepresentasikan pecahan desimal tertentu secara presisi, yang menyebabkan akumulasi kesalahan pembulatan (*rounding errors*) pada operasi aritmatika berkelanjutan.
3. **Apa definisi dari fenomena "Dual-Write Problem" dalam arsitektur sistem terdistribusi?**
   - *Jawaban*: Kondisi ketika aplikasi harus menulis state ke dua sistem penyimpanan independen tanpa koordinasi transaksi terdistribusi, di mana kegagalan parsial pada salah satu sistem menyebabkan inkonsistensi state global.
4. **Pada pola Transactional Outbox, komponen apa yang bertanggung jawab memindahkan data dari tabel outbox ke message broker?**
   - *Jawaban*: Outbox Relay / Message Relayer (bisa berupa *polling worker background thread* atau CDC connector seperti Debezium yang membaca WAL basis data).
5. **Apa fungsi klausa SQL `FOR UPDATE` saat memuat data entitas di dalam sebuah transaksi?**
   - *Jawaban*: Mengunci baris data yang dipilih dengan *pessimistic exclusive lock*, mencegah transaksi lain membaca dengan kunci yang sama, memodifikasi, atau menghapus baris tersebut sampai transaksi saat ini selesai (`COMMIT`/`ROLLBACK`).

#### Bagian B: Intermediate (5 Soal)
1. **Mengapa penambahan klausa `SKIP LOCKED` sangat penting pada kueri pemrosesan tabel Outbox oleh multi-worker instance?**
   - *Jawaban*: Klausa `SKIP LOCKED` memungkinkan beberapa worker instance membaca dan mengunci batch baris secara konkuren tanpa terblokir oleh baris yang sedang diproses oleh worker lain, sehingga mencegah *lock contention* dan memungkinkan skalabilitas horizontal.
2. **Jelaskan perbedaan mendasar antara Driving/Inbound Port dan Driven/Outbound Port!**
   - *Jawaban*: *Driving Port* adalah interface yang diekspos oleh Application Core untuk dipanggil oleh Adapter luar (misal: Controller memanggil UseCase). Sedangkan *Driven Port* adalah interface yang didefinisikan oleh Core namun diimplementasikan oleh Adapter infrastruktur luar (misal: Core memanggil Repository atau Broker Adapter).
3. **Bagaimana cara mencegah deadlock database saat dua transaksi konkuren memutasi sepasang akun yang sama secara berlawanan arah?**
   - *Jawaban*: Mengurutkan proses penguncian ID baris secara deterministik (misal: selalu mengunci ID yang lebih kecil terlebih dahulu sebelum ID yang lebih besar) terlepas dari arah alur transaksi bisnis.
4. **Apa implikasi jaminan pengiriman (*delivery semantics*) dari pola Transactional Outbox terhadap perancangan Consumer?**
   - *Jawaban*: Jaminan pengiriman bersifat *At-Least-Once Delivery* (ada potensi pengiriman event duplikat jika kegagalan terjadi pasca-publish sebelum update status outbox), sehingga Consumer wajib dirancang bersifat *Idempotent*.
5. **Apa kelemahan utama metode Outbox Polling dibandingkan metode CDC (Change Data Capture) via database Write-Ahead Log?**
   - *Jawaban*: Outbox Polling membebani resource database utama melalui query SQL periodik (IOPS, CPU, lock index) dan memiliki latency gap sebesar interval polling. CDC membaca langsung binlog/WAL di disk tanpa mengganggu query engine data.

#### Bagian C: Skenario Kasus Produksi (3 Soal)

1. **Skenario Kasus 1**:
   *Deskripsi Masalah*: Sebuah aplikasi e-commerce mencatat transaksi ke database PostgreSQL dan memancarkan event order via Transactional Outbox. Saat lonjakan diskon Flash Sale, tabel `outbox_events` mengalami backlog antrean hingga 2.000.000 baris. Worker polling gagal mengejar ketertinggalan dan memperlambat sistem database secara keseluruhan.
   *Pertanyaan Analisis*: Mengapa performa database ikut melambat drastis, dan arsitektur apa yang harus segera diubah untuk mengatasi masalah ini tanpa merusak data?
   *Jawaban Komprehensif*: 
   - *Penyebab*: Query polling berulang pada tabel berukuran jutaan baris menghasilkan fragmentasi indeks dan *table scan* yang berat. Autovacuum PostgreSQL bekerja sangat keras menangani ribuan update status baris per detik, mengonsumsi IOPS disk secara ekstrem.
   - *Solusi Perbaikan*: 
     1. Ubah strategi Outbox Polling menjadi streaming berbasis **CDC (Change Data Capture)** menggunakan Debezium/Kafka Connect yang memanfaatkan replication slot PostgreSQL (`pgoutput`). Ini memangkas konsumsi IOPS hingga 80%.
     2. Terapkan partisi tabel outbox harian (*Declarative Partitioning*) atau hapus baris yang telah terkirim (`DELETE` daripada `UPDATE status = 'PROCESSED'`) untuk meminimalkan ukuran tabel aktif (*vacuum overhead mitigation*).

2. **Skenario Kasus 2**:
   *Deskripsi Masalah*: Arsitektur microservices pembayaran Anda menggunakan Kafka. Terjadi insiden jaringan di mana consumer service inventori memproses event `PaymentReceived` dua kali untuk Order ID `#INV-9901`. Akibatnya, stok barang terpotong dua kali dan kuota inventori minus.
   *Pertanyaan Analisis*: Bagaimana cara merancang mekanisme Idempotency Guard di layer basis data consumer untuk mengeliminasi pemrosesan ganda tersebut?
   *Jawaban Komprehensif*:
   - Terapkan tabel kontrol idempotensi pada basis data Consumer (misal: `processed_events`) dengan kolom `event_id VARCHAR(64) PRIMARY KEY` atau `unique_transaction_ref`.
   - Jalankan pemotongan stok inventori dan pencatatan event ID di dalam satu blok transaksi database lokal:
     ```sql
     BEGIN;
     INSERT INTO processed_events (event_id, processed_at) VALUES ('event-uuid-from-kafka', NOW());
     -- Jika duplicate key error (SQLSTATE 23505), batalkan transaksi (Rollback) & kirim ACK ke Kafka
     UPDATE inventory SET stock = stock - 1 WHERE item_id = 'ITM-01' AND stock >= 1;
     COMMIT;
     ```
   - Dengan pendekatan ini, database menolak eksekusi ganda secara konsisten di tingkat ACID engine lokal.

3. **Skenario Kasus 3**:
   *Deskripsi Masalah*: Auditor finansial menemukan perbedaan pembukuan saldo sebesar Rp 50.000.000 selama 1 bulan pada sistem akuntansi microservices. Setelah ditelusuri, sistem menggunakan pola *microservices async choreography* di mana service ledger menulis mutasi berdasarkan konsumsi event Kafka tanpa transaksi ACID terpadu di tingkat gateway.
   *Pertanyaan Analisis*: Pola arsitektur apa yang harus diimplementasikan untuk menjamin auditabilitas finansial mutlak (*absolute auditability*) dan bagaimana struktur log tersebut disimpan?
   *Jawaban Komprehensif*:
   - Terapkan arsitektur **Event Sourcing** dan **Double-Entry Bookkeeping Ledger Engine**.
   - Dalam sistem akuntansi keuangan, saldo tidak boleh disimpan hanya sebagai angka mutasi langsung (*mutable balance*). Saldo adalah hasil agregasi (proyeksi) dari baris jurnal *Append-Only* yang tidak dapat diubah (*immutable*).
   - Setiap transaksi keuangan harus mencatat sepasang entri jurnal: satu akun didebit dan satu akun dikredit dengan nilai yang seimbang (*Balance Rule*: $\sum \text{Debit} - \sum \text{Kredit} = 0$).
   - Jika terjadi pembatalan transaksi, sistem dilarang menghapus atau mengubah baris transaksi lama, melainkan harus menerbitkan transaksi pembalik (*Reversal / Compensating Transaction*).

---

### 16. Summary

1. **Pemisahan Kendali Absolut**: Arsitektur Heksagonal (*Ports & Adapters*) menjamin bahwa aturan bisnis inti (*Core Domain*) terlindungi secara murni dari perubahan framework, protokol komunikasi, dan vendor basis data.
2. **Eliminasi Inkonsistensi Terdistribusi**: Mengirim event ke sistem eksternal secara langsung di tengah eksekusi basis data memicu *Dual-Write Problem*. Pola *Transactional Outbox* menjamin reliabilitas pengiriman data (*At-Least-Once Delivery*) dengan mengikat mutasi domain dan pencatatan event ke dalam satu transaksi lokal.
3. **Pertahanan terhadap Deadlock & Concurrency**: Pemanfaatan *pessimistic lock* pada transaksi konkuren tinggi wajib dikombinasikan dengan pengurutan penguncian ID yang deterministik guna menghindari kondisi kebuntuan thread database (*deadlock detection cascade*).
4. **Idempotensi adalah Mandat**: Di lingkungan jaringan terdistribusi di mana pengiriman ulang pesan (*retries*) adalah keniscayaan, *Consumer* wajib memiliki filter idempotensi berbasis kunci unik untuk mencegah duplikasi eksekusi state.