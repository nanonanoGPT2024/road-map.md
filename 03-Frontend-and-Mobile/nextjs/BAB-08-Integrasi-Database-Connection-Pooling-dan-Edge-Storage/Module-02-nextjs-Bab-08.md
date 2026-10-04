# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Integrasi Database, Connection Pooling, dan Edge Storage**
**Kategori: 03-Frontend-and-Mobile (Next.js)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Mendiagnosis dan Mengeliminasi Bottleneck Koneksi Database**: Mengidentifikasi kegagalan koneksi (*connection exhaustion*) pada arsitektur *ephemeral serverless* dan *edge runtime* Next.js App Router melalui perhitungan konkurensi matematis.
- **Mengarsitekturi Pola Data Hybrid (Edge + Node.js Runtime)**: Mengimplementasikan pemisahan runtime secara presisi—mengalokasikan pembacaan data berlatensi rendah ke *Edge Storage* (HTTP-based/KV) dan mutasi ACID ke *Regional Node.js Runtime* dengan koneksi terkelola.
- **Mengonfigurasi Connection Pooling Tingkat Lanjut**: Mengintegrasikan PgBouncer, AWS RDS Proxy, atau Prisma Accelerate/Neon Serverless Driver dengan konfigurasi *transaction-level pooling* dan mitigasi isu *prepared statements*.
- **Membangun Resilient Data Access Layer**: Mengembangkan *production-ready data access layer* pada Next.js yang mengimplementasikan *singleton pattern*, *connection lifecycle management*, *circuit breaker*, dan *distributed caching*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Next.js App Router Internals**: Memahami perbedaan eksekusi antara *Edge Runtime* (V8 isolate berbasis Web Standards) dan *Node.js Runtime*, serta siklus hidup Server Components, Server Actions, dan Route Handlers.
- **PostgreSQL Core Mechanics**: Pemahaman mendalam tentang *process-per-connection architecture*, konsumsi memori backend Postgres (`work_mem`, `shared_buffers`), dan mekanisme *locking*.
- **Protokol Jaringan**: Pemahaman tentang TCP 3-way handshake, TLS termination overhead, serta perbedaan antara stateful TCP sockets dan stateless HTTP/WebSocket tunneling.
- **TypeScript**: Mahir dalam typing tingkat lanjut, generics, dan asynchronous design patterns.

---

## 3. Concept & Internal Architecture

### Anatomi Masalah: "Process-per-Connection" vs "Ephemeral Compute"

PostgreSQL mengadopsi model konkurensi berbasis proses (*process-based concurrency model*). Setiap kali klien menginisiasi koneksi TCP ke PostgreSQL, postmaster utama melakukan `fork()` terhadap proses backend baru (`postgres`). Setiap proses ini mengalokasikan memori privat (`work_mem`, koneksi state, stack) yang biasanya berkisar antara 2 MB hingga 10 MB per koneksi sebelum mengeksekusi query.

```
PostgreSQL Server (max_connections = 100)
├── Postmaster (Port 5432)
│   ├── Fork: Backend Process [PID 1021] -> Client A (Memory ~5MB)
│   ├── Fork: Backend Process [PID 1022] -> Client B (Memory ~5MB)
│   └── Fork: Backend Process [PID 1023] -> Client C (Memory ~5MB)
└── Shared Memory (shared_buffers, WAL buffers, lock tables)
```

Pada server monolitik tradisional (misal Express.js pada instans EC2), satu proses Node.js mempertahankan *in-memory connection pool* (misal 10-20 koneksi TCP persisten) yang digunakan secara bergantian oleh ribuan request HTTP:

$$\text{Total DB Connections} = \text{Total Node.js Instances} \times \text{Pool Size}$$

Sebaliknya, pada Next.js yang di-deploy ke lingkungan *serverless* (Vercel, AWS Lambda, GCP Cloud Run scale-to-zero), model komputasinya bersifat *ephemeral*:
1. Lonjakan trafik (misal: flash sale) memicu *auto-scaling* dari 0 menjadi 500 fungsi secara instan.
2. Jika setiap instans fungsi menginisiasi koneksi database langsung menggunakan ORM/Driver konvensional dengan *pool size* default (misal 10 koneksi):
   $$500 \text{ instans} \times 10 \text{ koneksi} = 5.000 \text{ koneksi ke DB}$$
3. Hasil: PostgreSQL mengalami crash seketika akibat *connection exhaustion* (`FATAL: remaining connection slots are reserved for non-replicated superuser connections`) atau kehabisan RAM akibat OOM Killer OS.

```
Traffic Spike (Serverless Next.js)
  │
  ├── Lambda/Isolate 1  ──(10 TCP Conns)──┐
  ├── Lambda/Isolate 2  ──(10 TCP Conns)──┤
  ├── Lambda/Isolate ...──(10 TCP Conns)──┼──> PostgreSQL Server (max_connections = 200)
  └── Lambda/Isolate 500──(10 TCP Conns)──┘    [💥 FATAL: out of connection slots]
```

### TCP Handshake Overhead & Cold Starts

Membuat koneksi TCP baru membutuhkan round-trip latency signifikan:
1. TCP 3-way handshake: `SYN` $\to$ `SYN-ACK` $\to$ `ACK` (1 RTT).
2. TLS Negotiation: TLS 1.3 membutuhkan minimal 1 RTT tambahan.
3. PostgreSQL Startup Packet: Autentikasi (SCRAM-SHA-256 / MD5), parameter negotiation, backend spin-up (1-2 RTT).

Jika latensi jaringan antara Serverless Worker dan Database adalah 30ms, *overhead* murni untuk membuka koneksi sebelum menjalankan *single query* adalah:
$$\text{Latency Overhead} = (1 + 1 + 2) \times 30\text{ms} = 120\text{ms}$$

### Edge Runtime vs Node.js Runtime

Next.js mengizinkan pemilihan runtime per segmen file via `export const runtime = 'edge' | 'nodejs'`.

| Parameter | Node.js Runtime | Edge Runtime |
| :--- | :--- | :--- |
| **Arsitektur Underlying** | Full Node.js environment (v18/v20/v22) | V8 Isolates (mirip Cloudflare Workers) |
| **Sistem I/O Socket** | Raw TCP / POSIX Sockets (`net`, `tls`) | Standard Web APIs (`fetch`, limited TCP via `connect` standard) |
| **Dukungan Driver DB** | Seluruh driver konvensional (`pg`, `mysql2`, Prisma Engine C++) | Driver berbasis HTTP/WebSocket atau Wasm runtime |
| **Cold Start Time** | Sedang - Tinggi (150ms - 1500ms) | Ultra-rendah (0ms - 50ms) |
| **Ideal Use Case** | Transactional mutations, complex business logic, ACID | Auth gating, A/B testing, edge data reading (KV, Cache) |

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Lingkungan Modern?
1. **Kegagalan Pooling Lokal**: In-memory connection pool pada driver seperti `pg` atau `mysql2` berasumsi bahwa lifecycle aplikasi berjalan tanpa batas (*indefinite runtime*). Pada Serverless, fungsi dibekukan (*frozen*) atau dihancurkan (*destroyed*) setelah beberapa detik idle, membuat pool lokal tidak berguna dan justru meninggalkan *zombie connections* di server database.
2. **Keterbatasan Port & Socket Exhaustion**: Di sisi database server, konkurensi koneksi yang terlalu tinggi menghabiskan *file descriptors* pada kernel Linux.

### Solusi Arsitektur
1. **External Pooling Tier (PgBouncer / AWS RDS Proxy)**: Menempatkan middleware proxy stateful di depan database yang memisahkan koneksi klien dari koneksi server fisik (*multiplexing*).
2. **HTTP/WebSocket Database Tunneling (Neon / Supabase / Prisma Accelerate)**: Mengubah transaksi database dari TCP murni menjadi panggilan HTTP/WebSocket yang kompatibel dengan Edge Runtime.
3. **Edge Key-Value / In-Memory Storage (Upstash Redis, Vercel Edge Config)**: Memisahkan beban *read-heavy low-latency* dari relational DB utama, mengeksekusi operasi baca di jaringan Edge sedekat mungkin dengan pengguna (<10ms).

---

## 5. How (Workflow Detail)

Alur kerja arsitektur produksi modern memadukan Edge Runtime dan Node.js Runtime:

```
[ Klien / Browser ]
        │
        ├── (1) GET /api/v1/product/catalog (Edge Route Handler)
        │         │
        │         ▼
        │   [ Edge Runtime (V8 Isolate) ]
        │         │
        │         ├──(2) HTTP REST / Redis Pipeline ──────────────┐
        │         │                                               ▼
        │         │                                     [ Upstash Redis Global ]
        │         │                                     (Sub-millisecond Read)
        │         ▼
        │     Response (Edge Cache Hit)
        │
        └── (3) POST /api/v1/checkout (Server Action - Mutation)
                  │
                  ▼
            [ Node.js Runtime (Regional Lambda) ]
                  │
                  ├──(4) Session / App Level Singleton Check
                  │
                  ├──(5) Stateful TCP / TLS Connection ──────────┐
                  │                                               ▼
                  │                                     [ Connection Pooler ]
                  │                                     (PgBouncer / RDS Proxy)
                  │                                     Mode: Transaction
                  │                                               │
                  │                                               ├──(6) Multiplexed
                  │                                               │   Shared Conns
                  │                                               ▼
                  │                                     [ Aurora PostgreSQL ]
                  │                                     (ACID Strict Isolation)
                  │                                               │
                  ├──(7) Invalidate Edge Cache Key ───────────────┘
                  │
                  ▼
              Response
```

1. **Read Path**: Request diarahkan ke Edge Route Handler. Handler memanggil Upstash Redis melalui REST protocol (kompatibel dengan Edge Runtime) tanpa overhead TCP handshake manual. Data disajikan langsung dari edge node terdekat.
2. **Write Path**: Mutasi dialokasikan ke Node.js Runtime menggunakan Server Action. Handler mengeksekusi query melalui singleton ORM client menuju PgBouncer / RDS Proxy yang dikonfigurasi dalam mode *Transaction Pooling*.
3. **Cache Eviction Path**: Setelah transaksi database berhasil, Server Action mengeksekusi invalidasi cache pada layer Edge Storage menggunakan REST endpoint Redis.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem

Bayangkan sebuah **Restoran Mewah (Database Server)** dengan **10 Meja VIP (Maksimum Koneksi Database = 10)**.

- **Monolitik Tradisional**: Restoran mempekerjakan 2 orang pelayan tetap (*Node.js Instances*). Masing-masing pelayan memesan 5 meja VIP untuk grup tamunya secara terus-menerus (*Persistent Connection Pool*). Meja selalu terpakai secara efisien.
- **Serverless Tanpa Pooler**: 200 orang kurir makanan (*Serverless Functions*) datang serentak. Masing-masing menuntut untuk duduk di 1 meja VIP hanya untuk mengambil 1 bungkus sambal. Restoran kolaps seketika karena kehabisan meja; 190 kurir tertahan di luar, dan dapur meledak karena overhead staf penyambut tamu.
- **Serverless Dengan PgBouncer (Pooler)**: Sebuah loket kurir khusus dipasang di gerbang depan (*PgBouncer*). 200 kurir hanya berhubungan dengan loket tersebut. Loket dilayani oleh 5 staf internal yang secara efisien masuk ke dapur, mengambil pesanan, dan memberikannya ke kurir. Meja VIP restoran tetap aman dan tidak pernah kelebihan kapasitas.

### Diagram Arsitektur Pooling Mode

```
               [ NEXT.JS SERVERLESS INSTANCES ]
   Inst 1          Inst 2          Inst 3          Inst N (Scale-out)
  (Node.js)       (Node.js)       (Node.js)       (Node.js)
     │               │               │               │
     └───────┬───────┴───────┬───────┴───────────────┘
             │ (Ratusan koneksi TCP klien yang hidup-mati cepat)
             ▼
     ┌───────────────────────────────────────────────┐
     │           PGBOUNCER (TRANSACTION POOL)        │
     │  - Menerima 1.000+ incoming client sockets    │
     │  - Mengantrekan (queue) query saat pool penuh │
     │  - Mempertahankan persisten server pool       │
     └───────────────────────┬───────────────────────┘
                             │ (Hanya 20 koneksi TCP persisten)
                             ▼
     ┌───────────────────────────────────────────────┐
     │             POSTGRESQL INSTANCE               │
     │  - Dedicated backend processes terjaga        │
     │  - work_mem terisolasi, CPU terkontrol        │
     └───────────────────────────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### Simple Example: Prisma Global Singleton Pattern

Masalah krusial pada Next.js development mode (dengan Fast Refresh) adalah file dieksekusi ulang secara berkala. Tanpa singleton yang tepat, setiap hot-reload membuat instance `PrismaClient` baru, menghabiskan alokasi koneksi database lokal dalam hitungan menit.

```typescript
// lib/prisma.ts
import { PrismaClient } from '@prisma/client';

// Mendeklarasikan tipe untuk globalThis agar type-safe
declare global {
  // eslint-disable-next-line no-var
  var prismaGlobal: PrismaClient | undefined;
}

// Factory function untuk inisialisasi Prisma Client dengan logging adaptif
const prismaClientSingleton = (): PrismaClient => {
  return new PrismaClient({
    log:
      process.env.NODE_ENV === 'development'
        ? ['query', 'error', 'warn']
        : ['error'],
    datasources: {
      db: {
        // Menggunakan pooling URL (contoh: port 6543 untuk PgBouncer / Transaction pool)
        url: process.env.DATABASE_URL,
      },
    },
  });
};

// Menggunakan globalThis untuk mempertahankan instance selama hot-reload pada development
export const prisma = globalThis.prismaGlobal ?? prismaClientSingleton();

if (process.env.NODE_ENV !== 'production') {
  globalThis.prismaGlobal = prisma;
}
```

### Practical Example: Dual-Layer Edge Read & Node.js Write Architecture

Berikut implementasi sistem inventaris inventif berskala enterprise:
1. **Edge Route Handler** menggunakan Upstash Redis REST API untuk pembacaan stok berlatensi rendah (<10ms).
2. **Server Action** menggunakan PostgreSQL via PgBouncer dengan proteksi transaksi ACID dan cache invalidation seketika.

#### 1. Setup Environment Variables
```env
# URL PgBouncer (Port 6543) dengan flag pgbouncer=true & batas koneksi per Lambda instance diatur ke 1
DATABASE_URL="postgres://app_user:strong_password@pgbouncer.internal:6543/production_db?sslmode=require&pgbouncer=true&connection_limit=1"

# Upstash REST credentials (Edge Runtime compatible)
UPSTASH_REDIS_REST_URL="https://ap1-reliable-civet-12345.upstash.io"
UPSTASH_REDIS_REST_TOKEN="AcXXASQgZmQ3...Mzg1M2E="
```

#### 2. Edge Cache Layer Client
```typescript
// lib/edge-redis.ts
import { Redis } from '@upstash/redis';

if (!process.env.UPSTASH_REDIS_REST_URL || !process.env.UPSTASH_REDIS_REST_TOKEN) {
  throw new Error('Missing Upstash Redis environment variables');
}

// Client ini berjalan menggunakan native Web fetch() API, kompatibel dengan Edge Runtime
export const edgeRedis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL,
  token: process.env.UPSTASH_REDIS_REST_TOKEN,
});
```

#### 3. Edge Route Handler: High-Performance Read
```typescript
// app/api/products/[id]/stock/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { edgeRedis } from '@/lib/edge-redis';

// Mewajibkan route ini dieksekusi di Edge Runtime
export const runtime = 'edge';
export const dynamic = 'force-dynamic';

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(
  request: NextRequest,
  context: RouteContext
): Promise<NextResponse> {
  const { id: productId } = await context.params;

  if (!productId || typeof productId !== 'string') {
    return NextResponse.json(
      { error: 'Invalid or missing product ID' },
      { status: 400 }
    );
  }

  try {
    const cacheKey = `product:${productId}:stock`;
    
    // Pembacaan ultra-cepat via Redis REST di Edge
    const stock = await edgeRedis.get<number>(cacheKey);

    if (stock === null) {
      return NextResponse.json(
        { error: 'Product stock not found or cache miss' },
        { status: 404 }
      );
    }

    return NextResponse.json(
      { productId, stock, source: 'edge-cache' },
      {
        status: 200,
        headers: {
          'Cache-Control': 'public, s-maxage=5, stale-while-revalidate=10',
        },
      }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { error: 'Failed to retrieve stock from Edge Cache', details: message },
      { status: 500 }
    );
  }
}
```

#### 4. Server Action: ACID Mutation dengan Invalidation
```typescript
// app/actions/inventory.ts
'use server';

import { prisma } from '@/lib/prisma';
import { edgeRedis } from '@/lib/edge-redis';
import { revalidateTag } from 'next/cache';

interface ReservationResult {
  success: boolean;
  remainingStock?: number;
  error?: string;
}

export async function reserveStock(
  productId: string,
  quantityToReserve: number
): Promise<ReservationResult> {
  // Input validation
  if (!productId || quantityToReserve <= 0) {
    return { success: false, error: 'Invalid parameters for reservation' };
  }

  try {
    // Eksekusi mutasi dengan isolasi transaksi di PostgreSQL
    const updatedProduct = await prisma.$transaction(async (tx) => {
      // 1. Dapatkan stok saat ini dengan locking row eksplisit menggunakan raw query
      // Catatan: Penting saat persaingan tinggi untuk menghindari race condition (Phantom Read / Lost Update)
      const rows = await tx.$queryRaw<Array<{ id: string; stock: number }>>`
        SELECT id, stock 
        FROM "Product" 
        WHERE id = ${productId} 
        FOR UPDATE
      `;

      const product = rows[0];

      if (!product) {
        throw new Error('ERR_PRODUCT_NOT_FOUND');
      }

      if (product.stock < quantityToReserve) {
        throw new Error('ERR_INSUFFICIENT_STOCK');
      }

      // 2. Lakukan pengurangan stok
      const updated = await tx.product.update({
        where: { id: productId },
        data: {
          stock: {
            decrement: quantityToReserve,
          },
        },
        select: {
          id: true,
          stock: true,
        },
      });

      // 3. Catat history reservasi dalam transaksi yang sama
      await tx.stockAuditLog.create({
        data: {
          productId,
          change: -quantityToReserve,
          reason: 'RESERVATION',
        },
      });

      return updated;
    });

    // 4. Update/Sinkronisasi Edge Cache secara Atomik setelah transaksi DB sukses
    const cacheKey = `product:${productId}:stock`;
    await edgeRedis.set(cacheKey, updatedProduct.stock);

    // 5. Invalidate Next.js Data Cache Layer
    revalidateTag(`product-stock-${productId}`);

    return {
      success: true,
      remainingStock: updatedProduct.stock,
    };
  } catch (error) {
    if (error instanceof Error) {
      if (error.message === 'ERR_INSUFFICIENT_STOCK') {
        return { success: false, error: 'Stock insufficient to fulfill request' };
      }
      if (error.message === 'ERR_PRODUCT_NOT_FOUND') {
        return { success: false, error: 'Product does not exist' };
      }
    }

    console.error('Database transaction failure during reserveStock:', error);
    return {
      success: false,
      error: 'Internal database processing failure during reservation',
    };
  }
}
```

---

## 8. Real World Case Study: E-Commerce Flash Sale Architecture

### Konteks Bisnis
Sebuah platform flash sale berskala nasional mengalami lonjakan trafik dari 200 RPS menjadi 45.000 RPS dalam 3 detik ketika penjualan produk eksklusif dimulai.

### Masalah Arsitektur Awal
1. **Spesifikasi Database**: AWS RDS PostgreSQL `db.r6g.2xlarge` (8 vCPU, 64 GB RAM, `max_connections = 2000`).
2. **Implementasi Next.js**: Dideploy ke Vercel Serverless Functions. Setiap fungsi menggunakan Prisma Client langsung ke port 5432 DB tanpa pooler eksternal. Default Prisma connection pool dialokasikan `num_physical_cpus * 2 + 1`.
3. **Insiden**:
   - Dalam rentang 5 detik sejak flash sale dibuka, Vercel melakukan autoscaling hingga 3.200 fungsi secara serentak.
   - Database menerima $3.200 \times 5 = 16.000$ permintaan inisiasi koneksi TCP.
   - RDS CPU langsung melonjak ke 100% murni karena menangani TLS handshake dan forking OS process.
   - PostgreSQL membeku, memicu status `canceling statement due to statement timeout`, mengakibatkan *Cascading System Failure* dan downtime 42 menit.

```
Insiden:
Next.js Scale-out (3.200 Fns) ──> 16.000 TCP Requests ──> RDS Postgres (Max 2.000)
                                                              │
                                                              ▼
                                                    [🔥 100% CPU Spike]
                                                    [🔥 Connection Spanning Exhausted]
                                                    [💥 Outage 42 Menit]
```

### Solusi Teknis & Arsitektur Baru
Arsitek merombak alur transaksi ke pola **Tri-Tier Data Isolation**:

```
                       [ 45.000 RPS INCOMING ]
                                  │
                                  ▼
                     [ CLOUDFLARE EDGE WORKERS ]
                     - Rate limiting per IP
                     - Bot verification (Turnstile)
                                  │
                                  ▼
               [ NEXT.JS EDGE ROUTE: GET CATALOG/STOCK ]
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
       [ Cache HIT (44.500 RPS) ]      [ Cache MISS (500 RPS) ]
       Upstash Redis Global Clusters   Neon HTTP Proxy (Read Replica)
       Latensi: ~8ms                   Latensi: ~45ms
                                  │
                                  │
                  [ CHECKOUT MUTATION (2.000 RPS) ]
                                  │
                                  ▼
                 [ NEXT.JS REGIONAL NODE.JS RUNTIME ]
                                  │
                                  ▼
                     [ AWS RDS PROXY CLUSTER ]
                   Mode: Transaction Pooling
                   max_connections ke DB: 180 (Fixed)
                                  │
                                  ▼
                 [ AWS RDS POSTGRESQL MULTI-AZ ]
                   CPU stabil di 35%
                   Latensi p99: 18ms
```

### Metrik Hasil Transformasi

| Metrik | Arsitektur Lama | Arsitektur Baru | Peningkatan |
| :--- | :--- | :--- | :--- |
| **Max Concurrency Handled** | 1.800 RPS (Lalu Crash) | 45.000+ RPS | **25x Lipat** |
| **P99 Read Latency** | 480ms | 12ms | **40x Lebih Cepat** |
| **Database Max Connections Active** | 2.000 (Exhausted) | 180 (Terkontrol Ketat) | **91% Reduksi Beban** |
| **Infrastructure Monthly Cost** | $2.850 (Over-provisioned DB) | $890 (Optimized tier) | **68.7% Penghematan** |

---

## 9. Trade-offs: Komparasi Pola Integrasi Database

Dalam menentukan pendekatan integrasi database pada Next.js, setiap arsitektur memiliki kompromi teknis yang signifikan:

```
Direct TCP (Serverless)  ──>  [Kelebihan: Sederhana] ──> [Kekurangan: Crash pada Spikes]
External PgBouncer       ──>  [Kelebihan: Skalabilitas Tinggi] ──> [Kekurangan: Maintenance Ops]
HTTP/Edge Drivers        ──>  [Kelebihan: Zero Cold Start] ──> [Kekurangan: Vendor Lock-in / Fitur Terbatas]
```

| Dimensi Arsitektur | 1. Direct TCP (Node Runtime) | 2. PgBouncer / RDS Proxy | 3. HTTP/WebSocket Driver (Edge) | 4. Edge KV / Distributed Cache |
| :--- | :--- | :--- | :--- | :--- |
| **Latency (Read)** | 25ms - 60ms | 25ms - 50ms | 30ms - 80ms | **1ms - 15ms** |
| **Throughput Mutasi** | Rendah (Tergantung limits) | **Sangat Tinggi** | Sedang - Tinggi | Tidak cocok untuk ACID |
| **Runtime Support** | Node.js Runtime saja | Node.js Runtime saja | **Node.js & Edge Runtime** | **Node.js & Edge Runtime** |
| **Dukungan Prepared Stmts**| Penuh (`PREPARE ...`) | **Terbatas / Rusak** (Tx Mode)| Tergantung implementasi | N/A |
| **Kompleksitas Ops** | Nol | Menengah - Tinggi | Rendah (Managed SaaS) | Rendah (Managed SaaS) |
| **Beban Biaya** | Rendah (Namun DB harus besar)| Biaya Proxy + DB | Pay-per-request | Pay-per-read/write |
| **ACID Guarantees** | Penuh | Penuh | Penuh | Eventual Consistency |

---

## 10. Common Mistakes & Troubleshooting

### 1. Prisma Client Re-Instantiation di Server Actions
* **Kesalahan**: Mengimpor `new PrismaClient()` di dalam handler Server Action atau Route Handler.
* **Dampak**: Setiap eksekusi fungsi membuat connection pool baru. Dalam puluhan request, database kehabisan slot koneksi.
* **Solusi**: Gunakan strictly singleton pattern seperti diuraikan di Bagian 7.

### 2. Prepared Statements Collision pada PgBouncer Transaction Pooling
* **Gejala**: Muncul error dari PostgreSQL: `prepared statement "s0" already exists` atau `prepared statement does not exist`.
* **Akar Masalah**: PgBouncer Transaction Mode mengembalikan koneksi server fisik ke pool segera setelah transaksi selesai. Namun, driver seperti Prisma atau pg-promise menyimpan cache prepared statement pada koneksi tersebut. Klien berikutnya menerima koneksi fisik yang sama dengan state prepared statement yang bertabrakan.
* **Solusi**:
  Tambahkan parameter `pgbouncer=true` pada connection string URL jika menggunakan Prisma, atau set `prepare: false` pada driver pg:
  ```env
  DATABASE_URL="postgresql://user:pass@host:6543/db?pgbouncer=true"
  ```
  Pada konfigurasi `schema.prisma`:
  ```prisma
  datasource db {
    provider  = "postgresql"
    url       = env("DATABASE_URL")
    directUrl = env("DIRECT_URL") // Digunakan murni untuk Prisma Migrations via TCP direct
  }
  ```

### 3. Menggunakan Node Driver di Edge Runtime
* **Gejala**: Muncul build error atau runtime failure:
  `Module not found: Can't resolve 'net'` atau `The edge runtime does not support Node.js 'tls' module`.
* **Akar Masalah**: Mencoba mengeksekusi library TCP native (`pg`, `mysql2`, `@prisma/client` default) di dalam file bertanda `export const runtime = 'edge'`.
* **Solusi**:
  Gunakan driver khusus HTTP/WebSocket, contoh: `@neondatabase/serverless`, `@planetscale/database`, atau `@upstash/redis`.

### 4. Connection Leaks akibat Unhandled Rejections pada Raw Transactions
* **Gejala**: Jumlah koneksi `idle in transaction` di database terus meningkat hingga mencapai limit, meski trafik normal.
* **Akar Masalah**: Menggunakan klien koneksi manual (misal: `const client = await pool.connect()`) tanpa blok `try...finally` yang menjamin pelepasan koneksi (`client.release()`).
* **Solusi**:
  ```typescript
  // SALAH
  const client = await pool.connect();
  const res = await client.query('SELECT * FROM users');
  client.release(); // Terlewati jika query melempar Exception!

  // BENAR
  const client = await pool.connect();
  try {
    const res = await client.query('SELECT * FROM users');
    return res.rows;
  } finally {
    client.release(); // Dijamin selalu dieksekusi
  }
  ```

---

## 11. Best Practices (Production Checklist)

### Pool Sizing & Sizing Formulation
- [ ] Atur batas koneksi lokal serverless fungsi ke **1 atau 2** koneksi per Lambda instance:
  $$\text{Client Connection Limit} = 1$$
- [ ] Hitung kapasitas server database menggunakan formula PostgreSQL:
  $$\text{max\_connections} \le \frac{\text{RAM Bebas} - \text{Shared Buffers}}{\text{work\_mem}} + 15$$
- [ ] Terapkan rumus koneksi PgBouncer ke DB:
  $$\text{Pool Size to Postgres} = (\text{CPU Cores} \times 2) + \text{Disk Spindle Count}$$

### Connection String Separation
- [ ] Sediakan dua connection string di environment variables:
  - `DATABASE_URL`: Mengarah ke Pooler (Port 6543 / Transaction Mode) untuk Runtime Aplikasi.
  - `DIRECT_URL`: Mengarah ke Database Langsung (Port 5432 / Session Mode) untuk Prisma Migrations (`prisma migrate deploy`).

### Network & Security
- [ ] Pastikan pooling tier berada dalam satu VPC/Private Subnet dengan Next.js compute instances (misal: AWS VPC Peering) untuk menekan network latency di bawah 2ms.
- [ ] Wajibkan enforcement `sslmode=require` atau `sslmode=verify-full` pada semua URL koneksi.

### Telemetry & Monitoring
- [ ] Konfigurasi query monitoring menggunakan `pg_stat_activity` alert untuk mendeteksi status `idle in transaction` berdurasi $> 5$ detik.
- [ ] Setup OpenTelemetry / Prisma Tracing untuk memantau waktu akuisisi pool (`prisma.client.connect`).

---

## 12. Hands-on Practice

Implementasikan infrastruktur lokal yang menyimulasikan lingkungan produksi Next.js dengan PgBouncer dan PostgreSQL.

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

### Struktur Direktori Hands-on
```text
hands-on/m02/
├── docker-compose.yml
├── pgbouncer.ini
├── userlist.txt
├── package.json
├── tsconfig.json
├── prisma/
│   └── schema.prisma
├── lib/
│   └── db.ts
└── app/
    └── api/
        └── test-pool/
            └── route.ts
```

### Langkah 1: Siapkan Konfigurasi Docker (PostgreSQL + PgBouncer)

Buat file `hands-on/m02/userlist.txt`:
```text
"postgres" "postgres"
"app_user" "app_password"
```

Buat file `hands-on/m02/pgbouncer.ini`:
```ini
[databases]
app_db = host=postgres port=5432 dbname=app_db auth_user=postgres

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = plain
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 10
min_pool_size = 2
reserve_pool_size = 5
reserve_pool_timeout = 5
max_db_connections = 20
admin_users = postgres
ignore_startup_parameters = extra_float_digits
```

Buat file `hands-on/m02/docker-compose.yml`:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: local-postgres
    environment:
      POSTGRES_DB: app_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend-net

  pgbouncer:
    image: edoburu/pgbouncer:latest
    container_name: local-pgbouncer
    depends_on:
      - postgres
    ports:
      - "6432:6432"
    volumes:
      - ./pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini:ro
      - ./userlist.txt:/etc/pgbouncer/userlist.txt:ro
    networks:
      - backend-net

volumes:
  pgdata:

networks:
  backend-net:
```

Jalankan container:
```bash
docker compose up -d
```

### Langkah 2: Setup Schema Prisma

Buat file `hands-on/m02/prisma/schema.prisma`:
```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")
  directUrl = env("DIRECT_URL")
}

model UserAudit {
  id        String   @id @default(uuid())
  action    String
  timestamp DateTime @default(now())
  metadata  Json?
}
```

Buat file `hands-on/m02/.env`:
```env
# URL PgBouncer untuk transaksi aplikasi (port 6432)
DATABASE_URL="postgresql://postgres:postgres@localhost:6432/app_db?schema=public&pgbouncer=true&connection_limit=1"

# Direct URL untuk menjalankan Prisma Migration (port 5432)
DIRECT_URL="postgresql://postgres:postgres@localhost:5432/app_db?schema=public"
```

Eksekusi migrasi skema:
```bash
npx prisma migrate dev --name init
```

### Langkah 3: Setup Singleton Database Client

Buat file `hands-on/m02/lib/db.ts`:
```typescript
import { PrismaClient } from '@prisma/client';

declare global {
  // eslint-disable-next-line no-var
  var dbSingleton: PrismaClient | undefined;
}

export const db =
  globalThis.dbSingleton ??
  new PrismaClient({
    log: ['error', 'warn'],
  });

if (process.env.NODE_ENV !== 'production') {
  globalThis.dbSingleton = db;
}
```

### Langkah 4: Buat Test Route Handler Beban Tinggi

Buat file `hands-on/m02/app/api/test-pool/route.ts`:
```typescript
import { NextResponse } from 'next/server';
import { db } from '@/lib/db';

export const dynamic = 'force-dynamic';

export async function GET(): Promise<NextResponse> {
  try {
    // Menjalankan write query cepat untuk menguji pool turnover
    const audit = await db.userAudit.create({
      data: {
        action: 'STRESS_TEST_HIT',
        metadata: {
          userAgent: 'AutoTester',
          pid: process.pid,
        },
      },
    });

    return NextResponse.json({ success: true, id: audit.id });
  } catch (error) {
    const errMessage = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ success: false, error: errMessage }, { status: 500 });
  }
}
```

### Langkah 5: Eksekusi Uji Konkurensi

Jalankan server Next.js lokal:
```bash
npm run dev
```

Gunakan terminal terpisah untuk memicu 50 request konkuren menggunakan `curl` dan `xargs`:
```bash
seq 50 | xargs -n1 -P50 curl -s "http://localhost:3000/api/test-pool"
```

Verifikasi status koneksi pada container PgBouncer:
```bash
docker exec -it local-pgbouncer psql -p 6432 -U postgres -d pgbouncer -c "SHOW CLIENTS;"
docker exec -it local-pgbouncer psql -p 6432 -U postgres -d pgbouncer -c "SHOW POOLS;"
```
*Perhatikan bagaimana PgBouncer mengantrekan incoming clients tanpa membanjiri instance PostgreSQL utama.*

---

## 13. Exercise

### Level Easy
1. Modifikasi file `hands-on/m02/lib/db.ts` untuk mengimplementasikan *event logging* Prisma yang mencatat durasi query (`query duration`) ke konsol jika durasi eksekusi melampaui ambang batas 150ms.
2. **Kriteria Penerimaan**:
   - Query yang berjalan normal (<150ms) tidak memicu warning.
   - Query yang lambat memunculkan log format JSON: `{"level":"WARN","duration":210,"query":"..."}`.

### Level Medium
1. Buat Next.js Route Handler dengan runtime Edge (`export const runtime = 'edge'`) pada path `/api/health/db`.
2. Handler harus memverifikasi konektivitas ke Upstash Redis REST interface. Jika latency Redis $>200\text{ms}$ atau gagal, kembalikan status HTTP 503 Service Unavailable beserta informasi metrik latensinya.
3. **Kriteria Penerimaan**:
   - Respon wajib valid secara schema: `{ status: "UP" | "DOWN", latencyMs: number }`.
   - Tidak menggunakan Node.js runtime APIs.

### Level Hard
1. Implementasikan pola **Resilient Distributed Lock** menggunakan Redis REST di dalam Next.js Server Action untuk mencegah *Double Spend* pada saldo dompet pengguna (`UserWallet.balance`).
2. Server Action harus mengunci `userId` spesifik di Redis dengan durasi TTL 3 detik sebelum mengeksekusi mutasi PostgreSQL melalui `db.$transaction`.
3. Jika lock gagal didapatkan dalam 500ms (akibat request ganda paralel dari pengguna yang sama), Server Action harus menolak transaksi dengan respon error spesifik tanpa menyentuh koneksi PostgreSQL.
4. **Kriteria Penerimaan**:
   - Tidak terjadi kondisi balapan (*race condition*) ketika 10 request identik dikirim secara simultan.
   - Lock wajib dilepaskan (*released*) di blok `finally` via script Lua atau token atomic matching untuk mencegah pelepasan lock milik request lain.

---

## 14. Challenge

### Skenario Sistem: "Zero-Downtime Multi-Tenant Connection Router"

Sebuah platform SaaS Enterprise menggunakan model data **Multi-Tenant Hybrid**:
- 10 Enterprise Tenants memiliki Dedicated PostgreSQL Database masing-masing.
- 5.000 SMB Tenants berbagi 1 Shared Database Multi-Tenant.
- Arsitektur aplikasi dideploy sebagai **satu deployment global Next.js** pada Serverless Architecture.

### Tantangan Rekayasa
Rancang dan bangun layer arsitektur `TenantDatabaseManager` dengan batasan berikut:
1. **Dynamic Runtime Routing**: Setiap request incoming membawa JWT yang mengidentifikasi `tenantId`. Server Action harus mengarahkan query ke database yang benar secara dinamis.
2. **Connection Leak Prevention**: Anda dilarang membuka instance `PrismaClient` baru untuk setiap tenant pada setiap request (ini akan memicu instansiasi ratusan pool dan crash).
3. **Strict Memory Cap**: Instance Serverless Lambda memiliki batas RAM ketat 256MB. Jumlah connection pool aktif di dalam memori satu fungsi tidak boleh melampaui batas maksimum 5 pool concurrently.
4. **LRU Cache & Pool Eviction**: Bangun mekanisme eviction berbasis *Least Recently Used (LRU)* di mana pool tenant yang sedang idle ditutup koneksinya (`await client.$disconnect()`) dan dibersihkan dari memori secara graceful saat limit tercapai.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konseptual Dasar (5 Pertanyaan)

1. **Mengapa koneksi database TCP langsung dari ratusan Serverless Instances dapat merusak database PostgreSQL konvensional?**
   - A. Karena PostgreSQL tidak mendukung enkripsi TLS pada arsitektur serverless.
   - B. Karena model konkurensi PostgreSQL berbasis proses (*fork* proses baru per koneksi) yang menghabiskan memori dan slot koneksi dengan cepat.
   - C. Karena serverless functions secara default memblokir port 5432.
   - D. Karena DNS lookup gagal pada lingkungan ephemeral.
   *Jawaban yang benar: B*

2. **Apa fungsi utama dari parameter `pgbouncer=true` pada connection string database Prisma?**
   - A. Mengubah format query dari SQL mentah menjadi NoSQL format.
   - B. Menonaktifkan pembuatan prepared statement internal yang dapat bertabrakan pada Transaction Pooling mode.
   - C. Menginstruksikan Prisma untuk menggunakan protokol HTTP alih-alih TCP.
   - D. Mengaktifkan kompresi data gzip antara Node.js dan database.
   *Jawaban yang benar: B*

3. **Manakah dari pustaka penyimpanan berikut yang dapat diakses langsung dari Next.js Edge Runtime (`runtime = 'edge'`) tanpa bantuan TCP tunneling driver?**
   - A. Standard `pg` (node-postgres) driver.
   - B. `@upstash/redis` via HTTP REST protocol.
   - C. Driver bawaan Oracle DB.
   - D. Native MySQL2 connection pool.
   *Jawaban yang benar: B*

4. **Kapan instance Prisma Client global singleton dievaluasi ulang saat aplikasi di-deploy di lingkungan Vercel Production?**
   - A. Setiap kali ada request HTTP baru yang masuk.
   - B. Tidak pernah dievaluasi ulang selama lifecycle satu execution context/container Lambda yang hangat (*warm container*).
   - C. Setiap 60 detik secara otomatis oleh background thread Next.js.
   - D. Setiap kali file TypeScript di-compile ulang di edge.
   *Jawaban yang benar: B*

5. **Apa mode pooling pada PgBouncer yang paling optimal untuk serverless functions, dan apa konsekuensinya?**
   - A. Session Pooling; koneksi dipertahankan selamanya oleh satu worker.
   - B. Transaction Pooling; statement session-level seperti prepared statements dan `SET search_path` tidak persisten antar transaksi.
   - C. Statement Pooling; transaksi multi-query (`BEGIN...COMMIT`) didukung penuh.
   - D. Direct Mode; PgBouncer mematikan fungsi pooling.
   *Jawaban yang benar: B*

---

### Bagian B: Analisis & Pemecahan Masalah Menengah (5 Pertanyaan)

6. **Sebuah Server Action mengalami error: `Error: write EPIPE` atau `Connection terminated unexpectedly` setelah aplikasi Next.js mengalami idle selama 10 menit. Apa akar penyebab yang paling mungkin?**
   - A. Cache di browser klien telah kedaluwarsa.
   - B. Router NAT atau cloud firewall memutuskan koneksi TCP idle tanpa mengirimkan paket RST, sementara driver client menganggap koneksi masih aktif.
   - C. Server PostgreSQL melakukan restart otomatis setiap 10 menit secara default.
   - D. Environment variables pada Next.js otomatis terhapus saat state idle.
   *Jawaban yang benar: B*

7. **Mengapa pemisahan antara `DATABASE_URL` dan `DIRECT_URL` sangat diwajibkan saat mengintegrasikan Prisma dengan Supabase atau PgBouncer?**
   - A. Untuk memisahkan database staging dan database produksi dalam satu file skema.
   - B. Skrip migrasi skema (`prisma migrate`) memerlukan fitur level sesi seperti advisory locks dan prepared statements yang diblokir oleh Transaction Pooler.
   - C. Supabase memblokir eksekusi query biasa di port 5432.
   - D. Agar data cache dapat disinkronkan secara real-time ke Edge storage.
   *Jawaban yang benar: B*

8. **Perhatikan cuplikan konfigurasi berikut:**
   ```typescript
   export const runtime = 'edge';
   import { Client } from 'pg';
   
   export async function GET() {
     const client = new Client();
     await client.connect();
     return new Response('OK');
   }
   ```
   **Apa yang akan terjadi ketika kode ini di-build atau dieksekusi?**
   - A. Berjalan sukses dengan latensi 5ms karena menggunakan V8 isolate.
   - B. Build/Execution gagal karena paket `pg` membutuhkan modul Node core (`net`, `tls`) yang tidak tersedia di Edge Runtime.
   - C. Otomatis beralih ke Node.js runtime secara implisit.
   - D. PgBouncer akan menolak koneksi karena tidak ada SSL flag.
   *Jawaban yang benar: B*

9. **Pada PostgreSQL, apa dampak dari alokasi parameter `work_mem` yang terlalu tinggi (misal: 256MB per koneksi) di lingkungan dengan traffic lonjakan serverless?**
   - A. Kecepatan query meningkat secara eksponensial tanpa risiko apapun.
   - B. Risiko instan terjadinya OOM (Out of Memory) crash pada level sistem operasi jika banyak koneksi mengeksekusi operasi sorting/hashing simultan.
   - C. PgBouncer otomatis mengubah Transaction mode menjadi Session mode.
   - D. Disk IOPS database turun menjadi 0.
   *Jawaban yang benar: B*

10. **Bagaimana cara mencegah race condition (*phantom read* atau *lost update*) saat dua Server Action berjalan bersamaan untuk mengurangi saldo stok barang yang sama?**
    - A. Membaca data dengan isolasi non-blocking `SELECT ...` biasa.
    - B. Membungkus query dalam `$transaction` dan menambahkan klausa locking eksplisit `FOR UPDATE` pada statement query baris yang dibaca.
    - C. Mengandalkan `revalidatePath` di sisi Next.js framework.
    - D. Menambahkan sleep delay `setTimeout` sebelum mengeksekusi update.
    *Jawaban yang benar: B*

---

### Bagian C: Skenario Kasus Produksi Nyata (3 Pertanyaan)

#### Skenario 1: The Cascading Timeout Outage
Aplikasi Next.js pada klaster Kubernetes mengalami degradasi performa: Route Handler API pembayaran mulai menghasilkan respon `504 Gateway Timeout`. Log aplikasi menunjukkan bahwa ribuan panggilan ke database tertahan pada status:
`PrismaClientInitializationError: Timed out fetching a new connection from the pool. (Current connection limit: 5, pending requests: 254)`.
Database CPU utilisasi berada di angka 8%, dan database memiliki ratusan slot koneksi bebas yang belum terpakai.

11. **Berdasarkan data teknis di atas, apa penyebab utama kegagalan dan langkah mitigasi paling tepat?**
    - A. Database kehabisan memory; tingkatkan RAM server PostgreSQL utama.
    - B. Kapasitas pool lokal instance aplikasi (`connection_limit`) diatur terlalu kecil (hanya 5) relatif terhadap beban konkurensi request per Pod Node.js, sehingga request mengantre di memori lokal aplikasi sebelum mencapai jaringan database.
    - C. Kubernetes Service mesh memblokir semua trafik TCP keluar.
    - D. PgBouncer menolak koneksi karena userlist.txt korup.
    *Jawaban yang benar: B*
    *Rasional Analisis: Database CPU sangat rendah (8%) dan masih memiliki slot bebas, membuktikan bahwa PostgreSQL tidak sedang kelebihan beban. Error message menyatakan antrean pending terjadi di pool internal klien (`pending requests: 254` pada limit lokal `5`). Peningkatan `connection_limit` per pod yang proporsional dengan alokasi resource pod akan menyelesaikan hambatan antrean lokal ini.*

#### Skenario 2: The Stale Read Anomaly
Sebuah aplikasi marketplace memisahkan pembacaan data katalog via Edge Cache (Upstash Redis) dan mutasi pesanan via Node.js Server Actions (PostgreSQL). Setelah pengguna berhasil melakukan pemesanan (stok berkurang dari 1 menjadi 0), pengguna langsung diarahkan (*redirect*) ke halaman katalog produk. Pengguna mendapati tombol "Beli Sekarang" masih aktif dan produk tertulis "Tersedia", namun ketika diklik menghasilkan error transaksi.

12. **Mekanisme arsitektur apa yang mengalami kegagalan dan bagaimana rancangan perbaikan permanennya?**
    - A. PostgreSQL membatalkan transaksi secara diam-diam (*silent rollback*).
    - B. Terjadi desinkronisasi cache (*stale read*) karena mutasi database tidak menerapkan invalidasi write-through atau cache purging atomik terhadap Edge Redis sebelum redirect diselesaikan.
    - C. Redis mengalami memory corruption dan mengembalikan data lama.
    - D. Next.js App Router memblokir server action redirect secara sepihak.
    *Jawaban yang benar: B*
    *Rasional Analisis: Ini adalah masalah klasik *Cache Invalidation*. Mutasi berhasil di database utama, namun layer Edge Cache tidak diperbarui secara sinkron sebelum navigasi klien dieksekusi. Diperlukan implementasi write-through update: tulis ke DB, perbarui/hapus kunci di Redis secara atomik, jalankan `revalidateTag()`, baru return respon ke klien.*

#### Skenario 3: The Edge Runtime Global Scale-up
Sebuah media berita global mengimplementasikan Next.js Edge Route Handlers di 30 region dunia untuk melayani jutaan pembaca. Setiap Edge Handler membaca data preferensi pengguna dari PostgreSQL managed database yang berlokasi tunggal di region AWS `us-east-1` menggunakan pooling TCP konvensional. Handler mengalami latensi ekstrem di wilayah Asia Pasifik (Sydney dan Tokyo) dengan rata-rata response time mencapai 1.200ms.

13. **Apa kegagalan desain fundamental pada sistem tersebut dan apa arsitektur solusinya?**
    - A. Jaringan kabel optik bawah laut sedang putus secara global.
    - B. Pelanggaran batas hukum transit data di region Asia Pasifik.
    - C. Physical distance latency overhead: Membuka koneksi TCP stateful lintas benua dari Edge Region ke Single DB Region menimbulkan multiple round-trips (RTT) handshake. Solusinya adalah memindahkan pembacaan preferensi ke Global Edge Storage (seperti KV/Edge Config) atau menggunakan read-replicas terdistribusi dengan HTTP tunneling proxy.
    - D. V8 Isolate membatasi throughput jaringan hingga maksimal 100kbps.
    *Jawaban yang benar: C*
    *Rasional Analisis: Mengakses satu database relasional di `us-east-1` dari Tokyo/Sydney via TCP membutuhkan beberapa RTT fisik (latensi dasar per RTT ~150-200ms). Handshake TCP + TLS + DB auth mengonsumsi 600-800ms murni untuk network round-trip sebelum data diproses. Data yang sering dibaca di edge wajib disimpan di distributed edge store, atau menggunakan protocol database proxy berbasis HTTP dengan localized connection termination.*

---

## 16. Summary

1. **Paradigma Ephemeral Compute vs Stateful DB**: PostgreSQL dirancang dengan model satu proses per koneksi yang rentan terhadap lonjakan *scale-out* serverless Next.js. Tanpa middleware pooling, aplikasi berisiko tinggi mengalami crash akibat kehabisan koneksi (*connection exhaustion*).
2. **Pemisahan Peran Koneksi**: Gunakan arsitektur pemisahan *connection string*: gunakan `DATABASE_URL` (melalui PgBouncer / RDS Proxy mode Transaksi) untuk operational runtime aplikasi, dan `DIRECT_URL` (port TCP direct) khusus untuk Prisma migration dan maintenance DDL.
3. **Pemberdayaan Dual-Runtime**:
   - **Edge Runtime**: Maksimalkan untuk rute pembacaan data ultra-cepat (<15ms) menggunakan Edge Storage berbasis HTTP (Upstash Redis, Vercel Edge Config, Cloudflare KV).
   - **Node.js Runtime**: Khususkan untuk alur mutasi bisnis, validasi kompleks, integritas ACID, dan transaksi relasional yang aman.
4. **Prepared Statements Caution**: Penggunaan mode *Transaction Pooling* pada external pooler mewajibkan penonaktifan cache prepared statement (`pgbouncer=true`) untuk mencegah collision antar eksekusi query pada koneksi database fisik yang sama.
5. **Production Readiness Rule**: Koneksi database pada Next.js harus selalu dibungkus dalam *global singleton pattern* untuk deployment Node.js, menjaga connection limit per instans serverless pada angka terendah (1-2 koneksi), dan menerapkan isolasi baris (`FOR UPDATE`) pada mutasi kritis guna menjamin konsistensi data enterprise.