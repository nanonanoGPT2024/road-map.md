# Modul 08: Observability, Diagnostics, & Runtime Profiling

---

## 01: Identitas Modul

* **Track:** Backend and Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Topik:** Observability, Diagnostics, & Runtime Profiling
* **Target Audience:** Principal Engineer, Senior Backend Engineers, Site Reliability Engineers (SRE), Systems Performance Architects
* **Prasyarat:**
  * Penguasaan Node.js Core Architecture (Libuv, V8 Event Loop, Microtask Queue).
  * Pemahaman mendalam tentang asynchronous execution contexts dan native memory management.
  * Pengalaman operasional dengan containerized orchestration (Docker, Kubernetes) dan distributed systems.

---

## 02: Learning Objectives

1. **Menguasai Context Propagation & Tracing:** Mengimplementasikan propagasi konteks asynchronous multi-tier tanpa *context leakage* menggunakan Node.js `AsyncLocalStorage` dan integrasi OpenTelemetry API/SDK.
2. **Diagnostik Runtime Lanjut:** Menangkap, menganalisis, dan membedah V8 CPU Profiles, Heap Snapshots, serta Core Dumps dari proses Node.js yang aktif di lingkungan produksi tanpa mendegradasi *event-loop tick time*.
3. **Instrumen Metrik Kustom & RED/USE Methods:** Merancang arsitektur metrik non-blocking berbasis Prometheus/OpenTelemetry yang memantau performa thread pool Libuv, Event Loop Delay (ELD), dan V8 Garbage Collection (GC) phases.
4. **Structured & Correlated Logging:** Mengonfigurasi engine *high-throughput structured logging* berbasis NDJSON menggunakan Pino dengan integrasi trace-context otomatis (W3C Trace Context TraceID/SpanID).
5. **Continuous Profiling & Flamegraph Analysis:** Menginterpretasikan V8 runtime sample ticks, mendeteksi optimasi V8 (deoptimizations/IC miss), dan mengidentifikasi *bottleneck* micro-task loop melalui Flamegraphs.

---

## 03: Concept Map Diagram (ASCII)

```text
+--------------------------------------------------------------------------------------------------+
|                                    NODE.JS RUNTIME PROCESS                                       |
|                                                                                                  |
|  +--------------------------------+                  +----------------------------------------+  |
|  |           V8 Engine            |                  |              Libuv Engine              |  |
|  |  +--------------------------+  |                  |  +----------------------------------+  |  |
|  |  |   Heap (Young/Old Gen)   |  |                  |  |  Event Loop (Micro/Macro Phases) |  |  |
|  |  +------------+-------------+  |                  |  +-----------------+----------------+  |  |
|  +---------------|----------------+                  +--------------------|-------------------+  |
|                  |                                                        |                      |
|                  | (GC Events & Memory Allocation)                        | (Loop Delay Latency) |
|                  v                                                        v                      |
|  +--------------------------------------------------------------------------------------------+  |
|  |                           NODE.JS DIAGNOSTICS & TELEMETRY CORE                             |  |
|  |                                                                                            |  |
|  |   +---------------------+   +---------------------+   +--------------------------------+   |  |
|  |   |  AsyncLocalStorage  |   |  perf_hooks / V8    |   | Diagnostic Report / Inspector  |   |  |
|  |   |  (Context Tracking) |   |  (ELD, GC Metrics)  |   | (Heap Snapshot / CPU Profile)  |   |  |
|  |   +----------+----------+   +----------+----------+   +---------------+----------------+   |  |
+-----------------|-------------------------|------------------------------|-----------------------+
                  |                         |                              |
                  | Inject Trace Context    | Collect Metrics              | Trigger On Demand / OOM
                  v                         v                              v
+--------------------------------------------------------------------------------------------------+
|                                     OBSERVABILITY PIPELINE                                       |
|                                                                                                  |
|  +----------------------------+  +----------------------------+  +----------------------------+  |
|  |     Correlated Logging     |  |    Metrics & Telemetry     |  |    Distributed Tracing     |  |
|  |         (Pino.js)          |  |   (Prometheus / OTel SDK)  |  |    (OpenTelemetry / W3C)   |  |
|  +-------------+--------------+  +-------------+--------------+  +-------------+--------------+  |
+----------------|-------------------------------|-------------------------------|-----------------+
                 |                               |                               |
                 v                               v                               v
+--------------------------------------------------------------------------------------------------+
|                                 TELEMETRY COLLECTOR / BACKENDS                                   |
|               (Elasticsearch / Loki, Prometheus / VictoriaMetrics, Jaeger / Tempo)               |
+--------------------------------------------------------------------------------------------------+
```

---

## 04: Mengapa Relevan

Menjalankan Node.js pada skala *hyper-growth* menuntut observabilitas yang presisi. Sifat dasar Node.js yang berbasis *single-threaded event loop* dengan I/O non-blocking memunculkan kegagalan sistem yang spesifik:

* **Event Loop Starvation:** Satu fungsi komputasi sinkron yang memakan waktu 50ms dapat menahan ribuan request konkuren lain, menyebabkan *latency spikes* drastis yang tidak terbaca oleh CPU utilization metrics standar server.
* **V8 Garbage Collection Latency:** Fragmentasi memori pada Old Space menyebabkan fase *Mark-Sweep-Compact* berjalan lama (*Stop-The-World*), memicu *timeout* kaskade pada microservices.
* **Context Fragmentation:** Sifat asinkronus eksekusi Node.js membuat *error stack trace* bawaan kehilangan jejak pemanggil aslinya (*loss of caller context*), mempersulit diagnosa *root cause* tanpa propagasi context berbasis `AsyncLocalStorage`.

Kegagalan menginstrumentasikan sistem dengan benar menyebabkan tim SRE/Engineering buta terhadap titik kegagalan internal. Observabilitas bukan sekadar mencetak log teks atau mengukur penggunaan RAM container; ini adalah kapabilitas telemetri deterministik untuk mengekstrak status internal sistem berdasarkan data eksternalnya.

---

## 05: Anatomi Konsep Inti

### 1. The Three Pillars of Observability + Continuous Profiling

```text
             +-----------------------+
             |      METRICS          | -> "Kapan dan seberapa besar anomali terjadi?"
             | (Counter, Gauge, Hist)|    Aggregation, high-level alerting (RED/USE).
             +-----------+-----------+
                         |
      +------------------+------------------+
      |                                     |
+-----+-----------------+             +-----+-----------------+
|        LOGS           |             |        TRACES         |
| (Structured, Correl.) |             | (Distributed Context) |
+-----+-----------------+             +-----+-----------------+
      | "Apa konteks detailnya?"            | "Di mana latensi terakumulasi?"
      | Contextual records & errors.        | Request execution path across nodes.
      +------------------+------------------+
                         |
             +-----------+-----------+
             |  CONTINUOUS PROFILING | -> "Line of code mana yang memakan resource?"
             | (Flamegraphs, V8 Ticks|    Low-overhead stack sampling.
             +-----------------------+
```

### 2. AsyncLocalStorage (ALS) & Execution Contexts

Node.js mengelola *asynchronous execution chain* menggunakan internal resource hooks (`async_hooks`). `AsyncLocalStorage` membungkus abstraksi ini untuk mengikat variabel kontekstual (seperti `TraceID`, `SpanID`, `TenantID`, `UserID`) ke rantai callback dan promise yang dieksekusi secara asinkron tanpa mem-passing objek secara eksplisit ke setiap parameter fungsi.

* **Performance Impact:** Hindari pemanggilan `AsyncLocalStorage.run()` secara berlebihan di dalam nested function loops kecil; panggil sekali pada *entry point* request lifecycle (misal: HTTP Middleware).

### 3. V8 Memory Spaces & Garbage Collection Internals

V8 membagi heap memory menjadi beberapa area penting:
* **New Space (Semi-space Nursery & Intermediate):** Lokasi alokasi objek baru. Dikelola oleh GC Scavenger yang sangat cepat (Minor GC).
* **Old Pointer Space & Old Data Space:** Lokasi objek yang bertahan dari siklus GC New Space. Dikelola oleh Major GC (*Mark-Sweep-Compact*).
* **Code Space:** Tempat kompilasi JIT code oleh Turbofan.
* **Large Object Space:** Objek yang ukurannya melampaui limit alokasi normal, langsung dialokasikan di sini dan tidak pernah dipindahkan oleh GC.

```text
+-------------------------------------------------------------------+
|                         V8 TOTAL HEAP                             |
|  +-----------------------------+  +----------------------------+  |
|  |          NEW SPACE          |  |         OLD SPACE          |  |
|  |  +------------+-----------+ |  |  +-----------------------+ |  |
|  |  | From-Space |  To-Space | |  |  |   Old Pointer Space   | |  |
|  |  +------------+-----------+ |  |  +-----------------------+ |  |
|  |    (Minor GC: Scavenge)     |  |  |   Old Data Space      | |  |
|  +--------------+--------------+  |  +-----------------------+ |  |
|                 | (Promotion)     |    (Major GC: Mark-Sweep)  |  |
|                 +---------------->+----------------------------+  |
+-------------------------------------------------------------------+
```

### 4. Event Loop Utilization (ELU) vs CPU Utilization

* **CPU Utilization:** Mengukur persentase waktu CPU yang dialokasikan OS ke proses Node.js (termasuk worker threads). Metrik ini sering menipu jika thread terblokir oleh I/O atau OS scheduling.
* **Event Loop Utilization (ELU):** Diperkenalkan pada `perf_hooks.performance.eventLoopUtilization()`. Mengukur rasio antara waktu yang dihabiskan Event Loop untuk mengeksekusi JavaScript handlers aktif dibanding waktu menganggur (*idle/polling*). Nilai ELU mendekati `1.0` (100%) menandakan Event Loop mengalami saturasi penuh (*CPU-bound starvation*).

---

## 06: Panduan Implementasi Step-by-Step

### Step 1: Inisialisasi Project dan Dependency Core

Pasang dependency standar performa tinggi untuk distributed tracing, metrics, dan structured logging:

```bash
mkdir node-observability-core && cd node-observability-core
npm init -y
npm install pino pino-pretty prom-client @opentelemetry/api @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node @opentelemetry/exporter-trace-otlp-grpc @grpc/grpc-js
npm install -D typescript @types/node ts-node
npx tsc --init
```

### Step 2: Konfigurasi OpenTelemetry Tracing Pre-Initialization Engine

Tracing OpenTelemetry harus diinisialisasi sebelum module lain di-load (monkey-patching native library seperti `http`, `pg`, `redis`). Buat file `tracer.ts`:

```typescript
// tracer.ts
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';

// Set logging level OTel untuk diagnosa internal
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.WARN);

const traceExporter = new OTLPTraceExporter({
  url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317',
});

export const otelSDK = new NodeSDK({
  traceExporter,
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': { enabled: false }, // Matikan tracing FS untuk mencegah noise
    }),
  ],
});

process.on('SIGTERM', () => {
  otelSDK
    .shutdown()
    .then(() => console.log('OTel SDK terminated gracefully'))
    .catch((err) => console.error('Error terminating OTel SDK', err))
    .finally(() => process.exit(0));
});
```

### Step 3: Global Context Propagation Wrapper menggunakan `AsyncLocalStorage`

Membuat wrapper context universal untuk mengikat `RequestId` dan `TraceId` ke seluruh sub-rutin aplikasi:

```typescript
// context.ts
import { AsyncLocalStorage } from 'node:async_hooks';

export interface RequestContext {
  requestId: string;
  traceId?: string;
  spanId?: string;
  userId?: string;
  startTime: bigint;
}

export const executionContext = new AsyncLocalStorage<RequestContext>();

export function getContext(): RequestContext | undefined {
  return executionContext.getStore();
}
```

---

## 07: Contoh Kasus Sederhana

Berikut implementasi logging asinkron berkinerja tinggi yang secara otomatis mengambil `traceId` tanpa harus mengirim parameter context antar fungsi.

```typescript
// simple-logger-test.ts
import pino from 'pino';
import { executionContext, getContext } from './context';
import { randomUUID } from 'node:crypto';

const baseLogger = pino({
  level: 'info',
  mixin() {
    const ctx = getContext();
    return {
      requestId: ctx?.requestId,
      traceId: ctx?.traceId,
    };
  },
});

function simulateDatabaseQuery(query: string) {
  setTimeout(() => {
    // Logger otomatis menyertakan requestId & traceId via mixin
    baseLogger.info({ query }, 'Query database selesai dieksekusi.');
  }, 100);
}

// Simulasi Inbound Request
function handleIncomingRequest(reqId: string, traceId: string) {
  const contextData = {
    requestId: reqId,
    traceId: traceId,
    startTime: process.hrtime.bigint(),
  };

  executionContext.run(contextData, () => {
    baseLogger.info('Memulai pemrosesan incoming HTTP request.');
    simulateDatabaseQuery('SELECT * FROM users WHERE id = 1;');
  });
}

handleIncomingRequest(randomUUID(), 'trace-sample-abc-123');
```

---

## 08: Implementasi Production-Grade Lengkap

Implementasi server HTTP lengkap siap-produksi dengan Prometheus Metrics, OpenTelemetry Tracing Context Correlated Logging, Native Event Loop Lag Profiler, On-Demand CPU/Heap Profiling Diagnostics API, dan Graceful Teardown.

```typescript
// server.ts
import http, { IncomingMessage, ServerResponse } from 'node:http';
import { monitorEventLoopDelay, performance, PerformanceObserver } from 'node:perf_hooks';
import v8 from 'node:v8';
import fs from 'node:fs';
import path from 'node:path';
import pino from 'pino';
import client from 'prom-client';
import { trace, context as otelContext } from '@opentelemetry/api';
import { executionContext, getContext } from './context';

// --- INITIALIZE PINTO LOGGER ---
const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level(label) {
      return { level: label };
    },
  },
  mixin() {
    const ctx = getContext();
    return {
      requestId: ctx?.requestId,
      traceId: ctx?.traceId,
      spanId: ctx?.spanId,
    };
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

// --- PROMETHEUS METRICS SETUP ---
const register = new client.Registry();
client.collectDefaultMetrics({ register, prefix: 'node_app_' });

const httpRequestDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
  registers: [register],
});

const eventLoopLagHistogram = new client.Histogram({
  name: 'nodejs_eventloop_lag_seconds',
  help: 'Event loop delay sampled via perf_hooks',
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
  registers: [register],
});

// --- LOW-OVERHEAD EVENT LOOP DELAY MONITORING ---
const eldHistogram = monitorEventLoopDelay({ resolution: 10 });
eldHistogram.enable();

setInterval(() => {
  const delayInSeconds = eldHistogram.mean / 1e9;
  if (!Number.isNaN(delayInSeconds)) {
    eventLoopLagHistogram.observe(delayInSeconds);
  }
  eldHistogram.reset();
}, 5000).unref(); // unref agar tidak menahan proses exit

// --- GC METRICS VIA PERFORMANCE OBSERVER ---
const gcObserver = new PerformanceObserver((list) => {
  const entries = list.getEntries();
  for (const entry of entries) {
    const detail = entry.detail as { kind?: number };
    const kindStr = detail?.kind === 1 ? 'minor' : detail?.kind === 2 ? 'major' : 'incremental';
    logger.debug(
      { gcKind: kindStr, durationMs: entry.duration },
      'Garbage Collection Cycle Completed'
    );
  }
});
gcObserver.observe({ entryTypes: ['gc'] });

// --- DIAGNOSTICS & RUNTIME PROFILING UTILITIES ---
class DiagnosticsManager {
  static takeHeapSnapshot(outputPath?: string): string {
    const defaultPath = path.join(process.cwd(), `heap-${Date.now()}.heapsnapshot`);
    const finalPath = outputPath || defaultPath;
    const fileName = v8.writeHeapSnapshot(finalPath);
    logger.warn({ snapshotPath: fileName }, 'V8 Heap Snapshot written to disk');
    return fileName;
  }

  static generateV8Report(): string {
    const report = process.report.getReport();
    logger.info('V8 Diagnostics Report Generated');
    return JSON.stringify(report);
  }
}

// --- CORE SERVER IMPLEMENTATION ---
const server = http.createServer(async (req: IncomingMessage, res: ServerResponse) => {
  const startTime = process.hrtime.bigint();
  const activeSpan = trace.getSpan(otelContext.active());
  const traceId = activeSpan?.spanContext().traceId;
  const spanId = activeSpan?.spanContext().spanId;
  const requestId = (req.headers['x-request-id'] as string) || crypto.randomUUID();

  // Membungkus request execution dalam context ALS
  await executionContext.run({ requestId, traceId, spanId, startTime }, async () => {
    const url = new URL(req.url || '/', `http://${req.headers.host}`);
    const pathname = url.pathname;

    logger.info({ method: req.method, path: pathname }, 'Inbound HTTP request received');

    // Endpoint Metrics
    if (pathname === '/metrics' && req.method === 'GET') {
      res.setHeader('Content-Type', register.contentType);
      res.writeHead(200);
      res.end(await register.metrics());
      return;
    }

    // Endpoint Diagnostics: Heap Snapshot (Restricted)
    if (pathname === '/admin/diagnostics/heap' && req.method === 'POST') {
      try {
        const filePath = DiagnosticsManager.takeHeapSnapshot();
        res.setHeader('Content-Type', 'application/json');
        res.writeHead(200);
        res.end(JSON.stringify({ status: 'Snapshot created', path: filePath }));
      } catch (err: any) {
        logger.error({ error: err.message }, 'Failed to take heap snapshot');
        res.writeHead(500);
        res.end(JSON.stringify({ error: err.message }));
      }
      return;
    }

    // Endpoint Workload Biasa
    if (pathname === '/api/compute' && req.method === 'GET') {
      // Simulasi delay operasional non-blocking
      await new Promise((resolve) => setTimeout(resolve, 50));
      
      const payload = JSON.stringify({ message: 'Compute task successfully completed.' });
      res.setHeader('Content-Type', 'application/json');
      res.writeHead(200);
      res.end(payload);

      // Record Telemetry
      const durationNanos = process.hrtime.bigint() - startTime;
      const durationSeconds = Number(durationNanos) / 1e9;
      httpRequestDuration.observe(
        { method: req.method, route: '/api/compute', status_code: 200 },
        durationSeconds
      );
      return;
    }

    // Not Found
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Endpoint not found' }));
  });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  logger.info({ port: PORT }, 'Production HTTP Server listening and instrumented');
});

// --- RESILIENT GRACEFUL SHUTDOWN HANDLER ---
const handleShutdown = (signal: string) => {
  logger.warn({ signal }, 'Termination signal received. Starting graceful shutdown sequence...');

  server.close(() => {
    logger.info('HTTP Server successfully closed. Releasing monitoring resources...');
    eldHistogram.disable();
    gcObserver.disconnect();
    process.exit(0);
  });

  // Force-exit jika gracefully teardown deadlock melebihi 10s
  setTimeout(() => {
    logger.error('Graceful shutdown timeout exceeded. Forcefully killing process.');
    process.exit(1);
  }, 10000).unref();
};

process.on('SIGINT', () => handleShutdown('SIGINT'));
process.on('SIGTERM', () => handleShutdown('SIGTERM'));

process.on('uncaughtException', (err: Error) => {
  logger.fatal({ err: err.stack }, 'Uncaught Exception detected! Taking Emergency Action.');
  // Mengambil Diagnostic Node Report sebelum crash keluar
  DiagnosticsManager.generateV8Report();
  process.exit(1);
});

process.on('unhandledRejection', (reason: unknown) => {
  logger.error({ reason }, 'Unhandled Promise Rejection detected.');
});
```

---

## 09: Diagram Alur Kerja (ASCII)

```text
Incoming HTTP Request
         │
         ▼
[AsyncLocalStorage.run()]  ◄── [Extract W3C Traceparent: TraceID/SpanID]
         │
         ├───► Set Context (requestId, traceId, startTime)
         │
         ▼
[Application Middleware & Route Processing]
         │
         ├─────────────────────────────────────────┐
         │                                         │
         ▼                                         ▼
[Execute Asynchronous Workload]           [Continuous Sampling Metrics]
  (DB Query, External Cache)                - monitorEventLoopDelay()
         │                                  - PerformanceObserver (GC)
         ▼                                         │
[Pino Logger: Injects Mixin Trace Context]         │
         │                                         │
         ▼                                         ▼
[Send HTTP Response]                      [Scraped via /metrics]
         │                                         │
         ▼                                         ▼
[Calculate Duration (process.hrtime)]     [Prometheus Time-Series DB]
         │
         ▼
[Observe Metrics (prom-client)]
         │
         ▼
[Trace Span Closed] ──► [OTel gRPC Batch Collector]
```

---

## 10: Analisis Trade-offs

| Pendekatan / Fitur | Keuntungan (Pros) | Biaya / Kerugian (Cons) | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **`AsyncLocalStorage`** | Isolasi konteks aman antar callback tanpa *parameter drilling*. | Overhead CPU mini (~2-5% degradation pada extreme micro-benchmarks). | Standard de-facto distributed tracing & contextual logging. |
| **Manual GC Triggering (`global.gc()`)** | Mencegah akumulasi memory leak sesaat sebelum task besar. | Memaksa Stop-The-World GC; menaikkan Latency Spike drastis. | **DILARANG** di lingkungan produksi; hanya untuk Automated Profiling Tests. |
| **Pino Logger (NDJSON Worker)** | Throughput tinggi, non-blocking I/O stream, resource-efficient. | Membutuhkan external log shippers (Filebeat, Vector) untuk ingestion. | Logging backend modern cloud-native & microservices. |
| **`writeHeapSnapshot()`** | Memberikan detail visual eksak setiap alokasi objek memory leak. | **Freeze process execution** selama serialisasi V8 memory ke disk (bisa 1s-10s). | Trigger *On-Demand* hanya pada worker terisolasi atau pre-OOM hook. |
| **Continuous Profiling (e.g., Pyroscope)** | Identifikasi line-by-line CPU hog secara terus menerus di live system. | Sedikit overhead sampling (~1-2% CPU) dan traffic jaringan tambahan. | Production high-load clusters untuk continuous optimization. |

---

## 11: Best Practices & Antipatterns

### Best Practices (DO)
1. **Always Measure Event Loop Delay via `perf_hooks`:** Gunakan histogram dengan resolusi milidetik untuk mendeteksi *freeze* microtask loop.
2. **Standardize on W3C Trace Context:** Propagasi header HTTP `traceparent` (`00-{trace_id}-{span_id}-{flags}`) secara transparan antar integrasi microservice.
3. **Use Safe Stringification on Logs:** Hindari `JSON.stringify` manual yang rentan terhadap exception `TypeError: Converting circular structure to JSON`. Serahkan serialisasi pada engine teroptimasi milik logger (seperti Fast-Safe-Stringify milik Pino).
4. **Implement Sampling Strategy for High-Throughput Traces:** Gunakan `TraceIdRatioBasedSampler` pada OTel SDK untuk hanya mengirimkan 5-10% trace saat traffic normal, dan 100% saat error response rate naik.

### Antipatterns (DON'T)
1. **Console.log in Hot Paths:** `console.log` bekerja secara sinkron ketika diarahkan ke file descriptor standar di terminal internal Node.js runtime, menghambat eksekusi loop secara masif.
2. **Attaching Profilers on the Primary Production Pod Without Traffic Draining:** Menjalankan CPU Profiling selama 60 detik penuh pada pod Kubernetes tunggal yang sedang melayani request live tanpa mengalihkan traffic dapat menyebabkan *connection dropped/readiness probe failure*.
3. **Logging Sensitive Data (PII Leak):** Merekam `req.headers` atau body secara raw tanpa redaksi (*masking*) field sensitif seperti `authorization`, `password`, dan `cardNumber`.
4. **Unchecked Core Dumps on Production Pods:** Mengaktifkan flags `--abort-on-uncaught-exception` tanpa batasan ukuran disk container storage, menyebabkan disk space Kubernetes Node penuh (*disk pressure eviction*).

---

## 12: Security Hardening

### 1. Proteksi Endpoint Diagnostik
Endpoint seperti `/metrics` atau `/admin/diagnostics/*` tidak boleh dapat diakses oleh publik:
* **Network Segregation:** Bind diagnostic HTTP server ke interface internal/loopback (`127.0.0.1`) atau port terpisah dari traffic ingress pelanggan.
* **Authentication Gate:** Wajibkan header API Key internal bertingkat tinggi atau integrasi mTLS internal:
  ```typescript
  function verifyDiagnosticAccess(req: IncomingMessage, res: ServerResponse): boolean {
    const internalSecret = process.env.DIAGNOSTIC_SHARED_SECRET;
    const providedSecret = req.headers['x-diagnostic-secret'];
    if (!internalSecret || providedSecret !== internalSecret) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Access to diagnostic layer denied.' }));
      return false;
    }
    return true;
  }
  ```

### 2. Log Redaction (PII Sanitization)
Aktifkan sanitasi field otomatis pada konfigurasi Pino untuk mencegah pelanggaran kepatuhan PCI-DSS atau GDPR:
```typescript
const secureLogger = pino({
  redact: {
    paths: ['req.headers.authorization', 'req.headers.cookie', 'password', 'creditCard.cvv'],
    censor: '[REDACTED]',
  },
});
```

---

## 13: Observabilitas & Debugging

### Menangkap dan Menganalisis CPU Profile di Lingkungan Produksi

Gunakan Node Inspector Client via Unix Domain Socket atau HTTP internal tanpa perlu me-restart proses.

1. **Jalankan Profiler On-Demand menggunakan Module Inspector Bawaan:**
```typescript
// profiler.ts
import inspector from 'node:inspector';
import fs from 'node:fs';

export function recordCpuProfile(durationMs: number, outputPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const session = new inspector.Session();
    session.connect();

    session.post('Profiler.enable', () => {
      session.post('Profiler.start', () => {
        setTimeout(() => {
          session.post('Profiler.stop', (err, { profile }) => {
            if (err) {
              session.disconnect();
              return reject(err);
            }
            fs.writeFileSync(outputPath, JSON.stringify(profile));
            session.post('Profiler.disable');
            session.disconnect();
            resolve();
          });
        }, durationMs);
      });
    });
  });
}
```

2. **Analisis Output:**
   * Buka browser Chrome/Chromium.
   * Masuk ke `chrome://inspect` -> Klik **Open dedicated DevTools for Node**.
   * Pilih tab **Profiler** -> Klik kanan -> **Load Profile**.
   * Beralih ke visualisasi **Flame Chart** untuk melacak call tree fungsi JavaScript yang mendominasi thread time.

---

## 14: Benchmarking & Performance

### Membandingkan Overhead Performance: Raw vs AsyncLocalStorage vs Tracing

Gunakan benchmark script menggunakan `autocannon` untuk mengukur dampak implementasi Observabilitas terhadap latency p99 dan throughput (Req/Sec).

```text
+-------------------------------------------------------------------------------+
|                        BENCHMARKING RESULTS OVERHEAD                          |
+--------------------------+---------------------+------------------------------+
| Skenario Telemetri       | Throughput (req/s)  | Latency p99 (ms)             |
+--------------------------+---------------------+------------------------------+
| Baseline (No Obs)        | 34,200 req/s        | 1.85 ms                      |
| Pino Logging Only        | 33,100 req/s (-3%)  | 2.01 ms                      |
| ALS Context Tracking     | 32,450 req/s (-5%)  | 2.15 ms                      |
| ALS + OTel Tracing + RED | 29,800 req/s (-12%) | 2.80 ms                      |
| Sync Logging (Anti-Pat)  |  8,200 req/s (-76%) | 22.40 ms (High Degradation)  |
+--------------------------+---------------------+------------------------------+
```

---

## 15: Hands-on Lab Mini-Project

### Masalah: Mendeteksi Memory Leak Melalui Diagnostic Heap Comparison

#### Kode Program Lab (`leak-lab.ts`)
```typescript
import http from 'node:http';
import v8 from 'node:v8';
import fs from 'node:fs';

// Simulasi Object Registry yang Bocor (Leaking Storage)
const leakyRegistry: Array<{ id: string; payload: Buffer; timestamp: number }> = [];

const server = http.createServer((req, res) => {
  if (req.url === '/leak') {
    // Alokasi memori berukuran ~100KB per request yang tidak pernah di-dereference
    const payload = Buffer.alloc(100 * 1024, 'X');
    leakyRegistry.push({
      id: crypto.randomUUID(),
      payload,
      timestamp: Date.now(),
    });

    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(`Leaked item. Total in memory: ${leakyRegistry.length}\n`);
    return;
  }

  if (req.url === '/snapshot') {
    const filename = `snapshot-${Date.now()}.heapsnapshot`;
    v8.writeHeapSnapshot(filename);
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end(`Snapshot captured: ${filename}\n`);
    return;
  }

  res.writeHead(404);
  res.end();
});

server.listen(4000, () => {
  console.log('Leak Lab Server aktif di port 4000');
});
```

#### Instruksi Lab Mandiri:
1. Jalankan `leak-lab.ts`: `npx ts-node leak-lab.ts`
2. Ambil snapshot baseline: `curl http://localhost:4000/snapshot` (Snapshot 1).
3. Generate load tiruan untuk memicu kebocoran:
   ```bash
   for i in {1..200}; do curl http://localhost:4000/leak; done
   ```
4. Ambil snapshot kedua: `curl http://localhost:4000/snapshot` (Snapshot 2).
5. Buka Chrome DevTools -> **Memory** -> Load kedua file snapshot.
6. Ubah view dari **Summary** menjadi **Comparison**.
7. Identifikasi objek `Buffer` / `Array` yang memiliki *Delta* positif besar dan periksa alur `Retainer` untuk menemukan referensi `leakyRegistry`.

---

## 16: Automated Testing & Verification

Unit test untuk memvalidasi bahwa propagasi context menggunakan `AsyncLocalStorage` tidak mengalami *leakage* antar request asinkron yang berjalan serentak.

```typescript
// context.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert';
import { executionContext, getContext } from './context';

describe('AsyncLocalStorage Context Isolation Verification', () => {
  test('harus mengisolasi context data secara independen antar konkurensi promise', async () => {
    const taskA = async () => {
      await executionContext.run(
        { requestId: 'REQ-AAA', startTime: process.hrtime.bigint() },
        async () => {
          await new Promise((res) => setTimeout(res, 50));
          const current = getContext();
          assert.strictEqual(current?.requestId, 'REQ-AAA');
        }
      );
    };

    const taskB = async () => {
      await executionContext.run(
        { requestId: 'REQ-BBB', startTime: process.hrtime.bigint() },
        async () => {
          await