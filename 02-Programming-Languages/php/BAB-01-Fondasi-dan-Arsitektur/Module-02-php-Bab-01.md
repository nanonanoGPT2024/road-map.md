# Kurikulum Rekayasa Perangkat Lunak Enterprise: PHP Modern
## Bab 01: Fondasi dan Arsitektur
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Menganalisis** arsitektur internal Zend Engine 4 (PHP 8.2/8.3+), mencakup representasi memori `zval`, mekanisme *Copy-on-Write* (COW), *reference counting*, dan *Cyclic Garbage Collector*.
*   **Mengonfigurasi dan Mengoptimasi** *OPcache*, *JIT (Just-In-Time) Compiler*, dan *Preloading* untuk beban kerja enterprise berlatensi rendah.
*   **Merancang dan Menyetel** arsitektur runtime PHP-FPM (*FastCGI Process Manager*) berbasis *dynamic/static/on-demand process management* guna mencegah *process starvation* dan *memory leak*.
*   **Mengimplementasikan** pola *memory-efficient processing* menggunakan *Generators*, *Streams*, dan *Fibers* (Cooperative Multitasking) untuk I/O konkurensi tinggi.
*   **Mendiagnosis** anomali performa produksi (OOM, lock contention, zombie process) menggunakan profiling level kernel/runtime (`strace`, `pmap`, Blackfire/Xdebug Profiler).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib memahami:
*   Sintaks modern PHP 8.x (*Typed Properties*, *Attributes*, *Enums*, *Constructor Promotion*, *Match Expressions*).
*   Dasar sistem operasi Linux: POSIX signals, manajemen proses (`fork`, `kill`, `wait`), soket Unix domain vs TCP, dan alokasi memori virtual (`mmap`, `brk`).
*   Konsep protokol HTTP dan FastCGI binary protocol.
*   Tooling: Docker Engine, PHP 8.2/8.3 CLI + FPM, Composer, Linux debugging tools (`strace`, `valgrind`, `htop`).

---

### 3. Concept & Internal Architecture

#### 3.1 Anatomi Memori: Zend Engine, `zval`, dan Copy-on-Write (COW)
PHP adalah bahasa dengan *garbage-collected dynamic typing* yang dieksekusi di atas Zend Engine (ZE). Struktur data paling fundamental di level internal C adalah `zval` (Zend Value). Pada PHP 8.x, struktur `zval` dioptimasi menjadi 16 byte pada arsitektur 64-bit:

```c
struct _zval_struct {
    zend_value        value;            /* 8 bytes: pointer atau scalar integer/double */
    union {
        struct {
            ZEND_ENDIAN_LOHI_3(
                zend_uchar    type,     /* Type tag: IS_STRING, IS_ARRAY, IS_OBJECT, dll */
                zend_uchar    type_flags,
                union {
                    uint16_t  extra;    /* Context-specific flags */
                } u;
            )
        } v;
        uint32_t type_info;
    } u1;
    union {
        uint32_t     next;             /* Hash collision chain */
        uint32_t     cache_slot;       /* Literal cache slot */
        uint32_t     opline_num;       /* Execution counter */
        uint32_t     lineno;           /* Line number */
        uint32_t     num_args;         /* Argument count */
    } u2;                              /* 4 bytes */
};
```

Komponen nilai kompleks (seperti `zend_string`, `zend_array`, `zend_object`) dipisahkan ke heap dan diakses via pointer di dalam `zend_value`. Semua struktur ini memuat header referensi:

```c
struct _zend_refcounted_h {
    uint32_t         refcount;         /* 32-bit counter */
    union {
        struct {
            ZEND_ENDIAN_LOHI_3(
                zend_uchar    type,
                zend_uchar    flags,    /* IS_STR_PERSISTENT, GC_COLLECTABLE, dll */
                uint16_t      gc_info   /* Buffer root status untuk GC */
            )
        } v;
        uint32_t type_info;
    } u;
};
```

##### Mekanisme Copy-on-Write (COW):
Saat variabel `$b = $a` dieksekusi, Zend Engine **tidak** menduplikasi blok memori. Pointer `zend_value` disalin secara dangkal (*shallow copy*), dan `refcount` pada header referensi dinaikkan 1 level. Alokasi memori fisik baru dan duplikasi data (*deep copy*) hanya terjadi saat salah satu variabel mengalami mutasi (*write*).

```
State 1: Assignment ($a = [1, 2]; $b = $a;)
+---------------+          +---------------------------+
| zval ($a)     | -------> | zend_array                |
+---------------+          | - refcount: 2             |
| zval ($b)     | -------> | - data: [1, 2]            |
+---------------+          +---------------------------+

State 2: Mutation ($b[] = 3;) -> Copy-on-Write Triggered
+---------------+          +---------------------------+
| zval ($a)     | -------> | zend_array (Original)     |
+---------------+          | - refcount: 1             |
                           | - data: [1, 2]            |
                           +---------------------------+
+---------------+          +---------------------------+
| zval ($b)     | -------> | zend_array (Duplicated)   |
+---------------+          | - refcount: 1             |
                           | - data: [1, 2, 3]         |
                           +---------------------------+
```

#### 3.2 Cyclic Reference Garbage Collection (Concurrent Cycle Collector)
Refcounting standar gagal membebaskan memori pada kasus *circular reference* (Objek A merujuk Objek B, Objek B merujuk Objek A, lalu referensi lokal keduanya dihapus). Zend GC mengimplementasikan algoritma berbasis variasi *Bacon & Rajan (2001)*:

1.  **Possible Roots Buffer**: Setiap kali `refcount` suatu struktur kompleks turun namun tidak mencapai 0, Zend GC menandainya sebagai "Purple" (kandidat root potensial) dan menyimpannya di root buffer (default ukuran: 10.001 entri).
2.  **Marking Phase (Trial Deletion)**: Saat buffer penuh, GC menelusuri graph memori dari root, men-simulasikan pengurangan `refcount` untuk setiap child link (ditandai "Grey").
3.  **Scan Phase**: Jika `refcount` objek mencapai murni 0 setelah simulasi, objek tersebut ditandai "White" (garbage). Jika `refcount` > 0, statusnya dikembalikan dan ditandai "Black" (alive).
4.  **Sweep Phase**: Semua node "White" dilepaskan dari memori fisik via `zend_mm` (Zend Memory Manager).

#### 3.3 Zend Memory Manager (ZMM)
ZMM mengisolasi engine dari alokasi langsung via OS `malloc()` demi latensi dan kontrol siklus hidup *per-request*.
*   **Slab Allocator**: Membagi memori ke dalam Chunk (2MB), Page (4KB), dan Slot alokasi terstandarisasi untuk objek kecil (*small allocations* < 3KB).
*   **e* Family API**: `emalloc()`, `efree()`, `ecalloc()`. Memori yang dialokasikan via ZMM secara otomatis divalidasi dan di-flush secara agresif di akhir request (`RSHUTDOWN`), mencegah *system-wide leak* permanen sekalipun kode pengguna memiliki *logical leak*.

#### 3.4 OPcache, Preloading, & JIT Engine
*   **OPcache Engine**: Mengeliminasi fase Parsing, Lexing, dan Compilation. Hasil kompilasi opcode AST disimpan dalam memori bersama (*shared memory* via IPC/SHM). Worker FPM membaca langsung opcode dari memory segment ini.
*   **Preloading (PHP 7.4+)**: Mengkompilasi dan mem-binding file kelas ke memori persistent Zend Engine saat startup server (sebelum worker di-*fork*). Seluruh class/interface/trait tersedia secara global di semua request tanpa eksekusi `require`/autoloading via composer, serta tanpa biaya pengecekan modifikasi file (`stat()`).
*   **JIT (Tracing JIT vs Function JIT)**: PHP 8 memperkenalkan DynASM compiler. 
    *   *Function JIT*: Memeriksa unit function utuh.
    *   *Tracing JIT*: Memantau *hot execution loops* pada level runtime. Opcode yang berulang diterjemahkan langsung ke *native machine code* (x86-64 / ARM), mem-bypass *Virtual Machine evaluation loop* (FETCH-DECODE-EXECUTE).

---

### 4. Why & What

| Paradigma / Runtime | Shared-Nothing (PHP-FPM) | Event-Driven (Node.js/Swoole) | Multithreaded VM (Java/Go) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Isolasi total per-request; worker di-*fork* dan di-recycle. | Single/Multi-threaded Event Loop non-blocking I/O. | OS-level threads / Green threads (Goroutines) sharing heap memory. |
| **State Retention** | Nol status global di memori antar-request (stateless by design). | Persistent memory state (rentan leak variabel global). | Persistent static heap; mutasi butuh locks/mutex synchronization. |
| **Kegagalan Crash** | Isolasi fatal error; 1 request tewas tidak menjatuhkan worker lain. | Unhandled exception dapat mematikan seluruh instance process. | Panic dapat crash instance jika tidak terisolasi dalam goroutine/thread boundary. |
| **Resource Cost** | Baseline footprint per request lebih tinggi (proses overhead). | Footprint footprint memori rendah, performa raw I/O sangat tinggi. | Alokasi memori tinggi di startup, sangat efisien di runtime execution. |

#### Mengapa PHP Mempertahankan Shared-Nothing Architecture?
1.  **Zero Contention Concurrency**: Tiap request dieksekusi dalam ruang memori privat. Tidak ada risiko *race condition*, *deadlock*, atau degradasi performa akibat *synchronized locking* di level heap aplikasi.
2.  **Resilience**: Kerusakan memori atau memory leak akibat *third-party libraries* (C extensions) terisolasi penuh dan musnah begitu request mencapai terminasi.
3.  **Horizontal Scale Out**: Paradigma ini memaksa engineer menulis arsitektur stateless murni, menyederhanakan autoscaling multi-node di Kubernetes.

---

### 5. How: Request Execution Workflow Detail

```
   [ Client Request ]
           │
           ▼
   ┌───────────────┐
   │ NGINX / Envoy │ (Reverse Proxy / TLS Termination)
   └───────┬───────┘
           │ Unix Domain Socket / FastCGI Protocol
           ▼
┌─────────────────────────────────────────────────────────────┐
│ PHP-FPM Master Process (Root/Privileged)                    │
│   ├── Spawns/Manages Worker Pools                           │
│   └── Shared OPcache Memory Segment (SHM)                   │
└──────────┬──────────────────────────────────────────────────┘
           │ Hand-off file descriptor
           ▼
┌─────────────────────────────────────────────────────────────┐
│ PHP-FPM Worker Process (Unprivileged)                       │
│                                                             │
│ 1. MINIT  (Module Init - Ran once on worker boot)           │
│ 2. RINIT  (Request Init - Memory Arena initialized via ZMM) │
│                                                             │
│ 3. Opcode Execution Phase:                                  │
│    ├── Check OPcache Shared Memory                          │
│    │     ├─ HIT: Fetch bytecodes directly                   │
│    │     └─ MISS: Lexer -> Parser -> AST -> Zend Opcode     │
│    ├── Check JIT Buffer:                                    │
│    │     ├─ HIT: Execute Native CPU Instructions (x86_64)   │
│    │     └─ MISS: Run via Zend VM Interpreter Loop          │
│                                                             │
│ 4. RSHUTDOWN (Request Shutdown):                            │
│    ├── Run destructors (`__destruct`)                       │
│    ├── Flush output buffers                                 │
│    ├── Clear root GC buffer                                 │
│    └── ZMM Arena Free: Instantly reclaim all `emalloc`      │
│                                                             │
│ 5. MSHUTDOWN (Module Shutdown - Ran only on Worker Death)   │
└─────────────────────────────────────────────────────────────┘
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Arsitektur Restoran Kontrak Cepat (PHP-FPM) vs Bar Bersama (Node.js/Go)
*   **PHP-FPM**: Seperti ruangan kantor notaris swasta. Tiap klien masuk ke bilik mandiri, dilayani satu staf. Klien memakai meja tulis baru. Jika klien menumpahkan kopi (memory leak/fatal error), klien selesai, bilik dibakar bersih (ZMM purge), meja baru disediakan untuk klien selanjutnya. Tidak ada kontaminasi antar klien.
*   **Zval & COW**: Bayangkan Anda memesan buku pedoman. Alih-alih mencetak buku baru, kantor memberi Anda buku yang sama dengan cap "Buku #123, Pembaca: 2". Begitu Anda ingin mencoret-coret catatan di halaman 5, kantor seketika memfotokopi buku tersebut, memberi Anda salinan baru, dan membiarkan pembaca pertama tetap membaca buku aslinya.

```
       PHP-FPM Pool Architecture: Master - Worker Distribution

               +----------------------------------+
               |      PHP-FPM Master Process      |
               |       (PID: 1000 - Root)         |
               +-----------------+----------------+
                                 |
        +------------------------+------------------------+
        | epoll / kqueue signal monitoring                |
        v                                                 v
+-------------------------------+ +-------------------------------+
|     Worker 1 (PID: 1001)      | |     Worker 2 (PID: 1002)      |
|  Status: BUSY (Handling Req)  | |  Status: IDLE (Waiting)       |
|  Memory: [ ZMM Local Arena ]  | |  Memory: [ Clean Arena ]      |
+---------------+---------------+ +---------------+---------------+
                |                                 |
                +----------------+----------------+
                                 |
                                 v
               +----------------------------------+
               |  Shared Memory (SHM) Segment     |
               |  - Preloaded Class Structures    |
               |  - Compiled OPcache Hash Tables  |
               |  - JIT Compiled Native Machine   |
               +----------------------------------+
```

---

### 7. Simple & Practical Examples

#### 7.1 Simple Example: Memvalidasi Copy-On-Write dan Destruksi Refcount
Mengamati mutasi memori internal secara langsung via `debug_zval_dump()`:

```php
<?php
declare(strict_types=1);

// Alokasi string besar (Heap Memory)
$initialString = str_repeat("EnterprisePayload", 1024); // ~17 KB

echo "--- Status Awal (\$initialString) ---\n";
debug_zval_dump($initialString);
// Output menunjukkan refcount: 1

$referenceCopy = $initialString;

echo "\n--- Pasca Duplikasi (\$referenceCopy = \$initialString) ---\n";
debug_zval_dump($initialString);
// Output menunjukkan refcount: 2 (Memori TIDAK diduplikasi, pointer identik)

// Trigger Copy-On-Write via mutasi
$referenceCopy .= "_MODIFIED";

echo "\n--- Pasca Mutasi Variabel Salinan (COW Dipicu) ---\n";
echo "Original:\n";
debug_zval_dump($initialString); // refcount turun kembali ke 1
echo "Modified:\n";
debug_zval_dump($referenceCopy);  // memory block baru dialokasikan, refcount: 1
```

#### 7.2 Practical Example: Zero-Allocation Streaming Parser vs In-Memory Hydration
Memproses export data analitik raksasa (>5GB) tanpa melanggar batasan `memory_limit = 64M` menggunakan generator dan low-level stream cursor:

```php
<?php
declare(strict_types=1);

namespace Enterprise\Infrastructure\DataStream;

use Generator;
use RuntimeException;
use SplFileObject;

final readonly class LargePayloadStreamReader
{
    /**
     * Membaca file baris demi baris menggunakan unbuffered generator iterator.
     * Menggunakan memori konstan < 2MB tanpa memedulikan ukuran file.
     *
     * @return Generator<int, array<string, mixed>>
     */
    public function streamRecords(string $absolutePath): Generator
    {
        if (!file_exists($absolutePath) || !is_readable($absolutePath)) {
            throw new RuntimeException("Target log/data file tidak dapat diakses: {$absolutePath}");
        }

        // Buka file via SplFileObject (menggunakan stream C-level runtime zend)
        $file = new SplFileObject($absolutePath, 'rb');
        $file->setFlags(SplFileObject::READ_CSV | SplFileObject::SKIP_EMPTY | SplFileObject::DROP_NEW_LINE);
        $file->setCsvControl(',', '"', '\\');

        $headers = [];
        $rowNumber = 0;

        foreach ($file as $row) {
            if ($rowNumber === 0) {
                // Baris pertama diasumsikan sebagai CSV Header
                $headers = $row;
                $rowNumber++;
                continue;
            }

            if ($row === [null] || empty($row)) {
                continue;
            }

            // Yield record sebagai key-value map terasosiasi
            // Memory zval baris sebelumnya dibebaskan seketika oleh ZMM pada next iteration
            yield $rowNumber => array_combine($headers, $row);
            $rowNumber++;
        }
    }
}

// Eksekusi Konsumsi
$reader = new LargePayloadStreamReader();
$stream = $reader->streamRecords('/var/log/enterprise_massive_transactions.csv');

foreach ($stream as $index => $record) {
    // Simulasi pemrosesan bisnis per baris
    if ($index % 50000 === 0) {
        $memoryUsage = memory_get_usage(true) / 1024 / 1024;
        echo sprintf("Record ke-%d diproses. Penggunaan Memori Heap: %0.2f MB\n", $index, $memoryUsage);
    }
}
```

---

### 8. Real-World Case Study: High-Throughput Fintech Webhook Gateway

#### Masalah Produksi
Sebuah Payment Gateway Tier-1 menerima lonjakan transaksi webhook kilat (*flash sale* perbankan) dengan trafik **25.000 Request per Second (RPS)**. Infrastruktur eksisting di Kubernetes (20 Pods, PHP 8.2-FPM) tumbang dengan indikasi:
1.  **HTTP 502 Bad Gateway / 504 Gateway Timeout**.
2.  NGINX Error Log: `connect() to unix:/var/run/php-fpm.sock failed (11: Resource temporarily unavailable)`.
3.  Pod restart acak akibat *Out-Of-Memory (OOMKilled)* oleh Linux Kernel cgroup controller.

#### Analisis Akar Masalah (Root Cause Analysis)
1.  **FPM Pool Misconfiguration**: `pm = dynamic` dikonfigurasi dengan `pm.max_children = 250` per pod. Pada 20 pod, ini menghasilkan 5.000 proses yang bersaing memperebutkan CPU. Terjadi *massive context-switching* pada Linux CFS Scheduler.
2.  **Memory Limit Spikes**: Default `memory_limit = 512M`. Kode webhook me-load serialization graph penuh via Doctrine ORM. 250 worker x 512MB = potensi kebutuhan memori 128GB per pod, sedangkan Pod Memory Request/Limit Kubernetes hanya dialokasikan 8GB.
3.  **OPcache Throttling**: Flag `opcache.validate_timestamps=1` aktif di produksi, memaksa FPM mengecek sistem file stat disk di setiap request secara sinkron via system call `stat()`.

#### Solusi Arsitektur & Implementasi Tuning

##### Langkah 1: Rekonfigurasi PHP-FPM ke Mode `static`
Mode `static` mengeliminasi overhead sistem operasi saat melakukan dynamic fork worker under load. Formula penentuan worker:

$$\text{pm.max\_children} = \frac{\text{Total RAM Pod} - \text{Baseline Buffer (20\%)}}{\text{Average Process RSS}}$$

Dengan rata-rata proses webhook yang sudah dioptimasi memakan 35MB:
*   Total RAM: 8192 MB - Buffer 1638 MB = 6554 MB.
*   `pm.max_children` = $6554 / 35 \approx 180$.

`/usr/local/etc/php-fpm.d/www.conf`:
```ini
[www]
user = www-data
group = www-data
listen = /var/run/php-fpm.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660
listen.backlog = 65535

pm = static
pm.max_children = 180
pm.max_requests = 10000 ; Mengatasi akumulasi kebocoran minor pada third-party extensions

; Isolasi error & slow transaction profiling
request_terminate_timeout = 5s
catch_workers_output = yes
decorate_workers_output = no
```

##### Langkah 2: Production OPcache & JIT Hardening
`/usr/local/etc/php/conf.d/10-opcache.ini`:
```ini
zend_extension=opcache.so
opcache.enable=1
opcache.enable_cli=0
opcache.memory_consumption=512
opcache.interned_strings_buffer=64
opcache.max_accelerated_files=30000
opcache.validate_timestamps=0 ; HARD REQUIREMENT UNTUK HIGH CONCURRENCY
opcache.save_comments=0
opcache.enable_file_override=1

; Preload seluruh core classes domain ke level Zend Memory
opcache.preload=/var/www/html/config/preload.php
opcache.preload_user=www-data

; JIT Configuration: 1254 (Tracing Mode, Aggressive Profile Guided)
opcache.jit=tracing
opcache.jit_buffer_size=128M
```

##### Langkah 3: Preload Script
`/var/www/html/config/preload.php`:
```php
<?php
declare(strict_types=1);

// Wajib hanya memuat file murni class/interface tanpa dynamic bootstrap execution
$preloadFiles = [
    '/var/www/html/vendor/autoload.php',
    '/var/www/html/src/Kernel.php',
    '/var/www/html/src/Webhook/Infrastructure/Controller/PaymentWebhookController.php',
];

foreach ($preloadFiles as $file) {
    opcache_compile_file($file);
}
```

#### Hasil Benchmark Pasca Optimasi
*   **P99 Latency**: Berkurang dari 2.450ms menjadi **18ms**.
*   **Throughput**: 25.000 RPS ditangani dengan stabil tanpa satupun *socket dropped* atau *502 Bad Gateway*.
*   **Pod Memory Usage**: Rata-rata 4.2GB dari limit 8GB (kestabilan penuh tanpa indikasi OOMKilled).

---

### 9. Trade-offs

| Parameter Desain | Opsi A: `pm = static` | Opsi B: `pm = dynamic` | Analisis Konsekuensi Teknikal |
| :--- | :--- | :--- | :--- |
| **Footprint Memori** | Tinggi secara persisten (alokasi instan sejak startup). | Elastis (rendah saat idle, naik saat beban meningkat). | Opsi A memotong risiko OOM dinamis dan thrashing OS allocator. Opsi B hemat di VM bersama, buruk untuk Kubernetes. |
| **Request Latency** | Ultra Rendah & Konsisten. | Variatif (terjadi latency spike saat FPM me-`fork()` proses baru). | Pada beban lonjakan (*flash burst*), Opsi B menghasilkan *latency penalty* sebesar 15ms-100ms per *fork event*. |
| **Konfigurasi OPcache** | `validate_timestamps=0` | `validate_timestamps=1` | Nilai `0` membutuhkan restart service/reload signal saat deployment, tapi menghilangkan I/O `stat()` syscall pada setiap request. |
| **Model Preloading** | Aktif (`opcache.preload`) | Non-Aktif | Preloading mempercepat booting framework ~30-50%, tetapi perubahan source code menuntut full FPM Master restart (bukan sembarang graceful reload). |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: Memory Exhaustion akibat Global Static State Leak
```php
// CONTOH SALAH (ANTI-PATTERN)
final class AuditContextHolder 
{
    public static array $auditLog = []; // Tumbuh tanpa batas selama worker hidup di CLI/RoadRunner/Swoole

    public static function log(string $msg): void {
        self::$auditLog[] = $msg;
    }
}
```
*   **Penyebab**: Di ekosistem FPM, data static mati bersama request. Namun saat diuji coba pada worker persistent CLI, queue consumer, atau jika `pm.max_requests` di-set terlalu tinggi, struktur ini terus membesar, menghabisi heap ZMM.
*   **Troubleshooting Tool**: Gunakan `gc_mem_caches()` dan amati memory footprint via `memory_get_usage()`.
*   **Solusi Benar**: Gunakan dependency injection dengan lifecycle scoped atau pastikan eksplisit reset method pada event listener request teardown.

#### Kasus 2: OPcache Hash Table Collision & Interned Strings Buffer Exhaustion
*   **Gejala**: CPU tiba-tiba melonjak 100% tanpa pertambahan trafik. Aplikasi terasa melambat drastis.
*   **Pemeriksaan**:
    ```php
    print_r(opcache_get_status(false)['interned_strings_usage']);
    ```
*   **Akar Masalah**: Buffer interned string habis (`buffer_size` terlampaui), menyebabkan Zend Engine beralih ke string allocation individual di setiap worker tanpa reuse shared pointer.
*   **Solusi**: Naikkan `opcache.interned_strings_buffer` dari default 8MB menjadi 64MB atau 128MB untuk aplikasi dengan basis codebase besar (seperti Symfony/Laravel).

---

### 11. Best Practices (Production Checklist)

#### Keamanan dan Konfigurasi Runtime
- [ ] `expose_php = Off` terpasang di `php.ini` produksi.
- [ ] `display_errors = Off`, `log_errors = On`, `error_reporting = E_ALL`.
- [ ] `memory_limit` disesuaikan ketat per kebutuhan workload (misal: 64MB untuk microservice API, bukan 512MB membabi-buta).
- [ ] `max_execution_time` dibatasi secara ketat (misal: 5-10 detik) guna memutus thread deadlock atau hung socket downstream.

#### Performa FPM & OPcache
- [ ] `pm = static` dikonfigurasi pada containerized infrastructure (Docker / K8s).
- [ ] `opcache.validate_timestamps = 0` diterapkan di image produksi immutable.
- [ ] FastCGI listen socket menggunakan **Unix Domain Sockets** jika NGINX & FPM berada dalam 1 host/container, atau disetel dengan tuning TCP backlog mumpuni jika via loopback TCP: `net.core.somaxconn = 65535`.
- [ ] Script preloading dikompilasi tanpa adanya dependensi ke state konfigurasi dinamis (misal: database credentials).

---

### 12. Hands-on Practice: Membangun, Menyetel & Mendiagnosis Low-Level FPM Environment

Simpan semua file praktikum di direktori: `hands-on/m02/`

#### Step 1: Buat Struktur Project
```bash
mkdir -p hands-on/m02/app
cd hands-on/m02
```

#### Step 2: Konfigurasi Dockerfile Berbasis Alpine Enterprise
Buat file `hands-on/m02/Dockerfile`:
```dockerfile
FROM php:8.3-fpm-alpine

RUN apk add --no-cache linux-headers procps

# Konfigurasi OPcache
RUN docker-php-ext-enable opcache

# Copy custom configs
COPY docker-php-ext-opcache.ini /usr/local/etc/php/conf.d/
COPY php-fpm-tuning.conf /usr/local/etc/php-fpm.d/zz-tuning.conf

WORKDIR /var/www/html
COPY app/ /var/www/html/

CMD ["php-fpm", "-F"]
```

#### Step 3: Siapkan File Konfigurasi OPcache dan Tuning FPM
Buat file `hands-on/m02/docker-php-ext-opcache.ini`:
```ini
zend_extension=opcache.so
opcache.enable=1
opcache.memory_consumption=128
opcache.interned_strings_buffer=16
opcache.max_accelerated_files=10000
opcache.validate_timestamps=0
opcache.jit=tracing
opcache.jit_buffer_size=32M
```

Buat file `hands-on/m02/php-fpm-tuning.conf`:
```ini
[www]
listen = 9000
pm = static
pm.max_children = 5
pm.status_path = /status
ping.path = /ping
request_terminate_timeout = 3s
```

#### Step 4: Siapkan Kode Instrumentasi Diagnostik
Buat file `hands-on/m02/app/index.php`:
```php
<?php
declare(strict_types=1);

header('Content-Type: application/json');

// Mencegah memory starvation buatan
$startMemory = memory_get_usage(false);
$allocatedElements = [];

for ($i = 0; $i < 100_000; $i++) {
    // Alokasi dummy structure
    $allocatedElements[] = [
        'id' => $i,
        'hash' => sha1((string)$i),
        'timestamp' => microtime(true),
    ];
}

$peakMemory = memory_get_peak_usage(false);
$endMemory = memory_get_usage(false);

echo json_encode([
    'runtime' => 'PHP ' . PHP_VERSION,
    'opcache_enabled' => opcache_get_status()['opcache_enabled'] ?? false,
    'jit_status' => opcache_get_status()['jit']['enabled'] ?? false,
    'memory_stats' => [
        'start_bytes' => $startMemory,
        'peak_bytes' => $peakMemory,
        'end_bytes' => $endMemory,
        'delta_kb' => ($endMemory - $startMemory) / 1024,
    ],
    'process_id' => getmypid(),
], JSON_PRETTY_PRINT);
```

#### Step 5: Eksekusi dan Verifikasi Diagnostik
Jalankan container:
```bash
docker build -t php-internals-lab:latest .
docker run -d --name fpm-lab -p 9000:9000 php-internals-lab:latest
```

Verifikasi output response via FastCGI CLI tool (misal via cgi-fcgi):
```bash
docker exec -it fpm-lab SCRIPT_FILENAME=/var/www/html/index.php REQUEST_METHOD=GET cgi-fcgi -bind -connect 127.0.0.1:9000
```
Amati penggunaan memory heap ZMM yang dilaporkan secara detail pada payload respons.

---

### 13. Exercises

#### Level Easy
1. Modifikasi script `hands-on/m02/app/index.php` untuk menampilkan status internal OPcache (`opcache_get_status(false)`). Tampilkan parameter memori: `used_memory`, `free_memory`, dan `wasted_memory`.
2. Validasi apa yang terjadi pada `wasted_memory` ketika script dieksekusi 100 kali. Berikan analisis tertulis singkat mengapa nilainya statis jika `validate_timestamps=0`.

#### Level Medium
Buat sebuah class `CircularDependencyTracker` yang menginstansiasi dua objek saling merujuk silang (`$a->partner = $b; $b->partner = $a;`). 
*   Jalankan iterasi pembuatan instance 50.000 kali.
*   Bandingkan penggunaan memori ketika `gc_disable()` dijalankan vs ketika `gc_collect_cycles()` dipanggil secara manual.
*   Log output `gc_status()` untuk mengonfirmasi jumlah siklus (*cycles*) yang dibersihkan.

#### Level Hard
Rancang sebuah prototype memory-efficient pipeline menggunakan **PHP Fibers** (`\Fiber`) untuk mengimplementasikan *Cooperative Multi-Tasking*. 
*   Buat Fiber worker yang mensimulasikan non-blocking stream parser (chunking string 64KB).
*   Fiber harus men-`suspend()` eksekusi saat chunk selesai dibaca dan me-`resume()` saat pemrosesan luar selesai.
*   Buktikan bahwa penggunaan memori tidak bertumbuh secara linier terhadap ukuran total stream string yang diproses (uji dengan payload mock 500MB).

---

### 14. Challenge: Arsitektur Stateful to Stateless Migrasi

#### Deskripsi Skenario:
Sebuah perusahaan logistik memiliki backend legacy PHP CLI daemon yang berjalan konstan secara stateful selama berminggu-minggu tanpa henti (`while(true)`). Sistem ini kerap crash setiap 3-4 jam akibat kebocoran memori misterius (*slow memory leak*) sebesar 20MB per jam, sehingga mengganggu pemrosesan pelacakan armada armada truk real-time. 

Codebase memuat lebih dari 400.000 baris kode dengan dependensi dependency-injection container kompleks yang menyebarkan referensi statis dan event listeners di berbagai layer.

#### Misi Rekayasa Anda:
Rancang dokumen arsitektur komprehensif dan proof-of-concept skrip perbaikan untuk:
1.  **Isolasi Eksekusi**: Bagaimana Anda merombak mekanisme eksekusi agar beralih ke paradigma isolasi transaksional modular tanpa harus menulis ulang (*rewrite*) seluruh 400.000 baris kode domain?
2.  **Mitigasi ZMM**: Rancang mekanisme eksekusi berbasis worker pool terkelola (misalnya FPM worker lifespan loop / process pool runner berbasis Unix fork) yang mengeksekusi jobs dan secara deterministik membebaskan alokasi memori kembali ke sistem operasi (OS-level RSS) setelah memproses *N* jobs.
3.  **Observabilitas Kernel**: Tentukan skrip dan parameter diagnostik Linux (`pmap`, `gdb`, atau `/proc/[pid]/smaps`) yang akan Anda instruksikan kepada tim DevOps untuk membuktikan secara empiris bahwa memori yang bocor adalah memori heap C-level extension alih-alih userland PHP zval.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual)

##### Q1. Berapa ukuran dasar struktur `zval` pada arsitektur PHP 8 64-bit?
*   A. 8 bytes
*   B. 16 bytes
*   C. 24 bytes
*   D. 32 bytes
*   *Jawaban*: **B**
*   *Penjelasan*: PHP 8 mengoptimalkan `_zval_struct` menjadi 16 byte: 8 byte untuk `zend_value` union, 4 byte untuk `u1` (type info flags), dan 4 byte untuk `u2` (union helper/hash/cache data).

##### Q2. Kapan proses duplikasi memori aktual terjadi saat variabel PHP disalin via `$b = $a`?
*   A. Seketika saat baris deklarasi `$b = $a` dieksekusi.
*   B. Saat variabel `$a` dihapus menggunakan `unset()`.
*   C. Saat salah satu variabel `$a` atau `$b` diubah nilainya (*mutation*).
*   D. Saat Garbage Collector menjalankan siklus sweep.
*   *Jawaban*: **C**
*   *Penjelasan*: PHP mengimplementasikan *Copy-on-Write* (COW). Pointer data dibagi bersama dan refcount dinaikkan hingga mutasi pertama dilakukan pada salah satu variabel.

##### Q3. Apa efek samping mengaktifkan `opcache.validate_timestamps=0` di environment produksi?
*   A. OPcache dinonaktifkan sepenuhnya.
*   B. File PHP tidak dapat membaca konfigurasi database.
*   C. Perubahan file source code di disk tidak akan dieksekusi hingga PHP-FPM di-restart/reload.
*   D. Memori bersama (Shared memory) akan corrupt jika terjadi konkurensi.
*   *Jawaban*: **C**
*   *Penjelasan*: Nilai 0 mencegah engine memanggil system call `stat()` untuk memeriksa perubahan file disk, sehingga pembaruan kode mengharuskan FPM Master menerima reload signal (misal: `kill -USR2`).

##### Q4. Apa fungsi utama dari Zend Memory Manager (ZMM) `emalloc()` dibandingkan sistem standar `malloc()`?
*   A. Menyimpan objek secara permanen di database.
*   B. Mengenkripsi alokasi memori di level hardware.
*   C. Mengelola heap memori scoped per-request yang secara otomatis di-purge pada phase `RSHUTDOWN`.
*   D. Mencegah penggunaan pointer di modul ekstensi C.
*   *Jawaban*: **C**
*   *Penjelasan*: ZMM mengalokasikan memori via slab allocator yang terikat pada siklus hidup request tunggal, mencegah kebocoran memori level sistem operasi jika script crash.

##### Q5. Komponen mana dalam PHP 8 yang bertugas mengonversi byte code secara langsung ke native machine instruction x86/ARM?
*   A. FastCGI Dispatcher
*   B. JIT Compiler
*   C. Abstract Syntax Tree (AST) Parser
*   D. Cyclic Root Buffer
*   *Jawaban*: **B**
*   *Penjelasan*: JIT compiler menerjemahkan hot opcode Zend VM menjadi native machine code yang langsung dieksekusi oleh unit prosesor (CPU).

---

#### Bagian 2: Intermediate (Analisis Arsitektur)

##### Q6. Mengapa Cyclic Reference tidak dapat langsung dibersihkan oleh mekanisme Reference Counting dasar?
*   *Jawaban*: Karena pada referensi siklik (Objek A merujuk B, dan Objek B merujuk A), masing-masing objek mempertahankan refcount minimal 1 yang berasal dari satu sama lain, meskipun variabel penunjuk di scope pengguna telah di-unset. Akibatnya, refcount tidak pernah menyentuh 0, sehingga alokasi memori terisolasi dan tertahan.

##### Q7. Apa keuntungan preloading (`opcache.preload`) dibandingkan regular OPcache?
*   *Jawaban*: OPcache reguler menyimpan opcode di memori bersama namun tetap membutuhkan verifikasi inheritance class link, autoloader registration, dan scope compilation per request. Preloading menyelesaikan binding class, function, dan dependencies secara permanen di memory image Zend Engine sebelum menerima request, mengeliminasi biaya runtime resolution sepenuhnya.

##### Q8. Mengapa setting FPM `pm = dynamic` berisiko tinggi saat menerima traffic lonjakan tak terduga (*flash crowd*)?
*   *Jawaban*: Saat lonjakan tiba-tiba, FPM terpaksa melakukan banyak system call `fork()` untuk melahirkan proses worker baru secara on-the-fly. Proses `fork()` memicu latency penalty yang tinggi, fragmentasi memori, dan perebutan sumber daya CPU secara mendadak (*CPU spike*) yang dapat mengakibatkan penumpukan koneksi (*connection backlog saturation*).

##### Q9. Dalam kondisi apa JIT PHP justru dapat memperlambat performa aplikasi web I/O-bound konvensional?
*   *Jawaban*: Pada aplikasi I/O-bound (kebanyakan aplikasi CRUD web yang bottleneck di DB query/network API), waktu eksekusi CPU sangat minor dibandingkan durasi network wait. Menjalankan JIT Tracing Engine menimbulkan overhead CPU tambahan untuk profiling, kompilasi native code, dan manajemen JIT cache buffer tanpa memberikan kompensasi percepatan yang nyata.

##### Q10. Jelaskan perbedaan mendasar antara `memory_get_usage(false)` dan `memory_get_usage(true)`.
*   *Jawaban*: `false` (default) hanya melaporkan jumlah memori aktual yang saat itu terpakai oleh variabel dan struktur Zend VM (Userland Memory). Sedangkan `true` mengembalikan total alokasi memori real (system memory blocks/chunks) yang telah dipesan oleh Zend Memory Manager dari sistem operasi melalui OS call (`mmap`/`malloc`).

---

#### Bagian 3: Skenario Kasus Produksi

##### Kasus 1: Misteri OOM Killer di Lingkungan Container K8s
*   **Skenario**: Pod PHP-FPM Anda memiliki limit RAM Kubernetes 4GB. Parameter pool FPM diatur `pm = static`, `pm.max_children = 100`, dan di `php.ini` disetel `memory_limit = 128M`. Secara matematis: 100 worker * 128M = 12.8GB (berpotensi overcommit). Namun, dev lead berargumen: "Rata-rata penggunaan memori aplikasi kami hanya 25MB per request. Jadi total penggunaan riil hanya 2.5GB, aman di bawah batas 4GB." Dua hari kemudian pada jam sibuk, pod mati seketika akibat OOM (Exit Code 137).
*   **Pertanyaan Evaluasi**: Mengapa asumsi dev lead fatal, dan bagaimana mekanisme Linux OOM Killer memilih target terminasi?
*   **Jawaban/Analisis**:
    1.  Asumsi dev lead mengabaikan skenario *worst-case peak burst*. Cukup 30 request kompleks dari 100 worker memproses reporting besar yang menyentuh batas `memory_limit` 128MB secara simultan (30 x 128MB = ~3.84GB), ditambah baseline 70 worker lainnya (70 x 25MB = 1.75GB). Total memori seketika menjadi 5.59GB, melampaui limit 4GB pod.
    2.  Linux OOM Killer memonitor batas memory cgroup namespace container. Begitu ambang batas cgroup dilanggar, kernel menghitung skor `oom_score` (berbanding lurus dengan persentase memori resident set size/RSS yang dikonsumsi suatu PID). Worker PHP-FPM yang sedang mengonsumsi memori terbesar akan langsung di-kill via sinyal `SIGKILL` tanpa graceful shutdown, memicu kegagalan transaksi dan *broken pipe connection*.

##### Kasus 2: Degradasi Latensi Pasca Deployment CI/CD
*   **Skenario**: Deployment aplikasi e-commerce dilakukan dengan strategi symlink swap (direktori release baru di-link ke direktori `/current`). OPcache disetel dengan `opcache.validate_timestamps=0`. Sesaat setelah deploy dan FPM reload, request latensi P99 melonjak dari 15ms ke 1.200ms selama 45 detik pertama, sebelum akhirnya normal kembali.
*   **Pertanyaan Evaluasi**: Apa fenomena internal yang terjadi pada Zend Engine / OPcache, dan bagaimana mitigasinya?
*   **Jawaban/Analisis**:
    *   Fenomena ini disebut **Cache Stampede / Cold Cache Throttling**. Ketika worker di-reload, cache opcode kosong (*cold*). Ratusan request konkuren yang masuk secara bersamaan menemukan kondisi OPcache miss, memicu seluruh worker membaca file disk, melakukan parsing, lexical analysis, dan kompilasi AST secara serentak di ratusan thread/proses. CPU mengalami throttling parah.
    *   **Mitigasi**: Implementasikan teknik *Cache Warming* dalam pipeline deployment sebelum traffic dialihkan:
        1. Mengompilasi cache secara headless sebelum cut-off symlink menggunakan CLI warmup script (`opcache_compile_file` untuk semua file di direktori release baru).
        2. Menerapkan Preloading pada PHP-FPM instance baru, dan hanya mengalihkan traffic NGINX upstream ke instance baru setelah startup preload selesai diverifikasi via health check endpoint.

##### Kasus 3: Unix Domain Socket Queue Saturation
*   **Skenario**: Metrik server menunjukkan CPU usage hanya 30% dan RAM tersisa 60%. Namun, user menerima gelombang HTTP 502 Bad Gateway. Di log NGINX tertulis: `connect() to unix:/var/run/php-fpm.sock failed (11: Resource temporarily unavailable) while connecting to upstream`.
*   **Pertanyaan Evaluasi**: Diagnosalah bagian kernel dan konfigurasi FastCGI apa yang bottleneck, serta berikan langkah remediasi tuntas.
*   **Jawaban/Analisis**:
    *   **Akar Masalah**: Antrean socket (*listen backlog queue*) pada Unix Domain Socket telah jenuh (*full*). Worker FPM yang ada (`max_children`) mungkin sedang lambat merespons akibat downstream I/O wait (misal: remote database latency spike), sementara kapasitas antrean Linux OS socket (`somaxconn`) atau `listen.backlog` FPM terlalu rendah (default seringkali bernilai 511 atau 128). Request baru yang ditransfer oleh NGINX langsung di-*reject* seketika oleh kernel.
    *   **Langkah Remediasi**:
        1. Naikkan limit backlog kernel OS di `/etc/sysctl.conf`:
           ```ini
           net.core.somaxconn = 65535
           ```
           Terapkan via `sysctl -p`.
        2. Konfigurasikan file pool FPM:
           ```ini
           listen.backlog = 65535
           ```
        3. Audit slow queries atau hang connection di downstream service dengan mengaktifkan `slowlog = /var/log/php-fpm-slow.log` dan `request_slowlog_timeout = 2s` pada konfigurasi FPM pool.

---

### 16. Summary
*   **Zend Engine Runtime Model**: PHP 8.x mengandalkan perpaduan arsitektur *Shared-Nothing*, representasi efisien memori `zval` 16-byte, serta alokator slab internal via Zend Memory Manager (ZMM). 
*   **Memory Efficiency**: Mekanisme Copy-on-Write (COW) memastikan minimalisasi alokasi memori fisik saat duplikasi data hingga terjadi mutasi state. Cyclic references ditangani secara deterministik melalui *Concurrent Cycle Collection*.
*   **High Performance Subsystems**: Produksi kelas enterprise wajib memanfaatkan kombinasi OPcache dengan `validate_timestamps=0` untuk mengeliminasi system calls, class preloading untuk bypassing autoloading link overhead, dan JIT compiler untuk optimasi beban kerja CPU-bound.
*   **Production Stability**: PHP-FPM dengan konfigurasi worker `pm = static`, estimasi limit memori per worker yang presisi, dan backlog tuning pada Unix Domain Socket merupakan fondasi ketahanan sistem terhadap beban puncak jutaan request konkuren. Keberhasilan skala enterprise bergantung pada pemahaman komprehensif atas batas interaksi antara Zend Engine internals dan Kernel OS Linux.