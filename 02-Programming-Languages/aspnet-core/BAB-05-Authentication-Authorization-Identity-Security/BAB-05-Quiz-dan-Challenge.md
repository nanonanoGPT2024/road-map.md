# BAB 05: Quiz, Challenge, & Knowledge Check
**Authentication, Authorization, & Identity Security**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Anatomi `ClaimsPrincipal`, `ClaimsIdentity`, dan `Claim`
Jelaskan secara struktural hierarki antara `ClaimsPrincipal`, `ClaimsIdentity`, dan `Claim` dalam ASP.NET Core. Mengapa sebuah `ClaimsPrincipal` dirancang untuk dapat menampung koleksi lebih dari satu `ClaimsIdentity` (`IEnumerable<ClaimsIdentity>`), dan bagaimana runtime menentukan nilai properti boolean `User.Identity.IsAuthenticated` jika terdapat multiple identity dengan status autentikasi yang saling bertolak belakang?

### Soal 1.2: Pemisahan Tanggung Jawab Middleware Pipeline
Dalam pipeline ASP.NET Core, urutan registrasi middleware sangat krusial:
```csharp
app.UseRouting();
app.UseCors();
app.UseAuthentication();
app.UseAuthorization();
app.UseEndpoints(...);
```
Jelaskan secara presisi apa yang dieksekusi oleh runtime di balik layar saat transisi dari `UseAuthentication()` ke `UseAuthorization()`. Apa implikasi teknis dan status kode HTTP yang dihasilkan jika suatu endpoint yang diproteksi `[Authorize]` dieksekusi ketika:
1. `UseAuthentication()` lupa diregistrasikan sebelum `UseAuthorization()`.
2. `UseAuthorization()` dieksekusi sebelum `UseRouting()`.

### Soal 1.3: Mekanisme Proteksi Cookie via ASP.NET Core Data Protection API (DPAPI)
Bagaimana ASP.NET Core Cookie Authentication Handler mengamankan `AuthenticationTicket` sebelum dikirimkan ke client sebagai header `Set-Cookie`? Uraikan siklus enkripsi, penandatanganan (HMAC), peran *Master Key Ring*, dan bagaimana mekanisme rotasi kunci Data Protection memengaruhi validitas cookie yang masih aktif di browser pengguna.

### Soal 1.4: OIDC Authorization Code Flow with PKCE vs Implicit Flow
Mengapa *OAuth 2.0 Implicit Grant Flow* telah sepenuhnya dihentikan (deprecated) dalam standar keamanan modern, dan digantikan oleh *Authorization Code Flow with PKCE* (Proof Key for Code Exchange) untuk aplikasi Single Page Application (SPA) dan Mobile? Jelaskan fungsi matematis dan alur verifikasi antara `code_verifier` dan `code_challenge` dalam mitigasi serangan *Authorization Code Injection*.

### Soal 1.5: Dekonstruksi Role-Based (RBAC) vs Policy/Resource-Based Authorization
Mengapa penggunaan atribut hardcoded seperti `[Authorize(Roles = "Admin,Manager")]` dianggap sebagai *anti-pattern* pada aplikasi enterprise skala besar? Jelaskan arsitektur evaluasi berbasis `IAuthorizationRequirement` dan `AuthorizationHandler<TRequirement>`, serta bagaimana abstraksi ini memisahkan logika perizinan domain bisnis dari metadata identitas pengguna.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Resolusi dan Pemetaan Klaim JWT (`InboundClaimTypeMap`)
Sebuah microservice ASP.NET Core memvalidasi JWT dari Identity Provider (IdP) eksternal. Token memuat klaim `"sub": "usr_9982"` dan `"role": "BillingAdmin"`. Namun, saat controller membaca `User.FindFirst(ClaimTypes.NameIdentifier)` atau menjalankan `User.IsInRole("BillingAdmin")`, nilainya mengembalikan `null` atau `false`. 
1. Mekanisme internal apa di dalam `JwtSecurityTokenHandler` yang menyebabkan mutasi nama klaim ini?
2. Bagaimana cara menonaktifkan perilaku mutasi default tersebut secara global pada ASP.NET Core minimal API / Web API modern?

### Soal 2.2: Diagnostik `SecurityStampValidator` dan Invalidasi Sesi Terdistribusi
Dalam ASP.NET Core Identity, jelaskan cara kerja internal `SecurityStampValidator` dalam mendeteksi perubahan status kredensial pengguna (misal: password di-reset atau permission dicabut). Jika sistem berjalan di balik load balancer multi-server dengan Cookie Authentication default:
1. Mengapa pengguna terkadang masih dapat mengakses resource selama interval waktu tertentu setelah password diubah?
2. Bagaimana parameter `ValidationInterval` bekerja dan apa trade-off performa terhadap I/O database jika interval ini diatur ke `TimeSpan.Zero`?

### Soal 2.3: Analisis Kegagalan DPAPI pada Lingkungan Containerized (Kubernetes)
Sebuah aplikasi ASP.NET Core dideploy ke Kubernetes dengan 4 replika pod. Pengguna melaporkan insiden *intermittent 401 Unauthorized* atau dipaksa login ulang secara acak setiap kali me-refresh browser. Log aplikasi menampilkan pesan:
`System.Security.Cryptography.CryptographicException: The key {guid} was not found in the key ring.`
1. Jelaskan akar masalah (root cause) dari error tersebut terkait penyimpanan kunci ephemeral pada container.
2. Rancang solusi arsitektural enterprise untuk persistensi key ring dan sinkronisasi enkripsi at-rest menggunakan komponen cloud-native / distributed storage.

### Soal 2.4: Perilaku Evaluasi Ganda pada Custom `IAuthorizationHandler`
Diberikan skenario di mana dua buah handler (`BillingHandler` dan `ComplianceHandler`) didaftarkan ke Dependency Injection container untuk memvalidasi requirement yang sama: `ExportReportRequirement`.
Jika `BillingHandler` memanggil `context.Fail()`, namun `ComplianceHandler` berhasil memvalidasi dan memanggil `context.Succeed(requirement)`:
1. Apa keputusan akhir dari `DefaultAuthorizationEvaluator`? Jelaskan aturan prioritas antara `Fail()` eksplisit, `Succeed()`, dan *unhandled requirements*.
2. Kapan sebaiknya sebuah handler mengabaikan context (tidak memanggil `Fail` maupun `Succeed`) versus secara eksplisit memanggil `context.Fail()`?

### Soal 2.5: Bottleneck HTTP 431 / Request Header Too Large dan ITicketStore
Aplikasi enterprise mengalami lonjakan claims (misal: penambahan 50+ assigned groups/tenants pada identitas pengguna). Tiba-tiba reverse proxy (NGINX/Cloudflare) memutus koneksi dengan status `400 Bad Request` atau `431 Request Header Fields Too Large`.
1. Mengapa mitigasi dengan menaikkan buffer limit pada reverse proxy dianggap solusi buruk?
2. Bagaimana pola arsitektur `ITicketStore` (Session Store) pada `CookieAuthenticationOptions` memecahkan masalah ukuran header ini secara tuntas tanpa menghilangkan *state* claim pengguna?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden CPU Saturation & Latency Spikes pada Cluster Validasi JWT
* **Konteks:** Sebuah sistem microservice memproses throughput rata-rata 25.000 RPS. Seluruh request membawa header `Authorization: Bearer <jwt>`. Setelah deployment versi baru yang menambahkan validasi token di setiap downstream service via `JwtBearerHandler`, CPU usage di seluruh node melonjak hingga 100%, disertai lonjakan drastis pada Tail Latency (p99) dan ratusan event socket starvation.
* **Gejala:** Profiler menunjukkan alokasi memori masif pada instansiasi objek cryptographic, deserialisasi JSON berulang, dan latensi outbound HTTPS request berkala ke endpoint `.well-known/openid-configuration` dan `/jwks.json` milik Identity Provider.
* **Pertanyaan Diagnostik:**
  1. Identifikasi celah miskonfigurasi pada `TokenValidationParameters` atau lifecycle `JwtBearerEvents` yang memicu pemanggilan JWKS eksternal secara berlebihan atau kegagalan caching *Signing Keys*.
  2. Bagaimana strategi validasi asinkron (kriptografi lokal vs network round-trip) yang seharusnya diterapkan, dan bagaimana konfigurasi `ConfigurationManager<OpenIdConnectConfiguration>` mengontrol lifecycle HTTP client internalnya?
  3. Desain arsitektur gateway-offloading atau token-exchange pattern yang dapat memitigasi overhead verifikasi kriptografi berulang di setiap hop microservice.

---

### Skenario B: Race Condition pada Refresh Token Rotation (RTR) di Bawah Koneksi Paralel
* **Konteks:** Sistem SPA perbankan menerapkan *Refresh Token Rotation* (RTR) dengan aturan strict: *Setiap refresh token hanya boleh digunakan satu kali. Jika refresh token yang sudah hangus (revoked/used) dikirimkan ulang, sistem menganggap terjadi pencurian token, lalu otomatis membatalkan seluruh token chain dan memaksa logout.*
* **Gejala:** Pengguna jaringan seluler sering terlempar keluar dari aplikasi (forced logout) secara tiba-tiba saat membuka dashboard yang memicu 5 request API paralel secara simultan (misal: fetch profile, fetch notifications, fetch balance, fetch transactions, fetch banners). Token akses telah kedaluwarsa tepat sebelum 5 request dikirim, sehingga kelima request mencoba me-refresh token secara bersamaan menggunakan satu *refresh token* yang sama.
* **Pertanyaan Diagnostik:**
  1. Uraikan secara presisi urutan *race condition* yang terjadi pada database level ketika Request #1 berhasil menukar token, sedangkan Request #2 sampai #5 tiba beberapa milidetik setelahnya dengan token lama yang sudah di-rotasi.
  2. Rancang mekanisme state-concurrency handling (misalnya: *Grace Period / In-Flight Window* vs *Distributed Lock*) pada backend ASP.NET Core untuk membedakan antara *concurrency race condition* yang sah dari browser dengan *malicious token replay attack*.
  3. Buat implementasi algoritma pseudo-code / state machine pada ASP.NET Core Controller/Endpoint untuk menangani grace period tersebut secara aman tanpa membuka celah replay attack window yang terlalu lebar.

---

### Skenario C: Migrasi Arsitektur Otentikasi: BFF Pattern vs Pure Stateless JWT
* **Konteks:** Perusahaan fintech skala global sedang mendesain ulang arsitektur front-end dan otentikasi. Tim Security mewajibkan penghapusan total penyimpanan Access Token dan Refresh Token di *Browser Storage* (`localStorage` / `sessionStorage` / in-memory SPA) guna memitigasi serangan Cross-Site Scripting (XSS) dan supply-chain attacks pada library NPM.
* **Dilema:** Tim Infrastruktur menolak penggunaan *Server-Side Sessions* klasik karena dinilai akan merusak skalabilitas horizontal sistem stateless yang saat ini berjalan mulus di atas Kubernetes cluster dengan jutaan active sessions.
* **Pertanyaan Diagnostik:**
  1. Analisis arsitektur *Backend-For-Frontend* (BFF) menggunakan ASP.NET Core (misal: via YARP - Yet Another Reverse Proxy) untuk memediasi otentikasi: bagaimana pola ini mengubah token eksternal menjadi `SameSite=Strict; HttpOnly; Secure` cookies di browser, sembari tetap meneruskan stateless JWT ke backend microservices?
  2. Evaluasi mendalam trade-off arsitektural dari solusi BFF tersebut terhadap:
     * Kebutuhan distributed state session management.
     * Kerentanan terhadap Cross-Site Request Forgery (CSRF) dan strategi mitigasinya (misal: SameSite cookie vs Anti-forgery header tokens).
     * Kompleksitas operasional CI/CD dan cold-start scaling.

---

## 4. Chapter Challenge

### Tantangan Praktis: Multi-Tenant Policy-Based Authorization Engine with Distributed Revocation

#### Problem Statement
Anda ditugaskan merancang subsistem otentikasi & otorisasi enterprise untuk platform SaaS multi-tenant berbasis ASP.NET Core Web API. Sistem menggunakan skema otentikasi hybrid (JWT Bearer Token), namun memiliki kebutuhan dynamic access control yang sangat ketat: hak akses pengguna terhadap resource tidak bersifat statis di dalam klaim JWT, melainkan bergantung pada kombinasi **Tenant Context**, **Resource Ownership**, **Hierarchical Permissions**, dan status **Instant Revocation** (revocation seketika tanpa menunggu expiry token).

#### Requirements
1. **Dynamic Authorization Handler:**
   * Buat custom authorization requirement `ResourceOperationRequirement` yang menerima parameter `OperationName` (misal: `Read`, `Update`, `Delete`, `Approve`).
   * Implementasikan `ResourceBasedAuthorizationHandler<TResource>` yang memvalidasi apakah user memiliki permission terhadap instance resource tertentu.
   * Aturan otorisasi:
     * `Tenant Isolation`: User dari Tenant A sama sekali tidak boleh mengakses resource milik Tenant B, meskipun memiliki role "SuperAdmin".
     * `Contextual Ownership`: Pemilik resource (`resource.CreatedBy == User.Id`) memiliki izin `Read` dan `Update`.
     * `Delegated Permission`: Jika bukan pemilik, izin operasi dievaluasi dari distributed cache (Redis) berdasarkan hierarki role tenant pengguna.
2. **Real-time Distributed Revocation Check:**
   * Di dalam pipeline otorisasi/otentikasi, implementasikan verifikasi token blacklist / session revocation menggunakan Redis.
   * Jika user telah di-revoke oleh admin (misal: event `UserLockedEvent` atau `PermissionsChangedEvent`), request berikutnya harus langsung menghasilkan HTTP 403/401 dalam waktu `< 50ms`, terlepas dari sisa waktu kedaluwarsa JWT.
3. **Audit Log & Security Metrics:**
   * Setiap kali otorisasi ditolak (`AuthorizationFailure`), sistem harus memancarkan audit event terstruktur (via `ILogger` atau `Activity` OpenTelemetry) yang mencakup: `UserId`, `TenantId`, `ResourceName`, `ResourceId`, `RequiredOperation`, dan `FailureReason` tanpa membocorkan data sensitif.

#### Constraints
* **Zero In-Memory Leak:** Tidak boleh menggunakan in-memory storage statis pada single-node; semua state revocation dan roles cache harus terdistribusi via `IDistributedCache` / Redis abstraction.
* **High Performance Pipeline:** Authorization Handler tidak boleh melakukan *full database table scan*. Pembacaan context permission harus terindeks atau di-cache dengan strategi invalidasi berbasis key.
* **Clean Code:** Gunakan idiomatic ASP.NET Core abstractions (`IAuthorizationHandler`, `IAuthorizationService`, `HttpContextAccessor`, `AuthenticationSchemeOptions`).

#### Expected Output
* Kode implementasi C# lengkap yang memuat:
  1. Definisi model resource (`ITenantResource`), requirement, dan handler otorisasi.
  2. Implementasi middleware / event hook untuk real-time revocation.
  3. Konfigurasi registrasi service di `Program.cs` (`AddAuthorization`, `AddAuthentication`, Cache setup).
  4. Sebuah endpoint Controller / Minimal API yang memperagakan pemanggilan:
     ```csharp
     await _authorizationService.AuthorizeAsync(User, resourceInstance, Operations.Update);
     ```
  5. Format log JSON terstruktur saat terjadi evaluasi authorization success dan failure.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Model hierarki data identitas ASP.NET Core: `Claim` $\to$ `ClaimsIdentity` $\to$ `ClaimsPrincipal`.
- [ ] Perbedaan fundamental antara Authenticate, Challenge, Forbid, dan SignOut pada `IAuthenticationService`.
- [ ] Siklus kerja ASP.NET Core Data Protection API (DPAPI) meliputi Key Derivation, Authenticated Encryption, Key Ring lifecycle, dan rotasi kunci otomatis.
- [ ] Perbedaan implementasi dan lifecycle security antara JWT (Stateless Token) dan Cookie-based Ticket (Stateful/Session-backed).
- [ ] Keterbatasan RBAC dan keunggulan PBAC (*Policy-Based Access Control*) serta ABAC (*Attribute-Based Access Control*).
- [ ] Alur kerja OAuth 2.0 / OIDC spesifikasi modern: Authorization Code Flow dengan PKCE, Token Introspection, dan Refresh Token Rotation.
- [ ] Risiko keamanan web modern pada level protokol: XSS, CSRF, Token Theft, Replay Attack, serta mitigasi via `SameSite`, `HttpOnly`, CORS, dan CSP.
- [ ] Mekanisme kerja `SecurityStamp` pada ASP.NET Core Identity dan interaksinya dengan middleware autentikasi.

### Saya tidak perlu menghafal:
- [ ] Algoritma matematis internal kriptografi simetris/asimetris (misal: rincian operasi permutasi AES-256-GCM atau kurva eliptik ECDSA P-256).
- [ ] Seluruh format field JSON Web Key Set (JWKS) RFC 7517 secara spesifik byte-per-byte.
- [ ] Sintaks boiler-plate ekspresi reguler untuk validasi password strength bawaan Identity Options.
- [ ] Rincian bitwise flags pada implementasi enkripsi internal Windows DPAPI platform-spesifik.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `Authentication` dan `Authorization` pipeline dengan benar tanpa kesalahan urutan (*middleware ordering issue*).
- [ ] Mengimplementasikan `Custom IAuthorizationHandler` dan `IAuthorizationRequirement` untuk skenario otorisasi berbasis resource dinamis.
- [ ] Mengonfigurasi persistensi Data Protection Key Ring ke distributed storage (Redis/Database) dengan enkripsi at-rest (Key Vault/KMS).
- [ ] Melakukan troubleshooting dan perbaikan terhadap issue mapping klaim pada JWT (`JwtSecurityTokenHandler.DefaultInboundClaimTypeMap`).
- [ ] Mengimplementasikan pola arsitektur `ITicketStore` untuk memindahkan beban payload cookie berukuran besar ke distributed cache.
- [ ] Mengamankan SPA/Mobile client dengan menerapkan alur token refresh yang terlindungi dari race condition dan serangan token replay.
- [ ] Mendiagnostik error autentikasi dan otorisasi menggunakan audit log terstruktur serta traces OpenTelemetry.