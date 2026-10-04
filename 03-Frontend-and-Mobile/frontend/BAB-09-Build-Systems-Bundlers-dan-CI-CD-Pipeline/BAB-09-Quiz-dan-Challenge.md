# BAB 09: Quiz, Challenge, & Knowledge Check
**Bab 09: Enterprise Frontend Security, Authentication Architectures, & Client-Side Observability**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: DOM-based XSS, Sanitasi Kontekstual, dan Trusted Types API
Jelaskan secara mendalam perbedaan fundamental antara *Reflected/Stored XSS* dan *DOM-based XSS*. Mengapa penggunaan sanitasi berbasis regex atau *blacklisting string* hampir selalu gagal menangkal DOM-based XSS pada SPA modern? Bagaimana spesifikasi **W3C Trusted Types API** mengubah paradigma pertahanan browser dari reaktif (sanitasi runtime via library pihak ketiga seperti DOMPurify) menjadi proaktif (enforcement di level engine browser pada sink seperti `Element.innerHTML` atau `ScriptElement.src`)?

### Soal 1.2: Komparasi Arsitektur Auth: Token-in-Memory + PKCE vs Backend-for-Frontend (BFF)
Bandingkan dua pola arsitektur autentikasi utama pada Single Page Application (SPA):
1. **OAuth 2.1 Authorization Code Flow with PKCE** di mana access token disimpan di memory (closure/Web Worker) dan refresh token dikelola via client.
2. **Backend-for-Frontend (BFF) Pattern** di mana SPA murni beroperasi menggunakan HTTP-only, Secure, SameSite cookies, dan pertukaran token upstream ditangani sepenuhnya oleh layer backend/Node.js reverse proxy.

Analisis trade-off keduanya ditinjau dari vektor serangan XSS, CSRF, kompleksitas infrastruktur, dan skalabilitas edge computing.

### Soal 1.3: Content Security Policy (CSP) Level 3: Nonce-Based vs Hash-Based Strict CSP
Jelaskan kelemahan mendasar dari CSP berbasis allowlist domain (misal: `script-src https://apis.google.com https://cdn.example.com`) yang membuatnya rentan terhadap teknik *JSONP endpoint abuse* dan *path traversal script hosting*. Jelaskan bagaimana **Strict CSP** memanfaatkan kombinasi `strict-dynamic`, kriptografis `nonce-{random}`, dan `hash-{sha256}` untuk mengamankan dynamic script loading tanpa merusak modularitas aplikasi modern.

### Soal 1.4: W3C Trace Context Standard dan Propagasi Distributed Tracing
Bagaimana format header W3C `traceparent` (misal: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`) disusun? Jelaskan peran masing-masing komponen (`version`, `trace-id`, `parent-id`/`span-id`, `trace-flags`). Bagaimana frontend client bertindak sebagai inisiator *distributed trace* yang menghubungkan telemetri browser (user action, AJAX request) ke distributed tracing microservices di backend tanpa melanggar batasan CORS?

### Soal 1.5: Synthetic Monitoring vs Real User Monitoring (RUM) & Bias Sampling
Jelaskan perbedaan mendasar antara telemetri *Synthetic Monitoring* (e.g., automated headless browser runs via Lighthouse/Playwright di CI/CD) dan *Real User Monitoring* (RUM) yang dikoleksi via Performance Observer API langsung dari perangkat pengguna. Bagaimana Anda mengatasi fenomena sampling bias pada data RUM (misal: skew metrik Core Web Vitals yang disebabkan oleh *long-tail low-end mobile devices* di jaringan berlatensi tinggi)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Mutex Queue Interceptor pada Silent Token Refresh Race Condition
Bayangkan sebuah skenario di mana pengguna membuka dashboard dengan 8 widget independen yang secara bersamaan melakukan HTTP request paralel saat *access token* telah kedaluwarsa. 
- Jika HTTP client (misal: Axios/Fetch wrapper) tidak memiliki mekanisme sinkronisasi, akan terjadi 8 pemanggilan refresh token secara paralel yang memicu deteksi *Refresh Token Reuse / Revocation* di Auth Provider.
- Rancang mekanisme internal interceptor berbasis *promise queue / mutex lock* untuk memastikan hanya tepat 1 network request ke `/oauth/token` yang dieksekusi, sementara 7 request lainnya di-pause/suspended dan secara otomatis di-replay menggunakan access token yang baru.

### Soal 2.2: Cross-Origin `postMessage` Vulnerability & Prototype Pollution Sink
Perhatikan implementasi handler berikut yang digunakan pada komponen embedded micro-frontend:

```typescript
window.addEventListener('message', (event) => {
  const payload = JSON.parse(event.data);
  if (payload.action === 'SET_CONFIG') {
    Object.assign(window.__APP_CONFIG__, payload.config);
    renderApp();
  }
});
```

Identifikasi minimal 3 celah keamanan fatal pada kode di atas (hubungkan dengan validasi origin, eksekusi JSON parsing, dan risiko Prototype Pollution). Tuliskan perbaikan kode defensif dengan implementasi origin verification yang ketat dan sanitasi deep assignment.

### Soal 2.3: CORS Preflight Caching & Wildcard Reflection Vulnerabilities
Sebuah endpoint API `/api/v1/user/financial-data` mengembalikan header berikut saat menerima preflight request:
```http
Access-Control-Allow-Origin: https://malicious-site.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Max-Age: 86400
```
Jelaskan mengapa konfigurasi backend yang secara dinamis merefleksikan nilai header `Origin` request ke dalam `Access-Control-Allow-Origin` bersamaan dengan `Access-Control-Allow-Credentials: true` adalah bencana keamanan. Bagaimana browser mengevaluasi preflight cache (`Access-Control-Max-Age`), dan apa batas maksimal cache duration yang diizinkan oleh engine Chromium serta WebKit?

### Soal 2.4: Memory Leak Detection Akibat Telemetry Breadcrumbs & Global Event Listeners
Pada Single Page Application yang tidak pernah melakukan full page reload selama berhari-hari (misal: POS tablet atau monitoring dashboard), metrik konsumsi memori browser merayap naik (*gradual memory leak*) hingga tab mengalami crash (OOM). 
Setelah profiling via Chrome DevTools Heap Snapshot, ditemukan ribuan objek `Closure` dan `Detached HTMLDivElement` yang terikat pada instance OpenTelemetry/Sentry client SDK.
- Jelaskan bagaimana mekanisme registrasi automatic *click tracking* / *breadcrumbs listener* yang tidak di-prune dengan benar dapat menahan referensi DOM element di memory.
- Bagaimana arsitektur SDK telemetri seharusnya mengimplementasikan *circular buffer / bounded ring buffer* dan *weak references* (`WeakRef`, `WeakMap`) untuk mencegah memory leak tersebut?

### Soal 2.5: Production Source Maps Pipeline & Private Error Symbolication
Mengekspos file `.map` secara publik di CDN produksi membuka *reverse engineering* kode bisnis, arsitektur internal, dan API contract ke publik. Namun, menyembunyikan source map membuat stack trace error telemetry di dashboard Sentry/Datadog menjadi `bundle.min.js:1:24108` yang tidak dapat didebug.
- Rancang pipeline CI/CD dan arsitektur hosting source map yang aman, di mana production build tetap menghasilkan source map dengan `debugId` terintegrasi, diunggah secara privat ke internal telemetry server melalui secure API, dan dihapus/dikecualikan dari public web server root/CDN.
- Bagaimana browser error handler memproses header `SourceMap` atau `//# sourceMappingURL=` jika file tersebut berada di balik VPN/Autentikasi internal?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Thundering Herd Problem pada Edge Session Invalidation
*Konteks Insiden:* Platform e-commerce berskala 100.000 concurrent active users mengalami force-logout mendadak karena rotasi asymmetric signing key (JWKS) pada Authorization Server. Karena access token ditolak secara massal oleh edge CDN gateway dengan status HTTP 401, client SPA di browser seluruh pengguna secara serentak mengeksekusi fallback *silent refresh logic* ke Auth API. Hal ini memicu *thundering herd problem* (lonjakan mendadak 100.000 request/detik ke endpoint `/oauth/v2/token`), mengakibatkan cascading failure pada database autentikasi dan denial of service total pada seluruh sistem.

**Pertanyaan Diagnostik & Arsitektur:**
1. Rancang algoritma mitigasi di level frontend HTTP client SDK untuk mencegah sinkronisasi massal request refresh token (hubungkan dengan konsep *exponential backoff* dan *full jitter*).
2. Bagaimana pola arsitektur *graceful degradation* yang harus ditampilkan ke pengguna agar UI tidak freeze atau memunculkan loop reload halaman terus-menerus?
3. Jika Anda bertindak sebagai Principal Engineer, bagaimana Anda mendesain mekanisme komunikasi server-to-client (misal: via Server-Sent Events atau WebSocket notification) untuk mengoordinasikan key rollover tanpa memaksa seluruh client me-refresh token di detik yang sama?

---

### Skenario B: Third-Party Supply-Chain Attack via Tag Manager
*Konteks Insiden:* Tag analytics pihak ketiga yang dipasang via Google Tag Manager (GTM) pada Single Page Application perbankan diretas. Skrip vendor tersebut menyisipkan payload keylogger yang membaca input form pada halaman checkout/pembayaran dan mengirimkan nomor kartu kredit, tanggal kedaluwarsa, dan CVV ke domain C2 (`https://telemetry-collect-cdn.xyz/log`). Aplikasi Anda sebenarnya telah menerapkan library form validation dan enkripsi payload sebelum dikirim ke backend internal.

**Pertanyaan Diagnostik & Arsitektur:**
1. Mengapa enkripsi payload pada saat form submit gagal melindungi data dalam kasus ini?
2. Bagaimana formulasi header **Content Security Policy (CSP)** yang spesifik (`connect-src`, `script-src`, `form-action`) untuk mengisolasi dan membatasi ke mana saja data dari browser dapat dikirimkan secara outbound?
3. Rancang strategi arsitektur pembayaran yang aman (misal: *Hosted Fields* berbasis sandboxed cross-origin `iframe` dengan isolasi context) yang menjamin script analitik/GTM pada parent window secara matematis tidak memiliki akses ke input DOM sensitif.

---

### Skenario C: Cross-Origin Micro-Frontend Tracing & Opaque Script Error Masking
*Konteks Insiden:* Perusahaan Anda menerapkan arsitektur Micro-Frontend (MFE) menggunakan Webpack Module Federation. Container App di-host di `https://app.enterprise.com`, sedangkan remote module transaksi di-host di CDN terpisah `https://cdn-mfe.enterprise-assets.com`. 
Di production telemetry (RUM), 90% error transaksi tercatat sebagai:
`"Script error." line 0, column 0` tanpa stack trace sama sekali. 
Selain itu, distributed tracing terputus total: span trace dari container app memiliki `trace-id: AAA`, tetapi panggilan fetch dari remote module menghasilkan `trace-id: BBB` baru atau tidak membawa context tracing sama sekali saat memanggil backend microservice.

**Pertanyaan Diagnostik & Arsitektur:**
1. Apa akar penyebab teknis di balik pesan `"Script error."` pada runtime browser, dan atribut HTML serta HTTP response header apa saja yang wajib disetel pada CDN remote script untuk membuka stack trace aslinya ke `window.onerror`?
2. Bagaimana cara mengorkestrasi single global trace context lifecycle di runtime Module Federation agar instance tracer tidak terduplikasi antar host dan remotes?
3. Rancang schema distributed tracing middleware untuk Fetch/XHR yang aman dari kebocoran credential: header W3C `traceparent` harus otomatis disuntikkan ke API internal, namun wajib diblokir jika request dikirim ke external vendor pihak ketiga.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Secure Auth Vault & Telemetry-Aware HTTP Client Engine

#### Problem Statement
Sebagian besar SPA menyimpan JWT access token secara tidak aman di `localStorage` (rentan XSS data exfiltration) atau mengandalkan implementasi naive Axios interceptor yang rentan race condition saat token kedaluwarsa. Selain itu, request network sering kali terputus dari observabilitas APM modern karena tidak adanya inject trace context W3C.

Anda diminta untuk membangun sebuah core library TypeScript independen (*framework-agnostic*): **`@enterprise/secure-http-client`**.

#### Requirements & Spesifikasi Fungsional

1. **Secure Memory Token Vault:**
   - Token tersimpan secara terenkapsulasi dalam scope tertutup (Closure atau Web Worker).
   - Akses langsung ke raw token string dilarang dari window/global scope.
   - Sediakan interface untuk `setTokens(tokens)`, `getAccessToken()`, dan `clearTokens()`.

2. **Concurrency-Safe Interceptor Engine (Mutex Queue):**
   - HTTP client harus mendeteksi token expiration (HTTP 401).
   - Ketika 401 terdeteksi, request asli harus di-pause.
   - Hanya pemicu pertama yang boleh memanggil function `refreshToken()`. Request paralel berikutnya harus dimasukkan ke dalam antrean (*pending promise queue*).
   - Setelah refresh berhasil, seluruh request dalam antrean harus di-replay dengan access token baru.
   - Jika refresh gagal, seluruh antrean harus di-reject, vault dibersihkan, dan event `AUTH_SESSION_TERMINATED` dipancarkan.

3. **W3C Distributed Tracing Injection:**
   - Setiap outbound request wajib diinjeksi header `traceparent` yang valid sesuai standar W3C.
   - Span ID harus di-generate secara acak per-request menggunakan `crypto.getRandomValues()`.
   - Engine harus memiliki allowlist domain. Header telemetri **hanya boleh** diinjeksikan ke domain internal yang terdaftar.

4. **Trusted Types & Defensive DOM Error Handler:**
   - Menyediakan global unhandled rejection telemetry tracker yang aman dari recursive error loop.

#### Constraints
- **Zero Third-Party Runtime Dependencies:** Tidak boleh menggunakan library seperti Axios, Lodash, RxJS, atau Sentry SDK. Harus murni memanfaatkan Native `fetch`, `crypto`, dan TypeScript standard library.
- **Strict Typing:** Tidak boleh ada penggunaan tipe `any`. Semua status antrean, konfigurasi request, dan payload error harus menggunakan discriminated unions.
- **Robust Error Handling:** Mampu menangani request abort via `AbortController`.

#### Expected Deliverables
1. File `TokenVault.ts`: Modul pengelola token aman.
2. File `HttpClient.ts`: Wrapper fetch dengan concurrency mutex, distributed trace injection, dan request queue.
3. File `Tracing.ts`: Generator W3C trace context conformant.
4. Unit Test Simulation (dalam bentuk file test runnable / mock script) yang membuktikan:
   - 5 request paralel saat token expired hanya menghasilkan 1 call refresh token.
   - Ke-5 request berhasil menyelesaikan eksekusi dengan token baru.
   - Traceparent terinjeksi dengan benar dan bervariasi span-id-nya namun konsisten trace-id-nya jika dalam satu session.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Vektor eksploitasi XSS modern: DOM Clobbering, Prototype Pollution, dan Bypass DOMPurify via sanitization mXSS (mutation XSS).
- [ ] Spesifikasi CSP Level 3: Evaluasi `script-src`, `worker-src`, `connect-src`, `frame-ancestors`, serta keyword `'strict-dynamic'`.
- [ ] Alur OAuth 2.1 Authorization Code Flow dengan Proof Key for Code Exchange (PKCE) beserta fungsi parameter `code_verifier` dan `code_challenge`.
- [ ] Arsitektur Backend-for-Frontend (BFF) vs Client-Token Architecture dengan segala trade-off performa, kompleksitas, dan keamanan cookie (`SameSite=Strict/Lax`, `HttpOnly`, `__Host-` prefix).
- [ ] Format spesifikasi W3C Distributed Tracing (`traceparent` dan `tracestate`) serta integrasinya dengan OpenTelemetry.
- [ ] Metrik Core Web Vitals (LCP, INP, CLS) dan cara mengukurnya secara terprogram menggunakan PerformanceObserver API di runtime produksi.
- [ ] Mitigasi serangan Cross-Origin (CORS, COEP, COOP, CORP) dan dampaknya terhadap `SharedArrayBuffer` serta isolasi memori browser.

### Saya tidak perlu menghafal:
- [ ] Syntax regex kompleks untuk decoding base64 / parsing parsing string JWT manual (gunakan library standar atau Web Crypto).
- [ ] Daftar lengkap seluruh directive legacy CSP Level 1 dan 2 yang sudah deprecated oleh W3C.
- [ ] Nilai numerik hexadesimal exact untuk cipher suites TLS browser.
- [ ] Struktur internal binary data protobuf OpenTelemetry wire format (cukup pahami JSON/HTTP mapping-nya).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi Strict Nonce-Based Content Security Policy pada HTTP reverse proxy (Nginx/Cloudflare Workers) untuk SPA.
- [ ] Mengimplementasikan HTTP Interceptor berbasis antrean thread-safe (Promise queue) untuk silent token refresh tanpa bug race condition.
- [ ] Melakukan investigasi stack trace error `"Script error."` pada remote module cross-origin dan memperbaikinya via konfigurasi CORS & SRI.
- [ ] Mengintegrasikan PerformanceObserver API untuk menangkap metrik Interaction to Next Paint (INP) dan mendistribusikannya ke telemetry endpoint secara non-blocking via `navigator.sendBeacon`.
- [ ] Melakukan heap profiling via Chrome DevTools untuk menemukan retaining path dari DOM/closure memory leaks pada library telemetry client.