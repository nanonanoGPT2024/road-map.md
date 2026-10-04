# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis Internal Browser Rendering Engine**: Membedah alur eksekusi kritis (*Critical Rendering Path*) dari parsing HTML/CSS, *Render Tree construction*, *Layout/Reflow*, *Paint*, hingga GPU *Compositing* untuk mengeliminasi *layout thrashing* dan *jank*.
2. **Merancang Arsitektur State Reaktif Vanilla**: Membangun mesin state terpusat (*Unidirectional Data Flow*) berskala enterprise menggunakan JavaScript `Proxy`, *Publish-Subscribe pattern*, dan *batched asynchronous DOM patching* via `queueMicrotask`.
3. **Mengimplementasikan Web Components Standar Enterprise**: Menguasai enkapsulasi tingkat rendah menggunakan Custom Elements v1, Shadow DOM (Open/Closed), dan HTML Templates dengan komunikasi berbasis Custom Events tanpa dependensi framework eksternal.
4. **Menerapkan Profiling dan Mitigasi Memory Leak**: Mengidentifikasi serta menyelesaikan *detached DOM tree*, *dangling event listeners*, dan *unbounded closure retention* menggunakan Chrome DevTools Memory Heap Profiler.
5. **Menegakkan Keamanan Frontend (Defensive Engineering)**: Mengamankan alur manipulasi DOM dari serangan Cross-Site Scripting (XSS) berbasis DOM melalui implementasi sanitasi *Context-Aware*, *Trusted Types API*, dan *Content Security Policy* (CSP) Level 3.

---

## 2. Prerequisite

Untuk mencerna materi ini secara optimal, Anda wajib telah menguasai:

- **Advanced ES6+ JavaScript**: Primitive vs Reference Types, Closures, Prototypal Inheritance, Asynchronous (Promises, `async`/`await`), Event Loop (Call Stack, Task Queue, Microtask Queue), dan ES Modules (`import`/`export`).
- **DOM Core API**: `Document`, `Element`, `Node`, `EventTarget`, Event Propagation model (*Capturing*, *Target*, *Bubbling*), serta Event Delegation.
- **Fundamental Browser Networking & Security**: HTTP Semantics, CORS, Cookies (`SameSite`, `HttpOnly`), dan dasar web storage (`localStorage`, `sessionStorage`, `IndexedDB`).
- **Penguasaan Tooling Dasar**: Chrome DevTools (Elements panel, Performance panel, Memory Profiler, dan Console API).

---

## 3. Concept & Internal Architecture

### 3.1 Browser Engine Pipeline: Critical Rendering Path (CRP)

Browser tidak merender kode HTML mentah secara magis. Terdapat pipeline multi-tahap deterministik yang berjalan di dalam CPU dan GPU:

```
[HTML Stream] ---> [Tokenizer] ---> [Node Construction] ---> [DOM Tree]
                                                                  |
[CSS Stream]  ---> [Tokenizer] ---> [Rule Matching]     ---> [CSSOM Tree]
                                                                  |
                                                           [Render Tree]
                                                                  |
                                                        [Layout (Reflow)]
                                                                  |
                                                        [Paint (Repaint)]
                                                                  |
                                                        [Compositing (GPU)]
```

1. **DOM Tree Construction**: Alur byte mentah dikonversi menjadi karakter, kemudian di-tokenize, dikonversi menjadi *Nodes*, dan dirakit menjadi struktur pohon rekursif (DOM). Proses ini bersifat *incremental* (streaming).
2. **CSSOM Tree Construction**: Parsing CSS bersifat *render-blocking*. Browser membangun *CSS Object Model* yang juga berbentuk pohon hierarkis dengan kalkulasi spesifisitas gaya (*cascade*).
3. **Render Tree Generation**: Menggabungkan DOM dan CSSOM. Node dengan display `none` tidak akan masuk ke Render Tree (berbeda dengan `visibility: hidden` yang tetap masuk karena mempertahankan alokasi geometri).
4. **Layout (Reflow)**: Menghitung geometri pasti (posisi absolut $X, Y$, serta dimensi $Width, Height$) dari setiap node dalam *viewport*. Reflow memakan komputasi tinggi karena perubahan satu elemen dapat memicu kalkulasi ulang seluruh pohon layout secara kaskade.
5. **Paint**: Mengonversi node dari Render Tree menjadi piksel visual pada layar (warna, border, bayangan, teks).
6. **Compositing**: Mengirim layer-layer yang digambar secara terpisah ke GPU untuk digabungkan menjadi satu gambar di layar. Properti seperti `transform` dan `opacity` dilempar langsung ke proses Compositor, melewati tahap Layout dan Paint, sehingga mampu mencapai animasi stabil pada 60 FPS / 120 FPS.

### 3.2 Forced Synchronous Layout & Layout Thrashing

*Layout Thrashing* terjadi ketika JavaScript membaca properti geometris elemen (memaksa browser menjalankan layout kalkulasi instan) lalu langsung menulis properti DOM yang membatalkan layout tersebut, dilakukan secara berulang dalam satu frame siklus eksekusi.

```javascript
// ANTI-PATTERN: Layout Thrashing (O(N) Reflow)
for (let i = 0; i < elements.length; i++) {
  // BACA: Memaksa sinkronisasi layout (Style/Layout recalculated)
  const width = elements[i].offsetWidth; 
  // TULIS: Mengotori layout (Invalidates layout)
  elements[i].style.width = (width + 10) + 'px'; 
}

// OPTIMAL: Read-First, Batch-Write-Later (O(1) Reflow)
const widths = [];
for (let i = 0; i < elements.length; i++) {
  widths.push(elements[i].offsetWidth); // Batch Read
}
requestAnimationFrame(() => {
  for (let i = 0; i < elements.length; i++) {
    elements[i].style.width = (widths[i] + 10) + 'px'; // Batch Write
  }
});
```

### 3.3 Micro-Reactivity: The Proxy Pipeline

State reaktif modern dibangun di atas konstruksi `Proxy` dan `Reflect` ES6. `Proxy` mencegat operasi dasar runtime (*traps*) seperti `get`, `set`, dan `deleteProperty`.

Untuk mencegah rendering berulang secara berlebihan (*render thrashing*), mutasi state tidak boleh langsung memanipulasi DOM secara sinkron. Sebaliknya, mutasi harus dijadwalkan ke dalam **Microtask Queue** menggunakan `queueMicrotask` sehingga puluhan perubahan mutasi dalam satu *tick* eksekusi hanya menghasilkan **satu kali** re-render DOM.

```
State Mutation (set trap) 
      |
      v
Tandai Store "Dirty"
      |
      v
Apakah render telah dijadwalkan?
   ├── YA  --> Lewati (deduplicated)
   └── TDK --> queueMicrotask(() => executeFlushBatch())
                    |
                    v
             Async DOM Patch (1x render untuk N mutasi)
```

### 3.4 Web Components & Shadow Boundaries

Web Components adalah kumpulan tiga standar W3C:
1. **Custom Elements**: API pendaftaran tag HTML kustom (`customElements.define('app-element', Class)`).
2. **Shadow DOM**: Isolasi styling dan DOM subtree yang mencegah selector CSS luar bocor ke dalam komponen, serta mencegah selector dalam komponen merusak dokumen induk (*encapsulation boundary*).
3. **HTML Templates (`<template>` & `<slot>`)**: Deklarasi blueprint DOM inaktif yang tidak dievaluasi oleh parser sampai instansiasi runtime dilakukan melalui cloning (`cloneNode(true)`).

---

## 4. Why & What

### Mengapa Memahami Arsitektur Vanilla Sangat Krusial?

Di dunia enterprise, ketergantungan buta pada library level tinggi (React, Vue, Angular) tanpa pemahaman native platform menciptakan risiko sistemik:
- **Abstraksi Bocor (*Leaky Abstractions*)**: Masalah performa berat (memory leaks, layout thrashing, CPU spike) tidak dapat diselesaikan melalui framework abstraction jika engineer tidak mengerti alur kerja browser engine di baliknya.
- **Ketergantungan Ekosistem (*Framework Lock-in*)**: Desain komponen UI berbasis standar web native (Web Components) menjamin interoperabilitas total antartim; micro-frontend dapat mengonsumsi komponen yang sama tanpa memedulikan stack framework hosting.
- **Overhead Runtime**: Aplikasi modern sering kali mengirim megabyte JavaScript ke perangkat klien hanya untuk fungsionalitas UI sederhana, yang secara langsung merusak Core Web Vitals (INP, LCP, CLS).

### Apa yang Dibangun?

Arsitektur produksi berbasis **Frameworkless Modern Architecture**:
1. Single Store State Management berbasis `Proxy` dengan komputasi reaktif dan *asynchronous batched rendering*.
2. Autonomous Component Tree menggunakan **Web Components** yang menerapkan *Shadow DOM*, *Slot projection*, dan *unidirectional custom events*.
3. Sanitizer DOM berbasis *pipeline* defensif untuk mitigasi zero-day XSS injection.

---

## 5. How (Workflow Detail)

Berikut adalah diagram alir dari interaksi pengguna hingga pembaruan tampilan pada sistem:

```
1. User Interaction (Click / Input)
              │
              ▼
2. Custom Element Event Interceptor (Captures & dispatches intent)
              │
              ▼
3. Dispatch Action / Execute State Mutation
              │
              ▼
4. Proxy `set` Trap Fired
   ├── Validasi Skema Data (Type checking & boundary constraints)
   ├── Mutasi Internal State Cache (Immutability guarantee via structural cloning)
   └── Tandai Store sebagai "Dirty"
              │
              ▼
5. Scheduler (Batched Async Engine)
   ├── Cek apakah task rendering sudah terdaftar di Microtask Queue
   └── Jika belum, invoke: `queueMicrotask(flushRender)`
              │
              ▼
6. Microtask Execution (flushRender)
   ├── Loop seluruh subscriber yang bergantung pada state yang berubah
   ├── Ambil data sanitasi (Sanitize string payloads)
   └── Patch Shadow Root DOM via targeted structural updates
              │
              ▼
7. Browser Engine UI Pipeline
   ├── Style Invalidation (Hanya pada Shadow Boundary)
   ├── Composite Pipeline Execution
   └── UI Stabil (Frame selesai di-render)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Restoran Bintang Lima vs Browser Rendering

- **DOM Parsing**: Seperti manajer restoran yang membaca pesanan dari selembar kertas (*order slip*) kata demi kata, lalu mencatatnya di buku manifest restoran.
- **CSSOM Parsing**: Seperti kepala chef yang membaca buku resep dan aturan presentasi meja (*plating guide*).
- **Render Tree**: Daftar piring yang benar-benar akan disajikan ke meja tamu. Makanan yang dibatalkan tamu (`display: none`) tidak akan dimasak ataupun disiapkan.
- **Layout (Reflow)**: Penataan tata letak meja fisik: menghitung berapa milimeter jarak antara garpu, sendok, piring, dan gelas agar pas dengan ukuran meja. Jika seseorang menaruh vas bunga raksasa di tengah meja (*mutasi DOM tanpa ukuran pasti*), pelayan harus memindahkan semua piring kembali (*Forced Reflow*).
- **Paint**: Chef mengoleskan saus, warna sayuran, dan garnish ke atas piring sesuai instruksi presentasi.
- **Compositing**: Pelayan membawa nampan berisi beberapa piring yang sudah selesai ditata rapi ke meja pelanggan menggunakan lift makanan, tanpa mengubah susunan makanan di atas piring tersebut.

```
+-----------------------------------------------------------------------+
| BROWSER MEMORY SPACE                                                  |
|                                                                       |
|  +-----------------------------------------------------------------+  |
|  | GLOBAL EXECUTION CONTEXT                                        |  |
|  |                                                                 |  |
|  |  +---------------------+        +----------------------------+  |  |
|  |  | Reactive Store      |        | Event Bus / Mediators      |  |  |
|  |  |  - Proxy Target     |        |  - Event Subscriptions     |  |  |
|  |  |  - Subscribers Map  |        |  - Custom Event Handlers   |  |  |
|  |  +----------+----------+        +--------------+-------------+  |  |
|  +-------------|----------------------------------|----------------+  |
|                |                                  |                   |
|                | microtask notification           | dispatchEvent     |
|                v                                  v                   |
|  +-----------------------------------------------------------------+  |
|  | SHADOW DOM ROOT BOUNDARY                                        |  |
|  |                                                                 |  |
|  |  <data-table-component>                                         |  |
|  |    #shadow-root (open)                                          |  |
|  |      ├── <style> Encapsulated CSS </style>                     |  |
|  |      ├── <div class="table-container">                         |  |
|  |      │     └── <table> ... </table>                             |  |
|  |      └── <slot name="pagination"></slot>                        |  |
|  +-----------------------------------------------------------------+  |
|                                                                       |
+-----------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Reactive Store dengan Proxy & Microtask Batching

Contoh minimalis berikut menunjukkan mekanisme reaktivitas vanilla yang mengeksekusi re-render secara asinkron untuk mencegah pemborosan komputasi:

```javascript
// core/reactiveStore.js
export function createStore(initialState = {}, onUpdate = () => {}) {
  let isQueued = false;
  
  const state = new Proxy(initialState, {
    set(target, property, value, receiver) {
      if (Reflect.get(target, property, receiver) === value) {
        return true; // Tidak ada perubahan nilai (Idempotent)
      }
      
      const success = Reflect.set(target, property, value, receiver);
      
      if (success && !isQueued) {
        isQueued = true;
        // Batching mutasi via Microtask Queue
        queueMicrotask(() => {
          onUpdate(target);
          isQueued = false;
        });
      }
      return success;
    }
  });

  return state;
}

// Simulasi Penggunaan:
const store = createStore({ counter: 0, text: 'Initial' }, (latestState) => {
  console.log('[Render Engine] DOM Diperbarui dengan state:', JSON.stringify(latestState));
});

// Mutasi sinkron berturut-turut
store.counter = 1;
store.counter = 2;
store.counter = 3;
store.text = 'Batch Complete';

console.log('[App] Seluruh mutasi telah dijalankan secara sinkron.');
// OUTPUT:
// [App] Seluruh mutasi telah dijalankan secara sinkron.
// [Render Engine] DOM Diperbarui dengan state: {"counter":3,"text":"Batch Complete"}
// (Listener HANYA dipanggil 1 kali, bukan 4 kali!)
```

### 7.2 Practical Example: Enterprise Data Grid Web Component

Implementasi komponen Data Grid enterprise berbasis Custom Elements v1, Shadow DOM, state internal reaktif, sanitasi native, dan proteksi memory leak.

```javascript
/**
 * @file EnterpriseDataGrid.js
 * Komponen Web native berkinerja tinggi dengan isolasi Shadow DOM.
 */

class EnterpriseDataGrid extends HTMLElement {
  #shadowRoot;
  #state;
  #isRenderQueued = false;
  #abortController; // Untuk teardown event listener kolektif

  constructor() {
    super();
    this.#shadowRoot = this.attachShadow({ mode: 'open' });
    this.#abortController = new AbortController();

    // Inisialisasi State Reaktif Terisolasi
    this.#state = new Proxy(
      {
        columns: [],
        data: [],
        sortKey: null,
        sortAsc: true,
      },
      {
        set: (target, prop, value) => {
          target[prop] = value;
          this.#scheduleRender();
          return true;
        }
      }
    );
  }

  static get observedAttributes() {
    return ['title'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue !== newValue) {
      this.#scheduleRender();
    }
  }

  connectedCallback() {
    this.#injectBaseStyles();
    this.#bindShadowEvents();
  }

  disconnectedCallback() {
    // PREVENT MEMORY LEAK: Batalkan semua event listener di Shadow DOM
    this.#abortController.abort();
    this.#shadowRoot.innerHTML = '';
  }

  // Public API Methods
  setColumns(cols) {
    if (!Array.isArray(cols)) throw new TypeError('Columns must be an array');
    this.#state.columns = cols;
  }

  setData(rows) {
    if (!Array.isArray(rows)) throw new TypeError('Data must be an array');
    this.#state.data = rows;
  }

  #scheduleRender() {
    if (this.#isRenderQueued) return;
    this.#isRenderQueued = true;

    queueMicrotask(() => {
      this.#render();
      this.#isRenderQueued = false;
    });
  }

  #escapeHtml(str) {
    if (typeof str !== 'string') return String(str ?? '');
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  #injectBaseStyles() {
    const style = document.createElement('style');
    style.textContent = `
      :host {
        display: block;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        overflow: hidden;
        background: #ffffff;
      }
      .grid-header {
        padding: 12px 16px;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        font-weight: 600;
        color: #1e293b;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        text-align: left;
      }
      th {
        background: #f1f5f9;
        padding: 12px 16px;
        font-size: 13px;
        text-transform: uppercase;
        color: #475569;
        cursor: pointer;
        user-select: none;
        border-bottom: 2px solid #cbd5e1;
      }
      th:hover {
        background: #e2e8f0;
      }
      td {
        padding: 12px 16px;
        border-bottom: 1px solid #e2e8f0;
        color: #334155;
        font-size: 14px;
      }
      tr:last-child td {
        border-bottom: none;
      }
      tr:hover td {
        background: #f8fafc;
      }
      .empty-state {
        padding: 24px;
        text-align: center;
        color: #94a3b8;
      }
    `;
    this.#shadowRoot.appendChild(style);
  }

  #bindShadowEvents() {
    const { signal } = this.#abortController;

    // Delegasi Event Terpusat di dalam Shadow Root
    this.#shadowRoot.addEventListener(
      'click',
      (event) => {
        const th = event.target.closest('th[data-key]');
        if (th) {
          const key = th.dataset.key;
          const isAsc = this.#state.sortKey === key ? !this.#state.sortAsc : true;
          
          this.#state.sortKey = key;
          this.#state.sortAsc = isAsc;

          // Dispatch event ke luar boundary Shadow DOM
          this.dispatchEvent(
            new CustomEvent('grid-sort-changed', {
              detail: { key, ascending: isAsc },
              bubbles: true,
              composed: true, // Izinkan menyeberang batas Shadow Root
            })
          );
        }
      },
      { signal }
    );
  }

  #getProcessedData() {
    const { data, sortKey, sortAsc } = this.#state;
    if (!sortKey) return data;

    return [...data].sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];

      if (valA === valB) return 0;
      if (valA == null) return 1;
      if (valB == null) return -1;

      const comparison = valA > valB ? 1 : -1;
      return sortAsc ? comparison : -comparison;
    });
  }

  #render() {
    const processedData = this.#getProcessedData();
    const titleAttr = this.getAttribute('title') || 'Data View';

    let container = this.#shadowRoot.querySelector('.container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'container';
      this.#shadowRoot.appendChild(container);
    }

    container.innerHTML = `
      <div class="grid-header">${this.#escapeHtml(titleAttr)}</div>
      <table>
        <thead>
          <tr>
            ${this.#state.columns
              .map(
                (col) => `
              <th data-key="${this.#escapeHtml(col.key)}">
                ${this.#escapeHtml(col.label)}
                ${this.#state.sortKey === col.key ? (this.#state.sortAsc ? ' ▲' : ' ▼') : ''}
              </th>
            `
              )
              .join('')}
          </tr>
        </thead>
        <tbody>
          ${
            processedData.length === 0
              ? `<tr><td colspan="${this.#state.columns.length || 1}" class="empty-state">No data available</td></tr>`
              : processedData
                  .map(
                    (row) => `
              <tr>
                ${this.#state.columns
                  .map((col) => `<td>${this.#escapeHtml(row[col.key])}</td>`)
                  .join('')}
              </tr>
            `
                  )
                  .join('')
          }
        </tbody>
      </table>
    `;
  }
}

customElements.define('enterprise-data-grid', EnterpriseDataGrid);
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Live High-Frequency Trading Portal (FinTech)

- **Konteks**: Sistem FinTech B2B memproses pembaruan harga valuta asing (*forex*) dan pesanan likuiditas dari WebSocket dengan frekuensi mencapai 5.000 update/detik.
- **Masalah Awal**:
  1. Frontend mengalami *jank* parah: frame rate anjlok hingga 8 FPS, browser tab membeku (*frozen UI*), Total Blocking Time (TBT) > 4.500 ms.
  2. Terjadi memory leak masif: konsumsi RAM naik sebesar 15 MB/menit, mengakibatkan *Out Of Memory (OOM) crash* pada browser trader dalam waktu 3 jam penggunaan aktif.
- **Akar Masalah (Root Cause Analysis)**:
  - Kode lama mengeksekusi pembaruan DOM langsung (`element.textContent = data`) pada setiap payload WebSocket yang masuk, memicu layout & paint secara berulang tanpa throttle (*thousands of mutations per second*).
  - Menggunakan library pihak ketiga yang mendaftarkan listener pada `window` tanpa menyediakan *lifecycle hook cleanup* saat komponen di-detach.
  - Alokasi objek string baru secara berulang di dalam siklus loop tanpa garbage collector sempat menyapu (*memory fragmentation*).
- **Arsitektur Solusi**:
  1. **Message Throttling via Shared ArrayBuffer & Ring Buffer**: Menggabungkan aliran tick harga di tingkat Web Worker.
  2. **Microtask Rendering Scheduler**: Frontend hanya mengambil *snapshot* terkini setiap siklus `requestAnimationFrame` (sinkronisasi frame rate native 60Hz/120Hz).
  3. **In-Place DOM Mutation Pooling**: Mengubah DOM node yang sudah ada menggunakan cache referensi `Node` langsung, tanpa menghancurkan dan merekonstruksi sub-tree menggunakan `innerHTML`.
  4. **Strict Lifecycle Resource Cleanup**: Semua komponen mengimplementasikan lifecycle `disconnectedCallback` dengan `AbortController` yang terikat pada sinyal koneksi portal.
- **Hasil Metrik**:
  - Frame rate stabil di **60 FPS**.
  - Total Blocking Time turun dari **4.500 ms** menjadi **< 40 ms**.
  - Konsumsi memory stabil (*flat*) di angka **65 MB** selama 48 jam uji stres berkelanjutan.

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Kerugian / Risiko | Biaya Operasional / Komputasi |
| :--- | :--- | :--- | :--- |
| **Vanilla Frameworkless Architecture** | - Zero dependencies<br>- Ukuran bundle minimal (< 10KB)<br>- Performa mentah tak tertandingi | - Wajib membangun routing, sanitasi, dan state management sendiri<br>- *Time-to-market* fitur awal lebih lambat | - Biaya pemeliharaan tinggi jika dokumentasi arsitektur internal lemah |
| **Shadow DOM (Open)** | - Isolasi CSS sempurna<br>- Mencegah selector collision | - Font global dan theme context harus diinjeksi via CSS Custom Properties<br>- Styling elemen slot terbatas | - Sedikit memory footprint overhead per shadow root boundary |
| **Proxy-based Batching via `queueMicrotask`** | - Performa rendering otomatis optimal<br>- Mengeliminasi layout thrashing | - Stack trace debugging menjadi asinkron (lebih sulit dilacak)<br>- State mutasi instan tidak langsung tercermin di DOM dalam tick yang sama | - Minimal CPU overhead untuk tracking dirty queue |
| **Virtual DOM Library (e.g. React/Vue)** | - Ekosistem sangat kaya<br>- Kompatibilitas developer market luas | - Overhead bundle size besar (40KB - 150KB+)<br>- Overhead memory untuk mempertahankan VDOM tree ganda di RAM | - Latensi garbage collection meningkat saat data payload masif |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Detached DOM Tree Retention (Memory Leak)

*Kesalahan*: Menyimpan referensi elemen DOM di variabel JavaScript global atau closure, lalu menghapus elemen tersebut dari dokumen menggunakan `element.remove()`. Elemen tersebut tidak akan pernah dibebaskan oleh Garbage Collector (GC).

```javascript
// BUG: Detached DOM Memory Leak
const cache = [];
function createLeak() {
  const el = document.createElement('div');
  el.className = 'heavy-node';
  document.body.appendChild(el);
  cache.push(el); // Referensi tersimpan di global cache
  
  // Nanti di tempat lain:
  el.remove(); // Dihapus dari active DOM tree, tapi TETAP berada di memory heap!
}

// FIX: Pastikan menghapus referensi JS saat menghapus dari DOM
function fixLeak(index) {
  const el = cache[index];
  el.remove();
  cache.splice(index, 1); // Referensi dilepas, GC dapat membebaskan memori
}
```

### 10.2 Layout Thrashing dalam Animasi / Resize Handler

*Kesalahan*: Membaca dimensi geometri di dalam event handler scrolling atau resizing tanpa sinkronisasi rendering frame.

```javascript
// BUG: Pemicu Forced Layout berkali-kali
window.addEventListener('resize', () => {
  const width = document.querySelector('#sidebar').clientWidth; // Read
  document.querySelector('#main').style.marginLeft = `${width}px`; // Write
});

// FIX: Gunakan requestAnimationFrame debounce
let rafId = null;
window.addEventListener('resize', () => {
  if (rafId) cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(() => {
    const width = document.querySelector('#sidebar').clientWidth;
    document.querySelector('#main').style.marginLeft = `${width}px`;
  });
});
```

### 10.3 DOM-based XSS via `innerHTML` Unsanitized Interpolation

*Kesalahan*: Menyisipkan payload dari user/API langsung ke dalam template string `innerHTML`.

```javascript
// CRITICAL VULNERABILITY: XSS Injection
const userInput = '<img src=x onerror="alert(document.cookie)">';
element.innerHTML = `<span class="name">${userInput}</span>`;

// FIX 1: Gunakan textContent jika hanya teks
element.textContent = userInput;

// FIX 2: Gunakan sanitasi string atau Sanitizer API jika harus merender HTML
function sanitizeHTML(str) {
  const temp = document.createElement('div');
  temp.textContent = str;
  return temp.innerHTML;
}
element.innerHTML = `<span class="name">${sanitizeHTML(userInput)}</span>`;
```

---

## 11. Best Practices (Production Checklist)

- [ ] **DOM Sanitization Enforcement**: Jangan pernah menggunakan `innerHTML`, `outerHTML`, atau `document.write` secara langsung tanpa pipeline sanitasi. Gunakan DOMPurify atau sanitasi escape character yang ketat.
- [ ] **Lifecycle Memory Cleanup**: Pastikan setiap Custom Element membersihkan *interval*, *timeout*, WebSockets, dan event listeners di dalam `disconnectedCallback`. Gunakan pola `AbortController` terintegrasi.
- [ ] **Batched DOM Updates**: Kelompokkan seluruh operasi DOM Read terlebih dahulu, baru lanjutkan dengan DOM Write. Gunakan `queueMicrotask` untuk state updates dan `requestAnimationFrame` untuk manipulasi layout/animasi.
- [ ] **Compositor-friendly CSS**: Batasi properti animasi hanya pada `transform` dan `opacity`. Hindari menganimasikan `width`, `height`, `top`, `left`, `margin`, atau `padding`.
- [ ] **Shadow Boundary Encapsulation**: Terapkan enkapsulasi CSS menggunakan Shadow DOM guna mencegah kebocoran rule CSS pada skala ratusan modul micro-frontend.
- [ ] **Event Delegation Architecture**: Hindari mengikat listener pada setiap baris/elemen dinamis secara individual. Kaitkan satu listener pada root container dan manfaatkan `event.target.closest()`.
- [ ] **Content Security Policy (CSP)**: Terapkan header CSP `script-src 'self'` tanpa izinan `unsafe-inline` untuk melumpuhkan eksekusi skrip berbahaya di level protokol browser.

---

## 12. Hands-on Practice

Struktur direktori kerja praktikum:

```
hands-on/m02/
├── index.html
├── src/
│   ├── core/
│   │   ├── Store.js
│   │   └── Sanitizer.js
│   ├── components/
│   │   ├── MetricCard.js
│   │   └── ActivityFeed.js
│   └── app.js
└── styles/
    └── main.css
```

### Langkah 1: Implementasi Sanitizer

Buat berkas `hands-on/m02/src/core/Sanitizer.js`:

```javascript
export class Sanitizer {
  static escape(input) {
    if (typeof input !== 'string') return String(input ?? '');
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#x27;',
      '/': '&#x2F;',
    };
    return input.replace(/[&<>"'/]/g, (match) => map[match]);
  }
}
```

### Langkah 2: Implementasi Reactive Store Core

Buat berkas `hands-on/m02/src/core/Store.js`:

```javascript
export class Store {
  #state;
  #subscribers = new Set();
  #isBatchQueued = false;

  constructor(initialData = {}) {
    this.#state = new Proxy(initialData, {
      set: (target, key, val) => {
        if (target[key] === val) return true;
        target[key] = val;
        this.#notify();
        return true;
      },
      get: (target, key) => {
        return target[key];
      }
    });
  }

  get state() {
    return this.#state;
  }

  subscribe(callback) {
    this.#subscribers.add(callback);
    callback(this.#state); // Initial run
    return () => this.#subscribers.delete(callback); // Unsubscribe cleanup
  }

  #notify() {
    if (this.#isBatchQueued) return;
    this.#isBatchQueued = true;

    queueMicrotask(() => {
      this.#subscribers.forEach((fn) => fn(this.#state));
      this.#isBatchQueued = false;
    });
  }
}
```

### Langkah 3: Implementasi Web Component `metric-card`

Buat berkas `hands-on/m02/src/components/MetricCard.js`:

```javascript
import { Sanitizer } from '../core/Sanitizer.js';

export class MetricCard extends HTMLElement {
  #shadowRoot;

  constructor() {
    super();
    this.#shadowRoot = this.attachShadow({ mode: 'open' });
  }

  static get observedAttributes() {
    return ['label', 'value', 'trend'];
  }

  connectedCallback() {
    this.#render();
  }

  attributeChangedCallback() {
    this.#render();
  }

  #render() {
    const label = this.getAttribute('label') || '-';
    const value = this.getAttribute('value') || '0';
    const trend = this.getAttribute('trend') || 'neutral';

    this.#shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .label {
          font-size: 12px;
          color: #64748b;
          text-transform: uppercase;
          margin-bottom: 4px;
        }
        .value {
          font-size: 24px;
          font-weight: 700;
          color: #0f172a;
        }
        .trend-up { color: #16a34a; }
        .trend-down { color: #dc2626; }
      </style>
      <div class="label">${Sanitizer.escape(label)}</div>
      <div class="value ${Sanitizer.escape(trend)}">${Sanitizer.escape(value)}</div>
    `;
  }
}

customElements.define('metric-card', MetricCard);
```

### Langkah 4: Implementasi Root Bootstrap

Buat berkas `hands-on/m02/src/app.js`:

```javascript
import { Store } from './core/Store.js';
import './components/MetricCard.js';

const appStore = new Store({
  serverLoad: '24%',
  activeSessions: 1420,
  latency: '12ms',
});

// Bind UI ke state store
const loadMetric = document.getElementById('metric-load');
const sessionsMetric = document.getElementById('metric-sessions');
const latencyMetric = document.getElementById('metric-latency');

appStore.subscribe((state) => {
  loadMetric.setAttribute('value', state.serverLoad);
  sessionsMetric.setAttribute('value', state.activeSessions);
  latencyMetric.setAttribute('value', state.latency);
});

// Simulasi High-Frequency Streaming Events
const updateBtn = document.getElementById('btn-simulate');
updateBtn.addEventListener('click', () => {
  console.log('[App] Mengirim 10 mutasi serentak...');
  for (let i = 1; i <= 10; i++) {
    appStore.state.serverLoad = `${30 + i}%`;
    appStore.state.activeSessions = 1420 + i;
    appStore.state.latency = `${10 + (i % 3)}ms`;
  }
  console.log('[App] Mutasi selesai dikirim ke Proxy.');
});
```

### Langkah 5: Wrapper HTML

Buat berkas `hands-on/m02/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Enterprise Vanilla Architecture Testbed</title>
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline';">
  <link rel="stylesheet" href="styles/main.css">
</head>
<body>
  <h1>Mission Control Telemetry</h1>
  <div style="display: flex; gap: 16px; margin-bottom: 24px;">
    <metric-card id="metric-load" label="CPU Load" value="0%" trend="trend-up"></metric-card>
    <metric-card id="metric-sessions" label="Active Users" value="0"></metric-card>
    <metric-card id="metric-latency" label="Roundtrip Latency" value="0ms"></metric-card>
  </div>
  <button id="btn-simulate">Simulate High-Frequency Stream</button>

  <script type="module" src="src/app.js"></script>
</body>
</html>
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `MetricCard` pada Hands-on Practice untuk menambahkan properti atribut opsional `currency` (misal: `USD`, `IDR`). Format nilai data secara visual menggunakan native API `Intl.NumberFormat` saat atribut tersebut aktif.

### Level Medium
Perluas implementasi `Store` di `src/core/Store.js` agar mendukung mekanisme **History Tracking (Undo/Redo Engine)**. 
- Implementasikan metode `store.undo()` dan `store.redo()`.
- Pastikan bahwa navigasi history tidak memicu perulangan tak terbatas (*infinite loop*) pada traps Proxy dan tetap memanfaatkan `queueMicrotask` batching engine.

### Level Hard
Bangun komponen `<virtual-scroller-table>` menggunakan Web Components dan Shadow DOM yang mampu merender kumpulan data sebesar **100.000 baris** secara instan:
- Hanya boleh merender jumlah elemen fisik DOM secukupnya yang masuk ke dalam *viewport window* (misal: hanya merender 25 baris visible + 5 baris buffer di atas dan bawah).
- Tangani perhitungan offset *scroll top* secara matematis menggunakan kalkulasi tinggi baris statis.
- Batasi komputasi reflow saat event scrolling menggunakan `requestAnimationFrame`.

---

## 14. Challenge

### Skenario: Arsitektur Enterprise Micro-Frontend Runtime Shell

Anda ditugaskan sebagai Principal Architect untuk merancang platform web enterprise tanpa dependensi framework komersial (*zero-dependency frameworkless shell*). Shell ini harus mampu memuat 3 aplikasi mikro independen yang dikembangkan oleh 3 divisi berbeda:

**Spesifikasi Persyaratan Sistem:**
1. **Sandboxing Penuh**: Setiap aplikasi mikro berjalan di dalam `Shadow DOM (closed)` miliknya sendiri untuk menjamin integritas CSS dan struktur DOM.
2. **State & Event Bus Terisolasi**: Rancang sebuah `MessageBus` global menggunakan `CustomEvent` yang menerapkan verifikasi origin dan permission contract. Aplikasi mikro A tidak boleh dapat memodifikasi state privat aplikasi mikro B tanpa persetujuan.
3. **Resilience & Fault Isolation**: Jika salah satu Custom Element dari aplikasi mikro melempar runtime exception yang tidak tertangani (*uncaught exception*) atau mengalami layout freeze, host shell harus mampu mengisolasi error tersebut, mencopot elemen yang rusak dari active tree, membersihkan memory heap, dan menampilkan antarmuka *fallback recovery* tanpa me-refresh halaman browser.
4. **Memory Strict Compliance**: Pastikan alur *mount* dan *unmount* aplikasi mikro lolos dari deteksi kebocoran memori (0 byte growth) di Chrome Heap Snapshot setelah diuji siklus *mount-unmount* sebanyak 100 kali berturut-turut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)

1. **Tahapan mana dalam Critical Rendering Path yang bertanggung jawab menentukan koordinat posisi spasial dan ukuran dimensi node?**
   - A) Paint
   - B) CSSOM Parsing
   - C) Layout (Reflow)
   - D) Compositing

2. **Apa yang membedakan microtask queue (`queueMicrotask`) dari macrotask queue (`setTimeout`) dalam kaitannya dengan rendering browser?**
   - A) Microtask dieksekusi setelah browser menyelesaikan paint frame.
   - B) Semua microtask yang tertunda akan dikuras habis (*flushed*) sebelum browser melanjutkan ke siklus render berikutnya.
   - C) Macrotask memiliki prioritas lebih tinggi daripada microtask.
   - D) Microtask berjalan di thread GPU secara paralel.

3. **Manakah metode native API yang tepat untuk mendaftarkan Web Component kustom ke browser engine?**
   - A) `window.registerComponent('x-element', ElementClass)`
   - B) `document.createElement('x-element', { is: ElementClass })`
   - C) `customElements.define('x-element', ElementClass)`
   - D) `document.shadowRoot.attach('x-element', ElementClass)`

4. **Karakteristik utama dari `Shadow DOM` dengan mode `open` adalah:**
   - A) CSS di luar shadow DOM dapat langsung menembus dan mengubah class di dalam shadow root.
   - B) Objek `shadowRoot` dapat diakses dari luar melalui properti `element.shadowRoot`.
   - C) Tidak membutuhkan tag HTML templates.
   - D) Komponen tersebut kebal terhadap serangan XSS tanpa perlu sanitasi data.

5. **Apa fungsi dari `disconnectedCallback` dalam siklus hidup Custom Elements?**
   - A) Dipanggil saat komponen pertama kali dibuat di memori sebelum masuk ke DOM.
   - B) Dipanggil ketika atribut yang diamati (*observedAttributes*) mengalami perubahan.
   - C) Dipanggil ketika elemen dilepaskan dari pohon dokumen DOM aktif (fase krusial cleanup).
   - D) Menghentikan rendering jika koneksi internet klien terputus.

---

### Bagian 2: Intermediate (Analisis Singkat)

1. Jelaskan mengapa pemanggilan properti seperti `offsetWidth` atau `scrollTop` secara langsung setelah mengubah properti gaya CSS elemen (`element.style.height = ...`) menyebabkan degradasi performa yang disebut *Forced Synchronous Layout*!
2. Mengapa penggunaan `Proxy` lebih direkomendasikan daripada `Object.defineProperty` dalam perancangan sistem reaktivitas state berskala besar?
3. Sebutkan dua kondisi struktural yang membuat browser engine mampu mengeksekusi animasi murni pada tahap *Compositing* tanpa memicu *Layout* dan *Paint*!
4. Jelaskan bagaimana serangan *DOM-based Cross-Site Scripting* dapat tereksploitasi melalui manipulasi `location.hash` dan apa langkah mitigasi struktural terbaik tanpa bergantung pada sanitasi pihak ketiga!
5. Bagaimana mekanisme kerja sinyal `AbortSignal` dari `AbortController` dalam menyederhanakan manajemen pembatalan multi event-listener saat komponen UI dilepas dari DOM?

---

### Bagian 3: Skenario Kasus Produksi

1. **Skenario Kasus 1**:  
   Sebuah aplikasi pelacakan log real-time merender 500 baris teks per detik ke dalam kontainer `<div>`. Setelah berjalan selama 15 menit, penggunaan memori tab browser melonjak hingga 1,8 GB dan browser menampilkan status "Aw, Snap! (Out of Memory)". Analisis apa yang terjadi pada Garbage Collector dan jelaskan arsitektur solusi untuk mengatasinya!

2. **Skenario Kasus 2**:  
   Anda mengintegrasikan Web Component internal ke dalam aplikasi portal micro-frontend pihak ketiga. Komponen Anda menggunakan Shadow DOM. Namun, warna tema korporat (`--primary-color`) yang didefinisikan di dokumen luar tidak teraplikasikan ke tombol di dalam Shadow DOM Anda. Mengapa hal ini terjadi dan bagaimana mekanisme arsitektur resmi untuk mengekspos styling yang aman menembus batas Shadow DOM?

3. **Skenario Kasus 3**:  
   Audit performa Google Lighthouse menunjukkan metrik *Interaction to Next Paint* (INP) sebesar 680 ms (berwarna merah/buruk) pada sebuah halaman formulir entri data yang panjang. Setelah diselidiki, terdapat event listener `input` pada level dokumen yang menjalankan validasi regex berat dan memperbarui pesan status error di DOM secara langsung di setiap ketukan keyboard. Berikan langkah remedi konkret untuk memangkas INP hingga di bawah 100 ms!

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Bagian 1
1. **C** — Layout (Reflow) mengalkulasi koordinat dan ukuran geometris node.
2. **B** — Antrean microtask diproses tuntas sebelum fase render browser berikutnya dieksekusi.
3. **C** — `customElements.define` adalah spesifikasi standar W3C.
4. **B** — Mode `open` memungkinkan host instance memiliki properti `.shadowRoot` yang dapat dibaca JavaScript luar.
5. **C** — `disconnectedCallback` adalah lifecycle hook untuk pembersihan sumber daya saat elemen dicopot dari DOM.

#### Kunci Bagian 2
1. Mengubah CSS menandai layout sebagai *dirty/invalid*. Membaca properti geometris (`offsetWidth`) memaksa browser untuk langsung menjalankan rekalkulasi layout saat itu juga secara sinkron agar nilainya akurat, menghancurkan optimasi *lazy batching* bawaan browser.
2. `Proxy` dapat mencegat operasi penambahan/penghapusan properti baru secara dinamis serta manipulasi indeks array tanpa perlu mendefinisikan ulang getter/setter per properti seperti pada `Object.defineProperty`.
3. Ketika animasi hanya memanipulasi properti yang dapat didelegasikan ke thread GPU Compositor (yaitu `transform` dan `opacity`), dan elemen tersebut telah dialokasikan ke compositing layer mandiri (misal via `will-change: transform`).
4. Eksploitasi terjadi ketika string dari `location.hash` dieksekusi langsung ke sink yang mengevaluasi skrip seperti `element.innerHTML = location.hash`. Mitigasi struktural: gunakan sink aman seperti `element.textContent` atau parsing via `URLSearchParams` dengan validasi tipe data ketat dan deklarasi CSP tanpa `unsafe-inline`.
5. Satu instance `AbortController` dapat dioperasikan ke puluhan pemanggilan `addEventListener(type, fn, { signal })`. Saat komponen di-unmount, cukup panggil satu kali `abortController.abort()` untuk mencabut seluruh listener tersebut secara otomatis tanpa perlu mereferensikan nama fungsinya satu per satu.

#### Solusi Panduan Skenario Bagian 3
1. **Solusi Kasus 1**: Terjadi penumpukan node tak terbatas di DOM tree aktif. Solusi: Gunakan pola *Sliding Window / Buffer Cap* (misal: batasi maksimum hanya 500 node log di DOM pada satu waktu dengan membuang node terlama `container.firstElementChild.remove()`), atau gunakan teknik *Virtual Scroll* dan alokasi log mentah ke dalam ring buffer di JavaScript Array tanpa langsung menaruhnya ke DOM.
2. **Solusi Kasus 2**: Isolasi Shadow DOM memblokir selektor CSS luar, namun properti kustom CSS (*CSS Variables*) dapat menembus batasan Shadow DOM. Solusi: Pada stylesheet shadow root, gunakan CSS Custom Properties: `background-color: var(--primary-color, #defaultColor)`. Solusi alternatif: deklarasikan atribut `part="action-button"` pada tombol dan atur styling dari luar menggunakan selektor pseudo-element `::part(action-button)`.
3. **Solusi Kasus 3**: Remedi: (1) Terapkan teknik *Debounce* pada handler input agar eksekusi komputasi ditunda hingga pengguna jeda mengetik (misal jeda 150ms). (2) Pindahkan komputasi validasi regex berat keluar dari main thread menggunakan *Web Worker*. (3) Bungkus pembaruan pesan error DOM dalam `requestAnimationFrame` atau jadwalkan via `scheduler.yield()` / `setTimeout(..., 0)` agar thread utama dapat segera me-render frame animasi ketukan tombol.

---

## 16. Summary

- **Browser Performance Foundation**: Performa tinggi pada frontend bukan ditentukan oleh framework, melainkan oleh pemahaman mendalam atas *Critical Rendering Path*. Menghindari *Layout Thrashing* dengan memisahkan siklus baca dan tulis DOM adalah fondasi utama UI 60/120 FPS.
- **Batched Reactive Architecture**: Mengombinasikan `Proxy` dengan `queueMicrotask` memungkinkan arsitektur state terpusat yang reaktif, elegan, dan hemat komputasi tanpa memerlukan kompilator rumit.
- **Enterprise Web Components**: Standar Custom Elements v1 dan Shadow DOM menyediakan isolasi struktural dan enkapsulasi CSS tingkat platform, menjadikannya arsitektur ideal untuk micro-frontend dan design system lintas tim.
- **Defensive Engineering**: Keandalan aplikasi enterprise diukur dari manajemen siklus hidup objek (mencegah *memory leak* melalui `AbortController`) dan proteksi proaktif terhadap serangan injeksi *DOM-based XSS* melalui sanitasi ketat dan penegakan *Content Security Policy*.