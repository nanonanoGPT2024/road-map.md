# BAB 02: Quiz, Challenge, & Knowledge Check
**Dependency Injection & Configuration Deep Dive**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Siklus Hidup dan Disposal Tracking**
   Jelaskan secara mendalam perbedaan deterministik antara siklus hidup `Transient`, `Scoped`, dan `Singleton` dalam konteks *Root Container* vs *Scoped Container*. Mengapa dependensi bertipe `Transient` yang mengimplementasikan `IDisposable` atau `IAsyncDisposable` berpotensi menjadi *memory leak* laten jika di-resolve langsung dari root `IServiceProvider`?
   
2. **Triase Options Pattern: `IOptions`, `IOptionsSnapshot`, dan `IOptionsMonitor`**
   Bedah perbedaan fundamental dari ketiga variasi Options Pattern tersebut berdasarkan:
   * Siklus hidup registrasi DI (*Lifetime*).
   * Perilaku komputasi/caching nilai konfigurasi (*Lazy evaluation* vs *Cache-per-request*).
   * Dukungan terhadap *Hot-Reload* (`reloadOnChange: true`).
   * Batasan penggunaan di dalam komponen bertipe *Singleton* (misal: `IHostedService`).

3. **Hierarki Precedence dan Mekanisme Overwriting pada Configuration Engine**
   Pada builder default ASP.NET Core (`WebApplication.CreateBuilder`), jelaskan urutan evaluasi sumber konfigurasi dari prioritas terendah hingga tertinggi. Apa implikasi arsitektural dari urutan ini terhadap konfigurasi yang menggunakan *JSON array indexing* ketika ditimpa oleh *Environment Variables* di lingkungan Linux/Docker?

4. **Patologi Captive Dependency dan Mekanisme Scope Validation**
   Definisikan apa itu *Captive Dependency*. Mengapa konfigurasi `validateScopes: true` dan `validateOnBuild: true` secara default diaktifkan pada *Development Environment* namun dinonaktifkan di *Production*? Apa dampak performa (*trade-off*) dari validasi graf dependensi ini pada fase *startup*?

5. **Resolusi Polimorfik: Keyed Services vs Open Generics vs Factory Delegate**
   Mulai .NET 8, ASP.NET Core memperkenalkan *Keyed Services* secara *native*. Bandingkan pendekatan penyelesaian multi-implementasi dari suatu antarmuka (*interface*) menggunakan:
   * Native Keyed Services (`[FromKeyedServices]`, `AddKeyedScoped`).
   * Factory Delegate (`Func<IServiceProvider, IService>`).
   * Dynamic Resolution via Open Generics (`typeof(IRepository<>)`).
   Jelaskan kapan masing-masing pendekatan wajib dipilih berdasarkan *type safety* dan kemudahan *unit testing*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Dynamic Code Generation pada ServiceProviderEngine**
   ASP.NET Core DI container mengabstraksi eksekusi resolusi melalui beberapa engine, termasuk `DynamicMethod` / `ILEmit` (Compiled Expression Trees) dan fallback ke Reflection (`RuntimeServiceProviderEngine`). Jelaskan bagaimana runtime memutuskan kapan sebuah graf objek di-resolve menggunakan reflection dan kapan di-compile menjadi kode IL dinamis. Apa dampaknya terhadap metrik *warm-up time* pada arsitektur Serverless (misal: AWS Lambda / Azure Functions cold starts)?

2. **Diagnostik GC Pinning dan Root Container Memory Retention**
   Anda menemukan bahwa sebuah aplikasi web mengalami pertumbuhan memori (*Private Bytes*) yang linier meskipun metrik Gen 2 Collection berjalan reguler. Dari dump memori menggunakan `dotnet-dump`, Anda melihat jutaan referensi instans kelas transient `XmlDataSerializer` yang tertahan di memori. Objek tersebut mengimplementasikan `IDisposable`. Jelaskan alur penelusuran (*object root path*) dari instance tersebut kembali ke root container dan tindakan teknis apa yang harus dilakukan untuk memotong rantai referensi GC tersebut.

3. **Konkurensi dan Deadlock pada `IOptionsMonitor<T>` Change Token Trigger**
   `IOptionsMonitor<T>` memanfaatkan `IChangeToken` yang disediakan oleh `ConfigurationProvider` untuk mendeteksi mutasi file di disk via *File System Watcher*. Jelaskan potensi *concurrency issue* atau *race condition* yang terjadi saat file `appsettings.json` sedang ditulis ulang secara bertahap oleh proses deployment otomatis (misal: CI/CD agent) sementara ribuan thread aktif membaca opsi tersebut secara simultan.

4. **Internal Implementation: Custom `ConfigurationSource` dengan Asynchronous Reload**
   Ketika Anda membangun custom `ConfigurationProvider` yang mengambil konfigurasi dari remote database atau distributed key-value store (misal: Consul/etcd), mengapa method `ConfigurationProvider.Load()` didesain bersifat *synchronous*? Bagaimana cara yang benar mengimplementasikan pembaruan data asinkron (*push-based notification*) tanpa memblokir thread ASP.NET Core atau melanggar kontrak `IChangeToken`?

5. **Kloning Context dan Paralelisasi Pemanggilan Scoped Services**
   Secara arsitektur, satu `IServiceScope` hanya boleh diakses oleh satu alur eksekusi sekuensial (bukan *thread-safe*). Jika Anda memiliki sebuah API endpoint yang harus mengeksekusi tiga operasi batch secara paralel menggunakan `Task.WhenAll`, dan masing-masing operasi membutuhkan dependensi Scoped `IUnitOfWork`, bagaimana Anda mendesain mekanisme resolusi dependensi tersebut agar tidak terjadi *cross-thread access violation* pada `DbContext` internal?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Fatal OutOfMemory di Klaster Kubernetes (High-Throughput Ingestion)
* **Konteks:** Sebuah microservice ingest telemetri memproses 15.000 request/detik. Service ini menggunakan `AddSingleton<ITelemetryPipeline, TelemetryPipeline>()`. Di dalam implementasinya, class `TelemetryPipeline` mengeksekusi enkripsi data dengan memanggil `IServiceProvider.GetRequiredService<CryptoCipher>()` secara manual di setiap request. `CryptoCipher` diregistrasikan sebagai `Transient` dan mengimplementasikan `IDisposable` untuk membersihkan buffer `UnmanagedMemoryStream`.
* **Gejala:** Aplikasi stabil selama 20 menit pasca deployment, lalu penggunaan RAM melonjak tajam hingga Node Kubernetes terkena `OOMKilled`. Tidak ada lonjakan traffic yang abnormal.
* **Pertanyaan Diagnostik:**
  1. Identifikasi secara tepat mengapa GC (*Garbage Collector*) gagal merebut kembali memori unmanaged dan managed milik `CryptoCipher`.
  2. Jelaskan struktur referensi internal ASP.NET Core container (`ServiceProviderEngineScope`) yang menyebabkan akumulasi ini terjadi.
  3. Berikan rekomendasi arsitektur perbaikan tanpa mengubah `TelemetryPipeline` menjadi `Scoped` (karena alasan performa pembuatan instance).

### Skenario B: Race Condition dan Context Corruption pada Background Task
* **Konteks:** Sebuah service e-commerce mengimplementasikan `IHostedService` bernama `OrderFulfillmentWorker`. Worker ini berjalan secara periodik menggunakan `PeriodicTimer`. Untuk memproses pesanan, developer meng-inject `OrderDbContext` (Scoped) langsung ke dalam constructor `OrderFulfillmentWorker` (Singleton).
* **Gejala:** Saat dijalankan di lingkungan staging, aplikasi langsung melempar exception:
  `InvalidOperationException: Cannot consume scoped service 'OrderDbContext' from singleton 'OrderFulfillmentWorker'`.
  Developer tersebut "memperbaiki" masalah ini dengan mematikan validasi scope: `builder.Host.UseDefaultServiceProvider(o => o.ValidateScopes = false)`. Di production, setelah memproses beberapa batch transaksi concurrently, aplikasi mengalami data corruption dan throw:
  `InvalidOperationException: A second operation was started on this context instance before a previous operation completed. This is usually caused by different threads concurrently using the same instance of DbContext`.
* **Pertanyaan Diagnostik:**
  1. Mengapa mematikan `ValidateScopes` adalah *antipattern* yang berbahaya, dan apa implikasi logis dari keberadaan `OrderDbContext` di dalam instance Singleton?
  2. Jelaskan bagaimana *race condition* terjadi ketika timer interval memicu eksekusi baru sebelum eksekusi sebelumnya selesai, atau ketika ada async continuation (`await`) yang melanjutkan eksekusi di thread pool yang berbeda.
  3. Rancang pola resolusi `IServiceScopeFactory` yang benar dan *fault-tolerant* untuk worker tersebut.

### Skenario C: Split-Brain State pada Multi-Region Configuration Hot-Reload
* **Konteks:** Arsitektur microservice enterprise memanfaatkan HashiCorp Vault untuk rotasi kredensial database setiap 60 menit. Sistem menggunakan kustom `ConfigurationProvider` yang memicu pembaruan via `IOptionsSnapshot<DatabaseCredentials>`.
* **Gejala:** Saat rotasi token berlangsung, beberapa endpoint payment (yang menggunakan Scoped Services) sukses terhubung menggunakan kredensial baru. Namun, komponen audit logger dan background reconciliation engine (yang diinjeksi via Singleton Services) terus menggunakan kredensial lama hingga terjadi `AuthenticationFailedException` saat token kedaluwarsa.
* **Pertanyaan Diagnostik:**
  1. Mengapa injeksi `IOptionsSnapshot<T>` gagal pada Singleton services, dan apa exception yang dihasilkan runtime ASP.NET Core saat mencoba melakukan injeksi tersebut?
  2. Jika developer mengubah injeksi di Singleton menjadi `IOptions<T>`, mengapa nilai kredensial tidak pernah ter-update meskipun *configuration source* telah memicu reload?
  3. Bagaimana strategi implementasi Options Pattern yang benar menggunakan `IOptionsMonitor<T>` untuk memastikan seluruh komponen aplikasi (baik Scoped maupun Singleton) tetap berada pada konsistensi status (*eventual consistency*) tanpa memicu downtime atau koneksi terputus tiba-tiba?

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance Multi-Tenant Isolated DI Scope & Dynamic Configuration Provider**

### Problem
Dalam platform SaaS B2B, setiap Tenant memiliki konfigurasi database unik (koneksi terisolasi) dan limitasi rate-limiting yang disimpan dalam format JSON terenkripsi di Azure Blob Storage / AWS S3. Sistem monolit terdistribusi saat ini me-reload konfigurasi dengan cara merestart container Kubernetes yang menyebabkan *downtime* dan *connection drops*. Selain itu, developer sebelumnya melakukan *service locator pattern* di controller menggunakan `HttpContext.RequestServices`, memicu hilangnya jejak lifecycle dependensi dan memory leak.

### Requirements
1. **Custom Configuration Source & Provider:**
   * Bangun implementasi `IConfigurationSource` dan `ConfigurationProvider` kustom bernama `RemoteBlobConfigurationProvider`.
   * Provider harus mendukung *asynchronous polling* atau *push notifications* untuk mendeteksi perubahan konfigurasi tanpa restart aplikasi.
   * Implementasikan mekanisme `IChangeToken` untuk memberi sinyal pembaruan data secara thread-safe.
2. **Options Pattern Integration:**
   * Buat class model opsi `TenantSecurityOptions` yang divalidasi saat startup (`ValidateOnStart`) menggunakan *FluentValidation* atau *Data Annotations* (harus memvalidasi: `MaxConcurrentRequests > 0`, `IsolationLevel` tidak boleh null).
3. **Tenant Context & Scope Isolation Middleware:**
   * Buat middleware ASP.NET Core yang mengekstraksi header `X-Tenant-ID`.
   * Menggunakan `IServiceScopeFactory`, ciptakan isolated child scope untuk request tersebut dan daftarkan state kontekstual `ITenantContext` yang dapat diakses oleh dependensi scoped downstream.
4. **Keyed Services Integration (.NET 8+):**
   * Daftarkan implementasi engine rate limiter berbeda berdasarkan status tenant: `TenantTier.Free` menggunakan `InMemoryRateLimiter`, sedangkan `TenantTier.Enterprise` menggunakan `DistributedRedisRateLimiter`. Resolusi harus memanfaatkan native *Keyed Services*.

### Constraints
* **Zero Captive Dependencies:** Aplikasi harus berjalan dengan `ValidateScopes = true` dan `ValidateOnBuild = true` tanpa melempar exception saat inisialisasi host.
* **Zero Leak Tolerance:** Tidak boleh ada objek `IDisposable` yang di-resolve dari Root Container.
* **Performance:** Alokasi memori per request untuk pembuatan child scope tidak boleh me-recompile ekspresi graf dependensi (manfaatkan default container caching engine).

### Expected Output
Sajikan solusi terstruktur dalam bentuk kode C# produksi yang solid, mencakup:
1. Class `RemoteBlobConfigurationProvider` dan method ekstensi `AddRemoteBlobConfiguration`.
2. Model opsi beserta setup validasi `builder.Services.AddOptionsWithValidateOnStart<...>()`.
3. Middleware penanganan isolated scope dan injeksi `ITenantContext`.
4. Setup `Program.cs` yang mendemonstrasikan registrasi Keyed Services dan eksekusi skenario tanpa captive dependency.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Mekanisme alokasi memori dan siklus hidup `Transient`, `Scoped`, dan `Singleton` di dalam root container vs child scope.
- [ ] Aturan tracking dan batasan pelepasan (*disposal*) objek `IDisposable` / `IAsyncDisposable` oleh `ServiceProvider`.
- [ ] Perbedaan internal, konkurensi, dan use-case antara `IOptions<T>`, `IOptionsSnapshot<T>`, dan `IOptionsMonitor<T>`.
- [ ] Hierarki flattening dan precedence konfigurasi (`appsettings.json`, Environment Variables, Command Line, KeyPerFile).
- [ ] Mekanisme deteksi `Captive Dependency` dan alasan kegagalan arsitektural di baliknya.
- [ ] Mekanisme native Keyed Services di .NET 8+ dan cara kerjanya di bawah kap container dependency injection.
- [ ] Peran `IChangeToken` dalam abstraksi *hot-reload* konfigurasi.

### Saya tidak perlu menghafal:
- [ ] Kode *Intermediate Language* (IL) spesifik yang digenerate oleh `DynamicMethodEngine`.
- [ ] Urutan numerik default ordinal dari masing-masing internal provider di dalam array `ConfigurationManager.Sources`.
- [ ] Tanda tangan method internal dari tipe non-publik seperti `RuntimeServiceProviderEngine` atau `CallSiteFactory`.

### Saya harus bisa melakukan:
- [ ] Menemukan dan memperbaiki *Captive Dependency* menggunakan log startup dan stack trace runtime.
- [ ] Menganalisis dump memori aplikasi untuk melacak *memory leak* akibat penumpukan objek transient disposable.
- [ ] Mengimplementasikan *Options Pattern* yang aman untuk hot-reload pada service Singleton maupun Scoped.
- [ ] Mengisolasi eksekusi multi-thread dengan mengalokasikan child `IServiceScope` secara manual menggunakan `IServiceScopeFactory`.
- [ ] Membangun kustom `ConfigurationProvider` yang terintegrasi penuh dengan ekosistem `IConfiguration` dan mekanisme pembaruan berbasis token.
- [ ] Menulis arsitektur registrasi DI yang bersih menggunakan modul ekstensi (`IServiceCollection` extension methods) yang teruji secara unit-test.