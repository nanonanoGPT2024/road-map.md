# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Routing Lanjutan — Parallel dan Intercepting Patterns**
**Kategori: 03-Frontend-and-Mobile (Next.js Enterprise Curriculum)**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Membedah dan merekonstruksi cara kerja internal App Router Next.js saat menangani *Parallel Routes* (`@slot`) dan *Intercepting Routes* (`(.)`, `(..)`, `(...)`).
- Memahami siklus hidup resolusi *Router State Tree*, manipulasi *Flight Data/RSC Payload*, dan mekanisme *Segment Matching* pada navigasi *Soft* vs *Hard*.
- Merancang arsitektur UI kompleks multi-dimensi (seperti dashboard multimodal, conditional nested modals, dynamic parallel paneling) tanpa merusak URL canonical state.
- Mengeliminasi *race conditions* dan *state desynchronization* antara URL bar, client-side Router Cache, dan Server Components.
- Mengimplementasikan sistem *fallback lifecycle* deterministik menggunakan `default.tsx` dan menangani *hydration mismatch* pada skenario routing lanjutan.
- Mengintegrasikan sistem *monitoring*, *performance budgeting*, dan *SEO mitigation* untuk rute yang diintersepsi.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Next.js Core Fundamentals**: Memahami lifecycle App Router, arsitektur dasar Server Component (RSC) vs Client Component (`'use client'`), Suspense Boundary, dan nested layout.
- **Advanced React**: React 18+ concurrent features, dynamic slot injection via `props.children`, UI unmounting lifecycles, and synthetic event propagation.
- **HTTP & Browser Mechanics**: PushState/ReplaceState Web API, URL Spec (RFC 3986), HTTP conditional requests, dan Client Router Cache invalidation mechanics.
- **TypeScript**: Discriminated unions, template literal types, generic component props definition.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1. Anatomi Client-Side Router State Tree & RSC Wire Format

Next.js App Router tidak beroperasi seperti SPA konvensional (React Router) yang mencocokkan regex URL di sisi klien, bukan pula seperti Pages Router yang me-mount file fisik secara terisolasi. App Router mengelola **Router State Tree** hierarkis di memori browser, yang disinkronisasikan secara diferensial dengan server melalui format biner/teks streaming yang disebut **Flight RPC / React Server Component (RSC) Payload**.

```
Browser Memory: Router State Tree
├── layout: "app/layout.tsx"
└── parallel slots:
    ├── children: "app/page.tsx"
    ├── @analytics: "app/@analytics/page.tsx"
    └── @modal: "app/@modal/(.)photos/[id]/page.tsx" (Intercepted)
```

Saat pengguna bernavigasi:
1. Client Router mendeteksi perubahan via interceptor link/pushState.
2. Client mengirimkan request fetch HTTP khusus ke server dengan header HTTP internal:
   - `RSC: 1`
   - `Next-Router-State-Tree: <serialized_tree>`
   - `Next-Url: <current_url>`
3. Server memproses pohon rute bukan dari nol, melainkan menghitung *diff* (diferensial) antara `Next-Router-State-Tree` yang dikirim klien dan segmen baru yang diminta.
4. Server merender segmen yang terdampak dan mengalirkan chunk RSC Payload yang hanya berisi pohon virtual DOM sub-tree baru beserta instruksi mutasi Router Cache.

### 3.2. Dynamic Parallel Route Slot Injection

Parallel Routes didefinisikan menggunakan konvensi folder `@slotName`. Folder dengan awalan `@` adalah segmen eksplisit yang **tidak diekspos ke segmen URL**. `@slotName` dipetakan langsung oleh Next.js bundler ke dalam properti props dari komponen `layout.tsx` pada level direktori yang sama atau di atasnya.

```
app/
├── layout.tsx       --> Menerima props: { children, analytics, team }
├── page.tsx         --> Mengisi slot default (props.children)
├── @analytics/
│   └── page.tsx     --> Mengisi props.analytics
└── @team/
    └── page.tsx     --> Mengisi props.team
```

Secara internal, Next.js mendefinisikan layout root atau sub-layout dengan signature tipe:

```typescript
type LayoutProps = {
  children: React.ReactNode;
  analytics: React.ReactNode;
  team: React.ReactNode;
};
```

Pada level arsitektur runtime, slot bertindak sebagai boundary isolasi independen:
- Tiap slot dapat memiliki error boundary (`error.tsx`), loading boundary (`loading.tsx`), dan layout tersendiri.
- Eksekusi data fetching (`async/await` di RSC) di dalam `@analytics` tidak memblokir render stream di `@team`. Keduanya dieksekusi secara paralel di node runtime V8 server.

### 3.3. Intercepting Routes: URL Masking & Segment Hijacking Mechanics

*Intercepting Routes* memungkinkan Next.js membajak rute target dari konteks layout saat ini selama navigasi terjadi melalui transisi klien (*Soft Navigation*). Format konvensinya:
- `(.)` mencocokkan segmen pada **level yang sama**.
- `(..)` mencocokkan segmen **satu level di atas**.
- `(..)(..)` mencocokkan segmen **dua level di atas**.
- `(...)` mencocokkan segmen dari **root direktori `app/`**.

#### Perbedaan Hakiki: Soft Navigation vs Hard Navigation

Mekanisme ini adalah sumber bug terbesar jika internalnya tidak dipahami:

```
+-----------------------------------------------------------------------------+
| SKENARIO 1: SOFT NAVIGATION (Link click, router.push)                       |
| User berada di "/feed", klik <Link href="/photos/123">                     |
|                                                                             |
| 1. Client Router Cache mendeteksi interceptor marker:                       |
|    `app/@modal/(.)photos/[id]/page.tsx` cocok dengan path `/photos/123`.     |
| 2. URL browser dimutasi via history.pushState -> URL menjadi `/photos/123`.  |
| 3. Layout feed ("/feed") TIDAK di-unmount.                                  |
| 4. Next.js merender `@modal` menggunakan file interceptor.                   |
| 5. Hasil: Tampilan Feed tetap ada di background, Modal muncul di atasnya.   |
+-----------------------------------------------------------------------------+

+-----------------------------------------------------------------------------+
| SKENARIO 2: HARD NAVIGATION (F5 / Refresh, Direct URL Copy-Paste, SSR)      |
| Browser meminta langsung URL "GET /photos/123" ke server                    |
|                                                                             |
| 1. Server tidak memiliki riwayat Client Router Cache sebelumnya.           |
| 2. Interceptor `(.)photos` DIABAIKAN.                                       |
| 3. Server mencocokkan URL langsung ke rute kanonikal:                        |
|    `app/photos/[id]/page.tsx`.                                              |
| 4. Hasil: Halaman detail penuh (stand-alone page) di-render tanpa modal,     |
|    tanpa layout feed. Feed tidak pernah dieksekusi.                          |
+-----------------------------------------------------------------------------+
```

### 3.4. Lifecycle Resolusi `default.tsx`

Saat terjadi navigasi lunak (*soft navigation*), jika sebuah slot tidak cocok dengan rute baru, Next.js akan mempertahankan tampilan slot sebelumnya (*slot persistence*).

Namun, saat terjadi **Hard Navigation** (Full page reload):
1. Next.js melakukan revalidasi penuh terhadap seluruh segmen pohon.
2. Jika sebuah parallel slot tidak memiliki rute eksplisit yang cocok dengan URL yang diminta, Next.js **wajib** mencari file `default.tsx` di dalam direktori slot tersebut.
3. **Jika `default.tsx` tidak ditemukan pada slot yang aktif, Next.js akan melempar status HTTP 404 (Not Found)** untuk keseluruhan halaman, meskipun rute utama (`page.tsx`) valid.

---

## 4. Why & What

| Pertanyaan | Analisis Kritis |
| :--- | :--- |
| **Why Parallel Routes?** | Tanpa Parallel Routes, membangun *multi-pane dashboard* memerlukan pemindahan seluruh logic state ke Client Components (mengorbankan SSR), atau menggabungkan seluruh logic fetching ke dalam single monolithic `page.tsx` (mengorbankan granular caching, Suspense boundary streaming, dan isolasi kegagalan per-widget). |
| **Why Intercepting Routes?** | Mempertahankan paradigma URL-first design. Modal konvensional menyimpan state di query param (`?modal=true`) atau memory React (`useState`). Hal ini merusak *shareability*, *deep linking*, dan *SEO crawler indexing*. Intercepting routes memberikan pengalaman modal instan bagi user aktif, sekaligus memberikan representasi halaman penuh berindeks SEO bagi crawler atau user yang membuka tab baru. |
| **What are they NOT?** | Parallel Routes **bukan** pengganti conditional rendering sederhana (seperti `isOpen ? <A/> : <B/>`). Intercepting routes **bukan** modifikasi protokol HTTP redirect (301/302). Semuanya murni komputasi layer aplikasi pada routing virtual tree Next.js. |

---

## 5. How (Workflow Detail)

Berikut alur eksekusi saat pengguna mengakses galeri foto lalu membuka foto modal:

```
[User di "/feed"]
       │
       ▼
[Klik <Link href="/photos/101" scroll={false}>]
       │
       ├──────────────────────────────────────────────┐
       ▼                                              ▼
[Browser: history.pushState]             [Next.js Client Router]
[URL berubah menjadi /photos/101]                     │
                                                      ▼
                                         [Evaluasi Matched Slots]
                                         - Main Slot: tetap di /feed (dipertahankan)
                                         - @modal Slot: Cocok dengan (.)photos/[id]
                                                      │
                                                      ▼
                                         [Fetch RSC Payload]
                                         - Headers: Next-Url: /feed
                                         - Query segment: (.)photos/101
                                                      │
                                                      ▼
                                         [Server merender (.)photos/[id]/page.tsx]
                                                      │
                                                      ▼
                                         [Client menerima Stream Payload]
                                                      │
                                                      ▼
                                         [Slot @modal diisi komponen Modal]
                                         [State Feed di background tidak hilang]
```

Saat pengguna menekan tombol **F5 (Reload)** pada kondisi modal terbuka:

```
[Browser Reload: GET /photos/101]
       │
       ▼
[Next.js Server: Route Matching Algorithm]
       │
       ├─ Mencari folder 'app/photos/[id]/page.tsx' (Canonical Route)
       └─ Mengabaikan interceptor folder 'app/@modal/(.)photos/[id]'
       │
       ▼
[Server merender Root Layout -> app/photos/[id]/page.tsx]
       │
       ▼
[Client menerima Full HTML Dokument]
       │
       ▼
[User melihat halaman foto penuh (Standalone Page), BUKAN modal]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Panggung Teater dengan Pintu Jebakan (Trapdoor) dan Layar Proyektor

- **Parallel Routes (`@slot`)**: Seperti panggung teater yang dibagi menjadi tiga segmen fisik berbeda. Panggung Utama (`children`), Panggung Kiri (`@analytics`), dan Panggung Kanan (`@team`). Masing-masing memiliki kru panggung sendiri (Error Boundary & Suspense). Jika aktor di Panggung Kiri pingsan (Error), pertunjukan di Panggung Utama dan Kanan tetap berjalan lancar.
- **Intercepting Routes (`(..)`)**: Seperti Layar Proyektor Lipat Cepat. Ketika penonton masih duduk di auditorium (`/feed`) dan memesan katalog (`/photos/1`), kru panggung langsung menurunkan layar proyektor tepat di depan panggung utama secara instan (*Modal Interception*). Namun, jika penonton datang dari luar gedung langsung masuk melalui pintu belakang khusus katalog (`GET /photos/1`), mereka akan langsung diarahkan ke Ruang Galeri Penuh, bukan ke auditorium dengan layar proyektor.

### Diagram Topologi Arsitektur Direktori

```
app/
├── layout.tsx                     # Top-Level Layout (Penerima slots)
├── page.tsx                       # Halaman root /
├── feed/
│   └── page.tsx                   # Halaman /feed (Katalog)
├── photos/
│   └── [id]/
│       └── page.tsx               # Canonical Page: Fallback Reload / Direct Hit
├── @modal/
│   ├── default.tsx                # KRUSIAL: Render null jika modal tidak aktif
│   └── (.)photos/
│       └── [id]/
│           └── page.tsx           # Interceptor: Dirender saat link diklik dari /feed
└── default.tsx                    # Catch-all default root slot
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Conditional Dashboard Parallel Slots

Struktur folder:
```
app/
├── layout.tsx
├── page.tsx
├── @metrics/
│   ├── default.tsx
│   ├── page.tsx
│   └── error.tsx
└── @logs/
    ├── default.tsx
    └── page.tsx
```

`app/layout.tsx`:
```tsx
import React from 'react';

interface DashboardLayoutProps {
  children: React.ReactNode;
  metrics: React.ReactNode;
  logs: React.ReactNode;
}

export default function DashboardLayout({
  children,
  metrics,
  logs,
}: DashboardLayoutProps) {
  return (
    <div className="flex flex-col gap-6 p-8 max-w-7xl mx-auto">
      <header className="border-b pb-4">
        <h1 className="text-2xl font-bold tracking-tight">Enterprise Console</h1>
      </header>
      <main className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <section className="md:col-span-2 space-y-6">
          {children}
          {metrics}
        </section>
        <aside className="md:col-span-1 border-l pl-6">
          {logs}
        </aside>
      </main>
    </div>
  );
}
```

`app/@metrics/page.tsx`:
```tsx
import { Suspense } from 'react';

async function SlowMetricsData() {
  // Simulasi query OLAP lambat
  await new Promise((resolve) => setTimeout(resolve, 3000));
  return (
    <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
      <p className="text-sm font-medium text-emerald-800">System Throughput: 42,910 req/s</p>
    </div>
  );
}

export default function MetricsSlot() {
  return (
    <div className="border rounded-xl p-4 shadow-sm bg-white">
      <h2 className="text-lg font-semibold mb-2">Live Metrics</h2>
      <Suspense fallback={<div className="h-16 animate-pulse bg-slate-100 rounded" />}>
        <SlowMetricsData />
      </Suspense>
    </div>
  );
}
```

`app/@metrics/default.tsx` dan `app/@logs/default.tsx`:
```tsx
export default function DefaultSlot() {
  return null; // Memastikan slot aman jika terjadi unmatching navigation
}
```

---

### 7.2. Practical Example: Enterprise Photo Interception Pattern

Implementasi modal detail foto dengan aksesibilitas lengkap, sinkronisasi rute, dan fallback native.

#### Direktori:
```
app/
├── layout.tsx
├── @modal/
│   ├── default.tsx
│   └── (.)photos/
│       └── [id]/
│           └── page.tsx
└── photos/
    └── [id]/
        └── page.tsx
```

#### File: `app/@modal/default.tsx`
```tsx
export default function DefaultModal() {
  return null;
}
```

#### File: `app/@modal/(.)photos/[id]/page.tsx` (Intercepted Modal)
```tsx
import { ModalWrapper } from '@/components/ui/modal-wrapper';
import { PhotoDetailView } from '@/components/modules/photos/photo-detail-view';

interface InterceptedPhotoProps {
  params: Promise<{ id: string }>;
}

export default async function InterceptedPhotoModal({ params }: InterceptedPhotoProps) {
  const { id } = await params;

  return (
    <ModalWrapper title={`Asset Inspeksi #${id}`}>
      <PhotoDetailView photoId={id} isModalContext={true} />
    </ModalWrapper>
  );
}
```

#### File: `app/photos/[id]/page.tsx` (Canonical Standalone Page)
```tsx
import { PhotoDetailView } from '@/components/modules/photos/photo-detail-view';
import Link from 'next/link';

interface CanonicalPhotoProps {
  params: Promise<{ id: string }>;
}

export default async function CanonicalPhotoPage({ params }: CanonicalPhotoProps) {
  const { id } = await params;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 p-8 flex flex-col items-center">
      <nav className="w-full max-w-4xl mb-6">
        <Link 
          href="/" 
          className="text-sm text-cyan-400 hover:underline flex items-center gap-2"
        >
          &larr; Kembali ke Dashboard Feed
        </Link>
      </nav>
      <main className="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
        <PhotoDetailView photoId={id} isModalContext={false} />
      </main>
    </div>
  );
}
```

#### File: `components/ui/modal-wrapper.tsx` (Client Modal Logic)
```tsx
'use client';

import React, { useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';

export function ModalWrapper({ 
  children, 
  title 
}: { 
  children: React.ReactNode; 
  title: string;
}) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const onDismiss = useCallback(() => {
    router.back();
  }, [router]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) {
      dialog.showModal();
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onDismiss();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onDismiss]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onDismiss}
      onClick={(e) => {
        // Klik pada backdrop menutup dialog
        if (e.target === dialogRef.current) {
          onDismiss();
        }
      }}
      className="backdrop:bg-slate-950/80 backdrop:backdrop-blur-sm bg-transparent p-0 m-auto rounded-xl shadow-2xl open:animate-in open:fade-in-0 open:zoom-in-95"
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 w-[90vw] max-w-2xl rounded-xl p-6 overflow-hidden">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
          <button
            onClick={onDismiss}
            aria-label="Tutup Dialog"
            className="p-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
          >
            ✕
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </dialog>
  );
}
```

#### File: `components/modules/photos/photo-detail-view.tsx` (Shared Component)
```tsx
import Image from 'next/image';

export async function PhotoDetailView({ 
  photoId, 
  isModalContext 
}: { 
  photoId: string; 
  isModalContext: boolean;
}) {
  // Simulasi pemanggilan database/API
  const photoData = {
    id: photoId,
    title: `High-Resolution Asset ${photoId}`,
    url: `https://picsum.photos/seed/${photoId}/1200/800`,
    resolution: "3840x2160",
    size: "4.2 MB",
    format: "AVIF"
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
        <Image
          src={photoData.url}
          alt={photoData.title}
          fill
          priority
          sizes="(max-width: 768px) 100vw, 800px"
          className="object-cover"
        />
      </div>
      <div className="grid grid-cols-2 gap-4 py-2">
        <div>
          <span className="text-xs uppercase text-slate-400 font-semibold">Resolusi</span>
          <p className="text-sm font-medium">{photoData.resolution}</p>
        </div>
        <div>
          <span className="text-xs uppercase text-slate-400 font-semibold">Ukuran File</span>
          <p className="text-sm font-medium">{photoData.size}</p>
        </div>
      </div>
      {isModalContext && (
        <p className="text-xs text-amber-500 italic mt-2">
          * Mode Tinjauan Cepat (Tekan ESC untuk keluar atau Refresh untuk mode penuh)
        </p>
      )}
    </div>
  );
}
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: FinTech High-Volume Trading Platform (Omni-Terminal)

#### Konteks & Masalah Arsitektur:
Sebuah platform broker trading global membutuhkan sistem dashboard di mana trader dapat memantau *Watchlist*, *Live Order Book*, dan *Candlestick Graph* secara simultan. 
- **Kebutuhan 1**: Setiap panel memiliki siklus streaming data terpisah (WebSocket + HTTP Server-Sent Events).
- **Kebutuhan 2**: Jika trader mengklik sebuah transaksi di panel Order Book, sistem harus membuka modal "Audit Trail & Settlement Proof" tanpa mereset canvas chart candlestick WebGL (biaya re-rendering WebGL > 250ms).
- **Kebutuhan 3**: Auditor regulasi harus bisa mengambil URL dari modal audit tersebut, membagikannya via email ke regulator eksternal, dan regulator harus melihat dokumen audit dalam mode satu halaman penuh (*Full-page compliance view*), bukan dashboard trading.

#### Solusi Arsitektur:
1. **Parallel Routes 3 Slot**:
   - `app/terminal/layout.tsx` mengelola:
     - `children`: Candlestick Engine (WebGL Canvas Client Component).
     - `@orderbook`: RSC dengan auto-revalidation data stream.
     - `@watchlist`: Static RSC dengan Edge Caching.
     - `@auditModal`: Slot untuk menampung intervensi URL.
2. **Intercepting Route**:
   - Struktur folder: `app/terminal/@auditModal/(.)transaction/[txId]/page.tsx`.
   - Rute kanonikal: `app/transaction/[txId]/page.tsx`.
3. **Hasil**:
   - Saat trader membuka transaksi dari terminal, WebGL canvas tidak me-mount ulang (karena tree terminal tidak pernah unmount). Modal transaksi terbuka, URL sinkron ke `/transaction/tx_998811`.
   - Regulator yang membuka link `https://broker.com/transaction/tx_998811` langsung disajikan halaman kanonikal tanpa membebani server untuk merender antarmuka trading terminal yang kompleks.

---

## 9. Trade-offs (Analisis Konsekuensi Arsitektur)

| Dimensi Arsitektur | Keuntungan (Pros) | Biaya/Batasan (Cons/Trade-offs) |
| :--- | :--- | :--- |
| **Performance & Latency** | Mengurangi First Input Delay (FID/INP) dan CLS. Laman background tidak di-unmount, menghindari re-fetching data besar saat modal ditutup. | Memori browser klien lebih tinggi karena mempertahankan dua UI tree (Background layout + Modal layout) secara bersamaan. |
| **Edge Cache & RSC Payloads** | Streaming RSC modular: Kegagalan load pada satu slot tidak memblokir payload slot lainnya (Isolasi boundary Suspense). | Ukuran RSC Payload network transfer sedikit bertambah karena Next.js mengirim metadata router state tree multi-slot. |
| **Scalability & Developer Ergonomics** | Pemisahan kode yang sangat bersih (*Separation of Concerns*). Tim A mengurus `@analytics`, Tim B mengurus `@orderbook`. | Kompleksitas navigasi meningkat drastis. Debugging rute relatif (`(..)`) pada nested folder dalam memerlukan visualisasi tree yang presisi. |
| **Infrastructure & Server Costs** | Mengurangi beban komputasi server: Navigasi soft hanya meminta RSC diff untuk slot yang berubah, bukan full-page SSR layout. | Potensi *Cache Stampede* pada dynamic edge runtime jika `default.tsx` tidak dikonfigurasi dengan fallback rendering yang tepat. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Error 404 Fatal Saat Hard Refresh (Missing `default.tsx`)
- **Gejala**: Navigasi modal berhasil, namun saat menekan F5/Refresh, aplikasi melempar halaman 404 Next.js bawaan.
- **Penyebab**: Parallel slot tidak mendefinisikan `default.tsx`. Saat hard reload, Next.js mencari representasi dari slot tersebut untuk rute URL saat ini dan gagal menemukannya.
- **Solusi**: Selalu buat `default.tsx` di setiap level parallel slot:
  ```tsx
  // app/@modal/default.tsx
  export default function Default() {
    return null;
  }
  ```

### Mistake 2: Kesalahan Tingkat Kedalaman Interceptor (`(.)` vs `(..)`)
- **Gejala**: Mengklik link mengarahkan pengguna ke halaman kanonikal (full-page navigation) alih-alih membuka modal. Interceptor tidak terpanggil.
- **Penyebab**: Penghitungan level segmen salah. Ingat: Intercepting routes **menghitung level segmen rute, bukan level folder fisik pada disk**. Folder `@slot` tidak dihitung sebagai segmen URL.
- **Panduan Resolusi**:
  Jika link berada di: `app/dashboard/feed/page.tsx` (URL: `/dashboard/feed`)  
  Dan Anda ingin mencegat target: `app/dashboard/item/[id]/page.tsx` (URL: `/dashboard/item/[id]`)  
  Maka interceptor di dalam `@modal` harus menggunakan `(..)item` karena level URL-nya adalah saudara (*sibling*) satu tingkat di atas `feed`.

### Mistake 3: State Desynchronization pada Modal Unmount
- **Gejala**: Pengguna menutup modal menggunakan button close kustom (`setShowModal(false)`), tetapi URL di browser bar tetap tertinggal di `/photos/123`. Saat tombol browser *Back* diklik, aplikasi rusak.
- **Penyebab**: Memanipulasi state lokal React untuk menutup Intercepted Route.
- **Solusi**: Jangan pernah menutup Intercepted Modal menggunakan state boolean lokal. **Gunakan API Router**:
  ```tsx
  const router = useRouter();
  // Untuk menutup:
  router.back();
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Definisikan `default.tsx`**: Pastikan setiap folder parallel slot (`@slot`) memiliki file `default.tsx` eksplisit yang mengembalikan `null` atau fallback skeleton UI.
- [ ] **Gunakan Native `<dialog>` atau Headless UI Radix/Ark**: Pastikan modal menangani focus trap, Escape key handling, dan screen reader accessibility (`aria-modal="true"`).
- [ ] **Matikan Scroll Restore Jika Diperlukan**: Gunakan `<Link href="/target" scroll={false}>` saat memicu Intercepted Modal agar posisi scroll pada feed background tidak melompat ke atas.
- [ ] **Isolasi Suspense Boundary**: Bungkus pemanggilan data di dalam slot dengan boundary `<Suspense fallback={<Skeleton />}>` agar tidak menghambat parallel rendering segmen lain.
- [ ] **Tangani Kondisi Multi-Modal Escape**: Pastikan listener global mendeteksi apakah rute saat ini merupakan hasil `router.push()` atau direct hit sebelum mengeksekusi `router.back()`. Jika history stack kosong (direct hit via open-in-new-tab), fallback ke `router.push('/canonical-parent')`.
- [ ] **SEO Meta Tags Integrity**: Letakkan Metadata canonical (`metadataBase` & `alternates.canonical`) di halaman kanonikal (`photos/[id]/page.tsx`) agar search engine mengindeks URL tunggal yang valid.

---

## 12. Hands-on Practice

Buatlah workspace praktikum pada folder: `hands-on/m02/`

### Step 1: Inisialisasi Proyek
```bash
npx create-next-app@latest hands-on/m02 --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*"
cd hands-on/m02
```

### Step 2: Membuat Data Mock Layer
Buat file `lib/data.ts`:
```typescript
export interface Product {
  id: string;
  name: string;
  price: string;
  category: string;
  description: string;
}

export const PRODUCTS: Product[] = [
  { id: '1', name: 'Quantum Mechanical Keyboard', price: '$240', category: 'Hardware', description: 'Custom switches with ultra-low latency response.' },
  { id: '2', name: 'Zero-Latency Wireless Mouse', price: '$120', category: 'Hardware', description: 'Ergonomic sensor tuned for precision data analytics.' },
  { id: '3', name: 'Ultra-Wide 5K Monitor', price: '$1,150', category: 'Display', description: 'Curved OLED panel with HDR1000 master grade color profiling.' },
];
```

### Step 3: Implementasi Base Layout & Parallel Slots
Ubah file `app/layout.tsx`:
```tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Enterprise Store Console',
  description: 'Advanced routing lab',
};

export default function RootLayout({
  children,
  preview,
}: {
  children: React.ReactNode;
  preview: React.ReactNode;
}) {
  return (
    <html lang="id">
      <body className="bg-slate-50 text-slate-900 antialiased min-h-screen">
        <header className="bg-white border-b px-8 py-4">
          <span className="font-mono text-xs uppercase tracking-widest text-indigo-600 font-bold">Lab M02</span>
          <h1 className="text-xl font-bold">Parallel & Intercepting Dynamic System</h1>
        </header>
        <main className="p-8">
          {children}
        </main>
        {preview}
      </body>
    </html>
  );
}
```

### Step 4: Menyiapkan Default Slot Fallback
Buat file `app/@preview/default.tsx`:
```tsx
export default function DefaultPreview() {
  return null;
}
```

### Step 5: Implementasi Master Feed
Ubah file `app/page.tsx`:
```tsx
import Link from 'next/link';
import { PRODUCTS } from '@/lib/data';

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-semibold tracking-tight">Katalog Produk</h2>
        <span className="text-sm text-slate-500">Pilih produk untuk melihat inspeksi modal</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {PRODUCTS.map((product) => (
          <div key={product.id} className="bg-white border rounded-xl p-5 shadow-sm hover:shadow-md transition">
            <span className="text-xs font-semibold text-indigo-500 uppercase">{product.category}</span>
            <h3 className="font-bold text-lg mt-1">{product.name}</h3>
            <p className="text-slate-600 text-sm mt-2">{product.price}</p>
            <div className="mt-4 pt-4 border-t flex justify-end">
              <Link
                href={`/products/${product.id}`}
                scroll={false}
                className="text-xs font-semibold bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-lg hover:bg-indigo-100 transition"
              >
                Detail Modal &rarr;
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Step 6: Implementasi Intercepted Route
Buat folder dan file: `app/@preview/(.)products/[id]/page.tsx`:
```tsx
import { PRODUCTS } from '@/lib/data';
import { notFound } from 'next/navigation';
import { ClientPreviewDialog } from '@/components/client-dialog';

export default async function InterceptedProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const product = PRODUCTS.find((p) => p.id === id);

  if (!product) {
    notFound();
  }

  return (
    <ClientPreviewDialog title={`Modal Intercepted: ${product.name}`}>
      <div className="space-y-4">
        <div className="bg-indigo-50 p-4 rounded-lg">
          <p className="text-xs text-indigo-700 font-mono">STATUS: INTERCEPTED VIA ROUTE STATE TREE</p>
          <p className="text-sm text-indigo-900 mt-1">Laman root background tetap aktif. Tidak ada hard refresh.</p>
        </div>
        <p className="text-slate-700">{product.description}</p>
        <div className="flex justify-between items-center text-sm font-semibold border-t pt-4">
          <span>Harga Retail:</span>
          <span className="text-lg text-emerald-600">{product.price}</span>
        </div>
      </div>
    </ClientPreviewDialog>
  );
}
```

### Step 7: Buat Modal Client Interactivity
Buat file `components/client-dialog.tsx`:
```tsx
'use client';

import { useRouter } from 'next/navigation';

export function ClientPreviewDialog({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  const router = useRouter();

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center pb-2 border-b">
          <h3 className="font-bold text-slate-800">{title}</h3>
          <button
            onClick={() => router.back()}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
          >
            ✕
          </button>
        </div>
        {children}
        <button
          onClick={() => router.back()}
          className="w-full mt-4 bg-slate-900 text-white text-sm font-medium py-2 rounded-lg hover:bg-slate-800 transition"
        >
          Tutup Intersepsi
        </button>
      </div>
    </div>
  );
}
```

### Step 8: Implementasi Standalone Canonical Fallback
Buat file `app/products/[id]/page.tsx`:
```tsx
import { PRODUCTS } from '@/lib/data';
import { notFound } from 'next/navigation';
import Link from 'next/link';

export default async function CanonicalProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const product = PRODUCTS.find((p) => p.id === id);

  if (!product) {
    notFound();
  }

  return (
    <div className="max-w-xl mx-auto mt-12 bg-white border rounded-2xl p-8 shadow-sm space-y-6">
      <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl">
        <p className="text-xs text-amber-800 font-mono font-bold">STATUS: CANONICAL STANDALONE PAGE (FULL SSR)</p>
        <p className="text-xs text-amber-700 mt-1">Anda mengakses rute ini via Hard Reload (F5) atau Direct Hit URL.</p>
      </div>
      <div>
        <span className="text-xs uppercase text-slate-400 font-bold">{product.category}</span>
        <h1 className="text-3xl font-extrabold text-slate-900 mt-1">{product.name}</h1>
        <p className="text-2xl font-bold text-emerald-600 mt-2">{product.price}</p>
      </div>
      <p className="text-slate-600 leading-relaxed">{product.description}</p>
      <div className="pt-6 border-t">
        <Link
          href="/"
          className="inline-block bg-indigo-600 text-white font-medium px-4 py-2 rounded-lg hover:bg-indigo-700 transition"
        >
          &larr; Kembali ke Katalog Penuh
        </Link>
      </div>
    </div>
  );
}
```

### Step 9: Menjalankan dan Verifikasi
Jalankan server pengembangan:
```bash
npm run dev
```
1. Buka `http://localhost:3000`. Klik "Detail Modal". Perhatikan URL berubah menjadi `http://localhost:3000/products/1` dan modal terbuka tanpa unmounting halaman utama.
2. Tekan **F5** (Hard Refresh).
3. **Hasil**: Laman beralih secara anggun ke tampilan halaman penuh kanonikal (Kuning/Amber box). Parallel interceptor diabaikan.

---

## 13. Exercises

### Level Easy
Ubah implementasi `app/@preview/(.)products/[id]/page.tsx` untuk menampilkan badge dinamis berupa timestamp client saat modal berhasil dibuka tanpa memicu re-render pada background layout.

### Level Medium
Tambahkan slot paralel kedua bernama `@notifications` di `app/layout.tsx`. Konfigurasikan file `default.tsx` dan `page.tsx`-nya untuk membaca query parameter `?notify=success`. Jika parameter tidak ada, kembalikan `null`. Jika ada, tampilkan floating alert bar di sisi kanan bawah layar menggunakan Suspense streaming.

### Level Hard
Buat implementasi nested dynamic interception. Dari dalam modal produk yang sedang diintersepsi (`@preview/(.)products/[id]`), sediakan link "Lihat Merchant". Ketika diklik, URL berubah menjadi `/merchants/[merchantId]` dan membuka modal lapis kedua (Stacked Modal) secara intercepting tanpa menghilangkan modal produk pertama dan background feed. Tangani lifecycle tombol Back browser agar menutup modal lapis kedua terlebih dahulu, lalu modal pertama, sebelum kembali ke feed.

---

## 14. Challenge (Arsitektur Skala Besar)

**Deskripsi Kasus Nyata**:  
Sebuah platform SaaS Healthcare mengelola rekam medis pasien dengan kepatuhan HIPAA. Arsitektur aplikasi menuntut fitur *Split-Pane Workspace*:
- URL utama: `/patients/[patientId]/records`
- Di dalam layar tersebut, dokter dapat mengklik daftar rujukan lab yang merubah URL ke `/patients/[patientId]/records/lab/[labId]`.
- **Tantangan Arsitektur**:
  1. Panel rekam medis kiri harus mempertahankan scroll position dan form state yang belum tersimpan (*uncommitted input fields*).
  2. Panel kanan harus memuat hasil lab via parallel slot.
  3. Namun, jika URL diakses oleh analis farmasi dari luar sistem (direct link), analis tersebut **dilarang** melihat panel rekam medis kiri, melainkan dialihkan secara kanonikal ke antarmuka terisolasi `/lab-only/[labId]`.
  4. Desain pohon direktori App Router lengkap beserta skema middleware/guarding untuk mencegah kebocoran data pada hard refresh vs soft navigation.

*Tuliskan struktur folder lengkap, isi middleware resolusi rute, dan mitigasi Router Cache poisoning.*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)

#### Q1. Karakter konvensi apa yang digunakan oleh Next.js untuk menandai folder sebagai Parallel Route Slot?
- A. `[slotName]`
- B. `(slotName)`
- C. `@slotName`
- D. `_slotName`
*Kunci: C*  
*Rasional: Folder dengan awalan simbol `@` secara eksplisit mendefinisikan slot paralel dalam konvensi Next.js App Router dan tidak mempengaruhi struktur segmen URL.*

#### Q2. Apa tujuan utama dari file `default.tsx` pada Parallel Routes?
- A. Menjadi layout bawaan untuk semua rute.
- B. Menyediakan UI fallback ketika slot tidak cocok dengan rute aktif saat hard navigation.
- C. Menggantikan peran `page.tsx` saat file tersebut error.
- D. Mengaktifkan fitur Edge Streaming secara otomatis.
*Kunci: B*  
*Rasional: `default.tsx` wajib ada untuk menentukan apa yang harus dirender oleh slot paralel jika segmen URL saat ini tidak cocok dengan rute di dalam slot tersebut selama full page refresh.*

#### Q3. Interceptor marker `(..)` setara dengan operasi direktori apa?
- A. Level segmen yang sama.
- B. Dua level segmen di atas.
- C. Satu level segmen di atas.
- D. Root direktori `/app`.
*Kunci: C*  
*Rasional: Konvensi `(..)` mencocokkan segmen rute tepat satu level di atas direktori saat ini.*

#### Q4. Jika pengguna melakukan Hard Refresh (F5) saat berada pada URL yang diintersepsi, apa yang akan dirender oleh Next.js?
- A. Intercepted modal tetap muncul di atas layout sebelumnya.
- B. Rute kanonikal independen (Full page) dari target URL.
- C. Error 500 Internal Server Error.
- D. Redirect otomatis ke homepage `/`.
*Kunci: B*  
*Rasional: Hard navigation memotong router cache memory klien; server mengevaluasi rute murni berdasarkan URL kanonikal dan mengabaikan rule interception.*

#### Q5. Apakah nama folder parallel slot (misal: `@analytics`) akan tercermin di bar URL browser?
- A. Ya, selalu menjadi `/analytics`.
- B. Ya, hanya jika menggunakan intercepting routes.
- C. Tidak, slot parallel tidak memengaruhi segmen URL sama sekali.
- D. Hanya tercermin di environment production.
*Kunci: C*  
*Rasional: Parallel slots murni merupakan injeksi prop virtual level bundler dan tidak menambahkan segmen apapun ke dalam path URL.*

---

### Bagian 2: Intermediate (5 Soal)

#### Q6. Mengapa tombol penutup modal yang dibangun via Intercepting Routes sebaiknya memanggil `router.back()` daripada state setter lokal `setIsOpen(false)`?
- A. `router.back()` mengeksekusi lebih cepat karena bypass React fiber reconciler.
- B. Memanipulasi state lokal akan membiarkan URL browser tetap tertinggal di rute yang diintersepsi, merusak riwayat navigasi dan tombol forward/backward browser.
- C. State lokal tidak diizinkan di dalam folder bertanda kurung `(.)`.
- D. Next.js memblokir fungsi `useState` di dalam Client Components yang berada di bawah layout slot.
*Kunci: B*  
*Rasional: Intercepting routes mengikat UI modal ke URL. Jika modal ditutup lewat state internal tanpa memundurkan history stack URL, browser history akan mengalami desinkronisasi fatal terhadap representasi visual.*

#### Q7. Perhatikan struktur berikut:
```
app/
├── feed/
│   └── page.tsx
├── photos/
│   └── [id]/
│       └── page.tsx
└── @modal/
    └── (?)photos/
        └── [id]/
            └── page.tsx
```
Jika kita ingin mencegat URL `/photos/[id]` saat pengguna bernavigasi dari `/feed`, marker interceptor apa yang harus menggantikan `(?)` di dalam folder `@modal`?
- A. `(.)`
- B. `(..)`
- C. `(..)(..)`
- D. `(.)(.)`
*Kunci: B*  
*Rasional: URL pengirim adalah `/feed` (1 level dari root) dan target URL adalah `/photos/[id]`. Folder `@modal` berada di root direktori yang sejajar dengan `/feed` dan `/photos`. Dari perspektif segmen URL `/feed`, untuk mencapai segmen `/photos` diperlukan lompatan satu tingkat ke atas (`..`). Ingat bahwa folder `@modal` tidak dihitung sebagai level URL.*

#### Q8. Apa yang terjadi jika slot paralel `@sidebar` memicu runtime error pada komponen RSC-nya, namun memiliki file `@sidebar/error.tsx` terisolasi?
- A. Seluruh halaman crash dan menampilkan global error screen.
- B. Slot `@sidebar` menampilkan fallback error boundary lokal, sementara layout utama dan slot lainnya tetap beroperasi normal tanpa gangguan.
- C. Next.js secara otomatis me-redirect aplikasi ke default.tsx terdekat.
- D. Server runtime Node.js mati seketika.
*Kunci: B*  
*Rasional: Salah satu keunggulan utama Parallel Routes adalah isolasi error boundary. Error pada satu slot dapat ditangani secara lokal menggunakan `error.tsx` di folder slot tersebut tanpa merusak pohon UI segmen lain.*

#### Q9. Bagaimana Next.js RSC Payload dikirimkan ke browser saat berpindah antar Parallel Routes melalui soft navigation?
- A. Server merender ulang seluruh HTML dokumen via SSR dan mengirimkannya via WebSocket.
- B. Client mendownload bundle JavaScript baru untuk seluruh halaman.
- C. Client mengirim request fetch dengan header `RSC: 1` dan server mengalirkan payload diferensial (Flight data) hanya untuk slot-slot yang mengalami mutasi.
- D. Browser secara otomatis mengompilasi file TypeScript slot di web worker.
*Kunci: C*  
*Rasional: Next.js Client Router meminta payload RSC secara granular dengan mengirimkan representasi pohon rute saat ini melalui request header untuk menerima komputasi diff virtual DOM server.*

#### Q10. Pada saat apa pemanggilan hook `useSelectedLayoutSegment` atau `useSelectedLayoutSegments` sangat krusial digunakan bersama Parallel Routes?
- A. Untuk mengukur kecepatan rendering slot.
- B. Untuk membaca parameter string SQL secara aman.
- C. Untuk mendeteksi segmen aktif di dalam slot paralel tertentu secara programmatic guna menerapkan conditional styling pada layout induk.
- D. Untuk menghapus cache memori browser secara manual.
*Kunci: C*  
*Rasional: `useSelectedLayoutSegment('slotName')` memungkinkan layout induk mengetahui rute aktif apa yang sedang dirender di dalam parallel slot tertentu, sangat berguna untuk animasi tab dan conditional paneling.*

---

### Bagian 3: Production Scenarios (3 Soal Kasus)

#### Skenario 1: Bug Hilangnya State Form Background
Tim Anda membangun platform e-commerce enterprise. Di halaman `/checkout`, terdapat form input multi-step yang sangat panjang (kartu kredit, alamat, dll) yang disimpan di state React. Di dalam form tersebut terdapat link bantuan: `<Link href="/help/terms" scroll={false}>`. Anda telah membuat interceptor `app/checkout/@modal/(.)help/terms/page.tsx`. Namun, ketika user mengklik link dan modal terms terbuka, seluruh input form pada halaman checkout terhapus (re-mounted dari default state).  
**Apa akar masalah teknisnya dan bagaimana solusinya?**
- A. Slot modal harus dibungkus dengan `React.memo` agar form tidak re-mount.
- B. Link bantuan tidak sengaja memicu Hard Navigation karena menggunakan tag `<a>` murni, atau layout pada `/checkout` meletakkan `{children}` di dalam blok kondisional yang menyebabkan unmounting DOM tree.
- C. Next.js secara default menghapus seluruh memori heap saat Intercepting Route dipicu untuk menjaga keamanan HIPAA/PCI-DSS.
- D. Interceptor `(.)help` harus diubah menjadi `(...)help`.
*Kunci: B*  
*Rasional: Navigasi intercepting via Next.js `<Link>` dijamin mempertahankan state React komponen background asalkan layout tidak di-unmount dan navigasi benar-benar berupa soft navigation (bukan standard anchor tag atau script redirect yang menyebabkan browser hard reload).*

#### Skenario 2: Cache Poisoning pada Rute Terintersepsi di CDN Edge
Sebuah media publikasi berita menerapkan intercepting route untuk pratinjau artikel cepat: `/article/[id]`. Mereka mendapati bahwa pengguna yang mengakses langsung dari Google Search sering kali mendapatkan format response JSON mentah (RSC wire format: `1:HL["..."]`) alih-alih dokumen HTML lengkap.  
**Mengapa fenomena ini terjadi pada edge cache (misal: Cloudflare/Fastly)?**
- A. Next.js mengalami memory leak pada V8 engine edge worker.
- B. CDN Edge meng-cache response tanpa memasukkan header `Vary: RSC, Next-Router-State-Tree, Accept`. Akibatnya, request soft-navigation (yang meminta payload RSC) tersimpan di CDN dan dikirimkan ke request browser kanonikal biasa.
- C. Intercepting route tidak boleh digunakan bersama dynamic routes `[id]`.
- D. Search engine crawler memblokir intercepting routes secara otomatis.
*Kunci: B*  
*Rasional: HTTP Cache Poisoning terjadi jika CDN tidak mengikutsertakan header pembeda konten dalam `Vary key`. Karena URL request-nya identik (`/article/1`), request ber-header `RSC: 1` mengembalikan payload RSC stream. Jika di-cache sebagai representasi URL tersebut secara global, request dokumen HTML standar dari browser akan menerima payload JSON RSC tersebut.*

#### Skenario 3: Infinite Interception Loop Saat Direct Reload
Seorang engineer mencoba membuat fitur auth login modal menggunakan interception: mengklik login dari `/dashboard` membuka URL `/login` di dalam modal via `app/@auth/(.)login/page.tsx`. Di dalam rute kanonikal `app/login/page.tsx`, engineer tersebut menambahkan redirect:
```tsx
// app/login/page.tsx
if (condition) {
  redirect('/dashboard');
}
```
Saat user membuka URL `https://app.com/login` langsung dari tab kosong, terjadi infinite redirect loop yang merusak server.  
**Apa kesalahan struktural pada implementasi ini?**
- A. Redirect tidak boleh dijalankan di Server Component.
- B. Logika kondisi login mengevaluasi URL tanpa mempertimbangkan context header `Next-Url`, sehingga server memantulkan kembali request ke rute asal yang kembali memanggil interceptor.
- C. Fungsi `redirect()` Next.js melempar error internal `NEXT_REDIRECT` yang tertangkap secara salah oleh interceptor route.
- D. Slot `@auth` tidak memiliki file `loading.tsx`.
*Kunci: B*  
*Rasional: Manipulasi redirect pada rute kanonikal yang juga memiliki padanan interceptor harus sangat berhati-hati terhadap header referer dan Next-Url. Siklus redirect tak terbatas terjadi ketika aturan redirect melempar user ke path yang secara otomatis mencoba mengintersepsi kembali URL target tanpa validasi otentikasi state terminal.*

---

## 16. Summary

1. **Parallel Routes (`@slot`)** memecah monolith layout menjadi beberapa slot independen. Slot ini memungkinkan eksekusi render konkuren, *independent streaming*, serta isolasi kegagalan (*error boundary*) per-komponen di tingkat routing tanpa memodifikasi URL browser.
2. **`default.tsx` adalah Jaring Pengaman Mutlak**. Kegagalan menyediakan `default.tsx` pada parallel slot yang aktif akan menghasilkan status HTTP 404 ketika pengguna melakukan hard refresh (F5) pada segmen anak yang tidak cocok.
3. **Intercepting Routes (`(.)`, `(..)`, `(...)`)** mengeksekusi segment hijacking pada level Router State Tree memori klien. Pola ini membedakan secara tegas antara **Soft Navigation** (menampilkan modal di atas konteks saat ini) dan **Hard Navigation** (menampilkan halaman kanonikal penuh yang SEO-friendly).
4. **URL Masking vs Native Sync**: Intercepting routes menjaga integritas URL bar browser agar tetap dapat dibagikan (*shareable*), dapat di-bookmark, dan memiliki riwayat history yang benar menggunakan standard Web Navigation API (`router.back()`).
5. **Skala Produksi**: Penggunaan kombinasi Parallel dan Intercepting routes membutuhkan kewaspadaan tinggi terhadap konfigurasi CDN Caching (header `Vary`), kebersihan unmounting state, serta konsistensi level direktori relatif URL versus struktur folder fisik aplikasi.