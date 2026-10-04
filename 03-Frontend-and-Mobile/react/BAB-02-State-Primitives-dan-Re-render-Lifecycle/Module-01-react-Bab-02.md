# MODUL PEMBELAJARAN TEKNIK PERANGKAT LUNAK: REACT

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kurikulum:** React Architecture & Engineering
* **Bab:** 02 (Core Reconciliation, State Management, and Lifecycle Internals)
* **Modul:** 01
* **Topik:** State Primitives & Re-render Lifecycle
* **Tingkat Kesulitan:** Advanced / Staff Engineer Level
* **Prasyarat:** Pemahaman mendalam ECMAScript 2022+ (Closures, Prototype Chain, Event Loop), Virtual DOM / React Element Trees, TypeScript Generics, dan Hooks API dasar (`useState`, `useEffect`).

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta mampu:
1. Mengartikulasikan mekanisme internal React Fiber yang mengatur siklus hidup state primitives (`useState`, `useReducer`), termasuk representasi linked list pada Fiber nodes.
2. Membedah algoritma penjadwalan pembaruan state: alokasi *lanes*, proses *reconciliation*, dan transisi fase *Render* (deterministik, murni, asynchronous) ke fase *Commit* (sinkron, mutasi host DOM).
3. Mengidentifikasi, mengisolasi, dan memitigasi isu *stale closures*, pembaruan state yang hilang (*lost updates*), dan siklus render tak terbatas (*infinite loops*).
4. Merancang arsitektur state lokal komponen yang mematuhi hukum determinisme fungsional, memanfaatkan *automatic batching* React 18+, serta mengoptimalkan penggunaan memori di lingkungan browser enterprise.
5. Membangun custom state management primitives berbasis reducers yang tahan terhadap *race conditions* pada level rendering concurrent.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### UI Sebagai Proyeksi Murni dari State Komponen
Mental model dasar React berakar pada paradigma komputasi fungsional murni:

$$\text{UI} = f(\text{State})$$

Namun, pada sistem skala industri, relasi ini sering disalahartikan sebagai eksekusi sekuensial prosedural. Pengembang pemula menganggap `setState(newValue)` mengeksekusi mutasi variabel secara in-place. Mental model yang benar adalah:
* **State adalah Snapshot:** State dalam fungsi komponen bersifat konstan (*immutable*) untuk eksekusi (pass) render spesifik tersebut. Komponen tidak "mengamati" perubahan state secara real-time di tengah berjalannya tubuh fungsi; komponen memproyeksikan representasi UI berdasarkan *snapshot* nilai state yang diinjeksi React Fiber saat eksekusi dimulai.
* **Dispatch adalah Penjadwalan, Bukan Mutasi:** Memanggil fungsi updater bukanlah pemanggilan mutator objek, melainkan pengiriman (*dispatch*) sebuah objek aksi ke dalam antrean pembaruan (*update queue*) milik Fiber node terkait. React menjadwalkan pekerjaan komputasi untuk masa depan berdasarkan prioritas (*lane priority*).
* **Render adalah Komputasi Topologi Pohon:** Render bukanlah manipulasi Real DOM. Render adalah pemanggilan rekursif atau traversal struktural terhadap pohon komponen untuk menghitung struktur pohon Fiber berikutnya (*work-in-progress tree*) dan menghasilkan representasi perbedaan (*delta/effects*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah diagram arsitektur siklus pembaruan state pada React 18+ (Concurrent Fiber Reconciler):

```
+----------------------------------------------------------------------------------------------------+
|                                    USER INTERACTION / ASYNC EVENT                                  |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
                                      [ dispatchAction() ]
                                                  │
                                                  ▼
                          +───────────────────────────────────────────────+
                          |   Enqueue Update Object into Fiber.updateQueue|
                          |   Update: { lane, action, next, hasEagerState}|
                          +───────────────────────────────────────────────+
                                                  │
                                                  ▼
                          +───────────────────────────────────────────────+
                          |      scheduleUpdateOnFiber(fiber, lane)       |
                          |      Request Scheduler for execution tick     |
                          +───────────────────────────────────────────────+
                                                  │
                                                  ▼
========================================== RENDER PHASE ==============================================
(Asynchronous, Interruptible, Pure Function Calculation, NO DOM MUTATION)
                                                  │
                          +───────────────────────▼───────────────────────+
                          |            workLoopConcurrent()              |
                          |  Traverse Fiber Tree: beginWork()             |
                          +───────────────────────────────────────────────+
                                                  │
                                                  ▼
                          +───────────────────────────────────────────────+
                          |   Update Primitive: updateReducer / State    |
                          |   Iterate Update Queue & Resolve Base State   |
                          |   Run Object.is(newState, prevState) check    |
                          +───────────────────────────────────────────────+
                                                  │
                                      [ State Changed? ]
                                      ├─── NO  ───> [ Bailout (Early Exit, Drop WIP subtree) ]
                                      └─── YES ───> Continue
                                                  │
                                                  ▼
                          +───────────────────────────────────────────────+
                          |         Diffing / Reconciliation              |
                          |   Compare current Tree with WIP Tree          |
                          |   Flag Fiber with Effect Tag: Placement/Update|
                          +───────────────────────────────────────────────+
                                                  │
                                                  ▼
                          +───────────────────────────────────────────────+
                          |             completeWork()                    |
                          |   Bubble up effect tags to Root Fiber         |
                          +───────────────────────────────────────────────+
                                                  │
========================================== COMMIT PHASE ==============================================
(Synchronous, Non-interruptible, Mutates Real DOM)
                                                  │
                                                  ▼
                          +───────────────────────────────────────────────+
                          |               commitRoot()                    |
                          |  1. commitBeforeMutationEffects (DOM reads)   |
                          |  2. commitMutationEffects (DOM Writes / Native|
                          |     node insertion, deletion, attributes)     |
                          |  3. Switch Pointers: current <── WIP Tree     |
                          |  4. commitLayoutEffects (useLayoutEffect)     |
                          +───────────────────────────────────────────────+
                                                  │
                                                  ▼
                               +─────────────────────────────────────+
                               | Post-Commit Phase: Passive Effects  |
                               | (Scheduler flushes useEffect tasks) |
                               +─────────────────────────────────────+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Objek Fiber dan Linked List Hook
Pada representasi internal React (khususnya paket `react-reconciler`), setiap instance fungsional komponen terikat ke sebuah objek `FiberNode`. Objek ini memiliki field `memoizedState` yang menampung linked list dari hooks yang dieksekusi secara sekuensial.

```typescript
// Representasi internal disederhanakan dari Fiber Node
interface FiberNode {
  tag: WorkTag;                       // Mengidentifikasi tipe fiber (FunctionComponent, HostComponent, dll)
  key: null | string;
  elementType: any;
  type: any;
  stateNode: any;
  return: FiberNode | null;          // Pointer ke parent
  child: FiberNode | null;           // Pointer ke first child
  sibling: FiberNode | null;         // Pointer ke adjacent sibling
  index: number;
  
  // State primitif dan hooks disimpan di sini:
  memoizedState: Hook | null;        // Head dari Hook singly-linked list
  updateQueue: unknown;              // Antrean mutasi untuk class/host root
  lanes: Lanes;                      // Bitmask prioritas komputasi
  childLanes: Lanes;
  alternate: FiberNode | null;       // Pointer ke Double Buffering counterpart (current <-> WIP)
}

// Representasi struktur data Hook
interface Hook {
  memoizedState: any;                // Nilai state terakhir yang selesai di-render
  baseState: any;                    // Nilai state dasar sebelum pending updates diproses
  baseQueue: Update<any, any> | null;// Pending updates yang dilewati karena prioritas rendah
  queue: UpdateQueue<any, any> | null;// Antrean dispatch saat ini
  next: Hook | null;                 // Pointer ke hook berikutnya dalam urutan deklarasi
}

interface Update<S, A> {
  lane: Lane;
  action: A;
  hasEagerState: boolean;
  eagerState: S | null;
  next: Update<S, A> | null;         // Circular linked list pointer
}

interface UpdateQueue<S, A> {
  pending: Update<S, A> | null;      // Circular linked list dari updates yang belum diproses
  lanes: Lanes;
  dispatch: ((action: A) => void) | null;
  lastRenderedReducer: ((state: S, action: A) => S) | null;
  lastRenderedState: S | null;
}
```

### 2. Double Buffering Strategy
React mengelola dua pohon Fiber secara simultan di dalam memori:
1. **Current Tree:** Pohon Fiber yang saat ini tercermin secara visual pada Real DOM.
2. **Work-in-Progress (WIP) Tree:** Pohon Fiber alternatif yang sedang dikonstruksi atau dihitung selama fase render.

Ketika `dispatchAction` dipanggil, React mengalokasikan pekerjaan pada WIP node (yang di-clone dari current node melalui `createWorkInProgress`). Jika komputasi render selesai tanpa interupsi, pointer root berpindah:
```typescript
root.current = workInProgress;
```
Operasi pergantian pointer (*pointer swap*) ini berlangsung instan dan atomik pada awal sub-fase commit mutation, mencegah inkonsistensi rendering UI parsial (*tearing*).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Batched Updates (React 18 Automatic Batching)
Sebelum versi 18, React hanya menggabungkan (*batch*) pembaruan state di dalam event handlers native React (misal `onClick`). Pembaruan di dalam `setTimeout`, `Promise.then`, atau native event listener dieksekusi secara terpisah dan memicu render independen untuk setiap setState.

Pada React 18, mekanisme `batching` diterapkan secara universal melalui API internal scheduler berbasis microtasks dan lanes:

```typescript
// Skenario:
function handleClick() {
  setCount(c => c + 1);
  setFlag(f => !f);
  // React 17: 1 Render cycle jika di handler React
}

function handleAsync() {
  fetch('/api').then(() => {
    setCount(c => c + 1);
    setFlag(f => !f);
    // React 17: 2 Render cycles terpisah! Real DOM di-paint 2 kali.
    // React 18: 1 Render cycle tunggal (Automatic Batching).
  });
}
```

Jika pengembang perlu mengecualikan pembaruan dari batching untuk membaca perubahan Real DOM seketika, fungsi `flushSync` disediakan oleh modul `react-dom`. Perlu digarisbawahi bahwa `flushSync` mendegradasi performa karena memaksa reconciler membersihkan antrean (*flush*) secara sinkron.

### Stale Closures: Mekanisme dan Analisis Memori
Stale closure terjadi ketika fungsi mempertahankan referensi leksikal ke variabel dari scope eksekusi lama yang nilainya telah diperbarui pada render berikutnya.

Pertimbangkan kode berikut:
```typescript
const [count, setCount] = useState<number>(0);

useEffect(() => {
  const timer = setInterval(() => {
    // Closure menangkap 'count' pada saat effect pertama kali dieksekusi (count = 0)
    setCount(count + 1); 
  }, 1000);
  return () => clearInterval(timer);
}, []); // Dependency array kosong: closure di atas tidak pernah diperbarui
```
Setiap detik, `setCount(0 + 1)` dieksekusi. State tidak pernah beranjak dari `1`.

Solusi tingkat kompilasi dan runtime:
1. **Functional State Updates:** `setCount(prev => prev + 1)` mengambil nilai langsung dari `baseState`/`eagerState` pada antrean internal Hook, memotong ketergantungan leksikal terhadap closure snapshot.
2. **State Primitive Reducer:** Memusatkan transisi state ke dalam `useReducer` yang mendispatch aksi independen konteks temporal.

### Algoritma Bailout: `Object.is`
React menggunakan algoritma `Object.is(prev, next)` untuk menentukan apakah suatu komponen perlu melalui fase render ulang atau dihentikan (*bailout*):
* Jika state baru memiliki kesamaan referensi struktural dengan state lama:
  ```typescript
  if (is(basicStateReducer(hook.memoizedState, action), hook.memoizedState)) {
    return; // Bailout: tidak ada re-render untuk subtree ini
  }
  ```
* Mutasi langsung (*in-place mutation*) pada Array atau Object merusak deteksi ini:
  ```typescript
  const [items, setItems] = useState([1, 2, 3]);
  items.push(4);
  setItems(items); // Object.is(items, items) === true -> REACT BAILS OUT, UI TIDAK BERUBAH!
  ```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi kanonikal yang mendemonstrasikan perilaku state primitives, functional updates untuk menghindari stale closure, dan custom batching logic:

```typescript
import React, { useState, useReducer, useEffect, useRef } from 'react';

// Tipe untuk useReducer state machine
interface CounterState {
  count: number;
  step: number;
  history: number[];
}

type CounterAction =
  | { type: 'INCREMENT' }
  | { type: 'DECREMENT' }
  | { type: 'SET_STEP'; payload: number }
  | { type: 'RESET' };

const counterReducer = (state: CounterState, action: CounterAction): CounterState => {
  switch (action.type) {
    case 'INCREMENT':
      return {
        ...state,
        count: state.count + state.step,
        history: [...state.history, state.count + state.step],
      };
    case 'DECREMENT':
      return {
        ...state,
        count: state.count - state.step,
        history: [...state.history, state.count - state.step],
      };
    case 'SET_STEP':
      return {
        ...state,
        step: action.payload,
      };
    case 'RESET':
      return {
        count: 0,
        step: 1,
        history: [0],
      };
    default:
      return state;
  }
};

const initialState: CounterState = {
  count: 0,
  step: 1,
  history: [0],
};

export const StateLifecycleDemo: React.FC = () => {
  // Primitif 1: useState dasar
  const [simpleCount, setSimpleCount] = useState<number>(0);
  
  // Primitif 2: useReducer untuk transisi kompleks
  const [machineState, dispatch] = useReducer(counterReducer, initialState);
  
  // Track render count tanpa memicu re-render baru
  const renderCounterRef = useRef<number>(1);
  renderCounterRef.current += 1;

  // Kasus: Demonstrasi functional update vs direct value
  const handleBatchBrokenUpdate = () => {
    // Tiga mutasi langsung: Nilai akhir HANYA naik +1 karena snapshot leksikal
    setSimpleCount(simpleCount + 1);
    setSimpleCount(simpleCount + 1);
    setSimpleCount(simpleCount + 1);
  };

  const handleBatchCorrectUpdate = () => {
    // Tiga functional updates: Mengambil pending state secara sekuensial. Nilai naik +3
    setSimpleCount(prev => prev + 1);
    setSimpleCount(prev => prev + 1);
    setSimpleCount(prev => prev + 1);
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'monospace' }}>
      <h2>Re-render Diagnostics Panel (Render #: {renderCounterRef.current})</h2>
      
      <section style={{ border: '1px solid #ccc', padding: '16px', marginBottom: '16px' }}>
        <h3>useState: Functional vs Static Resolution</h3>
        <p>Current Count: {simpleCount}</p>
        <button onClick={handleBatchBrokenUpdate}>
          Execute Broken +3 (Actual: +1)
        </button>
        <button onClick={handleBatchCorrectUpdate} style={{ marginLeft: '8px' }}>
          Execute Correct Functional +3
        </button>
      </section>

      <section style={{ border: '1px solid #ccc', padding: '16px' }}>
        <h3>useReducer: Deterministic State Engine</h3>
        <p>Machine Count: {machineState.count} | Step: {machineState.step}</p>
        <p>History: {JSON.stringify(machineState.history)}</p>
        <button onClick={() => dispatch({ type: 'INCREMENT' })}>Increment by Step</button>
        <button onClick={() => dispatch({ type: 'DECREMENT' })} style={{ marginLeft: '8px' }}>Decrement by Step</button>
        <button onClick={() => dispatch({ type: 'SET_STEP', payload: 5 })} style={{ marginLeft: '8px' }}>Set Step = 5</button>
        <button onClick={() => dispatch({ type: 'RESET' })} style={{ marginLeft: '8px' }}>Reset</button>
      </section>
    </div>
  );
};
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari alur eksekusi implementasi Seksi 07:

1. **Baris 20–44 (`counterReducer`):** Mendefinisikan *pure reducer function*. Fungsi ini tidak melakukan operasi I/O, tidak memutasi `state` asal, dan mengembalikan referensi objek baru via *spread operator* (`...state`). Hal ini menjamin algoritma bailout React dapat mendeteksi ketidaksamaan identitas referensial (`Object.is(oldState, newState) === false`).
2. **Baris 54 (`useState<number>(0)`):** React memanggil `mountState` (jika fase initial mount) atau `updateState` (pada re-render). Di dalam struktur Fiber node komponen ini, dibuat pointer linked list `Hook` pertama yang mengalokasikan memori untuk menyimpan nilai number primitif `0`.
3. **Baris 57 (`useReducer(counterReducer, initialState)`):** Dialokasikan sebagai node kedua (`hook1.next`) dalam linked list Fiber. Menyediakan dispatcher atomik yang membungkus pembaruan state dengan skema berbasis intent aksi (*action-driven*).
4. **Baris 60–61 (`useRef<number>(1)`):** Ref disimpan sebagai hook ketiga (`hook2.next`). Ref memoizedState menyimpan container konstan `{ current: value }`. Mutasi langsung pada `renderCounterRef.current` tidak memicu re-render karena ref tidak didaftarkan ke dalam algoritma diffing jalur reconciler.
5. **Baris 65–68 (`handleBatchBrokenUpdate`):** 
   * Eksekusi pertama memanggil `setSimpleCount(0 + 1)`. Update object dialokasikan dengan nilai eager state `1`.
   * Eksekusi kedua memanggil `setSimpleCount(0 + 1)`. Karena referensi `simpleCount` tertahan pada nilai snapshot leksikal saat fungsi render berjalan (`0`), update object kedua juga membawa nilai `1`.
   * Eksekusi ketiga identik: membawa nilai `1`.
   * Saat scheduler React memproses antrean `updateQueue` pada render cycle berikutnya, nilai akhir `baseState` adalah `1`.
6. **Baris 72–75 (`handleBatchCorrectUpdate`):**
   * Pemanggilan `setSimpleCount(prev => prev + 1)` mendaftarkan lambda updater ke circular buffer linked list `UpdateQueue`.
   * Reconciler memproses rantai updater secara sekuensial:
     $$\text{updater}_1(0) \to 1; \quad \text{updater}_2(1) \to 2; \quad \text{updater}_3(2) \to 3$$
   * Hasil kalkulasi mutlak adalah `3`. Menjamin integritas transaksi data tanpa ketergantungan pada closure lama.

---

## SEKSI 09 — STUDI KASUS NYATA
**Domain:** Real-Time Fintech Algorithmic Order Book Execution
**Konteks Arsitektur:** Sebuah platform perdagangan saham institusional menerima puluhan pembaruan harga (*ticks*) per detik melalui antarmuka WebSocket. Komponen Order Book bertugas menampilkan daftar limit order yang aktif, menghitung kedalaman pasar (*market depth*), serta mengeksekusi konfirmasi transaksi lokal.

### Permasalahan
Tim frontend mengimplementasikan state order book menggunakan beberapa variabel `useState` terpisah untuk array penawaran (*bids*), permintaan (*asks*), status koneksi, dan agregasi volume. 
Masalah kritis yang muncul di produksi:
1. **State Inconsistency (Tearing):** Pembaruan WebSocket memicu mutasi parsial tak terkoordinasi antar state array terpisah, mengakibatkan kalkulasi total volume di UI tidak cocok dengan daftar order yang dirender.
2. **High Main-Thread Latency & Dropped Frames:** Puluhan kali panggilan `setState` per detik melumpuhkan thread utama browser karena overhead alokasi antrean reconciliation terus-menerus.
3. **Memory Leaks:** Closure handler WebSocket menahan referensi state lama ke array berukuran besar, mencegah garbage collector membersihkan V8 heap memory.

### Solusi Desain
1. Konsolidasi seluruh relasi state transaksional ke dalam satu implementasi custom high-performance state primitive menggunakan pola **Deterministic Finite State Machine (FSM)** via `useReducer`.
2. Penggunaan **Buffer & Batch Processing Engine** internal dengan pembatasan frekuensi (*throttling/flushing*) terikat pada window microtask scheduler untuk mencegah pemblokiran Main-Thread.
3. Struktur data normalized (*hash maps*) yang menjamin operasi $O(1)$ untuk mutasi order book alih-alih alokasi array baru $O(N)$ di setiap tick.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Di bawah ini adalah implementasi sistematis production-ready untuk modul Order Book Engine:

```typescript
import React, { useReducer, useEffect, useCallback, useRef, memo } from 'react';

// ==========================================
// 1. DATA CONTRACTS & IMMUTABLE TYPES
// ==========================================

export interface OrderLevel {
  price: number;
  quantity: number;
  total: number;
}

export interface OrderBookState {
  bids: Map<number, number>; // price -> quantity
  asks: Map<number, number>; // price -> quantity
  lastUpdateId: number;
  sequenceMismatch: boolean;
}

export type OrderBookAction =
  | {
      type: 'BATCH_TICK';
      payload: {
        updates: Array<{ side: 'bid' | 'ask'; price: number; quantity: number }>;
        updateId: number;
      };
    }
  | { type: 'RESET_STREAM' };

// ==========================================
// 2. DETERMINISTIC ENGINE (REDUCER)
// ==========================================

const INITIAL_ORDER_STATE: OrderBookState = {
  bids: new Map(),
  asks: new Map(),
  lastUpdateId: 0,
  sequenceMismatch: false,
};

function orderBookReducer(state: OrderBookState, action: OrderBookAction): OrderBookState {
  switch (action.type) {
    case 'BATCH_TICK': {
      const { updates, updateId } = action.payload;

      // Proteksi urutan paket data jaringan (Sequence Consistency Check)
      if (state.lastUpdateId !== 0 && updateId !== state.lastUpdateId + 1) {
        return {
          ...state,
          sequenceMismatch: true,
        };
      }

      // Clone map secara struktural untuk mematuhi immutability invariant React
      const nextBids = new Map(state.bids);
      const nextAsks = new Map(state.asks);

      for (let i = 0; i < updates.length; i++) {
        const { side, price, quantity } = updates[i];
        const targetMap = side === 'bid' ? nextBids : nextAsks;

        if (quantity === 0) {
          targetMap.delete(price);
        } else {
          targetMap.set(price, quantity);
        }
      }

      return {
        bids: nextBids,
        asks: nextAsks,
        lastUpdateId: updateId,
        sequenceMismatch: false,
      };
    }

    case 'RESET_STREAM':
      return INITIAL_ORDER_STATE;

    default:
      return state;
  }
}

// ==========================================
// 3. OPTIMIZED UI ROW (LEAF COMPONENT)
// ==========================================

interface OrderRowProps {
  price: number;
  quantity: number;
  side: 'bid' | 'ask';
}

const OrderRow = memo<OrderRowProps>(({ price, quantity, side }) => {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '2px 8px',
        color: side === 'bid' ? '#00c087' : '#ff3b30',
        fontFamily: 'monospace',
      }}
    >
      <span>{price.toFixed(2)}</span>
      <span>{quantity.toFixed(4)}</span>
    </div>
  );
});

OrderRow.displayName = 'OrderRow';

// ==========================================
// 4. MAIN ENGINE COMPONENT
// ==========================================

export const InstitutionalOrderBook: React.FC = () => {
  const [state, dispatch] = useReducer(orderBookReducer, INITIAL_ORDER_STATE);

  // Queue buffer internal untuk menyatukan ticks frekuensi tinggi dari WebSocket
  const incomingBufferRef = useRef<Array<{ side: 'bid' | 'ask'; price: number; quantity: number }>>([]);
  const sequenceTrackerRef = useRef<number>(0);
  const frameRequestRef = useRef<number | null>(null);

  // Mekanisme scheduler internal berbasis AnimationFrame untuk throttling render
  const flushUpdates = useCallback(() => {
    if (incomingBufferRef.current.length > 0) {
      const currentBatch = [...incomingBufferRef.current];
      incomingBufferRef.current = [];

      sequenceTrackerRef.current += 1;
      
      dispatch({
        type: 'BATCH_TICK',
        payload: {
          updates: currentBatch,
          updateId: sequenceTrackerRef.current,
        },
      });
    }

    frameRequestRef.current = requestAnimationFrame(flushUpdates);
  }, []);

  useEffect(() => {
    // Mulai render-loop engine
    frameRequestRef.current = requestAnimationFrame(flushUpdates);

    // Simulasi Stream WebSocket Jaringan Frekuensi Tinggi (50 events / detik)
    const intervalId = setInterval(() => {
      const mockSide: 'bid' | 'ask' = Math.random() > 0.5 ? 'bid' : 'ask';
      const mockPrice = mockSide === 'bid' ? 100 - Math.random() * 2 : 100 + Math.random() * 2;
      const mockQty = Math.floor(Math.random() * 10) === 0 ? 0 : Math.random() * 5; // Probabilitas likuidasi (0)

      incomingBufferRef.current.push({
        side: mockSide,
        price: parseFloat(mockPrice.toFixed(2)),
        quantity: parseFloat(mockQty.toFixed(4)),
      });
    }, 20);

    return () => {
      clearInterval(intervalId);
      if (frameRequestRef.current !== null) {
        cancelAnimationFrame(frameRequestRef.current);
      }
    };
  }, [flushUpdates]);

  // Derived state calculations (Dilakukan saat fase render secara deterministik)
  const sortedBids = Array.from(state.bids.entries())
    .map(([price, quantity]) => ({ price, quantity }))
    .sort((a, b) => b.price - a.price)
    .slice(0, 10);

  const sortedAsks = Array.from(state.asks.entries())
    .map(([price, quantity]) => ({ price, quantity }))
    .sort((a, b) => a.price - b.price)
    .slice(0, 10);

  return (
    <div style={{ width: '400px', backgroundColor: '#121212', color: '#ffffff', padding: '16px' }}>
      <header style={{ borderBottom: '1px solid #333', paddingBottom: '8px', marginBottom: '8px' }}>
        <h4 style={{ margin: 0 }}>High-Frequency Order Book</h4>
        <small style={{ color: state.sequenceMismatch ? '#ff3b30' : '#888' }}>
          Sequence ID: {state.lastUpdateId} {state.sequenceMismatch && '(ERR: DESYNC DETECTED)'}
        </small>
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div>
          <span style={{ fontSize: '11px', color: '#666' }}>ASKS (SELL ORDERS)</span>
          {sortedAsks.map(ask => (
            <OrderRow key={`ask-${ask.price}`} price={ask.price} quantity={ask.quantity} side="ask" />
          ))}
        </div>

        <div style={{ borderTop: '1px dashed #333', margin: '4px 0' }} />

        <div>
          <span style={{ fontSize: '11px', color: '#666' }}>BIDS (BUY ORDERS)</span>
          {sortedBids.map(bid => (
            <OrderRow key={`bid-${bid.price}`} price={bid.price} quantity={bid.quantity} side="bid" />
          ))}
        </div>
      </div>
    </div>
  );
};
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Evaluasi | `useState` Primitive | `useReducer` Primitive | Direct Mutable Reference (`useRef`) |
| :--- | :--- | :--- | :--- |
| **Model Paradigma** | Nilai individual diskrit. | State Machine / Transisi terpusat. | Akses memori mutabel secara persisten. |
| **Siklus Hidup Render** | Menjadwalkan reconciliation loop penuh via scheduler. | Menjadwalkan reconciliation loop penuh via scheduler. | Tidak memicu alur reconciliation maupun lifecycle phases. |
| **Determinisme State** | Rendah saat state interdependen satu sama lain. | Tinggi; seluruh transisi terikat pada aksi yang terisolasi. | Nol; mutasi dapat terjadi di sembarang lifecycle tanpa kontrol kompilator. |
| **Overhead Memori** | Minimal per instance primitive, namun membengkak jika banyak split states. | Alokasi objek `action` dan eksekusi fungsi reducer. | Sangat rendah; single object reference `{ current: T }`. |
| **Bailout Capability** | Otomatis via `Object.is`. | Otomatis via `Object.is` pada return value reducer. | Tidak ada konsep bailout karena tidak ada proses render. |
| **Gunakan Ketika...** | State independen bertipe primitif (boolean, string, number sederhana). | State kompleks, nested data structures, atau memiliki dependensi logika transisi berganda. | Menyimpan DOM nodes, ID interval/timer, mutable cache, atau buffer streaming. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Re-render Cascades via Unstable Initializers
* **Mekanisme Kegagalan:** Memberikan pemanggilan fungsi langsung ke argumen `useState` atau `useReducer`:
  ```typescript
  // PITFALL: computeExpensiveState() dieksekusi pada SETIAP render pass!
  const [data, setData] = useState(computeExpensiveState());
  ```
* **Mitigasi:** Gunakan *lazy initialization pattern* dengan meneruskan referensi fungsi murni (*function reference*):
  ```typescript
  // SOLUSI: Fungsi hanya dieksekusi sekali saat initial mount phase (mountState)
  const [data, setData] = useState(() => computeExpensiveState());
  ```

### 2. State Mutation Inside Render Phase (Bad Engine Loop)
* **Mekanisme Kegagalan:** Memanggil `dispatch` atau `setState` secara sinkron langsung di dalam tubuh eksekusi komponen tanpa pembungkus guard atau useEffect:
  ```typescript
  function BadComponent({ value }: { value: number }) {
    const [count, setCount] = useState(0);
    setCount(value); // RUNTIME ERROR: Too many re-renders. React limits the number of renders to prevent an infinite loop.
    return <div>{count}</div>;
  }
  ```
* **Mitigasi:** Transisi state yang bereaksi terhadap perubahan prop harus diselesaikan melalui kalkulasi derived state murni selama rendering, bukan dengan sinkronisasi ke state lokal:
  ```typescript
  function GoodComponent({ value }: { value: number }) {
    // Derived state: Tidak memerlukan useState mau pun useEffect
    const calculatedValue = value * 2;
    return <div>{calculatedValue}</div>;
  }
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Mengabaikan Dependency Array pada Asynchronous Closures
```typescript
// ANTI-PATTERN: Closure terjebak pada state awal
const [user, setUser] = useState<string>('Guest');

useEffect(() => {
  const handler = () => console.log(`Current active user: ${user}`);
  window.addEventListener('resize', handler);
  return () => window.removeEventListener('resize', handler);
}, []); // Warning: React Hook useEffect has a missing dependency: 'user'
```
* **Solusi Perbaikan:** Selalu patuhi linter `react-hooks/exhaustive-deps`. Jika fungsi handler membutuhkan state terbaru tanpa harus me-rebind listener secara terus-menerus, gunakan pola ref-forwarding:
```typescript
const [user, setUser] = useState<string>('Guest');
const userRef = useRef(user);

useEffect(() => {
  userRef.current = user;
}, [user]);

useEffect(() => {
  const handler = () => console.log(`Current active user: ${userRef.current}`);
  window.addEventListener('resize', handler);
  return () => window.removeEventListener('resize', handler);
}, []); // Bersih, listener stabil, closure tidak stale
```

### Kesalahan 2: Menggunakan Direct Array Mutation pada Functional Update
```typescript
// ANTI-PATTERN: Push memutasi array lama, referensi memori tidak berubah
const [list, setList] = useState<string[]>([]);
const addItem = (item: string) => {
  setList(prev => {
    prev.push(item); // MUTASI LANGSUNG!
    return prev;     // Object.is(prev, prev) === true. Render dibatalkan!
  });
};
```
* **Solusi Perbaikan:** Pastikan return value selalu berupa referensi memori yang baru