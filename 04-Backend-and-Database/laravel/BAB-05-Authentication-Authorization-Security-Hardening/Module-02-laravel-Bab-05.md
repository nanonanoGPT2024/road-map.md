# BAB 05: Authentication, Authorization & Security Hardening
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Mengonstruksi arsitektur autentikasi terdistribusi skala enterprise menggunakan Laravel Sanctum dan Laravel Passport (OAuth2/OIDC) dengan isolasi state token yang aman.
- Merancang dan mengimplementasikan *Custom Authentication Guard* dan *Custom User Provider* untuk integrasi sistem identitas eksternal (misal: IDP berbasis Keycloak, LDAP, atau Service Token berbasis mTLS).
- Membangun mesin otorisasi granular berbasis kombinasi RBAC (Role-Based Access Control) dan ABAC (Attribute-Based Access Control) memanfaatkan Gate, Policy, dan contextual pipeline di Laravel.
- Mengamankan komunikasi antarlayanan via *HMAC Webhook Signature verification*, *strict rate limiting* (Token Bucket/Redis Leaky Bucket), dan *sub-resource integrity hardening*.
- Menerapkan perlindungan mendalam terhadap vektor serangan modern (Timing attacks, Replay attacks, Race conditions pada refresh tokens, Session fixation, dan Insecure Direct Object References).

---

### 2. Prerequisite
- Pemahaman mendalam tentang Laravel Service Container, Pipeline, Middleware, dan Service Providers.
- Pengetahuan fundamental mengenai HTTP Protocol (RFC 7235, RFC 6749 OAuth 2.0, RFC 7519 JSON Web Token).
- Pemahaman tentang Cryptography Primitives (Symmetric vs Asymmetric Encryption, Argon2id, PBKDF2, HMAC-SHA256).
- Pengalaman administrasi Redis untuk token blacklist, caching, dan distributed rate limiting.

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur autentikasi dan otorisasi Laravel dibangun di atas abstraksi *Stateful Sessions* dan *Stateless Tokens*. Untuk memahami bagaimana Laravel mengevaluasi kredensial dan izin, kita harus membedah lifecycle internalnya.

```
Request 
   │
   ▼
[HTTP Kernel] ──► [Pipeline Middleware: Authenticate / Sanctum]
                         │
                         ▼
             [AuthManager (Illuminate\Auth\AuthManager)]
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
 [Guard Driver: 'session']      [Guard Driver: 'sanctum' / 'token']
         │                               │
         ├─► Membaca Cookie/Session ID   ├─► Membaca Bearer Token
         │                               │
         ▼                               ▼
 [User Provider: Eloquent / Database / Custom]
         │
         ├── Mengambil Entity User berdasarkan Identifier (UUID/ID)
         ├── Validasi Password via Hasher (Argon2id / Bcrypt)
         │
         ▼
 [Authenticated User Resolved & Bound to Request Context]
         │
         ▼
[Gate Engine (Illuminate\Auth\Access\Gate)]
         │
         ├─► Policy Resolution via Context Reflection
         ├─► ABAC Evaluation (User attributes, Resource state, Environment)
         │
         ▼
[Controller / Action Execution]
```

#### A. AuthManager, Guard, dan UserProvider Lifecycle
1. **`AuthManager`**: Bertindak sebagai *Factory* dan *Façade Manager*. Memetakan konfigurasi `config/auth.php` ke instansiasi konkret `Guard`.
2. **`Guard` (`Illuminate\Contracts\Auth\Guard` & `StatefulGuard`)**: Bertanggung jawab menentukan *bagaimana* sebuah request diidentifikasi. Guard mengekstrak kredensial dari request (Session Cookie, HTTP Header `Authorization: Bearer <token>`, atau mTLS Client Certificate), memvalidasi integritasnya, dan menyimpan instansi user yang terautentikasi di memori internal request.
3. **`UserProvider` (`Illuminate\Contracts\Auth\UserProvider`)**: Bertanggung jawab menentukan *di mana* dan *bagaimana* data user ditarik dari storage persisten (MySQL via Eloquent, DynamoDB, Redis, atau API IDP eksternal). Provider tidak peduli tentang HTTP; tugasnya murni kalkulasi hash password (`validateCredentials`) dan fetching user (`retrieveById`, `retrieveByCredentials`).

#### B. Sanctum vs. Passport: Deep Architectural Trade-Off
* **Laravel Sanctum**:
  - Menggunakan kombinasi *Stateful Cookie-based Authentication* (untuk SPA first-party menggunakan secure, `HttpOnly`, `SameSite=Lax` cookies melalui session driver) dan *Personal Access Tokens* (PAT) bertipe opaque tokens berawalan prefix (misal: `1|abcdef...`) yang disimpan di database dalam bentuk hash SHA-256.
  - Sangat ringan, latensi rendah (hanya lookup ke satu tabel `personal_access_tokens`), tidak memerlukan overhead kriptografi asimetris.
* **Laravel Passport**:
  - Implementasi penuh dari OAuth2 Server Specification (RFC 6749) berbasis League OAuth2 Server.
  - Mendukung grant types: *Authorization Code with PKCE*, *Client Credentials*, *Refresh Token*.
  - Menggunakan JSON Web Tokens (JWT) yang ditandatangani dengan kunci privat RSA/ECDSA, memungkinkan validasi stateless di level microservices API Gateway tanpa perlu menyentuh database auth pusat pada setiap request (hanya validasi public key signature).

#### C. Gate & Policy Evaluation Engine
Internal `Illuminate\Auth\Access\Gate` mengevaluasi otorisasi dengan urutan determistik:
1. **`before` Callbacks**: Interseptor global (biasanya digunakan untuk Superadmin override). Mengembalikan boolean langsung bypass policy.
2. **Policy Discovery & Binding**: Laravel memetakan model instance ke policy class via konvensi namespace atau eksplisit registration di `AuthServiceProvider`.
3. **Method Matching & Injection**: Gate menginjeksi `$user` aktif dan model target, lalu mengevaluasi method policy.
4. **`after` Callbacks**: Berguna untuk audit logging atau dynamic telemetry access decisions.

---

### 4. Why & What

| Dimensi | Pendekatan Monolith Dasar | Arsitektur Enterprise Hardened |
| :--- | :--- | :--- |
| **Penyimpanan Token** | Plain JWT di LocalStorage (Rentan XSS) | `HttpOnly`, `Secure`, `SameSite=Strict` Cookie untuk SPA, Opaque Hashed Token untuk Public API, Short-lived Asymmetric JWT untuk Distributed Microservices. |
| **Otorisasi** | Hardcoded `$user->role == 'admin'` di Controller/View | Centralized ABAC Policy Engine mengevaluasi *Subject*, *Action*, *Resource*, dan *Context Environment* (Waktu, IP Whitelist, Tenant ID). |
| **Session Tracking** | Session driver file bawaan tanpa isolasi | Redis Sentinel/Cluster terenkripsi dengan metadata session hashing, mutasi User-Agent detection, dan anti-concurrent login lock. |
| **API Boundary** | IP Rate limiter standar (60 req/min) | Distributed Sliding Window / Token Bucket via Redis, mTLS client verification, HMAC-SHA256 signature verification untuk incoming webhooks. |

---

### 5. How (Workflow Detail)

#### Workflow: Dynamic Attribute-Based Access Control (ABAC) Pipeline
```
[Client Request: PATCH /api/v1/settlements/{id}]
                   │
                   ▼
       [RateLimit & IP Context Validation]
                   │
                   ▼
  [Authenticate Guard: Custom Enterprise Guard]
     ├── Ekstrak Token/Assertion
     └── Bind User Entity + Tenant Entity ke Request
                   │
                   ▼
   [Gate Engine: Policy Evaluation]
     ├── Policy: SettlementPolicy@update
     ├── Context Injection:
     │     ├── Subject: User (Role: RegionalManager, Clearance: Level3)
     │     ├── Resource: Settlement (Status: Pending, Amount: 500M IDR, Region: JKT)
     │     └── Environment: Time (09:00 - 17:00), Network (Corp VPN)
     │
     └── Rule Engine:
           ├── Apakah Clearance >= Rule(Amount)?
           ├── Apakah User->Region == Resource->Region?
           └── Apakah Waktu eksekusi valid?
                   │
         ┌─────────┴─────────┐
       [Valid]            [Invalid]
         │                   │
         ▼                   ▼
[Controller Invoked]    [403 Forbidden Response + Security Audit Event]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengamanan Fasilitas Riset Nuklir
- **Authentication Guard (Pos Satpam Utama)**: Memeriksa fisik kartu identitas atau sidik jari (Sanctum/Passport). Satpam memastikan *"Siapa Anda sebenarnya"* bukan *"Apa hak Anda"*.
- **User Provider (Buku Arsip Kependudukan)**: Basis data intelijen tempat satpam mencari rekam jejak identitas saat Anda memberikan KTP (Database/LDAP/Active Directory).
- **ABAC Gate/Policy (Pintu Kedap Udara Bertingkat)**: Untuk membuka ruang reaktor:
  1. Anda butuh lencana Level 4 (*Role*).
  2. Suhu reaktor harus di bawah ambang batas (*Resource State*).
  3. Masuk hanya boleh berdua dengan supervisor dan harus pada jam kerja (*Environment Context*).

```
+---------------------------------------------------------------------------------+
|                       LARAVEL AUTHENTICATION ARCHITECTURE                       |
+---------------------------------------------------------------------------------+
                                       │
                               [HTTP Request]
                                       │
                                       ▼
                       +───────────────────────────────+
                       |        AuthManager            |
                       +───────────────────────────────+
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
+───────────────────────+                             +───────────────────────+
|      Web Guard        |                             |     Sanctum Guard     |
| (Session + Cookies)   |                             | (Bearer Token Opaque) |
+───────────────────────+                             +───────────────────────+
            │                                                     │
            └──────────────────────────┬──────────────────────────┘
                                       │
                                       ▼
                       +───────────────────────────────+
                       |    Custom / Eloquent Provider |
                       +───────────────────────────────+
                                       │
                                       ▼
                       +───────────────────────────────+
                       |   Authenticated SecurityUser  |
                       +───────────────────────────────+
                                       │
                                       ▼
                       +───────────────────────────────+
                       |     ABAC Gate Evaluation      |
                       | (Subject + Resource + Context)|
                       +───────────────────────────────+
                                       │
                      [PASSED] ────────┴──────── [FAILED]
                         │                          │
                         ▼                          ▼
               Execute Controller           Throw AuthorizationException (403)
```

---

### 7. Simple Example & Practical Example

#### A. Custom Guard & Custom User Provider
Kasus: Integrasi otentikasi upstream internal microservices menggunakan Header Service Assertion yang divalidasi dengan signature kriptografis publik.

```php
<?php

declare(strict_types=1);

namespace App\Services\Auth;

use App\Models\User;
use Illuminate\Contracts\Auth\Authenticatable;
use Illuminate\Contracts\Auth\Guard;
use Illuminate\Http\Request;

final class HeaderSignatureGuard implements Guard
{
    private ?Authenticatable $user = null;

    public function __construct(
        private readonly Request $request,
        private readonly ExternalIdpUserProvider $provider,
        private readonly string $secretKey
    ) {}

    public function check(): bool
    {
        return $this->user() !== null;
    }

    public function guest(): bool
    {
        return ! $this->check();
    }

    public function user(): ?Authenticatable
    {
        if ($this->user !== null) {
            return $this->user;
        }

        $token = $this->request->header('X-Internal-Token');
        $signature = $this->request->header('X-Internal-Signature');
        $timestamp = (int) $this->request->header('X-Internal-Timestamp');

        if (! $token || ! $signature || ! $timestamp) {
            return null;
        }

        // Mitigasi Replay Attack: Reques tidak boleh lebih dari 300 detik
        if (abs(time() - $timestamp) > 300) {
            return null;
        }

        // Mitigasi Timing Attack: Gunakan hash_equals
        $payload = "{$token}.{$timestamp}";
        $expectedSignature = hash_hmac('sha256', $payload, $this->secretKey);

        if (! hash_equals($expectedSignature, $signature)) {
            return null;
        }

        $this->user = $this->provider->retrieveByToken($token);

        return $this->user;
    }

    public function id(): ?int
    {
        return $this->user()?->getAuthIdentifier();
    }

    public function validate(array $credentials = []): bool
    {
        return false; // Stateless guard tidak mendukung validasi kredensial array standar
    }

    public function hasUser(): bool
    {
        return $this->user !== null;
    }

    public function setUser(Authenticatable $user): self
    {
        $this->user = $user;
        return $this;
    }
}
```

```php
<?php

declare(strict_types=1);

namespace App\Services\Auth;

use App\Models\User;
use Illuminate\Contracts\Auth\Authenticatable;
use Illuminate\Contracts\Auth\UserProvider;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Cache;

final class ExternalIdpUserProvider implements UserProvider
{
    public function __construct(private readonly string $idpBaseUrl) {}

    public function retrieveById($identifier): ?Authenticatable
    {
        return User::query()->find($identifier);
    }

    public function retrieveByToken($token): ?Authenticatable
    {
        return Cache::remember("idp_token:{$token}", 60, function () use ($token) {
            $response = Http::timeout(2)
                ->withHeaders(['Authorization' => "Bearer {$token}"])
                ->get("{$this->idpBaseUrl}/api/v1/introspect");

            if ($response->failed()) {
                return null;
            }

            $data = $response->json();

            return User::firstOrCreate(
                ['external_uuid' => $data['sub']],
                [
                    'email' => $data['email'],
                    'name' => $data['name'],
                    'clearance_level' => $data['clearance'] ?? 1,
                    'is_active' => true,
                ]
            );
        });
    }

    public function retrieveByCredentials(array $credentials): ?Authenticatable
    {
        return null;
    }

    public function validateCredentials(Authenticatable $user, array $credentials): bool
    {
        return false;
    }

    public function rehashPasswordIfRequired(Authenticatable $user, array $credentials, bool $force = false): void {}
}
```

Registrasi pada `AppServiceProvider`:
```php
public function boot(): void
{
    Auth::extend('header_signature', function ($app, $name, array $config) {
        return new HeaderSignatureGuard(
            $app['request'],
            Auth::createUserProvider($config['provider']),
            config('services.internal_auth.secret')
        );
    });

    Auth::provider('external_idp', function ($app, array $config) {
        return new ExternalIdpUserProvider(config('services.idp.url'));
    });
}
```

#### B. Dynamic ABAC Implementation Menggunakan Policy & Attributes
Mengevaluasi transaksi finansial berdasarkan atribut subject, atribut resource, dan waktu:

```php
<?php

declare(strict_types=1);

namespace App\Policies;

use App\Models\Settlement;
use App\Models\User;
use Carbon\CarbonImmutable;
use Illuminate\Auth\Access\Response;

final class SettlementPolicy
{
    /**
     * Otorisasi ABAC:
     * 1. User wajib memiliki level izin >= limit nominal resource.
     * 2. Branch Code user wajib sama dengan branch origin resource (multi-tenant boundary).
     * 3. Eksekusi hanya boleh di jam operasional (08:00 - 18:00 WIB).
     */
    public function approve(User $user, Settlement $settlement): Response
    {
        // 1. Evaluasi Waktu (Environment Context)
        $now = CarbonImmutable::now('Asia/Jakarta');
        if ($now->hour < 8 || $now->hour >= 18) {
            return Response::deny('Persetujuan hanya diizinkan selama jam operasional (08:00 - 18:00 WIB).');
        }

        // 2. Evaluasi Multi-Tenant Boundary (Resource vs Subject)
        if ($user->branch_id !== $settlement->branch_id) {
            return Response::deny('Pelanggaran yurisdiksi: Anda tidak terdaftar pada cabang settlement ini.');
        }

        // 3. Evaluasi Batas Otorisasi Nominal (ABAC Threshold)
        $requiredClearance = match (true) {
            $settlement->amount_cents >= 1_000_000_000_00 => 4, // > 1 Miliar: Clearance 4 (Director)
            $settlement->amount_cents >= 100_000_000_00   => 3, // > 100 Juta: Clearance 3 (VP)
            default                                      => 2, // < 100 Juta: Clearance 2 (Manager)
        };

        if ($user->clearance_level < $requiredClearance) {
            return Response::deny("Izin ditolak: Butuh level clearance {$requiredClearance} untuk nominal ini.");
        }

        // 4. Mencegah Self-Approval (Segregation of Duties)
        if ($user->id === $settlement->creator_id) {
            return Response::deny('Conflict of Interest: Pembuat transaksi dilarang melakukan persetujuan.');
        }

        return Response::allow();
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus Arsitektur: Bank Core API Gateway Migration ke Laravel Sanctum Multi-Guard
- **Kondisi Awal**: Sistem monolitik perbankan memiliki 3 jenis konsumen:
  1. Internal Web Backoffice SPA (React).
  2. Mobile Apps (iOS/Android) untuk nasabah.
  3. Sistem Mitra Eksternal B2B (Integrasi via Server-to-Server).
- **Insiden Keamanan**:
  - Token JWT untuk SPA disimpan di `localStorage` nasabah, terjadi kebocoran via serangan Third-Party Dependency XSS.
  - Token B2B tidak memiliki mekanisme auto-revocation terpusat, menyebabkan credentials partner yang bocor tetap aktif selama berhari-hari.
- **Solusi Arsitektur**:
  1. **Dual Guard Routing**:
     - *SPA Guard*: Sanctum Cookie-based Stateful Authentication via `EnsureFrontendRequestsAreStateful`. Tidak ada akses token yang disimpan di browser. Cookie ditandai `SameSite=Strict`, `HttpOnly`, `Secure`.
     - *Mobile Guard*: Sanctum Opaque Token dengan sliding expiration (15 menit) dan hash verification di Redis cluster.
     - *B2B Guard*: Passport Client Credentials Grant dengan asymmetric public/private keys + IP CIDR Whitelist middleware.
  2. **Audit & Revocation Pipeline**:
     - Event Listener pada `TokenCreated` dan `TokenRevoked` mendorong streaming event ke Apache Kafka untuk audit trail SIEM (Splunk).
     - Token lookup caching: Hash token disimpan di Redis dengan TTL mengikuti masa berlaku. Revocation langsung mengeksekusi Redis key deletion (`DEL token:{hash}`), menghilangkan latensi database.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                    ┌───────────────────────────────┐
                    │    PILIHAN ARSITEKTUR AUTH    │
                    └───────────────┬───────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
+───────────────────────────────+               +───────────────────────────────+
|     Stateless Pure JWT        |               |   Hashed DB/Redis Token       |
|    (Passport / Asymmetric)    |               |          (Sanctum)            |
+───────────────────────────────+               +───────────────────────────────+
| [+] Skalabilitas tak terbatas |               | [+] Instant Revocation mudah  |
| [+] Latensi auth 0ms (no DB)  |               | [+] Payload size sangat kecil |
| [-] Sulit di-revoke instan    |               | [-] Bottleneck DB / I/O Redis |
| [-] Header request membengkak |               | [-] Perlu sentralisasi state  |
+───────────────────────────────+               +───────────────────────────────+
```

| Dimensi | Stateful Session (Cookie) | Database Token (Sanctum) | Asymmetric JWT (OAuth2/Passport) |
| :--- | :--- | :--- | :--- |
| **Lookup Latency** | Rendah (Redis `GET` ~0.5ms) | Sedang (DB Query/Indexed ~2-5ms) | Sangat Rendah (CPU Crypto verification ~0.1ms, zero I/O) |
| **Revocation Velocity** | Real-time (Destroy session ID) | Real-time (Delete DB/Redis row) | Kompleks (Perlu Token Blacklist/JTI cache di distributed Redis) |
| **Network Overhead** | Minimal (Hanya Session ID) | Minimal (~64 character token) | Besar (JWT payload signed bisa mencapai 1-2 KB per request) |
| **Infrastruktur** | Redis Cluster Shared Session | Master/Read DB Replica scaling | Distributed Service Mesh compatible |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Timing Attack pada Verifikasi Token atau Webhook Signature
*Penyebab*: Menggunakan operator komparasi string standar `==` atau `===`. Operator ini akan berhenti mengevaluasi karakter pada kegagalan pertama (*early bail-out*), memungkinkan penyerang menebak signature byte per byte berdasarkan selisih waktu respons nanodetik.
*Solusi*: Wajib menggunakan fungsi *constant-time comparison* bawaan PHP:
```php
// SALAH (Rentan Side-Channel Timing Attack)
if ($requestSignature === $calculatedSignature) { ... }

// BENAR
if (! hash_equals($calculatedSignature, $requestSignature)) {
    abort(401, 'Invalid signature.');
}
```

#### 2. Replay Attack pada Webhook / Open API
*Penyebab*: Endpoint webhook publik hanya memverifikasi hash payload tanpa menyertakan dan membatasi komponen timestamp.
*Solusi*: Wajibkan header `X-Timestamp`, verifikasi umur payload, dan simpan *Nonce* ke Redis dengan TTL untuk memastikan satu request ID unik hanya bisa dieksekusi tepat satu kali (*idempotency lock*):
```php
$nonce = $request->header('X-Nonce');
$timestamp = (int) $request->header('X-Timestamp');

if (abs(now()->timestamp - $timestamp) > 300) {
    throw new SecurityException('Payload expired.');
}

if (! Redis::set("nonce:{$nonce}", '1', 'EX', 300, 'NX')) {
    throw new SecurityException('Replay attack detected. Nonce already consumed.');
}
```

#### 3. N+1 Problem pada Policy Evaluation saat Menggunakan Collection Otorisasi
*Penyebab*: Menjalankan authorize di loop controller:
```php
// SALAH: Memicu puluhan query jika relasi policy dimuat secara lazy
$posts->filter(fn($post) => Auth::user()->can('update', $post));
```
*Solusi*: Eager load relasi yang diperlukan oleh policy di level query builder atau gunakan Policy Filter langsung di tingkat database scope query.

---

### 11. Best Practices (Production Checklist)

- [ ] **Hash Algorithm**: Gunakan `Argon2id` sebagai default hasher pada `config/hashing.php` dengan `memory=65536, time=4, threads=1` (sesuai baseline OWASP).
- [ ] **Cookie Security Flags**: Pastikan seluruh session dan token cookie memiliki atribut `Secure = true`, `HttpOnly = true`, `SameSite = 'Strict'` atau `'Lax'`. Larang keras `SameSite = 'None'` kecuali untuk iframe terverifikasi dengan mTLS.
- [ ] **Strict CORS Whitelist**: Hindari penggunaan wildcard `*` pada `config/cors.php` saat `supports_credentials => true`. Wajib daftarkan origin domain secara eksplisit.
- [ ] **Rate Limiting Segregation**: Terapkan rate limiter yang berbeda antara public routes, route login/otentikasi (gunakan rate limit agresif berbasis IP + Email hash), dan authenticated internal routes.
- [ ] **Token Expiration & Pruning**: Jadwalkan command `php artisan sanctum:prune-expired` setiap jam di `routes/console.php` untuk mencegah bloating pada tabel token.
- [ ] **Mass Assignment Protection**: Larang penggunaan `Model::unguard()` di level arsitektur produksi. Gunakan explicit DTO (*Data Transfer Object*) untuk otorisasi perubahan role/clearance.

---

### 12. Hands-on Practice

Buat dan amankan Custom Sanctum Guard dengan dynamic IP-Binding untuk mendeteksi pembajakan token. Folder kerja: `hands-on/m02/`.

#### Langkah 1: Buat Migration Modifikasi Sanctum Token
File: `hands-on/m02/database/migrations/2026_03_30_000001_add_ip_binding_to_sanctum_tokens.php`
```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::table('personal_access_tokens', function (Blueprint $table) {
            $table->string('bound_ip_address', 45)->nullable()->after('token');
            $table->text('user_agent_hash')->nullable()->after('bound_ip_address');
        });
    }

    public function down(): void
    {
        Schema::table('personal_access_tokens', function (Blueprint $table) {
            $table->dropColumn(['bound_ip_address', 'user_agent_hash']);
        });
    }
};
```

#### Langkah 2: Override Sanctum PersonalAccessToken Model
File: `hands-on/m02/app/Models/SecurityPersonalAccessToken.php`
```php
<?php

declare(strict_types=1);

namespace App\Models;

use Laravel\Sanctum\PersonalAccessToken as SanctumToken;

final class SecurityPersonalAccessToken extends SanctumToken
{
    protected $fillable = [
        'name',
        'token',
        'abilities',
        'expires_at',
        'bound_ip_address',
        'user_agent_hash',
    ];
}
```

#### Langkah 3: Implementasikan Middleware Anti-Hijacking
File: `hands-on/m02/app/Http/Middleware/ValidateTokenFingerprint.php`
```php
<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Laravel\Sanctum\TransientToken;
use Symfony\Component\HttpFoundation\Response;

final class ValidateTokenFingerprint
{
    public function handle(Request $request, Closure $next): Response
    {
        $user = $request->user();

        if (! $user || ! $user->currentAccessToken() || $user->currentAccessToken() instanceof TransientToken) {
            return $next($request);
        }

        $token = $user->currentAccessToken();
        $clientIp = $request->ip();
        $userAgentHash = hash('sha256', (string) $request->userAgent());

        // Jika IP tersimpan tidak sama dengan IP requester saat ini -> Potensi Hijacking!
        if ($token->bound_ip_address && $token->bound_ip_address !== $clientIp) {
            // Revoke token secara instan
            $token->delete();

            return response()->json([
                'error' => 'Security violation: Client footprint mismatch. Token revoked.',
            ], Response::HTTP_FORBIDDEN);
        }

        // Verifikasi User Agent
        if ($token->user_agent_hash && ! hash_equals($token->user_agent_hash, $userAgentHash)) {
            $token->delete();

            return response()->json([
                'error' => 'Security violation: Browser environment mutated. Token revoked.',
            ], Response::HTTP_FORBIDDEN);
        }

        return $next($request);
    }
}
```

#### Langkah 4: Registrasi Model pada `AppServiceProvider`
```php
use App\Models\SecurityPersonalAccessToken;
use Laravel\Sanctum\Sanctum;

public function boot(): void
{
    Sanctum::usePersonalAccessTokenModel(SecurityPersonalAccessToken::class);
}
```

---

### 13. Exercise

#### Level Easy
1. Buat middleware `EnsureEmailIsCorporate` yang memeriksa apakah email user yang login berakhiran domain perusahaan tertentu (misal: `@enterprise.com`). Jika tidak, return error 403 Forbidden.

#### Level Medium
1. Buat custom validation rule `StrongPassword` yang mengevaluasi password terhadap database pwned passwords (HAVEIBEENPWNED API menggunakan k-Anonymity model) tanpa membocorkan plain password ke third party.

#### Level Hard
1. Implementasikan distributed rate-limiting berbasis Algoritma Token Bucket di Redis via Lua Script langsung dari Laravel Middleware. Limiter harus membedakan bucket size untuk user berbayar vs user gratisan secara otomatis tanpa latensi serialization PHP.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Security Engineer pada platform Payment Gateway. Sebuah bug ditemukan di mana penyerang melakukan serangan *Race Condition* (*Concurrent HTTP Requests*) pada endpoint penarikan saldo (`/api/v1/wallets/withdraw`). Penyerang mengirimkan 10 request secara paralel tepat pada milidetik yang sama menggunakan token yang sama sehingga otorisasi balance check lolos pada kesepuluh request sebelum data saldo sempat dikurangi oleh database update.

**Tugas Anda**:
1. Rancang arsitektur proteksi di level Laravel Middleware / Policy Layer yang mencegah concurrency attack ini menggunakan teknik *Atomic Redis Lock Token* atau *Conditional Guard Assertion*.
2. Solusi tidak boleh membuat endpoint normal menjadi lambat secara signifikan (overhead maksimal < 15ms).
3. Buat Unit/Feature Test yang menyimulasikan 10 asynchronous concurrent request menggunakan `Http::pool` atau ReactPHP / Guzzle Asynchronous pool untuk membuktikan bahwa hanya 1 transaksi yang berhasil dieksekusi, sedangkan 9 lainnya terhenti dengan status 409 Conflict atau 429 Too Many Requests.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa perbedaan tanggung jawab mendasar antara `Guard` dan `UserProvider` dalam Laravel Authentication?
2. Mengapa Laravel Sanctum menyimpan hash SHA-256 dari token di database, bukan plain-text token yang dikembalikan ke client?
3. Apa perbedaan fungsional antara `SameSite=Strict` dan `SameSite=Lax` pada konfigurasi cookie autentikasi?
4. Mengapa fungsi `hash_equals()` mutlak digunakan dibandingkan operator `===` saat memvalidasi cryptographic signatures?
5. Kapan Anda harus menggunakan Gate biasa vs Policy dalam arsitektur Laravel?

#### B. Pertanyaan Intermediate
1. Bagaimana cara kerja internal metode `EnsureFrontendRequestsAreStateful` pada Laravel Sanctum saat membedakan request dari SPA first-party dan request dari mobile client?
2. Dalam OAuth 2.0 PKCE (*Proof Key for Code Exchange*), ancaman apa yang ditangani oleh parameter `code_challenge` dan `code_verifier`?
3. Mengapa menyimpan access token di `localStorage` pada Single Page Application (SPA) dianggap insecure menurut OWASP, dan bagaimana arsitektur Cookie HttpOnly menyelesaikan hal tersebut?
4. Bagaimana cara menginvalidasi seluruh bearer tokens milik user secara atomik di Laravel Sanctum tanpa menghapus baris session web miliknya?
5. Jelaskan alur eksekusi method `before()` pada Laravel Gate class, dan bagaimana dampaknya jika method tersebut me-return nilai `null` versus `false`.

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Database read/write split Anda mengalami replication lag sebesar 2 detik. Seorang user baru saja mengganti passwordnya melalui web UI, lalu di-redirect ke halaman dashboard. Mengapa user tersebut terkadang tiba-tiba logout otomatis atau mendapatkan error `Unauthenticated` pada request berikutnya? Bagaimana memperbaikinya di konfigurasi Laravel Auth?
2. **Skenario 2**: Sistem B2B Webhook Anda mengirimkan ribuan event finansial per menit ke partner. Partner mengeluhkan bahwa payload tampering terjadi di transit. Rancang struktur header dan format signing HMAC menggunakan Laravel untuk membuktikan data integrity dan non-repudiation!
3. **Skenario 3**: Sebuah microservice Go perlu memvalidasi token yang diterbitkan oleh Laravel Passport tanpa harus melakukan HTTP call atau database query ke server Laravel. Bagaimana arsitektur Passport dikonfigurasi agar service Go tersebut dapat memverifikasi token secara mandiri?

---

### Jawaban Kuis

#### A. Basic
1. `Guard` mengatur logika ekstraksi identitas dari HTTP Request (misal: session cookie, bearer header) dan mempertahankan status autentikasi di memory. `UserProvider` mengatur mekanisme penarikan dan verifikasi kredensial data identitas pengguna dari sistem penyimpanan (Database, Redis, API pihak ketiga).
2. Jika database bocor (SQL Injection atau backup leak), penyerang tidak bisa langsung menggunakan token tersebut untuk menyamar sebagai user, karena token yang valid hanya diketahui oleh client dan tidak dapat direkonstruksi dari hash satu arah.
3. `SameSite=Strict` melarang cookie dikirimkan sama sekali pada cross-site requests (termasuk saat mengklik link biasa dari website luar). `SameSite=Lax` mengizinkan pengiriman cookie pada safe top-level navigations (seperti mengklik link `<a>` biasa) sambil tetap memblokir metode tidak aman seperti POST via cross-site form submission.
4. Karena `hash_equals()` mengeksekusi komparasi dalam waktu konstan (*constant-time*), terlepas dari pada karakter ke berapa ketidakcocokan ditemukan. Operator `===` memutus komparasi pada byte error pertama, membuka celah kebocoran timing information bagi penyerang (*Timing Side-Channel Attack*).
5. Gate ideal untuk otorisasi aksi umum yang tidak terikat pada specific model instance (misal: `access-admin-panel`). Policy digunakan untuk mengorganisasi logika otorisasi seputar model Eloquent tertentu (misal: `PostPolicy` untuk model `Post`).

#### B. Intermediate
1. Sanctum memeriksa header `Referer` atau `Origin` dari incoming request terhadap domain whitelist yang didaftarkan di `config/sanctum.php` (`stateful`). Jika domain cocok, Sanctum mengaktifkan middleware session stateful standar Laravel (menggunakan cookies). Jika tidak cocok, request diperlakukan sebagai stateless API request dan dievaluasi via Bearer token.
2. Mencegah Authorization Code Interception Attack pada *public clients* (mobile apps/SPA) di mana penyerang mencegat Authorization Code via deep-link hijacking. Tanpa memiliki `code_verifier` asli yang sesuai dengan `code_challenge`, kode otorisasi tersebut tidak dapat ditukarkan dengan access token.
3. JavaScript memiliki akses penuh membaca `localStorage`. Jika website rentan terhadap Cross-Site Scripting (XSS), script jahat dapat mencuri token. Dengan `HttpOnly` cookie, browser secara otomatis melarang JavaScript membaca nilai cookie tersebut, sehingga token kebal terhadap pencurian langsung melalui XSS.
4. Jalankan: `$user->tokens()->where('name', '!=', 'web-session')->delete();` atau beri kategori token via model scope, membatasi penghapusan hanya pada record `personal_access_tokens` tanpa menghapus session table/cookie session ID.
5. Jika method `before()` me-return `true` atau `false`, evaluasi Gate langsung berhenti (*early exit*), bypass semua logic policy. Jika me-return `null`, engine akan melanjutkan evaluasi ke method Policy spesifik yang ditargetkan.

#### C. Skenario Produksi
1. **Analisis & Solusi**: Saat user mengubah password, write database mengeksekusi update hash di Primary DB. Request redirect diarahkan ke Replica DB yang belum ter-sinkronisasi karena replication lag (2 detik). `Authenticate` middleware membandingkan session password hash dengan record di replica yang masih versi lama, menyebabkan invalidation mismatch. **Solusi**: Aktifkan opsi `'sticky' => true` pada konfigurasi database `mysql` di `config/database.php` agar koneksi tetap berada di Primary DB segera setelah ada operasi write dalam request lifecycle yang sama.
2. **Arsitektur Solusi Webhook**:
   - Header: `X-Signature: <hmac_hex>`, `X-Timestamp: <unix_epoch>`, `X-Request-Id: <uuid_v4>`.
   - Payload Signature: `hash_hmac('sha256', "{$timestamp}.{$requestId}." . $request->getContent(), $sharedSecret)`.
   - Receiver memverifikasi:
     1. Selisih `abs(now() - timestamp) <= 300` detik.
     2. Cek `$requestId` di Redis cache (mencegah replay attack).
     3. Komparasi `hash_equals(signature, calculatedSignature)`.
3. **Arsitektur Stateless Multi-Service**:
   - Laravel Passport menerbitkan token berformat JWT yang ditandatangani menggunakan RSA Private Key (`storage/oauth-private.key`).
   - Ekspor RSA Public Key (`storage/oauth-public.key`) ke microservice Go.
   - Service Go memvalidasi token JWT secara lokal (mengecek masa berlaku, issuer, audience, dan integritas signature menggunakan Public Key) tanpa perlu melakukan remote HTTP call ataupun akses langsung ke database Laravel.

---

### 16. Summary

- **Separation of Concerns**: Keamanan Laravel bertumpu pada isolasi yang jelas antara **Guard** (pemeriksa asal request) dan **Provider** (pengambil entitas identitas).
- **Zero-Trust Hardening**: Otentikasi modern tidak cukup hanya mengecek eksistensi user; setiap request harus melalui dynamic context validation (IP, Nonce, Time constraints, Environment attributes).
- **Cryptographic Hygiene**: Hindari reinventing primitives. Wajib gunakan `hash_equals()`, Argon2id, signed assertions, dan perlindungan cookie strict.
- **ABAC Over Simple RBAC**: Skalabilitas aplikasi enterprise menuntut pergeseran dari sekadar memeriksa *Role* menjadi evaluasi dinamis terhadap *Attributes* dari Subjek, Objek, dan Lingkungan via Gate & Policy engine.