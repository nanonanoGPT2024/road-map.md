# BAB 05: Anatomi Mendalam 4-Tier Caching Pipeline
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal/Staff Engineer dan Senior Architect diharapkan mampu:
*   **Menganalisis & Merekayasa** lifecycle 4-Tier Caching Pipeline Next.js (Request Memoization, Data Cache, Full Route Cache, dan Router Cache) secara deterministik pada arsitektur terdistribusi.
*   **Mengimplementasikan** *Custom Cache Handler* berbasis Redis/Key-Value store terdistribusi untuk menggantikan default file-system cache pada cluster multi-node (Kubernetes/Serverless).
*   **Merancang** strategi mutasi data dan purifikasi cache tingkat lanjut menggunakan *tag-based on-demand revalidation* (`revalidateTag`, `revalidatePath`) bebas *race-condition* dan *cache stampede*.
*   **Mengaudit & Menangani** *dynamic bailouts* yang tidak diinginkan akibat penggunaan Dynamic APIs (`cookies()`, `headers()`, dynamic parameters) yang merusak efisiensi *Full Route Cache*.
*   **Mengoptimalkan** metrik *Time to First Byte* (TTFB) dan meminimalkan latensi eksekusi *Serverless/Edge Functions* menuju sub-50ms p99 pada skala puluhan ribu Request Per Second (RPS).

---

### 2. Prerequisite
*   Pemahaman mendalam mengenai arsitektur React Server Components (RSC) vs Client Components dan proses streaming payload RSC.
*   Kemahiran dalam TypeScript enterprise patterns (Generics, Type Narrowing, Async Protocols).
*   Pengalaman operasional dengan distributed storage engines (Redis, Memcached, atau KV Engines) dan protokol jaringan (HTTP/2, HTTP/3, Edge CDN mechanics).
*   Penyelesaian Modul 01: *Fundamental Next.js App Router & Rendering Pipeline Lifecycle*.

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur caching Next.js (khususnya App Router) bukanlah satu lapisan tunggal, melainkan sebuah **komposisi empat subsistem ortogonal** yang beroperasi secara sekuensial dan terkoordinasi antara Client, Server Runtime, dan Persistence Layer.

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT (BROWSER)                                 |
|  +-----------------------------------------------------------------------------+  |
|  | [Tier 4] ROUTER CACHE (In-Memory React Tree / Session State)                 |  |
|  | - Menyimpan RSC Payload di memory browser per navigation session            |  |
|  | - Invalidasi: Page Refresh, Server Action mutasi, Stale Time expiration     |  |
|  +-----------------------------------------------------------------------------+  |
+------------------------------------------^----------------------------------------+
                                           | RSC Payload / HTML
+------------------------------------------v----------------------------------------+
|                                  SERVER RUNTIME                                   |
|  +-----------------------------------------------------------------------------+  |
|  | [Tier 3] FULL ROUTE CACHE (Static Render Output: HTML & RSC Payload)       |  |
|  | - Lokasi: Disk / In-Memory Server / Edge CDN                                |  |
|  | - Kriteria: Evaluasi saat Build Time atau ISR Revalidation                  |  |
|  | - Status: HIT -> Skip Rendering Tree | MISS -> Execute React Tree           |  |
|  +---------------------------------------^-------------------------------------+  |
|                                          | Render Phase
|  +---------------------------------------v-------------------------------------+  |
|  | [Tier 1] REQUEST MEMOIZATION (React Render Lifecycle)                      |  |
|  | - Lokasi: Memory (Per-Request Scope via React `cache` / fetch dedupe)       |  |
|  | - Lifespan: Dimusnahkan segera setelah server selesai merender request tree |  |
|  +---------------------------------------^-------------------------------------+  |
|                                          | fetch() / Data Fetching
|  +---------------------------------------v-------------------------------------+  |
|  | [Tier 2] DATA CACHE (Cross-Request Persistent Data Store)                   |  |
|  | - Lokasi: File-system (Default) atau External (via Cache Handler SPI)      |  |
|  | - Granularitas: Per URL/Tag via `next.tags` & `revalidate` time              |  |
|  | - Karakteristik: Persisten across user sessions, deployments, & server restarts |
|  +-----------------------------------------------------------------------------+  |
+------------------------------------------^----------------------------------------+
                                           | Query / HTTP Request
                               +-----------v-----------+
                               | Upstream API / DB / DS|
                               +-----------------------+
```

#### Tier 1: Request Memoization (React Component Tree Deduplication)
*   **Mekanisme Internal:** Berjalan di level React runtime menggunakan primitive `React.cache()` atau ekstensi Native `fetch` yang di-patch oleh Next.js.
*   **Ruang Lingkup:** Single HTTP Request Lifecycle.
*   **Algoritma:** Ketika sebuah komponen merender dan memanggil `fetch('https://api.internal/sku/123')`, Next.js membuat SHA-1 hash dari URL dan options-nya. Jika fungsi dengan hash yang sama dipanggil di komponen anak lain dalam satu render pass, sistem mengembalikan *cached promise* tanpa memicu I/O baru.
*   **Destruksi:** Begitu respons HTTP selesai di-stream ke client, memori referensi ini dibersihkan oleh V8 Garbage Collector.

#### Tier 2: Data Cache (Cross-Request Persistent Cache)
*   **Mekanisme Internal:** Terletak di luar siklus hidup eksekusi React. Data Cache menyimpan data JSON mentah atau return value fungsi yang di-wrap oleh `unstable_cache`.
*   **Persistensi:** Berbeda dengan Tier 1, data ini bertahan melewati ribuan request dan restarts, disimpan secara default pada path `.next/cache/fetch-cache/`.
*   **Revalidation Pipeline:** Mendukung dua pola:
    1.  *Time-based (Stale-While-Revalidate):* Setelah batas waktu `revalidate` terlampaui, request pertama tetap menerima data lama (STALE), sementara proses asinkronus (background worker) mengambil data baru dan memperbarui cache (REVALIDATE).
    2.  *On-Demand:* Melalui penandaan `tags` string yang dipurifikasi secara atomik lewat `revalidateTag(tagName)`.

#### Tier 3: Full Route Cache (Static HTML & RSC Payload)
*   **Mekanisme Internal:** Mengkomputasi dan menyimpan seluruh representasi halaman (HTML terkompresi dan biner RSC Payload) pada saat build time atau revalidasi pasca-build.
*   **Dynamic Bailout Detection:** Jika sebuah rute memanggil Dynamic Functions (`cookies()`, `headers()`, `searchParams` pada Server Components), Next.js secara otomatis *men-deopt* rute tersebut dari Full Route Cache ke Dynamic Rendering (on-demand compute per-request).
*   **Interaksi dengan Data Cache:** Jika sebuah rute berstatus statis namun mengeksekusi fetch dari Data Cache yang di-invalidate, Full Route Cache rute tersebut otomatis ditandai invalid dan diregenerasi pada render berikutnya.

#### Tier 4: Router Cache (Client-side In-Memory Session Cache)
*   **Mekanisme Internal:** Tersimpan di memory browser client (heap memory tab browser aktif). Menggunakan struktur payload berbasis RSC per path segment.
*   **Tujuan:** Memberikan sensasi navigasi instan (SPA-like) saat user melakukan *back/forward* atau navigasi via `<Link>` tanpa membuat request berulang ke server.
*   **Durasi:** Default `staleTimes` (Next.js 14.2+ / 15): Dynamic route segment di-cache secara transient selama 0 detik (atau beberapa detik tergantung konfigurasi), Static route segment bertahan selama 5 menit, kecuali dipaksa purifikasi lewat `router.refresh()` atau mutasi Server Actions.

---

### 4. Why & What

#### Mengapa Model Ini Diciptakan? (The "Why")
Pada arsitektur rendering monolitik atau SSR klasik (Pages Router / React SSR awal), setiap *page render* memicu rantai pemanggilan database atau microservices yang identik (*N+1 over-fetching* di server). Solusi lama biasanya menempatkan Redis secara manual di level business logic, memicu boilerplate kode yang rentan *invalidation bug*, atau menempatkan Varnish/Cloudflare di depan aplikasi yang sering kali menyebabkan *cart-leak* atau *personal data exposure* akibat konfigurasi header caching yang terlalu agresif.

App Router 4-Tier Caching Pipeline memisahkan lapisan UI state, Server Render state, Persistent Data state, dan Network In-flight state ke dalam kontrak API deklaratif yang formal.

#### Apa yang Diatur dan Dampaknya? (The "What")
*   **Determinisme Komputasi:** Mengubah rendering yang awalnya *Compute-heavy per-request* menjadi *I/O read-heavy* yang efisien.
*   **Isolasi Konkurensi:** Menjamin data yang di-fetch 50 kali dalam satu pohon render hierarkis yang dalam (misal: layout, middleware context, nested panels, audit trail) hanya di-eksekusi **tepat satu kali** ke data source.
*   **Multi-tenant Boundary Safety:** Memastikan segment yang dipersonalisasi (mengandung data pengguna) dapat dipisahkan secara struktural dari layout statis tanpa membatalkan caching komponen layout induk.

---

### 5. How (Workflow Detail)

Berikut adalah alur eksekusi request masuk dari Client hingga ke Persistence Layer:

```
[Request Masuk: User klik <Link href="/products/p-100">]
                           |
                           v
              <Ada di Router Cache Browser?>
               /                            \
        (YES) /                              \ (NO)
             v                                v
      [Render RSC UI]            [Kirim HTTP Request ke Next.js Server]
      (Instan - 0ms I/O)                      |
                                              v
                                 <Ada di Full Route Cache?>
                                  /                      \
                           (YES) /                        \ (NO: Dynamic Bailout / Expired)
                                v                          v
                        [Return RSC+HTML]         [Mulai React Server Render]
                        (Hit - Sub-10ms)                   |
                                                           v
                                              <Evaluasi pemanggilan fetch()>
                                                           |
                                                           v
                                            <Ada di Request Memoization?>
                                             /                         \
                                      (YES) /                           \ (NO)
                                           v                             v
                                  [Ambil dari Memori]          <Ada di Data Cache?>
                                  (0ms Latency)                 /                 \
                                                         (YES) /                   \ (NO)
                                                              v                     v
                                                      [Return Cached Data]   [Hit Upstream API/DB]
                                                                                    |
                                                                                    v
                                                                           [Tulis ke Data Cache]
                                                                                    |
                                                                                    v
                                                                          [Memoize Request ini]
```

#### Alur On-Demand Revalidation:
1. Operator/Webhook memanggil endpoint API atau Server Action: `revalidateTag('product-p-100')`.
2. Next.js Data Cache Layer mencari seluruh entri cache yang memiliki tag metadata `product-p-100`.
3. Entri yang cocok di-marked sebagai **EXPIRED/STALE** secara atomik di persistent cache.
4. Next.js Full Route Cache yang membungkus segment terkait otomatis ditandai **INVALID**.
5. Klien berikutnya yang meminta rute tersebut akan memicu *Server Render Phase*, membaca upstream data baru, dan mengompilasi ulang Full Route Cache.

---

### 6. Analogy & Diagram ASCII

#### Analogi Pabrik Manufaktur Enterprise
Bayangkan sebuah perakitan mobil kustom:
1.  **Request Memoization** adalah *baki peralatan teknisi*. Jika teknisi membutuhkan kunci pas ukuran 10mm sebanyak 5 kali saat merakit satu sasis mobil yang sama, teknisi tidak bolak-balik ke gudang; kunci pas ditaruh di sakunya selama pengerjaan sasis tersebut, lalu dikembalikan setelah selesai.
2.  **Data Cache** adalah *gudang sentral bahan baku*. Komponen mesin standar (misal: blok silinder) disimpan di sini. Gudang ini melayani ribuan teknisi berbeda. Jika stok komponen model A diganti dengan model B (on-demand revalidate), seluruh teknisi akan mengambil model B sejak detik pembaruan.
3.  **Full Route Cache** adalah *showroom mobil yang sudah jadi*. Jika pembeli datang menginginkan mobil standar tipe X, mobil langsung diserahkan dari showroom tanpa proses perakitan sama sekali.
4.  **Router Cache** adalah *katalog visual di tangan pembeli*. Pembeli membolak-balik halaman yang sudah pernah dilihatnya tanpa perlu menanyakan ulang ke staf showroom setiap detik.

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Demonstrasi Tag-based Revalidation & Dynamic Separation
File: `app/inventory/[sku]/page.tsx`
```tsx
import { revalidateTag } from 'next/cache';

// Fetch Tier 2: Persistent Data Cache dengan Tag
async function getInventoryData(sku: string) {
  const res = await fetch(`https://api.enterprise.internal/inventory/${sku}`, {
    next: { 
      tags: [`inventory-${sku}`, 'inventory-global'],
      revalidate: 3600 // SWR Fallback: 1 Jam
    }
  });

  if (!res.ok) throw new Error('Failed to fetch inventory');
  return res.json();
}

export default async function InventoryPage({ params }: { params: { sku: string } }) {
  // Komponen ini ter-render di Full Route Cache kecuali mendeteksi dynamic API
  const data = await getInventoryData(params.sku);

  // Server Action untuk Mutasi dan Cache Purge
  async function triggerManualRestock() {
    'use server';
    // Purifikasi Data Cache & otomatis menandai Full Route Cache terkait stale
    revalidateTag(`inventory-${params.sku}`);
  }

  return (
    <main className="p-8">
      <h1 className="text-xl font-bold">SKU: {params.sku}</h1>
      <p>Stock Level: {data.stockCount}</p>
      <form action={triggerManualRestock}>
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 mt-4 rounded">
          Force Invalidate Cache
        </button>
      </form>
    </main>
  );
}
```

#### B. Practical Example: Production Distributed Redis Cache Handler
Di lingkungan multi-container (Kubernetes cluster dengan 20 replika pod Next.js), default file-system Data Cache tidak sinkron antar-pod. Kita harus mengimplementasikan **Custom Cache Handler** via SPI (*Service Provider Interface*) Next.js yang kompatibel dengan protokol Next.js 14/15.

File: `cache-handler.js` (Root directory aplikasi)
```javascript
const { createClient } = require('redis');

const client = createClient({
  url: process.env.REDIS_CLUSTER_URL || 'redis://localhost:6379'
});

client.on('error', (err) => console.error('[REDIS CACHE ERROR]', err));
const connectPromise = client.connect();

module.exports = class DistributedCacheHandler {
  constructor(options) {
    this.options = options;
  }

  async get(key) {
    await connectPromise;
    try {
      const data = await client.get(`nextjs:cache:${key}`);
      if (!data) return null;

      const parsed = JSON.parse(data);
      // Format return value wajib mematuhi standar CacheHandler Next.js
      return {
        lastModified: parsed.lastModified,
        value: parsed.value, // RSC payload atau JSON value
      };
    } catch (error) {
      console.error(`[CACHE_GET_FAIL] Key: ${key}`, error);
      return null; // Fallback gracefully ke origin jika cache down
    }
  }

  async set(key, data, ctx) {
    await connectPromise;
    try {
      const payload = JSON.stringify({
        lastModified: Date.now(),
        value: data,
      });

      // Hitung TTL: ctx.lifespan atau revalidate value
      const ttl = typeof ctx.revalidate === 'number' ? ctx.revalidate : 86400; // Default 1 hari

      const multi = client.multi();
      multi.setEx(`nextjs:cache:${key}`, ttl, payload);

      // Mapping Tags ke Keys untuk atomik tag invalidation
      if (ctx.tags && Array.isArray(ctx.tags)) {
        for (const tag of ctx.tags) {
          multi.sAdd(`nextjs:tag:${tag}`, key);
          // Expire tag mapping set setelah 7 hari
          multi.expire(`nextjs:tag:${tag}`, 604800);
        }
      }

      await multi.exec();
    } catch (error) {
      console.error(`[CACHE_SET_FAIL] Key: ${key}`, error);
    }
  }

  async revalidateTag(tag) {
    await connectPromise;
    try {
      // Ambil seluruh keys yang terasosiasi dengan tag ini
      const keys = await client.sMembers(`nextjs:tag:${tag}`);
      if (keys.length > 0) {
        const multi = client.multi();
        // Hapus seluruh keys dari cache
        for (const key of keys) {
          multi.del(`nextjs:cache:${key}`);
        }
        // Hapus mapping tag itu sendiri
        multi.del(`nextjs:tag:${tag}`);
        await multi.exec();
        console.log(`[CACHE_TAG_PURGED] Tag: ${tag} (${keys.length} keys invalidated)`);
      }
    } catch (error) {
      console.error(`[CACHE_REVALIDATE_TAG_FAIL] Tag: ${tag}`, error);
    }
  }
};
```

File: `next.config.js`
```javascript
const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Daftarkan cache handler kustom untuk override file-system storage
  cacheHandler: process.env.NODE_ENV === 'production' 
    ? path.resolve(__dirname, 'cache-handler.js') 
    : undefined,
  // Matikan kompresi bawaan jika ditangani oleh Ingress/Cloudflare
  compress: false,
  experimental: {
    // Memastikan stale-while-revalidate background task berjalan terisolasi
    serverComponentsExternalPackages: ['redis'],
  }
};

module.exports = nextConfig;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: E-Commerce Tier-1 Flash Sale Engine (150.000 RPS)
*   **Konteks Masalah:** Sebuah platform e-commerce enterprise mengalami *database collapse* saat Flash Sale. Halaman detail produk (PDP) memuat: (1) Deskripsi & Gambar Produk (Statis), (2) Stock Counter & Flash-price (Ultra-dinamis, update per detik), (3) Rekomendasi Personalisasi User (Dinamis per user ID).
*   **Kegagalan Desain Awal:** PDP menggunakan `export const dynamic = 'force-dynamic'`. Setiap request mengeksekusi SSR murni. 150.000 RPS menghantam PostgreSQL cluster secara serentak, mengakibatkan *connection pool exhaustion*, p99 latensi melonjak hingga 12 detik, dan Node.js pod mengalami OOM (*Out Of Memory*).

#### Transformasi Arsitektur Berbasis 4-Tier Pipeline:
1.  **Dekomposisi Rute via Static Shell & Dynamic Islands:**
    *   Struktur PDP diubah menjadi default Static (`Full Route Cache` aktif). HTML shell dan asset statis disajikan langsung dari Edge CDN/Full Route Cache dengan latensi **8ms**.
2.  **Optimasi Data Cache & Dynamic Subtrees (PPR Mindset):**
    *   Bagian deskripsi produk di-cache pada Tier 2 via `fetch(..., { next: { tags: ['catalog-p-999'], revalidate: 86400 } })`.
    *   Stock counter tidak lagi menggunakan SSR, melainkan menggunakan React Server Component yang di-wrap dalam `<Suspense>` dan disajikan menggunakan client streaming via polling interval terkontrol atau WebSocket fallback.
3.  **Pemberian Batas Router Cache Client:**
    *   Karena user sering melakukan navigasi bolak-balik antara Search dan PDP, Next.js Router Cache dikonfigurasi secara eksplisit agar tidak menampilkan harga diskon yang sudah basi:
    ```typescript
    // app/layout.tsx
    export const experimental_staleTimes = {
      dynamic: 0, // Segera re-fetch RSC payload untuk bagian dynamic saat navigasi
      static: 180 // Cache data static shell selama 3 menit di memori browser
    };
    ```
4.  **Mitigasi Cache Stampede via Mutex Lock di Cache Handler:**
    Ketika tag di-revalidate serentak di tengah 150.000 RPS, sistem menyematkan Redis Distributed Lock (*Redlock pattern*). Hanya **1 request** yang diizinkan memanggil Upstream Microservice untuk menyusun data baru; 149.999 request lainnya disajikan data STALE selama 200ms grace period.
5.  **Hasil Pengujian:**
    *   Throughput naik dari 1.200 RPS menjadi **165.000 RPS**.
    *   Database load turun sebesar **94%**.
    *   Latency p99 stabil pada **38ms**.

---

### 9. Trade-offs

Menggunakan 4-Tier Caching Pipeline membawa kompromi sistem yang signifikan:

| Parameter | Agresif Caching (Full Route + Data Cache) | Minimal / Force-Dynamic Rendering |
| :--- | :--- | :--- |
| **P99 Latency (TTFB)** | **Ultra Low (5 - 30ms)**. Mayoritas disajikan dari memory/disk tanpa evaluasi AST React. | **High (150 - 1200ms)**. React harus mem-parse dan merender RSC Payload pada setiap siklus. |
| **Data Consistency** | **Eventual Consistency**. Terdapat jeda propagasi mutasi sebelum tag di-invalidate di seluruh cluster. | **Strong Consistency**. Data yang ditampilkan dijamin merupakan kondisi mutakhir database. |
| **Resource Cost** | **Storage Heavy**. Membutuhkan alokasi memori RAM/Redis yang besar untuk menampung serialisasi RSC & tags. | **Compute Heavy**. CPU usage node berputar 80-100% secara konstan akibat JSON serialization & JSX transforms. |
| **Debugging Complexity** | **Sangat Kompleks**. Butuh pelacakan header cache (`x-nextjs-cache`, dynamic triggers) dan status tag. | **Rendah**. Alur eksekusi bersifat linear layaknya framework MVC backend standar. |
| **Cache Stampede Risk** | **Tinggi**. Saat cache kunci terpopuler kedaluwarsa secara serentak di traffic puncak. | **Nol**. Tidak ada persistent cache yang dieksekusi secara masal. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. "Accidental Dynamic Bailout" Melalui Akses Header/Cookie Tak Sengaja
*   **Gejala:** Halaman yang seharusnya Static (diharapkan Full Route Cache HIT) selalu berstatus `DYNAMIC` di build log (`λ` bukannya `○`), membebani server database setiap kali diakses.
*   **Akar Masalah:** Pemanggilan `headers()` atau `cookies()` pada root layout atau komponen tingkat tinggi. Akses ini menginstruksikan Next.js bahwa seluruh subtree di bawahnya membutuhkan konteks HTTP unik, mematikan Full Route Cache untuk seluruh halaman.
*   **Perbaikan:** Isolasi pemanggilan dynamic APIs ke dalam leaf components (komponen terdalam) atau gunakan dynamic route parameter via static generation:
```tsx
// SALAH: Membaca cookie di Layout utama mematikan cache seluruh halaman anak
export default async function RootLayout({ children }) {
  const token = cookies().get('session'); // BAD: Mengubah seluruh app menjadi DYNAMIC
  return <html><body>{children}</body></html>;
}

// BENAR: Gunakan pola Suspense Boundary dan baca cookie HANYA di komponen yang membutuhkan
export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <Suspense fallback={<NavSkeleton />}>
          <UserPersonalizedNav /> {/* Dynamic function cookies() diisolasi di sini */}
        </Suspense>
        {children} {/* Subtree ini tetap dapat menikmati Full Route Cache */}
      </body>
    </html>
  );
}
```

#### 2. Cache Poisoning Akibat Request Memoization dengan Parameter Objek Kompleks
*   **Gejala:** Data yang diambil antar user yang berbeda tertukar atau fungsi `cache()` tidak melakukan deduplikasi (selalu MISS).
*   **Akar Masalah:** React `cache()` menggunakan shallow equality comparison (`Object.is`) untuk argumen fungsinya.
```typescript
import { cache } from 'react';

// BAHAYA: Objek konfigurasi baru dibuat pada setiap pemanggilan
export const getFinancialReport = cache(async (filter: { year: number }) => {
  return db.query(filter);
});

// Di Komponen A:
await getFinancialReport({ year: 2024 }); // Object reference 0x001 -> CACHE MISS
// Di Komponen B:
await getFinancialReport({ year: 2024 }); // Object reference 0x002 -> CACHE MISS (Tidak ter-memoize!)
```
*   **Perbaikan:** Serialisasi argumen atau gunakan primitive types:
```typescript
export const getFinancialReport = cache(async (year: number) => {
  return db.query({ year });
});
await getFinancialReport(2024); // Primitive number -> Object.is(2024, 2024) === true (CACHE HIT)
```

#### 3. Diagnosis Header Cache State di Production
Next.js menyertakan status cache pada respons header internal. Buka terminal atau DevTools dan periksa:
*   `x-nextjs-cache: HIT` -> Data diambil langsung dari Tier 2 (Data Cache).
*   `x-nextjs-cache: STALE` -> Data disajikan dari Data Cache lama, proses background revalidation sedang berjalan.
*   `x-nextjs-cache: MISS` -> Data diambil langsung dari Upstream API.
*   `x-nextjs-cache: REVALIDATED` -> Cache baru saja diperbarui pada request yang sama.

---

### 11. Best Practices (Production Checklist)

1.  [ ] **Gunakan Descriptive Cache Tags:** Buat format tag berjenjang, contoh: `entity:id` (e.g., `products:9812`, `categories:electronics`, `tenant:acme`).
2.  [ ] **Jangan Gunakan `no-store` Tanpa Pertimbangan Matang:** `fetch(url, { cache: 'no-store' })` mematikan Data Cache sepenuhnya. Evaluasi apakah `revalidate: 0` atau on-demand tags lebih tepat untuk use case tersebut.
3.  [ ] **Implementasikan Mutex Lock pada Custom Cache Handler:** Hindari *Dog-piling / Cache Stampede* saat me-revalidasi keys bervolume tinggi di cluster distributed Redis.
4.  [ ] **Audit Dynamic Usage:** Jalankan `pnpm build` secara berkala dalam CI/CD pipeline dan verifikasi route manifest. Pastikan rute publik berstatus statis (`○` atau `●`).
5.  [ ] **Konfigurasi Memory Limit V8 Engine:** Pastikan pod deployment Node.js memiliki parameter `--max-old-space-size` yang proporsional untuk mencegah OOM jika Request Memoization memegang objek JSON berukuran besar pada traffic concurrent tinggi.
6.  [ ] **Enforce Timeout Upstream:** Selalu passing `AbortController.signal` ke dalam `fetch` persistent Data Cache untuk mencegah deadlock di pipeline rendering server.

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum mandiri berikut pada folder `hands-on/m02/`.

#### Langkah 1: Inisialisasi Environment
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
pnpm init
pnpm add next@14.2.15 react@18.3.1 react-dom@18.3.1 ioredis
pnpm add -D typescript @types/node @types/react @types/react-dom
npx tsc --init
```

#### Langkah 2: Buat Simulasi Distributed Redis Mock & Cache Spy
File: `hands-on/m02/cache-handler.js`
```javascript
const memoryStore = new Map();
const tagMap = new Map();

module.exports = class FileSystemCacheHandler {
  constructor(options) {
    this.options = options;
  }

  async get(key) {
    console.log(`\x1b[33m[CACHE_GET]\x1b[0m Key: ${key}`);
    const entry = memoryStore.get(key);
    if (!entry) return null;
    return entry;
  }

  async set(key, data, ctx) {
    console.log(`\x1b[32m[CACHE_SET]\x1b[0m Key: ${key} | Tags: ${ctx.tags?.join(',') || 'none'}`);
    memoryStore.set(key, {
      value: data,
      lastModified: Date.now()
    });

    if (ctx.tags) {
      for (const t of ctx.tags) {
        if (!tagMap.has(t)) tagMap.set(t, new Set());
        tagMap.get(t).add(key);
      }
    }
  }

  async revalidateTag(tag) {
    console.log(`\x1b[31m[CACHE_PURGE_TAG]\x1b[0m Tag: ${tag}`);
    const keys = tagMap.get(tag);
    if (keys) {
      for (const k of keys) {
        memoryStore.delete(k);
      }
      tagMap.delete(tag);
    }
  }
};
```

#### Langkah 3: Konfigurasi App Router
File: `hands-on/m02/next.config.js`
```javascript
const path = require('path');
module.exports = {
  cacheHandler: path.resolve(__dirname, 'cache-handler.js'),
};
```

#### Langkah 4: Bangun Halaman Verifikasi 4-Tier
File: `hands-on/m02/app/analytics/page.tsx`
```tsx
import { revalidateTag } from 'next/cache';

async function fetchMetric(id: string) {
  // Simulasi I/O Latency
  console.log(`\x1b[36m>>> EXECUTING UPSTREAM FETCH FOR: ${id} <<<\x1b[0m`);
  const timestamp = new Date().toISOString();
  return { id, timestamp, value: Math.random() };
}

export default async function AnalyticsPage() {
  // Panggilan 1 & 2 menguji Request Memoization dalam 1 server pass
  const metricA1 = await fetchMetric('cpu-load');
  const metricA2 = await fetchMetric('cpu-load');

  async function handleInvalidate() {
    'use server';
    revalidateTag('metrics');
  }

  return (
    <div style={{ fontFamily: 'monospace', padding: 24 }}>
      <h2>4-Tier Caching Verification Lab</h2>
      <p>A1 Render Time: {metricA1.timestamp} (Val: {metricA1.value})</p>
      <p>A2 Render Time: {metricA2.timestamp} (Val: {metricA2.value})</p>
      <p>Memoized Identical: {(metricA1.value === metricA2.value).toString()}</p>
      
      <form action={handleInvalidate}>
        <button style={{ padding: '8px 16px', background: '#e11d48', color: '#fff' }}>
          Purge Tag: metrics
        </button>
      </form>
    </div>
  );
}
```

#### Langkah 5: Eksekusi dan Amati Terminal
```bash
npx next build
npx next start -p 3005
```
Akses `http://localhost:3005/analytics` beberapa kali di browser. Perhatikan log di console terminal: Buktikan bahwa pesan `EXECUTING UPSTREAM FETCH` hanya muncul saat cache kosong atau pasca-purge, dan amati trigger `[CACHE_GET]`, `[CACHE_SET]`, serta `[CACHE_PURGE_TAG]`.

---

### 13. Exercise

#### Level: Easy
1. Ubah sebuah dynamic component yang menggunakan `fetch('https://api.github.com/zen')` agar otomatis memperbarui datanya di background setiap 60 detik menggunakan parameter konfigurasi SWR native Next.js.
2. Identifikasi header HTTP lokal apa yang harus Anda kirim via `curl` untuk melewati (bypass) browser Router Cache secara manual.

#### Level: Medium
1. Buat custom wrapper function bernama `withDedupedAuthContext(userId: string)` menggunakan `React.cache()` yang mengambil data otorisasi user dari database, dan panggil fungsi ini di 3 server components terpisah pada hirarki rute yang sama. Buktikan via timestamp log bahwa query database hanya dieksekusi tepat 1 kali.
2. Buat sebuah rute Next.js yang membedakan penanganan invalidasi cache antara data *publik* (misal: review produk) dan data *privat tenant* (misal: invoice transaksi) dengan skema penamaan tags yang aman.

#### Level: Hard
1. Implementasikan algoritma **Cache Stampede Prevention (Probabilistic Early Expiration / XFetch)** di dalam fungsi `get()` pada implementasi Custom Cache Handler `cache-handler.js` yang telah dibuat. Parameter input: `delta` (waktu komputasi render) dan `beta` (faktor agresivitas pembaruan).

---

### 14. Challenge

#### Skenario Arsitektur: Zero-Downtime Multi-Region Cache Synchronization
Anda adalah Chief Architect untuk platform perbankan global. Next.js App Router di-deploy secara aktif di 3 AWS Regions: `us-east-1` (N. Virginia), `eu-west-1` (Frankfurt), dan `ap-southeast-1` (Singapura). 

**Tantangan Teknis:**
1. Desain arsitektur Data Cache & Full Route Cache yang menggunakan cluster **Redis Global Datastore / DynamoDB Global Tables**.
2. Ketika regulator mewajibkan pembaruan suku bunga acuan secara mendadak (misal: event FED Rate Hike), sebuah mutasi Server Action dieksekusi di region `us-east-1`.
3. Buat rancangan spesifikasi sistem yang mendistribusikan sinyal pembersihan cache (`revalidateTag`) ke region Eropa dan Asia dalam waktu **kurang dari 250 milidetik**, tanpa menyebabkan lonjakan *thundering herd* pada upstream core-banking database di masing-masing region.
4. Sertakan dokumentasi strategi penanganan skenario *Network Partition (Split-brain)*: Apa yang harus dikembalikan oleh Next.js Data Cache Handler di region Singapura jika koneksi link trans-pasifik ke redis master terputus?

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Di manakah letak fisik penyimpanan Request Memoization pada Next.js?**
   * *Jawaban:* Di dalam Heap Memory proses Node.js runtime/V8 isolates, terikat strictly hanya pada masa hidup (lifecycle) satu HTTP request tree rendering.
2. **Kapan browser Router Cache dibersihkan secara otomatis tanpa intervensi developer?**
   * *Jawaban:* Saat halaman browser di-refresh total (hard reload), saat navigasi berpindah domain, atau ketika durasi waktu `staleTimes` (in-memory timer) telah habis.
3. **Apa perbedaan mendasar antara `revalidatePath` dan `revalidateTag`?**
   * *Jawaban:* `revalidatePath` menghapus cache untuk rute URL tertentu (dan secara rekursif dapat membersihkan rute anaknya), sedangkan `revalidateTag` mempurifikasi entri cache secara selektif lintas rute URL berbeda berdasarkan metadata identifier yang disematkan pada data fetcher.
4. **Apakah `fetch()` di Next.js secara default meng-cache data selamanya jika tidak ada opsi yang diberikan?**
   * *Jawaban:* Pada Next.js 14, default-nya adalah `force-cache` (cache selamanya). Pada Next.js 15, default-nya diubah menjadi `no-store` (setara dengan fetch standar browser) kecuali dikonfigurasi secara eksplisit.
5. **Bagaimana cara mencegah rute statis memicu Dynamic Bailout saat developer membaca query parameters di Server Component?**
   * *Jawaban:* Query parameters (`searchParams`) secara inheren bersifat dynamic. Untuk menjaga rute tetap statis, jangan baca `searchParams` di level Server Component saat SSR; delegasikan pembacaan query param ke Client Component menggunakan hook `useSearchParams()` yang dibungkus di dalam `<Suspense>`.

#### Intermediate Questions
1. **Mengapa React `cache()` tidak dapat digunakan untuk membagikan data antar request pengguna yang berbeda?**
   * *Jawaban:* Karena React `cache()` menggunakan container `AsyncLocalStorage` atau Fiber context yang scope-nya diisolasi per request context thread. Mencampurkan data antar request via global memory berisiko memicu kebocoran data sensitif (data leak) antar user.
2. **Jelaskan siklus Stale-While-Revalidate (SWR) pada Tier 2 (Data Cache) ketika sebuah request datang setelah TTL expired!**
   * *Jawaban:* Request yang datang pertama kali setelah TTL expired akan langsung menerima data yang sudah kedaluwarsa (STALE) tanpa menunggu I/O backend. Secara paralel di latar belakang, Next.js menjadwalkan background job untuk mengeksekusi fetch ke origin. Begitu data baru selesai diunduh, cache diperbarui (REVALIDATE). Request berikutnya baru akan menerima data yang segar tersebut.
3. **Bagaimana hubungan antara Tier 3 (Full Route Cache) dan Tier 2 (Data Cache) saat perintah `revalidateTag` dijalankan?**
   * *Jawaban:* Keduanya memiliki relasi ketergantungan. Ketika `revalidateTag` dijalankan, Next.js menandai data di Data Cache sebagai invalid, dan secara otomatis menandai segmen HTML/RSC Payload di Full Route Cache yang mengonsumsi data tersebut sebagai 'STALE'.
4. **Apa dampak performa dari menggunakan opsi `{ cache: 'no-store' }` di layout utama (`app/layout.tsx`)?**
   * *Jawaban:* Opsi tersebut akan membatalkan (deopt) Full Route Cache untuk seluruh halaman aplikasi yang berada di bawah hierarki layout tersebut. Server terpaksa mengompilasi ulang RSC Payload dan mengeksekusi ulang layout tree pada setiap interaksi navigasi.
5. **Mengapa implementasi Custom Cache Handler wajib mengembalikan field `lastModified` pada fungsi `get()`?**
   * *Jawaban:* Nilai `lastModified` (epoch millisecond timestamp) digunakan oleh internal engine Next.js untuk mengkalkulasi apakah data yang tersimpan sudah melampaui batas waktu revalidasi (TTL) atau apakah data tersebut lebih lama dibanding waktu invalidasi tag terakhir.

#### Skenario Kasus Produksi
1. **Skenario 1: The Leaked Shopping Cart**
   * *Kasus:* Sebuah toko ritel mendapati pembeli A dapat melihat isi keranjang belanja pembeli B sesaat setelah checkout massal. Halaman checkout dibangun menggunakan Server Components.
   * *Analisis Akar Masalah:* Tim pengembang membungkus query database `getCart(userId)` dengan `unstable_cache` tanpa menyertakan `userId` ke dalam argumen *key parts* cache, atau rute checkout secara tidak sengaja ter-cache di Tier 3 (Full Route Cache) karena data keranjang diambil menggunakan fetch standar tanpa penandaan dynamic context (misal: tidak membaca cookie auth secara eksplisit di level tree pembungkus).
   * *Solusi Remediasi:* Pastikan keranjang belanja di-fetch dengan `no-store` atau gunakan header token unik pada key parts `unstable_cache(..., ['cart', userId])`, dan pastikan layout checkout mengeksekusi dynamic check via `cookies()`.

2. **Skenario 2: The Ghost Product Image**
   * *Kasus:* CMS admin telah mengganti gambar banner produk utama, dan endpoint webhook `revalidateTag('hero-banner')` merespons status 200 OK. Namun, 40% pengguna di berbagai belahan dunia masih melihat gambar lama selama berjam-jam.
   * *Analisis Akar Masalah:* Next.js Data Cache di server berhasil di-purge, tetapi pengguna masih terperangkap di **Tier 4 (Router Cache)** pada browser mereka, atau terdapat CDN Edge Cache pihak ketiga (misal: Cloudflare/Akamai) di depan Next.js yang mengabaikan header `Cache-Control` dari upstream dan memaksakan cache TTL statis tersendiri.
   * *Solusi Remediasi:* (1) Pastikan Edge CDN membaca header s-maxage / bypass saat mendeteksi revalidasi, (2) Konfigurasikan `experimental_staleTimes` untuk memperpendek durasi Router Cache di browser, (3) Eksekusi `router.refresh()` pada level frontend pasca trigger update.

3. **Skenario 3: The Redis OOM Crash During Nightly Batch Invalidation**
   * *Kasus:* Setiap jam 00:00, script internal mengeksekusi revalidasi 50.000 tag secara bersamaan via custom Redis cache handler. Seketika itu juga Redis cluster mengalami memory spike dan crash OOM (*Out Of Memory*).
   * *Analisis Akar Masalah:* Implementasi `revalidateTag` menggunakan perintah Redis blocking `SMEMBERS` lalu melakukan fetch data masif ke memori Node.js, atau struktur mapping `nextjs:tag:{tag}` menampung ratusan ribu keys tanpa mekanisme TTL terisolasi, menyebabkan heap exhaustion saat dibaca secara konkuren.
   * *Solusi Remediasi:* Ubah arsitektur pembersihan tag menggunakan Redis Streams / Message Queue untuk memproses invalidasi secara bertahap (chunked/throttled). Ganti operasi `SMEMBERS` dengan `SSCAN` agar operasi pembacaan set tidak memblokir single thread event loop Redis, dan terapkan *tombstone marker* daripada *mass-delete* serentak.

---

### 16. Summary

*   Caching pada Next.js App Router adalah sebuah **pipeline multi-tier** (Tier 1: Request Memoization, Tier 2: Data Cache, Tier 3: Full Route Cache, Tier 4: Router Cache) yang saling berinteraksi secara deterministik.
*   **Request Memoization** mengoptimalkan performa dalam satu render pass (deduping), sedangkan **Data Cache** mengamankan performa lintas request dan deploy (persistency).
*   **Full Route Cache** memotong waktu komputasi rendering HTML/RSC Payload secara radikal, tetapi sangat rentan terhadap **Dynamic Bailout** yang tidak disengaja akibat pemanggilan API dinamis (`cookies()`, `headers()`).
*   Pada deployment enterprise multi-instance, penggunaan default file-system cache **harus digantikan** dengan arsitektur **Custom Cache Handler** berbasis distributed memory store (seperti Redis) untuk menjamin konsistensi data di seluruh cluster.
*   Strategi invalidasi modern berpusat pada **Tag-based Revalidation** terperinci, menuntut insinyur memahami trade-off antara *eventual consistency*, pemakaian memori, serta proteksi terhadap *cache stampede* di skala produksi masif.