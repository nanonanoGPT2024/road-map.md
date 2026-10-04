# BAB 09: Performance Engineering, Profiling & Telemetry
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis dan mengisolasi bottleneck CPU dan degradasi memori di lingkungan Node.js menggunakan V8 Profiler native (`inspector`, `v8`, `perf_hooks`).
- Merancang dan mengimplementasikan arsitektur telemetri terdistribusi berbasis OpenTelemetry (OTel) dengan overhead CPU/memori terukur (<1% p99 overhead).
- Mengintegrasikan pelacakan asynchronous context end-to-end menggunakan `AsyncLocalStorage` tanpa memicu deoptimasi V8 atau context leak.
- Membangun pipeline pemantauan metrik runtime real-time (Event Loop Delay, Garbage Collection phases, Active Handles) dan mengekspornya ke format Prometheus/OTLP.
- Mendiagnosis degradasi performa skala enterprise (high concurrency, multi-tier microservices) menggunakan sampling profiler, allocation timelines, dan flame graph analysis.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Arsitektur Internal Node.js & V8**: Siklus hidup Event Loop (Libuv phases: timers, pending callbacks, poll, check, close), V8 Memory Spaces (New Space, Old Pointer/Data Space, Large Object Space, Code Space), dan Generational GC (Scavenge vs Mark-Sweep-Compact).
- **Pemrograman Asinkron Lanjutan**: Promise lifecycle, microtask queues, dan asynchronous scheduling patterns.
- **Networking & Protokol**: Dasar-dasar HTTP/2, gRPC, TCP socket, dan format serialisasi biner (Protocol Buffers).
- **Tooling Dasar**: Kemampuan mengeksekusi Node.js CLI, flags V8 (`--prof`, `--inspect`, `--max-old-space-size`), serta navigasi dasar terminal Unix/Linux.

---

### 3. Concept & Internal Architecture

Eksekusi JavaScript pada Node.js bertumpu pada runtime V8 dan Libuv. Membangun observabilitas pada sistem ini menuntut pemahaman mendalam tentang cara profiler mengekstraksi data internal mesin tanpa mendegradasi throughput aplikasi secara katastropik.

```
+-----------------------------------------------------------------------------------+
| Node.js Process                                                                   |
|                                                                                   |
|  +--------------------------------+   +----------------------------------------+  |
|  | Libuv Event Loop (OS Threads)  |   | V8 JavaScript Engine                   |  |
|  | - Timers (min-heap)            |   | - Parser & Bytecode Generator (Ignition)|  |
|  | - I/O Poll (epoll/kqueue)      |   | - JIT Compiler (TurboFan)              |  |
|  | - Check Phase (setImmediate)   |   | - Memory Heap (Scavenge, Mark-Compact) |  |
|  | - Active Handles / Requests    |   | - Sampling Profiler Engine (Safe Points)|  |
|  +---------------+----------------+   +-------------------+--------------------+  |
|                  ^                                        ^                       |
|                  |                                        |                       |
|  +---------------+----------------------------------------+--------------------+  |
|  | Diagnostic & Telemetry Layer                                                |  |
|  |                                                                             |  |
|  |  +---------------------------+        +----------------------------------+  |  |
|  |  | perf_hooks & Node Tracing |        | AsyncLocalStorage (ALS)          |  |  |
|  |  | - monitorEventLoopDelay() |        | - ExecutionContext Tree          |  |  |
|  |  | - PerformanceObserver     |        | - Resource Destruction Hooks     |  |  |
|  |  +-------------+-------------+        +----------------+-----------------+  |  |
|  |                |                                       |                    |  |
|  |                v                                       v                    |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  | OpenTelemetry Tracing / Metrics Core Engine                          |  |  |
|  |  | - In-Memory Ring Buffer (Zero-Allocation Batching)                     |  |  |
|  |  | - Context Propagation (W3C TraceContext: traceparent, tracestate)     |  |  |
|  |  +-------------------------------------+---------------------------------+  |  |
+--+----------------------------------------|------------------------------------+--+
                                            | Non-blocking Flush / Worker Thread
                                            v
                      +------------------------------------------+
                      | OpenTelemetry Collector / OTLP Endpoint  |
                      +------------------------------------------+
```

#### A. Mekanisme Profiling CPU: Instrumentation vs. Sampling
1. **Instrumentation Profiler**: Menyuntikkan kode pelacak (prologue/epilogue) di setiap function call. Metode ini memiliki *high overhead* (Heisenbug effect), mendistorsi inline caching, dan mencegah optimasi compiler TurboFan.
2. **Sampling Profiler (V8 Built-in)**: Berjalan pada OS thread terpisah. Setiap interval waktu tertentu (default: 1ms), thread profiler mengirimkan interrupt signal (misal: `SIGPROF` pada POSIX) ke thread utama V8. 
   - V8 membaca Program Counter (PC) dan merekonstruksi Call Stack dari register frame pointer (`rbp`/`ebp`).
   - Eksekusi stack sample disimpan ke dalam circular ring buffer.
   - Karena interupsi hanya membaca memory stack pada interval tertentu, overhead performa tetap rendah (<2-5%), menjadikannya standar baku untuk sistem produksi.

#### B. Event Loop Telemetry & Histogram High-Resolution
Memantau CPU utilization saja tidak cukup untuk Node.js, karena arsitektur *single-threaded event loop* dapat mengalami *starvation* meski CPU usage rendah (misalnya akibat blocking I/O atau microtask queue overflow).
- Modul `perf_hooks` menyediakan `monitorEventLoopDelay({ resolution: 10 })`.
- Di balik layar, API ini mengonfigurasi timer Libuv resolusi tinggi (menggunakan HdrHistogram). Setiap siklus, Libuv menghitung deviasi antara waktu yang dijadwalkan vs waktu eksekusi aktual:
  $$\text{Delay} = t_{\text{actual}} - t_{\text{scheduled}}$$
- Distribusi latensi ini dicatat dalam format bucket logaritmik (HdrHistogram) untuk menghitung p50, p90, p99, dan p99.9 tanpa alokasi memori berlebih.

#### C. Asynchronous Context Propagation: AsyncLocalStorage
Dalam arsitektur mikroservis terdistribusi, context propagation (Trace ID, Span ID, Baggage) harus dipertahankan di seluruh rantai asynchronous operations:
- `AsyncLocalStorage` (ALS) dibangun di atas C++ internal `AsyncWrap`.
- Setiap kali operasi asinkron diinisialisasi (Promise, fs call, timer), V8/Node.js mengaitkan internal ID unik (`asyncId`) dan trigger ID (`triggerAsyncId`).
- Objek context disimpan dalam struktur data berbasis internal weak-reference. Jika ALS disalahgunakan (misalnya menyimpan referensi instance objek besar yang saling terikat), V8 Garbage Collector tidak dapat membersihkan graph tersebut, memicu *retained memory leak*.

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Legacy | Pendekatan Production-Grade Telemetry |
| :--- | :--- | :--- |
| **Pencatatan Log & Tracing** | `console.log()` sinkron ke `stdout`, parsing regex string manual, tanpa korelasi request. | Structured Logging (Pino/NDJSON) dengan injeksi TraceID via `AsyncLocalStorage` otomatis. |
| **Metrik Runtime** | Interval `setInterval` memanggil `process.memoryUsage()`, menimbulkan jitter loop. | `perf_hooks.monitorEventLoopDelay()` (HdrHistogram Libuv) & GC PerformanceObserver hooks. |
| **Analisis Bottleneck CPU** | Tebak-tebakan kode, trial-and-error, restart container acak. | V8 Tick Profiling via DevTools Inspector Protocol, FlameGraph analysis, dan continuous profiling. |
| **Tracing Konteks** | Melewatkan parameter `reqContext` secara manual ke ratusan function signature (signature pollution). | Implicit Context Propagation via W3C Trace Context standard compliant OTel Tracer. |
| **Dampak Performa** | Blocking I/O saat serialisasi log, V8 de-optimasi, lonjakan p99 latency drastis. | Zero-allocation buffering, async I/O worker export, non-blocking telemetry footprint. |

---

### 5. How (Workflow Detail)

Alur kerja instrumentasi dan diagnosis performa produksi terdiri dari tiga fase:

```
[ Inisialisasi Runtime ]
          │
          ├──> 1. Aktifkan OTel SDK & TracerProvider sebelum runtime require/import modul lain.
          ├──> 2. Pasang monitorEventLoopDelay & GC PerformanceObserver.
          └──> 3. Konfigurasi AsyncLocalStorage bridge untuk unified context propagation.
          │
[ Eksekusi & Tracing Request ]
          │
          ├──> 1. Extract W3C TraceParent headers dari inbound transport (HTTP/gRPC).
          ├──> 2. Bungkus eksekusi handler dalam ALS Context (`als.run(context, callback)`).
          ├──> 3. Buat Span: Catat Network/DB latency via hooks otomatis.
          └──> 4. Injeksi TraceID ke setiap structured log entry secara deterministik.
          │
[ Deteksi Anomali & Profiling ]
          │
          ├──> Latensi p99 melebihi Threshold (> 500ms)?
          │       ├─ YES ──> Trigger V8 Profiler Snapshot via V8 Inspector Session.
          │       └─ NO  ──> Lanjutkan aggregasi ring-buffer metrik.
          │
          └──> Ekspor Metrik & Spans ke OTel Collector via Protocol Buffers (gRPC/HTTP).
```

---

### 6. Analogy & Diagram ASCII

Bayangkan Node.js sebagai sebuah **Dapur Restoran Modern**:
- **Event Loop (Libuv)** adalah **Kepala Koki Tunggal** (Single Threaded). Dia sangat cepat memasak, tetapi hanya bisa memproses satu tiket pesanan dalam satu waktu.
- **Microtask Queue** adalah catatan tempel (*post-it*) darurat yang ditempel tepat di depan mata Koki. Koki *harus* menyelesaikan semua post-it ini sebelum mengambil tiket pesanan baru dari antrean meja.
- **Sampling Profiler** adalah **Manajer Kualitas** yang berdiri di pojok dapur. Setiap 1 milidetik, dia melihat ke arah Koki, memotret posisi tangannya, dan mencatat apa yang sedang dikerjakan Koki. Dia tidak menghentikan Koki, hanya mengambil snapshot cepat.
- **AsyncLocalStorage** adalah **Buku Resep Ber-Barcode**. Ke mana pun pesanan berpindah (ke oven, ke kulkas, ke asisten pemotong), buku resep tersebut membawa barcode pesanan awal sehingga tidak tertukar dengan pesanan meja lain.

```
       +--------------------------------------------------------------+
       | EVENT LOOP CYCLE & SAMPLING SNAPSHOT                         |
       +--------------------------------------------------------------+
Time   |
  │    | [Phase: Poll] ----> Request 101 Diterima                     |
  │    |   │                                                          |
  │    |   ├──> Sampling Snapshot 1: [V8 Execution: JSON.parse]       |
  │    |   │                                                          |
  │    |   ├──> Async Call (DB Query) ──> Operasi didelegasikan       |
  │    |   │                                                          |
  │    | [Phase: Timers]                                              |
  │    |   │                                                          |
  │    |   └──> Sampling Snapshot 2: [Libuv: Idle / OS epoll wait]    |
  │    |   │                                                          |
  │    | [Phase: Poll] <──── DB Query Selesai                         |
  │    |   │                                                          |
  │    |   ├──> ALS Restore Context (Trace ID: 4bf92f3577b34da6)      |
  │    |   │                                                          |
  │    |   ├──> Sampling Snapshot 3: [V8 Execution: Data Processing]  |
  │    |   │    └── Blocked 120ms (RegExp ReDoS)                      |
  │    |   │        Sampling Snapshot 4: [V8: RegExp Exec]            |
  │    |   │        Sampling Snapshot 5: [V8: RegExp Exec]            |
  ▼    |   └──> Event Loop Delay Alarm Triggered! (p99 spike)         |
       +--------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Deteksi Event Loop Delay & GC Metrics Native
Skrip native (tanpa third-party package) untuk memonitor lag event loop dan durasi fase GC menggunakan `perf_hooks`.

```javascript
// runtime-monitor.js
import { monitorEventLoopDelay, PerformanceObserver, performance } from 'node:perf_hooks';
import v8 from 'node:v8';

// 1. Inisialisasi Event Loop Delay Tracker (Resolusi: 10ms)
const elHistogram = monitorEventLoopDelay({ resolution: 10 });
elHistogram.enable();

// 2. Observasi Garbage Collection Latency
const gcObserver = new PerformanceObserver((list) => {
  const entries = list.getEntries();
  for (const entry of entries) {
    const gcType = entry.detail?.kind || 'UNKNOWN';
    console.log(JSON.stringify({
      telemetry: 'gc_phase',
      duration_ms: entry.duration.toFixed(3),
      type: gcType,
      timestamp: performance.timeOrigin + entry.startTime
    }));
  }
});
gcObserver.observe({ entryTypes: ['gc'] });

// 3. Periodic Reporting Engine
setInterval(() => {
  const heap = v8.getHeapStatistics();
  const memoryUsage = process.memoryUsage();

  const metrics = {
    telemetry: 'runtime_snapshot',
    event_loop_delay_p50_ms: (elHistogram.percentile(50) / 1e6).toFixed(3),
    event_loop_delay_p99_ms: (elHistogram.percentile(99) / 1e6).toFixed(3),
    event_loop_delay_max_ms: (elHistogram.max / 1e6).toFixed(3),
    heap_used_mb: (memoryUsage.heapUsed / 1024 / 1024).toFixed(2),
    heap_total_mb: (memoryUsage.heapTotal / 1024 / 1024).toFixed(2),
    external_mb: (memoryUsage.external / 1024 / 1024).toFixed(2),
    heap_limit_mb: (heap.heap_size_limit / 1024 / 1024).toFixed(2),
    timestamp: Date.now()
  };

  console.log(JSON.stringify(metrics));
  elHistogram.reset();
}, 5000).unref(); // unref agar tidak mengunci event loop saat shutdown
```

#### B. Practical Example: Enterprise Distributed Telemetry Core
Implementasi pelacak performa transaksi lengkap dengan context propagation manual via `AsyncLocalStorage` dan trace injection terstruktur.

```javascript
// telemetry-core.js
import { AsyncLocalStorage } from 'node:async_hooks';
import { randomBytes } from 'node:crypto';
import http from 'node:http';

// Context Store untuk W3C Trace Context
class TelemetryContext {
  constructor(traceId, spanId, parentId = null) {
    this.traceId = traceId || randomBytes(16).toString('hex');
    this.spanId = spanId || randomBytes(8).toString('hex');
    this.parentId = parentId;
    this.startTime = process.hrtime.bigint();
    this.attributes = new Map();
  }

  setAttribute(key, value) {
    this.attributes.set(key, value);
  }

  toTraceParent() {
    return `00-${this.traceId}-${this.spanId}-01`;
  }
}

export const traceStorage = new AsyncLocalStorage();

// Zero-overhead Structured Logger
export const logger = {
  info(message, extra = {}) {
    const ctx = traceStorage.getStore();
    const payload = {
      level: 'INFO',
      timestamp: new Date().toISOString(),
      message,
      trace_id: ctx ? ctx.traceId : null,
      span_id: ctx ? ctx.spanId : null,
      ...extra
    };
    process.stdout.write(JSON.stringify(payload) + '\n');
  },
  error(message, error, extra = {}) {
    const ctx = traceStorage.getStore();
    const payload = {
      level: 'ERROR',
      timestamp: new Date().toISOString(),
      message,
      trace_id: ctx ? ctx.traceId : null,
      span_id: ctx ? ctx.spanId : null,
      error_name: error?.name,
      error_message: error?.message,
      stack: error?.stack,
      ...extra
    };
    process.stderr.write(JSON.stringify(payload) + '\n');
  }
};

// HTTP Server Production Architecture
const server = http.createServer((req, res) => {
  // Parse incoming W3C traceparent (format: 00-traceid-spanid-flags)
  const incomingHeader = req.headers['traceparent'];
  let traceId = null;
  let parentId = null;

  if (incomingHeader && typeof incomingHeader === 'string') {
    const parts = incomingHeader.split('-');
    if (parts.length === 4 && parts[0] === '00') {
      traceId = parts[1];
      parentId = parts[2];
    }
  }

  const context = new TelemetryContext(traceId, null, parentId);
  context.setAttribute('http.method', req.method);
  context.setAttribute('http.url', req.url);

  traceStorage.run(context, () => {
    logger.info('Inbound HTTP Request Initiated');

    // Injeksi trace context ke response header
    res.setHeader('traceparent', context.toTraceParent());

    res.on('finish', () => {
      const durationNs = process.hrtime.bigint() - context.startTime;
      const durationMs = Number(durationNs) / 1e6;

      logger.info('Inbound HTTP Request Completed', {
        status_code: res.statusCode,
        duration_ms: durationMs,
        attributes: Object.fromEntries(context.attributes)
      });
    });

    // Simulasi routing dan asynchronous downstream call
    if (req.url === '/api/checkout' && req.method === 'POST') {
      executeCheckoutWorkflow()
        .then((result) => {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(result));
        })
        .catch((err) => {
          logger.error('Checkout processing failure', err);
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Internal Server Error' }));
        });
    } else {
      res.writeHead(404);
      res.end();
    }
  });
});

async function executeCheckoutWorkflow() {
  const ctx = traceStorage.getStore();
  logger.info('Executing database reservation');

  // Child Span Context Simulation
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < 0.05) {
        return reject(new Error('Database lock acquisition timeout'));
      }
      logger.info('Database reservation succeeded');
      resolve({ orderId: 'ord_' + randomBytes(4).toString('hex'), status: 'confirmed' });
    }, 120);
  });
}

server.listen(3000, () => {
  console.log('Production Telemetry Server running on port 3000');
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario:
Sistem *Payment Settlement Engine* skala enterprise milik platform e-commerce memproses 8.500 transaksi per detik (TPS). Pada jam sibuk, p99 latency melonjak dari 45ms ke 3.200ms secara intermittent, diikuti *container eviction* oleh Kubernetes karena *Out-Of-Memory (OOMKilled)*.

#### Investigasi & Diagnosis:
1. **Inspeksi Event Loop Delay**:
   - Tim merekam log via `monitorEventLoopDelay()`. Ditemukan lonjakan delay di atas 1.500ms yang terjadi tepat sebelum OOM crash.
2. **Sampling Profiler**:
   - Pod canary dijalankan dengan flag `--cpu-prof --cpu-prof-interval=500`.
   - File log `.cpuprofile` dianalisis menggunakan Chrome DevTools. Hasil Flame Graph membuktikan bahwa 68% total tick thread V8 terserap di method `deepCloneObject()` yang melakukan rekursi tak terbatas saat memproses payload transaksi dengan circular reference tersembunyi.
3. **Heap Profiling**:
   - Diambil *Heap Snapshot* saat memori mencapai 80% dari pod cgroup limits (`v8.writeHeapSnapshot()`).
   - Objek retainer menunjukkan bahwa trace context array pada custom logger framework tersimpan secara global tanpa batas retensi (*unbounded queue*), menahan referensi ribuan object Request payload yang tidak sempat di-*garbage collect*.

#### Remediasi Arsitektur:
1. **Optimasi Memory Leak**: Mengganti custom array logger dengan zero-allocation ring buffer yang secara berkala men-drain payload ke transport stream terpisah.
2. **CPU Bound Protection**: Mengganti implementasi `deepCloneObject()` buatan sendiri dengan `structuredClone()` native atau schema serialization biner via Protocol Buffers.
3. **Hasil**: Latensi p99 stabil kembali di rentang 28ms - 35ms pada 10.000 TPS, dan memory footprint per pod turun dari 1.8GB ke stabil di 240MB tanpa ancaman OOM.

---

### 9. Trade-offs

Setiap instrumen telemetri dan profiling memiliki konsekuensi teknis langsung terhadap eksekusi runtime:

```
                  [ TINGKAT OBSERVABILITAS ]
                             ▲
                             │        • Full Core Dump Analysis
                             │
                             │   • V8 Allocation Timeline
                             │
                             │ • Continuous Sampling Profiler (V8)
                             │
                             │ • OTel Tracing + ALS
                             │
                             │ • monitorEventLoopDelay & GC Stats
                             │
  ───────────────────────────┴─────────────────────────────►
  0%                      [ OVERHEAD RUNTIME ]             30%+
```

| Mekanisme | Keuntungan | Biaya & Trade-off | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **V8 Sampling Profiler (`--cpu-prof`)** | Visibilitas level machine code / line-of-code call stack. Tidak perlu modifikasi kode aplikasi. | Menghasilkan disk I/O kontinu jika dump ditulis ke disk; overhead CPU 2-5%. | Aktifkan hanya di canary pod, staging, atau via remote trigger (on-demand profiling). |
| **AsyncLocalStorage (ALS)** | Context propagation clean, bebas polusi parameter fungsi. | Overhead mikroalokasi context frame setiap Promise settlement (~5-8% throughput drop pada I/O padat). | Standar de-facto untuk trace ID propagation; hindari mutasi context di loop ketat. |
| **Heap Snapshots (`v8.writeHeapSnapshot`)** | Memetakan 100% memory graph secara presisi hingga level closure variable. | **STW (Stop-The-World)** fatal! Engine membekukan eksekusi JavaScript selama snapshot (bisa 2-15 detik pada heap besar). | **DILARANG KERAS** dieksekusi di master live production traffic; gunakan isolasi pod drain dulu. |
| **Active Handles Inspection (`process._getActiveHandles`)** | Mendeteksi leaking socket / unclosed descriptor. | Mengakses undocumented private API Node.js; linear scan array mengonsumsi V8 microtasks. | Gunakan hanya saat shutdown timeout debugging atau audit diagnostik berkala. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Mengambil Heap Snapshot Langsung di Production Service
* **Penyebab**: Developer mengeksekusi `v8.writeHeapSnapshot()` saat request HTTP handler error.
* **Dampak**: V8 membekukan seluruh event loop untuk mengiterasi pointer heap memory. Kubelet health-check (liveness probe) gagal merespons, mengakibatkan pod dibunuh paksa (*kill -9*) di tengah penulisan snapshot, merusak output dan memicu restart loop (CrashLoopBackOff).
* **Solusi**: Lepaskan pod dari upstream load balancer (service deregistration/drain traffic), biarkan idle, lalu eksekusi heap snapshot.

#### Mistake 2: Leaking Context pada AsyncLocalStorage
* **Penyebab**: Menyimpan referensi EventEmitter atau Stream jangka panjang (global) di dalam context ALS tanpa penghapusan eksplisit.
* **Gejala**: Memory Heap Old Space tumbuh secara linear sebanding dengan akumulasi request.
* **Solusi**: Pastikan ALS context hanya memuat data primitif atau referensi immutable (string Trace ID, Span ID, User ID) berukuran kecil.

#### Mistake 3: Overhead Serialization JSON Berulang pada Logger
* **Penyebab**: Melakukan `JSON.stringify()` pada objek payload berukuran puluhan megabyte secara sinkron di main thread sebelum dikirim ke log pipeline.
* **Gejala**: Lonjakan Event Loop Delay tajam tanpa utilisasi database yang tinggi.
* **Solusi**: Gunakan level logging yang terfilter (hanya debug saat non-prod), truncate string payload besar, atau serahkan serialisasi JSON ke Worker Thread.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist arsitektur ini sebelum merilis sistem Node.js ke lingkungan enterprise:

- [ ] **Instrumentasi Non-Blocking**: OTel Collector Exporter dikonfigurasi dengan mode async batching (`BatchSpanProcessor`) dan batas antrean buffer terukur (`maxQueueSize: 2048`).
- [ ] **Event Loop Guard**: Mengaktifkan `monitorEventLoopDelay()` dengan pelaporan alarm otomatis ke monitoring dashboard (misal: PagerDuty/Grafana jika p99 > 100ms selama 1 menit berturut-turut).
- [ ] **GC Metrics Monitoring**: Metrik Scavenge (Minor GC) dan Mark-Sweep-Compact (Major GC) terekspos untuk mendeteksi *GC Thrashing* sedini mungkin.
- [ ] **Context Sanitization**: State yang dimasukkan ke `AsyncLocalStorage` dibatasi maksimal < 1KB per transaksi dan bebas dari referensi circular.
- [ ] **Log Level Enforcement**: Log level produksi disetel ke `INFO` atau `WARN`. Engine serialisasi log wajib menggunakan fast streaming NDJSON (misal: Pino) bukan `console.log`.
- [ ] **Resource Termination Handlers**: Implementasi graceful shutdown timeout: tutup listener, tunggu drain in-flight request, unref active timers, lalu flush trace buffers sebelum `process.exit(0)`.
- [ ] **Profiling Safe Guards**: Dynamic remote profiling (via V8 Inspector Session) dilindungi dengan authn/authz token dan dibatasi maksimal durasi 60 detik per sesi sampling.

---

### 12. Hands-on Practice

Praktikum ini mensimulasikan pendeteksian bottleneck CPU dan integrasi telemetry monitoring. Simpan semua file dalam direktori `hands-on/m02/`.

#### Langkah 1: Persiapan Struktur Direktori
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
```

#### Langkah 2: Buat Profiler Worker Script (`hands-on/m02/profiler-server.js`)
Buat service yang memiliki dua rute: rute normal cepat dan rute CPU bottleneck tersembunyi (ReDoS/Algorithmic Complexity).

```javascript
// hands-on/m02/profiler-server.js
import http from 'node:http';
import { monitorEventLoopDelay } from 'node:perf_hooks';
import inspector from 'node:inspector';
import fs from 'node:fs';

const elHistogram = monitorEventLoopDelay({ resolution: 10 });
elHistogram.enable();

// Engine Pembuat CPU-Bound Bottleneck Tersembunyi
function computeVulnerableRegex(input) {
  // Vulnerable pattern: Polynomial regular expression matching
  const regex = /^(a+)+$/;
  return regex.test(input);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (url.pathname === '/fast') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', duration: 'sub-millisecond' }));
    return;
  }

  if (url.pathname === '/compute') {
    const payload = url.searchParams.get('data') || 'aaaaaaaaaaaaaaaaaaaaaaaaaaaa!';
    const start = process.hrtime.bigint();
    
    // Memicu CPU overhead tinggi
    const match = computeVulnerableRegex(payload);
    
    const diff = Number(process.hrtime.bigint() - start) / 1e6;
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ match, execution_ms: diff }));
    return;
  }

  if (url.pathname === '/metrics') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      loop_delay_p50: (elHistogram.percentile(50) / 1e6).toFixed(2),
      loop_delay_p99: (elHistogram.percentile(99) / 1e6).toFixed(2),
      loop_delay_max: (elHistogram.max / 1e6).toFixed(2)
    }));
    return;
  }

  // Trigger Profiling secara Terprogram
  if (url.pathname === '/profile') {
    const session = new inspector.Session();
    session.connect();

    session.post('Profiler.enable', () => {
      session.post('Profiler.start', () => {
        console.log('[PROFILER] Sesi sampling CPU V8 dimulai...');
        
        setTimeout(() => {
          session.post('Profiler.stop', (err, { profile }) => {
            if (!err) {
              fs.writeFileSync('./v8-cpu-profile.cpuprofile', JSON.stringify(profile));
              console.log('[PROFILER] Snapshot tersimpan di v8-cpu-profile.cpuprofile');
            }
            session.disconnect();
          });
        }, 5000); // Record selama 5 detik
      });
    });

    res.writeHead(202, { 'Content-Type': 'text/plain' });
    res.end('Profiling session started for 5 seconds.');
    return;
  }

  res.writeHead(404);
  res.end();
});

server.listen(4000, () => {
  console.log('Telemetry Lab running on port 4000 (PID: ' + process.pid + ')');
});
```

#### Langkah 3: Eksekusi dan Pengujian Diagnostik
Jalankan server:
```bash
node hands-on/m02/profiler-server.js
```

Buka terminal kedua dan kirim request normal:
```bash
curl http://localhost:4000/fast
curl http://localhost:4000/metrics
```

Mulai perekaman CPU Profile via endpoint:
```bash
curl http://localhost:4000/profile
```

Seketika itu juga, kirim beban request yang memicu ReDoS:
```bash
curl "http://localhost:4000/compute?data=aaaaaaaaaaaaaaaaaaaaaaaaaa!"
```

Periksa metrik Event Loop Delay:
```bash
curl http://localhost:4000/metrics
```

Analisis hasil:
- Ambil file `hands-on/m02/v8-cpu-profile.cpuprofile`.
- Buka browser Chrome, akses `chrome://inspect`.
- Klik **Open dedicated DevTools for Node**, pilih tab **Profiler**, klik kanan -> **Load profile**, dan telusuri Flame Graph.
- Perhatikan bagaimana fungsi `computeVulnerableRegex` mendominasi lebar grafik (call stack percentage > 90%).

---

### 13. Exercise

#### Level: Easy
Buat skrip `telemetry-filter.js`. Implementasikan fungsi `sanitizeHeaders(headers)` yang bertugas menerima objek header HTTP mentah dan menghasilkan deep copy terfilter, di mana kunci-kunci sensitif (`authorization`, `cookie`, `x-api-key`) diganti nilainya dengan string `[REDACTED]`. Fungsi harus aman dari case-insensitive header names tanpa menyebabkan duplikasi alokasi memory yang berlebihan.

#### Level: Medium
Implementasikan class `EventLoopWatchdog`. Watchdog ini harus mengukur keterlambatan loop setiap interval 500ms menggunakan timer murni (`setInterval` vs `process.hrtime.bigint()`). Jika perbedaan waktu aktual melebihi expected delay lebih dari ambang batas 150ms selama 3 siklus berturut-turut, picu custom event `eventLoopBlocked` dengan data durasi blockage dan snapshot ringkasan status memori (`process.memoryUsage()`).

#### Level: Hard
Rancang modul `DistributedContextSpan` menggunakan `node:async_hooks` murni (tanpa dependensi `AsyncLocalStorage` high-level). Modul Anda harus mampu:
1. Mengaitkan objek context `{ spanId, parentId, baggage }` ke setiap execution async context via internal `AsyncWrap`.
2. Secara deterministik menghancurkan mapping data pada internal map saat event `destroy(asyncId)` terpanggil oleh V8 garbage collector untuk mencegah memory leak.
3. Mendukung skenario nested execution context dengan pewarisan context parent yang benar.

---

### 14. Challenge

**Skenario**: Anda adalah Staff Principal Systems Engineer pada sebuah bank digital. Sistem API Gateway berbasis Node.js yang melayani 20.000 RPS mengalami degradasi performa: latensi p999 meningkat drastis hingga 4.000ms setiap 15 menit, namun utilisasi CPU host server hanya 22%. Tim menduga ada kombinasi antara:
1. Microtask starvation (terlalu banyak `process.nextTick` atau unhandled recursive Promise chains).
2. Thrashing pada New Space Garbage Collection akibat alokasi buffer temporer berukuran sedang secara masif.
3. Event loop blocked oleh blocking I/O terselubung (misalnya pembacaan sertifikat SSL secara sinkron di tengah request flow).

**Tantangan**:
Rancang arsitektur telemetri mandiri (in-process diagnostic agent) tanpa dependensi eksternal berat (pure native Node.js APIs) yang dapat:
- Mendeteksi secara mandiri kondisi saat anomali latensi p999 mulai terbentuk (early warning threshold).
- Mengambil **CPU Profile** sepanjang 3 detik secara non-blocking dan otomatis mengekstrak 3 nama fungsi teratas (top offenders) yang menyita waktu eksekusi.
- Mengumpulkan histogram breakdown Garbage Collection (durasi dan frekuensi Scavenge vs Mark-Sweep).
- Mengunggah payload diagnostik ringkas tersebut dalam format JSON terstruktur ke endpoint audit eksternal, lalu membersihkan semua buffer diagnostik untuk mencegah memory bloat.

*Buktikan arsitektur Anda dapat berjalan dengan overhead memori statis < 15MB dan overhead throughput CPU < 1.5% pada kondisi traffic puncak.*

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic:
1. Mengapa metode *Sampling Profiler* lebih direkomendasikan untuk analisis performa di lingkungan production dibandingkan *Instrumentation Profiler*?
2. Apa perbedaan mendasar antara metrik *CPU Usage* dengan *Event Loop Delay* pada Node.js runtime?
3. Sebutkan risiko teknis utama mengeksekusi `v8.writeHeapSnapshot()` secara sinkron pada container produksi yang sedang aktif menerima traffic!
4. Apa fungsi dari parameter `resolution` saat menginisialisasi `monitorEventLoopDelay({ resolution })`?
5. Mengapa format log berbasis NDJSON (Newline Delimited JSON) lebih disukai daripada human-readable text logs biasa untuk ingest pipeline observability?

#### Pertanyaan Intermediate:
6. Bagaimana cara kerja internal `AsyncLocalStorage` mengaitkan context transaksi di antara pemanggilan callback berbasis asynchronous I/O?
7. Jelaskan bagaimana algoritma HdrHistogram pada `perf_hooks` mampu mencatat distribusi latensi mikrodetik secara akurat tanpa memicu overhead alokasi memori yang tinggi!
8. Pada skenario apa penanganan tracing context menggunakan header W3C `traceparent` dapat mengalami "broken trace context chain" di Node.js?
9. Apa perbedaan dampak performa antara fase Garbage Collection *Scavenge* (Scavenger) dan *Mark-Sweep-Compact* terhadap throughput transaksi?
10. Mengapa eksekusi microtask queue (`process.nextTick` dan resolved Promise) yang tak terkontrol dapat membekukan *macrotask phases* (seperti I/O dan Timers) pada Libuv?

#### Skenario Kasus Produksi:
11. **Skenario 1**: Sebuah container Node.js menunjukkan lonjakan tajam pada metrik `external` memori di `process.memoryUsage()`, sementara `heapUsed` tetap stabil di angka 100MB. Apakah ini memory leak JavaScript biasa? Bagaimana Anda mengidentifikasi sumber masalahnya?
12. **Skenario 2**: Setelah menambahkan OpenTelemetry SDK dengan `auto-instrumentations-node` pada layanan monolitik besar, latensi p99 meningkat sebesar 18% dan RPS menurun sebesar 25%. Langkah profiling dan isolasi apa yang harus Anda lakukan untuk menemukan plugin instrumentasi yang bermasalah?
13. **Skenario 3**: Log produksi Anda mendadak memunculkan ribuan Trace ID yang bernilai `null` atau `undefined` khusus pada request yang melibatkan streaming data berukuran besar menggunakan `stream.pipeline` atau `Transform` streams. Mengapa context ALS bisa hilang di tengah stream lifecycle dan bagaimana solusinya?

---

### 16. Summary

1. **Prinsip Dasar Observabilitas Node.js**: Memahami performa Node.js menuntut pemantauan dua pilar utama secara simultan: efisiensi V8 Engine (eksekusi JavaScript & alokasi Heap) dan kelancaran Libuv Event Loop (antrean task & delay phase).
2. **Korelasi Terdistribusi**: Menggunakan W3C Trace Context bersama `AsyncLocalStorage` memungkinkan rekonstruksi lintasan request end-to-end melintasi batas mikroservis tanpa merusak kebersihan kode application layer.
3. **Sampling vs Stop-The-World**: Profiling produksi harus selalu mengutamakan sampling probabilistik non-blocking (V8 CPU Profiler, event loop sampling). Tindakan invasif seperti full Heap Snapshot hanya boleh dilakukan pada pod yang telah terisolasi dari live traffic.
4. **Zero-Allocation Telemetry**: Arsitektur telemetri yang andal tidak boleh memperburuk performa sistem yang sedang dipantaunya. Menggunakan ring buffer, batching asynchronous, dan serialisasi data yang terukur adalah kunci mencapai overhead performa sub-persen.