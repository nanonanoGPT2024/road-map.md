# Bab 05 Module 01: Authentication, Authorization, & Identity Security

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Back-End Engineering / .NET Core Specialization
*   **Kategori:** 02-Programming-Languages
*   **Topik Induk:** ASP.NET Core Architecture & Security Engineering
*   **Modul:** Authentication, Authorization, & Identity Security
*   **Kode Modul:** ASPNET-SEC-0501
*   **Tingkat Kesulitan:** Advanced / Enterprise Grade
*   **Prasyarat:** Pemahaman mendalam tentang ASP.NET Core Middleware Pipeline, Dependency Injection Lifecycle, C# Asynchronous Programming (`async`/`await`), Protokol HTTP/HTTPS, Dasar Kriptografi Simetris dan Asimetris (HMAC, RSA, ECDSA).
*   **Target Framework:** .NET 8.0 / .NET 9.0 LTS

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Menganalisis Internal Middleware Pipeline:** Mengartikulasikan secara presisi bagaimana `AuthenticationMiddleware` dan `AuthorizationMiddleware` berinteraksi dengan `HttpContext`, `IAuthenticationService`, dan `IAuthorizationService`.
2.  **Membangun Sistem Identitas Berbasis Klaim (Claims-Based Identity):** Menata dekonstruksi dan konstruksi `ClaimsPrincipal`, `ClaimsIdentity`, dan `Claim` untuk pemetaan subjek yang aman dan tidak ambigu.
3.  **Mengimplementasikan Mekanisme Token JWT & Validasi Kriptografis:** Mengonfigurasi `JwtBearerHandler` dengan validasi asimetris berbasis JWKS (JSON Web Key Set), mitigasi clock-skew, dan validasi audiens ganda secara manual maupun otomatis.
4.  **Merancang Otorisasi Kompleks Berbasis Kebijakan (Policy-Based) & Sumber Daya (Resource-Based):** Membangun `AuthorizationHandler<TRequirement, TResource>` kustom untuk evaluasi hak akses bersyarat dinamis (ABAC/Attribute-Based Access Control).
5.  **Menerapkan Strategi Revokasi Token Terdistribusi:** Mengintegrasikan penyimpanan terdistribusi (Redis) untuk token blacklisting dan penanganan rotasi Refresh Token dengan deteksi *replay attack*.
6.  **Melakukan Hardening Tingkat Lanjut pada Data Protection API (DPAPI):** Mengonfigurasi persistensi kunci kriptografi ASP.NET Core Data Protection ke penyimpanan eksternal dengan enkripsi *at-rest*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Identitas Adalah Paspor, Otorisasi Adalah Visa

Mental model paling mendasar dalam keamanan ASP.NET Core adalah pemisahan absolut antara **Siapa Anda (Authentication)** dan **Apa yang Boleh Anda Lakukan (Authorization)**.

```
+--------------------------------------------------------------------+
|                         ClaimsPrincipal                            |
|  "Paspor Digital Pengguna"                                         |
|                                                                    |
|  +--------------------------------------------------------------+  |
|  |             ClaimsIdentity (Scheme: Bearer)                  |  |
|  |  - IsAuthenticated: true                                     |  |
|  |  - AuthenticationType: "Bearer"                              |  |
|  |                                                              |  |
|  |  Claims Koleksi:                                             |  |
|  |  +--------------------------------------------------------+  |  |
|  |  | sub: "usr_991823a"                                     |  |  |
|  |  | iss: "https://auth.enterprise.com"                     |  |  |
|  |  | aud: "https://api.enterprise.com"                      |  |  |
|  |  | role: "FinancialAuditor"                               |  |  |
|  |  | tenant_id: "ten_us_east_41"                            |  |  |
|  |  | max_approval_limit: "5000000"                          |  |  |
|  |  +--------------------------------------------------------+  |  |
|  +--------------------------------------------------------------+  |
+--------------------------------------------------------------------+
```

1.  **Authentication (Autentikasi):** Menghasilkan bukti. Middleware autentikasi bertugas memeriksa kredensial (token, cookie, sertifikat mTLS) dan menerjemahkannya menjadi objek `ClaimsPrincipal`. Autentikasi tidak pernah menolak request secara langsung dengan status `403 Forbidden`; ia hanya menjawab: *"Kredensial valid (berikut identitasnya)*" atau *"Kredensial tidak valid/absen (identitas anonim)"*.
2.  **Claims Identity:** Paspor Anda berisi serangkaian pernyataan (*claims*): nama, tanggal lahir, kewarganegaraan. Klaim adalah pasangan key-value yang dipercaya karena diterbitkan oleh entitas berwenang (Issuer). Di ASP.NET Core, satu individu (`ClaimsPrincipal`) bisa memiliki banyak identitas (`ClaimsIdentity`), misalnya identitas dari Active Directory perusahaan sekaligus identitas personal dari GitHub.
3.  **Authorization (Otorisasi):** Menginspeksi visa. Otorisasi berjalan *setelah* autentikasi. Otorisasi mengevaluasi kebijakan (*policy*) terhadap klaim yang ada di `ClaimsPrincipal` dan konteks sumber daya yang diminta (*resource context*). Jika syarat gagal dipenuhi, authorization middleware memutus alur eksekusi dan menghasilkan HTTP `401 Unauthorized` (jika subjek anonim) atau HTTP `403 Forbidden` (jika subjek terautentikasi tetapi tidak berhak).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Permintaan (Request Lifecycle) pada Pipeline Autentikasi & Otorisasi

```
                HTTP Request (Header: Authorization Bearer <token>)
                                        |
                                        v
                     +--------------------------------------+
                     |       UseRouting Middleware          |
                     +--------------------------------------+
                                        |
                                        v
                     +--------------------------------------+
                     |    UseAuthentication Middleware      |
                     +--------------------------------------+
                                        |
            +---------------------------+---------------------------+
            | Memanggil IAuthenticationService.AuthenticateAsync()  |
            v                                                       v
   [Scheme: "Bearer"]                                      [Scheme: "Cookies"]
   JwtBearerHandler membaca token                          CookieAuthenticationHandler
            |                                                       |
   Validasi Signature Kriptografis                                 Dekripsi Data Protection Cookie
   Validasi Issuer, Audience, Lifetime                             Validasi Expiration & Session
            |                                                       |
            +---------------------------+---------------------------+
                                        |
                       Sukses? (ClaimsPrincipal terbentuk)
                                   /        \
                             Ya   /          \  Tidak
                                 v            v
           HttpContext.User = Principal    HttpContext.User = Anonymous (Kosong)
                                 \            /
                                  \          /
                                   v        v
                     +--------------------------------------+
                     |    UseAuthorization Middleware       |
                     +--------------------------------------+
                                        |
               Cek Endpoint Metadata (Memeriksa attribute [Authorize])
                                        |
                    +-------------------+-------------------+
                    | Ada Requirement [Authorize] / Policy? |
                    +-------------------+-------------------+
                             /                     \
                       Ya   /                       \  Tidak
                           v                         v
       Panggil IAuthorizationService.AuthorizeAsync()  Lolos ke Next Middleware / Endpoint
                           |
        +------------------+------------------+
        | Evaluasi Semua Handler Requirement  |
        +------------------+------------------+
                 /                       \
        Sukses? /                         \ Gagal?
               v                           v
     Lanjut ke Endpoint Controller /   HttpContext.User.IsAuthenticated?
     Minimal API Delegate                         /                 \
                                            Ya   /                   \  Tidak
                                                v                     v
                                         HTTP 403 Forbidden    HTTP 401 Unauthorized
```

### Pohon Objek Identitas Keamanan ASP.NET Core

```
HttpContext
 └── User: ClaimsPrincipal
      ├── Identity: IIdentity (tipe: ClaimsIdentity)
      │    ├── IsAuthenticated: bool
      │    ├── AuthenticationType: string ("Bearer", "Identity.Application", dll)
      │    ├── NameClaimType: string
      │    ├── RoleClaimType: string
      │    └── Claims: IEnumerable<Claim>
      │         ├── Claim { Type: "sub", Value: "10928" }
      │         ├── Claim { Type: "email", Value: "admin@corp.com" }
      │         └── Claim { Type: "role", Value: "PlatformAdmin" }
      └── Identities: IEnumerable<ClaimsIdentity> (Mendukung Multi-Identity)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi `AuthenticationMiddleware`

Pada level source-code runtime ASP.NET Core, `AuthenticationMiddleware` beroperasi sangat ramping. Implementasi internalnya dapat dirangkum sebagai berikut:

```csharp
public class AuthenticationMiddleware
{
    private readonly RequestDelegate _next;
    public IAuthenticationSchemeProvider Schemes { get; }

    public AuthenticationMiddleware(RequestDelegate next, IAuthenticationSchemeProvider schemes)
    {
        _next = next;
        Schemes = schemes;
    }

    public async Task Invoke(HttpContext context)
    {
        context.Features.Set<IAuthenticationFeature>(new AuthenticationFeature
        {
            OriginalPath = context.Request.Path,
            OriginalPathBase = context.Request.PathBase
        });

        // Menemukan DefaultAuthenticateScheme (misal: "Bearer")
        var defaultAuthenticate = await Schemes.GetDefaultAuthenticateSchemeAsync();
        if (defaultAuthenticate != null)
        {
            var result = await context.AuthenticateAsync(defaultAuthenticate.Name);
            if (result?.Principal != null)
            {
                context.User = result.Principal;
            }
        }

        await _next(context);
    }
}
```

*Mekanisme Utama:*
*   Middleware ini **tidak pernah** melempar exception ketika autentikasi gagal (token kadaluwarsa, signature salah, header tidak ada). Ia hanya membungkus hasil evaluasi ke dalam `AuthenticateResult.Fail()` atau `AuthenticateResult.NoResult()`.
*   Jika gagal, `context.User` dibiarkan bernilai default (`ClaimsPrincipal` anonim dengan `Identity.IsAuthenticated = false`).
*   Tanggung jawab penolakan diserahkan sepenuhnya ke middleware hilir: `AuthorizationMiddleware`.

### 2. Dekonstruksi Evaluasi Kebijakan (`IAuthorizationService`)

Ketika request mencapai endpoint yang diproteksi `[Authorize(Policy = "RequireAdmin")]`, `AuthorizationMiddleware` memanggil komponen internal:

```csharp
public interface IAuthorizationService
{
    Task<AuthorizationResult> AuthorizeAsync(
        ClaimsPrincipal user, 
        object? resource, 
        IEnumerable<IAuthorizationRequirement> requirements);
        
    Task<AuthorizationResult> AuthorizeAsync(
        ClaimsPrincipal user, 
        object? resource, 
        string policyName);
}
```

*Alur Internal Eksekusi Requirement:*
1.  **Policy Retrieval:** `IAuthorizationPolicyProvider` mengambil konfigurasi kebijakan berdasarkan `policyName`.
2.  **Context Creation:** Dibuat instance `AuthorizationHandlerContext(requirements, user, resource)`.
3.  **Handler Invocation:** Semua implementasi `IAuthorizationHandler` yang terdaftar dalam dependency injection container yang cocok dengan jenis requirement akan dipanggil secara asinkron via `Task.WhenAll`.
4.  **Evaluator Determination:** `IAuthorizationEvaluator` mengevaluasi context. Jika ada **satu saja** handler memanggil `context.Fail()`, otorisasi divonis gagal permanen (short-circuit negatif). Otorisasi dianggap berhasil hanya jika semua requirement telah ditandai `context.Succeed(requirement)` dan tidak ada flag kegagalan eksplisit.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### JWT vs Statefully Encrypted Cookies

| Dimensi | JSON Web Token (JWT / Bearer) | ASP.NET Core Encrypted Cookie |
| :--- | :--- | :--- |
| **Penyimpanan State** | Stateless (Self-contained claims) | Stateful (Session store) atau semi-stateless (Client-side payload) |
| **Validasi Integritas** | Tanda tangan kriptografis (JWS: HMAC / RSA / ECDSA) | Enkripsi + Otentikasi (Authenticated Encryption: AES-CBC-HMAC / AES-GCM via DPAPI) |
| **Vektor Serangan Utama** | Pencurian Token via XSS, Eksfiltrasi LocalStorage | Cross-Site Request Forgery (CSRF), XSS via Cookie non-HttpOnly |
| **Biaya Komputasi** | Tinggi pada verifikasi signature CPU-bound (Asymmetric cryptography) | Rendah hingga Sedang (Dekripsi simetris cepat) |
| **Mekanisme Revokasi** | Kompleks (Perlu blacklist terdistribusi / short-lived token) | Sangat mudah (Hapus tiket dari server session store atau Data Protection) |
| **Konfigurasi CORS** | Tidak terikat batasan cookie cross-site browser | Tunduk pada atribut browser `SameSite` (Lax, Strict, None) |

### Kriptografi Penandatanganan Token: Simetris vs Asimetris

```
Simetris (HS256):
Identity Provider  ---[ Shared Secret: "k3y_s4ng4t_r4h4s14_d4n_p4nj4ng_sek4li!" ]---> Resource API
(Tanda tangani token)                                                      (Verifikasi token)
*Kelemahan: Resource API harus mengetahui secret yang sama persis. Jika Resource API dikompromikan,
penyerang dapat MEMBUAT token palsu dengan otoritas penuh.*

Asimetris (RS256 / ES256):
Identity Provider (Private Key) --- Menerbitkan Token ---> Resource API (Public Key / JWKS)
(Hanya IdP yang bisa sign)                                 (Hanya bisa verifikasi, tidak bisa sign)
*Keuntungan: Arsitektur Zero-Trust. Service API mikro hanya butuh Public Key yang diekspos via JWKS endpoint.*
```

### Clock Skew: Pedang Bermata Dua

Secara default, implementasi `TokenValidationParameters` di ASP.NET Core menambahkan toleransi waktu sebesar **5 menit** (`ClockSkew = TimeSpan.FromMinutes(5)`).
*   **Alasan Historis:** Mengantisipasi desinkronisasi jam antar server fisik yang berbeda NTP pool.
*   **Bahaya di Lingkungan Modern:** Jika sebuah JWT diatur memiliki masa aktif 5 menit, token tersebut secara riil dapat digunakan hingga **10 menit**. Dalam arsitektur microservices modern yang tersinkronisasi via NTP presisi tinggi, nilai ini **wajib** dipangkas menjadi maksimal 5 detik atau `TimeSpan.Zero` untuk mitigasi security window.

### Data Protection API (DPAPI)

Cookie autentikasi ASP.NET Core tidak menggunakan JWT; mereka menggunakan format biner terenkripsi yang diatur oleh **Data Protection API**.
*   Secara default, kunci DPAPI disimpan di folder profil pengguna lokal atau `%LOCALAPPDATA%` dan dienkripsi dengan Windows DPAPI / machine key.
*   **Masalah Fatal di Container / K8s:** Jika container berganti pod atau mengalami restart, kunci lokal hilang. Hasilnya: seluruh pengguna yang memiliki cookie aktif seketika menerima `401 Unauthorized` karena sistem baru tidak memiliki *private key* untuk mendekripsi payload cookie lama. Diperlukan persistensi kunci ke database/Blob Storage dan enkripsi kunci menggunakan Key Vault.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah aplikasi mandiri ASP.NET Core Minimal API yang mengonfigurasi autentikasi JWT Bearer asimetris, validasi ketat, registrasi claim, dan policy otorisasi berjenjang.

```csharp
// Program.cs
using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

// 1. Definisikan Secret & Parameter Validasi Kriptografis
var issuerSecret = "V3ry_Str0ng_S3cr3t_K3y_F0r_HMAC_SHA256_M1n1mum_32_Ch4rs!";
var signingKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(issuerSecret));

// 2. Registrasi Authentication Engine
builder.Services.AddAuthentication(options =>
{
    options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(options =>
{
    options.RequireHttpsMetadata = false; // Set TRUE di production
    options.SaveToken = true;
    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuer = true,
        ValidIssuer = "https://auth.enterprise.internal",
        ValidateAudience = true,
        ValidAudience = "https://api.enterprise.internal",
        ValidateIssuerSigningKey = true,
        IssuerSigningKey = signingKey,
        ValidateLifetime = true,
        ClockSkew = TimeSpan.Zero, // Menghilangkan window toleransi default 5 menit
        RequireExpirationTime = true,
        NameClaimType = ClaimTypes.NameIdentifier,
        RoleClaimType = ClaimTypes.Role
    };
});

// 3. Registrasi Authorization Policies
builder.Services.AddAuthorization(options =>
{
    // Kebijakan Global Fallback: Setiap endpoint tertutup secara default kecuali ditandai [AllowAnonymous]
    options.FallbackPolicy = new AuthorizationPolicyBuilder()
        .RequireAuthenticatedUser()
        .Build();

    // Custom Policy: ABAC Sederhana berdasarkan Claim
    options.AddPolicy("ElevatedRiskOperator", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireRole("SystemOperator");
        policy.RequireClaim("security_clearance_level", "L3", "L4", "L5");
    });
});

var app = builder.Build();

// 4. Integrasi Pipeline Middleware (Urutan sangat krusial!)
app.UseAuthentication();
app.UseAuthorization();

// 5. Endpoints

// Endpoint Publik: Bypass authorization fallback policy via AllowAnonymous
app.MapGet("/api/health", () => Results.Ok(new { Status = "Healthy", Timestamp = DateTime.UtcNow }))
   .AllowAnonymous();

// Endpoint Terproteksi Umum (Membutuhkan user terautentikasi berdasarkan Fallback Policy)
app.MapGet("/api/profile", (ClaimsPrincipal user) =>
{
    var userId = user.FindFirst(ClaimTypes.NameIdentifier)?.Value;
    var roles = user.FindAll(ClaimTypes.Role).Select(r => r.Value).ToList();

    return Results.Ok(new
    {
        Message = "Access Granted",
        SubjectId = userId,
        AssignedRoles = roles
    });
});

// Endpoint Sangat Terbatas: Membutuhkan Policy Spesifik
app.MapPost("/api/system/purge-cache", [Authorize(Policy = "ElevatedRiskOperator")] () =>
{
    return Results.Ok(new { Message = "Cache successfully purged by high-clearance operator." });
});

app.Run();
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Konfigurasi Service (`Program.cs`)

*   **Baris 11–15:** `builder.Services.AddAuthentication(...)`
    Mengikat skema autentikasi default aplikasi ke `Bearer`. Jika controller atau minimal API memanggil `ChallengeAsync()` atau `AuthenticateAsync()` tanpa parameter nama skema, ASP.NET Core otomatis menggunakan skema `JwtBearerDefaults.AuthenticationScheme`.
*   **Baris 16–33:** `.AddJwtBearer(...)`
    Mendaftarkan `JwtBearerHandler`.
    *   `ValidateIssuerSigningKey = true`: Memvalidasi integritas matematis dari token. Header dan payload di-hash ulang menggunakan key publik/rahasia untuk memastikan data tidak dimanipulasi di tengah jalan.
    *   `ClockSkew = TimeSpan.Zero`: **Kritis untuk keamanan**. Menghilangkan toleransi default 300 detik. Token dengan klaim `exp: 1700000000` akan langsung ditolak pada detik `1700000001`.
    *   `NameClaimType` & `RoleClaimType`: Mengarahkan mapping internal objek `ClaimsIdentity`. Secara historis, klaim JWT standar seperti `"sub"` dan `"role"` dapat dipetakan secara otomatis ke URI XML SOAP lama (`http://schemas.xmlsoap.org/...`) oleh library `JwtSecurityTokenHandler`. Konfigurasi ini memastikan kompatibilitas pemetaan identitas modern.
*   **Baris 36–49:** `builder.Services.AddAuthorization(...)`
    *   `options.FallbackPolicy`: Mengubah paradigma arsitektur keamanan API menjadi *Zero-Trust / Whitelist by Default*. Jika developer lupa menambahkan atribut `[Authorize]` pada endpoint baru, endpoint tersebut tetap **terkunci rapat** bagi publik dan membutuhkan autentikasi.
    *   `options.AddPolicy("ElevatedRiskOperator", ...)`: Mendefinisikan authorization policy berbasis multi-kriteria: subjek harus memiliki peran `SystemOperator` **DAN** klaim `security_clearance_level` yang bernilai minimal salah satu dari L3, L4, atau L5.

### Alur Middleware Execution

*   **Baris 54–55:** `app.UseAuthentication()` dieksekusi sebelum `app.UseAuthorization()`.
    *   Jika `UseAuthorization()` dipanggil sebelum `UseAuthentication()`, `HttpContext.User` masih bernilai kosong/anonim saat dievaluasi oleh engine otorisasi. Akibatnya, seluruh request yang membutuhkan proteksi akan selalu ditolak dengan status HTTP 401, meskipun header Authorization membawa bearer token valid.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Multi-Tenant Enterprise B2B FinTech Core

Sebuah platform pemrosesan kredit mikro multi-tenant berskala enterprise melayani ribuan institusi perbankan. Setiap request API masuk mewakili seorang *Loan Officer* yang mencoba mengakses data pinjaman (`LoanApplication`).

**Kebutuhan Sistem:**
1.  **Isolasi Tenant Absolut:** Officer dari Bank X dilarang keras membaca data milik Bank Y (Bahkan jika officer tersebut memiliki role `GlobalSuperAdmin`).
2.  **Fine-Grained Dynamic Authorization (ABAC):** Officer hanya boleh menyetujui pinjaman jika nominal pengajuan (`Amount`) berada di bawah limit wewenang klaim officer (`max_approval_limit`).
3.  **Token Revocation Instan:** Jika seorang officer dinonaktifkan dari sistem HR perbankan, token JWT officer yang bersangkutan harus seketika ditolak di seluruh klaster API, tanpa menunggu masa aktif token habis (`exp` timeout).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi skala industri lengkap dengan Resource-Based Authorization Handler, dynamic evaluation context, dan validasi Distributed Cache Revocation (Redis-backed via IDistributedCache).

### 1. Model Domain & Authorization Requirement

```csharp
// Models/LoanApplication.cs
namespace Enterprise.Security.Domain;

public record LoanApplication(
    Guid Id, 
    string TenantId, 
    decimal Amount, 
    string Currency, 
    string Status, 
    string SubmitterUserId
);

// Security/Requirements/LoanApprovalRequirement.cs
using Microsoft.AspNetCore.Authorization;

namespace Enterprise.Security.Requirements;

public class LoanApprovalRequirement : IAuthorizationRequirement
{
    // Requirement ini bertindak sebagai marker interface untuk operasi Approval
}
```

### 2. Distributed Token Blacklist Store

```csharp
// Security/Services/ITokenRevocationService.cs
namespace Enterprise.Security.Services;

public interface ITokenRevocationService
{
    Task RevokeTokenAsync(string jti, TimeSpan ttl, CancellationToken cancellationToken = default);
    Task<bool> IsTokenRevokedAsync(string jti, CancellationToken cancellationToken = default);
}

// Security/Services/DistributedCacheTokenRevocationService.cs
using Microsoft.Extensions.Caching.Distributed;

namespace Enterprise.Security.Services;

public class DistributedCacheTokenRevocationService : ITokenRevocationService
{
    private readonly IDistributedCache _cache;
    private const string KeyPrefix = "revoked_tokens:";

    public DistributedCacheTokenRevocationService(IDistributedCache cache)
    {
        _cache = cache;
    }

    public async Task RevokeTokenAsync(string jti, TimeSpan ttl, CancellationToken cancellationToken = default)
    {
        var options = new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = ttl
        };

        await _cache.SetStringAsync($"{KeyPrefix}{jti}", "revoked", options, cancellationToken);
    }

    public async Task<bool> IsTokenRevokedAsync(string jti, CancellationToken cancellationToken = default)
    {
        var result = await _cache.GetStringAsync($"{KeyPrefix}{jti}", cancellationToken);
        return result != null;
    }
}
```

### 3. Resource-Based Authorization Handler (Tenant Isolation & Financial Limit)

```csharp
// Security/Handlers/LoanApprovalAuthorizationHandler.cs
using System.Security.Claims;
using Enterprise.Security.Domain;
using Enterprise.Security.Requirements;
using Microsoft.AspNetCore.Authorization;

namespace Enterprise.Security.Handlers;

public class LoanApprovalAuthorizationHandler : AuthorizationHandler<LoanApprovalRequirement, LoanApplication>
{
    private readonly ILogger<LoanApprovalAuthorizationHandler> _logger;

    public LoanApprovalAuthorizationHandler(ILogger<LoanApprovalAuthorizationHandler> logger)
    {
        _logger = logger;
    }

    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        LoanApprovalRequirement requirement,
        LoanApplication resource)
    {
        var user = context.User;

        // 1. Ekstraksi Klaim Identitas FinTech
        var userTenantId = user.FindFirst("tenant_id")?.Value;
        var approvalLimitClaim = user.FindFirst("max_approval_limit")?.Value;
        var userId = user.FindFirst(ClaimTypes.NameIdentifier)?.Value;

        if (string.IsNullOrEmpty(userTenantId) || string.IsNullOrEmpty(approvalLimitClaim) || string.IsNullOrEmpty(userId))
        {
            _logger.LogWarning("Otorisasi gagal: User {UserId} tidak memiliki struktur klaim tenant/limit lengkap.", userId);
            context.Fail(); // Short-circuit kegagalan
            return Task.CompletedTask;
        }

        // 2. Evaluasi Isolasi Multi-Tenant
        if (!string.Equals(userTenantId, resource.TenantId, StringComparison.Ordinal))
        {
            _logger.LogCritical("Pelanggaran Keamanan Tenant: User {UserId} dari Tenant {UserTenant} mencoba mengakses Resource milik Tenant {ResourceTenant}",
                userId, userTenantId, resource.TenantId);
            context.Fail();
            return Task.CompletedTask;
        }

        // 3. Evaluasi Limit Persetujuan Finansial (ABAC Logic)
        if (!decimal.TryParse(approvalLimitClaim, out var maxApprovalLimit))
        {
            _logger.LogError("Format klaim limit approval korup untuk User {UserId}: {RawClaim}", userId, approvalLimitClaim);
            context.Fail();
            return Task.CompletedTask;
        }

        if (resource.Amount > maxApprovalLimit)
        {
            _logger.LogInformation("Otorisasi ditolak: Nominal aplikasi ({Amount}) melampaui limit wewenang User {UserId} ({Limit})",
                resource.Amount, userId, maxApprovalLimit);
            
            // Jangan panggil context.Fail() di sini jika Anda ingin membiarkan handler lain mengevaluasi fallback;
            // tetapi jika limit ini sifatnya absolut, biarkan tanpa context.Succeed().
            return Task.CompletedTask;
        }

        // 4. Evaluasi Self-Approval Anti-Fraud Rule
        if (string.Equals(userId, resource.SubmitterUserId, StringComparison.OrdinalIgnoreCase))
        {
            _logger.LogWarning("Fraud Prevention: User {UserId} dilarang menyetujui aplikasi kredit miliknya sendiri.", userId);
            context.Fail();
            return Task.CompletedTask;
        }

        // Semua kriteria terpenuhi
        context.Succeed(requirement);
        return Task.CompletedTask;
    }
}
```

### 4. Middleware Blacklist Token Validation Interceptor

```csharp
// Security/Middleware/TokenBlacklistMiddleware.cs
using System.IdentityModel.Tokens.Jwt;
using System.Net;
using Enterprise.Security.Services;

namespace Enterprise.Security.Middleware;

public class TokenBlacklistMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<TokenBlacklistMiddleware> _logger;

    public TokenBlacklistMiddleware(RequestDelegate next, ILogger<TokenBlacklistMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, ITokenRevocationService revocationService)
    {
        if (context.User.Identity?.IsAuthenticated == true)
        {
            // Ambil identifier token unik (jti = JWT ID)
            var jti = context.User.FindFirst(JwtRegisteredClaimNames.Jti)?.Value;

            if (!string.IsNullOrEmpty(jti))
            {
                var isRevoked = await revocationService.IsTokenRevokedAsync(jti, context.RequestAborted);
                if (isRevoked)
                {
                    _logger.LogWarning("Percobaan akses dengan token yang sudah dicabut (JTI: {JTI}).", jti);
                    context.Response.StatusCode = (int)HttpStatusCode.Unauthorized;
                    context.Response.ContentType = "application/json";
                    await context.Response.WriteAsync("{\"error\": \"token_revoked\", \"message\": \"The authorization token has been revoked.\"}", context.RequestAborted);
                    return; // Terminasi pipeline
                }
            }
        }

        await _next(context);
    }
}
```

### 5. Komposisi Program & Endpoint Controller

```csharp
// Program.cs
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Enterprise.Security.Domain;
using Enterprise.Security.Handlers;
using Enterprise.Security.Middleware;
using Enterprise.Security.Requirements;
using Enterprise.Security.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

// Registrasi Cache & Infrastructure
builder.Services.AddDistributedMemoryCache(); // Gunakan AddStackExchangeRedisCache() di production
builder.Services.AddSingleton<ITokenRevocationService, DistributedCacheTokenRevocationService>();

// Registrasi Handler Otorisasi Kustom
builder.Services.AddScoped<IAuthorizationHandler, LoanApprovalAuthorizationHandler>();

// Registrasi Authentication
var keyBytes = Encoding.UTF8.GetBytes("SuperSecretFintechSigningKey2026!#CentralBankCompliant");
var signingKey = new SymmetricSecurityKey(keyBytes);

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.RequireHttpsMetadata = true;
        options.SaveToken = true;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = "https://identity.fintech.internal",
            ValidateAudience = true,
            ValidAudience = "https://core.fintech.internal",
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = signingKey,
            ValidateLifetime = true,
            ClockSkew = TimeSpan.Zero
        };
    });

builder.Services.AddAuthorization();

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();
app.UseMiddleware<TokenBlacklistMiddleware>(); // Dieksekusi setelah AuthN untuk membaca context.User

// Endpoint Eksekusi Approval Berbasis Resource
app.MapPost("/api/loans/{id:guid}/approve", async (
    Guid id, 
    ClaimsPrincipal user, 
    IAuthorizationService authService) =>
{
    // Simulasi pengambilan entitas dari Database
    var loanApplication = new LoanApplication(
        Id: id,
        TenantId: "bank_mandiri_prod",
        Amount: 4500000.00m,
        Currency: "IDR",
        Status: "PendingReview",
        SubmitterUserId: "officer_101"
    );

    // Evaluasi Otorisasi Berbasis Resource (Imperative Authorization)
    var authResult = await authService.AuthorizeAsync(
        user, 
        loanApplication, 
        new LoanApprovalRequirement()
    );

    if (!authResult.Succeeded)
    {
        // Gagal lolos ABAC / Multi-Tenant validation
        return Results.Forbid();
    }

    // Mutasi status domain jika lolos
    return Results.Ok(new
    {
        Message = "Loan application successfully approved.",
        LoanId = loanApplication.Id,
        ApprovedBy = user.FindFirst(ClaimTypes.NameIdentifier)?.Value
    });
});

app.Run();
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### RBAC (Role-Based) vs ABAC (Attribute-Based) vs ReBAC (Relationship-Based)

```
                    KOMPLEKSITAS ARSITEKTUR
                              ^
                              |               [ReBAC] (Google Zanzibar, SpiceDB)
                              |               Relasi Graph: User -> MemberOf -> Workspace -> Document
                              |
                              |       [ABAC] (Claims Policy, Resource Handlers)
                              |       Kondisi Kontekstual: Jam kerja, Geolocation, Limit Finansial
                              |
                              | [RBAC]
                              | Pemetaan statis: User in Role ("Admin", "Manager")
                              +--------------------------------------------------------> SKALABILITAS
```

| Tipe Model | Keuntungan | Kerugian | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **RBAC** | Sangat mudah diimplementasikan (`[Authorize(Roles = "Admin")]`), overhead performa rendah. | *Role Explosion* (AdminJkt, AdminSby, AdminApprover), tidak fleksibel terhadap konteks data. | Sistem administrasi internal sederhana, portal CMS. |
| **ABAC** | Fleksibilitas tinggi, keputusan berbasis kombinasi atribut subjek, sumber daya, dan *environment*. | Evaluasi komputasi lebih tinggi, pengujian unit test permutasi matriks logika lebih kompleks. | Domain finansial, rekam medis (HIPAA), perbankan multi-tenant. |
| **ReBAC** | Ideal untuk multi-level ownership hirarkis (akses berbasis kepemilikan folder/organisasi). | Membutuhkan arsitektur *graph data store* khusus, latensi network hop tambahan. | Platform kolaborasi dokumen (Google Docs, Figma, GitHub Organization). |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Race Condition pada Revokasi Refresh Token:**
    *   *Edge Case:* Dua request paralel masuk menggunakan `refresh_token` yang sama persis dalam pecahan milidetik yang identik (akibat latency jaringan atau browser retry agresif).
    *   *Bahaya:* Sistem rotasi token mendeteksi ini sebagai *Replay Attack* (karena satu token terpakai dua kali) dan langsung mencabut seluruh rantai token pengguna, mengakibatkan *forced logout* pada pengguna valid.
    *   *Mitigasi:* Gunakan Redis Distributed Lock (`RedLock`) saat mengonsumsi refresh token, atau sediakan *grace period* transien (misal: 15 detik) di mana token lama tetap dianggap valid khusus untuk request yang sedang berjalan berdampingan.
2.  **Inkonsistensi Type Mapping `ClaimTypes`:**
    *   *Edge Case:* JWT Anda memiliki payload `{"role": "Operator"}`. Namun saat dipanggil `user.IsInRole("Operator")`, hasilnya `false`.
    *   *Penyebab:* `JwtSecurityTokenHandler.DefaultInboundClaimTypeMap` secara otomatis memetakan `"role"` menjadi `"http://schemas.microsoft.com/ws/2008/06/identity/claims/role"`.
    *   *Solusi:* Bersihkan mapping default secara eksplisit:
        ```csharp
        JwtSecurityTokenHandler.DefaultInboundClaimTypeMap.Clear();
        ```
        atau gunakan handler modern .NET 8+:
        ```csharp
        JsonWebTokenHandler.DefaultInboundClaimTypeMap.Clear();
        ```
3.  **Beban Memori Akibat String Allocation pada Claims Identik:**
    *   *Edge Case:* 10,000 request bersamaan mengeksekusi pipeline autentikasi. Setiap request membuat string baru untuk klaim role `"PlatformUser"`.
    *   *Mitigasi:* Manfaatkan `ClaimsIdentity` string interning atau implementasikan custom transformation cache jika mengurai klaim kompleks dalam skala *high-throughput*.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Manual Token Parsing di Dalam Business Logic / Controller

*Anti-Pattern:*
```csharp
// SANGAT BURUK: Memvalidasi dan mengekstrak klaim secara manual di controller
[HttpGet("data")]
public IActionResult GetData([FromHeader] string authorization)
{
    var token = authorization.Replace("Bearer ", "");
    var handler = new JwtSecurityTokenHandler();
    var jwt = handler.ReadJwtToken(token); // BAHAYA: Hanya membaca header & payload TANPA VALIDASI SIGNATURE!
    var userId = jwt.Claims.First(c => c.Type == "sub").Value;
    return Ok(userId);
}
```

*Correct Pattern:*
Biarkan `JwtBearerHandler` melakukan validasi kriptografi menyeluruh di pipeline. Inject `ClaimsPrincipal` langsung melalui DI / parameter aksi:
```csharp
[HttpGet("data")]
public IActionResult GetData(ClaimsPrincipal user)
{
    var userId = user.FindFirstValue(ClaimTypes.NameIdentifier);
    if (userId is null) return Unauthorized();
    return Ok(userId);
}
```

### 2. Mengabaikan Verifikasi Issuer & Audience

*Anti-Pattern:*
```csharp
TokenValidationParameters = new TokenValidationParameters
{
    ValidateIssuer = false,   // BAHAYA BESAR: Siapapun dapat mencetak token dari server Auth lain
    ValidateAudience = false, // BAHAYA BESAR: Token untuk API 'Billing' bisa ditembakkan ke API 'NuclearLaunch'
    IssuerSigningKey = myKey
};
```

*Correct Pattern:*
Wajibkan validasi `Issuer` dan `Audience` secara eksplisit pada setiap Resource Server.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Eksternalisasi Data Protection Keys (Kritis untuk Container / Kubernetes):**
    Simpan kunci DPAPI pada Redis terenkripsi atau Azure Blob / AWS S3, dan bungkus (*wrap*) kunci menggunakan master key dari Key Vault:
    ```csharp
    builder.Services.AddDataProtection()
        .PersistKeysToStackExchangeRedis(redisConnectionMultiplexer, "DataProtection-Keys")
        .ProtectKeysWithCertificate(x509Certificate2);
    ```
2.  **Zero-Trust Policy as Default:**
    Gunakan `FallbackPolicy` yang mewajibkan autentikasi di seluruh level aplikasi. Gunakan atribut `[AllowAnonymous]` secara eksplisit hanya pada endpoint yang benar-benar terbuka untuk publik.
3.  **Strict Typing untuk Konvensi Klaim:**
    Hindari penulisan string literal (*magic strings*) untuk nama klaim dan policy.
    ```csharp
    public static class CustomSecurityClaims
    {
        public const string TenantId = "tid";
        public const string ClearanceLevel = "clr_lvl";
        public const string MaxApprovalLimit = "max_limit";
    }
    ```
4.  **Short-Lived Access Tokens:**
    Atur masa aktif Access Token (JWT) sangat pendek (maksimal 5–15 menit). Perpanjangan sesi dilakukan menggunakan Refresh Token yang disimpan aman di HttpOnly, Secure, SameSite Cookie.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Migrasi ke `JsonWebTokenHandler` (.NET 8+)

Secara default, ASP.NET Core lawas menggunakan `JwtSecurityTokenHandler` yang berbasis representasi model berat. .NET 8 mengadopsi `JsonWebTokenHandler` yang beroperasi langsung pada `ReadOnlySpan<byte>` dan memangkas alokasi memori secara signifikan.

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        // Menggunakan engine high-performance token handler
        options.UseSecurityTokenValidators = false; 
    });
```

### 2. Eliminasi Polling JWKS (Caching Public Key Metadata)

Jika memvalidasi token dari Identity Provider eksternal (Auth0, Keycloak, Duende IdentityServer), hindari *network call* pada setiap validasi:
*   `ConfigurationManager<OpenIdConnectConfiguration>` internal ASP.NET Core secara default melakukan *caching* metadata JWKS. Pastikan Anda tidak membuat instance handler secara transien (`AddTransient`) yang dapat merusak mekanisme cache in-memory ini.
*   Set interval *refresh* metadata secara berkala (misal: 24 jam) dengan mekanisme failover jika ada rotasi kunci otomatis (*key rotation rollover*).

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Pemberantasan Eksploitasi Algoritma "none" (Algorithm Confusion Mitigation):**
    Pastikan `TokenValidationParameters.ValidAlgorithms` dikunci secara eksplisit ke algoritma yang disepakati (misal: `SecurityAlgorithms.HmacSha256` atau `SecurityAlgorithms.RsaSha256`). Ini mencegah penyerang mengirim token dengan header `{"alg": "none"}` yang dapat mematikan verifikasi integritas pada pustaka yang rentan.
2.  **Mitigasi XSS pada Token Storage:**
    Jangan pernah menyimpan JWT di `localStorage` atau `sessionStorage` browser. Jika aplikasi berupa Single Page Application (SPA), terapkan pola **BFF (Backend-For-Frontend)** menggunakan `Yarp.ReverseProxy`. Browser hanya memegang HttpOnly, Secure, SameSite Encrypted Cookie; token Bearer sesungguhnya dikelola dan disuntikkan secara aman oleh layer server BFF.
3.  **Strict Transport Security (HSTS):**
    Token Bearer yang terkirim melalui HTTP polos (cleartext) rentan terhadap pembajakan (sniffing) jaringan:
    ```csharp
    app.UseHsts();
    app.UseHttpsRedirection();
    ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Sistem otentikasi wajib memiliki audit trail yang lengkap tanpa membocorkan materi kredensial sensitif.

### Konfigurasi Event-Driven Logging pada `JwtBearerEvents`

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Events = new JwtBearerEvents
        {
            OnAuthenticationFailed = context =>
            {
                var logger = context.HttpContext.RequestServices
                    .GetRequiredService<ILoggerFactory>()
                    .CreateLogger("Security.Authentication");

                logger.LogError(context.Exception, "Autentikasi Token Gagal dari IP {RemoteIP}. Alasan: {Message}",
                    context.HttpContext.Connection.RemoteIpAddress,
                    context.Exception.Message);

                return Task.CompletedTask;
            },
            OnTokenValidated = context =>
            {
                var logger = context.HttpContext.RequestServices
                    .GetRequiredService<ILoggerFactory>()
                    .CreateLogger("Security.Authentication");

                var userId = context.Principal?.FindFirst(ClaimTypes.NameIdentifier)?.Value;
                logger.LogInformation("Token Berhasil Divalidasi untuk Subjek: {UserId}", userId);

                return Task.CompletedTask;
            },
            OnChallenge = context =>
            {
                var logger = context.HttpContext.RequestServices
                    .GetRequiredService<ILoggerFactory>()
                    .CreateLogger("Security.Authorization");

                logger.LogWarning("Otorisasi Terputus (Challenge Dipicu): Error: {Error}, Deskripsi: {ErrorDescription}",
                    context.Error,
                    context.ErrorDescription);

                return Task.CompletedTask;
            }
        };
    });
```

*Aturan Audit Log Finansial:* **DILARANG KERAS** melakukan logging terhadap raw JWT bearer token atau raw refresh token di server log (`ILogger`), APM (Elastic APM, Datadog), maupun console stdout. Hanya log metadata token (seperti JTI, Issuer, Subject ID, Timestamp).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+---------------------------------------------------------------------------------------------------+
|                           ASP.NET CORE SECURITY PIPELINE CHEAT SHEET                             |
+---------------------------------------------------------------------------------------------------+
| REGISTRASI PIPELINE (WAJIB URUT):                                                                 |
|   app.UseRouting();                                                                               |
|   app.UseAuthentication(); // 1. Isi HttpContext.User                                             |
|   app.UseAuthorization();  // 2. Evaluasi Kebijakan terhadap User                                 |
|   app.MapControllers();                                                                           |
+---------------------------------------------------------------------------------------------------+
| KUNCI VALIDASI TOKEN KRITIS (TokenValidationParameters):                                         |
|   ValidateIssuer = true         -> Mencegah spoofing IDP                                          |
|   ValidateAudience = true       -> Mencegah token reuse antar sistem berbeda                      |
|   ValidateLifetime = true       -> Memeriksa klaim exp & nbf                                      |
|   ClockSkew = TimeSpan.Zero     -> Menghapus toleransi 5 menit default                            |
|   IssuerSigningKey = [Key]      -> Memverifikasi signature matematis                              |
+---------------------------------------------------------------------------------------------------+
| MODEL OTORISASI:                                                                                  |
|   Simple Role       -> [Authorize(Roles = "Admin")]                                               |
|   Declarative Policy-> [Authorize(Policy = "MustBePermanentEmployee")]                            |
|   Imperative/ABAC   -> await _authService.AuthorizeAsync(User, resource, new CustomRequirement())|
+---------------------------------------------------------------------------------------------------+
| DIAGNOSA KODE STATUS HTTP:                                                                        |
|   HTTP 401 Unauthorized -> Pengguna tidak terautentikasi (Token hilang, invalid, kadaluwarsa)     |
|   HTTP 403 Forbidden    -> Pengguna terautentikasi, namun klaim/hak akses ditolak oleh Policy     |
+---------------------------------------------------------------------------------------------------+
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1.  **Apa perbedaan mendasar antara respons kode status HTTP 401 Unauthorized dan HTTP 403 Forbidden di ASP.NET Core?**
    *   *Jawaban:* `401 Unauthorized` menandakan bahwa identitas pengguna belum divalidasi atau kredensial yang diberikan tidak valid (masalah Autentikasi). Sedangkan `403 Forbidden` menandakan bahwa server telah mengenali siapa pengguna tersebut (`HttpContext.User.Identity.IsAuthenticated == true`), namun pengguna tidak memiliki hak akses/wewenang yang disyaratkan untuk mengakses sumber daya yang diminta (masalah Otorisasi).
2.  **Apa fungsi dari `ClockSkew` pada `TokenValidationParameters` dan mengapa nilai default-nya dapat menjadi celah keamanan pada sistem yang membutuhkan presisi tinggi?**
    *   *Jawaban:* `ClockSkew` adalah batas toleransi perbedaan waktu server antara pembuat token (IdP) dan penerima token (Resource Server). Nilai default-nya adalah 5 menit. Celahnya: jika sebuah token memiliki masa aktif 5 menit, token tersebut secara efektif masih dapat digunakan hingga 10 menit setelah diterbitkan, memberikan penyerang *window of opportunity* lebih panjang untuk mengeksploitasi token yang seharusnya sudah kadaluwarsa.
3.  **Apa yang terjadi jika urutan penulisan middleware di `Program.cs` terbalik menjadi `app.UseAuthorization()` sebelum `app.UseAuthentication()`?**
    *   *Jawaban:* Middleware otorisasi akan mengevaluasi `HttpContext.User` sebelum middleware autentikasi sempat memvalidasi token dan mengisi objek tersebut. Akibatnya, `HttpContext.User` akan selalu dianggap anonim, sehingga setiap endpoint yang diproteksi dengan atribut `[Authorize]` akan selalu menghasilkan status `401 Unauthorized`.
4.  **Di mana sajakah komponen `ClaimsPrincipal`, `ClaimsIdentity`, dan `Claim` diletakkan dalam hierarki objek?**
    *   *Jawaban:* Satu `ClaimsPrincipal` (merepresentasikan subjek/pengguna) memiliki satu atau lebih koleksi `ClaimsIdentity` (merepresentasikan identitas resmi dari berbagai skema penerbit), dan setiap `ClaimsIdentity` memuat sekumpulan atribut data granular individual berupa pasangan key-value yang disebut `Claim`.
5.  **Mengapa algoritma tanda tangan token asimetris (seperti RS256) lebih disukai pada arsitektur microservices enterprise dibandingkan simetris (HS256)?**
    *   *Jawaban:* Karena pada skema asimetris, hanya Identity Provider yang memegang *Private Key* untuk mencetak token, sedangkan puluhan microservice lain hanya memerlukan *Public Key* untuk memverifikasinya. Jika salah satu microservice dibobol, penyerang tidak dapat mencetak token palsu baru. Sebaliknya, pada skema simetris (HS256), *Shared Secret* harus dibagikan ke seluruh microservice; kebocoran di satu service membahayakan integritas otentikasi seluruh ekosistem.

### Soal Tingkat Menengah (Intermediate)

6.  **Bagaimana cara kerja metode `context.Fail()` dalam sebuah `IAuthorizationHandler` jika dibandingkan dengan tidak memanggil metode apapun?**
    *   *Jawaban:* Memanggil `context.Fail()` secara eksplisit menandai evaluasi otorisasi sebagai *gagal permanen* (veto), yang tidak dapat dianulir oleh handler lain yang berhasil (`context.Succeed()`). Sebaliknya, jika handler tidak memanggil `context.Fail()` maupun `context.Succeed()`, handler tersebut hanya bersikap netral; otorisasi masih bisa berhasil jika ada handler lain yang memanggil `context.Succeed(requirement)`.
7.  **Jelaskan mengapa implementasi rotasi Refresh Token membutuhkan arsitektur Distributed Lock saat menangani request konkurensi tinggi!**
    *   *Jawaban:* Tanpa lock terdistribusi, dua request konkuren yang membawa refresh token yang sama dapat diproses secara simultan di instance microservice yang berbeda. Request pertama menukar token dan membatalkan token lama. Request kedua yang tiba berselisih milidetik akan membaca token tersebut sebagai "sudah pernah terpakai", memicu mekanisme deteksi pencurian token (*Reuse Detection*) yang berakibat pada pembatalan seluruh sesi pengguna yang sah secara keliru.
8.  **Bagaimana dampak kegagalan konfigurasi persistensi Data Protection API (DPAPI) pada aplikasi ASP.NET Core yang dideploy ke klaster Kubernetes dengan multi-pod replica?**
    *   *Jawaban:* Setiap pod akan menghasilkan kunci enkripsi DPAPI secara lokal dan terisolasi di memorinya masing-masing. Ketika request berikutnya dari seorang pengguna diarahkan oleh Load Balancer ke pod yang berbeda (pod B) dari pod yang menerbitkan cookie autentikasi (pod A), pod B tidak memiliki kunci untuk mendekripsi cookie tersebut. Akibatnya, pengguna akan mengalami *session drop* (logout mendadak) secara acak setiap kali request berpindah pod.
9.  **Mengapa penggunaan claim `ClaimTypes.Role` sering kali menimbulkan masalah saat berinteraksi dengan payload JSON standar OpenID Connect / OAuth2?**
    *   *Jawaban:* Karena implementasi warisan (legacy) .NET memetakan `ClaimTypes.Role` ke URI SOAP panjang: `http://schemas.microsoft.com/ws/2008/06/identity/claims/role`. Padahal standar OpenID Connect / OIDC hanya menggunakan properti JSON sederhana `"role"` atau `"roles"`. Ketidakcocokan pemetaan ini menyebabkan method `user.IsInRole("Admin")` mengembalikan `false` kecuali mapping internal dinonaktifkan (`DefaultInboundClaimTypeMap.Clear()`).
10. **Dalam skenario Resource-Based Authorization, mengapa evaluasi hak akses tidak bisa diselesaikan hanya menggunakan deklarasi filter atribut `[Authorize(Policy = "...")]` di atas Controller Action?**
    *   *Jawaban:* Atribut filter dievaluasi pada tahap awal pipeline MVC/Routing sebelum parameter model binding dieksekusi atau sebelum data entitas spesifik diambil dari basis data. Pada otorisasi berbasis sumber daya (ABAC), keputusan izin bergantung pada *state* data instans entitas nyata (contoh: mengecek apakah `loan.TenantId == user.TenantId` atau `loan.Amount <= user.Limit`). Oleh karena itu, evaluasi harus dilakukan secara imperatif di dalam method controller/endpoint setelah objek model sumber daya berhasil dimuat.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang Bangun: Secure Multi-Tenant Document Vault dengan Token Revocation Engine

Bangun sebuah Web API ASP.NET Core tingkat produksi mandiri yang mengimplementasikan sistem manajemen dokumen terproteksi ketat dengan batasan arsitektur berikut:

#### Spesifikasi Proyek:
1.  **Arsitektur Autentikasi:**
    *   Gunakan autentikasi JWT Bearer dengan masa aktif token sangat singkat: **60 detik**.
    *   Implementasikan endpoint `/api/auth/token` yang mencetak token dengan klaim: `sub`, `tenant_id`, `clearance_level` (Tier1, Tier2, Tier3), `jti`, dan `exp`.
2.  **Mekanisme Revokasi Terdistribusi:**
    *   Implementasikan endpoint `/api/auth/revoke` yang menerima payload `{ "jti": "string" }` dan mencatat identifier tersebut ke dalam cache terdistribusi (`IDistributedCache`).
    *   Tulis custom middleware `RevocationInterceptorMiddleware` yang memverifikasi apakah `jti` dari token yang masuk telah tercatat di blacklist. Jika ya, putus koneksi dan kembalikan status `401 Unauthorized` dengan pesan JSON standar RFC 7807 (Problem Details).
3.  **Otorisasi Berbasis Sumber Daya (ABAC):**
    *   Buat domain entity `VaultDocument` yang memiliki properti: `Id`, `TenantId`, `RequiredClearanceLevel`, `Classification` (`Public`, `Confidential`, `TopSecret`), dan `OwnerUserId`.
    *   Bangun `DocumentAccessAuthorizationHandler` yang mengimplementasikan aturan:
        *   Pengguna **hanya** dapat mengakses dokumen dari `TenantId` yang identik dengan klaim miliknya.
        *   Akses ke dokumen `Confidential` membutuhkan minimal `clearance_level: Tier2`.
        *   Akses ke dokumen `TopSecret` membutuhkan minimal `clearance_level: Tier3` **DAN** pengguna harus merupakan pemilik asli (`OwnerUserId == sub`).
4.  **Pengujian Ketat:**
    *   Tulis minimal satu suite pengujian integrasi (`WebApplicationFactory<Program>`) menggunakan xUnit yang menguji skenario:
        *   Officer Tenant A mencoba membaca dokumen Tenant B -> Wajib menghasilkan respons `403 Forbidden`.
        *   Token yang belum kadaluwarsa namun telah direvokasi via endpoint revoke -> Wajib menghasilkan respons `401 Unauthorized`.
        *   Permintaan valid dengan clearance cukup -> Menghasilkan respons `200 OK`.