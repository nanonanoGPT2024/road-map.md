# Paradigma Rendering: RSC, Streaming, & Partial Prerendering (PPR)

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Modul:** Next.js Enterprise Architecture
*   **Bab:** 03 — Paradigma Rendering Modern
*   **Topik:** React Server Components (RSC), HTTP Streaming, dan Partial Prerendering (PPR)
*   **Prasyarat:** Pemahaman mendalam tentang React 18/19 (Suspense, Concurrent Mode), arsitektur Client-Side Rendering (CSR) vs Traditional Server-Side Rendering (SSR), protokol HTTP/1.1 vs HTTP/2/3 multiplexing, serta lifecycle DOM hydration.
*   **Estimasi Waktu Baca/Praktik:** 120 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini secara menyeluruh, Anda diharapkan mampu:

1.  **Mendekonstruksi Protokol RSC Payload:** Menganalisis dan mengurai representasi JSON-like serialization (`RSC Wire Format`) yang dikirim dari Node.js/Edge runtime ke browser tanpa mengirimkan runtime JavaScript dependencies ke client bundle.
2.  **Mengarsitekturi Komposisi Komponen Hibrida:** Menerapkan pola `Server-First Component Architecture` dengan segregasi batas interaktivitas (`'use client'`) dan akses I/O langsung (`'use server'`) guna meminimalisasi ukuran First Load JS.
3.  **Mengimplementasikan HTTP Chunked Streaming via Suspense:** Mengonfigurasi progressive rendering multi-slot menggunakan boundaries `<Suspense>` untuk mereduksi Time to First Byte (TTFB) dan mempercepat First Contentful Paint (FCP) pada sistem terdistribusi berkepadatan data tinggi.
4.  **Mengaktifkan dan Mengoptimasi Partial Prerendering (PPR):** Menggabungkan shell layout statis instan (Edge Cache) dengan Dynamic Holes yang di-stream secara paralel dalam satu single HTTP lifecycle connection.
5.  **Mendiagnosis dan Mengeliminasi Waterfall Network:** Mengidentifikasi anti-pattern rendering sequential data fetching pada pohon komponen server dan menggantinya dengan un-awaited promises streaming architecture.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Mental Model Dua Fase (Two-Phase Execution Plane)

Dalam arsitektur React klasik (SSR Pages Router), mental model pengembang adalah **"Jalankan kode sekali di server untuk menghasilkan HTML mentah, kirim seluruh JavaScript ke klien, lalu jalankan ulang seluruh komponen di klien (Hydration)"**. Ini menghasilkan *Hydration Cost Overhead* yang linear terhadap kompleksitas halaman: semakin besar aplikasi, semakin lambat Time to Interactive (TTI).

```
Paradigma Klasik (Pages Router SSR):
Server Execution: Component Tree  ──> HTML String
Browser Execution: Component Tree + Data Fetching Code  ──> Hydration (Reconciliation)
Masalah: Kode dependensi (e.g., date-fns, lodash, markdown parser) ikut terkirim ke klien!
```

Arsitektur Modern (App Router RSC + PPR) membagi execution plane menjadi dua domain komputasi yang terisolasi secara kriptografis dan jaringan:

```
Paradigma Modern (App Router RSC + Streaming):
Server Execution Plane (RSC):
[Database / Secret Vault]
       │
   (Fetch Data)
       ▼
[Server Components] ──(Serialize to AST)──> [RSC Wire Format Stream] ──┐
                                                                       │ (HTTP/2 Stream)
Browser Execution Plane (RCC):                                         ▼
[Client Components] ◄────(Inject Virtual DOM Slots)────────────────────┘
       │
(Hydrate ONLY interactive leaves, e.g., Buttons, Inputs)
```

### Hukum Konservasi Komputasi (Rule of Zero-Bundle Execution)
Setiap baris kode server, dependensi NPM, SDK database, atau komputasi kriptografi yang diisolasi di dalam RSC memiliki **biaya byte bundle sebesar nol (0 KB)** di browser. Klien tidak pernah menerima source code dari Server Component; klien hanya menerima *instruksi struktural* (AST/JSON) tentang apa yang harus dirender dan di mana Client Component interaktif harus dipasang (*slotted*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Alur Siklus Hidup Permintaan Partial Prerendering (PPR)

Diagram di bawah ini mengilustrasikan bagaimana Edge CDN menyajikan Static Shell seketika sementara runtime server membuka pipeline HTTP Streaming paralel untuk menyuplai Dynamic Holes via Suspense.

```
Pengguna (Browser)              Edge CDN / Cache              Node.js/Edge Compute Layer      Internal Services (DB/Auth)
      │                               │                                   │                         │
      │── 1. HTTP GET /dashboard ────>│                                   │                         │
      │                               │── [Cache Hit: Static Shell]       │                         │
      │<─ 2. HTTP 200 (Stream Open)───│                                   │                         │
      │      [Kirim Pre-rendered      │                                   │                         │
      │       HTML Shell Statis]      │── 3. Invoke Dynamic Hole Router ─>│                         │
      │                               │      (Buka Background Worker)     │── 4. Query Data (Auth) ─>│
      │   (Browser me-render Shell,   │                                   │                          │
      │    animasi Skeleton aktif)    │                                   │<─ 5. Return Auth Context │
      │                               │                                   │                         │
      │                               │                                   │── 6. Query Data (Slow) ─>│
      │                               │                                   │      (e.g., Analitik)   │
      │                               │                                   │                         │
      │                               │<─ 7. Chunk 1: Dynamic Slot A ─────│                         │
      │<─ 8. Push Chunk 1 (HTML+RSC)──│      (User Profile Info Ready)    │                         │
      │   (Swap Skeleton A via DOM)   │                                   │                         │
      │                               │                                   │<─ 9. Resolusi Query DB ─│
      │                               │                                   │      (Analitik Selesai) │
      │                               │<─ 10. Chunk 2: Dynamic Slot B ────│                         │
      │<─ 11. Push Chunk 2 (HTML+RSC)─│       (Dashboard Charts Ready)    │                         │
      │   (Swap Skeleton B via DOM)   │                                   │                         │
      │                               │                                   │                         │
      │<─ 12. End of Stream (EOF) ────│───────────────────────────────────│                         │
      ▼                               ▼                                   ▼                         ▼
```

### Dekonstruksi Protokol RSC Payload (Wire Format)

Ketika Server Component dieksekusi, output-nya bukan HTML murni dan bukan pula JavaScript source code, melainkan serialized React Element tree stream:

```
M1:{"id":"./src/components/MetricCard.client.tsx","chunks":["app/page:chunk-XYZ"],"name":"MetricCard"}
S1:"react.suspense"
J0:[["$","div",null,{"className":"grid","children":[["$","$1",null,{"fallback":["$","div",null,{"className":"skeleton"}],"children":["$","@2",null,{}]}]]}]]
M2:{"id":"./src/components/ChartWrapper.client.tsx","chunks":["app/page:chunk-ABC"],"name":"ChartWrapper"}
J2:{"$@2":["$","$M2",null,{"data":[120,450,890],"metricType":"REVENUE"}]]}
```

*   **Prefix `M`:** Metadata Client Component reference (manifest chunk JavaScript klien yang harus di-download browser).
*   **Prefix `J`:** Node JSON struktural React Element (representasi Virtual DOM server).
*   **Prefix `S`:** Deklarasi batas Suspense boundary (`react.suspense`).
*   **Prefix `$`:** React Element Identifier. Simbol `@` menandakan lazy slot placeholder yang ditautkan ke chunk async berikutnya.

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Serialization Boundary & Protocol Bridge
Batas antara RSC dan Client Component disebut *Serialization Boundary*. Setiap prop yang dilewatkan dari Server Component ke Client Component **harus dapat diserialisasi (JSON-serializable)** atau bertipe spesifik yang didukung protokol React Flight:

*   **Tipe yang Didukung:** Primitives (`string`, `number`, `boolean`, `null`, `undefined`), Array, Plain Objects, `Map`, `Set`, TypedArrays, Promises, and React Elements (`JSX`).
*   **Tipe Terlarang:** Functions (kecuali dideklarasikan dengan `'use server'` sebagai Server Action), Class instances (prototype methods akan hilang), Symbols non-registry.

```
┌────────────────────────────────────────────────────────┐
│            Server Component Context (RSC)              │
│                                                        │
│  const authUser = await db.user.findFirst();           │
│  const tokenPromise = fetchSecretToken(); // Promise   │
└──────────────────────────┬─────────────────────────────┘
                           │
                 Serialization Boundary
              [React Flight Serialization]
                           │
┌──────────────────────────▼─────────────────────────────┐
│            Client Component Context (RCC)              │
│  'use client';                                         │
│                                                        │
│  export default function Profile({ authUser, token })  │
│  // authUser adalah plain deserialized object          │
│  // token dapat di-unwrap via use(tokenPromise)        │
└────────────────────────────────────────────────────────┘
```

### 2. Mekanisme Suspense & HTTP Chunked Transfer Encoding
Ketika server merender sebuah async component yang dibungkus `<Suspense fallback={<Skeleton />}>`:

1.  Engine perenderan (Flight Server Engine) memulai traversal Virtual DOM.
2.  Jika sebuah component melempar *Promise* (pending execution), server **tidak memblokir** proses rendering halaman.
3.  Server segera memancarkan (emit) fallback UI ke stream HTTP sebagai bagian dari payload awal HTML:
    ```html
    <!-- Fallback HTML dikirim seketika -->
    <div id="suspense-fallback-P:1">
       <div class="skeleton-shimmer"></div>
    </div>
    <template id="suspense-replacement-P:1"></template>
    ```
4.  Koneksi TCP HTTP tetap terbuka (`Transfer-Encoding: chunked`).
5.  Setelah Promise resolve di background, engine merender komponen aktual ke format HTML dan RSC Payload, lalu menembakkannya ke stream yang sama beserta inline script instruksi swapping:
    ```html
    <!-- Resolusi dikirim kemudian -->
    <div hidden id="suspense-content-P:1">
       <div class="real-metric-card">Rp 128.500.000</div>
    </div>
    <script>
       $RC('suspense-fallback-P:1', 'suspense-content-P:1');
    </script>
    ```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### RSC Execution Engine vs SSR Tradisional

| Karakteristik | Traditional SSR (Pages Router) | React Server Components (RSC) |
| :--- | :--- | :--- |
| **Output Eksekusi** | HTML String murni + Inline JSON Data (`__NEXT_DATA__`) | Virtual DOM Serialized Stream (`RSC Payload`) + Selective HTML |
| **Ukuran JS Bundle Klien** | Mencakup seluruh dependensi tree halaman | **Nol bytes** untuk Server Components & Server-only packages |
| **State Retention On-Nav** | Hilang saat full page refresh; butuh client router khusus | State UI Klien dipertahankan saat navigasi parsial |
| **Data Fetching Paradigm** | `getServerSideProps` / `getStaticProps` di level root | Co-located async/await langsung pada leaf component manapun |
| **Refetching Model** | Full page execution ulang atau explicit JSON fetch | Refresh subtree presisi via Server Actions / `router.refresh()` |

### Partial Prerendering (PPR) Deep Dive
PPR mengeliminasi perdebatan usang antara Static Site Generation (SSG) dan Dynamic Server-Side Rendering (SSR). Di masa lalu, jika satu modul pada dashboard memerlukan data real-time, seluruh halaman harus dideklarasikan sebagai `dynamic = 'force-dynamic'` (mengorbankan caching CDN).

PPR mengeksekusi kompilasi secara hybrid:
1.  **Build Time:** Compiler menandai static shells (layout, static headers, navigation bars) dan merendernya menjadi HTML statis permanen yang disimpan pada Edge CDN edge locations.
2.  **Runtime Request:** CDN langsung merespons dengan shell statis dalam hitungan millisecond (Edge cache hit).
3.  **Dynamic Continuation:** Edge worker secara paralel mengeksekusi asynchronous dynamic holes di background server, memancarkan data dinamis langsung ke stream koneksi klien yang terbuka tanpa *round-trip handshake* ulang.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi arsitektur multi-slot streaming yang menggabungkan async RSC, streaming boundaries, dan dynamic hole data resolution.

### Struktur Direktori:
```
src/
├── app/
│   ├── dashboard/
│   │   ├── layout.tsx
│   │   ├── loading.tsx
│   │   └── page.tsx
├── components/
│   ├── dynamic-telemetry.tsx
│   ├── financial-metrics.tsx
│   └── interactive-filter.client.tsx
└── lib/
    └── telemetry-service.ts
```

### 1. `src/lib/telemetry-service.ts` (Mock Data Layer)
```typescript
export interface SystemMetric {
  tps: number;
  memoryUsageMb: number;
  nodeHealth: 'HEALTHY' | 'DEGRADED';
}

export async function fetchSystemMetrics(): Promise<SystemMetric> {
  // Simulasi latensi I/O downstream microservice (2.5 detik)
  await new Promise((resolve) => setTimeout(resolve, 2500));
  
  return {
    tps: 14205,
    memoryUsageMb: 512.42,
    nodeHealth: 'HEALTHY',
  };
}

export async function fetchFinancialTotal(): Promise<{ revenue: number }> {
  // Simulasi query OLAP database cepat (400 ms)
  await new Promise((resolve) => setTimeout(resolve, 400));
  
  return { revenue: 4_290_120_000 };
}
```

### 2. `src/components/financial-metrics.tsx` (Fast Async RSC)
```typescript
import { fetchFinancialTotal } from '@/lib/telemetry-service';

export async function FinancialMetrics() {
  const { revenue } = await fetchFinancialTotal();

  return (
    <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
      <h3 className="text-sm font-medium text-slate-400">Total Pendapatan (Gross)</h3>
      <p className="text-2xl font-bold text-emerald-400">
        {new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(revenue)}
      </p>
    </div>
  );
}
```

### 3. `src/components/dynamic-telemetry.tsx` (Slow Async RSC)
```typescript
import { fetchSystemMetrics } from '@/lib/telemetry-service';

export async function DynamicTelemetry() {
  const data = await fetchSystemMetrics();

  return (
    <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
      <h3 className="text-sm font-medium text-slate-400">Throughput Real-time</h3>
      <div className="mt-2 flex items-center gap-4">
        <span className="text-3xl font-extrabold text-blue-500">
          {data.tps.toLocaleString()} TPS
        </span>
        <span
          className={`px-2 py-0.5 text-xs font-semibold rounded ${
            data.nodeHealth === 'HEALTHY' ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300'
          }`}
        >
          {data.nodeHealth}
        </span>
      </div>
      <p className="text-xs text-slate-500 mt-2">Alokasi Memori: {data.memoryUsageMb} MB</p>
    </div>
  );
}
```

### 4. `src/components/interactive-filter.client.tsx` (Client Component Boundary)
```typescript
'use client';

import { useState } from 'react';

interface InteractiveFilterProps {
  children: React.ReactNode;
}

export function InteractiveFilter({ children }: InteractiveFilterProps) {
  const [filterActive, setFilterActive] = useState<boolean>(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <span className="text-sm text-slate-300">Live Telemetry Pipeline</span>
        <button
          type="button"
          onClick={() => setFilterActive(!filterActive)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            filterActive ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
        >
          {filterActive ? 'Filter Aktif' : 'Semua Metrik'}
        </button>
      </div>
      <div className={filterActive ? 'opacity-90' : 'opacity-100'}>
        {/* Server component di-slot ke children tanpa merusak boundary */}
        {children}
      </div>
    </div>
  );
}
```

### 5. `src/app/dashboard/page.tsx` (RSC Composition & Multi-Stream Orchestration)
```typescript
import { Suspense } from 'react';
import { FinancialMetrics } from '@/components/financial-metrics';
import { DynamicTelemetry } from '@/components/dynamic-telemetry';
import { InteractiveFilter } from '@/components/interactive-filter.client';

export const experimental_ppr = true; // Flag Partial Prerendering Next.js

function MetricSkeleton() {
  return (
    <div className="p-4 bg-slate-900/50 border border-slate-800 rounded-lg animate-pulse">
      <div className="h-4 w-28 bg-slate-800 rounded mb-3" />
      <div className="h-8 w-44 bg-slate-800 rounded" />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <main className="p-8 max-w-7xl mx-auto space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight text-white">Dashboard Monitoring Finansial</h1>
        <p className="text-sm text-slate-400">Pipelining data hybrid RSC dengan partial prerendering.</p>
      </header>

      <InteractiveFilter>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Slot Cepat: Resolved ~400ms */}
          <Suspense fallback={<MetricSkeleton />}>
            <FinancialMetrics />
          </Suspense>

          {/* Slot Lambat: Resolved ~2500ms */}
          <Suspense fallback={<MetricSkeleton />}>
            <DynamicTelemetry />
          </Suspense>
        </div>
      </InteractiveFilter>
    </main>
  );
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Telaah Kritis `src/app/dashboard/page.tsx`
*   **Baris 6:** `export const experimental_ppr = true;`
    *   Menginstruksikan Next.js static build runner untuk memecah layout komponen ini ke format static snapshot + dynamic holes stream. Seluruh markup di luar `<Suspense>` akan langsung dipanggang (*pre-rendered*) menjadi HTML statis saat proses `next build`.
*   **Baris 24:** `<InteractiveFilter>`
    *   Komponen klien bertindak sebagai wrapper komposisional. Dengan melewatkan Server Components (`FinancialMetrics`, `DynamicTelemetry`) sebagai prop `children`, kita mencegah konversi implisit Server Components menjadi Client Components. Pola ini disebut **"Passing Server Components to Client Components as Props/Children"**.
*   **Baris 26 & 31:** `<Suspense fallback={<MetricSkeleton />}>`
    *   Mendefinisikan decoupling boundary. Mesin HTTP Streaming memecah respons TCP menjadi independent fragments. Runtime server mengeksekusi `FinancialMetrics()` dan `DynamicTelemetry()` secara paralel non-blocking (`Promise.all` semantics di level scheduler React engine).

### Telaah Kritis `src/components/interactive-filter.client.tsx`
*   **Baris 1:** `'use client';`
    *   Bukan berarti komponen ini *hanya* dieksekusi di browser. Komponen ini tetap dirender ke static HTML pada initial render (SSR), namun **masuk ke dalam manifest JavaScript client bundle** untuk proses hidrasi dan event loop listener binding (`onClick`).
*   **Baris 7-9 & 26:** `interface InteractiveFilterProps { children: React.ReactNode; }` dan `{children}`
    *   Krusial: Variabel `children` adalah output yang telah dieksekusi di server (RSC Payload Node). Client Component tidak mendownload dependensi dari children tersebut; ia hanya mengatur posisi penempatan DOM element di layout layer.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Platform: Global Multi-Tenant B2B Logistics Orchestrator ("LogiGlobal Core")

#### Konteks & Skala Masalah:
*   **Volume:** 15.000 konkurensi dispatcher aktif secara global.
*   **Permasalahan Sistem Lama:** Menggunakan Traditional SSR (`getServerSideProps`) pada dashboard pelacakan kargo.
*   **Bottleneck:** Dashboard harus memanggil 3 microservices:
    1.  Core Fleet Gateway (Latensi: 120ms)
    2.  Customs & Compliance Clearing System (Latensi downstream bervariasi: 1.8 detik – 4.5 detik akibat legacy mainframe sync)
    3.  Driver Geo-Tracking Redis Cache (Latensi: 40ms)
*   **Dampak Bisnis:** Karena arsitektur SSR lama bersifat all-or-nothing, TTFB rata-rata melonjak ke **3.8 detik**. Browser user membeku (blank screen dengan spinning loader tab bawaan browser) selama hampir 4 detik. bounce rate tim operasional lapangan mencapai 28%, memperlambat alokasi peti kemas di pelabuhan.

#### Solusi Arsitektural:
Migrasi ke Next.js App Router dengan paradigma:
1.  Layout utama dan sidebar navigasi statis dipanggang via **Partial Prerendering (PPR)** ke Edge CDN.
2.  Data Redis Driver Geo-Tracking dan Fleet Gateway dibungkus dalam fast-tier stream boundary (`<Suspense>`).
3.  Compliance Clearing System dialokasikan ke isolated low-priority stream boundary terpisah.

#### Metrik Hasil Transformasi:
*   **Time To First Byte (TTFB):** Turun drastis dari **3.800 ms** menjadi **38 ms** (Penurunan ~99% via CDN Edge Shell).
*   **First Contentful Paint (FCP):** Turun dari **3.800 ms** menjadi **110 ms**.
*   **First Load JavaScript Bundle Size:** Turun dari **480 KB** menjadi **64 KB** karena pustaka visualisasi grafik GeoJSON berukuran besar dipindahkan ke Server-Only Components.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Implementasi sistem analitik pelacakan kontainer logistik mission-critical dengan proteksi kegagalan upstream dan streaming chunked resilience.

### 1. `next.config.ts` (Aktivasi Flag PPR Modern)
```typescript
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  experimental: {
    ppr: 'incremental', // Mengaktifkan PPR modular per-route
  },
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

export default nextConfig;
```

### 2. `src/domain/cargo/types.ts`
```typescript
export interface FleetSummary {
  activeTrucks: number;
  delayedShipments: number;
  customsHoldCount: number;
}

export interface ManifestAuditLog {
  id: string;
  cargoId: string;
  verificationHash: string;
  clearedAt: string;
}
```

### 3. `src/domain/cargo/api.ts` (Enterprise Downstream Client)
```typescript
import 'server-only'; // Enforce zero-leakage ke client bundle

import { FleetSummary, ManifestAuditLog } from './types';

const LOGISTICS_UPSTREAM_URL = process.env.LOGISTICS_GATEWAY_URL || 'https://api.internal.logiglobal.net';

export async function getFleetMetrics(): Promise<FleetSummary> {
  const res = await fetch(`${LOGISTICS_UPSTREAM_URL}/v1/fleet/fast-summary`, {
    headers: {
      Authorization: `Bearer ${process.env.INTERNAL_SERVICE_KEY}`,
      'X-Origin-Node': 'Edge-RSC-Worker',
    },
    // Invalidate data tiap 60 detik (Time-based Revalidation terintegrasi Cache Next.js)
    next: { revalidate: 60, tags: ['fleet-metrics'] },
  });

  if (!res.ok) {
    throw new Error(`Gagal membaca armada: HTTP status ${res.status}`);
  }

  return res.json();
}

export async function getLegacyCustomsAudit(): Promise<ManifestAuditLog[]> {
  // Simulasi pemanggilan sistem kepabeanan legacy yang lambat dan rapuh
  const res = await fetch(`${LOGISTICS_UPSTREAM_URL}/v1/customs/legacy-audit`, {
    headers: { Authorization: `Bearer ${process.env.INTERNAL_SERVICE_KEY}` },
    // Bypass seluruh cache untuk audit real-time, murni dynamic streaming hole
    cache: 'no-store',
  });

  if (!res.ok) {
    throw new Error(`Upstream Kepabeanan Gagal: ${res.statusText}`);
  }

  return res.json();
}
```

### 4. `src/components/cargo/customs-table.tsx` (Slow Dynamic Slot with Isolated Error Boundary)
```typescript
import { getLegacyCustomsAudit } from '@/domain/cargo/api';

export async function CustomsTable() {
  let records;
  try {
    records = await getLegacyCustomsAudit();
  } catch (error) {
    // Graceful degradation di dalam stream slot itu sendiri
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-4 text-amber-400 text-sm">
        Sistem audit kepabeanan legacy sedang mengalami desinkronisasi. Menampilkan cache lokal terenkripsi.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-left text-sm text-slate-300">
        <thead className="bg-slate-900/80 text-xs uppercase text-slate-400">
          <tr>
            <th className="px-4 py-3">Audit ID</th>
            <th className="px-4 py-3">Kargo Hash ID</th>
            <th className="px-4 py-3">Timestamp Pembersihan</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-950">
          {records.map((log) => (
            <tr key={log.id} className="hover:bg-slate-900/40">
              <td className="px-4 py-3 font-mono text-xs">{log.id}</td>
              <td className="px-4 py-3 font-mono text-xs text-indigo-400">{log.cargoId}</td>
              <td className="px-4 py-3 text-slate-400">{new Date(log.clearedAt).toLocaleString('id-ID')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### 5. `src/app/operations/cargo/page.tsx` (PPR Orchestration Node)
```typescript
import { Suspense } from 'react';
import { getFleetMetrics } from '@/domain/cargo/api';
import { CustomsTable } from '@/components/cargo/customs-table';

export const experimental_ppr = true;

// Komponen metrik cepat: dipanggil langsung di root async RSC
async function FastFleetCards() {
  const fleet = await getFleetMetrics();

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
        <span className="text-xs text-slate-400 uppercase font-semibold">Truk Aktif Beroperasi</span>
        <p className="text-2xl font-bold text-white mt-1">{fleet.activeTrucks}</p>
      </div>
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
        <span className="text-xs text-slate-400 uppercase font-semibold">Pengiriman Tertunda (Delay)</span>
        <p className="text-2xl font-bold text-amber-500 mt-1">{fleet.delayedShipments}</p>
      </div>
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
        <span className="text-xs text-slate-400 uppercase font-semibold">Tertahan Otoritas Pabean</span>
        <p className="text-2xl font-bold text-rose-500 mt-1">{fleet.customsHoldCount}</p>
      </div>
    </div>
  );
}

function TableSkeletonLoader() {
  return (
    <div className="w-full space-y-2 animate-pulse">
      <div className="h-10 bg-slate-800/80 rounded w-full" />
      <div className="h-12 bg-slate-800/40 rounded w-full" />
      <div className="h-12 bg-slate-800/40 rounded w-full" />
      <div className="h-12 bg-slate-800/40 rounded w-full" />
    </div>
  );
}

export default function CargoOperationsPage() {
  return (
    <div className="p-8 space-y-8 bg-black min-h-screen text-slate-100">
      {/* BAGIAN 1: Static Shell (Instant Pre-render via Edge) */}
      <section className="flex flex-col gap-2">
        <span className="text-xs font-mono text-emerald-400 tracking-wider">SECURE DISPATCH NODE // REGION AP-SOUTHEAST-1</span>
        <h1 className="text-3xl font-extrabold text-white">Konsol Monitoring Operasional Kargo</h1>
      </section>

      {/* BAGIAN 2: Fast Tier Dynamic Stream (Tercapai dalam <150ms) */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-slate-400">Ringkasan Armada Global</h2>
        <Suspense fallback={<div className="h-20 bg-slate-900 animate-pulse rounded-xl" />}>
          <FastFleetCards />
        </Suspense>
      </section>

      {/* BAGIAN 3: Heavy Tier Dynamic Stream (Tergantung koneksi legacy) */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-400">Log Verifikasi Kliring Kepabeanan Real-Time</h2>
          <span className="text-xs text-slate-500 font-mono">Stream Id: customs-audit-stream</span>
        </div>
        <Suspense fallback={<TableSkeletonLoader />}>
          <CustomsTable />
        </Suspense>
      </section>
    </div>
  );
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Dimensi Arsitektural | Pure Client-Side Rendering (CSR) | Streaming RSC + PPR (Modern App Router) | Traditional Static Site Generation (SSG) |
| :--- | :--- | :--- | :--- |
| **First Contentful Paint (FCP)** | Sangat Lambat (Menunggu parsing bundle JS) | **Sangat Cepat** (Static Shell disajikan Edge CDN) | **Ultra Cepat** (Pre-built HTML murni) |
| **Time to Interactive (TTI)** | Lambat (JS execution berukuran masif) | **Optimal** (Hanya leaf interactive yang dihidrasi) | Instan (Jika murni tanpa interaktivitas) |
| **Beban Server Compute (CPU/RAM)** | Rendah (Hanya serving static files via CDN) | **Menengah-Tinggi** (Keep-alive TCP streaming runtime) | Nol saat runtime (Hanya build time compute) |
| **Data Freshness (Keaktualan Data)** | Real-time (Fetch langsung dari browser) | **Ultra Real-time** (Streamed per-request tanpa full SSR) | Basi/Stale (Menunggu proses re-build atau ISR) |
| **Infrastruktur Persyaratan** | Static Object Store (e.g., AWS S3, Cloudflare Pages) | **Node.js/V8 Edge Runtime** (Mendukung persistent stream) | Static CDN Cache |
| **Bundle Size Leaks Risk** | Sangat Tinggi (Mudah membocorkan helper backend) | **Nol** (Server components terisolasi secara struktural) | Nol (Build-time baked) |

---

## SEKSI 12 — EDGE CASES & PITFALLS (Failure Modes & Mitigation)

### 1. The Headless Stream Hanging (Server Zombie Request)
*   **Failure Scenario:** Salah satu microservice downstream pada async RSC mengalami network deadlock tanpa timeout. Koneksi HTTP streaming tetap terbuka tanpa mengirimkan closing chunk byte. Browser user menampilkan visual skeleton status selamanya tanpa transisi timeout.
*   **Mitigasi:** Terapkan strict timeout wrapping menggunakan `AbortController` pada setiap sub-resource request di server.

```typescript
export async function fetchWithStrictTimeout(url: