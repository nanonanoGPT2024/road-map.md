# BAB 07: Quiz, Challenge, & Knowledge Check
**State Management Terdesentralisasi & Skala Besar**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Monolithic Global Store vs Decentralized Scoped Store**  
   Dalam arsitektur enterprise berskala besar, mengapa pola *Single Monolithic Global Store Tree* (seperti konfigurasi root NgRx klasik tanpa boundary) kerap berubah menjadi anti-pattern (*God Object*)? Jelaskan skenario di mana desentralisasi state menggunakan Scoped Stores (misalnya `@ngrx/component-store` atau `@ngrx/signals` yang di-inject pada level feature/komponen) jauh lebih unggul dalam aspek *garbage collection*, pemisahan kepemilikan (*domain boundary*), dan pencegahan *memory leak*.

2. **Normalisasi State dan Dampaknya pada Memoization**  
   Mengapa *deeply nested state structure* merupakan musuh utama dalam performa state management? Jelaskan mekanisme normalisasi state (menggunakan pola entitas: `ids: string[]` dan `entities: Record<string, T>`) dan bagaimana struktur data datar (*flat*) ini mengoptimalkan komputasi murni (*pure computation*) serta efisiensi *cache invalidation* pada memoized selectors.

3. **Immutability vs Structural Sharing di JavaScript Engine (V8)**  
   Prinsip dasar immutability mewajibkan kita tidak memutasikan state secara in-place. Jelaskan secara mekanis bagaimana *structural sharing* memitigasi overhead alokasi memori di V8 engine ketika kita memperbarui 1 entitas di dalam koleksi 10.000 data. Apa implikasi teknis jika seorang engineer salah menerapkan kloning (misal: *deep clone* via `structuredClone` atau `JSON.parse(JSON.stringify())`) di dalam reducer/state updater?

4. **Lifecycle Coupling: Root-Provided vs Component-Provided State**  
   Bandingkan siklus hidup (*lifecycle*) state yang didaftarkan melalui `providedIn: 'root'` dengan state yang didaftarkan pada metadata komponen (`providers: [MyLocalStore]`). Bagaimana Angular Dependency Injection (DI) hierarki mengatur instansiasi, re-use, hingga proses eksekusi `ngOnDestroy` pada store terdesentralisasi ketika sebuah routed view di-destroy?

5. **Reactivity Primitive: RxJS Stream vs Angular Signals pada State Skala Besar**  
   Analisis perbedaan mendasar antara *Push-only reactive streams* (RxJS `Observable`/`BehaviorSubject`) dengan *Pull-Push reactive primitives* (`Signal`/`computed`) dalam konteks decentralized state management. Mengapa Signals secara inheren mengeliminasi kebutuhan manual *glitch-free dependency tracking* dan operator seperti `distinctUntilChanged`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Zombie Child Problem & Late Unsubscription Invalidation**  
   Jelaskan bagaimana fenomena *Zombie Child* terjadi pada arsitektur RxJS Selector lama ketika parent component menghancurkan child component sebelum child sempat unsubscribe dari stream state. Bagaimana modern Signal-based state (`@ngrx/signals` atau native `signal()`) secara internal mendesain dependency graph-nya sehingga sepenuhnya kebal (*immune*) terhadap *Zombie Child Problem*?

2. **Dynamic State Slices Injection & Route Splitting Collision**  
   Saat mengimplementasikan *feature slicing* dinamis via lazy loading (`provideState` atau dynamic store injection), apa yang terjadi di internal registry store jika dua feature module yang di-load secara paralel mendaftarkan slice name yang identik? Bagaimana arsitektur state harus dirancang untuk mendeteksi atau mengisolasi collision ini di skala multi-team?

3. **Selector Factory Invalidation Trap**  
   Perhatikan pola selector berikut:  
   ```typescript
   export const selectItemById = (id: string) => 
     createSelector(selectEntities, (entities) => entities[id]);
   ```  
   Jika selector factory di atas dipanggil langsung di dalam fungsi komponen atau loop template (`store.select(selectItemById(item.id))`), jelaskan mengapa performa memoization akan hancur total (*cache thrashing*). Bagaimana cara mengatasi problem ini menggunakan *dynamic/parameterized state slice patterns* atau Signal computed maps?

4. **Atomic Optimistic Updates dengan Rollback Strategy**  
   Dalam skenario optimistic update pada localized store: entitas di-update seketika di state lokal sebelum HTTP response kembali. Jika network mengembalikan `500 Internal Server Error` atau timeout, bagaimana mekanisme state machine internal store memulihkan (*rollback*) data ke *previous known-good state* tanpa menimpa (*overwriting*) mutasi lain yang terjadi secara concurrent di entitas yang sama selama proses HTTP pending?

5. **Cross-Micro-Frontend State Synchronization Leakage**  
   Ketika aplikasi Angular dipecah menjadi beberapa Micro-Frontends (MFE) menggunakan Module Federation, mengapa membagikan satu instansiasi State Store secara global via `shared` Webpack/Rspack scope sering kali berujung pada *runtime fatal errors* (misalnya: dual RxJS injection, mismatched injection tokens, atau zone mismatch)? Pola desentralisasi apa yang paling robust untuk sinkronisasi state antar-MFE tanpa menimbulkan tight-coupling?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck FinTech Real-Time Dashboard (High-Frequency State Thrashing)
Sebuah dashboard trading enterprise menerima tick data valuta asing melalui WebSocket dengan frekuensi ~500 payload/detik. Arsitektur saat ini menggunakan Global NgRx Store di mana setiap message langsung di-*dispatch* sebagai Action: `[FX Socket] Tick Received`.  
*Gejala:* Frame rate anjlok ke <15 FPS, UI mengalami freeze reguler setiap 2 detik akibat Major Garbage Collection, dan browser memory consumption merangkak naik hingga crash (Out of Memory).  
* **Pertanyaan Diagnostik:**
  1. Identifikasi 3 bottleneck struktural utama pada pipeline data di atas (hubungkan dengan Action processing, Reducer execution, dan Angular Change Detection).
  2. Rancang arsitektur refactoring menggunakan *decentralized localized state* (misal: SignalStore atau ComponentStore) yang memanfaatkan teknik *buffering/batching*, eksekusi *outside Angular Zone* (atau Zoneless), dan Signal updates tanpa membanjiri Global Action Stream!

### Skenario B: Race Condition pada Concurrency-Heavy Multi-Step Enterprise Form
Pada aplikasi Enterprise Resource Planning (ERP), form approval procurement yang kompleks dibagi menjadi 3 tab independen yang memuat decentralized sub-stores. User dapat mengedit data finansial di Tab A dan approval limits di Tab B secara bersamaan. Saat user menekan tombol global "Submit Final", kedua sub-store memicu request autosave asynchronous ke backend, disusul oleh request aggregasi final.  
*Insiden:* Sering kali data limit Tab B menimpa perhitungan finansial Tab A di database, dan UI menampilkan state tidak konsisten (*split-brain state*).  
* **Pertanyaan Diagnostik:**
  1. Mengapa desentralisasi state tanpa orkestrator transaksi memicu *write race conditions* ini?
  2. Rancang arsitektur koordinasi (*Saga*, *State Coordinator Service*, atau *Two-Phase Commit state pattern*) pada Angular level yang memastikan persistensi data lokal terisolasi bersifat transaksional dan atomic sebelum final state disahkan.

### Skenario C: Migrasi Monolith State NgRx ke Modular SignalStore
Sebuah platform SaaS enterprise memiliki monolitik NgRx state yang berumur 5 tahun dengan 400+ actions, 50 reducers, dan efek yang saling bergantung (*action-churn*). Tim engineering memutuskan untuk menghentikan pola global monolith dan bermigrasi ke arsitektur terdesentralisasi menggunakan `@ngrx/signals` (NgRx SignalStore) secara bertahap (*strangler fig pattern*).  
* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda merancang boundary lapisan interoperabilitas (*interop layer*) agar fitur baru yang dibangun dengan SignalStore tetap dapat membaca data dari Legacy Global NgRx Store secara reaktif tanpa menimbulkan siklus dependensi sirkular?
  2. Apa trade-off arsitektural antara menggunakan SignalStore Custom Features (`signalStoreFeature`) vs Native Class-based Signals Services dalam standarisasi enterprise code di puluhan tim feature?

---

## 4. Chapter Challenge

### Tantangan Praktis: "Architecting a Resilient Distributed Order-Execution Engine"

#### Problem Statement
Anda ditugaskan merancang arsitektur state untuk modul "Execution Desk" pada aplikasi enterprise logistik. Modul ini menangani ratusan armada pengiriman yang statusnya terus berubah. Sistem ini memerlukan isolasi state per armada, mendukung pembaruan optimis dengan kapabilitas *undo/rollback*, dan harus berjalan pada mode **Zoneless** (`provideExperimentalZonelessChangeDetection()`). Penggunaan Global Monolithic Store dilarang keras karena isu isolasi memori antar armada.

#### Requirements
1. **Custom SignalStore Feature Architecture**:  
   Buat sebuah *reusable custom store feature* `@ngrx/signals` bernama `withOptimisticEntity<T>` yang menyediakan state, signals, dan methods:
   - State: `entities: Signal<T[]>`, `pendingOperations: Signal<Map<string, OptimisticOperation<T>>>`, `callState: Signal<'idle' | 'loading' | 'error'>`.
   - Methods:
     - `executeOptimistic(id: string, update: Partial<T>, remoteCall$: Observable<T>): Promise<void>`
     - Meng-update state secara instan, mencatat history mutasi.
     - Jika `remoteCall$` sukses, bersihkan status pending.
     - Jika `remoteCall$` gagal/error, batalkan mutasi (*rollback*) secara otomatis ke nilai sebelumnya dan update error message ke state.
2. **Decentralized Provisioning**:  
   State engine harus di-scope pada level route-component tree sehingga ketika user menutup panel armada tertentu, seluruh alokasi memori untuk store armada tersebut wajib di-garbage collect secara otomatis oleh runtime engine tanpa menyisakan active RxJS stream.
3. **Concurrency-Safe Normalized Structure**:  
   State internal wajib dinormalisasi (menggunakan ID sebagai key) guna menghindari O(N) array search mutation saat order updates berfrekuensi tinggi masuk.

#### Constraints
- **Strict Typing:** Dilarang menggunakan `any` atau `as unknown as Type` yang merusak type safety.
- **Zoneless Safe:** Tidak boleh mengandalkan `ChangeDetectorRef.markForCheck()` atau `NgZone`. Seluruh reaktivitas wajib murni berbasis Angular Signals.
- **Zero Leak:** Tidak boleh ada subscription dangling jika `remoteCall$` masih berlangsung saat komponen di-unmount. Gunakan cancellation mechanics bawaan Angular (seperti `takeUntilDestroyed`).

#### Expected Output
1. Implementasi TypeScript lengkap untuk generic `withOptimisticEntity` custom feature.
2. Komponen demonstrasi (`FleetDeskComponent`) yang men-consume store tersebut, memicu *optimistic updates*, dan menangani skenario HTTP error rollback secara terisolasi.
3. Unit test logic (menggunakan Vitest / Jasmine) yang membuktikan bahwa ketika mock network request melempar error, state entitas kembali persis ke snapshot sebelum mutasi dijalankan.

---

## 5. Knowledge Check & Checklist

Verifikasi kesiapan penguasaan teknis Anda sebelum melangkah ke bab arsitektur berikutnya.

### Saya harus memahami:
- [ ] Batasan matematis dan performa antara `O(1)` normalized lookup vs `O(N)` nested array searching di state tree.
- [ ] Perbedaan garbage collection lifecycle antara Singleton Services (`providedIn: 'root'`) vs Component-level providers.
- [ ] Konsep *glitch-free reactivity* pada Signal dependency graph dan perbedaannya dengan RxJS push-based diamond problem.
- [ ] Dampak memory footprint dari *structural sharing* vs mutasi langsung vs *deep defensive copy*.
- [ ] Pola desentralisasi state: Feature Store, ComponentStore, SignalStore, dan Local Ephemeral State.
- [ ] Masalah arsitektural *Action Churning* (efek yang men-dispatch action yang men-dispatch action lain) pada enterprise scale.

### Saya tidak perlu menghafal:
- [ ] Boilerplate sintaksis library pihak ketiga yang terus berubah (cukup pahami prinsip kerja reducers, selectors, dynamic extensions).
- [ ] Konfigurasi internal build tools (Webpack/Vite federation plugin options) di luar boundary kontrak interface state.
- [ ] Operator-operator eksotik RxJS yang jarang digunakan dalam state lifecycle (cukup kuasai `switchMap`, `exhaustMap`, `concatMap`, `mergeMap`, `takeUntilDestroyed`).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis dan menghentikan *memory leak* akibat active subscription pada state store yang terlambat di-destroy.
- [ ] Mengimplementasikan *Optimistic UI Updates* yang dilengkapi mekanisme rollback otomatis saat request asynchronous gagal.
- [ ] Memisahkan state domain enterprise yang masif menjadi *decentralized scoped slices* menggunakan `@ngrx/signals` atau `@ngrx/component-store`.
- [ ] Melakukan profiling alokasi heap memory dan frame-rate performance menggunakan Chrome DevTools Performance & Memory Profiler pada state berkecepatan tinggi.
- [ ] Membangun Custom SignalStore Features (`signalStoreFeature`) yang reusable, type-safe, dan extensible untuk kebutuhan arsitektur internal perusahaan.