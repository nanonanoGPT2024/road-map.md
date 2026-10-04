# SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: PHP-ENG-B10M01
* **Kategori**: 02-Programming-Languages / PHP
* **Tingkat Kemahiran**: Advanced / Enterprise Architect
* **Prasyarat**: 
  * Penguasaan mendalam arsitektur PHP 8.x dan PHP-FPM.
  * Pemahaman protokol FastCGI, HTTP/2, dan HTTP/3.
  * Pengalaman dasar dengan Linux Containerization (Docker/OCI) dan orkestrasi Kubernetes.
  * Pemahaman networking dasar (TCP/IP, DNS resolution, reverse proxy).
* **Alat & Ekosistem Terkait**:
  * PHP 8.3+ CLI & FPM
  * OpenTelemetry (OTel) PHP SDK & `opentelemetry` C-Extension
  * Prometheus, Grafana, Jaeger
  * Kubernetes (v1.28+) & Envoy / Nginx Ingress
  * OTel Collector Contrib

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:
1. **Mengonstruksi Service Level Indicators (SLI)** dan **Service Level Objectives (SLO)** yang terukur berbasis user-journey untuk sistem terdistribusi berbasis PHP.
2. **Mengimplementasikan Tiga Pilar Observabilitas (Metrics, Traces, Logs)** menggunakan standardisasi OpenTelemetry (OTel) dan context propagation W3C Trace Context pada runtime PHP.
3. **Mendesain arsitektur kontainer Cloud-Native** berbasis PHP-FPM dengan integrasi reverse proxy zero-downtime, non-root execution, dan graceful termination.
4. **Mengeliminasi bottleneck I/O telemetry flush** menggunakan teknik out-of-band tracing via `fastcgi_finish_request()` atau asynchronous batch export.
5. **Mengonfigurasi probe siklus hidup Kubernetes (`livenessProbe`, `readinessProbe`, `startupProbe`)** yang akurat untuk menghindari premature routing dan cascading failures.
6. **Mencegah kebocoran data sensitif (PII)** pada trace attributes dan log stream melalui dynamic data masking dan distributed context isolation.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Stateless Scripting vs Enterprise Distributed System
Dalam arsitektur monolitik LAMP tradisional, PHP diperlakukan sebagai skrip *stateless shared-nothing* berdurasi pendek. Kegagalan proses diselesaikan dengan membunuh request dan melepaskan seluruh memori secara otomatis saat eksekusi selesai.

Pada ekosistem Enterprise Cloud-Native, paradigma ini runtuh:
* **PHP bukan entitas mandiri**: PHP adalah simpul (*node*) dalam grafik panggilan terdistribusi (*distributed call graph*). Hilangnya konteks eksekusi pada simpul PHP akan memutus rantai visibilitas sistem secara global.
* **Ephemeral Lifecycle**: Pod Kubernetes bersifat *cattle, not pets*. Aplikasi harus siap dimatikan kapan saja (SIGTERM) tanpa membuang transaksi yang sedang berjalan (*in-flight requests*) dan tanpa memicu *connection reset by peer* (TCP RST) ke upstream ingress.
* **The Telemetry Overhead Paradox**: Menambahkan observabilitas (APM, distributed tracing, high-frequency metrics) ke dalam runtime per-request seperti PHP-FPM dapat menambah latensi 10%–40% jika arsitekturnya salah. SRE PHP modern harus memisahkan *business logic path* dari *telemetry serialization path*.

```
Traditional Mindset:
[Request] ---> [Nginx] ---> [PHP Script] (Echo HTML, exit, die)

Enterprise SRE Mindset:
                Distributed Trace Context Injected (traceparent header)
                                    |
[K8s Ingress] ---> [Sidecar Envoy] ---> [PHP-FPM Worker] ---> [FastCGI Finish Request]
       |                  |                    |                       |
   (Metrics)          (Metrics)       (Span In-Flight)        (Telemetry Flush to OTel)
       |                  |                    |                       |
       +------------------+--------------------+---------------------> [OTel Collector DaemonSet]
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Topology Arsitektur Pod PHP-FPM Cloud-Native

```
+---------------------------------------------------------------------------------------+
| KUBERNETES POD                                                                        |
|                                                                                       |
|  [Incoming HTTP Request]                                                              |
|            |                                                                          |
|            v                                                                          |
|  +--------------------+   Unix Domain Socket (UDS)    +----------------------------+  |
|  | Nginx / Envoy      | ----------------------------> | PHP-FPM Master Process     |  |
|  | (Reverse Proxy     |   fastcgi://run/fpm.sock      | (PID 1 / Process Manager)  |  |
|  | Container)         |                               +----------------------------+  |
|  +--------------------+                                              |                |
|            |                                            fork()       v                |
|            | Status Metrics                           +----------------------------+  |
|            | (Prometheus Format)                      | Worker Pool (PID 2..N)     |  |
|            v                                          | - Business Logic Execution |  |
|   :8080/nginx-metrics                                 | - OTel Tracing Middleware  |  |
|                                                       +----------------------------+  |
|                                                                      |                |
|                                    Trace Spans / Metrics via gRPC    |                |
+----------------------------------------------------------------------|----------------+
                                                                       |
+----------------------------------------------------------------+     |
| K8S NODE (DAEMONSET)                                           |     |
|                                                                v     |
|  +----------------------------------------------------------------+  |
|  | OpenTelemetry Collector Contrib                                |<-+
|  |                                                                |
|  | [Receivers: OTLP/gRPC :4317]                                   |
|  |    |                                                           |
|  | [Processors: Memory Limiter -> Batch -> Resource Detection]   |
|  |    |                                                           |
|  | [Exporters: Prometheus / Jaeger / OTLP HTTP]                   |
|  +----------------------------------------------------------------+
        |                                        |
        v                                        v
+------------------+                    +------------------+
| Prometheus TSDB  |                    | Jaeger / Tempo   |
| (Metric Storage) |                    | (Trace Storage)  |
+------------------+                    +------------------+
```

### 2. Alur Eksekusi Request & Asynchronous Draining Lifecycle

```
Client                  Nginx Proxy              PHP-FPM Worker               OTel Collector
  |                          |                         |                            |
  |--- HTTP GET /checkout -->|                         |                            |
  |    (w/ traceparent)      |--- FastCGI (Pass Env) ->|                            |
  |                          |                         |-- [Start Root/Child Span]  |
  |                          |                         |-- [Execute DB Queries]     |
  |                          |                         |-- [End Span Calculation]   |
  |                          |<-- HTTP 200 OK (Data) --|                            |
  |<-- Return JSON Payload --|    fastcgi_finish_req() |                            |
  |                          |                         |-- [Serialize Spans]        |
  |                          |                         |-- OTLP Batch Export (gRPC)->|
  |                          |                         |    (Non-blocking to Client)|
  |                          |                         |<-- Export Ack -------------|
  |                          |                         |-- [Worker Idle / Next Req] |
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Siklus Hidup Request PHP-FPM vs Observability Hooks
PHP-FPM mengeksekusi request melalui siklus `MINIT` (Module Init), `RINIT` (Request Init), eksekusi skrip, `RSHUTDOWN` (Request Shutdown), dan `MSHUTDOWN` (Module Shutdown).
* **RINIT**: Ekstensi OpenTelemetry mengaitkan (*hook*) dirinya pada Zend Engine executor. Fungsi seperti `zend_execute_ex` di-override untuk merekam awal eksekusi fungsi/metode. Header W3C `traceparent` diekstrak dari larik `$_SERVER`.
* **Execution**: Ketika trace span dibuat, trace context disimpan dalam storage thread-safe (TSRMLS) atau static global execution context.
* **RSHUTDOWN**: Titik paling kritis. Jika batch processor mengirimkan trace melalui synchronous curl/gRPC di sini, latency client membengkak. Karena itu, *flushing* trace harus ditangani sesudah response socket ditutup via `fastcgi_finish_request()` atau didelegasikan ke shared memory/unix socket agent.

### 2. Mekanisme Zero-Downtime Signal Handling
Kubernetes mengirim sinyal `SIGTERM` ke pod saat proses *eviction* atau *rolling update*:
1. **PHP-FPM Master Process**: Menerima `SIGTERM`. Secara default, PHP-FPM langsung menghentikan worker secara agresif. Ini adalah perilaku yang merusak.
2. **Kompensasi Konfigurasi**: Sinyal PHP-FPM harus diarahkan menggunakan `SIGQUIT` untuk graceful stop:
   * Master berhenti menerima koneksi baru pada socket.
   * Master menunggu worker yang sedang aktif hingga batas `process_control_timeout` tercapai.
   * Worker menyelesaikan request yang sedang berjalan, me-flush buffer, dan keluar secara bersih.
3. **Race Condition dengan Ingress**: Endpoint Pod dihapus dari `iptables`/IPVS kube-proxy secara asinkron. Jika PHP-FPM langsung menolak koneksi sebelum kube-proxy memperbarui routing table di Node, request yang sedang mengalir akan menghasilkan HTTP `502 Bad Gateway`. Solusinya adalah menyuntikkan lifecycle hook `preStop` sleep sebelum sinyal diteruskan ke FPM.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Framework SLI, SLO, dan Error Budget untuk Sistem PHP
* **Service Level Indicator (SLI)**: Metrik kuantitatif yang menunjukkan performa sistem aktual.
  $$\text{SLI}_{\text{Availability}} = \frac{\sum \text{Successful Requests } (HTTP < 500)}{\sum \text{Total Requests}} \times 100\%$$
  $$\text{SLI}_{\text{Latency}} = \frac{\sum \text{Requests faster than } 200\text{ms}}{\sum \text{Total Requests}} \times 100\%$$
* **Service Level Objective (SLO)**: Target keandalan yang disepakati, misal: *SLI Availability 99.9% dalam sliding window 30 hari*.
* **Error Budget**: Total toleransi kegagalan dalam window tertentu:
  $$\text{Error Budget} = 100\% - \text{SLO} = 100\% - 99.9\% = 0.1\%$$
  Jika sistem menerima 10.000.000 request/bulan, maka kuota error maksimal adalah 10.000 request HTTP 5xx.

### 2. Distributed Tracing & W3C Trace Context Specification
Untuk menghubungkan span lintas service (misal: PHP Microservice memanggil Go Inventory Service), PHP harus membaca dan mempropagasi header W3C:
* `traceparent`: `version-trace_id-parent_id-trace_flags`
  * Format: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
  * `00`: Versi spesifikasi W3C.
  * `4bf92f3577b34da6a3ce929d0e0e4736`: 16-byte global Unique Trace ID.
  * `00f067aa0ba902b7`: 8-byte Parent Span ID.
  * `01`: Trace Flags (`01` merepresentasikan *recorded/sampled*).
* `tracestate`: Membawa metadata spesifik vendor/tenant tanpa merusak kontinuitas trace global.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi production-ready OpenTelemetry Tracing & Metrics initialization pada PHP 8.3 tanpa framework dependencies eksternal (menggunakan `open-telemetry/sdk`).

```php
<?php
declare(strict_types=1);

namespace Enterprise\Telemetry;

use OpenTelemetry\API\Common\Time\SystemClock;
use OpenTelemetry\API\Trace\Propagation\TraceContextPropagator;
use OpenTelemetry\API\Trace\SpanKind;
use OpenTelemetry\API\Trace\StatusCode;
use OpenTelemetry\API\Trace\TracerInterface;
use OpenTelemetry\Context\Context;
use OpenTelemetry\Context\Propagation\ArrayAccessGetterSetter;
use OpenTelemetry\Contrib\Otlp\SpanExporter;
use OpenTelemetry\SDK\Common\Attribute\Attributes;
use OpenTelemetry\SDK\Resource\ResourceInfo;
use OpenTelemetry\SDK\Resource\ResourceInfoFactory;
use OpenTelemetry\SDK\Trace\Sampler\ParentBased;
use OpenTelemetry\SDK\Trace\Sampler\TraceIdRatioBasedSampler;
use OpenTelemetry\SDK\Trace\SpanProcessor\BatchSpanProcessor;
use OpenTelemetry\SDK\Trace\TracerProvider;
use OpenTelemetry\SemConv\ResourceAttributes;
use Throwable;

final class TelemetryManager
{
    private static ?TracerProvider $tracerProvider = null;
    private static ?TracerInterface $tracer = null;

    /**
     * Inisialisasi Tracing Provider dengan konfigurasi Enterprise
     */
    public static function init(string $serviceName, string $environment, float $sampleRate = 0.1): void
    {
        $resource = ResourceInfoFactory::emptyResource()->merge(
            ResourceInfo::create(Attributes::create([
                ResourceAttributes::SERVICE_NAME => $serviceName,
                ResourceAttributes::DEPLOYMENT_ENVIRONMENT => $environment,
                ResourceAttributes::HOST_NAME => gethostname(),
                ResourceAttributes::PROCESS_PID => getmypid(),
            ]))
        );

        // Ekspor ke OTel Collector lokal melalui gRPC atau HTTP Protobuf
        $exporter = new SpanExporter(
            endpoint: getenv('OTEL_EXPORTER_OTLP_ENDPOINT') ?: 'http://otel-collector:4318/v1/traces'
        );

        // Batch processor untuk efisiensi buffering I/O
        $spanProcessor = new BatchSpanProcessor(
            exporter: $exporter,
            clock: SystemClock::getInstance(),
            maxQueueSize: 2048,
            scheduledDelayMillis: 200,
            exportTimeoutMillis: 1000,
            maxExportBatchSize: 512
        );

        // Sampler: Parent-based dengan fallback ke sampling rasio (misal 10%)
        $sampler = new ParentBased(new TraceIdRatioBasedSampler($sampleRate));

        self::$tracerProvider = new TracerProvider(
            spanProcessors: [$spanProcessor],
            sampler: $sampler,
            resource: $resource
        );

        self::$tracer = self::$tracerProvider->getTracer('enterprise.telemetry.core', '1.0.0');
    }

    public static function getTracer(): TracerInterface
    {
        if (self::$tracer === null) {
            throw new \RuntimeException('TelemetryManager must be initialized before use.');
        }
        return self::$tracer;
    }

    /**
     * Eksekusi callable dalam konteks Span terisolasi dengan auto context-propagation
     */
    public static function traceOperation(string $operationName, callable $callback, array $attributes = []): mixed
    {
        $tracer = self::getTracer();
        
        // Ekstraksi context dari HTTP Request Headers jika ada
        $carrier = getallheaders();
        $context = TraceContextPropagator::getInstance()->extract($carrier, ArrayAccessGetterSetter::getInstance());

        $span = $tracer->spanBuilder($operationName)
            ->setParent($context)
            ->setSpanKind(SpanKind::SPAN_KIND_SERVER)
            ->setAttributes($attributes)
            ->startSpan();

        $scope = $span->activate();

        try {
            return $callback($span);
        } catch (Throwable $e) {
            $span->recordException($e, [
                'exception.escaped' => true,
            ]);
            $span->setStatus(StatusCode::STATUS_ERROR, $e->getMessage());
            throw $e;
        } finally {
            $span->end();
            $scope->detach();
        }
    }

    /**
     * Menjalankan flushing non-blocking pasca response FastCGI selesai
     */
    public static function shutdown(): void
    {
        if (function_exists('fastcgi_finish_request')) {
            fastcgi_finish_request(); // Lepaskan client HTTP socket secara instan
        }

        if (self::$tracerProvider !== null) {
            self::$tracerProvider->shutdown();
        }
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

| Baris / Rentang | Komponen Arsitektur | Analisis Teknis Mendalam |
| :--- | :--- | :--- |
| **Line 26–34** | `ResourceInfoFactory` | Menyusun identitas semantik komponen (*Semantic Conventions*) yang konsisten dengan OpenTelemetry. Memberikan atribut permanen (`service.name`, `deployment.environment`, `host.name`, `process.pid`) pada setiap span yang diekspor. |
| **Line 37–39** | `SpanExporter` | Menentukan destinasi endpoint telemetry. Nilai default diarahkan ke agent/daemonset OTel collector (`otel-collector:4318`) menggunakan transmisi HTTP Protobuf untuk meminimalisir connection establishment overhead. |
| **Line 42–49** | `BatchSpanProcessor` | Mencegah transmisi sinkron per span (*blocking I/O*). Span ditampung dalam antrean buffer internal hingga mencapai `maxExportBatchSize` (512 item) atau timeout `scheduledDelayMillis` (200ms) terpenuhi. |
| **Line 52** | `ParentBased` Sampler | Menerapkan keputusan sampling hierarkis: jika service hulu (misal API Gateway) memutuskan sampling `true`, PHP worker wajib merekam span. Jika hulu tidak menentukan, fallback ke `TraceIdRatioBasedSampler` (10% dari total trafik mandiri). Menghemat storage APM backend. |
| **Line 77–79** | `TraceContextPropagator` | Melakukan deserialisasi header W3C standar (`traceparent`, `tracestate`) dari variabel `getallheaders()`. Menyambungkan ID tracing transaksi terdistribusi dari reverse proxy ke worker PHP. |
| **Line 81–85** | `spanBuilder` | Mengalokasikan node span baru dengan tipe `SPAN_KIND_SERVER`. Span ini menjadi span root lokal atau span anak (*child span*) dari context yang diekstraksi. |
| **Line 87** | `$span->activate()` | Memasukkan span ke dalam Context Engine aktif via thread context/static stack pointer, sehingga library downstream (database wrapper, HTTP client) dapat mengambil parent ID secara implisit. |
| **Line 91–96** | `recordException` | Mencegat *uncaught exception*, mengekstrak stack trace, exception class name, dan pesan error ke dalam span attributes, lalu mengeset status span menjadi `STATUS_ERROR` sebelum bubble up. |
| **Line 98–99** | `$scope->detach()` | Mengembalikan context execution ke scope sebelumnya untuk menghindari memory leak atau konteks trace tercemar pada request berikutnya di worker yang sama. |
| **Line 107–109**| `fastcgi_finish_request` | **Teknik Fundamental SRE**: Memaksa PHP-FPM memutus koneksi dengan reverse proxy (Nginx/Envoy). Reverse proxy langsung merender response ke user, sementara runtime PHP melanjutkan instruksi `tracerProvider->shutdown()` untuk flush data ke OTel Collector secara asinkron tanpa membebani p99 latency user. |

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Insiden Produksi
* **Sistem**: Microservice Pembayaran & Checkout (PHP 8.3-FPM di Kubernetes EKS, 120 Pods).
* **Insiden**: Selama event Flash Sale, terjadi lonjakan trafik 800%. Kubernetes Horizontal Pod Autoscaler (HPA) melakukan *scale-out* agresif dari 40 ke 120 Pod, kemudian melakukan *scale-down* mendadak saat trafik mereda.
* **Gejala Masalah**:
  1. Client mendapati lonjakan HTTP `502 Bad Gateway` sebesar 4.2% tepat saat HPA melakukan scale-down terminasi pod.
  2. Database Connection Pool (PostgreSQL) mengalami kehabisan connection pool (*starvation*) secara mendadak.
  3. APM Trace Dashboard kehilangan 30% root traces selama lonjakan, menyisakan fragmented traces tanpa parent context.
* **Akar Masalah (Root Cause Analysis)**:
  1. Pod PHP-FPM langsung menerima `SIGTERM` dan mati sebelum Nginx Ingress selesai memperbarui routing IPVS table. Request baru masih diarahkan ke Pod yang sedang sekarat.
  2. Worker PHP-FPM ter-kill seketika tanpa menutup transaksi PostgreSQL yang sedang aktif, memicu long-lived connection locks di database.
  3. OTel SDK menggunakan synchronous exporter berbasis cURL pada `register_shutdown_function`, membuat request terkunci hingga 2000ms saat endpoint collector mengalami congestion.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Solusi menyeluruh: Kubernetes Deployment Manifest yang diperkeras (*hardened*), konfigurasi PHP-FPM pool, entrypoint zero-downtime script, dan OTel tracing middleware.

### 1. Hardened PHP-FPM Pool Configuration (`zz-docker.conf`)

```ini
[global]
; Logging ke stdout dalam format raw untuk diparsing log collector
error_log = /proc/self/fd/2
log_level = notice
; Beri waktu worker menyelesaikan eksekusi request sebelum Master mematikan paksa
process_control_timeout = 25s

[www]
listen = /var/run/php-fpm/php-fpm.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660

; Dynamic Process Manager untuk efisiensi Pod
pm = dynamic
pm.max_children = 50
pm.start_servers = 10
pm.min_spare_servers = 5
pm.max_spare_servers = 15
pm.max_requests = 1000 ; Mengatasi degradasi memori fragmentasi Zend Engine

; Status & Ping endpoints untuk Kubernetes Probes
pm.status_path = /fpm-status
ping.path = /fpm-ping
ping.response = pong

; Logging akses FastCGI
access.log = /proc/self/fd/2
access.format = '{"time":"%{%Y-%m-%dT%H:%M:%S%z}t","client":"%{HTTP_X_FORWARDED_FOR}e","uri":"%r","status":%s,"response_time_ms":%d,"cpu_user":%C,"mem_peak_mb":%{mega}M}'

clear_env = no
catch_workers_output = yes
decorate_workers_output = no
```

### 2. Container Entrypoint Script (`entrypoint.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

# Handler graceful termination
_term() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] [INFO] SIGTERM diterima, memulai penghentian graceful PHP-FPM..."
  # Mengirim SIGQUIT ke master process untuk graceful draining
  kill -QUIT "$fpm_pid" 2>/dev/null || true
  wait "$fpm_pid"
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] [INFO] PHP-FPM berhasil dihentikan secara bersih."
}

# Trap sinyal SIGTERM dan SIGINT
trap _term SIGTERM SIGINT

# Mulai PHP-FPM di background untuk menangkap PID
php-fpm -F -R &
fpm_pid=$!

# Tunggu sampai socket file terbentuk
while [ ! -S /var/run/php-fpm/php-fpm.sock ]; do
    sleep 0.1
done
chmod 666 /var/run/php-fpm/php-fpm.sock

echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] [INFO] PHP-FPM Master berjalan dengan PID: $fpm_pid"
wait "$fpm_pid"
```

### 3. Kubernetes Deployment & Pod LifeCycle Manifest (`deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-service
  namespace: production
  labels:
    app.kubernetes.io/name: checkout-service
    app.kubernetes.io/part-of: payment-platform
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app: checkout-service
  template:
    metadata:
      labels:
        app: checkout-service
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: php-fpm
          image: internal-registry.corp/checkout/php:8.3-v1.4.2
          imagePullPolicy: IfNotPresent
          lifecycle:
            preStop:
              exec:
                # KRITIKAL: Tunggu 10 detik agar kube-proxy/ingress mencabut IP Pod dari routing table
                # sebelum mengirim sinyal penghentian ke PHP-FPM
                command: ["/bin/sh", "-c", "sleep 10"]
          env:
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://$(HOST_IP):4318/v1/traces"
            - name: HOST_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.hostIP
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "1024Mi"
          volumeMounts:
            - name: shared-socket
              mountPath: /var/run/php-fpm
          readinessProbe:
            exec:
              command:
                - /usr/bin/env
                - SCRIPT_NAME=/fpm-ping
                - SCRIPT_FILENAME=/fpm-ping
                - REQUEST_METHOD=GET
                - cgi-fcgi
                - -bind
                - -connect
                - /var/run/php-fpm/php-fpm.sock
            initialDelaySeconds: 3
            periodSeconds: 5
            timeoutSeconds: 2
            successThreshold: 1
            failureThreshold: 3
          livenessProbe:
            exec:
              command:
                - /usr/bin/env
                - SCRIPT_NAME=/fpm-ping
                - SCRIPT_FILENAME=/fpm-ping
                - REQUEST_METHOD=GET
                - cgi-fcgi
                - -bind
                - -connect
                - /var/run/php-fpm/php-fpm.sock
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3

        - name: nginx-sidecar
          image: internal-registry.corp/base/nginx-sidecar:1.25-alpine
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
          lifecycle:
            preStop:
              exec:
                command: ["/usr/sbin/nginx", "-s", "quit"]
          volumeMounts:
            - name: shared-socket
              mountPath: /var/run/php-fpm
          ports:
            - name: http
              containerPort: 8080

      volumes:
        - name: shared-socket
          emptyDir: {}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Pola Pod Topologi: Sidecar Nginx vs Ingress Langsung FastCGI

| Parameter Evaluasi | Pola: Sidecar Nginx + PHP-FPM (Dipilih) | Pola: Ingress Langsung ke PHP-FPM (TCP FastCGI) |
| :--- | :--- | :--- |
| **Kompleksitas Pod** | **Tinggi**: Membutuhkan 2 kontainer per pod, emptyDir volume sharing, konfigurasi IPC. | **Rendah**: Hanya satu container PHP-FPM yang langsung diekspos melalui service TCP. |
| **Performa Latensi** | **Optimal**: Komunikasi via Unix Domain Socket (UDS) tanpa overhead TCP stack di localhost. | **Sub-optimal**: Melewati TCP loopback; overhead koneksi FastCGI dari Ingress controller. |
| **Static File Handling** | Nginx langsung melayani file statis tanpa membebani proses interpreter PHP. | Seluruh request (termasuk statis) berpotensi membebani proses worker PHP. |
| **Buffering & Streaming**| Nginx menangani slow-client network buffering; worker PHP segera bebas. | Worker PHP tertahan (*blocked*) jika network client lambat membaca chunk response. |
| **Konsumsi Memori** | Menambah alokasi ~20MB–50MB memory per Pod untuk Nginx runtime. | Zero memory footprint tambahan selain FPM engine. |

### Instrumentasi OpenTelemetry: C-Extension vs Pure Userland PHP SDK

| Aspek | OTel C-Extension (`ext-opentelemetry`) | Pure PHP Userland SDK |
| :--- | :--- | :--- |
| **CPU Overhead** | **Sangat Rendah** (~1.5%–3% latency impact). Hook langsung di Zend Execution Core. | **Tinggi** (~10%–25% latency impact) karena interpretasi AST runtime. |
| **Instalasi & Portabilitas**| Membutuhkan kompilasi C via `pecl`/`docker-php-ext-install`. Bergantung versi libc. | Cukup `composer require`. Portabilitas 100% di semua lingkungan PHP 8+. |
| **Auto-Instrumentation**| Mendukung *auto-hooking* internal fungsi (PDO, cURL, Redis, Guzzle) secara deklaratif. | Harus membungkus class wrapper manual (*decorator pattern*) atau proxy layer. |
| **Debuggability** | Sulit di-debug jika terjadi Segmentation Fault (harus via GDB/Valgrind core dump). | Sangat mudah di-trace dan di-debug melalui standard PHP exception mechanisms. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Memory Leak dalam Long-Running Sub-processes
Meskipun PHP-FPM membersihkan memori antar HTTP request, objek telemetry yang disimpan dalam singleton static storage (seperti context array) yang tidak di-detach dengan benar via `$scope->detach()` akan memicu memory exhaustion jika worker memproses ribuan request (`pm.max_requests` diset terlalu tinggi).

### 2. Cascading Failure dari OpenTelemetry Collector Timeout
Jika OTel Collector DaemonSet crash atau kehabisan memori, PHP workers yang mencoba mengirim spans via synchronous OTLP HTTP akan mengalami hang selama durasi timeout default (biasanya 5–10 detik).
* **Solusi**: Atur konfigurasi timeout jaringan ekspor secara ketat:
  ```php
  $spanProcessor = new BatchSpanProcessor($exporter, timeout: 500); // 500ms max
  ```
  Dan gunakan `SystemClock` non-blocking dengan buffer queue terisolasi.

### 3. Kehilangan Konteks Async Job (Horizon/Message Queue)
Context propagation W3C seringkali putus saat sebuah request melempar message ke AMQP/Kafka.
* **Gejala**: Log transaksi backend consumer memunculkan `trace_id` baru, membuat tracking end-to-end terputus.
* **Mitigasi**: Selalu serialize dan inject W3C header ke dalam payload metadata queue:
  ```php
  $headers = [];
  TraceContextPropagator::getInstance()->inject($headers, ArrayAccessGetterSetter::getInstance());
  $queuePayload = ['body' => $data, '_telemetry_context' => $headers];
  ```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Ekspor Telemetri Secara Sinkron dalam Jalur Eksekusi User
❌ **SALAH**: Melakukan network call ekspor span sebelum merender response ke client.
```php
// SALAH: Client menunggu OTel push selesai!
$span->end();
$tracerProvider->getSpanProcessor()->forceFlush(); // HTTP POST Collector 150ms!
echo json_encode($data);
```

✔ **BENAR**: Tutup response client terlebih dahulu menggunakan FastCGI feature, baru jalankan proses flushing.
```php
// BENAR: Mengembalikan response instan, flush dikerjakan di background worker
echo json_encode($data);
if (function_exists('fastcgi_finish_request')) {
    fastcgi_finish_request();
}
$span->end();
$tracerProvider->shutdown();
```

### 2. Menggunakan Liveness Probe yang Terhubung ke Dependency Eksternal
❌ **SALAH**: Membuat endpoint `/healthz` yang memeriksa koneksi database PostgreSQL dan Redis.
```php
// Jika Database lambat/fail, Kubernetes membunuh SEMUA POD secara bersamaan!
// Terjadi cascading reboot storm.
if (!$db->ping()) {
    http_response_code(500);
    exit;
}
```

✔ **BENAR**: Pisahkan Liveness Probe dan Readiness Probe.
* **Liveness Probe**: Hanya memeriksa apakah proses runtime lokal (PHP-FPM worker) masih merespons loop (`ping.path = /fpm-ping`).
* **Readiness Probe**: Memeriksa apakah pod siap menerima trafik (resource internal siap).
* Jika database down, service harus merespons HTTP 503 ke client, BUKAN membiarkan Kubernetes me-restart kontainer tanpa henti.

### 3. Log Ingestion Mengabaikan Correlation ID
❌ **SALAH**: Log plain text tanpa integrasi TraceID.
```php
$logger->error("Payment execution failed for user: " . $userId);
```

✔ **BENAR**: Menyuntikkan `trace_id` dan `span_id` secara otomatis ke format log JSON terstruktur.
```php
use OpenTelemetry\API\Trace\Span;

$spanContext = Span::getCurrent()->getContext();
$logger->error("Payment execution failed", [
    'trace_id' => $spanContext->getTraceId(),
    'span_id' => $spanContext->getSpanId(),
    'user_id' => $userId,
    'context' => 'financial_checkout'
]);
```

### 4. Menggunakan `pm = static` pada Node Kubernetes Berskala Dinamis
❌ **SALAH**: Mengunci alokasi proses worker PHP (`pm.max_children = 100`) statis pada container dengan memory limit rendah (512MB).
* **Efek**: Saat lonjakan request, 100 worker mengalokasikan 100 * 30MB = 3GB memori -> Kernel memicu `OOMKilled` (Exit Code 137).

✔ **BENAR**: Hitung batas memori berdasarkan cgroup pod dan gunakan alokasi dinamis (`pm = dynamic`) atau hitung batas absolut:
$$\text{pm.max\_children} = \frac{\text{Container Memory Limit} - \text{Baseline Overhead (128MB)}}{\text{Peak Worker Memory Consumption (e.g., 40MB)}}$$

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Semantic Attributes Standard**: Ikuti format OpenTelemetry Semantic Conventions (v1.24+). Gunakan atribut:
   * `http.response.status_code` (integer, e.g., 200)
   * `http.request.method` (string, e.g., "GET")
   * `db.system` (string, e.g., "postgresql")
   * `db.statement` (sanitized query string)
2. **Container Security Compliance**:
   * Kontainer PHP-FPM dan Nginx harus berjalan dengan `runAsNonRoot: true` dan UID non-zero (misal `UID 10001: appuser`).
   * Pasang `readOnlyRootFilesystem: true` dan mounting direktori volatile (`/tmp`, `/var/run`, `/var/log`) via `emptyDir`.
3. **Structured In-flight Masking**: Terapkan filter regular expression di level logging & trace enrichment untuk nomor kartu kredit (PCI-DSS), token JWT, dan kata sandi sebelum serialisasi keluar dari Pod.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Head-Based vs Tail-Based Sampling
Instrumentasi telemetri berskala masif menghasilkan beban jaringan dan biaya storage APM yang eksorbitan.
* **Head-Based Sampling**: Keputusan untuk merekam span diambil di awal request (ingress/gateway layer). Kelemahannya: Trace yang menghasilkan HTTP 500 bisa lolos tidak terekam jika masuk ke dalam 90% traffic yang diabaikan.
* **Tail-Based Sampling**: Seluruh span sementara disimpan di OTel Collector daemonset/buffer. Collector mengevaluasi trace secara menyeluruh: jika trace memiliki atribut `http.status_code >= 500` atau latensi > 1500ms, trace disimpan 100%. Jika trace normal (200 OK, latency < 50ms), collector hanya menyimpan 1%.

```
[PHP-FPM Worker] --(100% Spans via UDS/Localhost)--> [OTel Collector Contrib]
                                                            |
                                               Evaluasi Sampling Logic:
                                               - Error? -> Simpan 100%
                                               - Slow?  -> Simpan 100%
                                               - Normal -> Simpan 1%
                                                            |
                                                            +---> [Backend APM]
```

---

# SEKSI 16 — KEAMANAN & HARDENING

### Sanitasi Telemetri dan Isolasi Context Eksekusi
Span attributes rentan menjadi celah kebocoran data (*data leakage*) jika parameter database atau payload HTTP mengandung PII (Personally Identifiable Information).

```php
<?php
declare(strict_types=1);

namespace Enterprise\Security;

use OpenTelemetry\API\Trace\SpanInterface;

final class DataSanitizer
{
    private const PII_PATTERNS = [
        '/(\b[0-9]{4}[- ]?){3}[0-9]{4}\b/' => '[REDACTED_CC]',      // Credit Card
        '/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/' => '[REDACTED_EMAIL]', // Email
        '/(bearer\s+[a-zA-Z0-9_\-\.]+)/i'   => 'Bearer [REDACTED_TOKEN]' // JWT
    ];

    public static function sanitizeAttributes(array $attributes): array
    {
        $sanitized = [];
        foreach ($attributes as $key => $value) {
            if (is_string($value)) {
                $sanitized[$key] = preg_replace(
                    array_keys(self::PII_PATTERNS),
                    array_values(self::PII_PATTERNS),
                    $value
                );
            } else {
                $sanitized[$key] = $value;
            }
        }
        return $sanitized;
    }

    public static function secureSetAttribute(SpanInterface $span, string $key, mixed $value): void
    {
        if (is_string($value)) {
            $maskedValue = preg_replace(
                array_keys(self::PII_PATTERNS),
                array_values(self::PII_PATTERNS),
                $value
            );
            $span->setAttribute($key, $maskedValue);
            return;
        }
        $span->setAttribute($key, $value);
    }
}
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Standar Log JSON Terstruktur Berorientasi OTel
Setiap baris log yang dihasilkan oleh aplikasi PHP harus berupa JSON valid satu baris (*single-line JSON*) yang diinjeksikan Trace Context secara terpadu.

```json
{
  "timestamp": "2026-03-31T08:14:22.104Z",
  "severity": "ERROR",
  "service": {
    "name": "checkout-service",
    "version": "1.4.2",
    "environment": "production"
  },
  "trace": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7",
    "sampled": true
  },
  "message": "Payment gateway timeout after 3000ms",
  "exception": {
    "class": "Enterprise\\Payment\\GatewayTimeoutException",
    "code": 504,
    "file": "/var/www/html/src/Gateway/StripeAdapter.php",
    "line": 84
  },
  "http": {
    "method": "POST",
    "url": "/api/v1/checkout/process",
    "client_ip": "203.0.113.195"
  }
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### 1. Sinyal Kendali PHP-FPM Master Process
* `kill -QUIT <pid>`: **Graceful stop**. Menunggu in-flight requests selesai sebelum keluar.
* `kill -USR1 <pid>`: **Re-open log files**. Digunakan oleh utility logrotate.
* `kill -USR2 <pid>`: **Graceful reload**. Reload konfigurasi worker dan binary tanpa memutus master listener socket.

### 2. OTel Collector Environment Variables Vital
```bash
OTEL_PHP_AUTOLOAD_ENABLED=true
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=none # Nonaktifkan jika scrape via Prometheus endpoint
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
OTEL_PROPAGATORS=tracecontext,baggage
```

### 3. Perintah Diagnostik Eksekusi FastCGI
* Uji liveness endpoint via CLI tanpa cURL:
  ```bash
  cgi-fcgi -bind -connect /var/run/php-fpm/php-fpm.sock
  ```
* Pantau status worker PHP-FPM secara realtime:
  ```bash
  SCRIPT_NAME=/fpm-status SCRIPT_FILENAME=/fpm-status QUERY_STRING=full REQUEST_METHOD=GET \
  cgi-fcgi -bind -connect /var/run/php-fpm/php-fpm.sock
  ```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. **Mengapa pemanggilan fungsi `fastcgi_finish_request()` sangat krusial dalam pipeline observabilitas PHP-FPM?**
   * *Jawaban*: Fungsi tersebut langsung menutup koneksi socket HTTP dan me-render respons secara instan ke reverse proxy/user, sehingga operasi IO yang mahal seperti serialisasi trace dan flush network export ke OTel Collector dieksekusi setelah response terkirim tanpa menambah latency p99 user.

2. **Apa perbedaan struktural antara `trace_id` dan `span_id` pada spesifikasi W3C Trace Context?**
   * *Jawaban*: `trace_id` adalah identifikasi unik 16-byte (32 digit hex) yang merepresentasikan keseluruhan perjalanan siklus hidup request di seluruh node terdistribusi, sedangkan `span_id` adalah identifikasi unik 8-byte (16 digit hex) yang merepresentasikan durasi eksekusi unit kerja individual pada satu komponen/fungsi tertentu.

3. **Mengapa direktif `clear_env = no` wajib diset pada pool configuration PHP-FPM di Kubernetes?**
   * *Jawaban*: Secara default PHP-FPM membersihkan (*clears*) semua environment variable sistem pada worker process. Menyetel ke `no` memastikan environment variable injeksi Kubernetes (seperti database credentials, cluster secret, dan OTel endpoints) dapat diakses via `getenv()` atau `$_ENV`.

4. **Sinyal UNIX mana yang harus dikirimkan ke PHP-FPM Master process agar tidak memicu HTTP 502 saat proses rolling update Kubernetes?**
   * *Jawaban*: Sinyal `SIGQUIT`. Sinyal ini memerintahkan master process untuk berhenti menerima koneksi baru dan membiarkan child processes menyelesaikan in-flight request yang sedang aktif.

5. **Apa fungsi dari header HTTP `traceparent`?**
   * *Jawaban*: Membawa konteks trace terdistribusi antar sistem via protokol HTTP yang mencakup version, trace ID, parent span ID, dan sampling flags sesuai konsensus W3C.

---

### Soal Tingkat Menengah (Intermediate)
6. **Mengapa konfigurasi `preStop: exec: command: ["sleep", "10"]` dibutuhkan pada kontainer PHP-FPM di dalam Pod Kubernetes?**
   * *Jawaban*: Proses pencabutan endpoint Pod dari IPVS/iptables ingress controller di Kubernetes berjalan secara asinkron. Jeda *sleep* mencegah kontainer mematikan listen socket sebelum ingress selesai menghapus IP Pod dari routing table, sehingga mencegah terjadinya koneksi HTTP 502 Bad Gateway pada request yang masuk di saat bersamaan.

7. **Bagaimana cara mencegah collector exhaustion jika microservice PHP mengalami lonjakan error secara masif?**
   * *Jawaban*: Mengonfigurasi `BatchSpanProcessor` dengan membatasi parameter `maxQueueSize` (misal 2048) sehingga kelebihan span dibuang (*dropped*) alih-alih meledakkan memori proses PHP, mengaktifkan `memory_limiter` processor di OpenTelemetry Collector, serta menerapkan circuit breaker pada exporter OTLP.

8. **Mengapa Liveness Probe tidak boleh digunakan untuk memverifikasi koneksi database service hilir (*downstream*)?**
   * *Jawaban*: Jika database mengalami latensi tinggi atau downtime, Liveness Probe pada semua Pod PHP akan gagal serentak. Kubernetes akan merestart seluruh kontainer secara berantai (*restart storm*), memperparah degradasi jaringan dan menghalangi pemulihan database.

9. **Apa dampak performa jika trace attributes diisi dengan string query SQL mentah tanpa sanitasi prepared statements?**
   * *Jawaban*: Selain menimbulkan risiko keamanan kebocoran kredensial/PII, string query SQL berukuran besar meningkatkan konsumsi memori alokasi Zend Engine secara signifikan dan memperlambat serialisasi Protobuf/JSON saat pengiriman batch span.

10. **Bagaimana mekanisme `ParentBased` Sampler menentukan apakah request PHP lokal harus ditrace atau tidak?**
    * *Jawaban*: Sampler ini memprioritaskan keputusan sampling dari node upstream yang ada pada context flag `traceparent`. Jika request datang dari gateway yang telah men-sample transaksi (`flags = 01`), PHP akan 100% merekam span tersebut; jika upstream tidak men-sample (`flags = 00`), PHP tidak merekam. Jika tanpa upstream, sampler fallback ke konfigurasi rasio lokal.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Rancang Bangun: Observable & Fault-Tolerant Checkout Engine
Buatlah sebuah implementasi purwarupa production-ready mikro-layanan checkout yang memiliki ketahanan mutlak terhadap terminasi mendadak.

#### Spesifikasi Proyek:
1. **Runtime Framework**: PHP 8.3 CLI/FPM murni (tanpa framework Laravel/Symfony).
2. **Kebutuhan Tracing**:
   * Tangkap incoming HTTP header W3C `traceparent`.
   * Buat root span `POST /checkout`.
   * Buat sub-span manual `database_save_order` yang mensimulasikan latensi operasi DB selama 150ms.
   * Buat sub-span manual `payment_gateway_call` yang mensimulasikan pemanggilan HTTP external API dengan sampling atribut status sanitasi.
3. **Kebutuhan Resiliensi Deployment**:
   * Siapkan `Dockerfile` multi-stage build yang memisahkan stage build composer dengan minimal runtime base image alpine.
   * Terapkan konfigurasi non-root UID 10001.
   * Siapkan `docker-compose.yaml` yang menghubungkan Pod/Container aplikasi checkout dengan local `otel-collector`, `jaeger-all-in-one`, dan reverse proxy `nginx`.
4. **Chaos Testing Scenario**:
   * Jalankan pengujian beban menggunakan tools seperti `k6` atau `hey` dengan konkurensi 50 requests/detik.
   * Di tengah pengujian, kirimkan perintah `docker kill -s SIGTERM <php-container-id>` atau `kubectl delete pod` secara mendadak.
   * **Target**: Validasi melalui Jaeger UI bahwa tidak ada transaksi aktif yang terputus di tengah jalan, seluruh in-flight request sukses diselesaikan dengan status `200 OK`, dan trace ID tetap utuh terekam di Jaeger tanpa ada missing parent spans.