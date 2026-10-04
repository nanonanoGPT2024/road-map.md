# BAB 09: ADVANCED CONCURRENCY & MODERN RUNTIMES
## MODUL 01: High-Performance Runtimes & Asynchronous Processing

---

### SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum**: 02-Programming-Languages / PHP
* **Kode Modul**: PHP-ADV-0901
* **Level Kompleksitas**: Advanced (Level 4/4)
* **Prasyarat Pengetahuan**:
  * Pemahaman mendalam lifecycle PHP-FPM (*Request-Response Lifecycle*).
  * Penguasaan OOP PHP 8.2+ (*Strict Typing*, *Anonymous Classes*, *WeakMap*, *Generators*).
  * Pemahaman dasar sistem operasi: *Process*, *Thread*, *Non-blocking I/O*, *System Calls* (`epoll`/`kqueue`), dan *File Descriptors*.
  * Manajemen dependensi via Composer dan arsitektur PSR-7/PSR-15.
* **Tech Stack**:
  * PHP 8.2+ / PHP 8.3 CLI
  * Spiral RoadRunner v2023.x / v2024.x (Go-powered application server)
  * Swoole 5.x / OpenSwoole 22.x
  * Revolt PHP (Event Loop engine standar PHP) & Amp v3
  * Native PHP `Fiber` Engine

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Mendekonstruksi** keterbatasan model arsitektur *Shared-Nothing* pada PHP-FPM dan mengidentifikasi bottleneck I/O-bound pada sistem konkurensi tinggi.
2. **Menganalisis dan Memilih** antara arsitektur Server Eksternal (RoadRunner) dan Extension-Level Engine (Swoole) berdasarkan trade-off operasional, keamanan, dan portabilitas kode.
3. **Mengimplementasikan** asynchronous non-blocking workflow menggunakan native PHP `Fiber` dan Revolt Event Loop secara aman tanpa memblokir thread eksekusi utama.
4. **Mencegah dan Menanggulangi** *State Pollution*, *Memory Leaks*, dan *Connection Starvation* pada lingkungan *Long-Running PHP Process*.
5. **Membangun** pipeline pemrosesan HTTP dengan throughput tinggi yang mempertahankan konsistensi data per-request menggunakan *Context Isolation* dan *Connection Pooling*.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

#### Paradigma Klasik: Shared-Nothing (PHP-FPM)
Selama lebih dari dua dekade, mental model developer PHP terpaku pada paradigma *Shared-Nothing*:
1. Web server (Nginx/Apache) menerima request HTTP.
2. Request diteruskan ke worker pool PHP-FPM via FastCGI.
3. Worker PHP menginisialisasi seluruh runtime: meng-compile/memuat file (meski ada OPcache), menginisialisasi framework, dependensi, koneksi database, dan variabel global.
4. Request diproses, respons dikirimkan.
5. **Seluruh memori dibersihkan (Garbage Collected)**, state di-destroy, koneksi ditutup atau dikembalikan.

Model ini sangat aman (tidak ada kebocoran state antar-request) dan fault-tolerant (fatal error pada satu request tidak mempengaruhi request lain). Namun, memiliki inefisiensi masif: *bootstrap overhead* terjadi berulang kali, dan ketika terjadi operasi I/O (akses database, HTTP call pihak ketiga), worker PHP berada dalam status *blocked* (idle menunggu socket I/O OS), membuang-buang siklus CPU dan slot worker.

#### Paradigma Modern: Long-Running & Asynchronous Co-operative
Mental model *High-Performance PHP* mengubah eksekusi skrip menjadi server aplikasi permanen di memori:
* **Bootstrapping Sekali**: Framework, container dependensi, routing, dan ORM metadata dimuat ke memori saat server dinyalakan (*server boot*).
* **Eksekusi Berulang**: Worker tetap hidup (*long-running process*). Satu worker melayani puluhan ribu request berturut-turut tanpa mengulang fase bootstrap.
* **Non-Blocking I/O & Event Loop**: Ketika I/O terjadi, worker tidak berhenti. Melalui abstraksi *Fibers* atau *Coroutines*, kontrol eksekusi diserahkan kembali (*yield*) ke Event Loop, memungkinkan thread yang sama mengeksekusi request lain sambil menunggu paket data I/O tiba di level OS kernel (`epoll`/`kqueue`).
* **Kebutuhan Disiplin Ekstrem**: Karena worker tidak mati, kebocoran memori (uncleaned static array, dangling event listeners) dan kontaminasi state (menyimpan data user A pada static property yang kemudian terbaca oleh user B) menjadi ancaman fatal nomor satu.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

#### 1. Perbandingan Model PHP-FPM vs Long-Running Runtimes

```
=== ARSITEKTUR 1: PHP-FPM (Tradisional) ===
Client -> Nginx -> FastCGI -> [FPM Pool] -> Spawn/Assign Worker
                                              |-- Bootstrap Engine & App
                                              |-- Parse Router & DI
                                              |-- Execute & BLOCK on DB Query (Idle)
                                              |-- Flush Output Buffer
                                              +-- TEAR DOWN / FREE ALL MEMORY

=== ARSITEKTUR 2: RoadRunner (Hybrid Go + PHP CLI) ===
Client -> [RoadRunner Server (Go)] 
               | (Goroutines handle TCP/HTTP concurrency non-blocking)
               | (Distributes via IPC: Unix Domain Sockets / Pipes)
               v
         [PHP Worker 1 (CLI)] -> Bootstrap ONCE -> Loop: [Receive Request -> Process -> Send Response]
         [PHP Worker 2 (CLI)] -> Bootstrap ONCE -> Loop: [Receive Request -> Process -> Send Response]
         [PHP Worker N (CLI)] -> Bootstrap ONCE -> Loop: [Receive Request -> Process -> Send Response]

=== ARSITEKTUR 3: Swoole / OpenSwoole (In-Process Coroutines Engine) ===
Client -> [Swoole Master Process]
               |
               v (Reactor Threads - Non-Blocking epoll)
          [Swoole Manager Process]
               |
               v (Spawns & Monitors)
          [Worker Process 1] <--- Non-blocking Coroutine Scheduler (Single Thread, Multi-Task)
             |-- Coroutine A: DB Read (Suspended on I/O)
             |-- Coroutine B: HTTP Call (Suspended on I/O)
             +-- Coroutine C: Compute Hash (Executing on CPU)
```

#### 2. Siklus Hidup Eksekusi Fiber / Coroutine dalam Event Loop

```
+-------------------------------------------------------------------------+
|                              EVENT LOOP                                 |
|                                                                         |
|  [Poll OS I/O: epoll_wait() / kqueue()] <---+                           |
|        |                                    |                           |
|        v (Events Ready: Socket Readable)    | (No events or idle)       |
|  [Scheduler / Ready Queue]                  |                           |
|        |                                    |                           |
|        v Pick Next Runnable Task            |                           |
|  +--------------------+                     |                           |
|  | Fiber / Coroutine  |                     |                           |
|  | Execution Context  |                     |                           |
|  +--------------------+                     |                           |
|        |                                    |                           |
|        |-- Task Running...                  |                           |
|        |-- Encounters Non-Blocking I/O      |                           |
|        v                                    |                           |
|  [Fiber::suspend()] ------------------------+                           |
|     (Registers socket to Event Loop & Yields execution)                 |
+-------------------------------------------------------------------------+
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. Mekanisme Event Loop & I/O Multiplexing
Pada level kernel OS, I/O multiplexing dilakukan melalui system call seperti `epoll` (Linux) atau `kqueue` (macOS/BSD). Event Loop memetakan *File Descriptors* (FD) dari socket jaringan ke sebuah registry:
* Socket ditandai sebagai `O_NONBLOCK`.
* Operasi read/write tidak akan mem-pause CPU thread. Jika buffer kosong, syscall langsung menghasilkan nilai error `EAGAIN` atau `EWOULDBLOCK`.
* Event loop memanggil `epoll_wait()`. Thread tidur hingga kernel memberitahu bahwa data pada FD tertentu telah tiba.

#### 2. Native Fibers (PHP 8.1+)
Sebelum PHP 8.1, asynchronous execution dicapai via Generators (`yield`), yang terbatas dan memiliki masalah *function coloring* (semua fungsi pemanggil harus ikut me-yield).
* **Fibers** adalah *isolated stackful coroutines* yang dikontrol secara manual (*cooperative multitasking*).
* Berbeda dengan OS Threads, Fiber tidak memiliki kernel scheduling dan tidak berjalan paralel antar core CPU secara preemptive. Fiber berpindah konteks hanya jika diperintahkan secara eksplisit melalui `Fiber::suspend()` dan dilanjutkan via `$fiber->resume()`.
* Setiap Fiber mengalokasikan Call Stack C-level tersendiri (default 4KB hingga 2MB tergantung OS dan arsitektur), memungkinkan penundaan eksekusi di titik mana pun di dalam fungsi bersarang (*deep call stack*), bukan hanya di tingkat pemanggil pertama.

#### 3. Inter-Process Communication (IPC) pada RoadRunner
RoadRunner memisahkan arsitektur menjadi dua layer:
1. **Network Layer (Go Server)**: Bertanggung jawab menerima koneksi HTTP/gRPC, TLS termination, static file serving, dan queue handling. Go memanfaatkan goroutine yang sangat ringan (2KB per stack).
2. **Execution Layer (PHP CLI Workers)**: RoadRunner mempertahankan *pool* proses PHP CLI standar. 
3. **Goroutine-to-PHP IPC**: Komunikasi data request dan response ditransmisikan menggunakan protokol biner efisien (Goridge) melalui Unix Domain Sockets atau standard input/output (`stdin`/`stdout`). Tidak ada ekstensi C kustom yang perlu di-compile ke dalam engine PHP, menjadikannya 100% kompatibel dengan core PHP standar.

#### 4. Engine Hooking & Coroutine Scheduling pada Swoole
Swoole mengambil pendekatan invasif:
* Berjalan sebagai ekstensi native C/C++ pada Zend Engine.
* Mengganti fungsi internal libc (seperti `sleep`, `stream_select`, `curl_exec`, koneksi socket PDO) melalui *Runtime Hooking* (`Swoole\Runtime::enableCoroutine()`).
* Mengonversi operasi blocking internal PHP menjadi operasi coroutine non-blocking secara transparan di balik layar.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### 1. Masalah Concurrency: Threading vs Coroutines
* **Preemptive Multitasking (OS Threads)**: Sistem operasi mengontrol alokasi waktu CPU per thread. Context switching memerlukan peralihan dari user-space ke kernel-space, penyimpanan register CPU, dan berpotensi memicu *race condition* yang membutuhkan *mutex*, *semaphores*, atau *locks*.
* **Cooperative Multitasking (Coroutines/Fibers)**: Task berjalan hingga secara sukarela menyerahkan kontrol (*yield*). Karena context switch sepenuhnya terjadi di user-space dan task tidak dapat disela di tengah operasi komputasi sinkronus, race conditions terkait modifikasi variabel dalam satu tick loop menjadi tereliminasi, tanpa overhead locking OS.

#### 2. Lifecycle Global State & Bahaya Memory Leaks
Dalam PHP-FPM, memory leak minor kerap diabaikan karena saat request selesai, Zend Engine menjalankan `zend_bailout()` dan membersihkan heap memori secara menyeluruh (`request_shutdown`).

Dalam runtime *Long-Running*:
```
+----------------------------------------------------+
| Application Boot (Load Classes, Services, Config)  |
+----------------------------------------------------+
                          |
                          v
        +-----------------------------------+
  +---->| Loop: Wait for Inbound Request    |
  |     +-----------------------------------+
  |                       |
  |                       v
  |     +-----------------------------------+
  |     | Handle Request in Isolated Scope  |
  |     +-----------------------------------+
  |                       |
  |                       v
  |     +-----------------------------------+
  |     | Clean Per-Request Memory State    |
  |     +-----------------------------------+
  |                       |
  +-----------------------+
```

Jika aplikasi menambahkan objek ke dalam array global atau static:
```php
class MetricsCollector {
    public static array $history = []; // BERBAHAYA!
}
```
Setiap request yang mengeksekusi `MetricsCollector::$history[] = $requestData;` akan menumpuk memori di RAM server. Setelah ratusan ribu request, memori habis (*Out-Of-Memory / OOM Crash*).

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi non-blocking concurrent task runner menggunakan native PHP 8.2+ `Fiber` yang digerakkan oleh event loop sederhana berbasis `stream_select`.

```php
<?php

declare(strict_types=1);

namespace Architecture\AsyncEngine;

/**
 * EventLoop sederhana untuk mendemonstrasikan cooperative multitasking
 * menggunakan native PHP Fiber tanpa dependency eksternal.
 */
final class SimpleEventLoop
{
    /** @var array<int, \Fiber> */
    private array $fibers = [];

    /** @var array<int, resource> */
    private array $readStreams = [];

    /** @var array<int, \Fiber> */
    private array $streamCallbacks = [];

    public function defer(\Fiber $fiber): void
    {
        $this->fibers[] = $fiber;
    }

    public function addReadStream($stream, \Fiber $fiber): void
    {
        $id = (int)$stream;
        $this->readStreams[$id] = $stream;
        $this->streamCallbacks[$id] = $fiber;
    }

    public function run(): void
    {
        // Jalankan seluruh fiber awal hingga suspend pertama
        foreach ($this->fibers as $key => $fiber) {
            $fiber->start();
            unset($this->fibers[$key]);
        }

        // Loop multiplexing I/O
        while (!empty($this->readStreams)) {
            $read = $this->readStreams;
            $write = null;
            $except = null;

            // Block hanya sampai ada stream yang ready (atau timeout)
            $readyCount = stream_select($read, $write, $except, 0, 200_000);

            if ($readyCount === false) {
                throw new \RuntimeException("Kegagalan pada stream_select()");
            }

            if ($readyCount > 0) {
                foreach ($read as $stream) {
                    $id = (int)$stream;
                    $fiber = $this->streamCallbacks[$id];

                    unset($this->readStreams[$id], $this->streamCallbacks[$id]);

                    // Bangunkan kembali Fiber yang menunggu I/O
                    if ($fiber->isSuspended()) {
                        $fiber->resume($stream);
                    }
                }
            }
        }
    }
}

/**
 * Fungsi utilitas untuk HTTP fetching non-blocking menggunakan Fiber
 */
function asyncHttpGet(SimpleEventLoop $loop, string $host, int $port, string $path): \Fiber
{
    return new \Fiber(function () use ($loop, $host, $port, $path): string {
        $socket = @stream_socket_client(
            "tcp://{$host}:{$port}",
            $errorCode,
            $errorMessage,
            5.0,
            STREAM_CLIENT_ASYNC_CONNECT | STREAM_CLIENT_CONNECT
        );

        if (!$socket) {
            throw new \RuntimeException("Koneksi gagal: {$errorMessage} ({$errorCode})");
        }

        stream_set_blocking($socket, false);

        $request = "GET {$path} HTTP/1.1\r\nHost: {$host}\r\nConnection: close\r\n\r\n";
        fwrite($socket, $request);

        // Suspend eksekusi fiber sampai kernel OS menandai socket ready to read
        $loop->addReadStream($socket, \Fiber::getCurrent());
        \Fiber::suspend();

        // Eksekusi berlanjut di sini saat resume dipanggil oleh loop
        $response = '';
        while (!feof($socket)) {
            $buffer = fread($socket, 8192);
            if ($buffer !== false) {
                $response .= $buffer;
            }
        }
        fclose($socket);

        return $response;
    });
}

// === RUNTIME EXECUTION ===
$loop = new SimpleEventLoop();

echo "[" . date('H:i:s') . "] Memulai concurrent non-blocking HTTP calls...\n";

$f1 = asyncHttpGet($loop, 'example.com', 80, '/');
$f2 = asyncHttpGet($loop, 'httpbin.org', 80, '/get');

$loop->defer($f1);
$loop->defer($f2);

$loop->run();

echo "[" . date('H:i:s') . "] Selesai mengeksekusi seluruh Fiber secara non-blocking.\n";
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis implementasi `SimpleEventLoop` dan native `Fiber`:

1. **Baris 24-28 (`addReadStream`)**:
   Mendaftarkan socket resource ke dalam watch-list event loop, dipetakan langsung dengan instance `Fiber` yang saat ini sedang aktif dan ditangguhkan.
2. **Baris 33-36 (`run - initial loop`)**:
   Mengeksekusi `$fiber->start()`. Ini menginisialisasi call-stack terpisah untuk setiap fiber. Kode berjalan hingga menemui instruksi penangguhan (`Fiber::suspend()`).
3. **Baris 45 (`stream_select($read, ...)`)**:
   Menggunakan OS system call level rendah (`select`) untuk memeriksa status file descriptor socket. Parameter timeout diatur sebesar `200_000` mikrodetik (0.2 detik). Operasi ini melepaskan kontrol CPU secara efisien tanpa *busy waiting*.
4. **Baris 58-60 (`$fiber->resume($stream)`)**:
   Ini adalah esensi dari *Cooperative Multitasking*. Ketika kernel menyatakan bahwa paket TCP telah tiba pada socket buffer, Event Loop me-restore konteks eksekusi Fiber tepat di mana ia berhenti.
5. **Baris 78 (`stream_set_blocking($socket, false)`)**:
   Instruksi krusial yang mengonfigurasi file descriptor socket ke mode non-blocking. Syscall I/O apa pun pada resource ini akan langsung kembali seketika tanpa menahan proses worker.
6. **Baris 85 (`\Fiber::suspend()`)**:
   Menghentikan eksekusi di tengah fungsi `asyncHttpGet`. Seluruh status frame memori, pointer instruksi lokal, dan variabel tetap terjaga di stack memory Fiber, sementara alur kontrol program kembali ke `SimpleEventLoop::run()`.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario: Payment Gateway Webhook Receiver & Dispatcher
Sebuah platform fintech memproses webhook dari 50+ payment provider secara global. 
* **Beban Traffic**: 4.000 request per detik (RPS) pada jam sibuk.
* **Karakteristik Pekerjaan**:
  1. Menerima payload JSON webhook.
  2. Memverifikasi HMAC SHA-256 signature secara CPU-bound (cepat: < 1ms).
  3. Menyimpan raw payload ke Database/S3 (I/O-bound: ~35ms latency).
  4. Menerbitkan event ke Apache Kafka / RabbitMQ (I/O-bound: ~15ms latency).
  5. Mengembalikan response HTTP `200 OK` ke provider.

#### Masalah pada PHP-FPM
Dengan arsitektur PHP-FPM:
* Setiap request menghabiskan waktu total ~51ms.
* Satu worker FPM hanya dapat memproses: $1000\text{ms} / 51\text{ms} \approx 19.6 \text{ RPS}$.
* Untuk melayani 4.000 RPS, sistem memerlukan: $4000 / 19.6 \approx 204$ concurrent worker PHP-FPM aktif.
* Jika alokasi RAM per FPM worker adalah ~35MB, maka konsumsi RAM server mencapai: $204 \times 35\text{MB} \approx 7.14\text{GB}$ murni hanya untuk worker yang sebagian besar statusnya adalah *idle waiting* socket I/O. Begitu terjadi lonjakan latensi pada Kafka (misal Kafka naik menjadi 200ms), FPM pool langsung mengalami *exhaustion* (502 Bad Gateway).

#### Solusi Arsitektural: RoadRunner Worker Pool + State Isolation
Mengganti runtime execution layer menggunakan **RoadRunner Worker Pool**. Hanya dibutuhkan 8-16 permanent worker PHP (disesuaikan dengan jumlah core CPU) yang menangani stream data tanpa bootstrap ulang. Latensi bootstrap tereduksi menjadi 0ms, konsumsi memori konstan, dan throughput meningkat hingga 400-600% pada hardware yang sama.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi production-ready untuk Worker RoadRunner yang menangani request secara resilient, mengelola per-request state isolation, dan memproses request secara clean.

#### 1. Konfigurasi RoadRunner (`.rr.yaml`)
```yaml
version: "3"

server:
  command: "php worker.php"
  relay: "pipes"

http:
  address: "0.0.0.0:8080"
  max_request_size: 10
  pool:
    num_workers: 8
    max_jobs: 5000 # Restart worker setelah 5000 request untuk mitigasi memory leaks
    allocate_timeout: 60s
    destroy_timeout: 60s

logs:
  mode: production
  level: warn
  encoding: json
```

#### 2. Implementasi Worker Application (`worker.php`)
```php
<?php

declare(strict_types=1);

use Nyholm\Psr7\Response;
use Nyholm\Psr7\Factory\Psr17Factory;
use Spiral\RoadRunner\Worker;
use Spiral\RoadRunner\Http\PSR7Worker;

require_once __DIR__ . '/vendor/autoload.php';

/**
 * ContextContainer: Mengisolasi dependensi dan state yang hanya berlaku per satu request.
 * Mencegah kebocoran data antar transaksi (State Contamination).
 */
final class RequestContext
{
    private static ?self $current = null;

    public function __construct(
        public readonly string $traceId,
        public readonly float $startTime
    ) {}

    public static function setCurrent(?self $context): void
    {
        self::$current = $context;
    }

    public static function get(): self
    {
        if (self::$current === null) {
            throw new \RuntimeException("Tidak ada active execution context.");
        }
        return self::$current;
    }
}

/**
 * Service pemrosesan webhook (Stateless Singleton)
 */
final readonly class WebhookProcessor
{
    public function __construct(
        private string $secretKey
    ) {}

    public function process(string $signature, string $payload): bool
    {
        // CPU-bound Signature Verification
        $computed = hash_hmac('sha256', $payload, $this->secretKey);
        
        if (!hash_equals($computed, $signature)) {
            return false;
        }

        // Simulasi non-blocking publish ke internal broker / database storage
        // Pada production nyata, gunakan asynchronous client driver
        return true;
    }
}

// === BOOTSTRAP FASE (Hanya berjalan SATU KALI saat worker di-spawn) ===
$psr17Factory = new Psr17Factory();
$worker = Worker::create();
$psr7Worker = new PSR7Worker($worker, $psr17Factory, $psr17Factory, $psr17Factory);

$processor = new WebhookProcessor(getenv('WEBHOOK_SECRET') ?: 'default-secret-key');

// === EVENT LOOP REQUEST WORKER ===
while (true) {
    try {
        $request = $psr7Worker->waitRequest();
        
        if ($request === null) {
            // Worker diberhentikan oleh master supervisor RoadRunner (Graceful Shutdown)
            break;
        }
    } catch (\Throwable $e) {
        $psr7Worker->respond(new Response(400, [], 'Bad Request Protocol'));
        continue;
    }

    // Inisialisasi Context Baru untuk Request Ini
    $traceId = $request->getHeaderLine('X-Trace-ID') ?: bin2hex(random_bytes(16));
    RequestContext::setCurrent(new RequestContext($traceId, microtime(true)));

    try {
        $signature = $request->getHeaderLine('X-Signature-SHA256');
        $body = (string)$request->getBody();

        if (empty($signature) || empty($body)) {
            $response = new Response(400, ['Content-Type' => 'application/json'], json_encode([
                'error' => 'Missing signature or payload',
                'trace_id' => $traceId
            ], JSON_THROW_ON_ERROR));
            
            $psr7Worker->respond($response);
            continue;
        }

        $isValid = $processor->process($signature, $body);

        if (!$isValid) {
            $response = new Response(401, ['Content-Type' => 'application/json'], json_encode([
                'error' => 'Invalid HMAC signature',
                'trace_id' => $traceId
            ], JSON_THROW_ON_ERROR));
            
            $psr7Worker->respond($response);
            continue;
        }

        // Berhasil memproses webhook
        $response = new Response(200, ['Content-Type' => 'application/json'], json_encode([
            'status' => 'acknowledged',
            'trace_id' => $traceId
        ], JSON_THROW_ON_ERROR));

        $psr7Worker->respond($response);

    } catch (\Throwable $e) {
        // Tangkap fatal exception tanpa membunuh worker process
        $errorPayload = json_encode([
            'error' => 'Internal Processing Error',
            'trace_id' => $traceId
        ], JSON_THROW_ON_ERROR);

        $psr7Worker->respond(new Response(500, ['Content-Type' => 'application/json'], $errorPayload));
    } finally {
        // === CRITICAL CLEANUP: Wajib membersihkan context state ===
        RequestContext::setCurrent(null);

        // Jika terdeteksi akumulasi memori mendekati ambang batas tertentu, paksa restart
        if (memory_get_usage(true) > 64 * 1024 * 1024) { // 64MB Threshold
            $worker->stop();
            break;
        }
    }
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Arsitektur | PHP-FPM Tradisional | Spiral RoadRunner | Swoole / OpenSwoole | Amp / Revolt (Pure PHP) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Shared-Nothing (Spawn-Die) | Long-Running Worker Pool | Long-Running In-Engine Coroutine | Single-Thread Event Loop |
| **Kebutuhan Ekstensi C** | Standar (Tidak butuh) | Standar (Zero Extension) | **Wajib** (Ekstensi C++ compiled) | Standar (Ekstensi `ev`/`uv` opsional) |
| **Isolation Data** | Sempurna (Kernel cleanup) | Disiplin Manual (Worker boundary) | Disiplin Manual Ekstrem (Coroutine boundary) | Disiplin Manual Ekstrem |
| **Debugging Complexity**| Sangat Rendah (Xdebug native) | Rendah (Standard CLI debug) | Tinggi (Hooked call-stacks) | Moderat |
| **Non-blocking I/O** | Tidak Ada (I/O Blocking) | Pada Server Layer (Go), PHP Sync | Penuh via Transparent Coroutine Hook | Penuh via Promise/Fiber Loop |
| **Throughput (RPS)** | Baseline ($1\times$) | Tinggi ($3\times - 5\times$) | Sangat Tinggi ($5\times - 10\times$) | Tinggi ($3\times - 4\times$) |
| **Memory Leak Risk** | Hampir Nol | Rendah (Mitigasi by max-jobs) | Tinggi (Wajib profiling berkala) | Tinggi (Perlu manajemen referensi) |

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. Static Property Contamination
Dalam aplikasi modular, programmer sering menyimpan state context di static class:
```php
class AuthContext {
    public static ?User $user = null;
}
```
Pada request pertama: User A login, `AuthContext::$user = UserA`. Jika programmer lupa me-reset variable ini pada blok `finally`, request berikutnya dari User B pada worker yang sama akan mewarisi instance `UserA`. Ini adalah celah keamanan kategoris **Critical Data Leakage**.

#### 2. Open File Descriptors & Socket Leaks
Jika membuka resource file atau connection stream tanpa membungkusnya dalam safe block:
```php
$fp = fopen('/var/log/custom.log', 'a');
// Exception terjadi di sini...
// fclose($fp) terlewati!
```
Pada PHP-FPM, resource ditutup otomatis di akhir request. Pada long-running runtime, file descriptor tetap open. Sistem operasi memiliki batas maksimum open files per process (`ulimit -n`). Worker akan mengalami crash fatal `Too many open files`.

#### 3. Database Connection Dropping (MySQL Has Gone Away)
Karena worker hidup dalam hitungan hari/minggu, koneksi PDO yang di-cache di dalam Dependency Injection Container akan idle jika tidak ada traffic (misalnya tengah malam). Timeout internal MySQL (`wait_timeout`, default 8 jam) akan memutus TCP connection secara sepihak. Saat request baru masuk, query gagal dengan pesan: `PDOException: MySQL server has gone away`. Solusinya adalah penggunaan *Connection Pool* dengan health-check *ping* sebelum penggunaan.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Kesalahan 1: Menggunakan Fungsi Sinkronus Pemblokir Eksekusi (Blocking Calls)
```php
// SALAH (Mengunci SELURUH Event Loop atau Coroutine Scheduler):
sleep(5); 

// BENAR (Revolt Event Loop / Fiber context):
\Revolt\EventLoop::delay(5.0, static function (): void {
    // Callback dieksekusi setelah 5 detik, worker tetap memproses hal lain selama 5 detik
});

// BENAR (Swoole context dengan Runtime Hook aktif):
\Swoole\Coroutine::sleep(5);
```

#### Kesalahan 2: Mengasumsikan `superglobals` ($_GET, $_POST, $_SERVER) Selalu Terisi
Pada RoadRunner atau Swoole HTTP Server, variabel `$_SERVER`, `$_GET`, dan `$_POST` tidak diisi secara otomatis untuk setiap request masuk kecuali diaktifkan secara eksplisit via compatibility flags.
* **Solusi**: Tinggalkan sepenuhnya variabel superglobal. Migrasikan seluruh kode ke abstraksi antarmuka **PSR-7 (HTTP Message Interface)** (`ServerRequestInterface`).

#### Kesalahan 3: Circular References pada Event Listeners
Menyimpan callable closure yang menangkap instance objek `$this` ke dalam listener global tanpa pembersihan:
```php
class ReportGenerator {
    public function register(): void {
        GlobalDispatcher::addListener('generate', function() {
            $this->doSomething(); // Circular reference!
        });
    }
}
```
Objek `ReportGenerator` tidak akan pernah bisa di-destruct oleh Zend GC engine karena `GlobalDispatcher` memegang referensi kuat ke closure. Gunakan `WeakReference` atau deregister listener secara eksplisit.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Reset Interfaces pada Dependency Injection Containers**:
   Pastikan framework atau container mengimplementasikan `ResetInterface` (tersedia secara native di Symfony/Laravel modern).
   ```php
   interface ResettableService
   {
       public function reset(): void;
   }
   ```
   Panggil pembersihan ini pada event listener worker setelah `$worker->respond()`.

2. **Batasi Masa Hidup Worker (Recycling Strategy)**:
   Jangan pernah membiarkan satu proses worker hidup selamanya tanpa batas request. Konfigurasi `max_jobs: 2000` atau `max_requests: 5000` pada layer supervisor (RoadRunner/Swoole). Ini merupakan strategi *defense-in-depth* terbaik untuk membersihkan alokasi memori C-level internal yang bocor tipis.

3. **Immutable Request/Response Pattern**:
   Gunakan arsitektur PSR-7/PSR-15 Middleware pipeline yang stateless. Controller dan handler tidak boleh memiliki mutable instance properties. Objek service harus murni berperilaku sebagai operasi behavior (*Pure Services*).

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

#### 1. Implementasi Database Connection Pool
Membuka koneksi database baru setiap request membutuhkan TCP Handshake 3-way, SSL Negotiation, dan Otentikasi (~10-20ms). Pada long-running runtime, kita mempertahankan sekelompok koneksi aktif (*Connection Pool*):

```php
<?php

declare(strict_types=1);

namespace Architecture\Database;

final class SimpleConnectionPool
{
    /** @var \SplQueue<\PDO> */
    private \SplQueue $pool;
    private int $currentSize = 0;

    public function __construct(
        private readonly string $dsn,
        private readonly string $user,
        private readonly string $password,
        private readonly int $maxSize = 10
    ) {
        $this->pool = new \SplQueue();
    }

    public function acquire(): \PDO
    {
        if (!$this->pool->isEmpty()) {
            $pdo = $this->pool->dequeue();
            // Lakukan quick verification bahwa connection masih hidup
            try {
                $pdo->query('SELECT 1');
                return $pdo;
            } catch (\PDOException) {
                // Koneksi mati, discard dan biarkan logic di bawah membuat yang baru
                $this->currentSize--;
            }
        }

        if ($this->currentSize < $this->maxSize) {
            $this->currentSize++;
            return new \PDO($this->dsn, $this->user, $this->password, [
                \PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION,
                \PDO::ATTR_PERSISTENT => false
            ]);
        }

        throw new \RuntimeException("Connection pool exhausted.");
    }

    public function release(\PDO $pdo): void
    {
        $this->pool->enqueue($pdo);
    }
}
```

#### 2. OPcache Preloading
Kombinasikan runtime long-running dengan OPcache Preloading pada `php.ini`:
```ini
opcache.enable=1
opcache.enable_cli=1
opcache.preload=/var/www/html/preload.php
opcache.preload_user=www-data
```
Preloading akan meng-compile seluruh source code file, me-resolve dependensi class, dan menempatkan struktur data internal class langsung ke dalam shared memory yang immutable sebelum kode apapun dieksekusi. Hasilnya: nol overhead kompilasi opcodes selama server berjalan.

---

### SEKSI 16 — KEAMANAN & HARDENING

#### 1. Pencegahan Cross-Request Pollution Attack
Ketika data user disimpan di class non-stateless, penyerang dapat secara sengaja mengirimkan request berukuran raksasa atau memicu fatal error di tengah eksekusi untuk mengganggu eksekusi request milik user lain yang antre di worker yang sama.
* **Mitigasi**: Selalu gunakan mekanisme try-finally di tingkatan terluar loop worker:
```php
try {
    $this->handle($request);
} finally {
    // Isolasi tereksekusi bahkan jika ada Exception yang tidak tertangkap
    $this->cleanSecurityContext();
}
```

#### 2. Mitigasi Uncontrolled Crash Propagation
Jika worker mengalami unhandled Fatal Error atau `exit()` / `die()`, runtime eksternal (RoadRunner) harus dikonfigurasi agar secara otomatis melakukan isolasi kerusakan:
* Worker yang mati harus segera di-spawn ulang oleh supervisor tanpa mendowntime-kan web server.
* Jangan pernah memanggil fungsi `exit()` atau `die()` di dalam kode aplikasi yang berjalan di lingkungan long-running runtime. Menggunakan `exit` akan langsung mematikan seluruh proses worker CLI.

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

#### 1. Contextual Tracing dengan Coroutine / Fiber Context
Dalam lingkungan paralel/konkuren, sequential logging tradisional menjadi tidak berguna karena log dari berbagai request yang masuk secara bersamaan akan saling bercampur aduk (*interleaved*).

Gunakan Unique Trace ID yang disuntikkan ke Log Record:
```php
$logger->info("Memproses pembayaran", [
    'trace_id' => RequestContext::get()->traceId,
    'execution_time_ms' => (microtime(true) - RequestContext::get()->startTime) * 1000
]);
```

#### 2. Profiling Memory Leak menggunakan WeakMap
Untuk mendeteksi apakah instance controller atau model tidak berhasil dibersihkan oleh Garbage Collector:
```php
final class LeakDetector
{
    /** @var \WeakMap<object, string> */
    private static \WeakMap $registry;

    public static function init(): void {
        self::$registry = new \WeakMap();
    }

    public static function track(object $object, string $tag): void {
        self::$registry[$object] = $tag;
    }

    public static function dumpActiveCount(): int {
        return count(self::$registry);
    }
}
```
Karena `WeakMap` tidak meningkatkan hitungan *Reference Counter* (zval refcount) dari objek, jika objek tersebut berhasil di-garbage-collect, objek tersebut otomatis terhapus dari `WeakMap`. Jika count terus naik seiring waktu, Anda berhasil mendeteksi memory leak.

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

* **PHP-FPM**: Bersih, aman, shared-nothing, namun boros CPU/RAM untuk bootstrap I/O-bound concurrency.
* **RoadRunner**: Arsitektur hybrid terbaik. Engine HTTP berbasis Go super cepat + Worker Pool native PHP CLI tanpa ekstensi rumit. Kompatibel dengan 99% ekosistem PHP.
* **Swoole**: Runtime paling kuat untuk performa absolut. Mengubah internal engine PHP menjadi async coroutine event-driven, tetapi memiliki footprint kompleksitas paling tinggi dan membutuhkan ekstensi C++.
* **Fiber (PHP 8.1+)**: Komponen primitif native PHP untuk cooperative multitasking. Membutuhkan Event Loop Scheduler (misal: Revolt) untuk eksekusi non-blocking yang nyata.

#### Aturan Emas Long-Running PHP:
1. **DILARANG** menyimpan state request di properti static atau singleton service.
2. **DILARANG** menggunakan pemanggil blocking seperti `sleep()`, gunakan async timer.
3. **DILARANG** memanggil `exit()` atau `die()`.
4. **SELALU** bersihkan context per-request di blok `finally`.
5. **KONFIGURASIKAN** `max_jobs` pada worker supervisor untuk daur ulang memori berkala.

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Soal Basic (1 - 5)
1. **Mengapa overhead bootstrapping pada PHP-FPM menjadi bottleneck utama pada arsitektur microservices?**
   * *Jawaban*: Karena pada setiap request HTTP yang masuk, PHP-FPM harus menginisialisasi ulang seluruh dependensi framework, file parsing (OPcache hit tetap memerlukan hash-table class linking), inisialisasi IoC container, dan konfigurasi database, lalu memusnahkannya secara total setelah response dikirim.

2. **Apakah native PHP `Fiber` dapat menjalankan dua task secara paralel pada dua CPU core berbeda secara bersamaan?**
   * *Jawaban*: Tidak. `Fiber` adalah stackful *coroutine* berbasis *cooperative multitasking*. Fiber berjalan secara konkuren pada satu single-thread CPU dan hanya berpindah eksekusi saat programmer memanggil `Fiber::suspend()` secara sukarela.

3. **Apa fungsi dari IPC (Inter-Process Communication) pada RoadRunner?**
   * *Jawaban*: Sebagai jembatan komunikasi transfer data request/response berkecepatan tinggi antara server Go (yang menangani networking HTTP) dengan sekumpulan worker process PHP CLI melalui Unix Domain Sockets atau standard pipes (`stdin`/`stdout`).

4. **Apa yang akan terjadi jika fungsi `exit(0)` dipanggil di dalam controller aplikasi yang berjalan di atas RoadRunner?**
   * *Jawaban*: Proses worker PHP CLI yang bersangkutan akan langsung berhenti/mati. Meskipun supervisor RoadRunner akan men-spawn worker baru sebagai penggantinya, proses kematian mendadak ini membuang waktu dan berpotensi memutus request aktif yang sedang diproses oleh worker tersebut.

5. **Mengapa variabel superglobal seperti `$_GET` atau `$_POST` tidak disarankan untuk digunakan pada long-running application servers?**
   * *Jawaban*: Karena superglobals dirancang untuk lifecycle PHP-FPM tradisional. Pada long-running runtime, data request masuk direpresentasikan melalui immutable PSR-7 request objects. Superglobals seringkali tidak terisi atau dapat menyimpan sisa data dari request sebelumnya jika tidak dibersihkan secara manual.

#### Soal Intermediate (6 - 10)
6. **Jelaskan risiko penggunaan PDO persistent connection (`PDO::ATTR_PERSISTENT => true`) pada arsitektur long-running runtime dibandingkan dengan PHP-FPM!**
   * *Jawaban*: Pada long-running runtime, koneksi database sudah secara otomatis persisten di level lifecycle worker proses. Mengaktifkan `ATTR_PERSISTENT` di level driver PDO lama dapat membingungkan manajemen connection pool, menyembunyikan status kegagalan koneksi (*broken pipe*), dan mempersulit graceful connection draining saat worker di-recycle.

7. **Bagaimana cara kerja Runtime Hooking pada Swoole dalam mengubah fungsi blocking seperti `file_get_contents()` menjadi non-blocking?**
   * *Jawaban*: Swoole meng-intercept system call socket/file libc pada level C-extension engine. Ketika fungsi native PHP memanggil operasi read/write, Swoole mengalihkan operasi tersebut ke event loop epoll internal dan secara otomatis men-suspend coroutine yang aktif saat itu tanpa mengubah sintaks kode PHP user.

8. **Mengapa isolasi memory leak menggunakan `WeakMap` lebih superior dibandingkan array tracking biasa?**
   * *Jawaban*: Karena `WeakMap` tidak menambahkan reference count pada objek yang dijadikan key. Jika objek tersebut tidak lagi dirujuk di bagian aplikasi lain, Garbage Collector PHP akan langsung menghancurkannya dan entry-nya di dalam `WeakMap` akan hilang seketika, memungkinkan deteksi kebocoran memori secara akurat tanpa menahan objek di RAM.

9. **Apa perbedaan mendasar antara model Concurrency Preemptive (seperti Go Goroutines atau OS Threads) dengan Cooperative (seperti PHP Fibers)?**
   * *Jawaban*: Preemptive scheduler dapat menghentikan eksekusi sebuah task kapan saja secara paksa untuk memindahkan giliran eksekusi ke task lain, membutuhkan mekanisme thread-safety (seperti lock/mutex). Cooperative multitasking sepenuhnya menyerahkan kontrol pemindahan kepada task itu sendiri; sebuah task harus secara sukarela memanggil suspend/yield agar task lain dapat berjalan.

10. **Bagaimana mekanisme Connection Pool mengatasi masalah latensi pada interaksi Database di traffic konkurensi tinggi?**
    * *Jawaban*: Connection pool membuat dan mempertahankan sekumpulan koneksi database terbuka yang sudah terotentikasi di memori. Saat request masuk, worker cukup mengambil koneksi yang sudah siap dari antrean (*dequeue*), mengeksekusi query, dan mengembalikannya (*enqueue*), sehingga menghilangkan total latensi TCP 3-way handshake dan SSL/auth overhead pada setiap transaksi.

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Judul Proyek: "High-Throughput Parallel Stock Price Aggregator"

#### Deskripsi
Bangunlah sebuah server microservice mandiri berbasis command-line menggunakan PHP 8.2+ dan pustaka Event Loop (`revolt/event-loop` atau native `Fiber`) yang mampu mengambil harga saham secara paralel dari 5 mock endpoint REST API finansial yang berbeda tanpa memblokir I/O eksekusi.

#### Spesifikasi Kebutuhan:
1. **Non-blocking Dispatcher**: Buat class `ConcurrentFetcher` yang menerima daftar URL endpoint (simulasikan endpoint lokal menggunakan script PHP terpisah dengan fungsi `usleep` bervariasi antara 200ms hingga 1500ms).
2. **Fiber Integration**: Setiap HTTP fetch wajib dieksekusi di dalam `Fiber` terisolasi atau task Revolt terpisah.
3. **Timeout Guard**: Jika satu endpoint tidak merespons dalam waktu 800ms, gagalkan task tersebut secara individual tanpa membatalkan task lain yang sedang berjalan.
4. **Per-Request Isolation**: Pastikan setiap log agregasi memiliki UUID `batch_id` unik yang diekstraksi dari Context storage tanpa menggunakan variabel global/static mentah.
5. **Memory Profiler**: Tampilkan penggunaan memori real-time (`memory_get_usage(true)`) sebelum proses berjalan, saat memproses 100 batch berulang, dan sesudah pemrosesan selesai untuk membuktikan tidak adanya akumulasi memori liar (*zero leak validation*).

#### Kriteria Keberhasilan:
* Waktu total untuk mengambil 5 data endpoint yang masing-masing memiliki latensi rata-rata 500ms harus selesai dalam waktu total **$\le$ 600ms** (bukan sequential 2.500ms).
* Alokasi RAM delta setelah 100 kali batch processing harus berada di bawah selisih $\le 50\text{KB}$ dari alokasi awal setelah pemanggilan `gc_collect_cycles()`.