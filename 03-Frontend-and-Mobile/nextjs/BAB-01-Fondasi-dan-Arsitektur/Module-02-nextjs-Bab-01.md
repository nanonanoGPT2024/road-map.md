# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Next.js Enterprise Foundation)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Membedah React Flight Wire Protocol**: Menjelajahi mekanisme serialisasi React Server Components (RSC) dari server ke client via HTTP streaming, serta memahami rekonstruksi React Fiber tree tanpa re-rendering redundan.
2. **Menguasai dan Mengendalikan 4-Tier Next.js Caching Architecture**: Mengimplementasikan kontrol granuler terhadap *Request Memoization*, *Data Cache*, *Full Route Cache*, dan *Router Cache*, termasuk mitigasi cache stampede pada high-throughput environments.
3. **Mengarsitekturi Runtime Execution Models**: Menentukan secara presisi kapan menggunakan *Edge Runtime (V8 Isolates)* versus *Node.js Server Runtime (Libuv event loop)* dengan mempertimbangkan batas komputasi, I/O latency, dan kompatibilitas paket npm.
4. **Mengimplementasikan Pola Komposisi Lanjutan**: Membangun *Streaming with Suspense Boundaries*, *Parallel Routes*, *Intercepting Routes*, serta *Hardened Server Actions* yang tahan terhadap exploitasi CSRF dan bypass autorisasi.
5. **Membangun Arsitektur Produksi Skala Besar**: Mendesain topologi *Multi-Zone Next.js*, reverse proxy orchestration, zero-downtime deployments, dan observability pipeline berbasis OpenTelemetry standar enterprise.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib memiliki pemahaman mendalam tentang:

* **Node.js Internals**: Event loop phase execution, garbage collection (V8 heap vs off-heap memory), stream piping (`ReadableStream`, `TransformStream`), and process clustering.
* **React 18/19 Core Architecture**: Concurrent Mode, Fiber architecture, Reconciliation algorithm, Transitions (`useTransition`), dan Suspense boundary mechanics.
* **Modern Web Networking**: Protokol HTTP/2 & HTTP/3 multiplexing, header controls (`Cache-Control`, `stale-while-revalidate`, `Vary`), TCP slow start, TLS termination, dan edge reverse proxies (Cloudflare, AWS CloudFront, Fastly).
* **TypeScript Advanced**: Discriminated unions, template literal types, higher-order type inference, dan generics constraints.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 React Server Components (RSC) & Flight Wire Protocol

Next.js App Router tidak merender HTML murni di server lalu mengirimkannya secara konvensional untuk dihidrasi secara keseluruhan (*destructive rehydration*). Sebaliknya, arsitektur ini memisahkan component tree menjadi dua domain: Server Component Tree dan Client Component Tree.

Proses eksekusi RSC menggunakan **React Flight Protocol**:
1. Server mengeksekusi komponen asinkron (*Async Server Components*).
2. React men-serialize Server Component tree ke dalam stream berbasis teks format JSON-RPC/Flight:
   * Baris yang diawali dengan identifier (misal `0:`, `1:`) memetakan chunk model UI.
   * Client Components diserialisasikan sebagai referensi modul (*Client Module References*) berupa manifest ID dan URL file bundle JavaScript, **bukan implementasi kodenya**.
   * Data props yang diteruskan dari Server ke Client Component diserialisasikan menjadi JSON payload di dalam protokol Flight.
3. Client menerima chunk stream tersebut secara progresif via chunked transfer encoding (`Transfer-Encoding: chunked`).
4. Browser mengeksekusi parsing format Flight secara bersamaan (*concurrently*) dan menyisipkannya ke dalam Fiber tree hidup tanpa menghilangkan local state dari Client Component yang sudah termuat.

```
+-------------------------------------------------------------------------+
| SERVER RUNTIME (Node.js / Edge)                                         |
|                                                                         |
|  Page (Server)                                                          |
|    |---> Header (Server)                                                |
|    |---> ProductFeed (Server, Async Data Fetch)                         |
|            |---> ClientReviews (Client Reference ID: "chunk_a7b.js")    |
|                                                                         |
|  [React Flight Serializer]                                              |
|    |                                                                    |
|    +---> Yields: "0:[\"$\",\"div\",null,{\"children\":[... ]}]"         |
|    +---> Yields: "1:I[\"chunk_a7b.js\",[\"default\"],\"ClientReviews\"]" |
+-------------------------------------------------------------------------+
                                    |
                    HTTP/2 Streaming Pipeline (Chunked)
                                    |
                                    v
+-------------------------------------------------------------------------+
| BROWSER RUNTIME (Client)                                                |
|                                                                         |
|  [Flight Protocol Deserializer & Fiber Reconciler]                      |
|    |                                                                    |
|    +---> Parses Server Tree Skeleton (Zero JS Runtime Overhead)         |
|    +---> Dynamic Import chunk_a7b.js ONLY for ClientReviews             |
|    +---> Progressive Hydration ONLY for ClientReviews                   |
|    `---> Existing DOM & React Client State are Preserved!               |
+-------------------------------------------------------------------------+
```

### 3.2 Matrix 4-Tier Caching Lifecycle

Next.js App Router mengimplementasikan empat lapisan cache independen yang bekerja secara berjenjang:

| Layer | Lokasi | Siklus Hidup (Lifetime) | Tujuan | Mekanisme Invalidasi |
| :--- | :--- | :--- | :--- | :--- |
| **Request Memoization** | Server Memory (V8 Heap Request-Scope) | Per satu siklus incoming HTTP request | Deduping pemanggilan fungsi/fetch identik di berbagai komponen | Otomatis reset saat request selesai |
| **Data Cache** | Server Persistent Store (Disk/Redis/Blob) | Melintasi multiple user requests & deploys | Menyimpan data fetch lintas request | `revalidateTag()`, `revalidatePath()`, TTL timer |
| **Full Route Cache** | Server Persistent Store (Disk/Build Output) | Melintasi request; dihitung saat build/revalidate | Menyimpan serialized RSC payload dan HTML statis | On-demand invalidation via Data Cache revalidation |
| **Router Cache** | Client Memory (Browser Session) | Session pengguna / in-memory React state | Navigasi instan back/forward di sisi client | `router.refresh()`, navigasi form mutation, cache TTL (30s dynamic / 5m static) |

```
Incoming Request
      │
      ▼
[1. Full Route Cache] ──(Hit)──► Return Pre-rendered HTML + Flight Payload
      │ (Miss)
      ▼
Execute RSC Render
      │
      ▼
Fetch Call Encountered
      │
      ▼
[2. Request Memoization] ──(Hit)──► Return Deduplicated Instance
      │ (Miss)
      ▼
[3. Data Cache] ──(Hit)──────────► Return Cached Upstream Response
      │ (Miss)
      ▼
Fetch from Upstream Origin / Database
      │
      ├─► Write to Data Cache
      └─► Return to RSC Render Pipeline
            │
            ▼
Output Cached to Full Route Cache (if static)
            │
            ▼
Send Stream to Client
            │
            ▼
[4. Router Cache (Client Memory)] ── Updates In-Memory Cache on Navigation
```

### 3.3 Edge Runtime vs Node.js Server Runtime

```
+------------------------------------+------------------------------------+
| Edge Runtime (V8 Isolates)         | Node.js Runtime (Libuv Pool)       |
+------------------------------------+------------------------------------+
| - Cold start: < 5ms                | - Cold start: 150ms - 1500ms       |
| - Memory footprint: 10MB - 128MB   | - Memory footprint: 128MB - 2GB+   |
| - Execution model: Event-driven V8 | - Execution model: Full event loop |
| - Native APIs: Fetch, Streams,     | - Native APIs: fs, child_process,  |
|   Web Crypto, TextEncoder/Decoder  |   net, TCP sockets, TLS, dynamic   |
| - Restrictions: NO native binary   | - Restrictions: Higher memory and  |
|   bindings (.node), NO arbitrary   |   higher cold start overhead       |
|   eval, NO native TCP driver       |                                    |
|   (requires HTTP-based DB proxies) |                                    |
+------------------------------------+------------------------------------+
```

---

## 4. Why & What

### Mengapa Paradigma Tradisional Gagal pada Skala Enterprise?
Pada arsitektur SPA murni (React CSR), client harus mendownload mega-bundle JavaScript sebelum browser dapat merender layout pertama, menyebabkan metrik **Time to Interactive (TTI)** dan **First Contentful Paint (FCP)** memburuk di jaringan berlatensi tinggi.

Pada SSR klasik (Next.js Pages Router via `getServerSideProps`), server memblokir respons HTTP hingga seluruh data siap (*data-fetching waterfall*). Jika salah satu microservice database downstream mengalami latensi 2 detik, browser pengguna menampilkan layar kosong selama 2 detik sebelum byte pertama dikirimkan (metrik **Time to First Byte / TTFB** terdegradasi).

### Solusi Arsitektur App Router Modern
App Router dengan RSC dan HTTP Streaming (`Suspense`) memecah model monolitik ini:
* **Selective SSR & Progressive Hydration**: Shell layout dikirimkan instan (TTFB < 50ms), sementara komponen berbasis I/O berat di-stream ke browser saat data siap.
* **Zero Client-Side Bundle Impact**: Dependency berat (seperti library formatting, Markdown parsers, JSON schema validators) yang ditaruh di dalam RSC tidak pernah dikirim ke browser client.
* **Unified Security Boundary**: Data kredensial database, internal endpoint URI, dan API secret tokens terkapsulasi secara fisik di server runtime.

---

## 5. How (Workflow Detail)

Alur eksekusi request pada level arsitektur produksi Next.js berjalan dengan tahapan deterministik berikut:

```
[Client Request]
       │
       ▼
1. Edge Middleware (V8 Isolate)
   ├─► Validasi JWT / Signature Session (Non-blocking)
   ├─► Edge Routing & URL Rewrite (Geo-routing, Tenant identification)
   └─► Response Header Injection (Nonce CSP, Correlation ID)
       │
       ▼
2. Core Server Gateway (Node.js / Edge Container)
   ├─► Evaluasi Full Route Cache
   │     ├─► Match: Return cached stream
   │     └─► Miss: Inisiasi React Server Component Tree Rendering
   │
   ├─► RSC Execution
   │     ├─► Async function calls trigger Database / Microservice requests
   │     ├─► Request Memoization mencegah duplikasi pemanggilan request yang sama
   │     └─► Evaluasi Data Cache (cek Tag & revalidate timer)
   │
   ├─► Serialization to Flight Protocol Stream
   │     ├─► Fast path: Render root layout skeleton immediately -> Stream via HTTP chunk
   │     └─► Slow path (Suspense): Emit placeholder fallback, stream completed nodes later
   │
   └─► Final HTTP Payload: Hybrid Stream (HTML markup + `<script>` Flight data injections)
       │
       ▼
3. Browser Client
   ├─► Parser menerima stream chunk pertama -> Immediate FCP
   ├─► Menghidrasi Client Components secara terisolasi tanpa memblokir DOM lain
   └─► Memperbarui Client-side Router Cache untuk navigasi instan berikutnya
```

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Logistik Pabrik Perakitan Mobil

* **Client Component (SPA klasik)**: Anda memesan mobil dari pabrik, tetapi pabrik hanya mengirimkan lembaran baja, mesin terpisah, dan buku manual setebal 2.000 halaman ke garasi rumah Anda. Anda harus merakit mobil tersebut sendiri di rumah sebelum bisa menyalakannya (Boros memori dan baterai perangkat pengguna).
* **Pages Router (SSR Klasik)**: Pabrik merakit seluruh mobil secara komplit. Namun, jika spion mobil tertunda produksinya selama 3 jam, seluruh mobil ditahan di pabrik dan tidak dikirim sampai spion terpasang.
* **App Router (RSC + Suspense + Streaming)**: Pabrik merakit sasis, roda, dan bodi utama (Layout & Shell) lalu langsung mengirimkannya dengan truk pengiriman cepat (Instant TTFB). Sementara mobil melaju ke rumah Anda, tim interior menyelesaikan jok dan aksesoris (Suspense payload). Begitu sampai di garasi, teknisi hanya perlu mengencangkan baut tombol elektronik di setir (Selective Hydration).

```
TRADISIONAL SSR (Blocking):
[--- Fetch Data A ---][--- Fetch Data B (Slow) ---][-- Render HTML --] >>> Browser (Blank screen) >>> Paint

APP ROUTER STREAMING:
[-- Shell RSC Render --] >>> Browser (Layout & Skeleton Rendered)
[-- Fetch Data A (Fast) --] >>> Stream Chunk A >>> Browser Hydrates Component A
[--- Fetch Data B (Slow) ---] >>> Stream Chunk B >>> Browser Replaces Skeleton B
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: RSC vs Client Boundary

Berikut pemisahan boundary yang benar antara Server Component dan Interactive Client Component:

```tsx
// app/simple-counter/CounterButton.tsx
"use client";

import { useState } from "react";

interface CounterButtonProps {
  initialCount: number;
}

export function CounterButton({ initialCount }: CounterButtonProps) {
  const [count, setCount] = useState<number>(initialCount);

  return (
    <button
      onClick={() => setCount((prev) => prev + 1)}
      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
    >
      Interaksi Client: {count}
    </button>
  );
}
```

```tsx
// app/simple-counter/page.tsx
import { CounterButton } from "./CounterButton";

// Server Component: Menjalankan eksekusi I/O tanpa bundle JS ke client
async function getInitialServerData(): Promise<number> {
  // Simulasi query database / microservice
  return 42;
}

export default async function SimpleCounterPage() {
  const initialData = await getInitialServerData();

  return (
    <main className="p-8">
      <h1 className="text-xl font-bold mb-4">Zero-JS Server Layout</h1>
      <p className="text-gray-600 mb-2">Nilai awal ini di-fetch dari server database:</p>
      {/* Mengirimkan data dari Server ke Client Boundary */}
      <CounterButton initialCount={initialData} />
    </main>
  );
}
```

---

### 7.2 Practical Example: Enterprise High-Throughput Inventory Monitor

Struktur kode skala produksi berikut mencakup:
1. Validasi Zod pada schema data eksternal.
2. Penanganan multi-tier cache dengan tagging granular.
3. Hardened Server Action dengan verifikasi autorisasi dan safe parsing.
4. Streaming granular melalui React `Suspense`.

#### A. Data Access Layer & Type Definitions
```typescript
// lib/dal/inventory.ts
import "server-only"; // Memastikan modul ini TIDAK DAPAT di-import oleh Client Components
import { z } from "zod";

export const InventoryItemSchema = z.object({
  sku: z.string().min(3),
  name: z.string(),
  stockLevel: z.number().int().nonnegative(),
  reservedLevel: z.number().int().nonnegative(),
  lastUpdated: z.string().datetime(),
});

export type InventoryItem = z.infer<typeof InventoryItemSchema>;

export async function getInventoryBySku(sku: string): Promise<InventoryItem> {
  const upstreamUrl = `${process.env.INTERNAL_INVENTORY_API}/v1/skus/${encodeURIComponent(sku)}`;
  
  // Tagging data cache untuk targeted on-demand revalidation
  const response = await fetch(upstreamUrl, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${process.env.INTERNAL_SERVICE_TOKEN}`,
      "Content-Type": "application/json",
      "X-Correlation-Id": crypto.randomUUID(),
    },
    next: {
      tags: [`inventory:${sku}`, "inventory:all"],
      revalidate: 60, // ISR Fallback 60 detik jika tag tidak dipicu
    },
  });

  if (!response.ok) {
    throw new Error(`Gagal mengambil SKU: ${sku}. Status HTTP: ${response.status}`);
  }

  const rawData = await response.json();
  const parsed = InventoryItemSchema.safeParse(rawData);

  if (!parsed.success) {
    throw new Error(`Data corruption terdeteksi dari upstream API: ${parsed.error.message}`);
  }

  return parsed.data;
}
```

#### B. Server Action Terproteksi
```typescript
// actions/inventory-mutations.ts
"use server";

import { revalidateTag } from "next/cache";
import { z } from "zod";

const StockAdjustmentSchema = z.object({
  sku: z.string().min(3),
  delta: z.number().int().min(-500).max(500),
  reason: z.string().min(5),
});

export interface ActionResult<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export async function adjustStockAction(
  prevState: unknown,
  formData: FormData
): Promise<ActionResult<{ newStock: number }>> {
  try {
    // 1. Validasi Input Data
    const rawPayload = {
      sku: formData.get("sku"),
      delta: Number(formData.get("delta")),
      reason: formData.get("reason"),
    };

    const validated = StockAdjustmentSchema.safeParse(rawPayload);
    if (!validated.success) {
      return {
        success: false,
        error: `Payload tidak valid: ${validated.error.issues.map(i => i.message).join(", ")}`,
      };
    }

    // 2. Autentikasi / Otorisasi State (Mock context isolation)
    const sessionToken = process.env.INTERNAL_SERVICE_TOKEN;
    if (!sessionToken) {
      return { success: false, error: "Konteks sesi server tidak terverifikasi." };
    }

    // 3. Mutasi ke Upstream Core System
    const mutationUrl = `${process.env.INTERNAL_INVENTORY_API}/v1/skus/${validated.data.sku}/adjust`;
    const res = await fetch(mutationUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${sessionToken}`,
      },
      body: JSON.stringify(validated.data),
    });

    if (!res.ok) {
      return { success: false, error: `Upstream error: HTTP ${res.status}` };
    }

    const resultData = await res.json();

    // 4. On-demand Precise Cache Invalidation
    // Hanya membatalkan cache SKU spesifik ini, bukan seluruh database
    revalidateTag(`inventory:${validated.data.sku}`);

    return {
      success: true,
      data: { newStock: resultData.stockLevel },
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Terjadi kesalahan internal server";
    return { success: false, error: message };
  }
}
```

#### C. Interactive Client Component
```tsx
// components/InventoryAdjuster.tsx
"use client";

import { useActionState } from "react";
import { adjustStockAction, ActionResult } from "@/actions/inventory-mutations";

interface Props {
  sku: string;
}

const initialState: ActionResult<{ newStock: number }> = {
  success: false,
};

export function InventoryAdjuster({ sku }: Props) {
  const [state, formAction, isPending] = useActionState(adjustStockAction, initialState);

  return (
    <div className="border border-slate-300 rounded p-4 bg-white shadow-sm">
      <h3 className="text-md font-semibold text-slate-800 mb-2">Penyesuaian Stok Cepat (Server Action)</h3>
      <form action={formAction} className="space-y-3">
        <input type="hidden" name="sku" value={sku} />
        
        <div>
          <label className="block text-sm text-slate-600">Delta Jumlah Stok (+/-)</label>
          <input
            type="number"
            name="delta"
            required
            defaultValue={1}
            className="w-full border rounded px-3 py-1 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-600">Alasan Penyesuaian</label>
          <input
            type="text"
            name="reason"
            required
            placeholder="Audit inventaris berkala"
            className="w-full border rounded px-3 py-1 text-sm"
          />
        </div>

        {state.error && (
          <div className="text-red-600 text-sm bg-red-50 p-2 rounded border border-red-200">
            {state.error}
          </div>
        )}

        {state.success && (
          <div className="text-emerald-700 text-sm bg-emerald-50 p-2 rounded border border-emerald-200">
            Sukses mengubah stok. Level baru: {state.data?.newStock}
          </div>
        )}

        <button
          type="submit"
          disabled={isPending}
          className="w-full bg-slate-900 text-white py-2 rounded text-sm hover:bg-slate-800 disabled:opacity-50 transition"
        >
          {isPending ? "Memproses Pembaruan..." : "Simpan Mutasi"}
        </button>
      </form>
    </div>
  );
}
```

#### D. Page Integration with Streaming Boundary
```tsx
// app/inventory/[sku]/page.tsx
import { Suspense } from "react";
import { getInventoryBySku } from "@/lib/dal/inventory";
import { InventoryAdjuster } from "@/components/InventoryAdjuster";

interface PageProps {
  params: Promise<{ sku: string }>;
}

// Server Component: Menjalankan eksekusi I/O terisolasi
async function InventoryDetails({ sku }: { sku: string }) {
  const item = await getInventoryBySku(sku);

  return (
    <div className="bg-slate-50 border rounded-lg p-6 space-y-2">
      <div className="text-2xl font-bold text-slate-900">{item.name}</div>
      <div className="text-sm font-mono text-slate-500">SKU: {item.sku}</div>
      <div className="flex gap-4 pt-4">
        <div className="p-3 bg-white border rounded">
          <span className="block text-xs text-slate-500">Stok Tersedia</span>
          <span className="text-xl font-bold text-emerald-600">{item.stockLevel}</span>
        </div>
        <div className="p-3 bg-white border rounded">
          <span className="block text-xs text-slate-500">Stok Dipesan</span>
          <span className="text-xl font-bold text-amber-600">{item.reservedLevel}</span>
        </div>
      </div>
      <div className="text-xs text-slate-400 mt-2">Sinkronisasi terakhir: {item.lastUpdated}</div>
    </div>
  );
}

function InventorySkeleton() {
  return (
    <div className="bg-slate-100 border rounded-lg p-6 space-y-4 animate-pulse">
      <div className="h-8 bg-slate-200 rounded w-1/3"></div>
      <div className="h-4 bg-slate-200 rounded w-1/4"></div>
      <div className="flex gap-4 pt-4">
        <div className="h-16 bg-slate-200 rounded w-28"></div>
        <div className="h-16 bg-slate-200 rounded w-28"></div>
      </div>
    </div>
  );
}

export default async function InventoryPage({ params }: PageProps) {
  const { sku } = await params;

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      <header className="border-b pb-4">
        <h1 className="text-3xl font-extrabold text-slate-900">Dashboard Manajemen Gudang</h1>
        <p className="text-slate-500 text-sm">Real-time Data Fetching & Isolated Client Hydration</p>
      </header>

      {/* Streaming boundary: Shell layout di-render secara instan ke browser */}
      <Suspense fallback={<InventorySkeleton />}>
        <InventoryDetails sku={sku} />
      </Suspense>

      <InventoryAdjuster sku={sku} />
    </div>
  );
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Flash Sale E-Commerce Global (50M MAU, 120.000 RPS Peak)

* **Problem**: 
  Sebuah marketplace ritel global menghadapi lonjakan trafik masif pada jam peluncuran produk diskon. Arsitektur lama berbasis SSR dinamis menyebabkan Node.js event loop lagging (*heartbeat delay > 1200ms*), mengakibatkan koneksi database downstream habis (*connection pool starvation*) dan sistem kolaps dalam 45 detik pertama peluncuran.
* **Diagnosa Teknis**:
  * Render SSR monolithic memicu ratusan ribu koneksi paralel langsung ke database PostgreSQL melalui Prisma ORM.
  * Halaman produk melakukan dynamic rendering penuh hanya demi menampilkan 1 elemen dinamis: *Available Stock Badge*, sementara deskripsi, gambar, dan review produk bersifat statis.
* **Solusi Arsitektur Menggunakan Next.js Production Pattern**:
  1. **Decoupled Shell Layout & ISR**: Mengubah halaman utama produk menjadi statis via Full Route Cache menggunakan fallback ISR dinamis (`revalidate = 3600`). Payload static HTML & Flight assets di-offload 100% ke Edge CDN.
  2. **Streaming Suspense untuk Komponen Kritis**: Membungkus komponen inventaris stok dinamis ke dalam boundary `Suspense`. Browser langsung menerima respons instan dari CDN (< 25ms), lalu koneksi streaming dibuka untuk mengambil badge status ketersediaan.
  3. **Data Cache dengan Redis Stale-While-Revalidate Adapter**: Menghubungkan Next.js Data Cache ke cluster distributed Redis. Saat cache kadaluarsa, hanya 1 request pertama yang diizinkan memanggil backend API (menggunakan mutex lock), request lainnya menerima data stale secara transparan.
  4. **Edge Token Bucket Rate-Limiting**: Mencegah botting pada Server Action checkout menggunakan Edge Middleware berbasis V8 Isolate dengan latensi eksekusi < 2ms.
* **Hasil (Metrik Produksi)**:
  * P95 TTFB turun dari 2.400ms menjadi 42ms.
  * Load downstream database berkurang hingga 94,8%.
  * Zero-downtime tercapai dengan throughput konstan 125.000 RPS.

---

## 9. Trade-offs

Setiap keputusan arsitektur di Next.js melibatkan trade-off langsung antara performa, latensi, isolasi data, dan kompleksitas operasional:

```
+---------------------------------------------------------------------------------------------------+
| STRATEGI          | PERFORMANCE (TTFB) | HIT LATENCY | SCALABILITY  | COST IMPACT | KOMPLEKSITAS  |
+---------------------------------------------------------------------------------------------------+
| Static Pre-render | Ultra Cepat        | < 15ms      | Hampir Tak   | Sangat      | Rendah        |
| (SSG / Build-time)| (Static CDN)       |             | Terbatas     | Rendah      |               |
+---------------------------------------------------------------------------------------------------+
| On-Demand ISR     | Cepat              | 20ms - 80ms | Sangat       | Rendah      | Sedang        |
| (Tag Revalidation)| (Cache edge/disk)  |             | Tinggi       |             |               |
+---------------------------------------------------------------------------------------------------+
| Dynamic Streaming | Bertahap           | Initial:    | Menengah-    | Menengah-   | Tinggi        |
| (RSC + Suspense)  | (Shell cepat, data | 50ms - 150ms| Tinggi       | Tinggi      |               |
|                   | menyusul)          |             |              |             |               |
+---------------------------------------------------------------------------------------------------+
| Full Dynamic SSR  | Lambat             | 250ms -     | Terbatas     | Sangat      | Rendah        |
| (No-store)        | (Tergantung DB/I/O)| 2000ms+     | pada compute | Tinggi      |               |
+---------------------------------------------------------------------------------------------------+
```

### Analisis Mendalam Trade-offs:
1. **Edge Runtime vs Node.js**:
   * *Edge*: Cold start instan (~5ms), efisiensi biaya luar biasa di multi-region. Namun, **tidak mendukung native driver TCP** (membutuhkan database proxy seperti Prisma Accelerate atau Neon over HTTP), batasan memori ketat (biasanya 128MB per invokasi), dan tidak mendukung seluruh node modules.
   * *Node.js*: Kompatibilitas library npm 100%, akses native socket TCP, memory limit longgar. Namun, memiliki ancaman cold start kontainer berat (1s+) dan biaya compute instance VM/container yang konstan.
2. **Server Actions vs REST/tRPC API Routes**:
   * *Server Actions*: DX luar biasa, integrasi form mutasi otomatis, dead code elimination otomatis, dan native RPC. Namun, coupling ketat dengan framework frontend (sukar dikonsumsi langsung oleh native iOS/Android mobile clients).

---

## 10. Common Mistakes & Troubleshooting

### 1. The Serialization Boundary Crash
* **Gejala**: Error `Error: Functions cannot be passed directly to Client Components unless you explicitly expose it with "use server"`.
* **Root Cause**: Mengirimkan objek kompleks yang mengandung method, class instances (misal: Prisma Client instances atau Date/Symbol method), atau callback function langsung dari Server Component ke Client Component.
* **Solusi**: Pastikan seluruh boundary payload berbentuk plain JSON-serializable primitives, atau transformasikan class instance menjadi Plain Old JavaScript Object (POJO) menggunakan Zod atau serialisasi eksplisit.

### 2. Thundering Herd Problem pada ISR Cache
* **Gejala**: Saat cache tag expire di traffic puncak, ribuan request bersamaan memicu kalkulasi ulang ke backend secara simultan, menembus batas koneksi database downstream.
* **Root Cause**: Next.js Data Cache default pada disk lokal multi-instance tidak membagikan lock revalidasi antar server node pod Kubernetes.
* **Solusi**: Gunakan custom Next.js Cache Handler yang terdistribusi (Redis / Memcached) dengan implementasi atomic locking / Mutex.

```typescript
// cache-handler.mjs (Custom Cache Handler untuk Next.js)
import { createClient } from "redis";

const redis = createClient({ url: process.env.REDIS_CACHE_URL });
redis.connect().catch(console.error);

export default class EnterpriseRedisCacheHandler {
  async get(key) {
    const data = await redis.get(key);
    return data ? JSON.parse(data) : null;
  }

  async set(key, data, ctx) {
    // Implementasi TTL berbasis internal metadata ctx.revalidate
    const ttl = typeof ctx.revalidate === "number" ? ctx.revalidate : 86400;
    await redis.set(key, JSON.stringify(data), { EX: ttl });
  }

  async revalidateTag(tag) {
    // Mencari kunci terkait tag dan membatalkannya secara terkoordinasi
    const keys = await redis.sMembers(`tag:${tag}`);
    if (keys.length > 0) {
      await redis.del(keys);
      await redis.del(`tag:${tag}`);
    }
  }
}
```

### 3. Hydration Mismatch Akibat State Perangkat yang Divergen
* **Gejala**: Warning di konsol browser: `Hydration failed because the initial UI does not match what was rendered on the server`.
* **Root Cause**: Menggunakan nilai dinamis yang bergantung pada client (misal: `window.innerWidth`, `localStorage`, atau `new Date().toLocaleString()`) langsung di fase initial render Client Component.
* **Solusi**: Gunakan pattern `useEffect` dengan hydration guard flag atau pisahkan rendering state client setelah mounting:

```tsx
"use client";

import { useState, useEffect } from "react";

export function ClientOnlyTimestamp() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <span className="opacity-0">Memuat waktu...</span>; // Placeholder sinkron dengan SSR
  }

  return <span>{new Date().toLocaleTimeString()}</span>;
}
```

---

## 11. Best Practices (Production Checklist)

### Security Checklist
- [ ] Beri anotasi `import "server-only"` pada semua modul data-access/database layer untuk mencegah kebocoran kode kredensial ke client bundle secara absolut.
- [ ] Validasi seluruh payload Server Actions menggunakan Zod/Valibot. Jangan percaya input form dari client.
- [ ] Konfigurasi Content Security Policy (CSP) berbasis cryptographic nonce di middleware untuk mengeliminasi serangan XSS.
- [ ] Terapkan Origin Header Check pada Server Actions untuk proteksi Cross-Site Request Forgery (CSRF).

### Architecture & Performance Checklist
- [ ] Pastikan dependency besar (misal: `lodash`, `moment`, `markdown-it`, `shiki`) hanya di-import di dalam Server Components.
- [ ] Pasang `next/dynamic` dengan `{ ssr: false }` hanya pada modul interactive third-party canvas/chart yang tidak membutuhkan SEO.
- [ ] Konfigurasikan image domains secara eksplisit pada `next.config.js` dan gunakan format modern `AVIF` dan `WebP`.
- [ ] Selalu bungkus dynamic leaf nodes di dalam `<Suspense>` boundaries untuk mencegah TTFB blocking.

### Observability & Telemetry Checklist
- [ ] Aktifkan modul `instrumentation.ts` bawaan Next.js untuk registrasi OpenTelemetry SDK.
- [ ] Teruskan header `x-correlation-id` / `traceparent` dari Edge Middleware ke seluruh downstream API microservices.
- [ ] Pantau core Web Vitals (INP, LCP, CLS) menggunakan endpoint pelaporan via `useReportWebVitals` atau custom edge sink.

---

## 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun sistem arsitektur produksi Next.js yang menerapkan **Data Access Layer terisolasi, Streaming Suspense, dan Server Action mutasi dengan On-Demand Revalidation**.

### Direktori Kerja Target
Seluruh file praktikum harus ditempatkan di:
```text
hands-on/m02/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── telemetry/
│       └── route.ts
├── actions/
│   └── audit-actions.ts
├── components/
│   ├── AuditFeedClient.tsx
│   └── MetricCardStreaming.tsx
├── lib/
│   └── dal.ts
├── next.config.mjs
├── package.json
└── tsconfig.json
```

### Langkah 1: Inisialisasi Konfigurasi Dasar

Buat file konfigurasi inti:

```json
// hands-on/m02/package.json
{
  "name": "nextjs-enterprise-m02",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "server-only": "^0.0.1",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.6.0"
  }
}
```

```javascript
// hands-on/m02/next.config.mjs
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Mengaktifkan isolasi logging streaming fetch di development console
    logging: {
      fetches: {
        fullUrl: true,
      },
    },
  },
};

export default nextConfig;
```

### Langkah 2: Membangun Data Access Layer (DAL)

Buat file DAL terisolasi dengan implementasi server-only:

```typescript
// hands-on/m02/lib/dal.ts
import "server-only";
import { z } from "zod";

export const SystemMetricSchema = z.object({
  cpuUtilization: z.number(),
  memoryUsageMB: z.number(),
  activeConnections: z.number(),
  timestamp: z.string(),
});

export type SystemMetric = z.infer<typeof SystemMetricSchema>;

// Mock data fetcher yang mensimulasikan latensi I/O tinggi
export async function getLiveSystemMetrics(): Promise<SystemMetric> {
  // Simulasi latensi jaringan database downstream (1.5 detik)
  await new Promise((resolve) => setTimeout(resolve, 1500));

  return {
    cpuUtilization: parseFloat((Math.random() * 40 + 10).toFixed(2)),
    memoryUsageMB: Math.floor(Math.random() * 1024 + 2048),
    activeConnections: Math.floor(Math.random() * 500 + 1200),
    timestamp: new Date().toISOString(),
  };
}

export async function getAuditLogs(): Promise<string[]> {
  // Fetch simulasi dengan Request Memoization bawaan
  return [
    "LOG_101: TLS handshake established from edge-proxy-sg",
    "LOG_102: JWT token issued for session role 'operator'",
    "LOG_103: Redis cluster healthy at shard-us-east-1a",
  ];
}
```

### Langkah 3: Membuat Mutasi Server Actions Terproteksi

```typescript
// hands-on/m02/actions/audit-actions.ts
"use server";

import { revalidateTag } from "next/cache";
import { z } from "zod";

const TriggerDumpSchema = z.object({
  targetModule: z.enum(["SYSTEM", "NETWORK", "AUTH"]),
  authorizationCode: z.string().min(6),
});

export async function submitAuditLogAction(formData: FormData) {
  const payload = {
    targetModule: formData.get("targetModule"),
    authorizationCode: formData.get("authorizationCode"),
  };

  const parsed = TriggerDumpSchema.safeParse(payload);

  if (!parsed.success) {
    return {
      success: false,
      message: `Validasi gagal: ${parsed.error.issues[0].message}`,
    };
  }

  // Simulasi mutasi database audit trail
  await new Promise((resolve) => setTimeout(resolve, 300));

  // Invalidate cache tag
  revalidateTag("audit-trail");

  return {
    success: true,
    message: `Audit triggered for module ${parsed.data.targetModule} at ${new Date().toISOString()}`,
  };
}
```

### Langkah 4: Membuat Komponen Streaming & Hydration

```tsx
// hands-on/m02/components/MetricCardStreaming.tsx
import { getLiveSystemMetrics } from "@/lib/dal";

export async function MetricCardStreaming() {
  const metrics = await getLiveSystemMetrics();

  return (
    <div style={{ border: "1px solid #059669", padding: "1rem", borderRadius: "8px", background: "#ecfdf5" }}>
      <h3 style={{ margin: 0, color: "#065f46" }}>Live Node Telemetry (Streaming Leaf Node)</h3>
      <p style={{ margin: "4px 0" }}>CPU: <strong>{metrics.cpuUtilization}%</strong></p>
      <p style={{ margin: "4px 0" }}>RAM: <strong>{metrics.memoryUsageMB} MB</strong></p>
      <p style={{ margin: "4px 0" }}>TCP Sockets: <strong>{metrics.activeConnections}</strong></p>
      <small style={{ color: "#047857" }}>Sampled at: {metrics.timestamp}</small>
    </div>
  );
}

export function MetricCardSkeleton() {
  return (
    <div style={{ border: "1px dashed #9ca3af", padding: "1rem", borderRadius: "8px", background: "#f3f4f6" }}>
      <p style={{ color: "#6b7280", margin: 0 }}>Memuat data stream telemetri dari upstream...</p>
    </div>
  );
}
```

```tsx
// hands-on/m02/components/AuditFeedClient.tsx
"use client";

import { useActionState } from "react";
import { submitAuditLogAction } from "@/actions/audit-actions";

export function AuditFeedClient({ logs }: { logs: string[] }) {
  const [state, formAction, isPending] = useActionState(
    async (_prev: unknown, formData: FormData) => {
      return await submitAuditLogAction(formData);
    },
    null
  );

  return (
    <div style={{ border: "1px solid #cbd5e1", padding: "1rem", borderRadius: "8px", marginTop: "1.5rem" }}>
      <h3 style={{ margin: 0 }}>Log Audit Terkini (Hydrated Client)</h3>
      <ul>
        {logs.map((log, idx) => (
          <li key={idx} style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>{log}</li>
        ))}
      </ul>

      <form action={formAction} style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
        <select name="targetModule" style={{ padding: "0.4rem" }}>
          <option value="SYSTEM">Modul SYSTEM</option>
          <option value="NETWORK">Modul NETWORK</option>
          <option value="AUTH">Modul AUTH</option>
        </select>

        <input
          type="password"
          name="authorizationCode"
          placeholder="Auth Code (min 6 char)"
          required
          style={{ padding: "0.4rem", border: "1px solid #94a3b8" }}
        />

        <button
          type="submit"
          disabled={isPending}
          style={{ padding: "0.4rem 1rem", background: "#0f172a", color: "#fff", border: "none", borderRadius: "4px" }}
        >
          {isPending ? "Mengirim..." : "Trigger Audit Log"}
        </button>
      </form>

      {state && (
        <p style={{ color: state.success ? "#15803d" : "#b91c1c", fontSize: "0.9rem", marginTop: "0.5rem" }}>
          {state.message}
        </p>
      )}
    </div>
  );
}
```

### Langkah 5: Mengintegrasikan Page Shell

```tsx
// hands-on/m02/app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: "800px", margin: "0 auto" }}>
        {children}
      </body>
    </html>
  );
}
```

```tsx
// hands-on/m02/app/page.tsx
import { Suspense } from "react";
import { getAuditLogs } from "@/lib/dal";
import { MetricCardStreaming, MetricCardSkeleton } from "@/components/MetricCardStreaming";
import { AuditFeedClient } from "@/components/AuditFeedClient";

export default async function DashboardPage() {
  // Shell Page me-render audit logs instan
  const initialLogs = await getAuditLogs();

  return (
    <main>
      <h1>Arsitektur Next.js Enterprise: Hands-on Module 02</h1>
      <p style={{ color: "#475569" }}>
        Halaman ini membuktikan eksekusi Non-blocking HTTP Streaming dan Client Hydration terisolasi.
      </p>

      {/* Streaming Boundary: Bagian lambat diisolasi tanpa menahan layout utama */}
      <section style={{ margin: "1.5rem 0" }}>
        <h2>Status Mesin Waktu-Nyata</h2>
        <Suspense fallback={<MetricCardSkeleton />}>
          <MetricCardStreaming />
        </Suspense>
      </section>

      {/* Komponen Client Interaktif */}
      <AuditFeedClient logs={initialLogs} />
    </main>
  );
}
```

---

## 13. Exercise

### Level Easy
Modifikasi file `hands-on/m02/lib/dal.ts` untuk menambahkan caching strategy berbasis waktu (`next: { revalidate: 15 }`) pada fungsi baru bernama `getAppHealthStatus()`. Tampilkan output status tersebut di file `app/page.tsx` tanpa menggunakan `<Suspense>`.
* **Kriteria Keberhasilan**: Status health tampil saat build statis, dan jika di-refresh, nilai timestamp internal hanya berubah paling cepat setiap 15 detik.

### Level Medium
Buatlah sebuah *Parallel Route* slot bernama `@analytics` di dalam direktori `app/` yang memuat komponen visualisasi grafik CPU statis. 
* **Kriteria Keberhasilan**: Slot `@analytics` merender kontennya secara independen di file `layout.tsx` menggunakan `props.analytics`, memiliki file `default.tsx` fallback, dan menampilkan error state tersendiri jika microservice analitik gagal dipanggil tanpa memecahkan halaman utama.

### Level Hard
Implementasikan sebuah custom middleware di file `middleware.ts` pada root hands-on yang:
1. Menghasilkan Cryptographic Nonce CSP acak per request.
2. Menyematkan header keamanan standar industri: `Content-Security-Policy`, `X-Frame-Options: DENY`, dan `X-Content-Type-Options: nosniff`.
3. Meneruskan nonce tersebut ke komponen Server Component via header request internal (`x-nonce`) sehingga script inline dapat tereksekusi dengan valid tanpa flag `unsafe-inline`.
* **Kriteria Keberhasilan**: Semua header terdeteksi via browser DevTools `curl -I`, inline script tanpa tag nonce diblokir oleh browser CSP engine.

---

## 14. Challenge

### Studi Kasus Arsitektur: Dynamic Multi-Tenant White-Label E-Commerce Platform

Anda ditunjuk sebagai Principal Architect untuk merancang platform B2B White-Label e-commerce global yang melayani lebih dari 10.000 tenant brand independen dalam 1 codebase Next.js App Router tunggal.

#### Batasan & Kebutuhan Sistem:
1. **Custom Domain Dynamic Resolution**: Request dari `store.brand-a.com` dan `shop.brand-b.co.uk` masuk ke cluster Next.js yang sama. Middleware harus mendeteksi domain, mencocokkan tenant ID dari cache edge (V8 Isolate) dalam waktu < 3ms, dan melakukan internal rewrite ke subdirektori tenant tanpa redirect 301/302.
2. **Strict Isolated Caching**: Revalidasi cache (`revalidateTag`) untuk Tenant A **sama sekali tidak boleh** membatalkan atau mengotori cache data milik Tenant B, meskipun mereka berbagi skema database dan layout template yang identik.
3. **Resilient Streaming Under Degradation**: Jika engine inventaris stok tenant mengalami down/timeout (Circuit Breaker status: OPEN), halaman landing page produk harus tetap dapat dirender via static cache dengan fallback UI "Status stok sementara tidak tersedia" secara otomatis dalam waktu < 200ms TTFB.
4. **Zero Client-Side Secret Leakage**: Konfigurasi payment gateway (Stripe/Adyen keys) berbeda untuk setiap tenant. Sistem harus menjamin secara kriptografis bahwa variabel privat tenant tidak pernah terbundle ke browser client mana pun.

#### Tugas Tantangan:
Tuliskan dokumen spesifikasi arsitektur teknis lengkap beserta diagram alur pemrosesan request dan potongan kode middleware, custom data fetcher layer, dan skema invalidasi cache terdistribusi untuk platform tersebut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda / Konseptual Singkat)

1. Apa peran format serialisasi **React Flight** di Next.js App Router?
   * A. Menggantikan format JSON dengan binary Protocol Buffers murni pada REST API.
   * B. Mengirimkan representasi tree komponen server dan referensi module client ke browser dalam bentuk chunk streaming.
   * C. Melakukan kompresi file CSS dan JavaScript sebelum diunggah ke CDN.
   * D. Menghubungkan WebSocket client secara langsung ke database instance.

2. Kapan **Request Memoization** di server Next.js di-reset atau dibersihkan?
   * A. Setiap 60 detik secara default.
   * B. Ketika perintah `revalidateTag` dijalankan.
   * C. Segera setelah siklus satu incoming HTTP request selesai diproses server.
   * D. Ketika container server di-restart.

3. Manakah direktif yang wajib dideklarasikan di baris paling atas sebuah file untuk membuat Server Action?
   * A. `"use server-action"`
   * B. `"use server"`
   * C. `"use backend"`
   * D. `"server-only"`

4. Apa fungsi dari package `"server-only"` jika di-import ke dalam sebuah file modul?
   * A. Memaksa fungsi di dalamnya dijalankan menggunakan Edge Runtime.
   * B. Melempar build-time error jika modul tersebut tanpa sengaja di-import ke Client Component.
   * C. Menghapus semua kode TypeScript dari file saat dicompile.
   * D. Mengamankan file dari eksploitasi SQL Injection secara otomatis.

5. Lapisan cache Next.js manakah yang beroperasi langsung di dalam memori web browser pengguna?
   * A. Full Route Cache
   * B. Data Cache
   * C. Router Cache
   * D. Request Memoization

---

### Bagian B: Intermediate (Analisis Kasus Singkat)

6. Sebuah komponen dideklarasikan dengan `async function ProductInfo()` dan langsung memanggil `db.query()`. Mengapa komponen ini **wajib** berstatus Server Component dan tidak bisa dijadikan Client Component?
   * A. Karena Client Component tidak mendukung sintaks CSS Tailwind.
   * B. Karena Client Component di-bundle ke browser; menyertakan koneksi database langsung di client akan membocorkan kredensial database dan memicu error karena runtime browser tidak memiliki socket TCP native.
   * C. Karena React Fiber tidak mengizinkan async function pada arsitektur DOM browser.
   * D. Karena file Client Component hanya dapat membaca data bertipe string.

7. Perhatikan potongan kode berikut:
   ```typescript
   export const dynamic = "force-static";
   export default async function Page() {
     const data = await fetch("https://api.internal/stats", { cache: "no-store" });
     return <div>{data.status}</div>;
   }
   ```
   Apa yang terjadi saat proses `next build` dijalankan? Mengapa terjadi konflik?
   * A. Build sukses, `cache: "no-store"` diprioritaskan sehingga halaman menjadi dinamis total.
   * B. Terjadi conflict build warning/error karena `force-static` memaksa halaman menjadi statis, sementara `no-store` secara eksplisit meminta data selalu diambil dinamis per request tanpa cache.
   * C. Halaman otomatis dihapus oleh compiler Next.js.
   * D. Request fetch dialihkan ke browser runtime.

8. Jelaskan perbedaan fundamental antara fungsi `revalidatePath("/products/[id]", "page")` dan `revalidateTag("product-data")` pada pembaruan data sistem e-commerce berskala 100.000 SKU!
   * A. Tidak ada perbedaan performa; keduanya memvalidasi ulang seluruh disk server.
   * B. `revalidatePath` hanya membatalkan cache berdasarkan URL path tertentu, sedangkan `revalidateTag` membatalkan seluruh data cache yang ditempeli tag identifier tersebut lintas URL dan komponen secara granular tanpa perlu mengetahui ribuan path URL-nya.
   * C. `revalidateTag` hanya bekerja pada Edge runtime, sedangkan `revalidatePath` eksklusif untuk Node.js.
   * D. `revalidateTag` membutuhkan database external Redis, sedangkan `revalidatePath` tidak.

9. Mengapa nesting Client Component di dalam Server Component (`Server -> Client`) diizinkan, sedangkan meng-import Server Component secara langsung di dalam file Client Component (`Client -> Server`) dilarang?
   * A. Karena compiler webpack Next.js akan mendegradasi Server Component tersebut menjadi Client Component jika di-import langsung di file yang bertanda `"use client"`.
   * B. Karena file Client Component tidak memiliki akses internet.
   * C. Karena Server Component berukuran byte lebih besar.
   * D. Karena React Hook tidak berfungsi di Server Component.

10. Bagaimana cara yang benar menyematkan Server Component sebagai anak dari sebuah Client Component tanpa merusak batasan eksekusi server-side nya?
    * A. Melakukan dynamic import `next/dynamic` dengan opsi server.
    * B. Mengirimkan Server Component tersebut melalui `children` prop atau slot JSX props lainnya dari parent Server Component level atas.
    * C. Menggunakan tag iframe HTML.
    * D. Memanggil method `fetch()` ke komponen tersebut dari client.

---

### Bagian C: Skenario Kasus Produksi (Troubleshooting & Real-World Fixes)

11. **Skenario 1 (Memory Leak pada Server Actions)**:
    Sebuah aplikasi perbankan Next.js yang dideploy pada kluster Kubernetes (Node.js runtime pod) mengalami crash *Out Of Memory (OOM)* setiap 6 jam. Setelah pemeriksaan memory dump, ditemukan bahwa terdapat array global di server yang digunakan untuk menampung event logging dari `submitTransactionAction`. Mengapa arsitektur Serverless / Pod Container Next.js membuat pattern global state in-memory berbahaya dan bagaimana arsitektur yang benar untuk logging audit trail?

12. **Skenario 2 (Stale Session Pasca Mutasi)**:
    Setelah pengguna mengganti foto profil via Server Action, halaman profil pengguna tetap menampilkan foto lama meskipun fungsi `revalidatePath('/profile')` telah dipanggil di action tersebut. Namun, jika pengguna menutup browser dan membukanya kembali, foto baru langsung tampil. Selidiki lapisan cache mana yang menjadi biang kerok kegagalan update instan ini dan sebutkan solusinya pada sisi client code!

13. **Skenario 3 (Suspense Streaming Terblokir Total)**:
    Tim frontend membuat layout dashboard dengan struktur:
    ```tsx
    // app/dashboard/layout.tsx
    export default async function Layout({ children }) {
      const user = await fetchUserDataFromSlowService(); // Membutuhkan waktu 3000ms
      return <div><Sidebar user={user} />{children}</div>;
    }
    ```
    Di dalam `children` (`app/dashboard/page.tsx`), mereka membungkus feed komponen dengan `<Suspense fallback={<Skeleton />}>`. Namun, browser tetap mengalami blank screen selama 3 detik sebelum skeleton maupun layout muncul. Analisis mengapa streaming Suspense pada `page.tsx` terblokir total dan rancang refactoring yang tepat!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A:
1. **B** — Protokol Flight mengalirkan tree UI RSC dan mapping modul client melalui HTTP streaming.
2. **C** — Request Memoization hidup secara spesifik hanya selama satu siklus request HTTP masuk dan otomatis dibuang saat request selesai.
3. **B** — Direktif resmi JavaScript/React untuk Server Actions adalah `"use server"`.
4. **B** — Module `"server-only"` dirancang sebagai safety-guard agar compiler memicu error jika modul I/O rahasia ter-import di file Client Component.
5. **C** — Router Cache tersimpan eksklusif di memori browser pengguna untuk menampung navigasi rute sementara.

#### Bagian B:
6. **B** — File client dikirim ke browser. Akses DB langsung akan mengekspos kredensial rahasia dan gagal dieksekusi karena browser tidak memiliki API low-level OS (socket/net).
7. **B** — Konfigurasi route segment `force-static` menuntut seluruh operasi bersifat build-time static, sehingga penggunaan fetch `no-store` menghasilkan konflik instruksi rendering yang ditolak Next.js.
8. **B** — Tag-based invalidation (`revalidateTag`) menargetkan data secara semantik lintas rute secara presisi, sangat efisien untuk katalog puluhan ribu item tanpa harus melakukan komputasi URL per halaman.
9. **A** — Bundler akan memperlakukan modul apa pun yang di-import langsung oleh file beranotasi `"use client"` sebagai bagian dari bundle client-side JS.
10. **B** — Pola *Composition Pattern*: Mengirimkan RSC melalui `props.children` ke Client Component mempertahankan eksekusi RSC tetap di server runtime, sementara Client Component hanya merender placeholder kontainernya.

#### Bagian C:
11. **Solusi Skenario 1**:
    * *Root Cause*: Menggunakan shared global state (seperti array global `const logs = []` di modul server) pada aplikasi Node.js enterprise menyebabkan memory leak karena objek tidak pernah di-garbage collect oleh V8 engine antar-request. Terlebih lagi, pada multi-pod container, array tersebut tidak sinkron antar instance pod.
    * *Fix*: Hapus global state in-memory. Alirkan log secara asynchronous menggunakan library logging terstandarisasi (misal: Winston/Pino) langsung ke stdout sebagai JSON stream untuk dikumpulkan oleh log aggregator (misal: Datadog, FluentBit, AWS CloudWatch), atau kirim ke message broker eksternal (Kafka/RabbitMQ).
12. **Solusi Skenario 2**:
    * *Root Cause*: Masalah terletak pada **Client-side Router Cache**. Meskipun `revalidatePath` di server berhasil memperbarui Full Route Cache dan Data Cache, browser client masih memegang snapshot route di memorinya sendiri selama navigasi session aktif.
    * *Fix*: Panggil `router.refresh()` dari hook `useRouter()` milik `next/navigation` segera setelah Server Action menghasilkan status sukses, atau pastikan server action mengembalikan payload baru yang diikat ke optimistic state UI client via `useOptimistic()`.
13. **Solusi Skenario 3**:
    * *Root Cause*: Waterfall eksekusi pada hierarki arsitektur Next.js. Parent Layout dieksekusi sebelum Page dieksekusi. Karena `fetchUserDataFromSlowService()` di-await langsung di root Layout tanpa boundary Suspense tersendiri, seluruh pipeline HTTP Response tertahan di Layout level selama 3000ms sebelum sempat memproses `<Suspense>` yang ada di `page.tsx`.
    * *Fix*: Hilangkan pemanggilan blocking data fetching di root `layout.tsx`. Pindahkan fetch data profil pengguna ke komponen tersendiri (`<UserProfile />`), bungkus dengan `<Suspense>` di dalam Layout, atau delegasikan pengambilan user profile ke Client Component yang membaca session cookie/token via lightweight endpoint.

---

## 16. Summary

1. **React Server Components (RSC)** mengubah paradigma performa frontend secara revolusioner: komponen server dieksekusi murni di backend dan dialirkan ke browser menggunakan format **React Flight Wire Protocol**, menghasilkan **0-byte JavaScript bundle overhead** untuk dependensi server-side.
2. Next.js App Router mengorkestrasi alur data melalui **Matrix 4-Tier Cache**: *Request Memoization* (deduplikasi request HTTP in-memory), *Data Cache* (penyimpanan lintas request persisten), *Full Route Cache* (pre-rendered HTML dan RSC payload di server), dan *Router Cache* (cache riwayat rute di memori browser).
3. **HTTP Streaming dengan Suspense Boundaries** memecahkan masalah SSR blocking klasik (TTFB latency waterfall). Shell halaman utama dikirim seketika, sementara komponen I/O berat dialirkan secara bertahap saat data siap dan dihidrasi secara terisolasi tanpa merusak interactivity halaman yang sudah ada.
4. Pada lingkungan enterprise skala besar, ketahanan sistem dijamin melalui pemisahan boundary yang disiplin: penggunaan package `server-only` untuk Data Access Layer, validasi skema ketat menggunakan Zod pada Server Actions, implementasi distributed cache lock untuk mencegah thundering herd, dan observability menggunakan OpenTelemetry.