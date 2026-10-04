# MODUL 02: DEEP DIVE, IMPLEMENTASI LANJUTAN & ARSITEKTUR PRODUKSI
**Kategori:** 03-Frontend-and-Mobile  
**Bab 01:** BAB-01-Fondasi-dan-Arsitektur  
**Tingkat Kesulitan:** Advanced / Enterprise-Grade

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Anatomi React Fiber Engine**: Membedah struktur internal `FiberNode`, mekanisme pointer-linked tree (`child`, `sibling`, `return`), serta siklus hidup *Double Buffering* (`current` vs `workInProgress`).
2. **Menguasai Mekanisme Scheduler & Lane Priority Model**: Mengidentifikasi bagaimana React mengklasifikasikan pembaruan UI ke dalam 31-bit integer *Lanes*, mengelola interupsi *render phase*, dan memitigasi isu *frame-dropping*.
3. **Mengeliminasi Concurrency Pitfalls & UI Tearing**: Mengimplementasikan `useTransition`, `useDeferredValue`, dan `useSyncExternalStore` secara presisi guna mencegah *state tearing* dan *render de-optimizations*.
4. **Merancang Arsitektur Skala Enterprise**: Menerapkan arsitektur berbasis *Feature-Sliced Design* (FSD) atau *Clean Architecture* di React dengan pemisahan tegas antara Server vs Client Component boundaries.
5. **Menjalankan Profiling & Debugging Tingkat Lanjut**: Mengisolasi kemacetan performa (*bottlenecks*) menggunakan React Profiler API, mengaudit *commit phases*, dan mengeliminasi *cascading renders*.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib memahami:
* Konsep dasar ES6+ (Tagged template literals, Symbols, WeakMap/WeakSet, Bitwise operators, Generator Functions, dan Microtasks vs Macrotasks pada Event Loop).
* Modul 01: Fondasi DOM Virtual, Reconciliation dasar, JSX transpilasi, dan lifecycle hooks standar (`useState`, `useEffect`, `useMemo`, `useCallback`).
* Pemahaman fundamental mengenai Browser Rendering Pipeline (Parsing, Style Calculation, Layout, Paint, Compositing) dan metrik Core Web Vitals (INP, LCP, CLS).

---

## 3. Concept & Internal Architecture

### 3.1 Evolusi dari Stack Reconciler ke Fiber Architecture
Pada React 15 ke bawah, mekanisme reconciler bergantung pada pemanggilan fungsi rekursif secara sinkron melalui *call stack* JavaScript bawaan (*Stack Reconciler*). Jika hierarki komponen sangat dalam, rekursi ini mengunci thread utama (*main thread execution*) hingga seluruh pohon selesai di-*diff*. Akibatnya, browser tidak dapat memproses input pengguna, animasi terputus (*jank*), dan frame rate jatuh di bawah 60 FPS.

React Fiber (diperkenalkan sejak React 16 dan dimatangkan penuh pada model Concurrent React 18/19) merekayasa ulang algoritma rekursi menjadi struktur data linked list virtual. Ini memungkinkan React mengimplementasikan **Cooperative Multitasking**: pekerjaan rendering dapat dipecah menjadi unit-unit kecil (*units of work*), dijeda (*pause*), dibatalkan (*abort*), atau dialihkan prioritasnya berdasarkan input pengguna berprioritas tinggi.

### 3.2 Anatomi FiberNode
Setiap elemen React yang di-*instantiate* memiliki padanan sebuah objek `FiberNode`. Berikut adalah representasi struktural TypeScript dari unit internal tersebut:

```typescript
type WorkTag = 0 | 1 | 2 | 3 | 5 | 6 /* FunctionComponent, ClassComponent, HostRoot, HostComponent, dll. */;
type Flags = number; // Bitmask untuk side-effects (Placement, Update, Deletion, Passive, dll.)
type Lanes = number; // Bitmask 31-bit untuk alokasi prioritas

interface FiberNode {
  // Tag identifikasi tipe komponen
  tag: WorkTag;
  key: null | string;
  elementType: any;
  type: any;
  stateNode: any; // Mengarah ke DOM node asli (HostComponent) atau class instance

  // Struktur Topologi Tree (Singly Linked List)
  return: FiberNode | null;     // Parent pointer
  child: FiberNode | null;      // First child pointer
  sibling: FiberNode | null;    // Next sibling pointer
  index: number;

  // Props & State Management
  pendingProps: any;            // Props baru yang masuk untuk dirender
  memoizedProps: any;           // Props yang digunakan untuk menghasilkan output terakhir
  updateQueue: unknown;         // Antrean state updates (Lanes-aware)
  memoizedState: any;           // Head dari linked-list Hooks (FunctionComponent) atau state object

  // Concurrency & Prioritization Engine
  lanes: Lanes;                 // Prioritas pembaruan pada node ini
  childLanes: Lanes;            // Agregasi prioritas pembaruan pada subtree turunan

  // Double Buffering Mechanism
  alternate: FiberNode | null;  // Pointer ke twin node di tree sebelah (Current <-> WorkInProgress)

  // Side-effect Flags (Mutasi DOM, Lifecycle calls)
  flags: Flags;
  subtreeFlags: Flags;
  deletions: Array<FiberNode> | null;
}
```

### 3.3 Mekanisme Double Buffering
Mirip dengan teknik rendering pada game engine untuk menghindari flicker grafis, React memelihara dua Fiber tree secara bersamaan:
1. **`current` Tree**: Merefleksikan UI yang saat ini terpasang secara aktif di layar DOM browser.
2. **`workInProgress` (WIP) Tree**: Tree yang sedang dirakit atau dimutasi di memori selama *Render Phase*.

Pointer `alternate` menghubungkan setiap node di `current` tree dengan pasangannya di `workInProgress` tree. Ketika proses reconciler selesai, React hanya perlu mengubah pointer `root.current` dari pohon lama ke pohon WIP baru dalam operasi Commit Phase yang sinkron dan instan:

$$\text{HostRoot}.\text{current} \longleftarrow \text{workInProgress}$$

### 3.4 Dua Fase Eksekusi: Render Phase vs Commit Phase

```
[ User Event / Network / State Update ]
                 │
                 ▼
     ┌────────────────────────┐
     │      RENDER PHASE      │ ◄─── Interuptible, Asynchronous, Paling Berat (CPU)
     │   (Reconciliation)     │      Dapat dibatalkan/diulang tanpa efek samping ke DOM
     └───────────┬────────────┘
                 │ (Fiber tree selesai ditandai dengan flags / mutations)
                 ▼
     ┌────────────────────────┐
     │      COMMIT PHASE      │ ◄─── Uninterruptible, Synchronous, Sangat Cepat
     │     (DOM Mutation)     │      Memodifikasi DOM Asli & Menjalankan Layout Effects
     └────────────────────────┘
```

1. **Render Phase**:
   * Menjalankan fungsi `performUnitOfWork`.
   * Menelusuri pohon secara *depth-first search*:
     * Turun ke bawah memanggil `beginWork(current, workInProgress, renderLanes)`.
     * Naik ke atas memanggil `completeWork(current, workInProgress, renderLanes)`.
   * Bersifat murni (*pure computation*), tidak menyentuh DOM riil. Jika pekerjaan memakan waktu lebih dari *time-slice* frame (~5ms) dan ada interaksi pengguna (misal: keystroke), fase ini diinterupsi dan scheduler mengembalikan kendali ke browser.
2. **Commit Phase**:
   * Mengambil alih pohon WIP yang telah selesai dikalkulasi beserta daftar penanda mutasi (*flags/effects*).
   * Dieksekusi melalui 3 sub-fase:
     * **Before Mutation Phase**: Membaca snapshot DOM (`getSnapshotBeforeUpdate`).
     * **Mutation Phase**: Memodifikasi DOM node sebenarnya (menyisipkan node baru, mengubah atribut, menghapus node via `commitMutationEffects`).
     * **Layout Phase**: Mengeksekusi layout effects (`useLayoutEffect`), memperbarui ref pointer.
   * Menjalankan **Passive Effects** (`useEffect`) secara asinkron sesaat setelah browser selesai melakukan *paint*.

### 3.5 Lane Priority Model (Bitmask Engine)
Sebelumnya React menggunakan model *Expiration Times*. Sejak versi 18, React mengadopsi model *Lanes* yang menggunakan operasi bitwise 31-bit integer. Hal ini memberikan kemampuan ekspresi yang jauh lebih granular: pembaruan tidak lagi hanya sebuah angka linear tunggal yang habis masa berlakunya, melainkan dapat dipisahkan (*batched*), digabungkan (*merged*), atau ditangguhkan (*suspended*).

```text
SyncLane               = 0b0000000000000000000000000000001 (Discrete clicks, typing)
InputContinuousLane    = 0b0000000000000000000000000000100 (Hover, scrolling, wheel)
DefaultLane            = 0b0000000000000000000000100000000 (Data fetching, standard setState)
TransitionLane1        = 0b0000000000000000000100000000000 (startTransition UI)
IdleLane               = 0b0100000000000000000000000000000 (Off-screen work, analytics)
```

Melalui operasi bitmask:
* Memeriksa prioritas: `const hasIntersection = (a & b) !== 0;`
* Menggabungkan lanes: `lanes = lanes | newLane;`
* Menghapus prioritas yang selesai: `lanes = lanes & ~completedLane;`

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal?
* **UI Jank & Input Latency**: Operasi diffing struktur DOM virtual besar yang berjalan sinkron memblokir *Main Thread*. Browser kehilangan target 16.67ms (60 FPS) atau 8.33ms (120 FPS), memicu pembatalan animasi CSS dan lambatnya respon saat pengguna mengetik.
* **State Tearing**: Ketika membaca data dari external state store (Redux, Zustand, RxJS) saat proses rendering asynchronous berlangsung, komponen A bisa membaca snapshot data versi lama, sedangkan komponen B membaca snapshot data versi baru setelah diinterupsi oleh event listener. Tampilan visual menjadi inkonsisten (*torn UI*).

### Solusi React Concurrent Model
* **Time Slicing**: Memecah beban komputasi CPU menjadi segmen 5ms menggunakan perantara `MessageChannel` (bukan `requestIdleCallback` bawaan karena isu inkonsistensi frame rate antar browser).
* **Graceful Degradation via Suspense & Transitions**: Memisahkan perubahan UI mendesak (*Urgent Updates*: form input, buttons) dari perubahan yang dapat ditunda (*Non-Urgent Updates*: visualisasi filter pencarian, transisi tab) tanpa membutuhkan library micro-tasking manual.

---

## 5. How: Workflow Detail

Diagram berikut mengilustrasikan alur eksekusi `startTransition` vs `Urgent Update` di bawah kendali Fiber Reconciler:

```
[ Urgent Update (Keystroke) ]      [ Non-Urgent Update (Filter List via startTransition) ]
             │                                              │
             ▼                                              ▼
   Assign: SyncLane (0b01)                       Assign: TransitionLane (0b10000...)
             │                                              │
             └──────────────────────┬───────────────────────┘
                                    │
                                    ▼
                         [ React Scheduler ]
                                    │
            Is there a pending Urgent Task in Main Thread?
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼ YES                               ▼ NO
     [ Suspend Transition Work ]             [ Run workLoopConcurrent ]
     [ Process SyncLane Work ]                            │
     [ Commit Sync to DOM ]                  ┌────────────┴────────────┐
                  │                          ▼                         ▼
                  └────────────────► [ Resume Transition Work ]   [ Time Slice Expired (>5ms)? ]
                                             │                         │
                                             ▼                         ▼
                                    [ Complete Work Loop ]     [ Yield back to Browser ]
                                             │                         │
                                             ▼                         ▼
                                   [ commitRoot (Swap tree) ]  [ Schedule next microtask ]
```

### Rincian Eksekusi `workLoopConcurrent`
Secara internal, inti dari Render Phase beroperasi di dalam loop berikut:

```javascript
function workLoopConcurrent() {
  // Lanjutkan memproses unit kerja selama belum mencapai batas waktu frame
  // dan ada node berikutnya yang perlu dikerjakan.
  while (workInProgress !== null && !shouldYield()) {
    performUnitOfWork(workInProgress);
  }
}
```
1. `shouldYield()` berkonsultasi dengan Scheduler API menggunakan `performance.now()`. Jika waktu eksekusi telah melampaui batas *yield interval* (~5ms), loop berhenti dan menaruh kelanjutan kerja ke antrean macrotask via `MessageChannel.port1.postMessage`.
2. `performUnitOfWork` mengeksekusi `beginWork()`. Jika node tidak mengalami perubahan props, context, atau lanes (`checkScheduledUpdateOrContext(current, renderLanes)` menghasilkan false), node di-*bailout* dan reconciler melompati rendering seluruh subtree tersebut via `bailoutOnAlreadyFinishedWork`.
3. Setelah mencapai leaf node, loop berbalik memanggil `completeWork()` untuk merangkai DOM instance dan mengakumulasi `subtreeFlags`.

---

## 6. Analogy & Diagram ASCII

### Analogi Arsitektur: Dual-Buffer Video Engine
Bayangkan React sebagai tim pengembang video game grafis:
* **Current Tree (Front Buffer)**: Monitor menampilkan bingkai (frame) grafis yang sedang dilihat penonton. Tidak ada yang boleh mencoret-coret monitor ini secara langsung karena akan memunculkan glitch visual.
* **WorkInProgress Tree (Back Buffer)**: Di belakang layar, GPU menggambar frame berikutnya secara mendetail.
* **Scheduler (Frame Controller)**: Mengizinkan artis menggambar latar belakang yang berat. Namun jika komandan (User) menekan tombol tembak (SyncLane), pengerjaan latar belakang dihentikan seketika untuk merespons tembakan terlebih dahulu.
* **Commit Phase (Buffer Swap)**: Begitu frame selesai digambar sempurna, sinyal V-Sync menukar pointer: *Back Buffer* beralih menjadi *Front Buffer*. Penonton melihat hasil yang mulus tanpa sedikit pun lag grafis.

### Representasi Topologi Fiber Tree
```text
           HostRootFiber (current)
                 │
                 │ .child
                 ▼
             AppFiber ◄─────────────────────────┐
                 │                              │
                 │ .child                       │ .return
                 ▼                              │
           SidebarFiber ──────.sibling──────► ContentFiber
                 │                                  │
                 │ .child                           │ .child
                 ▼                                  ▼
             NavFiber                           ListFiber
                                                    │
                                                    │ .child
                                                    ▼
                                                ItemFiber ──.sibling──► ItemFiber
```

---

## 7. Simple & Practical Implementation

### 7.1 Simple Example: Menghindari Blocking UI Menggunakan `useTransition`
Berikut perbandingan performa langsung antara manipulasi state sinkron dan asynchronous concurrent batching.

```tsx
import React, { useState, useTransition, ChangeEvent } from 'react';

export const FilterComparison: React.FC = () => {
  const [query, setQuery] = useState<string>('');
  const [filteredItems, setFilteredItems] = useState<string[]>([]);
  const [isPending, startTransition] = useTransition();

  const handleHeavyFiltering = (e: ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    
    // Urgent Update: Nilai input field harus segera berubah di layar
    setQuery(value);

    // Non-Urgent Update: Mengkalkulasi 20.000 elemen dialokasikan ke TransitionLane
    startTransition(() => {
      const generated = Array.from({ length: 20000 }, (_, idx) => 
        `Entity-${value}-${idx}`
      ).filter(item => item.includes(value));
      
      setFilteredItems(generated);
    });
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'monospace' }}>
      <h3>Concurrent Transition Benchmark</h3>
      <input
        type="text"
        value={query}
        onChange={handleHeavyFiltering}
        placeholder="Type rapidly to test UI fluidity..."
        style={{ padding: '8px', fontSize: '16px', width: '100%' }}
      />
      {isPending && <p style={{ color: '#ff6b00' }}>[Scheduler] Rendering non-urgent UI in background...</p>}
      
      <p>Rendered Records: {filteredItems.length}</p>
    </div>
  );
};
```

### 7.2 Practical Example: Enterprise Custom Real-time Store via `useSyncExternalStore`
Untuk mencegah *UI tearing* pada sistem streaming event real-time (seperti WebSockets atau Kafka bridge) di React 18+, dilarang menggunakan `useEffect` + `setState`. Standar industri mewajibkan penggunaan `useSyncExternalStore`.

```tsx
import React, { useSyncExternalStore } from 'react';

// Kontrak Subscription Store Enterprise
type Listener = () => void;

interface MarketTick {
  symbol: string;
  price: number;
  timestamp: number;
}

class MarketDataEngine {
  private static instance: MarketDataEngine;
  private state: Map<string, MarketTick> = new Map();
  private listeners: Set<Listener> = new Set();

  private constructor() {
    // Simulasi ingestion data berkecepatan tinggi (100 updates/sec)
    setInterval(() => {
      this.mutateRandomPrice();
    }, 10);
  }

  public static getInstance(): MarketDataEngine {
    if (!MarketDataEngine.instance) {
      MarketDataEngine.instance = new MarketDataEngine();
    }
    return MarketDataEngine.instance;
  }

  private mutateRandomPrice(): void {
    const symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD'];
    const target = symbols[Math.floor(Math.random() * symbols.length)];
    const currentPrice = this.state.get(target)?.price ?? 50000;
    const delta = (Math.random() - 0.5) * 50;

    this.state.set(target, {
      symbol: target,
      price: parseFloat((currentPrice + delta).toFixed(2)),
      timestamp: Date.now(),
    });

    this.notify();
  }

  public subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  public getSnapshot = (): Map<string, MarketTick> => {
    // Kembalikan referensi immutable atau identitas stabil
    // PENTING: Jangan menghasilkan array/objek baru setiap pemanggilan jika isi data sama!
    return this.state;
  };
}

export const OrderBookTracker: React.FC<{ symbol: string }> = ({ symbol }) => {
  const engine = MarketDataEngine.getInstance();
  
  // Mengintegrasikan External Store secara aman dari UI Tearing
  const ticks = useSyncExternalStore(
    engine.subscribe,
    engine.getSnapshot,
    // Server snapshot fallback untuk SSR
    () => new Map<string, MarketTick>()
  );

  const tick = ticks.get(symbol);

  return (
    <div style={{ border: '1px solid #ccc', margin: '8px', padding: '12px', borderRadius: '4px' }}>
      <h4>Asset: {symbol}</h4>
      <p>Latest Rate: <strong>${tick?.price ?? 'Awaiting data...'}</strong></p>
      <small>Timestamp: {tick ? new Date(tick.timestamp).toISOString() : '-'}</small>
    </div>
  );
};
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Trading Terminal FinTech "ApexGlobal"
* **Konteks**: Terminal perdagangan instrumen derivatif ApexGlobal memproses 1.000 pembaruan harga per detik melalui gRPC-Web Stream. Dashboard menampilkan grafik modular, antrean order book (*bids & asks*), dan form eksekusi order instan.
* **Permasalahan**: Ketika volatilitas pasar tinggi, user yang sedang mengetikkan nominal order mengalami delay input hingga 400ms (*severe input freezing*). Profiling via Chrome DevTools merekam Total Blocking Time (TBT) mencapai 3.200ms karena render tree order book (berisi 1.500 baris DOM) mengunci thread sinkron.

### Diagnosis Arsitektural & Solusi
1. **Diagnosis**: Pembaruan harga WebSocket dieksekusi melalui dispatch global Redux biasa. Setiap ada paket data masuk, ia memicu *re-render cascade* dari root dashboard menuju seluruh child component. Akibatnya, browser melewatkan frame pengetikan pada input tag.
2. **Solusi Refaktorisasi Tiga Lapisan**:
   * **Lapisan Ingestion**: Mengisolasi ticker data dari React Root State ke dalam Memory Store khusus (seperti pola `MarketDataEngine` di atas).
   * **Lapisan Reconciler**: Membagi konsumsi data komponen order book menggunakan `useDeferredValue` dengan batas suspensi rendering.
   * **Lapisan Isolasi Mutasi**: Menerapkan CSS `contain: strict` pada kontainer order book dan membatasi Virtual Scrolling hanya merender 30 node aktif yang terlihat di viewport.

### Hasil Metrik Performa
* **Interaction to Next Paint (INP)**: Turun dari 480ms (kategori *Poor*) ke **18ms** (kategori *Good*).
* **Total Blocking Time (TBT)**: Dari 3.200ms tereduksi menjadi **45ms** (penurunan ~98.5%).
* **Memory Footprint**: Stabil di angka 85MB tanpa ada *memory leak* akibat penumpukan closure event listeners.

---

## 9. Trade-offs & Deep Engineering Balance

| Aspek Arsitektur | Pilihan A: Sinkron Tradisional (`useState` / Context murni) | Pilihan B: Concurrent Mode (`useTransition` / `useSyncExternalStore`) |
| :--- | :--- | :--- |
| **CPU vs Memory Trade-off** | Menghemat alokasi heap memori karena hanya ada satu pohon yang direkonsiliasi dalam satu waktu. | Membutuhkan alokasi memori heap tambahan hingga 2x lipat saat proses *Double Buffering* & kloning linked list Fiber berjalan. |
| **Input Latency (INP)** | Buruk pada komponen kompleks. Render tree besar memblokir event handling microtask/macrotask. | Optimal (< 50ms). React menginterupsi komputasi rendering untuk meloloskan interaksi input pengguna. |
| **Kompleksitas Mental Model** | Rendah. Model eksekusi linear memudahkan pelacakan alur stack trace saat debugging. | Tinggi. Siklus hidup fungsi komponen dapat dieksekusi berulang kali (*discarded renders*) sebelum berhasil di-*commit*. |
| **Karakteristik Tearing External Store** | Sangat rentan mengalami *UI Tearing* jika state manager pihak ketiga tidak dirancang sesuai arsitektur concurrency React. | Aman dan konsisten di seluruh hierarki view berkat jaminan mutasi atomik lewat `useSyncExternalStore`. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Side-Effects di Render Phase (Pure Function Violation)
```tsx
// ❌ CRITICAL BUG: Memanggil side-effect di dalam body komponen
const UserList: React.FC = () => {
  const [data, setData] = useState([]);
  
  // Salah! Pada Concurrent Mode, Render Phase bisa berjalan berkali-kali 
  // dan dibatalkan sebelum Commit Phase. Ini memicu HTTP call ganda atau telemetry corrupt!
  analytics.track('VIEW_RENDERED'); 

  return <div>...</div>;
};

//  SOLUSI: Pindahkan ke useEffect atau Event Handlers
const UserListCorrected: React.FC = () => {
  useEffect(() => {
    analytics.track('VIEW_RENDERED');
  }, []);

  return <div>...</div>;
};
```

### 10.2 Snapshot Instability pada `useSyncExternalStore`
```tsx
// ❌ CRITICAL BUG: Menghasilkan referensi objek baru pada getSnapshot
const useInvalidStore = () => {
  return useSyncExternalStore(
    subscribe,
    // Error: Mengembalikan referensi array baru setiap saat memicu infinite loop render!
    () => [1, 2, 3] 
  );
};

//  SOLUSI: Pastikan getSnapshot mengembalikan referensi objek yang stabil
const CACHED_ARRAY = [1, 2, 3];
const useValidStore = () => {
  return useSyncExternalStore(
    subscribe,
    () => CACHED_ARRAY
  );
};
```

### 10.3 De-optimizing Bailout Mechanism
React membatalkan (*bailout*) render subtree jika `oldProps === newProps`. Kesalahan umum:
```tsx
// ❌ Menghancurkan optimasi memo/bailout
<MemoizedDataGrid 
  config={{ timeout: 5000 }} // Objek baru dialokasikan pada setiap render parent!
  onAction={() => execute()}   // Fungsi inline baru dibuat pada setiap render!
/>

//  SOLUSI: Pertahankan referensi menggunakan useMemo dan useCallback
const stableConfig = useMemo(() => ({ timeout: 5000 }), []);
const handleAction = useCallback(() => execute(), []);

<MemoizedDataGrid 
  config={stableConfig} 
  onAction={handleAction} 
/>
```

---

## 11. Best Practices & Production Checklist

- [ ] **Bebas Side-Effects di Render Path**: Pastikan seluruh function components bersifat *strictly pure*. Tidak ada mutasi variabel eksternal di luar `useEffect` atau `useLayoutEffect`.
- [ ] **Aktivasi StrictMode**: Pasang `<React.StrictMode>` di root production & staging development. StrictMode secara sengaja me-render komponen dua kali di development untuk mendeteksi *impure code* dan *memory leak*.
- [ ] **Terapkan `useSyncExternalStore`**: Audit seluruh implementasi custom state manager atau subscription window event (misal: `window.innerWidth`, scroll position) agar menggunakan hook ini.
- [ ] **Gunakan Compiler / Linter Rules**: Terapkan `@typescript-eslint/recommended` dan `eslint-plugin-react-hooks`.
- [ ] **Manfaatkan Profiler API**: Pasang komponen `<Profiler id="CoreWorkflow" onRender={handleMetrics}>` pada alur kritis transaksi untuk memonitor `actualDuration` dan `baseDuration`.
- [ ] **Batas Suspense yang Granular**: Hindari membungkus seluruh aplikasi ke dalam satu Suspense boundary besar. Pecah boundary per section/widget guna memungkinkan *selective hydration*.

---

## 12. Hands-on Practice

Simpan seluruh hasil latihan praktikum ini pada direktori: `hands-on/m02/`

### File: `hands-on/m02/package.json`
```json
{
  "name": "react-m02-concurrency-lab",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.4.5",
    "vite": "^5.2.0"
  }
}
```

### File: `hands-on/m02/src/SchedulerProfiler.tsx`
```tsx
import React, { Profiler, ProfilerOnRenderCallback, useState, useTransition } from 'react';

export const SchedulerProfilerLab: React.FC = () => {
  const [dataSize, setDataSize] = useState<number>(500);
  const [items, setItems] = useState<number[]>([]);
  const [isPending, startTransition] = useTransition();

  const onRenderCallback: ProfilerOnRenderCallback = (
    id,
    phase,
    actualDuration,
    baseDuration,
    startTime,
    commitTime
  ) => {
    console.info({
      ComponentId: id,
      ExecutionPhase: phase,
      TimeTakenMs: Number(actualDuration.toFixed(2)),
      SubtreeFullCostMs: Number(baseDuration.toFixed(2)),
      PhaseStart: startTime,
      PhaseCommitted: commitTime,
    });
  };

  const triggerHeavyComputation = () => {
    startTransition(() => {
      // Beban komputasi simulasi
      const buffer = new Array(dataSize).fill(0).map((_, i) => Math.sin(i) * Math.cos(i));
      setItems(buffer);
    });
  };

  return (
    <Profiler id="FiberVisualizer" onRender={onRenderCallback}>
      <div style={{ border: '1px solid #444', padding: '16px', borderRadius: '8px' }}>
        <h2>Fiber Lifecycle & Profiler Diagnostics</h2>
        <label>
          Item Volume: 
          <input 
            type="range" 
            min="100" 
            max="15000" 
            value={dataSize} 
            onChange={(e) => setDataSize(Number(e.target.value))} 
          />
          <span>({dataSize} nodes)</span>
        </label>
        <br /><br />
        <button onClick={triggerHeavyComputation} disabled={isPending}>
          {isPending ? 'Reconciling in Background...' : 'Run Work Loop Benchmark'}
        </button>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '12px' }}>
          {items.map((val, idx) => (
            <div 
              key={idx} 
              style={{
                width: '8px',
                height: '8px',
                backgroundColor: val > 0 ? '#00e676' : '#e91e63'
              }} 
            />
          ))}
        </div>
      </div>
    </Profiler>
  );
};
```

---

## 13. Exercises

### 13.1 Level Easy: Dynamic Document Title via `useSyncExternalStore`
* **Instruksi**: Buat hook `useDocumentTitleStore` yang membaca dan subscribe terhadap mutasi judul dokumen browser (`document.title`) tanpa memicu re-render yang tidak sinkron di seluruh komponen.
* **Kriteria Keberhasilan**: Hook mengembalikan title terkini dan menyediakan method untuk mengubahnya, menggunakan mekanisme store murni.

### 13.2 Level Medium: Custom Responsive Breakpoint Engine
* **Instruksi**: Implementasikan custom store untuk memonitor CSS Media Queries (`window.matchMedia`).
* **Kebutuhan Teknis**: Hindari penambahan event listener berlebih pada window resize. Gunakan subscription berbasis `MediaQueryList.addEventListener('change', listener)`.
* **Kriteria Keberhasilan**: Lulus validasi Concurrent Mode tanpa trigger warning mismatch saat SSR.

### 13.3 Level Hard: Lane-Aware Priority Debouncer
* **Instruksi**: Buat komponen pencarian yang mengkombinasikan debouncing klasik dengan `useDeferredValue`.
* **Kebutuhan Teknis**: Jika pengguna mengetik lambat (> 300ms antar karakter), pencarian langsung dieksekusi secara sinkron. Jika pengguna mengetik sangat cepat (< 50ms), eksekusi dideferensiasi ke `TransitionLane` dan menampilkan indikator *stale data visualization* (tampilan data memudar/opacity 0.6) saat `currentValue !== deferredValue`.

---

## 14. Challenge

### Studi Kasus: Real-Time Telemetry Matrix (Mission Control Dashboard)
Sebuah sistem pemantauan satelit menampilkan matriks telemetri yang terdiri dari **50.000 metrik status komponen**. Metrik diperbarui dari jaringan peer-to-peer WebSocket setiap 50 milidetik.

**Kebutuhan Sistem:**
1. Pengguna harus dapat memfilter matriks menggunakan Regular Expression di kolom pencarian tanpa mengalami degradasi input responsif (target frame budget: maks 16ms/frame).
2. Ketika penyaringan berat sedang dikalkulasi, data matriks lama harus tetap dapat di-scroll secara mulus tanpa freeze (*No UI Tearing*).
3. Anda tidak diperkenankan menggunakan library state management pihak ketiga (Redux, MobX, TanStack, dll.). Seluruh state subscription harus dibangun di atas arsitektur *Native React Concurrent Primitives* (`useSyncExternalStore`, `useTransition`, `useDeferredValue`).

**Target Evaluasi:**
* Laporan Profiler membuktikan 0 task yang melebihi durasi blocking 50ms.
* Zero memory leakage selama pengujian stres koneksi selama 10 menit (verifikasi alokasi memori melalui Snapshot Chrome DevTools Memory Heap).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Bagian 1: Basic (Pilihan Ganda)

1. **Apa perbedaan struktural utama antara Stack Reconciler dan Fiber Reconciler?**
   * A. Stack Reconciler menggunakan Web Worker, Fiber menggunakan Main Thread.
   * B. Stack Reconciler berbasis pemanggilan fungsi rekursif sinkron, Fiber berbasis struktur data singly linked list yang dapat diinterupsi.
   * C. Stack Reconciler memanipulasi DOM langsung tanpa Virtual DOM, Fiber menggunakan Virtual DOM.
   * D. Stack Reconciler tidak mendukung props dan state.

2. **Pointer manakah pada `FiberNode` yang menghubungkan node saat ini dengan node induk langsungnya?**
   * A. `parent`
   * B. `ancestor`
   * C. `return`
   * D. `alternate`

3. **Kapan `commit phase` React dieksekusi?**
   * A. Setelah seluruh unit kerja Render Phase selesai dan perubahan DOM siap dimutasi secara atomik.
   * B. Di setiap iterasi pemanggilan `beginWork`.
   * C. Bersamaan saat fungsi komponen dieksekusi pertama kali.
   * D. Tepat sebelum `shouldYield()` bernilai true.

4. **Karakteristik utama dari `Render Phase` di Concurrent React adalah:**
   * A. Menerapkan mutasi layout secara instan ke DOM window.
   * B. Bersifat asinkron, komputasinya murni (*pure*), dan dapat dijeda (*interrupted*) oleh Scheduler.
   * C. Hanya berjalan satu kali selama siklus hidup aplikasi berjalan.
   * D. Menjalankan seluruh hook `useEffect` secara blocking.

5. **Hook apa yang wajib digunakan untuk membaca data dari event emitter eksternal tanpa risiko visual tearing pada React 18+?**
   * A. `useEffect`
   * B. `useLayoutEffect`
   * C. `useSyncExternalStore`
   * D. `useImperativeHandle`

---

### 15.2 Bagian 2: Intermediate (Analisis Benar/Salah & Isian Singkat)

6. *(True/False)*: Pada model Double Buffering, React merekonstruksi seluruh pohon `workInProgress` dari nol setiap kali terjadi mutasi state kecil.
7. *(Isian Singkat)*: Sebutkan nama teknik penjadwalan yang membatasi waktu eksekusi JavaScript sekitar 5ms per frame agar thread utama browser tetap responsif menerima input!
8. *(True/False)*: Komponen di dalam `startTransition` diproses menggunakan prioritas yang setara dengan event ketikan keyboard (`SyncLane`).
9. *(Isian Singkat)*: Properti apa pada `FiberNode` yang menghubungkan pohon *Current* dengan pohon *Work-In-Progress*?
10. *(True/False)*: Operasi bitmask Lane model memungkinkan React untuk menggabungkan beberapa pembaruan prioritas menggunakan operator bitwise OR (`|`).

---

### 15.3 Bagian 3: Production Incident Troubleshooting (Analisis Skenario)

#### Skenario 1
Sebuah platform E-Commerce mengalami insiden di mana grafik analitik penjualan kadang menampilkan data pelanggan yang salah ketika pengguna beralih tab dashboard secara cepat di jaringan 3G. Hasil audit kode menunjukkan bahwa data store dibaca melalui variabel global singleton dan diperbarui via hook `useEffect`.  
*Jelaskan akar penyebab bug ini berdasarkan konsep Concurrency dan sebutkan langkah korektif arsitekturalnya!*

#### Skenario 2
Saat melakukan audit menggunakan React Profiler pada dashboard pelaporan keuangan, ditemukan bahwa nilai `actualDuration` pada sebuah grid tabel bernilai 240ms, dan layout shift terjadi berulang kali saat user mengetik filter. Pengembang telah membungkus pemanggilan filter dengan `useTransition`. Namun, input ketikan tetap terasa sangat lambat (*laggy*).  
*Identifikasi mengapa `useTransition` gagal mengisolasi lag dan bagaimana memperbaikinya!*

#### Skenario 3
Aplikasi Web Enterprise Anda mengalami kebocoran memori (*memory leak*) secara perlahan di lingkungan produksi. Setelah heap dump dianalisis, ditemukan ribuan objek `FiberNode` dengan flag `PassiveEffect` tertahan di heap memory dan tidak ter-garbage collection.  
*Apa kemungkinan terbesar kesalahan implementasi yang dilakukan tim pengembang di level lifecycle effects?*

---

### Kunci Jawaban & Rubrik Evaluasi

#### Bagian 1
1. **B** — Fiber menggantikan call stack recursion JavaScript dengan heap-allocated singly-linked list nodes.
2. **C** — Pointer internal untuk parent adalah `return` (karena merepresentasikan ke mana eksekusi kembali setelah menyelesaikan leaf node).
3. **A** — Commit phase berjalan sinkron dan tidak dapat diinterupsi setelah render phase menghasilkan tree WIP yang siap dipublikasi.
4. **B** — Render phase dirancang purely computational agar aman untuk dihentikan dan diulang jika ada interupsi prioritas tinggi.
5. **C** — `useSyncExternalStore` adalah primitif resmi penjaga konsistensi data sinkron pada concurrent model.

#### Bagian 2
6. **False** — React menggunakan kembali (*reuses*) alokasi `FiberNode` yang sudah ada dari pointer `alternate` untuk menghemat alokasi memori GC.
7. **Time Slicing** (atau Cooperative Multitasking).
8. **False** — `startTransition` mengalokasikan pembaruan ke `TransitionLane` (non-urgent), jauh di bawah prioritas `SyncLane`.
9. **`alternate`**.
10. **True** — Operasi Lane menggunakan 31-bit integer bitmasks, di mana agregasi dilakukan dengan bitwise OR.

#### Bagian 3
* **Solusi Skenario 1**: Akar masalahnya adalah **UI Tearing & Race Condition**. Penggunaan `useEffect` untuk membaca global singleton di Concurrent Mode menyebabkan pembaruan tertunda dan komponen membaca state yang tidak terkoordinasi saat rendering diinterupsi oleh perpindahan tab. **Langkah Korektif**: Bungkus singleton store menggunakan API `useSyncExternalStore` dan pastikan setiap snapshot data bersifat immutable atau terikat pada ID siklus request aktif.
* **Solusi Skenario 2**: `useTransition` hanya memprioritaskan pembaruan state yang dideferensiasikan. Jika state dari `query` text input dimasukkan ke dalam callback transition yang sama dengan list filtering, atau jika komponen input text membaca state yang sama dengan tabel yang sedang dirender, thread tetap akan terkunci. **Langkah Korektif**: Pisahkan state menjadi dua: Satu *urgent state* untuk mengendalikan input visual secara instan (`query`), dan satu *transition state* untuk data tabel (`deferredQuery` atau via `startTransition(() => setFilteredTableData(data))`). Pastikan tabel dibungkus dengan `React.memo` agar tidak ikut re-render saat state urgent berubah.
* **Solusi Skenario 3**: Kegagalan membersihkan subscription (*teardown function*) pada `useEffect`. Jika sebuah hook mendaftarkan event listener ke event emitter global, DOM window, atau interval tanpa mengembalikan fungsi pembersih (`return () => cleanup()`), closure akan terus mengikat `FiberNode` tersebut di memori, mencegah V8/JSC Garbage Collector membebaskan alokasi tree yang sudah terlepas (*detached*).

---

## 16. Summary

1. **Arsitektur Fiber** adalah landasan modern React yang mengubah rekursi sinkron menjadi struktur linked list virtual yang dapat diinterupsi (*interruptible units of work*).
2. Mekanisme **Double Buffering** memastikan user tidak pernah melihat tampilan setengah matang; manipulasi UI dikerjakan secara tak terlihat pada `workInProgress` tree sebelum ditukar atomik ke `current` tree.
3. **Lanes Model** mengalokasikan prioritas pembaruan menggunakan bitmask 31-bit integer, memungkinkan pemisahan tegas antara tugas interaktif (*Urgent*) dan tugas komputasi berat (*Transitions*).
4. Untuk menjaga stabilitas data pada sistem enterprise berkecapatan tinggi, integrasi data store eksternal wajib mengadopsi **`useSyncExternalStore`** guna mengeliminasi bencana visual *state tearing*.