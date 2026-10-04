# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Bab:** 07 (Materi Lanjutan) | **Tingkat:** Enterprise Frontend Engineering

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Memetakan Critical Rendering Path (CRP):** Mengidentifikasi tahap parsing, kalkulasi style, layout/reflow, paint, dan compositing pada browser engine modern guna mengeliminasi bottleneck rendering.
2. **Menguasai Runtime Engine & Asynchronous Mechanics:** Mengatur urutan eksekusi JavaScript pada Call Stack, Web APIs, Microtask Queue, Macrotask Queue (Task Queue), dan Render Pipeline (`requestAnimationFrame`) dengan presisi waktu frame (16.67ms per frame / 60 FPS).
3. **Mendeteksi dan Memitigasi Memory Leaks:** Mengidentifikasi detached DOM nodes, retainers graph, uncleaned closures, dan heap fragmentation menggunakan Chrome DevTools Memory Profiler.
4. **Mendesain Arsitektur State Predictable Berkinerja Tinggi:** Mengimplementasikan state management berbasis Finite State Machine (FSM) dan reactive pub/sub tanpa external library yang aman terhadap race conditions.
5. **Mengonstruksi Production-Ready Core Web Vitals:** Mengoptimasi Largest Contentful Paint (LCP), Interaction to Next Paint (INP), dan Cumulative Layout Shift (CLS) pada skala aplikasi web multi-halaman maupun single-page architecture.

---

## 2. Prerequisite

Untuk mendapatkan hasil maksimal dari modul ini, Anda wajib menguasai:

* **ECMAScript Modern (ES6+):** Deep understanding terkait Closures, Lexical Scope, Prototypes, Symbols, Promises, TypedArrays, dan Generators.
* **Dasar DOM Manipulation & Event Bubbling:** Mekanisme event propagation (Capturing, Target, Bubbling) dan native DOM tree mutations.
* **HTTP & Network Fundamentals:** TCP/IP handshake, TLS negotiation, HTTP/2 & HTTP/3 multiplexing, Browser Cache Control headers.
* **Development Environment:** Node.js LTS terinstal, Chromium-based browser dengan DevTools (Performance, Memory, Network panel) terbiasa digunakan.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Browser Engine Architecture & The Critical Rendering Path

Browser modern (Chromium/Blink, Gecko, WebKit) tidak membaca kode frontend sebagai satu kesatuan statis, melainkan melalui pipeline multi-threaded:

```
[Network Stream: Bytes] 
        │
        ▼ (Tokenization & Decoding)
[Characters: HTML/CSS Strings]
        │
        ▼ (Parsing: Lexer & Tree Construction)
[Nodes: DOM Tree] + [CSSOM Tree]
        │
        ▼ (Style Calculation)
   [Render Tree]
        │
        ▼ (Layout / Reflow: Geometry & Positions)
  [Layout Tree / Box Model (x, y, w, h)]
        │
        ▼ (Paint: Display Lists & Recording)
[Layer Tree: Drawing Commands]
        │
        ▼ (Tiling & Rasterization: GPU Acceleration)
  [Composited Tiles (Pixels on Screen)]
```

1. **Parsing & Tree Construction:**
   * Parser mengubah raw HTML stream menjadi token (`StartTag`, `EndTag`, `Character`).
   * Token dikonversi menjadi node objek JavaScript. Ketika script synchronous (`<script>`) ditemukan, parsing HTML terblokir (*parser-blocking*) karena JavaScript berpotensi memodifikasi DOM melalui `document.write()` atau mutasi langsung.
   * `async` memecah dependensi blocking dengan mengunduh di thread terpisah dan mengeksekusi langsung saat selesai diunduh.
   * `defer` mengunduh secara parallel dan mengeksekusi secara sequential tepat setelah DOM selesai diparsing sebelum `DOMContentLoaded`.

2. **Style Resolution & The CSSOM:**
   * CSS bersifat *render-blocking*. Browser tidak dapat merender DOM parsial jika stylesheet belum selesai dievaluasi, untuk mencegah Flash of Unstyled Content (FOUC).
   * Selector matching dievaluasi dari **kanan ke kiri** (*Right-to-Left*). Selector kompleks seperti `div.main ul > li a.active` memiliki evaluasi komputasi lebih mahal dibandingkan atomic class selector seperti `.c-nav__link--active`.

3. **Layout / Reflow Engine:**
   * Menghitung geometri matematis (koordinat absolut, lebar, tinggi) tiap visible node.
   * Mengubah properti geometris (`width`, `height`, `margin`, `top`, `fontSize`, `display`) memicu **Reflow Global** atau **Reflow Lokal**, membebani CPU thread utama.

4. **Paint & Compositing:**
   * Paint mengonversi box model menjadi instruksi bitmap drawing (color, shadow, border-radius).
   * Compositing membagi dokumen ke dalam lapisan-lapisan (*RenderLayers* -> *GraphicsLayers*). Properti seperti `transform` dan `opacity` dialokasikan ke layer terpisah dan diproses langsung oleh GPU (Hardware Compositor thread), melewati fase Layout dan Paint secara utuh.

---

### 3.2 JavaScript Runtime & Event Loop Deep Dive

JavaScript bersifat *single-threaded non-blocking asynchronous concurrent language*. Paradigma ini diatur melalui interaksi antar beberapa komponen memory dan execution queues:

```
┌────────────────────────────────────────────────────────┐
│                      V8 RUNTIME                        │
│  ┌──────────────────────┐     ┌─────────────────────┐  │
│  │     MEMORY HEAP      │     │     CALL STACK      │  │
│  │ (Objects, Closures,  │     │ (Execution Contexts,│  │
│  │  Retained References)│     │  Stack Frames)      │  │
│  └──────────────────────┘     └──────────┬──────────┘  │
└──────────────────────────────────────────┼─────────────┘
                                           │
                                           ▼ (Pushes/Pops)
┌────────────────────────────────────────────────────────┐
│                   BROWSER EVENT LOOP                   │
│                                                        │
│  1. Execute ONE Macrotask from Queue                   │
│  2. Drain ENTIRE Microtask Queue until empty           │
│  3. Check Animation Frame Callbacks (rAF)              │
│  4. Run Intersection / Resize Observers                │
│  5. Render Steps (Style -> Layout -> Paint)            │
└───────────────────────┬────────────────────────────────┘
                        │
       ┌────────────────┴────────────────┐
       ▼                                 ▼
┌──────────────┐                 ┌──────────────┐
│  MACROTASK   │                 │  MICROTASK   │
│    QUEUE     │                 │    QUEUE     │
├──────────────┤                 ├──────────────┤
│ setTimeout   │                 │ Promise.then │
│ setInterval  │                 │ queueMicrotask│
│ setImmediate │                 │ MutationObs  │
│ I/O Events   │                 │              │
└──────────────┘                 └──────────────┘
```

* **Microtask Invariant:** Setiap kali satu Macrotask selesai atau Call Stack kosong, engine akan menguras (*drain to exhaustion*) seluruh antrean Microtask, termasuk Microtask baru yang didaftarkan saat Microtask lain sedang berjalan. Jika terjadi infinite recursive microtask (`function loop() { queueMicrotask(loop); }`), thread utama akan hang seketika tanpa sempat melakukan re-render layout.
* **Frame Budget (16.67ms / 60Hz):** Browser membutuhkan ~16.67 milidetik untuk menyelesaikan satu frame. Jika eksekusi JavaScript + Style + Layout + Paint melampaui angka ini, frame akan terlewati (*dropped frames / jank*).

---

### 3.3 Memory Management & V8 Garbage Collection Mechanics

* **Generational Hypothesis:** Mayoritas objek dalam memori memiliki siklus hidup yang sangat pendek (*infant mortality*).
* **V8 Heap Segmentation:**
  1. **New Space (Nursery + Intermediate):** Objek baru dialokasikan di sini. Dikoleksi sangat cepat oleh **Scavenger Algorithm** (berbasis Cheney's Copying Algorithm).
  2. **Old Pointer / Old Data Space:** Objek yang bertahan setelah 2 siklus Scavenging dipromosikan ke sini. Dikoleksi oleh **Major GC (Mark-Sweep-Compact)**.
* **GC Leaks Trigger:**
  * **Accidental Global Variables:** Variabel yang tidak sengaja tertempel pada `window`.
  * **Forgotten Timers / Callbacks:** `setInterval` mempertahankan referensi objek scope luar di dalam closure-nya.
  * **Detached DOM Elements:** Node DOM telah dihapus dari antarmuka pengguna via `removeChild()`, tetapi variabel JavaScript masih menyimpan referensinya. Hal ini menyebabkan seluruh sub-tree DOM tidak dapat di-*garbage collect*.

---

## 4. Why & What

| Dimensi | Pendekatan Naif / Pemula | Pendekatan Enterprise Architecture |
| :--- | :--- | :--- |
| **DOM Updates** | Mengubah DOM berkali-kali secara inkremental dalam loop synchronous. | Batching baca/tulis DOM melalui scheduler, menggunakan `DocumentFragment`, atau CSS-transform. |
| **State Handling** | Global variable tersebar, DOM diinspeksi untuk mengetahui kondisi state saat ini. | Deterministic Finite State Machine (FSM) terisolasi dengan state transitions yang terprediksi. |
| **Event Handling** | Memasang ribuan listener langsung ke node anak individual. | Event Delegation pada container root dengan routing berbasis dataset dan selector engine. |
| **Memory Cleanup**| Mengandalkan automatic garbage collection secara pasif tanpa tracking lifecycle. | Lifecycle disposal explicit (`abortController.abort()`, `WeakMap`, detaching observers, clear references). |
| **Rendering Performance** | Membiarkan browser melakukan kalkulasi CSS layout pada tiap event listener scroll/resize. | Mengisolasi layout recalculation melalui Passive Listeners, IntersectionObserver, Virtualization, dan Web Workers. |

---

## 5. How (Workflow Detail)

Alur kerja arsitektural rendering engine dan state-pipeline di tingkat produksi:

```
[User Action / Network Stream]
              │
              ▼
[State Mutation Engine (FSM / Store)]
              │ (Emits New State Immutably)
              ▼
[Scheduler / Task Coordinator]
  ├── Non-urgent tasks  ──> requestIdleCallback() / Microtask
  └── High-priority UI  ──> requestAnimationFrame()
              │
              ▼
[Read/Write Phase Isolation Engine]
  ├── Phase 1: BATCH READ  (Measure: offsetHeight, getBoundingClientRect)
  └── Phase 2: BATCH WRITE (Mutate: transform, classList.toggle)
              │
              ▼
[Targeted Node Painting] (GPU Compositor bypasses CPU Reflow)
              │
              ▼
[Frame Completion (Sub-16ms Budget)]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Konduktor Orkestra vs Pasar Tradisional

Bayangkan sebuah panggung konser musik simfoni (Rendering Engine).

* **Pasar Tradisional (Pendekatan Naif):** Setiap musisi (DOM Node) berteriak secara acak kapan pun mereka ingin (Layout Thrashing). Pemain biola menanyakan tempo ke pemain cello, lalu pemain trompet mengubah kunci nada seketika. Konduktor pusing, musik terputus-putus (*frame dropped/jank*).
* **Konduktor Orkestra (Arsitektur Enterprise):** Konduktor membagi waktu dalam ketukan terstruktur (*Event Loop & rAF*). 
  1. Fase Pembacaan Partitur: Semua musisi melihat not balok secara bersamaan tanpa memainkan alat musik (*Batch Read*).
  2. Fase Eksekusi Suara: Semua instrumen dibunyikan serempak mengikuti aba-aba tangan konduktor (*Batch Write*). Suara terpadu, sinkron, tanpa jeda.

### Diagram: Layout Thrashing vs Batched Execution

#### BAD (Layout Thrashing / Forced Synchronous Layout):
```
Time ───►
[ JS: Read (elem.offsetWidth) ] ────► Browser dipaksa hitung Layout seketika! (CPU Spikes)
[ JS: Write (elem.style.width) ] ───► Layout invalid
[ JS: Read (elem2.offsetWidth) ] ───► Browser hitung Layout ULANG! (Jank)
[ JS: Write (elem2.style.width) ]───► Layout invalid lagi
```

#### GOOD (Batched Read-Then-Write Architecture):
```
Time ───►
[ JS: Read All ]  ───► getBoundingClientRect() untuk elem1, elem2, elem3 (Single Cached Layout Read)
[ JS: Write All ] ───► style changes untuk elem1, elem2, elem3 (Scheduled single dirty pass)
[ Browser Engine] ───► SINGLE Style -> SINGLE Layout -> SINGLE Paint
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membedakan Urutan Eksekusi Event Loop

Mari verifikasi kepatuhan internal runtime terhadap microtask dan macrotask:

```javascript
console.log('[1] Synchronous Script Start');

// Macrotask
setTimeout(() => {
  console.log('[6] Macrotask (setTimeout 0ms)');
}, 0);

// Microtask
Promise.resolve().then(() => {
  console.log('[3] Microtask 1 (Promise)');
}).then(() => {
  console.log('[4] Microtask 2 (Chained Promise)');
});

// Explicit Microtask
queueMicrotask(() => {
  console.log('[5] Microtask 3 (queueMicrotask)');
});

// Render Task
requestAnimationFrame(() => {
  console.log('[7] Animation Frame Callback (Before Paint)');
});

console.log('[2] Synchronous Script End');

// OUTPUT ORDER:
// [1] Synchronous Script Start
// [2] Synchronous Script End
// [3] Microtask 1 (Promise)
// [4] Microtask 2 (Chained Promise)
// [5] Microtask 3 (queueMicrotask)
// [7] Animation Frame Callback (Before Paint) -> (bisa sebelum/sesudah macrotask tergantung frame tick)
// [6] Macrotask (setTimeout 0ms)
```

---

### 7.2 Practical Example: Enterprise-Grade Fast DOM Batcher & Detached Leak Prevention

Implementasi modul manajemen DOM bebas layout-thrashing dengan lifecycle awareness:

```javascript
/**
 * Core Batch Engine untuk mencegah Layout Thrashing
 * Menerapkan Two-Phase Commit: READ phase -> WRITE phase
 */
class DOMBatchScheduler {
  #reads = new Set();
  #writes = new Set();
  #scheduled = false;

  read(fn) {
    this.#reads.add(fn);
    this.#requestFlush();
  }

  write(fn) {
    this.#writes.add(fn);
    this.#requestFlush();
  }

  #requestFlush() {
    if (this.#scheduled) return;
    this.#scheduled = true;

    requestAnimationFrame(() => {
      this.#flush();
    });
  }

  #flush() {
    const start = performance.now();

    // 1. Eksekusi semua pembacaan DOM (Kalkulasi geometri)
    for (const read of this.#reads) {
      try {
        read();
      } catch (err) {
        console.error('DOM Batcher Read Error:', err);
      }
    }
    this.#reads.clear();

    // 2. Eksekusi semua penulisan DOM (Mutasi visual)
    for (const write of this.#writes) {
      try {
        write();
      } catch (err) {
        console.error('DOM Batcher Write Error:', err);
      }
    }
    this.#writes.clear();

    this.#scheduled = false;
    const duration = performance.now() - start;
    if (duration > 16.67) {
      console.warn(`[Frame Budget Exceeded] Batch took ${duration.toFixed(2)}ms`);
    }
  }
}

export const domScheduler = new DOMBatchScheduler();

/**
 * Enterprise Reactive Card Component
 * Menggunakan WeakRef dan AbortController untuk menjamin Zero Memory Leaks
 */
export class SafeCardComponent {
  #element;
  #abortController;
  #state = { isExpanded: false };

  constructor(containerElement) {
    this.#element = containerElement;
    this.#abortController = new AbortController();
    this.#initEvents();
  }

  #initEvents() {
    const { signal } = this.#abortController;

    // Event listener yang terikat secara ketat pada AbortSignal
    this.#element.addEventListener(
      'click',
      (e) => this.#handleClick(e),
      { signal }
    );
  }

  #handleClick(e) {
    const target = e.target.closest('[data-action="toggle"]');
    if (!target) return;

    this.#state.isExpanded = !this.#state.isExpanded;
    this.render();
  }

  render() {
    let measuredHeight = 0;

    // BACA (Measure)
    domScheduler.read(() => {
      measuredHeight = this.#element.firstElementChild?.scrollHeight ?? 0;
    });

    // TULIS (Mutate)
    domScheduler.write(() => {
      if (this.#state.isExpanded) {
        this.#element.style.maxHeight = `${measuredHeight}px`;
        this.#element.classList.add('is-expanded');
      } else {
        this.#element.style.maxHeight = '0px';
        this.#element.classList.remove('is-expanded');
      }
    });
  }

  /**
   * Wajib dipanggil saat modul atau komponen di-unmount dari DOM
   */
  destroy() {
    // 1. Cabut semua listener seketika tanpa perlu removeEventListener manual
    this.#abortController.abort();

    // 2. Putuskan referensi DOM untuk Garbage Collector
    this.#element = null;
    this.#state = null;
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time B2B Trading Platform (Jank 12 FPS & Browser Crash)

#### Latar Belakang Masalah
Sebuah platform broker saham multinasional menyajikan live dashboard berisi **5.000 instrumen finansial**. Data diperbarui melalui WebSocket dengan intensitas **300 pembaruan harga per detik**. 

#### Gejala
* UI mengalami pembekuan (*unresponsive main thread*).
* Profiler menunjukkan *FPS anjlok hingga 10–15 FPS*.
* Tab browser pengguna macet (*Aw, Snap! - Out of Memory*) setelah dibuka selama 45 menit.

#### Investigasi DevTools (Root-Cause Analysis)
1. **Layout Thrashing Massal:** Setiap pesan WebSocket yang masuk memicu callback yang langsung mengeksekusi:
   ```javascript
   // Bencana Performa:
   tickerEl.style.backgroundColor = 'green';
   const currentWidth = tickerEl.offsetWidth; // Memaksa Reflow Seketika!
   tickerEl.style.width = `${currentWidth + 2}px`;
   ```
2. **Detached DOM Leaks:** Komponen Bar Chart menghapus node SVG saat re-render, namun objek data lama disimpan di array global `window.tradeHistory = []` yang mereferensikan closure handler dengan binding ke elemen SVG yang sudah terhapus. Sebanyak 1.8 GB RAM teralokasi oleh "Detached SVGElement".

#### Solusi Arsitektural Enterprise
1. **Data Throttling & In-Memory State Buffering:** Mengumpulkan mutasi WebSocket ke dalam dirty set memori lokal, lalu hanya merender diff pada setiap interval render frame (`requestAnimationFrame`).
2. **DOM Virtualization:** Hanya merender 30 item yang terlihat di viewport pengguna menggunakan *Windowing Mechanism*. Sisa 4.970 node tidak dibuat di DOM.
3. **Hardware-Accelerated Compositing:** Mengganti mutasi lebar kolom (`width`) dengan `transform: scaleX(...)`, mengalihkan pekerjaan dari CPU Main Thread ke GPU Compositor.
4. **Lifecycle Disposal:** Memasang `WeakMap` untuk metadata DOM dan membersihkan historical references saat komponen terlepas.

#### Hasil Metrik
* **FPS:** Konstan pada 58–60 FPS.
* **Heap Memory:** Stabil pada angka ~48 MB tanpa kenaikan linear (*flatline footprint*).
* **INP (Interaction to Next Paint):** Turun drastis dari 850ms menjadi 18ms.

---

## 9. Trade-offs

Setiap keputusan arsitektur memiliki konsekuensi. Tidak ada solusi perak (*no silver bullet*).

```
          [Performa Ekstrem: Direct Canvas/WebGL]
                         ▲
                        / \
                       /   \
  (Memory / Complexity)     (Developer Velocity)
                     /       \
                    /         \
[Vanilla Batched DOM] ◄───────► [Virtual DOM Framework]
```

| Pendekatan | Pros | Cons | Biaya Komputasi / Trade-off |
| :--- | :--- | :--- | :--- |
| **Direct Batched DOM (Vanilla)** | Zero-overhead footprint, ukuran bundle 0 KB, memory utilization paling minimal. | Boilerplate tinggi, butuh disiplin pemisahan read/write ketat dari seluruh tim. | Murah di CPU runtime, mahal di waktu engineering. |
| **Virtual DOM Reconciliation** | Declarative DX, abstraksi aman terhadap Layout Thrashing manual. | Memerlukan overhead parsing diffing tree di memori, garbage collector memproses node vDOM sementara. | Boros alokasi heap untuk transient object trees. |
| **Canvas 2D / WebGL Direct Rendering** | Performa 60-120 FPS tanpa batas batas reflow DOM, memproses jutaan elemen visual. | Mengorbankan accessibility bawaan (a11y), screen-reader tidak membaca elemen, text selection harus dibuat manual. | Sangat mahal dalam hal rekayasa UX/A11y, biaya maintenance kode tinggi. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Forced Synchronous Layout di dalam Loop
```javascript
// SALAH: Mengakibatkan N kali Reflow berturut-turut
function resizeAllBad(elements) {
  for (let i = 0; i < elements.length; i++) {
    elements[i].style.width = elements[i].offsetWidth + 10 + 'px';
  }
}

// BENAR: Membaca semua ukuran terlebih dahulu, baru menulis
function resizeAllGood(elements) {
  // 1. Read phase (Browser membaca dari cache layout)
  const widths = elements.map(el => el.offsetWidth);

  // 2. Write phase (Browser mengagregasi dirty styles)
  elements.forEach((el, i) => {
    el.style.width = `${widths[i] + 10}px`;
  });
}
```

### Mistake 2: Retaining Closures pada Window Listeners
```javascript
// SALAH: Element instance tertahan di closure selamanya
function setupWidget(domNode) {
  const largeData = new Uint8Array(10_000_000); // 10MB
  window.addEventListener('resize', () => {
    console.log(domNode.id, largeData.length);
  });
}

// BENAR: Gunakan AbortController dan isolate static state
function setupWidgetClean(domNode) {
  const controller = new AbortController();
  const id = domNode.id; // Hindari menahan pointer ke domNode utuh jika hanya butuh id

  window.addEventListener('resize', () => {
    console.log(id);
  }, { signal: controller.signal });

  return () => controller.abort(); // Lifecycle teardown hook
}
```

### Troubleshooting Runbook: Mendeteksi Memory Leak
1. Buka Chrome DevTools -> tab **Memory**.
2. Pilih **Allocation instrumentation on timeline**, klik **Start**.
3. Lakukan aksi pengguna (misal: Buka modal -> Tutup modal) berulang kali sebanyak 10 kali.
4. Klik **Stop**. Perhatikan bar vertikal biru:
   * Jika bar vertikal biru tidak pernah kembali ke baseline nol setelah bar abu-abu (GC) muncul, berarti ada retainers yang menolak dibersihkan.
5. Pada *Class filter*, cari `Detached`. Klik salah satu detached node dan periksa panel **Retainers** di bawahnya untuk melihat objek JavaScript mana yang masih memegang referensinya.

---

## 11. Best Practices (Production Checklist)

### Layout & Paint Optimization
- [ ] Hindari membaca properti layout (`offsetTop`, `scrollTop`, `clientWidth`, `getComputedStyle`) tepat setelah mengubah properti style.
- [ ] Berikan instruksi layer explicit menggunakan CSS `will-change: transform` hanya pada elemen yang aktif beranimasi, dan hapus properti tersebut setelah animasi selesai untuk menghemat VRAM GPU.
- [ ] Pastikan animasi berjalan eksklusif pada layer Compositor: hanya gunakan `transform` dan `opacity`.

### Asynchronous Execution & Event Loop
- [ ] Pecah tugas JavaScript berdurasi panjang (*Long Tasks* > 50ms) menggunakan `scheduler.yield()` atau pembagian batch via `requestIdleCallback()`.
- [ ] Hindari recursive `queueMicrotask` atau unresolved `Promise` chain loops yang membekukan engine.

### Memory & State Hygenic
- [ ] Seluruh global event subscription (`window`, `document`, WebSocket) wajib memiliki mekanisme teardown (*cleanup/unmount hook*).
- [ ] Gunakan `WeakMap` atau `WeakSet` untuk metadata yang terasosiasi dengan objek DOM.
- [ ] Gunakan `{ passive: true }` pada event listener `touchstart` dan `wheel` agar browser tidak memblokir thread scrolling utama.

---

## 12. Hands-on Practice: Virtualized Data Grid (No Framework)

Buat folder proyek: `hands-on/m02/`

### Struktur File:
```
hands-on/m02/
├── index.html
├── style.css
└── src/
    ├── app.js
    └── VirtualScroller.js
```

### Kode Implementasi:

#### `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Production Virtual Grid</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="app-layout">
    <header>
      <h1>High-Performance Data Grid (100,000 Rows)</h1>
      <div id="metrics" class="metrics-badge">FPS: Calculating...</div>
    </header>
    <main>
      <!-- Container Viewport -->
      <div id="scroll-viewport" class="virtual-viewport">
        <!-- Spacer untuk menyimulasikan tinggi total konten -->
        <div id="scroll-spacer" class="virtual-spacer"></div>
        <!-- Container elemen yang dirender secara aktual -->
        <div id="items-holder" class="items-holder"></div>
      </div>
    </main>
  </div>
  <script type="module" src="src/app.js"></script>
</body>
</html>
```

#### `hands-on/m02/style.css`
```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: #0f172a;
  color: #f8fafc;
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.app-layout {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  height: 100%;
  padding: 1.5rem;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.metrics-badge {
  background: #1e293b;
  border: 1px solid #334155;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-family: monospace;
  font-size: 0.875rem;
  color: #38bdf8;
}

.virtual-viewport {
  flex: 1;
  position: relative;
  overflow-y: auto;
  border: 1px solid #334155;
  border-radius: 8px;
  background-color: #1e293b;
  contain: strict; /* Mengisolasi layout internal dari seluruh halaman */
}

.virtual-spacer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  pointer-events: none;
}

.items-holder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  will-change: transform;
}

.grid-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  height: 40px;
  border-bottom: 1px solid #334155;
  background-color: #1e293b;
}

.grid-row:nth-child(even) {
  background-color: #0f172a;
}

.grid-col-id {
  color: #94a3b8;
  font-family: monospace;
  width: 80px;
}

.grid-col-name {
  flex: 1;
}

.grid-col-val {
  font-weight: 600;
  color: #4ade80;
}
```

#### `hands-on/m02/src/VirtualScroller.js`
```javascript
export class VirtualScroller {
  #viewport;
  #spacer;
  #holder;
  #items;
  #itemHeight;
  #buffer;
  #totalItems;
  #abortController;

  constructor({ viewport, spacer, holder, items, itemHeight = 40, buffer = 5 }) {
    this.#viewport = viewport;
    this.#spacer = spacer;
    this.#holder = holder;
    this.#items = items;
    this.#itemHeight = itemHeight;
    this.#buffer = buffer;
    this.#totalItems = items.length;
    this.#abortController = new AbortController();

    this.#init();
  }

  #init() {
    // 1. Set total height spacer
    this.#spacer.style.height = `${this.#totalItems * this.#itemHeight}px`;

    // 2. Pasang Scroll Handler menggunakan Passive Listener
    const { signal } = this.#abortController;
    let ticking = false;

    this.#viewport.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          this.#render();
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true, signal });

    // Initial render
    this.#render();
  }

  #render() {
    const scrollTop = this.#viewport.scrollTop;
    const viewportHeight = this.#viewport.clientHeight;

    // Menghitung index item yang harus muncul
    let startIndex = Math.floor(scrollTop / this.#itemHeight) - this.#buffer;
    startIndex = Math.max(0, startIndex);

    let endIndex = Math.ceil((scrollTop + viewportHeight) / this.#itemHeight) + this.#buffer;
    endIndex = Math.min(this.#totalItems, endIndex);

    // Hitung offset translasi Y untuk holder
    const offsetY = startIndex * this.#itemHeight;
    this.#holder.style.transform = `translate3d(0, ${offsetY}px, 0)`;

    // Bangun fragment DOM untuk batch render
    const fragment = document.createDocumentFragment();

    for (let i = startIndex; i < endIndex; i++) {
      const item = this.#items[i];
      const row = document.createElement('div');
      row.className = 'grid-row';
      row.innerHTML = `
        <span class="grid-col-id">#${item.id}</span>
        <span class="grid-col-name">${item.label}</span>
        <span class="grid-col-val">${item.value}</span>
      `;
      fragment.appendChild(row);
    }

    // Ganti isi holder secara atomik
    this.#holder.replaceChildren(fragment);
  }

  destroy() {
    this.#abortController.abort();
    this.#holder.replaceChildren();
    this.#items = null;
    this.#viewport = null;
  }
}
```

#### `hands-on/m02/src/app.js`
```javascript
import { VirtualScroller } from './VirtualScroller.js';

// 1. Generate 100,000 Data Set
const data = Array.from({ length: 100_000 }, (_, i) => ({
  id: (i + 1).toString().padStart(6, '0'),
  label: `Corporate Portfolio Security Alpha-${i + 1}`,
  value: `$${(Math.random() * 10000).toFixed(2)}`
}));

// 2. Mount Scroller
const scroller = new VirtualScroller({
  viewport: document.getElementById('scroll-viewport'),
  spacer: document.getElementById('scroll-spacer'),
  holder: document.getElementById('items-holder'),
  items: data,
  itemHeight: 40,
  buffer: 6
});

// 3. FPS & Performance Meter Engine
const metricsEl = document.getElementById('metrics');
let frameCount = 0;
let lastTime = performance.now();

function checkFPS(now) {
  frameCount++;
  if (now - lastTime >= 1000) {
    const fps = Math.round((frameCount * 1000) / (now - lastTime));
    metricsEl.textContent = `FPS: ${fps} | Items: ${data.length.toLocaleString()}`;
    metricsEl.style.color = fps < 45 ? '#ef4444' : '#38bdf8';
    frameCount = 0;
    lastTime = now;
  }
  requestAnimationFrame(checkFPS);
}
requestAnimationFrame(checkFPS);
```

---

## 13. Exercise

### Level Easy
Tentukan urutan output log dari kode asynchronous berikut tanpa menjalankannya di konsol browser:
```javascript
console.log('A');
setTimeout(() => console.log('B'), 0);
Promise.resolve().then(() => {
  console.log('C');
  return Promise.resolve('D');
}).then((val) => console.log(val));
queueMicrotask(() => console.log('E'));
console.log('F');
```
*Tugas:* Tuliskan urutan huruf dan sertakan identifikasi antrean (Sync/Microtask/Macrotask) untuk setiap huruf.

### Level Medium
Diberikan fungsi berikut yang mengalami masalah berat **Forced Synchronous Layout**:
```javascript
function alignHeights(elements) {
  elements.forEach((el, index) => {
    if (index > 0) {
      const prevHeight = elements[index - 1].clientHeight;
      el.style.height = `${prevHeight + 5}px`;
    }
  });
}
```
*Tugas:* Tulis ulang implementasi fungsi di atas agar berjalan dalam $O(N)$ waktu baca-tulis terpisah menggunakan `requestAnimationFrame` tanpa memicu reflow berganda.

### Level Hard
Buat class `ReactiveDataStore` murni (Vanilla JS) dengan batasan:
1. Menyimpan state bertingkat (*nested object*).
2. Mendukung metode `.subscribe(key, callback)`.
3. Memanfaatkan `Proxy` JavaScript.
4. Notifikasi subscription wajib di-*batch* secara otomatis menggunakan **Microtask Queue** (`queueMicrotask`), sehingga jika terjadi 1.000 mutasi properti synchronous dalam satu eksekusi fungsi, subscriber hanya dipanggil **satu kali** dengan nilai akhir.

---

## 14. Challenge (Studi Kasus Nyata)

### High-Frequency Financial Ticker Engine

Anda ditugaskan merancang modul frontend yang menerima update harga pasar saham dari simulasi WebSocket:
* **Beban Data:** 10.000 events/detik berisi `{ ticker: string, price: number, delta: number }`.
* **Kebutuhan Visual:** List antarmuka harus menampilkan 50 saham paling aktif. Jika harga naik, warna baris berkedip hijau sejenak; jika turun, berkedip merah.
* **Batasan Ketat (Hard Constraints):**
  1. Main thread execution tidak boleh mengalami *Long Task* (> 50ms).
  2. Memory footprint harus konstan (tidak boleh ada kenaikan grafik memory secara linear selama 30 menit uji stres).
  3. Dilarang menggunakan framework eksternal apa pun (React, Vue, lodash, dsb).
  4. Animasi perubahan warna dilarang memicu tahap Layout/Reflow pada browser (wajib murni Composite).
  5. UI harus responsif terhadap klik pengguna (Latency klik input < 50ms / lolos audit INP Google).

*Deliverable:* Desain arsitektur modul, mitigasi bottleneck dengan buffering/worker, dan implementasi kodenya.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konseptual Fundamental (Basic)
1. **Tahap manakah dalam Critical Rendering Path yang membutuhkan biaya komputasi paling tinggi jika terjadi mutasi geometri seperti `margin-left`?**
   * A. Composite
   * B. Rasterization
   * C. Layout / Reflow
   * D. Paint

2. **Perbedaan fundamental antara Macrotask Queue dan Microtask Queue dalam siklus Event Loop adalah:**
   * A. Macrotask dieksekusi lebih dulu sebelum Microtask pertama dijalankan.
   * B. Seluruh antrean Microtask dihabiskan (*drained*) segera setelah sebuah task/macrotask selesai, sebelum render step atau task berikutnya.
   * C. Microtask hanya disediakan untuk event klik mouse.
   * D. Macrotask berjalan pada background web-worker thread.

3. **Mengapa penggunaan CSS `transform: translate3d(0, y, 0)` lebih disukai daripada memodifikasi `top` atau `margin-top` saat melakukan animasi pergerakan?**
   * A. Karena `transform` tidak membutuhkan CSSOM tree.
   * B. Karena `transform` dapat dieksekusi langsung oleh Compositor Thread di GPU tanpa memicu ulang fase Layout dan Paint.
   * C. Karena `top` tidak didukung oleh browser berbasis Chromium.
   * D. Karena `transform` berjalan di thread Microtask.

4. **Bagaimana cara kerja atribut `defer` pada pemanggilan tag `<script src="...">`?**
   * A. Memblokir parser HTML sampai script selesai diunduh dan dieksekusi.
   * B. Mengunduh secara paralel dan mengeksekusi script secara instan begitu unduhan selesai, tanpa memperhatikan urutan parsing HTML.
   * C. Mengunduh secara paralel dengan parsing HTML, dan mengeksekusi script secara berurutan hanya setelah dokumen selesai diparsing (*DOM Interactive*).
   * D. Menunda unduhan script sampai pengguna melakukan scrolling pertama.

5. **Apa yang dimaksud dengan kondisi Detached DOM Node?**
   * A. Elemen DOM yang tidak memiliki properti styling CSS.
   * B. Node DOM yang telah dicabut dari layout visual dokumen, namun tetap bertahan di memori heap karena masih ada variabel/closure JavaScript yang mereferensikannya.
   * C. Elemen yang dibuat menggunakan `document.createElement` tetapi belum dipasangi ID.
   * D. Node DOM yang dirender di dalam `<iframe>`.

---

### Bagian B: Analisis Kode & Algoritma (Intermediate)
6. **Perhatikan kode berikut:**
   ```javascript
   function updateWidths() {
     const boxes = document.querySelectorAll('.box');
     for (let i = 0; i < boxes.length; i++) {
       const box = boxes[i];
       const currentWidth = box.getBoundingClientRect().width;
       box.style.width = `${currentWidth + 10}px`;
     }
   }
   ```
   **Anomali performa rendering apa yang secara langsung terjadi jika ada 500 elemen `.box`?**
   * A. Memory Overflow (Crash)
   * B. Forced Synchronous Layout / Layout Thrashing
   * C. Microtask Starvation
   * D. CSS Parsing Deadlock

7. **Kapan browser engine memutuskan untuk menjalankan callback yang didaftarkan melalui `requestAnimationFrame`?**
   * A. Tepat sebelum siklus repaint/rendering frame berikutnya dijalankan oleh browser.
   * B. Tepat setelah `setTimeout(fn, 0)` selesai dieksekusi di Macrotask queue.
   * C. Segera setelah parsing dokumen HTML selesai, sebelum event `DOMContentLoaded`.
   * D. Selalu konstan tepat setiap 1 milidetik.

8. **Manakah dari pola penggunaan event listener berikut yang paling efektif mencegah kebocoran memori saat elemen sering dibuat dan dihancurkan secara dinamis?**
   * A. Menambahkan listener langsung ke setiap elemen dengan inline event handler (`onclick="..."`).
   * B. Menggunakan global variable untuk menampung seluruh DOM instances.
   * C. Menggunakan pola Event Delegation pada parent container statis dan memanfaatkan `AbortController` signal untuk cleanup instan.
   * D. Mengandalkan V8 Garbage Collector secara otomatis tanpa mencabut listener.

9. **Apa dampak utama terhadap runtime jika microtask mendaftarkan microtask baru secara rekursif tanpa henti (*infinite microtask creation*)?**
   * A. Macrotask queue akan mengambil alih eksekusi secara otomatis.
   * B. Thread rendering dan task queue terblokir total, menyebabkan antarmuka halaman hang dan unresponsive.
   * C. Browser akan melempar error `Maximum call stack size exceeded` seketika.
   * D. Kecepatan rendering meningkat menjadi 120 FPS.

10. **Apa fungsi dari parameter `{ passive: true }` pada `addEventListener`?**
    * A. Memberitahu browser bahwa handler ini tidak akan pernah memanggil `event.preventDefault()`, memungkinkan browser melakukan scroll halus secara instan tanpa menunggu listener selesai dieksekusi.
    * B. Mengubah listener dari synchronous menjadi asynchronous Web Worker task.
    * C. Memastikan event hanya dipicu satu kali saja.
    * D. Memaksa event berjalan di fase capturing, bukan bubbling.

---

### Bagian C: Skenario Kasus Arsitektural Produksi
11. **Skenario 1:** Sebuah website e-commerce memiliki skor Largest Contentful Paint (LCP) yang buruk (5.8 detik). Banner LCP adalah gambar berukuran 1.2 MB dengan tag `<img src="banner.jpg">` yang di-inject melalui tag `<script>` pihak ketiga di akhir file `body`. Analisis letak kegagalan alur rendering dan rekomendasikan tindakan arsitektural untuk menekan angka LCP menjadi < 2.0 detik!

12. **Skenario 2:** Tim frontend Anda melaporkan bahwa aplikasi Single Page Application (SPA) perbankan yang berjalan lama mengalami peningkatan penggunaan memori secara linear (dari 30MB menjadi 800MB setelah 2 jam). Di halaman riwayat transfer, terdapat event listener ke `window` yang dipasang setiap kali komponen tabel dibuka. Bagaimana Anda merekayasa arsitektur base component untuk memastikan regresi memory leak semacam ini dicegah secara sistematis di tingkat CI/CD dan code pattern?

13. **Skenario 3:** Halaman visualisasi data analitik memiliki 20 chart interaktif. Ketika slider filter rentang waktu digeser (*slide event*), slider terasa tersendat-sendat (*jank*) dengan Interaction to Next Paint (INP) mencapai 450ms. Profiler CPU menunjukkan *scripting time* 380ms yang memproses komputasi kalkulasi data array mentah sebelum menggambar grafik. Bagaimana strategi arsitektural untuk membagi tugas komputasi dan rendering ini agar INP turun di bawah 50ms?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A (Basic)
1. **C** — Mutasi geometris (`margin-left`) memicu seluruh pipeline secara lengkap dari tahap Layout/Reflow, lalu Paint, hingga Compositing.
2. **B** — Aturan Event Loop mewajibkan Microtask Queue dikuras hingga kosong sebelum melanjutkan ke proses berikutnya.
3. **B** — Properti `transform` ditangani langsung oleh Compositor thread di GPU, menghindari tahap Layout dan Paint.
4. **C** — `defer` mengunduh secara asinkron tanpa memblokir parser HTML dan menjamin eksekusi script sesuai urutan setelah HTML selesai diurai.
5. **B** — Detached node adalah elemen yang sudah dilepas dari DOM Tree aktif, namun gagal dibersihkan oleh Garbage Collector karena masih tersimpan pada referensi variabel/closure.

#### Bagian B (Intermediate)
6. **B** — Membaca `getBoundingClientRect().width` lalu langsung menulis `style.width` secara berulang dalam loop memaksa engine browser menghitung geometri berulang kali (Layout Thrashing).
7. **A** — `requestAnimationFrame` dirancang khusus untuk berjalan tepat sebelum siklus render/paint browser dimulai.
8. **C** — Event delegation meminimalkan alokasi listener di memori, dan `AbortController` memutus referensi event listener secara menyeluruh dalam satu pemanggilan `.abort()`.
9. **B** — Berbeda dengan Call Stack yang akan melempar stack overflow, Microtask queue yang terus terisi akan memonopoli Main Thread tanpa henti, sehingga browser tidak pernah mencapai tahap rendering maupun menangani macrotask.
10. **A** — Flag `passive: true` mencegah thread komposit menunggu hasil eksekusi JavaScript (karena jaminan tidak ada pemanggilan `preventDefault()`), mengeliminasi delay pada scroll sentuh.

#### Bagian C (Solusi Skenario Produksi)
11. **Rekomendasi Solusi Skenario 1:**
    * *Akar Masalah:* Discovery latency gambar sangat terlambat karena bergantung pada parser JavaScript pihak ketiga di akhir `<body>`.
    * *Langkah Solusi:*
      1. Tempatkan tag `<img>` banner langsung pada HTML mentah (SSR) tanpa menunggu JavaScript.
      2. Berikan tag `<link rel="preload" fetchpriority="high" as="image" href="banner.webp" type="image/webp">` di dalam blok `<head>`.
      3. Kompresi gambar menjadi format modern (AVIF/WebP) dan sesuaikan resolusi dengan viewport (`srcset`).
      4. Pasang atribut `loading="eager"` dan `fetchpriority="high"` langsung pada tag `<img>`.
12. **Rekomendasi Solusi Skenario 2:**
    * *Akar Masalah:* Event listener global yang terus bertambah pada obyek `window` tanpa di-deregister saat komponen unmount, menahan referensi instance tabel di dalam closure (*detached memory leak*).
    * *Langkah Solusi:*
      1. Buat abstraksi `BaseComponent` lifecycle yang mengikat seluruh event listener internal ke satu instance `AbortController`.
      2. Metode `unmount()` secara otomatis mengeksekusi `this.abortController.abort()` dan mengosongkan referensi internal (`this.state = null`, `this.domNode = null`).
      3. Di pipeline CI/CD, tambahkan *End-to-End Automated Leak Detection* menggunakan Playwright / Puppeteer dengan mengambil heap dump snapshot sebelum dan sesudah navigasi 50x; gagalkan build jika heap size delta bertambah melebihi threshold tertentu (> 5MB).
13. **Rekomendasi Solusi Skenario 3:**
    * *Akar Masalah:* Heavy computation dijalankan synchronous di thread utama (Main Thread) saat event dragging slider berlangsung, menunda browser melakukan frame paint.
    * *Langkah Solusi:*
      1. Pindahkan seluruh kalkulasi filtering data mentah (380ms) ke **Web Worker** terpisah. Main thread hanya mengirimkan payload filter range.
      2. Terapkan *Debouncing/Throttling* pada input slider untuk mengurangi frekuensi pengiriman pesan ke Web Worker.
      3. Gunakan `scheduler.yield()` atau pembagian batch rendering jika data chart digambar melalui canvas atau SVG, sehingga event input pengguna tetap bisa disisipkan (*unblocked main thread*), menekan INP ke level < 50ms.

---

## 16. Summary

1. **Browser Architecture Invariant:** Pemahaman mendalam atas Critical Rendering Path (Parsing $\rightarrow$ Style $\rightarrow$ Layout $\rightarrow$ Paint $\rightarrow$ Composite) adalah dasar optimasi web. Sebisa mungkin batasi manipulasi visual hanya pada properti yang dapat diproses langsung oleh GPU Compositor (`transform`, `opacity`).
2. **Event Loop Predictability:** Microtask Queue selalu menguras habis tugasnya sebelum Browser melanjutkan ke tahap Render Step atau Macrotask berikutnya. Menjalankan proses blocking pada microtask sama berbahayanya dengan synchronous loop.
3. **Layout Hygiene:** Hindari layout thrashing dengan menerapkan *Two-Phase Commit Pattern* (Kumpulkan seluruh pembacaan/measurements terlebih dahulu sebelum melakukan penulisan/mutasi styles).
4. **Memory Discipline:** Garbage Collector tidak membebaskan memori selama masih ada jalur referensi dari root window. Bersihkan event listener, batalkan operasi asinkron yang belum selesai via `AbortController`, dan hindari penyimpanan node DOM yang sudah terlepas di dalam array atau closure global.
5. **Architectural Virtualization:** Di tingkat aplikasi skala besar, jangan merender data melampaui kapasitas viewport pengguna. Gunakan teknik virtual scrolling untuk mempertahankan performa rendering 60 FPS dan penggunaan memori yang konstan.