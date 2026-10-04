# BAB 10: Performance, SSR, Nuxt 3, dan Production Hardening
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Membedah Arsitektur Internal Nitro Engine & Nuxt 3 SSR:** Memahami siklus hidup rendering dari fase resolusi rute HTTP di lapisan server hingga hidrasi DOM di klien secara granular.
2. **Mengimplementasikan Strategi Hybrid Rendering & Edge Delivery:** Mengonfigurasi dan mengoptimalkan *Incremental Static Regeneration* (ISR), *Stale-While-Revalidate* (SWR), SSR dinamis, dan *Client-Side Rendering* (CSR) berbasis rute menggunakan *Route Rules*.
3. **Mendeteksi dan Memitigasi Hydration Mismatches & SSR Memory Leaks:** Mengisolasi *request-scoped state* untuk mencegah kebocoran data antar-pengguna (*cross-request state pollution*) dan profiling heap V8 pada lingkungan Node.js runtime.
4. **Membangun Pertahanan Server-Side (Production Hardening):** Menerapkan arsitektur *Content Security Policy* (CSP) dinamis dengan cryptographic nonces, rate limiting terdistribusi via Redis, serta *Graceful Shutdown* pada containerized Node.js.
5. **Mengoptimalkan Payload Serialization:** Memangkas ukuran transfer `__NUXT__` payload hingga lebih dari 50% melalui seleksi data deterministik (`pick`/`transform`) dan *payload extraction*.

---

### 2. Prerequisite

Peserta didik wajib memiliki pemahaman mendalam pada domain berikut:
* **Vue 3 Composition API Internals:** Reactivity core (`ref`, `reactive`, `shallowRef`), lifecycle hooks, custom directives, dan SSR context APIs.
* **Dasar Arsitektur SSR:** Perbedaan eksekusi *isomorphic code* pada Node.js runtime (V8) vs Web Browser DOM environment.
* **HTTP Protocol & Network Security:** HTTP/2 & HTTP/3 multiplexing, *TLS termination*, header keamanan (HSTS, CSP, CORS, X-Frame-Options), dan mekanisme *caching* (Cache-Control, ETag).
* **Containerization & Node.js Diagnostics:** Konsep isolasi Docker, V8 memory allocation (`--max-old-space-size`), *garbage collection* (Scavenge vs Mark-Sweep), dan pembacaan Node.js *Heap Snapshots*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Nitro Engine: The Universal Server Engine
Nuxt 3 mentranslasikan aplikasi Vue menjadi artefak server-agnostik melalui **Nitro**. Nitro bukan sekadar wrapper Express atau Fastify; Nitro adalah bundler dan runtime server minimalis berbasis Rollup dan `h3` (HTTP framework berperforma tinggi).

```
[ Incoming Request: GET /catalog/sku-99 ]
                    │
                    ▼
       ┌─────────────────────────┐
       │   Nitro Server Engine   │
       │     (h3 Router/Hooks)   │
       └────────────┬────────────┘
                    │
        [ Route Rules Matching? ]
        ├─── SWR / ISR ───► [ Cache Storage Engine (Redis / FS / KV) ]
        │                   └─► Hit? ──► Return Cached HTML + Payload
        │                   └─► Miss? ─► Proceed to SSR Pipeline
        │
        └─── SSR / Dynamic
                    │
                    ▼
       ┌─────────────────────────┐
       │  Vue SSR Bundle Engine  │
       │   (vue/server-renderer) │
       └────────────┬────────────┘
                    │
                    ├─ 1. Create Request Context (EventContext)
                    ├─ 2. Instantiate NuxtApp & Pinia (Isolated Instance)
                    ├─ 3. Run Universal Middleware & Component setup()
                    ├─ 4. Suspense Resolution (Await useAsyncData / useFetch)
                    ├─ 5. renderToString() -> VNode Tree to HTML String
                    └─ 6. Serialize State (__NUXT__ JSON Payload)
                    │
                    ▼
       ┌─────────────────────────┐
       │  Nitro Response Engine  │
       │ (Append Headers, CSP,   │
       │  Compress Brotli/Gzip)  │
       └────────────┬────────────┘
                    │
                    ▼
[ Outgoing Response: HTML Stream/String with __NUXT__ Data ]
```

Nitro membagi tanggung jawab rendering menjadi dua fase:
1. **Server Initialization & Context Setup:** Setiap request memicu instantiasi konteks terisolasi (`EventContext`). Dependensi global dihindari untuk mencegah *cross-talk* data antar-klien.
2. **Payload Serialization (`devalue`):** Nitro menggunakan algoritma serialisasi `devalue` (bukan sekadar `JSON.stringify`) untuk mendukung tipe data kompleks seperti `Date`, `RegExp`, `Map`, `Set`, dan referensi siklis (*circular references*), lalu menempelkannya ke tag `<script id="__NUXT__" type="application/json">`.

#### 3.2. Lifecycle Hidrasi Klien dan Rekonsiliasi DOM
Pada klien, browser mem-parsing HTML yang dikirim server dan menampilkan UI secara visual (First Contentful Paint). Namun, UI tersebut bersifat statis (tidak interaktif) hingga fase **Client-Side Hydration** selesai:

```
[ Browser parses HTML ] ──► [ Paint Static DOM ] (FCP)
                                    │
    ┌───────────────────────────────┴───────────────────────────────┐
    ▼                                                               ▼
[ Download JS Chunks ]                                [ Parse inline __NUXT__ JSON ]
    │                                                               │
    └───────────────────────────────┬───────────────────────────────┘
                                    ▼
                     [ Initialize Vue 3 Runtime ]
                                    │
                 [ Hydration: DOM Reconciliation Step ]
                                    │
      ┌─────────────────────────────┴─────────────────────────────┐
      ▼                                                           ▼
[ Match VNode with Real DOM ]                       [ Hydration Mismatch Trigger? ]
      │                                                           │
      ├─ Match: Attach Event Listeners                            ├─ Text/Tag Discrepancy
      └─ Status: Interactive (TTI)                                ├─ Client re-renders VNode
                                                                  └─ Performance degradation!
```

Jika struktur VNode klien berbeda 1 node saja dari DOM SSR (misal: format tanggal berdasarkan zona waktu browser vs UTC server, atau perbedaan tag HTML karena modifikasi ekstensi browser), Vue 3 akan membatalkan rekonsiliasi node tersebut, membuang sub-tree DOM yang ada, dan merender ulang dari awal via klien (*bailout*). Hal ini menyebabkan *layout shift* (CLS) dan membuang waktu CPU klien.

#### 3.3. Mekanisme Kebocoran Memori (Memory Leaks) pada SSR
Di browser, memori dibersihkan total saat tab ditutup atau halaman di-refresh (*page teardown*). Di server (Node.js runtime), proses berjalan secara persisten selama berminggu-minggu melayani jutaan permintaan.

Penyebab kebocoran memori SSR yang fatal:
1. **Module-Level State (Singletons):** Mendeklarasikan objek reaktif di luar cakupan fungsi `setup()` atau factory function.
   ```typescript
   // ANTI-PATTERN: Singleton State di Server Engine
   // Seluruh request dari User A, B, dan C berbagi referensi array yang sama!
   import { reactive } from 'vue'
   export const globalSharedState = reactive<string[]>([]) // BAHAYA FATAL
   ```
2. **Uncleaned Event Listeners / Timers:** Menginisialisasi `setInterval` atau berlangganan event bus/Node.js `EventEmitter` di dalam *lifecycle* yang tereksekusi di server (`setup`, `beforeCreate`) tanpa destruksi (karena `onUnmounted` **tidak pernah dipanggil di server**).
3. **Closure Context Retention:** Menyimpan referensi objek request (`H3Event` atau context) ke dalam antrean panjang, map global, atau callback asinkron tak terputus.

---

### 4. Why & What

| Pendekatan | Mekanisme Rendering | Tempat Komputasi | Time to First Byte (TTFB) | Server Load & Cost | Kapan Digunakan |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Traditional SPA** | Klien membangun seluruh DOM via JS. | Browser Klien | Sangat Cepat (Static File) | Sangat Rendah (CDN/S3) | Dashboard internal, aplikasi SaaS B2B otentikasi penuh. |
| **Full SSR** | Render HTML setiap request masuk secara on-the-fly. | Node.js Server | Sedang (Tergantung latency query DB/API) | Tinggi (CPU-bound per request) | Halaman akun pengguna dinamis, real-time analytics. |
| **Static (SSG)** | Pre-render seluruh halaman saat `build time`. | CI/CD Machine | Sangat Cepat (Global CDN) | Nol (Hanya static storage) | Dokumentasi teknis, landing page statis tanpa update berkala. |
| **SWR / ISR** | Serve stale HTML dari cache, update background asinkron. | CDN Edge / Node.js Engine | Sangat Cepat (<50ms via cache hit) | Rendah (Komputasi hanya saat TTL kedaluwarsa) | E-commerce catalog, portal berita, direktori publik berskala masif. |

---

### 5. How: Workflow Detail Arsitektur Produksi

Proses pengiriman halaman dari edge ke browser menggunakan arsitektur enterprise:

```
[ Client Request ]
       │
       ▼
[ Cloudflare / CloudFront (Edge Layer) ]
       │
       ├── Cache Hit (Public SWR)? ──► Return Edge Cached HTML
       └── Cache Miss / Dynamic
               │
               ▼
[ Ingress Controller (Nginx / Envoy / Traefik) ] ── (Terminasi TLS, WAF, Rate Limit Layer 1)
               │
               ▼
[ Nuxt 3 Cluster (Node.js Nitro Engine via PM2 / K8s Pods) ]
       │
       ├─ Nitro Hook: `request` (Generate CSP Nonce, Inject Request ID)
       ├─ Route Matcher: Check Cache Rule (`swr: 300`)
       │       │
       │       ├─ Storage Cache Hit (Redis Storage Driver)? ──► Return Cached HTML
       │       └─ Storage Cache Miss:
       │               ├─ Run Server Plugins
       │               ├─ Instantiate App & Request-scoped Pinia
       │               ├─ Fetch Data (`useAsyncData` with Deduplication)
       │               ├─ SSR Render: Render VNode tree to String Stream
       │               ├─ Save Render Output to Redis Cache (Background)
       │               └─ Inject Security Headers (CSP Nonce, HSTS, XSS Protection)
       │
       ▼
[ Browser Runtime Execution ]
       ├─ Paint DOM from HTML Stream
       ├─ Read Deserialized `__NUXT__`
       ├─ Hydrate VNode tree without fetch calls (Zero Waterfall)
       └─ Mount App & Attach Event Handlers
```

---

### 6. Analogi & Diagram ASCII

#### Analogi: Arsitektur Restoran Siap Saji Berbintang
* **SPA (Client-Side Rendering):** Pelayan mengantarkan bahan makanan mentah, kompor portabel, dan buku resep ke meja pelanggan. Pelanggan harus memasak sendiri makanannya sebelum bisa makan. (Browser lambat, butuh spesifikasi HP tinggi).
* **SSR Murni:** Koki memasak setiap porsi hidangan dari nol saat pesanan masuk, memotong sayur, dan memanggang daging seketika. (Pelanggan menunggu lebih lama untuk gigitan pertama/TTFB, dapur bisa over-capacity jika tamu membeludak).
* **SWR/ISR (Hybrid):** Koki menyiapkan hidangan di lemari pemanas bersuhu stabil. Ketika tamu datang, pesanan langsung dihidangkan dalam hitungan detik. Di saat yang sama, asisten koki memeriksa: "Jika hidangan di lemari sudah berada di sana lebih dari 5 menit, buatkan batch baru untuk ditaruh di lemari menggantikan yang lama." Pelanggan selalu mendapat makanan cepat saji, dapur tidak pernah meledak.

#### Diagram: SSR Memory Leak vs Request Isolation
```
SKENARIO 1: MEMORY LEAK (Module-Level Singleton)
Request A ──► [ Module Scope: const userCache = [] ] ◄── Request B (Data Leak & Ram Bloat!)
                     ▲
                     │ (Array terus bertambah, referensi tertahan di memori V8,
                     │  Garbage Collector Mark-Sweep TIDAK BISA membersihkan)
                     ▼
              [ OOM Crash: V8 Heap Out Of Memory ]

--------------------------------------------------------------------------------------

SKENARIO 2: REQUEST-SCOPED ISOLATION (Safe Enterprise Pattern)
Request A ──► [ H3 EventContext ] ──► [ NuxtApp Instance A ] ──► [ Store A ] ──► Destroy on End
Request B ──► [ H3 EventContext ] ──► [ NuxtApp Instance B ] ──► [ Store B ] ──► Destroy on End
              (Tiap request memiliki lifecycle independen; GC membersihkan memori secara tuntas)
```

---

### 7. Implementasi Lanjutan & Arsitektur Produksi

#### 7.1. Konfigurasi Nuxt Enterprise (`nuxt.config.ts`)
Konfigurasi berikut mengaktifkan kompilasi teroptimasi, hybrid rendering, engine penyimpanan Redis untuk SWR, isolasi payload, dan hardening.

```typescript
// nuxt.config.ts
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  // Menjamin kepatuhan standar TypeScript strict
  typescript: {
    strict: true,
    typeCheck: true
  },

  // Eksperimental flags untuk performa maksimal
  experimental: {
    payloadExtraction: true,      // Ekstraksi payload ke file JSON terpisah untuk efisiensi HTTP/2 caching
    renderJsonPayloads: true,     // Optimasi payload serialisasi via JSON parsable script
    componentIslands: true,        // Mendukung server-only dynamic islands
    headNext: true                // Arsitektur modern unhead
  },

  // Hybrid Rendering & Caching Rules Engine
  routeRules: {
    // Static Pre-rendered pages (Build Time)
    '/about': { prerender: true },
    '/terms': { prerender: true },

    // SWR: Cache disimpan 1 jam (3600 detik), revalidasi di background
    '/products/**': { 
      swr: 3600,
      headers: {
        'Cache-Control': 'public, max-age=60, s-maxage=3600, stale-while-revalidate=86400'
      }
    },

    // Dynamic SSR murni untuk area privat/autentikasi
    '/dashboard/**': { ssr: true, headers: { 'Cache-Control': 'private, no-cache' } },

    // Fallback Client-Side Only (SPA) untuk area interaktif kompleks non-SEO
    '/workspace/**': { ssr: false }
  },

  // Konfigurasi Nitro Server Engine
  nitro: {
    compressPublicAssets: true,
    // Driver Cache Terdistribusi untuk SWR Multi-Instance
    storage: {
      cache: {
        driver: 'redis',
        host: process.env.REDIS_HOST || '127.0.0.1',
        port: Number(process.env.REDIS_PORT) || 6379,
        password: process.env.REDIS_PASSWORD || '',
        db: 0,
        ttl: 3600
      }
    },
    // Server-side timing header untuk audit performa network
    timing: true
  },

  // Proteksi dependencies dari SSR bundling issue
  build: {
    transpile: ['tslib']
  }
})
```

#### 7.2. Production-Hardened Security Plugin (Dynamic CSP with Cryptographic Nonce)
Penggunaan CSP statis sering kali mematikan hidrasi SSR karena script inline bawaan Nuxt diblokir oleh browser. Pola industri enterprise menggunakan **Cryptographic Nonce per-request**.

```typescript
// server/plugins/security-headers.ts
import { defineNitroPlugin } from 'nitropack/runtime'
import crypto from 'node:crypto'

export default defineNitroPlugin((nitroApp) => {
  nitroApp.hooks.hook('render:html', (htmlContext, { event }) => {
    // 1. Generate Nonce Unik kriptografis berbasis Cryptographically Secure PRNG (CSPRNG)
    const nonce = crypto.randomBytes(16).toString('base64')

    // 2. Simpan nonce di context event untuk injeksi internal
    event.context.nonce = nonce

    // 3. Modifikasi script tags pada struktur HTML Nuxt untuk menginjeksi atribut nonce
    htmlContext.head = htmlContext.head.map((tag: string) => {
      if (tag.startsWith('<script')) {
        return tag.replace('<script', `<script nonce="${nonce}"`)
      }
      return tag
    })

    htmlContext.bodyScripts = htmlContext.bodyScripts.map((tag: string) => {
      if (tag.startsWith('<script')) {
        return tag.replace('<script', `<script nonce="${nonce}"`)
      }
      return tag
    })

    // 4. Susun Content Security Policy yang Sangat Ketat (Strict CSP Level 3)
    const cspDirectives = [
      `default-src 'self'`,
      `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https: 'unsafe-inline'`, // fallback untuk browser lama
      `style-src 'self' 'unsafe-inline' fonts.googleapis.com`,
      `font-src 'self' fonts.gstatic.com`,
      `img-src 'self' data: https://cdn.enterprise-domain.com`,
      `connect-src 'self' https://api.enterprise-domain.com`,
      `frame-ancestors 'none'`,
      `base-uri 'self'`,
      `object-src 'none'`,
      `form-action 'self'`
    ]

    // 5. Injeksi HTTP Header ke Response
    setHeader(event, 'Content-Security-Policy', cspDirectives.join('; '))
    setHeader(event, 'X-Frame-Options', 'DENY')
    setHeader(event, 'X-Content-Type-Options', 'nosniff')
    setHeader(event, 'Referrer-Policy', 'strict-origin-when-cross-origin')
    setHeader(event, 'Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
  })
})
```

#### 7.3. Request-Isolated Enterprise Pinia Store
Menjamin isolasi total antar-request pada sisi server. Hindari menyimpan objek request atau socket pada state global.

```typescript
// stores/catalog.ts
import { defineStore } from 'pinia'

export interface Product {
  id: string
  sku: string
  title: string
  price: number
  inventory: number
}

interface CatalogState {
  products: Record<string, Product>
  currentProductId: string | null
  lastFetched: number | null
}

export const useCatalogStore = defineStore('catalog', {
  state: (): CatalogState => ({
    products: {},
    currentProductId: null,
    lastFetched: null
  }),

  getters: {
    activeProduct: (state): Product | null => {
      if (!state.currentProductId) return null
      return state.products[state.currentProductId] ?? null
    }
  },

  actions: {
    setProduct(product: Product) {
      // Menggunakan Record untuk direct index access O(1)
      this.products[product.id] = product
      this.currentProductId = product.id
      this.lastFetched = Date.now()
    },

    // Hindari async functions di actions yang menyimpan lifecycle timers atau subscriptions
    clearActiveProduct() {
      this.currentProductId = null
    }
  }
})
```

#### 7.4. Data Fetching Anti-Watermarking & Payload Minimization
Komponen Vue yang menerapkan pola penanganan hidrasi deterministik, eliminasi *over-fetching*, dan penanganan state sinkron.

```vue
<!-- components/ProductDetail.vue -->
<script setup lang="ts">
import { useCatalogStore, type Product } from '~/stores/catalog'

interface Props {
  productId: string
}

const props = defineProps<Props>()
const catalogStore = useCatalogStore()
const config = useRuntimeConfig()

// Menghindari Hydration Mismatch via Deterministic Fetching Key
// Pastikan useAsyncData memiliki unique key yang mengisolasi parameter
const { data: product, pending, error } = await useAsyncData<Product>(
  `product-detail-${props.productId}`,
  () => $fetch<Product>(`/api/v1/products/${props.productId}`, {
    baseURL: config.public.apiBaseUrl,
    headers: {
      'Accept': 'application/json'
    }
  }),
  {
    // ENTERPRISE OPTIMIZATION:
    // Hanya ambil field yang benar-benar dipakai di template!
    // Memangkas payload __NUXT__ hingga 70% dari field database backend yang bloated.
    pick: ['id', 'sku', 'title', 'price'],
    // Pastikan lazy: false jika critical untuk First Paint SEO
    lazy: false,
    // Transformasi data deterministik jika diperlukan
    transform: (raw) => ({
      ...raw,
      title: raw.title.trim()
    })
  }
)

// Sinkronisasi ke Pinia Store secara aman (hanya jika data tersedia)
if (product.value) {
  catalogStore.setProduct(product.value)
}
</script>

<template>
  <div class="product-container">
    <div v-if="pending" class="skeleton-loader" aria-busy="true">
      Loading critical product metrics...
    </div>

    <div v-else-if="error" class="error-boundary" role="alert">
      <h1>Failed to load product</h1>
      <p>{{ error.message }}</p>
    </div>

    <section v-else-if="product" class="product-view">
      <h1 class="text-2xl font-bold">{{ product.title }}</h1>
      <p class="sku-label">SKU: {{ product.sku }}</p>
      <p class="price-tag">
        <!-- 
          PERINGATAN HYDRATION MISMATCH:
          Format currency harus mengunci locale secara eksplisit!
          Jangan gunakan toLocaleString() default browser tanpa argumen bahasa.
        -->
        {{ new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(product.price) }}
      </p>
    </section>
  </div>
</template>
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Mega-Platform E-Commerce B2C Global
* **Traffic:** 50 Juta Pageviews/Bulan, Spike hingga 35.000 RPS saat Flash Sale Global.
* **Problem Statement:** 
  1. Arsitektur SPA lama mengalami penalti Core Web Vitals (LCP > 4.8 detik pada jaringan 4G berkembang).
  2. Pendekatan awal migrasi ke Full SSR menyebabkan CPU bottleneck di cluster Kubernetes Node.js, memicu error `503 Service Unavailable` saat lonjakan traffic.
  3. Memory leak tak terdeteksi me-restart pod setiap 2 jam akibat OOM (*Out-Of-Memory*).

#### Solusi Arsitektur
1. **Penerapan Tiered Hybrid Edge SWR:**
   * Halaman katalog produk di-cache pada layer Edge Cloudflare Workers dengan TTL 60 detik (`stale-while-revalidate=86400`).
   * Nitro menggunakan storage Redis Cluster multi-zone sebagai origin cache.
   * Node.js pods hanya merender HTML ketika terjadi cache invalidation dari webhook PIM/Warehouse API.
2. **Eliminasi Memory Leak via Profiling:**
   * Melakukan heap dump analysis menggunakan Node.js `--inspect` dan Google Chrome DevTools.
   * Ditemukan kebocoran memori fatal: Middleware autentikasi menambahkan listener pada event emitter server global tanpa pembersihan: `process.on('unhandledRejection')` didaftarkan berulang kali di setiap request.
   * Memindahkan registrasi hooks tersebut ke lifecycle bootstrapping Nitro Server (`server/plugins`), bukan di request lifecycle middleware.
3. **Payload Optimization:**
   * Mengaktifkan `experimental.payloadExtraction` dan pemangkasan DTO backend menggunakan properti `pick` pada seluruh composable `useAsyncData`.

#### Hasil Metrik (Before vs After)

| Metrik Kinerja | Sebelum (SPA + Inefficient SSR) | Sesudah (Hardened Hybrid Nuxt 3) |
| :--- | :--- | :--- |
| **Largest Contentful Paint (LCP)** | 4.8 detik | 1.1 detik (P95) |
| **Time To First Byte (TTFB)** | 1.2 detik (Dynamic SSR) | 38 ms (Global Edge SWR Hit) |
| **Node.js Pod CPU Utilization** | Rata-rata 85% - 90% (Throttling) | Rata-rata 12% - 18% |
| **Crash Restart Pods (OOM)** | ~14 kali per hari | 0 kali per bulan |
| **Infrastruktur AWS EKS Cost** | $14,200 / Bulan | $4,800 / Bulan (Turun 66.2%) |

---

### 9. Trade-offs: Analisis Komparatif Arsitektur Produksi

```
[ SSR Murni ]   <--- (Kompleksitas Operasional Tinggi, Server Cost Tinggi, TTFB Sedang)
      ▲
      │        [ SWR / ISR ] <--- SWEET SPOT ENTERPRISE
      │                              (Data Konsisten, Biaya Rendah, TTFB Sangat Cepat)
      ▼
[ Edge Static ] <--- (Biaya Nol, Kecepatan Maksimum, Data Kurang Real-time)
```

| Dimensi Arsitektur | Client-Side Rendering (SPA) | Pure SSR (Per-Request) | Hybrid SWR / ISR (Edge Driven) |
| :--- | :--- | :--- | :--- |
| **Raw Compute Latency (TTFB)** | Instan (Static asset delivery) | 150ms - 800ms (Query dependent) | < 50ms (Edge Cache Hit) |
| **Data Freshness / Consistency** | Read-after-write mutlak | Read-after-write mutlak | Eventual Consistency (Stale window) |
| **Server Resource Overhead** | Nol (Offloaded ke klien) | Sangat Tinggi (CPU V8 rendering) | Minimal (Hanya saat stale revalidate) |
| **SEO Indexability (Crawler)** | Buruk (Bergantung JS rendering bot)| Sempurna (Full static HTML parsed) | Sempurna (Full static HTML parsed) |
| **Biaya Infrastruktur Edge/Cloud** | Terendah | Tertinggi (Horizontal Pod Autoscaling) | Sedang - Rendah (Redis + CDN caching) |
| **Hydration Failure Penalty** | Tidak Ada | Tinggi (Bailout re-render DOM) | Tinggi (Bailout re-render DOM) |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Mengakses Objek Window/Document pada Root Setup Component
* **Kesalahan:**
  ```typescript
  // setup() context berjalan di server DAN di client
  const screenWidth = window.innerWidth // CRASH PADA NODE.JS: ReferenceError: window is not defined
  ```
* **Solusi & Mitigasi:**
  Gunakan pengecekan platform secara ketat atau manfaatkan lifecycle hook yang dijamin hanya berjalan di browser:
  ```typescript
  // Solusi A: Lifecycle hook client-only
  onMounted(() => {
    const screenWidth = window.innerWidth // Aman
  })

  // Solusi B: Nuxt Environment Flag
  if (import.meta.client) {
    const screenWidth = window.innerWidth // Aman dari Node.js execution
  }
  ```

#### 10.2. Hydration Mismatch Akibat Data Non-Deterministik
* **Gejala:** Muncul error di console browser: `[Vue warn]: Hydration text content mismatch in <p>: server rendered "12:00:00 AM" but client rendered "07:00:00"`.
* **Penyebab:** Eksekusi kode yang menghasilkan nilai berbeda antara server V8 (sering kali berzona UTC) dan browser lokal pengguna (misal: WIB/GMT+7), atau penggunaan `Math.random()`.
* **Solusi:**
  1. Bungkus node dengan tag `<ClientOnly>` jika data tersebut benar-benar bergantung pada konfigurasi mesin lokal.
  2. Standarisasi format parsing waktu pada server dan klien dengan timezone eksplisit:
     ```typescript
     // Gunakan konfigurasi timezone deterministik
     const formattedDate = new Intl.DateTimeFormat('id-ID', {
       timeZone: 'Asia/Jakarta',
       dateStyle: 'medium',
       timeStyle: 'short'
     }).format(timestamp)
     ```

#### 10.3. Profiling SSR Memory Leak Menggunakan Clinic.js
Jika container pod mengalami peningkatan memori terus-menerus (*linear upward slope*), jalankan profiling diagnostik:
1. Build aplikasi: `pnpm build`
2. Jalankan server Nitro via Clinic.js Doctor:
   ```bash
   npx clinic doctor --on-port 'autocannon -c 100 -d 30 http://localhost:3000' -- node .output/server/index.mjs
   ```
3. Jika Clinic Doctor mengindikasikan masalah pada Event Loop atau Memory, generate Heap Profiler:
   ```bash
   npx clinic heapprofiler --on-port 'autocannon -c 50 -d 30 http://localhost:3000' -- node .output/server/index.mjs
   ```
4. Buka laporan HTML yang dihasilkan; amati *flamegraph* untuk melihat fungsi mana yang menahan alokasi memori objek tanpa di-sweep oleh V8 GC.

---

### 11. Best Practices (Production Checklist)

#### Phase 1: Security & Hardening
- [ ] Strict Content Security Policy (CSP) dengan implementasi nonces diterapkan via Nitro plugin hook.
- [ ] Header `X-Powered-By: Nuxt` dan `X-Powered-By: Nitro` dihapus total di reverse proxy atau via `nitro.appConfig`.
- [ ] Route rules rate-limiting aktif untuk endpoint otentikasi dan API internal.
- [ ] Docker container dijalankan menggunakan user `non-root` (`USER node`).

#### Phase 2: SSR Data Optimization
- [ ] Seluruh pemanggilan `useFetch` atau `useAsyncData` menggunakan `pick` atau `transform` untuk mencegah kebocoran database schema ke payload `__NUXT__`.
- [ ] Tidak ada data non-serializable (fungsi, class instances kompleks) yang di-return dari SSR composables.
- [ ] Identifikasi unique key pada `useAsyncData` bersifat konsisten dan deterministik.

#### Phase 3: Performance & Scalability
- [ ] Route rules telah mengisolasi jalur statis, SWR, dan dynamic SSR dengan benar.
- [ ] Storage Redis terkonfigurasi dengan eviction policy `volatile-lru` atau `allkeys-lru` untuk menghindari memory exhaustion pada Redis.
- [ ] Ekstraksi payload (`experimental.payloadExtraction: true`) aktif untuk halaman berkarakteristik konten statis/SWR.
- [ ] Compression Brotli dan Gzip diaktifkan pada build level Nitro atau Cloud Reverse Proxy.
- [ ] Endpoint `/healthz` terkonfigurasi via Nitro Server Route untuk Kubernetes Liveness dan Readiness Probes.

---

### 12. Hands-on Practice: Membangun Enterprise SSR Hardened Service

Buat direktori baru pada proyek Anda: `hands-on/m02/` dan ikuti langkah berikut:

#### Langkah 1: Inisialisasi Proyek Nuxt 3 Minimal
Jalankan di terminal:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
pnpm init
pnpm add nuxt vue vue-router pinia @pinia/nuxt
pnpm add -D typescript @types/node
```

#### Langkah 2: Buat Skema Konfigurasi `nuxt.config.ts`
Implementasikan konfigurasi berikut:
```typescript
// hands-on/m02/nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@pinia/nuxt'],
  typescript: {
    strict: true
  },
  experimental: {
    payloadExtraction: false, // Set false untuk hands-on lokal agar mempermudah inspeksi HTML
    renderJsonPayloads: true
  },
  routeRules: {
    '/': { swr: 30 }, // SWR 30 detik
    '/realtime': { ssr: true }
  },
  nitro: {
    timing: true
  }
})
```

#### Langkah 3: Buat Endpoint Healthcheck & Simulasi Data API
Buat file `server/api/status.get.ts`:
```typescript
// hands-on/m02/server/api/status.get.ts
export default defineEventHandler((event) => {
  return {
    status: 'healthy',
    timestamp: Date.now(),
    pid: process.pid,
    memoryUsage: process.memoryUsage()
  }
})
```

Buat file mock database `server/api/system-metrics.get.ts`:
```typescript
// hands-on/m02/server/api/system-metrics.get.ts
export default defineEventHandler(async () => {
  // Simulasi latency database 150ms
  await new Promise((resolve) => setTimeout(resolve, 150))
  
  return {
    serverTime: new Date().toISOString(),
    activeNodes: 12,
    internalSecretKey: 'SECRET_DB_PASSWORD_SHOULD_NEVER_LEAK_TO_CLIENT',
    networkLoadGbps: 4.872
  }
})
```

#### Langkah 4: Buat Halaman Produksi dengan Pengamanan Data Payload
Buat file `app.vue`:
```vue
<!-- hands-on/m02/app.vue -->
<script setup lang="ts">
interface SystemMetrics {
  serverTime: string
  activeNodes: number
  networkLoadGbps: number
}

// Implementasi sanitasi data menggunakan "pick"
const { data: metrics, pending, refresh } = await useAsyncData<SystemMetrics>(
  'enterprise-system-metrics',
  () => $fetch('/api/system-metrics'),
  {
    // Hanya izinkan field ini masuk ke serialisasi __NUXT__
    // 'internalSecretKey' akan otomatis terbuang di sisi server!
    pick: ['serverTime', 'activeNodes', 'networkLoadGbps']
  }
)
</script>

<template>
  <main style="font-family: sans-serif; padding: 2rem;">
    <h1>Enterprise Cloud Infrastructure Monitor</h1>
    
    <div v-if="pending">Loading infrastructure metrics...</div>
    <div v-else-if="metrics" style="border: 1px solid #ccc; padding: 1.5rem; border-radius: 8px;">
      <p><strong>Cluster Active Nodes:</strong> {{ metrics.activeNodes }}</p>
      <p><strong>Throughput:</strong> {{ metrics.networkLoadGbps }} Gbps</p>
      
      <!-- Safe Rendering: Menghindari Hydration Mismatch dengan ClientOnly jika bergantung waktu dinamis -->
      <ClientOnly>
        <template #fallback>
          <p>Synchronizing local timestamp...</p>
        </template>
        <p><strong>Client Synchronized at:</strong> {{ new Date(metrics.serverTime).toLocaleString() }}</p>
      </ClientOnly>

      <button @click="() => refresh()" style="padding: 0.5rem 1rem; cursor: pointer;">
        Force Revalidate
      </button>
    </div>

    <footer style="margin-top: 2rem;">
      <p><em>Inspect Page Source (Ctrl+U) to verify that 'internalSecretKey' is NOT exposed in the payload!</em></p>
    </footer>
  </main>
</template>
```

#### Langkah 5: Pengujian dan Verifikasi
1. Jalankan aplikasi: `pnpm nuxi dev`
2. Buka browser pada `http://localhost:3000`
3. Tekan `Ctrl + U` (View Page Source).
4. Lakukan pencarian string: `SECRET_DB_PASSWORD_SHOULD_NEVER_LEAK_TO_CLIENT`.
5. **Verifikasi:** String tersebut **tidak boleh ditemukan sama sekali** di dalam source HTML maupun tag payload JSON `__NUXT__`. Hal ini membuktikan bahwa strategi data pruning berjalan sempurna di level SSR server engine.

---

### 13. Exercise

#### Level: Easy
* **Tugas:** Buat Route Rule di `nuxt.config.ts` untuk path `/archive/**` yang menerapkan pre-rendering total saat build-time, dan path `/api/proxy/**` yang menonaktifkan SSR serta mengabaikan CORS cache.
* **Kriteria Sukses:** Halaman `/archive` menghasilkan file `.html` statis di direktori `.output/public`, dan response header untuk `/api/proxy` tidak memicu kalkulasi SSR.

#### Level: Medium
* **Tugas:** Identifikasi dan perbaiki *Hydration Mismatch* pada komponen berikut tanpa membungkus seluruh komponen menggunakan `<ClientOnly>`:
  ```vue
  <template>
    <div class="user-greeting">
      <span>Welcome back! Logged in at: {{ renderTime }}</span>
      <span v-if="isMobile">Mobile Viewport Active</span>
    </div>
  </template>
  <script setup>
  const renderTime = new Date().toLocaleTimeString()
  const isMobile = window.innerWidth < 768
  </script>
  ```
* **Kriteria Sukses:** Tidak ada warning hydration di DevTools console browser, dan layout tetap stabil pada render awal.

#### Level: Hard
* **Tugas:** Buat sebuah Nitro Server Plugin (`server/plugins/rate-limiter.ts`) yang mengintersepsi event request Nitro:
  1. Hitung jumlah request berdasarkan alamat IP (`event.node.req.socket.remoteAddress`).
  2. Implementasikan algoritma sliding window (gunakan JavaScript memory `Map` dengan TTL auto-cleanup).
  3. Jika request melebihi 10 RPS per IP, kembalikan HTTP status code `429 Too Many Requests` dalam format JSON tanpa masuk ke pipeline render Vue SSR.
* **Kriteria Sukses:** Stress test lokal menggunakan tools seperti `autocannon` atau `wrk` memunculkan response 429 ketika limit dilampaui, tanpa menyebabkan crash pada thread event loop.

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Sebuah platform perbankan digital berskala enterprise ingin membangun arsitektur halaman ringkasan portofolio pengguna dengan kriteria:
1. Shell HTML dasar harus di-deliver dalam < 100ms menggunakan Edge-cached layout.
2. Komponen saldo tabungan bersifat **strictly sensitive** (tidak boleh masuk ke cache publik mana pun, tidak boleh di-serialize ke payload statis yang dapat dilihat pihak ketiga).
3. Terjadi dependensi eksternal: API pihak ketiga untuk kurs valuta asing sangat lambat (latency P99 ~ 2.5 detik) dan sering mengalami timeout.
4. Tim infosec menuntut tidak boleh ada inline-script tanpa SHA-256 integrity hash atau nonce kriptografis.

**Tantangan Arsitektur:**
Rancang dan bangun arsitektur sistem menggunakan fitur-fitur mutakhir Nuxt 3 (Nuxt Server Islands, Custom Headers, Nitro Error Boundaries, dan Async Suspense Streaming). Sistem harus:
* Tetap merender seluruh shell layout dan data user lokal seketika tanpa terblokir oleh API valuta asing yang lambat (Gunakan Streaming SSR atau Component Islands).
* Menangani kegagalan timeout API valas secara gracefully dengan mekanisme fallback UI isolatif tanpa mematikan proses SSR halaman utama.
* Memastikan seluruh audit performa Google Lighthouse mendapatkan skor Core Web Vitals > 95 dan skor Keamanan Moz/Mozilla Observatory mendapatkan grade "A+".

*(Selesaikan tantangan ini dengan menyusun struktur arsitektur file, konfigurasi modul, dan diagram aliran kontrol intersep tanpa bantuan template instan).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa `onMounted()` tidak pernah dipanggil di sisi server selama proses SSR?**
   * *Jawaban:* `onMounted` secara arsitektural merepresentasikan fase di mana representasi Virtual DOM telah dikonversi dan dimasukkan (mounted) ke dalam Real DOM browser. Karena server Node.js tidak memiliki DOM tree nyata (hanya merender string HTML teks mentah), lifecycle ini sengaja diabaikan di server untuk mencegah inisialisasi operasi browser-specific.

2. **Apa peran utama engine `Nitro` dalam ekosistem Nuxt 3?**
   * *Jawaban:* Nitro berperan sebagai runtime server dan compilation engine universal yang membungkus aplikasi Nuxt agar dapat dijalankan secara konsisten di berbagai platform runtime (Node.js, Deno, Bun, Cloudflare Workers, AWS Lambda) dengan dependensi server minimal via framework `h3`.

3. **Mengapa kita tidak boleh menggunakan state global di luar cakupan fungsi (misal: variabel file-level `let count = 0`) pada kode SSR?**
   * *Jawaban:* Variabel di tingkat modul bersifat *singleton* di lingkungan proses Node.js. Variabel tersebut akan digunakan bersama secara persisten oleh seluruh pengguna yang mengakses server, menyebabkan kebocoran data sensitif (*cross-request state pollution*) antar pengguna yang berbeda.

4. **Apa implikasi dari properti `lazy: true` pada composable `useFetch`?**
   * *Jawaban:* `lazy: true` menginstruksikan Nuxt untuk tidak memblokir transisi navigasi klien atau perenderan server saat data sedang di-fetch. Server/klien akan segera merender komponen dengan status `pending: true` alih-alih menunggunya hingga selesai (*non-blocking resolution*).

5. **Apa fungsi dari `experimental.payloadExtraction` di `nuxt.config.ts`?**
   * *Jawaban:* Fitur ini memisahkan data SSR (payload `__NUXT__`) dari file HTML mentah menjadi file JSON fisik terpisah. Hal ini memungkinkan browser dan CDN meng-cache data JSON tersebut secara independen menggunakan header HTTP caching modern, mengurangi transfer bandwidth secara drastis saat navigasi berikutnya.

#### Bagian 2: Intermediate (5 Pertanyaan)
6. **Jelaskan perbedaan mekanis mendasar antara `swr: true` dan `ssr: false` pada konfigurasi `routeRules`!**
   * *Jawaban:* `swr: true` (Stale-While-Revalidate) merender halaman di server sekali, menyimpannya di cache layer (memori/Redis), dan mengembalikan HTML yang sudah dirender tersebut ke request berikutnya sambil memperbarui cache di background secara asinkron. Sedangkan `ssr: false` sepenuhnya menonaktifkan rendering server dan hanya mengembalikan file HTML kosong ke browser, memaksa browser mengompilasi DOM via Client-Side Rendering (SPA mode).

7. **Bagaimana algoritma devalue mencegah kerentanan keamanan XSS dibandingkan `JSON.stringify` biasa pada payload injection?**
   * *Jawaban:* `devalue` secara otomatis melakukan sanitasi karakter berbahaya seperti `<`, `>`, dan `/` yang dapat digunakan penyerang untuk menyuntikkan tag script penutup `</script><script>alert(1)</script>` di tengah payload data JSON yang tertanam pada dokumen HTML.

8. **Apa yang dimaksud dengan "Hydration Bailout" dan bagaimana dampaknya terhadap performa halaman?**
   * *Jawaban:* Hydration bailout adalah kondisi di mana runtime Vue klien mendeteksi ketidakcocokan parah antara server-generated HTML dan client VNode. Vue menghentikan proses patching inkremental, membuang struktur DOM server yang ada, dan merender ulang sub-tree tersebut dari awal via JavaScript klien. Hal ini meningkatkan Total Blocking Time (TBT), memicu Cumulative Layout Shift (CLS), dan membebani CPU klien.

9. **Mengapa penulisan `new Date().toLocaleString()` secara langsung di template dapat memicu hydration mismatch?**
   * *Jawaban:* Output dari fungsi tersebut sangat bergantung pada konfigurasi sistem operasi (locale bahasa dan zona waktu). Jika zona waktu server Node.js (misal: UTC) berbeda dengan browser pengguna (misal: GMT+7), teks yang dihasilkan di server tidak akan cocok dengan yang dihitung klien, memicu peringatan hydration error.

10. **Bagaimana parameter `transform` pada `useAsyncData` menghemat penggunaan memori di klien?**
    * *Jawaban:* `transform` mengeksekusi fungsi sanitasi data di sisi server sebelum objek disimpan ke payload serialisasi. Objek masif dari backend dipangkas, sehingga browser klien hanya menerima dan mengalokasikan memori untuk data yang benar-benar ditampilkan, mereduksi footprint heap memori JavaScript di browser secara signifikan.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario:** Aplikasi Nuxt 3 Anda mendadak mengalami crash di Kubernetes pod dengan indikasi exit code 137 (OOMKilled) setelah Anda meluncurkan fitur dashboard real-time yang menggunakan WebSocket via external library. Analisis kemungkinan akar masalahnya!
    * *Jawaban:* Kemungkinan besar koneksi WebSocket diinisialisasi di dalam *root* fungsi `setup()` atau universal lifecycle hook tanpa pembatasan platform (`import.meta.client`). Karena server me-render setiap request, server membuka koneksi WebSocket baru ke remote cluster pada setiap HTTP request yang masuk dan menahannya di memori karena tidak ada mekanisme disconnect di server (mengingat `onUnmounted` tidak dieksekusi di Node.js). Hal ini menghabiskan pool connection file descriptor dan memori heap V8 secara linear hingga pod dibunuh oleh OOM Killer.

12. **Skenario:** Tim QA melaporkan bahwa pada halaman produk tertentu, token autentikasi rahasia milik pengguna admin yang sedang mengedit produk terkadang terlihat di page source oleh pengguna anonim biasa. Bagaimana insiden keamanan katastropik ini bisa terjadi pada arsitektur SSR?
    * *Jawaban:* Insiden ini terjadi akibat penggunaan *Cross-Request State Pollution*. Variabel auth state dideklarasikan di level modul (singleton) di server, atau instance Pinia tidak diisolasi per request (`createPinia()` dipanggil di luar konteks request handler Nuxt). Ketika admin melakukan fetch data, token disimpan di singleton memory. Ketika request berikutnya dari pengguna anonim masuk pada thread Node.js yang sama, SSR engine menyertakan state lama yang masih tersimpan di singleton tersebut ke dalam payload serialisasi HTML pengguna anonim.

13. **Skenario:** Anda telah mengaktifkan Content Security Policy (CSP) yang ketat dengan directive `script-src 'self'`. Namun setelah deployment produksi, seluruh aplikasi Nuxt 3 Anda menjadi layar putih kosong dan hydration mati total. Jelaskan mengapa hal ini terjadi dan bagaimana solusinya!
    * *Jawaban:* Nuxt secara inheren menyuntikkan inline script berisi payload `window.__NUXT__ = {...}` untuk hidrasi klien. Kebijakan CSP `script-src 'self'` memblokir eksekusi seluruh inline script yang tidak memiliki hashing atau cryptographic nonce yang valid. Solusinya adalah mengimplementasikan server hook plugin yang men-generate `nonce` unik menggunakan CSPRNG per-request, lalu menyematkan nonce tersebut pada header HTTP CSP dan ke setiap script tag Nuxt via `render:html` hook.

---

### 16. Summary

Mengoperasikan Nuxt 3 pada skala enterprise menuntut pergeseran paradigma dari pengembangan frontend tradisional ke ranah rekayasa sistem terdistribusi. Node.js runtime bukan lagi sekadar server build tool, melainkan lingkungan produksi kritis yang rentan terhadap *memory leak*, *thread contention*, dan kerentanan keamanan data.

Kunci utama stabilitas aplikasi SSR enterprise bertumpu pada tiga pilar:
1. **Pemisahan Lifecycle & Isolasi Status (Context Isolation):** Menjamin ketiadaan objek *singleton* lintas request, memahami eksekusi hook SSR vs Browser, dan mengeliminasi hidrasi non-deterministik.
2. **Efisiensi Hybrid Rendering:** Mengurangi beban CPU server secara drastis melalui pemanfaatan route rules yang strategis (SWR, ISR, Edge Prerender) sehingga server hanya melakukan komputasi intensif ketika benar-benar dibutuhkan.
3. **Hardening & Data Pruning:** Melindungi aplikasi dari potensi eksfiltrasi data backend melalui seleksi ketat serialisasi payload (`pick`/`transform`) serta penerapan layer pertahanan server seperti Dynamic CSP Nonces dan rate limiting terdistribusi.