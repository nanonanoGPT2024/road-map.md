# BAB 02: Routing Engine, Middleware Pipeline & HTTP Layer
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** siklus hidup internal HTTP request dari `public/index.php`, melalui `Illuminate\Routing\Router`, hingga terminasi aplikasi pada kernel HTTP.
- **Mengarsitekturi** custom middleware pipeline lanjutan dengan implementasi *terminable middleware*, manipulasi response streaming, dan mutasi payload request secara immutability-safe.
- **Mengoptimalkan** performa matching route menggunakan *route caching engine* dan teknik *compiled regex tree* untuk aplikasi berskala jutaan route.
- **Membangun** mekanisme *Explicit Route Model Binding* kustom dengan caching layer multi-tingkat (L1 in-memory + L2 Redis) guna mencegah bottleneck I/O database.
- **Mendiagnosis** dan memitigasi memory leak serta state pollution pada HTTP layer saat berjalan di atas application server berbasis long-lived process runtime (Laravel Octane: FrankenPHP/Swoole/RoadRunner).

---

### 2. Prerequisite
Untuk memahami materi ini secara mendalam, Anda wajib menguasai:
- **Arsitektur Internal PHP**: Siklus hidup request PHP-FPM vs CLI Long-lived Process, Garbage Collection (Zend Engine zvals, refcounting), dan alokasi memori heap vs stack.
- **Standar Antarmuka HTTP**: Pemahaman konseptual PSR-7 (HTTP Message Interfaces), PSR-15 (HTTP Server Handlers/Middleware), serta adaptasi internal Laravel berbasis komponen Symfony HTTPFoundation (`Symfony\Component\HttpFoundation\Request` dan `Response`).
- **Design Pattern**: Gang of Four (GoF) Pipeline pattern, Chain of Responsibility, Decorator pattern, dan Dependency Injection/Service Container resolution life-cycle.
- **PHP 8.2+ Core Engine**: Typed properties, attributes, first-class callable syntax, closures, dan WeakMap.

---

### 3. Concept & Internal Architecture

#### 3.1 Siklus Hidup Request-Response Engine
Alur eksekusi HTTP Laravel tidak dimulai dari routing, melainkan dari bootstrap aplikasi di kernel HTTP. Ketika request masuk melalui web server (Nginx/Caddy/Apache) ke `public/index.php`:

```
Request (SAPI / Engine)
   │
   ▼
public/index.php
   │ (Instansiasi Application & Http\Kernel via bootstrap/app.php)
   ▼
Illuminate\Foundation\Http\Kernel::handle(Request $request)
   │
   ├──> sendRequestThroughRouter($request)
   │       │
   │       ├──> bootstrap() [Load Environment, Config, Providers, Facades, ExceptionHandler]
   │       │
   │       └──> (new Pipeline($this->app))
   │               ->send($request)
   │               ->through($this->middleware)
   │               ->then($this->dispatchToRouter())
   │                       │
   │                       ▼
   │            Illuminate\Routing\Router::dispatch($request)
   │                       │
   │                       ├──> findRoute($request) ──> RouteCollection::match($request)
   │                       │
   │                       └──> runRouteWithinStack($route, $request)
   │                               │
   │                               └──> (new Pipeline($this->app))
   │                                       ->through($middleware)
   │                                       ->then(fn() => $route->run())
   │                                               │
   │                                               ▼
   │                                     Controller / Closure Action
   ▼
Response Generated
   │
   ├──> Illuminate\Http\Response::send()
   │
   ▼
Illuminate\Foundation\Http\Kernel::terminate($request, $response)
   │
   └──> Terminating Middleware (`terminate()` hooks)
   └──> Application Terminating Callbacks
```

Di Laravel 11, struktur kernel disederhanakan melalui fluent configuration di `bootstrap/app.php` (`withRouting()`, `withMiddleware()`), namun engine internal di balik layar tetap memanfaatkan `Illuminate\Foundation\Http\Kernel` dan `Illuminate\Routing\Router`.

#### 3.2 Dynamic Route Compilation & Compiled Regex Tree
Laravel tidak mencocokkan route secara linear O(N) menggunakan perulangan looping sederhana pada production runtime yang telah dioptimasi. Sebaliknya, proses kompilasi (`php artisan route:cache`) mentransformasikan seluruh deklarasi rute menjadi satu file PHP statis (`bootstrap/cache/routes-v7.php`) yang memetakan method HTTP ke dalam struktur data *Combined Regular Expression*:

```php
// Representasi simplifikasi internal Symfony/Laravel Route Collection Compiler
[
    'GET' => [
        'regex' => '#^(?|/api/v1/users/([^/]+)(*MARK:m_user)|/api/v1/orders/([^/]+)(*MARK:m_order))$#x',
        'tokens' => [
            'm_user' => [...],
            'm_order' => [...],
        ]
    ]
]
```
Dengan operator PCRE branch reset `(?|...)` dan control verb `(*MARK:name)`, engine regex PCRE C-level mencocokkan URI path dan mengekstrak parameter dalam satu lintasan CPU cycle deterministik berkecepatan $O(1)$ amortized terhadap total rute yang terdaftar.

#### 3.3 Pipeline Architecture: Transformasi Array Reduce
Jantung pemrosesan middleware Laravel diatur oleh kelas `Illuminate\Pipeline\Pipeline`. Alur ini mengimplementasikan Chain of Responsibility pattern dengan membungkus eksekusi middleware di dalam nested anonymous closure menggunakan fungsi bawaan PHP `array_reduce`:

```php
// Mekanisme internal Illuminate\Pipeline\Pipeline::carry()
protected function carry(): Closure
{
    return function ($stack, $pipe) {
        return function ($passable) use ($stack, $pipe) {
            if (is_callable($pipe)) {
                return $pipe($passable, $stack);
            } elseif (! is_object($pipe)) {
                [$name, $parameters] = $this->parsePipeString($pipe);
                $pipe = $this->container->make($name);
                $parameters = array_merge([$passable, $stack], $parameters);
            } else {
                $parameters = [$passable, $stack];
            }

            $response = $pipe->{$this->method}(...$parameters);

            return $this->handleJsonResponse($response);
        };
    };
}
```

Setiap middleware bertindak sebagai wrapper dekorator. Pemanggilan `$next($request)` tidak langsung melompat ke middleware berikutnya secara procedural, melainkan mengevaluasi closure terluar berikutnya dari tumpukan frame call stack memory.

#### 3.4 Long-Lived Process Runtime & Memory Safety (Octane Architecture)
Pada arsitektur long-lived process runtime (FrankenPHP worker mode, RoadRunner, atau Swoole), lifecycle aplikasi tidak dihancurkan saat HTTP response selesai dikirim:
- **PHP-FPM**: Request Datang $\to$ Boot Kernel $\to$ Dispatch $\to$ Terminate $\to$ Engine State Purged (Shared Nothing).
- **Laravel Octane**: Boot Kernel Sekali (Master Process) $\to$ Request Datang $\to$ Fork Worker / Async Coroutine Execution $\to$ Reset Request-Scoped Singletons $\to$ Worker Tetap Hidup Menunggu Request Berikutnya.

**Bahaya Arsitektur**: Jika middleware menyimpan instance `$request`, data user terotentikasi, atau data transaksional ke dalam static property atau singleton service tanpa didaftarkan ke dalam array pembersihan (`octane:warm` / reset listeners), terjadi *Cross-Request Memory Leak* dan *Data Bleeding* antar user yang berbeda.

---

### 4. Why & What

| Komponen | What (Definisi & Perilaku) | Why (Alasan Rekayasa & Dampak Kritis) |
| :--- | :--- | :--- |
| **Pipeline Core Engine** | Wrapper composable untuk HTTP request/response interception via nested closure chaining. | Menjamin separation of concerns; lapisan keamanan (CORS, Rate Limiting, Sanitization, Auth) dieksekusi secara deklaratif dan terisolasi sebelum payload menyentuh core business logic. |
| **Route Cache Engine** | Serialisasi seluruh route instance ke array bytecode PHP murni via artisan command. | Meniadakan overhead registrasi route runtime, parsing file deklarasi rute, dan kompilasi closure pada setiap siklus request. Menurunkan TTFB (Time to First Byte) hingga 40-70%. |
| **Explicit Binding** | Pola resolusi parameter dinamis rute yang terikat pada IoC resolver terdedikasi. | Mencegah duplicate query injection pada controller, sentralisasi autorisasi domain boundary, dan enkapsulasi strategi multi-level caching data agregat. |
| **Terminable Pipeline** | Antarmuka middleware (`terminable`) yang mengeksekusi method `terminate()` paska network flush response. | Memindahkan komputasi berat non-kritis (e.g., audit logging, dynamic metric shipping, webhook dispatching) ke luar critical path time user, sehingga latency drop drastis. |

---

### 5. How (Workflow Detail)

Berikut adalah tahapan teknis resolusi dan dispatching route dari level Kernel:

1. **Request Ingestion**: Kernel menerima instance `Symfony\Component\HttpFoundation\Request` dan membungkusnya ke dalam `Illuminate\Http\Request`.
2. **Global Middleware Pipeline**: Request diteruskan ke global pipeline array (didefinisikan di `bootstrap/app.php`).
3. **Route Matching Step**:
   - `Router::findRoute($request)` dipanggil.
   - `RouteCollection::match()` mengevaluasi method HTTP dan path info terhadap compiled regex dictionary.
   - Jika route ditemukan, instansiasi objek `Illuminate\Routing\Route` dikembalikan; jika tidak, Symfony `ResourceNotFoundException` dilemparkan dan diterjemahkan menjadi HTTP 404.
4. **Route-Specific Middleware Resolution**:
   - Router mengekstrak alias middleware dan middleware group dari instance route terkait.
   - Urutan middleware disortir berdasarkan dependensi prioritas via `$middlewarePriority`.
5. **Route Pipeline Execution**:
   - Secondary pipeline diinisiasi khusus untuk middleware spesifik rute tersebut.
6. **Parameter Injection & Model Binding**:
   - `SubstituteBindings` middleware memindai signature controller method via PHP Reflection API (`ReflectionMethod`).
   - Parameter rute yang cocok dievaluasi via *Implicit Binding* (Query Database berdasar type-hint) atau *Explicit Binding* (Callback terdaftar di `Route::bind()`).
7. **Action Dispatch**: Route action (Controller Invocation atau Invokable Class) dieksekusi via `app()->call([$controller, $method])`.
8. **Response Normalization**: Return value di-cast ke instance `Illuminate\Http\Response` atau `Illuminate\Http\JsonResponse` via `Router::toResponse()`.
9. **Network Socket Flush**: Header dan body dikirim ke web server via fastcgi/socket buffers (`$response->send()`).
10. **Application Teardown (`terminate`)**: Loop berjalan memanggil method `terminate($request, $response)` dari semua middleware terminable yang terlibat dalam request stack tersebut.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Inspeksi Perakitan Logistik Bandara (Airport Security Pipeline)
Bayangkan HTTP Request sebagai seorang penumpang maskapai internasional:
- **Global Middleware**: Gate security utama bandara (Pengecekan Paspor & X-Ray Barang). Semua orang wajib melewatinya. Jika bawa barang terlarang, langsung diusir (Short-circuit response 403/401).
- **Route Matching Engine**: Papan navigasi terminal penerbangan. Sistem secara instan mencocokkan nomor tiket ke Gate yang spesifik.
- **Route Middleware**: Gate pemeriksaan khusus (Pemeriksaan visa transit atau fast-track VIP).
- **Controller Action**: Kursi pesawat penumpang. Destinasi akhir di mana kebutuhan utama terpenuhi.
- **Terminable Middleware**: Petugas darat yang mendata manifes penumpang ke arsip bandara *setelah* pesawat lepas landas. Penumpang tidak perlu menunggu proses pencatatan arsip tersebut selesai untuk bisa terbang.

#### Diagram Arsitektur Eksekusi Request & Pipeline

```
          [ INCOMING HTTP CLIENT REQUEST ]
                         │
                         ▼
        ┌──────────────────────────────────┐
        │       public/index.php           │
        └────────────────┬─────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │   HTTP Kernel & Bootstrap Init   │
        └────────────────┬─────────────────┘
                         │
    ═════════════════════╪═════════════════════════════════ (Global Pipeline Layer)
    [ GLOBAL MIDDLEWARE PIPELINE ]
    │   ├── TrustProxies
    │   ├── PreventRequestsDuringMaintenance
    │   └── ValidatePostSize
    ═════════════════════╪═════════════════════════════════
                         │
                         ▼
        ┌──────────────────────────────────┐
        │      Router Engine Matching      │
        │   (Compiled Regex Tree Lookup)   │
        └────────────────┬─────────────────┘
                         │
    ═════════════════════╪═════════════════════════════════ (Route-Specific Pipeline)
    [ ROUTE-SPECIFIC MIDDLEWARE PIPELINE ]
    │   ├── EncryptCookies / StartSession
    │   ├── SubstituteBindings (Model Binding Engine)
    │   ├── Custom Enterprise Auth / HMAC Validation
    │   └── Context-Aware Rate Limiting
    ═════════════════════╪═════════════════════════════════
                         │
                         ▼
        ┌──────────────────────────────────┐
        │    IoC Controller Invocation     │
        │   (Method Dependency Injection)  │
        └────────────────┬─────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │   Response Preparation (Cast)    │
        └────────────────┬─────────────────┘
                         │
                         ▼
        ┌──────────────────────────────────┐
        │ Response Sent ($response->send())│ ===> [ TCP FLUSH TO CLIENT ]
        └────────────────┬─────────────────┘
                         │
    ═════════════════════╪═════════════════════════════════ (Async Post-Response Lifecycle)
    [ TERMINABLE MIDDLEWARE ENGINE ]
    │   ├── Audit Trail Logging
    │   ├── Flush Telemetry to OpenTelemetry/Prometheus
    │   └── Memory Cleanup (Octane Specific Safe-Hooks)
    ═══════════════════════════════════════════════════════
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Middleware Pipeline Wrapping
Contoh sederhana manipulasi response header dan context timing tanpa mutating objek global secara destruktif:

```php
declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

final class ExecutionTimeTrackingMiddleware
{
    /**
     * Handle an incoming request.
     *
     * @param  \Closure(\Illuminate\Http\Request): (\Symfony\Component\HttpFoundation\Response)  $next
     */
    public function handle(Request $request, Closure $next): Response
    {
        $startTime = microtime(true);

        /** @var Response $response */
        $response = $next($request);

        $executionTimeMs = round((microtime(true) - $startTime) * 1000, 2);
        $response->headers->set('X-Execution-Time-Ms', (string) $executionTimeMs);

        return $response;
    }
}
```

#### 7.2 Practical Example: Enterprise API Gateway Routing & Explicit Cached Model Binding
Sistem enterprise membutuhkan validasi integritas payload via HMAC SHA-256 signature, route binding dengan dua lapis cache (APCu in-memory + Redis) untuk memitigasi read storm pada resource tenant, serta log terminasi terisolasi.

##### A. Explicit Route Binder dengan Multi-Tier Cache Layer
```php
declare(strict_types=1);

namespace App\Routing\Binders;

use App\Models\Tenant;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Support\Facades\Cache;

final class TenantRouteBinder
{
    /**
     * Resolve the route binding with Multi-Tier Cache.
     * Tier 1: In-Memory Runtime Request Cache
     * Tier 2: Redis Distributed Cache
     * Tier 3: PostgreSQL Primary DB with Failover
     */
    public function resolve(string $value): Tenant
    {
        $cacheKey = "tenant:route_binding:{$value}";

        /** @var Tenant|null $tenant */
        $tenant = Cache::store('redis')->remember($cacheKey, now()->addMinutes(10), function () use ($value) {
            return Tenant::query()
                ->where('uuid', $value)
                ->orWhere('domain_identifier', $value)
                ->where('is_active', true)
                ->first();
        });

        if ($tenant === null) {
            throw (new ModelNotFoundException())->setModel(Tenant::class, [$value]);
        }

        return $tenant;
    }
}
```

Registrasi binder di `app/Providers/AppServiceProvider.php`:
```php
declare(strict_types=1);

namespace App\Providers;

use App\Models\Tenant;
use App\Routing\Binders\TenantRouteBinder;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\ServiceProvider;

final class AppServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        Route::bind('tenant', function (string $value): Tenant {
            return $this->app->make(TenantRouteBinder::class)->resolve($value);
        });
    }
}
```

##### B. Enterprise HMAC Request Verification & Terminable Audit Middleware
```php
declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\HttpException;

final class EnterpriseHmacAuthenticationMiddleware
{
    private const SIGNATURE_HEADER = 'X-Enterprise-Signature';
    private const TIMESTAMP_HEADER = 'X-Enterprise-Timestamp';
    private const MAX_DRIFT_SECONDS = 300; // 5 menit time drift tolerance

    /**
     * Verify incoming signature before controller execution.
     */
    public function handle(Request $request, Closure $next): Response
    {
        $signature = $request->header(self::SIGNATURE_HEADER);
        $timestamp = $request->header(self::TIMESTAMP_HEADER);

        if (! $signature || ! $timestamp) {
            throw new HttpException(401, 'Autentikasi Header HMAC tidak lengkap.');
        }

        // Mitigasi Replay Attack via Timestamp Drift Checking
        if (abs(time() - (int) $timestamp) > self::MAX_DRIFT_SECONDS) {
            throw new HttpException(401, 'Request expired: Clock skew terdeteksi melebih toleransi.');
        }

        /** @var string $secret */
        $secret = config('services.enterprise_gateway.hmac_secret');
        $payloadToVerify = $request->getMethod() . '|' . $request->getRequestUri() . '|' . $timestamp . '|' . $request->getContent();
        $computedSignature = hash_hmac('sha256', $payloadToVerify, $secret);

        if (! hash_equals($computedSignature, $signature)) {
            throw new HttpException(403, 'Akses Ditolak: Signature cryptographically mismatch.');
        }

        // Teruskan ke pipeline berikutnya
        return $next($request);
    }

    /**
     * Terminable hook executed POST response network-flush.
     */
    public function terminate(Request $request, Response $response): void
    {
        // Komputasi audit logging di luar critical path request latency
        Log::channel('audit')->info('HTTP Transaction Processed', [
            'method' => $request->getMethod(),
            'uri' => $request->getRequestUri(),
            'status_code' => $response->getStatusCode(),
            'client_ip' => $request->ip(),
            'user_agent' => $request->userAgent(),
            'correlation_id' => $request->header('X-Correlation-ID'),
            'memory_peak_usage' => memory_get_peak_usage(true),
        ]);
    }
}
```

##### C. Controller Terintegrasi Explicit Binding & Route Configuration
File: `app/Http/Controllers/TenantGatewayController.php`
```php
declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Tenant;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

final class TenantGatewayController
{
    public function show(Tenant $tenant, Request $request): JsonResponse
    {
        return new JsonResponse([
            'status' => 'success',
            'data' => [
                'tenant_uuid' => $tenant->uuid,
                'name' => $tenant->name,
                'environment' => $tenant->environment,
                'bound_by_route_engine' => true,
            ],
            'meta' => [
                'requested_by' => $request->ip(),
            ]
        ], Response::HTTP_OK);
    }
}
```

File: `routes/api.php`
```php
declare(strict_types=1);

use App\Http\Controllers\TenantGatewayController;
use App\Http\Middleware\EnterpriseHmacAuthenticationMiddleware;
use Illuminate\Support\Facades\Route;

Route::prefix('v1/gateways/{tenant}')
    ->middleware([EnterpriseHmacAuthenticationMiddleware::class])
    ->group(function () {
        Route::get('/profile', [TenantGatewayController::class, 'show'])
            ->name('tenant.profile.show');
    });
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Arsitektur FinTech Multi-Tenant Core Banking Engine melayani 40.000 Request Per Second (RPS) pada event peak load bulanan (Payroll processing & flash sale). Sistem beroperasi di Kubernetes Cluster (EKS) dengan 120 Pods, berjalan di atas Laravel 11 dengan runtime **Laravel Octane (FrankenPHP)**.

#### Permasalahan Utama
1. **Database Connection Saturation**: Implicit route model binding standar menjalankan *N* query eksplisit ke database utama (`WHERE id = ?`) pada setiap request, membuat connection pool PostgreSQL kolaps (5000+ max connections exceeded).
2. **High Latency akibat Synchronous Logging**: Audit log perbankan yang diwajibkan oleh regulator (ISO 27001 & PCI-DSS) memperlambat response time sebesar 45ms per request karena synchronous I/O write ke storage/ELK.
3. **State Leakage pada Octane**: Penggunaan singleton middleware untuk menahan konteks tenant aktif menyebabkan kebocoran data (*cross-tenant data leakage*), di mana Tenant A menerima response terenkripsi milik Tenant B saat worker reuse terjadi.

#### Solusi Arsitektural
1. **Custom Optimized Route Binding Engine**: Mengubah implicit binding menjadi multi-tiered cached explicit binding yang melayani 98.4% parameter resolution langsung dari Redis cluster replica dan distributed shared memory (APCu) tanpa menyentuh primary database.
2. **Terminable Pipeline Offloading**: Menggeser write stream audit log ke dalam method `terminate()`. Network output dikirimkan ke client dalam kisaran $\approx 4\text{ms}$, kemudian background telemetry dikirimkan secara async melalui socket pipeline ke Fluentbit daemon set.
3. **Octane-Safe Context Lifecycle**: Membungkus tenant context ke dalam request-scoped container wrapper yang di-flush setiap kali middleware pipeline selesai atau melalui event `OperationTerminated`.

```
[ Request In: Tenant B ] ──> [ HMAC + Context Isolation Middleware ]
                                     │
                                     ├── Sets Request Attribute: $request->attributes->set('tenant', $resolved)
                                     │   (TIDAK MENGGUNAKAN GLOBAL STATIC VARIABLE)
                                     │
                                     ▼
                             [ Controller Action ]
                                     │
                                     ▼
                             [ Response Flushed (4ms) ]
                                     │
                                     ▼
                         [ Terminable Middleware Hook ]
                                     │
                                     ├── Emits Log to Local FIFO Socket Buffer
                                     └── Clears Local Contextual Resolvers
```

#### Hasil Metrik Produksi
- **P99 Response Latency**: Turun dari $180\text{ ms}$ menjadi $12\text{ ms}$.
- **Database CPU Utilization**: Berkurang dari $85\%$ menjadi $18\%$ pada peak 40k RPS.
- **Incident Rate**: Zero occurrences of cross-tenant data bleeding terdeteksi setelah implementasi scoped request attribute containerization.

---

### 9. Trade-offs

```
                  Routing Architectural Trade-offs
┌───────────────────────────────────────┬───────────────────────────────────────┐
│           ROUTE COMPILATION           │            DYNAMIC ROUTING            │
│         (route:cache enabled)         │         (Dynamic Closures)            │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ [+] Fast O(1) Amortized PCRE Match    │ [-] High O(N) Array Iteration Match   │
│ [+] Zero file I/O runtime load        │ [-] Continuous Route Reflection I/O   │
│ [-] Tidak mendukung Closure di routes │ [+] Mendukung Inline Route Closures   │
│ [-] Deploy pipeline wajib build step  │ [+] Kemudahan prototyping dev lokal   │
└───────────────────────────────────────┴───────────────────────────────────────┘
┌───────────────────────────────────────┬───────────────────────────────────────┐
│        SYNCHRONOUS MIDDLEWARE         │         TERMINABLE MIDDLEWARE         │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ [+] Menjamin write selesai sebelum    │ [+] Latency request sangat minimal;   │
│     client menerima return payload.   │     client tidak dibebani wait time.  │
│ [-] Menambah Network I/O latency      │ [-] Worker process tetap occupied     │
│     langsung ke P95/P99 latency user. │     di background hingga proses usai. │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

- **Performa vs Memory Overhead**: Explicit Model Binding yang meng-cache objek Eloquent penuh dapat menyebabkan konsumsi RAM tinggi pada Redis. Solusi trade-off: Serialisasikan model hanya dalam bentuk DTO (Data Transfer Object) atau array representasi ringkas, bukan rehydrated Active Record object penuh dengan relasi.
- **Octane Throughput vs Isolation Risk**: Menjalankan app di atas Octane melipatgandakan throughput hingga 4x lipat dibanding FPM tradisional, tetapi menuntut zero-tolerance terhadap perancangan stateful singleton di HTTP middleware.

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Memory Leak Melalui Static Middleware Property pada Octane
*Anti-Pattern*:
```php
final class TenantContextMiddleware
{
    public static ?Tenant $currentTenant = null; // FATAL DI OCTANE: State bocor ke request berikutnya!

    public function handle(Request $request, Closure $next): Response
    {
        self::$currentTenant = Tenant::find($request->header('X-Tenant-ID'));
        return $next($request);
    }
}
```
*Solusi*: Gunakan request attributes yang selalu terisolasi pada frame instance request:
```php
final class TenantContextMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $tenant = Tenant::find($request->header('X-Tenant-ID'));
        $request->attributes->set('current_tenant', $tenant); // SAFE: Terikat pada lifecycle instance request saat ini
        return $next($request);
    }
}
```

#### 10.2 Broken Route Cache Akibat Route Closure
*Anti-Pattern*: Menggunakan closure secara langsung di `routes/web.php` atau `routes/api.php` ketika production pipeline mengeksekusi `php artisan route:cache`.
```php
Route::get('/status', function () { // MENGAKIBATKAN Serialization of 'Closure' is not allowed Exception
    return response()->json(['status' => 'ok']);
});
```
*Solusi*: Pindahkan seluruh callback ke dalam dedicated Controller atau Invokable Action Class:
```php
Route::get('/status', App\Http\Controllers\HealthCheckAction::class);
```

#### 10.3 Mutasi Request yang Tidak Memperbarui Server Parameter
*Anti-Pattern*: Mengubah data request dengan `$request->merge()` lalu berharap data tersebut ter-update pada raw body `file_get_contents('php://input')` atau underlying Symfony request component.
*Solusi*: Jika membutuhkan mutasi menyeluruh yang aman ke downstream third-party library, gunakan `$request->duplicate()` atau manipulasi langsung pada attributes bag:
```php
$request->attributes->set('sanitized_payload', $sanitizedArray);
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic Route Caching**: Wajib menjalankan `php artisan route:cache` pada pipeline CI/CD deployment container image build.
- [ ] **Strict Route Parameter Regex Constraints**: Selalu definisikan explicit constraint pada parameter dinamis untuk menghindari salah jalur routing regex:
  ```php
  Route::get('/users/{id}', [UserController::class, 'show'])->whereNumber('id');
  Route::get('/orders/{uuid}', [OrderController::class, 'show'])->whereUuid('uuid');
  ```
- [ ] **Ordering Middleware Priority**: Definisikan urutan spesifik di `bootstrap/app.php` jika middleware autentikasi bergantung pada parameter decoding atau CORS middleware.
- [ ] **Non-Blocking Termination**: Pastikan method `terminate()` pada middleware tidak memanggil external API sinkron yang rentan timeout; gunakan local logging buffer atau async message dispatching (RabbitMQ/Amazon SQS).
- [ ] **Rate Limiting Segregation**: Bedakan limit tier route publik (unauthenticated) dan rute API privat via `RateLimiter::for()` menggunakan composite key:
  ```php
  RateLimiter::for('api', function (Request $request) {
      return Limit::perMinute(60)->by($request->user()?->id ?: $request->ip());
  });
  ```
- [ ] **Strict Typed Route Actions**: Wajibkan Controller method menggunakan typed parameters dan return types (`Response`, `JsonResponse`, dll) untuk mempermudah static analysis (PHPStan Level 8+).

---

### 12. Hands-on Practice

Struktur direktori praktikum yang akan kita bangun:
```
hands-on/m02/
├── app/
│   ├── Http/
│   │   ├── Controllers/
│   │   │   └── Api/
│   │   │       └── EnterpriseResourceController.php
│   │   └── Middleware/
│   │       ├── DynamicScopedRateLimiter.php
│   │       └── RequestSanitizationPipeline.php
│   └── Routing/
│       └── Binders/
│           └── SecureEncryptedIdBinder.php
├── bootstrap/
│   └── app.php
├── routes/
│   └── api.php
└── tests/
    └── Feature/
        └── AdvancedRoutingAndPipelineTest.php
```

#### Langkah 1: Implementasi Secure Encrypted ID Route Binder
Buat binder kustom yang mendekripsi parameter rute terenkripsi secara otomatis sebelum masuk controller.
File: `app/Routing/Binders/SecureEncryptedIdBinder.php`

```php
declare(strict_types=1);

namespace App\Routing\Binders;

use Illuminate\Contracts\Encryption\Encrypter;
use Illuminate\Contracts\Encryption\DecryptException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

final readonly class SecureEncryptedIdBinder
{
    public function __construct(
        private Encrypter $encrypter
    ) {}

    /**
     * Resolve the obfuscated/encrypted route parameter into a pure integer ID.
     */
    public function resolve(string $value): int
    {
        try {
            $decrypted = $this->encrypter->decrypt($value);
            
            if (! is_numeric($decrypted)) {
                throw new NotFoundHttpException('Resource identifier schema is invalid.');
            }

            return (int) $decrypted;
        } catch (DecryptException $e) {
            throw new NotFoundHttpException('Resource not found or decryption key mismatched.', $e);
        }
    }
}
```

#### Langkah 2: Implementasi Dynamic Scoped Rate Limiter Middleware
File: `app/Http/Middleware/DynamicScopedRateLimiter.php`

```php
declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Cache\RateLimiter;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\HttpException;

final readonly class DynamicScopedRateLimiter
{
    public function __construct(
        private RateLimiter $limiter
    ) {}

    public function handle(Request $request, Closure $next, string $scope = 'default', int $maxAttempts = 5): Response
    {
        $fingerprint = sha1($scope . '|' . ($request->user()?->getAuthIdentifier() ?? $request->ip()));

        if ($this->limiter->tooManyAttempts($fingerprint, $maxAttempts)) {
            $seconds = $this->limiter->availableIn($fingerprint);
            
            throw new HttpException(
                statusCode: Response::HTTP_TOO_MANY_REQUESTS,
                message: "Rate limit tier [{$scope}] exceeded. Try again in {$seconds} seconds.",
                headers: [
                    'Retry-After' => (string) $seconds,
                    'X-RateLimit-Limit' => (string) $maxAttempts,
                    'X-RateLimit-Remaining' => '0',
                ]
            );
        }

        $this->limiter->hit($fingerprint, decaySeconds: 60);

        /** @var Response $response */
        $response = $next($request);

        $response->headers->set('X-RateLimit-Limit', (string) $maxAttempts);
        $response->headers->set('X-RateLimit-Remaining', (string) $this->limiter->retriesLeft($fingerprint, $maxAttempts));

        return $response;
    }
}
```

#### Langkah 3: Controller Implementation
File: `app/Http/Controllers/Api/EnterpriseResourceController.php`

```php
declare(strict_types=1);

namespace App\Http\Controllers\Api;

use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

final class EnterpriseResourceController
{
    public function show(int $decryptedId): JsonResponse
    {
        return new JsonResponse([
            'status' => 'success',
            'data' => [
                'resolved_internal_id' => $decryptedId,
                'message' => 'Parameter berhasil didekripsi oleh custom route binder pipeline.',
            ]
        ], Response::HTTP_OK);
    }
}
```

#### Langkah 4: Routing Setup
File: `routes/api.php`

```php
declare(strict_types=1);

use App\Http\Controllers\Api\EnterpriseResourceController;
use App\Http\Middleware\DynamicScopedRateLimiter;
use Illuminate\Support\Facades\Route;

Route::get('/secure-resource/{encryptedId}', [EnterpriseResourceController::class, 'show'])
    ->middleware([
        DynamicScopedRateLimiter::class . ':critical_tier,3', // Max 3 requests/minute
    ])
    ->name('api.secure-resource.show');
```

File: `bootstrap/app.php` (Binding Configuration)

```php
declare(strict_types=1);

use App\Routing\Binders\SecureEncryptedIdBinder;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Support\Facades\Route;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
        then: function () {
            Route::bind('encryptedId', function (string $value): int {
                return app(SecureEncryptedIdBinder::class)->resolve($value);
            });
        }
    )
    ->withMiddleware(function (Middleware $middleware) {
        // Daftarkan global middleware atau konfigurasi alias jika diperlukan
    })
    ->withExceptions(function (Exceptions $exceptions) {
        // Konfigurasi Exception Handling
    })->create();
```

#### Langkah 5: Comprehensive Automated Testing Suite
File: `tests/Feature/AdvancedRoutingAndPipelineTest.php`

```php
declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Contracts\Encryption\Encrypter;
use Symfony\Component\HttpFoundation\Response;
use Tests\TestCase;

final class AdvancedRoutingAndPipelineTest extends TestCase
{
    private Encrypter $encrypter;

    protected function setUp(): void
    {
        parent::setUp();
        $this->encrypter = $this->app->make(Encrypter::class);
    }

    public function test_route_binder_successfully_resolves_and_decrypts_parameter(): void
    {
        $internalId = 48921;
        $encryptedPayload = $this->encrypter->encrypt((string) $internalId);

        $response = $this->getJson("/api/secure-resource/{$encryptedPayload}");

        $response->assertStatus(Response::HTTP_OK)
            ->assertHeader('X-RateLimit-Limit', '3')
            ->assertHeader('X-RateLimit-Remaining', '2')
            ->assertJson([
                'status' => 'success',
                'data' => [
                    'resolved_internal_id' => $internalId,
                ]
            ]);
    }

    public function test_route_binder_aborts_with_404_on_invalid_tampered_token(): void
    {
        $tamperedPayload = 'invalid-payload-token';

        $response = $this->getJson("/api/secure-resource/{$tamperedPayload}");

        $response->assertStatus(Response::HTTP_NOT_FOUND);
    }

    public function test_dynamic_middleware_rate_limiter_blocks_excessive_traffic(): void
    {
        $encryptedPayload = $this->encrypter->encrypt('1001');

        // Consume 3 allowed tokens
        $this->getJson("/api/secure-resource/{$encryptedPayload}")->assertStatus(Response::HTTP_OK);
        $this->getJson("/api/secure-resource/{$encryptedPayload}")->assertStatus(Response::HTTP_OK);
        $this->getJson("/api/secure-resource/{$encryptedPayload}")->assertStatus(Response::HTTP_OK);

        // 4th request must fail with 429
        $response = $this->getJson("/api/secure-resource/{$encryptedPayload}");

        $response->assertStatus(Response::HTTP_TOO_MANY_REQUESTS)
            ->assertHeader('Retry-After');
    }
}
```

---

### 13. Exercise

#### Level Easy
Buat middleware bernama `CorrelationIdMiddleware` yang memeriksa apakah request menyertakan header `X-Correlation-ID`. Jika tidak ada, generate UUID v4 baru dan masukkan ke dalam header request serta set ke header response yang keluar.
- **Kriteria Evaluasi**: Validitas UUID, header persisten di request dan response, tidak menimpa header yang sudah dikirim oleh upstream proxy.

#### Level Medium
Implementasikan *Dynamic Route Macro* via `Route::macro('auditedResource', ...)` yang secara otomatis meregistrasikan resource controller standar (index, store, show, update, destroy) tetapi menyisipkan middleware audit trail yang berbeda khusus untuk mutasi data (`POST`, `PUT`, `PATCH`, `DELETE`) tanpa memasangnya pada operasi baca (`GET`).
- **Kriteria Evaluasi**: Keberhasilan eksekusi `php artisan route:cache`, separasi isolasi middleware mutasi vs read.

#### Level Hard
Rancang dan implementasikan kustom *Pipeline Dispatcher* yang mendukung eksekusi parallel middleware bercabang menggunakan PHP 8.2 Fiber atau Concurrent Concurrency Engine (misal pada event checking multi IP intelligence & user sanctions check) sebelum akhirnya controller dieksekusi. Jika salah satu cabang gagal, short-circuit request secara instan.
- **Kriteria Evaluasi**: Thread/Fiber safety, zero state pollution, error propagation yang akurat, handling latency timeout.

---

### 14. Challenge

**Studi Kasus**: Anda memimpin migrasi API Gateway platform e-commerce enterprise dengan $150.000$ route aktif dari monolitik lama ke Laravel 11 running on Laravel Octane.

**Kondisi Problematic**:
1. Route dynamic pattern matching memakan latency CPU hingga $35\text{ ms}$ per request hanya untuk mencocokkan URL pattern karena ribuan dynamic regular expression wildcard (`{slug}`, `{category}`, `{merchant}`).
2. Beberapa partner integrasi mengirimkan payload HTTP request yang sama berulang-ulang dalam rentang 1 detik (Idempotency issues).
3. Tim keamanan mewajibkan audit log mencatat byte size aktual yang benar-benar terkirim lewat socket jaringan beserta memory peak aplikasi.

**Tugas Arsitektur**:
Rancang end-to-end routing dan middleware architecture yang menyelesaikan ketiga masalah di atas:
- Terapkan Trie-based static segment prioritization untuk mereduksi matching time menjadi sub-$1\text{ ms}$.
- Rancang Idempotency Middleware yang thread-safe menggunakan distributed atomic lock (Redis) tanpa menimbulkan bottleneck thread lockup.
- Sediakan terminable middleware yang mengukur delta exact memory usage dan transfer byte length secara akurat tanpa mengganggu throughput Octane worker.
- **Batasan**: Tidak boleh menggunakan library third-party di luar ekosistem resmi Laravel/Symfony; wajib lolos standar memory-leak testing di bawah load 10.000 concurrent connection.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)

**Q1: Apa fungsi utama dari method `terminate()` pada kelas Middleware Laravel?**
- A) Menghentikan eksekusi script PHP secara instan menggunakan `exit()`.
- B) Mengeksekusi kode secara asinkron setelah response HTTP dikirimkan (flushed) ke web server/klien.
- C) Menghapus session dan cookie pengguna dari browser.
- D) Mengembalikan koneksi database ke pool sebelum controller selesai dijalankan.
> **Jawaban: B**  
> *Penjelasan*: Method `terminate()` dipanggil setelah HTTP response dikirimkan ke client via `send()`, memungkinkan komputasi non-kritis dijalankan tanpa menambah latency waktu tunggu client.

**Q2: Perintah artisan apa yang digunakan untuk mengompilasi seluruh rute menjadi single compiled cached file demi performa tinggi di production?**
- A) `php artisan route:compile`
- B) `php artisan optimize:routes`
- C) `php artisan route:cache`
- D) `php artisan make:route-cache`
> **Jawaban: C**  
> *Penjelasan*: `route:cache` memvalidasi dan mengompilasi seluruh definisi rute ke dalam file statis `bootstrap/cache/routes-v7.php`.

**Q3: Kapan route closure (anonymous function) menjadi masalah di Laravel?**
- A) Saat aplikasi dijalankan menggunakan PHP 8.2.
- B) Saat menjalankan `php artisan route:cache`, karena closure PHP bawaan tidak dapat diserialisasi secara aman menjadi teks/file cache.
- C) Ketika rute tersebut menerima HTTP POST request.
- D) Saat middleware pipeline memiliki lebih dari 3 layer.
> **Jawaban: B**  
> *Penjelasan*: Closure engine PHP tidak mendukung native serialization. Mencoba melakukan caching pada rute berbasis closure akan menghasilkan exception `LogicException: Unable to prepare route [...] for serialization`.

**Q4: Dalam alur eksekusi internal Laravel, komponen manakah yang bertanggung jawab merangkai middleware menggunakan nested closure?**
- A) `Illuminate\Routing\RouteCollection`
- B) `Illuminate\Pipeline\Pipeline`
- C) `Illuminate\Container\Container`
- D) `Symfony\Component\HttpFoundation\Request`
> **Jawaban: B**  
> *Penjelasan*: Kelas `Illuminate\Pipeline\Pipeline` membungkus lapisan middleware dengan memanfaatkan fungsi `array_reduce` menjadi struktur nested closure yang dapat dieksekusi secara berurutan.

**Q5: Apa perbedaan fundamental antara Implicit Binding dan Explicit Binding?**
- A) Implicit binding hanya untuk database MySQL, explicit binding untuk PostgreSQL.
- B) Implicit binding bekerja otomatis berdasarkan type-hinting model dan nama parameter; Explicit binding dikonfigurasi secara manual via `Route::bind()` dengan resolusi custom.
- C) Implicit binding dieksekusi di controller, explicit binding dieksekusi di web server (Nginx).
- D) Implicit binding mengabaikan middleware, explicit binding mematuhi middleware.
> **Jawaban: B**  
> *Penjelasan*: Implicit binding memanfaatkan type-hint Eloquent Model dan mencocokkan segment name secara otomatis, sedangkan Explicit binding mengharuskan developer mendaftarkan callback khusus untuk mengontrol bagaimana string identifier diterjemahkan menjadi objek/data.

---

#### Intermediate (5 Soal)

**Q6: Mengapa penggunaan `static property` pada kelas Middleware berbahaya saat aplikasi dijalankan di atas Laravel Octane?**
- A) Menyebabkan compile error saat Octane melakukan warming cache.
- B) Static property tidak didukung oleh PHP 8.2 typed properties.
- C) Nilai static property akan bertahan di memori worker process lintas request, memicu kebocoran data antar user yang berbeda.
- D) Mengurangi performa CPU karena garbage collector dipaksa berjalan terus menerus.
> **Jawaban: C**  
> *Penjelasan*: Worker Laravel Octane tidak melakukan terminate process PHP secara instan (long-lived process). Nilai pada static property akan tetap tersimpan di RAM dan dapat diakses/dimutasi oleh request pengguna lain yang diproses oleh worker yang sama berikutnya.

**Q7: Manakah ekspresi internal yang paling merepresentasikan bagaimana Laravel mengompilasi rute untuk pencocokan cepat oleh regex engine?**
- A) Array loop bertingkat `foreach($routes as $route) { if(preg_match(...)) }`
- B) Single Combined Regex memanfaatkan PCRE branch reset group `(?|...)` dengan control verb `(*MARK:id)`
- C) SQL Query yang dijalankan ke sqlite database in-memory
- D) Binary search tree pada hash file JSON
> **Jawaban: B**  
> *Penjelasan*: Route compilation Laravel berbasis Symfony Route Compiler menggabungkan ribuan rute ke dalam single regular expression tree menggunakan syntax PCRE branch reset dan control verb `MARK` untuk memastikan pencocokan deterministik dengan kecepatan optimal.

**Q8: Jika sebuah middleware melempar exception sebelum memanggil `$next($request)`, apa yang terjadi pada siklus request?**
- A) Request dialihkan ke route fallback secara otomatis.
- B) Pipeline langsung terputus (short-circuit), controller tidak dieksekusi, dan kontrol diserahkan ke `ExceptionHandler`.
- C) Laravel mencoba menjalankan middleware berikutnya tanpa request payload.
- D) Aplikasi mengalami core dump / fatal crash.
> **Jawaban: B**  
> *Penjelasan*: Pipeline pattern mengandalkan pemanggilan eksplisit `$next($request)`. Jika exception dilempar, eksekusi pipeline terputus secara langsung dan alur ditangkap oleh centralized `Illuminate\Foundation\Exceptions\Handler`.

**Q9: Pada implementasi Explicit Binding berikut, potensi celah apa yang paling kritikal?**
```php
Route::bind('account', function ($value) {
    return Account::where('id', $value)->firstOrFail();
});
```
- A) Tidak menggunakan asynchronous processing.
- B) Melakukan unindexed raw query secara procedural.
- C) Rentan mengekspos data multi-tenant jika tidak membatasi scope resolusi pada tenant yang saat ini sedang terotentikasi.
- D) Method `firstOrFail()` dilarang digunakan di dalam ServiceProvider.
> **Jawaban: C**  
> *Penjelasan*: Explicit binding tanpa scoping autorisasi (misal: memeriksa apakah akun tersebut milik user/tenant yang sedang login) membuka celah kerentanan Insecure Direct Object References (IDOR).

**Q10: Bagaimana cara terbaik memutasi payload HTTP Request di middleware sebelum diteruskan ke Controller jika kita ingin mencegah side-effects pada library downstream?**
- A) Memodifikasi variable superglobal `$_POST` secara manual.
- B) Menggunakan method `$request->merge()` atau menyimpan data yang telah disanitasi ke dalam `$request->attributes` bag.
- C) Meng-overwrite protected property `$request->request` menggunakan Reflection API.
- D) Melakukan redirect 307 ke URL yang sama dengan query parameter baru.
> **Jawaban: B**  
> *Penjelasan*: Menggunakan `$request->attributes` (atau `$request->merge()`) merupakan standar resmi HttpFoundation untuk menyisipkan data terisolasi tanpa memanipulasi low-level PHP globals atau merusak integritas input stream mentah.

---

#### Skenario Kasus Produksi (3 Soal)

**Q11: Sebuah aplikasi web FinTech mengalami lonjakan latency (P99 naik dari 20ms ke 850ms) setelah penambahan middleware compliance audit log. Middleware tersebut mengirimkan log request/response ke third-party HTTP Log Server via Guzzle client di dalam method `handle()`. Bagaimana solusi rekayasa terbaik untuk memulihkan performa tanpa kehilangan fungsionalitas logging?**
- A) Tingkatkan memory limit PHP dari 512MB menjadi 2GB di server php.ini.
- B) Ubah konfigurasi Nginx buffer size menjadi 128k.
- C) Pindahkan pengiriman log dari method `handle()` ke method `terminate()`, dan delegasikan transport log ke background message queue (SQS/Redis) atau local socket daemon buffer (Fluentbit/Logstash).
- D) Nonaktifkan route caching agar logging dievaluasi secara dinamis.
> **Jawaban: C**  
> *Penjelasan*: Pemanggilan external HTTP client di method `handle()` memblokir eksekusi sebelum response dapat dikirim ke client (synchronous blocking I/O). Memindahkannya ke `terminate()` dan mengalihkan transport ke queue/socket lokal membebaskan user latency secara instan.

**Q12: Tim QA melaporkan bahwa pada stress testing Laravel Octane (FrankenPHP) dengan 500 concurrent connections, terjadi data cross-leakage: Tenant A terkadang menerima laporan keuangan milik Tenant B. Investigasi menemukan kode berikut di middleware:**
```php
final class AppContext
{
    private static ?Tenant $tenant = null;
    public static function set(Tenant $t): void { self::$tenant = $t; }
    public static function get(): ?Tenant { return self::$tenant; }
}

final class TenantResolverMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $tenant = Tenant::findOrFail($request->header('X-Tenant-ID'));
        AppContext::set($tenant);
        return $next($request);
    }
}
```
**Mengapa insiden ini terjadi dan apa mitigasi arsitektur yang permanen?**
- A) `Tenant::findOrFail` tidak thread-safe; harus diganti dengan `Tenant::find()`.
- B) Octane menggunakan persistent workers di mana kelas `AppContext` dimuat satu kali di memori heap master process. Penggunaan static property membagikan state antar request yang dieksekusi secara bergantian atau bersamaan pada worker yang sama. Mitigasinya: Bind context ke Service Container menggunakan scoped instance atau simpan langsung di Request Attributes.
- C) Header `X-Tenant-ID` ter-cache oleh browser; mitigasinya adalah mengirimkan header `Cache-Control: no-cache`.
- D) Masalah terjadi karena FrankenPHP tidak mendukung PDO transaction; mitigasinya beralih kembali ke Apache MPM Prefork.
> **Jawaban: B**  
> *Penjelasan*: Persistent worker lifecycle pada runtime Octane tidak menghancurkan static properties antar HTTP request. Data Tenant yang tersimpan di static variable `AppContext::$tenant` akan terbawa ke request berikutnya jika request berikutnya gagal/lupa melakukan overwrite, atau saat concurrent coroutines berjalan paralel. Mengikatnya pada container scope atau request attributes mengisolasi data murni pada satu siklus request saja.

**Q13: Sebuah platform e-commerce memiliki 12.000 route. Saat menjalankan deployment di pipeline CI/CD, proses `php artisan route:cache` memakan waktu sangat lama dan menghabiskan memori pipeline (Out Of Memory Exception). Setelah diselidiki, terdapat puluhan route grup yang didefinisikan menggunakan closure kompleks yang memuat relasi model Eloquent secara inline. Apa rekomendasi arsitektur untuk mengatasi masalah ini?**
- A) Jalankan pipeline dengan parameter `memory_limit=-1` dan biarkan route closure tetap ada.
- B) Hapus file `routes/api.php` dan gabungkan semuanya ke `routes/web.php`.
- C) Refactor seluruh route closure menjadi dedicated Controller classes / Single-Action Invokable Classes, singkirkan query database saat proses registrasi route, dan pastikan route definition hanya berisi deklarasi metadata HTTP murni.
- D) Matikan sistem routing Laravel dan ganti dengan Nginx raw fastcgi_pass regex redirection.
> **Jawaban: C**  
> *Penjelasan*: Menjalankan query database atau mendefinisikan inline closure di dalam file routing adalah anti-pattern berat. Saat `route:cache` dijalankan, Laravel mem-parsing file rute. Jika file tersebut mengeksekusi operasi logic atau mengandung closure, proses serialisasi akan gagal atau memakan memori masif. Mengonversinya ke clean controller references memulihkan kecepatan dan kompatibilitas serialisasi route cache secara instan.

---

### 16. Summary

1. **HTTP Core Foundation**: Request di Laravel diabstraksikan melalui lapisan Symfony HTTPFoundation yang diproses oleh Kernel melalui nested Chain of Responsibility pipeline pattern via `Illuminate\Pipeline\Pipeline`.
2. **Kompilasi Routing Tingkat Lanjut**: Route caching (`php artisan route:cache`) mentransformasikan pencocokan linear menjadi *Compiled Regex Tree* dengan algoritma PCRE branch reset markers yang berkecepatan $O(1)$ amortized terhadap total volume route.
3. **Explicit Parameter Binding**: Memisahkan logika resolusi domain model dari Controller ke layer terdedikasi (`Route::bind()`), memfasilitasi multi-level caching (Redis/APCu), serta mengisolasi validasi IDOR.
4. **Terminable Architecture**: Method `terminate()` memisahkan proses pengiriman network data ke client dari komputasi background non-kritis (audit logging, metrics, queue offloading), mereduksi response time secara signifikan.
5. **Octane & Concurrency Safety**: Long-lived process runtimes mengharuskan developer menghindari stateful singleton dan static properties di dalam HTTP layer guna mencegah memory leak bencana dan insiden cross-request data pollution.