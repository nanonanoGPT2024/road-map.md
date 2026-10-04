# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Production Observability, Resiliency, & CI/CD Pipeline**  
**Topik: GraphQL (Kategori: 04-Backend-and-Database)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonfigurasi distributed tracing end-to-end berbasis OpenTelemetry (OTel) pada level GraphQL execution layer dan field-level resolver.
- Mengimplementasikan ekspor metrik operasional (Golden Signals: Latency, Traffic, Errors, Saturation) ke Prometheus dan visualisasi via Grafana.
- Mengintegrasikan GraphQL Schema Registry (Apollo Studio / GraphQL Hive) untuk field-level usage analytics, client awareness, dan tracking depresiasi skema.
- Merancang pola resiliensi tingkat lanjut: Circuit Breaker per upstream service, Adaptive Concurrency Limiting, Outlier Detection, dan Partial Error Fallbacks.
- Membangun pipeline CI/CD komprehensif menggunakan GitHub Actions, Rover/Hive CLI untuk *automated schema breaking-change detection*, linting, dan zero-downtime deployment (Canary/Blue-Green).

---

## 2. Prerequisite
Untuk memahami modul ini secara komprehensif, Anda wajib menguasai:
- Arsitektur GraphQL dasar hingga menengah (Schema Definition Language, Resolvers, Execution Context, Directives).
- Pengetahuan fundamental microservices dan distributed systems: HTTP/2, gRPC, REST, Reverse Proxy/API Gateway (Envoy/Kong).
- Konsep dasar OpenTelemetry (Tracer, Span, Baggage, Exporter, Context Propagation via W3C Trace Context).
- Pemahaman praktis Docker, Kubernetes (Deployment, Service, Pod disruption budgets), dan CI/CD Runner (GitHub Actions syntax).
- Node.js 18+ / 20+ LTS dan TypeScript enterprise stack.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Distributed Tracing & Execution Phase Instrumentation
Eksekusi GraphQL memiliki fase internal: **Parse**, **Validate**, **Execute**, dan resolver field evaluation. Instrumentasi konvensional pada level HTTP middleware hanya melihat GraphQL request sebagai satu panggilan monolitik `POST /graphql` dengan status HTTP 200 (meskipun resolver internal melempar error).

```
[Client Request]
       │
       ▼
[HTTP Server (Express/Fastify)] ── Span: "HTTP POST /graphql"
       │
       ├─► [GraphQL Parser] ────── Span: "graphql.parse"
       ├─► [GraphQL Validator] ─── Span: "graphql.validate"
       │
       └─► [GraphQL Execution Engine] ── Span: "graphql.execute"
                 │
                 ├─► Resolver: Query.user ────── Span: "resolve: Query.user"
                 │         │
                 │         └─► Upstream REST/DB ─ Span: "HTTP GET /users/123"
                 │
                 └─► Resolver: User.orders ───── Span: "resolve: User.orders"
                           │
                           └─► Upstream gRPC ──── Span: "rpc: OrderService/GetOrders"
```

Untuk mendeteksi N+1 problem, bottleneck I/O, dan cascading failure, tracing harus diinjeksi ke dalam siklus resolver. OpenTelemetry mengaitkan context context propagation:
1. HTTP Header `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01` diekstraksi di HTTP Gateway.
2. Root span dibuat untuk GraphQL Operation Name.
3. Child span dibuat per field execution via Apollo Server Plugin API atau GraphQL Yoga envelop plugins (`useOpenTelemetry`).
4. Context di-inject ke upstream HTTP/gRPC request context untuk melanjutkan span tree ke backend microservice.

### 3.2 Schema Registry, Traffic Ingestion, & Contract Validation
Schema Registry (seperti Apollo Studio, Inigo, atau Hive) bertindak sebagai *source of truth* atas evolusi skema. 

Arsitektur Registry berbasis Edge Data Ingestion:
1. **Telemetry Reporter Plugin**: Engine GraphQL mengirimkan *usage reports* (berisi signature hash query, field yang diakses, status eksekusi, dan metadata klien) secara asynchronous via batch background worker ke Registry API.
2. **Schema Composition & Check Engine**: Saat developer membuka Pull Request (PR), CI pipeline mengekstrak skema baru dan memvalidasinya terhadap traffic produksi 30 hari terakhir. Jika sebuah field dihapus namun metrik menunjukkan 1.200 request/menit dari Client `iOS-App v4.2`, registry memblokir PR tersebut (*Breaking Change Violation*).

### 3.3 Resiliency: Cascading Failure Containment
GraphQL rentan terhadap *amplification attack* dan *cascading failures*. Bila upstream microservice mengalami degradasi:
- **Default GraphQL Behavior**: Menunggu timeout, menahan socket connection, thread pool/event loop kehabisan resource, memicu *out-of-memory* (OOM) atau crash pada GraphQL gateway.
- **Enterprise Resiliency Pattern**:
  - **Circuit Breaker per DataSource**: Isolasi failure rate per domain upstream (misal: UserService, OrderService, InventoryService). Jika error rate > 50% dalam window 10 detik, sirkuit berstatus `OPEN`. Request langsung dialihkan ke fallback atau di-short-circuit tanpa menyentuh upstream.
  - **Graceful Nullability Degradation**: Manfaatkan karakteristik non-nullable/nullable field GraphQL. Field yang gagal di-resolve menghasilkan nilai `null` dan menambahkan entri ke array `errors`, sementara sibling resolver yang sehat tetap menghasilkan data valid ke client (200 Partial Response).

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Production GraphQL |
| :--- | :--- | :--- |
| **Observability** | Log HTTP status code (200 OK) & aggregate latency router. | Field-level distributed tracing, per-resolver timing, OpenTelemetry, APM RED metrics. |
| **Error Handling** | Throw error ke root; request gagal total (500 Internal Error). | Nullable field degradation, Partial Errors, Circuit Breakers, Outlier Detection. |
| **Schema Evolution** | Komunikasi manual antar-tim backend & frontend; deprecation notice di Slack. | Automated Schema Checks di CI/CD, field-usage analysis terhadap traffic production live. |
| **Deployment** | Direct rolling update tanpa verifikasi skema runtime. | Contract validation, Canary release dengan verifikasi traffic telemetry terintegrasi. |
| **Rate Limiting** | IP-based request rate limiting (contoh: 100 req/min). | Query Complexity & Depth Analysis combined with Token Bucket per Client-ID. |

---

## 5. How (Workflow Detail)

### 5.1 End-to-End Tracing & Telemetry Flow
```
[Client] 
   │ (HTTP POST with W3C traceparent & client-name/version headers)
   ▼
[Reverse Proxy / Envoy]
   │ (Propagate headers, emit envoy metrics)
   ▼
[GraphQL Gateway (Apollo/Envelop)]
   │ 1. Parse & validate AST
   │ 2. Extract trace context -> Start Root Span
   │ 3. Execute Resolvers
   │      ├─ Check Circuit Breaker (Opossum)
   │      ├─ Execute DataFetchers / DataLoaders
   │      └─ Record field execution duration to Prometheus Histogram
   │ 4. End Root Span & export via OTLP (gRPC/HTTP) to OTel Collector
   ▼
[OpenTelemetry Collector]
   │ ── Export Traces ──► [Jaeger / Tempo / Datadog]
   │ ── Export Metrics ─► [Prometheus / Grafana Mimir]
   ▼
[Schema Registry (Hive/Apollo)] ◄── Periodic Batch Usage Reports
```

### 5.2 CI/CD Verification Workflow
1. Developer commit perubahan schema SDL ke Git branch.
2. GitHub Actions terpicu:
   - **Step 1: Linting**: `graphql-eslint` memvalidasi konvensi penamaan, directive, dan dokumentasi skema.
   - **Step 2: Schema Diff**: Tool membandingkan branch schema dengan production schema target.
   - **Step 3: Traffic Impact Analysis**: CLI memanggil Registry API untuk memeriksa apakah penghapusan/modifikasi field digunakan oleh klien aktif dalam 30 hari terakhir.
   - **Step 4: Automated Testing**: Integrasi e2e test dengan snapshot contract.
   - **Step 5: Conditional Gate**: Jika terdeteksi breaking change pada active clients, build berstatus `FAILED` dan memberikan log detail per client ID.

---

## 6. Analogy & Diagram ASCII

### 6.1 Analogi Observabilitas & Resiliensi: Pusat Distribusi Logistik Modern
Bayangkan GraphQL Gateway sebagai **Pusat Distribusi Paket**:
- **Logistik Tradisional (REST)**: Truk terpisah untuk setiap barang. Jika truk sepatu mogok, toko baju tidak terpengaruh, namun konsumen harus berinteraksi dengan puluhan kurir.
- **GraphQL**: Satu kurir membawa kontainer gabungan berisi sepatu, baju, dan elektronik dalam satu pesanan.
- **Tanpa Observability & Circuit Breaker**: Jika gudang elektronik terbakar, kurir menunggu di depan gerbang gudang elektronik tanpa batas waktu, menyebabkan seluruh pengiriman paket baju dan sepatu tertahan.
- **Dengan OpenTelemetry & Resiliency**: Kurir memiliki scanner GPS per item (Distributed Tracing). Saat sistem mendeteksi gudang elektronik tutup/kebakaran (Circuit Breaker OPEN), kurir menandai kotak elektronik sebagai "Tertunda/Kosong" (`null` field), menyegel paket baju dan sepatu, dan langsung mengantarkannya ke konsumen tepat waktu.

### 6.2 Arsitektur Resiliensi & Observabilitas
```
+-------------------------------------------------------------------------+
| GRAPHQL GATEWAY ENGINE                                                  |
|                                                                         |
|  +--------------------+    +------------------------------------------+ |
|  | OpenTelemetry Hook |    | Resiliency Layer                         | |
|  | - Execution Tracer |    | +--------------------------------------+ | |
|  | - Resolver Metrics |    | | Circuit Breaker: Auth Service (CLOSE)| | |
|  | - Error Counters   |    | +--------------------------------------+ | |
|  +---------┬----------+    | +--------------------------------------+ | |
|            │               | | Circuit Breaker: Order Service (OPEN)| | |
|            ▼               | +--------------------------------------+ | |
|   [OTel Exporter]          +--------------------┬---------------------+ |
+------------┼------------------------------------┼-----------------------+
             │ OTLP Protocol                      │ Fallback / Degradation
             ▼                                    ▼
+-------------------------+             +-------------------+
| OpenTelemetry Collector |             | Return Null Field |
+------------┬------------+             | + Partial Error   |
             │                          +-------------------+
       +-----+-----+
       ▼           ▼
  [Prometheus]  [Tempo]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Instrumentasi OpenTelemetry Dasar pada GraphQL
Contoh sederhana inisialisasi Tracer OpenTelemetry sebelum Apollo Server berjalan.

```typescript
// telemetry.ts
import { NodeSDK } from '@opentelemetry/sdk-node';
import { ConsoleSpanExporter } from '@opentelemetry/sdk-trace-node';
import { PeriodicExportingMetricReader, ConsoleMetricExporter } from '@opentelemetry/sdk-metrics';
import { GraphQLInstrumentation } from '@opentelemetry/instrumentation-graphql';
import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';

export const otelSDK = new NodeSDK({
  traceExporter: new ConsoleSpanExporter(),
  metricReader: new PeriodicExportingMetricReader({
    exporter: new ConsoleMetricExporter(),
    exportIntervalMillis: 10000,
  }),
  instrumentations: [
    new HttpInstrumentation(),
    new GraphQLInstrumentation({
      depth: 5,
      allowValues: false, // Security: jangan rekam argument sensitif ke dalam span
    }),
  ],
});

// Jalankan SDK sebelum kode server lain di-load
otelSDK.start();
```

---

### 7.2 Practical Example: Enterprise Observability, Circuit Breaker, dan Resiliency

Berikut adalah implementasi skala enterprise menggunakan Apollo Server v4, Prometheus client (`prom-client`), dan Circuit Breaker (`opossum`) dengan partial error degradation.

#### Struktur File:
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── server.ts
│   ├── telemetry.ts
│   ├── metrics.ts
│   ├── circuitBreaker.ts
│   ├── schema.ts
│   └── dataSources/
│       └── orderService.ts
```

#### File: `src/metrics.ts`
```typescript
import client from 'prom-client';

client.collectDefaultMetrics({ prefix: 'graphql_app_' });

export const httpDuration = new client.Histogram({
  name: 'graphql_request_duration_seconds',
  help: 'Durasi eksekusi request GraphQL dalam detik',
  labelNames: ['operation_name', 'operation_type', 'status'],
  buckets: [0.01, 0.05, 0.1, 0.3, 0.5, 1, 2, 5],
});

export const resolverDuration = new client.Histogram({
  name: 'graphql_resolver_duration_seconds',
  help: 'Durasi eksekusi field resolver dalam detik',
  labelNames: ['field_name', 'parent_type'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
});

export const circuitBreakerStateGauge = new client.Gauge({
  name: 'graphql_circuit_breaker_state',
  help: 'Status circuit breaker (0 = Closed, 1 = Half-Open, 2 = Open)',
  labelNames: ['service_name'],
});

export const registry = client.register;
```

#### File: `src/circuitBreaker.ts`
```typescript
import CircuitBreaker from 'opossum';
import { circuitBreakerStateGauge } from './metrics';

const options: CircuitBreaker.Options = {
  timeout: 3000, // Timeout I/O 3 detik
  errorThresholdPercentage: 50, // Buka breaker jika 50% request gagal
  resetTimeout: 10000, // Coba lagi setelah 10 detik
  rollingCountTimeout: 10000,
  rollingCountBuckets: 10,
};

export function createProtectedService<TArgs extends any[], TReturn>(
  name: string,
  action: (...args: TArgs) => Promise<TReturn>,
  fallbackAction: (...args: TArgs) => Promise<TReturn>
): CircuitBreaker<TArgs, TReturn> {
  const breaker = new CircuitBreaker(action, options);

  breaker.fallback(fallbackAction);

  // Monitor status untuk Prometheus
  const updateMetric = () => {
    let state = 0; // CLOSED
    if (breaker.halfOpen) state = 1;
    if (breaker.opened) state = 2;
    circuitBreakerStateGauge.set({ service_name: name }, state);
  };

  breaker.on('open', updateMetric);
  breaker.on('close', updateMetric);
  breaker.on('halfOpen', updateMetric);
  breaker.on('fallback', (result) => {
    console.warn(`[CIRCUIT-BREAKER] Fallback dieksekusi untuk ${name}`);
  });

  updateMetric();
  return breaker;
}
```

#### File: `src/schema.ts`
```typescript
export const typeDefs = `#graphql
  type Order {
    id: ID!
    totalAmount: Float!
    status: String!
    createdAt: String!
  }

  type User {
    id: ID!
    username: String!
    email: String!
    # Field ini nullable untuk mendukung Graceful Degradation
    orders: [Order]
  }

  type Query {
    user(id: ID!): User
    health: String!
  }
`;
```

#### File: `src/server.ts`
```typescript
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@apollo/server/express4';
import { ApolloServerPlugin } from '@apollo/server';
import express, { Request, Response } from 'express';
import http from 'http';
import cors from 'cors';
import { json } from 'body-parser';
import { typeDefs } from './schema';
import { registry, httpDuration, resolverDuration } from './metrics';
import { createProtectedService } from './circuitBreaker';

// Definisi Model
interface Order {
  id: string;
  totalAmount: number;
  status: string;
  createdAt: string;
}

// Simulasi Microservice Upstream yang tidak stabil
const fetchOrdersFromUpstream = async (userId: string): Promise<Order[]> => {
  // Simulasi network failure 60% waktu
  if (Math.random() < 0.6) {
    throw new Error(`Upstream Order Microservice Timeout/Unavailable for user: ${userId}`);
  }
  return [
    { id: 'ord-101', totalAmount: 250.5, status: 'COMPLETED', createdAt: '2023-10-01' },
    { id: 'ord-102', totalAmount: 89.9, status: 'PROCESSING', createdAt: '2023-10-05' },
  ];
};

// Fallback jika Circuit Breaker OPEN atau eksekusi gagal
const fallbackOrders = async (userId: string): Promise<Order[]> => {
  console.warn(`Mengembalikan fallback empty-state untuk orders user: ${userId}`);
  return []; // Graceful fallback
};

const orderServiceBreaker = createProtectedService(
  'OrderMicroservice',
  fetchOrdersFromUpstream,
  fallbackOrders
);

// Apollo Plugin untuk Performance Tracing & Prometheus Metrics
const metricsPlugin: ApolloServerPlugin = {
  async requestDidStart(requestContext) {
    const start = process.hrtime();
    const opName = requestContext.request.operationName || 'Anonymous';

    return {
      async executionDidStart() {
        return {
          willResolveField({ info }) {
            const fieldStart = process.hrtime();
            return () => {
              const fieldDiff = process.hrtime(fieldStart);
              const duration = fieldDiff[0] + fieldDiff[1] / 1e9;
              resolverDuration.observe(
                { field_name: info.fieldName, parent_type: info.parentType.name },
                duration
              );
            };
          },
        };
      },
      async willSendResponse(ctx) {
        const diff = process.hrtime(start);
        const duration = diff[0] + diff[1] / 1e9;
        const status = ctx.errors && ctx.errors.length > 0 ? 'error' : 'success';
        
        httpDuration.observe(
          {
            operation_name: opName,
            operation_type: ctx.operation?.operation || 'query',
            status,
          },
          duration
        );
      },
    };
  },
};

const resolvers = {
  Query: {
    user: async (_: any, { id }: { id: string }) => {
      // Fast path resolver lokal/DB utama
      return {
        id,
        username: `developer_${id}`,
        email: `dev_${id}@corp.engineering`,
      };
    },
    health: () => 'OK',
  },
  User: {
    orders: async (parent: { id: string }) => {
      try {
        // Melindungi panggilan upstream via Circuit Breaker
        return await orderServiceBreaker.fire(parent.id);
      } catch (error: any) {
        // Log telemetry error tapi jangan fail query secara global
        console.error(`Gagal meresolve orders: ${error.message}`);
        return null; // Nullable bubbling degradation
      }
    },
  },
};

async function startServer() {
  const app = express();
  const httpServer = http.createServer(app);

  const server = new ApolloServer({
    typeDefs,
    resolvers,
    plugins: [metricsPlugin],
    includeStacktraceInErrorResponses: false, // Security: jangan leak stack trace
  });

  await server.start();

  app.use(cors());
  app.use(json());

  // Prometheus Scrape Endpoint
  app.get('/metrics', async (_req: Request, res: Response) => {
    try {
      res.set('Content-Type', registry.contentType);
      res.end(await registry.metrics());
    } catch (ex) {
      res.status(500).end(ex);
    }
  });

  app.use('/graphql', expressMiddleware(server));

  const PORT = process.env.PORT || 4000;
  httpServer.listen(PORT, () => {
    console.log(`🚀 Gateway siap di: http://localhost:${PORT}/graphql`);
    console.log(`📊 Prometheus Metrics siap di: http://localhost:${PORT}/metrics`);
  });
}

startServer().catch((err) => {
  console.error('Fatal crash on startup:', err);
  process.exit(1);
});
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: E-Commerce Tier-1 Global (Super-App Checkout Bottleneck)
* **Konteks**: Sebuah sistem e-commerce berskala 120.000 Request per Second (RPS) menggunakan federated GraphQL architecture. Terdapat lebih dari 40 domain microservices di belakang router.
* **Insiden (Black Friday)**:
  - Microservice "Promo & Dynamic Voucher Engine" mengalami lonjakan CPU 100% akibat query SQL yang unindexed.
  - Waktu respons Promo Service naik dari 15ms menjadi 8.000ms (timeout limit).
  - Karena field `appliedDiscounts` pada type `Cart` bersifat *non-nullable* (`[Discount!]!`) dan tidak diisolasi dengan circuit breaker, seluruh query halaman Checkout (`Cart`, `Items`, `ShippingAddress`, `PaymentMethods`) throw GraphQL error global.
  - Seluruh pengguna global tidak bisa melakukan Checkout meskipun service `Payment` dan `Inventory` dalam kondisi 100% sehat. Revenue loss mencapai $450.000 per 10 menit.
* **Solusi Arsitektural**:
  1. **Schema Refactoring via Hive Registry CI**: Mengubah field non-nullable `appliedDiscounts` menjadi nullable (`[Discount]`). CI pipeline memvalidasi skema baru dan memastikan frontend mobile menangani nilai `null` dengan fallback tampilan "Diskon gagal dimuat, silakan lanjutkan pembayaran reguler".
  2. **Implementasi Adaptive Outlier Detection & Circuit Breaker**: Dipasang Circuit Breaker per-subgraph dengan threshold 20% timeout rate. Jika breached, Gateway langsung me-return fallback array kosong tanpa menunggu network socket I/O.
  3. **Field-level Tracing Alerting**: Alert Prometheus berbasis rasio degradasi resolver (`sum(rate(graphql_resolver_errors[1m])) by (field) / sum(rate(graphql_resolver_calls[1m])) by (field) > 0.05`).
* **Hasil**: Pada insiden berikutnya, ketika service Voucher kembali drop, Checkout conversion rate tetap bertahan di angka 94% dengan partial degradation, dan latensi checkout gateway tetap stabil di 120ms (P99).

---

## 9. Trade-offs (Analisis Komparatif Arsitektur)

| Variabel | Field-Level Detailed Tracing (Full Span Tree) | Aggregated Operation Metrics (Gateway Level) |
| :--- | :--- | :--- |
| **Observability Granularity** | Sangat tinggi. Mengetahui secara presisi resolver field mana yang lambat atau melempar exception. | Rendah/Menengah. Hanya mengetahui nama query/mutation secara umum. |
| **CPU & Memory Overhead** | **Signifikan**. Alokasi objek Span pada ribuan field per request dapat menaikkan Garbage Collection pause hingga 15-25%. | **Sangat Rendah**. Hanya mengukur titik masuk dan titik keluar HTTP request (< 1% overhead). |
| **Network Egress Cost** | **Tinggi**. Mengirimkan jutaan spans ke OTel Collector/Jaeger membutuhkan bandwidth besar dan storage retention mahal. | **Rendah**. Hanya mengirimkan metrik numerik time-series teragregasi (Prometheus scrape). |
| **Mitigasi Produksi** | Terapkan **Probabilistic Sampling** (contoh: trace 1% dari total traffic sukses, tetapi trace 100% traffic error/timeout). | Metrik diaktifkan 100% sepanjang waktu tanpa sampling. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 High-Cardinality Labels pada Prometheus Metrics
* **Kesalahan**: Menambahkan dynamic ID (seperti `user_id`, `order_id`, atau query argument) sebagai label metric Prometheus.
  ```typescript
  // FATAL MISTAKE:
  resolverDuration.observe({ userId: args.userId }, duration);
  ```
* **Dampak**: Eksplosi kardinalitas (jutaan time-series unik) membuat Prometheus crash akibat Out-of-Memory (OOM).
* **Solusi**: Hanya gunakan label dengan *bounded values*: `operation_name`, `field_name`, `parent_type`, dan `status`.

### 10.2 Tracing Span Leakage & Memory Leaks
* **Kesalahan**: Tidak menutup span (`span.end()`) jika resolver mengalami unhandled rejection atau melempar synchronous error sebelum return statement.
* **Dampak**: Span context menggantung di memory memory leak lambat tapi fatal di Node.js event loop.
* **Solusi**: Selalu wrap lifecycle span di dalam blok `try...finally`:
  ```typescript
  const span = tracer.startSpan('resolve_field');
  try {
    return await doWork();
  } finally {
    span.end(); // Dijamin tereksekusi
  }
  ```

### 10.3 Blind Breaking Changes Akibat Perubahan Nullability
* **Kesalahan**: Mengubah field dari nullable (`String`) menjadi non-nullable (`String!`) pada schema produksi tanpa memverifikasi data existing di database backend.
* **Dampak**: Jika ada satu saja baris data di backend yang bernilai `null`, GraphQL execution engine akan melempar fatal error dan "meledakkan" parent object hingga root (null bubbling), membatalkan seluruh query.
* **Solusi**: Skema evolution guard via CI check dan runtime schema validation sebelum rilis.

---

## 11. Best Practices (Production Checklist)

- [ ] **Observability**: W3C Trace Context (`traceparent`) dipropagasi dari Client API Gateway Subgraphs Database.
- [ ] **Observability**: Head-based sampling atau tail-based sampling diterapkan pada OpenTelemetry Collector (misal: 5% baseline, 100% errors).
- [ ] **Observability**: Kardinalitas metrik diproteksi; tidak ada UUID atau data dinamis dalam labels Prometheus.
- [ ] **Resiliency**: Seluruh upstream remote I/O dibungkus Circuit Breaker dengan batas timeout yang ketat (< 3 detik).
- [ ] **Resiliency**: Field yang memanggil distributed service eksternal wajib bersifat **nullable** untuk mendukung Partial Response.
- [ ] **Security & Tracing**: Argumen GraphQL disanitasi (`allowValues: false` pada OTel instrumentation) agar PII (Personally Identifiable Information) tidak bocor ke log trace.
- [ ] **CI/CD Automation**: GitHub Actions mengeksekusi `schema check` terhadap Schema Registry sebelum PR diizinkan merge.
- [ ] **CI/CD Automation**: Zero-downtime deployment dikonfigurasi menggunakan Kubernetes Readiness Probes yang memverifikasi koneksi ke Subgraph dependency.

---

## 12. Hands-on Practice

Buatlah implementasi pipeline CI/CD menggunakan GitHub Actions yang secara otomatis memvalidasi apakah perubahan skema GraphQL bersifat breaking change atau aman terhadap schema registry mock.

### Struktur Folder
Simpan seluruh file berikut di dalam folder: `hands-on/m02/`

```
hands-on/m02/
├── .github/
│   └── workflows/
│       └── graphql-ci.yml
├── schema-base.graphql
├── schema-current.graphql
└── scripts/
    └── check-schema.js
```

#### File: `hands-on/m02/schema-base.graphql` (Production baseline)
```graphql
type Product {
  id: ID!
  title: String!
  description: String
  price: Float!
  inventoryCount: Int!
}

type Query {
  product(id: ID!): Product
  allProducts: [Product!]!
}
```

#### File: `hands-on/m02/schema-current.graphql` (Perubahan yang diajukan developer - Memiliki Breaking Change)
```graphql
type Product {
  id: ID!
  # BREAKING: title di-rename menjadi name
  name: String!
  description: String
  # BREAKING: price diubah tipenya dari Float menjadi Int
  price: Int!
  # SAFE: field baru nullable
  discountPercentage: Float
}

type Query {
  product(id: ID!): Product
  # BREAKING: Menghapus allProducts
}
```

#### File: `hands-on/m02/scripts/check-schema.js`
Script validator mandiri berbasis AST parser GraphQL untuk mendeteksi breaking changes tanpa ketergantungan tool cloud eksternal.

```javascript
const fs = require('fs');
const { buildSchema } = require('graphql');

function loadSchema(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  return buildSchema(content);
}

function runContractCheck() {
  console.log('🔍 Memulai Static GraphQL Breaking Change Inspector...\n');
  
  const baseSchema = loadSchema('schema-base.graphql');
  const currentSchema = loadSchema('schema-current.graphql');

  const breakingChanges = [];

  const baseTypeMap = baseSchema.getTypeMap();
  const currentTypeMap = currentSchema.getTypeMap();

  for (const typeName in baseTypeMap) {
    if (typeName.startsWith('__')) continue;

    if (!currentTypeMap[typeName]) {
      breakingChanges.push(`[TYPE REMOVED] Type '${typeName}' telah dihapus.`);
      continue;
    }

    const baseType = baseTypeMap[typeName];
    const currentType = currentTypeMap[typeName];

    if (baseType.getFields && currentType.getFields) {
      const baseFields = baseType.getFields();
      const currentFields = currentType.getFields();

      for (const fieldName in baseFields) {
        if (!currentFields[fieldName]) {
          breakingChanges.push(`[FIELD REMOVED] Field '${typeName}.${fieldName}' telah dihapus.`);
        } else {
          const baseFieldType = baseFields[fieldName].type.toString();
          const currentFieldType = currentFields[fieldName].type.toString();

          if (baseFieldType !== currentFieldType) {
            breakingChanges.push(
              `[TYPE CHANGED] Field '${typeName}.${fieldName}' mengubah tipe dari '${baseFieldType}' menjadi '${currentFieldType}'.`
            );
          }
        }
      }
    }
  }

  if (breakingChanges.length > 0) {
    console.error('❌ CRITICAL: Breaking changes terdeteksi!');
    breakingChanges.forEach((change) => console.error(`  - ${change}`));
    process.exit(1);
  } else {
    console.log('✅ Skema lolos validasi! Tidak ada breaking change terdeteksi.');
    process.exit(0);
  }
}

runContractCheck();
```

#### File: `hands-on/m02/.github/workflows/graphql-ci.yml`
```yaml
name: GraphQL Schema & Resiliency CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  schema-validation:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v3

      - name: Setup Node.js Environment
        uses: actions/setup-node@v3
        with:
          node-version: 20
          cache: 'npm'
          cache-dependency-path: hands-on/m02/package.json

      - name: Install Dependencies
        working-directory: hands-on/m02
        run: |
          npm init -y
          npm install graphql

      - name: Execute Contract Breaking Change Check
        working-directory: hands-on/m02
        run: node scripts/check-schema.js
```

---

## 13. Exercise

### Level Easy
Ubah implementasi `hands-on/m02/scripts/check-schema.js` agar mampu mendeteksi penambahan field baru yang bersifat non-nullable pada skema input mutation (karena penambahan argumen wajib pada input type adalah breaking change untuk client lama).

### Level Medium
Tambahkan custom OpenTelemetry span processor pada kode `src/server.ts` yang secara dinamis menambahkan attribute span `app.error_code` dan menandai span status sebagai `ERROR` setiap kali resolver GraphQL mengembalikan error code `UNAUTHENTICATED` atau `INTERNAL_SERVER_ERROR`.

### Level Hard
Implementasikan plugin Apollo Server yang menerapkan algoritma **Adaptive Rate Limiter** berbasis *Leaky Bucket*:
- Hitung bobot/complexity query sebelum eksekusi (Field dasar bernilai 1 poin, field dengan nested resolver bernilai 5 poin).
- Simpan konsumsi token pengguna menggunakan mock in-memory Store (atau Redis).
- Tolak eksekusi dan return status error code `RATE_LIMIT_EXCEEDED` jika akumulasi complexity query melebihi threshold kuota token klien per menit.

---

## 14. Challenge
**Arsitektur Resiliensi Distributed Federation di Multi-Region Deployment**:
Rancang dokumen arsitektur dan spesifikasi implementasi (Proof-of-Concept) di mana GraphQL Federation Gateway harus beroperasi di dua region (`ap-southeast-1` dan `us-east-1`):
1. **Dynamic Routing & Regional Outlier Ejection**: Gateway di region Jakarta harus memprioritaskan Subgraphs lokal. Jika latensi Subgraph lokal melampaui 500ms (P95) selama 30 detik berturut-turut, gateway harus secara transparan mengalihkan 30% traffic ke region Singapore via private backbone link.
2. **Schema Registry Real-time Sync**: Skema baru tidak boleh diterapkan serentak. Rancang mekanisme rolling schema update di mana schema baru hanya aktif di Canary Pods (10% traffic) sambil memantau *error budget* (SLO 99.95%) via Prometheus query. Jika error budget terkikis lebih dari 0.01% dalam 5 menit pertama, rollback schema secara otomatis tanpa intervensi manusia.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. **Mengapa tracing level HTTP (contoh: middleware Express) tidak cukup untuk mengamati performa GraphQL?**
   - A. Karena HTTP middleware tidak mendukung format JSON.
   - B. Karena sebagian besar request GraphQL dikirim ke single endpoint (`/graphql`) dengan status response 200 OK meskipun resolver internal mengalami error.
   - C. Karena HTTP middleware tidak dapat membaca header Authorization.
   - D. Karena GraphQL tidak menggunakan protokol TCP.

2. **Kapan kondisi di mana sebuah Circuit Breaker beralih dari state `OPEN` ke `HALF-OPEN`?**
   - A. Segera setelah error pertama terjadi pada upstream service.
   - B. Setelah reset timeout period berlalu untuk menguji apakah upstream service telah pulih.
   - C. Saat error rate upstream mencapai 100%.
   - D. Saat CPU usage gateway turun di bawah 10%.

3. **Manakah dari perubahan skema berikut yang dikategorikan sebagai BREAKING CHANGE?**
   - A. Menambahkan field baru bertipe `String` (nullable) ke sebuah Object type.
   - B. Menambahkan nilai baru ke dalam Enum type yang dikembalikan dalam query response.
   - C. Mengubah tipe field dari `String!` (non-nullable) menjadi `String` (nullable).
   - D. Menghapus sebuah field yang masih di-query oleh klien mobile versi lama.

4. **Apa fungsi utama dari W3C `traceparent` header dalam distributed tracing?**
   - A. Menyimpan JWT token milik user yang login.
   - B. Membawa informasi trace ID, parent span ID, dan trace flags antar-service untuk menjaga kesinambungan trace context.
   - C. Mengompresi payload response GraphQL agar lebih hemat bandwidth.
   - D. Memberikan instruksi ke database untuk melakukan query caching.

5. **Apa risiko utama dari penambahan parameter dinamis (seperti UUID user) ke dalam label metrik Prometheus?**
   - A. Memory leak pada gateway akibat Prometheus High Cardinality explosion.
   - B. Prometheus akan memblokir request IP client secara otomatis.
   - C. Database upstream akan terkunci (Deadlock).
   - D. Skema GraphQL akan berubah menjadi invalid.

---

### Bagian 2: Intermediate (Pilihan Ganda)
6. **Dalam GraphQL execution engine, apa dampak dari error yang dilempar oleh field yang didefinisikan sebagai NON-NULLABLE (`Type!`) tanpa adanya circuit breaker/fallback?**
   - A. Field tersebut otomatis mengembalikan nilai string kosong `""`.
   - B. GraphQL engine melakukan retry request sebanyak 3 kali ke database.
   - C. Terjadi "Null Bubbling", di mana null merambat ke parent object hingga menemukan nullable ancestor terdekat atau membatalkan seluruh query (`data: null`).
   - D. Server akan crash seketika dengan error fatal exit code 1.

7. **Pada pola Graceful Degradation dengan Circuit Breaker, strategi apa yang paling tepat saat downstream inventory service berstatus `OPEN`?**
   - A. Hentikan Apollo Server dan biarkan Kubernetes me-restart Pod.
   - B. Return `null` pada field inventory (jika field nullable) dan isi pesan error informatif pada array `errors`, biarkan sisa payload data lain terkirim.
   - C. Ubah status HTTP response menjadi 503 Service Unavailable untuk seluruh request.
   - D. Tahan koneksi client secara blocking hingga inventory service pulih kembali.

8. **Bagaimana cara kerja verifikasi traffic-based schema checks pada GraphQL Hive atau Apollo Studio?**
   - A. Menjalankan load test sintetis setiap kali ada Pull Request masuk.
   - B. Membandingkan schema diff pada PR dengan riwayat hash field yang benar-benar dikonsumsi oleh client traffic asli dalam rentang waktu tertentu.
   - C. Mengirimkan email notifikasi ke seluruh developer frontend setiap kali PR di-merge.
   - D. Memeriksa sintaks AST skema tanpa melihat log traffic historis.

9. **Apa peran Prometheus Exporter endpoint (`/metrics`) pada arsitektur observability container?**
   - A. Menjadi webhook penerima log dari CloudWatch.
   - B. Menyediakan HTTP pull endpoint berformat teks standar openmetrics yang secara berkala di-scrape oleh server Prometheus.
   - C. Menyimpan file dump memory heap Node.js secara permanen.
   - D. Memvalidasi token otorisasi GraphQL query.

10. **Manakah konfigurasi instrumentasi OpenTelemetry yang paling krusial untuk mencegah kebocoran data sensitif (PII) ke distributed tracing storage?**
    - A. Mematikan fitur Span Exporter.
    - B. Menonaktifkan perekaman argumen query (`allowValues: false` atau data sanitization hook).
    - C. Mengubah protokol transmisi trace dari gRPC ke HTTP.
    - D. Mengaktifkan trace sampling rate 100%.

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: Tim Anda baru saja merilis query baru dengan kalkulasi berat yang sering timeout. Dashboard Grafana menunjukkan bahwa P99 Latency melonjak menjadi 12 detik, namun metric HTTP Gateway tetap menampilkan `status: 200`. Bagaimana Anda mengonfigurasi metrik Prometheus dan alerting rule untuk mendeteksi anomali ini secara akurat?
12. **Skenario 2**: CI pipeline memblokir deployment karena terdeteksi penghapusan field `User.legacyAvatarUrl`. Tim frontend mengklaim web app versi terbaru sudah tidak menggunakan field tersebut. Langkah investigasi sistematis apa yang harus Anda lakukan sebelum memutuskan untuk mem-bypass atau mempertahankan blokir CI tersebut?
13. **Skenario 3**: Terjadi cascading failure di mana ketika service Payment lambat, thread pool dan memori pada GraphQL Gateway terkuras habis, menyebabkan query publik yang tidak berhubungan (seperti `getCatalog`) ikut down. Arsitektur mitigasi apa yang wajib diterapkan pada GraphQL Gateway untuk mengisolasi kegagalan ini?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian 1: Basic
1. **B** - GraphQL hampir selalu mengembalikan HTTP 200 OK dengan error payload di body response, sehingga tracing HTTP standar tidak mencerminkan kegagalan internal resolver.
2. **B** - State `HALF-OPEN` adalah masa percobaan setelah cooldown reset timeout untuk menguji kestabilan upstream dengan sampel request terbatas.
3. **D** - Menghapus field aktif adalah breaking change fatal karena client lama yang memanggil field tersebut akan langsung menerima query execution error.
4. **B** - W3C `traceparent` membawa trace ID dan context span antar-layanan terdistribusi.
5. **A** - Nilai unbounded pada label metrik menyebabkan ledakan kardinalitas memori di Prometheus.

#### Bagian 2: Intermediate
6. **C** - Prinsip GraphQL Spec: Error pada non-nullable field akan merambat ke atas (bubble up) mencari parent nullable terdekat. Jika tidak ada, seluruh root data menjadi `null`.
7. **B** - Mengembalikan `null` dengan partial response menjaga user experience pada komponen aplikasi lain yang datanya sukses diambil.
8. **B** - Registry modern mencocokkan diff perubahan skema dengan audit log penggunaan field aktual dari client produksi.
9. **B** - Pola standar Prometheus adalah *Pull Architecture*, di mana scraper mengambil data metrik dari path `/metrics`.
10. **B** - Argumen input GraphQL sering mengandung password, token, atau informasi personal (PII); parsing value harus disanitasi atau dinonaktifkan pada trace span.

#### Bagian 3: Panduan Jawaban Kasus
11. **Solusi Skenario 1**:
    - Jangan hanya memantau HTTP response status code router.
    - Buat metric Prometheus Histogram untuk resolver duration (`graphql_resolver_duration_seconds`) dan counter untuk GraphQL execution errors (`graphql_execution_errors_total{operation_name="HeavyQuery"}`).
    - Buat Alertmanager rule berbasis P95/P99 latency resolver: `histogram_quantile(0.95, sum(rate(graphql_resolver_duration_seconds_bucket[5m])) by (le, operation_name)) > 2.0`.
12. **Solusi Skenario 2**:
    - Buka schema registry dashboard (Hive/Apollo Studio) dan filter audit log field `User.legacyAvatarUrl`.
    - Periksa dimensi `Client Name` dan `Client Version`. Seringkali web app sudah clean, namun aplikasi Android/iOS versi 6 bulan lalu masih aktif digunakan user dan memanggil field tersebut.
    - Jika masih ada traffic aktif: Batalkan penghapusan field, tandai field dengan directive `@deprecated(reason: "Gunakan avatarUrl")`, buat timeline komunikasi deprecation ke user untuk update aplikasi.
    - Jika traffic 0 request dalam 30-90 hari: Aman untuk override atau hapus field.
13. **Solusi Skenario 3**:
    - **Circuit Breaker & Outlier Ejection**: Bungkus resolver `Payment` dengan circuit breaker (timeout ketat, misal 2 detik).
    - **Resource Isolation**: Batasi max concurrency ke Payment service (contoh: max 50 concurrent sockets via dedicated HTTP Agent).
    - **Graceful Partial Failure**: Pastikan field `paymentInfo` pada query bernilai nullable, sehingga ketika payment error, catalog tetap ter-render sempurna.

---

## 16. Summary
- **Observability Terperinci**: Mengoperasikan GraphQL di skala enterprise menuntut pergeseran dari HTTP-level monitoring ke **Field-Level Observability** menggunakan OpenTelemetry dan Prometheus untuk mengukur latensi dan error resolver internal.
- **Resiliency via Isolation**: Skema GraphQL harus didesain toleran terhadap kegagalan. Penggunaan **nullable fields** yang dikombinasikan dengan **Circuit Breakers** mencegah kegagalan satu upstream microservice melumpuhkan seluruh respons sistem (*cascading failure*).
- **CI/CD Guardrails**: Skema adalah kontrak publik API Anda. Validasi otomatis breaking change berbasis real traffic data di CI pipeline adalah satu-satunya cara menjamin evolusi skema zero-downtime tanpa merusak pengalaman pengguna pada versi klien yang lebih lawas.