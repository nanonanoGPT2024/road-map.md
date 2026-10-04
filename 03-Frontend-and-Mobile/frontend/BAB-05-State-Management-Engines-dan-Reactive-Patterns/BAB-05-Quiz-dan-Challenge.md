# BAB 05: Quiz, Challenge, & Knowledge Check
**Bab 05: Arsitektur Rendering Lanjutan, Hydration, dan Optimasi Performa Runtime (Core Web Vitals & Memory)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dekomposisi Critical Rendering Path (CRP):**  
   Jelaskan secara mendalam urutan eksekusi browser dari penerimaan raw bytes HTML hingga tahap *Composite*. Mengapa CSS diklasifikasikan sebagai *render-blocking* sementara JavaScript secara default diklasifikasikan sebagai *parser-blocking*? Analisis bagaimana spesifikasi HTML5 memproses tag `<script>` dengan atribut `async` vs `defer` terhadap konstruksi DOM dan CSSOM.

2. **Evolusi Core Web Vitals (LCP, CLS, dan Penggantian FID ke INP):**  
   Uraikan metrik Core Web Vitals terbaru. Mengapa Google menggantikan *First Input Delay* (FID) dengan *Interaction to Next Paint* (INP) sebagai metrik responsivitas interaksi standar per 2024? Jelaskan apa saja fase penundaan (*input delay*, *processing duration*, *presentation delay*) yang dihitung di dalam INP dan apa implikasi teknisnya terhadap eksekusi Event Loop.

3. **Mekanika Hydration dan Komparasi Pola Rendering (SSR, SSG, ISR, CSR):**  
   Jelaskan apa yang sebenarnya terjadi pada level runtime browser saat proses *hydration* berlangsung pada framework berbasis Virtual DOM (seperti React/Vue). Mengapa proses ini sering disebut sebagai *costly dual-pass penalty*, dan apa perbedaan fundamental antara *Traditional Hydration*, *Streaming SSR with Selective Hydration*, dan paradigma *Resumability*?

4. **Siklus Hidup Garbage Collection (GC) dan V8 Memory Management:**  
   Bagaimana V8 JavaScript Engine mengelola alokasi memori melalui *Generational Garbage Collection* (Scavenge/New Space vs Mark-Sweep-Compact/Old Space)? Sebutkan 3 (tiga) penyebab paling umum terjadinya *Detached DOM Nodes* dan bagaimana kondisi tersebut menyebabkan *memory leak* permanen jika referensinya tertahan dalam *closure*.

5. **Pemisahan Threading: Main Thread vs Compositor Thread vs Worker Thread:**  
   Bagaimana arsitektur multi-thread pada browser modern (Chromium-based) membagi tanggung jawab komputasi UI? Properti CSS apa saja yang dijamin dapat dieksekusi murni pada *Compositor Thread* tanpa memicu *Reflow (Layout)* maupun *Repaint*, dan bagaimana GPU rasterization diakselerasi melalui CSS property `will-change`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **INP Optimization & Long Task Splitting:**  
   Sebuah fungsi pemrosesan data synchronous memblokir Main Thread selama 280ms di dalam event handler `onClick`, menyebabkan degradasi INP drastis pada mobile device low-end. Rancang mekanisme refactor eksekusi fungsi tersebut menggunakan kombinasi `scheduler.yield()` (atau fallback berbasis `MessageChannel` / `setTimeout`), `requestAnimationFrame`, dan microtask queue untuk mempertahankan frame budget 16.6ms (60 FPS) tanpa memecah konsistensi *state*.

2. **Cumulative Layout Shift (CLS) Debugging & Dynamic Layout Defense:**  
   Sebuah halaman web mengalami lonjakan CLS dari 0.02 menjadi 0.38 di lingkungan produksi karena tiga faktor: *web font swap* (FOUT/FOIT), *ad-banner dynamic injection*, dan *responsive image gallery*. Bedah secara teknis bagaimana Anda mengeliminasi layout shift ini menggunakan kombinasi CSS `font-display: optional` dengan *font metric override*, `contain-intrinsic-size` dengan CSS Content Visibility, dan kalkulasi `aspect-ratio` sebelum media di-load.

3. **Memory Profiling: Membedah Heap Snapshot:**  
   Saat menganalisis *Heap Snapshot* di Chrome DevTools, Anda menemukan ukuran *Shallow Size* yang sangat kecil pada sebuah objek, namun *Retained Size*-nya mencapai ratusan megabyte. Jelaskan arti teknis dari kedua metrik ini. Tuliskan metodologi langkah-demi-langkah menggunakan visualisasi *Retainer Tree* untuk melacak root cause kebocoran memori yang diakibatkan oleh lingering *Event Target*, uncleaned *AbortController*, atau *RxJS/EventEmitters* subscription.

4. **Tree-Shaking Failures dan Bundle Analysis:**  
   Mengapa impor modul tertentu seperti `import { debounce } from 'lodash'` sering kali gagal di-*tree-shake* oleh module bundler (seperti Webpack/Rollup) dan menyertakan keseluruhan pustaka ke dalam bundle produksi? Jelaskan peran spesifikasi ES Modules (ESM) vs CommonJS (CJS), deklarasi `"sideEffects": false` pada `package.json`, dan dead-code elimination pada tahap Abstract Syntax Tree (AST) analysis.

5. **Off-Main-Thread Processing via Web Workers & Transferable Objects:**  
   Ketika mentransfer data berukuran besar (misalnya: dataset array terenkripsi 50MB) dari Main Thread ke Web Worker menggunakan `postMessage()`, terjadi freezing sementara pada UI thread akibat *Structured Clone Algorithm*. Jelaskan mekanisme internal mengapa cloning ini memblokir thread dan berikan solusi implementasi alternatif menggunakan `ArrayBuffer` dan *Transferable Objects* untuk mencapai operasi zero-copy transfer dengan kompleksitas waktu $O(1)$.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Black Friday - Bottleneck LCP & Mobile Crash pada Tier-3 Devices
* **Konteks:** Sebuah platform e-commerce enterprise berskala global meluncurkan program flash sale tahunan. Beberapa menit setelah pembukaan, analitik Real User Monitoring (RUM) mendeteksi LCP (Largest Contentful Paint) anjlok hingga 6.8 detik pada 75% traffic mobile (didominasi perangkat Android entry-level dengan RAM 2GB-3GB pada jaringan 4G fluktuatif). Tingkat bounce rate meroket 45%. Halaman landing dibangun menggunakan SSR framework (Next.js) dengan carousel produk hero banner berukuran besar (animasi auto-sliding), library CSS-in-JS runtime, serta script analitik 3rd-party (GTM, Hotjar, Facebook Pixel, Optimizely) yang berjalan bersamaan.
* **Pertanyaan Diagnostik:**
  1. Identifikasi dan klasifikasikan 4 (empat) *bottleneck* fundamental pada rantai CRP yang berkontribusi langsung terhadap keterlambatan LCP dan kelelahan CPU/memori perangkat tersebut.
  2. Rancang rencana remediasi arsitektur darurat (tindakan instan) dan solusi struktural jangka menengah untuk menurunkan LCP ke batas aman (< 2.0s), mencakup penanganan assets hero banner (format, preloading, decoding, fetchpriority), eliminasi runtime CSS-in-JS overhead, dan penundaan evaluasi 3rd party tags melalui Web Workers atau façade pattern.

### Skenario B: Hydration Mismatch Cascade & Form State Corruption pada Checkout Flow
* **Konteks:** Pada sistem checkout perbankan, pengguna sering melaporkan bug aneh: saat menginput kode kupon atau nomor kartu pada form yang lambat dimuat, karakter yang telah diketik tiba-tiba terhapus, form kembali ke status awal (uncontrolled re-render), atau checkout button menjadi disabled secara permanen. Investigasi awal menunjukkan console browser dipenuhi warning: `Hydration failed because the initial UI does not match what was rendered on the server`. Hal ini dipicu oleh pengecekan status autentikasi lokal via `localStorage`, deteksi timezone klien menggunakan `Intl.DateTimeFormat`, dan dynamic localization yang dieksekusi secara sinkron di level root layout sebelum proses hydration tuntas.
* **Pertanyaan Diagnostik:**
  1. Mengapa inkonsistensi antara Server HTML dan Client Virtual DOM tree menyebabkan engine framework melempar *destructive re-render* atau *complete DOM patch*, dan mengapa hal ini menghancurkan state lokal native form DOM nodes?
  2. Tuliskan arsitektur perbaikan komprehensif untuk mencegah *Hydration Mismatch* pada aplikasi ini. Bagaimana memisahkan data rendering deterministik (server) dari non-deterministik client-only state dengan aman menggunakan teknik two-pass rendering, resilient hydration boundaries, atau server context injection tanpa memicu layout shift?

### Skenario C: Memory Bloat & Main-Thread Freezing pada Real-Time Financial Dashboard
* **Konteks:** Sebuah web application terminal pasar finansial menampilkan 200+ running tickers dan chart visualisasi Order Book melalui koneksi WebSocket berfrekuensi tinggi (500 payload/detik). Setelah tab aplikasi dibuka selama 30-45 menit, penggunaan memori tab browser melonjak dari 150MB ke 1.8GB, menyebabkan browser menampilkan crash screen *Out of Memory* (Error code: `STATUS_BREAKPOINT` atau `RESULT_CODE_KILLED_BAD_MESSAGE`). Profiling menunjukkan DOM node bertambah secara kontinu dan Garbage Collector berjalan terus-menerus (*GC Churn*), memangkas frame rate hingga 8 FPS.
* **Pertanyaan Diagnostik:**
  1. Analisis mekanisme kegagalan sistem ini dari sudut pandang alokasi memori runtime, object allocation rate, DOM mutation frequency, dan retensi referensi data stream.
  2. Susun cetak biru arsitektur teknis untuk menstabilkan konsumsi memori di bawah 200MB konstan selama runtime tak terbatas. Solusi Anda harus mencakup teknik *Data Throttling/Buffering*, *Object Pooling*, *DOM Virtualization*, dan penggunaan canvas/WebGL untuk rendering visual tanpa membebani Main Thread DOM tree.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Telemetry Data-Grid Engine dengan Zero Memory Leak & Sub-50ms INP

#### Problem:
Sebuah sistem monitoring infrastruktur cloud membutuhkan dashboard visualisasi logs/telemetri yang mampu menerima stream data berkecepatan tinggi (1.000 log events per detik) secara live tanpa membuat UI lag, tanpa memory leak, dan mempertahankan interaktivitas tinggi (klik, filter, search) dengan INP < 50ms di semua perangkat. Implementasi tabel standar HTML dengan rendering framework reaktif konvensional selalu crash dalam waktu kurang dari 5 menit.

#### Requirements:
1. **Engine Komputasi Off-Thread:**
   * Bangun modul data ingestion berbasis **Web Worker**.
   * Web Worker bertanggung jawab menerima data stream mock (via `setInterval` atau simulated WebSocket), melakukan parsing, sorting, filtering, dan agregasi data.
   * Transfer data dari Web Worker ke Main Thread wajib menggunakan **Transferable Objects** (`ArrayBuffer` atau `SharedArrayBuffer` dengan fallback aman) atau structured payload yang di-batch setiap 100ms untuk mengeliminasi Main Thread starvation.
2. **Virtual DOM-less / Virtualized Viewport:**
   * Implementasikan custom **Virtual Scroll List** murni (vanilla TypeScript atau framework wrapper tingkat rendah).
   * Hanya merender DOM nodes yang terlihat di viewport (misal: 30-50 baris) + small buffer (overscan).
   * DOM nodes harus di-*recycle* (node reuse) alih-alih di-destroy dan di-create ulang setiap scrolling untuk mencegah garbage collection churn.
3. **INP & Frame Scheduling Defense:**
   * Setiap aksi pengguna (pencarian teks pada input box) tidak boleh memblokir thread virtual scroll.
   * Gunakan pembagian prioritas tugas: input user dialokasikan sebagai task prioritas tinggi, sementara sinkronisasi filter ke Worker berjalan secara interruptible/asynchronous menggunakan scheduler modern (`scheduler.yield()` atau fallback `MessageChannel`).
4. **Memory Profiling Gate:**
   * Alokasi heap memori aplikasi harus datar (flat line) setelah fase stabilisasi 60 detik. Tidak boleh ada detached DOM nodes saat filter diterapkan dan dibersihkan berulang kali.

#### Constraints:
* Dilarang menggunakan library tabel eksternal siap pakai (e.g., AG-Grid, TanStack Table, React Virtualized). Arsitektur virtualisasi dan recycling harus dibangun sendiri untuk membuktikan pemahaman mekanisme DOM & Viewport.
* Bundle size total implementasi custom virtual grid logic tidak boleh melebihi 10KB (minified).
* Menjaga performa 60 FPS saat continuous fast-scrolling (terverifikasi via DevTools Performance Monitor).

#### Expected Output:
* Repositori atau file demonstrasi fungsional (HTML/CSS/TypeScript) yang mencakup:
  1. `worker.ts`: Penanganan stream data, index array, sorting, dan transfer buffer.
  2. `virtual-grid.ts`: Algoritma perhitungan scroll offset, windowing slice, DOM pooling/recycling, dan containment styling (`will-change: transform`, `contain: strict`).
  3. `scheduler.ts`: Abstraksi pembagian task untuk rendering buffer vs user event handling.
* Laporan performa teknis (Markdown) berisi:
  * Screenshot/data ringkasan Chrome DevTools Performance Trace yang membuktikan ketiadaan *Long Tasks* (> 50ms) saat streaming aktif.
  * Hasil perbandingan memory heap snapshot pada menit ke-1 vs menit ke-10 yang membuktikan ketiadaan memory leak (zero detached DOM nodes).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi detail Critical Rendering Path (CRP): Parsing HTML $\to$ DOM Tree $\to$ CSSOM Tree $\to$ Render Tree $\to$ Layout $\to$ Paint $\to$ Composite.
- [ ] Formula kalkulasi dan ambang batas metrik Core Web Vitals: LCP ($\le 2.5\text{s}$), INP ($\le 200\text{ms}$), dan CLS ($\le 0.1$) pada persentil ke-75.
- [ ] Perbedaan fase eksekusi Microtask (Promises, `queueMicrotask`, `MutationObserver`) vs Macrotask/Task (`setTimeout`, I/O, UI rendering) dalam Event Loop browser.
- [ ] Mekanisme kerja V8 Garbage Collector: Perbedaan Scavenger (Semi-space allocation) dan Mark-Sweep-Compact serta trigger terjadinya Full GC pause.
- [ ] Konsep *Layout Thrashing* (Forced Synchronous Layout) akibat membaca geometri DOM (`offsetHeight`, `getBoundingClientRect`) tepat setelah melakukan mutasi DOM.
- [ ] Perbedaan arsitektural rendering: CSR, SSR murni, Static Site Generation (SSG), Incremental Static Regeneration (ISR), Streaming SSR, dan Island Architecture.
- [ ] Konsep Hydration Mismatch: Penyebab, konsekuensi performa, dan strategi penanganannya pada isomorphic codebase.
- [ ] Cara kerja CSS containment (`contain: strict | content | size | layout | paint`) dan properti `content-visibility: auto` dalam mengoptimalkan First Paint.

### Saya tidak perlu menghafal:
- [ ] Seluruh tabel kode heksadesimal atau magic numbers internal engine V8 memory flags (e.g., `--max-old-space-size`).
- [ ] Setiap baris kode implementasi polifill legacy browser untuk API modern (cukup pahami fungsionalitas dan API kontrak standarnya).
- [ ] Urutan exact microsecond komputasi internal GPU driver untuk hardware acceleration.

### Saya harus bisa melakukan:
- [ ] Merekam, membaca, dan mendiagnosis bottlenecks pada Chrome DevTools **Performance Panel** (mengidentifikasi Long Tasks, Layout Shifts, Unscheduled Timers, Dropped Frames).
- [ ] Mengambil, membandingkan (*Comparison View*), dan menganalisis **Heap Snapshots** untuk mengidentifikasi *Detached DOM Nodes* dan menemukan retainers yang menyebabkan *memory leak*.
- [ ] Mengonfigurasi bundle analysis (via Webpack Bundle Analyzer, Rollup Plugin Visualizer, dsb.) dan membedah duplicate dependencies serta modul non-tree-shakeable.
- [ ] Mengimplementasikan *code-splitting* dinamis pada level rute dan komponen menggunakan dynamic imports (`import()`) dan lazy-loading boundaries yang resilient.
- [ ] Menulis arsitektur script non-blocking menggunakan Web Worker dengan komunikasi transfer data efisien (*Transferable Objects*).
- [ ] Mengatur strategi loading aset prioritas tinggi secara optimal menggunakan resource hints (`rel="preload"`, `rel="preconnect"`, `fetchpriority="high"`, `decoding="async"`).
- [ ] Menulis custom virtualized list untuk merender puluhan ribu baris data tanpa membebani Main Thread dan DOM tree.