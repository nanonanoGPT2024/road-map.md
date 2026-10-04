# Modul Pembelajaran: Authentication, Authorization & Security Hardening

---

## 01: Identitas Modul
* **Track:** Backend & Database Development
* **Kategori:** 04-Backend-and-Database
* **Topik:** Laravel Core Security Architecture
* **Bab:** 05 — Keamanan, Otentikasi, dan Kontrol Akses
* **Modul:** 01 — Authentication, Authorization & Security Hardening
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** Pemahaman arsitektur MVC Laravel, Service Container, Dependency Injection, Middleware, Eloquent ORM, Database Migrations, dan HTTP Lifecycle.

---

## 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta didik mampu:
1. Mengonfigurasi dan mengoperasikan arsitektur otentikasi multi-guard (Stateful Session & Stateless API Token via Laravel Sanctum).
2. Merancang dan menerapkan sistem otorisasi granular berbasis Attribute-Based Access Control (ABAC) dan Role-Based Access Control (RBAC) menggunakan Laravel Gates & Policies.
3. Mengamankan aplikasi web dari serangan OWASP Top 10 (CSRF, XSS, Mass Assignment, SQL Injection, Replay Attacks, dan Session Fixation).
4. Menerapkan penguatan keamanan defensif (*Security Hardening*) tingkat lanjut: Rate Limiting terdistribusi (Redis), HTTP Security Headers, Password Hashing Argon2id, Content Security Policy (CSP), dan Enkripsi Payload Sensitif.
5. Membangun pipeline validasi otomatis dan automated integration tests untuk mengaudit integritas izin dan keamanan otentikasi.

---

## 03: Concept Map Diagram ASCII
```
+--------------------------------------------------------------------------------------------------+
|                                    HTTP REQUEST LIFECYCLE                                        |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                               GLOBAL / ROUTE MIDDLEWARE PIPELINE                                 |
|  +------------------------+  +------------------------+  +------------------------------------+  |
|  | SecurityHeaders (CSP)  |->| ThrottleRequests/Redis |->| VerifyCsrfToken / EnsureFrontendReq |  |
|  +------------------------+  +------------------------+  +------------------------------------+  |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                  AUTHENTICATION LAYER (Guards)                                   |
|               +--------------------------------+--------------------------------+                |
|               |                                                                 |                |
|               v                                                                 v                |
|  +------------------------+                                       +---------------------------+  |
|  |   SessionGuard (Web)   |                                       |   SanctumGuard (Token/API)|  |
|  | - Encrypted Cookies    |                                       | - Personal Access Tokens  |  |
|  | - Session Fixation Prv |                                       | - Transient SPA Sessions  |  |
|  +------------------------+                                       +---------------------------+  |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                   AUTHORIZATION LAYER (Access)                                   |
|               +--------------------------------+--------------------------------+                |
|               |                                                                 |                |
|               v                                                                 v                |
|  +------------------------+                                       +---------------------------+  |
|  |      Gates (RBAC)      |                                       |     Policies (ABAC)       |  |
|  | - Global Access Rules  |                                       | - Model-Specific Logic    |  |
|  | - Role/Ability Mapping |                                       | - Resource Ownership      |  |
|  +------------------------+                                       +---------------------------+  |
+--------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                             BUSINESS LOGIC (Controllers / Actions)                               |
+--------------------------------------------------------------------------------------------------+
```

---

## 04: Mengapa Relevan?
Celah keamanan otentikasi dan otorisasi secara konsisten menempati peringkat teratas pada *OWASP Top 10 Application Security Risks* (khususnya *Broken Access Control* dan *Identification & Authentication Failures*). Di lingkungan produksi modern, aplikasi tidak hanya melayani sesi browser monolitik, melainkan arsitektur hibrida (Single Page Application, Mobile App, Microservices API, dan Webhook pihak ketiga).

Kegagalan memahami abstraksi keamanan Laravel—seperti menggunakan guard yang salah untuk REST API, mengabaikan regenerasi sesi saat otentikasi, atau membiarkan celah *Mass Assignment*—dapat mengakibatkan kebocoran data massal (*data breach*), pengambilalihan akun (*account takeover*), dan eksfiltrasi kredensial. Modul ini membekali engineer dengan pemahaman mendalam untuk merancang arsitektur keamanan defensif yang terisolasi dan tangguh di Laravel.

---

## 05: Anatomi Konsep Inti

### 1. Authentication Engine: Guards & Providers
Sistem otentikasi Laravel memisahkan mekanisme verifikasi identitas menjadi dua komponen:
* **Guards (`Illuminate\Contracts\Auth\Guard`):** Menentukan bagaimana pengguna diotentikasi untuk setiap request (misal: `SessionGuard` membaca cookie sesi terenkripsi, `SanctumGuard` memvalidasi Bearer Token `personal_access_tokens`).
* **User Providers (`Illuminate\Contracts\Auth\UserProvider`):** Menentukan bagaimana data identitas diambil dari storage (biasanya `EloquentUserProvider` via model `User` atau `DatabaseUserProvider`).

### 2. Password Hashing: Argon2id vs Bcrypt
Laravel secara *default* menggunakan `BcryptHasher`. Namun, untuk standar industri tingkat lanjut, `Argon2Id` menyediakan resistensi lebih tinggi terhadap serangan komputasi paralel GPU/ASIC dengan parameter kompleksitas waktu (*time cost*), memori (*memory cost*), dan paralelisasi (*threads*).

### 3. Session Security Lifecycle
Otentikasi berbasis stateful web rentan terhadap *Session Fixation* dan *Session Hijacking*. Siklus hidup sesi yang aman memerlukan:
* **Regenerasi Session ID:** Wajib dieksekusi via `$request->session()->regenerate()` tepat setelah verifikasi kredensial berhasil.
* **Invalidasi Mutlak:** Pemanggilan `$request->session()->invalidate()` dan penjaminan token CSRF baru via `$request->session()->regenerateToken()` saat logout.
* **Atribut Cookie:** `HttpOnly` (mencegah akses via JavaScript), `Secure` (hanya via HTTPS), dan `SameSite=Strict` atau `SameSite=Lax`.

### 4. Authorization Architecture: Gates vs Policies
* **Gates:** Penutupan (*closures*) otorisasi berbasis rute/aksi independen, ideal untuk izin non-entitas (contoh: `access-admin-dashboard`).
* **Policies:** Kelas yang mengorganisir logika otorisasi di sekitar model Eloquent tertentu (contoh: `PostPolicy` untuk model `Post`), mendukung metode standar RESTful (`viewAny`, `view`, `create`, `update`, `delete`, `restore`, `forceDelete`).

### 5. API Authentication (Laravel Sanctum)
Sanctum menyediakan sistem otentikasi *dual-mode*:
1. **Stateful SPA Authentication:** Menggunakan cookie sesi terenkripsi standar Laravel dengan proteksi CSRF otomatis (memvalidasi header `X-XSRF-TOKEN`).
2. **API Token Authentication:** Menggunakan token berbasis SHA-256 yang disimpan di database, diurai dari header `Authorization: Bearer <token>`, dilengkapi dengan mekanisme pembatasan izin (*Token Abilities*).

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Konfigurasi Hashing & Security Guards
Buka file `config/hashing.php` dan `config/auth.php` untuk mengatur default engine dan guard.

```php
// config/hashing.php
return [
    'driver' => env('HASH_DRIVER', 'argon2id'),
    'argon' => [
        'memory' => 65536, // 64 MB
        'threads' => 1,
        'time' => 4,
    ],
    'bcrypt' => [
        'rounds' => env('BCRYPT_ROUNDS', 12),
        'verify' => true,
    ],
];
```

```php
// config/auth.php
return [
    'defaults' => [
        'guard' => 'web',
        'passwords' => 'users',
    ],

    'guards' => [
        'web' => [
            'driver' => 'session',
            'provider' => 'users',
        ],
        'api' => [
            'driver' => 'sanctum',
            'provider' => 'users',
        ],
    ],

    'providers' => [
        'users' => [
            'driver' => 'eloquent',
            'model' => App\Models\User::class,
        ],
    ],
];
```

### Langkah 2: Middleware Pipeline Hardening
Daftarkan middleware pengamanan global dan per-route di `bootstrap/app.php` (Laravel 11) atau `app/Http/Kernel.php` (Laravel 10).

```php
// bootstrap/app.php (Contoh arsitektur Laravel 11)
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use App\Http\Middleware\SecurityHeadersMiddleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->append(SecurityHeadersMiddleware::class);
        $middleware->statefulApi(); // Mengaktifkan Sanctum SPA Guard
        
        $middleware->throttleApi('api', [
            \Illuminate\Routing\Middleware\ThrottleRequests::class.':api',
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        //
    })->create();
```

---

## 07: Contoh Kasus Sederhana: Gate-Based Access Control

Contoh deklarasi Gate otorisasi untuk membatasi akses dasbor berdasarkan *role* pengguna.

```php
// app/Providers/AppServiceProvider.php
namespace App\Providers;

use App\Models\User;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        // Mendefinisikan Gate sederhana
        Gate::define('access-finance-dashboard', function (User $user) {
            return $user->role === 'finance_auditor' && $user->is_active;
        });
    }
}
```

Implementasi di Controller:
```php
// app/Http/Controllers/FinanceDashboardController.php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Symfony\Component\HttpFoundation\Response;

class FinanceDashboardController extends Controller
{
    public function index(Request $request)
    {
        // Memeriksa otorisasi via Gate
        if (! Gate::allows('access-finance-dashboard')) {
            abort(Response::HTTP_FORBIDDEN, 'Akses Ditolak: Kredensial role tidak memenuhi syarat.');
        }

        return view('finance.dashboard');
    }
}
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi lengkap sistem multi-tier authorization & dynamic token-based API authentication dengan model *Document Management*, menerapkan Policies, Form Request Validation, Rate Limiting, dan Custom Security Headers.

### 1. Migrations & Model User / Document
```php
// database/migrations/2026_01_01_000001_create_security_core_tables.php
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::create('users', function (Blueprint $table) {
            $table->id();
            $table->string('name', 100);
            $table->string('email', 150)->unique();
            $table->string('password');
            $table->string('role', 30)->default('viewer'); // admin, editor, viewer
            $table->json('permissions')->nullable();
            $table->boolean('is_active')->default(true);
            $table->timestamp('email_verified_at')->nullable();
            $table->rememberToken();
            $table->timestamps();
            
            $table->index(['email', 'is_active']);
        });

        Schema::create('documents', function (Blueprint $table) {
            $table->id();
            $table->foreignId('user_id')->constrained()->cascadeOnDelete();
            $table->string('title', 200);
            $table->text('payload_encrypted');
            $table->enum('classification', ['public', 'internal', 'confidential', 'secret'])->default('internal');
            $table->timestamps();
            $table->softDeletes();
            
            $table->index(['classification', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('documents');
        Schema::dropIfExists('users');
    }
};
```

### 2. Model: User & Document
```php
// app/Models/User.php
namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Notifications\Notifiable;
use Laravel\Sanctum\HasApiTokens;

class User extends Authenticatable
{
    use HasApiTokens, HasFactory, Notifiable;

    protected $fillable = [
        'name',
        'email',
        'password',
        'role',
        'permissions',
        'is_active',
    ];

    protected $hidden = [
        'password',
        'remember_token',
    ];

    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'password' => 'hashed',
            'permissions' => 'array',
            'is_active' => 'boolean',
        ];
    }

    public function documents(): HasMany
    {
        return $this->hasMany(Document::class);
    }

    public function hasAbility(string $ability): bool
    {
        return in_array($ability, $this->permissions ?? [], true);
    }
}
```

```php
// app/Models/Document.php
namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\SoftDeletes;
use Illuminate\Database\Eloquent\Casts\Attribute;
use Illuminate\Support\Facades\Crypt;

class Document extends Model
{
    use SoftDeletes;

    protected $fillable = [
        'user_id',
        'title',
        'payload_encrypted',
        'classification',
    ];

    /**
     * Mutator & Accessor untuk enkripsi otomatis payload sensitif.
     */
    protected function payload(): Attribute
    {
        return Attribute::make(
            get: fn (mixed $value, array $attributes) => Crypt::decryptString($attributes['payload_encrypted']),
            set: fn (string $value) => ['payload_encrypted' => Crypt::encryptString($value)]
        );
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
```

### 3. Policy: DocumentPolicy (ABAC Logic)
```php
// app/Policies/DocumentPolicy.php
namespace App\Policies;

use App\Models\Document;
use App\Models\User;
use Illuminate\Auth\Access\Response;

class DocumentPolicy
{
    /**
     * Pre-authorization check: Admin memiliki akses mutlak (Superuser Bypass).
     */
    public function before(User $user, string $ability): ?bool
    {
        if ($user->role === 'admin' && $user->is_active) {
            return true;
        }

        return null; // Lanjutkan ke method spesifik
    }

    public function view(User $user, Document $document): Response
    {
        if (! $user->is_active) {
            return Response::deny('Akun Anda dinonaktifkan.');
        }

        // Dokumen publik dapat diakses siapapun yang terotentikasi
        if ($document->classification === 'public') {
            return Response::allow();
        }

        // Resource ownership check
        if ($document->user_id === $user->id) {
            return Response::allow();
        }

        // Dokumen confidential membutuhkan role editor dan hak akses eksplisit
        if ($document->classification === 'confidential' && $user->role === 'editor' && $user->hasAbility('read:confidential')) {
            return Response::allow();
        }

        return Response::deny('Anda tidak memiliki wewenang untuk membaca dokumen ini.');
    }

    public function update(User $user, Document $document): Response
    {
        if (! $user->is_active) {
            return Response::deny('Akun Anda dinonaktifkan.');
        }

        return $user->id === $document->user_id
            ? Response::allow()
            : Response::deny('Hanya pemilik dokumen yang dapat mengubah data ini.');
    }

    public function delete(User $user, Document $document): Response
    {
        return ($user->id === $document->user_id && $user->hasAbility('delete:document'))
            ? Response::allow()
            : Response::deny('Operasi penghapusan ditolak. Otoritas tidak mencukupi.');
    }
}
```

### 4. Custom Middleware: Security Headers
```php
// app/Http/Middleware/SecurityHeadersMiddleware.php
namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class SecurityHeadersMiddleware
{
    public function handle(Request $request, Closure $next): Response
    {
        /** @var Response $response */
        $response = $next($request);

        // Mencegah Clickjacking
        $response->headers->set('X-Frame-Options', 'DENY');
        
        // Mencegah MIME-sniffing
        $response->headers->set('X-Content-Type-Options', 'nosniff');
        
        // Mencegah XSS di browser legacy
        $response->headers->set('X-XSS-Protection', '1; mode=block');
        
        // Mengontrol pengiriman metadata referrer
        $response->headers->set('Referrer-Policy', 'strict-origin-when-cross-origin');
        
        // Enforce HTTPS HSTS (2 tahun + preload)
        $response->headers->set('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload');
        
        // Content Security Policy (CSP) ketat
        $csp = "default-src 'self'; " .
               "script-src 'self'; " .
               "style-src 'self' 'unsafe-inline'; " .
               "img-src 'self' data: https:; " .
               "font-src 'self'; " .
               "object-src 'none'; " .
               "frame-ancestors 'none'; " .
               "base-uri 'self'; " .
               "form-action 'self';";
               
        $response->headers->set('Content-Security-Policy', $csp);

        return $response;
    }
}
```

### 5. Controller: Secure Authentication & API Controller
```php
// app/Http/Controllers/Api/AuthController.php
namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\Response;

class AuthController extends Controller
{
    public function login(Request $request): JsonResponse
    {
        $credentials = $request->validate([
            'email' => ['required', 'string', 'email:rfc,dns'],
            'password' => ['required', 'string', 'min:12'],
            'device_name' => ['required', 'string', 'max:50'],
        ]);

        $user = User::where('email', $credentials['email'])->first();

        if (! $user || ! Hash::check($credentials['password'], $user->password)) {
            throw ValidationException::withMessages([
                'email' => ['Kredensial yang diberikan tidak cocok dengan data kami.'],
            ]);
        }

        if (! $user->is_active) {
            return response()->json([
                'message' => 'Akun dinonaktifkan oleh administrator.',
            ], Response::HTTP_FORBIDDEN);
        }

        // Buat token dengan kemampuan (abilities) sesuai role dan permissions
        $token = $user->createToken(
            $request->input('device_name'),
            $user->permissions ?? ['*'],
            now()->addHours(8) // Token TTL
        )->plainTextToken;

        return response()->json([
            'token_type' => 'Bearer',
            'access_token' => $token,
            'expires_at' => now()->addHours(8)->toIso8601String(),
        ], Response::HTTP_OK);
    }

    public function logout(Request $request): JsonResponse
    {
        // Revoke token yang sedang aktif digunakan saat request ini
        $request->user()->currentAccessToken()->delete();

        return response()->json([
            'message' => 'Token otentikasi berhasil dicabut (Revoked).',
        ], Response::HTTP_OK);
    }
}
```

```php
// app/Http/Controllers/Api/DocumentController.php
namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Document;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Symfony\Component\HttpFoundation\Response;

class DocumentController extends Controller
{
    public function show(Request $request, Document $document): JsonResponse
    {
        // Evaluasi Policy via Authorize method
        Gate::authorize('view', $document);

        return response()->json([
            'id' => $document->id,
            'title' => $document->title,
            'payload' => $document->payload, // Otomatis didekripsi via Accessor
            'classification' => $document->classification,
            'owner_id' => $document->user_id,
        ], Response::HTTP_OK);
    }

    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'title' => ['required', 'string', 'max:200'],
            'payload' => ['required', 'string'],
            'classification' => ['required', 'in:public,internal,confidential,secret'],
        ]);

        $document = new Document();
        $document->user_id = $request->user()->id;
        $document->title = $validated['title'];
        $document->payload = $validated['payload']; // Otomatis dienkripsi via Mutator
        $document->classification = $validated['classification'];
        $document->save();

        return response()->json([
            'message' => 'Dokumen terenkripsi berhasil disimpan.',
            'id' => $document->id,
        ], Response::HTTP_CREATED);
    }
}
```

### 6. Dynamic Route Configuration & Distributed Rate Limiting
```php
// routes/api.php
use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\DocumentController;
use Illuminate\Support\Facades\Route;

// Public Endpoint dengan proteksi Rate Limit ketat berbasis IP
Route::post('/v1/auth/login', [AuthController::class, 'login'])
    ->middleware('throttle:5,1'); // Max 5 request per menit per IP

// Authenticated Endpoints via Sanctum Guard
Route::middleware(['auth:sanctum', 'throttle:60,1'])->prefix('v1')->group(function () {
    Route::post('/auth/logout', [AuthController::class, 'logout']);
    
    Route::get('/documents/{document}', [DocumentController::class, 'show']);
    Route::post('/documents', [DocumentController::class, 'store']);
});
```

---

## 09: Diagram Alur Kerja ASCII: Stateful vs Stateless Auth

```
=== STATEFUL WEB (SESSION + COOKIE + CSRF) ===
Browser                         Laravel Application                Redis / Session Store
   |                                    |                                    |
   |--- 1. POST /login (Credentials) -->|                                    |
   |                                    |--- 2. Hash::check() Password ----->|
   |                                    |--- 3. $request->session()->reg() ->|
   |                                    |--- 4. Set Session Payload -------->| (Save Session ID)
   |<-- 5. Set-Cookie: session_id, -----|                                    |
   |       XSRF-TOKEN (HttpOnly, Secure)|                                    |
   |                                    |                                    |
   |--- 6. POST /data (Cookie+Header) ->|                                    |
   |       Header: X-XSRF-TOKEN         |--- 7. Validate CSRF Match -------->|
   |                                    |--- 8. Fetch User from Session ---->|
   |<-- 9. 200 OK Response -------------|                                    |


=== STATELESS API (SANCTUM BEARER TOKEN) ===
Client / Mobile App             Laravel Application                Database (PAT)
   |                                    |                                    |
   |--- 1. POST /api/v1/auth/login ---->|                                    |
   |       (Credentials)                |--- 2. Hash::check() & Verify ----->|
   |                                    |--- 3. Hash & Store Token --------->| (INSERT token)
   |<-- 4. 200 OK (plainTextToken) -----|                                    |
   |                                    |                                    |
   |--- 5. GET /api/v1/documents/42 --->|                                    |
   |       Authorization: Bearer <tok>  |--- 6. SHA-256 Hash Token --------->|
   |                                    |--- 7. Lookup Valid & Non-Expired ->|
   |                                    |--- 8. Execute DocumentPolicy ----->|
   |<-- 9. 200 OK (JSON Payload) -------|                                    |
```

---

## 10: Analisis Trade-offs

| Pendekatan / Fitur | Keuntungan | Kerugian / Risiko | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **Stateful Sessions (Cookies)** | Kebal terhadap pencurian skrip jika `HttpOnly`, pembatalan sesi instan di server. | Memerlukan mitigasi CSRF aktif, kendala CORS dan integrasi non-browser (*Mobile Apps*). | Monolith Blade Views, First-party Single Page Applications (Next.js/Nuxt SPA pada domain/subdomain yang sama). |
| **Personal Access Tokens (Sanctum)** | Stateless untuk klien, sangat mudah digunakan pada Mobile & Third-party integrations, mendukung granular abilities. | Setiap request memicu query database/cache untuk validasi token, penambahan overhead I/O. | API seluler pihak ketiga, sistem integrasi B2B, Microservices internal. |
| **Bcrypt (Default Hasher)** | Konsumsi memori sangat rendah, kompatibilitas bawaan universal di semua CPU. | Rentan terhadap komputasi paralel masif menggunakan rig mining GPU/FPGA modern. | Sistem dengan resource server terbatas (< 512MB RAM total). |
| **Argon2id Hasher** | Tahan terhadap serangan brute-force berbasis ASIC/GPU via konfigurasi memory-hardness. | Beban konsumsi RAM dan thread CPU tinggi pada spikes traffic otentikasi. | Aplikasi tingkat Enterprise, FinTech, data medis dengan spesifikasi server memadai. |
| **Gates vs Policies** | Gate: Ringkas untuk proteksi rute sederhana. | Tidak terstruktur untuk model kompleks, berpotensi menciptakan duplikasi logika izin. | Gate untuk otentikasi global (e.g. `view-nova`), Policy untuk entitas Domain Model. |

---

## 11: Best Practices & Antipatterns

### ✅ Best Practices
1. **Regenerate Session ID Secara Konsisten:** Panggil `$request->session()->regenerate()` setiap kali user berhasil melewati tahapan verifikasi identitas (login, 2FA challenge).
2. **Gunakan Explicit Policy Registration:** Hindari asumsi nama model otomatis; bind model ke policy di `AuthServiceProvider` atau konvensi direktori standar.
3. **Defense in Depth dengan Encrypted Attributes:** Data rahasia (seperti nomor identitas, payload rahasia) wajib dienkripsi di level basis data menggunakan `Illuminate\Support\Facades\Crypt`.
4. **Batas Rentang Validitas Token (Token Expiration):** Konfigurasikan `'expiration' => 480` (dalam menit) pada `config/sanctum.php` untuk mencegah token berlaku selamanya.
5. **Fail-Closed Authorization:** Policy harus selalu mengembalikan `Response::deny()` secara default jika kondisi validasi hak akses tidak terpenuhi secara eksplisit.

### ❌ Antipatterns
1. **Insecure Direct Object Reference (IDOR):** Mengambil data resource langsung menggunakan ID tanpa otorisasi:
   ```php
   // ANTI-PATTERN
   public function getDoc($id) {
       return Document::findOrFail($id); // Siapapun yang login bisa baca dokumen orang lain!
   }
   ```
2. **Mass Assignment Vulnerability pada Kolom Privilege:** Mengizinkan input `$request->all()` saat `User::create()` tanpa memproteksi atribut `role` atau `permissions` di `$fillable`.
3. **Hardcoded Secrets & Hashes:** Menyimpan *API salt*, kunci simetris, atau fallback password di kode sumber (*source control*).
4. **Verifikasi Izin di UI Saja:** Menyembunyikan tombol "Hapus" pada view/frontend tanpa memvalidasi `Gate::authorize('delete', $model)` pada controller backend.
5. **Stateless API Tanpa Rate Limiter:** Membiarkan rute `/oauth/token` atau `/api/login` tanpa batasan request per menit, membuka jalan bagi serangan *brute force credential stuffing*.

---

## 12: Security Hardening

### 1. Advanced Rate Limiting via Redis
Definisikan custom limiter dengan dynamic decay rates di `AppServiceProvider`:

```php
// app/Providers/AppServiceProvider.php
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;

public function boot(): void
{
    RateLimiter::for('login-endpoint', function (Request $request) {
        $email = (string) $request->input('email');
        
        return [
            // Batasi per email target (mencegah penargetan satu akun dari multi IP)
            Limit::perMinute(5)->by($email),
            // Batasi per IP klien (mencegah distributed dictionary attacks)
            Limit::perMinute(10)->by($request->ip()),
        ];
    });
}
```

### 2. Mencegah Timing Attacks
Gunakan pembanding string berwaktu konstan (`hash_equals`) saat memverifikasi tanda tangan kriptografi atau token manual:

```php
if (! hash_equals($knownSignature, $userProvidedSignature)) {
    abort(403, 'Invalid signature.');
}
```

### 3. Password Validation Strict Rules
Gunakan aturan validasi password uncompromised (memeriksa database Pwned Passwords via k-Anonymity):

```php
use Illuminate\Validation\Rules\Password;

$request->validate([
    'password' => [
        'required',
        'string',
        Password::min(12)
            ->letters()
            ->mixedCase()
            ->numbers()
            ->symbols()
            ->uncompromised(3), // Ditolak jika muncul >3 kali di kebocoran data publik
    ],
]);
```

---

## 13: Observabilitas & Debugging

### Logging Mutlak Peristiwa Keamanan
Gunakan Laravel Event Listeners untuk merekam jejak audit keamanan (*Security Audit Trail*) ke logging pipeline tersendiri.

```php
// app/Listeners/LogAuthenticationEvents.php
namespace App\Listeners;

use Illuminate\Auth\Events\Failed;
use Illuminate\Auth\Events\Login;
use Illuminate\Support\Facades\Log;

class LogAuthenticationEvents
{
    public function handleLogin(Login $event): void
    {
        Log::channel('security')->info('Authentication Successful', [
            'user_id' => $event->user->getAuthIdentifier(),
            'guard' => $event->guard,
            'ip_address' => request()->ip(),
            'user_agent' => request()->userAgent(),
            'timestamp' => now()->toIso8601String(),
        ]);
    }

    public function handleFailed(Failed $event): void
    {
        Log::channel('security')->warning('Authentication Failed Attempt', [
            'attempted_user' => $event->credentials['email'] ?? 'unknown',
            'guard' => $event->guard,
            'ip_address' => request()->ip(),
            'user_agent' => request()->userAgent(),
            'timestamp' => now()->toIso8601String(),
        ]);
    }
}
```

Daftarkan logging channel di `config/logging.php`:
```php
'channels' => [
    'security' => [
        'driver' => 'daily',
        'path' => storage_path('logs/security-audit.log'),
        'level' => 'info',
        'days' => 90, // Retention 90 hari untuk compliance ISO27001/SOC2
    ],
],
```

---

## 14: Benchmarking & Performance

Proses otentikasi melibatkan pemrosesan kriptografi berat (Argon2id/Bcrypt). Di bawah ini adalah panduan benchmarking performa hashing dan dampak latensi otentikasi.

### Benchmark Password Hashing Latency
Gunakan Artisan Command untuk mengukur CPU cost pada server target:

```php
// app/Console/Commands/BenchmarkHashing.php
namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\Hash;

class BenchmarkHashing extends Command
{
    protected $signature = 'benchmark:hashing {iterations=10}';
    protected $description = 'Ukur durasi eksekusi hashing Argon2id