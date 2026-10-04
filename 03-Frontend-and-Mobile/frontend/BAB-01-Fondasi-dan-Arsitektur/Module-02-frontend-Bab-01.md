# BAB 01: Fondasi dan Arsitektur
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
1. **Menganalisis dan Mengoptimasi Critical Rendering Path (CRP):** Menjelaskan siklus hidup rendering peramban (*parse*, *style*, *layout*, *paint*, *composite*) dan mengeliminasi *layout thrashing* secara terukur menggunakan profiling tools.
2. **Mengaudit dan Mencegah Memory Leak pada V8 Engine:** Mengidentifikasi alokasi memori pada *Heap*, menganalisis *Detached DOM Nodes*, serta mengimplementasikan siklus pembersihan referensi secara presisi pada arsitektur Single Page Application (SPA).
3. **Merancang dan Mengimplementasikan Arsitektur Micro-Frontend:** Membangun infrastruktur Micro-Frontend berbasis *Webpack Module Federation* atau *Vite Dynamic Remotes* dengan isolasi runtime, *shared dependencies*, dan *cross-application event-bus* nir-konflik.
4. **Menerapkan Pola State Management Lanjutan:** Mengonstruksi arsitektur *unidirectional data flow* dan *fine-grained reactivity* menggunakan Proxy-based patterns untuk meminimalkan *unnecessary re-renders*.
5. **Mengimplementasikan Resilient Network & Caching Strategy:** Mengembangkan strategi offline-first menggunakan Service Worker, Cache API, dan protokol HTTP/2-HTTP/3 multiplexing untuk menekan First Contentful Paint (FCP) dan Largest Contentful Paint (LCP) ke standar p99 < 1.2 detik.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Arsitektur JavaScript Runtime:** Event Loop (Microtask vs Macrotask), Call Stack, Lexical Scope, dan Closures.
- **Modern ECMAScript (ES2022+):** Modules (`import`/`export`), Symbols, WeakMap/WeakSet, Proxies, Promises, Async/Await.
- **Dasar Web APIs:** DOM Tree manipulation, Web Workers, Fetch API, AbortController.
- **Tooling Ekosistem:** Node.js (v18+), paket manager (pnpm/npm), dan konsep dasar *AST (Abstract Syntax Tree)* pada bundling (Rollup/Webpack/Vite).

---

### 3. Concept & Internal Architecture

Arsitektur frontend modern skala enterprise menuntut pemahaman mendalam tentang bagaimana kode dieksekusi oleh mesin peramban (*browser engine*) pada level sistem level rendah (*low-level system*).

#### 3.1. Browser Internals & Critical Rendering Path (CRP)

Peramban modern (Chromium/Blink, Gecko, WebKit) memisahkan eksekusi ke dalam beberapa thread:
- **Browser Thread:** Mengelola address bar, bookmarks, navigasi jaringan.
- **Renderer Thread:** Menjalankan parsing HTML/CSS, eksekusi JavaScript, dan penghitungan kalkulasi layout visual.
- **Compositor Thread & Raster Thread:** Memecah layer visual menjadi tiles dan menggambarnya ke GPU.

```
+-----------------------------------------------------------------------------------+
| RENDERER THREAD                                                                   |
|                                                                                   |
|  [HTML] ---> (HTML Parser) --------> [DOM Tree]                                   |
|                                          |                                        |
|  [CSS]  ---> (CSS Parser)  --------> [CSSOM Tree]                                 |
|                                          |                                        |
|                                          v                                        |
|                                   [Render Tree]                                   |
|                                          |                                        |
|                                          v                                        |
|                                   [Layout/Reflow]                                 |
|                         (Kalkulasi Box Model Geometri: X, Y, W, H)                |
|                                          |                                        |
|                                          v                                        |
|                                   [Paint/Repaint]                                 |
|                         (Rasterisasi Warna, Border, Bayangan)                     |
+------------------------------------------|----------------------------------------+
                                           v
+-----------------------------------------------------------------------------------+
| COMPOSITOR THREAD & GPU                                                           |
|                                                                                   |
|                            [Composite Layers]                                     |
|                   (Transformasi 3D, Opacity, GPU Blitting)                        |
+-----------------------------------------------------------------------------------+
```

##### Pipeline Render:
1. **DOM Construction:** Raw bytes $\rightarrow$ Characters $\rightarrow$ Tokens $\rightarrow$ Nodes $\rightarrow$ DOM Tree.
2. **CSSOM Construction:** CSS bersifat *render-blocking*. Peramban menghentikan rendering sampai seluruh CSS diunduh dan pohon CSSOM selesai dikonstruksi.
3. **Render Tree:** Menggabungkan DOM dan CSSOM. Elemen dengan `display: none` diabaikan sepenuhnya dari Render Tree, sedangkan elemen dengan `visibility: hidden` tetap masuk karena masih memakan ruang geometris.
4. **Layout (Reflow):** Menghitung dimensi fisik dan posisi absolut setiap simpul pada viewport. Operasi ini computationally expensive ($\mathcal{O}(N)$ atau $\mathcal{O}(N \log N)$ terhadap ukuran sub-tree).
5. **Paint:** Mengonversi elemen visual menjadi piksel-piksel pada layar.
6. **Compositing:** Menyerahkan layer-layer independen ke GPU. Properti seperti `transform` dan `opacity` dieksekusi langsung pada Compositor Thread tanpa memicu Reflow atau Repaint ulang.

#### 3.2. V8 Memory Management: Generational Garbage Collector

Eksekusi JavaScript pada Chromium digerakkan oleh V8 Engine. Memori dialokasikan pada dua area utama: **Stack** (data primitif, stack frame) dan **Heap** (objek, closure, fungsi).

```
+-----------------------------------------------------------------------------------+
| V8 HEAP MEMORY                                                                    |
|                                                                                   |
|  +-------------------------------------+  +------------------------------------+  |
|  | NEW SPACE (Nursery + Intermediate)  |  | OLD SPACE (Tenured Objects)        |  |
|  | - Dialokasikan untuk objek baru     |  | - Objek yang bertahan dari >2 GC   |  |
|  | - Minor GC (Scavenger: Cheney's Alg)|  | - Major GC (Mark-Sweep-Compact)   |  |
|  | - Sangat cepat, ukuran kecil (1-8MB)|  | - Full GC, stop-the-world pauses   |  |
|  +-------------------------------------+  +------------------------------------+  |
|                                                                                   |
|  +-------------------------------------+  +------------------------------------+  |
|  | LARGE OBJECT SPACE                  |  | CODE SPACE                         |  |
|  | - Alokasi objek melebihi limit New  |  | - JIT-compiled machine code        |  |
|  +-------------------------------------+  +------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

- **Minor GC (Scavenger):** Menggunakan algoritma Cheney. Membagi New Space menjadi *From-Space* dan *To-Space*. Mengosongkan memori yang tidak memiliki referensi secara instan melalui pemindahan pointer aktif.
- **Major GC (Mark-Sweep-Compact):** Dijalankan saat Old Space penuh. 
  - *Marking:* Traversal objek dari root.
  - *Sweeping:* Mengosongkan slot memori objek tak bertuan.
  - *Compacting:* Menggeser memori aktif untuk mengatasi fragmentasi memori.

**Akar Masalah Detached DOM Tree:** Objek DOM yang telah dihapus dari antarmuka visual (`element.remove()`), namun masih direferensikan oleh variabel global, closure, atau event listener pada JavaScript Heap. Peramban tidak dapat menghapus node ini dari memori, menyebabkan akumulasi kebocoran RAM sistem.

#### 3.3. Arsitektur Rendering: Perbandingan Paradigma

| Parameter | CSR (Client-Side Rendering) | SSR (Server-Side Rendering) | Island Architecture | Resumability (Qwik-style) |
| :--- | :--- | :--- | :--- | :--- |
| **TTFB (Time to First Byte)** | Cepat (Static CDN) | Menengah-Lambat (Compute server) | Menengah | Menengah |
| **FCP (First Contentful Paint)** | Lambat | Sangat Cepat | Sangat Cepat | Sangat Cepat |
| **TTI (Time to Interactive)** | Lambat (JS bundle besar) | Lambat (*Hydration bottleneck*) | Cepat (*Partial hydration*) | Instan (Nir-hidrasi) |
| **Hydration Cost** | Komprehensif di client | Komprehensif di client | Terisolasi per-pulau interaktif | Nol (Lazy executed via serialised HTML) |
| **Beban Infrastruktur** | Rendah (Object Storage) | Tinggi (Node.js/Edge servers) | Sedang | Sedang |

---

### 4. Why & What

#### Mengapa Monolitik Frontend Gagal di Skala Enterprise?
1. **Deployment Coupling:** Perubahan 1 baris kode pada modul *Checkout* mengharuskan kompilasi dan regresi pada modul *Catalog*, *Auth*, dan *Billing*.
2. **Build Time Bloat:** AST parsing puluhan ribu file TypeScript menghasilkan pipeline CI/CD berdurasi puluhan menit hingga hitungan jam.
3. **Dependency Drift & Version Lock-in:** Seluruh domain dipaksa menggunakan versi framework yang identik, menghambat migrasi inkremental.
4. **Runtime Blast Radius:** Error runtime unhandled pada widget pihak ketiga dapat mematikan seluruh alur eksekusi single-page container.

#### Apa Solusinya?
Adopsi **Micro-Frontend Architecture** berbasis **Runtime Module Federation** dipadukan dengan **Isolasi Domain**. 
- Memungkinkan aplikasi frontend dipecah menjadi unit-unit deployable independen (*Remotes*) yang dirakit secara on-demand oleh aplikasi induk (*Host/Shell*).
- Setiap remote mengisolasi dependensi, alur deployment, dan siklus hidup kompilasi, namun tetap memberikan user experience SPA terpadu tanpa *hard-reload*.

---

### 5. How (Workflow Detail)

Berikut adalah alur orkestrasi runtime produksi untuk arsitektur Micro-Frontend berbasis dynamic injection:

```
[User Browser]
      |
      | (1) Request URL https://app.enterprise.io/
      v
[Host Application (Shell)]
      |
      |-- (2) Fetch remote-manifest.json (Service Discovery)
      |-- (3) Resolve URL Remote Micro-Apps (CDN edge)
      |
      +------> [Remote A: Billing (v1.2.0)]
      |              |-- Unduh remoteEntry.js
      |              \-- Inisialisasi Shared Scope (React, Lib-Core)
      |
      +------> [Remote B: Analytics (v2.0.4)]
                     |-- Unduh remoteEntry.js
                     \-- Validasi Host Sandbox (Shadow DOM / Scoped CSS)
```

1. **Host Bootstrapping:** Peramban memuat file HTML dasar Host Shell.
2. **Manifest Discovery:** Host mengambil metadata `remote-manifest.json` dari API Gateway/CDN yang memetakan versi aplikasi mikro dengan URL target.
3. **Shared Scope Negotiation:** Container Host dan Remote melakukan perbandingan semantik versi (*semver*). Jika Host menyediakan `react@18.2.0` dan Remote membutuhkan `react@^18.0.0`, Remote akan menggunakan instance React milik Host (mencegah duplikasi runtime di memori).
4. **Runtime Mounting:** Modul remote dimuat secara asinkronus ke DOM mount point dengan penanganan fallback isolasi error boundary.

---

### 6. Analogy & Diagram ASCII

#### Analogi Komposisi Kapal Induk (*Aircraft Carrier Fleet*)
Bayangkan arsitektur Micro-Frontend sebagai armada kapal perang:
- **Host Application:** Adalah *Kapal Induk (Shell)*. Menyediakan dek landasan pacu, navigasi terpusat, sistem radar, dan pasokan bahan bakar bersama (*Shared Core Dependencies, Global Auth, Event Bus*).
- **Remote Applications:** Adalah *Pesawat Tempur (Squadrons)*. Memiliki spesialisasi misi sendiri (*Billing, Analytics, Inventory*). Dapat lepas landas, diganti dengan model baru, atau masuk hanggar tanpa perlu menenggelamkan atau memodifikasi lambung kapal induk.
- **Detached DOM Memory Leak:** Ibarat pesawat tempur yang telah mendarat dan dibongkar dari dek, namun tali pengikat bahan bakarnya (*dangling event listener/closure*) tidak pernah dilepas. Menumpuk bahan bakar bocor di dek sampai kapal kehilangan daya apung dan tenggelam (*out-of-memory crash*).

#### Diagram Arsitektur Host-Remote Module Federation

```
+-----------------------------------------------------------------------------------+
| CONTAINER HOST RUNTIME (Shell Application)                                        |
|                                                                                   |
|  +------------------------+  +------------------------+  +---------------------+  |
|  | Global Identity Context|  | Enterprise Event Bus   |  | Shared Dependencies |  |
|  | (Auth, RBAC Tokens)    |  | (Publish/Subscribe)    |  | (React, Axios, UI)  |  |
|  +-----------+------------+  +-----------+------------+  +----------+----------+  |
|              |                           |                          |             |
|              +-------------------+-------+                          |             |
|                                  |                                  |             |
|     +----------------------------v----------------------------------v-------+     |
|     | Dynamic Module Loader (Runtime Script Injection + Sandbox Fallback)   |     |
|     +----------------------------+------------------------------------------+     |
+----------------------------------|------------------------------------------------+
                                   |
            +----------------------+----------------------+
            |                                             |
            v                                             v
+-----------------------+                     +-----------------------+
| REMOTE A: BILLING     |                     | REMOTE B: INVENTORY   |
| (Webpack Federated)   |                     | (Vite Module Runner)  |
|                       |                     |                       |
| - Exposed: ./Widget   |                     | - Exposed: ./Grid     |
| - Uses Shared Scope   |                     | - Uses Shared Scope   |
| - CSS: Scoped Modules |                     | - CSS: Shadow DOM     |
+-----------------------+                     +-----------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengeliminasi Layout Thrashing (CRP Optimization)

*Layout Thrashing* terjadi ketika JavaScript membaca dan menulis geometri DOM secara bergantian di dalam perulangan loop, memaksa browser melakukan *Synchronous Reflow* berulang kali.

```typescript
// BAD: Menyebabkan N kali Reflow (Layout Thrashing)
function resizeElementsBad(elements: HTMLElement[]): void {
  for (let i = 0; i < elements.length; i++) {
    // READ (Memaksa layout engine mengalkulasi ulang posisi instan)
    const currentWidth = elements[i].offsetWidth; 
    // WRITE (Membuat geometri DOM invalid)
    elements[i].style.width = `${currentWidth + 10}px`; 
  }
}

// GOOD: Batching Operasi Read dan Write (Optimized CRP)
function resizeElementsGood(elements: HTMLElement[]): void {
  // Phase 1: BATCH READ (Semua pembacaan dieksekusi dalam satu layout cycle)
  const widths = elements.map(el => el.offsetWidth);

  // Phase 2: BATCH WRITE (Semua mutasi di-schedule menggunakan rAF untuk Frame berikutnya)
  window.requestAnimationFrame(() => {
    elements.forEach((el, index) => {
      el.style.width = `${widths[index] + 10}px`;
    });
  });
}
```

#### Practical Example: Enterprise Cross-Application Event-Bus dengan Lifecycle Guard

Implementasi event-bus nir-dependensi berdaya tahan tinggi antar Micro-Frontend dengan pencegahan kebocoran memori berbasis `WeakRef` dan validasi tipe ketat.

```typescript
/**
 * Event-Bus Micro-Frontend Enterprise
 * Menggunakan WeakRef untuk mencegah Detached Memory Leak
 */

export interface EventPayloadMap {
  'AUTH_SESSION_EXPIRED': { timestamp: number; reason: string };
  'ORDER_CREATED': { orderId: string; amount: number; currency: string };
  'GLOBAL_NOTIFY': { level: 'INFO' | 'WARN' | 'ERROR'; message: string };
}

export type EventCallback<T> = (data: T) => void;

class EnterpriseEventBus {
  private static instance: EnterpriseEventBus;
  // Menyimpan listener menggunakan WeakRef container untuk mencegah memory leaks
  private listeners: Map<
    keyof EventPayloadMap,
    Set<{ callbackRef: (data: unknown) => void; owner: WeakRef<object> }>
  > = new Map();

  private constructor() {}

  public static getInstance(): EnterpriseEventBus {
    if (!EnterpriseEventBus.instance) {
      EnterpriseEventBus.instance = new EnterpriseEventBus();
    }
    return EnterpriseEventBus.instance;
  }

  /**
   * Subscribe ke event bus dengan mengikat lifecycle listener ke objek pemilik (Owner)
   */
  public subscribe<K extends keyof EventPayloadMap>(
    event: K,
    callback: EventCallback<EventPayloadMap[K]>,
    owner: object
  ): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }

    const listenerSet = this.listeners.get(event)!;
    const subscriptionRecord = {
      callbackRef: callback as (data: unknown) => void,
      owner: new WeakRef(owner)
    };

    listenerSet.add(subscriptionRecord);

    // Unsubscribe function (Idempotent cleanup)
    return () => {
      listenerSet.delete(subscriptionRecord);
      if (listenerSet.size === 0) {
        this.listeners.delete(event);
      }
    };
  }

  /**
   * Publish event ke seluruh Remote yang sedang aktif
   */
  public publish<K extends keyof EventPayloadMap>(
    event: K,
    payload: EventPayloadMap[K]
  ): void {
    const listenerSet = this.listeners.get(event);
    if (!listenerSet) return;

    for (const record of Array.from(listenerSet)) {
      const ownerDeref = record.owner.deref();
      
      // Jika owner sudah di-garbage collect oleh V8, bersihkan listener secara proaktif
      if (!ownerDeref) {
        listenerSet.delete(record);
        continue;
      }

      try {
        record.callbackRef(payload);
      } catch (err) {
        console.error(`[EventBus Error] Gagal mengeksekusi listener untuk event: ${String(event)}`, err);
      }
    }

    if (listenerSet.size === 0) {
      this.listeners.delete(event);
    }
  }
}

export const eventBus = EnterpriseEventBus.getInstance();
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Skala
Sebuah platform perbankan digital B2B memiliki monolitik frontend Angular/React hybrid dengan ukuran bundle mencapai **42 MB**, melibatkan 6 divisi rekayasa perangkat lunak (*Core Banking, Wealth Management, Payment Gateways, Forex, Corporate Admin*). 
- **Metrik Awal:** Build time CI/CD: 48 menit. Time-to-Interactive (TTI) di cold-start: 11.4 detik. Fatal crash akibat *V8 Out-Of-Memory* terjadi rata-rata 320 kali per 10.000 sesi.

#### Arsitektur Transformasi
Arsitek tim melakukan dekomposisi monolit menjadi arsitektur Micro-Frontend terfederasi:

```
[Akamai CDN Edge]
       |
       v
+------------------+     Fetch remoteEntry.js     +-------------------------+
| Shell Application|<============================>| Remote: Payments App    |
| (Host React 18)  |                              | (Vite Module Fed)       |
+--------+---------+                              +-------------------------+
         |
         |               Fetch remoteEntry.js     +-------------------------+
         +=======================================>| Remote: Forex Trading   |
                                                  | (React 18 + Web Workers)|
                                                  +-------------------------+
```

1. **Runtime Host Container:** Menggunakan Shell minimalis (ukuran < 80 KB gzipped) yang hanya mengelola otentikasi JWT, layout shell navigasi, dan routing tingkat atas.
2. **Federated Remotes:** Setiap domain dikonversi menjadi aplikasi remote independen yang merilis artifact-nya ke folder CDN terisolasi (`/cdn/remotes/payments/[hash]/remoteEntry.js`).
3. **Optimasi CRP & Memory:** 
   - Modul Forex Trading yang memproses 500 WebSocket tick/detik dipindahkan ke dalam *Dedicated Web Worker*. Operasi pengolahan state tidak lagi mengonsumsi CPU thread utama.
   - Pemanfaatan `requestAnimationFrame` untuk melakukan throttling render grafik valuta asing.

#### Hasil Terukur (Production Impact)
- **CI/CD Pipeline:** Waktu build turun drastis dari 48 menit menjadi 2.5 menit per domain.
- **Core Web Vitals:** LCP p95 membaik dari 7.2 detik menjadi 1.15 detik. TTI turun dari 11.4 detik menjadi 1.4 detik.
- **Kestabilan Runtime:** Insiden *Memory Crash* berkurang hingga 99.4% melalui isolasi siklus hidup alokasi DOM dan pembersihan referensi secara berkala saat navigasi antar-modul.

---

### 9. Trade-offs

Arsitektur micro-frontend dan rekayasa low-level performa bukanlah solusi perak (*no silver bullet*). Berikut perbandingan trade-off yang harus dianalisis:

| Dimensi Arsitektural | Keuntungan (Pros) | Konsekuensi Negatif (Cons / Trade-offs) | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Micro-Frontend via Module Federation** | Otonomi tim maksimal, rilis independen, isolasi kompilasi. | Kompleksitas tooling tinggi, potensi inkonsistensi styling, kompleksitas debugging lintas batas repo. | Standardisasi Design System via Web Components, centralized contract testing. |
| **Shared Global Dependencies** | Menghindari duplikasi download paket berat (React, Lodash, UI Engine). | Risiko *version collision*. Jika Host memaksakan versi major baru, Remote yang belum siap berpotensi runtime-error. | Aturan *strictVersion: false* dengan implementasi *fallback singleton* per minor release. |
| **Fine-Grained Reactivity (Proxy-based)** | Render minimalis, re-render hanya terjadi tepat pada simpul teks/elemen target. | Alokasi Proxy instances dalam jumlah jutaan dapat menaikkan overhead alokasi memori awal. | Batasi kedalaman reaktivitas (*shallow reactive*) untuk dataset tabular berukuran raksasa. |
| **Aggressive Service Worker Caching** | Navigasi offline instan, beban server origin mendekati nol untuk aset statis. | Risiko *Stale Cache*. Pengguna terjebak pada kode lama jika arsitektur cache busting gagal. | Cache header invariant: `Cache-Control: no-cache` pada file manifest; hash unik per chunk. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Detached DOM Nodes melalui Closure Callback
*Gejala:* Penggunaan memori peramban naik linier seiring waktu hingga tab browser mengalami crash (OOM).

```typescript
// ❌ ANTI-PATTERN: Closure menahan referensi elemen DOM besar
function setupHeavyWidget() {
  const massiveDomElement = document.getElementById('analytics-table');
  const heavyDataPayload = new Array(1000000).fill('leak_data');

  const onResize = () => {
    // heavyDataPayload dan massiveDomElement tertahan dalam lexical scope closure
    console.log('Size updated:', massiveDomElement?.clientWidth, heavyDataPayload.length);
  };

  window.addEventListener('resize', onResize);
  // Unmount hanya menghapus elemen dari tree visual, tapi listener global tetap memegang referensi!
  massiveDomElement?.remove();
}

//  CORRECT IMPLEMENTATION: Detach listener dan putus lexical reference
function setupHeavyWidgetFixed() {
  let massiveDomElement: HTMLElement | null = document.getElementById('analytics-table');
  
  const onResize = () => {
    if (!massiveDomElement) return;
    console.log('Size updated:', massiveDomElement.clientWidth);
  };

  const controller = new AbortController();
  window.addEventListener('resize', onResize, { signal: controller.signal });

  return function destroy() {
    // 1. Cabut event listener secara instan via AbortController
    controller.abort();
    // 2. Putus referensi pointer secara eksplisit
    massiveDomElement?.remove();
    massiveDomElement = null;
  };
}
```

#### 2. CSS Collision & Global Scope Pollution pada Micro-Frontend
*Gejala:* Style Remote A menimpa button pada Remote B tanpa peringatan kompilator.
- *Root Cause:* Dua aplikasi mikro mendefinisikan class `.btn-primary` dengan properti berbeda pada tingkat CSS root.
- *Troubleshooting:*
  1. Audit DOM inspector untuk memeriksa asal file CSS yang menimpa deklarasi spesifik (*specificity cascade*).
  2. Isolasi styling dengan memanfaatkan **Shadow DOM** (`attachShadow({ mode: 'open' })`) atau konfigurasikan PostCSS/CSS Modules prefixing unik per sub-aplikasi (misal: `.mfe-billing .btn-primary`).

#### 3. Hydration Mismatch Bottleneck
*Gejala:* Layar berkedip (*flash of content*) saat SSR loading, diiringi pesan konsol: `Warning: Text content did not match. Server: "X" Client: "Y"`.
- *Diagnosa:* Komponen merender data non-deterministik seperti `new Date()`, `Math.random()`, atau membaca `window.localStorage` secara sinkron saat fase initial render komponen server.
- *Solusi:* Isolasi kode non-deterministik hanya di dalam lifecycle client (`useEffect` atau `onMounted`).

---

### 11. Best Practices (Production Checklist)

#### Architecture & Performance
- [ ] CSS animations hanya memanfaatkan properti `transform` dan `opacity` untuk menjamin render berlangsung murni pada Compositor Thread (GPU).
- [ ] Hindari forced synchronous layouts: Gunakan `IntersectionObserver` alih-alih polling `getBoundingClientRect()` di dalam scroll listener.
- [ ] Eksekusi dataset parsing > 5MB di luar UI Thread menggunakan Dedicated Web Worker.
- [ ] Module Federation Host harus mengimplementasikan timeout fallback jika remote gagal merespons dalam < 3000ms.

#### Security
- [ ] Amankan runtime eksekusi Remote Micro-Frontend dengan membatasi akses DOM melalui *Content Security Policy (CSP)* yang ketat:
  ```http
  Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.enterprise.io;
  ```
- [ ] Sandboxing window object jika remote berasal dari domain ketiga menggunakan `iframe` sandboxed atau library Proxy Virtualization (e.g., qiankun JS Sandbox).

#### Memory & Reliability
- [ ] Wajib menggunakan `AbortController` untuk pembatalan massal fetch requests dan event listener ketika komponen di-unmount.
- [ ] Analisis Heap Snapshot minimal 1x per sprint: Bandingkan snapshot *Before User Action* vs *After Action* vs *After Unmount*. Jumlah simpul `Detached HTMLDivElement` harus nol.

---

### 12. Hands-on Practice

Buatlah infrastruktur simulasi Micro-Frontend Host & Remote berbasis Native ESM Import Maps dan Sandboxed Messaging pada repositori lokal Anda di `hands-on/m02/`.

#### Struktur Direktori:
```
hands-on/m02/
├── package.json
├── host-app/
│   ├── index.html
│   ├── src/
│   │   ├── main.ts
│   │   └── sandbox-loader.ts
├── remote-app/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       └── widget.ts
```

#### Langkah-Langkah Implementasi:

##### Langkah 1: Host Sandbox Loader (`hands-on/m02/host-app/src/sandbox-loader.ts`)
Implementasikan sandbox runner yang melindungi namespace `window` global dari polusi Remote.

```typescript
export class RuntimeSandbox {
  private fakeWindow: Record<string, unknown> = {};
  private proxy: Window;

  constructor() {
    this.proxy = new Proxy(window, {
      get: (target, prop: string) => {
        if (prop in this.fakeWindow) {
          return this.fakeWindow[prop];
        }
        const value = target[prop as keyof Window];
        // Bind window functions back to original window context
        if (typeof value === 'function') {
          return value.bind(target);
        }
        return value;
      },
      set: (_target, prop: string, value: unknown) => {
        this.fakeWindow[prop] = value;
        return true;
      },
      has: (_target, prop: string) => {
        return prop in this.fakeWindow || prop in window;
      }
    });
  }

  public executeScript(code: string): void {
    const runner = new Function('window', `with(window) { ${code} }`);
    runner(this.proxy);
  }

  public getSandboxState(): Record<string, unknown> {
    return { ...this.fakeWindow };
  }
}
```

##### Langkah 2: Host Orchestrator (`hands-on/m02/host-app/src/main.ts`)

```typescript
import { RuntimeSandbox } from './sandbox-loader';

console.log('[Host] Menginisialisasi Host Platform...');

const sandbox = new RuntimeSandbox();

// Simulasi load skrip Remote yang mencoba mencemari global variable
const simulatedRemoteCode = `
  window.remoteVariable = "SECURITY_BREACH_DATA";
  console.log("[Remote Inside Sandbox] Setting remoteVariable berhasil");
`;

sandbox.executeScript(simulatedRemoteCode);

// Verifikasi window global tidak tercemar
console.log('[Host Root Window] window.remoteVariable:', (window as unknown as Record<string, unknown>).remoteVariable); // undefined
console.log('[Host Sandboxed Window]:', sandbox.getSandboxState()); // { remoteVariable: "SECURITY_BREACH_DATA" }
```

##### Langkah 3: Eksekusi dan Verifikasi
Jalankan kompilasi TypeScript dan tinjau luaran terminal/browser console:
```bash
cd hands-on/m02/host-app
npx tsx src/main.ts
```
*Hasil yang diharapkan:* Nilai `window.remoteVariable` pada Host Root Window tetap bernilai `undefined`, menandakan keberhasilan isolasi eksekusi modul Remote.

---

### 13. Exercise

#### Tingkat: Easy
Identifikasi bottleneck performa dari cuplikan kode render berikut dan perbaiki kodenya:
```javascript
function updateBadges(items) {
  items.forEach(item => {
    document.getElementById(item.id).innerHTML = `<span>${item.count}</span>`;
  });
}
```
*Tugas:* Ubah implementasi di atas agar menggunakan `DocumentFragment` atau batch update untuk menghindari modifikasi pohon DOM berulang pada setiap iterasi.

#### Tingkat: Medium
Buat sebuah fungsi utilitas TypeScript `detectLayoutThrashing(callback: () => void): void` yang melakukan *monkey patching* sementara terhadap properti geometris (`offsetHeight`, `offsetWidth`, `scrollTop`, dll.) dan memancarkan peringatan `console.warn` jika terdeteksi pembacaan geometri yang diselingi oleh penulisan DOM (`style.*`, `setAttribute`, dll.) dalam 1 siklus frame eksekusi yang sama.

#### Tingkat: Hard
Rancang dan bangun implementasi arsitektur **DOM Virtual-Scroll Engine** dari nol (*pure TypeScript*, tanpa framework).
- *Spesifikasi Teknis:*
  - Harus mampu me-render daftar array berisi 500.000 item.
  - Alokasi elemen DOM fisik pada halaman dibatasi konstan hanya sebanyak item yang muat pada viewport + buffer (misal: total $\approx 30$ elemen).
  - Mengelola translateY secara deterministik saat pengguna menggulir secara cepat (*high-velocity scroll*).
  - Penggunaan memori Heap harus konstan ($\mathcal{O}(1)$ relative to total records).

---

### 14. Challenge

#### Skenario: Arsitektur Frontend High-Frequency Trading Terminal

Anda ditunjuk sebagai Principal Frontend Architect untuk membangun ulang terminal valuta asing institusional yang menangani:
- **Throughput Data:** 3.000 update tick harga per detik via WebSocket.
- **Visualisasi Komponen:** 1 tabel order book (100 kedalaman baris), 1 grafik real-time WebGL, dan 1 order execution widget.
- **Batasan SLA Sistem:** 
  1. Main thread execution time tidak boleh melebihi 16.6ms per frame (wajib lock di 60 FPS tanpa dropped frames).
  2. Alokasi memori heap browser tidak boleh melebihi batas 150 MB selama 8 jam jam kerja trading nonstop.
  3. Desain harus berbasis Micro-Frontend: Modul Grafik dikembangkan oleh Tim Data Viz (Tech Stack: Svelte), modul Order Execution oleh Tim Core Banking (Tech Stack: React 18).

#### Deliverables yang Harus Dirancang:
1. **Diagram Alur Data & State Processing:** Bagaimana data tick WebSocket di-ingest, di-buffer, di-filter, dan dikirimkan ke UI tanpa menyebabkan layout thrashing dan V8 garbage collection spikes?
2. **Spesifikasi Teknis Interop Micro-Frontend:** Bagaimana cara mengintegrasikan modul berbasis Svelte dan React di dalam satu container tanpa overhead performa dan kebocoran memori?
3. **Peta Penanganan Memori:** Rancang strategi pencegahan kebocoran memori pada data streaming yang masuk terus menerus secara matematis dan sistematis.

*(Sajikan rancangan arsitektur ini dalam bentuk dokumen cetak biru desain sistem teknis lengkap dengan diagram komponen dan pseudo-code komponen pengatur state buffer).*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda & Analisis Singkat)
1. Apa perbedaan mendasar antara fase **Layout (Reflow)** dan **Paint (Repaint)** pada Critical Rendering Path?
   - A. Layout mengubah warna piksel, Paint menghitung posisi elemen.
   - B. Layout menghitung koordinat dan geometri elemen visual, Paint mengonversi elemen tersebut menjadi piksel pada raster buffer.
   - C. Layout dieksekusi di GPU, Paint dieksekusi di CPU.
   - D. Layout hanya terjadi sekali, Paint terjadi pada setiap interaksi.
2. Mengapa properti CSS `transform: translate3d()` lebih efisien daripada `top: ...px` untuk animasi?
   - A. Mengurangi alokasi memori pada stack JavaScript.
   - B. Melewati tahapan Layout dan Paint, langsung diproses oleh Compositor Thread dan GPU.
   - C. Menghentikan parsing HTML secara instan.
   - D. Menyebabkan Garbage Collector membersihkan layer lama.
3. Area memori mana pada V8 Engine yang menampung objek yang berhasil melewati beberapa kali siklus Garbage Collection?
   - A. New Space (Nursery).
   - B. Intermediate Space.
   - C. Old Pointer Space (Old Generation).
   - D. Large Object Space.
4. Apa yang dimaksud dengan *Detached DOM Node*?
   - A. Node yang dibuat di luar memori browser.
   - B. Node DOM yang sudah dilepas dari pohon dokumen aktif, namun masih ditahan oleh referensi variabel JavaScript.
   - C. Komponen React yang tidak memiliki file CSS.
   - D. Elemen HTML yang disembunyikan menggunakan `display: none`.
5. Apa fungsi utama manifest file (`remoteEntry.js`) pada Webpack Module Federation?
   - A. Berisi salinan seluruh source code aplikasi remote secara statis.
   - B. Bertindak sebagai interface publik dan resolver runtime yang berisi mapping modul yang diekspos serta daftar shared dependencies.
   - C. Menjadi database penyimpanan token otentikasi user.
   - D. Mengubah CSS menjadi instruksi WebGL.

#### Bagian 2: Intermediate
6. Mengapa pembacaan properti seperti `element.scrollTop` secara langsung setelah mutasi `element.style.height` memicu performa bottleneck yang fatal?
   - A. Karena properti tersebut bersifat asynchronous.
   - B. Karena memicu *Forced Synchronous Layout* (Layout Thrashing), memaksa browser menghitung ulang geometri secara seketika sebelum giliran render berikutnya.
   - C. Karena V8 akan langsung melakukan Scavenge Garbage Collection.
   - D. Karena menghapus elemen anak dari memori.
7. Pada arsitektur Island Architecture, apa yang dimaksud dengan proses *Selective / Partial Hydration*?
   - A. Hanya men-download file HTML tanpa CSS.
   - B. Mengubah seluruh kode client menjadi WebAssembly.
   - C. Merender seluruh halaman secara statis di server, dan hanya menjalankan hidrasi JavaScript pada komponen (*islands*) yang secara spesifik membutuhkan interaktivitas pengguna.
   - D. Melakukan compile ulang aplikasi pada sisi client setiap kali user melakukan navigasi.
8. Bagaimanakah cara kerja Garbage Collector tipe Scavenger (Cheney's Algorithm) di New Space V8?
   - A. Menandai seluruh heap dan menghentikan seluruh thread selama 5 detik.
   - B. Membagi New Space menjadi From-Space dan To-Space; menyalin objek yang masih aktif ke To-Space, lalu membalik peran kedua space tersebut dan mengosongkan From-Space.
   - C. Memindahkan seluruh objek langsung ke disk SSD.
   - D. Menghapus semua memori yang berumur lebih dari 10 milidetik.
9. Manakah cara paling aman untuk mendistribusikan token sesi global antar Micro-Frontend tanpa menyebabkan high-coupling atau runtime pollution?
   - A. Menyimpan token di variabel global `window.enterpriseToken = "..."`.
   - B. Membaca langsung DOM dari Remote lain via querySelector.
   - C. Menggunakan broadcast messaging via Sandboxed Event Bus berbasis Pub/Sub yang mengonfirmasi identitas pemanggil (*origin validation*).
   - D. Meng-embed token di setiap file JavaScript yang di-build.
10. Kapan sebaiknya arsitektur Micro-Frontend **TIDAK** digunakan pada sebuah proyek?
    - A. Ketika aplikasi memiliki lebih dari 100 fitur.
    - B. Ketika tim rekayasa perangkat lunak berskala kecil (< 15 engineer), domain bisnis masih dalam tahap pencarian product-market fit, dan dependensi antar modul masih sangat erat.
    - C. Ketika aplikasi harus di-host pada multi-cloud.
    - D. Ketika aplikasi membutuhkan dukungan mobile responsive.

#### Bagian 3: Skenario Kasus Produksi
11. **Kasus 1: Memory Leak Diagnostik**
    Tim Anda merilis fitur dasbor live-chart baru. Pengguna korporat melaporkan bahwa setelah membuka tab dashboard selama 4 jam tanpa reload, tab peramban mereka crash dengan status *Out of Memory*. Pada Chrome DevTools Heap Snapshot, tercatat ribuan instance `Detached HTMLDivElement` yang dikaitkan dengan event listener global window. 
    *Pertanyaan:* Uraikan tahapan investigasi snapshot dan langkah mitigasi kode definitif untuk menuntaskan masalah ini!
12. **Kasus 2: Micro-Frontend Dependency Mismatch**
    Host Application berjalan menggunakan `React v18.2.0`. Tim Remote "Checkout" meluncurkan pembaruan yang dikompilasi menggunakan `React v17.0.2` dan library pihak ketiga yang bergantung secara kaku (*strict peer dependency*) pada React 17. Pada saat runtime, pemanggilan hook pada modul Checkout melempar error: `Invalid Hook Call: Hooks can only be called inside the body of a function component`.
    *Pertanyaan:* Analisis mengapa error ini terjadi di level arsitektur Module Federation, dan bagaimana konfigurasi `shared` scope pada Module Federation harus diatur untuk mengatasinya?
13. **Kasus 3: Eliminasi FCP Spike di Jaringan Terbatas**
    Sebuah aplikasi logistik lapangan diakses menggunakan jaringan seluler 3G di daerah pelosok. FCP saat ini berada di angka 6.8 detik karena bundle entry JavaScript sebesar 3.8 MB yang berisi seluruh rute aplikasi.
    *Pertanyaan:* Rancang strategi arsitektural komprehensif (melibatkan Bundler, Service Worker, dan CDN) untuk memangkas FCP hingga di bawah 1.5 detik tanpa mematikan fitur utama aplikasi!

---

### Kunci Jawaban & Evaluasi Pemahaman

#### Bagian 1: Basic
1. **B** — Layout menghitung kalkulasi geometris simpul; Paint menggambar warna, teks, bayangan ke dalam piksel raster visual.
2. **B** — Properti transformasi 3D langsung dialihkan ke Compositor Thread/GPU tanpa memicu Reflow atau Repaint pada main thread.
3. **C** — Objek yang bertahan setelah 2 kali siklus minor GC akan dipromosikan (*tenured*) ke Old Pointer Space.
4. **B** — Node DOM yang telah dicopot dari pohon visual aktif namun variabel referensinya masih tertahan di heap memory.
5. **B** — Berfungsi sebagai file manifest/resolver runtime yang memetakan modul yang diekspos dan menegosiasikan shared dependency.

#### Bagian 2: Intermediate
6. **B** — Browser dipaksa menghentikan eksekusi JavaScript dan langsung menjalankan layout engine seketika (*Forced Synchronous Layout*) untuk mendapatkan kalkulasi metrik posisi terbaru.
7. **C** — Arsitektur Island memprioritaskan pure static HTML dari server dan hanya menghidrasi komponen interaktif individual yang membutuhkan JavaScript di browser.
8. **B** — Cheney's copying algorithm memisahkan new space menjadi From dan To space, memindahkan pointer simpul aktif, dan mengklaim ulang space lama secara instan.
9. **C** — Pola Sandboxed Event-Bus menjaga isolasi state, mencegah perusakan variabel global di `window`, dan memvalidasi kredensial pengirim event.
10. **B** — Mengadopsi arsitektur Micro-Frontend pada tim kecil atau domain yang belum stabil menimbulkan *operational overhead* dan kompilasi kompleks yang melampaui manfaat skalabilitasnya.

#### Bagian 3: Skenario Kasus Produksi
11. **Rasional Solusi Kasus 1:**
    - *Investigasi:* Ambil 3 Heap Snapshot berturut-turut dengan interval 15 menit. Filter berdasarkan string *"Detached"*. Identifikasi retainers path dari elemen yang bocor untuk menemukan objek root yang menahannya.
    - *Mitigasi:* Identifikasi event listener pada `window` atau `setInterval` yang tidak dibersihkan saat komponen di-unmount. Terapkan `AbortController` yang terikat pada siklus hidup unmount komponen untuk memutus seluruh event listener global secara atomik, serta setel referensi elemen DOM ke `null`.
12. **Rasional Solusi Kasus 2:**
    - *Akar Masalah:* React Hooks mensyaratkan single instance dispatcher per runtime context. Terjadi duplikasi instance React (Host memuat React 18, Remote memuat React 17 secara bersamaan) yang merusak internal execution dispatcher.
    - *Solusi:* Pada konfigurasi Webpack/Vite Module Federation, konfigurasi shared dependencies harus diselaraskan:
      ```javascript
      shared: {
        react: { singleton: true, requiredVersion: "^18.0.0" },
        "react-dom": { singleton: true, requiredVersion: "^18.0.0" }
      }
      ```
      Jika Remote terpaksa menggunakan React 17 karena dependensi legacy, modul tersebut harus diisolasi total ke dalam *Sandboxed IFrame Sub-App* atau dikompilasi menjadi *Standard Web Component* tanpa membagikan React runtime context dari Host.
13. **Rasional Solusi Kasus 3:**
    - *Optimasi Bundler:* Terapkan *Route-based Dynamic Splitting* (`React.lazy()` / Dynamic `import()`) untuk memecah bundle monolitik 3.8 MB menjadi pecahan chunk kecil per-halaman (< 80 KB).
    - *Infrastruktur Jaringan:* Aktifkan kompresi Brotli (`br`) pada CDN Edge, terapkan HTTP/2 multiplexing, dan tambahkan preloading `<link rel="modulepreload">` untuk initial route chunks.
    - *Service Worker Strategy:* Implementasikan Service Worker dengan strategi *Cache-First (Stale-While-Revalidate)* untuk static core app shell, sehingga pemuatan subsequent FCP pada jaringan 3G tereduksi menjadi instant (< 500ms) langsung dari disk Cache Storage.

---

### 16. Summary

1. **Performa Dimulai dari Engine:** Pemahaman mendalam atas Critical Rendering Path (CRP) dan arsitektur alokasi memori V8 GC merupakan prasyarat mutlak untuk membangun aplikasi frontend kelas enterprise yang stabil dan responsif.
2. **Kendalikan Layout & Memory:** Hindari *Layout Thrashing* dengan melakukan batching pembacaan dan penulisan DOM melalui `requestAnimationFrame`. Cegah *Detached DOM Leaks* dengan disiplin membersihkan closures, event listeners, dan timers menggunakan lifecycle guard modern seperti `AbortController` dan `WeakRef`.
3. **Skalabilitas Organisasi via Micro-Frontend:** Micro-Frontend bukan sekadar pemisahan repositori, melainkan orkestrasi runtime mandiri berbasis Module Federation yang membutuhkan standardisasi isolasi style, sandboxing namespace, dan komunikasi berbasis event-bus asinkronus yang aman.
4. **Resiliensi Melalui Desain:** Kecepatan dan keandalan sistem frontend modern diukur dari performa p99 Core Web Vitals pada kondisi jaringan ekstrem, yang dicapai melalui pemisahan chunk pintar, kompresi edge modern, dan strategi caching offline-first.