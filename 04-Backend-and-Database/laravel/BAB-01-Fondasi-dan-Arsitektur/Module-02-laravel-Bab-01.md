# BAB 01: Fondasi & Arsitektur
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengurai secara komprehensif alur internal `Illuminate\Container\Container` dan `Illuminate\Pipeline\Pipeline`.
- Mengimplementasikan teknik resolusi dependensi lanjutan: *Contextual Binding*, *Tagged Services*, *Rebinding Listeners*, dan *Scoped Lifecycle*.
- Menganalisis dan mengeliminasi *State Pollution* serta *Memory Leak* pada runtime persisten (*Laravel Octane / FrankenPHP / RoadRunner*).
- Merancang arsitektur pipeline pemrosesan HTTP dan *Terminable Middleware* untuk observabilitas beban tinggi (*high-throughput observability*).
- Mengonfigurasi strategi optimasi produksi tingkat kernel (*Opcache preloading, bytecode caching, compiler optimizations*).

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib memahami:
- **PHP 8.2/8.3 Internals**: *Reflection API*, *Fiber*, *WeakMap*, *First-Class Callable*, dan manajemen memori zval/garbage collection.
- **Siklus Hidup Eksekusi PHP-FPM**: Model eksekusi *Shared-Nothing* (*Request -> Boot -> Execute -> Tear Down*).
- **Dasar Laravel Module 01**: Service Container dasar, Service Providers, dan HTTP Kernel standar.

---

### 3. Concept & Internal Architecture

#### 3.1 Resolusi Internal Service Container (`Illuminate\Container\Container`)
Service Container di Laravel bukan sekadar array penyimpan instans (*service locator*), melainkan *Inversion of Control (IoC) Engine* berbasis refleksi dinamis.

```
Request Make -> [Check Instances (Singleton)] -> Hit? -> Return
                      | (Miss)
               [Check Bindings] --------------> Hit? -> Resolve Closure/Target
                      | (Miss)
           [Target Is Instantiable?] ---------> No  -> Throw BindingResolutionException
                      | (Yes)
            [Inspect Constructor via ReflectionClass]
                      |
        [Loop Parameters & Resolve Dependencies via TypeHint]
                      |
             [Instantiate Object with Dependencies]
                      |
                 [Fire Resolving Callbacks]
                      |
                   [Return Instance]
```

Ketika method `App::make($abstract)` dipanggil:
1. **Instance Cache Check**: Kontainer memeriksa properti `$instances`. Jika service terdaftar sebagai singleton dan telah diinstansiasi, instans langsung dikembalikan ($O(1)$).
2. **Contextual Binding Resolution**: Kontainer memeriksa apakah pemanggil (*build stack*) memiliki aturan khusus pada array `$contextual[$concrete][$abstract]`.
3. **Closure Execution vs Reflection Fallback**:
   - Jika terikat via closure (`$bindings[$abstract]['concrete']`), closure dieksekusi.
   - Jika tidak terikat, kontainer menginisialisasi `ReflectionClass($abstract)`. Jika kelas berstatus *abstract* atau berupa *interface*, dilempar `BindingResolutionException`.
4. **Recursive Dependency Injection**: Kontainer membaca parameter konstruktor melalui `ReflectionMethod::getParameters()`. Setiap parameter diperiksa tipe datanya secara rekursif via `resolveClass()` atau diekstrak dari default value / contextual binding primitive via `resolvePrimitive()`.
5. **Rebinding Listeners**: Jika suatu interface di-*rebind* setelah objek bergantung diinstansiasi, closure pada properti `$reboundCallbacks` akan dipicu untuk memperbarui state dependensi pada konsumen terkait.

#### 3.2 Anatomi Pipeline Pattern (`Illuminate\Pipeline\Pipeline`)
Inti dari HTTP Kernel, Routing, dan Middleware di Laravel adalah abstraksi dari fungsi matematis komposisi:
$$f(g(h(Request)))$$

Secara internal, `Pipeline` menggunakan `array_reduce` native PHP untuk membungkus tumpukan middleware menjadi rantai Closure berlapis (*Onion Architecture*):

```php
// Representasi internal logika Pipeline::then()
$pipeline = array_reduce(
    array_reverse($pipes),
    $this->carry(),
    $this->prepareDestination($destination)
);

return $pipeline($passable);
```

Setiap middleware bertindak sebagai *decorator* yang menerima objek `$passable` (dalam konteks HTTP adalah `Request`) dan Closure `$next`.

#### 3.3 Transisi Paradigma: PHP-FPM vs Runtime Persisten (Laravel Octane)
Pada PHP-FPM tradisional, seluruh alur aplikasi di-*bootstrap* dari nol pada setiap HTTP request, lalu seluruh alokasi memori dibersihkan (*Shared-Nothing*).

Pada runtime persisten (*Swoole, RoadRunner, FrankenPHP*):
- Kernel di-*bootstrap* **satu kali** saat worker pertama kali hidup (*Long-running Worker Process*).
- Objek `Application` dan seluruh dependensi Singleton menetap di RAM lintas ribuan HTTP request.
- **Bahaya Utama**: Mengikat state pengguna/request (seperti data auth, custom tenant ID) ke dalam Service Singleton akan menyebabkan kebocoran data antar user (*Data Leak / State Pollution*).

---

### 4. Why & What

| Fitur / Komponen | Mengapa Dibutuhkan (Why) | Apa Itu (What) |
| :--- | :--- | :--- |
| **Contextual Binding** | Menghilangkan kopling keras ketika dua implementasi berbeda dari satu interface dibutuhkan oleh service yang berbeda tanpa membuat subclass buatan. | Mekanisme kontainer untuk menyuntikkan implementasi konkret berdasarkan kelas pemanggil (*consumer class*). |
| **Scoped Lifecycle** | Menghindari *state pollution* di runtime Octane sekaligus mencegah instansiasi berulang dalam siklus satu request yang sama. | Siklus hidup objek yang berperilaku seperti singleton selama **satu siklus request**, dan otomatis di-*flush* saat request berakhir. |
| **Terminable Middleware** | Memindahkan pekerjaan non-blocking (seperti audit logging, analitik, metrik Prometheus) ke luar waktu tunggu client. | Middleware yang mengimplementasikan method `terminate()`, dieksekusi setelah respon HTTP terkirim ke klien. |
| **Rebinding Callbacks** | Mempertahankan integritas objek jika dependency injection dimodifikasi secara dinamis di runtime (misalnya penggantian auth driver atau dynamic tenant). | Event-driven listener pada kontainer yang memicu update referensi internal ketika sebuah service di-bind ulang. |

---

### 5. How (Workflow Detail)

Alur penanganan Request tingkat lanjut dalam arsitektur kernel:
```
Client Request
      │
      ▼
[Swoole/FrankenPHP Worker Loop]
      │
      ├─► 1. Clone/Sandbox Container Instance (Jika runtime Octane)
      ├─► 2. Register Request Context via Scoped Instances
      │
[HTTP Kernel Pipeline Execution]
      │
      ├─► Middleware 1 (Global: TrustProxies)
      │     └─► Middleware 2 (Contextual: Dynamic Tenant Identification)
      │           └─► Middleware 3 (Routing & Authorization)
      │                 │
      │                 ▼
      │           [Controller Action Executed via Reflection]
      │                 │
      │                 ▼
      │           [Response Object Generated]
      │                 │
      │◄── Response 3 ──┘
      │
      ├─► Send Response Headers & Body to Socket (Client Menerima Respons)
      │
[Post-Response Cycle: Terminable Middleware]
      │
      ├─► Push Metric to Prometheus Collector (Terminable Logic)
      ├─► Dispatch Async Background Jobs
      │
[Tear Down / State Purge]
      │
      ├─► Fire 'request.handled' Event
      ├─► Container::flush() (Bersihkan Scoped Instances, Instances flagged for purge)
      └─► Worker Loop Standby for Next Connection
```

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi Bawang Bombay (The Onion Architecture of Middlewares)
Bayangkan sebuah dokumen rahasia yang dimasukkan ke dalam 3 lapisan amplop:
1. Amplop Luar (Rate Limiter)
2. Amplop Tengah (Authentication)
3. Amplop Dalam (Encryption)

Untuk membaca dan merespons:
```
REQUEST INCOMING ────────────────────────────────────────────────────────►
 [Amplop Luar: Buka] 
     [Amplop Tengah: Buka] 
         [Amplop Dalam: Buka] 
             ★ INTI: Controller memproses & membuat jawaban ★
         [Amplop Dalam: Segel Ulang & Tulis Header] 
     [Amplop Tengah: Hitung waktu eksekusi] 
 [Amplop Luar: Catat Audit Trail]
◄─────────────────────────────────────────────────────── RESPONSE OUTGOING
```

#### 6.2 Diagram Status Memori: FPM vs Octane
```
[PHP-FPM Lifecycle]
Request 1: [Init RAM] ──> [Bootstrap Container] ──> [Execute] ──> [DESTROY ALL RAM]
Request 2: [Init RAM] ──> [Bootstrap Container] ──> [Execute] ──> [DESTROY ALL RAM]

[Laravel Octane Lifecycle]
Worker Start: [Init RAM] ──> [Bootstrap Base Container] 
Request 1:                        └──> [Fork Context/Scoped] ──> [Execute] ──> [Flush Scoped]
Request 2:                        └──> [Fork Context/Scoped] ──> [Execute] ──> [Flush Scoped]
Worker Die (e.g. 10.000 reqs): [DESTROY PROCESS RAM]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Simulasi Native Micro-Pipeline
Memahami bagaimana `Illuminate\Pipeline\Pipeline` mengeksekusi middleware menggunakan native PHP:

```php
<?php

declare(strict_types=1);

$pipes = [
    function ($passable, $next) {
        $passable['stack'][] = 'Layer 1: Start';
        $response = $next($passable);
        $response['stack'][] = 'Layer 1: End';
        return $response;
    },
    function ($passable, $next) {
        $passable['stack'][] = 'Layer 2: Auth Validated';
        return $next($passable);
    },
];

$destination = function ($passable) {
    $passable['stack'][] = 'Core Destination Executed';
    return $passable;
};

// Pipeline logic
$pipeline = array_reduce(
    array_reverse($pipes),
    function ($nextPipe, $pipe) {
        return function ($passable) use ($nextPipe, $pipe) {
            return $pipe($passable, $nextPipe);
        };
    },
    $destination
);

$result = $pipeline(['stack' => []]);
// Output Result:
// Layer 1: Start -> Layer 2: Auth Validated -> Core Destination Executed -> Layer 1: End
```

#### 7.2 Practical Example: Multi-Driver Contextual & Scoped Architecture
Implementasi injeksi driver yang berbeda tergantung pada Consumer Controller dan pengelolaan state request isolation yang aman untuk Octane:

```php
<?php

declare(strict_types=1);

namespace App\Core\Infrastructure;

use Illuminate\Support\ServiceProvider;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

// 1. Interfaces & Abstractions
interface AuditLoggerInterface
{
    public function log(string $action, array $context): void;
}

final readonly class CloudWatchAuditLogger implements AuditLoggerInterface
{
    public function log(string $action, array $context): void
    {
        // Pengiriman ke AWS CloudWatch
    }
}

final readonly class LocalAuditLogger implements AuditLoggerInterface
{
    public function log(string $action, array $context): void
    {
        // Pengiriman ke Local File / Elastic Stack internal
    }
}

// 2. Scoped Request Context (Aman dari State Pollution di Octane)
final class RequestContext
{
    private ?string $tenantId = null;
    private ?string $correlationId = null;

    public function init(string $tenantId, string $correlationId): void
    {
        $this->tenantId = $tenantId;
        $this->correlationId = $correlationId;
    }

    public function getTenantId(): ?string
    {
        return $this->tenantId;
    }

    public function getCorrelationId(): ?string
    {
        return $this->correlationId;
    }
}

// 3. Consumers
final readonly class PaymentProcessingService
{
    public function __construct(
        private AuditLoggerInterface $logger,
        private RequestContext $context
    ) {}

    public function process(float $amount): void
    {
        $this->logger->log('payment_initiated', [
            'amount' => $amount,
            'tenant' => $this->context->getTenantId(),
            'correlation' => $this->context->getCorrelationId(),
        ]);
    }
}

final readonly class InternalReportService
{
    public function __construct(
        private AuditLoggerInterface $logger
    ) {}

    public function generate(): void
    {
        $this->logger->log('report_generated', ['type' => 'daily_sales']);
    }
}

// 4. Service Provider dengan Contextual Binding & Scoped Instance
final class ArchitectureAdvancedServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        // Scoped: Di-instansiasi 1x per request, auto-flush di Octane
        $this->app->scoped(RequestContext::class, function () {
            return new RequestContext();
        });

        // Contextual Binding: Injeksi implementasi yang berbeda untuk interface yang sama
        $this->app->when(PaymentProcessingService::class)
            ->needs(AuditLoggerInterface::class)
            ->give(fn () => new CloudWatchAuditLogger());

        $this->app->when(InternalReportService::class)
            ->needs(AuditLoggerInterface::class)
            ->give(fn () => new LocalAuditLogger());
    }
}

// 5. Terminable Middleware: Pipeline Observability
final class TraceAndMetricsTerminableMiddleware
{
    public function __construct(
        private RequestContext $context
    ) {}

    public function handle(Request $request, \Closure $next): Response
    {
        // Pre-routing execution
        $correlationId = $request->header('X-Correlation-ID', (string) \Illuminate\Support\Str::uuid());
        $tenantId = $request->header('X-Tenant-ID', 'default');
        
        $this->context->init($tenantId, $correlationId);

        $response = $next($request);
        $response->headers->set('X-Correlation-ID', $correlationId);

        return $response;
    }

    public function terminate(Request $request, Response $response): void
    {
        // Dijalankan SETELAH data dikirim ke client (Non-blocking response)
        $duration = microtime(true) - LARAVEL_START;
        
        // Kirim status code, duration, memory usage ke StatsD / Prometheus daemon
        if ($duration > 1.5) {
            \Illuminate\Support\Facades\Log::warning('Slow transaction detected', [
                'correlation_id' => $this->context->getCorrelationId(),
                'duration' => $duration,
                'status' => $response->getStatusCode(),
            ]);
        }
    }
}
```

---

### 8. Real World Case Study: FinTech Multi-Tenant Core Banking Engine

#### Permasalahan
Sebuah sistem agregator switching pembayaran memproses $4.500$ request per detik (RPS). Aplikasi berjalan di atas infrastruktur Kubernetes dengan runtime Laravel Octane (FrankenPHP). 
- **Incident #1**: Tenant A secara berkala mendapatkan response yang berisi konfigurasi API Key dan saldo ledger milik Tenant B.
- **Incident #2**: Tingkat latensi P99 menyentuh angka 3.200ms akibat middleware memproses validasi ledger hashing dan audit logging secara sinkron sebelum respons dikembalikan ke gateway perbankan.

#### Root Cause Analysis (RCA)
1. **State Pollution**: Driver tenant context diregistrasikan sebagai `$this->app->singleton(TenantContext::class)`. Pada FrankenPHP worker loop, instansiasi singleton tidak dihancurkan saat request selesai, menyebabkan request berikutnya memakai konteks tenant sebelumnya jika header tenant kosong atau lolos validasi.
2. **Synchronous Middlewares**: Audit logging dan analitik performa berjalan di dalam rantai pemrosesan middleware utama, menahan socket koneksi klien selama proses I/O socket menuju database logs.

#### Arsitektur Solusi
1. Konversi dependency lifecycle `TenantContext` dari `singleton` menjadi `scoped`.
2. Mendaftarkan `TenantContext` ke konfigurasi array `octane.flush` untuk memaksa dereferensi memori pada worker loop.
3. Pisahkan alur I/O logging ke dalam `TerminableMiddleware` dan eksekusi logging di luar siklus respons HTTP.
4. Implementasi dynamic contextual injection pada repository perbankan.

```php
namespace App\Providers;

use App\Domain\Tenant\TenantContext;
use App\Domain\Banking\LedgerRepositoryInterface;
use App\Infrastructure\Banking\PostgresLedgerRepository;
use App\Infrastructure\Banking\DynamoDbLedgerRepository;
use App\Infrastructure\Http\Controllers\HighThroughputPaymentController;
use Illuminate\Support\ServiceProvider;

final class ProductionBankingServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        // 1. Isolation Lifecycle
        $this->app->scoped(TenantContext::class, function () {
            return new TenantContext();
        });

        // 2. High-throughput contextual split:
        // Controller core payment menggunakan engine in-memory/DynamoDb
        $this->app->when(HighThroughputPaymentController::class)
            ->needs(LedgerRepositoryInterface::class)
            ->give(DynamoDbLedgerRepository::class);

        // Controller standar / pelaporan tetap menggunakan PostgreSQL
        $this->app->bind(LedgerRepositoryInterface::class, PostgresLedgerRepository::class);
    }
}
```

---

### 9. Trade-offs & Engineering Decisions

```
+---------------------------------------------------------------------------------+
|                              TRADEOFF MATRIX                                    |
+--------------------------+------------------------------+-----------------------+
| Keputusan Arsitektur     | Keuntungan (+)               | Biaya / Konsekuensi (-)|
+--------------------------+------------------------------+-----------------------+
| Laravel Octane           | - Latensi turun ~70-80%      | - Risiko State Leak   |
| (FrankenPHP / Swoole)    | - Throughput naik 4x-6x      | - Memory leak debugging|
|                          | - Bootstrap overhead lenyap  | - Wajib thread-safe   |
+--------------------------+------------------------------+-----------------------+
| Reflection Autowiring    | - Kecepatan development      | - Penalti mikro-CPU   |
| vs Manual Bindings       | - Sedikit boilerplate code   | - Opcache miss risk   |
|                          |                              | - Gagal di compile-time|
+--------------------------+------------------------------+-----------------------+
| Scoped Lifecycle         | - Menjamin state isolation   | - Memory re-allocation|
|                          | - Safe-by-default di Octane  |   overhead per-request|
+--------------------------+------------------------------+-----------------------+
| Terminable Middleware    | - Waktu respons ke klien     | - Menahan koneksi     |
|                          |   sangat cepat               |   FPM/Worker sebelum  |
|                          | - I/O decoupled dari respons |   ambil antrean baru  |
+--------------------------+------------------------------+-----------------------+
```

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Memory Leak & State Pollution pada Singleton Octane
*Anti-pattern:*
```php
// DI DAFTARKAN SEBAGAI SINGLETON DI OCTANE
final class CartManager {
    private array $items = []; // BAHAYA: Array ini terus tumbuh & dipakai antar-user!

    public function addItem($item): void {
        $this->items[] = $item;
    }
}
```
*Solusi Remediasi:*
Gunakan `app->scoped()`, atau jika harus singleton, sediakan lifecycle reset via event listener `OperationTerminated`:
```php
// config/octane.php
'listeners' => [
    RequestTerminated::class => [
        FlushCartManager::class,
    ],
],
```

#### 10.2 Resolving Circular Dependencies
*Error:* `Maximum function nesting level of '512' reached` atau `BindingResolutionException: Target is not instantiable while building...`
*Diagnosis:* Service A membutuhkan Service B di konstruktor, dan Service B membutuhkan Service A.
*Remediasi:* Pisahkan *shared logic* ke Service C yang independen, atau injeksi `\Illuminate\Contracts\Container\Container` dan panggil `make()` secara lazy saat method terkait dipanggil.

#### 10.3 Penyalahgunaan Terminable Middleware pada PHP-FPM
*Masalah:* Terminable middleware berjalan lambat dan gateway timeout ($504$).
*Penyebab:* Web server (Nginx) menggunakan FastCGI dengan konfigurasi `fastcgi_finish_request()` dinonaktifkan atau PHP dijalankan via mod_php/CGI klasik. Akibatnya, browser tetap menunggu eksekusi `terminate()` selesai.
*Remediasi:* Pastikan Nginx dan PHP-FPM mendukung `fastcgi_finish_request()`:
```nginx
fastcgi_keep_conn on;
fastcgi_ignore_client_abort off;
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Config & Route Caching Strictness**: Tidak boleh ada fungsi `env()` dipanggil selain di dalam direktori `config/*`. Seluruh pembacaan konfigurasi harus lewat `config('app.name')`.
- [ ] **Worker Memory Threshold**: Atur batas memori worker restart pada Octane/FrankenPHP (contoh: `--max-requests=2500` atau `--memory-limit=512`).
- [ ] **Dependency Rebinding Hygiene**: Jangan gunakan closures anonim besar di dalam provider `register()`. Pecah menjadi kelas factory khusus untuk menjaga konsistensi Opcache Preloading.
- [ ] **Explicit Contextual Targets**: Hindari penggunaan wildcard interface binding jika aplikasi memiliki lebih dari 3 variasi implementasi driver.
- [ ] **Deterministic Cleanups**: Daftarkan semua service yang menyimpan state internal ke array `$flush` di file konfigurasi Octane.

---

### 12. Hands-on Practice

Buat dan simpan file-file implementasi berikut di dalam repositori proyek Anda pada path: `hands-on/m02/`

#### Langkah 1: Buat Scoped Context Holder
File: `hands-on/m02/src/Context/TraceContext.php`
```php
<?php

declare(strict_types=1);

namespace HandsOn\M02\Context;

final class TraceContext
{
    private string $traceId;
    private float $startedAt;

    public function initialize(string $traceId): void
    {
        $this->traceId = $traceId;
        $this->startedAt = microtime(true);
    }

    public function getTraceId(): string
    {
        return $this->traceId ?? 'undefined';
    }

    public function getElapsedTime(): float
    {
        return microtime(true) - ($this->startedAt ?? microtime(true));
    }
}
```

#### Langkah 2: Buat Pipeline Log Driver Contextual
File: `hands-on/m02/src/Contracts/MetricReporterInterface.php`
```php
<?php

declare(strict_types=1);

namespace HandsOn\M02\Contracts;

interface MetricReporterInterface
{
    public function report(string $metric, float|int $value, array $tags = []): void;
}
```

File: `hands-on/m02/src/Services/StatsDReporter.php`
```php
<?php

declare(strict_types=1);

namespace HandsOn\M02\Services;

use HandsOn\M02\Contracts\MetricReporterInterface;

final readonly class StatsDReporter implements MetricReporterInterface
{
    public function report(string $metric, float|int $value, array $tags = []): void
    {
        // Simulasi emisi UDP ke daemon StatsD
        echo sprintf("[StatsD UDP] Metric: %s | Val: %f | Tags: %s\n", $metric, (float)$value, json_encode($tags));
    }
}
```

File: `hands-on/m02/src/Services/LogFileReporter.php`
```php
<?php

declare(strict_types=1);

namespace HandsOn\M02\Services;

use HandsOn\M02\Contracts\MetricReporterInterface;

final readonly class LogFileReporter implements MetricReporterInterface
{
    public function report(string $metric, float|int $value, array $tags = []): void
    {
        // Simulasi emisi ke local disk log
        echo sprintf("[File Log] Metric: %s | Val: %f | Tags: %s\n", $metric, (float)$value, json_encode($tags));
    }
}
```

#### Langkah 3: Terminable Middleware
File: `hands-on/m02/src/Http/Middleware/ExecutionTraceMiddleware.php`
```php
<?php

declare(strict_types=1);

namespace HandsOn\M02\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;
use HandsOn\M02\Context\TraceContext;
use HandsOn\M02\Contracts\MetricReporterInterface;

final readonly class ExecutionTraceMiddleware
{
    public function __construct(
        private TraceContext $traceContext,
        private MetricReporterInterface $reporter
    ) {}

    public function handle(Request $request, Closure $next): Response
    {
        $traceId = $request->header('X-Trace-ID', bin2hex(random_bytes(8)));
        $this->traceContext->initialize($traceId);

        $response = $next($request);
        $response->headers->set('X-Trace-ID', $traceId);

        return $response;
    }

    public function terminate(Request $request, Response $response): void
    {
        $elapsed = $this->traceContext->getElapsedTime() * 1000; // ms
        $this->reporter->report('http.request.duration_ms', $elapsed, [
            'trace_id' => $this->traceContext->getTraceId(),
            'status' => $response->getStatusCode(),
            'path' => $request->path(),
        ]);
    }
}
```

#### Langkah 4: Registrasi ServiceProvider Tingkat Lanjut
File: `hands-on/m02/src/Providers/DeepDiveServiceProvider.php`
```php
<?php

declare(strict_types=1);

namespace HandsOn\M02\Providers;

use Illuminate\Support\ServiceProvider;
use HandsOn\M02\Context\TraceContext;
use HandsOn\M02\Contracts\MetricReporterInterface;
use HandsOn\M02\Services\StatsDReporter;
use HandsOn\M02\Services\LogFileReporter;
use HandsOn\M02\Http\Middleware\ExecutionTraceMiddleware;

final class DeepDiveServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        // Registrasikan context sebagai scoped instance
        $this->app->scoped(TraceContext::class, function () {
            return new TraceContext();
        });

        // Contextual binding: Middleware menggunakan StatsD
        $this->app->when(ExecutionTraceMiddleware::class)
            ->needs(MetricReporterInterface::class)
            ->give(StatsDReporter::class);

        // Fallback default
        $this->app->bind(MetricReporterInterface::class, LogFileReporter::class);
    }
}
```

---

### 13. Exercises

#### Level Easy
Ubah konfigurasi container agar saat kelas `App\Services\PaymentService` membutuhkan interface `App\Contracts\PaymentGatewayInterface`, kontainer memberikan instansiasi `App\Services\StripePaymentGateway`, sedangkan kelas lainnya mendapatkan `App\Services\FakePaymentGateway`.
```php
// Solusi:
$this->app->when(\App\Services\PaymentService::class)
    ->needs(\App\Contracts\PaymentGatewayInterface::class)
    ->give(\App\Services\StripePaymentGateway::class);

$this->app->bind(
    \App\Contracts\PaymentGatewayInterface::class,
    \App\Services\FakePaymentGateway::class
);
```

#### Level Medium
Buat sebuah custom pipeline runner bernama `TransactionPipeline` yang memproses objek `TransactionContext` melewati 3 langkah verifikasi: `CheckBalance`, `VerifyKyc`, dan `FraudDetection`. Pastikan jika salah satu step mengembalikan nilai `false`, proses langsung berhenti tanpa mengeksekusi step berikutnya.
```php
// Solusi Implementasi:
namespace App\Pipelines;

use Illuminate\Pipeline\Pipeline;

final class TransactionContext {
    public bool $isValid = true;
    public string $rejectionReason = '';
    public function __construct(public readonly int $userId, public readonly float $amount) {}
}

final class CheckBalance {
    public function handle(TransactionContext $context, \Closure $next) {
        if ($context->amount > 10000) {
            $context->isValid = false;
            $context->rejectionReason = 'Insufficient funds';
            return $context; // Break circuit: tidak memanggil $next
        }
        return $next($context);
    }
}

final class VerifyKyc {
    public function handle(TransactionContext $context, \Closure $next) {
        if ($context->userId === 404) {
            $context->isValid = false;
            $context->rejectionReason = 'KYC rejected';
            return $context;
        }
        return $next($context);
    }
}

// Eksekusi Pipeline:
$result = app(Pipeline::class)
    ->send(new TransactionContext(userId: 1, amount: 500))
    ->through([CheckBalance::class, VerifyKyc::class])
    ->then(fn ($context) => $context);
```

#### Level Hard
Buat implementasi custom wrapper container yang mampu mendeteksi *Rebinding* pada interface `App\Contracts\CacheStoreInterface`. Jika implementasi cache di-bind ulang saat runtime, service `DynamicCacheManager` harus secara otomatis mengupdate properti internal `store`-nya tanpa perlu restart worker.

```php
// Solusi:
namespace App\Core;

use Illuminate\Contracts\Foundation\Application;

interface CacheStoreInterface { public function getDriverName(): string; }
final class RedisStore implements CacheStoreInterface { public function getDriverName(): string { return 'redis'; } }
final class MemcachedStore implements CacheStoreInterface { public function getDriverName(): string { return 'memcached'; } }

final class DynamicCacheManager {
    public function __construct(private CacheStoreInterface $store) {}
    public function setStore(CacheStoreInterface $store): void { $this->store = $store; }
    public function getActiveDriver(): string { return $this->store->getDriverName(); }
}

// Di ServiceProvider:
$this->app->singleton(DynamicCacheManager::class, function (Application $app) {
    return new DynamicCacheManager($app->make(CacheStoreInterface::class));
});

// Daftarkan Rebinding Callback
$this->app->rebinding(
    CacheStoreInterface::class,
    function (Application $app, CacheStoreInterface $newStore) {
        if ($app->resolved(DynamicCacheManager::class)) {
            $app->make(DynamicCacheManager::class)->setStore($newStore);
        }
    }
);
```

---

### 14. Challenge
Rancang arsitektur **Zero-Downtime Multi-Region Pipeline Limiter** murni menggunakan kernel Laravel tanpa dependensi package eksternal:
1. Buat custom pipeline runner yang menginspeksi header `X-Region-Target` (US, EU, AP).
2. Terapkan algoritma *Sliding Window Rate Limiter* via Contextual Redis Connections (misal: Region US menggunakan cluster Redis US, Region EU menggunakan cluster Redis EU).
3. Jika koneksi Redis regional mengalami network split (timeout > 200ms), pipeline harus otomatis *fail-open* ke Local In-Memory Cache via WeakMap dan mengirim sinyal peringatan ke terminable event listener.
4. Kode harus 100% thread-safe dan bebas dari *memory state leakage* saat dijalankan di bawah Laravel Octane dengan konkurensi 1.000 concurrent requests.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Pertanyaan)
1. **Apa perbedaan mendasar antara method `$this->app->singleton()` dan `$this->app->bind()`?**
   - *Jawaban:* `bind()` meregistrasikan definisi class yang akan selalu dibuat ulang setiap kali di-*resolve*, sedangkan `singleton()` hanya membuat instansiasi objek satu kali pada pemanggilan pertama dan menyimpannya di cache internal memori kontainer untuk dikembalikan pada pemanggilan selanjutnya.

2. **Kapan method `terminate()` pada Terminable Middleware dieksekusi?**
   - *Jawaban:* Dieksekusi setelah kernel selesai memanggil method `$response->send()` (setelah header HTTP dan konten dikirimkan ke webserver/klien via FastCGI buffer).

3. **Mengapa method `env()` dilarang digunakan di luar file konfigurasi pada lingkungan produksi?**
   - *Jawaban:* Karena saat perintah `php artisan config:cache` dijalankan, Laravel memuat semua file konfigurasi ke dalam satu cache array bytecode dan menghapus variabel lingkungan runtime dari superglobal `$_ENV`/`getenv()`. Memanggil `env()` akan mengembalikan nilai `null`.

4. **Apa fungsi dari method `$this->app->scoped()` di Laravel?**
   - *Jawaban:* Menginisialisasi service yang bertindak sebagai singleton hanya dalam lingkup siklus hidup satu request/job, dan referensinya otomatis dibersihkan saat request selesai. Fitur ini dirancang khusus untuk mencegah *state leakage* pada Laravel Octane.

5. **Apa fungsi dari array `$bootstrappers` pada `Illuminate\Foundation\Http\Kernel`?**
   - *Jawaban:* Array yang mendefinisikan urutan kelas bootstrapper yang harus dijalankan sebelum request diproses (misal: loading environment, loading configuration, registering facade aliases, registering providers, dan booting providers).

#### Intermediate Level (5 Pertanyaan)
6. **Bagaimana cara kerja Contextual Binding secara internal di dalam container?**
   - *Jawaban:* Container memanfaatkan array internal `$contextual[$concrete][$abstract]`. Saat membangun kelas `$concrete`, container menginspeksi tumpukan stack resolusi (`$buildStack`). Jika ditemukan target dependensi `$abstract` di dalam array tersebut, container mengeksekusi resolver khusus yang terdaftar alih-alih melakukan resolusi binding global.

7. **Apa yang terjadi jika Anda memanggil `$this->app->make()` pada kelas konkret yang belum pernah didaftarkan sama sekali di Service Provider?**
   - *Jawaban:* Container akan menggunakan PHP Reflection API (`ReflectionClass`) untuk membaca constructor kelas tersebut (*Zero-configuration resolution* / *Auto-wiring*). Jika seluruh dependensi constructor bertipe kelas konkret atau interface yang sudah terikat, container berhasil membuat objeknya secara otomatis.

8. **Jelaskan risiko penggunaan properti static di dalam controller saat aplikasi dijalankan dengan Laravel Octane!**
   - *Jawaban:* Pada Octane, worker process PHP tidak dimatikan antar-request. Properti static akan bertahan di memori lintas request pengguna yang berbeda, mengakibatkan kebocoran data (*data leakage/state pollution*) dan pertumbuhan konsumsi memori tak terkontrol (*memory leak*).

9. **Mengapa method `array_reduce` digunakan pada abstraksi Pipeline?**
   - *Jawaban:* Karena Pipeline mengimplementasikan konsep *decorator composition*. `array_reduce` mereduksi array middleware menjadi satu Closure tunggal yang terkurung berlapis (*nested closures*), di mana setiap lapisan membungkus lapisan berikutnya dan diakhiri oleh *destination core action*.

10. **Bagaimana cara mengatasi memori yang membengkak akibat event listener pada worker persisten Octane?**
    - *Jawaban:* Daftarkan listener pembersih pada event `Illuminate\Contracts\Http\Kernel::terminate` atau Octane `RequestTerminated` untuk melepaskan referensi array, mengosongkan static properties, atau menggunakan `WeakMap` untuk mengikat objek terhadap lifecycle request.

#### Kasus Arsitektur Produksi (3 Skenario)
11. **Skenario 1:** Sebuah aplikasi API mengalami memory leak di production (RAM worker naik terus hingga worker di-kill OOM) setelah bermigrasi ke Laravel Octane. Setelah audit, ditemukan bahwa ada Singleton service bernama `AuditTrailCollector` yang menampung log transaksi ke dalam array privat sebelum di-*bulk insert*. 
    - *Identifikasi Masalah & Solusi:*
      - *Akar Masalah:* Singleton tidak direset saat request selesai, array terus bertambah setiap ada request baru hingga memori habis.
      - *Solusi:* Ubah binding dari `singleton` ke `scoped`, atau implementasikan pembersihan array eksplisit dengan mengeksekusi flush data di akhir request via method `flush()` yang didaftarkan ke array `octane.flush` atau lewat middleware `terminate()`.

12. **Skenario 2:** Sebuah aplikasi SaaS B2B mengharuskan koneksi database berganti secara dinamis tergantung subdomain klien (`tenant_a`, `tenant_b`). Engineer meletakkan logic pergantian koneksi di method `boot()` pada `AppServiceProvider`. Mengapa pendekatan ini salah dan bagaimana arsitektur yang benar?
    - *Identifikasi Masalah & Solusi:*
      - *Akar Masalah:* Method `boot()` pada service provider dieksekusi sebelum routing middleware dijalankan, sehingga Request URL/Route parameter subdomain belum diuraikan oleh router Laravel.
      - *Solusi:* Buat `IdentifyTenantMiddleware` yang berada di pipeline HTTP. Ekstrak subdomain di dalam middleware, kemudian gunakan `DB::purge('tenant')` dan `Config::set('database.connections.tenant.database', $tenantDbName)` serta `DB::reconnect('tenant')` secara kontekstual per request.

13. **Skenario 3:** Tim Anda mengembangkan sistem otorisasi berbasis Policy yang sangat kompleks. Setiap evaluasi permission menjalankan $5$ query database. Pada satu endpoint, policy dipanggil $30$ kali untuk validasi list data koleksi, mengakibatkan $150$ query database redundan.
    - *Identifikasi Masalah & Solusi:*
      - *Akar Masalah:* Policy tidak meng-cache hasil evaluasi permission internal untuk model User dan Resource yang sama dalam siklus satu request (*Request-level cache miss*).
      - *Solusi:* Implementasikan repository permission yang diikat dengan `scoped` lifecycle di Service Container. Di dalam repository, simpan hasil verifikasi permission ke properti in-memory array/WeakMap dengan key `user_{id}_perm_{action}_{resource_id}`. Seluruh pemanggilan Policy akan mengambil dari cache in-memory tanpa menyentuh database berulang kali, dan otomatis bersih pada request berikutnya.

---

### 16. Summary
1. **Service Container Laravel** adalah IoC container dinamis yang memanfaatkan Reflection API untuk *autowiring*, namun memberikan kontrol granular lewat *contextual binding*, *method injection*, dan *lifecycle scopes*.
2. **Pipeline Pattern** adalah tulang punggung pemrosesan request-response yang mengemas middleware menggunakan komposisi closure berlapis via `array_reduce`.
3. **Peralihan ke Arsitektur Persisten (Octane)** mengubah model eksekusi dari *Shared-Nothing* menjadi *Long-running Process*. Pemahaman atas perbedaan siklus hidup singleton vs scoped instances adalah syarat mutlak untuk mencegah bug fatal *State Pollution*.
4. **Terminable Middleware** memungkinkan pemisahan beban komputasi/I/O non-kritis ke fase pasca-pengiriman respon, mempercepat latensi respon yang dirasakan oleh end-user secara signifikan.