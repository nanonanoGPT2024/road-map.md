# Bab 10: Enterprise Architecture & Reliability Engineering
## Module 01: Production Readiness & Resilient Microservice Architecture

---

### Seksi 01: Identitas Modul
* **Track:** Node.js Backend & Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Level:** Advanced (L4/L5 Backend Engineer)
* **Prasyarat:** Asynchronous I/O Fundamentals, Event Loop Mechanics, Intermediate Docker & Kubernetes, Redis Basics, Express/Fastify Enterprise Routing.
* **Alokasi Waktu:** 8 Jam Teori & Studio Praktikum
* **Target Output:** Mahasiswa mampu merancang, mengimplementasikan, dan menguji arsitektur Node.js microservice yang memiliki resiliensi tingkat produksi (*zero-downtime graceful lifecycle*, *fault-tolerant downstream execution*, *distributed telemetry*, dan *fail-safe resource handling*).

---

### Seksi 02: Learning Objectives
1. **Menerapkan Advanced Process Lifecycle:** Menguasai orkestrasi terminasi proses Node.js (`SIGTERM`/`SIGINT`) secara deterministik, membersihkan *active handles*, mendrainase *in-flight HTTP requests*, dan menutup *connection pools* database tanpa kehilangan data (*data-loss prevention*).
2. **Membangun Fault-Tolerant Communication Layers:** Mengonfigurasi pola resiliensi tingkat lanjut mencakup *exponential backoff with jitter*, *idempotency keys*, dan *stateful Circuit Breaker* terdistribusi untuk memitigasi *cascading failure*.
3. **Mengintegrasikan Telemetri Terdistribusi:** Mengimplementasikan instrumentasi metrik (Prometheus) dan *distributed tracing context propagation* (OpenTelemetry/W3C Trace Context) secara presisi ke dalam *event loop* Node.js.
4. **Menerapkan Multi-Layer Security & Resource Control:** Mengamankan runtime Node.js dari ancaman *event loop starvation*, *unhandled rejections*, dan *prototype pollution* menggunakan *hardened configurations*, rate limiter berlapis, dan proteksi memori.

---

### Seksi 03: Concept Map Diagram ASCII
```
+----------------------------------------------------------------------------------------------------+
|                         PRODUCTION-READY NODE.JS RESILIENT ARCHITECTURE                           |
+----------------------------------------------------------------------------------------------------+
                                                  |
         +----------------------------------------+----------------------------------------+
         |                                        |                                        |
         v                                        v                                        v
+------------------+                    +--------------------+                    +------------------+
| Process Runtime  |                    | Resilience & Flow  |                    | Observability    |
| & Lifecycle      |                    | Control Mechanisms |                    | & Telemetry      |
+------------------+                    +--------------------+                    +------------------+
  |-- Signal Traps (SIGTERM/SIGINT)       |-- Circuit Breaker Pattern              |-- Prometheus Metrics
  |-- Connection Pool Draining            |   (CLOSED/OPEN/HALF-OPEN)              |   (RED Method)
  |-- In-flight Request Drain             |-- Exponential Backoff + Jitter         |-- Distributed Tracing
  |-- Memory Pressure Monitoring          |-- Redis Token Bucket Limiter           |   (OpenTelemetry/W3C)
  +-- Docker/K8s PID 1 Handling           +-- Outbox Idempotency Worker            +-- Structured JSON Logs
                                                  |
                                                  v
                                    +----------------------------+
                                    | Downstream Microservices / |
                                    | PostgreSQL / Redis / Kafka |
                                    +----------------------------+
```

---

### Seksi 04: Mengapa Relevan
Pada lingkungan monolitik tradisional, kegagalan jaringan atau keterlambatan database sering kali diatasi dengan mekanisme *restart* sederhana. Namun, pada arsitektur Microservices terdistribusi skala *high-concurrency*, Node.js sangat rentan terhadap **Cascading Failures** (kegagalan berantai). Karakteristik *single-threaded event loop* membuat Node.js rentan mengalami *resource exhaustion* dan *event-loop blockage* apabila *downstream services* mengalami *high latency* (*slow-death scenario*). 

Menerapkan *Production Readiness* bukan sekadar membuat kode berjalan, melainkan membangun determinisme sistemik:
* Menghindari *abrupt socket drops* saat *rolling deployment* Kubernetes.
* Mencegah *Thundering Herd Problem* saat dependensi pulih dari *downtime*.
* Memastikan visibilitas granular terhadap bottlenecks tanpa degradasi throughput.

---

### Seksi 05: Anatomi Konsep Inti

#### 1. Deterministic Graceful Shutdown Sequence
Node.js mengelola I/O melalui *active handles* di `libuv`. Ketika sinyal terminasi (`SIGTERM`) dikirimkan oleh Kubernetes atau Process Manager:
1. Pod ditandai `Terminating`, Service Controller menghapus endpoint dari `iptables`/Kube-Proxy.
2. Server HTTP berhenti menerima koneksi baru (`server.close()`).
3. Readiness Probe beralih ke status `503 Service Unavailable`.
4. Berikan *grace period delay* (mengakomodasi *propagation delay* pada K8s routing table).
5. Drain semua *in-flight requests* dengan batasan timeout hard-limit.
6. Tutup koneksi downstream (PostgreSQL Pool, Redis Client, Kafka Consumers).
7. Eksekusi `process.exit(0)`.

#### 2. Distributed Circuit Breaker Pattern
Pola ini memproteksi runtime dari pemanggilan downstream yang telah gagal secara persisten melalui tiga state:
* **CLOSED:** Permintaan diteruskan secara normal. Jika tingkat kegagalan (*failure rate*) melampaui batas ambang (*error threshold percentage*) dalam interval jendela waktu tertentu, status berpindah ke **OPEN**.
* **OPEN:** Permintaan langsung digagalkan seketika (*fail-fast*) tanpa mengirim network I/O, mengembalikan fallback response atau HTTP 503. Timer pendinginan (*reset timeout*) diaktifkan.
* **HALF-OPEN:** Setelah reset timeout berakhir, sebagian kecil *trial requests* diizinkan lolos. Jika berhasil, sirkuit kembali ke **CLOSED**. Jika gagal, sirkuit kembali ke **OPEN**.

#### 3. Structured Telemetry via OpenTelemetry (OTel) & Prometheus
* **Metrics (RED Method):** Rate (throughput req/sec), Errors (rasio 4xx/5xx req/sec), Duration (latensi p50, p95, p99 melalui histogram).
* **Distributed Tracing:** Menyuntikkan metadata konteks `traceparent` (Trace ID, Span ID, Trace Flags) ke dalam *outgoing HTTP/gRPC headers* untuk memastikan korelasi pemanggilan lintas microservice.

---

### Seksi 06: Panduan Implementasi Step-by-Step

#### Persiapan Dependency
Inisialisasi workspace Node.js modern berbasis TypeScript/ESM:
```bash
npm init -y
npm install express opossum prom-client @opentelemetry/api @opentelemetry/sdk-node \
    @opentelemetry/auto-instrumentations-node @opentelemetry/exporter-trace-otlp-grpc \
    pino pino-http pino-pretty dotenv ioredis pg
npm install -D typescript @types/node @types/express @types/pg ts-node
```

#### Struktur Modul Standard
```text
├── src/
│   ├── config/             # Runtime environments & validation
│   ├── infrastructure/     # Database, Redis, Circuit Breakers
│   ├── middlewares/        # Metrics, Tracing, Error Handlers
│   ├── telemetry/          # Prometheus & OTel Bootstrap
│   ├── modules/order/      # Domain Logic
│   └── app.ts              # Express initialization
├── index.ts                # Entrypoint & Process Lifecycle Manager
├── tsconfig.json
└── package.json
```

---

### Seksi 07: Contoh Kasus Sederhana: Graceful Process Lifecycle Trap

Kode berikut mendemonstrasikan penanganan sinyal kernel POSIX secara deterministik untuk membersihkan libuv active handles.

```typescript
// basic-lifecycle.ts
import http from 'node:http';

const server = http.createServer((req, res) => {
  if (req.url === '/work') {
    // Simulasi pekerjaan I/O intensif selama 3 detik
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'completed' }));
    }, 3000);
    return;
  }
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('OK');
});

server.listen(3000, () => {
  console.log('HTTP Server listening on port 3000. PID:', process.pid);
});

function handleShutdown(signal: string) {
  console.log(`\nReceived ${signal}. Starting graceful shutdown...`);

  // Berhenti menerima koneksi baru
  server.close((err) => {
    if (err) {
      console.error('Error during server close:', err);
      process.exit(1);
    }
    console.log('All pending requests drained. Process exiting gracefully.');
    process.exit(0);
  });

  // Force shutdown jika request menggantung melebihi 5 detik
  setTimeout(() => {
    console.error('Forced shutdown timeout reached. Terminating process ungracefully.');
    process.exit(1);
  }, 5000).unref(); // .unref() agar timer ini tidak menahan Event Loop jika server selesai lebih awal
}

process.on('SIGTERM', () => handleShutdown('SIGTERM'));
process.on('SIGINT', () => handleShutdown('SIGINT'));
```

---

### Seksi 08: Implementasi Production-Grade Lengkap

Di bawah ini adalah implementasi sistem produksi terdistribusi lengkap: Inisialisasi OpenTelemetry, HTTP Server dengan Structured Logging, Metric Registry, Circuit Breaker ke Downstream Payment Gateway, PostgreSQL Connection Pool, dan Dynamic Lifecycle Manager.

#### 1. Telemetry Initializer (`src/telemetry/tracer.ts`)
```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';

const traceExporter = new OTLPTraceExporter({
  url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317',
});

export const otelSdk = new NodeSDK({
  traceExporter,
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': { enabled: false }, // Kurangi noise tracing fs
    }),
  ],
});

otelSdk.start();
```

#### 2. Core Service Engine (`src/index.ts`)
```typescript
import './telemetry/tracer.js'; // Must be imported first
import express, { Request, Response, NextFunction } from 'express';
import { Pool } from 'pg';
import CircuitBreaker from 'opossum';
import client from 'prom-client';
import pino from 'pino';
import pinoHttp from 'pino-http';
import http from 'node:http';

// ==========================================
// 1. Logger & Metrics Setup
// ==========================================
const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

const httpLogger = pinoHttp({ logger });

const collectDefaultMetrics = client.collectDefaultMetrics;
const Registry = client.Registry;
const register = new Registry();
collectDefaultMetrics({ register });

const httpRequestDurationMicroseconds = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'code'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
});
register.registerMetric(httpRequestDurationMicroseconds);

// ==========================================
// 2. Database & Downstream Integrations
// ==========================================
const dbPool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: Number(process.env.DB_PORT) || 5432,
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  database: process.env.DB_NAME || 'orders_db',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

interface PaymentPayload {
  orderId: string;
  amount: number;
}

// Simulasi unstable downstream service call
async function executePaymentRemoteCall(payload: PaymentPayload): Promise<{ transactionId: string }> {
  const url = process.env.PAYMENT_GATEWAY_URL || 'https://httpbin.org/delay/1';
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 2000); // 2-second timeout

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Downstream Gateway returned HTTP ${response.status}`);
    }

    return { transactionId: `TX-${Date.now()}` };
  } finally {
    clearTimeout(timeoutId);
  }
}

// Konfigurasi Enterprise Circuit Breaker
const breakerOptions: CircuitBreaker.Options = {
  timeout: 3000, // Timeout operasi jika Promise menggantung > 3s
  errorThresholdPercentage: 50, // Buka sirkuit jika 50% request gagal
  resetTimeout: 10000, // Tunggu 10s sebelum pindah ke HALF-OPEN
  rollingCountTimeout: 10000, // Jendela sampel statistik
  rollingCountBuckets: 10,
};

const paymentCircuitBreaker = new CircuitBreaker(executePaymentRemoteCall, breakerOptions);

paymentCircuitBreaker.on('open', () => logger.warn('PAYMENT_CIRCUIT_BREAKER_OPEN: Fail-fast activated'));
paymentCircuitBreaker.on('halfOpen', () => logger.info('PAYMENT_CIRCUIT_BREAKER_HALF_OPEN: Probing downstream'));
paymentCircuitBreaker.on('close', () => logger.info('PAYMENT_CIRCUIT_BREAKER_CLOSED: Operational nominal'));
paymentCircuitBreaker.fallback(() => {
  return { transactionId: 'FALLBACK_PENDING_RECONCILIATION' };
});

// ==========================================
// 3. Application Initialization
// ==========================================
const app = express();
app.use(express.json());
app.use(httpLogger);

let isShuttingDown = false;

// Middleware interceptor untuk drain phase
app.use((req: Request, res: Response, next: NextFunction) => {
  if (isShuttingDown) {
    res.set('Connection', 'close');
    res.status(503).json({ error: 'Server is undergoing maintenance. Retry on alternate replica.' });
    return;
  }
  next();
});

// Request Duration Metrics Interceptor
app.use((req: Request, res: Response, next: NextFunction) => {
  const end = httpRequestDurationMicroseconds.startTimer();
  res.on('finish', () => {
    if (req.route) {
      end({ route: req.route.path, code: res.statusCode, method: req.method });
    }
  });
  next();
});

// ==========================================
// 4. Routes Definition
// ==========================================

// K8s Liveness Probe: Memastikan node process tidak deadlock
app.get('/healthz/liveness', (req: Request, res: Response) => {
  res.status(200).send('OK');
});

// K8s Readiness Probe: Memastikan dependensi database siap melayani traffic
app.get('/healthz/readiness', async (req: Request, res: Response) => {
  if (isShuttingDown) {
    res.status(503).send('SHUTTING_DOWN');
    return;
  }
  try {
    await dbPool.query('SELECT 1');
    res.status(200).send('READY');
  } catch (err) {
    logger.error({ err }, 'Readiness probe failed: Database unreachable');
    res.status(503).send('DB_UNAVAILABLE');
  }
});

// Telemetry Metrics Endpoint
app.get('/metrics', async (req: Request, res: Response) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

// Domain Endpoint
app.post('/api/v1/orders', async (req: Request, res: Response) => {
  const { amount } = req.body;
  
  if (!amount || typeof amount !== 'number') {
    res.status(400).json({ error: 'Valid amount is required.' });
    return;
  }

  const orderId = `ORD-${Date.now()}`;

  try {
    // 1. Eksekusi pemanggilan downstream lewat Circuit Breaker
    const paymentResult = await paymentCircuitBreaker.fire({ orderId, amount });

    // 2. Transaksi Database Terisolasi
    const dbResult = await dbPool.query(
      'INSERT INTO orders(id, amount, status, transaction_id) VALUES($1, $2, $3, $4) RETURNING *',
      [orderId, amount, 'PROCESSED', paymentResult.transactionId]
    );

    res.status(201).json({
      success: true,
      data: dbResult.rows[0] || { orderId, status: 'PROCESSED', transactionId: paymentResult.transactionId },
    });
  } catch (error: any) {
    logger.error({ error, orderId }, 'Order processing failed');
    res.status(500).json({ error: 'Internal processing failure', detail: error.message });
  }
});

// Centralized Error Handling Middleware
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  logger.error({ err }, 'Unhandled runtime error intercepted');
  res.status(500).json({ error: 'An unexpected system error occurred' });
});

// ==========================================
// 5. Server Lifecycle & Graceful Shutdown
// ==========================================
const PORT = process.env.PORT || 3000;
const server = http.createServer(app);

server.listen(PORT, () => {
  logger.info(`Application worker running on port ${PORT} [PID: ${process.pid}]`);
});

const activeSockets = new Set<any>();
server.on('connection', (socket) => {
  activeSockets.add(socket);
  socket.on('close', () => activeSockets.delete(socket));
});

function gracefulShutdown(signal: string) {
  if (isShuttingDown) return;
  isShuttingDown = true;

  logger.warn(`Termination signal ${signal} received. Initiating graceful shutdown...`);

  // Kubernetes sync buffer: beri jeda 2 detik agar ingress controller mengalihkan traffic
  const ingressBufferMs = 2000;
  
  setTimeout(() => {
    logger.info('Stopping HTTP server from accepting new connections...');
    server.close(async (err) => {
      if (err) {
        logger.error({ err }, 'Error closing HTTP server instance');
        process.exit(1);
      }

      logger.info('HTTP server closed. Draining external resource pools...');

      try {
        await dbPool.end();
        logger.info('PostgreSQL connection pool drained successfully.');
        
        paymentCircuitBreaker.shutdown();
        logger.info('Circuit Breaker timers dismantled.');

        logger.info('Graceful shutdown procedure concluded without errors. Exiting.');
        process.exit(0);
      } catch (poolErr) {
        logger.error({ poolErr }, 'Error during database pool termination');
        process.exit(1);
      }
    });

    // Destroy idle sockets yang masih menggantung via keep-alive
    for (const socket of activeSockets) {
      if (socket.requestsCount === 0) {
        socket.destroy();
      }
    }

    // Safety timeout hard limit
    const HARD_TIMEOUT_MS = 10000;
    setTimeout(() => {
      logger.fatal('Forced shutdown invoked: active handles could not be drained within limit');
      process.exit(1);
    }, HARD_TIMEOUT_MS).unref();

  }, ingressBufferMs);
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

process.on('unhandledRejection', (reason: any) => {
  logger.fatal({ reason }, 'FATAL: Unhandled Promise Rejection detected. Triggering safe exit.');
  gracefulShutdown('unhandledRejection');
});

process.on('uncaughtException', (error: Error) => {
  logger.fatal({ error }, 'FATAL: Uncaught Exception thrown. Process state corrupted.');
  process.exit(1); // Fast exit on dirty state
});
```

---

### Seksi 09: Diagram Alur Kerja ASCII: Graceful Drain & Circuit Breaker Logic

```
   Downstream Service Invocation Sequence with Circuit Breaker
   ===========================================================
   
   Client Request
         |
         v
   [Circuit Breaker]
         |
         +---> State == OPEN? -----> [YES] ---> Trigger Fallback Response (Fast Fail)
         |                                           |
        [NO]                                         v
         |                                  Return 503 / Degraded Mode
         v
   Execute Request w/ Hard Timeout (2000ms)
         |
         +---> Request Success? ---> [YES] ---> Record Success -> Return Result
         |
        [NO] (Timeout / Error 5xx)
         |
         v
   Increment Failure Metric
         |
   Failure % >= 50% Threshold? ----> [YES] ---> Trip State to OPEN (Start 10s Reset Timer)
         |
        [NO]
         |
         v
   Trigger Fallback / Return Controlled Error
```

---

### Seksi 10: Analisis Trade-offs

| Pendekatan | Keuntungan | Biaya / Trade-off | Skenario Penggunaan Terbaik |
| :--- | :--- | :--- | :--- |
| **Fail-Fast (Circuit Breaker)** | Mencegah penumpukan antrean koneksi, membebaskan memory microservice, melindungi downstream. | Kompleksitas arsitektur; pengguna mendapatkan *degraded responses*. | Pemanggilan HTTP/gRPC dependensi pihak ketiga atau service non-kritis. |
| **Aggressive Retries with Backoff** | Menyelesaikan masalah *transient network blips* secara transparan bagi user. | Dapat memicu efek *DDoS* pada backend yang sedang kolaps (*Retry Storms*). | Operasi jaringan idempotent dengan *Exponential Jitter* ketat (maks 3 percobaan). |
| **Long-Lived Process Termination** | Memastikan nol request yang *corrupted* atau terputus paksa di tengah jalan. | Waktu deployment container pod menjadi lebih lama (menambah *rollout duration*). | Service finansial, proses *order checkout*, dan komputasi multi-step ACID. |

---

### Seksi 11: Best Practices & Antipatterns

#### Best Practices
* **Gunakan Connection Timeout Eksplisit:** Selalu pasang parameter `timeout` pada instans Axios, Fetch, atau Database Driver. Secara *default*, soket Node.js tidak memiliki timeout dan dapat menggantung selamanya.
* **Gunakan Exponential Backoff dengan Full Jitter:** Hitung interval jeda percobaan ulang dengan rumus:
  $$\text{Sleep} = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$
  Hal ini mencegah sinkronisasi request dari ribuan client secara simultan.
* **Terapkan Unhandled Error Traps:** Jangan biarkan `uncaughtException` berjalan tanpa `process.exit(1)`. Kondisi memori pasca uncaught exception berada dalam status non-deterministik.

#### Antipatterns
* **`process.exit(0)` Langsung di Event Handler `SIGTERM`:** Mengakibatkan koneksi database terputus instan, transaksi aktif di-rollback mendadak, dan client menerima response `ECONNRESET`.
* **Menggunakan Catch-All Error Swallow:** `try { ... } catch (e) {}` tanpa rethrow atau structured log, mengaburkan kegagalan cascading downstream dari pemantauan APM.

---

### Seksi 12: Security Hardening
1. **Event Loop Lag Protection:** Terapkan limiter beban server menggunakan modul seperti `@fastify/under-pressure` atau pemantau `perf_hooks.monitorEventLoopDelay`. Tolak request baru (`503`) jika *lag* melampaui 100ms untuk mencegah eksekusi DoS.
2. **Container Security Dropping Root:** Pastikan *Dockerfile* Node.js beralih dari user root ke user `node`:
   ```dockerfile
   FROM node:20-alpine
   WORKDIR /usr/src/app
   COPY --chown=node:node package*.json ./
   RUN npm ci --only=production
   COPY --chown=node:node . .
   USER node
   CMD ["node", "dist/index.js"]
   ```
3. **HTTP Header Sanitization:** Pasang `helmet` untuk menonaktifkan header `X-Powered-By: Express` guna meminimalisasi *fingerprinting attack*.

---

### Seksi 13: Observabilitas & Debugging

#### Format Structured Logging Standar (Pino)
Hindari penggunaan `console.log()` dalam lingkungan *high-load* karena sifatnya yang *blocking* ketika menulis ke stdout TTY. Gunakan *asynchronous structured JSON logger*:

```json
{
  "level": "error",
  "time": "2026-03-31T09:41:02.123Z",
  "pid": 4821,
  "hostname": "order-srv-7d9f8c6b-xk2j1",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "orderId": "ORD-1711878062",
  "err": {
    "type": "CircuitBreakerOpenException",
    "message": "Circuit breaker is open for payment-gateway",
    "stack": "Error: Circuit breaker open..."
  },
  "msg": "Order processing failed"
}
```

#### Diagnosis Active Handles Libuv
Untuk mendeteksi resource atau timer yang menghalangi Node.js dari exit secara normal saat fase *shutdown*, jalankan inspeksi handle internal:
```typescript
// debugging active handles
console.log(process._getActiveHandles());
console.log(process._getActiveRequests());
```

---

### Seksi 14: Benchmarking & Performance

Jalankan uji beban menggunakan Autocannon untuk melihat degradasi performa dan perilaku server ketika downstream mengalami latensi tinggi:

```bash
# Skenario 1: Normal Load (100 concurrent connections, durasi 30 detik)
npx autocannon -c 100 -d 30 -m POST \
  -H "Content-Type: application/json" \
  -b '{"amount": 150000}' \
  http://localhost:3000/api/v1/orders

# Skenario 2: Simulasi Circuit Breaker Under Failure Stress
npx autocannon -c 500 -d 20 -m POST \
  -H "Content-Type: application/json" \
  -b '{"amount": 250000}' \
  http://localhost:3000/api/v1/orders
```

#### Ekspektasi Metrik Kinerja (Target Baseline)
* **P99 Latency:** $< 50\text{ ms}$ (Kondisi normal), $< 5\text{ ms}$ (Kondisi Circuit Breaker `OPEN` / Fast-Fail).
* **Event Loop Lag:** Rata-rata $< 15\text{ ms}$, p99 $< 50\text{ ms}$.
* **Memory Leak:** Kemiringan grafik *heap usage* konstan datar pasca *Garbage Collection cycles*.

---

### Seksi 15: Hands-on Lab Mini-Project

#### Objektif
Bangun microservice resilient yang memanggil mock upstream service yang tidak stabil (*unstable flaking dependency*).

#### Skenario Eksekusi
1. Jalankan dependency server lokal yang mengembalikan kode status HTTP 500 setiap 3 dari 5 request:
```typescript
// mock-upstream.ts
import http from 'node:http';
let counter = 0;
http.createServer((req, res) => {
  counter++;
  if (counter % 3 === 0) {
    res.writeHead(500);
    res.end('Dependency Failure');
  } else {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'SUCCESS' }));
  }
}).listen(4000);
```
2. Hubungkan modul `CircuitBreaker` dan algoritma *Exponential Backoff* pada microservice Node.js Anda untuk memanggil port `4000`.
3. Verifikasi bahwa Circuit Breaker berpindah ke state `OPEN` secara otomatis saat threshold error terlewati, dan amati bahwa downstream mock server tidak lagi menerima traffic selama status `OPEN`.

---

### Seksi 16: Automated Testing & Verification

Berikut test suite integrasi menggunakan **Jest** dan **Supertest** untuk memverifikasi pemutusan Circuit Breaker secara terprogram.

```typescript
// tests/resilience.spec.ts
import request from 'supertest';
import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import express from 'express';
import CircuitBreaker from 'opossum';

describe('Production Resilience Suite: Circuit Breaker & Fallback', () => {
  let app: express.Application;
  let unstableAction: jest.Mock;
  let breaker: CircuitBreaker;

  beforeAll(() => {
    app = express();
    app.use(express.json());

    unstableAction = jest.fn();

    breaker = new CircuitBreaker(unstableAction, {
      errorThresholdPercentage: 50,
      resetTimeout: 1000,
      rollingCountTimeout: 2000,
    });

    breaker.fallback(() => ({ fallbackTriggered: true }));

    app.get('/test-breaker', async (req, res) => {
      try {
        const result = await breaker.fire();
        res.status(200).json(result);
      } catch (err) {
        res.status(500).json({ error: 'Failed' });
      }
    });
  });

  it('harus beralih ke state OPEN setelah rentetan downstream failure', async () => {
    // 1. Simulasikan kegagalan berturut-turut
    unstableAction.mockRejectedValue(new Error('Network Remote Outage'));

    for (let i = 0; i < 5; i++) {
      const res = await request(app).get('/test-breaker');
      expect(res.status).toBe(200);
      expect(res.body).toEqual({ fallbackTriggered: true });
    }

    // 2. Sirkuit sekarang harus berstatus OPEN
    expect(breaker.opened).toBe(true);

    // 3. Verifikasi pemanggilan fungsi asli dihentikan (Fast-Fail execution)
    const callsCountBefore = unstableAction.mock.calls.length;
    await request(app).get('/test-breaker');
    const callsCountAfter = unstableAction.mock.calls.length;

    expect(callsCountAfter).toBe(callsCountBefore); // Tidak ada eksekusi I/O baru ke downstream
  });
});
```

---

### Seksi 17: Troubleshooting Guide

| Gejala Masalah | Investigasi Root Cause | Solusi Perbaikan |
| :--- | :--- | :--- |
| **Kubernetes melempar status `OOMKilled` (Exit Code 137).** | Alokasi V8 Old Memory melebihi batas Container Memory Limit. Garbage Collector tidak dieksekusi tepat waktu. | Set flag Node.js `--max-old-space-size` bernilai 75% dari K8s memory limit (cth: Limit 1GB $\rightarrow$ Set `--max-old-space-size=768`). |
| **Request terputus dengan error `502 Bad Gateway` saat Rolling Deployment.** | Pod dihapus sebelum ingress router memperbarui tabel routing downstream. | Tambahkan pre-stop sleep buffer (2-5 detik) pada pod lifecycle hook atau di awal `SIGTERM` handler. |
| **Event Loop Lag tinggi (>500ms), namun CPU usage rendah.** | Terjadi pemanggilan fungsi sinkronus blocking (cth: `JSON.parse` pada payload raksasa, Regex DoS, atau crypto sync methods). | Ganti dengan streaming parser (`stream-json`), offload komputasi ke `worker_threads`, dan gunakan async crypto API. |

---

### Seksi 18: Checklist Produksi

- [ ] **Runtime Engine:** Menggunakan LTS Node.js Runtime versi terbaru (v20+ / v22+).
- [ ] **Signal Interception:** `SIGTERM` dan `SIGINT` ditangkap dan menangani pembersihan handle secara deterministik.
- [ ] **Process Execution:** Proses tidak berjalan dengan ID root (`USER node` dalam container).
- [ ] **Probes Separation:** Endpoint Liveness (`/healthz/liveness`) dan Readiness (`/healthz/readiness`) dipisah secara tegas.
- [ ] **Database Pools:** Pool database memiliki batasan `max`, `idleTimeoutMillis`, dan `connectionTimeoutMillis` yang tervalidasi.
- [ ] **Circuit Breakers:** Semua remote network I/O dibungkus dalam *Circuit Breaker* dengan timeout eksplisit.
- [ ] **Telemetry Readiness:** Metrik Prometheus terekspos pada path terproteksi atau internal port.
- [ ] **Distributed Tracing:** Tracing context header (`traceparent`) terpropagasi pada setiap pemanggilan HTTP downstream.
- [ ] **Memory Management:** Alokasi `--max-old-space-size` diselaraskan secara matematis dengan limit container cgroups.
- [ ] **Fatal Error Strategy:** `uncaughtException` dan `unhandledRejection` tercatat