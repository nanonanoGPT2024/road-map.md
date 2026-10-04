# Bab 04: Functional Programming, Concurrency, & Memory Management
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Internal Zend Engine Memory Manager (Zend MM):** Membedah struktur internal `zval`, mekanisme *reference counting*, algoritma penanganan siklus referensi (*Cycle Collector*), serta alokasi memori pada level C runtime.
2. **Menguasai Arsitektur Konkurensi Modern PHP:** Mengimplementasikan orkestrasi konkurensi berbasis *cooperative multitasking* menggunakan PHP *Fibers* (PHP 8.1+) dan membedakannya secara arsitektural dari *Event-Loop userland* (Revolt/Amp, ReactPHP) serta runtime persistent (Swoole, RoadRunner, FrankenPHP).
3. **Menerapkan Paradigma Pemrograman Fungsional Tingkat Lanjut:** Mengonstruksi pipeline komputasi bebas efek samping (*pure functions*, *immutability*, *currying*, *monadic composition*) dengan memanfaatkan fitur modern seperti `readonly class`, *first-class callables*, dan struktur data persisten.
4. **Mencegah & Menangani Memory Leaks pada Long-Running Process:** Mengaudit, mendeteksi, dan mengeliminasi kebocoran memori mikro pada daemon/worker batch enterprise melalui instrumentasi profil memori, pengelolaan siklus hidup variabel, serta optimasi Garbage Collection (GC).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Arsitektur runtime PHP standar (lifecycle Request-Response PHP-FPM).
* Pointer dan alokasi memori dasar (pemahaman konseptual Stack vs Heap).
* Fitur modern PHP 8.0 - 8.3 (`match`, typed properties, `readonly`, generators).
* Penggunaan CLI dasar, debugging dengan Linux profiling tool (`strace`), dan konfigurasi `php.ini`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Anatomi Zend Memory Manager (Zend MM) & `zval`

PHP mengeksekusi kode di atas Zend Engine. Di level terendah, engine tidak memanggil alokator sistem operasi (`malloc`/`free`) secara langsung untuk setiap variabel, melainkan menggunakan layer abstraksi: **Zend Memory Manager (Zend MM)**. Zend MM mengalokasikan blok memori besar (*chunks*, tipikal 2MB) dari OS dan membaginya ke dalam *pages* (4KB) dan *slots* untuk meminimalkan *system call overhead* dan fragmentasi memori.

Setiap variabel di PHP direpresentasikan oleh struktur C bernama `zval` (Zend Value). Pada PHP 7 dan 8, ukuran `zval` dioptimasi menjadi **16 bytes** pada arsitektur 64-bit:

```c
struct _zval_struct {
    zend_value        value; // 8 bytes: union untuk integer, double, pointer ke object/string/array
    union {
        struct {
            ZEND_ENDIAN_LOHI_3(
                zend_uchar    type,         // Tipe data: IS_UNDEF, IS_STRING, IS_ARRAY, IS_OBJECT, dll.
                zend_uchar    type_flags,   // Flag konstanta, refcounted, immutable
                union {
                    uint16_t  extra;        // Info tambahan pemrosesan internal
                } u;
            )
        } v;
        uint32_t type_info;
    } u1;
    union {
        uint32_t     next;                 // Hash collision chain
        uint32_t     cache_slot;           // Zend VM execution cache
        uint32_t     opline_num;           // Trace debugging
        uint32_t     lineno;               // Ast line
        uint32_t     num_args;             // Function argument tracking
    } u2; // 4 bytes metadata tambahan
};
```

Nilai skalar primitif (`int`, `float`, `bool`) disimpan langsung di dalam union `zend_value`. Tipe kompleks (`string`, `array`, `object`) disimpan sebagai pointer menuju struktur heap spesifik (`zend_string`, `zend_array`, `zend_object`) yang memiliki *header reference counting* (`zend_refcounted_h`).

#### 3.2 Reference Counting & The Cycle Collection Algorithm

Setiap struktur kompleks memiliki field `gc`:
```c
typedef struct _zend_refcounted_h {
    uint32_t         refcount;
    union {
        struct {
            ZEND_ENDIAN_LOHI_3(
                zend_uchar    type,
                zend_uchar    flags,
                uint16_t      gc_info
            )
        } v;
        uint32_t type_info;
    } u;
} zend_refcounted_h;
```

Mekanisme de-alokasi default adalah *Reference Counting*:
1. Ketika variabel diarahkan ke nilai kompleks, `refcount` bertambah (`refcount++`).
2. Ketika variabel keluar dari scope (`unset` atau akhir fungsi), `refcount` berkurang (`refcount--`).
3. Jika `refcount == 0`, memori langsung dibebaskan kembali ke pool Zend MM secara instan tanpa menunggu Garbage Collector.

##### Masalah Circular Reference:
Ketika Object A memiliki referensi ke Object B, dan Object B memiliki referensi balik ke Object A, lalu kedua variabel lokal yang menunjuk ke mereka di-*unset*, `refcount` keduanya tidak pernah mencapai 0 (berhenti di angka 1). Ini menyebabkan *memory leak* jika engine hanya mengandalkan reference counting murni.

##### Algoritma Synchronous Cycle Collector (Bacon & Rajan Variant):
Untuk mengatasi siklus referensi tanpa memblokir eksekusi program:
1. Ketika `refcount` dari suatu `zend_refcounted` berkurang tetapi tidak mencapai 0, Zend Engine mencurigai nilai tersebut sebagai bagian dari circular reference dan menandainya dengan warna **Purple** serta memasukkannya ke dalam **GC Roots Buffer** (kapasitas default: 10.001 elemen).
2. Jika *Roots Buffer* penuh, fungsi `gc_collect_cycles()` dipicu secara otomatis.
3. Algoritma melakukan traversal multi-tahap:
   * **Stage 1 (Mark Grey):** Engine melakukan DFS (Depth-First Search) ke seluruh child node, mengurangi refcount hipotetis sebesar 1. Node yang dikunjungi ditandai warna **Grey**.
   * **Stage 2 (Scan & Mark White/Black):** Engine memeriksa refcount hipotetis. Jika `refcount == 0`, node tersebut dipastikan dead-cycle dan ditandai **White**. Jika `refcount > 0`, refcount dikembalikan dan ditandai **Black** (alive).
   * **Stage 3 (Sweep):** Seluruh node berwarna **White** dibersihkan dan memorinya dikembalikan ke Zend MM.

#### 3.3 Concurrency: Native Fibers vs Shared-Nothing FastCGI

Tradisional PHP beroperasi dengan arsitektur **Shared-Nothing Multi-Process**: web server (seperti Nginx) meneruskan request ke PHP-FPM, di mana satu worker proses melayani tepat satu request dari awal hingga akhir, lalu seluruh memori request dibersihkan secara instan via `zend_mm_shutdown()`.

**Fibers (PHP 8.1+)** memperkenalkan primitif konkurensi native tingkat rendah: *Cooperative Multitasking* (stackful coroutines). Berbeda dengan *preemptive OS threads* yang dikontrol oleh kernel scheduler dengan overhead context switch yang tinggi, Fiber dikontrol sepenuhnya di *userland*:
* Fiber memiliki call stack C dan PHP terisolasi sendiri (default dialokasikan 4KB s.d. 8KB virtual memory).
* Ketika operasi I/O terjadi, eksekusi Fiber dapat di-`suspend()` (menyerahkan kontrol kembali ke scheduler utama/event loop).
* State stack (posisi pointer instruksi, variabel lokal, call frames) tetap tersimpan di memori hingga dieksekusi kembali via `resume()`.

---

### 4. Why & What

| Paradigma / Komponen | Mengapa Diperlukan di Enterprise? | Apa Karakteristiknya? |
| :--- | :--- | :--- |
| **Zend MM & Cycle Control** | Mencegah Out-Of-Memory (OOM) pada worker worker queue (RabbitMQ/Kafka consumer) yang memproses jutaan pesan tanpa restart. | Alokasi pool dinamis, bypass GC periodik untuk batch berkecepatan tinggi, destruksi instan. |
| **PHP Fibers** | Menangani ribuan I/O concurrent calls (external API, database reads) dalam satu proses tanpa thread racing. | Primitif stackful interruptible, zero race condition bawaan runtime, non-preemptive. |
| **Functional Immutability** | Menghilangkan *side-effects* tersembunyi pada domain enterprise yang kompleks, memastikan determinisme transaksi keuangan. | State tidak dapat dimutasi setelah inisiasi; modifikasi menghasilkan snapshot baru. |

---

### 5. How (Workflow Detail)

Alur kerja siklus hidup variabel, isolasi konkurensi Fiber, dan determinasi GC:

```
[Inisialisasi Variabel / Fiber]
              │
              ▼
    [Alokasi di Zend MM]
    - Alokasi Chunk/Page
    - Pembuatan zval (16 bytes)
    - Set Refcount = 1
              │
              ▼
   [Fiber Context Switching] 
   - Scheduler menjalankan Fiber A
   - Fiber A butuh non-blocking I/O -> Fiber::suspend()
   - Context Switch: Stack A diparkir di memory
   - Scheduler memanggil Fiber B -> Fiber B dieksekusi
              │
              ▼
   [Pembersihan / Dereferensi]
   - Variabel di-unset atau keluar scope
   - Refcount dikurangi (refcount--)
              │
       ┌──────┴──────┐
       ▼             ▼
[Refcount == 0] [Refcount > 0]
       │             │
       │             ▼
       │      [Ada potensi circular link?]
       │      ├── Tidak ──> Tetap di memory
       │      └── Ya ─────> Masuk ke GC Roots Buffer (Warna: Purple)
       ▼                    │
[Free Memory]               ▼
(Zend MM Pool)       [Roots Buffer Penuh (10.000+)?]
                            │
                     ├── Tidak ──> Tunggu
                     └── Ya ─────> Jalankan `gc_collect_cycles()`
                                   - Mark Grey
                                   - Scan White
                                   - Sweep & Free
```

---

### 6. Analogy & Diagram ASCII

#### Zend Memory Architecture:
```
+------------------------------------------------------------------------+
|                          OS VIRTUAL MEMORY                             |
|  +------------------------------------------------------------------+  |
|  |                Zend Memory Manager (Zend MM)                     |  |
|  |  +----------------------------+  +----------------------------+  |  |
|  |  |      Chunk (2MB)           |  |      Chunk (2MB)           |  |  |
|  |  | +--------+--------+--------+  | +--------+--------+--------+  |  |
|  |  | | Page 0 | Page 1 | Page n |  | | Page 0 | Page 1 | Page n |  |  |
|  |  | +--------+--------+--------+  | +--------+--------+--------+  |  |
|  |  +----------------------------+  +----------------------------+  |  |
|  +------------------------------------------------------------------+  |
+------------------------------------------------------------------------+
                                  ▲
                                  │ Mengalokasikan
+---------------------------------+--------------------------------------+
| zval (16 Bytes)                                                        |
| [Value Pointer / Scalar Value: 8B] [Type Info: 4B] [Zend VM Aux: 4B]   |
+---------------------------------+--------------------------------------+
                                  │ Menunjuk ke tipe kompleks
                                  ▼
+------------------------------------------------------------------------+
| zend_object / zend_array (Heap)                                        |
| +------------------------------------+-------------------------------+ |
| | zend_refcounted_h (GC Info: refcount, flags, color)                | |
| +------------------------------------+-------------------------------+ |
| | Properti / Payload Data Nyata                                      | |
+------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Manipulasi Refcount & Deteksi Siklus Memory

File: `simple_gc_inspect.php`
```php
<?php

declare(strict_types=1);

// Verifikasi alokasi memori internal menggunakan ekstensi opcache / standard engine info
printf("Memori Awal: %d KB\n", memory_get_usage() / 1024);

class Node
{
    public ?Node $link = null;
    public function __construct(public string $name) {}
}

// 1. Buat circular reference eksplisit
$a = new Node('Alpha');
$b = new Node('Beta');

$a->link = $b;
$b->link = $a;

// Kedua object saling mereferensikan
unset($a, $b);

// Pada titik ini, kedua object tidak dapat diakses lagi dari userland, 
// tetapi masih menempati heap karena refcount masing-masing = 1.
printf("Memori sebelum GC dijalankan: %d KB\n", memory_get_usage() / 1024);

// Paksa cycle collector bekerja
$collected = gc_collect_cycles();
printf("GC dibersihkan: %d siklus node\n", $collected);
printf("Memori setelah GC dijalankan: %d KB\n", memory_get_usage() / 1024);
```

#### 7.2 Practical Example: Enterprise Concurrent Pipeline Engine Berbasis Native Fibers

Skenario: Microservice orkestrator yang harus memanggil beberapa downstream service secara paralel menggunakan cooperative non-blocking stream parsing, mengontrol konsumsi memori, dan mengisolasi context error secara fungsional.

File: `ConcurrentTaskPool.php`
```php
<?php

declare(strict_types=1);

namespace Enterprise\Concurrency;

use Fiber;
use Throwable;

/**
 * Representasi hasil komputasi fungsional (Result Monad-like Pattern)
 * @template T
 */
final readonly class Result
{
    /**
     * @param T|null $data
     */
    private function __construct(
        public bool $isSuccess,
        public mixed $data,
        public ?Throwable $error = null
    ) {}

    /**
     * @template U
     * @param U $data
     * @return self<U>
     */
    public static function ok(mixed $data): self
    {
        return new self(true, $data);
    }

    public static function fail(Throwable $error): self
    {
        return new self(false, null, $error);
    }
}

/**
 * Event-driven cooperative task scheduler menggunakan PHP native Fibers
 */
final class FiberEventScheduler
{
    /** @var array<int, array{fiber: Fiber, socket: resource|null}> */
    private array $tasks = [];
    
    /** @var array<int, Result<mixed>> */
    private array $results = [];

    private int $taskIdCounter = 0;

    /**
     * Mendaftarkan callable untuk dieksekusi sebagai Fiber terisolasi
     */
    public function defer(callable $callable): int
    {
        $id = ++$this->taskIdCounter;
        $fiber = new Fiber(function () use ($id, $callable): void {
            try {
                $return = $callable();
                $this->results[$id] = Result::ok($return);
            } catch (Throwable $e) {
                $this->results[$id] = Result::fail($e);
            }
        });

        $this->tasks[$id] = ['fiber' => $fiber, 'socket' => null];
        return $id;
    }

    /**
     * Cooperative IO: Menunggu stream resource ready untuk dibaca tanpa memblokir thread
     * @param resource $stream
     */
    public static function awaitReadable(mixed $stream): void
    {
        if (!is_resource($stream)) {
            throw new \InvalidArgumentException('Stream tidak valid');
        }

        stream_set_blocking($stream, false);
        
        // Menyerahkan eksekusi kembali ke scheduler loop dengan meta stream
        Fiber::suspend($stream);
    }

    /**
     * Menjalankan seluruh pipeline task hingga complete
     * @return array<int, Result<mixed>>
     */
    public function run(): array
    {
        while (!empty($this->tasks)) {
            $readStreams = [];
            $streamToTaskMap = [];

            foreach ($this->tasks as $id => $taskMeta) {
                $fiber = $taskMeta['fiber'];

                if (!$fiber->isStarted()) {
                    $yielded = $fiber->start();
                    if ($yielded && is_resource($yielded)) {
                        $this->tasks[$id]['socket'] = $yielded;
                    }
                } elseif ($fiber->isSuspended()) {
                    $socket = $taskMeta['socket'];
                    if ($socket === null) {
                        // Resumable task non-IO
                        $fiber->resume();
                    } else {
                        // Kumpulkan socket untuk multi-plexing
                        $readStreams[] = $socket;
                        $streamToTaskMap[(int)$socket] = $id;
                    }
                }

                if ($fiber->isTerminated()) {
                    unset($this->tasks[$id]);
                }
            }

            // Multiplexing I/O via stream_select (Level OS epoll/kqueue wrapper)
            if (!empty($readStreams)) {
                $write = null;
                $except = null;
                $timeoutSeconds = 0;
                $timeoutMicroseconds = 50000; // 50ms tick interval

                $ready = @stream_select($readStreams, $write, $except, $timeoutSeconds, $timeoutMicroseconds);

                if ($ready !== false && $ready > 0) {
                    foreach ($readStreams as $readySocket) {
                        $taskId = $streamToTaskMap[(int)$readySocket];
                        $this->tasks[$taskId]['socket'] = null; // Clear waiting socket
                        $this->tasks[$taskId]['fiber']->resume();
                        
                        if ($this->tasks[$taskId]['fiber']->isTerminated()) {
                            unset($this->tasks[$taskId]);
                        }
                    }
                }
            }
        }

        return $this->results;
    }
}

// =========================================================================
// Simulasi Pengujian Produksi
// =========================================================================

$scheduler = new FiberEventScheduler();

// Task 1: Non-blocking HTTP Call menggunakan stream socket murni
$scheduler->defer(function (): string {
    $fp = @stream_socket_client('tcp://httpbin.org:80', $errno, $errstr, 5);
    if (!$fp) {
        throw new \RuntimeException("Socket connection failed: $errstr");
    }

    $request = "GET /base64/SFRUUEJJTiBpcyBhd2Vzb21l HTTP/1.1\r\nHost: httpbin.org\r\nConnection: close\r\n\r\n";
    fwrite($fp, $request);

    // Yield control sampai downstream mengembalikan byte buffer
    FiberEventScheduler::awaitReadable($fp);

    $response = '';
    while (!feof($fp)) {
        $chunk = fread($fp, 1024);
        if ($chunk === false || $chunk === '') {
            break;
        }
        $response .= $chunk;
    }
    fclose($fp);

    return substr($response, 0, 120) . '... [TRUNCATED]';
});

// Task 2: CPU-bound Functional Batch Transformation
$scheduler->defer(function (): array {
    $numbers = range(1, 1000);
    // Pure functional immutable pipeline
    return array_reduce(
        $numbers,
        fn(array $carry, int $num): array => ($num % 2 === 0) ? [...$carry, $num * $num] : $carry,
        []
    );
});

$metricsStart = memory_get_usage(true);
$results = $scheduler->run();
$metricsEnd = memory_get_usage(true);

echo "--- HASIL PIPELINE KONKURENSI FIBER ---\n";
foreach ($results as $id => $res) {
    if ($res->isSuccess) {
        printf("Task %d: BERHASIL -> Type: %s\n", $id, gettype($res->data));
    } else {
        printf("Task %d: GAGAL -> Error: %s\n", $id, $res->error->getMessage());
    }
}
printf("Alokasi Puncak Memori: %0.2f KB\n", ($metricsEnd - $metricsStart) / 1024);
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Arsitektur Financial Payment Gateway Webhook Ingestion Engine
* **Volume:** 25.000 webhooks per detik dari berbagai vendor perbankan.
* **Masalah:** Menggunakan PHP-FPM klasik membutuhkan alokasi 1.200 worker instance dengan alokasi RAM masif (48 GB). Terjadi latensi degradasi parah hingga *HTTP 504 Gateway Timeout* saat upstream core banking mengalami perlambatan response time I/O (3000ms).
* **Solusi Arsitektur Modern:**
  1. Migrasi ke persistent worker runtime berbasis Fiber / Coroutine runtime (RoadRunner + PSR-7 Workers).
  2. Implementasi **Zero-Leak Stream Aggregator**: Seluruh incoming payload di-*stream* langsung sebagai immutability Value Objects (`readonly struct`).
  3. Non-blocking logging dan database pooling connection menggunakan dynamic worker concurrency pool.

#### Arsitektur Desain Produksi:

```
[Incoming Webhook Traffic] 
          │ (25,000 req/sec)
          ▼
   [Cloud Flare / WAF]
          │
          ▼
   [High-Performance RoadRunner / FrankenPHP Workers]
   (Long-Running PHP CLI Workers - Multi Fiber per Worker)
          │
          ├──> [Fiber 1] Validasi HMAC In-Memory (Zero Allocation)
          ├──> [Fiber 2] Non-blocking Pipeline ke Redis Buffer
          └──> [Fiber n] Stream write ke Kafka Topic
                    │
                    ▼
          [Manual GC Management]
          - gc_disable() saat streaming batch aktif
          - Trigger explicit gc_collect_cycles() setiap threshold 2000 request
```

#### Hasil Metrik:
* Penurunan kebutuhan alokasi instance: Dari 1.200 worker FPM menjadi **32 Persistent CLI Workers**.
* Konsumsi RAM: Turun dari **48 GB** menjadi **2.4 GB**.
* P99 Latency: Turun dari **2.450 ms** menjadi **18 ms**.
* Zero crash/leak selama 30 hari uptime continuous streaming.

---

### 9. Trade-offs

| Pendekatan | Latency (P99) | Resource Overhead | Kompleksitas Kode | Resiko Stabilitas |
| :--- | :--- | :--- | :--- | :--- |
| **PHP-FPM (Shared-Nothing)** | Tinggi (karena setup/teardown VM setiap request) | Sangat Tinggi (RAM scale linearly per worker process) | Sangat Rendah (Stateless murni, memory leak aman) | Rendah (Crash pada satu worker terisolasi) |
| **Native Fibers (Custom Loop)** | Rendah (Userland cooperative multiplexing) | Rendah (Memory footprint per Fiber ~4-8KB) | Sangat Tinggi (Harus mengontrol stack non-blocking secara manual) | Sedang (Bug pada socket block dapat memblokir proses induk) |
| **Swoole / OpenSwoole Coroutine** | Ekstrim Rendah (C-level IO Hooking) | Sangat Rendah (Asynchronous event-driven C runtime) | Sedang (Paradigma mirip Node.js/Go) | Tinggi (Segfault berpotensi mematikan seluruh engine worker; resiko static contamination) |
| **RoadRunner (Go Process Manager)** | Sangat Rendah (Goroutine transport via IPC pipes) | Rendah (PHP worker persistent, zero framework bootstrapping) | Rendah-Sedang (PSR-7/PSR-15 standard compliant) | Rendah-Sedang (Memerlukan sanitasi *state* antar request) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. State Contamination pada Persistent Execution
* **Gejala:** User A dapat melihat data credential User B setelah microservice berjalan beberapa jam di runtime FrankenPHP/RoadRunner.
* **Penyebab:** Menyimpan request-bound data di dalam properti kelas `static` atau singleton container tanpa melakukan reset di level lifecycle middleware.
* **Troubleshooting:**
  Gunakan tool analisis statis (`psalm` atau `phpstan` dengan plugin strict-mode). Implementasikan `ResetInterface` dari Symfony atau PSR contract:
  ```php
  public function reset(): void {
      $this->state = []; // Wajib dikosongkan setiap request cycle berakhir
  }
  ```

#### 2. GC Thrashing pada Pengolahan Big Data
* **Gejala:** CPU load melonjak 100% pada CLI daemon, throughput per detik turun drastis meskipun memori RAM masih tersisa luas.
* **Penyebab:** Engine terus-menerus memanggil `gc_collect_cycles()` karena *Roots Buffer* (10.000 entry) terisi berulang-ulang dalam hitungan milidetik saat meng-instansiasi jutaan object temporer.
* **Solusi:**
  ```php
  // Nonaktifkan GC otomatis saat batch parsing intensif
  gc_disable();
  
  foreach ($massiveDataSet as $data) {
      // Eksekusi komputasi domain fungsional
  }
  
  // Nyalakan kembali dan bersihkan di akhir batch
  gc_enable();
  gc_collect_cycles();
  ```

#### 3. Hanging Fiber Akibat Blocking I/O
* **Gejala:** Seluruh eksekusi scheduler Fiber berhenti secara total dan tidak merespon traffic masuk lainnya.
* **Penyebab:** Memanggil fungsi bawaan yang bersifat blocking murni (seperti `file_get_contents`, `PDO::query`, `sleep`) di dalam tubuh Fiber alih-alih menggunakan non-blocking streams atau async driver.
* **Troubleshooting:** Audit syscall menggunakan `strace -p <PID> -f` untuk melacak blocker blocking read/poll call.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Immutability Penuh:** Definisikan domain entities dengan keyword `readonly class` untuk menjamin thread-safety konseptual dan membatasi side-effects.
- [ ] **Monitor Zend Memory Pools:** Lakukan monitoring internal via `memory_get_usage(false)` (alokasi real PHP) dan `memory_get_usage(true)` (alokasi OS system layer).
- [ ] **Sanitasi Static References:** Pastikan tidak ada koleksi data/array yang bertambah secara infinite di scope global atau static method.
- [ ] **Gunakan Weak References:** Terapkan `WeakReference` atau `WeakMap` untuk arsitektur *caching* atau *in-memory metadata listeners* agar tidak mencegah Garbage Collector membersihkan object yang sudah mati.
- [ ] **Set Batas Memori CLI Secara Eksplisit:** Selalu pasang hard-cap `ini_set('memory_limit', '512M')` pada worker daemon agar kernel OS (OOM Killer) tidak mematikan process host secara brutal jika terjadi anomali memory leak.
- [ ] **Manajemen GC Terjadwal:** Pada process pipeline data, panggil `gc_collect_cycles()` secara deterministik (misal: setiap kelipatan 5.000 message yang terproses).

---

### 12. Hands-on Practice

Buatlah direktori praktikum dengan hierarki berikut:
```bash
hands-on/
└── m02/
    ├── docker-compose.yml
    ├── Dockerfile
    ├── src/
    │   ├── LeakSimulator.php
    │   ├── FiberWorkerPool.php
    │   └── MemoryAuditor.php
    └── run_benchmark.php
```

#### Langkah 1: Siapkan `Dockerfile` (PHP 8.3 CLI + Extension Debugging)
Simpan di `hands-on/m02/Dockerfile`:
```dockerfile
FROM php:8.3-cli-alpine

RUN apk add --no-cache linux-headers bash procps
RUN docker-php-ext-install pcntl

WORKDIR /app
CMD ["php", "run_benchmark.php"]
```

#### Langkah 2: Buat Modul Pemeriksa Memori (`src/MemoryAuditor.php`)
Simpan di `hands-on/m02/src/MemoryAuditor.php`:
```php
<?php

declare(strict_types=1);

namespace HandsOn;

final class MemoryAuditor
{
    public static function dump(string $checkpoint): void
    {
        $memRaw = memory_get_usage(false);
        $memReal = memory_get_usage(true);
        $gcInfo = gc_status();

        printf(
            "[%s] Emalloc: %0.2f MB | System: %0.2f MB | GC Runs: %d | GC Roots: %d\n",
            str_pad($checkpoint, 18),
            $memRaw / 1024 / 1024,
            $memReal / 1024 / 1024,
            $gcInfo['runs'],
            $gcInfo['roots']
        );
    }
}
```

#### Langkah 3: Buat Simulator Kebocoran Memori & GC Recovery (`src/LeakSimulator.php`)
Simpan di `hands-on/m02/src/LeakSimulator.php`:
```php
<?php

declare(strict_types=1);

namespace HandsOn;

final class DynamicNode
{
    public ?DynamicNode $sibling = null;
    public string $payload;

    public function __construct()
    {
        // 100 KB mock string per node
        $this->payload = str_repeat('X', 102400);
    }
}

final class LeakSimulator
{
    public static function createCircularLeak(int $iterations): void
    {
        for ($i = 0; $i < $iterations; $i++) {
            $nodeA = new DynamicNode();
            $nodeB = new DynamicNode();

            // Circular cross-reference binding
            $nodeA->sibling = $nodeB;
            $nodeB->sibling = $nodeA;

            // Variabel dibiarkan out-of-scope tanpa explicit unset
        }
    }
}
```

#### Langkah 4: Eksekusi Benchmark Runner (`run_benchmark.php`)
Simpan di `hands-on/m02/run_benchmark.php`:
```php
<?php

declare(strict_types=1);

require_once __DIR__ . '/src/MemoryAuditor.php';
require_once __DIR__ . '/src/LeakSimulator.php';

use HandsOn\MemoryAuditor;
use HandsOn\LeakSimulator;

echo "=== MEMORY LEAK & GC DEEP-DIVE RUNNER ===\n\n";

MemoryAuditor::dump("Startup");

// Tahap 1: Injeksi circular objects
LeakSimulator::createCircularLeak(500);
MemoryAuditor::dump("Post 500 Cyclics");

// Tahap 2: Buat beban siklus lagi hingga melampaui buffer roots bawaan
LeakSimulator::createCircularLeak(10000);
MemoryAuditor::dump("Post 10K Cyclics");

// Tahap 3: Pembersihan siklus secara manual
echo "\n-> Memanggil gc_collect_cycles() secara eksplisit...\n";
$collected = gc_collect_cycles();
echo "-> Berhasil merebut $collected node siklus dari Zend MM\n\n";

MemoryAuditor::dump("Post Explicit GC");
```

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi higher-order `pipeline(callable ...$fns): callable` yang menerima fungsi fungsional murni dan mengeksekusinya secara linear dari kiri ke kanan (komposisi fungsional), gunakan `readonly class` untuk membungkus data state.

#### Level: Medium
Buat class `AsyncRateLimiter` berbasis Fiber yang membatasi eksekusi operasi I/O hanya dapat berjalan maksimal 5 concurrent operations secara serentak. Jika quota 5 terlewati, fiber task ke-6 harus di-`suspend()` secara otomatis dan baru di-`resume()` saat salah satu task selesai.

#### Level: Hard
Bangun mini event-loop berbasis Fiber yang mengintegrasikan streaming parsing JSON berukuran multi-gigabyte. Task harus melakukan deserialisasi chunk-by-chunk tanpa pernah mengizinkan memory footprint PHP engine melampaui 16 MB, sambil secara paralel menyiarkan event progress ke stream output lain.

---

### 14. Challenge

**Skenario Sistem:**
Sebuah platform trading kripto enterprise membutuhkan in-memory order-book matcher berlatensi mikro (High-Frequency Trading) yang ditulis dalam lingkungan PHP CLI 8.3 murni tanpa dependensi library eksternal vendor.

**Spesifikasi Persyaratan:**
1. Mampu mengonsumsi mock payload market feed hingga 50.000 update orders/detik melalui stream non-blocking sockets.
2. Orderbook harus dirancang menggunakan paradigma immutable data structures (Functional Persistent Trees).
3. **Konstrain Memori Absolut:** Proses harus berjalan terus-menerus selama minimal 30 menit simulasi tanpa terjadi memory drift (pertumbuhan memori harus 0% plateau) dan hard ceiling alokasi memori tidak boleh melampaui batas **32 MB**.
4. Deteksi circular reference harus ditangani tanpa memicu *GC Stop-The-World* latensi yang merusak execution window perdagangan (P99 latency harus di bawah 5 milidetik).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Berapa ukuran memori fisik yang dialokasikan oleh Zend Engine untuk satu struct `zval` standar pada arsitektur sistem operasi 64-bit?
2. Pada kondisi apa Zend Memory Manager (Zend MM) langsung membebaskan memori suatu variabel tanpa melibatkan algoritma Garbage Collector?
3. Apa perbedaan konseptual mendasar antara implementasi `Generator` dan `Fiber` di PHP?
4. Mengapa penggunaan keyword `readonly` pada class property membantu dalam penerapan paradigma pemrograman fungsional?
5. Apakah PHP Fibers mengeksekusi instruksi pada multi-core CPU secara paralel seperti halnya pthread OS? Jelaskan secara ringkas.

#### Bagian 2: Intermediate (5 Pertanyaan)
1. Apa fungsi dari buffer *GC Roots* dan apa pemicu default dari eksekusi siklus evaluasi circular references?
2. Mengapa persistent workers seperti FrankenPHP, Swoole, atau RoadRunner rentan terhadap masalah kebocoran memori dibandingkan dengan mode runtime PHP-FPM klasik?
3. Jelaskan state warna (*Purple, Grey, Black, White*) yang digunakan oleh Cycle Collection Algorithm milik Zend Engine!
4. Bagaimana cara kerja `WeakMap` dalam mencegah memory leaks jika dibandingkan dengan penyimpanan metadata object pada standard `SplObjectStorage` atau array native?
5. Mengapa teknik `gc_disable()` justru direkomendasikan pada proses pengolahan batch data intensif yang membuat jutaan object berumur sangat pendek?

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Analitis)
1. **Kasus Worker Hang:**
   Sebuah daemon consumer Kafka yang ditulis menggunakan PHP 8.2 tiba-tiba membeku (*unresponsive*) tanpa error log apa pun setelah memproses 200.000 event. CPU usage turun ke 0% dan memory usage tetap stabil di 220 MB. Berdasarkan arsitektur internal I/O dan Fibers, hipotesis apa yang paling mungkin menyebabkan kebuntuan sistem ini, dan langkah debugging OS apa yang harus Anda jalankan?
2. **Kasus Memory Drift pada Long-Running Daemon:**
   Sebuah worker job queue mengalami kenaikan alokasi memori sistem secara bertahap (`memory_get_usage(true)`) sebesar 500 KB per menit, padahal output `memory_get_usage(false)` menunjukkan angka konstan di kisaran 12 MB. Mengapa anomali fragmentasi Zend MM ini dapat terjadi, dan bagaimana solusinya?
3. **Kasus Latency Spike pada Real-time Microservice:**
   Sebuah service agregasi berbasis coroutine mencatatkan spike latensi periodik setiap 30 detik dari normal 5ms melompat ke 450ms. Profiling menunjukkan lonjakan bertepatan dengan pemanggilan internal `gc_collect_cycles()`. Bagaimana Anda mendesain ulang arsitektur alokasi object untuk meratakan latensi ini?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **16 Bytes.**
2. Ketika variabel nilai kompleks tersebut memiliki nilai `refcount == 0` (tidak ada lagi simbol yang merujuk padanya di userland scope).
3. `Generator` bersifat *stackless coroutine* (hanya dapat me-yield kontrol dari frame fungsi itu sendiri), sedangkan `Fiber` bersifat *stackful coroutine* (dapat disuspend dari kedalaman call stack manapun, termasuk dari dalam nested function calls).
4. Karena keyword `readonly` mencegah mutasi nilai properti setelah inisialisasi, menjamin sifat *immutability* dan mengeliminasi *unintended side-effects*.
5. **Tidak.** Fiber adalah *cooperative concurrency (userland coroutines)* yang berjalan di satu core OS thread yang sama, bergantian melalui mekanisme context switch sukarela (*cooperative yielding*).

#### Bagian 2: Intermediate
1. GC Roots buffer menyimpan pointer ke zval kompleks yang refcount-nya berkurang tetapi tidak mencapai 0 (berpotensi sirkular). Pemicu defaultnya adalah saat jumlah kandidat di dalam root buffer mencapai 10.001 entry.
2. Karena PHP-FPM merestart dan mengosongkan heap Zend MM secara total di setiap akhir lifecycle request (`RSHUTDOWN`), sedangkan persistent worker mempertahankan memori heap terus-menerus antar request.
3. 
   * **Purple:** Kandidat dicurigai siklus referensi.
   * **Grey:** Sedang dalam proses tracking traversal DFS (refcount dikurangi 1 secara simulasi).
   * **White:** Terbukti sebagai dead cycle (refcount menjadi 0 pada simulasi), siap dibersihkan (*garbage*).
   * **Black:** Terbukti masih memiliki referensi hidup di luar siklus internal, dikembalikan ke heap.
4. `WeakMap` tidak menaikkan `refcount` dari object yang dijadikan sebagai key. Jika object tersebut di-unset dari tempat lain, entry pada `WeakMap` akan otomatis hilang, sehingga tidak menghambat pembebasan memori.
5. Karena pembuatan jutaan object berumur pendek akan memicu penuhanan roots buffer secara repetitif, menyebabkan CPU habis terbuang hanya untuk mengeksekusi algoritma cycle collection (*GC thrashing*) terhadap objek yang sebetulnya akan segera mati secara alami.

#### Bagian 3: Skenario Kasus Produksi
1. **Analisa:** Kemungkinan besar salah satu event memicu pemanggilan stream/socket yang berada dalam kondisi blocking murni (tanpa set `stream_set_blocking($stream, false)` atau tanpa implementasi socket timeout).
   **Langkah Debugging:** Jalankan utility Linux trace: `strace -p <PID> -e trace=network,poll,select,read` untuk melihat pada file descriptor (FD) mana thread PHP tersebut terblokir (stuck di `recvfrom` atau `epoll_wait`).
2. **Analisa:** Terjadi fragmentasi memori di level alokator C (*malloc fragmentation*) atau Zend MM Chunk fragmentation. Variabel dialokasikan dan dibebaskan dengan ukuran chunk bervariasi yang membuat OS tidak dapat merebut kembali halaman memori (*dirty pages*).
   **Solusi:** Gunakan alokator alternatif modern seperti `jemalloc` melalui `LD_PRELOAD` pada container environment untuk meredam fragmentasi, atau atur *worker max requests threshold* (misal: restart process setiap 100.000 cycle).
3. **Analisa:** GC Pause (Stop-The-World) terjadi karena jutaan object kecil dialokasikan dan disimpan dalam collection sirkular, menyebabkan cycle collector memindai graf referensi yang sangat masif.
   **Solusi:**
   1. Ganti struktur data class instances menjadi Flat Typed Arrays atau buffer biner (`SplFixedArray`).
   2. Matikan GC otomatis via `gc_disable()` dan jalankan evaluasi GC secara manual pada interval off-peak via micro-batching.
   3. Gunakan pattern object-pooling untuk meng-reuse instansiasi objek tanpa membebani collector Zend MM.

---

### 16. Summary

* **Zend MM** adalah fondasi runtime alokasi performa tinggi di PHP yang bekerja di atas alokator OS, mengelola memory layout via blok chunks, pages, dan `zval` (16 bytes).
* **Reference Counting** menangani 95%+ siklus pembebasan memori secara langsung dengan overhead mendekati nol, sedangkan **Cycle Collector** adalah pelindung sinkronus untuk mencegah kebocoran sirkular yang tidak terjangkau.
* **PHP Fibers** memberikan kapabilitas *stackful cooperative multitasking*, membuka pintu bagi runtime modern tanpa blocking I/O dengan skalabilitas concurrency yang bersaing dengan ekosistem async modern.
* Membangun arsitektur enterprise pada persistent runner (RoadRunner, FrankenPHP, Swoole) menuntut pemahaman arsitektur memori mendalam: data immutability, sanitasi static context, dan manajemen lifecycle alokasi engine.