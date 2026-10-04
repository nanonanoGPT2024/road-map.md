# Bab 01: Arsitektur Fundamental Redis
## Module 01: In-Memory Engine, Reactor Pattern, dan Event Loop

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis mekanisme internal Redis berbasis arsitektur *single-threaded event loop* dan bagaimana *I/O multiplexing* (`epoll`, `kqueue`) mengeksekusi puluhan ribu operasi per detik tanpa *thread contention*.
*   Mengidentifikasi representasi struktur data tingkat rendah di memori, termasuk abstraksi `redisObject`, *Simple Dynamic String* (SDS), dan alokator memori `jemalloc`.
*   Mengevaluasi batasan performa terkait *Head-of-Line* (HoL) *blocking* akibat perintah $O(N)$ dan menentukan strategi mitigasi berbasis arsitektur non-blocking.
*   Mengonfigurasi dan mengoperasikan instans Redis siap produksi dengan parameter memori, jaringan, dan *eviction policy* yang optimal.
*   Mendiagnosis anomali performa menggunakan telemetri *native* (`INFO`, `SLOWLOG`, `LATENCY DOCTOR`) dan metrik sistem operasi Linux.

---

### 2. Fundamental Concept
Redis (*Remote Dictionary Server*) adalah *in-memory data structure store* yang beroperasi pada lapisan RAM untuk menjamin latensi baca dan tulis pada level submilisidetik (*sub-millisecond latency*). 

Secara mekanis, keunggulan performa Redis didasarkan pada tiga fondasi rekayasa perangkat lunak:
1.  **RAM vs. Disk Access Mechanics**: Waktu akses memori utama (DRAM) berada pada rentang ~100 nanodetik, dibandingkan dengan NVMe SSD (~10–100 mikrosidetik) atau HDD mekanik (~10 milidetik). Redis meniadakan operasi *disk seek/write* sinkron pada *critical execution path*.
2.  **I/O Multiplexing & Reactor Pattern**: Redis mengimplementasikan varian dari *Reactor Pattern*. Alih-alih membuat satu *thread* atau *process* per koneksi klien (seperti model Apache prefork atau model konkurensi berbasis *thread pool* berukuran besar yang memicu *context switching* masif), satu *thread* utama Redis memantau ratusan ribu soket jaringan secara non-blocking menggunakan primitif kernel sistem operasi (`epoll` pada Linux, `kqueue` pada BSD/macOS).
3.  **Bebas Sinkronisasi (*Lock-Free Execution Engine*)**: Karena perintah dieksekusi secara serial oleh satu *thread* utama, Redis tidak memerlukan primitif sinkronisasi seperti *mutex*, *read-write locks*, atau *condition variables* pada struktur data internalnya. Hal ini meniadakan *race condition*, *deadlock*, dan degradasi performa akibat *lock contention*.

---

### 3. Why It Matters
Dalam arsitektur sistem terdistribusi modern, basis data relasional berbasis disk (seperti PostgreSQL atau MySQL) menjadi *bottleneck* utama ketika throughput transaksi melebihi kapasitas I/O subsistem penyimpanan (*disk I/O saturation*). Menempatkan sistem komputasi berlatensi tinggi pada *hot path* pemrosesan permintaan HTTP/gRPC akan menyebabkan *cascading failures* dan penumpukan antrean koneksi (*connection backlog exhaustion*).

Kegagalan memahami model eksekusi Redis sering berujung pada insiden fatal di level produksi:
*   **Pemblokiran Tak Disengaja (*Accidental Blocking*)**: Eksekusi algoritma $O(N)$ seperti `KEYS *` atau deserialisasi objek raksasa (*large payload*) membekukan seluruh pemrosesan server Redis. Seluruh klien lain mengalami *timeout*.
*   **Out-Of-Memory (OOM) Termination**: Manajemen alokasi memori yang keliru memicu Linux OOM Killer untuk mematikan proses Redis secara paksa (`SIGKILL`), mengakibatkan *downtime* total dan hilangnya data yang belum sempat dipersistensikan.
*   **Latensi Ekor (*Tail Latency Spikes*)**: Fragmentasi memori atau konfigurasi *fork-based snapshotting* (RDB) yang salah pada alokasi RAM masif menyebabkan lonjakan $p99$ latensi hingga hitungan detik.

---

### 4. What Problem It Solves
Tabel perbandingan antara arsitektur multithreaded tradisional berbasis *disk/locking* dengan arsitektur *single-threaded in-memory* Redis:

| Karakteristik | Basis Data Tradisional (RDBMS/Disk Cache) | Redis In-Memory Engine |
| :--- | :--- | :--- |
| **Media Utama** | Disk (NVMe/SSD/HDD) dengan *buffer pool* | RAM (DRAM) dengan persistensi opsional (AOF/RDB) |
| **Model Konkurensi** | Multi-threaded / Multi-process per koneksi | Single-threaded Event Loop (I/O Threading di v6.0+) |
| **Mekanisme Kunci Data**| Pessimistic/Optimistic Lock, Table/Row-level Locks | Serial execution (Atomic by default tanpa mutex) |
| **Overhead I/O Jaringan** | Context switching thread masif, stack allocation besar | Non-blocking socket polling via OS event notification |
| **Latensi Tipikal** | 5 ms – 50 ms | 100 µs – 1 ms |
| **Throughput Single Node**| 5.000 – 20.000 ops/sec | 100.000 – 1.000.000 ops/sec |

---

### 5. How It Works
Internal Redis bekerja melalui siklus terpadu yang berpusat pada pustaka abstraksi *event* bernama `ae.c` (*A simple event-driven library*).

```
[Linux Kernel Network Stack]
       │  (epoll_wait / kqueue)
       ▼
[aeProcessEvents] ◄────────────── SIKLUS EVENT LOOP
       │
       ├─► [File Events] (Socket I/O)
       │         │
       │         ├── 1. Accept incoming client connection
       │         ├── 2. Read socket buffer -> parse RESP protocol
       │         ├── 3. Execute command handler (LUT hash table)
       │         └── 4. Write result to client output buffer
       │
       └─► [Time Events] (Internal Timers)
                 │
                 └── serverCron() -> Purge expired keys, resize hash table, software watchdog
```

#### Alur Eksekusi Internal
1.  **Event Registration**: Saat inisialisasi, Redis membuat *event loop* (`aeCreateEventLoop`) dan mendaftarkan *file descriptor* (FD) milik socket listening server ke subsistem `epoll` menggunakan flag `EPOLLIN`.
2.  **Event Polling**: `aeProcessEvents` memanggil `epoll_wait()`. Thread utama tertidur (*sleep*) di tingkat kernel hingga ada FD yang siap menerima aksi baca (*read ready*) atau tulis (*write ready*).
3.  **Parsing Protokol (RESP)**: Ketika data masuk dari klien, callback membaca paket jaringan ke dalam *query buffer*. Parser mengubah format teks *REdis Serialization Protocol* (RESP) menjadi larik objek `robj`.
4.  **Eksekusi Perintah**: Redis mencari fungsi perintah pada tabel *command table* (misal: `SET` memetakan ke fungsi `setCommand`). Eksekusi fungsi langsung memodifikasi *global keyspace* (tipe data `dict`). Seluruh operasi pada titik ini bersifat atomik murni terhadap perintah lain.
5.  **Penyangga Keluaran (*Output Buffer*)**: Hasil komputasi diformat ke RESP dan dimasukkan ke dalam *client output buffer*. Handler mendaftarkan event `EPOLLOUT` pada FD terkait.
6.  **I/O Threading (Redis 6.0+)**: Untuk memecahkan *bottleneck* siklus CPU pada enkripsi/dekripsi jaringan dan parsing protokol, Redis 6+ memperkenalkan *I/O threads*. I/O Thread bertugas memparalelkan pembacaan soket, parsing protokol RESP, dan penulisan output buffer ke soket. **Perhatikan:** Eksekusi logika perintah tetap berjalan secara deterministik pada *single main thread*.

#### Representasi Memori: Simple Dynamic String (SDS) & redisObject
Redis tidak menggunakan string standar bahasa C (`char*` dengan terminasi `\0`). String internal dibungkus dalam SDS (`sds.h`):

```c
struct __attribute__ ((__packed__)) sdshdr8 {
    uint8_t len;         /* Jumlah byte terpakai */
    uint8_t alloc;       /* Jumlah byte teralokasi (tanpa header dan null-byte) */
    unsigned char flags; /* Tipe SDS (5-bit: SDS_TYPE_5, SDS_TYPE_8, dst.) */
    char buf[];          /* Raw byte array */
};
```
*   **O(1) Length Lookup**: Panjang string diketahui seketika tanpa perlu transversal $O(N)$ via `strlen()`.
*   **Binary Safe**: Dapat menyimpan sembarang representasi biner (gambar terkompresi, Protobuf, dsb.) karena tidak bergantung pada karakter `\0` untuk menentukan akhir string.
*   **Buffer Overflow Prevention**: Alokasi SDS secara otomatis melakukan kalkulasi kapasitas sebelum melakukan konkatenasi.

Setiap nilai dalam Redis kemudian dibungkus dalam abstraksi `redisObject` (`server.h`):
```c
typedef struct redisObject {
    unsigned type:4;       /* Tipe data: OBJ_STRING, OBJ_LIST, OBJ_HASH, dll */
    unsigned encoding:4;   /* Representasi internal: OBJ_ENCODING_RAW, OBJ_ENCODING_EMBSTR, dll */
    unsigned lru:24;       /* Informasi LRU / LFU untuk algoritma eviction */
    int refcount;          /* Penghitung referensi memori */
    void *ptr;             /* Penunjuk ke data aktual */
} robj;
```

---

### 6. Architectural Diagram

```
+-------------------------------------------------------------------------------+
|                             LINUX OPERATING SYSTEM                            |
|                                                                               |
|  +-----------------------+     +-----------------------+                      |
|  | Socket FD #1 (Client) |     | Socket FD #2 (Client) |  ... (10k+ Sockets)  |
|  +-----------------------+     +-----------------------+                      |
|              │                             │                                  |
|              ▼                             ▼                                  |
|     +───────────────────────────────────────────────────────────+             |
|     │             KERNEL I/O SUBSYSTEM: epoll_wait()            │             |
|     +───────────────────────────────────────────────────────────+             |
+-----------------------------------│-------------------------------------------+
                                    │ Multiplexed Events Ready
                                    ▼
+-------------------------------------------------------------------------------+
|                             REDIS SERVER PROCESS                              |
|                                                                               |
|   +───────────────────────────────────────────────────────────────────────+   |
|   │               MAIN THREAD (aeMain Engine Loop: ae.c)                  │   |
|   │                                                                       │   |
|   │  1. Dispatch File Events ──────────────────────────────────────────┐  │   |
|   │                                                                    │  │   |
|   │  2. COMMAND EXECUTION ENGINE (Strictly Single-Threaded)            │  │   |
|   │     ┌────────────────────────────────────────────────────────┐     │  │   |
|   │     │ - Lookup Command Table -> "SET", "HGET", "ZADD"        │     │  │   |
|   │     │ - Direct Mutation on Memory Structures                 │◄────┘  │   |
|   │     └────────────────────────┬───────────────────────────────┘        │   |
|   │                              │                                        │   |
|   │  3. Time Events Processing   ▼                                        │   |
|   │     ┌────────────────────────────────────────────────────────┐        │   |
|   │     │ serverCron() Execution (Eviction, Expire Sweep)        │        │   |
|   │     └────────────────────────────────────────────────────────┘        │   |
|   +──────────────────────────────┬────────────────────────────────────────+   |
|                                  │ Read/Write Offloading                      |
|                                  ▼                                            |
|   +───────────────────────────────────────────────────────────────────────+   |
|   │               OPTIONAL I/O THREADS (Redis 6.0+)                       │   |
|   │   [Thread 1: Parse RESP] [Thread 2: Write Socket] [Thread N: ...]     │   |
|   +──────────────────────────────┬────────────────────────────────────────+   |
|                                  │                                            |
|                                  ▼ Pointer Dereference                        |
|   +───────────────────────────────────────────────────────────────────────+   |
|   │                      IN-MEMORY STORAGE ENGINE                         │   |
|   │                                                                       │   |
|   │   GLOBAL KEYSPACE (dict.c) ──► Keys (SDS) ──► Values (redisObject)    │   |
|   │                                                  │                    │   |
|   │                     ┌────────────────────────────┴─────────────┐      │   |
|   │                     ▼                                          ▼      │   |
|   │          [EMBSTR / RAW SDS]                           [ZIPLIST / LISTPACK]│
|   │                                                                       │   |
|   │   MEMORY ALLOCATOR LAYER: jemalloc / libc malloc                      │   |
|   +───────────────────────────────────────────────────────────────────────+   |
+-------------------------------------------------------------------------------+
```

---

### 7. Minimal Working Example (Raw RESP Protocol via Netcat)
Untuk memahami bagaimana Redis memproses *command* tanpa abstraksi pustaka pihak ketiga, kita dapat berinteraksi langsung menggunakan protokol RESP level rendah melalui `nc` (Netcat).

Jalankan perintah berikut pada terminal:

```bash
# Buka koneksi TCP langsung ke instans Redis lokal
nc 127.0.0.1 6379
```

Kirim paket RESP murni berikut secara manual (tekan Enter untuk setiap baris):

```text
*3
$3
SET
$9
infra_key
$12
system_ready
```

**Penjelasan Format RESP (Serialization Parsing):**
*   `*3`: Menandakan array yang terdiri dari 3 elemen.
*   `$3`: Menandakan panjang bulk string berikutnya adalah 3 byte.
*   `SET`: Nilai string perintah.
*   `$9`: Panjang bulk string berikutnya (9 byte).
*   `infra_key`: Nama key.
*   `$12`: Panjang bulk string berikutnya (12 byte).
*   `system_ready`: Nilai string yang disimpan.

Respons dari server Redis:
```text
+OK
```
*   `+OK`: Simbol `+` menandakan tipe data *Simple String* yang dikembalikan oleh event loop Redis.

Ambil data tersebut menggunakan raw RESP:
```text
*2
$3
GET
$9
infra_key
```

Respons dari server Redis:
```text
$12
system_ready
```
*   `$12`: Bulk string dengan panjang 12 byte, diikuti oleh payload murni.

---

### 8. Real-World Production Implementation (Go Client Engine)
Implementasi koneksi Redis performa tinggi pada aplikasi backend Go, menerapkan *connection pooling*, pengaturan *timeout* defensif, *exponential backoff retry*, dan verifikasi status koneksi secara terisolasi.

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"time"

	"github.com/redis/go-redis/v9"
)

type RedisEngine struct {
	client *redis.Client
}

type Config struct {
	Host         string
	Port         int
	Password     string
	DB           int
	PoolSize     int
	MinIdleConns int
}

func NewRedisEngine(ctx context.Context, cfg Config) (*RedisEngine, error) {
	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)

	rdb := redis.NewClient(&redis.Options{
		Addr:         addr,
		Password:     cfg.Password,
		DB:           cfg.DB,
		PoolSize:     cfg.PoolSize,
		MinIdleConns: cfg.MinIdleConns,
		
		// Konfigurasi batas waktu I/O jaringan
		DialTimeout:  2 * time.Second,
		ReadTimeout:  500 * time.Millisecond,
		WriteTimeout: 500 * time.Millisecond,
		PoolTimeout:  1 * time.Second,

		// Penanganan retry otomatis untuk transient network failures
		MaxRetries:      3,
		MinRetryBackoff: 10 * time.Millisecond,
		MaxRetryBackoff: 100 * time.Millisecond,

		// Custom dialer untuk setting parameter kernel TCP
		Dialer: func(ctx context.Context, network, addr string) (net.Conn, error) {
			netDialer := &net.Dialer{
				Timeout:   2 * time.Second,
				KeepAlive: 30 * time.Second,
			}
			conn, err := netDialer.DialContext(ctx, network, addr)
			if err != nil {
				return nil, err
			}
			// Pastikan algoritma Nagle dimatikan (TCP_NODELAY = true)
			if tcpConn, ok := conn.(*net.TCPConn); ok {
				_ = tcpConn.SetNoDelay(true)
			}
			return conn, nil
		},
	})

	// Validasi koneksi awal (liveness check)
	pingCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()

	if err := rdb.Ping(pingCtx).Err(); err != nil {
		_ = rdb.Close()
		return nil, fmt.Errorf("redis liveness check failed on %s: %w", addr, err)
	}

	return &RedisEngine{client: rdb}, nil
}

func (re *RedisEngine) SetWithTTL(ctx context.Context, key string, value []byte, ttl time.Duration) error {
	if key == "" {
		return errors.New("key cannot be empty")
	}

	// Memastikan context memiliki batas waktu eksekusi
	execCtx, cancel := context.WithTimeout(ctx, 600*time.Millisecond)
	defer cancel()

	err := re.client.Set(execCtx, key, value, ttl).Err()
	if err != nil {
		return fmt.Errorf("failed to execute SET for key %s: %w", key, err)
	}
	return nil
}

func (re *RedisEngine) Get(ctx context.Context, key string) ([]byte, error) {
	if key == "" {
		return nil, errors.New("key cannot be empty")
	}

	execCtx, cancel := context.WithTimeout(ctx, 600*time.Millisecond)
	defer cancel()

	val, err := re.client.Get(execCtx, key).Bytes()
	if err != nil {
		if errors.Is(err, redis.Nil) {
			return nil, nil // Cache miss, bukan kegagalan sistem
		}
		return nil, fmt.Errorf("failed to execute GET for key %s: %w", key, err)
	}
	return val, nil
}

func (re *RedisEngine) Close() error {
	return re.client.Close()
}

func main() {
	ctx := context.Background()

	cfg := Config{
		Host:         "127.0.0.1",
		Port:         6379,
		Password:     "", // Masukkan auth jika diaktifkan
		DB:           0,
		PoolSize:     50,
		MinIdleConns: 10,
	}

	engine, err := NewRedisEngine(ctx, cfg)
	if err != nil {
		log.Fatalf("Fatal init: %v", err)
	}
	defer func() {
		if err := engine.Close(); err != nil {
			log.Printf("Error closing engine: %v", err)
		}
	}()

	key := "session:token:usr_9981"
	payload := []byte(`{"user_id": 9981, "role": "admin"}`)

	// Set data dengan TTL 60 detik
	if err := engine.SetWithTTL(ctx, key, payload, 60*time.Second); err != nil {
		log.Fatalf("Write error: %v", err)
	}
	fmt.Printf("State: Key %s berhasil ditulis\n", key)

	// Baca kembali data
	data, err := engine.Get(ctx, key)
	if err != nil {
		log.Fatalf("Read error: %v", err)
	}

	if data != nil {
		fmt.Printf("State: Data ditemukan -> %s\n", string(data))
	} else {
		fmt.Println("State: Key tidak ditemukan (Cache Miss)")
	}
	os.Exit(0)
}
```

---

### 9. Implementation Details & Edge Cases
1.  **Memory Allocator Overhead (jemalloc)**: Redis mengalokasikan memori dalam blok pangkat dua atau *fixed bins*. Jika Anda menyimpan string sebesar 33 byte, `jemalloc` mungkin mengalokasikan slot berukuran 48 atau 64 byte. Fenomena ini disebut *internal fragmentation*.
2.  **String Encoding Optimization (`embstr` vs `raw`)**:
    *   Jika panjang nilai string SDS $\le 44$ byte, Redis menggunakan representasi `OBJ_ENCODING_EMBSTR`. Memori untuk header `redisObject` dan struktur `SDS` dialokasikan sekaligus dalam **satu blok kontinu memori tunggal** (`malloc(sizeof(robj) + sizeof(sdshdr8) + len + 1)`). Ini meminimalkan alokasi heap dan memaksimalkan *CPU L1/L2 cache locality*.
    *   Jika string $> 44$ byte, encoding berubah menjadi `OBJ_ENCODING_RAW`, yang membutuhkan dua kali panggilan alokasi memori terpisah (satu untuk `redisObject`, satu untuk `SDS`).
3.  **Kernel Overcommit Memory**: Pada Linux, jika `sysctl vm.overcommit_memory = 0`, pemanggilan `fork()` untuk proses *snapshotting* RDB atau *AOF rewrite* dapat gagal dengan status *Out-of-Memory* meskipun kapasitas RAM fisik masih mencukupi. Hal ini terjadi karena OS mengasumsikan *worst-case scenario* bahwa child process menduplikasi 100% *page table* induk secara langsung. Nilai ini **wajib** diatur ke `1` di tingkat kernel.
4.  **Epoll Event Starvation**: Jika klien mengirim pipeline masif berisi 100.000 command dalam satu paket, thread tunggal Redis akan terus membaca soket tersebut hingga batas tertentu, berpotensi menunda pemrosesan soket klien lain jika ukuran buffer pembacaan tidak dibatasi secara adil.

---

### 10. Anti-Patterns & Common Pitfalls

#### Anti-Pattern 1: Menggunakan Perintah $O(N)$ pada Global Keyspace
```bash
# BURUK (FATAL DI PRODUKSI): 
# Memindai seluruh keyspace secara sinkron.
# Menahan event loop selama puluhan detik pada database dengan jutaan key.
KEYS user:*
```
```bash
# BAIK:
# Menggunakan kursor non-blocking inkremental.
# Mengembalikan chunk data secara iteratif tanpa membekukan event loop.
SCAN 0 MATCH user:* COUNT 100
```

#### Anti-Pattern 2: Large Keys / Bloated Payloads
Menyimpan satu key JSON atau hash set berukuran $> 10 \text{ MB}$.
*   **Dampak Buruk**: Ketika key ini diambil (`GET`), soket output buffer mengalami pembengkakan masif, mendominasi bandwidth kartu jaringan, dan memblokir thread tunggal selama proses serialisasi/deserialisasi memori.
*   **Perbaikan**: Kompresi data dengan zstandard/snappy di sisi aplikasi, atau pecah struktur objek menjadi beberapa sub-key.

#### Anti-Pattern 3: Menjalankan Perintah `FLUSHALL` / `FLUSHDB` Sinkron
```bash
# BURUK:
# Menghapus seluruh keyspace pada thread utama secara sinkron.
FLUSHALL
```
```bash
# BAIK:
# Mendelegasikan pembebasan memori ke background thread (Bio Thread).
FLUSHALL ASYNC
```

---

### 11. Performance Characteristics & Benchmarks
Kompleksitas waktu untuk perintah-perintah fundamental Redis:
*   `GET` / `SET`: $O(1)$
*   `DEL` (Single Key): $O(1)$ jika key bertipe skalar; $O(M)$ jika key bertipe koleksi dengan $M$ elemen.
*   `SCAN`: $O(1)$ per iterasi panggilan, $O(N)$ untuk transversal penuh.

#### Standar Metrik Latensi (Peralatan Bare-Metal / High-End Cloud C6i Instance)
*   **Throughput (Single Threaded Execution)**: $100.000 \text{ ops/sec} - 150.000 \text{ ops/sec}$.
*   **Throughput (I/O Threads enabled, Redis 6.0+)**: $300.000 \text{ ops/sec} - 500.000 \text{ ops/sec}$.
*   **$p50$ Latency**: $\approx 250 \ \mu\text{s}$.
*   **$p99$ Latency**: $< 1{,}2 \text{ ms}$.

Uji performa bawaan menggunakan `redis-benchmark`:
```bash
redis-benchmark -h 127.0.0.1 -p 6379 -c 50 -n 100000 -t set,get -q -P 16
```
Parameter:
*   `-c 50`: 50 koneksi konkuren secara paralel.
*   `-n 100000`: Total akumulasi 100.000 request.
*   `-q`: Mode quiet (hanya menampilkan data throughput).
*   `-P 16`: Melakukan *pipelining* 16 request per putaran I/O jaringan.

---

### 12. Security Considerations
1.  **Proteksi Bind Interface**: Secara default, Redis mendengarkan koneksi pada loopback interface (`127.0.0.1`). Menyetel parameter `bind 0.0.0.0` pada instans yang terekspos langsung ke internet tanpa konfigurasi firewall akan menyebabkan pengambilalihan sistem (*Remote Code Execution* melalui injeksi file SSH key atau cron job via perintah `CONFIG SET dir`).
2.  **Access Control List (ACL)**: Hindari penggunaan password global tunggal. Terapkan konfigurasi *least privilege* berbasis ACL (`redis.conf`):
    ```text
    user app_service on >ComplexSecretPasswd123! ~app:* +@read +@write -@admin -@dangerous
    ```
3.  **Command Disabling/Renaming**: Matikan akses ke fungsi-fungsi destruktif atau yang bersifat mengekspos lingkungan internal server:
    ```text
    rename-command FLUSHDB ""
    rename-command FLUSHALL ""
    rename-command CONFIG ""
    rename-command DEBUG ""
    ```
4.  **Enkripsi Transit (TLS Termination)**: Redis mendukung enkripsi native TLS sejak versi 6.0. Mengaktifkan TLS mencegah penyadapan data teks terbuka protokol RESP di segmen jaringan lokal (*man-in-the-middle attack*):
    ```text
    tls-port 6379
    port 0
    tls-cert-file /etc/redis/tls/redis.crt
    tls-key-file /etc/redis/tls/redis.key
    tls-ca-cert-file /etc/redis/tls/ca.crt
    ```

---

### 13. Observability, Metrics & Telemetry
Metrik kunci yang wajib dipantau secara kontinu menggunakan Prometheus `redis_exporter`:

| Metrik Prometheus / Redis INFO | Threshold Peringatan (Warning) | Tindakan Korektif |
| :--- | :--- | :--- |
| `instantaneous_ops_per_sec` | Penurunan tiba-tiba $> 50\%$ | Periksa saturasi CPU atau kemungkinan *blocking command*. |
| `mem_fragmentation_ratio` | $> 1.5$ atau $< 1.0$ | Jika $> 1.5$, aktifkan `activedefrag yes`. Jika $< 1.0$, swap aktif (bahaya). |
| `blocked_clients` | $> 10$ | Identifikasi client yang menggunakan operasi `BLPOP`/`BRPOP` terblokir. |
| `rejected_connections` | $> 0$ | Tingkatkan parameter `maxclients` dan `somaxconn` sistem operasi. |
| `used_memory` mendekati `maxmemory`| $> 85\%$ kapasitas terkonfigurasi | Naikkan kapasitas RAM, evaluasi TTL, atau ubah *eviction policy*. |

#### Triage Langsung Menggunakan CLI
1.  **Memantau Perintah Lambat**:
    ```bash
    # Ambil 10 perintah terakhir yang dieksekusi melebihi ambang batas slowlog
    SLOWLOG GET 10
    ```
2.  **Mendeteksi Lonjakan Latensi Eksternal/Internal**:
    ```bash
    # Analisis statistik internal terhadap sumber spike latensi
    LATENCY DOCTOR
    ```

---

### 14. Failure Modes & Resilience
1.  **Linux Kernel OOM Killer**:
    *   *Skenario*: Penggunaan memori Redis melampaui alokasi fisik tanpa batas `maxmemory`. Kernel mengirim `SIGKILL`.
    *   *Mitigasi*: Set batas tegas pada `redis.conf`:
        ```text
        maxmemory 4gb
        maxmemory-policy volatile-lru
        ```
2.  **Output Buffer Saturation (`OOM command not allowed`)**:
    *   *Skenario*: Sebuah klien lambat meminta transfer dataset masif. Penyangga data keluar di RAM terus membengkak hingga menyentuh batas `maxmemory`.
    *   *Mitigasi*: Konfigurasi limit proteksi buffer pada klien normal:
        ```text
        client-output-buffer-limit normal 10mb 5mb 60
        ```
3.  **Thundering Herd / Cache Stampede**:
    *   *Skenario*: Sebuah key bernilai tinggi (*hot key*) kedaluwarsa secara mendadak. Ratusan *thread* aplikasi secara simultan membaca nilai `nil` dari Redis dan membanjiri database SQL utama.
    *   *Mitigasi*: Terapkan *probabilistic early expiration* (algoritma XFetch) atau gunakan mekanisme *distributed lock* berdurasi pendek saat melakukan kalkulasi ulang cache.

---

### 15. Trade-offs & Alternatives

| Kriteria | Redis | Memcached | KeyDB | Dragonfly |
| :--- | :--- | :--- | :--- | :--- |
| **Model Threading** | Single-threaded core + Multi-threaded I/O | Multi-threaded murni | Multi-threaded (fork of Redis) | Multi-threaded (Shared-nothing architecture) |
| **Struktur Data** | Kaya (List, Set, Hash, ZSet, Stream, Bitmap) | Key-Value murni (Bytes only) | Mirip Redis (Identik) | Mirip Redis (Mendukung subset besar) |
| **Dukungan Persistensi**| RDB (Snapshot) & AOF (Append-only log) | Tidak ada (In-memory transient murni)| RDB & AOF | RDB & Snapshot |
| **Model Clustering** | Native Redis Cluster (Hash Slots) | Client-side consistent hashing | Native Redis Cluster | Native Redis Cluster kompatibel |
| **Kelebihan Utama** | Ekosistem sangat matang, prediktabilitas eksekusi tinggi | Overhead per-key sangat kecil, simpel | Utilisasi muti-core tanpa setup cluster | Throughput masif pada mesin komputasi besar (64+ Core)|
| **Kekurangan Utama** | Bottleneck skalar CPU tunggal jika salah konfigurasi | Fitur fungsional manipulasi data terbatas | Komunitas lebih kecil dibanding Redis | Kompatibilitas perintah tertentu belum 100% |

---

### 16. Migration / Integration Strategy
Pola integrasi standar industri untuk mengadopsi Redis adalah arsitektur **Cache-Aside (Lazy Loading)** dengan perlindungan sistematis:

```
[Aplikasi Klien] 
      │
      ├── (1) GET Key ──────────────────────────► [Redis Engine]
      │                                                │
      ├─◄── (2) Data Ditemukan (Cache Hit) ────────────┘
      │
      ├─ (Jika Cache Miss)
      │     │
      │     ├── (3) Query Data Asli ────────────► [Database Relasional/SQL]
      │     │                                          │
      │     ├─◄ (4) Return ResultSet ─────────────────┘
      │     │
      │     └── (5) SET Key dengan Jittered TTL ─► [Redis Engine]
      ▼
```

#### Pencegahan Cache Avalanche Melalui Expire Jittering
Jangan pernah menetapkan nilai kedaluwarsa absolut statis pada kumpulan key yang digenerasi secara berdekatan. Tambahkan variansi acak (*jitter*):
$$\text{ActualTTL} = \text{BaseTTL} + \text{UniformRandom}(0, \text{JitterRange})$$

Contoh kode:
```go
// Menghindari seluruh session expired pada detik yang sama
baseTTL := 3600 * time.Second
jitter := time.Duration(rand.Intn(300)) * time.Second
finalTTL := baseTTL + jitter
```

---

### 17. Verification & Testing Strategies
Verifikasi ketahanan aplikasi terhadap kegagalan Redis di level integrasi testing menggunakan Testcontainers.

Contoh implementasi pengujian Go menggunakan kontainer Redis riil:

```go
package main

import (
	"context"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func TestRedisIntegration_SetGet(t *testing.T) {
	ctx := context.Background()

	// Inisialisasi kontainer Redis riil secara dinamis
	req := testcontainers.ContainerRequest{
		Image:        "redis:7.2-alpine",
		ExposedPorts: []string{"6379/tcp"},
		WaitingFor:   wait.ForLog("Ready to accept connections tcp"),
	}

	redisC, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: req,
		Started:          true,
	})
	if err != nil {
		t.Fatalf("Gagal menjalankan Redis container: %v", err)
	}
	defer func() {
		if err := redisC.Terminate(ctx); err != nil {
			t.Fatalf("Gagal mematikan container: %v", err)
		}
	}()

	endpoint, err := redisC.Endpoint(ctx, "")
	if err != nil {
		t.Fatalf("Gagal mengambil endpoint container: %v", err)
	}

	// Eksekusi skenario uji
	rdb := redis.NewClient(&redis.Options{Addr: endpoint})
	defer rdb.Close()

	testKey := "test:health"
	testVal := "cluster_ok"

	err = rdb.Set(ctx, testKey, testVal, 5*time.Second).Err()
	if err != nil {
		t.Fatalf("Set gagal: %v", err)
	}

	got, err := rdb.Get(ctx, testKey).Result()
	if err != nil {
		t.Fatalf("Get gagal: %v", err)
	}

	if got != testVal {
		t.Errorf("Ekspektasi %s, mendapatkan %s", testVal, got)
	}
}
```

---

### 18. Operational Runbook

#### Prosedur 1: Mengatasi Fragmentasi Memori Tanpa Downtime
*Gejala*: `INFO memory` menunjukkan `mem_fragmentation_ratio > 1.6` dan alokasi memori fisik sistem menipis secara kritis.

1.  Periksa rasio fragmentasi saat ini:
    ```bash
    redis-cli INFO memory | grep -E "mem_fragmentation_ratio|used_memory_human|used_memory_rss_human"
    ```
2.  Aktifkan defragmentasi aktif secara dinamis:
    ```bash
    redis-cli CONFIG SET activedefrag yes
    ```
3.  Konfigurasikan beban defragmentasi CPU agar tidak mengganggu operasional:
    ```bash
    redis-cli CONFIG SET active-defrag-cycle-min 10
    redis-cli CONFIG SET active-defrag-cycle-max 25
    ```
4.  Monitor proses hingga rasio turun kembali ke $\approx 1{,}1 - 1{,}2$, lalu nonaktifkan kembali bila diperlukan:
    ```bash
    redis-cli CONFIG SET activedefrag no
    ```

#### Prosedur 2: Triage Insiden Latensi Tinggi (Spike $p99$)
*Gejala*: Klien melaporkan rentetan error `Command timed out after 500ms`.

1.  Cek apakah ada perintah lambat yang sedang mengeksekusi saat ini:
    ```bash
    redis-cli SLOWLOG GET 5
    ```
2.  Cek daftar koneksi yang memonopoli komputasi atau memakan memori input/output raksasa:
    ```bash
    redis-cli CLIENT LIST | tr ' ' '\n' | grep -E "cmd=|obl=|qbuf=|name="
    ```
3.  Terminasi koneksi klien anomali secara manual:
    ```bash
    redis-cli CLIENT KILL ID <client-id>
    ```

---

### 19. Best Practices Checklist

#### Konfigurasi Infrastruktur & Desain Sistem
* [ ] Parameter kernel `vm.overcommit_memory` diatur ke nilai `1` pada `/etc/sysctl.conf`.
* [ ] Parameter `net.core.somaxconn` dinaikkan ke minimal `2048` (default kernel `128` terlalu kecil).
* [ ] Fitur Linux *Transparent Huge Pages* (THP) dimatikan (`echo never > /sys/kernel/mm/transparent_hugepage/enabled`). Jika aktif, THP memicu latensi ekor masif saat alokasi copy-on-write RDB snapshot.
* [ ] Parameter `maxmemory` selalu ditentukan dengan batas aman (misal: 75% dari total memori fisik host).
* [ ] Memilih `maxmemory-policy` yang sesuai dengan domain data (rekomendasi: `volatile-lru` untuk mixed storage, atau `allkeys-lru` untuk dedicated cache).

#### Penulisan Kode Aplikasi (Development)
* [ ] Tidak pernah mengeksekusi `KEYS *` pada kode produksi; selalu gunakan `SCAN` inkremental.
* [ ] Seluruh key memiliki batas kedaluwarsa (TTL) eksplisit untuk mencegah akumulasi memori liar (*memory leaks*).
* [ ] Mengaktifkan *TCP Keepalive* pada driver klien untuk mendeteksi pemutusan koneksi secara dini.
* [ ] Selalu membungkus operasi berantai dalam *Pipelines* untuk mengurangi *round-trip time* (RTT) jaringan.

#### Operasional Produksi
* [ ] Perintah administratif berbahaya (`FLUSHALL`, `CONFIG`) telah di-rename atau di-disable lewat konfigurasi.
* [ ] Slowlog diatur pada batas sensitif (misal: `slowlog-log-slower-than 10000` mikrosidetik / 10 ms).
* [ ] Otomasi backup RDB/AOF disimpan secara reguler ke penyimpanan objek sekunder terisolasi (S3/GCS).

---

### 20. References & Deep Dive Reading
1.  **Redis Source Code Documentation**:
    *   `src/server.c`: Alur utama siklus hidup *event loop* dan inisialisasi server.
    *   `src/ae.c`: Implementasi arsitektur abstraksi *Reactor Pattern*.
    *   `src/sds.c`: Spesifikasi internal alokasi memori *Simple Dynamic Strings*.
2.  **Linux Kernel Networking Subsystem**:
    *   Manual Page: `epoll(7)` - *I/O event notification facility*.
    *   Manual Page: `sysctl/vm.txt` - *Overcommit Memory Handling Documentation*.
3.  **RFC & Spesifikasi Protokol**:
    *   Spesifikasi Internal Redis Serialization Protocol: [RESP2 and RESP3 Specifications](https://redis.io/docs/reference/protocol-spec/).
4.  **Whitepaper**:
    *   Sanfilippo, S. (Antirez). *Redis: The Design and Implementation of an In-Memory Engine*.
    *   Evans, J. (2006). *A Scalable Concurrent malloc(3) Implementation for FreeBSD (jemalloc mechanics)*.