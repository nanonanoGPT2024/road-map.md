# BAB 03: Quiz, Challenge, & Knowledge Check
**State Management & Data Flow Reaktif**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi Internal `@State` dan Lifecycle Storage**  
   Mengapa mutating property biasa (`var`) di dalam struct `View` dilarang oleh compiler Swift, dan bagaimana SwiftUI runtime mengalokasikan serta mempertahankan memori untuk property wrapper `@State` meskipun struct `View` itu sendiri dihancurkan dan dibuat ulang (*transient*) pada setiap pass evaluasi layout?

2. **Diferensiasi Semantik: `@Binding` vs Closure Callback**  
   Secara performa dan data flow, apa perbedaan mendasar antara mem-pass state child melalui `@Binding` dua arah (*two-way*) dibandingkan menggunakan unidirectional closure callback (`(Value) -> Void`)? Kapan penggunaan `@Binding` justru menjadi anti-pattern yang merusak prinsip modularitas?

3. **Mekanisme Dynamic Member Lookup pada Projectable Value (`$`)**  
   Jelaskan bagaimana sintaks projection (`$state`) bekerja di balik layar menggunakan fitur `projectedValue` pada property wrapper Swift, dan bagaimana `@Binding` mengeksploitasi dynamic member lookup untuk menavigasi nested property tanpa menduplikasi alokasi state.

4. **Hierarki Dependency Tree pada `@Environment`**  
   Bagaimana SwiftUI mengkalkulasi dan me-resolve dependency graph saat sebuah value diinjeksikan melalui `.environment(...)`? Apa implikasi struktural terhadap performa render downstream jika root view menginjeksi structural data type kompleks (seperti struct konfigurasi masif) ke dalam environment?

5. **State Ownership Boundary: Source of Truth vs Derived State**  
   Dalam arsitektur reaktif SwiftUI, apa konsekuensi teknis jika sebuah child view membuat salinan lokal (`@State private var localCopy = parentData`) dari data yang diterimanya dari parent? Jelaskan fenomena "State Desynchronization" yang timbul akibat kegagalan sinkronisasi siklus hidup data tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Evolusi Invalidation: Combine `@ObservableObject` vs Swift Observation `@Observable`**  
   Bandingkan alur kerja notifikasi perubahan antara `ObservableObject` (berbasis `objectWillChange` dari Combine) dengan macro `@Observable` (berbasis Swift Observation engine). Mengapa macro `@Observable` mampu mengeliminasi over-rendering secara drastis pada SwiftUI view tree yang hanya membaca sebagian kecil property dari sebuah model?

2. **AttributeGraph & Invalidation Loop Detection**  
   Jelaskan peran *AttributeGraph* dalam runtime SwiftUI saat memetakan state dependencies ke node view hierarchy. Apa yang secara teknis memicu log console runtime: `Modifying state during view update, this will cause undefined behavior`, dan bagaimana urutan eksekusi internal yang memicu infinite loop tersebut?

3. **Inisialisasi Berbahaya `@StateObject` di dalam View Initializer**  
   Mengapa inisialisasi `@StateObject` dengan dependensi dari view parameter (`init(service: Service) { _viewModel = StateObject(wrappedValue: ViewModel(service)) }`) dianggap berbahaya dan rentan menimbulkan silent bug ketika parent view me-reconstruct child view tersebut dengan dependensi baru? Bagaimana pola mitigasi arsitektural yang benar?

4. **Task Lifetime Management & Concurrency State Races**  
   Bagaimana modifier `.task(id: ...)` mengoordinasikan eksekusi asynchronous terhadap state mutation? Apa yang terjadi jika child view di-unmount dari hirarki visual sebelum asynchronous task selesai menulis state ke main-thread storage? Analisis potensi memory leak dan race condition yang dapat terjadi.

5. **Structural Identity vs Explicit Identity terhadap Retensi State**  
   Bagaimana SwiftUI menentukan apakah `@State` dari sebuah view harus dipertahankan atau di-reset saat struktur view mengalami percabangan logika conditional branching (penggunaan `if-else` vs `.opacity()`), dan bagaimana injeksi eksplisit `.id(UUID())` mengintervensi penghancuran node pada memory graph?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Invalidation Storm pada Financial Ticker Dashboard
Sebuah aplikasi trading crypto multi-aset menampilkan daftar 200 pair mata uang secara real-time. Data diperbarui melalui WebSocket dengan frekuensi ~50 update per detik. Arsitektur saat ini menggunakan satu class `GlobalMarketStore` bertipe `ObservableObject` yang memegang array `[CryptoPair]`. Setiap kali sebuah pair berubah harganya, array diperbarui dan memicu `objectWillChange`.
* Gejala: Interface mengalami frame drop parah (scroll stuttering < 15 FPS), CPU usage menyentuh 100%, dan profiling via Instruments (Time Profiler & SwiftUI View Body) menunjukkan evaluasi body berulang kali pada baris cell yang datanya sama sekali tidak berubah.

**Pertanyaan Diagnostik:**
1. Mengapa granularitas invalidasi berbasis Combine pada skenario ini gagal mengisolasi update per-cell?
2. Bagaimana Anda merestrukturisasi model data menggunakan arsitektur Swift Observation (`@Observable`) atau local state slicing agar hanya cell yang harganya bermutasi yang dievaluasi ulang oleh AttributeGraph?

---

### Skenario B: Race Condition dan Loss of Integrity pada Form Transaksi Checkout
Pada checkout view sebuah e-commerce enterprise, user dapat memilih kupon diskon, metode pembayaran, dan mengisi tip custom. Pemilihan kupon memicu network call asynchronous untuk memvalidasi diskon, sementara pemilihan metode pembayaran juga memvalidasi kelayakan nominal secara async. Kedua operasi ini memutasi shared state `OrderSummary` melalui concurrent `Task` di background.
* Gejala: Pada kondisi koneksi tidak stabil (high latency jitter), terjadi state corruption: nominal diskon dari kupon yang gagal divalidasi tetap terpotong pada total order summary jika respon API metode pembayaran tiba belakangan dan menimpa validasi sebelumnya.

**Pertanyaan Diagnostik:**
1. Identifikasi concurrency antipattern pada mutasi asynchronous state di atas yang menyebabkan dirty writes dan unhandled order of execution.
2. Rancang struktur state orchestration menggunakan Swift Structured Concurrency (`async/await`, `actor`, atau Task cancellation handling) untuk menjamin atomic updates dan data integrity pada `OrderSummary`.

---

### Skenario C: Dilema Arsitektur Modular Multi-Package SPM
Tim enterprise Anda mengelola 15 modul Swift Package Manager (SPM). Modul autentikasi mendefinisikan `UserSessionState`. Modul fitur (`FeatureCart`, `FeatureSettings`, `FeatureFeed`) harus mengakses dan sebagian memutasi data session tersebut tanpa menciptakan circular dependency antar paket.
* Tim memperdebatkan dua pendekatan:
  * **Opsi 1**: Menginjeksi `UserSessionState` via `.environment()` di root app container dan membiarkan downstream feature mengonsumsinya secara implisit.
  * **Opsi 2**: Menggunakan explicit unidirectional dependency injection melalui view model factories dan passing explicit protocol abstractions.

**Pertanyaan Diagnostik:**
1. Bedah kelemahan Opsi 1 dalam konteks static type safety, UI testability (isolated preview), dan modular compilation boundaries.
2. Rekomendasikan pola kompromi arsitektural yang mempertahankan kemudahan environment flow namun tetap menjamin strict decoupling, testability, dan isolasi mutasi state lintas modul SPM.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Frequency Real-Time Telemetry & Order Book Engine

#### Problem Statement
Anda ditugaskan membangun engine visualisasi untuk sistem telemetri data pasar bursa finansial. Data stream memancarkan order updates (Bid/Ask entries) pada frekuensi 60Hz. Desain lama gagal beroperasi karena setiap tick data me-render ulang seluruh container view, menyebabkan AttributeGraph overhead yang membuat main thread terkunci (*hitched*).

#### Requirements
1. **Isolated Reactivity Engine**:
   - Bangun model data `OrderBookEngine` menggunakan macro `@Observable`.
   - Pisahkan model menjadi slice granular (`BidSlice`, `AskSlice`, `SpreadMetric`) sehingga perubahan pada Bid data *sama sekali tidak* memicu re-evaluation pada View yang merender Ask data atau Spread metrics.
2. **Debounced/Throttled Aggregator**:
   - Buat pipeline concurrency yang mampu menyerap throughput network tinggi (high write rate), namun membatasi update flush ke SwiftUI render loop pada interval stabil (misal: adaptif 30Hz - 60Hz) menggunakan Swift Concurrency async sequences atau background actor buffer.
3. **Optimized Structural Hierarchy**:
   - Terapkan child views yang diisolasi dengan identitas statis (`explicit EquatableView` atau granular state tracking) untuk merender tabel order level-by-level tanpa alokasi struct yang redundan.
4. **Diagnostic Tooling**:
   - Sertakan custom Visual Invalidation Debugger (misal: flashing border overlay menggunakan `Self._printChanges()` atau runtime tracking helper) yang membuktikan secara visual bahwa hanya row yang bermutasi yang menjalankan evaluasi view body.

#### Constraints
- Wajib menggunakan target platform iOS 17+ (Swift 5.9+ / Swift 6 language mode).
- Dilarang keras menggunakan `ObservableObject` / `@Published` Combine legacy.
- Dilarang memblokir Main Thread (Main Actor starvation < 1ms per frame).
- Memory footprint harus stabil (zero retained leak cycles pada streaming berkelanjutan).

#### Expected Output
Source code implementasi modular yang mencakup:
1. `TelemetryActor`: Mengelola buffer data mentah dari background network simulasi.
2. `@Observable class OrderBookViewState`: Mengelola fine-grained observable properties.
3. Dekomposisi SwiftUI Views (`OrderBookContainerView`, `BidListView`, `AskListView`, `OrderRowView`).
4. Unit/UI test case atau verification harness yang membuktikan body pass hanya terjadi pada node yang terdampak.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Bagaimana SwiftUI runtime mengalokasikan dan mempertahankan data `@State` pada external backing store di luar lifetime struct `View`.
- [ ] Perbedaan fundamental antara tracking dependensi berbasis macro Swift `@Observable` (`withObservationTracking`) versus event streaming berbasis Combine `objectWillChange`.
- [ ] Peran internal *AttributeGraph* dalam memetakan dependencies, invalidasi node, dan pencegahan layout thrashing.
- [ ] Perbedaan antara *Structural Identity* dan *Explicit Identity* serta pengaruh langsungnya terhadap siklus hidup (preservation/destruction) local state.
- [ ] Batasan isolation thread: mengapa mutasi state UI *harus* strictly beroperasi pada `@MainActor` dan bagaimana Swift Concurrency memvalidasi boundary ini secara statis.
- [ ] Implikasi performa dari passing dependency lewat dynamic environment hierarchy terhadap subtree invalidation.

### Saya tidak perlu menghafal:
- [ ] Alamat offset memori atau private assembly symbol dari SwiftUI C++ dynamic runtime library.
- [ ] Angka benchmark absolut frame rendering time per-device (cukup pahami batas 16.6ms untuk target 60 FPS dan 8.3ms untuk 120 FPS ProMotion).
- [ ] Seluruh implementasi macro expansion code dari `@Observable` baris-per-baris (cukup pahami registrasi observer via key path tracking).

### Saya harus bisa melakukan:
- [ ] Mendiagnosis over-rendering dan frame drops menggunakan Instruments (SwiftUI View Body, Time Profiler) serta debugging console via `Self._printChanges()`.
- [ ] Mengonversi arsitektur legacy berbasis Combine (`ObservableObject`, `@StateObject`, `@ObservedObject`) ke modern Swift Observation Framework (`@Observable`) secara presisi.
- [ ] Merancang data flow unidirectional yang aman dari race conditions pada aplikasi multi-threaded berskala besar.
- [ ] Memecah monolithic state model menjadi bounded-context state slices untuk meminimalisasi re-render cascading di dalam complex UI trees.
- [ ] Membangun custom state binding abstractions yang decoupled, type-safe, dan ramah terhadap automated unit testing serta isolated Xcode Previews.