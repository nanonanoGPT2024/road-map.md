# Routing Lanjutan, Parallel, & Intercepting Patterns

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** `03-Frontend-and-Mobile`
* **Track:** Next.js Enterprise Frontend Architecture
* **Topik:** Bab 02 Module 01: Routing Lanjutan, Parallel, & Intercepting Patterns
* **Target Audience:** Senior Frontend Engineers, Technical Architects, Fullstack Engineers
* **Prasyarat Pengetahuan:** Next.js App Router Fundamentals, React Server Components (RSC) vs Client Components, Suspense boundary semantics, HTTP/DOM Navigation lifecycle.

---

## SEKSI 02 — LEARNING OBJECTIVES

1. Menguasai arsitektur Router Tree di Next.js App Router, mencakup resolusi parallel slots dan intercepting token matching.
2. Mengimplementasikan UI multi-panel independen menggunakan Named Parallel Slots (`@slot`) dengan isolasi state dan fallback stream (`default.tsx`).
3. Mengembangkan pola routing kontekstual kompleks (*modal-over-page*, *split-view master-detail*) dengan Intercepting Routes (`(.)`, `(..)`, `(..)(..)`, `(...)`).
4. Mengendalikan siklus hidup Client-Side Navigation Cache dan konsistensi revalidasi data pada sub-tree navigasi parallel.
5. Membangun sistem modal URL-driven berskala produksi dengan jaminan deep-linking langsung, reload resilience, dan aksesibilitas (WAI-ARIA).
6. Mencegah memory leaks dan *unwanted state retention* saat unmounting parallel slot layouts.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam Pages Router tradisional atau vanilla React Single Page Applications (SPA), UI modal atau panel samping umumnya direpresentasikan sebagai *ephemeral state* (`useState(isOpen)`). Mental model ini merusak arsitektur web modern karena tiga alasan:

1. **State Terisolasi dari URL:** Kehilangan kapabilitas deep-linking, bookmarking, dan riwayat navigasi browser (Back/Forward buttons).
2. **Bundle Bloat:** Kode modal sering kali diimpor dan di-*bundle* langsung pada layout utama, membebani First Input Delay (FID) dan Largest Contentful Paint (LCP).
3. **Ketergantungan Eksekusi Klien:** Bergantung pada runtime JavaScript klien untuk merender layer view.

Next.js App Router menggeser paradigma ini ke **URL-as-Single-Source-of-Truth** melalui *Parallel Routing* dan *Intercepting Routing*. 

* **Parallel Routing (`@slot`):** Bukan sekadar props injection biasa, melainkan cabang independen dari *Fiber tree* yang dirender secara konkuren oleh server. Setiap slot memiliki boundary eksekusi, loading, dan error lifecycle sendiri.
* **Intercepting Routing (`(..)pattern`):** Mekanisme routing contextual proxying. Router mengevaluasi rute asal (initiator). Jika navigasi terjadi secara client-side (`next/link` atau `useRouter`), router menyajikan rute intersepsi tanpa membuang context layout sebelumnya. Jika navigasi terjadi via *Hard Reload* (F5) atau direct request HTTP GET, Next.js menyajikan rute kanonikal aslinya.

```
       [ Client Side Transition ]
  Feed Page (/feed) ------------> Intercepted Route (@modal/(.)photo/[id])
        |                               (Overlaid via Parallel Slot)
        |
  [ Hard Page Refresh / Direct Hit ]
  URL Request (/photo/[id]) ------> Canonical Full Page Route (/photo/[id])
                                        (Standalone Clean View)
```

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Parallel & Intercepting Pipeline Internal

```
+--------------------------------------------------------------------------------------------------+
| BROWSER ACTION                                                                                   |
| User clicks <Link href="/photos/101"> inside /feed                                               |
+--------------------------------------------------------------------------------------------------+
                                           |
                                           v
+--------------------------------------------------------------------------------------------------+
| NEXT.JS CLIENT ROUTER EVALUATION ENGINE                                                          |
| 1. Periksa route segment tree saat ini: ['feed']                                                 |
| 2. Resolusi target: '/photos/101'                                                                |
| 3. Deteksi Interception Rules pada Segment:                                                      |
|    - Cek eksistensi direktori layout aktif                                                       |
|    - Ditemukan: app/feed/@modal/(.)photos/[id]                                                   |
+--------------------------------------------------------------------------------------------------+
                                           |
             +-----------------------------+-----------------------------+
             |                                                           |
      [ Soft Navigation ]                                         [ Hard Refresh ]
             |                                                           |
             v                                                           v
+------------------------------------------+    +--------------------------------------------------+
| RSC FETCH ENGINE (FLIGHT PROTOCOL)       |    | HTTP GET REQUEST ke Server Engine                |
| - Header: RSC=1                          |    | URL: /photos/101                                 |
| - Header: Next-Url: /feed                |    +--------------------------------------------------+
+------------------------------------------+                             |
             |                                                           v
             v                                          +----------------------------------+
+------------------------------------------+    | RENDER FULL PAGE HIERARCHY       |
| PARALLEL SLOT RESOLUTION                 |    | app/layout.tsx                   |
| 1. Layout aktif (/feed) tetap mounted    |    |   └── app/photos/[id]/page.tsx   |
| 2. Slot `@modal` diarahkan ke:           |    +----------------------------------+
|    app/feed/@modal/(.)photos/[id]        |                             |
| 3. Main children slot:                   |                             v
|    Tetap merender /feed (dipertahankan)  |                 +-----------------------+
| 4. Parallel slots lainnya:               |                 | Render Complete Document|
|    Fallback ke default.tsx jika tdk match|                 | (Clean Standalone DOM)|
+------------------------------------------+                 +-----------------------+
             |
             v
+------------------------------------------+
| REACT CLIENT RECONCILER                  |
| 1. Mempertahankan state feed tree        |
| 2. Mengisi slot `@modal` dengan RSC tree |
|    hasil render intercepted view         |
| 3. History pushState: URL jadi /photos/101|
+------------------------------------------+
```

### Dynamic Tree Matrix

```
app/
├── layout.tsx                <-- Root Layout (Menerima slots: { children, modal })
├── default.tsx               <-- Root default slot fallback (CRITICAL)
├── feed/
│   ├── page.tsx              <-- Halaman /feed (children)
│   └── @modal/               <-- Named Parallel Slot
│       ├── default.tsx       <-- Fallback ketika rute modal tidak aktif (mengembalikan null)
│       └── (.)photos/
│           └── [id]/
│               └── page.tsx  <-- Intercepted view (Overlayed modal)
└── photos/
    └── [id]/
        └── page.tsx          <-- Canonical view (Standalone page)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The `@slot` Directory Convention

Simbol `@` menandai *named parallel slot*. Slot tidak mempengaruhi segmen URL path. Segmen `app/@modal/settings/page.tsx` akan diakses melalui URL `/settings`, bukan `/@modal/settings`.

* Layout pada level hierarki yang sama akan menerima slot ini sebagai props:
  ```typescript
  export default function Layout(props: {
    children: React.ReactNode;
    modal: React.ReactNode;
  }) { ... }
  ```
* Properti `children` secara struktural adalah slot implisit: `@children`.

### 2. Segment Interception Matching Rules

Prefix interception bertindak relatif terhadap letak rute di dalam sistem direktori:

| Notasi Pattern | Target Resolusi | Penjelasan Teknis |
|---|---|---|
| `(.)` | Level yang sama | Mengintersepsi segmen pada level direktori yang identik dengan slot |
| `(..)` | Satu level di atas | Mengintersepsi segmen dari parent direktori (1 tingkat ke atas) |
| `(..)(..)` | Dua level di atas | Mengintersepsi segmen dari 2 tingkat direktori ke atas |
| `(...)` | Dari root `app` | Mengintersepsi segmen langsung dari root direktori aplikasi |

*Peringatan Direktori vs Segmen Rute:* Notasi `(..)` mengevaluasi segmen rute, bukan direktori filesystem. Jika terdapat Route Groups `(marketing)`, grup tersebut tidak dihitung sebagai level hierarki segmen navigasi.

### 3. Flight Router State & The Invalidation Contract

Ketika client melakukan navigasi melalui `next/link`, Next.js menyertakan metadata rute aktif via HTTP Request Header `Next-Router-State-Tree`. 

Server membaca state tree tersebut, menghitung perbedaan (RSC diff), lalu mengalirkan payload Flight format. Jika layout parent mendefinisikan parallel slot, tetapi URL target tidak memiliki kecocokan segment pada slot tersebut:
* Pada navigasi client (*soft navigation*): Next.js mempertahankan visual state slot sebelumnya jika tidak ada instruksi unmount eksplisit.
* Pada direct request (*hard navigation*): Next.js **wajib** membaca file `default.tsx`. Jika `default.tsx` tidak ditemukan pada tingkat direktori tersebut, Next.js akan melempar status **404 Not Found**.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Navigasi Deterministik vs Indeterminis: Masalah `default.tsx`

Salah satu titik kritis arsitektur Parallel Routes adalah handling terhadap *unmatched slots*.

Misalkan aplikasi memiliki struktur:
* Layout utama menerima `props.analytics` dan `props.team`.
* URL `/dashboard/team` merender UI tim pada slot `team`, tetapi tidak merender apapun pada slot `analytics`.

```typescript
// app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
  analytics,
  team,
}: {
  children: React.ReactNode;
  analytics: React.ReactNode;
  team: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <main className="col-span-1">{children}</main>
      <aside className="col-span-1">{team}</aside>
      <aside className="col-span-1">{analytics}</aside>
    </div>
  );
}
```

#### Skenario 1: Soft Navigation (Client-Side Transition)
User berada di `/dashboard` lalu mengklik link ke `/dashboard/team`. Router mengenali bahwa slot `analytics` tidak memiliki pembaruan untuk segmen `/dashboard/team`. Router mempertahankan sub-tree RSC terakhir yang dirender pada slot `analytics`. State tidak hilang.

#### Skenario 2: Hard Reload (Browser Refresh F5 / Direct Hit via URL)
Browser mengosongkan memori DOM dan melakukan cold request ke server untuk `/dashboard/team`. Next.js merekonstruksi Router Cache dari nol. 
* Slot `team` -> Ditemukan: `app/dashboard/@team/page.tsx` (atau sub-path terkait).
* Slot `analytics` -> Tidak ditemukan segmen yang cocok untuk `/dashboard/team`.
* Server memeriksa keberadaan `app/dashboard/@analytics/default.tsx`.
  * **Jika ada:** Mengembalikan output komponen default tersebut (misal `null`).
  * **Jika TIDAK ada:** Next.js membatalkan rendering seluruh layout dan mengembalikan response status **404 Not Found**.

*Konklusi Arsitektural:* File `default.tsx` adalah *mandatory fallback boundary* untuk setiap Named Parallel Slot guna menjamin idempotensi request HTTP GET.

### Interception Matching Boundary Execution

Bagaimana server Next.js membedakan render Intercepted Route vs Canonical Route ketika URL-nya sama?

Mekanisme ini diatur via HTTP Request Headers:
1. `Next-Url`: Berisi URL asal tempat navigasi dimulai.
2. `RSC`: Bernilai `1` menandakan payload yang diminta adalah RSC Flight data stream, bukan static HTML shell.

Ketika server menerima request URL `/photos/42`:
* Jika `Next-Url: /feed` disertakan dalam header, engine mendeteksi bahwa segment `/photos/42` memiliki file interceptor di level feed: `app/feed/@modal/(.)photos/[id]/page.tsx`. Server memproses interceptor tersebut dan mengabaikan `app/photos/[id]/page.tsx`.
* Jika header `Next-Url` tidak ada (akses via browser address bar langsung), interceptor di-bypass sepenuhnya. Server mengeksekusi `app/photos/[id]/page.tsx` menghasilkan full-page layout kanonikal.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah struktur file minimum sistem modal berbasis rute untuk galeri item:

```
app/
├── layout.tsx
├── default.tsx
├── page.tsx
├── @modal/
│   ├── default.tsx
│   └── (.)items/[id]/
│       └── page.tsx
└── items/
    └── [id]/
        └── page.tsx
```

### 1. Root Layout
```tsx
// app/layout.tsx
import React from 'react';

export default function RootLayout({
  children,
  modal,
}: {
  children: React.ReactNode;
  modal: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body className="antialiased bg-slate-950 text-slate-100">
        <header className="border-b border-slate-800 p-4">
          <h1 className="text-xl font-bold">App Catalog Engine</h1>
        </header>
        <main className="p-6">{children}</main>
        {modal}
      </body>
    </html>
  );
}
```

### 2. Root Default & Page
```tsx
// app/default.tsx
export default function Default() {
  return null;
}

// app/page.tsx
import Link from 'next/link';

export default function HomePage() {
  const items = [
    { id: '101', name: 'Microservice Gateway' },
    { id: '102', name: 'Distributed Cache' },
  ];

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Infrastruktur Unggulan</h2>
      <div className="flex gap-4">
        {items.map((item) => (
          <Link
            key={item.id}
            href={`/items/${item.id}`}
            className="p-4 bg-slate-900 border border-slate-700 rounded hover:border-blue-500 transition"
          >
            {item.name}
          </Link>
        ))}
      </div>
    </div>
  );
}
```

### 3. Parallel Slot Fallback (`@modal/default.tsx`)
```tsx
// app/@modal/default.tsx
export default function DefaultModalSlot() {
  return null;
}
```

### 4. Intercepted Route Modal (`@modal/(.)items/[id]/page.tsx`)
```tsx
// app/@modal/(.)items/[id]/page.tsx
import { ModalWrapper } from '@/components/ui/modal-wrapper';
import { getItemDetails } from '@/lib/data-service';
import { notFound } from 'next/navigation';

export default async function InterceptedItemModal({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const item = await getItemDetails(id);

  if (!item) {
    notFound();
  }

  return (
    <ModalWrapper title={`Modal: ${item.name}`}>
      <div className="p-4 space-y-2">
        <p className="text-sm text-slate-300">{item.description}</p>
        <span className="inline-block px-2 py-1 text-xs font-mono bg-blue-950 text-blue-400 border border-blue-800 rounded">
          Status: {item.status}
        </span>
      </div>
    </ModalWrapper>
  );
}
```

### 5. Canonical Standalone Route (`items/[id]/page.tsx`)
```tsx
// app/items/[id]/page.tsx
import { getItemDetails } from '@/lib/data-service';
import { notFound } from 'next/navigation';
import Link from 'next/link';

export default async function CanonicalItemPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const item = await getItemDetails(id);

  if (!item) {
    notFound();
  }

  return (
    <div className="max-w-2xl mx-auto py-12">
      <Link
        href="/"
        className="text-sm text-blue-400 hover:underline mb-6 inline-block"
      >
        &larr; Kembali ke Katalog Utama
      </Link>
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8">
        <h1 className="text-3xl font-bold mb-4">{item.name}</h1>
        <p className="text-slate-300 mb-6">{item.description}</p>
        <div className="border-t border-slate-800 pt-4 flex justify-between items-center text-sm text-slate-400">
          <span>Item ID: {id}</span>
          <span className="font-mono text-emerald-400">{item.status}</span>
        </div>
      </div>
    </div>
  );
}
```

### 6. Modal Wrapper Reusable Client Component
```tsx
// components/ui/modal-wrapper.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef } from 'react';

export function ModalWrapper({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const overlayRef = useRef<HTMLDivElement>(null);

  const onDismiss = useCallback(() => {
    router.back();
  }, [router]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDismiss();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onDismiss]);

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === overlayRef.current) onDismiss();
      }}
    >
      <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-xl overflow-hidden shadow-2xl">
        <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800">
          <h2 id="modal-title" className="text-lg font-semibold text-slate-100">
            {title}
          </h2>
          <button
            onClick={onDismiss}
            className="text-slate-400 hover:text-white transition"
            aria-label="Tutup dialog"
          >
            &times;
          </button>
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Kritis `app/@modal/(.)items/[id]/page.tsx`
* **Baris 1:** Tidak memiliki direktif `'use client'`. File ini merupakan **React Server Component (RSC)** murni.
* **Baris 8-12:**
  ```typescript
  export default async function InterceptedItemModal({
    params,
  }: {
    params: Promise<{ id: string }>;
  })
  ```
  Di Next.js versi terbaru, `params` adalah asynchronous `Promise`. Mengakses nilai parameter dinamis membutuhkan keyword `await params`.
* **Baris 13:**
  ```typescript
  const item = await getItemDetails(id);
  ```
  Eksekusi data fetching berjalan direct-to-database atau microservice backend dari server layer tanpa terekspos ke network inspector client.
* **Baris 15-17:**
  ```typescript
  if (!item) {
    notFound();
  }
  ```
  Jika identifikasi resource gagal, server langsung membangkitkan sinyal `notFound()`, yang akan ditangkap oleh boundary `not-found.tsx` terdekat tanpa membocorkan stack trace.
* **Baris 20:**
  ```typescript
  <ModalWrapper title={`Modal: ${item.name}`}>
  ```
  Komponen Client Wrapper membungkus RSC payload item. Dengan arsitektur ini, interactivity logic (event listeners, portal, state) terisolasi pada `ModalWrapper`, sedangkan konten data di-render secara server-side.

### Analisis Kritis `components/ui/modal-wrapper.tsx`
* **Baris 14-16:**
  ```typescript
  const onDismiss = useCallback(() => {
    router.back();
  }, [router]);
  ```
  Menggunakan `router.back()` alih-alih `router.push('/')` sangat krusial. Ini membalikkan stack riwayat peramban (*browser history stack*), memastikan bahwa status history kembali sinkron dengan posisi sebelum modal terbuka.
* **Baris 18-24:**
  ```typescript
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDismiss();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onDismiss]);
  ```
  Pembersihan listener (*cleanup function*) mutlak diperlukan untuk mencegah memory leakage saat modal di-unmount dari virtual DOM.
* **Baris 29-33:**
  ```typescript
  onClick={(e) => {
    if (e.target === overlayRef.current) onDismiss();
  }}
  ```
  Pemeriksaan `e.target === overlayRef.current` memvalidasi bahwa event click murni berasal dari area backdrop/scrim, bukan merupakan propagasi (*bubbling*) dari klik di dalam bodi modal.

---

## SEKSI 09 — STUDI KASUS NYATA

### Latar Belakang Masalah
Sebuah platform Audit Forensik Transaksi Finansial berskala Enterprise (*Fraud Monitoring System*) memproses jutaan transaksi per hari. Para analis fraud membuka ratusan rincian transaksi per shift.

### Masalah Arsitektur Sebelumnya
1. Detail transaksi dimunculkan via traditional React state (`selectedTxId`). Masalah: Analis tidak dapat membagikan URL modal ke rekan verifikator via Slack; membuka link hanya memunculkan dashboard utama, kehilangan state transaksi.
2. Analis sering kali membuka rincian transaksi pada tab browser baru (*Open in new tab*). Menggunakan URL query params atau state menyebabkan halaman detail pada tab baru menjadi rusak atau merender layout dashboard penuh secara tidak perlu, menghabiskan memori RAM analis.
3. Kebutuhan compliance: Setiap modal audit yang dibuka harus mengisolasi thread stream data live-updating, tanpa merusak timeline chart yang sedang berjalan pada dashboard induk.

### Solusi Rekayasa dengan Next.js
Menerapkan parallel layout `@transactionModal` digabung dengan Intercepting Route `(..)transactions/[id]` dan standalone fallback pada `/transactions/[id]`.
* Ketika diklik dari Dashboard: Transaksi muncul seketika sebagai intercepting modal, context stream dashboard dipertahankan.
* Ketika link di-copy/paste atau di-refresh (F5): Transaksi merender view forensik layar penuh (Canonical View) berstandar ISO-27001 dengan audit trail lengkap tanpa membebani server dengan dashboard chart telemetry.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur direktori implementasi:
```
app/
├── layout.tsx
├── default.tsx
├── transactions/
│   ├── [id]/
│   │   └── page.tsx         <-- Full Page Forensic View
│   └── page.tsx             <-- Transactions Landing
└── dashboard/
    ├── layout.tsx           <-- Dashboard Layout with Parallel Slot
    ├── page.tsx             <-- Master Transactions Table (Children)
    ├── default.tsx
    └── @auditModal/         <-- Named Parallel Slot
        ├── default.tsx      <-- Null Fallback
        └── (..)transactions/
            └── [id]/
                └── page.tsx <-- Intercepted Forensic Modal
```

### 1. Unified Types Definition
```typescript
// types/forensic.ts
export interface FinancialTransaction {
  id: string;
  senderAccount: string;
  receiverAccount: string;
  amount: number;
  currency: string;
  riskScore: number;
  timestamp: string;
  flags: string[];
}
```

### 2. Mock Data Service
```typescript
// lib/forensic-service.ts
import { FinancialTransaction } from '@/types/forensic';

const MOCK_DB: Record<string, FinancialTransaction> = {
  'tx-9821': {
    id: 'tx-9821',
    senderAccount: 'ACC-NL-4091',
    receiverAccount: 'ACC-KY-9912',
    amount: 142500.0,
    currency: 'USD',
    riskScore: 89.4,
    timestamp: '2025-02-14T08:21:00Z',
    flags: ['RAPID_MOVEMENT', 'HIGH_RISK_JURISDICTION'],
  },
  'tx-9822': {
    id: 'tx-9822',
    senderAccount: 'ACC-SG-1010',
    receiverAccount: 'ACC-ID-5531',
    amount: 3200.0,
    currency: 'USD',
    riskScore: 12.1,
    timestamp: '2025-02-14T08:24:12Z',
    flags: [],
  },
};

export async function fetchTransactionById(id: string): Promise<FinancialTransaction | null> {
  // Simulasi latency koneksi internal cluster
  await new Promise((resolve) => setTimeout(resolve, 80));
  return MOCK_DB[id] || null;
}

export async function fetchRecentTransactions(): Promise<FinancialTransaction[]> {
  await new Promise((resolve) => setTimeout(resolve, 50));
  return Object.values(MOCK_DB);
}
```

### 3. Dashboard Layout dengan Slot Parallel
```tsx
// app/dashboard/layout.tsx
import React from 'react';

export default function DashboardLayout({
  children,
  auditModal,
}: {
  children: React.ReactNode;
  auditModal: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full bg-slate-950 text-slate-100 overflow-hidden">
      {/* Sidebar Navigasi Statis */}
      <aside className="w-64 border-r border-slate-800 p-6 flex flex-col justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-wider text-rose-500 mb-8">
            SENTINEL // AML
          </h2>
          <nav className="space-y-2 text-sm font-medium">
            <span className="block px-3 py-2 bg-slate-900 border-l-2 border-rose-500 rounded">
              Transactions Monitor
            </span>
          </nav>
        </div>
        <div className="text-xs text-slate-500">Node Cluster: SG-01 (Active)</div>
      </aside>

      {/* Main Stream Area */}
      <section className="flex-1 flex flex-col overflow-y-auto">
        <header className="h-16 border-b border-slate-800 px-8 flex items-center justify-between">
          <div className="font-mono text-sm text-slate-400">
            SECURE ACCESS LEVEL: TIER-3 ANALYST
          </div>
        </header>
        <main className="p-8 flex-1">{children}</main>
      </section>

      {/* Parallel Slot Mount Point */}
      {auditModal}
    </div>
  );
}
```

### 4. Parallel Default Fallbacks
```tsx
// app/dashboard/default.tsx
export default function DashboardDefault() {
  return null;
}

// app/dashboard/@auditModal/default.tsx
export default function AuditModalDefault() {
  return null;
}
```

### 5. Main Dashboard View (Children)
```tsx
// app/dashboard/page.tsx
import { fetchRecentTransactions } from '@/lib/forensic-service';
import Link from 'next/link';

export default async function DashboardPage() {
  const transactions = await fetchRecentTransactions();

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold tracking-tight">Antrian Transaksi Mencurigakan</h3>
        <p className="text-slate-400 text-sm">Klik transaksi untuk inspeksi cepat forensik data.</p>
      </div>

      <div className="border border-slate-800 rounded-lg overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 uppercase text-xs">
            <tr>
              <th className="px-6 py-3">Transaction ID</th>
              <th className="px-6 py-3">Sender</th>
              <th className="px-6 py-3">Receiver</th>
              <th className="px-6 py-3">Amount</th>
              <th className="px-6 py-3">Risk Score</th>
              <th className="px-6 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {transactions.map((tx) => (
              <tr key={tx.id} className="hover:bg-slate-900/50 transition">
                <td className="px-6 py-4 font-mono font-medium text-slate-200">{tx.id}</td>
                <td className="px-6 py-4 font-mono text-slate-400">{tx.senderAccount}</td>
                <td className="px-6 py-4 font-mono text-slate-400">{tx.receiverAccount}</td>
                <td className="px-6 py-4">
                  {tx.amount.toLocaleString('en-US', { style: 'currency', currency: tx.currency })}
                </td>
                <td className="px-6 py-4">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${
                      tx.riskScore > 75
                        ? 'bg-rose-950 text-rose-400 border border-rose-800'
                        : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    }`}
                  >
                    {tx.riskScore}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  {/* Link navigasi mengarah ke URL kanonikal /transactions/[id] */}
                  <Link
                    href={`/transactions/${tx.id}`}
                    scroll={false}
                    className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 px-3 py-1.5 rounded transition"
                  >
                    Audit
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### 6. Client Interceptor Wrapper
```tsx
// components/dashboard/audit-modal-frame.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect } from 'react';

export function AuditModalFrame({
  children,
  txId,
}: {
  children: React.ReactNode;
  txId: string;
}) {
  const router = useRouter();

  const handleDismiss = useCallback(() => {
    router.back();
  }, [router]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleDismiss();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleDismiss]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="audit-title"
      className="fixed inset-0 z-50 flex items-center justify-end bg-black/75 backdrop-blur-xs"
    >
      <div className="h-full w-full max-w-xl bg-slate-900 border-l border-slate-700 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
        <header className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-950">
          <div>
            <span className="text-xs font-mono text-rose-400 tracking-wider">FORENSIC OVERLAY</span>
            <h2 id="audit-title" className="text-lg font-bold text-slate-100">
              Transaction: {txId}
            </h2>
          </div>
          <button
            onClick={handleDismiss}
            className="p-2 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition"
            aria-label="Tutup Panel"
          >
            &#x2715;
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-6">{children}</div>
      </div>
    </div>
  );
}
```

### 7. Intercepted Forensic Modal
Menggunakan token `(..)` karena target route `/transactions/[id]` berada 1 segmen di atas root direktori `dashboard`.
```tsx
// app/dashboard/@auditModal/(..)transactions/[id]/page.tsx
import { fetchTransactionById } from '@/lib/forensic-service';
import { notFound } from 'next/navigation';
import { AuditModalFrame } from '@/components/dashboard/audit-modal-frame';

export default async function InterceptedAuditModal({
  params,
}: {
  params: Promise<{ id: string }>;