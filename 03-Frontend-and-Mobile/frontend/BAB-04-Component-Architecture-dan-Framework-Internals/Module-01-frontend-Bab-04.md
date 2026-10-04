# Bab 04 Module 01: Component Architecture & Framework Internals

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Frontend & Mobile Engineering
*   **Kategori:** 03-Frontend-and-Mobile
*   **Topik Utama:** Component Architecture & Framework Internals
*   **Prasyarat Konseptual:** JavaScript Advanced (ECMAScript 2022+), DOM API, Call Stack, Event Loop & Microtask Queue, Functional Programming Basics (Purity, Immutability, Higher-Order Functions).
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Target Audiens:** Senior Frontend Engineers, Technical Leads, dan Software Architects yang merancang UI library internal, performant design systems, dan aplikasi web skala enterprise.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1.  **Membongkar Mekanisme Reconciliation & Virtual DOM:** Mengartikulasikan secara matematis dan algoritmik cara kerja diferensiasi tree (diffing algorithm) dari kompleksitas $O(n^3)$ menjadi heuristik $O(n)$, serta membedakannya dengan Fine-Grained Reactivity (Signal Graph).
2.  **Mengimplementasikan Mini-Reactivity Engine:** Membangun reactive primitive (`signal`, `effect`, `computed`) dari dasar menggunakan arsitektur publish-subscribe berbasis dependency graph topological sorting.
3.  **Merancang Komponen Tingkat Lanjut (Component Patterns):** Mengimplementasikan Compound Components, Render Props, State Reducer Pattern, dan Custom Hooks secara idiomatis untuk meminimalkan coupling dan memaksimalkan ekstensibilitas API.
4.  **Menganalisis State Management Lifecycle:** Menjelaskan secara presisi batas (boundaries) siklus hidup komponen dari inisialisasi, batching re-render, passive effect scheduler, hingga teardown memori di browser runtime.
5.  **Mencegah Memory Leak dan Render Cascade:** Mendiagnosis degradasi performa pada tingkat garbage collection dan frame rate (60/120 FPS), serta mengeliminasi bottleneck rendering path melalui optimasi alokasi objek dan stabilisasi referensi memorisasi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Komponen sebagai Proyeksi Matematis Terhadap State

Banyak engineer pemula memandang komponen UI sebagai kumpulan template markup (HTML) yang disisipi logika interaktif (imperatif). Paradigma framework modern mengharuskan pergeseran mental model: **UI adalah proyeksi murni dari State pada suatu titik waktu ($t$).**

$$\text{UI} = f(\text{State})$$

Jika State berubah dari $S_0$ menjadi $S_1$, runtime framework bertanggung jawab mengomputasikan transisi visual:

$$\Delta \text{UI} = f(S_1) - f(S_0)$$

Tantangan fundamental dari arsitektur frontend adalah: *Bagaimana framework mendeteksi bahwa State berubah, dan bagaimana runtime mengeksekusi $\Delta \text{UI}$ ke Host Environment (DOM) secara minimal, deterministik, dan tanpa memblokir thread eksekusi utama browser?*

### VDOM Reconciliation vs. Fine-Grained Reactive Graphs

Terdapat dua mazhab utama dalam runtime UI modern:

```
+-----------------------------------------------------------------------------------+
|                            PARADIGMA FRAMEWORK RUNTIME                            |
+---------------------------------------------------------+-------------------------+
|                Virtual DOM (Component-Level)            |   Fine-Grained Signals  |
+---------------------------------------------------------+-------------------------+
| Karakteristik:                                          | Karakteristik:          |
| - Komponen dieksekusi ulang dari atas ke bawah.         | - Komponen dieksekusi   |
| - Menghasilkan pohon VNode baru dalam memori.           |   hanya SATU KALI       |
| - Diffing pohon lama vs baru (Reconciliation).          |   saat mount.           |
| - Komputasi terpusat pada diffing runtime.              | - DOM node diikat       |
| - Contoh: React.                                        |   langsung ke Signal.   |
|                                                         | - Zero reconciliation.  |
|                                                         | - Contoh: Solid, Svelte.|
+---------------------------------------------------------+-------------------------+
```

1.  **Virtual DOM (VDOM) Coarse-Grained Scheduling:** Ketika state berubah, framework mengeksekusi ulang fungsi komponen untuk membangun representasi virtual tree baru. Proses ini menukar efisiensi memori (alokasi objek VNode) demi fleksibilitas deklaratif runtime.
2.  **Fine-Grained Reactive Primitives (Signals):** Komponen bukanlah unit re-render, melainkan unit inisialisasi. Fungsi komponen dieksekusi satu kali untuk memasang dependensi. Ketika signal bernilai baru, subscriber langsung memutasi target DOM node tanpa rekursi pohon komponen.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Siklus Hidup Re-render VDOM (Reconciliation Loop)

Diagram alur berikut mengilustrasikan transisi state dari pemanggilan aksi pengguna hingga mutasi DOM riil, dipisahkan ke dalam fase Render dan fase Commit.

```
+-------------+
| User Action | (Contoh: onClick, input event)
+------+------+
       |
       v
+-------------+      Schedule Update
|  setState   | ------------------------+
+-------------+                         |
                                        v
                    +---------------------------------------+
                    |           SCHEDULER / BATCHER         |
                    | Mengelompokkan update microtask       |
                    +-------------------+-------------------+
                                        |
                                        v  [FASE RENDER: Murni, Bebas Efek Samping]
                    +---------------------------------------+
                    |          RECONCILER ENGINE            |
                    | 1. Eksekusi Component(props, state)   |
                    | 2. Generate WorkInProgress (WIP) Tree |
                    | 3. Heuristic Diffing:                 |
                    |    - Type Checking                    |
                    |    - Key Reconciliation               |
                    +-------------------+-------------------+
                                        |
                         Tree Sama?     |
                        +---------------+---------------+
                        |                               |
                     [Ya]                             [Tidak]
                        |                               |
                        v                               v
                 +--------------+               +---------------+
                 | Bailout      |               | Tandai Effect |
                 | (Skip Child) |               | Tag (Placement|
                 +--------------+               | Update, Delete|
                                                +-------+-------+
                                                        |
                                                        v  [FASE COMMIT: Sinkron & Mutatif]
                                        +-------------------------------+
                                        |       RENDERER (Host DOM)     |
                                        | Menerapkan mutasi ke DOM nyata|
                                        | node.appendChild(), dll.      |
                                        +---------------+---------------+
                                                        |
                                                        v
                                        +-------------------------------+
                                        |     POST-COMMIT (Layout/Idle) |
                                        | Eksekusi Lifecycle Hook /     |
                                        | Passive Effects (useEffect)   |
                                        +-------------------------------+
```

### Dependency Graph Resolusi Signal (Fine-Grained)

Ketika signal berubah, runtime harus menavigasi graf dependensi terarah (Directed Acyclic Graph) secara topologis untuk menghindari kesalahan komputasi sementara (*glitch*).

```
        [ Signal A ] (Value: 2)           [ Signal B ] (Value: 3)
             |                                 |
             +---------------+                 |
                             |                 |
                             v                 v
                      [ Computed C: A * B ] (Value: 6)
                             |
                             v
                      [ Computed D: C + 10 ] (Value: 16)
                             |
                             v
                      [ Effect: DOM Mutator ] -> Mutasi elemen span.textContent
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Struktur Objek Virtual DOM (VNode)

VNode adalah representasi JavaScript polos (*plain object*) dari sebuah node DOM. Contoh representasi internal VNode:

```typescript
interface VNode {
  type: string | ComponentFunction;
  props: Record<string, any> & { children?: VNode[] };
  key: string | number | null;
  dom: Node | null; // Referensi pointer langsung ke host environment
}
```

### 2. Heuristik Diffing ($O(n)$)

Masalah umum membandingkan dua pohon secara rekursif membutuhkan kompleksitas waktu $O(n^3)$ (Levenshtein distance pada pohon). Framework modern mereduksinya menjadi $O(n)$ berdasarkan dua asumsi heuristik:
1.  **Dua elemen dengan tipe yang berbeda akan menghasilkan pohon yang berbeda.** Jika tipe tag berubah dari `<div>` menjadi `<section>`, engine langsung menghancurkan seluruh subtree lama beserta instansinya tanpa memeriksa anaknya.
2.  **Developer dapat memberikan petunjuk elemen stabil melalui prop `key`.** Kunci stabilitas ini menginstruksikan reconciler untuk melacak elemen antar-render meski posisinya bergeser dalam array anak.

### 3. Anatomical Mechanics: Fiber / WorkInProgress Node

Dalam model konkuren (seperti React Fiber), stack rekursif digantikan oleh struktur data **Doubly-Linked List Tree**, memungkinkan proses render dijeda (*interruptible*), dibatalkan, atau dilanjutkan.

```typescript
interface FiberNode {
  type: any;
  key: string | null;
  stateNode: any;            // Pointer ke DOM instance atau class instance

  // Struktur Doubly-Linked Tree
  return: FiberNode | null;  // Pointer ke Parent Fiber
  child: FiberNode | null;   // Pointer ke Anak Pertama
  sibling: FiberNode | null; // Pointer ke Saudara Berikutnya

  // State & Effects
  pendingProps: any;
  memoizedProps: any;
  memoizedState: any;        // Linked-list dari Hooks (jika function component)
  flags: number;             // Bitwise mask: Placement, Update, Deletion
  alternate: FiberNode | null; // Pointer ke WorkInProgress / Current counterpart
}
```

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Alasan Algoritmik di Balik Larangan Melakukan Mutasi State Langsung

Mengapa framework seperti React mewajibkan immutability (misalnya `setState(prev => ({...prev, count: 1}))`) daripada `this.state.count = 1`?

Jawabannya berakar pada **efisiensi komputasi pengecekan ekuivalensi (Identity vs Structural Comparison)**.

Dalam JavaScript, perbandingan objek secara mendalam (*structural deep comparison*) memerlukan penelusuran rekursif terhadap seluruh *keys* dan *values*, yang memiliki kompleksitas $O(k)$ di mana $k$ adalah jumlah properti objek bertingkat:

```typescript
function isDeepEqual(objA: any, objB: any): boolean {
  if (Object.is(objA, objB)) return true;
  // Membutuhkan iterasi properti, refleksi tipe, dan rekursi mendalam...
  // Terlalu mahal dilakukan pada 60 FPS (setiap 16.6ms)
  return false;
}
```

Dengan mengadopsi prinsip **Immutability**, engine hanya perlu mengevaluasi referensi memori menggunakan perbandingan shallow / referensial:

$$\text{Object.is}(A, B) \implies O(1)$$

Jika referensi memori $A \neq B$, reconciler menyimpulkan bahwa sub-tree tersebut telah termutasi dan menjadwalkan render. Jika referensi sama ($A === B$), engine melakukan *bailout* (melewati proses komputasi render child component sepenuhnya).

### Batching & Microtask Coordination

Framework modern tidak memicu proses re-render secara sinkron setiap kali state dimutasi. Melakukan render secara sinkron untuk 10 kali pemanggilan `setState` berturut-turut akan memicu 10 kali layout recomputation dan pemborosan CPU.

Sebagai gantinya, framework memanfaatkan **Microtask Queue** JavaScript runtime:

```typescript
let isBatching = false;
const updateQueue = new Set<() => void>();

function scheduleUpdate(task: () => void) {
  updateQueue.add(task);
  if (!isBatching) {
    isBatching = true;
    queueMicrotask(flushUpdates);
  }
}

function flushUpdates() {
  try {
    for (const task of updateQueue) {
      task();
    }
  } finally {
    updateQueue.clear();
    isBatching = false;
  }
}
```

Ketika fungsi event handler selesai dieksekusi (Call Stack kosong), browser memeriksa Microtask Queue sebelum merender frame berikutnya. Seluruh state mutations dieksekusi dalam satu batch terkonsentrasi.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi **Mini-Reactivity Engine (Signals & Effects)** dari nol, yang menunjukkan bagaimana arsitektur tanpa Virtual DOM bekerja pada level sistem.

```typescript
// reactivity.ts

type Subscriber = () => void;

// Menyimpan efek yang sedang aktif dieksekusi
let activeEffect: Subscriber | null = null;

export interface Signal<T> {
  (): T;             // Getter
  (nextValue: T): void; // Setter
}

export function createSignal<T>(initialValue: T): Signal<T> {
  let value = initialValue;
  const subscribers = new Set<Subscriber>();

  function read(): T {
    if (activeEffect) {
      // Dependency Tracking: Tambahkan efek yang sedang berjalan ke daftar langganan
      subscribers.add(activeEffect);
    }
    return value;
  }

  function write(nextValue: T): void {
    if (!Object.is(value, nextValue)) {
      value = nextValue;
      // Dependency Notification: Jalankan seluruh subscriber yang bergantung pada signal ini
      // Salin Set untuk mencegah siklus rekursif tak terbatas saat iterasi
      const runQueue = Array.from(subscribers);
      runQueue.forEach((subscriber) => subscriber());
    }
  }

  return function accessor(nextValue?: T): any {
    if (arguments.length === 0) {
      return read();
    }
    write(nextValue as T);
  } as Signal<T>;
}

export function createEffect(effectFn: () => void): void {
  const execute = () => {
    const prevEffect = activeEffect;
    activeEffect = execute;
    try {
      effectFn();
    } finally {
      activeEffect = prevEffect;
    }
  };

  // Jalankan segera sekali untuk mendaftarkan dependency awal
  execute();
}

export function createComputed<T>(fn: () => T): () => T {
  const [readInternal, writeInternal] = [
    createSignal<T | undefined>(undefined),
    (val: T) => internalSignal(val)
  ];
  const internalSignal = createSignal<T>(undefined as unknown as T);

  createEffect(() => {
    internalSignal(fn());
  });

  return () => internalSignal();
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis implementasi `reactivity.ts` di atas:

*   **Baris 6: `let activeEffect: Subscriber | null = null;`**
    *   Variabel penampung global (*ambient context*). Menjadi jembatan sinkron (*synchronous context token*) antara saat `effect` mulai mengeksekusi fungsinya dan saat `read()` pada signal terpanggil di dalam fungsi tersebut.
*   **Baris 14: `const subscribers = new Set<Subscriber>();`**
    *   Penggunaan struktur data `Set` menjamin keunikan referensi listener. Mencegah duplikasi pendaftaran efek yang sama jika signal diakses berkali-kali dalam satu blok logika yang sama ($O(1)$ lookup dan deduplikasi).
*   **Baris 16–21: `function read(): T`**
    *   Mekanisme **Dependency Collection**. Saat dipanggil, fungsi membaca nilai `activeEffect`. Jika tidak null, artinya pembacaan terjadi di dalam konteks reaktif, sehingga runtime otomatis mendaftarkan efek tersebut sebagai dependensi dari signal bersangkutan.
*   **Baris 24–32: `function write(nextValue: T): void`**
    *   Mekanisme **Dirty Checking & Notification**. Evaluasi kesetaraan nilai baru dan lama dilakukan dengan `Object.is`. Jika nilai berubah, dibuat array snapshot dari `subscribers` sebelum iterasi dimulai (`Array.from(subscribers)`). Hal ini krusial untuk mencegah jebakan *infinite loop* jika sebuah effect menghapus dan mendaftarkan ulang dirinya sendiri saat eksekusi.
*   **Baris 40–53: `function createEffect(effectFn: () => void)`**
    *   Membungkus fungsi pengguna ke dalam closure `execute`. Sebelum fungsi pengguna dijalankan, `activeEffect` diisi dengan pointer ke dirinya sendiri. Setelah fungsi selesai, pointer dikembalikan ke `prevEffect` (mengadopsi struktur stack) untuk mendukung efek bersarang (*nested effects*).

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Masalah Produksi: Enterprise Real-Time Data Grid

Sebuah platform pertukaran aset keuangan (Financial Trading Desk) menampilkan tabel order book dengan **10.000 baris data aktif**. Setiap baris berisi informasi harga, kuantitas volume, pergerakan bid/ask, dan form interaktif untuk mengeksekusi order instan.

```
+-----------------------------------------------------------------------------------------+
| SIMULASI TICKER STREAM: WebSocket (50 pesan / detik)                                   |
+-----------------------------------------------------------------------------------------+
| Order Book Row #1  | BTC-USD | $64,230.50 | +1.2% | [ Quick Buy ]                       |
| Order Book Row #2  | ETH-USD |  $3,450.10 | -0.5% | [ Quick Buy ]                       |
| ...                | ...     | ...        | ...   | ...                                 |
| Order Book Row #9k | SOL-USD |   $145.20 | +5.4% | [ Quick Buy ]                       |
+-----------------------------------------------------------------------------------------+
```

### Masalah Arsitektur:
1.  **Render Cascades:** Pembaruan harga pada 1 instrumen (misalnya: BTC-USD) menyebabkan seluruh tabel (10.000 komponen baris) me-render ulang karena state disimpan pada tingkat *Root Component* tanpa batas rekonkiliasi yang tepat.
2.  **Thread Starvation & Input Latency:** Browser Main Thread membeku (*long tasks* > 250ms), menyebabkan aksi pengguna (seperti mengetikkan angka pada input field Quick Buy) mengalami freezing parah (*high Input Delay*, drop frame hingga < 15 FPS).
3.  **Memory Thrashing:** Alokasi puluhan ribu objek Virtual DOM baru per detik memicu *Garbage Collection (GC) pauses* secara berkala.

### Solusi Desain Komponen:
1.  Isolasi sub-pohon melalui **Compound Components & Localized State**.
2.  Penggunaan **State Reducer Pattern** untuk menyatukan transisi state kompleks.
3.  Implementasi kontrol referensial dan stabilisasi listener menggunakan teknik memory anchoring.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi arsitektur komponen modular performa tinggi menggunakan pola **Compound Component** yang diintegrasikan dengan pemisahan konteks pembacaan dan pemutakhiran data secara terisolasi.

```tsx
// TradingGrid.tsx
import React, {
  createContext,
  useContext,
  useReducer,
  useMemo,
  useCallback,
  useRef,
  memo,
  ReactNode,
  Dispatch
} from "react";

// --- DOMAIN TYPES ---
export interface OrderItem {
  id: string;
  symbol: string;
  price: number;
  volume: number;
}

interface GridState {
  orders: Record<string, OrderItem>;
  orderIds: string[];
}

type GridAction =
  | { type: "UPDATE_TICK"; payload: { id: string; price: number; volume: number } }
  | { type: "BATCH_UPDATE"; payload: OrderItem[] };

// --- STATE MANAGEMENT INTERNALS ---
function gridReducer(state: GridState, action: GridAction): GridState {
  switch (action.type) {
    case "UPDATE_TICK": {
      const { id, price, volume } = action.payload;
      const target = state.orders[id];
      if (!target || (target.price === price && target.volume === volume)) {
        return state; // Bailout: Hindari alokasi referensi baru jika data identik
      }
      return {
        ...state,
        orders: {
          ...state.orders,
          [id]: { ...target, price, volume }
        }
      };
    }
    case "BATCH_UPDATE": {
      const newOrders = { ...state.orders };
      let hasChanged = false;

      for (const item of action.payload) {
        const existing = newOrders[item.id];
        if (!existing || existing.price !== item.price || existing.volume !== item.volume) {
          newOrders[item.id] = item;
          hasChanged = true;
        }
      }

      if (!hasChanged) return state;

      return {
        orderIds: Object.keys(newOrders),
        orders: newOrders
      };
    }
    default:
      return state;
  }
}

// --- SEPARATED CONTEXT ARCHITECTURE (Mencegah Render Cascade) ---
const GridDataStateContext = createContext<GridState | null>(null);
const GridDispatchContext = createContext<Dispatch<GridAction> | null>(null);

// --- ROOT COMPONENT (Provider Compound Pattern) ---
export interface TradingGridProps {
  initialOrders: OrderItem[];
  children: ReactNode;
}

export function TradingGrid({ initialOrders, children }: TradingGridProps) {
  const [state, dispatch] = useReducer(gridReducer, {
    orders: initialOrders.reduce((acc, curr) => ({ ...acc, [curr.id]: curr }), {}),
    orderIds: initialOrders.map((o) => o.id)
  });

  return (
    <GridDispatchContext.Provider value={dispatch}>
      <GridDataStateContext.Provider value={state}>
        <div className="trading-grid-container" role="table">
          {children}
        </div>
      </GridDataStateContext.Provider>
    </GridDispatchContext.Provider>
  );
}

// --- CONSUMPTION HOOKS DENGAN INVARIANT ASSERTION ---
export function useGridDispatch(): Dispatch<GridAction> {
  const context = useContext(GridDispatchContext);
  if (!context) {
    throw new Error("useGridDispatch harus digunakan di dalam komponen <TradingGrid />");
  }
  return context;
}

function useOrderItem(id: string): OrderItem | undefined {
  const state = useContext(GridDataStateContext);
  if (!state) {
    throw new Error("useOrderItem harus digunakan di dalam komponen <TradingGrid />");
  }
  return state.orders[id];
}

export function useGridOrderIds(): string[] {
  const state = useContext(GridDataStateContext);
  if (!state) {
    throw new Error("useGridOrderIds harus digunakan di dalam komponen <TradingGrid />");
  }
  return state.orderIds;
}

// --- LEAF COMPONENT: OPTIMIZED ROW ---
interface OrderRowProps {
  id: string;
  onExecuteTrade: (id: string, price: number) => void;
}

export const OrderRow = memo(function OrderRow({ id, onExecuteTrade }: OrderRowProps) {
  const item = useOrderItem(id);
  // Ref stabil untuk callback aksi guna menghindari regenerasi fungsi anonim
  const tradeHandlerRef = useRef(onExecuteTrade);
  tradeHandlerRef.current = onExecuteTrade;

  const handleAction = useCallback(() => {
    if (item) {
      tradeHandlerRef.current(item.id, item.price);
    }
  }, [item?.id, item?.price]);

  if (!item) return null;

  return (
    <div className="order-row" role="row" style={{ display: "flex", gap: "1rem" }}>
      <span role="cell" className="font-mono">{item.symbol}</span>
      <span role="cell" className="font-mono">{item.price.toFixed(2)}</span>
      <span role="cell" className="font-mono">{item.volume}</span>
      <button role="cell" onClick={handleAction}>
        Execute
      </button>
    </div>
  );
});

// --- COMPOSABLE SUB-COMPONENTS EXPORTS ---
TradingGrid.Row = OrderRow;
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter | React (VDOM Reconciliation) | SolidJS (Fine-Grained Signals) | Svelte (Compile-Time Reactivity) |
| :--- | :--- | :--- | :--- |
| **Mekanisme Reaktif** | Runtime Diffing Pohon Virtual | Dependency Graph Objek Reaktif | Static Analysis AST Transformations |
| **Overhead Runtime Memory** | Tinggi (Membuat node VDOM & Fiber ganda) | Rendah (Hanya objek Signal & Subscription) | Sangat Rendah (Mutasi langsung native element) |
| **Ukuran Bundle Baseline** | Relatif Besar (~40KB gzip untuk runtime) | Sedang (~7KB gzip runtime) | Minimal (~1-2KB baseline, tumbuh linear) |
| **Interoperabilitas Dinamis** | Sangat Tinggi (Bebas mengevaluasi JSX dinamis) | Tinggi (JSX bertransformasi ke native node) | Terbatas pada batas-batas sintaks template |
| **Karakteristik CPU** | Lonjakan siklus CPU pada diffing massal | Distribusi stabil, tanpa fase diffing | Sangat ringan pada eksekusi runtime browser |
| **Batas Mental Model** | Kepatuhan mutlak aturan Immutability | Eksplisit Get/Set, siklus hidup transparan | Sintaks assignments `$:` berbasis compiler |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Zombie Child Problem
*   **Kasus:** Terjadi saat arsitektur reaktif berbasis sub-store mengeksekusi listener pada child component sebelum parent component menyelesaikan render penghapusan node tersebut.
*   **Dampak:** Child component mencoba membaca data dari store menggunakan ID yang sudah tidak valid di database/state, menyebabkan lemparan eksepsi `TypeError: Cannot read properties of undefined`.
*   **Mitigasi:** Struktur reconciler harus menjamin urutan eksekusi **Top-Down Subscriber Notification** atau menerapkan validasi defensif (*null check bailout*) di level selektor komponen lokal.

### 2. Stale Closures pada Event Listeners & Effect
*   **Kasus:** Mengakses nilai state/props di dalam closure asinkron atau `useEffect` tanpa array dependensi yang sinkron.
*   **Dampak:** Komponen mengeksekusi logika menggunakan snapshot data masa lalu yang sudah tidak valid.
*   **Mitigasi:** Gunakan `useRef` sebagai mutable container yang nilainya selalu diperbarui di setiap render untuk closure yang bersifat long-lived.

### 3. De-optimizasi Objek JSX Children Melalui Inlined Expressions
*   **Kasus:** Menulis kode seperti `<Parent><Child /></Parent>`. Elemen `<Child />` ditranspilasi menjadi `React.createElement(Child, null)`.
*   **Dampak:** Meskipun `Parent` dioptimasi menggunakan `memo`, properti `props.children` **selalu mendapatkan referensi objek baru** di setiap iterasi render induk terluar, membatalkan optimasi `memo`.
*   **Mitigasi:** Lewatkan referensi elemen yang sudah dimemorisasi (`useMemo(() => <Child />, [])`) atau ubah struktur hierarki komponen ke bentuk flat/isolated composition.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menggunakan Array Index Sebagai React `key`

```tsx
// SALAH: Penggunaan index sebagai identitas reconciliation
{items.map((item, index) => (
  <ListItem key={index} data={item} />
))}
```

*   **Penyebab Masalah:** Jika sebuah item dihapus atau disisipkan di posisi tengah, index semua item setelahnya akan bergeser. Reconciler mengira elemen terakhir yang dihapus dan mengeksekusi update mutasi teks/input secara salah pada elemen lainnya, merusak local state (misalnya isi form input).
*   **Perbaikan:** Selalu gunakan ID deterministik yang unik secara struktural.

```tsx
// BENAR: Penggunaan identifier entitas yang persisten
{items.map((item) => (
  <ListItem key={item.id} data={item} />
))}
```

---

### 2. Memisahkan State yang Seharusnya Atomik

```tsx
// SALAH: State terfragmentasi yang memicu tearing & re-render berkali-kali
const [isLoading, setIsLoading] = useState(false);
const [data, setData] = useState<Data | null>(null);
const [error, setError] = useState<Error | null>(null);

function fetchData() {
  setIsLoading(true);
  api.get()
    .then(res => { setData(res); setIsLoading(false); })
    .catch(err => { setError(err); setIsLoading(false); });
}
```

*   **Penyebab Masalah:** Pembaruan tiga variabel state terpisah dapat memicu rendering parsial di lingkungan non-batched runtime lama, serta meningkatkan risiko kombinasi state ilegal (seperti `isLoading === false`, `data === null`, dan `error === null`).
*   **Perbaikan:** Gunakan diskriminasi union dengan `useReducer`.

```tsx
// BENAR: Finite State Machine yang atomik
type FetchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: Data }
  | { status: 'error'; error: Error };
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Rule of Separation: UI Rendering Context vs Action Context:** Jangan campurkan objek State yang sering berubah dengan fungsi mutator (dispatch) dalam satu Context Provider. Buat dua provider terpisah agar komponen yang hanya butuh memicu aksi tidak terpaksa me-render ulang saat state berubah.
2.  **Inversion of Control (IoC) via Compound Components:** Berikan kendali komposisi DOM kepada konsumen modul tanpa mengekspos internal state loop komponen tersebut secara terbuka.
3.  **Strict Purity dalam Fase Render:** Pastikan blok fungsi komponen bersih dari *side-effects* (tidak ada mutasi variabel luar, tidak ada network call sinkron, tidak ada pendaftaran DOM listener manual). Seluruh efek samping harus diisolasi di fase post-commit (`useEffect` / passive runner).
4.  **Colocation State:** Simpan state sedekat mungkin dengan tempat ia digunakan. Memindahkan seluruh state ke Global Store (Redux/Zustand) tanpa pertimbangan modularitas memicu overhead tracing dan isolasi data yang buruk.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Stabilisasi Alokasi Hidden Classes V8
JavaScript engine (V8) mengoptimalkan properti objek menggunakan **Hidden Classes (Maps)**. Jika Anda merancang komponen yang menerima opsi dinamis, pertahankan urutan dan bentuk properti objek yang konstan. Menghapus properti menggunakan operator `delete` mengubah hidden class objek secara drastis (*de-optimization to dictionary mode*). Gunakan passing `undefined` alih-alih `delete`.

### 2. Penataan Dependensi Menggunakan Shallow Dependency Hashing
Hindari penggunaan objek/array non-primitif sebagai dependensi memo hook:

```tsx
// TIDAK EFISIEN: Dibuat ulang setiap render, membatalkan useMemo
useMemo(() => computeHeavy(options), [{ threshold: 10 }]);

// EFISIEN: Ekstraksi nilai primitif eksplisit
useMemo(() => computeHeavy({ threshold }), [threshold]);
```

### 3. Windowing & Virtualization
Untuk dataset lebih dari 1.000 elemen, render DOM secara parsial menggunakan algoritma virtualisasi windowing:
*   Hanya render elemen yang masuk ke dalam Viewport Container:
    $$\text{StartIndex} = \lfloor \text{scrollTop} / \text{itemHeight} \rfloor$$
    $$\text{EndIndex} = \lfloor (\text{scrollTop} + \text{viewportHeight}) / \text{itemHeight} \rfloor$$
*   Gunakan transform `translateY` untuk memposisikan container baris tanpa merekonstruksi seluruh tree dokumen DOM.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Injeksi XSS Melalui Sintaks Render Dinamis
Framework modern secara default melakukan auto-escaping terhadap string di dalam template rendering. Namun, kerentanan kritis muncul saat developer memanfaatkan mekanisme escape-hatch:

```tsx
// POTENSI EKSPLOITASI XSS TINGKAT TINGGI
<div dangerouslySetInnerHTML={{ __html: userProvidedPayload }} />
```

*   **Hardening Protocol:** Wajib membersihkan payload HTML menggunakan sanitizer parser berbasis AST (seperti `DOMPurify`) sebelum diserahkan ke pipeline kompilasi framework:
```tsx
import DOMPurify from "dompurify";

const sanitizedMarkup = DOMPurify.sanitize(userProvidedPayload, {
  USE_PROFILES: { html: true },
  FORBID_TAGS: ["script", "iframe", "object", "embed"],
  FORBID_ATTR: ["onerror", "onload", "onclick"]
});

<div dangerouslySetInnerHTML={{ __html: sanitizedMarkup }} />
```

### 2. JSON State Hydration Injection
Saat melakukan Server-Side Rendering (SSR), developer sering meletakkan serialized state ke tag script:

```html
<!-- RENTAN: Jika state payload mengandung string "</script><script>maliciousCode()</script>" -->
<script>
  window.__INITIAL_STATE__ = ${JSON.stringify(state)};
</script>
```

*   **Mitigasi Sanitasi:** Gantikan karakter unsafe Unicode pada output serialisasi:
```typescript
function safeSerialize(state: any): string {
  return JSON.stringify(state).replace(/</g, '\\u003c');
}
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

### 1. Programmatic Performance Tracing dengan `Profiler`

Gunakan native framework instrumentation API untuk melacak durasi commit subtree dan membuang datanya ke platform telemetri (misalnya OpenTelemetry):

```tsx
import React, { Profiler, ProfilerOnRenderCallback } from "react";

const onRenderCallback: ProfilerOnRenderCallback = (
  id, // string id prop dari Profiler tree yang dimonitor
  phase, // "mount" atau "update"
  actualDuration, // Waktu eksekusi render subtree (ms)
  baseDuration, // Estimasi waktu render tanpa memoization (ms)
  startTime, // Waktu saat render dimulai
  commitTime // Waktu commit ke host renderer
) => {
  if (actualDuration > 16.6) {
    // Terjadi drop frame (< 60 FPS)! Kirim telemetry event
    navigator.sendBeacon("/telemetry/perf", JSON.stringify({
      componentId: id,
      phase,
      duration: actualDuration,
      slowdownRatio: actualDuration / baseDuration,
      