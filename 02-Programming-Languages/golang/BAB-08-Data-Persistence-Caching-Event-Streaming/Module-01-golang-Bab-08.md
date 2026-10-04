# BAB 08 / MODUL 01: Data Persistence, Caching & Event Streaming

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Topik Utama:** Golang Systems & Backend Engineering
* **Nomor Modul:** Bab 08 — Modul 01
* **Judul Modul:** Data Persistence, Caching & Event Streaming
* **Target Tingkat Keahlian:** Advanced / Production-Ready Backend Engineer
* **Prasyarat Pengetahuan:** Concurrency Primitives (`sync`, Channels, Goroutines), Context Propagation (`context.Context`), Network I/O dasar, dan Fondasi Database Relasional (SQL Engine).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Mengonfigurasi Database Connection Pool (`database/sql`)**: Membedah arsitektur internal connection pool Go, mengidentifikasi kebocoran koneksi (*connection leak*), serta menetapkan parameter `SetMaxOpenConns`, `SetMaxIdleConns`, dan `SetConnMaxLifetime` secara presisi berbasis profil beban (*workload*).
2. **Mengimplementasikan Pola Caching Berkinerja Tinggi**: Membangun arsitektur *Cache-Aside* menggunakan Redis, mengintegrasikan mitigasi *Cache Stampede* berbasis `golang.org/x/sync/singleflight`, dan merancang strategi masa kedaluwarsa data (*TTL with jitter*).
3. **Membangun Event Pipeline Terdistribusi Menggunakan Apache Kafka**: Mengonfigurasi Kafka Writer dan Reader menggunakan driver murni Go (`segmentio/kafka-go`), memahami semantik partisi, *consumer groups*, rebalancing, dan strategi *offset commit*.
4. **Menerapkan Transactional Outbox Pattern**: Mengeliminasi *dual-write distributed inconsistency* dengan menyatukan operasi mutasi state database dan emisi pesan event streaming ke dalam satu transaksi atomik (ACID).
5. **Menjamin Reliabilitas dan Idempoten Event Processing**: Merancang skema deduplikasi pesan pada sisi *consumer* untuk menjamin semantik *at-least-once delivery* dapat berjalan dengan aman tanpa risiko data ganda (*duplicate execution*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Dual-Write Dilemma & Ilusi Jaringan
Banyak *engineer* pemula mengasumsikan bahwa dua pemanggilan jaringan (*network call*) berurutan dapat berjalan seolah-olah keduanya atomik:

```go
// ANTI-PATTERN: Berbahaya di Sistem Terdistribusi
err := db.ExecContext(ctx, "UPDATE balances SET amount = amount - 100 WHERE id = $1", userID)
if err == nil {
    kafkaProducer.Publish("balance-updated", event) // Jika proses crash di sini, event hilang selamanya!
}
```

Mental model yang benar: **Jaringan selalu tidak dapat diandalkan (*fallible*)**. Anda tidak boleh mengasumsikan konsistensi data antara dua penyimpanan berbeda (misalnya Postgres dan Kafka) tanpa adanya koordinator transaksi terdistribusi formal (seperti 2PC yang lambat) atau pola arsitektural berbasis *Eventual Consistency* seperti **Transactional Outbox Pattern**.

### Tiga Pilar Data Lifecycle
1. **Source of Truth (Data Persistence - PostgreSQL):** Menjamin integritas data tertinggi (ACID). Lambat secara latensi relatif terhadap memori, berbiaya I/O tinggi, menjadi leher botol (*bottleneck*) konkuren jika tidak dikelola dengan connection pooling yang tepat.
2. **Acceleration Layer (Caching - Redis):** Mengurangi beban throughput pembacaan (*read throughput*) dari database utama. Bersifat volatil. Cache **bukan** source of truth; data di dalamnya hanyalah proyeksi terkuantisasi waktu (*time-quantized projection*) dari database.
3. **Decoupling & Propagation Layer (Event Streaming - Kafka):** Menyebarkan fakta (*facts/events*) yang telah terjadi di sistem ke downstream services secara asinkron tanpa membebani thread eksekusi utama (OLTP context).

```
   [ Client Request ]
           │
           ▼
    ┌─────────────┐       Cache Hit
    │ Redis Cache │ ──────────────────┐
    └─────────────┘                   │
      │ Cache Miss                    │
      ▼                               ▼
    ┌─────────────┐             [ Response ]
    │ PostgreSQL  │ (Atomik)
    │ ┌─────────┐ │
    │ │ Business│ │
    │ ├─────────┤ │
    │ │ Outbox  │ │
    │ └─────────┘ │
    └─────────────┘
           │
           │ (CDC / Poller Engine)
           ▼
    ┌─────────────┐
    │ Kafka Topic │ ──► [ Downstream Consumers ]
    └─────────────┘
```

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran data end-to-end yang menunjukkan bagaimana operasi tulis (*write path*) menggunakan Transactional Outbox Pattern, dan operasi baca (*read path*) menerapkan Cache-Aside yang dilindungi oleh Singleflight Engine.

```
WRITE PATH (Transactional Outbox Pattern):
========================================================================================
[ HTTP Client ]
      │
      │ 1. POST /orders
      ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Go Application Core                                                                  │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │ BEGIN TX (PostgreSQL)                                                          │  │
│  │   2. INSERT INTO orders (...)                                                  │  │
│  │   3. INSERT INTO outbox_events (aggregate_type, payload, status = 'PENDING')   │  │
│  │ COMMIT TX                                                                      │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────┘
      │
      │ Transaksi selesai secara atomik
      ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Background Worker (Go Goroutine / Outbox Relay)                                      │
│                                                                                      │
│  4. SELECT * FROM outbox_events WHERE status = 'PENDING' FOR UPDATE SKIP LOCKED      │
│  5. Publish message to Kafka Broker                                                  │
│  6. UPDATE outbox_events SET status = 'PROCESSED' WHERE id = ...                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
[ Apache Kafka ] ───► [ Downstream Consumers: Analytics, Invoicing, Notifications ]


READ PATH (Cache-Aside + Singleflight Lock Elimination):
========================================================================================
[ HTTP Client ]
      │
      │ 1. GET /orders/{id}
      ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Go Application Core                                                                  │
│                                                                                      │
│  2. Query Redis ──────────────────────────────[ FOUND ]──────────► Return JSON       │
│        │                                                                             │
│     [ MISS ]                                                                         │
│        ▼                                                                             │
│  3. singleflight.Group.Do(orderID, fn)                                               │
│        │                                                                             │
│        ├─► [ Goroutine 1 (Winner) ] ──► Fetch Postgres ──► Set Redis (with TTL)      │
│        │                                                          │                  │
│        └─► [ Goroutines 2..N (Waiters) ] ◄────────────────────────┘                  │
│                   │                                                                  │
│                   └─► Menerima hasil Goroutine 1 tanpa query database ulang          │
└──────────────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
  Return JSON
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi Internal `database/sql` Connection Pool
Package `database/sql` bukan koneksi individual ke database, melainkan sebuah **abstraksi connection pool thread-safe**. Di dalamnya terdapat dua slice koneksi:
* `freeConn []*driverConn`: Kumpulan koneksi idle yang siap digunakan.
* `connRequests map[uint64]chan connRequest`: Antrean permintaan koneksi jika pool mencapai batas `MaxOpenConns`.

```
                    database/sql Pool Architecture
                   ┌──────────────────────────────┐
                   │           DB Struct          │
                   │                              │
OpenConns Count ──►│  maxOpen, maxIdle, waitDuration
                   │                              │
                   │   freeConn       connRequests│
                   └──────┬─────────────────┬─────┘
                          │                 │
              Pop idle    │                 │ Block & Wait
                          ▼                 ▼
                   ┌─────────────┐   ┌─────────────┐
                   │ *driverConn │   │ chan connReq│
                   └─────────────┘   └─────────────┘
                          ▲
                          │ Return to pool (PutBack)
                          │
                     Worker Done
```

* **Siklus Hidup Eksekusi Query:**
  1. Goroutine memanggil `db.Conn(ctx)` atau `db.QueryContext(ctx)`.
  2. Pool memeriksa apakah ada koneksi di `freeConn`. Jika ada dan belum kedaluwarsa (`time.Since(conn.createdAt) < ConnMaxLifetime`), koneksi diambil.
  3. Jika `freeConn` kosong dan jumlah koneksi aktif < `maxOpen`, pool membuka koneksi TCP baru via underlying driver (`pgx`).
  4. Jika jumlah koneksi aktif >= `maxOpen`, goroutine akan **terblokir** (*blocked*), menunggu di `connRequests` sampai ada koneksi yang dikembalikan atau context dibatalkan (`ctx.Done()`).
  5. **Bahaya Fatal:** Kegagalan memanggil `rows.Close()` mencegah koneksi kembali ke `freeConn`, menyebabkan *connection starvation* yang menghentikan seluruh request di aplikasi.

### 2. Redis Client Multiplexing & In-Flight Management
`go-redis` secara internal mengelola pool koneksi TCP berbasis goroutine-safe ring/slice buffer. Permintaan pipelining mengumpulkan beberapa perintah dalam satu *network write syscall*, mengurangi *overhead round-trip time* (RTT) secara drastis melalui kernel socket buffer.

### 3. Kafka Consumer Group & Partition Assignment
Pada Kafka, paralelisme konsumsi dibatasi oleh **jumlah partisi** pada suatu topik:
* Jika suatu topik memiliki 8 partisi, maksimal 8 consumer dalam satu *consumer group* yang dapat memproses data secara simultan (1 partisi = 1 consumer).
* Arsitektur driver Go (`segmentio/kafka-go`) mengelola koneksi TCP per broker, menangani heartbeat di background goroutine untuk mencegah *rebalance storm*, dan menyediakan fetcher loop yang mengisi buffer channel memori lokal.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Transaksi ACID & Snapshot Isolation pada PostgreSQL
Dalam sistem konkurensi tinggi, integritas data ditentukan oleh level isolasi transaksi:
* **Read Committed (Default):** Setiap query dalam transaksi hanya membaca data yang sudah di-commit sebelum query itu dimulai. Rentan terhadap *non-repeatable reads* dan *phantom reads*.
* **Repeatable Read:** Menggunakan snapshot database yang diambil pada awal transaksi. Mencegah *non-repeatable reads*. Jika dua transaksi mencoba memutasi baris data yang sama, salah satu akan menerima error serialisasi: `ERROR: could not serialize access due to concurrent update`.
* **SELECT ... FOR UPDATE SKIP LOCKED:** Mekanisme penting untuk implementasi sistem *job queue* atau *outbox table* konkuren. Klausa `SKIP LOCKED` menginstruksikan PostgreSQL untuk melompati baris yang sedang dikunci oleh transaksi lain, mencegah pemblokiran thread antar-goroutine worker.

### Pola Caching & Mitigasi Penalti Sistem
1. **Cache-Aside (Lazy Loading):** Aplikasi mencari data di cache terlebih dahulu. Jika *miss*, aplikasi mengambil dari DB, menyimpannya di cache, lalu mengembalikannya ke user.
2. **Cache Stampede (Thundering Herd):** Terjadi saat key cache yang sangat populer (*hot key*) kedaluwarsa (*expired*), dan ribuan goroutine konkuren secara simultan mendeteksi *cache miss*, lalu secara serentak menghantam database utama dengan query berat yang sama.
   * *Solusi Go:* `singleflight.Group`. Komponen sinkronisasi ini menduplikasi eksekusi fungsi yang sedang berjalan dengan *key* yang sama sehingga hanya ada tepat **1 goroutine** yang mengeksekusi query database, sedangkan goroutine lain menunggu dan membaca hasil yang sama dari memori.
3. **Probabilistic Early Expiration (XFetch algorithm) / TTL Jitter:** Menambahkan variasi acak (*jitter*) pada TTL:
   $$\text{TTL}_{\text{effective}} = \text{TTL}_{\text{base}} + \text{rand}(0, \text{jitter})$$
   Trik ini mencegah banyak key yang dibuat bersamaan kedaluwarsa pada detik yang sama secara massal.

### Semantik Pengiriman Pesan Kafka
* **At-most-once:** Commit offset sebelum pesan diproses. Jika pemrosesan gagal/crash, pesan hilang.
* **At-least-once:** Proses pesan terlebih dahulu, pastikan sukses, baru lakukan commit offset. Jika aplikasi crash di tengah eksekusi, pesan akan dikirim ulang (*redelivery*). **Konsekuensi:** Consumer harus **Idempoten**.
* **Idempotency Strategy:** Simpan ID unik pesan (*UUID/Deduplication Key*) di distributed storage (Postgres/Redis) dengan validasi atomic lock:
  ```sql
  INSERT INTO processed_events (event_id, processed_at) VALUES ($1, NOW()) ON CONFLICT (event_id) DO NOTHING;
  ```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental: Mengonfigurasi `database/sql` connection pool, Redis client dengan *connection pooling*, dan Kafka Reader/Writer secara murni di Go.

```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net"
	"strconv"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
)

// InfrastructureConfig menyimpan dependensi infrastruktur terpadu.
type InfrastructureConfig struct {
	DB    *sql.DB
	Redis *redis.Client
}

// InitDatabasePool menginisialisasi PostgreSQL connection pool dengan parameter aman.
func InitDatabasePool(dsn string) (*sql.DB, error) {
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		return nil, fmt.Errorf("gagal parsing DSN: %w", err)
	}

	// Konfigurasi pool produksi
	db.SetMaxOpenConns(25)                 // Batas mutlak koneksi terbuka simultan
	db.SetMaxIdleConns(10)                 // Koneksi standby di pool
	db.SetConnMaxLifetime(30 * time.Minute) // Daur ulang koneksi untuk refresh state firewall/LB
	db.SetConnMaxIdleTime(5 * time.Minute)  // Putus koneksi idle yang tidak terpakai

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("koneksi database gagal (ping timeout): %w", err)
	}

	return db, nil
}

// InitRedisClient menginisialisasi Redis client pool.
func InitRedisClient(addr string, password string, dbIndex int) (*redis.Client, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:         addr,
		Password:     password,
		DB:           dbIndex,
		PoolSize:     50,               // Maksimum koneksi socket konkuren
		MinIdleConns: 10,               // Minimal koneksi standby
		DialTimeout:  3 * time.Second,  // Timeout koneksi awal
		ReadTimeout:  1 * time.Second,  // Batas toleransi operasi GET
		WriteTimeout: 1 * time.Second,  // Batas toleransi operasi SET
	})

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("koneksi redis gagal: %w", err)
	}

	return rdb, nil
}

// InitKafkaWriter menginisialisasi pipeline produser pesan Kafka.
func InitKafkaWriter(brokerAddr string, topic string) *kafka.Writer {
	return &kafka.Writer{
		Addr:         kafka.TCP(brokerAddr),
		Topic:        topic,
		Balancer:     &kafka.LeastBytes{}, // Load balancing berbasis ukuran payload
		BatchSize:    100,                 // Kirim pesan per batch
		BatchTimeout: 10 * time.Millisecond,
		WriteTimeout: 5 * time.Second,
		RequiredAcks: kafka.RequireAll,    // Menjamin durabilitas: semua replica harus ACK
	}
}

// InitKafkaReader menginisialisasi Kafka consumer group.
func InitKafkaReader(brokerAddr, topic, groupID string) *kafka.Reader {
	return kafka.NewReader(kafka.ReaderConfig{
		Brokers:        []string{brokerAddr},
		GroupID:        groupID,
		Topic:          topic,
		MinBytes:       10e3, // 10KB fetch minimum
		MaxBytes:       10e6, // 10MB fetch maximum
		CommitInterval: 0,    // 0 = Manual commit untuk At-Least-Once delivery eksplisit
		Dialer: &kafka.Dialer{
			Timeout:   10 * time.Second,
			DualStack: true,
		},
	})
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode fundamental di Seksi 07:

1. **`db.SetMaxOpenConns(25)`:** Mengontrol batas atas alokasi socket TCP ke PostgreSQL. Mengapa 25? PostgreSQL menggunakan model *process-per-connection*. Terlalu banyak koneksi terbuka bersamaan (misalnya 1000) akan membebani CPU database akibat *context switching* memori internal engine Postgres.
2. **`db.SetConnMaxLifetime(30 * time.Minute)`:** Batas usia maksimum sebuah koneksi. Komponen jaringan intermediate (AWS NLB, Azure Load Balancer, Router NAT) sering kali menutup koneksi idle secara sepihak (*TCP drop/RST*) tanpa memberi tahu driver klien. Daur ulang berkala mencegah eksekusi query pada *zombie/dead sockets*.
3. **`PoolSize: 50` pada Redis Options:** Menghindari alokasi dinamis berulang yang memicu GC pressure. Pool connection pre-allocated memastikan ketersediaan koneksi instan saat lonjakan request tiba.
4. **`RequiredAcks: kafka.RequireAll` (-1 / all in Kafka spec):** Memberikan jaminan integritas tingkat tertinggi. Broker utama (*leader partition*) tidak akan mengirim balasan sukses sebelum data berhasil disinkronkan ke seluruh replika aktif (*In-Sync Replicas / ISR*).
5. **`CommitInterval: 0` pada Kafka Reader:** Menonaktifkan *auto-commit background routine*. Offset hanya boleh bergeser maju jika aplikasi telah berhasil memproses muatan data secara utuh, mencegah data hilang saat terjadi panic runtime di dalam loop aplikasi.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Payment Settlement & Notification Architecture
**Permasalahan:** Sebuah platform E-Commerce memproses transaksi pembayaran secara massal. Sistem harus:
1. Menyimpan status transaksi `orders` secara atomik di database Postgres.
2. Menghindari pembatalan order akibat kegagalan Kafka broker (ketersediaan broker tidak boleh memblokir transaksi pembayaran).
3. Mencegah read load menghantam database saat ribuan pengguna memeriksa status checkout mereka secara terus-menerus.
4. Mengirimkan event `OrderSettled` ke Kafka secara andal untuk dikonsumsi oleh layanan Akuntansi (*Invoicing Service*) dan Layanan Notifikasi Email.

### Rancangan Solusi:
* Gunakan **Transactional Outbox Pattern**: Data order dan event outbox disimpan dalam **satu transaksi database lokal** (ACID).
* Sebuah goroutine terisolasi (**Outbox Worker**) membaca event berstatus `PENDING` dengan kueri non-blocking (`FOR UPDATE SKIP LOCKED`), mengirimkannya ke Kafka, lalu menandainya sebagai `PROCESSED`.
* Jalur baca (**Read Path**) dilindungi oleh Redis cache dengan **Singleflight** untuk mencegah *Cache Stampede*.
* Sisi consumer menerapkan **Deduplication Gate** berbasis PostgreSQL untuk mencapai semantik *idempotent handling*.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah sistem lengkap yang siap dijalankan, memadukan persistence, outbox polling worker, redis caching dengan singleflight, dan idempotent consumer.

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
	"sync"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
	"golang.org/x/sync/singleflight"
)

// --- MODELS & STRUCTS ---

type Order struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type OutboxEvent struct {
	ID            int64     `json:"id"`
	AggregateType string    `json:"aggregate_type"`
	AggregateID   string    `json:"aggregate_id"`
	Payload       string    `json:"payload"`
	Status        string    `json:"status"`
	CreatedAt     time.Time `json:"created_at"`
}

// OrderService bertindak sebagai pengendali utama alur domain.
type OrderService struct {
	db          *sql.DB
	redis       *redis.Client
	kafkaWriter *kafka.Writer
	sfGroup     singleflight.Group
}

func NewOrderService(db *sql.DB, rdb *redis.Client, kw *kafka.Writer) *OrderService {
	return &OrderService{
		db:          db,
		redis:       rdb,
		kafkaWriter: kw,
	}
}

// --- WRITE PATH DENGAN TRANSACTIONAL OUTBOX ---

func (s *OrderService) CreateOrder(ctx context.Context, order Order) error {
	tx, err := s.db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelReadCommitted})
	if err != nil {
		return fmt.Errorf("gagal memulai transaksi: %w", err)
	}
	defer tx.Rollback() // Aman dipanggil; diabaikan jika Commit sukses

	// 1. Simpan Order ke Database
	orderQuery := `INSERT INTO orders (id, user_id, amount, status, created_at) 
	               VALUES ($1, $2, $3, $4, $5)`
	_, err = tx.ExecContext(ctx, orderQuery, order.ID, order.UserID, order.Amount, order.Status, order.CreatedAt)
	if err != nil {
		return fmt.Errorf("gagal insert order: %w", err)
	}

	// 2. Serialisasi data order untuk outbox payload
	payloadBytes, err := json.Marshal(order)
	if err != nil {
		return fmt.Errorf("gagal marshal outbox payload: %w", err)
	}

	// 3. Simpan Event ke Outbox Table pada transaksi DB yang SAMA
	outboxQuery := `INSERT INTO outbox_events (aggregate_type, aggregate_id, payload, status, created_at) 
	                VALUES ($1, $2, $3, 'PENDING', $4)`
	_, err = tx.ExecContext(ctx, outboxQuery, "ORDER", order.ID, string(payloadBytes), time.Now())
	if err != nil {
		return fmt.Errorf("gagal insert outbox event: %w", err)
	}

	// Commit transaksi ACID
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("gagal commit database: %w", err)
	}

	return nil
}

// --- BACKGROUND OUTBOX RELAY WORKER ---

func (s *OrderService) StartOutboxWorker(ctx context.Context) {
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("Menghentikan outbox worker...")
			return
		case <-ticker.C:
			s.processOutboxBatch(ctx)
		}
	}
}

func (s *OrderService) processOutboxBatch(ctx context.Context) {
	// Menggunakan FOR UPDATE SKIP LOCKED untuk menghindari race condition antar replica worker
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		log.Printf("[Outbox] Gagal start tx: %v\n", err)
		return
	}
	defer tx.Rollback()

	query := `SELECT id, aggregate_id, payload 
	          FROM outbox_events 
	          WHERE status = 'PENDING' 
	          ORDER BY id ASC 
	          LIMIT 20 
	          FOR UPDATE SKIP LOCKED`

	rows, err := tx.QueryContext(ctx, query)
	if err != nil {
		log.Printf("[Outbox] Gagal query events: %v\n", err)
		return
	}
	defer rows.Close()

	type eventToPublish struct {
		id          int64
		aggregateID string
		payload     string
	}
	var events []eventToPublish

	for rows.Next() {
		var e eventToPublish
		if err := rows.Scan(&e.id, &e.aggregateID, &e.payload); err != nil {
			log.Printf("[Outbox] Scan error: %v\n", err)
			return
		}
		events = append(events, e)
	}

	if len(events) == 0 {
		return
	}

	var kafkaMessages []kafka.Message
	for _, e := range events {
		kafkaMessages = append(kafkaMessages, kafka.Message{
			Key:   []byte(e.aggregateID),
			Value: []byte(e.payload),
			Time:  time.Now(),
		})
	}

	// Publish ke broker Kafka
	err = s.kafkaWriter.WriteMessages(ctx, kafkaMessages...)
	if err != nil {
		log.Printf("[Outbox] Broker publish gagal: %v\n", err)
		return
	}

	// Update status outbox menjadi PROCESSED
	for _, e := range events {
		_, err := tx.ExecContext(ctx, `UPDATE outbox_events SET status = 'PROCESSED' WHERE id = $1`, e.id)
		if err != nil {
			log.Printf("[Outbox] Update status gagal: %v\n", err)
			return
		}
	}

	if err := tx.Commit(); err != nil {
		log.Printf("[Outbox] Commit update outbox gagal: %v\n", err)
	}
}

// --- READ PATH: CACHE-ASIDE + SINGLEFLIGHT ---

func (s *OrderService) GetOrderByID(ctx context.Context, orderID string) (*Order, error) {
	cacheKey := fmt.Sprintf("order:%s", orderID)

	// 1. Coba ambil dari Cache Redis
	val, err := s.redis.Get(ctx, cacheKey).Result()
	if err == nil {
		var cachedOrder Order
		if err := json.Unmarshal([]byte(val), &cachedOrder); err == nil {
			return &cachedOrder, nil
		}
	} else if !errors.Is(err, redis.Nil) {
		// Log error jika redis mati, namun teruskan eksekusi fallback ke DB
		log.Printf("[Redis Warning] gagal get data: %v\n", err)
	}

	// 2. Cache Miss: Gunakan Singleflight untuk melindungi database dari thundering herd
	result, err, _ := s.sfGroup.Do(orderID, func() (interface{}, error) {
		// Query database utama
		query := `SELECT id, user_id, amount, status, created_at FROM orders WHERE id = $1`
		var ord Order
		err := s.db.QueryRowContext(ctx, query, orderID).Scan(
			&ord.ID, &ord.UserID, &ord.Amount, &ord.Status, &ord.CreatedAt,
		)
		if err != nil {
			return nil, err
		}

		// Hitung TTL dengan Jitter (Mencegah sinkronisasi kedaluwarsa serempak)
		baseTTL := 15 * time.Minute
		jitter := time.Duration(rand.Intn(180)) * time.Second
		effectiveTTL := baseTTL + jitter

		// Simpan kembali ke Redis secara asinkron (non-blocking untuk caller)
		payload, err := json.Marshal(ord)
		if err == nil {
			_ = s.redis.Set(context.Background(), cacheKey, payload, effectiveTTL).Err()
		}

		return &ord, nil
	})

	if err != nil {
		return nil, fmt.Errorf("database query error: %w", err)
	}

	return result.(*Order), nil
}

// --- CONSUMER PATH: IDEMPOTENT PROCESSING ---

func StartIdempotentConsumer(ctx context.Context, reader *kafka.Reader, db *sql.DB) {
	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) {
				return
			}
			log.Printf("[Consumer] Fetch error: %v\n", err)
			continue
		}

		// Eksekusi logic dengan idempotency check
		err = processEventAtomically(ctx, db, msg)
		if err != nil {
			log.Printf("[Consumer] Gagal proses event id %s: %v\n", string(msg.Key), err)
			// Jangan commit offset, biarkan redelivery atau route ke DLQ
			continue
		}

		// Commit offset manual setelah proses berhasil (At-Least-Once safety)
		if err := reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("[Consumer] Offset commit failed: %v\n", err)
		}
	}
}

func processEventAtomically(ctx context.Context, db *sql.DB, msg kafka.Message) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// 1. Cek idempotensi menggunakan tabel riwayat deduplikasi
	// Gunakan message identifier (Key atau custom UUID dari Kafka header)
	eventKey := string(msg.Key)
	res, err := tx.ExecContext(ctx, 
		`INSERT INTO processed_events (event_id, processed_at) VALUES ($1, NOW()) ON CONFLICT (event_id) DO NOTHING`, 
		eventKey,
	)
	if err != nil {
		return fmt.Errorf("deduplication check query failed: %w", err)
	}

	rowsAffected, err := res.RowsAffected()
	if err != nil {
		return err
	}

	// Jika rowsAffected == 0, event ini SUDAH PERNAH diproses sebelumnya! Abaikan operasi downstream.
	if rowsAffected == 0 {
		log.Printf("[Consumer Deduplication] Event %s telah diproses sebelumnya. Melewati mutasi data.\n", eventKey)
		return tx.Commit()
	}

	// 2. Eksekusi Business Logic Konsumen (Contoh: Potong limit/Kirim Invoicing)
	var ord Order
	if err := json.Unmarshal(msg.Value, &ord); err != nil {
		return fmt.Errorf("unmarshal error: %w", err)
	}

	// Simulasi mutasi state lain...
	_, err = tx.ExecContext(ctx, 
		`INSERT INTO audit_invoices (order_id, user_id, settled_amount) VALUES ($1, $2, $3)`,
		ord.ID, ord.UserID, ord.Amount,
	)
	if err != nil {
		return fmt.Errorf("invoicing record error: %w", err)
	}

	return tx.Commit()
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Pola Konsistensi Cache: Cache-Aside vs Write-Through vs Write-Back

| Parameter | Cache-Aside (Lazy) | Write-Through | Write-Back (Write-Behind) |
| :--- | :--- | :--- | :--- |
| **Resistensi Data Loss** | **Sangat Tinggi** (Source of Truth langsung tersimpan di DB) | **Sangat Tinggi** (Data ditulis sinkron ke Cache & DB) | **Rendah** (Data hanya di RAM dulu, rawan crash) |
| **Latensi Tulis** | **Rendah-Sedang** (Hanya tulis ke DB + evict cache) | **Tinggi** (Menunggu 2x network round-trip DB & Cache) | **Sangat Rendah** (Langsung simpan di cache memori) |
| **Risiko Stale Read** | Ada (Window time antara update DB dan Redis invalidation) | Sangat Rendah | Sangat Tinggi (Jika worker sync DB macet) |
| **Kompleksitas Kode** | Rendah / Modular | Sedang | Sangat Tinggi (Perlu buffer queue persistensi memori) |

### Outbox Pattern: Table Polling Engine vs CDC (Change Data Capture / Debezium)

| Kriteria Evaluasi | Polling Publisher (`SKIP LOCKED`) | CDC Engine (Debezium + Postgres WAL) |
| :--- | :--- | :--- |
| **Overhead Database** | Menghasilkan kueri `SELECT`/`UPDATE` periodik pada disk I/O. | Nyaris nol query SQL; membaca native Postgres WAL (*Write-Ahead Log*). |
| **Latensi Propagasi** | Dibatasi oleh interval polling (misal 500ms - 1s). | Real-time / Sub-detik (*near-instant streaming*). |
| **Ketergantungan Infra**| **Murni Go Runtime** (Tidak butuh dependensi eksternal). | Butuh cluster Apache Kafka Connect, JVM, & ZooKeeper/KRaft. |
| **Operasional & DevOps** | Sangat sederhana, mudah di-deploy via container standard. | Sangat kompleks; migrasi skema tabel butuh sinkronisasi ketat. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Transaction Leak via Unhandled Error / Early Return:**
   Jika Anda memanggil `tx, _ := db.Begin()` tanpa menyertakan `defer tx.Rollback()`, lalu terjadi `return err` di tengah percabangan kode, transaksi tersebut akan menggantung (*idle in transaction*). Hal ini mengunci tabel dan menahan alokasi memori PostgreSQL secara permanen.
2. **Redis Failover / Out-of-Memory (OOM):**
   Ketika instance Redis mengalami saturasi RAM dan mencapai `maxmemory`, Redis dapat menolak penulisan (`OOM command not allowed`). Kode Go harus menangani skenario ini sebagai degradasi halus (*graceful degradation*): catat *error*, jangan panic, dan biarkan sistem tetap melayani baca/tulis langsung ke PostgreSQL.
3. **Kafka Head-of-Line Blocking pada Consumer Retry:**
   Jika sebuah pesan rusak (*poison pill payload*) gagal diproses dan consumer terus mencoba kembali tanpa batas (*infinite retry*), seluruh antrean partisi akan terhenti total. Solusi: Gunakan skema **Dead Letter Queue (DLQ)** setelah $N$ kali kegagalan (*threshold max retry*).
4. **Driver Goroutine Leakage akibat `rows.Close()` Terlewat:**
   ```go
   rows, err := db.QueryContext(ctx, "SELECT ...")
   if err != nil { return err }
   // JIKA LUPA DEFER rows.Close() DI SINI:
   // Koneksi TCP underlying tidak pernah dikembalikan ke pool.
   // Seluruh pool akan hang saat mencapai MaxOpenConns.
   defer rows.Close()
   ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Injeksi Konteks Kosong (`context.Background()` di Request Path)
* **Kesalahan Fatal:** Menggunakan `context.Background()` saat mengeksekusi query database di dalam handler HTTP.
* **Dampak Buruk:** Ketika klien membatalkan request atau koneksi putus (misal menutup browser), PostgreSQL tetap memproses query berat tersebut hingga selesai, membuang sumber daya komputasi.
* **Perbaikan:** Selalu teruskan `r.Context()` dari HTTP request handler ke seluruh lapisan `db.QueryContext` dan `rdb.Get(ctx)`.

### 2. Mutasi Cache Tanpa Penanganan Invalidasi Bersamaan (*Race Condition*)
* **Kesalahan Fatal:** Menggunakan alur `Update DB -> Set Cache Baru`.
* **Dampak Buruk:** Jika Request A dan Request B mengeksekusi pembaruan hampir bersamaan, urutan penulisan di Redis dapat terbalik akibat jitter jaringan, menyebabkan data usang (*stale data*) tersimpan di cache dalam jangka panjang.
* **Perbaikan:** Terapkan pola **Cache Invalidation (Eviction)**: Jangan update nilai cache; cukup panggil `rdb.Del(ctx, cacheKey)` setelah transaksi database commit.

### 3. Asumsi Urutan Partisi Global pada Kafka
* **Kesalahan Fatal:** Mengira pesan di Kafka terurut secara absolut di seluruh broker.
* **Dampak Buruk:** Order status `CREATED` dan `CANCELLED` dapat diproses terbalik jika pesan dikirim ke partisi yang berbeda.
* **Perbaikan:** Tetapkan `Key` partisi secara deterministik (contoh: gunakan `order_id` sebagai pesan key). Kafka menjamin pengurutan strictly ordered **hanya di dalam partisi yang sama**.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Desain DTO Terpisah untuk Persistensi & Streaming:**
   Jangan pernah menggunakan struct entitas database (`ORM model`) secara langsung sebagai kontrak schema event Kafka. Ubah struktur internal menjadi skema payload event domain eksplisit (`OrderSettledEventV1`) agar refaktorisasi skema DB tidak merusak downstream consumer.
2. **Gunakan String Query SQL Statis (Prepared Statements Safe):**
   Hindari konkatenasi string SQL (`fmt.Sprintf("SELECT * FROM users WHERE id = %s", id)`). Selalu manfaatkan parameter binding (`$1, $2` atau `?`) untuk mencegah **SQL Injection** dan mengizinkan database engine memanfaatkan eksekusi query plan yang telah di-cache.
3. **Skema Penamaan Metrik & Kunci Redis Terstruktur:**
   Format key Redis wajib mengikuti konvensi namespace yang jelas dan modular:
   $$\text{Format:} \quad \langle\text{service}\rangle:\langle\text{domain}\rangle:\langle\text{identifier}\rangle:\langle\text{field}\rangle$$
   *Contoh:* `ordersvc:order:ord-992104:details`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Optimasi 1: PostgreSQL Batch Insertion
Hindari insert data dalam loop satu per satu. Gunakan fitur *Unnest* PostgreSQL atau syntax multi-row insert:

```go
// OPTIMAL: 1 Round-Trip Jaringan untuk N data
func BatchInsertOrders(ctx context.Context, db *sql.DB, orders []Order) error {
    query := `INSERT INTO orders (id, user_id, amount, status) 
              SELECT * FROM UNNEST($1::text[], $2::text[], $3::numeric[], $4::text[])`
    
    ids := make([]string, len(orders))
    userIDs := make([]string, len(orders))
    amounts := make([]float64, len(orders))
    statuses := make([]string, len(orders))

    for i, o := range orders {
        ids[i] = o.ID
        userIDs[i] = o.UserID
        amounts[i] = o.Amount
        statuses[i] = o.Status
    }

    _, err := db.ExecContext(ctx, query, ids, userIDs, amounts, statuses)
    return err
}
```

### Optimasi 2: Mencegah Heap Escape pada JSON Unmarshaling
Ketika membaca jutaan event Kafka, hindari mengalokasikan struct baru di heap secara terus-menerus. Gunakan `sync.Pool` untuk mendaur ulang slice buffer atau objek penampung parser jika throughput melebihi 50.000 RPS.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Enkripsi Transit (mTLS):** Wajibkan konfigurasi `*tls.Config` pada koneksi database PostgreSQL, cluster Redis, dan Kafka Broker di level production. Jangan pernah mengizinkan parameter koneksi `sslmode=disable` di luar environment pengujian unit test lokal.
2. **Sanitasi Kredensial pada Error Log:** Driver Go sering kali mencantumkan DSN lengkap beserta plaintext password saat mencetak koneksi error (`dial tcp: connect: connection refused`). Bungkus (*mask/sanitize*) error tersebut sebelum diteruskan ke pipeline log terbuka:
   ```go
   // Parsing DSN dan sembunyikan password sebelum log
   u, err := url.Parse(dsn)
   if err == nil {
       log.Printf("Connecting to database host: %s with user: %s", u.Host, u.User.Username())
   }
   ```
3. **Prinsip Least Privilege SQL User:** User aplikasi Go tidak boleh memiliki izin level DDL (`DROP TABLE`, `ALTER TABLE`). Batasi akun aplikasi runtime hanya dengan hak akses `SELECT`, `INSERT`, `UPDATE`, dan `DELETE`. Migrasi skema database harus dijalankan secara independen melalui CI/CD pipeline menggunakan akun terpisah (*admin/migrator*).

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk mendeteksi performa buruk dan potensi masalah sedini mungkin, Anda wajib mengekspos metrik koneksi secara berkala ke sistem monitoring seperti Prometheus:

```go
func MonitorDBStats(db *sql.DB, interval time.Duration) {
	ticker := time.NewTicker(interval)
	go func() {
		for range ticker.C {
			stats := db.Stats()
			// Laporkan ke Prometheus Gauge atau Structured Logger
			log.Printf("[DB POOL STATS] OpenConnections=%d, InUse=%d, Idle=%d, WaitCount=%d, WaitDuration=%v",
				stats.OpenConnections,
				stats.InUse,
				stats.Idle,
				stats.WaitCount,
				stats.WaitDuration,
			)
			
			// Deteksi tanda-tanda kehabisan koneksi (starvation)
			if stats.WaitDuration > 1*time.Second {
				log.Println("[CRITICAL ALERT] Goroutines mengalami blocking antrean koneksi database lebih dari 1 detik!")
			}
		}
	}()
}
```

Implementasikan pula OpenTelemetry tracing pada Kafka message headers menggunakan context carrier untuk melacak siklus hidup request dari API Gateway, Database, hingga Kafka Consumer downstream secara terdistribusi.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ GOLANG HIGH PERFORMANCE DATA PIPELINE CHEAT SHEET                                      │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ database/sql Best Config │ SetMaxOpenConns(25-100), SetMaxIdleConns(MaxOpen/2),        │
│                          │ SetConnMaxLifetime(30m), SetConnMaxIdleTime(5m).            │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ rows.Close() Mandate     │ Selalu panggil via defer langsung setelah penanganan error! │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Anti-Cache Stampede      │ Bungkus pengambilan data miss dengan singleflight.Group.    │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ TTL Strategy             │ Tambahkan Random Jitter: TTL = BaseTTL + rand(0, Jitter).   │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Dual-Write Mitigation    │ Transactional Outbox Pattern + SKIP LOCKED polling.         │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Kafka Delivery Guarantee │ At-Least-Once (Manual Commit) + Idempotent Table di DB.     │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Basic (1-5)

1. **Apa yang terjadi secara internal jika aplikasi memanggil `db.QueryContext` ketika seluruh koneksi di pool berstatus `InUse` dan nilai `MaxOpenConns` telah tercapai?**
   * A. Query otomatis dibatalkan dan langsung mengembalikan error koneksi.
   * B. Goroutine akan diblokir (*wait*) mengantre hingga ada koneksi yang dikembalikan atau context mengalami timeout.
   * C. Pool akan membuka koneksi baru darurat sementara yang mengabaikan batas limit.
   * D. Database engine PostgreSQL akan mematikan koneksi klien tertua.

2. **Mengapa penutupan resource query `rows.Close()` sangat penting ditempatkan di dalam fungsi yang menggunakan `database/sql`?**
   * A. Untuk membersihkan alokasi memori query string di stack Go.
   * B. Karena jika tidak dipanggil, koneksi TCP database tetap terkunci dan tidak bisa kembali ke pool idle.
   * C. Untuk memerintahkan PostgreSQL mengeksekusi perintah auto-commit.
   * D. Karena garbage collector Go tidak bisa mengosongkan interface pointer.

3. **Apa tujuan utama penambahan nilai acak (*jitter*) pada konfigurasi TTL saat menyimpan cache ke Redis?**
   * A. Mencegah Redis kehabisan memori.
   * B. Mempercepat encoding payload JSON.
   * C. Mencegah banyak key kedaluwarsa serempak yang memicu fenomena cache stampede.
   * D. Mengamankan data dari serangan distributed timing attack.

4. **Kapan waktu yang tepat untuk melakukan commit message offset pada consumer Kafka yang mengadopsi semantik *at-least-once*?**
   * A. Tepat sebelum payload pesan dibaca dari socket.
   * B. Segera setelah pesan berhasil diterima di buffer memori aplikasi.
   * C. Di background routine secara interval berkala tanpa memperhatikan status pemrosesan.
   * D. Hanya setelah seluruh proses bisnis dan penyimpanan data pesan berhasil dijalankan tanpa error.

5. **Apa fungsi dari package `golang.org/x/sync/singleflight`?**
   * A. Membatasi aplikasi agar hanya berjalan di 1 thread CPU OS.
   * B. Menyatukan eksekusi fungsi duplikat yang berjalan bersamaan sehingga hanya satu fungsi yang dipanggil.
   * C. Mengubah koneksi TCP biasa menjadi koneksi multiplexed HTTP/2.
   * D. Melakukan enkripsi otomatis pada pesan Kafka.

### Soal Tingkat Intermediate (6-10)

6. **Mengapa pemanggilan `rdb.Del(ctx, key)` (Cache Invalidation) lebih disukai daripada `rdb.Set(ctx, key, newData, ttl)` sesaat setelah mutasi data di database SQL berhasil?**
   * A. Eksekusi `DEL` di Redis jauh lebih cepat daripada alokasi memori `SET`.
   * B. Menghindari race condition antar-request update konkuren yang dapat menimpa data Redis dengan urutan yang salah.
   * C. Karena Redis tidak mendukung update inplace untuk key bertipe JSON string.
   * D. Untuk menghemat bandwidth jaringan ingress pada server Redis.

7. **Mengapa query outbox worker wajib menyertakan klausa SQL `FOR UPDATE SKIP LOCKED`?**
   * A. Untuk mengurutkan pemrosesan data event berdasarkan ID secara descending.
   * B. Agar row data event yang sedang diproses oleh satu worker instance tidak dibaca atau dikunci oleh worker instance lain yang berjalan paralel.
   * C. Untuk memaksa query menggunakan indeks primary key B-Tree.
   * D. Menjamin PostgreSQL tidak mencatat transaksi ini ke Write-Ahead Log (WAL).

8. **Manakah konfigurasi `kafka.Writer` yang memastikan bahwa sebuah pesan tidak akan hilang meskipun broker leader mengalami kegagalan hardware mendadak setelah menerima pesan?**
   * A. `RequiredAcks: kafka.RequireNone`
   * B. `RequiredAcks: kafka.RequireOne`
   * C. `RequiredAcks: kafka.RequireAll` dipadukan dengan konfigurasi broker `min.insync.replicas >= 2`
   * D. `Balancer: &kafka.Hash{}`

9. **Jika Redis mengalami down/crash total di production, bagaimana seharusnya kode Go di layer repositori bereaksi dalam arsitektur Cache-Aside yang tangguh?**
   * A. Melemparkan panic runtime dan menghentikan seluruh proses container Go.
   * B. Mengembalikan status HTTP 500 Internal Server Error ke user sampai Redis pulih.
   * C. Mencatat error Redis sebagai log warning, lalu melakukan fallback mengambil data langsung dari PostgreSQL.
   * D. Mengulangi pemanggilan Redis secara sinkron tanpa jeda waktu timeout.

10. **Bagaimana cara paling efektif untuk mengimplementasikan deduplikasi pesan yang idempoten pada consumer Kafka di level database PostgreSQL?**
    * A. Menghapus tabel data lama setiap kali pesan baru tiba.
    * B. Membaca seluruh baris database ke memory slice Go lalu memvalidasinya dengan linear search.
    * C. Menyimpan identifier unik event ke tabel deduplikasi menggunakan query `INSERT ... ON CONFLICT (event_id) DO NOTHING` dalam transaksi yang sama.
    * D. Mengandalkan partition key Kafka semata tanpa pelacakan database tambahan.

---

### Kunci Jawaban & Pembahasan

* **1: B** — Ketika connection pool telah mencapai batas `MaxOpenConns`, pemanggilan query baru akan menunggu secara non-blocking di antrean `connRequests` sampai context timeout atau koneksi idle tersedia kembali.
* **2: B** — Koneksi database yang diasosiasikan dengan instance `rows` tidak akan dikembalikan ke pool sebelum `rows.Close()` dipanggil secara eksplisit, menyebabkan *connection leak*.
* **3: C** — TTL Jitter mendistribusikan waktu kedaluwarsa key secara stokastik di seluruh rentang waktu sehingga beban database tidak memuncak drastis secara tiba-tiba saat key kedaluwarsa.
* **4: D** — At-least-once menjamin tidak ada data yang hilang; dengan demikian offset hanya boleh di-commit setelah pekerjaan bisnis benar-benar tuntas diselesaikan.
* **5: B** — `singleflight` menekan *thundering herd* dengan memastikan hanya satu goroutine yang mengeksekusi operasi mahal (misalnya query database) untuk ID yang sama dalam kurun waktu bersamaan.
* **6: B** — Jika dua request update berjalan bersamaan, jeda jaringan dapat membuat instruksi `SET` versi lama tereksekusi belakangan setelah instruksi baru, menyebabkan inkonsistensi cache. Invalidation (`DEL`) memusnahkan risiko ini.
* **7: B** — `SKIP LOCKED` memungkinkan beberapa instance background worker memproses antrean outbox secara paralel dari database yang sama tanpa terkendala *lock contention* atau memproses event yang identik.
* **8: C** — `RequireAll` menjamin data telah tersimpan di node leader sekaligus seluruh replica aktif (*in-sync*) sebelum broker mengirim acknowledgment ke produser Go.
* **9: C** — Cache adalah layer akselerasi, bukan *source of truth*. Gangguan pada sistem caching semestinya menurunkan performa (*graceful degradation*), bukan menghentikan ketersediaan layanan sistem secara keseluruhan.
* **10: C** — Memanfaatkan fitur integritas struktural database relasional (`UNIQUE constraint` dan atomic upsert) adalah cara paling aman untuk memastikan satu pesan Kafka tidak pernah dieksekusi lebih dari satu kali (*idempotent execution*).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Proyek:
Rancang dan bangun sebuah service terintegrasi berskala produksi bernama **"FlashSale Engine"** menggunakan Go.

### Persyaratan Fungsional & Spesifikasi Sistem:
1. **Database Schema (PostgreSQL):**
   * Buat tabel `inventory` (`item_id` VARCHAR PRIMARY KEY, `stock` INT CHECK (stock >= 0)).
   * Buat tabel `orders` (`order_id` VARCHAR PRIMARY KEY, `item_id` VARCHAR, `user_id` VARCHAR, `created_at` TIMESTAMPTZ).
   * Buat tabel `outbox_events` (`id` BIGSERIAL PRIMARY KEY, `payload` JSONB, `status` VARCHAR, `created_at` TIMESTAMPTZ).
   * Buat tabel `processed_events` (`event_id` VARCHAR PRIMARY KEY, `processed_at` TIMESTAMPTZ).
2. **Flash-Sale Endpoint (`POST /checkout`):**
   * Gunakan Transaksi PostgreSQL untuk memotong stock:
     ```sql
     UPDATE inventory SET stock = stock - 1 WHERE item_id = $1 AND stock > 0;
     ```
   * Jika baris terupdate = 0, kembalikan HTTP status `410 Gone` (Stock Habis).
   * Jika berhasil, buat record di tabel `orders` dan record event di `outbox_events` dalam satu transaksi atomik.
3. **Outbox Engine Goroutine:**
   * Bangun loop pekerja background yang membaca tabel `outbox_events` setiap 250ms dengan `FOR UPDATE SKIP LOCKED`.
   * Terbitkan data ke Kafka broker pada topic `flashsale-orders`.
   * Tandai status event menjadi `PROCESSED`.
4. **Caching & Anti-Stampede Protection:**
   * Implementasikan endpoint `GET /inventory/{item_id}`.
   * Simpan data stok di Redis dengan TTL 60 detik + Jitter random (1-10 detik).
   * Bungkus kueri pembacaan database menggunakan `singleflight.Group` untuk menangani lonjakan pembacaan konkuren saat stok berubah.
5. **Uji Beban & Verifikasi Sistem (Load Testing):**
   * Gunakan tool benchmarking seperti `k6` atau `hey` untuk menembakkan 500 permintaan checkout secara simultan ke 1 unit stok barang yang sama.
   * **Target Keberhasilan:** Tepat 1 transaksi berhasil mendapatkan barang, 499 transaksi lainnya menerima respon stok habis, dan tepat 1 event outbox berhasil diterbitkan ke Kafka tanpa data race (`go run -race`).
6. **Graceful Shutdown Integration:**
   * Tangani sinyal termination OS (`SIGINT`, `SIGTERM`).
   * Pastikan aplikasi menutup `kafka.Writer`, mematikan Outbox Worker, mendrain koneksi pool `database/sql`, dan memutus koneksi Redis secara aman tanpa ada data yang menggantung di memori.