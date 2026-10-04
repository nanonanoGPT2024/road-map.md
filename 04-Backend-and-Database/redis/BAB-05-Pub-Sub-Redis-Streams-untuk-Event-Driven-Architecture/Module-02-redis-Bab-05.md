# Redis Bab 05 - Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut (*advanced production-grade*) untuk:

1. **Membedah Struktur Data Internal Redis Streams**: Memahami representasi memori *Radix Tree* (`rax`) dan *Listpack*, serta implikasi alokasi memori terhadap *throughput* I/O.
2. **Merancang Pipeline Konsumsi Skala Besar**: Mengimplementasikan *Consumer Groups*, *Pending Entries List* (PEL), dan pola *auto-claim* untuk menjamin semantik pengiriman *at-least-once* tanpa kebocoran memori.
3. **Membangun Sistem Resilien Anti-Poison-Pill**: Mengimplementasikan mekanisme *Dead-Letter Queue* (DLQ), *exponential backoff*, dan *idempotency engine* berkinerja tinggi menggunakan atomisitas Redis.
4. **Mengoperasikan Redis Streams di Skala Enterprise**: Menganalisis *trade-off* latensi dan retensi data (`MAXLEN ~`), strategi *cross-slot routing* pada Redis Cluster, serta optimasi *persistence* (AOF/RDB) untuk meminimalkan *data loss*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus telah menguasai:
* Pemahaman fundamental Redis Data Structures (String, Hash, Set, Sorted Set).
* Pemahaman konsep dasar Pub/Sub Redis (Publish, Subscribe, Pattern Subscribe) dan keterbatasannya (*fire-and-forget*, tiadanya *history* data).
* Dasar-dasar konkurensi (Thread/Goroutine, Channel, Mutex, Deadlock).
* Konsep *Event-Driven Architecture* (EDA), message broker patterns, dan *idempotent consumer*.
* Familiaritas dengan salah satu bahasa backend berkinerja tinggi (Go / TypeScript / Java / Rust). Modul ini menyediakan implementasi kode berbasis **Go (Golang)**.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Representasi Memori: Radix Tree (`rax`) dan Listpack

Redis Streams (`stream.h`) dirancang bukan sebagai *linked list* sederhana, melainkan gabungan struktur data hierarkis canggih: **Radix Tree (`rax`)** yang menampung simpul daun berupa **Listpack**.

```
+-------------------------------------------------------------------+
|                         Radix Tree (rax)                          |
|             (Key: Prefix 64-bit Timestamp ID / Epoch)             |
+---------------------------------+---------------------------------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
+-----------------------+                   +-----------------------+
|  Node A (Listpack)    |                   |  Node B (Listpack)    |
|  Entries [0..N]       |                   |  Entries [N+1..M]     |
| +-------------------+ |                   | +-------------------+ |
| | Master Entry:     | |                   | | Master Entry:     | |
| | Fields: [k1, k2]  | |                   | | Fields: [k1, k2]  | |
| +-------------------+ |                   | +-------------------+ |
| | ID: 1711900000-0  | |                   | | ID: 1711900005-0  | |
| | Flags | Diff | v1 | |                   | | Flags | Diff | v1 | |
| +-------------------+ |                   | +-------------------+ |
| | ID: 1711900000-1  | |                   | | ID: 1711900005-1  | |
| | Flags | Diff | v2 | |                   | | Flags | Diff | v2 | |
+-----------------------+                   +-----------------------+
```

1. **Radix Tree (`rax`)**:
   * Digunakan untuk mengindeks rentang waktu ID Stream (`<millisecondsTime>-<sequenceNumber>`).
   * Mengurangi *overhead* pointer memori 64-bit yang masif dibandingkan representasi B-Tree atau SkipList konvensional saat menyimpan kunci yang memiliki *prefix* waktu serupa.
2. **Listpack**:
   * Setiap daun (*leaf node*) dari Radix Tree menampung sejumlah pesan ke dalam satu blok memori contiguous (Listpack).
   * **Struktur Delta Compression**: Jika beberapa pesan berurutan memiliki field key yang sama (`{"user_id": "1", "event": "click"}`), nama field hanya ditulis satu kali dalam *Master Entry* listpack tersebut. Pesan-pesan selanjutnya hanya menyimpan perbedaan (delta) ID dan nilai spesifiknya.
   * Parameter engine: `stream-node-max-bytes` (default 4096 bytes) dan `stream-node-max-entries` (default 100 entries). Jika batas ini terlampaui, Redis memecah (*split*) node dan membuat Listpack baru di dalam Radix Tree.

### 3.2 Anatomy of Stream ID

Stream ID terdiri dari dua unsigned 64-bit integer:
$$\text{Stream ID} = \langle \text{millisecondsTime} \rangle - \langle \text{sequenceNumber} \rangle$$
* `millisecondsTime`: Unix epoch dalam milidetik dari jam server Redis.
* `sequenceNumber`: Penghitung inkremental monotonik untuk pesan yang tiba di milidetik yang sama.
* Sifat ini menjamin total urutan (*strictly monotonically increasing*), elemen krusial untuk replikasi deterministik dan konsistensi status *stream processing*.

### 3.3 Consumer Groups, PEL, dan State Tracking

Consumer Groups di Redis Streams mengadopsi model *distributed cursor* mirip Apache Kafka, namun dengan pelacakan individual per entri melalui data structure **Pending Entries List (PEL)**.

```
                      +-----------------------------+
                      |       XADD mystream         |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |         mystream            |
                      |  [E1, E2, E3, E4, E5, E6]   |
                      +--------------+--------------+
                                     |
            +------------------------+------------------------+
            | Group: "order-workers"                          |
            | Last Delivered ID: E4                           |
            +------------------------+------------------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
     +-----------------+                           +-----------------+
     | Consumer: C1    |                           | Consumer: C2    |
     | Reads: E1, E2   |                           | Reads: E3, E4   |
     +--------+--------+                           +--------+--------+
              |                                             |
              v                                             v
     +-----------------+                           +-----------------+
     |   PEL for C1    |                           |   PEL for C2    |
     | E1: time, redel |                           | E3: time, redel |
     | E2: time, redel |                           | E4: time, redel |
     +-----------------+                           +-----------------+
              |                                             |
           XACK E1                                     (Crash/Hang)
              |                                             |
              v                                             v
     +-----------------+                           +-----------------+
     | PEL: [E2]       |                           | E3 & E4 Stale!  |
     | (E1 dibebaskan) |                           | Butuh Claim     |
     +-----------------+                           +-----------------+
```

* **Last Delivered ID**: Pointer 64-bit yang mencatat ID pesan terakhir yang dibagikan ke consumer mana pun dalam grup tersebut. Ditugaskan saat consumer mengeksekusi `XREADGROUP ... >`.
* **Pending Entries List (PEL)**:
  * Setiap Consumer Group memiliki satu *global PEL*, dan setiap Consumer di dalam grup memiliki referensi subset ke *local PEL*.
  * Begitu pesan dikirimkan ke worker melalui `XREADGROUP`, ID pesan tersebut beserta metadata (waktu pengiriman terakhir, ID consumer pemilik, dan counter pengiriman) dimasukkan ke PEL.
  * Pesan **tidak dihapus dari PEL** sampai worker mengirimkan sinyal `XACK`.
  * *Memory Hazard*: Jika aplikasi membaca data tanpa pernah memanggil `XACK`, ukuran PEL akan terus membesar (*unbounded memory growth*), memicu *out-of-memory* (OOM) pada node Redis.

---

## 4. Why & What

| Fitur / Karakteristik | Redis Pub/Sub | Redis Lists (`LPUSH`/`RPOP`) | Redis Streams |
| :--- | :--- | :--- | :--- |
| **Model Pengiriman** | At-most-once (*fire-and-forget*) | At-least-once (jika dibantu temporary storage) | At-least-once (terkelola via PEL) |
| **Persistensi Data** | Tidak ada (pesan hilang jika client disconnect) | Tersimpan di memory/disk sampai di-pop | Persisten di memory/disk dengan retensi terkontrol |
| **Fanout Delivery** | Ya, broadcast ke semua subscriber | Tidak, single worker mengambil data | Ya, multiple Consumer Groups bisa membaca stream sama |
| **Load Balancing** | Tidak (semua client menerima pesan sama) | Ya (satu pesan hanya diambil satu worker) | Ya, diatur dalam batas Consumer Group |
| **State Inspection** | Nol (tidak ada rekam jejak) | Sangat terbatas (`LRANGE`) | Sangat tinggi (`XPENDING`, `XINFO`, `XRANGE`) |
| **Failure Recovery** | Mustahil | Butuh mekanisme custom (`RPOPLPUSH` / `LMOVE`) | Built-in via `XCLAIM` / `XAUTOCLAIM` |
| **Overhead Memori** | Nol (hanya transient buffer) | Rendah (Listpack/Quicklist) | Sedang-Tinggi (Listpack + Radix Tree + PEL) |

### Mengapa Menggunakan Redis Streams?
Redis Streams menjembatani kesenjangan antara kesederhanaan antrian Redis List dan kompleksitas operasional klaster Apache Kafka. Redis Streams memberikan kapabilitas:
1. **Sub-millisecond P99 Ingestion Latency**: Ideal untuk skenario transaksi real-time di mana latensi Kafka (yang berbasis disk I/O dan OS page cache flushing) dianggap terlalu lambat.
2. **Built-in Inspection & Tracking**: PEL memungkinkan sistem mendeteksi worker yang mati (*heartbeat decay*) dan mengklaim ulang pesan tanpa merusak urutan pesan global secara signifikan.
3. **Resource Efficiency**: Cocok untuk skala event volume rendah hingga menengah (puluhan juta event per hari) tanpa memerlukan koordinasi ZooKeeper/KRaft atau cluster JVM yang memakan banyak memori.

---

## 5. How (Workflow Detail)

Siklus hidup pemrosesan event terdistribusi dengan Redis Streams:

```
[Producer] 
    │
    │ 1. XADD mystream MAXLEN ~ 1000000 * payload {...}
    ▼
[Redis Stream] ── (ID Dibuat & Ditambahkan ke Daun Listpack)
    │
    │ 2. XREADGROUP GROUP g1 w1 BLOCK 2000 COUNT 50 STREAMS mystream >
    ▼
[Consumer w1] ── (Pesan masuk ke PEL w1)
    │
    ├── [Eksekusi Berhasil] ──> 3a. XACK mystream g1 <id> (Hapus dari PEL)
    │
    └── [Eksekusi Gagal/Crash]
            │
            ▼
    [Failure Recovery Loop w2]
            │
            │ 3b. XAUTOCLAIM mystream g1 w2 30000 0-0 COUNT 50
            ▼
    [Re-processed by w2]
            │
            ├── Jika Counter Delivery > MaxRetry:
            │       │
            │       ├──> 4a. XADD mystream:dlq * payload {...}
            │       └──> 4b. XACK mystream g1 <id>
            │
            └── [Eksekusi Sukses]:
                    └──> 4c. XACK mystream g1 <id>
```

### Langkah 1: Ingestion dengan Trimming Adaptif
Producer menulis event ke stream menggunakan perintah:
```redis
XADD mystream MAXLEN ~ 1000000 * field1 val1 field2 val2
```
* Simbol `~` (approximate trimming) sangat penting. Ini menginstruksikan Redis untuk memotong data hanya ketika seluruh node Listpack dapat dibuang, mengubah kompleksitas operasi pemotongan dari $\mathcal{O}(N)$ menjadi $\mathcal{O}(1)$ yang amortized.

### Langkah 2: Distribusi Workload Melalui Consumer Groups
Consumer membaca pesan yang belum pernah didistribusikan ke worker lain dengan parameter ID spesial `>`:
```redis
XREADGROUP GROUP mygroup worker-1 BLOCK 5000 COUNT 10 STREAMS mystream >
```
Redis secara atomik:
1. Mengambil 10 pesan berikutnya setelah `Last Delivered ID`.
2. Mencatat ID pesan tersebut ke dalam PEL global `mygroup` dan PEL lokal `worker-1`.
3. Mengembalikan array event ke `worker-1`.

### Langkah 3: Eksekusi dan Acknowledgment
Worker mengeksekusi business logic. Setelah transaksi database selesai, worker wajib mengirimkan:
```redis
XACK mystream mygroup 1711900000-0
```
Jika `XACK` dieksekusi, node ID dihapus dari PEL. Ruang memori PEL dibebaskan.

### Langkah 4: Failover dan Dead-Letter Recovery Loop
Jika worker mati saat memproses pesan:
1. Pesan tersangkut di PEL tanpa ada `XACK`.
2. Worker lain (misal: supervisor thread atau worker-2) secara berkala menjalankan `XAUTOCLAIM`:
   ```redis
   XAUTOCLAIM mystream mygroup worker-2 60000 0-0 COUNT 20
   ```
   Redis memeriksa pesan-pesan di PEL yang waktu tunggunya (*idle time*) sudah melampaui $60000\text{ ms}$ (60 detik), lalu secara atomik mengalihkan kepemilikan pesan tersebut ke `worker-2` dan mereset *idle timer*-nya.
3. Jika counter pengiriman (*delivery count*) melampaui ambang batas maksimum (misal: 3 kali percobaan), pesan dikategorikan sebagai *Poison Pill*. Worker memindahkan payload ke *Dead Letter Queue* (`mystream:dlq`) via `XADD` dan segera mengeksekusi `XACK` pada stream utama agar pipeline tidak tersumbat.

---

## 6. Analogy & Diagram ASCII

### Analogi Kantor Pos Modern
* **Redis Stream**: Jalur ban berjalan (*conveyor belt*) logistik paket. Setiap paket memiliki barcode bertempelkan stempel waktu mikrodetik (*Stream ID*).
* **Consumer Group**: Tim pemilah barang (misal: "Tim Retur").
* **Consumer**: Karyawan individu di dalam tim tersebut (misal: "Budi" dan "Siti").
* **XREADGROUP ... >**: Manajer mengambil paket baru dari conveyor dan memberikannya ke meja Budi.
* **PEL (Pending Entries List)**: Buku catatan gantung di meja Budi. Berisi daftar paket yang sedang dia periksa. Manajer tahu persis paket mana yang ada di meja Budi.
* **XACK**: Budi mencap paket sebagai "SELESAI", lalu menghapus nomor resi dari buku catatan gantungnya.
* **XAUTOCLAIM**: Budi tiba-tiba jatuh pingsan (crash). Setelah 30 menit, Siti memeriksa buku catatan gantung Budi, melihat paket yang terbengkalai terlalu lama, lalu mengambil paket itu ke mejanya untuk diproses.

---

## 7. Simple Example & Practical Example

Berikut adalah implementasi end-to-end berstandar industri menggunakan **Go** dan library `github.com/redis/go-redis/v9`.

Struktur proyek:
```
hands-on/m02/
├── go.mod
├── go.sum
└── main.go
```

### 7.1 `go.mod`
```go
module redis-streams-production

go 1.22

require (
	github.com/google/uuid v1.6.0
	github.com/redis/go-redis/v9 v9.5.1
)
```

### 7.2 `main.go`
Kode ini mencakup Producer, Consumer, Idempotency Handler, Auto-Claimer, dan Dead-Letter Queue (DLQ).

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

const (
	StreamName     = "stream:orders:v1"
	GroupName      = "grp:order-processors"
	DLQStreamName  = "stream:orders:dlq"
	MaxDeliveryTry = 3
	IdleClaimTime  = 10 * time.Second
)

type OrderEvent struct {
	ID        string
	OrderID   string
	Amount    string
	Timestamp string
}

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	rdb := redis.NewClient(&redis.Options{
		Addr:         "localhost:6379",
		Password:     "",
		DB:           0,
		PoolSize:     20,
		MinIdleConns: 5,
	})

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Gagal terhubung ke Redis: %v", err)
	}
	defer rdb.Close()

	// Inisialisasi Consumer Group
	err := rdb.XGroupCreateMkStream(ctx, StreamName, GroupName, "$").Err()
	if err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
		log.Fatalf("Gagal membuat consumer group: %v", err)
	}

	var wg sync.WaitGroup

	// Jalankan Producer Simulator
	wg.Add(1)
	go func() {
		defer wg.Done()
		producerLoop(ctx, rdb)
	}()

	// Jalankan 2 Concurrent Consumer Workers
	for i := 1; i <= 2; i++ {
		workerName := fmt.Sprintf("worker-%d", i)
		wg.Add(1)
		go func(name string) {
			defer wg.Done()
			consumerLoop(ctx, rdb, name)
		}(workerName)
	}

	// Jalankan Auto-Claimer (Recovery Routine)
	wg.Add(1)
	go func() {
		defer wg.Done()
		autoClaimLoop(ctx, rdb, "worker-recovery")
	}()

	// Graceful Shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	<-sigChan

	log.Println("[SHUTDOWN] Menerima sinyal terminasi, mematikan seluruh engine...")
	cancel()
	wg.Wait()
	log.Println("[SHUTDOWN] Seluruh worker telah berhenti dengan bersih.")
}

func producerLoop(ctx context.Context, rdb *redis.Client) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			orderID := uuid.New().String()
			args := &redis.XAddArgs{
				Stream: StreamName,
				MaxLen: 100000,
				Approx: true,
				Values: map[string]interface{}{
					"order_id":  orderID,
					"amount":    "150000.00",
					"created":   time.Now().UnixNano(),
				},
			}

			id, err := rdb.XAdd(ctx, args).Result()
			if err != nil {
				log.Printf("[PRODUCER] Gagal mengirim event: %v", err)
				continue
			}
			log.Printf("[PRODUCER] Event diterbitkan: ID=%s, OrderID=%s", id, orderID)
		}
	}
}

func consumerLoop(ctx context.Context, rdb *redis.Client, consumerName string) {
	log.Printf("[%s] Berhasil dijalankan...", consumerName)

	for {
		select {
		case <-ctx.Done():
			return
		default:
			// Read new messages
			streams, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    GroupName,
				Consumer: consumerName,
				Streams:  []string{StreamName, ">"},
				Count:    5,
				Block:    3 * time.Second,
			}).Result()

			if err != nil {
				if errors.Is(err, redis.Nil) || errors.Is(err, context.Canceled) {
					continue
				}
				log.Printf("[%s] XREADGROUP error: %v", consumerName, err)
				time.Sleep(1 * time.Second)
				continue
			}

			for _, stream := range streams {
				for _, msg := range stream.Messages {
					processMessage(ctx, rdb, consumerName, msg)
				}
			}
		}
	}
}

func processMessage(ctx context.Context, rdb *redis.Client, consumerName string, msg redis.XMessage) {
	orderID, ok := msg.Values["order_id"].(string)
	if !ok {
		log.Printf("[%s] Malformed payload, melewatkan ID: %s", consumerName, msg.ID)
		rdb.XAck(ctx, StreamName, GroupName, msg.ID)
		return
	}

	// Idempotency Gate menggunakan Redis SETNX
	idempotencyKey := fmt.Sprintf("idempotency:order:%s", orderID)
	acquired, err := rdb.SetNX(ctx, idempotencyKey, "processed", 24*time.Hour).Result()
	if err != nil {
		log.Printf("[%s] Lock error untuk order %s: %v", consumerName, orderID, err)
		return
	}

	if !acquired {
		log.Printf("[%s] Duplicate skipped: Order %s telah diproses sebelumnya", consumerName, orderID)
		rdb.XAck(ctx, StreamName, GroupName, msg.ID)
		return
	}

	// Simulasi Business Logic
	log.Printf("[%s] Memproses Order: %s (MsgID: %s)", consumerName, orderID, msg.ID)
	time.Sleep(200 * time.Millisecond)

	// Acknowledge Pesan dari PEL
	if err := rdb.XAck(ctx, StreamName, GroupName, msg.ID).Err(); err != nil {
		log.Printf("[%s] Gagal mengirim ACK untuk MsgID %s: %v", consumerName, msg.ID, err)
	}
}

func autoClaimLoop(ctx context.Context, rdb *redis.Client, claimerName string) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			// Memeriksa dan mengklaim pesan yang tersangkut di PEL melewati batas waktu IdleClaimTime
			res, _, err := rdb.XAutoClaim(ctx, &redis.XAutoClaimArgs{
				Stream:   StreamName,
				Group:    GroupName,
				Consumer: claimerName,
				MinIdle:  IdleClaimTime,
				Start:    "0-0",
				Count:    10,
			}).Result()

			if err != nil {
				if !errors.Is(err, context.Canceled) {
					log.Printf("[AUTOCLAIM] Gagal menjalankan XAUTOCLAIM: %v", err)
				}
				continue
			}

			for _, msg := range res {
				log.Printf("[AUTOCLAIM] Berhasil mengklaim pesan menggantung ID: %s", msg.ID)
				handleDeadLetterOrRetry(ctx, rdb, claimerName, msg)
			}
		}
	}
}

func handleDeadLetterOrRetry(ctx context.Context, rdb *redis.Client, workerName string, msg redis.XMessage) {
	// Dapatkan detail pesan dari PEL untuk mengecek total pengiriman
	pendings, err := rdb.XPendingExt(ctx, &redis.XPendingExtArgs{
		Stream: StreamName,
		Group:  GroupName,
		Start:  msg.ID,
		End:    msg.ID,
		Count:  1,
	}).Result()

	if err != nil || len(pendings) == 0 {
		return
	}

	deliveryCount := pendings[0].RetryCount

	if deliveryCount >= MaxDeliveryTry {
		log.Printf("[DLQ-ALERT] Pesan %s gagal diproses sebanyak %d kali. Mengirim ke DLQ.", msg.ID, deliveryCount)

		// Pindahkan ke Dead Letter Queue
		pipe := rdb.TxPipeline()
		pipe.XAdd(ctx, &redis.XAddArgs{
			Stream: DLQStreamName,
			MaxLen: 50000,
			Approx: true,
			Values: map[string]interface{}{
				"origin_stream":  StreamName,
				"origin_msg_id":  msg.ID,
				"payload":        msg.Values,
				"failure_reason": "MaxRetryExceeded",
				"archived_at":    time.Now().Unix(),
			},
		})
		pipe.XAck(ctx, StreamName, GroupName, msg.ID)

		if _, err := pipe.Exec(ctx); err != nil {
			log.Printf("[DLQ-ERROR] Gagal memindahkan pesan %s ke DLQ: %v", msg.ID, err)
		}
		return
	}

	// Eksekusi ulang jika belum melampaui retry
	processMessage(ctx, rdb, workerName, msg)
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Pipeline Pemrosesan Pembayaran Dompet Digital (50.000 Transaksi / Detik)
Sebuah perusahaan *financial technology* menghadapi bottleneck latensi P99 pada Kafka saat menangani event *flash-sale payment*. Overhead latensi commit offset dan sinkronisasi disk pada Kafka mencapai 45ms. Sistem dimigrasikan menggunakan arsitektur **Redis Cluster Streams**.

```
                   Client Traffic (50k req/sec)
                                │
                                ▼
                       API Gateway Load Balancer
                                │
     ┌──────────────────────────┼──────────────────────────┐
     ▼                          ▼                          ▼
Worker Pod 1               Worker Pod 2               Worker Pod 3
     │                          │                          │
HashTag: {wallet:01}       HashTag: {wallet:02}       HashTag: {wallet:03}
     ▼                          ▼                          ▼
Node 1 (Redis Master)      Node 2 (Redis Master)      Node 3 (Redis Master)
Stream: tx:{wallet:01}     Stream: tx:{wallet:02}     Stream: tx:{wallet:03}
```

### Solusi Arsitektur
1. **Sharding via Hash Tags**:
   * Redis Cluster membagi slot kunci ke berbagai node. Stream tunggal tidak bisa dipecah antar node.
   * Tim menggunakan *Hash Tags* pada nama Stream: `stream:transactions:{shard_id}` di mana `shard_id = crc32(account_id) % 64`.
   * Ini mendistribusikan 50.000 transaksi ke 64 Stream mandiri di 16 master nodes tanpa konflik cross-slot.
2. **Durability Tuning**:
   * Konfigurasi persistensi: `appendonly yes`, `appendfsync everysec`.
   * Latensi P99 drop dari **45ms** menjadi **1.8ms**.
   * Replikasi asynchronous ke Replica Node dengan parameter `WAIT 1 100` untuk transaksi nominal besar guna memastikan persistensi tersinkronisasi ke minimal 1 replika sebelum memberi respons sukses ke payment gateway.

---

## 9. Trade-offs

| Parameter | Redis Streams | Apache Kafka | RabbitMQ |
| :--- | :--- | :--- | :--- |
| **P99 Read/Write Latency** | **Ultra Rendah (< 2 ms)** (In-memory storage) | Sedang (15 - 50 ms) (Disk buffer based) | Rendah (5 - 10 ms) (Erlang Actor Engine) |
| **Max Storage Capacity** | Dibatasi oleh RAM (Mahal untuk multi-terabyte) | Skala Terabyte - Petabyte (Murah, disk-backed) | Dibatasi oleh RAM & Disk swap |
| **Consumer Partitioning** | Manual (via hash-tag keys/multiple streams) | Built-in (Automatic partition rebalance) | Routing Key exchange binding |
| **Message Ordering** | Strict per stream ID | Strict per partition | Strict per queue FIFO |
| **Message Replay** | Fleksibel (`XRANGE` via ID) | Fleksibel (seek offset) | Sangat Terbatas (setelah ACK, data dibuang) |
| **Operational Complexity**| Sangat Rendah jika sudah ada Redis Cluster | Sangat Tinggi (JVM, Zookeeper/KRaft, OS Tuning)| Menengah (Erlang runtime management) |

---

## 10. Common Mistakes & Troubleshooting

### 1. PEL Memory Leak (Kebocoran Memori Akibat Missing ACK)
* **Gejala**: RAM Redis membengkak perlahan meskipun `XADD` menggunakan `MAXLEN ~`. Eksekusi command mendadak lambat (*latency spikes*).
* **Penyebab**: Aplikasi membaca pesan menggunakan `XREADGROUP`, namun lupa atau gagal memanggil `XACK` pada kondisi *error code-path*. Entri di dalam PEL tersimpan selamanya.
* **Deteksi**:
  ```redis
  XINFO GROUPS <stream_key>
  # Perhatikan nilai field "pending". Jika pending bernilai jutaan, terjadi kebocoran memori pada PEL.
  ```
* **Solusi**: Pastikan ada blok `defer` atau `finally` untuk menangani ACK jika terjadi *unrecoverable business validation error*. Lakukan pembersihan manual:
  ```redis
  XACK <stream_key> <group_name> <id_1> <id_2> ...
  ```

### 2. O(N) Uncapped Trimming Degradation
* **Gejala**: Operasi `XADD` menghasilkan spike CPU 100% pada node master.
* **Penyebab**: Menggunakan parameter `MAXLEN 100000` eksak (tanpa karakter `~`). Redis terpaksa membedah listpack dan membersihkan memori tepat sebesar satu entri setiap kali ada write baru ($\mathcal{O}(N)$ node traversal).
* **Solusi**: Selalu gunakan approximate trimming: `XADD <key> MAXLEN ~ 100000 * <fields...>`. Ini memotong seluruh daun Listpack sekaligus secara amortized ($\mathcal{O}(1)$).

### 3. Blocking Thread Starvation pada Connection Pool
* **Gejala**: Aplikasi microservice hang secara acak dan connection pool timeout.
* **Penyebab**: Menjalankan blocking call `XREADGROUP ... BLOCK 10000` menggunakan client pool yang sama dengan pemanggilan perintah reguler (`GET`, `SET`). Seluruh koneksi di pool terkunci menunggu event stream.
* **Solusi**: Pisahkan Connection Pool: buat *Dedicated Connection* khusus untuk loop *blocking read*, jangan dicampur dengan general-purpose connection pool.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Selalu Gunakan Approximate Trimming (`~`)**: Hindari strict eviction untuk melindungi CPU throughput.
2. [ ] **Terapkan Idempotency Key**: Gunakan `SETNX` atau `Redlock` berbasis Hash event-id di database sebelum memproses data dari Redis Streams.
3. [ ] **Monitoring PEL secara Real-time**: Set alert threshold pada monitoring Prometheus/Grafana jika metrik `redis_stream_group_pending_messages` bertambah secara monotonik.
4. [ ] **Implementasikan DLQ Pattern**: Jangan biarkan pesan poison-pill dicoba ulang tanpa henti (*infinite retry storm*).
5. [ ] **Tentukan Nama Consumer yang Deterministik**: Gunakan kombinasi `Hostname-ContainerID-UUID` untuk mempermudah audit via `XINFO CONSUMERS`.
6. [ ] **Gunakan Hash Tags pada Redis Cluster**: Format stream key dengan `{partition_key}:stream_name` agar seluruh data stream dan lock yang berhubungan berada pada slot hash yang sama.
7. [ ] **Pisahkan Connection Instance**: Alokasikan koneksi persisten tersendiri untuk operasi `BLOCK`.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### Skenario Praktikum:
Mensimulasikan insiden produksi: Menjalankan streaming ingestion, mematikan salah satu worker secara paksa (*SIGKILL*), dan mengamati worker kedua mengambil alih (*auto-claim*) pekerjaan worker yang mati tanpa kehilangan satu pun event.

### Langkah 1: Siapkan Server Redis Lokal
Jalankan instance Redis melalui container:
```bash
docker run -d --name redis-stream-lab -p 6379:6379 redis:7.2-alpine
```

### Langkah 2: Buat Direktori dan File Kode
```bash
mkdir -p hands-on/m02
cd hands-on/m02
go mod init redis-streams-production
go get github.com/redis/go-redis/v9 github.com/google/uuid
```
Salin kode dari **Seksi 7.2** ke file `hands-on/m02/main.go`.

### Langkah 3: Eksekusi dan Amati PEL
Jalankan worker di terminal 1:
```bash
go run main.go
```

Buka terminal 2, lakukan inspeksi internal Redis secara langsung:
```bash
# Periksa status group
docker exec -it redis-stream-lab redis-cli XINFO GROUPS stream:orders:v1

# Periksa status konsumen
docker exec -it redis-stream-lab redis-cli XINFO CONSUMERS stream:orders:v1 grp:order-processors

# Periksa PEL secara langsung
docker exec -it redis-stream-lab redis-cli XPENDING stream:orders:v1 grp:order-processors - + 10
```

### Langkah 4: Simulasikan Poison-Pill / Failure Injection
Masukkan pesan rusak yang memicu infinite error ke dalam stream secara manual dari terminal 2:
```bash
docker exec -it redis-stream-lab redis-cli XADD stream:orders:v1 * broken_field "corrupted"
```
Amati log di terminal 1: Worker akan mendeteksi payload malformed, mengeksekusi penanganan gracefully, dan membuang/ACK pesan tersebut tanpa memblokir antrian.

---

## 13. Exercise

### Level Easy
Modifikasi implementasi Go di atas agar Producer menyertakan atribut `priority` (High/Normal) pada setiap pesan, lalu buat filter di consumer log.

### Level Medium
Ubah interval `IdleClaimTime` menjadi 5 detik, dan implementasikan penghitung metrik sederhana menggunakan Redis Hash (`HINCRBY metrics:stream processed 1`) setiap kali sebuah worker sukses menyelesaikan pemrosesan event.

### Level Hard
Implementasikan skema *Batch Processing Engine*:
Alih-alih memproses satu pesan per satu waktu, ubah worker untuk membaca 100 pesan sekaligus (`COUNT 100`), mengeksekusi operasi penulisan batch ke database secara mock, dan melakukan batch acknowledge (`XACK stream group id1 id2 id3 ...`) dalam satu roundtrip jaringan pipeline.

---

## 14. Challenge

**Tantangan Sistem Finansial: Poison-Pill Isolation Engine dengan Backoff Adaptif**

Rancang arsitektur Consumer Redis Streams tingkat lanjut tanpa mengandalkan library pihak ketiga selain driver standar Redis:
1. **Adaptive Exponential Backoff**: Jika pesan gagal diproses (misal service payment gateway pihak ketiga down), pesan tidak boleh langsung dikirim ke DLQ. Pesan harus di-retry dengan interval waktu eksponensial: Retry 1 = 2 detik, Retry 2 = 4 detik, Retry 3 = 8 detik, dst.
2. **Keterbatasan Engine**: Redis `XAUTOCLAIM` tidak memiliki parameter backoff bertingkat natively.
3. **Problem**: Bagaimana Anda mendesain mekanisme ini tanpa memblokir throughput pesan-pesan valid lainnya yang berada di belakang ID pesan gagal tersebut? Tuliskan desain arsitekturalnya dan skema Sorted Set pendukungnya (`ZADD schedule_time message_id`).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. Struktur data internal apa yang digunakan oleh Redis Streams untuk mengindeks ID pesan?
   * A. Linked List
   * B. SkipList
   * C. Radix Tree (`rax`)
   * D. B+ Tree
   * *Kunci Jawaban: C. Redis mengimplementasikan Radix Tree efisien bernama `rax`.*

2. Apa arti karakter `>` pada pemanggilan perintah `XREADGROUP`?
   * A. Baca pesan dari awal stream.
   * B. Baca hanya pesan yang belum pernah diserahkan ke consumer lain dalam grup.
   * C. Hapus pesan setelah dibaca.
   * D. Baca pesan yang idle time-nya paling tinggi.
   * *Kunci Jawaban: B. `>` merepresentasikan event baru yang belum pernah dialokasikan ke worker lain.*

3. Apa kepanjangan dan fungsi dari PEL pada Redis Streams?
   * A. Pipeline Execution List: buffer perintah client.
   * B. Pending Entries List: melacak pesan yang sudah dibaca namun belum di-ACK.
   * C. Partition Event Log: log replikasi cluster.
   * D. Processed Entry Limit: batas ukuran stream.
   * *Kunci Jawaban: B. Pending Entries List melacak status pesan yang belum di-ACK.*

4. Perintah mana yang digunakan untuk mengklaim ulang pesan yang terbengkalai akibat matinya sebuah consumer?
   * A. `XRELOAD`
   * B. `XCONSUME`
   * C. `XAUTOCLAIM`
   * D. `XRESET`
   * *Kunci Jawaban: C. `XAUTOCLAIM` (atau `XCLAIM`) memindahkan ownership pesan stale di PEL ke worker aktif.*

5. Mengapa perintah `XADD mystream MAXLEN ~ 1000 * f v` lebih disukai di lingkungan produksi dibandingkan `MAXLEN 1000`?
   * A. Karakter `~` mengompresi payload string menjadi format biner.
   * B. Karakter `~` melakukan approximate trimming berbasis Listpack node sehingga kompleksitasnya amortized $\mathcal{O}(1)$.
   * C. Karakter `~` otomatis mencadangkan data ke disk SSD.
   * D. Karakter `~` mencegah duplikasi pesan.
   * *Kunci Jawaban: B. Approximate trimming mengeliminasi bottleneck traversal memori.*

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis)

6. Apa risiko operasional terbesar jika worker terus menerus mengeksekusi `XREADGROUP` tanpa pernah memanggil `XACK`?
   * A. Stream akan otomatis terhapus oleh engine Redis.
   * B. Terjadi memory leak pada Pending Entries List (PEL) yang memicu Redis OOM (Out Of Memory).
   * C. Redis CPU akan terkunci pada status starvation.
   * D. Redis Cluster langsung melakukan split-brain failover.
   * *Kunci Jawaban: B. PEL terus menampung metadata pesan yang tidak pernah dibebaskan.*

7. Manakah pernyataan yang BENAR mengenai delta compression pada Listpack Redis Streams?
   * A. Semua integer dienkripsi menggunakan algoritma AES-256.
   * B. Field key yang repetitif pada kumpulan event berurutan dicatat pada master entry sehingga menghemat alokasi memori string.
   * C. Nilai string yang sama disimpan di luar instance Redis.
   * D. Delta compression mematikan fungsi replication slave.
   * *Kunci Jawaban: B. Master entry menyimpan skema field; pesan individual dalam satu node Listpack hanya merekam perubahannya.*

8. Di Redis Cluster, mengapa membuat stream tunggal yang diakses oleh ribuan client dari berbagai partisi order ID dapat menjadi anti-pattern?
   * A. Redis Cluster tidak mendukung tipe data Stream.
   * B. Sebuah Stream key terikat pada satu single hash slot (satu master node), sehingga memusatkan seluruh beban I/O pada satu core CPU.
   * C. Redis Cluster akan menduplikasi stream tersebut ke seluruh node secara otomatis.
   * D. Ukuran stream ID tidak kompatibel dengan algoritma CRC16.
   * *Kunci Jawaban: B. Key pada Redis Cluster terpetakan ke tepat 1 dari 16384 slot, membatasi skalabilitas satu Stream pada kemampuan single-thread core node tersebut.*

9. Apa fungsi argumen `BLOCK <ms>` pada perintah `XREADGROUP`?
   * A. Mengunci seluruh redis node agar client lain tidak bisa menulis.
   * B. Menahan koneksi client secara non-polling sampai ada pesan baru yang masuk atau batas timeout terlewati.
   * C. Memblokir IP worker lain yang mencurigakan.
   * D. Menghentikan sementara proses trimming data.
   * *Kunci Jawaban: B. Long-polling hemat CPU untuk menunggu kedatangan event baru.*

10. Jika kita membutuhkan jaminan pemrosesan *Strictly Once* (Exactly-Once Semantics), langkah apa yang mutlak diperlukan pada layer consumer?
    * A. Cukup mengandalkan Redis Streams karena sifatnya sudah natively Exactly-Once.
    * B. Mengatur `appendfsync always` pada file redis.conf.
    * C. Mengimplementasikan Idempotency check (misal hash ID di cache/DB) di consumer sebelum mengeksekusi logika domain.
    * D. Menghindari pemanggilan perintah `XACK`.
    * *Kunci Jawaban: C. Redis Streams menjamin At-Least-Once Delivery; exactly-once hanya bisa dicapai bila dikombinasikan dengan idempotency consumer.*

---

### Bagian 3: Production Case Analysis (Analisis Skenario Nyata)

#### Kasus 1: Fenomena Dead-Letter Loop
* **Skenario**: Sistem worker pembayaran mendadak mengalami lonjakan CPU hingga 100% dan latensi sistem melonjak drastis. Setelah diinspeksi, sebuah pesan berisi ID akun yang tidak valid menyebabkan error null-pointer di kode backend. Worker me-restart sendiri, membaca pesan yang sama via `XAUTOCLAIM`, error kembali, dan siklus ini berulang tanpa henti (*Crash Loop*).
* **Solusi Arsitektural**: Jelaskan tindakan mitigasi yang harus dilakukan pada kode consumer untuk memutus siklus ini!
* *Jawaban Evaluasi*: Worker harus memanfaatkan nilai `retry-count` dari output `XAUTOCLAIM` atau `XPENDING`. Jika counter percobaan sudah melampaui batas toleransi (misal 3 kali), worker wajib mengalihkan pesan ke Dead-Letter Stream (`XADD stream:dlq`) dan memanggil `XACK` pada stream utama.

#### Kasus 2: Lonjakan Latensi Trimming
* **Skenario**: Saat event promo nasional, Producer mencatat kenaikan latensi dari 1ms menjadi 400ms per `XADD`. Konfigurasi yang digunakan adalah `XADD app-stream MAXLEN 5000000 * payload ...`.
* **Solusi Arsitektural**: Apa kesalahan fatal pada pipeline ini dan bagaimana memperbaikinya secara instan tanpa downtime?
* *Jawaban Evaluasi*: Producer menggunakan strict trimming `MAXLEN 5000000` tanpa tilde `~`. Redis dipaksa merestrukturisasi listpack pada setiap operasi `XADD`. Ubah parameter menjadi `XADD app-stream MAXLEN ~ 5000000 * payload ...`. Ini mengubah degradasi dari $\mathcal{O}(N)$ menjadi amortized $\mathcal{O}(1)$.

#### Kasus 3: Stale Worker PEL Accumulation
* **Skenario**: Sebuah worker pod di Kubernetes dihapus (terminated) oleh Horizontal Pod Autoscaler (HPA) saat beban mereda. Seminggu kemudian, administrator menemukan memori Redis membengkak ratusan megabyte oleh ribuan entri berstatus pending milik worker pod yang sudah mati tersebut.
* **Solusi Arsitektural**: Perintah Redis apa yang harus dijalankan untuk membersihkan worker yang sudah tidak aktif beserta sisa pesannya?
* *Jawaban Evaluasi*: Jalankan `XAUTOCLAIM` oleh worker yang masih hidup untuk mengambil alih seluruh unacknowledged message dari worker yang mati tersebut ke consumer yang aktif, lalu jalankan `XGROUP DELCONSUMER <stream> <group> <terminated-worker-name>` untuk menghapus state PEL lokal milik worker lama secara permanen.

---

## 16. Summary

1. **Redis Streams** adalah struktur data log *append-only* berperforma tinggi yang didukung oleh kombinasi memori **Radix Tree (`rax`)** dan **Listpack**, dirancang untuk *Event-Driven Architecture* dengan latensi sub-milidetik.
2. Fitur **Consumer Groups** memfasilitasi *competing consumer pattern* dengan load balancing terdistribusi. Mekanisme internal **Pending Entries List (PEL)** memastikan sistem mencapai semantik pengiriman data **At-Least-Once**.
3. Ketahanan sistem produksi terhadap kegagalan bertumpu pada penggunaan kombinasi perintah `XREADGROUP`, `XACK`, dan pemulihan berkala melalui `XAUTOCLAIM`.
4. Untuk mencegah konsumsi memori dan degradasi latensi yang tidak terkendali:
   * Wajib menggunakan *approximate trimming* (`MAXLEN ~`).
   * Wajib memastikan seluruh alur kode mengeksekusi `XACK` atau memindahkan pesan gagal ke *Dead-Letter Queue (DLQ)*.
   * Wajib menerapkan *Idempotency Gate* pada aplikasi untuk menangani duplikasi pesan.