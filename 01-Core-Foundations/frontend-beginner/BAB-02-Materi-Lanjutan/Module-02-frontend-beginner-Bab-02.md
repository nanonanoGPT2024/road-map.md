# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Track: Core Foundations — Frontend Engineering
### BAB 02: Materi Lanjutan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis dan Mengoptimalkan Critical Rendering Path (CRP):** Menjelaskan secara presisi siklus hidup parsing DOM/CSSOM, kalkulasi Render Tree, Layout (Reflow), Paint, dan Compositing pada browser engine modern (Blink/Gecko).
2. **Menguasai Runtime Execution & Memory Management:** Mengidentifikasi alokasi memori pada V8 Engine (Call Stack, Memory Heap, New Space, Old Space), siklus Garbage Collection (Scavenge vs Mark-Sweep-Compact), serta mencegah *memory leak* akibat closures, detached DOM nodes, dan unmanaged event listeners.
3. **Mengimplementasikan Event Loop & Asynchronous Architecture:** Mengorkestrasikan eksekusi microtasks (Promises, MutationObserver) vs macrotasks (setTimeout, I/O, UI Rendering) untuk mencapai 60/120 FPS tanpa frame drop (*jank*).
4. **Membangun Arsitektur State Management Reaktif Tanpa Dependensi Eksternal:** Merancang custom reactive store berbasis Observer Pattern, EventTarget, atau ES6 Proxies dengan batch-rendering via `requestAnimationFrame`.
5. **Menerapkan Enkapsulasi Komponen Berstandar W3C:** Mengembangkan arsitektur berbasis native Web Components (Custom Elements v1, Shadow DOM v1, Template Elements) yang siap integrasi pada sistem monorepo enterprise berskala besar.

---

## 2. Prerequisite

Sebelum menempuh modul lanjutan ini, peserta wajib memahami:
- **Core JavaScript (ECMAScript 2022+):** Scope, closures, prototype chain, async/await, destructing, ES Modules (`import`/`export`).
- **DOM & CSS Dasar:** Seleksi elemen via DOM API (`querySelector`), manipulasi class/attribute, CSS Box Model, Flexbox/Grid, serta positioning context.
- **Konsep Client-Server:** HTTP/HTTPS lifecycle, payload parsing (JSON), dan REST API fundamentals.
- **Developer Tooling:** Penggunaan Chrome DevTools (Console, Elements panel, Network tab inspection).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Browser Rendering Engine: The Critical Rendering Path (CRP)

Browser modern adalah sistem operasi mini terdistribusi yang memproses stream byte mentah menjadi pixel visual yang interaktif. Proses ini ditangani oleh rendering engine (seperti Blink pada Chromium atau WebKit pada Safari) melalui alur sekuensial yang sangat teroptimasi:

```
[Raw Bytes] -> [Characters] -> [Tokens] -> [Nodes] -> [DOM Tree]
                                                          |
[Raw CSS]   -> [Tokens]     -> [Nodes]  -> [CSSOM Tree]  |
                                                 |        |
                                                 v        v
                                            [Render Tree]
                                                 |
                                                 v
                                           [Layout/Reflow]
                                                 |
                                                 v
                                              [Paint]
                                                 |
                                                 v
                                           [Compositing] -> [GPU Screen Buffer]
```

1. **DOM Construction:** Byte stream HTML didekodekan sesuai encoding (UTF-8), dianalisis secara leksikal menjadi token (`TagOpen`, `TagClose`, `Attribute`), diubah menjadi instance objek `Node`, dan akhirnya dirangkai menjadi struktur hirarki `DOM Tree`.
2. **CSSOM Construction:** Serupa dengan HTML, CSS diurai menjadi ruleset yang bersifat *render-blocking*. CSSOM bersifat pohon hierarki independen di mana inheritance cascade dihitung.
3. **Render Tree Generation:** Engine mengawinkan DOM dan CSSOM. Node dengan properti `display: none` atau tag `<head>` tidak dimasukkan ke dalam Render Tree. Namun, node dengan `visibility: hidden` tetap dimasukkan karena tetap memakan ruang fisik.
4. **Layout (Reflow):** Engine menghitung geometri pasti (ukuran, posisi koordinat $X, Y$) dari setiap node relatif terhadap viewport. Operasi ini sangat mahal secara komputasional ($O(N \log N)$ hingga $O(N^2)$ pada nesting kompleks).
5. **Paint:** Engine memecah render tree menjadi visual instruction list (draw rect, draw text, raster image). Operasi ini sering kali dibagi menjadi beberapa visual layers (`GraphicsLayer`).
6. **Compositing:** Browser Compositor Thread mengirimkan layer-layer terpisah ke GPU via raster worker threads untuk digabungkan menjadi single frame buffer akhir yang ditampilkan pada layar fisik.

### 3.2 JavaScript Runtime & Memory Architecture (V8 Deep Dive)

JavaScript dieksekusi di single-threaded main thread, namun runtime V8 memisahkan memori secara ketat:

- **Stack (Call Stack):** Menyimpan primitive types (string, number, boolean, null, undefined, symbol, bigint) dan reference pointers yang memiliki alokasi memori fixed-size. Struktur data LIFO (Last-In-First-Out).
- **Heap (Memory Heap):** Alokasi memori tidak terstruktur dinamis untuk Object, Array, Function, dan closures.
  - *New Space (Young Generation):* Objek baru berumur pendek. Diperiksa secara cepat melalui *Scavenger GC* (Cheney's algorithm).
  - *Old Space (Old Generation):* Objek yang bertahan dari dua siklus GC dipromosikan ke sini. Dikelola oleh *Major GC (Mark-Sweep-Compact)* yang memicu thread pause (Stop-the-World latency jika tidak dioptimalkan).

### 3.3 Event Loop: Macrotask vs Microtask Execution Pipeline

Untuk menjaga rendering tetap mulus pada interval ~16.67ms (target 60 FPS), runtime membagi antrean pekerjaan sebagai berikut:

1. Ambil dan selesaikan **SATU** task tertua dari **Macrotask Queue** (Task Queue: `setTimeout`, `setInterval`, `setImmediate`, I/O).
2. Kuras dan selesaikan **SELURUH** task di dalam **Microtask Queue** (`Promise.then/catch/finally`, `queueMicrotask`, `MutationObserver`). Jika microtask menjadwalkan microtask lain, proses terus berlanjut hingga microtask queue benar-benar kosong.
3. Masuk ke fase **Render Execution** (jika waktu frame tiba):
   - Trigger event `resize`, `scroll`.
   - Jalankan callback `requestAnimationFrame` (rAF).
   - Jalankan kalkulasi Layout & Paint.
4. Ulangi ke siklus berikutnya.

---

## 4. Why & What

### Mengapa Pendekatan Enterprise Berbeda dengan Pemula?
Aplikasi skala enterprise (seperti dashboard trading perbankan, platform analitik big data, atau back-office ERP global) menghadapi ribuan transaksi data per detik. Pengembang pemula sering kali mengabaikan internal browser, yang berdampak pada:
- **Layout Thrashing:** Membaca properti layout geometri (misal: `element.offsetHeight`) sesaat setelah memodifikasi styling, memaksa browser melakukan synchronous layout kalkulasi berulang kali dalam satu frame.
- **Memory Bloat & Leaks:** Menumpuk memory retainers sehingga tab browser mengonsumsi RAM gigabyte-an dan akhirnya mengalami crash (Out-Of-Memory/OOM).
- **Framework Fatigue & Overhead:** Membawa bundle framework yang terlalu besar untuk masalah-masalah performa mikro yang seharusnya diselesaikan pada level native DOM/Browser API.

### Apa yang Kita Bangun?
Kita akan membedah dan membangun sistem foundational:
- Event-driven unidirectional state store vanilla dengan zero runtime external dependencies.
- Pipeline batch-rendering berbasis Web APIs (`DocumentFragment`, `requestAnimationFrame`).
- Komponen web terisolasi menggunakan Web Components (Shadow DOM) dengan arsitektur lifecycle yang tangguh terhadap memory leak.

---

## 5. How (Workflow Detail)

Alur perancangan modul enterprise di tingkat frontend core:

1. **State Mutation:** User atau event memicu mutasi state.
2. **Microtask Queue Dispatcher:** State store menerima mutasi, memperbarui record internal, dan alih-alih me-render seketika, store mendaftarkan job update ke Microtask Queue atau requestAnimationFrame queue (*Debounce/Batching Phase*).
3. **Diffing / Fragment Construction:** Render pipeline mempersiapkan node di memori menggunakan `DocumentFragment` offline tree atau Virtual Node abstraction.
4. **Fast Atomic DOM Swap:** Elemen DOM yang aktif diganti secara atomik untuk mencegah pemanggilan berulang pada subsistem Layout Engine.
5. **Lifecycle Teardown Cleanup:** Pendaftaran destruktor untuk membersihkan `AbortController`, event listeners, dan references untuk membebaskan V8 heap allocator.

---

## 6. Analogy & Diagram ASCII

### Analogi CRP & Event Loop: Pabrik Percetakan Buku Modern
Bayangkan sebuah pabrik majalah harian:
- **DOM/CSSOM** adalah draft naskah mentah dan pedoman palet warna editorial.
- **Render Tree** adalah layout approval: editor membuang artikel yang dilarang terbit (`display: none`).
- **Layout** adalah penentuan tata letak halaman: menghitung ukuran kolom, margin, dan posisi foto secara matematis.
- **Paint** adalah proses penyemprotan tinta warna (Cyan, Magenta, Yellow, Black) ke kertas.
- **Compositing** adalah pemotongan dan penjilidan halaman-halaman tersebut secara paralel menggunakan mesin sortir berkecepatan tinggi (GPU).

Jika penulis terus mengubah ukuran gambar di tengah proses percetakan (Layout Thrashing), mesin cetak harus dimatikan total, plat dibongkar ulang, dan siklus diulang dari awal.

### Arsitektur Aliran Frame Engine

```
+-------------------------------------------------------------------------+
| Browser Main Thread (Frame Interval ~16.6ms)                           |
+-------------------------------------------------------------------------+
| [Task] -> [All Microtasks] -> [rAF Callback] -> [Layout] -> [Paint]   |
+-------------------------------------------------------------------------+
     |               |                |
     | (setTimeout)  | (Promises)     | (Geom Mutation)
     v               v                v
+----------+   +-------------+   +-------------------+
| Macro Q  |   | Micro Q     |   | Layout Engine     |
+----------+   +-------------+   | (Forced Reflow    |
                                 |  Danger Zone!)    |
                                 +-------------------+
                                          |
                                          v Compositor Thread
                                 +-------------------+
                                 | GPU Rasterization |
                                 +-------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Bahaya Layout Thrashing vs Batch Read/Write

#### Kode Bermasalah (Mengakibatkan Forced Reflow):
```javascript
// BAD: Interleaved Read/Write memicu Layout berkali-kali
function resizeAllBad(elements) {
  for (let i = 0; i < elements.length; i++) {
    // READ (Layout dipaksa sinkron untuk membaca geometri terkini)
    const currentWidth = elements[i].offsetWidth; 
    // WRITE (Menandai geometri sebagai dirty)
    elements[i].style.width = (currentWidth + 10) + 'px'; 
  }
}
```

#### Kode Teroptimasi (Separated Read & Write via Fast Pipeline):
```javascript
// GOOD: Pisahkan pembacaan (Batch Read) dan penulisan (Batch Write)
function resizeAllOptimized(elements) {
  // Batch Read: Browser menggunakan cache geometri yang sama
  const widths = elements.map(el => el.offsetWidth);

  // Batch Write via requestAnimationFrame
  window.requestAnimationFrame(() => {
    elements.forEach((el, index) => {
      el.style.width = `${widths[index] + 10}px`;
    });
  });
}
```

---

### 7.2 Practical Example: Enterprise-Grade Micro-Store & Reactive Custom Element

Sistem berikut mengimplementasikan custom state store reaktif terisolasi dan Shadow DOM web component native yang menangani dynamic rendering dengan alokasi heap minimal.

```javascript
/**
 * @file Enterprise Reactive Store and Native Component Architecture
 * @version 1.0.0
 */

/**
 * @template T
 * Immutable Reactive Store Engine dengan Microtask Batch Notification
 */
class EnterpriseStore {
  /** @type {T} */
  #state;
  /** @type {Set<(state: T) => void>} */
  #subscribers = new Set();
  /** @type {boolean} */
  #isBatchScheduled = false;

  /**
   * @param {T} initialState 
   */
  constructor(initialState) {
    this.#state = Object.freeze({ ...initialState });
  }

  /**
   * @returns {T} Current State Snapshot (Readonly)
   */
  getState() {
    return this.#state;
  }

  /**
   * Atomic State Mutation dengan batched microtask notification
   * @param {Partial<T> | ((prevState: T) => Partial<T>)} updater 
   */
  setState(updater) {
    const nextPartial = typeof updater === 'function' ? updater(this.#state) : updater;
    this.#state = Object.freeze({ ...this.#state, ...nextPartial });

    if (!this.#isBatchScheduled) {
      this.#isBatchScheduled = true;
      // Gunakan Microtask Queue agar banyak mutasi sinkron dirangkum menjadi satu render
      queueMicrotask(() => {
        this.#isBatchScheduled = false;
        this.#notify();
      });
    }
  }

  /**
   * @param {(state: T) => void} subscriber 
   * @returns {() => void} Unsubscribe cleanup hook
   */
  subscribe(subscriber) {
    this.#subscribers.add(subscriber);
    // Emit state terkini secara langsung saat registrasi
    subscriber(this.#state);
    return () => {
      this.#subscribers.delete(subscriber);
    };
  }

  #notify() {
    for (const subscriber of this.#subscribers) {
      try {
        subscriber(this.#state);
      } catch (err) {
        console.error('[Store] Error in subscriber pipeline:', err);
      }
    }
  }
}

/**
 * Enterprise Performance Data Display Component
 * Memanfaatkan Shadow DOM v1 & AbortController Memory Safe Architecture
 */
class PerformanceMetricElement extends HTMLElement {
  /** @type {ShadowRoot} */
  #shadowRoot;
  /** @type {AbortController | null} */
  #abortController = null;
  /** @type {() => void | null} */
  #storeUnsubscribe = null;

  static get observedAttributes() {
    return ['data-threshold'];
  }

  constructor() {
    super();
    this.#shadowRoot = this.attachShadow({ mode: 'closed' });
    this.#shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          contain: content; /* Isolasi layout & style recalculation */
        }
        .metric-card {
          padding: 16px;
          border-radius: 8px;
          background: #ffffff;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
          border-left: 6px solid #cbd5e1;
          transition: border-color 0.2s ease;
        }
        .metric-card.warning {
          border-left-color: #ef4444;
          background: #fff5f5;
        }
        .title {
          font-size: 0.875rem;
          color: #64748b;
          text-transform: uppercase;
        }
        .value {
          font-size: 1.5rem;
          font-weight: 700;
          color: #0f172a;
        }
      </style>
      <div class="metric-card" id="card">
        <div class="title" id="metric-title">N/A</div>
        <div class="value" id="metric-value">0</div>
      </div>
    `;
  }

  /**
   * Lifecyle: Connected Callback (Mounting Phase)
   */
  connectedCallback() {
    this.#abortController = new AbortController();
    const { signal } = this.#abortController;

    // Contoh Event Binding yang Memory Leak Proof via AbortSignal
    this.addEventListener('click', this.#handleClick.bind(this), { signal });
  }

  /**
   * Dependency Injection untuk integrasi Store
   * @param {EnterpriseStore<{label: string, value: number}>} store 
   */
  bindStore(store) {
    if (this.#storeUnsubscribe) {
      this.#storeUnsubscribe();
    }

    this.#storeUnsubscribe = store.subscribe((state) => {
      this.#render(state);
    });
  }

  /**
   * Lifecyle: Attribute Changed Callback
   */
  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue !== newValue && name === 'data-threshold') {
      // Re-trigger visual evaluasi
      this.#evaluateThreshold(Number(newValue));
    }
  }

  #handleClick() {
    this.dispatchEvent(new CustomEvent('metric-selected', {
      detail: { timestamp: performance.now() },
      bubbles: true,
      composed: true // Mengizinkan event tembus batas Shadow DOM
    }));
  }

  /**
   * Render Terisolasi dengan Fast DOM Mutations
   * @param {{label: string, value: number}} state 
   */
  #render(state) {
    const titleEl = this.#shadowRoot.getElementById('metric-title');
    const valEl = this.#shadowRoot.getElementById('metric-value');

    if (titleEl && valEl) {
      titleEl.textContent = state.label;
      valEl.textContent = state.value.toLocaleString();
      this.#evaluateThreshold(Number(this.getAttribute('data-threshold') || '100'));
    }
  }

  #evaluateThreshold(threshold) {
    const cardEl = this.#shadowRoot.getElementById('card');
    const valEl = this.#shadowRoot.getElementById('metric-value');
    if (!cardEl || !valEl) return;

    const currentVal = parseFloat(valEl.textContent || '0');
    if (currentVal > threshold) {
      cardEl.classList.add('warning');
    } else {
      cardEl.classList.remove('warning');
    }
  }

  /**
   * Lifecycle: Disconnected Callback (Unmounting & Teardown Phase)
   */
  disconnectedCallback() {
    // 1. Bersihkan subscription store untuk mencegah Retained Objects di V8 Heap
    if (this.#storeUnsubscribe) {
      this.#storeUnsubscribe();
      this.#storeUnsubscribe = null;
    }

    // 2. Abort semua native listener yang terdaftar melalui signal
    if (this.#abortController) {
      this.#abortController.abort();
      this.#abortController = null;
    }
  }
}

// Definisikan Custom Element jika belum teregistrasi
if (!customElements.get('enterprise-metric-card')) {
  customElements.define('enterprise-metric-card', PerformanceMetricElement);
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Financial High-Frequency Order Book Dashboard
Sebuah platform broker valuta asing (FX Trading) memproses data masuk via WebSocket dengan throughput rata-rata **2.500 price-ticks per detik**.

### Problem Statement:
Implementasi awal menggunakan manipulasi DOM naif:
```javascript
socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  const row = document.getElementById(`order-${data.id}`);
  row.innerText = data.price; // Forced Reflow & Paint terus-menerus
  document.body.appendChild(row);
};
```
**Dampak di Produksi:**
- Main thread terblokir secara permanen (*CPU 100%*).
- Frame rate anjlok ke **4–8 FPS** (*UI freeze total*).
- Terjadi **Heap Out-Of-Memory (OOM)** crash dalam 15 menit berjalan karena listeners dan detached nodes tidak dibersihkan saat baris order book kadaluarsa.

### Solusi Arsitektural Enterprise:
1. **Penerapan Ring-Buffer In-Memory:** Mengisolasi data mentah yang masuk dari representasi visual.
2. **Coalesced RAF Batching:** Data di-buffer dan dikompresi (hanya tick harga terakhir per order ID yang dipertahankan dalam jendela 16.6ms).
3. **Double Buffering Virtual Fragment:** Update DOM dilakukan secara offline menggunakan `DocumentFragment` dan diaplikasikan via `requestAnimationFrame`.

```javascript
class HighThroughputOrderBook {
  constructor(tableBodyEl) {
    this.container = tableBodyEl;
    this.buffer = new Map(); // Key: OrderID, Value: Latest Data
    this.isTicking = false;
  }

  // Dipanggil 2500x/detik dari WebSocket thread listener
  ingest(tickData) {
    this.buffer.set(tickData.id, tickData);

    if (!this.isTicking) {
      this.isTicking = true;
      window.requestAnimationFrame(this.#flushToDOM.bind(this));
    }
  }

  #flushToDOM() {
    // Eksekusi tepat sebelum Paint phase dimulai oleh browser
    const fragment = document.createDocumentFragment();

    for (const [id, tick] of this.buffer.entries()) {
      let tr = document.getElementById(`row-${id}`);
      if (!tr) {
        tr = document.createElement('tr');
        tr.id = `row-${id}`;
        tr.innerHTML = `<td>${id}</td><td class="price"></td>`;
        fragment.appendChild(tr);
      }
      // Mutasi visual aman
      tr.querySelector('.price').textContent = tick.price.toFixed(4);
    }

    if (fragment.children.length > 0) {
      this.container.appendChild(fragment);
    }

    this.buffer.clear();
    this.isTicking = false;
  }
}
```

**Hasil Pengukuran DevTools Performance Profile:**
- Frame rate stabil di angka **58-60 FPS**.
- Main Thread Idle Time meningkat dari 0% menjadi 72%.
- Zero Garbage Collection thrashing.

---

## 9. Trade-offs

| Parameter | Direct Native DOM Manipulation | Virtual Abstraction Layer (Custom/Shadow DOM) | Framework Runtime (React/Vue/Angular) |
| :--- | :--- | :--- | :--- |
| **Performance (Raw Throughput)** | **Sangat Tinggi** (Jika dioptimasi secara manual tanpa reflow). | **Tinggi** (CSS Containment & Encapsulation engine native). | **Moderat - Rendah** (Overhead tree-diffing dan alokasi V8 wrapper). |
| **Latency (First Paint / TTI)** | **Minimal (~0ms)**, tanpa JavaScript hydration cost. | **Sangat Rendah**, hanya overhead registrasi custom registry. | **Tinggi**, membutuhkan download, parse, dan execute runtime bundle (30-150KB+). |
| **Scalability (Maintenance)** | **Buruk**. Mudah terjadi spaghetti code dan DOM coupled logic. | **Tinggi**. Enkapsulasi kuat standar platform W3C tanpa breaking changes antar versi. | **Sangat Tinggi**. Ekosistem luas, standardisasi struktur file, declarative programming. |
| **Engineering Cost** | Mahal diawal. Memerlukan senior engineers dengan pemahaman mendalam tentang platform internals. | Moderat. Standar W3C Web Components lintas tim/lintas teknologi. | Rendah/Tersedia Luas. Ketersediaan talent pool engineer di pasar sangat banyak. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Detached DOM Tree Leaks
* **Kesalahan:** Menghapus elemen dari tampilan dengan `parentElement.removeChild(child)` tetapi tetap menyimpan referensinya di dalam global array atau closure object.
* **Deteksi:** Ambil Heap Snapshot di Chrome DevTools, filter dengan istilah `Detached HTMLElement`.
* **Solusi:** Set referensi objek variabel lokal ke `null` setelah elemen dilepas dari dokumen.

### 2. Layout Thrashing via Read-After-Write Loops
* **Kesalahan:**
  ```javascript
  elements.forEach(el => {
    el.style.height = `${container.offsetHeight}px`; // Membaca offsetHeight memicu reflow setiap iterasi!
  });
  ```
* **Solusi:** Ekstraksi pembacaan metrik ke luar perulangan.
  ```javascript
  const targetHeight = container.offsetHeight; // 1x Reflow read
  elements.forEach(el => {
    el.style.height = `${targetHeight}px`; // Write execution
  });
  ```

### 3. Zombie Event Listeners
* **Kesalahan:** Mengabaikan penghapusan listener pada komponen dinamis yang memiliki umur pakai singkat (*ephemeral components*).
* **Solusi:** Gunakan `AbortController` API modern:
  ```javascript
  const controller = new AbortController();
  window.addEventListener('resize', handler, { signal: controller.signal });
  // Saat komponen didestruksi:
  controller.abort(); // Secara otomatis mencabut listener tanpa perlu menyimpan referensi fungsi asli
  ```

---

## 11. Best Practices (Production Checklist)

- [ ] **CSS Containment:** Pasang properti CSS `contain: content;` atau `contain: layout style;` pada dynamic widgets dan custom elements untuk mengisolasi boundary reflow browser.
- [ ] **Fast Reads & Writes:** Gunakan library mutasi berbasis microtask atau pisahkan fase baca/tulis secara konsisten (`requestAnimationFrame` untuk styling updates).
- [ ] **GPU Accelerated Transforms:** Gunakan hanya properti `transform` (misal: `translate3d`) dan `opacity` untuk animasi interface. Hindari menganimasi `top`, `left`, `margin`, atau `padding`.
- [ ] **Passive Event Listeners:** Untuk event handling interaktif frekuensi tinggi (`scroll`, `wheel`, `touchstart`), wajib set flag `{ passive: true }` agar tidak memblokir main-thread compositor.
- [ ] **Strict Memory Lifecycle Hooking:** Pastikan seluruh Custom Elements mengimplementasikan teardown logic komprehensif pada lifecycle `disconnectedCallback()`.
- [ ] **Immutable State Snapshots:** Cegah direct in-place mutation pada state store menggunakan `Object.freeze()` di layer output untuk mendeteksi runtime mutation errors lebih dini.

---

## 12. Hands-on Practice

Simpan seluruh hasil pekerjaan Anda pada direktori lokal: `hands-on/m02/`

### File: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Core Architecture M02</title>
  <style>
    body { font-family: sans-serif; padding: 2rem; background: #f8fafc; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
  </style>
</head>
<body>
  <h1>Mission Control Telemetry</h1>
  <button id="mutate-btn">Simulasikan Mutasi Skala Tinggi</button>
  <hr/>
  <div class="grid" id="metrics-container">
    <enterprise-metric-card id="cpu-metric" data-threshold="80"></enterprise-metric-card>
    <enterprise-metric-card id="mem-metric" data-threshold="1024"></enterprise-metric-card>
  </div>

  <script type="module" src="./app.js"></script>
</body>
</html>
```

### File: `hands-on/m02/app.js`
1. Salin implementasi class `EnterpriseStore` dan `PerformanceMetricElement` dari Seksi 7.2 ke dalam berkas modular.
2. Buat instances dua store: `cpuStore` dan `memStore`.
3. Lakukan binding antar custom element dengan masing-masing store.
4. Tulis event listener pada `#mutate-btn` untuk memicu 1.000 mutasi data berturut-turut dalam single loop.
5. Verifikasi di Performance tab Chrome DevTools: pastikan render hanya terjadi **satu kali** per tick rendering berikutnya berkat integrasi microtask queue batcher.

---

## 13. Exercise

### Level Easy
Modifikasi implementasi class `EnterpriseStore` agar mendukung dynamic accessor `getStateKey(key)` untuk mengambil nilai state secara selektif tanpa menduplikasi referensi object secara keseluruhan.

### Level Medium
Buat sebuah fungsi utilitas `measureLayoutThrashing(mutationFn)` yang memanfaatkan `PerformanceObserver` API (entry type `longtask` atau User Timing marks) untuk mengukur durasi dan mendeteksi apakah suatu callback memicu forced synchronous layout di atas limit 16.6ms.

### Level Hard
Implementasikan custom virtual scrolling engine native (panjang list data: 50.000 data nodes). Komponen hanya boleh men-generate elemen DOM fisik yang terlihat di layar (*visible buffer window*) plus 3 baris overscan. Elemen DOM lama harus di-recycle, bukan di-destroy total, untuk meminimalkan alokasi memori heap pada V8 engine.

---

## 14. Challenge

### Studi Kasus: Enterprise Canvas/DOM Hybrid CAD Viewer

**Skenario Sistem:**
Anda ditugaskan mendesain subsistem arsitektur antarmuka untuk aplikasi CAD berbasis web berstandar industri. Dashboard harus menampilkan 5.000 node inspeksi yang tersebar pada kanvas tak terbatas (*infinite canvas*). Pengguna dapat melakukan operasi *panning* dan *zooming* (60 FPS mutlak). Setiap node menampilkan teks atribut yang tajam (resolusi font berbasis CSS), namun garis koneksi antar node harus digambar pada layer terpisah.

**Instruksi Teknis & Kriteria Keberhasilan:**
1. Desain hierarki rendering di mana interaksi pointer (drag, zoom) tidak pernah memicu layout cycle pada 5.000 node secara sinkron.
2. Manfaatkan kombinasi CSS `will-change`, CSS transform matriks 3D, isolasi Web Components Shadow DOM (`contain: strict`), serta Compositor Layers.
3. Rancang strategi pembersihan memori jika CAD viewer dimuat dan ditutup secara dinamis di dalam Single-Page App tanpa memicu kenaikan memory retention size pada heap inspection.
4. **Batas Tantangan:** Implementasikan ini sepenuhnya menggunakan Native Modern Web Platform (Pure ECMAScript, DOM API, CSS Platform features). Dilarang keras menggunakan framework, bundling tools, ataupun third-party runtime library.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Konseptual)

1. **Apa perbedaan struktural mendasar antara proses Layout (Reflow) dan Paint pada browser rendering engine?**
   - A. Layout menentukan warna piksel, Paint menentukan posisi piksel.
   - B. Layout menghitung ukuran geometri dan koordinat elemen di viewport, sedangkan Paint mengisinya dengan warna, teks, gambar, dan border visual.
   - C. Paint dijalankan sebelum Layout pada pipeline render tree.
   - D. Layout dieksekusi di GPU thread, sedangkan Paint dieksekusi di Main Thread.

2. **Manakah dari baris kode JavaScript berikut yang seketika memaksa browser menjalankan Forced Synchronous Layout (Reflow)?**
   - A. `element.style.color = 'red';`
   - B. `console.log(element.id);`
   - C. `const height = element.getBoundingClientRect().height;` setelah modifikasi style sebelumnya.
   - D. `element.classList.add('active');`

3. **Di area memori manakah primitive variables berukuran tetap dialokasikan pada V8 Engine?**
   - A. Old Space
   - B. Call Stack
   - C. Scavenger Heap
   - D. Large Object Space

4. **Bagaimana urutan eksekusi antrean berikut jika dijadwalkan pada waktu yang sama?**
   ```javascript
   setTimeout(() => console.log('A'), 0);
   Promise.resolve().then(() => console.log('B'));
   queueMicrotask(() => console.log('C'));
   ```
   - A. A -> B -> C
   - B. B -> C -> A
   - C. C -> B -> A
   - D. B -> A -> C

5. **Apa fungsi utama dari pemanggilan `attachShadow({ mode: 'closed' })` pada custom element native?**
   - A. Mencegah browser me-render elemen sama sekali.
   - B. Menyembunyikan dan mengisolasi internal Shadow Root dari akses skrip luar melalui properti `.shadowRoot`.
   - C. Mempercepat parsing CSS hingga 2 kali lipat.
   - D. Menonaktifkan event bubbling ke parent element.

---

### Bagian 2: Intermediate (Analisis Logika & Arsitektur)

6. **Mengapa pemanggilan `requestAnimationFrame` lebih direkomendasikan untuk manipulasi visual animasi dibandingkan `setTimeout(..., 16.6)`?**
   - Jelaskan hubungan sinkronisasi callback `rAF` dengan monitor refresh rate dan compositor thread.

7. **Perhatikan kode berikut. Apakah kode ini berpotensi menyebabkan memory leak? Jika ya, jelaskan apa objek yang tertahan di memory (retainer)!**
   ```javascript
   function setupLeak() {
     const heavyData = new Array(1000000).fill('payload');
     const button = document.getElementById('submit-btn');
     button.addEventListener('click', () => {
       console.log('Button clicked, data length:', heavyData.length);
     });
   }
   setupLeak();
   ```

8. **Bagaimana mekanisme kerja properti CSS `contain: content;` dalam meningkatkan performa aplikasi enterprise yang memiliki ribuan DOM nodes?**

9. **Apa perbedaan siklus pembersihan memori V8 antara Minor GC (Scavenger) dan Major GC (Mark-Sweep-Compact)? Mengapa Major GC berisiko menyebabkan antarmuka mengalami visual stuttering (*jank*)?**

10. **Jelaskan peran parameter `composed: true` saat menginisialisasi `new CustomEvent(name, { composed: true, bubbles: true })` di dalam Shadow DOM!**

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario Kasus Memory Profiling:**
    Sebuah aplikasi data-entry akuntansi dilaporkan berjalan sangat lambat setelah digunakan staf selama 4 jam berturut-turut tanpa reload browser. Setelah Anda mengambil Heap Snapshot, ditemukan ribuan instance `HTMLDivElement` dengan status `(Detached)`. 
    - Analisis bagaimana siklus hidup DOM detachment ini bisa terjadi secara struktural pada kode aplikasi.
    - Sebutkan 3 langkah investigasi menggunakan Chrome DevTools untuk melacak pointer root (*retaining path*) yang menahan elemen-elemen tersebut agar tidak bisa dibersihkan oleh Garbage Collector!

12. **Skenario Kasus UI Freezing:**
    Tim frontend Anda melaporkan bahwa ketika menerima payload data array 10.000 record dari server, antarmuka mengalami *freeze* selama 1,2 detik sebelum data berhasil dirender ke layar.
    - Bedah kegagalan arsitektur eksekusi pada skenario ini dikaitkan dengan pembagian waktu di Main Thread.
    - Buat rancangan solusi teknis menggunakan teknik **Time-Slicing** (pemotongan tugas) dengan memanfaatkan `scheduler.yield()` modern atau fallback berbasis Microtask/Macrotask agar antarmuka tetap responsif terhadap input pengguna selama proses rendering array tersebut berlangsung!

13. **Skenario Kasus Concurrency & State Inconsistency:**
    Dua buah komponen mikro independen di layar mendengarkan WebSocket channel yang sama. Keduanya memicu mutasi parsial pada central store secara bersamaan dalam jeda sub-millisecond. Tanpa perancangan antrean mutasi yang benar, apa anomali visual yang dapat terjadi pada browser Layout Engine? Bagaimana arsitektur batching microtask yang kita bangun di Bab 7.2 mencegah masalah *race-condition* visual tersebut?

---

## 16. Summary

1. **The Critical Rendering Path (CRP)** adalah fondasi utama efisiensi performa frontend. Memahami alur parsing bytes hingga compositing di GPU memungkinkan perekayasa perangkat lunak mengeliminasi bottleneck struktural seperti Layout Thrashing.
2. **V8 Engine Memory Management** membedakan alokasi Stack untuk fixed primitives dan Heap untuk dynamic objects. Garbage collection tidak boleh dipandang sebagai sistem otomatis tanpa konsekuensi; retensi referensi melalui closures, zombie event listeners, dan detached DOM nodes adalah penyebab utama kegagalan fatal performa di browser.
3. **Event Loop Orchestration:** Mengetahui batas pemisah tegas antara Macrotask Queue, Microtask Queue, dan Render Phase (requestAnimationFrame) adalah kunci utama dalam membangun custom reactivity framework tanpa mengorbankan kelancaran antarmuka (60/120 FPS).
4. **Standard-Based Modularity:** Web Components (Custom Elements v1 dan Shadow DOM v1) menyediakan enkapsulasi native level platform berkinerja tinggi. Melalui pendekatan arsitektur yang sadar memori (*memory-safe lifecycle hooks*), sistem antarmuka berskala enterprise dapat dibangun secara berkelanjutan, tangguh, dan bebas dari ketergantungan framework yang rapuh.