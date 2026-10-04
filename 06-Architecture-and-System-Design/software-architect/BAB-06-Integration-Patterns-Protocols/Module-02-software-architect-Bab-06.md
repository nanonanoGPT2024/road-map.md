# BAB 06: Integration Patterns & Protocols
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mendiagnosis dan Mengeliminasi Dual-Write Problem** pada sistem terdistribusi menggunakan kombinasi *Transactional Outbox Pattern* dan *Change Data Capture (CDC)*.
2. **Merancang dan Mengimplementasikan Idempotent Consumer Pattern** berkinerja tinggi menggunakan teknik *Distributed Locking* dan *Deduplication Store* dengan jaminan *Exactly-Once Processing Semantics* pada level aplikasi.
3. **Mengimplementasikan Enterprise Integration Patterns (EIP)** tingkat lanjut: *Claim-Check Pattern* untuk payload berukuran besar dan *Content-Based Dynamic Router* dengan protokol hibrida (gRPC, Kafka, dan REST).
4. **Menganalisis Trade-off Latensi, Throughput, dan Konsistensi** antar protokol integrasi sinkron vs asinkron di bawah kondisi degradasi jaringan (*network partitions*).
5. **Mengaudit, Melacak, dan Men-debug Aliran Pesan Terdistribusi** menggunakan *Distributed Tracing Context Propagation* (W3C Trace Context) berbasis OpenTelemetry pada batas-batas protokol heterogen.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memahami:
* **Jaringan Komputer:** Model OSI, TCP handshakes, TLS 1.3 termination, serta protokol transport (HTTP/1.1 vs HTTP/2 multiplexing).
* **Distributed Systems Fundamentals:** Teorema CAP/PACELC, model konsistensi data (*Linearizable*, *Sequential*, *Eventual Consistency*), dan kegagalan parsial (*split-brain*, *network jitter*).
* **Basis Data Relasional:** Tingkat isolasi transaksi ACID (*Read Committed*, *Repeatable Read*, *Serializable*), Write-Ahead Logging (WAL), dan locking primitives.
* **Dasar Message Broker:** Topologi Apache Kafka (Topic, Partition, Offset, Consumer Group) atau RabbitMQ (Exchange, Queue, Binding).
* **Bahasa Pemrograman:** Pemahaman mendalam mengenai Go (Golang) untuk concurrency primitives (`goroutine`, `channel`, `sync.Mutex`, `context`).

---

### 3. Concept & Internal Architecture

Integrasi sistem tingkat enterprise menuntut reliabilitas mutlak di atas infrastruktur fisik yang tidak dapat diandalkan (*unreliable network*). Masalah klasik yang dihadapi arsitek adalah ketidakmungkinan melakukan atomic commit melintasi batas jaringan heterogen (misalnya: menyimpan data ke database relasional PostgreSQL dan mempublikasikan event ke Apache Kafka secara bersamaan) tanpa protokol koordinasi berat seperti Two-Phase Commit (2PC) yang merusak throughput dan skalabilitas.

#### A. Transactional Outbox Pattern & CDC Engine Internals

Pendekatan modern memecahkan masalah ini dengan memanfaatkan *Local Transaction Boundary* dari basis data relasional.

```
+-------------------------------------------------------------------------------+
|                              APPLICATION RUNTIME                              |
|                                                                               |
|  [Business Logic] ---> BEGIN TX                                               |
|                          |---> INSERT INTO orders (...)                       |
|                          |---> INSERT INTO outbox_events (payload, status...) |
|                        COMMIT TX                                              |
+----------------------------+--------------------------------------------------+
                             |
                   PostgreSQL Write-Ahead Log (WAL)
                             |
                             v
+----------------------------+--------------------------------------------------+
|                   CHANGE DATA CAPTURE (CDC) ENGINE                            |
|                   (e.g., Debezium Engine / Kafka Connect)                     |
|                                                                               |
|  [Replication Slot] ---> Read Logical Decoding Stream (pgoutput)              |
|                          Transform to CloudEvents Schema                      |
|                          Publish to Target Kafka Topic (orders.events)         |
+----------------------------+--------------------------------------------------+
                             |
                             v
                     [ Apache Kafka Cluster ]
```

1. **Local ACID Transaction:** Aplikasi menulis state mutasi bisnis (`orders`) dan metadata event (`outbox_events`) di dalam satu transaksi database lokal yang sama. Jika database mengalami *crash* atau *rollback*, kedua operasi gagal secara bersamaan.
2. **Logical Decoding / WAL Streaming:** CDC Engine (misal: Debezium) terhubung ke PostgreSQL menggunakan modul *logical decoding* (`pgoutput`). Mesin CDC membaca WAL secara non-blocking langsung dari disk database, mengubah representasi biner menjadi aliran event terstruktur.
3. **At-Least-Once Delivery Guarantee:** CDC engine menjamin setiap record outbox yang di-commit akan dipancarkan ke broker perpesanan minimal satu kali (*at-least-once*).

#### B. Idempotent Consumer & Deduplication Engine Internals

Karena broker pesan modern menggunakan jaminan *at-least-once delivery*, duplikasi pesan pasti terjadi akibat *network retry*, *consumer rebalance*, atau *broker acknowledgment timeout*. Konsumen wajib bersifat idempoten.

```
                           Incoming Message (Msg ID: "uuid-1234")
                                          |
                                          v
                         +--------------------------------+
                         |      Distributed Lock         |
                         |   (Redis SET NX EX: 10s)       |
                         +----------------+---------------+
                                          |
                        +-----------------+-----------------+
                        | Lock Acquired?                    |
                       YES                                 NO
                        |                                   |
                        v                                   v
          +-----------------------------+         +--------------------+
          | Check Idempotency Record    |         | Concurrency Retry/ |
          | (DB: processed_messages)    |         | Drop duplicate req |
          +--------------+--------------+         +--------------------+
                         |
           +-------------+-------------+
           | Record Exists?            |
          NO                          YES
           |                           |
           v                           v
  +--------------------+      +--------------------+
  | Execute Business   |      | ACK to Broker      |
  | Logic (ACID TX)    |      | (Skip Execution)   |
  | + Record Msg ID    |      +--------------------+
  +--------------------+
           |
           v
  +--------------------+
  | Release Lock & ACK |
  +--------------------+
```

Komponen internal idempotensi mencakup:
* **Fencing Token / Distributed Lock:** Mencegah eksekusi paralel dari dua instance event yang identik yang dikonsumsi secara serentak (*concurrent duplicate delivery*).
* **Idempotency Store:** Tabel persisten berbasis database atau key-value store in-memory (dengan snapshot disk) yang mencatat *Unique Message Hash/ID* beserta status eksekusi dan responsnya.
* **Atomic State Mutation:** Penyimpanan riwayat idempoten harus terjadi di dalam transaksi atomik yang sama dengan mutasi bisnis lokal.

#### C. Claim-Check Pattern Internals

Broker pesan terdistribusi (Kafka, RabbitMQ) dioptimalkan untuk memproses pesan kecil (umumnya < 1 MB). Memaksa broker memproses payload besar (puluhan megabyte, misal dokumen PDF atau citra medis) menyebabkan memory bloat, GC pause yang tinggi, dan membebani throughput I/O jaringan broker.

```
[ Producer ] 
     |
     | 1. Upload Raw Payload (>1MB)
     v
+------------------------+
| Object Storage (S3/GCS)| <----+
+------------------------+      |
     |                          |
     | 2. Returns Payload Ref   | 4. Fetch Payload by Ref
     v                          |
[ Broker Message ]              |
  - ID: "msg-001"               |
  - Payload_Ref: "s3://..." ----+
     |
     | 3. Publish Light Metadata
     v
[ Apache Kafka ]
     |
     v
[ Consumer ]
```

---

### 4. Why & What

| Dimensi Arsitektur | Mengapa Dibutuhkan (Why) | Apa Solusi/Mekanismenya (What) |
| :--- | :--- | :--- |
| **Dual-Write Problem** | Menghindari kondisi race condition dan ketidakkonsistenan status (*inconsistent state*) ketika operasi write ke database berhasil namun publish ke broker gagal (atau sebaliknya). | **Transactional Outbox + CDC:** Menghapus kebutuhan dua sistem koordinasi transaksi, mendelegasikan propagasi ke stream processor berbasis WAL. |
| **Pesan Duplikat** | Jaringan TCP dan broker perpesanan berbasis *at-least-once* dapat mengirim ulang pesan yang sama ketika terjadi network partition atau kegagalan ACK. | **Idempotent Consumer:** Melindungi database dari mutasi ganda (misal: double-debit rekening) menggunakan verifikasi kunci unik deterministik. |
| **Payload Bloat** | Broker pesan mengalami degradasi performa drastis jika ukuran pesan melebihi batas optimum (umumnya > 1MB), menyebabkan OOM dan replikasi lambat. | **Claim-Check Pattern:** Memisahkan metadata kontrol (dikirim via event broker) dari data biner mentah (disimpan pada Object Storage). |
| **Spaghetti Protocol** | Integrasi antar subsistem sering kali mencampuradukkan protokol sinkron latensi rendah dengan pipeline batch/event streaming yang heterogen. | **Content-Based Dynamic Router:** Lapisan gateway/mediator yang menganalisis header payload untuk menentukan protokol transfer optimal secara runtime. |

---

### 5. How (Workflow Detail)

Berikut adalah tahapan operasional integrasi end-to-end dengan keandalan enterprise:

```
[Client]       [Order Service]          [PostgreSQL]             [Debezium]            [Kafka]             [Payment Service]
   |                  |                      |                       |                    |                        |
   | 1. POST /order   |                      |                       |                    |                        |
   |----------------->|                      |                       |                    |                        |
   |                  | 2. BEGIN TX          |                       |                    |                        |
   |                  |--------------------->|                       |                    |                        |
   |                  | 3. INSERT order      |                       |                    |                        |
   |                  | 4. INSERT outbox     |                       |                    |                        |
   |                  |--------------------->|                       |                    |                        |
   |                  | 5. COMMIT TX         |                       |                    |                        |
   |                  |--------------------->|                       |                    |                        |
   | 6. HTTP 201      |                      |                       |                    |                        |
   |<-----------------|                      |                       |                    |                        |
   |                  |                      |-- 7. Tail WAL Stream->|                    |                        |
   |                  |                      |   (pgoutput plugin)   |                    |                        |
   |                  |                      |                       | 8. Publish Message |                        |
   |                  |                      |                       |------------------->|                        |
   |                  |                      |                       |                    |-- 9. Poll Event ------>|
   |                  |                      |                       |                    |   (Trace Propagation)  |
   |                  |                      |                       |                    |                        |
   |                  |                      |                       |                    | 10. Check Redis Lock   |
   |                  |                      |                       |                    |     & Deduplication DB |
   |                  |                      |                       |                    |                        |
   |                  |                      |                       |                    | 11. Mutate & Dedupe TX |
   |                  |                      |                       |                    |                        |
   |                  |                      |                       |                    | 12. Commit Offset      |
   |                  |                      |                       |                    |<-----------------------|
```

1. **Inisiasi Klien:** Klien mengeksekusi request mutasi data ke `Order Service`.
2. **Kompilasi Transaksi Atomik:** `Order Service` membuka transaksi lokal database relasional.
3. **Persistensi State Bisnis:** Entitas order disimpan ke dalam tabel `orders`.
4. **Pencatatan Outbox:** Payload event bisnis beserta context tracing OpenTelemetry diserialisasi dan disimpan ke dalam tabel `outbox_events`.
5. **Komit Database:** Transaksi di-commit. Ketiadaan transaksi terdistribusi memastikan waktu eksekusi berorde single-digit milidetik.
6. **Respons Klien:** Klien menerima status sukses seketika (optimistic responsiveness).
7. **Deteksi Mutasi Engine CDC:** Debezium membaca log replikasi WAL PostgreSQL secara real-time tanpa membebani indeks atau memicu query polling `SELECT`.
8. **Forwarding ke Broker:** Mesin CDC mempublikasikan event ke topik `order-events` di Kafka dengan message key tertentu (misal: `order_id`) guna menjaga urutan partisi (*partition ordering*).
9. **Konsumsi Terdistribusi:** `Payment Service` menarik event dari Kafka dan mengekstrak konteks distributed tracing dari message header.
10. **Akuisisi Lock Idempotensi:** `Payment Service` mengecek ke cache cluster (Redis) menggunakan atomic `SET NX EX` untuk mencegah balapan antar thread konsumsi.
11. **Eksekusi Bisnis Idempoten:** Jika belum pernah diproses, logika bisnis dieksekusi di dalam transaksi database lokal bersamaan dengan pencatatan `event_id` ke dalam tabel `processed_events`.
12. **Offset Acknowledgment:** Offset partisi Kafka di-commit hanya setelah transaksi database lokal sukses. Jika terjadi kegagalan, offset tidak bergerak, memicu mekanisme retry otomatis atau pengalihan ke Dead Letter Queue (DLQ).

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata: Sistem Pengiriman Berharga dengan Safe Deposit Box

Bayangkan Anda mengirimkan emas batangan 100 kg melalui kurir pos standar yang hanya mampu membawa paket maksimal 2 kg:
1. **Masalah Ukuran (Claim-Check):** Jika Anda memaksa memasukkan 100 kg emas ke tas kurir motor, tas akan jebol dan motor rusak. Solusinya: Anda meletakkan emas tersebut di lemari besi aman (*Secure Safe Vault*) yang dapat diakses siapa pun yang memegang kuncinya.
2. **Klaim Tiket (Claim-Check Receipt):** Anda mengambil struk bukti simpan yang berisi nomor brankas dan kode otorisasi (berat kertas hanya 5 gram). Anda memberikan kertas ini ke kurir pos.
3. **Pencatatan Buku Kas (Transactional Outbox):** Anda tidak langsung menelepon penerima barang karena sinyal sering putus. Anda mencatat pengiriman ini di buku besar Anda sendiri. Asisten Anda (CDC) bertugas memantau buku besar tersebut dan mengirimkan surat konfirmasi saat ada waktu.
4. **Penerimaan Terverifikasi (Idempotent Consumer):** Penerima menerima surat konfirmasi dua kali karena kantor pos mengirimkan kurir cadangan. Penerima memeriksa buku registrasinya: jika nomor registrasi brankas sudah pernah diambil dan dicairkan, surat kedua langsung diarsipkan ke tong sampah tanpa mengambil ulang emas ke lemari besi.

#### Diagram Arsitektur Integrasi Heterogen (EIP Engine)

```
+---------------------------------------------------------------------------------------+
|                             ENTERPRISE INTEGRATION RUNTIME                            |
+---------------------------------------------------------------------------------------+

        +-----------------------+
        | Source Event Producer |
        +-----------+-----------+
                    | (Trace Context Injected)
                    v
    +---------------+---------------+
    | Content-Based Dynamic Router  |
    +---------------+---------------+
                    |
      +-------------+-------------+
      |                           |
(Payload > 1MB)            (Payload <= 1MB)
      |                           |
      v                           v
+---------------+         +---------------+
|  Claim-Check  |         | Direct Event  |
|  Transformer  |         |  Pipeline     |
+-------+-------+         +-------+-------+
        |                         |
        | [Put Object to S3]      |
        v                         |
  [ S3 Bucket ]                   |
        | (S3 URI Generated)      |
        +------------+            |
                     |            |
                     v            v
           +---------+------------+----------+
           |       Apache Kafka Topic        |
           |     (orders.v1.transactional)   |
           +-----------------+---------------+
                             |
                             v
               +-------------+-------------+
               |    Idempotent Consumer    |
               +-------------+-------------+
                             |
                   +---------+---------+
                   | Deduplication     |
                   | Engine            |
                   +----+---------+----+
                        |         |
             (Duplicate)|         |(Unique / New)
                        v         v
                 +--------+     +------------------------+
                 | Drop & |     | 1. Download from S3    |
                 |  ACK   |     |    (if Claim-Check)    |
                 +--------+     | 2. Execute Mutation    |
                                | 3. Record Idempotency  |
                                | 4. Commit Offset       |
                                +------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: In-Memory Idempotency Filter (Go)

Contoh dasar implementasi filter idempoten menggunakan in-memory cache dengan TTL dan Mutual Exclusion primitives.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

var ErrDuplicateEvent = errors.New("event duplicate detected: message already processed or in-flight")

type Event struct {
	ID        string
	Payload   string
	Timestamp time.Time
}

type MemoryIdempotencyFilter struct {
	mu      sync.RWMutex
	storage map[string]time.Time
	ttl     time.Duration
}

func NewMemoryIdempotencyFilter(ttl time.Duration) *MemoryIdempotencyFilter {
	return &MemoryIdempotencyFilter{
		storage: make(map[string]time.Time),
		ttl:     ttl,
	}
}

// CheckAndMark mengembalikan error jika event ID sudah ada dan belum expired.
func (f *MemoryIdempotencyFilter) CheckAndMark(ctx context.Context, eventID string) error {
	f.mu.Lock()
	defer f.mu.Unlock()

	now := time.Now()
	if exp, exists := f.storage[eventID]; exists {
		if now.Before(exp) {
			return ErrDuplicateEvent
		}
	}

	// Simpan eventID dengan waktu kadaluarsa
	f.storage[eventID] = now.Add(f.ttl)
	return nil
}

func main() {
	filter := NewMemoryIdempotencyFilter(5 * time.Second)
	ctx := context.Background()

	event := Event{
		ID:        "evt-ord-8891",
		Payload:   "ORDER_CREATED",
		Timestamp: time.Now(),
	}

	// Eksekusi 1: Sukses
	err := filter.CheckAndMark(ctx, event.ID)
	if err != nil {
		fmt.Printf("Execution 1 Failed: %v\n", err)
	} else {
		fmt.Printf("Execution 1 Success: Processing %s\n", event.ID)
	}

	// Eksekusi 2: Duplikat (Ditolak)
	err = filter.CheckAndMark(ctx, event.ID)
	if err != nil {
		fmt.Printf("Execution 2 Intercepted: %v\n", err)
	} else {
		fmt.Printf("Execution 2 Success: Processing %s\n", event.ID)
	}
}
```

---

#### B. Practical Example: Enterprise Transactional Outbox + Redis Distributed Idempotency (Go)

Implementasi tingkat produksi yang menangani:
1. Penyimpanan Outbox secara transaksional di PostgreSQL.
2. Konsumen idempoten menggunakan Redis Distributed Lock (Redlock algorithm style via atomic script) dan basis data transaksional.
3. Propagasi Context OpenTelemetry W3C.

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	trace "go.opentelemetry.io/otel/trace"
)

// Domain Models
type Order struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type OutboxEvent struct {
	ID            string            `json:"id"`
	AggregateType string            `json:"aggregate_type"`
	AggregateID   string            `json:"aggregate_id"`
	Type          string            `json:"type"`
	Payload       []byte            `json:"payload"`
	TraceHeaders  map[string]string `json:"trace_headers"`
	CreatedAt     time.Time         `json:"created_at"`
}

// OrderRepository handles atomic outbox insertion
type OrderRepository struct {
	db *sql.DB
}

func NewOrderRepository(db *sql.DB) *OrderRepository {
	return &OrderRepository{db: db}
}

// CreateOrderWithOutbox creates the order and stages the event in the outbox table within the same transaction.
func (r *OrderRepository) CreateOrderWithOutbox(ctx context.Context, order Order) error {
	tr := otel.Tracer("order-service")
	ctx, span := tr.Start(ctx, "OrderRepository.CreateOrderWithOutbox")
	defer span.End()

	// 1. Ekstraksi Context OpenTelemetry ke dalam Outbox Headers
	carrier := propagation.MapCarrier{}
	otel.GetTextMapPropagator().Inject(ctx, carrier)

	orderJSON, err := json.Marshal(order)
	if err != nil {
		return fmt.Errorf("failed to marshal order: %w", err)
	}

	outbox := OutboxEvent{
		ID:            uuid.NewString(),
		AggregateType: "ORDER",
		AggregateID:   order.ID,
		Type:          "ORDER_CREATED",
		Payload:       orderJSON,
		TraceHeaders:  carrier,
		CreatedAt:     time.Now().UTC(),
	}

	traceHeadersJSON, err := json.Marshal(outbox.TraceHeaders)
	if err != nil {
		return fmt.Errorf("failed to marshal trace headers: %w", err)
	}

	// 2. Transaksi Database Atomik Lokal
	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Simpan ke tabel orders
	orderQuery := `INSERT INTO orders (id, user_id, amount, status, created_at) VALUES ($1, $2, $3, $4, $5)`
	_, err = tx.ExecContext(ctx, orderQuery, order.ID, order.UserID, order.Amount, order.Status, order.CreatedAt)
	if err != nil {
		return fmt.Errorf("failed to insert order: %w", err)
	}

	// Simpan ke tabel outbox_events
	outboxQuery := `
		INSERT INTO outbox_events (id, aggregate_type, aggregate_id, event_type, payload, trace_headers, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`
	_, err = tx.ExecContext(ctx, outboxQuery, outbox.ID, outbox.AggregateType, outbox.AggregateID, outbox.Type, outbox.Payload, traceHeadersJSON, outbox.CreatedAt)
	if err != nil {
		return fmt.Errorf("failed to insert outbox event: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit outbox transaction: %w", err)
	}

	return nil
}

// EnterpriseIdempotentConsumer handles incoming messages with distributed lock and DB dedup
type EnterpriseIdempotentConsumer struct {
	redisClient *redis.Client
	db          *sql.DB
}

func NewEnterpriseIdempotentConsumer(rClient *redis.Client, db *sql.DB) *EnterpriseIdempotentConsumer {
	return &EnterpriseIdempotentConsumer{
		redisClient: rClient,
		db:          db,
	}
}

func (c *EnterpriseIdempotentConsumer) ProcessOrderEvent(ctx context.Context, msgData []byte) error {
	var event OutboxEvent
	if err := json.Unmarshal(msgData, &event); err != nil {
		return fmt.Errorf("poison pill message unmarshal failed: %w", err)
	}

	// 1. Rekonstruksi Distributed Tracing Context
	carrier := propagation.MapCarrier(event.TraceHeaders)
	extractedCtx := otel.GetTextMapPropagator().Extract(ctx, carrier)
	tr := otel.Tracer("consumer-service")
	extractedCtx, span := tr.Start(extractedCtx, "ProcessOrderEvent", trace.WithSpanKind(trace.SpanKindConsumer))
	defer span.End()

	lockKey := fmt.Sprintf("lock:event:%s", event.ID)
	dedupKey := fmt.Sprintf("dedup:event:%s", event.ID)

	// 2. Distributed Locking menggunakan Redis SET NX EX (Timeout 10 detik)
	acquired, err := c.redisClient.SetNX(extractedCtx, lockKey, "locked", 10*time.Second).Result()
	if err != nil {
		return fmt.Errorf("redis connection error during lock acquisition: %w", err)
	}
	if !acquired {
		return errors.New("concurrent processing detected, event is locked by another instance")
	}
	defer c.redisClient.Del(extractedCtx, lockKey)

	// 3. Pengecekan Duplikasi Cepat (Fast-path In-Memory Dedup Cache)
	exists, err := c.redisClient.Exists(extractedCtx, dedupKey).Result()
	if err != nil {
		return fmt.Errorf("redis error checking dedup key: %w", err)
	}
	if exists > 0 {
		span.AddEvent("Duplicate detected via Redis Cache. Skipping processing.")
		return nil // Acknowledged tanpa eksekusi ulang
	}

	// 4. Eksekusi Transaksi Bisnis + Database Dedup (Slow-path Guaranteed ACID)
	tx, err := c.db.BeginTx(extractedCtx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to begin consumer transaction: %w", err)
	}
	defer tx.Rollback()

	// Periksa tabel processed_events
	var processedID string
	err = tx.QueryRowContext(extractedCtx, "SELECT id FROM processed_events WHERE id = $1 FOR UPDATE", event.ID).Scan(&processedID)
	if err == nil {
		// Event sudah pernah diproses di DB
		c.redisClient.Set(extractedCtx, dedupKey, "processed", 24*time.Hour)
		return nil
	} else if !errors.Is(err, sql.ErrNoRows) {
		return fmt.Errorf("failed to query processed_events: %w", err)
	}

	// Eksekusi Logika Bisnis Konsumen
	var order Order
	if err := json.Unmarshal(event.Payload, &order); err != nil {
		return fmt.Errorf("failed to unmarshal order payload: %w", err)
	}

	// Contoh mutasi: Update alokasi stok atau invoice
	updateQuery := `INSERT INTO payments (id, order_id, amount, status, processed_at) VALUES ($1, $2, $3, $4, $5)`
	_, err = tx.ExecContext(extractedCtx, updateQuery, uuid.NewString(), order.ID, order.Amount, "SETTLED", time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to insert payment execution: %w", err)
	}

	// Catat ID ke processed_events
	insertDedup := `INSERT INTO processed_events (id, processed_at) VALUES ($1, $2)`
	_, err = tx.ExecContext(extractedCtx, insertDedup, event.ID, time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to insert dedup record: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit consumer transaction: %w", err)
	}

	// 5. Update Dedup Cache (TTL 24 jam)
	c.redisClient.Set(extractedCtx, dedupKey, "processed", 24*time.Hour)

	return nil
}

func main() {
	// Driver harness setup untuk verifikasi sintaksis dan arsitektur runtime
	fmt.Println("Enterprise Integration Patterns Engine initialized.")
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Settlement Multi-Bank Real-Time (Fintech Gateway)

* **Skala Sistem:** 45.000 Transaksi per Detik (TPS) pada jam puncak (*peak hour*), volume transaksi harian melampaui Rp 850 Miliar, terhubung dengan 14 API perbankan inti (*Core Banking*) yang menggunakan kombinasi ISO-8583, gRPC, dan REST/JSON.
* **Insiden Kegagalan Awal:**
  Sebelum implementasi pola modern, arsitektur menggunakan *Dual-Write Direct Publish* (Aplikasi menulis ke PostgreSQL lalu langsung melakukan publish ke Kafka topic via HTTP middleware). 
  Saat terjadi lonjakan beban (*flash sale*):
  1. Latensi commit database melonjak hingga 4.200 ms.
  2. Koneksi ke Kafka broker mengalami transient timeout.
  3. Klien menerima pesan error HTTP 500, namun transaksi bank sebenarnya telah berhasil dipotong di database lokal.
  4. Pengguna melakukan percobaan ulang transaksi (*retry spamming*), memicu insiden pendebetan ganda senilai Rp 3,2 Miliar dalam kurun waktu 12 menit sebelum sistem dinonaktifkan secara darurat.
* **Transformasi Solusi Arsitektur:**
  1. **Migrasi Outbox Berbasis WAL:** Mengganti direct publish dengan *Transactional Outbox Engine*. Tabel outbox di-partitioning secara harian (*declarative range partitioning*).
  2. **Debezium Cluster Deployment:** Tiga node Debezium terdistribusi membaca stream WAL dari logical replication slot PostgreSQL dengan format output serialisasi Protobuf terkompresi.
  3. **High-Throughput Deduplication Layer:** Menerapkan dua tahap verifikasi idempoten:
     * *Layer 1 (L1 Cache):* Redis Cluster (12 node sharded) dengan script Lua untuk atomic check-and-set token verifikasi (p99 latency < 1.2 ms).
     * *Layer 2 (L2 Persistence):* Tabel dedup partisi pada PostgreSQL dengan composite primary key `(event_id, tenant_id)`.
  4. **Dynamic Claim-Check Storage:** Payload transaksi di atas 256 KB secara otomatis dialihkan ke bucket MinIO/Ceph on-premise multi-region, hanya URI dan secure checksum SHA-256 yang dimasukkan ke pesan Kafka.
* **Metrik Hasil Pasca Implementasi:**
  * **Tingkat Kegagalan Integrasi Dual-Write:** 0% (Matematis tereliminasi oleh ACID outbox boundary).
  * **Double Debit Incident:** 0 insiden selama 18 bulan pengujian beban dan produksi.
  * **End-to-End Replication Latency:** Rata-rata 18 ms dari commit outbox PostgreSQL hingga diterima oleh event consumer Kafka.

---

### 9. Trade-offs

Setiap pola integrasi enterprise memiliki konsekuensi arsitektural yang signifikan terhadap performa, latensi, throughput, dan kompleksitas operasional:

| Pendekatan / Pola | Latensi (p99) | Throughput | Kompleksitas Infrastruktur | Jaminan Konsistensi | Biaya Operasional (Cost) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Dual-Write (Direct DB + Direct Broker)** | Sangat Rendah (5–15 ms) | Menengah | Sangat Rendah (Tanpa middleware tambahan) | **Tidak Ada** (Rentan Data Loss / Zombie Records) | Rendah (Tetapi risiko finansial akibat bug sangat tinggi) |
| **Two-Phase Commit (2PC / XA)** | Sangat Tinggi (> 500 ms, rentan blocking) | Buruk (< 1.000 TPS) | Ekstrem (Perlu XA Transaction Manager) | **Strong Consistency** | Tinggi (Membutuhkan database engine terspesialisasi) |
| **Transactional Outbox via CDC (Debezium + Kafka)** | Rendah–Menengah (20–60 ms) | Sangat Tinggi (> 100.000 TPS) | Tinggi (Butuh cluster Kafka Connect/Debezium, WAL tuning) | **Eventual Consistency** (Jaminan At-Least-Once Delivery) | Menengah–Tinggi (Storage WAL overhead, compute Kafka) |
| **Outbox via Polling Publisher (`SELECT FOR UPDATE SKIP LOCKED`)** | Tinggi (100–1.000 ms, tergantung interval polling) | Rendah–Menengah (< 5.000 TPS) | Rendah (Hanya worker service internal) | **Eventual Consistency** | Rendah (Menghabiskan CPU DB karena frekuensi query) |
| **Claim-Check Pattern (Object Store + Broker)** | Menengah (Tambahan 15–30 ms per RTT Object Storage) | Tinggi (Menghemat network bandwidth broker) | Menengah (Memerlukan Object Storage dengan lifecycle cleanup) | Mengikuti Broker (Payload konsisten via referensi immutable) | Efisien (Biaya storage S3 jauh lebih murah daripada RAM broker) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Outbox Table Bloat & Performance Degradation
* **Gejala:** Query aplikasi melambat drastis seiring waktu. Ukuran disk database meningkat tajam meskipun data utama sedikit.
* **Akar Masalah:** Developer lupa membuat mekanisme pembersihan (*purging/compaction*) pada tabel `outbox_events` setelah pesan diekstraksi ke Kafka. VACUUM PostgreSQL tidak sanggup mengejar frekuensi write/delete jutaan baris.
* **Solusi Arsitektur:** Terapkan database table partitioning bulanan/harian, lalu lakukan `TRUNCATE PARTITION` atau gunakan CDC berbasis WAL tanpa mengharuskan penghapusan row seketika via `DELETE` (gunakan ephemeral logical slots).

#### 2. Poison Pill Events & Infinite Crash Loops
* **Gejala:** Consumer service mengalami crash restart berulang kali (*CrashLoopBackOff* di Kubernetes), menyebabkan pembacaan partisi terhenti total (*Head-of-Line Blocking*).
* **Akar Masalah:** Pesan pada Kafka topic mengalami korupsi data atau ketidaksesuaian skema serialisasi (misal: JSON parsing error). Kode consumer melakukan panic dan menolak melakukan ACK/Offset Commit.
* **Solusi Arsitektur:** Pasang *Non-blocking Dead Letter Queue (DLQ)*. Tangkap deserialization error secara eksplisit, bypass pemrosesan bisnis, kirim pesan rusak ke topic `.DLQ` beserta header metadata error, lalu segera commit offset pesan tersebut.

#### 3. Out-of-Order Execution Akibat Concurrent Consumers
* **Gejala:** Event `ORDER_CANCELLED` dieksekusi lebih dulu sebelum event `ORDER_CREATED`, menyebabkan status order tidak valid di Read Model.
* **Akar Masalah:** Partisi Kafka tidak dikonfigurasi dengan Partition Key yang tepat (menggunakan round-robin default), atau consumer memproses pesan partisi yang sama menggunakan dynamic thread-pool internal tanpa partisi kunci memori.
* **Solusi Arsitektur:** Selalu tetapkan Partition Key berbasis Entitas Unik (misal: `tenant_id` atau `order_id`). Di sisi consumer, jika menggunakan konkurensi goroutine internal, routing pesan berdasarkan hash key ke antrean channel worker tertentu.

#### 4. Redis Idempotency Race Condition (Lock Expiry Pitfall)
* **Gejala:** Terjadi pemrosesan ganda pada pesan berat yang memakan waktu eksekusi lebih lama dari nilai TTL Distributed Lock.
* **Akar Masalah:** Eksekusi logika bisnis memakan waktu 12 detik, sedangkan TTL Redis lock diatur hanya 10 detik. Lock dilepas otomatis saat proses transaksi pertama masih berjalan, sehingga instance kedua dapat mengambil lock dan mengeksekusi mutasi.
* **Solusi Arsitektur:** Gunakan mekanisme *Heartbeat Lock Renewal* (seperti algoritma Redisson watchdog) yang memperpanjang sewa lock secara otomatis selama goroutine pemrosesan masih aktif, atau buat boundary transaksi terisolasi secara deterministik pada database ACID L2.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist arsitektural ini sebelum merilis sistem integrasi ke lingkungan produksi:

- [ ] **Data Integrity & Consistency**
  - [ ] Seluruh penulisan status eksternal diisolasi menggunakan Transactional Outbox Pattern di dalam boundary transaksi lokal.
  - [ ] Tidak ada dependensi direct network I/O (HTTP/gRPC/Third-party) di dalam blok transaksi database ACID.
  - [ ] Tabel outbox dan dedup menggunakan skema partisi deklaratif (*Declarative Range Partitioning*).
- [ ] **Idempotency & Concurrency**
  - [ ] Menggunakan skema compound dedup key: `{tenant_id}:{entity_type}:{entity_id}:{event_version}`.
  - [ ] Mekanisme lock terdistribusi dilengkapi dengan dynamic heartbeat renewal atau batas aman timeout (safety margins).
  - [ ] Database idempotency check menggunakan klausul `INSERT ... ON CONFLICT DO NOTHING` atau `FOR UPDATE` lock.
- [ ] **Observability & Tracing**
  - [ ] Konteks W3C TraceContext (`traceparent`, `tracestate`) diinjeksi ke dalam header Kafka/Message Broker.
  - [ ] Metric latensi pelacakan end-to-end (waktu sejak event dibuat di database outbox hingga dieksekusi di konsumen) dipantau via Prometheus gauge.
  - [ ] Alerting terpasang untuk Consumer Group Lag yang melampaui ambang batas SLO.
- [ ] **Resilience & Scalability**
  - [ ] DLQ (Dead Letter Queue) terkonfigurasi dengan mekanisme manual/automated replay pipeline.
  - [ ] Circuit breaker dan exponential backoff dengan full jitter diterapkan pada seluruh interkoneksi protokol sinkron.
  - [ ] Batas ukuran payload broker pesan dijaga ketat (< 1MB) menggunakan enforce schema registry dan Claim-Check pattern.

---

### 12. Hands-on Practice

Praktikum ini akan menuntun Anda membangun pipeline end-to-end: PostgreSQL Transactional Outbox, Mock CDC Worker, dan Idempotent Consumer yang terintegrasi dengan Redis.

#### Direktori Kerja: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/scripts
cd hands-on/m02/
```

#### File 1: `docker-compose.yml`
Simpan konfigurasi cluster lokal:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    container_name: m02-postgres
    environment:
      POSTGRES_USER: enterprise_user
      POSTGRES_PASSWORD: secretpassword
      POSTGRES_DB: enterprise_db
    ports:
      - "5432:5432"
    volumes:
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    container_name: m02-redis
    ports:
      - "6379:6379"
```

#### File 2: `scripts/init.sql`
Inisialisasi skema basis data outbox dan konsumsi:

```sql
CREATE TABLE orders (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE outbox_events (
    id VARCHAR(64) PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE processed_events (
    id VARCHAR(64) PRIMARY KEY,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customer_balance (
    user_id VARCHAR(64) PRIMARY KEY,
    balance NUMERIC(15, 2) NOT NULL
);

-- Seed Initial Balance
INSERT INTO customer_balance (user_id, balance) VALUES ('usr-100', 5000000.00);
```

#### File 3: `go.mod`
Inisialisasi dependensi modul:

```text
module hands-on/m02

go 1.21

require (
	github.com/google/uuid v1.4.0
	github.com/lib/pq v1.10.9
	github.com/redis/go-redis/v9 v9.3.0
)
```

#### File 4: `main.go`
Aplikasi pipeline lengkap yang memicu skenario Outbox dan mengonsumsinya secara idempoten:

```go
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
)

const (
	pgDSN    = "postgres://enterprise_user:secretpassword@localhost:5432/enterprise_db?sslmode=disable"
	redisDSN = "localhost:6379"
)

type OrderCreatedPayload struct {
	OrderID string  `json:"order_id"`
	UserID  string  `json:"user_id"`
	Amount  float64 `json:"amount"`
}

func main() {
	ctx := context.Background()

	// 1. Setup Database & Cache Connection
	db, err := sql.Open("postgres", pgDSN)
	if err != nil {
		log.Fatalf("Postgres Connection Error: %v", err)
	}
	defer db.Close()

	rdb := redis.NewClient(&redis.Options{Addr: redisDSN})
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis Connection Error: %v", err)
	}

	fmt.Println("=== STEP 1: Memulai Transaksi Outbox Lokal ===")
	orderID := "ord-" + uuid.NewString()[:8]
	eventID := "evt-" + uuid.NewString()[:8]
	userID := "usr-100"
	orderAmount := 250000.00

	// Simulasikan Pembuatan Order + Outbox Atomik
	err = createOrderTransactional(ctx, db, orderID, eventID, userID, orderAmount)
	if err != nil {
		log.Fatalf("Gagal membuat Order dan Outbox: %v", err)
	}
	fmt.Printf("[OK] Order %s dan Event %s berhasil di-commit secara atomik.\n", orderID, eventID)

	fmt.Println("\n=== STEP 2: Simulai CDC Engine Membaca Outbox & Dispatch ===")
	// Membaca outbox yang belum diproses
	eventPayload, err := fetchAndMarkOutbox(ctx, db, eventID)
	if err != nil {
		log.Fatalf("Gagal membaca outbox: %v", err)
	}

	fmt.Println("\n=== STEP 3: Simulasi Konkurensi Ekstrem (Duplikasi Pengiriman) ===")
	// Kita akan memanggil fungsi konsumsi dua kali secara paralel dengan event yang SAMA
	var wg sync.WaitGroup
	for i := 1; i <= 2; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			err := processEventWithIdempotency(ctx, workerID, db, rdb, eventID, eventPayload)
			if err != nil {
				fmt.Printf("[Worker-%d] Error: %v\n", workerID, err)
			} else {
				fmt.Printf("[Worker-%d] Eksekusi Sukses / Ditangani secara Aman.\n", workerID)
			}
		}(i)
	}
	wg.Wait()

	fmt.Println("\n=== STEP 4: Verifikasi Integritas Data Akhir ===")
	verifyFinalBalance(ctx, db, userID)
}

func createOrderTransactional(ctx context.Context, db *sql.DB, orderID, eventID, userID string, amount float64) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// Insert Order
	_, err = tx.ExecContext(ctx, "INSERT INTO orders (id, user_id, amount, status) VALUES ($1, $2, $3, $4)",
		orderID, userID, amount, "PENDING")
	if err != nil {
		return err
	}

	payloadData, _ := json.Marshal(OrderCreatedPayload{OrderID: orderID, UserID: userID, Amount: amount})

	// Insert Outbox
	_, err = tx.ExecContext(ctx, `
		INSERT INTO outbox_events (id, aggregate_type, aggregate_id, event_type, payload, processed) 
		VALUES ($1, $2, $3, $4, $5, $6)`,
		eventID, "ORDER", orderID, "ORDER_CREATED", payloadData, false)
	if err != nil {
		return err
	}

	return tx.Commit()
}

func fetchAndMarkOutbox(ctx context.Context, db *sql.DB, eventID string) ([]byte, error) {
	var payload []byte
	err := db.QueryRowContext(ctx, "SELECT payload FROM outbox_events WHERE id = $1", eventID).Scan(&payload)
	if err != nil {
		return nil, err
	}

	// Update status processed
	_, err = db.ExecContext(ctx, "UPDATE outbox_events SET processed = TRUE WHERE id = $1", eventID)
	return payload, err
}

func processEventWithIdempotency(ctx context.Context, workerID int, db *sql.DB, rdb *redis.Client, eventID string, payload []byte) error {
	lockKey := fmt.Sprintf("lock:evt:%s", eventID)

	// Distributed Lock via Redis (TTL 5 detik)
	acquired, err := rdb.SetNX(ctx, lockKey, workerID, 5*time.Second).Result()
	if err != nil {
		return fmt.Errorf("redis failure: %w", err)
	}
	if !acquired {
		return fmt.Errorf("concurrency collision: worker gagal mengakuisisi lock, event sedang diproses")
	}
	defer rdb.Del(ctx, lockKey)

	// L2 DB Check: Apakah event sudah pernah dieksekusi?
	var exists string
	err = db.QueryRowContext(ctx, "SELECT id FROM processed_events WHERE id = $1", eventID).Scan(&exists)
	if err == nil {
		fmt.Printf("[Worker-%d] FAST-DROP: Event %s terdeteksi duplikat di DB.\n", workerID, eventID)
		return nil
	} else if err != sql.ErrNoRows {
		return fmt.Errorf("db error: %w", err)
	}

	// Eksekusi Pemotongan Saldo di dalam Transaksi ACID
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	var data OrderCreatedPayload
	if err := json.Unmarshal(payload, &data); err != nil {
		return err
	}

	// Kurangi saldo
	res, err := tx.ExecContext(ctx, "UPDATE customer_balance SET balance = balance - $1 WHERE user_id = $2 AND balance >= $1",
		data.Amount, data.UserID)
	if err != nil {
		return err
	}
	rows, _ := res.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("insufficient balance or invalid user")
	}

	// Catat bahwa event sudah selesai diproses
	_, err = tx.ExecContext(ctx, "INSERT INTO processed_events (id) VALUES ($1)", eventID)
	if err != nil {
		return err
	}

	if err := tx.Commit(); err != nil {
		return err
	}

	fmt.Printf("[Worker-%d] SUCCESS: Saldo berhasil dipotong untuk Order %s.\n", workerID, data.OrderID)
	return nil
}

func verifyFinalBalance(ctx context.Context, db *sql.DB, userID string) {
	var balance float64
	err := db.QueryRowContext(ctx, "SELECT balance FROM customer_balance WHERE user_id = $1", userID).Scan(&balance)
	if err != nil {
		log.Fatalf("Gagal membaca saldo: %v", err)
	}
	fmt.Printf("Status Saldo Akhir Customer %s: Rp %.2f (Ekspektasi: Rp 4750000.00)\n", userID, balance)
}
```

#### Cara Menjalankan:
```bash
# 1. Jalankan container dependensi
docker-compose up -d

# Tunggu database siap (~5 detik)
sleep 5

# 2. Download library Go
go mod tidy

# 3. Eksekusi Program
go run main.go

# 4. Bersihkan lingkungan setelah selesai
docker-compose down -v
```

---

### 13. Exercise

Selesaikan latihan arsitektural berikut untuk memperkuat implementasi integrasi Anda:

#### Level Easy
Ubah implementasi `EnterpriseIdempotentConsumer` pada modul ini agar mencatat metrik latensi proses ke stdout. Jika waktu proses antara pembuatan event (`outbox.created_at`) hingga konsumsi selesai melampaui 1.000 ms, cetak log peringatan tingkat `WARN` yang menandakan potensi *lagging*.

#### Level Medium
Tambahkan mekanisme **Dead Letter Queue (DLQ)** lokal ke fungsi konsumsi:
* Modifikasi skema basis data untuk menambahkan tabel `dead_letter_events (id, original_payload, error_reason, failed_at)`.
* Jika parsing JSON payload mengalami kegagalan fatal (misal disuntik data rusak sengaja: `{"invalid-json"`), tangkap error tersebut, insert ke tabel `dead_letter_events`, dan kembalikan error `nil` ke runner utama agar offset pesan tidak tertahan.

#### Level Hard
Rancang komponen **Claim-Check Transformer Engine** modular menggunakan interface Go:
* Buat interface `PayloadStore` dengan method `Put(ctx, key, reader) (uri string, err)` dan `Get(ctx, uri) (io.ReadCloser, err)`.
* Implementasikan dua provider: `FilesystemPayloadStore` (untuk local disk/NFS) dan simulasi `S3PayloadStore`.
* Modifikasi outbox publisher agar memeriksa `len(payload)`. Jika ukuran melebihi 64 KB, simpan payload ke `PayloadStore`, hapus field isi biner pada pesan outbox, lalu sisipkan field `claim_check_uri: "s3://..."`. Konsumen harus secara transparan mengunduh kembali payload mentah sebelum memanggil handler bisnis.

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Anda adalah Principal Architect pada perusahaan Logistik Global yang menangani pelacakan paket kargo melintasi 3 Region AWS (Singapura, Frankfurt, Virginia). Sistem Anda memproses event telemetri IoT berukuran masif (120.000 event/detik) dengan variasi latensi satelit maritim yang ekstrem (koneksi kapal sering offline selama 6 jam lalu membanjiri broker dengan burst data terakumulasi yang out-of-order).

**Batasan Masalah:**
1. Event pelacakan mengandung status koordinat fisik kapal dan kondisi kontainer pendingin (*temperature-sensitive payload*).
2. Broker lokal di kapal mengumpulkan data secara offline, kemudian memancarkannya kembali ke cloud saat koneksi satelit online.
3. Event tiba di Kafka Cloud secara tidak berurutan (*out-of-order delivery*). Event versi lama dapat tiba beberapa jam setelah event versi baru berhasil diproses.
4. Anda dilarang menolak event lama karena data riwayat rute harus lengkap (*no data loss*), tetapi state terkini dari kontainer pada dashboard operasional **TIDAK BOLEH** tertimpa (*overwritten*) oleh event lama yang tiba terlambat.
5. Biaya egress transfer data antar-region AWS sangat mahal, sehingga replikasi data mentah melintasi region dilarang.

**Tugas Arsitektur:**
1. Rancang arsitektur integrasi sistem yang menjamin:
   * Eventual consistency antar Region.
   * State resolution menggunakan teknik *Conflict-Free Replicated Data Types (CRDT)* atau *Vector Clocks / Lamport Timestamps*.
   * Skema Dynamic Routing berbasis metadata geografis.
2. Buat dokumen spesifikasi teknis ringkas (dalam bentuk rancangan diagram alur pesan ASCII dan pemetaan skema event) yang menjelaskan bagaimana sistem Anda mencegah regresi status terkini (*state regression*) tanpa membebani database dengan distributed lock multi-region.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (5 Pertanyaan)

1. **Apa perbedaan mendasar antara *at-least-once delivery* dan *exactly-once processing*?**
   * A. At-least-once menjamin data dikirim tanpa duplikasi, sedangkan exactly-once mengizinkan duplikasi terkontrol.
   * B. At-least-once menjamin pesan tidak pernah hilang tetapi dapat terduplikasi; exactly-once processing adalah kombinasi at-least-once broker delivery dengan penanganan deduplikasi idempoten pada level aplikasi.
   * C. At-least-once hanya berjalan pada protokol HTTP, sedangkan exactly-once membutuhkan broker Kafka.
   * D. Exactly-once dijamin penuh secara native oleh seluruh protokol TCP tanpa modifikasi logika software.
   * *Jawaban:* **B**. Broker terdistribusi secara fisik hanya mampu menjamin at-least-once secara efisien; pemrosesan exactly-once dicapai melalui logika aplikasi yang idempoten.

2. **Mengapa *Dual-Write Direct Publish* (menulis ke database lalu mengirim ke message broker secara berurutan) dianggap anti-pattern pada distributed systems?**
   * A. Karena memakan bandwidth jaringan dua kali lipat.
   * B. Karena tidak adanya transaksi atomik melintasi batas database dan network broker memicu kegagalan parsial: salah satu operasi dapat berhasil sementara yang lain gagal, memicu inkonsistensi status sistem.
   * C. Karena Kafka tidak mendukung payload JSON dari database relasional.
   * D. Karena memicu crash instan pada PostgreSQL WAL engine.
   * *Jawaban:* **B**. Masalah mendasar dual-write adalah ketiadaan atomisitas; jika aplikasi mati di antara dua operasi tersebut, data akan hilang dari broker atau tersimpan sebagai *ghost record* di DB.

3. **Bagian internal PostgreSQL manakah yang dibaca oleh CDC Engine modern seperti Debezium?**
   * A. Shared Buffer Pool
   * B. Write-Ahead Log (WAL) melalui modul Logical Decoding
   * C. Temporary Tablespace
   * D. Query Plan Cache Engine
   * *Jawaban:* **B**. CDC engine terhubung ke logical replication slots dan membaca stream perubahan data dari WAL tanpa mengeksekusi query `SELECT` yang membebani query planner.

4. **Tujuan utama implementasi *Claim-Check Pattern* adalah...**
   * A. Mengamankan password pengguna di dalam database relasional.
   * B. Mencegah degradasi performa dan memory bloat pada broker perpesanan dengan memisahkan payload biner besar ke Object Storage.
   * C. Mengubah protokol Kafka menjadi gRPC secara otomatis.
   * D. Menghindari kebutuhan distributed tracing pada microservices.
   * *Jawaban:* **B**. Pola Claim-Check menjaga message broker tetap memproses metadata ringan, sedangkan payload besar dialihkan ke distributed object store yang lebih hemat biaya dan skalabel.

5. **Apa fungsi perintah atomic `SETNX` pada Redis dalam konteks consumer idempoten?**
   * A. Menghapus seluruh cache yang kadaluarsa.
   * B. Mengatur nilai key hanya jika key tersebut belum ada (*Set if Not eXists*), bertindak sebagai mutual-exclusion distributed lock.
   * C. Mengenkripsi payload JSON sebelum dikirim ke database.
   * D. Menghubungkan Redis ke cluster PostgreSQL.
   * *Jawaban:* **B**. `SETNX` menyediakan mutual exclusion primitif berkecepatan tinggi untuk mencegah eksekusi serentak atas event yang identik.

---

#### B. Intermediate (5 Pertanyaan)

6. **Mengapa implementasi Outbox Polling Publisher menggunakan `SELECT ... FOR UPDATE` sederhana dapat memicu bottleneck konkurensi di database?**
   * A. Karena PostgreSQL tidak mendukung isolasi transaksi saat polling.
   * B. Karena row locking tradisional memblokir thread worker lain yang mencoba membaca batch berikutnya; solusinya adalah menggunakan `SKIP LOCKED`.
   * C. Karena query SELECT mengubah hak akses file disk WAL.
   * D. Karena memicu pembacaan berulang pada Dead Letter Queue.
   * *Jawaban:* **B**. Tanpa klausul `SKIP LOCKED`, seluruh worker polling akan memperebutkan lock pada row yang sama, menurunkan throughput secara drastis (*lock contention*).

7. **Pada distributed tracing (OpenTelemetry), komponen apa yang bertugas menyuntikkan dan mengekstrak ID trace antar protokol jaringan heterogen (misal dari HTTP header ke Kafka record header)?**
   * A. Tracer Provider
   * B. TextMapPropagator
   * C. Sampling Filter
   * D. OTLP Exporter
   * *Jawaban:* **B**. `TextMapPropagator` bertanggung jawab membaca dan menulis metadata konteks (`traceparent`) melintasi batas serialisasi array byte atau header jaringan.

8. **Bagaimana cara mencegah memory leak atau unbounded table growth pada tabel `processed_events` (deduplication store)?**
   * A. Menghapus tabel tersebut secara manual setiap sistem restart.
   * B. Mengatur retensi data menggunakan table partitioning berbasis waktu dengan `DROP PARTITION` berkala, atau mengandalkan primary storage di Redis dengan TTL otomatis.
   * C. Menghindari indexing pada kolom primary key event_id.
   * D. Mengalihkan database dari PostgreSQL ke SQLite.
   * *Jawaban:* **B**. Data idempoten hanya perlu disimpan sepanjang *maximum replay window* broker (misal 7 atau 14 hari); setelah itu partisi lama dapat di-drop secara aman untuk mencegah pembengkakan disk.

9. **Apa risiko arsitektur jika batas TTL Redis distributed lock disetel terlalu rendah dibandingkan durasi pemrosesan bisnis?**
   * A. Transaksi database lokal otomatis dibatalkan oleh kernel OS.
   * B. Lock kedaluwarsa sebelum eksekusi selesai, membuka celah bagi worker lain untuk memproses event yang sama secara konkuren, merusak jaminan idempoten.
   * C. Redis kehabisan memori secara permanen.
   * D. Kafka secara otomatis menghapus topic yang bersangkutan.
   * *Jawaban:* **B**. Jika sewa lock berakhir sebelum proses mutasi tuntas, thread kedua dapat menganggap sistem idle dan mengeksekusi duplikasi mutasi secara simultan.

10. **Dalam implementasi Content-Based Router, atribut manakah yang paling ideal dianalisis untuk menentukan keputusan routing performa tinggi?**
    * A. Melakukan deep inspection parsing terhadap seluruh payload body terenkripsi.
    * B. Memeriksa metadata pada protocol headers (misal: Kafka Record Headers atau HTTP Headers) tanpa melakukan deserialisasi terhadap keseluruhan body payload.
    * C. Menyimpan body pesan ke hard disk lokal terlebih dahulu.
    * D. Menunggu ACK dari semua consumer hilir sebelum merutekan pesan.
    * *Jawaban:* **B**. Membaca header protocol menghindari beban komputasi CPU akibat deserialisasi unmarshal JSON/Protobuf penuh pada layer gateway/routing mediator.

---

#### C. Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario:** Tim engineering Anda melaporkan bahwa konsumen event pembayaran mendadak berhenti memproses antrean pesan (consumer lag melonjak tajam). Log menunjukkan adanya error `json: cannot unmarshal string into Go struct field .amount of type float64` yang terjadi berulang-ulang tanpa henti pada offset partisi yang sama.
    * **Pertanyaan Arsitektural:** Apa diagnosis Anda dan solusi apa yang harus diimplementasikan segera tanpa mengorbankan integritas data?
    * **Kunci Solusi & Analisis:**
      * *Diagnosis:* Sistem mengalami insiden **Poison Pill Event** (pesan dengan skema cacat masuk ke topik). Consumer tidak menangkap error deserialisasi dan menolak memindahkan offset Kafka, sehingga partisi macet total (*Head-of-Line Blocking*).
      * *Solusi Segera:* Implementasikan penanganan error fatal pada deserializer. Ekstrak pesan rusak mentah tersebut, inject context header berisi error stack trace, kirim langsung ke **Dead Letter Queue (DLQ) Topic**, lalu commit offset pesan pada partisi utama agar aliran antrean normal dapat berlanjut.

12. **Skenario:** Sebuah startup e-commerce mengimplementasikan Outbox Pattern dengan CDC Debezium. Namun, pada saat event promosi besar, Debezium tertinggal (lag WAL mencapai 120 GB), memicu habisnya ruang disk penyimpanan database utama PostgreSQL yang hampir menyebabkan database mengalami crash fatal (*out-of-disk downtime*).
    * **Pertanyaan Arsitektural:** Mengapa WAL PostgreSQL menumpuk saat CDC tertinggal, dan mekanisme mitigasi preventif apa yang harus diaktifkan?
    * **Kunci Solusi & Analisis:**
      * *Akar Masalah:* PostgreSQL **Logical Replication Slots** secara default menahan penghapusan WAL disk sampai slot replikasi (Debezium) mengonfirmasi bahwa LSN (Log Sequence Number) tersebut telah terbaca. Jika Debezium lambat, WAL akan terus bertambah tanpa batas.
      * *Mitigasi:* Konfigurasi parameter PostgreSQL `max_slot_wal_keep_size` (misal 20GB). Jika lag Debezium melampaui batas ini, database akan membatalkan replication slot demi melindungi ketersediaan database utama dari crash disk out-of-space, sembari memicu alert darurat untuk re-snapshotting Debezium.

13. **Skenario:** Dua transaksi pembayaran dengan payload identik masuk ke payment consumer dalam selang waktu 2 milidetik pada thread yang berbeda. Sistem menggunakan Redis lock untuk idempoten. Namun, kedua worker lolos dari pemeriksaan idempoten dan memotong saldo user dua kali. Log menunjukkan worker kedua memperoleh lock **setelah** worker pertama selesai memeriksa tabel dedup, tetapi **sebelum** worker pertama berhasil menyelesaikan `tx.Commit()` pemotongan saldo.
    * **Pertanyaan Arsitektural:** Mengapa kegagalan konkurensi ini terjadi, dan bagaimana memperbaiki boundary transaksinya?
    * **Kunci Solusi & Analisis:**
      * *Akar Masalah:* Terjadi *Time-of-Check to Time-of-Use (TOCTOU)* race condition. Worker pertama melepaskan lock Redis sebelum transaksi DB lokal di-commit, atau distributed lock tidak mencakup keseluruhan siklus hidup transaksi database lokal.
      * *Solusi:* Pastikan Distributed Lock Redis dipertahankan (*held*) hingga transaksi ACID database lokal benar-benar tuntas (`tx.Commit()`). Sebagai pertahanan lapis kedua (*defense-in-depth*), tambahkan constraint unik database `UNIQUE(event_id)` pada tabel mutasi atau tabel dedup lokal, sehingga jika terjadi kebocoran lock, level isolasi database relasional akan menolak insert kedua dengan error *unique constraint violation*.

---

### 16. Summary

1. **Eliminasi Dual-Write:** Mengandalkan propagasi jaringan ganda tanpa transaksi terdistribusi adalah sumber utama inkonsistensi data. Kombinasi **Transactional Outbox Pattern** dan **Change Data Capture (CDC)** mengubah mutasi multi-sistem menjadi satu transaksi atomik lokal yang aman.
2. **Kenyataan Jaringan Terdistribusi:** Jaringan fisik tidak pernah menjamin pengiriman pesan tepat satu kali (*exactly-once*). Semua integrasi asinkron harus berasumsi bahwa pengiriman berulang (*duplicate delivery*) adalah keniscayaan dan wajib ditangani oleh **Idempotent Consumer**.
3. **Pemisahan Jalur Kontrol dan Jalur Data:** Message Broker harus diperlakukan sebagai pipa transmisi event yang ramping. Memindahkan muatan biner besar ke Object Store menggunakan **Claim-Check Pattern** melindungi kapasitas I/O memory dan memastikan kestabilan broker pada throughput tinggi.
4. **Resiliensi Berlapis (Defense-in-Depth):** Sistem integrasi enterprise yang tangguh menggabungkan in-memory distributed locking (Redis), database ACID dedup