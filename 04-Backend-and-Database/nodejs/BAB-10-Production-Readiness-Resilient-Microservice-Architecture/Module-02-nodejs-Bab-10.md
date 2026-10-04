# BAB 10: Production Readiness & Resilient Microservice Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai perancangan arsitektur microservices berbasis Node.js yang memiliki ketahanan tinggi (*high resilience*) terhadap kegagalan parsial (*cascading failures*).
- Mengimplementasikan pola arsitektur *fault tolerance* tingkat lanjut: *Circuit Breaker*, *Bulkhead*, *Rate Limiting*, *Retry with Exponential Backoff & Jitter*, serta *Graceful Degradation*.
- Memahami dan mengonfigurasi siklus hidup proses Node.js di lingkungan orkestrasi container (Kubernetes/ECS), termasuk propagasi POSIX *signals* (`SIGTERM`, `SIGINT`), *connection draining*, serta desain *probe* liveness/readiness yang deterministik.
- Membangun *observability stack* komprehensif menggunakan OpenTelemetry untuk *distributed tracing*, metrik *runtime* Node.js (V8 heap, Libuv event loop delay), dan *structured logging* berkorelasi.
- Mengidentifikasi, mengisolasi, dan memitigasi kegagalan kritis di tingkat kernel, event loop, dan dependensi I/O downstream.

---

### 2. Prerequisite
Untuk mencerna materi ini secara optimal, peserta wajib memahami:
- Arsitektur internal runtime Node.js: Event Loop, Libuv Thread Pool, dan V8 Garbage Collection mechanics.
- Protokol komunikasi HTTP/1.1, HTTP/2, gRPC, serta transport layer TCP (handshake, connection pooling, socket lifecycle).
- Dasar-dasar containerization (Docker) dan prinsip orkestrasi Kubernetes (Pods, Services, Lifecycle Hooks).
- Pengalaman menulis aplikasi modular Node.js menggunakan TypeScript atau Modern JavaScript (ES2022+).

---

### 3. Concept & Internal Architecture

Dalam arsitektur *distributed systems*, microservice Node.js beroperasi dalam model *single-threaded event-driven concurrency*. Karakteristik ini memberikan efisiensi I/O tinggi, namun sangat rentan terhadap dua vektor kegagalan utama:
1. **Event Loop Starvation:** Pemrosesan komputasi sinkron atau penanganan *parsing* payload masif yang memblokir alokasi siklus CPU, menghentikan pemrosesan I/O lain, dan menyebabkan *health check timeout*.
2. **Cascading Failure akibat Downstream Latency:** Kegagalan atau degradasi performa pada layanan downstream (database, payment gateway, microservice lain) yang menyebabkan penumpukan TCP socket yang menggantung (*hanging sockets*), memory bloat pada *buffer* V8, dan kehabisan *file descriptors*.

```
+--------------------------------------------------------------------------------+
|                             NODE.JS PROCESS LIFECYCLE                          |
+--------------------------------------------------------------------------------+
|                                                                                |
|  POSIX Signal (SIGTERM)                                                        |
|         │                                                                      |
|         ▼                                                                      |
|  [process.on('SIGTERM')] ──► Mark Service UNREADY (/readyz -> 503)             |
|         │                                                                      |
|         ├──────────────────► Sleep preStop Delay (e.g. 5s-15s for Ingress sync)|
|         │                                                                      |
|         ├──────────────────► server.close() (Stop accepting new TCP connections)|
|         │                                                                      |
|         ├──────────────────► Drain Active In-Flight Requests (with Timeout)    |
|         │                                                                      |
|         ├──────────────────► Close DB Pools, Redis, Message Broker Consumers   |
|         │                                                                      |
|         ▼                                                                      |
|  [process.exit(0)]                                                             |
|                                                                                |
+--------------------------------------------------------------------------------+
```

#### A. Mekanisme Sinyal POSIX dan Kubernetes Termination
Ketika pod dijadwalkan untuk terminasi (akibat *rolling update*, *auto-scaling*, atau *node drain*):
1. API Server Kubernetes menandai Pod sebagai `Terminating` dan menghapusnya dari Endpoint/Kube-Proxy target (Ingress berhenti mengarahkan traffic baru).
2. Kubelet mengirimkan sinyal `SIGTERM` ke PID 1 di container.
3. Kubelet menunggu hingga batas `terminationGracePeriodSeconds` (default: 30 detik). Jika proses belum mati, `SIGKILL` dikirimkan secara paksa ke OS kernel, menghentikan proses seketika dan memotong transaksi yang sedang berjalan.
4. **Masalah Race Condition:** Propagasi iptables/IPVS di seluruh cluster membutuhkan waktu sekian milidetik hingga beberapa detik. Jika aplikasi Node.js langsung mengeksekusi `server.close()` tepat saat menerima `SIGTERM`, request in-flight yang dikirim oleh Ingress dalam jendela propagasi tersebut akan menerima error `502 Bad Gateway` (*connection refused*).

#### B. Circuit Breaker State Machine
Pola Circuit Breaker mencegah aplikasi menghabiskan sumber daya (thread pool Libuv, memory buffer, socket pool) untuk memanggil dependensi yang sedang tidak responsif.

State Machine terdiri dari 3 kondisi:
- **CLOSED:** Kondisi normal. Semua request dialirkan ke downstream. Metrik kegagalan (HTTP 5xx, timeout) diukur dalam *sliding window*.
- **OPEN:** Tingkat kegagalan melewati ambang batas (*threshold*). Request downstream diputus seketika (*fail-fast*) tanpa melakukan I/O network, langsung mengembalikan respons *fallback* atau error deklaratif.
- **HALF-OPEN:** Setelah *cooldown period* terlewati, sejumlah kecil request uji coba (*canary probes*) diperbolehkan lewat. Jika sukses, status kembali ke `CLOSED`. Jika gagal, sirkuit kembali ke status `OPEN`.

---

### 4. Why & What

| Dimensi | Pendekatan Monolitik Tradisional / Naif | Resilient Enterprise Microservice |
| :--- | :--- | :--- |
| **Error Propagation** | Error downstream memicu timeout cascading, mengunci resource hingga crash global. | Kegagalan diisolasi oleh *Circuit Breaker* & *Bulkhead*; degradasi elegan (*fallback*). |
| **Termination Lifecycle** | Aplikasi dimatikan paksa via `SIGKILL` atau exit instan; koneksi DB putus tak beraturan (*dangling state*). | *Graceful shutdown* deterministik dengan TCP draining, flush tracing data, dan cleanup resource. |
| **Traffic Overload** | Menerima seluruh traffic hingga *out of memory* (OOM) atau event loop macet total. | *Token bucket* rate-limiting terdistribusi dan *adaptive load shedding* berbasis event loop delay. |
| **Observability** | Log teks tidak terstruktur di `stdout`, *siloed tracking*, sulit merekonstruksi insiden multi-service. | *OpenTelemetry distributed tracing*, metrik V8/Libuv, dan *contextual logging* terinjeksi Trace ID & Span ID. |

---

### 5. How (Workflow Detail)

Alur penanganan dependensi I/O berstatus *mission-critical*:

1. **Ingress Phase:**
   - Request masuk via Reverse Proxy / API Gateway.
   - Node.js memvalidasi *Event Loop Lag*. Jika lag melebihi ambang batas toleransi (misal: > 150ms), aktifkan *load shedding* (HTTP 503 / 429) untuk melindungi integritas internal engine.
2. **Context Propagation Phase:**
   - Ekstraksi `traceparent` W3C headers via OpenTelemetry API.
   - Buat span eksekusi baru dan tautkan ke *AsyncLocalStorage* untuk konteks logging global.
3. **Downstream Execution Phase:**
   - Request dieksekusi melalui layer *Bulkhead* (membatasi konkurensi maksimum ke resource tertentu).
   - Masuk ke layer *Circuit Breaker*. Jika sirkuit `OPEN`, lempar exception atau eksekusi *fallback* instan.
   - Jika sirkuit `CLOSED`, kirim payload dengan *timeout* strict (misal: 1500ms) menggunakan *Keep-Alive HTTP Agent* yang terisolasi.
   - Terapkan *Exponential Backoff* dengan *Full Jitter* untuk request berkarakteristik idempoten:
     $$\text{Sleep} = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$
4. **Egress/Clean-up Phase:**
   - Metrik durasi dan status direkam ke Prometheus sink via OpenTelemetry Collector.
   - Span ditutup (*span.end()*).

---

### 6. Analogy & Diagram ASCII

#### Circuit Breaker State Transition & Graceful Teardown Flow

```
                      CIRCUIT BREAKER STATE ENGINE
                      
     +-------------------------------------------------------+
     |                                                       |
     |                     [ CLOSED ]                        |
     |                   (Normal Traffic)                    |
     |                          │                            |
     +──────────────────────────┼────────────────────────────+
               Failure Rate >   │   ▲
               Threshold (%)    │   │ Canary Requests
                                │   │ Succeed
                                ▼   │
     +──────────────────────────┬───┴────────────────────────+
     |                          │                            |
     |                          │    Timeout Elapsed         |
     |        [ OPEN ] ─────────┴──► [ HALF-OPEN ]           |
     |    (Fast-Fail Mode)            (Canary Probes)        |
     |         │                            │                |
     +─────────┼────────────────────────────┼────────────────+
               ▲                            │
               └────────────────────────────┘
                   Canary Request Fails
```

```
                   ZERO-DOWNTIME SHUTDOWN TIMELINE
                   
[Kubernetes Kubelet]         [Ingress / Endpoints]        [Node.js Process]
        │                             │                         │
        │─── Pod Deletion Event ─────►│                         │
        │                             │── Update iptables... ──►│
        │─── SIGTERM ──────────────────────────────────────────►│
        │                                                       │ (Active /readyz -> 503)
        │                                                       │ 
        │                   [ Propagation Window (e.g. 5s) ]    │ (Still serving existing
        │                   (New traffic stops routing here)    │  and straggler requests)
        │                                                       │
        │                                                       │── server.close()
        │                                                       │── Drain DB Connections
        │                                                       │── Flush OTel Spans
        │                                                       │── process.exit(0)
        │◄── Pod Container Terminated ──────────────────────────│
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Native HTTP Graceful Shutdown & Unhandled Rejection Trap

```javascript
// simple-resilience.mjs
import http from 'node:http';
import process from 'node:process';

const server = http.createServer((req, res) => {
  if (req.url === '/healthz') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ status: 'UP' }));
  }

  // Simulasi beban I/O
  setTimeout(() => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ message: 'Execution complete' }));
  }, 200);
});

server.listen(3000, () => {
  console.log('Instance active on port 3000');
});

// Penanganan anomali fatal tanpa recovery
function handleFatalCrash(error, origin) {
  console.error(`Fatal crash detected at ${origin}:`, error);
  // Fail-fast: Jangan biarkan node berjalan dalam kondisi state korup
  process.exit(1);
}

process.on('uncaughtException', (err) => handleFatalCrash(err, 'uncaughtException'));
process.on('unhandledRejection', (reason) => handleFatalCrash(reason, 'unhandledRejection'));

// Siklus teardown sinyal POSIX
function shutdown(signal) {
  console.log(`Received ${signal}. Initiating termination sequence...`);
  
  server.close((err) => {
    if (err) {
      console.error('Error during HTTP adapter closure:', err);
      process.exit(1);
    }
    console.log('HTTP network listeners drained successfully. Exiting.');
    process.exit(0);
  });

  // Force-kill watchdog timeout
  setTimeout(() => {
    console.error('Termination grace period exceeded. Forcing termination.');
    process.exit(1);
  }, 10000).unref(); // unref() agar timer ini tidak menahan event loop jika drain selesai cepat
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
```

#### Practical Example: Production-Grade Resilient Microservice Framework

Implementasi lengkap menggunakan Fastify, Brakes/Cockatiel Circuit Breaker, OpenTelemetry Tracing, dan Lifecycle State Management.

```typescript
// src/server.ts
import fastify, { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { CircuitBreakerPolicy, ConsecutiveBreaker, handleAll, retry, wrap } from 'cockatiel';
import { trace, context, SpanStatusCode } from '@opentelemetry/api';
import process from 'node:process';
import { setTimeout as sleep } from 'node:timers/promises';

// --- CONFIGURATION & STATE FLAGS ---
interface AppState {
  isShuttingDown: boolean;
  isReady: boolean;
  activeRequests: number;
}

const state: AppState = {
  isShuttingDown: false,
  isReady: true,
  activeRequests: 0,
};

const tracer = trace.getTracer('payment-microservice', '1.0.0');

// --- CIRCUIT BREAKER & RETRY POLICY SETUP ---
// Isolasi circuit breaker: Buka circuit jika 3 kegagalan berurutan, cooldown 10 detik
const breakerPolicy = CircuitBreakerPolicy.builder(handleAll)
  .handleResult(res => res === false)
  .setThreshold(new ConsecutiveBreaker(3))
  .setHalfOpenAfter(10_000)
  .build();

const retryPolicy = retry(handleAll, {
  maxAttempts: 3,
  backoff: 'exponential',
  initialDelay: 200,
  maxDelay: 2000,
});

// Komposisi: Retry terlebih dahulu, dipantau oleh Circuit Breaker
const resilientPipeline = wrap(breakerPolicy, retryPolicy);

breakerPolicy.onBreak(() => console.warn('[CIRCUIT] Alert: Circuit Breaker OPEN! Traffic fast-failing.'));
breakerPolicy.onReset(() => console.info('[CIRCUIT] Info: Circuit Breaker CLOSED. Operations normalized.'));
breakerPolicy.onHalfOpen(() => console.info('[CIRCUIT] Info: Circuit Breaker HALF-OPEN. Probing downstream.'));

// --- DEPENDENCY CLIENT SIMULATOR ---
async function callDownstreamPaymentGateway(transactionId: string): Promise<boolean> {
  const currentSpan = trace.getActiveSpan();
  
  return await resilientPipeline.execute(async () => {
    // Simulasi flaky downstream service
    const latency = Math.floor(Math.random() * 300);
    await sleep(latency);

    const isFailure = Math.random() < 0.4; // 40% failure rate
    if (isFailure) {
      currentSpan?.addEvent('downstream_failure_detected', { transactionId });
      throw new Error('Downstream 500 Internal Gateway Error');
    }

    return true;
  });
}

// --- SERVER INSTANTIATION ---
export function buildServer(): FastifyInstance {
  const app = fastify({
    logger: {
      level: 'info',
      formatters: {
        log(object) {
          const activeSpan = trace.getActiveSpan();
          if (activeSpan) {
            const { traceId, spanId } = activeSpan.spanContext();
            return { ...object, traceId, spanId };
          }
          return object;
        }
      }
    },
    disableRequestLogging: false,
  });

  // Track In-Flight Requests
  app.addHook('onRequest', async (req, reply) => {
    state.activeRequests++;
  });

  app.addHook('onResponse', async (req, reply) => {
    state.activeRequests--;
  });

  // Kubernetes Probes
  app.get('/livez', async (req: FastifyRequest, reply: FastifyReply) => {
    // Liveness mengecek apakah runtime hidup. Jangan bergantung pada DB luar.
    return reply.status(200).send({ status: 'alive' });
  });

  app.get('/readyz', async (req: FastifyRequest, reply: FastifyReply) => {
    // Readiness menentukan apakah pod siap menerima traffic
    if (state.isShuttingDown || !state.isReady) {
      return reply.status(503).send({ status: 'terminating', activeRequests: state.activeRequests });
    }
    return reply.status(200).send({ status: 'ready' });
  });

  // Core Business Route
  app.post('/api/v1/checkout', async (req: FastifyRequest, reply: FastifyReply) => {
    const parentSpan = tracer.startSpan('HTTP POST /api/v1/checkout');

    return await context.with(trace.setSpan(context.active(), parentSpan), async () => {
      try {
        const { transactionId } = req.body as { transactionId: string };
        parentSpan.setAttribute('app.transaction.id', transactionId);

        // Eksekusi downstream terproteksi
        const success = await callDownstreamPaymentGateway(transactionId);

        parentSpan.setStatus({ code: SpanStatusCode.OK });
        return reply.status(200).send({ success, transactionId });
      } catch (error: any) {
        parentSpan.recordException(error);
        parentSpan.setStatus({
          code: SpanStatusCode.ERROR,
          message: error.message || 'Execution error'
        });

        if (error.name === 'BrokenCircuitError') {
          // Graceful degradation fallback
          app.log.error('Circuit open. Applying degraded fallback response.');
          return reply.status(503).send({
            error: 'Service Degraded',
            message: 'Payment provider unavailable. Request queued for batch reconciliation.',
            fallbackApplied: true
          });
        }

        return reply.status(500).send({ error: 'Checkout Failed', detail: error.message });
      } finally {
        parentSpan.end();
      }
    });
  });

  return app;
}

// --- INITIALIZATION & GRACEFUL TEARDOWN CONTROLLER ---
const server = buildServer();
const PORT = Number(process.env.PORT) || 8080;

server.listen({ port: PORT, host: '0.0.0.0' }, (err, address) => {
  if (err) {
    server.log.fatal(err);
    process.exit(1);
  }
  server.log.info(`Microservice node active on ${address}`);
});

async function initiateGracefulShutdown(signal: string) {
  server.log.warn(`Signal [${signal}] intercepted. Commencing graceful teardown...`);

  // 1. Matikan readiness flag seketika
  state.isReady = false;
  state.isShuttingDown = true;

  // 2. Tunda proses (Delay) untuk memberikan jendela propagasi unregistration Ingress k8s
  const INGRESS_PROPAGATION_MS = parseInt(process.env.PRE_STOP_DELAY_MS || '5000', 10);
  server.log.info(`Suspending termination for ${INGRESS_PROPAGATION_MS}ms for endpoint sync...`);
  await sleep(INGRESS_PROPAGATION_MS);

  // 3. Set Watchdog force exit timer (Dead Man's Switch)
  const TERMINATION_TIMEOUT_MS = 20000;
  const forceKillTimer = setTimeout(() => {
    server.log.fatal('Graceful drain timeout reached. Enforcing emergency process kill.');
    process.exit(1);
  }, TERMINATION_TIMEOUT_MS).unref();

  // 4. Tutup listener HTTP (Mencegah traffic masuk baru)
  try {
    await server.close();
    server.log.info('HTTP listener successfully suspended.');

    // 5. Drain Active Connections / Storage Pools / Flush OTel
    server.log.info(`Awaiting completion of ${state.activeRequests} active transactions...`);
    while (state.activeRequests > 0) {
      await sleep(250);
    }

    server.log.info('All pending requests fully satisfied. Clean teardown complete.');
    clearTimeout(forceKillTimer);
    process.exit(0);
  } catch (error) {
    server.log.error(`Exception triggered during teardown: ${error}`);
    process.exit(1);
  }
}

process.on('SIGTERM', () => initiateGracefulShutdown('SIGTERM'));
process.on('SIGINT', () => initiateGracefulShutdown('SIGINT'));
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Insiden Cascading Timeout Core Banking Gateway (PT Transaksi Finansial Nusantara)

* **Skala Sistem:** 45 microservices Node.js, 18.000 RPS peak, klaster Kubernetes bare-metal (350 worker nodes).
* **Insiden:**
  Saat *Payday Flash Sale* pukul 00:00, salah satu downstream Core Banking (Third-party Legacy SOAP Engine) mengalami degradasi response time dari 80ms menjadi 12.000ms.
* **Mekanisme Kegagalan (*Domino Effect*):**
  1. Microservice API Gateway Node.js tidak memiliki konfigurasi timeout I/O yang ketat (`http.Agent` memakai default OS socket timeout: ~120 detik).
  2. Pool socket TCP Gateway penuh menahan koneksi gantung (*hanging sockets*).
  3. Memori V8 heap Gateway melonjak karena menampung object callback closure dari ribuan asynchronous promise yang terisolasi menunggu balasan.
  4. Node.js Libuv thread pool terbebani parsing DNS resolver secara berulang.
  5. Event loop delay melonjak dari 2ms ke 450ms.
  6. Endpoint `/healthz` Gateway gagal merespons liveness probe Kubernetes dalam durasi 1000ms.
  7. Kubelet membunuh (*restarted*) pod secara massal. Begitu pod baru *spin up*, pod langsung dihantam traffic antrean yang masif dan seketika OOMKilled kembali (*death spiral*). Total downtime: 42 menit. Kerugian reputasi dan finansial masif.

* **Solusi Rekayasa:**
  1. **Strict Context Timings:** Menerapkan pembatasan timeout downstream absolut maksimum 1500ms menggunakan `AbortController`.
  2. **Circuit Breaker:** Memasang Cockatiel Circuit Breaker dengan ambang batas kegagalan 15%. Begitu Core Banking lambat, sirkuit membuka seketika; Gateway langsung mengembalikan respons `HTTP 424 Failed Dependency` atau fallback *asynchronous processing* via Apache Kafka.
  3. **Probe Decoupling:** Memisahkan endpoint Kubernetes:
     - `/livez` murni mengembalikan status 200 via memory flag instan (hanya mati jika event loop macet permanen).
     - `/readyz` mengevaluasi event loop lag dan status dependency.
  4. **Pod Disruption & Grace Period Tuning:** Menerapkan `terminationGracePeriodSeconds: 60` dengan `preStop` container lifecycle hook yang memanggil script sleep 10 detik sebelum melepaskan proses.

---

### 9. Trade-offs

```
+-----------------------------------------------------------------------------------------+
|                                ARCHITECTURAL TRADE-OFFS                                 |
+------------------------------------+----------------------------------------------------+
| CIRCUIT BREAKER & FAST-FAIL        | RETRIES WITH JITTER                                |
| Pro: Mencegah saturasi resource    | Pro: Menghilangkan intermittent transient error    |
| Con: User mendapati partial failure| Con: Meningkatkan beban ke sistem yang sedang sakit|
+------------------------------------+----------------------------------------------------+
| OPENTELEMETRY TRACING IN-DEPTH     | EVENT LOOP AGILITY                                 |
| Pro: Observability transparan      | Pro: Throughput tinggi                             |
| Con: CPU overhead 3-8% & memori    | Con: Rawan degradasi jika instrumentation tracing  |
|      alokasi span di V8 heap       |      melakukan parsing context berlebihan           |
+------------------------------------+----------------------------------------------------+
```

- **Aggressive Timeouts vs False Positives:** Timeout yang terlalu pendek (< 500ms) pada jaringan cloud multi-tenant dapat memicu *false positive* kegagalan network hop, menyebabkan pemutusan transaksi valid.
- **Fail-Fast vs Eventual Consistency:** Pola graceful degradation sering mengharuskan fallback ke antrean asynchronous (Kafka/RabbitMQ). Ini menuntut arsitektur membaca data secara *eventually consistent*, menambah kompleksitas di layer frontend UI/UX.

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Dependency Checking di Liveness Probe
```typescript
// ANTI-PATTERN: Salah fatal! Menghubungkan Liveness Probe dengan DB eksternal
app.get('/livez', async (req, reply) => {
  const dbAlive = await checkDatabasePing(); // JIKA DB MATI, SELURUH POD DIBUNUH K8S!
  if (!dbAlive) return reply.status(500).send();
  return reply.status(200).send();
});

// BEST PRACTICE: Liveness probe hanya memverifikasi alur internal Node.js runtime
app.get('/livez', (req, reply) => {
  // Hanya pastikan node.js event loop masih mampu memproses callback
  reply.status(200).send({ status: 'ok' });
});
```

#### Mistake 2: Membiarkan Event Loop Lag Tanpa Proteksi Load Shedding
Ketika Node.js menerima beban berlebih, response time melambat secara eksponensial. Lakukan mitigasi proaktif:
```typescript
import { monitorEventLoopDelay } from 'node:perf_hooks';

const histogram = monitorEventLoopDelay({ resolution: 20 });
histogram.enable();

app.addHook('onRequest', async (req, reply) => {
  // 99th percentile delay dalam nanodetik -> konversi ke milidetik
  const p99LagMs = histogram.percentile(99) / 1e6;
  
  if (p99LagMs > 100) { // Jika lag > 100ms, tolak request baru
    reply.header('Retry-After', 2);
    return reply.status(503).send({
      error: 'Load Shedding Active',
      message: 'Node compute capacity temporarily saturated.'
    });
  }
});
```

#### Mistake 3: Memory Leak pada Unhandled Promise Rejection
Menggunakan empty handler `process.on('unhandledRejection', () => {})` untuk "mencegah crash" adalah anti-pattern fatal. State memori aplikasi menjadi tidak terprediksi (*inconsistent internal state*). Pendekatan yang benar adalah melakukan logging diagnostik lalu menghentikan proses secara terukur (*fail-fast & let orchestrator revive*).

---

### 11. Best Practices (Production Checklist)

1. [ ] **Process Handling:** Pastikan process tidak dijalankan langsung sebagai PID 1 tanpa init system (gunakan `tini` atau `dumb-init` dalam Dockerfile untuk forward sinyal POSIX dengan benar).
2. [ ] **Lifecycle Separation:** Implementasikan endpoint `/livez` (proses hidup) dan `/readyz` (siap terima traffic) secara modular dan terpisah.
3. [ ] **PreStop Hook:** Berikan sleep hook di konfigurasi pod deployment Kubernetes (`lifecycle.preStop.exec.command: ["sleep", "10"]`) sebelum mengirimkan `SIGTERM`.
4. [ ] **Draining Grace Period:** Atur `terminationGracePeriodSeconds` lebih besar daripada akumulasi `preStop sleep` + `server.close() timeout`.
5. [ ] **Circuit Breaker:** Konfigurasikan Circuit Breaker dan Timeout pada seluruh HTTP Client, gRPC Stub, dan Query Database.
6. [ ] **Observability Trace Injection:** Pastikan seluruh out-going HTTP call menginjeksikan header W3C (`traceparent`) secara otomatis.
7. [ ] **V8 Heap Constraints:** Konfigurasikan flag `--max-old-space-size` bernilai 75-80% dari total batas limit memory container pod untuk mencegah *abrupt Linux OOM killer invocation*.
8. [ ] **Keep-Alive Sockets:** Konfigurasikan `keepAlive: true` dan daur ulang connection pool melalui custom `http.Agent` untuk mengeliminasi overhead *TCP handshake*.

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum ini pada direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Environment
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm init -y
npm install fastify cockatiel @opentelemetry/api @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node
npm install --save-dev typescript @types/node tsx
npx tsc --init
```

#### Langkah 2: Buat Entry Point Microservice Resilien
Buat file `hands-on/m02/resilient-app.ts` menggunakan implementasi dari sub-bab **7. Practical Example**.

#### Langkah 3: Verifikasi Perilaku Circuit Breaker & Graceful Shutdown
Jalankan microservice:
```bash
npx tsx resilient-app.ts
```

Buka terminal kedua, tembakkan request intensif untuk memicu Circuit Breaker:
```bash
for i in {1..20}; do
  curl -X POST http://localhost:8080/api/v1/checkout \
    -H "Content-Type: application/json" \
    -d "{\"transactionId\": \"TRX-$i\"}"
  echo ""
  sleep 0.1
done
```
*Perhatikan terminal log server:* Saat kegagalan terakumulasi, cockatiel akan mencetak peringatan `[CIRCUIT] Alert: Circuit Breaker OPEN!`. Request berikutnya akan langsung menerima respons status 503 tanpa delay.

#### Langkah 4: Uji Graceful Drain via POSIX Signal
Jalankan loop request di terminal kedua, lalu di terminal pertama kirimkan sinyal `SIGTERM`:
```bash
kill -SIGTERM $(pgrep -f "tsx resilient-app.ts")
```
*Verifikasi:* Server akan mencetak tahapan unregistering `/readyz`, menahan terminasi selama pre-stop delay, menyelesaikan active in-flight requests, lalu keluar dengan exit code `0`.

---

### 13. Exercise

#### Level: Easy
Ubah implementasi liveness probe pada sub-bab 7 agar menyertakan informasi metrik penggunaan memori internal runtime (`process.memoryUsage()`) tanpa merusak performa event loop.

#### Level: Medium
Implementasikan adaptive rate limiting menggunakan algoritma *Token Bucket* yang mengecek header `x-forwarded-for` dan membatasi throughput maksimal 10 request per detik per client IP. Jika limit terlampaui, kembalikan response header `Retry-After`.

#### Level: Hard
Bangun sebuah generic HTTP client wrapper di Node.js menggunakan TypeScript yang mengintegrasikan:
1. `AbortController` dengan timeout dinamis per attempt.
2. Exponential backoff retry engine yang hanya melakukan percobaan ulang pada error kode: 502, 503, 504, dan `ECONNRESET`.
3. Circuit breaker instance per target upstream hostname.
4. Auto-injection span context tracing W3C ke HTTP header target downstream.

---

### 14. Challenge

**Skenario:** Anda adalah Principal Architect dari sebuah platform perbankan digital. Sistem Anda menghadapi fenomena *Gray Failure* (degradasi parsial laten yang tidak memicu error eksplisit melainkan lonjakan latency tinggi secara intermiten) pada cluster database PostgreSQL downstream.

**Spesifikasi Masalah:**
1. Connection pool gateway database Node.js (`pg.Pool`) mengalami socket starvation: koneksi aktif tertahan eksekusi slow queries, menyebabkan incoming request tertumpuk di internal queue pool.
2. Ketika queue pool penuh, event loop mulai terhambat secara drastis, memicu kegagalan liveness check, sehingga Kubernetes me-restart pod yang sehat.
3. Pod yang baru restart membebani database kembali dengan koneksi awal yang masif (*thundering herd problem*).

**Tantangan Arsitektur:**
Rancang dan bangun sistem proteksi reaktif komprehensif pada service Node.js tersebut tanpa bergantung pada software pihak ketiga di luar Node.js runtime layer. Solusi harus mencakup:
- *Backpressure management* pada pooling database: menolak request segera (*fail-fast load-shedding*) jika waktu tunggu di queue koneksi melewati batas aman tertentu.
- Sinkronisasi status *Readiness Probe* dengan saturasi resource internal DB pool.
- Mekanisme self-healing pembatasan laju reconnect (*connection rate ramp-up*) saat sistem baru menyala agar tidak menghantam DB yang sedang recovery.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual Dasar (5 Soal)
1. **Mengapa penanganan sinyal `SIGKILL` tidak dapat dikonfigurasi melalui listener `process.on('SIGKILL', ...)` di Node.js?**
   - *Jawaban:* `SIGKILL` adalah sinyal kernel level-9 yang tidak dapat ditangkap, diblokir, atau diabaikan oleh proses pengguna. Kernel langsung mencabut alokasi memori dan process table entry secara instan tanpa mengizinkan eksekusi instruksi di user space.

2. **Apa perbedaan mendasar antara endpoint `/livez` dan `/readyz` pada orkestrasi microservice Kubernetes?**
   - *Jawaban:* `/livez` (Liveness) mendeteksi apakah proses runtime Node.js masih hidup atau mengalami deadlock fatal. Jika gagal, container akan direstart. `/readyz` (Readiness) mendeteksi apakah aplikasi siap menerima traffic dari load balancer/ingress. Jika gagal, pod tidak direstart, melainkan hanya dilepas dari routing endpoint.

3. **Mengapa `process.exit(1)` lebih direkomendasikan daripada membiarkan proses tetap berjalan setelah terjadi event `uncaughtException`?**
   - *Jawaban:* Karena saat `uncaughtException` terpicu, konteks memori V8 dan state internal aplikasi berpotensi korup (misal: connection pool tertutup separuh, resource lock menggantung). Menjalankan proses dalam state korup berisiko merusak integritas data transaksi.

4. **Apa fungsi dari metode `.unref()` pada timer `setTimeout` yang digunakan dalam graceful shutdown handler?**
   - *Jawaban:* `.unref()` memberitahu Libuv bahwa timer tersebut tidak boleh mencegah event loop untuk berhenti (*exit*) jika seluruh event I/O lain telah selesai ditangani. Timer ini hanya berfungsi sebagai pengaman pasif (watchdog).

5. **Apa yang dimaksud dengan "Jitter" dalam strategi retry backoff, dan mengapa ini penting dalam skala mikroservis masif?**
   - *Jawaban:* Jitter adalah penambahan variasi acak (*random noise*) pada interval waktu tunggu retry. Fungsinya mencegah fenomena *thundering herd*, di mana ratusan pod mengirimkan request retry secara serentak pada milidetik yang sama ke downstream yang sedang bermasalah.

#### Bagian B: Analisis Intermediate (5 Soal)
6. **Perhatikan skenario ini: Service A memanggil Service B via HTTP. Di service A, circuit breaker berstatus OPEN. Mengapa service A tetap harus mengembalikan metrik spesifik ke sistem observability?**
   - *Jawaban:* Untuk memberikan visibilitas instan ke engineer/SRE bahwa kegagalan ditangani secara terproteksi oleh fail-fast policy, memisahkan indikator error lokal aplikasi dengan error kegagalan dependensi.

7. **Bagaimana race condition dapat terjadi antara update iptables Kubernetes dan event `SIGTERM` pada pod Node.js jika tidak menggunakan delay/preStop hook?**
   - *Jawaban:* Sinyal `SIGTERM` diterima pod secara simultan atau lebih cepat daripada waktu yang dibutuhkan Ingress/Kube-Proxy untuk memperbarui rule routing jaringan. Jika service langsung menutup socket server, paket TCP dari request yang masih dialihkan oleh ingress lama akan dibalas dengan `RST` (Connection Refused), menghasilkan HTTP 502 pada klien.

8. **Mengapa operasi `JSON.parse()` dengan ukuran payload yang sangat besar (misal 50MB) berisiko mematikan Pod di cluster Kubernetes produksi?**
   - *Jawaban:* `JSON.parse` adalah operasi CPU-bound sinkron. Parsing payload masif memblokir thread tunggal event loop selama ratusan milidetik atau detik. Selama proses ini, probe liveness Kubernetes yang masuk tidak dapat diproses hingga akhirnya timeout, menyebabkan Kubelet mengira pod mengalami deadlock dan me-restart container secara keliru.

9. **Apa peran AsyncLocalStorage (ALS) dalam tracing OpenTelemetry pada arsitektur async Node.js?**
   - *Jawaban:* ALS menyediakan mekanisme pelacakan konteks eksekusi asinkron secara kontinu di seluruh rantai pemanggilan promise/callback, memungkinkan pengambilan context TraceId dan SpanId aktif secara deterministik tanpa perlu mengoper context object secara manual ke setiap parameter fungsi.

10. **Kapan kondisi sebuah Circuit Breaker bertransisi dari OPEN menjadi HALF-OPEN?**
    - *Jawaban:* Transisi terjadi secara otomatis setelah periode waktu pendinginan (*sleep window / cooldown timeout*) yang ditentukan telah berakhir, mengindikasikan bahwa sirkuit siap menguji downstream dengan sejumlah kecil request percontohan (*canary*).

#### Bagian C: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1:**
    *Sebuah microservice Node.js di cluster Kubernetes mengalami restart loop (CrashLoopBackOff). Log menunjukkan pesan: `Error: listen EADDRINUSE: address already in use :::8080`. Setelah dianalisis, container menggunakan process manager pihak ketiga yang spawn 2 child workers di dalam single container tanpa membedakan port.*
    - **Akar Masalah:** Pelanggaran prinsip *Single Responsibility per Container*. Menjalankan multi-process cluster Node.js di dalam satu container pod Kubernetes memicu konflik alokasi port TCP jika worker tidak berbagi cluster master listener via module `node:cluster`.
    - **Solusi Produksi:** Hapus process manager di dalam container. Jalankan satu proses Node.js murni per container. Delegasikan horizontal scaling ke level orkestrator (Kubernetes ReplicaSet / HPA).

12. **Skenario 2:**
    *Setelah rilis fitur baru, dashboard metrik menunjukkan memori V8 heap konstan di angka aman (300MB), namun Linux Kernel OOM killer tetap mematikan pod Node.js tersebut (Exit Code 137). Limit pod diatur ke 1GB.*
    - **Akar Masalah:** Memory leak terjadi di luar V8 managed heap (*Off-Heap memory*). Kemungkinan besar disebabkan oleh alokasi `Buffer` yang masif dan tidak dibebaskan, leak pada Native Addon C++ (N-API), atau penumpukan socket stream pada layer Libuv.
    - **Investigasi & Solusi:** Analisis alokasi memory via `process.memoryUsage().arrayBuffers` dan `process.memoryUsage().external`. Periksa penggunaan modul native dan stream compression (seperti zlib) yang memakan buffer off-heap.

13. **Skenario 3:**
    *Aplikasi Checkout Node.js memiliki latency normal P95 sebesar 40ms. Selama peak traffic, P99 melonjak drastis hingga 3500ms, namun utilisasi CPU Pod hanya 20% dan RAM 35%. Downstream DB latency terpantau normal di 5ms.*
    - **Akar Masalah:** *Socket Pool Starvation* atau *Libuv Thread Pool Contention*. Node.js secara default memiliki batas konkurensi DNS resolution (`UV_THREADPOOL_SIZE=4`) dan batas default keepAlive pool HTTP client. Jika service melakukan outbound request ke domain yang butuh resolusi DNS, request antre menunggu thread Libuv yang terkunci.
    - **Solusi Produksi:** Naikkan batas `UV_THREADPOOL_SIZE` (misal ke 16 atau 64) via environment variable sistem. Gunakan DNS caching di layer node/pod (misal CoreDNS local cache atau `dnscache` module). Konfigurasikan `maxSockets` pada agent HTTP client ke nilai yang sepadan dengan beban puncak traffic.

---

### 16. Summary

- **Resilience is Non-Negotiable:** Membangun microservice enterprise berbasis Node.js menuntut kesadaran mendalam bahwa jaringan dan dependensi eksternal sewaktu-waktu pasti gagal.
- **Fail-Fast & Isolate:** Menggunakan mekanisme *Circuit Breaker*, *Bulkhead*, dan *Timeout* mencegah satu downstream yang lambat merusak keseluruhan arsitektur cluster melalui *cascading failures*.
- **Deterministic Lifecycle:** Integrasi yang presisi dengan siklus sinyal POSIX kernel OS (`SIGTERM`) dan orkestrator (Kubernetes termination grace period & readiness probes) adalah syarat mutlak untuk mencapai reliabilitas *Zero Downtime Deployment*.
- **Deep Observability:** Log terisolasi tidak lagi memadai. Penggunaan OpenTelemetry untuk mentransmisikan *distributed traces*, memantau *event loop lag*, dan melacak alokasi heap memampukan identifikasi anomali secara presisi sebelum berdampak pada user akhir.