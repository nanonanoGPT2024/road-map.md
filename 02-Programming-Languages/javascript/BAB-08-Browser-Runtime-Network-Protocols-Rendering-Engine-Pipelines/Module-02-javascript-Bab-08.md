# BAB 08: Browser Runtime, Network Protocols & Rendering Engine Pipelines
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal/Staff Software Engineer diharapkan mampu:
- **Menganalisis dan Membedah Siklus Hidup Frame (Frame Lifecycle)**: Mengisolasi eksekusi JavaScript pada Main Thread, penghitungan Layout (Reflow), Paint (Repaint), hingga Composite dan Tiling pada Compositor Thread dan GPU Process.
- **Mengoptimalkan Transport Layer & Network Protocols**: Mengimplementasikan strategi orkestrasi HTTP/2 Multiplexing, HTTP/3 (QUIC via UDP) 0-RTT Connection Establishment, Early Hints (103), Priority Hints (`fetchpriority`), dan Speculative Loading API untuk menekan TTFB dan Network Waterfall.
- **Membangun Runtime Pipeline Berkinerja Tinggi**: Mengeliminasi bottleneck pada Main Thread menggunakan Service Worker, Dedicated Web Worker pools via `Comlink` patterns, serta rendering grafis non-blocking melalui `OffscreenCanvas`.
- **Menerapkan Streaming Architecture**: Memanfaatkan WhatWG Streams API (`ReadableStream`, `TransformStream`, `WritableStream`) dengan penanganan backpressure native untuk memproses payload biner/JSON berskala besar langsung di browser tanpa menyebabkan lonjakan alokasi heap V8.
- **Mengontrol Core Web Vitals (CWV) secara Programatik**: Mengotomatisasi audit, debugging, dan mitigasi Layout Instability (CLS), Long Animation Frames (LoAF) yang memengaruhi Interaction to Next Paint (INP), dan Largest Contentful Paint (LCP) pada skala jutaan sesi pengguna.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib menguasai:
1. **Engine JavaScript & Memory Management**: V8 Garbage Collection mechanics (Scavenger, Mark-Sweep-Compact), hidden classes, inline caching, dan alokasi stack vs. heap.
2. **Dasar Asinkron Modern**: Event loop (Microtask queue vs. Macrotask queue), Promises, dan Async/Await internals.
3. **Dasar Jaringan Komputer**: Model OSI, TCP 3-way handshake, TLS 1.3 handshake, dan struktur header HTTP/1.1 dasar.
4. **Tooling & Profiling**: Mahir menggunakan Chrome DevTools (Performance Panel, Memory Profiler, Network Waterfall, dan Rendering drawer).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur browser modern (seperti Chromium/Blink, WebKit, Gecko) bukan sekadar parser dokumen tunggal, melainkan sistem operasi terdistribusi berbasis *multi-process architecture*. Memahami interaksi antar-proses ini adalah prasyarat untuk rekayasa web kelas enterprise.

```
                    BROWSER MULTI-PROCESS TOPOLOGY
                    
  +---------------------------------------------------------------+
  |                        Browser Process                        |
  |  (UI, Network Stack via Network Service, Storage, Permissions)|
  +---------------------------------------------------------------+
           | IPC (Mojo)                   | IPC (Mojo)
           v                              v
  +-----------------------+      +-------------------------------+
  |   Renderer Process    |      |          GPU Process          |
  | (Blink / V8 Engine)   |      | (Skia, Vulkan, Direct3D, Metal|
  |                       |      |  Rasterization & Composition) |
  |  Main Thread          |      +-------------------------------+
  |  Compositor Thread    |                      ^
  |  Raster Worker Thread |                      | Shared Memory /
  |  Worker Threads       |----------------------+ GPU Command Buffer
  +-----------------------+
```

#### 3.1. Browser Multi-Process Architecture & IPC
Chromium mengisolasi operasi dalam beberapa proses independen yang berkomunikasi menggunakan IPC (*Inter-Process Communication*) berbasis Mojo:
- **Browser Process**: Mengelola *chrome UI* (address bar, bookmark), tab lifecycle, dan mengorkestrasi proses lain. Memuat *Network Service* yang menangani soket TCP/UDP, TLS handshakes, HTTP parsing, dan disk cache.
- **Renderer Process**: Menjalankan engine Blink dan VM V8. Diisolasi per-site (Site Isolation) demi keamanan. Mengonversi HTML/CSS/JS menjadi piksel interaktif.
- **GPU Process**: Mengisolasi instruksi grafis dari berbagai tab. Mengonversi drawing commands dari Skia menjadi instruksi native hardware (Direct3D, Metal, OpenGL, Vulkan).

#### 3.2. Rendering Engine Pipeline Stages
Ketika byte HTML diterima dari Network Process melalui Mojo IPC Data Pipe, siklus berikut dieksekusi secara ketat:

```
Bytes -> Characters -> Tokens -> Nodes -> DOM Tree
                                            |
Style Sheets -> CSS Rules -> CSSOM Tree ----+--> Render Tree (Layout Object Tree)
                                                       |
                                                 Layout (Reflow)
                                                       |
                                                 Paint (Display Lists)
                                                       |
                                                 Compositing (Layerize)
                                                       |
                                                 [Compositor Thread]
                                                 Tiling & Raster (GPU)
                                                       |
                                                 Draw Quads -> GPU Display
```

1. **DOM Construction**: HTML tokenizer mem-parse stream biner secara incremental. Jika menemukan tag `<script>` synchronous, tokenisasi berhenti total (parser-blocking) karena script dapat memodifikasi DOM via `document.write` atau mengakses CSSOM.
2. **CSSOM Construction**: CSS di-parse menjadi rule tree. Berbeda dengan HTML, CSS adalah *render-blocking*. Engine tidak dapat merender subtree DOM sebelum CSSOM siap, guna mencegah FOUC (*Flash of Unstyled Content*).
3. **Style Calculation (Recalculate Style)**: DOM dan CSSOM digabungkan untuk menentukan computed style untuk setiap node. Komputasi selector matching bergerak dari kanan ke kiri (*right-to-left*).
4. **Layout (Reflow)**: Menentukan geometri, ukuran, dan posisi absolut setiap elemen visual di layar (menghasilkan *Layout Tree* atau *Fragment Tree*). Operasi ini mahal ($O(N \log N)$ atau lebih tergantung kedalaman pohon) dan dapat dipicu ulang secara prematur oleh *Forced Synchronous Layout*.
5. **Pre-Paint**: Membangun pohon properti (*Property Trees*: Transform, Clip, Effect, Scroll). Menghilangkan traversal berulang pada Layout Tree saat transformasi grafis berlangsung.
6. **Paint (Repaint)**: Menghasilkan urutan instruksi visual (*Display Items* / *Skia Drawing Commands*) seperti `drawRect()`, `drawTextBlob()`. Urutan paint mengikuti aturan stacking context CSS (background, border, block children, floats, inline children, positioned elements).
7. **Compositing**: Mengelompokkan elemen visual ke dalam *Composited Layers*. Layer-layer ini ditransfer ke **Compositor Thread**, membebaskan Main Thread.
8. **Rasterization**: Compositor membagi layer menjadi petak-petak kecil (*tiles*). Melalui *Raster Worker Threads* dan GPU, instruksi Skia di-raster ke dalam bitmapped memory (Texture).
9. **Draw Quad Emission**: Compositor mengirimkan *Compositor Frame* yang berisi *Draw Quads* ke GPU Process untuk di-swap ke frame buffer layar pada interval V-Sync (biasanya 60Hz atau 120Hz).

#### 3.3. Threading Architecture pada Renderer
- **Main Thread**: Parsing HTML/CSS, komputasi Layout, Paint, eksekusi JavaScript (V8), Garbage Collection, dispatching events. Jika Main Thread terblokir > 50ms, browser mencatat *Long Task*, memicu frame dropped (jank) dan degradasi INP.
- **Compositor Thread**: Bertanggung jawab menerima input scroll/pinch, menginterpolasi transformasi CSS (`transform`, `opacity`), menghitung visibility tile, dan meminta rasterisasi. Operasi di thread ini berjalan 60-120fps meskipun Main Thread terkunci (*frozen*).

#### 3.4. Network Protocols: HTTP/2 vs HTTP/3 (QUIC)
Transport layer secara langsung menentukan latensi rendering:

| Fitur | HTTP/1.1 | HTTP/2 | HTTP/3 (QUIC) |
| :--- | :--- | :--- | :--- |
| **Transport Protocol** | TCP | TCP | UDP (QUIC Implementation) |
| **Handshake Latency** | 1-RTT TCP + 1-2 RTT TLS 1.3 | 1-RTT TCP + 1-2 RTT TLS 1.3 | 1-RTT QUIC (Combined Crypto + Transport), 0-RTT Session Resumption |
| **Multiplexing** | Tidak Ada (Head-of-Line Blocking pada Application Layer) | Ya (Streams dalam 1 koneksi TCP) | Ya (Streams independen sejati pada Transport Layer) |
| **Head-of-Line Blocking** | Kritis (Antrean request HTTP) | Kritis pada Transport Layer (TCP Packet Loss memblokir semua streams) | Tereliminasi Total (Packet loss pada Stream A tidak memblokir Stream B) |
| **Connection Migration** | Tidak Ada (Socket terikat IP:Port) | Tidak Ada | Native (Berdasarkan Connection ID 64-bit; tahan roaming Wi-Fi -> Seluler) |

---

### 4. Why & What

#### Problem Space (The "Why")
Di aplikasi web skala enterprise (e.g., SaaS dashboard, fintech trading platform, enterprise e-commerce), kelemahan performa runtime dan network berdampak langsung pada metrik bisnis:
- **Main Thread Starvation**: Pemrosesan payload JSON yang besar (megabytes) membekukan thread utama, mematikan interaktivitas pengguna, dan menghasilkan INP buruk (> 200ms).
- **Layout Thrashing**: Kode JavaScript yang membaca properti geometri (`offsetHeight`, `getBoundingClientRect`) lalu memodifikasi DOM secara berulang memaksa engine melakukan siklus Style -> Layout berulang kali dalam satu frame (sub-16ms budget).
- **Network Pipeline Latency**: Round-trip time (RTT) yang tinggi, waterfall loading resource statis tanpa prioritas, serta packet loss TCP di jaringan nirkabel menunda pengiriman LCP.

#### Solution Anatomy (The "What")
Arsitektur runtime modern memanfaatkan:
1. **Network Hints & Resource Optimization**: `fetchpriority="high"`, Early Hints HTTP 103, dan Speculation Rules API untuk memanipulasi network scheduler browser.
2. **Streaming Ingestion**: Mengalirkan chunk respons network langsung ke parser data menggunakan Web Streams tanpa buffering utuh di memori.
3. **Offloading Komputasi**: Menjalankan data parsing, state computation, dan layout logis di Web Worker/SharedWorker.
4. **Compositor-Only Animations**: Mengisolasi mutasi UI hanya pada properti `transform`, `opacity`, dan `filter` untuk menjamin render 60-120 FPS tanpa Layout/Paint pass.

---

### 5. How (Workflow Detail)

Berikut adalah urutan komputasi end-to-end dari inisiasi network request hingga komposisi GPU frame:

```
[User Navigate / Fetch Initiated]
               |
               v
1. Network Service: TLS 1.3 / QUIC Handshake -> Send Request
               |
2. HTTP 103 Early Hints diproses -> Preload Critical Resources (CSS/JS)
               |
3. HTTP 200 Stream Dimulai -> Byte chunks dikirim via Mojo Data Pipe ke Renderer
               |
4. HTML Tokenizer membaca chunks -> Membangun DOM Nodes incremental
               |
5. Script Preload Scanner memindai tag eksternal -> Fetch paralel dengan 'fetchpriority'
               |
6. CSS Diterima -> CSSOM Dibangun -> Style Recalculate
               |
7. Layout Object Tree Dibangun -> Geometri (Bounding Boxes) dikalkulasi
               |
8. Paint Generation -> Display List dikompilasi ke Skia Draw Commands
               |
9. Layerization -> Main thread mengoper Layer Tree ke Compositor Thread via Commit
               |
10. Compositor Thread -> Membagi Layer menjadi Tiles -> Kirim instruksi ke Raster Worker
               |
11. GPU Process -> Mengeksekusi Rasterization -> Bitmaps disimpan di GPU Memory (VRAM)
               |
12. Compositor mengumpulkan Quads -> Menghasilkan CompositorFrame -> Submit ke GPU
               |
13. Screen Display: Vertical Sync (V-Sync) -> Buffer Swap -> Tampilan ter-update
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional (Browser Runtime Architecture)
- **Browser Process**: Menara Pengawas Lalu Lintas Udara (*Air Traffic Control*). Mengatur izin mendarat, keamanan bandara, alokasi landasan pacu, dan otorisasi.
- **Main Thread**: Jalur pemeriksaan imigrasi dan tiket tunggal. Semua penumpang harus diverifikasi di sini. Jika satu penumpang membawa dokumen kompleks bermasalah (*Long Task / Heavy JS Parsing*), seluruh antrean di belakangnya terhenti total (*Main Thread Jank*).
- **Compositor Thread**: Eskalator otomatis dan ban berjalan bagasi (*Automated Conveyor Belts*). Tetap berjalan memindahkan bagasi ke pesawat secara konstan meskipun antrean imigrasi utama sedang macet parah.
- **GPU Process**: Mesin derek dan armada truk jet kargo berat. Melakukan tugas fisik terberat (memuat beban ke pesawat / mengecat jutaan piksel) dalam hitungan milidetik secara paralel.

#### Diagram: Layout Thrashing vs. Optimized Render Cycle

```
ANTI-PATTERN: LAYOUT THRASHING (FORCED SYNCHRONOUS LAYOUT)
Frame Budget (16.6ms)
|-----------------------------------------------------------------|
JS: Read (offsetWidth) -> Write (style.width) -> Read -> Write...
     |                     |                     |       |
   [Layout]              [Layout]              [Layout] [Layout]  <-- Engine dipaksa
   (Mahal!)              (Mahal!)              (Mahal!) (Mahal!)      menghitung ulang

BEST PRACTICE: BATCHED STATE & COMPOSITOR OFFLOADING
Frame Budget (16.6ms)
|-----------------------------------------------------------------|
[-- JS: Batch Reads --] -> [-- JS: Batch Writes --] 
       (DOM)                      (DOM/Class)       
                                       |
                                    [Layout] (Hanya SEKALI per frame)
                                       |
                                    [Paint]
                                       |
                   [Compositor Thread Mengambil Alih untuk Frame Selanjutnya]
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Menghindari Forced Synchronous Layout
Contoh berikut mengilustrasikan perbedaan fatal antara layout thrashing dan batching mutasi DOM.

```javascript
/**
 * @file layout-optimization.js
 * Demonstrasi eliminasi Forced Synchronous Layout
 */

// ANTI-PATTERN: Forced Synchronous Layout (Layout Thrashing)
function resizeElementsBad(elements) {
  // Profiler akan mendeteksi multiple "Recalculate Style" dan "Layout" events
  for (let i = 0; i < elements.length; i++) {
    // READ: Memaksa Layout Tree dihitung secara instan karena ada perubahan sebelumnya
    const currentWidth = elements[i].offsetWidth; 
    // WRITE: Membatalkan Layout Tree yang baru saja dihitung
    elements[i].style.width = `${currentWidth + 10}px`; 
  }
}

// ARSITEKTUR OPTIMAL: Read/Write Separation (Batching)
function resizeElementsOptimized(elements) {
  const count = elements.length;
  const widths = new Float64Array(count);

  // Phase 1: Batch READ (Hanya 1 kali query ke layout tree)
  for (let i = 0; i < count; i++) {
    widths[i] = elements[i].offsetWidth;
  }

  // Phase 2: Batch WRITE (Ditunda ke frame berikutnya atau dikelompokkan bersama)
  window.requestAnimationFrame(() => {
    for (let i = 0; i < count; i++) {
      elements[i].style.width = `${widths[i] + 10}px`;
    }
  });
}
```

#### 7.2. Practical Example: Stream Processing dengan Backpressure & Zero Main-Thread Parsing
Berikut adalah implementasi nyata pipeline transfer data transaksi bernilai miliaran byte. Kode menggunakan `TransformStream` untuk membedah NDJSON (*Newline Delimited JSON*) biner secara chunked tanpa membekukan Main Thread, dialirkan ke `OffscreenCanvas` di dalam Web Worker.

##### `worker.js` (Web Worker Pipeline)
```javascript
/**
 * @file worker.js
 * Dedicated Worker: Stream consumer, Data Parsing, dan OffscreenCanvas Rendering
 */

/**
 * Custom TransformStream untuk mengurai chunks biner Uint8Array menjadi string per baris
 * @returns {TransformStream<Uint8Array, string>}
 */
function createLineSplitter() {
  let buffer = '';
  const decoder = new TextDecoder();

  return new TransformStream({
    transform(chunk, controller) {
      buffer += decoder.decode(chunk, { stream: true });
      const lines = buffer.split('\n');
      // Simpan sisa baris yang belum utuh di buffer
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.trim().length > 0) {
          controller.enqueue(line);
        }
      }
    },
    flush(controller) {
      if (buffer.trim().length > 0) {
        controller.enqueue(buffer);
      }
    }
  });
}

/**
 * Custom TransformStream untuk serialisasi string JSON menjadi entitas objek
 * @returns {TransformStream<string, object>}
 */
function createJSONParser() {
  return new TransformStream({
    transform(line, controller) {
      try {
        const parsed = JSON.parse(line);
        controller.enqueue(parsed);
      } catch (err) {
        console.error('Data corrupted, skipping frame:', err);
      }
    }
  });
}

/**
 * Menginisialisasi listener worker
 */
self.onmessage = async (event) => {
  const { type, canvas, dataUrl } = event.data;

  if (type === 'INIT_PIPELINE') {
    /** @type {OffscreenCanvas} */
    const offscreen = canvas;
    const ctx = offscreen.getContext('2d');
    if (!ctx) throw new Error('Cannot acquire 2D context from OffscreenCanvas');

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, offscreen.width, offscreen.height);

    let renderY = 20;

    try {
      // Inisiasi HTTP streaming request
      const response = await fetch(dataUrl, {
        headers: { 'Accept': 'application/x-ndjson' },
        priority: 'high' // Priority Hints untuk Network Service
      });

      if (!response.body) {
        throw new Error('Response body streaming is not supported');
      }

      // Stream pipeline execution dengan backpressure native
      const stream = response.body
        .pipeThrough(createLineSplitter())
        .pipeThrough(createJSONParser());

      const reader = stream.getReader();

      while (true) {
        const { value: record, done } = await reader.read();
        if (done) break;

        // Render data visual langsung di OffscreenCanvas tanpa sentuh Main Thread
        ctx.fillStyle = record.type === 'BUY' ? '#22c55e' : '#ef4444';
        ctx.fillRect(record.x, renderY, record.volume * 0.1, 4);
        renderY = (renderY + 8) % offscreen.height;
      }

      self.postMessage({ type: 'STATUS', status: 'STREAM_COMPLETED' });
    } catch (error) {
      self.postMessage({ type: 'ERROR', error: error.message });
    }
  }
};
```

##### `main.js` (Main Thread Orchestrator)
```javascript
/**
 * @file main.js
 * Inisialisasi OffscreenCanvas, Worker Thread Pool, dan Network Pre-connections
 */

// Inisialisasi Resource Hints secara dinamis via DOM
function injectNetworkOptimizations(targetDomain) {
  // Preconnect TCP + TLS Handshake
  const preconnectLink = document.createElement('link');
  preconnectLink.rel = 'preconnect';
  preconnectLink.href = targetDomain;
  preconnectLink.crossOrigin = 'anonymous';
  document.head.appendChild(preconnectLink);

  // Speculation Rules API (jika didukung) untuk prefetching route navigasi berikutnya
  if (HTMLScriptElement.supports && HTMLScriptElement.supports('speculationrules')) {
    const specScript = document.createElement('script');
    specScript.type = 'speculationrules';
    specScript.textContent = JSON.stringify({
      prefetch: [
        {
          source: 'list',
          urls: ['/analytics-overview', '/order-book'],
          requires: ['anonymous-client-ip-when-cross-origin']
        }
      ]
    });
    document.head.appendChild(specScript);
  }
}

async function bootstrap() {
  injectNetworkOptimizations('https://api.marketdata.enterprise.com');

  const canvasElement = document.getElementById('telemetry-canvas');
  if (!(canvasElement instanceof HTMLCanvasElement)) {
    throw new Error('Canvas element not found in DOM');
  }

  // Transfer kepemilikan canvas ke Worker thread
  const offscreen = canvasElement.transferControlToOffscreen();
  const worker = new Worker(new URL('./worker.js', import.meta.url), {
    type: 'module'
  });

  worker.onmessage = (e) => {
    const { type, status, error } = e.data;
    if (type === 'STATUS') console.log(`Worker Event: ${status}`);
    if (type === 'ERROR') console.error(`Worker Failure: ${error}`);
  };

  // Transfer Control: canvas context kini sepenuhnya berada di Worker
  worker.postMessage(
    {
      type: 'INIT_PIPELINE',
      canvas: offscreen,
      dataUrl: 'https://api.marketdata.enterprise.com/v1/stream-trades'
    },
    [offscreen] // Transferable Object: Memori dipindahkan, bukan disalin
  );
}

document.addEventListener('DOMContentLoaded', bootstrap);
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low Latency FinTech Trading Terminal (250,000 Updates/Detik)
- **Konteks**: Sebuah institusi finansial global membangun aplikasi order-book real-time berbasis web. Aplikasi menerima pembaruan status transaksi bursa via Secure WebSockets (WSS) dan Server-Sent Events (SSE).
- **Insiden di Produksi**:
  Pada sesi pembukaan pasar saham (high volatility), tab browser mengalami *tab crash* (OOM - Out of Memory) atau drop frame masif (0-5 FPS). Metrik Core Web Vitals mencatat INP melonjak ke **2.4 detik**, dan browser sering menampilkan status "*Page Unresponsive*".
- **Akar Masalah (Root Cause)**:
  1. *JSON Parsing Overhead*: Serialisasi JSON sebesar 12 MB/detik dilakukan langsung di Main Thread. Microtask queue dipenuhi oleh unresolved Promises dari websocket listeners.
  2. *Layout Thrashing Eksplosif*: Komponen UI memperbarui DOM nodes tabel order book sebanyak 10.000 kali per detik tanpa throttling, memicu `Recalculate Style` dan `Layout` secara berantai pada subtree yang memiliki 8.000 nested DOM elements.
  3. *Compositor Layer Explosion*: Developer menambahkan rule CSS `will-change: transform` ke setiap baris tabel untuk "mengoptimalkan" animasi, yang memaksa GPU process mengalokasikan ribuan backing texture hingga batas VRAM GPU (2 GB) terlampaui.

#### Solusi Arsitektural & Hasil Rekayasa:

```
+-----------------------------------------------------------------------------------+
|                              MAIN THREAD (Zero Jank)                              |
|  - Minimal DOM: Virtual List (hanya render 40 baris terlihat)                     |
|  - Tidak ada kalkulasi bisnis/parsing                                             |
|  - Scheduler via requestAnimationFrame + MessageChannel                           |
+-----------------------------------------------------------------------------------+
            ^                                                ^
            | (Immutable Frame Updates - 60 FPS)             | SharedArrayBuffer /
            | PostMessage (Transferable)                     | Atomics (Zero-Copy)
+-------------------------------------------------+          |
|                 WEB WORKER POOL                 |----------+
|  Worker 1: WebSocket / SSE Ingestion            |
|  Worker 2: ArrayBuffer Deserializer (Protobuf)  |
|  Worker 3: In-Memory Order Book State Engine    |
+-------------------------------------------------+
```

1. **Offloading Transport & Parsing**:
   Memindahkan WebSocket connection ke `SharedWorker`. Payload biner diubah dari JSON ke **Protocol Buffers (Protobuf)** via ArrayBuffer. Data didekode sepenuhnya di worker tanpa mengonsumsi CPU Main Thread.
2. **Eliminasi Compositor Overdraw**:
   Menghapus rule `will-change: transform` massal. Menerapkan CSS `contain: strict;` pada container order-book agar kalkulasi Layout subtree tidak memicu reflow pada keseluruhan halaman (*Layout Boundaries*).
3. **Double-Buffering & RAF Throttling**:
   State transaksi diakumulasikan di Worker. Main Thread hanya meminta *diff snapshot* tepat sebelum fase V-Sync menggunakan `requestAnimationFrame`, dibatasi maksimal 60 updates/detik ke DOM.
4. **Hasil Akhir**:
   - Frame rate stabil pada **58 - 60 FPS** konstan saat market spike.
   - P99 Interaction to Next Paint (INP) turun dari **2,400ms** menjadi **18ms**.
   - Penggunaan memori heap V8 turun sebesar **74%**.

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan (Pros) | Biaya & Risiko (Cons) | Kapan Digunakan | Kapan Dihindari |
| :--- | :--- | :--- | :--- | :--- |
| **Worker Offloading (Web Worker/SharedWorker)** | Membebaskan Main Thread dari komputasi berat; INP stabil; zero-jank processing. | Serialization overhead pada `postMessage` (jika tidak transfer buffer); kehilangan direct DOM access; kompleksitas debugging state. | Pemrosesan file biner/JSON besar, parsing data stream, kriptografi, komputasi grafik. | UI interaktif sederhana, mutasi state lokal kecil, event handler biasa. |
| **Composited Layers (`transform`, `opacity`, `will-change`)** | Animasi diakselerasi hardware oleh GPU; bebas dari Layout & Paint passes; smooth 120 FPS. | *Layer Explosion*: Konsumsi VRAM melonjak drastis; text blurry akibat rasterization sub-pixel scale; latency komposit awal. | Animasi transformasi, sliding drawer, modal transitions, smooth scrolling lists. | Diaplikasikan ke ratusan/ribuan elemen sekaligus di dalam satu view (e.g. table rows). |
| **Streams API vs Direct Payload Fetching** | Memory footprint rendah; Time-to-First-Action (TTFA) cepat; pemrosesan data dengan backpressure. | Kompleksitas penanganan chunk parsing (memerlukan buffer boundaries state); dukungan tooling analitik terbatas. | File transfer ukuran > 5MB, continuous streaming (NDJSON), telemetry log aggregation. | Endpoint REST JSON pendek di bawah 50KB dengan siklus render tunggal. |
| **Speculation Rules API (Prerender)** | Navigasi halaman instan (0ms perceived latency) karena halaman dirender penuh di background. | Konsumsi bandwidth dan baterai tinggi; potensi eksekusi analytics berulang jika tidak diisolasi; konkurensi memori bertambah. | Navigasi funnel checkout krusial dengan probabilitas klik > 80%. | Kondisi koneksi seluler lambat (Save-Data header aktif), atau halaman dengan side-effects finansial. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus Debugging 1: The Invisible Layer Explosion (Crash VRAM GPU)
- **Gejala**: Aplikasi crash pada perangkat mobile mid-end atau GPU tab reset saat membuka daftar list panjang. Performance timeline menunjukkan *Gpu Rasterization Time* sangat tinggi.
- **Akar Masalah**: Penggunaan snippet CSS berikut secara sembarangan:
  ```css
  /* ANTI-PATTERN */
  .list-item {
    will-change: transform; /* Menciptakan layer grafis unik untuk setiap baris */
  }
  ```
- **Solusi Troubleshooting**:
  1. Buka Chrome DevTools -> Tekan `Cmd+Shift+P` (Mac) atau `Ctrl+Shift+P` (Win) -> Ketik `Show Layers`.
  2. Periksa panel Layers: Amati jumlah total composite layer dan estimasi memori. Jika layer > 50-100, terjadi layer explosion.
  3. Hapus properti `will-change` statis. Terapkan secara dinamis hanya saat interaksi dimulai (`pointerenter`), dan hapus saat selesai (`transitionend`).

#### Kasus Debugging 2: High Interaction to Next Paint (INP) Akibat Long Microtasks
- **Gejala**: Lighthouse mencatat skor INP merah (> 400ms). Trace Performance menunjukkan blok oranye lebar bernama `Task` dengan sub-blok `Run Microtasks`.
- **Akar Masalah**: Menggunakan `Promise.resolve().then(...)` secara rekursif atau chaining promises berskala ribuan untuk memecah beban tugas. Microtask dijalankan tepat setelah stack panggilan saat ini kosong, dan **tidak pernah mengembalikan kontrol ke Event Loop** untuk me-render frame! Main thread tetap terblokir hingga antrean microtask habis.
- **Solusi**: Gunakan `scheduler.yield()` modern atau fallback ke `scheduler.postTask` / Task Queue via `MessageChannel`:
  ```javascript
  // Helper memecah Long Task ke Macrotask Queue sejati
  async function yieldToMain() {
    if ('scheduler' in window && 'yield' in window.scheduler) {
      return await window.scheduler.yield();
    }
    return new Promise((resolve) => {
      const { port1, port2 } = new MessageChannel();
      port1.onmessage = () => resolve();
      port2.postMessage(null);
    });
  }

  async function processHeavyArray(items) {
    for (let i = 0; i < items.length; i++) {
      heavyComputation(items[i]);
      // Kembalikan kendali ke engine setiap 16ms agar UI dapat merender frame baru
      if (i % 100 === 0) {
        await yieldToMain();
      }
    }
  }
  ```

---

### 11. Best Practices (Production Checklist)

#### Network Layer Optimization
- [ ] Aktifkan **HTTP/3 (QUIC)** pada Edge Server / CDN untuk mengurangi dampak packet loss pada jaringan mobile.
- [ ] Implementasikan **103 Early Hints** untuk stylesheet kritis dan preconnect domain font pihak ketiga.
- [ ] Atur atribut `fetchpriority="high"` secara eksklusif hanya pada Largest Contentful Paint (LCP) element image tag.
- [ ] Terapkan header `Cache-Control: public, max-age=31536000, immutable` pada seluruh static assets ber-hash.

#### Rendering Pipeline Optimization
- [ ] Gunakan CSS `contain: content` atau `contain: strict` pada kontainer modular untuk membatasi ruang lingkup Reflow/Paint engine.
- [ ] Manfaatkan CSS property `content-visibility: auto` untuk elemen off-screen guna menunda kalkulasi layout hingga mendekati viewport.
- [ ] Pastikan seluruh animasi hanya memanipulasi properti yang di-handle oleh Compositor Thread: `transform` dan `opacity`. Hindari menganimasikan `top`, `left`, `width`, `height`, atau `box-shadow`.
- [ ] Eliminasi Forced Synchronous Layout: Hindari pembacaan geometri DOM (`offsetHeight`, `clientWidth`, `scrollTop`) tepat setelah memodifikasi styling inline atau class.

#### Execution Thread Optimization
- [ ] Pindahkan parsing dataset kompleks (CSV, XML, JSON > 1MB) ke Web Worker.
- [ ] Gunakan `OffscreenCanvas` saat merender chart dinamis, canvas visualizer, atau pemrosesan gambar skala besar.
- [ ] Audit Long Tasks (> 50ms) menggunakan `PerformanceObserver` dengan opsi `buffered: true` dan pantau metric `Long Animation Frames (LoAF)`.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun pipeline streaming performa tinggi untuk memproses payload log besar secara non-blocking. Struktur repositori yang harus disiapkan:

```
hands-on/m02/
├── index.html
├── server.js
├── src/
│   ├── app.js
│   ├── worker.js
│   └── styles.css
└── package.json
```

#### Langkah 1: Inisialisasi Project & Dependencies
Jalankan di terminal:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
npm init -y
npm install fastify @fastify/cors
```

#### Langkah 2: Buat Server Penyedia NDJSON Stream (`server.js`)
```javascript
import Fastify from 'fastify';
import cors from '@fastify/cors';
import { Readable } from 'node:stream';

const fastify = Fastify({ logger: false });
fastify.register(cors, { origin: '*' });

fastify.get('/stream-logs', async (request, reply) => {
  reply.raw.setHeader('Content-Type', 'application/x-ndjson');
  reply.raw.setHeader('Transfer-Encoding', 'chunked');

  let count = 0;
  const maxRecords = 50000;

  const nodeStream = new Readable({
    read() {
      // Menghasilkan chunk buatan secara streaming
      if (count >= maxRecords) {
        this.push(null);
        return;
      }

      // Kirim batch 500 baris per tick
      let batch = '';
      for (let i = 0; i < 500 && count < maxRecords; i++) {
        const payload = JSON.stringify({
          id: ++count,
          timestamp: Date.now(),
          level: count % 5 === 0 ? 'ERROR' : 'INFO',
          value: Math.random() * 100
        });
        batch += payload + '\n';
      }
      this.push(batch);
    }
  });

  return reply.send(nodeStream);
});

fastify.listen({ port: 3000 }, (err) => {
  if (err) throw err;
  console.log('Telemetry Server running at http://localhost:3000');
});
```

#### Langkah 3: Antarmuka UI Rendering (`index.html`)
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>High-Performance Pipeline Playground</title>
  <link rel="stylesheet" href="src/styles.css">
</head>
<body>
  <div class="layout-container">
    <header>
      <h1>Engine Pipeline Telemetry</h1>
      <button id="btn-start">Start Streaming Ingestion</button>
      <div id="metrics-panel">Processed: <span id="counter">0</span> records</div>
    </header>

    <main class="viewport-canvas">
      <!-- Canvas ini akan dioper ke Worker Thread -->
      <canvas id="pipeline-canvas" width="800" height="400"></canvas>
    </main>
  </div>
  <script type="module" src="src/app.js"></script>
</body>
</html>
```

#### Langkah 4: CSS dengan Isolasi Layout Boundary (`src/styles.css`)
```css
body {
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
  background: #0b0f19;
  color: #f1f5f9;
}

.layout-container {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.viewport-canvas {
  /* Layout Boundary Isolation */
  contain: strict;
  width: 800px;
  height: 400px;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  background: #020617;
}

canvas {
  display: block;
}
```

#### Langkah 5: Worker Ingestion Engine (`src/worker.js`)
```javascript
let canvasCtx = null;
let xCursor = 0;

self.onmessage = async (e) => {
  const { type, canvas, endpoint } = e.data;

  if (type === 'INIT') {
    canvasCtx = canvas.getContext('2d');
    canvasCtx.fillStyle = '#020617';
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

    try {
      const response = await fetch(endpoint);
      if (!response.body) throw new Error('ReadableStream not supported');

      const textDecoder = new TextDecoder();
      const reader = response.body.getReader();
      let pendingBuffer = '';
      let processedCount = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        pendingBuffer += textDecoder.decode(value, { stream: true });
        const lines = pendingBuffer.split('\n');
        pendingBuffer = lines.pop() || '';

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();
          if (!line) continue;

          const record = JSON.parse(line);
          processedCount++;

          // Visualisasi langsung di OffscreenCanvas
          canvasCtx.fillStyle = record.level === 'ERROR' ? '#f43f5e' : '#38bdf8';
          const barHeight = (record.value / 100) * 380;
          canvasCtx.fillRect(xCursor, 400 - barHeight, 2, barHeight);

          xCursor = (xCursor + 3) % canvas.width;
          if (xCursor === 0) {
            canvasCtx.fillStyle = 'rgba(2, 6, 23, 0.4)';
            canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
          }
        }

        // Emit telemetry secara batch ke main thread
        self.postMessage({ type: 'PROGRESS', count: processedCount });
      }

      self.postMessage({ type: 'COMPLETE' });
    } catch (err) {
      self.postMessage({ type: 'ERROR', message: err.message });
    }
  }
};
```

#### Langkah 6: Client Orchestrator (`src/app.js`)
```javascript
const btnStart = document.getElementById('btn-start');
const counterEl = document.getElementById('counter');
const canvasEl = document.getElementById('pipeline-canvas');

let worker = null;

// Pantau Long Animation Frames (LoAF) untuk memastikan Main Thread tetap 0ms jank
if ('PerformanceObserver' in window) {
  try {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 50) {
          console.warn(`[LoAF Warning] Main Thread Blocked: ${entry.duration.toFixed(2)}ms`, entry);
        }
      }
    });
    observer.observe({ type: 'long-animation-frame', buffered: true });
  } catch {
    // Graceful degradation bila LoAF tidak didukung browser
  }
}

btnStart.addEventListener('click', () => {
  btnStart.disabled = true;

  // Inisialisasi OffscreenCanvas
  const offscreen = canvasEl.transferControlToOffscreen();
  worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });

  worker.onmessage = (event) => {
    const { type, count, message } = event.data;
    if (type === 'PROGRESS') {
      counterEl.textContent = count.toLocaleString();
    } else if (type === 'COMPLETE') {
      btnStart.disabled = false;
      console.log('Stream data visualization successfully finalized.');
    } else if (type === 'ERROR') {
      console.error('Worker failed:', message);
    }
  };

  worker.postMessage(
    {
      type: 'INIT',
      canvas: offscreen,
      endpoint: 'http://localhost:3000/stream-logs'
    },
    [offscreen]
  );
});
```

---

### 13. Exercises

#### Level: Easy
1. **Identifikasi Forced Synchronous Layout**:
   Diberikan blok kode:
   ```javascript
   function updateCardHeights() {
     const cards = document.querySelectorAll('.card');
     for (let i = 0; i < cards.length; i++) {
       const height = cards[i].getBoundingClientRect().height;
       cards[i].style.height = `${height * 1.2}px`;
     }
   }
   ```
   Tulis ulang fungsi di atas menggunakan pola decoupled read-write phases (`requestAnimationFrame`) agar browser hanya melakukan kalkulasi layout satu kali.

#### Level: Medium
1. **Transform Stream Decoupler**:
   Buat sebuah `TransformStream` yang berfungsi sebagai rate limiter. Stream ini menerima chunk teks, mengelompokkannya hingga mencapai ukuran minimal 64KB, lalu mengirimkannya ke controller downstream guna mengurangi frekuensi emit pada sistem penerima. Pastikan metode `flush` membersihkan sisa data secara benar saat stream ditutup.

#### Level: Hard
1. **Network Priority & Speculative Routing Controller**:
   Bangun library JavaScript vanilla (`NavigationPrefetcher`) yang:
   - Mengamati pergerakan kursor pengguna (`pointerover` pada tautan).
   - Memastikan pengguna meng-hover tautan minimal selama 65 milidetik (*intent threshold*) sebelum memicu aksi.
   - Menginjeksikan aturan `Speculation Rules API` dinamis untuk mem-prerender rute tersebut jika browser mendukungnya.
   - Menyediakan graceful fallback menggunakan `fetch(url, { priority: 'low' })` untuk browser yang belum mendukung Speculation Rules API.
   - Membatalkan (abort) network request jika pointer keluar (`pointerout`) dari link sebelum 65ms tercapai.

---

### 14. Challenge

#### Skenario Kasus Kompleks: "The Degraded Black Friday Checkout"
- **Kondisi Awal**: Platform e-commerce enterprise Anda mengalami lonjakan traffic 10x lipat saat kampanye diskon berlangsung.
- **Problem Statement**:
  1. Halaman checkout menerima keluhan dari jutaan pengguna smartphone entry-level Android: tombol "Bayar Sekarang" sering kali tidak merespons klik (unresponsive) selama 3-5 detik setelah halaman selesai dimuat visualnya (Metrik **INP** mencapai 3800ms).
  2. Profiler menunjukkan LCP (Largest Contentful Paint) gambar produk terlambat muncul pada detik ke-7 karena terhalang antrean (*network waterfall*) oleh 15 script analitik pihak ketiga.
  3. Saat pengguna mengetikkan kupon promo, seluruh kolom form mengalami *keyboard typing lag* yang parah. Script validasi kupon memanipulasi DOM dan membaca styling CSS secara inline pada event listener `keydown`.
- **Misi Anda**:
  Rancang dan implementasikan cetak biru arsitektur (arsitektur script, CSS layering, strategi orkestrasi resource, dan task chunking) tanpa menghapus script analitik bisnis yang diwajibkan oleh stakeholder, dengan batasan ketat:
  - P95 INP < 150ms.
  - P95 LCP < 2.0 detik pada koneksi 4G standar.
  - Tidak diperbolehkan menggunakan framework pihak ketiga (wajib Zero-Dependency Vanilla JavaScript).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Pertanyaan**: Apa perbedaan utama antara fase Layout (Reflow) dan Paint (Repaint) pada pipeline engine browser?
   - **Jawaban & Rationale**: Layout menghitung posisi geometri absolut dan ukuran kotak (*bounding box*) setiap elemen pada layar. Paint mengonversi elemen tersebut menjadi sekumpulan instruksi visual (Skia display items/commands) untuk menggambar warna, border, teks, dan bayangan. Layout selalu memicu Paint, tetapi Paint belum tentu memicu Layout.

2. **Pertanyaan**: Mengapa memanipulasi properti CSS `transform` dan `opacity` jauh lebih efisien dibandingkan memanipulasi `top` atau `left`?
   - **Jawaban & Rationale**: Properti `top` dan `left` mengubah geometri elemen sehingga memaksa browser menjalankan siklus *Layout -> Paint -> Composite*. Sebaliknya, modifikasi `transform` dan `opacity` melewati tahap Layout dan Paint secara total; perubahannya dikomputasi langsung pada Compositor Thread dan GPU Process (*Compositor-only property*), menjaga frame rate 60/120fps.

3. **Pertanyaan**: Mengapa eksekusi tag `<script>` synchronous bersifat parser-blocking?
   - **Jawaban & Rationale**: Karena JavaScript memiliki kapabilitas untuk memodifikasi struktur dokumen secara langsung (misalnya melalui `document.write` atau manipulasi node) dan membaca computed style (CSSOM). Engine browser harus menghentikan tokenisasi HTML hingga script diunduh dan dieksekusi selesai demi menjaga integritas pohon DOM.

4. **Pertanyaan**: Apa fungsi dari atribut `fetchpriority="high"` pada elemen `<img>`?
   - **Jawaban & Rationale**: Memberikan petunjuk eksplisit kepada Resource Fetcher di Network Service browser untuk menaikkan prioritas scheduling download gambar tersebut di atas resource lain dengan prioritas default/rendah, sehingga gambar LCP dapat dimuat secepat mungkin.

5. **Pertanyaan**: Apa yang terjadi jika buffer `postMessage` tidak di-transfer (bukan Transferable Object) saat dikirim ke Web Worker?
   - **Jawaban & Rationale**: Data akan diduplikasi secara mendalam menggunakan algoritma Structured Clone. Jika datanya besar (misal array biner 100MB), penyalinan memori ini memakan waktu puluhan milidetik di Main Thread, menyebabkan frame drop dan peningkatan alokasi memori heap V8 secara ganda.

#### Intermediate Questions
6. **Pertanyaan**: Bagaimana mekanisme HTTP/3 QUIC mengeliminasi masalah Head-of-Line (HoL) Blocking yang masih terjadi pada HTTP/2?
   - **Jawaban & Rationale**: HTTP/2 membungkus banyak stream logika di dalam satu koneksi transport TCP tunggal. Jika sebuah paket TCP hilang (*packet loss*), TCP stack menahan seluruh byte buffer downstream hingga paket yang hilang dikirim ulang (*retransmitted*), memblokir semua HTTP/2 stream yang ada di koneksi tersebut. HTTP/3 menggunakan protokol UDP di mana protokol QUIC mengelola streams secara independen pada transport level. Packet loss pada Stream A tidak memengaruhi kelanjutan pembacaan data pada Stream B.

7. **Pertanyaan**: Jelaskan bahaya penggunaan `requestAnimationFrame` untuk operasi komputasi non-rendering yang berat!
   - **Jawaban & Rationale**: `requestAnimationFrame` dieksekusi tepat sebelum browser melakukan kalkulasi Style, Layout, dan Paint pada Main Thread. Menjalankan kalkulasi komputasi non-visual yang berat di dalam callback ini akan langsung memperpanjang durasi rendering pipeline, melewati batas frame budget (16.6ms untuk 60fps), dan menghasilkan visual jank seketika.

8. **Pertanyaan**: Apa peran `Property Trees` dalam Blink/Chromium engine pipeline modern?
   - **Jawaban & Rationale**: Property Trees memisahkan data spesifik seperti Transform, Clip, Effect (opacity), dan Scroll dari Layout Object Tree. Hal ini memungkinkan Compositor Thread memproses scroll dan transformasi hierarkis tanpa harus melakukan traversal rekursif yang mahal terhadap seluruh Layout Tree.

9. **Pertanyaan**: Mengapa pemanggilan `getBoundingClientRect()` secara langsung setelah menambahkan class CSS baru memicu *Layout Thrashing*?
   - **Jawaban & Rationale**: Penambahan class CSS menandai layout tree dalam kondisi *dirty* (invalidated). Pemanggilan `getBoundingClientRect()` memaksa engine sinkron secara imperatif untuk mengembalikan geometri geometris akurat detik itu juga. Engine terpaksa menghentikan eksekusi JS dan mengeksekusi kalkulasi style dan layout secara prematur (*Forced Synchronous Layout*).

10. **Pertanyaan**: Bagaimana cara kerja Speculation Rules API dibandingkan dengan tag `<link rel="prefetch">` tradisional?
    - **Jawaban & Rationale**: `<link rel="prefetch">` hanya mengunduh resource statis dokumen HTML dan menyimpannya di cache HTTP. `Speculation Rules API` mendukung aturan dinamis berbasis JSON dan mampu melakukan *full prerendering*—membuka halaman di renderer process tak terlihat di background, menjalankan JavaScript, membangun DOM, hingga eksekusi layout penuh. Saat user mengklik link, halaman instan berganti tanpa loading time (0ms navigation).

#### Production Scenarios
11. **Pertanyaan**: Dalam audit performa SaaS Analytics Dashboard, ditemukan bahwa interaksi sorting tabel data 5.000 baris memakan waktu 350ms. Performance panel menunjukkan blok besar kuning bertuliskan "Recalculate Style" dan "Layout" yang memakan waktu 300ms. Bagaimana tahapan mitigasi teknis Anda untuk menurunkan angka tersebut di bawah 50ms tanpa mengurangi jumlah data?
    - **Solusi & Analisis**:
      1. Terapkan arsitektur *Virtual Scrolling*: Render ke DOM hanya 20-50 baris yang saat ini berada di dalam viewport pengguna. Sisanya diwakili oleh placeholder spacer atau padding.
      2. Terapkan isolasi render boundary pada container tabel menggunakan `contain: strict;` dan `content-visibility: auto;`.
      3. Pindahkan algoritma sorting dan restructuring array data ke Dedicated Web Worker. Main Thread hanya menerima slice data terurut yang muat di viewport.
      4. Eksekusi mutasi DOM penggantian baris menggunakan `documentFragment` atau template cloning di dalam callback `requestAnimationFrame`.

12. **Pertanyaan**: Sistem telemetri mendeteksi bahwa pada rilis terbaru aplikasi mobile-web Anda, metrik Cumulative Layout Shift (CLS) melonjak tajam dari 0.02 menjadi 0.28. Setelah diinvestigasi, tidak ada perubahan ukuran banner atau gambar tanpa dimensi. Komponen apa pada pipeline rendering yang kemungkinan besar menjadi sumber masalah?
    - **Solusi & Analisis**:
      Akar masalah kemungkinan besar berasal dari *Font Loading Pipeline* yang memicu **FOUT (Flash of Unstyled Text)** atau pergeseran metrik font fallback. Ketika web font kustom dimuat secara asinkron tanpa sinkronisasi layout, penggantian font fallback dengan web font menyebabkan perbedaan dimensi glyph (*font metric mismatch*), sehingga teks reflow dan menggeser elemen di bawahnya.
      *Solusi*: Gunakan CSS `font-display: optional` (mencegah reflow layout jika font terlambat tiba) atau gunakan descriptor `@font-face` modern: `size-adjust`, `ascent-override`, dan `descent-override` untuk menyamakan metrik fallback font sistem secara presisi dengan target web font.

13. **Pertanyaan**: API gateway Anda mendukung HTTP/2 Multiplexing. Namun, monitoring network menunjukkan bahwa aset-aset JavaScript berukuran kecil (masing-masing 10KB) yang berjumlah 80 file dimuat secara berurutan (*waterfall pattern*), bukan paralel simultan. Apa penyebab kegagalan orkestrasi network pipeline ini di browser runtime?
    - **Solusi & Analisis**:
      Akar masalah terjadi karena ketergantungan modul asinkron bertingkat (*dynamic dependency chaining*): File A meng-import File B, yang kemudian meng-import File C (`import './b.js'`). Browser Preload Scanner tidak dapat mendeteksi dependensi tersebut sebelum script induk diunduh, di-parse, dan dieksekusi secara berurutan.
      *Solusi*: Gunakan `<link rel="modulepreload" href="...">` pada file-file esensial di dokumen HTML utama agar Preload Scanner dari Network Service mengunduh seluruh graph dependensi secara paralel di transport stream HTTP/2 tanpa menunggu hasil eksekusi V8 module resolution.

---

### 16. Summary

1. **Rendering Engine Pipeline Hierarchy**:
   Rendering modern membagi tugas secara ketat: DOM/CSSOM (Parsing) $\to$ Style Recalculation $\to$ Layout (Geometry) $\to$ Paint (Drawing Instructions) $\to$ Compositing $\to$ Tiling/Rasterization (GPU). Menguasai pemisahan ini memungkinkan pencegahan *Layout Thrashing* dan pemanfaatan jalur akselerasi hardware.
2. **Thread Boundary Optimization**:
   Main Thread browser harus dilindungi untuk interaktivitas pengguna (menjamin metrik INP optimal). Operasi non-visual dan komputasi berat (streaming ingestion, file parsing, state computation) wajib dialirkan ke Web Worker pool, sementara grafis intensif dioper ke `OffscreenCanvas`.
3. **Transport Layer Primacy**:
   Efisiensi runtime dimulai dari Network Layer. Penggunaan HTTP/3 (QUIC) menuntaskan masalah packet-loss blocking, sementara Priority Hints (`fetchpriority`), Early Hints (103), dan Speculation Rules API memberi kendali presisi kepada engineer untuk mengatur pipeline pengiriman aset sebelum pipeline parsing engine dimulai.
4. **Data Stream Processing**:
   Mengintegrasikan WhatWG Streams API (`ReadableStream`, `TransformStream`) memampukan browser runtime menyerap volume payload enterprise secara kontinu dengan alokasi memori konstan melalui backpressure control, menghindari kegagalan alokasi memori V8 Heap Crash.