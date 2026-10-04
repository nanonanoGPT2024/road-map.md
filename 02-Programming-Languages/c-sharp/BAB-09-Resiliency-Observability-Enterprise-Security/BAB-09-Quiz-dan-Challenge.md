# BAB 09: Quiz, Challenge, & Knowledge Check
**Resiliency, Observability & Enterprise Security**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Taksonomi Resiliency Pattern & Resource Isolation
Dalam rekayasa sistem terdistribusi menggunakan C# dan .NET, pola *Resilience* dirancang untuk mencegah kegagalan lokal merambat menjadi *cascading failure*. 
Jelaskan perbedaan mendasar antara pola **Bulkhead Isolation** dan **Rate Limiting** dari perspektif alokasi sumber daya komputasi (*thread pool*, *connection pool*, memori) runtime .NET! Kapan Anda harus mengombinasikan keduanya dalam sebuah *inbound request pipeline*?

### Soal 1.2: Anatomi Triad Observability Modern pada .NET Runtime
Ekosistem .NET 8/9 telah mengadopsi standar OpenTelemetry (OTel) secara *native* pada level *runtime BCL* tanpa memerlukan *third-party shim*. 
Jelaskan pemetaan komponen BCL berikut ke dalam 3 pilar Observability standar W3C/OpenTelemetry:
1. `System.Diagnostics.ActivitySource` & `System.Diagnostics.Activity`
2. `System.Diagnostics.Metrics.Meter` & `System.Diagnostics.Metrics.Counter<T>`
3. `Microsoft.Extensions.Logging.ILogger` dengan *Structured Logging* & *Message Templates*

Mengapa penggunaan string concatenation/interpolation langsung pada `ILogger` merupakan anti-pattern baik dari sisi observabilitas maupun performa memori (alokasi *heap*)?

### Soal 1.3: ASP.NET Core Data Protection API (DPAPI) vs Raw Cryptographic Primitives
Banyak engineer secara keliru mengimplementasikan enkripsi data *at-rest* menggunakan instansiasi manual `AesManaged` atau `AesGcm` untuk proteksi data stateful aplikasi.
Jelaskan arsitektur **ASP.NET Core Data Protection API**! Bagaimana sistem mengelola *Key Ring*, *Key Derivation*, *Key Rotation*, dan *Revocation* secara otomatis, serta pada skenario apa Anda **wajib** menggunakan Data Protection API dibandingkan menggunakan primitive class `System.Security.Cryptography.AesGcm` langsung?

### Soal 1.4: Verifikasi Kriptografis & Lifecycle Validasi JWT Bearer
Ketika memvalidasi *JSON Web Token* (JWT) di *edge* ASP.NET Core pipeline menggunakan `Microsoft.AspNetCore.Authentication.JwtBearer`, runtime mengeksekusi serangkaian validasi kriptografis dan klaim.
Bedah siklus validasi token di dalam `JwtSecurityTokenHandler` / `JsonWebTokenHandler`! Jelaskan peranan spesifik dari:
- `IssuerSigningKeyResolver` vs `ConfigurationManager<OpenIdConnectConfiguration>`
- Penanganan parameter `ClockSkew`
- Risiko kerentanan keamanan jika algoritma verifikasi diubah secara otomatis (*algorithm confusion attack*).

### Soal 1.5: Keamanan Memori untuk Data Sensitif (Zeroing Memory & Memory Pinning)
Tipe data `System.String` bersifat *immutable* dan dialokasikan pada Managed Heap di bawah kendali *Garbage Collector* (GC). 
Jelaskan risiko keamanan enterprise terkait siklus hidup objek string yang menyimpan informasi sensitif (seperti PIN, Private Key, atau Master Secret) di dalam memori proses! Bagaimana kombinasi tipe modern seperti `ReadOnlySpan<T>`, `byte[]`, `CryptographicOperations.ZeroMemory()`, dan `GC.AllocateArray<T>(..., pinned: true)` menyelesaikan kelemahan fundamental dari `String` maupun deprecated `SecureString`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Polly v8 ResiliencePipeline State Machine & Thundering Herd
Polly v8 memperkenalkan arsitektur baru berbasis `ResiliencePipeline` yang berfokus pada alokasi memori mendekati nol (*zero-allocation*) dan performa tinggi.
Analisis transisi *state machine* internal dari **Circuit Breaker** (`Closed`, `Open`, `Half-Open`)! Bagaimana mekanisme evaluasi kegagalan internal bekerja dalam menentukan batas transisi (*sampling duration*, *failure ratio*, dan *minimum throughput*)? Jika sebuah service mengalami pemulihan parsial dan masuk ke state `Half-Open`, bagaimana algoritma menangani konkurensi request yang masuk bersamaan untuk mencegah *Thundering Herd* ke upstream yang masih rentan?

### Soal 2.2: Context Propagation & AsyncLocal<T> Mechanics dalam Distributed Tracing
Distributed tracing membutuhkan propagasi konteks trace lintas batas asynchronous (`Task`) dan proses remote.
Bagaimana .NET mendistribusikan konteks `Activity.Current` menembus *thread switch* saat eksekusi `await` menggunakan infrastruktur `ExecutionContext` dan `AsyncLocal<T>`? Jelaskan mekanisme internal `DistributedContextPropagator` saat menginjeksi dan mengekstrak *W3C Trace Context headers* (`traceparent`, `tracestate`) pada `HttpClient` dan `ASP.NET Core Kestrel` pipeline!

### Soal 2.3: Analisis DiagnosticListener Leak & EventSource Contention
Sebuah microservice C# berkinerja tinggi mengalami peningkatan penggunaan memori yang tidak wajar (*memory leak*) dan penurunan throughput setelah dipasang custom logging and telemetry adapter.
Dari hasil memory dump analysis via `dotnet-dump`, ditemukan jutaan objek tertahan yang berakar dari subscription `DiagnosticListener.AllListeners`. Jelaskan secara teknis bagaimana mekanisme observer pattern pada `DiagnosticListener` dapat menyebabkan kebocoran memori jangka panjang jika siklus hidup *subscription* (`IDisposable`) dan payload event capture tidak diisolasi secara benar!

### Soal 2.4: Kriptografi Autentikasi: AES-GCM Nonce Reuse Catastrophe
Dalam .NET cryptography, `System.Security.Cryptography.AesGcm` menyediakan enkripsi terotentikasi (*Authenticated Encryption with Associated Data* / AEAD).
Mengapa penggunaan ulang *Nonce/IV* (Initialization Vector) yang sama dengan Secret Key yang sama pada algoritma AES-GCM dikategorikan sebagai kegagalan kriptografis fatal (*catastrophic failure*)? Bagaimana Anda merancang algoritma pembangkitan Nonce 12-byte yang aman secara deterministik dan thread-safe pada service multi-threaded yang memproses puluhan ribu request enkripsi per detik?

### Soal 2.5: Deep Dive: Policy-Based Dynamic Authorization Runtime Engine
Dalam enterprise authorization, ASP.NET Core memisahkan definisi otorisasi menjadi *Policies*, *Requirements*, dan *Handlers* (`IAuthorizationHandler`).
Jelaskan bagaimana runtime authorization engine mengevaluasi konteks ketika terdapat banyak handler untuk sebuah requirement tunggal (`context.Succeed()` vs `context.Fail()`)! Jika sebuah handler memanggil I/O asynchronous yang lambat untuk mengecek database permission, bagaimana Anda mengoptimasi evaluasi authorization pipeline tersebut agar tidak memicu kehabisan thread worker pada ThreadPool?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Cascading Failure Akibat Mis-konfigurasi Polly Retry & Thread-Pool Starvation
* **Latar Belakang**: Sebuah platform pembayaran memproses rata-rata 12.000 RPS. Komponen `PaymentGatewayService` memanggil downstream provider pihak ketiga via `HttpClient`. Ketika downstream provider mengalami latensi tinggi (dari 50ms melonjak menjadi 4500ms) akibat masalah database internal mereka, `PaymentGatewayService` milik Anda tiba-tiba mengalami crash bertingkat: CPU utilization mencapai 100%, ketersediaan worker thread pada ThreadPool mendekati 0 (*Thread Starvation*), dan service gagal merespons liveness health check Kubernetes hingga pod di-restart paksa secara berulang (*CrashLoopBackOff*).
* **Investigasi Awal**:
  Kode integrasi menggunakan implementasi retry pipeline berikut:
  ```csharp
  // Konfigurasi Resilience Pipeline Polly v8
  builder.AddRetry(new RetryStrategyOptions
  {
      MaxRetryAttempts = 5,
      Delay = TimeSpan.FromMilliseconds(100),
      BackoffType = DelayBackoffType.Constant
  });
  builder.AddTimeout(TimeSpan.FromSeconds(5));
  ```
  `HttpClient` tidak mengonfigurasi batas timeout internal, dan seluruh request menggunakan timeout default (100 detik).
* **Pertanyaan Diagnostik**:
  1. Bedah secara mekanistis mengapa strategi kombinasi Retry konstan (5x) dengan delay 100ms dan global timeout 5 detik di atas mempercepat degradasi sistem dan memicu *Self-Inflicted Denial of Service* (Cascading Collapse)!
  2. Susun ulang arsitektur pipeline ketahanan Polly v8 tersebut dengan mengurutkan secara tepat: *Rate Limiter*, *Total Timeout*, *Circuit Breaker*, *Attempt Timeout*, dan *Retry with Exponential Backoff + Jitter*. Jelaskan justifikasi matematis urutan penempatan (*layering execution order*) dari masing-masing middleware tersebut.

---

### Skenario B: Race Condition pada Stateful In-Memory Encryption Session
* **Latar Belakang**: Sebuah aplikasi FinTech memproses transfer dana volume tinggi. Untuk mematuhi standar PCI-DSS, payload request yang berisi nomor kartu kredit dienkripsi segera setelah didekode di Controller sebelum ditaruh ke queue. Tim engineering mengimplementasikan wrapper kriptografi AES-GCM berikut yang didaftarkan sebagai **Singleton** service:
  ```csharp
  public class AesGcmEncryptionService : ICryptoService
  {
      private readonly AesGcm _aesGcm;
      private readonly byte[] _key;

      public AesGcmEncryptionService(IConfiguration config)
      {
          _key = Convert.FromBase64String(config["MasterKey"]);
          _aesGcm = new AesGcm(_key, tagSizeInBytes: 16);
      }

      public EncryptedPayload Encrypt(ReadOnlySpan<byte> plaintext)
      {
          byte[] nonce = new byte[12];
          RandomNumberGenerator.Fill(nonce); // Cryptographically secure

          byte[] ciphertext = new byte[plaintext.Length];
          byte[] tag = new byte[16];

          _aesGcm.Encrypt(nonce, plaintext, ciphertext, tag); // Potensi Bottleneck / Exception

          return new EncryptedPayload(nonce, ciphertext, tag);
      }
  }
  ```
* **Insiden**: Di production dengan 32 core server dan beban konkurensi 15.000 RPS, log sistem dibanjiri oleh `CryptographicException: The operation failed because of an internal cryptographic error` secara intermiten, dan pada beberapa kondisi terjadi *silent payload corruption* di mana data didekripsi menjadi bit sampah.
* **Pertanyaan Diagnostik**:
  1. Identifikasi *root cause* dari error konkurensi di atas! Apakah instance `AesGcm` di .NET aman digunakan secara thread-safe lintas multi-thread konkruen? Bagaimana status underlying native provider (OpenSSL di Linux vs BCrypt di Windows) memengaruhi perilaku ini?
  2. Tuliskan refactoring arsitektur thread-safe berperforma tinggi untuk service ini tanpa menimbulkan alokasi objek GC yang masif pada pemrosesan throughput tinggi (misalnya pertimbangan penggunaan `ObjectPool<AesGcm>`, per-thread storage, atau ephemeral initialization).

---

### Skenario C: Cardinality Explosion & Tracing Overhead pada High-Throughput Service
* **Latar Belakang**: Layanan `OrderDispatchingEngine` Anda mengimplementasikan distributed tracing penuh menggunakan OpenTelemetry .NET SDK yang mengekspor data via gRPC ke OpenTelemetry Collector / Jaeger. Saat beban puncak (40.000 RPS), cluster APM (Collector & Jaeger backend) mengalami *out-of-memory*, dan service C# itu sendiri mengalami degradasi throughput hingga 35% dibandingkan saat telemetry dinonaktifkan.
* **Hasil Profiling**:
  Ditemukan kode instrumentasi berikut pada hot-path method pemrosesan order:
  ```csharp
  using (var activity = OrderActivitySource.StartActivity("ProcessOrder", ActivityKind.Internal))
  {
      activity?.SetTag("order.id", order.Id.ToString());
      activity?.SetTag("customer.email", order.CustomerEmail);
      activity?.SetTag("payload.raw", JsonSerializer.Serialize(order));
      activity?.AddEvent(new ActivityEvent("StateTransition", DateTimeOffset.UtcNow, 
          new ActivityTagsCollection { { "timestamp.ticks", DateTime.UtcNow.Ticks } }));
      
      // Pemrosesan domain logic
      await DispatchInternalAsync(order);
  }
  ```
* **Pertanyaan Diagnostik**:
  1. Tinjau implementasi di atas dari sudut pandang **Enterprise Security (Data Leakage/PII)** dan **Observability Performance (Cardinality Explosion & GC Overhead)**! Pelanggaran apa saja yang telah dilakukan?
  2. Rekomendasikan strategi komprehensif untuk memulihkan stabilitas sistem dengan menerapkan:
     - Teknik mitigasi alokasi string dan serialisasi JSON pada hot-path telemetry.
     - Strategi *Sampling* OpenTelemetry (bandingkan *Head-based Sampling* vs *Tail-based Sampling* untuk use case finansial).
     - Filtering sensitivitas data (PII Masking) sesuai standar PCI-DSS/GDPR.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Resilient & Cryptographically Audited Outbox Dispatcher

#### 1. Deskripsi Masalah
Sebagai Principal Architect pada core banking system, Anda diminta membangun core engine untuk **Transactional Outbox Dispatcher**. Komponen ini bertanggung jawab membaca batch transaksi finansial tertunda dari basis data dan mempublikasikannya ke downstream Payment Broker melalui REST API. Layanan ini beroperasi dalam domain *zero-trust*, rentan terhadap network latency, dan wajib dapat diaudit secara forensik dengan jejak trace W3C yang lengkap tanpa membocorkan data nasabah.

#### 2. Kebutuhan Teknis (Technical Requirements)
1. **Resilience Engine (Polly v8)**:
   - Buat `ResiliencePipeline<HttpResponseMessage>` terpusat menggunakan `ResiliencePipelineBuilder<HttpResponseMessage>`.
   - Konfigurasi pipeline harus mencakup:
     - **Attempt Timeout**: 1.5 detik per request attempt.
     - **Retry Policy**: Maksimal 3 retry, Exponential Backoff (base delay 200ms) dengan jitter penuh (*Decorrelated Jitter*), hanya bereaksi terhadap `HttpRequestException` dan HTTP Status Codes: 408, 429, 502, 503, 504.
     - **Circuit Breaker**: Transisi ke state `Open` jika failure rate >= 50% dalam rentang waktu sampling 10 detik dengan throughput minimum 20 transaksi. Durasi break: 5 detik.
     - **Total Pipeline Timeout**: 8 detik (membatasi total siklus eksekusi keseluruhan retry).
2. **Distributed Tracing & Metrics (OpenTelemetry Native)**:
   - Definisikan `ActivitySource` tersendiri dengan nama `"Enterprise.OutboxDispatcher"`.
   - Setiap pengiriman outbox event harus membungkus span `ActivityKind.Client` dengan W3C format context propagation manual ke headers `HttpClient`.
   - Catat custom business metrics menggunakan `System.Diagnostics.Metrics.Meter`:
     - `Counter<long>`: Total event terkirim (dengan tag: `status` = success/failure).
     - `Histogram<double>`: Durasi eksekusi dispatching HTTP call (dalam milliseconds).
3. **Hardware-Accelerated In-Memory Encryption (Payload Auditing)**:
   - Sebelum payload dikirimkan melalui jaringan, payload data sensitif (misal: JSON body) harus dienkripsi menggunakan `AesGcm` untuk kebutuhan *audit log record*.
   - Nonce (12-byte) harus dibangkitkan menggunakan `RandomNumberGenerator`.
   - Gunakan `ArrayPool<byte>.Shared` atau `Span<byte>` / stackalloc untuk alokasi buffer enkripsi guna mencapai performa *zero unnecessary heap allocations*.
   - Segera lakukan *zeroing memory* pada plaintext buffer setelah enkripsi selesai dengan memanggil `CryptographicOperations.ZeroMemory()`.

#### 3. Batasan Teknis (Constraints)
- Menggunakan standar C# modern (.NET 8/9 LTS target).
- **Zero Raw PII Leaks**: Dilarang merekam payload mentah, data email, nomor rekening, atau Plaintext Token ke dalam OTel Tags/Attributes ataupun log framework.
- Tidak boleh menggunakan `Polly` versi legacy (wajib syntax Polly v8 API: `Polly.ResiliencePipeline`).
- Solusi enkripsi harus aman terhadap akses multi-thread concurrent tanpa locking masif (`lock` object statement yang memblokir worker thread dilarang).

#### 4. Expected Output & Structure
Sajikan implementasi fungsional siap produksi dalam format C# source file terstruktur yang mencakup:
- Class `OutboxDispatcherService` yang memuat fungsi `DispatchTransactionAsync(TransactionPayload payload, CancellationToken ct)`.
- Inisialisasi thread-safe cryptographic buffer handler.
- Registrasi DI (`IServiceCollection`) lengkap untuk konfigurasi OpenTelemetry, Metric/Activity registration, dan Polly Resilience Pipeline.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan pemahaman materi tingkat lanjut Anda sebelum melanjutkan ke topik berikutnya:

### Saya harus memahami:
- [ ] Alur transisi status pada Circuit Breaker Pattern (Closed -> Open -> Half-Open) dan kondisi metrik matematis yang memicu transisi.
- [ ] Urutan eksekusi (*pipeline layering*) berbagai komponen ketahanan (Timeout vs Bulkhead vs Circuit Breaker vs Retry) di Polly v8.
- [ ] Peran `ActivitySource` dan `Activity` dalam BCL .NET serta korelasinya dengan OpenTelemetry Tracer dan Span.
- [ ] Mekanisme propagasi konteks trace melintasi thread pool via `ExecutionContext` dan `AsyncLocal<T>`, serta antar proses via W3C `traceparent`.
- [ ] Perbedaan implementasi metrik: `Counter`, `Histogram`, dan `ObservableGauge` pada BCL `System.Diagnostics.Metrics`.
- [ ] Cara kerja *Authenticated Encryption with Associated Data* (AEAD) khususnya AES-GCM (Ciphertext, Tag, Nonce) dan implikasi nonce reuse.
- [ ] Manajemen siklus hidup secret di memory dan mitigasi ancaman dump memori via GC-pinning dan `CryptographicOperations.ZeroMemory()`.
- [ ] Arsitektur Data Protection API (DPAPI) di ASP.NET Core: isolasi aplikasi, key escrow, dan sinkronisasi key ring terdistribusi (Redis/Blob).
- [ ] Lifecycle autentikasi JWT di ASP.NET Core: verifikasi signature, penanganan token revocation list, dan proteksi dari common claims vulnerabilities.
- [ ] Mekanisme evaluasi Policy-based Authorization (`IAuthorizationHandler`, `AuthorizationHandlerContext`) pada arsitektur Zero-Trust.

### Saya tidak perlu menghafal:
- [ ] Nilai byte-structure hexadecimal dari format W3C TraceContext specification RFC.
- [ ] Sintaks signature parameter dari semua overload `AesGcm.Encrypt` / `AesGcm.Decrypt`.
- [ ] Nama-nama field konstanta claim strings spesifik di `System.Security.Claims.ClaimTypes`.
- [ ] Implementasi algoritma hashing underlying kriptografis (seperti permutasi internal SHA256 atau AES S-box).
- [ ] Struktur internal implementasi class private runtime Polly v8 pipeline builder engine.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi Polly v8 `ResiliencePipeline` dengan strategi exponential backoff, jitter, circuit breaker, dan isolation timeout secara modular.
- [ ] Menginstrumentasikan source code dengan native .NET `ActivitySource` dan `Meter` tanpa menimbulkan memory leak atau degradasi CPU.
- [ ] Menganalisis traceparent distributed context dan mendiagnosis *broken trace context propagation* pada async boundary.
- [ ] Mengimplementasikan enkripsi dan dekripsi payload performa tinggi menggunakan `System.Security.Cryptography.AesGcm` secara thread-safe dan hemat alokasi heap.
- [ ] Membersihkan memori sensitif secara deterministik (*zeroing memory*) dari array/span untuk memitigasi memory dump attacks.
- [ ] Membangun custom authorization requirement dan handler asynchronous yang resilient terhadap dependency failure.
- [ ] Mengaudit log enterprise dan telemetry pipelines untuk memastikan kepatuhan regulasi terhadap kebocoran PII (Personally Identifiable Information).