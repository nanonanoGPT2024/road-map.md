# BAB 10: Enterprise SRE, Observability, & Cloud-Native Deployment
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonfigurasi dan mengoperasikan instrumentasi *Full-Stack Observability* (Tracing, Metrics, Logs/Telemetry) berbasis standar industri OpenTelemetry (OTel) dan Prometheus pada *runtime* PHP 8.x (PHP-FPM, RoadRunner, dan FrankenPHP).
- Merancang arsitektur agregasi metrik non-blocking yang mengatasi limitasi model *shared-nothing* memori PHP menggunakan APCu, Redis, atau Shared Memory (`sysvshm`/IPC).
- Mengintegrasikan *continuous production profiling* berbasis sampling (Excimer / Pyroscope) dengan *overhead* CPU di bawah 1.5% pada skala jutaan transaksi per hari.
- Mengimplementasikan mekanisme *Graceful Shutdown*, manajemen sinyal POSIX (`SIGTERM`, `SIGQUIT`), dan orkestrasi *Kubernetes Lifecycle Probes* (Startup, Liveness, Readiness) tanpa *downtime* atau *dropped TCP connections*.
- Menganalisis *distributed trace contexts* (W3C TraceContext format) lintas *boundary* RPC/HTTP/Message Queue untuk mitigasi degradasi latensi p99 dan p99.9.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- Arsitektur internal PHP 8.x (Zend VM lifecycle: `MINIT`, `RINIT`, `RSHUTDOWN`, `MSHUTDOWN`).
- Mekanisme eksekusi PHP-FPM (`pm = dynamic/static`, *worker processes*, FastCGI binary protocol).
- Dasar containerization Docker & orkestrasi Kubernetes (Pod lifecycle, Service, Ingress, probes).
- Protokol networking: HTTP/1.1, HTTP/2, TCP handshake, DNS resolution, Unix Domain Sockets (UDS).
- Konsep dasar SRE: SLI (Service Level Indicator), SLO (Service Level Objective), SLA, Error Budget, dan MTTR/MTTD.

---

### 3. Concept & Internal Architecture

#### 3.1. Paradigma Observabilitas: PHP-FPM vs Persistent Runtimes
Pada arsitektur runtime modern (Go, Java, Node.js), proses aplikasi bersifat *long-running* dan membagi *memory heap* antar thread/coroutine. Metrik in-memory dapat diakumulasi secara atomik menggunakan struktur data global.

Sebaliknya, PHP tradisional (PHP-FPM) mengadopsi model **Shared-Nothing Memory Architecture**:
1. Setiap HTTP request dialokasikan ke satu worker process yang terisolasi.
2. Siklus hidup request diawali dengan `RINIT` (Request Init) dan diakhiri dengan `RSHUTDOWN` (Request Shutdown).
3. Pada fase `RSHUTDOWN`, seluruh alokasi memori Zend Engine di-purge (`zend_mem_heap_destroy`). Variabel in-memory yang menyimpan metrik seperti counter atau histogram akan musnah seketika.

```
+-----------------------------------------------------------------------------------+
|                        PHP-FPM Worker Lifecycle & Memory Isolation                |
+-----------------------------------------------------------------------------------+
| Request Ingress -> FastCGI -> [RINIT] -> [Execute Script] -> [RSHUTDOWN] -> Reset |
|                                   |             |                 |               |
|                                   v             v                 v               |
|                           Local Zend Heap   Allocations    zend_mem_heap_destroy  |
|                               (0 state)    (Transient)       (Memory Freed)       |
+-----------------------------------------------------------------------------------+
                                        | (IPC / SHM Bridge Required)
                                        v
+-----------------------------------------------------------------------------------+
|  Shared Storage Layer: APCu / Linux tmpfs Shared Memory / Redis / OTel Daemon     |
+-----------------------------------------------------------------------------------+
```

Untuk mengimplementasikan metrik sistem seperti Prometheus (berbasis model *pull/scraping* via HTTP endpoint `/metrics`), PHP-FPM membutuhkan jembatan *inter-process state*:
- **APCu (`apc_inc`, `apc_fetch`)**: Memori bersama berbasis C extension di shared memory Linux (`shmget`/`mmap`).
- **Disk/tmpfs Buffer**: File sementara di `/dev/shm` yang diakses via atomik locks atau lock-free atomic CAS (*Compare-And-Swap*).
- **In-Memory Store (Redis/Dragonfly)**: Sentralisasi state metrik lokal per Node Pod.

Pada *persistent runtimes* modern seperti **FrankenPHP** (Caddy based) atau **RoadRunner** (Go worker manager), siklus hidup aplikasi berada di dalam loop *worker*, di mana state metrik Prometheus dapat dipertahankan di memory Go/C runtime tanpa dependensi I/O eksternal.

#### 3.2. OpenTelemetry Tracing Internals: W3C TraceContext
OpenTelemetry PHP bekerja pada dua layer:
1. **C Extension (`ext-opentelemetry`)**: Mengaitkan *hook* pada level Zend VM bytecode execution (`zend_execute_ex` and `zend_execute_internal`). Ini mencegat pemanggilan fungsi (seperti PDO, cURL, Guzzle, Redis) secara transparan dengan *overhead* minimum tanpa modifikasi *userland code*.
2. **Userland SDK**: Mengelola alokasi span, parentage, attribute injection, sampling decision (*Head-based* vs *Tail-based*), serta ekspor buffer عبر gRPC atau OTLP/HTTP.

W3C Context Propagation mewajibkan transmisi HTTP Header standar:
- `traceparent`: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
  - `version`: `00` (1 byte hex)
  - `trace-id`: `4bf92f3577b34da6a3ce929d0e0e4736` (16 bytes hex)
  - `parent-id`/`span-id`: `00f067aa0ba902b7` (8 bytes hex)
  - `trace-flags`: `01` (1 byte bitmap, bit `01` menandakan *sampled*)
- `tracestate`: Menyimpan metadata *vendor-specific* dalam pasangan key-value.

#### 3.3. Sampling Profiler Internals (Excimer Engine)
Berbeda dengan profiler deterministik seperti Xdebug (yang menyuntikkan instruksi ke setiap opcode call dan memperlambat throughput hingga 300%-1000%), **Continuous Sampling Profiler** seperti **Excimer** (dikembangkan oleh Wikimedia Foundation) menggunakan interupsi *POSIX timer* (`setitimer` / `timer_create` dengan `SIGPROF`).

```
Interval POSIX SIGPROF (e.g., 10ms)
       |
       v
+--------------+     +--------------+     +--------------+
| Worker Thread| --> | Worker Thread| --> | Worker Thread|
| (Opcode Exec)|     | (Opcode Exec)|     | (Opcode Exec)|
+--------------+     +--------------+     +--------------+
       |
       +---> [SIGPROF Handler Catches Zend VM Callstack Frame]
             Record: Function Name, File, Line
             Increment: Stack Trace Occurrence in Buffer
```

Profiler menghentikan eksekusi Zend VM setiap interval tertentu (misal: 10ms), merekam *snapshot* dari `EG(current_execute_data)`, mengagregasikannya menjadi format *collapsed stack traces* atau *pprof*, lalu melanjutkan eksekusi program. Pendekatan statistik ini membatasi *overhead* CPU rata-rata di bawah 1.5%.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik Klasik | Modern Enterprise Cloud-Native PHP |
| :--- | :--- | :--- |
| **Telemetry Format** | Log teks tidak terstruktur (plain text ke file `storage/logs/laravel.log`) | Structured JSON (ECS/OTel Schema) dialirkan langsung ke `/dev/stdout` & `/dev/stderr` |
| **Tracing System** | Request ID lokal, terputus saat request keluar via cURL/Guzzle | W3C Distributed Context Propagation terinjeksi otomatis via OTel instrumentation |
| **Metric Scraping** | Push metrics via cron jobs atau synchronous query ke database | Prometheus Pull Architecture menggunakan local *shared memory engine* atau Sidecar agent |
| **Runtime Scaling** | VM statis dengan alokasi worker FPM tetap | Horizontal Pod Autoscaler (HPA) K8s berbasis metrik kustom (Request Per Second, P95 Latency) |
| **Lifecycle Hooks** | Kill process langsung via `kill -9` atau restart Apache/Nginx kasar | Graceful draining dengan `SIGQUIT`/`SIGTERM`, preStop lifecycle hooks, & probe K8s |

- **Apa itu?** Observabilitas enterprise bukan sekadar instalasi dashboard grafis, melainkan penyelarasan tiga pilar (*Traces, Metrics, Logs*) yang diikat oleh satu identitas: `TraceID` dan `SpanID`, diekspor secara asinkron tanpa memblokir I/O transaksi pengguna.
- **Mengapa krusial?** Dalam arsitektur microservices atau distributed enterprise, kegagalan request di satu service dapat merambat ke puluhan dependensi lain (*cascading failure*). Tanpa distributed context dan high-resolution metrics, melacak *root cause* dari lonjakan latensi p99 akan menghabiskan waktu berjam-jam (MTTR tinggi).

---

### 5. How (Workflow Detail)

Alur kerja instrumen observabilitas lengkap dalam cluster Kubernetes:

```
[Client Request]
       |
       v (HTTP Request with/without Traceparent)
+------------------------------------------------------------------------------------+
| K8s Ingress Controller (Envoy / Traefik / NGINX Ingress)                           |
| -> Extracts/Generates W3C Trace ID                                                |
| -> Forwards traceparent downstream                                                |
+------------------------------------------------------------------------------------+
       |
       v (Unix Domain Socket / TCP)
+------------------------------------------------------------------------------------+
| Pod: PHP Application Container                                                     |
|                                                                                    |
| 1. Web Server / SAPI (FrankenPHP / PHP-FPM)                                        |
| 2. ext-opentelemetry / Composer SDK:                                               |
|    - Parses W3C Context from $_SERVER['HTTP_TRACEPARENT']                          |
|    - Starts Root/Child Span                                                        |
| 3. Application Execution:                                                          |
|    - Logger injects TraceId & SpanId to Structured JSON Log                        |
|    - Prometheus APCu Registry records duration histogram & counter                 |
| 4. End Request:                                                                    |
|    - Span buffer flushed asynchronously via OTLP (gRPC) to Sidecar                 |
+------------------------------------------------------------------------------------+
       |                                              |
       | (OTLP via gRPC: 4317)                        | (Metrics Scrape via HTTP: 9145)
       v                                              v
+---------------------------------+          +--------------------------------------+
| Pod Sidecar: OTel Collector     |          | Prometheus Server / VictoriaMetrics  |
| - Batching                      |          +--------------------------------------+
| - Tail-based Sampling Filter    |
+---------------------------------+
       |
       +-----> Jaeger / Tempo / Datadog
```

1. **Ingress Arrival**: Request masuk ke Ingress Controller; `traceparent` di-generate jika belum tersedia.
2. **Context Hydration**: Hook PHP engine membaca header `HTTP_TRACEPARENT` dan menginisialisasi `TracerProvider`.
3. **Execution & Instrumentation**:
   - Query SQL PDO dibungkus *Span* child otomatis.
   - Panggilan HTTP downstream (via Guzzle) disuntikkan header `traceparent` baru.
   - Logger terstruktur (Monolog) meng-enrich payload log dengan field `trace_id`, `span_id`, dan `service.name`.
   - Waktu eksekusi dicatat ke Prometheus Histogram di dalam shared memory buffer.
4. **Transport**:
   - Log dialirkan ke `stdout` (dikoleksi oleh DaemonSet FluentBit / Vector).
   - Metrik dipaparkan di endpoint `/metrics` internal.
   - Trace dikirim secara *non-blocking* ke OpenTelemetry Collector Sidecar Pod melalui protocol OTLP/gRPC.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Skala Besar
- **PHP-FPM Worker**: Counter imigrasi individual. Begitu satu penumpang selesai, petugas imigrasi membersihkan mejanya secara total (*Shared-Nothing*).
- **W3C Traceparent**: Paspor penumpang dengan stempel nomor registrasi global. Di konter imigrasi, bagasi, maupun boarding gate, paspor yang sama distempel tanpa membuat nomor baru (*Context Propagation*).
- **APCu Prometheus Collector**: Papan pengumuman elektronik sentral bandara. Setiap petugas imigrasi menekan tombol lokal untuk menambah jumlah antrean di layar sentral tanpa harus meninggalkan meja (*Shared Memory Aggregate*).
- **Excimer Continuous Profiler**: Pengawas keamanan yang mengambil foto bandara setiap 10 detik. Dari kompilasi ribuan foto acak, manajemen tahu area mana yang paling sering macet tanpa harus membuntuti setiap penumpang secara individual (*Sampling Profiler*).

#### Arsitektur Orkestrasi Pod Produksi
```
+------------------------------------------------------------------------------------------+
| KUBERNETES POD ARCHITECTURE                                                              |
|                                                                                          |
|  +-------------------------------------+         +------------------------------------+  |
|  | Container: app-php-engine           |         | Container: otel-collector-sidecar  |  |
|  |                                     |         |                                    |  |
|  |  +-------------------------------+  |         |  +------------------------------+  |  |
|  |  | PHP 8.3 + FrankenPHP/FPM      |  |         |  | OpenTelemetry Collector      |  |  |
|  |  | - App Code                    |  |         |  | Receivers:                   |  |  |
|  |  | - ext-opentelemetry           |  |  OTLP   |  |   otlp: [grpc://127.0.0.1:4317|  |  |
|  |  | - ext-apcu (Prometheus Store) |==|========>| Processors:                     |  |  |
|  |  +-------------------------------+  | (gRPC)  |   batch, memory_limiter         |  |  |
|  |                 |                   |         | Exporters:                      |  |  |
|  |                 v                   |         |   otlp/tempo, otlp/jaeger       |  |  |
|  |        +-----------------+          |         +------------------------------------+  |
|  |        | /dev/stdout     |          |                            |                    |
|  |        +-----------------+          |                            | Export             |
|  +-----------------|-------------------+                            v                    |
|                    | (JSON Logs)                 +------------------------------------+  |
|                    v                             | Remote Telemetry Backend           |  |
|         Container Runtime Engine                 | (Grafana Mimir/Tempo/Loki)         |  |
|        (CRI collects stdout/stderr)              +------------------------------------+  |
+------------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Inisialisasi OpenTelemetry Manual & Context Propagation
Contoh kode berikut menunjukkan cara kerja fundamental propagasi konteks trace W3C tanpa *magic framework*.

```php
<?php
declare(strict_types=1);

require_once __DIR__ . '/vendor/autoload.php';

use OpenTelemetry\API\Globals;
use OpenTelemetry\API\Trace\Propagation\TraceContextPropagator;
use OpenTelemetry\Context\Context;
use OpenTelemetry\SDK\Trace\TracerProviderFactory;

// 1. Inisialisasi Global Tracer Provider
putenv('OTEL_SERVICE_NAME=payment-authenticator');
putenv('OTEL_TRACES_EXPORTER=none'); // Sandbox mode (memory-only)

$tracerProvider = (new TracerProviderFactory())->create();
Globals::tracerProvider()->registerIfAbsent($tracerProvider);

$tracer = Globals::tracerProvider()->getTracer('io.enterprise.payment');

// 2. Simulasi Request Masuk dengan Header W3C dari Ingress
$incomingHeaders = [
    'traceparent' => '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
];

// Extract context dari header
$extractedContext = TraceContextPropagator::getInstance()->extract($incomingHeaders);

// 3. Jalankan Span dengan parent context yang diekstrak
$rootSpan = $tracer->spanBuilder('AuthorizeCardPayment')
    ->setParent($extractedContext)
    ->setAttribute('payment.gateway', 'cybersource')
    ->setAttribute('payment.amount', 1500000)
    ->setAttribute('payment.currency', 'IDR')
    ->startSpan();

// Aktivasi context di execution scope
$scope = $rootSpan->activate();

try {
    // Simulasi logic internal
    $childSpan = $tracer->spanBuilder('ValidateCardChecksum')
        ->startSpan();
    
    // Do work...
    usleep(15000); // 15ms latency
    $childSpan->end();
    
    echo sprintf(
        "Trace ID: %s | Active Span ID: %s\n",
        $rootSpan->getContext()->getTraceId(),
        $rootSpan->getContext()->getSpanId()
    );
} finally {
    $rootSpan->end();
    $scope->detach();
}
```

#### 7.2. Practical Example: Production-Grade Telemetry Stack
Berikut adalah implementasi sistem produksi yang mencakup:
1. **Telemetry Pipeline Processor** (Monolog integration with Trace Context).
2. **Prometheus APCu Metric Aggregator**.
3. **Kubernetes Health Probe Handlers** dengan deep checks (DB, Redis, & Memory limits).

##### File: `src/Infrastructure/Observability/TelemetryContextProcessor.php`
```php
<?php
declare(strict_types=1);

namespace Enterprise\Observability;

use Monolog\LogRecord;
use Monolog\Processor\ProcessorInterface;
use OpenTelemetry\API\Trace\Span;

/**
 * Processor Monolog untuk menginjeksi trace_id dan span_id aktif ke seluruh record log.
 */
final class TelemetryContextProcessor implements ProcessorInterface
{
    private string $serviceName;
    private string $environment;

    public function __construct(string $serviceName, string $environment)
    {
        $this->serviceName = $serviceName;
        $this->environment = $environment;
    }

    public function __invoke(LogRecord $record): LogRecord
    {
        $spanContext = Span::getCurrent()->getContext();

        $telemetryData = [
            'service' => [
                'name' => $this->serviceName,
                'environment' => $this->environment,
            ],
            'trace' => [
                'id' => $spanContext->isValid() ? $spanContext->getTraceId() : null,
            ],
            'span' => [
                'id' => $spanContext->isValid() ? $spanContext->getSpanId() : null,
                'sampled' => $spanContext->isSampled(),
            ],
        ];

        return $record->with(extra: array_merge($record->extra, $telemetryData));
    }
}
```

##### File: `src/Infrastructure/Observability/PrometheusMetricCollector.php`
```php
<?php
declare(strict_types=1);

namespace Enterprise\Observability;

use RuntimeException;

/**
 * High-performance, zero-allocation Prometheus metric collector menggunakan APCu Shared Memory.
 * Thread-safe untuk multi-worker PHP-FPM / FrankenPHP engine.
 */
final class PrometheusMetricCollector
{
    private const KEY_PREFIX = 'prom_metric:';

    public function __construct()
    {
        if (!\extension_loaded('apcu') || !\apc_fetch('apcu_enabled', $success) && !\ini_get('apc.enabled')) {
            // Fail-open pada non-production, fail-hard pada runtime production
            if (\getenv('APP_ENV') === 'production') {
                throw new RuntimeException('FATAL: ext-apcu is required for Prometheus in-memory aggregation.');
            }
        }
    }

    /**
     * Menambahkan counter secara atomik di memory.
     */
    public function incrementCounter(string $metricName, array $labels = [], int $step = 1): void
    {
        $key = $this->buildKey('counter', $metricName, $labels);
        
        $result = \apcu_inc($key, $step, $success);
        if ($result === false) {
            // Inisialisasi jika key belum ada
            \apcu_add($key, $step);
            $this->registerMetricKey('counter', $metricName, $key);
        }
    }

    /**
     * Merekam durasi operasi dalam bentuk Histogram Buckets.
     */
    public function recordHistogram(string $metricName, float $durationSeconds, array $labels = [], array $buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]): void
    {
        // 1. Increment total count dan total sum
        $countKey = $this->buildKey('histogram_count', $metricName, $labels);
        $sumKey = $this->buildKey('histogram_sum', $metricName, $labels);
        
        if (\apcu_inc($countKey, 1, $success) === false) {
            \apcu_add($countKey, 1);
            $this->registerMetricKey('histogram_count', $metricName, $countKey);
        }

        // Float sum menggunakan atomic CAS loop
        $this->addFloatValue($sumKey, $durationSeconds);
        $this->registerMetricKey('histogram_sum', $metricName, $sumKey);

        // 2. Increment cumulative bucket counters
        foreach ($buckets as $bucket) {
            if ($durationSeconds <= $bucket) {
                $bucketLabels = array_merge($labels, ['le' => (string)$bucket]);
                $bucketKey = $this->buildKey('histogram_bucket', $metricName, $bucketLabels);
                
                if (\apcu_inc($bucketKey, 1, $success) === false) {
                    \apcu_add($bucketKey, 1);
                    $this->registerMetricKey('histogram_bucket', $metricName, $bucketKey);
                }
            }
        }

        // Bucket Inf+
        $infLabels = array_merge($labels, ['le' => '+Inf']);
        $infKey = $this->buildKey('histogram_bucket', $metricName, $infLabels);
        if (\apcu_inc($infKey, 1, $success) === false) {
            \apcu_add($infKey, 1);
            $this->registerMetricKey('histogram_bucket', $metricName, $infKey);
        }
    }

    /**
     * Render format standar Prometheus exposition text format (0.0.4)
     */
    public function exportMetrics(): string
    {
        $registryKey = self::KEY_PREFIX . 'metric_registry';
        $registered = \apcu_fetch($registryKey) ?: [];
        
        $output = "";
        foreach ($registered as $metricKey => $metadata) {
            $value = \apcu_fetch($metricKey);
            if ($value !== false) {
                $output .= sprintf(
                    "%s{%s} %s\n",
                    $metadata['name'],
                    $this->formatLabels($metadata['labels']),
                    is_float($value) ? sprintf("%.6f", $value) : (string)$value
                );
            }
        }
        return $output;
    }

    private function buildKey(string $type, string $metricName, array $labels): string
    {
        \ksort($labels);
        return self::KEY_PREFIX . $type . ':' . $metricName . ':' . \md5(\json_encode($labels));
    }

    private function registerMetricKey(string $type, string $metricName, string $storageKey): void
    {
        $registryKey = self::KEY_PREFIX . 'metric_registry';
        
        // Optimistic CAS concurrency lock
        do {
            $oldRegistry = \apcu_fetch($registryKey) ?: [];
            if (isset($oldRegistry[$storageKey])) {
                return;
            }
            $newRegistry = $oldRegistry;
            $newRegistry[$storageKey] = [
                'name' => $metricName . ($type === 'histogram_bucket' ? '_bucket' : ($type === 'histogram_count' ? '_count' : ($type === 'histogram_sum' ? '_sum' : ''))),
                'labels' => $this->extractLabelsFromKey($storageKey),
            ];
        } while (!\apcu_cas($registryKey, $oldRegistry, $newRegistry));
    }

    private function addFloatValue(string $key, float $val): void
    {
        do {
            $old = \apcu_fetch($key);
            if ($old === false) {
                if (\apcu_add($key, $val)) {
                    break;
                }
                $old = \apcu_fetch($key);
            }
            $new = ((float) $old) + $val;
        } while (!\apcu_cas($key, $old, $new));
    }

    private function extractLabelsFromKey(string $key): array
    {
        // Simple extraction fallback logic (in real-world, stored in metadata)
        return [];
    }

    private function formatLabels(array $labels): string
    {
        $parts = [];
        foreach ($labels as $k => $v) {
            $parts[] = sprintf('%s="%s"', $k, \addcslashes($v, "\"\n\\"));
        }
        return \implode(',', $parts);
    }
}
```

##### File: `src/Infrastructure/Http/ProbeController.php`
```php
<?php
declare(strict_types=1);

namespace Enterprise\Http;

use PDO;
use Redis;
use RedisException;
use Throwable;

final class ProbeController
{
    private PDO $pdo;
    private Redis $redis;

    public function __construct(PDO $pdo, Redis $redis)
    {
        $this->pdo = $pdo;
        $this->redis = $redis;
    }

    /**
     * Kubernetes Startup Probe:
     * Memastikan resource dasar, cache warming, dan skema runtime siap.
     */
    public function handleStartup(): void
    {
        // Fail jika komponen vital belum terkoneksi
        if (!$this->checkDatabase() || !$this->checkRedis()) {
            $this->sendResponse(503, ['status' => 'STARTUP_FAILED', 'reason' => 'Dependencies unavailable']);
            return;
        }

        $this->sendResponse(200, ['status' => 'STARTED']);
    }

    /**
     * Kubernetes Liveness Probe:
     * Memastikan worker tidak deadlock atau kehabisan alokasi memori internal.
     * HANYA periksa status proses saat ini, JANGAN query network dependency di sini.
     */
    public function handleLiveness(): void
    {
        $memoryUsage = \memory_get_usage(true);
        $memoryLimit = $this->getMemoryLimitInBytes();

        // Jika konsumsi memori melewati threshold kritis 90%, restart pod via liveness failure
        if ($memoryLimit > 0 && ($memoryUsage / $memoryLimit) > 0.90) {
            $this->sendResponse(500, [
                'status' => 'OOM_RISK',
                'memory_usage_mb' => $memoryUsage / 1024 / 1024,
                'memory_limit_mb' => $memoryLimit / 1024 / 1024
            ]);
            return;
        }

        $this->sendResponse(200, ['status' => 'ALIVE']);
    }

    /**
     * Kubernetes Readiness Probe:
     * Memastikan apakah Pod siap menerima traffic beban nyata dari Service/Load Balancer.
     */
    public function handleReadiness(): void
    {
        $checks = [
            'database' => $this->checkDatabase(),
            'redis' => $this->checkRedis(),
        ];

        $isHealthy = !in_array(false, $checks, true);

        $this->sendResponse($isHealthy ? 200 : 503, [
            'status' => $isHealthy ? 'READY' : 'DEGRADED',
            'components' => $checks
        ]);
    }

    private function checkDatabase(): bool
    {
        try {
            $stmt = $this->pdo->query('SELECT 1');
            return $stmt !== false && $stmt->fetchColumn() === 1;
        } catch (Throwable) {
            return false;
        }
    }

    private function checkRedis(): bool
    {
        try {
            return $this->redis->ping() === true;
        } catch (RedisException) {
            return false;
        }
    }

    private function getMemoryLimitInBytes(): int
    {
        $ini = \ini_get('memory_limit');
        if ($ini === '-1') {
            return -1;
        }
        $val = (int) $ini;
        $unit = \strtolower(\substr($ini, -1));
        return match ($unit) {
            'g' => $val * 1024 * 1024 * 1024,
            'm' => $val * 1024 * 1024,
            'k' => $val * 1024,
            default => (int) $ini,
        };
    }

    private function sendResponse(int $code, array $payload): void
    {
        \http_response_code($code);
        \header('Content-Type: application/json; charset=utf-8');
        \header('Cache-Control: no-cache, no-store, must-revalidate');
        echo \json_encode($payload, JSON_THROW_ON_ERROR);
    }
}
```

##### File: `public/index.php` (Graceful Signal Handler Implementation)
```php
<?php
declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';

// Registrasi Async POSIX Signal Handling untuk CLI / Long-Running Workers
if (\php_sapi_name() === 'cli' && \extension_loaded('pcntl')) {
    \pcntl_async_signals(true);

    $shouldTerminate = false;
    $handler = function (int $signalNumber) use (&$shouldTerminate): void {
        \fwrite(\STDOUT, sprintf("Menerima sinyal terminasi: %d. Memulai proses graceful drain...\n", $signalNumber));
        $shouldTerminate = true;
    };

    \pcntl_signal(\SIGTERM, $handler);
    \pcntl_signal(\SIGQUIT, $handler);
    \pcntl_signal(\SIGINT, $handler);
}

// Simulasi Routing HTTP
$uri = $_SERVER['REQUEST_URI'] ?? '/';

if ($uri === '/health/startup') {
    (new \Enterprise\Http\ProbeController($pdo, $redis))->handleStartup();
    exit;
}

if ($uri === '/health/liveness') {
    (new \Enterprise\Http\ProbeController($pdo, $redis))->handleLiveness();
    exit;
}

if ($uri === '/health/readiness') {
    (new \Enterprise\Http\ProbeController($pdo, $redis))->handleReadiness();
    exit;
}

if ($uri === '/metrics') {
    \header('Content-Type: text/plain; version=0.0.4; charset=utf-8');
    echo (new \Enterprise\Observability\PrometheusMetricCollector())->exportMetrics();
    exit;
}
```

---

### 8. Real World Case Study: Payment Gateway Monolith to Microservices

#### 8.1. Konteks Skala & Arsitektur
- **Beban Sistem**: 35.000 transaksi pembayaran per detik (Peak).
- **Infrastruktur**: 80 Pod Kubernetes (`c6i.2xlarge` nodes). Runtime transisi dari PHP-FPM klasik ke FrankenPHP (Caddy Go + Zend Engine integration).
- **Problem**: 
  1. *Spike Timeout*: 0.8% transaksi pembayaran mengalami `504 Gateway Timeout` di payment partner downstream, tanpa adanya jejak log yang menghubungkan panggilan HTTP awal dari mobile user dengan downstream provider.
  2. *Resource Contention*: Logging teks berbasis disk I/O menyebabkan filesystem pod crash (`iowait` 80%).
  3. *Unclean Deploys*: Saat rolling release di Kubernetes, 200–500 transaksi per release mengalami koneksi terputus tiba-tiba (*HTTP 502 Bad Gateway*).

#### 8.2. Langkah Remediasi & Rekayasa Arsitektur
1. **Tracing Implementation**:
   - Diimplementasikan `ext-opentelemetry` C extension untuk memotong overhead reflection userland.
   - Dikonfigurasi *Tail-Based Sampling* pada OpenTelemetry Collector Sidecar: 100% trace error (HTTP 5xx / Exceptions) disimpan, sementara trace dengan latency di bawah 200ms di-sample hanya 1%.
2. **Unified Logging Pipeline**:
   - Monolog dialihkan sepenuhnya menggunakan `StreamHandler('php://stdout')` dengan `JsonFormatter`.
   - Logging asynchronous dikoleksi oleh node DaemonSet (Vector) yang mem-buffer log ke Kafka sebelum disimpan ke ClickHouse. Disk Pod dibuat *ephemeral* dan *read-only*.
3. **Graceful Termination Architecture**:
   - Ditambahkan `preStop` hook pada pod specification Kubernetes untuk menunda pengiriman `SIGTERM` selama 5 detik, memberi jeda pada Kube-Proxy/Ingress Controller untuk menghapus Endpoints IP Pod dari load balancer sebelum proses PHP mati.
   - Konfigurasi parameter `process_control_timeout = 15s` pada `php-fpm.conf` untuk memastikan worker menyelesaikan eksekusi transaksi yang sedang berjalan sebelum dimatikan.

#### 8.3. Hasil Validasi (Impact Metrics)
- **MTTD / MTTR**: Turun dari rata-rata 47 menit menjadi 2.5 menit via visualisasi Service Dependency Graph Jaeger.
- **Rolling Deployment Errors**: 0 dropped transactions (100% zero-downtime deployment tercapai).
- **Latency Profiling**: Overhead tracing tercatat hanya sebesar 0.45ms per transaksi.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Biaya & Kompromi (Trade-offs) |
| :--- | :--- | :--- |
| **OTel C Extension vs Pure PHP Userland SDK** | **Pros**: Kecepatan native, nol refleksi kode, memory footprint nyaris 0.<br>**Cons**: Dependensi compile C library pada Docker build, kompleksitas debugging memory leak engine level. | Ekstensi C sulit di-debug menggunakan stacktrace PHP standar; jika segmentation fault terjadi, seluruh worker FPM crash. |
| **Prometheus APCu Buffer vs Pushgateway HTTP** | **Pros**: Write latency sub-microsecond, thread-safe, scraping dilakukan pull secara fleksibel.<br>**Cons**: Metrik lokal pada node Pod; jika Pod di-evict K8s, metrik transaksi terakhir yang belum di-scrape hilang. | Prometheus Pushgateway mengubah model pull menjadi push, menyebabkan bottleneck throughput pada skala 10k+ req/sec. |
| **Head-based Sampling vs Tail-based Sampling** | **Pros (Head)**: Sampling diputuskan di awal, menghemat bandwidth jaringan dan CPU Pod.<br>**Cons (Head)**: Seringkali transaksi yang lambat/error justru tidak terekam karena lolos dari sampling acak awal. | Tail-based sampling mewajibkan Sidecar OTel menahan span buffer di memori sebelum mengambil keputusan, membutuhkan RAM cluster lebih besar (+200MB/Pod). |
| **Sampling Profiler (Excimer) vs APM Tracing Lengkap** | **Pros**: Mampu melacak sampai baris kode spesifik, loop berlebih, dan memory retention internal.<br>**Cons**: Menghasilkan volume data diagnostik raksasa jika diaktifkan terus-menerus. | Harus dibatasi pada sampling rate rendah (10–50Hz); overhead disk ingestion untuk trace profile flamegraph. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistakes
1. **Liveness Probes Menguji Network Dependencies**:
   *Anti-pattern*: Menyertakan `$pdo->query()` atau `$redis->ping()` di dalam handler `/health/liveness`.
   *Dampak Katastropik*: Saat database mengalami *transient spike* atau network blip 2 detik, Kubelet menganggap semua Pod PHP mati secara serentak, membunuh seluruh pod (*cascading pod restart death spiral*), memperparah beban database.
2. **Synchronous OTLP Exporting over HTTP**:
   *Anti-pattern*: Mengekspor telemetry trace langsung ke backend remote via HTTP client di dalam siklus eksekusi PHP-FPM.
   *Dampak*: Latensi request melonjak dari 20ms menjadi 300ms karena worker tertahan (blocked) oleh network latency server APM eksternal. Gunakan selalu **Local Sidecar Agent via UDP/gRPC/UDS**.
3. **Trace Context Stripping oleh Reverse Proxy**:
   *Anti-pattern*: Nginx atau API Gateway internal tidak mengonfigurasi `proxy_pass_request_headers on;` atau memfilter header yang mengandung karakter underscore/strip, memutus rantai W3C trace.
4. **Log Spooling ke Disk Kontainer**:
   *Anti-pattern*: Menulis log Monolog ke `/var/www/html/storage/logs/laravel.log` di dalam kontainer Docker Kubernetes.
   *Dampak*: Pod mengalami crash akibat kehabisan disk space (*Evicted due to DiskPressure*), performa I/O terdegradasi parah.

#### 10.2. Troubleshooting Guide

```
+-----------------------------------------------------------------------------------+
|               DIAGNOSTIC WORKFLOW: TRACE PROPAGATION FAILURE                      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
                         Apakah Span masuk ke OTel Backend?
                                   /           \
                           (TIDAK)/             \(YA)
                                 /               \
       Cek koneksi OTLP Sidecar                   Apakah Trace Terputus (Root baru)?
       $ nc -zvw3 127.0.0.1 4317                            |
               |                                            v
     [Koneksi Terbuka?]                  Cek Header 'traceparent' di PHP Worker:
      /             \                    error_log($_SERVER['HTTP_TRACEPARENT']);
   (YA)             (TIDAK)                                 |
    |                  |                      +-------------+-------------+
    v                  v                      |                           |
Periksa log         OTel Sidecar Pod      [Header Ada]             [Header Kosong]
Sidecar:            Down. Check K8s:          |                           |
kubectl logs        kubectl describe pod  Periksa W3C Parser        Ingress/Gateway
-c otel-collector                         format regex validator   membuang header W3C
```

- **Isu: Metrik Prometheus Nilainya Selalu 0 atau Hilang**:
  - *Diagnosa*: Pastikan APCu diaktifkan untuk CLI jika menggunakan RoadRunner/FrankenPHP (`apc.enable_cli=1` di `php.ini`).
  - *Verifikasi*: Jalankan script via command line:
    ```bash
    php -r "apcu_inc('test_key', 1); echo apcu_fetch('test_key');"
    ```
- **Isu: SIGTERM Menyebabkan HTTP 502 Saat Rolling Update**:
  - *Akar Masalah*: Kubernetes menghapus endpoint pod secara asinkron dari kube-proxy. Jika FPM langsung berhenti saat menerima sinyal `SIGTERM`, paket data TCP in-flight dari Load Balancer akan ditolak dengan `RST`.
  - *Solusi*: Pasang lifecycle hook `preStop: exec: command: ["/bin/sleep", "5"]` di K8s deployment spec.

---

### 11. Best Practices (Production Checklist)

#### Pre-Flight Production Readiness Checklist
- [ ] **Structured Logging**: Seluruh log emitted ke `php://stdout` atau `php://stderr` dalam format JSON murni standar RFC 8259 tanpa escape karakter berlebih.
- [ ] **Correlation Injection**: Log Processor otomatis menyuntikkan `trace_id` dan `span_id` ke dalam JSON root level.
- [ ] **OTel Sidecar Transport**: PHP runtime berkomunikasi ke OTel Collector lokal melalui IPC Unix Domain Socket atau `127.0.0.1:4317` (gRPC).
- [ ] **Decoupled Probes Architecture**:
  - `Startup Probe`: Menjamin dependensi kritis (DB, Redis, Schemas) tersedia sebelum aplikasi dinyatakan up.
  - `Readiness Probe`: Menjamin aplikasi siap melayani traffic (dicek secara periodik).
  - `Liveness Probe`: **HANYA** memeriksa state memori/thread lokal, terisolasi dari external calls.
- [ ] **Kubernetes Signal & Drain**:
  - `preStop` hook sleep minimal 5-10 detik.
  - `terminationGracePeriodSeconds` disetel di atas `process_control_timeout` PHP-FPM (misal: 30 detik).
- [ ] **Prometheus Shared State**: Tidak menggunakan file disk locks untuk tracking metrics; gunakan APCu memory atau daemon aggregator lokal.
- [ ] **Sampling Controls**: Production tracing sampling dibatasi pada 1%-5% untuk status HTTP 2xx, dan 100% untuk status HTTP 5xx.

---

### 12. Hands-on Practice: Implementasi End-to-End Local Observability Stack

Praktikum ini menyusun seluruh arsitektur di atas ke dalam direktori: `hands-on/m02/`.

#### Langkah 1: Persiapan Struktur Direktori
```bash
mkdir -p hands-on/m02/{src,config,public}
cd hands-on/m02
```

#### Langkah 2: Buat File `composer.json`
```json
{
  "name": "enterprise/observability-lab",
  "type": "project",
  "require": {
    "php": ">=8.2",
    "monolog/monolog": "^3.5",
    "open-telemetry/sdk": "^1.0",
    "open-telemetry/exporter-otlp": "^1.0"
  },
  "autoload": {
    "psr-4": {
      "Enterprise\\": "src/"
    }
  }
}
```
*Jalankan: `composer install`*

#### Langkah 3: Konfigurasi OpenTelemetry Collector (`config/otel-collector-config.yaml`)
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 256

exporters:
  logging:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
```

#### Langkah 4: Buat `docker-compose.yaml`
```yaml
version: '3.8'

services:
  otel-collector:
    image: otel/opentelemetry-collector:0.95.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./config/otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317" # gRPC
      - "4318:4318" # HTTP

  app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - APP_ENV=production
      - OTEL_SERVICE_NAME=order-service
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - OTEL_EXPORTER_OTLP_PROTOCOL=grpc
    ports:
      - "8080:8080"
    depends_on:
      - otel-collector
```

#### Langkah 5: Buat Dockerfile Multi-Stage (`Dockerfile`)
```dockerfile
FROM php:8.3-cli-alpine

RUN apk add --no-cache autoconf build-base linux-headers protobuf-dev \
    && pecl install apcu \
    && docker-php-ext-enable apcu

WORKDIR /app
COPY . /app

# Enable APCu for CLI mode testing
RUN echo "apc.enable_cli=1" >> /usr/local/etc/php/conf.d/docker-php-ext-apcu.ini

EXPOSE 8080
CMD ["php", "-S", "0.0.0.0:8080", "-t", "public"]
```

#### Langkah 6: Implementasi Application Entrypoint (`public/index.php`)
```php
<?php
declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';

use Monolog\Logger;
use Monolog\Handler\StreamHandler;
use Monolog\Formatter\JsonFormatter;
use Enterprise\Observability\TelemetryContextProcessor;
use Enterprise\Observability\PrometheusMetricCollector;

// 1. Setup Structured Logger
$logger = new Logger('orders');
$streamHandler = new StreamHandler('php://stdout', Logger::DEBUG);
$streamHandler->setFormatter(new JsonFormatter());
$logger->pushHandler($streamHandler);
$logger->pushProcessor(new TelemetryContextProcessor('order-service', 'production'));

// 2. Metrics Collector
$metrics = new PrometheusMetricCollector();

$route = $_SERVER['REQUEST_URI'] ?? '/';

if ($route === '/metrics') {
    header('Content-Type: text/plain; version=0.0.4');
    echo $metrics->exportMetrics();
    exit;
}

// 3. Simulated Transaction Execution
$startTime = microtime(true);
$orderId = bin2hex(random_bytes(8));

$logger->info("Memproses order baru", ['order_id' => $orderId]);

// Catat metrik
$metrics->incrementCounter('orders_total', ['status' => 'success']);
$duration = microtime(true) - $startTime;
$metrics->recordHistogram('order_processing_seconds', $duration, ['endpoint' => '/checkout']);

header('Content-Type: application/json');
echo json_encode(['status' => 'ORDER_PROCESSED', 'order_id' => $orderId, 'latency_sec' => $duration]);
```

#### Langkah 7: Eksekusi & Validasi Telemetri
1. Bangun dan jalankan stack:
   ```bash
   docker compose up --build -d
   ```
2. Picu HTTP request ke aplikasi:
   ```bash
   curl -i http://localhost:8080/checkout
   ```
3. Verifikasi Log Terstruktur (JSON Output):
   ```bash
   docker compose logs app
   ```
   *Ekspektasi: Muncul log JSON dengan payload terstruktur.*
4. Verifikasi Prometheus Exposition Text Format:
   ```bash
   curl -i http://localhost:8080/metrics
   ```
   *Ekspektasi: Nilai counter `orders_total` dan histogram `order_processing_seconds` terpapar.*

---

### 13. Exercise

#### Level 1 - Easy
Ubah `TelemetryContextProcessor` agar dapat mengekstrak `HTTP_USER_AGENT` dan Client IP dari HTTP request header secara aman (menghindari IP spoofing dengan validasi terhadap trusted proxies) dan menambahkannya ke attribute `http.client.ip`.

#### Level 2 - Medium
Bangun sistem integrasi middleware Guzzle HTTP Client yang secara otomatis:
1. Membaca Active Span saat ini dari OpenTelemetry Context.
2. Menyuntikkan header W3C `traceparent` ke *outgoing HTTP request* pihak ketiga.
3. Mencatat durasi HTTP outbound call tersebut ke Prometheus metric terpisah: `http_client_request_duration_seconds`.

#### Level 3 - Hard
Rancang dan implementasikan APCu-backed Rate Limiter + Prometheus Metric Exporter tanpa lock race condition (*CAS-based*). Implementasi harus:
1. Menggunakan algoritma *Token Bucket* atomik.
2. Mengekspos metrik `rate_limit_exceeded_total` dengan label `client_id` dan `route`.
3. Memastikan bahwa dalam skenario 1.000 concurrent requests, tidak ada alokasi token yang bocor (*no double allocation*).

---

### 14. Challenge: Arsitektur Out-of-Process Profiling pada Scale Extreme

**Konteks**:
Sebuah platform live-streaming video memiliki API Backend PHP yang menerima **120.000 requests/sec** pada event flash sale. Anda mendapati bahwa pada kondisi traffic puncak, terjadi *CPU Thrashing* periodik setiap 15 menit yang menyebabkan Pod PHP-FPM mengalami spike latensi p99 dari 45ms melonjak ke 3.500ms selama rentang 30 detik.

**Ketentuan Desain**:
1. Anda dilarang keras mengaktifkan Xdebug atau synchronous APM tracing pada production environment.
2. Anda harus merancang solusi profiling continuous sampling berbasis **Excimer / Pyroscope** yang:
   - Berjalan dengan overhead CPU global Pod di bawah 1%.
   - Mengambil sampel stack trace hanya pada transaksi yang berjalan di atas threshold 200ms (*slow request detection sampling*).
   - Menghubungkan stack trace profiler tersebut secara deterministik ke `TraceID` OpenTelemetry dari request yang lambat tersebut.
3. Rancang deployment spec Kubernetes (Sidecar container vs DaemonSet Collector) untuk mengekspor data flamegraph tersebut ke storage backend sentral tanpa membebani disk ephemeral container atau jaringan cluster.
4. Buat dokumen arsitektur teknis yang menjelaskan mekanisme penanganan crash/segmentation fault jika profiler sampling engine mengalami deadlock saat mengakses Zend Memory Heap.

---

### 15. Quiz Evaluasi Pemahaman

#### Sesi 1: Basic (Pilihan Ganda)

1. Mengapa PHP-FPM tidak dapat menyimpan metrik Prometheus secara native langsung pada global variable PHP?
   - A. Karena PHP mematikan thread safety secara default.
   - B. Karena PHP-FPM menggunakan model Shared-Nothing; memori di-destroy pada fase `RSHUTDOWN`.
   - C. Karena Prometheus menolak scraping data dari server web FastCGI.
   - D. Karena tipe data Integer di PHP tidak thread-safe.

2. Komponen W3C TraceContext yang membawa informasi Trace Identifier unik sepanjang 16 byte adalah:
   - A. `tracestate`
   - B. `traceparent`
   - C. `x-request-id`
   - D. `span-context`

3. Karakteristik utama dari Continuous Sampling Profiler (seperti Excimer) dibandingkan Deterministic Profiler (seperti Xdebug) adalah:
   - A. Memodifikasi seluruh opcode call graph aplikasi.
   - B. Mencegat callstack secara periodik via POSIX interrupts dengan overhead sangat rendah.
   - C. Berjalan hanya pada local development environment.
   - D. Membutuhkan compiler C khusus saat menjalankan kode PHP.

4. Tujuan utama penulisan log aplikasi diarahkan ke `/dev/stdout` di kontainer Docker adalah:
   - A. Mencegah log dibaca oleh container lain.
   - B. Menyerahkan manajemen log aggregation dan storage ke container runtime engine / log shippers (Vector/FluentBit).
   - C. Meningkatkan latency response HTTP.
   - D. Memaksa engine PHP melakukan sinkronisasi file descriptor secara eksklusif.

5. Dalam konfigurasi Kubernetes Pod, apa akibat fatal jika Database ping ditempatkan pada **Liveness Probe**?
   - A. Database akan kehabisan koneksi secara instan.
   - B. Pod akan di-restart massal oleh Kubelet saat Database down sementara, menciptakan *cascading recovery failure*.
   - C. Pod tidak dapat di-scale oleh HPA.
   - D. Log container otomatis terhapus.

---

#### Sesi 2: Intermediate (Pilihan Ganda)

6. Pada integrasi OpenTelemetry, kapan waktu yang tepat untuk melakukan *Context Detach* setelah mengaktifkan Span?
   - A. Di awal script sebelum fungsi `run()` dipanggil.
   - B. Di dalam block `finally` setelah span ditutup (`$span->end()`).
   - C. Secara otomatis dieksekusi oleh Garbage Collector PHP.
   - D. Di dalam destruct controller.

7. Untuk mengimplementasikan Prometheus Metric Aggregation pada arsitektur PHP-FPM multi-worker tanpa database eksternal, teknologi in-memory mana yang paling efisien pada level OS lokal?
   - A. Memcached via TCP.
   - B. APCu Shared Memory (`shm` / `mmap`) pada kernel memory host/container.
   - C. Simpan ke SQLite di `/tmp`.
   - D. Threaded Worker Pools.

8. Apa fungsi dari instruksi `preStop: exec: command: ["/bin/sleep", "5"]` pada Pod Specification Kubernetes PHP?
   - A. Memperlambat startup Pod agar database siap.
   - B. Memberi waktu bagi ingress/service mesh untuk menghapus IP Pod dari load balancer sebelum proses dihentikan oleh `SIGTERM`.
   - C. Menghemat alokasi memori buffer FPM.
   - D. Menjalankan proses backup database sebelum rolling update.

9. Teknik tracing *Tail-Based Sampling* memiliki keunggulan dibandingkan *Head-Based Sampling* karena:
   - A. Mengurangi konsumsi CPU pada OpenTelemetry Collector.
   - B. Keputusan sampling dibuat setelah request selesai, memungkinkan penyimpanan 100% trace error atau trace berlatensi tinggi.
   - C. Dapat dijalankan tanpa menggunakan Collector Sidecar.
   - D. Menghilangkan kebutuhan propagasi W3C Header.

10. Fungsi Zend Engine lifecycle hook yang dijalankan tepat saat eksekusi satu request selesai adalah:
    - A. `MINIT`
    - B. `MSHUTDOWN`
    - C. `RSHUTDOWN`
    - D. `GINIT`

---

#### Sesi 3: Skenario Kasus Produksi

11. **Skenario 1**:
    Sebuah aplikasi PHP 8.3 e-commerce mengalami masalah di mana Ingress Controller mencatat status code `502 Bad Gateway` selama 3-5 detik saat proses deployment baru berlangsung di Kubernetes. Namun, pada log aplikasi PHP (`stdout`) tidak ada error log yang tercatat sama sekali.
    *Tugas*: Analisis rantai penyebab masalah ini dari sudut pandang *TCP connection lifecycle*, *Kubernetes Endpoints controller*, dan sinyal proses PHP (`SIGTERM`), serta berikan perbaikan konfigurasinya.

12. **Skenario 2**:
    Tim SRE menemukan bahwa metrik histogram Prometheus untuk endpoint `/api/v1/checkout` menunjukkan waktu pemrosesan p99 sebesar 2.100ms. Namun, saat tim developer memeriksa trace di Jaeger, span terpanjang yang tercatat di aplikasi PHP hanya memakan waktu 120ms.
    *Tugas*: Identifikasi di layer infrastruktur mana *blindspot* latensi ini berada, dan bagaimana merekayasa instrumentasi observabilitas untuk menangkap gap waktu tersebut.

13. **Skenario 3**:
    Penggunaan APCu untuk Prometheus metrics scraper pada 64 worker PHP-FPM menghasilkan memory exhaustion (*APCu cache out of memory*) setelah berjalan 48 jam.
    *Tugas*: Jelaskan fenomena apa yang terjadi terkait *metric cardinality* dan bagaimana merefaktor fungsi `buildKey` untuk memitigasi hal tersebut.

---

### Kunci Jawaban Quiz

#### Sesi 1: Basic
1. **B**: PHP-FPM Shared-Nothing membersihkan heap memori Zend Engine pada fase `RSHUTDOWN`.
2. **B**: `traceparent` membawa 16-byte Trace ID, 8-byte Span ID, dan sampling flags.
3. **B**: Continuous sampling profiler mengandalkan POSIX timer/interrupts berkala untuk membaca callstack tanpa mengintervensi setiap baris eksekusi.
4. **B**: Sesuai dengan Twelve-Factor App manifesto (XI. Logs: Treat logs as event streams ke stdout).
5. **B**: Liveness probe yang gagal menyebabkan pod di-kill; jika DB down, seluruh cluster pod terbunuh.

#### Sesi 2: Intermediate
6. **B**: Harus selalu di dalam `finally` block agar scope context terbebas meskipun terjadi unhandled exception.
7. **B**: APCu menggunakan kernel shared memory (`shm`), melewati TCP networking overhead.
8. **B**: Mencegah race condition antara pembaruan `iptables`/IPVS Kubernetes dengan terminasi instan socket FastCGI.
9. **B**: Tail-based sampling menganalisis trace secara menyeluruh sebelum menentukan apakah trace tersebut bernilai tinggi untuk disimpan.
10. **C**: `RSHUTDOWN` (Request Shutdown) adalah event pembersihan memori per request.

#### Sesi 3: Skenario Kasus Produksi (Pedoman Penilaian Solusi)
11. **Analisis Skenario 1**:
    - *Akar Masalah*: Pod menerima `SIGTERM` secara instan dari Kubelet saat deployment dimulai. FPM langsung menutup listening socket atau berhenti menerima request baru. Namun, Ingress/Kube-Proxy belum selesai mempropagasi pembaruan iptables untuk menghapus IP Pod lama dari routing table. Akibatnya, request baru masih dikirim ke Pod yang sedang sekarat, menghasilkan `TCP RST` (502 Bad Gateway).
    - *Solusi*: 
      1. Tambahkan `lifecycle.preStop.exec.command: ["sleep", "5"]` pada template container di manifest K8s.
      2. Set `process_control_timeout = 10s` di `php-fpm.conf`.
      3. Atur deployment strategy `maxSurge: 25%`, `maxUnavailable: 0`.

12. **Analisis Skenario 2**:
    - *Akar Masalah*: Blindspot terjadi di luar scope eksekusi Zend Engine. Kemungkinan besar latensi terjadi pada antrean antarmuka FastCGI (*Queueing Delay* pada PHP-FPM listen backlog) atau reverse-proxy worker buffering. Request tertahan di queue Nginx/FrankenPHP sebelum dieksekusi oleh PHP worker (`RINIT`), sehingga OTel span PHP baru mulai mencatat waktu setelah antrean selesai.
    - *Solusi*:
      1. Aktifkan instrumentasi tracing pada Ingress/Nginx layer sehingga *Parent Span* dimulai dari Ingress Controller.
      2. Monitor metrik Prometheus `php_fpm_listen_queue` dan `php_fpm_listen_queue_length`. Gap antara total waktu Ingress dan Span PHP menunjukkan *Queue Wait Time*.

13. **Analisis Skenario 3**:
    - *Akar Masalah*: **High Cardinality Explosion**. Developer kemungkinan menyertakan unbounded data (seperti `user_id`, `order_id`, atau parameter timestamp) ke dalam *labels* metric. Setiap kombinasi label yang unik menghasilkan alokasi key APCu baru secara permanen di memori (`prom_metric:...`), menghabiskan seluruh segment shm APCu.
    - *Solusi*:
      1. Audit seluruh penggunaan label metrik: HANYA gunakan bounded enum (misal: `http_status_code` [200, 400, 500], `method` [GET, POST], `route_name` [/checkout]).
      2. Jangan pernah memasukkan ID entitas dinamis ke dalam Prometheus Labels. Pindahkan data granular tersebut ke attribute OpenTelemetry Tracing/Logs.

---

### 16. Summary

Implementasi observabilitas dan SRE pada ekosistem enterprise PHP 8.x menuntut pemahaman arsitektur runtime tingkat lanjut. Sifat *shared-nothing* dari PHP-FPM bukanlah halangan, melainkan karakteristik desain yang menuntut pemisahan state metrik yang disiplin ke shared memory layer (APCu) atau sidecar proxy. 

Dengan menyelaraskan standar W3C TraceContext di layer OpenTelemetry, mengekspor logs terstruktur ke stdout secara non-blocking, serta mengorkestrasikan lifecycle hooks Kubernetes secara presisi, aplikasi PHP enterprise mampu beroperasi dengan kestabilan *four-nines* (99.99%), zero-downtime rolling releases, dan kapabilitas audit performa transaksi mikro yang transparan pada skala ratusan ribu transaksi per detik.