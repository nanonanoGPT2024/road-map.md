# BAB 04: Quiz, Challenge, & Knowledge Check
**Bab 04: Client-Side State Management, Reactivity Engines, & Scalable Data Flow Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Taksonomi State pada Frontend Modern**  
   Jelaskan perbedaan struktural, siklus hidup (*lifecycle*), dan strategi kepemilikan (*ownership*) antara **Server State** (e.g., query cache), **Client UI State** (e.g., modal visibility, form draft), **URL/Location State** (e.g., query params, pagination), dan **Persistent State** (e.g., IndexedDB, LocalStorage). Mengapa memaksakan Server State masuk ke dalam Client Global Store tunggal (seperti monolitik Redux tree) dikategorikan sebagai *anti-pattern* pada skala enterprise?

2. **Pull-Based vs Push-Based Reactivity Systems**  
   Bandingkan model reaktivitas *Pull-based* (seperti Virtual DOM dirty checking / reconciliation cycle milik React) dengan model *Push-based / Fine-grained Reactive* (seperti Signals pada Solid.js/Preact atau Svelte 5 Runes). Analisis dari sudut pandang kompleksitas komputasi $O(N)$ vs $O(1)$ dalam mendeteksi dan memperbarui node DOM yang terisolasi saat sebuah nilai primitif berubah.

3. **Immutability vs Transparent Mutability via Proxy**  
   Jelaskan implikasi teknis terhadap alokasi memori, pembersihan *Garbage Collection* (GC), dan kecepatan *change detection* antara pendekatan *Immutable State Updates* (e.g., structural sharing via `Object.freeze` atau library Immer) dibandingkan dengan pendekatan *Transparent Mutability* berbasis JavaScript `Proxy` (e.g., Vue 3 Reactivity, MobX, Valtio). Kapan overhead alokasi objek baru pada immutability melampaui overhead abstraksi traps pada `Proxy`?

4. **Prinsip Deterministik pada Flux/Redux Pattern**  
   Pola Flux menetapkan aturan: *Single Source of Truth, State is Read-Only, dan Changes are Made with Pure Functions*. Jelaskan secara mendalam mengapa fungsi *reducer* wajib bersifat matematis murni (*pure function* tanpa side-effect). Apa konsekuensi fatal pada fitur *Time-Travel Debugging*, *State Rehydration* SSR, dan integritas *concurrency* jika sebuah reducer memanggil API eksternal atau memodifikasi objek di luar cakupannya?

5. **Derived State dan Bahaya Denormalisasi State**  
   Definisikan apa itu *Derived/Computed State*. Mengapa menyimpan *derived state* secara redundan di dalam state tree primer (misal: menyimpan `items`, `filter`, dan `filteredItems` sekaligus) merupakan sumber *bugs* desinkronisasi yang fatal? Bagaimana mekanisme *memoization* (seperti selector pattern pada Reselect atau dependency graph pada signal `computed`) mencegah siklus komputasi ulang yang tidak perlu?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Signal Dependency Tracking & Topological Sorting**  
   Bagaimana mesin reaktivitas berbasis Signal (seperti implementasi TC39 proposal atau Solid.js) secara otomatis mencatat dependensi (*dependency tracking*) saat runtime tanpa memerlukan array dependency eksplisit seperti `useEffect` React? Jelaskan bagaimana struktur data *Directed Acyclic Graph* (DAG) dan algoritma *topological sorting* digunakan untuk mencegah *glitch* (kondisi di mana computed signal mengeksekusi state transien yang inkonsisten).

2. **Granular Subscriptions via `useSyncExternalStore` & Context Optimization**  
   React Context API secara *default* memicu re-render pada seluruh komponen *consumer* jika referensi objek `value` berubah, terlepas dari apakah properti yang dikonsumsi komponen tersebut berubah atau tidak. Jelaskan bagaimana library state modern (seperti Zustand atau TanStack Store) mengabaikan keterbatasan ini menggunakan React 18 hook `useSyncExternalStore`, *selector subscription pattern*, dan *bail-out equality checks* untuk mengisolasi re-render.

3. **Deep Structural Sharing pada SWR/Cache Invalidation**  
   Ketika sebuah *server cache engine* (seperti TanStack Query) melakukan *re-fetch* di background dan menerima respons JSON baru dari REST API, jelaskan algoritma internal *structural sharing* yang diterapkan pada payload JSON tersebut. Bagaimana proses traversal rekursif mempertahankan kesetaraan referensial (`===`) pada sub-pohon data yang tidak berubah agar tidak memicu re-render pada *subscriber* komponen yang bersangkutan?

4. **Debugging Memory Leaks pada Proxy-based State Stores**  
   Saat menggunakan store berbasis `Proxy` (misal: Valtio atau modul kustom), skenario apa yang dapat menyebabkan *memory leak* tersembunyi yang mencegah garbage collection pada komponen yang telah di-*unmount*? Jelaskan keterlibatan referensi sirkular antara callback listener di dalam Proxy handler, array subscriptions global, dan penggunaan `WeakMap`/`WeakSet` untuk mitigasi retensi memori tersebut.

5. **Race Condition, Stale Responses, & Network Abort Architecture**  
   Sebuah *typeahead search component* memicu pembaruan state asinkron pada setiap ketukan tuts keyboard. Analisis mekanisme kegagalan jika race condition ditangani hanya dengan membandingkan *timestamp* lokal vs penanganan menggunakan `AbortController` yang terikat pada sinyal fetch. Mengapa pembatalan di tingkat protokol jaringan (TCP/HTTP stream termination) jauh lebih superior dibandingkan mengabaikan payload data di memori klien?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Bottleneck Latensi Ekstrem pada High-Frequency Trading UI
Anda adalah Lead Frontend Engineer pada platform analitik kripto real-time. Dashboard menerima streaming order-book via WebSocket dengan kecepatan rata-rata **4.000 update ticks per detik**. Arsitektur lama mendispatch Redux action untuk setiap tick, mengakibatkan UI macet total (*frame rate* anjlok ke 4 FPS), *input lag* paruh waktu melampaui 2 detik, dan CPU browser menyentuh 100% akibat banjir *garbage collection* dari pembuatan objek action baru.

*   **Pertanyaan Diagnostik:**
    1. Mengapa alur data berbasis *standard dispatch-reducer cycle* gagal secara fundamental dalam menangani throughput data berfrekuensi tinggi?
    2. Rancang arsitektur data layer baru yang memisahkan *ingestion rate* dari *render rate*. Bagaimana Anda menerapkan teknik **ArrayBuffer / TypedArrays off-thread** di dalam Web Worker, **Time-Sliced Batching** menggunakan `requestAnimationFrame`, dan **Direct DOM Canvas / Selective Mutation Tree** untuk mempertahankan visual 60 FPS?

### Skenario B: Desinkronisasi Data pada Multi-Step Optimistic UI
Sebuah aplikasi SaaS e-commerce logistik memiliki alur multi-step update: user dapat mengubah volume kargo, menambah catatan, dan mengubah rute armada secara bersamaan di koneksi 3G/flaky. Tim menerapkan *Optimistic UI Updates* agar aplikasi terasa instan. Namun, di produksi muncul anomali fatal: jika request `Update Volume` gagal (HTTP 500) sementara request paralel `Update Rute` berhasil (HTTP 200), rollback yang dieksekusi secara naif mengembalikan seluruh state ke titik awal sebelum `Update Rute` dikirim, menyebabkan data di UI menyimpang dari data faktual di database.

*   **Pertanyaan Diagnostik:**
    1. Mengapa model *snapshot-based rollback* monolitik gagal pada lingkungan operasi asinkron yang konkuren?
    2. Rancang arsitektur **Optimistic Mutation Queue** berbasis **Command Pattern** atau **Patch-Based Inversion (CRDT/Operational Transformation sederhana)**. Jelaskan bagaimana Anda menerapkan *transactional rollback* yang hanya membatalkan *delta* dari operasi yang gagal tanpa merusak perubahan optimistis lainnya yang berstatus *in-flight* atau berhasil.

### Skenario C: State Federation pada Arsitektur Micro-Frontend
Perusahaan berskala global memecah platform aplikasinya menjadi 4 Micro-Frontend (MFE) independen: *Catalog* (React 18), *Checkout* (Vue 3), *Account Settings* (Svelte 5), dan *Global Navigation* (Vanilla TypeScript), yang diintegrasikan menggunakan Module Federation. Terjadi perdebatan keras antartim mengenai cara berbagi state global (seperti Data Autentikasi Pengguna, Shopping Cart, dan Preferensi Mata Uang).

*   **Pertanyaan Diagnostik:**
    1. Berikan evaluasi kritis mendalam terhadap 3 pendekatan berikut:
       *   **Opsi 1:** Shared Redux/Zustand Store instance via `window.__GLOBAL_STORE__`.
       *   **Opsi 2:** Reactive Event Bus berbasis browser API standar (`CustomEvent` + `BroadcastChannel`).
       *   **Opsi 3:** Framework-agnostic Signal Primitive Bus (menggunakan TC39 Signal Polyfill yang diekspos sebagai singleton federasi).
    2. Pilih salah satu pendekatan atau kombinasi yang paling tangguh terhadap *framework version mismatch*, *memory boundary leak*, dan *contract schema drift*. Justifikasikan arsitektur Anda dengan diagram aliran data dan strategi versioning kontraktualnya.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Zero-Dependency Reactive Store Engine dengan Micro-Subscribers & Optimistic Rollback Pipeline

#### Problem Statement
Sebagian besar library state management menambahkan ukuran bundle yang tidak perlu atau mengikat logika aplikasi secara permanen ke satu framework tertentu. Anda diminta untuk merancang dan mengimplementasikan mesin reaktivitas *zero-dependency* berbasis TypeScript murni yang mengimplementasikan arsitektur mutasi atomik, selector granular $O(1)$, dan pipeline eksekusi mutasi optimistik yang mampu melakukan rollback granular secara otomatis jika terjadi error jaringan.

#### Requirements
1. **Core Store Architecture:**
   * Buat class `EngineStore<T extends Record<string, any>>`.
   * State bersifat *immutable* bagi dunia luar: method `getState()` mengembalikan *frozen snapshot* atau *shallow-cloned read-only copy*.
   * Mengimplementasikan `set(updater: (draft: T) => void | Partial<T>)` dengan dukungan pembaruan granular.
2. **Granular Selective Subscriptions:**
   * Method `subscribe<R>(selector: (state: T) => R, listener: (value: R, oldValue: R) => void, equalityFn?: (a: R, b: R) => boolean): () => void`.
   * Jika bagian state yang diekstrak oleh `selector` tidak berubah berdasarkan `equalityFn` (default: strict equality `===`), `listener` **tidak boleh dipanggil** saat state global bermutasi.
   * Method `subscribe` wajib mengembalikan fungsi *unsubscribe* untuk mencegah retensi memori.
3. **Atomic Optimistic Mutation Pipeline:**
   * Implementasikan method `mutateOptimistic<R>(action: OptimisticAction<T, R>): Promise<R>`.
   * Interface aksi harus mencakup:
     * `optimisticPatch: (state: T) => T`: Perubahan lokal yang diterapkan seketika.
     * `networkEffect: (signal: AbortSignal) => Promise<R>`: Operasi asinkron sesungguhnya.
     * `rollback: (state: T, patchApplied: T) => T`: Handler cerdas untuk membatalkan mutasi lokal jika `networkEffect` melempar exception atau *abort*.
4. **Structural Sharing Integrity:**
   * Ketika mutasi terjadi pada properti bersarang, pastikan *node referensi* yang tidak termutasi di dalam pohon objek mempertahankan identitas memori aslinya (`Object.is(oldSubTree, newSubTree) === true`).

#### Constraints
* **Zero Dependencies:** Tidak boleh menggunakan library eksternal apa pun (dilarang menggunakan Redux, Zustand, Immer, RxJS, Lodash, dll.).
* **Strict TypeScript:** Tidak boleh ada tipe `any` atau `as unknown as Type` (kecuali type-guard internal yang valid). *Type-safety* wajib dipelihara dari initial state hingga selector output.
* **Ukuran Kode Runtime:** Kode engine tidak boleh melebihi **250 baris kode** (tidak termasuk comments dan unit test) untuk memastikan efisiensi algoritma.
* **Leak Proof:** Store harus lolos uji unsubscribe memory leak (tidak boleh ada listener yang tertinggal di internal Set/Map setelah invoke unsubscribe).

#### Expected Output
* File TypeScript lengkap: `engine-store.ts`.
* Script verifikasi/test mandiri (menggunakan runner Node.js native test, Bun, atau Vitest) yang membuktikan:
  1. Eksekusi selector selektif (Komponen A tidak terpicu saat Komponen B mengubah cabangnya).
  2. Structural sharing integritas referensial.
  3. Simulasi kegagalan jaringan yang memicu automatic optimistic rollback tanpa merusak mutasi paralel berikutnya.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi siklus data searah (*Unidirectional Data Flow*) dan trade-off komputasi antara *Push-based* vs *Pull-based reactivity*.
- [ ] Batasan native React Context dalam performa skala besar dan bagaimana *external store pattern* (`useSyncExternalStore`) menyelesaikan isu *unnecessary cascading re-renders*.
- [ ] Mekanisme deteksi perubahan berbasis JavaScript `Proxy` vs *Compile-time Reactivity* (Svelte) vs *Dirty-checking Reconciliation* (React).
- [ ] Algoritma *Structural Sharing* dan perannya dalam menjaga kesetaraan referensi objek pada arsitektur immutable.
- [ ] Strategi mitigasi *race condition* menggunakan `AbortController`, *monotonic sequence tokens*, dan *optimistic queueing*.

### Saya tidak perlu menghafal:
- [ ] Seluruh signature API spesifik dari setiap library pihak ketiga (Redux Toolkit, MobX, Recoil, Zustand, Jotai, XState).
- [ ] Trik syntax unik bundler lama untuk mengekspor singleton module.
- [ ] Kode implementasi low-level V8 C++ untuk alokasi `JSProxy` di level engine browser.

### Saya harus bisa melakukan:
- [ ] Menganalisis memory snapshot di Chrome DevTools Heap Profiler untuk melacak kebocoran memori akibat *stale subscription listeners* atau *unbounded cache collections*.
- [ ] Memisahkan data arsitektural secara tegas antara *Server Cache* (via TanStack Query/SWR) dan *Client UI State* tanpa denormalisasi data redundan.
- [ ] Mengimplementasikan *custom subscriber* yang decoupled, type-safe, dan efisien dengan zero dependencies.
- [ ] Merancang alur mutasi optimistik yang tangguh terhadap gangguan konektivitas, kegagalan parsial server, dan *out-of-order network responses*.
- [ ] Memprofil performa render pohon komponen untuk mengidentifikasi dan membasmi *render thrashing* yang disebabkan oleh *unstable object references* di dalam store global.