# BAB 03: Quiz, Challenge, & Knowledge Check
**Paradigma Rendering: RSC, Streaming, & Partial Prerendering (PPR)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Evolusi Paradigma: SSR Klasik vs. React Server Components (RSC)**  
   Jelaskan perbedaan fundamental arsitektur antara Server-Side Rendering (SSR) konvensional (seperti pada Next.js Pages Router) dengan React Server Components (RSC) pada App Router dalam hal artefak yang dikirimkan melalui jaringan (*network payload*), siklus hidup eksekusi (*execution lifecycle*), dan dampaknya terhadap JavaScript bundle size di sisi klien!

2. **Hydration Boundary & Aturan Serialisasi Props**  
   Ketika menandai sebuah modul dengan direktif `'use client'`, modul tersebut menjadi batas hidrasi (*client-server boundary*). Mengapa Anda tidak dapat mengoper fungsi non-serializable (seperti callback event handler atau instance class kustom) dari Server Component ke Client Component sebagai props? Analisis batasan ini dari sudut pandang representasi *RSC Payload wire format*!

3. **Mekanisme HTTP Chunked Transfer Encoding pada Streaming SSR**  
   Secara arsitektural, bagaimana React 18 `<Suspense>` dan Next.js memanfaatkan HTTP/1.1 `Transfer-Encoding: chunked` (atau HTTP/2 data frames) untuk mengalirkan potongan HTML dan script *in-flight* ke browser sebelum seluruh data tree selesai di-resolve di server?

4. **Anatomi Partial Prerendering (PPR)**  
   Partial Prerendering menggabungkan SSG dan SSR dalam satu HTTP request yang sama. Uraikan bagaimana compiler Next.js membedakan *static shell* dan *dynamic holes* pada fase build! Apa keuntungan arsitektural PPR dibanding pendekatan tradisional "SSG Shell + Client-side Data Fetching (SWR/React Query)"?

5. **Dynamic Functions dan Degradasi Prerendering**  
   Mengapa pemanggilan fungsi-fungsi seperti `cookies()`, `headers()`, atau pembacaan `searchParams` secara langsung menurunkan status rendering rute dari static (*prerendered*) menjadi dynamic rendering? Bagaimana cara mengisolasi pemanggilan fungsi-fungsi ini agar tidak "meracuni" (*poisoning*) status statis dari rute induknya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **RSC Poisoning & Server-Only Boundaries**  
   Sebuah modul utilitas `db.ts` memuat Prisma Client dan token rahasia database. Modul ini secara tidak sengaja diimpor oleh komponen utilitas helper yang juga diimpor oleh Client Component (`'use client'`).  
   * **Pertanyaan:** Mengapa Next.js compiler kadang memunculkan error build yang ambigu pada kasus ini? Bagaimana mekanisme paket `server-only` mencegah kebocoran kode rahasia ini ke client bundle saat proses kompilasi Webpack/Turbopack?

2. **Dilema Server-Driven Waterfall vs. Parallel Suspense Fetching**  
   Perhatikan pola hierarki RSC berikut:
   ```tsx
   // Parent RSC
   export default async function Dashboard() {
     const user = await getUser();
     return (
       <div>
         <Suspense fallback={<SkeletonA />}>
           <Metrics user={user} />
         </Suspense>
         <Suspense fallback={<SkeletonB />}>
           <Analytics user={user} />
         </Suspense>
       </div>
     );
   }
   ```
   * **Pertanyaan:** Jika `Metrics` dan `Analytics` sama-sama melakukan fetching asinkron yang independen tetapi membutuhkan ID dari `user`, bagaimana pola eksekusi microtask di Node.js runtime menangani ini? Kapan waterfall tetap terjadi meskipun sudah dibungkus dengan `<Suspense>`, dan bagaimana arsitektur komposisi yang ideal untuk memaksimalkan throughput streaming?

3. **Mekanisme Preservasi State Klien saat Re-rendering RSC**  
   Ketika pengguna memicu `router.refresh()` atau mengeksekusi Server Action yang mengembalikan data baru, server akan me-render ulang pohon RSC dan mengirimkan payload baru ke klien.  
   * **Pertanyaan:** Bagaimana React Reconciliation Engine mencocokkan (*diffing*) RSC Payload baru dengan DOM tree yang ada tanpa mereset lokal state (seperti input teks atau status scroll) di dalam Client Component anak?

4. **Debugging Hydration Mismatch pada Dynamic Holes**  
   Sebuah aplikasi Next.js mengalami *Layout Shift* dan error konsol: `Text content does not match server-rendered HTML` pada boundary yang dibungkus `<Suspense>` saat di-deploy ke Edge Network dengan PPR aktif.  
   * **Pertanyaan:** Apa penyebab paling umum perbedaan representasi antara prerendered shell fallback dengan streamed chunk saat fallback digantikan oleh konten dinamis? Bagaimana Anda mendiagnosis apakah masalahnya ada di serialisasi tanggal (*timezone mismatch*), akses objek `window`, atau CDN Edge-caching anomali?

5. **Deep Dive: Double Payload Problem pada Initial Page Load**  
   Saat pertama kali mengakses URL rute Next.js App Router (bukan navigasi SPA), browser menerima respons HTML awal DAN sebuah script tag yang berisi serialized *RSC Payload* inline.  
   * **Pertanyaan:** Mengapa Next.js harus menduplikasi data tersebut (mengirim data dalam bentuk HTML ter-render sekaligus raw data dalam RSC Payload inline)? Apa dampaknya terhadap Time-to-First-Byte (TTFB) vs Time-to-Interactive (TTI) jika data tree sangat besar?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Masif pada Flash-Sale E-Commerce (11.11 Event)
Sistem e-commerce Anda mengalami lonjakan traffic 100x lipat saat kampanye flash sale. Arsitektur halaman produk (`/products/[id]`) menggunakan Dynamic Server-Side Rendering karena layout menampilkan:
* Data produk dasar (statis: judul, deskripsi, gambar).
* Stok inventaris real-time (sangat dinamis: berubah tiap milidetik).
* Rekomendasi personalisasi berbasis AI (lambat: latensi p99 ~1.8 detik).
* Status keranjang belanja user yang login (berbasis cookie session).

**Masalah:** TTFB melonjak hingga 2.5 detik, koneksi database pool exhausted karena semua query dieksekusi secara sinkron di tingkat root layout sebelum respon pertama dikirim. Server Node.js mulai mengembalikan HTTP 504 Gateway Timeout.

* **Pertanyaan Diagnostik & Solusi:**
  1. Bagaimana Anda merestrukturisasi halaman ini menggunakan arsitektur **Partial Prerendering (PPR)** dan **Streaming SSR** agar CDN Edge dapat langsung menyajikan *static shell* dalam waktu < 50ms ke semua user?
  2. Komponen mana yang harus diisolasi ke dalam dynamic holes, bagaimana hierarki `<Suspense>` disusun, dan strategi data fetching apa yang harus diterapkan untuk stok real-time agar tidak memblokir render rekomendasi AI?

---

### Skenario B: Race Condition dan Cache Leakage pada Multi-Tenant Dashboard
Sebuah aplikasi SaaS multi-tenant perbankan menggunakan App Router. Setiap organisasi memiliki subdomain unik (`tenant1.app.com`, `tenant2.app.com`). Pengembang menggunakan fungsi `headers()` di root layout untuk mengekstrak subdomain dan menentukan tema serta skema data. Untuk optimasi performa, pengembang mengimplementasikan `unstable_cache` pada level fetch fungsi RSC untuk meng-cache ringkasan saldo akun perusahaan:

```tsx
export async function getAccountSummary(tenantId: string) {
  return unstable_cache(
    async () => fetchSummaryFromDB(tenantId),
    ['account-summary'],
    { revalidate: 60 }
  )();
}
```

**Insiden:** Pengguna dari Tenant A sesekali melihat data ringkasan saldo milik Tenant B setelah Tenant B melakukan refresh data.

* **Pertanyaan Diagnostik & Solusi:**
  1. Identifikasi akar penyebab arsitektural (*root cause*) dari kebocoran data (*data leakage*) di atas pada level caching layer Next.js!
  2. Bagaimana interaksi antara dynamic functions (`headers()`), cache key generation, dan Next.js Full Route Cache mempengaruhi terjadinya anomali isolasi tenant ini?
  3. Tuliskan refaktor kode yang tepat untuk memastikan data isolation 100% aman namun tetap memanfaatkan performa caching RSC!

---

### Skenario C: Migrasi Arsitektur Monolitik SPA ke Hybrid RSC Enterprise
Perusahaan fintech memiliki aplikasi web kompleks dengan 500+ komponen React (Vite-based SPA). Seluruh state diatur oleh Redux Toolkit, dan data di-fetch melalui Axios interceptors di sisi klien. Perusahaan memutuskan migrasi ke Next.js App Router untuk memperbaiki SEO dan First Contentful Paint (FCP). Tim engineering memigrasikan aplikasi dengan cara membungkus rute utama `/dashboard` dengan `'use client'` pada file `page.tsx` teratas agar Redux Provider dan seluruh lifecycle `useEffect` lama tetap berjalan tanpa refaktor besar-besaran.

**Dampak:** Bundle size halaman dashboard justru membengkak sebesar 35% dibandingkan aplikasi Vite lama, TTFB stagnan, dan core web vitals (khususnya INP - Interaction to Next Paint) anjlok secara signifikan.

* **Pertanyaan Diagnostik & Solusi:**
  1. Bedah secara teknis mengapa strategi *"All-in Client Component"* pada Next.js App Router menghasilkan overhead bundle dan inefisiensi performa yang lebih buruk daripada pure SPA bundler seperti Vite!
  2. Rancang *phased migration roadmap* dan panduan arsitektur dekomposisi komponen (Client-Server Composition Pattern) untuk memisahkan Redux-dependent UI (transaksional) dengan server-renderable UI (read-only charts, static navigation, auditing logs)!

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi High-Throughput Real-Time Financial Dashboard dengan Partial Prerendering (PPR)

#### Problem Statement
Anda diminta merancang prototipe inti untuk modul terminal pasar modal institusional pada rute `/markets/[ticker]`. Rute ini menuntut kecepatan initial load setara static site (TTFB < 50ms secara global melalui Edge), namun harus mampu memuat data fluktuasi harga berlatensi tinggi, order book real-time, dan status otentikasi portofolio pengguna secara terisolasi tanpa saling memblokir.

#### Requirements
1. **Routing & Composition Architecture:**
   * Terapkan canary flag `experimental.ppr = true` (atau mode PPR App Router terkini).
   * **Static Shell:** Breadcrumb, navigasi global, layout grid, dan profil metadata perusahaan (ticker name, description, exchange sector) harus di-prerender secara statis pada saat build time.
   * **Dynamic Hole 1 (Low Latency):** Widget otentikasi user & ringkasan portofolio (`UserBalance`) yang membaca session via `cookies()`.
   * **Dynamic Hole 2 (High Latency Data Streaming):** Widget performa historis saham (`MarketDepth`) yang memanggil API pihak ketiga dengan latensi artifisial 2.5 detik.
   * **Dynamic Hole 3 (Live Order Book):** Client Component (`OrderBookStreamer`) yang di-hydrate secara independen untuk menangani streaming harga via WebSocket/Server-Sent Events setelah halaman terpasang di browser.
2. **Boundary Isolation:**
   * Tidak boleh ada kebocoran dynamic execution ke dalam Static Shell (verifikasi via log build output; status rute harus teridentifikasi sebagai `◐ (Partial Prerender)`).
   * Bungkus dynamic holes dengan `<Suspense>` granular yang menampilkan skeleton visual presisi untuk meminimalkan Cumulative Layout Shift (CLS < 0.01).
3. **Data Security & Boundary Protection:**
   * Buat modul simulasi database `lib/vault.ts` yang memuat data sensitif API keys. Gunakan paket `server-only` untuk memastikan fungsi di dalamnya tidak dapat dieksekusi atau diimpor oleh modul berlabel `'use client'`.

#### Constraints
* **Framework:** Next.js 14.2+ atau 15+ (App Router).
* **Bundle Rules:** Komponen chart/websocket hanya boleh dimuat oleh Dynamic Hole 3; dynamic bundle JavaScript untuk client-side hydration pada shell statis harus mendekati 0 KB di luar runtime inti Next.js.
* **No Client Fetch on Shell:** Dilarang menggunakan `useEffect` fetching untuk profil metadata perusahaan; data ini wajib berasal dari Server Component.

#### Expected Output
1. Struktur direktori direktori file Next.js lengkap (`layout.tsx`, `page.tsx`, komponen RSC, dan komponen Client).
2. Kode lengkap `page.tsx` yang mendemonstrasikan orkestrasi Suspense, isolasi dynamic calls, dan streaming boundaries.
3. Penjelasan teknis ringkas (maks 2 paragraf) tentang bagaimana Next.js menyajikan rute ini ke browser: apa yang terjadi di milidetik ke-10, milidetik ke-100, dan milidetik ke-2500 saat request masuk.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan deterministik antara arsitektur SSR (Pages Router) vs Streaming RSC (App Router).
- [ ] Struktur data dan peran *RSC Payload* (Flight protocol representation) dalam proses hidrasi dan navigasi SPA.
- [ ] Batasan serialisasi boundary Client-Server: mengapa non-serializable objects (function, symbols, instances) tidak dapat melewati boundary props.
- [ ] Mekanisme kerja Partial Prerendering (PPR) dalam membagi satu pohon komponen menjadi *Prerendered HTML Shell* dan *Dynamic Microtask Streaming Chunks*.
- [ ] Efek samping (*cascading dynamic de-opt*) dari pemanggilan Dynamic APIs (`cookies()`, `headers()`, `searchParams`) terhadap kemampuan caching Next.js.
- [ ] Peran dan cara kerja HTTP `Transfer-Encoding: chunked` dalam mengalirkan HTML di React 18 Suspense.
- [ ] Mengapa Client Component (`'use client'`) tetap di-render di server pada initial page load, bukan sekadar dieksekusi di browser.

### Saya tidak perlu menghafal:
- [ ] Sintaks internal format biner/teks dari RSC Wire Format (misal: penanda tag `0:`, `M1:`, `"$"`, dll.).
- [ ] Konfigurasi webpack internal tingkat rendah yang mengatur code-splitting React Flight plugin.
- [ ] Seluruh signature method internal dari compiler parser Turbopack.

### Saya harus bisa melakukan:
- [ ] Mengaudit bundle client menggunakan tools analitik bundle untuk melacak Client Boundary leakage.
- [ ] Mengimplementasikan pola *RSC Composition (Lifting Content Up / Passing Server Components as Children)* untuk menghindari degradasi Client Component wrapper.
- [ ] Mencegah kebocoran modul server sensitif ke bundle browser menggunakan guardrail `import 'server-only'`.
- [ ] Memecah monolithic Suspense tree menjadi granular out-of-order streaming points untuk mengoptimalkan Core Web Vitals (FCP, LCP, CLS, INP).
- [ ] Melakukan troubleshooting dan resolving error *Hydration Mismatch* yang dipicu oleh dynamic data fallback desynchronization.