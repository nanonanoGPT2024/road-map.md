# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis dan Membedah Internal Browser Engine**: Memahami siklus eksekusi JavaScript engine (V8/SpiderMonkey) yang beririsan langsung dengan Browser Rendering Pipeline (Blink/Gecko), termasuk perbedaan alokasi pada Task Queue (Macrotask), Microtask Queue, serta kaitannya dengan `requestAnimationFrame` (rAF) dan `requestIdleCallback` (rIC).
- **Mendesain State Machine & Reactive Store Mandiri**: Mengimplementasikan arsitektur state management deterministik berbasis pola desain *Observer* dan *Proxy-based Reactivity* murni (Vanilla JS) tanpa dependensi library eksternal, dengan jaminan *unidirectional data flow*.
- **Mencegah Degradasi Rendering Runtime**: Mengidentifikasi dan memitigasi *Forced Synchronous Layout* (Layout Thrashing), memory leaks akibat *detached DOM nodes*, serta memanipulasi sub-tree DOM berkinerja tinggi menggunakan `DocumentFragment` dan API modern (`IntersectionObserver`, `ResizeObserver`, `MutationObserver`).
- **Membangun Arsitektur Web Siap Produksi**: Mengonfigurasi arsitektur frontend berperforma tinggi yang mematuhi standar Google Core Web Vitals (LCP < 2.5s, INP < 200ms, CLS < 0.1), lengkap dengan strategi caching berlapis (*HTTP Cache-Control*, Service Worker Cache API) dan bundling modern.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Core JavaScript Engine**: Eksekusi konkurensi (Event Loop, Call Stack, Memory Heap, Lexical Environment, Closure).
- **Modern ECMAScript (ES2020+)**: `Promise`, `async/await`, dynamic imports (`import()`), `Proxy`, `Reflect`, `WeakMap`, dan `WeakSet`.
- **DOM/CSSOM Fundamental**: Struktur pohon DOM, CSS cascading & specificity, event bubbling, event capturing, dan event delegation.
- **Tools**: Node.js runtime (v18+ LTS), npm/pnpm, dan familiarity dengan Chrome DevTools (khususnya tab *Performance*, *Memory Heap Snapshot*, dan *Performance Insights*).

---

## 3. Concept & Internal Architecture (Mendalam)

Aplikasi frontend tingkat enterprise tidak hanya berurusan dengan tampilan antarmuka, melainkan bertindak sebagai klien terdistribusi yang mengeksekusi komputasi lokal, sinkronisasi state jaringan, dan orkestrasi perenderan grafis pada perangkat pengguna.

### 3.1 Siklus Hidup Rendering Pipeline & Event Loop
Setiap frame yang dirender oleh browser (misalnya pada monitor 60Hz dengan durasi per frame ~16.67ms, atau 120Hz dengan ~8.33ms) harus melewati alur pipeline yang ketat:

```
[ JavaScript Engine ] -> [ Style Invalidation ] -> [ Layout (Reflow) ] -> [ Paint ] -> [ Composite ]
```

1. **JavaScript Evaluation**: Eksekusi sinkronus, Microtask checkpoint (Promise callbacks, `queueMicrotask`), dan Macrotasks (Timer, I/O callback).
2. **Style Calculation**: Rekonsiliasi selector CSS terhadap pohon DOM guna menghitung *Computed Styles* per elemen.
3. **Layout (Reflow)**: Kalkulasi geometrik (lebar, tinggi, posisi absolut $x, y$) dari elemen-elemen yang memiliki representasi visual.
4. **Paint**: Konversi geometri elemen ke dalam instruksi penggambaran piksel (draw calls) yang dipisahkan ke dalam beberapa layer (Painting layers).
5. **Composite**: Pengiriman bitmap layer ke Graphics Processing Unit (GPU) melalui Compositor Thread untuk dirangkai menjadi frame final pada layar.

```
+-----------------------------------------------------------------------------------+
| Browser Main Thread                                                               |
|                                                                                   |
|  +---------------------+   +-------------------------+   +---------------------+  |
|  | Task (Macrotask)    |-->| Microtasks Drain        |-->| requestAnimation-  |  |
|  | (setTimeout/I/O)    |   | (Promises, queueMicro)  |   | Frame (rAF)         |  |
|  +---------------------+   +-------------------------+   +---------------------+  |
|                                                                     |             |
|  +---------------------+   +-------------------------+              v             |
|  | Paint (Draw calls)  |<--| Layout / Reflow         |<--[ Recalculate Style ]    |
|  +---------------------+   +-------------------------+                            |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Compositor Thread (GPU Rasterization)                                             |
|                                                                                   |
|  [ Layer Trees ] ----> [ Tiling / Raster ] ----> [ GPU Frame Buffer -> Display ]  |
+-----------------------------------------------------------------------------------+
```

### 3.2 Forced Synchronous Layout & Layout Thrashing
Secara default, browser menunda operasi layout hingga akhir frame berjalan (batching). Namun, pembacaan properti geometri (`offsetHeight`, `clientWidth`, `getBoundingClientRect()`, `scrollTop`) secara langsung setelah mutasi DOM akan memaksa engine menjalankan layout seketika itu juga (*Forced Synchronous Layout*). Jika dilakukan berulang kali dalam sebuah loop, fenomena ini disebut **Layout Thrashing**.

```javascript
// ANTI-PATTERN: Layout Thrashing (O(N) layout computation per frame)
for (let i = 0; i < elements.length; i++) {
  // MUTASI DOM (Invalidasi Layout)
  elements[i].style.width = '100px';
  // BACA DOM (Memaksa Browser Melakukan Reflow Seketika)
  const height = elements[i].offsetHeight; 
}

// SOLUSI: Read-then-Write Separation (Batching)
// Baca seluruh metrik terlebih dahulu
const heights = elements.map(el => el.offsetHeight);
// Tulis perubahan secara serentak
elements.forEach((el, i) => {
  el.style.width = '100px';
});
```

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal di Skala Enterprise?
Pada aplikasi berukuran masif (misal: sistem ERP, antarmuka perbankan, platform analitik real-time), pembaruan DOM berbasis *ad-hoc* (misal: `document.getElementById('total').innerText = x`) berakibat pada:
- **Non-Deterministic State**: Sulit memprediksi state mana yang sedang aktif ketika terjadi kesalahan/bug (race conditions data async).
- **Memory Leaks**: Event listener yang menempel pada DOM yang telah dihapus tanpa siklus hidup deregistrasi yang terstandarisasi.
- **Main Thread Stalling**: Eksekusi JavaScript berdurasi panjang (> 50ms) yang memblokir respons antarmuka, mengakibatkan metrik *Interaction to Next Paint* (INP) jebol.

### Apa yang Harus Dibangun?
Arsitektur produksi modern membutuhkan:
1. **Unidirectional Data Architecture**: Aliran data satu arah yang deterministik dari Store $\to$ View $\to$ Action $\to$ Reducer/Mutator $\to$ Store.
2. **Reactivity Engine Berbasis Native Proxy**: Deteksi mutasi state tanpa overhead komputasi perbandingan mendalam (*deep equality checking*) di setiap tick.
3. **Optimized Render Strategy**: Komposit rendering isolatif menggunakan fragmen dan pemanfaatan Web APIs modern untuk *offscreen virtualization*.

---

## 5. How (Workflow Detail)

Alur mutasi dan perenderan data dalam arsitektur reaktif mandiri:

```
[ User Interaction / Network Event ]
                |
                v
        [ Dispatch Action ]
                |
                v
       [ Reducer / Mutator ]
                |
                v
       [ Mutate State Object ]
                |
                v
   [ Proxy Intercepts (set/delete) ]
                |
                v
     [ Notify Subscribers (Set) ]
                |
                v
 [ Batch Schedule via requestAnimationFrame ]
                |
                v
  [ DOM Diffing / Targeted Patch Execution ]
                |
                v
   [ Browser Compositor Updates Screen ]
```

1. **Trigger**: Interaksi pengguna memicu pemanggilan Action.
2. **Dispatch**: Action membawa Payload ke State Mutator murni (deterministic update).
3. **Interception**: Objek `Proxy` menangkap mutasi state (trap `set`), memvalidasi tipe data, dan mendaftarkan ID properti yang kotor (*dirty property*).
4. **Micro-Queue/Batching**: Render tidak langsung dieksekusi seketika melainkan dijadwalkan via `requestAnimationFrame` untuk mencegah redundant render.
5. **Reconciliation & Mutate**: Hanya bagian DOM yang bergantung pada *dirty property* yang dirender ulang menggunakan `Node.replaceChild` atau mutasi atribut langsung.

---

## 6. Analogy & Diagram ASCII

Bayangkan sebuah **Restoran Bintang Lima**:
- **Kitchen (JavaScript Engine)**: Koki memasak pesanan makanan (komputasi data).
- **Service Window (Layout & Reflow)**: Pengatur piring menyusun piring secara presisi sesuai ukuran meja tamu.
- **Waiter/Runner (Compositor Thread & GPU)**: Membawa piring yang sudah ditata ke meja tanpa mengubah isi masakan.

Jika Koki terus memanggil Pengatur Piring untuk mengukur ulang diameter mangkuk di setiap potongan daun bawang (*Layout Thrashing*), seluruh proses dapur berhenti total. Restoran yang efisien akan menyiapkan semua potongan bahan (Compute), menatanya sekaligus (Batch Layout), lalu membiarkan Runner mengantarnya dengan cepat (Compositing).

```
TRADISIONAL (Layout Thrashing):
Kitchen: [Potong] -> Ping Waiter: [Ukur Meja!] -> [Potong] -> Ping Waiter: [Ukur Meja!] -> [Kelelahan/Stall]

ARSITEKTUR PRODUKSI (Batched Phase):
Kitchen:    [Potong][Potong][Potong] (JavaScript State Processing)
                      |
                      v
Plating:    [Tata Semua Mangkuk Sekaligus] (Single Reflow / DocumentFragment)
                      |
                      v
Runners:    [Kirim ke Meja Tamu] (GPU Compositing)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Reaktivitas Mandiri Berbasis `Proxy`
Contoh fondasi reaktivitas minimalis menggunakan JavaScript murni.

```javascript
/**
 * Primitive Reactive Implementation
 */
function createSignal(initialValue) {
  let value = initialValue;
  const subscribers = new Set();

  const read = () => {
    return value;
  };

  const write = (newValue) => {
    if (value !== newValue) {
      value = newValue;
      subscribers.forEach((callback) => callback(value));
    }
  };

  const subscribe = (callback) => {
    subscribers.add(callback);
    callback(value); // Initial run
    return () => subscribers.delete(callback); // Teardown function
  };

  return [read, write, subscribe];
}

// Penggunaan:
const [count, setCount, onCountChange] = createSignal(0);
const unsubscribe = onCountChange((val) => {
  console.log(`DOM Updated: Count is now ${val}`);
});

setCount(1); // Output: DOM Updated: Count is now 1
setCount(2); // Output: DOM Updated: Count is now 2
unsubscribe();
setCount(3); // Tidak ada output (listener dicabut)
```

### 7.2 Practical Example: Enterprise-Grade Observable Store & Component Architecture
Berikut implementasi nyata arsitektur state management mutakhir dengan *batched asynchronous DOM patcher*.

```typescript
// types.ts
export type Listener<T> = (state: T) => void;
export type Unsubscribe = () => void;

export interface StoreOptions<T> {
  enableLogging?: boolean;
}

// store.ts
export class ReactiveStore<T extends Record<string, any>> {
  private _state: T;
  private _listeners: Set<Listener<T>> = new Set();
  private _isQueued = false;

  constructor(initialState: T, private options: StoreOptions<T> = {}) {
    this._state = this._createProxy(initialState);
  }

  public get state(): T {
    return this._state;
  }

  public subscribe(listener: Listener<T>): Unsubscribe {
    this._listeners.add(listener);
    // Jalankan satu kali untuk inisialisasi visual
    listener(this._state);
    return () => {
      this._listeners.delete(listener);
    };
  }

  private _createProxy(target: T): T {
    const handler: ProxyHandler<T> = {
      get: (obj, prop: string | symbol) => {
        const val = Reflect.get(obj, prop);
        if (val !== null && typeof val === 'object') {
          return this._createProxy(val); // Deep reactivity
        }
        return val;
      },
      set: (obj, prop: string | symbol, value: any) => {
        const oldValue = Reflect.get(obj, prop);
        if (oldValue !== value) {
          const success = Reflect.set(obj, prop, value);
          if (success) {
            this._scheduleNotify();
          }
          return success;
        }
        return true;
      }
    };
    return new Proxy(target, handler);
  }

  private _scheduleNotify(): void {
    if (this._isQueued) return;
    this._isQueued = true;

    // Batching perbaruan DOM ke rAF (align dengan refresh rate layar)
    window.requestAnimationFrame(() => {
      if (this.options.enableLogging) {
        console.info('[Store Mutate Flush]', this._state);
      }
      this._listeners.forEach((listener) => listener(this._state));
      this._isQueued = false;
    });
  }
}

// component.ts
export abstract class BaseComponent<T extends Record<string, any>> {
  protected container: HTMLElement;
  protected store: ReactiveStore<T>;
  private _unsubscribe: Unsubscribe | null = null;

  constructor(containerId: string, store: ReactiveStore<T>) {
    const el = document.getElementById(containerId);
    if (!el) {
      throw new Error(`Target container #${containerId} tidak ditemukan di DOM.`);
    }
    this.container = el;
    this.store = store;
  }

  public mount(): void {
    this._unsubscribe = this.store.subscribe((state) => {
      this._renderOptimized(state);
    });
  }

  public unmount(): void {
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
    this.container.innerHTML = '';
  }

  // Menggunakan DocumentFragment untuk menghindari continuous reflow
  private _renderOptimized(state: T): void {
    const fragment = document.createDocumentFragment();
    const temporaryWrapper = document.createElement('div');
    temporaryWrapper.innerHTML = this.template(state);

    while (temporaryWrapper.firstChild) {
      fragment.appendChild(temporaryWrapper.firstChild);
    }

    this.container.replaceChildren(fragment);
    this.afterRender();
  }

  protected abstract template(state: T): string;
  protected afterRender(): void {}
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Financial High-Frequency Order Book Dashboard
Sebuah platform broker trading memproses lebih dari 1.000 transaksi per detik. Dashboard trader menampilkan daftar penawaran (Order Book) dan histori transaksi terkini.

#### Permasalahan:
- Implementasi awal menggunakan pembaruan langsung ke DOM via panggilan WebSocket:
  ```javascript
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    const row = document.createElement('tr');
    row.innerHTML = `<td>${data.price}</td><td>${data.amount}</td>`;
    tableBody.appendChild(row); // 1000x appendChild per detik!
  };
  ```
- **Dampak Fatal**: CPU Main Thread 100%, terjadi pembekuan UI (*jank* parah), metrik INP melonjak ke **850ms**, konsumsi memori browser meroket hingga crash (*Out Of Memory* / OOM) setelah 15 menit berjalan.

#### Solusi Rekayasa Arsitektur:
1. **Penerapan Virtual Scroller / Windowing**: Merender hanya elemen yang berada di dalam *Viewport* pengguna ($\sim 30$ baris) menggunakan `IntersectionObserver`.
2. **Buffer Stream dengan Micro-batching**:
   - Memasukkan data transaksi WebSocket ke dalam *in-memory ring buffer*.
   - Mengosongkan (*flush*) buffer ke Store hanya sekali per tick layar menggunakan `requestAnimationFrame`.
3. **Penyimpanan Objek Menggunakan Primitif Tipe Data Tetap**: Penggunaan `TypedArray` (`Float64Array`) untuk data harga historis guna meminimalisir overhead Garbage Collector (GC).

#### Hasil Implementasi:
- **FPS**: Stabil di 60 FPS tanpa drop frame.
- **INP (Interaction to Next Paint)**: Turun dari 850ms menjadi **24ms**.
- **Memory Footprint**: Stabil di $\sim 45\text{MB}$ konstan selama 24 jam pengujian stress-test.

---

## 9. Trade-offs

| Pendekatan / Keputusan Arsitektur | Keuntungan | Biaya / Trade-off | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Proxy-Based Deep Reactivity** | Developer Experience (DX) unggul; mutasi objek otomatis memicu sinkronisasi UI tanpa wrapper rumit. | Overhead memori bertambah untuk nested object; penalti performa pada mutasi dataset masif (>100k entitas). | Gunakan mutasi dangkal (*shallow reactivity*) atau `Object.freeze()` untuk koleksi data statis berukuran besar. |
| **Batched Updates via `requestAnimationFrame`** | Mengeliminasi *Layout Thrashing*; meratakan pembaruan antarmuka dengan refresh rate perangkat. | Peningkatan latensi internal minor (data yang diperbarui akan tertunda maksimal $16.6\text{ms}$). | Dapat diterima untuk representasi visual manusia; gunakan microtask untuk komputasi background non-visual. |
| **Virtual DOM Custom / ReplaceChildren Batching** | Mencegah state UI tidak sinkron (*desynchronization*); bebas dari kompleksitas library luar. | Melakukan *re-instantiation* parser HTML browser jika parsing template string digunakan tanpa diffing cerdas. | Terapkan fine-grained update langsung ke Text Node atau gunakan template cloning (`<template>`). |
| **Fine-grained Observers (Mutation/Resize)** | Akurasi tinggi terhadap perubahan DOM/Viewport secara asynchronous. | Alokasi memori berlebih jika observer dibuat berulang kali per elemen individual. | Pola *Shared Observer Singleton*: satu instance observer memantau banyak target DOM element. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Memory Leak Melalui Detached DOM Nodes
**Masalah**: Menghapus elemen dari tampilan visual (DOM tree), namun referensinya masih tersimpan di dalam memori JavaScript (array, closure, atau event listener). Browser tidak dapat melakukan *garbage collect*.

```javascript
// KESALAHAN FATAL:
const elementCache = [];

function createWidget() {
  const btn = document.createElement('button');
  btn.innerText = "Klik Saya";
  document.body.appendChild(btn);
  
  elementCache.push(btn); // Referensi kuat tersimpan di sini!
  
  btn.addEventListener('click', () => {
    // btn dihapus dari DOM, namun elementCache masih memegangnya
    document.body.removeChild(btn);
  });
}
```

**Solusi & Troubleshooting via Chrome DevTools**:
1. Gunakan `WeakMap` atau `WeakSet` jika membutuhkan asosiasi metadata terhadap DOM Node.
2. Buka DevTools $\to$ Tab **Memory** $\to$ Pilih **Heap snapshot** $\to$ Lakukan aksi UI $\to$ Ambil Snapshot kedua.
3. Filter dengan kata kunci: `Detached HTMLButtonElement`.
4. Jika ditemukan objek berwarna merah/kuning, periksa *Retainer tree* di panel bawah untuk melacak closure/variabel global mana yang masih mengikat elemen tersebut.

### 10.2 Microtask Queue Starvation
**Masalah**: Pemanggilan microtask rekursif tanpa henti yang memblokir Browser Main Thread, sehingga rAF, layout, dan paint tidak pernah dieksekusi.

```javascript
// KESALAHAN FATAL:
function infiniteMicrotask() {
  Promise.resolve().then(() => {
    infiniteMicrotask(); // Microtask Queue tidak pernah kosong!
  });
}
// Browser UI akan freeze total meski CPU tidak crash seketika.
```

**Solusi**:
Jadwalkan iterasi komputasi intensif menggunakan Macrotask scheduling (`setTimeout(fn, 0)`) atau web workers, atau gunakan `scheduler.yield()` pada browser modern.

---

## 11. Best Practices (Production Checklist)

### Layout & Render Optimization
- [ ] Hindari pembacaan properti geometri (`offsetWidth`, `getBoundingClientRect`) tepat setelah mutasi CSS/DOM.
- [ ] Terapkan CSS `contain: content;` atau `contain: strict;` pada sub-komponen terisolasi untuk membatasi ruang lingkup reflow layout engine.
- [ ] Pastikan animasi berjalan eksklusif pada properti `transform` dan `opacity` untuk delegasi komputasi penuh ke GPU Compositor thread.

### Event & Memory Lifecycle
- [ ] Wajib menyediakan method `destroy()` atau `unmount()` pada setiap class komponen untuk mencabut event listener dan memutuskan observer (`observer.disconnect()`).
- [ ] Gunakan `AbortController` untuk pembersihan event listener massal:
  ```javascript
  const controller = new AbortController();
  element.addEventListener('click', handler, { signal: controller.signal });
  // Saat teardown:
  controller.abort(); // Mencabut seluruh listener terdaftar secara otomatis
  ```

### Asset Delivery & Core Web Vitals
- [ ] Pastikan Largest Contentful Paint (LCP) elemen memiliki atribut CSS `fetchpriority="high"`.
- [ ] Tetapkan dimensi eksplisit (`width` dan `height` atau `aspect-ratio`) pada semua media gambar dan video untuk menjamin Cumulative Layout Shift (CLS) bernilai 0.

---

## 12. Hands-on Practice

Buatlah proyek modular produksi sederhana di direktori `hands-on/m02/` dengan struktur berikut:

```
hands-on/m02/
├── index.html
├── src/
│   ├── core/
│   │   ├── Store.js
│   │   └── Component.js
│   ├── components/
│   │   └── TransactionList.js
│   └── main.js
└── styles/
    └── main.css
```

### Langkah 1: Siapkan `hands-on/m02/index.html`
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Production High-Performance Architecture</title>
  <link rel="stylesheet" href="styles/main.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>Enterprise Transaction Feed</h1>
      <div id="metrics-panel">
        <span>FPS: <strong id="fps-counter">0</strong></span>
        <span>Item Count: <strong id="item-counter">0</strong></span>
      </div>
      <button id="btn-stress-test" class="btn">Mulai Stream Transaksi</button>
    </header>

    <main>
      <div id="transaction-container"></div>
    </main>
  </div>
  <script type="module" src="src/main.js"></script>
</body>
</html>
```

### Langkah 2: Buat Reactive Store `hands-on/m02/src/core/Store.js`
```javascript
export class Store {
  #state;
  #listeners = new Set();
  #rafId = null;

  constructor(initialState = {}) {
    this.#state = this.#createReactiveObject(initialState);
  }

  get state() {
    return this.#state;
  }

  subscribe(listener) {
    this.#listeners.add(listener);
    listener(this.#state);
    return () => this.#listeners.delete(listener);
  }

  #createReactiveObject(target) {
    return new Proxy(target, {
      get: (obj, prop) => {
        const value = Reflect.get(obj, prop);
        if (value !== null && typeof value === 'object') {
          return this.#createReactiveObject(value);
        }
        return value;
      },
      set: (obj, prop, value) => {
        const oldVal = Reflect.get(obj, prop);
        if (oldVal !== value) {
          Reflect.set(obj, prop, value);
          this.#dispatchFlush();
        }
        return true;
      }
    });
  }

  #dispatchFlush() {
    if (this.#rafId) return;
    this.#rafId = window.requestAnimationFrame(() => {
      this.#listeners.forEach(fn => fn(this.#state));
      this.#rafId = null;
    });
  }
}
```

### Langkah 3: Buat Base Component `hands-on/m02/src/core/Component.js`
```javascript
export class Component {
  #unsubscribe = null;

  constructor(container, store) {
    if (!container) throw new Error("Root container DOM target wajib didefinisikan.");
    this.container = container;
    this.store = store;
  }

  mount() {
    this.#unsubscribe = this.store.subscribe((state) => {
      this.render(state);
    });
  }

  unmount() {
    if (this.#unsubscribe) {
      this.#unsubscribe();
      this.#unsubscribe = null;
    }
  }

  render(state) {
    throw new Error("Method render() wajib diimplementasikan oleh turunan kelas.");
  }
}
```

### Langkah 4: Implementasikan `hands-on/m02/src/components/TransactionList.js`
```javascript
import { Component } from '../core/Component.js';

export class TransactionList extends Component {
  render(state) {
    // Optimasi: Memanfaatkan HTML Template & DocumentFragment
    const fragment = document.createDocumentFragment();
    const listWrapper = document.createElement('ul');
    listWrapper.className = 'tx-list';

    state.transactions.slice(-20).reverse().forEach((tx) => {
      const li = document.createElement('li');
      li.className = `tx-item tx-${tx.type}`;
      li.innerHTML = `
        <span class="tx-id">#${tx.id}</span>
        <span class="tx-account">${tx.account}</span>
        <span class="tx-amount">$${tx.amount.toFixed(2)}</span>
      `;
      listWrapper.appendChild(li);
    });

    fragment.appendChild(listWrapper);
    this.container.replaceChildren(fragment);
  }
}
```

### Langkah 5: Buat Integrasi Utama `hands-on/m02/src/main.js`
```javascript
import { Store } from './core/Store.js';
import { TransactionList } from './components/TransactionList.js';

const initialState = {
  transactions: [],
  isRunning: false
};

const appStore = new Store(initialState);
const container = document.getElementById('transaction-container');
const listComponent = new TransactionList(container, appStore);
listComponent.mount();

// Monitoring FPS Sederhana
let frameCount = 0;
let lastTime = performance.now();
const fpsDisplay = document.getElementById('fps-counter');
const itemDisplay = document.getElementById('item-counter');

function loopMetrics() {
  frameCount++;
  const now = performance.now();
  if (now - lastTime >= 1000) {
    fpsDisplay.innerText = frameCount.toString();
    frameCount = 0;
    lastTime = now;
  }
  window.requestAnimationFrame(loopMetrics);
}
loopMetrics();

// Generator Transaksi Berkelajuan Tinggi
const stressBtn = document.getElementById('btn-stress-test');
let intervalId = null;
let currentId = 1000;

stressBtn.addEventListener('click', () => {
  appStore.state.isRunning = !appStore.state.isRunning;

  if (appStore.state.isRunning) {
    stressBtn.innerText = "Hentikan Stream Transaksi";
    stressBtn.classList.add('active');

    // Menghasilkan data setiap 10ms (100 event per detik)
    intervalId = setInterval(() => {
      currentId++;
      const accounts = ['ACC-ID-9921', 'ACC-ID-4412', 'ACC-ID-7819', 'ACC-ID-0012'];
      const types = ['credit', 'debit'];
      
      const newTx = {
        id: currentId,
        account: accounts[Math.floor(Math.random() * accounts.length)],
        type: types[Math.floor(Math.random() * types.length)],
        amount: Math.random() * 5000 + 10
      };

      // Mutasi State
      appStore.state.transactions.push(newTx);
      itemDisplay.innerText = appStore.state.transactions.length.toString();
    }, 10);
  } else {
    stressBtn.innerText = "Mulai Stream Transaksi";
    stressBtn.classList.remove('active');
    clearInterval(intervalId);
  }
});
```

### Langkah 6: Tambahkan Desain `hands-on/m02/styles/main.css`
```css
:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --text-main: #f8fafc;
  --accent-green: #10b981;
  --accent-red: #ef4444;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-main);
  padding: 24px;
}

#app {
  max-width: 800px;
  margin: 0 auto;
}

header {
  background: var(--bg-secondary);
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 24px;
}

#metrics-panel {
  margin: 12px 0;
  display: flex;
  gap: 24px;
}

.btn {
  background: #3b82f6;
  border: none;
  color: white;
  padding: 10px 20px;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
}

.btn.active {
  background: var(--accent-red);
}

.tx-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tx-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 16px;
  background-color: var(--bg-secondary);
  border-radius: 6px;
  contain: content; /* Mencegah reflow merambat keluar */
}

.tx-credit { border-left: 4px solid var(--accent-green); }
.tx-debit { border-left: 4px solid var(--accent-red); }
```

---

## 13. Exercises

### Level Easy
Modifikasi file `Store.js` agar memiliki method pembantu `reset()`, yang mengembalikan seluruh state ke kondisi inisial tanpa memutuskan array listener yang sudah terdaftar.

### Level Medium
Tambahkan *Selector Caching* (Memoization) pada class `Component`. Komponen hanya boleh menjalankan `render()` jika subset slice state tertentu yang didefinisikan mengalami mutasi nilai riil (shallow equality), bukan setiap kali state global berubah.

### Level Hard
Implementasikan struktur *Virtual Windowing* murni pada `TransactionList.js` tanpa plugin pihak ketiga. Jika array state memiliki 10.000 entitas transaksi, DOM hanya boleh memuat maksimal 15 Node `<li>` sesuai koordinat scroll viewport pengguna saat ini.

---

## 14. Challenge

### Studi Kasus: Telemetry Canvas & DOM Real-Time Visualizer
Sebuah laboratorium sensor industri meminta Anda membuat dashboard web pemantauan suhu 500 unit mesin secara paralel.

**Ketentuan Teknis**:
1. Setiap sensor mengirimkan pembaruan data acak berfrekuensi 30Hz - 60Hz.
2. Anda dilarang menggunakan framework eksternal apa pun (React, Vue, Svelte, Angular).
3. Anda harus menyajikan dua layer:
   - Layer 1 (DOM Tree): Status ringkasan dan alarm peringatan jika suhu $> 100^\circ\text{C}$.
   - Layer 2 (HTML5 Canvas): Mini grafik plot riwayat tren suhu 60 detik terakhir per mesin.
4. **Batas Toleransi Kinerja**:
   - Total Long Task (Main Thread execution $> 50\text{ms}$) harus bernilai **0**.
   - Konsumsi CPU Main thread pada laptop baseline (Core i5 4-core) tidak boleh melampaui **25%**.
   - Tidak boleh ada alokasi Garbage Collection besar yang memicu freeze visual.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (5 Soal)
1. Mengapa eksekusi mutasi DOM dianggap sebagai operasi yang "mahal" (expensive) di browser web?
2. Apa perbedaan mendasar antara Microtask Queue dan Macrotask (Task) Queue dalam eksekusi Event Loop?
3. Pada tahapan rendering pipeline manakah properti CSS `transform: translate3d()` dieksekusi?
4. Apa fungsi dari Web API `requestAnimationFrame` dan kapan browser mengeksekusinya?
5. Mengapa teknik `replaceChildren()` atau `DocumentFragment` lebih diutamakan dibandingkan manipulasi `innerHTML` berulang kali?

### Bagian B: Analisis & Arsitektur (5 Soal)
1. Perhatikan kode berikut:
   ```javascript
   const w1 = box1.offsetWidth;
   box1.style.width = (w1 + 10) + 'px';
   const w2 = box2.offsetWidth;
   box2.style.width = (w2 + 10) + 'px';
   ```
   Sebutkan nama anomali performa yang terjadi dan jelaskan langkah perbaikannya!
2. Mengapa struktur data `WeakMap` sangat krusial digunakan saat mengasosiasikan private state dengan elemen DOM?
3. Jelaskan risiko arsitektural dari implementasi `Proxy` yang mengintercept operasi `get` dan `set` secara rekursif mendalam (*deep reactive*) pada struktur data JSON dengan 50.000 baris array!
4. Bagaimana CSS property `contain: strict;` membantu browser menghemat siklus CPU saat terjadi mutasi DOM pada subtree komponen?
5. Mengapa metrik Core Web Vitals *Interaction to Next Paint* (INP) menggantikan First Input Delay (FID)? Apa yang diukur secara berbeda?

### Bagian C: Skenario Kasus Produksi (3 Soal)

#### Skenario 1: The Memory Leak Mystery
Aplikasi dashboard Single-Page Application (SPA) perbankan Anda menggunakan arsitektur Vanilla JS Component. Pengguna yang membuka aplikasi selama lebih dari 3 jam berturut-turut tanpa me-refresh halaman melaporkan bahwa browser menjadi sangat lambat hingga akhirnya menampilkan halaman error crash (*Aw, Snap!*).
- **Pertanyaan**: Langkah investigasi apa yang akan Anda jalankan di Chrome DevTools, hipotesis kegagalan apa yang paling mungkin terjadi pada implementasi siklus hidup komponen, dan bagaimana solusinya?

#### Skenario 2: The E-Commerce Infinite Scroll Lock
Sebuah halaman katalog e-commerce menerapkan *infinite scroll*. Setelah memuat 500 produk pakaian beserta gambar dan keterangannya, pengguna mengalami freeze layar setiap kali menggulir halaman ke atas atau ke bawah.
- **Pertanyaan**: Jelaskan mengapa memory dan render tree browser tersendat meskipun gambar sudah di-*lazy-load*, dan arsitektur apa yang wajib diimplementasikan untuk menyelesaikan masalah ini?

#### Skenario 3: The Broken Metrics Score
Sebuah aplikasi web logistik menunjukkan skor LCP 1.1 detik (Sangat Baik), namun nilai CLS mencapai 0.45 (Buruk, batas aman < 0.1). Setelah dianalisis, banner promo dinamis dan font kustom diinjeksi via JavaScript tepat setelah data API berhasil diterima.
- **Pertanyaan**: Jelaskan mengapa fenomena tersebut merusak skor CLS dan bagaimana langkah rekayasa CSS serta DOM layout untuk memaksa CLS kembali ke angka 0?

---

## 16. Summary
- Menulis kode frontend kelas enterprise menuntut pemahaman menyeluruh terhadap **Browser Internals**, bukan sekadar menempelkan pustaka pihak ketiga.
- Eksekusi JavaScript, penghitungan style, layout (reflow), painting, dan compositing memiliki kaitan siklus yang terstruktur. Pengabaian siklus ini memicu kegagalan fatal seperti **Layout Thrashing** dan **Main Thread Lock**.
- Pola arsitektur berbasis **Proxy Reactivity** yang dipadukan dengan **Batching Scheduler** (`requestAnimationFrame`) memastikan mutasi state secepat apa pun tetap sinkron secara teratur dengan siklus refresh hardware.
- Penggunaan API native mutakhir (`IntersectionObserver`, `DocumentFragment`, `AbortController`, dan CSS containment) adalah fondasi utama dalam menciptakan aplikasi dengan metrik **Core Web Vitals** yang konsisten di standar hijau produksi.

---

### Jawaban Kunci Quiz Evaluasi

#### Bagian A
1. Karena mutasi DOM memicu rangkaian invalidasi pohon render browser: penghitungan ulang Computed CSSOM, kalkulasi geometri (Reflow), repainting layer piksel, hingga pengiriman bitmap ke GPU.
2. Microtask Queue (Promise, `queueMicrotask`) dieksekusi secara instan dan tuntas tepat setelah Call Stack sinkronus kosong sebelum giliran Macrotask berikutnya dieksekusi atau sebelum browser melakukan rendering/paint. Macrotask (Timer, I/O) dieksekusi satu per siklus event loop.
3. Dieksekusi langsung pada tahap **Compositing** (Compositor Thread & GPU), melompati tahapan Layout dan Paint secara total.
4. `requestAnimationFrame` meminta browser menjadwalkan pembaruan visual tepat sebelum proses Repaint frame berikutnya berjalan, sinkron dengan refresh rate fisik monitor.
5. `innerHTML` memaksa browser menghancurkan seluruh pohon sub-DOM lama dan mem-parsing ulang string menjadi token HTML secara berulang (overhead parsing tinggi). Sebaliknya, `DocumentFragment` dan `replaceChildren` melakukan mutasi secara in-memory dalam satu batch operasional atomic.

#### Bagian B
1. **Layout Thrashing (Forced Synchronous Layout)**. Solusi: Pisahkan fase baca dan tulis:
   ```javascript
   const w1 = box1.offsetWidth;
   const w2 = box2.offsetWidth;
   box1.style.width = (w1 + 10) + 'px';
   box2.style.width = (w2 + 10) + 'px';
   ```
2. Karena `WeakMap` memegang referensi kunci objek secara *lemah* (*weak reference*). Ketika elemen DOM dihapus dari tree, Garbage Collector dapat secara otomatis memusnahkan asosiasi data tersebut tanpa meninggalkan memory leak.
3. Pembuatan Proxy rekursif pada skala 50.000 objek akan memakan alokasi heap memori yang masif dan memperlambat CPU saat melakukan traversal struktur data; mutasi primitif kecil dapat memicu invalidasi berantai jika tidak dipagari dengan pembatasan kedalaman (*depth limiting*).
4. `contain: strict;` memberi tahu browser bahwa elemen tersebut memiliki dimensi mandiri dan perubahannya tidak akan pernah memengaruhi layout elemen luar. Browser membatasi area reflow hanya pada kotak elemen bersangkutan.
5. FID hanya mengukur latensi respons interaksi *pertama kali*, sedangkan INP mengukur responsivitas latensi dari *seluruh* interaksi (klik, ketuk, ketik) sepanjang siklus hidup sesi aplikasi hingga frame layar baru benar-benar selesai digambar (*painted*).

#### Bagian C
1. **Skenario 1**: Ambil snapshot heap di DevTools Memory tab, cari `Detached HTMLElement`. Hipotesis: Sub-komponen yang dihapus tidak mencabut listener atau referensi pada state global store masih menempel. Solusi: Jalankan unmount hook untuk mencabut seluruh listener dan bersihkan subscriber array store.
2. **Skenario 2**: Terjadi ledakan jumlah DOM nodes (DOM bloat). Meskipun gambar di-lazy-load, ratusan ribu simpul elemen DOM tetap membebani memory heap dan pohon layout. Solusi: Gunakan teknik *Virtual Scrolling/DOM Windowing* (hanya 15-30 elemen DOM aktif yang eksis secara riil).
3. **Skenario 3**: Banner promo dan pemuatan Web Font mengubah ukuran layout elemen tetangga secara tiba-tiba (*layout shift*). Solusi: Berikan skeleton container dengan dimensi `height` tetap menggunakan CSS sebelum data tiba, dan gunakan CSS `font-display: optional;` atau `font-display: swap;` dengan metrik fallback yang diselaraskan (*size-adjust*).