# Bab 01: Fundamental Architecture & Core Mental Model
## Module 01: Next.js Architecture, Foundations, dan Paradigma App Router

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis** perbedaan fundamental antara arsitektur Single Page Application (SPA) murni, traditional Server-Side Rendering (SSR), dan React Server Components (RSC) architecture pada Next.js App Router.
- **Mengidentifikasi** eksekusi runtime batas (*boundary*) antara Node.js Server Environment dan Browser Client Environment.
- **Mengimplementasikan** struktur direktori App Router berbasis filesystem routing menggunakan convention files (`layout`, `page`, `loading`, `error`).
- **Mendiagnosis** dan merekonstruksi kegagalan umum seperti *hydration mismatch* dan *client-server serialization boundary errors*.
- **Merancang** arsitektur komponen hibrida yang meminimalkan pengiriman JavaScript bundle ke client (*zero-bundle-size components*).

---

### 2. Introduction & Conceptual Hook
Dalam arsitektur React klasik (Client-Side Rendering murni via Vite atau CRA), browser mengunduh HTML kosong (`<div id="root"></div>`), dilanjutkan dengan bundle JavaScript raksasa. Browser kemudian harus mem-parsing JS, mengeksekusi runtime React, meminta data via API (waterfall), dan akhirnya merender UI. Model ini menghabiskan daya komputasi perangkat klien, memperlambat *First Contentful Paint* (FCP), dan merusak *Search Engine Optimization* (SEO).

```
React SPA:   [Blank HTML] -> [Download Large JS] -> [Execute JS] -> [Fetch Data API] -> [Render UI]
Next.js RSC: [Server Evaluates RSC + Fetches DB] -> [Stream Fast HTML + RSC Payload] -> [Instant Paint] -> [Selective Hydration]
```

Next.js mengadopsi paradigma komputasi hibrida melalui **App Router** (dibangun di atas React 18+ primitives: Server Components, Suspense, dan Streaming). Next.js memosisikan server bukan sekadar penyedia API statis, melainkan mesin evaluasi logika antarmuka: dependensi berat, koneksi database, dan parsing data terjadi langsung di server, menghasilkan markup dan data stream yang siap dikonsumsi klien secara instan tanpa biaya bundle JavaScript.

---

### 3. Why This Matters
Dalam skala enterprise, pemilihan arsitektur web berdampak langsung pada parameter finansial dan operasional:
1. **Core Web Vitals & Business Impact:** Keterlambatan interaktivitas (*Interaction to Next Paint* - INP) dan render elemen terbesar (*Largest Contentful Paint* - LCP) menurunkan conversion rate e-commerce secara langsung. RSC mereduksi bundle client hingga puluhan kilobyte dengan mempertahankan library analitik, markdown parser, atau query database murni di server.
2. **Infrastructure Cost Reduction:** Menghilangkan keharusan membangun *BFF (Backend-for-Frontend)* middleware terpisah karena Next.js mengeksekusi data layer langsung di boundary server sebelum streaming ke user.
3. **Security by Isolation:** Mengurangi permukaan serangan (attack surface) browser dengan menjaga secrets, token database, dan algoritma proprietary tetap terisolasi di runtime server.

---

### 4. What is Next.js App Router?
Next.js adalah full-stack React framework yang mengimplementasikan spesifikasi **React Server Components (RSC)**.

Secara default, seluruh komponen di dalam direktori `app/` berstatus **Server Components**. Komponen ini:
- Dieksekusi secara eksklusif di server (Node.js atau Edge runtime).
- Tidak pernah menyertakan kodenya ke dalam bundle client JavaScript.
- Mengakses resource back-end (database, file system, internal cache) secara native tanpa latency network hop HTTP tambahan.

Sebaliknya, **Client Components** (dideklarasikan secara eksplisit dengan direktif `'use client'` di baris pertama file) dieksekusi di server untuk menghasilkan HTML awal (pre-rendering), kemudian di-*hydrate* di browser untuk mengikat state, effects, dan event listeners (`onClick`, `onChange`).

---

### 5. Core Concept Architecture & Flow Diagram

Diagram alur eksekusi request pada Next.js App Router:

```
[ Client Browser ]
        |
        | 1. HTTP GET /dashboard
        v
+--------------------------------------------------------------------+
| Next.js Server / Edge Runtime                                      |
|                                                                    |
|  [Middleware Engine] (Edge)                                        |
|         |                                                          |
|         v                                                          |
|  [Routing & Matcher] -> Matches: app/dashboard/page.tsx            |
|         |                                                          |
|  [RSC Component Tree Evaluation]                                   |
|   +-- RootLayout (Server)                                          |
|   |    +-- Sidebar (Server)                                        |
|   |    +-- DashboardPage (Server: Direct DB Query via ORM)         |
|   |    +-- RealtimeWidget ('use client' Boundary)                  |
|         |                                                          |
|         |-- Evaluates Server Tree -> Generates Virtual DOM         |
|         |-- Keeps Client Components as Slots/References            |
|         v                                                          |
|  [Serialization Engine]                                            |
|   +---> RSC Payload (JSON-like representation of UI tree)          |
|   +---> Progressive HTML Engine (Render to ReadableStream)         |
+--------------------------------------------------------------------+
        |
        | 2. Streaming Response (Multiplexed over HTTP/2)
        |    Chunk 1: Immediate HTML Shell for Critical Paint
        |    Chunk 2: React Server Component Payload (Flight Data)
        v
[ Client Browser Runtime ]
        |
        |-- 3. DOM Parser paints initial HTML (Fast FCP & LCP)
        |-- 4. React Fiber reconciles DOM with RSC Payload
        |-- 5. Browser downloads ONLY scripts for 'use client' components
        +-- 6. Hydration occurs SELECTIVELY (RealtimeWidget becomes interactive)
```

---

### 6. How It Works Under the Hood
1. **Compilation Phase (Next.js Compiler via Turbopack/SWC):**
   Next.js memisahkan modul menjadi dua graph dependensi terpisah: *Server Component Module Graph* dan *Client Component Module Graph*. Komponen dengan direktif `'use client'` ditandai sebagai boundary manifest (*Flight Manifest*).
2. **Execution Phase (Request Time):**
   Ketika request masuk, React di server mengeksekusi fungsi komponen async. React tidak menghasilkan HTML secara langsung, melainkan format serialisasi internal bernama **Flight Data** (RSC Payload). Format ini merepresentasikan:
   - Komponen HTML primitif (`<div>`, `<span>`).
   - Prop values dari server components.
   - Placeholder tag untuk Client Components (berisi path ke file JS client yang dibutuhkan).
3. **HTML Streaming:**
   Renderer Next.js membaca stream RSC Payload ini dan secara simultan memancarkan string HTML. Teknik streaming ini memanfaatkan transfer-encoding chunked, memungkinkan browser menampilkan UI skeleton sebelum query data yang lambat selesai.
4. **Hydration Engine:**
   Di browser, script client menginisialisasi React Fiber. React membaca RSC Payload yang disisipkan di dalam HTML, memetakan Client Components ke DOM yang ada, dan mengaitkan event handlers tanpa merender ulang Server Components.

---

### 7. Minimal Reproducible Example
Struktur direktori:
```
my-app/
├── app/
│   ├── layout.tsx
│   └── page.tsx
├── package.json
└── tsconfig.json
```

File: `app/layout.tsx`
```tsx
import type { ReactNode } from 'react';

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: 'sans-serif', margin: '2rem' }}>
        <header style={{ borderBottom: '1px solid #ccc', paddingBottom: '1rem' }}>
          <strong>Next.js Fundamental Architecture</strong>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
```

File: `app/page.tsx`
```tsx
// Server Component secara default (Tanpa 'use client')
export default async function HomePage() {
  const timestamp = new Date().toISOString();

  return (
    <section>
      <h1>Server-Driven Layout</h1>
      <p>Timestamp dieksekusi di server: {timestamp}</p>
      <small>Tidak ada JavaScript tambahan untuk rendering teks ini di client.</small>
    </section>
  );
}
```

---

### 8. Real-World Practical Example: Server-Client Boundary Split
Implementasi katalog telemetri server dengan selective hydration untuk komponen interaktif.

Struktur file:
```
app/
├── metrics/
│   ├── components/
│   │   ├── metrics-skeleton.tsx
│   │   └── refresh-trigger.tsx
│   ├── loading.tsx
│   ├── error.tsx
│   └── page.tsx
```

File: `app/metrics/components/refresh-trigger.tsx`
```tsx
'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';

interface RefreshTriggerProps {
  initialCount: number;
}

export function RefreshTrigger({ initialCount }: RefreshTriggerProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [clickCount, setClickCount] = useState(initialCount);

  const handleRefresh = () => {
    setClickCount((prev) => prev + 1);
    
    // Memberitahu Next.js untuk merevalidasi Server Component tree tanpa refresh halaman
    startTransition(() => {
      router.refresh();
    });
  };

  return (
    <div style={{ padding: '1rem', border: '1px solid #0070f3', borderRadius: '4px' }}>
      <p>Client Interactivity State: {clickCount} clicks</p>
      <button 
        onClick={handleRefresh} 
        disabled={isPending}
        style={{ cursor: isPending ? 'not-allowed' : 'pointer' }}
      >
        {isPending ? 'Syncing with Server...' : 'Trigger Server Re-fetch'}
      </button>
    </div>
  );
}
```

File: `app/metrics/page.tsx`
```tsx
import { RefreshTrigger } from './components/refresh-trigger';

interface MetricPayload {
  uptime: number;
  memoryUsage: string;
  source: string;
}

// Simulasi fetching resource internal server / DB
async function getSystemMetrics(): Promise<MetricPayload> {
  // Simulasi I/O bound latency
  await new Promise((resolve) => setTimeout(resolve, 800));

  const memory = process.memoryUsage();
  return {
    uptime: process.uptime(),
    memoryUsage: `${(memory.heapUsed / 1024 / 1024).toFixed(2)} MB`,
    source: process.env.NODE_ENV || 'production',
  };
}

export default async function MetricsPage() {
  const data = await getSystemMetrics();

  return (
    <div>
      <h2>System Telemetry (Direct Node.js Context)</h2>
      <dl>
        <dt>Engine Process Uptime:</dt>
        <dd>{data.uptime.toFixed(4)}s</dd>
        
        <dt>Heap Memory Used:</dt>
        <dd>{data.memoryUsage}</dd>
        
        <dt>Runtime Target:</dt>
        <dd>{data.source}</dd>
      </dl>

      {/* Boundary Crossing: Server mengalirkan data primitif ke Client Component */}
      <RefreshTrigger initialCount={0} />
    </div>
  );
}
```

File: `app/metrics/loading.tsx`
```tsx
export default function Loading() {
  return (
    <div style={{ padding: '2rem', color: '#666' }}>
      <p>Mengambil telemetri sistem langsung dari server runtime...</p>
    </div>
  );
}
```

File: `app/metrics/error.tsx`
```tsx
'use client';

import { useEffect } from 'react';

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Unhandled Server Component Error:', error);
  }, [error]);

  return (
    <div style={{ padding: '1rem', border: '1px solid red', color: 'red' }}>
      <h3>Gagal memuat telemetri server.</h3>
      <p>{error.message}</p>
      <button onClick={() => reset()}>Coba lagi</button>
    </div>
  );
}
```

---

### 9. Implementation Step-by-Step Guide
1. **Inisialisasi Project:**
   ```bash
   npx create-next-app@latest next-core-arch --typescript --eslint --no-tailwind --app --src-dir=false --import-alias="@/*"
   cd next-core-arch
   ```
2. **Verifikasi Boundary Dependency Rules:**
   Instal package untuk mencegah server logic bocor ke client bundle:
   ```bash
   npm install server-only
   ```
3. **Konfigurasi Server Guard:**
   Buat file `lib/server-database.ts`:
   ```typescript
   import 'server-only';

   export function queryDatabasePrivate() {
     return { secretKey: process.env.DB_INTERNAL_KEY || "native-secret-1234" };
   }
   ```
   *Jika file ini di-import di dalam Client Component (`'use client'`), compiler Next.js akan membatalkan build secara otomatis.*

---

### 10. Edge Cases, Pitfalls & Failure Modes
1. **Hydration Mismatch:**
   Terjadi ketika HTML hasil pre-render server berbeda dari HTML komputasi client pertama kali.
   *Contoh Kerusakan:* Menggunakan `new Date().toLocaleTimeString()` atau `window.innerWidth` langsung di dalam body komponen.
   *Solusi Teknis:* Isolasi data berbasis waktu/browser dalam hook `useEffect` atau flag `mounted`.
2. **Passing Non-Serializable Props across Boundary:**
   Server Components tidak dapat mengirimkan function callbacks, Symbol, atau class instances dengan prototype methods ke Client Components.
   ```tsx
   // SERVER COMPONENT
   <ClientButton onClickAction={() => console.log('fails')} /> // ERROR SERIALIZATION
   ```
3. **Poisoning the Module Graph:**
   Menaruh `'use client'` di level file paling atas tanpa kebutuhan nyata memaksa seluruh child component di tree tersebut ikut masuk ke dalam client bundle, merusak efisiensi zero-bundle-size RSC.

---

### 11. Trade-offs & Engineering Decisions

| Parameter | Next.js App Router (RSC) | Pure React SPA (Vite) | Next.js Pages Router (SSR) |
| :--- | :--- | :--- | :--- |
| **Initial Bundle Size** | Minimal (Zero-KB base for static branches) | Bertambah seiring kompleksitas UI | Moderat (JSON page props runtime) |
| **Data Waterfall Risk**| Rendah (Data ditarik co-located di server) | Tinggi (Network waterfalls di client) | Rendah (Fetch terpusat di `getServerSideProps`) |
| **Compute Location** | Hibrida (Dynamic Node.js / Edge + Browser)| Client Exclusive | Tersegmentasi (Semua SSR via runtime server) |
| **DX & Mental Model** | Kompleks (Isolasi boundary RSC vs RCC) | Sederhana (Semua komponen bertipe Client) | Sedang (Pemisahan data layer dan view layer) |
| **Streaming UI** | Native via React Suspense | Harus diatur manual via state skeleton | Kurang fleksibel (Blocking HTML render) |

---

### 12. Performance & Optimization Strategy
1. **Pushing the Client Boundary to the Leaves:**
   Jangan bungkus seluruh halaman dengan `'use client'`. Buat Server Component membungkus konten statis dan hanya tandai elemen interaktif kecil (tombol, input) sebagai Client Component.
2. **RSC Payload Pre-fetching:**
   Next.js secara default mem-prefetch Server Component Payload saat tag `<Link href="...">` masuk ke dalam viewport browser via `IntersectionObserver`. Optimalkan dengan:
   ```tsx
   import Link from 'next/link';
   // Nonaktifkan prefetch agresif hanya untuk route data-heavy
   <Link href="/analytics" prefetch={false}>Analytics</Link>
   ```
3. **Streaming Suspense Chunking:**
   Gunakan React `Suspense` untuk memisahkan stream data lambat agar tidak memblokir render initial layout:
   ```tsx
   <Suspense fallback={<MetricsSkeleton />}>
     <SlowDataComponent />
   </Suspense>
   ```

---

### 13. Security Considerations & Hardening
1. **Data Exposure Across RSC Serialization Boundary:**
   RSC Payload menyertakan nilai props dalam plain text JSON-like string. Jika server component membaca objek database utuh:
   ```tsx
   // RISIKO TINGGI: passwordHash ikut terkirim di Flight Data Stream
   const user = await db.user.findFirst();
   return <UserProfileCard user={user} />;
   ```
   *Mitigasi:* Bentuk Data Transfer Object (DTO) yang eksplisit:
   ```tsx
   const { id, username } = await db.user.findFirst();
   return <UserProfileCard user={{ id, username }} />;
   ```
2. **Environment Variable Leaks:**
   Hanya variabel dengan prefix `NEXT_PUBLIC_` yang di-injeksi ke bundle client. Pastikan secrets (API Keys, Database URLs) tidak memiliki prefix ini.

---

### 14. Testing Strategy
Untuk menguji arsitektur App Router, strategi pengujian dibagi menjadi dua isolasi:

File: `__tests__/metrics-page.test.tsx` (Integration Test via Vitest / Jest)
```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MetricsPage from '@/app/metrics/page';

// Mock dependensi eksternal / DB logic
vi.mock('process', () => ({
  uptime: () => 123.456,
  memoryUsage: () => ({ heapUsed: 50 * 1024 * 1024 }),
  env: { NODE_ENV: 'test' }
}));

describe('Server Component: MetricsPage', () => {
  it('harus mengeksekusi logika server dan merender telemetri dengan benar', async () => {
    // RSC mengembalikan Promise (Async Component)
    const PageComponent = await MetricsPage();
    render(PageComponent);

    expect(screen.getByText('System Telemetry (Direct Node.js Context)')).toBeDefined();
    expect(screen.getByText('123.4560s')).toBeDefined();
  });
});
```

---

### 15. Observability & Debugging
Untuk melacak eksekusi Server Components dan lifecycle stream:
1. **Aktifkan Profiling React Server Components:**
   Di file `next.config.mjs`:
   ```javascript
   /** @type {import('next').NextConfig} */
   const nextConfig = {
     logging: {
       fetches: {
         fullUrl: true,
       },
     },
   };
   export default nextConfig;
   ```
2. **Flight Response Inspection:**
   Buka DevTools > Network Tab. Filter berdasarkan `Fetch/XHR`. Inspeksi request path halaman. Perhatikan request dengan header `RSC: 1`. Respons tersebut merupakan payload serialisasi teks internal React (`Flight data`), bukan HTML baku.

---

### 16. Common Antipatterns & Refactoring

#### Antipattern: Globalizing the Client Directive
Menandai root layout atau komponen tingkat tinggi sebagai Client Component hanya untuk menggunakan context atau modal sederhana:

```tsx
// ❌ BURUK: Mematikan seluruh optimasi RSC di bawahnya
'use client';

export default function Layout({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState('dark');
  return <div className={theme}>{children}</div>;
}
```

#### Refactoring: Leaf-node Localization & Composition
Gunakan pattern Composition: jadikan Client Component sebagai pembungkus yang menerima `children` (Server Component) sebagai prop:

```tsx
// ✅ BAIK: ThemeProvider menjadi Client boundary, children tetap Server Component
'use client';

import { useState } from 'react';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme] = useState('dark');
  return <div className={`theme-${theme}`}>{children}</div>;
}

// app/layout.tsx (Server Component)
import { ThemeProvider } from './theme-provider';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <ThemeProvider>
          {children} {/* children dieksekusi di Server! */}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

---

### 17. FAQ & Troubleshooting
- **Q: Apakah kita masih memerlukan API Routes (`route.ts`) untuk mengambil data di dalam Server Component?**
  *A: Tidak.* Mengambil data via `fetch('http://localhost:3000/api/...')` dari Server Component di domain yang sama adalah antipattern. Eksekusi database query atau ORM secara native langsung di dalam Server Component untuk memotong HTTP overhead.
- **Q: Mengapa saya mendapatkan error `window is not defined` padahal sudah memakai `'use client'`?**
  *A: Client Components tetap melewati pre-rendering di server untuk memproduksi HTML awal.* Hindari mengakses API browser di root level fungsi komponen. Akses global `window`/`document` hanya di dalam hook `useEffect`.

---

### 18. Knowledge Check / Self-Assessment
1. Apa format komputasi yang dihasilkan oleh Next.js Server Components sebelum di-stream ke browser?
   - A. Bytecode V8
   - B. Flight Data / RSC Payload
   - C. Pure WebAssembly
   - D. Static JSON Object
2. *Skenario Debugging:* Anda memiliki library validasi regex berukuran 2MB. Di mana letak penempatan terbaik agar library ini tidak pernah sampai ke browser klien? Jelaskan mekanisme internalnya.
3. Mengapa meneruskan callback handler seperti `onSuccess={() => void}` dari Server Component ke Client Component memicu error kompilasi runtime?

---

### 19. Hands-on Challenge / Mini-Project
**Challenge: Build a Zero-Bundle Markdown Documentation Viewer**
- **Objective:** Buat route `/docs` yang membaca file `.md` langsung dari filesystem server (gunakan modul native Node `fs/promises`).
- **Persyaratan Arsitektural:**
  1. Halaman harus Server Component dan parsing markdown (misal menggunakan library `marked`) harus terjadi 100% di server.
  2. Implementasikan Client Component mini bernama `<CopyCodeButton />` yang membaca snippet kode dan berinteraksi dengan API Clipboard browser.
  3. Komposisikan layout sehingga parser markdown tidak menyumbang 1 byte pun ke JavaScript bundle browser (Verifikasi melalui DevTools Network tab coverage).

---

### 20. Summary & Next Steps
Anda telah menguasai:
- Transisi paradigma dari komputasi client murni (SPA) ke hybrid Server-Client execution tree.
- Anatomi request Next.js: dari Edge/Node runtime, RSC payload generation, hingga streaming selective hydration.
- Praktik terbaik isolasi boundary menggunakan `'use client'` dan teknik komposisi React.

**Next Module:** *Module 02: Routing System Deep Dive (Dynamic Segments, Parallel Routes, and Intercepting Routes).*