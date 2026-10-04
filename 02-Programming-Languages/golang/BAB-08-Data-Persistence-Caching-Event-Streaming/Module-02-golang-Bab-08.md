# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Data Persistence, Caching & Event Streaming**  
**Kategori: 02-Programming-Languages (Golang)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer tingkat lanjut diharapkan mampu:

1. **Menganalisis dan Mengoptimalkan Connection Pool Engine**: Membedah dan mengonfigurasi mekanisme internal connection pooling pada driver database Go (`database/sql` dan `jackc/pgx/v5/pgxpool`) untuk mencegah *connection starvation*, *leakage*, dan bottleneck konkurensi di bawah beban tinggi (high-throughput).
2. **Merancang Pola Caching Resilien Tingkat Produksi**: Mengimplementasikan arsitektur *Cache-Aside* multi-tier terdistribusi menggunakan Redis yang kebal terhadap *Cache Stampede* (menggunakan `golang.org/x/sync/singleflight`), *Cache Penetration*, dan *Cache Avalanche*, serta menerapkan *Distributed Mutex* berbasis Lua script atomik.
3. **Mengeliminasi Fenomena Dual-Write Problem**: Mengimplementasikan pola *Transactional Outbox Pattern* secara atomik bersamaan dengan mutasi domain database relasional, memanfaatkan Change Data Capture (CDC) atau poller asinkron berkecepatan tinggi menuju Apache Kafka/RabbitMQ.
4. **Membangun Konsumen Event-Driven Idempoten**: Merancang Kafka Consumer Group yang tangguh dengan pengelolaan commit offset manual, *at-least-once processing semantics*, *Dead Letter Queue* (DLQ), dan mekanisme deduplikasi transaksi idempotensi menggunakan key penyimpanan terdistribusi.
5. **Mengintegrasikan Observabilitas End-to-End**: Menyematkan metrik OpenTelemetry/Prometheus dan distributed tracing ke dalam layer persistensi, caching, dan pipeline event streaming.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam tentang:

*   **Go Concurrency Model**: Goroutines, channels, sinkronisasi primitif (`sync.Mutex`, `sync.RWMutex`, `sync.WaitGroup`, `sync/atomic`), dan propagasi `context.Context` (pembatalan, timeout, deadline).
*   **Go Memory Model & Escape Analysis**: Alokasi stack vs heap, pointer lifecycle, dan dampak alokasi memori terhadap latensi Garbage Collector (GC).
*   **Basis Data Relasional & Transaksional ACID**: PostgreSQL isolation levels (*Read Committed*, *Repeatable Read*, *Serializable*), Locking mechanisms (*Row-level locks*, *Advisory locks*, *Optimistic vs Pessimistic Locking*).
*   **Jaringan & Protokol Dasar**: TCP/IP socket connection, multiplexing, pooling, protokol RESP (Redis Serialization Protocol), dan Kafka wire protocol.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi dan Siklus Hidup `database/sql` vs `pgxpool`

Mekanisme standar `database/sql` di Go tidak secara langsung membuka satu koneksi fisik ke server database pada saat `sql.Open()` dieksekusi. `sql.Open()` hanya memvalidasi driver dan argumen string DSN, lalu menginisialisasi objek struct `sql.DB`.

```
                  ┌────────────────────────────────────────┐
                  │                 sql.DB                 │
                  │                                        │
                  │  ┌──────────────┐    ┌──────────────┐  │
Request Conn ────►│  │  freeConn    │    │  connRequest │  │
                  │  │  []*driverConn│   │  chan connReq│  │
                  │  └──────┬───────┘    └──────▲───────┘  │
                  └─────────┼───────────────────┼──────────┘
                            │ (If Available)    │ (If Pool Exhausted & MaxOpen reached)
                            ▼                   │
                     Return Conn         Queue Request (Wait for freeConn / Context Timeout)
```

Di dalam struct internal `sql.DB`, terdapat field kritis berikut:
*   `freeConn []*driverConn`: Slice yang menyimpan koneksi idle siap pakai.
*   `connRequests map[uint64]chan connRequest`: Map queue yang menampung goroutine yang terblokir menunggu koneksi bebas ketika limit `MaxOpenConns` tercapai.
*   `numOpen int`: Penghitung (*counter*) total koneksi aktif (digunakan + idle).
*   `mu sync.Mutex`: Mutex tunggal yang memproteksi seluruh operasi peminjaman (`conn`), pengembalian (`putConn`), dan pembukaan koneksi fisik baru (`openNewConnection`).

**Bottleneck `database/sql` Mutex Contention:**  
Ketika ribuan goroutine meminjam dan mengembalikan koneksi secara simultan, perebutan kunci `sql.DB.mu` menjadi titik kemacetan (contention hotspot). Alternatif produksi untuk PostgreSQL dengan throughput tinggi adalah driver `jackc/pgx/v5/pgxpool`. 

`pgxpool` membagi (*sharding*) internal state pool atau meminimalkan penggunaan central lock menggunakan kombinasi channel lock-free dan resource pool berkinerja tinggi, sehingga menawarkan latensi akuisisi koneksi yang jauh lebih stabil pada konkurensi ekstrem.

### 3.2 Redis Protocol (RESP), Pipeline, dan Distributed Lock Mutex

Redis memproses perintah dalam model single-threaded event loop berbasis I/O multiplexing (`epoll`/`kqueue`). 

#### Redis Pipelining Internal
Pada komunikasi sinkron standar (Request-Response), latensi total transaksi dipengaruhi secara dominan oleh Network Round Trip Time (RTT). Jika client mengeksekusi 100 perintah secara berurutan tanpa pipeline:
$$\text{Total Latency} = 100 \times \text{RTT} + 100 \times \text{Execution Time}$$

Dengan **Redis Pipelining**, client mengirimkan sekumpulan perintah ke socket buffer client tanpa menunggu balasan dari perintah sebelumnya. Engine Redis membaca paket-paket perintah dari TCP socket buffer, mengeksekusinya satu per satu di memori, dan mengantrekan output balasan ke dalam socket buffer kernel server untuk dikirim kembali dalam batch tunggal. Ini mereduksi latensi menjadi:
$$\text{Total Latency} \approx (1 \times \text{RTT}) + \sum \text{Execution Time}$$

#### Distributed Lock via Lua Script
Implementasi primitif `SETNX` (SET if Not eXists) tidak cukup untuk sistem enterprise jika proses akuisisi, validasi token kepemilikan, dan pelepasan kunci tidak atomik. 

```
Client A: Acquires Lock (TTL: 5s, Token: "uuid-A")
   │
   ▼
[Long Garbage Collection Pause / Heavy I/O: 6s]
   │
   ├─► TTL Expired in Redis!
   │   Client B: Acquires Lock (TTL: 5s, Token: "uuid-B")
   ▼
Client A Resumes: Deletes Lock (Without checking token -> ACCIDENTALLY DELETES CLIENT B's LOCK!)
```

Untuk menjamin pelepasan kunci atomik, Redis mewajibkan eksekusi Lua script:
```lua
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```
Lua script dieksekusi secara atomik dalam engine Redis; tidak ada perintah lain yang dapat menyela eksekusi script ini.

### 3.3 Event-Driven Architecture & The Dual-Write Problem

Masalah *Dual-Write* terjadi ketika sebuah layanan aplikasi harus menulis data ke basis data ACID (misal: PostgreSQL) dan mempublikasikan event ke Message Broker (misal: Kafka) secara bersamaan.

```
       Dual-Write Anti-Pattern:
       
       ┌────────────────────────┐
       │   Go Microservice      │
       └────┬──────────────┬────┘
            │              │
    (1) DB Commit   (2) Kafka Publish (FAILED! Network partition)
            │              │
            ▼              ▼
     ┌─────────────┐ ┌───────────┐
     │ PostgreSQL  │ │   Kafka   │  ===> INCONSISTENT STATE!
     │ (Committed) │ │ (No Msg)  │
     └─────────────┘ └───────────┘
```

Solusi absolut enterprise adalah **Transactional Outbox Pattern**:
1. Mutasi tabel bisnis (misal: `orders`) dan insert metadata event ke dalam tabel outbox (misal: `outbox_events`) dieksekusi di dalam **satu transaksi database lokal yang sama**.
2. Jika transaksi rollback, outbox event otomatis rollback.
3. Komponen *Message Relay* independen (bisa berupa poller Go dengan `SELECT ... FOR UPDATE SKIP LOCKED` atau CDC engine seperti Debezium yang membaca PostgreSQL Write-Ahead Log / WAL) membaca tabel outbox secara streaming dan mengirimkannya ke Kafka.
4. Setelah event terkonfirmasi ACK dari broker, status outbox diubah menjadi `PROCESSED` atau baris dihapus.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive) | Pendekatan Enterprise / Lanjutan |
| :--- | :--- | :--- |
| **Database Access** | Global connection string, driver default, tanpa batas timeout eksplisit, rawan koneksi idle menggantung selamanya. | Driver tuning mendalam (`pgxpool`), konfigurasi presisi `MaxConns`, `MinConns`, `MaxConnLifetime`, `HealthCheckPeriod`, query tracing, query cancellation via contexts. |
| **Cache Strategy** | Query DB $\rightarrow$ Set Redis tanpa perlindungan konkurensi. Rawan *Cache Stampede*, memory blowup akibat unkeyed singleflight. | Multi-tier Caching (Local Cache `sync.Map`/ristretto + Distributed Redis), *Singleflight Request Coalescing*, Distributed Lock watchdog, probabalistic early expiration (XFetch). |
| **Integrasi Event** | Direct publish ke broker setelah/sebelum DB query dalam handler HTTP (Dual-write anti-pattern). | Transactional Outbox Pattern, CDC Engine via WAL decoder, Idempotent Consumer State Store, Dead Letter Queue (DLQ) exponential backoff. |
| **Reliability** | *Fail-silent*, tidak ada circuit breaker, unhandled connection pool saturation memicu crash OOM. | Degradasi bertahap (*Graceful degradation*), connection pool backpressure detection, dynamic circuit breakers, non-blocking telemetry. |

---

## 5. How (Workflow Detail)

### Alur Kerja: End-to-End Resilient Order Processing

```
Client Request
      │
      ▼
[API Gateway / Router]
      │
      ▼
[Order Service: ExecuteOrder Engine]
      │
      ├─► 1. Begin Database Transaction (Serializable/Read Committed)
      │        ├── INSERT INTO orders (...)
      │        └── INSERT INTO outbox_events (id, topic, payload, status="PENDING")
      ├─► 2. Commit Transaction (Atomic Local ACID Guarantee)
      │
      ├─► 3. Invalidate/Update Cache (Best-Effort Async Invalidation)
      │
      └─► Return HTTP 201 Created to Client
      
[Async Outbox Publisher (Background Worker)]
      │
      ├─► Loop:
      │     BEGIN Tx
      │     SELECT * FROM outbox_events WHERE status='PENDING' 
      │     ORDER BY created_at ASC LIMIT 100 
      │     FOR UPDATE SKIP LOCKED;
      │
      ├─► Publish to Kafka Broker (Producer with acks=all)
      │
      └─► UPDATE outbox_events SET status='PROCESSED' WHERE id IN (...)
            COMMIT Tx

[Kafka Event Stream]
      │
      ▼
[Consumer Engine: Payment Processor]
      │
      ├─► 1. Poll Record from Kafka Partition
      ├─► 2. Check Idempotency Store (Redis/Postgres Unique Constraint)
      │        ├── IF EXISTS: ACK Offset and Skip (Ignore duplicate)
      │        └── IF NOT: Proceed
      ├─► 3. Execute Domain Logic
      ├─► 4. Save Event ID into Idempotency Store
      └─► 5. Commit Kafka Offset Synchronously/Batched
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Logistik Pabrik Perakitan Otomotif

*   **Database Connection Pool** ibarat **Armada Truk Pengangkut Logistik**: Truk (koneksi) mahal untuk dibeli dan dipanaskan (TCP handshake, TLS handshake, alokasi memori buffer backend). Menyimpan truk cadangan di garasi (`MaxIdleConns`) membuat pengiriman cepat. Namun jika Anda membuka garasi untuk 10.000 truk (`MaxOpenConns` tanpa batas), jalan raya pabrik (CPU dan RAM Database Server) akan mengalami macet total (*thrashing*), membakar bahan bakar tanpa ada barang yang terkirim.
*   **Singleflight** ibarat **Satu Kurir Mewakili Ratusan Pemesan Tiket**: Jika 1000 orang di satu kantor ingin memesan tiket konser yang sama di jam yang sama, daripada 1000 orang tersebut menyerbu situs tiket secara bersamaan (Cache Stampede yang melumpuhkan server tiket), ditunjuk 1 orang kurir untuk pergi membeli tiket tersebut. 999 orang lainnya menunggu di lobi kantor. Saat kurir kembali dengan tiket, salinannya dibagikan ke 1000 orang tersebut.
*   **Transactional Outbox** ibarat **Buku Tamu Resepsionis Bersatu**: Anda tidak boleh mengirim surat pemberitahuan ke kantor pos (Kafka) sebelum yakin tamu tersebut benar-benar terdaftar di buku induk hotel (Database). Untuk menghindari lupa kirim atau tamu batal masuk, resepsionis menulis data tamu dan langsung menulis surat di baki keluar (*outbox tray*) dalam satu sapuan pena. Pengantar surat bertugas mengambil tumpukan surat dari baki tersebut tanpa peduli tamu mana yang sedang check-in saat itu.

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: High-Throughput `pgxpool` Initialization

Contoh konfigurasi standar produksi untuk PostgreSQL connection pool menggunakan driver murni Go `jackc/pgx/v5/pgxpool`.

```go
package main

import (
	"context"
	"fmt"
	"log"
	"runtime"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func InitDatabasePool(ctx context.Context, dsn string) (*pgxpool.Pool, error) {
	config, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("gagal parsing DSN konfigurasi: %w", err)
	}

	// Dynamic pool sizing berdasarkan kapasitas komputasi runtime
	cpuCount := runtime.NumCPU()
	config.MaxConns = int32(cpuCount * 4) // Formula dasar I/O bound tuning
	config.MinConns = int32(cpuCount)
	config.MaxConnLifetime = 30 * time.Minute
	config.MaxConnIdleTime = 5 * time.Minute
	config.HealthCheckPeriod = 1 * time.Minute

	// Menghubungkan pool dengan timeout ketat
	ctxConnect, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	pool, err := pgxpool.NewWithConfig(ctxConnect, config)
	if err != nil {
		return nil, fmt.Errorf("gagal menginisialisasi pgxpool: %w", err)
	}

	// Validasi koneksi fisik (Ping)
	if err := pool.Ping(ctxConnect); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping database gagal: %w", err)
	}

	log.Printf("Postgres Pool berhasil diinisialisasi. MinConns: %d, MaxConns: %d\n", config.MinConns, config.MaxConns)
	return pool, nil
}
```

---

### 7.2 Practical Example: Enterprise Distributed Caching & Outbox Pattern

Berikut adalah implementasi level arsitektur produksi yang menggabungkan:
1. Singleflight pattern untuk eliminasi stampede.
2. Redis distributed lock dengan auto-renewal via context cancellation.
3. Transactional Outbox pattern worker.

```go
package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"golang.org/x/sync/singleflight"
)

// ==========================================
// 1. DATA STRUCTURES & INTERFACES
// ==========================================

type Order struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type OutboxEvent struct {
	ID        string    `json:"id"`
	Topic     string    `json:"topic"`
	Payload   []byte    `json:"payload"`
	CreatedAt time.Time `json:"created_at"`
}

type MessageProducer interface {
	Publish(ctx context.Context, topic string, key string, payload []byte) error
}

// ==========================================
// 2. RESILIENT CACHE-ASIDE SERVICE
// ==========================================

type OrderCacheService struct {
	rdb        *redis.Client
	sfGroup    singleflight.Group
	fetchDBFn  func(ctx context.Context, id string) (*Order, error)
	cacheTTL   time.Duration
}

func NewOrderCacheService(
	rdb *redis.Client, 
	fetchDBFn func(ctx context.Context, id string) (*Order, error),
	ttl time.Duration,
) *OrderCacheService {
	return &OrderCacheService{
		rdb:       rdb,
		fetchDBFn: fetchDBFn,
		cacheTTL:  ttl,
	}
}

func (s *OrderCacheService) GetOrder(ctx context.Context, orderID string) (*Order, error) {
	cacheKey := fmt.Sprintf("cache:order:%s", orderID)

	// L1: Cek Cache Redis
	val, err := s.rdb.Get(ctx, cacheKey).Bytes()
	if err == nil {
		var cached Order
		if unmarshalErr := json.Unmarshal(val, &cached); unmarshalErr == nil {
			return &cached, nil
		}
	} else if !errors.Is(err, redis.Nil) {
		// Log network error tapi jangan gagalkan eksekusi, fallback ke DB
		log.Printf("[CACHE WARN] Redis read error for key %s: %v", cacheKey, err)
	}

	// L2: Singleflight Call Coalescing (Eliminasi Cache Stampede)
	// Hanya 1 goroutine yang memanggil s.fetchDBFn untuk key yang sama
	result, err, shared := s.sfGroup.Do(orderID, func() (interface{}, error) {
		// Fetch data dari database
		dbOrder, dbErr := s.fetchDBFn(ctx, orderID)
		if dbErr != nil {
			return nil, dbErr
		}

		// Serialisasi & Simpan kembali ke Redis (Cache-Aside)
		payload, serErr := json.Marshal(dbOrder)
		if serErr == nil {
			setErr := s.rdb.Set(ctx, cacheKey, payload, s.cacheTTL).Err()
			if setErr != nil {
				log.Printf("[CACHE WARN] Gagal menyimpan key %s: %v", cacheKey, setErr)
			}
		}

		return dbOrder, nil
	})

	if err != nil {
		return nil, err
	}

	log.Printf("[CACHE LOG] Key: %s, Data shared to concurrent requests: %t", cacheKey, shared)
	return result.(*Order), nil
}

// ==========================================
// 3. ATOMIC DISTRIBUTED LOCK MUTEX (REDIS)
// ==========================================

const unlockLuaScript = `
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
`

type DistributedLock struct {
	rdb    *redis.Client
	key    string
	token  string
	expiry time.Duration
}

func NewDistributedLock(rdb *redis.Client, key string, expiry time.Duration) (*DistributedLock, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return nil, err
	}
	return &DistributedLock{
		rdb:    rdb,
		key:    fmt.Sprintf("lock:%s", key),
		token:  hex.EncodeToString(b),
		expiry: expiry,
	}, nil
}

func (l *DistributedLock) Acquire(ctx context.Context) (bool, error) {
	ok, err := l.rdb.SetNX(ctx, l.key, l.token, l.expiry).Result()
	if err != nil {
		return false, fmt.Errorf("redis setnx error: %w", err)
	}
	return ok, nil
}

func (l *DistributedLock) Release(ctx context.Context) error {
	res, err := l.rdb.Eval(ctx, unlockLuaScript, []string{l.key}, l.token).Result()
	if err != nil {
		return fmt.Errorf("evaluating unlock lua script failed: %w", err)
	}
	if res.(int64) == 0 {
		return errors.New("lock ownership mismatch or lock already expired")
	}
	return nil
}

// ==========================================
// 4. TRANSACTIONAL OUTBOX REPOSITORY & WORKER
// ==========================================

type OrderRepository struct {
	db *sql.DB
}

func NewOrderRepository(db *sql.DB) *OrderRepository {
	return &OrderRepository{db: db}
}

// CreateOrderWithOutbox mengeksekusi insert tabel domain & outbox secara ACID lokal
func (r *OrderRepository) CreateOrderWithOutbox(ctx context.Context, order *Order) error {
	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("failed to begin tx: %w", err)
	}
	defer tx.Rollback() // Rollback jika tidak ada commit

	// 1. Insert ke tabel order
	queryOrder := `INSERT INTO orders (id, user_id, amount, status, created_at) VALUES ($1, $2, $3, $4, $5)`
	_, err = tx.ExecContext(ctx, queryOrder, order.ID, order.UserID, order.Amount, order.Status, order.CreatedAt)
	if err != nil {
		return fmt.Errorf("failed to insert order: %w", err)
	}

	// 2. Insert ke outbox table
	payload, err := json.Marshal(order)
	if err != nil {
		return fmt.Errorf("failed to marshal outbox payload: %w", err)
	}

	queryOutbox := `INSERT INTO outbox_events (id, topic, payload, created_at) VALUES ($1, $2, $3, $4)`
	outboxID := fmt.Sprintf("outbox-%s", order.ID)
	_, err = tx.ExecContext(ctx, queryOutbox, outboxID, "order.events.created", payload, time.Now().UTC())
	if err != nil {
		return fmt.Errorf("failed to insert outbox event: %w", err)
	}

	// 3. Commit kedua operasi secara serentak
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit tx: %w", err)
	}

	return nil
}

// OutboxPublisherWorker memproses event pending secara asynchronous
type OutboxPublisherWorker struct {
	db       *sql.DB
	producer MessageProducer
	stopChan chan struct{}
	wg       sync.WaitGroup
}

func NewOutboxPublisherWorker(db *sql.DB, producer MessageProducer) *OutboxPublisherWorker {
	return &OutboxPublisherWorker{
		db:       db,
		producer: producer,
		stopChan: make(chan struct{}),
	}
}

func (w *OutboxPublisherWorker) Start(interval time.Duration) {
	w.wg.Add(1)
	go func() {
		defer w.wg.Done()
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-w.stopChan:
				log.Println("[OUTBOX WORKER] Stopping loop...")
				return
			case <-ticker.C:
				if err := w.processBatch(context.Background()); err != nil {
					log.Printf("[OUTBOX WORKER ERROR] %v", err)
				}
			}
		}
	}()
}

func (w *OutboxPublisherWorker) processBatch(ctx context.Context) error {
	tx, err := w.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// Kunci baris dengan FOR UPDATE SKIP LOCKED untuk konkurensi antar replika worker
	query := `
		SELECT id, topic, payload, created_at 
		FROM outbox_events 
		ORDER BY created_at ASC 
		LIMIT 50 
		FOR UPDATE SKIP LOCKED
	`
	rows, err := tx.QueryContext(ctx, query)
	if err != nil {
		return err
	}
	defer rows.Close()

	var events []OutboxEvent
	var idsToDelete []string

	for rows.Next() {
		var evt OutboxEvent
		if scanErr := rows.Scan(&evt.ID, &evt.Topic, &evt.Payload, &evt.CreatedAt); scanErr != nil {
			return scanErr
		}
		events = append(events, evt)
		idsToDelete = append(idsToDelete, evt.ID)
	}

	if len(events) == 0 {
		return nil // Tidak ada pending event
	}

	// Publish ke message broker
	for _, evt := range events {
		if pubErr := w.producer.Publish(ctx, evt.Topic, evt.ID, evt.Payload); pubErr != nil {
			return fmt.Errorf("failed publishing event %s to broker: %w", evt.ID, pubErr)
		}
	}

	// Hapus atau perbarui status outbox setelah berhasil dikirim
	deleteQuery := `DELETE FROM outbox_events WHERE id = ANY($1)`
	_, err = tx.ExecContext(ctx, deleteQuery, idsToDelete)
	if err != nil {
		return fmt.Errorf("failed deleting sent outbox events: %w", err)
	}

	return tx.Commit()
}

func (w *OutboxPublisherWorker) Stop() {
	close(w.stopChan)
	w.wg.Wait()
	log.Println("[OUTBOX WORKER] Stopped gracefully.")
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash Sale Ledger & Order Allocation Engine (120.000 RPS)

#### Permasalahan (Root Cause Failure)
Sebuah platform e-commerce Tier-1 mengalami keruntuhan infrastruktur pada event Flash Sale 11.11. 
1. Database PostgreSQL kehabisan koneksi (*Connection Exhaustion: `FATAL: remaining connection slots are reserved for non-replication superuser connections`*). 150 pod aplikasi Go membuka `MaxOpenConns = 100`, membanjiri server dengan total 15.000 koneksi fisik. CPU Database melonjak ke 100% akibat context switching OS threads dan lock contention.
2. Latensi cache Redis naik dari 2ms ke 450ms karena *Cache Stampede*: ratusan ribu request mencoba memperbarui data kuota item yang kedaluwarsa secara serentak ke Database (*Dogpiling effect*).
3. Terjadi *Dual-Write Split-Brain*: 4.200 transaksi pesanan berhasil ditulis ke database, namun crash pada instance Go menyebabkan event pemotongan stok ke Kafka gagal dikirim. Akibatnya terjadi insiden *Overselling* massal senilai miliaran rupiah.

#### Solusi Arsitektur
1. **Connection Pool Shrinking & PgBouncer Multi-Tiering**:
   *   Mengurangi `MaxConns` pada instance Go dari 100 ke 15 per pod.
   *   Menerapkan PgBouncer di depan database cluster dengan mode `transaction pooling`. Total koneksi aktual ke PostgreSQL backend dibatasi keras pada:
       $$\text{Backend Conns} = (\text{CPU Cores} \times 2) + \text{Spindle Disk Count} = (64 \times 2) + 8 = 136$$
2. **Singleflight + Jittered Exponential TTL**:
   *   Mengintegrasikan `singleflight.Group` di lapisan service Go, mereduksi lonjakan 120.000 query konkuren ke database untuk produk yang sama menjadi tepat **1 query** ke DB per detik.
   *   Menambahkan random jitter pada TTL Redis: $\text{TTL} = \text{BaseTTL} + \text{rand}(0, 60\text{s})$ untuk menghindari masa kedaluwarsa serentak (*Cache Avalanche*).
3. **Penerapan Transactional Outbox + Debezium CDC**:
   *   Menghilangkan penerbitan direct-to-Kafka dari handler HTTP. Seluruh mutasi divalidasi dan dicatat ke tabel `outbox_events` dalam transaksi ACID.
   *   Debezium membaca PostgreSQL WAL secara non-blocking dan meneruskan streaming ke Kafka dengan latensi sub-detik (p99 < 80ms).
4. **Idempotency Engine pada Consumer**:
   *   Setiap consumer menerapkan *atomic deduplication check* memanfaatkan Redis `SET order:idempotency:<id> "PROCESSING" EX 86400 NX`.

#### Hasil Metrik Pasca Implementasi
*   **Database CPU Utilization**: Turun drastis dari 100% konstan menjadi rata-rata 34% pada beban puncak 120.000 RPS.
*   **Cache Hit Ratio**: Naik dari 68.2% menjadi 99.85%.
*   **Inkonsistensi Data (Overselling)**: 0 Kasus (Eliminasi total *Dual-Write Failure*).
*   **P99 Latency**: Berkurang dari 3.800ms menjadi 42ms.

---

## 9. Trade-offs (Arsitektur & Desain)

```
                              DATA CONSISTENCY STRATEGY
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
[Transactional Outbox + Poller]                                 [Change Data Capture (CDC)]
Pros:                                                           Pros:
- Mudah diimplementasikan di kode Go murni                      - Zero-load pada query DB (baca WAL)
- Tidak butuh dependensi infra tambahan                         - Latensi streaming real-time (<50ms)
- Kontrol query SQL penuh                                       - Menjamin urutan historis absolut
Cons:                                                           Cons:
- Polling menambah read-load pada DB                            - Overhead infra (Debezium, Kafka Connect)
- Delay minimum dibatasi oleh Ticker polling                    - Kompleksitas schema migration handling
```

| Parameter | GORM (ORM Layer) | pgx / database/sql murni |
| :--- | :--- | :--- |
| **Kecepatan Eksekusi** | Sedang (Overhead refleksi dan alokasi `interface{}`) | Sangat Cepat (Zero-reflection mapping langsung ke struct) |
| **Alokasi Heap Memori** | Tinggi (Banyak alokasi per query scan) | Sangat Rendah (Optimal untuk alokasi GC seminimal mungkin) |
| **Keamanan Tipe (Type Safety)** | Parsial (`map[string]interface{}` rawan typo) | Tinggi (Dukungan penuh type casting dan code generation sqlc) |
| **Kontrol Koneksi & Wire Protocol** | Terisolasi di balik layer abstraksi | Kontrol granular (Prepared statements, pipeline protocol, native types) |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Connection Leak melalui Unclosed Rows
**Kesalahan Fatal:**
```go
// ANTI-PATTERN: rows.Close() diabaikan atau terlambat ditunda
rows, err := db.QueryContext(ctx, "SELECT id, name FROM users")
if err != nil {
    return err
}
// BUG: Jika looping panik atau return dini karena error rows.Scan,
// koneksi underlying TIDAK PERNAH dikembalikan ke freeConn slice!
for rows.Next() {
    var u User
    if err := rows.Scan(&u.ID, &u.Name); err != nil {
        return err // KONEKSI BOCOR SELAMANYA DI SINI
    }
}
```

**Solusi Standar Produksi:**
```go
// BENAR: defer rows.Close() tepat setelah pengecekan error nil
rows, err := db.QueryContext(ctx, "SELECT id, name FROM users")
if err != nil {
    return err
}
defer rows.Close() // Pastikan SELALU dieksekusi saat keluar scope

for rows.Next() {
    var u User
    if err := rows.Scan(&u.ID, &u.Name); err != nil {
        return fmt.Errorf("scan error: %w", err)
    }
}

// WAJIB: Selalu cek rows.Err() untuk mendeteksi error di tengah streaming TCP
if err := rows.Err(); err != nil {
    return fmt.Errorf("error during row iteration: %w", err)
}
```

### 10.2 Context Cancellation Membatalkan Rollback
Jika context timeout dari HTTP request dibatalkan saat query gagal, pemanggilan `tx.Rollback()` dengan context yang sama akan gagal dieksekusi karena context telah `Canceled`.
```go
// ANTI-PATTERN
defer tx.Rollback() // Menggunakan tx context yang mungkin sudah expired

// BENAR
defer func() {
    if p := recover(); p != nil {
        _ = tx.Rollback()
        panic(p)
    } else if err != nil {
        // Gunakan context background terpisah dengan timeout jika rollback via query spesifik
        _ = tx.Rollback()
    }
}()
```

### 10.3 Unkeyed atau Global Singleflight Collision
Menggunakan key singleflight yang ambigu (misalnya hanya `id` tanpa domain scope):
```go
// KESALAHAN: ID produk "123" dan ID pengguna "123" bertabrakan
sf.Do(id, fetchFunc) 

// BENAR: Terapkan namespacing strict
sfKey := fmt.Sprintf("catalog:products:%s", id)
sf.Do(sfKey, fetchFunc)
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Connection Pool Isolation**: Konfigurasikan `SetMaxOpenConns` dan `SetMaxIdleConns` secara seimbang (misal: `MaxIdleConns = MaxOpenConns`) untuk mencegah osilasi buka-tutup soket TCP (*TCP Handshake Churn*).
- [ ] **Connection Lifetime Recycling**: Selalu pasang `SetConnMaxLifetime` (misal: 15–30 menit) di bawah ambang batas load balancer, AWS NLB, atau timeout koneksi idle firewall (biasanya 60 menit) guna mencegah *Broken Pipe / Connection Reset by Peer*.
- [ ] **Timeout Strictness**: Jangan pernah memanggil operasi DB tanpa `context.WithTimeout` atau DSN query parameter `statement_timeout`.
- [ ] **Cache Stampede Prevention**: Setiap pembacaan cache tingkat tinggi yang terintegrasi database wajib dilindungi primitif penggabung request (`singleflight`) atau probabilistic early expiration.
- [ ] **Redis Non-Zero Expiration**: Hindari `SET` tanpa expiration time (TTL) kecuali ditujukan khusus untuk data referensi statis yang diatur kapasitas memorinya dengan Redis *eviction policy* (`volatile-lru` / `allkeys-lru`).
- [ ] **Deduplication Engine**: Konsumen stream/event wajib mengasumsikan broker menerapkan pengiriman *at-least-once*. Idempotensi transaksi mutlak disediakan di level aplikasi via tabel deduplikasi atau Redis atomic tokens.
- [ ] **Graceful Consumer Shutdown**: Pada saat SIGTERM/SIGINT diterima, tahan offset commit, selesaikan record yang sedang diproses di goroutine pool, kemudian tutup channel Kafka Reader secara teratur.

---

## 12. Hands-on Practice

Struktur direktori praktikum yang wajib dibangun:

```
hands-on/m02/
├── cmd/
│   └── api/
│       └── main.go
├── docker-compose.yml
├── go.mod
├── go.sum
└── internal/
    ├── domain/
    │   └── order.go
    ├── event/
    │   └── consumer.go
    └── persistence/
        ├── cache.go
        └── postgres.go
```

### Langkah 1: Siapkan Dependency dan Infrastruktur

Buat file `docker-compose.yml`:
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: pguser
      POSTGRES_PASSWORD: pgpassword
      POSTGRES_DB: enterprisedb
    ports:
      - "5432:5432"
    command: postgres -c 'max_connections=200'

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  kafka:
    image: bitnami/kafka:3.7
    ports:
      - "9092:9092"
    environment:
      - KAFKA_CFG_NODE_ID=0
      - KAFKA_CFG_PROCESS_ROLES=controller,broker
      - KAFKA_CFG_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093
      - KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=0@kafka:9093
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
```

Jalankan container:
```bash
docker compose up -d
```

Inisialisasi schema database di PostgreSQL:
```sql
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outbox_events (
    id VARCHAR(64) PRIMARY KEY,
    topic VARCHAR(128) NOT NULL,
    payload BYTEA NOT NULL,
    status VARCHAR(32) DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_outbox_status_created ON outbox_events(status, created_at);
```

### Langkah 2: Inisialisasi Modul Go
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init enterprise-storage

# Unduh dependensi produksi
go get github.com/jackc/pgx/v5
go get github.com/redis/go-redis/v9
go get golang.org/x/sync/singleflight
go get github.com/segmentio/kafka-go
```

### Langkah 3: Implementasi Idempotent Kafka Consumer
Tulis kode berikut pada `hands-on/m02/internal/event/consumer.go`:

```go
package event

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
)

type OrderPaidConsumer struct {
	reader *kafka.Reader
	rdb    *redis.Client
}

func NewOrderPaidConsumer(brokers []string, topic string, groupID string, rdb *redis.Client) *OrderPaidConsumer {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		Topic:          topic,
		GroupID:        groupID,
		MinBytes:       10e3, // 10KB
		MaxBytes:       10e6, // 10MB
		CommitInterval: 0,    // Synchronous manual commit
	})

	return &OrderPaidConsumer{
		reader: reader,
		rdb:    rdb,
	}
}

func (c *OrderPaidConsumer) Listen(ctx context.Context) error {
	log.Println("[KAFKA] Consumer loop dimulai...")
	for {
		msg, err := c.reader.FetchMessage(ctx)
		if err != nil {
			if errorsIsContext(err, ctx) {
				return nil // Graceful exit
			}
			log.Printf("[KAFKA ERROR] FetchMessage: %v", err)
			continue
		}

		if err := c.processMessage(ctx, msg); err != nil {
			log.Printf("[KAFKA PROCESS ERROR] Gagal proses offset %d: %v", msg.Offset, err)
			// Strategi penanganan error: DLQ atau Exponential Backoff
			continue
		}

		// Commit offset secara manual setelah proses transaksi tuntas
		if err := c.reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("[KAFKA COMMIT ERROR] Offset %d: %v", msg.Offset, err)
		}
	}
}

func (c *OrderPaidConsumer) processMessage(ctx context.Context, msg kafka.Message) error {
	idempotencyKey := fmt.Sprintf("idempotency:event:%s", string(msg.Key))

	// Atomically set key jika belum pernah dieksekusi (TTL 24 Jam)
	isNew, err := c.rdb.SetNX(ctx, idempotencyKey, "PROCESSED", 24*time.Hour).Result()
	if err != nil {
		return fmt.Errorf("idempotency store failure: %w", err)
	}

	if !isNew {
		log.Printf("[IDEMPOTENT] Mengabaikan duplikasi pesan key: %s", string(msg.Key))
		return nil
	}

	// Simulasi Eksekusi Logika Bisnis
	log.Printf("[EVENT PROCESSED] Partition: %d, Offset: %d, Key: %s, Data: %s", 
		msg.Partition, msg.Offset, string(msg.Key), string(msg.Payload))

	return nil
}

func (c *OrderPaidConsumer) Close() error {
	return c.reader.Close()
}

func errorsIsContext(err error, ctx context.Context) bool {
	return ctx.Err() != nil
}
```

---

## 13. Exercise

### Level Easy
Tuliskan micro-benchmark Go (`testing.B`) yang membandingkan performa antara query serial vs batching pipelining pada Redis menggunakan library `go-redis/v9`. Ukur perbedaan throughput (*allocs/op* dan *ns/op*).

### Level Medium
Buat sebuah middleware Go HTTP yang mengamati durasi query pada `database/sql` menggunakan tracing wrapper. Jika sebuah query melebihi ambang batas 200 milidetik, middleware secara otomatis mencatat *query statement*, parameter non-sensitif, dan stack trace ke logger level `WARN` (*Slow Query Logger*).

### Level Hard
Implementasikan sebuah library **Reliable Poller** untuk PostgreSQL outbox pattern yang memiliki fitur:
1. Dynamic worker pool scaling: Menambah konkurensi worker jika antrean outbox menumpuk.
2. Graceful partition failover menggunakan PostgreSQL Advisory Locks (`pg_try_advisory_lock`), memastikan tidak ada 2 node worker Go yang memproses partisi/batch event yang sama.
3. Exponential backoff retry handler untuk broker Kafka yang sedang mengalami transien offline.

---

## 14. Challenge (Studi Kasus Nyata Arsitektur)

**Skenario Tantangan:**  
Perusahaan Fintech Payment Gateway multi-wilayah (Multi-Region Active-Active: Singapore & Jakarta) menghadapi situasi di mana dua data center memproses mutasi saldo rekening nasabah secara konkuren. 

**Persyaratan Tantangan:**
1. Desain arsitektur data persistence dan streaming Go murni yang mencegah terjadinya *Double Spending* ketika jaringan koneksi antar wilayah (Inter-region WAN) mengalami partisi selama hingga 15 menit.
2. Buat skema koordinasi cache Redis dan Event Log Kafka yang menjamin *Strong Consistency* pada pemotongan saldo, namun tetap memberikan *Eventual Consistency* pada pembacaan riwayat transaksi di dashboard mobile nasabah.
3. Rancang mekanisme rekonsiliasi data otomatis (CRDT atau Event Sourcing Replay Engine) yang akan mengeksekusi *conflict resolution* saat koneksi jaringan antar-wilayah kembali pulih.
4. Tuliskan implementasi komponen inti sinkronisasi engine tersebut dalam bahasa Go tanpa menggunakan ORM eksternal.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. Apa fungsi internal dari konfigurasi `db.SetConnMaxIdleTime(d)` pada struct `sql.DB` di Go?
2. Mengapa pemanggilan `rows.Close()` wajib diletakkan di dalam blok `defer` langsung setelah pengecekan error `db.Query`?
3. Apa perbedaan mendasar antara perintah Redis `MSET` dengan teknik `Redis Pipelining`?
4. Mengapa Redis lock primitif `SET lock_key unique_token NX PX 5000` tidak aman jika dilepas hanya dengan `DEL lock_key`?
5. Mengapa arsitektur microservices modern melarang publikasi Kafka event langsung di dalam HTTP request handler sebelum database transaction di-commit?

### Bagian 2: Intermediate (5 Soal)
6. Bagaimana `golang.org/x/sync/singleflight` bekerja secara internal dalam menahan 1000 goroutine yang meminta resource yang sama secara bersamaan?
7. Mengapa query `SELECT ... FROM outbox_events WHERE status = 'PENDING' FOR UPDATE SKIP LOCKED` lebih disukai dibandingkan `SELECT ... FOR UPDATE` biasa pada sistem multi-instance publisher?
8. Apa dampak konkurensi jika nilai `MaxIdleConns` disetel jauh lebih kecil daripada `MaxOpenConns` pada aplikasi dengan traffic *bursty* (bergelombang tinggi)?
9. Bagaimana strategi penanganan *Tombstone* records dan schema migration pada implementasi Change Data Capture (CDC) berbasis Debezium ke Kafka?
10. Kapan sebaiknya kita memilih isolation level `Serializable` dibandingkan `Read Committed` yang dikombinasikan dengan pessimistic locking (`FOR UPDATE`) di PostgreSQL?

### Bagian 3: Skenario Kasus Produksi (3 Soal)

**Kasus A: Broken Pipe Cascading Outage**  
Sebuah aplikasi Go mengalami lonjakan error secara periodik setiap 60 menit sekali: `driver: bad connection` atau `read: connection reset by peer`. Ini memicu HTTP 500 spike pada load balancer sebelum kembali normal dengan sendirinya. Database backend (AWS Aurora RDS) menunjukkan CPU dan memory dalam keadaan sehat (< 20%).  
*Pertanyaan:* Analisis letak kesalahan konfigurasi connection pool Go Anda dan rumuskan solusi mitigasinya!

**Kasus B: The Phantom Deduplication**  
Sebuah payment consumer mengandalkan Redis `SETNX` untuk mencegah pemrosesan event ganda. Suatu ketika, terjadi pemadaman listrik pada node Redis master, dan Redis Sentinel mempromosikan replica menjadi master baru. Terjadi pemrosesan ganda pada ratusan transaksi pembayaran.  
*Pertanyaan:* Mengapa `SETNX` pada Redis standar gagal menjaga idempotensi dalam kondisi failover master-replica, dan arsitektur apa yang harus dibangun untuk menutup celah inkonsistensi tersebut?

**Kasus C: Singleflight Context Leak**  
Seorang developer membungkus database query di dalam `singleflight.Group.DoChan`. Ketika client HTTP pertama membatalkan koneksinya (misal: browser tab ditutup), context HTTP tersebut dibatalkan (`context.Canceled`). Dampaknya, 50 client lain yang sedang menunggu hasil pemanggilan singleflight tersebut ikut menerima error `context canceled`, meskipun koneksi mereka masih aktif.  
*Pertanyaan:* Jelaskan mekanisme kegagalan tersebut dan bagaimana cara memisahkan (*detach*) context lifecycle antara request pembawa (*caller*) dengan background execution worker!

---

## 16. Summary

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ENTERPRISE STORAGE ARCHITECTURE MATRIX                          │
├───────────────────┬──────────────────────────────────┬─────────────────────────────────┤
│ Komponen          │ Pola Anti-Pattern (Bahaya)       │ Standar Enterprise (Produksi)   │
├───────────────────┼──────────────────────────────────┼─────────────────────────────────┤
│ Persistence       │ Pool unbounded, rows unclosed,   │ pgxpool, strict sizing context, │
│                   │ lock contention global mutex.    │ PgBouncer, non-blocking metrics.│
├───────────────────┼──────────────────────────────────┼─────────────────────────────────┤
│ Caching           │ Naive Cache-Aside, TTL serentak, │ Singleflight request coalescing,│
│                   │ unvalidated lock deletion.       │ Lua atomic release, early-fetch.│
├───────────────────┼──────────────────────────────────┼─────────────────────────────────┤
│ Event Streaming   │ Direct-write dual mutations,     │ Transactional Outbox, CDC WAL,  │
│                   │ auto-commit offset indiscriminat.│ Manual commit, Deduplication DB.│
└───────────────────┴──────────────────────────────────┴─────────────────────────────────┘
```

1. **Abstraksi Database Membutuhkan Disiplin Ketat**: Driver basis data Go menyembunyikan kompleksitas soket TCP melalui connection pool abstraction. Kesalahan pengelolaan lifecycle connection (`rows.Close()`, idle churn, context starvation) adalah penyebab utama degradasi performa pada sistem berskala masif.
2. **Eliminasi Dual-Write adalah Kewajiban Mutlak**: Mencoba menyelaraskan database ACID dan Message Broker terdistribusi menggunakan kode aplikasi sekuensial sederhana merupakan cacat arsitektur. Transactional Outbox Pattern menjamin konsistensi status melalui atomisitas transaksi lokal.
3. **Caching Menuntut Perlindungan Komprehensif**: Caching bukan sekadar memanggil operasi `GET` dan `SET` pada Redis. Perlindungan terhadap anomali beban (*Cache Stampede*, *Avalanche*) menggunakan `singleflight` dan atomisitas penguncian terdistribusi via Lua script merupakan prasyarat mutlak sistem mission-critical.