# Bab 07 Module 01: Performance Engineering & Core Web Vitals

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** Frontend & Mobile Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Modul:** Bab 07 Module 01
* **Topik Utama:** Performance Engineering & Core Web Vitals (INP, LCP, CLS, TTFB, FCP)
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat Teknis:** Pemahaman mendalam mengenai JavaScript Event Loop, Browser Rendering Engine (Blink/Gecko), DOM Parsing lifecycle, HTTP/2 & HTTP/3 networking layer, dan Performance Observer API.

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. Menganalisis siklus render browser secara atomik (Parse HTML -> Recalculate Styles -> Layout -> Paint -> Composite) dan mengidentifikasi bottleneck eksekusi JavaScript pada Main Thread.
2. Membedah, mengukur, dan mengoptimalkan metrik Core Web Vitals modern: **Largest Contentful Paint (LCP)**, **Interaction to Next Paint (INP)** (menggantikan FID), dan **Cumulative Layout Shift (CLS)**, beserta metrik diagnostik penunjang (**TTFB**, **FCP**).
3. Mengimplementasikan telemetri Real User Monitoring (RUM) native menggunakan `PerformanceObserver` API untuk dikirim ke edge collector endpoint tanpa membebani Main Thread.
4. Mendiagnosis jank, long tasks (>50ms), dan layout thrashing menggunakan Chrome DevTools Performance Profiler, serta mengeliminasi long animation frames (LoAF).
5. Merancang arsitektur web modern yang menjamin skor Core Web Vitals berada pada persentil ke-75 (p75) kategori "Good" pada skala jutaan pengguna konkuren.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model: The Frame Budget & Thread Ownership
Browser adalah sistem penjadwalan berbasis frame yang bekerja di bawah batas waktu perangkat keras. Pada layar 60Hz, batas waktu pemrosesan sebuah frame adalah **16.67ms**; pada layar 120Hz, batas tersebut menyusut menjadi **8.33ms**. 

```
┌─────────────────────────────────────────────────────────────┐
│ Frame Budget (16.6ms @ 60Hz)                                │
├──────────────────────────────────────┬──────────────────────┤
│ JavaScript Execution, Style, Layout  │ Paint, Composite, GPU│
│ [=========== MAIN THREAD ===========]│ [=== GPU THREAD ===] │
└──────────────────────────────────────┴──────────────────────┘
```

Jika pekerjaan Main Thread melampaui batas ini, frame akan terpotong (*dropped frame*), menyebabkan *jank*. 

Performance Engineering bukanlah aktivitas ad-hoc yang dilakukan di akhir siklus pengembangan dengan cara menambahkan `React.lazy()` atau mengompresi gambar. Performance Engineering adalah **analisis batasan sistem (system constraint analysis)**. 

Setiap baris kode CSS, HTML, dan JavaScript memperebutkan dua sumber daya yang terbatas:
1. **Network Bandwidth & Latency:** Seberapa cepat byte ditransfer dan didekompresi dari server/CDN ke memori browser.
2. **Main Thread Compute Time:** Seberapa efisien CPU mengurai (parse), mengompilasi, mengeksekusi JavaScript, menghitung kalkulasi geometri (Layout), dan mendistribusikan layer ke Compositor Thread.

Pola pikir Staff Engineer:
* Jangan berasumsi; ukur menggunakan **Field Data (Real User Monitoring)**, bukan hanya **Lab Data (Lighthouse)**. Lighthouse dijalankan pada CPU terisolasi dengan koneksi simulasi; RUM mencerminkan fragmentasi perangkat dunia nyata (low-end Android, fluktuasi jaringan seluler, ekstensi browser pengguna).
* Main Thread browser bersifat kooperatif (*cooperative scheduling*). Tugas Anda adalah mencegah tugas monolitik (Long Tasks) dengan memecahnya (*chunking*) agar Main Thread dapat merespons input pengguna dalam kurun waktu kurang dari 50 milidetik.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Alur Rendering Pipeline Browser & Korelasi Core Web Vitals

```
Network / Server                  Main Thread Pipeline                     Compositor / Screen
─────────────────                 ────────────────────                     ───────────────────
      │                                     │                                       │
[HTTP Request]                              │                                       │
      │ ─── (TTFB Phase)                    │                                       │
[First Byte Arrives]                        │                                       │
      │ ─── HTML Parsing ─────────────────> │                                       │
      │                                [DOM Parser]                                 │
      │                                     │                                       │
[CSS/Subresources]                          │ ── Style Recalculation                │
      │ ─── (FCP Occurs) ─────────────────> │         │                             │
      │                                     │      [Layout] (Geometry calculation)  │
      │                                     │         │                             │
[LCP Candidate Loaded]                      │      [Pre-Paint]                      │
 (Image/Text Node)                          │         │                             │
      │ ─── (LCP Finalized) ──────────────> │      [Paint] (Display Lists)          │
      │                                     │         │                             │
      │                                     │   [Commit/Tile] ────────────────────> │
      │                                     │                                 [Compositing]
      │                                     │                                       │
      │                                     │                                [GPU Raster]
      │                                     │                                       │
      │                                     │                              [Pixel to Screen]
      │                                     │                                       │
      │                         ┌───────────┴───────────┐                           │
      │                         │  User Interaction     │                           │
      │                         │  (Click, Keydown)     │                           │
      │                         └───────────┬───────────┘                           │
      │                                     │                                       │
      │                                [Input Delay] ── (INP Phase 1)               │
      │                                     │                                       │
      │                           [Event Callbacks] ─── (INP Phase 2: Processing)   │
      │                                     │                                       │
      │                            [Style/Layout]                                   │
      │                                     │                                       │
      │                         [Presentation Delay] ── (INP Phase 3) ────────────> │
      │                                                                        [Next Paint]
```

### Penjelasan Diagram Alur:
1. **Time to First Byte (TTFB):** Mengukur latensi jaringan dan durasi pemrosesan backend dari navigasi inisial hingga byte pertama HTML diterima.
2. **First Contentful Paint (FCP):** Waktu yang dibutuhkan browser untuk merender elemen DOM pertama (teks, gambar non-putih, canvas).
3. **Largest Contentful Paint (LCP):** Mengukur waktu render elemen visual terbesar di dalam viewport (biasanya gambar hero, blok teks `<h1>`, atau poster video).
4. **Interaction to Next Paint (INP):** Menghitung latensi terpanjang interaksi pengguna sepanjang siklus hidup halaman, dihitung dari:
   $$\text{INP} = \text{Input Delay} + \text{Processing Duration} + \text{Presentation Delay}$$
5. **Cumulative Layout Shift (CLS):** Akumulasi skor pergeseran layout tak terduga (*unexpected shift*) selama elemen DOM bergerak setelah di-render tanpa intervensi interaksi pengguna langsung.

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Largest Contentful Paint (LCP) Internals
LCP diidentifikasi oleh API browser melalui algoritma seleksi heuristik. Browser memantau elemen-elemen berikut yang berada di viewport:
* Elemen `<img>` (dan gambar di dalam elemen `<svg>`).
* Elemen `<video>` (menggunakan poster frame atau paint pertama frame video).
* Elemen dengan background image yang dimuat melalui fungsi CSS `url()`.
* Node teks tingkat blok (misalnya `<h1>`, `<p>`, atau inline text nodes yang dibungkus blok).

Ukuran elemen dihitung berdasarkan luas visual yang terlihat di viewport pengguna. Jika elemen diperkecil dari ukuran aslinya, ukuran yang dilaporkan adalah ukuran render terkecil. Sebaliknya, jika elemen ditarik (*stretched*), ukuran intrinsik terkecil yang digunakan. Browser berhenti mengirimkan kandidat `LargestContentfulPaint` baru begitu pengguna melakukan interaksi pertama (klik atau penekanan tombol).

Sub-parts dari durasi LCP terdiri dari 4 metrik independen:
$$\text{LCP Time} = \text{TTFB} + \text{Resource Load Delay} + \text{Resource Load Duration} + \text{Element Render Delay}$$
* **Resource Load Delay:** Waktu antara respons HTML pertama tiba hingga browser menemukan resource LCP (misalnya karena tertanam di dalam CSS eksternal alih-alih tag `<img>` di HTML murni).
* **Resource Load Duration:** Waktu aktual pengunduhan aset LCP dari jaringan.
* **Element Render Delay:** Waktu antara aset selesai diunduh hingga browser selesai melakukan decode, layout, dan paint ke layar.

### 2. Interaction to Next Paint (INP) Internals
INP menggantikan FID (First Input Delay). Jika FID hanya mengukur penundaan awal sebelum handler dieksekusi pada interaksi pertama, INP mengukur interaksi holistik di seluruh lifecycle aplikasi:

```
Interaction Lifecycle:
├── 1. Input Delay ──────────> (Terkendala oleh task lain yang sedang berjalan di Main Thread)
├── 2. Processing Time ─────> (Waktu eksekusi semua callback event: pointerdown, click, dll)
└── 3. Presentation Delay ───> (Recalculate Style, Layout, Compositor scheduling, GPU buffer swap)
```

Browser mengamati semua interaksi via pointer (klik, tap) dan keyboard. Untuk setiap interaksi, waktu dimulai ketika pengguna memulai input fisik dan berakhir ketika browser telah memperbarui buffer tampilan layar (Next Paint). Nilai INP halaman adalah interaksi dengan latensi terburuk (atau persentil ke-98 pada halaman dengan ratusan interaksi).

### 3. Cumulative Layout Shift (CLS) Internals
CLS mengukur instabilitas visual. Algoritma browser menghitung **Layout Shift Score**:
$$\text{Layout Shift Score} = \text{Impact Fraction} \times \text{Distance Fraction}$$
* **Impact Fraction:** Persentase area viewport yang terdampak oleh pergeseran elemen yang tidak stabil di antara dua frame. Jika sebuah elemen mencakup 50% viewport dan bergeser ke bawah sebesar 20% viewport, total area terdampak adalah $50\% + 20\% = 70\%$ (Impact Fraction = 0.70).
* **Distance Fraction:** Jarak pergeseran horizontal atau vertikal terbesar dibagi dengan dimensi terbesar viewport (lebar atau tinggi). Jika elemen bergeser sejauh 200px pada layar setinggi 1000px, Distance Fraction = $200 / 1000 = 0.20$.
* **Skor Shift:** $0.70 \times 0.20 = 0.14$.

Layout shifts dikelompokkan ke dalam "Session Windows". Sebuah sesi berakhir ketika jeda antar-shift melampaui 1 detik, atau durasi total sesi mencapai 5 detik. CLS adalah skor jendela sesi tertinggi yang tercatat selama lifecycle dokumen.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Long Animation Frames API (LoAF) vs Long Tasks
Secara historis, Main Thread bottleneck diidentifikasi melalui **Long Tasks API** (setiap task di Main Thread yang berjalan $> 50\text{ms}$). Namun, Long Tasks memiliki kelemahan mendasar:
1. Tidak memberikan konteks *render phase* (kapan layout dan paint terjadi).
2. Tidak mengidentifikasi secara detail file JavaScript atau fungsi spesifik mana yang menyebabkan blocking (*culprit script attribution*).

Browser modern mengadopsi **Long Animation Frames (LoAF)** API (W3C standard). LoAF mengukur durasi siklus animasi render yang melampaui $50\text{ms}$. Siklus ini mencakup pemrosesan input event, timer, UI updates, serta tahapan `requestAnimationFrame`, layout, dan paint.

```
Long Task Boundary:
[ Task Execution > 50ms ] -> Pelaporan blind tanpa konteks render.

Long Animation Frame (LoAF) Boundary:
├─ Microtasks & UI Event Listeners
├─ requestAnimationFrame Callbacks
├─ Style Recalculation
├─ Layout Engine Computation
└─ Paint Execution
   └── Melaporkan script URL, function name, source offset, dan char position.
```

### Mekanisme Kerja Yielding to Main Thread
Ketika JavaScript mengeksekusi kalkulasi besar secara sinkron, eksekusi tersebut memonopoli Main Thread. Untuk mengembalikan responsivitas Main Thread tanpa membatalkan kalkulasi, kita harus melakukan *yielding* (menyerahkan kendali kembali ke event loop).

Secara internal:
1. **`setTimeout(fn, 0)`**: Memasukkan macrotask baru ke dalam Macrotask Queue. Masalah: Browser memberlakukan minimum clamping delay sebesar $\approx 4\text{ms}$ jika nesting level $> 5$, serta menempatkan task di belakang I/O events lainnya secara non-deterministik.
2. **`requestAnimationFrame(fn)`**: Berjalan *sebelum* paint frame berikutnya. Ini berguna untuk mutasi visual, tetapi tidak cocok untuk yielding eksekusi komputasi latar belakang karena dapat menunda rendering.
3. **`scheduler.yield()`**: Standar native modern. Membuat continuous microtask-like continuation yang secara spesifik menyerahkan Main Thread ke browser scheduler, memeriksa antrean interaksi input, mengeksekusi paint yang tertunda, dan segera melanjutkan eksekusi kode kita tanpa penundaan overhead timer.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Implementasi custom telemetri RUM yang mengamati **LCP**, **INP**, dan **CLS** menggunakan `PerformanceObserver` tingkat rendah tanpa pustaka pihak ketiga.

```typescript
// CoreWebVitalsCollector.ts

export interface MetricPayload {
  name: 'LCP' | 'INP' | 'CLS';
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  navigationPreload?: number;
  entries: PerformanceEntry[];
}

export class CoreWebVitalsCollector {
  private clsScore: number = 0;
  private clsEntries: PerformanceEntry[] = [];
  private sessionValue: number = 0;
  private sessionEntries: PerformanceEntry[] = [];
  private onMetric: (metric: MetricPayload) => void;

  constructor(callback: (metric: MetricPayload) => void) {
    this.onMetric = callback;
    this.initLCPObserver();
    this.initCLSObserver();
    this.initINPObserver();
  }

  private getRating(name: MetricPayload['name'], value: number): MetricPayload['rating'] {
    const thresholds = {
      LCP: { good: 2500, poor: 4000 },
      INP: { good: 200, poor: 500 },
      CLS: { good: 0.1, poor: 0.25 },
    };

    if (value <= thresholds[name].good) return 'good';
    if (value <= thresholds[name].poor) return 'needs-improvement';
    return 'poor';
  }

  private initLCPObserver(): void {
    if (!PerformanceObserver.supportedEntryTypes.includes('largest-contentful-paint')) {
      return;
    }

    const observer = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries();
      const lastEntry = entries[entries.length - 1] as PerformanceEntry;

      this.onMetric({
        name: 'LCP',
        value: lastEntry.startTime,
        rating: this.getRating('LCP', lastEntry.startTime),
        entries: [lastEntry],
      });
    });

    observer.observe({ type: 'largest-contentful-paint', buffered: true });
  }

  private initCLSObserver(): void {
    if (!PerformanceObserver.supportedEntryTypes.includes('layout-shift')) {
      return;
    }

    const observer = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries() as any[]) {
        // Abaikan shift yang dipicu oleh interaksi pengguna (hadRecentInput = true)
        if (!entry.hadRecentInput) {
          const firstSessionEntry = this.sessionEntries[0];
          const lastSessionEntry = this.sessionEntries[this.sessionEntries.length - 1];

          // CLS Session Window Logic (max 5s, gap max 1s)
          if (
            this.sessionValue &&
            entry.startTime - lastSessionEntry.startTime < 1000 &&
            entry.startTime - firstSessionEntry.startTime < 5000
          ) {
            this.sessionValue += entry.value;
            this.sessionEntries.push(entry);
          } else {
            this.sessionValue = entry.value;
            this.sessionEntries = [entry];
          }

          if (this.sessionValue > this.clsScore) {
            this.clsScore = this.sessionValue;
            this.clsEntries = this.sessionEntries;

            this.onMetric({
              name: 'CLS',
              value: this.clsScore,
              rating: this.getRating('CLS', this.clsScore),
              entries: this.clsEntries,
            });
          }
        }
      }
    });

    observer.observe({ type: 'layout-shift', buffered: true });
  }

  private initINPObserver(): void {
    if (!PerformanceObserver.supportedEntryTypes.includes('event')) {
      return;
    }

    let maxDuration = 0;
    let worstEntry: PerformanceEntry | null = null;

    const observer = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries() as any[];

      for (const entry of entries) {
        // Hanya pantau interaksi yang valid dan memiliki interactionId
        if (entry.interactionId) {
          const duration = entry.duration;
          if (duration > maxDuration) {
            maxDuration = duration;
            worstEntry = entry;

            this.onMetric({
              name: 'INP',
              value: maxDuration,
              rating: this.getRating('INP', maxDuration),
              entries: [worstEntry],
            });
          }
        }
      }
    });

    // durationThreshold 16ms memastikan kita menangkap interaksi bermasalah (> 1 frame)
    observer.observe({
      type: 'event',
      durationThreshold: 16,
      buffered: true,
    } as any);
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 24-34 (`getRating`)**: Menentukan batas ambang metrik sesuai standar World Wide Web Consortium (W3C) dan Google Web Vitals:
  * LCP: $\le 2500\text{ms}$ (Good), $> 4000\text{ms}$ (Poor).
  * INP: $\le 200\text{ms}$ (Good), $> 500\text{ms}$ (Poor).
  * CLS: $\le 0.1$ (Good), $> 0.25$ (Poor).
* **Baris 48 (`buffered: true`)**: Menjamin bahwa entri yang dihitung *sebelum* skrip telemetry dieksekusi tetap diambil dari buffer memori browser. Tanpa flag ini, metrics awal halaman akan hilang.
* **Baris 61 (`!entry.hadRecentInput`)**: Pengecekan penting untuk CLS. Jika pengguna baru saja mengklik layar dalam $500\text{ms}$ terakhir, layout shift dianggap sebagai respon valid dari aksi pengguna dan *tidak* dimasukkan ke dalam metrik CLS.
* **Baris 67-73 (Session Window Algorithm)**: Mengelompokkan layout shifts ke dalam sesi jendela waktu dinamis. Jika ada jeda lebih dari $1000\text{ms}$ atau rentang total melebihi $5000\text{ms}$, sesi baru dimulai. Ini mencegah bias penalti pada Single Page Applications (SPA) yang berjalan lama.
* **Baris 97 (`entry.interactionId`)**: Membedakan input native individual (seperti `pointerdown`, `pointerup`) yang tergabung dalam satu interaksi holistik yang sama. Nilai non-nol menjamin korelasi metrik terhadap interaksi riil pengguna.
* **Baris 113 (`durationThreshold: 16`)**: Memerintahkan engine browser untuk memfilter entri interaksi yang selesai di bawah $16\text{ms}$ (1 frame pada 60Hz), mengurangi overhead pemrosesan telemetri di Main Thread.

---

## SEKSI 09 — STUDI KASUS NYATA
**Skenario Produksi:** Sebuah platform Enterprise B2B Dashboard Analytics (1.500.000 DAU) mengalami penurunan drastis pada kepuasan pelanggan dan penurunan skor SEO secara global.

### Problem Breakdown:
1. **LCP = 5.8 detik (Poor):** Komponen tabel analitik utama memuat data via GraphQL, menunggu bundle JavaScript monolitik sebesar 4.2 MB di-download dan di-parse terlebih dahulu, baru kemudian membuat container DOM dan mengunduh hero metric image.
2. **INP = 680 milidetik (Poor):** Setiap kali pengguna memilih rentang tanggal (*Date Range Picker*) atau memfilter baris tabel, terjadi blocking di Main Thread selama ratusan milidetik. Hal ini disebabkan oleh komputasi kalkulasi finansial ribuan baris array yang dilakukan secara sinkron, memicu rekalkulasi style masif di seluruh DOM tree.
3. **CLS = 0.42 (Poor):** Saat chart dimuat, container chart tidak memiliki dimensi eksplisit (`height: auto`). Ketika library visualisasi (Canvas/SVG) selesai dimuat, chart di-render dan menggeser seluruh tabel transaksi ke bawah sebesar 400px.

### Solusi Arsitektural:
* **LCP:** Mengimplementasikan *Speculative Pre-rendering*, konversi Hero Image ke format WebP/AVIF modern, penambahan tag `<link rel="preload">`, serta pemecahan *Critical Rendering Path* dengan *CSS Inlining* dan *Code Splitting* level rute.
* **INP:** Memindahkan kalkulasi matematis dataset ke **Dedicated Web Worker** menggunakan OffscreenCanvas, serta menerapkan scheduler task-chunking via `scheduler.yield()`.
* **CLS:** Menerapkan CSS `contain-intrinsic-size` dan rasio aspek eksplisit (`aspect-ratio`) pada visualisasi grafik analitik.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Solusi menyeluruh yang mengatasi masalah **INP** (menggunakan *chunked execution* dan `scheduler.yield`), **CLS** (menggunakan CSS aspect ratio container), serta transmisi telemetri via `navigator.sendBeacon`.

### 1. Core Scheduling Optimizer Engine (`SchedulerOptimizer.ts`)

```typescript
// SchedulerOptimizer.ts

/**
 * Polyfill/Wrapper untuk scheduler.yield() dengan fallback ke MessageChannel
 * untuk mencegah timer clamping 4ms dari setTimeout.
 */
export async function yieldToMainThread(): Promise<void> {
  // Gunakan native implementation jika tersedia di browser modern
  if ('scheduler' in window && 'yield' in (window as any).scheduler) {
    return await (window as any).scheduler.yield();
  }

  // Fallback performan menggunakan MessageChannel (Macrotask Queue tanpa 4ms clamp)
  return new Promise((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });
}

/**
 * Memecah komputasi masif menjadi batch-batch kecil yang ramah Main Thread (INP < 50ms)
 */
export async function processLargeDatasetInChunks<T, R>(
  items: T[],
  processor: (item: T) => R,
  maxChunkTimeMs: number = 16
): Promise<R[]> {
  const results: R[] = [];
  let lastYieldTime = performance.now();

  for (let i = 0; i < items.length; i++) {
    results.push(processor(items[i]));

    const currentTime = performance.now();
    // Jika eksekusi telah berjalan melebihi alokasi chunk (frame budget), serahkan thread
    if (currentTime - lastYieldTime >= maxChunkTimeMs) {
      await yieldToMainThread();
      lastYieldTime = performance.now();
    }
  }

  return results;
}
```

### 2. High-Performance Dashboard View Component (`AnalyticsDashboard.ts`)

```typescript
// AnalyticsDashboard.ts
import { yieldToMainThread, processLargeDatasetInChunks } from './SchedulerOptimizer';

interface Transaction {
  id: string;
  amount: number;
  tax: number;
}

export class AnalyticsDashboard {
  private container: HTMLElement;
  private telemetryQueue: any[] = [];

  constructor(containerElement: HTMLElement) {
    this.container = containerElement;
    this.renderSkeleton();
    this.setupRUMReporting();
  }

  /**
   * Mengeliminasi CLS dengan memesan dimensi layout menggunakan aspect-ratio & contain
   */
  private renderSkeleton(): void {
    this.container.innerHTML = `
      <style>
        .dashboard-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.5rem;
          width: 100%;
        }
        /* Mencegah CLS: Pesan ruang render grafik sebelum JS chart engine dimuat */
        .chart-reserved-container {
          width: 100%;
          aspect-ratio: 16 / 9;
          contain-intrinsic-size: 100% 450px;
          content-visibility: auto;
          background-color: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
        }
        .hero-banner {
          width: 100%;
          height: auto;
          aspect-ratio: 1200 / 400;
        }
      </style>
      <div class="dashboard-grid">
        <!-- Optimasi LCP: Image Hero dideklarasikan dengan fetchpriority high -->
        <img 
          class="hero-banner" 
          src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1200&q=80" 
          alt="Executive Analytics Overview"
          fetchpriority="high"
          loading="eager"
          decoding="async"
        />
        <div id="chart-slot" class="chart-reserved-container"></div>
        <div id="table-slot"></div>
      </div>
    `;
  }

  /**
   * Menangani pemrosesan data volume tinggi tanpa memicu Long Task pada INP
   */
  public async handleFilterAction(rawTransactions: Transaction[]): Promise<void> {
    const tableSlot = document.getElementById('table-slot');
    if (!tableSlot) return;

    // Tampilkan state indikator lokal secara atomik (Immediate Visual Feedback)
    tableSlot.setAttribute('aria-busy', 'true');

    // Yield segera untuk memastikan paint feedback status 'busy' muncul ke layar
    await yieldToMainThread();

    // Jalankan heavy transformation via chunking optimizer
    const processedData = await processLargeDatasetInChunks(
      rawTransactions,
      (tx) => {
        // Simulasi kalkulasi finansial berat
        let compound = tx.amount;
        for (let i = 0; i < 500; i++) {
          compound += Math.sin(tx.tax) * Math.cos(compound);
        }
        return { id: tx.id, netValue: compound.toFixed(2) };
      },
      10 // Target sub-frame chunking budget: 10ms
    );

    // Update DOM secara terstruktur
    tableSlot.innerHTML = `
      <table class="min-w-full divide-y divide-gray-200">
        <tbody>
          ${processedData.slice(0, 50).map(d => `<tr><td>${d.id}</td><td>${d.netValue}</td></tr>`).join('')}
        </tbody>
      </table>
    `;
    tableSlot.removeAttribute('aria-busy');
  }

  /**
   * Telemetri RUM yang diisolasi menggunakan sendBeacon tanpa memblokir pembongkaran halaman
   */
  private setupRUMReporting(): void {
    const reportEndpoint = '/api/v1/rum-telemetry';

    const flushQueue = () => {
      if (this.telemetryQueue.length === 0) return;
      const blob = new Blob([JSON.stringify(this.telemetryQueue)], {
        type: 'application/json',
      });
      navigator.sendBeacon(reportEndpoint, blob);
      this.telemetryQueue = [];
    };

    // Amankan pengiriman metrik pada akhir lifecycle
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        flushQueue();
      }
    });

    window.addEventListener('pagehide', flushQueue);
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Teknik Optimasi | Metrik Utama | Keuntungan Arsitektural | Biaya Sistem / Trade-off Negatif | Skenario yang Cocok |
| :--- | :--- | :--- | :--- | :--- |
| **`scheduler.yield()` Chunking** | **INP** | Mencegah pembekuan Main Thread, eliminasi Long Tasks secara deterministik. | Total waktu eksekusi komputasi (*wall-clock time*) bertambah karena overhead context switching. | Manipulasi data besar di memory pada sisi klien. |
| **Web Workers (Off-main-thread)** | **INP** | Memindahkan komputasi seutuhnya dari rendering thread ke background thread. | Biaya serialisasi data lewat `Structured Clone Algorithm` (atau memory transfer overhead). | Komputasi data masif (>100.000 records), image decoding lokal. |
| **Inline Critical CSS** | **FCP / LCP** | Menghilangkan network round-trip blocking CSS eksternal. | Cache browser tidak dapat dimanfaatkan secara modular untuk style sheet tersebut; memperbesar ukuran HTML. | First-time visitors, landing pages, SSR hydration routes. |
| **`fetchpriority="high"`** | **LCP** | Mengubah prioritas network waterfall engine browser langsung ke aset visual utama. | Menggeser bandwidth dari aset critical lain (seperti CSS bundle atau font utama) jika salah ditempatkan. | Hero Image, file poster video banner pertama. |
| **CSS `content-visibility: auto`** | **INP / CLS** | Melompati proses Layout dan Paint untuk node di luar viewport (rendering virtualization). | Mengharuskan penetapan `contain-intrinsic-size`; jika estimasi salah, berpotensi memicu CLS saat di-scroll. | Halaman dokumen panjang, infinite scrolling list. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Hidden Cost of Client-Side Hydration
* **Failure Mode:** Pada aplikasi Server-Side Rendered (SSR) modern (React/Next.js/Nuxt), markup HTML di-render dari server (LCP tampak cepat). Namun, ketika halaman selesai dimuat, seluruh bundle JavaScript dieksekusi serentak untuk mengaitkan event listener (*Hydration*). Jika pengguna mengklik halaman pada window ini, aksi akan membeku (*Uncanny Valley*), menyebabkan INP melonjak drastis hingga ribuan milidetik.
* **Mitigasi:** Gunakan teknik arsitektur modern seperti *Islands Architecture* (Astro) atau *Partial/Progressive Hydration*. Tunda hidrasi komponen yang berada di bawah viewport sampai elemen terlihat (*IntersectionObserver*).

### 2. Microtask Queue Starvation
* **Failure Mode:** Melakukan batching menggunakan `Promise.resolve().then(...)` bertingkat. Karena antrean Microtask diproses hingga tuntas sebelum browser menyerahkan kendali kembali ke Macrotask Queue atau Render Pipeline, eksekusi microtask yang chaining tanpa henti akan **membuat Main Thread kelaparan (starvation)**. Ini menghasilkan blocking yang identik dengan while-loop sinkron.
* **Mitigasi:** Jangan gunakan microtask untuk yielding. Gunakan `scheduler.yield()` atau fallback `MessageChannel` (macrotask boundary).

### 3. Font Swapping Layout Thrashing
* **Failure Mode:** Menggunakan `font-display: swap` tanpa fallback sizing yang presisi. Ketika custom web-font selesai dimuat, font tersebut menggantikan sistem fallback font (Arial/Times). Karena metrik metrik glif (ascent, descent, advance width) berbeda, seluruh paragraf mengubah posisinya, memicu CLS secara instan.
* **Mitigasi:** Gunakan CSS Font Face overrides: `size-adjust`, `ascent-override`, dan `descent-override` untuk menyamakan metrik fallback font sistem secara presisi dengan web-font yang akan dimuat.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menunda Pemuatan LCP dengan `loading="lazy"`
* **Anti-Pattern:** Menambahkan atribut `loading="lazy"` pada gambar hero LCP.
  ```html
  <!-- KESALAHAN FATAL -->
  <img src="hero.webp" loading="lazy" class="hero-image" />
  ```
  Ini menyebabkan engine browser menunda pengunduhan gambar sampai kalkulasi layout pertama selesai dan browser mengonfirmasi gambar berada di dalam viewport. Metrik LCP akan turun secara drastis.
* **Solusi Benar:** Gunakan `loading="eager"` dan `fetchpriority="high"`.
  ```html
  <!-- BENAR -->
  <img src="hero.webp" loading="eager" fetchpriority="high" class="hero-image" />
  ```

### 2. Membaca dan Menulis Layout Property Berulang-ulang (Forced Synchronous Layout)
* **Anti-Pattern:**
  ```javascript
  // KESALAHAN FATAL: Layout Thrashing
  elements.forEach((el) => {
    const width = el.offsetWidth; // READ (Force Layout calculation)
    el.style.width = width + 10 + 'px'; // WRITE (Invalidate Layout)
  });
  ```
* **Solusi Benar:** Pisahkan fase pembacaan (*batch read*) dan penulisan (*batch write*), atau gunakan `requestAnimationFrame`.
  ```javascript
  // BENAR
  const widths = elements.map(el => el.offsetWidth); // Batch Read
  elements.forEach((el, i) => {
    el.style.width = widths[i] + 10 + 'px'; // Batch Write
  });
  ```

### 3. Menghapus Elemen DOM via Animasi Berbasis CSS Top/Left
* **Anti-Pattern:** Menggunakan CSS property `top`, `left`, `margin` untuk transisi animasi. Hal ini memicu pipeline recalculate layout dan paint di setiap frame (60 kali per detik).
* **Solusi Benar:** Selalu gunakan CSS `transform`