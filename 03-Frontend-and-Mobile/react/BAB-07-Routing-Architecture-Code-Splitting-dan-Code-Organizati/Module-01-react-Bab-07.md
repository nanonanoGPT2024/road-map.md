# Modul Pembelajaran: Routing Architecture, Code-Splitting, & Code Organization

---

## SEKSI 01 — IDENTITAS MODUL
* **Domain Kurikulum:** `03-Frontend-and-Mobile`
* **Topik Inti:** `react`
* **Kode Modul:** `REACT-MOD-07-01`
* **Judul:** *Routing Architecture, Code-Splitting, & Code Organization*
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman mendalam tentang React Fiber, Reconciler, Lifecycle, Hooks (`useTransition`, `useDeferredValue`), Modern ECMAScript Dynamic Import, serta bundler primitives (Vite/Rollup/Webpack).

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. Merancang arsitektur perutean berskala besar (*enterprise-grade*) berbasis deklaratif data APIs (`createBrowserRouter` / React Router v6.4+) yang memisahkan dependensi jaringan dari *lifecycle rendering*.
2. Mengimplementasikan teknik *Code-Splitting* granular menggunakan `React.lazy`, dynamic `import()`, dan Webpack/Rollup chunk splitting strategies guna memangkas *Initial Bundle Size* dan mengoptimalkan metrik Core Web Vitals (khususnya LCP dan INP).
3. Menguasai orkestrasi *Suspense boundaries* multi-tier untuk mencegah *waterfall rendering* dan *layout thrashing* selama navigasi asinkron.
4. Menerapkan pola organisasi kode *Feature-Driven Architecture* (Screaming Architecture) yang mendukung batasan isolasi domain (*domain boundaries*), skalabilitas tim multi-skuad, dan *colocated route configuration*.
5. Merancang mekanisme proteksi rute, otorisasi berbasis *Role-Based Access Control* (RBAC), serta *pre-fetching logic* pada level interaksi pengguna (*intent-based prefetching*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model 1: Routing Sebagai Finite State Machine (Bukan Sekadar URL Mapping)
Sebagian besar *developer* memperlakukan router hanya sebagai pemetaan sederhana antara URL string dan komponen visual. Dalam aplikasi skala produksi, URL adalah serialisasi dari *Global Application State*. Router bertindak sebagai orchestrator transisi status (*state machine*) yang mengontrol:
* Validasi otentikasi/otorisasi sebelum mount tree.
* Resolusi data paralel (*parallel data fetching*) di luar render loop.
* Penanganan kegagalan (*error boundary isolation*) terlokalisasi.

### Mental Model 2: The Fetch-as-You-Render vs. Render-as-You-Fetch Shift
Paradigma konvensional (*Fetch-on-Render*) menunda pengambilan data hingga komponen selesai di-*mount* (misalnya di dalam `useEffect`). Hal ini menghasilkan fenomena *Network Waterfall*:
```
Download Shell Bundle -> Render Shell -> Download Page Bundle -> Render Page -> Fetch Data -> Render Data UI
```
Pendekatan modern (*Render-as-You-Fetch* melalui Data Routers):
```
Trigger Navigasi -> [Download Chunk + Fetch Data Terparalelisasi] -> Render Tree Lengkap Langsung
```

### Mental Model 3: Code Splitting Bukan Pemotongan Acak
*Code-splitting* bukan sekadar membungkus setiap komponen dengan `React.lazy()`. Memecah *bundle* secara berlebihan (*hyper-fragmentation*) menimbulkan penalti jaringan HTTP/2 multiplexing overhead dan kompresi Brotli/Gzip yang buruk akibat hilangnya kamus kompresi bersama (*shared dictionary*). Pemisahan harus dilakukan pada batas-batas isolasi transaksi: *Route-level chunking* dan *heavy vendor isolation*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah diagram alur siklus hidup navigasi, resolusi data, dan hidrasi kode asinkron pada arsitektur modern data router dengan *intent-based prefetching*.

```
[User Action: Hover/Focus Link] 
              │
              ▼
   (Intent Detector via PointerEvent)
              │
              ├─- Initiates Dynamic Chunk Fetch (import('./PageChunk.js'))
              └─- Initiates Data Loader Fetch (queryClient.prefetchQuery)
              │
[User Action: Click Link]
              │
              ▼
   (Navigation Event Intercepted by History API)
              │
              ▼
  ┌────────────────────────────────────────────────────────┐
  │         React Router v6.4+ Data Router Engine          │
  └────────────────────────────────────────────────────────┘
              │
   ┌──────────┴─────────────────────────┐
   │                                    │
   ▼                                    ▼
[Match Route Definitions]        [Check Auth / RBAC Guards]
   │                                    │
   │                                    ├─-> FAILED: Redirect to /unauthorized
   │                                    │
   ▼                                    ▼
[Execute loaders in Parallel]    [Ensure Code Chunks Loaded]
 (Promise.all([L1, L2, ...]))       (Lazy chunk resolution)
   │                                    │
   └──────────┬─────────────────────────┘
              │
              ▼
  { Are Chunks and Critical Data Ready? }
         /         \
       YES          NO
       /             \
      ▼               ▼
[Render Route View]  [Trigger Suspense Fallback / NProgress Bar]
      │               │
      │               ▼
      │         (Background: Streaming/Waiting promises)
      │               │
      ▼               ▼
[Reconcile Fiber Tree & Mount UI]
      │
      ▼
[Capture Metrics: TTFB, INP, LCP]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dynamic `import()` dan Primitif Module Loader
Ekspresi `import('module')` bukan merupakan fungsi JavaScript standar, melainkan sintaks sintaktis khusus level bahasa (ES2020). Ketika bundler (Vite melalui Rollup, atau Webpack) mendeteksi pemanggilan ini, bundler memotong AST (*Abstract Syntax Tree*) pada titik tersebut dan menghasilkan *split point*.
* **Vite/Rollup:** Menghasilkan file ES Module terpisah di folder `dist/assets/`, diakses menggunakan `<link rel="modulepreload">` atau fungsi pembungkus runtime internal yang memetakan ID modul ke URL fisik.
* **Mekanisme Eksekusi:** Menghasilkan `Promise` native yang me-*resolve* objek modul yang memiliki properti `default` (atau *named exports*).

### 2. Internals `React.lazy` dan Suspense Protocol
`React.lazy` menerima fungsi yang mengembalikan Promise (misalnya `() => import(...)`). Secara internal, `React.lazy` membungkus pemanggilan ini dalam sebuah objek *LazyComponent* dengan struktur internal mirip berikut:
* Status: `-1` (Uninitialized), `0` (Pending), `1` (Resolved), `2` (Rejected).
* Properti `_payload` dan `_init`.

Ketika Reconciler berjalan:
1. Fiber engine memanggil `_init(payload)`.
2. Jika payload masih pending, `_init` **melempar Promise tersebut ke luar stack eksekusi** (`throw thenable`).
3. React Reconciler menangkap (*catches*) nilai yang dilempar menggunakan *boundary* internal.
4. React mencari nenek-moyang terdekat (*ancestor*) bertipe `SuspenseComponent`.
5. Komponen Suspense mencatat Promise tersebut dan merender `fallback` prop ke visual tree.
6. Saat Promise berstatus resolve (`thenable.then(...)`), React menjadwalkan ulang *work loop* baru pada Fiber Suspense tersebut untuk merender konten aktual.

### 3. Arsitektur Data Router (React Router v6.4+)
Berbeda dari model klasik di mana komponen dievaluasi dari atas ke bawah saat rendering, Data Router decoupling navigasi dari render:
* **Route Object Matrix:** Didefinisikan dalam bentuk tree statis sebelum React melakukan inisialisasi render.
* **Parallel Execution Engine:** Ketika navigasi terjadi ke path `/workspace/:id/analytics`, router memecah path menjadi segmen: `['workspace', ':id', 'analytics']`. Loader untuk setiap segmen dijalankan bersamaan secara paralel menggunakan `Promise.allSettled`, bukan serial *waterfall*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Strategi Pengorganisasian Kode: Feature-Driven Development (FDD)
Struktur pengorganisasian kode standar berbasis peran teknis (`/components`, `/hooks`, `/pages`, `/services`) gagal dalam skala *enterprise* dengan puluhan pengembang. Modifikasi satu modul bisnis memaksa *context-switching* melintasi direktori global, meningkatkan risiko *coupling* dan *merge conflict*.

Sebagai gantinya, gunakan arsitektur modular terisolasi (*Feature-Driven/Screaming Architecture*):

```
src/
├── app/                  # Application Shell & Core Providers
│   ├── providers/        # Global context (Query, Theme, Auth)
│   ├── router/           # Central route definition
│   └── store/            # Global atomic state stores
├── assets/               # Global static assets
├── components/           # Reusable generic UI elements (Design System)
├── features/             # Domain-driven feature boundaries
│   ├── billing/          # Feature slice: Pembayaran & Langganan
│   │   ├── api/          # Endpoints, queries, mutations
│   │   ├── components/   # Internal UI components (not shared globally)
│   │   ├── hooks/        # Feature-specific custom hooks
│   │   ├── routes/       # Route declaration & loaders slice
│   │   ├── types/        # TypeScript contracts
│   │   └── index.ts      # Public API barrier (re-exports explicitly)
│   └── order-management/ # Feature slice lain
└── lib/                  # Shared external client wrappers (Axios, Supabase)
```

**Aturan Isolasi (Strict Architectural Rules):**
1. Sebuah modul di dalam `features/billing` dilarang mengimpor file internal dari `features/order-management` secara langsung (misal: `../order-management/components/Invoice.tsx`).
2. Antar-fitur hanya boleh berinteraksi melalui *Public API* (`features/target/index.ts`).
3. Logika routing harus diletakkan dekat (*colocated*) dengan fiturnya di folder `features/*/routes/`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Contoh berikut mendemonstrasikan implementasi *Intent-Based Pre-fetching Router* dengan `React.lazy`, data loading, dan boundary isolasi.

```tsx
// src/lib/lazy-with-preload.ts
import React, { ComponentType, LazyExoticComponent } from 'react';

export type PreloadableComponent<T extends ComponentType<unknown>> = 
  LazyExoticComponent<T> & {
    preload: () => Promise<{ default: T }>;
  };

export function lazyWithPreload<T extends ComponentType<unknown>>(
  factory: () => Promise<{ default: T }>
): PreloadableComponent<T> {
  const Component = React.lazy(factory) as PreloadableComponent<T>;
  Component.preload = factory;
  return Component;
}
```

```tsx
// src/app/router/AppRouter.tsx
import React, { Suspense } from 'react';
import { 
  createBrowserRouter, 
  RouterProvider, 
  RouteObject, 
  Link, 
  Outlet 
} from 'react-router-dom';
import { lazyWithPreload } from '../../lib/lazy-with-preload';

// 1. Lazy loaded components with preload capability
const AnalyticsDashboard = lazyWithPreload(
  () => import('../../features/analytics/routes/AnalyticsPage')
);
const SettingsPage = lazyWithPreload(
  () => import('../../features/settings/routes/SettingsPage')
);

// Fallback skeleton
const PageLoadingFallback = () => (
  <div style={{ padding: '2rem', display: 'flex', gap: '1rem', flexDirection: 'column' }}>
    <div style={{ width: '40%', height: '24px', background: '#e2e8f0', borderRadius: '4px' }} />
    <div style={{ width: '100%', height: '200px', background: '#f1f5f9', borderRadius: '8px' }} />
  </div>
);

// Layout Shell
const RootLayout = () => {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', minHeight: '100vh' }}>
      <aside style={{ borderRight: '1px solid #e2e8f0', padding: '1rem' }}>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {/* Intent-based Prefetch: memicu chunk download saat cursor berada di atas link */}
          <Link 
            to="/analytics" 
            onPointerEnter={() => AnalyticsDashboard.preload()}
            style={{ textDecoration: 'none', color: '#0f172a', fontWeight: 500 }}
          >
            Analytics
          </Link>
          <Link 
            to="/settings" 
            onPointerEnter={() => SettingsPage.preload()}
            style={{ textDecoration: 'none', color: '#0f172a', fontWeight: 500 }}
          >
            Settings
          </Link>
        </nav>
      </aside>
      <main>
        <Suspense fallback={<PageLoadingFallback />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
};

const routes: RouteObject[] = [
  {
    path: '/',
    element: <RootLayout />,
    children: [
      {
        path: 'analytics',
        element: <AnalyticsDashboard />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
    ],
  },
];

const router = createBrowserRouter(routes);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Berkas `lazy-with-preload.ts`
* `Line 3-7`: Pembuatan *type definition* `PreloadableComponent`. Kita memperluas tipe bawaan `LazyExoticComponent<T>` dengan properti fungsi imperatif `.preload()` yang mengembalikan `Promise<{ default: T }>`.
* `Line 9-11`: Implementasi fungsi pembungkus `lazyWithPreload`. Fungsi ini menerima fungsi pabrik (*factory function*) dynamic import.
* `Line 12`: Memanggil `React.lazy(factory)` native.
* `Line 13`: Menempelkan referensi fungsi `factory` secara langsung ke properti `.preload`. Ini memungkinkan kita mengeksekusi *dynamic import* kapan saja dari luar secara imperatif tanpa harus merender komponen tersebut terlebih dahulu ke DOM.

### Analisis Berkas `AppRouter.tsx`
* `Line 12-17`: Pemisahan kode deklaratif. Komponen `AnalyticsPage` dan `SettingsPage` tidak disertakan di dalam bundle *main entry point*. Bundler akan memotong keduanya menjadi chunk terpisah (misalnya `AnalyticsPage-[hash].js`).
* `Line 33-46`: Komponen navigasi yang menyertakan optimasi performa *Intent Prefetching*. Melalui event listener `onPointerEnter` (lebih presisi daripada `onMouseEnter` untuk layar sentuh maupun pointer desktop), aplikasi memanggil `AnalyticsDashboard.preload()`.
* **Mekanisme Eksekusi:** Waktu rata-rata antara pengguna mengarahkan mouse (*hover*) ke tombol hingga menyelesaikan klik fisik (*click*) berkisar antara 100ms hingga 300ms. Dengan mengeksekusi pemanggilan *bundle download* pada rentang jeda ini, saat pengguna menekan mouse, *bundle script* sudah berada di cache memori peramban. Halaman dapat me-*mount* seketika (0ms *perceived delay*).
* `Line 48-50`: Tag `<Outlet />` dibungkus dalam `<Suspense>`. Ini memastikan layout induk (`RootLayout`, sidebar, header) tetap persisten dan interaktif. Hanya area dinamis `<Outlet />` yang bertransisi menampilkan `fallback` jika proses *download* chunk belum selesai.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Enterprise Production Scenario)

### Konteks
Sebuah platform analitik finansial enterprise multi-tenant (*FinTech SaaS*) memiliki ukuran berkas JavaScript mencapai 14.8 MB pada build produksi.

### Masalah
* **Metrik LCP (Largest Contentful Paint):** 5.8 detik pada jaringan 4G standar.
* **INP (Interaction to Next Paint):** 620 milidetik.
* Seluruh fitur (Billing, Trading Platform, Multi-tenant Admin Panel, dan Reporting Engine berbasis Chart.js) dimuat di dalam satu *monolithic bundle* (`index.js`).
* Ketika pengguna tier "Viewer" masuk, peramban mereka tetap mengunduh dan mengeksekusi kode modul Admin dan Trading Engine yang tidak memiliki izin akses bagi mereka.

### Solusi Arsitektur
1. **Restrukturisasi Direktori:** Migrasi ke *Feature-Driven Architecture* dengan isolasi publik boundary.
2. **Dynamic Route-Level Splitting & Role-Based Lazy Chunk Injection:** Memisahkan *entry route* berdasarkan peran otorisasi. Pengguna *Viewer* tidak akan memicu download chunk administrasi.
3. **Intent-driven Loader Prefetching:** Mengintegrasikan pemuatan rute React Router dengan React Query client cache.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem produksi rute enterprise dengan proteksi RBAC tingkat rute, isolasi boundary error, dan data loading terpisah.

```typescript
// src/features/auth/types/auth.types.ts
export type UserRole = 'ADMIN' | 'TRADER' | 'VIEWER';

export interface UserSession {
  id: string;
  name: string;
  role: UserRole;
  token: string;
}
```

```tsx
// src/app/router/ProtectedRoute.tsx
import React, { PropsWithChildren } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { UserRole } from '../../features/auth/types/auth.types';

interface ProtectedRouteProps extends PropsWithChildren {
  user: { role: UserRole } | null;
  allowedRoles: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  user,
  allowedRoles,
  children,
}) => {
  const location = useLocation();

  if (!user) {
    // Redirect ke autentikasi dengan menyimpan lokasi tujuan asal
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    // Alihkan ke rute terlarang secara eksplisit
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
};
```

```tsx
// src/features/trading/routes/trading.routes.tsx
import React from 'react';
import { RouteObject } from 'react-router-dom';
import { lazyWithPreload } from '../../../lib/lazy-with-preload';
import { QueryClient } from '@tanstack/react-query';

// Loader terisolasi (dieksekusi paralel tanpa menunggu download komponen UI)
export const tradingDataLoader = (queryClient: QueryClient) => async () => {
  const queryKey = ['trading', 'market-depth'];
  return (
    queryClient.getQueryData(queryKey) ??
    (await queryClient.fetchQuery({
      queryKey,
      queryFn: async () => {
        const res = await fetch('/api/v1/market-depth');
        if (!res.ok) throw new Error('Gagal mengunduh market depth.');
        return res.json();
      },
      staleTime: 1000 * 30, // 30 detik
    }))
  );
};

// Chunk UI dipisahkan
export const TradingDashboard = lazyWithPreload(
  () => import('../components/TradingDashboard')
);

export const createTradingRoutes = (queryClient: QueryClient): RouteObject => ({
  path: 'trading',
  loader: tradingDataLoader(queryClient),
  element: <TradingDashboard />,
  errorElement: (
    <div role="alert" style={{ padding: '2rem', color: '#b91c1c' }}>
      <h3>Kesalahan Fatal pada Modul Trading</h3>
      <p>Gagal memuat visualisasi pasar modal. Silakan muat ulang.</p>
    </div>
  ),
});
```

```tsx
// src/app/router/index.tsx
import React, { Suspense } from 'react';
import { 
  createBrowserRouter, 
  RouterProvider, 
  Outlet, 
  Navigate 
} from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProtectedRoute } from './ProtectedRoute';
import { createTradingRoutes } from '../../features/trading/routes/trading.routes';
import { UserSession } from '../../features/auth/types/auth.types';

const queryClient = new QueryClient();

// Mock status sesi dari state global / secure storage
const mockCurrentUser: UserSession = {
  id: 'usr-9942',
  name: 'Jane Street Trader',
  role: 'TRADER',
  token: 'jwt-sec-token',
};

const EnterpriseAppLayout = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header style={{ padding: '1rem', borderBottom: '1px solid #ccc' }}>
        FinTech Engine UI | User: {mockCurrentUser.name} ({mockCurrentUser.role})
      </header>
      <main style={{ flex: 1, overflow: 'auto' }}>
        <Suspense fallback={<div style={{ padding: '2rem' }}>Memuat Fragment UI...</div>}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
};

export const router = createBrowserRouter([
  {
    path: '/',
    element: <EnterpriseAppLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/trading" replace />,
      },
      {
        element: (
          <ProtectedRoute 
            user={mockCurrentUser} 
            allowedRoles={['ADMIN', 'TRADER']} 
          >
            <Outlet />
          </ProtectedRoute>
        ),
        children: [
          createTradingRoutes(queryClient),
        ],
      },
      {
        path: 'forbidden',
        element: <div>Akses Ditolak: Anda tidak memiliki wewenang untuk modul ini.</div>,
      },
      {
        path: '*',
        element: <div>404 - Endpoint UI Tidak Ditemukan</div>,
      },
    ],
  },
]);

export const App = () => (
  <QueryClientProvider client={queryClient}>
    <RouterProvider router={router} />
  </QueryClientProvider>
);
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter / Pendekatan | Single Monolithic Bundle | Route-Level Splitting (React.lazy) | Route-Level Splitting + Prefetching Data Loaders |
| :--- | :--- | :--- | :--- |
| **Initial Load (LCP)** | Sangat Buruk (Mengunduh seluruh codebase JS aplikasi) | Cepat (Hanya mengunduh bundle shell awal dan rute aktif) | Sangat Cepat (Ukuran bundle minimal, rute berikutnya sudah siap di cache) |
| **Transisi Antar Rute** | Instan (Semua kode JavaScript sudah ada di memori lokal) | Muncul Flash Skeleton/Spinner (Harus fetch chunk `.js` lewat jaringan) | Mendekati Instan (Chunk `.js` dan data payload sudah ditarik saat hover) |
| **Beban Jaringan / Data** | Boros di awal (Mengunduh modul yang mungkin tidak dibuka) | Paling Hemat (Hanya mengunduh apa yang benar-benar diklik pengguna) | Sedikit Menghabiskan Data (Kemungkinan membuang bandwidth jika hover tanpa klik) |
| **Kompleksitas Kode** | Sangat Sederhana (Import standar `import A from './A'`) | Menengah (Perlu membungkus rute dengan `<Suspense />`) | Tinggi (Memerlukan routing contract, isolasi loader, state coordination) |
| **Debugging Overhead** | Rendah (StackTrace jelas, source maps linear) | Sedang (Perlu konfigurasi chunk mapping di build tool) | Tinggi (Async stack trace terpisah antara loader thread dan visual render) |

---

## SEKSI 12 — EDGE CASES & PITFALLS (Failure Modes & Mitigation)

### 1. The Dynamic Import Chunk Deployment Race Condition (Stale Asset 404)
* **Kondisi Kegagalan:** Pengguna sedang aktif membuka versi aplikasi v1.0. Tim DevOps menjalankan rilis produksi v2.0 yang mengganti file di CDN dengan hash baru. Ketika pengguna mengklik navigasi rute baru yang belum di-*load*, browser mencoba mengunduh `/assets/TradingPage-OldHash.js`. Server CDN mengembalikan HTTP `404 Not Found`. React melempar uncaught error: `ChunkLoadError: Loading chunk failed`.
* **Mitigasi:** Bungkus fungsi dynamic import dengan mekanisme retry dan fallback automatic hard reload jika terjadi error loading chunk:

```typescript
// src/lib/safe-lazy-import.ts
export function safeLazyImport<T>(
  importer: () => Promise<T>,
  retries = 2,
  interval = 1000
): Promise<T> {
  return new Promise((resolve, reject) => {
    importer()
      .then(resolve)
      .catch((error) => {
        if (retries === 0) {
          // Jika rilis baru menyebabkan file chunk lama hilang, paksa browser refresh
          // untuk mengambil HTML entry point terbaru beserta index chunk barunya
          if (typeof window !== 'undefined' && error?.name === 'ChunkLoadError') {
            window.location.reload();
            return;
          }
          reject(error);
          return;
        }

        setTimeout(() => {
          safeLazyImport(importer, retries - 1, interval).then(resolve, reject);
        }, interval);
      });
  });
}
```

### 2. Layout Flickering / Double-Spinners (Suspense Cascading)
* **Kondisi Kegagalan:** Terdapat nested Suspense di tingkat rute induk dan anak. Navigasi rute anak memicu fallback tingkat atas menggantikan layout global, menghancurkan status form atau scrollbar sidebar.
* **Mitigasi:** Gunakan `useTransition` dari React 18 saat memicu navigasi berbasis state imperatif untuk menunda perubahan antarmuka hingga komponen baru siap di-*mount*:

```tsx
import { useTransition } from 'react';
import { useNavigate } from 'react-router-dom';

export const SafeNavButton = ({ to }: { to: string }) => {
  const [isPending, startTransition] = useTransition();
  const navigate = useNavigate();

  return (
    <button
      disabled={isPending}
      onClick={() => {
        startTransition(() => {
          navigate(to);
        });
      }}
    >
      {isPending ? 'Mengalihkan...' : 'Buka Halaman'}
    </button>
  );
};
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menggunakan Named Export Tanpa Normalisasi Default Export pada `React.lazy`
*Anti-pattern:*
```tsx
// SALAH: React.lazy mewajibkan Promise yang me-resolve objek dengan properti { default: Component }
const Dashboard = React.lazy(() => 
  import('./Dashboard').then(mod => mod.Dashboard) // Error jika tipe export tidak serasi!
);
```
*Solusi:*
```tsx
// BENAR: Normalisasi secara eksplisit
const Dashboard = React.lazy(async () => {
  const module = await import('./Dashboard');
  return { default: module.Dashboard };
});
```

### Kesalahan 2: Mendefinisikan Komponen `lazy()` di Dalam Siklus Render
*Anti-pattern:*
```tsx
const ParentView = () => {
  // FATAL: Setiap ParentView re-render, referensi LazyComponent dibuat ulang.
  // Komponen akan unmount, me-reset seluruh internal state, dan re-fetch file bundle terus menerus!
  const ChildLazy = React.lazy(() => import('./ChildComponent'));
  return <ChildLazy />;
};
```
*Solusi:*
Pindahkan selalu pemanggilan `React.lazy` ke **tingkat modul (file scope paling luar)** sehingga referensi fungsi bersifat statis dan stabil.

### Kesalahan 3: Tidak Mengisolasi Vendor Library Berat
*Anti-pattern:*
Mengimpor library parsing berukuran masif (seperti `xlsx`, `pdfmake`, atau modul chart besar) langsung di file utilitas global. Mengakibatkan bundle awal terkontaminasi kode yang jarang dipakai.
*Solusi:*
Gunakan Dynamic Import pada level pemanggilan fungsi:
```tsx
async function handleExportReport(data: ReportData[]) {
  // Hanya fetch modul export saat tombol diklik oleh pengguna
  const { exportToExcel } = await import('../lib/excel-exporter');
  exportToExcel(data);
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Colocated Loaders with Route Modules:** Jangan kumpulkan seluruh data-fetching loader dalam satu file tunggal `/api/loaders.ts`. Deklarasikan fungsi loader di dalam file rute fitur masing-masing (`features/feature-name/routes/feature.routes.tsx`).
2. **Barrel File Discipline (Hindari `index.ts` Obesitas):** Hindari mengimpor seluruh modul dari file index pusat jika bundler Anda tidak dikonfigurasi dengan *sideEffects: false*. Ini memicu *tree-shaking failure*.
3. **Chunk Naming Strategy:** Konfigurasikan penamaan chunk yang deskriptif pada Vite/Rollup config agar telemetry APM (New Relic / Datadog) mudah mengidentifikasi chunk yang gagal dimuat.
4. **Link Component Wrapper:** Bungkus komponen `<Link />` native dari router menjadi komponen design system kustom yang otomatis memiliki perilaku *intent-based prefetching* berdasarkan koneksi data pengguna (`navigator.connection.saveData`).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Manual Chunking pada Build Configuration
Melalui `vite.config.ts` (berbasis Rollup), isolasi vendor dependensi besar ke dalam chunk statis yang jarang berubah untuk memaksimalkan browser caching:

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Pisahkan node_modules vendor inti yang jarang di-update dari bisnis logic
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom') || id.includes('react-router-dom')) {
              return 'vendor-react-core';
            }
            if (id.includes('@tanstack/react-query')) {
              return 'vendor-tanstack';
            }
            if (id.includes('lucide-react')) {
              return 'vendor-icons';
            }
          }
        },
      },
    },
    target: 'es2022', // Manfaatkan fitur native ES modern untuk bundle yang lebih padat
  },
});
```

### 2. Network-Aware Prefetching
Jangan lakukan pre-fetching secara agresif jika pengguna mengaktifkan mode hemat daya/data:

```typescript
export function shouldPrefetch(): boolean {
  if (typeof navigator === 'undefined') return false;
  
  // Deteksi mode Save-Data
  const connection = (navigator as unknown as { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
  if (connection?.saveData) return false;
  
  // Hindari prefetch pada koneksi seluler lambat (2G / slow-2G)
  if (connection?.effectiveType && ['slow-2g', '2g'].includes(connection.effectiveType)) {
    return false;
  }
  
  return true;
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Open Redirection Attack Melalui Parameter Router
Saat mengarahkan rute login kembali ke rute semula menggunakan state URL (`/login?returnTo=https://evil-phishing.com`), aplikasi dapat dieksploitasi untuk serangan *Open Redirect*.

*Mitigasi:* Validasi jalur redirect hanya berupa relative pathname lokal:
```typescript
export function getSafeRedirectPath(target: string | null, fallback = '/dashboard'): string {
  if (!target) return fallback;
  
  // Blokir protokol absolut atau double-slash protocol bypass (//evil.com)
  if (target.startsWith('/') && !target.startsWith('//') && !target.includes(':')) {
    return target;
  }
  
  return fallback;
}
```

### 2. Cross-Site Scripting (XSS) via Dynamic Import Path Traversal
Jangan pernah menerima input dinamis dari URL search parameter untuk menentukan nama berkas yang akan di-import:
```typescript
// KERENTANAN FATAL:
const page = searchParams.get('page');
const DynamicComp = React.lazy(() => import(`../../pages/${page}`)); // PATH TRAVERSAL XSS!
```
*Mitigasi:* Gunakan pemetaan *Whitelist* statis:
```typescript
const VIEW_MAP = {
  profile: () => import('../../features/profile'),
  security: () => import('../../features/security'),
} as const;

const DynamicComp = React.lazy(VIEW_MAP[page as keyof typeof VIEW_MAP] ?? VIEW_MAP.profile);
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Lacak performa waktu unduh chunk asinkron dan error chunk menggunakan Web Vitals dan custom performance markers:

```typescript
// src/lib/chunk-telemetry.ts
export function trackChunkLoad(chunkName: string) {
  const markStart = `${chunkName}-start`;
  const markEnd = `${chunkName}-end`;
  
  performance.mark(markStart);

  return {
    onLoaded: () => {
      performance.mark(markEnd);
      performance.measure(chunkName, markStart, markEnd);
      const entries = performance.getEntriesByName(chunkName);
      const duration = entries[entries.length - 1]?.duration;

      // Kirim durasi ke analitik endpoint (misal Datadog / OpenTelemetry)
      navigator.sendBeacon?.(
        '/telemetry/chunks',
        JSON.stringify({ chunkName, durationMs: duration, timestamp: Date.now() })
      );
    },
    onError: (error: Error) => {
      navigator.sendBeacon?.(
        '/telemetry/chunk