# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Utama:** Next.js Enterprise Architecture
*   **Modul:** Bab 08 Module 01: Integrasi Database, Connection Pooling, & Edge Storage
*   **Prasyarat:** Next.js App Router (Server Components & Server Actions), TypeScript Lanjutan, Arsitektur Database Relasional (PostgreSQL), Asynchronous JavaScript Runtime Internals.
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Alokasi Waktu:** 8 Jam (Teori, Deep Dive, Implementasi Laboratorium)

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Mendiagnosis dan Mengeliminasi Connection Exhaustion:** Memahami siklus hidup koneksi TCP/IP dalam lingkungan Serverless/Edge compute dan menerapkan pooling proxy (PgBouncer, Prisma Accelerate, Supabase Supavisor) secara deterministik.
2.  **Mengimplementasikan Pola Singleton Prisma Engine:** Mengonfigurasi Prisma Client dan Drizzle ORM pada Next.js App Router tanpa memicu kebocoran memori akibat Hot Module Replacement (HMR) di lingkungan development atau konkurensi tak terkendali di production.
3.  **Mengintegrasikan Database Dialect HTTP/WebSocket:** Membangun lapisan data transport independen terhadap stateful TCP connection menggunakan protokol HTTP/WebSocket (misal: `@neondatabase/serverless`) untuk eksekusi query latensi rendah pada Vercel Edge Runtime / Cloudflare Workers.
4.  **Mendesain Global Edge Caching & Distributed KV Store:** Mengoperasikan Upstash Redis dan Cloudflare KV di layer Edge untuk memangkas latensi TTFB data dinamis melalui caching read-heavy berkinerja tinggi.
5.  **Menerapkan Zero-Trust Security & Resilient Architecture:** Memitigasi ancaman SQL Injection, mengisolasi credential environment variables dari browser context, serta membangun mekanisme graceful degradation saat terjadi database failover.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam model server konvensional (misal: Node.js/Express LTS yang berjalan di atas VPS atau container Kubernetes berumur panjang), sebuah aplikasi memulai proses, membuat satu pool koneksi TCP (misal: 10–20 koneksi), dan membagikan koneksi-koneksi tersebut ke ribuan request yang masuk secara bergantian (*interleaved I/O*).

```
[ Model Tradisional (Long-Running Process) ]
Client Req 1 ──┐
Client Req 2 ──┼──> [ Next.js Node Process ] ─── (Connection Pool: 10 Conn) ───> [ PostgreSQL ]
Client Req 3 ──┘
```

Namun, di era **Serverless & Edge Runtime**, paradigma tersebut berubah drastis:
1.  **Ephemeral Instances (Fungsi Berumur Pendek):** Runtime Next.js (AWS Lambda, Vercel Serverless Functions) di-*scale up* secara instan dari 0 hingga 1.000 instance terisolasi saat terjadi lonjakan traffic (*burst*).
2.  **Satu Instance = Satu Pool Baru:** Jika setiap instance serverless menginisialisasi 5–10 koneksi TCP ke PostgreSQL, maka 1.000 instance akan mencoba membuka **5.000–10.000 koneksi TCP langsung** secara bersamaan.
3.  **PostgreSQL Connection Collapse:** PostgreSQL mengalokasikan proses terpisah (`postgres: backend process`) dan memori kerja (`work_mem`) untuk setiap koneksi klien. Batas default PostgreSQL umumnya berkisar antara 100 hingga 300 koneksi. Ketika batas ini terlampaui, database akan mengalami *connection starvation*, menolak koneksi baru (`FATAL: remaining connection slots are reserved`), kehabisan RAM, dan akhirnya *crash*.

```
[ Model Serverless Tanpa Pooling (Anti-Pattern) ]
Instance #001 ─── (Pool: 5) ───┐
Instance #002 ─── (Pool: 5) ───┼──> [ 1000 Instances = 5000 Connections! ] ──X [ PostgreSQL max_connections=100 ]
Instance #999 ─── (Pool: 5) ───┘                                              (DATABASE CRASH: Out of RAM / Starvation)
```

**Mental Model yang Benar:** 
Pandang lingkungan Serverless/Edge Anda sebagai kumpulan agen I/O tanpa status (*stateless transient workers*). Mereka tidak boleh mempertahankan koneksi TCP persisten jangka panjang ke database relasional internal. Komunikasi harus didelegasikan melalui:
*   **Connection Pooler Middleware Eksternal (Transaction Pooling Mode)** yang menyerap lonjakan ribuan koneksi stateless dan memadatkannya menjadi beberapa puluh koneksi TCP stabil ke engine database.
*   **Stateless HTTP/WebSocket Gateways** di mana *transport protocol* TCP dienkapsulasi ke dalam stateless request-response HTTP pipelining.
*   **Edge KV/Cache Store** sebagai filter pertama guna memotong eksekusi query database sebelum mencapai storage engine utama.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur hibrida end-to-end yang mengintegrasikan Next.js (Node.js runtime & Edge runtime), Connection Pooler, Database Relasional, dan Edge In-Memory Storage:

```
+----------------------------------------------------------------------------------------------------+
|                                      GLOBAL CLIENTS / BROWSERS                                     |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+----------------------------------------------------------------------------------------------------+
|                              EDGE NETWORK (CDN / ANYCAST ROUTING)                                  |
|                                                                                                    |
|   +--------------------------------------------------------------------------------------------+   |
|   | Next.js Edge Runtime (Vercel Edge / Cloudflare Workers)                                    |   |
|   | - Middleware, Auth Verification, Fast Edge Route Handlers                                  |   |
|   +--------------------------------------------------------------------------------------------+   |
|             │                                                                 │                    |
|             │ (Sub-millisecond Read/Write)                                     │ (Stateless HTTP)   |
|             ▼                                                                 ▼                    |
|   +-------------------+                                             +--------------------+         |
|   | Upstash Redis KV  |                                             | Neon HTTP Query    |         |
|   | (Global Cluster)  |                                             | Gateway            |         |
|   +-------------------+                                             +--------------------+         |
|             ▲                                                                 │                    |
+-------------│-----------------------------------------------------------------│--------------------+
              │                                                                 │
              │ Cache Invalidation                                              │ Fast Edge Read
              │ via Server Actions                                              │
              │                                                                 │
+-------------│-----------------------------------------------------------------│--------------------+
|             │                REGION DATA CENTER (AWS us-east-1)               │                    |
|             │                                                                 │                    |
|   +-------------------------------------------------------------+             │                    |
|   | Next.js Serverless Functions (Node.js Runtime)              |             │                    |
|   | - Prisma / Drizzle ORM                                      |             │                    |
|   | - Complex Business Logic, Heavy Mutations, Server Actions   |             │                    |
|   +-------------------------------------------------------------+             │                    |
|             │                                                                 │                    |
|             │ TCP Handshake (Connection via Singleton Pooler)                 │                    |
|             ▼                                                                 │                    |
|   +-------------------------------------------------------------+             │                    |
|   | External Connection Pooler (PgBouncer / Supavisor)          |             │                    |
|   | - Pooling Mode: Transaction                                 |             │                    |
|   | - Mengubah ribuan koneksi fungsi -> Pool stabil 20-50 conn  |             │                    |
|   +-------------------------------------------------------------+             │                    |
|             │                                                                 │                    |
|             │ Persistent Local Unix Socket / Low-Latency TCP                  │                    |
|             ▼                                                                 ▼                    |
|   +------------------------------------------------------------------------------------+           |
|   | Primary PostgreSQL Database Cluster (Engine: Neon / Supabase / AWS Aurora RDS)     |           |
|   | - Storage Engine (NVMe/EBS)                                                        |           |
|   | - Write-Ahead Logging (WAL)                                                        |           |
|   +------------------------------------------------------------------------------------+           |
+----------------------------------------------------------------------------------------------------+
```

### Siklus Eksekusi Request:
1. **Edge Read Flow:** Klien mengakses halaman profil. Next.js Edge Runtime mencegat request, memeriksa Upstash Redis KV. Jika cache hit, data dikembalikan dalam <15ms tanpa menyentuh database relasional.
2. **Cold Query Flow:** Jika cache miss, Edge Runtime mengeksekusi stateless SQL melalui Neon HTTP Driver melewati port 443 tanpa overhead TCP 3-way handshake database konvensional.
3. **Heavy Transaction/Mutation Flow:** Server Action pada Node.js runtime dieksekusi. Runtime memanggil singleton Prisma/Drizzle client yang terhubung ke PgBouncer/Supavisor (port 6543) via transaction mode. PgBouncer meminjamkan koneksi PostgreSQL fisik hanya selama transaksi aktif, lalu segera mengembalikannya ke pool.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Anatomi TCP Handshake vs HTTP Database Transport

Dalam database relasional standar berbasis TCP:
1. **SYN $\rightarrow$ SYN-ACK $\rightarrow$ ACK** (1.5 Round Trip Time / RTT).
2. **TLS Handshake** (Client Hello $\rightarrow$ Server Hello $\rightarrow$ Certificate $\rightarrow$ Key Exchange) (1–2 RTT).
3. **Database Authentication Packet Exchange** (StartupMessage $\rightarrow$ AuthenticationMD5/SASL $\rightarrow$ ReadyForQuery) (2 RTT).
Total overhead sebelum query pertama dapat dieksekusi: **4.5–5.5 RTT**. Jika serverless instance berada di region Frankfurt (eu-central-1) dan database berada di N. Virginia (us-east-1) dengan RTT 75ms, maka inisialisasi koneksi membutuhkan waktu **>350ms** murni untuk overhead jaringan.

HTTP-based Database Drivers (seperti Neon serverless driver) membungkus query SQL ke dalam single stateless HTTP POST payload:
* Memanfaatkan koneksi HTTPS persistent/multiplexed (HTTP/2 atau HTTP/3 QUIC) ke gateway terdekat.
* Eksekusi query dikirim dalam *single flight*: Request payload membawa token enkripsi, metadata sesi, dan teks SQL. Gateway lokal mengeksekusinya ke database core via dedicated fiber backbone. Latensi tereduksi menjadi **1 RTT**.

### 2. Mekanisme Internal PgBouncer: Session vs Transaction vs Statement Pooling

| Mode Pooling | Kapan Koneksi Database Dilepas? | Kompatibilitas Fitur PostgreSQL | Cocok untuk Serverless? |
| :--- | :--- | :--- | :--- |
| **Session Pooling** | Ketika klien secara eksplisit memutus koneksi TCP. | 100% kompatibel dengan semua fitur PostgreSQL (Prepared Statements, `LISTEN/NOTIFY`, Temporary Tables). | **TIDAK**. Instance serverless yang mati mendadak dapat menggantung (*idle-in-transaction*) koneksi. |
| **Transaction Pooling** | Segera setelah transaksi (`COMMIT` atau `ROLLBACK`) selesai. | Memutus dukungan untuk modul yang terikat pada level sesi (`LISTEN/NOTIFY`, session-level `SET`, dynamic prepared statements default). | **SANGAT DIREKOMENDASIKAN**. Memungkinkan 10.000 worker berbagi 50 koneksi aktif. |
| **Statement Pooling** | Segera setelah single statement SQL selesai dieksekusi. | Transaksi multi-statement (`BEGIN ... COMMIT`) **TIDAK didukung**. | **JARANG**. Sangat restriktif untuk aplikasi OLTP modern. |

### 3. V8 Engine Isolate vs Node.js Event Loop di Next.js

* **Node.js Serverless Runtime:** Menjalankan runtime Node.js penuh dengan akses ke libc, libuv, POSIX socket API (`net`, `tls`). Driver database TCP tradisional (misal: pg, mysql2) dapat berjalan dengan lancar.
* **Edge Runtime (V8 Isolate):** Tidak memiliki event loop Node.js penuh dan **TIDAK MEMILIKI modul `net` atau `tls` bawaan**. Runtime ini hanya mengimplementasikan standar Web API (`fetch`, `Request`, `Response`, `SubtleCrypto`, `WebSocket`). Inilah mengapa ORM tradisional yang mengandalkan direct TCP socket akan melempar error fatal: `Error: Module not found: Can't resolve 'net'` jika dieksekusi di Edge Runtime.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Prisma Engine Architecture: Library vs Binary vs WASM

Prisma tidak berkomunikasi secara langsung dari TypeScript ke PostgreSQL. Di balik layar, Prisma menggunakan arsitektur engine internal:
* **Query Engine (Rust):** Kode TypeScript Prisma mengompilasi Abstract Syntax Tree (AST) dari query Anda, mengirimkannya melalui Foreign Function Interface (FFI) atau Node-API wrapper ke binary Rust.
* **Rust Connection Pool:** Binary Rust tersebut memelihara pool koneksi TCP internal miliknya sendiri. Ukuran pool ini diatur melalui parameter URL `connection_limit` (default: $\text{num\_cpus} \times 2 + 1$).
* **Prisma Accelerate & WASM:** Untuk Edge Runtime di mana binary native Rust (.so/.dylib) tidak dapat di-spawn, Prisma mengompilasi engine Rust ke WebAssembly (WASM) dan menggunakan driver adapter (`@prisma/adapter-pg` atau `@prisma/adapter-neon`) yang memetakan pemanggilan I/O Rust ke Web API fetch/WebSocket.

### Drizzle ORM: Zero-Overhead Compilation

Berbeda dengan Prisma, Drizzle ORM tidak memiliki query engine binary perantara. Drizzle bertindak murni sebagai *query builder & type mapper*:
* Menghasilkan string SQL mentah dan binding parameter langsung dalam JavaScript heap memory.
* Ukuran bundle Drizzle sangat kecil (~50KB vs Prisma >10MB binary footprint), sehingga secara signifikan memangkas waktu **Cold Start** pada Next.js Serverless Functions (dari ~800ms menjadi <100ms).

### Distributed Cache Invalidation: Stale-While-Revalidate (SWR) Pattern

Pada Edge Storage (Upstash Redis), integritas data dijamin melalui kombinasi Read-Through Cache dan Event-Driven Invalidation:
1. **Cache-Aside Pattern:** Aplikasi membaca dari Edge Cache. Jika terjadi miss, baca dari Primary DB melalui Transaction Pooler, lalu tuliskan hasilnya ke Cache dengan parameter TTL (Time-To-Live).
2. **Server Action Invalidation:** Setiap kali mutasi data berhasil dijalankan (misal: `updateUserProfile()`), aplikasi wajib memicu dua langkah atomik:
   * Menulis data baru ke Database Relasional.
   * Mengirim instruksi `redis.del(cacheKey)` atau memperbarui cache secara inline, serta memanggil `revalidateTag()` / `revalidatePath()` bawaan Next.js.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan dua pendekatan modern untuk integrasi data layer di Next.js:
1. **Pendekatan A:** Node.js Runtime menggunakan Prisma dengan Singleton Connection Pooler Pattern.
2. **Pendekatan B:** Edge Runtime menggunakan Drizzle ORM dengan Neon Serverless HTTP Driver.

### Konfigurasi Prisma Singleton (Node.js Serverless Environment)

```typescript
// src/lib/db/prisma.ts
import { PrismaClient } from '@prisma/client';

// Deklarasi namespace global untuk TypeScript guna mencegah re-instansiasi pada Next.js HMR
declare global {
  // eslint-disable-next-line no-var
  var prismaGlobal: PrismaClient | undefined;
}

// Konfigurasi factory client
const createPrismaClient = (): PrismaClient => {
  return new PrismaClient({
    log:
      process.env.NODE_ENV === 'development'
        ? ['query', 'error', 'warn']
        : ['error'],
    datasources: {
      db: {
        // DATABASE_URL harus mengarah ke port PgBouncer (misal: port 6543)
        // Format: postgresql://user:pass@pooler.host:6543/db?pgbouncer=true&connection_limit=5
        url: process.env.DATABASE_URL,
      },
    },
  });
};

// Pola Singleton: Jika prismaGlobal sudah ada (pada memori Node process), gunakan kembali.
// Jika belum, inisialisasi instance baru.
export const db = globalThis.prismaGlobal ?? createPrismaClient();

if (process.env.NODE_ENV !== 'production') {
  globalThis.prismaGlobal = db;
}
```

### Konfigurasi Drizzle + Neon HTTP Driver (Edge Runtime Compatible)

```typescript
// src/lib/db/drizzle-edge.ts
import { neon, neonConfig } from '@neondatabase/serverless';
import { drizzle } from 'drizzle-orm/neon-http';
import * as schema from './schema';

// Optimasi untuk lingkungan serverless Edge: pipelining via sub-request HTTP
neonConfig.fetchConnectionCache = true;

if (!process.env.DATABASE_AUTHENTICATED_URL) {
  throw new Error('DATABASE_AUTHENTICATED_URL environment variable is missing.');
}

// Inisialisasi stateless SQL client via fetch API
const sql = neon(process.env.DATABASE_AUTHENTICATED_URL);

// Inisialisasi instance Drizzle dengan typed schema
export const edgeDb = drizzle(sql, { schema });
```

### Schema Definisi (Drizzle Schema)

```typescript
// src/lib/db/schema.ts
import { pgTable, uuid, varchar, timestamp, text, integer } from 'drizzle-orm/pg-core';

export const organizations = pgTable('organizations', {
  id: uuid('id').defaultRandom().primaryKey(),
  name: varchar('name', { length: 255 }).notNull(),
  slug: varchar('slug', { length: 255 }).notNull().unique(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});

export const auditLogs = pgTable('audit_logs', {
  id: uuid('id').defaultRandom().primaryKey(),
  organizationId: uuid('organization_id')
    .references(() => organizations.id, { onDelete: 'cascade' })
    .notNull(),
  action: varchar('action', { length: 100 }).notNull(),
  payload: text('payload').notNull(),
  executionTimeMs: integer('execution_time_ms').notNull(),
  createdAt: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
});
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `src/lib/db/prisma.ts`

*   **Baris 6–9 (`declare global { var prismaGlobal: ... }`):**
    Di lingkungan development, Next.js membersihkan cache modul Node.js pada setiap perubahan file untuk memfasilitasi Hot Module Replacement (HMR). Jika `new PrismaClient()` dipanggil di lingkup module global tanpa trik ini, setiap kompilasi ulang akan membuat *instance baru* beserta pool koneksi baru. Dalam 10 kali edit kode, terdapat 10 pool aktif yang berjalan paralel, memicu error database `too many connections`. Objek `globalThis` tidak dihapus oleh HMR, menjadikannya tempat penyimpanan memori yang aman.
*   **Baris 19 (`url: process.env.DATABASE_URL`):**
    Perhatikan parameter query `?pgbouncer=true`. Flag ini krusial untuk Prisma saat terhubung ke PgBouncer dalam mode transaksi. Parameter ini menginstruksikan Prisma untuk menonaktifkan *database-level prepared statements*, karena PgBouncer Transaction Mode tidak mendukung statement caching berbasis session ID PostgreSQL.
*   **Baris 24 (`export const db = globalThis.prismaGlobal ?? createPrismaClient();`):**
    Menggunakan operator *nullish coalescing* (`??`). Jika variabel global sudah berisi instance aktif, variabel lokal akan merujuk ke pointer memori yang sama.
*   **Baris 26–28 (`if (process.env.NODE_ENV !== 'production') ...`):**
    Di production (misal AWS Lambda), setiap container mengeksekusi proses yang terisolasi secara fisik. Modul global tidak boleh bocor lintas siklus hidup container yang tidak terkontrol, sehingga reassignment ke global hanya dilakukan pada environment development.

### Analisis File `src/lib/db/drizzle-edge.ts`

*   **Baris 1 (`import { neon, neonConfig } ...`):**
    Mengimpor driver resmi Neon. Tidak ada dependensi terhadap library native OS C++ atau Node.js core module (`net`, `crypto`). Driver ini murni menggunakan Web Standard `fetch` API.
*   **Baris 7 (`neonConfig.fetchConnectionCache = true;`):**
    Menginstruksikan Neon engine untuk melakukan cache terhadap koneksi HTTP keep-alive header selama eksekusi sub-request yang berlangsung berdekatan. Ini mengurangi overhead negosiasi TLS saat menjalankan batch query independen.
*   **Baris 14 (`const sql = neon(...)`):**
    Fungsi `neon` mengembalikan execution function yang menerima string template SQL berparameter dan mengirimkannya sebagai payload JSON melalui POST request ke endpoint gateway Neon.
*   **Baris 17 (`export const edgeDb = drizzle(sql, { schema });`):**
    Membungkus klien stateless Neon ke dalam abstraksi Drizzle ORM lengkap dengan schema introspection untuk *end-to-end type safety*.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Platform E-Commerce Flash Sale Skala Global

**Konteks Klien:** Sebuah platform e-commerce multi-region ("MegaRetail") mengalami lonjakan traffic masif saat kampanye Flash Sale tahunan. Traffic melonjak dari rata-rata 500 RPS menjadi **45.000 RPS** dalam rentang waktu 3 menit.

**Permasalahan Sistem Awal (Failure State):**
1. Aplikasi Next.js di-deploy ke Vercel Serverless Functions.
2. Setiap kali user membuka landing page Flash Sale, Server Component memanggil `prisma.product.findUnique()` langsung ke AWS RDS PostgreSQL db.m5.large (max connections = 380).
3. Dalam 30 detik pertama: Vercel melakukan auto-scaling instan hingga 1.200 Serverless Functions.
4. Total percobaan koneksi TCP ke PostgreSQL mencapai 1.200 x 5 = **6.000 koneksi**.
5. Database RDS mengalami CPU spikes hingga 100%, konsumsi memori melampaui swap space, dan PostgreSQL mengalami panic restart.
6. Error rate aplikasi: **99.4% HTTP 500 Internal Server Error**. Kerugian estimasi: \$250.000 dalam 15 menit downtime.

**Kebutuhan Solusi Arsitektural:**
* **Beban Read:** 95% traffic adalah read-only (melihat katalog produk, harga, dan ketersediaan sisa stok). Data ini harus dipindahkan ke Global Edge Key-Value Store (Upstash Redis) dengan latensi <15ms.
* **Beban Write:** 5% traffic adalah transaksi pemesanan (checkout/reservasi kuota stok). Akses write harus dialirkan melalui Transaction Connection Pooler terdedikasi dengan locking mekanisme atomik (optimistic concurrency).
* **Zero Infrastructure Crash:** Database RDS PostgreSQL tidak boleh menerima lebih dari **80 koneksi TCP simultan**, terlepas dari seberapa masif Serverless Functions melakukan scale out.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem berstandar produksi yang mencakup:
1. **Edge-layer Upstash Redis Caching Client**.
2. **Server Action Transaksional Kuat** dengan Prisma + PgBouncer.
3. **Edge Route Handler** untuk menyajikan data dengan latensi sangat rendah.

### Struktur Direktori:
```text
src/
├── app/
│   ├── api/
│   │   └── flash-sale/
│   │       └── [productId]/
│   │           └── route.ts        # Edge Runtime Route Handler
│   └── actions/
│       └── checkout.ts             # Node.js Server Action
├── lib/
│   ├── db/
│   │   ├── prisma.ts               # Transaction Pooler Singleton
│   │   └── redis.ts                # Edge Redis Client
│   └── errors/
│       └── app-error.ts
```

### 1. Inisialisasi Upstash Redis (Edge Compatible)

```typescript
// src/lib/db/redis.ts
import { Redis } from '@upstash/redis';

if (!process.env.UPSTASH_REDIS_REST_URL || !process.env.UPSTASH_REDIS_REST_TOKEN) {
  throw new Error('Upstash Redis credentials are not defined in environment variables.');
}

// Client ini beroperasi di atas HTTP/REST API, 100% kompatibel dengan V8 Edge Isolates
export const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL,
  token: process.env.UPSTASH_REDIS_REST_TOKEN,
});
```

### 2. Edge Route Handler: High-Performance Read-Through Cache

```typescript
// src/app/api/flash-sale/[productId]/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { redis } from '@/lib/db/redis';
import { edgeDb } from '@/lib/db/drizzle-edge';
import { sql } from 'drizzle-orm';

// Menetapkan runtime ke Edge Isolate
export const runtime = 'edge';
export const dynamic = 'force-dynamic';

interface ProductCachePayload {
  id: string;
  name: string;
  price: number;
  stock: number;
  cachedAt: number;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ productId: string }> }
) {
  const startTime = Date.now();
  const { productId } = await params;

  if (!productId || productId.length > 64) {
    return NextResponse.json(
      { error: 'Invalid product identifier' },
      { status: 400 }
    );
  }

  const cacheKey = `cache:product:${productId}`;

  try {
    // 1. Cek Edge In-Memory Cache (Latency: 5-15ms)
    const cachedData = await redis.get<ProductCachePayload>(cacheKey);

    if (cachedData) {
      return NextResponse.json(
        {
          data: cachedData,
          source: 'edge-cache',
          latencyMs: Date.now() - startTime,
        },
        {
          status: 200,
          headers: {
            'X-Cache-Lookup': 'HIT',
            'Cache-Control': 'public, s-maxage=5, stale-while-revalidate=10',
          },
        }
      );
    }

    // 2. Cache Miss: Fallback ke Stateless Neon HTTP Query (Latency: 60-120ms)
    const queryResult = await edgeDb.execute(
      sql`SELECT id, name, price, stock FROM products WHERE id = ${productId} LIMIT 1;`
    );

    const product = queryResult.rows[0] as unknown as ProductCachePayload | undefined;

    if (!product) {
      return NextResponse.json(
        { error: 'Product not found' },
        { status: 404 }
      );
    }

    const payload: ProductCachePayload = {
      id: product.id,
      name: product.name,
      price: Number(product.price),
      stock: Number(product.stock),
      cachedAt: Date.now(),
    };

    // 3. Tuliskan kembali ke Edge Redis dengan TTL 10 detik (Write-Through Cache)
    await redis.set(cacheKey, payload, { ex: 10 });

    return NextResponse.json(
      {
        data: payload,
        source: 'database-fallback',
        latencyMs: Date.now() - startTime,
      },
      {
        status: 200,
        headers: {
          'X-Cache-Lookup': 'MISS',
        },
      }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { error: 'Internal Data Fetch Error', details: message },
      { status: 500 }
    );
  }
}
```

### 3. Server Action Transaksional: Resilient Checkout & Invalidation

```typescript
// src/app/actions/checkout.ts
'use server';

import { db } from '@/lib/db/prisma';
import { redis } from '@/lib/db/redis';
import { revalidatePath } from 'next/cache';

interface CheckoutResult {
  success: boolean;
  orderId?: string;
  error?: string;
}

export async function processCheckout(
  productId: string,
  userId: string,
  quantity: number = 1
): Promise<CheckoutResult> {
  // Validasi Input
  if (!productId || !userId || quantity <= 0) {
    return { success: false, error: 'Invalid checkout parameters.' };
  }

  try {
    // Jalankan transaksi database ACID melalui PgBouncer Transaction Pool
    const transactionResult = await db.$transaction(
      async (tx) => {
        // 1. Dapatkan stok terkini dengan row-level lock (SELECT FOR UPDATE)
        // Mencegah Race Condition (Double Spending Stok)
        const products = await tx.$queryRaw<Array<{ id: string; stock: number; price: number }>>`
          SELECT id, stock, price FROM "products" 
          WHERE id = ${productId} 
          FOR UPDATE;
        `;

        const targetProduct = products[0];

        if (!targetProduct) {
          throw new Error('PRODUCT_NOT_FOUND');
        }

        if (targetProduct.stock < quantity) {
          throw new Error('INSUFFICIENT_STOCK');
        }

        // 2. Dekremen stok
        await tx.$executeRaw`
          UPDATE "products" 
          SET stock = stock - ${quantity}, "updatedAt" = NOW() 
          WHERE id = ${productId};
        `;

        // 3. Buat order record
        const totalAmount = targetProduct.price * quantity;
        const createdOrders = await tx.$queryRaw<Array<{ id: string }>>`
          INSERT INTO "orders" ("id", "userId", "productId", "quantity", "totalAmount", "status", "createdAt")
          VALUES (gen_random_uuid(), ${userId}, ${productId}, ${quantity}, ${totalAmount}, 'PAID', NOW())
          RETURNING id;
        `;

        return createdOrders[0];
      },
      {
        maxWait: 5000, // Maksimal waktu menunggu koneksi dari pool (5 detik)
        timeout: 7000, // Maksimal durasi eksekusi transaksi (7 detik)
      }
    );

    // Invalidation Fase: Bersihkan Cache di Edge secara Paralel
    const cacheKey = `cache:product:${productId}`;
    await Promise.all([
      redis.del(cacheKey),
      // Update data di cache secara optimistik (opsional, atau biarkan diisi via Next Read Miss)
    ]);

    // Revalidasi ISR Cache Next.js
    revalidatePath(`/products/${productId}`);

    return {
      success: true,
      orderId: transactionResult.id,
    };
  } catch (error) {
    if (error instanceof Error) {
      if (error.message === 'INSUFFICIENT_STOCK') {
        return { success: false, error: 'Flash sale item is completely sold out.' };
      }
      if (error.message === 'PRODUCT_NOT_FOUND') {
        return { success: false, error: 'Product does not exist.' };
      }
    }

    // Logging internal telemetry (Sentry / Datadog)
    console.error('[CRITICAL] Transaction Failure in processCheckout:', error);

    return {
      success: false,
      error: 'Transaction failed due to high concurrency load. Please retry.',
    };
  }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Direct TCP (Node Runtime) | PgBouncer/Pooler Middleware | Neon HTTP Stateless | Upstash Redis Edge |
| :--- | :--- | :--- | :--- | :--- |
| **Batas Maksimal Koneksi** | Sangat Rendah (~100 - 300) | Sangat Tinggi (~10.000+) | Tak Terbatas (Stateless) | Sangat Tinggi (HTTP REST) |
| **Latensi Query Baseline** | **Terendah (<1ms pada LAN)** | Rendah (~1.5ms) | Sedang (~20-40ms HTTP) | **Ekstrem Cepat (2-10ms)** |
| **Kompatibilitas Fitur SQL** | Penuh (100%) | Terbatas (No Session State) | Penuh (Kecuali Session persistent) | N/A (Key-Value Engine) |
| **Cold Start Latency** | Tinggi (TCP & Handshake) | Sedang (Pooled TCP) | **Sangat Rendah** | **Sangat Rendah** |
| **Prepared Statements Support**| Didukung Penuh | Wajib Dimatikan/Deallocated | Didukung via Parameterization | Tidak Tersedia |
| **Biaya Operasional** | Murah (Direct ke VM) | Menengah (Perlu Node Proxy) | Pay-per-Request / SaaS | Pay-per-Request / SaaS |

### Analisis Pengambilan Keputusan:
1. **Pilih Direct TCP:** Hanya jika aplikasi di-deploy pada dedicated infrastructure berumur panjang (Kubernetes Cluster, AWS ECS, Railway Container) di mana jumlah proses server terkontrol ketat.
2. **Pilih PgBouncer (Transaction Mode):** Solusi wajib jika Anda menggunakan ORM berat (seperti Prisma) di dalam Vercel Serverless Function standar yang membutuhkan transaksi multi-step kompleks (`$transaction`).
3. **Pilih HTTP Stateless Driver:** Solusi ideal jika Anda menulis logic di Next.js **Edge Runtime** (`export const runtime = 'edge'`) yang memerlukan pembacaan/penulisan langsung ke SQL tanpa dependensi runtime Node.js.
4. **Pilih Edge KV Store:** Wajib digunakan sebagai lapisan caching read-heavy terdepan untuk data yang diakses massal guna melindungi core relasional database dari beban berlebih.

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Prepared Statement Collision Problem
* **Kondisi:** Saat PgBouncer diatur ke `pool_mode = transaction`, dua query terpisah dari instance serverless berbeda dapat dialokasikan ke koneksi PostgreSQL fisik backend yang sama secara bergantian.
* **Gejala:** Driver mencoba mendaftarkan prepared statement dengan nama default (`s0`, `s1`). Klien kedua akan gagal dengan error fatal: `ERROR: prepared statement "s0" already exists`.
* **Mitigasi:**
  * Pada Prisma: Wajib menambahkan `?pgbouncer=true` pada connection string URL. Ini memaksa Prisma menggunakan *unprepared queries*.
  * Pada Drizzle: Jangan gunakan `db.prepare()` jika ter