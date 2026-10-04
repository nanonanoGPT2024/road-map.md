# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 03-Frontend-and-Mobile
### BAB-05: State Management Engines & Reactive Patterns
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta memiliki kompetensi tingkat lanjut untuk:
1. **Menganalisis & Mengkonstruksi Reactive Engine:** Membedah dan membangun mesin reaktivitas *fine-grained* berbasis Dependency Graph (DAG - *Directed Acyclic Graph*) mandiri yang *glitch-free* menggunakan algoritma *Push-Pull Synchronization*.
2. **Merancang Deterministic State Machines:** Mengimplementasikan finite state machine (FSM) dan statechart hierarki (Statecharts/Actor Model) menggunakan XState v5 untuk sistem transaksional kritis tanpa celah *illegal state transition*.
3. **Mengoptimalkan Throughput & Memori Frontend:** Menerapkan normalisasi state entitas terdistribusi tingkat lanjut, optimasi *selector memoization*, serta manajemen siklus hidup memori guna menghindari memory leaks akibat closure dan *stale subscriptions*.
4. **Mengeksekusi Arsitektur State Skala Enterprise:** Mengintegrasikan streaming data frekuensi tinggi (WebSockets/Web Workers) ke dalam UI tree tanpa memicu *reconciliation thrashing* pada Concurrent Renderer.

---

### 2. Prerequisite

Peserta wajib menguasai:
* Mekanisme JavaScript Runtime Internals: Microtask queue, Event Loop, Garbage Collection (Mark-and-Sweep, WeakMap/WeakSet), dan V8 Hidden Classes.
* TypeScript Tingkat Lanjut: Conditional Types, Template Literal Types, Mapped Types, Variadic Tuple Types, dan Type-level programming.
* Konsep State Management Dasar (Module 01): Flux architecture, unidirectional data flow, mutable vs immutable structural sharing.
* Metrik Performa Web Vitals: Interaction to Next Paint (INP), Long Animation Frames (LoAF), dan alokasi heap profil V8.

---

### 3. Concept & Internal Architecture

Arsitektur state management modern pada skala enterprise tidak lagi berkutat pada dikotomi sederhana "Redux vs Context". Di balik framework UI modern (React 19, SolidJS, Vue 3, Svelte 5) terdapat paradigma formal matematis dan rekayasa graf dependensi yang mendikte bagaimana state dihitung, dimutasi, dan dirender.

#### 3.1. Fine-Grained Reactivity Core: Dynamic Dependency Tracking & Topological Order

Reaktivitas granular (*fine-grained*) beroperasi pada level sel individual data (sering disebut *Signals* atau *Observables*), bukan pada level komponen pohon visual (VNode reconciler). Arsitektur ini dibangun di atas tiga pilar utama:
1. **Signal (Source):** Node produsen yang menyimpan nilai dasar dan daftar *subscribers*.
2. **Computed/Memo (Derivation):** Node perantara yang bertindak sebagai konsumen sekaligus produsen, merepresentasikan proyeksi murni dari satu atau lebih Signal.
3. **Effect (Sink):** Node konsumen akhir yang mengeksekusi *side-effect* terhadap lingkungan eksternal (DOM, API, Storage) ketika dependensinya berubah.

```
+-------------------------------------------------------------+
|               Push-Pull Reactivity Algorithm                |
+-------------------------------------------------------------+
 1. Mutasi (Push Phase):
    [Signal A] --(Dirty Flag)--> [Computed C] --(Dirty Flag)--> [Effect E]
         |                              |
      (Nilai Baru)               (Tandai STALE)           (Antrekan ke Scheduler)

 2. Evaluasi (Pull Phase):
    [Effect E] mengeksekusi -> Membaca [Computed C]
                                      |
                         C memeriksa: "Apakah A kotor?"
                                      |-- Ya -> Hitung ulang C
                                      |-- Tidak -> Kembalikan nilai cache
```

##### Algoritma Push-Pull & Solusi Glitch-Free
Masalah klasik dalam graf reaktif adalah **Glitch** (Diamond Problem), di mana sebuah dependensi terbagi menjadi dua jalur komputasi yang kemudian bertemu kembali pada satu *sink*. Jika evaluasi dilakukan murni secara *eager-push*, *sink* dapat membaca kombinasi state lama dan baru, menghasilkan status transisi ilegal yang berkedip di UI.

```
       [Signal A]
        /      \
    [Comp B]  [Comp C]
        \      /
       [Effect D]
```
Solusi enterprise modern menggunakan **Push-Pull 2-Phase Engine**:
* **Phase 1 (Push Notification):** Ketika Signal bermutasi, sinyal kotor (*dirty mark*) didorong ke bawah sepanjang graf dependensi secara topologis. Tidak ada kode komputasi pengguna yang dieksekusi pada fase ini. Node turunan hanya ditandai dengan flag: `STALE` (pasti berubah) atau `POSSIBLY_STALE` (bergantung pada komputasi lain).
* **Phase 2 (Pull Evaluation):** Ketika *sink* (misalnya Effect atau UI read) dipanggil oleh scheduler, ia melakukan *pull* mundur. Jika node perantara berstatus `POSSIBLY_STALE`, ia meminta parent-nya untuk menyelesaikan komputasi terlebih dahulu. Jika nilai komputasi parent tidak berubah secara struktural (`Object.is(old, new)`), node tersebut membatalkan status kotornya, menghemat evaluasi subtree di bawahnya (*early bailout*).

#### 3.2. Formal Statecharts & Actor Model Architecture

Bagi alur logika kompleks (transaksi finansial, autentikasi multi-faktor, *real-time bidding*), penggunaan state berbasis boolean primitif (`isLoading`, `hasError`, `isSuccess`) menyebabkan ledakan status ilegal (state space explosion: $2^n$ kemungkinan status untuk $n$ boolean flag).

Statecharts formal mengimplementasikan ekstensi State Machine Harel:
$$\mathcal{M} = \langle S, S_0, \Sigma, V, \delta, \mathcal{H} \rangle$$
* $S$: Himpunan status hierarki (compound) dan paralel (orthogonal).
* $\Sigma$: Himpunan kejadian (*events*).
* $V$: Himpunan data internal (*extended state* atau *context*).
* $\delta: S \times \Sigma \times \text{Guard}(V) \rightarrow S \times \text{Action}(V)$: Fungsi transisi deterministik yang dibatasi oleh penjaga kondisi (*guards*).
* $\mathcal{H}$: Mekanisme memori histori.

Dengan memodelkan UI sebagai aktor-aktor yang berkomunikasi secara asynchronous melalui *message passing*, UI terisolasi penuh dari kondisi balapan (*race condition*).

#### 3.3. Normalized Entity Store & Memory Topology

Aplikasi enterprise memanipulasi struktur data relasional (misal: Transaksi memiliki Hubungan dengan Akun, Akun memiliki Pengguna). Menyimpan data secara bersarang (*nested state*) mengakibatkan:
1. Redundansi data di berbagai cabang state tree.
2. Kesulitan pembaruan parsial yang berujung pada mutasi referensial besar-besaran (merusak shallow-equality memoizer).
3. Kompleksitas penanganan siklus referensi.

Arsitektur state enterprise menerapkan **Relational Normalization Topology**:
* State direduksi menjadi tabel-tabel datar: `byId: Record<string, Entity>` dan `allIds: Array<string>`.
* Hubungan direpresentasikan via foreign keys (ID).
* Query derivasi dikompilasi menggunakan memoized projections (Reselect/Proxy patterns) yang mempertahankan kesamaan referensial (*referential stability*) hingga granularitas atribut terkecil.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (Naive Flux/Global Store) | Enterprise Reactive & Statechart Architecture |
| :--- | :--- | :--- |
| **Model Eksekusi** | Re-render level pohon komponen dari root/branch secara menyeluruh. | Reaktivitas terfokus (*fine-grained*); pembaruan langsung ke target node DOM/Leaf. |
| **Integritas Alur** | Boolean multiplexing (`if (loading && !error)`). Rawan *race condition*. | Finite State Machine matematis. Transisi ilegal dicegah secara statis oleh compiler/runtime. |
| **Karakteristik Mutasi** | Kloning objek immutable skala masif di main thread; GC *spikes*. | Transaksi ter-batch, shallow mutation terisolasi, tracking dependensi level-properti. |
| **Skalabilitas Data** | Penurunan frame rate linier terhadap volume data WebSocket/Streaming. | Penyerapan data terisolasi via Web Worker dan Ring Buffer, merender state termutasi secara ter-batch. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur state mutakhir bekerja sebagai berikut:

```
[External Event / WebSocket]
          |
          v
[Web Worker Buffer / Deserializer]
          |
  (Offloaded Transferable ArrayBuffer)
          |
          v
[Enterprise Reactive State Engine]
          |
          +--> [FSM/Statechart Transition Engine] 
          |       | (Validasi Event & Guard Evaluation)
          |       v
          +--> [Normalized Relational Storage]
                  | (Id-indexed mutator)
                  v
[Push Phase: Topologically Sort Dirty Nodes]
          |
[Pull Phase: Memoized Derivations (Glitch-Free Resolving)]
          |
[Scheduled Atomic Batch Flush]
          |
          v
[Direct Leaf-Node DOM Mutator / Fiber Concurrent Scheduler]
```

1. **Ingestion:** Payload masif diterima di luar main-thread melalui Web Worker untuk parsing JSON.
2. **State Validation:** Event dikirimkan ke Statechart Engine. Jika state saat ini tidak mengizinkan event tersebut, event dibuang (*noop*) atau dicatat ke telemetry audit trail.
3. **Storage Mutation:** Normalizer memperbarui tabel relasional `byId` spesifik.
4. **Graph Notification:** Sinyal menandai dependensi langsung sebagai kotor. Scheduler menahan rendering hingga seluruh tick microtask selesai (*batching*).
5. **Reconciliation:** Hanya leaf node atau komponen yang langsung membaca properti yang termutasi yang akan dieksekusi ulang.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Jaringan Pipa Hidrolik vs Pabrik Fotokopi
* **Naive Rendering (Pabrik Fotokopi):** Setiap kali ada satu kata yang berubah dalam sebuah buku setebal 500 halaman, Anda memfotokopi ulang seluruh buku tersebut, membandingkan setiap halamannya dengan buku lama, lalu mengganti buku di rak perpustakaan. Ini adalah cara kerja reconciler konvensional yang tidak efisien.
* **Fine-Grained Reactivity (Jaringan Pipa Hidrolik):** Setiap nilai data adalah sebuah katup fluida. Komputasi turunan adalah pipa perantara. Ketika katup utama diputar 5 derajat, tekanan hanya mengalir ke pipa-pipa yang tersambung secara fisik ke katup tersebut, langsung menggerakkan piston akhir tanpa mengganggu bagian mesin lainnya.

#### Diagram: Resolusi Topological Glitch (Diamond Problem)
```
          +-------------+
          |  Signal A   | (Nilai: 1)
          +-------------+
             /       \
            /         \
           v           v
    +----------+   +----------+
    | Comput B |   | Comput C |
    |  (A * 2) |   |  (A + 1) |
    +----------+   +----------+
            \         /
             \       /
              v     v
           +-----------+
           | Effect D  | -> Mengamati: B + C
           +-----------+

MASALAH TANPA TOPOLOGICAL ORDER:
1. Signal A berubah: 1 -> 2
2. B dievaluasi duluan: B = 4. 
3. D langsung dievaluasi sebelum C sempat dihitung! 
   D membaca: B(baru=4) + C(lama=2) = 6 (GLITCH: Inkosisten!)
4. C dievaluasi: C = 3.
5. D dievaluasi ulang: B(4) + C(3) = 7. (D dieksekusi 2x, visual berkedip).

SOLUSI DEEP PUSH-PULL (GLITCH-FREE):
1. Signal A berubah: 1 -> 2.
2. Push Phase: Tandai B dan C sebagai STALE, tandai D sebagai STALE.
3. Scheduler memanggil D. D melakukan Pull:
   - D meminta B -> B melihat status STALE -> B recompute: 4 -> Status CLEAN.
   - D meminta C -> C melihat status STALE -> C recompute: 3 -> Status CLEAN.
4. D membaca B(4) + C(3) = 7. 
   D hanya dieksekusi TEPAT 1 KALI dengan data konsisten.
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Implementasi Core Push-Pull Fine-Grained Reactive Engine (TypeScript)

Berikut adalah implementasi minimalis sebuah Reactive Core lengkap dengan *dependency tracking*, *glitch protection*, dan *automatic cleanup*.

```typescript
// Core Types
type Subscriber = {
  execute: () => void;
  dependencies: Set<Set<Subscriber>>;
};

let activeSubscriber: Subscriber | null = null;
const batchQueue: Set<() => void> = new Set();
let isBatching = false;

export function batch(fn: () => void): void {
  const previousBatching = isBatching;
  isBatching = true;
  try {
    fn();
  } finally {
    isBatching = previousBatching;
    if (!isBatching) {
      flushBatch();
    }
  }
}

function flushBatch(): void {
  while (batchQueue.size > 0) {
    const effectsToRun = Array.from(batchQueue);
    batchQueue.clear();
    for (const run of effectsToRun) {
      run();
    }
  }
}

export class Signal<T> {
  private value: T;
  private subscribers: Set<Subscriber> = new Set();

  constructor(initialValue: T) {
    this.value = initialValue;
  }

  get(): T {
    if (activeSubscriber !== null) {
      this.subscribers.add(activeSubscriber);
      activeSubscriber.dependencies.add(this.subscribers);
    }
    return this.value;
  }

  set(newValue: T): void {
    if (Object.is(this.value, newValue)) return;
    this.value = newValue;

    for (const sub of Array.from(this.subscribers)) {
      if (isBatching) {
        batchQueue.add(sub.execute);
      } else {
        sub.execute();
      }
    }
  }
}

export function createSignal<T>(initialValue: T): [() => T, (v: T) => void] {
  const s = new Signal(initialValue);
  return [() => s.get(), (v: T) => s.set(v)];
}

export function createEffect(fn: () => void): () => void {
  const subscriber: Subscriber = {
    execute: () => {
      cleanup(subscriber);
      const prev = activeSubscriber;
      activeSubscriber = subscriber;
      try {
        fn();
      } finally {
        activeSubscriber = prev;
      }
    },
    dependencies: new Set(),
  };

  function cleanup(sub: Subscriber): void {
    for (const depSet of sub.dependencies) {
      depSet.delete(sub);
    }
    sub.dependencies.clear();
  }

  subscriber.execute();

  // Return teardown manual
  return () => cleanup(subscriber);
}

export function createComputed<T>(fn: () => T): () => T {
  const [read, write] = createSignal<T>(undefined as unknown as T);
  createEffect(() => {
    write(fn());
  });
  return read;
}
```

#### 7.2. Practical Example: Enterprise Order Execution Engine (Statechart + Normalized Store)

Implementasi sistem entri order trading institusional menggunakan Finite State Machine deterministik murni via TypeScript dan store relasional terenkapsulasi.

```typescript
// types.ts
export type OrderSide = 'BUY' | 'SELL';
export type OrderStatus = 'IDLE' | 'VALIDATING' | 'SUBMITTING' | 'EXECUTED' | 'REJECTED';

export interface OrderEntity {
  id: string;
  symbol: string;
  price: number;
  quantity: number;
  side: OrderSide;
}

export type OrderEvent =
  | { type: 'SET_SYMBOL'; payload: string }
  | { type: 'SET_METRICS'; payload: { price: number; quantity: number } }
  | { type: 'SUBMIT' }
  | { type: 'API_SUCCESS'; payload: { orderId: string } }
  | { type: 'API_ERROR'; payload: { reason: string } }
  | { type: 'RESET' };

export interface MachineContext {
  symbol: string;
  price: number;
  quantity: number;
  lastOrderId: string | null;
  errorMessage: string | null;
}

// Engine Implementation
export class OrderStateMachine {
  private currentState: OrderStatus = 'IDLE';
  private context: MachineContext = {
    symbol: '',
    price: 0,
    quantity: 0,
    lastOrderId: null,
    errorMessage: null,
  };

  private listeners: Set<(state: OrderStatus, ctx: MachineContext) => void> = new Set();

  public getState(): OrderStatus {
    return this.currentState;
  }

  public getContext(): Readonly<MachineContext> {
    return Object.freeze({ ...this.context });
  }

  public subscribe(fn: (state: OrderStatus, ctx: MachineContext) => void): () => void {
    this.listeners.add(fn);
    fn(this.currentState, this.getContext());
    return () => this.listeners.delete(fn);
  }

  private notify(): void {
    const frozenCtx = this.getContext();
    for (const listener of this.listeners) {
      listener(this.currentState, frozenCtx);
    }
  }

  // Pure State Transition Function
  public transition(event: OrderEvent): void {
    const prevState = this.currentState;

    switch (this.currentState) {
      case 'IDLE':
      case 'REJECTED': {
        if (event.type === 'SET_SYMBOL') {
          this.context.symbol = event.payload;
          this.context.errorMessage = null;
        } else if (event.type === 'SET_METRICS') {
          this.context.price = event.payload.price;
          this.context.quantity = event.payload.quantity;
          this.context.errorMessage = null;
        } else if (event.type === 'SUBMIT') {
          // Guard Evaluation
          if (!this.context.symbol || this.context.price <= 0 || this.context.quantity <= 0) {
            this.currentState = 'REJECTED';
            this.context.errorMessage = 'Parameter order tidak valid (Symbol, Price, atau Quantity).';
          } else {
            this.currentState = 'VALIDATING';
            this.notify();
            this.executeAsyncValidationAndSubmit();
            return;
          }
        }
        break;
      }

      case 'VALIDATING': {
        // Transition internal async diproteksi dari event eksternal
        if (event.type === 'API_SUCCESS') {
          this.currentState = 'EXECUTED';
          this.context.lastOrderId = event.payload.orderId;
        } else if (event.type === 'API_ERROR') {
          this.currentState = 'REJECTED';
          this.context.errorMessage = event.payload.reason;
        }
        break;
      }

      case 'EXECUTED': {
        if (event.type === 'RESET') {
          this.currentState = 'IDLE';
          this.context = {
            symbol: '',
            price: 0,
            quantity: 0,
            lastOrderId: null,
            errorMessage: null,
          };
        }
        break;
      }

      default:
        break;
    }

    if (prevState !== this.currentState || event.type.startsWith('SET_')) {
      this.notify();
    }
  }

  private async executeAsyncValidationAndSubmit(): Promise<void> {
    try {
      // Simulasi Latency Network & API Gateway Gatekeeper
      await new Promise((resolve) => setTimeout(resolve, 300));
      
      // Simulasi Kondisi Random Failure
      if (this.context.price * this.context.quantity > 10_000_000) {
        throw new Error('Margin limit exceeded! Maximum exposure: $10,000,000');
      }

      const generatedId = `ORD-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      this.transition({ type: 'API_SUCCESS', payload: { orderId: generatedId } });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown Transmission Error';
      this.transition({ type: 'API_ERROR', payload: { reason: msg } });
    }
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem: Terminal Trading B2B Global (LMAX / Bloomberg Web-Terminal Equivalent)
* **Metrik Beban:** 8.000 order book ticks/detik via binary WebSocket connection (ArrayBuffer encoded Protobuf).
* **Masalah Kritis:** Main-thread React 18 mengalami frame drop akut (FPS drop ke 7-12 FPS). Interaksi input order macet (*input latency* hingga 450ms, INP gagal total), diakibatkan oleh *Redux dispatch serialisation* yang menumpuk di Task Queue, memaksa VNode tree di-reconcile secara berlebihan.

```
ARSITEKTUR LAMA (MONOLITHIC STORE / BOTTLENECK):
[WebSocket] 
    |
(8000 actions/detik)
    v
[Redux Dispatcher] -> [Single Large Reducer] -> [Global State Tree Mutation]
                                                      |
                                            (React Root Re-render)
                                                      |
                                      [Main Thread JANK / 10 FPS]

ARSITEKTUR SOLUSI (DECOUPLED HYBRID SIGNAL-ACTOR ENGINE):
[WebSocket] 
    |
(Binary ArrayBuffer)
    v
[Dedicated Web Worker] === (Ring Buffer / Batch 50ms) ===> [Main Thread Signal Bridge]
                                                                |
                                             +------------------+------------------+
                                             |                                     |
                                   (High-Freq Price Ticks)               (Low-Freq Order State)
                                             |                                     |
                                  [Fine-Grained DOM Sinks]           [Order Statechart Machine]
                               (Direct Canvas/Text Node Update)       (Deterministic Validation)
                                   (Zero React Tree Diffing)               (UI Form Only)
```

#### Solusi Arsitektural:
1. **Thread Isolation via Web Worker:** Parsing biner ditangani penuh oleh *Web Worker*. Worker menggunakan Ring Buffer terstruktur dan mengirimkan *window snapshot* terkompresi setiap 50ms (20fps tick rate, bukan 8000 raw frames) ke UI layer.
2. **Bypass Virtual DOM untuk High-Frequency Leaf Nodes:** Metrik harga (*L1/L2 Market Depth*) dialihkan dari React Component Tree ke node Signals mandiri yang langsung beroperasi pada `textContent` DOM nodes atau `HTMLCanvasElement` kontekstual menggunakan *Direct Reactive Mount*.
3. **Actor-Engine Boundary:** Input order milik user ditempatkan pada FSM terisolasi yang tidak pernah berlangganan (*unsubscribe*) terhadap tick buku harga global, menjamin responsivitas UI input order pada latency < 16ms.

---

### 9. Trade-offs

| Paradigma | Throughput Kecepatan Mutasi | Beban Memori Heap | Kompleksitas Mental & Maintenance | Debuggability & Time-Travel |
| :--- | :--- | :--- | :--- | :--- |
| **Fine-Grained Signals (Solid/Custom)** | **Sangat Tinggi** (O(1) direct update ke pointer dependensi). | **Tinggi** (Overhead ribuan objek dependensi graph dan closure subscription). | **Sedang** (Memerlukan pemahaman tracking context implisit). | **Rendah** (Sulit merekam global snapshot; pelacakan mutasi non-linear). |
| **Immutable Reducers (Redux/Zustand)** | **Rendah - Sedang** (O(N) tree shallow copying, GC thrashing). | **Sangat Rendah** (Struktur data plain object, mudah dibersihkan GC). | **Rendah** (Alur data searah eksplisit, fungsi murni mudah dipahami). | **Sangat Tinggi** (Deterministic log events, time-travel native, snapshot trivial). |
| **Hierarchical Statecharts (XState)** | **Sedang** (Overhead transisi state formal dan guard checks). | **Sedang** (Penyimpanan konfigurasi mesin dan machine instances). | **Tinggi** (Kurva belajar tinggi, butuh spesifikasi diagram formal). | **Sangat Tinggi** (Alur eksekusi terekam dalam diagram matematis deterministik). |
| **Transparent Mutable Proxy (MobX/Valtio)** | **Tinggi** (Tracking otomatis via proxy trap interception). | **Tinggi** (Proxy wrapper per objek dan metadata listener arrays). | **Rendah** (Berperilaku seperti JavaScript biasa). | **Sedang** (Mutasi implisit menyulitkan identifikasi sumber trigger). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Memory Leaks Melalui Dangling Subscriptions
* **Penyebab:** Computed Signals atau Effects mendaftarkan referensi ke Signal berumur panjang (misal: Global User Session Signal), namun komponen UI lokal tempat effect tersebut dibuat telah di-*unmount*. Akibatnya, Garbage Collector tidak dapat mereklamasi memori komponen karena referensi kuat (*strong reference*) yang tertahan di daftar `subscribers` milik Global Signal.
* **Solusi/Deteksi:** Gunakan `WeakRef` untuk referensi dependensi jika siklus hidup tidak terikat, atau terapkan disiplin *Explicit Disposal/AbortController Pattern*. Pantau alokasi Retained Size pada Chrome DevTools Memory Heap Snapshot (cari konstruktor `Subscriber` atau `Closure`).

#### 10.2. The Diamond Dependency Glitch
* **Penyebab:** Menghitung ulang derivasi turunan sebelum seluruh node induk dalam lintasan topologi selesai dievaluasi, memunculkan kondisi inkonsisten sementara.
* **Solusi:** Gunakan sistem flag penandaan dua tahap (*Push Dirty Status*, lalu *Pull with Dynamic Topological Memoization*). Jangan pernah mengeksekusi komputasi pengguna langsung pada fase *Setter Push*.

#### 10.3. Over-Normalization Selector Cascading
* **Penyebab:** Memecah entitas menjadi relasi yang terlalu granular sehingga untuk merender satu baris tabel sederhana diperlukan puluhan pemanggilan selector gabungan (*joins*).
* **Solusi:** Terapkan strategi *denormalisasi terkontrol* (*Read-Optimized Projections*) untuk view yang membutuhkan throughput tinggi.

---

### 11. Best Practices (Production Checklist)

- [ ] **State Boundary Segregation:** Pisahkan state menjadi 4 strata tegas: *Server Cache State* (TanStack Query), *Client Form/Transient State* (Local UI), *Global Relational State* (Normalized Core), dan *High-Frequency Streaming State* (Direct Signal/Worker).
- [ ] **Deterministic Event Typing:** Seluruh event pada State Machine wajib menggunakan discriminated union dengan tipe literal diskrit (`type: 'CONTEXT_ACTION'`), bukan string sembarang.
- [ ] **Structural Sharing Sanitization:** Pastikan mutasi immutable menggunakan structural sharing murni. Jangan gunakan `JSON.parse(JSON.stringify(state))` yang memotong referensi identik dan menghancurkan efisiensi memoizer.
- [ ] **Selector Memory Boundaries:** Seluruh memoized selector yang menerima argumen dinamis (misal: ID) wajib dibatasi menggunakan Cache LRU (*Least Recently Used*) untuk menghindari kebocoran memori tak terbatas.
- [ ] **Off-Main-Thread Processing:** Parsing JSON dari WebSocket berukuran > 50KB wajib dieksekusi di Web Worker menggunakan `Transferable Objects` (misal: `ArrayBuffer`).
- [ ] **Automated FSM Exhaustiveness Testing:** Buat test case berbasis model (*Model-Based Testing*) yang mengeksekusi seluruh kemungkinan kombinasi transisi status untuk mendeteksi *deadlock state*.

---

### 12. Hands-on Practice

Implementasikan pipeline reaktif streaming lokal di folder workspace berikut: `hands-on/m02/`

#### Langkah 1: Inisialisasi Arsitektur Workspace
Buat struktur direktori:
```bash
mkdir -p hands-on/m02/src/{core,workers,ui}
cd hands-on/m02
npm init -y
npm install typescript @types/node --save-dev
npx tsc --init
```

#### Langkah 2: Buat Reactive Ring Buffer Stream Adapter
Simpan pada `hands-on/m02/src/core/StreamBuffer.ts`:
```typescript
export class StreamBuffer<T> {
  private buffer: T[];
  private capacity: number;
  private head: number = 0;
  private tail: number = 0;
  private isFull: boolean = false;

  constructor(capacity: number) {
    this.capacity = capacity;
    this.buffer = new Array<T>(capacity);
  }

  public push(item: T): void {
    this.buffer[this.head] = item;
    if (this.isFull) {
      this.tail = (this.tail + 1) % this.capacity;
    }
    this.head = (this.head + 1) % this.capacity;
    this.isFull = this.head === this.tail;
  }

  public flush(): T[] {
    if (this.head === this.tail && !this.isFull) return [];
    
    const items: T[] = [];
    let current = this.tail;
    while (current !== this.head || (this.isFull && items.length === 0)) {
      items.push(this.buffer[current]);
      current = (current + 1) % this.capacity;
      if (current === this.head) break;
    }
    this.head = 0;
    this.tail = 0;
    this.isFull = false;
    return items;
  }
}
```

#### Langkah 3: Integrasikan Main-Thread Worker Mock Consumer
Simpan pada `hands-on/m02/src/ui/app.ts`:
```typescript
import { StreamBuffer } from '../core/StreamBuffer.js';
import { createSignal, createEffect, batch } from './reactive-core.js'; // Dari 7.1

interface MarketTick {
  price: number;
  timestamp: number;
}

const buffer = new StreamBuffer<MarketTick>(100);
const [latestPrice, setLatestPrice] = createSignal<number>(0);
const [tickCount, setTickCount] = createSignal<number>(0);

// Effect memantau DOM
createEffect(() => {
  console.log(`[UI UPDATE] Latest Price: $${latestPrice().toFixed(2)} | Total Processed: ${tickCount()}`);
});

// Simulasi WebSocket Tick Ingestion
setInterval(() => {
  buffer.push({
    price: 50000 + (Math.random() * 200 - 100),
    timestamp: Date.now(),
  });
}, 5);

// Flush Scheduler (20fps - 50ms)
setInterval(() => {
  const ticks = buffer.flush();
  if (ticks.length === 0) return;

  batch(() => {
    const last = ticks[ticks.length - 1];
    setLatestPrice(last.price);
    setTickCount(tickCount() + ticks.length);
  });
}, 50);
```

Jalankan transpilasi dan eksekusi menggunakan Node runtime untuk melihat kestabilan batch rendering:
```bash
npx tsc
node src/ui/app.js
```

---

### 13. Exercise

#### Level: Easy
Implementasikan fungsi `untrack(fn: () => T): T` pada Core Signal Engine di Section 7.1. Primitif ini harus mengeksekusi operasi pembacaan nilai Signal di dalam blok `fn` tanpa mendaftarkan `activeSubscriber` yang sedang berjalan ke dalam daftar dependensi sinyal tersebut.

#### Level: Medium
Rancang sebuah `NormalizedEntityAdapter<T extends { id: string }>` generik yang menyediakan antarmuka:
* `upsertMany(entities: T[]): void`
* `selectById(id: string): () => T | undefined`
* `removeOne(id: string): void`
Pastikan fungsi `selectById` mengembalikan Signal yang hanya memicu efek jika nilai entitas dengan ID tersebut mengalami perubahan data nyata (*deep/shallow equality check*).

#### Level: Hard
Kembangkan subsistem rekonsiliasi state lintas tab (*cross-tab state synchronizer*) menggunakan `BroadcastChannel` API dan algoritma **Lamport Timestamps**. Jika terjadi mutasi state paralel di Tab A dan Tab B dalam waktu bersamaan, engine harus mampu mendeteksi konflik dan mengaplikasikan *Last-Write-Wins (LWW)* secara konsisten di kedua tab tanpa menyebabkan *infinite sync broadcast loop*.

---

### 14. Challenge

**Studi Kasus:** Rancang Arsitektur Mesin Offline-First Multi-Document Workspace (seperti Miro/Figma light).

**Kebutuhan Sistem:**
1. Pengguna dapat mengubah atribut objek visual (koordinat x, y, warna, rotasi) pada canvas lokal dengan frekuensi 60fps (drag-and-drop) tanpa lag.
2. Setiap operasi mutasi harus dicatat sebagai aksi reversibel (*Undo/Redo Command Pattern*) dengan konsumsi memori hemat (*structural delta compression*, bukan kloning kanvas utuh).
3. Koneksi jaringan bersifat unreliable. Ketika koneksi terputus (*offline*), seluruh aksi di-buffer ke dalam IndexedDB. Saat koneksi pulih, sistem mengeksekusi sinkronisasi deterministik terhadap server. Jika ada konflik konkuren dari kolaborator lain, terapkan resolusi berbasis FSM.
4. **Target Evaluasi:** Anda wajib menuliskan skema State Machine formal, desain Normalized Storage untuk jutaan elemen vektor, dan algoritma Push-Pull reactivity custom yang membatasi re-render kanvas hanya pada koordinat *Bounding Box* objek yang sedang berubah.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa akar penyebab terjadinya fenomena *Glitch* (Diamond Dependency Problem) pada sistem reaktif naif?
2. Mengapa struktur `WeakMap` lebih disukai dibandingkan `Map` standar dalam implementasi dependency injection/tracking reactivity engine?
3. Sebutkan kelemahan utama dari struktur *deep nested state tree* dalam implementasi unidirectional data flow!
4. Apa peran dari fungsi penjaga (*Guard*) dalam Finite State Machine formal?
5. Mengapa pengelompokan mutasi (*batching*) ke dalam microtask queue penting bagi performa rendering browser?

#### Pertanyaan Intermediate
6. Jelaskan perbedaan mendasar siklus komputasi antara paradigma *Eager Evaluation* dan *Push-Pull (Lazy) Derivation* pada Signals!
7. Bagaimana cara mencegah *infinite reactive loops* yang terjadi ketika sebuah `Effect` secara tidak sengaja memodifikasi `Signal` yang dibacanya sendiri di dalam blok kodenya?
8. Kapan penggunaan Normalized Entity Store justru menurunkan performa aplikasi dibandingkan menggunakan denormalized local state?
9. Bagaimana isolasi state berbasis Actor Pattern mencegah masalah *race condition* pada pemanggilan data asynchronous paralel?
10. Bagaimana V8 JavaScript Engine memperlakukan *dynamic property deletion* (`delete obj[id]`) pada normalized dictionary, dan bagaimana pola pengosongan properti yang ramah performa mesin virtual?

#### Skenario Kasus Produksi
11. **Kasus 1:** Sebuah aplikasi dashboard monitoring performa server menampilkan 50 grafik real-time. Setiap 2 detik, grafik diperbarui. Pengguna melaporkan bahwa setelah membuka tab browser selama 3 jam, memory consumption meningkat dari 150MB ke 2.8GB hingga tab mengalami *Out of Memory (OOM)* crash. Langkah apa yang Anda ambil untuk mengidentifikasi baris kode/objek penyebab, dan arsitektur apa yang harus diperbaiki?
12. **Kasus 2:** Pada form checkout e-commerce berskala enterprise, user menekan tombol "Bayar Sekarang" dua kali secara sangat cepat (*double click*) dalam latensi 120ms sebelum server sempat merespons. Sistem memproses dua transaksi penagihan kartu kredit sekaligus. Bagaimana Anda menyelesaikan masalah ini secara absolut di level arsitektur state frontend tanpa bergantung pada disable visual tombol HTML saja?
13. **Kasus 3:** Tim Anda bermigrasi dari state management berbasis Redux monolith ke fine-grained Signals. Setelah migrasi, tim menemukan bahwa CPU usage melonjak tinggi saat inisialisasi aplikasi awal (Cold Start), meskipun performa interaksi (INP) meningkat pesat. Analisis penyebab struktural dari masalah ini dan berikan solusinya!

---

### 16. Summary

1. **Paradigma Fine-Grained vs Virtual DOM Reconciliation:** Fine-grained reactivity mentransformasikan pengelolaan dependensi dari evaluasi pohon komponen visual yang boros komputasi menjadi graf dependensi terarah (DAG) tingkat sel. Hasilnya, mutasi data dapat langsung diarahkan ke leaf node yang relevan dengan kompleksitas mutasi $O(1)$.
2. **Kestabilan Sistem via Deterministic Statecharts:** Penggunaan representasi boolean flag majemuk merupakan anti-pattern enterprise. Mengganti variabel status acak dengan Finite State Machines (FSM) formal memastikan bahwa transisi ilegal tidak mungkin dieksekusi oleh UI layer, memutus seluruh potensi kondisi balapan (*race condition*) secara deterministik.
3. **Pemisahan Jalur Eksekusi (Compute vs Render):** Pada beban data frekuensi tinggi (streaming/ticks), data mentah harus diproses di luar main-thread (Web Worker), difilter menggunakan *Ring Buffers*, dan disalurkan ke DOM melalui microtask scheduler yang ter-batch secara ketat guna menjaga *Interaction to Next Paint (INP)* tetap di bawah ambang batas kritis 200ms.