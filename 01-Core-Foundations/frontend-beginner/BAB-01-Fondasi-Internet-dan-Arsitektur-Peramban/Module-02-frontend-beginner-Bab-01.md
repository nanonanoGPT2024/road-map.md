# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis dan Membedah Siklus Internal Browser Engine**: Mengidentifikasi bagaimana Blink/V8 memproses byte stream jaringan menjadi pixels on screen melalui parsing, kalkulasi CSSOM, pembuatan Render Tree, Layout, Paint, hingga GPU Compositing.
2. **Mengeliminasi Runtime Layout Thrashing & Forced Synchronous Layout**: Mendiagnosis eksekusi JavaScript yang memicu reflow berulang melalui Performance Profiler dan memitigasinya menggunakan batching mutation, `requestAnimationFrame`, serta Virtual DOM primitives manual.
3. **Mengidentifikasi dan Memitigasi Detached DOM Nodes & V8 Memory Leaks**: Menggunakan Chrome DevTools Memory Heap Snapshot dan Allocation Timeline untuk melacak siklus hidup memori objek JavaScript dan referensi DOM yang tertinggal.
4. **Merancang Pipeline Network Resource Scheduling Tingkat Lanjut**: Mengimplementasikan strategi Resource Hints (`preload`, `prefetch`, `preconnect`), Priority Hints (`fetchpriority`), dan module bundling architecture yang tahan terhadap Network Bottleneck pada protokol HTTP/2 dan HTTP/3.
5. **Mengarsitekturi Enterprise Frontend Baseline**: Membangun fondasi arsitektur scalable production-ready tanpa framework bloated, mengintegrasikan Content Security Policy (CSP) nonces/hashes, Subresource Integrity (SRI), dan standard modularisasi clean directory structure.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus memiliki pemahaman mendalam tentang:
* **Dasar HTTP/1.1 vs HTTP/2**: Mekanisme multiplexing, head-of-line blocking, dan TCP handshake latency.
* **JavaScript Execution Context & Event Loop**: Perbedaan microtask (`Promise`, `queueMicrotask`) dan macrotask (`setTimeout`, I/O).
* **Konsep Dasar DOM & CSSOM**: Struktur pohon representasi data HTML/CSS.
* **Node.js Environment & Build Tools Dasar**: Penggunaan runtime Node.js, package manager (`pnpm` / `npm`), dan konsep bundling tools dasar (Vite/Rollup).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Browser Threading Model & Rendering Engine Pipeline

Browser modern (seperti Chromium) mengadopsi arsitektur multi-process:
1. **Browser Process**: Mengelola address bar, bookmarks, navigasi, dan network requests.
2. **Renderer Process**: Menjalankan WebAssembly/JavaScript (V8 engine), parsing HTML/CSS, kalkulasi DOM/CSSOM, layout, dan painting. Process ini di-sandbox untuk keamanan.
3. **GPU Process**: Mengelola render instruction dan mengirimkannya ke hardware display.

Di dalam **Renderer Process**, eksekusi dibagi ke beberapa dedicated thread:
* **Main Thread**: Mengeksekusi JavaScript, Style Calculation, Layout (Reflow), dan Paint Tree generation.
* **Compositor Thread**: Menerima draw quads dari Main Thread, membagi halaman menjadi layer-layer (tiling), dan mengirim perintah composite langsung ke GPU via IPC (Inter-Process Communication). Thread ini tetap responsif meskipun Main Thread mengalami lockup karena eksekusi JavaScript berat.
* **Raster Thread**: Mengubah display list hasil Paint menjadi bitmaps (rasterization), sering kali dibantu oleh Skia/Ganesh/Graphite graphics engine yang mengeksekusi instruksi langsung di GPU.
* **Worker Threads**: Mengisolasi eksekusi JavaScript latar belakang (`Web Workers`, `Service Worker`) tanpa memblokir Main Thread.

```
+-------------------------------------------------------------------------------+
| RENDERER PROCESS                                                              |
|                                                                               |
|  +-------------------------------------------------------------------------+  |
|  | MAIN THREAD                                                             |  |
|  |                                                                         |  |
|  |  [HTML Bytes] -> Tokenizer -> Parser -> DOM Tree                        |  |
|  |                                            |                            |  |
|  |  [CSS Bytes]  -> Tokenizer -> Parser -> CSSOM Tree                      |  |
|  |                                            |                            |  |
|  |                                     Render Tree                         |  |
|  |                                            |                            |  |
|  |                                     Layout (Reflow)                     |  |
|  |                                            |                            |  |
|  |                                         Paint                           |  |
|  |                                            |                            |  |
|  |                                     Display Lists                       |  |
|  |  [JS Engine: V8]                           |                            |  |
|  |  (Compiles & Executes) --------------------+                            |  |
|  +--------------------------------------------|----------------------------+  |
|                                               v Commit                        |
|  +-------------------------------------------------------------------------+  |
|  | COMPOSITOR THREAD                                                       |  |
|  |  - Layer Tiling                                                         |  |
|  |  - Viewport Scrolling & Pinch-Zoom                                      |  |
|  |  - Dispatches Raster Tasks ------------------------------------------+  |  |
|  +----------------------------------------------------------------------|--+  |
|                                                                         |     |
|  +-------------------------------------------------------------------+  |     |
|  | RASTER THREAD POOL                                                |  |     |
|  |  - Rasterizes Display Lists into Bitmaps in GPU/Shared Memory <----+  |     |
|  +-------------------------------------------------------------------|--+     |
+----------------------------------------------------------------------|--------+
                                                                       v IPC
+-------------------------------------------------------------------------------+
| GPU PROCESS                                                                   |
|  - Compositor Frame Assembly                                                  |
|  - Output to Display Surface / Screen Hardware Buffer                         |
+-------------------------------------------------------------------------------+
```

### 3.2 Critical Rendering Path (CRP) - Tahap Demi Tahap

1. **DOM Construction**: HTML tokenizer mengonversi raw bytes (`48 65 6c...`) menjadi karakter -> tokens (`StartTag: html`, `StartTag: body`) -> nodes -> DOM Tree. Parsing ini bersifat *incremental*; browser tidak menunggu seluruh dokumen terunduh untuk mulai membangun DOM.
2. **CSSOM Construction**: CSS bersifat *render-blocking*. Browser tidak dapat menampilkan konten halaman sebelum selesai mem-parse seluruh CSS karena aturan CSS yang ditulis di akhir dapat menimpa (*cascade*) aturan di awal. Berbeda dengan HTML, CSSOM *tidak dapat* dibangun secara parsial untuk keperluan rendering visual.
3. **Render Tree Generation**: Kombinasi DOM dan CSSOM. Node dengan `display: none` diabaikan sepenuhnya dari Render Tree, sedangkan elemen dengan `visibility: hidden` tetap masuk ke dalam Render Tree karena masih memakan ruang geometris pada layar. Elemen semu (pseudo-elements seperti `::before`, `::after`) dibuat pada fase ini.
4. **Layout (Reflow)**: Menghitung posisi dan geometri pasti dari setiap node dalam viewport. Mengukur posisi `(x, y)` dan dimensi `(width, height)`. Bersifat hierarkis; perubahan dimensi pada root node dapat memicu recalculation ke seluruh subtree.
5. **Paint**: Mengonversi Render Tree menjadi display list instruksi visual: `drawRect()`, `drawText()`, urutan `z-index`, bayangan, dan perbatasan.
6. **Compositing**: Mengangkat elemen-elemen tertentu ke hardware layer tersendiri (menggunakan property seperti `transform`, `opacity`, `will-change`), kemudian Compositor Thread mengombinasikan layer-layer tersebut tanpa memicu Layout ulang atau Paint ulang di Main Thread.

### 3.3 Memory Lifecycle & V8 Internals: Garbage Collection

V8 mengalokasikan memori dalam beberapa segmen:
* **New Space (Nursery & Intermediate Semi-Spaces)**: Objek baru dialokasikan di sini. Berukuran kecil (1-64MB). Dikelola oleh algoritma **Scavenger** (Cheney's Copying Algorithm) yang sangat cepat.
* **Old Pointer Space & Old Data Space**: Objek yang selamat dari dua siklus Scavenger dipromosikan (*tenured*) ke sini. Dikelola oleh **Major GC (Mark-Sweep-Compact)**:
  * *Marking*: Menelusuri roots (global `window`, call stack variables, active DOM wrappers). Menandai objek yang reachable. Menggunakan *Tri-color marking* (White, Grey, Black) secara inkremental dan concurrent.
  * *Sweeping*: Menemukan memory blocks kosong dari objek White (unreachable) dan menambahkannya ke free-list.
  * *Compacting*: Menggeser memori untuk menata kembali fragmentasi memori pada Old Space.

```
V8 HEAP STRUCTURE:
+----------------------------------------------------------------------------+
| NEW SPACE (1MB - 64MB)                 | OLD SPACE                         |
| +-----------------+------------------+ | +-------------------------------+ |
| | From-Space      | To-Space         | | | Old Pointer Space             | |
| | (Nursery Alloc) | (Scavenge Target)| | | (References to other objects) | |
| +-----------------+------------------+ | +-------------------------------+ |
|         |                   ^          | | Old Data Space                | |
|         +--- Scavenge Cycle-+          | | (Raw data: strings, boxed int)| |
|                   |                    | +-------------------------------+ |
|                   +--- 2x Survived --->| Large Object Space (No GC move)   |
|                        Promotion       | Code Space (JIT compiled asm)     |
+----------------------------------------+-----------------------------------+
```

#### Penyebab Detached DOM Tree
DOM node ditulis dalam C++ (Blink core engine) dan diekspos ke JavaScript melalui *V8 Wrapper Object*. 
Jika sebuah elemen dihapus dari DOM document via `element.remove()`, namun masih ada referensi JavaScript aktif (misalnya tersimpan dalam variabel global, closure event listener, array cache), maka C++ DOM node tersebut tidak dapat dibebaskan oleh Blink Garbage Collector. Node ini menjadi **Detached DOM Node**, mengonsumsi memori native Blink dan heap V8 secara simultan.

---

## 4. Why & What

### Mengapa Memahami Internal Engine Sangat Penting di Level Enterprise?
Framework modern (React, Vue, Svelte) mengeksekusi abstraksi di atas Web API. Tanpa memahami lifecycle internal browser:
1. Engineer menulis kode deklaratif yang secara tidak sengaja memicu puluhan kali **Forced Synchronous Layout** per frame, menurunkan performa dari 60/120 FPS ke sub-15 FPS (*jank*).
2. Single Page Applications (SPA) yang berjalan seharian di workstation (misal: sistem monitoring perbankan, POS kasir, CRM) mengalami akumulasi *Detached DOM Nodes*, mengakibatkan tab browser crash akibat Out-Of-Memory (OOM).
3. Strategi loading asset yang buruk memicu render-blocking waterfall berkepanjangan, merusak skor *First Contentful Paint* (FCP) dan *Interaction to Next Paint* (INP).

### Apa itu Architecture-First Frontend Foundation?
Fondasi arsitektur frontend mencakup desain modular dari:
* **Asset Loading Orchestration**: Pengaturan prioritas bandwidth browser untuk meminimalisir waktu tunggu critical path.
* **Batch Mutation Pipelines**: Pemisahan tegas fase kalkulasi kalkulatif (Read) dan fase mutasi visual (Write).
* **Defensive Defensive Programming terhadap Browser Memory**: Sanitasi event listeners, pemutusan siklus referensi, dan destruksi manual struktur data kompleks saat unmounting komponen.

---

## 5. How (Workflow Detail)

### 5.1 Siklus Hidup Eksekusi Frame (The 16.6ms / 8.3ms Lifecycle)

Untuk mempertahankan 60Hz (16.6ms per frame) atau 120Hz (8.3ms per frame), browser mengeksekusi pipeline teratur di setiap frame tick:

```
[vsync signal]
      |
      v
+------------------+
| 1. Input Events  | -> Touch, Wheel, Pointer, Key events di-dispatch
+------------------+
      |
      v
+------------------+
| 2. Timers/Micro  | -> Macrotasks (expired timers), Microtask queue drainage
+------------------+
      |
      v
+------------------+
| 3. rAF Callbacks | -> requestAnimationFrame callbacks dieksekusi (Kalkulasi animasi)
+------------------+
      |
      v
+------------------+
| 4. Style Recalc  | -> Menghitung ulang CSS rules yang cocok dengan DOM
+------------------+
      |
      v
+------------------+
| 5. Layout        | -> Geometry calculation (width, height, top, left)
+------------------+
      |
      v
+------------------+
| 6. Paint         | -> Menghasilkan display list per layer
+------------------+
      |
      v
+------------------+
| 7. Commit & Comp | -> Layer diserahkan ke Compositor -> Raster -> GPU display
+------------------+
      |
      v
+------------------+
| 8. Idle Period   | -> requestIdleCallback dieksekusi jika budget waktu tersisa
+------------------+
```

### 5.2 Menghindari Forced Synchronous Layout & Layout Thrashing

**Normal Flow:**
JavaScript membaca layout -> JavaScript menulis mutasi DOM -> Frame selesai -> Browser menjalankan Style Recalc & Layout secara kolektif (Batched) satu kali.

**Thrashing Flow:**
```
JS: Write DOM (elementA.classList.add('wide'))
JS: Read Layout (elementA.offsetWidth) -> BROWSER DIPAKSA LAYOUT DETIK ITU JUGA!
JS: Write DOM (elementB.classList.add('wide'))
JS: Read Layout (elementB.offsetWidth) -> BROWSER DIPAKSA LAYOUT LAGI!
```

**Solusi Arsitektural (Read/Write Separation):**
1. Eksekusi semua pembacaan nilai geometris (*read phase*).
2. Simpan nilai ke variabel JavaScript murni.
3. Eksekusi semua modifikasi DOM (*write phase*) dalam antrean `requestAnimationFrame`.

---

## 6. Analogy & Diagram ASCII

### Analogi: Konveksi Pakaian Massal vs Pesanan Custom Interupsi
Bayangkan seorang mandor konveksi (Main Thread):
* **Normal Batching**: Mandor mengumpulkan 100 lembar kain pesanan (DOM nodes), mengukur semuanya sekaligus dengan pita ukur (Read Phase: Style/Layout), memotong kain semuanya sekaligus (Write Phase: Paint/Raster), lalu mengirimkannya ke bagian pengepakan (Compositor Thread).
* **Layout Thrashing**: Mandor memotong 1 kain -> langsung mengukur ulang panjang meja kerja karena takut berubah -> memotong 1 kain lagi -> mengukur ulang meja kerja lagi. Efisiensi pabrik langsung drop 99% hanya karena waktu habis dipakai mengukur ulang meja yang sama berulang kali.

### Diagram: Layout Thrashing vs Optimized Batching

```
BAD: LAYOUT THRASHING PIPELINE
Frame Start
  |
  +-- JS: el[0].height = '20px'
  |
  +-- JS: read el[0].offsetHeight  ===> [FORCED REFLOW 1] (CPU Stalls)
  |
  +-- JS: el[1].height = '40px'
  |
  +-- JS: read el[1].offsetHeight  ===> [FORCED REFLOW 2] (CPU Stalls)
  |
  +-- JS: el[2].height = '60px'
  |
  +-- JS: read el[2].offsetHeight  ===> [FORCED REFLOW 3] (CPU Stalls)
  |
Frame End (Frame Budget Terlampaui: Jank / Stutter Terdeteksi)

----------------------------------------------------------------------------

GOOD: SEPARATED READ/WRITE BATCHING
Frame Start
  |
  +-- JS Phase 1 (READ):
  |     const h0 = el[0].offsetHeight (Cache reading)
  |     const h1 = el[1].offsetHeight (No reflow: DOM is clean)
  |     const h2 = el[2].offsetHeight (No reflow: DOM is clean)
  |
  +-- JS Phase 2 (WRITE via rAF):
  |     el[0].style.transform = `scaleY(...)`
  |     el[1].style.transform = `scaleY(...)`
  |     el[2].style.transform = `scaleY(...)`
  |
  +-- Normal Style & Layout (Dieksekusi TEPAT 1 KALI oleh Browser Engine)
  |
Frame End (Frame Selesai dalam 4ms: Smooth 60/120 FPS)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Anti-Pattern Layout Thrashing vs Solusi Batch

```javascript
// ==========================================
// ANTI-PATTERN: Forced Synchronous Layout Thrashing
// ==========================================
function badResizeBoxes(boxes) {
  for (let i = 0; i < boxes.length; i++) {
    // READ: Memaksa browser menghitung layout secara sinkron pada loop ke-(n > 0)
    const currentWidth = boxes[i].offsetWidth; 
    
    // WRITE: Membatalkan cache layout yang baru saja dihitung
    boxes[i].style.width = `${currentWidth + 10}px`; 
  }
}

// ==========================================
// OPTIMIZED PATTERN: Decoupled Read/Write Phasing
// ==========================================
function optimizedResizeBoxes(boxes) {
  // Phase 1: Pure Reads (Browser menggunakan cache layout yang sudah ada)
  const widths = new Array(boxes.length);
  for (let i = 0; i < boxes.length; i++) {
    widths[i] = boxes[i].offsetWidth;
  }

  // Phase 2: Pure Writes (Dijadwalkan pada pipeline render berikutnya)
  requestAnimationFrame(() => {
    for (let i = 0; i < boxes.length; i++) {
      boxes[i].style.width = `${widths[i] + 10}px`;
    }
  });
}
```

### 7.2 Practical Example: Enterprise Reactive DOM Patching Engine & Resource Scheduling

Implementasi vanilla class arsitektural yang menangani virtual mutations, detached DOM mitigation, dan dynamic resource scheduling.

```javascript
/**
 * @file EnterpriseDomOrchestrator.js
 * @description Single-file reactive batching engine with memory-safe lifecycles.
 */

export class DomOrchestrator {
  #readQueue = new Set();
  #writeQueue = new Set();
  #isFlushScheduled = false;
  #activeNodeRegistry = new FinalizationRegistry((heldValue) => {
    console.warn(`[MemoryTracker] DOM Wrapper Garbage Collected for: ${heldValue}`);
  });

  /**
   * Schedule a non-blocking read operation
   * @param {Function} task
   */
  read(task) {
    this.#readQueue.add(task);
    this.#requestFlush();
  }

  /**
   * Schedule a non-blocking write operation
   * @param {Function} task
   */
  write(task) {
    this.#writeQueue.add(task);
    this.#requestFlush();
  }

  #requestFlush() {
    if (this.#isFlushScheduled) return;
    this.#isFlushScheduled = true;

    requestAnimationFrame((timestamp) => {
      this.#flushQueues(timestamp);
    });
  }

  #flushQueues(timestamp) {
    // Eksekusi seluruh READ tasks terlebih dahulu
    for (const readTask of this.#readQueue) {
      try {
        readTask(timestamp);
      } catch (err) {
        console.error('[DomOrchestrator] Read Task Error:', err);
      }
    }
    this.#readQueue.clear();

    // Eksekusi seluruh WRITE tasks setelah seluruh pembacaan selesai
    for (const writeTask of this.#writeQueue) {
      try {
        writeTask(timestamp);
      } catch (err) {
        console.error('[DomOrchestrator] Write Task Error:', err);
      }
    }
    this.#writeQueue.clear();

    this.#isFlushScheduled = false;
  }

  /**
   * Factory method untuk membuat managed element yang bebas detached DOM leaks.
   * @param {string} tagName 
   * @param {HTMLElement} parentNode 
   * @returns {{ element: HTMLElement, destroy: () => void }}
   */
  createManagedElement(tagName, parentNode) {
    let element = document.createElement(tagName);
    const elementId = `elem_${crypto.randomUUID()}`;
    element.dataset.managedId = elementId;

    parentNode.appendChild(element);

    // Track life cycle via WeakRef & FinalizationRegistry
    this.#activeNodeRegistry.register(element, elementId);

    const abortController = new AbortController();

    const destroy = () => {
      // 1. Cabut semua event listeners via signal
      abortController.abort();

      // 2. Cabut elemen dari tree native C++ DOM
      if (element && element.parentNode) {
        element.parentNode.removeChild(element);
      }

      // 3. Putus referensi JavaScript internal agar lolos Scavenge/Mark-Sweep
      element = null;
    };

    return {
      element,
      signal: abortController.signal,
      destroy
    };
  }
}

/**
 * Enterprise Network Scheduler
 * Mengatur injeksi dynamic preload dan prefetch sesuai network speed & device memory
 */
export class NetworkScheduler {
  static initAdaptiveHints(resourceMap) {
    // Navigator Network Information API
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const isSaveData = connection ? connection.saveData : false;
    const effectiveType = connection ? connection.effectiveType : '4g';

    // Jika pengguna berada pada koneksi lambat atau mode hemat data, jangan agresif preload
    if (isSaveData || effectiveType === '2g' || effectiveType === 'slow-2g') {
      console.warn('[NetworkScheduler] Slow network detected. Aggressive preloading disabled.');
      return;
    }

    resourceMap.forEach(({ url, as, priority }) => {
      const link = document.createElement('link');
      link.rel = 'preload';
      link.href = url;
      link.as = as;
      if (priority) {
        link.setAttribute('fetchpriority', priority);
      }
      link.crossOrigin = 'anonymous';
      document.head.appendChild(link);
    });
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time High-Frequency Trading Terminal Dashboard
* **Skala**: Dashboard internal bank memantau 5.000 ticker valas & saham secara serentak via WebSocket payload (50 messages/detik).
* **Masalah**:
  1. Halaman web mengalami progressive slowdown: CPU Main Thread usage mencapai 100%, render frame anjlok dari 60 FPS ke 8 FPS setelah 20 menit beroperasi.
  2. Memory Heap V8 naik dari 45MB hingga menembus 1.8GB, menyebabkan crash `Aw, Snap!` (OOM).
* **Root Cause Analysis (RCA)**:
  * *Penyebab 1 (Layout Thrashing)*: Setiap pesan WebSocket masuk, handler memanggil DOM manipulation: `row.style.height = ...`, lalu segera memanggil `table.scrollTop` untuk auto-scroll. 50 pesan per detik memicu 50 kali Forced Synchronous Layout berturut-turut.
  * *Penyebab 2 (Detached DOM Leak)*: Saat ticker lama dihapus dari tabel, array referensi JavaScript global menyimpan pointer ke `HTMLTableRowElement` untuk keperluan audit history. Blink tidak dapat membebaskan memori table rows karena masih dirujuk JS.
* **Solusi & Implementasi**:
  1. **Isolasi Buffer Menggunakan Double Buffering Virtual DOM**: Data WebSocket tidak langsung menulis ke DOM, melainkan ditampung ke TypedArray buffer murni di JavaScript. Mutasi DOM di-throttle tepat di callback `requestAnimationFrame` dengan batch fragment.
  2. **WeakMap / WeakRef Cache**: Array audit history diubah menggunakan `WeakRef` dan `WeakMap`. Jika DOM node dihapus dari native DOM tree, GC V8 langsung membebaskan instance wrapper tanpa hambatan.
  3. **CSS Layering**: Row visual updates diubah dari mutasi geometri (`height`, `top`) menjadi Composite-Only properties (`transform: translate3d()`), memotong siklus Layout & Paint dan langsung menyerahkan render data ke Compositor Thread.
* **Hasil**:
  * Penggunaan CPU Main Thread turun dari 100% menjadi 14%.
  * Frame rate terkunci stabil di 60 FPS terus-menerus.
  * Heap memory stabil di kisaran 65MB konstan selama 24 jam tanpa memory degradation.

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya / Kerugian | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **CSS Transforms (`transform`, `opacity`) vs Geometric Properties (`width`, `margin`)** | Menghindari Layout dan Paint; dieksekusi murni di GPU via Compositor Thread. 60-120 FPS konsisten. | Konsumsi VRAM GPU meningkat karena browser harus mengalokasikan dedicated backing store layer. Terlalu banyak layer memicu *Layer Explosion*. | Wajib untuk animasi, drag-and-drop, modal dialog transitions, dan chart cursors. |
| **Batch Mutation Engine vs Direct DOM Mutation** | Mengeliminasi forced synchronous reflow, menyatukan rendering lifecycle secara terpusat. | Abstraksi tambahan, ada latency mikro (penundaan eksekusi hingga RAF berikutnya). | Aplikasi data-intensive: analitik, spreadsheet web, data grids. |
| **Aggressive Dynamic Preloading (`<link rel="preload">`)** | Mengurangi First Meaningful Paint dan LCP secara drastis dengan memulai download lebih awal di CRP. | Memonopoli bandwidth network; berpotensi membuang kuota pengguna jika aset tidak terpakai; mendegradasi performa pada low-tier connection. | Hanya gunakan untuk critical font files dan hero images (maksimal 2-3 aset utama per halaman). |
| **WeakRef / FinalizationRegistry GC tracking** | Mencegah kebocoran memori akibat circular references secara transparan. | Garbage collection scheduling bersifat non-deterministik; V8 engine API overhead; tidak boleh dipakai untuk flow control kritikal. | Digunakan untuk runtime telemetry, caching libraries, dan visual components memory clean-up harnesses. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Forced Reflow Lewat Layout Properties Read
* **Gejala**: Performance profile menunjukkan baris merah tebal panjang bertuliskan *Forced Reflow* di dalam timeline task.
* **Bad Code**:
  ```javascript
  const box = document.getElementById('box');
  box.style.margin = '10px';
  // Mengakses offsetTop memaksa layout kalkulasi instan!
  console.log(box.offsetTop);
  ```
* **Perbaikan**: Lakukan kalkulasi layout *sebelum* memanipulasi style, atau manfaatkan `IntersectionObserver` / `ResizeObserver` yang berjalan asinkron di luar critical path layout engine.

### 2. Event Listener Ghosting & Closures Retaining Outer Scope
* **Gejala**: Heap snapshot menunjukkan ribuan closure scopes dan instance class yang tidak ter-garbage-collect meskipun parent component sudah dimusnahkan.
* **Bad Code**:
  ```javascript
  class GridComponent {
    constructor() {
      this.hugeData = new Array(1000000).fill("payload");
      this.handler = () => { console.log(this.hugeData.length); };
      window.addEventListener('resize', this.handler);
    }
    destroy() {
      // Salah: Elemen dihapus dari halaman tapi listener window masih menahan "this.handler"
      // yang membawa referensi "this.hugeData".
      document.getElementById('grid').remove();
    }
  }
  ```
* **Perbaikan**: Selalu bersihkan event listener secara deterministik menggunakan `AbortController`:
  ```javascript
  class GridComponent {
    #abortController = new AbortController();
    constructor() {
      this.hugeData = new Array(1000000).fill("payload");
      window.addEventListener('resize', () => {
        console.log(this.hugeData.length);
      }, { signal: this.#abortController.signal });
    }
    destroy() {
      this.#abortController.abort(); // Membersihkan semua listener secara instan
      document.getElementById('grid').remove();
    }
  }
  ```

### 3. Subresource Integrity (SRI) Mismatch Failures
* **Gejala**: Resource script eksternal gagal dimuat dengan status blocked di console: `Failed to find a valid digest in the 'integrity' attribute for resource...`
* **Solusi**: SRI memerlukan hashing kriptografis yang akurat (SHA-384 atau SHA-512) dan response dari CDN wajib menyertakan header `Access-Control-Allow-Origin: *`.

---

## 11. Best Practices (Production Checklist)

### Performa & CRP
- [ ] CSS ditaruh di `<head>` untuk menghindari Flash of Unstyled Content (FOUC).
- [ ] Script non-kritis menggunakan atribut `defer` atau `type="module"` untuk membebaskan Main Thread selama parsing HTML.
- [ ] Tidak ada akses ke layout-triggering properties (`offsetWidth`, `clientHeight`, `getComputedStyle()`) tepat setelah memanipulasi class/inline-style.
- [ ] Animasi terbatas hanya menggunakan properti `transform` dan `opacity`.
- [ ] Menggunakan `will-change` secara hemat dan menghapusnya setelah animasi selesai untuk mencegah memory layer bloating.

### Memori & Lifecycle
- [ ] Komponen mengimplementasikan metode `destroy()` / `unmount()` yang terstandarisasi.
- [ ] Global listeners (`window`, `document`) diikat menggunakan `AbortSignal`.
- [ ] Data berulang dan instansiasi chart divalidasi tidak meninggalkan Detached DOM Nodes melalui heap dump verification.

### Keamanan (Security Baseline)
- [ ] Mengaktifkan Content Security Policy (CSP) level 3 via HTTP Header tanpa `'unsafe-inline'`.
- [ ] Seluruh static vendor scripts di-load menggunakan Subresource Integrity hash (`integrity="sha384-..."`).
- [ ] External hyperlinks menyertakan atribut `rel="noopener noreferrer"`.

---

## 12. Hands-on Practice

Buat dan navigasikan ke direktori kerja:
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
```

### Struktur Project
```
hands-on/m02/
├── index.html
├── src/
│   ├── main.js
│   ├── PerformanceMonitor.js
│   └── VirtualBatchRenderer.js
└── styles/
    └── main.css
```

### File: `hands-on/m02/styles/main.css`
```css
:root {
  --bg-primary: #0f172a;
  --surface-primary: #1e293b;
  --text-primary: #f8fafc;
  --accent: #38bdf8;
  --danger: #ef4444;
  --success: #22c55e;
}

body {
  margin: 0;
  padding: 24px;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.controls {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

button {
  padding: 10px 16px;
  background-color: var(--accent);
  color: var(--bg-primary);
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
}

button:hover {
  opacity: 0.9;
}

.metrics-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  background-color: var(--surface-primary);
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #334155;
}

.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--accent);
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 8px;
  max-height: 500px;
  overflow-y: auto;
  padding: 12px;
  background-color: var(--surface-primary);
  border-radius: 8px;
}

.data-node {
  height: 40px;
  background-color: #334155;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  transition: transform 0.1s ease-out;
  contain: layout style paint;
}
```

### File: `hands-on/m02/src/PerformanceMonitor.js`
```javascript
export class PerformanceMonitor {
  #fpsElement = document.getElementById('metric-fps');
  #domCountElement = document.getElementById('metric-dom');
  #heapElement = document.getElementById('metric-heap');
  
  #frames = 0;
  #lastTime = performance.now();

  start() {
    const loop = (currentTime) => {
      this.#frames++;
      
      if (currentTime >= this.#lastTime + 1000) {
        const fps = Math.round((this.#frames * 1000) / (currentTime - this.#lastTime));
        this.#fpsElement.textContent = `${fps} FPS`;
        this.#frames = 0;
        this.#lastTime = currentTime;

        this.#domCountElement.textContent = document.getElementsByTagName('*').length;

        if (performance.memory) {
          const heapUsedMB = (performance.memory.usedJSHeapSize / (1024 * 1024)).toFixed(2);
          this.#heapElement.textContent = `${heapUsedMB} MB`;
        } else {
          this.#heapElement.textContent = 'N/A (Use Chrome)';
        }
      }

      requestAnimationFrame(loop);
    };

    requestAnimationFrame(loop);
  }
}
```

### File: `hands-on/m02/src/VirtualBatchRenderer.js`
```javascript
export class VirtualBatchRenderer {
  #container = document.getElementById('render-grid');
  #nodes = [];
  #abortController = new AbortController();

  init(count = 2000) {
    this.cleanup();
    this.#abortController = new AbortController();

    const fragment = document.createDocumentFragment();
    this.#nodes = new Array(count);

    for (let i = 0; i < count; i++) {
      const div = document.createElement('div');
      div.className = 'data-node';
      div.textContent = `${i + 1}`;
      fragment.appendChild(div);
      this.#nodes[i] = div;
    }

    this.#container.appendChild(fragment);
  }

  // EKSEKUSI TIDAK EFISIEN: Layout Thrashing disengaja untuk profiling
  triggerThrash() {
    const start = performance.now();
    for (let i = 0; i < this.#nodes.length; i++) {
      // WRITE
      this.#nodes[i].style.width = `${(Math.sin(Date.now() + i) * 20 + 60)}px`;
      // READ seketika itu juga -> Memaksa engine melakukan Reflow
      const offset = this.#nodes[i].offsetWidth;
      if (offset > 70) {
        this.#nodes[i].style.backgroundColor = '#ef4444';
      } else {
        this.#nodes[i].style.backgroundColor = '#334155';
      }
    }
    console.log(`[Thrashing Run] Executed in: ${(performance.now() - start).toFixed(2)}ms`);
  }

  // EKSEKUSI EFISIEN: Read-Write separation + Transform composites
  triggerOptimized() {
    const start = performance.now();
    const length = this.#nodes.length;
    const computedScales = new Float32Array(length);

    // Read/Computation Phase (Zero DOM Reads yang memicu reflow)
    const timestamp = Date.now();
    for (let i = 0; i < length; i++) {
      computedScales[i] = (Math.sin(timestamp + i) * 0.2 + 1.0);
    }

    // Write Phase: Dibungkus ke dalam Animation Frame Pipeline
    requestAnimationFrame(() => {
      for (let i = 0; i < length; i++) {
        const scale = computedScales[i];
        this.#nodes[i].style.transform = `scale(${scale})`;
        this.#nodes[i].style.backgroundColor = scale > 1.1 ? '#22c55e' : '#334155';
      }
      console.log(`[Optimized Run] Executed in: ${(performance.now() - start).toFixed(2)}ms`);
    });
  }

  cleanup() {
    this.#abortController.abort();
    while (this.#container.firstChild) {
      this.#container.removeChild(this.#container.firstChild);
    }
    this.#nodes = [];
  }
}
```

### File: `hands-on/m02/src/main.js`
```javascript
import { PerformanceMonitor } from './PerformanceMonitor.js';
import { VirtualBatchRenderer } from './VirtualBatchRenderer.js';

document.addEventListener('DOMContentLoaded', () => {
  const monitor = new PerformanceMonitor();
  monitor.start();

  const renderer = new VirtualBatchRenderer();
  renderer.init(3000);

  document.getElementById('btn-init').addEventListener('click', () => {
    renderer.init(3000);
  });

  document.getElementById('btn-thrash').addEventListener('click', () => {
    renderer.triggerThrash();
  });

  document.getElementById('btn-optimized').addEventListener('click', () => {
    renderer.triggerOptimized();
  });

  document.getElementById('btn-cleanup').addEventListener('click', () => {
    renderer.cleanup();
  });
});
```

### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline';">
  <title>Browser Internals & Rendering Lab</title>
  <link rel="stylesheet" href="./styles/main.css">
</head>
<body>
  <h1>Enterprise Rendering Optimization Lab</h1>
  
  <div class="metrics-panel">
    <div class="metric-card">
      <div>Render Performance</div>
      <div id="metric-fps" class="metric-value">0 FPS</div>
    </div>
    <div class="metric-card">
      <div>DOM Tree Size</div>
      <div id="metric-dom" class="metric-value">0</div>
    </div>
    <div class="metric-card">
      <div>Heap Memory</div>
      <div id="metric-heap" class="metric-value">0 MB</div>
    </div>
  </div>

  <div class="controls">
    <button id="btn-init">Populate 3,000 Nodes</button>
    <button id="btn-thrash" style="background-color: var(--danger); color: white;">Execute Layout Thrashing</button>
    <button id="btn-optimized" style="background-color: var(--success); color: white;">Execute Compositor Batch</button>
    <button id="btn-cleanup">Unmount & Clean Memory</button>
  </div>

  <div id="render-grid" class="grid-container"></div>

  <script type="module" src="./src/main.js"></script>
</body>
</html>
```

### Instruksi Pengujian di Browser
1. Jalankan static server lokal:
   ```bash
   npx serve .
   ```
2. Buka Chrome DevTools -> tab **Performance**.
3. Klik tombol *Populate 3,000 Nodes*.
4. Klik *Record* pada Performance Profiler, lalu klik *Execute Layout Thrashing*. Stop recording. Amati drop frame rate dan peringatan ungu bertuliskan **Recalculate Style & Forced Reflow**.
5. Klik *Record* kembali, lalu klik *Execute Compositor Batch*. Stop recording. Perhatikan hilangnya layout waterfall dan frame rate bertahan di 60 FPS.

---

## 13. Exercise

### Exercise 1 (Easy): Priority Hints Tuning
* **Tantangan**: Diberikan sebuah HTML dengan 3 gambar dan 1 script bundle analytic. Gambar pertama adalah Largest Contentful Paint (LCP) Hero Banner, sedangkan 2 gambar lainnya berada di bawah viewport (below the fold).
* **Tugas**: Tambahkan atribut HTML native (`loading`, `fetchpriority`, `decoding`) untuk memastikan resource pipeline memprioritaskan hero banner tanpa blocking rendering parser browser.
* **Kriteria Keberhasilan**: Browser mendownload Hero image dengan priority `High`, lazy load pada 2 image berikutnya, dan script analitik tidak memblokir parsing DOM.

### Exercise 2 (Medium): Layout Thrashing Refactoring
* **Tantangan**: Kode warisan berikut membaca posisi elemen dan memindahkannya ke kanan secara bertahap:
  ```javascript
  function moveElements(selector) {
    const elements = document.querySelectorAll(selector);
    for (let el of elements) {
      const left = el.getBoundingClientRect().left;
      el.style.left = `${left + 5}px`;
    }
  }
  ```
* **Tugas**: Refactor fungsi tersebut tanpa mengubah fungsionalitas visual, tetapi pisahkan execution phase menjadi Read-Phase dan Write-Phase menggunakan CSS transform `translate()`.
* **Kriteria Keberhasilan**: Performance profiler menunjukkan 0 kali pemanggilan *Layout* sinkron berulang selama perulangan berjalan.

### Exercise 3 (Hard): Detached DOM & Leak Hunter
* **Tantangan**: Buat skrip stress-test yang memuat modal dialog dinamis ke dalam halaman, menambahkan 10.000 row tabel, lalu menutup dan menghapus modal tersebut. 
* **Tugas**: Cegah terjadinya memory leak dengan menjamin tidak ada Detached Elements yang tertinggal di V8 memory heap snapshot setelah modal ditutup.
* **Kriteria Keberhasilan**: Bandingkan dua Heap Snapshots (sebelum modal dibuka vs setelah modal ditutup dan di-garbage collect via Chrome DevTools icon trash). Filter `Detached` pada Class Filter harus bernilai **0 instances**.

---

## 14. Challenge

### Arsitektur Live Telemetry Virtualizer (Zero-Lag Dashboard)
Rancang arsitektur komponen tabel streaming data virtual yang mampu menampilkan hingga **100.000 records log transaksi**, dengan requirement teknis enterprise:
1. **DOM Node Ceiling**: Jumlah DOM Node di halaman tidak boleh melebihi 100 elemen pada kondisi scroll posisi mana pun (implementasikan dynamic sliding window virtualization murni tanpa third-party library).
2. **Main Thread Budget**: Waktu pemrosesan recalculate data dan shifting viewport tidak boleh melebihi budget frame **8ms** per render cycle (INP < 50ms).
3. **Memory Safety**: Ketika data feed di-reset, seluruh referensi internal harus dibersihkan, tanpa meninggalkan residual heap allocation di V8 garbage collector.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Mengapa file stylesheet (`<link rel="stylesheet">`) dikategorikan sebagai *render-blocking*?**
   * A. Karena file CSS berukuran lebih besar daripada HTML.
   * B. Karena browser harus mengunduh dan membangun CSSOM secara utuh sebelum dapat membuat Render Tree visual dengan benar.
   * C. Karena CSS dieksekusi di dalam dedicated GPU process.
   * D. Karena file CSS memblokir proses rendering di Compositor Thread saja.
   * *Jawaban yang benar*: B. CSS bersifat render-blocking karena jika halaman ditampilkan sebelum seluruh CSS selesai di-parse, browser akan menampilkan FOUC (Flash of Unstyled Content) atau terpaksa menghitung ulang tata letak setiap kali aturan baru ditemukan.

2. **Perbedaan mendasar antara properti CSS `display: none` dan `visibility: hidden` pada Render Tree adalah...**
   * A. Keduanya sama-sama masuk ke Render Tree.
   * B. `display: none` tetap masuk Render Tree, sedangkan `visibility: hidden` dihapus.
   * C. `display: none` dikeluarkan sepenuhnya dari Render Tree, sedangkan `visibility: hidden` tetap masuk ke Render Tree dan memakan ruang geometris pada Layout.
   * D. `display: none` hanya diproses oleh Compositor Thread.
   * *Jawaban yang benar*: C. `display: none` tidak dialokasikan di Render Tree maupun Layout phase, sedangkan `visibility: hidden` tetap memerlukan kalkulasi geometris dimensi dan posisi di Layout phase.

3. **Di thread manakah parsing JavaScript dan perhitungan Layout secara default berlangsung pada browser berbasis Chromium?**
   * A. GPU Thread
   * B. Main Thread
   * C. Compositor Thread
   * D. Network Worker Thread
   * *Jawaban yang benar*: B. Pada arsitektur Renderer Process Chromium, eksekusi JavaScript (V8), parsing DOM, Style Calculation, dan Layout dieksekusi pada Main Thread.

4. **Kapan callback yang didaftarkan ke `requestAnimationFrame()` dieksekusi oleh browser?**
   * A. Langsung setelah microtask queue kosong, tanpa menunggu rendering.
   * B. Tepat sebelum browser menjalankan tahapan Style Recalculation dan Layout pada frame rendering berikutnya.
   * C. Setelah Compositor selesai mengirim draw quad ke GPU.
   * D. Secara acak bergantung pada ketersediaan idle memory CPU.
   * *Jawaban yang benar*: B. `requestAnimationFrame` dieksekusi tepat sebelum browser menjalankan pipeline kalkulasi visual (Style Recalculation -> Layout -> Paint) pada frame yang bersangkutan.

5. **Apa fungsi utama dari atribut `defer` pada tag `<script>`?**
   * A. Menghentikan parsing HTML sampai script selesai di-download dan dieksekusi.
   * B. Menjalankan script di background Web Worker thread.
   * C. Memungkinkan script di-download secara asynchronous paralel dengan parsing HTML, dan dieksekusi hanya setelah seluruh dokumen HTML selesai di-parse.
   * D. Menghindari validasi Content Security Policy.
   * *Jawaban yang benar*: C. Atribut `defer` mendownload script secara background tanpa memblokir tokenizer HTML dan menjamin eksekusi script sesuai urutan deklarasi tepat setelah parsing HTML selesai.

### Bagian 2: Intermediate (5 Soal)
6. **Perhatikan urutan kode berikut:**
   ```javascript
   element.style.width = '100px';
   console.log(element.offsetWidth);
   element.style.height = '200px';
   console.log(element.offsetHeight);
   ```
   **Dampak internal apa yang terjadi pada Rendering Engine?**
   * A. Browser melakukan 1 kali Layout di akhir eksekusi task.
   * B. Terjadi Forced Synchronous Layout sebanyak 2 kali secara berturut-turut karena pembacaan layout property menyela penulisan inline style.
   * C. Eksekusi dialihkan secara instan ke Compositor Thread.
   * D. Browser melempar error unhandled rejection.
   * *Jawaban yang benar*: B. Mengakses `offsetWidth` setelah mengubah `style.width` memaksa browser engine menghentikan script dan menjalankan Layout sinkron untuk mendapatkan nilai terkini. Hal ini diulang kembali pada baris berikutnya, menghasilkan Layout Thrashing.

7. **Pada engine V8, memori yang dialokasikan untuk objek baru yang memiliki siklus hidup sangat singkat dikelola oleh...**
   * A. Major GC menggunakan Mark-Sweep-Compact.
   * B. Scavenger Collector pada New Space.
   * C. Dedicated GPU Unified Buffer.
   * D. Large Object Space.
   * *Jawaban yang benar*: B. V8 mengalokasikan objek baru pada New Space (Nursery) yang dibersihkan secara berkala dan sangat cepat menggunakan algoritma Scavenger.

8. **Mengapa animasi properti CSS `transform: translate()` jauh lebih efisien dibandingkan memanipulasi properti `top` / `left`?**
   * A. Karena `transform` tidak membutuhkan memori VRAM.
   * B. Karena `transform` dieksekusi langsung oleh Compositor Thread dan GPU tanpa memicu Layout dan Paint ulang di Main Thread.
   * C. Karena `top` dan `left` adalah fitur legacy yang sudah di-deprecated.
   * D. Karena `transform` berjalan di microtask queue.
   * *Jawaban yang benar*: B. Perubahan `transform` dan `opacity` merupakan Composite-Only properties; browser cukup memanipulasi GPU layer matrix yang sudah ada tanpa melibatkan Main Thread untuk menghitung ulang koordinat geometris elemen lain.

9. **Apa yang dimaksud dengan fenomena "Detached DOM Node"?**
   * A. Elemen DOM yang tidak memiliki class CSS.
   * B. Node C++ pada Blink core yang telah dicopot dari struktur active tree document, tetapi memori native-nya tidak dapat dibebaskan karena masih ada pointer referensi yang aktif di JavaScript.
   * C. Elemen HTML yang dipindahkan ke dalam iframe lain.
   * D. Tag HTML kustom yang belum terdaftar di CustomElementsRegistry.
   * *Jawaban yang benar*: B. Detached DOM terjadi ketika sebuah elemen sudah di-detach dari viewport/document tree, tetapi masih dirujuk oleh JavaScript (misal variabel atau array), menyebabkan pemborosan memori (leak) di level Blink dan V8.

10. **Bagaimana mekanisme header `Content-Security-Policy` dengan direktif `script-src 'nonce-r4nd0m'` melindungi aplikasi web?**
    * A. Melarang browser mengunduh script yang ukurannya lebih dari 1MB.
    * B. Mengizinkan eksekusi tag `<script>` inline hanya jika nilai atribut `nonce` pada tag tersebut identik secara kriptografis dengan token unik yang dikirimkan server pada HTTP header request tersebut.
    * C. Mengompresi script menggunakan enkripsi AES-256.
    * D. Memaksa script dimuat melalui service worker terdaftar.
    * *Jawaban yang benar*: B. CSP Nonce memitigasi serangan Cross-Site Scripting (XSS) dengan memastikan bahwa script injeksi asing tidak akan dieksekusi oleh browser karena script tersebut tidak memiliki token rahasia acak yang cocok dengan HTTP header sesi terkait.

### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1**: Tim Anda merilis fitur live chart monitoring ke production. Setelah 4 jam aplikasi berjalan di layar monitor operasi klien, tab browser crash. Analisis Memory Dump menunjukkan alokasi heap stabil di 80MB, namun total proses sistem browser memakan RAM hingga 3.5GB. Analisis mana yang paling tepat mengenai akar permasalahan ini?
    * A. Terjadi V8 Memory Leak pada struktur JSON string.
    * B. Terjadi Detached DOM Nodes atau GPU Backing Store Layer Leak di level native C++ (Blink/GraphicsLayer) yang tidak tercermin penuh di V8 JS Heap melainkan di Native Memory renderer process.
    * C. Network request mengalami TCP packet drop berkepanjangan.
    * D. V8 engine gagal menjalankan kompilasi JIT TurboFan.
    * *Jawaban yang benar*: B. JS Heap hanya memonitor objek managed JavaScript. Jika grafik terus-menerus memproduksi layer grafis baru (`will-change: transform` berlebih) atau detached DOM elements tanpa di-destroy secara native, alokasi memori C++ native pada Blink dan GPU process akan meluap hingga memicu OS membunuh browser process karena OOM.

12. **Skenario Kasus 2**: Situs portal e-commerce Anda memiliki skor Google Core Web Vitals yang buruk pada metrik LCP (Largest Contentful Paint) yaitu 4.8 detik pada jaringan 4G. LCP didorong oleh gambar produk utama. Setelah diaudit, file gambar produk baru mulai terunduh di detik ke-3.1 setelah script `bundle.js` selesai dieksekusi. Solusi arsitektural mana yang paling tepat dan elegan?
    * A. Mengubah format gambar menjadi base64 dan menanamkannya langsung di dalam JavaScript bundle.
    * B. Menambahkan tag `<link rel="preload" as="image" href="..." fetchpriority="high">` langsung di bagian `<head>` HTML yang di-render dari server, sehingga browser network engine mengunduh gambar secara prioritasi paralel sebelum JavaScript bundle selesai di-parse.
    * C. Mengatur timeout pada rendering gambar menggunakan `setTimeout(..., 1000)`.
    * D. Memindahkan script bundle ke akhir tag `</body>` tanpa atribut `defer`.
    * *Jawaban yang benar*: B. Preload link dengan Priority Hint `fetchpriority="high"` menaikkan ranking antrean resource loader browser ke posisi paling atas di awal CRP parsing, mengunduh aset visual utama tanpa harus menunggu bundle JS dieksekusi.

13. **Skenario Kasus 3**: Sebuah aplikasi perbankan memuat modul pembayaran legacy via CDN eksternal. Security architect mewajibkan validasi integritas aset agar jika server CDN diretas, kode berbahaya tidak dapat dieksekusi di browser nasabah. Implementasi kombinasi atribut apa yang wajib dipasang pada elemen script?
    * A. `async="true"` dan `referrerpolicy="no-referrer"`
    * B. `crossorigin="anonymous"` dan `integrity="sha384-[hash-base64]"` (Subresource Integrity)
    * C. `rel="prefetch"` dan `sandbox="allow-scripts"`
    * D. `type="text/javascript"` dan `credentials="include"`
    * *Jawaban yang benar*: B. Subresource Integrity (SRI) menggunakan hash kriptografis (`integrity`) dan memerlukan `crossorigin="anonymous"` untuk mengizinkan browser membaca response body lintas domain tanpa membocorkan credential, memvalidasi bahwa byte file CDN tidak berubah sebelum dieksekusi.

---

## 16. Summary

```
                 ENTERPRISE BROWSER RUNTIME ARCHITECTURE
                 
 [ Network Layer ]  ==>  Resource Scheduling (Preload / FetchPriority / SRI)
                                |
                                v
 [ Main Thread ]    ==>  HTML/CSS Parse  ->  DOM / CSSOM Construction
                                |
                                v
                         Render Tree Assembly
                                |
                         Layout Calculation (Mitigate Forced Reflow Thrash)
                                |
                         Paint Display Lists Creation
                                |
                                v Commit Layer
 [ Compositor ]     ==>  Tiling & Layer Composite (transform, opacity)
                                |
                                v Rasterize
 [ GPU Process ]    ==>  Hardware Frame Buffer Output
```

1. **Rendering Performance Bukan Soal JavaScript Cepat Saja**: Menulis kode frontend enterprise menuntut kesadaran penuh terhadap batas fungsional antara Main Thread (CPU) dan Compositor/Raster Thread (GPU).
2. **Layout Thrashing Merusak Rendering Cycle**: Memisahkan fase **Read** (pengukuran) dan **Write** (modifikasi) adalah aturan mutlak saat memanipulasi DOM secara masif. Manfaatkan CSS Containment (`contain: layout style paint`) dan layer-only properties (`transform`, `opacity`) untuk mengisolasi cascade reflow.
3. **Siklus Hidup Memori Menembus Batas JS**: Pembersihan data tidak selesai hanya dengan menghapus variabel. DOM Nodes yang dicopot dari document tree wajib dibersihkan referensi wrapper-nya di JavaScript agar memori C++ native pada engine Blink dapat dibebaskan oleh Garbage Collector.
4. **Keamanan & Resiliensi Dimulai dari Fondasi Dokumen**: Integrasi ketat Content Security Policy (CSP) berbasis nonces dan Subresource Integrity (SRI) menjamin pipeline pengiriman kode enterprise ke end-user bebas dari serangan injeksi dependensi.

Di Modul 03, kita akan melangkah lebih jauh ke ranah **Deep CSS Engineering: Layout Engines, Cascade Layers, Modern Architecture & Design Systems at Scale**. Kita akan membedah mekanika formatting context tingkat lanjut (Grid, Flexbox, Multi-Column), CSS Custom Properties runtime scope, dan arsitektur styling untuk platform skala besar.