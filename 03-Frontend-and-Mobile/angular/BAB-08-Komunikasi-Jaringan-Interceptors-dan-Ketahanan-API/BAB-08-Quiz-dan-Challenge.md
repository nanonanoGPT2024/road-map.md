# BAB 08: Quiz, Challenge, & Knowledge Check
**Komunikasi Jaringan, Interceptors, dan Ketahanan API**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Pertanyaan 1: Immutability pada HttpRequest
Mengapa objek `HttpRequest` di Angular didesain secara *immutable*? Jelaskan implikasi arsitektural dari keputusan desain ini terhadap *interceptor chain*, dan bagaimana metode `req.clone()` bekerja di bawah kap mesin untuk memodifikasi *headers*, *params*, atau *body* tanpa merusak integritas *request pipeline*.

### Pertanyaan 2: Functional Interceptor vs Class-Based Interceptor
Angular v15+ memperkenalkan `HttpInterceptorFn` untuk menggantikan class-based interceptor (`HttpInterceptor` dengan injection token `HTTP_INTERCEPTORS`). Analisis perbedaan mendasar keduanya dari perspektif:
1. *Dependency Injection lifecycle* dan eksekusi konteks.
2. Efisiensi kompilasi dan *tree-shaking*.
3. Urutan eksekusi (*chain of responsibility*) saat dikonfigurasi melalui `provideHttpClient(withInterceptors([...]))`.

### Pertanyaan 3: Lifecycle Cold Observable pada HttpClient
Metode-metode pada `HttpClient` (seperti `.get()`, `.post()`) menghasilkan *Cold Observable*. Jelaskan siklus hidup transmisi HTTP tersebut dari fase inisiasi hingga terminasi. Apa konsekuensi teknis jika Observable tersebut di-*subscribe* oleh beberapa *consumer* secara terpisah tanpa memanfaatkan operator *multicasting* (`shareReplay`), dan kapan *underlying network request* (XHR/Fetch) sebenarnya dieksekusi?

### Pertanyaan 4: HttpContext dan Type-Safe Metadata
Jelaskan peran `HttpContext` dan `HttpContextToken` dalam komunikasi jaringan Angular. Bagaimana mekanisme ini memfasilitasi pertukaran metadata antar-komponen pemanggil dan *interceptor chain* tanpa mengotori HTTP *Headers* atau *URL Query Parameters*? Berikan contoh use-case valid di mana `HttpContext` mutlak diperlukan.

### Pertanyaan 5: Error Boundary: ErrorEvent vs HttpErrorResponse
Dalam penanganan kesalahan jaringan via `catchError`, Angular dapat mengembalikan instance `HttpErrorResponse` yang membungkus dua jenis kegagalan yang berbeda secara fundamental: *client-side/network error* dan *backend-side error*. Jelaskan bagaimana cara membedakan keduanya secara programatik, dan mengapa strategi resolusi untuk kedua jenis error tersebut harus dipisahkan secara arsitektural.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Pertanyaan 1: Interceptor Chain Deadlock & Stream Completion
Perhatikan implementasi functional interceptor berikut:
```typescript
export const loggingInterceptor: HttpInterceptorFn = (req, next) => {
  console.log('Outgoing request:', req.url);
  // Engineer lupa memanggil next(req) atau mengembalikan stream kosong
  return EMPTY; 
};
```
Analisis dampak internal pada aplikasi Angular jika sebuah interceptor mengembalikan `EMPTY`, `NEVER`, atau stream yang tidak pernah *emit* dan tidak pernah *complete*. Apa yang terjadi pada UI subscription, `takeUntilDestroyed`, dan status memori komponen pemanggil?

### Pertanyaan 2: AbortController, XHR Cancellation, dan Backend Idempotency
Ketika Observable HTTP di-*unsubscribe* sebelum server memberikan respons (misalnya via operator `switchMap` atau perpindahan rute), bagaimana Angular menghentikan transmisi jaringan pada layer browser? Apakah pembatalan ini menjamin bahwa operasi mutasi (*write operation* seperti POST/PATCH) di sisi backend tidak dieksekusi? Jelaskan mitigasi yang harus diterapkan untuk menjaga konsistensi data.

### Pertanyaan 3: Resiliency Strategy: Retry Berbasis Jitter dan Status Code Filtering
Banyak implementasi pemula menggunakan operator `retry(3)` secara membabi buta pada seluruh kegagalan HTTP. Jelaskan mengapa pendekatan ini berbahaya bagi infrastruktur backend (*retry storm*). Rancang arsitektur retry yang benar dengan mengombinasikan:
1. Pengecekan idempotensi request (metode HTTP).
2. Filter status code (transient errors vs non-retryable errors).
3. Algoritma *Exponential Backoff* dengan *Full Jitter*.

### Pertanyaan 4: In-Flight Request Deduplication (Race Condition Prevention)
Pada dashboard kompleks, beberapa komponen independen dapat meminta data master yang sama (misal: `/api/v1/user-profile`) secara simultan pada saat inisialisasi aplikasi. Rancang mekanisme interceptor atau service-level caching untuk melakukan *request deduplication* (menggabungkan *in-flight requests* yang identik ke dalam satu transmisi HTTP yang sama), dan jelaskan bagaimana membersihkan cache tersebut secara tepat begitu stream *complete* atau *error*.

### Pertanyaan 5: SSR, Hydration, dan TransferState Leak
Pada aplikasi Angular SSR (Server-Side Rendering), request HTTP yang dipicu selama rendering di server sering kali tereksekusi kembali di sisi klien saat proses hidrasi berlangsung. Jelaskan mekanisme `withHttpTransferCacheOptions` pada `provideHttpClient`. Bagaimana Angular melakukan serialisasi respons HTTP ke dalam DOM HTML, dan apa potensi kerentanan keamanan serta *memory overhead* jika respons data berukuran besar?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: "The Thundering Herd 401 Storm" (Production Outage)
* **Konteks:** Aplikasi Enterprise Banking memiliki dashboard analitik dengan 18 widget independen. Saat token JWT access expired (berumur 15 menit), user masih aktif berinteraksi. Dashboard memicu auto-refresh berkala secara simultan untuk ke-18 widget tersebut.
* **Gejala:** Seluruh 18 request menerima HTTP 401 Unauthorized secara bersamaan. Akibat implementasi *auth interceptor* yang naif, interceptor memicu 18 endpoint panggilan `/api/v1/auth/refresh` secara paralel. Server autentikasi mendeteksi ini sebagai indikasi *token reuse attack* (karena refresh token dirotasi pada setiap pemanggilan), membatalkan seluruh sesi, dan memaksa user keluar secara tiba-tiba (*forced logout loop*).
* **Tugas Diagnostik & Solusi:**
  1. Identifikasi *single point of failure* pada alur interceptor tersebut.
  2. Rancang arsitektur sinkronisasi menggunakan RxJS primitives (`BehaviorSubject`, `Subject`, `mutex lock`, atau *queueing*) di dalam functional interceptor untuk memastikan: hanya 1 request refresh token yang dikirimkan ke server, sementara 17 request lainnya ditahan (*queued/paused*) dan secara otomatis di-*replay* dengan token baru setelah refresh berhasil.

### Skenario B: "Ghost Mutations & Out-of-Order Search" (Data Integrity Bug)
* **Konteks:** Aplikasi e-commerce memiliki fitur filter pencarian real-time dengan autosave preferensi pengguna ke backend. Kode implementasi komponen pencarian adalah sebagai berikut:
```typescript
queryControl.valueChanges.pipe(
  debounceTime(300),
  distinctUntilChanged(),
  tap(query => this.saveUserPreference(query)), // POST ke backend
  switchMap(query => this.catalogService.search(query)) // GET ke backend
).subscribe(results => this.renderResults(results));
```
* **Gejala:** 
  1. Kadang-kadang preferensi pengguna di database menyimpan karakter parsial yang usang (misal: "lapt" tersimpan padahal input terakhir adalah "laptop").
  2. Jika koneksi tidak stabil, respons HTTP GET pencarian untuk kata kunci lama terkadang menimpa hasil pencarian yang lebih baru jika backend merespons dengan latensi acak.
* **Tugas Diagnostik & Solusi:**
  1. Bedah secara mendalam mengapa operator `tap` dengan *side-effect* asinkron tanpa *flattening operator* merusak urutan eksekusi dan memicu *race condition* (Ghost Mutation).
  2. Mengapa `switchMap` pada `catalogService.search` saja belum cukup menyelesaikan anomali ini? Rekonstruksi alur RxJS tersebut agar *race condition* dieliminasi sepenuhnya dan mutasi data dijamin *idempotent* serta *strictly ordered*.

### Skenario C: "The Cascading Latency Collapse" (Architectural Trade-off)
* **Konteks:** Microservice payment gateway mitra mengalami degradasi internal, menyebabkan latensi endpoint checkout `/api/v1/checkout` melonjak dari 200ms menjadi 45 detik (tepat sebelum batas timeout reverse proxy Nginx 60 detik). Klien Angular tidak memiliki konfigurasi timeout global.
* **Gejala:** User mengklik tombol "Bayar", UI macet (*loading state* menggantung tanpa batas waktu yang jelas), user yang panik mengklik tombol berulang kali. Browser thread kehabisan resource koneksi HTTP (*max connections per domain* limit tercapai), menyebabkan fungsionalitas lain dalam aplikasi lumpuh total (*cascading failure*).
* **Tugas Diagnostik & Solusi:**
  1. Bagaimana Anda merancang arsitektur ketahanan API pada layer frontend yang mencakup:
     * *Global request timeout* via Interceptor yang dapat di-*override* per request menggunakan `HttpContext`.
     * Implementasi *Circuit Breaker Pattern* pada sisi client (State: *CLOSED*, *OPEN*, *HALF-OPEN*) untuk mencegah pengiriman request jika dependensi backend telah terbukti kolaps.
  2. Jelaskan trade-off antara *eager client-side failure* (memberi notifikasi error instan ke user) vs *retrying with exponential backoff* pada transaksi berbayar non-idempotent.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Resilient HTTP Core Engine
Bangun modul komunikasi jaringan enterprise menggunakan Angular v17/v18+ yang mengombinasikan mekanisme autentikasi mutakhir, ketahanan jaringan, dan optimasi performa.

#### Deskripsi Masalah
Banyak aplikasi enterprise mengalami kegagalan sistemik saat menghadapi: *transient network drops*, *concurrent unauthorized requests*, beban payload berulang yang tidak terduplikasi, dan API backend yang lambat tanpa batasan timeout yang jelas. Anda diminta menggantikan layer HTTP dasar dengan sistem yang tangguh (*fault-tolerant*).

#### Spesifikasi Kebutuhan
1. **Functional Interceptor Composition:**
   Bangun rantai functional interceptor tanpa menggunakan class-based architecture:
   * `correlationIdInterceptor`: Menambahkan UUID v4 unik pada header `X-Correlation-ID` untuk tracing transaksi end-to-end.
   * `timeoutInterceptor`: Menerapkan timeout dinamis (default: 10 detik, dapat diubah via `HttpContextToken<number>`).
   * `authRefreshInterceptor`: Menangani HTTP 401 via *Mutex Queueing Pattern*. Hanya boleh ada 1 eksekusi refresh token yang berjalan pada satu waktu; semua request konkuren yang gagal wajib di-*hold* dan diulang (*replay*) begitu refresh token berhasil. Jika refresh gagal, batalkan antrean dan picu sinyal logout.
   * `retryWithBackoffInterceptor`: Melakukan retry otomatis secara eksklusif untuk request *idempotent* (GET, HEAD, PUT, DELETE) yang mengalami transient error (HTTP 502, 503, 504 atau Network Error), dengan formula *Exponential Backoff with Full Jitter*. Request POST tidak boleh di-retry secara otomatis kecuali memiliki token idempotensi khusus via `HttpContext`.
   * `deduplicationInterceptor`: Mencegah pengiriman request GET simultan yang identik jika request pertama masih berstatus *in-flight*.

2. **HttpContext Configuration API:**
   Sediakan custom tokens:
   * `IS_IDEMPOTENT_MUTATION = new HttpContextToken<boolean>(() => false)`
   * `REQUEST_TIMEOUT = new HttpContextToken<number>(() => 10000)`
   * `BYPASS_AUTH = new HttpContextToken<boolean>(() => false)`
   * `ENABLE_DEDUPLICATION = new HttpContextToken<boolean>(() => true)`

3. **Constraints:**
   * Wajib berbasis **Angular 17/18 Standalone Architecture** (`provideHttpClient(withInterceptors([...]))`).
   * Dilarang menggunakan library eksternal untuk state management atau RxJS utils tambahan; hanya gunakan modul bawaan `@angular/common/http` dan `rxjs`.
   * Wajib menangani *memory leak*: pastikan semua *internal queues* atau subjects di-cleanup jika terjadi error fatal.
   * *Strict TypeScript Mode* aktif (`noImplicitAny: true`, `strictNullChecks: true`).

#### Expected Output
1. File implementasi TypeScript yang bersih dan modular:
   * `network-tokens.ts`: Definisi token konteks.
   * `auth-refresh.interceptor.ts`: Interceptor sinkronisasi refresh token.
   * `resilience.interceptor.ts`: Implementasi timeout, retry backoff, dan deduplikasi.
2. Kode unit test (menggunakan `HttpTestingController`) yang memverifikasi skenario ekstrim: 5 request konkuren menerima 401 secara bersamaan, dan hanya 1 kali POST request refresh yang ditembakkan ke endpoint auth.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mengapa `HttpRequest` dan `HttpHeaders` bersifat *immutable* dan implikasi pembuatan referensi barunya di memori.
- [ ] Perbedaan eksekusi Functional Interceptors (`HttpInterceptorFn`) vs Multi-provider Class Interceptors.
- [ ] Bahwa RxJS Observable pada `HttpClient` bersifat *cold*, *single-value* (mengirimkan satu nilai lalu complete), dan bagaimana perilakunya saat dibatalkan (*cancellation semantics*).
- [ ] Cara kerja *Chain of Responsibility* pada `HttpHandlerFn` / `next(req)`.
- [ ] Mekanisme propagasi metadata internal menggunakan `HttpContext` dan `HttpContextToken`.
- [ ] Klasifikasi transient network errors (HTTP 408, 502, 503, 504) versus client logic errors (HTTP 400, 401, 403, 422).
- [ ] Matematika di balik *Exponential Backoff with Full Jitter* untuk mencegah *thundering herd problem*.
- [ ] Dampak hidrasi SSR terhadap duplikasi pemanggilan API dan cara mitigasinya via `withHttpTransferCache`.

### Saya tidak perlu menghafal:
- [ ] Kode implementasi numerik status HTTP standar RFC (cukup pahami kategori 2xx, 4xx, 5xx dan gunakan konstanta enum/status codes).
- [ ] Sintaks legacy `HttpModule` lama (AngularJS / Angular v4.x terdahulu berbasis class provider `HTTP_INTERCEPTORS`).
- [ ] Detail algoritma kriptografi UUID v4 untuk correlation ID (cukup gunakan implementasi standar `crypto.randomUUID()`).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `provideHttpClient` menggunakan *functional features* (`withInterceptors`, `withFetch`, `withXsrfConfiguration`).
- [ ] Mengkloning dan memutasi request (`req.clone()`) untuk menambahkan bearer token, *custom tracing headers*, atau mengubah URL secara dinamis.
- [ ] Mengimplementasikan *Queueing Token Refresh Pattern* anti-race-condition menggunakan operator RxJS (`filter`, `take`, `switchMap`, `catchError`).
- [ ] Mengisolasi error HTTP secara granular menggunakan operator `catchError` tanpa memutus stream Observable induk.
- [ ] Membatalkan (*cancel*) request HTTP yang sedang berjalan menggunakan `takeUntilDestroyed` atau abort triggers saat komponen dihancurkan.
- [ ] Menulis unit testing komprehensif untuk *interceptor chain* menggunakan `provideHttpClientTesting` dan `HttpTestingController`.