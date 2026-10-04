# Bab 01 Module 01: Anatomi Request Lifecycle dan Bootstrapping Service Container

---

## 1. Module Overview & Learning Objectives

Modul ini membedah mekanisme internal eksekusi Laravel dari level runtime engine PHP-FPM hingga HTTP response dikembalikan ke client. Anda akan mempelajari transisi lifecycle, pembentukan Application Context, register/boot cycle pada Service Providers, hingga resolusi dependency melalui Service Container (IoC).

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** alur eksekusi request Laravel mulai dari entry point `public/index.php`, HTTP Kernel, Service Provider phases, hingga Pipeline dispatching.
- **Mengidentifikasi** perbedaan mendasar antara fase `register()` dan `boot()` pada `ServiceProvider` guna mencegah dependency resolution race conditions.
- **Mendiagnosis** memory leak dan bottleneck performa pada environment stateful (Laravel Octane) versus standard ephemeral runtime (PHP-FPM).
- **Mengimplementasikan** kustom bootstraper dan container binding secara type-safe dengan dependency injection berbasis PSR-11.

---

## 2. Conceptual Architecture & Mental Model

Di level sistem operasi dan Web Server (Nginx/Apache), request HTTP diubah menjadi environment variable via protokol FastCGI (CGI/FCGI) dan dikirim ke PHP-FPM master process, yang mendelegasikannya ke worker process.

```
[Client Request] 
       │
       ▼
[Web Server (Nginx)] 
       │ (FastCGI / UNIX Socket)
       ▼
[PHP-FPM Worker Pool] ──> Menjalankan isolated script instance
       │
       ▼
[public/index.php] ──────> Entry point tunggal
       │
       ├─► [Composer Autoloader] (`vendor/autoload.php`)
       │
       ├─► [Bootstrap Application] (`bootstrap/app.php`)
       │        └─ Instansiasi `Illuminate\Foundation\Application` (IoC Container)
       │
       ├─► [Kernel Handling] (`Illuminate\Foundation\Http\Kernel`)
       │        ├─ Global Middlewares via Pipeline (Onion Architecture)
       │        ├─ Bootstrappers Execution:
       │        │    ├─ LoadEnvironmentVariables (.env)
       │        │    ├─ LoadConfiguration (config/*.php)
       │        │    ├─ HandleExceptions (Error handling)
       │        │    ├─ RegisterFacades (Facade alias mapping)
       │        │    ├─ RegisterProviders (Jalankan register() semua provider)
       │        │    └─ BootProviders (Jalankan boot() semua provider)
       │        │
       │        └─ Routing Engine ──> Route Matching ──> Controller/Action
       │
       ├─► [Response Generation & Headers Propagation]
       │
       └─► [Terminate Lifecycle] ──> Terminating Middlewares & Shutdown Handlers
```

Pada PHP tradisional (ephemeral execution model), seluruh siklus di atas diulang dari nol untuk setiap request: memory dialokasikan, script di-parse, dieksekusi, dan seluruh state di-flush dari RAM. 

Di runtime modern seperti **Laravel Octane (Swoole/RoadRunner)**, Application Container hanya di-bootstrap **satu kali** saat server pertama kali start. Tiap request yang masuk hanya menggunakan container clone atau state yang sudah siap (pre-warmed), sehingga bootstrap overhead tereduksi dari ~25-50ms menjadi mikrodetik.

---

## 3. Why This Matters: Failure Modes & Real-World Impact

Memahami alur lifecycle bukan sekadar teori akademis; ketidaktahuan atas arsitektur ini memicu insiden sistem fatal:

1. **State Leakage dalam Octane/Daemon Runtime:**
   Mengikat (*binding*) dependency berstatus mutable ke dalam Container secara `singleton` dapat menyebabkan data user A bocor ke user B karena Application Context tidak dihancurkan antar request.
2. **Provider Circular Dependency / Premature Resolution:**
   Memanggil method `app()->make()` atau dependency injection di method `register()` milik Service Provider sebelum core provider lain (seperti Config atau Database) selesai di-register akan menghasilkan exception fatal: *Target class does not exist* atau *Unresolvable dependency resolution*.
3. **Overhead Akibat Over-Bootstrapping:**
   Mendaftarkan logic berat (I/O, database query, API ping) langsung di dalam `boot()` method Service Provider yang berjalan di setiap HTTP request (termasuk untuk static asset atau health check endpoints) akan melipatgandakan response latency secara signifikan.

---

## 4. What: Technical Definition & Internal Mechanics

### Entry Point (`public/index.php`)
File ini memiliki tanggung jawab minimal:
1. Mendefinisikan konstanta `LARAVEL_START` untuk benchmarking.
2. Memuat Composer autoloader PSR-4.
3. Memanggil bootstrap file `bootstrap/app.php`.
4. Mengambil instance `Illuminate\Contracts\Http\Kernel`.
5. Mengirim `Illuminate\Http\Request` ke Kernel untuk diproses dan memanggil `send()` pada `Illuminate\Http\Response`.
6. Memanggil `$kernel->terminate($request, $response)` untuk post-response tasks.

### The Application Instance (`Illuminate\Foundation\Application`)
Merupakan turunan langsung dari `Illuminate\Container\Container`. Objek ini adalah *God Object* arsitektur Laravel yang bertindak sebagai:
- **IoC Container Registry:** Menyimpan mapping interface-to-implementation.
- **Service Locator Internal:** Menyimpan shared singletons.
- **Path Repository:** Mengelola absolute base path sistem.

### Bootstrappers (`\Illuminate\Foundation\Bootstrap\*`)
Array class yang dieksekusi oleh HTTP Kernel via method `$kernel->bootstrap()` sebelum request dialirkan ke router.
- `LoadEnvironmentVariables`: Parsing `.env` via `vlucas/phpdotenv`.
- `LoadConfiguration`: Membaca dan mengonsolidasi seluruh array konfigurasi dari path `config/`.
- `HandleExceptions`: Mendaftarkan custom error handling, fatal shutdown function, dan standard warning trap.
- `RegisterFacades`: Mendaftarkan `Facade::setFacadeApplication($this)`.
- `RegisterProviders`: Mengiterasi array providers dan mengeksekusi `register()`.
- `BootProviders`: Mengiterasi array providers dan mengeksekusi `boot()`.

---

## 5. How: Step-by-Step Execution Pipeline

1. **HTTP Ingestion:** Client mengirim HTTP request ke port 80/443. Web server memetakan URI ke `public/index.php`.
2. **Composer Autoload Init:** Class map dan PSR-4 map dialokasikan ke memori.
3. **Application Instantiation:** `new Application(realpath(__DIR__.'/../'))`. Base bindings terdaftar: `app`, `Container::class`, `PackageManifest`.
4. **Kernel Capturing:** Kernel mengambil request capture: `Request::capture()`, membungkus global `$_GET`, `$_POST`, `$_SERVER`, `$_COOKIE`, dan `php://input`.
5. **Bootstrapper Pipeline:** Eksekusi 6 bootstrapper default secara sekuensial.
6. **Middleware Pipeline Dispatching:** Menggunakan pattern Pipeline (`Illuminate\Pipeline\Pipeline`). Request dialirkan menembus array of global middlewares.
7. **Route Resolution:** Router (`Illuminate\Routing\Router`) mencocokkan HTTP Method dan Path dengan RouteCollection.
8. **Controller / Action Execution:** Parameter route di-resolve via Reflection API / Route Model Binding, dependencies di-inject otomatis via container.
9. **Response Transformation:** Output controller (String, Array, Model, Resource) dibungkus menjadi instance `Illuminate\Http\Response` atau `JsonResponse`.
10. **Emitting Output:** `$response->send()` mengirimkan HTTP status code, header via `header()`, dan stream body via `echo`.
11. **Termination:** Kernel menjalankan `terminate()` untuk memicu middleware terminable dan event `kernel.handled`. FastCGI connection ditutup via `fastcgi_finish_request()`.

---

## 6. Architecture / Data Flow Diagram

Berikut visualisasi aliran data mulai dari Ingestion layer sampai Termination phase:

```
[ HTTP Ingestion: Nginx ]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ public/index.php                                       │
│                                                        │
│ 1. composer/autoload.php                               │
│ 2. bootstrap/app.php ──► Instansiasi Application ($app)│
└───────────────────┬────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│ Illuminate\Foundation\Http\Kernel                      │
│                                                        │
│  [ Bootstrapping Phase ]                               │
│  ├── LoadEnvironmentVariables                         │
│  ├── LoadConfiguration                                 │
│  ├── HandleExceptions                                  │
│  ├── RegisterFacades                                   │
│  ├── RegisterProviders ──► [Provider::register()]      │
│  └── BootProviders     ──► [Provider::boot()]          │
│                                                        │
│  [ Pipeline Passing: Outer-to-Inner Onion ]           │
│  ├── CheckForMaintenanceMode                           │
│  ├── ValidatePostSize                                  │
│  ├── TrimStrings / ConvertEmptyStringsToNull          │
│  │                                                     │
│  ▼                                                     │
│  [ Router & Dispatcher ]                               │
│  ├── Route Matching                                    │
│  ├── Route Middlewares (Auth, Throttle)                │
│  │                                                     │
│  ▼                                                     │
│  [ Controller / Closure Action Resolution ]            │
│  └── Method Injection via Reflection API               │
│                                                        │
│  [ Pipeline Return: Inner-to-Outer Onion ]            │
│  └── Response Decoration & Header Injection           │
└───────────────────┬────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│ Emitting to Client: $response->send()                  │
│ fastcgi_finish_request() (jika didukung)               │
└───────────────────┬────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────┐
│ Kernel Termination Phase: $kernel->terminate()         │
│ └── Terminable Middleware (TerminableInterface)        │
│ └── Cleanups, Queued jobs dispatching, Octane Resets   │
└────────────────────────────────────────────────────────┘
```

---

## 7. Minimal / Simple Example

Berikut adalah simulasi rekonstruksi arsitektur *Service Container* dan *Pipeline Dispatcher* minimal yang mendasari request lifecycle Laravel:

```php
<?php

declare(strict_types=1);

namespace Core;

use Closure;
use ReflectionClass;
use RuntimeException;

// 1. Core Container (Inversion of Control)
class SimpleContainer
{
    /** @var array<string, mixed> */
    protected array $bindings = [];
    
    /** @var array<string, object> */
    protected array $instances = [];

    public function bind(string $abstract, Closure|string|null $concrete = null, bool $shared = false): void
    {
        $concrete ??= $abstract;
        $this->bindings[$abstract] = compact('concrete', 'shared');
    }

    public function singleton(string $abstract, Closure|string|null $concrete = null): void
    {
        $this->bind($abstract, $concrete, true);
    }

    public function make(string $abstract): mixed
    {
        if (isset($this->instances[$abstract])) {
            return $this->instances[$abstract];
        }

        $concrete = $this->bindings[$abstract]['concrete'] ?? $abstract;

        if ($concrete instanceof Closure) {
            $object = $concrete($this);
        } else {
            $object = $this->build($concrete);
        }

        if (!empty($this->bindings[$abstract]['shared'])) {
            $this->instances[$abstract] = $object;
        }

        return $object;
    }

    protected function build(string $concrete): object
    {
        $reflector = new ReflectionClass($concrete);

        if (!$reflector->isInstantiable()) {
            throw new RuntimeException("Target [{$concrete}] is not instantiable.");
        }

        $constructor = $reflector->getConstructor();
        if (is_null($constructor)) {
            return new $concrete();
        }

        $dependencies = array_map(function ($param) {
            $type = $param->getType();
            if (!$type || $type->isBuiltin()) {
                throw new RuntimeException("Cannot resolve primitive dependency {$param->getName()}");
            }
            return $this->make($type->getName());
        }, $constructor->getParameters());

        return $reflector->newInstanceArgs($dependencies);
    }
}

// 2. Request & Execution Pipeline (Onion Architecture)
class Request { public string $uri = '/api/v1/health'; }
class Response { public function __construct(public string $content, public int $status = 200) {} }

class Pipeline
{
    /** @var array<class-string> */
    protected array $pipes = [];

    public function send(Request $passable): self
    {
        $this->passable = $passable;
        return $this;
    }

    public function through(array $pipes): self
    {
        $this->pipes = $pipes;
        return $this;
    }

    public function then(Closure $destination): Response
    {
        $pipeline = array_reduce(
            array_reverse($this->pipes),
            function ($stack, $pipe) {
                return function ($passable) use ($stack, $pipe) {
                    return (new $pipe())->handle($passable, $stack);
                };
            },
            $destination
        );

        return $pipeline($this->passable);
    }
}

// 3. Middlewares
class MeasureExecutionTime
{
    public function handle(Request $request, Closure $next): Response
    {
        $start = microtime(true);
        /** @var Response $response */
        $response = $next($request);
        $elapsed = (microtime(true) - $start) * 1000;
        $response->content .= " | Execution: " . number_format($elapsed, 2) . "ms";
        return $response;
    }
}

// 4. Client Execution
$app = new SimpleContainer();
$pipeline = new Pipeline();

$response = $pipeline
    ->send(new Request())
    ->through([MeasureExecutionTime::class])
    ->then(fn(Request $req) => new Response("Payload processed from {$req->uri}"));

echo $response->content . "\n";
// Output: Payload processed from /api/v1/health | Execution: 0.0Xms
```

---

## 8. Real-World Practical Example

Contoh nyata production-grade implementation: Memasang custom Contextual Telemetry Provider yang mengikat correlation-id (UUIDv7) ke IoC Container sebelum dependency domain layer diproses, lalu melacak lifecycle request sampai fase termination.

### 1. The Context Object

```php
<?php

declare(strict_types=1);

namespace App\Core\Telemetry;

use Symfony\Component\Uid\Uuid;

final class RequestCorrelationContext
{
    private readonly string $correlationId;
    private readonly float $startTime;

    public function __construct(?string $correlationId = null)
    {
        $this->correlationId = $correlationId ?? Uuid::v7()->toRfc4122();
        $this->startTime = microtime(true);
    }

    public function getCorrelationId(): string
    {
        return $this->correlationId;
    }

    public function getDurationMs(): float
    {
        return (microtime(true) - $this->startTime) * 1000;
    }
}
```

### 2. The Custom Service Provider

```php
<?php

declare(strict_types=1);

namespace App\Providers;

use App\Core\Telemetry\RequestCorrelationContext;
use Illuminate\Contracts\Support\DeferrableProvider;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\ServiceProvider;

final class TelemetryServiceProvider extends ServiceProvider
{
    /**
     * Daftarkan binding konteks ke IoC Container.
     * PERINGATAN: Jangan resolve service lain di dalam method ini!
     */
    public function register(): void
    {
        $this->app->scoped(RequestCorrelationContext::class, function ($app) {
            // Membaca incoming header jika ada, atau buat baru.
            $request = $app->make('request');
            $incomingId = $request->header('X-Correlation-ID');

            return new RequestCorrelationContext(
                is_string($incomingId) && !empty($incomingId) ? $incomingId : null
            );
        });
    }

    /**
     * Bootstrap services setelah seluruh register cycle selesai.
     */
    public function boot(): void
    {
        // Setup contextual logging via context tracking
        $context = $this->app->make(RequestCorrelationContext::class);
        
        Log::withContext([
            'correlation_id' => $context->getCorrelationId(),
        ]);
    }
}
```

### 3. Terminable Middleware for Performance & Header Emission

```php
<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use App\Core\Telemetry\RequestCorrelationContext;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Symfony\Component\HttpFoundation\Response;

final class TrackRequestLifecycleMiddleware
{
    public function __construct(
        private readonly RequestCorrelationContext $context
    ) {}

    public function handle(Request $request, Closure $next): Response
    {
        /** @var Response $response */
        $response = $next($request);

        // Pasang header korelasi untuk tracing end-to-end oleh consumer API
        $response->headers->set('X-Correlation-ID', $this->context->getCorrelationId());

        return $response;
    }

    /**
     * Dipanggil otomatis oleh Kernel saat fase terminate (post HTTP emission)
     */
    public function terminate(Request $request, Response $response): void
    {
        Log::info('HTTP Request Cycle Completed', [
            'method'      => $request->getMethod(),
            'uri'         => $request->getRequestUri(),
            'status'      => $response->getStatusCode(),
            'duration_ms' => round($this->context->getDurationMs(), 2),
            'memory_peak' => memory_get_peak_usage(true) / 1024 / 1024 . ' MB',
        ]);
    }
}
```

### 4. Registration via `bootstrap/app.php` (Laravel 11 Structure)

```php
<?php

use App\Http\Middleware\TrackRequestLifecycleMiddleware;
use App\Providers\TelemetryServiceProvider;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withProviders([
        TelemetryServiceProvider::class,
    ])
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->append(TrackRequestLifecycleMiddleware::class);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        // Exception binding
    })->create();
```

---

## 9. Trade-Off Analysis

| Pendekatan / Pola | Keuntungan | Kerugian | Skenario Penggunaan |
| :--- | :--- | :--- | :--- |
| **Traditional Lifecycle (PHP-FPM Ephemeral)** | Isolasi memori sempurna. Tidak ada resiko memory leak lintas request. Debugging trivial. | Latensi tinggi (20ms-50ms CPU time terbuang tiap request untuk mem-parsing dan bootstrapping class). | Sistem monolitik standar, CMS, internal tools dengan beban request per second (RPS) < 500. |
| **Daemonized/Pre-warmed Container (Octane/Swoole)** | Eksekusi super cepat (<2ms). Bootstrap hanya terjadi 1x. Resource CPU digunakan murni untuk domain logic. | Rentan Memory Leak; static property dan singletons bertahan di RAM. Memerlukan lifecycle hygiene ketat. | High-traffic public API, Realtime system, processing rate > 2000 RPS per node. |
| **Container Binding: Singleton (`singleton()`)** | Instansiasi objek tunggal, hemat CPU dan alokasi memory objek berat. | State tetap ada sepanjang container hidup. Berbahaya untuk objek yang mengikat `Request` atau `User`. | Service stateless seperti Mailer Client, S3 Client, Database Connection Pool. |
| **Container Binding: Scoped (`scoped()`)** | Aman di environment Octane; dibersihkan otomatis di akhir tiap lifecycle request. | Overhead rekonstruksi objek baru setiap cycle request dimulai. | Context holder, Auth User Session, Current Correlation Id. |

---

## 10. Anti-Patterns & Common Traps

### 1. Injeksi Request ke dalam Singleton Service

❌ **Anti-Pattern:**
```php
$this->app->singleton(PaymentProcessor::class, function ($app) {
    // BUG FATAL DI OCTANE: $app->make('request') akan me-retain Request pertama selamanya!
    return new PaymentProcessor($app->make('request')->bearerToken());
});
```

✅ **Pola Benar:**
```php
// Teruskan konteks via Method Injection saat eksekusi, bukan saat instantiation constructor
$this->app->singleton(PaymentProcessor::class, function () {
    return new PaymentProcessor();
});

// Pada Domain Layer / Controller
$processor->process($request->bearerToken(), $payload);
```

### 2. State Assumption di Service Provider `register()`

❌ **Anti-Pattern:**
```php
public function register(): void
{
    // FATAL: Event dispatcher atau Config mungkin belum selesai di-load oleh Core
    Event::listen(SomeEvent::class, SomeListener::class);
    
    // FATAL: Mengambil config di register bisa menyebabkan konfigurasi stale
    $secret = config('services.payment.secret');
}
```

✅ **Pola Benar:**
```php
public function register(): void
{
    // Hanya lakukan deklarasi binding IoC
    $this->app->bind(PaymentGatewayInterface::class, StripePaymentGateway::class);
}

public function boot(): void
{
    // Aman: Seluruh service provider telah dieksekusi method register()-nya
    Event::listen(SomeEvent::class, SomeListener::class);
}
```

---

## 11. Best Practices & Production Guidelines

1. **Jaga `register()` Tetap Murni (Pure Declarations):** Method `register()` hanya boleh digunakan untuk mengikat interface ke konkret class ke dalam `$this->app`. Jangan pernah mengeksekusi instansiasi objek, dispatching event, atau pemanggilan konfigurasi domain di sini.
2. **Gunakan `scoped()` untuk Objek Request-Dependent:** Jika sebuah service menyimpan state yang valid hanya selama siklus satu HTTP request berjalan, gunakan `$this->app->scoped()` alih-alih `$this->app->singleton()`.
3. **Eksekusi Heavy Tasks di Luar Request Critical Path:** Pindahkan logging analitik, notifikasi email, dan dispatching eksternal webhook ke fase `terminate()` (Terminable Middleware) atau Queue Worker sehingga koneksi FastCGI ke client dapat ditutup lebih cepat via `fastcgi_finish_request()`.
4. **Compile & Cache Configuration:** Pada fase deployment production, **wajib** menjalankan `php artisan config:cache`, `php artisan route:cache`, dan `php artisan view:cache` guna mengabaikan proses pemindaian direktori disk yang memakan ratusan I/O system calls pada bootstrapper.

---

## 12. Edge Cases & Failure Modes

1. **FastCGI Socket Drop:** Jika PHP-FPM worker kehabisan waktu (`max_execution_time`) saat berada di tengah execution pipeline, lifecycle Kernel berhenti seketika. Method `terminate()` pada middleware **tidak akan dieksekusi**, meninggalkan resource state yang menggantung (misal: unclosed locks pada Redis).
2. **Infinite Dependency Resolution Loop:** Jika Service A membutuhkan Service B melalui constructor, dan Service B membutuhkan Service A, pemanggilan `$app->make(ServiceA::class)` akan memicu recursive stack overflow:
   ```
   Fatal error: Maximum function nesting level of '512' reached, aborting!
   ```
   *Mitigasi:* Gunakan Event-driven approach atau Setter/Method injection untuk memecah direct dependency cycle.
3. **Out-of-Memory (OOM) pada Terminable Middlewares:** Terminable middleware dieksekusi setelah output dikirim ke browser, namun worker PHP masih hidup. Jika developer mengeksekusi memory-heavy database load di fase `terminate()`, worker dapat terbunuh oleh Linux OOM Killer sebelum menyelesaikan proses, tanpa sempat mengirim log error HTTP 500 ke client.

---

## 13. Security Implications (OWASP & Runtime Isolation)

- **Sensitive Variable Pollution:** Bootstrap class `LoadEnvironmentVariables` menyalin nilai dari file `.env` ke environment PHP (`$_ENV`, `$_SERVER`, `getenv()`). Jangan pernah membiarkan debugging tools mencetak dump dari `$app->toArray()` atau `phpinfo()` karena kunci enkripsi (`APP_KEY`) dan credential database akan terekspos secara transparan.
- **Header Injection via Untrusted Proxies:** Request capture mengandalkan client IP dan HTTP Host headers. Jika Laravel berada di belakang reverse proxy (Cloudflare, AWS ALB) dan `TrustProxies` middleware tidak dikonfigurasi secara eksplisit, penyerang dapat memalsukan IP melalui header `X-Forwarded-For` untuk membypass rate-limiting lifecycle.

---

## 14. Performance & Resource Considerations

- **Memory Footprint:** Basic empty bootstrap Laravel mengonsumsi sekitar **8MB - 12MB** memory per request di standard PHP-FPM. Pemanggilan reflection pada Service Container memiliki kompleksitas $O(1)$ untuk class yang telah di-resolve (tersimpan di internal array map), namun konstruksi dynamic reflection pertama kali memakan $O(n)$ proportional terhadap jumlah parameter constructor dan inheritance tree.
- **OPcache Impact:** Tanpa OPcache, PHP harus mengompilasi ratusan file Laravel menjadi bytecode pada setiap request, menaikkan request overhead hingga **200-400%**. Pastikan parameter `opcache.enable=1` dan `opcache.validate_timestamps=0` diset aktif di environment production.

---

## 15. Testing Strategies & Verification

Memverifikasi Service Provider dan lifecycle binding menggunakan test suite PHPUnit/Pest:

```php
<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Core\Telemetry\RequestCorrelationContext;
use Tests\TestCase;

final class LifecycleContainerTest extends TestCase
{
    public function test_telemetry_context_is_bound_as_scoped_instance(): void
    {
        // 1. Resolve instance pertama
        $instanceA = $this->app->make(RequestCorrelationContext::class);
        $this->assertNotEmpty($instanceA->getCorrelationId());

        // 2. Resolve instance kedua pada container context yang sama
        $instanceB = $this->app->make(RequestCorrelationContext::class);
        $this->assertSame($instanceA, $instanceB, 'Context harus identik di satu request cycle');

        // 3. Simulasikan lifecycle flush (seperti yang dilakukan Laravel Octane)
        $this->app->forgetScopedInstances();

        // 4. Resolve kembali, harus menghasilkan instance baru
        $instanceC = $this->app->make(RequestCorrelationContext::class);
        $this->assertNotSame($instanceA, $instanceC, 'Instance baru harus terbuat setelah scope di-flush');
    }
}
```

---

## 16. Observability, Telemetry & Debugging

Untuk menelusuri bootstraping phase secara programmatic, daftarkan tracing checkpoints langsung pada kernel events di file `bootstrap/app.php`:

```php
<?php

use Illuminate\Foundation\Http\Events\RequestHandled;
use Illuminate\Support\Facades\Event;

Event::listen(RequestHandled::class, function (RequestHandled $event) {
    $bootstrapDuration = microtime(true) - LARAVEL_START;
    
    if ($bootstrapDuration > 0.050) { // Log jika lifecycle overhead > 50ms
        error_log(sprintf(
            '[SLOW BOOTSTRAP ALERT] Route: %s | Time: %.4fs',
            $event->request->path(),
            $bootstrapDuration
        ));
    }
});
```

Saat debugging secara lokal, Anda dapat memeriksa daftar service provider yang terdaftar beserta bootstrappernya menggunakan CLI:

```bash
php artisan about
```

---

## 17. Enterprise Scale & Resilience

Pada arsitektur microservices berskala tinggi:
- **Stateless Pod Auto-scaling:** Pod horizontal autoscaler (HPA) di Kubernetes bergantung pada cold-start minimal. Pastikan `composer dump-autoload --optimize --classmap-authoritative` dieksekusi saat Docker image build untuk menghilangkan filesystem scanning yang memperlambat startup time pod baru.
- **Graceful Shutdown Integration:** Tangkap signal `SIGTERM` dari orchestrator. Di Laravel Octane, server membiarkan in-flight request menyelesaikan pipeline cycle-nya sebelum mematikan container worker pool (`--max-requests` cycle management).

---

## 18. Self-Assessment: Hands-On Challenge

### Skenario:
Sistem core banking Anda membutuhkan mekanisme di mana setiap database query yang dieksekusi selama request lifecycle menyertakan comment prefix yang berisi `Transaction-Context-ID`. ID ini dibuat di level awal request lifecycle dan harus dapat diakses di model manapun secara otomatis tanpa passing variable manual di Controller/Repository.

### Instruksi Penugasan:
1. Buat class `TransactionContext` yang menyimpan context ID unik.
2. Buat `TransactionContextServiceProvider` yang mengikat context tersebut secara aman untuk environment Octane (hindari memory leakage lintas request).
3. Buat Middleware yang menginisialisasi context dari incoming header HTTP `X-Txn-ID` (atau generate UUID jika absen).
4. Kaitkan context ID tersebut dengan Database Query Listener menggunakan `DB::beforeExecuting()` di method `boot()` provider.
5. Tulis unit test untuk membuktikan bahwa context ID ter-reset sepenuhnya saat container memanggil `$app->forgetScopedInstances()`.

---

## 19. Self-Assessment: Diagnostic Quiz

Jawablah pertanyaan berikut untuk menguji pemahaman mendalam Anda.

1. **Mengapa method `config('...')` berisiko mengembalikan nilai lama atau error jika dipanggil di dalam method `register()` pada Service Provider kustom?**
   - A. Karena file `.env` baru diparsing pada fase routing.
   - B. Karena bootstrapper `LoadConfiguration` belum tentu berjalan sebelum `RegisterProviders`.
   - C. Karena konfigurasi hanya boleh dipanggil dari dalam Controller.
   - D. Karena Service Provider lain mungkin sedang memodifikasi config secara async.

2. **Perbedaan fungsional utama antara method `$kernel->handle($request)` dan `$kernel->terminate($request, $response)` adalah:**
   - A. `handle` mengeksekusi routing, sedangkan `terminate` mengembalikan payload HTTP ke browser.
   - B. `handle` berjalan di user-space PHP, sedangkan `terminate` dieksekusi di level kernel C PHP-FPM.
   - C. `handle` memproses request hingga menghasilkan Response, sedangkan `terminate` memicu terminable middleware setelah response dikirim ke client.
   - D. `terminate` hanya berjalan ketika terjadi unhandled exception pada aplikasi.

3. **Pada implementasi Laravel Octane, apa yang terjadi jika Anda mendaftarkan instance class yang memegang reference objek Request ke dalam IoC Container menggunakan method `$this->app->singleton()`?**
   - A. Server Octane akan crash seketika dengan error Segment Fault.
   - B. Terjadi state leakage: request berikutnya dari client lain akan mengakses data request sebelumnya yang tersisa di memory.
   - C. Octane otomatis mengonversinya menjadi non-singleton tanpa konfirmasi.
   - D. Objek Request otomatis ter-refresh setiap kali controller dipanggil.

4. **Kapan instance dari class `Illuminate\Foundation\Application` pertama kali dibuat dalam sebuah web request standar?**
   - A. Di dalam constructor `Illuminate\Foundation\Http\Kernel`.
   - B. Saat Composer autoloader selesai mengindeks class map.
   - C. Di dalam file `bootstrap/app.php` yang dipanggil oleh `public/index.php`.
   - D. Setelah Nginx menyelesaikan upstream FastCGI handshake.

5. **Apa tujuan dari bootstrapper `RegisterFacades` jika Facade sebenarnya hanyalah static proxy?**
   - A. Meng-compile file class facade menjadi bytecode statis di disk.
   - B. Menginjeksi instance Container utama (`Application`) ke static property dasar `Facade::$app` agar facade dapat meresolve service target dari container secara dinamis.
   - C. Mencegah developer membuat object instance baru dari class Facade menggunakan operator `new`.
   - D. Memeriksa integritas signature hash setiap method yang dipanggil lewat Facade.

---

### Kunci Jawaban Diagnostic Quiz

1. **B** — Urutan bootstrapper kernel bersifat deterministik. Meskipun `LoadConfiguration` defaultnya berjalan sebelum `RegisterProviders`, pemanggilan konfigurasi antar provider yang saling bergantung pada fase registrasi dapat memicu race condition sebelum state konfigurasi selesai dikonsolidasi secara menyeluruh.
2. **C** — Method `handle()` bertugas mentransformasikan Request menjadi Response melalui Middlewares dan Route resolution. Method `terminate()` dijalankan pasca data dikirim (post-emission) untuk menjalankan background housekeeping tanpa menahan koneksi client.
3. **B** — Octane tidak me-reboot application container pada setiap request. Sebuah `singleton` akan terus hidup di memory worker process lintas request, sehingga request user berikutnya dapat membaca data privat user sebelumnya.
4. **C** — File `public/index.php` memanggil `bootstrap/app.php`, dan di file `bootstrap/app.php` inilah statement pembuatan instance Application: `Application::configure(...)` atau `new Application(...)` dieksekusi.
5. **B** — Facade bekerja dengan meneruskan static call `Facade::__callStatic()` ke runtime instance yang ada di Container. Agar class abstract `Facade` tahu container mana yang harus diakses, bootstrapper `RegisterFacades` mengeksekusi `Facade::setFacadeApplication($app)`.