# Modul Pembelajaran: Observabilitas, Resiliensi, & Deployment Berskala Besar

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 03-Frontend-and-Mobile
* **Topik:** nextjs
* **Bab:** 10 (Observabilitas dan Skalabilitas)
* **Modul:** 01 (Observabilitas, Resiliensi, & Deployment Berskala Besar)
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Teknis:** Pemahaman mendalam tentang Next.js App Router (RSC, Server Actions, Middleware), Docker containerization, Kubernetes runtime primitives, OpenTelemetry instrumentation, dan distributed systems observability.

---

## SEKSI 02 — LEARNING OBJECTIVES

1. Menginstrumentasi aplikasi Next.js enterprise menggunakan OpenTelemetry (OTel) SDK untuk distributed tracing, custom span generation, dan W3C Trace Context propagation melintasi boundary Node.js runtime dan Edge runtime.
2. Mengonfigurasi structured logging (JSON-LD format) berkorelasi tinggi yang mengikat `trace_id` dan `span_id` ke dalam setiap log level (debug, info, warn, error).
3. Merancang pipeline metrics collection menggunakan OpenTelemetry Prometheus Exporter untuk memantau Node.js event loop lag, garbage collection cycles, active handles, dan HTTP request throughput/latency.
4. Membangun pola resiliensi sistem (circuit breaker, exponential backoff with full jitter, proactive timeout, bulkhead isolation) pada integrasi downstream microservices.
5. Mengimplementasikan containerization berstandar industri dengan Docker multi-stage build, memanfaatkan mode `output: 'standalone'`, dynamic base path handling, serta zero-downtime deployment (Rolling Updates/Canary) di atas Kubernetes cluster dengan liveness, readiness, dan startup probes yang presisi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam sistem monolitik tradisional, alur eksekusi bersifat sinkron dan terisolasi dalam satu proses memori. Kegagalan fungsi dapat dilacak via stack trace lokal sederhana. Di era Next.js modern skala enterprise, batas antara client-side rendering (CSR), dynamic server-side rendering (SSR), React Server Components (RSC), Edge Middleware, dan integrasi backend terdistribusi menjadi sangat tipis.

Pergeseran paradigma yang fundamental:
* **Aplikasi Next.js Bukan Sekadar UI Layer:** Next.js adalah orkestrator data front-of-the-backend (BFF) yang mengeksekusi I/O intensif, caching berlapis, dan agregasi data terdistribusi.
* **Failure is an Inevitability, Not an Anomaly:** Dalam arsitektur berskala puluhan ribu RPS, microservice downstream akan mengalami degradasi, database akan kehabisan pool connection, dan memory leak pada Node.js runtime pasti terjadi jika buffer handling tidak higienis.
* **Mental Model Tiga Pilar Observabilitas:**
  * **Traces:** Memberikan representasi alur perjalanan request lintas batasan jaringan (Edge $\to$ Node.js Server $\to$ Microservices $\to$ DB). Tracing menjawab pertanyaan: *"Di mana bottleneck latensi terjadi?"*
  * **Metrics:** Data agregat numerik time-series yang mencerminkan kesehatan ekosistem secara makro (Node.js event loop delay, memory heap consumption, HTTP p99 latency). Metrics menjawab: *"Apakah sistem secara keseluruhan sehat?"*
  * **Logs:** Peristiwa diskrit yang kaya konteks metadata yang dikorelasikan langsung dengan Trace Context. Logs menjawab: *"Mengapa komponen spesifik tersebut gagal?"*

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur distribusi traffic, telemetri OpenTelemetry, dan proses orkestrasi deployment Next.js di Kubernetes:

```
+----------------------------------------------------------------------------------------------------+
|                                    INCOMING TRAFFIC / USERS                                        |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
                        +───────────────────────────────────────────────────+
                        |      Global Edge / Cloud Ingress (Cloudflare)     |
                        |      Injects: traceparent, x-request-id           |
                        +───────────────────────────────────────────────────+
                                                  │
                                                  ▼
+────────────────────────────────────────────────────────────────────────────────────────────────────+
| KUBERNETES CLUSTER (INGRESS-NGINX / TRAEFIK)                                                       |
|                                                                                                    |
| Routing: Round-Robin / Canary Weight                                                               |
+────────────────────────────────────────────────────────────────────────────────────────────────────+
         │                                                           │
         ▼ (Stable Pods - 90%)                                       ▼ (Canary Pods - 10%)
+───────────────────────────────────+                       +───────────────────────────────────+
| Pod: nextjs-app-stable            |                       | Pod: nextjs-app-canary            |
| +───────────────────────────────+ |                       | +───────────────────────────────+ |
| | Middleware (Edge/Node Runtime)| |                       | | Middleware (Edge/Node Runtime)| |
| | - Context Propagation         | |                       | | - Context Propagation         | |
| +───────────────┬───────────────+ |                       +───────────────┬───────────────+ |
|                 ▼                 |                       |                 ▼                 |
| | Server Components Engine      | |                       | | Server Components Engine      | |
| | - Custom Tracing Spans        | |                       | | - Custom Tracing Spans        | |
| | - Winston/Pino Logger         | |                       | | - Winston/Pino Logger         | |
| +───────────────┬───────────────+ |                       +───────────────┬───────────────+ |
|                 ▼                 |                       |                 ▼                 |
| | Resilience Layer              | |                       | | Resilience Layer              | |
| | - Opossum Circuit Breakers    | |                       | | - Opossum Circuit Breakers    | |
| | - Exponential Backoff         | |                       | | - Exponential Backoff         | |
| +───────────────┬───────────────+ |                       +───────────────┬───────────────+ |
|                 │                 |                       |                 │                 |
| Probes:         │                 |                       | Probes:         │                 |
| - /api/health/liveness            |                       | - /api/health/liveness            |
| - /api/health/readiness           |                       | - /api/health/readiness           |
| - /metrics (Prometheus Exporter)  |                       | - /metrics (Prometheus Exporter)  |
+─────────────────┼─────────────────+                       +─────────────────┼─────────────────+
                  │                                                           │
                  └─────────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                     +─────────────────────────────────────────────────────+
                     | OpenTelemetry OTLP Exporter (gRPC / HTTP/Protobuf)  |
                     +─────────────────────────────────────────────────────+
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
+───────────────────────────────────+                         +───────────────────────────────────+
|   OTel Collector DaemonSet / Pod  |                         |    Prometheus Server (Scrape)     |
|   - Tail-based Sampling Processor |                         |    - Scraping /metrics endpoint   |
|   - Redaction & Transformation    |                         |    - Alerts via Alertmanager      |
+─────────────────┬─────────────────+                         +───────────────────────────────────+
                  │
     ┌────────────┴────────────┐
     ▼                         ▼
+───────────────+      +────────────────+
| Datadog /     |      | ElasticSearch/ |
| Jaeger / Tempo|      | Loki (Logs)    |
+───────────────+      +────────────────+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. File Instrumentasi Internal Next.js (`instrumentation.ts`)
Next.js menyediakan hook siklus hidup runtime global melalui file `instrumentation.ts` yang ditempatkan pada root project atau di dalam direktori `src/`. Hook `register()` dipanggil sekali saat proses container/server Next.js pertama kali melakukan *bootstrapping*, sebelum kode routing atau modul server lainnya diinisialisasi.
* Di Node.js runtime, hook ini memuat `@opentelemetry/sdk-node`.
* Melakukan monkey-patching terhadap modul I/O inti (`http`, `https`, `net`, `dns`) untuk auto-instrumentasi.
* Mencegah inisialisasi ganda (*multiple instantiation*) yang dapat memicu duplikasi tracer atau memory leak pada worker thread.

### 2. Context Propagation & Distributed Tracing
Distributed tracing bergantung pada W3C Trace Context Specification:
* **`traceparent` Header:** Berisi format `version-trace_id-parent_id-trace_flags` (contoh: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`).
* **`tracestate` Header:** Membawa metadata spesifik vendor sistem pemantauan.
Ketika request masuk ke Next.js Middleware, Next.js mendestrukturisasi header tersebut. Context diteruskan secara asinkron menggunakan modul bawaan Node.js `node:async_hooks` (`AsyncLocalStorage`). Ini memastikan bahwa eksekusi di dalam RSC bertingkat (*nested React Server Components*) tetap mempertahankan `trace_id` yang sama persis tanpa perlu melakukan passing trace context secara manual via parameter fungsi.

### 3. Standalone Build Engine
Ketika Next.js dikompilasi dengan konfigurasi `output: 'standalone'`, Webpack dan Turbopack melakukan static trace analysis menggunakan `@vercel/nft` (Node File Trace).
* Mekanisme ini membaca seluruh `import`, `require`, dan dynamic lookup pada project, kemudian membangun dependency graph yang minimal.
* Output akhir diisolasi ke dalam `.next/standalone`, hanya menyalin file `node_modules` yang benar-benar digunakan saat runtime. File build berkurang dari rata-rata ~1.2GB menjadi <150MB, mempercepat waktu cold start container saat proses horizontal autoscaling (HPA) di Kubernetes.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Resiliensi Sistem: Pola Circuit Breaker & Retry Dynamics
Ketika microservice downstream (misalnya Core Banking API atau Inventory API) mengalami degradasi performa (peningkatan latensi dari 50ms menjadi 10.000ms):
* **Tanpa Circuit Breaker:** Request masuk ke Next.js akan menahan I/O connection, memblokir thread worker, menghabiskan pool socket, dan memicu *cascading failure* ke seluruh sistem front-end.
* **Dengan Circuit Breaker State Machine:**
  * **CLOSED:** Alur normal. Semua request dialirkan langsung ke downstream service. Kegagalan dihitung menggunakan sliding time-window.
  * **OPEN:** Ambang batas error/timeout terlampaui (misal: 50% error rate dalam 10 detik). Circuit breaker trip/terbuka. Request berikutnya langsung digagalkan secara instan (*fail-fast*) tanpa membuka socket ke downstream service, melindungi kapasitas thread pool Next.js.
  * **HALF-OPEN:** Setelah reset timeout berlalu (misal: 30 detik), sistem mengizinkan sebagian kecil traffic (*canary probes*) lewat. Jika berhasil, sirkuit kembali ke status `CLOSED`. Jika gagal, sirkuit kembali ke status `OPEN`.

Rumus Exponential Backoff dengan Full Jitter:
$$T_{\text{sleep}} = \operatorname{random}(0, \, \min(M_{\text{max}}, \, M_{\text{base}} \times 2^{\text{attempt}}))$$
Penggunaan *Full Jitter* mencegah fenomena *Thundering Herd Problem*, di mana ribuan worker Next.js mencoba melakukan retry secara bersamaan ke downstream service pada interval yang persis sama.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental OpenTelemetry SDK manual di Next.js menggunakan Node.js Runtime.

### 1. `next.config.mjs`
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    instrumentationHook: true,
  },
  // Mencegah kebocoran header internal ke public client
  poweredByHeader: false,
};

export default nextConfig;
```

### 2. `src/instrumentation.ts`
```typescript
export async function register(): Promise<void> {
  // Verifikasi runtime untuk menghindari eksekusi OTel Node.js SDK di Edge runtime
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { initializeOpenTelemetry } = await import('./lib/telemetry/otel-node');
    initializeOpenTelemetry();
  }
}
```

### 3. `src/lib/telemetry/otel-node.ts`
```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { PeriodicExportingMetricReader, ConsoleMetricExporter } from '@opentelemetry/sdk-metrics';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';

export function initializeOpenTelemetry(): void {
  // Aktifkan logging internal OTel untuk debugging konfigurasi lokal jika diperlukan
  if (process.env.NODE_ENV === 'development') {
    diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.INFO);
  }

  const traceExporter = new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317',
  });

  const sdk = new NodeSDK({
    resource: new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'nextjs-enterprise-service',
      [SemanticResourceAttributes.SERVICE_VERSION]: process.env.APP_VERSION || '1.0.0',
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'production',
    }),
    traceExporter,
    instrumentations: [
      new HttpInstrumentation({
        // Abaikan route internal Next.js dan static assets agar tidak membebani tracing collector
        ignoreIncomingRequestHook: (req) => {
          const url = req.url || '';
          return (
            url.startsWith('/_next/') ||
            url.startsWith('/static/') ||
            url === '/api/health/liveness' ||
            url === '/api/health/readiness' ||
            url === '/favicon.ico'
          );
        },
      }),
    ],
  });

  try {
    sdk.start();
    console.log('[Telemetri] OpenTelemetry NodeSDK berhasil diinisialisasi.');
  } catch (error) {
    console.error('[Telemetri] Gagal menginisialisasi OpenTelemetry NodeSDK:', error);
  }

  // Graceful shutdown ketika container menerima sinyal terminasi dari kernel
  process.on('SIGTERM', () => {
    sdk
      .shutdown()
      .then(() => console.log('[Telemetri] OpenTelemetry SDK berhasil di-terminate.'))
      .catch((error) => console.error('[Telemetri] Error saat terminasi OTel SDK:', error))
      .finally(() => process.exit(0));
  });
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Pada implementasi `src/lib/telemetry/otel-node.ts`:
1. `export function initializeOpenTelemetry(): void`: Mendeklarasikan entry point terisolasi yang dipanggil secara dinamis oleh `instrumentation.ts` hanya di environment Node.js.
2. `diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.INFO)`: Menyediakan logging diagnosa internal untuk memvalidasi apakah exporter berhasil melakukan *handshake* dengan OpenTelemetry Collector via protocol gRPC.
3. `const traceExporter = new OTLPTraceExporter({...})`: Menggunakan transport gRPC standar industri menuju target endpoint (port 4317). gRPC mengonsumsi resource CPU dan bandwidth jaringan lebih rendah dibanding JSON/HTTP karena menggunakan HTTP/2 dan protocol buffers.
4. `[SemanticResourceAttributes.SERVICE_NAME]: 'nextjs-enterprise-service'`: Menginjeksikan metadata resmi sesuai standar semantic convention OpenTelemetry, mempermudah aggregasi metrik lintas cluster.
5. `new HttpInstrumentation({ ignoreIncomingRequestHook: ... })`: Konfigurasi krusial untuk mencegah *telemetry noise*. Next.js menghasilkan ratusan request internal untuk image optimization, chunks, dan static assets. Menyaring URL internal dan probe endpoint (`/api/health/*`) menghemat kuota transmisi APM dan storage secara masif.
6. `process.on('SIGTERM', () => { sdk.shutdown()... })`: Mengaitkan siklus hidup telemetri ke lifecycle termination container Kubernetes. Ini mencegah hilangnya span trace (*data loss*) yang masih tertahan di buffer in-memory saat Pod dihentikan secara sepihak.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: "The Flash Sale Black Swan Failure"
Sebuah platform E-Commerce berskala Tier-1 mengalami lonjakan traffic dari 5.000 RPS menjadi 85.000 RPS saat kampanye flash sale tengah malam.

### Gejala Masalah:
* Aplikasi Next.js App Router mengalami lonjakan p99 response time dari 120ms menjadi 28.000ms.
* CPU utilization pada Pod Kubernetes stabil di level 40%, namun memory terus menanjak hingga memicu Pod restart berulang kali (*OOMKilled* / Out-Of-Memory).
* Pengguna menerima HTTP 504 Gateway Timeout secara sporadis dari load balancer Ingress.

### Investigasi Mendalam (*Root-Cause Analysis*):
1. **Tracing Analysis:** Melalui distributed trace Jaeger, ditemukan bahwa Server Components mengeksekusi panggilan downstream ke `Inventory-Service` yang mengalami lockup database.
2. **Ketiadaan Circuit Breaker & Timeout:** Setiap request SSR menunggu socket downstream selama default OS TCP timeout (120 detik). Akibatnya puluhan ribu request tertahan di Node.js memory space.
3. **Socket Exhaustion:** Node.js event loop kehabisan File Descriptors (FD) dan active handles. Ketiadaan backoff strategy menyebabkan frontend melakukan spamming retry ke backend yang sekarat, memperparah degradasi (*retry storm*).

### Solusi Arsitektural:
* Mengisolasi downstream caller menggunakan circuit breaker (`opossum`) dengan limit timeout agresif (1.5 detik) dan fallback response terdegradasi secara elegan (menampilkan cached catalog data).
* Mengubah container packaging ke mode standalone dengan non-root secure Alpine image, serta mengonfigurasi startup, liveness, dan readiness probe secara akurat di Kubernetes deployment manifest.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem resiliensi enterprise lengkap, custom tracer, logger berkorelasi trace ID, dan artifact deployment container Kubernetes.

### 1. `src/lib/resilience/circuit-breaker.ts`
```typescript
import CircuitBreaker from 'opossum';
import { trace, SpanStatusCode } from '@opentelemetry/api';

interface CircuitBreakerOptions {
  timeout: number;
  errorThresholdPercentage: number;
  resetTimeout: number;
}

const DEFAULT_OPTIONS: CircuitBreakerOptions = {
  timeout: 1500, // Trigger timeout jika downstream tidak merespons dalam 1.5 detik
  errorThresholdPercentage: 50, // Buka sirkuit jika 50% request gagal dalam window period
  resetTimeout: 10000, // Waktu tunggu 10 detik sebelum mencoba status HALF-OPEN
};

export function createResilientCaller<TArgs extends unknown[], TReturn>(
  fn: (...args: TArgs) => Promise<TReturn>,
  actionName: string,
  options: Partial<CircuitBreakerOptions> = {}
): (...args: TArgs) => Promise<TReturn> {
  const finalOptions = { ...DEFAULT_OPTIONS, ...options };
  const breaker = new CircuitBreaker(fn, finalOptions);

  breaker.on('open', () => {
    console.warn(`[CIRCUIT_BREAKER_ALERT] Sirkuit ${actionName} beralih ke status: OPEN. Fail-fast diaktifkan.`);
  });

  breaker.on('halfOpen', () => {
    console.info(`[CIRCUIT_BREAKER_INFO] Sirkuit ${actionName} beralih ke status: HALF-OPEN. Menguji downstream.`);
  });

  breaker.on('close', () => {
    console.info(`[CIRCUIT_BREAKER_INFO] Sirkuit ${actionName} kembali ke status: CLOSED. Downstream normal.`);
  });

  return async (...args: TArgs): Promise<TReturn> => {
    const tracer = trace.getTracer('resilience-layer');
    return tracer.startActiveSpan(`CircuitBreaker:${actionName}`, async (span) => {
      span.setAttribute('circuit.action', actionName);
      span.setAttribute('circuit.state', breaker.status.stats.fires > 0 ? (breaker.opened ? 'OPEN' : 'CLOSED') : 'INITIAL');

      try {
        const result = await (breaker.fire(...args) as Promise<TReturn>);
        span.setStatus({ code: SpanStatusCode.OK });
        return result;
      } catch (error: unknown) {
        const err = error as Error;
        span.recordException(err);
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: err.message || 'Downstream failure inside breaker execution',
        });
        throw err;
      } finally {
        span.end();
      }
    });
  };
}
```

### 2. `src/lib/telemetry/logger.ts`
```typescript
import winston from 'winston';
import { trace } from '@opentelemetry/api';

const customFormat = winston.format.printf(({ level, message, timestamp, ...meta }) => {
  const currentSpan = trace.getActiveSpan();
  const spanContext = currentSpan ? currentSpan.spanContext() : undefined;

  const logPayload = {
    timestamp,
    level,
    message,
    trace_id: spanContext ? spanContext.traceId : 'none',
    span_id: spanContext ? spanContext.spanId : 'none',
    trace_flags: spanContext ? spanContext.traceFlags : 0,
    ...meta,
  };

  return JSON.stringify(logPayload);
});

export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DDTHH:mm:ss.SSSZ' }),
    customFormat
  ),
  defaultMeta: { service: 'nextjs-ecommerce-frontend' },
  transports: [
    new winston.transports.Console(),
  ],
});
```

### 3. `src/app/api/products/[id]/route.ts` (Implementasi Resilient Route Handler)
```typescript
import { NextRequest, NextResponse } from 'next/server';
import { createResilientCaller } from '@/lib/resilience/circuit-breaker';
import { logger } from '@/lib/telemetry/logger';
import { trace } from '@opentelemetry/api';

interface ProductData {
  id: string;
  name: string;
  stock: number;
  price: number;
}

// Simulasi panggilan downstream raw network I/O
async function fetchProductFromInventoryService(productId: string): Promise<ProductData> {
  const inventoryServiceUrl = process.env.INVENTORY_SERVICE_URL || 'http://inventory-api.internal:8080';
  const response = await fetch(`${inventoryServiceUrl}/api/v1/products/${productId}`, {
    headers: { 'Content-Type': 'application/json' },
    // Next.js caching strategy
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`Downstream inventory service returned HTTP status ${response.status}`);
  }

  return response.json() as Promise<ProductData>;
}

// Membungkus service call dengan Circuit Breaker
const resilientFetchProduct = createResilientCaller(
  fetchProductFromInventoryService,
  'fetchProductFromInventoryService',
  { timeout: 1200, errorThresholdPercentage: 40 }
);

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  const productId = params.id;
  const currentTracer = trace.getTracer('next-route-handler');

  return currentTracer.startActiveSpan('GET /api/products/[id]', async (span) => {
    span.setAttribute('product.id', productId);
    logger.info('Menerima request query product data', { productId });

    try {
      const product = await resilientFetchProduct(productId);
      return NextResponse.json({ success: true, data: product });
    } catch (error: unknown) {
      const err = error as Error;
      logger.error('Gagal mengeksekusi pemanggilan product downstream service', {
        productId,
        errorMessage: err.message,
        errorStack: err.stack,
      });

      // Fallback graceful degradation response
      if (err.message.includes('Timed out') || err.message.includes('Breaker is open')) {
        return NextResponse.json(
          {
            success: false,
            fallback: true,
            message: 'Layanan inventori sedang mengalami degradasi beban traffic. Menampilkan estimasi cached data.',
            data: { id: productId, name: 'Standard Product', stock: 0, price: 0 },
          },
          { status: 200 } // Status 200 dengan degraded payload agar client frontend tidak crash
        );
      }

      return NextResponse.json(
        { success: false, message: 'Internal Server Error' },
        { status: 500 }
      );
    } finally {
      span.end();
    }
  });
}
```

### 4. `Dockerfile` (Multi-stage Standalone Enterprise Grade)
```dockerfile
# -----------------------------------------------------------------------------
# STAGE 1: Dependency Resolver
# -----------------------------------------------------------------------------
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# -----------------------------------------------------------------------------
# STAGE 2: Build Artifact Engine
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Eksekusi build Next.js (menghasilkan .next/standalone via output: 'standalone')
RUN npm run build

# -----------------------------------------------------------------------------
# STAGE 3: Minimal Production Runtime Runner
# -----------------------------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Buat grup dan pengguna non-root demi aspek keamanan container isolation
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Salin aset publik dan minimal server chunk
COPY --from=builder /app/public ./public

# Tetapkan hak akses direktori cache ke user non-root
RUN mkdir .next && chown nextjs:nodejs .next

# Salin output standalone otomatis dari trace dependency builder
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# Server Next.js standalone dijalankan secara native oleh node tanpa npm lifecycle
CMD ["node", "server.js"]
```

### 5. `k8s-deployment.yaml` (Kubernetes Production Manifest)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nextjs-enterprise-frontend
  namespace: production
  labels:
    app: nextjs-frontend
    tier: frontend
spec:
  replicas: 4
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 0
  selector:
    matchLabels:
      app: nextjs-frontend
  template:
    metadata:
      labels:
        app: nextjs-frontend
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
      containers:
        - name: nextjs-container
          image: registry.internal.company.com/frontend/nextjs-app:v1.4.2
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 3000
              protocol: TCP
          env:
            - name: NODE_ENV
              value: "production"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector.observability.svc.cluster.local:4317"
            - name: OTEL_SERVICE_NAME
              value: "nextjs-frontend-prod"
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2000m"
              memory: "1536Mi"
          # Lifecycle probe yang presisi untuk eliminasi downtime
          startupProbe:
            httpGet:
              path: /api/health/liveness
              port: 3000
            failureThreshold: 30
            periodSeconds: 2
            timeoutSeconds: 2
          livenessProbe:
            httpGet:
              path: /api/health/liveness
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /api/health/readiness
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 2
---
apiVersion: v1
kind: Service
metadata:
  name: nextjs-frontend-service
  namespace: production
spec:
  type: ClusterIP
  selector:
    app: nextjs-frontend
  ports:
    - name: http
      port: 80
      targetPort: 3000
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Next.js Node.js Standalone Runtime | Serverless Edge Runtime (Vercel Edge/Cloudflare) | Next.js Serverless Container (AWS ECS Fargate) |
| :--- | :--- | :--- | :--- |
| **Footprint Memori** | Menetap (512MB - 1.5GB baseline). Caching I/O in-memory stabil. | Ultra-rendah (<128MB per isolate). Tidak ada shared memory state. | Menengah-Tinggi (Berbagi compute base, scaling bertahap). |
| **Startup / Latency** | Cold start awal saat pod init (~10-30 detik). Tidak ada cold-start per HTTP request. | Nyaris nol cold-start (~5-15ms). Cocok untuk routing global. | Cold-start kontainer menengah (1-3 menit untuk scaling baru). |
| **Tracing & OTel Support** | **Dukungan Penuh (Full Protocol).** Mendukung monkey patching native Node.js. | **Terbatas.** Tidak mendukung library native `node:*` atau socket gRPC langsung. | **Dukungan Penuh.** Mirip dengan Standalone di K8s. |
| **Kapasitas Koneksi DB** | Stabil melalui Connection Pooling (PgBouncer/Prisma pool di runtime). | Rentan mengeksekusi koneksi exhaustion tanpa Data Proxy khusus. | Relatif stabil bergantung batas task limit. |
| **Resiliensi Circuit Breaker** | State breaker dipertahankan di memory worker thread aplikasi. | Sulit diaplikasikan secara terisolasi tanpa eksternal KV store. | State breaker dipertahankan secara stabil di setiap Task instance. |
| **Efisiensi Finansial** | Sangat tinggi pada traffic konsisten besar via reserved Kubernetes nodes. | Sangat hemat pada traffic bursty; mahal pada volume traffic konstan tinggi. | Biaya per vCPU/RAM lebih mahal dibanding bare metal K8s. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Headless Static Chunk Mismatch (Canary Deployment Trap)
* **Kasus:** Saat Canary deployment melepaskan v2 secara bertahap (misal 10%), user client yang sedang membuka v1 menerima HTML dari pod v1. Namun, saat user bernavigasi ke route lain, browser me-request resource `.next/static/chunks/app-route-xyz.js`. Jika request chunk diarahkan ke pod v2 oleh load balancer dan hash file berbeda, server me-return **HTTP 404 ChunkLoadError**.
* **Mitigasi:** Simpan seluruh compiled static assets (`.next/static`) ke dalam Object Storage eksternal terpusat (AWS S3/Cloudflare R2) yang berada di balik Global CDN dengan `assetPrefix`. Pod v1 dan v2 hanya memproses data dynamic, sementara chunk statis selalu tersedia di CDN secara independen dari lifecycle pod.

### 2. Node.js Dynamic Import Inside Async Spans
* **Kasus:** Melakukan lazy import modul di dalam active tracing span dapat menyebabkan context propagation hilang jika asynchronous continuation context terputus oleh engine V8 promise resolution yang belum di-patch oleh OTel context manager.
* **Mitigasi:** Selalu pastikan instrumentasi SDK dieksekusi secara sinkron di file `instrumentation.ts` dan hindari memanggil runtime initialization di dalam handler request individual.

### 3. File Descriptor Leak Melalui Unclosed Telemetry Sockets
* **Kasus:** Membuka HTTP exporter trace baru pada setiap kali span dibuat atau me-reinstantiate OpenTelemetry SDK pada setiap route rendering.
* **Mitigasi:** Inisialisasi SDK hanya sekali menggunakan singleton pattern yang dijamin oleh lifecycle hook `register()` di file `instrumentation.ts`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menjalankan Next.js Menggunakan Perintah `npm start` di Production Container
* **Kesalahan:** Menuliskan `CMD ["npm", "run", "start"]` di Dockerfile.
* **Dampak Buruk:** NPM berjalan sebagai Process ID (PID) 1. NPM tidak meneruskan signal `SIGTERM` atau `SIGINT` dari Linux kernel ke sub-proses