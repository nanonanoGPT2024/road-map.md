# Kurikulum Enterprise: Rekayasa Full-Stack Modern
## Kategori: 04-Backend-and-Database
### Bab 01: Fondasi dan Arsitektur Sistem
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
- **Merancang dan Mengimplementasikan Arsitektur Backend-for-Frontend (BFF)**: Memisahkan konsentrasi logika presentasi dan agregasi data mikroservis menggunakan runtime Node.js/Go dengan throughput tinggi dan isolasi kegagalan (*fault isolation*).
- **Menganalisis dan Memitigasi Isu Runtime Full-Stack**: Mengatasi *hydration mismatch*, *memory leaks* pada Node.js Server-Side Rendering (SSR), serta *connection pool exhaustion* pada layer database relasional saat lonjakan trafik masif.
- **Menguasai Siklus Hidup Request-Response End-to-End**: Mengonfigurasi *streaming SSR* dengan React Server Components (RSC) dan HTTP/2 / HTTP/3 Multiplexing yang terintegrasi dengan reverse proxy/edge gateway.
- **Menerapkan Pola Konsistensi Terdistribusi**: Mengimplementasikan *Transactional Outbox Pattern* dan *Distributed Tracing* (OpenTelemetry) yang menghubungkan frontend (browser instrumentation) hingga layer persistensi basis data.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Core Full-Stack**: Pemahaman mendalam JavaScript/TypeScript (ESNext), Node.js Event Loop (libuv, phases, microtasks), dan React Internals (Fiber architecture, reconciliation).
- **Networking & Protokol**: HTTP/1.1 vs HTTP/2/3, TLS termination, TCP handshake, WebSocket, dan DNS routing.
- **Backend & Database**: Arsitektur RESTful API, GraphQL basics, PostgreSQL (ACID properties, isolation levels, MVCC), dan Redis (in-memory data structures & eviction policies).
- **Tooling**: Docker, Docker Compose, k6 (load testing), PostgreSQL CLI (`psql`), cURL.

---

### 3. Concept & Internal Architecture

Arsitektur full-stack tingkat enterprise modern beralih dari model *Traditional Monolithic MVC* atau *Single Page Application (SPA) + Monolithic API* menuju **Decoupled Edge-Ready Component Architecture** yang menggabungkan *BFF (Backend-For-Frontend)*, *Isomorphic Runtimes*, dan *Asynchronous Persistence Pipelines*.

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT TIER                                        |
|  +---------------------------------------------------------------------------------+  |
|  | Web Browser / Mobile App                                                        |  |
|  | - Client Runtime (React Fiber, DOM, Local Cache)                                |  |
|  | - OpenTelemetry Web Tracer (Trace Parent Header Propagation: W3C TraceContext)  |  |
|  +---------------------------------------------------------------------------------+  |
+------------------------------------------+--------------------------------------------+
                                           |
                                      HTTP/3 (QUIC)
                                           |
+------------------------------------------v--------------------------------------------+
|                                     EDGE TIER                                         |
|  +---------------------------------------------------------------------------------+  |
|  | Cloudflare Workers / Fastly Compute@Edge / Reverse Proxy (NGINX)                |  |
|  | - TLS Termination, DDoS Shield, Edge Caching, Geo-Routing                      |  |
|  +---------------------------------------------------------------------------------+  |
+------------------------------------------+--------------------------------------------+
                                           |
                                      HTTP/2 (mTLS)
                                           |
+------------------------------------------v--------------------------------------------+
|                          BACKEND-FOR-FRONTEND (BFF) TIER                              |
|  +---------------------------------------------------------------------------------+  |
|  | Node.js / Go BFF Cluster                                                        |  |
|  | - React Server Components (RSC) Rendering Engine & Streaming Pipeline          |  |
|  | - Circuit Breaker (opossum / sony/gobreaker), Rate Limiter, Auth Validation     |  |
|  | - Request Aggregator & Data Shaping Engine (Eliminates over/under-fetching)     |  |
|  +-------------------+-----------------------------------------+-------------------+  |
+----------------------|-----------------------------------------|----------------------+
                       |                                         |
            gRPC (Protobuf) / Internal HTTP           Distributed Caching (RESP)
                       |                                         |
+----------------------v-------------------+   +-----------------v----------------------+
|        CORE MICROSERVICES TIER           |   |             CACHE TIER                 |
|  +------------------------------------+  |   |  +----------------------------------+  |
|  | Product, Order, Inventory Services |  |   |  | Redis Cluster                    |  |
|  | (Go / Java / Rust)                 |  |   |  | - Session, CDN Offload, Lookups  |  |
|  +------------------+-----------------+  |   |  +----------------------------------+  |
+---------------------|--------------------+   +----------------------------------------+
                      |
        SQL (Pool: pgBouncer / Read-Write Replicas)
                      |
+---------------------v-----------------------------------------------------------------+
|                                 DATABASE TIER                                         |
|  +---------------------------------------------------------------------------------+  |
|  | PostgreSQL HA Cluster (Patroni / Raft Consensus)                                |  |
|  | - Primary (Write-Ahead Logging / WAL)                                           |  |
|  | - Read Replicas (Streaming Replication)                                         |  |
|  | - Transactional Outbox Table -> Debezium CDC Engine -> Kafka Broker             |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

#### Komponen Internal Utama:
1. **Hydration & Isomorphic State Reconciliation**:
   Pada SSR klasik, server memproses tree komponen menjadi string HTML mentah via `renderToString()`. Browser mem-parse HTML tersebut, membangun DOM, mengunduh bundle JavaScript, lalu mengeksekusi *hydration* (mencocokkan DOM server dengan tree React Fiber). Jika terdapat data dinamis non-deterministik (misal: `new Date()` atau `Math.random()`), terjadi **Hydration Mismatch**: React membuang DOM server dan melakukan render ulang di client, menyebabkan layout shift drastis dan degradasi Time-to-Interactive (TTI).
   
   Pada arsitektur modern (React 18+ Streaming SSR & Server Components):
   - Server merender tree dalam bentuk *chunks* stream (UI format terpolarisasi via `renderToPipeableStream`).
   - Browser menerima frame HTML parsial dan langsung menampilkan kerangka visual (*Selective Hydration* via `<Suspense>`).
   - Node.js memancarkan transfer encoding `Transfer-Encoding: chunked`, mendegradasi memory footprint server karena output tidak perlu di-*buffer* secara utuh di RAM.

2. **Connection Lifecycle & Resource Exhaustion (BFF-to-DB vs BFF-to-Service)**:
   Node.js bersifat *single-threaded event-driven non-blocking I/O*. Ketika BFF terhubung langsung ke database relasional (seperti PostgreSQL) tanpa connection pool multiplexer (misalnya `pgBouncer`), setiap koneksi memakan resource memori dedicated di OS kernel database (~2-10 MB per connection process pada PostgreSQL). Jika BFF menerima 5.000 concurrent request, backend Node.js akan membuka pool koneksi secara masif yang berujung pada status `FATAL: remaining connection slots are reserved for non-replication superuser connections`. 
   
   Arsitektur enterprise memisahkan concern ini:
   - Client berinteraksi dengan BFF melalui koneksi HTTP/2 multiplexed berlatensi rendah.
   - BFF berinteraksi dengan upstream domain microservices menggunakan protocol binary berkecepatan tinggi (gRPC).
   - Domain microservices membatasi connection pooling ke PostgreSQL melalui pgBouncer dengan mode `transaction pooling`.

---

### 4. Why & What

| Dimensi Arsitektur | Single-Tier Full-Stack Monolith (Express/Django + Templates) | Decoupled Client-Side Rendering (SPA + Monolithic API) | Distributed Full-Stack (Edge + BFF + Microservices) |
| :--- | :--- | :--- | :--- |
| **Kelebihan Utama** | Kesederhanaan deployment; zero network boundary antara UI dan Model. | Pemisahan tegas tim frontend dan backend; static hosting hemat biaya. | Performa rendering optimal, aggregasi data efisien, skalabilitas granular per-tier. |
| **Kelemahan Kritis** | Beban komputasi terpusat; scaling horizontal boros memori; coupling tinggi. | SEO buruk tanpa SSR; network waterfall tinggi; *over-fetching* data di client. | Kompleksitas infrastruktur, distributed debugging, overhead latency jika jaringan internal tidak teroptimasi. |
| **Kapan Digunakan** | MVP, platform internal internal-facing, tim berukuran 1-3 engineer. | B2B dashboard di mana SEO tidak relevan, aplikasi kaya manipulasi visual (Canvas/Figma-like). | E-commerce enterprise, portal perbankan, media berskala tinggi (juta-an DAU). |

#### Alasan Arsitektur BFF (Backend-For-Frontend):
BFF bertindak sebagai penerjemah dan kompresor kontekstual. Kebutuhan data untuk antarmuka Desktop, Mobile iOS, dan Smart Watch sangat berbeda. Memaksa satu monolithic API generic untuk melayani ketiganya menimbulkan kompromi performa (*over-fetching* pada mobile, *multiple round-trips* pada desktop). BFF mengagregasi 5-10 pemanggilan microservice downstream secara konkuren via jaringan privat berlatensi <1ms, membentuk DTO yang ramping, lalu mengirimkannya ke client dalam satu payload efisien.

---

### 5. How (Workflow Detail)

Alur eksekusi request enterprise dari browser hingga persistence tier dan kembali:

```
[Browser Client]
       |
       |  1. GET /products/p-1002 (Accept: text/html)
       v
[Edge / Reverse Proxy]
       |
       |  2. Cache Miss -> Route ke upstream BFF
       v
[Node.js BFF Server]
       |-- 3. Inisialisasi OpenTelemetry Context (TraceID: `a1b2c3d4...`)
       |-- 4. Jalankan Pipeline SSR (React Server Components Engine)
       |
       |-- 5. Paralel Query via Internal Microservices Gateway (gRPC)
       |      |--> Product Service: `GetProductDetails(id="p-1002")`
       |      |--> Inventory Service: `GetStockLevel(id="p-1002")`
       |      +--> Pricing Service: `GetTieredDiscounts(id="p-1002")`
       |
       |-- 6. Stream Chunk Awal (Shell HTML + `<head>` + Loading Skeleton) langsung ke Client!
       |
[Downstream Services]
       |-- 7. Query PostgreSQL via pgBouncer
       |-- 8. Kembalikan Protobuf Response ke BFF
       |
[Node.js BFF Server]
       |-- 9. Resolve Suspense Boundary, Render sisa DOM Tree
       |-- 10. Flush Script Tag berisikan Stream Payload State ke HTTP Chunked Stream
       |
[Browser Client]
       |-- 11. Browser menerima Chunk bertahap, melakukan parsing incremental
       |-- 12. Client-side Hydration mengambil alih komponen interaktif (Selective Hydration)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Dapur Restoran Bintang Lima
- **Frontend SPA Murni**: Pengunjung masuk ke dapur, mengambil resep mentah, dan harus memasak sendiri di meja mereka (*client-side rendering*). Meja penuh bahan mentah (*over-fetching*), dan waktu tunggu sebelum suapan pertama sangat lama.
- **BFF (Backend-For-Frontend)**: Pelayan pribadi (BFF) yang mengetahui preferensi spesifik meja Anda. Pelayan ini berlari ke bagian dapur pemotongan daging, dapur pastry, dan dapur saus secara paralel, meracik piring saji secara proporsional sesuai kebutuhan meja Anda, lalu menyajikannya dalam keadaan siap santap.
- **Selective Hydration (Streaming)**: Pelayan menyajikan air minum dan roti pembuka secara instan (Shell UI) agar Anda tidak kelaparan selagi menunggu *main course* matang di dapur, alih-alih menahan Anda menunggu 45 menit sampai seluruh hidangan siap secara bersamaan.

```
+-----------------------------------------------------------------------------+
| STREAMING RENDERING TIMELINE                                                |
+-----------------------------------------------------------------------------+
Tradisional SSR:
Request ===> [ Server Render Lengkap ] ===> [ Download HTML ] ===> [ Parse & Hydrate ] ===> TTI
             |<- CPU Server Sibuk ->|       (Blank Screen)         (Layout Freeze)

Modern Streaming SSR (RSC):
Request ===> [ Chunk 1: Shell ] ===> Browser render Shell (FCP)
             [ Chunk 2: Content ] ==> Browser render Content (LCP)
             [ Chunk 3: JS Code ] ==> Hydrate Suspense Subtree (TTI Tercapai Cepat)
+-----------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Node.js Memory Leak via Context Scope pada Server Render
Kesalahan umum adalah mendeklarasikan singleton store di luar request scope pada runtime server:

```typescript
// ANTI-PATTERN: State bocor antar request concurrent (State Pollution & Memory Leak)
import express from 'express';
const app = express();

// Global variable: Dishare ke SEMUA request thread!
const globalUserSession: Record<string, any> = {};

app.get('/profile', (req, res) => {
  const userId = req.headers['x-user-id'] as string;
  globalUserSession[userId] = { accessedAt: Date.now() }; // Kebocoran memori + Race condition
  res.send(`User: ${userId}`);
});
```

*Solusi yang Benar*: Gunakan `AsyncLocalStorage` untuk konteks per-request yang terisolasi secara asinkron tanpa *variable leakage*.

#### B. Practical Enterprise Example: BFF Aggregator dengan Fault-Tolerance, Circuit Breaker, dan Streaming Response

Struktur implementasi BFF menggunakan Node.js, Express, dan Axios dengan pola arsitektur ketat:

```typescript
// bff-aggregator.ts
import express, { Request, Response, NextFunction } from 'express';
import axios, { AxiosInstance } from 'axios';
import CircuitBreaker from 'opossum';
import { AsyncLocalStorage } from 'async_hooks';
import http from 'http';

// 1. Context Propagation Setup
interface RequestContext {
  traceId: string;
  userId?: string;
}
const requestContext = new AsyncLocalStorage<RequestContext>();

// 2. HTTP Clients Definition with Connection Pooling
const productService: AxiosInstance = axios.create({
  baseURL: process.env.PRODUCT_SERVICE_URL || 'http://localhost:5001',
  timeout: 1500, // Strict timeout (SLA enforcement)
  httpAgent: new http.Agent({ keepAlive: true, maxSockets: 100 }),
});

const inventoryService: AxiosInstance = axios.create({
  baseURL: process.env.INVENTORY_SERVICE_URL || 'http://localhost:5002',
  timeout: 800,
  httpAgent: new http.Agent({ keepAlive: true, maxSockets: 100 }),
});

// 3. Circuit Breaker Options
const breakerOptions = {
  timeout: 2000,
  errorThresholdPercentage: 50,
  resetTimeout: 10000,
};

// 4. Wrap Microservice Calls with Circuit Breaker
const fetchProductBreaker = new CircuitBreaker(async (productId: string, headers: any) => {
  const response = await productService.get(`/api/v1/products/${productId}`, { headers });
  return response.data;
}, breakerOptions);

const fetchInventoryBreaker = new CircuitBreaker(async (productId: string, headers: any) => {
  const response = await inventoryService.get(`/api/v1/inventory/${productId}`, { headers });
  return response.data;
}, breakerOptions);

// Fallback logic jika inventory mati
fetchInventoryBreaker.fallback((productId: string) => {
  return { productId, stock: 0, status: 'UNKNOWN_FALLBACK', estimatedRestock: 'N/A' };
});

const app = express();

// Middleware: Tracing Context Injection
app.use((req: Request, res: Response, next: NextFunction) => {
  const traceId = (req.headers['x-trace-id'] as string) || `trace-${Date.now()}-${Math.random()}`;
  res.setHeader('x-trace-id', traceId);

  requestContext.run({ traceId, userId: req.headers['x-user-id'] as string }, () => {
    next();
  });
});

// Endpoint BFF: Agregasi Paralel & Transformasi DTO
app.get('/api/bff/pdp/:productId', async (req: Request, res: Response): Promise<void> => {
  const { productId } = req.params;
  const context = requestContext.getStore();
  const outgoingHeaders = { 'x-trace-id': context?.traceId };

  try {
    // Eksekusi paralel I/O non-blocking
    const productPromise = fetchProductBreaker.fire(productId, outgoingHeaders);
    const inventoryPromise = fetchInventoryBreaker.fire(productId, outgoingHeaders);

    const [productResult, inventoryResult] = await Promise.all([
      productPromise,
      inventoryPromise,
    ]);

    // Data Shaping: Hanya kembalikan data yang dibutuhkan oleh Client Tier
    const shapedResponse = {
      meta: {
        traceId: context?.traceId,
        timestamp: new Date().toISOString(),
      },
      data: {
        id: productResult.id,
        name: productResult.name,
        price: productResult.basePrice,
        currency: 'IDR',
        inventory: {
          available: inventoryResult.stock > 0,
          quantity: inventoryResult.stock,
          badgeStatus: inventoryResult.status,
        },
      },
    };

    res.status(200).json(shapedResponse);
  } catch (error: any) {
    // Fail-safe handling jika primary service (product) down
    res.status(502).json({
      error: 'Upstream Service Failure',
      traceId: context?.traceId,
      message: error.message,
    });
  }
});

const PORT = 4000;
app.listen(PORT, () => {
  console.log(`[BFF Engine] Online on port ${PORT}`);
});
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Flash Sale E-Commerce Skala 100.000 RPS
- **Latar Belakang**: Platform retail nasional meluncurkan flash sale diskon 90%. Pada pukul 00:00, 100.000 user aktif secara bersamaan membuka halaman Product Detail Page (PDP).
- **Insiden**:
  1. Halaman web blank (HTTP 504 Gateway Timeout).
  2. Beban CPU pod SSR Node.js melonjak hingga 100%, memicu crash beruntun (OOM / Out-of-Memory).
  3. PostgreSQL Primary drop karena kehabisan koneksi (max connections = 2.000 terlampaui dalam 3 detik).
- **Akar Masalah (Root Cause Analysis)**:
  - Pod SSR merender komponen kompleks via `renderToString()` yang bersifat CPU-bound sinkron dan memblokir Event Loop Node.js.
  - Setiap SSR request melakukan *cache miss* langsung ke PostgreSQL secara repetitif (Cache Stampede).
  - Tidak ada circuit breaker; ketika database melambat (latensi > 5 detik), koneksi menggantung di BFF, menyebabkan kehabisan slot koneksi TCP dan Node.js heap membengkak menampung closure request.
- **Arsitektur Solusi & Resolusi**:
  1. **Layer Edge Caching**: Mengimplementasikan *Stale-While-Revalidate* (SWR) pada CDN level (Cache-Control: `public, max-age=1, stale-while-revalidate=59`). 95% traffic tertahan di CDN.
  2. **Streaming SSR + RSC**: Mengganti pemanggilan sinkron dengan `renderToPipeableStream`. CPU load turun dari 100% konstan menjadi stabil di 35%.
  3. **Mutex Lock Caching (Single-flight Pattern)**: Menggunakan Redis Distributed Lock untuk mencegah ribuan pod merequest data produk yang sama secara serempak ke database ketika cache kedaluwarsa. Hanya 1 worker yang mengeksekusi query database, pod lain menunggu cache diperbarui.
  4. **pgBouncer Integration**: Menyisipkan pgBouncer di depan PostgreSQL cluster, mengonsolidasikan 10.000 pool koneksi dari microservices menjadi 150 dedicated connection ke engine PostgreSQL.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Performa / Throughput | Latensi (TTFB & LCP) | Skalabilitas Sistem | Kompleksitas & Biaya Operasional |
| :--- | :--- | :--- | :--- | :--- |
| **Traditional SPA + Direct Core Microservices** | **Tinggi di server**, rendah di browser entry. | TTFB sangat cepat (static S3), tetapi LCP lambat karena network waterfall. | Sangat scalable untuk layer presentasi; Core services rentan overload. | **Rendah**: Infra sederhana, hosting murah di bucket storage + CloudFront. |
| **Monolithic Full-Stack SSR (Single Node/Django)** | **Sedang**: CPU terbebani rendering HTML di setiap request. | TTFB lambat (komputasi berat sebelum response), LCP cepat jika sudah sampai. | Buruk: Sulit scale independen antara UI presentasi dan database transactions. | **Sedang**: Kode terpadu, namun biaya server compute membengkak saat traffic melonjak. |
| **Edge SSR + BFF + Microservices Architecture** | **Sangat Tinggi**: Komputasi terdistribusi, load terisolasi. | TTFB sangat optimal (Edge close to user), LCP superior via Streaming. | **Maksimal**: Setiap layer (Edge, BFF, Services, Cache, DB) scale secara otonom. | **Tinggi**: Membutuhkan tracing terdistribusi, CI/CD terpisah, biaya cluster k8s lebih tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Hydration Mismatch Akibat State Non-Deterministik
*Gejala*: Konsol browser memunculkan error: `Warning: Text content did not match. Server: "10:00:00" Client: "10:00:01"`. Layout terlihat melompat (flickering).
*Root Cause*: Kode mengeksekusi method non-deterministik seperti `new Date().toLocaleTimeString()` atau membaca nilai `window.innerWidth` langsung di body render SSR.
*Solusi*: Pindahkan akses state client-only ke dalam hook `useEffect` atau `useSyncExternalStore` yang hanya dieksekusi di browser setelah initial paint.

#### 2. Event Loop Starvation di Node.js BFF
*Gejala*: Latensi API tiba-tiba melonjak dari 15ms ke 8.000ms pada seluruh rute saat load tinggi, meskipun pemakaian CPU belum 100%.
*Root Cause*: Parsing JSON masif (`JSON.parse` ukuran 50MB) atau manipulasi array berat di dalam thread utama BFF, menghalangi libuv memproses event I/O lain.
*Solusi*: Gunakan streaming JSON parser (`JSONStream`) atau isolasi pemrosesan CPU-bound ke Node.js `worker_threads`.

#### 3. Database Connection Pool Exhaustion (Deadlock)
*Gejala*: Error PostgreSQL: `sorry, too many clients already`.
*Root Cause*: Microservice backend membuka connection pool sebesar 20 per pod. Saat pod di-scale out horizontal dari 10 pod menjadi 150 pod oleh HPA Kubernetes, total koneksi menjadi `150 * 20 = 3.000`, melebihi limit PostgreSQL (`max_connections = 1000`).
*Solusi*: Turunkan `max_connections` per pod aplikasi menjadi 2-5, dan pasang middleware pooler seperti **pgBouncer** dengan Transaction Pooling Mode.

#### Diagnostic Commands Checklist:
```bash
# Cek antrian koneksi PostgreSQL
psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Analisis latency event loop Node.js pada server produksi
npx clinic doctor -- on-port 4000 autocannon -c 100 -d 20 http://localhost:4000/api/bff/pdp/123

# Trace paket HTTP/2 multiplexing via cURL
curl -Iv --http2 https://api.yourdomain.com/api/bff/pdp/123
```

---

### 11. Best Practices (Production Checklist)

#### Keamanan (Security)
- [ ] **BFF Token Translation**: Jangan teruskan JWT pihak ketiga (misal Auth0/Okta) mentah ke client; konversi menjadi `HttpOnly`, `Secure`, `SameSite=Strict` Cookie di layer BFF untuk mencegah pencurian token via XSS.
- [ ] **Input Sanitization di Edge & BFF**: Validasi setiap DTO request payload menggunakan schema validator berkemampuan tinggi (Zod / TypeBox) sebelum menyentuh domain microservice.
- [ ] **CORS Lock-Down**: Jangan pernah menggunakan `Access-Control-Allow-Origin: *` pada BFF yang menangani kredensial perbankan / otentikasi.

#### Performa & Efisiensi
- [ ] **HTTP Keep-Alive**: Aktifkan HTTP/2 atau konfigurasi HTTP Agent `keepAlive: true` pada upstream client untuk mengeliminasi TLS/TCP handshake overhead di setiap inter-service invocation.
- [ ] **Selective Hydration**: Gunakan arsitektur *Island Architecture* (Astro) atau React Suspense boundaries untuk komponen yang tidak memerlukan interaktivitas pengguna secara instan.
- [ ] **Data Compression**: Terapkan kompresi `Brotli` (br) di atas Gzip pada response BFF untuk menghemat transfer bandwidth data hingga 20-30%.

#### Observabilitas & Operasional
- [ ] **Distributed Tracing (W3C Trace Context)**: Pastikan header `traceparent` di-forward dari browser melalui BFF ke database query tags (`/* trace_id=... */`).
- [ ] **Graceful Shutdown**: Implementasikan penanganan signal `SIGTERM` di BFF runtime untuk menyelesaikan pending HTTP streams dalam batas waktu toleransi (misal 15 detik) sebelum container dimatikan.
- [ ] **Health Checks Granular**: Pisahkan `/healthz/liveness` (apakah runtime menyala) dan `/healthz/readiness` (apakah Redis & Downstream dependencies dapat diakses).

---

### 12. Hands-on Practice

Buat dan jalankan arsitektur BFF mikro dengan isolasi database dan connection pooler di direktori `hands-on/m02/`.

#### Struktur Direktori
```
hands-on/m02/
├── docker-compose.yml
├── init.sql
├── bff/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       └── server.ts
└── services/
    └── product-service.js
```

#### Langkah Implementasi:

##### 1. File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: enterprise_db
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secretpassword
    ports:
      - "5432:5432"
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d enterprise_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  product-service:
    image: node:20-alpine
    working_dir: /app
    volumes:
      - ./services:/app
    command: sh -c "npm init -y && npm install pg express && node product-service.js"
    environment:
      DATABASE_URL: "postgres://admin:secretpassword@postgres:5432/enterprise_db"
      PORT: 5001
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "5001:5001"
```

##### 2. File: `hands-on/m02/init.sql`
```sql
CREATE TABLE products (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    base_price NUMERIC(15, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO products (id, name, base_price, stock) VALUES
('prod-1', 'Mechanical Keyboard Cloud-9', 1500000.00, 25),
('prod-2', 'Wireless Gaming Mouse', 850000.00, 0),
('prod-3', 'Ultra-Wide Monitor 34-Inch', 6200000.00, 5);
```

##### 3. File: `hands-on/m02/services/product-service.js`
```javascript
const express = require('express');
const { Pool } = require('pg');

const app = express();
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10, // Maksimal 10 koneksi per instance
  idleTimeoutMillis: 30000
});

app.get('/api/v1/products/:id', async (req, res) => {
  const { id } = req.params;
  try {
    const result = await pool.query('SELECT * FROM products WHERE id = $1', [id]);
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Product not found' });
    }
    res.json(result.rows[0]);
  } catch (err) {
    console.error('Database query error:', err);
    res.status(500).json({ error: 'Internal Database Error' });
  }
});

const PORT = process.env.PORT || 5001;
app.listen(PORT, () => {
  console.log(`[Product Core Service] Running on port ${PORT}`);
});
```

##### 4. Jalankan dan Uji
```bash
cd hands-on/m02/
docker compose up -d

# Verifikasi service aktif
curl -i http://localhost:5001/api/v1/products/prod-1
```

---

### 13. Exercise

#### Level 1 - Easy
**Tugas**: Modifikasi `product-service.js` agar menyertakan header custom `X-Response-Time` pada setiap response yang mencatat waktu eksekusi presisi dalam millisecond (menggunakan `process.hrtime()`).
*Acceptance Criteria*: Setiap response memiliki header `X-Response-Time: <angka>ms`.

#### Level 2 - Medium
**Tugas**: Di dalam folder `bff/`, bangun aplikasi Express TypeScript sederhana yang mengonsumsi `product-service:5001`. Implementasikan in-memory caching menggunakan Redis (`redis:6379`) dengan Time-To-Live (TTL) 30 detik.
*Acceptance Criteria*: Request pertama ke BFF mengambil data dari upstream service, request kedua dan seterusnya sebelum 30 detik merespon langsung dari Redis cache (dibuktikan dengan log tracing).

#### Level 3 - Hard
**Tugas**: Buat modul resilience circuit breaker di layer BFF menggunakan package `opossum`. Simulasikan kegagalan database dengan mematikan container Postgres (`docker compose stop postgres`).
*Acceptance Criteria*:
1. Ketika service gagal, circuit breaker terbuka (*Open State*).
2. BFF tidak boleh crash atau hang lebih dari 100ms; BFF wajib mengembalikan struktur response fallback: `{ id: "...", name: "...", status: "SERVICE_DEGRADED" }`.
3. Saat Postgres dihidupkan kembali (`docker compose start postgres`), circuit breaker bertransisi ke *Half-Open*, lalu *Closed* secara otomatis tanpa perlu restart container BFF.

---

### 14. Challenge

#### Skenario: Dual-Write & Zero-Downtime Data Migration Architecture
Perusahaan Anda memiliki sistem monolitik legacy yang menyimpan balance wallet pengguna langsung di database PostgreSQL. Anda ditugaskan memigrasikan layer full-stack ini ke sistem Ledger berbasis Event Sourcing tanpa downtime, tanpa inkonsistensi saldo (zero tolerance balance mismatch), dan melayani 20.000 transaksi bersamaan.

#### Tugas Rekayasa:
1. Rancang arsitektur implementasi **Transactional Outbox Pattern** pada layer backend menggunakan PostgreSQL Change Data Capture (Debezium) yang menembak ke Kafka broker.
2. Desain mekanisme fallback di BFF: Jika write operation ke sistem event sourcing baru gagal, sistem harus memiliki skema rekonsiliasi dual-write transaksional.
3. Rancang strategi frontend reconciliation: Bagaimana antarmuka frontend mengabstraksi latency migrasi asinkron ini kepada pengguna menggunakan *Optimistic UI Updates* yang aman tanpa mengekspos resiko *phantom balances*.

#### Output yang Diharapkan:
Dokumen desain arsitektural lengkap beserta diagram urutan (sequence diagram ASCII), skema schema database migrations (DDL), dan snippet pseudocode handling idempotency key pada transaksi outbox.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (Pilihan Ganda)

1. Apa penyebab utama terjadinya **Hydration Mismatch** pada aplikasi SSR modern?
   - A. Server dan browser menggunakan versi node yang berbeda.
   - B. Konten HTML yang di-generate server berbeda dari tree rendering awal yang dihasilkan browser client.
   - C. Browser memblokir pengunduhan file Javascript bundle karena CORS.
   - D. Koneksi database pada server terputus saat streaming.
   *Jawaban*: **B**. Hydration mismatch terjadi ketika representasi DOM hasil SSR tidak identik dengan Virtual DOM yang dibangun di client saat initial render phase.

2. Protokol jaringan manakah yang secara bawaan mendukung **Multiplexing** tanpa terkena dampak Head-of-Line Blocking pada layer transport?
   - A. HTTP/1.1 over TLS
   - B. HTTP/2 over TCP
   - C. HTTP/3 over QUIC (UDP)
   - D. WebSocket over TCP
   *Jawaban*: **C**. HTTP/3 menggunakan QUIC berbasis UDP, sehingga kehilangan satu packet data tidak menghentikan stream paket independen lainnya, mengeliminasi Head-of-Line blocking TCP.

3. Apa fungsi mendasar dari pola arsitektur **Backend-For-Frontend (BFF)**?
   - A. Menggantikan seluruh relasional database menjadi NoSQL.
   - B. Menyediakan endpoint generik untuk semua tipe client (Web, Mobile, IoT) secara seragam.
   - C. Mengoptimalkan agregasi data, transformasi payload, dan isolasi kebutuhan antarmuka tertentu dari core microservices.
   - D. Menghilangkan kebutuhan autentikasi pada level frontend.
   *Jawaban*: **C**. BFF berfokus pada melayani kebutuhan antarmuka spesifik (UI-focused aggregation) agar client tidak memikul overhead data yang berlebih.

4. Manakah mode pooling berikut pada **pgBouncer** yang paling efisien untuk aplikasi berskala traffic masif dengan karakteristik query stateless cepat?
   - A. Session Pooling
   - B. Transaction Pooling
   - C. Statement Pooling
   - D. Thread Pooling
   *Jawaban*: **B**. Transaction pooling mengalokasikan koneksi database ke client hanya selama satu transaksi berlangsung, kemudian mengembalikannya langsung ke pool setelah selesai, memungkinkan ribuan client dilayani oleh sedikit koneksi fisik.

5. Apa bahaya utama mengeksekusi operasi CPU-bound intensif (seperti enkripsi berat atau parsing file JSON raksasa) di dalam event loop utama Node.js?
   - A. Database otomatis menutup koneksi.
   - B. Libuv crash seketika dan me-restart OS.
   - C. Event Loop terblokir (*starvation*), mencegah penanganan request I/O concurrent lainnya secara global.
   - D. Memory RAM server langsung dikosongkan.
   *Jawaban*: **C**. Node.js menggunakan model single-threaded event loop untuk I/O orchestration. Eksekusi synchronous CPU-bound memblokir rotasi loop, melumpuhkan seluruh concurrency server.

---

#### Bagian B: Intermediate (Pilihan Ganda & Analisis Kasus)

6. Mengapa pendekatan SSR `renderToString()` tradisional di Node.js kurang ideal untuk menangani ribuan concurrent request dibandingkan `renderToPipeableStream`?
   - A. `renderToString()` bersifat asinkron murni dan tidak memakan resource RAM.
   - B. `renderToString()` memproses seluruh string secara sinkron di memori, memblokir event loop dan menunda Time-To-First-Byte (TTFB).
   - C. `renderToString()` tidak mendukung layout berbasis CSS modern.
   - D. `renderToString()` menghasilkan transfer payload 10 kali lebih besar dibanding HTML biasa.
   *Jawaban*: **B**. Pemanggilan sinkron `renderToString()` menahan komputasi hingga seluruh DOM selesai dirangkai di memori, memicu lonjakan memory footprint dan TTFB yang buruk saat konkurensi tinggi.

7. Perhatikan konfigurasi connection pool berikut:
   ```javascript
   const pool = new Pool({ max: 50, idleTimeoutMillis: 1000 });
   ```
   Jika aplikasi dideploy ke Kubernetes dengan horizontal auto-scaler (HPA) dari 5 pod ke 50 pod, potensi masalah apa yang akan menghantam PostgreSQL Primary jika DB memiliki limit `max_connections = 1000`?
   - A. Memory leak pada pod Node.js.
   - B. Tidak ada masalah, karena 50 * 50 = 2.500 koneksi akan otomatis di-queue di memory pod.
   - C. DB mengalami crash / *connection refusal* karena lonjakan pod berpotensi membuka hingga 2.500 koneksi simultan, melampaui kapasitas 1000.
   - D. Kubernetes membatalkan proses scaling pod.
   *Jawaban*: **C**. `max_connections` pada PostgreSQL bersifat absolut. Peningkatan pod tanpa connection proxy terpusat akan mengakibatkan *connection slot exhaustion*.

8. Bagaimana teknik mitigasi paling efektif untuk menangani insiden **Cache Stampede** (Thundering Herd) saat cache kunci produk populer kedaluwarsa?
   - A. Menghapus data dari database agar tidak bisa dibaca lagi.
   - B. Menggunakan Distributed Mutex / Single-flight pattern sehingga hanya 1 request yang mengisi cache ke DB, sementara request lain menunggu cache terisi.
   - C. Meningkatkan RAM Redis secara tak terbatas.
   - D. Mematikan fitur caching dan mengarahkan 100% request ke database.
   *Jawaban*: **B**. Mutex locking memastikan database hanya dieksekusi satu kali untuk meregenerasi entri cache, melindungi backend dari avalanche requests.

9. Manakah konfigurasi header caching HTTP yang ideal untuk static assets JavaScript bundle hasil kompilasi modern yang memiliki unique content hash (misal: `app-8fbc92.js`)?
   - A. `Cache-Control: no-cache, no-store, must-revalidate`
   - B. `Cache-Control: public, max-age=31536000, immutable`
   - C. `Cache-Control: public, max-age=0`
   - D. `Cache-Control: private, max-age=60`
   *Jawaban*: **B**. File dengan content hash bersifat kekal (*immutable*). Pengaturan waktu 1 tahun (`31536000`) dengan direktif `immutable` mencegah browser melakukan validasi berulang ke server asal.

10. Dalam distributed tracing OpenTelemetry pada sistem full-stack, header HTTP standar W3C manakah yang digunakan untuk mengalirkan konteks tracing dari client browser ke backend microservices?
    - A. `X-Custom-Trace-Id`
    - B. `traceparent`
    - C. `Authorization`
    - D. `Content-Encoding`
    *Jawaban*: **B**. `traceparent` adalah standar resmi W3C Distributed Tracing untuk mempropagasi TraceID, ParentID, dan TraceFlags antar batas sistem.

---

#### Bagian C: Skenario Kasus Produksi

11. **Skenario Kasus 1: Memory Leak Progresif pada Pod SSR Node.js**
    *Kondisi*: Pod SSR Next.js/Node.js di cluster production Anda mengalami OOMKilled (Out of Memory Killed) secara berkala setiap 6 jam sekali. Grafik memori menunjukkan pola gergaji (*sawtooth pattern*) yang selalu naik tanpa pernah turun kembali ke baseline, meskipun garbage collection berjalan.
    *Pertanyaan*: Bagaimana metodologi sistematis Anda untuk mendiagnosis dan menemukan baris kode penyebab kebocoran memori ini di lingkungan staging/produksi?
    *Jawaban Evaluasi Terstruktur*:
    1. Ambil heap dump berkala: Gunakan modul bawaan Node.js (`v8.writeHeapSnapshot()`) atau flag `--inspect` untuk mengambil minimal 3 snapshot memori: Snapshot A (setelah booting), Snapshot B (setelah traffic berjalan 1 jam), dan Snapshot C (saat memori menyentuh 80%).
    2. Bandingkan via Chrome DevTools: Muat snapshot ke Chrome DevTools Profiler, gunakan tampilan *Comparison view* antara Snapshot C terhadap Snapshot A.
    3. Analisis objek bocor: Cari objek dengan selisih retain size terbesar (biasanya berupa Closures, Event Listeners yang tidak di-unregister, Singleton Array, atau Cache objek global tanpa eviction policy).
    4. Periksa SSR Scope: Pastikan tidak ada instance data fetching context yang dideklarasikan di scope modul global di luar lifecycle request.

12. **Skenario Kasus 2: Lonjakan Latensi Ekstrem (P99 Spike) pada BFF**
    *Kondisi*: Dashboard monitoring menunjukkan latensi P50 BFF stabil di angka 20ms, namun latensi P99 melonjak hingga 4.500ms. BFF tersebut mengagregasi 4 downstream services menggunakan `Promise.all()`.
    *Pertanyaan*: Jelaskan penyebab mendasar dari jurang disparitas P50 vs P99 ini, dan bagaimana strategi rekayasa untuk memperbaikinya tanpa mengorbankan integritas data?
    *Jawaban Evaluasi Terstruktur*:
    1. Karakteristik `Promise.all()`: Operasi agregasi ini dibatasi oleh durasi service yang paling lambat (*slowest link in the chain*). Jika salah satu downstream service mengalami lonjakan P99 (misal: Service Inventory mengalami GC pause atau disk I/O stall 4.5 detik), seluruh response BFF ikut tertahan 4.5 detik.
    2. Perbaikan 1 (Strict Timeout per Service): Terapkan batas waktu ketat (*timeout*) individual pada setiap pemanggilan client HTTP/gRPC (misal: timeout inventory diset 500ms).
    3. Perbaikan 2 (Graceful Degradation): Gunakan `Promise.allSettled()` atau Circuit Breaker fallback. Jika Inventory timeout atau gagal, fallback mengembalikan status stok default (`"status": "check_at_checkout"`), sehingga BFF tetap dapat mengembalikan payload ke user dalam batas <200ms.

13. **Skenario Kasus 3: Cascading Failure Akibat Downstream Microservice Outage**
    *Kondisi*: Service Catalog mengalami crash fatal karena bug fatal exception. Dalam waktu 30 detik, pod BFF Node.js mulai crash satu per satu menyusul, disusul oleh membludaknya antrean pada Ingress Gateway (Nginx/Envoy).
    *Pertanyaan*: Fenomena apa yang sedang terjadi? Rancang blueprint proteksi berlapis untuk menahan cascade failure ini!
    *Jawaban Evaluasi Terstruktur*:
    1. Fenomena: **Cascading Failure** akibat ketiadaan isolasi kegagalan (*fault isolation*) dan akumulasi request tak terselesaikan yang menahan socket TCP serta memory heap BFF hingga kehabisan file descriptors dan memory exhaustion.
    2. Proteksi Lapis 1 (Circuit Breaker): Pasang Circuit Breaker (misal: Opossum) di BFF. Ketika error rate pemanggilan Catalog mencapai ambang batas 50%, circuit breaker *Trip/Open* seketika; seluruh request berikutnya langsung ditolak atau dialihkan ke Redis cache lokal tanpa menembak Catalog service.
    3. Proteksi Lapis 2 (Deadline & Rate Limiting): Terapkan gRPC deadlines atau HTTP context cancellation. Jika request di gateway dibatalkan pengguna (browser ditutup), signal pembatalan harus langsung menghentikan eksekusi di layer BFF dan microservice downstream.
    4. Proteksi Lapis 3 (Ingress Shedding): Konfigurasi Adaptive Concurrency Limiting di Edge/Ingress untuk me-reject traffic berlebih (HTTP 429 / 503) sebelum membanjiri downstream cluster.

---

### 16. Summary

1. **Arsitektur Full-Stack Modern Menuntut Dekopel Tegas**: Memisahkan konsentrasi presentasi (Edge/BFF) dari konsentrasi persistensi bisnis (Microservices/Databases) memungkinkan optimasi latency, caching yang presisi, dan skalabilitas horizontal yang independen.
2. **Streaming SSR Mengubah Paradigma TTFB & TTI**: Penggunaan streaming engine (React Server Components, HTTP chunked transfer) memecah isolasi rendering monolith, memberikan First Contentful Paint seketika ke browser, dan meminimalisir memory pressure di Node.js server.
3. **Resilience adalah Keharusan di Antara Boundaries**: Setiap pemanggilan melintasi network tier (BFF ke Services, Services ke Database) adalah titik potensi kegagalan. Penerapan Circuit Breakers, Strict Timeouts, Distributed Context Tracing (OpenTelemetry), dan Connection Pooling Multiplexing (seperti pgBouncer) adalah fondasi sistem enterprise anti-rapuh (*antifragile*).