# Bab 10 Module 01: Performance, SSR/Nuxt 3, & Production Hardening

---

## SEKSI 01 — IDENTITAS MODUL
* **Domain Kurikulum:** `03-Frontend-and-Mobile`
* **Track:** `Vue.js Enterprise Engineering`
* **Modul:** `Bab 10 Module 01`
* **Topik:** `Performance, SSR/Nuxt 3, & Production Hardening`
* **Prasyarat Teknis:** Vue 3 Composition API (`<script setup>`), TypeScript Tingkat Lanjut, Fundamental HTTP/Network (TCP, TLS, HTTP/2/3, Caching Headers), Arsitektur Node.js Runtime.
* **Target Audience:** Senior Frontend Engineer, Fullstack Engineer, Frontend System Architect.

---

## SEKSI 02 — LEARNING OBJECTIVES
Pada akhir modul ini, peserta didik mampu:
1. Menguasai siklus hidup rendering SSR (*Server-Side Rendering*) dan mekanisme hidrasi (*hydration engine*) Vue 3 untuk mengeliminasi *hydration mismatch* dan *memory leak*.
2. Merancang arsitektur aplikasi hibrida menggunakan Nuxt 3 (Universal SSR, Static Site Generation/SSG, Incremental Static Regeneration/ISR, dan Server-Side Route Rules).
3. Menganalisis dan mengoptimalkan metrik Core Web Vitals (LCP, INP, CLS) secara deterministik pada layer server runtime, bundling Vite, dan DOM client.
4. Menerapkan protokol pengamanan produksi (*production hardening*) mencakup Content Security Policy (CSP) berbasis nonces, sanitasi state hydration anti-XSS, mitigasi SSRF, dan audit dependensi engine Nitro.
5. Membangun observabilitas terdistribusi menggunakan OpenTelemetry, structured logging, dan error tracking terintegrasi pada edge/Node.js serverless runtimes.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

```
+-----------------------------------------------------------------------------+
| CLIENT-SIDE RENDERING (CSR) MENTAL MODEL                                    |
| Client: [HTML Kosong] -> Unduh JS -> Eksekusi JS -> Fetch API -> Render UI  |
| Masalah: Blank Screen, LCP Lambat, SEO Buruk, CPU-bound pada Client         |
+-----------------------------------------------------------------------------+
                                     VS
+-----------------------------------------------------------------------------+
| DUAL-ENVIRONMENT EXECUTION ENGINE (SSR / Nuxt 3)                           |
| 1. SERVER RUNTIME: Node.js/V8 Isolate                                       |
|    - Request Masuk -> Buat Request Context Unik                             |
|    - Inisialisasi Pinia Store / State -> Eksekusi Setup() -> Render String  |
|    - Susun HTML Statis + Serialisasi State Payload (__NUXT_DATA__)          |
|    - Flush Response Stream ke Browser                                       |
| 2. CLIENT RUNTIME: Browser Engine                                           |
|    - Terima HTML (FCP Cepat, Konten langsung terbaca)                       |
|    - Unduh Chunk JS Terkompresi                                             |
|    - Hidrasi: Vue mencocokkan Virtual DOM dengan DOM Aktual Server          |
|    - Aplikasi Aktif (Interactive / INP Siap)                                |
+-----------------------------------------------------------------------------+
```

Pergeseran paradigma terbesar dari SPA tradisional ke SSR/Nuxt 3 adalah: **Kode Anda berjalan di dua dunia yang memiliki hukum fisika berbeda.**

* **State Isolation:** Di browser, memori terisolasi per tab pengguna (`window` bersifat privat). Di server (Node.js/Nitro), satu proses runtime melayani ribuan request konkuren. Mutasi variabel global di server adalah pelanggaran fatal yang menyebabkan *Cross-Request State Pollution*—kondisi di mana Data User A bocor ke sesi User B.
* **Deterministic Hydration:** Hidrasi bukanlah render ulang dari nol; hidrasi adalah proses reaksioner di mana Vue Client "mengklaim" node DOM yang dicetak oleh Node.js Server. Jika pohon VNode client berbeda satu karakter saja dari DOM server (misalnya membaca `new Date()` atau `localStorage` pada fase setup), hidrasi mengalami desinkronisasi (*hydration mismatch*), memaksa browser membuang DOM dan melakukan *client-bailout* yang merusak performa LCP/INP.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur eksekusi request Nuxt 3 / Nitro engine dari client request hingga complete hydration:

```
[ BROWSER CLIENT ]                                            [ NITRO ENGINE / SERVER ]
       |                                                                 |
       | 1. HTTP GET /products/sku-992                                    |
       |---------------------------------------------------------------->|
       |                                                                 | 2. Route Rules Check
       |                                                                 |    (SWR, ISR, SSR, Proxy)
       |                                                                 | 3. H3 EventContext Init
       |                                                                 |    (AsyncLocalStorage)
       |                                                                 | 4. Vue SSR App Creation
       |                                                                 |    (createSSRApp per request)
       |                                                                 | 5. Router & Middleware
       |                                                                 | 6. Setup Scripts Execution
       |                                                                 |    - useAsyncData / $fetch
       |                                                                 |    - Upstream API Calling
       |                                                                 | 7. SSR Render to String
       |                                                                 |    (renderToString(app))
       |                                                                 | 8. State Serialization
       |                                                                 |    (devalue -> <script id="__NUXT_DATA__">)
       |                                                                 | 9. Security Headers Injected
       |                                                                 |    (CSP Nonce, HSTS, CORS)
       | 10. HTTP 200 OK (Stream HTML + Inlined Critical CSS + Payload)  |
       |<----------------------------------------------------------------|
       |                                                                 
[ BROWSER DOM ENGINE ]                                                   
       |                                                                 
  11. First Contentful Paint (FCP) - Browser parse HTML & CSS            
  12. Parse Inlined State Payload (__NUXT_DATA__)                        
  13. Parallel Fetch: Asynchronous JS Chunks (Vite Entrypoint)           
  14. Execute Client App Initializer                                     
  15. Vue Hydration Algorithm:                                           
      +-------------------------------------------------------+          
      | VNode Client Tree matched against Real DOM Node Tree  |          
      | Event Listeners attached (v-on:click, inputs)         |          
      | Reactive Effects Triggered                            |          
      +-------------------------------------------------------+          
  16. Time to Interactive (TTI) / Core Web Vitals Ready                  
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Vue 3 SSR Compiler & String Push Engine
Di balik layar, `@vue/compiler-ssr` mengubah Single File Component (SFC) secara berbeda dibanding `@vue/compiler-dom`.
* Kompiler client menghasilkan *render function* berbasis `h(tag, props, children)` atau blok pengenal patch flag.
* Kompiler SSR mentransformasikan template statis menjadi instruksi penggabungan string murni buffer: `_push('<div><span>Text</span></div>')`.
* Struktur dinamis menggunakan interpolasi runtime: `_push(`<div>${_ssrInterpolate(_ctx.msg)}</div>`)`.
Pendekatan ini memangkas overhead pembuatan Virtual DOM tree di server hingga 60-80%, mengurangi memory allocation per request.

### 2. State Serialization dengan devalue
Nuxt 3 tidak menggunakan `JSON.stringify` mentah untuk mengirimkan server-state ke client, melainkan menggunakan `devalue`.
* **Mengatasi Siklus:** Mendukung referensi melingkar (*circular references*).
* **Tipe Data Kompleks:** Mendukung serialisasi `Date`, `RegExp`, `Map`, `Set`, `BigInt`, `undefined`, dan `Error`.
* **XSS Mitigation:** Meng-escape secara otomatis karakter berbahaya seperti `<`, `>`, dan `/` untuk menghentikan injeksi `<script>` nakal yang diselipkan pada string JSON.

### 3. Asynchronous Context Isolation (`unctx` & `AsyncLocalStorage`)
Untuk menghindari *singleton leak*, Nuxt mengimplementasikan `unctx` yang dikombinasikan dengan Node.js `AsyncLocalStorage`.
Saat Anda memanggil fungsi composable tanpa passing parameter eksplisit (seperti `useRoute()`, `useNuxtApp()`), Nuxt menarik konteks aktif dari execution thread asinkron yang terisolasi. Jika developer menggunakan callback `setTimeout` atau raw Promise tanpa penanganan context binding, context reference ini terputus, menghasilkan error: `"Nuxt instance unavailable"`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Core Web Vitals: Korelasi dengan Nuxt 3 & SSR
* **LCP (Largest Contentful Paint):** Target $\le 2.5$ detik. LCP diukur dari elemen visual terbesar (biasanya hero image atau blok teks utama). SSR mempercepat LCP secara drastis dibanding SPA karena markup teks langsung tersedia. Namun, jika SSR memblokir proses rendering karena pemanggilan upstream API internal yang lambat (*Time To First Byte* / TTFB tinggi), LCP akan hancur.
* **INP (Interaction to Next Paint):** Target $\le 200$ milidetik (menggantikan FID). INP mengukur latensi respons UI terhadap klik/interaksi pengguna. Dalam aplikasi SSR berukuran besar, jika fase hidrasi membekukan thread utama CPU (Main Thread Task Duration > 50ms), user yang mengklik tombol saat JS sedang diurai akan mengalami kelambatan input drastis.
* **CLS (Cumulative Layout Shift):** Target $\le 0.1$. Terjadi pergeseran visual ketika elemen yang dirender server tiba-tiba diubah ukurannya atau digeser oleh komponen client yang terlambat dimuat (misalnya banner iklan atau hidrasi fallback `<ClientOnly>`).

### Strategi Rendering Hibrida: Route Rules
Nuxt 3 memungkinkan pemetaan arsitektur rendering per route path melalui konfigurasi engine Nitro:
* **SSR (Universal Rendering):** HTML dirender on-demand per request. Cocok untuk data personalisasi dinamis tinggi.
* **SSG (Static Pre-rendering):** HTML diekstrak saat build time. Cocok untuk dokumentasi dan landing page.
* **SWR (Stale-While-Revalidate):** Route disajikan dari cache memori/edge. Jika kedaluwarsa, response stale tetap disajikan ke client sementara worker server meregenerasi cache di latar belakang.
* **ISR (Incremental Static Regeneration):** Regenerasi berkala berbasis durasi time-to-live (TTL), memungkinkan konten diperbarui tanpa rebuild seluruh aplikasi.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi SSR Data Fetching yang tahan banting dengan isolasi error, state deduplication, dan pemisahan rendering client-only.

### File: `app/components/ProductMetric.vue`
```vue
<script setup lang="ts">
interface MetricProps {
  productId: string;
}

interface ProductDetails {
  id: string;
  name: string;
  stock: number;
  price: number;
  lastUpdated: string;
}

const props = defineProps<MetricProps>();

// Inisialisasi composable aman dengan useAsyncData
// Memastikan data di-fetch di server, di-serialize, dan dihidrasi di client tanpa duplicate network request
const { data: product, status, error, refresh } = await useAsyncData<ProductDetails>(
  `product-metric-${props.productId}`,
  () => $fetch<ProductDetails>(`/api/v1/products/${props.productId}`),
  {
    lazy: false,
    server: true,
    transform: (data) => ({
      ...data,
      lastUpdated: new Date(data.lastUpdated).toLocaleDateString('id-ID'),
    }),
  }
);
</script>

<template>
  <div class="product-card border p-4 rounded-lg bg-white shadow-sm">
    <div v-if="status === 'pending'" class="animate-pulse flex flex-col gap-2">
      <div class="h-6 bg-slate-200 rounded w-1/3"></div>
      <div class="h-4 bg-slate-200 rounded w-1/2"></div>
    </div>

    <div v-else-if="status === 'error'" class="text-rose-600">
      <p class="font-bold">Gagal memuat data produk.</p>
      <p class="text-xs text-slate-500">{{ error?.message }}</p>
      <button 
        @click="() => refresh()" 
        class="mt-2 px-3 py-1 bg-rose-50 border border-rose-200 text-rose-700 rounded text-sm hover:bg-rose-100"
      >
        Coba Lagi
      </button>
    </div>

    <div v-else-if="product" class="flex flex-col gap-2">
      <h2 class="text-xl font-bold tracking-tight text-slate-900">{{ product.name }}</h2>
      <p class="text-slate-600 font-mono text-sm">SKU: {{ product.id }}</p>
      <p class="text-emerald-700 font-semibold text-lg">
        Rp {{ product.price.toLocaleString('id-ID') }}
      </p>
      
      <!-- Komponen interaktif yang hanya boleh dirender di client untuk mencegah mismatch -->
      <ClientOnly>
        <template #fallback>
          <div class="h-8 bg-slate-100 border border-dashed rounded flex items-center justify-center text-xs text-slate-400">
            Sinkronisasi status keranjang...
          </div>
        </template>
        <div class="mt-4 pt-2 border-t flex justify-between items-center">
          <span class="text-xs text-slate-400">Stok real-time: {{ product.stock }}</span>
          <button class="px-4 py-2 bg-indigo-600 text-white rounded font-medium text-sm hover:bg-indigo-700">
            Beli Sekarang
          </button>
        </div>
      </ClientOnly>
    </div>
  </div>
</template>
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 18–29 (`useAsyncData`):**
  * Parameter pertama: `product-metric-${props.productId}` bertindak sebagai *unique cache key*. Nuxt memeriksa apakah payload dengan key ini sudah ada di `payload.data` browser. Jika ada, callback `$fetch` dilewati di client, menghindari *double fetching*.
  * Opsi `server: true`: Menginstruksikan Nuxt untuk menjalankan pemanggilan ini selama server render phase.
  * Opsi `transform`: Memproses struktur data sebelum diserialisasi ke dalam HTML payload. Ini krusial untuk payload slimming—menghilangkan field database internal yang tidak perlu sebelum dikirim ke jaringan.
* **Baris 46–60 (`ClientOnly`):**
  * Membatasi eksekusi rendering tombol aksi dan stock tracker ke browser context.
  * Blok `#fallback`: Slot ini dirender oleh server dan bertahan sampai bundel JavaScript client selesai terhidrasi. Ini mencegah pergeseran layout (CLS) karena reserved space dipertahankan.

---

## SEKSI 09 — STUDI KASUS NYATA (ENTERPRISE SCENARIO)

### Masalah
Platform E-Commerce Enterprise "MegaRetail" mengalami krisis arsitektur menjelang Flash Sale tahunan:
1. **TTFB Membengkak:** TTFB melonjak dari 150ms menjadi 4200ms saat traffic mencapai 25.000 concurrent requests/second. Node.js backend CPU mentok pada 100% akibat re-rendering halaman katalog produk yang sama secara terus-menerus.
2. **Hydration Mismatch Storm:** Sentry mencatat 120.000 error hydration per jam karena komponen flash-sale timer menghitung sisa waktu berbasis `Date.now()` di level root SFC, yang menyebabkan desinkronisasi jam server dan jam perangkat client.
3. **Cross-Session Data Leakage:** Akibat salah penempatan inisialisasi state cart di level root module (`const cart = reactive([])` di luar `setup()`), keranjang belanja satu user muncul di browser user lain yang login secara bersamaan.

### Solusi Arsitektural
1. Menerapkan **Stale-While-Revalidate (SWR)** via Nitro Route Rules untuk halaman katalog produk dan cache tag invalidation.
2. Memperbaiki State Architecture dengan **Pinia SSR Scoped Stores** untuk mencegah cross-session leak.
3. Mengisolasi flash-sale timer menggunakan kombinasi server timestamp passing dan client-side animation sync.
4. Menerapkan Content Security Policy (CSP) Nonce-based enforcement pada level response header Nitro.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & PRODUCTION CODE

### 1. File Konfigurasi Arsitektur: `nuxt.config.ts`
```typescript
import { defineNuxtConfig } from 'nuxt/config';

export default defineNuxtConfig({
  ssr: true,
  typescript: {
    strict: true,
    typeCheck: true,
  },
  routeRules: {
    // Landing pages & Marketing: SSG Pre-rendered
    '/': { prerender: true },
    
    // Product Catalog: SWR Caching selama 120 detik, stale dilayani hingga 10 menit
    '/products/**': {
      swr: 120,
      headers: {
        'Cache-Control': 'public, max-age=120, stale-while-revalidate=600',
      },
    },
    
    // User Cart & Checkout: Full SSR No-Store (Data Sensitif)
    '/checkout/**': {
      ssr: true,
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate',
      },
    },
    
    // Admin Backoffice: SPA Mode (CSR Only)
    '/admin/**': { ssr: false },
  },
  nitro: {
    compressPublicAssets: true,
    timing: true, // Server-Timing API header injection
  },
  vite: {
    build: {
      cssCodeSplit: true,
      rollupOptions: {
        output: {
          manualChunks(id) {
            // Memisahkan dependensi raksasa menjadi chunk independen
            if (id.includes('node_modules/lodash')) return 'vendor-lodash';
            if (id.includes('node_modules/chart.js')) return 'vendor-charts';
          },
        },
      },
    },
  },
});
```

### 2. Nitro Server Engine Security Middleware: `server/middleware/security-hardening.ts`
```typescript
import { defineEventHandler, setResponseHeader, createError } from 'h3';
import { randomBytes } from 'node:crypto';

export default defineEventHandler((event) => {
  // Hanya proses HTTP responses
  const req = event.node.req;
  const res = event.node.res;

  // 1. Mitigasi Host Header Injection
  const host = req.headers['host'];
  const allowedHosts = process.env.ALLOWED_HOSTS?.split(',') || ['localhost:3000'];
  if (host && !allowedHosts.includes(host)) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid Host Header',
    });
  }

  // 2. Generate Cryptographic Nonce per-request
  const nonce = randomBytes(16).toString('base64');
  event.context.nonce = nonce;

  // 3. Strict Content Security Policy (CSP) with Nonce
  const cspHeader = [
    `default-src 'self'`,
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src 'self' 'unsafe-inline'`, // Hindari unsafe-inline jika menggunakan CSS extraction utuh
    `img-src 'self' data: https://cdn.megaretail.com`,
    `font-src 'self'`,
    `connect-src 'self' https://api.megaretail.com`,
    `frame-ancestors 'none'`,
    `base-uri 'self'`,
    `form-action 'self'`,
  ].join('; ');

  setResponseHeader(event, 'Content-Security-Policy', cspHeader);
  setResponseHeader(event, 'X-Frame-Options', 'DENY');
  setResponseHeader(event, 'X-Content-Type-Options', 'nosniff');
  setResponseHeader(event, 'Referrer-Policy', 'strict-origin-when-cross-origin');
  setResponseHeader(event, 'Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  
  if (process.env.NODE_ENV === 'production') {
    setResponseHeader(event, 'Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
  }
});
```

### 3. Isolated State Management: `stores/cart.ts`
```typescript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export interface CartItem {
  id: string;
  sku: string;
  quantity: number;
  unitPrice: number;
}

// Store terikat pada instance Pinia per request, bukan global state module
export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>([]);
  const isHydrated = ref<boolean>(false);

  const subtotal = computed(() =>
    items.value.reduce((total, item) => total + item.quantity * item.unitPrice, 0)
  );

  const totalQuantity = computed(() =>
    items.value.reduce((total, item) => total + item.quantity, 0)
  );

  function initializeFromSession(cartPayload: CartItem[]) {
    // Melindungi mutasi dari cross-request injection
    items.value = [...cartPayload];
    isHydrated.value = true;
  }

  function addItem(item: CartItem) {
    const existingIndex = items.value.findIndex((i) => i.id === item.id);
    if (existingIndex > -1) {
      items.value[existingIndex].quantity += item.quantity;
    } else {
      items.value.push({ ...item });
    }
  }

  function clearCart() {
    items.value = [];
  }

  return {
    items,
    isHydrated,
    subtotal,
    totalQuantity,
    initializeFromSession,
    addItem,
    clearCart,
  };
});
```

### 4. Hydration-Safe Flash-Sale Product Component: `components/ProductFlashSale.vue`
```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useCartStore } from '~/stores/cart';

interface FlashSaleData {
  id: string;
  name: string;
  targetTimestamp: number;
  price: number;
}

const props = defineProps<{
  productId: string;
}>();

const cartStore = useCartStore();

// 1. Fetch server state secara deterministik
const { data: product, error } = await useAsyncData<FlashSaleData>(
  `flash-sale-${props.productId}`,
  () => $fetch(`/api/v1/flash-sale/${props.productId}`)
);

// State timer client-only
const timeLeftMs = ref<number>(0);
let timerInterval: ReturnType<typeof setInterval> | null = null;

// Synchronous format time function: menghindari mismatch
function calculateTimeLeft() {
  if (!product.value) return 0;
  return Math.max(0, product.value.targetTimestamp - Date.now());
}

onMounted(() => {
  // Hitung durasi awal hanya saat sudah di Browser
  timeLeftMs.value = calculateTimeLeft();
  
  // Update state setiap detik
  timerInterval = setInterval(() => {
    timeLeftMs.value = calculateTimeLeft();
    if (timeLeftMs.value <= 0 && timerInterval) {
      clearInterval(timerInterval);
    }
  }, 1000);
});

onUnmounted(() => {
  if (timerInterval) {
    clearInterval(timerInterval);
  }
});

const formattedTime = computed(() => {
  const totalSeconds = Math.floor(timeLeftMs.value / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
});

function handleAddToCart() {
  if (!product.value) return;
  cartStore.addItem({
    id: product.value.id,
    sku: product.value.id,
    quantity: 1,
    unitPrice: product.value.price,
  });
}
</script>

<template>
  <div v-if="error" class="p-4 bg-red-50 text-red-600 rounded">
    Gagal menginisialisasi promo.
  </div>

  <div v-else-if="product" class="p-6 border border-amber-200 bg-amber-50/30 rounded-xl">
    <div class="flex items-center justify-between">
      <h3 class="text-xl font-bold text-slate-800">{{ product.name }}</h3>
      
      <!-- Safe Client Container: Server mencetak Skeleton, Client menghidrasi Countdown -->
      <ClientOnly>
        <div class="px-3 py-1 bg-red-600 text-white font-mono font-bold text-sm rounded shadow-sm">
          Berakhir dalam: {{ formattedTime }}
        </div>
        <template #fallback>
          <div class="px-3 py-1 bg-slate-200 text-slate-500 font-mono text-sm rounded animate-pulse">
            Menghitung promo...
          </div>
        </template>
      </ClientOnly>
    </div>

    <div class="mt-4 flex items-center justify-between">
      <div class="text-2xl font-black text-rose-600 font-mono">
        Rp {{ product.price.toLocaleString('id-ID') }}
      </div>

      <button
        @click="handleAddToCart"
        :disabled="timeLeftMs <= 0 && timeLeftMs !== 0"
        class="px-6 py-2 bg-rose-600 hover:bg-rose-700 disabled:bg-slate-400 text-white font-semibold rounded-lg transition-colors"
      >
        Klaim Flash Sale
      </button>
    </div>
  </div>
</template>
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS KOMPARATIF

| Parameter | SPA Tradisional (Vite/Vue 3) | Pure SSR (Node.js Dynamic) | Nuxt 3 Hybrid (SWR / ISR Engine) |
| :--- | :--- | :--- | :--- |
| **First Contentful Paint (FCP)** | Sangat Lambat (Menunggu unduhan JS & parse VNode) | Sangat Cepat (HTML ter-render langsung dari stream) | Maksimal (Disajikan via Edge CDN Cache) |
| **Beban Server CPU** | Nol (Statik hosting murni di Object Storage/S3) | Sangat Tinggi (Server me-render string per HTTP hit) | Sangat Rendah (Render dieksekusi berkala/asinkron) |
| **Kompleksitas State** | Rendah (Hanya memori browser lokal) | Tinggi (Isolasi context per request wajib ketat) | Sangat Tinggi (Hydration synchronization + SWR timing) |
| **Skalabilitas Concurrency** | Hampir tak terbatas pada Static Storage | Membutuhkan auto-scaling horizontal agresif | Skala CDN (Menangani lonjakan flash-sale dengan aman) |
| **SEO & Social Crawlers** | Buruk tanpa Dynamic Pre-rendering proxy | Sempurna (Full markup ter-render) | Sempurna (Full markup ter-render) |
| **Latency Jaringan (TTFB)** | Cepat untuk HTML kosong, lambat untuk interaktivitas data | Bergantung pada downstream slowest microservice | Sangat Rendah (< 30-50ms via nearest POP CDN Edge) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Cross-Request State Pollution (Fatal Security Vulnerability)
* **Kondisi:** Menulis variabel stateful di level root module file JavaScript.
  ```typescript
  // FATAL ERROR PADA SSR!
  import { reactive } from 'vue';
  const sharedState = reactive({ user: null }); // Berbagi ruang memori yang sama pada seluruh proses Node.js
  export default function useUser() { return { sharedState }; }
  ```
* **Dampak:** Pengguna B dapat melihat identitas, data pribadi, atau sesi Pengguna A saat request diproses berbarengan dalam satu thread proses V8.
* **Mitigasi:** Selalu bungkus state di dalam composable via `useState()` atau Pinia Store yang terikat pada instance lifecycle Nuxt app (`useNuxtApp()`).

### 2. Microtask Context Disconnect (`AsyncLocalStorage` Lost)
* **Kondisi:** Memanggil Nuxt composables setelah melewati *macro-task* atau *unhandled async tick*.
  ```typescript
  // RUSAK: Composable dipanggil setelah raw setTimeout
  setTimeout(() => {
    const route = useRoute(); // Crash: "Nuxt instance is unavailable"
  }, 100);
  ```
* **Mitigasi:** Ambil semua konteks dependensi secara synchronous di level teratas sebelum memulai asynchronous dispatch.

### 3. Memory Leaks pada Persistent Server Process
* **Kondisi:** Mendaftarkan event listener pada `process`, global bus, atau menginisialisasi timer yang tidak dibersihkan di dalam code yang tereksekusi pada fase server.
* **Mitigasi:** `onMounted`, `onUpdated`, dan `onUnmounted` **TIDAK PERNAH DIJALANKAN DI SERVER**. Logika server hanya mengeksekusi `setup()`, hook lifecycle server-specific, dan Pinia actions yang dipanggil. Pastikan timer dan window/document listeners hanya berada di dalam blok `onMounted`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mengakses Web API Global di Server Setup
* **Salah:**
  ```vue
  <script setup>
  // Crash dengan "ReferenceError: window is not defined"
  const width = ref(window.innerWidth);
  </script>
  ```
* **Benar:**
  ```vue
  <script setup>
  const width = ref(0);
  onMounted(() => {
    width.value = window.innerWidth;
  });
  </script>
  ```

### 2. Menggunakan `useFetch` di Dalam Event Handler (Click Listener)
* **Salah:**
  ```vue
  <button @click="() => useFetch('/api/cart')">Update</button>
  ```
  `useFetch` adalah composable yang didesain untuk inisialisasi setup lifecycle component.
* **Benar:**
  Gunakan `$fetch` (Nitro HTTP client) untuk event handler atau mutasi imperatif on-demand.
  ```vue
  <button @click="async () => await $fetch('/api/cart', { method: 'POST' })">Update</button>
  ```

### 3. Invalid HTML Nesting Memicu Hydration Failure
* **Salah:** Menaruh tag `<div>` di dalam `<p>`, atau `<tr>` di luar `<tbody>`. Browser parser secara otomatis mengoreksi struktur HTML yang salah dengan menutup tag `<p>` secara prematur sebelum membaca `<div>`. Ketika Vue client mencoba mencocokkan VDOM tree dengan DOM yang sudah "diperbaiki" browser, terjadi *Hydration Failure*.
* **Benar:** Patuhi validitas spesifikasi HTML W3C secara ketat dalam perancangan template SFC.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **State Shrink-Wrapping (Payload Optimization):** Batasi ukuran payload `__NUXT_DATA__`. Jangan pernah mengembalikan full model entitas dari server API ke frontend jika UI hanya menampilkan judul dan ID. Gunakan parameter `pick: ['id', 'title']` pada `useFetch`.
2. **Explicit Component Hydration Isolation:** Pisahkan bagian halaman yang interaktif berat dan visual statis. Gunakan pattern Island Architecture jika memungkinkan atau bungkus area dinamis non-SEO ke dalam `<ClientOnly>`.
3. **Fail-Fast Error Boundaries:** Bungkus modul-modul independen yang rapuh (misalnya widget pihak ketiga, integrasi feeds eksternal) dengan `<NuxtErrorBoundary>` agar error lokal tidak me-render Error Page global 500 ke seluruh halaman.
4. **Nitro Storage Abstraction:** Hindari penggunaan file system `fs` lokal untuk menyimpan assets/cache di server runtime. Gunakan unstorage yang terhubung ke Redis atau S3 agar aplikasi tetap fully stateless dan siap untuk horizontal auto-scaling atau multi-region deployment.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Bundle Splitting & Tree-Shaking
Konfigurasikan Vite untuk melakukan eliminasi dead-code secara agresif:
```typescript
// nuxt.config.ts snippet
export default defineNuxtConfig({
  experimental: {
    payloadExtraction: true, // Ekstrak payload dari inline HTML menjadi file terpisah yang dapat di-cache
    treeshakeClientOnly: true, // Hapus total kode komponen ClientOnly dari bundel server
  },
  vite: {
    build: {
      target: 'esnext',
      minify: 'esbuild',
    },
  },
});
```

### 2. Network Resource Hints: Early Hints & Preload
Aktifkan *HTTP 103 Early Hints* pada proxy server (Cloudflare, Nginx, atau Nitro direct) untuk memberi tahu browser agar mengunduh file kritis (Font, Critical CSS) saat server Node.js masih sibuk memproses query database atau upstream API.

```
Link: </_nuxt/entry.modern.js>; rel=modulepreload; as=script,
      </fonts/inter.woff2>; rel=preload; as=font; crossorigin
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Anti-SSRF (Server-Side Request Forgery) Protection:** Saat melakukan fetching upstream di server Nuxt via dynamic input pengguna, pastikan URL divalidasi dan batasi hanya pada internal API whitelist:
   ```typescript
   // server/api/proxy.ts
   import { defineEventHandler, getQuery, createError } from 'h3';
   
   const ALLOWED_INTERNAL_HOSTS = ['https://internal-api.corp.local'];

   export default defineEventHandler((event) => {
     const { targetUrl } = getQuery(event);
     const parsed = new URL(String(targetUrl));

     if (!ALLOWED_INTERNAL_HOSTS.includes(parsed.origin)) {
       throw createError({ statusCode: 403, statusMessage: 'Forbidden Upstream Target' });
