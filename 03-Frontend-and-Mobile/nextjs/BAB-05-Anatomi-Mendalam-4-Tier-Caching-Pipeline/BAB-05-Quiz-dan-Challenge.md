# BAB 05: Quiz, Challenge, & Knowledge Check
**Anatomi Mendalam 4-Tier Caching Pipeline**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Request Memoization vs. Data Cache:**  
   Jelaskan perbedaan fundamental antara *Request Memoization* (React component-level cache) dan *Data Cache* (Next.js server-level cache) dari perspektif *lifecycle*, media penyimpanan (*storage engine*), serta cakupan isolasi antarpengguna (*cross-request sharing*). Mengapa `fetch` yang sama dieksekusi hanya sekali dalam satu *render tree pass*, tetapi dapat bertahan berminggu-minggu melintasi ribuan pengguna yang berbeda?

2. **Dekomposisi Full Route Cache:**  
   Dalam konteks *Full Route Cache*, Next.js menyimpan dua artefak utama saat *build time* atau *ISR revalidation*: HTML statis dan *React Server Component (RSC) Payload*. Analisis bagaimana browser mengonsumsi kedua artefak ini secara berurutan saat *initial hard navigation* versus *soft client-side navigation*, dan jelaskan mengapa HTML saja tidak cukup untuk arsitektur App Router.

3. **Mekanisme Router Cache pada Sisi Klien:**  
   Bagaimana *Router Cache* (in-memory RSC payload cache pada browser) menentukan masa kedaluwarsa segmen rute (*stale time*) secara default untuk *Static Routes* vs. *Dynamic Routes*? Bagaimana pemanggilan `router.refresh()` secara internal berinteraksi dengan *Router Cache* tanpa memicu *full page reload*?

4. **Kaskade Invalidation dari Dynamic Functions:**  
   Sebutkan apa saja yang diklasifikasikan sebagai *Dynamic Functions* di Next.js (`cookies()`, `headers()`, `searchParams`). Jelaskan bagaimana deteksi fungsi-fungsi ini di dalam *Server Component* secara otomatis menurunkan status rute dari statis menjadi dinamis, serta jelaskan dampaknya terhadap *Full Route Cache* dan *Data Cache*.

5. **Tag-based Revalidation vs. Path-based Revalidation:**  
   Secara arsitektural, apa perbedaan antara `revalidateTag('tag-name')` dan `revalidatePath('/path-name')` dalam hal *invalidation boundary*? Bagaimana mutasi cache ini merambat dari server (*Data Cache* dan *Full Route Cache*) ke browser yang sedang aktif (*Router Cache*)?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Bypassing Request Memoization Secara Tidak Disengaja:**  
   Perhatikan skenario di mana dua *Server Component* memanggil endpoint API yang identik menggunakan `fetch('https://api.internal/data')`. Mengapa penambahan konfigurasi `signal: new AbortController().signal` pada masing-masing pemanggilan `fetch` menggagalkan mekanisme *Request Memoization*? Jelaskan bagaimana *hash key generation* internal Next.js/React bekerja untuk mendeteksi *duplicate requests*.

2. **Race Condition pada Data Cache di Lingkungan Multi-Instance / Serverless:**  
   Jika aplikasi Next.js Anda berjalan di lingkungan multi-region containerized (misal: 10 pod Kubernetes di balik load balancer) tanpa implementasi `incrementalCacheHandlerPath` kustom (menggunakan filesystem default), jelaskan kegagalan konsistensi data yang terjadi saat `revalidateTag()` dipanggil pada salah satu pod. Bagaimana strategi *distributed cache synchronization* yang benar untuk memitigasi anomali ini?

3. **Interaksi Antara `fetchCache = 'force-no-store'` dan Segment Config:**  
   Jika sebuah *layout* menetapkan `export const fetchCache = 'force-no-store'`, namun salah satu *leaf page* di bawahnya mencoba melakukan `fetch(..., { next: { revalidate: 3600 } })`, konfigurasi mana yang menang? Bedah hierarki resolusi konfigurasi *Route Segment Config* Next.js saat terjadi konflik eksplisit antara *parent* dan *child*.

4. **Anatomi Internal Mutasi Server Actions Terhadap 4-Tier Pipeline:**  
   Ketika sebuah *Server Action* dieksekusi dari sisi klien dan memanggil `revalidatePath('/dashboard')`, deskripsikan siklus transmisi HTTP yang terjadi. Bagaimana respons dari *Server Action* memuat data mutasi sekaligus RSC Payload terbaru, dan bagaimana *Router Cache* pada klien mengintegrasikannya tanpa merusak *local state* komponen klien yang tidak terafektif?

5. **Router Cache Memory Bloat & Mitigation:**  
   Pada aplikasi *Single Page Application* berskala enterprise dengan ratusan segmen rute yang di-*prefetch* secara agresif melalui komponen `<Link>`, analisis potensi terjadinya kebocoran memori (*memory leak*) atau lonjakan RAM pada browser klien (*Router Cache*). Bagaimana Anda mengontrol dan membatasi perilaku *prefetching* (`prefetch={false}`, viewport-based prefetch) untuk rute data-intensif?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Thundering Herd pada Flash Sale E-Commerce
Platform e-commerce dengan trafik 80.000 RPS mengalami *downtime* kritis saat peluncuran *flash sale*. Produk utama menggunakan *Incremental Static Regeneration* (ISR) dengan `revalidate: 60`. Tepat pada detik ke-60 saat *cache entry* masuk status *stale*, terjadi lonjakan ratusan ribu request bersamaan. Alih-alih melayani *stale content* dan melakukan satu *background regeneration*, downstream database mengalami kelebihan beban hingga *connection pool* habis (*pool starvation*), memicu HTTP 500 kaskade ke seluruh kluster.
* **Pertanyaan Diagnostik:**  
  1. Mengapa mekanisme *Stale-While-Revalidate* default Next.js gagal mengisolasi lonjakan request (*thundering herd / cache stampede*) ke downstream database pada skala ini?
  2. Bagaimana modifikasi arsitektur caching yang harus diimplementasikan—baik di level *custom cache-handler* maupun layer Reverse Proxy/CDN—untuk memastikan prinsip *mutex/single-flight regeneration* terpenuhi?

### Skenario B: Kebocoran Data Antar-Tenant (Data Bleed) Akibat Kesalahan Caching
Sebuah aplikasi multi-tenant B2B SaaS menampilkan *dashboard analytics* perusahaan. Pengembang mengoptimasi query database analitik yang lambat dengan membungkusnya menggunakan `unstable_cache` dari `next/cache`:
```typescript
const getAnalytics = unstable_cache(
  async (tenantId: string) => fetchTenantMetrics(tenantId),
  ['analytics-data'],
  { revalidate: 300 }
);
```
Pengguna dari Perusahaan A melaporkan bahwa mereka sesekali melihat data rahasia milik Perusahaan B di dashboard mereka setelah melakukan refresh.
* **Pertanyaan Diagnostik:**  
  1. Tunjukkan kecacatan fatal pada pendefinisian *cache key* di kode `unstable_cache` di atas yang menyebabkan *cache cross-contamination* antar-tenant.
  2. Tuliskan implementasi perbaikan yang benar dengan mempertimbangkan *key parts*, *tags*, dan batas keamanan isolasi tenant.

### Skenario C: Dual-World Dilemma: Personalisasi vs. Global Edge Caching
Aplikasi portal berita global ingin mengimplementasikan caching statis di Edge CDN (*Full Route Cache* via ISR) untuk meminimalkan *Time to First Byte* (TTFB < 50ms di seluruh dunia). Namun, pada bagian *header*, terdapat status profil pengguna (avatar, status langganan premium, dan notifikasi belum dibaca) yang unik per pengguna dan dikontrol via cookie otentikasi JWT. Membaca cookie secara langsung di Server Component menyebabkan rute menjadi dinamis secara keseluruhan, melonjakkan TTFB menjadi 450ms dan membebani server backend.
* **Pertanyaan Diagnostik:**  
  1. Mengapa pendekatan *Server-Side Dynamic Rendering* secara penuh untuk kasus ini dianggap sebagai *architectural anti-pattern*?
  2. Rancang arsitektur hybrid yang memisahkan konten publik yang dapat di-*cache* secara agresif di *Full Route Cache* dengan konten privat berbasis pengguna, menggunakan kombinasi *Parallel Routes*, React `Suspense`, dan *Client-side fetching/Dynamic IO*.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Enterprise-Grade Distributed Cache Handler & Observability Profiler
**Problem Statement:**  
Default file-system *Data Cache* Next.js tidak memadai untuk produksi skala horizontal (*multi-container/serverless deployment*). Ketidaksinkronan data antar-pod, hilangnya cache saat *rolling restart*, serta ketiadaan visibilitas status cache (*HIT/MISS/STALE*) mempersulit debugging kinerja aplikasi.

**Requirements:**
1. **Custom Distributed Cache Engine:**
   * Implementasikan antarmuka `CacheHandler` kustom Next.js (menggunakan Redis / Valkey sebagai shared store).
   * Dukung operasi `get`, `set`, dan `revalidateTag`.
   * Implementasikan skema penanganan *Cache Stampede* menggunakan algoritma *distributed locking* (misal: Redlock atau probabilistic early expiration/XFetch).
2. **HTTP Telemetry & Observability Injection:**
   * Sisipkan custom response headers pada setiap respons:
     * `X-Next-Data-Cache: HIT | MISS | STALE | BYPASS`
     * `X-Next-Route-Cache: HIT | MISS`
     * `X-Execution-Latency: [time in ms]`
   * Buat audit logger terpusat yang mencatat setiap operasi invalidasi via `revalidatePath` atau `revalidateTag` dengan menyertakan metadata IP pemanggil, target tag, dan durasi propagasi.
3. **Deterministic Testing Suite:**
   * Buat satu skrip pengujian berbasis Node.js/k6 untuk membuktikan bahwa ketika 500 request paralel meminta data yang berstatus *stale*, sistem upstream/database **hanya menerima tepat 1 kali pemanggilan query**, sementara 499 request lainnya secara instan menerima *stale data* hingga cache selesai diperbarui.

**Constraints:**
* Wajib kompatibel dengan Next.js App Router (versi 14.x / 15.x).
* Runtime: Node.js (bukan Edge-only).
* Zero deployment downtime: handler harus menangani *graceful fallback* ke in-memory cache jika koneksi Redis terputus sementara.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup dan perbedaan ruang lingkup isolasi antara *Request Memoization*, *Data Cache*, *Full Route Cache*, dan *Router Cache*.
- [ ] Kriteria persis yang memicu *Route De-opt* dari Statis ke Dinamis (penggunaan `cookies()`, `headers()`, dynamic route parameters, dan parameter `searchParams`).
- [ ] Mekanisme internal `revalidatePath` vs `revalidateTag` dan pengaruhnya terhadap *Data Cache* dan *Full Route Cache*.
- [ ] Dampak pemilihan nilai `fetch` cache options (`force-cache`, `no-store`, `{ next: { revalidate, tags } }`).
- [ ] Bagaimana Server Actions berkoordinasi secara atomik untuk memutasi data, memicu invalidasi, dan memperbarui *Router Cache* klien dalam satu *network round-trip*.
- [ ] Alur serialisasi dan deserialisasi *RSC Payload* serta cara *Router Cache* memvalidasi status *freshness* segmen berbasis *staleTime*.

### Saya tidak perlu menghafal:
- [ ] Format biner/teks internal mentah dari protokol *React Server Component Payload*.
- [ ] Angka pasti alokasi limit ukuran memori internal *Router Cache* di berbagai versi browser yang berbeda.
- [ ] Hash algorithm internal yang digunakan oleh bundler Webpack/Turbopack untuk menghasilkan ID unik fungsi server-side.

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi `incrementalCacheHandlerPath` kustom untuk mengintegrasikan Redis/memcached sebagai *distributed Data Cache*.
- [ ] Mendiagnosis penyebab rute yang seharusnya statis menjadi dinamis menggunakan build output analyzer (`next build`).
- [ ] Mengimplementasikan *fine-grained caching* menggunakan kombinasi `unstable_cache`, React `cache()`, dan tag invalidation.
- [ ] Mengisolasi komponen privat pengguna di dalam boundary `Suspense` agar tidak merusak *Full Route Cache* pada halaman statis publik.
- [ ] Mengontrol dan mengaudit perilaku *Router Cache* pada klien untuk mencegah *stale data view* pasca navigasi kompleks tanpa membebani bandwidth jaringan.