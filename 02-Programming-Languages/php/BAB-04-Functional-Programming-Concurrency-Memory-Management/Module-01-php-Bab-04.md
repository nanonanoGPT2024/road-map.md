# KURIKULUM PEMROGRAMAN PHP TINGKAT LANJUT
## BAB 04: Functional Programming, Concurrency & Memory Management
### MODUL 01: Functional Programming Paradigms, Fiber Concurrency, and Zend Engine Memory Internals

---

### SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages
*   **Bahasa Pemrograman:** PHP (Targeting PHP 8.2+)
*   **Bab:** 04 — Lanjutan Ekosistem & Eksekusi Asinkron
*   **Modul:** 01 — Functional Programming, Concurrency & Memory Management
*   **Tingkat Kesulitan:** Advanced / Senior Engineer
*   **Prasyarat:** Pemahaman mendalam tentang Object-Oriented PHP, Type System PHP 8+, SPL (Standard PHP Library), dan pemahaman dasar arsitektur operating system (I/O multiplexing, thread vs process, stack vs heap).

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menguasai Paradigma Pemrograman Fungsional (FP) di PHP**: Mengimplementasikan konsep *pure functions*, *immutability*, *higher-order functions*, *currying*, serta teknik *functional composition* (seperti `pipe` dan `compose`) memanfaatkan sintaks First-Class Callables (`Closure::fromCallable` dan sintaks `foo(...)`) serta arrow functions.
2.  **Mendalami Mekanisme Konkurensi Kooperatif Menggunakan Fibers**: Menganalisis dan mengimplementasikan primitif konkurensi bawaan PHP 8.1+ (`Fiber`), memahami siklus hidup eksekusi Fiber (suspend, resume, terminate), dan membedakan konkurensi kooperatif berbasis Fiber dengan model preemptive threading atau event-loop berbasis Reactor.
3.  **Membedah Arsitektur Zend Memory Manager (ZMM)**: Menguraikan struktur internal `zval`, mekanisme *Reference Counting* (`refcount`, `is_ref`), *Copy-on-Write* (COW), dan algoritma *Concurrent Cycle Collection* (Bacon-Rajan variant) pada Zend Engine.
4.  **Mencegah Memory Leaks pada Long-Running Processes**: Mengidentifikasi dan memitigasi kebocoran memori akibat *circular references*, *uncollected static state*, dan *unbounded Fiber stacks* dalam arsitektur server asinkron (misalnya RoadRunner, Swoole, atau worker berbasis Revolt/Amphp).
5.  **Mengintegrasikan FP, Fibers, dan GC Optimization**: Merancang pipeline pemrosesan data asinkron yang murni, terisolasi, dan hemat memori dengan manipulasi manual terhadap siklus hidup Garbage Collector (`gc_collect_cycles`, `gc_mem_caches`).

---

### SEKSI 03 — MINDSET & MENTAL MODEL

#### Paradigma Fungsional: Transformasi Data Tanpa Efek Samping
Dalam paradigma imperatif/OOP standar, state tersebar dan dimutasi secara langsung di dalam memori objek. Dalam functional programming, komputasi dipandang sebagai evaluasi fungsi matematika. Mental model yang harus dibangun adalah **Data Pipeline**: data masuk sebagai input yang tidak dapat diubah (*immutable*), melewati serangkaian transformasi murni (*pure transformation*), dan menghasilkan representasi data baru tanpa mengubah status global aplikasi (*no side-effects*).

#### Konkurensi PHP: Dari "Share Nothing" ke Cooperative Fibers
PHP secara historis mengadopsi model *Shared-Nothing Architecture*, di mana setiap request HTTP dialokasikan memori independen oleh FPM dan dimusnahkan secara total saat request selesai (*request boundary lifecycle*). 

```
Imperative / Request-Boundary Mindset:
[Request In] -> [Allocate Memory] -> [Mutate State] -> [Flush Output] -> [Purge Heap]

Async / Long-Running Mindset (Fiber-based):
[Worker Bootstrapped Once]
   ├── Fiber 1: [Read Socket (Suspend)] ──┐
   ├── Fiber 2: [Process CPU Bound Task]   ├── Event Loop Interleaving (Same Process Memory)
   └── Fiber 1: [Resumed on Data Available]┘
```

Dengan diperkenalkannya `Fiber` di PHP 8.1 dan pergeseran ke arah aplikasi *long-running worker*, mental model Anda harus bergeser:
*   Eksekusi tidak lagi strictly linier-sinkron.
*   Konkurensi di PHP adalah **kooperatif**, bukan preemptive: sebuah Fiber harus secara sukarela menyerahkan kontrol (*yield/suspend*) kembali ke caller atau event loop.
*   Memori tidak lagi dibersihkan secara otomatis oleh engine di akhir eksekusi request; Anda memegang kendali penuh atas alokasi dan dealokasi memori.

#### Manajemen Memori: Refcounting dan Graph Cycles
Bayangkan memori sebagai *directed graph*. Setiap variabel (`zval`) adalah simpul referensi ke buffer data. Reference counting bertindak sebagai counter instan untuk melacak berapa banyak pointer yang menunjuk ke buffer tersebut. 
Namun, jika Simpul A menunjuk ke Simpul B, dan Simpul B menunjuk ke Simpul A, reference counter tidak akan pernah mencapai angka nol meskipun simpul-simpul tersebut sudah tidak dapat diakses lagi dari root scope (*garbage*). Memahami cara Zend Garbage Collector mendeteksi dan membersihkan *island of cycles* ini adalah kunci menjaga reliabilitas aplikasi skala enterprise.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

#### 1. Anatomi Zend Engine Memory & Siklus Hidup `zval`

```
+-----------------------------------------------------------------------+
|                              Zend Engine                              |
|                                                                       |
|   PHP Script Scope:           Zend Memory Manager (ZMM):              |
|   $a = ["data"];              +-------------------------------------+ |
|                               | zval (Value Container)              | |
|                               | - value: zend_value (pointer)       | |
|                               | - u1.type_info: IS_ARRAY            | |
|                               +------------------|------------------+ |
|                                                  |                    |
|                                                  v                    |
|                               +-------------------------------------+ |
|                               | zend_array (Heap Alloc)             | |
|   $b = $a;                    | - gc.refcount = 2 (COW Active)      | |
|   (Zero-copy reference)       | - gc.u.type_flags = ...             | |
|                               | - nNumUsed, nNumOfElements          | |
|                               | - arData (Array Buffer)             | |
|                               +-------------------------------------+ |
|                                                  |                    |
|   $b[] = "mutation";                             v (Copy-On-Write)    |
|   (Split memory!)             +-------------------------------------+ |
|                               | zend_array (New Allocation for $b)  | |
|                               | - gc.refcount = 1                   | |
|                               | - arData modified                   | |
|                               +-------------------------------------+ |
+-----------------------------------------------------------------------+
```

#### 2. Siklus Eksekusi Fiber vs Threading Tradisional

```
+---------------------------------------------------------------------------+
| OS Preemptive Threading (Context Switch diatur OS Kernel via Interupsi)   |
| Thread 1: [Exec]---->[Interrupt/Pause by Kernel]---->[Exec]               |
| Thread 2:            [Exec]---->[Interrupt by Kernel]                     |
+---------------------------------------------------------------------------+
| PHP 8.1+ Cooperative Fiber Concurrency (Context Switch diatur User-space)|
| Caller / Event Loop:                                                      |
|   [Start Fiber] ──────────────────────────┐                               |
|          ▲                                │ transfers control             |
|          │ Fiber::suspend()               ▼                               |
|          └─────────────────────────── [Fiber Core Processing]            |
|   [Do Other Work / Poll I/O]              │                               |
|          │                                │ (Suspended state stored in    |
|          │ Fiber::resume()                │  isolated C-stack buffer)     |
|          └───────────────────────────────►│                               |
|                                           [Finish execution]              |
+---------------------------------------------------------------------------+
```

#### 3. Zend Cyclic Garbage Collector State Machine

```
   [zval refcount decremented]
               |
               v
       (refcount > 0 ?) ──── NO ───► [Deallocate immediately (Free)]
               |
              YES
               v
   [Warna Simpul: PURPLE] ───► Masukkan ke GC Root Buffer (Possible Cycle)
               |
               v (Buffer Penuh / gc_collect_cycles() terpanggil)
   +------------------------------------------------------------------+
   | FASE 1: gc_mark_roots()                                          |
   | - Traverse graf dari root buffer.                                |
   | - Kurangi refcount virtual untuk setiap referensi internal.      |
   | - Jika refcount virtual == 0, warnai simpul GREY.                |
   | - Jika refcount virtual > 0, pulihkan (warnai BLACK).            |
   +------------------------------------------------------------------+
               |
               v
   +------------------------------------------------------------------+
   | FASE 2: gc_scan_roots()                                          |
   | - Cek simpul yang berstatus GREY.                                |
   | - Jika refcount == 0 permanen, warnai WHITE (Confirmed Garbage). |
   | - Jika refcount > 0, pulihkan anak-anaknya ke BLACK.             |
   +------------------------------------------------------------------+
               |
               v
   +------------------------------------------------------------------+
   | FASE 3: gc_collect_roots()                                       |
   | - Bebaskan semua memori simpul WHITE dari ZMM heap.              |
   | - Kembalikan status simpul BLACK ke alokasi normal.              |
   +------------------------------------------------------------------+
```

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. Anatomi Struct `zval` (C Source: `zend_types.h`)
Di dalam C kernel PHP (Zend Engine), setiap variabel dibungkus oleh struct `zval`. Ukuran `zval` selalu fixed (16 byte pada arsitektur 64-bit).

```c
struct _zval_struct {
    zend_value        value; // 8 byte: pointer ke union (long, double, zend_string*, zend_array*, zend_object*, dll)
    union {
        struct {
            ZEND_ENDIAN_LOHI_3(
                zend_uchar    type,         // Tipe variabel: IS_STRING, IS_ARRAY, IS_OBJECT, dll
                zend_uchar    type_flags,   // Flags seperti IS_TYPE_REFCOUNTED, IS_TYPE_COLLECTABLE
                union {
                    uint16_t  extra;        // Info tambahan instruksi bytecode
                } u;
            )
        } v;
        uint32_t type_info;
    } u1;
    union {
        uint32_t     next;                 // Hash collision chain
        uint32_t     cache_slot;           // Runtime cache index
        uint32_t     opline_num;           // VM execution context
        uint32_t     lineno;               // Nomor baris
        uint32_t     num_args;             // Argumen tracking
    } u2; // 4 byte metadata
};
```

*   **Pembedahan**: Ketika kita mengeksekusi `$b = $a`, PHP tidak menduplikasi alokasi memori heap yang ditunjuk oleh `zend_value`. Alih-alih menduplikasi, engine menyalin `zval` (16 byte) dan menaikkan nilai `gc.refcount` pada target `zend_refcounted` struct sebesar 1.
*   **Copy-On-Write (COW)**: Mekanisme duplikasi heap memory hanya terpicu jika salah satu variabel dimutasi (`write operation`). Jika mutasi terjadi dan `refcount > 1`, engine memanggil `zval_copy_ctor` untuk mengkloning data mentah dan memisahkan referensinya.

#### 2. Mekanisme Internal Fiber (C Source: `zend_fibers.c`)
Fiber diimplementasikan di layer C menggunakan arsitektur *boost::context* atau perakitan assembly arsitektur spesifik (*architecture-specific context switching*):
1.  **Fiber Stack Allocation**: Ketika objek `Fiber` diinstansiasi, engine mengalokasikan stack memori virtual terisolasi di heap C (secara default biasanya 4KB hingga 8KB, dapat bertumbuh tergantung OS dan konfigurasi).
2.  **Pointer Swapping**: Ketika `Fiber::suspend()` dipanggil, Zend Engine menyimpan status register CPU saat ini (Instruction Pointer/Program Counter, Stack Pointer, Base Pointer, register umum) ke dalam struct `zend_fiber_context`.
3.  **Context Transition**: Engine kemudian menukar stack pointer aktif kembali ke pointer C-stack caller (`VM main loop`). Nilai yang dioperasikan ke `Fiber::suspend($value)` ditaruh di slot komunikasi antar konteks dan dikembalikan sebagai hasil evaluasi metode `start()` atau `resume()`.
4.  **No OS Kernel Overhead**: Operasi ini berjalan murni di user-space tanpa intervensi *kernel context switch*, menjadikannya ribuan kali lebih ringan dibandingkan switching thread level OS (*pthread*).

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### 1. Paradigma Functional Programming di Ekosistem PHP
Secara default, PHP adalah bahasa multi-paradigma yang berakar pada model imperatif prosedural dan OOP klasik berbasis kelas. Namun, implementasi FP modern di PHP bertumpu pada fitur fundamental berikut:

*   **First-Class Callables (`Closure`)**: Sejak PHP 8.1, ekspresi seperti `strlen(...)` menghasilkan instance `Closure` terikat secara efisien tanpa string-parsing overhead dari `[$this, 'method']` versi lama.
*   **Pure Functions**: Fungsi matematika deterministik:
    $$\forall x, f(x) = y \implies f(x) \text{ selalu menghasilkan } y$$
    Fungsi murni dilarang membaca atau menulis ke *global state*, dilarang melakukan operasi I/O (disk, network), dan dilarang mengubah referensi argumen input.
*   **Immutability**: Objek yang state-nya tidak dapat diubah setelah inisialisasi. Implementasi modern memanfaatkan `readonly class` pada PHP 8.2+ yang secara otomatis memberlakukan `readonly` ke seluruh propertinya.

#### 2. Concurrency: Fibers vs Event Loops vs Multithreading
Untuk memahami konkurensi di PHP, kita harus mengklasifikasikan tiga model utama:

| Dimensi | Preemptive Threads (pthreads, ext-parallel) | Event Loop (Revolt, ReactPHP, Node.js) | Cooperative Fibers (PHP 8.1+ Core) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Paralel sejati (Multi-core) | Konkuren Asinkron (Single-core event demux) | Konkuren Kooperatif (Single-core context switch) |
| **Mekanisme Switch**| OS Kernel Scheduler | Non-blocking I/O callbacks / Tick polling | Explicit userland yield (`Fiber::suspend`) |
| **Race Conditions** | Sangat Tinggi (Butuh Mutex, Semaphore) | Rendah (Hanya di level state logical) | Rendah (Deterministic non-preemption) |
| **Memory Overhead** | Besar (Thread stack OS ~1-8 MB) | Sangat Kecil (Closure callbacks di ZMM) | Ringan (Isolated C stack ~ beberapa KB) |

**Fibers bukanlah Event Loop.** Fiber tidak memiliki event loop I/O multiplexer bawaan (`epoll`, `kqueue`, atau `io_uring`). Fiber adalah primitif kontrol aliran data (*low-level control flow primitive*). Untuk membangun framework non-blocking yang komprehensif, Fiber harus digabungkan dengan abstraction layer seperti Revolt Event Loop (`amphp/amp` v3).

#### 3. Zend Cyclic Garbage Collector
PHP menggunakan dual-engine memory strategy:
1.  **Reference Counting Engine**: Membersihkan 95%+ memori seketika objek kehilangan pointer (`refcount == 0`). Pembersihan bersifat instan (*zero pause*).
2.  **Cycle Collector Engine**: Reference counting gagal ketika terjadi circular reference:
    ```
    $nodeA->child = $nodeB;
    $nodeB->parent = $nodeA;
    unset($nodeA, $nodeB);
    ```
    Meskipun `$nodeA` dan `$nodeB` di-`unset`, circular link menyebabkan `refcount` masing-masing objek bernilai 1. Memori terkatung-katung (*leaked*) kecuali dibersihkan oleh Cyclic Garbage Collector.
    
Collector mengumpulkan objek yang dicurigai (saat refcount berkurang tapi tidak mencapai nol) ke dalam **Root Buffer** berukuran fixed (biasanya 10.000 simpul). Ketika buffer penuh, algoritma traversal multi-fase (*Bacon-Rajan*) dieksekusi secara sinkron, yang dapat memicu latency spike (*GC Stop-the-world pause*) pada proses PHP intensif.

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi mendasar yang menggabungkan:
1.  Functional composition (`pipe`, `curry`)
2.  State Immutability
3.  Pemanfaatan Fiber primitif untuk pemrosesan paralel kooperatif

```php
<?php

declare(strict_types=1);

namespace Architecture\Fundamentals;

use Fiber;
use InvalidArgumentException;

// ---------------------------------------------------------
// 1. IMMUTABLE DATA STRUCTURE & FUNCTIONAL PRIMITIVES
// ---------------------------------------------------------

/**
 * Immutable Data Record memanfaatkan PHP 8.2 readonly class.
 */
readonly class Transaction
{
    public function __construct(
        public string $id,
        public float $amount,
        public string $currency,
        public string $status
    ) {}

    public function withStatus(string $newStatus): self
    {
        return new self($this->id, $this->amount, $this->currency, $newStatus);
    }
}

/**
 * Higher-Order Function: Currying untuk validasi mata uang.
 * Mengembalikan callable bertipe: Closure(Transaction): Transaction
 */
function validateCurrency(string $expectedCurrency): \Closure
{
    return function (Transaction $transaction) use ($expectedCurrency): Transaction {
        if ($transaction->currency !== $expectedCurrency) {
            throw new InvalidArgumentException(
                "Invalid currency [{$transaction->currency}]. Expected [{$expectedCurrency}]."
            );
        }
        return $transaction;
    };
}

/**
 * Higher-Order Function: Pure mapper function untuk mengaplikasikan diskon.
 */
function applyFee(float $feePercentage): \Closure
{
    return function (Transaction $transaction) use ($feePercentage): Transaction {
        $deducted = $transaction->amount - ($transaction->amount * ($feePercentage / 100));
        return new Transaction(
            $transaction->id,
            $deducted,
            $transaction->currency,
            $transaction->status
        );
    };
}

/**
 * Functional Composition: Pipeline function
 * Menerima f(x), g(x), h(x) dan menghasilkan h(g(f(x)))
 */
function pipe(callable ...$functions): \Closure
{
    return static function (mixed $initialValue) use ($functions): mixed {
        return array_reduce(
            $functions,
            static fn (mixed $accumulator, callable $func): mixed => $func($accumulator),
            $initialValue
        );
    };
}

// ---------------------------------------------------------
// 2. FIBER-BASED CONCURRENT SCHEDULER
// ---------------------------------------------------------

class FiberScheduler
{
    /** @var \SplQueue<Fiber> */
    private \SplQueue $queue;

    public function __construct()
    {
        $this->queue = new \SplQueue();
    }

    public function enqueue(Fiber $fiber): void
    {
        $this->queue->enqueue($fiber);
    }

    /**
     * Menjalankan seluruh fiber secara kooperatif hingga antrean kosong.
     */
    public function run(): void
    {
        while (!$this->queue->isEmpty()) {
            /** @var Fiber $fiber */
            $fiber = $this->queue->dequeue();

            if ($fiber->isSuspended()) {
                $fiber->resume();
            } elseif (!$fiber->isStarted()) {
                $fiber->start();
            }

            // Jika setelah dieksekusi fiber kembali suspend (belum selesai), masukkan ke antrean lagi
            if ($fiber->isSuspended()) {
                $this->queue->enqueue($fiber);
            }
        }
    }
}

// ---------------------------------------------------------
// 3. RUNTIME INTEGRATION
// ---------------------------------------------------------

$scheduler = new FiberScheduler();

// Data set
$transactions = [
    new Transaction("TX-001", 100.0, "USD", "PENDING"),
    new Transaction("TX-002", 250.0, "USD", "PENDING"),
    new Transaction("TX-003", 50.0,  "USD", "PENDING"),
];

// Pipeline komputasi fungsional (Pure Transformations)
$processorPipeline = pipe(
    validateCurrency("USD"),
    applyFee(2.5),
    fn (Transaction $tx): Transaction => $tx->withStatus("COMPLETED")
);

// Mendaftarkan pemrosesan tiap transaksi ke dalam Fiber terpisah
foreach ($transactions as $tx) {
    $fiber = new Fiber(function () use ($tx, $processorPipeline): void {
        echo "[Fiber] Memulai transaksi {$tx->id}\n";
        
        // Simulasi non-blocking I/O stage 1: Yield eksekusi
        Fiber::suspend();
        
        // Menjalankan Functional Data Transformation Pipeline
        $processed = $processorPipeline($tx);
        
        // Simulasi non-blocking I/O stage 2: Yield eksekusi
        Fiber::suspend();

        echo "[Fiber] Selesai {$processed->id} -> Amount: {$processed->amount} | Status: {$processed->status}\n";
    });

    $scheduler->enqueue($fiber);
}

// Eksekusi Scheduler
$scheduler->run();
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah analisis teknis mendalam terhadap kode pada **SEKSI 07**:

1.  **Baris 13–24 (`readonly class Transaction`)**:
    *   Menerapkan PHP 8.2 keyword `readonly class`. Seluruh properti secara implisit bersifat immutable (`readonly private/public`). Zend Engine mengunci `zval` dari mutasi langsung setelah pemanggilan konstruktor selesai.
    *   Metode `withStatus` mengimplementasikan copy-and-update pattern fungsional. Alih-alih memutasi `$this->status`, ia mengalokasikan instance baru, menjamin isolasi status antar eksekusi.
2.  **Baris 29–40 (`function validateCurrency`)**:
    *   Mengembalikan instance `Closure` yang menahan variabel `$expectedCurrency` melalui mekanisme lexical scoping (`use`).
    *   Berperan sebagai *pure validator*: tidak memodifikasi input, melainkan melempar *exception* atau mengembalikan objek referensi asli jika valid.
3.  **Baris 58–68 (`function pipe`)**:
    *   Implementasi kanonikal dari functional chaining.
    *   Menggunakan `array_reduce` native C-level implementation di dalam Zend VM. Array fungsi dievaluasi dari kiri ke kanan; output dari callable ke-$n$ langsung dipetakan sebagai input bagi callable ke-$(n+1)$.
4.  **Baris 74–106 (`class FiberScheduler`)**:
    *   Implementasi primitif dari sebuah *cooperative micro-task runner*.
    *   Memanfaatkan struktur data memori native `\SplQueue` (berbasis linked-list di internal C) untuk meminimalisir overhead alokasi hash-table seperti pada array PHP biasa.
    *   Metode `run()`: Melakukan polling loop sederhana. Jika fiber berstatus `isSuspended()`, engine memanggil `Fiber::resume()`. Pointer konteks VM melompat kembali ke dalam stack Fiber lokal.
5.  **Baris 125–140 (`new Fiber(...)` dan `Fiber::suspend()`)**:
    *   Di dalam closure Fiber, `Fiber::suspend()` dipanggil dua kali.
    *   Panggilan pertama mensimulasikan jeda saat resource menunggu operasi soket jaringan atau respon disk I/O.
    *   Zend Engine membekukan seluruh C-stack frame dari Fiber tersebut dan mengembalikan eksekusi ke baris 97 (`$scheduler->run()`), mengeksekusi Fiber transaksi berikutnya tanpa memblokir thread proses.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario Produksi: Long-Running CLI Worker untuk Batch Processing Event Stream
Sebuah perusahaan payment gateway memproses stream transaksi webhook bernilai jutaan dolar per jam. Arsitektur lama menggunakan skrip PHP sinkron via cronjob yang mengeksekusi 1 transaksi per satu hitungan HTTP request. Masalah kritis muncul:
1.  **Bottleneck I/O Jaringan**: Worker menghabiskan 80% waktu CPU-nya dalam keadaan idle/blocking (menunggu database commit dan panggilan API eksternal Visa/Mastercard).
2.  **Memory Bloat & Crash**: Worker berbasis daemon (`while(true)`) mengalami crash fatal `Out of Memory (OOM)` setiap 40-60 menit karena kebocoran sirkular referensi pada ORM/Entity Manager yang tidak dibersihkan.
3.  **Inkonsistensi State (Data Race)**: Developer memutasi state model transaksi di memori global, menyebabkan data transaksi A merembes ke transaksi B di batch yang sama.

#### Solusi Arsitektural:
*   Membangun **Fiber-Driven Concurrent Ingestion Worker** yang memproses beberapa transaksi bersamaan secara non-blocking dalam single process thread.
*   Mengisolasi semua logika validasi dan kalkulasi ke dalam **Pure Immutable Functions**.
*   Menerapkan kontrol siklus hidup **Zend Garbage Collection** secara manual via event boundary hooks untuk mencegah akumulasi cycle buffer OOM.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem produksi lengkap tanpa framework eksternal, memadukan Event Loop primitif berbasis Fiber, Functional Pipelines, dan ZMM Garbage Collection Manager.

```php
<?php

declare(strict_types=1);

namespace Production\Engine;

use Fiber;
use SplQueue;
use Throwable;
use DateTimeImmutable;

// ============================================================================
// 1. DOMAIN MODELS (STRICT IMMUTABILITY)
// ============================================================================

readonly class IngestionPayload
{
    public function __construct(
        public string $eventId,
        public string $accountNumber,
        public float $amount,
        public string $signature,
        public DateTimeImmutable $timestamp
    ) {}
}

readonly class ProcessingResult
{
    public function __construct(
        public string $eventId,
        public bool $isSuccess,
        public float $settledAmount,
        public ?string $errorMessage = null
    ) {}
}

// ============================================================================
// 2. FUNCTIONAL CORE PIPELINE (PURE FUNCTIONS)
// ============================================================================

final class PipelineCore
{
    public static function verifySignature(string $secretKey): \Closure
    {
        return static function (IngestionPayload $payload) use ($secretKey): IngestionPayload {
            $expectedSignature = hash_hmac(
                'sha256',
                "{$payload->eventId}:{$payload->accountNumber}:{$payload->amount}",
                $secretKey
            );

            if (!hash_equals($expectedSignature, $payload->signature)) {
                throw new \SecurityException("Compromised payload signature for event: {$payload->eventId}");
            }

            return $payload;
        };
    }

    public static function calculateTax(float $taxRate): \Closure
    {
        return static function (IngestionPayload $payload) use ($taxRate): IngestionPayload {
            $deducted = $payload->amount - ($payload->amount * $taxRate);
            return new IngestionPayload(
                $payload->eventId,
                $payload->accountNumber,
                $deducted,
                $payload->signature,
                $payload->timestamp
            );
        };
    }

    public static function compose(callable ...$stages): \Closure
    {
        return static fn(mixed $input): mixed => array_reduce(
            $stages,
            static fn(mixed $carry, callable $stage): mixed => $stage($carry),
            $input
        );
    }
}

// ============================================================================
// 3. FIBER-BASED CONCURRENT WORKER RUNTIME
// ============================================================================

final class NonBlockingWorkerEngine
{
    /** @var SplQueue<Fiber> */
    private SplQueue $readyQueue;
    private int $processedCounter = 0;
    private const GC_COLLECTION_THRESHOLD = 500; // Trigger cycle collect every 500 tasks

    public function __construct(
        private readonly \Closure $transformationPipeline
    ) {
        $this->readyQueue = new SplQueue();
        
        // Optimasi Zend Engine GC: Matikan auto-run agresif di loop kritis
        gc_enable();
    }

    public function dispatch(IngestionPayload $payload): void
    {
        $fiber = new Fiber(function () use ($payload): void {
            try {
                // I/O Stage: Pre-validation simulated network call
                $this->nonBlockingSleep(5); // Simulated 5ms async I/O

                // Pure Functional Transformation Pipeline Execution
                /** @var IngestionPayload $processed */
                $processed = ($this->transformationPipeline)($payload);

                // I/O Stage: Database write simulation
                $this->nonBlockingSleep(10); // Simulated 10ms async database flush

                $result = new ProcessingResult($processed->eventId, true, $processed->amount);
                $this->handleSuccess($result);

            } catch (Throwable $e) {
                $result = new ProcessingResult($payload->eventId, false, 0.0, $e->getMessage());
                $this->handleFailure($result);
            }
        });

        $this->readyQueue->enqueue($fiber);
    }

    /**
     * Primitive Non-blocking Cooperative Delay
     */
    private function nonBlockingSleep(int $virtualMilliseconds): void
    {
        // Fiber menyerahkan eksekusi kembali ke scheduler loop utama
        $iterations = (int)ceil($virtualMilliseconds / 2);
        for ($i = 0; $i < $iterations; $i++) {
            Fiber::suspend();
        }
    }

    private function handleSuccess(ProcessingResult $res): void
    {
        echo "[SUCCESS] Event: {$res->eventId} | Settled: \${$res->settledAmount}\n";
    }

    private function handleFailure(ProcessingResult $res): void
    {
        echo "[FAILED]  Event: {$res->eventId} | Error: {$res->errorMessage}\n";
    }

    /**
     * Event Loop Execution Engine dengan Interleaved Memory Management
     */
    public function runLoop(): void
    {
        echo "[Engine] Event Loop running. Initial Memory: " . $this->getMemoryUsage() . "\n";

        while (!$this->readyQueue->isEmpty()) {
            $fiber = $this->readyQueue->dequeue();

            try {
                if (!$fiber->isStarted()) {
                    $fiber->start();
                } elseif ($fiber->isSuspended()) {
                    $fiber->resume();
                }

                if ($fiber->isSuspended()) {
                    $this->readyQueue->enqueue($fiber);
                } else {
                    // Task Lifecycle Berakhir
                    $this->processedCounter++;
                    $this->enforceMemoryBoundary();
                }
            } catch (Throwable $critical) {
                echo "[FATAL ENGINE ERROR] " . $critical->getMessage() . "\n";
            }
        }

        echo "[Engine] All tasks terminated. Final Memory: " . $this->getMemoryUsage() . "\n";
    }

    /**
     * ZMM Garbage Collection Boundary Management
     */
    private function enforceMemoryBoundary(): void
    {
        if ($this->processedCounter % self::GC_COLLECTION_THRESHOLD === 0) {
            // Evaluasi eksplisit graph cycle Zend Engine
            $collectedCycles = gc_collect_cycles();
            
            // Bersihkan Zend memory manager cache pools untuk mengembalikan memori OS
            gc_mem_caches();

            echo "--- [ZMM GC CYCLE TRIGGERED] Processed: {$this->processedCounter} | Cycles Cleared: {$collectedCycles} | Current Heap: " . $this->getMemoryUsage() . " ---\n";
        }
    }

    private function getMemoryUsage(): string
    {
        $bytes = memory_get_usage(true); // Real allocated memory from OS
        return sprintf('%.2f MB', $bytes / 1024 / 1024);
    }
}

// ============================================================================
// 4. BOOTSTRAPPER & EXECUTION SIMULATION
// ============================================================================

final class SecurityException extends \RuntimeException {}

$secretKey = "c8f93a1d94b0d87";

// Build Immutable Processing Pipeline
$pipeline = PipelineCore::compose(
    PipelineCore::verifySignature($secretKey),
    PipelineCore::calculateTax(0.12) // 12% Value Added Tax
);

$worker = new NonBlockingWorkerEngine($pipeline);

// Generate 1,500 payload batch untuk mensimulasikan heavy ingestion
for ($i = 1; $i <= 1500; $i++) {
    $evtId = "EVT-" . str_pad((string)$i, 6, "0", STR_PAD_LEFT);
    $amount = 100.0 * $i;
    
    // Generate valid HMAC signature
    $sig = hash_hmac('sha256', "{$evtId}:ACC-99:{$amount}", $secretKey);

    // Injeksikan satu data corrupt secara periodik untuk simulasi kegagalan murni
    if ($i % 300 === 0) {
        $sig = "invalid_signature_hash";
    }

    $payload = new IngestionPayload(
        $evtId,
        "ACC-99",
        $amount,
        $sig,
        new DateTimeImmutable()
    );

    $worker->dispatch($payload);
}

// Eksekusi Non-blocking Event Loop
$worker->runLoop();
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

```
          [Model Konkurensi & Paradigma PHP]
                     |
     +---------------+---------------+
     |                               |
[Fiber-Based Async]         [Traditional PHP-FPM]
  - Memory: Menetap           - Memory: Dihancurkan per req
  - Concurrency: Sangat Tinggi - Concurrency: Terbatas max_children
  - Danger: Leak akumulatif    - Danger: Bottleneck connection overhead
```

| Karakteristik | Imperative State Mutating (PHP-FPM Standard) | Pure Functional + Cooperative Fiber Runtime |
| :--- | :--- | :--- |
| **Throughput / Resources** | Rendah. 1 Proses FPM = 1 Request konkurensi. Terikat I/O blocking time. | Sangat Tinggi. Ribuan concurrent tasks terkelola di dalam 1 process heap. |
| **Overhead Alokasi Memori** | Tinggi secara global karena re-bootstrapping kernel framework di setiap HTTP request lifecycle. | Sangat Rendah. Framework di-boot sekali. Objek immutable kecil dialokasikan di ZMM dan diproses cepat. |
| **Kompleksitas Debugging** | Sangat Rendah. Call stack linier, error trace mudah diidentifikasi dari baris ke baris. | Tinggi. Call stack terpotong oleh `Fiber::suspend()`. Memerlukan tracing async khusus. |
| **Risiko Memory Leak** | Nol hingga Minimal. Garbage collection dibersihkan secara instan saat worker FPM me-reset memory pool. | Sangat Tinggi. Sedikit saja circular reference tersimpan di static array akan menyebabkan crash OOM. |
| **State Thread-Safety** | Terisolasi secara mutlak di tingkat memory process OS. | Aman dari multithreading race conditions, tetapi rentan terhadap *logical data bleeding* antar fiber. |

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. Circular Reference di Dalam Fiber Scope yang Ter-Suspend
Jika sebuah Fiber mengalokasikan objek circular reference (misalnya `$this->fiber = $fiber`) lalu melakukan suspend dan tidak pernah di-resume karena unhandled exception di Fiber lain, Zend Engine **tidak akan mendeteksi** siklus tersebut dalam loop normal. Stack context Fiber C tetap menahan referensi variabel lokal, membuat memori heap terisolasi secara permanen (*ZMM memory leak*).

#### 2. Arrow Functions & Implicit Scope Binding (`$this`)
Arrow functions (`fn() => ...`) otomatis meng-capture variabel dari lexical scope secara *by-value*, **termasuk objek `$this`**.
```php
class LeakGenerator {
    private array $cache = [];
    public function generate(): \Closure {
        // HATI-HATI: $this tertangkap secara implisit meskipun tidak dipakai langsung!
        return fn(int $x) => $x * 2;
    }
}
```
Jika closure ini dioper ke long-running service, instance `LeakGenerator` tidak akan pernah dimusnahkan oleh GC, menahan seluruh array `$cache` di memori selamanya.
*Mitigasi*: Selalu gunakan **`static fn()`** untuk seluruh pure higher-order functions agar engine mencegah binding otomatis terhadap `$this`.

#### 3. Uncaught Exception Di Dalam Fiber
Exception yang meledak di dalam Fiber dan tidak ditangkap oleh blok `try-catch` di dalam Fiber tersebut akan meloncat langsung ke level caller saat `Fiber::start()` atau `Fiber::resume()` dieksekusi. Ini dapat memutus rantai eksekusi keseluruhan event loop, membunuh proses daemon utama worker secara instan tanpa peringatan.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Kesalahan 1: Bergantung pada `gc_collect_cycles()` di Setiap Iterasi
```php
// ANTI-PATTERN: Menjalankan GC di setiap loop tick
while ($data = $source->read()) {
    $fiber->run();
    gc_collect_cycles(); // PERFORMA ANJLOK DRASTIS!
}
```
**Mengapa Salah?** Traversal cycle collector adalah operasi $O(N)$ yang mahal. Memeriksa ribuan node di Zend Root Buffer pada setiap iterasi mikro akan menyebabkan CPU throttling hingga 90% waktu hanya untuk mengecek heap kosong.  
**Solusi:** Terapkan threshold bertahap (*batching*): jalankan hanya setiap $N$ mutasi (misalnya 1.000 iterasi) atau pantau via `memory_get_usage()` delta.

#### Kesalahan 2: Memodifikasi Global / Static State dari Dalam Fiber
```php
// ANTI-PATTERN: Menggunakan static state di concurrency kooperatif
class Context {
    public static ?string $currentTraceId = null;
}

// Fiber 1
Context::$currentTraceId = "TRACE-AAA";
Fiber::suspend(); // Fiber 1 yield
echo Context::$currentTraceId; // BISA MENGHASILKAN "TRACE-BBB" JIKA FIBER 2 BERJALAN!
```
**Mengapa Salah?** Konkurensi kooperatif berbagi memori global yang sama dalam satu proses. Modifikasi terhadap variabel statis akan menginfiltrasi isolasi logika fiber lain (*data corruption*).  
**Solusi:** Gunakan Fiber-Local Storage (`FiberLocal` context pattern) atau passing state eksplisit melalui functional pipeline parameter.

#### Kesalahan 3: Asumsi bahwa `unset()` Langsung Mengembalikan Memori ke OS
```php
// SALAH PAHAM
unset($hugeArray);
// Mengira OS langsung menerima kembali RAM tersebut
```
**Mengapa Salah?** `unset()` hanya mengurangi `refcount` zval. Ketika `refcount == 0`, Zend Memory Manager (ZMM) mengembalikan memori tersebut ke internal heap pool PHP allocator, **bukan** ke Virtual Memory OS kernel (`glibc malloc/free`). OS tetap melihat proses PHP menggunakan RAM dalam jumlah besar sampai `gc_mem_caches()` dipanggil atau proses terminasi.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Declarations:** Selalu declare `strict_types=1` di baris pertama seluruh file tanpa pengecualian. Tipe data yang lemah (*weak typing*) merusak determinisme functional programming.
2.  **Stateless First-Class Callables:** Gunakan First-Class Callable Syntax PHP 8.1+ (`$this->method(...)` atau `MyClass::staticMethod(...)`) alih-alih instansiasi Closure manual berbasis string `[$obj, 'action']`. Ini di-resolve saat compile time via opcache slot.
3.  **Wajib Pure Readonly Record Objects:** Jangan pernah melewatkan array multidimensi mentah yang bersifat *mutable* ke dalam pipeline konkuren. Bungkus seluruh payload data transfer object (DTO) dengan `final readonly class`.
4.  **Deterministic Fiber Termination:** Selalu pastikan setiap jalur percabangan logika di dalam Fiber mencapai kondisi terminal. Jangan tinggalkan Fiber berstatus `isSuspended() === true` secara permanen di memori.
5.  **Batasi Ukuran Buffer Circular GC:** Atur konfigurasi php.ini:
    ```ini
    zend.enable_gc = 1
    ```
    Konfigurasikan memory metrics alert bila heap memory growth memiliki gradien positif linier selama 24 jam pengoperasian worker.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

#### 1. Menghindari Copy-On-Write Melalui Passing by Immutability
Meskipun terdengar paradoksal, membuat objek baru berukuran kecil (`new ValueObject(...)`) seringkali **lebih cepat dan hemat memori** di Zend VM dibandingkan melakukan mutasi associative array berukuran besar. 

Ketika array bermutasi, Zend Engine mengeksekusi deep re-allocation terhadap struktur `HashTable` dan `Bucket` internal:
```php
// Lambat: Memaksa alokasi bucket reallocation dan pemecahan COW
$bigArray['status'] = 'PROCESSED'; 

// Cepat & Ringan: PHP 8 mengalokasikan object struct fixed-size di memory pool
$newObject = $oldObject->withStatus('PROCESSED');
```

#### 2. Optimalisasi Alokasi Fiber Stack via C Allocator Tuning
Jika menjalankan puluhan ribu Fiber serentak, footprint alokasi stack internal C akan menguras memori OS. Pastikan sistem worker Anda mengonfigurasi batas memory limit secara ketat dan mengatur batching queue agar fiber yang hidup (*in-flight*) berada di ambang batas saturasi CPU cores.

#### 3. Tuning Garbage Collection
Gunakan fungsi diagnostik Zend Engine untuk mengukur efisiensi GC:
```php
$statusBefore = gc_status();
// [
//    "runs" => int,
//    "collected" => int,
//    "threshold" => int,
//    "roots" => int
// ]
```
Jika metrik `"roots"` tidak pernah mendekati `"threshold"`, mematikan manual invoke GC akan menghemat komputasi CPU cycles hingga 15-20%.

---

### SEKSI 16 — KEAMANAN & HARDENING

```
[Untrusted Input Source]
          |
          v
 [Payload Validation] ──► (Fail) ──► Instant Fiber Termination & Log Attack
          |
        (Pass)
          v
 [Pure Hash Verification] (Constant Time: hash_equals)
          |
          v
 [Fiber Sandboxing Context] (Isolated Error Boundary)
```

1.  **Timing-Attack Prevention pada Functional Pipeline:**
    Saat memvalidasi tanda tangan kriptografi atau token pada stream data asinkron, jangan gunakan operator persamaan standar (`==` atau `===`). Operator ini melakukan evaluasi byte-by-byte dan keluar pada karakter salah pertama (*early exit*), memungkinkan attacker mengukur selisih waktu eksekusi CPU (*timing leak*). Selalu gunakan `hash_equals()`.
2.  **Resource Exhaustion via Fiber Injection (DoS):**
    Di dalam arsitektur asinkron di mana Fiber di-spawn secara dinamis berdasarkan request external, pasang mekanisme **Backpressure Control**. Batasi kapasitas queue fiber aktif:
    ```php
    if ($readyQueue->count() >= MAX_CONCURRENT_FIBERS) {
        throw new ServerOverloadedException("Rate limit reached: Backpressure triggered");
    }
    ```
3.  **Memory Exfiltration Resistance:**
    Objek yang menahan data sensitif (API Keys, kredensial bank) tidak boleh tersimpan dalam closure capture variables (`use ($secret)`) dalam waktu lama. Terapkan metode penghapusan memori manual menggunakan `sodium_memzero()` pada string buffer sensitif setelah pipeline kalkulasi selesai dieksekusi.

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging konkurensi asinkron berbasis Fiber menghadirkan tantangan: stack trace tradisional tidak menampilkan jejak linier yang koheren karena eksekusi terputus saat Fiber ditangguhkan (*suspended*).

#### Teknik Tracing Asinkron Menggunakan Trace ID Injection
Kaitkan metadata konteks unik ke setiap siklus hidup fiber menggunakan custom wrapper:

```php
final class ObservableFiber
{
    private Fiber $fiber;
    private string $traceId;

    public function __construct(string $traceId, callable $callback)
    {
        $this->traceId = $traceId;
        $this->fiber = new Fiber(function () use ($callback): void {
            $this->log("Fiber [STARTED]");
            $callback();
            $this->log("Fiber [TERMINATED]");
        });
    }

    public function resume(): void
    {
        $this->log("Fiber [RESUMING]");
        $this->fiber->resume();
        if ($this->fiber->isSuspended()) {
            $this->log("Fiber [SUSPENDED]");
        }
    }

    private function log(string $event): void
    {
        error_log(sprintf(
            "[%s] [TraceID: %s] [Mem: %s] %s\n",
            date('Y-m-d H:i:s'),
            $this->traceId,
            memory_get_usage(),
            $event
        ));
    }
}
```

#### Diagnostic Metrics Logging
Pantau kesehatan internal Zend Memory Manager pada background daemon secara berkala dengan mengekstrak status alokasi:

```php
$memStats = [
    'allocated_heap' => memory_get_usage(false), // Memori yang dipakai zval aktual
    'real_system_allocated' => memory_get_usage(true), // Memori yang dipesan ZMM dari OS
    'peak_heap' => memory_get_peak_usage(false),
    'gc_roots_buffer' => gc_status()['roots'] ?? 0,
];
```

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Pure Functions**: Fungsi tanpa side effect. Output sepenuhnya ditentukan oleh argumen masukan.
*   **Immutability**: Hindari manipulasi internal state objek. Gunakan PHP 8.2 `readonly class` dan pattern `withProperty(...)` yang mengembalikan klon baru.
*   **Pipeline (`pipe`)**: Memadukan fungsi secara berantai di mana output fungsi pertama menjadi input fungsi kedua:
    $$\text{pipe}(f, g)(x) = g(f(x))$$
*   **Fiber Primitive**: Konkurensi kooperatif single-thread murni di level *user-space*.
    *   `$fiber = new Fiber($callable)`: Inisialisasi stack context.
    *   `$fiber->start(...)`: Memulai eksekusi sampai titik suspend pertama atau selesai.
    *   `Fiber::suspend($value)`: Membekukan C-stack Fiber, mengembalikan kontrol ke Caller.
    *   `$fiber->resume($value)`: Mengembalikan kontrol ke Fiber pada baris suspensi.
*   **Zend `zval`**: Struct C 16-byte yang membungkus seluruh variabel PHP.
*   **Copy-On-Write (COW)**: Memori array/string tidak digandakan saat di-assign ke variabel baru, melainkan menaikkan `refcount`. Gandaan fisik hanya dibuat saat salah satu variabel mengalami mutasi.
*   **Cycle Collection**: Algoritma Bacon-Rajan untuk mendeteksi siklus sirkular yang lolos dari refcounting instan. Bersihkan manual via `gc_collect_cycles()`.
*   **OS Memory Release**: Memanggil `unset()` tidak langsung mengembalikan RAM ke sistem operasi. Gunakan `gc_mem_caches()` untuk memangkas memory pools ZMM.

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Soal Basic (Tingkat Dasar)

1.  **Apa yang terjadi pada struktur internal Zend Memory Manager ketika kita menjalankan kode berikut:**
    ```php
    $x = ["foo" => "bar"];
    $y = $x;
    ```
    *   A. Array diduplikasi sepenuhnya di memori heap sistem.
    *   B. Array baru dibuat dengan pointer string yang sama.
    *   C. Tidak ada alokasi data array baru; `refcount` pada struct array bertambah menjadi 2.
    *   D. Variabel `$y` diubah menjadi reference pointer mutlak (`&`).
2.  **Manakah definisi yang paling akurat mengenai *Cooperative Concurrency* pada Fiber PHP 8.1+?**
    *   A. OS kernel memotong eksekusi kode setiap beberapa milidetik untuk context switching.
    *   B. Task/Fiber berjalan terus menerus hingga ia secara sukarela memanggil `Fiber::suspend()` atau selesai dieksekusi.
    *   C. Proses otomatis dijalankan di multi-core processor secara paralel.
    *   D. Fiber berjalan sebagai daemon thread independen di luar lifecycle engine PHP.
3.  **Apakah efek dari deklarasi `readonly class` pada PHP 8.2 terhadap mutasi properti?**
    *   A. Nilai properti dapat diubah maksimal satu kali setelah inisialisasi.
    *   B. Seluruh properti tidak dapat dimodifikasi setelah proses konstruksi objek selesai; runtime melempar Error jika dimutasi.
    *   C. Properti hanya dapat diakses melalui metode getter.
    *   D. Properti otomatis berubah menjadi string immutable.
4.  **Kapan Zend Reference Counting Engine menghapus memori sebuah variabel secara instan?**
    *   A. Saat fungsi `gc_collect_cycles()` dipanggil.
    *   B. Saat `refcount` zval mencapai angka 0.
    *   C. Saat skrip PHP berhenti berjalan.
    *   D. Setiap kali variabel dioper ke fungsi lain.
5.  **Manakah fungsi bawaan PHP yang digunakan untuk menyusun Higher-Order Pipeline dari koleksi fungsi?**
    *   A. `array_map`
    *   B. `array_filter`
    *   C. `array_reduce`
    *   D. `array_walk`

#### Soal Intermediate (Tingkat Menengah)

6.  **Perhatikan kode berikut. Mengapa kode ini dapat memicu memory leak pada long-running process?**
    ```php
    class EventHub {
        public static array $listeners = [];
        public function register(string $event): void {
            self::$listeners[$event][] = function() {
                return $this->handle();
            };
        }
    }
    ```
    *   A. Static array tidak didukung di PHP CLI.
    *   B. Anonymous function secara implisit meng-capture `$this`, mencegah garbage collector membersihkan instance `EventHub`.
    *   C. Closure menggunakan metode private.
    *   D. Array keys tidak di-unset menggunakan string hashing.
7.  **Apa perbedaan mendasar antara status `Fiber::isTerminated()` dan `Fiber::isSuspended()`?**
    *   A. `isSuspended` berarti proses crash, `isTerminated` berarti proses berhasil.
    *   B. `isSuspended` menandakan C-stack dibekukan sementara dan dapat dilanjutkan via `resume()`, sedangkan `isTerminated` berarti closure fiber telah keluar (*return*) atau melempar fatal exception.
    *   C. Keduanya memiliki arti yang sama secara internal di Zend Engine.
    *   D. `isTerminated` dipicu oleh operating system interrupt signal.
8.  **Bagaimana algoritma Bacon-Rajan (Cycle Collector) di PHP mendeteksi circular reference murni yang sudah menjadi garbage?**
    *   A. Menghitung total alokasi memori yang tersisa di OS kernel.
    *   B. Melakukan simulasi pengurangan refcount internal pada graf simpul yang dicurigai (root buffer); jika refcount-nya turun menjadi nol mutlak, simpul dikonfirmasi sebagai dead cycle.
    *   C. Memeriksa apakah nama variabel diawali dengan simbol pointer.
    *   D. Memindai call-stack traceback secara mundur (*reverse execution*).
9.  **Apa dampak memanggil `gc_mem_caches()` dalam arsitektur high-performance long-running worker?**
    *   A. Memaksa Zend Engine melepaskan memory pools yang kosong kembali ke OS Memory Allocator, mengurangi physical footprint RAM process.
    *   B. Menghapus seluruh file opcache di disk.
    *   C. Mematikan fitur garbage collector permanen.
    *   D. Menyetel ulang seluruh fiber queue menjadi status nol.
10. **Bagaimana cara mencegah arrow function `fn()` meng-capture `$this` secara implisit?**
    *   A. Menambahkan parameter dummy `$this = null`.
    *   B. Mendeklarasikan arrow function dengan prefix keyword `static fn()`.
    *   C. Menggunakan tanda kurung ganda `((fn() => ...))`.
    *   D. Memanggil `unset($this)` di baris pertama arrow function.

#### Kunci Jawaban & Rasional Singkat
1.  **C** — PHP mengimplementasikan Copy-On-Write (COW). Memory heap hanya dishare dan refcount bertambah 1.
2.  **B** — Konkurensi fiber bersifat kooperatif murni di level application userland code; context switch hanya terjadi saat eksplisit yield/suspend.
3.  **B** — `readonly class` mengunci seluruh properti dari mutasi setelah fase construction lifecycle berakhir.
4.  **B** — Destruksi memori instan pada PHP didorong oleh penurunan refcount hingga menyentuh 0.
5.  **C** — `array_reduce` adalah fondasi fungsional untuk mengonsolidasi array ekspresi callable menjadi fungsi pipeline terpadu (`pipe`).
6.  **B** — Lexical binding otomatis mengikat `$this` ke closure instance, menyebabkan instance objek tertahan selamanya di static registry `$listeners`.
7.  **B** — `isSuspended()` merepresentasikan pause sementara di tengah eksekusi, sementara `isTerminated()` menandakan eksekusi fiber telah selesai sepenuhnya.
8.  **B** — Cycle collection menguji isolated graph dengan virtual refcount subtraction untuk membuktikan bahwa node-node tersebut hanya saling merujuk satu sama lain tanpa pointer eksternal dari live scope.
9.  **A** — `gc_mem_caches()` menginstruksikan ZMM untuk membersihkan free-lists buffer dan mengembalikan blok chunk memori ke kernel OS.
10. **B** — Keyword `static` mencegah compiler Zend menyematkan context pointer `$this` ke dalam closure symbol table.

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Deskripsi Tantangan
Bangun sebuah library mini bernama **"FiberStream-Engine"**: Sebuah sistem ETL (Extract, Transform, Load) mikro berbasis Event Loop dan Fiber yang mampu memproses stream data CSV besar secara non-blocking, menerapkan validasi fungsional murni, dan secara deterministik membatasi penggunaan RAM agar tidak melebihi **20 Megabytes**, terlepas dari seberapa besar ukuran file input.

#### Spesifikasi Fungsional:
1.  **Extract (Source)**:
    *   Buat generator fungsional yang membaca file CSV berekstensi ribuan baris baris demi baris menggunakan stream buffer native (`fopen`, `fgetcsv`).
    *   Setiap baris yang diekstrak harus dibungkus ke dalam *Immutable Record Class* (`RowRecord`).
2.  **Transform (Functional Core Pipeline)**:
    *   Terapkan fungsi `pipe()` untuk mengombinasikan minimal 3 *pure transformations*:
        *   Sanitasi string (strip tags, trim whitespace).
        *   Transformasi data (konversi zona waktu tanggal ke UTC, kalkulasi formula numerik).
        *   Validasi skema ketat (melempar domain exception jika ada kolom kosong).
3.  **Concurrency Layer (Fiber Engine)**:
    *   Implementasikan scheduler internal yang memproses batch baris CSV menggunakan `Fiber`.
    *   Scheduler harus mampu membatasi konkurensi (misal: maksimal 50 Fiber aktif bersamaan). Jika antrean penuh, scheduler harus menunda pembacaan file hingga ada Fiber yang selesai (*backpressure management*).
4.  **Memory Guard (ZMM Hardening)**:
    *   Pantau memory footprint menggunakan `memory_get_usage(true)`.
    *   Pasang logic automasi: Jika garbage roots buffer mencapai ambang batas atau setiap pemrosesan kelipatan 500 baris, lakukan siklus pembersihan terpadu (`gc_collect_cycles()` dan `gc_mem_caches()`).
    *   Tulis log berkala yang membuktikan bahwa memory usage tetap konstan (*flat memory line*) dari awal baris pertama hingga baris ke-100.000.

#### Kriteria Keberhasilan Praktikum:
*   Tidak ada kebocoran memori (Grafik alokasi RAM flat/stabil di bawah batas limit 20MB).
*   Zero fatal unhandled exceptions saat parsing data error.
*   Seluruh operasi transformasi data 100% bebas mutasi state (pure immutable objects).
*   Kode mematuhi standar PSR-12, menggunakan `declare(strict_types=1)`, dan mengimplementasikan strict return types pada seluruh closure.