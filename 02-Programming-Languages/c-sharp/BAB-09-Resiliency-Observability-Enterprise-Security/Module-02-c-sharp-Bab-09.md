# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 02-Programming-Languages | **Topik:** C# | **Bab 09:** Resiliency, Observability, & Enterprise Security

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Mengonstruksi Resiliency Pipeline Modern (Polly v8 API):** Mendesain dan mengimplementasikan strategi *hedging*, *adaptive rate limiting*, dan *stateful circuit breaker* berkinerja tinggi tanpa alokasi memori berlebih (`GC pressure`) menggunakan abstraksi `ResiliencePipelineBuilder`.
2. **Menguasai High-Performance Distributed Tracing & Metrics:** Mengintegrasikan **OpenTelemetry (OTel)** secara native di .NET 8/9 menggunakan `System.Diagnostics.ActivitySource` dan `System.Diagnostics.Metrics.Meter` dengan propagasi W3C TraceContext lintas *distributed boundaries*.
3. **Menerapkan Zero-Allocation Cryptography & Zero-Trust Security:** Mengamankan *data-at-rest* dan *data-in-transit* menggunakan algoritma modern authenticated encryption (AES-256-GCM, ChaCha20-Poly1305) memanfaatkan `Span<T>`, `ReadOnlySpan<T>`, `Memory<T>`, serta `CryptographicOperations.ZeroMemory` untuk memitigasi kebocoran *memory-dump attack*.
4. **Membangun Arsitektur Enterprise Terdistribusi:** Mengonfigurasi mTLS (*Mutual TLS*) tingkat kernel via `SocketsHttpHandler` dan integrasi *Secret Management* berbasis *Hardware Security Module* (HSM) / Azure Key Vault / AWS KMS menggunakan pola *Envelope Encryption*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **C# Tingkat Lanjut:** Pemahaman mendalam mengenai `Task`, `ValueTask`, `IAsyncEnumerable<T>`, `Span<T>`, `ReadOnlySpan<T>`, memori heap vs stack, dan cara kerja CLR ThreadPool.
* **Dasar Resiliency & Networking:** Pemahaman dasar konsep HTTP status codes, socket exhaustion, TCP keep-alive, DNS TTL, dan arsitektur microservices.
* **Dasar Keamanan Perangkat Lunak:** Pemahaman mengenai TLS handshake, enkripsi simetris vs asimetris, dan hashing.
* **Tooling:** .NET 8/9 SDK, Docker/Docker Compose (untuk Jaeger, Prometheus, dan OpenTelemetry Collector).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Polly v8 Architecture: Direct-Delegate Execution Graph
Polly v8 (`Microsoft.Extensions.Resilience`) merombak total arsitektur v7. Di Polly v7, eksekusi dilakukan berbasis rantai delegasi bersarang (*deeply nested delegate execution tree*) yang menghasilkan banyak alokasi heap (`Closure`, `ExecutionContext` capture, dan alokasi `Task<TResult>`). 

Polly v8 memperkenalkan arsitektur **Zero-Allocation Execution Pipeline**:
* Pipeline dikompilasi menjadi sebuah *array of strategy components*.
* Context diteruskan sebagai `ResilienceContext`, sebuah struktur objek yang di-pool secara internal (`ObjectPool<ResilienceContext>`).
* Pemanggilan fungsi dibungkus dalam non-allocating `ValueTask` loop, memotong alokasi memori hingga 95% dibanding v7, dan meningkatkan *throughput* eksekusi hingga 4x lipat.

```
Incoming Request -> [ResiliencePipeline]
                          │
  ┌───────────────────────┴───────────────────────┐
  ▼                                               ▼
[Rate Limiter Strategy]                  [Timeout Strategy]
  │ (Shared Token Bucket)                         │ (Cancel Token Registration)
  ▼                                               ▼
[Circuit Breaker Strategy]               [Hedging / Retry Strategy]
  │ (Atomic State Machine: CAS)                   │ (Parallel Execution Engine)
  └───────────────────────┬───────────────────────┘
                          ▼
            [User Target Delegate (HTTP/gRPC/DB)]
```

### 3.2 OpenTelemetry Internals: `ActivitySource` & `Meter` Engine
Arsitektur observabilitas modern di .NET tidak memerlukan SDK eksternal untuk melakukan instrumentasi tingkat kode. Runtime .NET menyediakan engine internal berkecepatan tinggi:

1. **Distributed Tracing (`System.Diagnostics.Activity`):**
   * Menggunakan model W3C TraceContext (`traceparent`, `tracestate`).
   * Konteks trace dialirkan melalui `AsyncLocal<T>`, yang melekat pada `ExecutionContext` dari suatu logical thread.
   * `ActivitySource.StartActivity` memanfaatkan pemeriksaan sampling internal (`ActivitySamplingResult`). Jika listener (OTel Collector) tidak mengaktifkan tracing atau melakukan drop pada trace tersebut, alokasi objek `Activity` bernilai `null` sehingga beban runtime mendekati 0ns.
2. **Metrics Engine (`System.Diagnostics.Metrics`):**
   * Menggunakan arsitektur multi-dimensional metrics via `Meter` dan `Counter<T>` / `Histogram<T>`.
   * Agregasi internal berbasis LMAX Disruptor / ring-buffer tanpa *lock contention* pada jalur metrik kritis.

```
Thread Execution -> Check Sampling (SamplingResult)
                         │
         ┌───────────────┴───────────────┐
         ▼ (Not Sampled)                 ▼ (Sampled)
   Return null                    Instantiate Activity
   (Zero-alloc / 0.5ns)           Inject to AsyncLocal<ActivityContext>
                                  Record Tags / Baggage
                                  Flush to Channel<BatchLogRecord>
```

### 3.3 Memory Cryptography: Span-Based & Anti-Memory Forensic
Operasi kriptografi konvensional yang menggunakan `byte[]` dan `string` rentan terhadap eksploitasi pembacaan memori (*core dump analysis*). Alokasi `byte[]` di LOH (Large Object Heap) atau Gen0/Gen1 tidak langsung dibersihkan oleh Garbage Collector, meninggalkan *plaintext* kunci enkripsi dalam RAM.

Arsitektur kriptografi modern di .NET menerapkan:
1. **`Span<byte>` Stack Allocation:** Memanfaatkan `stackalloc byte[N]` untuk buffer kunci/IV berukuran kecil, mengeliminasi alokasi heap sepenuhnya.
2. **`CryptographicOperations.ZeroMemory`:** Memastikan bahwa byte-byte sensitif di-overwrite secara deterministik dengan nilai nol menggunakan instruksi CPU yang tidak dapat dieliminasi oleh optimasi JIT Compiler (*dead-store elimination defense*).
3. **AEAD (Authenticated Encryption with Associated Data):** Menghilangkan serangan *bit-flipping* dengan menyematkan Authentication Tag (misalnya AES-GCM dengan 128-bit tag).

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal?
* **Polly v7 / Custom Retry Loops:** Mengakibatkan *resource starvation* dan *thundering herd problem* saat terjadi *cascading failure*. Custom `try-catch-retry` loop yang dibuat secara naif sering kali tidak memiliki *jitter*, membanjiri downstream service yang sedang *down*.
* **Logging Berbasis String (`ILogger.LogInformation($"User {id}")`):** Memaksa alokasi string formatting, *boxing* tipe data primitif, dan tidak memiliki konteks korelasi antar microservice.
* **Kriptografi Naif (AES-CBC + PKCS7):** Rentan terhadap *Padding Oracle Attacks* dan *Memory Dumping*, serta tidak memvalidasi integritas data payload secara terpadu.

### Apa Solusi Arsitektur Modern?
* **Adaptive Resilience:** Penerapan *Hedging* (mengirim request kedua secara paralel jika request pertama melewati batas latensi persentil P95/P99) dan *Distributed Rate Limiting* berbasis sliding window.
* **Native In-Process Observability:** Menggunakan *zero-dependency instrumentation* yang dikompilasi langsung di dalam BCL (*Base Class Library*), diekspor secara asynchronous via protokol standard OTLP (*OpenTelemetry Protocol*).
* **Authenticated Envelope Encryption:** Mengenkripsi data menggunakan *Data Encryption Key* (DEK) sekali pakai via AES-GCM, di mana DEK tersebut kemudian dienkripsi menggunakan *Key Encryption Key* (KEK) yang berada di dalam HSM (Hardware Security Module).

---

## 5. How (Workflow Detail)

Alur integrasi arsitektur produksi:
1. **Inbound Stage:** Request masuk melewati reverse proxy dengan header `traceparent` W3C.
2. **mTLS Handshake:** Kestrel atau `SocketsHttpHandler` memverifikasi validitas sertifikat X.509 klien menggunakan custom chaining validator.
3. **Resilience & Tracing Pipeline:**
   * Inisialisasi `Activity` OTel dan ekstraksi konteks korelasi.
   * Eksekusi request dialirkan ke dalam `ResiliencePipeline` Polly v8 (RateLimiter -> Timeout -> CircuitBreaker -> Hedging).
4. **Data Layer Protection:**
   * Payload sensitif dienkripsi menggunakan DEK ephemeral via `AesGcm` berbasis memory buffer `Span<byte>`.
   * Memori kunci dibersihkan menggunakan `CryptographicOperations.ZeroMemory`.
5. **Outbound Propagation:** Header `traceparent` diinjeksi ke panggilan HTTP downstream menggunakan `DistributedContextPropagator`.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem
* **Resiliency Pipeline seperti Katup Keselamatan Pembangkit Listrik:** Jika tekanan uap (request) terlalu tinggi, *Rate Limiter* membatasi aliran. Jika katup utama macet (*timeout/failure*), *Circuit Breaker* memutus aliran secara otomatis agar turbin tidak meledak (*cascading collapse*). *Hedging* seperti menyalakan generator cadangan saat generator utama terdeteksi melambat sebelum benar-benar mati.
* **Envelope Encryption seperti Brankas dalam Brankas:** Dokumen transaksi Anda dimasukkan ke dalam brankas portabel kecil (*DEK*). Kunci brankas kecil tersebut kemudian dimasukkan ke dalam brankas utama bank yang tahan ledakan dan tidak dapat dipindahkan (*KEK di dalam HSM*).

### Arsitektur End-to-End Enterprise
```
[Client Application]
       │
       │ (mTLS / HTTP/2 + W3C TraceContext)
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Kestrel Hosting / Reverse Proxy Layer                       │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Core Application Pipeline (.NET 8/9)                        │
│                                                             │
│ 1. Telemetry Capture (OpenTelemetry System.Diagnostics)    │
│    ├─ Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736            │
│    └─ Span ID:  00f067aa0ba902b7                           │
│                                                             │
│ 2. Polly v8 Execution Pipeline Engine                       │
│    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│    │ Rate Limiter │──>│ Circ.Breaker │──>│   Hedging    │   │
│    └──────────────┘   └──────────────┘   └──────────────┘   │
│                                                             │
│ 3. Security Engine (Envelope Encryption)                    │
│    ├─ Plaintext Data -> AES-256-GCM (Span<byte>)            │
│    ├─ Ephemeral DEK  -> ZeroMemory on Dispose               │
│    └─ Key Encryption -> Cloud HSM / Key Vault (KEK)         │
└──────┬──────────────────────────────────────────────────────┘
       │
       ├──────────────────────────────┬───────────────────────┐
       ▼                              ▼                       ▼
┌──────────────┐              ┌──────────────┐        ┌──────────────┐
│  Downstream  │              │ OTLP Exporter│        │ Database     │
│  Microservice│              │ Collector    │        │ (Encrypted)  │
└──────────────┘              └──────────────┘        └──────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Polly v8 Basic Pipeline Definition
Implementasi dasar konfigurasi pipeline Polly v8 menggunakan dependency injection.

```csharp
using Microsoft.Extensions.DependencyInjection;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;
using System.Net.Sockets;

var services = new ServiceCollection();

// Registrasi Polly Resilience Pipeline v8
services.AddResiliencePipeline("default-pipeline", builder =>
{
    builder
        .AddRetry(new RetryStrategyOptions
        {
            ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>().Handle<SocketException>(),
            MaxRetryAttempts = 3,
            BackoffType = DelayBackoffType.Exponential,
            UseJitter = true,
            Delay = TimeSpan.FromMilliseconds(200)
        })
        .AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            FailureRatio = 0.5, // 50% kegagalan memicu Open State
            SamplingDuration = TimeSpan.FromSeconds(10),
            MinimumThroughput = 8,
            BreakDuration = TimeSpan.FromSeconds(30)
        })
        .AddTimeout(TimeSpan.FromSeconds(2));
});

var serviceProvider = services.BuildServiceProvider();
var pipelineProvider = serviceProvider.GetRequiredService<ResiliencePipelineProvider<string>>();
var pipeline = pipelineProvider.GetPipeline("default-pipeline");

// Eksekusi tanpa alokasi memori redundan
await pipeline.ExecuteAsync(async cancellationToken =>
{
    // Simulasi eksekusi I/O
    await Task.Delay(50, cancellationToken);
});
```

### 7.2 Practical Example: Enterprise Zero-Trust Resilient Client
Implementasi produksi yang menggabungkan:
1. Polly v8 Hedging Pipeline
2. Native OpenTelemetry Tracing & Metrics
3. Span-based AES-GCM Zero-Allocation Cryptography

```csharp
using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Security.Cryptography;
using Microsoft.Extensions.Logging;
using Polly;
using Polly.Hedging;

namespace Enterprise.Core.Architecture;

public sealed class TelemetryConstants
{
    public const string ServiceName = "Enterprise.OrderGateway";
    public static readonly ActivitySource ActivitySource = new(ServiceName, "1.0.0");
    public static readonly Meter Meter = new(ServiceName, "1.0.0");
    public static readonly Counter<long> EncryptedPayloadCounter = Meter.CreateCounter<long>(
        name: "security.payloads_encrypted_total",
        unit: "{payloads}",
        description: "Jumlah total payload yang dienkripsi secara aman.");
}

public interface ISecureVaultService
{
    Task<byte[]> EncryptSensitivePayloadAsync(ReadOnlyMemory<byte> plaintext, CancellationToken ct);
}

public sealed class EnterpriseSecureService : ISecureVaultService, IDisposable
{
    private readonly ResiliencePipeline _resiliencePipeline;
    private readonly ILogger<EnterpriseSecureService> _logger;
    private readonly byte[] _masterKek; // Simulasi KEK dari Hardware Security Module (HSM)

    public EnterpriseSecureService(ILogger<EnterpriseSecureService> logger)
    {
        _logger = logger;
        _masterKek = RandomNumberGenerator.GetBytes(32); // 256-bit Key

        // Konfigurasi Polly v8: Pipeline dengan Hedging untuk menjamin P99 latency
        _resiliencePipeline = new ResiliencePipelineBuilder()
            .AddHedging(new HedgingStrategyOptions
            {
                MaxHedgedAttempts = 2,
                Delay = TimeSpan.FromMilliseconds(150), // Kirim request paralel jika > 150ms
                ShouldHandle = new PredicateBuilder().Handle<TimeoutException>().Handle<HttpRequestException>()
            })
            .AddTimeout(TimeSpan.FromSeconds(1))
            .Build();
    }

    public async Task<byte[]> EncryptSensitivePayloadAsync(ReadOnlyMemory<byte> plaintext, CancellationToken ct)
    {
        using Activity? activity = TelemetryConstants.ActivitySource.StartActivity(
            "EnterpriseSecureService.EncryptSensitivePayload", 
            ActivityKind.Internal);

        activity?.SetTag("security.algorithm", "AES-256-GCM");
        activity?.SetTag("payload.size_bytes", plaintext.Length);

        return await _resiliencePipeline.ExecuteAsync(async state =>
        {
            // Menjalankan enkripsi data-at-rest dengan zero-memory leak guarantees
            byte[] encryptedBuffer = PerformAesGcmEncryption(plaintext.Span);
            TelemetryConstants.EncryptedPayloadCounter.Add(1, new KeyValuePair<string, object?>("status", "success"));
            return await ValueTask.FromResult(encryptedBuffer);
        }, ct);
    }

    private byte[] PerformAesGcmEncryption(ReadOnlySpan<byte> plaintext)
    {
        // Alokasi stack/heap terkontrol: Nonce (12 bytes), Tag (16 bytes)
        byte[] result = new byte[12 + 16 + plaintext.Length];
        Span<byte> nonce = result.AsSpan(0, 12);
        Span<byte> tag = result.AsSpan(12, 16);
        Span<byte> ciphertext = result.AsSpan(28, plaintext.Length);

        // Menghasilkan Nonce aman cryptographically
        RandomNumberGenerator.Fill(nonce);

        // Deklarasi Ephemeral DEK (Data Encryption Key) pada stack
        Span<byte> ephemeralDek = stackalloc byte[32];
        try
        {
            RandomNumberGenerator.Fill(ephemeralDek);

            using var aesGcm = new AesGcm(ephemeralDek, 16);
            aesGcm.Encrypt(nonce, plaintext, ciphertext, tag);

            return result;
        }
        finally
        {
            // Defense-in-depth: Hapus DEK dari CPU stack frame secara deterministik
            CryptographicOperations.ZeroMemory(ephemeralDek);
        }
    }

    public void Dispose()
    {
        CryptographicOperations.ZeroMemory(_masterKek);
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Tier-1 Payment Processing Core (50.000 TPS)

#### Problem
Sistem *Core Banking Payment Gateway* di sebuah bank multinasional mengalami insiden kritis saat event diskon nasional. 
* **Gejala:** 
  1. Latensi P99 melompat dari 45ms ke 12.800ms.
  2. Terjadi *Thread Pool Starvation* masif (alokasi thread melonjak dari 150 ke 3.000+ thread).
  3. Server OOM (Out Of Memory) akibat dump string HTTP client dan kegagalan logging.
  4. Database downstream mengalami lockup karena diterpa *cascading retries* jutaan request secara sinkron.

#### Root Cause Analysis
1. Arsitektur lama menggunakan Polly v7 dengan `WaitAndRetry` tanpa *jitter*, mengakibatkan efek *thundering herd* langsung ke database.
2. Logging logging payload kartu kredit secara mentah memicu *Garbage Collector Gen2 pause* berdurasi 3-4 detik.
3. Ketiadaan *Distributed Context Propagation* membuat teknisi buta atas microservice mana yang mengalami deadlock pertama kali.

#### Solusi Arsitektur Baru
1. **Penerapan Hedging + Circuit Breaker Polly v8:**
   * Menerapkan Hedging pada downstream database read-replicas dengan ambang batas latensi 80ms.
   * Mengaktifkan *Consecutive Failures Circuit Breaker* dengan *Jittered Exponential Backoff* untuk memulihkan database master.
2. **Standardisasi OpenTelemetry Native:**
   * Mengeliminasi Serilog string interpolations di jalur kritis dan menggantikannya dengan `System.Diagnostics.ActivitySource` + OTLP exporter over gRPC.
3. **Kriptografi Terisolasi Memory-Safe:**
   * Proteksi token PAN (Primary Account Number) menggunakan `AesGcm` berbasis `Span<byte>` dengan *Envelope Encryption* (DEK/KEK).

#### Metrik Hasil Perbaikan
| Parameter | Arsitektur Lama | Arsitektur Baru (Implementasi Modul Ini) |
|---|---|---|
| Latensi P99 | 12.800 ms | **58 ms** |
| Throughput Maksimal | 8.200 TPS (Jatuh) | **54.000 TPS (Stabil)** |
| ThreadPool Thread Count | 3.200 (Starvation) | **145 (Rata-rata terkelola)** |
| Alokasi Memori GC per Detik | 1.8 GB / det | **110 MB / det** |
| Waktu MTTR (Mean Time to Resolution) | 45 Menit | **2 Menit (Terdeteksi via Jaeger Trace Context)** |

---

## 9. Trade-offs

Setiap keputusan arsitektur tingkat enterprise memiliki konsekuensi desain.

```
       [High Resiliency / Hedging]
                 ▲
                / \
               /   \  Trade-off: Resource Consumption
              /     \
             /       \
[Low Latency]─────────[Low Compute Cost]
```

### 1. Resiliency (Hedging vs. Resource Amplification)
* **Keuntungan:** Hedging memotong tail-latency (P95/P99) secara dramatis dengan mengeksekusi request kedua secara bersamaan jika yang pertama lambat.
* **Kerugian:** Jika salah dikalibrasi, Hedging akan melipatgandakan beban traffic backend hingga 200%. Hanya gunakan hedging pada operasi yang bersifat *idempotent* dan miliki ambang delay batas atas persentil P90.

### 2. Observability (Full Distributed Tracing vs. Network/Memory Overhead)
* **Keuntungan:** 100% Trace Sampling menjamin visibilitas atas setiap anomali dan error yang terjadi di sistem.
* **Kerugian:** Pada skala 50.000 TPS, tracing 100% memproduksi puluhan gigabyte data telemetri per menit, membebani jaringan dan storage collector.
* **Mitigasi:** Terapkan *Adaptive Head-based Sampling* (misal: 5% untuk traffic normal, 100% untuk status code error atau request berlatensi tinggi).

### 3. Cryptography (Envelope Encryption vs. Compute Latency)
* **Keuntungan:** Perlindungan tingkat militer terhadap kebocoran kunci dan *data tampering*.
* **Kerugian:** Enkripsi AES-GCM menambahkan overhead komputasi CPU sebesar 2-5% dan latensi sekitar 5-15 mikrosekon per operasi. Jika diimplementasikan menggunakan alokasi heap `byte[]`, dapat memicu eskalasi GC. Wajib menggunakan `Span<byte>` dan `stackalloc`.

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Tidak Menerapkan Jitter pada Konfigurasi Retry
```csharp
// SALAH (Menyebabkan Thundering Herd ke downstream backend)
BackoffType = DelayBackoffType.Constant,
Delay = TimeSpan.FromSeconds(1)

// BENAR (Menghasilkan persebaran request secara stochastic)
BackoffType = DelayBackoffType.Exponential,
UseJitter = true,
Delay = TimeSpan.FromMilliseconds(200)
```

### Mistake 2: Membocorkan Memori Kriptografi (*Key Residue in Dump*)
```csharp
// SALAH: Key tetap berada di Large Object Heap dan tidak pernah dibersihkan
byte[] key = GetSecretKeyFromVault();
var aes = Aes.Create();
aes.Key = key; // GC tidak menghapus array saat di-collect

// BENAR: Memori dihapus paksa dari memori sesaat setelah dipakai
Span<byte> key = stackalloc byte[32];
RandomNumberGenerator.Fill(key);
try {
    // Jalankan enkripsi...
} finally {
    CryptographicOperations.ZeroMemory(key);
}
```

### Mistake 3: Memutus Trace Context Saat Menyeberang Async Boundary Naif
* **Penyebab:** Menggunakan `Task.Run` dengan `ExecutionContext.SuppressFlow()` atau thread kustom tanpa menyematkan konteks `Activity.Current`.
* **Solusi/Troubleshooting:** Jangan memutus `ExecutionContext`. Pastikan tracing header (`traceparent`) selalu diinjeksi saat menggunakan `HttpClient` melalui delegating handler:

```csharp
DistributedContextPropagator.Current.Inject(
    activity, 
    httpRequestMessage, 
    static (carrier, key, value) => carrier.Headers.TryAddWithoutValidation(key, value));
```

### Debugging & Troubleshooting Guideline
1. **Gejala Circuit Breaker Tidak Pernah Terbuka:**
   * Verifikasi parameter `MinimumThroughput`. Jika throughput aktual di bawah batas minimum throughput dalam jendela `SamplingDuration`, status breaker tidak akan pernah berubah ke *Open* meskipun failure rate mencapai 100%.
2. **Activity Context Bernilai Null:**
   * Pastikan `ActivitySource` diinisialisasi dengan nama dan versi yang tepat sama dengan konfigurasi builder `AddSource("NamaService")` di konfigurasi OpenTelemetry SDK.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis sistem ke production:

- [ ] **Resilience:** Semua pipeline *Hedging* dibatasi hanya pada request yang bersifat strictly *Idempotent* (GET, PUT terproteksi, idempotent POST).
- [ ] **Resilience:** Circuit Breaker dikonfigurasi dengan fallback degradation yang jelas (*graceful degradation*), bukan melempar generic exception ke user.
- [ ] **Observability:** `ActivitySource` dan `Meter` dideklarasikan sebagai instance `static readonly` per library/domain class untuk mencegah overhead reinstansiasi.
- [ ] **Observability:** Menggunakan *Semantic Conventions* resmi OpenTelemetry untuk penamaan tags (misal: `http.request.method`, `server.address`).
- [ ] **Observability:** Sampling rate diatur secara dinamis pada level Collector untuk request non-error (maksimal 5-10% di baseline high-traffic).
- [ ] **Security:** Menggunakan AES-GCM atau ChaCha20-Poly1305. Tidak menggunakan algoritma usang seperti AES-CBC, DES, atau 3DES.
- [ ] **Security:** Setiap variabel array sensitif (dekripsi password/kunci) wajib dibersihkan secara deterministik via `CryptographicOperations.ZeroMemory` di dalam blok `finally`.
- [ ] **Security:** mTLS diaktifkan pada layer komunikasi internal antar service, memverifikasi *Thumbprint* dan *Revocation List* (CRL) secara berkala.

---

## 12. Hands-on Practice

Buatlah struktur folder `hands-on/m02/` dan implementasikan micro-architecture lengkap berikut:

### Langkah 1: Inisialisasi Proyek
```bash
mkdir -p hands-on/m02/EnterpriseCoreArchitecture
cd hands-on/m02/EnterpriseCoreArchitecture
dotnet new webapi -f net8.0
dotnet add package Microsoft.Extensions.Resilience --version 8.10.0
dotnet add package OpenTelemetry.Exporter.Console --version 1.9.0
dotnet add package OpenTelemetry.Extensions.Hosting --version 1.9.0
```

### Langkah 2: Buat Pipeline dan Cryptography Handler
Simpan kode berikut di `hands-on/m02/EnterpriseCoreArchitecture/Program.cs`:

```csharp
using System.Diagnostics;
using System.Security.Cryptography;
using Microsoft.AspNetCore.Mvc;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using Polly;

var builder = WebApplication.CreateBuilder(args);

// 1. Setup OpenTelemetry Core
var activitySource = new ActivitySource("Enterprise.HandsOn.Service", "1.0.0");
builder.Services.AddOpenTelemetry()
    .ConfigureResource(r => r.AddService("Enterprise.HandsOn.Service"))
    .WithTracing(tracing => tracing
        .AddSource("Enterprise.HandsOn.Service")
        .AddAspNetCoreInstrumentation()
        .AddConsoleExporter());

// 2. Setup Polly v8 Resilience Pipeline
builder.Services.AddResiliencePipeline("financial-pipeline", pipeline =>
{
    pipeline.AddTimeout(TimeSpan.FromSeconds(2))
            .AddRetry(new()
            {
                MaxRetryAttempts = 2,
                BackoffType = DelayBackoffType.Exponential,
                UseJitter = true
            });
});

var app = builder.Build();

app.MapPost("/process-payment", async (
    [FromBody] PaymentRequest request,
    [FromServices] ResiliencePipelineProvider<string> pipelineProvider) =>
{
    using var activity = activitySource.StartActivity("ProcessPaymentTransaction", ActivityKind.Server);
    activity?.SetTag("payment.account_id", request.AccountId);

    var pipeline = pipelineProvider.GetPipeline("financial-pipeline");

    return await pipeline.ExecuteAsync(async ct =>
    {
        // Enkripsi Payload Sensitif dengan Zero-Memory Allocation
        Span<byte> encryptedData = stackalloc byte[12 + 16 + 32]; // Nonce + Tag + Mock Ciphertext (32 bytes)
        Span<byte> key = stackalloc byte[32];
        
        try
        {
            RandomNumberGenerator.Fill(key);
            RandomNumberGenerator.Fill(encryptedData[..12]); // Nonce

            using var aes = new AesGcm(key, 16);
            ReadOnlySpan<byte> mockPayload = stackalloc byte[32]; // Simulasi PAN data
            aes.Encrypt(encryptedData[..12], mockPayload, encryptedData[28..], encryptedData.Slice(12, 16));

            activity?.SetTag("payment.status", "encrypted_and_processed");
            return Results.Ok(new { Status = "Processed", Nonce = Convert.ToBase64String(encryptedData[..12].ToArray()) });
        }
        finally
        {
            // Sanitasi Memori
            CryptographicOperations.ZeroMemory(key);
            CryptographicOperations.ZeroMemory(encryptedData);
        }
    });
});

app.Run();

public record PaymentRequest(string AccountId, decimal Amount);
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan aplikasi dan lakukan trigger request:
```bash
dotnet run
# Buka terminal lain:
curl -X POST http://localhost:5000/process-payment \
   -H "Content-Type: application/json" \
   -d '{"accountId":"ACC-9921", "amount": 1500000}'
```
Perhatikan *console trace output* yang mendokumentasikan rentang eksekusi Activity secara lengkap tanpa memicu alokasi memori GC.

---

## 13. Exercise

### Level Easy
Ubah implementasi `RetryStrategyOptions` pada pipeline di sesi hands-on agar:
1. Hanya melakukan retry pada status exception `TimeoutException`.
2. Batas maksimum percobaan retry diatur menjadi 4 kali.
3. Mencetak log pesan peringatan (*warning*) setiap kali terjadi retry menggunakan delegate event `OnRetry`.

### Level Medium
Implementasikan sebuah `DelegatingHandler` custom bernama `TracingContextEnrichmentHandler` untuk `HttpClient`:
1. Mengekstrak span ID dan trace ID aktif dari `Activity.Current`.
2. Menginjeksi header `traceparent` (sesuai format standar W3C) ke outgoing HTTP request header.
3. Menambahkan metrik counter `http.client.requests_forwarded` menggunakan `System.Diagnostics.Metrics.Meter`.

### Level Hard
Bangun implementasi kelas thread-safe `RotatingKeyEnvelopeEncryptor`:
1. Memiliki `ConcurrentDictionary` internal yang menampung Key ID (UUID) dan Key Material terenkripsi.
2. Melakukan rotasi ephemeral DEK otomatis setiap 1.000 kali proses enkripsi atau setiap 5 menit (mana yang tercapai lebih dulu).
3. Seluruh alokasi kriptografi tidak boleh menghasilkan alokasi string intermediate untuk representasi data heksadesimal atau Base64 di jalur eksekusi enkripsi (wajib menggunakan `System.Buffers.Text.Base64` langsung ke target buffer `Span<byte>`).

---

## 14. Challenge

### Studi Kasus Arsitektur: "The Black Friday Zero-Downtime Payment Resilient Engine"

#### Skenario Masalah
Anda adalah Principal Architect pada sistem checkout e-commerce tier-1. Sistem backend Anda bergantung pada tiga *3rd-party Payment Service Providers* (PSP):
1. **PSP-A:** Biaya transaksi murah, namun kerap mengalami lonjakan latensi (P99 > 3000ms) di jam sibuk.
2. **PSP-B:** Sangat stabil (P99 < 80ms), namun mengenakan biaya 3x lipat dibanding PSP-A.
3. **PSP-C:** Sistem warisan (*legacy*), rentan *crash* total jika menerima lebih dari 500 TPS (harus dilindungi dengan ketat).

#### Misi Desain Anda
Desain arsitektur berbasis C# (.NET 8/9) dengan spesifikasi:
1. **Dynamic Adaptive Routing & Hedging:** Request checkout pertama secara *default* dikirimkan ke PSP-A. Jika PSP-A tidak merespons dalam 120ms, sistem harus segera melepaskan Hedging Request ke PSP-B secara paralel tanpa membatalkan koneksi PSP-A. Response tercepat yang valid digunakan, dan request yang lambat dibatalkan.
2. **Active Circuit Tripping & Cascade Shield:** Jika PSP-A gagal sebanyak 10 kali berturut-turut, seluruh traffic dialihkan sepenuhnya ke PSP-B selama jendela pemulihan 60 detik. PSP-C hanya digunakan sebagai fallback darurat dengan batasan `RateLimiter` lokal ketat maksimum 450 TPS.
3. **Forensic Traceability:** Setiap langkah branching hedging wajib terekam dalam satu Trace Session terpadu di OpenTelemetry dengan representasi span hierarkis:
   * Parent Span: `Order-Payment-Execution`
   * Child Span A: `PSP-A-Attempt`
   * Child Span B: `PSP-B-Hedged-Attempt`
4. **Data Privacy Guard:** Seluruh informasi nomor kartu kredit harus dienkripsi dengan AES-256-GCM. Kunci enkripsi DEK tidak boleh bertahan lebih dari 0 tick di LOH/heap, dan diverifikasi bersih dari snapshot memory dump.

Rancang arsitektur ini, tuliskan skema dependensi modul, dan konstruksikan *Production-Ready Implementation Class* intinya!

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (5 Soal)
1. **Apa perbedaan mendasar eksekusi internal antara Polly v8 dengan Polly versi terdahulu?**
   * A. Polly v8 menghilangkan integrasi async-await.
   * B. Polly v8 menggantikan nested delegate trees dengan loop eksekusi berbasis array pipeline yang meminimalisasi alokasi heap.
   * C. Polly v8 hanya mendukung protocol gRPC.
   * D. Polly v8 menghapus fitur Circuit Breaker.
2. **Struktur data mana yang digunakan .NET untuk menyalurkan konteks korelasi tracing antar logical thread secara implisit?**
   * A. `ThreadLocal<T>`
   * B. `ConcurrentStack<T>`
   * C. `AsyncLocal<T>`
   * D. `GC.KeepAlive<T>`
3. **Mengapa algoritma AES-GCM lebih direkomendasikan untuk keamanan enterprise dibandingkan AES-CBC?**
   * A. AES-GCM berjalan di layer kernel mode.
   * B. AES-GCM menyediakan integritas data terotentikasi (AEAD) secara native, mencegah modifikasi ciphertext (*bit-flipping*).
   * C. AES-GCM tidak membutuhkan kunci simetris.
   * D. AES-GCM mengompresi payload secara otomatis.
4. **Apa fungsi utama dari `CryptographicOperations.ZeroMemory`?**
   * A. Mengalokasikan array kosong dengan performa tinggi.
   * B. Menghapus data sensitif secara deterministik di memori agar tidak dieliminasi oleh optimasi JIT compiler.
   * C. Membebaskan objek dari pemantauan Garbage Collector.
   * D. Mengisi memori dengan angka acak kriptografi.
5. **Format standar yang digunakan OpenTelemetry untuk header propagasi HTTP terdistribusi adalah:**
   * A. B3 Single Header
   * B. X-Correlation-ID
   * C. W3C TraceContext (`traceparent`)
   * D. OpenTracing Base64

### Bagian B: Konsep Lanjutan (5 Soal)
6. **Kapan strategi Polly Hedging paling tepat digunakan dalam arsitektur microservices?**
   * A. Pada operasi mutasi non-idempotent seperti transfer dana.
   * B. Pada operasi baca idempotent dengan batasan latensi P99 ketat yang memiliki redundansi backend.
   * C. Saat downstream service sedang mengalami kehabisan memori total (OOM).
   * D. Untuk menggantikan fungsi database index.
7. **Mengapa pemeriksaan `ActivitySource.StartActivity` dapat menghasilkan nilai `null`?**
   * A. Karena terjadi memory leak pada CLR runtime.
   * B. Karena listener (OpenTelemetry SDK) tidak mengaktifkan sampling untuk activity tersebut.
   * C. Karena ActivitySource tidak didukung di sistem operasi Linux.
   * D. Karena traceparent header korup.
8. **Bahaya utama dari penggunaan `stackalloc Span<byte>` di C# tanpa batasan ukuran yang valid adalah:**
   * A. Terjadinya `StackOverflowException` yang langsung mematikan proses runtime secara instan.
   * B. Memperlambat kinerja Garbage Collection Gen0.
   * C. Mengunci alokasi memori LOH secara permanen.
   * D. Objek otomatis dipindahkan ke Paged Memory di hard disk.
9. **Dalam implementasi Circuit Breaker, apa yang dimaksud dengan kondisi state `Half-Open`?**
   * A. Sistem mematikan seluruh logging telemetri.
   * B. Sistem mengizinkan sejumlah kecil traffic percobaan melintas untuk memvalidasi apakah downstream service telah pulih.
   * C. Sistem menolak 50% traffic secara acak.
   * D. Sistem menduplikasi seluruh request ke monitoring pipeline.
10. **Bagaimana cara mencegah DNS Resolution Stale saat memanggil microservice via `HttpClient` yang dibungkus resilience pipeline?**
    * A. Melakukan re-instansiasi `HttpClient` baru setiap kali request.
    * B. Mengonfigurasi `PooledConnectionLifetime` pada `SocketsHttpHandler`.
    * C. Mematikan fitur keep-alive pada HTTP headers.
    * D. Menggunakan IP address mentah secara langsung.

### Bagian C: Skenario Kasus Produksi (3 Soal)
11. **Skenario 1:** Sebuah microservice pemrosesan klaim asuransi mengalami lonjakan latensi ekstrem. Tim telemetri melihat bahwa ribuan trace span terputus (orphan traces) ketika alur program memanggil library pihak ketiga yang memproses dokumen via event internal. Apa solusi struktural di .NET untuk mengikat kembali korelasi trace tersebut?
12. **Skenario 2:** Database cluster Anda sering mengalami crash total setiap kali terjadi downtime singkat selama 3 detik. Investigasi menunjukkan bahwa saat database kembali menyala, terjadi lonjakan 40.000 query secara instan dari aplikasi .NET. Fitur dan konfigurasi apa pada resilience engine yang wajib ditambahkan untuk menghentikan fenomena ini?
13. **Skenario 3:** Tim keamanan siber (SecOps) menemukan bahwa kunci dekripsi data pelanggan dapat diekstraksi dari dump RAM server aplikasi saat crash. Padahal kode telah membungkus kunci menggunakan variabel lokal di dalam fungsi private. Mengapa hal ini bisa terjadi dan bagaimana arsitektur penanganannya di C#?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A & B
1. **B** | Loop berbasis array internal di Polly v8 memotong alokasi heap delegasi bersarang.
2. **C** | `AsyncLocal<T>` mengalirkan konteks eksekusi otomatis melintasi async-await state machine.
3. **B** | Modus GCM mengautentikasi keaslian ciphertext via authentication tag terintegrasi.
4. **B** | JIT optimization sering kali mengabaikan manipulasi penulisan array jika variabel tersebut tidak lagi dibaca (*dead-store*). `ZeroMemory` menggunakan intrinsic barrier untuk memaksakan pembersihan fisik RAM.
5. **C** | W3C TraceContext mendefinisikan standar `traceparent` dan `tracestate`.
6. **B** | Hedging mengeksekusi request spekulatif paralel, sehingga operasi harus strictly idempotent agar tidak menduplikasi mutasi data.
7. **B** | Null-object pattern dioptimalkan runtime jika tidak ada observer/sampler yang mendengarkan `ActivitySource`.
8. **A** | Stack frame terbatas ukurannya (biasanya 1MB). Melebihi batas stackalloc akan memicu crash OS unrecoverable tanpa `catch` block.
9. **B** | *Half-Open* adalah fase transisi evaluasi kesiapan backend downstream.
10. **B** | `PooledConnectionLifetime` memaksa rotasi socket connection secara berkala untuk me-refresh entri cache DNS.

#### Solusi Bagian C (Skenario Kasus Produksi)
11. **Solusi Skenario 1:**
    * Ambil identitas context parent sebelum memanggil library: `ActivityContext parentContext = Activity.Current?.Context ?? default;`
    * Saat event pihak ketiga selesai dan masuk kembali ke kode internal, bangun child activity dengan eksplisit parent link:
      ```csharp
      using var activity = TelemetryConstants.ActivitySource.StartActivity(
          "ThirdPartyCallbackHandler", 
          ActivityKind.Consumer, 
          parentContext);
      ```
    * Tautkan context menggunakan `ActivityLink` jika tracing melewati sistem message broker decoupling.
12. **Solusi Skenario 2:**
    * Tambahkan **Adaptive Concurrency Limiter** / **Rate Limiter** di depan panggilan database.
    * Konfigurasikan **Circuit Breaker** dengan **Decorrelated Jitter Exponential Backoff**:
      ```csharp
      builder.AddCircuitBreaker(new() {
          SamplingDuration = TimeSpan.FromSeconds(30),
          FailureRatio = 0.5,
          BreakDuration = TimeSpan.FromSeconds(15)
      });
      builder.AddRetry(new() {
          BackoffType = DelayBackoffType.Exponential,
          UseJitter = true, // KRUSIAL: Memecah gelombang request terdistribusi
          Delay = TimeSpan.FromMilliseconds(500)
      });
      ```
13. **Solusi Skenario 3:**
    * Objek string atau `byte[]` konvensional di C# dikelola oleh GC di managed memory heap. Saat objek keluar dari scope, GC tidak langsung menimpa memori byte tersebut sampai fase compaction/sweeping berikutnya (yang bisa memakan waktu berjam-jam).
    * **Perbaikan:** Gunakan alokasi unmanaged/stack via `Span<byte>` atau pin pointer memory menggunakan `Fixed`, kemudian eksekusi pembersihan mutlak di blok `finally`:
      ```csharp
      Span<byte> secretKey = stackalloc byte[32];
      try {
          // Operasi dekripsi...
      } finally {
          CryptographicOperations.ZeroMemory(secretKey);
      }
      ```

---

## 16. Summary

Modul ini telah mengupas tuntas arsitektur ketahanan, keterlihatan, dan keamanan tingkat tinggi pada platform .NET 8/9:
1. **Resilience Engine:** Migrasi ke **Polly v8** menghadirkan kapabilitas *zero-allocation pipelines* dengan strategi canggih seperti *Hedging* dan *Circuit Breaking* yang siap menangani beban masif tanpa mengorbankan memori heap CLR.
2. **Observability Native:** Penggunaan langsung `System.Diagnostics.ActivitySource` dan `System.Diagnostics.Metrics.Meter` menyingkirkan ketergantungan pada SDK pihak ketiga di jalur kode inti, mengalirkan konteks korelasi W3C secara transparan dan berkinerja tinggi.
3. **Enterprise Zero-Trust Security:** Kombinasi *Envelope Encryption*, enkripsi terotentikasi (*Authenticated Encryption with Associated Data* - AEAD via `AesGcm`), manipulasi berbasis memori aman (`Span<T>`), serta sanitasi deterministik via `CryptographicOperations.ZeroMemory` memberikan perlindungan mutlak bagi data sensitif terhadap ancaman analisis memori forensik modern.