# Kurikulum Enterprise Frontend Engineering

## Kategori: 03-Frontend-and-Mobile
### Bab 07: Performance Engineering & Core Web Vitals
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** siklus render browser engine tingkat rendah (*Parse*, *Style*, *Layout*, *Pre-paint*, *Paint*, *Composite*) dan mengidentifikasi anomali *Long Tasks* serta *Forced Synchronous Layout*.
- **Merancang dan mengimplementasikan** arsitektur mitigasi Core Web Vitals (CWV) modern: LCP (*Largest Contentful Paint*), INP (*Interaction to Next Paint*), dan CLS (*Cumulative Layout Shift*) untuk target p75/p95 di skala enterprise.
- **Mengembangkan** pipeline task scheduling non-blocking memanfaatkan `scheduler.yield()`, `scheduler.postTask()`, dan delegasi komputasi asinkron via Web Workers (`Comlink`).
- **Membangun** sistem Real User Monitoring (RUM) *zero-overhead* menggunakan `PerformanceObserver` API dan integrasi pelaporan telemetri via `navigator.sendBeacon` yang diperkaya distributed tracing headers.
- **Mengevaluasi** trade-off antara SSR *Hydration*, *Streaming HTML*, *Islands Architecture*, dan *Resumability* pada performa *Time to First Byte* (TTFB) hingga LCP.

---

### 2. Prerequisite

Peserta wajib menguasai:
- Arsitektur JavaScript Engine: V8 Call Stack, Memory Heap, Macrotask vs Microtask Queue.
- Network Protocol: HTTP/2 Multiplexing, HTTP/3 QUIC, TLS 1.3 Handshake, Resource Hints (`preload`, `prefetch`, `preconnect`).
- DOM Life Cycle & Render Tree construction: Render Pipeline Blink/Gecko.
- State Management & Component Lifecycle pada React 18+ (Concurrent Features, Suspense, Server Components) atau framework modern setara.

---

### 3. Concept & Internal Architecture

#### 3.1. Browser Threading Model & Blink Rendering Engine Pipeline

Performa web modern ditentukan oleh koordinasi antara thread-thread utama di browser engine (Blink/Chromium):

```
+---------------------------------------------------------------------------------------+
|                                    BROWSER PROCESS                                    |
|  - Network Stack (HTTP/2, HTTP/3, Cache)                                              |
|  - Storage Engine, Permissions, UI Management                                         |
+-------------------------------------------+-------------------------------------------+
                                            | IPC
+-------------------------------------------v-------------------------------------------+
|                                   RENDERER PROCESS                                    |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | MAIN THREAD                                                                     |  |
|  |  [JS Engine: V8] -> [HTML/CSS Parser] -> [Style Recalc] -> [Layout (Reflow)]    |  |
|  |         |                                                      |                |  |
|  |         +--> Task Queue (Micro/Macro)                          v                |  |
|  |                                                        [Pre-paint / Paint]      |  |
|  |                                                                |                |  |
|  |                                                                v                |  |
|  |                                                         [Layerize Tree]         |  |
|  +----------------------------------------------------------------+----------------+  |
|                                                                   | Commit             |
|  +----------------------------------------------------------------v----------------+  |
|  | COMPOSITOR THREAD                                                               |  |
|  |  - Compositor Tiling                                                            |  |
|  |  - Off-main-thread Scrolling & Animations (transform / opacity)                 |  |
|  +----------------------------------------------------------------+----------------+  |
|                                                                   | Tiles / Draw Quads |
|  +----------------------------------------------------------------v----------------+  |
|  | RASTER THREAD POOL                                                              |  |
|  |  - Rasterizes Display Lists into Bitmaps via Skia/Ganesh/Graphite               |  |
|  +----------------------------------------------------------------+----------------+  |
+-------------------------------------------+-------------------------------------------+
                                            | Shared Memory / IPC
+-------------------------------------------v-------------------------------------------+
|                                      GPU PROCESS                                      |
|  - Draw Quads Composition -> Frame Buffer Display                                     |
+---------------------------------------------------------------------------------------+
```

1. **Main Thread**:
   - Mengeksekusi eksekusi JavaScript, resolving DOM/CSSOM, perhitungan Layout (geometri dan posisi node), serta pembangunan Display List (instruksi gambar skia) saat fase *Paint*.
   - Jika JavaScript mengeksekusi komputasi sinkron > 50ms (*Long Task*), seluruh pipeline di Main Thread macet, menyebabkan degradasi **INP** dan hilangnya frame visual (*jank*).
2. **Compositor Thread**:
   - Beroperasi secara terpisah dari Main Thread. Bertanggung jawab memotong layer menjadi ubin (*tiles*), mengarahkan operasi transform/opacity ke GPU, dan menangani scroll interaktif tanpa menunggu komputasi JS di Main Thread, *kecuali* jika dicegah oleh non-passive event listeners (`e.preventDefault()`).
3. **Raster Thread Pool**:
   - Mengubah Display List dari layer-layer DOM menjadi bitmap di memori GPU.

#### 3.2. Dekonstruksi Metrik Core Web Vitals (CWV)

```
Time ---------------------------------------------------------------------------------------->
[TTFB] --------> [FCP] -------------> [LCP] ------------------------> [INP] (On Interaction)
  ^                ^                    ^                               ^
  |                |                    |                               |
Request/Response  First Contentful     Largest Node Rendered           Event Latency
HTML Document     Element Rendered     (Image, Video Poster, Block)    (Input Delay + Processing
                                                                        Time + Presentation Delay)
```

1. **Largest Contentful Paint (LCP)**:
   - Mengukur waktu ketika elemen konten visual terbesar pada viewport selesai dirender.
   - Formula internal:
     $$\text{LCP} = \text{Time to First Byte (TTFB)} + \text{Resource Load Delay} + \text{Resource Load Duration} + \text{Element Render Delay}$$
   - LCP *paling sering* terdegradasi oleh: gambar beresolusi tinggi tanpa atribut `fetchpriority="high"`, render-blocking CSS/JS, dan keterlambatan hidrasi SSR.

2. **Interaction to Next Paint (INP)**:
   - Menggantikan First Input Delay (FID). Mengukur latensi keseluruhan dari *seluruh* interaksi pengguna (click, tap, keydown) sepanjang siklus hidup halaman.
   - Formula internal:
     $$\text{INP Latency} = \text{Input Delay} + \text{Processing Duration} + \text{Presentation Delay}$$
     - **Input Delay**: Waktu event menunggu Main Thread bebas dari Long Tasks sebelumnya.
     - **Processing Duration**: Waktu eksekusi seluruh event listener callback (`onClick`, `onChange`, dll.).
     - **Presentation Delay**: Waktu bagi browser engine untuk recalculate style, relayout, repaint, dan mengirimkan frame baru ke Compositor & GPU.

3. **Cumulative Layout Shift (CLS)**:
   - Mengukur pergeseran layout tak terduga dari elemen yang terlihat di viewport.
   - Formula:
     $$\text{Layout Shift Score} = \text{Impact Fraction} \times \text{Distance Fraction}$$
   - Penyebab mendasar: Dimensi aset (`width`/`height`) yang tidak ditentukan, dynamic DOM injection di atas konten eksis tanpa reservasi slot memori layar, dan Web Font loading tanpa metrik alignment (*FOUT/FOIT*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Performance Engineering |
| :--- | :--- | :--- |
| **Paradigma Optimasi** | Ad-hoc (audit Lighthouse sesekali di workstation lokal) | RUM Continuous Profiling (p75/p95/p99 data pengguna riil di agregasi via data lake) |
| **Metrik Interaksi** | Hanya fokus pada load-time (TTFB/FCP) | Full-lifecycle responsiveness (INP under continuous load) |
| **Task Management** | Eksekusi JS monolitik blocking event-loop | Fine-grained non-blocking scheduler via `scheduler.yield()` & Web Workers |
| **Arsitektur Rendering**| Blind Full Hydration (React SSR default) | Progressive/Selective Hydration, Streaming SSR, atau Resumability |
| **Penanganan Aset** | Global asset bundle dengan basic compression (Gzip) | Dynamic Brotli/Zstandard, Priority Hints, Font Metric Overrides, Speculation API |

Mengapa ini esensial bagi arsitektur enterprise?
1. **Dampak Finansial**: Setiap peningkatan latensi 100ms pada e-commerce checkout dapat menurunkan conversion rate sebesar 1-2%.
2. **SEO & Ranking Degradation**: Google Search Console menetapkan batas ketat p75 CWV: LCP $\le$ 2.5s, INP $\le$ 200ms, CLS $\le$ 0.1. Kegagalan melanggar threshold ini berakibat langsung pada penurunan organic impression.
3. **Hardware Heterogeneity**: Sebagian besar pengguna enterprise global mengakses aplikasi dari perangkat low-to-mid end dengan CPU throttling agresif dan memori terbatas, di mana JS payload > 300KB dapat memblokir Main Thread hingga 3-5 detik.

---

### 5. How (Workflow Detail)

Alur kerja mitigasi dan optimasi performa skala enterprise beroperasi di dua level: **Build/Architectural Pipeline** dan **Runtime Execution Pipeline**.

```
BUILD/DEPLOY PIPELINE
[Source Code] 
      │
      ├──> Static Bundle Analysis (AST Parse, Tree Shaking, Chunk Split)
      ├──> Font Metric Matcher (Inject Size-Adjust CSS Overrides)
      ├──> Asset Pipeline (WebP/AVIF generation, inline critical SVG)
      └──> Edge Routing Config (Early Hints 103, Speculation Rules)

RUNTIME PIPELINE (Per Connection)
[HTTP Request] 
      │
      ├──> Edge: Return 103 Early Hints (Preload LCP, Preconnect Origins)
      ├──> Browser: Streaming HTML parse starts immediately
      ├──> Browser: Fetch critical CSS & High-priority LCP asset simultaneously
      ├──> Main Thread: Scheduler processes tasks with cooperative yielding
      ├──> Background: Worker handles analytical telemetry & complex computations
      └──> Instrumentation: PerformanceObserver aggregates CWV -> Beaconing to RUM
```

#### Langkah Implementasi:
1. **LCP Optimization Path**:
   - Terbitkan header HTTP 103 Early Hints di layer edge/CDN.
   - Eliminasi render-blocking JavaScript dan split critical CSS.
   - Anotasikan aset LCP dengan `fetchpriority="high"` dan decoding asinkron `decoding="async"`.
2. **INP Optimization Path**:
   - Pecah tugas komputasi panjang (> 50ms) menggunakan slicing asinkron berbasis `scheduler.yield()` atau fallback `MessageChannel`.
   - Gunakan `scheduler.postTask()` dengan prioritas `'user-visible'` atau `'background'`.
   - Pindahkan komputasi data murni (parsing JSON masif, enkripsi, transformasi visual canvas) ke Web Worker thread pool.
3. **CLS Optimization Path**:
   - Sertakan `aspect-ratio` atau eksplisit `width` dan `height` pada setiap media container.
   - Reservasi dimensi bounding-box untuk komponen dinamis (iklan, rekomendasi, alert banner) menggunakan CSS containment (`contain-intrinsic-size` & `content-visibility`).
   - Normalisasi metrik font fallback menggunakan `@font-face` atribut `size-adjust`, `ascent-override`, dan `descent-override`.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Restoran untuk Threading & Cooperative Scheduling

- **Main Thread = Koki Tunggal (Head Chef)**: Koki harus memotong sayur, memasak, menghias piring, dan menerima pesanan baru dari pelayan.
- **Long Task Blocking**: Jika koki mulai mencincang daging selama 2 jam tanpa henti, tidak ada pesanan baru yang bisa disajikan, dan pengunjung yang ingin memesan minuman akan diabaikan (INP melonjak tinggi, aplikasi hang).
- **Cooperative Yielding (`scheduler.yield`)**: Koki memotong 5 potong daging, lalu berhenti 2 detik untuk memeriksa apakah ada pesanan baru dari pelanggan, lalu melanjutkan memotong lagi.
- **Web Worker = Asisten Dapur di Ruangan Lain**: Koki menyerahkan tugas menghitung stok gudang (komputasi data) kepada asisten, sehingga koki tetap bisa memasak di dapur utama tanpa gangguan.
- **Compositor = Pelayan Sajian**: Pelayan membawa makanan yang sudah ada di nampan ke meja pelanggan secara mandiri, tanpa terpengaruh koki yang sedang sibuk.

#### Diagram: Forced Synchronous Layout vs Cooperative Task Yielding

```
FORCED SYNCHRONOUS LAYOUT (Layout Thrashing)
JS: Write DOM -> Read style -> Write DOM -> Read style
[ JS (Write) ] -> [ Layout! ] -> [ JS (Write) ] -> [ Layout! ]  <-- BAD (N recalculations)

COOPERATIVE TASK SCHEDULING (Main Thread Friendly)
Main Thread Execution Timeline:
|-- Task A (Chunk 1) --| Yield |-- Task A (Chunk 2) --| Yield |-- Paint / Event Handling --|
[    12ms compute     ]   │   [    15ms compute     ]   │   [ Browser can draw frame! ]
                          v                             v
                   [Event Check]                 [User Input] (INP < 50ms)
```

---

### 7. Code Implementations

#### 7.1. Simple Example: Progressive Task Chunking Menggunakan `scheduler.yield()` Modern Fallback

File: `task-scheduler.ts`
Implementasi production-ready task slicing yang kompatibel dengan browser yang belum mendukung Scheduler API natif.

```typescript
/**
 * task-scheduler.ts
 * Engine penjadwalan non-blocking untuk mencegah long task di Main Thread.
 */

// Interface untuk deklarasi Scheduler API global
declare global {
  interface Window {
    scheduler?: {
      yield?: () => Promise<void>;
      postTask?: (
        callback: () => any,
        options?: { priority: 'user-blocking' | 'user-visible' | 'background'; delay?: number }
      ) => Promise<any>;
    };
  }
}

/**
 * Cooperative yield generator: Mengembalikan eksekusi ke browser event loop
 * untuk merender frame atau merespons interaksi input pengguna.
 */
export async function yieldToMain(): Promise<void> {
  // 1. Prioritaskan native Scheduler API jika tersedia
  if (typeof window !== 'undefined' && window.scheduler?.yield) {
    return window.scheduler.yield();
  }

  // 2. Gunakan fallback performa tinggi: MessageChannel (Macro-task queue)
  // MessageChannel mengeksekusi lebih cepat daripada setTimeout(fn, 0) yang memiliki minimum 4ms clamp.
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => {
      resolve();
    };
    channel.port2.postMessage(null);
  });
}

/**
 * Memproses array data dalam bentuk chunk secara asinkron tanpa memblokir Main Thread.
 *
 * @param items Koleksi item yang akan diproses
 * @param processor Callback pemrosesan per item
 * @param maxExecutionMs Batas durasi per interval sebelum eksekusi wajib di-yield (default 16ms ~ 1 frame)
 */
export async function processInChunks<T, R>(
  items: T[],
  processor: (item: T, index: number) => R,
  maxExecutionMs: number = 16
): Promise<R[]> {
  const results: R[] = [];
  let lastYieldTime = performance.now();

  for (let i = 0; i < items.length; i++) {
    results.push(processor(items[i], i));

    // Evaluasi durasi eksekusi saat ini
    const currentTime = performance.now();
    if (currentTime - lastYieldTime >= maxExecutionMs) {
      // Waktu chunk terlampaui, serahkan kendali kembali ke event loop
      await yieldToMain();
      lastYieldTime = performance.now();
    }
  }

  return results;
}
```

#### 7.2. Practical Example: Enterprise Real User Monitoring (RUM) Instrumentation Agent

File: `rum-telemetry.ts`
Library telemetri performa modular yang memantau Core Web Vitals (LCP, INP, CLS), mendeteksi anomali, dan mengirimkan metrik dengan reliabilitas tinggi ke ingestion proxy via `sendBeacon`.

```typescript
/**
 * rum-telemetry.ts
 * Production-grade Real User Monitoring client agent.
 */

export interface MetricPayload {
  name: 'LCP' | 'INP' | 'CLS' | 'TTFB';
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  delta: number;
  id: string;
  navigationType: string;
  url: string;
  timestamp: number;
  attribution?: Record<string, any>;
}

export interface RUMConfig {
  endpoint: string;
  sampleRate: number; // 0.0 to 1.0
  debug?: boolean;
}

export class EnterpriseRUM {
  private static instance: EnterpriseRUM;
  private config: RUMConfig;
  private queue: MetricPayload[] = [];
  private isFlushing: boolean = false;

  private constructor(config: RUMConfig) {
    this.config = config;
    if (this.shouldSample()) {
      this.initObservers();
      this.setupUnloadHandler();
    }
  }

  public static initialize(config: RUMConfig): EnterpriseRUM {
    if (!EnterpriseRUM.instance) {
      EnterpriseRUM.instance = new EnterpriseRUM(config);
    }
    return EnterpriseRUM.instance;
  }

  private shouldSample(): boolean {
    return Math.random() < this.config.sampleRate;
  }

  private getRating(name: MetricPayload['name'], value: number): MetricPayload['rating'] {
    switch (name) {
      case 'LCP':
        return value <= 2500 ? 'good' : value <= 4000 ? 'needs-improvement' : 'poor';
      case 'INP':
        return value <= 200 ? 'good' : value <= 500 ? 'needs-improvement' : 'poor';
      case 'CLS':
        return value <= 0.1 ? 'good' : value <= 0.25 ? 'needs-improvement' : 'poor';
      case 'TTFB':
        return value <= 800 ? 'good' : value <= 1800 ? 'needs-improvement' : 'poor';
    }
  }

  private initObservers(): void {
    if (typeof PerformanceObserver === 'undefined') return;

    // 1. Observer: Largest Contentful Paint (LCP)
    try {
      const lcpObserver = new PerformanceObserver((entryList) => {
        const entries = entryList.getEntries();
        const lastEntry = entries[entries.length - 1] as PerformanceEntry & {
          element?: Element;
          url?: string;
          size?: number;
        };

        if (lastEntry) {
          this.recordMetric({
            name: 'LCP',
            value: Math.round(lastEntry.startTime),
            delta: Math.round(lastEntry.startTime),
            id: `lcp-${Date.now()}`,
            navigationType: this.getNavigationType(),
            url: window.location.href,
            timestamp: Date.now(),
            rating: this.getRating('LCP', lastEntry.startTime),
            attribution: {
              elementTagName: lastEntry.element?.tagName,
              elementId: lastEntry.element?.id,
              elementClass: lastEntry.element?.className,
              resourceUrl: lastEntry.url,
              byteSize: lastEntry.size,
            },
          });
        }
      });
      lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {
      this.logWarn('LCP not supported', e);
    }

    // 2. Observer: Cumulative Layout Shift (CLS)
    try {
      let clsValue = 0;
      let sessionEntries: PerformanceEntry[] = [];

      const clsObserver = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries() as any[]) {
          // Hanya hitung layout shift tanpa interaksi input terkini (hadRecentInput = false)
          if (!entry.hadRecentInput) {
            clsValue += entry.value;
            sessionEntries.push(entry);
          }
        }

        this.recordMetric({
          name: 'CLS',
          value: parseFloat(clsValue.toFixed(4)),
          delta: parseFloat(clsValue.toFixed(4)),
          id: `cls-${Date.now()}`,
          navigationType: this.getNavigationType(),
          url: window.location.href,
          timestamp: Date.now(),
          rating: this.getRating('CLS', clsValue),
          attribution: {
            shiftCount: sessionEntries.length,
          },
        });
      });
      clsObserver.observe({ type: 'layout-shift', buffered: true });
    } catch (e) {
      this.logWarn('CLS not supported', e);
    }

    // 3. Observer: Interaction to Next Paint (INP)
    try {
      let longestInteractionDuration = 0;

      const inpObserver = new PerformanceObserver((entryList) => {
        for (const entry of entryList.getEntries() as any[]) {
          if (!entry.interactionId) continue;

          // Evaluasi durasi terpanjang dari interaksi (durasi mencakup input delay + processing + presentation)
          if (entry.duration > longestInteractionDuration) {
            longestInteractionDuration = entry.duration;

            this.recordMetric({
              name: 'INP',
              value: Math.round(entry.duration),
              delta: Math.round(entry.duration),
              id: `inp-${entry.interactionId}`,
              navigationType: this.getNavigationType(),
              url: window.location.href,
              timestamp: Date.now(),
              rating: this.getRating('INP', entry.duration),
              attribution: {
                eventType: entry.name,
                processingStart: entry.processingStart,
                processingEnd: entry.processingEnd,
                targetNode: entry.target ? entry.target.nodeName : null,
              },
            });
          }
        }
      });
      inpObserver.observe({ type: 'event', buffered: true, durationThreshold: 16 });
    } catch (e) {
      this.logWarn('INP not supported', e);
    }
  }

  private recordMetric(metric: MetricPayload): void {
    if (this.config.debug) {
      console.info(`[RUM Metric] ${metric.name}:`, metric.value, metric);
    }
    this.queue.push(metric);
    this.scheduleFlush();
  }

  private scheduleFlush(): void {
    if (this.isFlushing) return;
    this.isFlushing = true;

    // Gunakan requestIdleCallback untuk transfer data saat thread lowong
    const scheduleFn = window.requestIdleCallback || ((cb) => setTimeout(cb, 1000));
    scheduleFn(() => {
      this.flush();
      this.isFlushing = false;
    });
  }

  private flush(): void {
    if (this.queue.length === 0) return;

    const payload = JSON.stringify({
      metrics: [...this.queue],
      clientMetadata: {
        userAgent: navigator.userAgent,
        connection: (navigator as any).connection?.effectiveType || 'unknown',
        deviceMemory: (navigator as any).deviceMemory || 'unknown',
        hardwareConcurrency: navigator.hardwareConcurrency || 'unknown',
      },
    });

    this.queue = [];

    // Gunakan sendBeacon untuk mencegah request terputus saat page unmount
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' });
      const success = navigator.sendBeacon(this.config.endpoint, blob);
      if (!success) {
        this.fallbackFetch(payload);
      }
    } else {
      this.fallbackFetch(payload);
    }
  }

  private fallbackFetch(payload: string): void {
    fetch(this.config.endpoint, {
      body: payload,
      method: 'POST',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
    }).catch((err) => this.logWarn('RUM dispatch failed', err));
  }

  private setupUnloadHandler(): void {
    const flushHandler = () => this.flush();
    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        flushHandler();
      }
    });
    window.addEventListener('pagehide', flushHandler);
  }

  private getNavigationType(): string {
    if (performance.getEntriesByType) {
      const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      return navEntry ? navEntry.type : 'navigate';
    }
    return 'navigate';
  }

  private logWarn(message: string, error: unknown): void {
    if (this.config.debug) {
      console.warn(`[RUM Warning]: ${message}`, error);
    }
  }
}
```

---

### 8. Real World Case Study: E-Commerce Scale Migration

#### Konteks Masalah
Sebuah platform e-commerce enterprise dengan 35 juta *Monthly Active Users* (MAU) mengalami penurunan drastis pada konversi mobile funnel checkout. Berdasarkan data audit Google Search Console:
- **LCP p75**: 4.8 detik pada jaringan 4G/Android mid-range (Ambang batas aman $\le 2.5\text{s}$).
- **INP p75**: 680ms saat interaksi tombol "Pilih Varian Produk" dan "Tambah ke Keranjang" (Ambang batas aman $\le 200\text{ms}$).
- **CLS**: 0.28 akibat dynamic promo banner dan font swapping.

#### Akar Masalah (Root Causes)
1. **LCP**: Hero product image dirender setelah Single Page Application (SPA) memuat bundle JavaScript monolitik sebesar 1.4MB, memicu eksekusi API catalog secara lambat (client-side waterfall).
2. **INP**: Handler event `onChange` pada varian produk mengeksekusi perhitungan stock availability matriks kompleks (1200 SKU kombinasional) secara sinkron di Main Thread, bersamaan dengan re-rendering React subtree monolitik tanpa concurrent boundaries.
3. **CLS**: Custom brand web font menyebabkan Flash of Unstyled Text (FOUT) dengan perbedaan tinggi x-height sebesar 18% dari system fallback font.

#### Solusi Arsitektural & Rekayasa Teknis

1. **Resolusi LCP**:
   - Memindahkan rendering halaman Product Detail Page (PDP) ke **Edge-rendered Streaming SSR** menggunakan edge nodes di 12 region.
   - Mengimplementasikan HTTP 103 Early Hints untuk mengumumkan link header preload image LCP:
     ```http
     HTTP/1.1 103 Early Hints
     Link: </images/hero-sku-101.avif>; rel=preload; as=image; fetchpriority=high
     ```
   - Menyematkan langsung atribut prioritas pada image element:
     ```html
     <img 
       src="/images/hero-sku-101.avif" 
       fetchpriority="high" 
       loading="eager" 
       decoding="async" 
       width="600" 
       height="600" 
       alt="SKU 101 Hero" 
     />
     ```

2. **Resolusi INP**:
   - Mengisolasi kalkulasi matriks ketersediaan stok 1200 SKU ke **Web Worker** menggunakan library RPC ringan berbasis `Comlink`.
   - Menggunakan React 18 `useTransition` pada re-rendering state varian, membebaskan Main Thread untuk segera merespons sentuhan pengguna (visual feedback state transisi dipicu dalam < 30ms).
   - Mengimplementasikan non-blocking chunk yielding saat menyusun DOM opsi selector.

3. **Resolusi CLS**:
   - Menerapkan CSS Font Metric Overrides menggunakan `size-adjust`, `ascent-override`, dan `descent-override` untuk menyelaraskan geometri font fallback (Arial/Roboto) dengan custom web font:
     ```css
     @font-face {
       font-family: 'BrandCustomFont-Fallback';
       src: local('Arial');
       ascent-override: 92.5%;
       descent-override: 24.1%;
       line-gap-override: 0%;
       size-adjust: 102.3%;
     }

     :root {
       font-family: 'BrandCustomFont', 'BrandCustomFont-Fallback', sans-serif;
     }
     ```

#### Hasil Metrik Pasca Implementasi (Produksi)

| Metrik | Sebelum Optimasi (p75) | Setelah Optimasi (p75) | Peningkatan |
| :--- | :--- | :--- | :--- |
| **LCP** | 4.8 detik | 1.6 detik | **-66.6%** |
| **INP** | 680 ms | 78 ms | **-88.5%** |
| **CLS** | 0.28 | 0.015 | **-94.6%** |
| **Conversion Rate** | 2.1% | 2.74% | **+30.4% Relatif** |

---

### 9. Trade-Offs Architecture

```
                  [ ARCHITECTURE TRADE-OFF AXIS ]
                           High Compute
                                ^
                                │   SSR Hydration (Node.js)
                                │   - High Server Cost
                                │   - Fast LCP, High INP Risk (Uncanny Valley)
                                │
          Edge Streaming SSR    │
          - Lowest TTFB         │
          - Complex Cold Starts │
────────────────────────────────┼────────────────────────────────> Client Efficiency
                                │   Resumability / Islands Architecture
                                │   - Zero Hydration
                                │   - Tooling Migration Cost
                                │
     Client SPA (React CSR)     │
     - High Bandwidth / Low CPU │
     - Poor LCP / Bad SEO       │
                                v
                           Low Compute
```

| Strategi Arsitektur | Keuntungan | Kerugian & Batasan | Mitigasi Trade-off |
| :--- | :--- | :--- | :--- |
| **Full Client Hydration** (React/Vue Standard) | Arsitektur sederhana, rendering interaktif kaya state. | *Uncanny Valley*: Elemen terlihat (LCP tercapai) tetapi tombol tidak merespons hingga seluruh hydration JS selesai (INP spike). | Terapkan React 18 Selective Hydration dengan `React.lazy` dan `<Suspense>`. |
| **Resumability** (e.g., Qwik Engine) | Zero hydration footprint. Handler dieksekusi on-demand via URL serialization. INP mendekati instan (< 30ms). | Ekosistem dependensi lebih sempit; require architectural shift dari paradigma react hook konvensional. | Terapkan pada front-facing landing page dan catalog, batasi backend admin ke SPA standar. |
| **Aggressive Speculative Prerender** (`Speculation Rules API`) | Instan navigation (0ms TTFB/LCP untuk link internal). | Memboroskan bandwidth klien dan memori perangkat; beban request server melonjak 2-3x lipat jika salah prediksi. | Pasang batas threshold hover (> 200ms) sebelum memicu prerender, dan batasi hanya pada koneksi tanpa `Save-Data`. |
| **Offloading to Web Workers** | Menjamin Main Thread 100% bebas jank untuk event handling visual. | Overhead serialisasi data via structured clone transfer; tidak memiliki akses langsung ke DOM tree. | Gunakan `ArrayBuffer` transferrable objects untuk dataset biner besar guna menihilkan clone overhead. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Common Mistake: Layout Thrashing (Forced Synchronous Layout)
**Penyebab**: Membaca properti geometri layout DOM (`offsetHeight`, `clientWidth`, `getBoundingClientRect()`) sesaat setelah memodifikasi style DOM (`classList.add()`, `.style.width`), memaksa browser mengeksekusi pipeline *Layout (Reflow)* secara sinkron berulang kali di dalam loop.

*Contoh Buruk (Anti-pattern)*:
```typescript
// ANTI-PATTERN: Forced Reflow Loop
function resizeAllCards(cards: HTMLElement[]) {
  for (let i = 0; i < cards.length; i++) {
    // Write
    cards[i].style.width = '200px';
    // Read (Memicu relayout sinkron seketika untuk setiap iterasi)
    const height = cards[i].offsetHeight;
    cards[i].style.height = `${height * 1.5}px`;
  }
}
```

*Perbaikan (Pattern)*:
```typescript
// OPTIMAL PATTERN: Batch Reads First, Then Batch Writes
function resizeAllCardsOptimized(cards: HTMLElement[]) {
  // Fase 1: Batch Reads
  const heights = cards.map((card) => {
    card.style.width = '200px';
    return card.offsetHeight;
  });

  // Fase 2: Batch Writes via rAF
  requestAnimationFrame(() => {
    cards.forEach((card, index) => {
      card.style.height = `${heights[index] * 1.5}px`;
    });
  });
}
```

#### 10.2. Troubleshooting Flow: Mendiagnosis INP Tinggi pada Produksi

```
[INP Alert > 200ms]
         │
         ▼
[Identifikasi Event Type & Selector dari RUM Attribution]
         │
         ├──> Apakah Input Delay tinggi? (> 50ms)
         │       │
         │       └──> YES: Main Thread terblokir Long Task SEBELUM input terjadi.
         │                 Action: Profiling DevTools Performance -> Cari Macrotask durasi panjang / Microtask starvation.
         │
         ├──> Apakah Processing Time tinggi? (> 50ms)
         │       │
         │       └──> YES: Callback JavaScript lambat.
         │                 Action: Audit onClick/onChange. Pindahkan komputasi ke Web Worker / Terapkan scheduler.yield().
         │
         └──> Apakah Presentation Delay tinggi? (> 50ms)
                 │
                 └──> YES: Browser tercekik saat me-render efek hasil kalkulasi.
                           Action: Kurangi kompleksitas DOM Tree; hindari forced style recalculations; sederhanakan CSS selector.
```

---

### 11. Best Practices (Production Checklist)

#### Architectural Level
- [ ] Terapkan HTTP 103 Early Hints di CDN layer untuk critical CSS dan LCP assets.
- [ ] Setup Edge Caching dengan stale-while-revalidate policy untuk dynamic shell HTML.
- [ ] Terapkan `Speculation Rules API` selektif untuk pre-rendering rute target berikutnya berdasarkan user intent.

#### Resource & Asset Level
- [ ] Pastikan elemen LCP selalu memuat atribut `fetchpriority="high"` dan hindari penggunaan `loading="lazy"` pada viewport pertama.
- [ ] Sertakan dimensi rasio aspek (`width`/`height` rasio CSS) pada semua elemen image, video, dan dynamic iframe.
- [ ] Konfigurasikan font web dengan `font-display: optional` atau `font-display: swap` yang disertai metrik penyesuaian `@font-face` overrides (`size-adjust`).

#### JavaScript Execution & Scheduling Level
- [ ] Batasi total eksekusi single task JavaScript maksimal 50ms (idealnya < 16ms) menggunakan cooperative yielding (`scheduler.yield`).
- [ ] Bungkus state update non-urgent menggunakan concurrent scheduling (`useTransition` atau `scheduler.postTask(..., { priority: 'background' })`).
- [ ] Enkapsulasi heavy mathematical operations, cryptographic routines, dan heavy dataset manipulations ke dalam Web Worker pool.

#### Monitoring & Observability
- [ ] Integrasikan `PerformanceObserver` RUM agent dengan payload minimal dikompresi.
- [ ] Setup automated Performance Budget di CI/CD pipeline (e.g., bundle size delta $\le 5\%$, synthetic INP regression test via Lighthouse CI).
- [ ] Kirim telemetri CWV p75/p95 ke OpenTelemetry / Datadog / Grafana dengan korelasi release version git commit SHA.

---

### 12. Hands-on Practice

Buat direktori dan struktur file berikut di repository latihan Anda:
`hands-on/m02/`

```
hands-on/m02/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── main.ts
    ├── worker.ts
    ├── scheduler.ts
    └── font-style.css
```

#### Langkah 1: Inisialisasi Environment
Buat konfigurasi project menggunakan Vite dan TypeScript.

File: `hands-on/m02/package.json`
```json
{
  "name": "enterprise-performance-m02",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "vite": "^5.1.0"
  },
  "dependencies": {
    "comlink": "^4.4.1"
  }
}
```

File: `hands-on/m02/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ESNext",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ESNext", "DOM", "DOM.Iterable"],
    "moduleResolution": "Bundler",
    "strict": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

#### Langkah 2: Implementasi Worker Pipeline (Comlink)

File: `hands-on/m02/src/worker.ts`
```typescript
import * as Comlink from 'comlink';

export interface HeavyComputeService {
  computeMatrix(dataSize: number): number;
}

const service: HeavyComputeService = {
  computeMatrix(dataSize: number): number {
    let result = 0;
    // Simulasi komputasi intensif CPU
    for (let i = 0; i < dataSize * 1_000_000; i++) {
      result += Math.sqrt(i) * Math.sin(i);
    }
    return result;
  },
};

Comlink.expose(service);
```

#### Langkah 3: Implementasi Task Scheduler Engine

File: `hands-on/m02/src/scheduler.ts`
```typescript
export async function yieldToMain(): Promise<void> {
  if ('scheduler' in window && (window as any).scheduler?.yield) {
    return (window as any).scheduler.yield();
  }
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });
}
```

#### Langkah 4: Implementasi Main Application Logic & INP Benchmarking

File: `hands-on/m02/src/main.ts`
```typescript
import * as Comlink from 'comlink';
import { type HeavyComputeService } from './worker';
import { yieldToMain } from './scheduler';

// 1. Inisialisasi Web Worker via Comlink
const workerInstance = new Worker(new URL('./worker.ts', import.meta.url), {
  type: 'module',
});
const workerService = Comlink.wrap<HeavyComputeService>(workerInstance);

// 2. Setup DOM Elements
const app = document.getElementById('app')!;
app.innerHTML = `
  <div style="padding: 24px; font-family: sans-serif;">
    <h1>Enterprise Performance Engineering Testbed</h1>
    <div style="display: flex; gap: 12px; margin-bottom: 24px;">
      <button id="btn-blocking" style="padding: 8px 16px; background: #e53e3e; color: white;">Blocking Run (Bad INP)</button>
      <button id="btn-yielding" style="padding: 8px 16px; background: #dd6b20; color: white;">Cooperative Yielding Run</button>
      <button id="btn-worker" style="padding: 8px 16px; background: #38a169; color: white;">Worker Offloaded Run</button>
    </div>
    
    <div>
      <label>Interactivity Feedback Test (Type here fast while clicking buttons):</label><br />
      <input type="text" id="interactive-input" style="width: 100%; padding: 8px; margin-top: 8px;" placeholder="Ketik sesuatu di sini..." />
    </div>

    <div id="status-panel" style="margin-top: 24px; padding: 12px; background: #edf2f7; border-radius: 4px;">
      Status: Siap
    </div>
    
    <div id="render-target" style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 24px;"></div>
  </div>
`;

const statusPanel = document.getElementById('status-panel')!;
const renderTarget = document.getElementById('render-target')!;

// Skenario 1: Blocking execution (Long Task ~ 500ms)
document.getElementById('btn-blocking')!.addEventListener('click', () => {
  statusPanel.innerText = 'Status: Mengeksekusi secara sinkron (Main thread terblokir!)...';
  const start = performance.now();
  
  let val = 0;
  for (let i = 0; i < 50_000_000; i++) {
    val += Math.sqrt(i);
  }

  statusPanel.innerText = `Status: Selesai Blocking dalam ${(performance.now() - start).toFixed(2)}ms. Hasil: ${val.toFixed(2)}`;
});

// Skenario 2: Cooperative Task Yielding
document.getElementById('btn-yielding')!.addEventListener('click', async () => {
  statusPanel.innerText = 'Status: Mengeksekusi via Task Slicing & Cooperative Yielding...';
  const start = performance.now();

  const totalItems = 2000;
  renderTarget.innerHTML = '';
  let lastYield = performance.now();

  for (let i = 0; i < totalItems; i++) {
    const node = document.createElement('div');
    node.style.width = '12px';
    node.style.height = '12px';
    node.style.backgroundColor = `#${Math.floor(Math.random() * 16777215).toString(16)}`;
    renderTarget.appendChild(node);

    // Yield jika pengerjaan melebihi budget frame 16ms
    if (performance.now() - lastYield >= 16) {
      await yieldToMain();
      lastYield = performance.now();
    }
  }

  statusPanel.innerText = `Status: Selesai Yielding dalam ${(performance.now() - start).toFixed(2)}ms tanpa blocking.`;
});

// Skenario 3: Worker Offloading
document.getElementById('btn-worker')!.addEventListener('click', async () => {
  statusPanel.innerText = 'Status: Mengirim komputasi ke Background Web Worker...';
  const start = performance.now();

  const result = await workerService.computeMatrix(50);

  statusPanel.innerText = `Status: Worker selesai dalam ${(performance.now() - start).toFixed(2)}ms. Hasil: ${result.toFixed(2)}`;
});

// PerformanceObserver untuk logging INP & Long Tasks ke console
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.duration > 50) {
      console.warn(`[LONG TASK DETECTED]: ${entry.duration.toFixed(2)}ms`, entry);
    }
  }
});
observer.observe({ entryTypes: ['longtask'] });
```

File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Enterprise Performance Engineering</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

#### Langkah Menjalankan Hands-on
1. Masuk ke direktori: `cd hands-on/m02`
2. Pasang dependencies: `npm install`
3. Jalankan development server: `npm run dev`
4. Buka DevTools -> Tab **Performance** -> Throttle CPU ke **6x slowdown**.
5. Uji tombol "Blocking Run" sambil mengetik secara simultan di input box untuk mengamati freeze/lag (INP > 500ms).
6. Uji tombol "Cooperative Yielding" dan "Worker Offloaded Run" sambil mengetik untuk membuktikan bahwa UI tetap mulus (INP < 50ms).

---

### 13. Exercises

#### Level Easy
Pada dokumen HTML dinamis, slot iklan (*ad slot*) sering menyebabkan lonjakan CLS karena ukuran container belum ditentukan sebelum iframe iklan selesai dimuat. Modifikasi komponen berikut agar memiliki nilai CLS 0 menggunakan teknik CSS Modern Containment.
- **Tugas**: Perbaiki markup dan CSS agar slot iklan berukuran tetap 300x250px memiliki reserved space sebelum aset termuat tanpa memicu layout recalculation beruntun.

#### Level Medium
Buat sebuah wrapper function `debounceWithYield<T extends (...args: any[]) => any>` yang menerima sebuah callback pemrosesan input pencarian teks. Wrapper ini harus:
1. Mendebounce input selama 250ms.
2. Membagi kalkulasi filtering data (100.000 records) menggunakan `scheduler.yield()` setiap 12ms.
3. Mengembalikan Promise berisi data yang telah difilter tanpa memicu blocking frame > 50ms saat diinspeksi via Chrome DevTools Performance Profiler.

#### Level Hard
Rancang dan bangun arsitektur mini library **Speculative Route Prefetcher** berbasis TypeScript:
- Pantau posisi kursor mouse pengguna dan viewport intersection link internal (`<a>` tag) menggunakan `IntersectionObserver`.
- Jika sebuah link masuk ke viewport *dan* mouse bergerak mendekati radius 50px dari link tersebut (atau di-hover $\ge 65\text{ms}$), daftarkan URL ke dalam script `type="speculationrules"` secara dinamis di runtime DOM.
- Matikan fungsionalitas jika browser klien terdeteksi mengaktifkan mode hemat daya/data (`navigator.connection.saveData === true`) atau menggunakan koneksi lambat (`effectiveType === '2g'`).

---

### 14. Real-World Architectural Challenge

#### Skenario Kasus:
Anda adalah Principal Performance Architect pada aplikasi Web Real-Time Financial Trading (*Brokerage Platform*). Aplikasi ini menerima hingga 5.000 update harga instrumen (tick updates) per detik melalui WebSocket.

#### Kondisi Aktual:
1. Setiap pesan tick WebSocket memicu kalkulasi ulang Profit & Loss (P&L) portofolio klien dan memperbarui grafik visual SVG/Canvas.
2. Ketika pasar mengalami volatilitas ekstrem (surge volume), browser klien mengalami kondisi UI freeze: interaksi tombol eksekusi trading "Sell/Buy" memiliki latensi INP sebesar **1.450ms**, yang mengakibatkan komplain kegagalan eksekusi order pada harga yang diharapkan (slippage).
3. DOM Memory footprint terus meningkat tajam (*Memory Leak* bertahap) dan garbage collection (GC) memblokir Main Thread rata-rata 120ms setiap siklus 10 detik.

#### Tugas Rekayasa:
Rancang dokumen arsitektur dan cetak biru teknis lengkap (High-Level Design & Pseudo-Engine Architecture):
1. **WebSocket Ingestion & Buffering Architecture**: Bagaimana Anda memisahkan konsumsi soket dari Main Thread?
2. **Data Aggregation & Throttling Strategy**: Bagaimana Anda mengelola 5.000 tick/detik agar sesuai dengan batasan refresh rate monitor pengguna (60Hz / 120Hz) tanpa kehilangan data analitik?
3. **Decoupled Execution Pipeline**: Bagaimana Anda memisahkan path visual rendering (Canvas) dan path kritikal eksekusi order (INP priority) menggunakan Web Workers, `OffscreenCanvas`, dan Task Priority Scheduling (`scheduler.postTask`)?

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa metrik Interaction to Next Paint (INP) lebih representatif terhadap pengalaman nyata pengguna dibandingkan First Input Delay (FID)?
2. Apa perbedaan mendasar antara tugas yang dialokasikan ke Microtask Queue (seperti `Promise.then`) dan Macrotask Queue (seperti `MessageChannel` atau `setTimeout`) terkait dampaknya terhadap rendering frame browser?
3. Pada fase rendering Blink engine, atribut CSS apakah yang secara eksklusif dapat diproses langsung oleh *Compositor Thread* tanpa memicu *Layout* atau *Paint* ulang pada Main Thread?
4. Mengapa menyematkan atribut `loading="lazy"` pada gambar Largest Contentful Paint (LCP) dianggap sebagai anti-pattern performa yang parah?
5. Bagaimana browser menghitung *Distance Fraction* pada metrik Cumulative Layout Shift (CLS)?

#### 5 Pertanyaan Intermediate
6. Jelaskan mekanisme kerja internal `scheduler.yield()` dan mengapa implementasi fallback berbasis `MessageChannel` secara teknis lebih unggul daripada `setTimeout(fn, 0)`.
7. Apa yang dimaksud dengan fenomena *Uncanny Valley* pada aplikasi Single Page Application yang menggunakan Full Hydration SSR standar, dan bagaimana mitigasinya?
8. Bagaimana implementasi HTTP 103 Early Hints dapat memotong *Resource Load Delay* pada LCP dibandingkan dengan deklarasi tag `<link rel="preload">` di dalam dokumen HTML?
9. Jelaskan bagaimana *Forced Synchronous Layout* (Layout Thrashing) terjadi ketika kode membaca properti `element.scrollHeight` sesaat setelah mengubah `element.style.height`.
10. Dalam kondisi apa `navigator.sendBeacon()` dapat gagal mengirimkan data telemetri RUM, dan bagaimana pola fallback enterprise yang tepat untuk mengatasinya?

#### 3 Skenario Kasus Produksi
11. **Skenario A**: Tim frontend melaporkan bahwa setelah beralih ke dynamic custom web font, skor CLS melonjak dari 0.02 menjadi 0.22, meskipun layout container teks telah didefinisikan dengan lebar tetap (`width: 100%`). Inspeksi DevTools menunjukkan layout shift terjadi tepat pada saat text rendering beralih dari font fallback ke web font. Solusi tingkat rendah apa yang wajib diimplementasikan?
12. **Skenario B**: Dashboard analytics menampilkan bahwa LCP p75 di workstation developer adalah 1.1s, namun telemetry RUM di produksi mencatat nilai LCP p75 sebesar 4.2s khusus untuk segmen pengguna mobile di wilayah dengan jaringan intermiten. Analisis breakdown LCP menunjukkan bahwa *Resource Load Duration* adalah kontributor 70% dari durasi tersebut. Tindakan optimasi apa yang paling efektif?
13. **Skenario C**: Sebuah modul autocomplete search input memiliki skor INP buruk (340ms). Profiling menunjukkan bahwa 80ms dihabiskan untuk eksekusi query filtering array di dalam memory, dan 220ms dihabiskan untuk *Presentation Delay* saat framework merender ulang 500 node komponen DOM list item. Bagaimana restrukturisasi arsitektur rendering komponen ini untuk menurunkan INP ke < 50ms?

---

### Kunci Jawaban & Rubrik Penilaian Quiz

#### Jawaban Basic
1. FID hanya mengukur latensi dari interaksi *pertama kali* saja saat halaman dimuat (hanya mengukur *Input Delay*). INP mengukur *keseluruhan* interaksi pengguna sepanjang sesi halaman dibuka, mencakup waktu *Input Delay*, *Processing Time*, hingga *Presentation Delay* (frame baru benar-benar muncul di layar).
2. Microtask queue dieksekusi sampai tuntas (drained completely) sebelum browser diizinkan kembali melanjutkan eksekusi tugas berikutnya atau me-render frame. Terlalu banyak microtask akan menyebabkan *Microtask Starvation* dan membekukan render frame. Macrotask memungkinkan browser menyisipkan proses render di antara task-task yang berbeda.
3. Properti `transform` dan `opacity`. Keduanya dapat dialihkan eksekusinya langsung ke Compositor Thread dan GPU tanpa memicu kalkulasi ulang geometri layout atau raster ulang display list pada Main Thread.
4. Karena `loading="lazy"` menginstruksikan browser engine untuk menunda unduhan gambar sampai browser selesai menghitung posisi layout dan memastikan aset dekat dengan viewport. Ini menambahkan *Resource Load Delay* yang sangat besar pada gambar yang seharusnya menjadi elemen LCP utama di atas viewport (*above-the-fold*).
5. *Distance Fraction* adalah jarak pergeseran terbesar dari elemen yang tidak stabil dalam viewport dibagi dengan dimensi dimensi terbesar viewport (lebar atau tinggi).

#### Jawaban Intermediate
6. `scheduler.yield()` secara khusus menangguhkan eksekusi JS saat ini, mengembalikan kontrol ke browser untuk memproses pending visual rendering atau input events, lalu melanjutkan eksekusi task persis setelahnya tanpa kehilangan prioritas task context. `MessageChannel` mengeksekusi callback pada task queue berikutnya tanpa delay artifisial, sedangkan `setTimeout(fn, 0)` memiliki spesifikasi standar HTML berupa minimum clamping delay 4ms jika kedalaman nesting timer $\ge 5$.
7. *Uncanny Valley* adalah kondisi di mana SSR berhasil menyajikan HTML dan CSS lengkap dengan cepat (konten visual terlihat fungsional bagi mata pengguna), tetapi kode JavaScript hydration belum selesai dieksekusi. Ketika pengguna mengklik tombol interaktif, aplikasi tidak memberikan respons apa pun karena event listeners belum terpasang. Mitigasi: Selective/Progressive Hydration, Streaming SSR, atau arsitektur Resumability.
8. HTTP 103 Early Hints dikirimkan oleh server/edge sesaat setelah request diterima, mendahului pembuatan atau eksekusi streaming dokumen HTML utama. Browser dapat memulai koneksi TLS handshake dan mengunduh LCP image paralel sebelum byte pertama HTML selesai di-generate oleh server application.
9. Ketika properti style diubah (`element.style.height`), browser menandai internal layout tree sebagai *dirty*. Begitu baris berikutnya membaca `element.scrollHeight`, browser terpaksa menghentikan eksekusi JavaScript engine dan melakukan kalkulasi geometri layout seketika (*forced synchronous reflow*) agar dapat mengembalikan nilai ukuran yang akurat kepada kode JS.
10. `navigator.sendBeacon()` dapat gagal jika ukuran payload melebihi kuota buffer browser (biasanya 64KB per proses), atau ketika proses browser ditutup paksa (*force kill process* oleh OS). Fallback pattern: Batasi ukuran queue telemetry, kompresi payload, dan sediakan fallback ke API `fetch` dengan properti `{ keepalive: true }`.

#### Jawaban Skenario Kasus Produksi
11. **Solusi Skenario A**: Terapkan Font Metric Overrides menggunakan aturan CSS `@font-face` dengan mendeklarasikan fallback font lokal yang diselaraskan geometrinya (`size-adjust`, `ascent-override`, `descent-override`, `line-gap-override`) agar bounding-box huruf dari font sistem sama persis dengan font kustom sebelum file font terunduh, serta setel `font-display: optional` untuk meniadakan pergeseran layout jika font telat terunduh.
12. **Solusi Skenario B**: Terapkan format modern dengan kompresi superior (AVIF/WebP), integrasikan dynamic responsive image (`srcset` dan `sizes`) agar perangkat mobile tidak mengunduh resolusi desktop, prioritaskan aset via `fetchpriority="high"`, dan tempatkan media delivery di Edge CDN multi-region yang mengaktifkan kompresi HTTP/3 QUIC untuk mengurangi dampak packet-loss pada jaringan seluler.
13. **Solusi Skenario C**:
   - Pindahkan filtering array data ke Web Worker atau pecah komputasi menggunakan `scheduler.yield()`.
   - Untuk Presentation Delay: Terapkan *Virtual Scrolling* (windowing via `@tanstack/virtual` atau setara) sehingga browser hanya merender sejumlah DOM node yang muat di viewport pengguna (misal 10 node saja, bukan 500 node).
   - Bungkus update input rendering state menggunakan API `startTransition` (Concurrent React) agar input feedback teks dapat dirender instan pada frame berikutnya mendahului render list hasil pencarian.

---

### 16. Summary

1. **Core Web Vitals Engineering** bukan sekadar optimasi frontend kosmetik, melainkan rekayasa sistem yang menuntut pemahaman menyeluruh terhadap arsitektur internal browser engine (koordinasi Main Thread, Compositor, dan GPU Rasterization).
2. **LCP Mitigations** bertumpu pada eliminasi delay rantai jaringan: implementasi HTTP 103 Early Hints, penempatan aset pada CDN edge, dan penandaan prioritas eksplisit (`fetchpriority="high"`).
3. **INP Governance** mewajibkan penghapusan Long Tasks (> 50ms) dari Main Thread melalui transisi ke cooperative multitasking (`scheduler.yield()`), prioritas tugas (`scheduler.postTask()`), dan pemisahan komputasi data berat ke Web Worker pool.
4. **CLS Defense** dicapai melalui determinasi geometri layout statis: penerapan CSS containment, eksplisit rasio media visual, serta teknik font metric matching untuk meniadakan FOUT shift.
5. **Production Observability**: Mengganti metrik berbasis audit sintetis statis dengan arsitektur Real User Monitoring (RUM) menggunakan `PerformanceObserver` dan distributed telemetry beaconing yang mengukur p75 dan p95 beban kerja pengguna nyata.