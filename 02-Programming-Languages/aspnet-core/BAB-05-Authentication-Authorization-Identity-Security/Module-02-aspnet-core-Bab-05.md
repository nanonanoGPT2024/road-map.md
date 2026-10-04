# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 05: Authentication, Authorization, Identity & Security**  
**Kategori: 02-Programming-Languages / aspnet-core**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Membedah Internal Pipeline**: Mengurai eksekusi internal `AuthenticationMiddleware`, `IAuthenticationHandlerProvider`, `ClaimsPrincipalFactory`, dan `IAuthorizationEvaluator` hingga level alokasi memori dan siklus hidup request.
2. **Merancang Custom Authorization Engine**: Mengimplementasikan Policy-Based Authorization dinamis dan Resource-Based Authorization berbasis `IAuthorizationRequirement` dan `AuthorizationHandler<TRequirement, TResource>` untuk isolasi data multi-tenant.
3. **Mengembangkan Token Lifecycle Architecture**: Membangun arsitektur token JWT + Refresh Token yang dilengkapi *Cryptographic Family Revocation*, deteksi *Token Replay Attack*, dan blacklist terdistribusi menggunakan Redis.
4. **Mengonfigurasi Enterprise Data Protection API (DPAPI)**: Mengamankan *key ring* ASP.NET Core dengan persistence layer terdistribusi (Redis/Database) dan *Key Encryption at Rest* menggunakan certificate/Azure Key Vault.
5. **Menerapkan Defense-in-Depth Security**: Mengintegrasikan Mutual TLS (mTLS), strict dynamic rate limiting per-claim identity, dan mitigasi serangan cross-cutting (CSRF, timing attacks, claim-tampering).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
* Fundamental ASP.NET Core Middleware Pipeline dan Dependency Injection Container (Service Lifetimes: Transient, Scoped, Singleton).
* Konsep dasar Symmetric & Asymmetric Cryptography (HMAC-SHA256, RSA-2048/4096, ECDSA, X.509 Certificates).
* Pemahaman RFC 7519 (JSON Web Token), RFC 6749 (OAuth 2.0 Framework), dan OpenID Connect Core 1.0.
* Sintaks C# tingkat lanjut: `ValueTask`, `IAsyncEnumerable`, Thread-safe primitives (`ConcurrentDictionary`, `SemaphoreSlim`), Memory optimization (`Span<T>`, `ReadOnlyMemory<T>`).
* Pengalaman operasional dengan Redis Cluster dan Relational Database (PostgreSQL/SQL Server).

---

## 3. Concept & Internal Architecture

### 3.1 Siklus Hidup Authentication Subsystem

ASP.NET Core mengeksekusi autentikasi bukan sebagai *imperative action*, melainkan sebagai *state hydration mechanism* melalui middleware pipeline.

```
Request ---> [AuthenticationMiddleware]
                    |
                    v
          [IAuthenticationService]
                    |
                    v
      [IAuthenticationSchemeProvider] ---> (Mencari Skema Default: "Bearer")
                    |
                    v
        [IAuthenticationHandler] --------> (Mengeksekusi JwtBearerHandler)
                    |
                    +--> Membaca HTTP Header "Authorization: Bearer <token>"
                    +--> Validasi Token (Signature, Issuer, Lifetime via TokenValidationParameters)
                    +--> Rekonstruksi ClaimsIdentity & ClaimsPrincipal
                    |
                    v
         [Set HttpContext.User] <-------- (ClaimsPrincipal berhasil di-assign)
                    |
Request Lanjut ---> [AuthorizationMiddleware]
```

#### Komponen Internal Utama:
* **`IAuthenticationHandler`**: Menangani logika interpretasi skema tertentu (`JwtBearerHandler`, `CookieAuthenticationHandler`). Handler mengeksekusi tiga operasi primitif:
  * `AuthenticateAsync()`: Mengekstrak kredensial dari context dan menghasilkan `AuthenticateResult.Success`, `AuthenticateResult.Fail`, atau `AuthenticateResult.NoResult`.
  * `ChallengeAsync()`: Dipanggil saat unauthenticated user mencoba mengakses resource terproteksi (HTTP 401).
  * `ForbidAsync()`: Dipanggil saat authenticated user tidak memiliki hak akses (HTTP 403).
* **`ClaimsPrincipal` & `ClaimsIdentity`**: Satu `ClaimsPrincipal` dapat memuat banyak `ClaimsIdentity` (contoh: satu identitas dari sertifikat mTLS dan satu identitas dari JWT Bearer).
* **Security Context Flow**: `HttpContext.User` disimpan di thread execution context melalui `AsyncLocal<T>`, namun dalam ASP.NET Core diikat langsung pada instance `DefaultHttpContext` per request.

### 3.2 Authorization Subsystem Internals

Pipeline otorisasi ASP.NET Core menggunakan pattern *Requirements-and-Handlers* terpisah dari routing maupun controller:

```
[AuthorizationMiddleware]
        |
        +--> Membaca Endpoint Metadata: [Authorize(Policy = "TenantAdmin")]
        |
        v
[IAuthorizationPolicyProvider] ---> Mengompilasi AuthorizationPolicy
        |
        v
[IAuthorizationService.AuthorizeAsync(ClaimsPrincipal, Object, Policy)]
        |
        v
[IAuthorizationEvaluator]
        |
        +--> Iterasi seluruh IAuthorizationHandler yang terdaftar di DI
        |    (Menjalankan Handler secara paralel atau sekuensial)
        |
        +--> Mengumpulkan Context: context.HasSucceeded vs context.HasFailed
        |
        v
Hasil: Succeeded -> Lanjut ke Endpoint
       Failed    -> Eksekusi IAuthenticationService.ForbidAsync()
```

Evaluator mengevaluasi flag `AuthorizationHandlerContext`:
1. Jika ada satu handler yang memanggil `context.Fail()`, otorisasi **pasti gagal**, terlepas dari apakah ada handler lain yang memanggil `context.Succeed()`.
2. Jika tidak ada `context.Fail()`, seluruh requirement dalam policy harus memiliki minimal satu handler yang memanggil `context.Succeed(requirement)`.

### 3.3 Data Protection API (DPAPI) Architecture

ASP.NET Core menggunakan Data Protection stack untuk enkripsi stateful (Cookies, Anti-Forgery Tokens, OIDC state parameter, token revocation identifiers).

* **Key Ring Management**: Terdiri dari Master Keys yang memiliki metadata masa aktif (CreationDate, ActivationDate, ExpirationDate).
* **Key Encryption Key (KEK)**: Mengenkripsi kunci data di media penyimpanan agar data protection key tidak tersimpan dalam bentuk *plaintext*.
* **Cryptographic Isolation**: Menggunakan parameter `PurposeString` untuk menurunkan kunci enkripsi turunan (*sub-key derivation* via SP800-108 KDF HMAC-SHA512). Payload yang dienkripsi untuk "Purpose A" tidak akan bisa didekripsi oleh "Purpose B" meskipun menggunakan key ring yang sama.

---

## 4. Why & What

### Mengapa Default Implementation Gagal di Level Enterprise?

1. **Stateless JWT Fallback Pitfall**:
   * *Masalah*: Token JWT murni bersifat stateless. Jika akun karyawan di-suspend atau hak akses dicabut di database, token tetap valid hingga expired (`exp` claim).
   * *Solusi Enterprise*: Hybrid Token Architecture. Validasi signature dan lifetime dilakukan secara stateless di memory CPU, namun penarikan status sesi/revokasi menggunakan layer caching distributed ultra-low latency (Redis cluster) berbasis `jti` (JWT ID) dan Token Family Hash.

2. **Insecure Data Protection Key Storage**:
   * *Masalah*: Secara default, DPAPI menyimpan kunci enkripsi di lokal file system (`%LOCALAPPDATA%\ASP.NET\DataProtection-Keys`). Di Kubernetes cluster dengan multi-replica pod, Pod A tidak bisa mendekripsi session/cookie yang dienkripsi oleh Pod B (menyebabkan *CryptographicException* atau random logouts).
   * *Solusi Enterprise*: Persistent shared Key Ring ke Redis atau Database (PostgreSQL/SQL Server) dengan enkripsi lapisan kedua menggunakan X.509 Certificate atau Cloud KMS (Azure Key Vault / AWS KMS).

3. **RBAC Rigidness**:
   * *Masalah*: Penggunaan `[Authorize(Roles = "Admin")]` membuat kode kaku (*hard-coded*).
   * *Solusi Enterprise*: Policy-Based Authorization berbasis Claims dan dynamic context (ReBAC/ABAC: Attribute-Based Access Control) yang mengevaluasi parameter request (Tenant ID, Resource Ownership, Risk Score, IP Geolocation).

---

## 5. How (Workflow Detail)

### 5.1 Refresh Token Cryptographic Family Revocation Workflow

Untuk mencegah *Token Replay Attack* ketika refresh token dicuri di jaringan publik, terapkan arsitektur *Token Family*:

```
User Action          Client                     Identity API                    Redis / Database
    |                  |                             |                                 |
    |-- Request Login ->                             |                                 |
    |                  |-- Authenticate -----------> |                                 |
    |                  |                             |-- Generate FamilyId (UUID)      |
    |                  |                             |-- Issue Access Token (AT1)      |
    |                  |                             |-- Issue Refresh Token (RT1)     |
    |                  |                             |-- Store: RT1, FamilyId, Valid --+-> Save
    |                  |<- Return (AT1, RT1) --------|                                 |
    |                  |                             |                                 |
    |-- Token Expired ->                             |                                 |
    |                  |-- Refresh (RT1) ----------> |                                 |
    |                  |                             |-- Validasi RT1 di Redis --------+-> Check
    |                  |                             |-- Status: AKTIF                 |
    |                  |                             |-- Invalidate RT1 (Mark Used)    |
    |                  |                             |-- Issue RT2 (Same FamilyId)     |
    |                  |                             |-- Issue AT2                     |
    |                  |<- Return (AT2, RT2) --------|                                 |
    |                  |                             |                                 |
    |-- REPLAY ATTACK -|                             |                                 |
    |   (Attacker RT1) |                             |                                 |
    |                  |-- Refresh (RT1) [REPLAY] -> |                                 |
    |                  |                             |-- Validasi RT1 di Redis --------+-> Check
    |                  |                             |-- Status: SUDAH DIGUNAKAN!      |
    |                  |                             |   (POTENSI BREACH / PENCURIAN)  |
    |                  |                             |-- HANGUSKAN SEMUA TOKEN DALAM --+-> REVOKE ALL!
    |                  |                             |   FAMILY INI (FamilyId)         |
    |                  |<- 401 Unauthorized ---------|                                 |
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Keamanan Gedung Pemerintahan

* **Authentication (Skema & Handler)**: Kartu Tanda Pengenal (KTP). Pemeriksa di gerbang hanya memastikan KTP tersebut asli, dikeluarkan oleh instansi berwenang, belum kadaluwarsa, dan foto sesuai dengan wajah pembawa (Signature & Expiration Valid).
* **ClaimsPrincipal**: Berkas profil yang tertera pada KTP (Nama, Alamat, Tanggal Lahir, Golongan Darah).
* **Authorization Requirement**: Prosedur standar masuk ruangan brankas: "Harus memiliki level izin Top-Secret DAN harus memiliki kunci fisik brankas."
* **Resource-Based Authorization Handler**: Petugas keamanan brankas yang memeriksa: "Anda memang staf Top-Secret (Claims), tapi brankas #402 ini HANYA boleh dibuka jika Anda terdaftar sebagai *Managing Officer* dari berkas #402 ini (Resource Check)."
* **Data Protection API (DPAPI)**: Kotak deposit brankas internal tempat menyimpan blueprint gedung. Kotak ini terkunci dengan Master Key. Jika kunci master hilang, seluruh isi kotak tidak dapat dipulihkan.

### Arsitektur Aliran Enkripsi Data Protection (DPAPI)

```
[ Plaintext Payload (e.g., Auth Session/Cookie) ]
                         |
                         v
       +-----------------------------------+
       |    IDataProtector (CreateProtector)|
       |    Purpose: "Auth.Cookie.v1"       |
       +-----------------------------------+
                         |
                         v [KDF: HKDF-HMAC-SHA512]
         +-------------------------------+
         |   Derived Sub-Key Generation  |
         +-------------------------------+
                         |
       +-----------------+-----------------+
       | Key Ring Source:                  |
       | Distributed Redis Key Store       |
       | (Payload di-protect via KMS/Cert) |
       +-----------------+-----------------+
                         |
                         v [Authenticated Encryption: AES-256-GCM / HMAC]
[ Encrypted Ciphertext + KeyId + IV + Auth Tag ]
```

---

## 7. Code Implementation: Production-Grade

Berikut adalah implementasi clean-architecture untuk **Dynamic Policy & Resource-Based Authorization** dan **Hybrid JWT Authentication Engine** dengan revocation handling.

### 7.1 Resource-Based Authorization Engine

#### Models & Requirements
```csharp
// Domain Model
public sealed record FinancialReport(
    Guid Id, 
    Guid OrganizationId, 
    string ClassificationLevel, // "Public", "Internal", "Confidential", "Restricted"
    decimal Amount, 
    bool IsLocked
);

// Requirement
using Microsoft.AspNetCore.Authorization;

public sealed class DocumentClassificationRequirement : IAuthorizationRequirement
{
    public DocumentClassificationRequirement(string minimumRequiredClassification)
    {
        MinimumRequiredClassification = minimumRequiredClassification;
    }

    public string MinimumRequiredClassification { get; }
}
```

#### Authorization Handler
```csharp
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Logging;

public sealed class FinancialReportAuthorizationHandler 
    : AuthorizationHandler<DocumentClassificationRequirement, FinancialReport>
{
    private readonly ILogger<FinancialReportAuthorizationHandler> _logger;

    public FinancialReportAuthorizationHandler(ILogger<FinancialReportAuthorizationHandler> logger)
    {
        _logger = logger;
    }

    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        DocumentClassificationRequirement requirement,
        FinancialReport resource)
    {
        // 1. Validasi Context User
        if (context.User?.Identity?.IsAuthenticated != true)
        {
            _logger.LogWarning("Evaluasi otorisasi gagal: User unauthenticated.");
            return Task.CompletedTask;
        }

        // 2. Multi-tenant Boundary Check
        var tenantClaim = context.User.FindFirst("tenant_id")?.Value;
        if (!Guid.TryParse(tenantClaim, out var userTenantId) || userTenantId != resource.OrganizationId)
        {
            _logger.LogWarning("Access Denied: Cross-tenant access attempt by User {UserId} to Resource {ResourceId}", 
                context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value, resource.Id);
            
            // Explicit Failure: Pelanggaran batas tenant langsung membatalkan seluruh handler pipeline
            context.Fail(new AuthorizationFailureReason(this, "Cross-tenant access violation."));
            return Task.CompletedTask;
        }

        // 3. Status Resource Check
        if (resource.IsLocked && !context.User.HasClaim("permission", "finance:override_lock"))
        {
            _logger.LogWarning("Access Denied: Resource {ResourceId} terkunci.", resource.Id);
            context.Fail(new AuthorizationFailureReason(this, "Dokumen terkunci untuk audit."));
            return Task.CompletedTask;
        }

        // 4. Clearance Level Evaluation
        var userClearance = context.User.FindFirst("clearance_level")?.Value ?? "Public";
        if (GetClearanceWeight(userClearance) >= GetClearanceWeight(requirement.MinimumRequiredClassification))
        {
            context.Succeed(requirement);
        }
        else
        {
            _logger.LogWarning("Access Denied: Clearance {UserClearance} tidak mencukupi untuk {RequiredClearance}", 
                userClearance, requirement.MinimumRequiredClassification);
        }

        return Task.CompletedTask;
    }

    private static int GetClearanceWeight(string clearance) => clearance switch
    {
        "Public" => 1,
        "Internal" => 2,
        "Confidential" => 3,
        "Restricted" => 4,
        _ => 0
    };
}
```

### 7.2 Distributed Token Blacklist / Revocation Engine

Mekanisme pencegahan penggunaan token yang telah direvokasi menggunakan Redis cache terdistribusi.

```csharp
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.Logging;

public interface ITokenRevocationService
{
    Task RevokeTokenAsync(string jti, TimeSpan lifetime, CancellationToken ct = default);
    Task RevokeFamilyAsync(Guid familyId, TimeSpan lifetime, CancellationToken ct = default);
    Task<bool> IsTokenRevokedAsync(string jti, Guid? familyId, CancellationToken ct = default);
}

public sealed class RedisTokenRevocationService : ITokenRevocationService
{
    private readonly IDistributedCache _cache;
    private readonly ILogger<RedisTokenRevocationService> _logger;

    public RedisTokenRevocationService(IDistributedCache cache, ILogger<RedisTokenRevocationService> logger)
    {
        _cache = cache;
        _logger = logger;
    }

    public async Task RevokeTokenAsync(string jti, TimeSpan lifetime, CancellationToken ct = default)
    {
        var key = $"blacklist:token:{jti}";
        await _cache.SetStringAsync(key, "revoked", new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = lifetime
        }, ct);
        _logger.LogInformation("Token JTI {Jti} telah direvokasi.", jti);
    }

    public async Task RevokeFamilyAsync(Guid familyId, TimeSpan lifetime, CancellationToken ct = default)
    {
        var key = $"blacklist:family:{familyId}";
        await _cache.SetStringAsync(key, "compromised", new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = lifetime
        }, ct);
        _logger.LogCritical("Security Alert: Token Family {FamilyId} diblokir total.", familyId);
    }

    public async Task<bool> IsTokenRevokedAsync(string jti, Guid? familyId, CancellationToken ct = default)
    {
        // 1. Cek individual token blacklist
        var tokenCheck = await _cache.GetStringAsync($"blacklist:token:{jti}", ct);
        if (tokenCheck is not null) return true;

        // 2. Cek Family Blacklist jika familyId disediakan
        if (familyId.HasValue)
        {
            var familyCheck = await _cache.GetStringAsync($"blacklist:family:{familyId.Value}", ct);
            if (familyCheck is not null) return true;
        }

        return false;
    }
}
```

### 7.3 Service Configuration & DPAPI Hardening

Perakitan komponen pada `Program.cs` dengan isolasi Key Ring menggunakan Redis dan konfigurasi event JwtBearer.

```csharp
using System.Security.Cryptography.X509Certificates;
using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.IdentityModel.Tokens;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);

// 1. Setup Redis Connection
var redisConnectionString = builder.Configuration.GetConnectionString("Redis") 
    ?? throw new InvalidOperationException("Redis ConnectionString missing");
var redisConnection = ConnectionMultiplexer.Connect(redisConnectionString);

// 2. Setup Hardened Data Protection API (DPAPI)
builder.Services.AddDataProtection()
    .SetApplicationName("EnterpriseFinCoreApp")
    .PersistKeysToStackExchangeRedis(redisConnection, "DataProtection-Keys")
    .SetDefaultKeyLifetime(TimeSpan.FromDays(90));
    // Pada production: Tambahkan Proteksi Enkripsi Kunci:
    // .ProtectKeysWithCertificate(new X509Certificate2("path-to-cert.pfx", "password"))

// 3. Register Redis Token Revocation Service
builder.Services.AddSingleton<IConnectionMultiplexer>(redisConnection);
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = redisConnectionString;
    options.InstanceName = "FinCoreAuth:";
});
builder.Services.AddSingleton<ITokenRevocationService, RedisTokenRevocationService>();

// 4. Dynamic Authorization Handlers Setup
builder.Services.AddSingleton<IAuthorizationHandler, FinancialReportAuthorizationHandler>();

builder.Services.AddAuthorizationBuilder()
    .AddPolicy("ConfidentialFinancials", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.Requirements.Add(new DocumentClassificationRequirement("Confidential"));
    });

// 5. Configured JWT Bearer with Low-Latency Distributed Blacklist Check
var jwtSecret = builder.Configuration["Jwt:SigningKey"] 
    ?? throw new InvalidOperationException("JWT Key missing");
var signingKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSecret));

builder.Services.AddAuthentication(options =>
{
    options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    options.DefaultChallengeScheme = JwtBearerDefaults.AuthenticationScheme;
})
.AddJwtBearer(options =>
{
    options.RequireHttpsMetadata = true;
    options.SaveToken = false; // Hindari alokasi memori HttpContext yang tidak perlu
    options.TokenValidationParameters = new TokenValidationParameters
    {
        ValidateIssuerSigningKey = true,
        IssuerSigningKey = signingKey,
        ValidateIssuer = true,
        ValidIssuer = "https://identity.fincore.enterprise",
        ValidateAudience = true,
        ValidAudience = "fincore-api",
        ValidateLifetime = true,
        ClockSkew = TimeSpan.FromSeconds(15) // Ketat: Kurangi drift clock default 5 menit
    };

    options.Events = new JwtBearerEvents
    {
        OnTokenValidated = async context =>
        {
            var revocationService = context.HttpContext.RequestServices
                .GetRequiredService<ITokenRevocationService>();
            
            var jti = context.Principal?.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Jti)?.Value;
            var familyClaim = context.Principal?.FindFirst("family_id")?.Value;
            Guid? familyId = Guid.TryParse(familyClaim, out var parsedFamily) ? parsedFamily : null;

            if (string.IsNullOrEmpty(jti) || await revocationService.IsTokenRevokedAsync(jti, familyId, context.HttpContext.RequestAborted))
            {
                context.Fail("Token ini telah dicabut atau invalid.");
            }
        }
    };
});

var app = builder.Build();

app.UseHttpsRedirection();
app.UseAuthentication();
app.UseAuthorization();

// 6. Resource-based Authorization Minimal API Endpoint Execution
app.MapGet("/api/reports/{id:guid}", async (
    Guid id,
    IAuthorizationService authService,
    ClaimsPrincipal user,
    CancellationToken ct) =>
{
    // Mock database fetch
    var report = new FinancialReport(
        Id: id,
        OrganizationId: Guid.Parse("11111111-2222-3333-4444-555555555555"),
        ClassificationLevel: "Confidential",
        Amount: 50_000_000m,
        IsLocked: false
    );

    // Dynamic Resource-Based Authorization Check
    var authResult = await authService.AuthorizeAsync(user, report, new DocumentClassificationRequirement("Confidential"));

    if (!authResult.Succeeded)
    {
        return Results.Forbid();
    }

    return Results.Ok(report);
}).RequireAuthorization();

app.Run();
```

---

## 8. Real World Case Study: Global Multi-Tenant FinTech Core Banking

### Konteks Bisnis & Masalah
Sebuah platform Core Banking melayani 40 mitra bank regional (multi-tenant) dengan 1.500.000 Daily Active Users (DAU).
* **Insiden Keamanan**: Terjadi kebocoran sesi di mana token pengguna dari Tenant A (Bank A) dapat mengakses dokumen pinjaman milik Tenant B (Bank B) akibat implementasi otorisasi berbasis `[Authorize(Roles = "Manager")]` statis yang hanya memeriksa peran tanpa mengevaluasi *resource tenant boundary*.
* **Availability Incident**: Setiap kali container di-restart saat rolling update di Kubernetes, seluruh pengguna ter-logout secara serentak karena instance pod baru men-generate instance DPAPI key yang baru di folder lokal kontainer (menyebabkan HTTP 401 massal).

### Solusi Arsitektur
1. **Migrasi DPAPI ke Distributed Clustered Persistence**:
   * Menyimpan key ring ke Redis Cluster yang di-replicate cross-zone.
   * Enkripsi Key Ring at rest menggunakan Sertifikat Asimetris 4096-bit yang di-inject melalui Kubernetes Secret.
2. **Penerapan Multi-tenant Enforced Authorization Evaluator**:
   * Menolak kompilasi policy tanpa requirement kepemilikan tenant.
   * Membuat `BaseResourceAuthorizationHandler` wajib untuk seluruh entitas database.
3. **Sliding Refresh Token Family dengan Detection Circuit Breaker**:
   * Jika sistem mendeteksi token reuse (Token Replay Attack), sistem secara otomatis mengeksekusi script LUA ke Redis untuk mematikan semua sub-sesi di bawah `family_id` yang sama dalam waktu < 2 milidetik.

### Hasil Metrik
* 0 incident cross-tenant data leakage dalam audit kepatuhan PCI-DSS Level 1.
* Rolling deployment di Kubernetes 100% transparan bagi pengguna aktif (zero authentication dropped sessions).

---

## 9. Trade-offs: Architectural Decision Records (ADR)

| Dimensi | Stateless Pure JWT | Stateful Session / Reference Token | Hybrid JWT + Distributed Revocation (Dipilih) |
| :--- | :--- | :--- | :--- |
| **Latency** | Sangat Rendah (~0ms, CPU crypto memory only). | Tinggi (1 network I/O call ke store per seluruh request). | Sangat Rendah (~0.5ms lookup ke Redis cache in-memory via single key). |
| **Scalability** | Horizontal tak terbatas, zero dependency. | Dibatasi oleh kapasitas IOPS database session. | Sangat tinggi, scale horizontal via Redis read-replicas. |
| **Security (Revocation)** | Sangat Lemah (Harus menunggu token expired alami). | Sangat Kuat (Instant revocation di database/cache). | Sangat Kuat (Instant via Blacklist Check & Family Invalidation). |
| **Payload Size** | Besar (Claims tersimpan dalam base64 header). | Sangat Kecil (Hanya token ID / string opaque). | Menengah (Base64 JWT + Minimal Claim + JTI Guid). |
| **Infra Cost & Complexity** | Zero infrastructure cost. | Butuh session store berkemampuan throughput masif. | Butuh deployment Redis terdistribusi dengan High Availability. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Inconsistent Claims Mapping (`ClaimTypes` vs `JwtRegisteredClaimNames`)
* **Kesalahan**: Token di-generate dengan claim `sub`, namun saat dibaca bernilai `null` di Controller.
* **Akar Masalah**: Secara default, legacy handler ASP.NET Core memetakan `sub` menjadi `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier`.
* **Solusi**:
  ```csharp
  // Matikan default inbound claims mapping sebelum inisialisasi:
  System.IdentityModel.Tokens.Jwt.JwtSecurityTokenHandler.DefaultInboundClaimTypeMap.Clear();
  ```

### 2. Async Deadlock dalam Custom Authorization Handler
* **Kesalahan**: Memanggil async API secara sinkronous menggunakan `.Result` atau `.Wait()` di dalam handler.
* **Akar Masalah**: Thread pool starvation pada throughput tinggi.
* **Solusi**: Ubah seluruh handler mewarisi `AuthorizationHandler<T>` dan implementasikan method `override Task HandleRequirementAsync(...)` murni secara asinkron tanpa *blocking calls*.

### 3. Key Ring Stale Cache pada DPAPI
* **Gejala**: Log aplikasi menampilkan `CryptographicException: The key {GUID} was not found in the key ring.`
* **Akar Masalah**: Pod baru membuat master key baru karena waktu sinkronisasi Redis lambat atau instance tidak sinkron dengan Key Vault.
* **Solusi**: Pastikan TTL Redis key diatur permanen atau minimal 90 hari, dan konfigurasikan `RefreshInterval` pada Data Protection options untuk polling perubahan key ring.

---

## 11. Best Practices (Production Checklist)

- [ ] **Disable Default Claim Mapping**: Panggil `DefaultInboundClaimTypeMap.Clear()` untuk mencegah perubahan otomatis nama claim JWT standar.
- [ ] **Strict Clock Skew**: Set `TokenValidationParameters.ClockSkew` maksimum 15 - 30 detik (default ASP.NET Core adalah 300 detik / 5 menit, terlalu longgar untuk enterprise financial platform).
- [ ] **Protect DPAPI at Rest**: Selalu panggil `.PersistKeysTo...` dikombinasikan dengan `.ProtectKeysWith...` (Certificate / Cloud KMS). Jangan biarkan kunci tersimpan unencrypted.
- [ ] **Fail-Safe Authorization**: Selalu rancang handler otorisasi dengan mentalitas *deny-by-default*. Jika input null atau claim tidak lengkap, langsung kembalikan tanpa memanggil `context.Succeed()`.
- [ ] **Auditing Failure Reasons**: Manfaatkan `context.Fail(new AuthorizationFailureReason(this, "Reason"))` untuk mencatat audit log keamanan secara komprehensif tanpa membocorkan internal exceptions ke response consumer.
- [ ] **Zero Sensitive Data in JWT Claims**: Jangan simpan PII (Nomor KTP/SSN, password hash, credit card) di dalam claim payload karena JWT hanya di-encode (Base64URL), bukan dienkripsi.
- [ ] **Rate-limit Challenge Endpoints**: Lindungi endpoint `/connect/token` atau `/api/auth/login` menggunakan rate-limiter ASP.NET Core (`PartitionedRateLimiter`) berbasis Client IP dan Username untuk mencegah brute force dan credential stuffing.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan di folder workspace: `hands-on/m02/`

### Skenario: Membangun Resilient Resource-based Security Core dengan DPAPI
1. **Inisialisasi Project**:
   ```bash
   mkdir -p hands-on/m02/SecureFinEngine
   cd hands-on/m02/SecureFinEngine
   dotnet new web -f net8.0
   dotnet add package Microsoft.AspNetCore.Authentication.JwtBearer
   dotnet add package Microsoft.AspNetCore.DataProtection.StackExchangeRedis
   dotnet add package Microsoft.Extensions.Caching.StackExchangeRedis
   ```
2. **Setup Local Redis**:
   Jalankan container Redis:
   ```bash
   docker run --name fin-redis -p 6379:6379 -d redis:7-alpine
   ```
3. **Implementasi Komponen**:
   * Buat class `DocumentClassificationRequirement` dan `FinancialReportAuthorizationHandler` seperti pada Bab 7.
   * Pasang integrasi DPAPI ke Redis lokal `localhost:6379`.
   * Implementasikan endpoint `/api/auth/token` yang men-generate valid JWT token berisi claim `tenant_id` dan `clearance_level`.
   * Implementasikan endpoint data terproteksi dengan Resource Authorization check.
4. **Verifikasi**:
   * Jalankan pengujian cross-tenant request via cURL: Pastikan respon mengembalikan `403 Forbidden`.
   * Jalankan pengujian valid token: Respon mengembalikan `200 OK`.
   * Matikan pod/aplikasi, nyalakan kembali: Pastikan token lama dan data protection cookies tetap valid (bukti stateless + distributed DPAPI persistence berjalan sempurna).

---

## 13. Exercise

### Level Easy
Ubah `DocumentClassificationRequirement` agar mendukung multi-clearance level via parameter array (`string[] allowedClearances`), dan sesuaikan handler agar mengizinkan akses jika salah satu clearance cocok.

### Level Medium
Buat sebuah custom `IAuthorizationPolicyProvider` yang mampu membaca policy berformat dinamis seperti `[Authorize(Policy = "MinimumClearance:Confidential")]` secara *on-the-fly* tanpa perlu mendeklarasikan masing-masing policy satu per satu di `Program.cs`.

### Level Hard
Bangun custom `IAuthenticationHandler` bernama `ApiKeyAuthenticationHandler` yang:
1. Membaca header `X-Api-Key`.
2. Menghitung cryptographic hash HMAC-SHA256 dari key tersebut.
3. Mencocokkan nilai hash secara *constant-time comparison* (`CryptographicOperations.FixedTimeEquals`) guna mencegah *side-channel timing attacks*.
4. Menginjeksi `ClaimsPrincipal` dengan skema autentikasi `"ApiKey"`.

---

## 14. Challenge: Zero-Trust Step-Up Authentication Engine

### Skenario Tantangan
Anda ditugaskan mendesain sistem otorisasi di Core Banking Platform untuk endpoint transaksi bernilai tinggi: `/api/transactions/execute-wire-transfer`.

### Kondisi & Kebutuhan Khusus:
1. **Context-Aware Step-Up**:
   * Transaksi di bawah IDR 100.000.000 hanya memerlukan JWT standar dengan claim `scope: transfer`.
   * Transaksi IDR 100.000.000 ke atas mewajibkan **Step-Up Authentication**: Token harus memiliki claim `amr` (Authentication Methods References) bernilai `mfa` DAN masa terbit claim `auth_time` tidak boleh lebih dari 120 detik yang lalu (Fresh Session).
2. **Device Fingerprint Binding**:
   * Token harus terikat secara kriptografis dengan Header `X-Device-Fingerprint`. Jika fingerprint yang dikirimkan saat transfer berbeda dengan claim `device_hash` di token, tolak request secara instan dan picu event revokasi sesi pengguna secara global di Redis.
3. **Non-repudiation Audit**:
   * Setiap evaluasi authorization handler yang gagal pada endpoint ini harus menuliskan structured security log ke stream distributed broker dengan payload yang telah disanitasi.

**Instruksi**: Rancang dan implementasikan struktur requirements, resource payload, authorization handlers, dan registrasi DI tanpa menggunakan third-party identity framework. Buktikan keamanan arsitektur terhadap serangan token hijacking!

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama dari `AuthenticationMiddleware` dalam ASP.NET Core?
   * A. Menolak request yang tidak memiliki permission
   * B. Mengonstruksi `ClaimsPrincipal` dan menaruhnya ke `HttpContext.User` berdasarkan skema terdaftar
   * C. Menghubungi database pengguna setiap kali ada HTTP request masuk
   * D. Mengenkripsi response body secara otomatis

2. Jika dalam sebuah policy terdapat dua `AuthorizationHandler` untuk requirement yang sama, apa yang terjadi jika Handler A memanggil `context.Succeed()` dan Handler B memanggil `context.Fail()`?
   * A. Request diizinkan karena minimal satu handler berhasil
   * B. Exception dilempar karena status ambivalen
   * C. Request ditolak (Forbidden) karena pemanggilan `context.Fail()` bersifat mutlak menggugurkan otorisasi
   * D. Handler yang terakhir terdaftar di DI yang menang

3. Mengapa `ClockSkew` pada `TokenValidationParameters` perlu diatur sekecil mungkin di level produksi?
   * A. Agar token kadaluwarsa lebih lambat
   * B. Untuk meminimalkan celah waktu validitas token setelah waktu `exp` aslinya terlewati
   * C. Untuk mempercepat eksekusi string parsing CPU
   * D. Agar tidak perlu sinkronisasi waktu server NTP

4. Di manakah lokasi default penyimpanan key ring Data Protection API jika tidak dikonfigurasi secara manual?
   * A. In-Memory RAM saja
   * B. File system lokal pengguna sistem operasi server (`%LOCALAPPDATA%` atau `~/.aspnet/DataProtection-Keys`)
   * C. SQL Server default instance
   * D. Docker Volume Shared

5. Apa perbedaan mendasar antara skema `Challenge` dan `Forbid`?
   * A. `Challenge` menghasilkan HTTP 401 (Unauthorized/Unauthenticated); `Forbid` menghasilkan HTTP 403 (Authenticated but Unauthorized)
   * B. `Challenge` untuk cookie; `Forbid` untuk JWT Bearer
   * C. Keduanya menghasilkan output HTTP 403 namun log yang dihasilkan berbeda
   * D. `Challenge` memblokir IP address pengguna; `Forbid` hanya memutus koneksi

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Arsitektur)
6. Manakah konfigurasi penanganan JWT yang paling optimal untuk throughput tinggi dan memory footprint rendah?
   * A. Set `options.SaveToken = true` agar token dapat diakses langsung dari HttpContext
   * B. Set `options.SaveToken = false` dan gunakan `TokenValidationParameters.ValidateTokenReplay = true`
   * C. Set `options.SaveToken = false`, aktifkan strict lifetime validation, dan tangani revokasi melalui Redis distributed cache secara asinkron di event `OnTokenValidated`
   * D. Selalu parse token secara manual di Controller menggunakan `JwtSecurityTokenHandler`

7. Apa konsekuensi dari implementasi `IAuthorizationHandler` sebagai `Transient` service jika handler tersebut mengonsumsi dependency scoped (`DbContext`)?
   * A. Error kompilasi C#
   * B. Runtime captive dependency yang valid, namun Handler akan di-resolve per-evaluasi requirement dan aman selama `IAuthorizationService` di-resolve per request (Scoped)
   * C. Memory leak permanen pada Root DI Provider
   * D. Database connection akan dibagikan ke semua HTTP request lain

8. Mengapa enkripsi payload menggunakan `IDataProtectionProvider` tidak dapat didekripsi jika string `purpose` yang dimasukkan berbeda saat proses `CreateProtector(purpose)`?
   * A. DPAPI menambahkan purpose ke dalam plain text data
   * B. Key Derivation Function (HKDF) menggunakan purpose string sebagai entropy untuk menurunkan sub-key kriptografi yang berbeda secara matematis
   * C. DPAPI membatalkan dekripsi menggunakan exception handling buatan
   * D. Master key terhapus otomatis saat purpose tidak cocok

9. Pada sliding session refresh token, apa tujuan utama membubuhkan parameter `family_id`?
   * A. Mengelompokkan pengguna berdasarkan role yang sama
   * B. Mendeteksi pencurian token; jika sebuah token usang dalam family yang sama digunakan ulang, seluruh rangkaian token dalam family tersebut hangus
   * C. Mengurangi alokasi memory di cluster Redis
   * D. Mempermudah query database relasional

10. Mengapa method `CryptographicOperations.FixedTimeEquals` wajib digunakan saat mencocokkan hash API Key dibandingkan operator `==` standar?
    * A. Karena fixed time membatasi eksekusi thread hanya pada 1 core CPU
    * B. Mencegah serangan *Timing Side-Channel Attacks* di mana penyerang bisa menebak karakter byte berdasarkan selisih waktu respon komparasi string
    * C. Mengonversi string langsung menjadi Span tanpa alokasi byte array baru
    * D. Mempercepat performa eksekusi komparasi hingga 10x lipat

---

### Bagian 3: Production Case Study Scenarios

#### Kasus 1: Misteri Kegagalan Otorisasi Cross-Container
* **Skenario**: Sistem Microservices ASP.NET Core berjalan di atas Kubernetes. Aplikasi memproteksi cookie auth dan antiforgery token. Pengguna melaporkan bahwa mereka acak mengalami HTTP 400 (Antiforgery failure) atau terlempar ke halaman login saat navigasi halaman, terutama ketika Kubernetes melakukan autoscaling dari 3 pod menjadi 10 pod.
* **Pertanyaan**: Jelaskan akar penyebab masalah internal arsitekturnya, dan tuliskan kode perbaikannya pada konfigurasi `IServiceCollection`!

#### Kasus 2: Degradasi Performa Akibat Excessive Auth Event Lookup
* **Skenario**: Sebuah API dengan traffic 25.000 RPS menggunakan `OnTokenValidated` di `JwtBearerEvents` untuk memeriksa status banned user langsung ke PostgreSQL Database via `DbContext`. Terjadi lonjakan response time dari 15ms menjadi 3500ms, diiringi kehabisan Database Connection Pool (Npgsql pool exhaustion).
* **Pertanyaan**: Identifikasi titik kegagalan arsitektural di atas dan susun solusi perbaikan multi-tier caching untuk mengembalikan latency ke < 5ms tanpa mengorbankan keamanan real-time revocation!

#### Kasus 3: Celah Keamanan Inbound Claim Tampering
* **Skenario**: Seorang penyerang berhasil memalsukan JWT dari Identity Provider pihak ketiga yang tidak dipercaya, namun signature validation berhasil dilewati di environment testing karena developer menggunakan flag:
```csharp
TokenValidationParameters = new TokenValidationParameters {
    ValidateIssuerSigningKey = false,
    ValidateAudience = false
};
```
Ketika developer membetulkan flag tersebut di production, aplikasi tetap kebobolan karena attacker menggunakan token valid dari Identity Provider lain (Public Provider) yang juga menerbitkan claim `sub: "12345"`.
* **Pertanyaan**: Mengapa hal tersebut bisa terjadi meskipun signature valid, dan konfigurasi apa yang hilang pada arsitektur validasi token ASP.NET Core?

---

### Kunci Jawaban & Pembahasan Quiz

#### Bagian 1
1. **B** - Middleware mengekstrak kredensial dari header/cookie, memvalidasinya melalui scheme handler, dan menetapkan `ClaimsPrincipal` ke `HttpContext.User`.
2. **C** - `context.Fail()` mengesampingkan semua keberhasilan (`context.Succeed()`). Sekali dipanggil, evaluasi requirement policy dijamin gagal.
3. **B** - Default `ClockSkew` 5 menit memungkinkan token yang sebenarnya sudah expired 4 menit lalu masih dianggap sah. Menurunkannya ke ~15 detik meminimalkan jendela kerentanan.
4. **B** - Lokasi default adalah local storage OS profile user, yang menyebabkan masalah desinkronisasi pada server farm / multi-container pod.
5. **A** - `Challenge` memicu 401 saat sistem tidak mengenal identitas penyeru. `Forbid` memicu 403 saat penyeru dikenali namun tidak memiliki hak istimewa atas data/resource.

#### Bagian 2
6. **C** - Menonaktifkan `SaveToken` mengurangi konsumsi memori per request, strict validation menjaga integritas, dan Redis cache memberikan pengecekan status revocation dengan biaya I/O minimal.
7. **B** - `AuthorizationHandler` scoped/transient aman diinjeksi scoped service selama tidak didaftarkan sebagai `Singleton` pada application root provider.
8. **B** - Sub-key kriptografi diturunkan secara unik berdasarkan purpose parameter melalui HMAC Key Derivation Function. Purpose berbeda menghasilkan kunci dekripsi yang salah, memicu integritas gagal.
9. **B** - Token family mengikat rantai generasi refresh token. Penggunaan ulang token lama mengindikasikan token tersebut telah dicuri dan dieksploitasi oleh penyerang, sehingga seluruh family harus dibatalkan seketika.
10. **B** - Komparasi standar `==` menghentikan pengecekan pada karakter pertama yang tidak cocok (short-circuiting). Hal ini membocorkan pola waktu (*timing leaks*) yang memungkinkan penyerang merekonstruksi hash byte demi byte.

#### Bagian 3 (Kasus Produksi)
* **Solusi Kasus 1**:
  * *Akar Masalah*: Masing-masing Pod container mengisolasi key ring DPAPI di file system ephemeral lokal pod. Pod A tidak dapat mendekripsi cookie/antiforgery yang di-generate Pod B.
  * *Perbaikan*: Persist DPAPI key ring ke storage terdistribusi (Redis / Database) dan lindungi key dengan shared certificate atau Cloud KMS.
    ```csharp
    builder.Services.AddDataProtection()
        .SetApplicationName("SharedBankingSystem")
        .PersistKeysToStackExchangeRedis(redisMultiplexer, "DataProtection-Keys")
        .ProtectKeysWithCertificate(clusterCert);
    ```
* **Solusi Kasus 2**:
  * *Akar Masalah*: Membuka koneksi database relasional per-HTTP request di dalam pipeline otorisasi membunuh connection pool.
  * *Perbaikan*: Terapkan *Tiered Cache*:
    1. L1 Memory Cache lokal (`IMemoryCache`) dengan sliding expiration sangat singkat (5-10 detik) untuk menangani request berulang dari koneksi/user yang sama.
    2. L2 Distributed Cache (`IDistributedCache` / Redis) dengan TTL 60 detik.
    3. Update status banned/revoked melalui mekanisme pub/sub (Redis Pub/Sub) untuk seketika membersihkan cache L1 lokal di seluruh pod jika user diblokir. Database relasional TIDAK BOLEH disentuh secara langsung di pipeline request path.
* **Solusi Kasus 3**:
  * *Akar Masalah*: Aplikasi memvalidasi tanda tangan (*signature*), tetapi gagal mengunci `ValidIssuer` dan `ValidAudience`. Penyerang mendaftarkan diri di Identity Provider publik lain (contoh: Auth0/Firebase gratisan) dan men-generate token valid dengan klaim `sub` yang sama dengan target korban.
  * *Perbaikan*: Wajib mengaktifkan `ValidateIssuer = true`, mendaftarkan *white-list* Issuer tepercaya secara eksplisit (`ValidIssuer`), dan mengaktifkan validasi `ValidAudience = "my-target-api"` agar token dari audiens sistem lain ditolak mentah-mentah.

---

## 16. Summary

Implementasi pengamanan enterprise pada ASP.NET Core menuntut pemisahan tegas antara status identitas (*Authentication*) dan otoritas kontekstual (*Authorization*). 

1. **Authentication Pipeline**: Bekerja sebagai de-serialisasi identitas kriptografis ke dalam `ClaimsPrincipal`. Melalui konfigurasi parameter token yang ketat (`ClockSkew`, `ValidateAudience`, `ValidateIssuer`) dan isolasi data protection terdistribusi, sistem terhindar dari desinkronisasi node dan serangan pemalsuan token.
2. **Hybrid Authorization Engine**: Menjembatani keunggulan efisiensi stateless JWT dengan kekuatan reaktif stateful token revocation list melalui pemanfaatan Redis low-latency validation pada event `OnTokenValidated`.
3. **Resource & Policy-Based Authorization**: Mengeliminasi kerapuhan RBAC statis, memastikan isolasi multi-tenant data tidak dapat ditembus secara cross-boundary, serta mematuhi prinsip *least-privilege* dan *defense-in-depth* di seluruh lapisan aplikasi modern.