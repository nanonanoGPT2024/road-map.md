# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis** siklus hidup internal peramban (*browser rendering engine* dan *JavaScript V8 runtime*) hingga tingkat *frame budget* 16.6ms (60 FPS) dan 8.33ms (120 FPS).
2. **Merancang** sistem reaktivitas data stateful (*fine-grained reactivity*) berbasis *Proxy* dan *Observer Pattern* tanpa ketergantungan pada *library* eksternal.
3. **Mengimplementasikan** arsitektur *Component-Driven* tingkat produksi menggunakan Vanilla JavaScript / TypeScript yang mengisolasi *state*, *lifecycle*, dan *DOM reconciliation*.
4. **Mengidentifikasi dan Mengeliminasi** degradasi performa kritis, termasuk *Layout Thrashing*, kebocoran memori (*Detached DOM Trees*), dan blokade pada *Main Thread*.
5. **Mengukur dan Mengoptimasi** metrik Core Web Vitals (*Largest Contentful Paint* [LCP], *Interaction to Next Paint* [INP], *Cumulative Layout Shift* [CLS]) pada skenario aplikasi berskala enterprise.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta harus telah menguasai:
* Pemahaman fundamental DOM Manipulation & Event Bubbling/Capturing (Bab 04 & 05).
* JavaScript Asynchronous: Promises, Async/Await, dan Microtask Queue dasar (Bab 07).
* Konsep OOP & Functional Programming dasar di ES6+ (Bab 08).
* Pemahaman mendasar terkait HTTP/HTTPS networking, caching headers, dan modul bundler (Bab 09 - Module 01).

---

## 3. Concept & Internal Architecture

Memahami arsitektur produksi menuntut pemahaman terhadap dua mesin utama di dalam browser: **Rendering Engine** (misal: Blink, WebKit, Gecko) dan **JavaScript Engine** (misal: V8, JavaScriptCore, SpiderMonkey).

### 3.1. Browser Critical Rendering Path (CRP)

Ketika payload HTML diterima oleh *network stack*, peramban mengeksekusi pipeline berikut:

```
[Bytes] -> [Characters] -> [Tokens] -> [Nodes] -> [DOM Tree]
                                                        \
[Bytes] -> [Characters] -> [Tokens] -> [Nodes] -> [CSSOM Tree] -> [Render Tree]
                                                                        |
                                                                   [Layout]
                                                                        |
                                                                    [Paint]
                                                                        |
                                                                  [Composite]
```

1. **DOM Tree Construction**: Aliran bita (*byte stream*) diubah menjadi karakter, kemudian ditokenisasi menjadi tag-tag HTML, dikonversi menjadi objek *Node*, dan akhirnya disusun menjadi struktur pohon (*Tree*).
2. **CSSOM Tree Construction**: Bersamaan dengan parsing HTML, CSS diparsing menjadi struktur hierarkis CSS Object Model. Sifat CSS adalah **render-blocking**.
3. **Render Tree Construction**: Penggabungan DOM dan CSSOM. Node yang memiliki properti `display: none` diabaikan sepenuhnya dari Render Tree, sedangkan elemen dengan `visibility: hidden` tetap disertakan karena mempertahankan dimensi geometris.
4. **Layout (Reflow)**: Peramban menghitung geometri pasti (posisi $X, Y$, lebar, dan tinggi) dari setiap node pada viewport. Operasi ini menuntut kalkulasi matematis intensif.
5. **Paint (Rasterization)**: Mengubah visual elemen (warna, border, bayangan, teks) menjadi piksel-piksel pada layer memori.
6. **Compositing**: Mengirimkan layer-layer gambar ke GPU untuk digabungkan dan dirender ke layar fisik pengguna. Modifikasi properti CSS seperti `transform` dan `opacity` memungkinkan bypass fase Layout dan Paint, langsung menuju Composite.

### 3.2. JavaScript Runtime: V8 Execution & Memory Architecture

V8 mengeksekusi JavaScript melalui alur:
* **Parser**: Mengubah *source code* menjadi Abstract Syntax Tree (AST).
* **Ignition**: Interpreter yang menghasilkan *Bytecode* yang dapat langsung dieksekusi secara cepat.
* **TurboFan**: Optimizing compiler yang mengambil *Bytecode* beserta data profiling (*type feedback*) dan mengompilasinya menjadi *Machine Code* yang sangat teroptimasi. Jika asumsi tipe berubah (polimorfisme liar), terjadi **Deoptimization** (bailout) kembali ke Bytecode.

#### Memory Management & Garbage Collection (GC)
Memori V8 terbagi dalam dua segmentasi utama:
1. **Stack**: Mengalokasikan nilai primitif dan referensi pointer secara terstruktur LIFO (*Last In, First Out*).
2. **Heap**: Mengalokasikan objek, array, closure, dan struktur data dinamis.
   * **Young Generation**: Objek berumur pendek. Di-clearing menggunakan *Scavenge GC* (algoritma Cheney semi-space) yang sangat cepat.
   * **Old Generation**: Objek yang lolos dari beberapa siklus Scavenge. Di-clearing menggunakan *Major GC (Mark-Sweep-Compact)* yang berpotensi memicu *Stop-The-World* (STW) latency bila tumpukan memori terfragmentasi.

---

## 4. Why & What

### Mengapa Perlu Arsitektur Lanjutan?
Dalam tahap pemula, penulisan kode imperatif sederhana (`document.getElementById`, `element.innerHTML = ...`) mencukupi. Namun, pada aplikasi enterprise (seperti *banking portal*, *telemetry dashboard*, atau *e-commerce checkout*):
* **Manipulasi DOM Naif Merusak Performa**: Mengubah DOM secara sporadis memicu rentetan *Forced Synchronous Layout* (Layout Thrashing).
* **Kebocoran State & Memori**: Tanpa manajemen siklus hidup (*lifecycle teardown*), listener yang terikat pada elemen yang dihapus akan menahan elemen tersebut di memori (*Detached DOM Node*), mengakibatkan lonjakan konsumsi RAM secara linear seiring durasi penggunaan.
* **Maintainability & Skalabilitas Kode Rendah**: *Spaghetti state*—di mana 5 fungsi berbeda memodifikasi satu elemen DOM yang sama—membuat aplikasi mustahil diuji (*untestable*) dan rentan terhadap regresi (*bug-ridden*).

### Apa Solusinya?
* Mengadopsi paradigma **Reactivity Engine** berbasis unifikasi *Publisher-Subscriber* atau *Proxy*.
* Membangun abstraksi **Component Layer** dengan isolasi State, Props, Template, dan Cleanup Lifecycle.
* Menerapkan komputasi asynchronous tersegregasi via **Web Workers** untuk kalkulasi berat dan scheduling via `requestAnimationFrame` serta `requestIdleCallback`.

---

## 5. How (Workflow Detail)

Berikut adalah alur arsitektural siklus mutasi data hingga visualisasi piksel pada aplikasi tingkat produksi:

```
[User Action / Network Event]
             │
             ▼
     [Mutate State] ──(via Proxy Trap)
             │
             ▼
   [Notify Subscribers]
             │
             ▼
  [Batching Queue Scheduler] ──(Aggregasi mutasi via Microtask)
             │
             ▼
   [Reconciliation Phase] ──(Virtual Tree / Template String Diff)
             │
             ▼
     [DOM Write Patch] ──(requestAnimationFrame)
             │
             ▼
   [Compositor Commit] ──(GPU Flush -> Display)
```

1. **State Mutation Trap**: Setiap mutasi objek state ditangkap oleh JavaScript `Proxy` handler (`set` trap).
2. **Subscriber Scheduling**: Mutasi tidak langsung memicu penulisan DOM secara synchronous. Mutasi didaftarkan ke dalam *Batching Queue*.
3. **Microtask Aggregation**: Melalui `Promise.resolve()`, antrean mutasi dikonsolidasikan. Lima puluh mutasi synchronous dalam satu siklus tick hanya akan menghasilkan tepat **satu** eksekusi render.
4. **Reconciliation & Batch DOM Update**: Patching dilakukan pada node yang relevan, diselaraskan dengan refresh rate monitor melalui `window.requestAnimationFrame`.
5. **Teardown & GC Verification**: Seluruh instansiasi komponen menyediakan metode pembersihan (`destroy`/`unmount`) untuk melepas `AbortController`, event listener, dan referensi cache.

---

## 6. Analogy & Diagram ASCII

### Analogi Pabrik Perakitan Otomotif
Bayangkan sebuah pabrik perakitan mobil:
* **DOM** adalah *lantai pabrik fisik* yang masif dan lambat dipindahkan. Mengubah satu baut langsung di mobil yang sedang melaju di lintasan (*Direct DOM manipulation*) membutuhkan penghentian seluruh rantai perakitan (*Stop-The-World Layout*).
* **State** adalah *cetak biru digital* (*blueprint*). Mengubah cetak biru di komputer itu instan dan murah.
* **Reconciliation Engine** adalah *mandor perakitan cerdas*. Mandor mengumpulkan seluruh revisi cetak biru selama satu shift kerja (*Batching*), membandingkannya dengan kondisi fisik mobil (*Diffing*), lalu memberikan instruksi perbaikan seminimal mungkin ke teknisi (*Patching*).
* **Memory Leak** adalah tumpukan suku cadang rusak yang tidak pernah dibuang dari lantai pabrik karena teknisi lama lupa mencabut tanda label kepemilikannya. Lama kelamaan, lantai pabrik penuh dan seluruh pabrik macet total (*Crash/OOM*).

### Diagram: Event Loop, Microtasks, dan Render Steps

```
+-------------------------------------------------------------------------+
|                              EVENT LOOP                                 |
+-------------------------------------------------------------------------+
|                                                                         |
|  +-------------------+        +--------------------+                    |
|  |   MACROTASK QUEUE |        |  MICROTASK QUEUE   |                    |
|  |  (setTimeout, I/O)|        | (Promise, Mutation)|                    |
|  +---------+---------+        +---------+----------+                    |
|            |                            |                               |
|            | [1 Task]                   | [Flush ALL until Empty]       |
|            v                            v                               |
|       +----+----------------------------+-----+                         |
|       |          JAVASCRIPT CALL STACK        |                         |
|       +-------------------+-------------------+                         |
|                           |                                             |
|                           v (If 16.6ms window is due)                   |
|       +-------------------+-------------------+                         |
|       |              RENDER STEPS             |                         |
|       |                                       |                         |
|       |  1. run requestAnimationFrame         |                         |
|       |  2. Recalculate Styles                |                         |
|       |  3. Layout (Calculate Box Geometry)   |                         |
|       |  4. Paint (Record Draw Calls)         |                         |
|       |  5. Composite (GPU Blit)              |                         |
|       +---------------------------------------+                         |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Reaktivitas Data Murni Menggunakan ES6 Proxy

```javascript
/**
 * Implementasi Reaktivitas Dasar dengan Dependency Tracking
 */
let activeEffect = null;

class Dependency {
  constructor() {
    this.subscribers = new Set();
  }

  depend() {
    if (activeEffect) {
      this.subscribers.add(activeEffect);
    }
  }

  notify() {
    this.subscribers.forEach((effect) => effect());
  }
}

function createReactiveObject(target) {
  const depMap = new Map();

  function getDep(key) {
    let dep = depMap.get(key);
    if (!dep) {
      dep = new Dependency();
      depMap.set(key, dep);
    }
    return dep;
  }

  return new Proxy(target, {
    get(obj, key) {
      const dep = getDep(key);
      dep.depend();
      return Reflect.get(obj, key);
    },
    set(obj, key, value) {
      const oldValue = obj[key];
      const success = Reflect.set(obj, key, value);
      if (oldValue !== value) {
        const dep = getDep(key);
        dep.notify();
      }
      return success;
    },
  });
}

function watchEffect(effect) {
  activeEffect = effect;
  effect(); // Jalankan sekali untuk mengumpulkan dependency
  activeEffect = null;
}

// Pengujian Reaktivitas
const userState = createReactiveObject({ username: 'Alex', loginAttempts: 0 });

watchEffect(() => {
  console.log(`[Telemetry UI] Status Akun: ${userState.username}, Percobaan: ${userState.loginAttempts}`);
});

// Mutasi state memicu trigger effect secara otomatis
userState.loginAttempts += 1;
userState.username = 'Alexander';
```

### 7.2. Practical Example: Mini Component Engine Berskala Enterprise

Berikut adalah implementasi sistem komponen modern berorientasi objek yang menangani *Batched Rendering*, *Scoped Event Delegation*, *Lifecycle Teardown*, dan pencegahan *Memory Leak*.

```javascript
/**
 * Base Component Architecture untuk Enterprise Single Page App (Vanilla TS/JS)
 */
export class EnterpriseComponent {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      throw new Error(`Inisialisasi Gagal: Elemen #${containerId} tidak ditemukan.`);
    }

    this.state = null;
    this.abortController = new AbortController();
    this._isRenderQueued = false;

    this.init();
  }

  /**
   * Mengatur reactive state dengan automated microtask batch rendering
   */
  initState(initialState) {
    this.state = new Proxy(initialState, {
      set: (target, property, value) => {
        if (target[property] === value) return true;
        target[property] = value;
        this.scheduleRender();
        return true;
      },
    });
  }

  /**
   * Menjadwalkan render pada Microtask Queue untuk mencegah Layout Thrashing
   */
  scheduleRender() {
    if (this._isRenderQueued) return;
    this._isRenderQueued = true;

    queueMicrotask(() => {
      window.requestAnimationFrame(() => {
        this.render();
        this._isRenderQueued = false;
      });
    });
  }

  /**
   * Registrasi event listener dengan lifecycle binding terisolasi
   */
  bindEvent(selector, eventType, handler) {
    this.container.addEventListener(
      eventType,
      (event) => {
        const targetElement = event.target.closest(selector);
        if (targetElement && this.container.contains(targetElement)) {
          handler.call(this, event, targetElement);
        }
      },
      { signal: this.abortController.signal }
    );
  }

  /**
   * Lifecycle Method: Mount
   */
  init() {
    this.setup();
    this.render();
    this.bindEvents();
  }

  setup() {}
  template() { return ''; }
  bindEvents() {}

  render() {
    // Menghindari innerHTML naive bila di production: sanitasi template
    const templateString = this.template();
    
    // Virtualization / Direct Paint minimizer
    const range = document.createRange();
    range.selectNode(this.container);
    const fragment = range.createContextualFragment(templateString);

    this.container.replaceChildren(fragment);
  }

  /**
   * Membersihkan listener dan referensi DOM untuk mencegah Memory Leaks
   */
  destroy() {
    this.abortController.abort(); // Membatalkan seluruh listener seketika
    this.container.replaceChildren();
    this.state = null;
  }
}

/**
 * IMPLEMENTASI NYATA: Monitor Transaksi Finansial
 */
export class TransactionDashboardComponent extends EnterpriseComponent {
  setup() {
    this.initState({
      transactions: [
        { id: 'TX-101', amount: 5000000, status: 'SUCCESS' },
        { id: 'TX-102', amount: 12500000, status: 'PENDING' },
      ],
      filter: 'ALL',
    });
  }

  bindEvents() {
    this.bindEvent('.btn-filter', 'click', (event, target) => {
      this.state.filter = target.dataset.filter;
    });

    this.bindEvent('.btn-add', 'click', () => {
      const newTx = {
        id: `TX-${Math.floor(100 + Math.random() * 900)}`,
        amount: Math.floor(Math.random() * 20000000),
        status: Math.random() > 0.5 ? 'SUCCESS' : 'PENDING',
      };
      // Trigger immutable update
      this.state.transactions = [...this.state.transactions, newTx];
    });
  }

  template() {
    const filteredList = this.state.transactions.filter((tx) => {
      if (this.state.filter === 'ALL') return true;
      return tx.status === this.state.filter;
    });

    return `
      <div class="p-6 bg-slate-900 text-white rounded-lg font-sans">
        <header class="flex justify-between items-center mb-6">
          <h1 class="text-xl font-bold tracking-tight">Sistem Kliring Transaksi Terdistribusi</h1>
          <div class="space-x-2">
            <button data-filter="ALL" class="btn-filter px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm">Semua</button>
            <button data-filter="SUCCESS" class="btn-filter px-3 py-1 bg-emerald-700 hover:bg-emerald-600 rounded text-sm">Sukses</button>
            <button data-filter="PENDING" class="btn-filter px-3 py-1 bg-amber-700 hover:bg-amber-600 rounded text-sm">Pending</button>
            <button class="btn-add px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-sm font-semibold">+ Transaksi</button>
          </div>
        </header>

        <section class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="border-b border-slate-700 text-slate-400 text-sm">
                <th class="py-2">ID Transaksi</th>
                <th class="py-2">Nominal</th>
                <th class="py-2">Status Operasional</th>
              </tr>
            </thead>
            <tbody>
              ${filteredList
                .map(
                  (tx) => `
                <tr class="border-b border-slate-800 text-sm">
                  <td class="py-3 font-mono text-cyan-400">${tx.id}</td>
                  <td class="py-3 font-semibold">Rp ${tx.amount.toLocaleString('id-ID')}</td>
                  <td class="py-3">
                    <span class="px-2 py-0.5 rounded text-xs ${
                      tx.status === 'SUCCESS' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-amber-950 text-amber-300 border border-amber-800'
                    }">
                      ${tx.status}
                    </span>
                  </td>
                </tr>
              `
                )
                .join('')}
            </tbody>
          </table>
        </section>
      </div>
    `;
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time Logistics Fleet Telemetry Dashboard
* **Skala Sistem**: Sistem memantau 15.000 armada truk ekspedisi secara serentak.
* **Volume Data**: Pembaruan koordinat GPS via WebSocket berlangsung pada frekuensi 100 paket/detik.
* **Problem**: 
  1. Penggunaan `tableElement.innerHTML = ...` setiap data WebSocket masuk mengakibatkan CPU freeze 100%, FPS anjlok ke level 8 FPS, dan interaksi pengguna mengalami freezing total (**INP > 1.200ms**).
  2. Alokasi memori heap naik hingga 1.8 GB dalam waktu 30 menit pemantauan, berujung pada crash browser tab (**Out Of Memory**).
* **Diagnosa Profiling**:
  * DevTools Performance: *Recalculate Style* dan *Layout* dipanggil 100 kali per detik di *Main Thread* tanpa sinkronisasi monitor refresh cycle (Layout Thrashing massal).
  * DevTools Memory (Allocation Sampling): Ditemukan 150.000+ *Detached HTMLTableCellElement* yang tertahan akibat closures pada WebSocket message subscriber callback yang tidak pernah dibersihkan.
* **Solusi Rekayasa Arsitektur**:
  1. **Web Worker Offloading**: Parsing protokol data binary (Protobuf/JSON) dan kalkulasi geofencing dipindahkan dari *Main Thread* ke *Dedicated Web Worker*.
  2. **Batch Windowing Scheduler**: Perubahan data di-buffer dalam memory-array dan dipancarkan ke *Main Thread* hanya setiap 16.6ms sekali (`~60 FPS`) menggunakan struktur payload ringkas.
  3. **Virtual DOM DOM-Recycling / Virtual Scrolling**: DOM fisik dibatasi hanya merender data yang terlihat pada viewport (misal: 25 baris tabel). Elemen di luar viewport di-recycle posisinya menggunakan CSS `transform: translateY(...)`.
* **Hasil Pengukuran**:
  * P99 INP membaik dari 1.200ms menjadi **24ms** (Rating: *Good*).
  * Konsumsi RAM stabil secara konstan pada flat **78 MB** selama 12 jam continuous stress-test.

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Kerugian & Konsekuensi | Skenario Pemakaian Terbaik |
| :--- | :--- | :--- | :--- |
| **Direct DOM Manipulation** | Efisiensi memori maksimum, zero library footprint, direct execution. | Raw layout thrashing risk, kode rapuh (*fragile*), state management manual yang chaotic. | Micro-widget, interaksi terisolasi pada landing page ultra-ringan. |
| **Virtual DOM Reconciliation** | Abstraksi deklaratif tinggi, meminimalisir penulisan mutasi DOM manual. | Runtime overhead overhead tinggi (CPU overhead saat membandingkan dua memory trees besar). | Data aplikasi kompleks dengan mutasi sporadis di berbagai segmen UI. |
| **Fine-Grained Reactivity (Proxy/Signals)** | Operasi DOM pinpointed (tanpa diffing seluruh tree), batching efisien. | Kompleksitas tinggi saat debugging, footprint memory awal untuk dependency graph Map/Set. | Enterprise SaaS Dashboard, Real-time transactional tracking portal. |
| **Web Worker Processing** | Main Thread bebas dari computational lag, menjamin target 60-120 FPS. | Overhead serialisasi data via structured clone transfer, tanpa akses langsung ke DOM API. | Enkripsi end-to-end, kompresi file/gambar di browser, data filtering masif (>50k array items). |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Layout Thrashing (Forced Synchronous Layout)
* **Penyebab**: Melakukan pembacaan properti geometri (seperti `offsetWidth`, `clientHeight`, `scrollTop`, `getBoundingClientRect()`) segera setelah melakukan penulisan style ke DOM. Peramban dipaksa memproses siklus layout saat itu juga tanpa batching.
* **Contoh Rusak**:
  ```javascript
  // BURUK: Layout Thrashing Loop
  elements.forEach((el) => {
    const width = el.offsetWidth; // READ (memicu reflow paksa)
    el.style.width = `${width + 10}px`; // WRITE
  });
  ```
* **Solusi**:
  ```javascript
  // BENAR: Memisahkan Fase READ dan WRITE
  const widths = elements.map((el) => el.offsetWidth); // Batch READ
  elements.forEach((el, index) => {
    el.style.width = `${widths[index] + 10}px`; // Batch WRITE
  });
  ```

### 10.2. Detached DOM Tree Memory Leaks
* **Penyebab**: Menyimpan referensi elemen DOM ke dalam variabel global atau array cache, namun elemen visualnya telah dihapus via `remove()` atau `innerHTML = ''`. Garbage Collector tidak dapat mereclaim memori tersebut karena pointer aktif masih eksis.
* **Deteksi & Mitigasi**:
  * Gunakan DevTools Memory tab -> Ambil Heap Snapshot -> Filter berdasarkan string `Detached`.
  * Selalu gunakan `WeakRef` atau `WeakMap` jika memerlukan caching elemen DOM, atau lakukan pemutusan pointer secara eksplisit: `this.cachedElement = null;`.

### 10.3. Zombie Microtask Blockade
* **Penyebab**: Rekursi mutasi state reaktif tak berujung di dalam microtask loop yang menahan peramban untuk melangkah ke rendering step berikutnya.
* **Mitigasi**: Batasi loop reaktivitas dengan depth-counter guard (maksimal 25-50 cascading passes). Lempar error diagnostik jika limit terlampaui.

---

## 11. Best Practices (Production Checklist)

- [ ] **Core Web Vitals Integrity**: INP < 200ms pada persentil ke-75; CLS < 0.1 dengan selalu menetapkan atribut `width` dan `height` eksplisit pada `img`, `video`, dan elemen kontainer dinamis.
- [ ] **Event Listener Hygiene**: Seluruh event binding menggunakan `AbortController` signal untuk eksekusi mass cleanup dalam satu pemanggilan metode `abort()`.
- [ ] **Passive Event Listeners**: Tambahkan `{ passive: true }` pada event listener `touchstart`, `touchmove`, dan `wheel` agar browser tidak menunda scroll rendering untuk memeriksa `preventDefault()`.
- [ ] **Layout Mutation Batching**: Penulisan mutasi layout dibungkus di dalam `window.requestAnimationFrame()`.
- [ ] **DOM Subtree Replacement**: Hindari perakitan string `innerHTML` berulang di dalam looping besar; manfaatkan `DocumentFragment` atau `createContextualFragment()`.
- [ ] **CSS Compositor Optimization**: Gunakan properti `transform` dan `opacity` untuk animasi grafis. Manfaatkan properti `will-change` hanya secara temporer saat animasi akan dipicu, lalu hapus properti tersebut setelah selesai.

---

## 12. Hands-on Practice

Buatlah direktori dan file untuk laboratorium performa arsitektur frontend dengan struktur berikut:

```
hands-on/m02/
├── index.html
├── src/
│   ├── app.js
│   ├── core/
│   │   ├── Component.js
│   │   └── ReactiveStore.js
│   └── components/
│       └── HighFrequencyGrid.js
└── styles/
    └── main.css
```

### Langkah 1: `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Frontend Architecture Benchmark</title>
  <link rel="stylesheet" href="styles/main.css">
</head>
<body>
  <div id="app-root"></div>
  <script type="module" src="src/app.js"></script>
</body>
</html>
```

### Langkah 2: `hands-on/m02/styles/main.css`
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
  padding: 2rem;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 1rem;
}

.metric-card {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 12px;
  contain: content; /* CSS Containment untuk isolasi layout & paint */
}

.metric-value {
  font-size: 1.25rem;
  font-weight: 700;
  font-family: monospace;
}

.metric-up { color: #34d399; }
.metric-down { color: #f87171; }
```

### Langkah 3: `hands-on/m02/src/core/ReactiveStore.js`
```javascript
export class ReactiveStore {
  constructor(initialState) {
    this.subscribers = new Set();
    this.state = this._createProxy(initialState);
  }

  _createProxy(data) {
    return new Proxy(data, {
      set: (target, prop, value) => {
        if (target[prop] === value) return true;
        target[prop] = value;
        this.notify();
        return true;
      }
    });
  }

  subscribe(callback) {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }

  notify() {
    this.subscribers.forEach(cb => cb(this.state));
  }
}
```

### Langkah 4: `hands-on/m02/src/core/Component.js`
```javascript
export class Component {
  constructor(containerId, store) {
    this.container = document.getElementById(containerId);
    this.store = store;
    this.abortController = new AbortController();
    this._renderScheduled = false;

    this.unsubscribe = this.store.subscribe(() => this.requestRender());
    this.requestRender();
    this.bindEvents();
  }

  requestRender() {
    if (this._renderScheduled) return;
    this._renderScheduled = true;
    
    // Batch updates to requestAnimationFrame
    window.requestAnimationFrame(() => {
      this.render();
      this._renderScheduled = false;
    });
  }

  bindEvents() {}
  template() { return ''; }

  render() {
    const range = document.createRange();
    range.selectNode(this.container);
    const fragment = range.createContextualFragment(this.template());
    this.container.replaceChildren(fragment);
  }

  destroy() {
    this.unsubscribe();
    this.abortController.abort();
    this.container.replaceChildren();
  }
}
```

### Langkah 5: `hands-on/m02/src/components/HighFrequencyGrid.js`
```javascript
import { Component } from '../core/Component.js';

export class HighFrequencyGrid extends Component {
  bindEvents() {
    this.container.addEventListener('click', (e) => {
      const btn = e.target.closest('#btn-toggle-stream');
      if (btn) {
        window.dispatchEvent(new CustomEvent('toggle-simulation'));
      }
    }, { signal: this.abortController.signal });
  }

  template() {
    const { items, isStreaming } = this.store.state;
    return `
      <div>
        <header style="margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <h2>Mesin Telemetri Market Stream (Batch rAF Optimized)</h2>
            <p style="color: #94a3b8; font-size: 0.875rem;">Mengisolasi Paint dengan CSS Containment</p>
          </div>
          <button id="btn-toggle-stream" style="padding: 8px 16px; background-color: ${isStreaming ? '#e11d48' : '#2563eb'}; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600;">
            ${isStreaming ? 'Hentikan Telemetri' : 'Mulai Telemetri Cepat'}
          </button>
        </header>

        <div class="grid-container">
          ${items.map(item => `
            <div class="metric-card" id="card-${item.id}">
              <div style="font-size: 0.75rem; color: #94a3b8;">${item.symbol}</div>
              <div class="metric-value ${item.delta >= 0 ? 'metric-up' : 'metric-down'}">
                ${item.price.toFixed(2)}
              </div>
              <div style="font-size: 0.75rem; color: ${item.delta >= 0 ? '#34d399' : '#f87171'};">
                ${item.delta >= 0 ? '+' : ''}${item.delta.toFixed(2)}%
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }
}
```

### Langkah 6: `hands-on/m02/src/app.js`
```javascript
import { ReactiveStore } from './core/ReactiveStore.js';
import { HighFrequencyGrid } from './components/HighFrequencyGrid.js';

// Setup Mock Data
const INITIAL_ITEMS = Array.from({ length: 50 }, (_, i) => ({
  id: i + 1,
  symbol: `PORTFOLIO-ASSET-${i + 1}`,
  price: 100 + Math.random() * 500,
  delta: 0
}));

const store = new ReactiveStore({
  items: INITIAL_ITEMS,
  isStreaming: false
});

const dashboard = new HighFrequencyGrid('app-root', store);

let intervalId = null;

window.addEventListener('toggle-simulation', () => {
  store.state.isStreaming = !store.state.isStreaming;

  if (store.state.isStreaming) {
    // Simulasi High-Frequency Updates (50 mutasi/detik)
    intervalId = setInterval(() => {
      const nextItems = store.state.items.map(item => {
        const change = (Math.random() - 0.49) * 2;
        return {
          ...item,
          price: Math.max(10, item.price + change),
          delta: change
        };
      });
      store.state.items = nextItems;
    }, 20);
  } else {
    clearInterval(intervalId);
  }
});
```

---

## 13. Exercise

### Level Easy
Modifikasi implementasi `EnterpriseComponent` di Bab 7.2 untuk menambahkan metrik penghitung total perenderan (*render counter*) yang dicetak pada console setiap kali fungsi `render()` selesai dijalankan. Pastikan pemanggilan mutasi 10 state secara berurutan dalam satu fungsi synchronous hanya memicu **satu** kali proses render.

### Level Medium
Buat sebuah mekanisme **Custom Event Bus** menggunakan class native JavaScript yang mendukung:
1. Pendaftaran listener (`on(eventName, handler)`).
2. Trigger event (`emit(eventName, payload)`).
3. Deregistrasi individual listener (`off(eventName, handler)`).
4. Pencegahan Memory Leak: Setiap pemanggilan `on` harus mengembalikan fungsi `unsubscribe` tanpa perlu menyimpan referensi fungsi asli di layer consumer.

### Level Hard
Implementasikan custom scheduler menggunakan `requestIdleCallback` yang bertugas mendistribusikan pemrosesan 5.000 kalkulasi array data berat (contoh: kalkulasi standard deviasi) ke dalam potongan-potongan kecil waktu senggang browser (*idle frames*). Jika sisa waktu frame (`deadline.timeRemaining()`) kurang dari 2ms, komputasi harus ditangguhkan ke idle window berikutnya agar Main Thread tidak pernah mengalami drop frame di bawah 60 FPS.

---

## 14. Challenge

**Skenario**: Anda ditunjuk sebagai Senior Frontend Architect untuk sistem pemantauan gempa bumi nasional.
* **Kebutuhan**: Terdapat peta interaktif dan data feed yang menerima pembaruan gempa mikro dari 3.000 sensor dengan throughput 500 payload/detik.
* **Batasan Teknis**: 
  1. Aplikasi tidak boleh menggunakan framework (Wajib Native Vanilla JS/TS).
  2. Alokasi memori heap browser tidak boleh bertambah lebih dari 5 MB/jam (*Flat Memory Profile*).
  3. Skor INP P95 harus terjaga di bawah 50ms saat user berinteraksi dengan visualisasi sensor.
  4. Penggunaan CPU Main Thread dilarang menyentuh batas 40% pada laptop spesifikasi low-end (Intel Core i3 / 4GB RAM).
* **Tugas Arsitektur**: Rancang proposal desain teknis menyeluruh (lengkap dengan pseudocode arsitektur, diagram pipeline antrean memori, strategi Web Worker serialization, dan algoritma *DOM virtualization*) untuk menyelesaikan kasus ekstrim ini secara deterministik.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)

1. Apa perbedaan mendasar antara fase **Layout** dan fase **Paint** pada Critical Rendering Path?
   - A. Layout menghitung warna piksel, Paint menghitung koordinat node.
   - B. Layout menghitung ukuran dan posisi geometri tiap node; Paint mengisi piksel warna, borders, dan text visuals.
   - C. Layout hanya berjalan pada CSS Flexbox, Paint berjalan pada CSS Grid.
   - D. Paint dieksekusi sebelum Layout di dalam pipeline V8.
   *(Kunci: B)*

2. Di antara event loop phases berikut, manakah yang memiliki prioritas eksekusi paling cepat setelah JavaScript call stack kosong?
   - A. `setTimeout` callback (Macrotask).
   - B. `requestIdleCallback`.
   - C. `Promise.then` callback (Microtask).
   - D. `setImmediate`.
   *(Kunci: C)*

3. Properti CSS manakah di bawah ini yang memicu tahapan **Composite** saja tanpa harus mengulang tahapan Layout dan Paint?
   - A. `top` dan `left`
   - B. `width` dan `height`
   - C. `transform` dan `opacity`
   - D. `margin` dan `padding`
   *(Kunci: C)*

4. Apa dampak penggunaan `innerHTML += '<li>Item</li>'` di dalam sebuah iterasi perulangan 1.000 kali?
   - A. Terjadi serialisasi ulang dan destruksi/rekreasi total seluruh elemen DOM anak sebanyak 1.000 kali secara beruntun.
   - B. Browser mengelompokkannya secara otomatis ke dalam satu frame render tunggal.
   - C. Terjadi optimasi instan di tingkat V8 bytecode.
   - D. Mengurangi konsumsi memori heap secara dramatis.
   *(Kunci: A)*

5. Mengapa method `AbortController.signal` sangat direkomendasikan dalam perancangan arsitektur komponen frontend modern?
   - A. Karena dapat mempercepat rendering CSS Grid.
   - B. Memungkinkan unbinding massal seluruh event listener yang terikat pada sinyal tersebut hanya dengan satu baris pemanggilan `abort()`.
   - C. Mencegah V8 mengeksekusi Garbage Collector.
   - D. Mengubah pemrosesan Main Thread menjadi multi-threaded secara native.
   *(Kunci: B)*

---

### Bagian 2: Intermediate (5 Soal)

6. Apa yang dimaksud dengan fenomena **Layout Thrashing**?
   - A. Memori peramban habis akibat infinite loop recursion.
   - B. Kondisi di mana browser dipaksa menjalankan synchronous layout calculation berulang kali akibat selang-seling operasi DOM Read dan DOM Write.
   - C. Gagalnya GPU melakukan alokasi buffer rendering.
   - D. Terjadinya crash visual karena penumpukan z-index yang melampaui limit 32-bit integer.
   *(Kunci: B)*

7. Diberikan potongan kode:
   ```javascript
   console.log('A');
   setTimeout(() => console.log('B'), 0);
   Promise.resolve().then(() => console.log('C'));
   queueMicrotask(() => console.log('D'));
   console.log('E');
   ```
   Urutan output console yang deterministik adalah:
   - A. A -> B -> C -> D -> E
   - B. A -> E -> B -> C -> D
   - C. A -> E -> C -> D -> B
   - D. A -> C -> D -> E -> B
   *(Kunci: C)*

8. Bagaimana V8 menangani optimasi eksekusi objek dengan struktur properti yang seragam?
   - A. Melalui alokasi Direct RAM Injection.
   - B. Menggunakan sistem **Hidden Classes** (Shapes/Maps) dan **Inline Caches (IC)**.
   - C. Mengonversi seluruh objek menjadi flat binary string.
   - D. Menghapus key yang jarang diakses dari heap.
   *(Kunci: B)*

9. Mengapa *Detached DOM Node* berbahaya bagi stabilitas aplikasi skala enterprise?
   - A. Menyebabkan aplikasi mengalami Cross-Site Scripting (XSS).
   - B. Elemen visual tetap tampil di layar meskipun sudah dihapus dari HTML source.
   - C. Objek node telah dihapus dari DOM Tree aktif, tetapi tetap menempati memori Heap karena referensinya masih tersimpan pada variabel JavaScript.
   - D. Merusak sertifikasi SSL/TLS browser.
   *(Kunci: C)*

10. Apa kegunaan utama dari deklarasi CSS `contain: content;` pada komponen UI yang sering mengalami pembaruan data?
    - A. Memaksa elemen untuk memuat aset gambar secara asinkron.
    - B. Mengisolasi subtree rendering sehingga kalkulasi Reflow dan Repaint di dalam elemen tersebut tidak merembet ke seluruh dokumen luar.
    - C. Mencegah user melakukan copy-paste teks.
    - D. Membatasi ukuran teks agar tidak meluap dari border.
    *(Kunci: B)*

---

### Bagian 3: Production Scenarios (3 Kasus Kompleks)

#### Skenario 1
Sebuah e-commerce web platform mengalami lonjakan metrik **INP (Interaction to Next Paint)** hingga mencapai 650ms saat pengguna mengetik pada input filter pencarian katalog produk. Ketika form diketik, event listener `input` memfilter 40.000 array produk secara sinkron di Main Thread sebelum merender hasilnya.
* **Pertanyaan**: Apa rekomendasi arsitektur terbaik untuk memulihkan skor INP ke batas hijau (< 200ms) tanpa mengurangi fungsionalitas pencarian langsung?
* **Solusi Rekayasa**:
  1. Pindahkan operasi pencarian dan pemfilteran 40.000 item array ke **Dedicated Web Worker** agar Main Thread tetap responsif menerima input ketikan keyboard berikutnya.
  2. Terapkan teknik **Debounce** (misal: 150ms) pada event handler input untuk membatasi frekuensi instruksi kerja.
  3. Render hasil pencarian ke DOM menggunakan pola **Virtual Scrolling** (hanya memanipulasi node yang tampil di viewport).

#### Skenario 2
Tim QA melaporkan bahwa dashboard monitoring operasional pabrik mengalami crash browser tab (Error: *Out of Memory*) secara konsisten setiap kali dashboard dibiarkan menyala selama lebih dari 4 jam pada unit display monitoring. Dashboard tersebut menginstansiasi chart baru menggunakan library pihak ketiga setiap kali menerima polling HTTP tiap 5 detik.
* **Pertanyaan**: Di manakah akar masalah kebocoran memori ini dan bagaimana langkah remediasi arsitekturalnya?
* **Solusi Rekayasa**:
  1. Akar masalah: Instansiasi library chart terus dibuat baru tanpa memanggil metode destruksi visual (`chart.destroy()`), sehingga instance lama, context canvas/SVG, dan event listener internalnya menumpuk di Old Generation Heap (*Detached instances*).
  2. Remediasi: Terapkan metode **Lifecycle Teardown**. Sebelum membuat chart baru, panggil eksplisit fungsi cleanup instance lama. Alternatif terbaik: Jangan instansiasi ulang chart; cukup mutasi dataset instance chart yang sudah ada (`chart.update(newData)`).

#### Skenario 3
Pada aplikasi Single Page Application (SPA) perbankan internal, pengguna melaporkan layar mengalami "kedipan visual" (*screen flickering*) dan perpindahan letak layout (*layout instability*) yang drastis ketika beralih antar tab data rekening nasabah, menghasilkan skor **CLS (Cumulative Layout Shift) = 0.42**.
* **Pertanyaan**: Langkah teknis apa yang wajib diambil untuk mengeliminasi layout shifting tersebut?
* **Solusi Rekayasa**:
  1. Berikan alokasi ukuran geometris tetap (*explicit aspect-ratio* atau *min-height container*) pada wadah penampung data rekening sebelum data AJAX/Fetch selesai dimuat.
  2. Implementasikan struktur **Skeleton Loader** dengan dimensi lebar-tinggi yang identik dengan kontainer data final untuk mereservasi ruang pada Render Tree.
  3. Hindari penyisipan elemen dinamis di atas elemen yang telah selesai dirender tanpa interaksi langsung dari pengguna.

---

## 16. Summary

1. **Browser Internals Mastery**: Menulis kode frontend kelas produksi mensyaratkan pemahaman mendalam atas Critical Rendering Path (DOM -> CSSOM -> Render Tree -> Layout -> Paint -> Composite) dan Event Loop scheduling (Call Stack -> Microtasks -> requestAnimationFrame -> Layout/Paint -> Macrotasks).
2. **Reactivity & State Synchronization**: Hindari mutasi DOM secara langsung dan imperatif. Bangun arsitektur reaktif berbasis `Proxy` dengan scheduler penulisan batch pada microtask loop guna mengeliminasi Layout Thrashing dan redundant paints.
3. **Memory Lifecycle Management**: Kebocoran memori pada browser sering kali berakar dari *Detached DOM Nodes* dan *Dangling Event Listeners*. Biasakan menggunakan sinyal `AbortController` terpadu untuk melakukan disposal massal saat siklus hidup komponen berakhir.
4. **Engineering for Core Web Vitals**: Aplikasi berskala enterprise mengukur keberhasilan rekayasa perangkat lunak melalui stabilitas runtime dan metrik kuantitatif: menjaga INP di bawah 200ms melalui isolasi komputasi (Web Workers) dan menjaga CLS di bawah 0.1 dengan reservasi geometri rendering yang disiplin.