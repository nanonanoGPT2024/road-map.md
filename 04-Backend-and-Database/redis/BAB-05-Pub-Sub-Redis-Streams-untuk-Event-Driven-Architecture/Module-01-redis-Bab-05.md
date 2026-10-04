# Bab 05 Module 01: Pub/Sub & Redis Streams untuk Event-Driven Architecture

---

## 01: Identitas Modul

* **Track**: Backend Engine & Distributed Infrastructure Engineering
* **Kategori**: 04-Backend-and-Database
* **Topik**: Redis Distributed Systems & Event Broker
* **Kode Modul**: REDIS-EDA-0501
* **Level**: Advanced
* **Prasyarat**:
  * Penguasaan struktur data dasar Redis (Strings, Hashes, Sets, Sorted Sets).
  * Pemahaman mendalam terkait protokol TCP/IP, koneksi non-blocking/asinkron, dan event loop.
  * Pengetahuan arsitektur microservices dan pola komunikasi asinkron (Message Broker, Event Sourcing).
* **Target Tools & Versi**:
  * Redis Engine: Versi 7.2+ (Core Engine & ACL v2)
  * Runtimes: Go 1.22+ (`github.com/redis/go-redis/v9`), Node.js 20 LTS (`ioredis` v5+)
  * Tooling: Docker Compose v2, `redis-cli`, `redis-benchmark`

---

## 02: Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Perbedaan Fundamental**: Membedakan secara arsitektural antara model fire-and-forget (Redis Pub/Sub) dan log-based persistent streaming (Redis Streams) hingga level protokol dan manajemen memori.
2. **Merancang Topologi Event Sourcing**: Membangun topologi event ingestion bertaraf enterprise menggunakan Redis Streams, Consumer Groups, dan pola mutasi atomik.
3. **Mengimplementasikan Failover Consumer**: Menangani skenario consumer failure, pending messages, poison pills, dan dead-letter queue (DLQ) secara otomatis dengan `XPENDING`, `XCLAIM`, dan `XAUTOCLAIM`.
4. **Mengoptimalkan Skalabilitas Memori**: Menerapkan strategi retensi data streaming melalui capped streams (`MAXLEN ~`) dan trimming strategy tanpa mengorbankan I/O throughput.
5. **Mengamankan dan Memonitor Pipeline**: Menerapkan granular Access Control Lists (ACL v2) dan instrumen observabilitas telemetri (lag monitoring, pending message counts, stream depth metrics).

---

## 03: Concept Map Diagram ASCII

```
+-----------------------------------------------------------------------------+
|                          REDIS EVENT BROKER ENGINE                          |
+-----------------------------------------------------------------------------+
                                       |
           +---------------------------+---------------------------+
           |                                                       |
           v                                                       v
+-----------------------+                               +---------------------+
|     Redis Pub/Sub     |                               |    Redis Streams    |
|   (Fire-and-Forget)   |                               |  (Append-Only Log)  |
+-----------------------+                               +---------------------+
| * Ephemeral Messages  |                               | * Persistent Disk   |
| * In-Memory Buffers   |                               | * Consumer Groups   |
| * No Replay Support   |                               | * Ack / PEL Support |
| * Low Sub-ms Latency  |                               | * Message ID (Time) |
+-----------+-----------+                               +----------+----------+
            |                                                      |
    +-------+-------+                                      +-------+-------+
    |               |                                      |               |
    v               v                                      v               v
+-------+       +-------+                              +-------+       +-------+
| Sub A |       | Sub B |                              | Group |       | Group |
| (Live)|       | (Live)|                              |  App1 |       |  App2 |
+-------+       +-------+                              +---+---+       +---+---+
                                                           |               |
                                                   +-------+-------+       |
                                                   v               v       v
                                               +-------+       +-------+ +---+
                                               | Cons1 |       | Cons2 | | C1|
                                               +-------+       +-------+ +---+
                                               [Pending Entries List (PEL)]
```

---

## 04: Mengapa Relevan

Dalam arsitektur *event-driven* modern, pemilihan transport data menentukan reliabilitas dan skalabilitas sistem:

* **Redis Pub/Sub** ideal untuk skenario performa tinggi yang menoleransi *ephemeral data*, seperti distribusi status WebSocket, notifikasi real-time, dan invalidasi cache terdistribusi. Kelemahan utamanya adalah ketiadaan mekanisme *buffering*: jika subscriber *disconnect*, data yang dikirim selama durasi tersebut hilang secara permanen.
* **Redis Streams** mengatasi keterbatasan tersebut dengan mengimplementasikan struktur data *append-only log* yang terinspirasi oleh Apache Kafka, namun tetap berjalan *in-memory* dengan persistensi RDB/AOF. Redis Streams mendukung *at-least-once delivery*, koordinasi beban antar worker via *Consumer Groups*, inspeksi *Pending Entries List* (PEL), dan penanganan kegagalan consumer.

Penguasaan kedua paradigma ini krusial untuk membangun sistem backend yang responsif, *fault-tolerant*, dan hemat sumber daya tanpa harus selalu menambah kompleksitas infrastruktur terpisah seperti Kafka atau RabbitMQ.

---

## 05: Anatomi Konsep Inti

### 1. Redis Pub/Sub: Protokol & Buffer Internals

Pub/Sub beroperasi pada lapisan koneksi client. Ketika subscriber mengeksekusi `SUBSCRIBE notifications`, koneksi dialihkan ke *listening mode*.

* **Struktur Data Internal**: Redis menyimpan dictionary global di mana *key* adalah nama channel, dan *value* adalah linked list dari pointers ke client descriptor (`redisClient`).
* **PubSub Output Buffer Limit**: Setiap client memiliki buffer output memori. Jika subscriber lambat mengonsumsi data sementara publisher mengirim data secara intensif, buffer akan terisi penuh. Saat batas `client-output-buffer-limit pubsub` terlampaui, Redis secara sepihak memutus koneksi subscriber untuk melindungi integritas memori server.

```
Publisher ---> [ Redis Server ]
                    |
                    +--- (Buffer A) ---> Client A (Healthy)
                    |
                    +--- (Buffer B Exceeded!) -X-> Client B (Terminated by OOM Guard)
```

### 2. Redis Streams: Log-Based In-Memory Engine

Redis Streams menggunakan representasi data internal **Radix Tree** (Rax) yang dioptimasi dengan compact listpacks, memungkinkan penyimpanan jutaan entri dengan overhead memori minimal.

* **Message Identifier (`<millisecondsTime>-<sequenceNumber>`)**:
  Setiap pesan memiliki ID unik berbasis waktu Unix millisecond ditambah sequence number 64-bit untuk resolusi konflik pada milidetik yang sama (contoh: `1710921600000-0`).
* **Consumer Groups**:
  Mekanisme pembagian beban pembacaan data. Setiap consumer group memelihara pointer state (`Last Delivered ID`) yang menunjukkan progres pembacaan stream.
* **PEL (Pending Entries List)**:
  Tabel pelacak pesan yang sudah dikirim ke worker tertentu namun belum menerima konfirmasi penerimaan (`XACK`). PEL menyimpan: ID Pesan, Nama Consumer, Idle Time (milidetik sejak delivery terakhir), dan Delivery Counter.

```
Stream Entry ID: 1710921600000-0
[ Payload: { order_id: "ORD-99", amount: 50000 } ]
       |
       v  (XREADGROUP GROUP workers-group worker-1)
[ In-Flight / Unacknowledged ] ---> Logged in PEL
       |
       +---> Client Success ---> (XACK) ---> Purged from PEL
       |
       +---> Client Crash   ---> (XAUTOCLAIM / XCLAIM by worker-2)
```

---

## 06: Panduan Implementasi Step-by-Step

### Tahap 1: Konfigurasi Server Redis

Jalankan Redis dengan konfigurasi buffer Pub/Sub dan AOF yang aman:

```bash
cat <<EOF > redis.conf
appendonly yes
appendfsync everysec
client-output-buffer-limit pubsub 32mb 8mb 60
stream-node-max-bytes 4096
stream-node-max-entries 100
EOF

docker run -d --name redis-eda -p 6379:6379 -v $(pwd)/redis.conf:/usr/local/etc/redis/redis.conf redis:7.2 redis-server /usr/local/etc/redis/redis.conf
```

### Tahap 2: Operasional Dasar Redis Pub/Sub

```bash
# Terminal 1: Subscriber
redis-cli SUBSCRIBE orders:notifications

# Terminal 2: Publisher
redis-cli PUBLISH orders:notifications '{"event":"order_created","id":"ORD-101"}'
```

### Tahap 3: Lifecycle Management Redis Streams

```bash
# 1. Ingestion stream baru menggunakan XADD (dengan soft-limit capping ~ 10000)
redis-cli XADD orders:stream MAXLEN ~ 10000 * order_id "ORD-101" user_id "USR-55" amount "250000"

# 2. Inisialisasi Consumer Group dari awal stream (ID 0)
redis-cli XGROUP CREATE orders:stream order-processing-group 0 MKSTREAM

# 3. Read Stream melalui Consumer Group
redis-cli XREADGROUP GROUP order-processing-group consumer-node-1 COUNT 1 BLOCK 2000 STREAMS orders:stream >

# 4. Inspeksi Status PEL (Pending Entries List)
redis-cli XPENDING orders:stream order-processing-group

# 5. Acknowledge message setelah pemrosesan sukses
# Format: XACK <stream> <group> <message-id>
redis-cli XACK orders:stream order-processing-group "1710921600000-0"
```

---

## 07: Contoh Kasus Sederhana

Implementasi Pub/Sub ringan menggunakan Node.js/TypeScript untuk invalidasi cache terdistribusi:

```typescript
// cache_invalidation.ts
import Redis from "ioredis";

const pub = new Redis({ host: "127.0.0.1", port: 6379 });
const sub = new Redis({ host: "127.0.0.1", port: 6379 });

const localMemoryCache = new Map<string, string>();

async function main() {
  // Subscribe channel invalidasi
  await sub.subscribe("cache:invalidate");

  sub.on("message", (channel, message) => {
    if (channel === "cache:invalidate") {
      const { key } = JSON.parse(message);
      localMemoryCache.delete(key);
      console.log(`[Cache Invalidation] Key '${key}' successfully purged locally.`);
    }
  });

  // Simulasi update state di instance ini
  localMemoryCache.set("user:100", "Budi Santoso");
  console.log("Local cache initialized:", localMemoryCache.get("user:100"));

  // Publish event invalidasi ke seluruh cluster instance
  setTimeout(async () => {
    const payload = JSON.stringify({ key: "user:100", timestamp: Date.now() });
    await pub.publish("cache:invalidate", payload);
  }, 1000);
}

main().catch(console.error);
```

---

## 08: Implementasi Production-Grade Lengkap

Sistem pemrosesan transaksi e-commerce berbasis Go menggunakan Redis Streams, dilengkapi:
1. Producer dengan *stream length trimming*.
2. Worker pool paralel dengan graceful shutdown.
3. Autoclaim/Recovery engine untuk menangkap pesan hang/crash worker lain.

```go
// main.go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/rand"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	StreamName    = "orders:events:v1"
	ConsumerGroup = "order-execution-cluster"
	MaxStreamLen  = 100000
	ClaimMinIdle  = 5 * time.Second
)

type OrderEvent struct {
	OrderID   string    `json:"order_id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	Timestamp time.Time `json:"timestamp"`
}

type StreamWorker struct {
	client       *redis.Client
	workerName   string
	wg           *sync.WaitGroup
	ctx          context.Context
	cancel       context.CancelFunc
}

func NewStreamWorker(client *redis.Client, name string) *StreamWorker {
	ctx, cancel := context.WithCancel(context.Background())
	return &StreamWorker{
		client:     client,
		workerName: name,
		wg:         &sync.WaitGroup{},
		ctx:        ctx,
		cancel:     cancel,
	}
}

func (w *StreamWorker) InitTopology(ctx context.Context) error {
	err := w.client.XGroupCreateMkStream(ctx, StreamName, ConsumerGroup, "0").Err()
	if err != nil && err.Error() != "BUSYGROUP Consumer Group name already exists" {
		return fmt.Errorf("failed to create consumer group: %w", err)
	}
	return nil
}

func (w *StreamWorker) ProduceEvent(ctx context.Context, order OrderEvent) (string, error) {
	data, err := json.Marshal(order)
	if err != nil {
		return "", err
	}

	args := &redis.XAddArgs{
		Stream: StreamName,
		MaxLen: MaxStreamLen,
		Approx: true,
		Values: map[string]interface{}{
			"payload":   string(data),
			"schema_v":  "1.0",
			"producer":  w.workerName,
		},
	}

	return w.client.XAdd(ctx, args).Result()
}

func (w *StreamWorker) StartConsumer(ctx context.Context) {
	w.wg.Add(1)
	go func() {
		defer w.wg.Done()
		log.Printf("[%s] Consumer daemon started", w.workerName)

		for {
			select {
			case <-ctx.Done():
				log.Printf("[%s] Halting consumer loop...", w.workerName)
				return
			default:
				// 1. Baca stream untuk pesan baru (ID: '>')
				entries, err := w.client.XReadGroup(ctx, &redis.XReadGroupArgs{
					Group:    ConsumerGroup,
					Consumer: w.workerName,
					Streams:  []string{StreamName, ">"},
					Count:    10,
					Block:    2 * time.Second,
				}).Result()

				if err != nil {
					if errors.Is(err, redis.Nil) || errors.Is(err, context.Canceled) {
						continue
					}
					log.Printf("[%s] Error reading stream: %v", w.workerName, err)
					time.Sleep(500 * time.Millisecond)
					continue
				}

				for _, stream := range entries {
					for _, message := range stream.Messages {
						w.processMessage(ctx, message)
					}
				}
			}
		}
	}()
}

func (w *StreamWorker) StartRecoveryDaemon(ctx context.Context) {
	w.wg.Add(1)
	go func() {
		defer w.wg.Done()
		ticker := time.NewTicker(3 * time.Second)
		defer ticker.Stop()

		var startID = "0-0"

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				// Auto-claim pending entries yang hang lebih dari ClaimMinIdle
				messages, nextID, err := w.client.XAutoClaim(ctx, &redis.XAutoClaimArgs{
					Stream:   StreamName,
					Group:    ConsumerGroup,
					Consumer: w.workerName,
					MinIdle:  ClaimMinIdle,
					Start:    startID,
					Count:    5,
				}).Result()

				if err != nil && !errors.Is(err, context.Canceled) {
					log.Printf("[%s] XAutoClaim error: %v", w.workerName, err)
					continue
				}

				startID = nextID

				for _, message := range messages {
					log.Printf("[%s] Recovered stale message: %s", w.workerName, message.ID)
					w.processMessage(ctx, message)
				}
			}
		}
	}()
}

func (w *StreamWorker) processMessage(ctx context.Context, msg redis.XMessage) {
	payloadRaw, ok := msg.Values["payload"].(string)
	if !ok {
		log.Printf("[%s] Invalid message payload structure: %s", w.workerName, msg.ID)
		w.client.XAck(ctx, StreamName, ConsumerGroup, msg.ID)
		return
	}

	var event OrderEvent
	if err := json.Unmarshal([]byte(payloadRaw), &event); err != nil {
		log.Printf("[%s] Unmarshal error (Poison Pill): %v. Acking to prevent loop.", w.workerName, err)
		w.client.XAck(ctx, StreamName, ConsumerGroup, msg.ID)
		return
	}

	// Simulasi mutasi data / pemrosesan bisnis
	time.Sleep(time.Duration(100+rand.Intn(200)) * time.Millisecond)
	log.Printf("[%s] Processed Order %s -> Amount: $%.2f", w.workerName, event.OrderID, event.Amount)

	// Acknowledge pesan setelah berhasil diproses
	if err := w.client.XAck(ctx, StreamName, ConsumerGroup, msg.ID).Err(); err != nil {
		log.Printf("[%s] Failed to XACK ID %s: %v", w.workerName, msg.ID, err)
	}
}

func (w *StreamWorker) Stop() {
	w.cancel()
	w.wg.Wait()
	log.Printf("[%s] All workers exited gracefully.", w.workerName)
}

func main() {
	rdb := redis.NewClient(&redis.Options{
		Addr:         "localhost:6379",
		Password:     "",
		DB:           0,
		PoolSize:     20,
		MinIdleConns: 5,
	})
	defer rdb.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("Redis connection refused: %v", err)
	}
	cancel()

	worker1 := NewStreamWorker(rdb, "worker-node-alpha")
	if err := worker1.InitTopology(context.Background()); err != nil {
		log.Fatalf("Topology init failure: %v", err)
	}

	// Jalankan Consumers
	worker1.StartConsumer(worker1.ctx)
	worker1.StartRecoveryDaemon(worker1.ctx)

	// Simulasi Publisher terpisah
	go func() {
		for i := 1; i <= 20; i++ {
			time.Sleep(300 * time.Millisecond)
			_, err := worker1.ProduceEvent(context.Background(), OrderEvent{
				OrderID:   fmt.Sprintf("ORD-%05d", i),
				UserID:    fmt.Sprintf("USR-%03d", rand.Intn(100)),
				Amount:    rand.Float64() * 1000,
				Timestamp: time.Now(),
			})
			if err != nil {
				log.Printf("Produce error: %v", err)
			}
		}
	}()

	// Graceful Shutdown Handler
	shutdownSig := make(chan os.Signal, 1)
	signal.Notify(shutdownSig, syscall.SIGINT, syscall.SIGTERM)
	<-shutdownSig

	log.Println("Shutting down workers...")
	worker1.Stop()
}
```

---

## 09: Diagram Alur Kerja ASCII

### Alur Eksekusi Streams Consumer Group & Auto-Claim Lifecycle

```
Producer                     Redis Server (Stream & PEL)                  Consumer Worker A         Consumer Worker B
   |                                     |                                         |                         |
   |--- XADD orders:stream ... --------->|                                         |                         |
   |    (Stream ID: 1710-0 generated)    |                                         |                         |
   |                                     |                                         |                         |
   |                                     |<--- XREADGROUP ('>') -------------------|                         |
   |                                     |     (Deliver 1710-0 to Worker A)        |                         |
   |                                     |===> [Add 1710-0 to PEL (Worker A)] ===>|                         |
   |                                     |---------------------------------------->|                         |
   |                                     |                                         | (CRASH OCCURS!)         |
   |                                     |                                         X (No XACK Sent)          |
   |                                     |                                                                   |
   |                                     |<--- XAUTOCLAIM (MinIdle: 5s) -------------------------------------|
   |                                     |     (PEL scans idle > 5000ms)                                     |
   |                                     |===> [Transfer 1710-0 ownership in PEL to Worker B]                |
   |                                     |------------------------------------------------------------------>|
   |                                     |                                                                   | (Processes Task)
   |                                     |<--- XACK orders:stream group 1710-0 ------------------------------|
   |                                     |===> [Evict 1710-0 from PEL]                                       |
   v                                     v                                                                   v
```

---

## 10: Analisis Trade-offs

| Dimensi Arsitektural | Redis Pub/Sub | Redis Streams | Apache Kafka | RabbitMQ |
| :--- | :--- | :--- | :--- | :--- |
| **Persistensi Data** | Tidak Ada (Ephemeral) | Ada (In-Memory + Disk RDB/AOF) | Ada (Distributed Commit Log Disk) | Ada (Disk/Memory Queues) |
| **Pola Konsumsi** | Broadcast (Fan-out) | Fan-out & Competing Consumers | Consumer Group Balancing | Competing Consumers & Routing |
| **Throughput (Ops/sec)** | ~1,000,000/sec | ~100,000 - 300,000/sec | ~500,000/sec (Batching) | ~50,000/sec |
| **Delivery Guarantee** | At-most-once | At-least-once | At-least-once / Exactly-once | At-least-once |
| **Overhead Memori** | Nol (Transient) | Moderat (Listpack/Radix Tree) | Nol pada Redis (Dedicated cluster) | Tergantung depth antrean |
| **Message Replay** | Tidak Didukung | Didukung (Read dari ID tertentu) | Sangat Optimal (Offset rewind) | Sangat Terbatas |
| **Kompleksitas Operasional** | Sangat Rendah | Rendah (Built-in Redis) | Sangat Tinggi (JVM, ZK/KRaft) | Menengah (Erlang VM) |

---

## 11: Best Practices & Antipatterns

### Best Practices
* **Gunakan Approximate Trimming (`MAXLEN ~`)**:
  Selalu gunakan operator `~` pada `XADD` atau `XTRIM`. Trimming presisi tanpa `~` memaksa Redis merestrukturisasi listpack node secara instan, menghasilkan lonjakan kompleksitas O(N) dan latency spike.
* **Terapkan DLQ Policy pada PEL Counter**:
  Jika counter pengiriman (`delivery_count`) pada `XPENDING` melebihi threshold (misal: > 5x), pindahkan pesan secara programatis ke stream Dead Letter Queue (`orders:stream:dlq`) dan panggil `XACK` pada stream utama untuk memutus infinite crash loop.
* **Gunakan Connection Pooling Khusus Sub/Consumer**:
  Jangan mencampuradukkan koneksi blocking (`XREAD ... BLOCK`, `SUBSCRIBE`) dengan koneksi pool transactional/query umum (`GET`, `SET`, `HGETALL`).

### Antipatterns
* **Unbounded Stream Growth**:
  Menjalankan `XADD` tanpa strategi limitasi `MAXLEN` atau `MINID`, yang berujung pada kehabisan memori server (*Out of Memory* - OOM Kill).
* **Pub/Sub untuk Event Finansial**:
  Menggunakan Pub/Sub untuk transaksi pembayaran. Jika subscriber restart atau jaringan mengalami micro-disconnection, data event hilang tanpa jejak audit.
* **Membiarkan Pesan Mengendap di PEL**:
  Lupa mengeksekusi `XACK` setelah operasi selesai. Hal ini menyebabkan ukuran memori PEL membesar tanpa batas meskipun stream sudah di-trim.

---

## 12: Security Hardening

Implementasikan pembatasan akses ketat menggunakan Redis ACL v2 (tersedia sejak Redis 6/7) untuk mengisolasi service worker:

```text
# 1. Konfigurasi User Producer: Hanya boleh menulis ke orders:stream
ACL SETUSER order_producer_svc on >ProdSecr3tPass! ~orders:events:* +xadd +ping -@all

# 2. Konfigurasi User Consumer: Hanya boleh membaca, claim, dan ack
ACL SETUSER order_consumer_svc on >ConsSecr3tPass! ~orders:events:* +xreadgroup +xack +xautoclaim +xpending +xgroup +ping -@all

# 3. Disable Dangerous Commands pada level Redis Daemon
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command KEYS ""
```

---

## 13: Observabilitas & Debugging

### Monitoring Metrics Kunci

1. **Consumer Group Lag**:
   Hitung selisih antara ID terakhir yang di-*generate* stream dan `last-delivered-id` milik Consumer Group.
   ```bash
   redis-cli XINFO GROUPS orders:events:v1
   ```
2. **Pending Entries Counter**:
   Memeriksa jumlah antrean unacknowledged message.
   ```bash
   redis-cli XPENDING orders:events:v1 order-execution-cluster
   ```
3. **Consumer Introspection**:
   ```bash
   redis-cli XINFO CONSUMERS orders:events:v1 order-execution-cluster
   ```

### Diagnostik Command Cheatsheet

```bash
# Debug detail struktur internal stream (Radix tree entries & listpack segments)
redis-cli XINFO STREAM orders:events:v1 FULL

# Observasi detail memory overhead untuk stream spesifik
redis-cli MEMORY USAGE orders:events:v1
```

---

## 14: Benchmarking & Performance

Jalankan pengujian throughput menggunakan tool bawaan `redis-benchmark`:

### Skenario 1: Benchmark Pub/Sub Throughput
```bash
redis-benchmark -t pub -q -n 100000 -c 50 -d 256
redis-benchmark -t sub -q -n 100000 -c 50
```

### Skenario 2: Benchmark Redis Streams Ingestion (Pipeline Mode)
```bash
redis-benchmark -r 100000 -n 1000000 -c 100 -P 16 \
  -d 512 XADD benchmark:stream "*" field1 "value1" field2 "value2"
```

### Optimasi Performa Engine
* **Batch Processing**: Gunakan opsi `COUNT 50` atau `COUNT 100` pada `XREADGROUP` untuk meminimalisir network round-trip.
* **Pipeline Acknowledgement**: Eksekusi batch `XACK` dalam satu pipeline TCP untuk mengurangi I/O contention.

---

## 15: Hands-on Lab Mini-Project

### Skenario Kasus
Rancang sistem streaming *Inventory Reservation System* yang memproses event order secara atomik dan menangani *worker failure simulation*.

### Langkah Eksekusi

1. **Jalankan Redis Environment**:
   ```bash
   docker run -d --name lab-redis -p 6379:6379 redis:7.2-alpine
   ```

2. **Jalankan Ingestion Script (Lab Producer)**:
   ```bash
   for i in {1..50}; do
     redis-cli XADD inventory:events * order_id "ORD-$i" sku "SKU-REDIS-BOOK" qty "1"
   done
   ```

3. **Inisialisasi Consumer Group**:
   ```bash
   redis-cli XGROUP CREATE inventory:events inventory-processors 0 MKSTREAM
   ```

4. **Simulasikan Crash Worker**:
   Baca 5 pesan pertama tanpa memberikan `XACK`:
   ```bash
   redis-cli XREADGROUP GROUP inventory-processors worker-crashed COUNT 5 STREAMS inventory:events >
   ```

5. **Lakukan Inspeksi & Recovery**:
   Lihat status antrean macet:
   ```bash
   redis-cli XPENDING inventory:events inventory-processors - + 10
   ```
   Ambil alih paksa (*claim*) pesan-pesan tersebut oleh worker aktif:
   ```bash
   redis-cli XAUTOCLAIM inventory:events inventory-processors worker-healthy 0 0-0 COUNT 10
   ```

6. **Acknowledge Semua Pesan Hasil Recovery**:
   Ambil ID pesan yang dikembalikan dan selesaikan transaksi dengan `XACK`.

---

## 16: Automated Testing & Verification

Contoh unit/integration testing menggunakan Go test framework dan testcontainers-go:

```go
// stream_test.go
package main

import (
	"context"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
)

func TestStreamProduceAndConsumePipeline(t *testing.T) {
	ctx := context.Background()
	rdb := redis.NewClient(&redis.Options{Addr: "localhost:6379"})
	defer rdb.Close()

	testStream := "test:stream:pipeline"
	testGroup := "test-group"

	// Cleanup
	rdb.Del(ctx, testStream)

	// Setup Group
	err := rdb.XGroupCreateMkStream(ctx, testStream, testGroup, "0").Err()
	if err != nil {
		t.Fatalf("Failed to initialize group: %v", err)
	}

	// Produce
	msgID, err := rdb.XAdd(ctx, &redis.XAddArgs{
		Stream: testStream,
		Values: map[string]interface{}{"metric": "cpu_load", "value": 85.5},
	}).Result()
	if err != nil {
		t.Fatalf("XADD failed: %v", err)
	}

	// Read via Consumer Group
	streams, err := rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
		Group:    testGroup,
		Consumer: "test-runner",
		Streams:  []string{testStream, ">"},
		Count:    1,
		Block:    1 * time.Second,
	}).Result()

	if err != nil {
		t.Fatalf("XREADGROUP failed: %v", err)
	}

	if len(streams) == 0 || len(streams[0].Messages) == 0 {
		t.Fatalf("Expected 1 message, got none")
	}

	consumedMsg := streams[0].Messages[0]
	if consumedMsg.ID != msgID {
		t.Errorf("Expected ID %s, got %s", msgID, consumedMsg.ID)
	}

	// Verify PEL Presence
	pel, err := rdb.XPending(ctx, testStream, testGroup).Result()
	if err != nil || pel.Count != 1 {
		t.Fatalf("Expected PEL count 1, got %d", pel.Count)
	}

	// Ack
	err = rdb.XAck(ctx, testStream, testGroup, consumedMsg.ID).Err()
	if err != nil {
		t.Fatalf("XACK failed: %v", err)
	}

	// Verify PEL Cleared
	pelAfter, _ := rdb.XPending(ctx, testStream, testGroup).Result()
	if pelAfter.Count != 0 {
		t.Errorf("Expected PEL count 0 after ACK, got %d", pelAfter.Count)
	}
}
```

---

## 17: Troubleshooting Guide

### Isu 1: Subscriber Terputus Tiba-Tiba (Pub/Sub)
* **Gejala Log Redis**: `Client id=X scheduled to be closed ASAP for overcoming of output buffer limits.`
* **Akar Masalah**: Subscribed client lambat membaca data (*slow consumer*), menyebabkan buffer client melewati ambang `client-output-buffer-limit pubsub`.
* **Solusi**: Tingkatkan limit buffer jika throughput traffic burst bersifat sementara:
  ```text
  CONFIG SET client-output-buffer-limit "pubsub 128mb 32mb 120"
  ```
  atau migrasikan sistem ke **Redis Streams**.

### Isu 2: Memori Redis Bocor Meski Stream Ditrim
* **Gejala**: Memori terus naik walau `MAXLEN` sudah dikonfigurasi.
* **Akar Masalah**: Pesan dikonsumsi namun tidak pernah di-`XACK`. Akibatnya, `Pending Entries List (PEL)` membesar secara eksponensial di dalam metadata node.
* **Solusi**: Audit PEL menggunakan `XPENDING <stream> <group> - + 100` dan eksekusi batch `XACK` pada entry kadaluarsa.

### Isu 3: High CPU Saat Eksekusi `XREADGROUP`
* **Gejala**: CPU Redis Server 100% konstan.
* **Akar Masalah**: Polling loop intensif pada aplikasi tanpa parameter `BLOCK` (busy-waiting loop).
* **Solusi**: Selalu set nilai timeout non-zero pada blocking call (misal: `BLOCK 2000`).

---

## 18: Checklist Produksi

- [ ] **Data Retention Sizing**: Semua command `XADD` menyertakan strategi `MAXLEN ~ <N>` atau `MINID ~ <Threshold>`.
- [ ] **Buffer Guard Configuration**: Nilai `client-output-buffer-limit pubsub` telah disesuaikan dengan skenario *worst-case traffic spike*.
- [ ] **Consumer Crash Recovery**: Terdapat background daemon yang mengeksekusi `XAUTOCLAIM` secara periodik untuk menangkap pesan hang di PEL.
- [ ] **Poison Pill Mitigation**: Penanganan error JSON/schema parser memiliki fallback ke Dead Letter Queue (DLQ) + `XACK` agar pipeline tidak macet.
- [ ] **Access Isolation**: Autentikasi berbasis Redis ACL v2 telah diaktifkan, membatasi hak akses producer dan consumer secara independen