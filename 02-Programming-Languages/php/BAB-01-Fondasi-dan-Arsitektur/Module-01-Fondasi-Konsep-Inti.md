# Bab 01 Modul 01: Arsitektur Zend Engine, Request Lifecycle, dan Eksekusi Opcode

---

### 1. Learning Objectives
*   **Menganalisis** siklus hidup eksekusi internal PHP dari inisialisasi modul (`MINIT`) hingga terminasi modul (`MSHUTDOWN`).
*   **Mengevaluasi** peran Server API (SAPI) dalam mengisolasi Zend Engine dari antarmuka web server (FPM, CLI, Apache).
*   **Mengurai** pipeline kompilasi PHP: Tokenizing (Lexing), Parsing (AST generation), Compilation (Opcode generation), dan Execution (Zend Virtual Machine).
*   **Mengukur dan mengoptimasi** alokasi memori level-rendah melalui Zend Memory Manager (ZMM) dan struktur data internal `zval`.
*   **Mendiagnosis** anomali performa menggunakan Opcache dump, VLD (Vulcan Logic Dumper), dan debugging engine berbasis CLI.

---

### 2. Conceptual Anchor
Bayangkan PHP Engine seperti pabrik manufaktur modular berbasis pesanan *just-in-time*. 
*   **SAPI (Server API)** adalah dermaga bongkar muat kargo yang menerima pesanan dari berbagai moda transportasi (truk kontainer Nginx via FastCGI, kurir kilat CLI, atau tongkang Apache). Dermaga mengemas request ke dalam format standar yang dimengerti lantai pabrik.
*   **Zend VM & Compiler** adalah jalur perakitan: cetak biru (kode sumber PHP) dipindai secara berurutan, diurai menjadi instruksi hierarkis (Abstract Syntax Tree), dikonversi menjadi kartu kerja mesin otomatis (Opcodes).
*   **OPcache** adalah gudang penyimpanan kartu kerja siap pakai; jika cetak biru yang sama masuk dua kali, mesin melewati perancangan ulang dan langsung mengambil kartu kerja yang ada.
*   **Request Lifecycle** adalah jam kerja shift pabrik: fasilitas dinyalakan sekali saat pabrik dibangun (`MINIT`), jalur perakitan dibersihkan untuk setiap paket individu yang datang (`RINIT`), pesanan dirakit dan dikirim keluar, sisa material dibersihkan dari meja kerja (`RSHUTDOWN`), hingga akhirnya seluruh pabrik dimatikan jika operasional berhenti total (`MSHUTDOWN`).

---

### 3. Why This Matters
Mayoritas engineer memperlakukan PHP sebagai bahasa scripting "black box": kode masuk, respons HTTP keluar. Pendekatan ini runtuh seketika saat aplikasi mencapai skala jutaan request per detik, mengalami kebocoran memori misterius pada *long-running worker* (seperti RoadRunner, Swoole, atau Laravel Horizon), atau menghadapi CPU thrashing akibat kegagalan OPcache.

Memahami arsitektur internal Zend Engine bukan sekadar pengetahuan teoretis, melainkan landasan rekayasa performa tingkat lanjut:
*   **Efisiensi Sumber Daya:** Menghindari eksekusi I/O disk yang redundan dengan memahami *compilation cache* dan *shared memory allocation*.
*   **Desain State Management:** Menghindari alokasi state global yang berbahaya pada arsitektur *stateless worker pool*.
*   **Diagnostik Root-Cause:** Mampu membaca output VLD dan profil memory ZMM untuk membedakan antara overhead *garbage collection* vs kebocoran memori native C-level.

---

### 4. What It Is
PHP adalah bahasa pemrograman interpreted yang dikompilasi secara dinamis ke instruksi bytecode internal (disebut *Opcodes*) yang kemudian dieksekusi oleh mesin virtual berbasis tumpukan/register hibrida: **Zend Virtual Machine (Zend VM)**.

```
+-----------------------------------------------------------------------+
|                             PHP Engine                                |
|                                                                       |
|  +--------------------+   +----------------------------------------+  |
|  | SAPI Layer         |   | Zend Memory Manager (ZMM)              |  |
|  | (CLI, FPM, Embed)  |   | (Chunk, Page, Slot, emalloc, efree)    |  |
|  +--------------------+   +----------------------------------------+  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | Zend Core & Zend VM                                             |  |
|  |  [Lexing] -> [Parsing] -> [AST] -> [Compilation] -> [Opcodes]   |  |
|  +-----------------------------------------------------------------+  |
|                                                                       |
|  +---------------------------------+  +----------------------------+  |
|  | Zend Extensions (OPcache, Xdebug)|  | Core Extensions (ext/*)    |  |
|  +---------------------------------+  +----------------------------+  |
+-----------------------------------------------------------------------+
```

Komponen Inti:
1.  **SAPI (Server Application Programming Interface):** Abstraksi protokol antarmuka eksternal (FPM, CLI, Litespeed). Menyediakan implementasi hook standar seperti `sapi_startup`, `sapi_shutdown`, `ub_write`, dan pengelolaan input payload.
2.  **Zend Compiler:** Mentranslasikan string PHP menjadi struktur data hierarkis `zend_ast`, yang diubah menjadi array instruksi eksekusi `zend_op_array`.
3.  **Zend VM (Executor):** Mesin eksekusi runtime yang mengeksekusi elemen `zend_op` secara sekuensial. Menggunakan mekanisme dispatch (secara default *Hybrid Switch-Call* atau *Direct Threaded Code* pada arsitektur GCC/Clang).
4.  **Zend Memory Manager (ZMM):** Lapisan alokasi memori kustom di atas alokator native OS (`malloc`/`free`). Mengelola memori per-request melalui `emalloc`/`efree` dan membersihkannya secara deterministik saat *request shutdown*.
5.  **`zval` (Zend Value):** Struktur C dasar 16-byte yang membungkus tipe data PHP, referensi metadata tipe, bendera `refcount`, dan memori nilai aktual.

---

### 5. How It Works
Eksekusi PHP terjadi dalam dua siklus makro utama: **Process Lifecycle** dan **Request Lifecycle**.

#### Siklus Makro 1: Process Lifecycle (Engine Startup & Shutdown)
1.  **Module Init (`MINIT`):**
    *   Terjadi saat proses master PHP (misalnya master process PHP-FPM) pertama kali dijalankan.
    *   Engine menginisialisasi modul inti, mengalokasikan tabel fungsi global, mem-parsing `php.ini`, dan mendaftarkan konstanta bawaan.
    *   Ekstensi mendaftarkan struktur konfigurasi persisten dan fungsi C-level mereka.
2.  **Module Shutdown (`MSHUTDOWN`):**
    *   Terjadi saat seluruh proses worker di-terminate (misalnya SIGTERM pada FPM master).
    *   Membersihkan alokasi memori persisten dan membatalkan registrasi modul secara global.

#### Siklus Makro 2: Request Lifecycle (Per-Request Execution)
1.  **Request Init (`RINIT`):**
    *   SAPI menerima transaksi baru (misal request HTTP masuk ke FPM worker).
    *   ZMM menginisialisasi tumpukan memori request.
    *   Engine menyiapkan superglobal (`$_SERVER`, `$_POST`, `$_GET`, dll.).
    *   Masing-masing ekstensi memanggil callback `RINIT` miliknya (misal: setting waktu start request pada ext/date).
2.  **Pipeline Kompilasi & Eksekusi:**
    *   **Lexical Analysis (Re2c):** Stream karakter kode PHP diubah menjadi *token* numerik (dapat diamati via `token_get_all`).
    *   **Syntax Analysis (Bison Parser):** Token disusun menjadi struktur logika pohon: *Abstract Syntax Tree (AST)*.
    *   **Compilation:** AST diubah menjadi instruksi linier `zend_op_array`. Jika **OPcache** aktif, engine memeriksa *hash* file di Shared Memory (SHM). Jika ditemukan, fase Lexing/Parsing dilewati sepenuhnya.
    *   **Execution:** Zend Executor mengambil `zend_op_array` dan mengeksekusinya instruksi demi instruksi dalam konteks *execution stack* (`zend_execute_data`).
3.  **Request Shutdown (`RSHUTDOWN`):**
    *   Ekstensi mengeksekusi instruksi pembersihan lokal via callback `RSHUTDOWN`.
    *   Output buffer diflus secara paksa ke SAPI (`ub_write`).
    *   Semua fungsi *shutdown* yang terdaftar (`register_shutdown_function`) dieksekusi.
    *   Garbage Collector mengeksekusi pembersihan siklik yang belum selesai.
    *   **Memory Bailout:** ZMM membebaskan seluruh blok memori per-request yang tersisa (yang dialokasikan via `emalloc`), menjamin *leak isolation* antar request dalam worker pool yang sama.

---

### 6. Architecture / Flow Diagram

```
+-----------------------------------------------------------------------------+
|                           PROCESS INITIALIZATION (CLI/FPM Startup)         |
|  [Boot Engine] ---> [Read php.ini] ---> [Register Constants] ---> [MINIT]   |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                           REQUEST LIFECYCLE (Per-Request Execution)        |
|                                                                             |
|      [SAPI Ingress: Web Request / CLI Script]                                |
|                        |                                                    |
|                        v                                                    |
|                     [RINIT] (ZMM Allocator Reset, Setup Superglobals)       |
|                        |                                                    |
|                        v                                                    |
|              +--[OPcache Hit?]--+                                           |
|              |                  |                                           |
|         YES (Memory)        NO (Cold File Path)                             |
|              |                  |                                           |
|              |                  v                                           |
|              |         [Lexer (Tokenization)]                               |
|              |                  |                                           |
|              |                  v                                           |
|              |         [Parser (AST Gen)]                                   |
|              |                  |                                           |
|              |                  v                                           |
|              |         [Compiler (zend_op_array)]                           |
|              |                  |                                           |
|              |                  v                                           |
|              |         [Store to OPcache SHM]                               |
|              |                  |                                           |
|              +-------->+<-------+                                           |
|                        |                                                    |
|                        v                                                    |
|              [Zend VM: zend_execute]                                        |
|              (Opcode Iteration, Operand Resolution, Handler Invoke)         |
|                        |                                                    |
|                        v                                                    |
|                     [RSHUTDOWN]                                             |
|              (Call Shutdown Functions, Flush Buffers, Destruct Objects)     |
|                        |                                                    |
|                        v                                                    |
|              [ZMM Memory Cleanup: Free Non-Persistent Allocs]               |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                           PROCESS TERMINATION (Server Shutdown)            |
|                     [MSHUTDOWN] ---> [Unload Modules] ---> [Exit Process]   |
+-----------------------------------------------------------------------------+
```

---

### 7. Minimal Deterministic Example
Berikut demonstrasi pemecahan kode PHP ke struktur internal Token dan verifikasi *Execution Phase*:

```php
<?php
declare(strict_types=1);

// Step 1: Lexical Representation (Tokens)
$sourceCode = '<?php $a = 42; echo $a;';
$tokens = token_get_all($sourceCode);

echo "=== LEXICAL TOKENS ===" . PHP_EOL;
foreach ($tokens as $token) {
    if (is_array($token)) {
        printf(
            "Token: %-20s | String: %-10s | Line: %d\n",
            token_name($token[0]),
            var_export($token[1], true),
            $token[2]
        );
    } else {
        printf("Literal Token: %-13s | String: %-10s\n", 'RAW_CHAR', var_export($token, true));
    }
}

// Step 2: Lifecycle Hook Verification
echo PHP_EOL . "=== LIFECYCLE STATE ===" . PHP_EOL;
printf("SAPI Name        : %s\n", php_sapi_name());
printf("ZMM Allocations  : %d bytes (Real: %d bytes)\n", 
    memory_get_usage(false), 
    memory_get_usage(true)
);
```

Eksekusi CLI:
```bash
php minimal.php
```

Output Terprediksi:
```text
=== LEXICAL TOKENS ===
Token: T_OPEN_TAG           | String: '<?php '   | Line: 1
Token: T_VARIABLE           | String: '$a'       | Line: 1
Literal Token: RAW_CHAR      | String: '='       
Literal Token: RAW_CHAR      | String: ' '       
Token: T_LNUMBER            | String: '42'       | Line: 1
Literal Token: RAW_CHAR      | String: ';'       
Literal Token: RAW_CHAR      | String: ' '       
Token: T_ECHO               | String: 'echo'     | Line: 1
Literal Token: RAW_CHAR      | String: ' '       
Token: T_VARIABLE           | String: '$a'       | Line: 1
Literal Token: RAW_CHAR      | String: ';'       

=== LIFECYCLE STATE ===
SAPI Name        : cli
ZMM Allocations  : [integer] bytes (Real: 2097152 bytes)
```

---

### 8. Production-Grade Implementation
Sistem diagnostik runtime produksi untuk membedah status internal OPcache, konfigurasi Zend VM JIT, serta status konsumsi memori per-proses worker.

```php
<?php
declare(strict_types=1);

namespace Infrastructure\Diagnostics;

final class ZendEngineInspector
{
    public function __construct(
        private readonly bool $isProduction = true
    ) {}

    /**
     * Menganalisis kondisi kesehatan Opcache dan Compiler State.
     * @return array<string, mixed>
     */
    public function inspectRuntimeState(): array
    {
        $status = [];
        
        $status['engine'] = [
            'php_version' => PHP_VERSION,
            'sapi' => \PHP_SAPI,
            'zend_version' => zend_version(),
            'thread_safety' => ZEND_THREAD_SAFE,
            'debug_build' => ZEND_DEBUG_BUILD,
        ];

        $status['memory_manager'] = [
            'zmm_usage_bytes' => memory_get_usage(false),
            'zmm_real_allocated_bytes' => memory_get_usage(true),
            'peak_usage_bytes' => memory_get_peak_usage(false),
            'peak_real_allocated_bytes' => memory_get_peak_usage(true),
        ];

        if (function_exists('opcache_get_status')) {
            /** @var array<string, mixed>|false $opcacheStatus */
            $opcacheStatus = opcache_get_status(false);
            
            if ($opcacheStatus !== false) {
                $status['opcache'] = [
                    'enabled' => $opcacheStatus['opcache_enabled'] ?? false,
                    'full' => $opcacheStatus['memory_usage']['free_memory'] === 0,
                    'used_memory_mb' => round(($opcacheStatus['memory_usage']['used_memory'] ?? 0) / 1024 / 1024, 2),
                    'free_memory_mb' => round(($opcacheStatus['memory_usage']['free_memory'] ?? 0) / 1024 / 1024, 2),
                    'wasted_memory_percentage' => round($opcacheStatus['memory_usage']['current_wasted_percentage'] ?? 0.0, 2),
                    'hit_rate' => round($opcacheStatus['opcache_statistics']['opcache_hit_rate'] ?? 0.0, 2),
                    'cached_scripts_count' => $opcacheStatus['opcache_statistics']['num_cached_scripts'] ?? 0,
                    'jit' => $opcacheStatus['jit'] ?? ['enabled' => false],
                ];
            } else {
                $status['opcache'] = ['enabled' => false, 'error' => 'Opcache status unretrievable'];
            }
        } else {
            $status['opcache'] = ['enabled' => false, 'error' => 'ext-opcache not loaded'];
        }

        return $status;
    }

    /**
     * Memvalidasi apakah file terisolasi dalam cache internal engine tanpa eksekusi disk IO.
     */
    public function isScriptPrecompiled(string $absoluteFilePath): bool
    {
        if (!function_exists('opcache_is_script_cached')) {
            return false;
        }

        return opcache_is_script_cached($absoluteFilePath);
    }
}

// Harness Eksekusi
$inspector = new ZendEngineInspector(isProduction: false);
header('Content-Type: application/json; charset=utf-8');
echo json_encode($inspector->inspectRuntimeState(), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
```

---

### 9. Edge Cases, Failure Modes & Antipatterns

| Skenario / Antipattern | Mekanisme Kegagalan Engine | Dampak Sistem | Mitigasi Arsitektur |
| :--- | :--- | :--- | :--- |
| **OPcache Wasted Buffer Saturation** | Pembuatan file sementara berulang (eval, dynamic temporary cache files) menghasilkan *string un-invalidation*. | Opcache mencapai batas `max_wasted_percentage`, memicu restart otomatis yang membekukan request (stop-the-world). | Set `opcache.max_wasted_percentage=10` dan pastikan runtime code-generation tidak menyentuh filesystem yang dipantau OPcache. |
| **Leak pada Ekstensi C Native** | Ekstensi pihak ketiga menggunakan `malloc()` standard C dan lupa memanggil `free()`, alih-alih `emalloc()`/`efree()`. | Memory leak tidak terisolasi oleh request cleanup ZMM. Memory footprint worker membengkak hingga terkena OOM Killer OS. | Konfigurasi `pm.max_requests` pada PHP-FPM untuk merecycle worker secara periodik; audit ekstensi C dengan Valgrind. |
| **State Retention dalam Long-Running CLI Workers** | Global variables, static properties, dan listener array tidak direset saat siklus `RINIT`/`RSHUTDOWN` tidak terjadi (misal: Daemon/Worker). | Kebocoran referensi objek (`refcount > 0`), retensi circular references yang membebani Cycle Collector. | Gunakan explicit cleanup / `gc_collect_cycles()`, atau bungkus pemrosesan task dalam subprocess pool (`pcntl_fork`). |
| **Dynamic Include Explosion** | Menggunakan pola `require $module . '.php'` dinamis dengan permutasi tinggi. | Menembus batas kapasitas hash table Opcache (`opcache.max_accelerated_files`). | Terapkan PSR-4 strict autoloading terpusat dan lakukan OPcache preloading pada aplikasi. |

---

### 10. Performance Profiles & Memory Mechanics

#### Struktur Data Internal `zval` (PHP 8.x)
Di level C-source (`zend_types.h`), `zval` dikompresi menjadi tepat 16 byte pada arsitektur 64-bit:
```c
struct _zval_struct {
    zend_value        value; // 8 bytes (union: long, double, ptr, zend_string*, zend_array*, dll)
    union {
        struct {
            uint8_t    type;         // Primary Type (IS_STRING, IS_ARRAY, dll)
            uint8_t    type_flags;   // Reference counting, GC flags
            uint16_t   u;            // Reserved / Extra context
        } v;
        uint32_t type_info;          // 4 bytes
    } u1;
    union {
        uint32_t     next;           // Hash collision chain
        uint32_t     cache_slot;     // Runtime cache slot offset
        uint32_t     lineno;         // AST Line number
    } u2;                            // 4 bytes
};                                   // Total = 16 bytes
```

#### Mekanika Copy-on-Write (CoW)
PHP menerapkan strategi lazy copy via flags `IS_TYPE_REFCOUNTED`:
```
Variabel $a diinisialisasi
$a = "Payload string panjang" 
   --> zval ($a) ---> zend_value ---> zend_string (refcount=1)

Variabel $b mereferensikan $a
$b = $a; 
   --> zval ($a) \
                  +---> zend_value ---> zend_string (refcount=2) [TIDAK ADA DUPLIKASI MEMORI]
   --> zval ($b) /

Modifikasi pada $b
$b .= " modifikasi";
   --> zend_string (refcount=2) dipisahkan (CoW Event Triggered)!
   --> zval ($a) ---> zend_string (refcount=1) [Payload string panjang]
   --> zval ($b) ---> zend_string (refcount=1) [Payload string panjang modifikasi]
```

*   **Kompleksitas Kompilasi (Cold Run):** $\mathcal{O}(N)$ waktu terhadap panjang tokens sumber; $\mathcal{O}(M)$ memori untuk membangun AST.
*   **Kompleksitas Eksekusi (Hot OPcache):** $\mathcal{O}(1)$ compilation overhead; Instruksi dieksekusi secara in-memory langsung dari Zend VM array registers.

---

### 11. Comparative Architectural Trade-offs

| Pendekatan Eksekusi | Keuntungan Utama | Kerugian / Risiko | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Traditional PHP-FPM (Stateless Lifecycle)** | Isolasi memori sempurna. `RSHUTDOWN` membunuh seluruh leak request. Zero state contamination antar request. | Overhead `RINIT`/`RSHUTDOWN` tetap terjadi. Framework bootstrap (parsing config, container build) berulang jika tanpa OPcache preloading. | REST API umum, Monolith Web Application standar, arsitektur *Zero-Shared-State*. |
| **Long-Running Engine Workers (Swoole, RoadRunner)** | State aplikasi dan framework tetap hidup di memori. Throughput meningkat hingga 5x-10x karena bypass request bootstrap. | Pelanggaran boundary `RSHUTDOWN`. Kebocoran variabel statis, DB connection stale, global variable mutation mencemari request lain. | Low-latency microservices, WebSockets, real-time messaging engine, high-concurrency ingestion. |
| **Direct FastCGI CLI/Micro-Worker** | Setup minimalis, sangat ringan, kontrol deterministik per runtime instance. | Tidak memiliki pooling thread-safe native; konfigurasi auto-scaling bergantung sepenuhnya pada container orchestrator. | Batch background worker, AWS Lambda / Serverless PHP layers (Bref). |

---

### 12. Security Profiles & Threat Mitigation

#### Vektor Kerentanan Terkait Engine:
1.  **OPcache Poisoning (Shared Memory Corruption):**
    *   *Mekanisme:* Jika file permission pada file cache atau direktori script PHP dapat ditimpa oleh user OS lain di server multitenant, opcode berbahaya dapat disuntikkan ke dalam SHM buffer.
    *   *Mitigasi:* Konfigurasikan `opcache.validate_permission=1` dan pisahkan execution user via dedicated FPM pool pools (`listen.owner`, `listen.group`).
2.  **Unbounded AST Allocation (Denial of Service):**
    *   *Mekanisme:* Memaksa engine memproses file dengan nested array/ekspresi yang luar biasa dalam melalui `eval()` atau include dinamis, menyebabkan C-stack exhaust (Segmentation Fault).
    *   *Mitigasi:* Nonaktifkan fungsi berbahaya:
        ```ini
        disable_functions = eval,exec,passthru,shell_exec,system,proc_open
        ```
3.  **Arbitrary Bytecode Cache Injection:**
    *   *Mitigasi:* Jangan pernah mendasarkan eksekusi script pada user-supplied input paths (`include $_GET['page'] . '.php'`). Selalu terapkan whitelist absolut.

---

### 13. Tooling, Diagnostics & Observability

#### CLI Diagnostics:
Inspect Opcodes menggunakan PHP built-in (PHP 7.4+ mendukung inspection tanpa dependensi eksternal melalui opcache CLI dump script):
```bash
# Verifikasi sintaks dan kompilasi AST tanpa menjalankan eksekusi
php -l target_script.php

# Dump opcodes menggunakan extension VLD (jika terpasang)
php -d vld.active=1 -d vld.execute=0 target_script.php
```

#### Penggunaan PHP Native CLI Debugger:
```bash
# Dump informasi internal Opcache
php -r "var_dump(opcache_get_status());"

# Dump definisi token sumber
php -r "print_r(token_get_all(file_get_contents('target_script.php')));"
```

#### Observability Dashboard Matrix:
Untuk memantau Zend Engine di level produksi, stream metrik berikut ke sistem APM (Prometheus/DataDog):
*   `php_fpm_active_processes`: Konkurensi thread eksekusi VM saat ini.
*   `php_opcache_memory_used_bytes` vs `php_opcache_memory_free_bytes`: Mendeteksi kehabisan Shared Memory.
*   `php_opcache_wasted_percentage`: Menghindari triggering Opcache full restart.
*   `php_opcache_hit_rate`: Wajib di atas 99% di level produksi.

---

### 14. Cross-Platform & Environment Matrix

| Parameter / Konfigurasi | Linux (Debian/RHEL - POSIX) | macOS (Darwin - BSD based) | Windows Server (Win32) |
| :--- | :--- | :--- | :--- |
| **SAPI Preferensi** | `php-fpm` (UNIX domain sockets) | `php-fpm` (Local DEV environment) | `FastCGI` via IIS / Dedicated CLI Workers |
| **OPcache Memory Backend** | POSIX Shared Memory (`mmap` / `/dev/shm`) | POSIX Shared Memory (`mmap`) | Windows Native File-Mapping APIs |
| **Thread Safety (ZTS)** | Non-Thread Safe (NTS) standar industri | NTS standar industri | Thread Safe (ZTS) diwajibkan jika menggunakan Apache worker |
| **Process Forking (`pcntl`)** | Didukung penuh (`pcntl_fork`) | Didukung untuk development | **Tidak Didukung** (Fatal Error jika dipanggil) |

---

### 15. Testing & Verification Regimen

Gunakan PHPUnit test suite ini untuk memverifikasi karakteristik runtime engine pada target environment deployment Anda.

```php
<?php
declare(strict_types=1);

use PHPUnit\Framework\TestCase;

final class ZendEngineVerificationTest extends TestCase
{
    public function testOpcacheIsLoadedAndActive(): void
    {
        $this->assertTrue(
            extension_loaded('Zend OPcache'),
            'Ekstensi OPcache wajib aktif pada lingkungan produksi.'
        );

        $status = opcache_get_status(false);
        $this->assertIsArray($status, 'OPcache status harus dapat dibaca.');
        $this->assertTrue(
            $status['opcache_enabled'],
            'OPcache execution engine harus bernilai TRUE.'
        );
    }

    public function testMemoryManagerIsReleasingMemoryCorrectly(): void
    {
        $initialMemory = memory_get_usage(false);
        
        // Buat alokasi lokal masif
        $transientArray = [];
        for ($i = 0; $i < 50_000; $i++) {
            $transientArray[] = "node_payload_block_{$i}";
        }
        
        $allocatedMemory = memory_get_usage(false);
        $this->assertGreaterThan($initialMemory, $allocatedMemory);

        // Hancurkan referensi data
        unset($transientArray);

        $reclaimedMemory = memory_get_usage(false);
        
        // Pastikan alokator memori lokal merestorasi baseline secara deterministik
        $leakageVariance = $reclaimedMemory - $initialMemory;
        $this->assertLessThan(
            8192, 
            $leakageVariance, 
            'ZMM harus mengembalikan memori yang di-unset mendekati baseline awal request.'
        );
    }

    public function testSapiExposesNonThreadSafeExecution(): void
    {
        // Standar arsitektur microservices berbasis Linux FPM
        $this->assertEquals(0, ZEND_THREAD_SAFE, 'Target environment harus NTS (Non-Thread-Safe).');
    }
}
```

---

### 16. Step-by-Step Implementation Guide

Berikut prosedur verifikasi dan optimasi Zend VM execution state pada server berbasis Linux:

1.  **Validasi Modul Zend Engine Aktif:**
    ```bash
    php -v
    ```
    *Pastikan output mengandung:* `with Zend OPcache vX.Y.ZZ, Copyright (c) Zend Technologies`.

2.  **Konfigurasi Parameter Inti OPcache (`/etc/php/8.3/fpm/conf.d/10-opcache.ini`):**
    ```ini
    ; Alokasi memori bersama (Shared Memory) dalam Megabyte
    opcache.memory_consumption=256

    ; Buffer untuk alokasi string terinternalisasi
    opcache.interned_strings_buffer=16

    ; Batas maksimum script yang dicache
    opcache.max_accelerated_files=20000

    ; Matikan validasi kesegaran file di produksi (Bypass Disk IO Stat)
    opcache.validate_timestamps=0

    ; Tangkap fatal errors untuk shutdown observability
    opcache.record_warnings=1

    ; Optimasi register alokasi ZMM
    opcache.enable_cli=0
    ```

3.  **Terapkan Hot Cache Preloading (Opsional - PHP 7.4+):**
    Tambahkan pada file konfigurasi:
    ```ini
    opcache.preload=/var/www/app/preload.php
    opcache.preload_user=www-data
    ```

4.  **Restart Daemon FPM & Validasi In-Memory State:**
    ```bash
    sudo systemctl restart php8.3-fpm
    php -r "print_r(opcache_get_status(false)['memory_usage']);"
    ```

---

### 17. Industrial Real-World Case Study

#### Insiden: Latency Spike 3500ms pada Flash-Sale Deployment
*   **Konteks Perusahaan:** Platform E-Commerce berbasis PHP 8.2 yang melayani 28.000 Request/Detik via 48 Node PHP-FPM di Kubernetes.
*   **Gejala:** Sesaat setelah rolling-update konfigurasi, throughput cluster turun 80%, latensi P99 melesat dari 45ms ke 3.500ms, CPU usage pada seluruh worker node melonjak drastis ke 100%.
*   **Investigasi Root-Cause:**
    1.  Metrik `opcache_hit_rate` anjlok dari 99.8% ke 12.3%.
    2.  Pemeriksaan direktori menunjukkan opsi konfigurasi:
        ```ini
        opcache.validate_timestamps=1
        opcache.revalidate_freq=0
        ```
    3.  Aplikasi menggunakan framework monolitik besar dengan lebih dari 32.000 file source PHP (`vendor` included), melampaui default `opcache.max_accelerated_files=10000`.
    4.  **Mekanisme Kegagalan:** Karena file melebihi kapasitas hash table OPcache dan `revalidate_freq=0`, untuk *setiap baris include/require pada tiap request*, FPM memicu syscall `stat()` ke Network File System / Storage Overlay Kubernetes untuk memeriksa timestamp perubahan file, yang membakar habis CPU cycle pada level kernel-space context switching.
*   **Tindakan Resolusi:**
    1.  Ubah `opcache.max_accelerated_files=65536`.
    2.  Set `opcache.validate_timestamps=0` dalam base Docker image.
    3.  Pembersihan cache dilakukan eksplisit melalui zero-downtime Blue/Green deployment rollout (node lama dimatikan bersama shared memorinya, node baru memuat memory fresh).
*   **Hasil:** CPU Utilization kembali stabil di 22% pada load penuh, P99 latency terpangkas ke 38ms.

---

### 18. Best Practices & Design Principles

*   **Immense Disk I/O Bypass:** Jangan pernah biarkan `opcache.validate_timestamps=1` aktif di lingkungan production. Gunakan proses deploy immutability.
*   **Respect the Lifecycle Boundary:** Sadari batasan data lifecycle:
    *   State pada variabel `$GLOBALS`, static attributes kelas, dan singletons **terisolasi per-request** pada PHP-FPM tradisional, tetapi **bertahan selamanya (persistent)** pada async worker seperti RoadRunner/FrankenPHP/Swoole.
*   **Penyelarasan Slot Hash Table:** Set nilai `opcache.max_accelerated_files` ke bilangan prima atau nilai representatif yang lebih besar dari total script codebase aktual (hitung via: `find . -type f -name "*.php" | wc -l`).
*   **Linear Compilation via Native String Interning:** Tingkatkan nilai `opcache.interned_strings_buffer` (misal 16MB atau 32MB) pada aplikasi berbasis Domain-Driven Design yang sarat dengan pemanggilan nama class, interface, dan namespace panjang berulang kali.

---

### 19. Self-Correction & Common Pitfalls

*   **Salah Kaprah: "Garbage Collector PHP Harus Dipanggil Tiap Request Selesai"**
    *   *Koreksi:* Jangan menempatkan `gc_collect_cycles()` di akhir controller request. ZMM memusnahkan **seluruh arena alokasi** memori request pada fase `RSHUTDOWN` secara instan dalam blok C-pointer memory swap. Memanggil GC manual secara agresif justru membuang CPU cycle dengan menelusuri pohon referensi siklik yang sebentar lagi akan dibakar oleh memory allocator engine.
*   **Kebingungan Relasi SAPI vs PHP Core:**
    *   *Koreksi:* SAPI bukan layer di dalam PHP Core, melainkan antarmuka adapter (bridge) yang menengahi protokol luar dan engine core. CLI tidak memiliki timeout secara default (`max_execution_time=0`), sedangkan FPM diatur oleh parameter SAPI konfigurasi pool (`request_terminate_timeout`).
*   **Miskonsepsi Eksekusi Skrip:**
    *   *Koreksi:* PHP tidak "menginterpretasi file baris per baris secara live dari hard disk". File selalu dipindai secara utuh ke token, dikonversi menjadi AST, dikompilasi menjadi Opcodes, dan dieksekusi di RAM. Jika Opcache aktif, file disk tidak disentuh sama sekali setelah initial run.

---

### 20. Capstone Exercises

#### Level 1: Analisis Tokenizing & Struktur Parsing (Easy)
Tulis skrip CLI PHP murni yang menerima path file PHP lain sebagai argumen input, memprosesnya melalui Lexer (`token_get_all`), dan mencetak:
1.  Total jumlah token yang dihasilkan.
2.  Berapa banyak token yang bertipe komentar (`T_COMMENT`, `T_DOC_COMMENT`).
3.  Berapa persentase token logika murni dibanding spasi/karakter formatting (`T_WHITESPACE`).

#### Level 2: Detektor Memory Leak Antar Siklus (Medium)
Rancang harness eksekusi loop yang mensimulasikan lingkungan long-running worker (misal: 1.000 iterasi tugas).
*   Implementasikan skenario di mana satu class service sengaja membocorkan memori melalui array statis privat yang mereferensikan closure context `$this`.
*   Tulis class `MemorySentinel` yang membaca selisih memori internal via `memory_get_usage()` pada awal dan akhir setiap siklus.
*   Log peringatan secara otomatis ketika terdeteksi kenaikan delta alokasi memory yang tidak diklaim oleh ZMM selama 5 iterasi berturut-turut.

#### Level 3: Bedah Real-time Zend Opcode Executor & Preloader (Hard / Extreme)
Buat prototype micro-framework berbasis CLI dengan kapabilitas inspeksi engine internal:
1.  Buat skrip `bootstrap.php` yang mendefinisikan sebuah hierarki interface, abstract class, dan implementasi konkret.
2.  Bangun command yang memanfaatkan fungsi internal Opcache (`opcache_compile_file`) untuk mengompilasi file tersebut langsung ke Shared Memory tanpa mengeksekusi body fungsinya.
3.  Lakukan verifikasi menggunakan `opcache_is_script_cached()`.
4.  Gunakan `xdebug` atau script dump memory inspection native untuk membuktikan bahwa ketika file tersebut di-`require` kembali, engine tidak memicu stat check I/O dan alokasi `zend_op_array` dialihkan langsung dari segment memory OPcache. Pastikan program mengembalikan exit code 0 jika verifikasi sukses, dan exit code 1 jika cache miss.