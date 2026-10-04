# Kurikulum Enterprise Frontend Engineering: Core Foundations
## Bab 05: Materi Lanjutan
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menganalisis siklus hidup *Critical Rendering Path* (CRP) dan mengeksekusi optimasi layout engine browser untuk mengeliminasi *layout thrashing* dan *forced synchronous layout*.
- Merancang arsitektur reaktivitas data state-driven berbasis native JavaScript `Proxy` dan `Reflect` dengan pattern pub/sub terdistribusi tanpa dependensi eksternal.
- Mengimplementasikan teknik pemrosesan asynchronous berkinerja tinggi memanfaatkan kombinasi *Microtask Queue*, *Macrotask Queue*, `requestAnimationFrame`, serta *Web Workers* untuk *off-main-thread computation*.
- Mengisolasi komponen UI menggunakan Web Components API (Custom Elements, Shadow DOM v1, HTML Templates) yang memenuhi standar enkapsulasi tingkat enterprise.
- Mengaudit dan mengoptimasi metrik Core Web Vitals (LCP, INP, CLS) pada skala produksi menggunakan Performance Profiler dan resource hints.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, engineer wajib menguasai:
- **Core JavaScript Engine Mechanics**: Eksekusi konteks, *call stack*, lexical scope, closures, prototipikal inheritance, dan ES6+ syntax.
- **Asynchronous Foundations**: `Promise`, `async/await`, penanganan error network (`fetch`), dan dasar-dasar Event Loop.
- **DOM & CSSOM Manipulation**: Penggunaan DOM API dasar (`querySelector`, `addEventListener`), CSS specificity, dan box model.
- **Tooling Environment**: Pengoperasian Node.js runtime, Package Manager (pnpm/npm), dan dasar konfigurasi bundler (Vite/Rollup).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Browser Engine Pipeline & Critical Rendering Path (CRP)

Browser engine modern (seperti Blink pada Chromium atau WebKit pada Safari) memproses dokumen melalui serangkaian pipeline multi-threaded:

```
[HTML Stream] ---> Tokenisasi ---> Parsing ---> DOM Tree  
                                                    \
[CSS Stream]  ---> Tokenisasi ---> Parsing ---> CSSOM Tree ---> [Render Tree]
                                                                     |
                                                               [Layout / Reflow]
                                                                     |
                                                               [Paint Phase]
                                                                     |
                                                             [Composite Layers] ---> GPU VRAM
```

1. **DOM Construction**: HTML diurai menjadi token, kemudian dikonversi menjadi *Nodes*, lalu disusun membentuk *DOM Tree*. Proses ini bersifat *incremental* (dapat dibangun selagi data di-stream).
2. **CSSOM Construction**: CSS diurai menjadi token dan node hierarkis. Berbeda dari DOM, CSSOM bersifat *render-blocking* penuh karena browser tidak dapat merender subtree sebagian yang gayanya berpotensi ditimpa (*cascading*) di akhir stylesheet.
3. **Render Tree Generation**: Kombinasi DOM dan CSSOM. Node dengan `display: none` diabaikan sepenuhnya dari Render Tree, sedangkan elemen dengan `visibility: hidden` tetap disertakan karena mempertahankan dimensi spasial.
4. **Layout (Reflow)**: Kalkulasi geometri presisi (koordinat $X, Y$, lebar, tinggi) dari setiap node pada Render Tree terhadap viewport. Kalkulasi ini menggunakan algoritma rekursif *box-model positioning*.
5. **Paint**: Konversi geometri node menjadi piksel visual pada layar (warna, border, bayangan, teks). Operasi ini dipecah ke dalam layer-layer terpisah (*GraphicsLayers*).
6. **Compositing**: Mengirimkan layer-layer cat ke GPU melalui Thread Compositor. Mengubah properti seperti `transform` dan `opacity` hanya memicu tahapan Compositing, melewati Layout dan Paint secara total (*zero-cost reflow/paint*).

#### B. JavaScript Event Loop: Microtasks vs Macrotasks vs Rendering Pipeline

Pusat kendali eksekusi browser single-threaded diatur oleh Event Loop dengan determinisme ketat:

```
 +--------------------------------------------------------------------+
 |                            CALL STACK                              |
 +--------------------------------------------------------------------+
                                   | (Stack Empty)
                                   v
 +--------------------------------------------------------------------+
 |                        MICROTASKS QUEUE                            |
 |  (Promise.then, MutationObserver, queueMicrotask)                  |
 |  * Eksekusi habis hingga queue kosong secara rekursif               |
 +--------------------------------------------------------------------+
                                   |
                                   v
 +--------------------------------------------------------------------+
 |                       ANIMATION FRAME CALLBACKS                    |
 |  (requestAnimationFrame - Tepat sebelum Paint)                     |
 +--------------------------------------------------------------------+
                                   |
                                   v
 +--------------------------------------------------------------------+
 |                        RENDERING ENGINE                            |
 |  Style Calc -> Layout -> Paint -> Composite                        |
 +--------------------------------------------------------------------+
                                   |
                                   v
 +--------------------------------------------------------------------+
 |                         MACROTASK QUEUE                            |
 |  (setTimeout, setInterval, I/O, UI Events, MessageChannel)         |
 |  * Ambil tepat SATU macrotask per tick                             |
 +--------------------------------------------------------------------+
```

- **Drain to Exhaustion**: Microtask queue harus dikosongkan secara absolut sebelum eksekusi browser dapat berlanjut ke tahapan rendering atau macrotask berikutnya. Membuat chain Promise yang tidak berujung (`recursive queueMicrotask`) akan membekukan UI (*starvation*).
- **Rendering Opportunity**: Browser berusaha melakukan render pada interval sinkron refresh rate layar (misal: 60Hz = 16.6ms per frame, 120Hz = 8.3ms per frame). Jika main thread terblokir oleh eksekusi sinkronus lebih dari interval ini, terjadi *frame drop* (*jank*).

#### C. Arsitektur Reaktivitas Berbasis Meta-Programming (`Proxy` & `Reflect`)

Sistem reaktivitas modern mengandalkan abstraksi interceptor meta-programming untuk mengamati mutasi state tanpa setter/getter manual:

1. **Target**: Plain JavaScript Object/Array yang menyimpan representasi state murni.
2. **Handler Trap**: Intersepsi terhadap operasi fundamental internal JavaScript via metode internal `[[Get]]`, `[[Set]]`, `[[DeleteProperty]]`.
3. **Dependency Tracking (`track`)**: Selama eksekusi fungsi komputasi atau render, akses terhadap properti via `[[Get]]` mendaftarkan efek (*Subscriber Effect*) yang aktif ke dalam `WeakMap` dependensi.
4. **Trigger Mechanism (`trigger`)**: Mutasi properti via `[[Set]]` mencari seluruh efek yang terasosiasi di dalam `WeakMap` dan menjadwalkan eksekusi ulangnya via microtask queue untuk mencegah *duplicate renders*.

---

### 4. Why & What

| Dimensi Arsitektural | Pendekatan Naif / Tradisional | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Mutasi DOM** | Mengubah DOM langsung secara berulang di dalam iterasi loop (`element.style.width = ...`). | Batch mutation, memanfaatkan `requestAnimationFrame`, CSS containment, dan dirty checking. |
| **Pengelolaan State** | Global variable dengan manual DOM re-rendering; coupling ketat antara data layer dan view layer. | Reactive Data-Store (Fine-grained reactivity berbasis `Proxy`), immutable boundary, Unidirectional Data Flow (UDF). |
| **Komponen UI** | Template string HTML disuntik via `innerHTML`, CSS polutif terhadap global namespace. | Web Components (Shadow DOM v1), isolasi style token level host, native template instansiasi via `<template>`. |
| **Komputasi Berat** | Dijalankan langsung di Main Thread; UI mengalami freeze selama pemrosesan data (array > 100k item). | Off-main-thread processing via Web Workers / Web Assembly, transfer buffer berbasis `ArrayBuffer` (*Zero-copy transfer*). |

---

### 5. How (Workflow Detail)

Alur kerja perancangan antarmuka reaktif berkinerja tinggi di tingkat produksi:

```
[User Action / Network Event]
             │
             ▼
[State Mutation via Proxy] ──> Trap [[Set]] aktif
             │
             ├──> Eksekusi Reflect.set()
             │
             ▼
[Dependency Graph Lookup] ──> Ambil subscribers dari WeakMap<Target, Map<Prop, Set<Effect>>>
             │
             ▼
[Microtask Batch Scheduler] ──> Masukkan invalidasi ke Set komputasi
             │
             ▼
[Flushing Microtask Queue] ──> Batching per frame
             │
             ▼
[requestAnimationFrame Execution] ──> Mutasi DOM secara terisolasi (Read-then-Write phase)
             │
             ▼
[Compositor / GPU Paint] ──> Selesai tanpa jank
```

1. **State Mutation Phase**: Modifikasi nilai pada reactive store memicu trap `set`.
2. **Dependency Resolution**: Engine mencocokkan target dan properti pada registry dependensi (`WeakMap` memori aman, otomatis garbage collected jika objek target didestruksi).
3. **Batch Scheduling**: Hindari eksekusi efek secara langsung. Masukkan efek ke dalam deduping queue (`Set`). Daftarkan microtask via `queueMicrotask` untuk mengeksekusi (*flush*) queue sekali saja di akhir tick JavaScript.
4. **Frame Sync Execution**: Jika efek melibatkan mutasi visual langsung, delegasikan tahap akhir ke `requestAnimationFrame` untuk memastikan operasi eksekusi DOM sinkron dengan refresh rate GPU.

---

### 6. Analogi & Diagram ASCII

#### Analogi: Pabrik Otomasi Logistik (Browser Engine)
Bayangkan sebuah pabrik manufaktur:
- **DOM/CSSOM** adalah *Cetak Biru Arsitektur*.
- **Main Thread** adalah *Jalur Rel Tunggal* dalam pabrik. Segala jenis kereta (eksekusi JavaScript, penghitungan cetak biru, pengecatan dinding) berjalan di atas rel yang sama.
- **Microtask** adalah *Instruksi Darurat Inspektur*: Sebelum kereta berikutnya boleh masuk rel, seluruh instruksi darurat yang menumpuk di meja harus dieksekusi detik itu juga.
- **Macrotask** adalah *Jadwal Pengiriman Reguler Kontainer*: Hanya satu kontainer dibuka per siklus kerja.
- **Layout Thrashing** terjadi ketika operator menyuruh mandor mengukur ulang seluruh denah pabrik (*Read*), lalu langsung memindahkan tiang pancang (*Write*), lalu mengukur ulang lagi (*Read*), berulang kali. Pabrik macet total.

#### Diagram: Layout Thrashing vs Batch Rendering

```
PENDEKATAN BURUK (Layout Thrashing):
Main Thread: ──[JS: Read]─[JS: Write]─[Reflow!]─[JS: Read]─[JS: Write]─[Reflow!]──> (Jank Frame: 45ms)
                               ^ Forced                   ^ Forced
                                 Synchronous                Synchronous
                                 Layout                     Layout

PENDEKATAN ENTERPRISE (Batched Mutex Operations):
Main Thread: ──[JS: Read 1 & 2]─[JS: Write 1 & 2]───────────────────────────────> [Layout & Paint]
              |─────── Phase 1: Pure Read ───────||────── Phase 2: Pure Write ────|   (Smooth: 4ms)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Deteksi Layout Thrashing & Perbaikannya

```javascript
// BURUK: Membaca geometri lalu menulis style secara berulang dalam loop (Layout Thrashing)
function resizeBad(elements) {
  for (let i = 0; i < elements.length; i++) {
    // READ (memicu browser menghitung layout secara sinkron jika ada pending writes)
    const currentHeight = elements[i].clientHeight;
    // WRITE (membuat layout saat ini dirty/invalid)
    elements[i].style.height = `${currentHeight + 10}px`;
  }
}

// BAIK: Pisahkan fase pembacaan (Batch Read) dan penulisan (Batch Write)
function resizeOptimized(elements) {
  const heights = [];
  
  // FASE 1: BATCH READ (Query DOM)
  for (let i = 0; i < elements.length; i++) {
    heights.push(elements[i].clientHeight);
  }
  
  // FASE 2: BATCH WRITE (Mutasi DOM via rAF untuk frame alignment)
  requestAnimationFrame(() => {
    for (let i = 0; i < elements.length; i++) {
      elements[i].style.height = `${heights[i] + 10}px`;
    }
  });
}
```

#### B. Practical Enterprise Example: Micro-Reactive Store Engine dengan Scheduler

File: `reactive-store.ts` (Implementasi native state manager reaktif berbasis batched microtask).

```typescript
type EffectSubscriber = () => void;

// WeakMap memastikan tidak ada memory leak saat target object dilepas dari memori
const targetMap = new WeakMap<object, Map<string | symbol, Set<EffectSubscriber>>>();
let activeEffect: EffectSubscriber | null = null;
const effectQueue = new Set<EffectSubscriber>();
let isFlushing = false;

/**
 * Mendaftarkan ketergantungan antara properti dan subscriber yang aktif
 */
function track(target: object, key: string | symbol): void {
  if (!activeEffect) return;

  let depsMap = targetMap.get(target);
  if (!depsMap) {
    depsMap = new Map();
    targetMap.set(target, depsMap);
  }

  let dep = depsMap.get(key);
  if (!dep) {
    dep = new Set();
    depsMap.set(key, dep);
  }

  dep.add(activeEffect);
}

/**
 * Memicu eksekusi seluruh subscriber yang bergantung pada properti
 */
function trigger(target: object, key: string | symbol): void {
  const depsMap = targetMap.get(target);
  if (!depsMap) return;

  const dep = depsMap.get(key);
  if (!dep) return;

  // Masukkan seluruh subscriber ke antrean batching
  dep.forEach((effect) => effectQueue.add(effect));
  scheduleFlush();
}

/**
 * Menjadwalkan pengosongan antrean komputasi via Microtask Queue
 */
function scheduleFlush(): void {
  if (isFlushing) return;
  isFlushing = true;

  queueMicrotask(() => {
    try {
      effectQueue.forEach((effect) => effect());
    } finally {
      effectQueue.clear();
      isFlushing = false;
    }
  });
}

/**
 * Pendaftaran Reactive Effect
 */
export function createEffect(fn: EffectSubscriber): void {
  const effectWrapper: EffectSubscriber = () => {
    activeEffect = effectWrapper;
    try {
      fn();
    } finally {
      activeEffect = null;
    }
  };

  // Eksekusi inisial untuk mengumpulkan dependencies
  effectWrapper();
}

/**
 * Deep Proxy Reactive State Creator
 */
export function createReactiveState<T extends object>(target: T): T {
  const handler: ProxyHandler<T> = {
    get(targetObj, prop, receiver) {
      const result = Reflect.get(targetObj, prop, receiver);
      track(targetObj, prop);
      
      // Auto-wrap nested objects (Deep Reactivity on demand)
      if (typeof result === 'object' && result !== null) {
        return createReactiveState(result);
      }
      return result;
    },
    set(targetObj, prop, value, receiver) {
      const oldValue = Reflect.get(targetObj, prop, receiver);
      if (oldValue === value) return true;

      const success = Reflect.set(targetObj, prop, value, receiver);
      if (success) {
        trigger(targetObj, prop);
      }
      return success;
    },
    deleteProperty(targetObj, prop) {
      const hasKey = Reflect.has(targetObj, prop);
      const success = Reflect.deleteProperty(targetObj, prop);
      if (hasKey && success) {
        trigger(targetObj, prop);
      }
      return success;
    }
  };

  return new Proxy(target, handler);
}
```

File: `data-grid-component.ts` (Implementasi Web Component yang memanfaatkan Reactive Store).

```typescript
import { createReactiveState, createEffect } from './reactive-store';

interface MetricItem {
  id: string;
  label: string;
  value: number;
}

export class EnterpriseDataGrid extends HTMLElement {
  private shadow: ShadowRoot;
  public state: { metrics: MetricItem[]; filter: string };

  constructor() {
    super();
    this.shadow = this.attachShadow({ mode: 'open' });
    
    // Inisialisasi reactive state
    this.state = createReactiveState({
      metrics: [] as MetricItem[],
      filter: ''
    });

    this.renderBase();
  }

  connectedCallback(): void {
    // Daftarkan reactive effect: update subtree hanya saat data state termutasi
    createEffect(() => {
      this.updateView();
    });

    this.bindEvents();
  }

  private renderBase(): void {
    this.shadow.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          contain: content; /* Isolasi layout & paint optimization */
        }
        .grid-container {
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 16px;
          background: #ffffff;
        }
        .search-input {
          width: 100%;
          padding: 8px 12px;
          margin-bottom: 12px;
          box-sizing: border-box;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
        }
        .data-list {
          list-style: none;
          padding: 0;
          margin: 0;
          max-height: 300px;
          overflow-y: auto;
        }
        .data-item {
          display: flex;
          justify-content: space-between;
          padding: 8px 12px;
          border-bottom: 1px solid #f1f5f9;
        }
        .data-item:last-child { border-bottom: none; }
      </style>
      <div class="grid-container">
        <input type="text" class="search-input" placeholder="Filter metrics..." />
        <ul class="data-list" id="metrics-target"></ul>
      </div>
    `;
  }

  private bindEvents(): void {
    const input = this.shadow.querySelector('.search-input') as HTMLInputElement;
    input.addEventListener('input', (e) => {
      this.state.filter = (e.target as HTMLInputElement).value;
    });
  }

  private updateView(): void {
    const listContainer = this.shadow.querySelector('#metrics-target');
    if (!listContainer) return;

    const filtered = this.state.metrics.filter((m) =>
      m.label.toLowerCase().includes(this.state.filter.toLowerCase())
    );

    // DocumentFragment untuk meminimalisir reflow saat manipulasi batch node
    const fragment = document.createDocumentFragment();

    filtered.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'data-item';
      li.setAttribute('data-id', item.id);
      
      const spanLabel = document.createElement('span');
      spanLabel.textContent = item.label;
      
      const spanVal = document.createElement('strong');
      spanVal.textContent = item.value.toLocaleString();

      li.append(spanLabel, spanVal);
      fragment.appendChild(li);
    });

    listContainer.replaceChildren(fragment);
  }
}

customElements.define('enterprise-data-grid', EnterpriseDataGrid);
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Skenario: Financial Real-time Dashboard Telemetry
- **Latar Belakang**: Platform analitik valuta asing enterprise memproses stream WebSocket frekuensi tinggi (hingga 800 tick per detik) dengan 50 instans grafik mini dan tabel order book secara live.
- **Permasalahan**: Implementasi awal menggunakan React/Vanilla DOM naif langsung memanggil `setState` atau melakukan mutasi innerHTML saat pesan WebSocket tiba.
  - Dampak: CPU Main Thread konsisten di angka 100%, Interaksi latency (*Interaction to Next Paint* - INP) mencapai 850ms, frame rate anjlok ke 12-15 FPS (*Severe Jank*).
- **Akar Masalah Arsitektur**:
  1. WebSocket callback berjalan sebagai Macrotask independen, langsung mengeksekusi DOM Read/Write secara tak teratur.
  2. Browser dipaksa menghitung ulang geometri (*Forced Synchronous Layout*) berkali-kali dalam satu tick (800 kali per detik).
- **Solusi Rekayasa Sistem**:
  1. **Worker Offloading**: WebSocket dialihkan ke dalam *Dedicated Web Worker*. Dekompresi binary payload (Protocol Buffers/MsgPack) dijalankan di background thread.
  2. **Zero-Copy ArrayBuffer Transfer**: Worker mengirimkan data komputasi ke main thread menggunakan `postMessage` dengan mentransfer kepemilikan buffer (`Transferable Objects`), meniadakan serialization overhead.
  3. **High-Frequency Throttle Buffer**: Main thread mengumpulkan state updates ke dalam Ring Buffer memory internal.
  4. **rAF Batching**: Rendering dieksekusi sinkron dengan refresh rate browser (maksimal 60 update/detik pada layar 60Hz) menggunakan `requestAnimationFrame`. Seluruh kalkulasi DOM dipadatkan menjadi fase batching diskrit.
- **Hasil**: INP terpangkas dari 850ms menjadi 34ms (Kategori "Good"). Beban CPU Main Thread turun dari 100% ke 18%.

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya & Trade-off | Skenario Penggunaan yang Tepat |
| :--- | :--- | :--- | :--- |
| **Proxy-based Fine-grained Reactivity** | - Update terjadi spesifik pada dependensi yang berubah.<br>- Tidak memerlukan komparasi VDOM diffing tree secara utuh. | - Overhead alokasi memori untuk struktur data Graph (`WeakMap`, `Set`).<br>- Initial tracking cost lebih lambat dibanding plain objects. | Aplikasi SPA kompleks dengan dependensi data tabular/hierarkis yang intensif. |
| **Web Workers Data Offloading** | - Main Thread terbebas dari blocking computation.<br>- UI tetap responsif 60/120 FPS tanpa dropped frames. | - Serialization latency jika tidak menggunakan `Transferable Objects` / `SharedArrayBuffer`.<br>- Tidak memiliki akses langsung ke DOM API. | Transformasi dataset masif (>100k records), kalkulasi kriptografi, parsing stream binary. |
| **Shadow DOM Encapsulation** | - CSS terisolasi secara mutlak; tidak ada styling leakage.<br>- Kompatibilitas tinggi lintas framework. | - Kesulitan dalam konsumsi design system token global tanpa konfigurasi CSS Custom Properties (`var(--...)`).<br>- Debugging inspeksi elemen lebih berlapis. | Micro-frontend enterprise, UI Design System component library pihak ketiga. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Mutasi Objek Mengabaikan Proxy Reference
- **Kesalahan**: Menyimpan referensi objek mentah (*raw target*) dan melakukan modifikasi data langsung ke objek target, bukan ke instans `Proxy`.
- **Dampak**: Trap `set` pada Proxy tidak pernah terpicu; subscribers tidak mengetahui adanya perubahan data (antarmuka menjadi stale).
- **Troubleshooting**: Selalu bungkus state melalui factory method dan cegah akses langsung ke raw object dengan mengisolasi scope raw object di dalam closure.

#### 2. Starvation pada Microtask Scheduling
- **Kesalahan**: Menjalankan rekursi microtask tak berujung (misal: memicu `queueMicrotask` di dalam listener microtask itu sendiri tanpa exit condition yang valid).
- **Dampak**: Main Thread membeku seketika. Browser tidak pernah mencapai fase *Rendering Opportunity* atau eksekusi *Macrotask* (UI completely unresponsive).
- **Troubleshooting**: Gunakan Profiler pada Browser DevTools. Jika panel "Bottom-Up" didominasi oleh `Microtask Run`, periksa guard/break condition pada scheduler loop.

#### 3. Reading Layout Properties Setelah Mutasi Style (Forced Reflow)
- **Kesalahan**:
  ```javascript
  card.style.transform = 'translateX(10px)';
  const width = card.offsetWidth; // Memaksa browser menghitung reflow saat itu juga!
  ```
- **Dampak**: Penurunan drastis performa jika dilakukan pada banyak elemen.
- **Troubleshooting**: Aktifkan fitur *Rendering > Frame Rendering Stats* pada Chrome DevTools. Amati layer border merah yang mengindikasikan forced recalculation. Terapkan arsitektur *Read-All then Write-All*.

---

### 11. Best Practices (Production Checklist)

- [ ] **CSS Triggers Minimization**: Utamakan penggunaan properti CSS `transform` dan `opacity` untuk animasi visual; hindari modifikasi `top`, `left`, `width`, `height`, dan `margin` secara dinamis.
- [ ] **Containment Optimization**: Terapkan atribut CSS `contain: layout style paint;` atau `contain: content;` pada komponen modular untuk mengisolasi boundary reflow browser hanya pada sub-pohon komponen tersebut.
- [ ] **DOM Mutation Batching**: Jangan lakukan `appendChild` satu-per-satu di dalam loop. Gunakan `DocumentFragment` atau `element.replaceChildren()` untuk mengeksekusi mutasi tree secara atomik.
- [ ] **Event Listener Hygiene**: Pastikan pemanggilan `removeEventListener` dilakukan saat komponen unmount atau destroyed. Gunakan `AbortController` signal pattern untuk pembersihan event listener multi-instance secara elegan:
  ```typescript
  const controller = new AbortController();
  window.addEventListener('resize', handler, { signal: controller.signal });
  // Pembersihan massal:
  controller.abort();
  ```
- [ ] **Passive Event Listeners**: Gunakan `{ passive: true }` pada touch dan wheel listener untuk memastikan UI scroll performance tidak terhambat oleh pengecekan `preventDefault()`.
- [ ] **Memory Leak Prevention**: Gunakan `WeakMap` dan `WeakSet` untuk meta-programming data store atau tracking metadata elemen DOM, sehingga elemen yang dihapus dari DOM dapat di-garbage collect oleh engine.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum ini ke dalam direktori struktur: `hands-on/m02/`

#### Langkah 1: Inisialisasi Project Sandbox
Buat konfigurasi project dasar tanpa framework eksternal:

`hands-on/m02/package.json`:
```json
{
  "name": "enterprise-frontend-foundations-m02",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "vite": "^5.1.0"
  }
}
```

#### Langkah 2: Implementasi Scheduler Komputasi (Batcher)
File: `hands-on/m02/src/core/scheduler.ts`

```typescript
export class RenderScheduler {
  private static readTasks: Array<() => void> = [];
  private static writeTasks: Array<() => void> = [];
  private static isScheduled = false;

  public static read(task: () => void): void {
    this.readTasks.push(task);
    this.requestFlush();
  }

  public static write(task: () => void): void {
    this.writeTasks.push(task);
    this.requestFlush();
  }

  private static requestFlush(): void {
    if (this.isScheduled) return;
    this.isScheduled = true;

    requestAnimationFrame(() => {
      this.flush();
    });
  }

  private static flush(): void {
    // FASE 1: Eksekusi seluruh operasi READ
    const reads = this.readTasks.slice();
    this.readTasks.length = 0;
    for (let i = 0; i < reads.length; i++) {
      reads[i]();
    }

    // FASE 2: Eksekusi seluruh operasi WRITE
    const writes = this.writeTasks.slice();
    this.writeTasks.length = 0;
    for (let i = 0; i < writes.length; i++) {
      writes[i]();
    }

    this.isScheduled = false;

    // Handle jika ada task baru yang terdaftar saat fase flushing
    if (this.readTasks.length > 0 || this.writeTasks.length > 0) {
      this.requestFlush();
    }
  }
}
```

#### Langkah 3: Web Worker Threading Setup
File: `hands-on/m02/src/workers/data-processor.worker.ts`

```typescript
// Background worker untuk pemrosesan dataset besar
self.onmessage = (event: MessageEvent<{ datasetSize: number }>) => {
  const { datasetSize } = event.data;
  
  // Alokasi TypedArray Float64 (8 byte per elemen)
  const buffer = new SharedArrayBuffer(datasetSize * Float64Array.BYTES_PER_ELEMENT);
  const view = new Float64Array(buffer);

  for (let i = 0; i < datasetSize; i++) {
    // Kalkulasi matematika acak berat
    view[i] = Math.sin(i) * Math.cos(i) * Math.sqrt(i * 1.5);
  }

  // Kirim balik buffer kepemilikan tanpa overhead cloning
  self.postMessage({ buffer, size: datasetSize });
};
```

#### Langkah 4: Hubungkan ke Root Interface
File: `hands-on/m02/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Deep Dive Core Foundations Engine</title>
  <style>
    body { font-family: sans-serif; padding: 2rem; background: #f8fafc; }
    #metrics-panel { display: flex; gap: 1rem; margin-top: 1rem; }
    .box { width: 100px; height: 100px; background: royalblue; color: white; display: flex; align-items: center; justify-content: center; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Arsitektur Main-Thread Rendering vs Worker Pipeline</h1>
  <button id="btn-stress">Stress Test (Naive)</button>
  <button id="btn-optimize">Run Optimized (Scheduler)</button>
  
  <div id="metrics-panel">
    <div class="box" id="box-1">Box 1</div>
    <div class="box" id="box-2">Box 2</div>
  </div>

  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

File: `hands-on/m02/src/main.ts`

```typescript
import { RenderScheduler } from './core/scheduler';

const box1 = document.getElementById('box-1') as HTMLElement;
const box2 = document.getElementById('box-2') as HTMLElement;

document.getElementById('btn-stress')?.addEventListener('click', () => {
  console.time('Naive Execution');
  // Memaksa Layout Thrashing
  for (let i = 0; i < 500; i++) {
    const h1 = box1.clientHeight;
    box1.style.height = `${(h1 % 200) + 1}px`;
    const h2 = box2.clientHeight;
    box2.style.height = `${(h2 % 200) + 1}px`;
  }
  console.timeEnd('Naive Execution');
});

document.getElementById('btn-optimize')?.addEventListener('click', () => {
  console.time('Scheduler Execution');
  for (let i = 0; i < 500; i++) {
    RenderScheduler.read(() => {
      const h1 = box1.clientHeight;
      const h2 = box2.clientHeight;
      
      RenderScheduler.write(() => {
        box1.style.height = `${(h1 % 200) + 1}px`;
        box2.style.height = `${(h2 % 200) + 1}px`;
      });
    });
  }
  console.timeEnd('Scheduler Execution');
});
```

---

### 13. Exercises

#### Level: Easy
1. Modifikasi class `RenderScheduler` pada Hands-on Practice agar mendukung prioritas eksekusi: tambahkan antrean ketiga `highPriorityWriteTasks` yang wajib dieksekusi sebelum `writeTasks` normal berjalan.
2. Buat fungsi generic `shallowEqual(objA: any, objB: any): boolean` berkinerja tinggi yang digunakan untuk mencegah mutasi state jika nilai properti primitif tidak mengalami perubahan nilai riil.

#### Level: Medium
1. Implementasikan array mutation traps pada reactive engine modul ini. Saat pemanggilan operasi mutasi native array seperti `push`, `pop`, `shift`, `unshift`, `splice`, pastikan efek reaktif terpicu dengan tepat tanpa memicu *infinite recursive triggers* pada pembacaan properti internal `length`.
2. Buat Web Component `<virtual-list-scroller>` yang hanya merender elemen visual yang berada tepat di viewport vertikal layar ($\pm 5$ item buffer) dari total 10.000 raw items untuk menjaga DOM node density tetap minimum.

#### Level: Hard
1. Rancang arsitektur Time-Slicing Task Runner berbasis `MessageChannel` (meniru arsitektur internal Fiber Engine) yang dapat mengeksekusi array komputasi besar tanpa memblokir rendering pipeline, dengan parameter jeda jika durasi eksekusi per frame telah melampaui batas anggaran (frame budget) 5ms.

---

### 14. Challenge

**Skenario**: Anda ditugaskan membangun sistem *Live In-Browser Code Analyzer* yang melakukan syntax validation dan linting terhadap 50.000 baris kode JavaScript secara real-time saat pengguna mengetik teks di `<textarea>`.

**Spesifikasi Kebutuhan**:
1. Mengetik pada antarmuka input tidak boleh mengalami latensi input visual lebih dari 16ms (Wajib mempertahankan 60 FPS, INP < 50ms).
2. Analisis linting regex/AST harus berjalan di background layer tanpa menahan interaksi kursor pengguna.
3. Hasil validasi berupa highlight garis bawah merah/kuning harus dipetakan tepat di atas viewport tanpa merusak scrolling alignment dan tanpa memicu forced layout thrashing.
4. Memori browser tidak boleh bertambah secara konstan (*zero uncollected memory leak*) saat user terus melakukan pengetikan selama 1 jam.

**Tugas**: Buat proposal arsitektur teknis lengkap mencakup alur diagram threading (Main Thread vs Workers vs SharedArrayBuffer), implementasi skema komunikasi zero-copy transfer, serta mitigasi DOM rendering jank saat rendering marker error berlangsung.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa memodifikasi CSS menggunakan `transform: translate3d()` lebih efisien dari sisi performa rendering dibandingkan memanipulasi koordinat `top` dan `left`?
2. Pada tahapan manakah di dalam siklus Event Loop browser, antrean *Microtask Queue* dieksekusi?
3. Sebutkan perbedaan perilaku teknis mendasar antara `<template>` HTML tag dengan elemen tersembunyi berproperti `display: none`!
4. Apa fungsi dari struktur data `WeakMap` dalam implementasi arsitektur Reactive Data Store?
5. Mengapa pembacaan properti `element.scrollTop` tepat setelah penulisan `element.style.padding` memicu degradasi performa (*Forced Synchronous Layout*)?

#### B. Pertanyaan Intermediate
6. Jelaskan bagaimana mekanisme antrean internal `queueMicrotask` dapat menyebabkan *main-thread starvation*, dan bagaimana cara mitigasinya!
7. Bagaimana arsitektur Shadow DOM v1 mengisolasi pengaruh CSS styling global terhadap child tree di dalam Web Component?
8. Kapan sebaiknya engineer memilih `MessageChannel` dibandingkan `setTimeout(fn, 0)` untuk penjadwalan Macrotask kustom?
9. Apa perbedaan esensial antara Web Worker standar (`Dedicated Worker`) dengan `SharedWorker` dalam arsitektur aplikasi multikomponen enterprise?
10. Mengapa pemanggilan `Reflect.set(target, prop, value, receiver)` lebih direkomendasikan di dalam Proxy handler trap dibandingkan melakukan assign langsung `target[prop] = value`?

#### C. Skenario Kasus Produksi
11. **Kasus 1**: Pada dashboard inventaris logistik, tim Anda menampilkan tabel 5.000 baris. Saat pengguna mengetik di kolom pencarian, frame rate anjlok hingga 5 FPS dan CPU profiling menunjukkan aktivitas "Recalculate Style" dan "Layout" menyerap waktu hingga 700ms. Identifikasi 2 langkah strategis rekayasa teknis untuk mengatasi isu ini secara tuntas tanpa library eksternal!
12. **Kasus 2**: Sebuah komponen analytics mengamati mutasi DOM target menggunakan `MutationObserver`. Ketika komponen lain melakukan animasi DOM, observer memicu ribuan mutasi per detik yang mengakibatkan memory heap browser meningkat hingga 1.5GB kemudian tab browser crash (OOM). Di mana letak kegagalan arsitekturnya dan bagaimana solusinya?
13. **Kasus 3**: Anda menemukan bahwa metrik LCP (Largest Contentful Paint) pada halaman e-commerce Anda memiliki latency tinggi (4.2 detik). Pemeriksaan Network Waterfall menunjukkan file JavaScript modular `app.js` berukuran besar dieksekusi di `<head>` dan memblokir parsing HTML dasar. Bagaimana konfigurasi pemuatan script modern yang harus diterapkan secara arsitektural?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Pertanyaan Basic
1. Properti `transform` diproses langsung oleh Thread Compositor dan diteruskan ke GPU tanpa harus memicu tahapan Layout (Reflow) maupun Paint pada Main Thread. Sebaliknya, manipulasi `top`/`left` mengubah geometri fisik box model sehingga browser diwajibkan melakukan siklus ulang Layout, Paint, hingga Composite.
2. Microtask Queue dieksekusi tepat setelah call stack sinkronus saat itu kosong, dan sebelum browser melanjutkan ke fase Rendering Opportunity (Style, Layout, Paint) berikutnya atau mengambil task baru dari Macrotask Queue.
3. Konten di dalam tag `<template>` tidak dimasukkan ke dalam dokumen DOM aktif selama inisialisasi; script di dalamnya tidak dieksekusi, gambar tidak di-load, dan tidak ada kalkulasi CSSOM/Render Tree yang dilakukan hingga elemen tersebut diinstansiasi secara manual via `.cloneNode()`. Sementara `display: none` tetap diurai masuk ke dalam DOM Tree dan memicu resource downloading (seperti image asset).
4. `WeakMap` hanya memegang referensi "lemah" (*weak reference*) terhadap objek key. Jika objek target telah dihapus dari siklus eksekusi aplikasi, JavaScript Garbage Collector dapat membersihkan memory node tersebut secara otomatis tanpa tertahan oleh registry store, mencegah *severe memory leaks*.
5. Penulisan `element.style.padding` menandai layout state sebagai *dirty*. Pembacaan `scrollTop` memerlukan perhitungan dimensi aktual real-time yang valid, sehingga browser terpaksa menghentikan eksekusi JavaScript dan langsung menjalankan siklus Layout engine secara sinkron saat itu juga (*Forced Synchronous Layout*).

#### Kunci Pertanyaan Intermediate
6. Microtask starvation terjadi jika sebuah microtask secara berulang mendaftarkan microtask baru ke dalam antrean (microtask queue tidak pernah kosong). Akibatnya, Event Loop terkunci dan tidak pernah melanjutkan ke tahapan render frame atau macrotask. Mitigasinya: pecah komputasi masif ke dalam macrotask interval (`requestAnimationFrame` atau `scheduler.postTask`) agar engine memiliki celah waktu untuk merender UI.
7. Shadow DOM menciptakan *Shadow Root boundary*. CSS selektor di luar boundary tidak dapat menembus ke dalam internal nodes (kecuali CSS Custom Properties yang mewarisi cascading tree), dan style internal yang didefinisikan di dalam Shadow Root tidak dapat mencemari (*leak*) DOM global di luar host element.
8. `setTimeout(fn, 0)` memiliki clamping minimum limitasi penundaan artificially sebesar ~4ms pada nested loop browser environment. `MessageChannel` menghasilkan zero-delay macrotask langsung pada tick macrotask berikutnya tanpa penalti penundaan 4ms tersebut, sehingga sangat optimal untuk fine-grained task slicing.
9. `Dedicated Worker` terikat secara eksklusif hanya pada satu tab/konteks pengeksekusi (1 worker instance per script page). `SharedWorker` dapat diakses dan digunakan secara simultan oleh multiple tab, iframe, atau window yang berjalan pada origin domain yang sama melalui koneksi port jaringan terpusat.
10. `Reflect.set` mengembalikan nilai boolean penanda keberhasilan operasi mutasi dan mempertahankan binding prototype context yang valid terhadap parameter `receiver`. Menggunakan `target[prop] = value` di dalam proxy trap berisiko memicu throw type error pada properti non-writable strict mode, serta merusak inheritance chain jika target memiliki setter kustom pada prototype-nya.

#### Kunci Skenario Kasus Produksi
11. **Solusi Kasus 1**:
    - Terapkan teknik **Virtual DOM Scrolling (DOM Virtualization)**: Alih-alih merender 5.000 elemen, hitung tinggi viewport container dan render hanya item yang terlihat di layar (misal: 20-30 node `<tr>`), perbarui isinya secara dinamis saat scroll event berlangsung.
    - Pasang CSS Containment `contain: strict;` pada parent container tabel untuk mencegah browser mengalkulasi ulang layout elemen lain di luar container tabel saat filter teks diproses.
12. **Solusi Kasus 2**:
    - **Akar Masalah**: Siklus *Infinite Reactive Loop*. Callback `MutationObserver` menjalankan operasi yang secara langsung memodifikasi atribut/child DOM yang sedang diamatinya sendiri, memicu observer memanggil callback-nya kembali secara eksponensial.
    - **Solusi**: Filter scope pengamatan menggunakan konfigurasi `attributeFilter` spesifik; putuskan siklus mutasi internal, atau gunakan flag mutex (*lock*) sebelum mengeksekusi manipulasi DOM di dalam callback observer; pastikan pemanggilan `observer.disconnect()` dilakukan saat unmount.
13. **Solusi Kasus 3**:
    - Pindahkan pemuatan file JavaScript dari `<head>` ke penutup body atau terapkan atribut `defer` / `type="module"` pada tag `<script>`.
    - Tambahkan `<link rel="preload">` untuk critical render path resource (seperti hero image atau primary stylesheet).
    - Terapkan CSS splitting dan letakkan critical inline CSS langsung pada header untuk menjamin first visual paint berlangsung sebelum JS parsing runtime dieksekusi penuh.

---

### 16. Summary

Penguasaan frontend tingkat enterprise bergeser dari sekadar konsumsi framework tingkat tinggi menuju pemahaman komprehensif terhadap mekanisme internal browser engine:

1. **Pipeline Rendering Determinism**: Performa rendering optimal tercapai ketika engineer memahami batasan biaya setiap operasi DOM. Meminimalkan reflow dan paint serta memaksimalkan kerja GPU Compositor (`transform`, `opacity`) adalah fondasi antarmuka 60 FPS bebas jank.
2. **Precision Event Loop Execution**: Arsitektur asynchronous modern menuntut diferensiasi tegas antara operasi *Microtask* (pengelolaan data state reaktif atomik), *Animation Frame* (sinkronisasi geometri visual dengan monitor refresh rate), dan *Macrotask* (penjadwalan background work).
3. **Off-Main-Thread Processing**: Komputasi berat harus didelegasikan keluar dari Main Thread menuju Web Workers via memory buffer terisolasi. UI thread bertindak murni sebagai view presentation layer yang responsif.
4. **Encapsulated & Reactive Foundation**: Mengombinasikan Web Components native dengan arsitektur Proxy-based fine-grained reactivity memungkinkan pembuatan sistem aplikasi berskala masif, decoupled, mudah diuji, serta bebas memory leak tanpa keterikatan absolut pada framework eksternal tertentu.