# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, software engineer diharapkan mampu:

1. **Menganalisis Internal Browser Engine**: Menguraikan alur kerja internal *browser engine* (Blink/V8, Gecko/SpiderMonkey) mulai dari proses *tokenization*, *tree construction*, *style computation*, *layout/reflow*, *paint*, hingga *compositing* pada layer GPU.
2. **Mengeliminasi Bottleneck Performa Render**: Mengidentifikasi dan memitigasi *Layout Thrashing* (*Forced Synchronous Layout*), *Excessive DOM Repaint*, dan *Long Tasks* yang memblokir *Main Thread* dengan memanfaatkan API web modern (`requestAnimationFrame`, `ResizeObserver`, `IntersectionObserver`).
3. **Mengimplementasikan Arsitektur Komponen Native Produksi**: Membangun sistem komponen modular berbasis *Web Components Native* (Custom Elements v1, Shadow DOM, HTML Templates) yang mengisolasi *style*, *state*, dan *lifecycle* tanpa dependensi *framework*.
4. **Mendesain Pola Pengelolaan Memori Rendah Jejak (*Low-Footprint Memory Management*)**: Mencegah kebocoran memori (*memory leaks*) dari siklus hidup *detached DOM trees*, *unbound event listeners*, serta mengoptimalkan *Garbage Collection* (GC) menggunakan `WeakMap`, `WeakSet`, dan `AbortController`.
5. **Membangun Pipeline Build dan Asset Bundling Skala Enterprise**: Mengonfigurasi strategi *code splitting*, *tree shaking*, *content hashing*, dan kompresi tingkat lanjut (Brotli/Gzip) untuk meminimalkan *First Contentful Paint* (FCP) dan *Cumulative Layout Shift* (CLS).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda harus sudah menguasai:

* **Sintaksis ECMAScript Modern (ES6+)**: `Class`, `Promise`, `async/await`, Destructuring, ES Modules (`import`/`export`).
* **Struktur Dasar DOM & Event-Driven Architecture**: Pemahaman tentang `document.querySelector`, *Event Bubbling*, *Capturing*, dan *Event Delegation*.
* **HTTP/Network Fundamentals**: HTTP/2 multiplexing, HTTP/3, TLS handshakes, Cache-Control headers (`max-age`, `immutable`, `ETag`).
* **Tooling Lingkungan Pengembangan**: Terminal Unix-like, Node.js runtime (v18+ LTS), dan manajer paket (pnpm/npm).

---

## 3. Concept & Internal Architecture

Memahami pengembangan web modern tingkat lanjut memerlukan dekonstruksi atas apa yang terjadi secara deterministik di balik layar ketika berkas HTML, CSS, dan JavaScript dieksekusi oleh mesin peramban (*browser engine*).

```
+---------------------------------------------------------------------------------------+
|                                    BROWSER ENGINE                                     |
|                                                                                       |
|  [Network Bytes] ---> [Tokenization] ---> [Nodes] ---> [DOM Tree]                     |
|                                                              \                        |
|  [Network Bytes] ---> [Tokenization] ---> [Nodes] ---> [CSSOM Tree]                   |
|                                                                \                      |
|                                                                 v                     |
|                                                         [Render Tree]                 |
|                                                               |                       |
|                                                               v                       |
|                                                         [Layout / Reflow]             |
|                                                               |                       |
|                                                               v                       |
|                                                         [Paint / Raster]              |
|                                                               |                       |
|                                                               v                       |
|  [GPU Thread] <========================================= [Compositing]               |
+---------------------------------------------------------------------------------------+
```

### 3.1 The Critical Rendering Path (CRP)

1. **DOM Tree Construction**:
   * *Byte Stream ke Karakter*: Parser membaca byte mentah (misal: `48 54 4D 4C`) dan menerjemahkannya ke karakter berdasarkan *encoding* dokumen (UTF-8).
   * *Tokenization*: Tokenizer berbasis *state-machine* mengonversi aliran karakter menjadi token diskret: `StartTag`, `EndTag`, `Character`, `Comment`, `DOCTYPE`.
   * *Tree Construction*: Token dikonsumsi oleh parser untuk menghasilkan objek `Node` yang saling terhubung dalam struktur hierarki pohon (*DOM Tree*). Parser bersifat *re-entrant*; jika menemukan tag `<script>` non-async/non-defer, proses parsing DOM dihentikan secara sinkron hingga skrip selesai diunduh dan dieksekusi.

2. **CSSOM Tree Construction**:
   * Bersamaan dengan parsing DOM, deklarasi CSS dipetakan menjadi *CSS Object Model* (CSSOM). Berbeda dengan DOM yang dapat diproses parsial (*incremental display*), CSSOM bersifat **render-blocking** secara total. Browser tidak dapat merender subtree apa pun sebelum CSSOM sepenuhnya stabil, guna menghindari *Flash of Unstyled Content* (FOUC).

3. **Render Tree Generation**:
   * Penggabungan DOM dan CSSOM. Node dengan nilai CSS `display: none` diabaikan sepenuhnya dari Render Tree. Sebaliknya, pseudo-element seperti `::before` dan `::after` disisipkan ke dalam Render Tree meskipun tidak ada di DOM murni.

4. **Layout (Reflow)**:
   * Menghitung geometri persis: posisi absolut koordinat $(x, y)$ dan dimensi (lebar, tinggi) tiap node relatif terhadap *viewport*. Kalkulasi ini menggunakan algoritma berbasis *Box Model*. Operasi Layout pada CPU bersifat mahal secara komputasional ($O(N)$ atau bahkan $O(N^2)$ pada nested table/deep DOM).

5. **Paint (Rasterization)**:
   * Mengonversi visual node (warna, bayangan, border, teks) menjadi representasi bitmap piksel pada memori. Menggunakan konsep *Display Lists* yang membagi visual menjadi beberapa perintah gambar visual.

6. **Compositing**:
   * Browser memecah halaman menjadi lapisan-lapisan (*layers*) independen. Lapisan ini dikirim ke GPU (*Graphical Processing Unit*) melalui *compositor thread*. GPU menangani transformasi matriks visual (seperti `transform: translate3d()` dan `opacity`) tanpa memicu Reflow atau Paint ulang pada CPU.

### 3.2 JavaScript Engine (V8): Pipeline & Event Loop

Di lingkungan Chromium, engine V8 mengeksekusi JavaScript melalui pipeline:
* **Parser**: Mengubah *source code* menjadi *Abstract Syntax Tree* (AST).
* **Ignition**: *Interpreter* yang mengompilasi AST menjadi *Bytecode*.
* **TurboFan**: *Optimizing compiler* yang mengambil profil *runtime* (*type feedback*) dan mengompilasi *hot bytecode* menjadi *Machine Code* native. Jika terjadi perubahan tipe data (*type mutation* / polymorphism), TurboFan melakukan *Deoptimization* balik ke bytecode.

**Event Loop, Task Queue, dan Microtask Queue**:
* **Call Stack**: Struktur data eksekusi LIFO (Last-In-First-Out).
* **Microtask Queue**: Dieksekusi **segera** setelah *call stack* kosong, sebelum browser menyerahkan kontrol ke siklus render berikutnya. Sumber microtask: `Promise.then/catch/finally`, `queueMicrotask()`, `MutationObserver`.
* **Macrotask (Task) Queue**: Dieksekusi bergantian, satu task per putaran siklus event loop. Sumber: `setTimeout`, `setInterval`, `setImmediate`, I/O, UI rendering events.
* **Render Pipeline Execution**: Browser menargetkan 60 FPS (1 frame per 16.66ms) atau 120 FPS (8.33ms). Callback `requestAnimationFrame` (rAF) dieksekusi tepat sebelum fase Layout dan Paint, menjadikannya satu-satunya titik valid untuk manipulasi DOM visual yang sinkron dengan refresh rate layar.

---

## 4. Why & What

### Mengapa Pendekatan Pemula Menjadi Liar di Skala Enterprise?
Pada skala aplikasi korporasi (*enterprise*), ratusan modul, ribuan elemen visual dinamis, dan koneksi data *real-time* (WebSocket/SSE) berjalan bersamaan. Kesalahan arsitektur sederhana dapat menyebabkan:
* **Jank & Dropped Frames**: Interaksi pengguna lag karena Main Thread diblokir kalkulasi tata letak berulang (*Layout Thrashing*).
* **Memory Bloat**: Aplikasi web yang dibiarkan terbuka berjam-jam (misal: sistem CRM, dashboard analitik pasar saham) perlahan memakan RAM hingga tab peramban mengalami *crash* (*Out of Memory*).
* **CSS Specificity Wars**: Kebocoran styling global akibat tidak adanya enkapsulasi, menyebabkan regresi antarmuka di tim lintas domain.

### Apa yang Kita Bangun?
Kita mengimplementasikan **Arsitektur Berbasis Standar Web Terenkapsulasi (Native Production Architecture)**:
* Menggunakan **Web Components Standard (Custom Elements + Shadow DOM)** untuk enkapsulasi absolut tanpa overhead kompilator pihak ketiga.
* Mengadopsi pola **Unidirectional Data Flow & State Batching** murni berbasis JavaScript murni (Vanilla).
* Menerapkan pengawasan memori deterministik dan strategi orkestrasi DOM rendering bebas jank.

---

## 5. How: Workflow Detail

Alur kerja arsitektur komponen native berbasis performa:

```
[State Mutation] 
       │
       ▼
[Batch Queue (Microtask Engine)] ──(Deduplikasi Perubahan)
       │
       ▼
[RequestAnimationFrame (rAF)] ────(Sinkronisasi Hardware Display)
       │
       ▼
[Shadow DOM Mutator] ─────────────(Hanya Render Patch Elemen Relevan)
       │
       ▼
[GPU Layer Promotion] ────────────(Transformasi & Animasi via CSS Compositor)
```

1. **State Mutation Dipicu**: Terjadi perubahan data via aksi pengguna atau payload WebSocket.
2. **Batch Queue**: Perubahan tidak langsung menyentuh DOM. Perubahan ditampung dalam antrean microtask untuk menduplikasi mutasi redundan dalam satu tick eksekusi.
3. **Frame Alignment**: Pembaruan DOM dikunci (*locked*) di dalam blok eksekusi `requestAnimationFrame`.
4. **Isolasi Mutasi Shadow DOM**: Perubahan diterapkan langsung pada sub-tree terisolasi (*Shadow Root*) sehingga tidak memicu kalkulasi ulang selektor CSS di level global dokumen.
5. **GPU Layer Promotion**: Node yang membutuhkan animasi dipromosikan ke layer compositing khusus menggunakan CSS `will-change` secara hemat dan selektif.

---

## 6. Analogy & Diagram ASCII

### Analogi: Konduktor Orkestra vs. Pekerja Lepas Tak Terkoordinasi
* **Pola Pemula (Layout Thrashing)**: Bayangkan seorang pekerja mendekorasi panggung yang meletakkan mikrofon, lalu turun ke bangku penonton untuk mengukur jaraknya menggunakan meteran. Kemudian naik lagi menaruh speaker, turun lagi mengukur jaraknya, dan mengulanginya 100 kali. Pertunjukan tertunda total.
* **Pola Enterprise (Batching & Shadow DOM)**: Konduktor orkestra mengumpulkan seluruh daftar instrumen, membuat sketsa tata letak secara terpisah (*Shadow DOM*), lalu menginstruksikan seluruh tim panggung memposisikan semua instrumen sekaligus dalam satu aba-aba tepat sebelum tirai dibuka (*requestAnimationFrame*).

### Siklus Eksekusi Frame Peramban (16.6ms Lifecycle)

```
+------------------------------------------------------------------------------------+
|                                SIKLUS SATU FRAME (16.6ms)                          |
+------------------------------------------------------------------------------------+
| 1. Input Events     | Wheel, Touch, Click dispatched                               |
| 2. JS Execution     | Macrotask -> Microtasks Drain (Promises, MutationObservers)  |
| 3. Begin Frame      | rAF (requestAnimationFrame Callbacks dieksekusi di sini)     |
| 4. Layout/Reflow    | Penghitungan Geometri Box Model (HINDARI BACA DOM DI SINI!)   |
| 5. Paint/Raster     | Penggambaran bitmap elemen ke memory buffers                 |
| 6. Composite        | GPU menggabungkan layer visual ke layar fisik               |
+------------------------------------------------------------------------------------+
```

---

## 7. Implementation Examples

### 7.1 Simple Example: Deteksi dan Solusi Layout Thrashing

Di bawah ini adalah perbandingan langsung antara kode bermasalah (*forced synchronous layout*) dan pola yang telah dioptimasi.

#### Bad Implementation (Layout Thrashing Trigger)
```javascript
/**
 * BURUK: Membaca properti geometri (offsetWidth) lalu langsung menulis (style.width)
 * secara bergantian di dalam loop memicu peramban melakukan sinkronisasi kalkulasi
 * layout secara paksa (Reflow) pada SETIAP iterasi.
 */
function resizeElementsBad(elements) {
  for (let i = 0; i < elements.length; i++) {
    // READ (Layout dipaksa sinkron)
    const currentWidth = elements[i].offsetWidth; 
    // WRITE (DOM diinvalidasi)
    elements[i].style.width = `${currentWidth + 10}px`; 
  }
}
```

#### Production-Grade Implementation (Batch Read-Write Separation)
```javascript
/**
 * BAIK: Memisahkan fase READ secara masal, kemudian menjadwalkan fase WRITE
 * secara serentak di dalam requestAnimationFrame.
 */
function resizeElementsOptimized(elements) {
  // Phase 1: BATCH READ (Semua pengukuran dibaca bersamaan)
  const widths = new Array(elements.length);
  for (let i = 0; i < elements.length; i++) {
    widths[i] = elements[i].offsetWidth;
  }

  // Phase 2: BATCH WRITE (Semua mutasi gaya visual dialokasikan ke render cycle)
  window.requestAnimationFrame(() => {
    for (let i = 0; i < elements.length; i++) {
      elements[i].style.width = `${widths[i] + 10}px`;
    }
  });
}
```

---

### 7.2 Practical Example: Enterprise Native Web Component

Komponen berikut mengimplementasikan:
* Enkapsulasi penuh menggunakan **Shadow DOM (closed mode)**.
* Reaktivitas atribut via `observedAttributes` dan `attributeChangedCallback`.
* Pembersihan memori deterministik menggunakan `AbortController`.
* Penjadwalan render berbasis antrean microtask (*microtask debounce batching*).

```javascript
/**
 * Enterprise MetricCard Component
 * Mendemonstrasikan enkapsulasi tinggi, zero-leak event handling, dan batched rendering.
 */
class MetricCard extends HTMLElement {
  #shadowRoot;
  #abortController;
  #state = {
    title: '',
    value: 0,
    trend: 'neutral'
  };
  #renderQueued = false;

  static get observedAttributes() {
    return ['metric-title', 'metric-value', 'metric-trend'];
  }

  constructor() {
    super();
    // Gunakan 'open' jika butuh testing eksternal, atau 'closed' untuk proteksi maksimal.
    this.#shadowRoot = this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    this.#abortController = new AbortController();
    const { signal } = this.#abortController;

    // Registrasi event listener menggunakan signal agar dapat dihapus otomatis secara deterministik
    this.addEventListener('click', this.#handleCardClick.bind(this), { signal });

    // Setup initial DOM tree scaffold
    this.#initShadowDOM();
    this.#queueRender();
  }

  disconnectedCallback() {
    // Membersihkan seluruh memory leaks dan event bindings saat node dihapus dari DOM
    if (this.#abortController) {
      this.#abortController.abort();
      this.#abortController = null;
    }
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue) return;

    switch (name) {
      case 'metric-title':
        this.#state.title = newValue || '';
        break;
      case 'metric-value':
        this.#state.value = Number(newValue) || 0;
        break;
      case 'metric-trend':
        this.#state.trend = ['up', 'down', 'neutral'].includes(newValue) ? newValue : 'neutral';
        break;
    }

    this.#queueRender();
  }

  #handleCardClick(event) {
    // Custom Events dengan bubbling melewati Shadow Boundary via composed: true
    this.dispatchEvent(new CustomEvent('metric-selected', {
      detail: { ...this.#state },
      bubbles: true,
      composed: true
    }));
  }

  #initShadowDOM() {
    this.#shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          contain: content; /* Isolasi layout, style, dan paint untuk optimasi browser engine */
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          transition: transform 0.2s ease, box-shadow 0.2s ease;
          user-select: none;
          cursor: pointer;
        }
        :host(:hover) {
          transform: translateY(-2px);
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .header {
          font-size: 0.875rem;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .body {
          margin-top: 8px;
          display: flex;
          align-items: baseline;
          gap: 8px;
        }
        .value {
          font-size: 1.875rem;
          font-weight: 700;
          color: #0f172a;
        }
        .trend {
          font-size: 0.875rem;
          font-weight: 600;
        }
        .trend-up { color: #16a34a; }
        .trend-down { color: #dc2626; }
        .trend-neutral { color: #64748b; }
      </style>
      <div class="card-container">
        <div class="header" id="label-title"></div>
        <div class="body">
          <div class="value" id="label-value"></div>
          <span class="trend" id="label-trend"></span>
        </div>
      </div>
    `;
  }

  #queueRender() {
    // Microtask Batching: Jika ada 10 mutasi atribut sekaligus, proses update DOM hanya terjadi 1 kali
    if (this.#renderQueued) return;
    this.#renderQueued = true;

    queueMicrotask(() => {
      this.#renderQueued = false;
      this.#applyDOMUpdates();
    });
  }

  #applyDOMUpdates() {
    if (!this.#shadowRoot) return;

    const titleEl = this.#shadowRoot.querySelector('#label-title');
    const valueEl = this.#shadowRoot.querySelector('#label-value');
    const trendEl = this.#shadowRoot.querySelector('#label-trend');

    if (titleEl) titleEl.textContent = this.#state.title;
    if (valueEl) valueEl.textContent = this.#state.value.toLocaleString();
    
    if (trendEl) {
      trendEl.textContent = this.#state.trend === 'up' ? '▲' : this.#state.trend === 'down' ? '▼' : '●';
      trendEl.className = `trend trend-${this.#state.trend}`;
    }
  }
}

// Mencegah error definisi ganda jika modul dimuat ulang (HMR)
if (!customElements.get('metric-card')) {
  customElements.define('metric-card', MetricCard);
}
```

---

## 8. Real-World Case Study: High-Throughput Financial Order Book

### Masalah
Sebuah platform broker saham enterprise menghadapi masalah performa parah pada antarmuka *Order Book* mereka. Server mengirimkan pembaruan harga melalui WebSocket hingga **150 paket data per detik**. 

Implementasi awal menggunakan manipulasi DOM naif via `element.innerHTML` pada setiap kedatangan pesan WebSocket. Dampak pada sistem:
1. Pemanfaatan CPU browser mencapai **100%** secara konstan.
2. Frame rate merosot hingga **8-12 FPS** (*extreme UI freezing*).
3. Pengguna tidak dapat menekan tombol eksekusi transaksi beli/jual karena *Main Thread starvation*.

### Solusi Arsitektur
1. **Ring Buffer & Throttling via rAF**: Menggunakan struktur data *Ring Buffer* untuk menyerap pesan WebSocket berfrekuensi tinggi tanpa melakukan manipulasi DOM secara langsung.
2. **Virtual DOM Off-Screen Buffer (DocumentFragment)**: Data hanya dipetakan ke DOM hidup tepat sebelum fase rendering monitor (16.6ms menggunakan `requestAnimationFrame`).
3. **CSS Containment (`contain: strict`)**: Mengisolasi kontainer Order Book agar perhitungan reflow dari ribuan baris angka tidak merambat ke seluruh halaman web.

```javascript
/**
 * Production High-Frequency DOM Engine
 */
class HighFrequencyOrderBook {
  #container;
  #updateQueue = [];
  #isLoopRunning = false;
  #maxBufferedRecords = 500;

  constructor(containerElement) {
    this.#container = containerElement;
    // Terapkan isolasi browser engine
    this.#container.style.contain = 'strict';
  }

  // Dipanggil setiap kali pesan data WebSocket masuk (150x per detik)
  onSocketMessage(orderPayload) {
    if (this.#updateQueue.length >= this.#maxBufferedRecords) {
      // Discard policy: Buang data terlama jika konsumsi render lambat (Backpressure handling)
      this.#updateQueue.shift();
    }
    this.#updateQueue.push(orderPayload);

    this.#startRenderLoop();
  }

  #startRenderLoop() {
    if (this.#isLoopRunning) return;
    this.#isLoopRunning = true;

    window.requestAnimationFrame((timestamp) => this.#renderFrame(timestamp));
  }

  #renderFrame(timestamp) {
    // Jika tidak ada data yang tersisa, hentikan loop
    if (this.#updateQueue.length === 0) {
      this.#isLoopRunning = false;
      return;
    }

    // Ambil seluruh data yang menumpuk di antrean saat frame ini dieksekusi (Batch Drain)
    const recordsToRender = this.#updateQueue.splice(0, this.#updateQueue.length);

    // Gunakan DocumentFragment untuk mutasi di luar DOM Tree aktif
    const fragment = document.createDocumentFragment();

    for (let i = 0; i < recordsToRender.length; i++) {
      const row = document.createElement('div');
      row.className = `order-row type-${recordsToRender[i].side}`;
      row.textContent = `${recordsToRender[i].price.toFixed(2)} - ${recordsToRender[i].amount}`;
      fragment.appendChild(row);
    }

    // Satu kali operasi mutasi aktif: Mengganti konten secara atomik
    this.#container.replaceChildren(fragment);

    // Lanjutkan loop di frame berikutnya jika ada data baru masuk selama proses render
    if (this.#updateQueue.length > 0) {
      window.requestAnimationFrame((t) => this.#renderFrame(t));
    } else {
      this.#isLoopRunning = false;
    }
  }
}
```

### Hasil Metrik Produksi
* **CPU Usage**: Menurun dari 100% menjadi rata-rata **14%**.
* **Frame Rate**: Stabil di angka **60 FPS**.
* **Latency Interaksi (INP - Interaction to Next Paint)**: Berkurang dari 850ms menjadi **12ms**.

---

## 9. Trade-Offs

| Pendekatan / Teknologi | Trade-Off Positif (Keuntungan) | Trade-Off Negatif (Konsekuensi & Biaya) |
| :--- | :--- | :--- |
| **Shadow DOM (Closed)** | Isolasi gaya visual dan penangkapan selektor global total; mencegah regresi CSS di skala ribuan developer. | Sulit dilakukan *theming* terpusat dari luar tanpa deklarasi eksplisit CSS Custom Properties (`--var`) atau `::part()`. |
| **CSS Containment (`contain: strict`)** | Browser mengabaikan subtree saat kalkulasi Layout & Paint; menghemat waktu kalkulasi CRP hingga 80%. | Dimensi elemen (`width` dan `height`) harus didefinisikan secara eksplisit; jika tidak, ukuran kontainer runtuh ke nilai 0. |
| **Virtual DOM / Framework Runtime** | Memberikan abstraksi deklaratif yang mudah dipelajari oleh developer junior-mid. | Menambahkan beban alokasi memori JS runtime, parsing overhead (KB size), dan overhead rekonsiliasi VDOM tree. |
| **Vanilla Engine Architecture** | Ukuran bundel nol kilobyte; performa native mentah tercepat yang mungkin dicapai pada peramban. | Membutuhkan disiplin tinggi dari tim *engineering*; rawan kebocoran memori jika developer tidak memahami GC. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Zombie Event Listeners
* **Gejala**: Penggunaan memori (*heap memory allocation*) terus merangkak naik setiap kali komponen antarmuka dibuka dan ditutup, menyebabkan aplikasi melambat (*tab freeze*).
* **Akar Masalah**: Menggunakan fungsi anonim di dalam `addEventListener` tanpa memanggil `removeEventListener` ketika elemen dilepas dari DOM.
* **Pencegahan**:
  ```javascript
  // JELEK: Listener anonim ini tidak akan pernah bisa di-remove
  window.addEventListener('resize', () => this.handleResize());

  // BENAR: Gunakan AbortSignal
  const controller = new AbortController();
  window.addEventListener('resize', () => this.handleResize(), { signal: controller.signal });
  // Saat teardown:
  controller.abort();
  ```

### 10.2 Detached DOM Tree Leak
* **Gejala**: Elemen HTML telah dihapus dari antarmuka visual, tetapi Profiler DevTools menunjukkan jutaan byte memori tertahan di objek `Detached HTMLDivElement`.
* **Akar Masalah**: Terdapat variabel global, array statis, atau closure yang masih menyimpan referensi ke node DOM tersebut.
* **Solusi**: Gunakan struktur data `WeakRef` atau `WeakMap` untuk memetakan metadata ke node DOM, sehingga *Garbage Collector* dapat membersihkannya saat node dilepas.

### 10.3 Debugging Menggunakan Chrome DevTools
1. **Performance Tab**: 
   * Tekan tombol Record. Lakukan interaksi.
   * Amati baris **Main**: Bar berwarna merah dengan segitiga merah di pojok kanan atas menandakan **Long Task (> 50ms)**.
   * Klik tab bawah **Bottom-Up**: Urutkan berdasarkan *Self Time* untuk melacak fungsi JS murni mana yang memakan waktu eksekusi CPU terbanyak.
2. **Memory Tab (Heap Snapshot)**:
   * Ambil *Snapshot 1*. Lakukan aksi (buka modal/tabel).
   * Tutup modal/tabel. Lakukan aksi Garbage Collection (ikon tong sampah di DevTools).
   * Ambil *Snapshot 2*.
   * Ubah dropdown dari "Summary" ke "Comparison". Filter berdasarkan string `Detached`. Jika nilainya > 0, terjadi kebocoran memori pada komponen tersebut.

---

## 11. Best Practices & Production Checklist

### Kategori Arsitektur & Performa Render
- [ ] Terapkan CSS `contain: content` atau `contain: layout style paint` pada daftar/komponen independen berulang.
- [ ] Hindari pembacaan properti geometri visual (seperti `.getBoundingClientRect()`, `.clientHeight`, `.scrollTop`) langsung sebelum operasi mutasi CSS.
- [ ] Alokasikan animasi visual secara ketat hanya pada dua properti: `transform` dan `opacity` untuk menghindari pemicuan layout engine.
- [ ] Gunakan `IntersectionObserver` untuk memuat gambar (*lazy-loading*) atau mengeksekusi logika hanya saat elemen terlihat di viewport.

### Kategori Isolasi Kode & Manajemen Memori
- [ ] Komponen native harus membungkus seluruh styling di dalam Shadow DOM agar tidak terjadi pencemaran CSS global.
- [ ] Hubungkan penghancuran resource/teardown event listeners dengan siklus `disconnectedCallback` pada Custom Elements.
- [ ] Hindari menyimpan referensi DOM langsung di dalam *state stores* global.

### Kategori Production Bundling & Network
- [ ] Konfigurasi kompresi Brotli level 11 untuk berkas statis saat proses build.
- [ ] Pastikan seluruh aset JavaScript eksternal dideklarasikan menggunakan atribut `<script type="module">` atau atribut `defer`.
- [ ] Atur *Cache-Control* berkas statis dengan hashing menjadi: `public, max-age=31536000, immutable`.

---

## 12. Hands-on Practice: Membangun Reactive Mini-Virtual Data Table

Simpan seluruh file praktikum ini ke dalam direktori: `hands-on/m02/`.

### Struktur Direktori:
```
hands-on/m02/
├── index.html
├── styles.css
└── app.js
```

### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Performance Sandbox</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <h1>Financial Data Stream Controller</h1>
    <div class="actions">
      <button id="btn-stress-bad">Jank Trigger (Naive DOM)</button>
      <button id="btn-stress-good">Performant Stream (Engine Batch)</button>
      <button id="btn-clear">Clear Data</button>
    </div>
    <div id="fps-counter">FPS: --</div>
  </header>

  <main>
    <section class="viewport-box">
      <h3>Active Render Target</h3>
      <div id="data-container" class="data-grid"></div>
    </section>
  </main>

  <script type="module" src="app.js"></script>
</body>
</html>
```

### File: `hands-on/m02/styles.css`
```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
  background-color: #0b0f19;
  color: #e2e8f0;
  padding: 24px;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #1e293b;
  padding-bottom: 16px;
  margin-bottom: 24px;
}

.actions {
  display: flex;
  gap: 12px;
}

button {
  background-color: #1e293b;
  color: #f8fafc;
  border: 1px solid #334155;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: background-color 0.2s;
}

button:hover {
  background-color: #334155;
}

#btn-stress-bad {
  border-color: #ef4444;
  color: #fca5a5;
}

#btn-stress-good {
  border-color: #22c55e;
  color: #86efac;
}

#fps-counter {
  font-size: 1.25rem;
  font-weight: 700;
  color: #38bdf8;
  min-width: 100px;
  text-align: right;
}

.viewport-box {
  background: #111827;
  border: 1px solid #1f2937;
  border-radius: 8px;
  padding: 16px;
}

.data-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  max-height: 600px;
  overflow-y: auto;
  contain: content; /* Isolasi internal engine layouting */
}

.cell {
  background: #1e293b;
  padding: 12px;
  border-radius: 4px;
  border-left: 4px solid #64748b;
  font-size: 0.85rem;
}

.cell.up {
  border-left-color: #22c55e;
}

.cell.down {
  border-left-color: #ef4444;
}
```

### File: `hands-on/m02/app.js`
```javascript
/**
 * Hands-on Practice: Perbandingan Langsung Mutasi Naif vs. Performant Engine
 */

const container = document.getElementById('data-container');
const btnStressBad = document.getElementById('btn-stress-bad');
const btnStressGood = document.getElementById('btn-stress-good');
const btnClear = document.getElementById('btn-clear');
const fpsDisplay = document.getElementById('fps-counter');

// 1. Real-Time FPS Tracker
let frameCount = 0;
let lastTime = performance.now();

function trackFPS(now) {
  frameCount++;
  if (now - lastTime >= 1000) {
    const fps = Math.round((frameCount * 1000) / (now - lastTime));
    fpsDisplay.textContent = `FPS: ${fps}`;
    fpsDisplay.style.color = fps < 30 ? '#ef4444' : fps < 55 ? '#f59e0b' : '#22c55e';
    frameCount = 0;
    lastTime = now;
  }
  requestAnimationFrame(trackFPS);
}
requestAnimationFrame(trackFPS);

// Data Mock Generator
function generateChunk(count) {
  const items = [];
  for (let i = 0; i < count; i++) {
    const isUp = Math.random() > 0.5;
    items.push({
      id: Math.floor(Math.random() * 1000000),
      symbol: `TICK-${Math.floor(Math.random() * 900 + 100)}`,
      val: (Math.random() * 1000).toFixed(2),
      status: isUp ? 'up' : 'down'
    });
  }
  return items;
}

// 2. NAIVE IMPLEMENTATION (Pemicu Frame Drop / Forced Reflows)
btnStressBad.addEventListener('click', () => {
  const items = generateChunk(3000);
  
  // Ini mensimulasikan pendekatan buruk: membaca layout dan menulis langsung ke DOM berkali-kali
  items.forEach(item => {
    const div = document.createElement('div');
    div.className = `cell ${item.status}`;
    div.innerHTML = `<strong>${item.symbol}</strong><br/>${item.val}`;
    container.appendChild(div);

    // BACA GEOMETRI SETELAH SETIAP INSERTION (FORCED REFLOW BENCANA BESAR)
    const forcedHeight = container.offsetHeight;
    div.style.opacity = forcedHeight > 0 ? "1" : "0.5";
  });
});

// 3. OPTIMIZED IMPLEMENTATION (Engine Batching & Clean Virtualization Approach)
btnStressGood.addEventListener('click', () => {
  const items = generateChunk(3000);

  // Pisahkan sepenuhnya antara perhitungan dan render
  // Gunakan DocumentFragment untuk meminimalkan keterlibatan Main Thread
  window.requestAnimationFrame(() => {
    const fragment = document.createDocumentFragment();

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const div = document.createElement('div');
      div.className = `cell ${item.status}`;
      
      // Gunakan textContent jika tidak membutuhkan parsing HTML kompleks
      const strong = document.createElement('strong');
      strong.textContent = item.symbol;
      
      const textNode = document.createTextNode(`: ${item.val}`);
      
      div.appendChild(strong);
      div.appendChild(textNode);
      fragment.appendChild(div);
    }

    // Satu kali mutasi layout tree
    container.appendChild(fragment);
  });
});

btnClear.addEventListener('click', () => {
  // Penghapusan bersih memory safe
  container.replaceChildren();
});
```

---

## 13. Exercises

### Level Easy
Ubah implementasi DOM manipulation berikut agar tidak memicu pemanggilan *Layout/Reflow* ganda pada elemen:
```javascript
// Soal
function applyBoxSizes(boxElements) {
  boxElements.forEach(box => {
    const h = box.clientHeight;
    box.style.height = (h * 1.5) + 'px';
  });
}
```
*Tugas Anda*: Tulis ulang fungsi di atas menggunakan pemisahan fase *Read* dan *Write* secara terpisah.

### Level Medium
Buat sebuah kelas JavaScript native bernama `DOMEventQueue` yang menerima fungsi pembaruan DOM visual dari berbagai komponen dan mengeksekusi semua pembaruan tersebut hanya di dalam satu frame visual `requestAnimationFrame` secara otomatis (*auto-coalescing*). Pastikan fungsi yang didaftarkan duplikat diabaikan.

### Level Hard
Buat komponen kustom native `<virtual-scroller>` berbasis *Web Components* yang mampu memuat 100.000 data array tanpa mengalami peningkatan memori peramban secara linear. Komponen hanya boleh me-render elemen DOM yang aktif terlihat pada *viewport visible area* (ditambah buffer 3 elemen atas & bawah), serta menghitung dinamika offset posisi elemen menggunakan transformasi CSS GPU (`transform: translateY()`).

---

## 14. Challenges

### Sistem Dashboard Real-Time Multi-Tab dengan Kontrol Memori Ketat
Sebuah bank investasi multinasional membutuhkan dashboard trading terpusat yang berjalan di browser klien. Dashboard ini memiliki kriteria arsitektur ekstrem:
1. **Zero Framework Allowed**: Tidak boleh menggunakan React, Vue, Angular, mau pun Svelte. Seluruh kode harus berbasis standar ECMAScript murni dan Web Components.
2. **Backpressure Handler**: Jika koneksi WebSocket mengirimkan lonjakan data 500 pesan per detik sementara hardware monitor klien dibatasi pada 60Hz, sistem antarmuka tidak boleh mengalami keterlambatan (*lag accumulation*) atau memory leak.
3. **Cross-Tab Synchronization**: Data yang diterima oleh Tab Utama (*Leader Tab*) harus disalurkan ke Tab Lainnya (*Worker Tabs*) melalui `BroadcastChannel` atau `SharedWorker` tanpa menduplikasi koneksi socket.
4. **Memory Guard**: Jika pemakaian memori internal heap (`performance.memory.usedJSHeapSize`) terdeteksi melampaui batas kritis 250MB, sistem harus secara deterministik memangkas riwayat cache DOM yang tidak aktif menggunakan algoritma pembersihan LRU (Least Recently Used) tanpa memicu interupsi visual bagi pengguna.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Basic Level (5 Soal)

#### Q1: Urutan yang benar dari alur Critical Rendering Path (CRP) peramban adalah...
* A. CSSOM -> DOM -> Paint -> Layout -> Composite
* B. DOM -> CSSOM -> Render Tree -> Layout -> Paint -> Composite
* C. Layout -> DOM -> CSSOM -> Paint -> Composite
* D. Render Tree -> CSSOM -> DOM -> Layout -> Composite
* **Kunci Jawaban**: **B**
* **Penjelasan**: Browser harus mem-parsing HTML menjadi DOM dan CSS menjadi CSSOM, menggabungkannya ke Render Tree, menghitung koordinat fisik di tahap Layout/Reflow, mengubahnya ke representasi piksel di Paint, dan menyerahkannya ke GPU di tahap Compositing.

#### Q2: Mengapa mutasi CSS menggunakan properti `transform` lebih disukai dibandingkan mengubah properti `top` atau `left` untuk animasi?
* A. Properti `transform` selalu memiliki prioritas eksekusi di thread Web Worker.
* B. Properti `transform` memicu Layout dan Paint ulang pada setiap frame CPU.
* C. Properti `transform` dapat dieksekusi langsung oleh GPU pada Compositor Thread tanpa memicu Reflow atau Paint ulang.
* D. Properti `top` dan `left` bukan bagian dari spesifikasi W3C.
* **Kunci Jawaban**: **C**
* **Penjelasan**: Perubahan `top`/`left` membatalkan geometri box model dan memicu siklus Layout -> Paint -> Composite secara berulang pada CPU. Perubahan `transform` langsung ditangani oleh GPU compositor layer tanpa melibatkan CPU untuk kalkulasi layout.

#### Q3: Manakah antrean tugas yang memiliki prioritas eksekusi lebih tinggi tepat setelah Call Stack JavaScript kosong?
* A. Macrotask Queue (`setTimeout`)
* B. Microtask Queue (`Promise.then`, `queueMicrotask`)
* C. Idle Callback Queue (`requestIdleCallback`)
* D. I/O Callback Queue
* **Kunci Jawaban**: **B**
* **Penjelasan**: Event Loop peramban akan selalu menguras habis (*drain*) seluruh antrean Microtask Queue hingga kosong sebelum memproses macrotask berikutnya atau melanjutkan ke fase rendering frame.

#### Q4: Apa fungsi utama deklarasi CSS `contain: content` dalam rekayasa antarmuka performa tinggi?
* A. Mengunci ukuran kontainer agar elemen anak tidak dapat bertambah.
* B. Mengisolasi sub-tree DOM sehingga perubahan layout, style, atau paint di dalamnya tidak merambat ke seluruh halaman dokumen luar.
* C. Mengompresi ukuran berkas CSS yang dimuat oleh komponen secara otomatis.
* D. Memaksa elemen tersebut dirender secara asinkron di dalam Thread Web Worker.
* **Kunci Jawaban**: **B**
* **Penjelasan**: `contain: content` adalah kombinasi dari `contain: layout style paint`. Properti ini memberitahu browser engine bahwa batas visual komponen sepenuhnya tertutup, sehingga browser tidak perlu menghitung ulang layout seluruh halaman (*global reflow*) jika terjadi mutasi di dalamnya.

#### Q5: Bagaimana cara paling aman membersihkan event listener secara serentak tanpa perlu menyimpan referensi fungsi callback asli?
* A. Memanggil `element.removeEventListener()` dengan fungsi anonim kosong.
* B. Mengatur `element.onclick = null`.
* C. Menggunakan objek `AbortController` dan menyematkan parameter `{ signal }` pada opsi listener.
* D. Menghapus elemen induk menggunakan `document.body.innerHTML = ''`.
* **Kunci Jawaban**: **C**
* **Penjelasan**: Opsi `signal` dari `AbortController` memungkinkan pemutusan/pembersihan listener secara instan dan atomik hanya dengan memanggil `controller.abort()`, mencegah timbulnya kebocoran memori dari fungsi closure yang tertahan.

---

### 15.2 Intermediate Level (5 Soal)

#### Q6: Kapan skenario Forced Synchronous Layout (Layout Thrashing) secara deterministik terjadi?
* A. Ketika developer mengimpor berkas CSS berukuran lebih dari 100 Kilobyte.
* B. Ketika JavaScript membaca properti geometri visual (seperti `offsetHeight`) segera setelah menulis perubahan style visual pada DOM.
* C. Ketika pemanggilan `requestAnimationFrame` dilakukan di dalam blok `setTimeout`.
* D. Ketika Web Worker mencoba membaca objek `window.document`.
* **Kunci Jawaban**: **B**
* **Penjelasan**: Peramban biasanya menunda komputasi layout hingga akhir eksekusi task (*lazy layout*). Namun, jika ada kode yang membaca properti geometri saat DOM dalam status *invalid/dirty* akibat penulisan sebelumnya, browser dipaksa mengeksekusi Layout saat itu juga (*synchronous reflow*).

#### Q7: Apa perbedaan mendasar antara *Custom Elements v1* dengan *Shadow DOM* dalam Web Components?
* A. Custom Elements mengelola enkapsulasi CSS, sedangkan Shadow DOM meregistrasi nama tag HTML baru.
* B. Custom Elements meregistrasi tag HTML dan siklus hidupnya, sedangkan Shadow DOM menyediakan enkapsulasi isolasi DOM dan CSS tree.
* C. Shadow DOM hanya dapat berjalan jika menggunakan library lit-element atau Polymer.
* D. Custom Elements hanya dapat dijalankan di node server melalui SSR.
* **Kunci Jawaban**: **B**
* **Penjelasan**: Custom Elements adalah standar untuk mendefinisikan tag HTML baru beserta lifecycle hooks-nya (`connectedCallback`, dll). Shadow DOM adalah standar terpisah untuk mengisolasi struktur DOM internal dan CSS dari jangkauan dokumen utama.

#### Q8: Diberikan kode berikut:
```javascript
Promise.resolve().then(() => console.log('A'));
setTimeout(() => console.log('B'), 0);
queueMicrotask(() => console.log('C'));
window.requestAnimationFrame(() => console.log('D'));
console.log('E');
```
#### Urutan pencetakan log yang benar pada konsol peramban modern adalah...
* A. E -> A -> C -> D -> B (atau E -> A -> C -> B -> D bergantung pada timing frame render)
* B. E -> B -> A -> C -> D
* C. A -> C -> E -> D -> B
* D. E -> A -> B -> C -> D
* **Kunci Jawaban**: **A**
* **Penjelasan**: Eksekusi sinkron (`E`) berjalan pertama. Lalu seluruh antrean microtask dikuras (`A` dan `C`). Selanjutnya, sebelum browser menggambar frame baru atau mengeksekusi macrotask, `requestAnimationFrame` (`D`) dipanggil jika siklus render sinkron, atau macrotask (`B`) dieksekusi di tick loop berikutnya. Jawaban pasti untuk urutan awal adalah `E -> A -> C`.

#### Q9: Mengapa struktur data `WeakMap` sangat krusial dalam arsitektur penanganan cache data yang terikat pada elemen DOM?
* A. Karena `WeakMap` memiliki performa pencarian nilai $O(\log N)$ yang lebih cepat dari objek biasa.
* B. Karena `WeakMap` dapat diurutkan berdasarkan insertion order.
* C. Karena referensi key objek DOM di dalam `WeakMap` bersifat lemah (*weak reference*); jika elemen DOM dihapus dari tree, memori objek tersebut dapat dibersihkan oleh Garbage Collector secara otomatis.
* D. Karena `WeakMap` dapat dibaca secara paralel dari Web Worker thread tanpa race condition.
* **Kunci Jawaban**: **C**
* **Penjelasan**: Pada objek `Map` standar, jika elemen DOM dijadikan key, elemen tersebut tidak akan pernah bisa di-garbage collect meskipun sudah dilepas dari dokumen induk. `WeakMap` mengizinkan GC membersihkan elemen yang tidak terpakai sehingga mencegah *Detached DOM memory leaks*.

#### Q10: Fitur Resource Hint manakah yang menginstruksikan peramban untuk memulai koneksi awal (DNS lookup + TCP Handshake + TLS negotiation) ke server eksternal sebelum permintaan aset riil dilakukan?
* A. `<link rel="preload">`
* B. `<link rel="prefetch">`
* C. `<link rel="preconnect">`
* D. `<link rel="dns-prefetch">`
* **Kunci Jawaban**: **C**
* **Penjelasan**: `preconnect` membuka socket koneksi TCP/TLS lengkap ke origin target. `dns-prefetch` hanya melakukan resolusi IP/DNS. `preload` mengunduh aset spesifik dengan prioritas tinggi, sedangkan `prefetch` mengunduh aset untuk navigasi halaman berikutnya di masa depan.

---

### 15.3 Production Scenarios (3 Skenario Kasus)

#### Q11: Kasus Analisis Crash Produksi
Aplikasi web analitik kesehatan korporat mengalami crash (*tab browser error: Out of Memory*) setelah dibuka selama 3 jam di layar monitor operasional rumah sakit. Saat dilakukan audit Heap Snapshot di DevTools, ditemukan ada 240.000 instans `HTMLParagraphElement` dengan status `Detached` yang tertahan oleh sebuah array internal bernama `subscribers` di dalam singleton object `TelemetryStore`.

Langkah arsitektur yang paling efektif dan tepat sasaran untuk memitigasi isu tersebut secara permanen tanpa merusak fungsionalitas aplikasi adalah:
* A. Mengganti semua elemen HTML paragraf dengan elemen teks SVG murni.
* B. Mengonfigurasi restart halaman otomatis (*window.location.reload()*) setiap 30 menit melalui skrip `setInterval`.
* C. Memutus referensi langsung node DOM dari array internal `TelemetryStore`, menggunakan `WeakSet`/`WeakMap`, atau mewajibkan setiap komponen membatalkan langganan (*unsubscribe*) pada siklus `disconnectedCallback`.
* D. Memperbesar batas virtual memory Chrome melalui flag terminal eksternal pengguna.
* **Kunci Jawaban**: **C**
* **Penjelasan**: Pemicu OOM adalah retensi referensi (*retaining path*) dari objek singleton jangka panjang (`TelemetryStore`) ke elemen DOM yang sebenarnya sudah dilepas dari visual. Solusinya adalah memutuskan referensi kuat (*strong reference*) tersebut dengan implementasi siklus teardown yang deterministik atau struktur data ber-referensi lemah (*weak references*).

#### Q12: Kasus Penalti Metrik Core Web Vitals (INP)
Audit Lighthouse menunjukkan skor performa Core Web Vitals pada metrik Interaction to Next Paint (INP) sebuah toko online bernilai **620ms** (Kategori Buruk). Investigasi menunjukkan bahwa saat pengguna menekan checkbox "Filter Kategori", kode JavaScript mengeksekusi pengurutan 15.000 item katalog secara sinkron di dalam UI thread sebelum mengubah status visual checkbox menjadi tercentang.

Pendekatan rekayasa manakah yang memberikan perbaikan skor INP paling optimal?
* A. Membungkus seluruh logika pengurutan di dalam fungsi `requestAnimationFrame`.
* B. Memindahkan komputasi pengurutan 15.000 item ke latar belakang menggunakan **Web Worker**, lalu segera membiarkan Main Thread meng-update status centang visual checkbox tanpa hambatan.
* C. Mengubah warna tombol checkbox menggunakan CSS `:active` pseudo-class.
* D. Mengalihkan proses rendering daftar barang ke server menggunakan Server-Side Rendering tanpa interaktivitas klien.
* **Kunci Jawaban**: **B**
* **Penjelasan**: INP mengukur responsivitas antarmuka terhadap input pengguna hingga frame visual berikutnya dirender. Menjalankan komputasi berat (15.000 items sorting) di Main Thread memblokir peramban untuk menggambar perubahan centang checkbox. Memindahkan kalkulasi intensif CPU ke Web Worker membebaskan Main Thread sehingga INP dapat langsung dirender di bawah 16ms.

#### Q13: Kasus Flash of Unstyled Content (FOUC) pada Web Components
Sebuah tim frontend enterprise mengadopsi native Web Components. Namun pada jaringan koneksi 3G/4G lambat, pengguna melihat teks polos tanpa gaya selama ~400ms sebelum komponen Custom Element mengunduh CSS-nya dan menampilkan antarmuka akhir secara utuh.

Bagaimana standar industri mengatasi fenomena ini secara native?
* A. Menyembunyikan seluruh body website menggunakan tag `<body style="display:none">` hingga window onload.
* B. Memanfaatkan pseudo-class CSS `:defined` (contoh: `my-card:not(:defined) { display: none; }` atau skeleton placeholder) untuk menyembunyikan atau menampilkan loading layout hingga elemen teregistrasi.
* C. Menghindari penggunaan Shadow DOM dan kembali menggunakan CSS styling global di tag `<head>`.
* D. Memasukkan seluruh kode JavaScript ke dalam atribut HTML `onclick`.
* **Kunci Jawaban**: **B**
* **Penjelasan**: Spesifikasi peramban menyediakan pseudo-class `:defined` yang merepresentasikan elemen yang telah sukses didaftarkan melalui `customElements.define()`. Selector `:not(:defined)` memungkinkan engineer menyematkan kerangka placeholder (*skeleton loader*) yang elegan selama fase parsing aset berlangsung, secara efektif meniadakan efek kejut FOUC.

---

## 16. Summary

1. **Pemahaman Arsitektur Mesin Peramban Adalah Kunci**: Mengembangkan aplikasi web performa tinggi tidak mungkin dicapai tanpa memahami interaksi antara alur eksekusi V8/Gecko Engine dan *Critical Rendering Path* (DOM -> CSSOM -> Layout -> Paint -> Composite).
2. **Kendalikan Layout Thrashing**: Jangan pernah mencampur operasi pembacaan geometri (*read*) dan manipulasi gaya visual (*write*) dalam loop sinkron. Pisahkan fase tersebut menggunakan batching antrean microtask atau `requestAnimationFrame`.
3. **Standar Web Native Menyediakan Isolasi Penuh**: Web Components (Custom Elements v1, Shadow DOM, Template) memberikan kapabilitas enkapsulasi komponen setara atau melampaui framework modern tanpa biaya overhead komputasi bundling runtime eksternal.
4. **Alokasikan Memori Secara Deterministik**: Kebocoran memori pada browser modern sebagian besar disebabkan oleh *Detached DOM Trees* yang masih terikat pada event listener, interval aktif, atau referensi kuat pada struktur data statis. Terapkan pola `AbortController` dan `WeakMap`/`WeakSet` untuk membersihkan dependensi secara atomik.