# BAB-10-Performance-SSR-Nuxt-3-dan-Production-Hardening: Quiz, Challenge, & Knowledge Check

Dokumen ini berisi kumpulan evaluasi mandiri komprehensif untuk menguji dan memperdalam pemahaman arsitektur, optimasi performa Server-Side Rendering (SSR) pada Nuxt 3 / Nitro Engine, mitigasi memory leak, keamanan lingkungan produksi, dan orkestrasi deployment enterprise.

---

## Bagian 1: Basic Questions (5 Soal & Pembahasan)

### Soal 1: Cross-Request State Pollution
**Pertanyaan:**  
Mengapa deklarasi reactive state menggunakan variabel modul global (misalnya `const globalUser = ref(null)` di luar `defineComponent` atau `<script setup>`) sangat berbahaya pada lingkungan Node.js SSR Nuxt 3, dan bagaimana `useState()` memecahkan masalah tersebut?

**Kunci Jawaban & Pembahasan:**  
Pada lingkungan Node.js SSR, proses Node.js dijalankan sebagai server tunggal yang persisten melayani ratusan atau ribuan HTTP request secara bersamaan (*multi-tenant single process*). Jika reactive state dideklarasikan di level root modul (file scope), variabel tersebut disimpan di dalam memori heap proses Node.js dan dibagi (*shared*) ke seluruh request incoming.
- **Dampak Fatal:** Terjadi kebocoran data sensitif (*cross-request data leakage*) di mana Request B dapat membaca atau menimpa state autentikasi Request A.
- **Solusi dengan `useState`:** Nuxt 3 menyediakan composable `useState(key, init)`. Composable ini mengikat reactive state langsung ke lifecycle instans Nuxt App aktif (`nuxtApp.payload.state`) yang terisolasi per context HTTP request via Node.js `AsyncLocalStorage`. Saat request selesai, state di-serialize ke payload HTML untuk dihidrasi di browser tanpa mencemari request klien lain di server.

---

### Soal 2: Hydration Mismatch Penyebab & Pencegahan
**Pertanyaan:**  
Apa yang dimaksud dengan *Hydration Mismatch* pada Nuxt 3, sebutkan dua penyebab paling umum yang sering terjadi di level kode, dan bagaimana teknik mengatasinya tanpa mematikan SSR secara global?

**Kunci Jawaban & Pembahasan:**  
*Hydration Mismatch* adalah kondisi inkonsistensi DOM tree ketika Virtual DOM yang dirender oleh browser runtime klien tidak identik dengan HTML string statis yang di-stream dari server SSR.
- **Penyebab Umum:**
  1. Penggunaan API browser langsung saat SSR pass, seperti `window.innerWidth`, `localStorage`, atau `navigator.userAgent`.
  2. Formatting waktu/tanggal dinamis (misal: `new Date().toLocaleTimeString()`) di mana timestamp server berbeda milidetik dengan waktu hidrasi klien, atau timezone server (UTC) berbeda dengan timezone browser klien (WIB).
  3. Struktur tag HTML tidak valid yang dinormalisasi browser secara otomatis (contoh: meletakkan tag `<div>` atau `<p>` di dalam tag `<p>`).
- **Pencegahan/Solusi:**
  - Bungkus komponen browser-dependent menggunakan `<ClientOnly fallbackTag="span" fallback="Loading...">`.
  - Gunakan composable `onMounted()` untuk manipulasi data yang bergantung pada environment klien.
  - Untuk waktu, format tanggal di server menggunakan referensi UTC atau sinkronkan via `useState` agar data snapshot server dioper ke klien tanpa evaluasi ulang.

---

### Soal 3: Route Rules & Hybrid Rendering di Nitro
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara opsi Route Rules `swr` (Stale-While-Revalidate), `isr` (Incremental Static Regeneration), dan `prerender` pada konfigurasi `nuxt.config.ts`. Kapan masing-masing strategi tepat digunakan?

**Kunci Jawaban & Pembahasan:**  
Nitro engine memungkinkan granular caching di level URL route:
1. **`prerender: true`**:
   - *Mekanisme:* Halaman di-render ke HTML statis saat fase build-time (`npx nuxt build` / `generate`). Server runtime tidak melakukan SSR komputasi sama sekali.
   - *Use Case:* Halaman statis murni yang jarang berubah, seperti Kebijakan Privasi, FAQ, Terms of Service, atau landing page marketing statis.
2. **`swr: number | true` (Stale-While-Revalidate)**:
   - *Mekanisme:* Request pertama memicu SSR dan hasilnya disimpan di cache layer (RAM/Redis/Vercel KV) selama TTL (Time-To-Live). Request berikutnya dalam window TTL akan langsung menerima cached response. Ketika TTL habis, request berikutnya tetap menerima halaman lama (*stale*) secara instan sementara Nitro meregenerasi halaman baru di latar belakang (*revalidate*).
   - *Use Case:* Katalog produk e-commerce, artikel berita, blog listing dengan traffic tinggi di mana sedikit delay pembaruan data (misal 60 detik) dapat ditoleransi demi latensi TTFB < 50ms.
3. **`isr: number | true`**:
   - *Mekanisme:* Konsep serupa dengan SWR pada platform serverless / edge tertentu (seperti Netlify/Vercel Blob), di mana halaman diregenerasi saat cache kedaluwarsa dan request yang datang menunggu atau disajikan versi statis yang baru di-persist ke CDN storage.
   - *Use Case:* Halaman dinamis semi-statis berskala puluhan ribu halaman yang tidak mungkin di-prerender semua saat build time (On-demand ISR).

---

### Soal 4: Composable Data Fetching: `useAsyncData` vs `useFetch` vs `$fetch`
**Pertanyaan:**  
Mengapa kita tidak boleh menggunakan `$fetch` langsung di dalam root `<script setup>` komponen Nuxt 3 pada mode SSR, dan apa fungsi parameter `key` serta properti `lazy` pada `useFetch`?

**Kunci Jawaban & Pembahasan:**  
- **Bahaya `$fetch` langsung:** `$fetch` adalah library HTTP client berbasis ofetch. Jika dipanggil langsung di root setup (`const data = await $fetch('/api/user')`), panggilan tersebut akan dieksekusi **dua kali**: pertama di server saat SSR, dan kedua di browser saat hidrasi klien. Ini memicu *double request*, membebani backend, dan menyebabkan flicker UI.
- **Peran `useFetch` / `useAsyncData`:** Keduanya membungkus `$fetch` dengan logika state transfer. Response di server disimpan ke `payload` JSON yang disisipkan ke halaman. Di browser, Nuxt membaca data dari `payload` tanpa menembak ulang HTTP request.
- **Parameter `key`:** Identifier unik untuk mengindeks cache data di dalam `nuxtApp.payload.data`. Jika dua komponen memakai key yang sama, mereka membagi payload yang sama.
- **Opsi `lazy: true`:** Menghindari pemblokiran navigasi halaman (*non-blocking*). Server atau client router tidak akan menunggu promise selesai untuk menampilkan layout/halaman; navigasi berjalan instan sementara state `status === 'pending'` dapat dimanfaatkan untuk menampilkan skeleton UI.

---

### Soal 5: Treeshaking dan Bundle Optimization
**Pertanyaan:**  
Bagaimana arsitektur impor Nuxt 3 memastikan modul server-only (seperti database query Prisma atau Node.js crypto) tidak bocor ke dalam JavaScript bundle klien?

**Kunci Jawaban & Pembahasan:**  
Nuxt 3 memisahkan bundle server dan client secara fisik melalui Rollup/Vite build matrix:
1. **Server Directory (`server/`)**: Seluruh file di `server/api`, `server/routes`, dan `server/middleware` hanya dikompilasi oleh Nitro engine untuk target runtime server (Node.js/Bun/Edge). File-file ini tidak pernah diikutsertakan ke dalam manifest Vite client-side bundle.
2. **File Suffixes (`.server.vue` dan `.client.vue`)**: Komponen dengan akhiran `.server.vue` hanya dirender di server dan HTML-nya dikirim tanpa JavaScript payload komponen tersebut.
3. **Environment Guards & Dead Code Elimination (DCE)**: Variabel `import.meta.server` dan `import.meta.client` dievaluasi saat compile time. Blok kode di dalam `if (import.meta.server) { ... }` akan di-*treeshake* (dibuang total) oleh Vite saat memproduksi client bundle, asalkan dependensi tidak diimpor secara statis di top-level scope tanpa dynamic import.

---

## Bagian 2: Intermediate Questions (5 Soal & Pembahasan)

### Soal 6: Isolasi Konteks Event & Async Hooks
**Pertanyaan:**  
Diberikan cuplikan server handler Nitro berikut:
```typescript
// server/api/report.ts
let currentUserId = ''

export default defineEventHandler(async (event) => {
  currentUserId = getHeader(event, 'x-user-id') || 'anonymous'
  await heavyDatabaseAggregation()
  return { user: currentUserId, status: 'generated' }
})
```
Jelaskan race condition apa yang terjadi jika endpoint ini menerima 50 concurrent request dalam 1 detik, dan tuliskan perbaikan kodenya yang benar!

**Kunci Jawaban & Pembahasan:**  
- **Masalah Race Condition:** Variabel `currentUserId` dideklarasikan di module scope (`server/api/report.ts`). Karena Node.js menjalankan event loop single-threaded dengan asinkronitas I/O, `await heavyDatabaseAggregation()` menangguhkan eksekusi request pertama. Saat request kedua masuk sebelum request pertama selesai, nilai `currentUserId` tertimpa oleh user ID request kedua. Akibatnya, request pertama akan mengembalikan response yang salah (terasosiasi dengan user lain).
- **Kode Perbaikan:**
```typescript
// server/api/report.ts
export default defineEventHandler(async (event) => {
  // Simpan variabel secara lokal di dalam scope event handler
  const currentUserId = getHeader(event, 'x-user-id') || 'anonymous'
  
  // Alternatif bila ingin diakses oleh middleware berikutnya dalam request yang sama:
  // event.context.userId = currentUserId

  await heavyDatabaseAggregation()
  
  return { 
    user: currentUserId, 
    status: 'generated' 
  }
})
```

---

### Soal 7: Memory Leak Profiling pada SSR Vue 3 / Nuxt 3
**Pertanyaan:**  
Mengapa penggunaan event listener global seperti `window.addEventListener` atau timer `setInterval` di dalam composable custom tanpa lifecycle teardown dapat menyebabkan memory leak parah pada server SSR, padahal `window` tidak tersedia di server?

**Kunci Jawaban & Pembahasan:**  
Meskipun `window` tidak ada di server, developer sering membuat composable yang menggunakan event bus Node.js (misalnya `process.on('message')`, EventEmitter eksternal, atau event listener pada koneksi database/Redis singleton):
1. **Lifecycle Hook SSR:** Di server, hook `onMounted` dan `onUnmounted` **TIDAK PERNAH DIJALANKAN**. Hanya `setup()` dan `onServerPrefetch` yang dieksekusi.
2. **Retained Reference Leak:** Jika sebuah composable me-register listener ke instans singleton (seperti `eventEmitter.on('event', callback)`) di dalam fungsi `setup()`, callback tersebut memegang referensi ke closure komponen Vue dan seluruh scope memori request tersebut.
3. Karena `onUnmounted` tidak dieksekusi di server untuk memanggil `.off()` / `removeListener()`, referensi callback ini akan terus menumpuk di heap memori pada setiap HTTP request yang masuk. Garbage Collector (V8) tidak dapat membersihkan alokasi memori tersebut, yang berujung pada degradasi performa, garbage collection pause tinggi, dan akhirnya crash dengan error `FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory`.

---

### Soal 8: Security Hardening: Content Security Policy (CSP) & Nonces
**Pertanyaan:**  
Nuxt 3 menyisipkan inline script untuk state hydration (`window.__NUXT__ = { ... }`). Bagaimana cara menerapkan Content Security Policy (CSP) dengan `script-src 'strict-dynamic'` tanpa menggunakan keyword `'unsafe-inline'` yang membahayakan aplikasi dari serangan XSS?

**Kunci Jawaban & Pembahasan:**  
Menggunakan `'unsafe-inline'` pada direktif `script-src` menonaktifkan proteksi CSP terhadap script injection XSS. Solusi enterprise yang didukung Nuxt 3 (misalnya via modul `@nuxtjs/security` atau server middleware kustom Nitro) adalah menggunakan **Cryptographic Nonce**:
1. Server Nitro mengenerate random base64 cryptographically secure string (nonce) untuk setiap HTTP incoming request menggunakan `crypto.randomBytes(16).toString('base64')`.
2. Server menyusun header HTTP response:
   ```http
   Content-Security-Policy: script-src 'strict-dynamic' 'nonce-<RANDOM_NONCE>' 'unsafe-inline' http: https:; object-src 'none'; base-uri 'none';
   ```
3. Nuxt menginjeksikan atribut `nonce="<RANDOM_NONCE>"` ke seluruh tag `<script>` yang digenerate oleh framework, termasuk skrip hidrasi payload state dan preloaded chunks.
4. Browser yang mendukung CSP Level 3 mengabaikan `'unsafe-inline'` saat mendeteksi adanya token nonce valid, dan mengeksekusi hanya inline script yang memiliki nilai nonce yang cocok persis dengan header response request tersebut.

---

### Soal 9: Optimasi Time To First Byte (TTFB) dengan Payload Extraction & CDN Caching
**Pertanyaan:**  
Dalam audit Core Web Vitals, metrik Time to First Byte (TTFB) halaman Nuxt 3 mencapai 1200ms di staging. Analisis menunjukkan ada 3 pemanggilan `useFetch` serial di `<script setup>`. Bagaimana cara merestrukturisasi kode dan konfigurasi Nitro untuk menekan TTFB hingga di bawah 150ms?

**Kunci Jawaban & Pembahasan:**  
1. **Paralelisasi Fetch (Menghilangkan Waterfall):**
   Ubah pemanggilan serial:
   ```typescript
   // Buruk (Waterfall):
   const { data: user } = await useFetch('/api/user')
   const { data: orders } = await useFetch('/api/orders')
   const { data: notifs } = await useFetch('/api/notifications')
   ```
   Menjadi konkurensi via `Promise.all` atau parallel `useAsyncData`:
   ```typescript
   // Optimal (Konkuren):
   const { data } = await useAsyncData('dashboard-data', async () => {
     const [user, orders, notifs] = await Promise.all([
       $fetch('/api/user'),
       $fetch('/api/orders'),
       $fetch('/api/notifications')
     ])
     return { user, orders, notifs }
   })
   ```
2. **Aktifkan Route Rules Caching di Nitro (`nuxt.config.ts`):**
   ```typescript
   routeRules: {
     '/dashboard/**': { swr: 60, cache: { maxAge: 60, staleMaxAge: 300 } }
   }
   ```
3. **Lazy Fetching untuk Data Non-Kritis:**
   Pindahkan data notifications atau chart interaktif ke klien menggunakan `lazy: true` atau eksekusi di `onMounted` agar HTML awal langsung di-stream tanpa menunggu API tier lambat.

---

### Soal 10: Graceful Shutdown & Health Checks pada Containerized Nuxt (Docker)
**Pertanyaan:**  
Mengapa sinyal `SIGTERM` harus ditangani dengan benar oleh Node.js server container Nuxt saat Kubernetes atau Docker swarm melakukan rolling update, dan apa yang terjadi jika aplikasi dijalankan via `CMD ["npm", "run", "start"]` alih-alih `CMD ["node", ".output/server/index.mjs"]`?

**Kunci Jawaban & Pembahasan:**  
- **Masalah `npm run start` (PID 1 Anti-pattern):** Jika container dijalankan dengan npm, proses npm berjalan sebagai Process ID 1 (PID 1). Secara default, npm tidak meneruskan sinyal POSIX seperti `SIGTERM` atau `SIGINT` ke child process (Node.js Nitro server). Ketika orchestrator mengirim `SIGTERM` untuk menghentikan container, Nitro server tidak mengetahuinya. Setelah masa grace period habis (default 30s), orchestrator mengirim `SIGKILL` paksa, yang langsung memutus koneksi database yang sedang aktif dan menggagalkan HTTP request in-flight yang sedang diproses pengguna (memicu error 502 Bad Gateway).
- **Praktik Terbaik:**
  1. Jalankan langsung binary keluaran build: `CMD ["node", ".output/server/index.mjs"]` sehingga Node.js menjadi PID 1 atau gunakan init manager ringan seperti `tini`.
  2. Implementasikan Nitro plugin graceful shutdown untuk menutup database connection pool dan menyelesaikan request aktif sebelum memanggil `process.exit(0)`.
  3. Sediakan endpoint liveness & readiness check (`/api/healthz`) untuk memastikan container hanya menerima traffic saat siap.

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Skenario)

### Skenario 1: Insiden "Black Friday Heap Out of Memory"
* **Konteks:** Sebuah platform e-commerce Nuxt 3 mengalami lonjakan traffic 10x lipat saat kampanye diskon jam 12 malam. Dalam waktu 7 menit, 4 pod Node.js mengalami crash bergantian dengan status `OOMKilled (Exit Code 137)`. Log APM menunjukkan peningkatan memori linear tanpa pernah turun kembali ke baseline.
* **Gejala Teknis:** CPU utilization mencapai 100% tepat sebelum pod tewas. Heap snapshot menunjukkan dominasi objek `VNode` dan referensi callback pada Pinia store.
* **Akar Masalah:**
  1. Ditemukan developer meletakkan plugin analytics kustom di mana pada root setup mereka memanggil:
     ```typescript
     // plugins/analytics.ts
     export default defineNuxtPlugin(() => {
       emitter.on('track', (payload) => {
         // Menyimpan history ke array global
         analyticsQueue.push(payload)
       })
     })
     ```
     Array `analyticsQueue` dideklarasikan di top-level plugin file tanpa batasan kapasitas. Di server, plugin dieksekusi berulang kali setiap ada request masuk, mendaftarkan listener baru ke emitter singleton dan array `analyticsQueue` terus menimbun payload request dari jutaan user.
  2. Pinia store didefinisikan dengan global variable caching tanpa `dispose()`.
* **Langkah Mitigasi & Remediasi:**
  1. **Hotfix:** Nonaktifkan server-side execution untuk analytics plugin dengan mengubah nama file menjadi `analytics.client.ts`.
  2. **Audit Composable:** Pastikan seluruh state store dikonstruksi melalui `defineStore` standar Pinia yang secara otomatis mereset context per request pada SSR.
  3. **Node Flag Tuning:** Tambahkan environment flag pada Dockerfile untuk profiling dan stabilitas alokasi heap:
     `NODE_OPTIONS="--max-old-space-size=2048 --heapsnapshot-near-heap-limit=3"`

---

### Skenario 2: Kebocoran Data Sesi User Akibat Cache Header Dinamis di CDN
* **Konteks:** Aplikasi SaaS B2B menggunakan Nuxt 3 di balik Cloudflare CDN. Halaman dashboard `/app/profile` tiba-tiba menampilkan nama, email, dan transaksi milik pengguna lain setelah update arsitektur Nitro Route Rules.
* **Gejala Teknis:** Pengguna A membuka `/app/profile` dan melihat datanya sendiri. Dua detik kemudian, Pengguna B di kantor berbeda membuka `/app/profile` dan melihat data milik Pengguna A.
* **Akar Masalah:**
  1. Di `nuxt.config.ts`, route rules diset secara global:
     ```typescript
     routeRules: {
       '/app/**': { swr: 300, headers: { 'cache-control': 'public, max-age=300' } }
     }
     ```
  2. Header `public` pada `Cache-Control` menginstruksikan intermediate proxy dan CDN edge server Cloudflare untuk menyimpan (*cache*) output HTML renderan pengguna pertama.
  3. SSR render menyertakan data sensitif ke dalam inline JSON payload (`window.__NUXT__`). Saat CDN melayani cached HTML tersebut ke pengguna berikutnya, payload data pengguna pertama ikut terkirim secara utuh.
* **Langkah Mitigasi & Remediasi:**
  1. **Immediate Purge:** Lakukan instant cache purge global di Cloudflare untuk path `/app/*`.
  2. **Header Hardening:** Route yang mengandung data terautentikasi dan spesifik pengguna (`private`) **HARAM** diberi header cache `public` atau SWR Nitro. Ubah aturan route:
     ```typescript
     routeRules: {
       '/app/**': { 
         ssr: true, // atau false untuk SPA mode dashboard
         headers: { 
           'cache-control': 'no-store, no-cache, must-revalidate, private',
           'vary': 'Cookie, Authorization'
         } 
       }
     }
     ```
  3. **Arsitektur Pemisahan State:** Gunakan pola *Shell SSR + Client Fetch* untuk area dashboard: layout dirender server, namun data profil user diambil secara privat via fetch ber-token bearer dari browser klien.

---

### Skenario 3: Penurunan Skor SEO Drastis Akibat Hydration Error & Flash of Unstyled Content (FOUC)
* **Konteks:** Website media berita nasional bermigrasi dari WordPress ke Nuxt 3. Pasca rilis, Google Search Console melaporkan penurunan drastis pada indeks mobile dan Core Web Vitals (skor LCP melonjak ke 4.8 detik dan CLS 0.42).
* **Gejala Teknis:** Mesin crawling Googlebot merekam tampilan kosong (*blank page*) pada beberapa artikel berita, dan console browser user dipenuhi warning: `Hydration completed but contains mismatches.`.
* **Akar Masalah:**
  1. Template komponen menggunakan tag `<ClientOnly>` secara berlebihan hingga membungkus seluruh tag konten artikel berita (`<article>`) karena developer malas menyelesaikan error manipulasi DOM. Akibatnya, server hanya merespons kontainer kosong ke crawler Googlebot.
  2. Terdapat custom CSS framework yang di-load secara asinkronus via script tag dinamis di dalam `onMounted`, memicu pergeseran tata letak radikal (*Cumulative Layout Shift*) saat browser selesai mendownload CSS setelah HTML selesai digambar.
* **Langkah Mitigasi & Remediasi:**
  1. **Restore Konten ke SSR:** Hapus pembungkus `<ClientOnly>` dari elemen konten semantik (`<article>`, `<h1>`, `<p>`). Selesaikan akar hydration error dengan menstandarkan rendering tanggal menggunakan helper terisolasi.
  2. **Zero-FOUC CSS Inlining:** Konfigurasi Vite & Nuxt agar melakukan critical CSS inlining langsung ke dalam `<head>` dokumen HTML melalui konfigurasi:
     ```typescript
     experimental: {
       inlineSSRStyles: true
     }
     ```
  3. **Preconnect & Font Preloading:** Tambahkan directive preconnect dan font display swap pada `nuxt.config.ts` untuk memangkas Largest Contentful Paint (LCP) ke kisaran < 1.2 detik.

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Produksi: "The Zero-Leak, Hardened Nuxt 3 Engine"

Anda ditugaskan sebagai Lead Performance Engineer untuk mengaudit dan merekonstruksi konfigurasi Nuxt 3 enterprise yang tahan beban tinggi, aman dari serangan XSS/injection, bebas dari cross-request pollution, dan memiliki metrik web vitals optimal.

#### Instruksi Pengerjaan:

1. **Konfigurasi `nuxt.config.ts` Tingkat Produksi:**
   Buat konfigurasi lengkap yang mencakup:
   - Route rules hybrid rendering (kombinasi `prerender`, `swr` dengan Redis cache backend, dan `ssr: false` untuk admin portal).
   - Security HTTP headers (HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, dan CSP base).
   - Optimasi bundle build (vite build rollupOptions manual chunks untuk memisahkan vendor libraries besar).

2. **Implementasi Server Middleware Isolasi Sesi (`server/middleware/security.ts`):**
   Buat middleware Nitro yang:
   - Mengekstrak request metadata (IP, User-Agent, Request ID).
   - Memvalidasi token bearer tanpa mencemari global state.
   - Menginjeksi `x-request-id` ke context request dan header response.

3. **Komponen SSR-Safe dengan State Hydration Handshake (`components/ProductCard.vue`):**
   Buat single file component yang:
   - Menampilkan harga dan countdown diskon real-time.
   - Menjamin tidak ada hydration mismatch antara server render dan browser render.
   - Memiliki skeleton loading state fallback yang mulus tanpa CLS.

#### Solusi Referensi Implementasi:

##### 1. File: `nuxt.config.ts`
```typescript
// nuxt.config.ts
export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  
  // Nonaktifkan telemetry di production
  telemetry: false,

  // Optimasi Rendering & Nitro Storage
  nitro: {
    compressPublicAssets: true,
    prerender: {
      crawlLinks: true,
      routes: ['/sitemap.xml', '/robots.txt']
    }
  },

  // Hybrid Route Rules
  routeRules: {
    // 1. Static Pages (Prerendered)
    '/about': { prerender: true },
    '/privacy': { prerender: true },

    // 2. High-Traffic Dynamic Content (SWR Cache)
    '/products/**': { 
      swr: 300, 
      headers: { 'cache-control': 'public, max-age=60, s-maxage=300, stale-while-revalidate=600' } 
    },

    // 3. User Dashboard (SPA Mode, No-Cache)
    '/dashboard/**': { 
      ssr: false, 
      headers: { 'cache-control': 'no-store, no-cache, must-revalidate, private' } 
    },

    // 4. API Endpoints
    '/api/**': { cors: false, headers: { 'x-service-tier': 'enterprise-core' } }
  },

  // Security Headers & Experimental Features
  app: {
    head: {
      htmlAttrs: { lang: 'id' },
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { 'http-equiv': 'X-Content-Type-Options', content: 'nosniff' },
        { 'http-equiv': 'X-Frame-Options', content: 'DENY' },
        { 'http-equiv': 'Referrer-Policy', content: 'strict-origin-when-cross-origin' }
      ]
    }
  },

  experimental: {
    inlineSSRStyles: true,
    payloadExtraction: true,
    renderJsonPayloads: true
  },

  // Vite Optimization
  vite: {
    build: {
      cssCodeSplit: true,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('lodash') || id.includes('date-fns')) {
                return 'utils-vendor'
              }
            }
          }
        }
      }
    }
  }
})
```

##### 2. File: `server/middleware/security.ts`
```typescript
// server/middleware/security.ts
import { defineEventHandler, getHeader, setHeader, createError } from 'h3'
import { randomUUID } from 'node:crypto'

export default defineEventHandler((event) => {
  // 1. Generate atau teruskan Request ID untuk distributed tracing
  const incomingReqId = getHeader(event, 'x-request-id')
  const requestId = incomingReqId || randomUUID()
  
  // Ikat request ID secara strictly scoped ke event context
  event.context.requestId = requestId
  setHeader(event, 'x-request-id', requestId)

  // 2. Proteksi Dasar Security Headers di Level HTTP Server
  setHeader(event, 'X-XSS-Protection', '1; mode=block')
  setHeader(event, 'Permissions-Policy', 'camera=(), microphone=(), geolocation=()')

  // 3. Ekstraksi Context User secara Aman (Tanpa Global Variable)
  const authHeader = getHeader(event, 'authorization')
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.substring(7)
    
    // Simpan token payload ke event.context (aman, terisolasi per HTTP request)
    event.context.auth = {
      rawToken: token,
      isAuthenticated: true
    }
  } else {
    event.context.auth = {
      rawToken: null,
      isAuthenticated: false
    }
  }
})
```

##### 3. File: `components/ProductCard.vue`
```vue
<!-- components/ProductCard.vue -->
<template>
  <div class="product-card">
    <div class="thumbnail-wrapper">
      <img 
        :src="product.thumbnail" 
        :alt="product.name"
        loading="lazy"
        width="300"
        height="200"
      />
    </div>
    
    <div class="content">
      <h3 class="title">{{ product.name }}</h3>
      <p class="price">{{ formattedPrice }}</p>

      <!-- ClientOnly untuk countdown waktu dinamis agar terhindar dari Hydration Mismatch -->
      <ClientOnly>
        <template #fallback>
          <div class="countdown-placeholder">
            <span>Memuat promo spesial...</span>
          </div>
        </template>
        <div v-if="timeLeft > 0" class="countdown-badge">
          Flash Sale Berakhir: {{ formattedTimeLeft }}
        </div>
        <div v-else class="promo-ended">
          Promo Reguler Telah Berakhir
        </div>
      </ClientOnly>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'

interface Product {
  id: string
  name: string
  price: number
  thumbnail: string
  promoExpiresAt: number // Timestamp UTC
}

const props = defineProps<{
  product: Product
}>()

// 1. Format harga konsisten antara server dan browser
const formattedPrice = computed(() => {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0
  }).format(props.product.price)
})

// 2. Reactive client-side timer handling
const timeLeft = ref<number>(0)
let timer: ReturnType<typeof setInterval> | null = null

const calculateTimeLeft = () => {
  const diff = Math.max(0, Math.floor((props.product.promoExpiresAt - Date.now()) / 1000))
  timeLeft.value = diff
}

const formattedTimeLeft = computed(() => {
  const m = Math.floor(timeLeft.value / 60)
  const s = timeLeft.value % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
})

// Lifecycle Teardown Aman (Hanya berjalan di client)
onMounted(() => {
  calculateTimeLeft()
  timer = setInterval(calculateTimeLeft, 1000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.product-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.thumbnail-wrapper img {
  width: 100%;
  height: auto;
  aspect-ratio: 3 / 2;
  object-fit: cover;
}
.content {
  padding: 16px;
}
.price {
  font-weight: 700;
  color: #059669;
}
.countdown-badge {
  background-color: #fef2f2;
  color: #dc2626;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.875rem;
  margin-top: 8px;
}
.countdown-placeholder {
  min-height: 29px; /* Mencegah layout shift (CLS) saat hidrasi */
  color: #94a3b8;
  font-size: 0.875rem;
  margin-top: 8px;
}
</style>
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Tandai `[x]` jika Anda telah menguasai konsep berikut secara teoritis dan praktis:

- [ ] **State Isolation:** Memahami bahaya shared state/variable di root scope file Nuxt server dan selalu menggunakan `useState()` atau Pinia factory per-request.
- [ ] **Hydration Diagnostics:** Mampu mengidentifikasi, mereproduksi, dan menyelesaikan error *Hydration mismatch* menggunakan DevTools serta teknik `<ClientOnly>` dan lifecycle segregation.
- [ ] **Nitro Route Rules:** Mampu merancang strategi hybrid rendering (kombinasi `prerender`, `swr`, `isr`, `ssr: false`) sesuai karakteristik data dan beban traffic.
- [ ] **Data Fetching Pattern:** Mampu membedakan kapan menggunakan `useFetch`, `useAsyncData`, `$fetch`, serta menghindari *duplicate fetch waterfall* di SSR.
- [ ] **Memory Leak Profiling:** Mengetahui cara mengambil V8 Heap Snapshot pada proses Node.js Nuxt dan melacak retained references pada event listeners dan timer.
- [ ] **Security Headers:** Memahami implementasi CSP (Content Security Policy) dengan Nonce, HSTS, X-Frame-Options, dan CORS di level konfigurasi Nitro.
- [ ] **Container Lifecycle:** Memahami penanganan sinyal POSIX (`SIGTERM`), arsitektur init process PID 1, dan orkestrasi graceful shutdown pada Docker/Kubernetes.
- [ ] **Core Web Vitals Optimization:** Mampu mengoptimasi TTFB (< 200ms), LCP (< 2.5s), dan CLS (< 0.1) pada arsitektur SSR modern.
