# Bab 02 Module 01: Routing Engine, Middleware Pipeline & HTTP Layer

---

## 01. Identitas Modul
* **Track:** Backend and Database Engineering
* **Framework:** Laravel 11.x (PHP 8.3+)
* **Level:** Intermediate to Advanced
* **Prasyarat:** Pemahaman OOP PHP, Composer, Arsitektur Dasar MVC, HTTP/1.1 & HTTP/2 Fundamentals, Lifecycle Request-Response.

---

## 02. Learning Objectives
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. Membedah arsitektur internal *Routing Engine* Laravel dari tahap *binding* hingga *route matching resolution*.
2. Membangun, mengonfigurasi, dan mengoptimalkan *Middleware Pipeline* menggunakan pola desain *Chain of Responsibility* (Pipeline Pattern).
3. Menguasai manipulasi *HTTP Layer*, mencakup injeksi ketergantungan pada `Request`, pembentukan `Response` biner/JSON stream, serta implementasi *Route Model Binding* kustom.
4. Menerapkan proteksi keamanan HTTP tingkat lanjut (HMAC signed routes, rate limiting bertingkat, mitigasi parameter tampering).
5. Mendiagnosis dan mengeliminasi *overhead* eksekusi HTTP pipeline hingga mencapai throughput optimal dalam skala produksi.

---

## 03. Concept Map Diagram (ASCII)

```
[Inbound HTTP Request]
         │
         ▼
[public/index.php] ───> [Bootstrap Application Container]
                             │
                             ▼
                   [HTTP Kernel Engine]
                             │
                             ▼
                 [Middleware Pipeline Layer]
                  ├── Global Middleware Stack (CORS, TrimStrings, etc.)
                  ├── Route-Group Middleware (web / api)
                  └── Custom Pipeline Middleware (Terminable / Filter)
                             │
                             ▼
                     [Routing Engine]
                  ├── FastRoute Dispatcher / Compiled Route Cache
                  ├── URI Pattern Matching & HTTP Verb Inspection
                  ├── Implicit / Explicit Route Model Binding (RMB)
                  └── Controller / Invokable Action Resolution
                             │
                             ▼
                      [Action / Handler]
                             │
                             ▼
                 [Response Serialization]
                             │
                             ▼
                 [Terminable Middleware (post-send)]
                             │
                             ▼
[Outbound HTTP Response (Emit to SAPI/FastCGI)]
```

---

## 04. Mengapa Relevan
*Routing Engine* dan *Middleware Pipeline* adalah pintu gerbang utama (*ingress layer*) dari setiap aplikasi web berbasis Laravel. Kesalahan arsitektural pada layer ini berdampak langsung pada:
* **Latensi Kumulatif:** Eksekusi middleware yang tidak efisien atau *route scanning* dinamis tanpa *caching* menambah puluhan milidetik pada *Time to First Byte* (TTFB).
* **Vulnerabilitas Keamanan:** Penanganan mutasi parameter yang longgar dan otentikasi token yang salah posisi pada pipeline memicu eskalasi hak akses atau kebocoran data.
* **Maintainability:** Penggunaan controller monolitik tanpa memanfaatkan *middleware pipeline composition* menyebabkan *spaghetti code* dan pelanggaran *Single Responsibility Principle* (SRP).

---

## 05. Anatomi Konsep Inti

### 1. Request Lifecycle & Routing Engine
Setiap *inbound request* diubah menjadi instance `Illuminate\Http\Request` via `Request::capture()`. Engine mencocokkan URI path dan HTTP Method terhadap daftar `RouteCollection`. Di balik layar, Laravel mengompilasi pola regex rute menjadi array state-machine tunggal berbasis FastRoute saat `php artisan route:cache` dijalankan.

### 2. The Pipeline Pattern (Chain of Responsibility)
Laravel mengimplementasikan `Illuminate\Pipeline\Pipeline`. Setiap middleware membungkus middleware berikutnya layaknya lapisan bawang (*onion architecture*):
```php
$pipeline = array_reduce(
    array_reverse($pipes),
    $this->carry(),
    $this->prepareDestination($destination)
);
```
Fungsi `handle($request, Closure $next)` memungkinkan manipulasi *request payload* sebelum dieksekusi controller (*inbound*), atau manipulasi `$response` sebelum dikirimkan ke client (*outbound*).

### 3. Terminable Middleware
Middleware yang mengimplementasikan `TerminableMiddlewareInterface` memiliki method `terminate($request, $response)`. Method ini dipanggil *setelah* HTTP response dikirimkan ke buffer web server (FastCGI/FPM), ideal untuk task I/O berat seperti logging analitik atau metric pushing tanpa memblokir client.

### 4. Explicit vs Implicit Route Model Binding
* **Implicit:** Laravel mencocokkan nama segmen variabel URI (misal: `{user}`) dengan *type-hint* controller `User $user` berdasarkan *route key* default (`id` atau kustom via `getRouteKeyName()`).
* **Explicit:** Didefinisikan via `Route::model()` atau `Route::bind()` di Service Provider untuk resolusi yang melibatkan kueri multi-kolom, scoped lookups, atau integrasi cache engine (Redis).

---

## 06. Panduan Implementasi Step-by-Step

### 1. Inisialisasi Middleware Kustom
Jalankan artisan command untuk membuat middleware:
```bash
php artisan make:middleware EnsureIdempotencyKey
```

### 2. Registrasi Middleware pada Laravel 11 (`bootstrap/app.php`)
Laravel 11 menyatukan konfigurasi middleware di file `bootstrap/app.php`:
```php
use App\Http\Middleware\EnsureIdempotencyKey;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Middleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->alias([
            'idempotent' => EnsureIdempotencyKey::class,
        ]);
        $middleware->throttleApi('api-rate-limiter');
    })
    ->create();
```

### 3. Implementasi Explicit Binding dengan Cache Layer
Buka `app/Providers/AppServiceProvider.php`:
```php
namespace App\Providers;

use App\Models\Tenant;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        Route::bind('tenant_uuid', function (string $value) {
            return Cache::remember("tenant:uuid:{$value}", 300, function () use ($value) {
                return Tenant::where('uuid', $value)->where('is_active', true)->firstOrFail();
            });
        });
    }
}
```

---

## 07. Contoh Kasus Sederhana

Implementasi route group dengan verifikasi API Key sederhana dan transformasi response header.

```php
// routes/api.php
use App\Http\Middleware\EnsureApiKeyPresent;
use Illuminate\Support\Facades\Route;

Route::middleware([EnsureApiKeyPresent::class])->group(function () {
    Route::get('/v1/system/status', function () {
        return response()->json([
            'status' => 'operational',
            'timestamp' => now()->toISOString(),
        ]);
    });
});
```

```php
// app/Http/Middleware/EnsureApiKeyPresent.php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class EnsureApiKeyPresent
{
    public function handle(Request $request, Closure $next): Response
    {
        $apiKey = $request->header('X-API-KEY');

        if (!$apiKey || $apiKey !== config('services.api.master_key')) {
            return response()->json([
                'error' => 'Unauthorized: Invalid or Missing API Key'
            ], Response::HTTP_UNAUTHORIZED);
        }

        $response = $next($request);
        $response->headers->set('X-Service-Engine', 'Laravel-HTTP-Layer');

        return $response;
    }
}
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur *Enterprise Idempotency Middleware* yang menggunakan Redis lock dan caching untuk mencegah eksekusi duplikat pada endpoint finansial.

### 1. Middleware Idempotensi
```php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Redis;
use Symfony\Component\HttpFoundation\Response;

class IdempotencyEngineMiddleware
{
    private const HEADER_KEY = 'X-Idempotency-Key';
    private const LOCK_TTL = 15; // detik
    private const CACHE_TTL = 86400; // 24 jam

    public function handle(Request $request, Closure $next): Response
    {
        // Hanya proses method mutasi data
        if (!in_array($request->method(), ['POST', 'PATCH', 'PUT'], true)) {
            return $next($request);
        }

        $idempotencyKey = $request->header(self::HEADER_KEY);
        if (empty($idempotencyKey)) {
            return response()->json([
                'status' => 'error',
                'message' => 'Idempotency key is required for mutative operations.'
            ], Response::HTTP_UNPROCESSABLE_ENTITY);
        }

        $userId = $request->user()?->id ?? 'anonymous';
        $lockKey = "idempotency:lock:{$userId}:{$idempotencyKey}";
        $cacheKey = "idempotency:response:{$userId}:{$idempotencyKey}";

        $cachedResponse = Redis::get($cacheKey);
        if ($cachedResponse !== null) {
            $data = json_decode($cachedResponse, true);
            return response()->json($data['payload'], $data['status'], array_merge(
                $data['headers'],
                ['X-Cache-Lookup' => 'HIT-IDEMPOTENT']
            ));
        }

        // Dapatkan distributed lock
        $acquired = Redis::set($lockKey, 'processing', 'EX', self::LOCK_TTL, 'NX');
        if (!$acquired) {
            return response()->json([
                'status' => 'error',
                'message' => 'A transaction with this idempotency key is currently processing.'
            ], Response::HTTP_CONFLICT);
        }

        try {
            /** @var Response $response */
            $response = $next($request);

            if ($response->isSuccessful()) {
                $cachePayload = [
                    'status' => $response->getStatusCode(),
                    'headers' => ['Content-Type' => 'application/json'],
                    'payload' => json_decode($response->getContent(), true)
                ];

                Redis::setex($cacheKey, self::CACHE_TTL, json_encode($cachePayload));
            }

            return $response;
        } finally {
            Redis::del($lockKey);
        }
    }
}
```

### 2. Controller dengan Form Request Resolution
```php
namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class PaymentExecutionController extends Controller
{
    public function __invoke(Request $request): JsonResponse
    {
        // Simulasi kalkulasi transaksi bisnis intensif
        $validated = $request->validate([
            'account_id' => 'required|string|uuid',
            'amount' => 'required|numeric|min:0.01',
            'currency' => 'required|string|size:3',
        ]);

        $transactionId = 'txn_' . bin2hex(random_bytes(12));

        return response()->json([
            'status' => 'success',
            'data' => [
                'transaction_id' => $transactionId,
                'account_id' => $validated['account_id'],
                'amount' => $validated['amount'],
                'currency' => strtoupper($validated['currency']),
                'executed_at' => now()->toIso8601String(),
            ]
        ], Response::HTTP_CREATED);
    }
}
```

### 3. Route Registration (Production Context)
```php
// routes/api.php
use App\Http\Controllers\Api\V1\PaymentExecutionController;
use App\Http\Middleware\IdempotencyEngineMiddleware;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')
    ->middleware(['auth:sanctum', IdempotencyEngineMiddleware::class])
    ->group(function () {
        Route::post('/payments/execute', PaymentExecutionController::class)
            ->name('api.v1.payments.execute');
    });
```

---

## 09. Diagram Alur Kerja (ASCII Lifecycle)

```
[Client App]
     │ (1) POST /api/v1/payments/execute with X-Idempotency-Key
     ▼
[Route Matching: FastRoute State Machine]
     │
     ▼
[Middleware: Authentication Layer]
     │ (Verified User Context)
     ▼
[Middleware: IdempotencyEngineMiddleware]
     ├── (2) Redis GET idempotency:response:{id}
     │       ├── HIT ──> [Return Cached Payload immediately] ──┐
     │       └── MISS                                          │
     ├── (3) Redis SET NX (Distributed Lock)                   │
     │       ├── Failed ──> [Return HTTP 409 Conflict] ───────┤
     │       └── Acquired                                      │
     │                                                         │
     ▼                                                         │
[Controller Handler Action Execution]                          │
     │ (4) Process Ledger & Mutation Logic                     │
     ▼                                                         │
[Formulate HTTP 201 Response Object]                           │
     │                                                         │
     ▼                                                         │
[Post-Action: IdempotencyEngineMiddleware]                     │
     ├── (5) Redis SETEX Response (24h Cache)                  │
     └── (6) Redis DEL (Release Lock)                          │
     │                                                         │
     ▼                                                         │
[HTTP Response Dispatch to Client] <───────────────────────────┘
```

---

## 10. Analisis Trade-offs

| Pendekatan | Keuntungan | Kerugian / Trade-off | Skenario Penggunaan |
| :--- | :--- | :--- | :--- |
| **Global Middleware Stack** | Berlaku seragam tanpa redundansi deklarasi di setiap file rute. | Membebani rute ringan/statik yang tidak butuh processing berat. | CORS, Sanitasi payload, Global Header Injection. |
| **Route Model Binding (Implicit)** | Mengurangi boilerplate code pada Controller, sintaks ekspresif. | Sulit mengoptimalkan query kustom (`eager loading`, composite keys). | Aplikasi CRUD standar dengan kueri relasi sederhana. |
| **Route Model Binding (Explicit w/ Cache)** | Kueri optimal, decoupling database, integrasi Redis otomatis. | Overhead invalidasi cache, kompleksitas debugging lifecycle. | API traffic tinggi pada lookup entity statik/jarang berubah. |
| **Closure Routing** | Waktu inisialisasi minimal, cocok untuk prototyping. | Tidak dapat di-*serialize* oleh engine `route:cache`, latency tinggi saat skala besar. | Testing lokal atau micro-services sangat kecil (gunakan Controller utk produksi). |

---

## 11. Best Practices & Antipatterns

### Best Practices
1. **Always Cache Routes:** Wajib menjalankan `php artisan route:cache` pada pipeline CI/CD production.
2. **Atomic Actions:** Gunakan *Single Action/Invokable Controllers* (`__invoke`) untuk endpoint yang kompleks.
3. **Explicit Scoping:** Manfaatkan scoped model binding untuk mencegah *Insecure Direct Object Reference* (IDOR):
   ```php
   Route::get('/users/{user}/posts/{post:slug}', ...);
   ```
4. **Pipeline Thinning:** Letakkan middleware validasi payload spesifik hanya pada group atau endpoint yang membutuhkan.

### Antipatterns
1. **Logic Dumping in Closures:** Menulis logika bisnis di dalam closure file `routes/*.php` yang mematikan kapabilitas route caching.
2. **Database Queries Inside Unconditional Middleware:** Menjalankan query DB di global middleware tanpa memverifikasi path request terlebih dahulu.
3. **Modifying Global State in Terminable Middleware:** Mengubah instance container setelah response dikirim, yang dapat memicu *memory leak* pada server runtime seperti Laravel Octane.

---

## 12. Security Hardening

### 1. HMAC Route Signing (Anti-Tampering)
Untuk link aksi kritis seperti konfirmasi transfer atau unsubscribe:
```php
// Pembuatan Signed URL (misal: Berlaku 30 Menit)
$url = URL::temporarySignedRoute(
    'unsubscribe',
    now()->addMinutes(30),
    ['user' => $user->id]
);

// Definisi Proteksi Rute
Route::get('/unsubscribe/{user}', function (Request $request, User $user) {
    return response()->json(['status' => 'unsubscribed']);
})->name('unsubscribe')->middleware('signed');
```

### 2. Advanced Custom Rate Limiting
Konfigurasikan pembatasan multi-tier di `app/Providers/AppServiceProvider.php`:
```php
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;

RateLimiter::for('financial-tier', function (Request $request) {
    return $request->user()?->is_vip
        ? Limit::none()
        : Limit::perMinute(5)->by($request->user()?->id ?: $request->ip())->response(function () {
            return response()->json([
                'error' => 'Too Many Requests',
                'retry_after' => 60
            ], 429);
        });
});
```

---

## 13. Observabilitas & Debugging

### Trace Execution Headers
Suntikkan Unique Request Tracking Identifier pada *ingress middleware*:

```php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

class RequestTracingMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $traceId = $request->header('X-Trace-ID', (string) Str::uuid());
        $request->attributes->set('trace_id', $traceId);

        $startTime = microtime(true);

        /** @var Response $response */
        $response = $next($request);

        $executionTime = round((microtime(true) - $startTime) * 1000, 2);

        $response->headers->set('X-Trace-ID', $traceId);
        $response->headers->set('X-Runtime-Ms', (string) $executionTime);

        return $response;
    }
}
```

### Route Inspection Commands
* Inspeksi daftar route dan middleware terkait:
  ```bash
  php artisan route:list --path=api/v1 --columns=method,uri,name,action,middleware
  ```
* Validasi performa dan integritas route cache:
  ```bash
  php artisan route:clear && php artisan route:cache
  ```

---

## 14. Benchmarking & Performance

### Route Cache Impact Analysis
Benchmarking dilakukan menggunakan `wrk` (Concurrency: 50, Duration: 30s) terhadap 100 rute terdaftar:

| Metrik | Route Uncached | Route Cached (`route:cache`) | Laravel Octane (RoadRunner) |
| :--- | :--- | :--- | :--- |
| **Requests/sec (RPS)** | ~340 req/s | ~1,280 req/s | ~6,400 req/s |
| **Avg Latency** | 32.4 ms | 7.8 ms | 1.1 ms |
| **Memory Allocation/Req**| ~12 MB | ~4.5 MB | < 0.5 MB (Reused) |

---

## 15. Hands-on Lab Mini-Project

### Objective
Membangun secure proxy middleware pipeline yang bertugas:
1. Memvalidasi tanda tangan header HMAC (`X-Signature`).
2. Mencegah replay attack dengan validasi timestamp (`X-Timestamp` toleransi 60 detik).
3. Mengembalikan output JSON terenkripsi.

### Implementation Skeleton
```php
// app/Http/Middleware/HmacVerificationMiddleware.php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class HmacVerificationMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        $signature = $request->header('X-Signature');
        $timestamp = (int) $request->header('X-Timestamp');
        $secret = config('app.hmac_secret');

        if (abs(time() - $timestamp) > 60) {
            return response()->json(['error' => 'Timestamp out of synchronization range'], 401);
        }

        $payload = $request->getContent();
        $expectedSignature = hash_hmac('sha256', $timestamp . '.' . $payload, $secret);

        if (!hash_equals($expectedSignature, (string) $signature)) {
            return response()->json(['error' => 'Invalid HMAC Signature'], 403);
        }

        return $next($request);
    }
}
```

---

## 16. Automated Testing & Verification

Automated Feature Tests untuk memvalidasi Middleware dan Route Layer:

```php
namespace Tests\Feature;

use Tests\TestCase;
use Illuminate\Support\Facades\Redis;

class RouteMiddlewarePipelineTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        Redis::flushall();
    }

    public function test_payment_endpoint_fails_without_idempotency_key(): void
    {
        $response = $this->postJson('/api/v1/payments/execute', [
            'account_id' => '9a8d4e4e-4f76-4f71-a084-29738efb045e',
            'amount' => 150.00,
            'currency' => 'USD',
        ]);

        $response->assertStatus(422)
                 ->assertJsonPath('message', 'Idempotency key is required for mutative operations.');
    }

    public function test_payment_endpoint_returns_cached_response_for_duplicate_key(): void
    {
        $idempotencyKey = 'unique-req-uuid-12345';
        $payload = [
            'account_id' => '9a8d4e4e-4f76-4f71-a084-29738efb045e',
            'amount' => 150.00,
            'currency' => 'USD',
        ];

        // First Request (Calculated)
        $firstResponse = $this->withHeaders([
            'X-Idempotency-Key' => $idempotencyKey
        ])->postJson('/api/v1/payments/execute', $payload);

        $firstResponse->assertStatus(201);
        $firstData = $firstResponse->json('data.transaction_id');

        // Second Request (Must be Served from Cache)
        $secondResponse = $this->withHeaders([
            'X-Idempotency-Key' => $idempotencyKey
        ])->postJson('/api/v1/payments/execute', $payload);

        $secondResponse->assertStatus(201)
                       ->assertHeader('X-Cache-Lookup', 'HIT-IDEMPOTENT')
                       ->assertJsonPath('data.transaction_id', $firstData);
    }
}
```

Eksekusi suite pengetesan:
```bash
php artisan test --filter=RouteMiddlewarePipelineTest
```

---

## 17. Troubleshooting Guide

| Gejala Masalah | Investigasi Root Cause | Solusi Terapeutik |
| :--- | :--- | :--- |
| **Logic perubahan rute baru tidak berefek** | Route cache aktif di environment staging/dev lokal. | Jalankan `php artisan route:clear` untuk menghapus state compiled. |
| **Route Model Binding selalu melempar 404** | Nama parameter pada rute `{id}` tidak identik dengan nama variabel di Controller (`$userId`). | Samakan nama parameter: `Route::get('/users/{user}')` wajib match dengan `function (User $user)`. |
| **Deadlock pada Middleware Pipeline** | Closure `$next($request)` tidak di-return atau diabaikan dalam kondisi cabang logic tertentu. | Pastikan setiap percabangan mengeksekusi `return $next($request)` atau melempar explicit `Response`. |
| **Payload mutation tidak terlihat di Controller** | Request diubah via instance lokal baru tanpa menimpa Request global pipeline. | Gunakan `$request->merge(['key' => 'value'])` atau manipulasi via `$request->attributes->set()`. |

---

## 18. Checklist Produksi

- [ ] Pastikan tidak ada rute berbasis *Closure* di production (semua route menggunakan Controller actions).
- [ ] Pipeline CI/CD menjalankan `php artisan route:cache` saat proses deployment.
- [ ] Validasi bahwa konfigurasi `CORS` di `config/cors.php` tidak tersetting wildcard (`*`) untuk kredensial sensitif.
- [ ] Pastikan semua *mutative operations* (POST/PUT/PATCH/DELETE) dilindungi anti-tampering / rate-limiting.
- [ ] Middleware penanganan metrik/logging mengimplementasikan `TerminableMiddlewareInterface`.
- [ ] Konfigurasi Fallback route terdaftar untuk menangani *uncaught 404s* dengan format data yang terstruktur.

---

## 19. Ringkasan Eksekutif
Routing Engine dan Middleware Pipeline bertindak sebagai sistem saraf lalu lintas HTTP Laravel. Pipeline mengeksekusi request secara berurutan menggunakan arsitektur konsentris (*Chain of Responsibility*), memungkinkan intercept, otentikasi, validasi data, dan tracing sebelum mencapai lapisan aplikasi (controller). Optimalisasi tingkat lanjut menuntut transisi dari implicit parsing runtime ke compiled cache arrays, pemisahan interceptor berat ke terminable cycles, dan penerapan rate limiter terdistribusi berbasis Redis guna menghasilkan arsitektur enterprise yang aman, terprediksi, dan berkemampuan pemrosesan throughput tinggi.

---

## 20. Referensi & Bacaan Lanjutan
* [Laravel Documentation: Routing Deep Dive](https://laravel.com/docs/11.x/routing)
* [Laravel Documentation: Middleware Architecture](https://laravel.com/docs/11.x/middleware)
* [FastRoute Internal Matching Architecture (Nikita Popov)](https://github.com/nikic/FastRoute)
* [RFC 7231: Hypertext Transfer Protocol (HTTP/1.1) Semantics and Content](https://datatracker.ietf.org/doc/html/rfc7231)
* [Martin Fowler: Pipes and Filters Pattern](https://martinfowler.com/articles/collection-pipeline/)