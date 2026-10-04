# BAB 07: State Management Terdesentralisasi dan Skala Besar
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** kelemahan arsitektur *Monolithic Global Store* pada aplikasi enterprise skala besar dan merumuskan dekomposisi modular berbasis *Decentralized Scoped Stores*.
- **Menguasai** arsitektur internal `@ngrx/signals` (`SignalStore`) dan membandingkannya secara mendalam dengan paradigma berbasis RxJS (`ComponentStore`).
- **Mengimplementasikan** *Custom SignalStore Features* yang dapat digunakan kembali (*reusable*), mencakup penanganan status panggilan asynchronous (`CallState`), entitas ternormalisasi (`EntityState`), dan sinkronisasi data optimis (*optimistic updates*).
- **Mengorkestrasi** komunikasi antar-*slice* state independen menggunakan pola *Mediator* dan *Decoupled Event Bus* tanpa menimbulkan *circular dependency*.
- **Mengoptimalkan** performa runtime hingga tingkat *micro-task* dengan memanfaatkan model reaktivitas *Fine-Grained Push-Pull Signals* dalam lingkungan Angular tanpa Zone.js (*Zoneless Change Detection*).
- **Mendiagnosis** dan memitigasi *memory leaks*, *race conditions*, dan *subscription thrashing* pada integrasi stream RxJS dan Signal primitives.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
1. **Angular Reactivity**: Penggunaan `signal()`, `computed()`, dan `effect()` serta siklus hidup pembersihan (*cleanup phases*).
2. **RxJS Concurrency Operators**: Penguasaan mendalam atas `switchMap`, `concatMap`, `mergeMap`, `exhaustMap`, dan implementasi operator *lossless/lossy backpressure*.
3. **Hierarchical Dependency Injection (DI)**: Perbedaan resolusi dependensi pada `root`, `EnvironmentInjector`, `ElementInjector`, dan *lifecycle scoping* (misalnya: `@Component({ providers: [...] })`).
4. **TypeScript Advanced Generics**: Pemahaman `Conditional Types`, `Mapped Types`, `Type Narrowing`, dan inferensi fungsi tingkat lanjut untuk memanipulasi *type signatures* SignalStore.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Topologi Reaktivitas: RxJS Stream vs Fine-Grained Signals

Arsitektur state terdesentralisasi modern di Angular bergeser dari model *Push-only Push-through-Pipe* (RxJS murni) ke model *Push-Pull Fine-Grained Reactivity* (Angular Signals).

```
RxJS BehaviorSubject Model (Push-Only):
[ Producer ] ---> push(value) ---> [ Operator Pipeline ] ---> push(value) ---> [ Template / AsyncPipe ]
* Setap emisi memicu evaluasi operator dan sinkronisasi change detection top-down (pada Zone.js default).

Signals Reactive Graph (Push-Pull):
[ Source Signal ] === notify dirty (Push) ===> [ ReactiveNode ]
        |                                            |
   (Value Read)                                 (Dependency Tracking)
        v                                            v
[ Computed Signal ] <===== pull current value ===== [ Template View Engine ]
```

Dalam internal Angular Signals, setiap signal diwakili oleh struktur data C++ / V8-optimized JavaScript object bernama `ReactiveNode`. `ReactiveNode` beroperasi dalam dua fase:
1. **Fase Notifikasi (Push)**: Ketika nilai sumber berubah, node sumber menandai semua node dependensi (*consumers*) sebagai *DIRTY* secara traversal, tanpa mengevaluasi nilai komputasi secara instan.
2. **Fase Evaluasi (Pull)**: Nilai dari `computed()` atau binding template hanya dievaluasi ulang saat runtime Angular benar-benar membaca nilai tersebut. Jika template tidak sedang dirender atau komponen berada di background, tidak ada komputasi yang terbuang.

#### 3.2 Arsitektur Internal `@ngrx/signals` (`SignalStore`)

`SignalStore` didesain modular berbasis *Functional Composition*. Alih-alih membuat kelas berbasis inheritance monolitik, SignalStore memproduksi struktur data *immutable* yang diperkaya secara bertahap melalui pipeline fungsi (`withState`, `withComputed`, `withMethods`, `withHooks`).

```
+-----------------------------------------------------------------------+
|                             SignalStore                               |
|                                                                       |
|  +------------------------+  +-------------------------------------+  |
|  |      State Slices      |  |          Computed Signals           |  |
|  |  (Deep Readonly Proxy) |  |   (Derived Push-Pull ReactiveNodes) |  |
|  +-----------+------------+  +------------------+------------------+  |
|              |                                  |                     |
|  +-----------v------------+  +------------------v------------------+  |
|  |      Custom Features   |  |          rxMethod Pipeline          |  |
|  | (Entity, CallState...) |  |  (RxJS Reactive Bridge via Injektor)|  |
|  +------------------------+  +-------------------------------------+  |
+-----------------------------------------------------------------------+
```

Di balik layar:
- State disimpan sebagai signal tunggal yang dibungkus oleh **JavaScript Proxy**. Proxy ini mengekspos setiap sub-properti state sebagai signal terisolasi (*read-only*).
- Pembaruan state dieksekusi melalui fungsi atomik `patchState()`. Fungsi ini menjamin *immutability* menggunakan *structural sharing* dangkal (*shallow copy*) atau terintegrasi dengan transformasi kustom.
- Integrasi asynchronous dikelola melalui `rxMethod<T>()`. `rxMethod` mengikat pipeline RxJS ke siklus hidup *Injection Context* di mana store tersebut diinstansiasi. Ketika injector hancur (*destroyed*), seluruh pipeline RxJS otomatis di-*complete* untuk mengeliminasi potensi *memory leak*.

---

### 4. Why & What

#### Problem: Monolithic Global Store Anti-Pattern
Pada sistem berskala ratusan ribu baris kode (misal: core banking atau platform ERP logistik), menempatkan seluruh state ke dalam satu Global Store (`@ngrx/store` monolitik) menyebabkan:
1. **State Pollution**: State transient milik komponen UI lokal (seperti pagination grid, state ekspansi baris, atau form draft) bocor ke global state.
2. **Coupling & Bundle Size Bloat**: Semua reducer, action, dan selector global saling terikat, menyulitkan dekomposisi berbasis micro-frontend atau domain module lazy-loading.
3. **Over-serialization & Overhead**: Redux DevTools mengalami degradasi performa drastis akibat serialisasi ribuan payload berfrekuensi tinggi per detik.

#### Solution: Decentralized & Scoped State Architecture
Pendekatan terdesentralisasi membagi state ke dalam batas-batas domain fungsional (*bounded contexts*) dengan siklus hidup (*lifecycle*) yang diikat langsung pada Angular Dependency Injection:
- **Root-level Slices**: Khusus data autentikasi, preferensi tema, dan hak akses aplikasi global.
- **Feature-level Slices**: Dimuat secara dinamis via *Environment Injector* rute tertentu (`provideState()` atau `provide(FeatureStore)` pada rute lazy-loaded).
- **Component-level Slices**: State transien lokal diikat langsung ke *Element Injector* komponen menggunakan `@Component({ providers: [FeatureStore] })`. Ketika komponen dihancurkan (misalnya saat modal ditutup atau navigasi keluar), seluruh state dan stream asynchronous langsung dibersihkan dari memori secara deterministik oleh garbage collector.

---

### 5. How (Workflow Detail)

Alur kerja state terdesentralisasi modern mengikuti siklus berikut:

```
[ Inisialisasi ]
       │
       ▼
[ Resolusi DI ] ──► (Root / Environment / Element Injector)
       │
       ▼
[ Pipeline Execution: SignalStore ]
       ├─ withState()      ──► Alokasi ReactiveNode State & Proxy
       ├─ withComputed()   ──► Pendaftaran Dynamic Tracking Graphs
       ├─ withMethods()    ──► Binding Mutasi State & rxMethod Side-Effects
       └─ withHooks()      ──► onInit / onDestroy Lifecycle Hooks
       │
       ▼
[ Runtime Processing ]
       ├── Pembacaan Template (Fine-grained Pull via Signals)
       └── Aksi Asynchronous (rxMethod: API Call -> Optimistic patchState -> API Resolve)
       │
       ▼
[ Teardown Phase ]
       └── Injector Destroyed ──► Auto-unsubscription rxMethod & Clean-up ReactiveNode Graph
```

1. **Definisi State**: Deklarasikan interface state murni tanpa referensi kelas eksternal.
2. **Ekstensi Modular**: Gunakan *Higher-Order Functions* untuk menyematkan fungsionalitas umum (misalnya pola `withCallState`).
3. **Instansiasi Berbasis Scope**: Tentukan provider store sesuai siklus hidup data:
   - Sesi Pengguna: Rute utama.
   - Analisis Transaksi: Rute fitur (lazy-loaded).
   - Form Entri Data / Data Grid Widget: Provider level komponen.
4. **Mutasi Atomik**: Gunakan `patchState` untuk memastikan mutasi deterministik.
5. **Penanganan I/O**: Gunakan `rxMethod` untuk menyambungkan stream RxJS eksternal (WebSocket, polling HTTP) langsung ke dalam state signal.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kantor Pos Terpusat vs Smart Locker Lokal

- **Global Store (Monolitik)**: Seperti **Satu Kantor Pos Pusat** untuk seluruh kota. Semua warga (komponen) harus mengirim surat (action), mengantre di satu loket pusat (root reducer), dan kurir harus mengecek peta seluruh kota untuk mengantarkan respon. Jika ada 10.000 permintaan paket kecil bersamaan, kantor pos pusat lumpuh.
- **Decentralized SignalStore**: Seperti jaringan **Smart Locker Mandiri** di setiap RT/RW atau gedung apartemen. Setiap gedung (fitur/komponen) memiliki unit lokernya sendiri. Transaksi lokal selesai di tempat tanpa membebani server logistik kota. Begitu penghuni apartemen pindah (komponen unmount), loker tersebut dibersihkan dan dialokasikan ulang secara instan.

#### Arsitektur Komunikasi Terdesentralisasi

```
+------------------------------------------------------------------------------------+
|                                    APP ROOT                                        |
|  Global Services: GlobalEventBus (RxJS), AuthStore (SignalStore)                  |
+------------------------------------------+-----------------------------------------+
                                           |
                   +-----------------------+-----------------------+
                   |                                               |
                   v                                               v
     +---------------------------+                   +---------------------------+
     |   Orders Feature Scope    |                   |   Billing Feature Scope   |
     |   (EnvironmentInjector)   |                   |   (EnvironmentInjector)   |
     |                           |                   |                           |
     |  +---------------------+  |                   |  +---------------------+  |
     |  | OrdersFacadeStore   |  |                   |  | InvoiceFacadeStore  |  |
     |  +----------+----------+  |                   |  +----------+----------+  |
     |             |             |                   |             |             |
     |   +---------v---------+   |  Event Dispatch   |   +---------v---------+   |
     |   | OrderList Cmp     |   | =================>|   | InvoiceWidget Cmp |   |
     |   | (ElementInjector) |   | (via EventBus)    |   | (ElementInjector) |   |
     |   | LocalTableStore   |   |                   |   | LocalCalcStore    |   |
     |   +-------------------+   |                   |   +-------------------+   |
     +---------------------------+                   +---------------------------+
```

---

### 7. Simple Example & Practical Example (Standar Industri)

#### 7.1 Simple Example: Counter SignalStore Terisolasi

```typescript
// counter.store.ts
import { signalStore, withState, withMethods, patchState } from '@ngrx/signals';

export interface CounterState {
  count: number;
  lastUpdatedBy: string;
}

const initialCounterState: CounterState = {
  count: 0,
  lastUpdatedBy: 'SYSTEM',
};

export const CounterStore = signalStore(
  withState(initialCounterState),
  withMethods((store) => ({
    increment(user: string): void {
      patchState(store, (state) => ({
        count: state.count + 1,
        lastUpdatedBy: user,
      }));
    },
    decrement(user: string): void {
      patchState(store, (state) => ({
        count: state.count - 1,
        lastUpdatedBy: user,
      }));
    },
    reset(): void {
      patchState(store, initialCounterState);
    },
  }))
);
```

#### 7.2 Practical Example: Enterprise-Grade Custom Feature Store & Orchestration

Berikut implementasi lengkap fitur reusable `withCallState` dan Store Domain Pemrosesan Pesanan (*Order Processing*) dengan penanganan asynchronous, optimasi konkurensi, dan isolasi memori:

```typescript
// shared/state/call-state.feature.ts
import { computed } from '@angular/core';
import { signalStoreFeature, withComputed, withState } from '@ngrx/signals';

export type CallState = 'init' | 'loading' | 'loaded' | { error: string };

export interface CallStateSlice {
  callState: CallState;
}

export function withCallState() {
  return signalStoreFeature(
    withState<CallStateSlice>({ callState: 'init' }),
    withComputed(({ callState }) => ({
      isLoading: computed(() => callState() === 'loading'),
      isLoaded: computed(() => callState() === 'loaded'),
      error: computed(() => {
        const state = callState();
        return typeof state === 'object' && 'error' in state ? state.error : null;
      }),
    }))
  );
}

// Helpers untuk mutasi call state
export function setLoading(): CallStateSlice {
  return { callState: 'loading' };
}

export function setLoaded(): CallStateSlice {
  return { callState: 'loaded' };
}

export function setError(error: string): CallStateSlice {
  return { callState: { error } };
}
```

```typescript
// features/orders/domain/order.models.ts
export interface Order {
  id: string;
  orderNumber: string;
  amount: number;
  status: 'PENDING' | 'SETTLED' | 'CANCELLED';
  createdAt: string;
}

export interface OrdersFilter {
  query: string;
  status: Order['status'] | 'ALL';
}
```

```typescript
// features/orders/state/orders.store.ts
import { inject } from '@angular/core';
import { signalStore, withState, withComputed, withMethods, withHooks, patchState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { computed } from '@angular/core';
import { pipe, switchMap, tap, catchError, of, exhaustMap } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { withCallState, setLoading, setLoaded, setError } from '../../shared/state/call-state.feature';
import { Order, OrdersFilter } from '../domain/order.models';

export interface OrdersState {
  orders: Order[];
  filter: OrdersFilter;
  selectedOrderId: string | null;
}

const initialState: OrdersState = {
  orders: [],
  filter: { query: '', status: 'ALL' },
  selectedOrderId: null,
};

export const OrdersStore = signalStore(
  // Menambahkan reusable CallState slice
  withCallState(),
  // Menambahkan state spesifik
  withState(initialState),
  // Computed Signals terisolasi
  withComputed(({ orders, filter, selectedOrderId }) => ({
    filteredOrders: computed(() => {
      const currentFilter = filter();
      const currentOrders = orders();
      
      return currentOrders.filter((order) => {
        const matchesQuery = order.orderNumber.toLowerCase().includes(currentFilter.query.toLowerCase());
        const matchesStatus = currentFilter.status === 'ALL' || order.status === currentFilter.status;
        return matchesQuery && matchesStatus;
      });
    }),
    selectedOrder: computed(() => {
      const id = selectedOrderId();
      if (!id) return null;
      return orders().find((o) => o.id === id) ?? null;
    }),
    totalVolume: computed(() => 
      orders().reduce((sum, order) => sum + order.amount, 0)
    ),
  })),
  // Mutasi sinkron dan asinkron (rxMethod)
  withMethods((store, http = inject(HttpClient)) => ({
    updateFilter(filter: Partial<OrdersFilter>): void {
      patchState(store, (state) => ({
        filter: { ...state.filter, ...filter },
      }));
    },
    selectOrder(id: string | null): void {
      patchState(store, { selectedOrderId: id });
    },
    // Safe stream processing dengan switchMap untuk pembatalan request lama
    fetchOrders: rxMethod<void>(
      pipe(
        tap(() => patchState(store, setLoading())),
        switchMap(() =>
          http.get<Order[]>('/api/v1/orders').pipe(
            tap((orders) => {
              patchState(store, { orders }, setLoaded());
            }),
            catchError((err: Error) => {
              patchState(store, setError(err.message || 'Gagal memuat pesanan'));
              return of(null);
            })
          )
        )
      )
    ),
    // Optimistic Update dengan rollback menggunakan exhaustMap untuk proteksi klik ganda
    cancelOrder: rxMethod<{ id: string; reason: string }>(
      pipe(
        exhaustMap(({ id, reason }) => {
          const originalOrders = store.orders();
          const target = originalOrders.find((o) => o.id === id);
          if (!target || target.status === 'CANCELLED') return of(null);

          // 1. Optimistic Patch
          patchState(store, (state) => ({
            orders: state.orders.map((o) => (o.id === id ? { ...o, status: 'CANCELLED' as const } : o)),
          }));

          // 2. Network Call
          return http.post<void>(`/api/v1/orders/${id}/cancel`, { reason }).pipe(
            catchError((err: Error) => {
              // 3. Rollback jika API gagal
              patchState(store, { orders: originalOrders }, setError(`Rollback: ${err.message}`));
              return of(null);
            })
          );
        })
      )
    ),
  })),
  // Siklus hidup inisialisasi deterministik
  withHooks({
    onInit(store) {
      store.fetchOrders();
    },
    onDestroy(store) {
      // Logic pembersihan eksplisit jika dibutuhkan (rxMethod terbebas otomatis dari memori)
      console.info('OrdersStore berhasil dihancurkan, resource dibebaskan.');
    },
  })
);
```

```typescript
// features/orders/components/order-list.component.ts
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { OrdersStore } from '../state/orders.store';

@Component({
  selector: 'app-order-list',
  standalone: true,
  imports: [CommonModule],
  // Scoped Provider: Instansiasi unik per komponen, dihancurkan otomatis bersama template lifecycle
  providers: [OrdersStore],
  template: `
    <div class="orders-container">
      <header>
        <h2>Daftar Transaksi (Total Volume: {{ store.totalVolume() | currency }})</h2>
        <div *ngIf="store.isLoading()" class="spinner">Memuat data real-time...</div>
        <div *ngIf="store.error()" class="error-banner">{{ store.error() }}</div>
      </header>

      <div class="filter-controls">
        <input 
          type="text" 
          placeholder="Cari No. Order..." 
          (input)="onSearch($event)"
        />
      </div>

      <table>
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Nominal</th>
            <th>Status</th>
            <th>Aksi</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let order of store.filteredOrders(); trackBy: trackById">
            <td>{{ order.orderNumber }}</td>
            <td>{{ order.amount | currency }}</td>
            <td><span [class]="'badge-' + order.status">{{ order.status }}</span></td>
            <td>
              <button 
                [disabled]="order.status === 'CANCELLED' || store.isLoading()"
                (click)="store.cancelOrder({ id: order.id, reason: 'Dibatalkan oleh Operator' })">
                Batalkan
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class OrderListComponent {
  // Store diinjeksikan secara fine-grained
  readonly store = inject(OrdersStore);

  onSearch(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.store.updateFilter({ query: value });
  }

  trackById(_index: number, order: { id: string }): string {
    return order.id;
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: High-Frequency Trading Portfolio Monitoring System
Sebuah institusi perbankan investasi mengelola dashboard portofolio ekuitas yang memproses lebih dari **800 perubahan data per detik** via WebSocket pada jam bursa dibuka, yang mencakup 500 aset aktif yang dikelompokkan ke dalam portofolio independen.

```
                    [ Real-Time Pricing WebSocket Engine ]
                                      |
                     (High-Frequency Raw Stream: 800 msg/s)
                                      |
                                      v
                        [ PriceStreamMediatorService ]
                        (Lossless Backpressure: auditTime)
                                      |
              +-----------------------+-----------------------+
              | Partition by Asset Id                         | Partition by Asset Id
              v                                               v
   [ AssetDetailStore: AAPL ]                      [ AssetDetailStore: GOOGL ]
   Scope: Virtual Grid Row 1                       Scope: Virtual Grid Row 2
   - price = signal(175.20)                        - price = signal(140.50)
   - pnl = computed(...)                           - pnl = computed(...)
              |                                               |
     (Only Row 1 Evaluates)                          (Only Row 2 Evaluates)
```

#### Arsitektur Permasalahan (Root Cause Failure)
Pada sistem lama berbasis Redux Monolitik Global:
1. Setiap pesan WebSocket memicu `store.dispatch(PriceUpdatedAction)`.
2. 800 *dispatches/sec* memicu 800 kali eksekusi seluruh selector tree.
3. Node Angular Zone.js mendeteksi *microtask tick* untuk setiap emisi WebSocket, menyebabkan seluruh komponen aplikasi mengalami *Change Detection Pass*. Akibatnya, UI freeze selama 1,2 detik per siklus 5 detik.

#### Solusi Implementasi
1. **Dekomposisi Menjadi Micro-Stores**: Dibuat store berskala kecil bernama `AssetDetailStore` yang disediakan pada tingkat baris virtual scroll (`ElementInjector`).
2. **Push-Pull Fine-Grained Signals**: Komponen hanya membaca `assetStore.price()`. Perubahan harga pada saham "AAPL" hanya memicu evaluasi `ReactiveNode` sel saham tersebut. Seluruh baris saham "GOOGL" tidak dievaluasi ulang sama sekali.
3. **Decoupled Backpressure Mediator**: Dibuat sebuah `PriceStreamMediatorService` tingkat aplikasi yang menerapkan operator RxJS `bufferTime(50)` untuk menggabungkan lonjakan data (*chunking*), kemudian memutasi masing-masing `AssetDetailStore` secara spesifik via ID registry.

Hasil Pengukuran Produksi:
- **CPU Main-Thread Idle Time**: Meningkat dari 14% menjadi 78%.
- **Memory Footprint Stable**: Menurun 65% karena garbage collection langsung menghancurkan state saham yang di-unmount dari virtual grid.
- **Render Latency**: Menurun dari 120ms ke < 8ms (memenuhi standar 60–120 FPS).

---

### 9. Trade-offs

| Dimensi Arsitektur | Monolithic Store (`@ngrx/store`) | Decentralized Store (`@ngrx/signals`) |
| :--- | :--- | :--- |
| **Granularitas Evaluasi** | Kasar (*Coarse*). Seluruh cabang state harus divalidasi via selektor murni. | Halus (*Fine-grained*). Hanya node dependensi terdaftar yang dievaluasi (*dirty-tracking*). |
| **Isolasi Memori & Lifecycle** | Rendah. State tersimpan selamanya hingga aplikasi ditutup jika tidak di-reset manual. | Tinggi. State dihancurkan otomatis mengikuti lifecycle Angular Dependency Injection. |
| **Debuggability & Tooling** | Sangat Tinggi. Ekosistem Redux DevTools matang (Time-travel debugging, action serialization). | Menengah. Bergantung pada logging kustom dan inspeksi DevTools Angular Signals native. |
| **Tingkat Kompleksitas Kode** | Tinggi (Boilerplate Actions, Reducers, Effects terpisah di banyak file). | Rendah. Ringkas, minim *boilerplate*, deklaratif dalam satu file berbasis fungsi. |
| **Komunikasi Antar Fitur** | Sederhana. Cukup `select()` state cabang lain di mana saja dalam aplikasi. | Memerlukan Pola Khusus (*Mediator Pattern* / Shared Root Store) untuk menghindari *circular dependency*. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Kebocoran Memori Akibat Unsubscribed Long-Running Observables dalam Store
*Penyebab*: Menggunakan `Observable.subscribe()` secara manual di dalam method `signalStore` tanpa mengaitkannya ke `DestroyRef` atau di luar konteks `rxMethod`.
```typescript
// SALAH: Memory Leak! Observable tidak pernah dibatalkan saat store di-destroy.
withMethods((store) => ({
  initBadStream() {
    interval(1000).subscribe((val) => {
      patchState(store, { counter: val });
    });
  }
}))

// BENAR: Gunakan rxMethod yang otomatis dibatalkan via Angular Injection Context.
withMethods((store) => ({
  initGoodStream: rxMethod<void>(
    pipe(
      switchMap(() => interval(1000)),
      tap((val) => patchState(store, { counter: val }))
    )
  )
}))
```

#### Kesalahan 2: State Mutation Langsung (Bypassing Immutability)
*Penyebab*: Memodifikasi properti internal objek atau array secara mutasi langsung sebelum memanggil `patchState`.
```typescript
// SALAH: Merusak reactive tracking karena referensi array tidak berubah!
patchState(store, (state) => {
  state.orders.push(newOrder); // Mutasi langsung (anti-pattern)
  return { orders: state.orders };
});

// BENAR: Buat salinan referensi baru (structural sharing).
patchState(store, (state) => ({
  orders: [...state.orders, newOrder]
}));
```

#### Kesalahan 3: Circular Dependency Antar Decentralized Stores
*Penyebab*: `OrdersStore` menginjeksi `InvoicesStore`, dan sebaliknya `InvoicesStore` menginjeksi `OrdersStore`.
*Gejala*: Error runtime `NullInjectorError` atau `Circular dependency detected`.
*Solusi*: 
1. Ekstraksi state bersama ke Store tingkat ketiga yang lebih tinggi (`BillingOrchestratorStore`).
2. Gunakan pola *Event Bus* asinkron menggunakan RxJS `Subject` murni di root service untuk pertukaran sinyal antar store.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Scope Minimization**: Jangan sediakan store di root (`providedIn: 'root'`) jika state tersebut hanya digunakan pada satu halaman rute atau modal.
2. [ ] **Atomic `patchState` Operations**: Kelompokkan beberapa perubahan properti ke dalam satu pemanggilan `patchState()` untuk menghindari kalkulasi ulang `computed` yang redundan.
3. [ ] **Concurrency Operator Audit**:
   - Gunakan `switchMap` untuk pencarian/filter di mana hanya request terakhir yang valid.
   - Gunakan `exhaustMap` untuk submit transaksi finansial guna mencegah *double submit*.
   - Gunakan `concatMap` untuk operasi berurutan (misal: antrean upload dokumen).
4. [ ] **Zoneless Readiness**: Pastikan tidak ada dependensi terhadap Zone.js. Gunakan signal binding native `store.mySignal()` langsung di template.
5. [ ] **Feature Modularization**: Pisahkan fungsionalitas umum seperti pagination, filtering, dan status pemanggilan API ke dalam `signalStoreFeature` yang *reusable*.
6. [ ] **Deep Readonly Enforcement**: Tandai seluruh interface state dengan `readonly` properties untuk mencegah mutasi tidak sengaja oleh developer.

---

### 12. Hands-on Practice

Buat implementasi state terdesentralisasi untuk modul eksekusi inventaris barang pada direktori `hands-on/m02/`.

#### Langkah 1: Setup Workspace & Install Dependensi
```bash
mkdir -p hands-on/m02/src/app/inventory-slice
cd hands-on/m02
npm init -y
npm install @angular/core@^18.0.0 @ngrx/signals@^18.0.0 rxjs@^7.8.0
```

#### Langkah 2: Buat File `inventory.models.ts`
Simpan di: `hands-on/m02/src/app/inventory-slice/inventory.models.ts`
```typescript
export interface InventoryItem {
  sku: string;
  name: string;
  stock: number;
  reserved: number;
}
```

#### Langkah 3: Implementasikan Store Terdesentralisasi dengan Reusable CallState
Simpan di: `hands-on/m02/src/app/inventory-slice/inventory.store.ts`
```typescript
import { signalStore, withState, withComputed, withMethods, patchState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { computed } from '@angular/core';
import { pipe, delay, of, tap } from 'rxjs';
import { InventoryItem } from './inventory.models';

export interface InventoryState {
  items: InventoryItem[];
  searchTerm: string;
}

const initialInventory: InventoryState = {
  items: [
    { sku: 'SKU-001', name: 'Server Rack 42U', stock: 12, reserved: 2 },
    { sku: 'SKU-002', name: 'Cat6 Ethernet Cable 305m', stock: 85, reserved: 10 },
    { sku: 'SKU-003', name: 'Managed Switch 24-Port', stock: 5, reserved: 5 },
  ],
  searchTerm: '',
};

export const InventoryStore = signalStore(
  withState(initialInventory),
  withComputed(({ items, searchTerm }) => ({
    availableStockList: computed(() => {
      const term = searchTerm().toLowerCase();
      return items()
        .filter((item) => item.name.toLowerCase().includes(term))
        .map((item) => ({
          ...item,
          available: item.stock - item.reserved,
        }));
    }),
    isDepleted: computed(() => items().some((item) => item.stock - item.reserved <= 0)),
  })),
  withMethods((store) => ({
    setSearchTerm(searchTerm: string): void {
      patchState(store, { searchTerm });
    },
    reserveItem: rxMethod<{ sku: string; quantity: number }>(
      pipe(
        delay(300), // Simulasi I/O delay
        tap(({ sku, quantity }) => {
          patchState(store, (state) => ({
            items: state.items.map((item) => {
              if (item.sku !== sku) return item;
              if (item.stock - item.reserved < quantity) {
                console.warn(`Stok tidak mencukupi untuk SKU: ${sku}`);
                return item;
              }
              return { ...item, reserved: item.reserved + quantity };
            }),
          }));
        })
      )
    ),
  }))
);
```

#### Langkah 4: Hubungkan ke Komponen Scoped Element
Simpan di: `hands-on/m02/src/app/inventory-slice/inventory-widget.component.ts`
```typescript
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { InventoryStore } from './inventory.store';

@Component({
  selector: 'app-inventory-widget',
  standalone: true,
  imports: [CommonModule],
  providers: [InventoryStore], // Isolasi Lifecycle Store
  template: `
    <div class="inventory-widget">
      <h3>Manajemen Inventaris Lokal</h3>
      <input 
        type="text" 
        placeholder="Filter item..." 
        (input)="store.setSearchTerm($any($event.target).value)" 
      />

      <div *ngIf="store.isDepleted()" class="alert-box">
        Peringatan: Terdapat inventaris dengan stok operasional habis!
      </div>

      <ul>
        <li *ngFor="let item of store.availableStockList()">
          {{ item.name }} ({{ item.sku }}) - 
          Tersedia: <strong>{{ item.available }}</strong> unit
          <button (click)="store.reserveItem({ sku: item.sku, quantity: 1 })">
            Reservasi 1 Unit
          </button>
        </li>
      </ul>
    </div>
  `
})
export class InventoryWidgetComponent {
  readonly store = inject(InventoryStore);
}
```

---

### 13. Exercise

#### Level Easy
Buat sebuah `signalStoreFeature` bernama `withToggle` yang membungkus boolean state (default `false`) beserta dua method: `toggle()` dan `setToggle(value: boolean)`. Pastikan type-safe dan dapat di-chain ke dalam store mana pun.

#### Level Medium
Kembangkan sebuah `CacheStoreSlice` yang menyimpan data respons API berbasis key-value map dengan Time-to-Live (TTL). Buat method `setWithTtl(key: string, data: any, ttlMs: number)` dan selector `getValid(key: string)` yang otomatis mengembalikan `null` jika timestamp telah kadaluwarsa.

#### Level Hard
Implementasikan sebuah arsitektur sinkronisasi multi-tab terdesentralisasi menggunakan **Web BroadcastChannel API**. Buat custom feature `withCrossTabSync({ channelName: string })` yang secara transparan menyinkronkan setiap mutasi `patchState` antar tab browser secara real-time tanpa infinite loop update, lengkap dengan penanganan resolusi konflik berbasis *Vector Clock* atau *Timestamp LWW (Last-Write-Wins)*.

---

### 14. Challenge

#### Sistem Telemetri Radar Maritim Real-Time (Tanpa Zone.js)
Sebuah sistem pelacakan armada maritim menerima data transmisi AIS (*Automatic Identification System*) dari ribuan kapal. Setiap kapal mengirimkan koordinat latitude, longitude, kecepatan, dan arah setiap 200ms.

**Spesifikasi Tantangan:**
1. Rancang arsitektur store berbasis Angular SignalStore di mana:
   - Tidak ada satu pun Global State Tree yang memuat array koordinat seluruh armada (mencegah bottleneck render).
   - Setiap elemen penanda kapal di canvas/SVG memiliki instansiasi Scoped Store sendiri yang terisolasi.
2. Implementasikan mekanisme **Lossy Adaptive Backpressure**: Jika frame rate browser turun di bawah 45 FPS, lewati (*drop*) paket update telemetri sementara untuk kapal yang berada di luar viewport (*viewport culling*).
3. Sediakan mekanisme *Federated Metrics*: Sebuah store agregasi di level dashboard atas yang dapat membaca total metrik (misal: Kecepatan Rata-rata Seluruh Armada) secara push-pull tanpa merender ulang store masing-masing kapal.
4. **Konstrain**: Seluruh solusi harus berjalan murni tanpa dependensi `zone.js` (`provideExperimentalZonelessChangeDetection()`), dilarang menggunakan `any`, dan harus 100% bebas dari kebocoran memori pada instansiasi/penghancuran ribuan kapal per menit.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara model reaktivitas Push-Only (RxJS) dan Push-Pull (Signals) pada Angular?**
   - *Jawaban*: Push-only memaksa seluruh pipeline dievaluasi langsung begitu nilai dipancarkan hingga ke subscriber. Push-pull hanya menandai dependensi sebagai *dirty* pada fase push, dan kalkulasi nilai aktual hanya ditarik (*pull*) saat nilai dibaca langsung oleh template atau consumer lain.
2. **Kapan siklus hidup (lifecycle) sebuah SignalStore yang disediakan pada `@Component({ providers: [MyStore] })` berakhir?**
   - *Jawaban*: Berakhir tepat saat komponen tersebut dihancurkan (*unmounted*) dari DOM tree oleh Angular Element Injector.
3. **Mengapa fungsi `patchState()` lebih disukai daripada melakukan mutasi langsung pada objek state?**
   - *Jawaban*: Karena `patchState()` menerapkan paradigma immutability via structural sharing yang memicu notifikasi pembaruan node reaktif secara atomik tanpa merusak konsistensi internal dependency graph.
4. **Apa fungsi utama dari hook `withHooks({ onDestroy: ... })` pada SignalStore?**
   - *Jawaban*: Menjalankan logika pembersihan eksplisit, melepaskan koneksi eksternal non-Angular (misal: menutup WebSocket, IndexedDB connection), atau logging teardown saat store injector dihancurkan.
5. **Bagaimana cara membaca nilai dari signal di dalam template komponen Angular?**
   - *Jawaban*: Dengan memanggil identitas signal tersebut sebagai fungsi tanpa argumen, contoh: `store.totalVolume()`.

#### Bagian 2: Intermediate (5 Pertanyaan)
1. **Bagaimana `rxMethod` dari `@ngrx/signals/rxjs-interop` menangani pembersihan memory leak saat komponen unmount?**
   - *Jawaban*: `rxMethod` melacak konteks Dependency Injection aktif (`DestroyRef`). Ketika injector hancur, internal RxJS subscription di-complete secara otomatis, menghentikan seluruh pipeline stream tanpa perlu pemanggilan `takeUntilDestroyed` manual.
2. **Apa dampak performa jika Anda menaruh data transient seperti `isDropdownOpen: boolean` ke dalam NgRx Monolithic Global Store?**
   - *Jawaban*: Terjadi overhead serialisasi Redux, pencatatan action yang tidak perlu di DevTools, eksekusi selector global yang berlebihan, serta memperlambat garbage collection karena state tetap hidup di memory heap root.
3. **Kapan Anda harus menggunakan `exhaustMap` dibandingkan `switchMap` di dalam method store asynchronous?**
   - *Jawaban*: Gunakan `exhaustMap` ketika request yang sedang berjalan harus dilindungi dari interupsi dan request baru harus diabaikan sampai request sebelumnya tuntas (misal: submit pembayaran). Gunakan `switchMap` ketika request baru harus membatalkan request lama yang usang (misal: autocomplete pencarian).
4. **Bagaimana cara kerja JavaScript Proxy internal pada `withState` SignalStore?**
   - *Jawaban*: Proxy mencegat akses properti ke state root dan secara dinamis mengembalikan referensi signal read-only individu untuk properti tersebut tanpa menyalin seluruh objek secara mendalam (*lazy signal creation*).
5. **Mengapa kita tidak boleh mengeksekusi operasi asinkron yang mengubah state di dalam block `computed()`?**
   - *Jawaban*: Karena fungsi `computed()` harus bersifat murni (*pure computation*), sinkron, dan bebas dari *side-effects*. Melakukan operasi asinkron di dalamnya akan merusak determinisme dependency graph Angular.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

1. **Skenario 1**: Tim Anda memigrasikan aplikasi ERP ke arsitektur Zoneless. Namun, salah satu fitur tabel yang menggunakan `SignalStore` lokal tidak memperbarui UI ketika menerima notifikasi WebSocket latar belakang. Di mana kemungkinan letak kesalahannya?
   - *Analisis & Solusi*: Kemungkinan WebSocket listener memutasi data menggunakan variabel biasa tanpa melewati `patchState`, atau template masih mengandalkan mekanisme dirty checking Zone.js lama alih-alih membaca Signal primitif secara langsung via sintaks eksekusi `store.data()`. Pastikan mutasi WebSocket dibungkus dalam `rxMethod` yang memanggil `patchState` dan template membaca signal accessor.

2. **Skenario 2**: Dua sub-komponen pada halaman yang sama memerlukan sinkronisasi state instan, tetapi keduanya tidak berada dalam hubungan *Parent-Child* langsung (mereka adalah *sibling components* dalam router-outlet). Bagaimana arsitektur store yang tepat tanpa menggunakan Global Store?
   - *Analisis & Solusi*: Daftarkan store tersebut pada level *Route Configuration* induk mereka (`providers: [SharedFeatureStore]`) menggunakan *EnvironmentInjector*. Dengan demikian, kedua komponen sibling tersebut menginjeksi instance store yang sama yang terisolasi hanya untuk rute tersebut, dan store otomatis dihancurkan saat pengguna berpindah ke rute domain lain.

3. **Skenario 3**: Sebuah form dinamis yang kompleks memiliki 200 field input. Setiap perubahan field memanggil selector derivasi `computed()` yang mahal. User mengalami lag pengetikan (*typing latency* ~100ms). Bagaimana Anda mengoptimalkan arsitektur state-nya?
   - *Analisis & Solusi*:
     1. Terapkan pemisahan state: jangan satukan seluruh 200 field ke dalam satu state atomik besar. Pisahkan menjadi sub-slices per seksi form (*Decentralized Field Group Stores*).
     2. Terapkan debouncing stream pada input event via `rxMethod` sebelum memutasi state.
     3. Isolasi komputasi derivasi yang mahal agar hanya bergantung pada signal field yang relevan, bukan pada signal form keseluruhan, memanfaatkan sifat fine-grained tracking `ReactiveNode`.

---

### 16. Summary

- **Decentralized State Management** menyelesaikan masalah skalabilitas, penggelembungkan kode (*code bloat*), dan kebocoran memori yang lazim terjadi pada *Monolithic Global Store* di aplikasi enterprise.
- Integrasi **`@ngrx/signals`** menghadirkan kapabilitas reaktivitas mutakhir (*Fine-Grained Push-Pull*) yang berjalan optimal pada arsitektur modern Angular tanpa Zone.js (*Zoneless*).
- Dengan memanfaatkan **Angular Hierarchical Dependency Injection**, siklus hidup state dapat diikat secara deterministik ke level rute (*EnvironmentInjector*) maupun komponen (*ElementInjector*), menjamin pembersihan resource otomatis.
- Fungsionalitas cross-cutting seperti pelacakan status asinkron (`CallState`), optimasi konkurensi (RxJS mapping operators), dan sinkronisasi data dapat diabstraksikan menjadi fitur independen yang dapat digunakan kembali menggunakan **SignalStore Features Composition**.