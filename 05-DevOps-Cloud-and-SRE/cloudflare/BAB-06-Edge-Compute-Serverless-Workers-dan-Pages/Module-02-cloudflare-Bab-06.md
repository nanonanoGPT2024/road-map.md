# BAB 06: Edge Compute Serverless (Workers & Pages)
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengoptimalkan Internal Runtime:** Menguasai mekanisme eksekusi V8 Isolate, memory snapshotting, event loop, dan alokasi resource pada Cloudflare Workers Runtime (`workerd`).
- **Mendesain Arsitektur Micro-Frontends & Micro-Services di Edge:** Mengimplementasikan Service Bindings untuk komunikasi antar-Worker tanpa overhead jaringan (*zero-cost IPC*), serta Smart Placement untuk minimalisasi latensi origin.
- **Mengembangkan Data Pipeline Streaming:** Membangun transformasi respons dinamis real-time menggunakan Web Streams API (`TransformStream`, `ReadableStream`) tanpa buffering memori edge.
- **Menerapkan Advanced Edge Security & Autentikasi:** Membangun engine validasi token JWT asinkronus berbasis Web Crypto API dan integrasi Mutual TLS (mTLS) upstream.
- **Mengoperasikan Fullstack Cloudflare Pages:** Mengonfigurasi routing Pages Functions tingkat lanjut, middleware pipelines, optimasi SSR/ISR, dan integrasi monorepo enterprise.
- **Menerapkan Observabilitas & Deployment Produksi:** Mengonfigurasi Tail Workers untuk agregasi log analitik, distributed tracing, serta zero-downtime deployment melalui Gradual Deployments (Canary Releases).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- Pengetahuan runtime JavaScript/TypeScript modern (ES2022+), Promises, Async/Await, dan Event Loop.
- Konsep dasar Cloudflare Workers & Pages dari Modul 01 (CLI `wrangler`, file konfigurasi `wrangler.toml`, deploy dasar).
- Pemahaman protokol HTTP/2, HTTP/3, WebSockets, dan manipulasi header/body HTTP.
- Dasar-dasar kriptografi: Public/Private Key Infrastructure (PKI), algoritma RSA/ECDSA, format JSON Web Token (JWT), JWKS.
- Node.js versi 18+ LTS atau 20+ LTS terpasang pada lingkungan lokal.

---

### 3. Concept & Internal Architecture

#### 3.1 V8 Isolates vs. Containerized/MicroVM Serverless
Berbeda dengan arsitektur serverless konvensional (misal: AWS Lambda berbasis Firecracker MicroVM atau container Docker) yang menginisialisasi kernel Linux mini untuk setiap instance:

```
[ Traditional Serverless (AWS Lambda / Cloud Run) ]
+-------------------------------------------------------+
| Guest OS / MicroVM Kernel (Linux)                     |  ~100MB - 500MB Memory
| Node.js Runtime Engine / V8 Instance                  |  Cold Start: 200ms - 2000ms
| Application Code Context                              |
+-------------------------------------------------------+

[ Cloudflare Workers (workerd / V8 Isolates) ]
+-------------------------------------------------------+
| Single Host OS Kernel + Shared Single Process Runtime |
| +----------------+ +----------------+ +-------------+ |  ~3MB - 5MB per Isolate
| | Isolate A (App)| | Isolate B (App)| | Isolate C   | |  Cold Start: < 5ms (Zero-Cold Start)
| +----------------+ +----------------+ +-------------+ |
+-------------------------------------------------------+
```

Pemisahan keamanan antar-tenant dilakukan langsung oleh *Google V8 Isolate boundaries*, bukan isolasi kernel hardware. Setiap request dialokasikan ke dalam konteks Isolate yang bersih, memotong waktu inisialisasi lingkungan eksekusi hingga sub-milidetik (< 5ms).

#### 3.2 Service Bindings: Zero-Cost IPC Architecture
Dalam arsitektur microservices berbasis container, pemanggilan layanan antar-service (Service A ke Service B) melibatkan *network serialization*, overhead DNS traversal, TLS handshake, dan transit melalui topologi routing internal/eksternal.

Service Bindings pada Cloudflare Workers menghapus seluruh lapisan tersebut:
- Worker pemanggil (Caller) dan Worker yang dipanggil (Callee) yang berada pada Point of Presence (PoP) yang sama dieksekusi dalam memori yang sama.
- Objek `Request` dan `Response` diteruskan secara referensial melalui *in-memory pointer pass-through* menggunakan V8 structural cloning.
- Latensi pemanggilan antar-Worker dipangkas menjadi **0 milidetik (sub-millisecond overhead)** tanpa enkripsi TLS ganda maupun socket networking.

#### 3.3 Smart Placement Heuristics
Ketika sebuah Worker perlu melakukan query ke backend database terpusat (misal: AWS RDS us-east-1), mengeksekusi Worker di PoP yang paling dekat dengan user (misal: Jakarta, CGK) justru menambah latensi total jika ada beberapa round-trip eksekusi serial:

$$\text{Total Latency} = \text{Client-to-Edge (CGK)} + N \times (\text{Edge-to-Origin (CGK} \to \text{IAD)})$$

Dengan **Smart Placement**, Cloudflare memantau telemetri request Workers. Jika komputasi Worker didominasi oleh latensi subrequest ke backend origin tertentu, runtime Cloudflare secara otomatis memindahkan eksekusi Worker tersebut ke PoP yang paling dekat dengan origin server (misal: IAD/Ashburn), meminimalkan round-trip global:

$$\text{Total Latency (Smart Placement)} = \text{Client-to-Origin (CGK} \to \text{IAD)} + N \times (\text{Local Intra-datacenter Latency})$$

#### 3.4 Web Streams Pipeline Memory Mechanics
Arsitektur edge compute memiliki batasan memori yang ketat (default: 128MB per Isolate). Memuat seluruh payload file besar atau respons API ke dalam memori (`await response.text()` atau `await response.arrayBuffer()`) akan memicu kegagalan runtime (*Memory Limit Exceeded*).

Cloudflare Workers mengimplementasikan Web Streams API native:
- **`ReadableStream`**: Komponen produsen data yang mengalirkan *chunks* (Uint8Array) secara incremental.
- **`WritableStream`**: Komponen konsumen data (misal: transmisi HTTP socket ke client).
- **`TransformStream`**: Komponen pemroses data perantara yang memanipulasi *chunk* tanpa harus menunggu keseluruhan aliran data selesai.

Mekanisme ini memungkinkan manipulasi payload berukuran Gigabyte pada edge dengan jejak memori (*memory footprint*) stabil di bawah **2MB**.

---

### 4. Why & What

| Dimensi | Cloudflare Workers & Pages | Traditional Edge/SSR (Node.js di VM/K8s) |
| :--- | :--- | :--- |
| **Footprint Memori** | ~3–5 MB per Isolate instance | ~150–500 MB per container pod |
| **Cold Start** | ~0 ms hingga < 5 ms global | 500 ms – 5000 ms (tergantung scaling pod) |
| **Distribusi Global** | Anycast network ke 300+ kota otomatis | Multi-region cluster manual (EKS, GKE, Traffic Director) |
| **Inter-Service Latency**| In-memory zero-latency via Service Bindings | Network routing + mTLS overhead (5ms - 50ms) |
| **Model Threading** | Asynchronous single-threaded (Non-blocking I/O) | Multi-threaded / Process-forking worker pool |
| **State Retention** | Ephemeral, stateless compute natively | Local persistent volume / stateful memory caching |

#### Alasan Menggunakan Workers & Pages di Skala Enterprise:
1. **Mengeliminasi Origin Egress Cost:** Menggunakan Workers Cache API dan transformasi Edge secara drastis mengurangi beban request langsung ke Origin Cloud (AWS, GCP, Azure).
2. **Dynamic Edge Personalization:** Pages Functions memungkinkan rendering SSR (*Server-Side Rendering*) dan streaming HTML secara langsung di edge terdekat dengan user, memangkas Time to First Byte (TTFB) hingga < 50ms secara global.
3. **Pemisahan Tanggung Jawab Tanpa Latensi Jaringan:** Melalui Service Bindings, tim platform dapat memisahkan Worker Autentikasi, Worker Billing, dan Worker Gateway ke repository mandiri tanpa mengorbankan performa sistem.

---

### 5. How (Workflow Detail)

Alur eksekusi request tingkat lanjut di Cloudflare Edge:

```
[Client (Browser/App)]
       |
       | 1. HTTP/3 Anycast Request (TLS 1.3 Termination di PoP Terdekat)
       v
[Cloudflare Edge Gateway / Global Proxy]
       |
       | 2. Routing Rules -> Workers Subsystem
       v
+---------------------------------------------------------------------------------+
| Cloudflare Workers Runtime (workerd)                                            |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   | Edge API Gateway Worker (Entrypoint)                                    |   |
|   |   - Validasi Header & IP Firewall Engine                                |   |
|   |   - Web Crypto Engine: Verifikasi JWT Signature secara offline (JWKS)   |   |
|   +-------------------------------------------------------------------------+   |
|         |                                         |                             |
|         | (In-Memory Service Binding)             | (In-Memory Service Binding) |
|         v                                         v                             |
|   +--------------------------+              +-----------------------------+     |
|   | Auth/User Context Worker |              | Transform/Business Worker   |     |
|   | Resolusi RBAC & Tenant   |              | Dynamic Processing & Logic  |     |
|   +--------------------------+              +-----------------------------+     |
|                                                           |                     |
|                                                           | Stream Piping       |
|                                                           v                     |
|                                             +-----------------------------+     |
|                                             | TransformStream Engine      |     |
|                                             | Masking PII / Gzip / Inject |     |
|                                             +-----------------------------+     |
+-----------------------------------------------------------|---------------------+
                                                            |
                                3. Non-blocking Fetch       | 4. Asynchronous
                                   (Smart Placement)        |    Event Dispatch
                                                            v
                                            +-------------------------------+
                                            | Origin Database / Core API    |
                                            +-------------------------------+
                                            | Tail Worker (Observability)   |
                                            | Batched metrics to DataDog/S3 |
                                            +-------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional vs. Jalur Diplomatik Khusus
- **Traditional Microservices (Container ke Container):** Seorang diplomat (data) dari Kedutaan A ingin menemui diplomat di Kedutaan B di seberang kota. Ia harus keluar gedung, masuk jalan raya umum, melewati lampu merah, membayar tol, dan melewati pemeriksaan keamanan imigrasi gerbang Kedutaan B secara berulang.
- **Service Bindings (Worker ke Worker):** Kedua departemen diplomatik berada di dalam gedung mega-struktur yang sama. Mereka hanya perlu berjalan melalui lorong pintu interior kedap udara tanpa perlu keluar ke jalan raya publik, tanpa tiket tol, dan tanpa pemeriksaan imigrasi ulang.

#### Topologi Enterprise Worker-to-Worker:
```
                               +-----------------------------+
                               |      Cloudflare Ingress     |
                               +-----------------------------+
                                              |
                                              v
                              +-------------------------------+
                              |    Gateway Worker (Edge)      |
                              +-------------------------------+
                                 |                         |
            (Service Binding:    |                         | (Service Binding:
             auth-service)       |                         |  catalog-service)
                                 v                         v
                   +------------------------+   +------------------------+
                   |  Auth Engine Worker    |   | Catalog Engine Worker  |
                   |  (RBAC/JWKS Cache)     |   | (Smart Placement ON)   |
                   +------------------------+   +------------------------+
                                                           |
                                                           | (Backbone Fetch)
                                                           v
                                                +----------------------+
                                                | Origin Central DB    |
                                                | (AWS us-east-1)      |
                                                +----------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Implementasi Streaming Response Menggunakan TransformStream
Kode berikut memodifikasi payload teks yang lewat secara *real-time* berbasis potongan (*chunk*), tanpa membebani memori Worker.

```typescript
// index.ts (Simple Worker)
export default {
  async fetch(request: Request): Promise<Response> {
    const originResponse = await fetch("https://jsonplaceholder.typicode.com/posts/1");

    // Definisikan transformator chunk
    const transformStream = new TransformStream({
      transform(chunk: Uint8Array, controller) {
        const textDecoder = new TextDecoder();
        const textEncoder = new TextEncoder();
        
        let chunkText = textDecoder.decode(chunk);
        // Modifikasi chunk secara real-time (contoh: uppercase kata tertentu)
        chunkText = chunkText.replaceAll("sunt", "[REDACTED]");
        
        controller.enqueue(textEncoder.encode(chunkText));
      }
    });

    // Hubungkan readable stream origin langsung ke writable stream transformasi
    const transformedBody = originResponse.body?.pipeThrough(transformStream);

    return new Response(transformedBody, {
      status: originResponse.status,
      headers: {
        ...Object.fromEntries(originResponse.headers),
        "x-edge-transform": "true",
        "content-type": "application/json; charset=utf-8"
      }
    });
  }
};
```

#### 7.2 Practical Example: Enterprise Edge Gateway Terintegrasi Service Binding & Validasi JWT Web Crypto

Berikut adalah arsitektur produksi untuk Gateway Worker yang memverifikasi JWT secara mandiri menggunakan Web Crypto API standar, lalu meneruskan request ke Backend Worker privat melalui **Service Binding**.

##### A. Konfigurasi `wrangler.toml` untuk Gateway Worker:
```toml
name = "enterprise-api-gateway"
main = "src/index.ts"
compatibility_date = "2024-04-01"
compatibility_flags = ["nodejs_compat"]

# Binding ke downstream private worker tanpa mengeksposnya ke public internet
[[services]]
binding = "CORE_CATALOG_SERVICE"
service = "core-catalog-backend"
environment = "production"

[vars]
AUTH_ISSUER = "https://auth.enterprise.internal/"
AUTH_AUDIENCE = "enterprise-api-clients"
```

##### B. File Implementasi Gateway: `src/index.ts`
```typescript
export interface Env {
  CORE_CATALOG_SERVICE: Fetcher; // Service Binding interface
  AUTH_ISSUER: string;
  AUTH_AUDIENCE: string;
}

interface JWTPayload {
  iss: string;
  aud: string;
  sub: string;
  exp: number;
  roles: string[];
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Bypass autentikasi untuk healthcheck
    if (url.pathname === "/healthz") {
      return new Response(JSON.stringify({ status: "healthy", timestamp: Date.now() }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }

    // 1. Ekstraksi Authorization Bearer Token
    const authHeader = request.headers.get("Authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return new Response(JSON.stringify({ error: "Missing or malformed Authorization header" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }

    const token = authHeader.substring(7);

    // 2. Verifikasi Token menggunakan Web Crypto API
    try {
      const payload = await verifyTokenSignature(token, env);

      // 3. Validasi Claims (exp, iss, aud)
      const nowEpoch = Math.floor(Date.now() / 1000);
      if (payload.exp < nowEpoch) {
        return new Response(JSON.stringify({ error: "Token expired" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        });
      }

      if (payload.iss !== env.AUTH_ISSUER || payload.aud !== env.AUTH_AUDIENCE) {
        return new Response(JSON.stringify({ error: "Invalid token claims" }), {
          status: 403,
          headers: { "content-type": "application/json" },
        });
      }

      // 4. Mutasi Request: Sisipkan Metadata Identitas ke Downstream Service
      const enrichedHeaders = new Headers(request.headers);
      enrichedHeaders.set("x-user-id", payload.sub);
      enrichedHeaders.set("x-user-roles", payload.roles.join(","));
      enrichedHeaders.delete("Authorization"); // Hapus raw token dari internal hop

      const downstreamRequest = new Request(request.url, {
        method: request.method,
        headers: enrichedHeaders,
        body: request.body,
        redirect: "manual",
      });

      // 5. Eksekusi Service Binding (In-Memory Dispatch ke private worker)
      const response = await env.CORE_CATALOG_SERVICE.fetch(downstreamRequest);

      // Sisipkan header telemetri Edge
      const finalHeaders = new Headers(response.headers);
      finalHeaders.set("x-edge-processed-by", "gateway-worker-v1");

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: finalHeaders,
      });

    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Internal Cryptographic Verification Error";
      return new Response(JSON.stringify({ error: "Unauthorized access", details: errorMessage }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }
  }
};

/**
 * Verifikasi signature JWT HS256 sederhana menggunakan Web Crypto API
 * (Pada arsitektur asimetris produksi, gunakan RS256/ES256 via JWKS cache)
 */
async function verifyTokenSignature(token: string, env: Env): Promise<JWTPayload> {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid JWT segment structure");
  }

  const [headerB64, payloadB64, signatureB64] = parts;

  // Decoding Payload
  const payloadJson = new TextDecoder().decode(base64UrlDecode(payloadB64));
  const payload: JWTPayload = JSON.parse(payloadJson);

  // Verifikasi Signature dengan HMAC-SHA256 (Secret demo: fallback internal key)
  const secretKey = "enterprise-production-hmac-shared-secret";
  const encoder = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secretKey),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"]
  );

  const dataToVerify = encoder.encode(`${headerB64}.${payloadB64}`);
  const signatureBytes = base64UrlDecode(signatureB64);

  const isValid = await crypto.subtle.verify(
    "HMAC",
    cryptoKey,
    signatureBytes,
    dataToVerify
  );

  if (!isValid) {
    throw new Error("Cryptographic signature mismatch");
  }

  return payload;
}

function base64UrlDecode(input: string): Uint8Array {
  let base64 = input.replace(/-/g, "+").replace(/_/g, "/");
  while (base64.length % 4) {
    base64 += "=";
  }
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}
```

##### C. Private Backend Worker yang dituju (`core-catalog-backend`):
```typescript
// Implementasi Worker internal yang TIDAK memiliki DNS eksternal publik
export default {
  async fetch(request: Request): Promise<Response> {
    const userId = request.headers.get("x-user-id");
    const roles = request.headers.get("x-user-roles");

    const data = {
      timestamp: new Date().toISOString(),
      invoker: userId,
      accessRoles: roles?.split(","),
      payload: [
        { id: "PROD-001", sku: "ENTERPRISE-COMPUTE-ENGINE", inventory: 420 },
        { id: "PROD-002", sku: "EDGE-CACHE-REPLICATOR", inventory: 89 }
      ]
    };

    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  }
};
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur E-Commerce Global Multi-Region (PT Global Retail Logistik)
- **Kondisi Awal:**
  - Aplikasi storefront monolitik SSR di-host di AWS Singapore (`ap-southeast-1`).
  - Total trafik: 45.000 RPS pada saat flash sale.
  - Pengguna di Eropa dan AS mengalami latency TTFB rata-rata 850ms–1400ms karena koneksi intercontinental TLS handshake dan rendering server yang tersentralisasi.
  - Biaya cloud egress AWS mencapai puluhan ribu USD per bulan hanya untuk menyajikan dynamic localized catalog.

- **Solusi Arsitektur Menggunakan Cloudflare Edge:**
  1. **Fullstack Migration ke Pages & Workers:**
     Storefront diubah menjadi Next.js edge-optimized menggunakan `@cloudflare/next-on-pages`. Komponen frontend di-deploy via Cloudflare Pages.
  2. **Smart Placement Worker API:**
     Worker yang membutuhkan integrasi transaksional langsung ke Postgres AWS dikonfigurasi dengan `smart_placement = true`. Cloudflare secara dinamis mengeksekusi Isolate compute Worker tersebut di Edge data center Ashburn/Singapura (dekat RDS).
  3. **Zero-Latency Micro-Frontend Routing:**
     Tim Checkout, Search, dan Product Details mengelola sub-aplikasi independen yang dikomposisikan di Edge menggunakan Service Bindings tanpa overhead API Gateway terpusat.
  4. **Dynamic Price Localization via Streams:**
     Mata uang dan pajak lokal diinjeksikan secara real-time ke dalam HTML body stream menggunakan `HTMLRewriter` langsung di Edge PoP lokal pengguna, menghapus ketergantungan render di Origin.

- **Hasil Pengujian Produksi:**
  - **TTFB Global:** Turun drastis dari 920ms rata-rata menjadi **48ms**.
  - **Origin CPU Load:** Beban server origin berkurang sebesar **78%**.
  - **Penghematan Bandwidth:** Egress cost origin turun sebesar **65%** berkat caching HTML dinamis dan kompresi edge.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian & Batasan |
| :--- | :--- | :--- |
| **Edge Compute (Cloudflare Workers)** | - Latensi jaringan ultra-rendah (<10ms ke user)<br>- Zero cold-start native<br>- Tidak ada manajemen infrastruktur/OS patching | - Runtime terbatas pada subset Web APIs (tidak ada binary C native bebas atau Node child processes)<br>- Batas eksekusi CPU time (50ms standar / hingga beberapa ratus ms di Workers Unbound)<br>- Memori per request maksimal 128MB–512MB |
| **Traditional Serverless (AWS Lambda)** | - Ekosistem luas (library native C/C++, Docker container support)<br>- Kapasitas memori hingga 10GB<br>- Durasi eksekusi hingga 15 menit | - Cold-start latency (200ms - 3 detik)<br>- Egress bandwidth cost tinggi<br>- Eksekusi terikat pada satu atau beberapa region yang dipilih |
| **Regional Container (Kubernetes Pods)** | - Kontrol penuh terhadap runtime, OS, kernel profiling<br>- Bebas batasan durasi proses dan memori per connection | - Kompleksitas pemeliharaan cluster dan auto-scaling rules<br>- Latensi inter-kontinental bagi pengguna global<br>- Biaya komputasi fixed/idle compute |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Memory Exhaustion via Stream Buffering
- **Kesalahan:** Menggunakan `await response.text()` atau `await response.json()` untuk payload berukuran besar (misal: > 50MB) yang memicu pesan error: `Error: Worker exceeded resource limits (Worker CPU/Memory limit hit)`.
- **Solusi:** Gunakan `TransformStream` dan hubungkan langsung melalui pipa `response.body.pipeThrough(...)`. Jangan pernah menahan seluruh array buffer di level isolate jika hanya ingin meneruskan atau memodifikasi streaming data.

#### 10.2 Service Binding Deadlock
- **Kesalahan:** Worker A memanggil Worker B via Service Binding, kemudian Worker B melakukan subrequest HTTP kembali ke URL publik Worker A.
- **Penyebab:** Siklus ketergantungan rekursif yang menghabiskan slot concurrent subrequests per-request limit (maksimal 50 subrequests concurrent).
- **Solusi:** Rancang arsitektur strictly Directional Acyclic Graph (DAG). Worker downstream tidak boleh memanggil Worker upstream. Gunakan arsitektur event decoupling seperti Cloudflare Queues untuk komunikasi balik asinkron.

#### 10.3 Unhandled Rejections dalam `ctx.waitUntil()`
- **Kesalahan:** Menjalankan operasi asinkron analitik/logging menggunakan `ctx.waitUntil(promise)` tanpa blok `catch`.
- **Dampak:** Jika promise mengalami panic/reject, Workers runtime akan mencatat unhandled promise rejection yang dapat menggagalkan eksekusi runtime context.
- **Solusi:**
  ```typescript
  ctx.waitUntil(
    sendAnalytics(data).catch((err) => {
      console.error("Telemetry failed to dispatch to collector:", err);
    })
  );
  ```

#### 10.4 Mengabaikan Isolasi Global State Mutability
- **Kesalahan:** Mengandalkan variabel global in-memory untuk menyimpan state request antar-pengguna:
  ```typescript
  // ANTI-PATTERN: Variabel global ini di-share pada Isolate yang sama!
  let userSessionCache: Record<string, any> = {};
  ```
- **Dampak:** Isolate dapat di-recycle sewaktu-waktu atau dibagikan ke request lain yang dieksekusi secara konkuren pada instance yang sama, menyebabkan kebocoran data (*data leak antar tenant*).
- **Solusi:** Anggap runtime Worker sepenuhnya stateless. Gunakan Durable Objects, Cloudflare KV, Hyperdrive, atau persistent remote storage untuk state manajemen.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Aktifkan Compatibility Flags Modern:** Selalu tentukan versi modern pada `wrangler.toml`:
   ```toml
   compatibility_date = "2024-04-01"
   compatibility_flags = ["nodejs_compat"]
   ```
2. [ ] **Gunakan Service Bindings Menggantikan Public HTTP:** Hindari pemanggilan antar microservice edge menggunakan URL `https://...`. Gunakan `services` declaration pada configuration untuk performa dan keamanan isolasi network.
3. [ ] **Optimasi Subrequest Multiplexing:** Gunakan `Promise.all()` untuk subrequests independen guna memanfaatkan koneksi paralel internal engine.
4. [ ] **Implementasikan Dead-Man Circuit Breaker:** Ketika downstream origin lambat, gunakan abort controller timeout:
   ```typescript
   const controller = new AbortController();
   const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 sec timeout
   const res = await fetch(originUrl, { signal: controller.signal });
   clearTimeout(timeoutId);
   ```
5. [ ] **Manfaatkan Tail Workers:** Konfigurasi Tail Worker terpisah untuk audit security dan log aggregation tanpa menambah latency pada Worker utama.
6. [ ] **Terapkan Gradual Deployments (Canary):** Hindari cut-over 100% langsung untuk release kritis; gunakan rule persentase routing via Cloudflare API.

---

### 12. Hands-on Practice

Struktur direktori praktikum:
```text
hands-on/m02/
├── wrangler.toml
├── package.json
├── tsconfig.json
└── src/
    ├── index.ts
    ├── rate-limiter.ts
    └── types.ts
```

#### Langkah 1: Inisialisasi Environment TypeScript Modern
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install --save-dev typescript wrangler @cloudflare/workers-types
```

#### Langkah 2: Konfigurasi `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "types": ["@cloudflare/workers-types"],
    "strict": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src/**/*"]
}
```

#### Langkah 3: Konfigurasi `wrangler.toml` Produksi
```toml
name = "edge-production-pipeline"
main = "src/index.ts"
compatibility_date = "2024-04-01"
compatibility_flags = ["nodejs_compat"]

[vars]
ENVIRONMENT = "production"
MAX_ALLOWED_WINDOW = "60"

# Tail worker integration untuk observabilitas
# (Bisa di-uncomment jika tail worker sudah ter-deploy)
# [[tail_consumers]]
# service = "enterprise-tail-logger"
```

#### Langkah 4: Tulis Tipe Data `src/types.ts`
```typescript
export interface Env {
  ENVIRONMENT: string;
  MAX_ALLOWED_WINDOW: string;
}

export interface SecurityAuditLog {
  clientIp: string;
  userAgent: string;
  method: string;
  path: string;
  edgePop: string;
  timestamp: number;
  durationMs: number;
}
```

#### Langkah 5: Tulis Utility Sliding Window Rate-Limiter In-Memory `src/rate-limiter.ts`
```typescript
// Implementasi sliding memory counter sederhana di edge level
const rateLimitMap = new Map<string, { count: number; expiresAt: number }>();

export function checkRateLimit(clientIp: string, maxRequests = 100, windowSec = 60): boolean {
  const now = Date.now();
  const clientData = rateLimitMap.get(clientIp);

  if (!clientData || now > clientData.expiresAt) {
    rateLimitMap.set(clientIp, { count: 1, expiresAt: now + windowSec * 1000 });
    return true;
  }

  if (clientData.count >= maxRequests) {
    return false; // Rate limited
  }

  clientData.count++;
  return true;
}
```

#### Langkah 6: Implementasi Worker Utama dengan Streaming Security Sanitizer `src/index.ts`
```typescript
import { Env, SecurityAuditLog } from "./types";
import { checkRateLimit } from "./rate-limiter";

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const startTime = performance.now();
    const clientIp = request.headers.get("cf-connecting-ip") || "127.0.0.1";
    const pop = (request as any).cf?.colo || "UNKNOWN";
    const url = new URL(request.url);

    // 1. Rate Limiting Check
    const isAllowed = checkRateLimit(clientIp, 150, parseInt(env.MAX_ALLOWED_WINDOW));
    if (!isAllowed) {
      return new Response(JSON.stringify({ error: "HTTP 429: Rate limit exceeded at edge." }), {
        status: 429,
        headers: { "content-type": "application/json" }
      });
    }

    // 2. Mock upstream origin proxy call
    const upstreamUrl = `https://jsonplaceholder.typicode.com${url.pathname}`;
    const originResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers: {
        "x-forwarded-by": "cloudflare-edge",
        "accept": "application/json"
      }
    });

    // 3. Setup Transform Stream untuk memfilter/mengaburkan PII (Personally Identifiable Information)
    const piiRedactor = new TransformStream({
      transform(chunk: Uint8Array, controller) {
        const decoder = new TextDecoder();
        const encoder = new TextEncoder();
        let payloadText = decoder.decode(chunk);

        // Regex substitusi sederhana untuk email masking
        payloadText = payloadText.replace(
          /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g,
          "***MASKED_PII_EMAIL***"
        );

        controller.enqueue(encoder.encode(payloadText));
      }
    });

    const transformedStream = originResponse.body ? originResponse.body.pipeThrough(piiRedactor) : null;

    // 4. Observability: Dispatch audit log via context execution (non-blocking)
    ctx.waitUntil(
      (async () => {
        const duration = performance.now() - startTime;
        const auditLog: SecurityAuditLog = {
          clientIp,
          userAgent: request.headers.get("user-agent") || "unknown",
          method: request.method,
          path: url.pathname,
          edgePop: pop,
          timestamp: Date.now(),
          durationMs: duration
        };

        // Simulasi pengiriman async telemetri ke observability backend
        console.log(`[EDGE TELEMETRY]: ${JSON.stringify(auditLog)}`);
      })()
    );

    // 5. Kembalikan stream ke client
    return new Response(transformedStream, {
      status: originResponse.status,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "x-edge-pop": pop,
        "x-edge-env": env.ENVIRONMENT
      }
    });
  }
};
```

#### Langkah 7: Pengujian Eksekusi Lokal
Jalankan Wrangler development server:
```bash
npx wrangler dev
```
Uji menggunakan `curl` pada terminal terpisah:
```bash
curl -i http://localhost:8787/comments/1
```
Periksa bahwa output email pada payload respons telah tersensor menjadi `***MASKED_PII_EMAIL***` tanpa terjadi memory crash.

---

### 13. Exercise

#### Level Easy
Ubah implementasi streaming pada `hands-on/m02/src/index.ts` agar menyuntikkan header kustom bernama `x-response-timestamp` yang berisi epoch time milidetik saat respons mulai dipancarkan dari edge.

#### Level Medium
Buat sebuah middleware Cloudflare Pages Functions (`functions/_middleware.ts`) yang:
1. Membaca header `CF-IPCountry`.
2. Jika negara asal adalah blacklist (misal: `"XX"`), secara instan menghentikan rantai pemanggilan (*terminate chain*) dan mengembalikan response error HTTP 403 Forbidden dengan payload JSON.
3. Jika lolos, teruskan request ke `next()` dan tambahkan header latency `x-function-time` ke response akhir.

#### Level Hard
Rancang dan implementasikan sebuah Edge Reverse-Proxy Circuit Breaker menggunakan Workers:
1. Setiap kali terjadi upstream error (status code 500, 502, 503, 504 berturut-turut sebanyak 5 kali), Worker secara otomatis mengaktifkan status *Tripped/Open* selama 30 detik.
2. Saat status *Open*, Worker tidak lagi memanggil upstream, melainkan menyajikan fallback payload JSON statis lokal dengan HTTP 200 dan header `x-circuit-status: OPEN`.
3. Setelah 30 detik berlalu (*Half-Open*), Worker mencoba mengalirkan 1 request uji coba ke upstream. Jika berhasil, status kembali ke *Closed*.

---

### 14. Challenge

**Skenario Sistem:**
Anda adalah Principal Cloud Infrastructure Architect di sebuah perusahaan Fintech Multi-tenant Global. Anda diminta membangun **Edge Intelligent Dynamic Routing Engine** menggunakan Cloudflare Workers yang memenuhi kriteria berikut:

1. **Dynamic Tenant Context Injection:**
   Sistem harus membedakan tenant dari Subdomain (`tenant-a.api.enterprise.com`) atau kustom header `X-Tenant-ID`.
2. **Canary Deployment Engine:**
   Sistem membaca konfigurasi persentase release dari KV/Environment (misal: 10% trafik diarahkan ke Worker Canary version, 90% ke Worker Stable version).
3. **Zero-Latency In-Memory Invocation:**
   Routing ke service masing-masing dilakukan menggunakan **Service Bindings** murni (bukan `fetch` melalui HTTP URL publik).
4. **Resiliency Failover:**
   Jika eksekusi Service Binding Canary melemparkan Exception/Error 5xx, gateway harus melakukan fail-over transparan (*silent fallback*) ke Worker Stable secara real-time tanpa mengembalikan error ke client.
5. **Observability via Tail Worker:**
   Setiap alur penanganan request harus mengirim metadata jejak eksekusi (apakah kena routing Canary, waktu eksekusi, fallback terjadi atau tidak) ke Tail Worker tanpa mengganggu aliran I/O respons utama.

*Tugas Anda:* Rancang arsitektur sistem, skema konfigurasi `wrangler.toml`, dan kode TypeScript gateway produksinya tanpa menggunakan library eksternal selain runtime standar Cloudflare.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. Apa perbedaan arsitektural utama antara eksekusi Cloudflare Workers dengan AWS Lambda konvensional?
2. Mengapa cold start pada Cloudflare Workers dapat ditekan hingga di bawah 5 milidetik?
3. Apa batasan utama jika kita menggunakan memori global variabel untuk menyimpan state data pengguna di dalam Worker script?
4. Apa fungsi dari parameter `ctx.waitUntil(promise)` pada lifecycle request Worker?
5. Mengapa pemanggilan antar Worker menggunakan **Service Bindings** lebih efisien dibandingkan pemanggilan fetch berbasis URL domain eksternal?

#### Bagian 2: Intermediate (5 Pertanyaan)
6. Bagaimana cara kerja mekanik aliran data pada `TransformStream` yang mencegah terjadinya memory overflow saat memproses payload respons besar di Edge?
7. Jelaskan algoritma heuristik yang digunakan Cloudflare **Smart Placement** untuk menentukan lokasi PoP eksekusi Worker.
8. Apa yang terjadi jika subrequest di dalam Worker memakan waktu lebih lama dari batas waktu *CPU execution time*? Apakah Worker akan langsung crash?
9. Bagaimana mekanisme Pages Functions menyusun pipeline eksekusi saat terdapat beberapa file `_middleware.ts` bersarang pada direktori bertingkat?
10. Mengapa kita tidak disarankan melakukan hashing password menggunakan `bcrypt` versi murni JavaScript di dalam Cloudflare Workers? Alternatif apa yang diwajibkan runtime?

#### Bagian 3: Skenario Kasus Produksi (3 Skenario)
11. **Skenario A:** Sebuah Worker streaming video proxy mengalami lonjakan CPU limit (*Error 1102: Worker exceeded CPU limit*) padahal throughput bandwidth hanya 25 MB/s. Setelah dianalisis, developer menggunakan manipulasi buffer string regex untuk parsing binary data. Bagaimana arsitektur yang benar untuk memproses binary stream pada Workers?
12. **Skenario B:** Tim Anda me-release konfigurasi Canary 20% pada Gateway Worker baru menggunakan Service Bindings. Namun, data metrik analitik menunjukkan 100% request tetap masuk ke instance versi lama. Tidak ada error build pada deploy log. Apa titik pemeriksaan prioritas Anda pada konfigurasi routing environment dan deployment tags?
13. **Skenario C:** Sebuah aplikasi global mengalami lonjakan pembacaan data JWKS dari endpoint auth origin terpusat, menyebabkan origin auth server tumbang (*DDoS oleh Edge sendiri*). Bagaimana Anda mengonfigurasi cache level-edge menggunakan Cache API standar Workers untuk mencegah Worker memanggil JWKS origin berulang kali?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. Cloudflare Workers berjalan di atas *V8 Isolates* di dalam proses yang terbagi (*shared multi-tenant process*), sedangkan AWS Lambda mengisolasi eksekusi menggunakan virtual machine ringan (*MicroVM Firecracker*) lengkap dengan Linux guest OS.
2. Karena Isolate tidak perlu me-load OS kernel, memory container, atau inisialisasi environment runtime baru; V8 Isolate hanya menciptakan context eksekusi Javascript baru di atas engine C++ yang sudah berjalan hangat (*pre-warmed process*).
3. Variabel global bersifat ephemeral, terikat pada siklus hidup Isolate individual yang dapat di-destroy sewaktu-waktu, dan berisiko mengalami *data leak* karena satu isolate instance dapat melayani request dari pengguna yang berbeda secara bergantian.
4. Memberitahu Workers runtime untuk memperpanjang masa aktif konteks eksekusi di latar belakang hingga promise selesai dieksekusi, meskipun stream respons HTTP sudah dikirimkan dan ditutup ke client.
5. Service Bindings berjalan langsung pada level internal memory pointer swap antar-isolate (Zero-cost IPC), mengeliminasi network serialization, DNS lookup, koneksi TCP socket, dan lapisan enkripsi TLS tambahan.

#### Bagian 2: Intermediate
6. `TransformStream` memecah payload menjadi *chunks* kecil yang independen secara berurutan. Begitu sebuah *chunk* diproses, data tersebut segera dialirkan ke out-stream dan dilepaskan dari memori isolate (*garbage collected*) sebelum chunk berikutnya diambil, menjaga konsumsi memori stabil konstan.
7. Cloudflare melacak latensi subrequest dari berbagai PoP ke origin server backend. Jika total latensi Worker didominasi oleh subrequest roundtrip bolak-balik ke origin, heuristik Smart Placement secara otomatis menjadwalkan eksekusi Worker di data center terdekat dengan origin backend.
8. Tidak serta merta. *CPU Execution Time* hanya menghitung durasi CPU aktif memproses instruksi JavaScript. Waktu tunggu jaringan I/O (seperti menunggu balasan `fetch` backend) dihitung sebagai *Wall-clock Time*, sehingga tidak memakan kuota CPU time limit.
9. Eksekusi berjalan secara hierarkis seperti *onion-model* (serupa Koa middleware). Middleware pada root directory dieksekusi terlebih dahulu sebelum request diteruskan secara bertingkat ke direktori yang lebih dalam via fungsi `next()`, dan proses unwinding respons terjadi dengan urutan sebaliknya.
10. `bcrypt` JavaScript murni melakukan komputasi CPU-bound intensif yang memblokir Event Loop Isolate sehingga akan cepat menabrak limit CPU Execution time (50ms). Pengembang diwajibkan menggunakan Web Crypto API native (`crypto.subtle`) berbasis implementasi engine C++ yang terakselerasi dan asynchronous.

#### Bagian 3: Skenario Kasus Produksi
11. **Penyebab & Solusi:** Mengonversi data stream biner menjadi string memicu alokasi memori berlebih dan eksekusi parsing regex pada event-loop Isolate memakan waktu CPU yang tinggi. Solusi: Gunakan native `Uint8Array` chunks langsung pada stream handler dan manfaatkan zero-copy memory WebAssembly (Wasm) yang dikompilasi dari Rust/C jika manipulasi biner tingkat rendah diperlukan.
12. **Titik Pemeriksaan:**
    - Periksa apakah konfigurasi `wrangler.toml` mengarahkan binding ke *environment* tertentu (`production` vs `canary`).
    - Verifikasi apakah gradual deployment diaktifkan pada Worker entrypoint yang benar atau hanya di-deploy sebagai tag script terpisah tanpa traffic routing percentage assignment pada Cloudflare API.
    - Pastikan request routing tidak ter-cache secara agresif di Edge Gateway Cache sebelum mencapai logika Worker.
13. **Solusi:**
    - Gunakan Workers Cache API (`caches.default`) untuk menyimpan public key set (JWKS) di edge data center lokal.
    - Tetapkan response header `Cache-Control: public, max-age=86400, stale-while-revalidate=3600`.
    - Simpan promise JWKS dalam in-memory cache sementara per-isolate context dengan strategi graceful fallback jika fetch baru mengalami kegagalan.

---

### 16. Summary

- **V8 Isolate Architecture** memberikan keunggulan performa mutlak berupa start-up time mendekati nol (*zero-cold start*) dan efisiensi memori tingkat tinggi dibandingkan arsitektur berbasis MicroVM/Container.
- **Service Bindings** mentransformasi arsitektur microservices terdistribusi di edge dengan menghadirkan komunikasi in-memory zero-latency antar Worker independen, meningkatkan keamanan modular tanpa degradasi performa.
- **Streaming Native (Web Streams API)** adalah fondasi pemrosesan payload data skala besar di edge, memungkinkan sanitasi, transformasi, dan pengayaan respons data dengan *memory footprint* minimal dan stabil di bawah limit runtime.
- **Smart Placement** dan **Web Crypto API** melengkapi arsitektur produksi Cloudflare Edge dengan memastikan kalkulasi kriptografi cepat dan penempatan titik komputasi optimal mendekati backend terpusat saat integrasi origin dibutuhkan.