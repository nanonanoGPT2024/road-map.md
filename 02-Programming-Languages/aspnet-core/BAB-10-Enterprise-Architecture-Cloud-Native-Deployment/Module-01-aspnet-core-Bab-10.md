# Bab 10 Module 01: Enterprise Architecture & Cloud-Native Deployment

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Backend Engineering & Cloud Architecture
*   **Kategori:** 02-Programming-Languages
*   **Teknologi Utama:** ASP.NET Core 8.0 / .NET 8 LTS, Docker, Kubernetes, OpenTelemetry
*   **Tingkat Kesulitan:** Advanced / Enterprise Grade
*   **Prasyarat:** Pemahaman mendalam tentang C# modern, Dependency Injection, RESTful API, Entity Framework Core, asinkronitas (`async`/`await`), dan konsep dasar orkestrasi kontainer.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1.  **Mendesain dan Mengimplementasikan Arsitektur Modular Monolith/Clean Architecture** pada ASP.NET Core yang mematuhi prinsip *Separation of Concerns*, DDD (*Domain-Driven Design*), dan *Hexagonal/Ports and Adapters*.
2.  **Membangun Kontainer Docker Cloud-Native Berkinerja Tinggi** menggunakan *multi-stage builds*, gambar *chiseled* Ubuntu atau Alpine non-root, dengan ukuran artefak minimal dan *surface attack* seminim mungkin.
3.  **Mengonfigurasi Lifecycle Management & Resiliensi Kubernetes** dengan probe terperinci (*Liveness*, *Readiness*, *Startup*), *graceful shutdown* berbasis `IHostApplicationLifetime`, serta penanganan sinyal `SIGTERM`.
4.  **Mengintegrasikan Observabilitas Terstandarisasi OpenTelemetry (OTel)** yang mencakup metrik, *distributed tracing*, dan *structured logging* ke platform kolektor enterprise.
5.  **Menerapkan Strategi Konfigurasi & Secret Management Enterprise** yang aman secara *runtime* tanpa mengekspos kredensial ke repositori kode sumber atau artefak kontainer.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa perangkat lunak enterprise, transisi dari aplikasi monolitik tradisional ke sistem *cloud-native* menuntut pergeseran paradigma dari model komputasi *pets* (server unik yang dipelihara manual) ke model *cattle* (instans kontainer efemeral yang dapat dimatikan dan digantikan kapan saja).

```
[ Traditional Monolith / Pet ]             [ Cloud-Native / Cattle ]
+----------------------------+             +---------+ +---------+ +---------+
| Long-running OS/VM         |             | Pod #1  | | Pod #2  | | Pod #3  |
| State stored on disk       |    VS       | (Stateless, Disposable, Ephemeral)|
| Hardcoded IP & Secrets     |             +---------+ +---------+ +---------+
| Manual Recovery            |                   ^          ^          ^
+----------------------------+                   | Orchestrator (K8s)  |
```

Prinsip dasar yang harus diinternalisasi:
*   **Stateless by Design:** Instans ASP.NET Core tidak boleh menyimpan *in-memory session state* yang bergantung pada siklus hidup mesin. Semua status persisten dieksternalisasi ke basis data terdistribusi atau *cache* (misal: Redis).
*   **Fast Startup, Graceful Termination:** Aplikasi harus siap menerima lalu lintas sesegera mungkin (*fast startup*) dan wajib membersihkan koneksi, menghabiskan *in-flight requests*, serta merilis *lock* saat menerima instruksi terminasi (*graceful shutdown*).
*   **Config & Secrets Externalization:** Mengikuti pedoman *The Twelve-Factor App*, artefak biner bersifat identik di seluruh *environment* (Dev, Staging, Prod); hanya konfigurasi dan secrets yang disuntikkan secara dinamis melalui *environment variables* atau *volume mounts*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur *high-level* penerapan ASP.NET Core dalam ekosistem Kubernetes enterprise yang terintegrasi dengan *Ingress Controller*, Service Mesh, Secrets Provider, dan Distributed Telemetry:

```
                              [ Public Traffic ]
                                      |
                                      v
                         +--------------------------+
                         |  K8s Ingress Controller  |
                         |   (e.g., NGINX / Envoy)  |
                         +--------------------------+
                                      |
                 +--------------------+--------------------+
                 | Mutual TLS (mTLS) via Service Mesh      |
                 v                                         v
   +---------------------------+             +---------------------------+
   |  ASP.NET Core Pod - A     |             |  ASP.NET Core Pod - B     |
   | +-----------------------+ |             | +-----------------------+ |
   | | Kestrel Web Server    | |             | | Kestrel Web Server    | |
   | +-----------------------+ |             | +-----------------------+ |
   | | Clean Architecture    | |             | | Clean Architecture    | |
   | | Core / Infra / API    | |             | | Core / Infra / API    | |
   | +-----------------------+ |             | +-----------------------+ |
   | | Health Check Pipeline | |             | | Health Check Pipeline | |
   | | (/healthz, /ready)    | |             | | (/healthz, /ready)    | |
   | +-----------------------+ |             | +-----------------------+ |
   |             |             |             |             |             |
   +-------------|-------------+             +-------------|-------------+
                 |                                         |
         +-------+-------+                         +-------+-------+
         | Metrics/Trace |                         | Metrics/Trace |
         v               v                         v               v
   +---------------------------+             +---------------------------+
   | OpenTelemetry Collector   | <-----------+ External Secret Provider  |
   | (Jaeger / Prometheus)     |             | (Azure KV / HashiCorp)    |
   +---------------------------+             +---------------------------+
```

### Diagram Siklus Hidup Terminasi Pod (Graceful Shutdown)

```
Kube-Scheduler / API Server           Kubelet               ASP.NET Core (Kestrel)
           |                             |                            |
           |--- Pod marked Terminating ->|                            |
           |    (Removed from Endpoints) |                            |
           |                             |--- SIGTERM --------------->|
           |                             |                            |-- Cancel CancellationTokenSource
           |                             |                            |-- Reject new TCP connections
           |                             |                            |-- Complete in-flight HTTP requests
           |                             |<-- Process Exits (Clean)---|
           |<-- Pod Removed -------------|
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Kestrel Web Server & K8s Connection Draining
Kestrel diatur untuk mendengarkan port non-root (secara *default* port 8080 pada .NET 8). Ketika Kubernetes mengirimkan sinyal `SIGTERM`, Kestrel secara otomatis memasuki tahap *draining*:
*   Port HTTP berhenti menerima koneksi baru (`SYN` ditolak).
*   Koneksi *keep-alive* yang menganggur (*idle*) langsung ditutup dengan *header* `Connection: close`.
*   Permintaan yang sedang berjalan (*in-flight requests*) diberikan jendela toleransi waktu yang diatur oleh `HostOptions.ShutdownTimeout`.

### 2. .NET Generic Host Architecture (`IHost`)
ASP.NET Core berjalan di atas `IHost`, yang mengoordinasikan *hosted services* (`IHostedService` / `BackgroundService`). 
*   Saat inisialisasi: Semua method `IHostedService.StartAsync` dieksekusi secara berurutan atau paralel sesuai konfigurasi `HostOptions.ServicesStartConcurrently`.
*   Saat terminasi: `IHostApplicationLifetime.ApplicationStopping` dipicu terlebih dahulu, diikuti dengan pemanggilan `IHostedService.StopAsync` dengan urutan terbalik (*reverse dependency order*).

### 3. Native AOT vs JIT di Kontainer
Pada .NET 8, kompilasi *Ahead-Of-Time* (Native AOT) menghasilkan biner mesin mandiri (*standalone machine code*), memangkas JIT compiler dan *strip metadata*. Dampaknya terhadap arsitektur:
*   *Cold start latency* berkurang drastis (orde milidetik), sangat krusial untuk mekanisme *auto-scaling* (HPA) di Kubernetes.
*   Konsumsi memori dasar (*working set*) turun hingga 50-70%.
*   Refleksi dinamis dibatasi; arsitektur harus mengadopsi C# Source Generators untuk serializer JSON dan *dependency injection*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Clean Architecture dalam Sistem Enterprise
Untuk mencegah *tight coupling* antara logika bisnis dengan *framework* pihak ketiga, Clean Architecture membagi sistem menjadi lapisan-lapisan konsentris:

1.  **Domain Layer:** Berisi entitas inti, *value objects*, *aggregates*, *domain events*, dan *domain exceptions*. Bebas dari dependensi eksternal (bahkan tidak mereferensikan EF Core).
2.  **Application Layer:** Mengorkestrasikan alur bisnis melalui use cases (umumnya menggunakan pola CQRS via MediatR atau handler murni). Mendefinisikan antarmuka abstraksi (*ports*) untuk infrastruktur.
3.  **Infrastructure Layer:** Mengimplementasikan antarmuka (*adapters*) seperti akses basis data (EF Core DbContext), integrasi message broker (RabbitMQ/Kafka), atau *external client*.
4.  **Presentation/Web Layer:** Menangani transportasi data HTTP, serialisasi/deserialisasi, middleware pipeline, dan autentikasi/otorisasi.

### The 12-Factor App Mapping ke Ekosistem .NET 8

| Faktor | Prinsip | Realisasi ASP.NET Core Enterprise |
| :--- | :--- | :--- |
| **I. Codebase** | Satu repositori yang dilacak | Monorepo atau Single Git Repo per Microservice. |
| **II. Dependencies** | Deklarasi dependensi eksplisit | NuGet via `.csproj` dan `Directory.Packages.props`. |
| **III. Config** | Simpan konfigurasi di environment | `Microsoft.Extensions.Configuration` membaca dari Environment Variables & Secret Stores. |
| **IV. Backing Services** | Perlakukan sumber daya sebagai *attached resources* | Abstraksi via Connection Strings yang diinjeksi secara dinamis. |
| **IX. Disposability** | Memaksimalkan ketahanan melalui fast startup & graceful shutdown | `HostOptions.ShutdownTimeout`, handling `SIGTERM`, dan Native AOT / ReadyToRun. |
| **XI. Logs** | Perlakukan log sebagai event streams | `Console.JsonConsoleLoggerProvider` mengirim *structured JSON* langsung ke `stdout`. |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah struktur dasar implementasi *health check* enterprise yang memisahkan *Liveness* (kondisi internal aplikasi hidup) dan *Readiness* (kemampuan aplikasi melayani dependensi eksternal).

### 1. Konfigurasi Probes pada Program.cs

```csharp
// File: Program.cs
using HealthChecks.UI.Client;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.Extensions.Diagnostics.HealthChecks;

var builder = WebApplication.CreateBuilder(args);

// Konfigurasi Kestrel Graceful Shutdown
builder.Services.Configure<HostOptions>(options =>
{
    options.ShutdownTimeout = TimeSpan.FromSeconds(30);
});

// Registrasi Health Checks
builder.Services.AddHealthChecks()
    // Liveness: Mengecek status internal process
    .AddCheck("self", () => HealthCheckResult.Healthy(), tags: new[] { "live" })
    // Readiness: Mengecek koneksi basis data
    .AddNpgSql(
        connectionString: builder.Configuration.GetConnectionString("DefaultConnection") 
            ?? throw new InvalidOperationException("Connection string is missing"),
        name: "postgres_db",
        failureStatus: HealthStatus.Unhealthy,
        tags: new[] { "ready" });

var app = builder.Build();

// Endpoint Liveness: Dipanggil Kubelet untuk menentukan apakah kontainer harus direstart
app.MapHealthChecks("/healthz/liveness", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("live"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
});

// Endpoint Readiness: Dipanggil Kubelet untuk mengizinkan Pod menerima trafik
app.MapHealthChecks("/healthz/readiness", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
});

app.Run();
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut bedah teknis baris krusial dari kode di Seksi 07:

1.  `options.ShutdownTimeout = TimeSpan.FromSeconds(30);`
    *   **Mekanisme:** Mengubah batas waktu *default* .NET (5 detik) menjadi 30 detik. K8s secara *default* memiliki `terminationGracePeriodSeconds: 30`. Memberi cukup waktu bagi koneksi database, *long-running tasks*, dan HTTP *in-flight requests* untuk selesai sebelum kernel membunuh proses (`SIGKILL`).
2.  `.AddCheck("self", () => HealthCheckResult.Healthy(), tags: new[] { "live" })`
    *   **Mekanisme:** Mengecek apakah siklus eksekusi internal runtime .NET masih merespons. Jika thread pool mengalami *deadlock* total, pemeriksaan ini akan *timeout*, menyebabkan K8s merestart pod.
    *   **Penting:** JANGAN mengecek dependensi eksternal (seperti DB) pada tag "live". Jika DB *down*, semua pod akan restart bersamaan (*cascading failure*).
3.  `.AddNpgSql(..., tags: new[] { "ready" })`
    *   **Mekanisme:** Menguji pembukaan koneksi TCP dan eksekusi kueri sederhana ke PostgreSQL (`SELECT 1`). Jika koneksi gagal, Pod ditandai `Unready`, sehingga Service Kubernetes mencabut Pod tersebut dari *traffic balancing*, tanpa membunuh proses aplikasinya.
4.  `Predicate = check => check.Tags.Contains("ready")`
    *   **Mekanisme:** Melakukan *filtering* selektif agar hanya health check dengan tag yang relevan yang dijalankan pada endpoint tertentu. Ini memisahkan lalu lintas operasional infra K8s dari beban kerja normal.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Insiden "502 Bad Gateway" Saat Zero-Downtime Rolling Update

**Latar Belakang:**  
Sebuah platform *fintech core-banking* yang melayani 15.000 Request Per Second (RPS) menggunakan ASP.NET Core di Kubernetes. Setiap kali *deployment* versi baru dilakukan melalui pipeline CI/CD, pengguna mengalami gelombang galat `HTTP 502 Bad Gateway` selama sekitar 5-10 detik.

**Analisis Akar Masalah (Root Cause Analysis):**
1.  **Race Condition Lifecycle:** Saat pod lama menerima `SIGTERM`, Kestrel segera menghentikan listener HTTP. Namun, pembaruan rute pada *Kube-Proxy* dan *Ingress Controller* membutuhkan latensi propagasi jaringan (sekitar 1-3 detik) untuk menghapus IP Pod dari daftar *endpoints*.
2.  **Dropped Requests:** Ingress tetap mengirim lalu lintas HTTP ke Pod lama yang sudah menutup port Kestrel-nya, menyebabkan koneksi TCP ditolak (*connection reset*).
3.  **Tidak Ada PreStop Delay:** Kontainer tidak menunda eksekusi terminasi internalnya untuk menunggu propagasi *iptables/IPVS* selesai di level kluster.

**Solusi Arsitektural Enterprise:**
1.  Menyuntikkan hook `preStop` pada manifest pod Kubernetes (`sleep 5`) untuk membiarkan *endpoints propagation* selesai sebelum `SIGTERM` dikirim ke runtime ASP.NET Core.
2.  Mengaktifkan `IHostApplicationLifetime` graceful handling untuk menyelesaikan transaksi keuangan yang sedang diproses.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi menyeluruh aplikasi berarsitektur Clean Architecture yang dilengkapi *enterprise-grade containerization*, *graceful shutdown*, dan konfigurasi Kubernetes.

### 1. Multi-Stage Dockerfile (Distroless / Non-Root)

```dockerfile
# BUILD STAGE
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
WORKDIR /source

# Mengoptimalkan caching layer: salin hanya file proyek terlebih dahulu
COPY Directory.Packages.props ./
COPY src/EnterpriseApp.Core/*.csproj ./src/EnterpriseApp.Core/
COPY src/EnterpriseApp.Infrastructure/*.csproj ./src/EnterpriseApp.Infrastructure/
COPY src/EnterpriseApp.Api/*.csproj ./src/EnterpriseApp.Api/

RUN dotnet restore src/EnterpriseApp.Api/EnterpriseApp.Api.csproj --runtime linux-musl-x64

# Salin seluruh kode sumber dan lakukan kompilasi rilis
COPY src/ ./src/
WORKDIR /source/src/EnterpriseApp.Api
RUN dotnet publish -c Release -o /app/publish \
    --no-restore \
    --runtime linux-musl-x64 \
    --self-contained false \
    /p:UseAppHost=false

# RUNTIME STAGE (Chiseled / Alpine Non-Root)
FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime
WORKDIR /app

# Menjalankan kontainer sebagai akun non-root demi alasan keamanan
# Port non-privileged default .NET 8 adalah 8080
ENV ASPNETCORE_HTTP_PORTS=8080 \
    DOTNET_EnableDiagnostics=0 \
    ASPNETCORE_ENVIRONMENT=Production

# User ID 'app' (1654) sudah terkonfigurasi di base image .NET 8 Alpine
USER $APP_UID

COPY --from=build --chown=$APP_UID:$APP_UID /app/publish .

EXPOSE 8080

ENTRYPOINT ["dotnet", "EnterpriseApp.Api.dll"]
```

### 2. Implementasi Graceful Worker & Lifecycle Notification

```csharp
// File: src/EnterpriseApp.Infrastructure/BackgroundServices/PaymentQueueConsumer.cs
namespace EnterpriseApp.Infrastructure.BackgroundServices;

using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

public sealed class PaymentQueueConsumer : BackgroundService
{
    private readonly ILogger<PaymentQueueConsumer> _logger;
    private readonly IHostApplicationLifetime _lifetime;

    public PaymentQueueConsumer(
        ILogger<PaymentQueueConsumer> logger,
        IHostApplicationLifetime lifetime)
    {
        _logger = logger;
        _lifetime = lifetime;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _lifetime.ApplicationStopping.Register(() =>
        {
            _logger.LogWarning("SIGTERM terdeteksi. Menghentikan penarikan pesan baru dari Queue...");
        });

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // Mensimulasikan konsumsi antrean transaksi finansial
                await ProcessPaymentQueueAsync(stoppingToken);
                await Task.Delay(1000, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                _logger.LogInformation("Operasi antrean dibatalkan secara aman.");
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Kesalahan tidak terduga dalam antrean pembayaran.");
            }
        }

        _logger.LogInformation("Drain antrean selesai. Worker berhenti total.");
    }

    private async Task ProcessPaymentQueueAsync(CancellationToken cancellationToken)
    {
        // Logika pemrosesan transaksi
        await Task.CompletedTask;
    }
}
```

### 3. Kubernetes Deployment Spec (Enterprise Manifest)

```yaml
# File: k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: enterprise-api-deployment
  labels:
    app.kubernetes.io/name: enterprise-api
    app.kubernetes.io/part-of: core-banking
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app: enterprise-api
  template:
    metadata:
      labels:
        app: enterprise-api
    spec:
      terminationGracePeriodSeconds: 60
      securityContext:
        runAsNonRoot: true
        runAsUser: 1654
        fsGroup: 1654
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: enterprise-api
        image: cr.internal.net/banking/enterprise-api:1.0.4
        imagePullPolicy: IfNotPresent
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        ports:
        - containerPort: 8080
          name: http-web
        env:
        - name: ConnectionStrings__DefaultConnection
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: connection-string
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 5"]
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "1000m"
            memory: "512Mi"
        startupProbe:
          httpGet:
            path: /healthz/liveness
            port: 8080
          failureThreshold: 30
          periodSeconds: 2
        livenessProbe:
          httpGet:
            path: /healthz/liveness
            port: 8080
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /healthz/readiness
            port: 8080
          periodSeconds: 5
          timeoutSeconds: 2
          failureThreshold: 2
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Arsitektur: Monolitik Modular vs Microservices Murni

```
[ Monolitik Modular ]                  [ Microservices Murni ]
+----------------------------+         +--------+   +--------+   +--------+
| App Boundary               |         | Svc A  |   | Svc B  |   | Svc C  |
| [Order] [Payment] [Notif]  |         +--------+   +--------+   +--------+
| In-Memory Method Calls     |              |            |            |
| Single Shared/Schema DB    |              +---> Network (gRPC/HTTP) +
+----------------------------+                    Distributed Database
```

| Dimensi | Modular Monolith (ASP.NET Core) | Microservices Murni |
| :--- | :--- | :--- |
| **Kompleksitas Jaringan** | Sangat Rendah (In-process memory invocation) | Sangat Tinggi (Service discovery, mTLS, circuit breaker) |
| **Latensi Komunikasi** | Nanodetik | Milidetik (Network serialization overhead) |
| **Konsistensi Data** | ACID transactions langsung via single UnitOfWork | BASE (Eventual Consistency via Sagas / Outbox Pattern) |
| **Batas Deployment** | Seluruh modul rilis bersamaan | Independen per service |
| **Overhead Operasional** | Minimal (Single pipeline, single K8s Pod spec) | Ekstrem (Perlu platform team, Service Mesh, Tracing masif) |
| **Rekomendasi Konteks** | Sistem fase awal hingga menengah-tinggi | Organisasi skala enterprise dengan puluhan squad otonom |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Pitfall Thread Starvation pada Health Check:**
    *   *Kondisi:* Health check endpoint memanggil *sync-over-async* code (misal: `dbTask.Result` atau `.Wait()`).
    *   *Dampak:* Saat trafik tinggi, thread pool habis (*starvation*). Endpoint `/healthz` gagal merespons dalam waktu `timeoutSeconds: 2`. Kubernetes menganggap pod mati dan membunuhnya, memperparah beban pada pod yang tersisa (*cascading collapse*).
    *   *Mitigasi:* Selalu gunakan API asinkron non-blocking (`await connection.OpenAsync(cancellationToken)`).

2.  **Edge Case: Pod Terjebak di `Terminating` State:**
    *   *Kondisi:* Metode `IHostedService.StopAsync` menunggu thread sinkronisasi latar belakang yang tidak pernah menerima cancellation token, melebihi batas `terminationGracePeriodSeconds`.
    *   *Dampak:* Kubernetes mengirim sinyal `SIGKILL` paksa. Data dalam buffer terpotong, file transaksi rusak.
    *   *Mitigasi:* Hormati selalu `CancellationToken` yang dilewatkan ke method `StopAsync`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Mistake 1: Menjalankan Kontainer sebagai `root`
*   *Deskripsi:* Membiarkan Dockerfile tanpa deklarasi instruksi `USER`, yang defaultnya mengeksekusi proses sebagai ID `0` (root).
*   *Bahaya:* Penyerang yang mengeksploitasi celah Remote Code Execution (RCE) dapat mengakses *underlying host kernel*.
*   *Solusi:* Gunakan *directive* `USER $APP_UID` di .NET 8, yang mengikat proses ke akun non-root berhak akses terbatas.

### Mistake 2: Memeriksa Dependensi Eksternal pada Liveness Probe
*   *Deskripsi:* Mendaftarkan pemeriksaan PostgreSQL ke endpoint `/healthz/liveness`.
*   *Bahaya:* Saat server PostgreSQL mengalami gangguan jaringan sementara selama 10 detik, probe liveness pada seluruh 50 pod gagal. Kubernetes membunuh seluruh 50 pod secara bersamaan, memperparah kondisi pemulihan.
*   *Solusi:* Liveness hanya memeriksa proses internal aplikasi. Dependensi eksternal secara eksklusif diperiksa di Readiness probe.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Strict Boundary Contexts:** Hindari dependensi sirkular antar-modul Clean Architecture. Gunakan arsitektur *Ports and Adapters*:
    *   `Domain` tidak memiliki dependensi proyek lain.
    *   `Application` hanya mereferensikan `Domain`.
    *   `Infrastructure` mereferensikan `Application`.
    *   `Api` mereferensikan `Infrastructure` dan `Application`.
2.  **Centralized Package Management (CPM):** Gunakan file `Directory.Packages.props` di root repositori untuk memastikan seluruh modul menggunakan versi NuGet SDK yang identik secara seragam.
3.  **Read-Only Root Filesystem:** Konfigurasikan `readOnlyRootFilesystem: true` di SecurityContext Kubernetes. Jika kontainer membutuhkan penulisan temporary file, pasang volume sementara berbasis `emptyDir` memori pada `/tmp`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Pemanfaatan Memory Limits & GC Tuning
Di lingkungan kontainer, .NET Garbage Collector (GC) secara otomatis mendeteksi batas memori kontainer (*cgroup limits*). Namun, konfigurasi manual disarankan untuk kestabilan beban kerja enterprise:

```xml
<!-- Tambahkan pada EnterpriseApp.Api.csproj -->
<PropertyGroup>
  <!-- Mengaktifkan Server GC untuk throughput tinggi multicore -->
  <ServerGarbageCollection>true</ServerGarbageCollection>
  <!-- Menghindari GC mengambil alih 100% memori kontainer sebelum alokasi dibersihkan -->
  <GCHeapHardLimitPercent>75</GCHeapHardLimitPercent>
</PropertyGroup>
```

### Response Compression & Minimal Allocations
*   Gunakan `System.Text.Json` Source Generators untuk menghindari alokasi memori yang disebabkan oleh *runtime reflection*.
*   Manfaatkan `ReadOnlyMemory<byte>` atau `ArrayPool<byte>.Shared` saat membaca *payload streaming* berskala besar pada lapisan infrastruktur API.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Drop Linux Capabilities:** Hapus seluruh kapabilitas Linux default kontainer di Kubernetes dengan deklarasi `capabilities: drop: ["ALL"]`. ASP.NET Core tidak memerlukan kapabilitas jaringan tingkat rendah (*raw sockets* atau *chown*).
2.  **External Secrets Management:** Hindari menyimpan credentials dalam format teks biasa di `appsettings.json`. Gunakan *Kubernetes External Secrets Operator* (ESO) untuk menyinkronkan rahasia dari HashiCorp Vault atau AWS Secrets Manager langsung ke Kubernetes Secret, yang kemudian diinjeksi via environment variable.

```csharp
// Mengabaikan pemuatan konfigurasi berbahaya jika berjalan di produksi
builder.Configuration.AddEnvironmentVariables(prefix: "BANKING_");
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Implementasi terpadu OpenTelemetry untuk tracing, metrics, dan structured logging menuju OTel Collector.

```csharp
// Program.cs
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var resourceBuilder = ResourceBuilder.CreateDefault()
    .AddService(serviceName: "EnterpriseCoreApi", serviceVersion: "1.0.0");

builder.Services.AddOpenTelemetry()
    .WithTracing(tracerProviderBuilder =>
    {
        tracerProviderBuilder
            .SetResourceBuilder(resourceBuilder)
            .AddAspNetCoreInstrumentation(opts =>
            {
                opts.RecordException = true;
            })
            .AddHttpClientInstrumentation()
            .AddEntityFrameworkCoreInstrumentation()
            .AddOtlpExporter(opt =>
            {
                opt.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://otel-collector:4317");
            });
    })
    .WithMetrics(meterProviderBuilder =>
    {
        meterProviderBuilder
            .SetResourceBuilder(resourceBuilder)
            .AddAspNetCoreInstrumentation()
            .AddRuntimeInstrumentation()
            .AddProcessInstrumentation()
            .AddOtlpExporter(opt =>
            {
                opt.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://otel-collector:4317");
            });
    });

// Mengonfigurasi Serilog/Console JSON Logger untuk logging terstruktur
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole(options =>
{
    options.IncludeScopes = true;
    options.TimestampFormat = "yyyy-MM-ddTHH:mm:ssZ ";
});
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Dockerfile:** Multi-stage -> Alpine/Chiseled -> Non-Root UID 1654 -> Port 8080.
*   **Startup Probe:** Menahan evaluasi Liveness/Readiness saat inisialisasi lambat (`failureThreshold * periodSeconds`).
*   **Liveness Probe:** Cek *hanya* kondisi internal (`/healthz/liveness`). Gagal = Pod Di-RESTART.
*   **Readiness Probe:** Cek *ketersediaan* dependensi eksternal DB/Cache (`/healthz/readiness`). Gagal = Pod DITARIK dari Service Traffic.
*   **Shutdown Hook:** Selalu sertakan `preStop: exec: sleep 5` pada Pod spec untuk mencegah error 502/Kestrel Race Conditions.
*   **Termination Budget:** Atur `HostOptions.ShutdownTimeout` selaras dengan `terminationGracePeriodSeconds` di Kubernetes.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1.  **Mengapa port HTTP default untuk kontainer ASP.NET Core pada image .NET 8 diubah dari port 80 menjadi 8080?**
    *   *Jawaban:* Port di bawah 1024 memerlukan hak akses administratif (*root/privileged*). Dengan menggunakan port 8080, kontainer dapat langsung dijalankan dengan prinsip *least privilege* menggunakan akun non-root (`app`, UID 1654) demi postur keamanan yang lebih kokoh.
2.  **Apa perbedaan mendasar antara tag `live` dan `ready` dalam implementasi Health Checks di ASP.NET Core?**
    *   *Jawaban:* Tag `live` digunakan untuk liveness probe yang memverifikasi apakah proses runtime web server masih beroperasi. Tag `ready` digunakan untuk memverifikasi apakah aplikasi siap menerima traffic, termasuk ketersediaan database, cache, dan dependensi krusial lainnya.
3.  **Apakah diperbolehkan meletakkan dependensi Entity Framework Core di dalam Domain Layer pada Clean Architecture? Jelaskan alasannya.**
    *   *Jawaban:* Tidak diperbolehkan. Domain Layer harus murni (*Pure Domain*) dan agnostik terhadap teknologi framework, persistence, atau database library tertentu agar domain logic dapat diuji dan dipelihara secara terisolasi.
4.  **Apa peran instruksi `COPY --from=build` pada multi-stage Dockerfile?**
    *   *Jawaban:* Instruksi tersebut menyalin hanya artefak biner hasil kompilasi akhir dari build environment sementara ke runtime image yang ramping, membuang seluruh .NET SDK, source code, dan build caches dari image final.
5.  **Bagaimana format standar output log aplikasi agar mudah dicerna oleh agregator log Kubernetes seperti FluentBit, Promtail, atau Vector?**
    *   *Jawaban:* Format terstruktur (Structured Logging) berbasis single-line JSON yang dialirkan langsung ke terminal standar (`stdout` / `stderr`).

### Soal Tingkat Lanjut (Intermediate)
6.  **Mengapa race condition 502 Bad Gateway dapat terjadi selama proses rolling update Kubernetes jika Pod tidak memiliki lifecycle hook `preStop`?**
    *   *Jawaban:* Karena ada latensi propagasi penghapusan IP Pod dari kube-proxy dan ingress endpoints di kluster. Jika Kestrel langsung merespons `SIGTERM` dengan menutup listener socket saat Ingress Controller masih memiliki rute IP Pod tersebut, trafik baru akan tetap diteruskan ke Pod dan koneksi TCP ditolak.
7.  **Apa fungsi dari `IHostApplicationLifetime.ApplicationStopping` dibandingkan dengan mengimplementasikan method `Dispose` pada singleton services?**
    *   *Jawaban:* `ApplicationStopping` dipicu segera saat sinyal pemadaman diterima sebelum server berhenti menerima request baru, memungkinkan service latar belakang membatalkan consumer queue dan menyelesaikan transaksi *in-flight* secara tertib sebelum dependensi utama seperti DbContext dan HTTP server mulai didisposisi.
8.  **Mengapa penggunaan pattern "Sync-over-Async" (seperti memanggil `.Result` atau `.Wait()`) pada implementasi custom `IHealthCheck` sangat berbahaya di lingkungan produksi?**
    *   *Jawaban:* Hal itu berpotensi mengunci *thread* pada .NET ThreadPool (*thread starvation*). Jika thread pool kehabisan thread untuk menangani health check, probe Kubernetes akan *timed out*, memicu terminasi pod secara keliru di tengah-tengah beban kerja yang tinggi.
9.  **Dalam kondisi apa Server Garbage Collection (`ServerGC`) lebih disukai daripada Workstation Garbage Collection (`WorkstationGC`) dalam kontainer Kubernetes?**
    *   *Jawaban:* `ServerGC` lebih disukai untuk aplikasi web dengan throughput tinggi yang memiliki alokasi multi-core CPU (>= 2 vCPU), karena setiap core memiliki heap GC dan thread sendiri, meminimalkan thread contention selama pengumpulan sampah memori.
10. **Bagaimana mitigasi keamanan untuk mencegah kebocoran informasi sensitif jika image kontainer ASP.NET Core berhasil diinspeksi oleh pihak luar?**
    *   *Jawaban:* Menggunakan base image *Distroless* atau *Chiseled* yang tidak menyertakan shell (`/bin/sh`) atau package manager, tidak membakar secrets ke dalam layer image via build args/env, serta mengenkripsi data transit dan memanfaatkan external dynamic secret injection pada saat runtime.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Instruksi Praktikum
Rancang dan bangun sebuah microservice ASP.NET Core 8 *Production-Ready* dengan nama **"Enterprise Vault Service"** yang memenuhi spesifikasi enterprise berikut:

1.  **Struktur Proyek:**
    *   Bagi solusi ke dalam 4 layer: `EnterpriseVault.Domain`, `EnterpriseVault.Application`, `EnterpriseVault.Infrastructure`, dan `EnterpriseVault.Api`.
2.  **Kontainerisasi:**
    *   Buat `Dockerfile` multi-stage berbasis `mcr.microsoft.com/dotnet/aspnet:8.0-alpine`.
    *   Jalankan kontainer menggunakan UID non-root bawaan .NET 8.
    *   Ukuran image akhir tidak boleh melebihi **120 MB**.
3.  **Ketahanan & Graceful Shutdown:**
    *   Implementasikan `BackgroundService` yang memproses *mock queue* per detik.
    *   Pastikan jika pod dimatikan (`docker stop` dengan timeout 30 detik), worker dapat menyelesaikan transaksi saat itu dan mencatat log konfirmasi terminasi bersih.
4.  **Health Check Endpoint:**
    *   Implementasikan endpoint `/healthz/liveness` (respons JSON status status aplikasi).
    *   Implementasikan endpoint `/healthz/readiness` yang mengecek status kueri dummy database (misal: SQLite / PostgreSQL in-memory) dan mengembalikan 200 OK atau 503 Service Unavailable.
5.  **Kubernetes Manifest:**
    *   Tulis file manifes `k8s-pod.yaml` lengkap dengan `lifecycle.preStop`, konfigurasi `startupProbe`, `livenessProbe`, `readinessProbe`, dan `resources` (requests dan limits memori/CPU).

Uji coba hasil pekerjaan Anda dengan mengeksekusi pengiriman sinyal `SIGTERM` manual via `docker kill --signal=SIGTERM <container_id>` dan periksa log keluaran untuk memastikan tidak ada unhandled exception atau transaksi yang terpotong. Evaluasi keberhasilan deployment Anda menggunakan perintah audit standar Kubernetes.