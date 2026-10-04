# BAB 09: High-Performance Runtimes & Asynchronous Processing
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis perbedaan mekanik mendasar antara model eksekusi *Shared-Nothing* klasik (PHP-FPM) dan *Long-Running Process Engine* (Swoole, RoadRunner, FrankenPHP).
- Menguasai arsitektur *Event Loop* (Revolt/libuv), *Cooperative Multitasking* berbasis PHP Fiber (Zend Fibers), dan *Coroutine Engine* C-level (OpenSwoole/Swoole).
- Mengimplementasikan pola konkurensi non-blocking tingkat lanjut: *Multiplexed I/O*, *Connection Pooling* (Database/Cache), *Channel Synchronization*, dan *Actor/Worker Pattern*.
- Mengidentifikasi, mengisolasi, dan memitigasi memory leak, state pollution, dan race conditions pada environment persisten.
- Merancang dan menerapkan arsitektur runtime enterprise siap produksi dengan toleransi kegagalan tinggi, zero-downtime deployment (graceful reload), serta observabilitas penuh (APM & metrics telemetry).

---

### 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib memahami:
- Arsitektur internal PHP: Siklus hidup request PHP-FPM, Zend VM execution model (`opline`, `zend_execute_data`), Zend Memory Manager (ZMM/emalloc), dan Garbage Collection cycle collector.
- Konsep dasar Operating System: POSIX Signal (`SIGTERM`, `SIGUSR1`, `SIGCHLD`), Socket multiplexing (`epoll`, `kqueue`), Process fork/spawn, dan Thread safety (ZTS vs NTS).
- Pemrograman asinkron dasar: Konsep event-driven I/O, Future/Promise, dan arsitektur Client-Server TCP/HTTP.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Shared-Nothing vs. Long-Running In-Memory Runtimes
Model tradisional PHP-FPM mengusung filosofi *Shared-Nothing Architecture*:
1. Web server (Nginx) menerima koneksi TCP, melakukan TLS termination, dan meneruskan request via FastCGI protocol.
2. Worker FPM menerima request, mengalokasikan memori via Zend Memory Manager (ZMM).
3. Kode di-compile atau diambil dari Opcache, dieksekusi secara serial.
4. Response dikembalikan; ZMM membersihkan seluruh memory heap (`zend_mm_shutdown()`), semua variabel, superglobal (`$_SERVER`, `$_GET`), koneksi database ditutup (atau di-cache via pdo_persistent secara terbatas), dan state kembali ke nol.

Sebaliknya, **High-Performance Long-Running Runtimes** (seperti Swoole, RoadRunner, FrankenPHP) memutus siklus inisialisasi berulang ini:
- **FrankenPHP (Go + CGO + SAPI LibPHP):** Memanfaatkan Go HTTP server (berbasis Caddy) yang mengorkestrasi thread CGO langsung ke thread-safe Zend Engine (ZTS). Dengan *Worker Mode*, script aplikasi dieksekusi sekali ke dalam memori, lalu event loop memproses HTTP request langsung di memory space yang sama tanpa FastCGI overhead.
- **RoadRunner (Go Process Manager):** Menggunakan Goroutine untuk menangani concurrency di sisi reverse proxy/network layer, lalu berkomunikasi dengan worker PHP (CLI processes) melalui IPC berperforma tinggi (Unix Domain Sockets atau standard pipes) dengan binary payload (Protobuf/JSON).
- **OpenSwoole / Swoole (C/C++ Engine Extension):** Mengganti runtime PHP dengan model event-driven berbasis `epoll`/`kqueue`. Master Process memanajemen Reactor Threads (I/O multiplexing), yang kemudian mendistribusikan task ke Worker Processes melalui POSIX shared memory atau IPC pipe.

```
+---------------------------------------------------------------------------------------------------+
| PHP-FPM Model (Shared-Nothing)                                                                   |
| [Request] -> [FastCGI] -> [Boot Runtime -> Init ZMM -> Compile/Opcache -> Execute -> Flush/Die]  |
| Overhead: 15-40ms untuk framework bootstrapping pada setiap request tunggal                       |
+---------------------------------------------------------------------------------------------------+
| Long-Running Engine Model (FrankenPHP / Swoole / RoadRunner)                                      |
| [Boot Runtime -> Bootstrap Framework -> Cache Dependency Tree -> Preload Global State]            |
|                                     |                                                             |
|           +-------------------------+-------------------------+                                   |
|           v                                                   v                                   |
|   [Event Loop: Req 1]                                 [Event Loop: Req 2]                         |
|   [Execute Action -> Flush Response]                  [Execute Action -> Flush Response]          |
|   (Zero Framework Bootstrap Overhead: Sub-millisecond Execution Time)                             |
+---------------------------------------------------------------------------------------------------+
```

#### B. Internal Fiber vs. Coroutine vs. Event Loop
1. **Revolt PHP / Amphp / ReactPHP (Userland Event Loop):**
   Menggunakan loop tunggal (`select`, `poll`, atau via ekstensi `ev`/`event`/`uv`). Non-blocking I/O dicapai dengan mendaftarkan file descriptor (FD) ke event loop. Callback/Promise dipicu ketika FD berstatus *readable* atau *writable*.
2. **PHP 8.1+ Fibers (Cooperative Multitasking Low-Level):**
   Fibers menyediakan kemampuan *stackful interruptible functions* tanpa native OS thread context switching overhead. Fiber memiliki isolated call stack-nya sendiri (`zend_fiber_stack`).
   - Eksekusi Fiber dapat di-suspend (`Fiber::suspend()`) saat menunggu I/O, mengembalikan kontrol ke scheduler eksternal (Event Loop).
   - Scheduler memantau socket via `stream_select()` atau libuv.
   - Ketika socket siap, scheduler memanggil `Fiber::resume()`, mengembalikan context frame CPU register ke kondisi sebelum suspend.
3. **OpenSwoole Coroutines (C-Level Hooking):**
   Swoole melangkah lebih jauh dengan melakukan *runtime hooking* pada standard C/PHP socket API (`PDO`, `curl`, `file_get_contents`, `stream_socket_client`). Ketika fungsi blocking dipanggil, Swoole secara otomatis menginterupsi coroutine aktif di C-level, mendaftarkan underlying POSIX socket FD ke Reactor `epoll`, lalu me-resume coroutine secara transparan saat data tiba, tanpa developer perlu menulis syntax `await`.

#### C. Memory Lifecycle, Zval Management, dan Leak Hazards
Dalam long-running runtime, siklus Garbage Collection berubah drastis:
- **Static Scope Retention:** Variabel statis class (`public static array $cache = [];`), closure context bindings, and singleton dependency injection containers **tidak pernah dibersihkan antar request**.
- **Cyclic References & Cycle Collector:** Walaupun PHP memiliki refcounting, struktur sirkular (Object A me-reference Object B, dan sebaliknya) membutuhkan *Garbage Collection Cycle Collector* (`gc_collect_cycles()`). Jika threshold buffer cycle (default 10,000 nodes pada zend_gc.c) tercapai pada intensitas alokasi tinggi, CPU spikes akan terjadi secara mendadak.
- **ZMM (Zend Memory Manager) Chunk Fragmentation:** Walaupun tidak ada direct leak di application-level, continuous allocation dan deallocation struktur kompleks di dalam persistent process dapat menyebabkan fragmentasi heap ZMM, yang memaksa OS menaikkan Resident Set Size (RSS) worker process.

---

### 4. Why & What

| Dimensi | PHP-FPM Standar | High-Performance Asynchronous Runtime |
| :--- | :--- | :--- |
| **Model Arsitektur** | Multi-process, single-threaded per request, Shared-Nothing | Multi-process / Multi-threaded Event Loop, Non-blocking Coroutine / Fiber |
| **I/O Model** | Synchronous Blocking I/O | Asynchronous Non-blocking I/O (epoll/kqueue) |
| **Biaya Bootstrapping** | 100% per request (Composer autoloader, DI Container, Config parsing) | 1x pada startup server (Cold start tinggi, Hot runtime instan) |
| **Resource Footprint** | Tinggi di memory footprint per worker (~20-50MB per proses FPM) | Efisien. Satu worker dapat menangani ribuan concurrent sockets |
| **Konektivitas Database** | 1 process = 1 persistent connection max (terbatas) | Dynamic Connection Pooling terpusat lintas coroutine |
| **Use Case Dominan** | CRUD Web Tradisional, CMS, Low-to-Medium Traffic | High-Throughput APIs, Real-time WebSockets, Microservices, Streaming |

#### Mengapa Beralih?
1. **Throughput Scaling:** Melejitkan throughput (RPS - Requests Per Second) 5 hingga 20 kali lipat dibanding PHP-FPM pada perangkat keras yang sama.
2. **Latensi I/O Ekstrem:** Saat aplikasi mikroservis perlu memanggil 5 downstream HTTP services dan 3 query database independen, FPM mengeksekusinya secara serial (Total latency = $\sum t$). Runtime asinkron mengeksekusinya secara paralel non-blocking via concurrency primitives (Total latency = $\max(t)$).
3. **Kemampuan Protokol Modern:** Mendukung native WebSockets, HTTP/2 Server Push, gRPC, dan server-sent events (SSE) secara elegan langsung dari PHP.

---

### 5. How (Workflow Detail)

Arsitektur siklus request-response pada runtime modern (misal: FrankenPHP/Swoole):

```
+---------------------------------------------------------------------------------------------------+
|                        ALUR SIKLUS HIDUP WORKER LONG-RUNNING                                      |
+---------------------------------------------------------------------------------------------------+
 1. INITIALIZATION & PRELOAD PHASE
    OS CLI -> Master Process Starts -> Execute Bootstrap -> Preload Code via Opcache
    -> Bind Service Containers -> Initialize Database Connection Pool -> Register Signal Handlers
                                              |
 2. FORKING / WORKER GENERATION               |
    Master Process melakukan fork N Worker Processes (atau ZTS Worker Threads)
                                              |
 3. EVENT LOOP LISTENING                     v
    Worker Process memasuki state: while ($running) {
        a. Suspend worker, tunggu incoming request dari shared master socket (epoll_wait).
        b. Accept Request -> Buat Request Context (Sandbox).
        c. Salin/Petakan Superglobals (PSR-7 / HttpFoundation Request abstraction).
                                              |
 4. REQUEST EXECUTION & CONCURRENCY           v
        d. Inisiasi Coroutine / Fiber untuk Controller execution.
        e. Jika ada Operasi I/O (DB, HTTP, Disk):
           - Coroutine switch: yield execution context.
           - Reactor thread memantau event I/O pada backend socket.
           - Saat ready: Coroutine resume, kembali ke stack frame execution.
                                              |
 5. TERMINATION & CLEANUP PHASE               v
        f. Response dikirimkan ke Client via Socket Stream.
        g. TRIGGER APPLICATION CLEANUP:
           - Reset Request-scoped singletons (misal: Current User, DB Transaction states).
           - Clear File Upload Buffers / Temporary files.
           - Evaluasi Memory Limit & Max Execution Count.
           - Jika Request Count > Limit -> Clean exit, Master Process re-forks a fresh worker.
    }
+---------------------------------------------------------------------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Restoran Tradisional (PHP-FPM) vs Restoran Fast-Track Modern (Coroutine Runtime)

- **PHP-FPM:** Mirip restoran di mana untuk setiap satu pelanggan, satu koki ditugaskan secara eksklusif. Koki tersebut masuk ke dapur, membangun kompor dari awal, memotong sayur, memasak steak, menunggu oven selama 30 menit (koki hanya diam menunggu oven), menyajikan makanan, lalu **merobohkan seluruh dapur dan kompor hingga rata dengan tanah**. Pelanggan berikutnya datang, koki baru harus membangun dapur lagi dari awal.
- **Asynchronous Runtime:** Dapur sudah dibangun dan peralatan menyala permanen (Bootstrap sekali). Koki memasukkan steak ke oven (I/O call non-blocking), memasang timer (Event Loop), lalu langsung melayani pesanan pasta untuk meja lain (Fiber/Coroutine switch). Ketika timer oven berdering, koki kembali mengambil steak dan menyajikannya. Dapur tidak pernah dirobohkan, hanya piring yang dicuci bersih antar sajian (Request Cleanup).

```
Arsitektur Swoole / Process Multiplexing:

                   +-----------------------------+
                   |     Master Process (OS)     |
                   |   (Listens to Network Port) |
                   +--------------+--------------+
                                  |
                   +--------------v--------------+
                   |    Reactor Threads Pool     |
                   |  (epoll / kqueue network)   |
                   +------+---------------+------+
                          |               |
             IPC Pipe / UDS       IPC Pipe / UDS
                          |               |
     +--------------------v--+         +--v--------------------+
     | Worker Process 1      |         | Worker Process 2      |
     | +-------------------+ |         | +-------------------+ |
     | | Coroutine Engine  | |         | | Coroutine Engine  | |
     | |  [Co 1]   [Co 2]  | |         | |  [Co 1]   [Co 2]  | |
     | +-------------------+ |         | +-------------------+ |
     | | Connection Pool   | |         | | Connection Pool   | |
     | | [DB1] [DB2] [DB3] | |         | | [DB1] [DB2] [DB3] | |
     | +-------------------+ |         | +-------------------+ |
     +-----------------------+         +-----------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Vanilla PHP 8.2+ Fiber Scheduler (Mekanisme Internal Tanpa Ekstensi)
Contoh berikut menunjukkan bagaimana runtime concurrency dibangun dari nol menggunakan standard library PHP:

```php
<?php

declare(strict_types=1);

namespace Enterprise\Async;

final class SimpleTask
{
    public function __construct(
        private readonly \Fiber $fiber,
        public mixed $sendValue = null
    ) {}

    public function run(): mixed
    {
        return $this->fiber->resume($this->sendValue);
    }

    public function isFinished(): bool
    {
        return $this->fiber->isTerminated();
    }
}

final class MicroScheduler
{
    /** @var \SplQueue<SimpleTask> */
    private \SplQueue $queue;

    public function __construct()
    {
        $this->queue = new \SplQueue();
    }

    public function enqueue(callable $callable): void
    {
        $fiber = new \Fiber($callable);
        $task = new SimpleTask($fiber);
        $this->queue->enqueue($task);
    }

    public function run(): void
    {
        while (!$this->queue->isEmpty()) {
            $task = $this->queue->dequeue();
            
            try {
                if (!$task->isFinished()) {
                    // Start or resume execution
                    $task->fiber->isStarted() ? $task->run() : $task->fiber->start();
                    
                    if (!$task->isFinished()) {
                        // Task belum selesai (yield/suspend), masukkan kembali ke antrian
                        $this->queue->enqueue($task);
                    }
                }
            } catch (\Throwable $e) {
                echo "Task Exception: " . $e->getMessage() . PHP_EOL;
            }
        }
    }
}

// Simulasi Non-blocking Non-preemptive Task Switching
$scheduler = new MicroScheduler();

$scheduler->enqueue(function (): void {
    echo "[Task A - Step 1] Inisialisasi request HTTP downstream\n";
    \Fiber::suspend();
    echo "[Task A - Step 2] Response HTTP downstream diterima, proses JSON\n";
});

$scheduler->enqueue(function (): void {
    echo "[Task B - Step 1] Membaca cache Redis lokal\n";
    \Fiber::suspend();
    echo "[Task B - Step 2] Mengupdate metrik transaksi\n";
});

echo "Scheduler Starting...\n";
$scheduler->run();
echo "Scheduler Finished.\n";
```

#### B. Practical Example: Enterprise Production Connection Pool (OpenSwoole Engine)
Contoh implementasi production-ready PDO connection pool thread-safe dengan dynamic health check, backoff retry, dan channel synchronization.

```php
<?php

declare(strict_types=1);

namespace Enterprise\Database;

use OpenSwoole\Coroutine;
use OpenSwoole\Coroutine\Channel;
use PDO;
use PDOException;
use RuntimeException;

final class Config
{
    public function __construct(
        public readonly string $dsn,
        public readonly string $username,
        public readonly string $password,
        public readonly int $minConnections = 5,
        public readonly int $maxConnections = 20,
        public readonly float $waitTimeoutSeconds = 3.0,
        public readonly int $maxIdleTimeSeconds = 60
    ) {}
}

final class PooledConnection
{
    private float $lastUsedAt;

    public function __construct(
        public readonly PDO $pdo,
        public readonly int $id
    ) {
        $this->lastUsedAt = microtime(true);
    }

    public function markUsed(): void
    {
        $this->lastUsedAt = microtime(true);
    }

    public function getIdleTime(): float
    {
        return microtime(true) - $this->lastUsedAt;
    }

    public function isAlive(): bool
    {
        try {
            $this->pdo->query('SELECT 1')->fetch();
            return true;
        } catch (\Throwable) {
            return false;
        }
    }
}

final class CoroutineDatabasePool
{
    private Channel $poolChannel;
    private int $currentConnections = 0;
    private bool $isTerminating = false;

    public function __construct(private readonly Config $config)
    {
        // Channel berfungsi sebagai blocking queue yang aware terhadap coroutine
        $this->poolChannel = new Channel($this->config->maxConnections);
        $this->warmup();
    }

    private function createConnection(): PooledConnection
    {
        $pdo = new PDO(
            $this->config->dsn,
            $this->config->username,
            $this->config->password,
            [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_PERSISTENT => false,
            ]
        );

        $this->currentConnections++;
        return new PooledConnection($pdo, $this->currentConnections);
    }

    private function warmup(): void
    {
        for ($i = 0; $i < $this->config->minConnections; $i++) {
            $conn = $this->createConnection();
            $this->poolChannel->push($conn);
        }
    }

    public function acquire(): PooledConnection
    {
        if ($this->isTerminating) {
            throw new RuntimeException("Pool is shutting down.");
        }

        // 1. Ambil dari pool jika tersedia tanpa blocking
        if (!$this->poolChannel->isEmpty()) {
            /** @var PooledConnection $conn */
            $conn = $this->poolChannel->pop(0.001);
            if ($this->validateConnection($conn)) {
                $conn->markUsed();
                return $conn;
            }
            $this->currentConnections--;
        }

        // 2. Jika pool kosong dan limit belum tercapai, buat koneksi baru
        if ($this->currentConnections < $this->config->maxConnections) {
            return $this->createConnection();
        }

        // 3. Pool penuh, suspend coroutine dan tunggu hingga koneksi dikembalikan
        $conn = $this->poolChannel->pop($this->config->waitTimeoutSeconds);
        
        if ($conn === false) {
            throw new RuntimeException("Database pool connection exhaustion timeout.");
        }

        if (!$this->validateConnection($conn)) {
            $this->currentConnections--;
            return $this->acquire(); // Retry recursive fetch
        }

        $conn->markUsed();
        return $conn;
    }

    public function release(PooledConnection $conn): void
    {
        if ($this->isTerminating) {
            $this->currentConnections--;
            return;
        }

        $this->poolChannel->push($conn, 0.5);
    }

    private function validateConnection(PooledConnection $conn): bool
    {
        if ($conn->getIdleTime() > $this->config->maxIdleTimeSeconds) {
            return $conn->isAlive();
        }
        return true;
    }

    public function shutdown(): void
    {
        $this->isTerminating = true;
        while (!$this->poolChannel->isEmpty()) {
            $conn = $this->poolChannel->pop(0.1);
            unset($conn);
            $this->currentConnections--;
        }
        $this->poolChannel->close();
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Flash Sale & Real-time Ledger API Bank Digital
- **Beban Lalu Lintas:** 45.000 Request/detik (RPS) pada peak hours dengan read/write ratio 70:30.
- **Problem PHP-FPM:**
  - Konfigurasi FPM mentok pada 800 workers per node. Ketika lonjakan traffic terjadi, pool FPM mengalami *queue exhaustion*.
  - Latensi P99 melonjak dari 45ms ke 12.000ms karena antrian soket kernel FastCGI penuh.
  - Setiap request membuka koneksi database terpisah, mengakibatkan PostgreSQL crash akibat `max_connections` (10.000+) meledak dan memicu Out-of-Memory (OOM) killer.

#### Solusi Arsitektur Menggunakan FrankenPHP + Swoole Concurrency:
1. **Migration Layer:** Migrasi aplikasi Laravel Core ke **FrankenPHP Worker Mode** dengan deployment pada Kubernetes Cluster.
2. **Eliminasi Bootstrap:** Waktu bootstrap Laravel (~35ms) dipotong menjadi 0ms per request karena aplikasi menetap di memori worker Caddy.
3. **Database Concurrency Isolation:**
   - Mengganti default database driver dengan *Coroutine-aware Connection Pool* (50 koneksi aktif per pod FrankenPHP, melayani 2.000 concurrent client streams). Total koneksi ke PostgreSQL turun dari 10.000 menjadi 400 pool terkelola.
4. **Context Sandbox Enforcer:**
   - Dibuat pipeline middleware ketat untuk membersihkan Request-scoped instances di IoC Container:
   ```php
   app()->forgetInstance('auth.user');
   app()->forgetInstance('request');
   ```

#### Hasil Benchmarking Produksi:
- **Throughput:** Meningkat dari 1.800 RPS (PHP-FPM 16 Pods) menjadi 26.500 RPS (FrankenPHP 4 Pods).
- **Latensi:** P95 turun dari 2.400ms ke 18ms; P99 stabil di 32ms.
- **Resource Footprint:** Penggunaan CPU Node berkurang 65%, memori hemat hingga 80% karena pemotongan ratusan OS process FPM menjadi shared worker thread.

---

### 9. Trade-offs

```
                  [ PERFORMANCE & THROUGHPUT ]
                               /\
                              /  \
                             /    \
                            /      \
                           /  SWOOLE\
                          /FRANKENPHP\
                         /            \
                        /              \
                       /                \
  [ STABILITY & ISOLATION ] ----------- [ ARCHITECTURAL SIMPLICITY ]
         (PHP-FPM)                               (PHP CLI SCRIPTS)
```

| Parameter | PHP-FPM | Long-Running Runtime (FrankenPHP / Swoole) |
| :--- | :--- | :--- |
| **Throughput & Latency** | Rendah - Menengah. Bound oleh bootstrap overhead dan context switching OS process. | Sangat Tinggi. P99 latency konsisten sangat rendah. |
| **Fault Isolation** | **Mutlak**. Crash/Fatal error/Memory leak di satu request mati seketika bersama script lifecycle; request lain aman. | **Rentan**. Uncaught exception fatal atau memory leak di satu thread/coroutine dapat mengorbankan worker process yang melayani ratusan client lain. |
| **Development Complexity** | **Sangat Rendah**. Model imperatif sekuensial standar tanpa perlu khawatir memory management mendalam. | **Tinggi**. Developer harus memahami garbage collection, non-blocking flow, lifecycle containment, thread/coroutine safety. |
| **Infrastructure Cost** | Tinggi pada beban ekstrem (membutuhkan over-provisioning pod/node besar). | Sangat Rendah. Mengoptimalkan density utilization hardware secara maksimal. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Memory Leak via Static Properties & Singletons
*Kesalahan:*
```php
class MetricCollector {
    public static array $durations = []; // Akan terus membengkak hingga OOM!
    public static function track(float $time): void {
        self::$durations[] = $time;
    }
}
```
*Solusi Enterprise:*
Hindari static accumulator global. Selalu batasi array dengan circular ring buffer atau kirimkan via channel metrics aggregator ke UDP/StatsD stream secara non-blocking.

#### 2. Coroutine State Pollution (Cross-Request Leak)
*Kesalahan:*
Menggunakan class static variable untuk menyimpan data pengguna aktif:
```php
class SecurityContext {
    private static ?User $currentUser = null;
    public static function setUser(User $user): void { self::$currentUser = $user; }
    public static function getUser(): ?User { return self::$currentUser; }
}
```
Pada runtime coroutine, Client B bisa membaca data milik Client A jika coroutine Client A melakukan suspend sebelum mengambil data.
*Solusi Enterprise:*
Gunakan **Coroutine Context Storage** berbasis ID Coroutine:
```php
use OpenSwoole\Coroutine;

class SecurityContext {
    public static function setUser(User $user): void {
        Coroutine::getContext()['user'] = $user;
    }
    public static function getUser(): ?User {
        return Coroutine::getContext()['user'] ?? null;
    }
}
```

#### 3. Blocking Calls di Dalam Loop Asinkron
*Kesalahan:*
Memanggil `sleep()`, `file_get_contents()`, `flock()`, atau library legacy yang menggunakan PHP cURL extension standar yang tidak di-hook. Hal ini akan mem-block **seluruh thread worker OS**, melumpuhkan ratusan coroutine lain di worker tersebut.
*Troubleshooting:*
- Aktifkan Runtime Coroutine Hooking: `\OpenSwoole\Runtime::enableCoroutine(SWOOLE_HOOK_ALL);`
- Gunakan audit analyzer static analysis tools untuk memblokir fungsi sinkron standar dalam codebase non-blocking.

---

### 11. Best Practices (Production Checklist)

- [ ] **Max Requests Recycling:** Konfigurasi worker recycling hard limit (contoh: me-restart worker setiap 10.000 request atau saat memory menembus threshold 80% dari batas container) untuk menetralisir slow micro-leaks.
- [ ] **State Sanitization Middleware:** Terapkan automated middleware yang melakukan reset DI Container scoped services, doctrine identity maps, dan superglobal mockings pada blok `finally`.
- [ ] **Disable Blocking Functions via php.ini:** Larang pemanggilan functions berbahaya via `disable_functions = sleep,usleep` di worker code, arahkan ke coroutine sleep (`Coroutine::sleep()`).
- [ ] **Dynamic Connection Pool Sizing:** Set Pool Size dengan rumus: $\text{Pool Size} = (\text{Worker Count} \times \text{Simultaneous Coroutines per Worker}) \div \text{Database Node Count}$. Batasi jangan sampai overload database upstream.
- [ ] **POSIX Signal Handling Graceful Termination:**
  ```php
  Process::signal(SIGTERM, function() use ($server, $pool) {
      $server->stop(); // Stop accepting new connections
      $pool->shutdown(); // Flush pending connections
      exit(0);
  });
  ```
- [ ] **Health Probing & Circuit Breaking:** Tambahkan endpoint `/livez` dan `/readyz` yang memverifikasi saturasi coroutine queue dan ketersediaan database connection pool.

---

### 12. Hands-on Practice

Buat dan simpan struktur file praktikum ini pada direktori: `hands-on/m02/`

#### Step 1: Inisialisasi Environment
Buat file `hands-on/m02/composer.json`:
```json
{
    "name": "enterprise/high-perf-runtime",
    "type": "project",
    "require": {
        "php": ">=8.2"
    },
    "autoload": {
        "psr-4": {
            "Enterprise\\Async\\": "src/"
        }
    }
}
```

#### Step 2: Implementasi State Container & Isolation Engine
Buat file `hands-on/m02/src/ContextManager.php`:
```php
<?php

declare(strict_types=1);

namespace Enterprise\Async;

final class ContextManager
{
    /** @var array<int, array<string, mixed>> */
    private static array $storage = [];

    public static function set(string $key, mixed $value): void
    {
        $cid = self::getCurrentContextId();
        self::$storage[$cid][$key] = $value;
    }

    public static function get(string $key): mixed
    {
        $cid = self::getCurrentContextId();
        return self::$storage[$cid][$key] ?? null;
    }

    public static function destroy(): void
    {
        $cid = self::getCurrentContextId();
        unset(self::$storage[$cid]);
    }

    public static function getActiveContextCount(): int
    {
        return count(self::$storage);
    }

    private static function getCurrentContextId(): int
    {
        // Mendeteksi Fiber context ID, jika tidak di dalam Fiber gunakan thread main ID (0)
        $fiber = \Fiber::getCurrent();
        return $fiber !== null ? spl_object_id($fiber) : 0;
    }
}
```

#### Step 3: Implementasi Resilient HTTP Micro-Worker Loop
Buat file `hands-on/m02/server.php`:
```php
<?php

declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

use Enterprise\Async\ContextManager;

$socket = stream_socket_server("tcp://0.0.0.0:8080", $errno, $errstr);
if (!$socket) {
    die("Error binding socket: $errstr ($errno)\n");
}

stream_set_blocking($socket, false);
echo "Enterprise Non-blocking Fiber Server running on port 8080...\n";

/** @var \SplQueue<\Fiber> $fibers */
$fibers = new \SplQueue();

$running = true;
// Register graceful termination signal
if (extension_loaded('pcntl')) {
    pcntl_signal(SIGTERM, function() use (&$running) { $running = false; });
    pcntl_signal(SIGINT, function() use (&$running) { $running = false; });
}

while ($running) {
    if (extension_loaded('pcntl')) {
        pcntl_signal_dispatch();
    }

    // Accept incoming connection
    $client = @stream_socket_accept($socket, 0.01);
    if ($client !== false) {
        stream_set_blocking($client, false);
        
        $fiber = new \Fiber(function() use ($client): void {
            ContextManager::set('request_id', bin2hex(random_bytes(8)));
            
            // Baca HTTP request header buffer
            $buffer = '';
            while (!str_contains($buffer, "\r\n\r\n")) {
                $chunk = @fread($client, 1024);
                if ($chunk === false || $chunk === '') {
                    \Fiber::suspend();
                    continue;
                }
                $buffer .= $chunk;
            }

            // Simulasi processing time
            $reqId = ContextManager::get('request_id');
            $body = json_encode([
                'status' => 'OK',
                'request_id' => $reqId,
                'active_contexts' => ContextManager::getActiveContextCount(),
                'timestamp' => microtime(true),
            ]);

            $response = "HTTP/1.1 200 OK\r\n" .
                        "Content-Type: application/json\r\n" .
                        "Content-Length: " . strlen($body) . "\r\n" .
                        "Connection: close\r\n\r\n" . 
                        $body;

            @fwrite($client, $response);
            @fclose($client);

            // KRUSIAL: Membersihkan context saat request lifecycle berakhir
            ContextManager::destroy();
        });

        $fibers->enqueue($fiber);
        $fiber->start();
    }

    // Cycle & resume suspended fibers
    $count = $fibers->count();
    for ($i = 0; $i < $count; $i++) {
        $fiber = $fibers->dequeue();
        if (!$fiber->isTerminated()) {
            $fiber->resume();
            $fibers->enqueue($fiber);
        }
    }

    // Minimal sleep untuk mencegah CPU starvation 100% pada spinlock idle
    usleep(1000); // 1ms
}

echo "Gracefully shutting down server...\n";
fclose($socket);
```

#### Step 4: Testing & Eksekusi
1. Jalankan server: `php server.php`
2. Kirim concurrent request dari terminal terpisah:
   `curl -i http://127.0.0.1:8080`
3. Amati bagaimana data `request_id` terisolasi sempurna antar koneksi dan `active_contexts` kembali ke 0.

---

### 13. Exercise

#### Level: Easy
Buat script PHP dengan native `Fiber` yang menjalankan dua task:
- Task 1: Menghitung angka 1 hingga 5, namun melakukan `Fiber::suspend()` setiap angka genap.
- Task 2: Mencetak string `[PING]` lalu suspend, kemudian mencetak `[PONG]` lalu terminate.
- Jalankan keduanya secara interleaved menggunakan loop scheduler sederhana.

#### Level: Medium
Implementasikan class `AsyncHttpClient` sederhana berbasis stream non-blocking (`stream_socket_client`, `stream_select`) terintegrasi dengan `Fiber`. Method `get(string $url): string` harus melakukan `Fiber::suspend()` saat socket belum siap dibaca, dan di-resume oleh event loop utama ketika response downstream tiba tanpa memblokir thread execution.

#### Level: Hard
Rancang engine **Worker Process Supervisor** menggunakan `pcntl_fork()`:
- Master process melakukan fork 4 worker process.
- Setiap worker mengeksekusi long-running while loop.
- Master memantau lifecycle worker melalui `pcntl_waitpid()`.
- Jika salah satu worker mati akibat runtime fatal error (simulasikan dengan trigger memory limit atau `exit(1)`), Master harus mendeteksi sinyal kematian, me-reap zombie process, dan secara otomatis melakukan auto-restart worker baru untuk menjaga pool tetap berjumlah 4.
- Terapkan penanganan sinyal `SIGUSR1` pada Master untuk melakukan **Graceful Rolling Reload** (restart worker satu per satu secara bergantian tanpa memutus incoming traffic).

---

### 14. Challenge

**Skenario Sistem:**
Anda adalah Principal Systems Architect di platform pembayaran instan. Anda diminta membangun engine **Asynchronous Dead-Letter Re-drive & Outbox Processor** menggunakan OpenSwoole atau Revolt PHP yang memenuhi parameter berikut:
1. Harus memproses minimum 5.000 webhook events/detik dari database pool table tanpa membebani IOPS database secara masif.
2. Setiap pengiriman webhook ke external merchant HTTP endpoint memiliki timeout P99 2.5 detik. Pengiriman WAJIB dilakukan secara concurrent non-blocking (maksimal 500 outbound request concurrently).
3. Jika merchant merespons HTTP status 429 atau 5xx, engine harus mengeksekusi algoritma *Exponential Backoff with Jitter* secara in-memory, lalu mengalokasikan task tersebut ke dynamic priority delay queue tanpa memblokir worker thread lainnya.
4. **Target:** Buat rancangan class, alur memory pipeline, handling crash worker, dan mekanisme zero-data-loss ketika server menerima sinyal `SIGTERM` dari orchestrator Kubernetes saat proses *drain* berlangsung 30 detik. Buktikan tidak ada memory leak dalam eksekusi 24 jam non-stop via cycle collector tracking.

---

### 15. Quiz Evaluasi Pemahaman

#### Section A: Basic (Pilihan Ganda & Konseptual Singkat)
1. **Mengapa PHP-FPM secara inheren bebas dari resiko memory leak antar request?**
   - a) Karena PHP-FPM tidak mendukung dynamic object allocation.
   - b) Karena Zend Memory Manager mereset dan membuang seluruh alokasi heap saat request berakhir (`zend_mm_shutdown`).
   - c) Karena PHP-FPM meng-compile script menjadi binary C native.
   - d) Karena PHP-FPM berjalan di mode Read-Only Memory.
2. **Apa peran utama dari primitive `Fiber` yang diperkenalkan pada PHP 8.1?**
   - a) Menjalankan kode pada thread CPU yang terpisah secara paralel preemptive.
   - b) Menyediakan stackful coroutine interruptible untuk cooperative multitasking di userland.
   - c) Menggantikan database connection pool extension.
   - d) Menghilangkan kebutuhan garbage collector di Zend Engine.
3. **Apa bahaya terbesar mendeklarasikan static property array pada framework yang berjalan di atas FrankenPHP Worker Mode atau Swoole?**
   - a) Static array tidak bisa dibaca oleh coroutine lain.
   - b) Terjadi memory leak permanen karena array akan terus bertambah ukurannya dan menetap sepanjang umur worker process.
   - c) Engine otomatis melempar `FatalError: Static arrays are deprecated`.
   - d) Data array otomatis di-flush ke disk dan memperlambat I/O.
4. **Apa perbedaan antara `Cooperative Multitasking` dan `Preemptive Multitasking`?**
   - Jawab singkat: *Cooperative* bergantung pada kode/task yang secara sukarela menyerahkan kontrol (`yield`/`suspend`), sedangkan *Preemptive* dikontrol paksa oleh OS scheduler melalui hardware context switching (interrupt).
5. **Sinyal POSIX apa yang secara konvensional digunakan untuk memicu `Graceful Reload` tanpa mematikan process socket listener?**
   - a) `SIGKILL`
   - b) `SIGUSR1` atau `SIGHUP`
   - c) `SIGSEGV`
   - d) `SIGSTOP`

#### Section B: Intermediate (Analisis Arsitektur & Troubleshooting)
6. **Perhatikan cuplikan kode ini di dalam runtime Swoole:**
   ```php
   $server->on('request', function ($request, $response) {
       $data = file_get_contents('http://slow-api.internal/data');
       $response->end($data);
   });
   ```
   **Jika Runtime Hooking TIDAK diaktifkan, apa dampak pemanggilan ini terhadap 100 client lain yang terhubung ke worker process yang sama?**
   - Seluruh worker process akan terblokir total (freeze) pada level kernel I/O selama latency `slow-api.internal` berlangsung. 100 client lain tidak akan diproses sama sekali hingga blocking read selesai.
7. **Bagaimana cara mendeteksi circular memory reference leak pada long-running PHP process secara programatik?**
   - Menggunakan kombinasi pemantauan `memory_get_usage(true)` untuk real OS allocation, `gc_mem_caches()`, serta mengevaluasi output kembalian dari `gc_collect_cycles()` yang mengembalikan jumlah cycle zval yang berhasil dibersihkan dari cyclic buffer.
8. **Mengapa Connection Pool database mutlak diperlukan pada runtime asinkron, sementara di PHP-FPM tidak umum digunakan?**
   - Di FPM, satu process melayani satu request secara sekuensial, sehingga satu koneksi database per process sudah mencukupi. Pada engine asinkron, satu worker melayani ribuan concurrent coroutines/requests secara multiplexing; jika semua request berbagi 1 koneksi PDO yang sama, stream query akan corrupt dan collision (out-of-sequence packets). Connection pool menyediakan mekanisme antrian koneksi multiplexed yang aman.
9. **Apa fungsi dari abstract socket `epoll` (Linux) / `kqueue` (BSD/macOS) pada modern I/O worker?**
   - I/O multiplexing event notification mechanism dengan kompleksitas $O(1)$ yang memungkinkan satu thread memonitor jutaan file descriptors (FD) untuk kesiapan read/write tanpa perlu melakukan polling scanning sekuensial yang boros CPU ($O(N)$).
10. **Apa yang dimaksud dengan "Zombie Process" saat mengimplementasikan Multi-process Worker Pool di PHP CLI, dan fungsi sistem apa yang digunakan untuk mencegahnya?**
    - Zombie process adalah child process yang telah selesai dieksekusi (terminated), tetapi entry-nya masih tertahan di process table OS karena parent belum membaca exit status-nya. Dicegah menggunakan fungsi `pcntl_wait()` atau `pcntl_waitpid()`, atau menangani sinyal `SIGCHLD`.

#### Section C: Skenario Kasus Produksi
11. **Skenario 1: Deadlock Connection Pool**
    Aplikasi microservice berbasis OpenSwoole dengan worker connection pool size = 10 menerima request transaksi finansial. Setiap request membutuhkan dua koneksi: Koneksi A untuk logging audit, dan Koneksi B untuk update saldo. Di bawah load tinggi (10 request masuk bersamaan), semua request berhasil meng-acquire Koneksi A, lalu secara simultan mencoba meng-acquire Koneksi B dari pool. Pool kosong, semua request ter-suspend menunggu Koneksi B rilis. Aplikasi hang total (Deadlock).
    *Pertanyaan:* Bagaimana modifikasi arsitektur pool atau flow request untuk menyelesaikan masalah ini tanpa menambah kapasitas database node?
    *Jawaban Evaluasi:* 
    1. Terapkan *Single Connection Transaction Scope*: Audit log dan saldo update harus dieksekusi menggunakan instans koneksi yang sama di dalam satu context unit-of-work.
    2. Jika isolasi mutlak diperlukan, audit logging diubah menjadi out-of-band non-blocking operation via in-memory queue (Channel) yang diproses terpisah oleh dedicated logging worker, sehingga request lifecycle hanya meng-acquire 1 koneksi database.
12. **Skenario 2: Latency Spikes Karena Cycle Collector Pause**
    Pada environment FrankenPHP, aplikasi mengalami P99 latency spikes sebesar 800ms setiap 2 menit sekali. Setelah dicek via metrics APM, lonjakan latency berkorelasi tepat dengan aktivitas Zend Garbage Collector cycle run.
    *Pertanyaan:* Apa root cause dari masalah ini dan bagaimana solusi tuning runtime-nya?
    *Jawaban Evaluasi:* 
    Root cause: Pembuatan jutaan objek jangka pendek dengan circular reference menyebabkan Zend GC root buffer (10.000 zvals) cepat penuh, memicu `gc_collect_cycles()` stop-the-world execution yang mengunci runtime. Solusi: Tuning `zend.enable_gc = 0` jika memori container cukup, atau jalankan `gc_collect_cycles()` secara manual pada titik idle / di akhir request cycle (`gc_collect_cycles()` dipanggil saat request selesai sebelum accept request baru), atau refactor codebase untuk memutus circular references (gunakan `WeakReference`).
13. **Skenario 3: Superglobal Mutability Collision**
    Sebuah aplikasi monolitik dimigrasikan dari FPM ke FrankenPHP Worker Mode. Beberapa developer senior mengeluhkan bahwa variabel `$_SERVER['HTTP_AUTHORIZATION']` terkadang tertukar antar pengguna yang mengakses endpoint bersamaan pada high concurrency.
    *Pertanyaan:* Jelaskan mengapa hal ini terjadi pada arsitektur worker thread dan bagaimana cara mengatasinya secara fundamental!
    *Jawaban Evaluasi:*
    Dalam FrankenPHP worker mode, superglobals bersifat global/shared jika dieksekusi di context yang tidak di-sandbox secara thread-safe. Jika Worker Thread A menerima request dan mengisi `$_SERVER`, lalu ter-suspend sebelum response selesai dikirim, Worker Thread B yang menerima request baru akan menimpa memory space `$_SERVER` tersebut jika engine tidak mengisolasi global state. Solusi fundamental: Hentikan penggunaan native PHP superglobals (`$_SERVER`, `$_GET`, `$_POST`). Refactor aplikasi agar mengadopsi standar **PSR-7 (ServerRequestInterface)** yang merepresentasikan request secara immutable value objects, dan inject context request secara murni via DI scoped dependencies.

---

### 16. Summary

1. **Paradigma Runtime:** Transisi dari PHP-FPM ke runtime modern (Swoole, FrankenPHP, RoadRunner) adalah evolusi dari pendekatan *Shared-Nothing Ephemeral* menuju *Persistent In-Memory Multitasking*.
2. **Eliminasi Overhead:** Dengan mempertahankan aplikasi tetap ter-bootstrap di memori, framework overhead berkurang drastis, memungkinkan PHP mencapai performa microsecond dan throughput puluhan ribu request per detik.
3. **Mekanika Konkurensi:** PHP 8.1+ Fibers menyediakan primitive stackful suspension cooperative multitasking native, yang jika dikombinasikan dengan I/O Multiplexing (Reactor pattern berbasis epoll) menghasilkan kapabilitas non-blocking sekelas Go (Goroutine) atau Node.js (Event Loop).
4. **Tanggung Jawab State Isolation:** Kecepatan tinggi menuntut disiplin tingkat tinggi. Developer harus bertanggung jawab penuh terhadap memory allocation lifecycle: membersihkan DI container, melarang global state yang mutable, mencegah memory leaks dari circular references, dan memastikan database connection pool terisolasi rapi antar coroutine context.