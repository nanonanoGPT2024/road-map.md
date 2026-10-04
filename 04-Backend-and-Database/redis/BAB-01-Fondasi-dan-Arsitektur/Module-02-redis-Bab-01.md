# BAB 01: Fondasi dan Arsitektur Redis
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis (C4)** siklus hidup pemrosesan data internal Redis, mencakup *event-driven architecture* berbasis `ae.c`, I/O multiplexing (`epoll`/`kqueue`), dan alokasi memori via `jemalloc`.
- **Mengevaluasi (C5)** trade-off performa antara *single-threaded core execution* dan *threaded I/O* (Redis 6+) pada beban kerja *network-bound* vs *CPU-bound*.
- **Merancang (C6)** arsitektur persistensi hibrida (*hybrid persistence* RDB + AOF) yang meminimalkan *tail latency* (p99/p99.9) akibat *disk stall* dan Linux *Copy-on-Write* (CoW) overhead.
- **Mengimplementasikan (C3)** pola akses tingkat lanjut (*pipelining*, transaksi `MULTI`/`EXEC`, dan script atomik Lua) menggunakan driver enterprise (Go `go-redis/v9`) dengan mitigasi konkurensi skala tinggi.
- **Mendiagnosis dan Memitigasi (C4/C5)** anomali produksi kritis seperti *memory fragmentation*, *eviction storm*, *blocking commands*, serta *connection pool starvation*.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memiliki:
- Pemahaman solid mengenai struktur data primitif Redis (Strings, Hashes, Lists, Sets, Sorted Sets) dari Modul 01.
- Pemahaman fundamental tentang sistem operasi Linux: Virtual Memory, File Descriptors, System Calls (`epoll_wait`, `read`, `write`, `fork`), dan TCP/IP network stack.
- Kemampuan membaca dan menulis kode Go (Golang) tingkat menengah, mencakup *concurrency patterns* (`goroutine`, `channel`, `sync.Pool`).
- Akses terminal dengan Redis Server >= 7.0 dan utilitas `redis-benchmark` / `redis-cli`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Event Loop & I/O Multiplexing Engine (`ae.c`)
Redis dibangun di atas *event-driven reactor pattern*. File sumber `ae.c` mengabstraksi mekanisme multiplexing I/O kernel Linux (`epoll`), BSD (`kqueue`), dan Solaris (`evport`). 

```
+-------------------------------------------------------------------------+
|                              Redis Server                               |
|                                                                         |
|  +--------------------+         +------------------------------------+  |
|  |   Time Events      |         |            File Events             |  |
|  |  (serverCron, etc) |         |      (Network Socket Read/Write)   |  |
|  +---------+----------+         +-----------------+------------------+  |
|            |                                      |                     |
|            +------------------+-------------------+                     |
|                               |                                         |
|                               v                                         |
|                 +---------------------------+                           |
|                 |    aeMain() Event Loop    |                           |
|                 +-------------+-------------+                           |
|                               |                                         |
|                               v                                         |
|                 +---------------------------+                           |
|                 |  aeApiPoll() (epoll_wait) |                           |
|                 +-------------+-------------+                           |
|                               |                                         |
+-------------------------------|-----------------------------------------+
                                v
               [Linux Kernel: TCP Sockets / epoll set]
```

1. **File Events**: Mengelola socket TCP klien. Saat *file descriptor* (FD) siap dibaca, `epoll_wait()` membangkitkan *read event* yang memanggil handler `readQueryFromClient()`.
2. **Time Events**: Menjalankan fungsi periodik via `serverCron()` (default 100ms / frekuensi 10Hz-100Hz via direktif `hz`). Tugasnya:
   - Kedaluwarsa (*active key expiration*).
   - Inkrementasi siklus pembersihan memori (*incremental eviction*).
   - Pengawasan status persistensi AOF/RDB dan replikasi.
   - Penutupan koneksi *idle/timed-out*.

#### 3.2 Threaded I/O (Redis 6.0+)
Secara historis, Redis mengeksekusi operasi baca, eksekusi perintah, dan tulis secara single-threaded. Pada throughput >100k req/detik, bottleneck utama bergeser dari alokasi CPU database ke overhead sistem operasi saat membaca (*read*) dan menulis (*write*) buffer TCP socket.

Redis 6+ memperkenalkan **I/O Threads**:
- **Main Thread**: Tetap menjadi satu-satunya eksekutor perintah manipulasi memori. Hal ini mempertahankan determinisme komputasi (bebas *race condition* dan *locking overhead* pada level *keyspace*).
- **Worker I/O Threads**: Didelegasikan untuk mem-parsing buffer jaringan masuk (*network parsing*) dan menyalin buffer respons keluar (*network serialization*) ke TCP socket.

```
Incoming TCP Payload 
      │
      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ I/O Thread 1 │      │ I/O Thread 2 │      │ I/O Thread N │
│ (Parse RESP) │      │ (Parse RESP) │      │ (Parse RESP) │
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │
       └──────────────┬──────┴─────────────────────┘
                      ▼
           ┌──────────────────────┐
           │     MAIN THREAD      │
           │  (Execute Commands)  │ ──> [Atomic In-Memory Mutation]
           └──────────┬───────────┘
                      │
       ┌──────────────┴──────┬─────────────────────┐
       │                     │                     │
       ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ I/O Thread 1 │      │ I/O Thread 2 │      │ I/O Thread N │
│(Write Socket)│      │(Write Socket)│      │(Write Socket)│
└──────────────┘      └──────────────┘      └──────────────┘
```

#### 3.3 Anatomi Struktur Data Internal & Alokasi Memori
Redis tidak menyimpan string secara telanjang (*naked C-string*). Setiap entitas disimpan di dalam struktur `robj` (*Redis Object*) yang membungkus tipe data sesungguhnya:

```c
typedef struct redisObject {
    unsigned type:4;        // OBJ_STRING, OBJ_LIST, OBJ_HASH, dll.
    unsigned encoding:4;    // OBJ_ENCODING_RAW, OBJ_ENCODING_EMBSTR, OBJ_ENCODING_LISTPACK
    unsigned lru:24;        // Metadata eviction (LRU timestamp atau LFU counter)
    int refcount;           // Reference counting untuk garbage collection internal
    void *ptr;              // Pointer ke alokasi data riil (misal: SDS)
} robj;
```

##### Simple Dynamic String (SDS)
Struktur SDS memecahkan keterbatasan string bawaan C (`char*` dengan terminasi `\0`):
- Kompleksitas $O(1)$ untuk `STRLEN` (panjang string di-cache pada header).
- *Binary safe*: Mampu menyimpan payload arbitrer termasuk biner gambar atau serialized protobuf.
- Mengurangi fragmentasi alokasi via *pre-allocation* dan *lazy free*.

Struktur SDS (`sdshdr8`, `sdshdr16`, dst.):
```
+--------+------+-------+------------------------------+----+
|  len   | alloc| flags |        buf (Content)         | \0 |
| (uint) |(uint)| (byte)|  H  e  l  l  o     W  o  r  l |    |
+--------+------+-------+------------------------------+----+
```
- **EMBSTR vs RAW**: Jika ukuran string $\le 44$ byte, Redis mengalokasikan `robj` dan `SDS` dalam satu blok memori kontigu berukuran 64 byte (ukuran standar 1 cache line pada arsitektur CPU modern x86_64). Jika $> 44$ byte, alokasi dilakukan dua kali (`RAW` encoding) yang memicu fragmentasi memori lebih tinggi.

##### jemalloc Memory Allocator
Redis menggunakan `jemalloc` secara default di Linux. `jemalloc` membagi memori menjadi:
- **Small chunks** (berbagai ukuran diskrit: 8, 16, 32, 48, 64, ..., 32256 byte).
- **Large chunks** (halaman 4KB hingga multiple MB).

Ketika key dihapus, memori seringkali tidak langsung dikembalikan ke kernel OS, melainkan ditahan di dalam *free bin* milik `jemalloc` untuk reuse berikutnya. Hal ini menimbulkan perbedaan antara `used_memory` (memori yang dialokasikan oleh Redis) dan `used_memory_rss` (*Resident Set Size* yang dibaca oleh kernel Linux). Rasio keduanya diukur sebagai **Memfrag Ratio**:
$$\text{mem\_fragmentation\_ratio} = \frac{\text{used\_memory\_rss}}{\text{used\_memory}}$$
Rasio $> 1.5$ mengindikasikan fragmentasi tinggi (pemborosan RAM), sedangkan $< 1.0$ mengindikasikan swap ke disk (kematian performa).

#### 3.4 Persistensi Produksi: RDB, AOF, dan Fork Semantics
Redis menyediakan dua mesin persistensi:
1. **RDB (Redis Database Backup)**: Snapshot biner point-in-time.
2. **AOF (Append Only File)**: Log transaksional setiap operasi mutasi data.

##### Linux Kernel `fork()` dan Copy-on-Write (CoW)
Baik snapshot RDB (`BGSAVE`) maupun AOF Rewrite (`BGREWRITEAOF`) mengandalkan system call `fork()` untuk membuat proses *child*.
- `fork()` menduplikasi *page table* proses induk ke proses anak tanpa menduplikasi alokasi memori fisik secara langsung.
- Kedua proses menandai seluruh *physical memory pages* sebagai *Read-Only*.
- Ketika proses *parent* (Redis main thread) menerima operasi tulis (misal: `SET key val`), kernel Linux menginterupsi eksekusi, melempar Page Fault, lalu menduplikasi halaman memori 4KB tersebut secara fisik (**Copy-on-Write**).

```
State Awal (Sesaat Setelah fork()):
Parent Page Table ──┐
                    ├─► [ Physical Page 1 (Read-Only) ]
Child Page Table  ──┘

Saat Parent Menerima Write ke Page 1:
Parent Page Table ────► [ Physical Page 1' (New Dirty Copy, RW) ]
Child Page Table  ────► [ Physical Page 1 (Original, Read-Only)  ]
```

*Peringatan Produksi*: Jika sistem Anda menjalankan fitur **Transparent Huge Pages (THP)** pada level kernel, ukuran default alokasi halaman membesar dari 4KB menjadi 2MB. Maka saat terjadi 1 byte mutasi, kernel Linux menduplikasi 2MB memori secara penuh. Ini menyebabkan latensi spikes masif (p99 > 500ms) dan kehabisan memori (*OOM Killer*).

##### Mesin AOF: Sync Policies
AOF menulis perubahan ke userspace buffer, lalu memanggil syscall `write()` ke page cache kernel, dilanjutkan dengan syscall `fsync()` untuk flushing ke disk fisik.

| Polisi (`appendfsync`) | Integritas Data | Latensi Eksekusi | Keterangan Produksi |
| :--- | :--- | :--- | :--- |
| `always` | Tertinggi (0 data loss) | Sangat Buruk ($> 1-10\text{ ms}$) | Mematikan skalabilitas in-memory. |
| `everysec` | Optimal ($\le 2\text{ detik loss}$) | Sangat Rendah ($< 0.1\text{ ms}$) | Standar de-facto industri enterprise. |
| `no` | Tidak menentu (Tergantung OS) | Terendah | OS melakukan flush setiap ~30 detik. Risiko loss tinggi. |

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Naive Cache) | Redis Arsitektur Lanjutan (Production-Grade) |
| :--- | :--- | :--- |
| **Konektivitas** | Buat/Tutup koneksi TCP per request | Connection Pooling persisten dengan limit idle & pre-warmed connections |
| **Manipulasi Batch** | Loop eksekusi $N$ kali `GET/SET` sequential | Pipelining TCP atau Lua Scripting atomik |
| **Penanganan Memori** | Mengandalkan OS Swap saat RAM habis | Dynamic eviction policy (`volatile-lfu` / `allkeys-lfu`) dengan tuning memory watermark |
| **Latensi Persistensi** | Sync manual / Blocking disk writes | Background thread `io_uring` / `fork()` CoW non-blocking dengan Linux THP dimatikan |
| **Skalabilitas Jaringan**| Terbatas pada 1 core single-thread I/O | Multi-threaded I/O (Redis 6+) mengutilisasi multi-core CPU untuk TCP processing |

---

### 5. How (Workflow Detail)

Alur transmisi dan pemrosesan satu siklus instruksi mutasi atomik:

```
[Klien Eksternal]
       │
       ▼ 1. Kirim RESP payload melalui TCP Stream
[NIC / Socket Buffer Klien]
       │
       ▼ 2. Kernel memicu I/O event
[Linux Kernel epoll_wait()]
       │
       ▼ 3. ae.c membangkitkan aeFileEvent
[Worker I/O Thread] ─── (Parse RESP Command: e.g., "*3\r\n$3\r\nSET...")
       │
       ▼ 4. Parsing selesai, submit parsed command
[Main Thread Execution Engine]
       ├── Validasi Maxmemory & Algoritma Eviction (LFU/LRU jika memori penuh)
       ├── Eksekusi modifikasi in-memory hashtable (dict.c)
       ├── Tambahkan mutasi ke AOF Buffer & Replikasi Backlog Buffer
       │
       ▼ 5. Letakkan response payload ke client output buffer
[Worker I/O Thread] ─── (Write RESP string "+OK\r\n" ke socket)
       │
       ▼ 6. Syscall write() / send()
[NIC Klien]
```

---

### 6. Analogy & Diagram ASCII

Bayangkan Redis sebagai **Dapur Restoran Bintang Lima**:
- **Main Thread (Master Chef)**: Satu-satunya orang yang memegang pisau dan wajan. Master Chef tidak pernah mengupas bawang, mencuci piring, atau mengantar pesanan ke meja tamu agar fokus menjaga presisi dan konsistensi rasa (menghindari tabrakan di dapur / *race conditions*).
- **Worker I/O Threads (Asisten Pramusaji)**: Menerima bon pesanan dari tamu, menerjemahkannya ke dalam format yang dipahami Chef (*parsing request*), dan membawakan makanan yang sudah jadi kembali ke meja tamu (*network writing*).
- **jemalloc (Manajer Gudang Bahan)**: Menata bahan baku ke dalam kotak-kotak berukuran presisi (kotak 16g, 32g, 64g). Bila ada bahan dibuang, kotaknya tidak langsung dikembalikan ke toko penyewaan (OS), tetapi disimpan di rak gudang untuk dipakai memasak berikutnya.

```
       +-------------------------------------------------------------+
       |                     RESTORAN REDIS                          |
       |                                                             |
Tamu   | [Pramusaji 1] ───\                                          |
(Client)                  +──► [BON TIKET]                            |
       | [Pramusaji 2] ───┤          │                               |
       |                  │          ▼                               |
       |                  │   +---------------+                      |
       |                  │   |  MASTER CHEF  | ◄──► [Gudang Bahan]  |
       |                  │   | (Main Thread) |      (jemalloc)      |
       | [Pramusaji 1] ◄──┼── +-------+-------+                      |
       |                  │           │                              |
       | [Pramusaji 2] ◄──/           ▼ (Catat Buku Resep)           |
       |                      [Jurnal Log Harian] (AOF/Disk)         |
       +-------------------------------------------------------------+
```

---

### 7. Code Implementations (Standar Industri Go)

Implementasi enterprise di bawah mendemonstrasikan integrasi Go dengan Redis:
- Connection pooling resilient.
- Script atomik Lua untuk rate-limiting bertingkat (*token bucket with burst*).
- Batching via Pipelining.
- Penanganan failure / contextual timeout.

```go
// Package main menyediakan implementasi Redis Client Enterprise Production-Ready.
package main

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisEnterpriseClient merangkum Redis client dengan konfigurasi industri.
type RedisEnterpriseClient struct {
	client *redis.Client
}

// Config memetakan konfigurasi koneksi tingkat produksi.
type Config struct {
	Addrs        []string
	Password     string
	DB           int
	MinIdleConns int
	PoolSize     int
	MaxRetries   int
}

// Lua Token Bucket Rate Limiter
// Menggunakan Redis time untuk menghindari drift clock lokal mesin klien.
const tokenBucketScript = `
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2]) -- tokens per second
local requested = tonumber(ARGV[3])

-- Ambil waktu Redis via TIME command (mengembalikan [seconds, microseconds])
local redis_time = redis.call('TIME')
local now = tonumber(redis_time[1]) + (tonumber(redis_time[2]) / 1000000)

-- Fetch current state
local data = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_updated = now
else
    -- Hitung akumulasi token baru berdasarkan durasi delta waktu
    local delta = math.max(0, now - last_updated)
    tokens = math.min(capacity, tokens + (delta * refill_rate))
    last_updated = now
end

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    -- Pasang TTL agar key yang tidak aktif terhapus otomatis (idle 1 jam)
    redis.call('EXPIRE', key, 3600)
    return {1, tokens} -- 1 = Allowed
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    return {0, tokens} -- 0 = Denied
end
`

var rateLimitLua = redis.NewScript(tokenBucketScript)

// NewRedisClient menginisialisasi redis.Client dengan tuning connection pool tingkat lanjut.
func NewRedisClient(cfg Config) (*RedisEnterpriseClient, error) {
	opts := &redis.Options{
		Addr:     cfg.Addrs[0],
		Password: cfg.Password,
		DB:       cfg.DB,

		// Connection Pool Tuning
		PoolSize:        cfg.PoolSize,     // Maksimum total koneksi fisik
		MinIdleConns:    cfg.MinIdleConns, // Pertahankan pre-warmed idle connection
		MaxIdleConns:    cfg.PoolSize,     // Hindari agresif teardown socket
		ConnMaxIdleTime: 5 * time.Minute,
		ConnMaxLifetime: 1 * time.Hour,

		// Timeout Tuning
		DialTimeout:  2 * time.Second, // Timeout establishing socket TCP
		ReadTimeout:  1 * time.Second, // Mencegah connection leak akibat hung I/O
		WriteTimeout: 1 * time.Second,

		// Resiliency
		MaxRetries:      cfg.MaxRetries,
		MinRetryBackoff: 8 * time.Millisecond,
		MaxRetryBackoff: 512 * time.Millisecond,

		// Custom Dialer untuk KeepAlive TCP
		Dialer: func(ctx context.Context, network, addr string) (net.Conn, error) {
			netDialer := &net.Dialer{
				Timeout:   2 * time.Second,
				KeepAlive: 30 * time.Second,
			}
			return netDialer.DialContext(ctx, network, addr)
		},
	}

	client := redis.NewClient(opts)

	// Validasi koneksi langsung via Ping
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("gagal terhubung ke redis cluster/standalone: %w", err)
	}

	return &RedisEnterpriseClient{client: client}, nil
}

// AllowRequest mengeksekusi Token Bucket Lua Script secara atomik.
func (r *RedisEnterpriseClient) AllowRequest(ctx context.Context, key string, capacity, refillRate, cost float64) (bool, float64, error) {
	res, err := rateLimitLua.Run(ctx, r.client, []string{key}, capacity, refillRate, cost).Result()
	if err != nil {
		return false, 0, fmt.Errorf("evaluasi Lua rate-limit gagal: %w", err)
	}

	results, ok := res.([]interface{})
	if !ok || len(results) < 2 {
		return false, 0, errors.New("format balasan Lua script tidak valid")
	}

	allowed := results[0].(int64) == 1
	remainingTokens := 0.0

	switch v := results[1].(type) {
	case int64:
		remainingTokens = float64(v)
	case string:
		fmt.Sscanf(v, "%f", &remainingTokens)
	}

	return allowed, remainingTokens, nil
}

// ExecuteBatchPipelining mendemonstrasikan optimasi Round-Trip-Time (RTT) via Pipelining.
func (r *RedisEnterpriseClient) ExecuteBatchPipelining(ctx context.Context, tenantID string, events map[string]string) error {
	pipe := r.client.Pipeline()

	for subKey, payload := range events {
		targetKey := fmt.Sprintf("tenant:%s:events:%s", tenantID, subKey)
		pipe.Set(ctx, targetKey, payload, 24*time.Hour)
		pipe.HIncrBy(ctx, fmt.Sprintf("tenant:%s:metrics", tenantID), "total_events", 1)
	}

	// Eksekusi semua command dalam satu TCP packet RTT
	cmders, err := pipe.Exec(ctx)
	if err != nil && !errors.Is(err, redis.Nil) {
		return fmt.Errorf("gagal memproses pipeline batch: %w", err)
	}

	log.Printf("Sukses flush pipeline. Total dieksekusi: %d instruksi", len(cmders))
	return nil
}

func main() {
	cfg := Config{
		Addrs:        []string{"127.0.0.1:6379"},
		Password:     "",
		DB:           0,
		PoolSize:     50,
		MinIdleConns: 10,
		MaxRetries:   3,
	}

	client, err := NewRedisClient(cfg)
	if err != nil {
		log.Fatalf("Fatal: %v", err)
	}
	defer client.client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// 1. Eksekusi Rate Limiter
	key := "ratelimit:user_uuid_1337"
	allowed, remaining, err := client.AllowRequest(ctx, key, 10, 2, 1)
	if err != nil {
		log.Printf("Rate limit error: %v", err)
	} else {
		log.Printf("Rate Limit Result: Allowed=%t, Sisa Token=%.2f", allowed, remaining)
	}

	// 2. Eksekusi Pipeline
	batch := map[string]string{
		"event_1": "payload_a",
		"event_2": "payload_b",
		"event_3": "payload_c",
	}
	if err := client.ExecuteBatchPipelining(ctx, "acme_corp", batch); err != nil {
		log.Printf("Batch error: %v", err)
	}
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Aplikasi**: Gateway Pembayaran E-Commerce (Flash Sale Global).
- **Beban Puncak**: 250.000 Request per Second (RPS) pada API Idempotency Check.
- **Problem**: Setiap kali flash sale dimulai, *latency spike* melonjak dari p50 1.2ms ke p99 > 850ms. Ratusan transaksi gagal akibat timeout, memicu penumpukan koneksi dan server crash (*cascading failure*).

#### Root Cause Analysis (RCA)
1. **System Call Fork & Memory Spikes**: Redis dikonfigurasi dengan persistensi AOF `auto-aof-rewrite-percentage 100`. Ketika memori mencapai 16GB, background AOF rewrite memicu kernel `fork()`.
2. **Transparent Huge Pages (THP) Aktif**: Kernel Linux memiliki setting `[always]` pada `/sys/kernel/mm/transparent_hugepage/enabled`. Saat alokasi memori diubah oleh ribuan request flash sale, CoW menduplikasi blok memori per 2MB (bukan 4KB). Terjadi pembekuan main-thread sebesar 450ms selama memory allocation storm.
3. **Eviction Throttling**: Konfigurasi `maxmemory-policy` disetel ke `allkeys-lru` menggunakan Redis default (5 random samples). Saat memori mendekati batas `maxmemory`, main thread menghabiskan 30% siklus CPU hanya untuk mencari kandidat key yang harus dibuang (*eviction loop*).

#### Solusi Arsitektural & Hasil
1. **Kernel Optimization**:
   ```bash
   # Matikan THP
   echo never > /sys/kernel/mm/transparent_hugepage/enabled
   # Alokasikan overcommit memory
   sysctl vm.overcommit_memory=1
   # Perbesar socket listen backlog
   sysctl -w net.core.somaxconn=65535
   ```
2. **Redis Configuration Remediations**:
   ```text
   # Mengaktifkan Multi-Threaded I/O untuk memproses traffic TCP skala 250k RPS
   io-threads 4
   io-threads-do-reads yes

   # Ubah kebijakan eviction ke LFU (Least Frequently Used) yang lebih deterministic
   maxmemory-policy volatile-lfu
   maxmemory-samples 10

   # Nonaktifkan AOF rewrite saat traffic tinggi, ganti ke scheduled cron saat off-peak
   no-appendfsync-on-rewrite yes
   auto-aof-rewrite-percentage 0
   ```
3. **Hasil Metrik**:
   - **Throughput**: Stabil memproses 260.000 RPS.
   - **Latensi p99**: Turun drastis dari 850ms ke **2.1ms**.
   - **Memory Copy Overhead**: Berkurang sebesar 88% selama proses background snapshot.

---

### 9. Trade-offs Architecture Analysis

#### 9.1 Mekanisme Persistensi: AOF vs RDB vs Hybrid

```
AOF (everysec) ───[ Tinggi ]──────── Integritas Data ───────[ Rendah ]── RDB Snapshot
                  [ Buruk  ]──────── RTO / Restore Speed ───[ Cepat  ]──
                  [ Tinggi ]──────── I/O Disk Load ─────────[ Rendah ]──
```

| Tipe Persistensi | Throughput Impact | Recovery Time (RTO) | Data Loss Risk (RPO) | Cost (Disk I/O) |
| :--- | :--- | :--- | :--- | :--- |
| **RDB Only** | Sangat Rendah | Sangat Cepat (Parsing binary direct ke memory) | Tinggi (Sejak snapshot terakhir, misal 15 menit) | Rendah (Batch sequential disk write) |
| **AOF (`everysec`)**| Sedang (~5-10% CPU overhead) | Lambat (Harus replay jutaan query di single thread) | Rendah (Maksimum 1-2 detik) | Tinggi (Append terus menerus ke disk) |
| **Hybrid (RDB Preamble + AOF)** | Seimbang | Cepat (Load base RDB + replay sisa delta AOF) | Rendah (Maksimum 1-2 detik) | Sedang |

#### 9.2 Threaded I/O vs Single-Threaded Purni

| Metrik | Single-Threaded | Threaded I/O (`io-threads 4`) |
| :--- | :--- | :--- |
| **Memory Footprint** | Rendah (0 thread synchronization overhead) | Sedang (+~10-15% memory untuk I/O buffers) |
| **Throughput (Small Payload)** | ~100k - 120k RPS | ~250k - 350k RPS |
| **Kompleksitas Debugging** | Sangat Mudah (Deterministic execution trace) | Tinggi (Perlu analisis race condition socket/epoll) |
| **Context Switching Overhead** | 0% (Hanya terikat pada core pinning) | Ada CPU context switching jika jumlah thread > core CPU fisik |

#### 9.3 Algoritma Eviction: LRU vs LFU

```
Akses Pattern:
Key A: Diakses 1000x minggu lalu, tidak pernah diakses hari ini.
Key B: Baru diakses 1x lima detik lalu.

Under LRU (Least Recently Used): Key A dibuang, Key B dipertahankan. (Sering salah prediksi)
Under LFU (Least Frequently Used): Key B dibuang, Key A dipertahankan (Frekuensi historis dilindungi).
```

---

### 10. Common Mistakes & Troubleshooting

#### 1. Menggunakan Command Algoritmik $O(N)$ di Produksi
- **Kesalahan**: Menjalankan `KEYS *`, `HGETALL` pada hash dengan 100k field, atau `SMEMBERS` pada set masif.
- **Dampak**: Redis memblokir seluruh operasi lain pada main thread. Semua request klien lain mengalami timeout.
- **Solusi**: Gunakan inkremental iterator: `SCAN`, `HSCAN`, `SSCAN`. Pasang batasan di sisi proxy/infra (misal: `rename-command KEYS ""` di `redis.conf`).

#### 2. Masalah Bigkeys Mengakibatkan Memory Latency
- **Diagnosa**:
  ```bash
  redis-cli --bigkeys
  redis-cli --memkeys
  ```
- **Mitigasi**: Jangan pernah menghapus key berukuran masif dengan command primitif `DEL` (karena alokasi `free()` dilakukan secara blocking synchronous). Gunakan:
  ```bash
  UNLINK key_raksasa   # Menghapus metadata key secara instan, mendealokasikan memori via background thread (lazy freeing)
  ```

#### 3. Memory Fragmentation Menguras Alokasi Server
- **Deteksi**: Periksa metrik via `redis-cli INFO memory`.
  ```text
  used_memory:10737418240 (10 GB)
  used_memory_rss:19327352832 (18 GB)
  mem_fragmentation_ratio:1.80
  ```
- **Solusi Tanpa Restart**: Aktifkan online dynamic defragmentation jemalloc:
  ```bash
  CONFIG SET activedefrag yes
  CONFIG SET active-defrag-ignore-bytes 100mb
  CONFIG SET active-defrag-threshold-lower 10
  CONFIG SET active-defrag-cycle-max 50
  ```

---

### 11. Best Practices & Production Checklist

#### Kernel & Operating System Level
- [ ] Nonaktifkan Linux Transparent Huge Pages:
  ```bash
  echo never > /sys/kernel/mm/transparent_hugepage/enabled
  ```
- [ ] Atur Virtual Memory Overcommit ke mode 1:
  ```bash
  sysctl vm.overcommit_memory=1
  ```
- [ ] Naikkan somaxconn TCP Listen Backlog:
  ```bash
  sysctl -w net.core.somaxconn=65535
  ```
- [ ] Naikkan batas file descriptor proses di `/etc/security/limits.conf`:
  ```text
  redis soft nofile 65536
  redis hard nofile 65536
  ```

#### Redis Configuration Level (`redis.conf`)
- [ ] Konfigurasi hard limit memori mutlak: `maxmemory <80% Total RAM Mesin>`.
- [ ] Pilih eviction policy yang tepat: `maxmemory-policy volatile-lfu` atau `allkeys-lru`.
- [ ] Aktifkan `lazyfree-lazy-eviction yes`, `lazyfree-lazy-expire yes`, `lazyfree-lazy-server-del yes`.
- [ ] Gunakan persistensi hibrida: `aof-use-rdb-preamble yes`.
- [ ] Jangan gunakan database index non-zero (`SELECT 1`, `SELECT 2`). Gunakan instance Redis terisolasi. Multi DB adalah anti-pattern yang sudah ditinggalkan.

#### Application & Driver Level
- [ ] Terapkan client-side connection pooling. Larang inisialisasi koneksi per HTTP request.
- [ ] Atur socket connect, read, dan write timeouts secara eksplisit (Max 1-2 detik).
- [ ] Kompresi payload string yang berukuran di atas 2KB menggunakan `zstd` atau `snappy` sebelum dikirim ke Redis untuk menghemat bandwidth TCP dan memory cacheline.

---

### 12. Hands-on Practice

Buat direktori praktikum dengan struktur berikut:
```text
hands-on/m02/
├── docker-compose.yml
├── redis.conf
└── main.go
```

#### Langkah 1: Siapkan Konfigurasi `redis.conf`
Simpan kode berikut di `hands-on/m02/redis.conf`:
```text
port 6379
bind 0.0.0.0
protected-mode no
tcp-backlog 2048
timeout 0
tcp-keepalive 300

# Threaded I/O Configuration
io-threads 2
io-threads-do-reads yes

# Memory Management
maxmemory 256mb
maxmemory-policy allkeys-lfu
maxmemory-samples 10
activedefrag yes

# Lazy Freeing
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes

# Persistence Hybrid
appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite yes
aof-use-rdb-preamble yes
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

#### Langkah 2: Buat Environment via `docker-compose.yml`
Simpan di `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'
services:
  redis-enterprise:
    image: redis:7.2-alpine
    container_name: redis_m02
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    volumes:
      - ./redis.conf:/usr/local/etc/redis/redis.conf
      - redis_data:/data
    ports:
      - "6379:6379"
    ulimits:
      nproc: 65535
      nofile:
        soft: 65535
        hard: 65535

volumes:
  redis_data:
```

Jalankan container:
```bash
docker compose up -d
```

#### Langkah 3: Uji Benchmarking Performa Threaded I/O & Pipeline
Jalankan benchmark perbandingan pemanggilan standar vs pipelining via container:
```bash
# Uji SET Standard Sequential
docker exec -it redis_m02 redis-benchmark -h 127.0.0.1 -p 6379 -t set -n 100000 -q

# Uji SET dengan Pipeline (Batching 16 commands)
docker exec -it redis_m02 redis-benchmark -h 127.0.0.1 -p 6379 -t set -n 100000 -P 16 -q
```
*Amati lompatan throughput (RPS) hingga 4-5x lipat saat menggunakan pipeline.*

---

### 13. Exercises

#### Level Easy
Ekstrak daftar top 5 memory consumers secara manual menggunakan `redis-cli` tanpa memblokir server.
- **Tugas**: Tulis perintah bash satu baris (*one-liner*) memanfaatkan `redis-cli --scan` dan `redis-cli DEBUG OBJECT` atau `MEMORY USAGE` untuk mengurutkan key terbesar pada database.

#### Level Medium
Buat script Go yang mendemonstrasikan **Pessimistic Locking vs Optimistic Locking (`WATCH`/`MULTI`/`EXEC`)**:
- Simulasikan *race condition* di mana 50 goroutine mencoba mengurangi stok inventori item yang sama (stok awal: 20).
- Buktikan bahwa eksekusi tanpa transaction menghasilkan data korup (stok minus), sedangkan implementasi `WATCH` menghasilkan stok akhir tepat 0 tanpa *over-selling*.

#### Level Hard
Rancang dan implementasikan **Sliding Window Log Rate Limiter** atomik murni di dalam Redis menggunakan **Sorted Set (ZSET)** via Lua Script:
- Key: ID Pengguna.
- Score: Unix Epoch Milliseconds.
- Member: Unique Request ID / UUID.
- Alur Lua:
  1. Hapus record transaksi yang berada di luar jendela waktu (`ZREMRANGEBYSCORE`).
  2. Hitung jumlah transaksi tersisa di jendela saat ini (`ZCARD`).
  3. Evaluasi apakah transaksi melebihi limit. Jika ya, tolak (`return 0`).
  4. Jika tidak, tambahkan entri baru (`ZADD`), set TTL, dan terima (`return 1`).

---

### 14. Real-World Architectural Challenge

#### Skenario Kasus: Outage Misterius "Core Banking Reconciliation"
Sebuah bank digital mengalami lonjakan latensi kritis setiap pukul 00:00 malam pada klaster Redis Core Transaction Cache.
- **Gejala**:
  - Main thread Redis *freeze* total selama 8 hingga 14 detik.
  - Health check Kubernetes gagal membunuh container (*Restart Storm*).
  - CPU usage melonjak hingga 100% pada satu core.
  - Metrik `INFO commandstats` menunjukkan latency command `EXPIRE` atau background cleanup melonjak puluhan ribu persen.
- **Kondisi Data**:
  - Aplikasi menaruh 5.000.000 key data sesi login pengguna setiap hari dengan TTL tepat `86400` detik (24 jam flat), dieksekusi serentak pada deployment pukul 00:00:00 malam sebelumnya.
- **Tantangan Arsitektur**:
  1. Analisis secara internal apa yang terjadi di dalam mesin `serverCron()` dan mekanisme *Active Key Expiry Engine* Redis saat jutaan key hangus pada detik yang persis sama.
  2. Susun rancangan remedi arsitektur tingkat kode aplikasi (*client-side mitigation*) dan konfigurasi server Redis untuk mengeliminasi latensi spike tersebut tanpa mengurangi integritas bisnis kedaluwarsa sesi.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)

1. Mengapa Redis tetap mengeksekusi manipulasi data pada single-thread utama meskipun fitur Threaded I/O (Redis 6+) telah diaktifkan?
   - A. Karena Linux kernel tidak mengizinkan multi-threading pada socket TCP.
   - B. Untuk menghindari race conditions, data lock overhead (mutex), dan mempertahankan sifat atomik murni tanpa locking complexity.
   - C. Karena modul jemalloc tidak kompatibel dengan arsitektur multi-thread.
   - D. Agar kompatibel dengan library lama berbahasa C.

2. Kapan Redis memilih encoding `EMBSTR` daripada `RAW` untuk tipe data String?
   - A. Ketika data string merupakan angka floating point murni.
   - B. Ketika panjang string tidak melebihi 44 byte, sehingga memory buffer SDS dan header robj dapat dialokasikan bersamaan dalam 1 cache line 64-byte.
   - C. Ketika key diberi tag khusus kompresi biner.
   - D. Hanya jika persistensi AOF dinonaktifkan.

3. Apa efek samping dari system call Linux `fork()` pada operasi persistensi Redis jika kernel mengaktifkan Transparent Huge Pages (THP)?
   - A. Mengurangi pemakaian memori server secara drastis.
   - B. Mempercepat proses snapshotting RDB menjadi 10x lebih instan.
   - C. Menyebabkan duplikasi memori Copy-on-Write (CoW) menjadi boros (alokasi per 2MB bukan 4KB) dan memicu spike latensi p99 main-thread.
   - D. Membuat Redis crash dengan error *Segmentation Fault* seketika.

4. Command mana yang paling aman untuk menghapus key set raksasa dengan jutaan elemen tanpa memblokir pemrosesan request lain?
   - A. `DEL`
   - B. `REMOVE`
   - C. `UNLINK`
   - D. `POP ALL`

5. Apa arti metrik `mem_fragmentation_ratio` jika output bernilai `0.85`?
   - A. Redis membuang 15% memori akibat fragmentasi heap.
   - B. Sebagian memori Redis telah di-swap keluar ke disk fisik oleh kernel OS, menandakan performa sistem berada dalam bahaya kritis.
   - C. Redis berjalan dalam mode ultra-kompresi.
   - D. Kapasitas RAM fisik server masih tersisa 85%.

---

#### Bagian 2: Intermediate (Pilihan Ganda)

6. Pada arsitektur persistensi AOF, opsi `appendfsync everysec` berarti:
   - A. Main thread melakukan pemanggilan blocking system call `fsync()` setiap satu detik tepat.
   - B. Penulisan payload ke OS page cache dilakukan oleh main thread, sementara eksekusi syscall `fsync()` didelegasikan ke thread background terpisah setiap detik.
   - C. Data dijamin 100% tidak akan pernah hilang dalam kondisi kernel crash sekalipun.
   - D. AOF Rewrite otomatis dijalankan setiap 1 detik.

7. Perhatikan implementasi transaksi:
   ```text
   WATCH counter
   MULTI
   INCR counter
   EXEC
   ```
   Apa yang terjadi jika ada klien lain yang mengubah `counter` di antara pemanggilan `WATCH` dan `EXEC`?
   - A. Command `EXEC` melempar runtime exception dan memutus koneksi TCP.
   - B. Operasi transaksi dibatalkan, `EXEC` mengembalikan `nil` multi-bulk reply, dan klien bertanggung jawab melakukan retry.
   - C. Redis mengantrekan perubahan klien lain tersebut ke antrean isolasi background.
   - D. Redis memblokir klien lain tersebut sampai transaksi selesai.

8. Dalam algoritma eviction `volatile-lfu`, metrik apa yang digunakan Redis untuk menentukan kandidat key yang harus dibuang?
   - A. Timestamp terakhir key diakses, diambil dari seluruh key di database.
   - B. Kombinasi frekuensi akses logaritmik (*decaying counter*) dan waktu akses, dievaluasi khusus pada key yang memiliki konfigurasi TTL/Expire.
   - C. Ukuran payload memori terbesar pada key tanpa TTL.
   - D. Urutan key pertama kali dimasukkan ke dalam memori (*First-In-First-Out*).

9. Apa kegunaan utama dari teknik **Pipelining** pada Redis?
   - A. Mengeksekusi mutasi data secara atomik di mana operasi tidak bisa diinterupsi oleh klien lain.
   - B. Meminimalisasi network round-trip time (RTT) dengan mengirimkan sekelompok batch perintah sekaligus ke dalam buffer TCP tanpa menunggu balasan per instruksi.
   - C. Menghubungkan output stream dari satu Redis instance langsung ke instance lain.
   - D. Melakukan partisi sharding otomatis di level transport layer.

10. Jika parameter konfigurasi `maxmemory-policy` disetel ke `noeviction`, apa respons Redis saat memori mencapai kapasitas limit `maxmemory` dan menerima command `SET` baru?
    - A. Mengembalikan pesan error `OOM command not allowed when used memory > 'maxmemory'`.
    - B. Secara acak mematikan koneksi klien paling lama.
    - C. Otomatis memicu dump file RDB lalu menghapus database secara diam-diam.
    - D. Menulis sisa data langsung ke swap storage OS tanpa batasan.

---

#### Bagian 3: Skenario Kasus Produksi

11. **Skenario 1**: Anda memantau klaster Redis menggunakan monitoring Grafana dan mendeteksi metrik *instantaneous_ops_per_sec* turun drastis dari 80.000 ke 200 RPS, sementara latency p999 melonjak ke 2.500ms. Log aplikasi mendeteksi error `Command timed out after 1000ms`. Saat Anda mengeksekusi `redis-cli SLOWLOG GET 10`, muncul baris berikut:
    ```text
    1) (integer) 402
    2) (integer) 1711928000
    3) (integer) 2450000  # Durasi dalam microsecond (~2.45 detik)
    4) 1) "SMEMBERS"
       2) "global:authorized_user_uuids"
    ```
    Jelaskan apa yang sedang terjadi di internal server Redis dan langkah darurat serta jangka panjang apa yang harus Anda lakukan.

12. **Skenario 2**: Sebuah pipeline data analitik melakukan pengiriman batch write menggunakan Redis Pipelining dengan payload 500.000 command `HSET` dalam satu kali pemanggilan flush dari klien. Server Redis seketika mengalami lonjakan memori tak terkendali hingga terbunuh oleh kernel Linux via `Out Of Memory (OOM) Killer`, meskipun total ukuran payload riil data yang ditulis hanya berkisar ~30MB. Apa penyebab struktural di internal Redis buffer yang memicu lonjakan memori tersebut?

13. **Skenario 3**: Sebuah arsitektur payment idempotency key menyimpan status request token menggunakan Redis. Developer menggunakan script Lua yang berjalan selama rata-rata 60ms karena melakukan kalkulasi kompleks dan loop traversing. Mengapa penggunaan script Lua berdurasi 60ms ini merupakan anti-pattern yang berbahaya bagi performa high-throughput sistem Redis, dan bagaimana mendesain ulang arsitekturnya?

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Bagian 1: Basic
1. **Jawaban: B**. Redis mempertahankan arsitektur single-thread untuk eksekusi perintah demi menghindari kebutuhan concurrency synchronization primitive (mutex/lock) yang mahal dan kompleks, serta menjaga konsistensi state data secara deterministik.
2. **Jawaban: B**. String berukuran $\le 44$ byte memanfaatkan `EMBSTR` agar alokasi struct metadata `robj` dan payload `sdshdr8` berada dalam satu cacheline kontigu (64-byte), mengoptimalkan efisiensi memory allocation dan mengurangi cache misses pada level hardware CPU.
3. **Jawaban: C**. THP memaksa kernel Linux menggunakan memory page 2MB (bukan 4KB). Setiap ada mutasi 1 byte saja pada halaman tersebut, kernel menyalin utuh 2MB memori (*Copy-on-Write*), melipatgandakan beban alokasi dan memblokir main thread.
4. **Jawaban: C**. `UNLINK` menghapus key namespace secara non-blocking ($O(1)$) dan menyerahkan proses de-alokasi memori aktual ke thread background (`bio.c`).
5. **Jawaban: B**. Rasio $< 1.0$ membuktikan bahwa Resident Set Size (RSS) memori lebih kecil daripada memori logika yang diminta Redis, yang merupakan indikator valid bahwa kernel Linux telah memindahkan sebagian halaman memori Redis ke file swap disk.

#### Bagian 2: Intermediate
6. **Jawaban: B**. Pada opsi `everysec`, main thread hanya melakukan syscall `write()` ke buffer sistem operasi secara non-blocking. Thread background `bio.c` (Background I/O) yang akan menjalankan fsync setiap detik, menyeimbangkan durabilitas data dan latensi.
7. **Jawaban: B**. Ini adalah mekanisme *Optimistic Concurrency Control*. Jika key yang di-watch dimutasi oleh koneksi lain sebelum `EXEC` dipanggil, transaksi akan diabaikan secara otomatis dan `EXEC` mengembalikan `nil`.
8. **Jawaban: B**. LFU (Least Frequently Used) melacak frekuensi hit menggunakan algoritma Morris counter 8-bit yang terdegradasi seiring berjalannya waktu (decaying factor), diaplikasikan hanya pada subset data yang memiliki TTL jika memilih varian `volatile-lfu`.
9. **Jawaban: B**. Pipelining mengirimkan banyak perintah dalam satu paket TCP transfer stream tanpa blocking menunggu ack setiap command, mengurangi overhead konteks network round trip (RTT) dan system call overhead secara dramatis.
10. **Jawaban: A**. Kebijakan `noeviction` secara ketat menolak operasi mutasi data baru yang membutuhkan alokasi memori tambahan dan melempar error Out of Memory ke layer aplikasi, namun tetap mengizinkan operasi read/hapus.

#### Bagian 3: Skenario Kasus Produksi
11. **Pembahasan Skenario 1**:
    - *Penyebab*: Pemanggilan perintah $O(N)$ `SMEMBERS` pada set berukuran masif (`global:authorized_user_uuids`) memblokir main thread Redis selama ~2.45 detik. Karena Redis single-threaded, ribuan request lain di antrean socket buffer mengalami timeouts dan cascading failure.
    - *Solusi Darurat*: Identifikasi IP klien pemanggil dan batalkan query atau putus koneksinya via `CLIENT KILL`. Segera ubah command di level aplikasi.
    - *Solusi Jangka Panjang*: Ganti `SMEMBERS` dengan `SSCAN` untuk membaca data secara bertahap (chunking), atau jika tujuannya hanya validasi membership, ubah ke `SISMEMBER` yang memiliki kompleksitas $O(1)$.
12. **Pembahasan Skenario 2**:
    - *Penyebab*: Ketika klien mengirim 500.000 command dalam satu pipeline raksasa, Redis harus mengalokasikan memori untuk menahan *Query Buffer* (input) serta menampung seluruh respons pada *Output Buffer* di RAM secara bersamaan sebelum dikirim balik ke network.
    - Lonjakan alokasi buffer klien (*client output buffer*) ini melampaui sisa memori fisik server hingga kernel OS memicu OOM Killer untuk menembak proses Redis.
    - *Solusi*: Batasi ukuran batch chunking pipeline di sisi klien (maksimal 500 hingga 1.000 command per batch execution).
13. **Pembahasan Skenario 3**:
    - *Penyebab*: Eksekusi script Lua di Redis bersifat atomik dan memblokir main thread. Selama 60ms script berjalan, server Redis mengalami *freeze total* untuk ratusan ribu request lain (pada 100k RPS, durasi 60ms menahan ~6.000 antrean request yang masuk).
    - *Redesain*:
      1. Pecah logika kalkulasi rumit dan komputasi berat agar dijalankan di sisi aplikasi worker (Go/Node.js).
      2. Gunakan Redis murni hanya untuk operasi state atomic checking (misal via `SET key token NX EX 30`).
      3. Jika mutasi multi-key diperlukan, pecah menjadi potongan skrip Lua atomik kecil dengan execution latency $< 1\text{ ms}$.

---

### 16. Summary
- **Mekanisme Inti**: Redis mengandalkan event loop non-blocking berbasis reactor pattern (`ae.c`) yang mengabstraksi abstraksi kernel I/O multiplexing (`epoll`).
- **Skalabilitas Jaringan**: Redis 6+ Threaded I/O mendelegasikan parsing protokol TCP dan transfer buffer ke thread worker independen, sementara eksekusi perintah logika memori tetap beroperasi pada single main thread demi mempertahankan atomisitas data tanpa concurrency locking cost.
- **Efisiensi Memori**: Alokator `jemalloc` dan format data dinamis seperti SDS (Simple Dynamic Strings) serta `listpack` dirancang untuk mengoptimalkan utilisasi cache-line CPU dan meminimalkan fragmentasi memori.
- **Ketahanan Produksi**: Mengoperasikan Redis pada skala enterprise menuntut disiplin tingkat sistem operasi: mematikan Transparent Huge Pages (THP), mengonfigurasi batas memory eviction LFU secara presisi, serta memanfaatkan asynchronous lazy freeing (`UNLINK`) dan Pipelining/Lua untuk menghindari blocking CPU latency.