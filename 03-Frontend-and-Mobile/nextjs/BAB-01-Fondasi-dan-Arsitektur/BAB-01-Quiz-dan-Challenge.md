# BAB 01: Quiz, Challenge, & Knowledge Check
**Arsitektur Komputasi & Mental Model App Router**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dikotomi Paradigma RSC vs SSR Klasik
Jelaskan secara fundamental perbedaan arsitektur antara **React Server Components (RSC)** pada App Router dan **Server-Side Rendering (SSR)** klasik (sebagaimana di Pages Router). Mengapa pernyataan *"RSC hanyalah SSR yang dijalankan tanpa hook `useEffect`"* merupakan kekeliruan fatal dalam memahami mental model komputasi Next.js modern? Uraikan dari perspektif execution lifecycle, JavaScript bundle footprint, dan format payload yang dikirimkan melalui wire protocol!

### Soal 1.2: Boundary Komposisi dan Anatomi Directive `"use client"`
Banyak developer mengira directive `"use client"` menandakan bahwa komponen tersebut dieksekusi *hanya* di browser. 
1. Bedah mekanisme sebenarnya dari directive `"use client"` pada level kompilator (bundler split point)!
2. Jelaskan mengapa sebuah Client Component tetap dieksekusi di server saat initial page load (pre-rendering)!
3. Bagaimana teknik arsitektural *Component Inversion / Slot Composition* (melewatkan Server Component sebagai `children` ke dalam Client Component) memungkinkan eksekusi kode server di dalam pohon subtree Client Component tanpa mengubah Server Component tersebut menjadi Client Component?

### Soal 1.3: Dynamic Rendering Inference & De-optimization Heuristics
Next.js App Router secara default memperlakukan route segments sebagai *Static Rendering*.
1. Sebutkan dan jelaskan *Dynamic APIs* (seperti `cookies()`, `headers()`, `searchParams`) yang secara otomatis mengubah perilaku kompilator dari Static ke Dynamic Rendering!
2. Mengapa pemanggilan `cookies()` pada Root Layout (`app/layout.tsx`) berdampak sistemik terhadap seluruh rute di bawahnya? Jelaskan konsekuensinya terhadap kemampuan CDN melakukan edge caching!

### Soal 1.4: Protokol Streaming dan Chunked Transfer Encoding
Jelaskan bagaimana integrasi antara **React Suspense** dan HTTP standard **Chunked Transfer Encoding** (`Transfer-Encoding: chunked`) merevolusi metrik Time to First Byte (TTFB) dan First Contentful Paint (FCP). Bagaimana browser merestorasi DOM subtree ketika sebuah chunk HTML yang dibungkus `<Suspense>` selesai di-stream belakangan oleh server?

### Soal 1.5: Serialization Boundary & The RSC Wire Format
Komunikasi data antara Server Component Tree dan Client Component Tree dibatasi oleh aturan serialisasi data.
1. Mengapa tipe data seperti native JavaScript `Function`, `Symbol`, `Map`/`Set` (pada implementasi standar), atau class instance (misalnya instance Prisma Client) memicu fatal error jika dilewatkan langsung via props dari Server Component ke Client Component?
2. Jelaskan struktur umum dari **RSC Payload** (format data berbasis baris/stream dengan marker seperti `$`, `@`, `S`) dan bagaimana browser menggunakan payload tersebut untuk merekonstruksi virtual DOM tanpa memicu re-fetch data!

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Caching Topology & Multi-Layer Invalidation
Next.js App Router memiliki 4 lapisan cache internal:
- **Request Memoization** (React core)
- **Data Cache** (Next.js server-side persistent fetch cache)
- **Full Route Cache** (Server build/revalidate cache)
- **Router Cache** (Client-side in-memory browser cache)

Gambarkan interaksi antar-lapisan ini saat sebuah HTTP request masuk! Apa yang terjadi secara mekanistik pada masing-masing layer ketika fungsi `revalidatePath('/dashboard')` dieksekusi di dalam Server Action?

### Soal 2.2: Root Cause Analysis Hydration Mismatch
Perhatikan snippet berikut yang memicu error: `Error: Hydration failed because the initial UI does not match what was rendered on the server`:

```tsx
// app/components/UserGreeting.tsx
'use client';

export default function UserGreeting() {
  const currentHour = new Date().getHours();
  const greeting = currentHour < 12 ? "Selamat Pagi" : "Selamat Malam";
  const userAgent = typeof window !== 'undefined' ? window.navigator.userAgent : 'Server';

  return (
    <div className="p-4 border">
      <h1>{greeting}</h1>
      <p>Device: {userAgent}</p>
      <span>Rendered at: {Date.now()}</span>
    </div>
  );
}
```
1. Identifikasi secara spesifik tiga titik kegagalan (*failure points*) yang memicu hydration mismatch pada komponen di atas!
2. Mengapa React runtime memilih untuk membuang (discard) subtree DOM server dan melakukan re-render penuh pada klien ketika terjadi ketidaksesuaian fatal, dan apa dampaknya terhadap Core Web Vitals (khususnya INP dan CLS)?
3. Tuliskan arsitektur perbaikan yang elegan menggunakan pola *two-pass rendering* atau isolasi dynamic value yang tepat!

### Soal 2.3: Module Scope Leakage & The `server-only` Guardrail
Dalam proyek berskala besar, seorang developer menulis utilitas database berikut:

```ts
// lib/db.ts
import { Pool } from 'pg';

export const dbPool = new Pool({
  connectionString: process.env.DATABASE_PRIVATE_URL,
});

export async function getUserSecret(userId: string) {
  const res = await dbPool.query('SELECT secret_token FROM users WHERE id = $1', [userId]);
  return res.rows[0];
}
```
Tanpa sengaja, fungsi `getUserSecret` diimpor ke dalam sebuah Client Component helper.
1. Apa yang terjadi pada nilai `process.env.DATABASE_PRIVATE_URL` di sisi client bundle jika variabel tersebut tidak diawali dengan `NEXT_PUBLIC_`?
2. Bagaimana mekanisme kerja internal paket `server-only` dalam mentransformasi proses kompilasi bundler (Webpack/Turbopack) sehingga insiden kebocoran kode backend ke bundle browser dapat digagalkan secara deterministik pada saat *build time*?

### Soal 2.4: Parallel and Intercepting Routes State Machine
Ketika mengimplementasikan modal dialog menggunakan kombinasi **Parallel Routes** (`@modal`) dan **Intercepting Routes** (`(..)photos/[id]`):
1. Mengapa navigasi *soft-navigation* (via `<Link>`) menampilkan modal overlay di atas halaman saat ini, sedangkan saat halaman di-*hard refresh* (F5), Next.js me-render halaman rute target secara penuh tanpa modal?
2. Apa fungsi teknis dari file `default.tsx` pada parallel routing slot, dan kegagalan sistemik apa yang terjadi pada runtime jika file `default.tsx` diabaikan saat menangani route transitions?

### Soal 2.5: Waterfalls vs Cascading Suspense Architecture
Misalkan Anda memiliki hirarki RSC berikut:
```tsx
// app/dashboard/page.tsx
export default async function Page() {
  const metrics = await fetchMetrics(); // butuh waktu 1.8 detik
  return (
    <main>
      <MetricsView data={metrics} />
      <Suspense fallback={<AnalyticsSkeleton />}>
        <AnalyticsSection /> {/* di dalamnya ada await fetchAnalytics() butuh 2.5 detik */}
      </Suspense>
    </main>
  );
}
```
1. Analisis mengapa arsitektur di atas memicu masalah **Sequential Waterfall** tersembunyi yang membuat boundary `<Suspense>` untuk `<AnalyticsSection>` kehilangan efektivitasnya secara total!
2. Rekonstruksi struktur tree component tersebut menggunakan pola **Parallel Data Fetching** atau dekomposisi Suspense granular agar Time to First Byte (TTFB) turun drastis ke level sub-100ms!

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Skala Besar (Cascading Latency Collapse Pasca-Migrasi)
**Latar Belakang:**  
Sebuah platform E-Commerce berskala enterprise memigrasikan halaman katalog produk dari Pages Router (`getServerSideProps`) ke App Router. Beberapa jam setelah deployment ke production, metrik server latency melonjak 600%, database connection pool ke PostgreSQL habis (*pool exhaustion*), dan layanan mengalami degradasi parsial (HTTP 504 Gateway Timeout).

**Hasil Investigasi Awal:**
1. Developer membuat wrapper otentikasi global di dalam file `app/layout.tsx`:
   ```tsx
   // app/layout.tsx
   export default async function RootLayout({ children }: { children: React.ReactNode }) {
     const cookieStore = cookies();
     const sessionToken = cookieStore.get('session_id')?.value;
     const user = await validateSessionWithDatabase(sessionToken); // Hit DB setiap request!
     
     return (
       <html>
         <body>
           <AuthProvider initialUser={user}>
             {children}
           </AuthProvider>
         </body>
       </html>
     );
   }
   ```
2. Halaman detail produk (`app/products/[slug]/page.tsx`) yang sebelumnya di-cache statis via ISR, kini selalu dieksekusi ulang secara dinamis untuk setiap request visitor publik.

**Pertanyaan Diagnostik:**
1. Jelaskan rantai kausalitas (*causal chain*) bagaimana pemanggilan `cookies()` di `RootLayout` memicu dynamic de-optimization secara global pada seluruh sub-tree rute aplikasi!
2. Mengapa isolasi session check menggunakan middleware dan arsitektur komposisi RSC bertingkat dapat memecahkan masalah ini tanpa harus memvalidasi session di level layout teratas?
3. Rancang arsitektur baru untuk Root Layout dan rute produk agar halaman katalog tetap berstatus *Static / Incremental Static Regeneration (ISR)* di Edge CDN, namun widget profil pengguna di Header tetap bersifat dinamis dan aman!

---

### Skenario B: Cross-Tenant Data Bleed & Cache Poisoning
**Latar Belakang:**  
Aplikasi SaaS Multi-Tenant B2B perbankan mendapati laporan insiden keamanan kritis: Tenant A sesekali dapat melihat ringkasan portofolio keuangan Tenant B pada halaman `/analytics`. Arsitektur data fetching yang dibangun developer tampak seperti berikut:

```ts
// lib/api/client.ts
let globalAuthToken: string = '';

export function setAuthToken(token: string) {
  globalAuthToken = token;
}

export async function fetchCompanyMetrics(tenantId: string) {
  return fetch(`https://api.internal.bank/metrics/${tenantId}`, {
    headers: {
      Authorization: `Bearer ${globalAuthToken}`,
    },
    next: { revalidate: 300 } // Data di-cache selama 5 menit
  }).then(res => res.json());
}
```

Dieksekusi di Server Component:
```tsx
// app/[tenant]/analytics/page.tsx
export default async function AnalyticsPage({ params }: { params: { tenant: string } }) {
  const token = cookies().get('tenant_jwt')?.value;
  setAuthToken(token!);
  const metrics = await fetchCompanyMetrics(params.tenant);

  return <AnalyticsDashboard data={metrics} />;
}
```

**Pertanyaan Diagnostik:**
1. Bedah dua celah fatal (*critical vulnerabilities*) pada implementasi kode di atas yang menyebabkan **Cross-Tenant Data Bleed** dalam lingkungan concurrency runtime Node.js serverless/container!
2. Jelaskan konsep **Module Scope State Preservation** pada server runtime Node.js dan mengapa variabel mutable di luar lifecycle fungsi me-render bencana pada aplikasi multi-user!
3. Mengapa konfigurasi `next: { revalidate: 300 }` pada native `fetch` di atas bertindak sebagai vektor *Data Cache Poisoning* antar-tenant? Bagaimana arsitektur cache key isolation yang benar jika data tersebut bersifat privat dan confidential?

---

### Skenario C: The Layout Shift & Cascading Spinners Crisis
**Latar Belakang:**  
Sebuah aplikasi web FinTech membedah Dashboard Keuangan (`/portal`) menjadi 4 bagian independen:
- `AccountBalance` (SLA upstream API: 150ms)
- `RecentTransactions` (SLA upstream API: 400ms)
- `CreditScoreWidget` (SLA upstream API: 2800ms, sering timeout)
- `MarketNewsFeed` (SLA upstream API: 1200ms)

Developer mengimplementasikan Suspense boundaries untuk masing-masing widget secara terpisah di dalam `page.tsx`:

```tsx
export default function PortalPage() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <Suspense fallback={<Spinner className="h-40" />}>
        <AccountBalance />
      </Suspense>
      <Suspense fallback={<Spinner className="h-40" />}>
        <RecentTransactions />
      </Suspense>
      <Suspense fallback={<Spinner className="h-40" />}>
        <CreditScoreWidget />
      </Suspense>
      <Suspense fallback={<Spinner className="h-40" />}>
        <MarketNewsFeed />
      </Suspense>
    </div>
  );
}
```

**Permasalahan UX:**
Pengguna mengalami fenomena *"Janky Layout Flash / UI Popcorn"* di mana antarmuka melompat-lompat secara konstan selama 3 detik, Cumulative Layout Shift (CLS) melonjak ke angka 0.42 (kategori "Poor"), dan jika `CreditScoreWidget` gagal (API 500), seluruh rute crash ke `error.tsx` terdekat karena ketiadaan Error Boundary lokal.

**Pertanyaan Diagnostik:**
1. Evaluasi trade-off arsitektur antara **Single Monolithic Suspense Boundary** vs **Hyper-Granular Suspense Boundaries** pada kasus di atas. Kapan granularitas Suspense justru merusak User Experience?
2. Bagaimana teknik rekayasa UI (CSS aspect-ratio reservation, skeleton matching, dan layout placeholder coordination) dapat mengeliminasi CLS secara total saat respons HTTP chunked streaming mendarat di browser?
3. Rancang arsitektur ketahanan sistem (*resilience architecture*) yang memadukan kombinasi `<Suspense>`, granular local React Error Boundaries, dan pattern *Graceful Degradation* sehingga kegagalan pada `CreditScoreWidget` tidak merusak widget lainnya serta menampilkan UI fallback kontekstual dengan tombol retry terisolasi!

---

## 4. Chapter Challenge

### Tantangan Praktis: Zero-Client-Footprint Dynamic Data Matrix dengan Interleaved Streaming Architecture

#### Deskripsi Skenario
Anda ditugaskan merancang arsitektur dashboard monitoring performa server multi-region (*Global Edge Analytics Matrix*) untuk sebuah cloud platform. Dashboard ini harus mampu menampilkan puluhan metrik dengan update frekuensi tinggi, namun memiliki aturan mutlak dari Head of Engineering: **Bundle JavaScript client-side yang dikirimkan ke browser untuk halaman ini harus ditekan seminimal mungkin (Zero-Client Footprint target untuk display data) tanpa mengorbankan interaktivitas real-time filter dan granular streaming.**

#### Requirements
1. **Interleaved Tree Architecture:**
   - Bangun sebuah Client Component pembungkus interaktif: `<MatrixShell />` yang mengelola local client state (misalnya: filter status aktif, dark/light view mode switcher, dan keyword search input).
   - Seluruh visualisasi metrik data tabular dan status server **wajib** berupa Server Components (`<ServerRackStatus />`, `<LatencyTable />`, `<BandwidthStream />`) yang disuntikkan ke dalam `<MatrixShell />` menggunakan arsitektur **Inversion of Control (Component Composition)** via `children` atau named slots.
2. **True Out-of-Order Streaming Execution:**
   - Komponen `<LatencyTable />` mengambil data lambat (simulasikan artificial delay 3000ms).
   - Komponen `<ServerRackStatus />` mengambil data cepat (simulasikan delay 400ms).
   - Implementasikan boundary `<Suspense>` terpisah dengan High-Fidelity Skeletons (identik secara dimensional terhadap rendered content untuk mencegah CLS = 0). Komponen cepat harus muncul ke layar secara instan tanpa terblokir oleh komponen lambat.
3. **Isolasi Dynamic APIs & Zero Secret Leakage:**
   - Dashboard memerlukan data session token dan custom header organisasi (`x-organization-id`).
   - Terapkan dynamic API usage (`headers()`) secara terisolasi sedemikian rupa sehingga rute tidak membocorkan credential, menggunakan package `server-only` untuk modul query internal, dan tidak menyebabkan static siblings di luar dashboard rute ter-deoptimasi.
4. **Resilient Local Error Handling:**
   - Simulasikan kemungkinan kegagalan 50% pada data fetching `<BandwidthStream />`. 
   - Bungkus widget tersebut dengan granular React Error Boundary di tingkat server-client bridge agar jika widget gagal, hanya area widget tersebut yang menampilkan pesan kesalahan dan opsi retry, sementara widget lain tetap berfungsi normal.

#### Constraints
- Dilarang keras menggunakan hook `useEffect` untuk fetching data! Seluruh fetching harus dieksekusi di level Server Components.
- Ukuran bundle JavaScript Client Component untuk halaman ini dibatasi maksimal **< 5 KB (Gzip)** di luar core React/Next.js runtime.
- Dilarang menyertakan string konfigurasi database atau token API di dalam Client Component, baik langsung maupun melalui serialisasi props.
- Wajib TypeScript dengan strict type-checking tanpa `any`.

#### Expected Output
1. File struktur modular (`page.tsx`, `MatrixShell.tsx`, `LatencyTable.tsx`, `ServerRackStatus.tsx`, `BandwidthStream.tsx`, `error-boundary.tsx`).
2. Kode implementasi lengkap yang mengilustrasikan teknik **Slot Composition Pattern** dan penanganan Suspense streaming.
3. Analisis penjelasan teknis berbobot mengenai rute eksekusi data flow: bagaimana RSC Payload di-stream dari Node.js server, bagaimana React reconciler di browser menjahit Server VDOM ke dalam Client Slot state, dan bagaimana Core Web Vitals (FCP, LCP, CLS) dioptimalkan secara arsitektural.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental antara kompilasi RSC Payload vs HTML generation pada SSR klasik.
- [ ] Bahwa directive `"use client"` bukan penanda "eksekusi hanya di client", melainkan boundary cut-point pemisahan kompilasi antara Server Graph dan Client Graph.
- [ ] Aturan ketat serialisasi melintasi Server-Client Boundary (JSON-like serializable constraint + React element references).
- [ ] Bagaimana Server Component dapat disarangkan (*nested*) di dalam Client Component melalui teknik komposisi `props.children` tanpa diubah menjadi Client Component.
- [ ] Hierarki dan siklus hidup 4 lapisan cache Next.js: Request Memoization, Data Cache, Full Route Cache, dan Router Cache.
- [ ] Mengapa pemanggilan Dynamic APIs (`cookies()`, `headers()`) memicu de-optimisasi Full Route Cache pada segmen rute terkait.
- [ ] Mekanisme kerja HTTP Chunked Transfer Encoding dalam menyajikan respons React Suspense secara streaming bertahap.
- [ ] Bahwa import module scope di server runtime bersifat persisten (*singleton-like*) antar-request dalam process lifecycle yang sama, sehingga mutable global state di server adalah anti-pattern kritis.
- [ ] Cara kerja paket `server-only` dalam melempar build-time error ketika kode backend tak sengaja bocor ke client graph.

### Saya tidak perlu menghafal:
- [ ] Karakter penanda internal (*internal wire format flags*) dari RSC payload engine (misal format string internal byte `$1`, `HL`, `["$","$L1",...]`).
- [ ] Algoritma internal hashing yang digunakan React core untuk Request Memoization key generation.
- [ ] Seluruh daftar konfigurasi internal Webpack/Turbopack loader yang menangani transformasi directive `"use client"`.

### Saya harus bisa melakukan:
- [ ] Menentukan letak garis batas (*boundary placement*) yang presisi antara Server Component dan Client Component untuk meminimalkan ukuran bundle JS client.
- [ ] Melakukan troubleshooting dan memperbaiki error *Hydration Mismatch* dengan menganalisis perbedaan server snapshot vs client state.
- [ ] Mengisolasi konsumsi dynamic functions (`cookies()`, `headers()`) ke rute atau sub-tree terkecil agar tidak merusak cache static sibling components.
- [ ] Membangun layout dengan zero Cumulative Layout Shift (CLS) menggunakan kombinasi Suspense streaming dan dimensionally accurate UI Skeletons.
- [ ] Mengonfigurasi proteksi *server-only boundaries* untuk mengamankan kredensial database dan environment variables sensitif dari kebocoran ke browser.
- [ ] Mengonstruksi arsitektur routing paralel dan intersepting dengan fail-safe `default.tsx` fallback handling.