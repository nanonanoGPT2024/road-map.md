# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 03-Frontend-and-Mobile
### BAB-01: Fondasi dan Arsitektur
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi Vue.js 3

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal Engineer/Senior Frontend Engineer diharapkan mampu:
- Membedah dan mengonfigurasi mekanisme internal Vue 3 Reactive Engine (`@vue/reactivity`), termasuk algoritma dependency tracking (`track`), mutasi (`trigger`), `Dep`, dan siklus hidup `ReactiveEffect`.
- Menganalisis operasi Virtual DOM (VNode), algoritma diffing rekursif, optimasi berbasis *Block Tree*, serta peran *PatchFlags* dan *ShapeFlags* dalam fase rendering.
- Mengontrol antrean asinkron pada runtime scheduler Vue (`nextTick`, job deduplication, flushing queue: `pre`, `post`, `sync`).
- Merancang arsitektur composable modular enterprise dengan memori terisolasi, manajemen *lifecycle effect scoping*, dan mitigasi memory leaks pada *Single Page Application* (SPA) berumur panjang.
- Mengimplementasikan *Custom Renderer* menggunakan `@vue/runtime-core` untuk target non-DOM.
- Membangun pipeline arsitektur frontend skala enterprise yang tahan uji beban, *type-safe* secara end-to-end, dan siap untuk deployment multi-region berskala jutaan pengguna aktif.

---

### 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib menguasai:
- **Advanced ECMAScript/TypeScript**: `Proxy`, `Reflect`, `WeakMap`, `WeakSet`, `Symbol`, Async Generators, Type Narrowing, Generics bertingkat, dan Template Literal Types.
- **Fundamental Web API**: Event Loop (Macro vs Microtasks), MutationObserver, Performance Profiler (Chrome DevTools Memory Heap Snapshot).
- **Vue 3 Fundamental**: SFC (*Single File Components*), Composition API dasar (`ref`, `reactive`, `computed`, `watch`, lifecycle hooks).
- **Arsitektur Frontend Dasar**: State Management patterns (Flux/Store), Virtual DOM vs Incremental DOM dasar.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Reaktivitas Mendalam: Mesin Inti (`@vue/reactivity`)
Reaktivitas Vue 3 tidak lagi menggunakan `Object.defineProperty` (Vue 2), melainkan beralih sepenuhnya ke ES2015 `Proxy` yang dipadukan dengan `Reflect`. Arsitektur ini dibangun di atas tiga struktur data relasional internal:
1. `targetMap`: Sebuah `WeakMap<TargetObject, KeyToDepMap>` global. `WeakMap` dipilih agar objek target dapat dikoleksi oleh Garbage Collector (GC) jika referensi luarnya hilang, mencegah memory leak struktural.
2. `depsMap`: Sebuah `Map<PropertyKey, Dep>` yang menyimpan representasi dependensi per properti objek.
3. `dep`: Sebuah entitas khusus (bertipe `Map<ReactiveEffect, number> | Set<ReactiveEffect>`) yang memetakan efek komputasi aktif yang berlangganan terhadap mutasi nilai properti tersebut.

```
+--------------------------------------------------------------------------------+
|                                   targetMap                                    |
| (WeakMap<TargetObject, Map<PropertyKey, Set<ReactiveEffect>>>>)               |
+--------------------------------------------------------------------------------+
                                        │
             ┌──────────────────────────┴──────────────────────────┐
             ▼                                                     ▼
     Target Object A                                       Target Object B
 ┌───────────────────────┐                             ┌───────────────────────┐
 │        depsMap        │                             │        depsMap        │
 │  (Map<Property, Dep>) │                             │  (Map<Property, Dep>) │
 └───────────┬───────────┘                             └───────────────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
 Key: "price"     Key: "qty"
 ┌─────────────┐  ┌─────────────┐
 │     Dep     │  │     Dep     │
 │ (Set<Effect>│  │ (Set<Effect>│
 └──────┬──────┘  └─────────────┘
        │
   ┌────┴───────────────────────────┐
   ▼                                ▼
Effect 1 (Render VNode)      Effect 2 (Computed Total)
```

Proses *tracking* dan *triggering* diatur melalui invokasi deterministik:
- **`track(target, type, key)`**: Dieksekusi pada *trap* `get()` milik `Proxy`. Mengambil instance `activeSub` (subskripsi aktif dari `ReactiveEffect`). Jika dependensi belum terdaftar dalam `dep`, efek tersebut akan ditambahkan ke daftar pengamat (*subscriber*), dan dependensi tersebut dicatat pada linked-list efek pemanggil untuk pembersihan (*cleanup*).
- **`trigger(target, type, key, newValue, oldValue)`**: Dieksekusi pada *trap* `set()` atau mutasi koleksi (`add`, `delete`). Mengumpulkan seluruh efek terkait properti tersebut ke dalam antrean batching untuk dieksekusi ulang secara terjadwal.

#### 3.2. Virtual DOM Diffing Engine & Optimasi Kompilator
Vue 3 membedakan dirinya dari Virtual DOM murni (seperti React standard) melalui **Compiler-Informed Virtual DOM**:
- **PatchFlags**: Pengenal numerik berbasis *bitwise* yang disuntikkan langsung oleh kompilator template ke dalam representasi VNode. Contohnya, `1 (TEXT)` menandakan hanya teks interpolasi yang dinamis, `8 (PROPS)` menandakan hanya atribut tertentu yang dinamis. Algoritma diffing runtime membaca flag ini melalui bitwise AND (`patchFlag & PatchFlags.TEXT`) dan langsung melompati rekonsiliasi atribut statis, children, atau styling yang tidak berubah.
- **Block Tree & ShapeFlags**: Kompilator membungkus elemen dinamis di dalam node penampung yang disebut "Block". Block mempertahankan properti `dynamicChildren: VNode[]`. Saat mutasi terjadi, runtime diffing tidak perlu melakukan penelusuran pohon penuh (Deep Tree Traversal $O(N)$), melainkan hanya melakukan iterasi datar (Flat Array Traversal $O(K)$, di mana $K$ adalah jumlah node dinamis).
- **Fast Path Algorithm (Longest Increasing Subsequence)**: Ketika array children dinamis memiliki *keys*, Vue 3 menggunakan algoritma diffing dua arah (sinkronisasi prefix dan suffix), dilanjutkan dengan pencarian *Longest Increasing Subsequence* (LIS) berbasis binary search ($O(N \log N)$) untuk menentukan jumlah node minimum yang perlu digeser pada DOM fisik.

#### 3.3. Scheduler Runtime & Microtask Batching
Setiap mutasi reaktif tidak langsung merender ulang DOM secara sinkron. Siklus pembaruan diatur oleh antrean `Scheduler`:
- Ketika `trigger()` terpanggil, `effect.scheduler()` menambahkan efek tersebut ke dalam set antrean `queue`.
- Set ini di-resolve menggunakan `Promise.resolve().then(flushJobs)` (microtask).
- Scheduler mengeksekusi sorting job berdasarkan `job.id` menaik. Ini menjamin:
  1. Komponen induk diperbarui sebelum komponen anak (karena induk selalu dibuat lebih dulu).
  2. Jika komponen anak di-unmount saat pembaruan induk, eksekusi pembaruan anak dapat diabaikan.
- **Flush Timing Modes**:
  - `pre`: Watcher dieksekusi sebelum komponen DOM di-render.
  - `post`: Watcher dieksekusi setelah komponen DOM di-render (berguna untuk mengakses referensi DOM yang telah diperbarui).
  - `sync`: Watcher dieksekusi secara instan dan sinkron tanpa masuk antrean microtask (berbahaya untuk performa jika memicu mutasi kaskade).

---

### 4. Why & What

| Dimensi | Vue 3 Enterprise Stack | Pendekatan Tradisional (Vue 2 / Naive VDOM) | Keuntungan Arsitektural |
| :--- | :--- | :--- | :--- |
| **Metode Proxy** | ES2015 `Proxy` | `Object.defineProperty` getter/setter | Menangkap penambahan/penghapusan properti dinamis dan mutasi indeks Array secara natif tanpa API bantuan (`$set`, `$delete`). Penghematan memori hingga ~50% saat inisialisasi state besar. |
| **Diffing Model** | Block Tree + Dynamic Children Array | Full-tree recursive reconciliation | Mengurangi beban CPU JavaScript secara drastis saat rekonsiliasi; hanya memproses node yang berubah tanpa memindai node statis. |
| **Tree-shaking** | Modular micro-packages (`@vue/runtime-dom`, `@vue/reactivity`) | Monolithic library core | Fitur opsional (misal: `<Transition>`, `v-model` modifiers) otomatis tereliminasi dari bundle akhir jika tidak diimpor. |
| **Lifecycle Scope** | `EffectScope` API | Manual track and teardown unwatchers | Memungkinkan isolasi, pause, dan dispose seluruh efek reaktif modular secara serentak, mencegah kebocoran memori pada arsitektur micro-frontend. |

---

### 5. How (Workflow detail)

```
[Template/Render Source]
         │
         ▼
[Vue Compiler (AST Construction & Static Analysis)]
         │
         ├─► Static Hoisting (Node statis diekstraksi ke luar render function)
         ├─► Slot Flag Detection
         └─► PatchFlag & Dynamic Children Tagging
         │
         ▼
[VNode Creation: createVNode(..., PatchFlags)]
         │
         ▼
[Runtime Scheduler / Reactive Effect]
         │
         ▼ (Data mutates -> Proxy Trap Trigger)
[Schedule Job enqueued into Microtask Queue]
         │
         ▼ (Promise Resolution)
[flushJobs() invoked]
         │
         ├─► Sort Queue (Parent to Child by Component ID)
         ├─► Execute Pre-Flush Watchers
         ├─► patchElement(n1, n2) via Fast Path (Block Tree & PatchFlags)
         │       └─► (If keyed children changed) Execute LIS Algorithm
         └─► Execute Post-Flush Watchers (e.g., watchPostEffect)
```

Alur eksekusi reaktif dari penulisan kode hingga mutasi browser DOM:
1. **Compilation Phase**: Template dikompilasi menjadi fungsi `render()`. Simbol-simbol statis di-*hoist* ke luar cakupan komponen agar tidak dialokasikan ulang di setiap siklus render.
2. **Setup Execution**: Skrip `setup()` dieksekusi sekali. Pemanggilan `ref()` dan `reactive()` menghasilkan wrapper `Proxy`.
3. **Mounting Phase**: Runtime membungkus pemanggilan fungsi `render()` ke dalam instance `ReactiveEffect`. Saat `render()` dieksekusi pertama kali, pembacaan nilai properti memicu trap `get()`, yang menjalankan `track()`. Ini mendaftarkan render effect ke dalam dependensi properti terkait.
4. **Mutation Phase**: Nilai properti diubah (`state.count++`). Trap `set()` mengintersepsi nilai baru dan menjalankan `trigger()`.
5. **Batching Phase**: `trigger()` mengambil subskripsi dari `targetMap` dan menyerahkan efek ke `queueJob`. Scheduler menunda eksekusi ke batas microtask menggunakan `Promise.resolve()`.
6. **Patching Phase**: Antrean diproses (`flushJobs`). Engine membandingkan VNode lama ($n_1$) dan VNode baru ($n_2$). Jika terdapat `PatchFlags`, rekonsiliasi melewati node anak statis dan langsung memodifikasi simpul DOM target menggunakan Web API native (`node.nodeValue`, `setAttribute`).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Kantor Redaksi Berita Skala Masif
Bayangkan sistem pemberitaan surat kabar:
- **`targetMap`**: Papan indeks pusat di seluruh kantor redaksi yang mencatat seluruh topik berita yang ada di dunia.
- **`dep` (Dependency)**: Daftar pelanggan koran edisi khusus untuk satu topik spesifik (misal: "Krisis Moneter").
- **`ReactiveEffect`**: Agen reporter atau mesin cetak yang bertugas memperbarui halaman depan. Ketika data topik berubah, hanya mesin cetak yang terdaftar di topik tersebut yang dibangunkan.
- **`PatchFlags`**: Kacamata pembaca kilat yang hanya menyorot teks bertinta merah tebal, mengabaikan 99% paragraf statis bertinta hitam biasa.
- **`Scheduler`**: Manajer percetakan yang menolak mencetak koran satu per satu setiap kali ada pembaruan kalimat, melainkan menampung semua memo pembaruan selama 1 jam, merapikannya, dan mencetak satu edisi kompilasi final secara serentak.

#### Diagram Algoritma Diffing: Keyed List Reconciliation via LIS
```
VNode Lama (n1):  [ A, B, C, D, E, F ]
VNode Baru (n2):  [ A, C, B, E, D, G, F ]

Langkah 1: Sinkronisasi Prefix (kiri ke kanan)
Cocok: Node [ A ] -> Lewati reconciler DOM.

Langkah 2: Sinkronisasi Suffix (kanan ke kiri)
Cocok: Node [ F ] -> Lewati reconciler DOM.

Sisa Sub-array yang tidak sinkron:
Tengah n1: [ B, C, D, E ]
Tengah n2: [ C, B, E, D, G ]

Langkah 3: Pemetaan Indeks & Komputasi LIS
Indeks n1 di n2:
C -> Posisi 0
B -> Posisi 1
E -> Posisi 2
D -> Posisi 3
G -> Posisi 4 (Node Baru -> Mount langsung)

Map Indeks Relatif: [1, 0, 3, 2]
Longest Increasing Subsequence (LIS): Indeks [0, 2] (Elemen C dan E)

Operasi DOM Aktual:
- Node C dan E Dibiarkan Statis (Zero Move).
- Node B dan D dipindahkan posisinya secara fisik menggunakan Node.insertBefore().
- Node G dibuat baru (Node.appendChild/insertBefore).
Hasil: Mutasi DOM seminimal mungkin, menghemat repaint/reflow browser.
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Mengimplementasikan Reaktivitas Minimal Mandiri (Mini Vue Reactivity)
Contoh berikut membongkar abstraksi internal Vue 3 dengan membuat ulang fungsionalitas inti `ref`, `track`, `trigger`, dan `effect`.

```typescript
// mini-reactivity.ts
type Dep = Set<ReactiveEffect>;
type KeyToDepMap = Map<any, Dep>;

const targetMap = new WeakMap<object, KeyToDepMap>();
let activeEffect: ReactiveEffect | null = null;

class ReactiveEffect {
  constructor(public fn: () => void) {}
  run() {
    activeEffect = this;
    try {
      this.fn();
    } finally {
      activeEffect = null;
    }
  }
}

export function effect(fn: () => void) {
  const _effect = new ReactiveEffect(fn);
  _effect.run();
}

function track(target: object, key: unknown) {
  if (!activeEffect) return;

  let depsMap = targetMap.get(target);
  if (!depsMap) {
    depsMap = new Map();
    targetMap.set(target, depsMap);
  }

  let dep = depsMap.get(key);
  if (!dep) {
    dep = new Set();
    depsMap.set(key, dep);
  }

  dep.add(activeEffect);
}

function trigger(target: object, key: unknown) {
  const depsMap = targetMap.get(target);
  if (!depsMap) return;

  const dep = depsMap.get(key);
  if (dep) {
    const effectsToRun = new Set(dep);
    effectsToRun.forEach((eff) => eff.run());
  }
}

export function ref<T>(initialValue: T) {
  let value = initialValue;
  return {
    get value(): T {
      track(this, 'value');
      return value;
    },
    set value(newVal: T) {
      if (newVal !== value) {
        value = newVal;
        trigger(this, 'value');
      }
    }
  };
}

// Verifikasi Eksekusi Mini Reactivity
const counter = ref(0);
effect(() => {
  console.log(`[MiniReactivity Log] Counter value: ${counter.value}`);
});

counter.value = 1; // Memicu eksekusi effect: Output 1
counter.value = 2; // Memicu eksekusi effect: Output 2
```

#### Practical Example: High-Throughput Safe Composable dengan Auto-Disposal Lifecycle
Implementasi enterprise composable untuk streaming data real-time berbasis WebSocket, dengan memanfaatkan `effectScope` untuk isolasi alokasi memori reaktif dan pencegahan kebocoran koneksi.

```typescript
// composables/useEnterpriseTelemetry.ts
import { ref, readonly, effectScope, onScopeDispose, type Ref } from 'vue';

export interface TelemetryPayload {
  readonly deviceId: string;
  readonly metric: number;
  readonly timestamp: number;
}

export interface TelemetryStreamOptions {
  heartbeatIntervalMs?: number;
  maxBufferLength?: number;
}

export function useEnterpriseTelemetry(
  endpointUrl: string,
  options: TelemetryStreamOptions = {}
) {
  const { heartbeatIntervalMs = 5000, maxBufferLength = 100 } = options;

  const data: Ref<TelemetryPayload[]> = ref([]);
  const isConnected = ref(false);
  const error: Ref<Error | null> = ref(null);

  // Mengisolasi efek reaktif composable ke dalam cakupan lokal
  const scope = effectScope();

  scope.run(() => {
    let socket: WebSocket | null = null;
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null;

    const initializeConnection = () => {
      try {
        socket = new WebSocket(endpointUrl);

        socket.onopen = () => {
          isConnected.value = true;
          error.value = null;
          heartbeatTimer = setInterval(() => {
            if (socket?.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: 'PING' }));
            }
          }, heartbeatIntervalMs);
        };

        socket.onmessage = (event: MessageEvent<string>) => {
          try {
            const parsed: TelemetryPayload = JSON.parse(event.data);
            // Menghindari reallocation massal, batasi ukuran buffer array
            if (data.value.length >= maxBufferLength) {
              data.value.shift();
            }
            data.value.push(parsed);
          } catch (err) {
            console.error('[Telemetry Composable] Parsing failure', err);
          }
        };

        socket.onerror = (ev: Event) => {
          error.value = new Error(`WebSocket Error: ${JSON.stringify(ev)}`);
        };

        socket.onclose = () => {
          isConnected.value = false;
          if (heartbeatTimer) clearInterval(heartbeatTimer);
        };
      } catch (err) {
        error.value = err instanceof Error ? err : new Error('Unknown Socket Exception');
      }
    };

    initializeConnection();

    // Pembersihan resource ketika lifecycle scope induk di-unmount
    onScopeDispose(() => {
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
        socket = null;
      }
      data.value = [];
    });
  });

  return {
    data: readonly(data),
    isConnected: readonly(isConnected),
    error: readonly(error),
    dispose: () => scope.stop()
  };
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario Kasus: Orderbook Pasar Finansial Berfrekuensi Tinggi (Crypto/Equities Exchange)
- **Konteks**: Dashboard trading enterprise menerima 2.500 mutasi perubahan harga/volume per detik melalui WebSocket.
- **Masalah**:
  - Implementasi naif menggunakan `ref<OrderbookRow[]>` menyebabkan thread utama browser *freeze* (frame rate drop ke 4 FPS).
  - Alokasi Garbage Collector (GC) mencapai 1.2 GB per menit akibat instansiasi objek VNode yang berulang-ulang.
  - Diffing Virtual DOM memindai 1.000 baris tabel setiap kali 1 tick harga berubah.
- **Solusi Rekayasa Berbasis Arsitektur Vue 3**:
  1. **Shallow Data Modeling**: Mengganti `ref` dalam yang dalam (*deep reactive*) dengan `shallowRef`. State orderbook disimpan dalam struktur Flat Array berindeks tetap (`Float64Array` atau array mutasi langsung tanpa membungkus setiap cell dalam `Proxy`).
  2. **Microtask Throttling / Custom Scheduler**: Mutasi dari WebSocket dikumpulkan ke dalam ring buffer di luar zona reaktivitas Vue. Scheduler kustom memicu update `shallowRef.value` hanya sekali per frame sinkronisasi tampilan browser ($16.6\text{ ms}$ via `requestAnimationFrame`).
  3. **Virtual DOM Bypass via Custom Directive/Manual DOM Patching**: Menggunakan patching text node DOM secara langsung untuk sel harga yang sering berkedip, memotong rekonsiliasi VDOM sepenuhnya.

#### Arsitektur Solusi (Ring Buffer + RAF Throttling)
```
WebSocket Raw Ticks (2500 events/sec)
         │
         ▼
[Typed Array Ring Buffer (Non-Reactive Zone)]
         │
         ├─► Aggregator Thread (WASM / Web Worker)
         │
         ▼
[requestAnimationFrame Loop (Setiap 16.6ms)]
         │
         ▼
Trigger shallowRef manual notification (triggerRef)
         │
         ▼
Vue VNode Patch (Hanya 60 FPS Render Cycles)
```

#### Implementasi Kernel Streaming Engine:
```typescript
// engine/OrderbookEngine.ts
import { shallowRef, triggerRef } from 'vue';

export interface OrderRow {
  readonly price: number;
  volume: number;
}

export class OrderbookEngine {
  // shallowRef hanya mentracking mutasi referensi pointer .value, bukan properti di dalamnya
  public orders = shallowRef<Map<number, OrderRow>>(new Map());
  private pendingChanges = new Map<number, number>();
  private isRafScheduled = false;

  public ingestTick(price: number, volume: number): void {
    this.pendingChanges.set(price, volume);

    if (!this.isRafScheduled) {
      this.isRafScheduled = true;
      requestAnimationFrame(this.flushBatch);
    }
  }

  private flushBatch = (): void => {
    const currentOrders = this.orders.value;

    this.pendingChanges.forEach((volume, price) => {
      if (volume <= 0) {
        currentOrders.delete(price);
      } else {
        const existing = currentOrders.get(price);
        if (existing) {
          existing.volume = volume;
        } else {
          currentOrders.set(price, { price, volume });
        }
      }
    });

    this.pendingChanges.clear();
    this.isRafScheduled = false;

    // Secara eksplisit memicu reactivity engine tanpa instansiasi ulang objek Map
    triggerRef(this.orders);
  };
}
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **`ref()` (Deep Reactivity)** | Mutasi otomatis terpantau tanpa intervensi manual; aman digunakan developer pemula dan menengah. | Konsumsi memori melonjak jika menyimpan dataset raksasa (ribuan baris), overhead inisialisasi rekursif Proxy, tekanan GC tinggi. |
| **`shallowRef()` / `markRaw()`** | Overhead inisialisasi mendekati $O(1)$; performa rendering identik dengan JavaScript murni. | Mutasi internal properti tidak mentrigger render; memerlukan mekanisme manual (`triggerRef()`), memperbesar kemungkinan bug "UI not updating". |
| **Direct DOM Manipulation via Ref** | Melewati abstraksi VNode Diffing secara total; latensi rendering sub-millisecond untuk kasus ekstrem. | Mematahkan paradigma deklaratif; rawan memicu State Desynchronization dan konflik saat komponen di-patch oleh parent VNode. |
| **Custom Renderer Engine (`createRenderer`)** | Memungkinkan Vue merender ke Canvas (Pixi.js), Terminal UI, atau Native Mobile tanpa dependensi Web Browser. | Harus mengimplementasikan seluruh operasi pohon DOM node secara manual (`insert`, `remove`, `patchProp`, `createElement`); kompleksitas pemeliharaan tinggi. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Reaktivitas Hilang Akibat Destrukturisasi Objek
- **Kesalahan**: Melakukan destructuring langsung pada objek `reactive()`.
  ```typescript
  const state = reactive({ count: 0, user: 'John' });
  const { count } = state; // Reaktivitas putus! count menjadi primitif number biasa.
  ```
- **Solusi**: Gunakan `toRefs()` atau `toRef()` untuk menjaga getter/setter proxy tetap tersambung ke sumber aslinya.
  ```typescript
  import { toRefs } from 'vue';
  const { count } = toRefs(state); // count bertipe Ref<number>, tetap reaktif.
  ```

#### 10.2. Kebocoran Memori (Memory Leak) dari Async Event & Timer pada Composable
- **Gejala**: Heap snapshot di Chrome DevTools terus menanjak tajam seiring navigasi halaman antar router view.
- **Penyebab**: Event listener global (`window.addEventListener`) atau `setInterval` yang dibuat dalam composable tidak dibersihkan saat komponen di-unmount.
- **Troubleshooting & Perbaikan**:
  Gunakan hook siklus hidup yang terikat ke instance komponen, atau jalankan composable di dalam `effectScope`.
  ```typescript
  import { onMounted, onUnmounted } from 'vue';

  export function useWindowResize() {
    const handler = () => { /* Handle resize */ };
    onMounted(() => window.addEventListener('resize', handler));
    // WAJIB DIHAPUS:
    onUnmounted(() => window.removeEventListener('resize', handler));
  }
  ```

#### 10.3. Loop Reaktif Tak Terbatas (Infinite Reactivity Loop) pada Watcher
- **Penyebab**: Memodifikasi state yang sedang diamati oleh watcher sinkron (`flush: 'sync'`) tanpa guard clause condition.
- **Debug Matrix**:

| Pesan Eror / Gejala | Root Cause Teknis | Solusi Diagnostik |
| :--- | :--- | :--- |
| `Maximum recursive updates exceeded...` | Watcher memodifikasi variabel dependen yang memicu watcher itu sendiri secara sirkular. | Berikan guard clause: `if (newVal === targetState) return;` atau pindahkan timing eksekusi ke `flush: 'post'`. |
| `Component is mounted, but DOM queries return null` | Mengakses referensi template ref DOM pada watcher bereksekusi default (`pre-flush`). | Ubah konfigurasi watcher menjadi `flush: 'post'` atau gunakan helper `watchPostEffect()`. |

---

### 11. Best Practices (Production Checklist)

#### Arsitektur & State Management
- [ ] Hindari menyimpan state non-reaktif besar (misal: instance client HTTP, WebGL Context, SDK Third-Party) di dalam `ref()` atau `reactive()`. Bungkus selalu menggunakan `markRaw()`.
- [ ] Gunakan `shallowRef` atau `shallowReactive` untuk koleksi data pagination atau data log tabular yang bersifat *read-heavy* dan berjumlah di atas $1.000$ item.
- [ ] Wajib mendeklarasikan generic explicit pada saat memanggil `ref<T>()` untuk menjamin keselarasan runtime dengan compile-time typing.

#### Rendering & Virtual DOM Optimization
- [ ] Pastikan seluruh blok perulangan `v-for` menggunakan `key` yang unik dan deterministik (misal: UUID atau Primary Key database). Dilarang keras menggunakan *array index* sebagai `key` pada elemen dinamis yang dapat dihapus, digeser, atau disortir.
- [ ] Pisahkan bagian template statis berukuran besar ke dalam komponen statis mandiri atau manfaatkan kompilator *hoisting* untuk menghindari alokasi ulang VNode children.
- [ ] Terapkan `v-once` untuk elemen/komponen yang dijamin tidak akan pernah berubah setelah initial mount.
- [ ] Terapkan `v-memo="[depA, depB]"` untuk list tabel masif guna mengabaikan proses VNode diffing sepenuhnya jika nilai primitif penentu kondisinya tidak berubah.

#### Bundle Engineering
- [ ] Matikan *Vue Features Flag* yang tidak digunakan pada build level (misal via Vite config: nonaktifkan `__VUE_OPTIONS_API__: false` dan `__VUE_PROD_DEVTOOLS__: false` untuk menghemat puluhan kilobyte ukuran bundle akhir).

---

### 12. Hands-on Practice

Buatlah implementasi arsitektur custom state manager berkinerja tinggi yang terisolasi di folder:
`hands-on/m02/`

#### Struktur Berkas
```
hands-on/m02/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
└── src/
    ├── core/
    │   └── ReactiveStore.ts
    ├── composables/
    │   └── useObservableStore.ts
    └── App.vue
```

#### Langkah 1: Inisialisasi Environment
Jalankan di shell:
```bash
mkdir -p hands-on/m02/src/core hands-on/m02/src/composables
cd hands-on/m02
npm init -y
npm i vue@^3.4.0
npm i -D typescript@^5.3.0 vite@^5.0.0 @vitejs/plugin-vue
```

Konfigurasikan `hands-on/m02/vite.config.ts`:
```typescript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  define: {
    __VUE_OPTIONS_API__: JSON.stringify(false),
    __VUE_PROD_DEVTOOLS__: JSON.stringify(false)
  }
});
```

#### Langkah 2: Implementasi Reactive Store Kernel
Tulis kode berikut pada `hands-on/m02/src/core/ReactiveStore.ts`:
```typescript
import { shallowRef, triggerRef, readonly, type DeepReadonly } from 'vue';

export abstract class ReactiveStore<T extends Record<string, any>> {
  private _state = shallowRef<T>({} as T);

  constructor(initialState: T) {
    this._state.value = initialState;
  }

  public get state(): DeepReadonly<T> {
    return readonly(this._state.value) as DeepReadonly<T>;
  }

  /**
   * Mutasi state atomik dengan isolasi pembacaan
   */
  protected update(mutator: (draft: T) => void): void {
    mutator(this._state.value);
    triggerRef(this._state);
  }
}
```

#### Langkah 3: Implementasi Store Khusus & Composable
Tulis kode berikut pada `hands-on/m02/src/composables/useObservableStore.ts`:
```typescript
import { onScopeDispose } from 'vue';
import { ReactiveStore } from '../core/ReactiveStore';

interface MetricsState {
  fps: number;
  memoryUsageMb: number;
  lastUpdated: number;
}

class MetricsStore extends ReactiveStore<MetricsState> {
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    super({ fps: 60, memoryUsageMb: 24.5, lastUpdated: Date.now() });
    this.startMockTelemetry();
  }

  private startMockTelemetry() {
    this.timer = setInterval(() => {
      this.update((draft) => {
        draft.fps = Math.floor(58 + Math.random() * 5);
        draft.memoryUsageMb = +(24 + Math.random() * 2).toFixed(2);
        draft.lastUpdated = Date.now();
      });
    }, 1000);
  }

  public stopTelemetry() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}

export function useMetrics() {
  const store = new MetricsStore();

  onScopeDispose(() => {
    store.stopTelemetry();
  });

  return {
    metrics: store.state
  };
}
```

#### Langkah 4: Hubungkan ke UI App
Tulis kode berikut pada `hands-on/m02/src/App.vue`:
```vue
<script setup lang="ts">
import { useMetrics } from './composables/useObservableStore';

const { metrics } = useMetrics();
</script>

<template>
  <main style="font-family: sans-serif; padding: 2rem;">
    <h1>Enterprise Metrics Monitor</h1>
    <div style="display: grid; gap: 1rem; max-width: 300px;">
      <div style="border: 1px solid #ccc; padding: 1rem; border-radius: 8px;">
        <strong>FPS Engine:</strong> {{ metrics.fps }}
      </div>
      <div style="border: 1px solid #ccc; padding: 1rem; border-radius: 8px;">
        <strong>RAM Usage:</strong> {{ metrics.memoryUsageMb }} MB
      </div>
      <div style="border: 1px solid #ccc; padding: 1rem; border-radius: 8px;">
        <strong>Timestamp:</strong> {{ new Date(metrics.lastUpdated).toLocaleTimeString() }}
      </div>
    </div>
  </main>
</template>
```

---

### 13. Exercise

#### Level Easy
**Soal**: Buat custom composable `useCounter` menggunakan Composition API murni dan `ref`. Tambahkan proteksi agar nilai counter tidak pernah turun di bawah angka `0` (non-negative constraint).

*Solusi Singkat*:
```typescript
import { ref, readonly } from 'vue';

export function useCounter(initialValue = 0) {
  const count = ref(Math.max(0, initialValue));
  const increment = () => count.value++;
  const decrement = () => {
    if (count.value > 0) count.value--;
  };
  return { count: readonly(count), increment, decrement };
}
```

#### Level Medium
**Soal**: Buat custom composable `useDebouncedRef<T>(value: T, delayMs: number)` yang mengembalikan `Ref<T>`, namun mutasi perubahannya ke dependensi pengamat (effect/watcher) ditunda hingga durasi debounce berakhir menggunakan custom implementation via `customRef`.

*Solusi Singkat*:
```typescript
import { customRef } from 'vue';

export function useDebouncedRef<T>(initialValue: T, delayMs = 300) {
  let timeout: ReturnType<typeof setTimeout>;
  let internalValue = initialValue;

  return customRef((track, trigger) => ({
    get() {
      track();
      return internalValue;
    },
    set(newValue: T) {
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        internalValue = newValue;
        trigger();
      }, delayMs);
    }
  }));
}
```

#### Level Hard
**Soal**: Rancang sebuah `Custom Directives` bernama `v-perf-track` yang menghitung berapa kali sebuah elemen spesifik di-mount ulang atau di-patch oleh Vue runtime, dan cetak peringatan ke konsol jika elemen tersebut mengalami *thrashing* (di-patch lebih dari 30 kali dalam jendela waktu 1 detik).

*Solusi Singkat*:
```typescript
import type { Directive } from 'vue';

interface PerfTrackingData {
  count: number;
  startTime: number;
}

const map = new WeakMap<HTMLElement, PerfTrackingData>();

export const vPerfTrack: Directive<HTMLElement> = {
  mounted(el) {
    map.set(el, { count: 0, startTime: performance.now() });
  },
  updated(el) {
    const data = map.get(el);
    if (!data) return;

    data.count++;
    const elapsed = performance.now() - data.startTime;

    if (elapsed < 1000 && data.count > 30) {
      console.warn(`[Perf Warning] DOM Thrashing detected on:`, el, `Patched ${data.count} times in ${elapsed.toFixed(0)}ms`);
    }

    if (elapsed >= 1000) {
      data.count = 0;
      data.startTime = performance.now();
    }
  },
  unmounted(el) {
    map.delete(el);
  }
};
```

---

### 14. Challenge

#### Skenario Kasus Kompleks: Arsitektur Global Cache Multi-Tab Sinkron dengan SharedWorker & WebLocks API

**Deskripsi Masalah**:
Perusahaan SaaS Anda memiliki sistem analitik berbasis multi-tab di mana pengguna sering membuka 5 hingga 10 tab browser secara bersamaan ke aplikasi yang sama. 
Saat ini, setiap tab melakukan polling terpisah ke REST/GraphQL API setiap 2 detik. Ini menyebabkan:
1. Beban server meningkat 10x lipat per pengguna aktif.
2. Kondisi *race conditions* saat mutasi hak akses (Role Authorization) dilakukan di satu tab, tab lain masih menggunakan state usang (*stale authorization*).

**Spesifikasi Teknis Tantangan**:
1. Bangun composable Vue 3 enterprise bernama `useSharedTabState<T>(key: string, initialValue: T)` yang:
   - Menggunakan `SharedWorker` atau perpaduan `BroadcastChannel` dan Web `navigator.locks` API.
   - Mengorkestrasi pemilihan 1 tab browser sebagai **Leader** (Primary Worker Node) yang bertugas melakukan fetching ke backend, sementara tab-tab lainnya bertindak sebagai **Follower**.
   - Menyediakan sinkronisasi reaktivitas atomik 2 arah: mutasi lokal pada tab manapun harus terpropagasi secara non-blocking ke antrean reaktivitas seluruh tab yang aktif.
   - Memiliki ketahanan *failover*: jika tab Leader ditutup oleh user, salah satu tab Follower harus otomatis dipromosikan menjadi Leader dalam waktu $< 200\text{ ms}$ tanpa kehilangan state terakhir.
   - Wajib mematuhi lifecycle isolation menggunakan `effectScope` agar composable tidak meninggalkan sisa instance socket/listener saat komponen tempat ia hidup di-unmount.

*Catatan: Kerjakan tantangan ini dengan menyusun modul TypeScript terisolasi tanpa library runtime eksternal selain paket bawaan `@vue/reactivity` dan `@vue/runtime-core`.*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. **Mengapa Vue 3 beralih dari `Object.defineProperty` ke `Proxy`?**
   - *Jawaban*: `Proxy` memungkinkan deteksi operasi yang sebelumnya tidak dapat dipantau oleh `Object.defineProperty`, seperti penambahan properti baru, penghapusan properti (`delete`), serta mutasi langsung pada indeks dan ukuran array tanpa memerlukan API mutator penolong khusus.
2. **Kapan instance subskripsi dependensi dicatat oleh runtime Vue 3?**
   - *Jawaban*: Saat fase get/evaluasi nilai properti (`trap get()`) yang berjalan di dalam cakupan eksekusi `ReactiveEffect` yang aktif (misalnya saat merender template, mengeksekusi `computed`, atau menjalankan callback `watchEffect`).
3. **Apa perbedaan mendasar antara `ref()` dan `shallowRef()`?**
   - *Jawaban*: `ref()` mengonversi seluruh objek nested yang ada di dalamnya menjadi proxy reaktif rekursif, sedangkan `shallowRef()` hanya memantau mutasi nilai aksesor pointer `.value`-nya saja tanpa membuat proxy untuk properti di dalam objeknya.
4. **Apa fungsi dari atribut `key` pada `v-for` list?**
   - *Jawaban*: Menyediakan identitas unik pada VNode agar algoritma Diffing (LIS) dapat mengenali elemen yang berpindah posisi dan mempertahankan state lokal instance elemen tersebut, meminimalkan operasi pembuatan ulang node DOM.
5. **Bagaimana cara menghentikan eksekusi seluruh watcher/computed secara bersamaan di dalam suatu blok fungsi?**
   - *Jawaban*: Mengelompokkan inisialisasinya di dalam cakupan `effectScope()` dan memanggil method `.stop()` pada instance scope tersebut.

#### Intermediate (5 Pertanyaan)
1. **Jelaskan peran `PatchFlags` dalam optimasi Virtual DOM Vue 3!**
   - *Jawaban*: `PatchFlags` adalah penanda bitwise kompilator yang melabeli jenis mutasi dinamis elemen. Ini memungkinkan fungsi rekonsiliasi melewati pemeriksaan statis (class, style, props) dan langsung melompat hanya ke properti dinamis spesifik sesuai representasi bitwise flag tersebut.
2. **Mengapa pemanggilan `toRefs()` diperlukan saat melakukan destructuring props pada Vue 3 Composition API?**
   - *Jawaban*: Karena props diakses melalui objek proxy. Melakukan destructuring langsung pada objek JavaScript biasa akan menyalin nilai primitifnya secara terpisah, sehingga memutuskan koneksi getter proxy bawaan yang mengikat tracking reaktivitas ke sumbernya.
3. **Bagaimana scheduler Vue menangani pembaruan berulang yang dipicu dalam loop sinkron yang sama?**
   - *Jawaban*: Scheduler memasukkan job ke antrean internal dan memanfaatkan struktur data unik (Set atau array ter-deduplikasi) lalu memprosesnya secara asinkron dalam satu siklus microtask melalui `Promise.resolve()`, sehingga hanya mengeksekusi render akhir 1 kali.
4. **Apa perbedaan antara watch timing `flush: 'pre'` dan `flush: 'post'`?**
   - *Jawaban*: `flush: 'pre'` mengeksekusi callback watcher sebelum Virtual DOM selesai di-patch ke DOM browser, sedangkan `flush: 'post'` mengeksekusinya setelah mutasi DOM selesai diterapkan ke antarmuka layar.
5. **Kapan kita harus membungkus objek pihak ketiga dengan `markRaw()`?**
   - *Jawaban*: Ketika kita menyimpan instance objek non-primitif yang kompleks (seperti Three.js scene, Chart.js instances, atau Axios instance) yang memiliki dependensi internal method yang luas, untuk mencegah Vue membungkusnya ke dalam proxy yang dapat merusak struktur internal objek atau memicu overhead pemindaian memori yang masif.

#### Kasus Produksi Enterprise (3 Skenario)

1. **Skenario 1**: 
   Sebuah aplikasi analitik e-commerce merender tabel dinamis dengan $5.000$ baris data. Setiap kali ada 1 status pesanan diperbarui dari backend, seluruh halaman mengalami frame rate drop drastis hingga 500ms. Setelah dianalisis, ternyata seluruh baris tabel di-render ulang.
   - *Tindakan Diagnostik & Solusi*:
     1. Analisis `key` pada `v-for`: Pastikan tidak menggunakan array index, gunakan order ID unik.
     2. Bungkus baris komponen menggunakan `v-memo="[order.status, order.updatedAt]"` agar VNode diffing sepenuhnya melompati baris yang statusnya tidak berubah.
     3. Ubah referensi state tabel induk dari `ref()` menjadi `shallowRef()` agar tidak membungkus 5000 item objek ke dalam deep reactive proxy.

2. **Skenario 2**:
   Di aplikasi perbankan berbasis micro-frontend, sub-aplikasi yang dibangun dengan Vue 3 di-mount dan di-unmount berkali-kali ke dalam shell container DOM. Setelah 1 jam penggunaan, memori browser tab membengkak hingga 2 GB dan tab mengalami crash.
   - *Tindakan Diagnostik & Solusi*:
     1. Lakukan Heap Snapshot perbandingan antar transisi mount/unmount untuk mengidentifikasi objek `Detached HTMLElement` dan array `dep` yang tertinggal.
     2. Identifikasi composable yang mendaftarkan event global (`window`, `document`) atau interval timer tanpa isolasi.
     3. Solusi arsitektur: Seluruh inisialisasi state modul micro-frontend wajib dibungkus dalam master `effectScope()`. Ketika sub-aplikasi di-unmount oleh container, trigger fungsi `scope.stop()` untuk melepaskan seluruh subskripsi `targetMap` dan callback lifecycle secara instan.

3. **Skenario 3**:
   Aplikasi streaming video mengikat pembacaan posisi `currentTime` (yang berubah 60 kali per detik) ke sebuah `ref` yang diamati oleh 10 komponen terpisah di layar. Layar mengalami jitter dan tearing parah pada perangkat mobile.
   - *Tindakan Diagnostik & Solusi*:
     1. Root cause: Mutasi reaktif dengan frekuensi 60Hz membebani runtime scheduler microtask queue secara berlebihan, memblokir rendering pipeline native.
     2. Hentikan tracking `currentTime` via deep reactive `ref`. 
     3. Pisahkan komponen yang benar-benar membutuhkan data resolusi tinggi (misal: progress bar) dan bypass reactivity: gunakan DOM update langsung pada progress bar element atau sinkronkan via canvas API di dalam loop `requestAnimationFrame`. Gunakan `ref` terpisah yang di-*throttle* (misal: 1 detik sekali) untuk komponen tampilan teks waktu yang tidak memerlukan akurasi sub-frame.

---

### 16. Summary
- Mesin reaktivitas Vue 3 bertumpu pada relasi `targetMap` (WeakMap) $\to$ `depsMap` (Map) $\to$ `dep` (Set), di mana trapping operasi interceptor dilakukan melalui ES2015 `Proxy` dan `Reflect`.
- Kompilator template Vue 3 secara cerdas menandai VNode menggunakan **PatchFlags** dan **Block Tree**, mengubah proses Virtual DOM reconciliation dari penelusuran pohon mendalam $O(N)$ menjadi penelusuran array dinamis yang datar $O(K)$.
- Algoritma diffing untuk *keyed children* mengombinasikan optimasi sinkronisasi prefix/suffix dengan penghitungan **Longest Increasing Subsequence** (LIS) untuk menekan jumlah mutasi DOM fisik ke level minimum mutlak.
- Pengaturan skala produksi menuntut pemahaman ketat atas siklus **Scheduler Microtask** dan flush timing (`pre`, `post`, `sync`) guna mencegah infinite recursion dan render blocking.
- Untuk aplikasi performa tinggi dan berfrekuensi data masif, developer enterprise harus memprioritaskan pemanfaatan `shallowRef`, `triggerRef`, `markRaw`, `v-memo`, serta isolasi siklus hidup menggunakan `effectScope` guna menjaga efisiensi Garbage Collection dan skalabilitas memori jangka panjang.