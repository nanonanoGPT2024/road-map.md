# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 01-Core-Foundations | **Topik:** frontend-beginner | **Bab:** BAB-10-Materi-Lanjutan

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
- **Menganalisis & Mengoptimasi Critical Rendering Path (CRP):** Mengidentifikasi hambatan parsing HTML/CSS, tahapan Style Recalculation, Layout (Reflow), Paint, dan Compositing pada browser engine (Blink/V8).
- **Menguasai Runtime Concurrency & Event Loop:** Membedakan eksekusi Synchronous Call Stack, Microtasks (`Promise`, `queueMicrotask`, `MutationObserver`), Macrotasks (`setTimeout`, I/O, UI Rendering), dan `requestAnimationFrame` untuk mencegah *frame drops*.
- **Mengeliminasi Layout Thrashing & Memory Leaks:** Mendiagnosis pemanggilan DOM API yang memicu sinkronisasi reflow paksa (*forced synchronous layout*) dan mengatasi kebocoran memori akibat *detached DOM nodes* serta *uncleaned closures*.
- **Membangun Arsitektur State Terdesentralisasi Tanpa Framework:** Mengimplementasikan pola reaktivitas modern (Observer/Signal pattern) berbasis Vanilla TypeScript dengan isolasi layer domain, data, dan UI.
- **Mengintegrasikan Background Thread Processing:** Mengalokasikan komputasi berat ke Web Workers untuk menjaga *Interaction to Next Paint* (INP) tetap berada di bawah ambang batas 200ms.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- **Core JavaScript (ES6+):** Closure, Lexical Scope, Prototype Chain, Promises, `async/await`, ES Modules (`import`/`export`).
- **DOM Manipulation Dasar:** Penggunaan `querySelector`, `addEventListener`, manipulasi *class list*, traversal node.
- **Modern CSS Fundamentals:** CSS Box Model, Flexbox, Grid, CSS Custom Properties (Variables), dan konsep dasar CSS Specificity.
- **Perkakas Pengembangan:** Penggunaan Chrome DevTools (Elements panel, Console panel, dasar Network panel), serta Node.js/npm untuk eksekusi build tool.

---

## 3. Concept & Internal Architecture

Memahami frontend pada tingkat enterprise menuntut pemahaman terhadap apa yang terjadi di balik abstraksi UI library/framework. Browser adalah sistem terdistribusi kompleks yang memproses data jaringan mentah menjadi piksel pada layar melalui dua subsistem utama: **Rendering Engine** (misalnya, Blink pada Chromium) dan **JavaScript Engine** (misalnya, V8).

```
+----------------------------------------------------------------------------------------------------+
|                                      BROWSER ARCHITECTURE                                          |
+----------------------------------------------------------------------------------------------------+
| [ Network Layer ] --> Bytes (HTML, CSS, JS)                                                       |
|        |                                                                                           |
|        v                                                                                           |
| +-----------------------------------------------+  +--------------------------------------------+ |
| |           RENDERING ENGINE (Blink)            |  |             JS ENGINE (V8)                 | |
| |                                               |  |                                            | |
| | HTML Parsing ---> DOM Tree                    |  | Memory Heap (Object allocations)           | |
| | CSS Parsing  ---> CSSOM Tree                  |  | Call Stack  (Execution contexts)          | |
| |        |             |                        |  |                                            | |
| |        +------+------+                        |  | Event Loop:                                | |
| |               v                               |  |  [Call Stack Empty?]                       | |
| |          Render Tree                          |  |         |                                  | |
| |               |                               |  |         v                                  | |
| |               v                               |  |  Process ALL Microtasks (Promise, queueMT) | |
| |       Layout (Reflow)                         |  |         |                                  | |
| |   (Geometry: x, y, width, height)             |  |         v                                  | |
| |               |                               |  |  Run requestAnimationFrame callbacks       | |
| |               v                               |  |         |                                  | |
| |       Paint (Rasterization)                   |  |         v                                  | |
| |   (Draw calls, paint records)                 |  |  Browser Render (Style, Layout, Paint)     | |
| |               |                               |  |         |                                  | |
| |               v                               |  |         v                                  | |
| |       Compositing (GPU)                       |  |  Process ONE Macrotask (Timer, I/O, Event) | |
| |   (Transform layers onto screen via GPU)      |  |                                            | |
| +-----------------------------------------------+  +--------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

### Critical Rendering Path (CRP) Internals
1. **DOM Tree Construction:** HTML diubah dari *Bytes* $\to$ *Characters* $\to$ *Tokens* $\to$ *Nodes* $\to$ *DOM Tree*. Proses ini bersifat *incremental* (streaming).
2. **CSSOM Tree Construction:** CSS bersifat *render-blocking*. CSSOM harus dibangun secara lengkap sebelum Render Tree dapat dibentuk karena cascading rules dapat mengubah visual node mana pun kapan saja.
3. **Render Tree:** Kombinasi DOM dan CSSOM. Node dengan `display: none` diabaikan, namun node dengan `visibility: hidden` tetap masuk ke Render Tree karena masih memakan ruang geometris.
4. **Layout (Reflow):** Menghitung kalkulasi posisi geometris presisi (koordinat vektor `x, y` dan dimensi `width, height`) dari setiap elemen dalam viewport.
5. **Paint:** Mengonversi visual node menjadi *paint records* (instruksi piksel seperti warna, border, shadow).
6. **Compositing:** Memisahkan elemen ke dalam layer GPU yang berbeda (misalnya elemen dengan `will-change: transform`), merasternya, dan menyusunnya bersama untuk ditampilkan ke display buffer.

### V8 Engine Memory & Event Loop Execution Order
JavaScript berjalan di *single-threaded environment* untuk komputasi logikanya (main thread), yang berbagi thread dengan rendering pipeline browser.
- **Heap:** Alokasi memori dinamis untuk objek, closure, dan array. V8 mengelola memori via *Orinoco Garbage Collector* (Generational GC: Nursery/Intermediate untuk *Young Generation*, Old Space untuk *Old Generation*).
- **Call Stack:** Struktur data LIFO (Last In First Out) yang menyimpan Execution Contexts.
- **Microtask Queue:** Dieksekusi secara tuntas (*run-to-completion until queue is drained*) segera setelah Call Stack kosong, **sebelum** browser diperbolehkan merender frame baru.
- **Macrotask Queue:** Diambil tepat satu task per loop iterasi, setelah itu runtime memeriksa ketersediaan microtask dan kebutuhan rendering.

---

## 4. Why & What

### Mengapa Pemahaman Arsitektur Lanjutan Penting?
Banyak pengembang terjebak dalam ilusi bahwa framework (seperti React, Vue, atau Angular) secara otomatis menyelesaikan semua masalah skalabilitas. Faktanya:
- Framework hanyalah lapisan abstraksi di atas Web API.
- Framework tidak dapat mencegah *Layout Thrashing* jika pengembang memanggil properti geometri seperti `element.offsetHeight` di dalam loop render.
- Kebocoran memori pada Single Page Application (SPA) berskala enterprise terakumulasi dari waktu ke waktu, menyebabkan tab browser mengalami crash (*OOM - Out of Memory*).
- Penggunaan library pihak ketiga tanpa kontrol kompilasi meningkatkan *Total Blocking Time* (TBT) dan merusak metrik *Core Web Vitals* Google.

### Apa yang Dibangun pada Modul Ini?
Kita tidak menggunakan framework eksternal. Kita membangun:
1. **Sistem State Reaktif Berbasis Signal/Observer:** Menggunakan closure dan native primitives untuk manajemen state berperforma tinggi dengan *fine-grained updates*.
2. **Batch Render Scheduler:** Menggunakan `requestAnimationFrame` dan *DocumentFragment* untuk mengeksekusi mutasi DOM massal tanpa frame dropping (stabil pada 60/120 FPS).
3. **Isolasi Background Thread via Web Worker:** Memisahkan pemrosesan data biner/komputasi analitik dari Main UI Thread.

---

## 5. How (Workflow Detail)

Berikut adalah alur kerja rekayasa frontend dari arsitektur data hingga visualisasi piksel pada layar:

```
[ Inisialisasi State ]
        |
        v
[ Mutasi State (Action) ]
        |
        +---> [ Observer / Signal Terpicu ]
                    |
                    v
              [ Batch Scheduler Queue ]
                    |
                    +-- (Kumpul mutasi dalam 1 tick microtask)
                    |
                    v
              [ requestAnimationFrame ]
                    |
                    v
              [ DOM Mutation (Write Phase) ]  <-- Jangan baca layout di sini!
                    |
                    v
              [ Browser: Style Recalc -> Layout -> Paint -> Composite ]
                    |
                    v
              [ Frame Ditampilkan (16.6ms budget untuk 60 FPS) ]
```

### Tahapan Eksekusi:
1. **State Mutation:** User atau WebSocket memicu mutasi state. Mutasi tidak langsung menyentuh DOM.
2. **Notification Dispatch:** Store menyiarkan sinyal perubahan hanya ke subscriber yang terdampak.
3. **Scheduler Queuing:** Semua mutasi DOM ditampung ke dalam array `renderQueue`.
4. **Frame Synchronization:** Di dalam callback `requestAnimationFrame`, browser memisahkan fase **Read** (pengukuran) dan **Write** (modifikasi DOM) untuk mencegah *Forced Synchronous Layout*.
5. **Compositor Promotion:** Properti visual yang berubah hanya menggunakan `transform` dan `opacity` untuk dilempar langsung ke GPU thread tanpa memicu Reflow atau Repaint.

---

## 6. Analogy & Diagram ASCII

### Analogi: Dapur Restoran Bintang Lima

Bayangkan browser sebagai sebuah dapur restoran:
- **Call Stack:** Chef utama yang hanya memiliki dua tangan. Dia hanya bisa memasak satu pesanan dalam satu waktu.
- **Microtask Queue:** Pesanan darurat tingkat tinggi (misal: "Garam tumpah di saus! Perbaiki sekarang sebelum disajikan!"). Chef harus menyelesaikan SEMUA pesanan darurat ini sebelum melangkah ke pesanan reguler berikutnya.
- **Macrotask Queue:** Pesanan makanan masuk dari pelayan (Tiket baru via `setTimeout` atau event klik pelanggan). Chef hanya mengambil SATU tiket per sesi.
- **Render Phase (60 FPS Clock):** Pelayan inspektur yang datang setiap 16.6 milidetik untuk mengambil piring yang sudah siap ke meja tamu. Jika Chef sibuk dengan task komputasi JavaScript yang panjang (Call Stack blocking), inspektur harus menunggu, piring terlambat disajikan, dan restoran mengalami *lag/stutter* (Jank).

```
+-----------------------------------------------------------------------+
|                    THE EVENT LOOP ASSEMBLY LINE                       |
+-----------------------------------------------------------------------+
  
   [ Incoming Tasks ] 
   (Click, Timeout, Network)
            |
            v
     +--------------+
     |  MACROTASK   | ---> [ Task 1 ]  (Ambil TEPAT SATU)
     |    QUEUE     |      [ Task 2 ]
     +--------------+             |
                                  v
                       +--------------------+
                       |     CALL STACK     | <=== JS Engine mengeksekusi
                       |   (Main Thread)    |      hingga kosong total
                       +--------------------+
                                  |
                                  v
     +--------------+  [ Drain completely! ]
     |  MICROTASK   | <--------------------+
     |    QUEUE     | ---> [ Microtask 1 ] | Loop sampai
     | (Promises)   |      [ Microtask 2 ] | antrean kosong
     +--------------+      [ Microtask 3 ]-+
                                  |
                                  v
                       +--------------------+
                       | requestAnimation   | <=== Eksekusi sebelum
                       | Frame (rAF) Queue  |      perhitungan visual
                       +--------------------+
                                  |
                                  v
                       +--------------------+
                       |   RENDER PIPELINE  |
                       | Style->Layout->    | ===> Output ke Monitor!
                       | Paint->Composite   |
                       +--------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Layout Thrashing vs Batched DOM Operations

#### Buruk (Layout Thrashing - Forced Synchronous Layout):
```typescript
// BUKAN STANDAR ENTERPRISE: Menyebabkan browser reflow berulang-ulang dalam satu frame
function resizeElementsBad(elements: HTMLElement[]): void {
  for (let i = 0; i < elements.length; i++) {
    // READ (Memaksa browser menghitung layout saat itu juga)
    const currentWidth = elements[i].offsetWidth; 
    // WRITE (Membatalkan layout yang baru saja dihitung)
    elements[i].style.width = `${currentWidth + 10}px`; 
  }
}
```

#### Benar (Separation of Reads and Writes):
```typescript
// STANDAR ENTERPRISE: Batching Read lalu Batching Write
function resizeElementsOptimized(elements: HTMLElement[]): void {
  // Fase 1: Kumpulkan semua hasil pembacaan (READ)
  const widths = elements.map((el) => el.offsetWidth);

  // Fase 2: Jadwalkan semua penulisan pada frame berikutnya (WRITE)
  requestAnimationFrame(() => {
    elements.forEach((el, index) => {
      el.style.width = `${widths[index] + 10}px`;
    });
  });
}
```

---

### Practical Example: Production-Ready Reactive Store & DOM Engine

Struktur modular murni tanpa dependensi eksternal, mengimplementasikan reactive primitive dan atomic rendering queue.

#### File: `core/reactive-store.ts`
```typescript
export type Listener<T> = (newValue: T, oldValue: T) => void;
export type Unsubscribe = () => void;

export class Signal<T> {
  private value: T;
  private listeners: Set<Listener<T>> = new Set();

  constructor(initialValue: T) {
    this.value = initialValue;
  }

  public get(): T {
    return this.value;
  }

  public set(newValue: T): void {
    if (Object.is(this.value, newValue)) return;
    const oldValue = this.value;
    this.value = newValue;
    this.notify(newValue, oldValue);
  }

  public subscribe(listener: Listener<T>): Unsubscribe {
    this.listeners.add(listener);
    // Jalankan satu kali saat inisialisasi untuk initial render
    listener(this.value, this.value);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(newValue: T, oldValue: T): void {
    // Eksekusi listener di dalam microtask untuk mencegah stack overflow
    // jika terjadi pemanggilan rekursif
    queueMicrotask(() => {
      for (const listener of this.listeners) {
        listener(newValue, oldValue);
      }
    });
  }
}
```

#### File: `core/dom-renderer.ts`
```typescript
type RenderTask = () => void;

export class DOMScheduler {
  private static instance: DOMScheduler;
  private writeTasks: Set<RenderTask> = new Set();
  private isFrameScheduled: boolean = false;

  private constructor() {}

  public static getInstance(): DOMScheduler {
    if (!DOMScheduler.instance) {
      DOMScheduler.instance = new DOMScheduler();
    }
    return DOMScheduler.instance;
  }

  public scheduleWrite(task: RenderTask): void {
    this.writeTasks.add(task);
    this.requestFlush();
  }

  private requestFlush(): void {
    if (this.isFrameScheduled) return;
    this.isFrameScheduled = true;

    requestAnimationFrame((timestamp) => {
      this.flush(timestamp);
    });
  }

  private flush(timestamp: DOMHighResTimeStamp): void {
    const tasks = Array.from(this.writeTasks);
    this.writeTasks.clear();
    this.isFrameScheduled = false;

    // Batasi eksekusi dalam budget frame (16.6ms)
    for (let i = 0; i < tasks.length; i++) {
      tasks[i]();
    }
  }
}
```

#### File: `components/metrics-dashboard.ts`
```typescript
import { Signal } from '../core/reactive-store.js';
import { DOMScheduler } from '../core/dom-renderer.js';

export interface MetricData {
  id: string;
  name: string;
  value: number;
}

export class MetricsDashboardComponent {
  private container: HTMLElement;
  private state: Signal<MetricData[]>;
  private scheduler: DOMScheduler;
  private unsubscribe?: () => void;

  constructor(containerId: string, initialState: MetricData[]) {
    const el = document.getElementById(containerId);
    if (!el) throw new Error(`Container #${containerId} not found`);
    this.container = el;
    this.state = new Signal<MetricData[]>(initialState);
    this.scheduler = DOMScheduler.getInstance();
    this.mount();
  }

  public updateData(newData: MetricData[]): void {
    this.state.set(newData);
  }

  private mount(): void {
    this.unsubscribe = this.state.subscribe((data) => {
      this.scheduler.scheduleWrite(() => {
        this.render(data);
      });
    });
  }

  private render(data: MetricData[]): void {
    // Gunakan DocumentFragment untuk menghindari multi-reflow
    const fragment = document.createDocumentFragment();

    data.forEach((metric) => {
      const row = document.createElement('div');
      row.className = 'metric-row';
      row.id = `metric-${metric.id}`;
      
      const label = document.createElement('span');
      label.className = 'metric-name';
      label.textContent = metric.name;

      const val = document.createElement('span');
      val.className = 'metric-value';
      val.textContent = metric.value.toFixed(2);

      row.appendChild(label);
      row.appendChild(val);
      fragment.appendChild(row);
    });

    // Menghapus elemen lama secara efisien
    this.container.replaceChildren(fragment);
  }

  public destroy(): void {
    if (this.unsubscribe) {
      this.unsubscribe();
    }
    this.container.replaceChildren();
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Financial Trading Terminal Dashboard (Real-time L2 Order Book)
- **Tantangan:** Sistem trading memproses update harga aset kripto dan valuta asing melalui WebSocket berfrekuensi tinggi (500 update/detik).
- **Gejala Masalah Awal:** 
  - UI mengalami pembekuan (*freeze*) total.
  - Interaksi pengguna (mengklik tombol order) memiliki latency > 800ms (*Interaction to Next Paint* buruk).
  - Browser memory heap naik dari 50MB menjadi 1.2GB dalam waktu 15 menit, berujung pada tab crash (`Aw, Snap!`).

### Akar Masalah (Root Causes):
1. **Direct DOM Mutation Per Socket Message:** Setiap kali pesan WebSocket masuk, aplikasi langsung melakukan manipulasi `element.innerText` dan memanggil `element.getBoundingClientRect()` untuk animasi pergerakan harga.
2. **Memory Leaks pada Closure:** Setiap pesan masuk menambahkan event listener anonim pada element baris tabel tanpa pernah dihapus (`removeEventListener`).
3. **Main Thread Starvation:** Pemilahan dan perhitungan selisih (*spread calculation*) 10.000 data dilakukan secara langsung di Main Thread.

### Arsitektur Solusi:
1. **Pemisahan Komputasi (Offscreen Data Processing):**
   - WebSocket dipindahkan ke dalam **Dedicated Web Worker**.
   - Worker memproses ordering, sorting, dan delta calculation.
   - Worker mengirimkan data snapshot ke Main Thread secara dibatasi (*throttled*) setiap 50ms (20 update/detik ke UI, bukan 500/detik).
2. **Zero-Allocation DOM Recycling (Virtual Scrolling / Pool Engine):**
   - Hanya membuat node DOM sebanyak yang terlihat pada viewport (misalnya 30 baris tabel).
   - Menggunakan `transform: translateY()` untuk penempatan posisi elemen agar diproses oleh Compositor Thread (GPU) tanpa memicu Reflow.
3. **Structured Memory Cleanup:**
   - Menghapus event delegation individual; menerapkan Event Delegation tunggal pada kontainer induk (*Root Container*).

```
[ WebSocket Server ] (500 msgs/sec)
        |
        v (Raw TCP/WS packets)
+---------------------------------------------------+
|               DEDICATED WEB WORKER                |
| - Parse JSON Payload                              |
| - Sort 10.000 Bids & Asks                         |
| - Buffer & Delta Compression                      |
| - Throttle interval: 50ms                         |
+---------------------------------------------------+
        |
        v (postMessage with Transferable ArrayBuffer)
+---------------------------------------------------+
|                   MAIN THREAD                     |
| - Receive sanitized 30 visible rows               |
| - Pass to DOMScheduler (requestAnimationFrame)    |
| - Update 30 existing DOM nodes in-place           |
|                                                   |
| Result: Main Thread usage drops: 98% -> 12%       |
| INP: 42ms (Target < 200ms) - Solid 60 FPS         |
+---------------------------------------------------+
```

---

## 9. Trade-offs & Matrix

| Pendekatan / Pola | Keuntungan | Kerugian / Biaya | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **Direct Vanilla DOM Manipulation (Unscheduled)** | - Zero dependency overhead.<br>- Sangat cepat untuk mutasi tunggal. | - Rentan *Layout Thrashing* jika tidak disiplin.<br>- Sangat sulit dirawat pada aplikasi kompleks. | Landing page statis, widget independen kecil. |
| **Custom Batch Scheduler (`rAF` + Signals)** | - Performa optimal (0 layout thrashing).<br>- Kontrol penuh atas render timing.<br>- Tanpa runtime library besar. | - Memerlukan pemahaman native browser yang tinggi bagi tim.<br>- Boilerplate kode manual. | Komponen kritis performa tinggi (Trading dashboard, Data grid, Editor). |
| **Virtual DOM Abstraction (React/similar)** | - Model mental deklaratif yang memudahkan dev.<br>- Ekosistem tooling dan modul sangat luas. | - Memory overhead dari representasi node ganda (JS Object vs Native Node).<br>- Ukuran bundle awal besar (JS parse/compile cost). | Aplikasi enterprise multi-halaman dengan ribuan form/view standar. |
| **Offloading to Web Workers** | - Main Thread bebas 100% dari komputasi berat.<br>- INP & FID terjaga sempurna. | - Biaya serialisasi data via `postMessage` (solusi: `SharedArrayBuffer` / Transferables).<br>- Worker tidak memiliki akses ke DOM. | Pemrosesan citra/video, komputasi grafik, data streaming frekuensi tinggi. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Microtask Starvation Trap
**Masalah:** Menggunakan rekursi `queueMicrotask` atau resolving `Promise` terus-menerus tanpa jeda macrotask.
```typescript
// BERBAHAYA: Main thread akan membeku total! 
// Browser TIDAK AKAN PERNAH mengeksekusi UI render atau event pengguna.
function starveBrowser(): void {
  queueMicrotask(() => {
    starveBrowser();
  });
}
```
**Solusi:** Berikan ruang bagi browser untuk bernapas dengan memecah pekerjaan ke dalam Macrotask via `setTimeout(fn, 0)` atau `scheduler.yield()` (modern browser API).

### 2. Detached DOM Tree Memory Leak
**Masalah:** Elemen HTML telah dihapus dari antarmuka visual (`parentElement.removeChild(el)`), tetapi referensinya masih tersimpan di dalam objek atau array JavaScript. Garbage Collector V8 tidak dapat membebaskan memori tersebut.
```typescript
// MEMORY LEAK!
const cache: HTMLElement[] = [];

function createAndRemoveElement() {
  const el = document.createElement('div');
  el.textContent = "Data sementara";
  document.body.appendChild(el);
  
  cache.push(el); // Referensi tersimpan di heap
  document.body.removeChild(el); // Dihapus dari layout, TAPI TIDAK dari heap!
}
```
**Troubleshooting via DevTools:**
1. Buka Chrome DevTools $\to$ Tab **Memory**.
2. Pilih profil **Heap snapshot** $\to$ Klik **Take snapshot**.
3. Lakukan aksi UI (buka dan tutup modal berkali-kali).
4. Ambil snapshot kedua.
5. Filter dengan kata kunci: `Detached HTMLDivElement`. Jika jumlahnya meningkat secara monoton, Anda memiliki *memory leak*.
6. Pastikan membersihkan array cache atau menggunakan `WeakSet` / `WeakMap`.

---

## 11. Best Practices (Production Checklist)

### Performa & Rendering (CRP)
- [ ] **Zero Forced Reflows:** Jangan membaca properti geometri (`offsetWidth`, `clientHeight`, `scrollTop`, dll.) setelah melakukan manipulasi CSS kelas atau style pada siklus event yang sama.
- [ ] **Composite Layers Activation:** Gunakan properti CSS `transform` dan `opacity` untuk animasi visual. Jangan pernah menganimasikan properti `top`, `left`, `width`, atau `margin`.
- [ ] **CSS `contain` Property:** Terapkan `contain: content;` atau `contain: strict;` pada komponen yang terisolasi secara visual untuk membatasi ruang lingkup Style Recalculation dan Layout engine.

### Keamanan (Defensive Frontend)
- [ ] **Sanitasi DOM Mutlak:** Jangan pernah menyuntikkan data dinamis menggunakan `element.innerHTML = userInput`. Gunakan `textContent`, atau gunakan native API `DOMPurify` / browser `Sanitizer API` jika terpaksa menggunakan HTML markup.
- [ ] **Context-aware Element Creation:** Gunakan `document.createElement` dan atur atribut via properti terstruktur (`img.src = validatedUrl`).

### Pemeliharaan Arsitektur
- [ ] **Lifecycle Cleanup Hooks:** Setiap komponen yang menginisialisasi Event Listener, Interval, atau Signal Subscription **wajib** memiliki metode `destroy()` atau `unmount()` untuk mencabut semua listener.
- [ ] **Strict Typing:** Definisikan skema data yang ketat menggunakan TypeScript interface untuk semua pertukaran payload data antara layer jaringan dan layer render.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah arsitektur frontend modular berkinerja tinggi yang menangani antrean pembaruan data real-time tanpa *layout thrashing*.

### Struktur Folder
Simpan semua file praktikum ini di: `hands-on/m02/`
```
hands-on/m02/
├── index.html
├── styles.css
├── src/
│   ├── store.ts
│   ├── scheduler.ts
│   └── app.ts
└── tsconfig.json
```

### Langkah 1: Buat `tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist"
  },
  "include": ["src/**/*"]
}
```

### Langkah 2: Buat `index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Vanilla Architecture</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>High-Frequency Order Feed</h1>
      <div class="controls">
        <button id="btn-start">Mulai Feed (1000 Event)</button>
        <button id="btn-clear">Bersihkan View</button>
      </div>
      <div id="metrics">FPS: <span id="fps-counter">60</span></div>
    </header>
    <main>
      <div id="order-container" class="order-list"></div>
    </main>
  </div>
  <script type="module" src="./dist/app.js"></script>
</body>
</html>
```

### Langkah 3: Buat `styles.css`
```css
:root {
  --bg-primary: #121212;
  --bg-surface: #1e1e1e;
  --text-primary: #e0e0e0;
  --accent-buy: #00c853;
  --accent-sell: #d50000;
  --font-mono: 'Courier New', Courier, monospace;
}

body {
  margin: 0;
  padding: 1.5rem;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, sans-serif;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #333;
  padding-bottom: 1rem;
}

.controls button {
  background: #333;
  color: #fff;
  border: 1px solid #555;
  padding: 0.5rem 1rem;
  cursor: pointer;
  border-radius: 4px;
}

.controls button:hover {
  background: #444;
}

.order-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-top: 1rem;
  max-height: 70vh;
  overflow-y: auto;
  contain: content; /* Isolasi layout recalculation */
}

.order-row {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem;
  background-color: var(--bg-surface);
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
}

.order-buy { border-left: 4px solid var(--accent-buy); }
.order-sell { border-left: 4px solid var(--accent-sell); }
```

### Langkah 4: Implementasikan `src/store.ts`
```typescript
export interface Order {
  id: string;
  ticker: string;
  price: number;
  amount: number;
  type: 'BUY' | 'SELL';
  timestamp: number;
}

export type StoreListener = (state: Order[]) => void;

export class OrderStore {
  private orders: Order[] = [];
  private listeners: Set<StoreListener> = new Set();

  public subscribe(listener: StoreListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public pushOrders(newOrders: Order[]): void {
    // Pertahankan batas maksimum 50 item terakhir pada memori
    this.orders = [...newOrders, ...this.orders].slice(0, 50);
    this.notify();
  }

  public clear(): void {
    this.orders = [];
    this.notify();
  }

  private notify(): void {
    for (const listener of this.listeners) {
      listener(this.orders);
    }
  }
}
```

### Langkah 5: Implementasikan `src/scheduler.ts`
```typescript
export class FrameScheduler {
  private static pendingTask: (() => void) | null = null;
  private static isScheduled: boolean = false;

  public static schedule(task: () => void): void {
    this.pendingTask = task;
    if (!this.isScheduled) {
      this.isScheduled = true;
      requestAnimationFrame(this.execute);
    }
  }

  private static execute = (_timestamp: DOMHighResTimeStamp): void => {
    FrameScheduler.isScheduled = false;
    if (FrameScheduler.pendingTask) {
      const task = FrameScheduler.pendingTask;
      FrameScheduler.pendingTask = null;
      task();
    }
  };
}
```

### Langkah 6: Implementasikan `src/app.ts`
```typescript
import { Order, OrderStore } from './store.js';
import { FrameScheduler } from './scheduler.js';

class App {
  private store = new OrderStore();
  private container = document.getElementById('order-container') as HTMLDivElement;
  private btnStart = document.getElementById('btn-start') as HTMLButtonElement;
  private btnClear = document.getElementById('btn-clear') as HTMLButtonElement;
  private fpsDisplay = document.getElementById('fps-counter') as HTMLSpanElement;

  private lastFrameTime = performance.now();
  private frameCount = 0;

  constructor() {
    this.initListeners();
    this.startFPSMonitor();
  }

  private initListeners(): void {
    this.store.subscribe((orders) => {
      // Gunakan FrameScheduler untuk mencegah Layout Thrashing
      FrameScheduler.schedule(() => {
        this.renderOrders(orders);
      });
    });

    this.btnStart.addEventListener('click', () => this.simulateHeavyLoad());
    this.btnClear.addEventListener('click', () => this.store.clear());
  }

  private renderOrders(orders: Order[]): void {
    const fragment = document.createDocumentFragment();

    for (let i = 0; i < orders.length; i++) {
      const order = orders[i];
      const row = document.createElement('div');
      row.className = `order-row ${order.type === 'BUY' ? 'order-buy' : 'order-sell'}`;

      const info = document.createElement('span');
      info.textContent = `${order.ticker} - ${order.type} @ ${order.price.toFixed(2)}`;

      const vol = document.createElement('span');
      vol.textContent = `Qty: ${order.amount.toFixed(4)}`;

      row.appendChild(info);
      row.appendChild(vol);
      fragment.appendChild(row);
    }

    this.container.replaceChildren(fragment);
  }

  private simulateHeavyLoad(): void {
    // Simulasi 1000 event masuk dalam batch cepat
    let sent = 0;
    const interval = setInterval(() => {
      if (sent >= 1000) {
        clearInterval(interval);
        return;
      }

      const mockBatch: Order[] = Array.from({ length: 10 }, (_, i) => ({
        id: crypto.randomUUID(),
        ticker: 'BTC/USDT',
        price: 60000 + (Math.random() * 200 - 100),
        amount: Math.random() * 2,
        type: Math.random() > 0.5 ? 'BUY' : 'SELL',
        timestamp: Date.now() + i
      }));

      this.store.pushOrders(mockBatch);
      sent += 10;
    }, 10);
  }

  private startFPSMonitor(): void {
    const calcFPS = (now: DOMHighResTimeStamp) => {
      this.frameCount++;
      const delta = now - this.lastFrameTime;

      if (delta >= 1000) {
        const fps = Math.round((this.frameCount * 1000) / delta);
        this.fpsDisplay.textContent = fps.toString();
        this.frameCount = 0;
        this.lastFrameTime = now;
      }

      requestAnimationFrame(calcFPS);
    };

    requestAnimationFrame(calcFPS);
  }
}

// Inisialisasi Aplikasi
new App();
```

---

## 13. Exercise

### Latihan 1 (Tingkat: Easy) - Menghilangkan Layout Thrashing
Diberikan cuplikan kode yang membaca dan menulis style secara berselang-seling:
```javascript
const boxes = document.querySelectorAll('.box');
boxes.forEach(box => {
  const height = box.clientHeight; // READ
  box.style.height = (height + 5) + 'px'; // WRITE
});
```
*Tugas:* Refactor kode tersebut ke dalam JavaScript modern menggunakan pola Read/Write Separation sehingga browser hanya memicu tepat **satu** kali proses reflow layout!

### Latihan 2 (Tingkat: Medium) - Async Event Queue Dispatcher
Buatlah sebuah class TypeScript bernama `AsyncQueue<T>` yang mengimplementasikan antrean pesan berbasis microtask. 
*Ketentuan:*
- Method `enqueue(item: T): void` memasukkan data ke buffer internal.
- Buffer harus dieksekusi secara otomatis dan dikirim secara berkala menggunakan `queueMicrotask`.
- Tidak boleh mengeksekusi worker callback lebih dari 1 kali dalam tick microtask yang sama (harus digabung/batched).

### Latihan 3 (Tingkat: Hard) - DOM Node Recycler (Zero-Allocation Scroller)
Buatlah sebuah *Virtual List Scroller Engine* sederhana tanpa library.
*Ketentuan:*
- Mampu menampilkan 100.000 item data string array.
- Hanya membuat maksimal 20 elemen `<div>` di dalam DOM tree sepanjang waktu.
- Gunakan listener `scroll` dengan kalkulasi `scrollTop` untuk mengubah data `textContent` dan properti CSS `transform: translateY(...)` dari 20 elemen yang ada secara dinamis sesuai pergerakan viewport scrollbar.

---

## 14. Challenge

### Studi Kasus: "The Fault-Tolerant Multi-Tab Collaborative State Engine"

#### Deskripsi Masalah:
Perusahaan Anda sedang membangun aplikasi enterprise perbankan internal di mana seorang teller dapat membuka beberapa tab browser secara bersamaan (Multi-tab Workflow). Masalah muncul saat Teller melakukan pembaruan saldo nasabah di Tab A, namun Tab B dan Tab C masih menampilkan saldo lama (stale data). Jika teller di Tab B melakukan transaksi penarikan, terjadi tabrakan transaksi (*race condition*) dan inkonsistensi data serius.

#### Persyaratan Teknis Tantangan:
1. **Zero-Backend Dependency Synchronization:** Sinkronisasi state lokal antar tab harus terjadi secara peer-to-peer di sisi client browser secara instan (< 50ms) tanpa bergantung pada polling HTTP atau WebSocket server tambahan.
2. **Tab Leader Election Mechanism:** Implementasikan algoritma *Leader Election* sederhana menggunakan Native Web APIs (`BroadcastChannel`, `localStorage`, atau `Web Locks API`). Tepat satu tab browser harus menjadi **LEADER**, dan tab lainnya bertindak sebagai **FOLLOWER**.
3. **Resilience & Failover:** Jika tab LEADER ditutup secara mendadak oleh teller, salah satu tab FOLLOWER harus mengambil alih status LEADER dalam waktu kurang dari 200 milidetik tanpa kehilangan riwayat mutasi state terakhir.
4. **Main Thread Safety:** Mekanisme audit logging dari pergerakan state tersebut harus disimpan ke dalam `IndexedDB` menggunakan thread terpisah (Web Worker) agar antarmuka teller tidak pernah mengalami stuttering (harus selalu 60 FPS).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa pemanggilan `element.offsetHeight` tepat setelah mengubah `element.style.width` menyebabkan performa menurun?**
   - A. Karena memicu Garbage Collection seketika.
   - B. Karena memicu Forced Synchronous Layout (Reflow paksa).
   - C. Karena JavaScript engine berpindah ke background thread.
   - D. Karena browser mematikan GPU acceleration.
   *Jawaban:* **B**. Browser terpaksa menghentikan eksekusi JavaScript untuk menghitung ulang geometri layout secara instan agar dapat mengembalikan nilai numerik yang akurat.

2. **Kapan tepatnya browser mengeksekusi antrean Microtask?**
   - A. Sebelum mengeksekusi script sinkronus pada Call Stack.
   - B. Segera setelah Call Stack kosong, sebelum tugas Macrotask berikutnya dan sebelum Render cycle berikutnya.
   - C. Tepat setelah event `requestAnimationFrame` selesai diproses.
   - D. Hanya ketika sistem operasi dalam status idle.
   *Jawaban:* **B**. Microtask queue dikuras hingga benar-benar kosong segera setelah stack eksekusi kosong.

3. **Manakah dari properti CSS berikut yang perubahannya diproses murni oleh GPU thread tanpa memicu Layout atau Paint?**
   - A. `width` dan `height`
   - B. `top` dan `margin-left`
   - C. `transform` dan `opacity`
   - D. `display` dan `visibility`
   *Jawaban:* **C**. Properti tersebut hanya memicu tahapan Compositing pada GPU.

4. **Apa fungsi utama dari `DocumentFragment` dalam manipulasi DOM native?**
   - A. Menyimpan DOM langsung ke dalam local cache storage.
   - B. Menjadi wadah DOM di luar memori dokumen utama yang memungkinkan penambahan multi-node tanpa memicu reflow parsial berulang.
   - C. Mengonversi HTML string menjadi format biner WebAssembly.
   - D. Mengisolasi CSS context agar tidak bocor ke elemen global.
   *Jawaban:* **B**. Perubahan yang dilakukan pada DocumentFragment tidak memicu reflow hingga fragment tersebut dimasukkan ke dalam DOM aktif.

5. **Apa yang terjadi jika kita mendaftarkan event listener pada sebuah elemen DOM, kemudian menghapus elemen tersebut dari layar tanpa memanggil `removeEventListener`?**
   - A. Event listener otomatis dihapus dan memori langsung bebas 100%.
   - B. Browser akan menampilkan runtime exception error.
   - C. Berpotensi terjadi memory leak jika closure listener masih memiliki referensi terhadap objek atau scope global.
   - D. Browser otomatis me-refresh halaman web.
   *Jawaban:* **C**. Objek elemen yang terlepas (*detached node*) dapat tertahan di memori V8 jika masih direferensikan oleh listener.

---

### Bagian 2: Intermediate (5 Pertanyaan)
1. **Diberikan urutan kode berikut:**
   ```javascript
   console.log('1');
   setTimeout(() => console.log('2'), 0);
   Promise.resolve().then(() => console.log('3'));
   requestAnimationFrame(() => console.log('4'));
   console.log('5');
   ```
   **Berdasarkan spesifikasi HTML Event Loop, apakah output konsol yang paling umum?**
   - A. 1, 5, 2, 3, 4
   - B. 1, 5, 3, 4, 2
   - C. 1, 2, 3, 4, 5
   - D. 1, 5, 4, 3, 2
   *Jawaban:* **B**. '1' dan '5' (Sync), lalu '3' (Microtask queue dikuras), lalu '4' (rAF callback sebelum repaint berikutnya), lalu '2' (Macrotask timer).

2. **Bagaimana cara kerja mekanisme Garbage Collection "Generational Hypothesis" pada JavaScript Engine (V8)?**
   - A. Semua objek disimpan dalam satu array linear tunggal sampai memori penuh.
   - B. Asumsi bahwa sebagian besar objek memiliki siklus hidup yang sangat singkat; memori dibagi menjadi *Young Generation* (sering dibersihkan dengan cepat) dan *Old Generation* (jarang dibersihkan).
   - C. Garbage collection hanya berjalan saat aplikasi ditutup oleh user.
   - D. Setiap variabel diberikan identifier waktu statis oleh compiler sebelum eksekusi.
   *Jawaban:* **B**. Sebagian besar objek mati sesaat setelah dialokasikan (Young Gen Scavenge), objek yang bertahan dipromosikan ke Old Space.

3. **Mengapa penggunaan Web Worker tidak dapat sepenuhnya menggantikan UI Virtual DOM Scheduler?**
   - A. Karena Web Worker berjalan lebih lambat daripada Main Thread.
   - B. Karena Web Worker tidak memiliki akses langsung ke objek `window`, `document`, dan DOM nodes.
   - C. Karena Web Worker tidak mendukung fitur asynchronous.
   - D. Karena transfer data ke Web Worker mematikan thread JavaScript utama.
   *Jawaban:* **B**. Worker berjalan di thread terisolasi (`WorkerGlobalScope`) dan tidak memiliki akses ke DOM API langsung.

4. **Apa perbedaan mendasar antara `window.requestAnimationFrame` dan `window.requestIdleCallback`?**
   - A. `rAF` dieksekusi tepat sebelum sinkronisasi repaint layar berikutnya (60Hz/120Hz), sedangkan `rIC` dieksekusi saat browser berada dalam periode frame idle tanpa beban kerja kritikal.
   - B. `rAF` adalah API usang, `rIC` adalah pengganti resminya.
   - C. `rAF` berjalan di Web Worker, `rIC` di Main Thread.
   - D. `rIC` memiliki prioritas lebih tinggi daripada antrean Microtask.
   *Jawaban:* **A**. `rAF` ditargetkan untuk visualisasi frame-rate locking, sedangkan `rIC` digunakan untuk tugas berprioritas rendah (misalnya analitik).

5. **Apa peran dari CSS property `will-change: transform` pada browser modern?**
   - A. Memaksa browser engine menghapus elemen dari memori cache.
   - B. Menginstruksikan browser sejak awal untuk mempromosikan elemen tersebut ke layer GPU terpisah (*Composited Layer*) guna menghindari render kompilasi mendadak.
   - C. Menghapus properti responsif pada CSS media query.
   - D. Mencegah user mengklik elemen tersebut saat animasi berlangsung.
   *Jawaban:* **B**. Ini adalah petunjuk bagi rendering engine untuk mengalokasikan sumber daya grafis GPU sebelum animasi terjadi.

---

### Bagian 3: Production Scenarios (3 Skenario Kasus)

#### Skenario 1
Sebuah platform analitik media sosial memuat ribuan tweet/post ke dalam satu timeline panjang. Pengguna melaporkan bahwa setelah melakukan scroll ke bawah selama 5 menit, browser menjadi sangat patah-patah (*stuttering*), dan akhirnya tab browser mengalami crash otomatis dengan kode kesalahan `Out of Memory`. 
**Langkah debugging teknis sistematis apa yang harus Anda lakukan dan tindakan arsitektural apa yang wajib diambil?**
*Solusi Analisis Enterprise:*
1. **Diagnosis:** Lakukan alokasi heap profiling melalui DevTools Memory Tab. Rekam interaksi scroll dan bandingkan Snapshot 1 (awal) dengan Snapshot N (setelah 5 menit). Amati pertumbuhan alokasi native DOM objects dan closure listeners.
2. **Akar Masalah:** Penumpukan node DOM yang tidak terbatas di dokumen aktif (*DOM bloat*). Setiap tweet menambahkan rata-rata 30-50 elemen DOM baru tanpa pernah mendestruksi elemen yang sudah keluar dari viewport atas.
3. **Solusi Arsitektur:** Terapkan **DOM Virtualization (Windowing)**. Hanya render elemen yang masuk dalam area viewport fisik ditambah buffer margin kecil (misalnya 10 item atas, 10 item bawah). Daftarkan satu delegated listener pada container alih-alih pada setiap tweet card individual.

#### Skenario 2
Sebuah dashboard perbankan menggunakan timer `setInterval(fetchRates, 1000)` untuk menarik data kurs valas. Ketika tab dashboard tersebut diminimalkan (*minimized*) atau berpindah ke tab background lain selama 1 jam, lalu dibuka kembali oleh staf, browser langsung mengalami freeze selama beberapa detik dengan lonjakan aktivitas prosesor drastis.
**Jelaskan secara arsitektural mengapa freeze tersebut terjadi pada browser modern dan bagaimana cara mengatasinya secara elegan!**
*Solusi Analisis Enterprise:*
1. **Akar Masalah:** Browser modern menerapkan *timer throttling* pada background tab (interval ditunda dan ditumpuk/dikonsolidasikan untuk menghemat baterai/CPU). Selain itu, callback network response yang kembali mungkin telah menumpuk eksekusi DOM Write yang belum sempat dijalankan karena browser menahan paint cycle saat backgrounded. Saat tab diaktifkan kembali (*tab focus*), semua task yang tertahan dieksekusi secara serentak di Main Thread, menyebabkan antrean rendering tersumbat.
2. **Solusi Arsitektur:** Gunakan **Page Visibility API** (`document.addEventListener('visibilitychange', ...)`). Ketika `document.hidden === true`, nonaktifkan polling interval atau batalkan koneksi sementara. Saat tab kembali visible (`document.hidden === false`), lakukan single fresh fetch untuk re-sinkronisasi state terkini.

#### Skenario 3
Sistem checkout e-commerce memiliki form multi-step yang kompleks. Terjadi anomali di mana data input kartu kredit pengguna terkadang hilang saat berpindah step, dan metrik INP (*Interaction to Next Paint*) tercatat sangat buruk (780ms) setiap kali tombol "Lanjut ke Pembayaran" ditekan.
**Setelah diinspeksi, tombol tersebut menjalankan validasi input, kalkulasi diskon kupon, enkripsi data, dan mutasi kelas visual error secara bersamaan di thread utama. Bagaimana Anda menyusun ulang eksekusi kode ini?**
*Solusi Analisis Enterprise:*
1. **Dekomposisi Pipeline:** Pisahkan pekerjaan menjadi: (a) Immediate visual feedback, (b) Non-blocking computational validation/encryption, (c) Asynchronous submission.
2. **Eksekusi:**
   - **Step 1 (UI Feedback):** Pada event klik, segera ubah state tombol menjadi loading (`disabled = true`, tampilkan spinner) di dalam `requestAnimationFrame` untuk memastikan frame feedback ter-render dalam budget 16ms (menekan INP < 50ms).
   - **Step 2 (Offload Heavy Tasks):** Delegasikan kalkulasi diskon kompleks dan proses enkripsi kriptografi ke **Web Worker** menggunakan native `crypto.subtle` API.
   - **Step 3 (Reconciliation):** Worker mengembalikan payload terenkripsi ke Main Thread via `postMessage`. Main thread kemudian mengeksekusi transisi langkah checkout berikutnya.

---

## 16. Summary

1. **Abstraksi Berakar pada Core:** Framework frontend datang dan pergi, namun pemahaman mendalam tentang Web APIs, Rendering Engine (Blink), dan JavaScript Engine (V8) adalah fondasi fundamental yang membedakan junior developer dari principal frontend engineer.
2. **Critical Rendering Path Adalah Kunci Efisiensi:** Reflow (Layout) adalah operasi yang sangat mahal secara komputasi. Disiplin dalam memisahkan fase pembacaan (*Read*) dan penulisan (*Write*) DOM menggunakan atomic schedulers (`requestAnimationFrame`) adalah keharusan pada aplikasi berperforma tinggi.
3. **Event Loop Menentukan Responsivitas:** Pahami batasan Call Stack, Microtasks, dan Macrotasks. Microtask starvation dapat membekukan aplikasi sama fatalnya dengan infinite loop. Selalu berikan ruang bernapas bagi rendering pipeline untuk menjaga stabilitas visual 60/120 FPS.
4. **Isolasi Beban Kerja (Multi-threading di Browser):** Manfaatkan Web Workers untuk membebaskan Main Thread dari komputasi berat, manipulasi data biner, dan parsing dataset besar, sehingga metrik Core Web Vitals (*khususnya Interaction to Next Paint - INP*) tetap berada pada batas performa kelas enterprise.