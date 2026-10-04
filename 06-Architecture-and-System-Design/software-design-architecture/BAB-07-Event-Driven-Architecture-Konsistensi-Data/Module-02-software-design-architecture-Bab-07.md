# BAB 07: EVENT-DRIVEN ARCHITECTURE & KONSISTENSI DATA
## MODUL 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengidentifikasi dan memitigasi anomali *Dual-Write Problem* menggunakan *Transactional Outbox Pattern* dan *Change Data Capture* (CDC).
- Mendesain dan mengimplementasikan koordinasi transaksi terdistribusi berbasis *Saga Pattern* (*Choreography* vs *Orchestration*) dengan mekanisme kompensasi otomatis.
- Membangun *Idempotent Consumer Engine* dengan penanganan deduplikasi pesan pada tingkat persistensi dan *in-memory cache*.
- Merancang topologi penanganan kegagalan tingkat lanjut (*Poison Pill Handling*, *Retry Topics*, *Dead Letter Queues* / DLQ, dan *Circuit Breaker* pada consumer).
- Mengelola evolusi skema pesan (*Schema Evolution*) tanpa *downtime* menggunakan Apache Avro / Protobuf dan Confluent/Apicurio Schema Registry dengan prinsip kompatibilitas maju (*forward*) dan mundur (*backward*).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- **Distributed Systems Fundamentals**: Teorema CAP, PACELC, model konsistensi (*Strong*, *Eventual*, *Causal*).
- **Messaging Core Concepts**: Broker, Topics, Partitions, Consumer Groups, Offsets, Semantik Pengiriman (*At-Most-Once*, *At-Least-Once*, *Exactly-Once*).
- **RDBMS Internals**: Mekanisme ACID, transaksi bertingkat, isolation level, dan write-ahead log (WAL).
- **Bahasa Pemrograman**: Go (Golang) tingkat menengah ke atas (goroutine, channels, context, SQL driver).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 The Dual-Write Problem & The Outbox Pattern
Ketika microservice perlu memperbarui database internal sekaligus menerbitkan event ke message broker (misalnya Apache Kafka), eksekusi dua operasi I/O terpisah ini rentan terhadap kegagalan parsial:

```
[Service Boundary]
 1. DB Exec: UPDATE account SET balance = balance - 100 WHERE id = 1; (SUCCESS)
 2. Network Failure / App Crash sebelum publish event!
 3. Broker Publish: Event `AccountDebited` TIDAK PERNAH TERKIRIM.
==> DATA TIDAK KONSISTEN ANTAR-SERVICE.
```

Solusi deterministik adalah **Transactional Outbox Pattern**. Mutasi domain dan pencatatan event ditulis ke database yang sama dalam satu transaksi ACID lokal:

```sql
BEGIN TRANSACTION;
-- 1. Mutasi Domain State
UPDATE accounts SET balance = balance - 100 WHERE id = 'acc-123';

-- 2. Tulis Event ke Outbox Table
INSERT INTO outbox_events (id, aggregate_type, aggregate_id, event_type, payload, status, created_at)
VALUES ('evt-001', 'Account', 'acc-123', 'AccountDebited', '{"amount":100}', 'PENDING', NOW());
COMMIT;
```

Pengiriman event dari outbox ke broker dieksekusi melalui:
1. **Polling Publisher**: Worker berkala membaca tabel menggunakan `SELECT ... FOR UPDATE SKIP LOCKED`.
2. **Transaction Log Tailing (CDC)**: Tool seperti Debezium membaca WAL Postgres/Binlog MySQL secara asinkron tanpa membebani query planner engine aplikasi.

```
+-------------------------------------------------------------------------------+
| Transactional Boundary (RDBMS)                                                |
|                                                                               |
|  +--------------------+     ACID Commit      +-----------------------------+  |
|  |   Domain Tables    | <==================> |     outbox_events Table     |  |
|  +--------------------+                      +-----------------------------+  |
+-------------------------------------------------------------+-----------------+
                                                              | Read WAL Engine
                                                              v
                                              +-------------------------------+
                                              | Debezium / Kafka Connect      |
                                              +---------------+---------------+
                                                              | Publish
                                                              v
                                              +-------------------------------+
                                              | Apache Kafka Cluster          |
                                              | Topic: account-events         |
                                              +-------------------------------+
```

#### 3.2 Saga Execution Coordinator (SEC) vs Choreography
Mengelola transaksi lintas batas layanan (*cross-boundary transaction*) menuntut implementasi Saga:
- **Choreography-based Saga**: Layanan mendengarkan event dari layanan lain dan secara mandiri memutuskan untuk mengeksekusi aksi lokal atau menerbitkan event lanjutan/kompensasi.
  - *Karakteristik*: Loose coupling, cocok untuk alur sederhana (2-4 langkah).
  - *Kelemahan*: Sulit dilacak (*spaghetti event chains*), risiko cyclic dependency.
- **Orchestration-based Saga**: Layanan orchestrator terpusat (*State Machine*) mengirimkan command kepada partisipan, memvalidasi respons, dan memerintahkan langkah rollback/kompensasi secara eksplisit jika terjadi kegagalan.
  - *Karakteristik*: Alur terkontrol, observabilitas tinggi, penanganan kegagalan terpusat.
  - *Kelemahan*: Orchestrator berisiko menjadi titik beban logis (*smart orchestrator, dumb pipes*).

#### 3.3 Consumer Idempotency Matrix
Distribusi pesan *At-Least-Once* memastikan tidak ada event yang hilang, tetapi membuka risiko event terduplikasi (*duplicate deliveries* akibat rebalance, network timeout, atau retry broker).

```
                      +-----------------------------+
                      |       Event Diterima        |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |   Cek Hash / Idempotency    |
                      |   Key di Cache (Redis)      |
                      +--------------+--------------+
                                     |
                      +--------------+--------------+
             Ada (Duplikat)                         Tidak Ada
                      |                                     |
                      v                                     v
          +-----------------------+             +-----------------------+
          | Log Duplicate Metrics |             | Jalankan DB Tx:       |
          | ACK ke Message Broker |             | 1. Simpan Key DB      |
          +-----------------------+             | 2. Eksekusi Bisnis    |
                                                +-----------+-----------+
                                                            |
                                                +-----------v-----------+
                                                | Set Cache & ACK Broker|
                                                +-----------------------+
```

---

### 4. Why & What

| Dimensi | Mengapa Dibutuhkan? | Apa Komponen / Polanya? |
| :--- | :--- | :--- |
| **Konsistensi Data** | Menghilangkan data corruption akibat kegagalan jaringan separuh jalan (*split-brain/partial commit*). | *Transactional Outbox*, *Debezium CDC*, *Two-Phase Commit Replacement*. |
| **Resiliensi Transaksi** | Transaksi terdistribusi ACID (2PC) mengunci resource (*blocking lock*), tidak skalabel di cloud. | *Saga Orchestrator*, Kompensasi Transaksi (Pembalik Aksi). |
| **Toleransi Redundansi** | Broker modern bekerja optimal pada semantik *At-Least-Once Delivery*. | *Idempotent Consumers*, Unique Transaction Keys, Deduplication Stores. |
| **Fault Isolation** | Pesan rusak (*malformed*) tidak boleh memblokir pemrosesan antrean partisi utama. | *Dead Letter Topic (DLT)*, *Retry Topic with Exponential Backoff*. |
| **Evolusi Kontrak** | Payload event berevolusi seiring iterasi fitur tanpa merusak consumer lama. | *Schema Registry*, Konvensi Protobuf/Avro (*Backward/Forward Compatibility*). |

---

### 5. How (Workflow Detail)

#### Workflow: Saga Orchestration Transaksi Pembayaran & Pemesanan
1. **Inisiasi**: Client memanggil `POST /orders`. Order Service bertindak sebagai Orchestrator, menyimpan `Order` dengan status `PENDING`, dan menerbitkan command via Kafka.
2. **Step 1 (Reservasi Stok)**:
   - Orchestrator mengirim command `ReserveInventoryCommand`.
   - Inventory Service memotong stok lokal secara ACID.
   - Inventory Service mempublikasikan `InventoryReservedEvent`.
3. **Step 2 (Pemotongan Saldo/Pembayaran)**:
   - Orchestrator menerima event stok berhasil, lalu mengirim command `ProcessPaymentCommand`.
   - Payment Gateway Service mencoba mendebit kartu/saldo.
   - *Kasus Gagal*: Pembayaran ditolak (`PaymentFailedEvent`).
4. **Step 3 (Kompensasi / Rollback)**:
   - Orchestrator menangkap `PaymentFailedEvent`.
   - State machine menandai status order: `COMPENSATING`.
   - Orchestrator mengirim command `CompensateInventoryCommand` (mengembalikan stok).
   - Inventory Service menambahkan kembali stok yang sempat ditahan.
   - Orchestrator mengupdate status akhir order ke `FAILED`.

```
Client         Order Orchestrator          Inventory Service          Payment Service
  |                    |                           |                         |
  |--- CreateOrder --->|                           |                         |
  |                    |-- ReserveStockCommand --->|                         |
  |                    |                           |-- (Debit Stock OK)      |
  |                    |<- StockReservedEvent -----|                         |
  |                    |                                                     |
  |                    |-- ProcessPaymentCommand --------------------------->|
  |                    |                                                     |-- (Payment Fails!)
  |                    |<- PaymentFailedEvent -------------------------------|
  |                    |
  |                    |-- CompensateStockCommand ->|
  |                    |                           |-- (Credit Stock Back)
  |                    |<- StockCompensatedEvent --|
  |                    |
  | (Order Mark FAILED)|
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Notaris dan Surat Perintah Berantai
Bayangkan Anda membeli rumah:
- **Tanpa Transaksi Outbox**: Anda membayar uang muka ke penjual, lalu Anda sendiri yang harus mengabari kantor BPN melalui kurir motor. Jika kurir tertabrak di jalan, penjual sudah memegang uang Anda, tetapi BPN tidak pernah mencatat perubahan kepemilikan.
- **Dengan Transaksi Outbox**: Anda mendatangi Notaris. Notaris mencatat pembayaran dan sekaligus memasukkan berkas pendaftaran BPN ke dalam lemari besi resminya dalam satu sesi tatap muka (Atomic). Kurir resmi notaris bertugas mengambil surat dari lemari besi tersebut dan mengantarkannya ke BPN sampai ada tanda terima resmi.
- **Saga Kompensasi**: Jika BPN menolak karena tanah sengketa, Notaris menginstruksikan bank untuk membatalkan pencairan uang dan mengembalikannya ke rekening Anda (Kompensasi).

#### Diagram Pola Resiliensi Consumer (Retry Topic & Dead Letter Queue)

```
[Kafka Ingress: Topic 'orders']
         |
         v
+------------------+     Gagal (Transient Error)     +----------------------+
| Main Consumer    |-------------------------------->| Topic: orders-retry-1|
| (Attempt 1)      |                                 | (Backoff: 5s)        |
+--------+---------+                                 +----------+-----------+
         | Sukses                                               |
         v                                                      v
   [Commit Offset]                                   +----------------------+
                                                     | Retry Consumer 1     |
                                                     | (Attempt 2)          |
                                                     +----------+-----------+
                                                                |
                                             Gagal              v
                                        +-----------------------------------+
                                        | Topic: orders-retry-2             |
                                        | (Backoff: 30s)                    |
                                        +-----------------+-----------------+
                                                          |
                                                          v
                                             +------------------------------+
                                             | Retry Consumer 2 (Attempt 3) |
                                             +------------+-----------------+
                                                          |
                                          Gagal Fatal     v
                                        +-----------------------------------+
                                        | Topic: orders-dlq (Dead Letter)   |
                                        | - Alerting (PagerDuty)            |
                                        | - Dashboard Investigasi Manual    |
                                        +-----------------------------------+
```

---

### 7. Implementation: Simple & Practical Examples

Berikut adalah implementasi sistem produksi tingkat tinggi menggunakan Go:

#### 7.1 Polling-Based Transactional Outbox Worker
Implementasi worker yang mengekstraksi data secara deterministik menggunakan PostgreSQL `FOR UPDATE SKIP LOCKED`.

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"time"

	_ "github.com/lib/pq"
)

type OutboxEvent struct {
	ID            string    `json:"id"`
	AggregateType string    `json:"aggregate_type"`
	AggregateID   string    `json:"aggregate_id"`
	EventType     string    `json:"event_type"`
	Payload       []byte    `json:"payload"`
	CreatedAt     time.Time `json:"created_at"`
}

type MessageProducer interface {
	Publish(ctx context.Context, topic string, key string, payload []byte) error
}

type MockKafkaProducer struct{}

func (m *MockKafkaProducer) Publish(ctx context.Context, topic string, key string, payload []byte) error {
	log.Printf("[Kafka Producer] Dispatched event to topic %s: Key=%s Payload=%s\n", topic, key, string(payload))
	return nil
}

type OutboxProcessor struct {
	db       *sql.DB
	producer MessageProducer
	batch    int
}

func NewOutboxProcessor(db *sql.DB, producer MessageProducer, batchSize int) *OutboxProcessor {
	return &OutboxProcessor{
		db:       db,
		producer: producer,
		batch:    batchSize,
	}
}

func (op *OutboxProcessor) ProcessPendingEvents(ctx context.Context) (int, error) {
	tx, err := op.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return 0, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// FOR UPDATE SKIP LOCKED menghindari lock contention antar horizontal worker pods
	query := `
		SELECT id, aggregate_type, aggregate_id, event_type, payload, created_at
		FROM outbox_events
		WHERE processed = FALSE
		ORDER BY created_at ASC
		LIMIT $1
		FOR UPDATE SKIP LOCKED;
	`

	rows, err := tx.QueryContext(ctx, query, op.batch)
	if err != nil {
		return 0, fmt.Errorf("failed to lock outbox rows: %w", err)
	}
	defer rows.Close()

	var events []OutboxEvent
	var idsToMark []string

	for rows.Next() {
		var evt OutboxEvent
		if err := rows.Scan(&evt.ID, &evt.AggregateType, &evt.AggregateID, &evt.EventType, &evt.Payload, &evt.CreatedAt); err != nil {
			return 0, fmt.Errorf("failed to scan row: %w", err)
		}
		events = append(events, evt)
		idsToMark = append(idsToMark, evt.ID)
	}

	if len(events) == 0 {
		return 0, nil
	}

	for _, event := range events {
		topic := fmt.Sprintf("%s-domain-events", event.AggregateType)
		if err := op.producer.Publish(ctx, topic, event.AggregateID, event.Payload); err != nil {
			return 0, fmt.Errorf("publish failed for event id %s: %w", event.ID, err)
		}
	}

	// Update status agar tidak diproses ulang
	markQuery := `UPDATE outbox_events SET processed = TRUE, processed_at = NOW() WHERE id = ANY($1);`
	if _, err := tx.ExecContext(ctx, markQuery, (idsToMark)); err != nil {
		return 0, fmt.Errorf("failed to mark outbox events: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return 0, fmt.Errorf("failed to commit outbox processing: %w", err)
	}

	return len(events), nil
}
```

#### 7.2 Idempotent Consumer Engine
Engine penerima pesan dengan verifikasi konsistensi ganda (Redis Cache + Unique DB Constraint Lock):

```go
package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"time"
)

var ErrDuplicateEvent = errors.New("event has already been processed")

type ProcessFunc func(ctx context.Context, payload []byte) error

type IdempotentConsumer struct {
	db *sql.DB
}

func NewIdempotentConsumer(db *sql.DB) *IdempotentConsumer {
	return &IdempotentConsumer{db: db}
}

func (c *IdempotentConsumer) ExecuteIdempotent(ctx context.Context, eventID string, source string, payload []byte, fn ProcessFunc) error {
	tx, err := c.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("cannot start transaction: %w", err)
	}
	defer tx.Rollback()

	// 1. Coba lock event ID via INSERT
	var insertedID string
	insertQuery := `
		INSERT INTO processed_events (event_id, source, processed_at)
		VALUES ($1, $2, NOW())
		ON CONFLICT (event_id) DO NOTHING
		RETURNING event_id;
	`
	err = tx.QueryRowContext(ctx, insertQuery, eventID, source).Scan(&insertedID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			// Event sudah pernah diproses sebelumnya
			log.Printf("[IdempotentConsumer] Event %s already executed. Skipping safely.\n", eventID)
			return ErrDuplicateEvent
		}
		return fmt.Errorf("failed to register event id idempotency: %w", err)
	}

	// 2. Eksekusi Business Logic inti dalam transaksi ACID yang sama
	if err := fn(ctx, payload); err != nil {
		return fmt.Errorf("business logic failed: %w", err)
	}

	// 3. Commit state atomic
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	log.Printf("[IdempotentConsumer] Event %s processed successfully\n", eventID)
	return nil
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Pemrosesan Pembayaran Global (Skala 50.000 TPS)
- **Konteks**: Sebuah perusahaan decacorn *financial technology* memproses transaksi multi-mata uang lintas batas.
- **Masalah Utama**:
  1. Terjadi anomali pemotongan saldo berganda (*double debit*) akibat network partition antara ingress payment proxy dan database ledger.
  2. Latensi tinggi akibat *distributed locking* (Redis Redlock) saat ribuan request memperebutkan satu akun merchant yang sama (*hot account*).
  3. Outbox worker reguler menyebabkan CPU spike 98% di PostgreSQL utama ketika jumlah antrean mencapai jutaan baris.
- **Arsitektur Solusi**:
  1. **CDC Replacement via Debezium**: Mengganti Polling Outbox dengan Debezium Engine yang membaca Postgres WAL secara streaming dan memasukkannya ke Apache Kafka topic dengan latency sub-10ms.
  2. **Partition Affinity Ledger**: Topic Kafka dibagi ke 128 partisi dengan `account_id` sebagai partition key, menjamin seluruh event untuk akun tertentu selalu diproses terurut secara serial oleh satu consumer instance, mengeliminasi kebutuhan distributed locks.
  3. **Idempotency Multi-Tier**:
     - *L1*: In-memory Bloom Filter pada consumer pod (menolak 99% duplikasi seketika).
     - *L2*: Redis key TTL 24 jam dengan atomic `SET NX EX`.
     - *L3*: Primary database unique constraint pada tabel `ledger_entries(idempotency_key)`.
- **Hasil Metrik**:
  - Nol kasus *double debit* dari 1,2 miliar transaksi bulanan.
  - Latensi p99 turun drastis dari 850ms ke 42ms.
  - Beban I/O database berkurang hingga 70% karena penghapusan query polling interval pendek.

---

### 9. Trade-offs & Comparisons

```
               [Latency]
                 /   \
                /     \
               /       \
              /         \
    [Throughput]-------[Consistency Guarantee]
```

| Pendekatan / Pola | Latency | Throughput | Konsistensi | Biaya Infrastruktur | Kompleksitas Operasional |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Polling Outbox** | Tinggi (Terikat Interval Polling) | Menengah-Rendah (DB Lock Contention) | Kuat (ACID Lokal) | Rendah (Hanya RDBMS lokal) | Rendah |
| **CDC (Debezium + Kafka)** | Sub-detik (~10-50ms) | Sangat Tinggi (Streaming append-only) | Kuat (WAL Replication) | Tinggi (Kafka Connect Cluster + Zookeeper/KRaft) | Sangat Tinggi |
| **Saga Orchestration** | Menengah (Banyak Round-trips jaringan) | Menengah-Tinggi | Eventual (Terkontrol State Machine) | Menengah | Tinggi |
| **Saga Choreography** | Rendah (Direct Asynchronous Fire) | Ekstrem | Eventual (Rentan Anomali) | Rendah-Menengah | Sangat Tinggi (Observabilitas sulit) |
| **Strict 2PC (Two-Phase Commit)**| Sangat Buruk (Blocking Latency Tinggi) | Sangat Rendah | Strong ACID | Sangat Tinggi | Ekstrem (Single Point of Failure) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. The Poison Pill Deadlock
- **Gejala**: Satu pesan dengan format JSON korup menyebabkan Consumer pod crash loop (*OOM/Panic*), partisi berhenti bergerak (*offset lag* melonjak tak terbatas).
- **Akar Masalah**: Exception tidak ditangkap (*unhandled panic*), dan broker terus mengirimkan pesan yang sama karena offset belum ter-commit.
- **Solusi**: Gunakan middleware pemulihan (*panic recovery*) yang menangkap error deserialisasi dan langsung mengirimkan raw payload ke `DLQ Topic` tanpa menghentikan offset cursor.

#### 2. Zombie Sagas (Orphan Executions)
- **Gejala**: Status transaksi menggantung di state `IN_PROGRESS` selamanya, stok barang tertahan dan tidak pernah dirilis ke publik.
- **Akar Masalah**: Orchestrator crash di tengah eksekusi, tanpa adanya mekanisme timeout reaper / dead-man switch.
- **Solusi**: Terapkan pattern **Timeout Sweep Worker** yang memindai transaksi `PENDING` dengan usia > threshold (misal 5 menit) dan secara otomatis men-trigger alur kompensasi rollback.

#### 3. Out-of-Order Compensation
- **Gejala**: Event rollback kompensasi tiba di microservice tujuan *sebelum* event aksi awal tiba karena latensi rute jaringan yang berbeda.
- **Akar Masalah**: Jaringan asinkron tidak menjamin urutan antar-topik yang berbeda.
- **Solusi**: Simpan state versioning pada entity agregat. Jika event kompensasi tiba untuk entitas yang belum dibuat, simpan record berstatus `TOMBSTONE`/`PRE_CANCELLED` sehingga ketika event create tiba terlambat, ia akan langsung dibatalkan seketika.

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Partition Key**: Jangan gunakan nilai acak (seperti UUID transaksi baru) sebagai Partition Key Kafka jika ordering diperlukan. Gunakan Business Entity ID (misal: `account_id`, `merchant_id`).
- [ ] **Idempotence Key Persistence**: Pastikan penyimpanan Idempotency Key dilakukan di *storage engine* dan *transaction boundary* yang sama dengan mutasi data bisnis.
- [ ] **Context & Distributed Tracing**: Selalu sematkan traceparent header (`W3C Trace Context`) ke dalam record metadata Kafka untuk visualisasi end-to-end tracing di OpenTelemetry/Jaeger.
- [ ] **Bounded Retry with Exponential Backoff & Jitter**: Jangan pernah mengulang pengiriman pesan gagal seketika secara terus menerus (*tight loop*). Tambahkan interval eksponensial dan keacakan (*jitter*) untuk menghindari *thundering herd problem*.
- [ ] **Schema Backward Compatibility Rules**: Konfigurasikan Schema Registry pada mode validasi `BACKWARD` atau `FULL` agar penambahan field baru di masa depan bersifat non-breaking bagi consumer lama.
- [ ] **Alerting Threshold on Offset Lag**: Pasang metric alert pada Prometheus jika Kafka `consumer_lag` melebihi ambang batas toleransi SLA (misalnya: lag > 5000 pesan selama 3 menit berturut-turut).

---

### 12. Hands-on Practice

Buat seluruh file praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Persiapan Lingkungan (Docker Compose)
Simpan file berikut di `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    container_name: m02-postgres
    environment:
      POSTGRES_USER: engine_user
      POSTGRES_PASSWORD: engine_password
      POSTGRES_DB: core_banking
    ports:
      - "5432:5432"
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

#### Langkah 2: Inisialisasi Skema Database
Simpan file berikut di `hands-on/m02/init.sql`:

```sql
CREATE TABLE accounts (
    id VARCHAR(64) PRIMARY KEY,
    owner_name VARCHAR(128) NOT NULL,
    balance NUMERIC(15, 2) NOT NULL CHECK (balance >= 0)
);

CREATE TABLE outbox_events (
    id VARCHAR(64) PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_outbox_unprocessed ON outbox_events(created_at) WHERE processed = FALSE;

CREATE TABLE processed_events (
    event_id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(64) NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seeding data awal
INSERT INTO accounts (id, owner_name, balance) VALUES ('acc-corp-01', 'Enterprise Holding', 10000000.00);
```

#### Langkah 3: Eksekusi Kode Aplikasi Pemroses Transaksi
Simpan file berikut di `hands-on/m02/main.go`:

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
)

func main() {
	dsn := "postgres://engine_user:engine_password@localhost:5432/core_banking?sslmode=disable"
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		log.Fatalf("Database connection failure: %v", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatalf("Database unreachable: %v", err)
	}
	log.Println("Terkoneksi ke PostgreSQL Engine.")

	ctx := context.Background()

	// 1. Eksekusi Transaksi Bisnis dengan Pola Transactional Outbox
	orderID := "ord-" + uuid.New().String()[:8]
	accountID := "acc-corp-01"
	amountToDebit := 500000.00

	err = DebitAccountWithOutbox(ctx, db, accountID, orderID, amountToDebit)
	if err != nil {
		log.Fatalf("Gagal memproses transaksi outbox: %v", err)
	}

	// 2. Verifikasi Baris Outbox yang Tersimpan
	var count int
	err = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM outbox_events WHERE processed = FALSE").Scan(&count)
	if err != nil {
		log.Fatalf("Query check failed: %v", err)
	}
	fmt.Printf("[Verifikasi Berhasil] Event outbox tersimpan secara atomik! Unprocessed events: %d\n", count)
}

func DebitAccountWithOutbox(ctx context.Context, db *sql.DB, accountID string, orderID string, amount float64) error {
	tx, err := db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// Operasi 1: Update Saldo
	res, err := tx.ExecContext(ctx, "UPDATE accounts SET balance = balance - $1 WHERE id = $2 AND balance >= $1", amount, accountID)
	if err != nil {
		return fmt.Errorf("gagal mutasi saldo: %w", err)
	}
	rowsAffected, _ := res.RowsAffected()
	if rowsAffected == 0 {
		return fmt.Errorf("saldo tidak mencukupi atau account id tidak ditemukan")
	}

	// Operasi 2: Buat Payload dan Simpan Event ke Outbox
	payload := map[string]interface{}{
		"order_id":   orderID,
		"account_id": accountID,
		"amount":     amount,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}
	payloadBytes, _ := json.Marshal(payload)

	eventID := "evt-" + uuid.New().String()
	_, err = tx.ExecContext(ctx, `
		INSERT INTO outbox_events (id, aggregate_type, aggregate_id, event_type, payload, processed)
		VALUES ($1, $2, $3, $4, $5, FALSE)
	`, eventID, "Account", accountID, "AccountDebited", payloadBytes)

	if err != nil {
		return fmt.Errorf("gagal menulis outbox: %w", err)
	}

	// Commit Transaksi ACID
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("gagal commit database: %w", err)
	}

	log.Printf("[Success] Akun %s didebit Rp%.2f | EventID: %s berhasil dibuat di Outbox.\n", accountID, amount, eventID)
	return nil
}
```

#### Langkah 4: Jalankan dan Uji
```bash
cd hands-on/m02
docker compose up -d
go mod init m02-eda
go get github.com/lib/pq
go get github.com/google/uuid
go run main.go
```

---

### 13. Exercises

#### 13.1 Level Easy
- **Tugas**: Tambahkan validasi pada struct event di Go untuk memastikan field `event_type` tidak boleh bernilai string kosong sebelum ditulis ke tabel outbox.
- **Kriteria Keberhasilan**: Program mengembalikan error eksplisit `ErrInvalidEventType` jika atribut tersebut kosong tanpa membuka koneksi transaksi ke PostgreSQL.

#### 13.2 Level Medium
- **Tugas**: Modifikasi kode `OutboxProcessor` di Bagian 7.1 untuk menambahkan mekanisme **Exponential Backoff Retry Strategy**. Jika koneksi ke mock broker gagal, worker harus mencoba kembali sebanyak 3 kali (100ms, 200ms, 400ms) sebelum membatalkan batch dan melepaskan lock baris database.
- **Kriteria Keberhasilan**: Aplikasi tidak menyebabkan database deadlock dan mencatat log warning terstruktur saat percobaan retry terjadi.

#### 13.3 Level Hard
- **Tugas**: Implementasikan **Distributed Dead Letter Queue (DLQ) Pipeline**. Buat fungsi consumer yang membaca stream data; jika payload mengalami parsing error (*unrecoverable*), kirimkan data ke topic `orders-dlq` beserta header diagnosis (`x-error-message`, `x-failed-at`, `x-original-topic`), lalu commit offset partisi utama agar pipeline tidak macet.
- **Kriteria Keberhasilan**: Unit test membuktikan pesan malformed masuk ke antrean DLT dan pesan valid berikutnya pada antrean utama tetap terproses secara sekuensial.

---

### 14. Challenge (Skenario Kompleks)

**Konteks Kasus**:
Anda adalah Principal Architect pada platform *Crypto/Stock Exchange*. Sistem harus mengeksekusi *Flash Sale Voucher Investasi* dengan kuota terbatas (1.000 voucher) yang diperebutkan oleh 500.000 user secara bersamaan dalam waktu 10 detik. 

**Kondisi Batasan Sistem**:
1. Tidak boleh terjadi *over-allocation* (voucher yang terbit tidak boleh melebihi kuota 1.000 unit, batas toleransi kesalahan = 0).
2. Database relasional pusat tidak mampu menahan 500.000 concurrent update connection secara langsung.
3. Transaksi melibatkan 3 sistem terpisah: `Voucher Inventory Service`, `User Balance Ledger`, dan `Notification Service`.
4. Jika pemotongan saldo user gagal karena dana tidak cukup, kuota voucher yang sudah sempat diambil harus dikembalikan ke pool secara instan dalam kurun waktu < 100ms agar user lain dapat mengklaimnya kembali.

**Instruksi Tantangan**:
Rancang arsitektur event-driven komprehensif yang menyelesaikan masalah ini tanpa menggunakan Distributed Lock yang memblokir (Non-blocking I/O). Tuliskan:
1. Topologi aliran pesan Kafka (jumlah partisi, penentuan partisi key, konfigurasi producer/consumer).
2. Pola konsistensi yang digunakan beserta diagram state machine orchestrator/choreography.
3. Strategi kompensasi real-time jika balance user tidak mencukupi.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Pemahaman Konseptual (Basic)
1. Apa masalah mendasar dari *Dual-Write Problem* pada arsitektur microservices?
2. Mengapa isolasi level transaksi tradisional RDBMS tidak dapat menjamin konsistensi data yang melibatkan pengiriman pesan broker eksternal?
3. Sebutkan perbedaan utama antara semantik pengiriman *At-Least-Once* dan *Exactly-Once* pada Kafka!
4. Apa fungsi klausa SQL `FOR UPDATE SKIP LOCKED` dalam implementasi polling outbox table?
5. Mengapa format teks biasa seperti JSON murni tanpa skema berisiko tinggi digunakan pada sistem EDA enterprise jangka panjang?

#### Bagian B: Analisis & Desain (Intermediate)
6. Bagaimana cara mencegah terjadinya *race condition* jika dua event kompensasi dari Saga Orchestrator tiba pada waktu yang bersamaan?
7. Mengapa Debezium CDC dinilai memiliki performa lebih tinggi dibandingkan Polling Worker untuk implementasi Transactional Outbox?
8. Dalam kondisi apa arsitektur *Choreography Saga* lebih direkomendasikan daripada *Orchestration Saga*?
9. Apa fungsi dari penambahan komponen *Jitter* pada algoritma Exponential Backoff saat melakukan retry pengiriman event?
10. Bagaimana Anda mengatasi issue *Tombstone Message* pada compact topic Kafka agar tidak menghapus riwayat audit data secara permanen?

#### Bagian C: Skenario Kasus Produksi
11. **Skenario 1**: Sebuah Consumer Group mengalami lag yang terus membengkak setelah tim melakukan deployment fitur baru. Resource CPU dan Memory berada pada tingkat normal (30%). Setelah diperiksa, log consumer dipenuhi oleh error timeout panggilan ke external payment gateway pihak ketiga. Bagaimana langkah remediasi arsitektural untuk memulihkan throughput tanpa menghilangkan pesan transaksi?
12. **Skenario 2**: Service B mendengarkan event dari Service A. Tiba-tiba terjadi network glitch yang mengakibatkan Service B menerima event `OrderCancelled` sebelum menerima event `OrderCreated`. Jelaskan arsitektur penanganan state (*Out-of-order execution*) untuk skenario ini agar saldo user tidak korup!
13. **Skenario 3**: Tim data engineering menuntut penambahan field baru yang bersifat *mandatory* (wajib diisi) pada schema event Kafka yang sudah aktif dikonsumsi oleh 15 downstream services di sistem produksi. Bagaimana strategi mitigasi perubahan kontrak ini tanpa merusak consumer lama (*zero-downtime transition*)?

---

### 16. Summary
- **Dual-Write Mitigation**: Mengandalkan pemanggilan API broker di dalam transaksi RDBMS lokal adalah kesalahan desain fatal. *Transactional Outbox Pattern* (melalui Polling atau CDC/Debezium) adalah fondasi mutlak untuk menjamin pengiriman event yang konsisten.
- **Event-Driven Consistency**: Menggantikan distributed ACID transaction dengan *Saga Pattern*. Saga mengelola konsistensi data melalui urutan transaksi lokal dan aksi kompensasi balik.
- **Defensive Consumer**: Setiap consumer pada arsitektur terdistribusi wajib berstatus *idempotent* dan mampu menangani duplikasi pengiriman tanpa merusak integritas state bisnis.
- **Resilience Topology**: Penggunaan multi-tiered topic (*Main*, *Retry*, *Dead-Letter Queue*) memastikan anomali satu event (*Poison Pill*) tidak melumpuhkan seluruh antrean pemrosesan sistem enterprise.