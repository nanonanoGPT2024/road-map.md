# BAB 06: Quiz, Challenge, & Knowledge Check
**Validation, Error Handling, & Fault Tolerance**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Siklus Hidup Validasi & Thread Safety:**  
   Jelaskan perbedaan mendasar antara validasi berbasis `System.ComponentModel.DataAnnotations` dengan FluentValidation (`AbstractValidator<T>`) dalam konteks siklus hidup request ASP.NET Core. Mengapa melakukan query I/O asinkron (misalnya pengecekan ke database) di dalam validator sering kali dianggap sebagai *anti-pattern* performa, dan bagaimana cara memitigasi risiko *thread pool starvation* jika validasi I/O tak terhindarkan?

2. **Evolusi Penanganan Kesalahan: `UseExceptionHandler` vs `IExceptionHandler` (.NET 8):**  
   Bandingkan arsitektur global exception handling lama berbasis middleware kustom dengan abstraksi `IExceptionHandler` yang diperkenalkan pada .NET 8. Bagaimana urutan eksekusi (*pipeline order*), manajemen status kode HTTP, dan integrasi rantai tanggung jawab (*chain of responsibility*) bekerja saat beberapa `IExceptionHandler` didaftarkan ke dalam kontainer IoC?

3. **Spesifikasi RFC 7807 (Problem Details for HTTP APIs):**  
   Mengapa industri beralih dari format respons kesalahan kustom (seperti payload generik `{ "success": false, "message": "error" }`) ke standar RFC 7807/RFC 9457 `ProblemDetails`? Analisis struktur field wajib dan opsional (`type`, `title`, `status`, `detail`, `instance`, serta *extensions*) dan implikasinya terhadap *machine-readability* pada arsitektur API Gateway atau microservices.

4. **Karakteristik Kegagalan: Transient vs Non-Transient Errors:**  
   Klasifikasikan perbedaan fundamental antara *transient error* dan *non-transient (deterministic) error*. Berikan masing-masing 2 contoh kode HTTP status atau exception sistem pada .NET, dan jelaskan mengapa mengeksekusi strategi *Retry* secara membabi buta pada respons HTTP `400 Bad Request` atau `409 Conflict` merupakan cacat desain arsitektur yang fatal.

5. **State Machine pada Circuit Breaker Pattern:**  
   Gambarkan dan jelaskan secara rinci tiga status utama dalam *Circuit Breaker* (`Closed`, `Open`, `Half-Open`). Apa parameter metrik yang memicu transisi dari `Closed` ke `Open` (misal: *failure rate threshold*, *minimum throughput*), dan bagaimana mekanisme status `Half-Open` menguji kesehatan downstream service tanpa membebani sistem yang sedang dalam masa pemulihan?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Response Streaming & Edge Case `Response.HasStarted`:**  
   Ketika sebuah unhandled exception terjadi di tengah-tengah serialisasi JSON stream respons HTTP yang besar (misalnya menggunakan `IAsyncEnumerable<T>`), runtime ASP.NET Core tidak dapat mengubah HTTP Status Code menjadi `500 Internal Server Error` karena header paket HTTP telah terkirim ke klien (`Response.HasStarted == true`). Bagaimana arsitektur ASP.NET Core menangani kondisi ini di level TCP socket, dan bagaimana Anda mendesain error handling agar klien tidak menerima *truncated/corrupted payload* yang dianggap valid?

2. **Polly v8 Resilience Pipeline: Strategi Komposisi Outer vs Inner:**  
   Dalam pustaka Polly v8 (`Polly.Core`), urutan deklarasi strategi dalam `ResiliencePipelineBuilder` menentukan hierarki pembungkusan (*wrapping hierarchy*). Jika Anda menggabungkan `Timeout`, `Retry`, dan `CircuitBreaker`, urutan mana yang secara arsitektural benar:  
   `Timeout (Outer) -> Retry -> Circuit Breaker (Inner)` ATAU `Retry (Outer) -> Circuit Breaker -> Timeout (Inner)`?  
   Bedah konsekuensi fatal jika urutan tersebut terbalik terhadap penghitungan metrik kegagalan pada Circuit Breaker.

3. **Ambiguity & Cancellation: `TaskCanceledException` vs `OperationCanceledException` vs HTTP 499:**  
   Ketika klien menutup koneksi HTTP (misal: browser menekan tombol *stop* atau koneksi mobile terputus), `HttpContext.RequestAborted` akan terpicu dan membatalkan `CancellationToken`. Telusuri bagaimana ASP.NET Core Kestrel menangani *cancellation* ini. Bagaimana Anda membedakan antara request yang dibatalkan oleh *Client Disconnect* (Nginx/Envoy error 499), pembatalan akibat internal processing timeout (HTTP 504), dan unhandled thread abort agar metrik alerting APM (Application Performance Monitoring) tidak dibanjiri oleh *false-positive alerts*?

4. **FluentValidation Scope Lifetime & Minimal API Filter Short-Circuiting:**  
   Jika sebuah `IValidator<T>` didaftarkan dengan lifetime `Singleton` namun memiliki dependensi injeksi terhadap `DbContext` yang ber-lifetime `Scoped`, bagaimana CLR dan runtime ASP.NET Core merespons saat *validation pipeline* dieksekusi? Tuliskan mekanisme internal bagaimana sebuah `IEndpointFilter` pada Minimal API dapat mengintersepsi *argument list*, mengeksekusi validasi secara manual, dan melakukan *short-circuiting* mengembalikan `TypedResults.ValidationProblem` sebelum delegate handler utama disentuh.

5. **Hedging Strategy & Algoritma Jitter pada Sistem Terdistribusi:**  
   Jelaskan cara kerja *Hedging* pada Polly v8 dibandingkan dengan *Retry*. Bagaimana *Hedging* mengeksekusi request cadangan secara paralel sebelum request pertama gagal, apa saja syarat mutlak idempotensi yang harus dipenuhi downstream API, dan mengapa menambahkan algoritma *Full Jitter* (misalnya Decorrelated Jitter) pada interval Retry sangat krusial untuk mencegah fenomena *Thundering Herd* pasca-insiden pemadaman layanan?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Thread Pool Starvation & Cascading Failure Incident
Sebuah platform E-Commerce berskala tinggi mengalami insiden kritis saat *Flash Sale*. Layanan *Payment Gateway* pihak ketiga mengalami peningkatan latensi drastis dari normalnya 150ms menjadi 45 detik per request, sebelum akhirnya *timed out*. 

Dalam waktu 3 menit, metrik Kestrel menunjukkan `Active Connections` melonjak, `ThreadPool.QueueLength` meningkat ribuan, CPU melompat ke 100%, dan seluruh API lain yang tidak berhubungan (seperti *Catalog* dan *Profile*) berhenti merespons (HTTP 503). Analisis log menunjukkan implementasi integrasi gateway menggunakan `HttpClientFactory` standar dengan `RetryPolicy` sederhana: mencoba kembali 5 kali secara sinkronis tanpa timeout granular, tanpa circuit breaker, dan tanpa jitter.

*   **Pertanyaan Diagnostik:**
    1. Mengapa latensi dari single dependency pihak ketiga dapat melumpuhkan seluruh aplikasi Kestrel secara global (*cascading failure* via *thread exhaustion*)?
    2. Rancang ulang topologi *Resilience Pipeline* menggunakan Polly v8 untuk integrasi gateway ini. Definisikan nilai timeout, circuit breaker threshold, rate limiter/bulkhead isolation, dan fallback policy yang tepat untuk mengisolasi kegagalan agar thread pool Kestrel tetap sehat.

### Skenario B: Race Condition, Double-Billing, & Non-Idempotent Retry
Sebuah aplikasi fintech mengimplementasikan *automatic retry* (3 kali percobaan dengan interval exponential backoff) pada method `ChargeCreditCardAsync()`. Pada saat lonjakan trafik, koneksi socket TCP terputus sesaat (*network blip*) tepat ketika bank pemroses telah berhasil mendebet dana nasabah, namun sebelum paket HTTP response 200 OK diterima oleh server aplikasi.

Sistem retry ASP.NET Core mendeteksi `HttpRequestException` (transient network fault) dan langsung mengeksekusi request retry kedua dan ketiga. Akibatnya, kartu kredit nasabah terdebet 3 kali untuk pesanan tunggal yang sama (*double/triple billing*).

*   **Pertanyaan Diagnostik:**
    1. Mengapa lapisan jaringan/HTTP tidak dapat menjamin idempotensi eksekusi secara otomatis pada level transmisi data?
    2. Rancang solusi arsitektur menyeluruh yang melibatkan *Idempotency-Key pattern*, modifikasi header HTTP, dan mekanisme state store (misal: Redis distributed lock/key validation) yang berkolaborasi dengan Polly Retry Pipeline untuk menjamin mutlak bahwa *transient failure* saat network timeout tidak akan pernah mengeksekusi mutasi ganda pada downstream payment core.

### Skenario C: Trade-off Arsitektur Validasi: Domain-Driven Validation vs External Pipeline
Tim engineering Anda sedang memperdebatkan lokasi terbaik penegakan validasi pada sistem *Core Banking*. 
*   **Faksi A:** Mengusulkan validasi total dilakukan secara deklaratif di lapisan luar (HTTP Request Pipeline) menggunakan FluentValidation dan Action/Endpoint Filters, sehingga *invalid state* langsung di-*short-circuit* sebelum mencapai lapisan aplikasi/domain.
*   **Faksi B:** Menolak Faksi A dan berargumen bahwa domain entity harus selalu *self-validating* (menggunakan Rich Domain Model, Value Objects, dan melemparkan `DomainValidationException` atau mengembalikan `Result<T>`), karena validasi di layer API rawan bocor saat entity yang sama dipanggil oleh Background Job, RabbitMQ consumer, atau gRPC channel.

*   **Pertanyaan Diagnostik:**
    1. Analisis *trade-off* mendalam performa, maintainability, dan keamanan dari kedua pendekatan tersebut. Apa bahaya laten validasi hanya di lapisan API terhadap *in-memory domain integrity*?
    2. Bagaimana arsitektur hibrida profesional dapat memisahkan antara *Input Format Validation* (structural/syntactic validation) dan *Domain Business Rules Validation* (semantic validation)? Bagaimana error dari kedua layer tersebut dipetakan secara seragam ke format respons RFC 7807 `ValidationProblemDetails` tanpa mengotori domain layer dengan ketergantungan framework ASP.NET Core?

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise Resilient Settlement Dispatcher
Rancang dan implementasikan sebuah *Mission-Critical Background & API Engine* untuk sistem Settlement FinTech yang mengintegrasikan mekanisme **Validasi Ketat**, **Global Error Handling berbasis RFC 7807**, dan **Fault Tolerance Pipeline berlapis** menggunakan .NET 8+.

#### 1. Problem Statement
Sistem harus menerima batch instruksi pembayaran settlement, memvalidasi integritas data finansial, mengirimkannya ke *Mock Third-Party Core Banking Engine* yang sengaja dibuat tidak stabil (*unstable*, melempar error HTTP 500, 408, 429, dan latensi acak), serta menangani setiap kegagalan tanpa crash, tanpa kehilangan data (*zero data loss*), dan tanpa membuat sistem kehabisan memori/thread.

#### 2. Technical Requirements
1. **Model & Syntactic Validation:**
   * Buat DTO `SettlementRequest`: `TransactionId` (Guid), `MerchantId` (String, format regex `MCH-[0-9]{5}`), `Amount` (Decimal, > 0, maks 2 digit desimal), `Currency` (ISO-4217, wajib IDR atau USD), `IdempotencyKey` (String, valid UUID v4).
   * Validasi dilakukan via `FluentValidation` menggunakan `IEndpointFilter` pada Minimal API. Validasi yang gagal harus otomatis menghasilkan RFC 7807 `ValidationProblemDetails` dengan status `400 Bad Request`.
2. **Global Exception Handling (.NET 8):**
   * Implementasikan `IExceptionHandler` kustom: `GlobalExceptionHandler` dan `FinancialDomainExceptionHandler`.
   * Tangani `DomainRuleViolationException` menjadi `422 Unprocessable Entity`.
   * Tangani kegagalan downstream/timeout menjadi `504 Gateway Timeout` atau `502 Bad Gateway` dengan payload ProblemDetails yang memiliki ekstensi `traceId` dan `timestampUtc`. Sembunyikan *stack trace* internal jika environment adalah *Production*.
3. **Resilience Strategy Composition (Polly v8):**
   * Gunakan `Microsoft.Extensions.Resilience` untuk menyusun `ResiliencePipeline` kustom yang membungkus pemanggilan `HttpClient` ke Core Banking:
     * **Total Timeout:** Membatasi seluruh siklus eksekusi maksimal 10 detik.
     * **Retry Strategy:** Maksimal 3 kali retry khusus untuk transient status codes (`500 Internal Server Error`, `502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`, dan `408 Request Timeout`), menggunakan *Decorrelated Jitter Exponential Backoff*.
     * **Circuit Breaker:** Membuka sirkuit jika rasio kegagalan mencapai 50% dari minimal 10 request dalam sampling duration 30 detik. Durasi break sirkuit adalah 15 detik.
     * **Concurrency Limiter / Bulkhead:** Batasi request paralel ke downstream banking maksimal 5 concurrent executions untuk mencegah resource exhaustion.
4. **Idempotency Protection:**
   * Buat cache layer (in-memory atau distributed) untuk memastikan request dengan `IdempotencyKey` yang sama dalam kurun waktu 1 jam tidak mengeksekusi downstream banking berulang kali, melainkan mengembalikan *cached response*.

#### 3. Constraints
* Dilarang menggunakan *legacy* Polly syntax (v7). Wajib menggunakan `ResiliencePipelineBuilder` atau extension method `AddResilienceHandler` pada `IHttpClientBuilder`.
* Dilarang menggunakan middleware kustom `app.Use(async (context, next) => ...)` untuk exception handling; gunakan native `builder.Services.AddExceptionHandler<T>()` dan `app.UseExceptionHandler()`.
* Performa pipeline tidak boleh mengalokasikan objek berlebih (*low allocation memory footprint*).

#### 4. Expected Output
* Kode C# lengkap yang terstruktur: Definisi Record/DTO, Validator, Exception classes, Exception Handlers, Registrasi Dependency Injection, Konfigurasi Resilience Pipeline, dan Endpoint Minimal API.
* Simulasi eksekusi downstream banking yang mendemonstrasikan transisi status: saat downstream mulai lambat/gagal, circuit breaker berpindah dari `Closed` -> `Open` (mengembalikan 503 dengan header `Retry-After`), dan mencoba kembali saat `Half-Open`.
* JSON payload respons saat terjadi validasi gagal yang mematuhi format RFC 7807.

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman Anda terhadap konsep bab ini. Tandai item yang telah Anda kuasai secara independen.

### Saya harus memahami:
- [ ] Arsitektur siklus hidup penanganan request ASP.NET Core: titik eksekusi Exception Handling Middleware, Endpoint Filters, Model Validation, dan Result Execution.
- [ ] Anatomi spesifikasi RFC 7807 / RFC 9457 (`ProblemDetails`, `ValidationProblemDetails`) dan pentingnya standardisasi machine-readable contract untuk response error.
- [ ] Mekanisme kerja `IExceptionHandler` pada .NET 8+, termasuk pola chaining multiple exception handlers dan penentuan nilai balik boolean `TryHandleAsync`.
- [ ] Perbedaan internal antara status `Closed`, `Open`, dan `Half-Open` pada Circuit Breaker Pattern, serta parameter matematik pembentuk *failure rate threshold*.
- [ ] Urutan pembungkusan (*wrapping order*) yang tepat saat mengombinasikan *Rate Limiting*, *Total Timeout*, *Retry*, *Circuit Breaker*, dan *Attempt Timeout* dalam Resilience Pipeline Polly v8.
- [ ] Bahaya race condition dan kegagalan ganda (*double-execution*) pada operasi non-idempoten yang dibungkus oleh Retry Policy, serta strategi mitigasinya menggunakan Idempotency-Key.
- [ ] Dampak buruk dari *sync-over-async* dan query database blocking di dalam pipeline validasi atau filter terhadap throughput Kestrel.

### Saya tidak perlu menghafal:
- [ ] Setiap properti ekstensi spesifik dari class `ProblemDetails` secara verbatim; Anda dapat melihat spesifikasi RFC atau dokumentasi Microsoft Docs saat dibutuhkan.
- [ ] Sintaks exact baris-per-baris dari konfigurasi objek Polly v8; Anda cukup memahami konsep strategi yang dikonfigurasi dan memanfaatkan Fluent Builder API / IntelliSense.
- [ ] Daftar lengkap semua kode error HTTP IANA; cukup kuasai pemetaan kategori utama (4xx Client Error vs 5xx Server Error) dan transient status codes yang umum (408, 429, 500, 502, 503, 504).

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan *Enterprise-Grade Global Error Handler* menggunakan `AddExceptionHandler<T>()` dan `ProblemDetails` yang aman dari *information disclosure* (menyembunyikan internal stack trace pada environment Production).
- [ ] Mengintegrasikan `FluentValidation` ke dalam Minimal API atau ASP.NET Core Controller menggunakan Endpoint Filters tanpa mengorbankan performa async.
- [ ] Mengonfigurasi `AddHttpClient` dengan Polly v8 Resilience Pipeline menggunakan `AddResilienceHandler`, mencakup kombinasi Timeout, Circuit Breaker, dan Jittered Retry.
- [ ] Mendiagnosis dan menghentikan insiden *cascading failure* di sistem produksi yang disebabkan oleh downstream API hang dan penumpukan thread Kestrel.
- [ ] Mencegah duplikasi data akibat transient failure pada jaringan dengan mengimplementasikan pola Idempotency Key pada lapisan Application Service.