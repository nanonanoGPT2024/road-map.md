# Kurikulum Enterprise React: Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 07: Routing Architecture, Code-Splitting, dan Code Organization**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Merancang dan Mengimplementasikan Arsitektur Routing Terdistribusi**: Membangun pohon rute berorientasi data (*data-driven routing*) berbasis React Router v6/v7 menggunakan *Data APIs* (`createBrowserRouter`, `loaders`, `actions`, `defer`) secara *type-safe* menggunakan TypeScript.
2. **Mengeksekusi Strategi Code-Splitting Multi-Layer**: Mengisolasi *bundle overhead* melalui kombinasi *Route-level chunking*, *Component-level dynamic importing*, *Intent-based prefetching*, dan optimasi konfigurasi bundler (Vite/Rollup).
3. **Mengabstraksi Struktur Kode Berbasis Domain (*Feature-Sliced Design*)**: Menata basis kode monolitik skala enterprise ke dalam modul-modul modular yang terisolasi (*co-located*), mudah dirawat, dan memiliki batas domain (*domain boundaries*) yang rigid.
4. **Membangun Sistem Otorisasi Akses Komprehensif (RBAC & Route Guards)**: Merancang mekanisme proteksi rute granular tanpa memicu *waterfall network request* dan tanpa merusak siklus hidup layout React (*zero layout shift*).
5. **Mengoptimalkan Metrik Web Vitals**: Menekan *Largest Contentful Paint* (LCP) dan *Interaction to Next Paint* (INP) pada navigasi rute melalui eliminasi *render-as-you-fetch waterfalls*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:

* **React Core**: Pemahaman mendalam tentang *Fiber Architecture*, rekonsiliasi, siklus hidup komponen, Hooks (`useEffect`, `useTransition`, `useMemo`, `useCallback`), dan mekanisme *Suspense* / *Error Boundary*.
* **TypeScript Lanjutan**: *Generics*, *Union Types*, *Conditional Types*, *Type Narrowing*, dan *Utility Types* (`Awaited`, `ReturnType`).
* **Dasar Navigasi Web**: Web History API (`pushState`, `replaceState`, `popstate`), protokol HTTP (status codes, caching headers), dan lifecycle browser request/response.
* **Modern Bundling Pipelines**: Pengetahuan dasar tentang mekanisme kerja Webpack atau Rollup/Vite, pemetaan *dynamic import* (`import()`), dan *dependency chunking*.

---

## 3. Concept & Internal Architecture

Navigasi pada aplikasi Single Page Application (SPA) modern menuntut sinkronisasi antara URL browser, data dependensi, dan tree komponen UI.

```
                    Siklus Navigasi React Router Data APIs
                    
 [ User Interaction ] -> Klik Link / trigger `navigate('/invoices/123')`
          │
          ▼
 [ Router Matching Engine ] -> Evaluasi Route Path & Granular Permissions
          │
          ├─── PARALLEL EXECUTION ──────────────────────────────────────┐
          │                                                             │
          ▼                                                             ▼
 [ Dynamic Chunk Fetch ]                                  [ Route Loaders Fetch ]
 fetch('invoices-chunk.js')                              loader({ params: { id: 123 } })
          │                                                             │
          └──────────────────────────────┬──────────────────────────────┘
                                         ▼
                       [ Promise.all Resolution ]
                                         │
                                         ▼
                     [ React Concurrent Transition ]
                   (Mempertahankan UI lama jika pending)
                                         │
                                         ▼
             [ React Suspense Boundary Resolution Tree ]
                         /                       \
                        ▼                         ▼
             [ Render Component Layout ]     [ Commit Phase ]
                dengan Hydrated Loader Data     Update DOM & URL
```

### 3.1. Internal Engine: React Router Data API vs Legacy Routing
Pada arsitektur legacy (React Router v5 dan v6 awal), *routing* diatur menggunakan paradigma **Fetch-on-Render**:
1. URL berubah -> Rute mencocokkan komponen -> Komponen dirender.
2. `useEffect` di dalam komponen baru dieksekusi -> Request API data berjalan.
3. Menghasilkan *waterfall effect*: Download JS Bundle $\rightarrow$ Parse/Execute $\rightarrow$ Render Loader $\rightarrow$ Fetch Data $\rightarrow$ Re-render Final UI.

Arsitektur data modern membalik paradigma ini menjadi **Render-as-you-Fetch**:
* Melalui `createBrowserRouter`, data loader dan *dynamic import code chunk* dieksekusi secara **paralel** tepat saat URL berubah (atau bahkan saat interaksi *intent* seperti hover berlangsung).
* Data loader dieksekusi di luar siklus hidup React render, memotong ketergantungan siklus hidup komponen pada inisialisasi jaringan.
* React Router mengoordinasikan *state transition* menggunakan internal abstraction yang kompatibel dengan React 18 Concurrent Mode (`startTransition`), mencegah *layout flashing* atau *blank state* sementara.

### 3.2. Dynamic Imports dan Mekanisme Pembagian Modul (Code Splitting)
Ketika sebuah aplikasi memanggil:
```typescript
const DashboardModule = React.lazy(() => import('./features/dashboard/DashboardPage'));
```
Bundler (seperti Vite/Rollup atau Webpack) tidak menyertakan modul tersebut ke dalam `main.[hash].js`. Bundler membuat *entry point* sekunder, memecah kode menjadi *chunk terpisah* (misal: `DashboardPage.[hash].js`), dan menggantikan sintaksis import dengan HTTP invocation dinamis berbasis ES Modules (`import()`) atau JSONP callback runtime.

Ketika rute dipicu:
1. `React.lazy` membungkus status Promise dari dynamic import.
2. Jika Promise bernilai *pending*, React melempar (*throw*) Promise tersebut ke atas tree, ditangkap oleh `SuspenseBoundary` terdekat.
3. Suspense mendeteksi Promise tertangkap, menunda render sub-tree, dan menampilkan *fallback*.
4. Ketika Promise resolved, React mencoba merender kembali sub-tree tersebut dengan modul yang sudah tersedia di *memory heap*.

### 3.3. Arsitektur Struktur Kode: Modularity Boundaries
Pada skala enterprise, arsitektur folder berbasis tipe (seperti `/components`, `/pages`, `/services`) runtuh karena beban kognitif tinggi dan *cross-dependency leakage*. Kita menerapkan **Feature-Sliced Design (FSD)** atau **Domain-Driven Directory Layout**:
* **App Layer**: Konfigurasi global (router provider, providers, styling global).
* **Processes / Routes Layer**: Halaman aplikasi, deklarasi rute, proteksi otentikasi.
* **Feature Layer**: Logika bisnis fungsional user (e.g., `feature/send-invoice`, `feature/billing-filter`).
* **Entity Layer**: Representasi data domain dan schema (e.g., `entity/invoice`, `entity/account`).
* **Shared Layer**: Kode agnostik domain yang dapat digunakan kembali (UI components primitif, utilitas HTTP client, dynamic hook registry).

---

## 4. Why & What

| Dimensi | Pendekatan Monolitik Tradisional | Arsitektur Enterprise Modern |
| :--- | :--- | :--- |
| **Bundling Strategy** | Single file `bundle.js` atau split vendor/app sederhana. File size membengkak > 5MB. | Micro-chunks per rute dan per interaksi kompleks. Main entry point < 150KB. |
| **Data Fetching Workflow** | `useEffect` waterfalls. Tampilan berkedip (spinner-in-spinner hell). | Parallel Data Loaders + Suspense Streaming. Data dan kode dimuat bersamaan. |
| **Route Security / Guards**| Kondisional render di dalam komponen (`if (!isAuth) return <Redirect />`). Terjadi render leak. | Pre-execution Guard via Data Router Loaders. Navigasi dibatalkan sebelum render terjadi. |
| **Organisasi Kode** | Folder-by-type (`/components`, `/hooks`, `/pages`). Sulit didegradasi/dihapus secara modular. | Domain/Feature-Colocated. Tiap feature mandiri: route, model, views, dan tests terisolasi. |
| **Prefetching Policy** | Tidak ada, atau manual fetch yang rentan *race conditions*. | Intent-driven dynamic module & data prefetching via intersection observer atau mouse hover. |

---

## 5. How (Workflow Detail)

Berikut adalah tahapan implementasi arsitektur routing enterprise:

```
  Tahap 1: Setup Kontrak Tipe & Registry Rute
      │
      ▼
  Tahap 2: Definisi Data Loaders dengan RBAC Check
      │
      ▼
  Tahap 3: Dynamic Chunk Loading & Intent Prefetching Strategy
      │
      ▼
  Tahap 4: Implementasi Error Boundary & Granular Suspense
      │
      ▼
  Tahap 5: Runtime State Hydration & Concurrent Commit
```

1. **Definisi Route Tree**: Rute dideklarasikan secara tersentralisasi menggunakan `createBrowserRouter`, mengisolasi rute publik, rute privat (*authenticated*), dan rute terproteksi peran (*role-based*).
2. **Pembuatan Loader Terisolasi**: Setiap segmen rute memiliki file `loader.ts` yang mengeksekusi pemeriksaan sesi otentikasi dan *fetch resource* secara paralel via `Promise.all`.
3. **Penyusunan Guard**: Loader melempar instance `Response` (seperti `redirect('/login')`) jika validasi kredensial gagal sebelum komponen merender apapun.
4. **Implementasi Prefetching**: Event `onMouseEnter` atau `onFocus` pada komponen navigasi memicu loader data dan module chunks browser cache secara *low-priority*.
5. **Penanganan Error Terisolasi**: Menerapkan `errorElement` per level segmen rute. Kerusakan pada modul *child* tidak merusak *root layout* aplikasi.

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Terminal Bandara Internasional
* **Monolithic Routing (Tradisional)**: Penumpang masuk terminal, semua bagasi dari seluruh penerbangan hari itu diturunkan di satu konveyor umum. Anda harus menunggu seluruh bagasi diproses sebelum pintu gerbang Anda dibuka.
* **Enterprise Distributed Routing (Modern)**: Anda tiba di terminal (Root Chunk). Gate dibuka secara spesifik untuk tiket Anda (RBAC Guard). Hanya logistik penerbangan Anda yang dimuat (Route Chunk Splitting). Makanan disajikan di pesawat sesuai pesanan yang telah dikirim saat boarding (Data Loaders & Prefetching). Jika ada kendala di mesin pesawat, penumpang diarahkan ke ruang tunggu tanpa menutup seluruh bandara (Granular Error Boundary).

### Diagram Alir Eksekusi Route Guard & Data Loader
```
                           [ Navigasi Dimulai ]
                                    │
                                    ▼
                      [ Rute Cocok Ditemukan? ]
                        │                    │
                      Tidak                  Ya
                        │                    │
                        ▼                    ▼
               [ 404 Error Boundary ]  [ Cek Auth via Loader ]
                                             │
                        ┌────────────────────┴───────────────────┐
                        │ Gagal                                  │ Berhasil
                        ▼                                        ▼
             [ Throw Response.redirect ]               [ Cek Granular RBAC ]
                        │                                        │
                        ▼                                ┌───────┴───────┐
               [ Eksekusi Redirect ]                     │ Ditolak       │ Diizinkan
                                                         ▼               ▼
                                                  [ 403 Forbidden ]  [ Eksekusi Parallel Fetch ]
                                                                             │
                                                                     ┌───────┴───────┐
                                                                     ▼               ▼
                                                              [ Fetch Data ]  [ Fetch JS Chunk ]
                                                                     │               │
                                                                     └───────┬───────┘
                                                                             │
                                                                             ▼
                                                                  [ Render Target View ]
```

---

## 7. Simple Example & Practical Example

### Simple Example: Type-Safe Route Loader dengan Dynamic Import

File: `src/simple/SimpleRoute.tsx`
```tsx
import React, { Suspense } from 'react';
import { createBrowserRouter, RouterProvider, type LoaderFunctionArgs } from 'react-router-dom';

// 1. Dynamic import target component
const UserAnalyticsLazy = React.lazy(() => import('./UserAnalytics'));

// 2. Strongly typed loader
export interface UserAnalyticsData {
  userId: string;
  totalTransactions: number;
}

export async function userAnalyticsLoader({ params }: LoaderFunctionArgs): Promise<UserAnalyticsData> {
  const { userId } = params;
  if (!userId) {
    throw new Response('Missing User ID', { status: 400 });
  }

  // Simulasi fetch external
  const res = await fetch(`https://api.example.com/users/${userId}/analytics`);
  if (!res.ok) {
    throw new Response('Failed to retrieve analytics', { status: res.status });
  }

  return res.json();
}

// 3. Declarative Route Composition
export const simpleRouter = createBrowserRouter([
  {
    path: '/users/:userId/analytics',
    loader: userAnalyticsLoader,
    element: (
      <Suspense fallback={<div>Loading component module...</div>}>
        <UserAnalyticsLazy />
      </Suspense>
    ),
    errorElement: <div>Error loading analytics context.</div>,
  },
]);

export function SimpleApp() {
  return <RouterProvider router={simpleRouter} />;
}
```

---

### Practical Example: Production-Ready Modular Architecture (FSD, RBAC, Data Loaders & Prefetching)

Struktur Direktori:
```text
src/
├── app/
│   ├── providers/
│   │   └── AuthProvider.tsx
│   └── routes/
│       ├── AppRouter.tsx
│       └── ProtectedRouteGuard.tsx
├── shared/
│   ├── api/client.ts
│   └── ui/PrefetchLink.tsx
└── features/
    └── billing/
        ├── api/billingLoader.ts
        ├── pages/BillingDashboardPage.tsx
        └── types.ts
```

#### Shared Pre-fetch Link Component (`src/shared/ui/PrefetchLink.tsx`)
```tsx
import React from 'react';
import { Link, type LinkProps } from 'react-router-dom';

interface PrefetchLinkProps extends LinkProps {
  onPrefetchModule?: () => Promise<unknown>;
  onPrefetchData?: () => Promise<unknown>;
}

export const PrefetchLink: React.FC<PrefetchLinkProps> = ({
  to,
  children,
  onPrefetchModule,
  onPrefetchData,
  onMouseEnter,
  onFocus,
  ...rest
}) => {
  const handlePrefetch = () => {
    // Jalankan prefetching secara idempotent dan background-priority
    if (onPrefetchModule) {
      onPrefetchModule().catch(() => {
        // Silent catch untuk module prefetching issues
      });
    }
    if (onPrefetchData) {
      onPrefetchData().catch(() => {
        // Silent catch untuk data prefetching issues
      });
    }
  };

  return (
    <Link
      to={to}
      onMouseEnter={(e) => {
        handlePrefetch();
        onMouseEnter?.(e);
      }}
      onFocus={(e) => {
        handlePrefetch();
        onFocus?.(e);
      }}
      {...rest}
    >
      {children}
    </Link>
  );
};
```

#### Billing Feature Module Types & Loader (`src/features/billing/api/billingLoader.ts`)
```tsx
import { LoaderFunctionArgs, redirect } from 'react-router-dom';
import { getCurrentUserSession } from '../../../shared/api/client';
import { BillingPayload } from '../types';

export const loadBillingModule = () => import('../pages/BillingDashboardPage');

export async function billingDashboardLoader({ request }: LoaderFunctionArgs): Promise<BillingPayload> {
  const session = await getCurrentUserSession();

  // Route Guard level loader: Cegah eksekusi fetch data jika unauthorized
  if (!session.isAuthenticated) {
    const url = new URL(request.url);
    throw redirect(`/auth/login?redirectTo=${encodeURIComponent(url.pathname)}`);
  }

  // RBAC Permission Check
  if (!session.roles.includes('FINANCE_ADMIN') && !session.roles.includes('SUPER_ADMIN')) {
    throw new Response('Akses Ditolak: Memerlukan Role Keuangan', { 
      status: 403, 
      statusText: 'Forbidden Access' 
    });
  }

  // Parallel network invocation
  const [invoicesRes, balanceRes] = await Promise.all([
    fetch('/api/v1/billing/invoices'),
    fetch('/api/v1/billing/balance'),
  ]);

  if (!invoicesRes.ok || !balanceRes.ok) {
    throw new Response('Gagal sinkronisasi data billing.', { status: 502 });
  }

  const invoices = await invoicesRes.json();
  const balance = await balanceRes.json();

  return {
    invoices,
    balance,
    generatedAt: new Date().toISOString(),
  };
}
```

#### Shared API Mock (`src/shared/api/client.ts`)
```tsx
export interface UserSession {
  isAuthenticated: boolean;
  userId: string | null;
  roles: string[];
}

export async function getCurrentUserSession(): Promise<UserSession> {
  // Simulasi cek auth via in-memory/cookie cache
  return {
    isAuthenticated: true,
    userId: 'usr_enterprise_99',
    roles: ['FINANCE_ADMIN'],
  };
}
```

#### Feature Types (`src/features/billing/types.ts`)
```tsx
export interface Invoice {
  id: string;
  amount: number;
  currency: string;
  status: 'PAID' | 'PENDING' | 'OVERDUE';
}

export interface BillingBalance {
  currentBalance: number;
  creditLimit: number;
}

export interface BillingPayload {
  invoices: Invoice[];
  balance: BillingBalance;
  generatedAt: string;
}
```

#### Page Component (`src/features/billing/pages/BillingDashboardPage.tsx`)
```tsx
import React from 'react';
import { useLoaderData, useNavigation } from 'react-router-dom';
import { BillingPayload } from '../types';

export const BillingDashboardPage: React.FC = () => {
  const data = useLoaderData() as BillingPayload;
  const navigation = useNavigation();

  const isNavigating = navigation.state === 'loading';

  return (
    <div style={{ opacity: isNavigating ? 0.7 : 1, transition: 'opacity 200ms ease' }}>
      <header>
        <h1>Portal Penagihan & Keuangan</h1>
        <p>Sinkronisasi terakhir: {new Date(data.generatedAt).toLocaleTimeString()}</p>
      </header>

      <section aria-labelledby="balance-heading">
        <h2 id="balance-heading">Ringkasan Neraca</h2>
        <div>Saldo Terpakai: {data.balance.currentBalance} USD</div>
        <div>Limit Kredit: {data.balance.creditLimit} USD</div>
      </section>

      <section aria-labelledby="invoices-heading">
        <h2 id="invoices-heading">Daftar Tagihan</h2>
        <ul>
          {data.invoices.map((inv) => (
            <li key={inv.id}>
              {inv.id} — {inv.amount} {inv.currency} [{inv.status}]
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
};

export default BillingDashboardPage;
```

#### Route Level Error Boundary Component (`src/app/routes/RouteErrorBoundary.tsx`)
```tsx
import React from 'react';
import { useRouteError, isRouteErrorResponse, useNavigate } from 'react-router-dom';

export const RouteErrorBoundary: React.FC = () => {
  const error = useRouteError();
  const navigate = useNavigate();

  let title = 'Kesalahan Sistem';
  let message = 'Terjadi galat yang tidak terduga pada aplikasi.';
  let statusCode = 500;

  if (isRouteErrorResponse(error)) {
    statusCode = error.status;
    title = `Kesalahan Navigasi (${error.status})`;
    message = error.data || error.statusText;
  } else if (error instanceof Error) {
    message = error.message;
  }

  return (
    <div role="alert" style={{ padding: '2rem', border: '1px solid #dc2626', borderRadius: '8px' }}>
      <h2 style={{ color: '#dc2626' }}>{title}</h2>
      <p>{message}</p>
      <p>Kode Status: {statusCode}</p>
      <button onClick={() => navigate(-1)}>Kembali ke Halaman Sebelumnya</button>
      <button onClick={() => window.location.reload()} style={{ marginLeft: '1rem' }}>
        Muat Ulang Aplikasi
      </button>
    </div>
  );
};
```

#### Main Routing Registry (`src/app/routes/AppRouter.tsx`)
```tsx
import React, { Suspense } from 'react';
import { createBrowserRouter, RouterProvider, Outlet } from 'react-router-dom';
import { billingDashboardLoader, loadBillingModule } from '../../features/billing/api/billingLoader';
import { RouteErrorBoundary } from './RouteErrorBoundary';
import { PrefetchLink } from '../../shared/ui/PrefetchLink';

const BillingDashboardLazy = React.lazy(loadBillingModule);

const RootLayout: React.FC = () => {
  return (
    <div className="enterprise-layout">
      <nav style={{ display: 'flex', gap: '1rem', padding: '1rem', background: '#f4f4f5' }}>
        <PrefetchLink to="/">Beranda</PrefetchLink>
        <PrefetchLink
          to="/finance/billing"
          onPrefetchModule={loadBillingModule}
          onPrefetchData={() =>
            billingDashboardLoader({
              request: new Request(window.location.origin + '/finance/billing'),
              params: {},
            })
          }
        >
          Keuangan (Prefetched)
        </PrefetchLink>
      </nav>
      <main style={{ padding: '1.5rem' }}>
        <Outlet />
      </main>
    </div>
  );
};

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        index: true,
        element: <div>Selamat datang di Sistem Intranet Enterprise.</div>,
      },
      {
        path: 'finance/billing',
        loader: billingDashboardLoader,
        errorElement: <RouteErrorBoundary />,
        element: (
          <Suspense fallback={<div>Memuat antarmuka Billing Engine...</div>}>
            <BillingDashboardLazy />
          </Suspense>
        ),
      },
    ],
  },
]);

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Global FinTech Platform Migrasi Monolitik ke Dynamic Routing

* **Konteks**: Platform pemrosesan pembayaran skala enterprise dengan 400+ rute, dashboard manajemen fraud berbasis bagan analitik berat, integrasi ekspor PDF/Excel, dan portal audit regulasi.
* **Kondisi Awal (The Bottleneck)**:
  * Single *initial JS bundle* mencapai **16.8 MB** (uncompressed).
  * Pengguna di jaringan seluler mengalami LCP $\approx$ 11.2 detik.
  * Navigasi antar rute lambat karena pola "Fetch-on-Render" menghasilkan rangkaian HTTP waterfalls yang dalam (Rata-rata 4 tingkat waterfall per rute: Auth $\rightarrow$ UserProfile $\rightarrow$ PageLayout $\rightarrow$ DomainData).
  * Tim teknik yang terdiri dari 35+ engineer sering mengalami *merge conflicts* pada satu file `routes.tsx` berukuran 4,000 baris.

### Solusi Arsitektural yang Diterapkan:
1. **Penerapan FSD Code Splitting**:
   * Modul audit, pelaporan, dan billing diisolasi ke dalam dynamic chunks independen via Rollup manual chunks grouping di `vite.config.ts`:
   ```typescript
   build: {
     rollupOptions: {
       output: {
         manualChunks: {
           vendor_charts: ['echarts', 'zrender'],
           vendor_data: ['ag-grid-community', 'ag-grid-react'],
           vendor_pdf: ['pdfmake'],
         }
       }
     }
   }
   ```
2. **Pola Data-Loader Paralel Mengeliminasi Waterfalls**:
   * Seluruh lifecycle fetch data dipindahkan dari `useEffect` ke `route.loader`. Data rute anak dieksekusi simultan bersama data rute induk via React Router internal parallel fetch engine.
3. **Intent-Based Predictive Module Prefetching**:
   * Pada komponen navigasi sidebar, diterapkan event listener *hover* dan *focus* yang memanggil fungsi dynamic import (`import(...)`) 150ms sebelum klik selesai terjadi.

### Hasil Metrik (Before vs After):
* **Initial Bundle Size**: 16.8 MB $\rightarrow$ **184 KB** (Penurunan **98.9%**).
* **Largest Contentful Paint (LCP)**: 11.2s $\rightarrow$ **1.1s** (pada skenario koneksi Fast 3G).
* **Interaction to Next Paint (INP)**: 450ms $\rightarrow$ **48ms**.
* **Merge Conflicts Routing**: Turun hingga nol karena konfigurasi rute dipecah secara terdesentralisasi di setiap modul fitur domain.

---

## 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Biaya / Trade-off | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **Granular Code-Splitting (Split tiap komponen)** | Initial bundle minimal, TTI sangat cepat untuk first-view. | Masalah *network latency* berulang (banyak HTTP requests) saat navigasi; resiko *waterfall chunks*. | Kelompokkan dependensi terkait via Rollup `manualChunks` atau batasi split hanya pada level batas rute (*route boundary*). |
| **Data Loaders (Render-as-you-fetch)** | Zero layout shift; data dan kode didownload paralel; UI tidak berkedip. | Navigasi URL tertunda sesaat hingga loader selesai (*perceived latency* jika API lambat). | Gunakan `defer()` / React Suspense Streaming pada loader agar data lambat tidak memblokir render instan. |
| **Predictive Prefetching on Hover** | Navigasi terasa instan (0ms perceived latency); data sudah siap di cache. | Pemborosan kuota data/bandwidth jika user sekadar menyapu kursor tanpa mengklik link. | Terapkan debounce interval (min. 60–100ms) sebelum eksekusi prefetch atau batasi via flag `navigator.connection.saveData`. |
| **Domain-Driven Directory (FSD)** | Kemudahan isolasi tim, skalabilitas tinggi, decoupling antar modul. | Menambah kedalaman path impor (*import depth*), beban konfigurasi path aliases. | Terapkan eslint-plugin-boundaries dan alias `@shared`, `@features` pada `tsconfig.json`. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Waterfall Module Loading pada Nested Dynamic Routes
* **Gejala**: Halaman memuat layout, lalu jeda 400ms, memuat sub-layout, jeda lagi 300ms, baru memuat view utama.
* **Penyebab**: Menumpuk `React.lazy` di rute anak tanpa mendefinisikan parallel prefetching di level loader induk.
* **Solusi**: Pastikan bundle child rute dipanggil sejajar menggunakan dynamic import Promise di dalam loader rute, atau kelompokkan bundle segmen tersebut via bundler chunk grouping.

### 2. State Loss / Layout Re-Mount Loop
* **Gejala**: Sidebar atau form input kehilangan state input pengguna saat URL berpindah antar tab anak.
* **Penyebab**: Mendeklarasikan komponen `Layout` di dalam level rute anak, sehingga layout ter-unmount dan ter-mount ulang pada setiap navigasi segmen.
* **Solusi**: Angkat layout ke posisi *Parent Route* sebagai layout route murni (`<Outlet />`), pisahkan view dinamis murni sebagai child route elements.

### 3. Chunk Load Error saat Deployment Baru (*Stale Assets*)
* **Gejala**: Pengguna lama yang masih membuka aplikasi mengalami `ChunkLoadError: Loading chunk failed` saat berpindah halaman pasca rilis produksi baru.
* **Penyebab**: Hash file JS lama telah dihapus dari CDN/server hosting oleh file deployment baru.
* **Solusi**: Bungkus dynamic import dengan *auto-reload fallback recovery engine*:
```typescript
function lazyWithRetry(componentImport: () => Promise<any>) {
  return React.lazy(async () => {
    const pageHasBeenForceRefreshed = JSON.parse(
      window.sessionStorage.getItem('chunk_force_refreshed') || 'false'
    );

    try {
      const component = await componentImport();
      window.sessionStorage.setItem('chunk_force_refreshed', 'false');
      return component;
    } catch (error) {
      if (!pageHasBeenForceRefreshed) {
        window.sessionStorage.setItem('chunk_force_refreshed', 'true');
        window.location.reload();
        return new Promise(() => {}); // Hold rendering while reloading
      }
      throw error;
    }
  });
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Kriteria Chunk Size**: Main entry chunk tidak boleh melampaui **200 KB** (gzipped).
- [ ] **Isolasi Error Granular**: Setiap route leaf wajib memiliki `errorElement` untuk mencegah error fatal meruntuhkan seluruh pohon aplikasi (*fail-safe isolation*).
- [ ] **Data Fetching via Loader**: Hilangkan semua pemanggilan data `fetch`/`axios` yang berada di dalam `useEffect` komponen halaman utama rute.
- [ ] **Data Deferral**: Gunakan utilitas `defer` dari React Router untuk data analitik sekunder yang lambat agar tidak menahan resolusi LCP rute utama.
- [ ] **Type-Safe Route Identifiers**: Hindari *hardcoded string paths* di dalam UI. Gunakan skema *typed path generators*.
- [ ] **Network-Aware Prefetching**: Periksa status hemat daya data pengguna sebelum eksekusi prefetch:
  ```typescript
  const isDataSaver = (navigator as any).connection?.saveData === true;
  if (!isDataSaver) { triggerPrefetch(); }
  ```
- [ ] **Batas Suspense Proporsional**: Gunakan Suspense skeleton loader yang memiliki dimensi geometris identik dengan elemen target asli untuk mencegah *Cumulative Layout Shift* (CLS).

---

## 12. Hands-on Practice

Buatlah implementasi arsitektur routing modular terpisah di folder target `hands-on/m02/`.

### Langkah 1: Inisialisasi Workspace
```bash
mkdir -p hands-on/m02
cd hands-on/m02
npm create vite@latest . -- --template react-ts
npm install react-router-dom
```

### Langkah 2: Buat Skema Modul Admin & Analisis
Buat file `src/features/analytics/AnalyticsModule.tsx`:
```tsx
import React from 'react';
import { useLoaderData } from 'react-router-dom';

export async function analyticsLoader() {
  await new Promise((resolve) => setTimeout(resolve, 800)); // Simulasi latensi jaringan
  return { cpuUsage: '22%', memoryUsage: '1.4GB', activeThreads: 14 };
}

export default function AnalyticsModule() {
  const stats = useLoaderData() as { cpuUsage: string; memoryUsage: string; activeThreads: number };

  return (
    <div style={{ padding: '1rem', border: '1px solid #0284c7', borderRadius: '4px' }}>
      <h3>Metrik Realtime Server</h3>
      <p>CPU: {stats.cpuUsage}</p>
      <p>Memori: {stats.memoryUsage}</p>
      <p>Thread: {stats.activeThreads}</p>
    </div>
  );
}
```

### Langkah 3: Hubungkan pada Master Router
Perbarui `src/App.tsx`:
```tsx
import React, { Suspense } from 'react';
import { createBrowserRouter, RouterProvider, Link, Outlet } from 'react-router-dom';

const AnalyticsView = React.lazy(() => import('./features/analytics/AnalyticsModule'));

const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <div style={{ fontFamily: 'sans-serif', margin: '2rem' }}>
        <nav style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
          <Link to="/">Home</Link>
          <Link to="/analytics">Analytics (Split Chunk)</Link>
        </nav>
        <Outlet />
      </div>
    ),
    children: [
      { index: true, element: <div>Halaman Index Publik.</div> },
      {
        path: 'analytics',
        lazy: async () => {
          // Dynamic loader resolution natively via React Router v6.4+
          const { analyticsLoader, default: Component } = await import('./features/analytics/AnalyticsModule');
          return {
            loader: analyticsLoader,
            Component,
          };
        },
      },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
```

### Langkah 4: Uji dan Verifikasi Chunking
Jalankan di terminal:
```bash
npm run build
```
Periksa output folder `dist/assets/`. Pastikan terdapat file chunk terpisah untuk modul Analytics (misal: `AnalyticsModule-[hash].js`), yang membuktikan bahwa kode modul tidak bercampur dengan entry point `index-[hash].js`.

---

## 13. Exercise

### Level Easy: Dynamic Route Guard dengan Parameter Status
Modifikasi skema guard rute agar menerima parameter array `requiredRoles: string[]`. Jika sesi pengguna memiliki setidaknya satu peran yang cocok, izinkan akses ke sub-rute; jika tidak cocok sama sekali, lempar `Response` HTTP status `403 Forbidden` terstruktur lengkap dengan pesan informatif pada loader data.

### Level Medium: Custom Hook Intent-Driven Prefetch
Buat custom React hook `useIntentPrefetch(routePath, moduleLoaderFn, dataLoaderFn)`:
* Hook harus mengembalikan objek event handler `onMouseEnter` dan `onFocus`.
* Pasang mekanisme throttle: Prefetch tidak boleh dieksekusi jika kursor menyapu elemen link di bawah 80 milidetik (*hover intent validation*).
* Pastikan hasil promise di-cache di level memory dictionary sederhana agar fetch tidak berulang jika link di-hover berkali-kali.

### Level Hard: Feature-Sliced Dynamic Route Injector
Bangun sebuah mekanisme *Decentralized Route Registry* di mana modul fitur dapat mendaftarkan rute miliknya sendiri ke master router tanpa modifikasi langsung pada file router inti. 
* Buat modul registrasi kontraktual menggunakan TypeScript interface `EnterpriseRouteModule`.
* Setiap modul fitur wajib mengekspor: `basePath`, `guards`, `loader`, dan lazy component tree.
* Implementasikan logic penggabung (*merging engine*) yang mengompilasi seluruh konfigurasi modular ini menjadi satu kesatuan instance `RouteObject[]` yang valid untuk `createBrowserRouter`.

---

## 14. Challenge

**Skenario Tantangan**: Arsitektur Multi-Tier Offline-First Route Engine dengan Micro-Fallbacks.

Rancang dan bangun sebuah routing layout arsitektural enterprise dengan batasan teknis berikut:
1. **Zero-Waterfall Lazy Tree**: Aplikasi memiliki 3 level nested routes (`/workspace/:wsId/project/:pId/board`). Ketiga level memuat komponen chunk berbeda dan loader independen. Tidak boleh ada satu pun child route yang menunggu eksekusi modul/loader child lainnya (*harus ditrigger paralel penuh via bundler dan Data API*).
2. **Offline-Resilient Stale While Revalidate (SWR) Loader**: Jika koneksi jaringan offline atau API mengembalikan 500/504, loader rute harus secara instan mengambil snapshot terakhir data dari IndexedDB/CacheStorage, merender layout tanpa error boundary fatal, dan menampilkan notifikasi ambang bahwa "Data ditampilkan dari cache offline".
3. **Chunk Prefetching Intersection Observer**: Bangun prefetcher berbasis *IntersectionObserver* yang secara otomatis mulai mendownload JS chunk dan data loader rute begitu Link navigasi masuk ke dalam viewport layar pengguna minimal sebesar 25%, dengan syarat browser tidak berada pada mode *Data Saver*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara implementasi `React.lazy` dengan dynamic import `import()` biasa?**
   * *Jawaban*: `import()` adalah sintaks level ECMAScript native yang mengembalikan Promise modul. Sedangkan `React.lazy` adalah wrapper React yang mengintegrasikan Promise hasil dynamic import tersebut ke dalam siklus rekonsiliasi Suspense engine.
2. **Mengapa pemanggilan data loader di React Router v6.4+ lebih unggul dibanding `useEffect` untuk pemuatan data awal halaman?**
   * *Jawaban*: Data loader berjalan paralel dengan resolusi modul sebelum atau bersamaan dengan fase render (Render-as-you-Fetch), mengeliminasi *network waterfall* yang biasanya terjadi saat fetch ditahan hingga komponen selesai ter-mount.
3. **Apa kegunaan prop `errorElement` pada konfigurasi objek rute?**
   * *Jawaban*: Menyediakan batasan error (*error boundary*) lokal untuk segmen rute terkait, sehingga kegagalan eksekusi loader atau render pada rute tersebut tidak meruntuhkan seluruh layout rute induk.
4. **Apa yang dimaksud dengan chunk splitting pada bundler modern?**
   * *Jawaban*: Proses pemecahan satu file bundle JavaScript besar menjadi beberapa berkas bundle kecil (*chunks*) terpisah yang dapat diunduh oleh klien secara *on-demand* sesuai kebutuhan.
5. **Apa fungsi fungsi `defer()` di dalam data loader?**
   * *Jawaban*: Memungkinkan loader untuk mengembalikan data kritis secara instan sambil menunda (*streaming*) data Promise yang lambat agar dirender menggunakan `<Suspense>` dan `<Await>` tanpa memblokir transisi rute.

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana cara mencegah memory leak atau pemborosan resource saat mengimplementasikan hover-based prefetching?**
   * *Jawaban*: Terapkan validasi *hover intent* dengan jeda waktu (misal 80–150ms) menggunakan timer, simpan cache Promise yang sedang berjalan agar request yang sama tidak diduplikasi (*deduplication*), dan batalkan operasi bila kursor keluar sebelum waktu delay terpenuhi.
2. **Mengapa kita harus melempar (*throw*) `Response` (seperti `throw redirect(...)` atau `throw new Response(...)`) di dalam loader daripada melakukan navigasi manual via hook `useNavigate`?**
   * *Jawaban*: Hook React seperti `useNavigate` tidak dapat dipanggil di luar konteks komponen React (loader berjalan di luar siklus hidup render komponen). Melempar `Response` memicu interrupt langsung di internal state machine router sebelum komponen apapun dirender.
3. **Bagaimana Rollup/Vite memisahkan modul pihak ketiga (*vendor*) ke dalam chunk terpisah menggunakan opsi konfigurasi `manualChunks`?**
   * *Jawaban*: Rollup mengevaluasi ID modul dari *module graph*. Jika path modul cocok dengan kriteria dalam fungsi atau objek `manualChunks` (misalnya terdapat di `node_modules/`), modul tersebut dialokasikan ke nama chunk target yang ditentukan secara deterministik.
4. **Apa yang menyebabkan terjadinya layout re-mounting ketika pengguna berpindah rute yang memiliki header dan sidebar yang sama?**
   * *Jawaban*: Header dan sidebar didefinisikan ulang secara redundan di dalam masing-masing komponen rute daun (*leaf route*), alih-alih didefinisikan satu kali pada *Parent Layout Route* yang memanfaatkan komponen `<Outlet />`.
5. **Bagaimana cara menangani type-safety secara komprehensif pada data yang dikembalikan oleh hook `useLoaderData()`?**
   * *Jawaban*: Ekspor tipe balik dari loader menggunakan utilitas tipe TypeScript: `export type LoaderData = Awaited<ReturnType<typeof myLoader>>`, kemudian lakukan *type casting* atau buat custom hook wrapper: `const data = useLoaderData() as LoaderData`.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

#### Skenario 1: Bug Layar Putih (*Blank Screen*) Pasca Deployment
* **Kasus**: Setelah tim merilis versi baru ke server produksi, pengguna yang sedang aktif membuka aplikasi melaporkan layar mendadak menjadi putih (blank) saat mereka mengklik menu baru. Console browser mencatat `ChunkLoadError: Failed to fetch dynamically imported module`.
* **Analisis & Solusi**: Masalah ini timbul karena hash nama file chunk lama pada CDN telah terhapus/ditimpa oleh deployment baru, sementara client masih memegang referensi hash lama. Solusinya:
  1. Tambahkan wrapper error boundary global yang menangkap error import modul dan melakukan force reload halaman satu kali via `window.location.reload()`.
  2. Di level infrastruktur CDN, terapkan *grace period* dengan tetap menyimpan file chunk versi $N-1$ selama beberapa jam setelah deployment versi $N$.

#### Skenario 2: Token Kedaluwarsa pada Navigasi Rute Cepat
* **Kasus**: Aplikasi menggunakan JWT. Pengguna mengklik rute yang membutuhkan data sensitif tepat saat token kedaluwarsa. Loader rute melempar error status 401. Namun, aplikasi malah terhenti pada error boundary tanpa mengarahkan pengguna ke halaman login secara elegan.
* **Analisis & Solusi**: Loader gagal menangani exception status 401 dari fetch client. Solusinya:
  Di dalam interceptor client HTTP atau langsung di dalam loader, tangkap response 401 dan segera konversi menjadi throw redirect resmi React Router:
  ```typescript
  if (response.status === 401) {
    throw redirect(`/login?expired=true&redirectTo=${encodeURIComponent(new URL(request.url).pathname)}`);
  }
  ```
  Ini menghentikan rantai pemanggilan loader lainnya secara serempak dan membawa browser ke login state tanpa menampilkan UI rusak ke user.

#### Skenario 3: Penurunan Metrik Interaction to Next Paint (INP) saat Navigasi Rute Kompleks
* **Kasus**: Modul pelaporan analitik keuangan memiliki ribuan DOM node. Begitu data loader selesai memuat data, navigasi rute membeku (*freezes*) selama 800ms, memicu peringatan INP buruk pada Google Core Web Vitals.
* **Analisis & Solusi**: Pembekuan terjadi pada main thread saat React mengeksekusi sinkronisasi dan mounting serentak untuk ribuan node DOM. Solusinya:
  1. Pecah rendering grid tabel kompleks menggunakan teknik virtualisasi list (`@tanstack/react-virtual`).
  2. Terapkan hook `useDeferredValue` atau `useTransition` pada data array yang sangat besar agar pembaruan tree UI berat didelegasikan sebagai prioritas *non-blocking* konkuren, menjaga responsivitas input browser tetap lancar di bawah 50ms.

---

## 16. Summary

1. **Evolusi Routing SPA**: Paradigma routing modern telah beralih dari pola *Fetch-on-Render* yang lambat dan rentan waterfall menjadi pola *Render-as-you-Fetch* berbasis Data APIs (`createBrowserRouter`, `loaders`).
2. **Efisiensi Kode Ekstrem**: Code-splitting bukan sekadar menambahkan `React.lazy`, melainkan strategi holistik yang mencakup pembagian modul berbasis domain, chunk grouping pada level bundler, dan *intent-driven prefetching*.
3. **Pemisahan Perhatian (Separation of Concerns)**: Pengorganisasian kode berbasis *Feature-Sliced Design* memastikan dependensi rute, status otentikasi, schema validasi, dan view UI terisolasi rapi, mencegah fragmentasi dan degradasi arsitektur seiring bertambahnya skala aplikasi enterprise.
4. **Ketahanan Produksi**: Sistem navigasi kelas produksi wajib mengantisipasi *stale chunks*, menerapkan kontrol akses peran (RBAC) pada lapis sebelum eksekusi rute (*pre-render layer*), serta mengisolasi titik kegagalan menggunakan *Granular Error Boundaries*.