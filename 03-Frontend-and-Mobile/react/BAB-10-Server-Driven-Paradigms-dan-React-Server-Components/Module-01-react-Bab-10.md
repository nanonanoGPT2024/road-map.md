# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Utama:** React
*   **Bab 10:** Modern Architecture & Next-Gen Paradigms
*   **Modul 01:** Server-Driven Paradigms & React Server Components (RSC)
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat Konseptual:** 
    *   Siklus hidup React (Mounting, Reconciliation, Commit)
    *   Arsitektur Server-Side Rendering (SSR) Klasik vs Single Page Applications (SPA)
    *   Node.js Streams API & Transfer Encoding Chunked HTTP/1.1 & HTTP/2
    *   Bundling primitives (Webpack Module Federation, Rollup/ESBuild dynamic imports)
*   **Estimasi Waktu Penyelesaian:** 120 - 180 Menit

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda ditargetkan untuk dapat:

1.  **Mendekonstruksi Paradigma RSC vs SSR Klasik:** Membedakan secara fundamental eksekusi SSR (HTML generation) dengan RSC (React Element Tree serialisasi melalui payload format streaming biner/teks khusus) tanpa ambiguitas terminologi.
2.  **Menganalisis Protokol Wire RSC:** Mengurai format streaming `react-server-dom` (ID chunks, model data, references) hingga level parser byte, serta memahami cara browser merekonstruksi Fiber Tree secara inkremental.
3.  **Mengarsitekturi Komposisi Server-Client Boundary:** Menerapkan batasan pemisahan modular (*Server-Client boundary*) menggunakan direktif `'use client'` dan `'use server'` tanpa menyebabkan kebocoran bundle (*bundle leakage*) atau kegagalan serialisasi props.
4.  **Mencegah dan Menanggulangi Poisoning Vektor:** Mengisolasi dependensi internal server via `server-only` untuk menggagalkan eksfiltrasi rahasia (*environment variables*, koneksi basis data langsung, private keys).
5.  **Mengoptimasi TTFB dan INP Skala Enterprise:** Mendesain strategi data-fetching berbasis multi-slot Suspense Streaming guna memangkas *Time to First Byte* (TTFB) dan menjaga ketersediaan thread utama (*Main Thread availability*) untuk interaksi pengguna (*Interaction to Next Paint* - INP).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: "Code on the Server, UI on the Client" Menuju "Unified Heterogeneous Component Graph"

Secara historis, mental model aplikasi web modern terfragmentasi menjadi dua kutub:
1.  **Pure SPA:** Server hanyalah penyedia REST/GraphQL JSON API tanpa *state* tampilan. Klien mengunduh bundel JavaScript masif, mengeksekusi komputasi, lalu merender DOM. Kelemahan: *Waterfalls network request*, ukuran bundel membengkak secara linier mengikuti fitur.
2.  **Classic SSR:** Server mengeksekusi pohon komponen menjadi string HTML mentah. Browser menerima HTML langsung, namun seluruh pohon komponen harus diunduh ulang sebagai bundel JavaScript untuk proses **Hydration** (menautkan event listener ke DOM statis). Kelemahan: Eksekusi komputasi ganda (*double-pass compute*) dan ukuran JS tetap besar.

```
MENTAL MODEL LAMA (SSR):
[Server] -> Render JSX to HTML String ------------------------> [Browser]
            Render JS Bundle (All Components) --------------> [Hydration: Bind Event Listeners]

MENTAL MODEL RSC:
[Server] -> Eksekusi Server Components -> Streaming RSC Payload -> [Browser]
            (Zero Bundle Size Impact)                              Integrasikan ke DOM
         -> Eksekusi Client Components -> Unduh JS Khusus Client -> Hydrate HANYA Client Leaf Nodes
```

RSC memperkenalkan paradigma **Heterogeneous Component Graph**:
Pohon komponen React kini terbelah menjadi dua dimensi runtime yang hidup berdampingan. **Server Components HANYA berjalan di server**. Komponen ini tidak pernah di-bundle ke browser, tidak pernah di-hydrate, tidak memiliki siklus hidup UI berbasis event pengguna (`useState`, `useEffect`), namun memiliki akses sinkron/asinkron tanpa batas ke *data source* backend (Database, Filesystem, Private Microservices). 

Sementara itu, **Client Components** bertindak sebagai *interactive islands* atau daun (*leaf nodes*) dalam pohon UI yang dieksekusi di server untuk HTML awal, kemudian di-hydrate secara selektif di browser. 

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram aliran eksekusi data dan kompilasi modul yang menggambarkan siklus hidup dari request browser hingga rekonsiliasi DOM melalui streaming protokol RSC.

```
+-------------------------------------------------------------------------------------------------------+
|                                  BROWSER / RUNTIME ENVIRONMENT                                        |
+-------------------------------------------------------------------------------------------------------+
    |                                                                                               ^
    | 1. HTTP Request (Navigation / Action)                                                         |
    v                                                                                               |
+---------------------------------------------------------------------------------------------------|---+
|                                 EDGE / NODE.JS RUNTIME ENGINE                                     |   |
|                                                                                                   |   |
|  +---------------------------------------------------------------------------------------------+  |   |
|  | REACT COMPONENT GRAPH EXECUTION PIPELINE                                                    |  |   |
|  |                                                                                             |  |   |
|  |  [Root Layout (Server)]                                                                     |  |   |
|  |         |                                                                                   |  |   |
|  |         +---> Direct DB Access (e.g. pg / Prisma) ===> Await I/O Query                      |  |   |
|  |         |                                                                                   |  |   |
|  |         v                                                                                   |  |   |
|  |  [ProductDetail (Server)]                                                                   |  |   |
|  |         |                                                                                   |  |   |
|  |         +---> <Suspense fallback={<Skeleton />}>                                            |  |   |
|  |                    |                                                                        |  |   |
|  |                    +---> [Reviews (Async Server)] ===> Slow I/O Streaming Wait              |  |   |
|  |                    |                                                                        |  |   |
|  |                    v                                                                        |  |   |
|  |         +--- [AddToCartButton ('use client')]                                               |  |   |
|  +---------|-----------------------------------------------------------------------------------+  |   |
|            |                                                                                      |   |
|            v                                                                                      |   |
|  +---------------------------+       +------------------------------------+                       |   |
|  | Server Serializer Engine  |       | Client Component Bundler Manifest  |                       |   |
|  | (react-server-dom-webpack)|       | (Webpack / Turbopack Metadata)     |                       |   |
|  +---------------------------+       +------------------------------------+                       |   |
|            |                                           |                                          |   |
|            | 2. Serialize Server Tree to Stream        | Resolusi Module ID & File URL            |   |
|            |    Replace Client Comp with $L markers    |                                          |   |
|            v                                           v                                          |   |
|  +------------------------------------------------------------------------+                       |   |
|  | RSC STREAMING PAYLOAD ENCODER (Chunked HTTP Output)                    |                       |   |
|  | Format:                                                                |                       |   |
|  | 0:{"$@":["$L1"]}                                                       |                       |   |
|  | 1:I{"id":"./src/Button.client.tsx","chunks":["client1"],"name":"default"} |                   |   |
|  | 0:{"title":"GPU NVidia","action":"$L1"}                               |                       |   |
|  +------------------------------------------------------------------------+                       |   |
+---------------------------------------------------------------------------------------------------|---+
    |                                                                                               |
    | 3. Progressive HTTP Stream (Chunks transmitted over wire)                                     |
    v                                                                                               |
+---------------------------------------------------------------------------------------------------|---+
|                                  BROWSER RUNTIME PARSER & RECONCILER                              |   |
|                                                                                                   |   |
|  +-------------------------------------+      +------------------------------------------------+  |   |
|  | RSC Stream Reader / Deserializer    | ===> | React Fiber Reconciler                         |  |   |
|  | Parser reads payload chunks on-fly  |      | Dynamic reconciliation without destroying state|  |   |
|  +-------------------------------------+      +------------------------------------------------+  |   |
|                   |                                                  |                            |   |
|                   | Perlu Client Asset?                              v                            |   |
|                   +-------------------------> [ Fetch JS Chunks ] -> Hydrate Interactive Leaf Node|
+-------------------------------------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Wire Format `react-server-dom`
Ketika server memproses Server Component, ia tidak menghasilkan HTML (kecuali digabung dengan pipeline SSR tradisional), melainkan format serialisasi JSON khusus berorientasi baris/stream. 

Format ini menggunakan tag representasional:
*   `M`: Menandakan definisi modul Client Component. Berisi ID modul, path chunk, dan nama ekspor.
*   `J`: Menandakan pohon elemen JSON/React. Berisi struktur komponen, props, dan penanda referensi.
*   `S`: Menandakan Suspense Boundary symbol. Digunakan untuk instruksi fallback dan streaming resolve.
*   `E`: Menandakan error chunk jika terjadi uncaught exception di thread server.

Contoh manifest decoding:
```text
M1:{"id":"./src/AddToCartButton.tsx","chunks":["client-app.js"],"name":"AddToCartButton"}
J0:["$","div",null,{"className":"container","children":[["$","h1",null,{"children":"Enterprise Server"}],["$","$L1",null,{"sku":"SKU-9921"}]]}]
```
*Analisis Anatomi:*
1.  Baris `M1` meregistrasikan bahwa referensi `$L1` diisi oleh Client Component dari file chunk `./src/AddToCartButton.tsx`.
2.  Baris `J0` mendefinisikan layout UI: Tag `div` membungkus `h1` dan sebuah slot referensi `$L1`. Perhatikan bahwa props `{ sku: "SKU-9921" }` diserialisasikan langsung ke argumen Client Component. 

### 2. The Flight Client & Deserializer Engine
Di sisi peramban, *Flight Client Runtime* mengonsumsi `ReadableStream` dari respons fetch. Alih-alih menunggu respons selesai (`EOF`), parser mengeksekusi metode streaming:
*   Setiap kali satu baris chunk terurai, *Flight Client* membuat *Promise* internal yang segera di-*resolve*.
*   Reconciler React menempatkan elemen UI ke dalam Fiber Tree secara inkremental.
*   State komponen klien di sekitarnya **tidak pernah hilang (*preserved*)** selama navigasi RSC baru masuk, karena proses ini memperlakukan pembaruan sebagai *Virtual DOM update*, bukan *hard document refresh*.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Batasan Serialisasi (The Serialization Boundary)
Salah satu hukum absolut RSC adalah: **Setiap data yang dilewatkan dari Server Component ke Client Component melalui props WAJIB dapat diserialisasi (*JSON-serializable*)**, ditambah beberapa tipe data yang didukung oleh protokol Flight.

| Tipe Data | Diizinkan Lewat Batas Server -> Client? | Catatan Teknis / Mekanisme |
| :--- | :--- | :--- |
| `string`, `number`, `boolean`, `null`, `undefined` | **YA** | Tipe primitif standar, diserialisasi langsung. |
| Plain Objects, Arrays | **YA** | Rekursif dipetakan ke representasi JSON. |
| `Date` | **YA** | Dikonversi via ISO string lalu direkonstruksi oleh Flight Parser. |
| `Map`, `Set` | **YA** | Didukung pada spesifikasi modern RSC Flight Protocol. |
| `TypedArray`, `ArrayBuffer` | **YA** | Ditransmisikan sebagai Base64 atau chunk biner. |
| **Promises** | **YA** | Dapat di-pipe dari server; Client membaca via hook `use(promise)`. |
| **Functions (Biasa/Anonim)** | **TIDAK** | *CRITICAL ERROR*. Fungsi memegang closure runtime server. |
| **Server Actions (`'use server'`)** | **YA** | Fungsi ditransformasikan compiler menjadi URL endpoint RPC metadata. |
| Custom Class Instances (OOP) | **TIDAK** | Prototype chains dan methods hilang saat serialisasi Flight. |
| Symbols | **PARSIAL** | Hanya simbol global yang terdaftar via `Symbol.for()`. |

### Bahaya Asinkronitas: Mengapa Server Components Tidak Punya State?
Server Components didesain murni sebagai fungsi eksekusi tunggal (*idempotent compute per request*). Mereka berjalan di backend, merender pohon ke dalam stream, dan membuang memorinya (*stateless lifecycle*). 

Jika Server Component diizinkan memiliki `useState`:
1.  Di mana state tersebut disimpan jika terdapat 100.000 concurrent user? Memori server akan mengalami lonjakan eksponensial (*Out of Memory*).
2.  Bagaimana cara sinkronisasi mutasi state lokal ke server tanpa overhead koneksi persisten seperti WebSocket bi-directional yang sangat mahal?
Oleh karena itu, reaktivitas dan state interaktif **didelegasikan sepenuhnya** ke Client Components via Web APIs dan DOM event listeners.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi arsitektur RSC murni berbasis ekosistem Node.js/Next.js App Router yang membedakan Server Component, Client Component, dan isolasi keamanan.

### Struktur Direktori:
```text
src/
├── app/
│   ├── layout.tsx
│   └── dashboard/
│       ├── page.tsx
│       └── DashboardClientWrapper.tsx
├── components/
│   ├── AnalyticsPanel.tsx
│   └── RealtimeMetricsToggle.tsx
└── services/
    └── metrics.ts
```

#### File 1: Isolasi Layanan Server (`src/services/metrics.ts`)
```typescript
import 'server-only';

export interface SystemMetric {
  id: string;
  subsystem: string;
  latencyMs: number;
  errorRate: number;
  timestamp: string;
}

// Simulasi akses langsung ke basis data internal via TCP/Socket
export async function queryCriticalMetrics(): Promise<SystemMetric[]> {
  // Database Pool Connection Execution Mock
  await new Promise((resolve) => setTimeout(resolve, 80)); // Simulate 80ms network latency

  return [
    {
      id: 'metric-core-01',
      subsystem: 'Auth Gateway',
      latencyMs: 14.2,
      errorRate: 0.001,
      timestamp: new Date().toISOString(),
    },
    {
      id: 'metric-core-02',
      subsystem: 'Payment Engine',
      latencyMs: 45.8,
      errorRate: 0.000,
      timestamp: new Date().toISOString(),
    },
  ];
}
```

#### File 2: Client Interactive Component (`src/components/RealtimeMetricsToggle.tsx`)
```typescript
'use client';

import React, { useState } from 'react';

interface Props {
  initialState: boolean;
  onFilterChange?: (enabled: boolean) => void;
}

export default function RealtimeMetricsToggle({ initialState, onFilterChange }: Props) {
  const [isActive, setIsActive] = useState<boolean>(initialState);

  const handleToggle = () => {
    const nextState = !isActive;
    setIsActive(nextState);
    if (onFilterChange) {
      onFilterChange(nextState);
    }
  };

  return (
    <div className="flex items-center gap-3 p-2 bg-neutral-900 border border-neutral-800 rounded">
      <span className="text-sm text-neutral-300">Live Polling Status:</span>
      <button
        type="button"
        onClick={handleToggle}
        className={`px-3 py-1 text-xs font-semibold rounded transition-colors ${
          isActive ? 'bg-emerald-600 text-white' : 'bg-rose-900 text-neutral-300'
        }`}
      >
        {isActive ? 'ENABLED' : 'PAUSED'}
      </button>
    </div>
  );
}
```

#### File 3: Server Orchestrator Page Component (`src/app/dashboard/page.tsx`)
```typescript
import React, { Suspense } from 'react';
import { queryCriticalMetrics } from '@/services/metrics';
import RealtimeMetricsToggle from '@/components/RealtimeMetricsToggle';

// Asynchronous Server Component
async function MetricsTable() {
  const metrics = await queryCriticalMetrics();

  return (
    <div className="overflow-x-auto w-full mt-4">
      <table className="min-w-full text-left text-sm font-light text-neutral-200">
        <thead className="border-b border-neutral-700 bg-neutral-800 font-medium">
          <tr>
            <th className="px-4 py-2">Subsystem</th>
            <th className="px-4 py-2">Latency</th>
            <th className="px-4 py-2">Error Rate</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.id} className="border-b border-neutral-800 hover:bg-neutral-800/50">
              <td className="whitespace-nowrap px-4 py-2 font-mono">{m.subsystem}</td>
              <td className="whitespace-nowrap px-4 py-2 font-mono">{m.latencyMs}ms</td>
              <td className="whitespace-nowrap px-4 py-2 font-mono">{m.errorRate}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function DashboardPage() {
  return (
    <main className="p-8 bg-neutral-950 min-h-screen text-neutral-100">
      <header className="flex justify-between items-center border-b border-neutral-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold">Mission Control Telemetry</h1>
          <p className="text-sm text-neutral-400">Zero-Bundle-Cost Server Evaluated Dashboard</p>
        </div>
        {/* Client Component leaf node */}
        <RealtimeMetricsToggle initialState={true} />
      </header>

      <section className="mt-6">
        <h2 className="text-lg font-semibold text-neutral-300">Infrastructure Nodes</h2>
        {/* Suspense streaming boundary */}
        <Suspense fallback={<div className="p-4 text-neutral-500 animate-pulse">Loading telemetry chunks...</div>}>
          <MetricsTable />
        </Suspense>
      </section>
    </main>
  );
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `src/services/metrics.ts`
*   **Baris 1: `import 'server-only';`**
    Menginstruksikan bundler (seperti Webpack/Turbopack) untuk melempar kompilasi *build error* jika ada file berlabel `'use client'` yang secara tidak sengaja mencoba mengimpor berkas ini. Mencegah kebocoran rahasia runtime server.
*   **Baris 11: `export async function queryCriticalMetrics()`**
    Fungsi I/O asinkron murni. Tidak memerlukan library parsing HTTP client seperti Axios. Komunikasi berjalan di layer kernel server langsung ke database.

### Analisis File `src/components/RealtimeMetricsToggle.tsx`
*   **Baris 1: `'use client';`**
    Ini bukan berarti "jalankan file ini HANYA di browser". Ini adalah deklarasi penanda (*boundary*) yang menandakan bahwa komponen ini, beserta semua modul turunannya, akan dimasukkan ke dalam JavaScript bundle klien dan memerlukan hydration di DOM peramban.
*   **Baris 8: `const [isActive, setIsActive] = useState<boolean>(initialState);`**
    State React murni. Variabel ini hidup di browser instance pengguna dan merender ulang hanya cabang subtree `RealtimeMetricsToggle` tanpa memicu re-render di `DashboardPage`.

### Analisis File `src/app/dashboard/page.tsx`
*   **Baris 5: `async function MetricsTable()`**
    Sebuah *Async React Server Component*. React mengeksekusi fungsi ini, mendeteksi penyelesaian `await queryCriticalMetrics()`, memetakan JSX, dan langsung mengubah hasilnya menjadi objek serialisasi Flight Protocol tanpa membebani browser dengan pustaka runtime manipulasi data.
*   **Baris 42: `<Suspense fallback={...}>`**
    React streaming boundary. Server segera mengirimkan payload shell luar halaman ke peramban tanpa menunggu `queryCriticalMetrics()` tuntas. Begitu database mengembalikan data, chunk sisa dikirimkan (*streamed*) melalui HTTP pipeline yang sama dan me-replace elemen fallback secara otomatis.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Financial Multi-Tenant Dashboard
*Konteks Organisasi:* Sebuah platform SaaS B2B Fintech mengeksekusi dashboard analitik portofolio dengan jutaan entri transaksi per menit. 

### Masalah Nyata yang Dihadapi (Legacy Architecture):
1.  **Waterfalls Fetching Ekstrem:** Menggunakan Next.js Pages Router (SPA/Hydrated Client). Browser mengunduh bundle sebesar 4.2 MB (mengandung library Charting masif, formatting library `moment.js`, sanitasi string, dan SDK database internal).
2.  **Hydration Bottleneck:** Browser kelas enterprise mengalami freeze CPU selama 1.2 detik saat hydration (INP = 780ms, TBT = 950ms) karena meng-hydrate ribuan baris tabel statis yang seharusnya tidak memerlukan interaksi event listeners.
3.  **Kebocoran Data Kredensial:** Tim pengembang secara tidak sengaja mengekspos token read-replica Postgres ke dalam layer `process.env.NEXT_PUBLIC_*` agar halaman dapat melakukan fetch langsung dari browser.

### Solusi Desain RSC:
*   Refaktorisasi struktur aplikasi ke Server Components: Semua tabel historis transaksi, format mata uang, dan sanitasi string diproses 100% di Server.
*   Bundle size berkurang dari 4.2 MB menjadi 84 KB (hanya menyisakan logika Client Component untuk filter dropdown dan interaksi tombol export).
*   Implementasi multi-slot Suspense Streaming untuk mengatasi latensi microservice lambat.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem pemrosesan portofolio skala enterprise dengan multi-tier asynchronous streaming, pemisahan boundary, dan Server Action mutasi.

```typescript
// File: src/features/portfolio/actions.ts
'use server';

import { revalidatePath } from 'next/cache';
import 'server-only';

interface AllocationUpdatePayload {
  portfolioId: string;
  targetRiskScore: number;
}

export async function updateRiskAllocation(payload: AllocationUpdatePayload) {
  // Simulasi mutasi database transaksional atomic
  if (payload.targetRiskScore < 0 || payload.targetRiskScore > 100) {
    throw new Error('VALIDATION_FAILED: Risk score out of allowable bounds.');
  }

  // Melakukan operasi I/O aman di server
  console.log(`[AUDIT_LOG]: Updating Portfolio ${payload.portfolioId} to Risk: ${payload.targetRiskScore}`);
  await new Promise((resolve) => setTimeout(resolve, 150)); // Simulating DB write

  // Menginstruksikan cache tree RSC untuk invalidasi data yang ter-cache
  revalidatePath('/portfolio');
  return { success: true, timestamp: Date.now() };
}
```

```typescript
// File: src/features/portfolio/components/RiskSlider.client.tsx
'use client';

import React, { useTransition, useState } from 'react';
import { updateRiskAllocation } from '../actions';

interface RiskSliderProps {
  portfolioId: string;
  currentRisk: number;
}

export default function RiskSlider({ portfolioId, currentRisk }: RiskSliderProps) {
  const [risk, setRisk] = useState<number>(currentRisk);
  const [isPending, startTransition] = useTransition();
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextVal = Number(e.target.value);
    setRisk(nextVal);

    // Membungkus eksekusi Server Action di dalam React Transition
    startTransition(async () => {
      try {
        const res = await updateRiskAllocation({ portfolioId, targetRiskScore: nextVal });
        if (res.success) {
          setFeedback(`Allocated successfully at ${new Date(res.timestamp).toLocaleTimeString()}`);
        }
      } catch (err: unknown) {
        setFeedback(err instanceof Error ? err.message : 'Unknown network failure');
      }
    });
  };

  return (
    <div className="bg-neutral-900 border border-neutral-800 p-4 rounded-lg flex flex-col gap-3">
      <div className="flex justify-between">
        <label htmlFor="risk-range" className="text-sm font-medium text-neutral-300">
          Target Risk Engine Tolerance: <span className="font-mono text-cyan-400">{risk}</span>
        </label>
        {isPending && <span className="text-xs text-amber-400 animate-pulse font-mono">Syncing State...</span>}
      </div>
      <input
        id="risk-range"
        type="range"
        min="0"
        max="100"
        value={risk}
        disabled={isPending}
        onChange={handleChange}
        className="w-full h-2 bg-neutral-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
      />
      {feedback && <span className="text-xs text-neutral-400 font-mono mt-1">{feedback}</span>}
    </div>
  );
}
```

```typescript
// File: src/features/portfolio/page.tsx
import React, { Suspense } from 'react';
import 'server-only';
import RiskSlider from './components/RiskSlider.client';

interface LedgerItem {
  id: string;
  asset: string;
  navUsd: number;
  weightPercentage: number;
}

// Simulasi Direct Microservice RPC Query
async function fetchLedger(portfolioId: string): Promise<LedgerItem[]> {
  // Deep I/O operation
  await new Promise((resolve) => setTimeout(resolve, 250)); // Simulating ledger fetch latency
  return [
    { id: 'LDG-001', asset: 'US Treasury Bonds (10Y)', navUsd: 1450000.5, weightPercentage: 45.2 },
    { id: 'LDG-002', asset: 'Enterprise High-Yield Debt', navUsd: 890000.0, weightPercentage: 27.8 },
    { id: 'LDG-003', asset: 'S&P Large-Cap Derivative', navUsd: 865000.25, weightPercentage: 27.0 },
  ];
}

async function PortfolioLedgerTable({ portfolioId }: { portfolioId: string }) {
  const ledger = await fetchLedger(portfolioId);

  return (
    <div className="border border-neutral-800 rounded-lg overflow-hidden bg-neutral-900/40">
      <table className="w-full text-left text-sm text-neutral-300">
        <thead className="bg-neutral-800 text-neutral-400 uppercase text-xs font-mono">
          <tr>
            <th className="px-6 py-3">Asset Ledger Class</th>
            <th className="px-6 py-3">NAV (USD)</th>
            <th className="px-6 py-3">Weight</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-800 font-mono">
          {ledger.map((item) => (
            <tr key={item.id} className="hover:bg-neutral-800/30">
              <td className="px-6 py-4 font-sans font-medium text-white">{item.asset}</td>
              <td className="px-6 py-4">${item.navUsd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
              <td className="px-6 py-4">{item.weightPercentage.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function PortfolioDashboard() {
  const targetPortfolioId = 'PF-PROD-99812';

  return (
    <div className="max-w-6xl mx-auto p-10 space-y-8 bg-black text-neutral-100 min-h-screen">
      <header className="border-b border-neutral-800 pb-6 flex justify-between items-end">
        <div>
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-500">Asset Management v4</span>
          <h1 className="text-3xl font-extrabold tracking-tight mt-1">Portfolio Rebalancer</h1>
        </div>
        <div className="text-right">
          <div className="text-xs text-neutral-500 font-mono">Target ID: {targetPortfolioId}</div>
        </div>
      </header>

      {/* Interactive Island */}
      <section className="max-w-xl">
        <RiskSlider portfolioId={targetPortfolioId} currentRisk={35} />
      </section>

      {/* Non-Interactive Zero-JS Streaming Ledger */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Ledger Holdings</h2>
          <span className="text-xs text-neutral-500 font-mono">Render Mode: Direct Server Stream</span>
        </div>
        <Suspense
          fallback={
            <div className="h-48 w-full border border-neutral-800 rounded-lg flex items-center justify-center bg-neutral-900/20">
              <span className="text-neutral-500 font-mono text-sm animate-pulse">
                Resolving Distributed Ledger Chunks...
              </span>
            </div>
          }
        >
          <PortfolioLedgerTable portfolioId={targetPortfolioId} />
        </Suspense>
      </section>
    </div>
  );
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Single Page Application (SPA) | Classic Server-Side Rendering (SSR) | React Server Components (RSC) |
| :--- | :--- | :--- | :--- |
| **Ukuran JS Bundle Klien** | Sangat Besar ($O(N)$ terhadap seluruh fitur aplikasi). | Sangat Besar (Seluruh kode pohon UI tetap dikirim untuk Hydration). | **Minimal ($O(K)$ hanya untuk interaktivitas leaf nodes).** |
| **Hydration Cost (CPU Time)** | Tinggi (Membangun seluruh virtual DOM & event bindings). | Sangat Tinggi (Bisa memicu *uncanny valley* di mana UI terlihat tapi tidak responsif). | **Nol untuk Server Nodes, sangat rendah untuk Client Nodes.** |
| **Akses Langsung ke Backend** | Tidak Bisa (Wajib via public network REST/GraphQL endpoints). | Parsial (Hanya via `getServerSideProps` / server wrappers terpisah). | **Bisa (Komponen adalah fungsi backend yang dapat query DB secara native).** |
| **State Preservation Antar Navigasi** | Sempurna (In-memory JavaScript router). | Buruk (Kecuali menggunakan micro-frontends/hack, hard full page reloads). | **Sempurna (Streaming payload di-reconcile oleh React Fiber secara in-place).** |
| **Kompleksitas Mental Model** | Rendah (Semua kode berjalan di lingkungan klien). | Menengah (Pemisahan lifecycle server-render vs client-mount). | **Tinggi (Membutuhkan pemahaman mendalam boundary serialisasi).** |
| **Tooling & Ecosystem Fit** | Universal (Vite, Rollup, CRA). | Luas (Next.js Pages, Remix, Astro). | **Ketats (Memerlukan compiler bundler integration mendalam: Next App Router, Waku).** |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Serialisasi Objek Bersarang Tersembunyi (Circular Dependencies)
Jika Server Component mencoba mengoper objek yang memiliki referensi sirkular ke Client Component:
```typescript
// ERROR SCENARIO
const user: any = { name: 'Alice' };
user.self = user; // Circular reference
return <UserBadge user={user} />; // RUNTIME EXCEPTION: TypeError: Converting circular structure to JSON
```
*Mitigasi:* Jalankan pemetaan eksplisit (*Data Transfer Object* pattern) sebelum data dikirim melalui props. Jangan pernah mengekspos instance model ORM mentah (misal: relasi Prisma/TypeORM) secara langsung.

### 2. Context Boundary Isolation
`React.createContext` dan `useContext` **TIDAK TERSEDIA** di Server Components. 
*Mekanisme Kegagalan:* Jika Server Component mencoba membaca React Context, aplikasi melempar build failure instan.
*Mitigasi:*
*   Gunakan Server Context primitives (jika platform mendukung) atau teruskan data melalui *Props Drilling* eksplisit di level Server Tree.
*   Jika context mutlak dibutuhkan (misal: Theme Provider, UI State Provider), letakkan Provider tersebut di dalam Client Component, lalu bungkus Server Components sebagai `children`!

```typescript
// SOLUSI: Pass Server Component sebagai children ke Client Provider
'use client';
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme] = useState('dark');
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

// Server Component (app/layout.tsx):
export default function RootLayout() {
  return (
    <ThemeProvider>
      {/* MetricsTable tetap berjalan sebagai Server Component! */}
      <MetricsTable /> 
    </ThemeProvider>
  );
}
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menandai Seluruh File dengan `'use client'` di Layer Atas
*Kesalahan Umum:* Meletakkan `'use client'` di level