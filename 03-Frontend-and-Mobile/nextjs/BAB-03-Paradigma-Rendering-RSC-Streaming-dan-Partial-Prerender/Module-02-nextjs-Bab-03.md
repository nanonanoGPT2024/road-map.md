# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Paradigma Rendering: RSC, Streaming, dan Partial Prerender**
**Kategori: 03-Frontend-and-Mobile | Topik: Next.js Enterprise Architecture**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Internal Flight Protocol:** Membedah serialisasi data, *chunk stream*, dan format wire protocol yang dihasilkan oleh React Server Components (RSC) engine.
2. **Menguasai Streaming SSR & React Suspense:** Mengimplementasikan orkestrasi *asynchronous streaming* tingkat lanjut dengan `renderToPipeableStream` / `renderToReadableStream` untuk memangkas *Time to First Byte* (TTFB) dan mengeliminasi *waterfall bottleneck*.
3. **Mengarsitekturi Partial Prerendering (PPR):** Mengombinasikan *static shell prerendering* dengan *dynamic runtime holes* dalam satu HTTP request loop menggunakan arsitektur hybrid Next.js Canary/App Router.
4. **Menerapkan Pola Interleaving & Composition:** Menyusun hierarki komponen kompleks antara Server Components dan Client Components tanpa memicu *client boundary leak* atau de-optimasi rendering.
5. **Mitigasi Masalah Kinerja Skala Enterprise:** Mendiagnosis dan memperbaiki *serialization overhead*, *concurrency exhaustion*, dan *unintended dynamic bailouts* pada platform berskala jutaan request harian.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Fundamental Next.js App Router (Layouts, Pages, Route Handlers, Route Segments).
* Konsep React 19 / Modern primitives: React Fiber, Suspense architecture, `use`, dan Concurrent Mode.
* Standar Web Streams API (`ReadableStream`, `TransformStream`, `WritableStream`) dan mekanisme I/O non-blocking Node.js.
* Konsep protokol jaringan: HTTP/1.1 *Chunked Transfer Encoding*, HTTP/2 & HTTP/3 *Multiplexing*.
* Dasar caching bertingkat: Edge Cache, Data Cache, Full Route Cache, dan Request Memoization.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi React Server Components & Flight Wire Protocol

RSC bukan sekadar mekanisme Server-Side Rendering (SSR) konvensional. Pada SSR tradisional (Pages Router), komponen dieksekusi di server untuk menghasilkan HTML string mentah. Saat HTML mencapai browser, seluruh JavaScript bundle diunduh dan dieksekusi ulang untuk proses **Hydration**.

Pada paradigma RSC, komponen server **tidak pernah dieksekusi di browser** dan kodenya tidak pernah masuk ke dalam client bundle. Next.js App Router memanfaatkan mesin kompilasi Webpack/Turbopack yang berkolaborasi dengan React Server Compiler untuk membagi pohon dependensi menjadi dua graf:
1. **Server Module Graph:** Dieksekusi eksklusif pada runtime server (Node.js atau Edge V8 isolate).
2. **Client Module Graph:** Diberi anotasi directive `'use client'`, dikompilasi menjadi bundle JavaScript untuk interaktivitas browser.

```
                    +---------------------------+
                    | Client Request (Browser)  |
                    +-------------+-------------+
                                  |
                                  v
+-----------------------------------------------------------------+
| Next.js Server Runtime (App Router Engine)                      |
|                                                                 |
|   +---------------------------------------------------------+   |
|   | RSC Execution Pipeline                                  |   |
|   | 1. Execute Server Component async functions             |   |
|   | 2. Fetch databases / Microservices directly             |   |
|   | 3. Interleave Client Component References (Client Leaf) |   |
|   +----------------------------+----------------------------+   |
|                                |                                |
|                                v                                |
|   +---------------------------------------------------------+   |
|   | React Flight Serializer                                 |   |
|   | Emits binary/text stream: JSON-like tree + Chunk IDs    |   |
|   +----------------------------+----------------------------+   |
|                                |                                |
|        +-----------------------+-----------------------+        |
|        | (Initial Document Hit)| (SPA Transition Hit)  |        |
|        v                       v                       |        |
|   +----------+          +--------------------+         |        |
|   | SSR HTML |          | Raw Flight Stream  |         |        |
|   | Renderer |          | (text/x-component) |         |        |
|   +----+-----+          +----------+---------+         |        |
|        |                           |                   |        |
+--------|---------------------------|-------------------+--------+
         |                           |
         | Chunked HTML              | Chunked Flight Payload
         v                           v
+-----------------------------------------------------------------+
| Browser Runtime                                                 |
| 1. HTML displays immediate visual fallback                      |
| 2. React Flight Deserializer parses chunks on-the-fly           |
| 3. Suspense reconciles Fiber nodes dynamically                  |
| 4. Client Components hydrate selectively (Selective Hydration)  |
+-----------------------------------------------------------------+
```

#### Format Format Raw Flight Protocol
Ketika navigasi dinamis terjadi di sisi klien, server merespons dengan header `Content-Type: text/x-component`. Format data ini berupa stream berbasis baris (*row-based streaming representation*):

```text
M1:{"id":"./src/components/CartButton.tsx","chunks":["app/cart:client"],"name":"CartButton"}
J0:[["$","div",null,{"className":"container","children":[["$","$L1",null,{"initialCount":0}]]}]]
```

* **Tag `M` (Module Reference):** Mendefinisikan metadata Client Component yang harus dimuat oleh browser (URL chunk, export name).
* **Tag `J` (JSON Component Tree):** Representasi Virtual DOM server. Kode `$L1` merujuk pada referensi modul `M1` di atas.
* **Tag `S` (Suspense Boundary):** Menandai slot Suspense yang belum selesai dieksekusi.
* **Tag `H` (Hints):** Metadata resource preloading (misal CSS, fonts, preload scripts).

Payload ini dapat di-parse secara parsial oleh browser tanpa menunggu keseluruhan response selesai (progressive stream parsing).

### 3.2. Streaming SSR Internals: Node.js vs Edge Runtime

Rendering konvensional bersifat *monolithic*: database query yang lambat akan memblokir *TTFB* untuk seluruh halaman. Streaming SSR memecah dokumen HTML menjadi chunks menggunakan mekanisme HTTP/1.1 `Transfer-Encoding: chunked` atau stream frames pada HTTP/2 & HTTP/3.

1. **Node.js Environment:** Menggunakan `react-dom/server` API `renderToPipeableStream`. Engine ini mengaitkan output rendering dengan Node.js `WritableStream`. Alokasi memori dikendalikan oleh *backpressure mechanism* bawaan streams Node.js (`stream.write()` mengembalikan boolean untuk pause/resume rendering pipeline).
2. **Edge Environment (V8 Isolates):** Menggunakan `renderToReadableStream` berbasis standar Web API. Output-nya berupa `ReadableStream<Uint8Array>`, sangat ringan dengan jejak memori (*footprint*) minimal, ideal untuk Cloudflare Workers, Fastly Compute, atau Vercel Edge Network.

### 3.3. Partial Prerendering (PPR) Engine Internals

Partial Prerendering (PPR) adalah kulminasi dari static generation (SSG) dan server-side streaming (SSR). PPR memungkinkan satu route menyajikan:
1. **Static Shell:** Layout statis, navbar, rangka halaman, dan fallback UI yang dikompilasi secara deterministik saat *build time* (atau revalidasi ISR) dan disimpan langsung di Edge CDN cache.
2. **Dynamic Holes:** Komponen server asinkron yang dibungkus oleh `<Suspense>`. Dynamic holes ini dievaluasi secara dinamis pada saat *runtime request*, lalu di-stream melalui koneksi HTTP yang sama persis saat shell statis sedang dikirim ke browser.

```
HTTP/2 200 OK (Response Stream Starts Immediately)
------------------------------------------------------------------------
[STATIC SHELL FROM CDN CACHE] (0ms - 20ms)
<!DOCTYPE html>
<html>
  <body>
    <nav>Static Navbar</nav>
    <main>
      <!--$?-->
      <template id="B:0"></template>
      <div class="skeleton">Loading dynamic live feed...</div>
      <!--/$-->
    </main>
  </body>
</html>
------------------------------------------------------------------------
[DYNAMIC STREAMING OVER THE WIRE FROM ORIGIN] (20ms - 250ms)
<div hidden id="S:0">
  <div class="live-data">Asset: BTC/USD | Price: $96,500.21</div>
</div>
<script>
  // Dynamic runtime hole replacement by React inline runtime
  $RC = function(b, c, e) { ... };
  $RC("B:0", "S:0");
</script>
------------------------------------------------------------------------
```

Browser menerima HTML statis secara instan dari edge terdekat, lalu koneksi tetap terbuka untuk menerima *chunk replacements* yang menyuntikkan komponen dinamis ke dalam placeholder yang ditandai oleh ID Suspense (`$RC` runtime call).

---

## 4. Why & What

### Karakteristik Masalah (The Enterprise Bottlenecks)
* **Waterfall Latency:** Mengambil data di komponen klien (`useEffect`) memicu latency beruntun (*chain request*): Unduh bundle JS -> Eksekusi -> Fetch Data API -> Render UI -> Fetch Data Anak.
* **Large Bundle Size:** Memasukkan library berat (seperti parser Markdown, kalkulator kriptografi, atau SDK analitik) ke Client Components membebani alokasi memori mobile CPU dan mendegradasi metrik *Core Web Vitals* (khususnya INP & LCP).
* **Binary Dilemma (All-or-Nothing Rendering):** Developer dipaksa memilih antara SSG murni (sangat cepat, namun data rentan *stale*) atau SSR murni (selalu mutakhir, namun TTFB lambat dan membebani server).

### Solusi Paradigma Baru
RSC, Streaming, dan PPR memecahkan paradoks ini dengan memisahkan dependensi komputasi dari delivery pipeline:
* **Zero-Bundle-Size Overhead:** Modul dan dependensi yang diimpor di Server Components tidak pernah dikirim ke browser.
* **Optimized TTFB & FCP:** Shell statis disajikan dalam hitungan milidetik melalui CDN, sementara komputasi backend yang lambat diisolasi dalam *streaming chunk boundaries*.
* **Colocation of Data & Compute:** Query data berada berdampingan dengan UI komponen, menghilangkan kebutuhan layer REST/GraphQL API internal murni untuk agregasi data frontend.

---

## 5. How (Workflow Detail)

Berikut adalah siklus kompilasi dan eksekusi request pada arsitektur Next.js PPR & Streaming:

```
[ BUILD TIME ]
      │
      ├─► 1. Webpack/Turbopack mengidentifikasi directive 'use client'
      │      └─► Menghasilkan Client Manifest & Server Component Graph.
      │
      └─► 2. Next.js mengevaluasi segmen statis vs dinamis
             └─► Mengkompilasi Static Shell (HTML + RSC payload statis) ke Disk/CDN.

[ RUNTIME REQUEST ]
      │
      ├─► 1. Request masuk ke Edge Router.
      │
      ├─► 2. Edge CDN langsung menyemburkan (flush) Static Shell ke Browser (TTFB < 50ms).
      │
      ├─► 3. Bersamaan dengan itu, Edge/Origin Server mengeksekusi Dynamic Holes:
      │      ├─► Membaca Cookie, Headers, Dynamic SearchParams.
      │      └─► Menjalankan Database Query & External Fetch secara paralel.
      │
      ├─► 4. React Streaming Engine memancarkan Flight Data Chunks ke wire:
      │      ├─► Chunk payload UI terisi data dinamis.
      │      └─► Script replacement inline dikirimkan ke stream buffer.
      │
      └─► 5. Browser menerima chunks:
             ├─► React reconciler menukar fallback skeleton dengan konten final.
             └─► Client components terhidrasi secara selektif tanpa interupsi UI.
```

---

## 6. Analogy & Diagram ASCII

### Analogi Operasional: Perakitan Mobil Modular

* **SSR Tradisional:** Anda memesan mobil kustom. Pabrik merakit seluruh mobil (mesin, interior, cat) sampai 100% tuntas sebelum mengirimkannya menggunakan truk. Anda menunggu lama tanpa mendapatkan apa pun, tetapi sekali tiba, mobil langsung utuh.
* **Client-Side Rendering (CSR):** Pabrik hanya mengirim rangka kosong beserta buku manual dan jutaan suku cadang ke garasi Anda. Anda terpaksa merakitnya sendiri di rumah (menghabiskan daya baterai dan memori browser Anda).
* **RSC + Streaming + PPR:** 
  * Pabrik mengirimkan bodi eksterior dan sasis standar secara instan yang sudah jadi dari gudang terdekat (**Static Shell via CDN**). Anda langsung bisa duduk di dalamnya (**Fast FCP**).
  * Mesin berperforma tinggi yang butuh konfigurasi khusus dikirimkan lewat kurir ekspres terpisah (**Dynamic Holes**). 
  * Begitu mesin tiba beberapa saat kemudian, tim mekanik langsung memasangnya ke kompartemen mesin yang sudah disiapkan (**Suspense dynamic replacement**), tanpa perlu membongkar bodi yang sudah Anda tempati (**Selective Hydration**).

### Arsitektur Aliran Data Streaming

```
+-----------------------------------------------------------------------------+
| BROWSER RUNTIME                                                             |
|                                                                             |
| Frame 0ms: [ Static Layout / Navbar / Breadcrumb ] <---- (Instant from CDN) |
| Frame 15ms: [ Skeleton Slot: Product Info ]                                 |
| Frame 15ms: [ Skeleton Slot: Personalized Pricing ]                         |
| Frame 15ms: [ Skeleton Slot: Recommended Items ]                            |
|                                                                             |
| (Stream ongoing via HTTP/2 Multiplexed connection...)                       |
|                                                                             |
| Frame 120ms: Stream receives [Product Info Payload]                         |
|              -> React swaps Skeleton Slot 1 with real UI                    |
|                                                                             |
| Frame 230ms: Stream receives [Personalized Pricing Payload]                 |
|              -> React swaps Skeleton Slot 2 with dynamic prices             |
|                                                                             |
| Frame 450ms: Stream receives [Recommended Items + Cart Client Component]   |
|              -> React swaps Skeleton Slot 3                                 |
|              -> Executes Selective Hydration on Cart Button                 |
+-----------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Demonstrasi Suspense Streaming Sederhana

File: `app/streaming-demo/page.tsx`
```tsx
import { Suspense } from 'react';

// Server Component dengan simulasi latensi I/O backend
async function SlowMetricsComponent() {
  // Simulasi fetch microservice analitik yang memakan waktu 2.5 detik
  await new Promise((resolve) => setTimeout(resolve, 2500));
  
  const metrics = {
    activeUsers: 14205,
    qps: 3410.8,
    systemStatus: 'HEALTHY' as const,
  };

  return (
    <div style={{ padding: '1rem', border: '1px solid #10b981', borderRadius: '8px' }}>
      <h3>Realtime Telemetry (Dynamic RSC)</h3>
      <p>Active Connections: {metrics.activeUsers.toLocaleString()}</p>
      <p>Throughput: {metrics.qps} Req/sec</p>
      <p>Engine Status: {metrics.systemStatus}</p>
    </div>
  );
}

function MetricsFallback() {
  return (
    <div style={{ padding: '1rem', border: '1px dashed #6b7280', borderRadius: '8px' }}>
      <p>Memuat telemetri server secara realtime...</p>
    </div>
  );
}

export default function StreamingDemoPage() {
  return (
    <main style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Enterprise Mission Control (Static Shell)</h1>
      <p>Komponen shell ini di-stream secara instan ke browser tanpa delay.</p>
      
      {/* Dynamic boundary ditandai dengan Suspense */}
      <Suspense fallback={<MetricsFallback />}>
        <SlowMetricsComponent />
      </Suspense>
    </main>
  );
}
```

---

### 7.2. Practical Example: Production-Grade E-Commerce PDP dengan PPR

Arsitektur halaman detail produk (PDP) skala enterprise dengan spesifikasi:
* **Shell Statis:** Gambar, Metadata SEO, Spesifikasi Teknis Produk (Prerendered).
* **Hole Dinamis 1:** Pengecekan Stok Real-time dari database inventaris terdistribusi.
* **Hole Dinamis 2:** Mesin Kalkulasi Harga Terpersonalisasi berdasarkan Cookie Tier Member.
* **Client Boundary:** Tombol "Add to Cart" interaktif dengan optimistik feedback.

#### 1. Next.js Configuration (Aktifkan PPR)
File: `next.config.mjs`
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    ppr: 'incremental', // Mengaktifkan Partial Prerendering mode inkremental
  },
};

export default nextConfig;
```

#### 2. Definisi Tipe Domain
File: `types/pdp.ts`
```typescript
export interface ProductSpec {
  id: string;
  sku: string;
  title: string;
  description: string;
  specs: Record<string, string>;
}

export interface InventoryStatus {
  sku: string;
  inStock: boolean;
  availableUnits: number;
  warehouseLocation: string;
}

export interface PersonalizedPrice {
  basePrice: number;
  discountedPrice: number;
  tier: 'REGULAR' | 'GOLD' | 'PLATINUM';
  currency: string;
}
```

#### 3. Client Component Leaf: Interaktivitas Tombol Beli
File: `components/pdp/AddToCartClient.tsx`
```tsx
'use client';

import React, { useState, useTransition } from 'react';

interface AddToCartProps {
  productId: string;
  sku: string;
  disabled: boolean;
  finalPrice: number;
  currency: string;
}

export function AddToCartClient({ productId, sku, disabled, finalPrice, currency }: AddToCartProps) {
  const [isPending, startTransition] = useTransition();
  const [added, setAdded] = useState(false);

  const handleAddToCart = () => {
    startTransition(async () => {
      // Simulasi mutasi Server Action atau API endpoint call
      await new Promise((resolve) => setTimeout(resolve, 300));
      setAdded(true);
    });
  };

  return (
    <div className="flex flex-col gap-2 mt-4">
      <button
        onClick={handleAddToCart}
        disabled={disabled || isPending}
        className={`px-6 py-3 rounded-lg font-semibold transition-all ${
          disabled
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : added
            ? 'bg-emerald-600 text-white'
            : 'bg-blue-600 hover:bg-blue-700 text-white'
        }`}
      >
        {isPending
          ? 'Memproses...'
          : added
          ? 'Berhasil Ditambahkan ke Keranjang!'
          : disabled
          ? 'Stok Habis'
          : `Beli Sekarang (${currency} ${finalPrice.toLocaleString()})`}
      </button>
      {added && (
        <span className="text-xs text-emerald-600 font-medium">
          Item tersimpan di sesi keranjang Anda.
        </span>
      )}
    </div>
  );
}
```

#### 4. Dynamic Server Component: Inventaris Real-Time
File: `components/pdp/RealtimeInventory.tsx`
```tsx
import { cookies } from 'next/headers';
import { InventoryStatus } from '@/types/pdp';

// Akses dynamic functions (cookies/headers) memaksa komponen menjadi runtime dynamic hole
async function fetchInventoryFromDB(sku: string): Promise<InventoryStatus> {
  // Simulasi query DB I/O: 180ms latency
  await new Promise((resolve) => setTimeout(resolve, 180));

  // Dynamic check header/cookie tracing jika diperlukan
  const cookieStore = await cookies();
  const sessionRegion = cookieStore.get('x-user-region')?.value || 'apac-default';

  return {
    sku,
    inStock: true,
    availableUnits: 14,
    warehouseLocation: sessionRegion,
  };
}

export async function RealtimeInventory({ sku }: { sku: string }) {
  const inventory = await fetchInventoryFromDB(sku);

  return (
    <div className="p-4 bg-slate-50 border border-slate-200 rounded-md">
      <div className="flex items-center gap-2">
        <span
          className={`h-3 w-3 rounded-full ${
            inventory.inStock ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'
          }`}
        />
        <span className="text-sm font-medium text-slate-700">
          {inventory.inStock
            ? `Tersedia: ${inventory.availableUnits} unit di warehouse (${inventory.warehouseLocation})`
            : 'Stok Habis di region Anda'}
        </span>
      </div>
    </div>
  );
}
```

#### 5. Dynamic Server Component: Pricing Engine
File: `components/pdp/DynamicPricing.tsx`
```tsx
import { cookies } from 'next/headers';
import { PersonalizedPrice } from '@/types/pdp';
import { AddToCartClient } from './AddToCartClient';

async function calculateMemberPrice(productId: string): Promise<PersonalizedPrice> {
  // Komponen ini membaca cookie untuk personalisasi harga
  const cookieStore = await cookies();
  const authTier = cookieStore.get('x-member-tier')?.value;

  // I/O latency simulasi kalkulasi kompleks: 320ms
  await new Promise((resolve) => setTimeout(resolve, 320));

  let discountFactor = 1.0;
  let resolvedTier: PersonalizedPrice['tier'] = 'REGULAR';

  if (authTier === 'PLATINUM') {
    discountFactor = 0.85; // Diskon 15%
    resolvedTier = 'PLATINUM';
  } else if (authTier === 'GOLD') {
    discountFactor = 0.92; // Diskon 8%
    resolvedTier = 'GOLD';
  }

  const basePrice = 12500000;
  return {
    basePrice,
    discountedPrice: basePrice * discountFactor,
    tier: resolvedTier,
    currency: 'IDR',
  };
}

export async function DynamicPricing({ productId, sku }: { productId: string; sku: string }) {
  const price = await calculateMemberPrice(productId);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline gap-3">
        <span className="text-3xl font-extrabold text-slate-900">
          {price.currency} {price.discountedPrice.toLocaleString()}
        </span>
        {price.discountedPrice < price.basePrice && (
          <span className="text-lg text-slate-400 line-through">
            {price.currency} {price.basePrice.toLocaleString()}
          </span>
        )}
      </div>

      {price.tier !== 'REGULAR' && (
        <span className="inline-block px-2 py-1 text-xs font-semibold text-amber-800 bg-amber-100 rounded w-fit">
          Tier Member: {price.tier} Benefit Applied
        </span>
      )}

      {/* Komposisi: Client Component disarangkan ke dalam Server Component */}
      <AddToCartClient
        productId={productId}
        sku={sku}
        disabled={false}
        finalPrice={price.discountedPrice}
        currency={price.currency}
      />
    </div>
  );
}
```

#### 6. Root Page Entry: Partial Prerendering Integration
File: `app/products/[sku]/page.tsx`
```tsx
import { Suspense } from 'react';
import { RealtimeInventory } from '@/components/pdp/RealtimeInventory';
import { DynamicPricing } from '@/components/pdp/DynamicPricing';
import { ProductSpec } from '@/types/pdp';

// KUNCI: Konfigurasi PPR Eksplisit pada level segment
export const experimental_ppr = true;

// Mock Fetching Data Statis (dieksekusi saat build time via generateStaticParams)
async function getProductStaticData(sku: string): Promise<ProductSpec> {
  return {
    id: `prod_${sku}`,
    sku: sku,
    title: 'Enterprise High-Performance Server Node v4',
    description: 'Arsitektur komputasi mutakhir dengan dukungan multi-tier memory redundancy dan Edge I/O throughput tinggi.',
    specs: {
      Processor: '64-Core Custom ARM Architecture',
      Memory: '256GB ECC DDR5-6400',
      Storage: '4TB NVMe PCIe 5.0 U.2 Enterprise SSD',
      Bandwidth: 'Dual 100Gbps QSFP28 Uplink',
    },
  };
}

export async function generateStaticParams() {
  return [
    { sku: 'SRV-64C-APAC' },
    { sku: 'SRV-128C-GLOBAL' },
  ];
}

// Fallback visual sisa shell statis
function InventorySkeleton() {
  return <div className="h-12 w-full bg-slate-200 animate-pulse rounded-md" />;
}

function PricingSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="h-10 w-48 bg-slate-200 animate-pulse rounded" />
      <div className="h-12 w-full bg-slate-200 animate-pulse rounded-lg mt-4" />
    </div>
  );
}

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const resolvedParams = await params;
  const product = await getProductStaticData(resolvedParams.sku);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 grid grid-cols-1 md:grid-cols-2 gap-12">
      {/* STATIC SHELL: Prerendered ke Edge Cache */}
      <section className="flex flex-col gap-6">
        <div className="aspect-square bg-slate-100 rounded-xl flex items-center justify-center border border-slate-200">
          <span className="text-slate-400 font-mono">Render Grafis Hardware: {product.sku}</span>
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{product.title}</h1>
          <p className="mt-2 text-slate-600 leading-relaxed">{product.description}</p>
        </div>
        <div className="border-t border-slate-200 pt-4">
          <h2 className="text-lg font-semibold text-slate-700 mb-2">Spesifikasi Unit</h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {Object.entries(product.specs).map(([key, val]) => (
              <div key={key}>
                <dt className="text-slate-500">{key}</dt>
                <dd className="font-medium text-slate-900">{val}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* DYNAMIC HOLES: Dieksekusi paralel saat runtime request */}
      <section className="flex flex-col gap-6 justify-start">
        {/* Dynamic Hole 1: Inventory */}
        <Suspense fallback={<InventorySkeleton />}>
          <RealtimeInventory sku={product.sku} />
        </Suspense>

        {/* Dynamic Hole 2: Pricing & Interactive Client Boundary */}
        <Suspense fallback={<PricingSkeleton />}>
          <DynamicPricing productId={product.id} sku={product.sku} />
        </Suspense>
      </section>
    </div>
  );
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Global FinTech Multi-Asset Trading Platform
* **Konteks:** Platform analitik bursa efek dan instrumen kripto dengan 45 juta pageview/bulan.
* **Masalah Kritis Awal (Legacy Architecture - SSR Standar):**
  * Halaman Dashboard mengagregasi 12 microservice (market feeds, open order book, wallet balance, auth tier, regulatory compliance alerts).
  * Latensi service paling lambat (regulatory compliance audit) mencapai 1.8 detik. Karena SSR bersifat memblokir (*all-or-nothing*), **TTFB berada di angka 1.95 detik**. Pengguna melihat layar putih kosong selama hampir 2 detik.
  * LCP (*Largest Contentful Paint*) berada di level 3.4 detik (Audit Core Web Vitals merah / POOR).
* **Solusi Arsitektur Menggunakan Next.js PPR & Streaming:**
  1. **Layout & Global Nav:** Dikompilasi menjadi Static Shell. Disimpan pada Edge Engine CDN dengan hit ratio 99.1%.
  2. **Chart Header & Metadata:** Didefinisikan sebagai static shell segment dengan SSG/ISR (revalidate: 3600).
  3. **High-Frequency Components (Live Price Ticker & Order Book):**
     * Dibuat menjadi dynamic hole menggunakan Suspense stream.
     * Menggunakan RSC untuk server-fetch ke gRPC microservice internal berlatensi rendah.
  4. **Deep-latency Audit Component:**
     * Diisolasi dalam `Suspense` terisolasi pada tier terbawah. Data ini tidak lagi memblokir bagian viewport atas.
* **Hasil Pengukuran Produksi:**
  * **TTFB:** Turun drastis dari **1.95s** menjadi **48ms** (97.5% drop) karena Edge langsung mengembalikan static shell.
  * **FCP:** Membaik dari **2.1s** menjadi **110ms**.
  * **LCP:** Membaik dari **3.4s** menjadi **680ms** (Lolos audit Google Web Vitals kategori GOOD).
  * **Throughput Server:** Beban CPU backend turun hingga 62% karena static shell di-serve langsung tanpa menyentuh Node.js compute instance.

---

## 9. Trade-offs

| Dimensi Arsitektur | Keuntungan (Pros) | Konsekuensi & Risiko (Cons) | Biaya / Mitigasi |
| :--- | :--- | :--- | :--- |
| **PPR (Partial Prerendering)** | TTFB secepat static delivery; UI langsung render; dynamic logic tetap terisolasi. | Masih berstatus eksperimental/canary di beberapa skenario edge; dependensi arsitektur hosting tinggi (Vercel/OpenNext). | Butuh testing regresi komprehensif saat upgrade minor version; fallback infra via standard streaming. |
| **Streaming SSR via Suspense** | Mematikan bottleneck *slowest-dependency*; user engagement naik karena persepsi latency turun. | Browser connection limits; memori Node.js teralokasi lebih lama jika koneksi klien buruk (*slow loris effect*). | Terapkan connection timeout yang agresif dan perhatikan backpressure stream buffer. |
| **React Server Components (RSC)** | Bundle JS klien turun drastis (zero-bundle libraries); keamanan data terisolasi di private subnet. | Kompleksitas mental model (Client vs Server trees); Flight protocol serialization overhead pada payload masif. | Hindari passing relational payload raksasa (>500KB) melalui Flight serialization bridge. |
| **Selective Hydration** | Hanya komponen interaktif yang menghabiskan main-thread browser execution time. | Jika hierarki pohon komponen terlalu dalam, hydration order dapat menyebabkan *layout shift* (CLS) mendadak. | Wajib mendefinisikan layout skeleton dengan ukuran dimensi eksplisit (`aspect-ratio`, fixed min-height). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Unintended Dynamic Bailout (De-optimasi Menyeluruh)
* **Penyebab:** Memanggil dynamic functions seperti `cookies()`, `headers()`, atau membaca `searchParams` di level `Layout` induk teratas tanpa isolasi Suspense boundary.
* **Dampak:** Seluruh halaman, termasuk segmen yang semestinya statis, didegradasi secara paksa menjadi runtime-rendered dynamic route. PPR gagal bekerja.
* **Solusi:** Turunkan pemanggilan `cookies()` ke komponen sedalam mungkin (leaf node), dan bungkus komponen tersebut ke dalam `<Suspense>`.

### 10.2. RSC Data Fetching Waterfall
* **Penyebab:**
  ```tsx
  // ANTI-PATTERN: Serial Waterfall di Server Component
  const user = await fetchUser(); // Butuh 200ms
  const projects = await fetchProjects(user.id); // Butuh 300ms (Total: 500ms blocking)
  ```
* **Solusi:**
  Gunakan pemanggilan paralel via `Promise.all` jika data tidak saling bergantung, atau pecah menjadi dua komponen server terpisah dengan masing-masing Suspense boundary.
  ```tsx
  // OPTIMAL PATTERN: Parallel Data Fetching via Suspense Composition
  <Suspense fallback={<UserSkeleton />}>
    <UserProfile />
  </Suspense>
  <Suspense fallback={<ProjectsSkeleton />}>
    <ProjectsList />
  </Suspense>
  ```

### 10.3. Client Boundary Leakage (Racun Serialization)
* **Penyebab:** Mengirim objek kompleks yang mengandung fungsi, class instances, circular references, atau simbol dari Server Component ke Client Component.
* **Error:** `Error: Only plain objects, and a few built-in classes, can be passed to Client Components from Server Components. Classes or methods are not supported.`
* **Solusi:** Pastikan boundary interface berupa DTO (Data Transfer Object) murni yang *JSON-serializable*. Lakukan transformasi instance kelas (misal: Date instances, Decimal.js) menjadi format ISO string atau primitive numbers sebelum disalurkan sebagai props.

### 10.4. Hydration Mismatch Akibat Injeksi State Runtime Acak
* **Penyebab:** Menggunakan `Math.random()`, `Date.now()`, atau `window.matchMedia` yang menghasilkan nilai berbeda antara execution time di server vs rehydration time di client.
* **Solusi:** Gunakan `useId()` untuk identifikasi elemen yang stabil antar-environment. Sinkronkan waktu menggunakan timestamp seragam yang disuplai dari server via props.

---

## 11. Best Practices (Production Checklist)

- [ ] **Directive Explicit Isolation:** Pastikan `'use client'` hanya ditaruh di level daun (*leaf components*), bukan di layout utama atau page entry wrapper.
- [ ] **PPR Flag Activation:** Verifikasi `experimental: { ppr: 'incremental' }` pada `next.config.mjs` dan export `export const experimental_ppr = true` pada segmen target.
- [ ] **Strict Typing Context Props:** Validasi bahwa seluruh props yang melintasi *Flight serialization barrier* bersifat serializable (`type Primitive = string | number | boolean | null | undefined | Array<Primitive> | { [key: string]: Primitive }`).
- [ ] **Sizing Fallbacks untuk Mencegah CLS:** Selalu berikan ukuran `height`, `min-height`, atau `aspect-ratio` pada komponen Skeleton Fallback untuk menjamin nilai CLS (*Cumulative Layout Shift*) < 0.1.
- [ ] **Segment Parallelization:** Pecah data-fetching masif menjadi granular components dengan Suspense independen daripada satu mega-query di tingkat halaman.
- [ ] **Secure Secret Encapsulation:** Pastikan credentials, database strings, dan private API keys hanya diakses di RSC, serta pastikan package `server-only` diimpor di layer service untuk mencegah data terekspos ke bundle browser.
- [ ] **Error Boundary Isolation:** Tempatkan `error.tsx` pada tingkat segmen untuk menangani kegagalan streaming secara elegan tanpa menumbangkan seluruh halaman.
- [ ] **Logging & Telemetry Tracing:** Pantau metric *Server Timing Header* (`Server-Timing: edge;desc="PPR Shell";dur=12, rsc;desc="Dynamic Holes";dur=140`) untuk visibilitas pipeline per segmen.

---

## 12. Hands-on Practice

Implementasikan struktur micro-streaming enterprise berikut pada workspace proyek Anda:

### Struktur Direktori Hands-on
```
hands-on/m02/
├── next.config.mjs
├── package.json
├── tsconfig.json
└── app/
    ├── layout.tsx
    ├── globals.css
    └── telemetry/
        ├── page.tsx
        ├── error.tsx
        └── components/
            ├── TelemetryStaticShell.tsx
            ├── CoreMetricsStream.tsx
            ├── GeoNodeDistribution.tsx
            └── InteractiveFilter.tsx
```

### Langkah 1: Inisialisasi dan Konfigurasi Next.js
Simpan di `hands-on/m02/next.config.mjs`:
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    ppr: 'incremental',
  },
};

export default nextConfig;
```

### Langkah 2: Layout Utama
Simpan di `hands-on/m02/app/layout.tsx`:
```tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Enterprise Telemetry Hub',
  description: 'Mission-critical distributed telemetry monitoring system',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body className="bg-slate-950 text-slate-100 antialiased min-h-screen">
        <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 bg-cyan-500 rounded" />
            <span className="font-bold tracking-wider text-sm">TELEMETRY::OPS</span>
          </div>
          <span className="text-xs font-mono text-slate-400">PPR ARCHITECTURE RUNTIME</span>
        </header>
        {children}
      </body>
    </html>
  );
}
```

### Langkah 3: Client Component untuk Kontrol Interaktif
Simpan di `hands-on/m02/app/telemetry/components/InteractiveFilter.tsx`:
```tsx
'use client';

import { useState } from 'react';

export function InteractiveFilter() {
  const [selectedInterval, setSelectedInterval] = useState('1m');

  return (
    <div className="flex items-center gap-2 bg-slate-900 p-1 rounded-lg border border-slate-800">
      {['30s', '1m', '5m', '15m'].map((interval) => (
        <button
          key={interval}
          onClick={() => setSelectedInterval(interval)}
          className={`px-3 py-1 text-xs rounded font-medium transition-all ${
            selectedInterval === interval
              ? 'bg-cyan-600 text-white shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          {interval}
        </button>
      ))}
    </div>
  );
}
```

### Langkah 4: Dynamic Hole Components dengan Variasi Latensi
Simpan di `hands-on/m02/app/telemetry/components/CoreMetricsStream.tsx`:
```tsx
import 'server-only';

async function getCoreMetrics() {
  // Simulasi query backend 400ms
  await new Promise((res) => setTimeout(res, 400));
  return {
    rps: 42109,
    p99Latency: 4.2,
    errorRate: 0.0012,
  };
}

export async function CoreMetricsStream() {
  const metrics = await getCoreMetrics();

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
        <p className="text-xs text-slate-400 font-mono">REQUESTS / SEC</p>
        <p className="text-2xl font-bold text-cyan-400 mt-1">{metrics.rps.toLocaleString()}</p>
      </div>
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
        <p className="text-xs text-slate-400 font-mono">P99 LATENCY</p>
        <p className="text-2xl font-bold text-emerald-400 mt-1">{metrics.p99Latency} ms</p>
      </div>
      <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
        <p className="text-xs text-slate-400 font-mono">ERROR RATE</p>
        <p className="text-2xl font-bold text-amber-400 mt-1">{(metrics.errorRate * 100).toFixed(3)}%</p>
      </div>
    </div>
  );
}
```

Simpan di `hands-on/m02/app/telemetry/components/GeoNodeDistribution.tsx`:
```tsx
import 'server-only';

async function getGeoNodes() {
  // Simulasi microservice lambat 1200ms
  await new Promise((res) => setTimeout(res, 1200));
  return [
    { region: 'ap-southeast-1', nodes: 142, health: 'OPTIMAL' },
    { region: 'us-east-1', nodes: 380, health: 'OPTIMAL' },
    { region: 'eu-west-1', nodes: 210, health: 'DEGRADED' },
  ];
}

export async function GeoNodeDistribution() {
  const nodes = await getGeoNodes();

  return (
    <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
      <h3 className="text-sm font-semibold mb-3 text-slate-300">Edge Node Cluster Telemetry</h3>
      <div className="space-y-2">
        {nodes.map((node) => (
          <div key={node.region} className="flex justify-between items-center text-xs font-mono border-b border-slate-800/60 pb-2">
            <span>{node.region}</span>
            <span className="text-slate-400">{node.nodes} instances</span>
            <span className={node.health === 'OPTIMAL' ? 'text-emerald-400' : 'text-amber-400'}>
              {node.health}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Langkah 5: Halaman Terintegrasi PPR
Simpan di `hands-on/m02/app/telemetry/page.tsx`:
```tsx
import { Suspense } from 'react';
import { CoreMetricsStream } from './components/CoreMetricsStream';
import { GeoNodeDistribution } from './components/GeoNodeDistribution';
import { InteractiveFilter } from './components/InteractiveFilter';

export const experimental_ppr = true;

function SkeletonLoader({ height }: { height: string }) {
  return <div className={`w-full ${height} bg-slate-800/50 animate-pulse rounded-lg`} />;
}

export default function TelemetryDashboardPage() {
  return (
    <main className="p-8 max-w-7xl mx-auto space-y-6">
      {/* STATIC SHELL */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Global Ingestion Infrastructure</h1>
          <p className="text-xs text-slate-400">Streamed from Multi-Region Isolates</p>
        </div>
        <InteractiveFilter />
      </div>

      {/* DYNAMIC HOLE 1 (Fast Stream: 400ms) */}
      <section>
        <Suspense fallback={<SkeletonLoader height="h-24" />}>
          <CoreMetricsStream />
        </Suspense>
      </section>

      {/* DYNAMIC HOLE 2 (Slow Stream: 1200ms) */}
      <section>
        <Suspense fallback={<SkeletonLoader height="h-44" />}>
          <GeoNodeDistribution />
        </Suspense>
      </section>
    </main>
  );
}
```

### Langkah 6: Jalankan dan Verifikasi
Eksekusi di terminal:
```bash
npm run build
npm run start
```
Buka Browser Network DevTools pada tab **Waterfall**:
1. Amati bahwa dokumen HTML awal memiliki timing **TTFB < 50ms**.
2. Perhatikan stream baris HTML tetap berstatus *pending transfer* hingga frame 1200ms berakhir.
3. Fallback skeleton ditukar secara transparan di DOM tanpa interupsi rendering filter interaktif.

---

## 13. Exercise

### Latihan 1 (Tingkat: Easy)
Buat Server Component `ServerTimeTicker` yang me-render waktu saat ini dalam format timestamp millisecond dengan artificial delay 500ms. Bungkus komponen ini dalam `<Suspense>` di halaman statis dan verifikasi bahwa teks "Memuat Sinkronisasi Waktu..." muncul sebelum angka timestamp ditampilkan.

### Latihan 2 (Tingkat: Medium)
Refaktor sebuah halaman profil pengguna yang memiliki dua dependensi asinkron:
1. `fetchUserProfile()` (Database I/O cepat: 100ms)
2. `fetchUserFinancialHistory()` (Legacy ERP I/O lambat: 2000ms)

Implementasikan arsitektur Streaming di mana kartu profil user dirender seketika tanpa harus menunggu riwayat transaksi finansial selesai dimuat.

### Latihan 3 (Tingkat: Hard)
Bangun arsitektur nested streaming dengan 3-tier Suspense hierarchy:
* Segmen A (Data Global Header, target: 50ms)
* Segmen B (Hierarchical Content Tree, target: 350ms)
* Segmen C (Deep Predictive Analytics, target: 1500ms)

Pastikan bahwa jika Segmen C melempar Exception (*Database Timeout*), komponen error boundary lokal menangkap kegagalan tersebut dan menampilkan pesan fallback tanpa merusak (*unmount*) Segmen A dan Segmen B yang sudah sukses ditampilkan ke layar.

---

## 14. Challenge

Rancang arsitektur halaman analitik multi-tenant B2B dengan kriteria:
1. **Hybrid Security & Zero Leak:** Tenant ID di-parse secara aman dari subdomain via `headers()` di server edge tanpa membocorkan identifier customer ke static shell bundle.
2. **PPR Performance:** Static dashboard shell (sidebar, navigation, theme container) wajib ter-cache di CDN secara global.
3. **Dynamic Parallelization:** 4 widget performa database tenant dimuat secara independen. Tiga widget harus di-stream secara paralel, dan widget keempat wajib memanfaatkan Dynamic Data Stream dari Webhook eksternal.
4. **Resilience Test:** Simulasikan lonjakan beban traffic (*simulated high network latency*) dan tunjukkan via diagram urutan alur data bagaimana Partial Prerendering menjamin UI responsiveness bagi user meskipun database backend tenant sedang terdegradasi.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan paling fundamental antara output dari SSR tradisional dengan React Server Components (RSC)?**
   * *Jawaban:* SSR tradisional mengeksekusi kode di server untuk menghasilkan string HTML murni yang kemudian membutuhkan proses *Full Hydration* dengan JavaScript bundle di browser. RSC menghasilkan stream Flight Protocol (serialisasi representasi virtual DOM) yang kodenya tidak pernah dikirim ke browser, menghilangkan *client bundle footprint* untuk dependensi server.
2. **Bagaimana format data Flight Protocol dikirimkan melalui jaringan?**
   * *Jawaban:* Dikirimkan sebagai data *row-based streaming representation* berbasis text (`text/x-component`) dengan ID modul, referensi JSON Virtual DOM, serta tag batas suspense yang di-parse browser secara progresif.
3. **Apakah library pihak ketiga yang di-import dalam Server Component otomatis menambah ukuran JavaScript bundle di browser?**
   * *Jawaban:* Tidak. Library yang di-import di Server Component tetap berada di server dan dieksekusi di server runtime; hanya hasil representasi datanya yang dikirim ke klien.
4. **Apa fungsi dari directive `'use client'`?**
   * *Jawaban:* Directive `'use client'` menandai batasan (*boundary*) antara modul Server Component dengan Client Component graph, menginstruksikan bundler untuk menyertakan file tersebut beserta anak dependensinya ke dalam JavaScript bundle klien.
5. **Bagaimana Suspense boundary menentukan komponen mana yang harus di-stream secara bertahap?**
   * *Jawaban:* Suspense mendeteksi komponen turunan yang melempar *Promise* (pending asynchronous operation). React akan memancarkan UI fallback terlebih dahulu, lalu menggantinya saat Promise resolve melalui streaming chunk.

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Mengapa pemanggilan fungsi `cookies()` atau `headers()` pada root layout dapat menggagalkan optimasi Partial Prerendering (PPR)?**
   * *Jawaban:* Memanggil dynamic functions di root layout menandai seluruh pohon segmen di bawahnya sebagai dinamis pada level paling tinggi, sehingga proses *static prerender phase* tidak dapat mengekstrak shell statis yang stabil.
7. **Bagaimana React menangani proses rehydration jika terjadi streaming chunk delay pada sebagian elemen halaman?**
   * *Jawaban:* Melalui konsep *Selective Hydration*. React menghidrasi bagian DOM statis dan komponen interaktif yang sudah selesai tiba di browser secara terpisah, tanpa harus menunggu seluruh streaming payload Suspense yang lambat selesai dimuat.
8. **Jelaskan peran runtime function `$RC` (atau inline runtime hydration script) dalam Streaming SSR!**
   * *Jawaban:* `$RC` adalah inline script ringan buatan React yang disuntikkan ke dalam HTML stream untuk menukar placeholder template fallback (`<template id="B:x">`) dengan konten HTML sebenarnya (`<div hidden id="S:x">`) secara real-time di DOM browser segera setelah chunk tersebut mendarat.
9. **Apa implikasi performa dari melewatkan props berukuran besar (misal array 10.000 records) dari Server Component ke Client Component?**
   * *Jawaban:* Menyebabkan pembengkakan ukuran Flight Protocol payload secara drastis, membebani CPU server saat serialisasi data, membebani bandwidth jaringan, serta memakan waktu CPU browser untuk deserialisasi JSON virtual DOM.
10. **Bagaimana cara mencegah modul yang mengandung private secret/logic ter-import secara tidak sengaja ke Client Component?**
    * *Jawaban:* Menggunakan package `import 'server-only'` di bagian paling atas modul. Jika file tersebut secara sengaja atau tidak sengaja di-import oleh file bertanda `'use client'`, kompilator Next.js/Turbopack akan melempar error saat build time.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario Kasus A:**
    Sebuah aplikasi portal berita mengalami lonjakan traffic masif. Metrik Core Web Vitals menunjukkan nilai TTFB 1.8 detik dan CLS (Cumulative Layout Shift) 0.35. Setelah diinvestigasi, halaman menggunakan SSR dinamis penuh karena membaca parameter tracking query string di tingkat layout utama, dan fallback Suspense-nya berupa div kosong tanpa styling ukuran.
    *Tindakan arsitektural apa yang wajib dilakukan untuk memangkas TTFB ke < 100ms dan CLS ke < 0.05?*
    * *Solusi:* 
      1. Pindahkan pembacaan search parameters dari root layout ke leaf component spesifik yang dibungkus oleh `<Suspense>`.
      2. Aktifkan Partial Prerendering (PPR) agar Layout, Navbar, dan Shell Artikel menjadi statis dan di-serve dari Edge CDN (memangkas TTFB ke < 100ms).
      3. Ganti fallback Suspense kosong dengan Skeleton Loader yang memiliki rasio tinggi/lebar (`aspect-ratio` atau min-height fixed) yang identik dengan elemen aslinya untuk mengeliminasi Layout Shift (CLS < 0.05).

12. **Skenario Kasus B:**
    Sebuah Server Action/Dynamic Component mengambil data dari REST microservice pihak ketiga yang terkadang lambat merespons hingga 8 detik. Selama periode ini, koneksi streaming browser tetap berstatus *pending*, dan setelah batas waktu tertentu koneksi terputus dengan error *Gateway Timeout* dari reverse proxy NGINX.
    *Bagaimana merancang arsitektur isolasi kegagalan pada skenario streaming ini?*
    * *Solusi:*
      1. Terapkan `AbortController` dengan timeout maksimal (misal: 2.5 detik) pada pemanggilan fetch microservice pihak ketiga.
      2. Bungkus komponen RSC tersebut dengan dedicated `<Suspense>` dan `<ErrorBoundary>` (atau file `error.tsx`).
      3. Sediakan strategi fallback bertingkat: jika fetch timeout, server component menangkap error dan mengembalikan data cache sekunder (stale cache) atau UI alternatif, mencegah koneksi HTTP menggantung melewati limit NGINX timeout.

13. **Skenario Kasus C:**
    Platform FinTech Anda mendistribusikan aplikasi secara global melalui multi-region edge deployment. Anda mengaktifkan PPR, tetapi mendapati bahwa pengguna di region Eropa menerima shell harga dalam mata uang USD yang merupakan default region saat build time.
    *Mengapa hal ini terjadi dan bagaimana memperbaikinya secara benar dalam paradigma PPR?*
    * *Solusi:*
      * Penyebab: Komponen mata uang ikut ter-prerender ke dalam Static Shell saat build time tanpa dibungkus dalam dynamic hole Suspense boundary.
      * Perbaikan: Ekstrak komponen penampil harga dan mata uang ke dalam Server Component terpisah yang membaca cookie/header region user via `headers()` / `cookies()`. Bungkus komponen ini di dalam `<Suspense fallback={<PriceCurrencySkeleton />}>`. Dengan demikian, shell statis tetap bersifat agnostik-region, sedangkan konversi mata uang di-stream secara dinamis sesuai asal request klien.

---

## 16. Summary

```
                      PARADIGMA RENDERING MODERN (RSC + STREAMING + PPR)
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                        │
  │   1. REACT SERVER COMPONENTS (RSC)                                                     │
  │      • Komputasi di server runtime; 0kb client JS payload impact.                     │
  │      • Direct access ke backend resources (DB, internal microservices).                │
  │      • Serialisasi pohon virtual DOM via Flight Protocol.                              │
  │                                                                                        │
  │   2. STREAMING SSR DENGAN SUSPENSE                                                    │
  │      • Eliminasi bottleneck rendering berbasis all-or-nothing.                         │
  │      • Flush HTML parsial instan melalui HTTP Chunked Transfer Encoding.               │
  │      • Selective Hydration memprioritaskan komponen interaktif yang terlihat duluan.    │
  │                                                                                        │
  │   3. PARTIAL PRERENDERING (PPR)                                                        │
  │      • Penyatuan elegan antara Static Site Generation (SSG) & Dynamic Streaming (SSR). │
  │      • Static Shell dikirim langsung dari Edge Cache (<50ms).                         │
  │      • Dynamic Holes dieksekusi paralel saat runtime dan disuntikkan ke stream.       │
  │                                                                                        │
  └────────────────────────────────────────────────────────────────────────────────────────┘
```

Penerapan kombinasi paradigma **RSC, Streaming, dan Partial Prerendering** menggeser batas performa aplikasi web modern. Dengan mengisolasi bagian dinamis di dalam batas Suspense dan membiarkan rangka statis terdistribusi di Edge CDN terdekat, rekayasa arsitektur perangkat lunak Next.js di level enterprise mampu mencapai metrik performa ekstrem: TTFB setara situs statis murni tanpa mengorbankan dinamika personalisasi data berskala masif.