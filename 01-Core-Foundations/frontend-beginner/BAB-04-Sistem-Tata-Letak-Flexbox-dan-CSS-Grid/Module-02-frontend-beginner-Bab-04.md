# BAB 04: Materi Lanjutan
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis Internal Browser Engine**: Menguraikan siklus *Critical Rendering Path* (CRP) tingkat lanjut, mekanisme eksekusi *JavaScript Event Loop* (microtask vs macrotask queue), serta implikasi *hardware-accelerated compositing* pada performa rendering DOM.
2. **Merancang State Orchestrator Mandiri**: Mengimplementasikan arsitektur state management deterministik berskala enterprise menggunakan *Proxy-based reactivity*, *Command-Query Separation* (CQS), dan *immutable data pipeline* tanpa dependensi eksternal.
3. **Membangun Network Resiliency Layer**: Menyusun *production-grade data-fetching layer* yang mengintegrasikan pembatalan operasi berbasis `AbortController`, *exponential backoff jitter*, *request deduplication*, dan *stale-while-revalidate caching*.
4. **Mencegah & Mengeliminasi Memory Leaks**: Mengidentifikasi dan memitigasi kebocoran alokasi heap browser menggunakan *Chrome DevTools Memory Profiler*, siklus hidup *detached DOM nodes*, serta referensi memori dengan `WeakMap` dan `WeakRef`.
5. **Menerapkan Production Observability**: Membangun telemetri sisi klien untuk melacak metrik *Core Web Vitals* (LCP, INP, CLS) dan *real-user monitoring* (RUM) dengan *error tracking instrumentation*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer harus memahami:
- **JavaScript Core & ESNext**: Execution Context, Lexical Scope, Closure, Event Loop dasar, Promise chaining, `async/await`, dan manipulasi objek lanjutan (`Object.defineProperty`, `Reflect`).
- **DOM & Web APIs**: DOM Tree traversal dasar, Event Bubbling/Capturing, Fetch API, `localStorage`/`sessionStorage`.
- **Dasar Rekayasa Web**: Konsep HTTP/1.1 vs HTTP/2/3, RESTful design patterns, semantic HTML5, dan CSS Box Model.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Browser Engine Internals: Critical Rendering Path & Compositing Engine

Arsitektur browser modern (seperti Chromium dengan engine Blink dan V8) memproses dokumen melalui *pipeline* deterministik multi-tahap:

```
HTML/CSS Raw Bytes 
  │
  ▼
[Tokenization & Parsing] ──► DOM Tree + CSSOM Tree
                                  │
                                  ▼
                            [Render Tree] (Hanya node yang visible)
                                  │
                                  ▼
                              [Layout] (Hitung geometri: x, y, width, height)
                                  │
                                  ▼
                              [Paint] (Rasterization: pengisian piksel warna)
                                  │
                                  ▼
                            [Composite] (Layer assembly di GPU)
```

1. **DOM & CSSOM Construction**:
   HTML Parser membaca aliran biner (*stream of bytes*), mengonversinya menjadi token (Tokenization), membangun simpul objek (*Node*), dan membentuk struktur pohon *Document Object Model* (DOM). Secara paralel, CSS diurai menjadi *CSS Object Model* (CSSOM). Kedua proses ini bersifat *render-blocking*.

2. **Render Tree**:
   Engine menggabungkan DOM dan CSSOM untuk menyusun Render Tree. Elemen dengan aturan `display: none` diabaikan sepenuhnya dari Render Tree, sedangkan elemen dengan `visibility: hidden` tetap dimasukkan karena masih memakan ruang geometris.

3. **Layout (Reflow)**:
   Engine menghitung dimensi geometris dan koordinat absolut setiap node. Perhitungan ini bergantung pada ukuran viewport.
   * *Layout Thrashing (Forced Synchronous Layout)*: Terjadi ketika JavaScript membaca properti geometris (`offsetHeight`, `clientWidth`, `getBoundingClientRect()`) segera setelah mengubah style DOM, memaksa browser menghentikan pipeline JS untuk menghitung ulang layout secara sinkron di tengah frame.

4. **Paint & Raster**:
   Mengonversi pohon render menjadi perintah menggambar visual (piksel). Paint memisahkan elemen ke dalam beberapa layer visual (*compositing layers*) jika elemen tersebut memiliki pemicu layer khusus (seperti CSS `will-change`, `transform: translateZ(0)`, atau elemen `<video>`).

5. **Compositing**:
   Layer-layer independen dikirimkan ke GPU (*Graphical Processing Unit*) untuk digabungkan menjadi satu frame utuh pada layar (*Tiling and Rasterization via GPU threads*). Perubahan pada properti `transform` dan `opacity` melewati tahap Layout dan Paint, langsung menuju Compositing, menghasilkan performa animasi 60/120 FPS tanpa frame drop.

---

#### B. JavaScript Event Loop: Microtasks, Macrotasks, dan Frame Rendering Phases

Arsitektur concurrency pada thread utama (Main Thread) browser bekerja secara berurutan:

```
┌────────────────────────────────────────────────────────┐
│                      Call Stack                        │
└───────────────────────────┬────────────────────────────┘
                            │ (Stack Empty)
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Microtask Queue                      │
│   (Promise, queueMicrotask, MutationObserver)          │
│   *Dihabiskan SELURUHNYA sampai queue kosong*          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Render Steps                         │
│   1. requestAnimationFrame (rAF) callbacks             │
│   2. Recalculate Style & Layout                        │
│   3. Paint & Composite                                 │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                   Macrotask Queue                      │
│   (setTimeout, setInterval, postMessage, I/O)          │
│   *Hanya dijalankan 1 task per loop cycle*             │
└────────────────────────────────────────────────────────┘
```

Jika sebuah Microtask secara rekursif mendaftarkan microtask baru, ia akan memblokir (*starve*) Render Steps dan Macrotasks, menyebabkan antarmuka pengguna menjadi *unresponsive* (*Jank*).

---

#### C. Arsitektur State: Observer & Reactive Proxy

Arsitektur state modern enterprise menghindari mutasi DOM langsung. Kita memisahkan *State Layer* dari *View Layer* menggunakan *Reactivity Graph*.

```
  [User Interaction / Event]
              │
              ▼
  [Action / Command Dispatcher]
              │
              ▼
    [Proxy Trap Handler] ───► (Intersepsi set, get, deleteProperty)
              │
              ▼
      [State Mutation] ─────► (Simpan state baru, buat freeze/snapshot)
              │
              ▼
     [Dependency Tracker] ───► (Notifikasi Subscribers / UI Elements)
              │
              ▼
       [Batch Render]  ─────► (Dijadwalkan via queueMicrotask/rAF)
```

Dengan memanfaatkan `Proxy` dan `Reflect`, setiap mutasi properti ditangkap secara deterministik, dependensi dikumpulkan saat evaluasi nilai (*getter dependency injection*), dan antarmuka diperbarui secara terkelompok (*batching*) guna menghindari re-render yang redundan.

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Vanilla Imperatif) | Pendekatan Enterprise (Arsitektur Lanjutan) |
| :--- | :--- | :--- |
| **State Tracking** | Membaca/menulis status langsung ke innerText / DOM data-attribute. | Single Source of Truth (SSOT) terisolasi menggunakan Reactive Store berbasis Proxy. |
| **Rendering** | Manipulasi DOM sinkron berulang kali, rentan *Layout Thrashing*. | Asynchronous Batch Rendering memanfaatkan microtask scheduler dan rAF. |
| **Network** | Pemanggilan `fetch` tanpa kontrol, resiko race condition & overhead memori. | Resilient API Client dengan timeout, request deduplication, dan AbortController. |
| **Memory Lifecycle**| Event listener global tidak pernah dilepas; referensi sirkular. | Explicit teardown, cleanup patterns, dan pengelolaan referensi lemah via `WeakMap`. |
| **Resilience & Telemetry**| `console.log` dan `try/catch` sporadis tanpa monitoring. | Global Error Boundary, sanitasi data, serta instrumen Real-User Monitoring (RUM). |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur frontend tingkat lanjut yang berorientasi produksi:

```
[1. Request Cycle]
   Client -> Deduplication Check -> Cache Verification -> Network Execution (with AbortSignal & Jitter Backoff)

[2. State Resolution Cycle]
   Network Payload -> Schema Validation/Sanitization -> Dispatch Mutator -> Proxy Interception -> Dependency Notification

[3. Batching & DOM Scheduling Cycle]
   Queue Notification -> Batch Collector (Microtask) -> Compute Minimal DOM Changes -> Schedule rAF -> Paint/Composite

[4. Diagnostics & Teardown Cycle]
   Measure Timings (Performance API) -> Push Observability Telemetry -> Trigger Component Teardown (Unbind listeners, drop WeakMaps)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Arsitektur
Bayangkan restoran bintang lima:
- **Imperatif (Naif)**: Tamu memesan langsung ke koki. Setiap kali ada permintaan garam, koki meninggalkan kompor, berlari ke pasar membeli garam, kembali memasak, lalu menghidangkan sepiring kecil. Dapur menjadi kacau (Layout Thrashing), waktu saji tak terprediksi.
- **Enterprise-Grade (Arsitektur Terkelola)**: Pelayan mencatat pesanan dalam buku log pusat (State Store). Koki menerima rekapitulasi pesanan dalam siklus tertentu (Batch Rendering via Event Loop). Jika ada dua tamu memesan hidangan yang sama secara bersamaan, pesanan digabung menjadi satu sesi memasak (Request Deduplication). Bahan cadangan disimpan di dapur darurat (Cache/Network Resiliency Layer).

#### Diagram Internal Memory Lifecycle & Event Loop Scheduler

```
+-------------------------------------------------------------------------+
|                              MAIN THREAD                                |
|                                                                         |
|  +---------------------+        +------------------------------------+  |
|  |     CALL STACK      |        |          REACTIVE STORE            |  |
|  |                     |        |                                    |  |
|  | fnA()               |        |  Proxy Target: { count: 0 }        |  |
|  |  └─> fnB() [Set]    |------->|  Handler.set()                     |  |
|  +---------------------+        |   └─> triggerSubscribers()         |  |
|                                 +------------------┬-----------------+  |
|                                                    |                    |
|                                                    v                    |
|  +-------------------------------------------------------------------+  |
|  |                        MICROTASKS QUEUE                           |  |
|  |  [Task 1: Batch Flush] -> [Task 2: State Resolution]              |  |
|  +---------------------------------┬---------------------------------+  |
|                                    | (When drained)                     |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  |                 ANIMATION / RENDER STEP (V-SYNC)                  |  |
|  |  rAF: Apply DOM Mutations (Fast Transforms, Class Toggles)        |  |
|  |  Recalculate Style -> Layout -> Paint -> GPU Composite            |  |
|  +---------------------------------┬---------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  |                         MACROTASK QUEUE                           |  |
|  |  [setTimeout Handler] -> [I/O Callback]                           |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Menghindari Forced Synchronous Layout (Layout Thrashing)

##### Kode Buruk (Memicu Thrashing):
```javascript
// Buruk: Siklus Interleaved Read-Write memicu Reflow berulang kali
function resizeBoxesBad(boxes) {
  for (let i = 0; i < boxes.length; i++) {
    // READ (Layout paksa sinkron)
    const currentWidth = boxes[i].offsetWidth; 
    // WRITE (Menandai layout menjadi kotor/invalid)
    boxes[i].style.width = `${currentWidth + 10}px`; 
  }
}
```

##### Kode Bersih Standar Industri:
```javascript
// Bersih: Pisahkan Fase Read dan Fase Write (Batching)
function resizeBoxesOptimized(boxes) {
  // Fase 1: READ semua metrik geometri secara bersamaan
  const widths = boxes.map((box) => box.offsetWidth);

  // Fase 2: Jadwalkan WRITE pada frame render berikutnya
  requestAnimationFrame(() => {
    boxes.forEach((box, index) => {
      box.style.width = `${widths[index] + 10}px`;
    });
  });
}
```

---

#### B. Practical Example: Enterprise-Grade Resilient State Store & Fetch Engine

Berikut adalah implementasi *Single-Module Architecture* yang memadukan Proxy Reactivity, Batch Scheduler, dan Resilient Network Client dengan standar *strict TypeScript-style ESNext*.

```javascript
/**
 * @file EnterpriseCoreArchitecture.js
 * Modul terintegrasi: Batch Scheduler, Reactive State, dan Resilient Network Client.
 */

// ============================================================================
// 1. ASYNCHRONOUS MICROTASK BATCH SCHEDULER
// ============================================================================
class BatchScheduler {
  static #queue = new Set();
  static #isFlushing = false;

  /**
   * Menjadwalkan fungsi callback agar dieksekusi secara batch dalam microtask queue.
   * @param {Function} job 
   */
  static schedule(job) {
    this.#queue.add(job);
    if (!this.#isFlushing) {
      this.#isFlushing = true;
      queueMicrotask(() => this.#flush());
    }
  }

  static #flush() {
    try {
      for (const job of this.#queue) {
        job();
      }
    } finally {
      this.#queue.clear();
      this.#isFlushing = false;
    }
  }
}

// ============================================================================
// 2. OBSERVABLE & DETERMINISTIC REACTIVE STORE
// ============================================================================
export class ReactiveStore {
  #state;
  #subscribers = new Map(); // Map<string, Set<Function>>

  /**
   * @param {Record<string, any>} initialState 
   */
  constructor(initialState = {}) {
    this.#state = this.#createProxy(initialState);
  }

  #createProxy(target) {
    const self = this;
    return new Proxy(target, {
      get(obj, prop) {
        return Reflect.get(obj, prop);
      },
      set(obj, prop, value) {
        const oldValue = obj[prop];
        if (oldValue === value) return true;

        const success = Reflect.set(obj, prop, value);
        if (success) {
          self.#notify(String(prop));
        }
        return success;
      }
    });
  }

  #notify(key) {
    const listeners = this.#subscribers.get(key);
    if (!listeners || listeners.size === 0) return;

    listeners.forEach((callback) => {
      // Jadwalkan update melalui batch scheduler agar UI tidak re-render berlebihan
      BatchScheduler.schedule(() => callback(this.#state[key]));
    });
  }

  /**
   * Berlangganan perubahan properti spesifik. Mengembalikan fungsi unsubscriber (cleanup).
   * @param {string} key 
   * @param {Function} callback 
   * @returns {() => void}
   */
  subscribe(key, callback) {
    if (!this.#subscribers.has(key)) {
      this.#subscribers.set(key, new Set());
    }
    this.#subscribers.get(key).add(callback);

    // Initial invocation (Reactivity Baseline)
    callback(this.#state[key]);

    return () => {
      const set = this.#subscribers.get(key);
      if (set) {
        set.delete(callback);
        if (set.size === 0) this.#subscribers.delete(key);
      }
    };
  }

  get state() {
    return this.#state;
  }
}

// ============================================================================
// 3. RESILIENT NETWORK CLIENT (Deduplication, Abort, Exponential Backoff)
// ============================================================================
export class ResilientNetworkClient {
  #inflightRequests = new Map();

  /**
   * Eksekusi HTTP Request dengan proteksi otomatis.
   * @param {string} url 
   * @param {RequestInit & { maxRetries?: number, timeoutMs?: number }} options 
   */
  async request(url, options = {}) {
    const { maxRetries = 3, timeoutMs = 8000, ...fetchOptions } = options;
    const requestKey = `${fetchOptions.method || 'GET'}:${url}`;

    // Request Deduplication Pattern: Jika request identik sedang berjalan, gunakan Promise yang sama
    if (this.#inflightRequests.has(requestKey)) {
      return this.#inflightRequests.get(requestKey);
    }

    const promise = this.#executeWithRetry(url, fetchOptions, maxRetries, timeoutMs)
      .finally(() => {
        this.#inflightRequests.delete(requestKey);
      });

    this.#inflightRequests.set(requestKey, promise);
    return promise;
  }

  async #executeWithRetry(url, fetchOptions, retriesLeft, timeoutMs) {
    let attempt = 0;
    
    while (attempt <= retriesLeft) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      // Gabungkan external signal jika ada
      const combinedSignal = fetchOptions.signal
        ? this.#anySignal([fetchOptions.signal, controller.signal])
        : controller.signal;

      try {
        const response = await fetch(url, {
          ...fetchOptions,
          signal: combinedSignal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP_${response.status}: ${response.statusText}`);
        }

        return await response.json();
      } catch (err) {
        clearTimeout(timeoutId);
        attempt++;

        const isAbort = err.name === 'AbortError';
        const isClientError = err.message.startsWith('HTTP_4');

        // Jangan retry jika error disebabkan user abort atau client error (4xx)
        if (attempt > retriesLeft || isAbort || isClientError) {
          throw err;
        }

        // Full Jitter Exponential Backoff: t = random_between(0, min(cap, base * 2 ^ attempt))
        const baseDelay = 300;
        const maxDelay = 4000;
        const exponentialDelay = Math.min(maxDelay, baseDelay * (2 ** attempt));
        const jitterDelay = Math.floor(Math.random() * exponentialDelay);

        await new Promise((resolve) => setTimeout(resolve, jitterDelay));
      }
    }
  }

  #anySignal(signals) {
    const controller = new AbortController();
    for (const signal of signals) {
      if (signal.aborted) {
        controller.abort();
        return signal;
      }
      signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
    return controller.signal;
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Dashboard Finansial Latensi Rendah (Real-Time Trading Desk)
* **Skala Sistem**: 100 instrumen finansial diperbarui setiap 100ms via WebSockets. Dashboard memuat 50 grafik canvas, 1 order-book DOM view, dan summary portofolio.
* **Insiden Produksi**:
  Setelah deployment, metrik *Interaction to Next Paint* (INP) melonjak hingga **1.400 ms** (kategori *Poor*). Konsumsi memori browser meningkat drastis hingga 1,8 GB dalam 30 menit, memicu crash browser tab (*Out of Memory* / Aw, Snap!).
* **Root Cause Analysis (RCA)**:
  1. *Layout Thrashing*: Order-book merender ulang baris tabel secara sinkron menggunakan `element.innerHTML` pada setiap packet WebSocket, diikuti pemanggilan `window.scrollTo()` untuk mengunci posisi kursor.
  2. *Retained DOM Nodes Memory Leak*: Komponen grafik mendaftarkan event listener pada `window.resize` tanpa pernah menghapusnya saat instrumen ditutup/dihapus oleh user. Object reference tersimpan di closure global.
* **Arsitektur Solusi & Resolusi**:
  1. *State Decoupling*: Pembaruan WebSocket diarahkan ke sebuah *In-Memory Double-Buffered Array*. State tidak langsung memicu rendering DOM, melainkan ditampung (*accumulated*).
  2. *Render Loop Alignment*: Komponen antarmuka menggunakan `requestAnimationFrame` tunggal untuk membaca state hasil agregasi setiap 16.6ms (target 60 FPS), menghilangkan fluktuasi layout sinkron.
  3. *Weak References & Destruction Life Cycle*: Mengalihkan manajemen listener grafik ke pola `AbortController.signal` terpadu. Ketika modul ditutup, controller membatalkan (`abort()`) seluruh event listeners dan WebSockets sekaligus, memastikan alokasi heap langsung dibersihkan oleh Garbage Collector V8.
* **Hasil Metrik**:
  - INP turun dari 1.400 ms menjadi **38 ms**.
  - Alokasi Heap Memory stabil di kisaran **45 MB - 60 MB** secara konstan selama pengujian stres 8 jam nonstop.

---

### 9. Trade-offs

Mengadopsi pola enterprise ini menghadirkan trade-off rekayasa yang harus dipertimbangkan:

| Aspek | Sisi Positif (Advantage) | Sisi Negatif (Cost / Trade-off) |
| :--- | :--- | :--- |
| **Proxy State Reactivity** | - Mutasi transparan.<br>- Fine-grained updates tanpa re-render pohon komponen global. | - Alokasi awal objek Proxy memiliki overhead CPU kecil dibanding objek POJO murni.<br>- Struktur data bersarang membutuhkan *deep proxying* yang menambah kompleksitas memori. |
| **Microtask Batching** | - Menghilangkan redundant paint cycles.<br>- Mempertahankan FPS tinggi. | - Terdapat latensi minimal (1 microtask tick) sebelum perubahan terefleksi di DOM; tidak cocok untuk kebutuhan layout yang membutuhkan sinkronisasi instan absolut. |
| **Request Deduplication & Jitter** | - Mengurangi beban server drastis.<br>- Mencegah *Thundering Herd Problem* pasca-downtime. | - Membutuhkan pengelolaan *in-flight promise lifecycle* yang teliti.<br>- Resiko data basi jika mutation request di-deduplicate secara keliru. |
| **Strict Lifecycle Cleanup** | - Garansi eliminasi memory leak 100%.<br>- Prediktabilitas aplikasi long-running. | - Tambahan boilerplate kode (`teardown()`, `dispose()`, `signal`).<br>- Menuntut disiplin kode tim yang sangat ketat. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Circular Object Proxy Trap Recursion
* **Gejala**: `RangeError: Maximum call stack size exceeded` saat memutasi state.
* **Penyebab**: Mutasi state dilakukan di dalam subscriber yang mendengarkan properti yang sama tanpa guard clause.
* **Solusi**:
```javascript
// SOLUSI: Periksa kesamaan nilai sebelum men-trigger reaksi
set(obj, prop, value) {
  if (Object.is(obj[prop], value)) return true; // Guard
  return Reflect.set(obj, prop, value);
}
```

#### 2. Detached DOM Tree Memory Leak
* **Gejala**: Memory snapshot heap terus bertambah meskipun elemen HTML telah dihapus dari antarmuka via `.remove()`.
* **Penyebab**: Masih ada variabel JavaScript atau closure yang menyimpan referensi ke elemen DOM tersebut.
* **Deteksi via Chrome DevTools**:
  1. Buka tab **Memory** -> Pilih **Heap Snapshot** -> Klik **Take Snapshot**.
  2. Lakukan interaksi create/destroy komponen di aplikasi.
  3. Ambil Snapshot kedua -> Filter hasil berdasarkan string: `"Detached"`.
  4. Amati node berwarna kuning/merah (*Retaining paths*).
* **Solusi**: Setel variabel referensi elemen ke `null` atau gunakan `WeakMap` untuk mengasosiasikan metadata dengan node DOM.

#### 3. Zombie Listeners pada Global Targets
* **Gejala**: Event handler tetap berjalan dan mengakses state komponen yang sudah dimusnahkan.
* **Solusi**: Gunakan `AbortController` terpadu untuk meregistrasi multi-event listener.
```javascript
class ResilientView {
  #abortController = new AbortController();

  mount() {
    const { signal } = this.#abortController;
    window.addEventListener('resize', this.onResize, { signal });
    window.addEventListener('scroll', this.onScroll, { signal });
  }

  unmount() {
    // Sekali eksekusi, membatalkan SEMUA listener yang terikat pada signal ini
    this.#abortController.abort();
  }
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **DOM Read/Write Isolation**: Jangan pernah memanggil fungsi pembaca geometri layout (`offsetWidth`, `getBoundingClientRect()`) setelah melakukan penulisan style (`style.top`, `classList.add()`) dalam siklus frame yang sama.
- [ ] **Use Hardware Compositing Wisely**: Batasi penggunaan `will-change: transform` hanya pada elemen yang secara dinamis dan aktif mengalami animasi, guna mencegah alokasi VRAM berlebihan di GPU.
- [ ] **Explicit Resource Disposal**: Setiap modul yang mendaftarkan event listener, timer (`setInterval`), atau koneksi streaming (SSE, WebSocket) wajib menyediakan method eksplisit `destroy()` atau `dispose()`.
- [ ] **Deterministic Fetching**: Seluruh *data fetching* sisi klien wajib menyertakan batas waktu (*timeout*) via `AbortSignal.timeout()` dan mitigasi kegagalan jaringan via *jittered backoff*.
- [ ] **Sanitize Before Render**: Seluruh data yang masuk ke pipeline DOM wajib melewati proses sanitasi (misal via *DOMPurify*) sebelum diinjeksikan ke template HTML.
- [ ] **Memory Baseline Assertions**: Lakukan pengujian memori terotomasi menggunakan Puppeteer / Playwright dengan memeriksa `performance.memory.usedJSHeapSize`.

---

### 12. Hands-on Practice

Simpan berkas-berkas berikut di dalam direktori `hands-on/m02/`.

#### Struktur Direktori:
```
hands-on/m02/
├── index.html
├── src/
│   ├── app.js
│   ├── core/
│   │   ├── scheduler.js
│   │   ├── store.js
│   │   └── client.js
│   └── components/
│       └── metrics-widget.js
└── styles/
    └── main.css
```

#### Langkah Implementasi:

##### 1. `hands-on/m02/src/core/scheduler.js`
```javascript
export class BatchScheduler {
  static #jobs = new Set();
  static #isScheduled = false;

  static enqueue(fn) {
    this.#jobs.add(fn);
    if (!this.#isScheduled) {
      this.#isScheduled = true;
      queueMicrotask(() => {
        try {
          this.#jobs.forEach((job) => job());
        } finally {
          this.#jobs.clear();
          this.#isScheduled = false;
        }
      });
    }
  }
}
```

##### 2. `hands-on/m02/src/core/store.js`
```javascript
import { BatchScheduler } from './scheduler.js';

export function createStore(initialState) {
  const subscribers = new Map();

  const state = new Proxy(initialState, {
    set(target, prop, value) {
      if (Object.is(target[prop], value)) return true;
      const success = Reflect.set(target, prop, value);
      if (success && subscribers.has(prop)) {
        subscribers.get(prop).forEach((callback) => {
          BatchScheduler.enqueue(() => callback(target[prop]));
        });
      }
      return success;
    }
  });

  function subscribe(prop, callback) {
    if (!subscribers.has(prop)) {
      subscribers.set(prop, new Set());
    }
    subscribers.get(prop).add(callback);
    callback(state[prop]); // Baseline invocation

    return () => {
      const listeners = subscribers.get(prop);
      if (listeners) {
        listeners.delete(callback);
      }
    };
  }

  return { state, subscribe };
}
```

##### 3. `hands-on/m02/src/core/client.js`
```javascript
export class ApiClient {
  #dedupeMap = new Map();

  async get(url, { timeoutMs = 5000 } = {}) {
    if (this.#dedupeMap.has(url)) {
      return this.#dedupeMap.get(url);
    }

    const abortCtrl = new AbortController();
    const timeout = setTimeout(() => abortCtrl.abort(), timeoutMs);

    const fetchPromise = fetch(url, { signal: abortCtrl.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP Error: ${res.status}`);
        return res.json();
      })
      .finally(() => {
        clearTimeout(timeout);
        this.#dedupeMap.delete(url);
      });

    this.#dedupeMap.set(url, fetchPromise);
    return fetchPromise;
  }
}
```

##### 4. `hands-on/m02/src/components/metrics-widget.js`
```javascript
export class MetricsWidget {
  #container;
  #store;
  #cleanupFunctions = [];

  constructor(containerElement, store) {
    this.#container = containerElement;
    this.#store = store;
  }

  mount() {
    this.#container.innerHTML = `
      <div class="card">
        <h3>Realtime Metrics Monitor</h3>
        <p>Throughput: <span id="throughput-val">0</span> req/s</p>
        <p>Latency: <span id="latency-val">0</span> ms</p>
        <button id="simulate-btn">Simulate Bursts</button>
      </div>
    `;

    const throughputEl = this.#container.querySelector('#throughput-val');
    const latencyEl = this.#container.querySelector('#latency-val');
    const buttonEl = this.#container.querySelector('#simulate-btn');

    // Subscribe ke reactive state
    const unsubThroughput = this.#store.subscribe('throughput', (val) => {
      throughputEl.textContent = val;
    });

    const unsubLatency = this.#store.subscribe('latency', (val) => {
      latencyEl.textContent = val;
    });

    const onBtnClick = () => {
      // Menstimulasi beberapa perubahan sekaligus; verifikasi bahwa rendering di-batch
      this.#store.state.throughput = Math.floor(Math.random() * 5000);
      this.#store.state.latency = Math.floor(Math.random() * 80);
    };

    buttonEl.addEventListener('click', onBtnClick);

    this.#cleanupFunctions.push(
      unsubThroughput,
      unsubLatency,
      () => buttonEl.removeEventListener('click', onBtnClick)
    );
  }

  destroy() {
    this.#cleanupFunctions.forEach((cleanup) => cleanup());
    this.#cleanupFunctions = [];
    this.#container.innerHTML = '';
  }
}
```

##### 5. `hands-on/m02/src/app.js`
```javascript
import { createStore } from './core/store.js';
import { MetricsWidget } from './components/metrics-widget.js';

const appRoot = document.getElementById('app');

const store = createStore({
  throughput: 1200,
  latency: 24
});

const widget = new MetricsWidget(appRoot, store);
widget.mount();

// Ekspor ke global untuk debugging lifecycle lewat browser console
window.__DIAGNOSTICS__ = {
  store,
  widget
};
```

##### 6. `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Frontend Foundations: Module 02</title>
  <link rel="stylesheet" href="styles/main.css">
</head>
<body>
  <main id="app"></main>
  <script type="module" src="src/app.js"></script>
</body>
</html>
```

##### 7. `hands-on/m02/styles/main.css`
```css
:root {
  --bg-color: #0f172a;
  --card-bg: #1e293b;
  --text-main: #f8fafc;
  --accent: #38bdf8;
}

body {
  margin: 0;
  padding: 2rem;
  background-color: var(--bg-color);
  color: var(--text-main);
  font-family: system-ui, -apple-system, sans-serif;
}

.card {
  background-color: var(--card-bg);
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #334155;
  max-width: 400px;
}

button {
  background-color: var(--accent);
  color: #0f172a;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 1rem;
}

button:hover {
  opacity: 0.9;
}
```

---

### 13. Exercise

#### Level: Easy
* **Instruksi**: Tambahkan validasi tipe data ke dalam method `createStore` di atas. Jika user mencoba memasukkan tipe data yang berbeda dengan tipe data nilai awal (*initial value*) pada key yang bersangkutan (misal: properti `throughput` yang awalnya bertipe `number` diubah menjadi `string`), lemparkan `TypeError` deskriptif dan batalkan mutasi.

#### Level: Medium
* **Instruksi**: Buat utilitas fungsi `virtualScroll({ container, totalItems, itemHeight, renderCallback })`. Fungsi ini hanya boleh me-render elemen-elemen DOM yang terlihat pada viewport ditambah buffer atas-bawah sebanyak 2 elemen. Uji implementasi Anda dengan 100.000 item array data numerik tanpa memicu degradasi FPS scrolling di browser.

#### Level: Hard
* **Instruksi**: Implementasikan sistem *Undo/Redo Time-Travel Architecture* pada store reaktif di hands-on practice menggunakan struktur data *Double Linked List* atau *Immutable Snapshots* (`Object.freeze`). Anda harus mendukung mutasi nested object (deep proxy) dan menjamin tidak ada kebocoran memori saat riwayat revisi mencapai batas konfigurasi maksimum (*bounded history* = 50 langkah).

---

### 14. Challenge

**Skenario**: Anda ditugaskan membangun *Offline-First Real-Time Telemetry SDK* internal yang akan diintegrasikan ke ribuan aplikasi edge client perusahaan. 

**Persyaratan Ketat (Constraints)**:
1. **Network Layer**: Data event telemetri dikirimkan secara batch via HTTP POST setiap 2 detik atau jika batch mencapai 50 item. Apabila jaringan putus, simpan antrean event ke dalam `IndexedDB`. Saat koneksi pulih, sinkronisasikan data ke server dengan strategi *exponential backoff jittered retry* tanpa menduplikasi data (*Idempotency Key* berbasis UUIDv4).
2. **Main-Thread Performance**: Proses serialisasi data telemetri dan enkripsi payload ringan tidak boleh memakan waktu frame thread utama lebih dari 4 ms. Jika estimasi beban kerja melampaui 4 ms, SDK harus membagi pemrosesan ke *Web Worker* atau memanfaatkan API `scheduler.yield()` / `requestIdleCallback`.
3. **Memory Budget**: SDK tidak boleh mengonsumsi lebih dari 5 MB RAM heap browser dalam kondisi terburuk (misal antrean data menumpuk akibat offline selama 2 jam).
4. **Deliverables**: Buat spesifikasi arsitektur teknis lengkap beserta proof-of-concept implementasi engine inti tanpa framework eksternal.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa memodifikasi style `transform` lebih diutamakan untuk animasi antarmuka daripada memodifikasi `top` atau `margin-left`?
2. Apa perbedaan fundamental antara siklus eksekusi Microtask (misal: `queueMicrotask`, `Promise.then`) dan Macrotask (misal: `setTimeout`) dalam satu putaran Event Loop?
3. Mengapa membaca properti geometri seperti `element.offsetHeight` tepat setelah mengubah `element.style.height` dikategorikan sebagai anti-pattern performa tinggi?
4. Apa peran struktural objek `Reflect` saat dipadukan dengan JavaScript `Proxy` handler?
5. Mengapa referensi objek yang disimpan di dalam `WeakMap` tidak menghalangi proses pengumpulan sampah (*Garbage Collection*) pada target object tersebut?

#### B. Pertanyaan Intermediate
6. Jelaskan bagaimana *Request Deduplication Pattern* menyelesaikan masalah race condition ketika dua komponen independen di layar meminta endpoint API data referensi yang sama secara serentak.
7. Pada skenario apa operasi `AbortController.abort()` tetap meninggalkan pekerjaan komputasi yang tidak perlu di memori browser, dan bagaimana cara memitigasinya?
8. Bagaimana browser menentukan apakah sebuah elemen perlu dipromosikan ke layer compositing terpisah (*Composited Layer*)?
9. Apa resiko arsitektural dari implementasi *Deep Proxy* (Proxy rekursif pada nested object) jika ditinjau dari sisi overhead memori dan instansiasi state awal?
10. Mengapa metode `window.addEventListener` dengan opsi `{ once: true }` lebih disarankan untuk event-event transisi visual satu kali dibandingkan pelepasan listener secara manual di dalam handler?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Sebuah tim melaporkan bahwa aplikasi Single Page Application (SPA) mereka mengalami freeze selama 500ms setiap kali berpindah tab navigasi, meskipun data yang dimuat sudah dicache di browser. Berdasarkan pemahaman arsitektur rendering engine dan microtasks, sebutkan dua kemungkinan penyebab utama masalah ini dan rancang solusi perbaikannya!
12. **Skenario 2**: Anda menemukan bahwa nilai metrik *Cumulative Layout Shift* (CLS) aplikasi web e-commerce Anda melonjak tajam saat banner dinamis dirender di bagian atas halaman menggunakan asynchronous fetch. Bagaimana Anda merekayasa arsitektur CSS dan DOM-nya untuk menurunkan skor CLS hingga mendekati angka 0?
13. **Skenario 3**: Sebuah aplikasi web analytics berjalan nonstop di monitor kontrol room (display kios). Setelah beroperasi selama 3 hari, tab browser selalu mengalami crash. Tim Anda menduga ada detached DOM memory leak dari komponen visualisasi real-time. Uraikan metodologi langkah demi langkah untuk mengisolasi baris kode penyebab kebocoran tersebut menggunakan Chrome DevTools Heap Profiler!

---

### 16. Summary

1. **Browser Pipeline Determinism**: Memahami siklus *Parse -> Layout -> Paint -> Composite* adalah pondasi mutlak untuk menulis kode JavaScript performa tinggi. Pengurangan Layout Thrashing dan pemanfaatan GPU compositing secara terukur adalah kunci mencapai rendering 60/120 FPS.
2. **Event Loop Orchestration**: Memanfaatkan prioritas Microtask Queue untuk batch state updates dan `requestAnimationFrame` untuk manipulasi DOM menghasilkan pembaruan visual yang sinkron dengan refresh rate display hardware.
3. **Decoupled Reactive Architecture**: Memisahkan View dari State menggunakan Proxy mengeliminasi ketergantungan pada manipulasi DOM manual yang rapuh, menyediakan platform yang terprediksi, terisolasi, dan mudah diuji.
4. **Resilient Data Transport**: Pemanggilan jaringan enterprise membutuhkan pengamanan komprehensif: pembatalan deterministik (`AbortController`), *Exponential Backoff with Full Jitter*, dan *Request Deduplication* guna menjaga ketersediaan layanan pada kondisi konektivitas ekstrem.
5. **Strict Lifecycle Discipline**: Alokasi heap JavaScript harus dikelola secara sadar. Setiap pendaftaran event listener dan struktur data berumur panjang wajib memiliki mekanisme destruksi terpadu (*teardown*) guna menjamin stabilitas aplikasi enterprise dalam jangka panjang.