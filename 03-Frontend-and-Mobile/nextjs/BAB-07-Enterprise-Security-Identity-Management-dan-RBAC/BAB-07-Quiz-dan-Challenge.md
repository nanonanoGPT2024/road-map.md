# BAB 07: Quiz, Challenge, & Knowledge Check
**Enterprise Security, Identity Management, & RBAC**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Batas Keamanan (Security Boundary) antara Server Component dan Client Component:**
   Jelaskan secara mendalam mengapa pemisahan eksekusi antara Server Components (RSC) dan Client Components bukan sekadar optimasi performa, melainkan batas isolasi keamanan (*security isolation boundary*). Bagaimana mekanisme Webpack/Turbopack melakukan *dead-code elimination* untuk mencegah runtime secrets (seperti private keys atau database connection strings) bocor ke client bundle, dan dalam kondisi apa kebocoran (*data leakage*) tetap dapat terjadi melalui Client Component props?

2. **Mitigasi CSRF pada Server Actions vs Route Handlers:**
   Next.js mengimplementasikan proteksi Cross-Site Request Forgery (CSRF) secara native pada Server Actions menggunakan perbandingan header `Host`/`X-Forwarded-Host` dan `Origin`. Mengapa proteksi bawaan ini tidak otomatis berlaku untuk kustom Route Handlers (`app/api/.../route.ts`), dan langkah arsitektural apa yang wajib diimplementasikan untuk mengamankan Route Handlers yang menerima mutasi data (`POST`, `PUT`, `DELETE`) dari serangan CSRF?

3. **Anatomi Cookie Flags dalam Konteks Identity Management:**
   Analisis perbedaan mendasar antara implementasi token otentikasi di `localStorage` vs `httpOnly`, `Secure`, `SameSite=Strict`/`Lax` cookies dalam arsitektur Next.js. Mengapa penggunaan `SameSite=Strict` dapat merusak alur redirect callback pada protokol federasi identitas pihak ketiga (seperti OAuth2/OIDC dengan Google atau Okta), dan bagaimana strategi mitigasi transisi state (`SameSite=Lax` vs temporal cookies) diterapkan secara aman?

4. **Defense-in-Depth: Data Access Layer (DAL) vs Middleware Authorization:**
   Mengapa mengandalkan Next.js Edge Middleware (`middleware.ts`) sebagai satu-satunya *gatekeeper* otorisasi (RBAC) dikategorikan sebagai anti-pattern fatal dalam arsitektur enterprise? Jelaskan konsep *Defense-in-Depth* dan bagaimana Data Access Layer (DAL) yang beroperasi langsung di Server Components / Server Actions menjadi *single source of truth* untuk evaluasi hak akses data.

5. **Trade-off Arsitektur Sesi: Stateless (JWT) vs Stateful (Database Sessions):**
   Bandingkan arsitektur session management menggunakan Stateless Cryptographic Tokens (JWT) dengan Stateful Database/Redis Sessions pada aplikasi Next.js enterprise yang berjalan di Edge/Serverless runtime. Evaluasi dampaknya terhadap:
   * Mekanisme pembatalan sesi instan (*instant revocation* / *kill-switch*),
   * Beban latensi jaringan (I/O overhead) pada Edge Middleware,
   * Skalabilitas horizontal saat terjadi lonjakan trafik masif (*traffic burst*).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Siklus Hidup Token Refresh pada Server Components (Asynchronous Streaming Limitation):**
   Di Next.js App Router, Server Components bersifat *read-only* terhadap respons HTTP stream dan tidak memiliki kemampuan untuk memanggil `cookies().set()` secara langsung untuk memutasi header `Set-Cookie`. Jika sebuah *Access Token* kadaluarsa saat Server Component sedang merender sub-tree paralel, jelaskan alur arsitektur yang benar untuk melakukan silent token refresh tanpa memicu kegagalan render atau membocorkan token yang belum diperbarui ke sisi klien!

2. **Debugging JWKS Caching dan Cold Starts di Edge Middleware:**
   Saat memvalidasi JWT yang ditandatangani secara asimetris (misal: RS256/ES256) di Edge Middleware menggunakan Remote JSON Web Key Set (JWKS), Anda mendapati peningkatan tajam pada P99 latency dan insiden `FetchError: Connection timed out` saat lonjakan instance cold-start di Edge Runtime. Bagaimana mekanisme internal *key caching* dan *rate limiting* JWKS client bekerja di Edge, dan bagaimana konfigurasi in-memory cache/stale-while-revalidate yang tepat untuk mengatasi bottleneck ini?

3. **Dynamic CSP (Content Security Policy) dengan Nonce pada Server Component Tree:**
   Next.js mendukung injeksi CSP menggunakan kriptografi *cryptographic nonce* per-request untuk memblokir eksploitasi Cross-Site Scripting (XSS). Uraikan secara teknis bagaimana sebuah nonce digenerate di Edge Middleware, diteruskan melalui internal request headers, disinkronisasi ke dalam runtime React Server DOM, dan diinjeksikan secara otomatis ke semua inline script tanpa menyebabkan *hydration mismatch* antara server dan client bundle!

4. **Eksploitasi Direct Invocation pada Server Actions IDs (IDOR/Privilege Escalation):**
   Server Actions diekspos melalui endpoint POST HTTP internal dengan header `Next-Action` yang merujuk pada hash ID terenkripsi dari action tersebut. Bagaimana penyerang dapat memanfaatkan direct invocation terhadap hash ID ini untuk memotong validasi UI-level, dan bagaimana Anda mendesain middleware/higher-order function (Action Wrapper) yang membungkus skema validasi Zod dan otorisasi sesi secara mutlak sebelum payload action dide-serialize dan dieksekusi?

5. **Cross-Origin Credential Leakage pada Edge CORS Engine:**
   Diberikan sebuah Route Handler yang harus mendukung request lintas domain dari subdomain internal dan third-party integration. Mengapa konfigurasi `Access-Control-Allow-Origin: *` gagal saat request menyertakan `credentials: 'include'`, dan bagaimana kerentanan fatal dapat muncul jika server secara naif memantulkan kembali header `Origin` dari incoming request (`Access-Control-Allow-Origin: req.headers.get('origin')`) tanpa validasi whitelist yang ketat (*origin reflection vulnerability*)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Global Token Invalidation Failure pada IdP Compromise
Sebuah enterprise fintech mengalami kompromi kredensial pada server Identity Provider (IdP) sentral mereka. Tim Security merilis sinyal global untuk mencabut (*revoke*) seluruh sesi aktif yang mempengaruhi 2 juta pengguna. Aplikasi Next.js Anda menggunakan arsitektur hybrid: JWT stateless berdurasi 1 jam diverifikasi di Edge Middleware untuk routing statis, sementara Data Access Layer memvalidasi token terhadap cache Redis cluster terdistribusi.

Namun, pasca-pencabutan di IdP, Edge Middleware tetap meloloskan ribuan request penyerang selama 45 menit berikutnya karena caching lokal token di edge runtime, sementara request yang mencapai DAL menyebabkan thundering herd problem ke Redis cluster hingga CPU mencapai 100%, mengakibatkan *cascading failure* ke seluruh database backend.

* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi secara presisi kelemahan arsitektural yang menyebabkan Edge Middleware gagal mendeteksi pencabutan token instan meskipun IdP telah memicu event pembatalan.
  2. Rancang arsitektur sinkronisasi *Edge-to-Origin Revocation List* yang efisien (misalnya via Edge Config, Redis Pub/Sub, atau Upstash Global Read Replicas) dengan latensi propagasi di bawah 5 detik secara global tanpa menghancurkan performa middleware.
  3. Bagaimana strategi mitigasi *thundering herd* pada layer DAL saat memvalidasi session revocation secara massal tanpa menyebabkan database backend exhaustion?

### Skenario B: Race Condition pada Concurrency Refresh Token Family Rotation
Aplikasi dashboard enterprise Anda menggunakan pola OAuth2 *Refresh Token Rotation* (RTR) dengan reuse detection. Di halaman dashboard, Next.js mengeksekusi 6 Server Components secara paralel menggunakan `Promise.all` untuk mengambil data dari berbagai microservices. Sesi pengguna memiliki Access Token yang kadaluarsa 2 detik yang lalu, tetapi Refresh Token-nya masih valid. 

Ketika request masuk, keenam Server Components mendeteksi Access Token telah expired dan secara independen memicu fungsi refresh token secara simultan ke Authorization Server. Authorization Server mendeteksi bahwa Refresh Token yang sama dikirim lebih dari satu kali (*token reuse event*), yang secara otomatis mengindikasikan indikasi pencurian token (*replay attack*). Akibatnya, IdP mencabut seluruh *Token Family*, membatalkan sesi pengguna seketika, dan pengguna dipaksa logout mendadak di tengah aktivitas kerja.

* **Pertanyaan Diagnostik & Solusi:**
  1. Mengapa eksekusi paralel di Server Components App Router secara inheren rentan terhadap race condition *Refresh Token Rotation* ini?
  2. Implementasikan arsitektur *Single-Flight / Request Deduplication pattern* (atau memanfaatkan React `cache()` / runtime in-memory mutex) untuk memastikan hanya tepat 1 network request yang dikirim ke Authorization Server, sementara 5 pemanggilan paralel lainnya menunggu (*await*) resolusi token baru yang sama.
  3. Bagaimana penanganan sinkronisasi response header `Set-Cookie` ke browser agar token baru tidak tertimpa (*overwritten*) secara salah oleh response stream yang saling balapan?

### Skenario C: Boundary Bleed pada Multi-Tenant Data Cache (`unstable_cache`)
Sebuah platform SaaS B2B perbankan di Next.js mengimplementasikan Multi-Tenant Role-Based Access Control (Tenant-isolated RBAC). Untuk mengoptimalkan latensi kalkulasi agregasi finansial yang berat, engineering team menggunakan fungsi `unstable_cache` untuk mencache hasil query data antar pemanggilan. 

Dua hari setelah deployment, tim kepatuhan melaporkan bahwa CFO dari Tenant A berhasil melihat data laporan agregasi keuangan milik Tenant B pada dashboard analitik mereka saat mengakses sistem di waktu yang hampir bersamaan.

```typescript
// Implementasi rentan yang ditemukan di repositori:
export async function getFinancialSummary(companyId: string, role: string) {
  return await unstable_cache(
    async () => {
      return await db.aggregateFinancialData(companyId);
    },
    ['financial-summary'], // cache key parts
    { revalidate: 3600, tags: ['finance'] }
  )();
}
```

* **Pertanyaan Diagnostik & Solusi:**
  1. Lakukan audit kode terhadap implementasi `unstable_cache` di atas dan jelaskan secara teknis mengapa terjadi *boundary bleed* (data leakage) antar tenant yang berbeda.
  2. Perbaiki fungsi `getFinancialSummary` menggunakan prinsip *Cryptographic Tenant Isolation*, *Cache Key Segregation*, dan validasi skema runtime context yang menjamin data multi-tenant tidak akan pernah tercampur dalam Data Cache layer Next.js.
  3. Bagaimana Anda merancang automated integration test menggunakan Vitest/Playwright untuk membuktikan bahwa data cache terisolasi mutlak per tenant ID dan per role context?

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Trust Enterprise Data Access Layer (DAL) & Dynamic ABAC Engine with Resilient Token Rotation

#### Problem Statement
Sebuah platform manajemen aset finansial enterprise membutuhkan fondasi otentikasi dan otorisasi zero-trust di Next.js (App Router). Sistem saat ini sering mengalami security drift: developer junior sering mengekspos Server Actions tanpa pemeriksaan hak akses, token refresh kerap gagal saat halaman memuat banyak komponen secara paralel, dan implementasi otorisasi masih terfragmentasi antara Middleware dan komponen UI, memicu potensi celah eskalasi hak istimewa (Privilege Escalation).

#### Requirements
1. **Dynamic ABAC Engine (Attribute-Based Access Control):**
   * Bangun engine otorisasi murni (functional) yang mengevaluasi hak akses tidak hanya berdasarkan Role (`ADMIN`, `COMPLIANCE_OFFICER`, `TRADER`), tetapi juga Attribute & Environment (`TenantId`, `ResourceStatus`, `TradingVolumeLimit`, `IPWhitelistRange`, `OperatingHours`).
   * Engine harus dapat digunakan secara seragam di: Data Access Layer (Server Components), Route Handlers, dan Server Actions.
2. **Resilient Token Rotation & Single-Flight Concurrency:**
   * Buat custom session provider engine yang menangani OIDC/OAuth2 Access & Refresh Token rotation.
   * Implementasikan mekanisme *Single-Flight Promise Locking* untuk mencegah insiden concurrency saat banyak Server Components mendeteksi expired token secara bersamaan.
   * Modifikasi request context secara internal sehingga operasi fetch berikutnya dalam lifecycle request yang sama menggunakan token baru yang baru saja di-refresh.
3. **Zero-Trust DAL Wrapper for Server Actions:**
   * Bangun abstraksi utilitas `createSecureAction` yang memvalidasi:
     1. Status autentikasi session yang valid.
     2. Validasi input skema menggunakan Zod.
     3. Evaluasi permission ABAC.
     4. Audit logging terstruktur (merekam actor, action, target resource, timestamp, dan status eksekusi) ke standard output/monitoring sink.
   * Jika evaluasi otorisasi gagal, lemparkan custom error serializable yang aman tanpa mengekspos arsitektur internal atau stack trace ke client.
4. **Strict CSP with Nonce Generator:**
   * Implementasikan Edge Middleware yang menghasilkan CSP strict (mengeliminasi `unsafe-inline` dan `unsafe-eval`) menggunakan dynamic per-request nonce yang diteruskan ke Root Layout.

#### Constraints
* **Runtimes:** Middleware harus fully-compatible dengan Edge Runtime (tidak boleh menggunakan package berbasis Node.js runtime seperti `crypto` bawaan lawas, gunakan `Web Crypto API` seperti `crypto.subtle`).
* **Framework:** Next.js 14+ / 15 App Router standard conventions.
* **Dependencies:** Tanpa library auth high-level instan (seperti Auth.js / NextAuth / Clerk). Anda harus membangun arsitektur DAL, Token Handler, dan ABAC wrapper dari low-level building blocks untuk membuktikan penguasaan internal mekanisme. (Boleh menggunakan `jose` untuk JWT/JWKS dan `zod` untuk validasi schema).
* **Performa:** Overhead evaluasi otorisasi pada Data Access Layer harus berada di bawah 2 milidetik per pemanggilan fungsi.

#### Expected Output
* Kode implementasi terstruktur:
  * `lib/auth/session.ts`: Engine manajemen token, refresh rotation mutex, dan verifikasi JWT/JWKS.
  * `lib/auth/abac.ts`: Policy rules definition dan evaluation engine.
  * `lib/auth/dal.ts`: Data Access Layer helper yang mengisolasi akses database dan memverifikasi izin actor.
  * `lib/auth/action-client.ts`: Wrapper `createSecureAction` untuk deklarasi Server Actions anti-bocor.
  * `middleware.ts`: CSP nonce generator, basic path filtering, dan session forwarding.
* Dokumen penjelasan arsitektur data flow (request lifecycle) dari Edge Middleware -> Server Component -> DAL -> Server Action execution.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Batas eksekusi (*execution boundary*) dan model ancaman (*threat model*) antara Server Component, Server Action, Client Component, dan Route Handler di Next.js App Router.
- [ ] Mengapa Next.js Edge Middleware tidak boleh dijadikan satu-satunya tumpuan (*single source of truth*) dalam otorisasi data privasi tinggi.
- [ ] Mekanisme proteksi CSRF native pada Next.js Server Actions dan batas limitasinya pada Route Handlers standar.
- [ ] Dampak arsitektural dari *Stateless Cryptographic Sessions* (JWT) vs *Stateful Distributed Sessions* (Redis/Database) terhadap latensi edge dan session revocation.
- [ ] Cara kerja *Refresh Token Rotation* (RTR) dan mengapa race condition concurrency di Server Components dapat memicu false-positive token replay detection.
- [ ] Mekanisme injeksi Dynamic Content Security Policy (CSP) menggunakan cryptographic nonces via Edge Middleware tanpa menyebabkan hydration mismatch.
- [ ] Risiko data poisoning dan tenant leakage pada cache layer Next.js (`unstable_cache` dan `fetch` cache tags) pada aplikasi Multi-Tenant.
- [ ] Perbedaan fundamental antara Role-Based Access Control (RBAC) dan Attribute-Based Access Control (ABAC) serta cara pemodelannya dalam sistem enterprise.

### Saya tidak perlu menghafal:
- [ ] Seluruh algoritma kriptografi internal dari spesifikasi IETF RFC 7519 (JSON Web Token) atau RFC 7515 (JWS) secara matematis mendalam (cukup memahami cara kerja asimetris vs simetris dan implementasinya via library seperti `jose`).
- [ ] Seluruh sintaks dan direktif lengkap Content Security Policy Level 3 (cukup memahami implementasi nonces, strict-dynamic, frame-ancestors, dan CSP report-to).
- [ ] Kode implementasi internal driver Redis atau database adapter untuk penyimpanan sesi.

### Saya harus bisa melakukan:
- [ ] Membangun Data Access Layer (DAL) terpusat yang memverifikasi sesi, otorisasi ABAC, dan melakukan sanitasi DTO (*Data Transfer Object*) sebelum data sampai ke Server Component / Client Component.
- [ ] Menerapkan Higher-Order Function / Wrapper untuk Server Actions yang mengeksekusi validasi schema (Zod), otorisasi kontekstual, dan audit log secara konsisten.
- [ ] Mengisolasi cache multi-tenant secara absolut menggunakan komposisi partisi *cache keys* yang melibatkan Tenant Context dan Role Identity.
- [ ] Mengonfigurasi Dynamic CSP with Nonces di Middleware dan meneruskannya secara aman ke Server Root Layout (`app/layout.tsx`).
- [ ] Menyelesaikan permasalahan race condition token refresh simultan menggunakan *single-flight deduplication* di lingkungan server runtime.
- [ ] Mengaudit bundle client menggunakan analyzer tool untuk memastikan tidak ada credential, connection string, atau private logic yang bocor ke file JavaScript publik.