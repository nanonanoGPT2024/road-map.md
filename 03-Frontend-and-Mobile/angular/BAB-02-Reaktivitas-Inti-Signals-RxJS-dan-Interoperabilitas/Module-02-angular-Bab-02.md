# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Signals, RxJS, dan Interoperabilitas)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Membedah Arsitektur Internal Signals:** Memahami model *push-pull reactivity*, struktur data *dependency graph* (`ReactiveNode`, Producers, Consumers), *versioning algorithm*, dan pencegahan *glitch* (*diamond dependency problem*).
- **Merancang Arsitektur Reaktif Hibrida Tingkat Enterprise:** Mengintegrasikan Signals untuk *synchronous UI state management* dan RxJS untuk *asynchronous stream composition*, *concurrency control*, dan *event-driven I/O*.
- **Menguasai Interoperabilitas Tingkat Lanjut:** Menggunakan `@angular/core/rxjs-interop` (`toSignal`, `toObservable`, `outputFromObservable`, `outputToObservable`) secara mendalam, termasuk mitigasi *race conditions*, eksekusi lintas *scheduling boundaries*, dan pengelolaan *injection context*.
- **Membangun Store Reaktif Kustom (Custom Signal Stores):** Mengembangkan arsitektur state kustom yang *type-safe*, *predictable*, dan mendukung *optimistic UI updates* tanpa dependensi pustaka pihak ketiga eksternal.
- **Mengoptimalkan Performa & Diagnostik Memori:** Mengeliminasi kebocoran memori (*memory leaks*), memitigasi *subscription accumulation*, serta mengisolasi eksekusi dari Zone.js menuju arsitektur *Zoneless Change Detection*.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus telah menguasai:
- Pengetahuan mendalam tentang TypeScript 5.x: *Advanced Generics*, *Discriminated Unions*, *Type Narrowing*, dan *Utility Types*.
- Konsep dasar Angular: Arsitektur komponen *standalone*, *Dependency Injection Context*, *lifecycle hooks* (`DestroyRef`), dan Change Detection (`OnPush`).
- Teori Asinkron & Event Loop: Microtasks, Macrotasks, Promises, serta dasar-dasar RxJS Core (*Observable execution*, *Hot vs Cold*, dasar-dasar *Schedulers*, dan *Higher-order Mapping Operators* seperti `switchMap`, `concatMap`, `mergeMap`, `exhaustMap`).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Model Push-Pull Reactivity pada Angular Signals

Angular Signals tidak menggunakan model *push-only* (seperti RxJS murni) ataupun *dirty-checking brute-force* (seperti Zone.js klasik). Signals mengimplementasikan paradigma **Push-Pull Reactivity (Push-Dirty, Pull-Value)**.

```
+-----------------------------------------------------------------+
|                    FASE 1: PUSH (Dirty Notification)           |
|                                                                 |
|  [WritableSignal] (Set value)                                   |
|         |                                                       |
|         v                                                       |
|  Tandai Consumer sebagai "Dirty" (Status Flag: OUT_OF_DATE)     |
|  Kirim notifikasi topologis ke bawah, TANPA kalkulasi ulang     |
+-----------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------+
|                    FASE 2: PULL (Evaluation on Read)            |
|                                                                 |
|  [Consumer / Template / Effect] membaca nilai (.value)          |
|         |                                                       |
|         v                                                       |
|  Cek version counter: Apakah Producer berubah sejak bacaan lalu? |
|  - Jika YA: Eksekusi komputasi, perbarui cache, naikkan versi   |
|  - Jika TIDAK: Kembalikan nilai cache instan (O(1))             |
+-----------------------------------------------------------------+
```

#### Struktur Data Internal: `ReactiveNode`
Di level internal kernel `@angular/core`, setiap signal dan consumer direpresentasikan sebagai `ReactiveNode`. Hubungan antar-node dimodelkan melalui *doubly linked list* atau array pointer dua arah:
- **Producers:** Node yang menyimpan atau menghasilkan nilai (misal: `WritableSignal`, `ComputedNode`).
- **Consumers:** Node yang bergantung pada nilai Producer (misal: `ComputedNode`, `EffectNode`, `TemplateConsumer`).

Ketika sebuah `computed()` dieksekusi:
1. `ReactiveNode` consumer didaftarkan ke dalam *global tracking context* melalui *ambient execution stack*.
2. Setiap kali Producer dibaca via pemanggilan fungsinya `producer()`, Producer mencatat Consumer aktif ke dalam *edge list*-nya, dan Consumer mencatat Producer ke dalam *dependency list*-nya (**Dynamic Dependency Tracking**).
3. Jika pada evaluasi berikutnya sebuah percabangan logika (*conditional branch*) menyebabkan Producer tertentu tidak dibaca lagi, relasi *edge* otomatis diputus (*pruned*) dari graf dependensi. Ini mencegah kebocoran memori dan komputasi sia-sia (*ghost dependencies*).

#### Penyelesaian Masalah "Diamond Dependency" (Glitch-Free Guarantee)

```
        [ Signal A ]
       /            \
      v              v
[ Computed B ]  [ Computed C ]
      \              /
       v            v
        [ Computed D ]
```

Pada sistem reaktif naif berbasis *Push-only*, jika `A` bernilai 1 lalu diubah menjadi 2:
1. `A` memicu `B`, `B` mengupdate `D` (D dievaluasi dengan `B` baru dan `C` lama -> **Glitch/State inkonsisten**).
2. `A` memicu `C`, `C` mengupdate `D` (D dievaluasi ulang dengan `B` baru dan `C` baru).

Angular Signals mengeliminasi masalah ini menggunakan **Topological Ordering** dan **Two-Phase Version Check**:
1. Saat `A` berubah, `A` menandai `B`, `C`, dan `D` sebagai *DIRTY* secara traversal ke bawah (*Push* fase ringan). Tidak ada fungsi komputasi yang dieksekusi pada langkah ini.
2. Ketika consumer akhir (`D`) diminta nilainya (*Pull*):
   - `D` memvalidasi dependensinya terlebih dahulu (`B` dan `C`).
   - `B` dan `C` mengompilasi ulang nilai baru mereka dari `A` dan memperbarui `version`-nya masing-masing.
   - `D` kemudian menghitung nilainya sendiri tepat **satu kali** menggunakan versi mutakhir dari `B` dan `C`. Hasilnya: *Zero glitch*, evaluasi minimal.

---

### 3.2 RxJS: Stream Event-Driven Berbasis Waktu

RxJS beroperasi pada paradigma **Push-Continuous**. Produsen data mendorong nilai ke konsumen secara asinkron atau sinkron melalui pipeline transformasi:
- **Cold Observables:** Pipeline data tidak aktif hingga ada pemanggilan `.subscribe()`. Eksekusi terisolasi per subscriber.
- **Hot Observables:** Produsen memancarkan data terlepas dari keberadaan subscriber (misal: `Subject`, WebSockets, DOM Events).
- RxJS tidak melacak dependensi secara implisit; pengembang wajib mengelola relasi dan *lifespan* aliran secara eksplisit menggunakan operator deklaratif seperti `takeUntilDestroyed`.

---

### 3.3 Interoperability Bridge (`@angular/core/rxjs-interop`)

Penjembatanan antara Signals dan RxJS memerlukan pemahaman siklus hidup (*lifecycle*) dan batas eksekusi (*scheduling boundaries*):

```
+---------------------------------------------------------------------+
|                          toSignal(observable$)                      |
|                                                                     |
|  [RxJS Observable] --(Push Emission)--> [Internal Subscription]     |
|                                                    |                |
|                                                    v                |
|  [Signal Consumer] <-- (Pull Value) ----- [WritableSignal State]    |
|                                                                     |
|  * Subscription terikat pada Injection Context (DestroyRef).        |
|  * Memerlukan initialValue jika Observable asinkron.                |
+---------------------------------------------------------------------+

+---------------------------------------------------------------------+
|                         toObservable(signal)                        |
|                                                                     |
|  [Signal Change]                                                    |
|         |                                                           |
|         v                                                           |
|  [Internal Effect]                                                  |
|         | (Dispatched via Microtask/Change Detection Cycle)         |
|         v                                                           |
|  [ReplaySubject(1)] --(Emit Next)------> [Subscriber Observable]    |
+---------------------------------------------------------------------+
```

> **Catatan Kritis:** `toObservable` tidak memancarkan nilai secara sinkron murni saat Signal berubah. Angular mengeksekusi signal watcher internal di dalam siklus microtask/scheduler internal (`EffectScheduler`). Oleh karena itu, penggabungan cepat (*synchronous back-to-back writes*) pada Signal dapat digabungkan (*coalesced*) sebelum `toObservable` memancarkan nilai terbarunya.

---

## 4. Why & What

| Dimensi Arsitektur | Angular Signals | RxJS Observables |
| :--- | :--- | :--- |
| **Karakteristik Komputasi** | Sinkron, *Pull-based* saat dibutuhkan | Asinkron/Sinkron, *Push-based* berkelanjutan |
| **State Caching** | Selalu memiliki nilai (*Stateful*), memori O(1) | Nilai bergantung operator (`shareReplay`, `BehaviorSubject`), bawaannya *Stateless* |
| **Pelacakan Dependensi** | Otomatis (*Dynamic Dependency Tracking*) | Manual dan Eksplisit melalui perakitan operator |
| **Dimensi Waktu** | Tidak ada konsep waktu (hanya state saat ini) | Mengontrol dimensi waktu (Debounce, Throttle, Delay, Buffer) |
| **Komposisi Multitasking** | Tidak mendukung operasi pembatalan (*cancellation*) | Sangat kuat: `switchMap` (cancel previous), `exhaustMap` (ignore new) |
| **Tujuan Utama Desain** | Sinkronisasi State Komponen, View, dan DOM | Manajemen IO Asinkron, WebSockets, Stream Event Kompleks |

### Mengapa Menggunakan Pendekatan Hibrida?
Menggunakan Signals untuk seluruh kebutuhan aplikasi akan membuat penanganan operasi asinkron kompleks (seperti *debouncing search input*, pembatalan HTTP *in-flight*, *exponential backoff retry*) menjadi berbelit-belit dan rentan bug *race condition*. Sebaliknya, memaksakan RxJS hingga ke template HTML melalui pipa `| async` menciptakan *boilerplate* tinggi, *memory leak vulnerability*, serta *overhead change detection* yang tidak efisien.

**Aturan Arsitektur:**
1. **Gunakan RxJS** pada lapisan *Edge/Infrastructure*: Interaksi API, WebSockets, *event stream processing*, operasi *time-based*, dan konkurensi I/O.
2. **Gunakan Signals** pada lapisan *Core/Presentation*: State model, data derivasi (*computed state*), bind template UI, dan koordinasi antar komponen.

---

## 5. How (Workflow Detail)

Berikut alur kerja integrasi state tingkat enterprise dalam arsitektur reaktif modern:

```
[User Action / Input]
         |
         v
[Component View / Signal Trigger]
         |
         v (toObservable)
[RxJS Orchestration Pipeline]
  - debounceTime(300)
  - distinctUntilChanged()
  - switchMap(query => ApiService.search(query).pipe(
        catchError(...)
    ))
         |
         v (toSignal)
[Signal State Store]
  - state.update(...)
         |
         v
[Computed Derived Selectors]
  - computed(() => filterResults(state()))
         |
         v
[DOM Render / Zoneless Change Detection]
```

Tahapan eksekusi:
1. Event UI memutasi sebuah `WritableSignal` atau memicu RxJS Subject.
2. Jika ada operasi berbasis waktu (*debouncing*, *concurrency switching*), data dialirkan ke RxJS.
3. Hasil pemrosesan RxJS dikembalikan ke domain Signal menggunakan `toSignal` atau mutasi state terkelola.
4. Dependency graph Signals secara atomik menandai node-node terkait sebagai *dirty*.
5. Angular Scheduler mengevaluasi node template yang relevan tanpa perlu memeriksa pohon komponen secara keseluruhan (*fine-grained local updates*).

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem
- **Signals dianalogikan sebagai Lembar Sebar (Spreadsheet):**
  Kolom `C1` memiliki rumus `=A1+B1`. Jika nilai `A1` diubah, `C1` tidak langsung dipaksa mencetak hasilnya ke printer secara instan. `C1` hanya ditandai "butuh kalkulasi ulang". Saat mata Anda (atau layar monitor) melihat ke sel `C1`, barulah rumus dievaluasi dan ditampilkan. Konsisten, sinkron, dan selalu memegang nilai saat ini.
- **RxJS dianalogikan sebagai Jalur Konveyor / Pipa Air Bertekanan:**
  Air yang mengalir melalui berbagai filter (katup, saringan kotoran, pencampur bahan kimia). Jika Anda membuka katup (`subscribe`), Anda menerima aliran air berkelanjutan seiring waktu. Anda dapat membatalkan aliran kapan saja, menahan laju aliran (*throttle*), atau mengalihkan ke pipa cadangan jika pipa utama meledak (*retry/catch*).

### Siklus Internal Diamond Dependency Resolution
```
T0: Initial State: A=1, B=A*2 (2), C=A*10 (10), D=B+C (12)

T1: Set A = 2
    +---------+
    |    A    |  (A.version = 2)
    +---------+
      |     |
      |     |  [PUSH PHASE: Send Dirty Flags Downwards]
      v     v
    +---+ +---+
    | B | | C |  (Flagged: OUT_OF_DATE, but NOT recalculated yet)
    +---+ +---+
      \     /
       v   v
    +---------+
    |    D    |  (Flagged: OUT_OF_DATE)
    +---------+

T2: Consumer membaca D()
    +---------+
    |    D    |  D membaca B() dan C() -> [PULL PHASE]
    +---------+
      |     |
      |     +--> C mengecek A -> A.version > C.lastVersion
      |          C menghitung ulang: 2 * 10 = 20 (C.version = 2)
      |
      +--------> B mengecek A -> A.version > B.lastVersion
                 B menghitung ulang: 2 * 2 = 4   (B.version = 2)

    D menghitung hasil akhir: 4 + 20 = 24 (D.version = 2)
    *Evaluasi bersih, tanpa emisi nilai temporer (glitch-free)*
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Primitive Debounced Signal
Membuat primitif reaktif kustom yang membungkus nilai signal dengan *debounce time* menggunakan interoperabilitas resmi:

```typescript
import { Signal, untracked } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { debounceTime } from 'rxjs/operators';

/**
 * Custom Reactive Primitive: debouncedSignal
 * Mengonversi Signal input menjadi Signal ter-debounce tanpa kebocoran konteks.
 */
export function debouncedSignal<T>(source: Signal<T>, dueTimeMs: number): Signal<T> {
  // 1. Ekstrak nilai awal tanpa mendaftarkan dependensi di level inisialisasi
  const initialValue = untracked(() => source());

  // 2. Jembatani ke RxJS untuk memanfaatkan kapabilitas waktu (debounceTime)
  const source$ = toObservable(source);
  const debounced$ = source$.pipe(debounceTime(dueTimeMs));

  // 3. Kembalikan ke ranah Signal
  return toSignal(debounced$, { initialValue });
}
```

---

### 7.2 Practical Example: Enterprise Hybrid Search & Live-Telemetry Store
Implementasi nyata di mana transaksi pencarian HTTP memiliki *debounce* dan *switch cancellation*, digabungkan dengan koneksi WebSockets secara *real-time*.

```typescript
import { Injectable, computed, inject, signal, DestroyRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { 
  Observable, 
  Subject, 
  combineLatest, 
  of, 
  timer 
} from 'rxjs';
import { 
  catchError, 
  debounceTime, 
  distinctUntilChanged, 
  map, 
  retry, 
  shareReplay, 
  switchMap, 
  tap 
} from 'rxjs/operators';

export interface MarketAsset {
  symbol: string;
  price: number;
  volume24h: number;
  lastUpdated: string;
}

export interface MarketState {
  assets: MarketAsset[];
  loading: boolean;
  error: string | null;
  searchTerm: string;
  activeFilter: 'ALL' | 'VOLUME_GT_1M';
}

@Injectable({
  providedIn: 'root',
})
export class EnterpriseMarketStore {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  private readonly apiUrl = 'https://api.internal.enterprise/v1/markets';

  // --- STATE CORE (Writable Signals) ---
  private readonly _searchTerm = signal<string>('');
  private readonly _activeFilter = signal<'ALL' | 'VOLUME_GT_1M'>('ALL');
  private readonly _loading = signal<boolean>(false);
  private readonly _error = signal<string | null>(null);

  // --- READONLY EXPOSURES ---
  readonly searchTerm = this._searchTerm.asReadonly();
  readonly activeFilter = this._activeFilter.asReadonly();
  readonly loading = this._loading.asReadonly();
  readonly error = this._error.asReadonly();

  // --- ASYNC PIPELINE INTEGRATION (RxJS) ---
  private readonly rawAssets$ = toObservable(this._searchTerm).pipe(
    debounceTime(350),
    distinctUntilChanged(),
    tap(() => {
      this._loading.set(true);
      this._error.set(null);
    }),
    switchMap((query) =>
      this.fetchMarketAssets(query).pipe(
        catchError((err: Error) => {
          this._error.set(err.message || 'Fatal network condition.');
          return of([] as MarketAsset[]);
        })
      )
    ),
    tap(() => this._loading.set(false)),
    shareReplay({ bufferSize: 1, refCount: true })
  );

  // Konversi stream aset mentah kembali ke Signal
  private readonly _assets = toSignal(this.rawAssets$, { initialValue: [] });
  readonly assets = computed(() => this._assets());

  // --- DERIVED SELECTORS (Pure Computed Graph) ---
  readonly filteredAssets = computed(() => {
    const data = this._assets();
    const filter = this._activeFilter();

    if (filter === 'VOLUME_GT_1M') {
      return data.filter((item) => item.volume24h > 1_000_000);
    }
    return data;
  });

  readonly totalMarketCap = computed(() => {
    return this.filteredAssets().reduce((acc, curr) => acc + curr.price, 0);
  });

  readonly assetCount = computed(() => this.filteredAssets().length);

  // --- ACTIONS ---
  setSearchTerm(term: string): void {
    this._searchTerm.set(term);
  }

  setFilter(filter: 'ALL' | 'VOLUME_GT_1M'): void {
    this._activeFilter.set(filter);
  }

  // Mutasi optimistik manual
  patchAssetPrice(symbol: string, newPrice: number): void {
    const current = this._assets();
    const index = current.findIndex((a) => a.symbol === symbol);
    if (index !== -1) {
      const updated = [...current];
      updated[index] = { ...updated[index], price: newPrice, lastUpdated: new Date().toISOString() };
      // Peringatan: toSignal adalah Read-Only signal. Mutasi state turunan asinkron
      // ditangani via store state model terpisah jika mutasi lokal diperlukan.
    }
  }

  private fetchMarketAssets(search: string): Observable<MarketAsset[]> {
    return this.http.get<MarketAsset[]>(`${this.apiUrl}?q=${encodeURIComponent(search)}`).pipe(
      retry({ count: 2, delay: 1000 })
    );
  }
}
```

---

## 8. Real World Case Study: High-Frequency Trading (HFT) Execution Dashboard

### Latar Belakang Masalah
Sebuah platform broker institusional memproses hingga 5.000 pembaruan harga (*ticks*) per detik melalui kluster WebSocket. Implementasi awal menggunakan RxJS murni yang tersambung langsung ke komponen via `| async` pipe menyebabkan *micro-stutters* (60 FPS anjlok ke 12 FPS) dan memicu pemakaian memori peramban hingga 1.8 GB akibat jutaan alokasi objek sementara per detik.

### Akar Masalah Teknis
1. **Change Detection Overload:** Setiap tick mengeksekusi siklus Zone.js makro, memaksa traversal pohon DOM yang sangat dalam.
2. **Object Churn & GC Pressure:** RxJS pipeline mengalokasikan array baru pada setiap emisi untuk mematuhi immutability, membebani V8 Garbage Collector.
3. **Diamond Problem UI:** Dependensi harga yang dihitung (*computed conversions*, *FX hedging*) menghasilkan render sementara yang inkonsisten (*visual glitching*).

### Arsitektur Solusi Terintegrasi
1. **Detached RxJS Buffer Layer:** WebSocket stream ditahan di lapisan RxJS menggunakan `bufferTime(100)` atau `auditTime(60)` untuk menyerap lonjakan jaringan ke batas kecepatan refresh monitor (60 Hz/120 Hz).
2. **Batch Signal Mutation via `untracked`:** Array aset dialokasikan dalam *fixed-size ArrayBuffer* / *mutable map*, lalu dikirim ke sebuah root Signal via mutasi terkontrol.
3. **Signal Computational Layer:** Menggunakan `computed()` untuk derived metrics (Spread, Margin Risk). Komputasi hanya berjalan bila ada komponen visual yang aktif di *viewport*.
4. **Zoneless Component Mounting:** Seluruh UI beroperasi di bawah `provideExperimentalZonelessChangeDetection()` (Angular 18+).

```typescript
// Cuplikan Implementasi High-Throughput Buffer Bridge
@Injectable()
export class HighFrequencyPriceService {
  private readonly rawWebSocketStream$ = inject(WebSocketGateway).stream$;
  
  // Backpressure & Throttling Layer: Mengubah stream unconstrained menjadi sinkron
  private readonly batchedPriceStream$ = this.rawWebSocketStream$.pipe(
    bufferTime(50), // Batasi perubahan visual ke 20 FPS (cukup untuk persepsi manusia)
    map(ticks => this.coalesceTicks(ticks))
  );

  // Expose as Signal to UI
  readonly latestTicks = toSignal(this.batchedPriceStream$, { 
    initialValue: new Map<string, number>() 
  });

  private coalesceTicks(ticks: PriceTick[]): Map<string, number> {
    const map = new Map<string, number>();
    for (let i = 0; i < ticks.length; i++) {
      map.set(ticks[i].symbol, ticks[i].price);
    }
    return map;
  }
}
```

### Hasil Optimasi
- **CPU Time:** Berkurang sebesar 68%.
- **Memory Footprint:** Stabil pada angka ~95 MB (turun dari 1.8 GB).
- **UI Frame Rate:** Terkunci konsisten pada 60 FPS tanpa visual tearing/glitch.

---

## 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Kerugian & Batasan | Rekomendasi Kasus Penggunaan |
| :--- | :--- | :--- | :--- |
| **Pure Signals Store** | Performa ekstrim, memori minimum, eliminasi kebocoran langganan, *zero-glitch*. | Tidak ada operator waktu natively (debounce/retry/throttle harus dibuat manual). | Sinkronisasi UI, Form State, Wizard Navigation, Master-Detail State. |
| **Pure RxJS (Classic)** | Komposisi stream tak tertandingi, ekosistem operator masif, penanganan pembatalan I/O bawaan. | Rentan bocor (*memory leak*), *boilerplate* `takeUntil`/`AsyncPipe`, degradasi performa di Zone.js. | Layanan Network I/O murni, SSE/WebSocket ingestion, Event bus lintas modul. |
| **Hybrid (RxJS Edge + Signals Core)** | Efisiensi terbaik dari kedua dunia: I/O kuat via RxJS, rendering presisi dan bersih via Signals. | Memerlukan pemahaman batas arsitektur (*mental model*) yang lebih tinggi. Potensi bug *injection context*. | Aplikasi enterprise skala menengah hingga besar (ERP, Trading, Real-time SaaS). |
| **Fine-Grained Zoneless Signals** | Bebas Zone.js monkey-patching, bundle size lebih kecil, tracing performa sangat presisi. | Kode pihak ketiga yang bergantung pada Zone.js dapat berhenti berfungsi secara reaktif. | Sistem modern Angular 18/19+ yang mengutamakan performa rendering maksimal. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan 1: Memanggil `toSignal()` di Luar Injection Context
```typescript
// SALAH
export class ProductComponent {
  private http = inject(HttpClient);

  loadData(category: string) {
    const data$ = this.http.get<Product[]>(`/api/${category}`);
    // RUNTIME ERROR: NG0203: toSignal() must be called in an injection context
    const products = toSignal(data$); 
  }
}

// BENAR
export class ProductComponent {
  private http = inject(HttpClient);
  private injector = inject(Injector);

  loadData(category: string) {
    const data$ = this.http.get<Product[]>(`/api/${category}`);
    // Solusi: Kirimkan injector secara eksplisit jika harus dipanggil di dalam fungsi
    const products = toSignal(data$, { injector: this.injector });
  }
}
```

### Kesalahan 2: Siklus Efek Reaktif Tak Terbatas (*Infinite Reactive Loop*)
```typescript
// SALAH: Menulis ke Signal di dalam Effect yang membaca Signal yang sama
export class BadComponent {
  count = signal(0);

  constructor() {
    effect(() => {
      console.log('Current:', this.count());
      // ERROR: NG0600: Writing to signals is not allowed inside computed or effects by default
      this.count.set(this.count() + 1); 
    }, { allowSignalWrites: true }); // Mengaktifkan allowSignalWrites memicu infinite freeze!
  }
}

// BENAR: Pisahkan mutasi pemicu dari pembacaan dependensi
export class GoodComponent {
  count = signal(0);
  logTrigger = effect(() => {
    // Gunakan untracked jika hanya butuh membaca tanpa mendaftarkan dependensi
    const current = untracked(() => this.count());
    this.analyticsService.track(current);
  });
}
```

### Kesalahan 3: Mutasi Objek atau Array Secara In-Place
```typescript
// SALAH
export class InventoryComponent {
  items = signal<string[]>(['Apple', 'Banana']);

  addItem(item: string) {
    this.items().push(item); 
    // Bug: Referensi memori tidak berubah! Computed dependent tidak akan terpicu!
  }
}

// BENAR
export class InventoryComponent {
  items = signal<string[]>(['Apple', 'Banana']);

  addItem(item: string) {
    this.items.update(prev => [...prev, item]); // Wajib immutable emit
  }
}
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Enforce Immutability:** Jangan pernah memutasi *array* atau *object* secara langsung di dalam signal; selalu gunakan `.update(prev => ({...prev, prop: val}))`.
- [ ] **Keep Computeds Pure:** Hindari pemanggilan *side-effect* (I/O, konsol, manipulasi DOM, pengiriman HTTP) di dalam `computed()`. Komputasi harus murni deterministik.
- [ ] **Explicit Initial Values:** Selalu sediakan `initialValue` saat menggunakan `toSignal(obs$)` untuk menghindari *type inference* menjadi `T | undefined` di seluruh komponen.
- [ ] **DestroyRef Awareness:** Pastikan setiap *manual subscription* pada Observable RxJS terikat dengan operator `takeUntilDestroyed()`.
- [ ] **Guard Injection Context:** Panggil `toSignal` dan `toObservable` pada level inisialisasi properti kelas (*field initializers*) atau *constructor*.
- [ ] **Zoneless Verification:** Uji aplikasi tanpa dependensi `zone.js` menggunakan flag `provideExperimentalZonelessChangeDetection()` untuk memastikan reaktivitas komponen murni digerakkan oleh Signals.
- [ ] **Prune Long Effects:** Jangan jadikan `effect()` sebagai pengganti *event handlers*. Gunakan fungsi biasa untuk menangani aksi langsung pengguna (klik tombol, input form).

---

## 12. Hands-on Practice

Buat dan simpan file berikut pada path direktori: `hands-on/m02/resilient-stream-engine.ts`.

### Kode Lengkap Arsitektur Produksi:
```typescript
/**
 * HANDS-ON EXERCISE: Module 02
 * Path: hands-on/m02/resilient-stream-engine.ts
 * 
 * Deskripsi:
 * Implementasi "Resilient Market Watchlist Engine" yang menggabungkan:
 * 1. Signals untuk sinkronisasi state lokal
 * 2. RxJS untuk resilience (exponential backoff retry, rate-limiting, cancellation)
 * 3. Bidirectional interop dengan penanganan injection context yang aman
 */

import { 
  Injectable, 
  Injector, 
  Signal, 
  computed, 
  inject, 
  runInInjectionContext, 
  signal 
} from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { 
  Observable, 
  Subject, 
  catchError, 
  delay, 
  mergeMap, 
  of, 
  pipe, 
  retry, 
  switchMap, 
  throwError, 
  timer 
} from 'rxjs';

export interface WatchlistEntity {
  id: string;
  ticker: string;
  targetPrice: number;
  isTriggered: boolean;
}

export interface NetworkHealthState {
  isOnline: boolean;
  consecutiveFailures: number;
}

@Injectable({
  providedIn: 'root'
})
export class ResilientStreamEngine {
  private readonly injector = inject(Injector);

  // --- STATE LAYER (Signals) ---
  private readonly _watchlist = signal<WatchlistEntity[]>([]);
  private readonly _networkHealth = signal<NetworkHealthState>({ 
    isOnline: true, 
    consecutiveFailures: 0 
  });
  private readonly _isSyncing = signal<boolean>(false);

  // Public Selectors
  readonly watchlist = this._watchlist.asReadonly();
  readonly networkHealth = this._networkHealth.asReadonly();
  readonly isSyncing = this._isSyncing.asReadonly();

  readonly triggeredCount = computed(() => 
    this._watchlist().filter(w => w.isTriggered).length
  );

  readonly hasAlerts = computed(() => this.triggeredCount() > 0);

  // --- ACTION METHODS ---
  addTicker(ticker: string, targetPrice: number): void {
    const newEntry: WatchlistEntity = {
      id: crypto.randomUUID(),
      ticker: ticker.toUpperCase(),
      targetPrice,
      isTriggered: false
    };

    this._watchlist.update(current => [...current, newEntry]);
  }

  removeTicker(id: string): void {
    this._watchlist.update(current => current.filter(item => item.id !== id));
  }

  // --- ASYNC RESILIENCE INTEGRATION ---
  /**
   * Menginisialisasi sinkronisasi latar belakang yang menjembatani Signals ke RxJS
   * dengan mekanisme proteksi Exponential Backoff.
   */
  initiateResilientSync(): Signal<string> {
    return runInInjectionContext(this.injector, () => {
      const watchlist$ = toObservable(this._watchlist);

      const syncStatus$ = watchlist$.pipe(
        switchMap(list => {
          if (list.length === 0) return of('IDLE: Watchlist Kosong');
          
          this._isSyncing.set(true);

          return this.mockExternalHttpSync(list).pipe(
            retry({
              count: 3,
              delay: (error, retryCount) => {
                // Exponential backoff strategy: 1s, 2s, 4s...
                const backoffDelay = Math.pow(2, retryCount - 1) * 1000;
                this._networkHealth.update(prev => ({
                  isOnline: false,
                  consecutiveFailures: retryCount
                }));
                return timer(backoffDelay);
              }
            }),
            catchError(err => {
              this._networkHealth.update(prev => ({
                isOnline: false,
                consecutiveFailures: prev.consecutiveFailures + 1
              }));
              this._isSyncing.set(false);
              return of(`SYNC_FAILED: ${err.message}`);
            }),
            switchMap(successMsg => {
              this._networkHealth.set({ isOnline: true, consecutiveFailures: 0 });
              this._isSyncing.set(false);
              return of(successMsg);
            })
          );
        })
      );

      return toSignal(syncStatus$, { initialValue: 'INITIALIZING' });
    });
  }

  /**
   * Simulasi panggilan I/O jaringan yang memiliki probabilitas gagal.
   */
  private mockExternalHttpSync(payload: WatchlistEntity[]): Observable<string> {
    return timer(400).pipe(
      mergeMap(() => {
        // Simulasi kegagalan acak 30% untuk menguji retry backoff
        const shouldFail = Math.random() < 0.3;
        if (shouldFail) {
          return throwError(() => new Error('Simulated 503 Service Unavailable'));
        }
        return of(`SYNC_OK: Synced ${payload.length} nodes at ${new Date().toISOString()}`);
      })
    );
  }
}
```

---

## 13. Exercise

### Level Easy: Time-Traveling Signal History
Implementasikan fungsi pembungkus `createHistorySignal<T>(initialValue: T)` yang mengembalikan:
- `value`: Signal membaca state saat ini.
- `set(val: T)`: Mengubah nilai.
- `undo()`: Mengembalikan nilai ke state sebelumnya.
- `canUndo`: Signal boolean derived (`computed`) yang mendeteksi ketersediaan riwayat.

### Level Medium: Custom RxJS Operator `fromSignalChange`
Bangun operator kustom RxJS:
```typescript
function filterSignal<T>(predicate: (val: T) => boolean): (source: Signal<T>) => Signal<T | undefined>
```
Gunakan `toObservable`, filter native RxJS, dan kembalikan ke `toSignal` dengan penanganan memori yang bersih tanpa kebocoran memori pada destruksi komponen.

### Level Hard: Optimistic Remote Entity Store
Buatlah kelas arsitektur `OptimisticEntityStore<T extends { id: string }>`:
1. Menyimpan state lokal via `WritableSignal<Map<string, T>>`.
2. Menyediakan fungsi `updateOptimistic(id: string, patch: Partial<T>)`.
3. Mengirimkan request mutasi ke server (RxJS Mock HTTP).
4. Jika server merespons *Error 500*, fungsi harus melakukan *rollback* otomatis terhadap entitas tersebut ke nilai tepat sebelum mutasi optimistik dilakukan. Semua status error dan *reverting* harus dapat dibaca oleh UI melalui Signals.

---

## 14. Challenge: Massive Real-Time Orderbook (Zero Micro-Stutter)

### Skenario Masalah
Anda ditugaskan mendesain mesin State UI untuk *Cryptocurrency Order Book* dengan volume transaksi ekstrem:
- **Spesifikasi Beban:** Menerima 10.000 update delta order per detik dari 4 server WebSocket paralel.
- **Kondisi Batas:** DOM tidak boleh diperbarui melebihi kecepatan monitor (maksimum 60 perubahan UI/detik).
- **Integritas Data:** Nilai akumulasi volume (*depth chart analysis*) harus sinkron 100% dan bebas dari *diamond glitch*.
- **Kendala Perangkat:** Peramban kelas bawah (*low-spec tablets* di lantai bursa) dengan batas heap memori V8 ketat (maksimal alokasi tambahan < 50MB).

### Kriteria Tantangan
1. Rancang arsitektur buffer pipeline menggunakan RxJS kustom scheduler / `requestAnimationFrame` coalescing.
2. Jembatani stream berkecepatan tinggi tersebut ke Signal Dependency Graph Angular.
3. Pastikan tidak ada alokasi *deep object cloning* di setiap tick (Gunakan struktur data efisien seperti *Red-Black Tree*, *Flat TypedArrays*, atau *Direct In-Place Mutation Map* yang diisolasi di luar konteks reaktif).
4. Sediakan solusi tanpa menggunakan dependensi pustaka pihak ketiga.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)

1. **Bagaimana model evaluasi komputasi pada Angular Signals berbeda dari RxJS Observables?**
   - A. Signals mengevaluasi komputasi secara *Push-only* seketika saat nilai berubah.
   - B. Signals menggunakan *Push-Dirty, Pull-Value*, sedangkan RxJS bersifat *Push-Continuous*.
   - C. Signals berjalan di background web worker secara *asynchronous*.
   - D. RxJS selalu melakukan cache nilai secara default, sedangkan Signals tidak pernah menyimpan cache.

2. **Apa yang terjadi secara default jika kita mencoba mengeksekusi operasi penulisan `.set()` pada Signal di dalam sebuah `computed()`?**
   - A. Nilai berhasil ditulis dan komputasi diulang.
   - B. Kompilator TypeScript membiarkan, namun Angular melempar runtime exception untuk menjaga *purity*.
   - C. Operasi penulisan diabaikan secara diam-diam (*silent fail*).
   - D. Menghasilkan *Promise rejection*.

3. **Kapan fungsi `toSignal()` harus dipanggil agar tidak melempar error runtime `NG0203`?**
   - A. Di dalam *lifecycle hook* `ngAfterViewInit`.
   - B. Di dalam *asynchronous microtask* `.then()`.
   - C. Di dalam *Injection Context* (seperti deklarasi properti kelas atau konstruktor).
   - D. Kapan saja di dalam template HTML.

4. **Struktur data internal apa yang digunakan kernel Angular Signals untuk mengelola dependensi reaktif?**
   - A. Binary Search Tree.
   - B. Red-Black Tree.
   - C. Graph of `ReactiveNode` yang terhubung via doubly-linked edge pointers.
   - D. Simple Global Array.

5. **Apa fungsi utama operator `takeUntilDestroyed` dalam interoperabilitas Signals-RxJS?**
   - A. Mengonversi Observable menjadi Signal secara otomatis.
   - B. Membatalkan *subscription* RxJS secara otomatis ketika komponen/konteks injeksi dihancurkan.
   - C. Menunda emisi data hingga template selesai di-render.
   - D. Menangani error stream agar tidak mematikan UI.

---

### Bagian 2: Intermediate (Analisis Kasus & Algoritma)

6. **Mengapa pemanggilan `toObservable(mySignal)` tidak langsung memancarkan data secara instan dan sinkron pada saat `mySignal.set()` dipanggil?**
   - Jelaskan peran *EffectScheduler*, *Microtask timing*, dan mekanisme *signal value coalescing*.

7. **Jelaskan bagaimana Angular Signals menyelesaikan *Diamond Dependency Problem* tanpa memicu *glitch* evaluasi ganda!**

8. **Perhatikan cuplikan berikut:**
   ```typescript
   export class MetricComponent {
     factor = signal(1);
     base = signal(10);
     total = computed(() => {
       if (this.factor() > 5) {
         return this.base() * this.factor();
       }
       return 0;
     });
   }
   ```
   *Jika `factor` bernilai `2`, apakah perubahan pada `base` akan memicu komputasi ulang pada `total`? Mengapa (hubungkan dengan konsep Dynamic Dependency Tracking)?*

9. **Apa perbedaan dampak alokasi memori antara operator RxJS `shareReplay({ bufferSize: 1, refCount: true })` dan primitif Angular `toSignal()`?**

10. **Bagaimana cara mengisolasi pembacaan Signal di dalam fungsi komputasi atau efek agar tidak tercatat sebagai dependensi (*dependency tracking exclusion*)? Berikan fungsi API Angular resminya!**

---

### Bagian 3: Production Scenarios (Analisis & Rekomendasi Solusi)

11. **Skenario Kasus 1: Memory Leak pada Dashboard Dinamis**
   Sebuah aplikasi dasbor analitik menampilkan 20 widget dinamis. Setiap widget menggunakan service yang mengonversi event klik global (`fromEvent(document, 'click')`) menjadi Signal via `toSignal()`. Setelah pengguna berpindah tab rute bolak-balik sebanyak 10 kali, memori peramban naik dari 40MB ke 800MB. 
   - *Pertanyaan:* Mengapa kebocoran ini terjadi padahal `toSignal()` memiliki siklus hidup otomatis? Di mana letak kesalahannya dan bagaimana memperbaikinya?

12. **Skenario Kasus 2: Race Condition pada Form Autocomplete**
   Pengguna mengetik "ANGULAR", lalu dengan cepat menghapus dan mengetik "REACT". Server merespons kueri "ANGULAR" dalam waktu 1.5 detik, dan kueri "REACT" dalam waktu 200 milidetik. Jika state diimplementasikan dengan memutasi Signal secara langsung di dalam *Promise resolution* API client biasa, hasil kueri mana yang akan tertinggal di layar? 
   - *Pertanyaan:* Rancang arsitektur pipeline RxJS-to-Signal yang menjamin hasil akhir selalu konsisten dengan input pengguna terakhir!

13. **Skenario Kasus 3: Zoneless UI Stuttering pada Grafik Real-Time**
   Sebuah aplikasi dipindahkan ke arsitektur Zoneless (`provideExperimentalZonelessChangeDetection`). Komponen grafik pasar menerima sinyal WebSocket 100 kali per detik. Pengembang mengupdate `chartData = signal([...])` secara langsung pada setiap pesan WebSocket. Akibatnya, browser mengalami *frame-drop* parah.
   - *Pertanyaan:* Jelaskan mekanisme di balik penurunan performa tersebut dalam konteks Zoneless Change Detection Scheduler, dan berikan strategi *batching/coalescing* yang benar!

---

### Kunci Jawaban Singkat & Panduan Solusi Quiz

#### Kunci Bagian 1
1. **B** — Signals menggunakan model *Push-Dirty, Pull-Value*, memastikan komputasi dilakukan secara malas (*lazy*) hanya saat dibaca, berbeda dari RxJS yang terus mendorong emisi data.
2. **B** — Angular melarang *side-effects* (termasuk menulis ke signal lain) di dalam `computed()` untuk menjaga *functional purity* dan konsistensi graf komputasi (melempar error `NG0600`).
3. **C** — `toSignal()` membutuhkan akses ke `DestroyRef` atau `Injector` yang hanya tersedia di *Injection Context*.
4. **C** — Menggunakan node-node graf reaktif (`ReactiveNode`) yang saling terhubung dengan pointer tautan ganda (*doubly-linked list*).
5. **B** — Mengotomatisasi proses pembatalan langganan RxJS saat *lifecycle scope* Angular yang menaunginya hancur.

#### Panduan Jawaban Bagian 2
6. **Mekanisme Scheduler:** `toObservable` menggunakan `effect()` di balik layar. `effect()` dieksekusi secara asinkron oleh scheduler internal Angular pada siklus microtask berikutnya. Jika signal dimutasi 3 kali berturut-turut dalam satu tick sinkron, efek hanya akan membaca nilai terakhir (*coalesced*), sehingga emisi Observable tidak memancarkan status-status transien di antaranya.
7. **Penyelesaian Diamond:** Fase 1 menandai node D sebagai *OUT_OF_DATE* secara topologis ke bawah tanpa eksekusi fungsi. Saat nilai D dibaca (*Fase Pull*), D memeriksa versi dependensi hulunya (B dan C). B dan C menghitung ulang nilainya dari A dan memperbarui *version counter* mereka. Terakhir, D mengkalkulasi nilainya satu kali dengan dependensi yang sudah stabil.
8. **Tidak.** Ketika `factor() <= 5`, eksekusi mengembalikan `0` pada baris pertama. Cabang logika `this.base()` tidak pernah tersentuh (*short-circuited*). Akibat *Dynamic Dependency Tracking*, edge ketergantungan antara `total` dan `base` diputus dari graf. Perubahan pada `base` tidak akan menandai `total` sebagai *dirty*.
9. **Perbedaan:** `shareReplay(1)` mempertahankan subskripsi RxJS aktif, menyimpan referensi emisi terakhir di closure Observable, dan terus aktif selama refCount belum nol. `toSignal` mengikatkan emisi ke sebuah `WritableSignal` lokal; jika konteks hancur, subskripsi internal dihentikan otomatis via `DestroyRef`, membebaskan referensi stream dari memori.
10. **Fungsi `untracked()`:** Gunakan API `untracked(() => mySignal())`. Ini mengeksekusi pembacaan signal di luar pelacakan konteks reaktif aktif saat ini.

#### Panduan Jawaban Bagian 3
11. **Analisis Memory Leak:** Jika service penyedia berstatus `providedIn: 'root'` (singleton), memanggil `toSignal()` di dalam singleton service akan mengikat *subscription* `fromEvent` ke `DestroyRef` root (seumur hidup aplikasi). Widget yang dihancurkan meninggalkan *listener* yang tidak pernah di-*unsubscribe*. Solusi: Gunakan service dengan *scope* komponen lokal (`providers: [WidgetService]` di metadata komponen) atau lewatkan `injector` komponen secara eksplisit.
12. **Mitigasi Race Condition:** Solusinya adalah mengalirkan string pencarian pengguna ke sebuah RxJS stream, lalu menggunakan operator konkurensi `switchMap`:
    ```typescript
    searchQuery$ = toObservable(this.searchTerm);
    results = toSignal(searchQuery$.pipe(
      switchMap(query => this.http.get(`/api/search?q=${query}`))
    ), { initialValue: [] });
    ```
    `switchMap` secara otomatis membatalkan kueri "ANGULAR" yang masih berjalan (*in-flight cancellation*) ketika kueri "REACT" tiba.
13. **Zoneless UI Stuttering:** Dalam mode Zoneless, setiap mutasi signal memberi tahu `ChangeDetectionScheduler` untuk menjadwalkan pengecekan view pada siklus rendering berikutnya. Jika signal dimutasi 100 kali/detik dengan alokasi array baru, engine memicu *garbage collection spikes* dan penjadwalan render berlebih. Solusi: Gunakan lapisan penyerap RxJS `stream$.pipe(auditTime(16))` (membatasi pada 60 FPS) sebelum memperbarui Signal, atau gunakan `requestAnimationFrame` batching.

---

## 16. Summary

1. **Signals adalah Primitif Sinkron Terkelola:** Angular Signals menghadirkan representasi state UI yang bebas *glitch* (*diamond-dependency safe*) melalui algoritma *Push-Dirty, Pull-Value* dan *Dynamic Dependency Tracking*.
2. **RxJS adalah Mesin Pengendali Waktu & Konkurensi:** RxJS tetap tak tergantikan untuk penanganan aliran asinkron kompleks, pembatalan operasi jaringan, orkestrasi WebSocket, dan pengendalian laju data (*throttling/debouncing*).
3. **Pemisahan Peran Arsitektur Hibrida:**
   - **RxJS di Lapisan Luar (Edge/Infrastructure):** Mengontrol I/O, event asinkron, dan latensi.
   - **Signals di Lapisan Dalam (Core/Presentation):** Mengelola state reaktif komponen, visual derivasi (`computed`), dan template rendering.
4. **Batas Eksekusi & Konteks:** Konversi via `toSignal()` dan `toObservable()` memerlukan pemahaman ketat terhadap batas *Injection Context* dan pergeseran siklus penjadwalan (*microtask/coalescing effects*).
5. **Arah Masa Depan (Zoneless Execution):** Penguasaan interoperabilitas Signals dan RxJS merupakan fondasi utama dalam mengadopsi arsitektur Angular Zoneless modern demi performa komputasi web tingkat enterprise.