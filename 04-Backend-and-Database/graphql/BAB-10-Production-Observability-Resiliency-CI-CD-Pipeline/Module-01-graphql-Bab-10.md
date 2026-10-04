# Bab 10: Enterprise Production Readiness & Lifecycle Operations
## Module 01: Production Observability, Resiliency, & CI/CD Pipeline

---

### 01: Identitas Modul
* **Track:** Backend and Database Engineering
* **Kategori:** 04-Backend-and-Database
* **Topik:** GraphQL Architecture & Operations
* **Tingkat Kesulitan:** Advanced / Production-Grade (Level 400)
* **Prasyarat:** Pemahaman mendalam tentang Node.js/TypeScript Runtime, GraphQL AST, Execution Context, Apollo Server/Yoga Engine, OpenTelemetry Standard, Distributed Tracing, Circuit Breaker Pattern, serta GitHub Actions/GitLab CI/CD.

---

### 02: Learning Objectives
Setelah menyelesaikan modul ini, engineer mampu:
1. Merancang dan mengimplementasikan telemetri holistik (*Tracing, Metrics, Logging*) berbasis **OpenTelemetry (OTel)** dan **Prometheus** dengan resolusi *field-level instrumentation* pada GraphQL Execution Engine.
2. Mengintegrasikan pola ketahanan sistem (*resiliency*) mencakup Distributed Circuit Breaking, Fallback Mechanisms, dan Execution Timeouts pada GraphQL resolvers guna mencegah *cascading failures*.
3. Membangun pipeline CI/CD modern yang mengotomatisasi *Schema Validation*, *Breaking Change Detection*, *Automated Load/Integration Testing*, dan *Zero-Downtime Safe Deployment* menggunakan GraphQL Hive / Apollo Studio Inspector.
4. Menerapkan proteksi operasional tingkat lanjut mencakup *Adaptive Rate Limiting*, *Query Complexity/Depth Limiting*, dan *Safe Error Masking* guna menjamin ketersediaan SLA 99.99%.

---

### 03: Concept Map Diagram ASCII

```
                                  [ GraphQL Client Query ]
                                             │
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │          API Gateway / Ingress Layer          │
                     │  - WAF, TLS Termination, Adaptive Rate Limit  │
                     └───────────────────────┬───────────────────────┘
                                             │
                                             ▼
                     ┌───────────────────────────────────────────────┐
                     │          GraphQL Production Engine            │
                     │  ┌─────────────────────────────────────────┐  │
                     │  │ Execution Pipeline & Plugins Engine     │  │
                     │  │ - OpenTelemetry Tracer (Trace Context)  │  │
                     │  │ - Complexity & Depth Limiter Validation │  │
                     │  │ - Safe Error Formatter / Masking        │  │
                     │  └────────────────────┬────────────────────┘  │
                     └───────────────────────┼───────────────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     │                                               │
                     ▼                                               ▼
     ┌───────────────────────────────┐               ┌───────────────────────────────┐
     │  Resilient Resolver Execution │               │ Telemetry & Observability Bus │
     │  ┌─────────────────────────┐  │               │ ┌───────────────────────────┐ │
     │  │ Circuit Breaker (Opossum│  │               │ │ OTel Collector -> Jaeger  │ │
     │  │ Fallback Mechanism      │  │───────────────┼─│ Prometheus Metrics Exporter││
     │  │ Timeout & Retry Engine  │  │               │ │ Structured JSON Logger    │ │
     │  └────────────┬────────────┘  │               │ └───────────────────────────┘ │
     └───────────────┼───────────────┘               └───────────────────────────────┘
                     │
                     ▼
     ┌───────────────────────────────┐
     │  Heterogeneous Downstream     │
     │  (gRPC, Microservices, DBs)   │
     └───────────────────────────────┘
```

---

### 04: Mengapa Relevan
Dalam ekosistem REST konvensional, observabilitas dan resiliensi berbasis pada *HTTP status codes* dan *endpoint URI*. Namun, pada arsitektur GraphQL:
* Seluruh kueri mengalir melalui satu endpoint HTTP (umumnya `POST /graphql`) dan secara default mengembalikan respons `200 OK`, bahkan ketika terjadi *partial execution errors*.
* Kompleksitas kueri bersifat dinamis; klien dapat meminta graf data bersarang (*nested graph*) yang memicu eksekusi puluhan resolver asinkron, rentan terhadap bottleneck $N+1$ dan *cascading failures* pada downstream microservices.
* Kegagalan satu downstream dependency tidak boleh meruntuhkan seluruh payload respons (*partial failure handling*).
* Perubahan skema (*breaking changes*) yang lolos ke tahap *production* dapat menghentikan operasi aplikasi klien mobile/web secara instan. Pipeline CI/CD yang kaku dan terotomatisasi secara komparatif adalah mitigasi mutlak untuk reliabilitas sistem.

---

### 05: Anatomi Konsep Inti

#### 1. Distributed Tracing & Field-Level Metrics
OpenTelemetry menginjeksi *Trace Context* (`traceparent`, `tracestate`) ke dalam *GraphQL Execution Context*. Setiap resolver dapat dieksekusi sebagai child span, merekam durasi, argumen (disanitasi), serta *field execution path* (`RootQuery.user.orders.items`).

$$\text{Latency}_{\text{total}} = \text{Parsing} + \text{Validation} + \sum_{i=1}^{n} \text{ResolverSpan}_i + \text{Formatting}$$

#### 2. Circuit Breaker & Fallback Patterns
Membungkus pemanggilan I/O downstream resolver. Apabila ambang batas *error rate* (misal $> 50\%$ dalam kurun 10 detik) terlampaui, sirkuit berpindah ke status `OPEN`, mengeksekusi *fallback handler* lokal (cache/stale data) secara instan tanpa membebani downstream yang sedang kritis, lalu berkala mengecek via `HALF-OPEN`.

#### 3. Schema Registry & CI/CD Verification Engine
Proses CI/CD memvalidasi schema diff terhadap riwayat query traffic asli (traffic-aware breaking change check). Jika sebuah field yang hendak dihapus masih memiliki *active client usage* dalam kurun waktu 30 hari terakhir, proses build diblokir (*exit code 1*).

---

### 06: Panduan Implementasi Step-by-Step

1. **Inisialisasi OpenTelemetry SDK:** Harus dieksekusi sebelum modul lain dimuat (*pre-execution bootstrap*) agar dapat melakukan monkey-patching terhadap engine GraphQL dan HTTP client.
2. **Konfigurasi Schema & Server Engine:** Bangun GraphQL server (menggunakan `@graphql-yoga` atau Apollo Server v4) yang diintegrasikan dengan OpenTelemetry Plugin, Prometheus Registry, dan Envelope plugins.
3. **Penyusunan Resilient Resolvers:** Bungkus eksekusi eksternal (Database, REST API, gRPC) menggunakan instance Circuit Breaker yang terisolasi per domain.
4. **Implementasi Plugin Sanitasi & Error Masking:** Format error agar detail internal (seperti DB connection strings, stack traces) tidak bocor ke klien publik, sembari tetap meneruskan *error log* lengkap ke tracing bus internal.
5. **Integrasi CI/CD Pipeline:** Tulis automasi GitHub Actions yang mengompilasi skema, memvalidasi dependensi skema terhadap GraphQL Hive/Apollo Studio, mengeksekusi integrasi end-to-end, dan merilis container via rolling update.

---

### 07: Contoh Kasus Sederhana

Berikut implementasi integrasi plugin telemetri dan Circuit Breaker minimalis:

```typescript
import { createYoga, createSchema } from 'graphql-yoga';
import { createServer } from 'http';
import CircuitBreaker from 'opossum';

// Mock Downstream Flaky Service
const fetchUserDataFromLegacyService = async (userId: string) => {
  if (Math.random() > 0.7) {
    throw new Error('Downstream Legacy Service Timeout');
  }
  return { id: userId, name: 'John Doe', tier: 'ENTERPRISE' };
};

// Circuit Breaker Options
const breakerOptions = {
  timeout: 1000, // 1 detik
  errorThresholdPercentage: 50,
  resetTimeout: 5000, // 5 detik cooldown
};

const userBreaker = new CircuitBreaker(fetchUserDataFromLegacyService, breakerOptions);
userBreaker.fallback((userId: string) => ({
  id: userId,
  name: 'Fallback User (Cached/Degraded)',
  tier: 'STANDARD',
}));

const schema = createSchema({
  typeDefs: /* GraphQL */ `
    type User {
      id: ID!
      name: String!
      tier: String!
    }
    type Query {
      user(id: ID!): User
    }
  `,
  resolvers: {
    Query: {
      user: async (_, { id }) => {
        return await userBreaker.fire(id);
      },
    },
  },
});

const yoga = createYoga({ schema, logging: 'debug' });
const server = createServer(yoga);

server.listen(4000, () => {
  console.log('Telemetry & Resilient Demo running on http://localhost:4000/graphql');
});
```

---

### 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur enterprise GraphQL terintegrasi:

#### File: `src/telemetry/tracer.ts`
```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';

diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.WARN);

const exporter = new OTLPTraceExporter({
  url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://localhost:4317',
});

export const otelSDK = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: 'graphql-enterprise-gateway',
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'production',
  }),
  traceExporter: exporter,
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': { enabled: false },
      '@opentelemetry/instrumentation-graphql': {
        enabled: true,
        mergeItems: true,
        ignoreTrivialResolveSpans: true,
      },
    }),
  ],
});

process.on('SIGTERM', () => {
  otelSDK.shutdown()
    .then(() => console.log('Tracing SDK terminated successfully'))
    .catch((err) => console.error('Error terminating Tracing SDK', err))
    .finally(() => process.exit(0));
});
```

#### File: `src/metrics/prometheus.ts`
```typescript
import client from 'prom-client';

export const prometheusRegistry = new client.Registry();
client.collectDefaultMetrics({ register: prometheusRegistry, prefix: 'graphql_engine_' });

export const graphqlRequestDuration = new client.Histogram({
  name: 'graphql_request_duration_seconds',
  help: 'Durasi eksekusi request GraphQL per operasi',
  labelNames: ['operation_name', 'operation_type', 'status'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
  registers: [prometheusRegistry],
});

export const graphqlFieldExecutionDuration = new client.Histogram({
  name: 'graphql_field_execution_duration_seconds',
  help: 'Durasi eksekusi field-level resolver',
  labelNames: ['parent_type', 'field_name'],
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
  registers: [prometheusRegistry],
});

export const circuitBreakerStateGauge = new client.Gauge({
  name: 'graphql_circuit_breaker_state',
  help: 'Status sirkuit breaker (0 = Closed, 1 = Half-Open, 2 = Open)',
  labelNames: ['service_name'],
  registers: [prometheusRegistry],
});
```

#### File: `src/resiliency/circuit-breaker.ts`
```typescript
import CircuitBreaker from 'opossum';
import { circuitBreakerStateGauge } from '../metrics/prometheus';

export interface ServiceCallPayload<T> {
  execute: () => Promise<T>;
  fallbackValue: T;
  serviceName: string;
}

export class ResiliencyManager {
  private static instances = new Map<string, CircuitBreaker>();

  public static getBreaker<T>(serviceName: string, fallbackValue: T): CircuitBreaker {
    if (!this.instances.has(serviceName)) {
      const breaker = new CircuitBreaker(
        async (fn: () => Promise<T>) => await fn(),
        {
          timeout: 2000,
          errorThresholdPercentage: 50,
          resetTimeout: 7000,
          rollingCountTimeout: 10000,
          rollingCountBuckets: 10,
        }
      );

      breaker.fallback(() => {
        console.warn(`[CIRCUIT_BREAKER_FALLBACK] Serving fallback data for: ${serviceName}`);
        return fallbackValue;
      });

      breaker.on('open', () => {
        console.error(`[CIRCUIT_BREAKER_STATE] Breaker for ${serviceName} is now OPEN`);
        circuitBreakerStateGauge.set({ service_name: serviceName }, 2);
      });

      breaker.on('halfOpen', () => {
        console.warn(`[CIRCUIT_BREAKER_STATE] Breaker for ${serviceName} is now HALF-OPEN`);
        circuitBreakerStateGauge.set({ service_name: serviceName }, 1);
      });

      breaker.on('close', () => {
        console.info(`[CIRCUIT_BREAKER_STATE] Breaker for ${serviceName} is now CLOSED`);
        circuitBreakerStateGauge.set({ service_name: serviceName }, 0);
      });

      circuitBreakerStateGauge.set({ service_name: serviceName }, 0);
      this.instances.set(serviceName, breaker);
    }

    return this.instances.get(serviceName)!;
  }
}
```

#### File: `src/server.ts`
```typescript
import { otelSDK } from './telemetry/tracer';
otelSDK.start(); // Wajib pertama kali

import createFastify, { FastifyRequest, FastifyReply } from 'fastify';
import { createYoga, createSchema, maskError } from 'graphql-yoga';
import { useOpenTelemetry } from '@envelop/opentelemetry';
import { ResiliencyManager } from './resiliency/circuit-breaker';
import { prometheusRegistry, graphqlRequestDuration } from './metrics/prometheus';
import { useDepthLimit } from '@envelop/depth-limit';

interface Product {
  id: string;
  title: string;
  inventoryCount: number;
}

const fetchRemoteInventory = async (productId: string): Promise<number> => {
  // Simulasi kegagalan network probabilistik
  if (Math.random() < 0.3) {
    throw new Error(`Inventory Microservice Downstream Failure on Item ${productId}`);
  }
  return 42;
};

const schema = createSchema({
  typeDefs: /* GraphQL */ `
    type Product {
      id: ID!
      title: String!
      inventoryCount: Int!
    }

    type Query {
      product(id: ID!): Product
      health: String!
    }
  `,
  resolvers: {
    Query: {
      product: async (_, { id }) => {
        const breaker = ResiliencyManager.getBreaker<number>(`InventoryService_${id}`, 0);
        const inventory = await breaker.fire(() => fetchRemoteInventory(id));

        return {
          id,
          title: `Enterprise Hardened Asset #${id}`,
          inventoryCount: inventory,
        };
      },
      health: () => 'OK',
    },
  },
});

const yoga = createYoga<{
  req: FastifyRequest;
  reply: FastifyReply;
}>({
  schema,
  logging: {
    debug: (...args) => console.debug('[DEBUG]', ...args),
    info: (...args) => console.info('[INFO]', ...args),
    warn: (...args) => console.warn('[WARN]', ...args),
    error: (...args) => console.error('[ERROR]', ...args),
  },
  plugins: [
    useOpenTelemetry({
      resolvers: true,
      variables: false, // Hindari PII leaks
      result: false,
    }),
    useDepthLimit({ maxDepth: 7 }),
  ],
  maskedErrors: {
    maskError(error: unknown, message: string) {
      const masked = maskError(error, message);
      console.error('[GRAPHQL_EXECUTION_ERROR]', error);
      return masked;
    },
  },
});

const app = createFastify({ logger: false });

app.route({
  url: '/graphql',
  method: ['GET', 'POST', 'OPTIONS'],
  handler: async (req, reply) => {
    const stopTimer = graphqlRequestDuration.startTimer({
      operation_type: 'graphql_operation',
    });
    
    const response = await yoga.handleNodeRequestAndResponse(req, reply, {
      req,
      reply,
    });
    
    stopTimer({ status: `${response.status}` });

    response.headers.forEach((value, key) => {
      reply.header(key, value);
    });

    reply.status(response.status);
    reply.send(response.body);

    return reply;
  },
});

app.get('/metrics', async (_, reply) => {
  reply.header('Content-Type', prometheusRegistry.contentType);
  reply.send(await prometheusRegistry.metrics());
});

const PORT = parseInt(process.env.PORT || '4000', 10);
app.listen({ port: PORT, host: '0.0.0.0' }, (err) => {
  if (err) {
    console.error('Fatal Server Boot Error', err);
    process.exit(1);
  }
  console.log(`Enterprise GraphQL Gateway Live on http://localhost:${PORT}/graphql`);
});
```

#### File: `.github/workflows/graphql-ci.yml`
```yaml
name: GraphQL CI/CD & Schema Governance Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  validate-schema-and-lint:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Setup Node.js Environment
        uses: actions/setup-node@v3
        with:
          node-version: 18.x
          cache: 'npm'

      - name: Install Dependencies
        run: npm ci

      - name: Run ESLint & GraphQL Schema Linting
        run: npm run lint

      - name: Compile TypeScript
        run: npm run build

      - name: Verify Schema Breaking Changes (GraphQL Inspector)
        run: |
          npx @graphql-inspector/cli diff \
            "git:origin/main:src/schema.graphql" \
            "src/schema.graphql" \
            --rule suppress-compatible-editor-breaks \
            --fail-on-breaking

      - name: Execute End-to-End Resiliency & Integration Suite
        run: npm run test:e2e
        env:
          NODE_ENV: test
          OTEL_EXPORTER_OTLP_ENDPOINT: http://localhost:4317
```

---

### 09: Diagram Alur Kerja CI/CD & Tracing ASCII

```
[ Developer Git Push ]
         │
         ▼
[ CI Engine: GitHub Actions ] ────► Step 1: Type Checking & Linter
         │
         ▼
[ Schema Inspector Check ] ───────► Step 2: Compare against Main Branch / Schema Registry
         │                          ├─ Breaking Change Found? ──► [ Fail Build / Abort ]
         │                          └─ Compatible Change?
         ▼
[ Automated Integration Suite ] ──► Step 3: Spin Mock Microservices & Execute Tests
         │
         ▼
[ Container Build & Publish ] ────► Step 4: Docker Multi-Stage Build & Push to Registry
         │
         ▼
[ Production Deployment ] ────────► Step 5: Kubernetes Blue-Green / Rolling Upgrade
         │
         ▼
[ Runtime Execution Loop ] 
  ├── Resolver Query ──► [ Ingress OpenTelemetry Span Injection ]
  │                           │
  │                           ▼
  ├── Downstream Call ──► [ Circuit Breaker Evaluates State ]
  │                           ├─ CLOSED: Invoke RPC/DB ──► Collect Field Metrics
  │                           └─ OPEN: Invoke Local Fallback (No Cascade Crash)
  │
  └── Response Generation ──► Prometheus Scrapes `/metrics` & OTel Exports Spans
```

---

### 10: Analisis Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya / Trade-off | Skenario Penggunaan Optimal |
| :--- | :--- | :--- | :--- |
| **Field-Level Tracing (OTel)** | Visibilitas granular per resolver; identifikasi $N+1$ query bottleneck secara instan. | CPU Overhead tinggi pada payload besar (>15% degradation jika trivial spans diaktifkan). | Staging environment dan limited percentage sampling di Production. |
| **Circuit Breakers on Resolvers** | Mencegah *thread pool exhaustion* & kegagalan berantai ketika downstream microservice crash. | Kompleksitas state management; data fallback berpotensi menimbulkan *stale data* ke klien. | Resolver yang bergantung pada dependensi I/O eksternal non-kritis (e.g., rekomendasi, inventory). |
| **Traffic-Aware Schema Checks** | Keamanan penuh bahwa breaking change tidak merusak klien live. | Membutuhkan setup eksternal (Hive/Studio) & polling database metric historis klien. | Sistem dengan puluhan klien mobile yang tidak dapat dipaksa melakukan *immediate update*. |
| **Query Complexity Limiting** | Melindungi server dari DoS via nested malicious recursive queries. | Kueri valid yang kompleks dari authorized admin/power user berisiko ditolak jika limit terlalu ketat. | Server publik/B2C dengan model akses query arbitrary. |

---

### 11: Best Practices & Antipatterns

#### Best Practices
1. **Always Ignore Trivial Field Spans:** Nonaktifkan tracing pada resolver skalar primitif (`String`, `Int`, `Boolean`) untuk menekan overhead serialization.
2. **Context-Propagated Distributed Tracing:** Selalu teruskan HTTP Header `traceparent` dari gateway GraphQL ke downstream microservices.
3. **Partial Failure Design:** Bangun skema dengan *nullable types* pada field non-kritis agar resolver yang ditangani oleh Circuit Breaker Fallback dapat mengembalikan `null` tanpa membatalkan field lain dalam pohon respon.
4. **Isolate Registry & App Metrics:** Pisahkan endpoint metrik Prometheus (`/metrics`) pada internal port atau proteksi dengan network ACL agar data metrik performa tidak terekspos ke internet publik.

#### Antipatterns
1. **Returning HTTP 500 on Resolver Failures:** Mengembalikan status 500 merusak *spec compliance* GraphQL dan memutus komunikasi data parsial. Gunakan array `errors` dengan data payload parsial.
2. **Synchronous Tracing Export:** Mengekspor tracing telemetry secara sinkron ke backend observability; hal ini memblokir Node.js Event Loop. Selalu gunakan *BatchSpanProcessor*.
3. **Hard Deletion of Schema Fields:** Menghapus field tanpa siklus `@deprecated(reason: "...")` bertahap minimal 2 siklus rilis.

---

### 12: Security Hardening

```
Client Payload
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Ingress Layer: Request Size Limit (e.g., max 100kb)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Envelop Validation Phase:                                │
│    - Depth Limiter: maxDepth <= 7                           │
│    - Complexity Calculator: maxCost <= 1000                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Execution Phase:                                         │
│    - Disable Introspection in Production                    │
│    - Safe Error Masking: Strips SQL traces & Node backtraces│
└─────────────────────────────────────────────────────────────┘
```

Konfigurasi pengerasan proteksi:
1. **Nonaktifkan Introspection di Production:** Cegah eksternal membaca seluruh metadata arsitektur sistem.
2. **Sanitisasi Pesan Kesalahan:** Error resolver harus dibungkus oleh fungsi *masking*, memisahkan *public message* dari *internal error log*.
3. **Depth & Complexity Limiter:** Validasi struktur Abstract Syntax Tree (AST) GraphQL sebelum dieksekusi oleh resolver.

---

### 13: Observabilitas & Debugging

Gunakan skema kueri logging terstruktur untuk mencocokkan trace dengan error GraphQL:

```json
{
  "timestamp": "2023-10-27T10:14:00.120Z",
  "level": "ERROR",
  "service": "graphql-enterprise-gateway",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "graphql": {
    "operationName": "GetProductDetails",
    "path": ["product", "inventoryCount"],
    "errorName": "DownstreamTimeoutException",
    "message": "Inventory Microservice Downstream Failure on Item 101"
  }
}
```

Trik tracing resolvers bermasalah via Jaeger: Cari tag `graphql.field.path = "product.inventoryCount"` dan filter span dengan tag `error = true`.

---

### 14: Benchmarking & Performance

Eksekusi benchmark menggunakan `k6` untuk mengukur dampak latensi aktivasi OpenTelemetry and Resiliency Layer:

#### File: `load-test.js`
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },  // Ramp-up ke 50 VUs
    { duration: '1m', target: 100 },  // Beban puncak 100 VUs
    { duration: '20s', target: 0 },   // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<250'], // 95% request harus di bawah 250ms
    http_req_failed: ['rate<0.01'],   // Error rate di bawah 1%
  },
};

export default function () {
  const query = `
    query GetProduct {
      product(id: "101") {
        id
        title
        inventoryCount
      }
    }
  `;

  const headers = { 'Content-Type': 'application/json' };
  const res = http.post('http://localhost:4000/graphql', JSON.stringify({ query }), { headers });

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has valid payload': (r) => JSON.parse(r.body).data.product !== null,
  });

  sleep(0.1);
}
```

Perintah eksekusi:
```bash
k6 run load-test.js
```

---

### 15: Hands-on Lab Mini-Project

#### Objektif
Bangun pipeline CI lokal dan jalankan GraphQL Engine dengan simulasi kegagalan downstream menggunakan Docker Compose yang mencakup: Jaeger, Prometheus, dan Gateway API.

#### 1. Setup `docker-compose.yml`
```yaml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686" # UI
      - "4317:4317"   # OTLP gRPC

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

#### 2. Konfigurasi `prometheus.yml`
```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'graphql-gateway'
    static_configs:
      - targets: ['host.docker.internal:4000']
```

#### 3. Instruksi Eksekusi
1. Jalankan infrastructure observability:
   ```bash
   docker compose up -d
   ```
2. Jalankan aplikasi server:
   ```bash
   npm install
   npm run start
   ```
3. Kirim query GraphQL berulang kali via cURL:
   ```bash
   curl -X POST http://localhost:4000/graphql \
     -H "Content-Type: application/json" \
     -d '{"query": "query { product(id: \"99\") { id title inventoryCount } }"}'
   ```
4. Buka Jaeger UI di `http://localhost:16686` untuk memvisualisasikan Trace Spans dan Prometheus di `http://localhost:9090` untuk mengevaluasi metrik histogram eksekusi resolver.

---

### 16: Automated Testing & Verification

Gunakan framework pengujian Jest/Supertest untuk memvalidasi penanganan downstream failure:

```typescript
import supertest from 'supertest';

describe('GraphQL Observability & Resiliency Test Suite', () => {
  const request = supertest('http://localhost:4000');

  it('should return masked errors and partial data gracefully during circuit trips', async () => {
    const query = {
      query: `
        query TestResilience {
          product(id: "invalid-downstream") {
            id
            title
            inventoryCount
          }
        }
      `,
    };

    const response = await request
      .post('/graphql')
      .send(query)
      .expect(200);

    expect(response.body.data).toBeDefined();
    expect(response.body.data.product.id).toBe('invalid-downstream');
    // Fallback inventory harus 0, membuktikan circuit breaker aktif
    expect(response.body.data.product.inventoryCount).toBe(0);
  });

  it('should reject queries that exceed depth limit', async () => {
    const maliciousQuery = {
      query: `
        query DeeplyNested {
          product(id: "1") {
            id
            # Simulasi recursive nested fields
          }
        }
      `,
    };
    // Depth validation assertion logic di sini
  });
});
```

---

### 17: Troubleshooting Guide

| Gejala Masalah | Investigasi Root Cause | Resolusi Tindakan Korektif |
| :--- | :--- | :--- |
| **High Gateway Latency** tanpa error. | Resolver trivial menghasilkan puluhan ribu span OpenTelemetry kecil yang membebani Node event loop. | Set `ignoreTrivialResolveSpans: true` pada `@opentelemetry/instrumentation-graphql`. |
| **Circuit Breaker Langsung Terbuka (Spurious Tripping).** | Properti `timeout` pada sirkuit breaker di bawah *P99 latency* normal downstream. | Naikkan timeout sirkuit breaker berdasarkan metrik downstream P99 + buffer 20%. |
| **Tracing ID Hilang pada Downstream.** | Header propagation `traceparent` tidak diinjeksi saat gateway melakukan fetch/axios ke microservice lain. | Pastikan `HttpInstrumentation` aktif dan context di-pass secara eksplisit bila menggunakan custom client. |
| **Metrics `/metrics` Kosong.** | Prometheus registry lokal ter-reset atau menggunakan multi-process tanpa *cluster metrics aggregation*. | Gunakan `prom-client.AggregatorRegistry` jika menggunakan NodeJS Cluster / PM2. |

---

### 18: Checklist Produksi

- [ ] **Tracer Initialized First:** OTel SDK diimpor dan dimulai sebelum paket pihak ketiga lainnya.
- [ ] **Batch Processing Enabled:** Menggunakan `BatchSpanProcessor` bukan `SimpleSpanProcessor` untuk ekspor traces.
- [ ] **Introspection Disabled:** Skema instrospeksi dinonaktifkan (`introspection: false`) di environment staging & production.
- [ ] **Query Depth & Complexity Limit:** Depth limiter diset maksimum pada rentang 6–10 level.
- [ ] **Error Masking Active:** Tidak ada database trace, SQL statement, atau hostnames internal yang lolos ke `errors[].message`.
- [ ] **Schema Registry CI Check:** CI Pipeline mengeksekusi pemeriksaan breaking changes terhadap traffic produksi nyata.
- [ ] **Circuit Breakers on All I/O:** Seluruh RPC, DB, dan HTTP external calls resolver dilindungi circuit breaker dan fallback default.
- [ ] **Liveness & Readiness Probes:** Endpoint `/health` atau query shallow `/graphql?query={health}` terhubung ke kubernetes probes.

---

### 19: Ringkasan Eksekutif

Operasional GraphQL pada skala enterprise menuntut pergeseran paradigma dari *endpoint-level operations* ke *field-level governance*. Integrasi OpenTelemetry memungkinkan visualisasi mendalam hingga ke level durasi resolver individual tanpa merusak throughput sistem apabila *trivial spans* difilter dengan benar. 

Resiliensi sistem dijamin melalui penerapan **Circuit Breakers** yang mengisolasi kegagalan microservice downstream, mempertahankan ketersediaan parsial graph melalui mekanisme fallback. 

Seluruh siklus hidup ini ditopang secara mutlak oleh CI/CD pipeline yang menerapkan verifikasi kompatibilitas skema secara otomatis sebelum proses deployment dilakukan, mengeliminasi risiko downtime dan *breaking changes* bagi ribuan klien.

---

### 20: Referensi & Bacaan Lanjutan

1. **OpenTelemetry JavaScript Documentation:** `https://opentelemetry.io/docs/instrumentation/js/`
2. **GraphQL Inspector CI/CD Integration Guide:** `https://the-guild.dev/graphql/inspector`
3. **Michael Nygard (2018):** *Release It! Design and Deploy Production-Ready Software (2nd Edition)* - Pragmatic Bookshelf (Pola Circuit Breaker & Bulkhead).
4. **Envelop Plugin Ecosystem (The Guild):** `https://the-guild.dev/graphql/envelop`
5. **Prometheus Metrics Naming Best Practices:** `https://prometheus.io/docs