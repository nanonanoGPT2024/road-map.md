# BAB 05 MODULE 01: State Management Engines & Reactive Patterns

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** Frontend and Mobile Engineering
* **Kategori Jalur:** `03-Frontend-and-Mobile`
* **Kode Modul:** `FE-ENG-05-01`
* **Judul Modul:** State Management Engines & Reactive Patterns
* **Tingkat Kompleksitas:** Advanced / Staff-Level Engineering
* **Prasyarat Konseptual:** 
  * Advanced JavaScript (ESNext, Closures, Prototypes, Microtasks/Macrotasks execution context).
  * DOM Reconciliation Engines (Virtual DOM diffing, Fiber Architecture, Direct DOM mutations).
  * Reactive Paradigms dasar (Observer Pattern, Publish-Subscribe, Iterable/AsyncIterable).
  * TypeScript Generics tingkat lanjut (Conditional types, Indexed access types, Type inference).

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, engineer diharapkan mampu:

1. **Membedah & Mengimplementasikan Reactive Primitives:** Merancang reactive engine berbasis Signal-Slot, Observable Streams, dan Immutable Flux Store murni tanpa dependensi eksternal dari nol.
2. **Menganalisis Topologi Dependency Tracking:** Mendiagnosis eksekusi runtime graph dynamic dependency tracking menggunakan struktur data doubly-linked list atau directed acyclic graph (DAG) untuk mencegah siklus rekursif dan *glitch artifacts*.
3. **Mengoptimalkan Jalur Rendering Engine:** Mengeliminasi unnecessary render passes dan component-level re-evaluation dengan mendistribusikan fine-grained reactivity langsung ke target DOM mutations.
4. **Menerapkan Manajemen State Skala Enterprise:** Mengonstruksi arsitektur state terdistribusi yang resilient, mendukung runtime telemetry, time-travel debugging, dan serialisasi memory-efficient pada aplikasi berbasis concurrent load tinggi.
5. **Mitigasi Masalah Kinerja & Memori:** Mendeteksi dan memitigasi memory leaks akibat lingering subscriptions, topological graph cycles, dan uncollected closures menggunakan profiling memory heaps tingkat lanjut.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam rekayasa sistem antarmuka web modern, state bukan sekadar objek JSON yang dimutasi semata untuk merender ulang komponen. State adalah **jantung deterministik dari finite state machine (FSM)** yang mengatur status sistem pada setiap irisan waktu ($t$).

```
        MENTAL MODEL PERGESERAN PARADIGMA:
        
   [Model Tradisional: Coarse-Grained Virtual DOM Reconciliation]
   State Change ───> Re-render Parent ───> Diff Virtual Subtree ───> Patch Real DOM
                   (Komputasi O(N) sebanding dengan ukuran sub-tree)

   [Model Modern: Fine-Grained Reactive Graph Evaluation]
   Signal Mutation ───> Direct Graph Notification ───> Point Mutation ke Real DOM node
                   (Komputasi O(1) sebanding dengan jumlah subscriber aktif)
```

### Konsep Inti Mental Model:
* **The Push-Pull Engine:** Sistem reaktif modern tidak murni bersandar pada *push* (mengirim data ke seluruh subscriber seketika) atau *pull* (menghitung ulang nilai saat dibaca). Mesin mutakhir mengombinasikannya: *Push dirty flags* secara topologis untuk menandai state yang usang, kemudian *Pull compute values* secara malas (*lazy evaluation*) saat nilai tersebut benar-benar diminta oleh render execution context.
* **State As Dependency Graph:** Pandanglah state sebagai node-node dalam *Directed Acyclic Graph* (DAG). Node dasar adalah *Source/Atom/Signal*, node perantara adalah *Derivations/Computed*, dan node daun adalah *Sinks/Effects*.
* **Glitch-Free Guarantee:** Keadaan di mana sebuah derivasi tidak boleh mengevaluasi intermediate state yang belum sinkron, yang dapat menghasilkan inkonsistensi visual sementara (*glitches*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur internal alur dynamic dependency tracking pada Fine-Grained Reactive Signals Engine:

```
+-----------------------------------------------------------------------------------------+
|                               REACTIVE ENGINE TOPOLOGY (DAG)                            |
+-----------------------------------------------------------------------------------------+
                                                                                           
   [Signal Node: A]              [Signal Node: B]                                         
     (version: 1)                  (version: 1)                                           
          │                             │                                                 
          │  register dep               │  register dep                                   
          ▼                             ▼                                                 
   +-------------------------------------------+                                          
   |          Computed Node: C (A + B)         |                                          
   |          (status: CLEAN, version: 1)      |                                          
   +-------------------------------------------+                                          
                         │                                                                
                         │ register dep                                                   
                         ▼                                                                
   +-------------------------------------------+                                          
   |               Effect Node: D              |                                          
   |       (Runs DOM Mutation: Target Node)    |                                          
   +-------------------------------------------+                                          
                                                                                           
================================ RUNTIME MUTATION FLOW ====================================
                                                                                           
1. MUTATION:                                                                              
   Signal A.set(2) ────────────────────────────────────────────────────────┐               
                                                                           │               
2. DIRTY PROPAGATION (Mark Phase):                                         ▼               
   Signal A ──(Notify Dirty)──> Computed C [Status: STALE] ──(Notify)──> Effect D [DIRTY] 
                                                                           │               
3. BATCH SCHEDULING:                                                       │               
   Queue.push(Effect D) ──> Microtask Scheduler Registered <───────────────┘               
                                                                                           
4. EVALUATION & PULL PHASE (Run Phase):                                                   
   Microtask Drain:                                                                       
     Effect D calls compute()                                                             
       └──> Reads Computed C                                                              
              └──> Computed C detects STALE:                                              
                     └──> Pulls Signal A (val: 2) & Signal B (val: 1)                     
                     └──> Computes new val: 3                                             
                     └──> C [Status: CLEAN]                                               
       └──> Effect D updates target DOM direct text node: "3"                             
+-----------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Mesin state reaktif modern (Signals) dibangun di atas tiga fondasi utama:

1. **Context Stack (`Subscriber Stack`):**
   Array atau linked list global yang menyimpan context eksekusi komputasi atau efek yang sedang aktif. Saat sebuah node computed/efek dieksekusi, node tersebut mendorong dirinya sendiri (*push*) ke stack. Saat membaca signal, signal memeriksa elemen teratas stack untuk mendaftarkan dependensi secara otomatis (*dynamic tracking*).

2. **Link Node (Dependency Edge):**
   Hubungan antara *Node Sumber* (Signal) dan *Node Konsumen* (Subscriber/Computed/Effect). Untuk efisiensi garbage collection, link ini umumnya mengimplementasikan *two-way linked list*:
   * Signal memegang referensi ke semua subscriber-nya (*dependents*).
   * Subscriber memegang referensi ke semua signal yang dibacanya (*dependencies*).

3. **Status Bitflags (Engine Flags):**
   State engine menggunakan bitwise flags untuk optimasi status node dalam memori:
   * `DIRTY (0b001)`: Nilai dependensi berubah pasti, kalkulasi ulang wajib dilakukan.
   * `CHECK (0b010)`: Nilai dependensi perantara (computed) mungkin berubah; perlu ditarik untuk konfirmasi keabsahan sebelum kalkulasi ulang.
   * `CLEAN (0b100)`: Nilai cache valid, gunakan langsung tanpa evaluasi ulang.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Glitch Freedom dan Topological Ordering
Masalah fundamental pada *naive observer pattern* adalah fenomena **Diamond Dependency**:

```
      Signal A
      /      \
     ▼        ▼
Computed B   Computed C
     \        /
      ▼      ▼
     Computed D
```

Jika Signal `A` berubah, dan observer engine mengeksekusi pendengar secara naif (DFS/BFS traversal):
1. `A` mengabari `B`. `B` menghitung ulang.
2. `B` mengabari `D`. `D` menghitung ulang menggunakan nilai baru `B` dan **nilai usang (stale)** dari `C`.
3. Inilah yang disebut **glitch**: `D` mengkalkulasi state yang secara matematis invalid selama beberapa milidetik.
4. Terakhir, `A` mengabari `C`, `C` menghitung ulang, dan `C` mengabari `D`. `D` menghitung ulang lagi untuk kedua kalinya.

**Solusi Algoritmik:**
Mesin reactive modern menerapkan pemisahan fasa:
1. **Notification/Marking Phase (Forward Pass):** Menandai node anak ke bawah dengan flag `CHECK` atau `DIRTY` secara rekursif tanpa mengeksekusi body fungsinya.
2. **Evaluation/Stabilization Phase (Backward/Pull Pass):** Mengurutkan eksekusi berdasarkan topological ordering atau level depth graph, sehingga `D` tidak akan pernah dievaluasi sebelum `B` dan `C` sama-sama mencapai status `CLEAN`.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi murni *fine-grained reactive engine* independen (Signals, Computed, Effect, Batching) dengan TypeScript:

```typescript
// Core Types
type Subscriber = {
  update(): void;
  flags: number;
};

const FLAG_CLEAN = 0;
const FLAG_CHECK = 1 << 0;
const FLAG_DIRTY = 1 << 1;

// Global Tracking Context
let activeSubscriber: Subscriber | null = null;
const subscriberStack: (Subscriber | null)[] = [];

let isBatching = false;
const pendingEffects: Set<Subscriber> = new Set();

export function pushContext(sub: Subscriber | null): void {
  subscriberStack.push(activeSubscriber);
  activeSubscriber = sub;
}

export function popContext(): void {
  activeSubscriber = subscriberStack.pop() ?? null;
}

export function batch(fn: () => void): void {
  const prevBatching = isBatching;
  isBatching = true;
  try {
    fn();
  } finally {
    isBatching = prevBatching;
    if (!isBatching) {
      flushEffects();
    }
  }
}

function flushEffects(): void {
  while (pendingEffects.size > 0) {
    const effectsToRun = Array.from(pendingEffects);
    pendingEffects.clear();
    for (const effect of effectsToRun) {
      effect.update();
    }
  }
}

// 1. SIGNAL INTERFACE & CLASS
export interface Signal<T> {
  get(): T;
  set(newValue: T): void;
}

export class SignalNode<T> implements Signal<T> {
  private value: T;
  private subscribers: Set<Subscriber> = new Set();

  constructor(initialValue: T) {
    this.value = initialValue;
  }

  get(): T {
    if (activeSubscriber !== null) {
      this.subscribers.add(activeSubscriber);
    }
    return this.value;
  }

  set(newValue: T): void {
    if (!Object.is(this.value, newValue)) {
      this.value = newValue;
      this.notify();
    }
  }

  private notify(): void {
    for (const sub of this.subscribers) {
      sub.flags |= FLAG_DIRTY;
      if (isBatching) {
        pendingEffects.add(sub);
      } else {
        sub.update();
      }
    }
  }

  unsubscribe(sub: Subscriber): void {
    this.subscribers.delete(sub);
  }
}

export function createSignal<T>(initialValue: T): [() => T, (val: T) => void] {
  const node = new SignalNode(initialValue);
  return [() => node.get(), (val: T) => node.set(val)];
}

// 2. COMPUTED INTERFACE & CLASS
export class ComputedNode<T> implements Subscriber {
  private fn: () => T;
  private cachedValue!: T;
  private dependencies: Set<SignalNode<any>> = new Set();
  private subscribers: Set<Subscriber> = new Set();
  public flags: number = FLAG_DIRTY;

  constructor(fn: () => T) {
    this.fn = fn;
  }

  get(): T {
    if (activeSubscriber !== null) {
      this.subscribers.add(activeSubscriber);
    }

    if (this.flags !== FLAG_CLEAN) {
      this.recompute();
    }

    return this.cachedValue;
  }

  update(): void {
    if ((this.flags & FLAG_DIRTY) === 0) {
      this.flags |= FLAG_CHECK;
      for (const sub of this.subscribers) {
        sub.update();
      }
    }
  }

  private recompute(): void {
    // Dynamic tracking cleanup
    for (const dep of this.dependencies) {
      dep.unsubscribe(this);
    }
    this.dependencies.clear();

    pushContext(this);
    try {
      const nextValue = this.fn();
      if (!Object.is(this.cachedValue, nextValue)) {
        this.cachedValue = nextValue;
      }
      this.flags = FLAG_CLEAN;
    } finally {
      popContext();
    }
  }
}

export function createComputed<T>(fn: () => T): () => T {
  const node = new ComputedNode(fn);
  return () => node.get();
}

// 3. EFFECT INTERFACE & IMPLEMENTATION
export class EffectNode implements Subscriber {
  private fn: () => void;
  public flags: number = FLAG_DIRTY;

  constructor(fn: () => void) {
    this.fn = fn;
    this.run();
  }

  run(): void {
    pushContext(this);
    try {
      this.fn();
      this.flags = FLAG_CLEAN;
    } finally {
      popContext();
    }
  }

  update(): void {
    this.flags |= FLAG_DIRTY;
    if (isBatching) {
      pendingEffects.add(this);
    } else {
      this.run();
    }
  }
}

export function createEffect(fn: () => void): void {
  new EffectNode(fn);
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 1–9 (`Subscriber`, `Bitflags`):**
  Mendefinisikan kontrak objek subscriber dan bitmask. Menggunakan operasi bitwise (`1 << 0`, `1 << 1`) menjamin manipulasi dirty checking berjalan pada instruksi CPU tingkat rendah dengan overhead latensi minimum.
* **Baris 11–13 (`subscriberStack`):**
  Struktur stack global untuk melacak context pemanggil secara imperatif saat runtime mengakses method `get()` pada signal.
* **Baris 15–38 (`batch` & `flushEffects`):**
  Menyediakan mekanisme transaksi untuk mutasi state majemuk. Mutasi dalam callback `batch` tidak memicu eksekusi effect secara sinkron seketika, melainkan mengumpulkan subscriber unik ke dalam `Set<Subscriber>` untuk dieksekusi sekali secara sekuensial saat blok tuntas.
* **Baris 54–60 (`SignalNode.get`):**
  Kunci *automatic dependency injection*. Jika fungsi dijalankan di dalam context effect/computed (`activeSubscriber !== null`), node otomatis mendaftarkan subscriber tersebut ke `this.subscribers`.
* **Baris 62–67 (`SignalNode.set`):**
  Menggunakan `Object.is` untuk *equality checking*. Jika nilai tidak berubah, proses propagating signal dihentikan di level leaf node, mencegah cascade re-evaluation yang mubazir.
* **Baris 108–122 (`ComputedNode.recompute`):**
  Menerapkan dynamic dependency untracking. Setiap kali evaluasi ulang dilakukan, computed melepaskan diri dari dependensi lama sebelum mengeksekusi ulang fungsi. Ini menangani dependensi kondisional cabang *if/else* tanpa memicu kebocoran memori (memory leak) dari dependency cabang yang tidak lagi aktif.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Financial Order Book & High-Frequency Scalping Terminal
Sebuah bursa kripto tier-1 memerlukan modul eksekusi visual di frontend yang menerima stream data via WebSocket dengan throughput hingga 500 pembaruan per detik (500 ops/sec).

**Tantangan Sistem:**
* Pola Virtual DOM standar (seperti pure React `useState` pada component root) membeku total karena proses recursive reconciliation memblokir JavaScript main-thread, menjatuhkan framerate hingga <15 FPS.
* Kebutuhan: Menghitung total likuiditas (Bid/Ask spread, Depth calculation, PnL) secara *real-time* dan memodifikasi *Specific DOM Nodes* langsung (warna baris dan volume bar) secara bypass tanpa re-render tree komponen virtual.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur state engine kustom dengan Fine-Grained Point-to-Point DOM mutations untuk Terminal Orderbook:

```typescript
// OrderBookEngine.ts

type Order = {
  price: number;
  size: number;
};

// In-Memory Fine-Grained Reactive Store
class OrderBookStore {
  // Signals mentah (Ingestion nodes)
  public bids: SignalNode<Order[]>;
  public asks: SignalNode<Order[]>;
  
  // Computed Nodes (Business Logic Derivations)
  public bestBid: ComputedNode<number>;
  public bestAsk: ComputedNode<number>;
  public spread: ComputedNode<number>;

  constructor() {
    this.bids = new SignalNode<Order[]>([]);
    this.asks = new SignalNode<Order[]>([]);

    this.bestBid = new ComputedNode<number>(() => {
      const currentBids = this.bids.get();
      return currentBids.length > 0 ? currentBids[0].price : 0;
    });

    this.bestAsk = new ComputedNode<number>(() => {
      const currentAsks = this.asks.get();
      return currentAsks.length > 0 ? currentAsks[0].price : 0;
    });

    this.spread = new ComputedNode<number>(() => {
      const bid = this.bestBid.get();
      const ask = this.bestAsk.get();
      return ask > 0 && bid > 0 ? ask - bid : 0;
    });
  }

  // Batch Ingestion dari WebSocket Event Stream
  public ingestDelta(newBids: Order[], newAsks: Order[]): void {
    batch(() => {
      this.bids.set(newBids);
      this.asks.set(newAsks);
    });
  }
}

// Point-to-Point DOM Binder (Tanpa Virtual DOM Overhead)
export class OrderBookRenderer {
  private store: OrderBookStore;

  constructor(store: OrderBookStore) {
    this.store = store;
  }

  public mount(rootContainer: HTMLElement): void {
    rootContainer.innerHTML = `
      <div class="terminal-panel" style="font-family: monospace; padding: 1rem; background: #0d1117; color: #c9d1d9;">
        <h3>REAL-TIME ORDER ENGINE</h3>
        <div class="row">Best Bid: <span id="val-best-bid" style="color: #3fb950;">--</span></div>
        <div class="row">Best Ask: <span id="val-best-ask" style="color: #f85149;">--</span></div>
        <div class="row">Spread: <span id="val-spread" style="color: #d29922;">--</span></div>
        <hr/>
        <div id="depth-container">Rendering pipeline: DIRECT REAL-DOM STREAM</div>
      </div>
    `;

    const elBid = rootContainer.querySelector('#val-best-bid') as HTMLElement;
    const elAsk = rootContainer.querySelector('#val-best-ask') as HTMLElement;
    const elSpread = rootContainer.querySelector('#val-spread') as HTMLElement;

    // Direct Reactive Bindings: Memodifikasi DOM text node langsung
    new EffectNode(() => {
      const bidVal = this.store.bestBid.get();
      elBid.textContent = bidVal.toFixed(2);
    });

    new EffectNode(() => {
      const askVal = this.store.bestAsk.get();
      elAsk.textContent = askVal.toFixed(2);
    });

    new EffectNode(() => {
      const spreadVal = this.store.spread.get();
      elSpread.textContent = spreadVal.toFixed(4);
    });
  }
}

// SIMULASI LOAD DATA WEBSOCKET
export function runSimulation() {
  const store = new OrderBookStore();
  const container = document.createElement('div');
  document.body.appendChild(container);

  const renderer = new OrderBookRenderer(store);
  renderer.mount(container);

  let p = 60000;
  // Memancarkan payload pada interval 16ms (ekivalen 60fps frame budget saturation)
  const timer = setInterval(() => {
    p += (Math.random() - 0.49) * 10;
    const mockBids: Order[] = [{ price: p - 1, size: Math.random() * 5 }];
    const mockAsks: Order[] = [{ price: p + 1, size: Math.random() * 5 }];

    store.ingestDelta(mockBids, mockAsks);
  }, 16);

  // Return cleanup mechanism
  return () => clearInterval(timer);
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Kriteria Metrik | React Context + Hooks | Flux Pattern (Redux Toolkit) | RxJS Observables | Fine-Grained Signals |
| :--- | :--- | :--- | :--- | :--- |
| **Model Reaktivitas** | Coarse-Grained (Render Push) | Push Action / Reducer Pull | Push Stream (Event-based) | Pull-Push Hybrid (Fine-Grained) |
| **Re-render Granularity** | Seluruh Sub-tree Komponen | Komponen ber-selector spesifik | Manual subscription / Operator | Langsung ke Leaf Node / Computed |
| **Footprint Memori** | Sangat Kecil (Bawaan React) | Menengah (Action/Middleware/Store)| Berat (Stream Contexts & Closures) | Sangat Ringan (Graph Linked Node) |
| **Overhead Kurva Belajar**| Rendah | Menengah (Boilerplate tinggi) | Sangat Tinggi (FRP paradigm) | Rendah ke Menengah |
| **Debugging / Tracing** | Sulit (Stale Closures, Cascade) | Sangat Baik (Time-Travel / DevTools)| Kompleks (Stack trace stream asynchronous)| Deterministik via Graph Introspection |
| **Ideal Use Case** | Theme, I18n, Low-frequency data | Transaksi Enterprise, Form Wizard | Chat, Data Feed Kompleks, WebSocket | High-Performance GUI, Visual Charts, Trading |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Cycle Dependencies (Infinite Loops)
**Kondisi Bahaya:** Node `A` bergantung pada `B`, dan dalam perjalanannya node `B` memicu penulisan kembali ke node `A`.
```typescript
// Infinite Loop Trigger:
createEffect(() => {
  const val = countSignal.get();
  countSignal.set(val + 1); // CRITICAL: Menulis ke signal yang memicu dirinya sendiri
});
```
*Mitigasi:* State Engine wajib menyertakan flag proteksi eksekusi. Jika node efek memanggil dirinya sendiri dalam frame evaluasi yang sama, engine harus melempar exception fatal: `CycleDetectedException: Reactive cycle detected across nodes`.

### 2. Conditional Dependency Tracking Drift
Jika subscriber memiliki percabangan logika seperti `a.get() ? b.get() : c.get()`, dependensi terhadap node `c` tidak boleh aktif saat `a` bernilai `true`. Jika engine tidak melakukan dynamic graph untracking, mutasi pada `c` akan memicu komputasi yang sebenarnya hasilnya tidak dipakai sama sekali oleh sistem.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Over-Subscribing via Memory Leaks
* **Kesalahan Fatal:** Menjalankan `createEffect` atau berlangganan observable di dalam lifecycle komponen yang terus me-mount ulang tanpa melakukan teardown/cleanup instance.
* **Solusi Industri:** Gunakan referensi `AbortController` atau simpan token `Dispose` yang dipanggil pada siklus lifecycle destruction (unmount) secara eksplisit.

### 2. Menggunakan Computed untuk Side Effects
* **Kesalahan Fatal:** Mengubah DOM atau memicu request HTTP di dalam body `createComputed`.
* **Solusi Industri:** Jaga `computed` murni idempotent (Pure Functions: $f(x) = y$). Gunakan `effect` untuk seluruh operasi mutasi dunia luar (*side effects*).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Normalized Flat State Structures:** Hindari objek JSON bertingkat dalam (*deep nested objects*). Pecah struktur data ke dalam kamus ID-ke-Entitas (`Record<string, Entity>`) menggunakan signal independen untuk tiap entitas agar mencegah cascade mutasi massal.
2. **Derive, Do Not Duplicate:** Jangan pernah menyimpan state di dalam store jika state tersebut dapat dikalkulasi secara matematis dari state lain. Gunakan `createComputed`. Ini mencegah invalid intermediate states.
3. **Atomic Writes via Transactional Batching:** Bungkus mutasi multipel yang terikat logika bisnis tunggal ke dalam satu eksekusi fungsi `batch()`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

* **Flat Doubly-Linked Lists over Sets:** Pada engine kelas produksi (seperti preact/signals), implementasi dependensi tidak menggunakan `Set<Subscriber>` standar karena overhead alokasi hash map JavaScript. Engine menggunakan doubly-linked list internal (`prevSub`, `nextSub`) langsung pada node pointer untuk efisiensi traversal $O(1)$ dan menghemat konsumsi memori hingga 60%.
* **Scheduler De-duplication Microtask:** Gunakan API platform modern seperti `queueMicrotask()` untuk batching alami browser, memastikan eksekusi evaluasi state tertunda hingga JavaScript execution stack kosong sebelum rAF (*requestAnimationFrame*) dieksekusi oleh layout engine browser.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Prototypes & State Pollution Mitigation:** Lindungi state container dari eksploitasi prototype pollution dengan menginisialisasi dictionary map tanpa prototipe dasar:
   ```typescript
   const stateDictionary = Object.create(null);
   ```
2. **Immutability Hardening pada Runtime Boundaries:** Lakukan pembekuan objek (*deep freeze*) pada nilai yang keluar dari store menuju boundary pihak ketiga (komponen luar) di environment development untuk mencegah mutasi langsung secara ilegal (*uncontrolled mutation*):
   ```typescript
   if (process.env.NODE_ENV !== 'production') {
     Object.freeze(payload);
   }
   ```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Sistem state engine enterprise wajib menyediakan *hooks* introspeksi global untuk memantau performa reaktivitas secara langsung:

```typescript
// Telemetry Hook Integration
interface ReactiveNodeTelemetry {
  id: string;
  type: 'SIGNAL' | 'COMPUTED' | 'EFFECT';
  executionTimeMs: number;
  dependencyCount: number;
}

export class EngineDiagnostics {
  private static onEvaluateHook: ((data: ReactiveNodeTelemetry) => void) | null = null;

  public static setObserver(fn: (data: ReactiveNodeTelemetry) => void) {
    this.onEvaluateHook = fn;
  }

  public static traceEvaluation(id: string, type: 'SIGNAL' | 'COMPUTED' | 'EFFECT', duration: number, deps: number) {
    if (this.onEvaluateHook) {
      this.onEvaluateHook({ id, type, executionTimeMs: duration, dependencyCount: deps });
    }
  }
}
```

Metrik ini dapat dikirimkan langsung ke OpenTelemetry exporter frontend untuk mendeteksi komponen mana yang memiliki durasi kalkulasi terpanjang (*Long Task blocking scripts*).

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Signal:** Primitive dasar pembawa state yang dapat dibaca dan ditulis (`get`/`set`). Menjadi produsen informasi dalam DAG.
* **Computed:** Penampung nilai turunan yang bersifat lazy, pure, idempotent, dan di-cache secara otomatis hingga dependensinya berstatus `DIRTY`.
* **Effect:** Konsumen akhir rantai DAG yang mengeksekusi *side-effects* (DOM mutasi, storage persistence) tanpa nilai kembalian.
* **Batching:** Penundaan propagasi dirty-checking dan eksekusi effect ke microtask queue untuk menghindari intermediate calculations.
* **Diamond Glitch Prevention:** Memastikan seluruh node dievaluasi dalam urutan topologis bersih sehingga UI tidak menampilkan data transitif yang rusak.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa arsitektur fine-grained reactivity berbasis Signals secara inheren lebih cepat dibanding Virtual DOM reconciliation standar pada update berfrekuensi tinggi?
* A) Karena Signal mengompilasi kode JavaScript langsung ke WebAssembly.
* B) Karena Signal mengeliminasi algoritma reconciliation pohon Virtual DOM secara total dan langsung mengeksekusi operasi mutasi pada pointer target DOM node yang terikat.
* C) Karena Signal berjalan di Web Worker terpisah sehingga bebas hambatan JavaScript main thread.
* D) Karena Signal menyimpan seluruh datanya di memori GPU.

### Soal 2
Apa yang dimaksud dengan fenomena "Diamond Dependency Problem" pada reactive graph?
* A) Kesalahan memori akibat memory leak yang berbentuk segiempat.
* B) Kegagalan membaca state karena key objek JSON terenkripsi secara asimetris.
* C) Kondisi di mana node turunan mengevaluasi data usang (*stale value*) sementara secara tidak sengaja karena memiliki dua jalur dependensi berbeda dari satu sumber signal yang sama.
* D) Masalah skalabilitas ketika store dibagi ke dalam empat micro-frontend berbeda.

### Soal 3
Kapan pemanggilan fungsi di dalam `createComputed` dieksekusi secara ideal oleh engine yang efisien?
* A) Segera saat sinyal dependensinya berubah, tanpa menunggu nilai tersebut dibaca.
* B) Setiap frame render requestAnimationFrame dieksekusi oleh browser.
* C) Secara *lazy* saat nilai computed tersebut dipanggil (`get()`) dan status flag node dependensinya terkonfirmasi `DIRTY`.
* D) Setiap kali ada aksi navigasi URL router.

### Soal 4
Apa dampak fatal jika sebuah `createEffect` melakukan mutasi ke Signal yang dibacanya sendiri di dalam body fungsi yang sama tanpa proteksi guards?
* A) Terjadi TypeError: Cannot read property of undefined.
* B) Browser mengalami infinite reactive cycle loop yang memblokir CPU execution stack hingga thread terhenti (stack overflow/browser freeze).
* C) Nilai signal akan otomatis ter-reset menjadi null.
* D) Efek secara otomatis diubah menjadi Observable RxJS oleh runtime browser.

### Soal 5
Mengapa mekanisme pembersihan dynamic dependency tracking (*untracking old dependencies*) wajib dilakukan saat computed node mengevaluasi ulang fungsinya?
* A) Agar computed node dapat di-garbage collect oleh browser setiap 5 detik.
* B) Untuk memastikan cabang logika kondisional (misal: percabangan `ternary/if-else`) yang tidak lagi aktif berhenti mengeksekusi komputasi ketika signal di cabang non-aktif tersebut berubah.
* C) Karena JavaScript engine tidak mendukung closures dengan lebih dari satu variabel.
* D) Untuk menghapus cache memori IndexedDB.

---

### Kunci Jawaban & Analisis Singkat
1. **B** — Signals tidak melakukan perbandingan komparasi struktur sub-tree virtual $O(N)$, melainkan mengeksekusi fungsi update leaf node $O(1)$ langsung ke reference target.
2. **C** — Diamond dependency menciptakan inkonsistensi sementara di mana satu simpul membaca nilai kombinasi baru dan lama secara bersamaan sebelum evaluasi selesai.
3. **C** — Pemanfaatan *lazy evaluation* membebaskan CPU dari komputasi matematis yang belum tentu ditampilkan di viewport browser.
4. **B** — Terjadi mutual recursion tak terbatas: Read -> Mutate -> Notify -> Read -> Mutate.
5. **B** — Jika tidak di-untrack, dependensi usang pada cabang yang kini tidak terpakai tetap terdaftar dan memicu recompute yang tidak bernilai guna (*wasted compute cycles*).

---

## SEKSI 20 — TANTANGAN MANDIRI & PROYEK PRAKTIKUM

### Arsitektur Tantangan: Membangun Time-Traveling Micro-State Engine
Implementasikan sebuah library state engine reaktif lengkap dengan spesifikasi teknis berikut:

1. **Persyaratan Fungsional Core:**
   * Bangun implementasi `createSignal`, `createComputed`, dan `createEffect` tanpa dependensi eksternal.
   * Sertakan implementasi fungsi `batch(fn)` yang menangani *nested batch calls* dengan aman.
2. **Mekanisme Time-Travel History:**
   * Buat class `TimeTravelStore` yang mengarsipkan setiap mutasi atomik signal ke dalam linked-list snapshot state.
   * Implementasikan method `undo()` dan `redo()` yang memundurkan/memajukan state aplikasi tanpa memicu penambahan record history baru.
3. **Deteksi Siklus (Cycle Detection Engine):**
   * Pasang mekanisme pengaman di dalam dispatcher loop: jika ada effect yang dieksekusi lebih dari 100 kali dalam satu synchronous run, batalkan proses eksekusi dan lemparkan error `CyclicDependencyException` lengkap dengan ID node yang bersalah.
4. **Uji Validasi:**
   * Buat implementasi visual sederhana (HTML native / CodeSandbox) berupa kalkulator harga e-commerce diskon multi-cabang yang memvalidasi bahwa glik/glitch visual tidak pernah terjadi saat status diskon dan kupon diubah secara bersamaan di dalam blok transaksi `batch()`.