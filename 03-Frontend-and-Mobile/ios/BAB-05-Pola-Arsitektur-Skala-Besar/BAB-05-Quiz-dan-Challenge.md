# BAB 05: Quiz, Challenge, & Knowledge Check
**Pola Arsitektur Skala Besar (Clean Architecture, MVVM, & TCA)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Dependency Inversion Principle pada Clean Architecture
Dalam implementasi Clean Architecture murni di ekosistem Swift, lapisan *Domain* tidak boleh memiliki ketergantungan (*dependency*) terhadap *Data Layer* maupun *Presentation Layer*.
1. Jelaskan secara mekanis bagaimana *Dependency Inversion Principle* (DIP) diwujudkan dalam Swift menggunakan protokol untuk memutus dependensi antara *Domain Use Case* dan *Repository Implementation*!
2. Mengapa *Domain Layer* dilarang keras mengimpor *framework* platform seperti `UIKit`, `SwiftUI`, atau *persistence library* seperti `CoreData` / `SwiftData`? Analisis konsekuensinya terhadap portabilitas logika bisnis dan determinisme *unit testing*.

### Soal 1.2: Transisi State-Driven: Combine MVVM vs Swift 5.9+ `@Observable`
Sebelum Swift 5.9, MVVM di SwiftUI mengandalkan `ObservableObject` dengan properti `@Published` yang berjalan di atas *framework* Combine. Sejak Swift 5.9, Apple memperkenalkan macro `@Observable` berbasis framework `Observation`.
1. Bagaimana perbedaan mendasar mekanisme *dependency tracking* dan *view invalidation* antara `ObservableObject` (yang memicu `objectWillChange`) dan macro `@Observable`?
2. Jelaskan dampaknya terhadap *rendering performance* ketika sebuah *ViewModel* memiliki 20 properti independen, namun sebuah View hanya membaca satu properti dari *ViewModel* tersebut!

### Soal 1.3: Anatomi Unidirectional Data Flow (UDF) pada The Composable Architecture (TCA)
TCA mendasarkan arsitekturnya pada prinsip *Unidirectional Data Flow* (UDF) dan pemrograman fungsional murni.
1. Uraikan alur hidup (*lifecycle*) sebuah mutasi data mulai dari interaksi UI, emisi `Action`, eksekusi pada `Reducer`, perubahan `State`, hingga pemanggilan side-effect melalui `Effect`!
2. Mengapa fungsi `reduce` pada TCA diwajibkan berupa *pure function* dengan mutasi *in-place* (`inout State`), dan bagaimana TCA menjamin isolasi operasi asinkron/I-O agar tidak mencemari determinisme *reducer*?

### Soal 1.4: Repository Pattern vs Data Source Abstraction
Sering terjadi kerancuan antara peran *Repository* dan *Remote/Local Data Source* pada aplikasi modular berskala besar.
1. Definisikan batasan tanggung jawab (*separation of concerns*) yang membedakan *Repository* dari *Data Source*!
2. Mengapa *Data Transfer Object* (DTO) dari respons API jaringan harus ditransformasikan (*mapped*) menjadi *Domain Entity* murni sebelum diekspos ke *Use Case*, alih-alih menggunakan model DTO langsung di seluruh lapisan aplikasi?

### Soal 1.5: Skalabilitas State: Single Source of Truth (TCA) vs Distributed State (MVVM)
Dalam aplikasi dengan lebih dari 150 modul fitur:
1. Bandingkan karakteristik *trade-off* skalabilitas antara pendekatan *Single State Tree* milik TCA (di mana state anak dikomposisikan ke state induk) dengan pendekatan *Distributed Isolated State* milik MVVM (di mana setiap ViewModel mengelola *state bucket*-nya sendiri)!
2. Analisis metrik konsumsi memori (*heap footprint*), kompleksitas *navigation stack handling*, dan resiko *state desynchronization* pada kedua pendekatan tersebut.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Actor Isolation Violation & Main-Thread Hitches pada MVVM
Diberikan cuplikan implementasi ViewModel berikut:

```swift
@Observable
final class OrderHistoryViewModel {
    var orders: [OrderEntity] = []
    var isProcessing: Bool = false
    private let fetchOrdersUseCase: FetchOrdersUseCaseProtocol

    init(fetchOrdersUseCase: FetchOrdersUseCaseProtocol) {
        self.fetchOrdersUseCase = fetchOrdersUseCase
    }

    func loadOrders() async {
        isProcessing = true
        do {
            let fetched = try await fetchOrdersUseCase.execute()
            self.orders = fetched.sorted { $0.timestamp > $1.timestamp }
        } catch {
            // Error handling
        }
        isProcessing = false
    }
}
```

1. Jika `loadOrders()` dipanggil dari *task* konteks latar belakang (*cooperative thread pool* non-MainActor), jelaskan resiko *thread safety* dan potensi *runtime hitch* yang terjadi pada rendering SwiftUI!
2. Tuliskan refaktorisasi arsitektural yang presisi menggunakan `@MainActor`, pemisahan komputasi berat (`sorting`) ke *detached task* / *background actor*, dan jelaskan bagaimana transisi *context switching* antar-thread diminimalisasi!

### Soal 2.2: TCA Effect Cancellation & Race Conditions pada Auto-Search
Sebuah fitur *live search* pada TCA mengeksekusi *network request* setiap kali pengguna mengetik satu karakter ke dalam textfield menggunakan aksi `.searchQueryChanged(String)`.
1. Bagaimana mekanisme internal TCA menangani pembatalan task asinkron yang sedang berjalan melalui `.cancellable(id:cancelInFlight:)`?
2. Apa yang terjadi di tingkat Swift Concurrency Runtime (`Task.cancel()`) jika respons dari pencarian string sebelumnya tiba di `Store` tepat sebelum request baru dikirimkan, namun request lama belum sepenuhnya selesai diproses oleh transport layer (URLSession)? Bagaimana cara menjamin linearitas hasil pencarian?

### Soal 2.3: Retain Cycles & Concurrency Leaks pada MVVM berbasis Combine vs AsyncStream
Dalam implementasi lama, ViewModel menyimpan `Set<AnyCancellable>`. Pada migrasi modern, ViewModel mengonsumsi `AsyncStream<LocationCoordinate>` dari sebuah *Location Manager*.
1. Identifikasi skenario kebocoran memori (*memory leak* / *task leak*) yang dapat terjadi jika sebuah `Task` yang mengiterasi `for await coordinate in locationStream` diinisialisasi di dalam ViewModel tanpa mengikat siklus hidupnya ke *view lifecycle*!
2. Bandingkan pola pembersihan memori antara pembatalan manual melalui `deinit` dengan mekanisme otomatis menggunakan modifier SwiftUI `.task(id:)`!

### Soal 2.4: TCA ViewStore / Store Scoping Re-render Bottleneck
Pada pohon komponen TCA yang besar, *subview* sering kali membutuhkan hanya sebagian kecil (*slice*) dari global state:

```swift
Scope(state: \.profile, action: \.profile) {
    ProfileFeature()
}
```

1. Jelaskan mekanisme komputasi diffing dan re-evaluasi body View pada SwiftUI saat menggunakan `store.scope`!
2. Jika sebuah mutasi terjadi pada state saudara (*sibling state*) di root level yang tidak digunakan oleh `ProfileFeature`, apakah `ProfileView` akan memicu komputasi ulang pada `body`? Jelaskan bagaimana *state observation scoping* dan *equatability* bekerja di bawah kap mesin TCA untuk mencegah hal tersebut!

### Soal 2.5: Kebocoran Abstraksi CoreData / SwiftData pada Domain Layer
Seorang developer mendefinisikan *Domain Entity* sebagai *subclass* dari `NSManagedObject` atau model beranotasi `@Model` (SwiftData) dengan dalih menghindari duplikasi kode antara *Domain Layer* dan *Persistence Layer*.
1. Buktikan mengapa keputusan arsitektural ini merusak prinsip *Boundary Decoupling* pada Clean Architecture, ditinjau dari manajemen dependensi *concurrency* (contoh: `NSManagedObjectContext` thread-confinement rules vs Swift Structured Concurrency)!
2. Bagaimana cara mengisolasi *faulting mechanism* dan *lazy loading* dari CoreData agar tidak bocor ke logika bisnis murni di Use Case?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: High-Frequency Ticker Dashboard Freeze (Insiden Performa Skala Besar)
Aplikasi investasi kripto enterprise Anda memiliki modul *Live Market Dashboard* yang mengonsumsi data *order book* via WebSocket dengan frekuensi rata-rata 60 update per detik. Arsitektur yang digunakan adalah MVVM dengan `@Observable`. 

Ketika pasar volatil, CPU usage melonjak hingga 100%, terjadi *main thread stall* rata-rata 45 frame drops per detik (UI patah-patah/freeze), dan aplikasi mengalami crash akibat *Out-of-Memory* (OOM) setelah 10 menit beroperasi di perangkat generasi lama.

```
[WebSocket Client (Engine)] 
       │ (60 msgs/sec via Background Thread)
       ▼
[OrderBookRepository] 
       │ (Maps DTO to Domain Entity)
       ▼
[OrderBookViewModel (@Observable)] 
       │ (Updates @ObservationTracked var bids: [OrderBookEntry])
       ▼
[SwiftUI View Hierarchy (LazyVStack with 200 Rows)]
```

#### Pertanyaan Diagnostik & Solusi:
1. **Root-Cause Analysis**: Jelaskan titik kegagalan (*bottleneck*) arsitektur di atas! Mengapa pembaruan langsung ke properti `@Observable` dengan frekuensi 60Hz melumpuhkan subsistem *layout engine* SwiftUI?
2. **Arsitektur Buffer & Throttling**: Rancang solusi perbaikan arsitektur di tingkat *Domain/Presentation boundary*! Buatlah skema algoritma penggabungan data (*batching/throttling strategy*) menggunakan Swift Concurrency (`AsyncAlgorithms` atau custom buffer actor) sehingga emisi mutasi ke UI dibatasi maksimum 10-15Hz tanpa kehilangan integritas harga pasar terkini!
3. **Data Structure Optimization**: Mengapa representasi `[OrderBookEntry]` pada *State* tidak cocok untuk operasi diffing cepat berfrekuensi tinggi, dan bagaimana Anda merefaktornya menggunakan struktur data yang lebih optimal (misal: contiguous storage atau keyed collections)?

---

### Skenario B: Double-Payment & Deadlock pada Checkout Multi-Step (TCA)
Sebuah aplikasi e-commerce global menggunakan arsitektur TCA modular untuk flow *Checkout*. Flow ini melibatkan: Validasi Saldo, Penguncian Inventori (Reserve Inventory), dan Eksekusi Payment Gateway.

Pada kondisi jaringan seluler fluktuatif (*packet loss 30%*), pengguna menekan tombol "Bayar Sekarang" berkali-kali secara agresif. Terjadi anomali kritis:
- Beberapa pengguna mengalami *double billing* (saldo terpotong dua kali).
- Sebagian pengguna lain mengalami *deadlock*: UI *loading indicator* berputar selamanya karena state payment terjebak pada status `.isProcessing = true`, sementara backend sudah mengembalikan respons error *idempotency conflict*.

```swift
// Snippet Reducer yang bermasalah:
case .payButtonTapped:
    state.isProcessing = true
    return .run { [cart = state.cart] send in
        let result = try await paymentClient.charge(cart.id, cart.totalAmount)
        await send(.paymentResponse(result))
    } catch: { error, send in
        await send(.paymentFailed(error.localizedDescription))
    }
```

#### Pertanyaan Diagnostik & Solusi:
1. **Race Condition & Concurrency Vulnerability**: Bedah kode di atas! Mengapa kode tersebut rentan terhadap eksploitasi multi-tap dan state desynchronization ketika terjadi keterlambatan jaringan?
2. **Idempotency & Effect Exhaustion**: Modifikasi implementasi *Reducer* tersebut dengan standar industri TCA menggunakan:
   - Mekanisme *Effect Cancellation* atau pencegahan *in-flight execution* (Debounce vs Throttle vs Idempotency Key Guard).
   - Pengamanan state transition machine (State Machine formal) yang menolak aksi `.payButtonTapped` jika state berada di luar `.idle`.
3. **Timeout & Cleanup Resilience**: Rancang penanganan kegagalan (*resilience policy*) agar `state.isProcessing` dijamin kembali ke status aman (fail-safe) jika downstream service backend tidak merespons dalam durasi batas waktu tertentu (*timeout window*).

---

### Skenario C: Dilema Modular Monolith: Clean MVVM vs Pure TCA untuk Aplikasi Core Banking
Tim arsitektur Bank Tier-1 yang terdiri dari 60 iOS Engineer sedang menyusun *blueprint* untuk refaktorisasi sistem perbankan utama (*Core Mobile Banking*). Aplikasi memiliki lebih dari 300 modul framework, dependensi pihak ketiga yang dikontrol sangat ketat, serta standar audit kepatuhan regulasi finansial yang ekstrim.

Sebagian tim menginginkan transisi penuh ke **TCA (The Composable Architecture)** demi kemudahan *time-travel debugging* dan determinisme *business test*. Sebagian tim lain mendesak penggunaan **Clean Architecture + Modern MVVM (`@Observable` + Protocols)** untuk menghindari ketergantungan pada *external open-source library* skala masif.

#### Pertanyaan Diagnostik & Trade-off:
1. **Analisis Build Time & Compiler Stress**: Apa dampak pengadopsian TCA secara ekstensif (macro expansion, generic reducer concatenation, existential types) terhadap *incremental compilation time* dan ukuran binari (*binary bloat*) pada skala 300+ modul, dibandingkan Clean MVVM murni berbasis SPM modular?
2. **Auditing & State Reproducibility**: Dari sudut pandang investigasi insiden transaksi fraud, bagaimana TCA mengungguli MVVM dalam menghasilkan *audit log* langkah-demi-langkah dari seluruh *action* pengguna, dan bisakah karakteristik *reproducibility* ini direplikasi di Clean MVVM tanpa mengorbankan portabilitas?
3. **Architectural Decision Record (ADR)**: Sebagai *Principal Architect*, buatlah sintesis rekomendasi keputusan! Strategi hibrida apa yang paling rasional untuk memadukan ketahanan abstraksi Clean Architecture di tingkat Core/Domain dengan prediktabilitas UDF/TCA di tingkat Presentation modul transaksi sensitif?

---

## 4. Chapter Challenge

### Tantangan Praktis: Refaktorisasi High-Concurrency Order Fulfillment Engine

#### Problem Statement
Anda mewarisi modul *Order Fulfillment* pada aplikasi pemesanan ride-hailing/delivery yang ditulis secara buruk: *God-ViewModel* (1500 baris kode), mencampurkan panggilan CoreLocation, WebSocket streaming, API Network, pemutakhiran UI SwiftUI, dan persistensi lokal secara langsung tanpa pemisahan *layer*. 

Aplikasi sering mengalami *data-race crash*, unit test mustahil dijalankan tanpa mocking tingkat rendah, dan status order sering tidak sinkron antara status di peta dan status rincian pembayaran.

#### Requirements
Rancang dan implementasikan subsistem arsitektur baru menggunakan pendekatan **Clean Architecture** murni dengan **Presentation Layer berbasis TCA atau Modern MVVM (@Observable + Structured Concurrency)**:

1. **Domain Layer**:
   - Definisikan Entity murni: `FulfillmentOrder`, `CourierLocation`, `OrderStatus` (enum state machine: `searching`, `allocated`, `enRoute`, `arrived`, `completed`, `cancelled`).
   - Buat Use Case: `TrackActiveOrderUseCase` yang menggabungkan aliran data status order via polling/WebSocket dan stream koordinat kurir real-time.
   - Semua kontrak dependensi dinyatakan dalam Swift Protocols yang tidak memiliki dependensi terhadap UIKit/SwiftUI/3rd party SDKs.

2. **Data Layer**:
   - Implementasikan `OrderRepository` yang mengoordinasikan `RemoteOrderDataSource` dan `LocalPersistenceDataSource`.
   - Menggunakan Swift Actors (`actor FulfillmentOrderRepository`) untuk memastikan *thread safety* pada *in-memory cache*.
   - Menerapkan pemetaan eksplisit (*mapping layer*): `OrderDTO -> FulfillmentOrder` yang memvalidasi integritas data (throw domain error jika payload korup).

3. **Presentation Layer (TCA atau Modern MVVM)**:
   - Menerapkan transisi state deterministik: UI tidak boleh menampilkan tombol "Batalkan" jika order sudah masuk ke status `enRoute` atau setelahnya.
   - Pembatalan *Task* otomatis jika pengguna meninggalkan layar pemantauan order (*screen dismiss*).
   - Penanganan *error recovery* modular jika koneksi terputus di tengah jalan (otomatis *retry* dengan *exponential backoff*).

4. **Testing Suite**:
   - Buat minimal 3 *Deterministic Unit Tests* untuk Use Case dan ViewModel/Reducer:
     1. Tes transisi status order yang sukses dari `searching` hingga `completed`.
     2. Tes penanganan kegagalan jaringan saat *tracking* yang memicu transisi ke state `.reconnecting`.
     3. Tes pembatalan aliran *stream* asinkron ketika event `cancelTracking` dipicu (bebas *leak*).

#### Constraints
- Menggunakan **Swift 5.9+** dengan flag compiler `-strict-concurrency=complete` aktif tanpa satupun *warning* atau *data-race diagnostic error*.
- Dilarang keras menggunakan *force unwrapping* (`!`), `DispatchQueue.main.async`, atau `@unchecked Sendable` (kecuali dibuktikan dengan *thread-safe lock mechanism* yang terdokumentasi).
- Seluruh mutasi UI wajib terisolasi di `@MainActor`.

#### Expected Output
Kirimkan satu bundel arsitektur modular terorganisir yang mencakup:
- Protokol dan implementasi *Domain Entities* dan *Use Cases*.
- Implementasi *Repository Actor* beserta DTO mapping logic.
- Kode *Reducer/ViewModel* lengkap dengan manajemen *Side Effects* dan *State Mutation*.
- Kode *Unit Test* lengkap menggunakan Swift Testing / XCTest dengan Mock Data Sources terisolasi.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk mengukur kematangan penguasaan materi Bab 05 secara mandiri.

### Saya harus memahami:
- [ ] Batasan arsitektural (*Architectural Boundaries*) dan aliran ketergantungan kode menurut *Inversion of Control* (IoC) dan *Dependency Inversion Principle* (DIP).
- [ ] Perbedaan fundamental antara model *Value Semantics* vs *Reference Semantics* dalam manajemen state aplikasi iOS.
- [ ] Mekanisme kerja *Observation framework* (Swift 5.9 Macro) di bawah kap mesin dibandingkan *Combine Publisher-Subscriber pattern*.
- [ ] Prinsip matematis di balik *Pure Functions*, *State Reducers*, dan *Single Source of Truth* dalam sistem reaktif berskala masif.
- [ ] Isolasi eksekusi asinkron (*Actor Model*, Global Actors `@MainActor`, dan Cooperative Thread Pool) dan kaitannya dengan konsistensi state.
- [ ] Bagaimana TCA mengelola siklus hidup *side-effects* menggunakan abstraksi `Effect` dan mekanisme pembatalannya.

### Saya tidak perlu menghafal:
- [ ] Seluruh varian operator Combine (`zip`, `combineLatest`, dsb.) karena Swift Concurrency (`AsyncSequence`, `AsyncStream`) menggantikan sebagian besar use-case orkestrasi asinkron dasar.
- [ ] Konfigurasi boilerplate internal framework eksternal secara harfiah; yang esensial adalah pemahaman alur arsitektural dan *trade-off*-nya.
- [ ] Sintaks macro code generation TCA baris-demi-baris; cukup pahami ekspansi struktural dan dampaknya pada hierarki state.

### Saya harus bisa melakukan:
- [ ] Memisahkan basis kode monolitik menjadi modul-modul SPM terisolasi (*Domain*, *Data*, *Presentation*, *Core/Network*).
- [ ] Menulis *Domain Logic* dan *Use Cases* murni yang 100% *unit-testable* tanpa memerlukan mocking framework eksternal atau UI host application.
- [ ] Melacak dan menumpas *memory leak*, *retain cycle*, dan *unbounded concurrency tasks* menggunakan Xcode Instruments (Allocations, Leaks, dan Time Profiler).
- [ ] Mengonfigurasi isolasi konkurensi penuh (`SWIFT_STRICT_CONCURRENCY=complete`) dan menyelesaikan error `Sendable` boundary crossings secara elegan.
- [ ] Memilih dengan tegas kapan harus menerapkan Clean MVVM ringan vs kapan kompleksitas aplikasi mewajibkan implementasi arsitektur terstruktur seperti TCA.