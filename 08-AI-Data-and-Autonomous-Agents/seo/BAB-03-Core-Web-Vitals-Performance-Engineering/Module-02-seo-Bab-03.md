# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Topik: SEO Rekayasa Tingkat Tinggi (Kategori: 08-AI-Data-and-Autonomous-Agents)
### BAB 03: Core Web Vitals & Performance Engineering
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta didik pada tingkat Staff/Principal Engineer diharapkan mampu:
- **Menganalisis dan Membedah Siklus Hidup Rendering Chromium**: Memahami secara deterministik bagaimana Blink Engine mengeksekusi tahapan *Parse*, *Style*, *Layout*, *Pre-Paint*, *Paint*, dan *Composite* serta korelasinya terhadap metrik Core Web Vitals (CWV).
- **Mendiagnosis dan Mengoptimasi LCP (Largest Contentful Paint) End-to-End**: Mengurangi empat sub-bagian LCP (*Time to First Byte*, *Resource Load Delay*, *Resource Load Duration*, *Element Render Delay*) hingga mencapai p75 < 1.8 detik pada skala jutaan URL.
- **Mengeliminasi Hambatan Interaktivitas Menuju INP (Interaction to Next Paint) Sub-200ms**: Mengidentifikasi *long tasks*, memecah eksekusi *Main Thread* menggunakan *Cooperative Scheduling* (`scheduler.yield()`, `requestIdleCallback`), dan mengisolasi komponen lambat menggunakan arsitektur Web Workers.
- **Mencegah Cumulative Layout Shift (CLS) Dinamis**: Mengendalikan *Layout Instability Engine*, mengeliminasi pergeseran akibat Web Fonts (FOUT/FOFO) menggunakan *Font Metrics Overrides*, dan mendesain slot injeksi asinkron (iklan/widget) tanpa *layout thrashing*.
- **Merancang Arsitektur Observabilitas RUM (Real User Monitoring)**: Mengimplementasikan *pipeline telemetry* performa berbasis *Navigation Timing API v2*, *PerformanceObserver*, dan *Attribution Build* untuk diekspor ke platform analitik/OLAP (*ClickHouse*, *BigQuery*).
- **Mengintegrasikan Performance Budget ke dalam CI/CD**: Memblokir regresi CWV sebelum rilis produksi melalui automated synthetic profiling dan validasi bot/crawler rendering budget.

---

### 2. Prerequisites

Peserta didik wajib memiliki pemahaman mendalam pada:
- **Arsitektur Browser**: Siklus hidup Event Loop (Microtasks, Macrotasks, Animation Frame Callbacks), perbedaan antara *Main Thread*, *Compositor Thread*, dan *Raster Thread*.
- **Protokol Jaringan & HTTP**: HTTP/2 multiplexing, HTTP/3 QUIC, TLS 1.3 0-RTT, Priority Hints, Cache-Control headers, dan mekanika 103 Early Hints.
- **Framework Frontend & SSR/Streaming**: React 18/Next.js App Router (Streaming SSR, Server Components), hydration mismatch mechanics, atau framework sejenis (Nuxt/SvelteKit).
- **Dasar SEO Teknis**: Mekanisme Googlebot Web Rendering Service (WRS), render-budget constraints, dan integrasi Search Console Core Web Vitals report.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Chromium Rendering Engine Internals & Pipeline Stages

Untuk mengoptimasi CWV secara presisi, *engineer* harus memahami alur konversi dari *bytes* jaringan ke piksel visual pada Chromium:

```
Network (Raw Bytes)
   │
   ▼
[HTML Parser] ──(Tokens)──► [DOM Tree]
                                 │
[CSS Parser]  ──(Tokens)──► [CSSOM Tree]
                                 │
                                 ▼
                          [Render/Style Tree]
                                 │
                                 ▼
                          [Layout Engine] (Geometry, X/Y, Width/Height)
                                 │
                                 ▼
                         [Pre-Paint (Property Trees)]
                                 │
                                 ▼
                          [Paint Engine] (Display Item Lists)
                                 │
                    ─────────────────────────── IPC Boundary
                                 │
                                 ▼
                     [Compositor Thread] (Tiling)
                                 │
                                 ▼
                     [Raster Thread (GPU)] (Bitmaps generated)
                                 │
                                 ▼
                            [Screen Display]
```

1. **DOM & CSSOM Construction**: Parsing HTML menghasilkan DOM. Saat menemukan tag `<link rel="stylesheet">` atau `<script>` sinkron, parser terblokir (*parser-blocking*). CSSOM harus selesai sebelum JavaScript sinkron dapat dieksekusi, karena JS dapat membaca struktur komputasi gaya (`window.getComputedStyle`).
2. **Style Resolution**: Menggabungkan DOM dan CSSOM untuk menghitung gaya akhir (*Computed Styles*) untuk setiap elemen visual.
3. **Layout (Reflow)**: Menentukan geometri visual (posisi dan ukuran). Ini adalah operasi mahal berorientasi pohon rekursif. Membaca dimensi DOM (`offsetHeight`, `getBoundingClientRect()`) langsung setelah mutasi gaya memicu *Forced Synchronous Layout* (Layout Thrashing).
4. **Pre-Paint**: Membangun *Property Trees* (Transform, Clip, Effect, Scroll). Ini memisahkan mutasi visual berbasis GPU (seperti CSS `transform` dan `opacity`) dari mutasi struktural.
5. **Paint**: Menghasilkan *Display Item Lists* (instruksi gambar: "gambar persegi panjang di X,Y", "tulis teks font Z"). Tidak menghasilkan piksel aktual di sini.
6. **Compositing & Rasterization**: *Compositor Thread* mengambil display items, membaginya menjadi layer-layer terpisah, lalu memecahnya menjadi petak-petak (*tiles*). Petak-petak ini dikirimkan ke *Raster Threads* yang didukung GPU untuk diubah menjadi *bitmap*, lalu digabungkan menjadi satu frame visual di layar.

#### 3.2 Metrik Kunci: Dekonstruksi & Analisis Sub-Bagian

##### Largest Contentful Paint (LCP)
LCP menandai titik ketika konten utama halaman kemungkinan telah dirender. Formula dekonstruksi matematis LCP:

$$\text{LCP} = \text{TTFB} + \text{Resource Load Delay} + \text{Resource Load Duration} + \text{Element Render Delay}$$

- **TTFB (Time to First Byte)**: Waktu dari inisiasi navigasi hingga byte pertama dokumen HTML tiba. Dipengaruhi oleh DNS, TLS, jarak geografis CDN, dan waktu eksekusi server rendering.
- **Resource Load Delay**: Delta waktu antara tibanya HTML awal dan saat browser mulai mendownload aset kandidat LCP. Target optimal: **0 ms**.
- **Resource Load Duration**: Durasi transfer download aset LCP. Bergantung pada ukuran payload kompresi (AVIF/WebP), prioritasi HTTP/2/3, dan alokasi bandwidth.
- **Element Render Delay**: Waktu dari selesainya transfer aset LCP hingga elemen tersebut benar-benar digambar di layar oleh GPU. Dipengaruhi oleh CSS yang memblokir rendering, JavaScript CPU-bound hydration, dan *main-thread saturation*.

##### Interaction to Next Paint (INP)
Menggantikan FID (First Input Delay), INP mengukur responsivitas halaman secara holistik sepanjang siklus hidup sesi pengguna terhadap interaksi klik, tap, dan keyboard. INP dihitung dari interaksi terburuk (persentil 98 untuk sesi dengan interaksi tinggi):

$$\text{INP} = \text{Input Delay} + \text{Processing Duration} + \text{Presentation Delay}$$

```
User Action (Click/Key)
   │
   ├─► [Input Delay] ────────► Menunggu Main Thread bebas dari task lain
   │
   ├─► [Processing Duration] ─► Eksekusi JS Event Handlers (click, change, dll.)
   │
   └─► [Presentation Delay] ──► Recalculate Style, Layout, Paint, Compositing & Frame Display
```

- **Input Delay**: Waktu tunggu antrean sebelum event handler mulai dieksekusi. Disebabkan oleh *Long Tasks* (>50ms) yang sedang berjalan di *Main Thread*.
- **Processing Duration**: Waktu total yang dihabiskan untuk menjalankan callback JavaScript terdaftar.
- **Presentation Delay**: Waktu yang dibutuhkan browser untuk menghitung ulang layout, melukis frame baru, dan mengirimkannya ke *compositor surface*.

##### Cumulative Layout Shift (CLS)
Mengukur stabilitas visual. Dihitung per frame dalam *session window* (maksimum 5 detik durasi per window, jeda 1 detik jika tidak ada pergeseran):

$$\text{Layout Shift Score} = \text{Impact Fraction} \times \text{Distance Fraction}$$

- **Impact Fraction**: Persentase area *viewport* yang terdampak oleh pergeseran elemen tidak stabil antar dua frame.
- **Distance Fraction**: Jarak terbesar pergeseran elemen yang tidak stabil dibagi dengan dimensi terbesar viewport (lebar atau tinggi).

---

### 4. Why & What

#### Mengapa CWV Sangat Krusial untuk SEO Modern
1. **Google Ranking Factor (Page Experience Signal)**: Sejak peluncuran Page Experience Update, CWV dievaluasi langsung menggunakan data CrUX (Chrome User Experience Report) pada level URL dan Origin. URL yang gagal memenuhi batas p75 "Good" akan mengalami penurunan bobot kompetitif pada kueri organik bernilai komersial tinggi.
2. **Crawl Budget & Rendering Efficiency**: Googlebot menggunakan alokasi daya komputasi terbatas untuk mengeksekusi WRS. Halaman dengan eksekusi *Main Thread* intensif (skrip berat, lambat render) dide-prioritaskan dalam antrean *render queue*, menyebabkan penundaan pengindeksan (*indexing lag*) untuk konten dinamis.
3. **Konversi E-Commerce vs Bounce Rate**: Data analitik industri membuktikan peningkatan LCP sebesar 100ms dapat menurunkan tingkat konversi sebesar 1.3%. INP yang buruk langsung merusak rasio *Add-to-Cart* karena UI tampak "membeku" saat pengguna menekan tombol transaksi.

#### Apa yang Harus Diubah Secara Arsitektural
Beralih dari optimasi reaktif/kosmetik (seperti sekadar mengecilkan gambar) menuju **Rekayasa Kinerja Arsitektur**:
- Mengubah SSR monolitik menjadi **Streaming SSR dengan Out-of-Order Hydration**.
- Menerapkan **Fetch Priority & Resource Hints Deterministic Engine**.
- Mengadopsi **Main-Thread Offloading Strategy** menggunakan Worker Threads.
- Menstandarkan sistem pemuatan font ke **Zero-CLS Font Loading Pipeline**.

---

### 5. How (Workflow Detail)

Alur kerja rekayasa performa CWV kelas enterprise:

```
[Tahap 1: Diagnostic]
   ├── Analisis CrUX API (Field Data p75 Origin/URL)
   └── Automated Lighthouse / WebPageTest Profile (Lab Data)
         │
         ▼
[Tahap 2: Bottleneck Identification]
   ├── Long Animation Frames (LoAF) API Profiling -> Identifikasi INP
   ├── Chrome DevTools Performance Trace -> Identifikasi Main Thread Contention
   └── Layout Instability Shift Trace -> Tangkap Node CLS
         │
         ▼
[Tahap 3: Architectural Remediation]
   ├── Edge Compute: 103 Early Hints, Dynamic Brotli/Zstandard Compression
   ├── Rendering: Split hydration, Server Components, Partial Prerendering
   └── Scheduling: scheduler.yield() & Priority Task Scheduling
         │
         ▼
[Tahap 4: Synthetic Guardrails in CI/CD]
   ├── GitHub Actions / GitLab CI menjalankan Lighthouse CI / Playwright Profiler
   └── Fail build jika Performance Budget terlampaui
         │
         ▼
[Tahap 5: Production Observability (RUM)]
   ├── Injeksi lightweight web-vitals RUM tracker
   └── Real-time anomaly alerting via ClickHouse / Datadog
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Restoran Bintang Lima Berkecepatan Tinggi
- **LCP (Hidangan Pembuka Utama Tiba)**: Pengunjung tidak peduli kapan seluruh bumbu selesai dihitung di dapur; mereka menilai kecepatan restoran dari seberapa cepat hidangan utama pertama disajikan di atas meja. Jika piring sudah diantar tapi pelayan menahan garpu (Element Render Delay), pengunjung tetap frustrasi.
- **INP (Responsivitas Pelayan)**: Pengunjung memanggil pelayan untuk meminta air. Jika pelayan sedang sibuk mencuci tumpukan piring kotor tanpa henti (*Long Task*), pengunjung harus menunggu lama sebelum pelayan menoleh (*Input Delay*), mencatat permintaan (*Processing*), dan menuangkan air (*Presentation Delay*). Pelayan yang baik akan melayani panggilan sebentar (*scheduler.yield()*), menuang air, lalu kembali mencuci piring.
- **CLS (Kestabilan Meja Makanan)**: Anda hendak menusukkan garpu ke steak, namun tiba-tiba meja digeser 10 cm ke samping karena pelayan lain baru saja menyisipkan vas bunga tambahan di tengah meja. Anda menusuk taplak meja kosong.

#### Diagram Interaksi INP vs LoAF (Long Animation Frames)

```
Target Frame Budget: 16.6ms (60 FPS)
─────────────────────────────────────────────────────────────────────────────
KONDISI BURUK (INP Tinggi / Frame Drop):
Main Thread: [------------------ Long Task: 180ms -----------------] [Render]
User Input:          ▲ (Click terjadi di sini)
                     │
                     └──► Input Delay: 120ms ──► Processing: 60ms ──► Pres: 15ms
                     Total INP = 195ms (Jelek, UI terasa beku)

─────────────────────────────────────────────────────────────────────────────
KONDISI OPTIMAL (Cooperative Scheduling via scheduler.yield()):
Main Thread: [--Task 1: 30ms--] ──yield──► [Input Handler: 8ms] ──yield──► [--Task 2: 25ms--]
User Input:           ▲ (Click)
                      │
                      └──► Input Delay: 5ms ──► Processing: 8ms ──► Pres: 8ms
                      Total INP = 21ms (Mulus / 60fps tercapai)
```

---

### 7. Implementation: Simple vs Practical Enterprise Code

#### 7.1 LCP Optimization: Edge Resource Hints & Deterministic Preloading

##### Pendekatan Naif (Buruk)
Mengandalkan browser scanner tanpa prioritas atau menggunakan lazy-loading pada LCP element.

```html
<!-- BURUK: Browser tidak tahu gambar ini adalah LCP, ditambah lazy-loading menunda fetch hingga DOM selesai dievaluasi -->
<img src="/hero-banner.jpg" loading="lazy" class="w-full">
```

##### Pendekatan Enterprise (Standar Industri)
Menginjeksi prioritas tingkat kernel/parser, mengoptimasi preload pada HTTP headers, dan memadukan format modern (AVIF) dengan fallback otomatis serta decoding asinkron.

```html
<!-- Ditempatkan sedini mungkin di dalam <head> dokumen HTML -->
<link rel="preload" 
      fetchpriority="high" 
      as="image" 
      type="image/avif" 
      href="https://cdn.enterprise.com/assets/hero-banner-1200.avif" 
      imagesrcset="https://cdn.enterprise.com/assets/hero-banner-600.avif 600w, 
                  https://cdn.enterprise.com/assets/hero-banner-1200.avif 1200w"
      imagesizes="(max-width: 768px) 100vw, 1200px">
```

Implementasi Edge Engine (Cloudflare Workers / Fastly Compute@Edge) untuk menginjeksi header `103 Early Hints` dan `Link` header:

```typescript
// edge-worker.ts
export default {
  async fetch(request: Request, env: any, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Kirim 103 Early Hints sebelum origin rendering selesai
    if (url.pathname === "/") {
      const earlyHintsHeader = new Headers();
      earlyHintsHeader.append(
        "Link",
        "</assets/hero-banner-1200.avif>; rel=preload; as=image; fetchpriority=high; type=image/avif"
      );
      earlyHintsHeader.append(
        "Link",
        "</css/critical.css>; rel=preload; as=style"
      );
      
      // Kirim info early hints jika runtime platform mendukung Informational Response
      // @ts-ignore
      if (typeof ctx.waitUntilEarlyHints === "function") {
        // @ts-ignore
        ctx.waitUntilEarlyHints(earlyHintsHeader);
      }
    }

    const response = await fetch(request);
    const newHeaders = new Headers(response.headers);
    
    // Terapkan caching deterministik dan security context
    newHeaders.set("Timing-Allow-Origin", "*");
    newHeaders.set("Server-Timing", `cdn-cache;desc="HIT", edge-time;dur=1.2`);

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  }
};
```

Markup Gambar LCP di Template HTML:

```html
<picture>
  <source type="image/avif" srcset="/assets/hero-banner-600.avif 600w, /assets/hero-banner-1200.avif 1200w" sizes="(max-width: 768px) 100vw, 1200px">
  <source type="image/webp" srcset="/assets/hero-banner-600.webp 600w, /assets/hero-banner-1200.webp 1200w" sizes="(max-width: 768px) 100vw, 1200px">
  <img src="/assets/hero-banner-1200.jpg" 
       alt="Enterprise Platform Hero Architecture"
       width="1200" 
       height="600" 
       fetchpriority="high"
       loading="eager"
       decoding="async"
       class="hero-img-responsive">
</picture>
```

#### 7.2 INP Optimization: Cooperative Scheduling via `scheduler.yield()`

##### Masalah: Eksekusi Event Handler Memblokir Thread (Input Lag)
```typescript
// BURUK: Menyaring 50.000 item dalam satu synchronous long-task (Memblokir Main Thread 250ms)
function handleFilterChange(query: string) {
  const filtered = heavyDataProcessing(largeDataSet, query);
  updateDOMTree(filtered); // Presentation Delay bengkak
}
```

##### Solusi Produksi: Polyfilled `scheduler.yield()` dengan Abort Signal & Task Chunking
```typescript
// scheduler-engine.ts
export class CooperativeScheduler {
  /**
   * Menyerahkan eksekusi kembali ke browser agar frame paint / user input dapat ditangani
   */
  public static async yieldToMain(): Promise<void> {
    // 1. Cek ketersediaan Scheduler API native (Chrome 115+)
    if ("scheduler" in window && "yield" in (window as any).scheduler) {
      return (window as any).scheduler.yield();
    }

    // 2. Fallback MessageChannel (Lebih presisi dari setTimeout 0 yang memiliki clamping 4ms)
    return new Promise((resolve) => {
      const channel = new MessageChannel();
      channel.port1.onmessage = () => resolve();
      channel.port2.postMessage(null);
    });
  }

  /**
   * Memproses array masif tanpa memicu Long Task (>50ms)
   */
  public static async processInChunks<T, R>(
    items: T[],
    processor: (item: T) => R,
    deadlineMs: number = 16
  ): Promise<R[]> {
    const results: R[] = [];
    let lastYield = performance.now();

    for (let i = 0; i < items.length; i++) {
      results.push(processor(items[i]));

      // Evaluasi apakah frame budget 16ms telah terlampaui
      if (performance.now() - lastYield > deadlineMs) {
        await CooperativeScheduler.yieldToMain();
        lastYield = performance.now();
      }
    }

    return results;
  }
}
```

Implementasi Penggunaan pada UI Filter Component:

```typescript
// search-controller.ts
import { CooperativeScheduler } from './scheduler-engine';

const searchInput = document.getElementById('search-input') as HTMLInputElement;
const resultsContainer = document.getElementById('results-view') as HTMLDivElement;

let currentAbortController: AbortController | null = null;

searchInput.addEventListener('input', async (e: Event) => {
  // Batalkan pekerjaan sebelumnya jika input baru masuk
  if (currentAbortController) {
    currentAbortController.abort();
  }
  
  currentAbortController = new AbortController();
  const { signal } = currentAbortController;
  const query = (e.target as HTMLInputElement).value;

  try {
    // Serahkan thread langsung agar user keystroke langsung ter-paint di input field (Menjaga INP < 50ms)
    await CooperativeScheduler.yieldToMain();
    
    if (signal.aborted) return;

    // Eksekusi pemrosesan data secara chunked
    const filteredDataset = await CooperativeScheduler.processInChunks(
      globalDataset,
      (item) => item.title.toLowerCase().includes(query.toLowerCase()) ? item : null,
      12 // Budget 12ms agar sisa 4ms digunakan browser untuk render
    );

    if (signal.aborted) return;

    // Update DOM secara bertahap menggunakan DocumentFragment
    await CooperativeScheduler.yieldToMain();
    renderDOMFragment(filteredDataset.filter(Boolean), resultsContainer);

  } catch (err: any) {
    if (err.name !== 'AbortError') {
      console.error('Render failure:', err);
    }
  }
});

function renderDOMFragment(items: any[], container: HTMLElement) {
  const fragment = document.createDocumentFragment();
  items.slice(0, 100).forEach((item) => {
    const el = document.createElement('div');
    el.className = 'search-row';
    el.textContent = item.title;
    fragment.appendChild(el);
  });
  container.innerHTML = '';
  container.appendChild(fragment);
}
```

#### 7.3 CLS Prevention: Zero-Shift Font Loading Architecture & Fluid Media

##### CSS Font Metrics Override (Mencegah Pergeseran Saat Web Font Selesai Dimuat)
```css
/* Definisikan Fallback Font lokal dengan metrik yang dimodifikasi */
@font-face {
  font-family: 'Inter-Fallback';
  src: local('Arial');
  /* Kalibrasi metrik agar identik dengan font 'Inter' */
  ascent-override: 90.49%;
  descent-override: 22.56%;
  line-gap-override: 0.00%;
  size-adjust: 107.40%;
}

/* Deklarasi Web Font Utama */
@font-face {
  font-family: 'Inter';
  src: url('/fonts/inter-latin.woff2') format('woff2');
  font-display: swap;
  font-weight: 400;
}

:root {
  /* Saat 'Inter' belum siap, gunakan 'Inter-Fallback' yang dimensinya identik */
  font-family: 'Inter', 'Inter-Fallback', sans-serif;
  line-height: 1.5;
}
```

##### Penanganan Dinamis Slot Iklan/Widget dengan CSS Aspect-Ratio & Min-Height Clamping
```css
/* Wadah Iklan Dinamis Mencegah CLS */
.ad-slot-container {
  width: 100%;
  max-width: 728px;
  /* Kunci tinggi minimum berdasarkan median historical slot */
  min-height: 90px;
  margin: 1.5rem auto;
  background-color: #f3f4f6; /* Placeholder agar visual stabil */
  contain-intrinsic-size: 728px 90px;
  content-visibility: auto; /* Optimasi rendering Chromium */
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Wadah Gambar Responsif Mencegah Layout Shift */
.responsive-media-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9; /* Menjamin rasio layout dihitung sebelum gambar diunduh */
  overflow: hidden;
  background: #e5e7eb;
}

.responsive-media-frame img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Platform**: Portal Berita Global & E-Commerce (Mega-Publisher).
- **Skala**: 120 Juta *Pageviews*/bulan, 4 Juta URL terindeks, 60% trafik berasal dari perangkat *mobile low-to-mid tier* (Android Go / Snapdragon 600 series).
- **Masalah Awal**:
  - Google Search Console: 68% URL berada di kategori "Poor" atau "Need Improvement".
  - Metrik: LCP p75 = 4.2s, INP p75 = 380ms, CLS p75 = 0.28.
  - Dampak SEO: Algoritma Google Core Update memotong Organic Search Impressions sebesar 22% dalam 3 bulan berturut-turut.

#### Root Cause Analysis (RCA)
1. **LCP Latency (4.2s)**:
   - Gambar LCP diinjeksi via JavaScript Client-Side Hydration menggunakan komponen carousel pihak ketiga.
   - Resource Load Delay: 1.8s (menunggu bundel JS utama sebesar 850KB di-download, di-*parse*, dan dieksekusi).
2. **INP Contention (380ms)**:
   - Tag Manager mengeksekusi 14 script analitik dan SDK periklanan pihak ketiga langsung di *Main Thread*.
   - Saat pengguna mengetuk tombol navigasi hamburger atau opsi filter, *Long Tasks* berdurasi 150-250ms sedang berjalan, menumpuk *Input Delay*.
3. **CLS Spikes (0.28)**:
   - Pemuatan slot iklan Google AdSense/OpenX dinamis tanpa ukuran tetap di atas LCP fold.
   - Perbedaan metrik antara font sistem fallback (`Arial`) dan custom corporate font menyebabkan pergeseran teks vertikal sebesar 32px saat *font swap* terjadi.

#### Solusi Arsitektur Diterapkan
1. **Edge-driven LCP Remediation**:
   - Pindah ke Next.js 14 SSR dengan Edge Streaming.
   - Mengambil URL gambar utama langsung saat *Server Render* dan menginjeksi tag `<link rel="preload" fetchpriority="high">` langsung pada head HTML awal.
   - Mengaktifkan konversi dinamis Cloudflare Images ke format AVIF dengan target kompresi q=75.
2. **Partytown & Cooperative Scheduler untuk INP**:
   - Memindahkan 70% skrip analitik (GTM, Meta Pixel, TikTok SDK) keluar dari *Main Thread* ke Web Worker menggunakan **Partytown**.
   - Menulis ulang komponen navigasi dan filter katalog dengan modul `scheduler.yield()` dan LoAF monitor.
3. **Font Calibration & Layout Box Clamping**:
   - Mengimplementasikan CSS `size-adjust`, `ascent-override`, dan `descent-override` pada font lokal sistem.
   - Memberikan reservasi dimensi pasti (`min-height: 250px` & `min-width: 300px`) untuk wadah iklan programmatic.

#### Hasil Pasca-Implementasi (90 Hari CrUX Cycle)

| Metrik | Sebelum Optimasi | Setelah Optimasi | Target Standar | Dampak Bisnis / SEO |
|---|---|---|---|---|
| **LCP (p75)** | 4.2 detik | **1.6 detik** | ≤ 2.5s | Masuk zona "Good" (94% valid URL) |
| **INP (p75)** | 380 ms | **110 ms** | ≤ 200ms | Input latency drop drastis pada mobile |
| **CLS (p75)** | 0.28 | **0.02** | ≤ 0.1 | Layout sepenuhnya stabil |
| **Organic Traffic** | -22% drop | **+31% YoY** | Pertumbuhan | Pemulihan penuh pasca Core Update |
| **Crawl Rate** | 2.1M hits/hari | **4.8M hits/hari** | Efisiensi | Googlebot mengonsumsi 2x lipat halaman |

---

### 9. Trade-offs & Engineering Decisions

Dalam rekayasa performa tingkat tinggi, setiap optimasi memiliki konsekuensi arsitektur:

```
┌───────────────────────────────────────┬───────────────────────────────────────┐
│               PENDEKATAN              │               TRADE-OFFS              │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ Inlining Critical CSS                 │ [+] Menghilangkan Render-Blocking CSS │
│                                       │ [-] Mematikan HTTP caching untuk CSS  │
│                                       │ [-] Memperbesar ukuran HTML mentah    │
│                                       │ [-] Meningkatkan beban memory server  │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ Offloading Third-Party ke Web Worker  │ [+] Membersihkan Main Thread (INP <)  │
│ (misal via Partytown)                 │ [-] Latensi akses DOM via IPC Worker  │
│                                       │ [-] Bug potensial pada tracking click │
│                                       │ [-] Meningkatkan komputasi memori RAM │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ Streaming SSR vs Client-Side SPA      │ [+] TTFB dan LCP jauh lebih cepat     │
│                                       │ [-] Infrastruktur server lebih mahal  │
│                                       │ [-] Overhead CPU edge/server tinggi   │
│                                       │ [-] Kompleksitas debugging hidrasi    │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ Image Format AVIF vs WebP             │ [+] AVIF 20-30% lebih hemat bandwidth │
│                                       │ [-] Encoding AVIF membutuhkan CPU 10x │
│                                       │     lebih intensif di origin server   │
│                                       │ [-] Kompatibilitas browser legacy     │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Menggunakan `loading="lazy"` pada LCP Image
- **Gejala**: Angka LCP melonjak 1.5x - 2.5x lebih lambat meskipun ukuran file kecil.
- **Penyebab**: Browser menonaktifkan *Preload Scanner* internal untuk elemen yang dideklarasikan dengan `loading="lazy"`. Browser menunda pengunduhan sampai fase Layout selesai dan posisi elemen terhadap viewport dapat dipastikan.
- **Solusi**: Pastikan gambar yang berpotensi menjadi LCP selalu menggunakan `loading="eager"` dan `fetchpriority="high"`.

#### 2. Layout Thrashing di dalam Event Handler
- **Gejala**: INP buruk, animasi tersendat (jank), Chrome DevTools menampilkan peringatan ungu: *"Forced Reflow"*.
- **Penyebab**: Pola baca-tulis-baca-tulis pada properti geometri DOM:
  ```typescript
  // BURUK: Menyebabkan layout dihitung berulang kali di dalam loop
  elements.forEach((el) => {
    const width = el.offsetWidth; // BACA (Reflow dipicu)
    el.style.width = (width * 2) + 'px'; // TULIS (Invalidate Layout)
  });
  ```
- **Solusi**: Pisahkan fase baca dari fase tulis (Batching):
  ```typescript
  // BENAR: Kumpulkan semua data dimensi terlebih dahulu, lalu lakukan penulisan
  const widths = elements.map((el) => el.offsetWidth); // Batch READ
  elements.forEach((el, i) => {
    el.style.width = (widths[i] * 2) + 'px'; // Batch WRITE
  });
  ```

#### 3. Long Animation Frames (LoAF) Logging & Diagnosis
Gunakan kode telemetri berikut langsung di konsol DevTools atau injeksi script RUM untuk melacak *script* yang merusak INP:

```typescript
// loaf-profiler.ts
if ('PerformanceObserver' in window && PerformanceObserver.supportedEntryTypes.includes('long-animation-frame')) {
  const observer = new PerformanceObserver((entryList) => {
    for (const entry of entryList.getEntries()) {
      // Periksa frame yang memakan waktu rendering lebih dari 50ms
      if (entry.duration > 50) {
        console.warn(`[LoAF Terdeteksi] Durasi Frame: ${entry.duration.toFixed(2)}ms`);
        console.log(`Blocking Duration: ${entry.blockingDuration}ms`);
        
        // Bedah kontributor script di dalam frame
        // @ts-ignore
        for (const script of entry.scripts) {
          console.table({
            source: script.sourceLocation,
            duration: script.duration,
            executionStart: script.executionStart,
            invoker: script.invoker
          });
        }
      }
    }
  });

  observer.observe({ type: 'long-animation-frame', buffered: true });
}
```

---

### 11. Best Practices & Production Checklist

#### Checklist Performa Produksi (Pra-Rilis)

##### A. LCP (Target: ≤ 2.5s p75)
- [ ] Gambar LCP di-*preload* di `<head>` dokumen menggunakan atribut `fetchpriority="high"`.
- [ ] Elemen LCP tidak menggunakan atribut `loading="lazy"`.
- [ ] Gambar dikompresi menggunakan format generasi terbaru (AVIF/WebP) dengan ukuran file < 150KB pada tampilan mobile.
- [ ] Server mengembalikan TTFB di bawah 600ms (ditingkatkan menggunakan Edge CDN caching / stale-while-revalidate).
- [ ] Tidak ada script pemblokir render (*render-blocking scripts*) yang dimuat sinkron tanpa `defer` atau `type="module"`.

##### B. INP (Target: ≤ 200ms p75)
- [ ] Tidak ada *Long Task* di *Main Thread* dengan durasi > 50ms selama navigasi dan interaksi reguler.
- [ ] Operasi array besar, filtering, dan komputasi matematika kompleks dialihkan ke Web Workers atau dipecah dengan `scheduler.yield()`.
- [ ] Handler interaksi (`pointerdown`, `click`, `keydown`) bebas dari *forced synchronous layouts*.
- [ ] Script analitik pihak ketiga dimuat via Web Worker (Partytown) atau memiliki atribut `defer`/`async`.

##### C. CLS (Target: ≤ 0.1 p75)
- [ ] Semua elemen `<img>`, `<video>`, dan `<iframe>` memiliki atribut `width` dan `height` eksplisit atau CSS `aspect-ratio`.
- [ ] Slot iklan programmatic dan dynamic widget dibungkus dalam container dengan `min-height` tetap.
- [ ] Font custom dikonfigurasi dengan metrik penyesuaian (`size-adjust`, `ascent-override`, `descent-override`) atau `font-display: optional`.
- [ ] Tidak ada konten dinamis yang diinjeksi di atas konten yang sudah ada, kecuali dipicu secara langsung oleh aksi pengguna (misalnya: konfirmasi pesan formulir).

---

### 12. Hands-on Practice

Buat dan simpan struktur proyek ini ke direktori: `hands-on/m02/`

```
hands-on/m02/
├── index.html
├── package.json
├── tsconfig.json
├── src/
│   ├── rum-engine.ts
│   └── task-breaker.ts
└── vite.config.ts
```

#### Langkah 1: Inisialisasi Proyek & Dependencies
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install web-vitals typescript vite
```

#### Langkah 2: Buat File `hands-on/m02/src/rum-engine.ts`
Implementasi production-grade RUM telemetry collector dengan *Attribution API*:

```typescript
import { onLCP, onINP, onCLS, onTTFB, Metric } from 'web-vitals/attribution';

interface TelemetryPayload {
  metric: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  navigationType: string;
  attribution: Record<string, any>;
  clientTimestamp: number;
}

function sendTelemetry(data: TelemetryPayload): void {
  const endpoint = '/api/rum-metrics';
  const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });

  // Gunakan sendBeacon agar transmisi data tidak terblokir saat halaman ditutup/unload
  if (navigator.sendBeacon) {
    navigator.sendBeacon(endpoint, blob);
  } else {
    fetch(endpoint, {
      method: 'POST',
      body: blob,
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  console.log(`[RUM Telemetry Dispatched] ${data.metric}:`, data);
}

function formatAndDispatch(metric: any): void {
  const payload: TelemetryPayload = {
    metric: metric.name,
    value: metric.value,
    rating: metric.rating,
    navigationType: metric.navigationType,
    clientTimestamp: Date.now(),
    attribution: {},
  };

  switch (metric.name) {
    case 'LCP':
      payload.attribution = {
        element: metric.attribution.element,
        url: metric.attribution.url,
        timeToFirstByte: metric.attribution.timeToFirstByte,
        resourceLoadDelay: metric.attribution.resourceLoadDelay,
        resourceLoadDuration: metric.attribution.resourceLoadDuration,
        elementRenderDelay: metric.attribution.elementRenderDelay,
      };
      break;
    case 'INP':
      payload.attribution = {
        eventTarget: metric.attribution.interactionTarget,
        eventType: metric.attribution.interactionType,
        loadState: metric.attribution.loadState,
        inputDelay: metric.attribution.inputDelay,
        processingDuration: metric.attribution.processingDuration,
        presentationDelay: metric.attribution.presentationDelay,
      };
      break;
    case 'CLS':
      payload.attribution = {
        largestShiftTarget: metric.attribution.largestShiftTarget,
        largestShiftTime: metric.attribution.largestShiftTime,
        largestShiftValue: metric.attribution.largestShiftValue,
      };
      break;
    default:
      payload.attribution = metric.attribution;
  }

  sendTelemetry(payload);
}

export function initRUMMonitoring(): void {
  onTTFB(formatAndDispatch);
  onLCP(formatAndDispatch);
  onINP(formatAndDispatch);
  onCLS(formatAndDispatch);
}
```

#### Langkah 3: Buat File `hands-on/m02/src/task-breaker.ts`
Implementasi interaksi tahan INP dengan simulasi tugas CPU tinggi:

```typescript
export async function runHeavyComputationWithScheduler(
  totalIterations: number,
  onProgress: (percent: number) => void
): Promise<void> {
  const start = performance.now();
  let lastYieldTime = performance.now();

  for (let i = 0; i < totalIterations; i++) {
    // Pekerjaan CPU-bound intensif
    Math.sqrt(i) * Math.sin(i);

    // Yield Main Thread setiap 10ms
    if (performance.now() - lastYieldTime > 10) {
      if ('scheduler' in window && 'yield' in (window as any).scheduler) {
        await (window as any).scheduler.yield();
      } else {
        await new Promise((resolve) => {
          const ch = new MessageChannel();
          ch.port1.onmessage = () => resolve(null);
          ch.port2.postMessage(null);
        });
      }
      lastYieldTime = performance.now();
      onProgress(Math.round((i / totalIterations) * 100));
    }
  }

  console.log(`Selesai dalam: ${(performance.now() - start).toFixed(2)}ms tanpa memblokir thread.`);
  onProgress(100);
}
```

#### Langkah 4: Buat File `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Performance Engineering Lab</title>
  
  <!-- CSS Kritis Di-inline untuk Mencegah Render Blocking -->
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; padding: 2rem; }
    .hero-container { width: 100%; max-width: 800px; aspect-ratio: 16 / 9; background: #ddd; }
    .hero-container img { width: 100%; height: 100%; object-fit: cover; }
    .interactive-card { margin-top: 2rem; padding: 1.5rem; border: 1px solid #ccc; border-radius: 8px; }
    .status-bar { height: 12px; width: 0%; background: #2563eb; transition: width 0.1s linear; }
  </style>

  <!-- Preload LCP Asset dengan Fetchpriority Tinggi -->
  <link rel="preload" href="https://images.unsplash.com/photo-1707343843437-caacff5cfa74?w=1200&auto=format&fit=crop&q=80" as="image" fetchpriority="high">
</head>
<body>

  <h1>Siklus Pengujian LCP, INP, & CLS</h1>
  
  <div class="hero-container">
    <img src="https://images.unsplash.com/photo-1707343843437-caacff5cfa74?w=1200&auto=format&fit=crop&q=80" 
         alt="LCP Hero Benchmark Image" 
         fetchpriority="high"
         loading="eager"
         decoding="async">
  </div>

  <div class="interactive-card">
    <h3>Pengujian Ketahanan INP (Cooperative Scheduling)</h3>
    <button id="btn-stress-test" style="padding: 10px 20px; font-size: 16px; cursor: pointer;">
      Jalankan 10.000.000 Perhitungan
    </button>
    <input type="text" placeholder="Ketik sesuatu di sini saat stress test berjalan..." style="width: 100%; margin-top: 1rem; padding: 8px;">
    
    <div style="margin-top: 1rem; background: #eee; height: 12px; border-radius: 6px; overflow: hidden;">
      <div id="progress" class="status-bar"></div>
    </div>
  </div>

  <script type="module">
    import { initRUMMonitoring } from './src/rum-engine.ts';
    import { runHeavyComputationWithScheduler } from './src/task-breaker.ts';

    // Inisialisasi RUM
    initRUMMonitoring();

    const btn = document.getElementById('btn-stress-test');
    const progressBar = document.getElementById('progress');

    btn.addEventListener('click', async () => {
      btn.setAttribute('disabled', 'true');
      await runHeavyComputationWithScheduler(10_000_000, (percent) => {
        progressBar.style.width = `${percent}%`;
      });
      btn.removeAttribute('disabled');
    });
  </script>
</body>
</html>
```

#### Langkah 5: Eksekusi dan Verifikasi
Jalankan dev server menggunakan Vite:
```bash
npx vite
```
Buka DevTools:
1. Buka tab **Performance**, rekam saat menekan tombol *"Jalankan 10.000.000 Perhitungan"* sembari mengetik di text box input.
2. Amati bahwa **Main Thread** tidak menampilkan baris merah tebal (*Long Tasks*) berdurasi masif. Interaksi ketikan pada teks input tetap responsif (INP < 50ms) berkat fragmentasi eksekusi menggunakan `yield()`.

---

### 13. Exercises

#### Level: Easy
- **Tugas**: Perbaiki potongan kode HTML berikut agar gambar LCP tidak memicu *Layout Shift* dan diunduh seawal mungkin oleh *Preload Scanner*.
- **Kode Awal**:
  ```html
  <div class="banner">
    <img src="/img/large-promo.jpg" loading="lazy" style="width: 100%;">
  </div>
  ```
- **Kriteria Keberhasilan**:
  1. Atribut `loading="lazy"` diganti dengan konfigurasi yang tepat.
  2. Prioritas jaringan diset ke tingkat tertinggi.
  3. Dimensi atau aspek rasio eksplisit diatur untuk mengunci tempat gambar.

#### Level: Medium
- **Tugas**: Buat fungsi JavaScript `batchDOMUpdates` yang menerima array berisi 500 objek teks `{ id: string, text: string }`.
- **Kriteria Keberhasilan**:
  1. Hindari mutasi DOM langsung secara individual di dalam loop tunggal.
  2. Gunakan `DocumentFragment` atau manipulasi *off-screen canvas*.
  3. Pantau agar tidak terjadi *Forced Synchronous Layout* selama proses rendering.

#### Level: Hard
- **Tugas**: Tulis custom middleware Cloudflare Workers / Node.js HTTP handler yang memvalidasi header request `Accept`.
- **Kriteria Keberhasilan**:
  1. Jika browser mendukung `image/avif`, lakukan rewrite URL gambar ke path format `.avif`.
  2. Injeksi header HTTP Link untuk `103 Early Hints` secara asinkron.
  3. Konfigurasi header `Cache-Control` dengan model *stale-while-revalidate* yang optimal bagi web crawler dan browser pengguna.

---

### 14. Enterprise Production Challenge

**Skenario Kasus**:
Anda adalah Principal Web Performance Architect di sebuah perusahaan marketplace travel berskala internasional. Sistem halaman detail pemesanan hotel (*Hotel Detail Page* / HDP) mengalami krisis performa berat:
- **LCP (p75)** berada di angka **4.8s** (Disebabkan galeri foto hotel berukuran 3MB dimuat menggunakan JavaScript masonry grid slider client-side).
- **INP (p75)** melonjak ke **650ms** saat pengguna memilih rentang tanggal (*Datepicker*) dan filter tipe kamar. Hal ini terjadi karena komponen *Datepicker* mengkalkulasi ulang ketersediaan harga untuk 365 hari ke depan secara sinkron pada setiap sentuhan/klik.
- **CLS (p75)** bernilai **0.42** akibat injeksi dinamis penawaran kupon diskon (*urgency banner*: "3 orang sedang melihat hotel ini!") yang diinjeksi 1.5 detik setelah halaman selesai dimuat tanpa reservasi layout.
- Akibat performa ini, Google Search Console menurunkan indeks halaman berstatus "Good" dari 85% menjadi 12%, dan GMV drop sebesar 18% dalam kurun waktu 45 hari.

**Instruksi Tantangan**:
1. Rancang arsitektur menyeluruh untuk menyelesaikan ketiga metrik CWV tersebut secara bersamaan tanpa menghapus fungsionalitas bisnis (galeri, *datepicker dynamic price*, dan *urgency banner*).
2. Tuliskan spesifikasi teknis penanganan komputasi *Datepicker* agar terbebas dari *Main-Thread Blocking* (berikan rancangan arsitektur worker atau scheduling chunking-nya).
3. Buat skema DOM & CSS layout untuk *urgency banner* dan *gallery grid* sehingga memiliki skor layout shift 0.00.
4. Rancang skema observabilitas RUM internal yang dapat memetakan *Attribution Data* spesifik jika terjadi regresi di region geografis dengan koneksi internet terbatas.

*(Tantangan ini tidak memiliki solusi instan tunggal; peserta wajib memetakan solusi dalam bentuk dokumen arsitektur dan potongan kode sistem yang komprehensif).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa menambahkan atribut `loading="lazy"` pada gambar yang menjadi kandidat LCP dianggap sebagai anti-pattern yang berbahaya bagi SEO?**
   - *Jawaban*: Karena `loading="lazy"` menginstruksikan browser untuk menunda pemuatan gambar sampai layout selesai dihitung dan posisi gambar terkonfirmasi berada di dekat viewport. Hal ini mematikan fungsi *Preload Scanner* browser, memperbesar *Resource Load Delay*, dan secara signifikan memperlambat pencapaian waktu LCP.

2. **Apa perbedaan mendasar antara metrik FID (First Input Delay) yang telah didepresiasi dan INP (Interaction to Next Paint)?**
   - *Jawaban*: FID hanya mengukur waktu tunggu (*Input Delay*) dari interaksi **pertama kali** pengguna dengan halaman dan mengabaikan waktu eksekusi kode (*processing*) serta rendering (*presentation delay*). Sebaliknya, INP mengukur siklus interaksi lengkap (*Input Delay + Processing Duration + Presentation Delay*) sepanjang masa pakai halaman (*full session*) untuk mendeteksi latensi interaktivitas terburuk.

3. **Bagaimana CSS `aspect-ratio` dapat meniadakan Cumulative Layout Shift (CLS) pada gambar responsif?**
   - *Jawaban*: CSS `aspect-ratio` memungkinkan layout browser menghitung rasio proporsional ruang yang dibutuhkan elemen visual berdasarkan lebarnya sebelum file gambar aktual selesai diunduh. Dengan demikian, browser langsung mereservasi ruang kosong yang stabil, mencegah pergeseran elemen konten lain saat gambar tiba.

4. **Kapan Chromium mengeksekusi *Compositor Thread*, dan mengapa mutasi menggunakan CSS `transform` lebih murah dibandingkan mutasi `top`/`left`?**
   - *Jawaban*: *Compositor Thread* dijalankan setelah *Paint Engine* memecah instruksi visual menjadi layer. Mutasi `transform` diproses langsung pada tingkat GPU di *Compositor Thread* tanpa memicu kembali tahapan *Layout* (Reflow) atau *Paint* (Repaint), sedangkan perubahan `top`/`left` memicu siklus *Layout* ulang secara hierarkis pada *Main Thread*.

5. **Apa fungsi dari Resource Hint `fetchpriority="high"`?**
   - *Jawaban*: Memberikan sinyal eksplisit kepada browser untuk menempatkan download resource tersebut di prioritas antrean teratas dari alokasi bandwidth jaringan, mendahului resource lain dengan jenis yang sama atau resource render-blocking yang belum diperlukan segera.

#### Bagian 2: Intermediate (5 Soal)
6. **Jelaskan apa yang dimaksud dengan *Forced Synchronous Layout* (Layout Thrashing) dan bagaimana mekanismenya merusak metrik INP.**
   - *Jawaban*: Layout Thrashing terjadi ketika kode JavaScript membaca properti geometri elemen (seperti `offsetWidth`, `clientHeight`) langsung setelah melakukan modifikasi DOM/CSS. Hal ini memaksa browser untuk langsung menghentikan eksekusi script dan menjalankan perhitungan ulang Layout secara sinkron di *Main Thread* agar nilai geometri yang dibaca akurat. Jika terjadi berulang kali dalam satu event loop, *Processing Duration* melonjak drastis dan menyebabkan frame drop serta INP tinggi.

7. **Bagaimana mekanisme header HTTP `103 Early Hints` membantu memangkas *Resource Load Delay* pada LCP?**
   - *Jawaban*: Server dapat langsung merespons dengan kode status HTTP 103 berisi Link header (preload resource kritis seperti CSS dan gambar LCP) segera setelah menerima request, sebelum server selesai memproses data dinamis/SSR HTML. Browser klien dapat mulai mengunduh aset penting tersebut selagi server masih memproses data di latar belakang.

8. **Mengapa penggunaan font-display: swap masih dapat menyebabkan skor CLS yang buruk jika tidak dikonfigurasi dengan font metric overrides?**
   - *Jawaban*: `font-display: swap` langsung menampilkan fallback font sistem sebelum web font custom selesai dimuat. Jika dimensi *glyph*, tinggi x-height, *ascent*, atau *descent* dari font fallback berbeda dari font custom, teks akan membesar atau mengecil saat web font diterapkan (*Flash of Unstyled Text* - FOUT). Perubahan ukuran kotak teks ini mendorong elemen-elemen di sekitarnya dan memicu Layout Shift score yang tinggi.

9. **Apa perbedaan antara eksekusi task menggunakan `setTimeout(fn, 0)` dibandingkan dengan `scheduler.yield()`?**
   - *Jawaban*: `setTimeout(fn, 0)` memasukkan task ke dalam antrean *Macrotask Event Loop* dengan jeda minimum (clamping) sekitar 4ms jika bersarang, dan browser memperlakukannya sama seperti task biasa lainnya. `scheduler.yield()` secara spesifik mengembalikan kendali ke rendering pipeline browser untuk melukis frame layar atau memproses input mendesak, lalu melanjutkan kelanjutan task tersebut di prioritas yang dioptimasi tanpa penalti clamping waktu.

10. **Bagaimana Long Animation Frames (LoAF) API memberikan visibilitas lebih baik terhadap masalah interaktivitas dibandingkan Long Tasks API lawas?**
    - *Jawaban*: Long Tasks API hanya melaporkan durasi eksekusi task yang melebihi 50ms tanpa memberikan visibilitas apakah task tersebut berdampak pada keterlambatan frame visual, serta minim detail atribusi kode. LoAF API mengukur keseluruhan siklus frame rendering, membedah *Presentation Delay*, dan mengidentifikasi secara presisi file skrip, fungsi invoker, posisi baris/karakter (*sourceLocation*), serta *style/layout recalculation time* yang bertanggung jawab atas keterlambatan frame tersebut.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**:
    Sebuah situs e-commerce melaporkan bahwa pada Google Search Console, metrik LCP untuk halaman katalog produk berada di angka 3.8s pada pengguna perangkat seluler, tetapi bernilai 1.1s pada pengujian lab Chrome DevTools dengan CPU Desktop. Pemeriksaan awal menunjukkan server menggunakan Edge Caching dengan TTFB 80ms. Mengapa disparitas masif ini terjadi dan apa mitigasi arsitekturalnya?
    - *Jawaban & Analisis Solusi*: Disparitas ini terjadi akibat tingginya *Element Render Delay* pada perangkat seluler berkemampuan komputasi rendah. Di lab desktop, CPU modern dapat mem-parse bundel JavaScript berukuran besar (misal 1MB) dalam hitungan milidetik, lalu merender gambar LCP ke layar seketika. Pada perangkat mobile low-tier, eksekusi hidrasi JavaScript monolitik mendominasi *Main Thread* selama 2-3 detik pasca aset gambar selesai diunduh (*hydration lock*), menahan proses melukis (*paint*) elemen ke layar. Solusinya: Hentikan hidrasi monolitik di client side. Implementasikan *Partial Hydration* / *Islands Architecture* atau streaming SSR dengan HTML statis untuk bagian visual LCP katalog, serta kurangi eksekusi script sebelum LCP terjadi.

12. **Skenario 2**:
    Tim marketing Anda mengintegrasikan alat pengujian A/B testing pihak ketiga berbasis JavaScript snippet sinkron di `<head>`. Tak lama berselang, skor INP melonjak dari 90ms menjadi 420ms di seluruh funnel konversi. Analisis DevTools menunjukkan snippet tersebut melakukan polling mutasi DOM secara agresif melalui `MutationObserver` dan memanggil `getBoundingClientRect()` secara berulang untuk menentukan posisi variasi eksperimen. Bagaimana arsitektur A/B testing ini harus diubah total tanpa menghilangkan kemampuan eksperimen bisnis?
    - *Jawaban & Analisis Solusi*: Snippet sinkron A/B testing ini memicu *Layout Thrashing* dan *Input Delay* masif. Solusi arsitekturnya adalah memindahkan logika A/B testing dari client-side ke **Edge Layer** (Edge-Side Experimentation). Edge Worker (misal: Cloudflare Workers, Fastly VCL) mengevaluasi cookie atau user bucket eksperimen, lalu merestrukturisasi dan menyajikan dokumen HTML yang sudah termutasi variasi A atau B langsung dari edge server secara streaming sebelum mencapai browser. Klien menerima HTML akhir yang bersih tanpa memerlukan skrip manipulasi DOM di client-side, mengembalikan nilai INP ke level aman (<100ms) dan mengeliminasi CLS sepenuhnya.

13. **Skenario 3**:
    Laporan RUM internal menunjukkan bahwa 15% pengguna mengalami CLS tinggi (>0.3) hanya saat melakukan scroll ke bawah secara perlahan pada artikel blog yang panjang, sedangkan pengujian Lighthouse otomatis (Synthetic) selalu memberikan skor CLS sempurna: 0.00. Apa akar masalah tersembunyi yang lazim terjadi dalam skenario ini dan bagaimana memperbaikinya?
    - *Jawaban & Analisis Solusi*: Pengujian sintetis (Lighthouse) secara default hanya mengaudit halaman dalam kondisi diam (*idle*) pada fold pertama tanpa mensimulasikan scrolling interaktif penuh pengguna. Skor CLS yang buruk saat scrolling biasanya dipicu oleh:
      1. Komponen *Infinite Scroll* atau *Lazy Load* gambar/iklan yang tidak menyertakan reservasi dimensi kotak (*placeholder skeleton* dengan ukuran tetap), sehingga ketika elemen masuk ke viewport, teks artikel di bawahnya terdorong ke bawah secara mendadak.
      2. Widget sticky/floating banner yang muncul secara asinkron dan memanipulasi posisi elemen artikel saudara (*sibling nodes*) alih-alih berada di layer komposit independen (`position: fixed` dengan `will-change: transform`).
      Perbaikannya: Terapkan CSS container bounding box dengan `contain-intrinsic-size` atau `min-height` pada semua container konten lazy-loaded di sepanjang dokumen artikel, dan pastikan elemen floating/banner menggunakan koordinat fixed tanpa mengganggu alur dokumen (flow layout).

---

### 16. Summary

- **Core Web Vitals adalah Metrik Tingkat Mesin Browser**: Kunci sukses optimasi CWV berada pada pemahaman arsitektur rendering engine Chromium (Blink). Memisahkan pekerjaan antara *Main Thread*, *Compositor Thread*, dan *GPU Rasterization* adalah fondasi utama rekayasa performa modern.
- **LCP Berfokus pada Eliminasi Critical Path Delay**: Mengoptimasi LCP bukan hanya soal kompresi aset gambar, melainkan mempercepat keempat sub-bagian LCP secara berurutan. Menggunakan **103 Early Hints**, `<link rel="preload" fetchpriority="high">`, kompresi AVIF, dan streaming SSR memastikan *Resource Load Delay* dan *Render Delay* mendekati 0ms.
- **INP Menuntut Cooperative Scheduling**: INP mengakhiri era eksekusi monolitik di *Main Thread*. Dengan menggunakan strategi fragmentasi tugas berbasis `scheduler.yield()`, pemanfaatan **Long Animation Frames (LoAF) API**, dan pemindahan beban kerja pihak ketiga ke Web Worker, aplikasi web dapat mempertahankan interaktivitas p75 < 200ms di bawah beban komputasi berat.
- **CLS Diselesaikan dengan Determinisme Ruang Visual**: Mengunci dimensi elemen visual sebelum byte konten diterima (menggunakan CSS `aspect-ratio`, layout bounding clamping, dan penyesuaian font metrics FOUT-less) sepenuhnya menghilangkan pergeseran visual yang tidak diinginkan.
- **Observabilitas RUM adalah Sumber Kebenaran Mutlak**: Karena Google mengevaluasi algoritma peringkat berdasarkan metrik lapangan nyata (CrUX data), pipeline telemetri RUM berbasis `PerformanceObserver` dengan pelaporan sub-atribusi detail merupakan infrastruktur wajib dalam siklus hidup rekayasa perangkat lunak enterprise.