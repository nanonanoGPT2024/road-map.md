# Modul 02: Deep Dive Observabilitas, Pola Resiliensi & Arsitektur Deployment Skala Enterprise (Next.js App Router)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengonfigurasi dan mengoperasikan instrumentasi **OpenTelemetry (OTel)** secara *native* pada Next.js (Node.js & Edge Runtime) untuk mengekspor distributed traces dan metrics ke OpenTelemetry Collector/APM (Datadog, New Relic, Grafana Tempo).
- Mengimplementasikan propagasi konteks *tracing* end-to-end melintasi Edge Middleware, React Server Components (RSC), Server Actions, Route Handlers, dan downstream microservices menggunakan `AsyncLocalStorage` dan W3C Trace Context (`traceparent`).
- Membangun pola resiliensi aplikasi (*Circuit Breaker*, *Exponential Backoff with Jitter*, *Bulkheading*, dan *Fallback Caching*) pada layer komputasi Next.js untuk mencegah kegagalan kaskade (*cascading failures*).
- Merancang dan mengeksekusi pipeline deployment skala besar nir-henti (*Zero-Downtime Deployment*) berbasis Docker `standalone` output di Kubernetes (EKS/GKE) menggunakan strategi *Canary Deployment*, *Graceful Shutdown*, serta integrasi multi-region read-replicas.
- Mengidentifikasi dan memitigasi degradasi performa kritis seperti *waterfall data fetching* pada RSC, kebocoran memori pada Node.js runtime container, dan *cold start latency* pada runtime serverless.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Next.js Core Architecture**: Pemahaman mendalam tentang App Router, React Server Components (RSC) vs Client Components, Streaming SSR, dan Suspense architecture.
- **Node.js Internals**: Pemahaman tentang Event Loop, `AsyncLocalStorage`, worker threads, dan penanganan sinyal OS (`SIGTERM`, `SIGINT`).
- **Networking & Distributed Systems**: Protokol HTTP/2, HTTP/3, gRPC, W3C Trace Context spec, DNS routing, dan TLS termination.
- **Containerization & Orchestration**: Docker multi-stage builds, Kubernetes primitive resources (Deployment, Service, Ingress, HPA, PDB, ConfigMap/Secret).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. OpenTelemetry & Native Instrumentation Hook (`instrumentation.ts`)

Next.js menyediakan antarmuka hook native bernama `register()` yang didefinisikan di dalam file `instrumentation.ts` (pada *root* direktori atau di dalam `src/`). File ini dieksekusi sekali ketika instance server Next.js diinisialisasi, sebelum kode aplikasi lainnya memproses request masuk.

```
+-----------------------------------------------------------------------------------+
| Next.js Process Initialization Lifecycle                                         |
|                                                                                   |
|  [Node.js Boot] ---> [instrumentation.ts: register()]                            |
|                             |                                                     |
|                             +---> Runtime Check: process.env.NEXT_RUNTIME         |
|                             |        |                                            |
|                             |        +---> 'nodejs': Inisialisasi NodeSDK         |
|                             |        |     (Auto-instrumentations: HTTP, Fetch,    |
|                             |        |      Pg, Redis, dll)                       |
|                             |        |                                            |
|                             |        +---> 'edge': Minimal Web APIs Tracer        |
|                             |                                                     |
|                             v                                                     |
|  [Server Ready] ---> [Middleware] ---> [RSC / Route Handlers]                    |
+-----------------------------------------------------------------------------------+
```

Di balik layar, Next.js membungkus runtime HTTP Server bawaan menggunakan OTel API. Ketika fitur eksperimental `instrumentationHook = true` diaktifkan (sudah default stabil pada versi modern), Next.js secara otomatis menghasilkan span internal untuk:
1. `BaseServer.handleRequest`: Span level tertinggi yang menangkap seluruh siklus hidup HTTP request.
2. `Render.renderToHTML` / `AppRender`: Tracing proses rendering React Server Components menjadi serialized flight data (RSC Payload) dan HTML streaming.
3. `AppRouteRouteHandlers.run`: Tracing eksekusi custom Route Handler (`app/api/.../route.ts`).
4. `ResolveMetadata`: Tracing proses resolusi dynamic metadata.

Tantangan arsitektur terbesar adalah lingkungan runtime hibrida: Next.js membagi eksekusi antara **Node.js Full Runtime** dan **V8 Edge Runtime**. Edge runtime tidak memiliki akses ke API internal Node.js (seperti `net`, `tls`, `fs`), sehingga OTel NodeSDK konvensional tidak dapat dijalankan di layer Edge. Solusinya memerlukan strategi seleksi runtime adaptif berbasis `process.env.NEXT_RUNTIME`.

### 3.2. Propagasi W3C Trace Context via AsyncLocalStorage

Pada arsitektur Next.js App Router, pemanggilan fetch bersarang (*nested fetch*) di dalam RSC tidak memiliki akses langsung ke objek `IncomingMessage` (req/res) klasik seperti di Express.js atau Pages Router. 

Untuk melacak siklus request dan meneruskan distributed context header (`traceparent`, `tracestate`, `x-correlation-id`) ke downstream API, Next.js memanfaatkan `AsyncLocalStorage` (ALS). Melalui ALS, context tracing diikat secara implisit ke rantai asinkron eksekusi:

```
[Incoming Request] (Headers: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01)
         |
         v
[Edge/Node Middleware] 
         |  (Ekstraksi traceparent, enkapsulasi Trace ID ke ALS & Request Headers)
         v
[React Server Component Tree]
   ├── <Header />  ---> [ALS Context: trace-id-xyz]
   └── <Feed />
         └── fetch('https://api.internal/posts')
               │
               └──> OTel Fetch Auto-Instrumentor menginjeksi:
                    "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-<new_span_id>-01"
```

### 3.3. Graceful Shutdown & Kubernetes Lifecycle

Ketika pod Next.js menerima sinyal terminasi (`SIGTERM`) dari kubelet, proses tidak boleh langsung mati karena masih ada request inflight yang sedang melakukan *streaming payload* ke browser klien. 

Siklus terminasi enterprise memerlukan tahapan:
1. Pod diubah statusnya menjadi `Terminating`, endpoints controller mencabut pod dari Service endpoints (mencegah *ingress* mengirim request baru).
2. `preStop` hook container dijalankan (misal: `sleep 10-15`) untuk memberi jeda propagasi iptables/IPVS di seluruh cluster node.
3. Server Next.js menangkap sinyal `SIGTERM`, berhenti menerima koneksi baru (`server.close()`), menyelesaikan seluruh active stream rendering, menutup koneksi database pool / persistent socket, dan flush buffer OTel spans ke collector sebelum exit code 0.

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional / Pemula | Pendekatan Enterprise Skala Besar |
| :--- | :--- | :--- |
| **Observabilitas** | `console.log` berbasis teks mentah yang terdistribusi acak; APM dipasang lewat monkey-patching runtime runtime client. | Distributed Tracing W3C compliant via OTel native spans; Structured JSON logging dengan metadata standar (`trace_id`, `span_id`, `service.name`, `environment`). |
| **Pola Fetching** | Raw native `fetch` tanpa kontrol timeout; tidak ada mekanisme fallback jika upstream down. | Resilient Client Wrapper: Circuit Breaker pattern, jittered backoff, adaptive deadline propagation, dan fallback stale-while-revalidate caching. |
| **Manajemen State Request** | Meneruskan correlation ID manual via props drilling antar komponen RSC. | Transparent Context Propagation menggunakan Node.js `AsyncLocalStorage` atau React `cache()` request boundary memoization. |
| **Deployment** | Build image monolitik besar; update deployment direct rolling tanpa drain time; downtime mikro saat rollout. | Docker Multi-Stage Standalone build (<150MB); Canary Deployment dengan traffic shifting terukur via Argo Rollouts / Flagger; Health Check probes terpisah (Liveness/Readiness/Startup). |

---

## 5. Workflow: Ingestion, Tracing, dan Resilient Execution

Alur kerja pemrosesan request enterprise diilustrasikan dalam diagram berikut:

```
User Request
    │
    ▼
[ Cloudflare / CloudFront CDN ]
    │ (Inject: X-Request-ID, CF-Ray-ID)
    ▼
[ Ingress Controller / ALB ]
    │ (Traffic Splitting: Canary 5% vs Stable 95%)
    ▼
[ Next.js Pod: Node.js HTTP Server ]
    │
    ├─► Phase 1: Middleware
    │     - Validasi Session / Auth Token
    │     - Rate Limiter check (Redis Sliding Window via Upstash/Dragonfly)
    │     - Sinkronisasi X-Correlation-ID & W3C Traceparent
    │
    ├─► Phase 2: RSC Executive Phase (Stream Render)
    │     - OTel Span: "AppRender.renderToStream"
    │     - Fetch Call Wrapper (Circuit Breaker status check)
    │     - IF Circuit == OPEN -> Return Degraded Fallback RSC (Cached View)
    │     - IF Circuit == CLOSED -> Execute HTTP/gRPC ke Core Microservice
    │
    ├─► Phase 3: Response Streaming
    │     - HTTP 200 OK Chunked Transfer-Encoding
    │     - Flush OpenTelemetry span metrics ke OTel Daemonset Pod (gRPC port 4317)
    │
    └─► Phase 4: Termination Handling (Pada event SIGTERM)
          - Stop new listeners -> Flush OpenTelemetry Provider -> Drain DB Connections -> Exit 0
```

---

## 6. Analogi & Diagram ASCII

Bayangkan sebuah **Bandara Internasional (Arsitektur Next.js)**:
- **Penumpang (Incoming HTTP Request)** membawa paspor unik dengan stempel transit (**W3C Trace Context / `traceparent`**).
- **Petugas Imigrasi (Middleware)** memeriksa visa dan stempel. Jika dokumen valid, ia mencatat ID penumpang di buku log pusat (**Distributed Tracer**) dan memberikan boarding pass bertanda khusus.
- **Lounge & Gate (React Server Components)**: Penumpang masuk ke gerbang yang berbeda. Di dalam gerbang, ada layanan katering (**Upstream Microservices**).
- **Circuit Breaker**: Jika katering di Gate 4 terbakar (**Microservice Outage**), staf tidak membiarkan penumpang kelaparan menunggu tanpa kepastian. Mereka segera menyajikan makanan cadangan instan yang sudah diawetkan (**Fallback Stale Cache**), mencegah seluruh penerbangan tertunda (**Cascading Failure**).
- **OTel Collector**: Menara pengawas yang memantau pergerakan setiap penumpang dari pintu masuk, boarding, hingga lepas landas secara real-time.

```
       +--------------------------------------------------------------+
       |               DISTRIBUTED SYSTEM BOUNDARY                     |
       +--------------------------------------------------------------+
                                      │
[Incoming Request]                    ▼
───────────────────► [Next.js Edge Middleware]
                      │ (Extracts: traceparent: 00-abc...-01)
                      ├──────────────────────────┐
                      ▼                          ▼
             [Node.js RSC Render]        [OTel Trace Collector]
                      │                  (Spans: Processing Time,
                      │                   Memory Usage, Status)
                      ▼                          ▲
             [Circuit Breaker Engine]            │
             ┌────────┴────────┐                 │
    (State: CLOSED)     (State: OPEN)            │
             │                 │                 │
             ▼                 ▼                 │
      [Upstream API]    [Fallback SWR Cache]     │
             │                 │                 │
             └────────┬────────┘                 │
                      ▼                          │
             [Downstream Response] ──────────────┘
```

---

## 7. Simple & Practical Code Implementation

Berikut adalah implementasi standar industri untuk instrumentasi, observabilitas, dan penanganan ketahanan (*resilience*).

### 7.1. Inisialisasi OpenTelemetry Multi-Runtime (`instrumentation.ts`)

```typescript
// instrumentation.ts
export async function register() {
  // Hanya inisialisasi OTel NodeSDK jika berada di Node.js runtime environment
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { NodeSDK } = await import('@opentelemetry/sdk-node');
    const { OTLPTraceExporter } = await import('@opentelemetry/exporter-trace-otlp-grpc');
    const { Resource } = await import('@opentelemetry/resources');
    const { SemanticResourceAttributes } = await import('@opentelemetry/semantic-conventions');
    const { SimpleSpanProcessor } = await import('@opentelemetry/sdk-trace-base');
    const { getNodeAutoInstrumentations } = await import('@opentelemetry/auto-instrumentations-node');

    const traceExporter = new OTLPTraceExporter({
      url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://otel-collector.monitoring.svc.cluster.local:4317',
    });

    const sdk = new NodeSDK({
      resource: new Resource({
        [SemanticResourceAttributes.SERVICE_NAME]: 'enterprise-nextjs-bff',
        [SemanticResourceAttributes.SERVICE_VERSION]: process.env.NEXT_PUBLIC_APP_VERSION || '1.0.0',
        [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'production',
      }),
      spanProcessor: new SimpleSpanProcessor(traceExporter),
      instrumentations: [
        getNodeAutoInstrumentations({
          // Nonaktifkan fs instrumentation untuk menghindari tracing disk read berlebihan pada RSC
          '@opentelemetry/instrumentation-fs': { enabled: false },
          '@opentelemetry/instrumentation-http': {
            enabled: true,
            ignoreIncomingRequestHook: (req) => {
              // Abaikan health check probes agar tidak mencemari telemetry metrics
              return req.url?.includes('/api/health') || req.url?.includes('/api/ready');
            },
          },
        }),
      ],
    });

    sdk.start();

    // Pastikan flush metrics saat instance dimatikan
    process.on('SIGTERM', () => {
      sdk.shutdown()
        .then(() => console.log('[OTel SDK] Terminated successfully'))
        .catch((err) => console.error('[OTel SDK] Termination error', err))
        .finally(() => process.exit(0));
    });
  }
}
```

### 7.2. Resilient Fetch Client dengan Circuit Breaker & Distributed Tracing

```typescript
// lib/resilience/resilient-fetch.ts
import { trace, context, SpanStatusCode } from '@opentelemetry/api';

enum CircuitState {
  CLOSED,
  OPEN,
  HALF_OPEN,
}

interface CircuitBreakerOptions {
  failureThreshold: number; // Jumlah failure sebelum circuit open
  recoveryTimeout: number;  // Durasi (ms) menunggu sebelum beralih ke HALF_OPEN
  requestTimeout: number;   // Timeout request individual (ms)
}

class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private nextAttempt: number = Date.now();

  constructor(private name: string, private options: CircuitBreakerOptions) {}

  public async execute<T>(fn: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
    const tracer = trace.getTracer('resilience-tracer');
    
    return tracer.startActiveSpan(`CircuitBreaker.${this.name}`, async (span) => {
      span.setAttribute('circuit.state', CircuitState[this.state]);

      if (this.state === CircuitState.OPEN) {
        if (Date.now() > this.nextAttempt) {
          this.state = CircuitState.HALF_OPEN;
          span.setAttribute('circuit.state_transition', 'HALF_OPEN');
        } else {
          span.setStatus({ code: SpanStatusCode.OK, message: 'Degraded Fallback Invoked' });
          span.setAttribute('circuit.short_circuited', true);
          span.end();
          return fallback();
        }
      }

      try {
        const result = await Promise.race([
          fn(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error(`Timeout after ${this.options.requestTimeout}ms`)), this.options.requestTimeout)
          ),
        ]);

        this.onSuccess();
        span.setStatus({ code: SpanStatusCode.OK });
        span.end();
        return result;
      } catch (err: any) {
        this.onFailure(err);
        span.recordException(err);
        span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
        span.end();
        return fallback();
      }
    });
  }

  private onSuccess() {
    this.failureCount = 0;
    this.state = CircuitState.CLOSED;
  }

  private onFailure(error: Error) {
    this.failureCount++;
    if (this.failureCount >= this.options.failureThreshold || this.state === CircuitState.HALF_OPEN) {
      this.state = CircuitState.OPEN;
      this.nextAttempt = Date.now() + this.options.recoveryTimeout;
    }
  }
}

// Registry Circuit Breaker singleton
const breakerRegistry = new Map<string, CircuitBreaker>();

export function getCircuitBreaker(name: string, options?: Partial<CircuitBreakerOptions>): CircuitBreaker {
  if (!breakerRegistry.has(name)) {
    breakerRegistry.set(
      name,
      new CircuitBreaker(name, {
        failureThreshold: options?.failureThreshold ?? 5,
        recoveryTimeout: options?.recoveryTimeout ?? 30000,
        requestTimeout: options?.requestTimeout ?? 3000,
      })
    );
  }
  return breakerRegistry.get(name)!;
}
```

### 7.3. Implementasi Konsumsi Data pada React Server Component

```tsx
// app/dashboard/inventory/page.tsx
import { Suspense } from 'react';
import { getCircuitBreaker } from '@/lib/resilience/resilient-fetch';
import { headers } from 'next/headers';

interface ProductInventory {
  sku: string;
  availableStock: number;
  isDegraded?: boolean;
}

async function fetchInventoryData(): Promise<ProductInventory[]> {
  const correlationId = (await headers()).get('x-correlation-id') || 'untracked-req';
  const breaker = getCircuitBreaker('core-inventory-service', {
    failureThreshold: 3,
    recoveryTimeout: 15000,
    requestTimeout: 2000,
  });

  return breaker.execute(
    // Operasi Utama
    async () => {
      const res = await fetch('https://inventory.internal.domain/v1/stocks', {
        headers: {
          'Content-Type': 'application/json',
          'X-Correlation-ID': correlationId,
        },
        // Revalidasi internal data cache Next.js
        next: { revalidate: 60, tags: ['inventory-data'] },
      });

      if (!res.ok) {
        throw new Error(`Upstream returned status ${res.status}`);
      }

      return res.json();
    },
    // Fallback Logic (Ketika upstream timeout / circuit breaker OPEN)
    async () => {
      console.warn(`[CIRCUIT-BREAKER] Degrading inventory data for req: ${correlationId}`);
      return [
        { sku: 'DEFAULT-SKU-1', availableStock: 0, isDegraded: true },
        { sku: 'DEFAULT-SKU-2', availableStock: 0, isDegraded: true },
      ];
    }
  );
}

export default async function InventoryPage() {
  const inventory = await fetchInventoryData();

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-4">Enterprise Inventory Dashboard</h1>
      {inventory.some((i) => i.isDegraded) && (
        <div className="bg-amber-100 border border-amber-400 text-amber-700 px-4 py-3 rounded mb-4" role="alert">
          <strong>Perhatian:</strong> Sistem sedang mengalami gangguan parsial. Data stok ditampilkan dalam mode *read-only fallback*.
        </div>
      )}
      <table className="min-w-full divide-y divide-gray-200">
        <thead>
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">SKU</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stock</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {inventory.map((item) => (
            <tr key={item.sku}>
              <td className="px-6 py-4 whitespace-nowrap">{item.sku}</td>
              <td className="px-6 py-4 whitespace-nowrap">{item.availableStock}</td>
              <td className="px-6 py-4 whitespace-nowrap">
                {item.isDegraded ? (
                  <span className="text-red-500 font-semibold">Cached / Outdated</span>
                ) : (
                  <span className="text-green-600 font-semibold">Live Operational</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
```

### 7.4. Health Check Endpoints (K8s Liveness & Readiness)

Next.js Route Handlers digunakan secara presisi untuk memisahkan status ketersediaan node:

```typescript
// app/api/health/liveness/route.ts
// Liveness probe: Memastikan instance Node.js tidak mengalami deadlock / freeze
export async function GET() {
  return new Response(JSON.stringify({ status: 'UP', timestamp: Date.now() }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
```

```typescript
// app/api/health/readiness/route.ts
// Readiness probe: Memastikan pod siap melayani traffic (misal: koneksi OTel Collector/Redis downstream aman)
export async function GET() {
  try {
    // Sisipkan pengecekan dependensi kritis jika perlu (contoh: status Redis)
    const isReady = true; 

    if (!isReady) {
      return new Response(JSON.stringify({ status: 'DEGRADED', reason: 'Cache unavailable' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ status: 'READY' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return new Response(JSON.stringify({ status: 'UNHEALTHY', error: (error as Error).message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash Sale E-Commerce Platform Global Tier-1
- **Traffic Profile**: 150.000 Requests Per Second (RPS) pada puncaknya.
- **Masalah Utama**: Selama promo Midnight Flash Sale, backend API inventory mengalami lonjakan latensi dari 45ms ke 12.000ms akibat lock contention pada basis data Postgres. Hal ini menyebabkan penumpukan eksekusi fetch pada layer Next.js SSR/RSC. Node.js thread pool kehabisan resource, memori melonjak hingga pod mengalami restart berantai akibat *OOMKilled* (Out Of Memory).

### Solusi Arsitektural:
1. **Adaptive Edge Rate Limiting**: Dipasang pada Cloudflare Workers & Next.js Edge Middleware dengan Redis Token Bucket per IP/User Session. Traffic non-transaksional dibatasi hingga 20 req/menit.
2. **Circuit Breaker dengan SWR Hydration**: Ketika inventory API mencapai timeout > 1.5 detik sebanyak 10 kali dalam jendela 10 detik, sirkuit berstatus OPEN. Next.js langsung menyajikan RSC payload dari *stale-cache* yang disimpan pada level In-Memory LRU/Redis layer tanpa menyentuh core API.
3. **Optimasi Docker Standalone & Memory Management**:
   Set alokasi memory limit Node.js secara deterministik:
   `node --max-old-space-size=1536 server.js` di dalam container dengan memory limit Kubernetes 2048Mi (memberikan headroom 512MB untuk OS dan OTel exporter buffers).
4. **Traffic Shifting via Canary**:
   Setiap update UI dideploy menggunakan Argo Rollouts: 5% traffic diarahkan ke pods baru selama 10 menit, dievaluasi berdasarkan metrik *Error Rate OTel < 0.1%* dan *p99 latency < 250ms*. Jika terlampaui, otomatis rollback seketika (*zero-downtime automated rollback*).

---

## 9. Trade-offs (Analisis Komparasi Kritis)

```
+-----------------------------------------------------------------------------------------+
|                  ARCHITECTURAL TRADE-OFF MATRIX                                         |
+----------------------+---------------------------+--------------------------------------+
| Pendekatan           | Keuntungan                | Konsekuensi / Biaya (Trade-offs)     |
+----------------------+---------------------------+--------------------------------------+
| In-Memory Circuit    | Latensi microsecond;      | Status tidak tersinkronisasi antar   |
| Breaker per Pod      | zero infrastructure cost; | replika pod; pod baru akan tetap     |
|                      | tidak butuh Redis.        | mengirim request ke API yang rusak.  |
+----------------------+---------------------------+--------------------------------------+
| Centralized Breaker  | Status global konsisten   | Latensi round-trip Redis (+2-5ms)    |
| (Redis-backed)       | di seluruh pods; kontrol  | untuk setiap RPC fetch; dependensi   |
|                      | terpusat real-time.       | single point of failure (SPOF).      |
+----------------------+---------------------------+--------------------------------------+
| OTel Auto-           | Zero-touch code;          | Overhead memori 15-25%; span noisy   |
| Instrumentation      | visibilitas instan untuk  | berlebihan jika tidak difilter;      |
|                      | HTTP/Redis/PG queries.    | resiko serialisasi lambat.           |
+----------------------+---------------------------+--------------------------------------+
| Streaming RSC        | Time to First Byte (TTFB) | Kompleksitas penanganan HTTP status; |
| via Suspense         | ultra-cepat; progressive  | status header dikirim sebelum render |
|                      | hydration di client.      | tuntas (tidak bisa kirim HTTP 500).  |
+----------------------+---------------------------+--------------------------------------+
```

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Error: "Headers already sent" saat Error Handling pada Streaming RSC
* **Gejala**: Ketika terjadi unhandled error di dalam RSC yang dibungkus oleh dynamic `<Suspense>`, aplikasi menghasilkan *crash log* dan user menerima UI blank parsial, tetapi HTTP response header tetap berstatus `200 OK`.
* **Akar Masalah**: Pada streaming SSR, chunk pertama HTML dikirimkan segera setelah shell halaman siap. Sekali HTTP header terkirim ke klien, status code HTTP tidak dapat diubah lagi menjadi `500 Internal Server Error`.
* **Solusi**: Bungkus komponen RSC rentan dengan `<ErrorBoundary>` di sisi client dan implementasikan `componentDidCatch` untuk log span error ke OTel tracer, serta fallback UI elegan secara visual di client.

### 10.2. Kebocoran Memori (Memory Leak) akibat Unbounded AsyncLocalStorage / OTel Span Buffering
* **Gejala**: Pemakaian RAM container Next.js naik secara linear (*sawtooth pattern* gagal turun) hingga pod terkena *OOMKilled* oleh K8s scheduler.
* **Akar Masalah**: Panggilan tracer OTel membuat span yang tidak pernah ditutup secara eksplisit (`span.end()` tidak berada dalam blok `finally {}`), atau simple processor digunakan alih-alih `BatchSpanProcessor`.
* **Solusi**:
  Gunakan `BatchSpanProcessor` pada mode produksi untuk mengumpulkan span sebelum di-flush secara batch asinkron:
  ```typescript
  import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
  
  const spanProcessor = new BatchSpanProcessor(traceExporter, {
    maxQueueSize: 2048,
    scheduledDelayMillis: 5000,
    exportTimeoutMillis: 30000,
    maxExportBatchSize: 512,
  });
  ```

### 10.3. Zombie Pods / HTTP 502 Bad Gateway saat Deployment Rollout
* **Gejala**: NGINX Ingress Controller mengembalikan `502 Bad Gateway` selama 5-10 detik ketika instance pod baru diluncurkan dan instance lama diterminasi.
* **Akar Masalah**: Pod lama langsung mematikan proses saat menerima sinyal `SIGTERM`, sementara iptables Ingress controller belum selesai memperbarui daftar routing endpoint pod.
* **Solusi**: Konfigurasikan `preStop` hook pada manifest deployment Kubernetes:
  ```yaml
  lifecycle:
    preStop:
      exec:
        command: ["/bin/sh", "-c", "sleep 15"]
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Docker Standalone Optimization**: Konfigurasi `output: 'standalone'` pada `next.config.js` untuk meminimalisir ukuran image container (hanya menyertakan file produksi minimal).
- [ ] **Non-root Execution User**: Jalankan Node.js server di dalam Docker container menggunakan unprivileged user (`nextjs:nodejs`, UID 1001).
- [ ] **Probe Separation**: Pisahkan rute `/api/health/liveness` (hanya uji status event loop Node.js) dan `/api/health/readiness` (uji kesiapan sistem eksternal).
- [ ] **Correlation ID Propagation**: Pastikan Edge Middleware selalu menginjeksi header `X-Correlation-ID` unik (`crypto.randomUUID()`) jika request masuk belum memilikinya.
- [ ] **Disable Unused Telemetry Auto-Instrumentation**: Matikan auto-instrumentation untuk modul `fs`, `dns`, atau pustaka utilitas rendah lainnya untuk menghemat CPU cycle.
- [ ] **Batch Span Exporting**: Selalu gunakan `BatchSpanProcessor` di environment staging & production, bukan `SimpleSpanProcessor`.
- [ ] **Graceful Drain Listener**: Pasang penanganan sinyal `SIGINT` dan `SIGTERM` secara eksplisit pada process node untuk memastikan graceful shutdown koneksi database dan trace buffer flushing.
- [ ] **Suspense Hierarchy Auditing**: Pastikan setiap komponen RSC yang melakukan asynchronous remote data fetching dibungkus dengan `<Suspense fallback={<Skeleton />} />` yang terisolasi.

---

## 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### File 1: Production Multi-stage Dockerfile
```dockerfile
# hands-on/m02/Dockerfile
FROM node:20-alpine AS base

# Step 1: Dependencies installation
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Step 2: Source builder
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run build

# Step 3: Production Runner
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy asset publik dan static build artifacts
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
```

### File 2: Konfigurasi Next.js Standalone
```javascript
// hands-on/m02/next.config.mjs
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    instrumentationHook: true,
  },
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

export default nextConfig;
```

### File 3: Kubernetes Deployment Manifest dengan Canary Lifecycle
```yaml
# hands-on/m02/k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nextjs-enterprise-bff
  labels:
    app: nextjs-enterprise-bff
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
      app: nextjs-enterprise-bff
  template:
    metadata:
      labels:
        app: nextjs-enterprise-bff
    spec:
      terminationGracePeriodSeconds: 45
      containers:
        - name: frontend
          image: enterprise/nextjs-bff:v1.2.0
          imagePullPolicy: IfNotPresent
          env:
            - name: NODE_ENV
              value: "production"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector.monitoring.svc.cluster.local:4317"
            - name: NODE_OPTIONS
              value: "--max-old-space-size=1536"
          ports:
            - containerPort: 3000
              name: http
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 15"]
          resources:
            requests:
              cpu: "500m"
              memory: "1024Mi"
            limits:
              cpu: "2000m"
              memory: "2048Mi"
          livenessProbe:
            httpGet:
              path: /api/health/liveness
              port: 3000
            initialDelaySeconds: 15
            periodSeconds: 10
            timeoutSeconds: 2
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /api/health/readiness
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 2
```

---

## 13. Exercises

### Level Easy
Ubah implementasi `instrumentation.ts` agar menambahkan attribute custom `deployment.region` yang diambil dari environment variable `REGION_NAME` ke dalam Global Tracer provider.
- *Petunjuk*: Gunakan method `.setAttribute()` pada resource initialization.

### Level Medium
Buat sebuah Higher-Order Function (HOC) atau Wrapper Function bernama `withDistributedTracing(actionName, fn)` untuk membungkus **Next.js Server Actions** (`'use server'`). Wrapper ini harus:
1. Menangkap span OTel baru sesuai nama `actionName`.
2. Menyimpan runtime execution duration.
3. Mencatat exception jika Server Action melempar error, lalu re-throw error tersebut ke layer client.

### Level Hard
Implementasikan sebuah custom cache handler untuk Next.js (`cacheHandler` di `next.config.js`) yang mengintegrasikan fallback mekanisme:
- Primary Cache: Redis via Upstash / ioredis.
- Secondary Fallback: In-Memory LRU Cache.
- Ketentuan: Jika instance Redis mengalami *connection timeout* (>200ms), cache handler tidak boleh melempar error ataupun mematikan proses SSR, melainkan fallback secara transparan ke In-Memory LRU dan mencatat distributed log warning dengan format JSON.

---

## 14. Real-world Challenge

**Skenario Tantangan**:
Sebuah platform perbankan digital mentransisikan sistem web mereka ke Next.js App Router. Sistem ini memiliki SLA 99.999% uptime. Pada jam-jam sibuk, sistem backend perbankan core (Mainframe legacy via gRPC gateway) sering mengalami *throttling* mendadak, mengembalikan status code `RESOURCE_EXHAUSTED` (HTTP 429 / 503 equivalent).

**Tugas Arsitektur**:
Rancang dan bangun arsitektur ketahanan frontend-to-backend menggunakan Next.js App Router dengan spesifikasi:
1. **Edge Middleware Throttler**: Mengimplementasikan Leaky Bucket rate limiter di middleware menggunakan Redis cluster.
2. **Adaptive Deadlines & Degradation**: Setiap request yang dialirkan ke RSC harus memiliki alokasi waktu maksimal (*Deadline Propagation*) sebesar 800ms. Jika downstream service belum merespons dalam durasi tersebut:
   - Request dibatalkan via `AbortController`.
   - UI mengembalikan status cached/mocked view yang ramah secara UX (degraded mode).
3. **Audit Trail**: Setiap degradasi sistem wajib mengirimkan event security telemetry asinkron ke endpoint audit trail perbankan tanpa memblokir thread rendering utama Next.js.
4. **Dokumentasikan**: Buat diagram state transitions dari arsitektur ketahanan yang Anda rancang, jelaskan bagaimana penanganan concurrency race condition dicegah saat circuit state berubah dari `OPEN` ke `HALF_OPEN` di lingkungan deployment dengan 50 replika pod pod Next.js horizontal.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Kapan fungsi `register()` di dalam `instrumentation.ts` dieksekusi oleh Next.js?
   - A. Setiap kali HTTP request baru masuk ke server.
   - B. Sekali ketika proses server Next.js diinisialisasi/booting.
   - C. Hanya saat menjalankan command `next build`.
   - D. Setiap kali client component selesai di-mount di browser.

2. Mengapa OpenTelemetry NodeSDK konvensional tidak dapat digunakan langsung di Next.js Edge Runtime?
   - A. Edge Runtime tidak mendukung protokol HTTP.
   - B. Edge Runtime berjalan di atas V8 engine terisolasi tanpa modul native Node.js (seperti `net`, `fs`).
   - C. Vercel melarang instalasi library pihak ketiga di Edge Middleware.
   - D. OTel API hanya dirancang khusus untuk backend berbasis bahasa Go dan Java.

3. Apa fungsi utama instruksi `output: 'standalone'` pada file `next.config.js`?
   - A. Menghasilkan static HTML file secara total (SSG murni).
   - B. Menghilangkan kebutuhan file `.env` di server produksi.
   - C. Menganalisis dependency tree dan hanya menyalin file produksi minimal untuk Docker image yang sangat ramping.
   - D. Menjalankan Next.js tanpa dependensi Node.js di server.

4. Header W3C standar mana yang digunakan untuk meneruskan distributed context trace antar service?
   - A. `x-custom-trace-token`
   - B. `traceparent`
   - C. `authorization`
   - D. `x-nextjs-span-carrier`

5. Mengapa liveness probe Kubernetes sebaiknya TIDAK memeriksa koneksi downstream database?
   - A. Karena koneksi database bersifat asinkron.
   - B. Jika database down sementara, semua pod Next.js akan dianggap unhealthy dan di-restart secara massal (cascading failure).
   - C. Database memblokir traffic port 3000 secara default.
   - D. Kubernetes tidak mengizinkan request TCP di dalam liveness probe.

---

### Bagian 2: Intermediate (Pilihan Ganda)
6. Manakah konfigurasi penanganan sinyal yang benar untuk mencegah *broken connection* saat Kubernetes mematikan pod Next.js?
   - A. Langsung panggil `process.exit(0)` di awal event `SIGTERM`.
   - B. Gunakan lifecycle `preStop: sleep` di K8s manifest dan tangkap `SIGTERM` di server untuk menyelesaikan inflight requests sebelum shutdown.
   - C. Mengabaikan sinyal `SIGTERM` dan menunggu `SIGKILL` dari sistem operasi.
   - D. Menghapus readiness probe dari manifes Kubernetes pod.

7. Jika terjadi exception di dalam sebuah Server Component yang di-stream menggunakan Suspense, mengapa HTTP response status code tetap 200?
   - A. Karena Next.js mengabaikan semua error di level RSC.
   - B. Response header dan status code 200 telah terlanjur dikirim ke client saat chunk rendering pertama dimulai.
   - C. Karena error di Server Component otomatis dialihkan ke browser via WebSocket.
   - D. Next.js App Router tidak mendukung status code 500.

8. Dalam pola Circuit Breaker, apa kondisi yang menyebabkan state berpindah dari `OPEN` ke `HALF_OPEN`?
   - A. Seluruh request upstream berhasil dikirim tanpa kegagalan selama 24 jam.
   - B. Terjadinya timeout request sebanyak 10 kali berturut-turut.
   - C. Habisnya masa jeda `recoveryTimeout` sejak kegagalan terakhir, membuka jalan untuk request uji coba terbatas.
   - D. Restart manual pod Next.js oleh cluster administrator.

9. Mengapa auto-instrumentation OTel untuk modul filesystem (`@opentelemetry/instrumentation-fs`) sering direkomendasikan untuk dimatikan pada Next.js?
   - A. Modul tersebut mengandung kerentanan keamanan RCE.
   - B. RSC secara berkala membaca file template dan chunk kompilasi lokal; mengaktifkannya menghasilkan noise ribuan span lokal yang membebani collector.
   - C. Modul filesystem memblokir proses rendering HTML secara permanen.
   - D. File descriptor di sistem Linux tidak kompatibel dengan distributed tracing.

10. Pendekatan manakah yang paling aman untuk menyimpan correlation ID request di dalam RSC tanpa menggunakan parameter props drilling?
    - A. Menyimpannya pada global variable `globalThis.currentRequestId`.
    - B. Membaca header via Next.js `headers()` API atau memanfaatkan context `AsyncLocalStorage`.
    - C. Menyimpannya di dalam browser LocalStorage via script injection.
    - D. Menggunakan Redis pub/sub untuk setiap request per user.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: The Cascading Timeout Disaster
Platform Anda mengalami lonjakan traffic saat perilisan produk. Microservice rekomendasi downstream melambat dari latensi 100ms menjadi 8.000ms. Seluruh pod Next.js BFF (*Backend-for-Frontend*) mengalami lonjakan penggunaan CPU hingga 100% dan latensi p99 meroket hingga 30 detik sebelum akhirnya pod mulai crash berurutan. 
*Pertanyaan Analisis*:
1. Analisis mengapa kegagalan microservice downstream dapat melumpuhkan keseluruhan cluster pod Next.js frontend!
2. Tindakan perbaikan apa yang harus segera diimplementasikan pada konfigurasi `fetch` dan arsitektur Next.js untuk mengisolasi kegagalan tersebut?

#### Skenario 2: Missing Traces in Microservices Dashboard
Tim Observabilitas mengeluhkan bahwa saat mereka menelusuri trace dari Jaeger/Datadog, jejak request dari Next.js Middleware terlihat, namun ketika request memasuki layer React Server Components dan melakukan HTTP fetch ke backend eksternal, trace terputus menjadi trace baru (*broken distributed trace chain*).
*Pertanyaan Analisis*:
1. Identifikasi faktor arsitektural internal Next.js yang menjadi penyebab hilangnya context trace antara Middleware dan RSC!
2. Bagaimana cara memastikan W3C Traceparent diinjeksi secara konsisten ke outgoing fetch request dari RSC?

#### Skenario 3: Zero-Downtime Rollout Glitch
Sebuah tim merelease pembaruan besar aplikasi Next.js ke cluster Kubernetes production dengan strategi `RollingUpdate`. Namun, selama proses rollout berjalan (sekitar 3 menit), customer melaporkan munculnya error pop-up `ChunkLoadError: Loading chunk failed` di aplikasi web mereka.
*Pertanyaan Analisis*:
1. Apa penyebab teknis di balik munculnya `ChunkLoadError` pada browser pengguna yang sedang aktif saat proses rolling update berlangsung?
2. Bagaimana desain deployment pipeline dan storage strategy (CDN / Asset Prefix) yang tepat untuk mengeliminasi masalah ini secara permanen?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Jawaban Bagian 1 & 2
1. **B** — `register()` dipanggil sekali saat booting server/worker Next.js.
2. **B** — Edge Runtime berbasis V8 isolates tanpa akses library low-level native Node.js OS bindings.
3. **C** — `standalone` memangkas node_modules dan file source, menyalin dependensi yang benar-benar digunakan saja.
4. **B** — W3C Trace Context mendefinisikan format `traceparent` (`version-trace_id-parent_id-flags`).
5. **B** — Liveness probe menentukan apakah container perlu di-restart. Menghubungkannya ke downstream DB memicu restart massal jika DB transient down.
6. **B** — Menggabungkan K8s `preStop` delay (sinkronisasi iptables) dan listener sinyal `SIGTERM` menjamin zero-downtime drain.
7. **B** — HTTP streaming membuka socket dan mengirim header 200 di awal chunk payload sebelum render selesai.
8. **C** — Status `HALF_OPEN` adalah fase verifikasi setelah masa tenggang `recoveryTimeout` tercapai.
9. **B** — Operasi read file internal bundler Next.js sangat masif; tracing FS mencemari APM dengan data berkategori *junk*.
10. **B** — `headers()` dan `AsyncLocalStorage` mengisolasi context per request lifecycle secara aman di server memory.

#### Panduan Jawaban Bagian 3: Skenario Kasus Produksi
* **Skenario 1**:
  1. *Akar Masalah*: Fetch tanpa limitasi timeout ketat menahan slot concurrency Node.js dan mempertahankan connection socket tetap terbuka di memory. Terjadi fenomena *resource starvation* (event loop lag meningkat, thread pool kehabisan resource, memori buffer menumpuk).
  2. *Solusi*: Pasang Circuit Breaker dengan batas timeout agresif (contoh: 1.5 detik), aktifkan fallback rendering (mengembalikan data kosong/parsial dengan banner degraded mode), dan terapkan `AbortController` signal pada seluruh downstream fetch.
* **Skenario 2**:
  1. *Akar Masalah*: Next.js Middleware dan RSC berjalan di layer/runtime boundary terpisah. Jika header `traceparent` tidak diinjeksi ulang ke request header headers yang diteruskan ke RSC, konteks trace global akan terputus.
  2. *Solusi*: Baca header tracing di middleware menggunakan `@opentelemetry/api`, buat span context baru, dan forward secara eksplisit via `requestHeaders.set('traceparent', ...)` menggunakan method `NextResponse.next({ request: { headers: requestHeaders } })`. Pastikan OTel NodeSDK diaktifkan dengan instrumentation HTTP/Fetch yang membaca context tersebut.
* **Skenario 3**:
  1. *Akar Masalah*: Pod versi lama yang memuat hash chunk file lama (`_next/static/chunks/[hash].js`) telah dihapus oleh rolling update, sementara browser klien lama masih meminta chunk dengan hash versi sebelumnya ke server baru yang hanya memiliki chunk hash versi baru.
  2. *Solusi*: Jangan simpan static asset hanya di dalam container pod ephemeral. Unggah seluruh direktori `.next/static` ke Object Storage (S3/GCS) yang diletakkan di belakang CDN Cloudfront/Cloudflare dengan retention policy multi-versi, lalu konfigurasikan `assetPrefix` pada `next.config.js` untuk mengarahkan request chunk langsung ke CDN.

---

## 16. Summary

1. **Observabilitas Berkelanjutan**: Mengimplementasikan OpenTelemetry native via `instrumentation.ts` dan integrasi W3C Trace Context memungkinkan penelusuran (*distributed tracing*) menyeluruh dari Edge Gateway hingga microservice terdalam, memberikan visibilitas penuh terhadap performa RSC dan Route Handlers.
2. **Arsitektur Resilien**: Sistem modern skala enterprise harus berasumsi bahwa kegagalan downstream adalah kepastian. Pola *Circuit Breaker*, *Graceful Degradation*, dan *Fallback Caching* menjamin ketersediaan UI frontend meskipun infrastruktur backend mengalami degradasi parah.
3. **Kesiapan Produksi & Deployment Skala Besar**: Operasional Next.js berskala ratusan ribu RPS memerlukan kontainerisasi minimalis (`standalone` mode), pemisahan granular health probe (`liveness` vs `readiness`), pengelolaan siklus hidup container Kubernetes yang tepat (`preStop` & `SIGTERM`), serta strategi decoupling static assets ke CDN multi-version storage.