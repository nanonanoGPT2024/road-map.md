# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengimplementasikan *distributed tracing* end-to-end berbasis OpenTelemetry API & SDK dengan propagasi konteks deterministik memanfaatkan `AsyncLocalStorage`.
- Merancang arsitektur telemetri performa tinggi dengan *zero event-loop blocking* menggunakan Worker Threads dan Unix Domain Sockets untuk *log shipping* dan *metric aggregation*.
- Melakukan isolasi dan diagnosis *memory leak* serta *event loop delay spikes* di lingkungan produksi tanpa mematikan proses utama, memanfaatkan mekanisme non-blocking *heap snapshotting* (`worker_threads` / `child_process.fork`).
- Mengoperasikan *continuous sampling profiling* V8 runtime di lingkungan kontainer Kubernetes dengan *overhead* CPU di bawah 1.5%.
- Menganalisis *post-mortem core dumps* dan format *Chrome DevTools Profile* untuk menemukan degradasi algoritma pada fase runtime Node.js.

---

## 2. Prerequisite

Sebelum memulai modul ini, Anda wajib memahami:
- **Node.js Internals**: Siklus hidup Libuv event loop (timers, pending callbacks, idle/prepare, poll, check, close callbacks) dan Microtask Queue (Promise jobs, `process.nextTick`).
- **Memory Management**: Arsitektur V8 Engine Heap (New Space, Old Pointer Space, Old Data Space, Large Object Space, Code Space) dan siklus Scavenge vs Mark-Sweep-Compact.
- **Concurrency primitives**: Ekosistem `node:worker_threads`, `node:child_process`, dan *inter-process communication* (IPC).
- **Networking**: Protokol HTTP/1.1, HTTP/2, gRPC dasar, serta terminologi OpenTelemetry (Tracer, Meter, Exporter, Collector, W3C TraceContext).

---

## 3. Concept & Internal Architecture

### 3.1 Context Propagation & AsyncLocalStorage Internals

Pada Node.js, konkurensi bersifat asinkron berbasis I/O multiplexing dalam *single thread execution context*. Tidak adanya model *thread-local storage* (TLS) seperti pada Java atau Go menuntut abstraksi runtime untuk melacak siklus hidup konteks request melintasi batas *asynchronous boundaries* (Promises, event emitters, setTimeout, native I/O).

V8 dan Libuv menyelesaikan problem ini melalui integrasi `async_hooks` yang mendasari `AsyncLocalStorage` (ALS).

```
[Request Inbound]
       │
       ▼
[ALS.run(store, callback)]
       │
       ├─► Init Resource (Triggered by Libuv async execution: net.Socket, PromiseInit)
       │     └─► V8 Engine preserves executionAsyncId & triggerAsyncId
       │
       ├─► Async Execution Chain (Promise.then / await)
       │     └─► Context propagated automatically via microtask queue mapping
       │
       ▼
[ALS.getStore()] ──► Membaca metadata request secara deterministik tanpa parameter drilling
```

Internal mekanisme ALS:
1. Setiap operasi asinkron mendapatkan alokasi *Async Resource Identifier* (`asyncId`) dan *Trigger Identifier* (`triggerAsyncId`).
2. Node.js V8 embedder bindings mengaitkan referensi JavaScript Store ke konteks eksekusi asinkron aktif saat ini.
3. Sejak Node.js v16.4+, emisi `AsyncLocalStorage` dioptimalkan secara native pada layer V8 microtask resolution tanpa dependensi penuh pada instansiasi objek `async_hooks` murni di userspace, mereduksi degradasi performa dari 30% menjadi kurang dari 1-2%.

### 3.2 Non-Blocking Heap Profiling Architecture

Mengeksekusi `v8.writeHeapSnapshot()` secara sinkron pada proses utama yang mengonsumsi RAM > 1.5 GB akan menghentikan (*freeze*) Event Loop selama ratusan hingga ribuan milidetik. Akibatnya, health-check Kubernetes (`livenessProbe`) mengalami timeout dan memicu restart loop (*CrashLoopBackOff*).

Arsitektur produksi mengatasi hal ini menggunakan strategi **Thread-offloaded Snapshotting** via `worker_threads` atau strategi **CoW (Copy-on-Write) Forking** via `child_process.fork()`:

```
+---------------------------------------------------------------------------------+
| Node.js Main Thread (Production Traffic)                                        |
| [Event Loop Running] ──┬───────────────────────────────────────────────────────|
+                        │ On-Demand Memory Breach Signal (>85% Heap Used)        |
                         ▼                                                        |
+---------------------------------------------------------------------------------+
| Fork Strategy (Linux Copy-on-Write)                                             |
|                                                                                 |
|  1. fork() process clone ──► [Child Process inherits memory pages without copy] |
|                                   │                                             |
|                                   ├─► Invokes v8.writeHeapSnapshot()            |
|                                   │   (Child frozen, Main continues serving)   |
|                                   │                                             |
|                                   ├─► Stream snapshot directly to S3 / Storage  |
|                                   │                                             |
|                                   └─► SIGKILL self (Child Process Exits)        |
+---------------------------------------------------------------------------------+
```

---

## 4. Why & What

| Dimensi | Observabilitas Tradisional (Console/APM Blackbox) | Arsitektur Observabilitas Produksi Modern |
| :--- | :--- | :--- |
| **Tracing Context** | Manual passing context ID/correlation ID melalui parameter fungsi (*anti-pattern*). | Implisit, *zero-signature overhead* via W3C TraceContext & `AsyncLocalStorage`. |
| **Diagnostic Decoupling** | Logging sinkron yang memblokir I/O; CPU Profiler menghentikan eksekusi transaksi. | Log transport asinkron berbasis memory-mapped buffer / IPC workers; Continuous V8 Sampling Profiling (19.9Hz). |
| **Memory Isolation** | Pengambilan snapshot di produksi memicu *downtime* layanan seketika. | Fork-isolated snapshotting berbasis virtual memory Copy-on-Write (CoW). |
| **Overhead** | Menambahkan APM agent closed-source berat yang memodifikasi prototype runtime (~10-15% CPU). | OpenTelemetry standar terbuka, *native telemetry channel* (`node:diagnostics_channel`), <2% CPU overhead. |

---

## 5. How (Workflow Detail)

Alur kerja observabilitas enterprise terbagi ke dalam 3 pipeline utama:

```
[ INBOUND REQUEST: Trace Context Header (traceparent) ]
                       │
                       ▼
         [ 1. Context Extraction & Storage ]
         AsyncLocalStorage mengisolasi Context (TraceId, SpanId, TenantId)
                       │
                       ├─────────────────────────────────────────┐
                       ▼                                         ▼
         [ 2. Diagnostics Tracing ]               [ 3. High-Throughput Logging ]
    Emisi event native internal via              Pino / Custom Log Engine
    `diagnostics_channel` (DB query,             Membaca context dari ALS
    HTTP outgoing, EventLoop latency)            Format JSON via Sonic-boom (Direct FD)
                       │                                         │
                       ▼                                         ▼
         [ 4. OpenTelemetry SDK ]                 [ 5. Worker Thread Transport ]
    BatchSpanProcessor memvalidasi sampling      Off-thread I/O transport ke Collector
                       │                                         │
                       └────────────────────┬────────────────────┘
                                            ▼
                       [ OTLP Ingestion Protocol (gRPC/HTTP) ]
                                            │
                                            ▼
                           [ OpenTelemetry Collector / APM ]
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah pabrik manufaktur berskala besar (Aplikasi Node.js):
- **Single Thread Event Loop** adalah **Operator Utama** yang mengarahkan ban berjalan. Operator ini tidak boleh berhenti sedetik pun.
- Menggunakan `console.log` secara langsung sama seperti menyuruh Operator Utama berhenti bekerja setiap 3 detik untuk menulis laporan log di papan tulis gudang luar.
- **Sonic-Boom / Worker Transport** adalah **Asisten Pribadi** yang berdiri di sebelah Operator. Operator hanya melempar kertas memo ke keranjang (memori bersama), dan Asisten yang berjalan keluar membawa tumpukan memo tersebut.
- **Copy-on-Write Heap Dump** adalah **Mesin Kloning Sesaat**. Alih-alih membekukan Operator Utama untuk memeriksa kondisi tubuhnya selama 1 jam, pabrik membuat klon bayangan Operator seketika. Klon bayangan berdiri diam untuk diperiksa dokter forensik, sementara Operator asli tetap memproses barang di ban berjalan.

```
                     ┌──────────────────────────────────────────────┐
                     │           NODE.JS EVENT LOOP ENGINE          │
                     └──────────────────────┬───────────────────────┘
                                            │
                    Logs / Spans            │  Triggers Fork on Alert
              ┌─────────────────────────────┴────────────────────────────┐
              ▼                                                          ▼
   ┌───────────────────────┐                                 ┌───────────────────────┐
   │ Ring Buffer / Worker  │                                 │   Child CoW Process   │
   │      (Off-Thread)     │                                 │   (Cloned RAM Snapshot)│
   └──────────┬────────────┘                                 └───────────┬───────────┘
              │                                                          │
              │ Non-blocking stream                                      │ Dumps Heap to Disk
              ▼                                                          ▼
   ┌───────────────────────┐                                 ┌───────────────────────┐
   │ Fluentd / OTel Agent  │                                 │   S3 Heap Storage     │
   └───────────────────────┘                                 └───────────────────────┘
```

---

## 7. Code Implementation: Practical Production Stack

Implementasi berikut memisahkan instrumentasi *contextual logging*, *safe heap dump generation*, dan *distributed tracing* secara modular dan siap digunakan di produksi.

### 7.1 Context Tracing Infrastructure (`telemetry/context.ts`)

```typescript
import { AsyncLocalStorage } from 'node:async_hooks';

export interface TraceContext {
  traceId: string;
  spanId: string;
  userId?: string;
  tenantId?: string;
}

export class ExecutionContext {
  private static instance = new AsyncLocalStorage<TraceContext>();

  public static run<R>(context: TraceContext, fn: () => R): R {
    return this.instance.run(context, fn);
  }

  public static get(): TraceContext | undefined {
    return this.instance.getStore();
  }

  public static getTraceId(): string {
    return this.instance.getStore()?.traceId ?? '00000000000000000000000000000000';
  }
}
```

### 7.2 High-Performance Worker-Thread Logger (`telemetry/logger.ts`)

```typescript
import pino from 'pino';
import { ExecutionContext } from './context.js';
import { resolve } from 'node:path';

// Menggunakan destination thread worker terpisah untuk logging asinkron tanpa I/O overhead
const transport = pino.transport({
  target: 'pino/file',
  options: {
    destination: 1, // stdout
    sync: false     // non-blocking
  }
});

export const logger = pino(
  {
    level: process.env.LOG_LEVEL || 'info',
    timestamp: pino.stdTimeFunctions.isoTime,
    mixin() {
      const ctx = ExecutionContext.get();
      if (!ctx) return {};
      return {
        trace_id: ctx.traceId,
        span_id: ctx.spanId,
        tenant_id: ctx.tenantId,
      };
    },
    formatters: {
      level(label) {
        return { level: label };
      },
    },
  },
  transport
);
```

### 7.3 Isolated Copy-on-Write Heap Dumper (`telemetry/heap-profiler.ts`)

```typescript
import { fork } from 'node:child_process';
import v8 from 'node:v8';
import { writeFileSync } from 'node:fs';
import { logger } from './logger.js';

export class ProductionProfiler {
  private static isDumping = false;

  public static triggerNonBlockingHeapSnapshot(destinationPath: string): Promise<string> {
    return new Promise((resolve, reject) => {
      if (this.isDumping) {
        return reject(new Error('Snapshot profile currently in progress'));
      }

      this.isDumping = true;
      const startTime = performance.now();

      // Implementasi fork child process untuk memanfaatkan OS Copy-on-Write (Linux/POSIX)
      // Child process mengisolasi freezing time dari event loop proses utama
      const child = fork(
        '-e',
        `
        const v8 = require('node:v8');
        const fileName = process.argv[1];
        try {
          const snapshotPath = v8.writeHeapSnapshot(fileName);
          process.send({ status: 'ok', path: snapshotPath });
        } catch (err) {
          process.send({ status: 'error', error: err.message });
        }
      `,
        [destinationPath],
        { stdio: ['ignore', 'ignore', 'ignore', 'ipc'] }
      );

      child.on('message', (msg: { status: string; path?: string; error?: string }) => {
        this.isDumping = false;
        const duration = (performance.now() - startTime).toFixed(2);
        
        if (msg.status === 'ok') {
          logger.info({ duration_ms: duration, path: msg.path }, 'CoW Heap snapshot successfully written');
          resolve(msg.path!);
        } else {
          logger.error({ error: msg.error }, 'Failed to write heap snapshot');
          reject(new Error(msg.error));
        }
      });

      child.on('error', (err) => {
        this.isDumping = false;
        reject(err);
      });

      child.on('exit', (code) => {
        this.isDumping = false;
        if (code !== 0) {
          reject(new Error(`Heap snapshot child process exited with code ${code}`));
        }
      });
    });
  }

  public static startContinuousMemoryMonitoring(thresholdBytes: number): NodeJS.Timeout {
    return setInterval(() => {
      const memoryUsage = process.memoryUsage();
      if (memoryUsage.heapUsed > thresholdBytes) {
        logger.warn(
          { heapUsed: memoryUsage.heapUsed, threshold: thresholdBytes },
          'Heap limit breach detected, triggering isolated dump'
        );
        const filename = `/tmp/heap-${Date.now()}.heapsnapshot`;
        this.triggerNonBlockingHeapSnapshot(filename).catch((err) => {
          logger.error({ err }, 'Automated heap snapshot failed');
        });
      }
    }, 10_000);
  }
}
```

### 7.4 Unified Express Server Integration (`app.ts`)

```typescript
import express, { Request, Response, NextFunction } from 'express';
import { randomUUID } from 'node:crypto';
import { ExecutionContext } from './telemetry/context.js';
import { logger } from './telemetry/logger.js';
import { ProductionProfiler } from './telemetry/heap-profiler.js';

const app = express();
app.use(express.json());

// Memory guard threshold: 1.2GB
const HEAP_LIMIT = 1.2 * 1024 * 1024 * 1024;
ProductionProfiler.startContinuousMemoryMonitoring(HEAP_LIMIT);

// Middleware Observabilitas (Context & Logging)
app.use((req: Request, res: Response, next: NextFunction) => {
  const traceId = (req.headers['x-trace-id'] as string) || randomUUID();
  const spanId = randomUUID().substring(0, 16);
  const tenantId = (req.headers['x-tenant-id'] as string) || 'unknown';

  ExecutionContext.run({ traceId, spanId, tenantId }, () => {
    const start = performance.now();
    logger.info({ path: req.path, method: req.method }, 'Incoming HTTP Request');

    res.on('finish', () => {
      const duration = performance.now() - start;
      logger.info(
        {
          path: req.path,
          statusCode: res.statusCode,
          duration_ms: duration.toFixed(3)
        },
        'Request Completed'
      );
    });

    next();
  });
});

app.get('/api/v1/work', async (req: Request, res: Response) => {
  // Operasi async acak
  await new Promise((resolve) => setTimeout(resolve, 50));
  res.json({ status: 'PROCESSED', traceId: ExecutionContext.getTraceId() });
});

// Diagnostic On-Demand Endpoint (Akses Terproteksi)
app.post('/internal/diagnostics/heap-dump', async (req: Request, res: Response) => {
  try {
    const fileName = `/tmp/manual-${Date.now()}.heapsnapshot`;
    const savedPath = await ProductionProfiler.triggerNonBlockingHeapSnapshot(fileName);
    res.status(202).json({ message: 'Snapshot completed', path: savedPath });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

export default app;
```

---

## 8. Real World Case Study: High-Throughput Fintech Gateway

### Deskripsi Masalah
Sebuah platform gateway pembayaran memproses 12.000 transaksi/detik pada kluster Kubernetes yang terdiri atas 40 *pod* Node.js. 

**Gejala Masalah**:
- Setiap 4 jam sekali, *p99 latency* melonjak drastis dari 45ms menjadi 2.500ms.
- Pod mengalami *OOMKilled* secara bergantian tanpa jejak eror jelas pada log aplikasi.
- Tim SRE mendapati metrik memori V8 naik tajam (*sawtooth pattern* yang gagal turun saat fase garbage collection).

### Investigasi Mendalam Menggunakan Observability Pipeline
1. **Analisis Diagnostics Channel**:
   Data trace dari OpenTelemetry menunjukkan *event loop delay* mencapai 1.800ms sesaat sebelum pod mati, terisolasi pada fase pemanggilan API settlement pihak ketiga.
2. **Post-Mortem Analysis**:
   Pengambilan *heap snapshot* secara manual memicu pod crash seketika karena *liveness probe fail*. Tim mengaktifkan *Copy-on-Write Heap Dump Mechanism*.
3. **Audit Heap Snapshot**:
   File `.heapsnapshot` dibuka menggunakan Chrome DevTools. Ditemukan objek `IncomingMessage` tersimpan di *retaining path*:
   ```
   Global Scope -> EventEmitter -> listeners -> retryQueue -> Closure Scope -> IncomingMessage
   ```
   Penyebab utama: Sebuah *error-handling library* pihak ketiga mendaftarkan event listener `client.on('error')` ke dalam `EventEmitter` singleton global tanpa memanggil `.removeListener()` ketika koneksi terputus.

### Solusi & Dampak Arsitektur
1. Mengubah registrasi listener menggunakan `AbortController` signal pattern (`{ signal: abortSignal }`) sehingga listener terlepas secara deterministik.
2. Memasang tracing continuous profiling untuk mendeteksi leak kecepatan alokasi (*allocation rate*) sebelum menyentuh batas ambang OOM:

```typescript
// Perbaikan retaining path via AbortSignal native di Node.js
export function bindSafeEventListener(emitter: EventEmitter, event: string, handler: (...args: any[]) => void) {
  const ac = new AbortController();
  emitter.on(event, handler, { signal: ac.signal });
  return () => ac.abort(); // Unbind total, membersihkan reference closure
}
```

**Hasil Pengukuran Setelah Optimasi**:
- *p99 latency* kembali stabil pada rentang **38ms - 42ms**.
- *Memory footprint* stabil di bawah 450MB per pod secara kontinu.
- Waktu identifikasi *root cause* bug serupa di masa depan terpangkas dari 3 hari menjadi 15 menit.

---

## 9. Trade-offs

| Pendekatan | Pros | Cons | Biaya Komputasi / Bottleneck |
| :--- | :--- | :--- | :--- |
| **AsyncLocalStorage** | Zero-leak parameter passing; tracing context terintegrasi native ke ekosistem. | Overhead pada throughput I/O sangat masif (~1-3%); bug jika menggunakan custom thenable. | CPU cycles ekstra pada V8 microtask tick scheduling. |
| **Worker Thread Logging** | Event loop utama 100% bebas dari blocking write ke STDOUT atau file stream. | Memori footprint naik karena instansiasi Worker Thread baru; overhead IPC serialization. | Penambahan alokasi baseline RAM (~30MB per worker thread). |
| **CoW Heap Snapshot** | Event Loop utama tidak mengalami freeze; ketersediaan layanan terjaga (uptime 99.99%). | Menggandakan *Virtual Memory* (VSS) sistem secara temporer; tidak kompatibel murni di OS Windows. | Risiko OOM di level OS jika Host Node tidak memiliki cukup swap/free page cache saat forking. |
| **OTel Full Instrumentation**| Visibilitas dependensi jaringan, queries, dan eksekusi fungsi tanpa celah. | Menghasilkan volume telemetri sangat masif (*high cardinality network bandwidth*). | *Ingestion cost* tinggi pada backend tracing (Tempo/Jaeger/Datadog). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Broken Context Propagation pada Custom Callback Wrappers
**Kesalahan**:
Menggunakan API berbasis event emitter atau callback library kuno yang membungkus pemanggilan di luar tracking AsyncLocalStorage.

```typescript
// SALAH: Konteks hilang karena callback dieksekusi di context origin lain
function executeLegacy(cb: () => void) {
  setTimeout(() => cb(), 100);
}

// BENAR: Re-binding context secara deterministik
import { AsyncLocalStorage } from 'node:async_hooks';
const als = new AsyncLocalStorage();

function executeFixed(cb: () => void) {
  const boundCb = AsyncLocalStorage.bind(cb);
  setTimeout(() => boundCb(), 100);
}
```

### 10.2 Logging Circular Object via Native Stringify
**Kesalahan**:
Menggunakan `JSON.stringify(data)` secara mentah di dalam middleware tracing. Jika data memuat `req` (yang merujuk pada `res`, dan sebaliknya), proses akan melempar exception `TypeError: Converting circular structure to JSON` atau memblokir CPU hingga V8 Crash.

**Penyelesaian**:
Gunakan serializer deterministik yang mengabaikan referensi melingkar seperti `fast-safe-stringify` atau manfaatkan native Pino serializing schema.

### 10.3 OOM Tersembunyi Akibat Tracing Queue Memory Buildup
Jika OpenTelemetry Collector mengalami down-time, in-memory span queue exporter dapat menumpuk ribuan objek trace span.
**Penyelesaian**:
Konfigurasikan pembatasan tegas pada `BatchSpanProcessor`:
```typescript
const traceProcessor = new BatchSpanProcessor(exporter, {
  maxQueueSize: 2048,          // Maksimum span yang disimpan di RAM
  maxExportBatchSize: 512,     // Ukuran chunk transmisi
  scheduledDelayMillis: 5000,  // Interval transmisi
  exportTimeoutMillis: 30000,  // Timeout jaringan
});
```

---

## 11. Best Practices (Production Checklist)

- [ ] **W3C TraceContext Compliance**: Selalu teruskan header `traceparent` dan `tracestate` ke setiap pemanggilan downstream I/O (HTTP, Message Broker, DB).
- [ ] **Sampling Rate Enforcement**: Jangan gunakan sampling 100% di produksi dengan throughput tinggi. Konfigurasikan `TraceIdRatioBasedSampler` pada rasio adaptif (e.g., 5% s.d 10%).
- [ ] **Non-Blocking Serializers**: Buang penggunaan modul logging seperti `winston` tanpa transport worker. Terapkan `pino` dengan sonic-boom destinations.
- [ ] **Safe Heap Dumps**: Jangan pernah mengeksekusi `v8.writeHeapSnapshot()` pada proses utama secara telanjang tanpa isolasi `fork()`.
- [ ] **High Cardinality Guard**: Jangan pernah memasukkan metadata unik tidak terbatas (misal: UUID, User Email, Token) ke dalam *Metric Labels/Tag Names*. Gunakan *Span Attributes* untuk data high cardinality.
- [ ] **Diagnostics Channel Utilization**: Manfaatkan `node:diagnostics_channel` untuk decoupled instrumentation libraries alih-alih me-monkey-patch method prototype internal.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── worker-transport.ts
│   ├── isolated-profiler.ts
│   └── server.ts
```

### Langkah 1: Inisialisasi Environment
Jalankan di root hands-on direktori:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install typescript @types/node pino express @types/express
npx tsc --init --target ES2022 --module NodeNext --moduleResolution NodeNext --outDir dist
```

### Langkah 2: Buat Profiler & Worker Script (`src/isolated-profiler.ts`)
```typescript
import { fork } from 'node:child_process';
import path from 'node:path';

export function captureIsolatedHeap(outputPath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const workerScript = `
      const v8 = require('node:v8');
      try {
        const file = process.argv[1];
        v8.writeHeapSnapshot(file);
        process.send({ success: true, path: file });
      } catch (err) {
        process.send({ success: false, error: err.message });
      }
    `;

    const child = fork('-e', workerScript, [outputPath], {
      stdio: ['ignore', 'ignore', 'ignore', 'ipc']
    });

    child.on('message', (msg: any) => {
      if (msg.success) resolve(msg.path);
      else reject(new Error(msg.error));
    });

    child.on('error', reject);
    child.on('exit', (code) => {
      if (code !== 0) reject(new Error(`Exit with code ${code}`));
    });
  });
}
```

### Langkah 3: Implementasikan Server Testing Performa (`src/server.ts`)
```typescript
import express from 'express';
import { captureIsolatedHeap } from './isolated-profiler.js';

const app = express();
const leakyArray: any[] = [];

// Endpoint simulasi leak
app.get('/leak', (req, res) => {
  for (let i = 0; i < 50000; i++) {
    leakyArray.push({
      timestamp: Date.now(),
      payload: 'mem-leak-test-data-'.repeat(20),
    });
  }
  res.send({ status: 'LEAKING', totalAllocatedObjects: leakyArray.length });
});

// Endpoint untuk memicu capture tanpa membekukan request lain
app.get('/snapshot', async (req, res) => {
  const dest = `/tmp/snapshot-${Date.now()}.heapsnapshot`;
  try {
    const savedPath = await captureIsolatedHeap(dest);
    res.send({ status: 'SUCCESS', savedPath });
  } catch (err: any) {
    res.status(500).send({ status: 'FAILED', error: err.message });
  }
});

app.get('/ping', (req, res) => {
  res.send('PONG - Event Loop Unblocked!');
});

app.listen(8080, () => {
  console.log('Telemetry Diagnostic Server running on port 8080');
});
```

### Langkah 4: Uji Coba Non-Blocking Validation
1. Jalankan server:
   ```bash
   npx ts-node-esm src/server.ts
   ```
2. Trigger leak berkali-kali di terminal 1:
   ```bash
   curl http://localhost:8080/leak
   curl http://localhost:8080/leak
   ```
3. Request heap snapshot di terminal 2:
   ```bash
   curl http://localhost:8080/snapshot
   ```
4. Verifikasi bahwa `/ping` merespons secara instan pada milidetik yang sama saat snapshot sedang diekspor:
   ```bash
   curl http://localhost:8080/ping
   ```

---

## 13. Exercises

### Level Easy
Modifikasi implementasi `logger.ts` agar mengecualikan (*masking*) field-field sensitif (seperti `password`, `authorization`, dan `creditCard`) secara otomatis menggunakan fungsionalitas Pino Redaction.

### Level Medium
Buat modul integrasi `node:diagnostics_channel` native untuk mendeteksi setiap pemanggilan method database SQL query dan mengekspos metrik `query_duration_ms` ke dalam struktur log tanpa melakukan *wrapping* manual pada pemanggilan method DB client.

### Level Hard
Bangun sebuah *Continuous Sampling CPU Profiler* yang secara otomatis mengumpulkan profile V8 (`v8.profiler`) selama 10 detik setiap kali *Event Loop Lag* (diukur via `perf_hooks.monitorEventLoopDelay`) melampaui angka 100ms selama 3 interval berturut-turut. Profiling harus disimpan ke disk dalam format `.cpuprofile` yang valid dan siap dianalisis di Chrome DevTools.

---

## 14. Challenge

### Studi Kasus: Telemetry Collector Under Massive Pressure
Sebuah aplikasi Node.js *Real-time Streaming Engine* memproses mutasi state sebesar 45.000 events/detik. Ketika Anda menyalakan APM Tracing agent, performa aplikasi turun drastis (throughput ambruk hingga 65% dan alokasi memori meledak).

**Tantangan**:
1. Buat sistem kustom tracing telemetry dengan batasan:
   - Maksimum alokasi memori sirkular buffer untuk traces adalah 64MB.
   - Jika buffer penuh akibat exporter remote down, sistem harus menerapkan strategi drop data (*drop newest* atau *drop oldest*) secara presisi dan non-blocking.
   - Tidak diperbolehkan menggunakan library APM *third-party* yang memodifikasi native prototype (`@opentelemetry/sdk-trace-node`, Datadog, New Relic). Gunakan primitives native: `node:async_hooks`, `node:worker_threads`, dan `node:perf_hooks`.
2. Sediakan pembuktian beban (*stress testing script*) yang mendemonstrasikan bahwa *event loop delay* tetap berada di bawah 15ms saat memproses beban puncak 50.000 event per detik.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa parameter drilling (passing metadata dari function ke function) dianggap anti-pattern dalam konteks distributed tracing di Node.js?**
2. **Apa perbedaan mendasar antara `executionAsyncId` dan `triggerAsyncId` pada arsitektur `async_hooks`?**
3. **Mengapa pemanggilan `console.log` secara native dapat mendegradasi performa aplikasi Node.js pada throughput tinggi?**
4. **Apa fungsi utama dari standar W3C `traceparent` header?**
5. **Mengapa sampling rate tracing 100% tidak disarankan untuk aplikasi kelas enterprise dengan jutaan request harian?**

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana mekanisme Copy-on-Write (CoW) pada Linux OS mencegah pembengkakan memori ganda saat proses di-forking untuk snapshotting?**
2. **Mengapa `AsyncLocalStorage` memiliki performa yang lebih tinggi dibanding modul `async_hooks` userspace lama?**
3. **Apa dampak negatif jika metadata high-cardinality (seperti timestamp unik atau session ID) dijadikan label pada metrik Prometheus?**
4. **Kapan kondisi di mana `AsyncLocalStorage.getStore()` dapat menghasilkan nilai `undefined` di tengah rantai eksekusi Promise?**
5. **Bagaimana cara kerja transport Pino yang menggunakan `pino.transport()` dalam mengisolasi I/O disk/stdout dari Event Loop utama?**

### Bagian 3: Production Scenarios (3 Skenario Kasus)

#### Skenario 1
Layanan pembayaran berbasis Node.js mengalami crash dengan pesan `JavaScript heap out of memory`. Setelah diteliti, tim SRE tidak dapat menemukan snapshot heap karena flag `--max-old-space-size` menyentuh batas maksimum pods memory limit (cgroups), sehingga Pod dimatikan oleh host Linux (OOMKilled) sebelum file snapshot selesai ditulis ke disk.
*Pertanyaan*: Bagaimana Anda mendesain konfigurasi memori Node.js dan Kubernetes Resource Limits agar file diagnostics tetap dapat ditangkap sebelum proses dibunuh secara paksa oleh Kernel OOM-killer?

#### Skenario 2
Setelah Anda menambahkan middleware OpenTelemetry yang mengekstraksi context dari header HTTP masuk, p99 latency aplikasi meningkat dari 30ms ke 120ms. Hasil profiling menunjukkan bahwa alokasi Garbage Collection (GC) Scavenge cycles meningkat 400%.
*Pertanyaan*: Komponen arsitektural mana dari trace creation yang kemungkinan besar menyebabkan lonjakan alokasi objek jangka pendek (short-lived objects) ini, dan bagaimana cara memitigasinya tanpa mematikan tracing?

#### Skenario 3
Sistem e-commerce Anda memiliki microservice Node.js yang melakukan integrasi ke database legacy via driver lama berbasis event listener event-driven murni (tanpa Promise). Tracing context ID (`traceId`) tiba-tiba tertukar antar satu pelanggan dengan pelanggan lain di bawah beban konkurensi 500 req/sec.
*Pertanyaan*: Analisis akar permasalahan teknis mengapa context ID bisa bocor (*cross-talk*) antar context pelanggan, dan susun solusi recovery strukturalnya menggunakan primitives Node.js.

---

### Kunci Jawaban & Evaluasi

#### Kunci Bagian 1: Basic
1. Parameter drilling merusak modularitas arsitektur, mengubah antarmuka (signature) fungsi domain murni untuk urusan infrastruktur, dan rawan terputus jika melewati library pihak ketiga.
2. `executionAsyncId` mengidentifikasi konteks eksekusi asinkron yang sedang berjalan saat ini, sedangkan `triggerAsyncId` adalah id konteks asinkron yang menyebabkan/memicu operasi ini dibuat.
3. `console.log` mengeksekusi operasi `fs.writeSync` secara sinkron terhadap stdout jika diarahkan ke TTY/file redirection di banyak platform, menyebabkan Libuv event loop berhenti menunggu I/O disk selesai.
4. Menstandarisasi format serialisasi context tracing lintas platform: versi, 16-byte trace-id, 8-byte parent-id (span-id), dan trace-flags (e.g. sampling bit).
5. Beban penyimpanan (storage cost), bandwidth jaringan, dan overhead CPU untuk memproses jutaan trace spans dapat melampaui biaya operasional komputasi server aplikasi itu sendiri.

#### Kunci Bagian 2: Intermediate
1. Saat `fork()` dipanggil, kernel Linux tidak menyalin halaman memori fisik (RAM), melainkan hanya menyalin tabel *page directory*. Halaman RAM fisik yang sama dibagikan secara read-only antara Parent dan Child. Alokasi baru hanya terjadi jika salah satu proses menulis data ke halaman tersebut (*copy on write*).
2. Node.js v16.4+ mengintegrasikan ALS langsung ke internal binding C++ engine V8 (Promise hooks optimization) tanpa mengaktifkan flag observabilitas umum `async_hooks` userspace yang men-disable optimasi native Promise inline allocation.
3. Terjadi ledakan kombinasi metrik (*cardinality explosion*). TSDB (Time Series Database) seperti Prometheus mengalokasikan index series terpisah untuk setiap variasi label, menyebabkan memori server TSDB habis (OOM crash).
4. Ketika context boundary terputus: misalnya callback dipanggil oleh native bridge non-tracked, atau ada *break of promise chain* di mana pemanggilan dipindahkan ke execution context yang tidak di-bind via `als.run()` atau `als.bind()`.
5. Worker transport Pino memindahkan serialisasi byte-stream dan flushing I/O ke dalam `node:worker_threads` terpisah via SharedArrayBuffer/MessagePort, membebaskan thread komputasi JavaScript utama dari kalkulasi string formatting dan I/O latency.

#### Kunci Bagian 3: Evaluasi Kasus Produksi
1. **Analisis Skenario 1**:
   Alokasikan `--max-old-space-size` pada nilai **70% s.d 75%** dari Kubernetes `resources.limits.memory` pod. Contoh: jika Pod Limit adalah 2Gi, atur `--max-old-space-size=1536` (1.5Gi). Sisakan 512MB untuk alokasi memori C++ (Buffer), Virtual Memory overhead, dan proses child fork agar saat `heapUsed` mencapai ambang batas, V8 trigger dump masih berada jauh di bawah ambang kill cgroups Linux OOM.
2. **Analisis Skenario 2**:
   Penyebab utama: SDK tracing instansiasi objek JavaScript baru (Spans, Context Map, attributes) secara berlebihan untuk setiap *tick* microtask yang langsung dibuang ke New Space, memicu Scavenge GC berulang. Mitigasi: Ubah implementasi trace sampler menjadi `ParentBasedSampler` dengan `TraceIdRatioBasedSampler(0.05)` di layer upstream paling awal, gunakan *span attribute object pool* atau hindari alokasi closure internal pada tracer wrapper.
3. **Analisis Skenario 3**:
   Driver legacy menggunakan `EventEmitter` global atau pooling instance yang meng-emit event kembali pada cycle event loop berikutnya tanpa menyimpan state context asli. Karena scope context lama tertimpa oleh request baru yang masuk sebelum event di-emit, callback membaca ALS context teratas/terakhir yang aktif. Solusi: Bungkus setiap listener menggunakan `AsyncLocalStorage.bind(handler)` atau lakukan capture context ID ke dalam lexical closure scope pada saat event listener didaftarkan, lalu restore context eksplisit via `als.run()` di dalam handler.

---

## 16. Summary

Observabilitas Node.js tingkat lanjut menuntut transisi dari logging/metrik pasif ke instrumentasi internal yang sadar arsitektur (*runtime-aware instrumentation*). Pemanfaatan `AsyncLocalStorage` menjamin korelasi konteks transaksi secara global tanpa merusak arsitektur kode. Untuk menjaga ketahanan produksi, operasi telemetri berat—seperti formatting JSON, log transport, dan *heap extraction*—harus selalu diisolasi dari Event Loop utama melalui pemanfaatan primitives tingkat rendah seperti `worker_threads` dan *Copy-on-Write forking*. Integrasi yang tepat dari teknik-teknik ini menjamin *visibility* sistem 100% tanpa mengorbankan performa transaksi aplikasi pada skala masif.