# Bab 07 Module 01: State Management Terdesentralisasi & Skala Besar

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 03-Frontend-and-Mobile
* **Teknologi Utama:** Angular v17+ / v18 (Modern Standalone Architecture, Signal Store, NgRx ComponentStore, Signals Reactive Graph)
* **Topik:** State Management Terdesentralisasi & Skala Besar (Decentralized & Enterprise-Scale State Management)
* **Level Teknis:** Advanced / Staff Engineer
* **Prasyarat Pengetahuan:** 
  * Reactive Programming mendalam menggunakan RxJS (`pipe`, `switchMap`, `exhaustMap`, `shareReplay`, `Subject`).
  * Angular Core Primitives: Signals (`signal`, `computed`, `effect`, `untracked`), Injector Tree, Dependency Injection Scope (`providedIn: 'root'` vs Component/Node Injector).
  * Arsitektur Enterprise Angular: Smart-Dumb Components, Micro-frontends, Lazy Loaded Feature Boundaries.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik mampu:
1. **Mendiagnosis & Mengeliminasi Bottleneck Single-Store Monolith:** Menguraikan kegagalan performa, collision overhead, dan memory retention dari arsitektur Global Store tunggal (klasik NgRx/Redux) pada aplikasi berskala jutaan pengguna dan puluhan feature domain.
2. **Merancang Topologi Desentralisasi State:** Mengimplementasikan pola isolasi state berbasis *Feature-Scoped Context*, *Component-Level Transient State*, dan *Shared Cross-Domain State* menggunakan `@ngrx/signals` (NgRx SignalStore) dan `@ngrx/component-store`.
3. **Menguasai Hierarki Dependency Injection untuk State Scoping:** Mengontrol siklus hidup (*lifecycle*) state dengan memanfaatkan Angular Hierarchical Injectors, menjamin garbage collection otomatis pada state ketika komponen/rute dihancurkan (*destroy*).
4. **Membangun Signal-Driven Reactive Pipeline:** Mengonstruksi pipeline aliran data deterministik dan race-condition-free menggunakan integrasi Angular Signals dan RxJS Interop (`toSignal`, `toObservable`).
5. **Menerapkan Telemetri, Auditing, & Immutability Hardening:** Mengimplementasikan middleware pelacakan state (custom SignalStore features), Deep Immutability Guards, serta mekanisme debugging observabilitas tinggi untuk sistem enterprise.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Monolith State vs Federated/Decentralized State
Arsitektur state management frontend tradisional sering kali memaksakan satu *single source of truth* global (Single State Tree). Pola ini berhasil pada aplikasi skala kecil-menengah, namun runtuh pada skala enterprise (Micro-frontends, monorepo dengan ratusan engineer):

```
MONOLITHIC STORE (Anti-Pattern pada Skala Besar)
[ Global State Tree (Mega Object) ]
  ├── Feature A State (Orders)
  ├── Feature B State (Catalog)
  ├── Feature C State (User Session)
  └── Feature D State (Ephemeral UI State - modal terbuka, form step)
  * Problem: Reducer collision, high serialization cost, memory leak, coupling tinggi.

FEDERATED / DECENTRALIZED STATE (Modern Enterprise Pattern)
[ Global Domain Context ] -> Session, Auth, Layout Engine (Root Injector)
      │
      ├── [ Scoped Subsystem State ] -> Bounded Context (Feature Route Injector)
      │         │
      │         └── [ Ephemeral Local State ] -> Isolated UI Component (Element Injector)
```

### Mental Model: Lifetime Scope = Dependency Injection Node
Alih-alih menyimpan seluruh UI state di global store dan mengosongkannya secara manual via action `RESET_STATE` saat navigasi (yang rawan human error dan kebocoran memori), perlakukan state store sebagai **instansi terikat lifecycle (Scoped Dependency)**:
* **Global State:** Hidup selama aplikasi berjalan (Single Page App session). Tempat untuk Identity, Tokens, Device Profile.
* **Feature/Domain State:** Hidup selama user berada di dalam Bounded Context (misal: modul `/checkout`). Dibuat saat rute dimuat, dihancurkan saat user beralih ke rute `/dashboard`.
* **Component Transient State:** Hidup bersama komponen individual (misal: tabel virtual dengan pagination, sorting, dan draft row). Dibuat saat komponen di-render, otomatis terkena Garbage Collection (GC) saat DOM di-unmount.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur komunikasi terdesentralisasi membagi state ke dalam tiga layer: Layer Global (Shared Service), Layer Scoped Feature (SignalStore via Route Providers), dan Layer Transient View (Component Store via Node Providers).

```
+---------------------------------------------------------------------------------------+
|                                    APPLICATION ROOT                                   |
|   +-------------------------------------------------------------------------------+   |
|   |                          Root Auth & Session State                             |   |
|   |   (SignalStore / Signal Service: providedIn: 'root', Persisted across routes)  |   |
|   +---------------------------------------+---------------------------------------+   |
+-------------------------------------------|-------------------------------------------+
                                            | (Read-Only Signal Propagation)
                                            v
+---------------------------------------------------------------------------------------+
|                    ROUTE INJECTOR: /orders (Lazy-Loaded Feature)                      |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                            OrderDomainFacadeStore                             |   |
|   |   - Lifecycle: Instantiated at Route Activation, GC'd at Route Exit           |   |
|   |   - State: activeOrders[], filterCriteria, loadingState, pagination           |   |
|   |   - Extensions: withEntities(), withMethods(), withHooks()                     |   |
|   +---------------------------------------+---------------------------------------+   |
|                                           |                                           |
|             +-----------------------------+-----------------------------+             |
|             | (Provides Isolated Context)                               |             |
|             v                                                           v             |
|   +------------------------------------+      +------------------------------------+  |
|   | COMPONENT TREE: OrderTableComponent|      | COMPONENT TREE: OrderFilterDrawer  |  |
|   | (Node Injector Provider)           |      | (Node Injector Provider)           |  |
|   |                                    |      |                                    |  |
|   | +--------------------------------+ |      | +--------------------------------+ |  |
|   | | TableTransientStore            | |      | | DrawerTransientStore           | |  |
|   | | - selectedRowIds: Set<string>  | |      | | - formDraftState               | |  |
|   | | - columnWidths: Map<string,num>| |      | | - isDirty: boolean             | |  |
|   | +--------------------------------+ |      | +--------------------------------+ |  |
|   | Automatically GC'd on ngOnDestroy  |      | Automatically GC'd on close/exit   |  |
|   +------------------------------------+      +------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

### Siklus Sinkronisasi Terdesentralisasi

```
[ User Interaction ] 
        │
        ▼
[ Transient UI Store (Component Node) ] ──(Trigger Business Effect)──┐
        │                                                            │
  (Local Update: Instant UI Feedback)                                ▼
        │                                            [ Feature Domain Store (Route Node) ]
        │                                                            │
        │                                            (Optimistic Update / API Execution)
        │                                                            │
        ▼                                                            ▼
[ Template Local Re-Render ] <───(Computed Signals Propagation)─── [ HTTP Backend ]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Reactive Graph (Signals Engine)
Angular Signals menggunakan push-pull reactivity model dengan *glitch-free guarantee*:
* **Producer Nodes:** Primitif reaktif yang menyimpan nilai (`signal()`).
* **Consumer Nodes:** Node kalkulasi atau efek (`computed()`, `effect()`) yang mendaftarkan dependensi secara dinamis saat proses evaluasi nilai.
* **Topological Sorting:** Ketika producer berubah, status *dirty* dipropagasikan ke seluruh directed acyclic graph (DAG) secara instan (push phase). Namun kalkulasi nilai turunan (`computed`) ditunda sampai nilai tersebut benar-benar dibaca (pull/lazy evaluation phase). Hal ini mencegah eksekusi berulang yang lazim terjadi pada `combineLatest` RxJS tradisional.

### 2. NgRx SignalStore Under The Hood
`@ngrx/signals` dibangun di atas arsitektur modular fungsional berbasis TypeScript composition:
* **Composite State:** Dibangun menggunakan chaining `signalStore(withState(...), withComputed(...), withMethods(...))`.
* **State Slicing:** Setiap key di dalam root state store secara otomatis diekspos sebagai signal tersendiri via `DeepSignal<T>`.
* **Proxy-based Nested Reading:** SignalStore mengimplementasikan JavaScript Proxy untuk traversal nested state tanpa harus membuat manual computed signal per property.
* **Micro-patch Batching:** Eksekusi `patchState(store, ...)` menggunakan update bertahap yang atomic. Perubahan dieksekusi secara sinkron, namun pemicuan change detection template Angular dipadukan ke dalam siklus render frame berikutnya.

### 3. Tree-Scattered Injector Mechanics
* **Element Injector vs Environment Injector:**
  * Komponen mendeklarasikan `providers: [OrderTableStore]` pada decorator `@Component`.
  * Angular Engine membuat instance baru `OrderTableStore` pada `NodeInjector` yang terikat langsung ke `LView` (Logical View) komponen tersebut.
  * Ketika komponen di-destroy dari DOM, Angular membersihkan `LView`, memutus referensi dependensi, dan memanggil lifecycle hook `onDestroy` pada service yang bersangkutan, memungkinkan Garbage Collector mesin V8 membebaskan alokasi heap memory secara instan.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### State Colocation vs Global Serialization
Hukum **State Colocation** menyatakan: *"Let state exist as close to where it is needed as possible."*
Ketika state dialirkan terlalu tinggi ke global store:
1. **Serialization Tax:** Objek raksasa harus di-klon (`structuredClone` atau spread operator `...`) pada setiap mutasi action reducer, memicu memory churn dan GC pauses di thread utama browser.
2. **Context Leakage:** Data transient seperti `filterDropdownOpen: true` terekspos ke domain lain yang tidak memiliki hak konsumsi terhadap UI tersebut.

### Concurrency & Race Condition Resolution
Dalam arsitektur terdesentralisasi, beberapa komponen dapat memicu mutasi asinkron secara simultan. Kita harus membedakan strategi konkurensi pada tingkat store:

| Operator RxJS | Pola Kasus di SignalStore Methods | Alasan Teknis |
|---|---|---|
| `switchMap` | Pencarian teks / Autocomplete | Membatalkan request API sebelumnya jika term baru diketik; menghindari data out-of-order. |
| `exhaustMap` | Submit transaksi pembayaran | Mengabaikan klik lanjutan user sampai request saat ini selesai dieksekusi; mencegah duplikasi state. |
| `concatMap` | Queue upload data berurutan | Menjamin urutan eksekusi mutasi FIFO secara deterministik. |
| `mergeMap` | Fetch detail paralel | Memproses data sebanyak mungkin secara independen tanpa membatalkan thread lain. |

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bertahap untuk membangun Decentralized Feature Store menggunakan `@ngrx/signals` yang mengisolasi Entity State, Derived Analytics, dan Asynchronous I/O.

### Langkah 1: Definisi Entity & Contract
```typescript
// order.model.ts
export interface Order {
  readonly id: string;
  readonly customerId: string;
  readonly amount: number;
  readonly currency: 'IDR' | 'USD';
  readonly status: 'PENDING' | 'PAID' | 'SHIPPED' | 'CANCELLED';
  readonly createdAt: string;
}

export interface OrderFilter {
  readonly search: string;
  readonly status: Order['status'] | 'ALL';
}
```

### Langkah 2: Konstruksi SignalStore Terdesentralisasi
```typescript
// order-feature.store.ts
import { computed, inject } from '@angular/core';
import { 
  signalStore, 
  withState, 
  withComputed, 
  withMethods, 
  patchState 
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { pipe, switchMap, tap } from 'rxjs';
import { tapResponse } from '@ngrx/operators';
import { HttpClient } from '@angular/common/http';

export interface OrderState {
  orders: Order[];
  filter: OrderFilter;
  isLoading: boolean;
  selectedOrderId: string | null;
}

const initialOrderState: OrderState = {
  orders: [],
  filter: { search: '', status: 'ALL' },
  isLoading: false,
  selectedOrderId: null,
};

export const OrderFeatureStore = signalStore(
  // Menetapkan store ini untuk injectable manual atau scoped providers
  withState(initialOrderState),
  
  withComputed(({ orders, filter, selectedOrderId }) => ({
    // Derived state murni tanpa redundant signals
    filteredOrders: computed(() => {
      const currentFilter = filter();
      const currentOrders = orders();
      
      return currentOrders.filter((order) => {
        const matchesSearch = order.customerId
          .toLowerCase()
          .includes(currentFilter.search.toLowerCase());
        const matchesStatus = 
          currentFilter.status === 'ALL' || order.status === currentFilter.status;
        return matchesSearch && matchesStatus;
      });
    }),
    
    totalRevenue: computed(() => {
      return orders()
        .filter((o) => o.status === 'PAID')
        .reduce((acc, curr) => acc + curr.amount, 0);
    }),

    selectedOrder: computed(() => {
      const id = selectedOrderId();
      if (!id) return null;
      return orders().find((o) => o.id === id) ?? null;
    })
  })),

  withMethods((store, http = inject(HttpClient)) => ({
    updateFilter(filter: Partial<OrderFilter>): void {
      patchState(store, (state) => ({
        filter: { ...state.filter, ...filter }
      }));
    },

    selectOrder(id: string | null): void {
      patchState(store, { selectedOrderId: id });
    },

    // Asynchronous Side Effect Handler via rxMethod
    loadOrdersByCustomerId: rxMethod<string>(
      pipe(
        tap(() => patchState(store, { isLoading: true })),
        switchMap((customerId) =>
          http.get<Order[]>(`/api/v1/customers/${customerId}/orders`).pipe(
            tapResponse({
              next: (orders) => patchState(store, { orders, isLoading: false }),
              error: (error: Error) => {
                patchState(store, { isLoading: false });
                console.error('Critical Fetch Failure:', error);
              }
            })
          )
        )
      )
    )
  }))
);
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi arsitektural dari implementasi `OrderFeatureStore` di Seksi 07:

1. **`export const OrderFeatureStore = signalStore(...)`**
   * Menghasilkan Factory Class token Injectable Angular. Berbeda dari service Angular konvensional dengan decorator `@Injectable()`, pemanggilan `signalStore()` menghasilkan struktur modular berbasis mixins yang *tree-shakable*.
2. **`withState(initialOrderState)`**
   * Menginisialisasi state primitive dasar. Secara internal, setiap properti (`orders`, `filter`, `isLoading`, `selectedOrderId`) dipecah menjadi `WritableSignal` reaktif mandiri yang dapat diakses langsung oleh konsumen store.
3. **`withComputed(({ orders, filter, selectedOrderId }) => ({ ... }))`**
   * Menggunakan destructuring untuk mengambil *deep signals* internal store. Semua computed di sini dievaluasi secara *lazy*. Jika tidak ada komponen aktif di layar yang membaca `totalRevenue()`, komputasi array `reduce` tidak akan pernah dijalankan di thread CPU.
4. **`patchState(store, (state) => ({ ... }))`**
   * Fungsi mutasi atomic formal. Penggunaan updater function `(state) => ({ ... })` memastikan state transition dievaluasi berdasarkan nilai state paling mutakhir, mencegah *stale closures* pada eksekusi asinkron multi-threading event-loop.
5. **`rxMethod<string>(pipe(...))`**
   * Menjembatani dunia Signals dan RxJS. `rxMethod` menerima stream reaktif (`Observable`), data non-reaktif (`string`), atau `Signal` sebagai trigger. Pipeline internal mengontrol konkurensi pemanggilan network I/O.
6. **`switchMap(...)` di dalam `rxMethod`**
   * Menjamin perlindungan *race condition*. Jika user memicu pencarian order ID A, lalu segera berganti ke ID B sebelum request A selesai, response dari request A dibatalkan pada transport level (jika didukung HTTP client) dan diabaikan dari mutasi state.

---

## SEKSI 09 — STUDI KASUS NYATA (Enterprise Scenario)

### Konteks Bisnis & Beban Sistem
Sistem FinTech Multi-Tenant: **Core Treasury & Trading Desk Portal**.
* **Beban Data:** Ribuan pembaruan kurs mata uang masuk per detik melalui WebSocket.
* **Kompleksitas UI:** Tabulasi dinamis workspace di mana pengguna dapat membuka hingga 10 tab order-book independen secara bersamaan.
* **Isu pada Arsitektur Lama:**
  * Penggunaan Global NgRx Monolith menyebabkan action dispatch rate mencapai 800 actions/detik.
  * DevTools Redux membeku (*freeze*).
  * Seluruh aplikasi mengalami UI micro-stutters karena selector global dievaluasi ulang di seluruh komponen yang tidak berkepentingan.
  * Saat tab ditutup, data order book tetap tersimpan di dalam global state tree, menyebabkan browser kehabisan alokasi RAM (Chrome OOM crash) setelah 4 jam penggunaan aktif.

### Solusi Desentralisasi
1. **Root Scope:** Hanya menyimpan Session Identity, Tenant Key, dan global Socket Connection.
2. **Tab Workspace Scope (Node Injector):** Setiap tab order-book menginstansiasi Store terpisah via providers komponen induk tab tersebut.
3. **Data Ingestion Pipe:** Mengonversi data stream WebSocket berfrekuensi tinggi menggunakan *sampling/micro-batching window* sebelum dipasok ke signal store lokal tab, sepenuhnya mengisolasi kalkulasi DOM hanya ke tab yang sedang aktif ditampilkan.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA

Berikut adalah implementasi end-to-end arsitektur terdesentralisasi untuk skenario Trading Desk Workspace, menggunakan custom SignalStore Extension untuk Observabilitas Audit Log.

### 1. Custom Reusable Feature Extension: WithAuditing
```typescript
// auditing.feature.ts
import { signalStoreFeature, withHooks } from '@ngrx/signals';
import { effect } from '@angular/core';

export function withAuditing(featureName: string) {
  return signalStoreFeature(
    withHooks({
      onInit(store) {
        if (typeof window !== 'undefined' && (window as unknown as { DEBUG_STATE: boolean }).DEBUG_STATE) {
          effect(() => {
            // Membaca internal state snapshot via untracked logging
            console.groupCollapsed(`[AUDIT TRACE] :: Domain: ${featureName} at ${new Date().toISOString()}`);
            console.log('Store Mutation Snapshot:', store);
            console.groupEnd();
          });
        }
      },
      onDestroy() {
        console.info(`[DEALLOCATION TRACE] :: Scoped Store for [${featureName}] has been GC'd.`);
      }
    })
  );
}
```

### 2. Tab Scoped Order Book SignalStore
```typescript
// order-book.store.ts
import { inject } from '@angular/core';
import { 
  signalStore, 
  withState, 
  withMethods, 
  patchState, 
  withComputed 
} from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { pipe, bufferTime, filter } from 'rxjs';
import { computed } from '@angular/core';
import { withAuditing } from './auditing.feature';
import { WebSocketStreamService } from './websocket-stream.service';

export interface MarketTick {
  price: number;
  volume: number;
  timestamp: number;
}

export interface OrderBookState {
  symbol: string;
  bids: MarketTick[];
  asks: MarketTick[];
  lastPrice: number;
  connectionStatus: 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING';
}

export function createOrderBookStore(symbol: string) {
  return signalStore(
    withState<OrderBookState>({
      symbol,
      bids: [],
      asks: [],
      lastPrice: 0,
      connectionStatus: 'DISCONNECTED',
    }),
    withAuditing(`OrderBook-[${symbol}]`),
    withComputed(({ bids, asks }) => ({
      spread: computed(() => {
        const topBid = bids()[0]?.price ?? 0;
        const topAsk = asks()[0]?.price ?? 0;
        return topAsk > 0 && topBid > 0 ? topAsk - topBid : 0;
      }),
      marketDepth: computed(() => ({
        totalBidVolume: bids().reduce((acc, t) => acc + t.volume, 0),
        totalAskVolume: asks().reduce((acc, t) => acc + t.volume, 0),
      }))
    })),
    withMethods((store, streamService = inject(WebSocketStreamService)) => ({
      setConnectionStatus(status: OrderBookState['connectionStatus']): void {
        patchState(store, { connectionStatus: status });
      },
      
      // Batch-processing High-Frequency Stream via Buffer
      subscribeToMarketStream: rxMethod<void>(
        pipe(
          () => streamService.getRawFeed(store.symbol()),
          // Mengurangi render churn: kumpulkan tick per 100ms
          bufferTime(100),
          filter((ticks) => ticks.length > 0),
          (bufferedStream) => bufferedStream.pipe(
            (source$) => source$.subscribe((ticks) => {
              const latestTick = ticks[ticks.length - 1];
              patchState(store, (state) => ({
                lastPrice: latestTick.price,
                // Mengambil 20 data teratas secara efisien
                bids: [...ticks.filter(t => t.volume > 0), ...state.bids].slice(0, 20),
                asks: state.asks
              }));
            })
          )
        )
      )
    }))
  );
}
```

### 3. Service Dummy WebSocket untuk Mocking Data Stream
```typescript
// websocket-stream.service.ts
import { Injectable } from '@angular/core';
import { Observable, interval, map } from 'rxjs';
import { MarketTick } from './order-book.store';

@Injectable({ providedIn: 'root' })
export class WebSocketStreamService {
  getRawFeed(symbol: string): Observable<MarketTick> {
    return interval(10).pipe(
      map(() => ({
        price: 50000 + Math.random() * 100 - 50,
        volume: parseFloat((Math.random() * 2).toFixed(4)),
        timestamp: Date.now()
      }))
    );
  }
}
```

### 4. Smart Workspace Tab Component (Element Injector Level)
```typescript
// order-book-tab.component.ts
import { 
  Component, 
  Input, 
  OnInit, 
  ChangeDetectionStrategy, 
  inject, 
  Provider 
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { createOrderBookStore } from './order-book.store';

// Helper Factory Provider untuk scoping dynamic token
export function provideOrderBookStore(symbol: string): Provider[] {
  return [
    {
      provide: 'ORDER_BOOK_STORE_TOKEN',
      useFactory: () => {
        const StoreClass = createOrderBookStore(symbol);
        return new StoreClass();
      }
    }
  ];
}

@Component({
  selector: 'app-order-book-tab',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="trading-panel">
      <header class="panel-header">
        <h3>Instrument: {{ store.symbol() }}</h3>
        <span [class]="'badge ' + store.connectionStatus().toLowerCase()">
          {{ store.connectionStatus() }}
        </span>
      </header>

      <section class="price-display">
        <h1 [class.uptick]="store.spread() >= 0">
          {{ store.lastPrice() | currency:'USD':'symbol':'1.2-2' }}
        </h1>
        <p>Market Spread: {{ store.spread() | number:'1.4-4' }}</p>
      </section>

      <section class="depth-display">
        <div>Total Bid Volume: {{ store.marketDepth().totalBidVolume | number:'1.2-2' }}</div>
        <div>Total Ask Volume: {{ store.marketDepth().totalAskVolume | number:'1.2-2' }}</div>
      </section>

      <div class="book-table">
        <h4>Recent Bids</h4>
        <ul>
          <li *ngFor="let bid of store.bids()">
            <span>Price: {{ bid.price | number:'1.2-2' }}</span> | 
            <span>Vol: {{ bid.volume }}</span>
          </li>
        </ul>
      </div>
    </div>
  `,
  styles: [`
    .trading-panel { border: 1px solid #333; padding: 1rem; border-radius: 4px; background: #1e1e1e; color: #fff; }
    .uptick { color: #00e676; }
    .badge.connected { color: #00e676; }
    .depth-display { display: flex; gap: 2rem; margin: 1rem 0; font-family: monospace; }
  `]
})
export class OrderBookTabComponent implements OnInit {
  @Input({ required: true }) symbol!: string;

  // Mengambil instance store yang terisolasi secara transien di level node ini
  protected store!: ReturnType<ReturnType<typeof createOrderBookStore>>;

  ngOnInit(): void {
    const DynamicStoreClass = createOrderBookStore(this.symbol);
    // Bind instansi langsung ke komponen instance
    this.store = new DynamicStoreClass();
    this.store.setConnectionStatus('CONNECTED');
    this.store.subscribeToMarketStream();
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

```
PERBANDINGAN PARADIGMA STATE MANAGEMENT ENTERPRISE
┌──────────────────────┬──────────────────────┬──────────────────────┬──────────────────────┐
│ Metrik / Dimensi     │ Monolithic NgRx      │ NgRx ComponentStore  │ NgRx SignalStore     │
│                      │ (Global Redux)       │ (Decentralized RxJS) │ (Decentralized Signal│
├──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Paradigm Core        │ Event-driven / Pure  │ Reactive Stream      │ Reactive Primitives  │
│                      │ Reducers             │ (RxJS Subject/Pipe)  │ (Push-Pull Signals)  │
├──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Boilerplate Index    │ Sangat Tinggi        │ Menengah             │ Sangat Rendah        │
│                      │ (Actions/Effects/Red)│                      │ (Functional Mixins)  │
├──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Memory Management    │ Manual eviction rawan│ Otomatis terikat     │ Otomatis terikat     │
│                      │ bocor (GC resistant) │ lifecycle Komponen   │ lifecycle Komponen   │
├──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Execution Cost       │ Global evaluation &  │ Observable sub/unsub │ O(1) Push tracking,  │
│                      │ Action Stream load   │ allocation overhead  │ Lazy Computed Pull   │
├──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Micro-Frontend       │ Sangat sulit di-     │ Mudah diisolasi per  │ Sangat mudah di-     │
│ Isolation            │ isolasi per domain   │ Web Component / App  │ isolasi & modular    │
├──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ Time-Travel Debug    │ Out-of-the-box (Via  │ Tidak didukung       │ Parsial via custom   │
│                      │ Redux DevTools)      │ native               │ extension logging    │
└──────────────────────┴──────────────────────┴──────────────────────┴──────────────────────┘
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Async Stale Closure Mutator Race
* **Mekanisme Gagal:** Menggunakan `store.property()` secara langsung di dalam method asinkron setelah melewati jeda `await` atau operator RxJS.
* **Skenario:**
  ```typescript
  // PITFALL CODE:
  async function updateProfile(newName: string) {
    const currentProfile = store.profile(); // Thread checkpoint 1
    const result = await api.validate(newName);
    // Jika ada update lain ke store.profile selama jeda await, mutasi di bawah
    // akan menimpa data baru tersebut dengan snapshot lama (stale data).
    patchState(store, { profile: { ...currentProfile, name: result } });
  }
  ```
* **Mitigasi Teknis:** Selalu gunakan atomic updater signature:
  ```typescript
  patchState(store, (state) => ({
    profile: { ...state.profile, name: result }
  }));
  ```

### 2. Zombie Child Components pada Hierarchical Injectors
* **Mekanisme Gagal:** Ketika parent component menghancurkan child component yang masih memiliki subscription aktif ke Store Parent, child component dapat membaca sinyal yang sudah berada dalam kondisi *invalidated* atau *partially disposed*, menyebabkan runtime exception: `Cannot read properties of undefined`.
* **Mitigasi Teknis:**
  Manfaatkan `takeUntilDestroyed()` dari Angular core interop untuk seluruh stream RX internal, dan gunakan computed signal murni yang toleran terhadap state bernilai `null`/`undefined`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menyimpan Derived Transient Data di dalam State Primer
* **Salah:**
  ```typescript
  patchState(store, {
    items: newItems,
    itemCount: newItems.length // ANTI-PATTERN: Menyimpan redundant calculated state
  });
  ```
* **Benar:**
  ```typescript
  // Gunakan withComputed
  withComputed(({ items }) => ({
    itemCount: computed(() => items().length)
  }))
  ```

### 2. Membocorkan State Provider ke Root Injector Tanpa Sengaja
* **Salah:** Mendeklarasikan store fitur yang menangani proses pendaftaran multi-step dengan `{ providedIn: 'root' }`. User membatalkan proses, masuk kembali 20 menit kemudian, dan data lama masih ada di form.
* **Benar:** Daftarkan store pada rute konfigurasi spesifik fitur tersebut:
  ```typescript
  // feature.routes.ts
  export const ROUTES: Route[] = [
    {
      path: 'onboarding',
      providers: [OnboardingFlowStore], // Store di-instansiasi saat rute aktif
      loadComponent: () => import('./onboarding.component')
    }
  ];
  ```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan State Colocation:** State harus hidup pada level terdalam yang mungkin. Jika hanya 1 komponen yang butuh, letakkan di Node Injector Komponen. Jika dipakai bersama oleh 1 fitur rute (misal Master-Detail), letakkan di Route Providers. Hanya bawa ke Root jika data tersebut otentikasi atau global layout config.
2. **Readonly Invariants Enforcement:** Bungkus semua tipe State Interface dengan keyword `readonly`. Mutasi internal *wajib* immutable via `patchState`.
3. **Pemisahan Efek Bersih Menggunakan RxMethod:** Jangan memadukan side-effect I/O (seperti manipulasi `window.localStorage` atau panggilan API) langsung di dalam signal setter. Bungkus selalu dalam `rxMethod` agar lifecycle cancellation ditangani engine.
4. **Clean Decoupling:** Smart Component hanya boleh menginjeksi Facade / Store. Presentational (Dumb) Component tidak boleh tahu keberadaan Store, melainkan hanya menerima `input()` dan mengekspos `output()`.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. Memory Deallocation Verification
Pastikan tidak ada leak memory pada transient state dengan mengimplementasikan automated disposal verification check:
```typescript
withHooks({
  onDestroy(store) {
    // Bersihkan buffer manual jika menggunakan WebSocket native atau workers
    store.teardownActiveBuffers?.();
  }
})
```

### 2. Signal Granularity Tuning
Hindari membuat satu Signal besar berisi satu objek raksasa. Gunakan fine-grained state:
* Memecah state menjadi bagian independen memastikan consumer hanya di-evaluasi ulang ketika field spesifik yang ia baca mengalami mutasi.
* Bandingkan:
  * Mengubah `state.user.preferences.theme` pada single object signal memicu re-evaluasi seluruh pembaca `state()`.
  * Menggunakan `DeepSignal` pada SignalStore memungkinkan pembaca hanya mengikat dependensi ke `store.user.preferences.theme()` secara granular.

---

## SEKSI 16 — KEAMANAN & HARDENING

### State Poisoning & Immutability Protection
Mesin JavaScript mengeksekusi referensi memori secara dangkal (*shallow*). Developer ceroboh dapat mengubah objek di template atau method:
```typescript
// VULNERABILITY: Object mutation by reference
const currentOrders = store.orders();
currentOrders.push(maliciousOrder); // Memutasi internal state tanpa patchState!
```

### Implementasi Deep Freeze Guard Middleware
Terapkan middleware hardening berikut pada environment production/staging:
```typescript
// immutability-guard.ts
export function deepFreeze<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  
  const propNames = Reflect.ownKeys(obj);
  for (const name of propNames) {
    const value = (obj as Record<string | symbol, unknown>)[name];
    if (value && typeof value === 'object') {
      deepFreeze(value);
    }
  }
  
  return Object.freeze(obj);
}

// Custom store feature
import { signalStoreFeature, withMethods } from '@ngrx/signals';

export function withImmutabilityGuard() {
  return signalStoreFeature(
    withMethods((store) => ({
      safePatch<S>(stateUpdate: Partial<S>):