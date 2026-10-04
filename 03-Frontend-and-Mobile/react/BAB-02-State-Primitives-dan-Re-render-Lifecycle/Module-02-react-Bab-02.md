# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: State Primitives dan Re-render Lifecycle**  
**Kategori: 03-Frontend-and-Mobile / react**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Internal Fiber Node & Reconciliation**: Mengurai struktur internal Fiber node (`memoizedState`, `updateQueue`, `lanes`) dan merekonstruksi bagaimana React mengalokasikan prioritas serta menjadwalkan siklus render.
2. **Menguasai Mekanisme Batching & State Transitions**: Mengontrol secara deterministik kapan React melakukan *automatic batching* dan kapan harus menginterupsi antrean eksekusi menggunakan `flushSync` atau `startTransition`.
3. **Mencegah State Tearing & Race Condition**: Mengimplementasikan custom external store yang aman dari fenomena *state tearing* di bawah lingkungan Concurrent Mode menggunakan primitive `useSyncExternalStore`.
4. **Mendesain Arsitektur State Skala Enterprise**: Membangun sistem state management mikro berbasis *selector-based subscriptions* dan *fine-grained reactivity* yang meminimalkan cascading re-render pada aplikasi berfrekuensi update tinggi (60 FPS).
5. **Melakukan Profiling & Eliminasi Render Bottleneck**: Mengidentifikasi *wasted renders*, *unstable hook dependencies*, dan *render phase side-effects* melalui React Profiler API dan Chromium Tracing.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **JavaScript Core & Runtime**: Event loop, Microtasks (`Promise`, `queueMicrotask`), Macrotasks (`setTimeout`, I/O), WeakMap/WeakSet, Closures, dan ES Modules.
- **TypeScript Advanced Types**: Generics, Discriminated Unions, Type Invariants, dan Index Signatures.
- **React Fundamental**: Lifecycle komponen fungsional, aturan dasar Hooks, sintaks JSX, dan konsep immutability data structures.

---

## 3. Concept & Internal Architecture

### 3.1 Struktur Data Fiber Node dan State Primitives

React tidak menyimpan state langsung di dalam instance fungsi komponen. State dialokasikan sebagai linked list berurutan pada properti `memoizedState` dari objek `FiberNode`.

```
FiberNode
  ├── tag: WorkTag (FunctionComponent, HostComponent, etc.)
  ├── type: ComponentFunction
  ├── stateNode: any
  ├── return: FiberNode | null (Parent)
  ├── child: FiberNode | null (First Child)
  ├── sibling: FiberNode | null (Next Sibling)
  ├── alternate: FiberNode | null (WorkInProgress <-> Current)
  ├── lanes: Lanes (Bitmask Prioritas Rendering)
  └── memoizedState: Hook
        ├── memoizedState: any (Nilai aktual state)
        ├── baseState: any
        ├── baseQueue: Update | null
        ├── queue: UpdateQueue | null
        └── next: Hook | null (Hook berikutnya)
```

Setiap pemanggilan hook (`useState`, `useReducer`, `useRef`, `useMemo`) mengeksekusi operasi traversal pada linked list ini. Urutan pemanggilan hook mendikte indeks node dalam rantai `memoizedState`. Inilah fondasi matematis dari aturan: *Do not call Hooks inside loops, conditions, or nested functions*.

### 3.2 Dual Buffering Engine

React memelihara dua pohon Fiber secara simultan untuk menghindari mutasi UI yang tidak tuntas:
1. **`current`**: Merepresentasikan state pohon yang sedang aktif di-render pada layar (DOM).
2. **`workInProgress` (WIP)**: Pohon alternatif yang dialokasikan di memori latar belakang untuk menghitung kalkulasi render baru tanpa memblokir thread UI.

```
       Current Tree                       WorkInProgress Tree
   [ Fiber: App (v1) ]  <--- alternate ---> [ Fiber: App (v2) ]
           |                                       |
           v                                       v
  [ Fiber: Child (v1) ] <--- alternate ---> [ Fiber: Child (v2) ]
```

Ketika proses komputasi render selesai dan pohon siap, React mengalihkan pointer root:
$$\text{FiberRoot.current} \leftarrow \text{workInProgress}$$
Operasi atomic pointer swap ini memastikan frame drop dapat dihindari saat komputasi berlangsung berat.

### 3.3 Anatomi UpdateQueue dan Siklus Penggabungan State

Setiap dispatch aksi pada `useState` atau `useReducer` menciptakan objek `Update` yang dimasukkan ke dalam antrean sirkular (`circular linked list`):

```typescript
type Update<S, A> = {
  lane: Lane;
  action: A;
  hasEagerState: boolean;
  eagerState: S | null;
  next: Update<S, A>;
};
```

Pada fase render berikutnya, React melakukan *replay* terhadap antrean update ini:
1. Mengevaluasi apakah `update.lane` memiliki prioritas yang cukup di dalam render lane yang sedang berjalan.
2. Jika prioritas cukup, `update.action` diproses menghasilkan state baru.
3. Jika prioritas tidak cukup, update di-*skip*, dan state tersebut disimpan di `baseQueue` untuk dihitung ulang pada render pass berikutnya dengan menjaga urutan konsistensi (*causal consistency*).

### 3.4 Lane Priority Model (Bitmask Architecture)

React merepresentasikan prioritas rendering menggunakan 31-bit integers (*Bitmask Lanes*). Model ini menggantikan sistem prioritas sekuensial (seperti format ekspektasi integer klasik 1, 2, 3...) guna mendukung multi-priority interleaving.

```
Total Lanes: 0b0000000000000000000000000000001
             SyncLane (0b0000000000000000000000000000001) - Click, Keypress
             InputContinuousLane (0b0000000000000000000000000000010) - Scroll, MouseMove
             DefaultLane (0b0000000000000000000000000010000) - Data Fetching
             TransitionLane (0b0000000000000000000100000000000) - useTransition
             IdleLane (0b0100000000000000000000000000000) - Offscreen Work
```

Dengan bitmask, React dapat melakukan evaluasi gabungan prioritas secara instan via bitwise operations:
```c
bool hasIntersection = (workInProgressLanes & renderLanes) !== 0;
```

---

## 4. Why & What

| Dimensi | Paradigma Naif (Direct Virtual DOM Diff) | Paradigma Fiber Architecture (React Modern) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Stack-based, sinkron, rekursif, non-interruptible. | Task-based, asinkron, linked list traversal, fully interruptible. |
| **Manajemen Frame** | Memblokir Main Thread jika sub-tree besar membutuhkan diffing > 16.67ms. | Cooperative Scheduling via `MessageChannel` / `requestIdleCallback`. |
| **State Batching** | Terbatas pada React Synthetic Events (React 17 ke bawah). | **Automatic Batching** di seluruh Promises, Timeouts, dan Native Events. |
| **Sinkronisasi Data** | Rentan terhadap *tearing* saat konkurensi diakses oleh external store. | Garansi isolasi mutasi data via `useSyncExternalStore`. |
| **State Priority** | FIFO (First-In, First-Out). Semua update dianggap sama penting. | Priority Inversion Handling via Lanes (UI responsive selalu mendahului fetch data). |

### Mengapa State Primitive Khusus Diperlukan?
1. **`useState` / `useReducer`**: Mengikat mutasi state dengan lifecycle Fiber, memicu re-render, mengintegrasikan update ke antrean scheduler.
2. **`useRef`**: Bertindak sebagai *escape hatch* yang persist secara memori lintas render tanpa mengaktifkan reconciliation cycle.
3. **`useSyncExternalStore`**: Menjamin pembacaan sinkron dari sumber data eksternal di luar arsitektur React, mencegah komponen membaca dua versi state yang berbeda dalam satu siklus render tunggal (*tearing*).

---

## 5. How (Workflow Detail)

Alur internal komputasi pembaruan state hingga selesai digambar ke layar:

```
[Trigger Phase]
       |
  dispatchAction() dipanggil
       |
  Hitung Eager State: State berubah? (Object.is)
       ├── TIDAK ──> Batal (Bailout / No-op)
       └── YA
            |
  Alokasikan Lane ke Fiber (misal: SyncLane atau TransitionLane)
       |
  Jadwalkan Root Scheduler (scheduleUpdateOnFiber)
       |
[Render Phase - Asynchronous & Interruptible]
       |
  Fiber Work Loop: Traversal WorkInProgress Tree
       |
  Eksekusi Komponen: Hook dipanggil ulang
       |
  Proses Hook UpdateQueue -> Hasilkan State Baru
       |
  Reconciliation: Bandingkan WIP Node vs Current Node
       |
  Tandai Effect Flags (Placement, Update, Deletion)
       |
[Commit Phase - Synchronous & Non-Interruptible]
       |
  1. Before Mutation Phase: Baca snapshot DOM (getSnapshotBeforeUpdate)
       |
  2. Mutation Phase: Mutasi Real DOM Node, detach Fiber lama
       |
  3. Swap Pointer: FiberRoot.current = WorkInProgress
       |
  4. Layout Phase: Eksekusi useLayoutEffect secara blocking
       |
  Browser Paint: Tampilan ter-render di monitor pengguna
       |
  5. Passive Phase: Eksekusi useEffect secara asinkron
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Git Branching & Staging
Bayangkan React bekerja layaknya arsitektur Git:
- **`current` tree** adalah branch `main` yang ter-deploy langsung di production server (DOM).
- **`workInProgress` tree** adalah fitur baru yang sedang di-develop di branch `staging`.
- Saat Anda memanggil `setState`, Anda membuat `commit` baru ke branch `staging`.
- Anda bisa menambahkan komit lain (eksekusi hook berikutnya) atau membatalkan komit jika ada pekerjaan berprioritas tinggi dari *hotfix* (`SyncLane`).
- Setelah seluruh review kode selesai (`Render Phase` valid), branch `staging` di-merge secara instan ke `main` via `fast-forward` (`Commit Phase Pointer Swap`).

### Diagram Antrean Hook pada Fiber Node

```
  FiberNode.memoizedState
            │
            ▼
    ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
    │     Hook 1    │        │     Hook 2    │        │     Hook 3    │
    │  (useState)   │───────>│  (useEffect)  │───────>│   (useRef)    │
    ├───────────────┤  next  ├───────────────┤  next  ├───────────────┤
    │ memoizedState:│        │ memoizedState:│        │ memoizedState:│
    │   { count: 0 }│        │  { create:.. }│        │ {current: DOM}│
    │               │        │               │        │               │
    │ queue:        │        │ queue: null   │        │ queue: null   │
    │   UpdateRing  │        │               │        │               │
    └───────┬───────┘        └───────────────┘        └───────────────┘
            │
            ▼
    ┌───────────────┐
    │  Update Node  │
    │  action: c=>c1│
    │  lane: 1      │
    │  next: ───────┼──┐ (Circular pointer balik ke Update pertama)
    └───────────────┘  │
            ▲          │
            └──────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Analisis Stale Closure & Queued State

Contoh fundamental ini mendemonstrasikan bagaimana antrean update sirkular menangani update berantai vs mutasi closure lama.

```typescript
import React, { useState } from 'react';

export const CounterEngine: React.FC = () => {
  const [count, setCount] = useState<number>(0);

  const handleIncorrectBatch = () => {
    // BUG: Ketiganya membaca closure variabel 'count' yang sama (0)
    setCount(count + 1); // target: 0 + 1
    setCount(count + 1); // target: 0 + 1
    setCount(count + 1); // target: 0 + 1
    // Hasil Akhir: 1, bukan 3.
  };

  const handleCorrectQueue = () => {
    // Solusi: Menggunakan updater function yang mengonsumsi antrean internal
    setCount((prev) => prev + 1); // Enqueue: (c_0) => c_0 + 1
    setCount((prev) => prev + 1); // Enqueue: (c_1) => c_1 + 1
    setCount((prev) => prev + 1); // Enqueue: (c_2) => c_2 + 1
    // Hasil Akhir: 3.
  };

  return (
    <div className="p-4 border rounded shadow-sm">
      <h3 className="text-lg font-bold">Counter: {count}</h3>
      <button 
        onClick={handleIncorrectBatch}
        className="mr-2 px-3 py-1 bg-red-600 text-white rounded"
      >
        Mutasi Closure Salah
      </button>
      <button 
        onClick={handleCorrectQueue}
        className="px-3 py-1 bg-green-600 text-white rounded"
      >
        Mutasi Antrean Benar
      </button>
    </div>
  );
};
```

---

### 7.2 Practical Example: Enterprise Reactive Micro-Store Tanpa Library Eksternal

Implementasi store state reaktif berperforma tinggi yang mematuhi standar konkurensi React menggunakan primitive `useSyncExternalStore`. Store ini mendukung *fine-grained selector* untuk mengeliminasi cascading re-renders pada sub-tree.

```typescript
import React, { useSyncExternalStore, useCallback, useRef } from 'react';

// --- FRAMEWORK-AGNOSTIC CORE ENGINE ---

type Listener = () => void;

export class ObservableStore<TState extends Record<string, any>> {
  private state: TState;
  private listeners: Set<Listener> = new Set();

  constructor(initialState: TState) {
    this.state = Object.freeze({ ...initialState });
  }

  public getState = (): TState => {
    return this.state;
  };

  public setState = (partial: Partial<TState> | ((prevState: TState) => Partial<TState>)): void => {
    const nextPartial = typeof partial === 'function' ? partial(this.state) : partial;
    const nextState = Object.freeze({
      ...this.state,
      ...nextPartial,
    });

    if (Object.is(this.state, nextState)) {
      return; // Bailout awal jika referensi identik
    }

    this.state = nextState;
    this.listeners.forEach((listener) => listener());
  };

  public subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
}

// --- REACT HOOK BRIDGE DENGAN SELEKTOR AMAN ---

export function useStoreSelector<TState extends Record<string, any>, TSelected>(
  store: ObservableStore<TState>,
  selector: (state: TState) => TSelected,
  isEqual: (a: TSelected, b: TSelected) => boolean = Object.is
): TSelected {
  const lastSelectedStateRef = useRef<TSelected | undefined>(undefined);

  const getSelection = useCallback(() => {
    const nextSelected = selector(store.getState());
    if (
      lastSelectedStateRef.current !== undefined &&
      isEqual(lastSelectedStateRef.current, nextSelected)
    ) {
      return lastSelectedStateRef.current;
    }
    lastSelectedStateRef.current = nextSelected;
    return nextSelected;
  }, [store, selector, isEqual]);

  return useSyncExternalStore(
    store.subscribe,
    getSelection,
    getSelection // Fallback untuk Server-Side Rendering (SSR)
  );
}

// --- PENGGUNAAN PRODUKSI ---

interface UserSessionState {
  username: string;
  theme: 'light' | 'dark';
  metrics: {
    notificationsCount: number;
    latencyMs: number;
  };
}

export const sessionStore = new ObservableStore<UserSessionState>({
  username: 'Alex_Architect',
  theme: 'dark',
  metrics: {
    notificationsCount: 4,
    latencyMs: 42,
  },
});

export const DisplayThemeOnly: React.FC = () => {
  // Komponen ini HANYA me-render ulang jika properti `theme` bermutasi
  const theme = useStoreSelector(
    sessionStore,
    useCallback((s) => s.theme, [])
  );

  console.log('[RENDER] Theme Component');
  return <div className="p-2 border">Active Theme: {theme}</div>;
};

export const DisplayNotificationsOnly: React.FC = () => {
  // Komponen ini HANYA me-render ulang jika count berubah
  const count = useStoreSelector(
    sessionStore,
    useCallback((s) => s.metrics.notificationsCount, [])
  );

  console.log('[RENDER] Notification Component');
  return <div className="p-2 border">Notifications: {count}</div>;
};

export const ControlPanel: React.FC = () => {
  return (
    <div className="p-4 flex gap-2">
      <button
        onClick={() =>
          sessionStore.setState((prev) => ({
            theme: prev.theme === 'light' ? 'dark' : 'light',
          }))
        }
        className="px-3 py-1 bg-blue-600 text-white rounded"
      >
        Toggle Theme (Isolasi Render)
      </button>

      <button
        onClick={() =>
          sessionStore.setState((prev) => ({
            metrics: {
              ...prev.metrics,
              notificationsCount: prev.metrics.notificationsCount + 1,
            },
          }))
        }
        className="px-3 py-1 bg-purple-600 text-white rounded"
      >
        Increment Notifications
      </button>
    </div>
  );
};
```

---

## 8. Real World Case Study: Financial Trading Terminal

### Konteks Masalah
Sebuah platform order-book bursa crypto menerima stream data WebSocket berisi pembaruan tick harga dan order depth hingga **1.200 event/detik**. Implementasi React standar yang menampung feed ini menggunakan `useState` di level root menyebabkan:
- Main thread terblokir penuh (*CPU usage 100%*).
- Frame rate ambruk dari 60 FPS ke < 12 FPS.
- State tearing: Header komponen menampilkan harga $65.420 sedangkan komponen grafik order depth menampilkan snapshot $65.410.

### Solusi Arsitektural
1. Pisahkan pipeline penerimaan data WebSocket dari siklus render React via *External Ring Buffer*.
2. Gunakan `useSyncExternalStore` dengan selective sampling.
3. Alokasikan pergerakan tick grafis ke *Lanes* berprioritas rendah menggunakan `startTransition` untuk menjamin interaksi mouse/order execution tetap direspons di bawah 16ms (`SyncLane`).

```typescript
import React, { useRef, useTransition, useState, useEffect } from 'react';
import { ObservableStore, useStoreSelector } from './practical-store';

// 1. Data Type Domain
export interface OrderBookTick {
  price: number;
  volume: number;
  timestamp: number;
}

interface MarketState {
  lastTick: OrderBookTick;
  bidDepth: OrderBookTick[];
  highFrequencyCounter: number;
}

export const marketStore = new ObservableStore<MarketState>({
  lastTick: { price: 0, volume: 0, timestamp: Date.now() },
  bidDepth: [],
  highFrequencyCounter: 0,
});

// 2. High-Frequency Engine (Simulasi Ingestion 1000 msg/sec)
export class MarketFeedSimulator {
  private intervalId: number | null = null;

  public start() {
    this.intervalId = window.setInterval(() => {
      // Direct store update, memotong tree rerender
      marketStore.setState((prev) => ({
        lastTick: {
          price: 65000 + Math.random() * 500,
          volume: parseFloat((Math.random() * 2).toFixed(4)),
          timestamp: Date.now(),
        },
        highFrequencyCounter: prev.highFrequencyCounter + 1,
      }));
    }, 1); // 1000 Hz throughput
  }

  public stop() {
    if (this.intervalId) clearInterval(this.intervalId);
  }
}

// 3. Komponen Display Kritis (Tear-Free via SyncStore)
export const CriticalTickerDisplay: React.FC = () => {
  const price = useStoreSelector(marketStore, (s) => s.lastTick.price);
  const counter = useStoreSelector(marketStore, (s) => s.highFrequencyCounter);

  return (
    <div className="bg-gray-900 text-emerald-400 p-4 font-mono">
      <h2>REALTIME TICKER (Zero-Tearing)</h2>
      <p className="text-2xl font-bold">${price.toFixed(2)}</p>
      <p className="text-xs text-gray-500">Ticks Processed: {counter}</p>
    </div>
  );
};

// 4. Komponen Berat: Interleave Rendering Menggunakan Concurrent Lanes
export const HeavyAnalyticalDepthChart: React.FC = () => {
  const [, startTransition] = useTransition();
  const [deferredPrice, setDeferredPrice] = useState<number>(0);

  // Subscribe ke store, tetapi tangguhkan proses kalkulasi berat ke transition lane
  useEffect(() => {
    const unsubscribe = marketStore.subscribe(() => {
      const currentPrice = marketStore.getState().lastTick.price;
      startTransition(() => {
        setDeferredPrice(currentPrice);
      });
    });
    return unsubscribe;
  }, []);

  // Simulasi kalkulasi rendering berat
  const heavyComputations = () => {
    let result = 0;
    for (let i = 0; i < 2_000_000; i++) {
      result += Math.sqrt(i) * Math.sin(i);
    }
    return result;
  };
  heavyComputations();

  return (
    <div className="bg-gray-800 text-gray-300 p-4">
      <h3>Analytical Projection (Transition Lane)</h3>
      <p>Computed Base: {deferredPrice.toFixed(2)}</p>
    </div>
  );
};
```

---

## 9. Trade-offs

| Pendekatan State | Keuntungan (*Pros*) | Kerugian (*Cons*) | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **Monolithic Component State (`useState` at root)** | Sangat mudah diimplementasikan, zero abstraction overhead, lifecycle terpadu penuh. | Cascading re-render masif. Tidak ada pemisahan domain kalkulasi. Mengakibatkan drop frame pada tree dalam. | Form statis, widget mandiri berskala kecil. |
| **Decoupled Context API** | Built-in ke React, tidak perlu dependensi pihak ketiga, mendukung dependency injection via tree. | Context me-render ulang seluruh consumer jika ada sembarang slice data yang berubah tanpa granular memoization layer. | Tema UI, Lokalisasi/I18n, Konfigurasi autentikasi statis. |
| **External Reactive Store (`useSyncExternalStore`)** | Zero wasted renders jika menggunakan selector. Aman dari state tearing saat concurrent mode. Throughput update sangat tinggi. | Boilerplate arsitektur lebih kompleks. Bypass React DevTools State Tree jika tidak diintegrasikan manual. | Realtime financial dashboard, canvas/game engine UI overlays, streaming analytics. |
| **Ref-Based Bypassing (`useRef` + direct DOM)** | Performa 60 FPS mentah absolut, bypass penuh terhadap reconciler. | Merusak deklaratifitas komponen, berisiko inkonsistensi layout visual, mustahil di-SSR. | Scrubbing video/audio, visualizer WebGL/Canvas interaktif, drag-and-drop hit testing. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Stale Closures pada Event Handler Asinkron

```typescript
// ANTI-PATTERN: Mengakses state langsung di callback asinkron
function StaleComponent() {
  const [data, setData] = useState<string>('init');

  useEffect(() => {
    const socket = new WebSocket('wss://example.com');
    socket.onmessage = () => {
      // BUG: 'data' selalu bernilai 'init' karena terperangkap di lexical environment run pertama
      console.log('Current state is: ' + data);
    };
    return () => socket.close();
  }, []); // Empty dependencies
}

// PRODUCTION SOLUTION: Akses via Ref atau Updater
function RobustComponent() {
  const [data, setData] = useState<string>('init');
  const dataRef = useRef(data);
  dataRef.current = data; // Sinkronkan nilai terkini di setiap render cycle

  useEffect(() => {
    const socket = new WebSocket('wss://example.com');
    socket.onmessage = () => {
      console.log('Current accurate state: ' + dataRef.current);
    };
    return () => socket.close();
  }, []);
}
```

### 10.2 State Tearing pada Concurrent Rendering

```typescript
// ANTI-PATTERN: Membaca mutable global object via useEffect + useState
let globalCounter = 0;

function FaultyConsumer() {
  const [val, setVal] = useState(globalCounter);

  useEffect(() => {
    const listener = () => setVal(globalCounter);
    events.on('change', listener);
    return () => events.off('change', listener);
  }, []);

  // DI CONCURRENT MODE: Render pass dapat diinterupsi. 
  // Bagian atas tree membaca globalCounter = 1, bagian bawah membaca globalCounter = 2.
  return <div>{val}</div>;
}

// PRODUCTION SOLUTION: Gunakan useSyncExternalStore secara native
function SafeConsumer() {
  const val = useSyncExternalStore(
    (callback) => {
      events.on('change', callback);
      return () => events.off('change', callback);
    },
    () => globalCounter
  );

  return <div>{val}</div>;
}
```

### 10.3 Infinite Re-render Cascades melalui Objek Dependensi Tak Stabil

```typescript
// ANTI-PATTERN: Instansiasi objek inline sebagai state setter dependencies
function BadMemoParent() {
  const [count, setCount] = useState(0);

  // Instansiasi referensi objek baru di SETIAP render!
  const config = { threshold: 10 };

  return <OptimizedChild config={config} />;
}

const OptimizedChild = React.memo<{ config: { threshold: number } }>(({ config }) => {
  useEffect(() => {
    // Dipanggil di setiap frame karena referensi config selalu baru!
    console.log('Config executed');
  }, [config]);

  return <div>Child</div>;
});

// PRODUCTION SOLUTION: Stabilkan referensi dengan useMemo atau pindahkan keluar scope
const STATIC_CONFIG = { threshold: 10 };

function GoodParent() {
  return <OptimizedChild config={STATIC_CONFIG} />;
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Bailout Primitive Purity**: Pastikan parameter setter fungsional tidak mengubah data secara mutatif (in-place modification) melainkan mengembalikan referensi baru (*Immutable Update Pattern*).
- [ ] **Safe External Subscriptions**: Audit seluruh integrasi IndexedDB, LocalStorage, window size, dan WebSocket agar menggunakan `useSyncExternalStore` alih-alih `useEffect + useState`.
- [ ] **Co-locate State Responsibly**: Jangan menaruh state lokal ke level Redux/Global Store jika state tersebut hanya dikonsumsi oleh satu cabang leaf node visual.
- [ ] **Eliminate Accidental Closures**: Pasang ESLint rule `react-hooks/exhaustive-deps` dengan konfigurasi level `error`, bukan `warn`.
- [ ] **Batching Strategy Evaluation**: Hindari pemanggilan `ReactDOM.flushSync` kecuali untuk use-case kritis seperti sinkronisasi animasi DOM sinkron murni (misal: scroll rect targeting).
- [ ] **Fine-Grained Memoization**: Hindari membalut semua komponen dengan `React.memo`. Gunakan profiling untuk menemukan bottleneck sebelum mengalokasikan memori overhead untuk memo cache.

---

## 12. Hands-on Practice

Buatlah workspace pengujian internal berikut di dalam direktori `hands-on/m02/`.

### Struktur Direktori
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── src/
│   ├── core/
│   │   └── AdvancedStore.ts
│   ├── components/
│   │   ├── MetricTile.tsx
│   │   └── ControlDeck.tsx
│   ├── index.tsx
│   └── App.tsx
```

### Langkah 1: Siapkan Konfigurasi `package.json`
```json
{
  "name": "react-state-deep-dive",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.4.5",
    "vite": "^5.2.11"
  }
}
```

### Langkah 2: Implementasi Custom Reactive Store Engine
Simpan kode berikut di `hands-on/m02/src/core/AdvancedStore.ts`:

```typescript
type Listener = () => void;

export class AdvancedStore<T extends Record<string, any>> {
  private state: T;
  private subscribers: Set<Listener> = new Set();

  constructor(initialState: T) {
    this.state = Object.freeze({ ...initialState });
  }

  public getState = (): T => this.state;

  public setState = (updater: Partial<T> | ((prev: T) => Partial<T>)): void => {
    const patch = typeof updater === 'function' ? updater(this.state) : updater;
    const nextState = Object.freeze({ ...this.state, ...patch });

    if (this.shallowEqual(this.state, nextState)) {
      return;
    }

    this.state = nextState;
    this.notify();
  };

  public subscribe = (listener: Listener): (() => void) => {
    this.subscribers.add(listener);
    return () => this.subscribers.delete(listener);
  };

  private notify() {
    this.subscribers.forEach((fn) => fn());
  }

  private shallowEqual(objA: any, objB: any): boolean {
    if (Object.is(objA, objB)) return true;
    if (typeof objA !== 'object' || objA === null || typeof objB !== 'object' || objB === null) {
      return false;
    }
    const keysA = Object.keys(objA);
    const keysB = Object.keys(objB);
    if (keysA.length !== keysB.length) return false;
    for (let i = 0; i < keysA.length; i++) {
      if (!Object.prototype.hasOwnProperty.call(objB, keysA[i]) || !Object.is(objA[keysA[i]], objB[keysA[i]])) {
        return false;
      }
    }
    return true;
  }
}
```

### Langkah 3: Implementasi Hook Consumer Komponen
Simpan kode berikut di `hands-on/m02/src/components/MetricTile.tsx`:

```typescript
import React, { useSyncExternalStore, useRef } from 'react';
import { AdvancedStore } from '../core/AdvancedStore';

interface MetricProps {
  store: AdvancedStore<{ cpuLoad: number; memoryUsage: number }>;
  metricKey: 'cpuLoad' | 'memoryUsage';
}

export const MetricTile: React.FC<MetricProps> = ({ store, metricKey }) => {
  const renderCounter = useRef(0);
  renderCounter.current += 1;

  const value = useSyncExternalStore(
    store.subscribe,
    () => store.getState()[metricKey]
  );

  return (
    <div style={{ border: '1px solid #444', padding: '16px', margin: '8px', borderRadius: '4px' }}>
      <h4>Metric: {metricKey}</h4>
      <p style={{ fontSize: '24px', fontWeight: 'bold' }}>{value.toFixed(2)}</p>
      <small style={{ color: '#888' }}>Total Re-render Komponen: {renderCounter.current}</small>
    </div>
  );
};
```

### Langkah 4: Root Application Setup
Simpan kode berikut di `hands-on/m02/src/App.tsx`:

```typescript
import React, { useEffect } from 'react';
import { AdvancedStore } from './core/AdvancedStore';
import { MetricTile } from './components/MetricTile';

const systemStore = new AdvancedStore({
  cpuLoad: 12.5,
  memoryUsage: 45.2,
});

export const App: React.FC = () => {
  useEffect(() => {
    // Engine simulasi: CPU berubah tiap 100ms, Memory berubah tiap 1000ms
    const cpuTimer = setInterval(() => {
      systemStore.setState((prev) => ({
        cpuLoad: 10 + Math.random() * 80,
      }));
    }, 100);

    const memTimer = setInterval(() => {
      systemStore.setState((prev) => ({
        memoryUsage: 30 + Math.random() * 20,
      }));
    }, 1000);

    return () => {
      clearInterval(cpuTimer);
      clearInterval(memTimer);
    };
  }, []);

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '24px' }}>
      <h1>Enterprise State Granularity Profiler</h1>
      <p>Perhatikan bahwa counter re-render MemoryUsage tidak terpengaruh oleh stream CPU yang berjalan cepat.</p>
      <div style={{ display: 'flex' }}>
        <MetricTile store={systemStore} metricKey="cpuLoad" />
        <MetricTile store={systemStore} metricKey="memoryUsage" />
      </div>
    </div>
  );
};
```

---

## 13. Exercise

### Level Easy
Ubah implementasi hook `useCounter` berikut agar aman dari antrean batching state closure:
```typescript
// Masalah: Pemanggilan increment sebanyak 3x secara sekuensial menghasilkan output count + 1
export function useCounter() {
  const [count, setCount] = useState(0);
  const incrementThrice = () => {
    setCount(count + 1);
    setCount(count + 1);
    setCount(count + 1);
  };
  return { count, incrementThrice };
}
```
*Kriteria Sukses*: Ubah menjadi pemanggilan berbasis updater closure sehingga `count` dipastikan bertambah tepat 3.

### Level Medium
Implementasikan hook kustom `useDebouncedState<T>(initialValue: T, delayMs: number): [T, (val: T) => void, boolean]` yang:
1. Mengembalikan nilai instan untuk rendering lokal.
2. Mengembalikan state ter-debounced yang aman dikonsumsi oleh dependensi network fetch.
3. Mengembalikan flag boolean `isPending` yang dieksekusi via `useTransition` internal.

### Level Hard
Buat custom store yang mendukung mekanisme **Atomic Undo/Redo Timeline**. 
1. Store harus menyimpan riwayat state dalam ring-buffer (maksimal 50 langkah).
2. Fungsi `undo()` dan `redo()` harus memulihkan state secara instan tanpa menciptakan re-render loop tak berujung.
3. Konsumen UI harus bisa men-subscribe ke slice tertentu dan tidak me-render ulang saat state yang di-undo tidak memengaruhi slice yang dipilih.

---

## 14. Challenge

### Studi Kasus: Real-Time Collaborative Canvas State Sync Engine

Anda ditugaskan merancang arsitektur state management untuk modul whiteboarding kolaboratif multi-tenant:
1. **Beban Data**: Kanvas menerima mutasi posisi vektor mouse dari 50 kolaborator simultan (masing-masing 60 packet/detik per user via WebRTC DataChannel).
2. **Kebutuhan UI**:
   - Lapisan render pointer kursor pengguna harus berjalan mulus pada kestabilan **60 FPS** tanpa alokasi garbage collection masif.
   - Komponen pohon layer dokumen (DOM biasa berisi daftar teks/objek kanvas) hanya boleh me-render ulang jika terjadi mutasi struktural (penambahan layer baru, penghapusan objek, perubahan hierarki grup).
3. **Batasan Ketat**:
   - Dilarang menggunakan state management eksternal (Zustand, Redux, MobX).
   - Seluruh sinkronisasi data ke komponen React harus menggunakan primitive murni: `useSyncExternalStore`, `useRef`, dan `startTransition`.
   - Hindari fenomena state tearing saat pengguna melakukan zoom/pan kanvas secara simultan dengan update remote via WebRTC.

Rancang arsitektur memori internal, model komputasi store, interface selektor, dan boundary isolasi komponen. Buktikan secara matematis melalui analisis kompleksitas bahwa render tree depth tidak akan memicu degradasi frame time di bawah 16ms!

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Konseptual)

1. **Di manakah React secara internal menyimpan nilai state aktual dari sebuah hook `useState`?**
   - A. Di dalam properti prototipe fungsi komponen.
   - B. Di dalam linked-list yang terikat pada field `memoizedState` milik Fiber node komponen tersebut.
   - C. Di dalam variabel global window runtime browser.
   - D. Di dalam atribut dataset elemen HTML DOM aktual.

2. **Apa yang dilakukan oleh operator `Object.is` saat nilai baru dioperasikan ke fungsi pembaruan `useState`?**
   - A. Melakukan deep equality clone terhadap seluruh nested object.
   - B. Memaksa komponen untuk me-render ulang tanpa memeriksa referensi.
   - C. Memeriksa identitas referensial; jika nilainya identik, React melakukan bailout (membatalkan fase render).
   - D. Mengubah objek menjadi format JSON string untuk membandingkan nilainya.

3. **Mulai React 18, apa yang dimaksud dengan fitur "Automatic Batching"?**
   - A. React memblokir eksekusi thread JavaScript setiap 10ms.
   - B. Penggabungan pembaruan state ke dalam satu render pass tunggal, berlaku lintas timeout, promise, dan native event handler.
   - C. Penghapusan kompilasi JSX ke JavaScript murni secara otomatis.
   - D. Penggabungan CSS classes secara otomatis saat proses build production.

4. **Kapan fase "Layout Effects" (`useLayoutEffect`) dijalankan dalam siklus lifecycle?**
   - A. Asinkron beberapa frame setelah browser selesai menggambar layar.
   - B. Sinkron, tepat setelah mutasi DOM selesai namun sebelum browser menggambar (painting) frame ke monitor.
   - C. Tepat sebelum pemanggilan fungsi komponen pertama kali.
   - D. Hanya saat server merender HTML pada arsitektur SSR.

5. **Apa fungsi utama dari hook `useRef` jika ditinjau dari re-render lifecycle?**
   - A. Memicu re-render berprioritas tinggi tanpa menyentuh reconciliation.
   - B. Menyimpan referensi nilai mutable yang persisten di sepanjang siklus hidup komponen tanpa memicu re-render saat diubah.
   - C. Mempercepat performa garbage collection secara paksa.
   - D. Mencegah komponen anak menerima props baru.

---

### Bagian 2: Intermediate (Pilihan Ganda / Analisis Kode)

6. **Perhatikan kode berikut. Berapa kali teks "CHILD RENDER" dicetak ke console saat tombol diklik satu kali?**
   ```typescript
   const Child = React.memo(({ value }: { value: number }) => {
     console.log("CHILD RENDER");
     return <div>{value}</div>;
   });

   function Parent() {
     const [count, setCount] = useState(0);
     const [text, setText] = useState("");

     const handleClick = () => {
       setCount(1);
       setText("updated");
     };

     return (
       <div>
         <button onClick={handleClick}>Run</button>
         <Child value={count} />
       </div>
     );
   }
   ```
   - A. 0 kali.
   - B. 1 kali (karena Automatic Batching menggabungkan mutasi, dan `value` pada `Child` berubah dari 0 ke 1).
   - C. 2 kali (karena setCount dan setText dipanggil terpisah).
   - D. 3 kali karena React StrictMode me-render ulang semuanya secara double.

7. **Kapan kondisi di mana Anda HARUS menggunakan `ReactDOM.flushSync`?**
   - A. Saat mengambil data dari REST API publik.
   - B. Ketika perlu membaca posisi scroll DOM segera setelah mutasi state tertentu diterapkan ke Real DOM.
   - C. Di dalam loop `array.map()` untuk mempercepat rendering item list.
   - D. Saat menulis skrip unit test menggunakan library Jest.

8. **Apa akar penyebab dari bug *State Tearing* pada Concurrent Mode?**
   - A. Bug memori leak pada Node.js engine v18.
   - B. Komponen membaca data langsung dari store eksternal mutable yang nilainya berubah di tengah-tengah proses rendering asinkron yang belum selesai.
   - C. Penggunaan CSS Grid yang bertabrakan dengan flexbox.
   - D. Ketidakcocokan versi TypeScript antara server dan client.

9. **Mengapa pemanggilan hook tidak boleh diletakkan di dalam blok kondisi `if (condition)`?**
   - A. Karena compiler Babel/SWC akan crash saat mem-parsing AST.
   - B. Karena linked list `memoizedState` pada Fiber bergantung secara absolut pada konsistensi urutan eksekusi hook antar-render.
   - C. Karena blok `if` membuat variabel hook dialokasikan ke stack lokal sementara, bukan heap.
   - D. Karena React mengharuskan seluruh file ditulis dalam paradigma functional murni tanpa branching.

10. **Apa perbedaan mendasar antara `useTransition` dan `useDeferredValue`?**
    - A. `useTransition` digunakan untuk CSS animations, sedangkan `useDeferredValue` untuk HTTP requests.
    - B. `useTransition` membungkus kode pengeksekusi pembaruan state (*updater function*), sedangkan `useDeferredValue` membungkus nilai itu sendiri (*derived value*).
    - C. `useTransition` bersifat synchronous, sedangkan `useDeferredValue` bersifat fully multi-threaded Web Worker.
    - D. Tidak ada perbedaan, keduanya alias untuk fungsi yang persis sama.

---

### Bagian 3: Skenario Kasus Produksi

11. **Skenario 1**: Sebuah platform e-commerce mengalami drop FPS drastis pada input form pencarian produk. Setiap karakter yang diketik pengguna memicu filter lokal terhadap 15.000 item di memori. Bagaimana Anda menstrukturkan state input dan state hasil pencarian agar input pengguna tetap responsif pada 60 FPS tanpa jeda?
12. **Skenario 2**: Dalam sebuah aplikasi pemantauan medis ICU, Anda menerima aliran data detak jantung (EKG) via WebSocket sebesar 200 payload per detik. Komponen EKG graph perlu me-refresh kurva canvas, sementara panel navigasi samping tidak boleh ikut ter-render ulang sama sekali. Jelaskan struktur arsitektur state yang Anda terapkan!
13. **Skenario 3**: Sebuah form multi-step kompleks menyimpan datanya di React Context. Komponen tombol submit berada di step 5, tetapi setiap kali pengguna mengetik satu karakter di field nama pada step 1, tombol submit ikut ter-render ulang. Mengapa hal ini terjadi di level reconciler, dan bagaimana Anda mengatasinya tanpa memecah Context menjadi 5 provider berbeda?

---

### Kunci Jawaban Evaluasi

#### Bagian 1 & 2
1. **B** — React menyimpan state di linked-list pada properti `memoizedState` di FiberNode.
2. **C** — Pengecekan referensial dilakukan via `Object.is`. Jika sama, eksekusi render turunan di-bailout.
3. **B** — React 18 secara otomatis melakukan batching pada seluruh event context.
4. **B** — `useLayoutEffect` dieksekusi secara sinkron di Layout Phase sebelum Browser Paint.
5. **B** — `useRef` mempertahankan data lintas render tanpa memicu siklus reconciler baru.
6. **B** — Berkat automatic batching, hanya ada 1 siklus render. `Child` ter-render 1 kali karena props `value` berubah dari 0 ke 1.
7. **B** — `flushSync` memaksa reconciler melakukan flush ke Real DOM secara sinkron untuk kebutuhan imperatif seperti membaca layout/scroll DOM.
8. **B** — Tearing terjadi jika external store berubah di tengah render pass yang terinterupsi saat membaca data yang sama di branch berbeda.
9. **B** — Rantai linked list Hook mengidentifikasi state berdasarkan urutan panggil traversal. Percabangan membuat urutan indeks node bergeser dan rusak.
10. **B** — `useTransition` digunakan di level trigger (saat Anda memegang dispatcher), sedangkan `useDeferredValue` digunakan saat Anda hanya menerima nilai dari props/up-stream.

#### Bagian 3 (Solusi Skenario Produksi)
11. **Solusi Skenario 1**:
    Gunakan pemisahan *Urgent Update* vs *Transition Update*:
    - State teks input dikelola via `useState` reguler untuk mengikat tag `<input />` secara sinkron (`SyncLane`), menjamin feedback visual ketikan instan tanpa lag.
    - Operasi filter 15.000 array dibungkus menggunakan `startTransition(() => setFilteredList(results))`. Dengan cara ini, kalkulasi filtering berjalan di *TransitionLane*. Jika user mengetik huruf berikutnya saat filtering sedang berjalan, React menginterupsi komputasi sebelumnya dan memprioritaskan karakter baru.

12. **Solusi Skenario 2**:
    Gunakan *Decoupled External Store* berbasis `useSyncExternalStore` dengan pembagian subscription:
    - Data EKG masuk tidak disimpan ke dalam state React root, melainkan ke instance kelas `RingBufferStore` murni.
    - Komponen canvas mendaftar listener ke instance tersebut menggunakan `useSyncExternalStore` atau direct imperative frame tick via `requestAnimationFrame`.
    - Komponen navigasi tidak memiliki dependensi atau subscription ke `RingBufferStore`, sehingga siklus Fiber traversal sama sekali tidak menyentuh sub-tree navigasi (*bailout total*).

13. **Solusi Skenario 3**:
    Hal ini terjadi karena React Context mendistribusikan notifikasi render ke seluruh consumer yang memanggil `useContext(FormContext)`, terlepas dari apakah field yang dikonsumsi berubah atau tidak.
    - **Solusi**: Pindahkan penyimpanan form state ke implementasi *Observable Pattern Store* (seperti pada subbab 7.2) di luar pohon React. Masukkan instance store tersebut ke dalam Context (bukan datanya, melainkan instancenya yang stabil).
    - Komponen input nama dan tombol submit masing-masing menggunakan hook `useStoreSelector` yang menyeleksi slice data yang relevan secara granular. Tombol submit hanya me-render ulang jika properti validasi tombol berubah.

---

## 16. Summary

1. **State Primitives Internal Architecture**: State di dalam React didukung oleh representasi *linked list* (`memoizedState`) pada masing-masing Fiber node, bukan oleh runtime instansiasi closure lokal.
2. **Reconciliation & Prioritas (Lanes)**: Siklus render React modern beroperasi secara preemptive dan asinkron menggunakan bitmask Lane priority. Pekerjaan render berprioritas rendah dapat ditangguhkan (*deferred*) dan diinterupsi oleh interaksi berprioritas tinggi (*Urgent UI Interaction*).
3. **Batching & Transisi**: Automatic batching menggabungkan beberapa pemanggilan state setter menjadi satu siklus evaluasi tunggal untuk menghindari thrashing DOM. `startTransition` mengizinkan komputasi intensif didelegasikan ke latar belakang tanpa memblokir input latency thread utama.
4. **Resiliensi Konkurensi**: Menghubungkan external state store mutable ke React wajib dilakukan via `useSyncExternalStore` demi mencegah *state tearing*, menjamin pembacaan snapshot yang konsisten secara atomik di seluruh sub-tree rendering.