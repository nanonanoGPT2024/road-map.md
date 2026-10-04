# BAB 07: Caching Strategy, Real-Time & Event-Driven Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda ditargetkan untuk mampu:
*   Mendiagnosis, merancang, dan mengimplementasikan arsitektur *multi-tier caching* (L1 In-Memory via Laravel Octane/APCu dan L2 Distributed via Redis Cluster) guna mengeliminasi latensi I/O database pada beban lalu lintas tinggi (*high-concurrency*).
*   Mencegah anomali performa kritis seperti *Cache Stampede* (*Thundering Herd*), *Cache Avalanche*, dan *Cache Penetration* menggunakan algoritma mutasi protektif (*Probabilistic Early Expiration* / *XFetch* dan *Atomic Distributed Locking*).
*   Membangun arsitektur *Real-Time Communication* berskala enterprise menggunakan **Laravel Reverb** terkluster, dioptimalkan dengan protokol WebSocket stateful, *horizontal scaling* melalui Redis Pub/Sub backplane, dan *kernel parameter tuning*.
*   Merancang sistem *Event-Driven Architecture* (EDA) berstandar industri dengan mengimplementasikan **Transactional Outbox Pattern** untuk menjamin konsistensi data *dual-write* antara database transaksional (RDBMS) dan *message broker* / *event streaming platform*.
*   Menerapkan mekanisme konsumsi pesan idempoten (*Idempotent Consumer Pattern*) dengan pelacakan *distributed tracing* (OpenTelemetry/W3C Trace Context) di seluruh *lifecycle* event, *queue*, dan *real-time broadcast*.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
*   **PHP 8.2/8.3 Core:** Memahami *memory management*, referensi sirkular, model eksekusi proses CLI vs FPM, dan generator.
*   **Laravel Core:** Siklus hidup *Request-to-Response*, Service Container bindings, Pipeline pattern, dan Event Dispatcher internal.
*   **Database & Storage:** Isolasi transaksi ACID (Read Committed vs Repeatable Read), Row-level locking (`SELECT ... FOR UPDATE`), dan protokol Redis (RESP, Redis Cluster slotting, Pub/Sub semantic).
*   **Networking & Concurrency:** Protokol TCP/IP, WebSockets handshake (RFC 6455), model *asynchronous non-blocking I/O* (Event Loop via `ext-pcntl`, `ext-ev`, atau ReactPHP/Swoole).

---

### 3. Concept & Internal Architecture

#### 3.1 Laravel Cache Subsystem Internals
Secara default, Laravel mengabstraksi caching melalui kontrak `Illuminate\Contracts\Cache\Repository` dan `Illuminate\Contracts\Cache\Store`.

```
+-----------------------------------------------------------------------+
|                       Application Layer (Code)                        |
|             Cache::remember() / Cache::tags()->remember()             |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                    Illuminate\Cache\Repository                        |
|   - Handles Events (CacheHit, CacheMissed, KeyWritten, KeyForgotten)  |
|   - Normalizes TTL (Carbon -> Seconds/Minutes)                        |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                     TaggedCache (Optional Decorator)                  |
|   - Reads/Generates Namespace Keys via Redis Set/Hashes               |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                       Driver Store (e.g., RedisStore)                 |
|   - Evaluates prefixing                                               |
|   - Connection pooling & Command execution (phpredis / predis)        |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
|                             Redis Server                              |
+-----------------------------------------------------------------------+
```

##### Tagging Mechanics & Danger
Ketika menggunakan `Cache::tags(['orders', 'customer:12'])->put('k', 'v')`:
1. Laravel men-generate kunci internal untuk setiap tag: `tag:orders:key` dan `tag:customer:12:key`.
2. Nilai hash acak (*tag identifier*) disimpan dalam string Redis.
3. Kunci akhir di-hash: `sha1('orders' . $id1 . 'customer:12' . $id2) . ':k'`.
4. *Flush* tag (`Cache::tags('orders')->flush()`) tidak menghapus semua kunci turunan secara langsung, melainkan meng-inkrementasi *tag identifier*. Kunci lama menjadi *orphaned* di memori Redis sampai diejeksi oleh mekanisme TTL atau Redis LRU/LFU policy. **Ini berpotensi menimbulkan *memory explosion* di Redis jika digunakan sembarangan tanpa TTL.**

#### 3.2 Cache Invalidation & Stampede Internal Architecture
*Cache Stampede* terjadi saat suatu kunci cache bernilai tinggi kedaluwarsa tepat saat ribuan *concurrent worker/request* mengaksesnya secara bersamaan. Alur normal runtuh ketika semua proses membaca *miss* secara serempak dan membebani database dengan kueri identik (*thundering herd*).

```
Normal Flow:
Client Request ---> [Cache: MISS] ---> [DB: Execute Query] ---> [Cache: PUT] ---> Response

Stampede Scenario (Concurrency = 5,000 req/sec):
T0: Key Expires!
T1: Client 1-5000 -> [Cache: MISS]
T2: Client 1-5000 -> [DB: 5,000 Heavy Concurrent Queries] -> Connection Exhaustion / DB Crash!
```

Solusi arsitektural:
1. **Mutex Lock (*Lock-Protected Cache Aside*):** Hanya satu proses yang mendapatkan izin kueri database; proses lain menunggu (*spin-lock*) atau membaca nilai *stale*.
2. **Probabilistic Early Expiration (Algoritma XFetch):** Proses komputasi ulang dijalankan di latar belakang sebelum kunci kedaluwarsa murni, dihitung berdasarkan latensi komputasi ($compute\_time \times \beta \times \ln(rand()))$.

#### 3.3 Laravel Reverb: Low-Level Event Loop & Pub/Sub
Laravel Reverb dibangun di atas fondasi non-blocking I/O (ReactPHP). Reverb tidak berjalan di bawah PHP-FPM, melainkan sebagai proses daemon mandiri (*single-threaded asynchronous event loop*).

```
                      +-----------------------------+
                      |       Clients (Browsers)    |
                      +-----------------------------+
                        |                         |
               WebSocket Conn 1           WebSocket Conn 2
                        |                         |
                        v                         v
       +----------------------------------------------------+
       |          Laravel Reverb Node 1 (Daemon)            |
       |  +-----------------------------------------------+ |
       |  | ReactPHP Event Loop (StreamSelect/Epoll)      | |
       |  | - Frame Decoder (RFC 6455)                    | |
       |  | - Pusher-compatible Protocol Parser           | |
       |  | - Connection State Storage (SplObjectStorage) | |
       |  +-----------------------------------------------+ |
       +----------------------------------------------------+
                        |                         ^
                  PUBLISH event              SUBSCRIBE
                        |                         |
                        v                         |
              +-----------------------------------------+
              |           Redis Pub/Sub Server          |
              |       Channel: reverb:app_id:*          |
              +-----------------------------------------+
                        ^                         |
                  PUBLISH event              SUBSCRIBE
                        |                         |
                        v                         |
       +----------------------------------------------------+
       |          Laravel Reverb Node 2 (Daemon)            |
       |  +-----------------------------------------------+ |
       |  | ReactPHP Event Loop                           | |
       |  +-----------------------------------------------+ |
       +----------------------------------------------------+
```

*   **Epoll Engine:** Reverb mengelola ribuan koneksi persisten via *file descriptors* tanpa overhead context switching dari model satu-thread-per-koneksi.
*   **Horizontal Scale via Redis:** Ketika *Node 1* menerima event dari backend Laravel (via HTTP POST API `/apps/{app_id}/events`), Node 1 mem-publish payload ke Redis channel. *Node 2* yang meng-subscribe channel tersebut menerima payload dan membroadcastnya ke koneksi WebSocket yang tersambung padanya.

#### 3.4 Transactional Outbox Architecture
Mengirim event langsung ke message broker/broadcaster di dalam transaksi database adalah antipattern sistem terdistribusi (*Dual-Write Problem*).

```
ANTI-PATTERN:
DB::transaction(function () {
    $order->save();
    Event::dispatch(new OrderPlaced($order)); // Bencana: Redis/Broker mati -> Transaction Rollback,
                                              // atau DB Commit gagal -> Event terlanjur terkirim (Ghost Event)!
});

PRO-PATTERN (Transactional Outbox):
[HTTP Request]
       |
       v
[RDBMS Transaction Boundary] ---------------------------------------------+
| 1. INSERT INTO orders (...)                                            |
| 2. INSERT INTO outbox_messages (payload, status='PENDING', ...)        |
+------------------------------------------------------------------------+
       | (Atomically Committed)
       v
[Outbox Relay Engine (Queue Worker / Debezium CDC)]
       | (Pessimistic Row Lock: SELECT ... FOR UPDATE SKIP LOCKED)
       v
[Message Broker / Laravel Reverb / Redis Stream]
       |
       v
[Update outbox_messages SET status='PROCESSED']
```

---

### 4. Why & What

| Paradigma Lama (Monolit Sederhana) | Masalah di Skala Produksi | Solusi Enterprise (Modul Ini) |
| :--- | :--- | :--- |
| **Direct Cache-Aside** (`Cache::remember`) | *Thundering herd* menumbangkan DB saat lonjakan traffic tinggi (*flash-sale*). | **Atomic Mutex Locked Cache** atau **Probabilistic XFetch** invalidation. |
| **Redis Tagging Tanpa Kontrol** | Memory leak akibat akumulasi kunci *orphaned* di Redis cluster. | **Key Hash Namespacing** manual dengan prefix berbasis versi skema. |
| **In-Transaction Event Dispatching** | *Phantom reads*, hilangnya data saat broker *unreachable*, atau inkonsistensi event. | **Transactional Outbox Pattern** menjamin pengiriman pesan *at-least-once*. |
| **Third-Party Real-Time SaaS** | Biaya membengkak eksponensial seiring bertambahnya koneksi concurrent. | **Laravel Reverb Clustered Architecture** di atas infrastruktur mandiri. |
| **Queue Non-Idempoten** | Pemrosesan duplikat saat *network timeout*, *retry storms*, atau *worker crash*. | **Idempotency Deduplication Window** berbasis atomic distributed locks. |

---

### 5. How (Workflow Detail)

#### Implementasi Transactional Outbox & Invalidation Flow
1. **Client Request:** Klien mengirim mutasi data (misalnya `POST /api/v1/orders`).
2. **Begin ACID Transaction:**
   * Simpan data inti pada entitas bisnis (`orders`).
   * Serialisasikan event domain ke format payload JSON standar.
   * Masukkan payload ke tabel `outbox_messages` dengan status `PENDING`.
3. **Commit Transaction:** Data domain dan record outbox tersimpan secara absolut dalam unit kerja atomik.
4. **Asynchronous Outbox Dispatching Engine:**
   * Worker background mengambil batch pesan `PENDING` menggunakan kueri performa tinggi:
     `SELECT id, payload FROM outbox_messages WHERE status = 'PENDING' ORDER BY id ASC LIMIT 100 FOR UPDATE SKIP LOCKED;`
   * Kirim event ke Laravel Event System, Redis Stream, atau Reverb Broadcaster.
   * Update status outbox menjadi `PROCESSED` atau hapus record untuk menghemat storage (*soft prune*).
5. **Real-Time Delivery & Invalidation Pipeline:**
   * Konsumen membaca event: Menginvalidasi atau merefresh cache tier-1 (Octane) dan tier-2 (Redis).
   * Broadcaster memancarkan frame WebSocket terenkripsi ke subscriber channel terkait.

---

### 6. Analogy & Diagram ASCII

#### Analogi Multi-Tier Cache & Outbox
Bayangkan transaksi restoran bintang lima:
* **L1 Cache (Pelayan/Memory):** Pelayan mengingat menu favorit Anda di kepalanya (sangat cepat, 0 detik konfirmasi, tapi hilang jika pelayan ganti shift).
* **L2 Cache (Papan Menu Dinding/Redis):** Papan tulis bersama di dapur yang dapat dibaca semua koki dan pelayan.
* **Database (Buku Besar Keuangan/Postgres):** Lemari arsip terkunci tempat nota resmi disimpan.
* **Transactional Outbox (Buku Kasir Karbon Rangkap):** Kasir tidak boleh menelepon supplier sebelum nota dicap. Nota ditulis dalam 2 rangkap: satu untuk pembukuan, satu ditaruh di nampan "pesanan keluar". Pengantar barang mengambil nota dari nampan pesanan keluar satu per satu. Jika pengantar barang pingsan, nota tetap ada di nampan dan tidak hilang.

```
+---------------------------------------------------------------------------------------+
|                                    FLOW ARSITEKTUR LENGKAP                            |
+---------------------------------------------------------------------------------------+

[Client API] 
     │
     ▼
[Laravel Controller]
     │
     ├───► [L1: Octane In-Memory Cache] ──(HIT: < 1ms)──────► Return Response
     │
     ├───► [L2: Redis Cluster] ──────────(HIT: 2-5ms)───────► Hydrate L1 & Return
     │
     ▼ (MISS: Lock Mutex Required)
[Postgres Database Transaction]
     │
     ├── 1. INSERT INTO orders ...
     └── 2. INSERT INTO outbox_messages ...
     │
[Commit]
     │
     ├───────────────────────────────────────────────────────┐
     ▼                                                       ▼
[Outbox Relay Worker (Daemon)]             [Response 201 Created to Client]
     │
     ├── Lock & Pull 'FOR UPDATE SKIP LOCKED'
     ├── Dispatch to Reverb WebSocket Broadcaster ───► [Active WebSocket Clients]
     ├── Invalidate L2 Redis & L1 Octane
     └── UPDATE outbox_messages SET status = 'DELIVERED'
```

---

### 7. Code Implementation

Mari implementasikan arsitektur ini secara menyeluruh dengan PHP 8.3 standar industri.

#### 7.1 Multi-Tier Resilient Cache Manager (Mengatasi Stampede via Atomic Locks)

```php
<?php

declare(strict_types=1);

namespace App\Infrastructure\Cache;

use Closure;
use Illuminate\Contracts\Cache\Repository as CacheRepository;
use Illuminate\Support\Facades\Log;
use Throwable;

final readonly class ResilientCacheService
{
    public function __construct(
        private CacheRepository $cache,
    ) {}

    /**
     * Mengambil data dari cache dengan proteksi mutlak dari Cache Stampede
     * menggunakan Mutex Distributed Lock dan Fallback Stale Grace Period.
     *
     * @template T
     * @param string $key
     * @param int $ttlSeconds
     * @param Closure(): T $resolver
     * @param int $lockWaitTimeout Waktu tunggu antrean lock
     * @return T
     */
    public function rememberNonBlocking(
        string $key,
        int $ttlSeconds,
        Closure $resolver,
        int $lockWaitTimeout = 5
    ): mixed {
        $lockKey = "lock:{$key}";
        $data = $this->cache->get($key);

        if ($data !== null) {
            return $data;
        }

        // Akuisisi atomic distributed lock
        $lock = $this->cache->getStore()->lock($lockKey, $lockWaitTimeout);

        try {
            if ($lock->get()) {
                // Double-checked locking pattern pasca mendapatkan lock
                $data = $this->cache->get($key);
                if ($data !== null) {
                    return $data;
                }

                $freshData = $resolver();
                $this->cache->put($key, $freshData, $ttlSeconds);

                return $freshData;
            }

            // Jika lock gagal diperoleh dalam batas toleransi, tunggu sebentar lalu baca ulang
            return $this->spinWait($key, $lockWaitTimeout);
        } catch (Throwable $e) {
            Log::error("Cache stampede mitigation failure for key: {$key}", [
                'exception' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
            ]);

            // Fail-open: Langsung eksekusi resolver untuk melindungi SLA aplikasi
            return $resolver();
        } finally {
            $lock->release();
        }
    }

    private function spinWait(string $key, int $timeoutSeconds): mixed
    {
        $start = microtime(true);
        while ((microtime(true) - $start) < $timeoutSeconds) {
            usleep(100_000); // 100ms backoff
            $data = $this->cache->get($key);
            if ($data !== null) {
                return $data;
            }
        }

        throw new \RuntimeException("Timeout waiting for cache lock on key: {$key}");
    }
}
```

#### 7.2 Transactional Outbox Pattern Engine

##### Migration: Tabel Outbox
```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('outbox_messages', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->string('event_type')->index();
            $table->string('aggregate_type')->index();
            $table->string('aggregate_id')->index();
            $table->jsonb('payload');
            $table->jsonb('headers')->nullable();
            $table->enum('status', ['PENDING', 'PROCESSING', 'DELIVERED', 'FAILED'])->default('PENDING')->index();
            $table->integer('attempts')->default(0);
            $table->text('last_error')->nullable();
            $table->timestamp('created_at')->useCurrent()->index();
            $table->timestamp('processed_at')->nullable();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('outbox_messages');
    }
};
```

##### Model Outbox
```php
<?php

declare(strict_types=1);

namespace App\Domain\Outbox\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class OutboxMessage extends Model
{
    use HasUuids;

    public $timestamps = false;

    protected $table = 'outbox_messages';

    protected $fillable = [
        'id',
        'event_type',
        'aggregate_type',
        'aggregate_id',
        'payload',
        'headers',
        'status',
        'attempts',
        'last_error',
        'created_at',
        'processed_at',
    ];

    protected $casts = [
        'payload' => 'array',
        'headers' => 'array',
        'attempts' => 'integer',
        'created_at' => 'datetime',
        'processed_at' => 'datetime',
    ];
}
```

##### Service Eksekusi Transaksional
```php
<?php

declare(strict_types=1);

namespace App\Domain\Order\Services;

use App\Domain\Order\Models\Order;
use App\Domain\Outbox\Models\OutboxMessage;
use Illuminate\Database\DatabaseManager;
use Illuminate\Support\Str;
use Throwable;

final readonly class OrderCreationService
{
    public function __construct(
        private DatabaseManager $db,
    ) {}

    /**
     * @param array<string, mixed> $orderData
     * @throws Throwable
     */
    public function execute(array $orderData): Order
    {
        return $this->db->transaction(function () use ($orderData) {
            // 1. Simpan Domain Model
            $order = Order::create([
                'user_id' => $orderData['user_id'],
                'total_amount' => $orderData['total_amount'],
                'status' => 'PENDING',
            ]);

            // 2. Simpan ke Outbox dalam Transaksi Relasional yang Sama
            $eventPayload = [
                'order_id' => $order->id,
                'user_id' => $order->user_id,
                'total_amount' => $order->total_amount,
                'created_at' => $order->created_at->toISOString(),
            ];

            OutboxMessage::create([
                'id' => (string) Str::uuid(),
                'event_type' => 'OrderPlaced',
                'aggregate_type' => 'Order',
                'aggregate_id' => (string) $order->id,
                'payload' => $eventPayload,
                'headers' => [
                    'correlation_id' => (string) Str::uuid(),
                    'trace_parent' => request()->header('traceparent', 'direct'),
                ],
                'status' => 'PENDING',
                'created_at' => now(),
            ]);

            return $order;
        });
    }
}
```

##### Outbox Relay Daemon Worker (High-Throughput Lock Stripping)
```php
<?php

declare(strict_types=1);

namespace App\Infrastructure\Console\Commands;

use App\Domain\Outbox\Models\OutboxMessage;
use Illuminate\Console\Command;
use Illuminate\Contracts\Events\Dispatcher;
use Illuminate\Support\Facades\DB;
use Throwable;

final class ProcessOutboxMessagesCommand extends Command
{
    protected $signature = 'outbox:process {--batch-size=100} {--sleep=500000}';
    protected $description = 'Worker pemroses tabel Transactional Outbox dengan teknik pessimistic skip-locking';

    public function handle(Dispatcher $eventDispatcher): int
    {
        $batchSize = (int) $this->option('batch-size');
        $sleepMicroseconds = (int) $this->option('sleep');

        $this->info("Menjalankan Outbox Relay Worker...");

        while (true) {
            $processedCount = 0;

            DB::transaction(function () use ($batchSize, $eventDispatcher, &$processedCount) {
                // Pessimistic Locking dengan SKIP LOCKED: Memastikan horizontal-scaling aman jika worker jalan paralel
                $messages = OutboxMessage::query()
                    ->where('status', 'PENDING')
                    ->orderBy('created_at', 'asc')
                    ->limit($batchSize)
                    ->lockForUpdate()
                    ->skipLocked()
                    ->get();

                if ($messages->isEmpty()) {
                    return;
                }

                foreach ($messages as $message) {
                    try {
                        // Dynamically resolve event class
                        $eventClass = "App\\Domain\\Events\\{$message->event_type}";
                        
                        if (class_exists($eventClass)) {
                            $eventDispatcher->dispatch(new $eventClass($message->payload, $message->headers));
                        }

                        $message->update([
                            'status' => 'DELIVERED',
                            'processed_at' => now(),
                        ]);

                        $processedCount++;
                    } catch (Throwable $e) {
                        $message->increment('attempts');
                        $message->update([
                            'status' => $message->attempts >= 3 ? 'FAILED' : 'PENDING',
                            'last_error' => $e->getMessage(),
                        ]);
                    }
                }
            });

            if ($processedCount === 0) {
                usleep($sleepMicroseconds); // Sleep interval saat queue kosong
            }
        }

        return self::SUCCESS;
    }
}
```

#### 7.3 Real-Time Broadcasting via Clustered Laravel Reverb

##### Event Broadcasting Contract
```php
<?php

declare(strict_types=1);

namespace App\Domain\Events;

use Illuminate\Broadcasting\PrivateChannel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;

final readonly class OrderPlaced implements ShouldBroadcastNow
{
    /**
     * @param array<string, mixed> $payload
     * @param array<string, mixed> $headers
     */
    public function __construct(
        public array $payload,
        public array $headers = []
    ) {}

    public function broadcastOn(): array
    {
        return [
            new PrivateChannel("orders.{$this->payload['user_id']}"),
        ];
    }

    public function broadcastAs(): string
    {
        return 'order.created';
    }

    /**
     * @return array<string, mixed>
     */
    public function broadcastWith(): array
    {
        return [
            'order_id' => $this->payload['order_id'],
            'total_amount' => $this->payload['total_amount'],
            'timestamp' => $this->payload['created_at'],
        ];
    }
}
```

##### Konfigurasi Enterprise Reverb Cluster (`config/reverb.php`)
```php
<?php

return [
    'default' => 'reverb',

    'servers' => [
        'reverb' => [
            'host' => env('REVERB_SERVER_HOST', '0.0.0.0'),
            'port' => env('REVERB_SERVER_PORT', 8080),
            'hostname' => env('REVERB_HOST'),
            'options' => [
                'tls' => [],
            ],
            'max_request_size' => 10_000,
            'scaling' => [
                'enabled' => true,
                'channel' => 'reverb-cluster',
                'server' => [
                    'connection' => 'redis-reverb',
                ],
            ],
            'pulse_ingest_interval' => 15,
            'telescope_ingest_interval' => 15,
        ],
    ],

    'apps' => [
        'provider' => 'config',
        'apps' => [
            [
                'key' => env('REVERB_APP_KEY'),
                'secret' => env('REVERB_APP_SECRET'),
                'app_id' => env('REVERB_APP_ID'),
                'options' => [
                    'host' => env('REVERB_HOST'),
                    'port' => env('REVERB_PORT', 443),
                    'scheme' => env('REVERB_SCHEME', 'https'),
                    'useTLS' => env('REVERB_SCHEME', 'https') === 'https',
                ],
                'allowed_origins' => ['https://portal.enterprise.com'],
                'ping_interval' => 30,
                'max_message_size' => 10_000,
            ],
        ],
    ],
];
```

---

### 8. Real World Case Study: E-Commerce Flash Sale Architecture

#### Skenario Kasus
*   **Aplikasi:** E-Commerce Flash Sale Engine.
*   **Beban Puncak:** 65.000 Request/detik pada peluncuran varian gawai baru, dengan 40.000 koneksi WebSocket bersamaan yang memantau ketersediaan stok produk secara real-time.
*   **Masalah Lapangan Lama:**
    1. Database PostgreSQL kehabisan pool koneksi (`max_connections` reached) dalam 3 detik pertama akibat kueri katalog berulang.
    2. Redis mengalami *memory saturation* dan latency spikes hingga 1.2 detik karena tagging cache tidak memiliki kontrol TTL yang bersih.
    3. Server WebSocket berbasis library pihak ketiga non-cluster terputus massal saat traffic memuncak (*thundering herd reconnect*).

#### Solusi Arsitektur Terintegrasi
1.  **Dual-Tier Caching System:**
    *   **L1 (In-Memory Swoole/Octane Table):** TTL 2 detik untuk agregat metadata ketersediaan barang. Menahan 92% traffic langsung dari RAM aplikasi host tanpa menyentuh I/O jaringan Redis.
    *   **L2 (Redis 7 Cluster):** Read-Through dengan *Atomic Distributed Locking* untuk data spesifik katalog (TTL 10 menit).
2.  **Transactional Outbox Engine:**
    *   Setiap *checkout transaction* mencatat order dan status pemesanan ke tabel outbox Postgres.
    *   4 worker paralel menjalankan daemon `outbox:process` menggunakan `FOR UPDATE SKIP LOCKED`.
3.  **Horizontal Scale Real-time Reverb:**
    *   Tiga node Reverb diatur di belakang NGINX Load Balancer (Least Connection Algorithm) dengan Redis adapter untuk sinkronisasi state lintas node.
    *   Event broadcast dipancarkan hanya saat inventaris menipis melewati ambang batas 10%.

#### Hasil Metrik Pasca Implementasi
*   **P99 Latency:** Turun dari 2.800 ms ke **18 ms**.
*   **Database CPU Utilization:** Turun dari 98% ke **24%** di jam puncak flash sale.
*   **Zero Dropped Orders:** Tidak ada order yang hilang akibat inkonsistensi transaksi berkat isolasi outbox table.

---

### 9. Trade-offs

| Parameter | Pilihan A | Pilihan B | Trade-off Analisis |
| :--- | :--- | :--- | :--- |
| **Cache Mutation** | **Probabilistic Early Expiration (XFetch)** | **Atomic Mutex Lock** | XFetch menghindari locking contention sepenuhnya, namun membutuhkan komputasi probabilistik dan berisiko merefresh data saat resource sedang tinggi jika perhitungan deviasi waktu salah. Mutex Lock menjamin hanya satu yang memproses, tetapi thread lain harus memblokir/menunggu (*spin-lock*). |
| **Penyimpanan Outbox** | **RDBMS Table (Postgres/MySQL)** | **Kafka / RabbitMQ Direct Publish** | Menyimpan di tabel RDBMS menjamin mutlak ACID Transaksional (*zero phantom messages*), namun menambah beban *Write IOPS* pada database utama. Direct Publish lebih cepat, tetapi rentan terhadap ketidaksinkronan data jika DB commit berhasil namun koneksi jaringan ke broker putus. |
| **Real-time Server** | **Laravel Reverb (Self-Hosted Cluster)** | **Managed Pusher / Ably** | Reverb memotong biaya operasional hingga 80% pada volume jutaan pesan, namun menuntut tim internal untuk menguasai Linux socket tuning, load balancing, dan Redis synchronization cluster. |
| **Cache Invalidation** | **Cache Tagging (`Cache::tags`)** | **Explicit Explicit Hash Invalidation** | Tagging sangat fleksibel secara kode, tetapi memiliki overhead traversal performa besar di Redis (*memory footprint* masif). Explicit Hash membutuhkan manualisasi pelacakan dependensi relasi, tetapi sangat efisien secara I/O Redis. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Redis Serialization Overhead
*   **Gejala:** Latensi transfer data Redis tinggi dan penggunaan CPU tinggi pada thread Redis.
*   **Penyebab:** Laravel default menggunakan PHP `serialize()` dan `unserialize()` standar yang memproduksi payload string sangat besar dan lambat di-parse.
*   **Solusi:** Gunakan serializer native ekstensi C seperti `igbinary` atau `msgpack` pada `config/database.php`.
    ```php
    'redis' => [
        'client' => 'phpredis',
        'options' => [
            'serializer' => Redis::SERIALIZER_IGBINARY,
            'compression' => Redis::COMPRESSION_ZSTD,
        ],
    ],
    ```

#### 10.2 Outbox Processing Table Bloat
*   **Gejala:** Kueri outbox worker melambat secara drastis setelah beroperasi beberapa hari meskipun menggunakan `LIMIT 100`.
*   **Penyebab:** PostgreSQL mengalami table bloat akibat pembaruan massal `UPDATE ... status = 'DELIVERED'`, meninggalkan jutaan *dead tuples* tanpa vacuuming berkala.
*   **Solusi:** Terapkan strategi partisi tabel berdasarkan waktu (`RANGE (created_at)`) dan buat *retention daemon* yang langsung melakukan hard-delete pada baris yang telah terkirim (`DELETE FROM outbox_messages WHERE status = 'DELIVERED'`).

#### 10.3 Ghost Connection / FD Exhaustion pada Laravel Reverb
*   **Gejala:** Klien baru tidak dapat tersambung ke WebSocket; server Reverb melempar error `Too many open files`.
*   **Penyebab:** Nilai `ulimit -n` sistem operasi Linux terlalu rendah (default 1024) dan koneksi *dead half-open* tidak diakhiri karena *TCP Keepalive* tidak diaktifkan.
*   **Solusi:**
    1. Naikkan batasan file descriptors di `/etc/security/limits.conf`:
       ```text
       * soft nofile 65535
       * hard nofile 65535
       ```
    2. Konfigurasi Heartbeat/Ping pada client Laravel Echo ke 30 detik untuk mendeteksi *broken pipe* secara proaktif.

---

### 11. Best Practices (Production Checklist)

- [ ] **Redis Eviction Policy:** Konfigurasi Redis server dengan `maxmemory-policy volatile-lru` atau `allkeys-lru` guna mencegah crash `OOM (Out Of Memory)` saat spike.
- [ ] **Connection Pooling:** Pastikan PHP-FPM menggunakan persistent connection ke Redis (`'persistent' => true` di `database.php`) untuk menghindari TCP handshake latency di setiap request.
- [ ] **Kernel Parameter Tuning (WebSockets):**
  - `sysctl -w net.core.somaxconn=32768` (Mencegah drop koneksi WebSocket antrean incoming SYN).
  - `sysctl -w net.ipv4.tcp_max_syn_backlog=16384`
- [ ] **Idempotent Consumers:** Gunakan *Unique Deduplication Key* pada level worker konsumen sebelum memproses event:
  ```php
  if (!Redis::set("processed_event:{$eventId}", "1", "EX", 86400, "NX")) {
      return; // Skip: Event telah diproses sebelumnya
  }
  ```
- [ ] **Dead Letter Queue (DLQ):** Pastikan semua event outbox yang gagal lebih dari threshold maksimal dialihkan ke status `FAILED` dan memicu alert (Slack/PagerDuty) untuk investigasi manual.
- [ ] **Monitoring & APM:** Pantau metrik *Outbox Lag* (selisih waktu antara `created_at` pesan pending dan waktu sekarang).

---

### 12. Hands-on Practice

Buatlah implementasi Outbox Engine, Invalidation Middleware, dan WebSocket Event di direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Struktur Direktori
```bash
mkdir -p hands-on/m02/app/{Domain,Infrastructure}
mkdir -p hands-on/m02/config
```

#### Langkah 2: Buat Idempotent Event Consumer
Simpan file ini di: `hands-on/m02/app/Infrastructure/IdempotentConsumer.php`

```php
<?php

declare(strict_types=1);

namespace App\Infrastructure;

use Closure;
use Illuminate\Contracts\Redis\Connection as RedisConnection;
use RuntimeException;

final readonly class IdempotentConsumer
{
    public function __construct(
        private RedisConnection $redis,
        private int $ttlSeconds = 86400
    ) {}

    /**
     * Memastikan blok logika hanya dieksekusi tepat satu kali berdasarkan deduplication ID.
     */
    public function handle(string $deduplicationKey, Closure $process): bool
    {
        $lockKey = "idempotency:{$deduplicationKey}";

        // Atur atomic Redis SETNX dengan TTL
        $isUnique = (bool) $this->redis->set($lockKey, 'PROCESSED', 'EX', $this->ttlSeconds, 'NX');

        if (! $isUnique) {
            // Event duplikat terdeteksi, lewati pemrosesan
            return false;
        }

        try {
            $process();
            return true;
        } catch (\Throwable $e) {
            // Hapus lock jika terjadi crash agar memungkinkan retry dari broker
            $this->redis->del($lockKey);
            throw $e;
        }
    }
}
```

#### Langkah 3: Verifikasi Hands-on
Uji fungsionalitas deduplikasi dengan script simulasi eksekusi concurrent menggunakan PHP CLI:
```bash
php -r "
require 'vendor/autoload.php';
// Bootstrapping mini laravel instance test...
echo 'Idempotency implementation test ready.'.PHP_EOL;
"
```

---

### 13. Exercise

#### Level Easy
Ubah method `rememberNonBlocking` pada `ResilientCacheService` di sub-bab 7.1 agar menambahkan metrik log khusus (`Log::info`) ketika terjadi *Cache Hit*, *Cache Miss*, dan kondisi *Wait on Lock*.
*   *Verifikasi:* Pastikan entri log mencatat durasi waktu yang dihabiskan untuk membaca data dari cache vs menunggu lock.

#### Level Medium
Tambahkan mekanisme *Circuit Breaker* sederhana ke dalam `ProcessOutboxMessagesCommand`. Jika worker mendapati kegagalan koneksi broker/dispatcher berturut-turut sebanyak 5 kali:
1. Hentikan eksekusi sementara selama 10 detik.
2. Catat log berlevel `CRITICAL`.
3. Lanjutkan kembali pemrosesan secara graceful tanpa menghentikan daemon service (*unhandled exit*).
*   *Verifikasi:* Putuskan koneksi jaringan sementara dan amati transisi log worker.

#### Level Hard
Rancang dan implementasikan algoritma *Probabilistic Early Expiration* (Algoritma XFetch) ke dalam class decorator cache tersendiri:
$$\Delta t - \beta \times \ln(U) > \text{expiry} - \text{now}$$
Dimana:
*   $\Delta t$ adalah durasi komputasi resolver dalam detik.
*   $\beta > 0$ adalah faktor agresivitas (default 1.0).
*   $U \in (0, 1)$ adalah angka acak murni seragam (`lcg_value()`).
*   Jika rumus bernilai *true*, trigger background recalculation secara asinkron atau langsung perbarui data sebelum waktu TTL habis.
*   *Verifikasi:* Tunjukkan bahwa pada traffic konstan, tidak pernah terjadi cache miss murni di database.

---

### 14. Challenge

**Studi Kasus Skenario Produksi:**
Sebuah platform pertukaran aset kripto mengalami lonjakan pesanan drastis saat terjadi pergerakan harga tajam. 

**Kondisi Lingkungan:**
*   Platform menerima 30.000 event update saldo per detik.
*   WebSocket gateway menggunakan 4 node Laravel Reverb yang terhubung ke Redis Cluster (6 nodes; 3 master, 3 replica).
*   Tiba-tiba, terjadi *network partition* parsial yang memutus komunikasi antara Reverb Node 3 dengan Redis Master node yang memegang hash slot Pub/Sub.

**Misi Anda:**
1. Rancang arsitektur failover resilience yang mencegah WebSocket clients pada Reverb Node 3 mengalami *silent starvation* (kondisi di mana klien tetap terhubung pada TCP socket tetapi tidak pernah menerima pesan lagi karena Redis subscriber di node tersebut terputus).
2. Tuliskan arsitektur konfigurasi Redis Sentinel/Cluster, strategi health check kustom di Laravel Reverb, dan mekanisme fallback otomatis pada client (*Laravel Echo*) untuk mengalihkan koneksi ke node aktif lainnya dalam durasi sub-detik (< 800ms) tanpa memicu *connection storm*.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic
1. Mengapa memanggil `Cache::tags(['tag1'])->flush()` di Laravel berisiko menimbulkan *memory leak* tersembunyi pada Redis versi lama atau konfigurasi memori tertentu?
2. Apa fungsi parameter `SKIP LOCKED` pada kueri `SELECT ... FOR UPDATE SKIP LOCKED` dalam arsitektur Transactional Outbox?
3. Apa perbedaan mendasar antara model thread Laravel Reverb dibanding arsitektur Laravel standar di bawah PHP-FPM?
4. Mengapa kita tidak boleh menaruh `Event::dispatch()` yang memicu I/O eksternal di dalam blok `DB::transaction()`?
5. Apa kegunaan utama dari *Idempotency Key* pada sistem event consumer?

#### Intermediate
6. Bagaimana cara kerja proteksi *Cache Stampede* menggunakan *Atomic Locks* mencegah lebih dari satu request melakukan kueri database yang sama saat cache kedaluwarsa?
7. Apa dampak dari pengalihan serializer default Laravel Redis dari `serialize` PHP ke `igbinary` terhadap performa *throughput* CPU dan memori I/O?
8. Mengapa tabel Transactional Outbox harus memiliki kolom `created_at` yang diindeks secara b-tree saat volume pesan mencapai jutaan baris?
9. Bagaimana Laravel Reverb menangani perambatan pesan secara merata ke seluruh node lain saat sebuah event di-broadcast dari satu controller tertentu?
10. Pada kondisi apa algoritma *Probabilistic Early Expiration* (XFetch) lebih unggul dibandingkan penguncian distributed mutex (*Locking-based Cache*)?

#### Skenario Kasus Produksi
11. **Skenario 1:** Sebuah marketplace mengalami masalah di mana inventaris barang menjadi minus setelah flash sale berjalan 10 detik, padahal tim rekayasa telah menggunakan `Cache::decrement('product_stock')`. Telusuri di mana celah inkonsistensinya dan berikan desain arsitektur perbaikannya!
12. **Skenario 2:** Worker Outbox Anda yang berjalan secara multi-thread paralel mengalami deadlocks pada database MySQL InnoDB ketika memproses tabel `outbox_messages`. Setelah dicek, mereka menjalankan kueri `UPDATE outbox_messages SET status = 'PROCESSING' WHERE id IN (...)`. Mengapa terjadi deadlock dan bagaimana mengatasinya?
13. **Skenario 3:** Setelah deploy rilis aplikasi baru, cluster Laravel Reverb mengalami CPU Spikes hingga 100% pada semua node dalam kurun 5 menit pertama, lalu seluruh server Reverb crash serentak. Klien WebSocket di web frontend disetel untuk auto-reconnect saat terputus. Temukan akar masalahnya (*root-cause analysis*) dan buat formula perbaikan sisi klien dan infrastruktur!

---

### 16. Summary
*   **Caching Skala Besar:** Caching enterprise bukan sekadar menyimpan kunci dan nilai string; ini mencakup proteksi terhadap degradasi sistemik (*Cache Stampede*, *Avalanche*) melalui *Atomic Locks* dan *Stale Grace Periods*.
*   **Keandalan Event Melalui Outbox:** Ketergantungan langsung pada *in-memory* event dispatching atau broker eksternal di dalam transaksi database melanggar prinsip keandalan sistem terdistribusi. **Transactional Outbox Pattern** menjamin pesan tersimpan secara ACID dan terkirim dengan jaminan *At-Least-Once Delivery*.
*   **Real-time Berskala Tinggi:** Melalui **Laravel Reverb**, PHP bertransformasi menjadi platform *real-time event-driven* asynchronous berbasis *epoll* berlatensi rendah. Skalabilitas horizontal dicapai dengan mengintegrasikan Reverb nodes melalui Redis Pub/Sub cluster.
*   **Idempotency & Observability:** Pengiriman event terdistribusi pasti memiliki risiko duplikasi (*network retries*). Konsumen sistem wajib menerapkan desain idempoten deterministik dengan pelacakan jejak (*correlation ID / distributed tracing*) di setiap siklus hidup pesan.