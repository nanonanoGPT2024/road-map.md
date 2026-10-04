# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (State Management & Data Flow Reaktif)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal dari sistem Observation modern (`@Observable`, `ObservationRegistrar`) serta membedakan mekanisme penelusuran dependensi (*dependency tracking*) berbutir halus (*fine-grained*) dibandingkan model berbasis Combine terdahulu (`ObservableObject`, `@Published`).
- Mengimplementasikan pola *Unidirectional Data Flow* (UDF) tingkat produksi yang aman terhadap *concurrency* (*thread-safe*), terisolasi pada `@MainActor`, dan modular.
- Menganalisis dan mengeliminasi *over-rendering*, *view invalidation storm*, serta kebocoran memori (*retain cycle*) yang diakibatkan oleh *escaping closures* atau *observation retention*.
- Merancang state pipeline asinkron yang menangani *backpressure*, *cancellation*, *task debouncing*, dan integrasi *Swift Concurrency* (`AsyncSequence`, `Actors`).
- Melakukan profiling performa runtime SwiftUI menggunakan Xcode Instruments (*SwiftUI View Body*, *Allocations*, dan *Time Profiler*) untuk mengidentifikasi *render bottleneck*.

---

## 2. Prerequisite

Peserta wajib memahami konsep dasar berikut:
- **Swift Language Fundamentals**: Swift Concurrency (`async`/`await`, `Task`, `Actor`, `@MainActor`), Generic Constraints, Macros, Memory Management (ARC, `weak`, `unowned`).
- **SwiftUI Core**: Siklus hidup `View`, deklarasi `body`, modulasi komponen, serta penggunaan dasar *property wrappers* (`@State`, `@Binding`, `@Environment`).
- **Combine Basics**: Pemahaman operator reaktif (`map`, `filter`, `debounce`, `combineLatest`) dan *publisher-subscriber lifecycle* sebagai konteks transisi menuju Observation Framework modern.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Evolusi: Combine (`ObservableObject`) vs. Swift Observation (`@Observable`)

Pada arsitektur SwiftUI lawas (iOS 13–16), state global/eksternal bergantung pada protokol `ObservableObject` yang ditopang oleh Combine:

```swift
// Legacy Approach (iOS 13-16)
final class LegacyViewModel: ObservableObject {
    @Published var name: String = ""
    @Published var counter: Int = 0
}
```

Mekanisme internal `ObservableObject`:
1. Setiap mutasi pada properti beranotasi `@Published` memicu `objectWillChange.send()`.
2. Sinyal ini bekerja pada level **objek**, bukan pada level properti spesifik.
3. Setiap View yang mengamati instance tersebut via `@ObservedObject` atau `@StateObject` akan menandai seluruh *view graph node* terkait sebagai *dirty*, meskipun View tersebut hanya membaca properti `name` dan yang termutasi adalah `counter`.

Swift 5.9 (iOS 17+) memperkenalkan framework `Observation` melalui Macro `@Observable`:

```swift
// Modern Approach (iOS 17+)
@Observable
final class ModernViewModel {
    var name: String = ""
    var counter: Int = 0
}
```

Makro `@Observable` mentranslasikan kode tersebut pada fase kompilasi menjadi:
- Penyisipan properti internal: `internal let _$observationRegistrar = ObservationRegistrar()`.
- Penggantian *stored properties* menjadi *computed properties* yang memanggil:
  - `_$observationRegistrar.access(self, keyPath: \.name)` di dalam `getter`.
  - `_$observationRegistrar.withMutation(of: self, keyPath: \.name)` di dalam `setter`.

### 3.2 Dynamic Dependency Tracking Graph

Berbeda dengan Combine yang memerlukan deklarasi eksplisit via *property wrapper* pada View (`@ObservedObject`), framework modern memanfaatkan runtime penelusuran otomatis:

```
[View Body Evaluation]
       │
       ▼
[Read property: viewModel.name]
       │
       ▼
[ObservationRegistrar.access(self, keyPath: \.name)]
       │
       ▼
[Registrar mendaftarkan ID View ke dalam Dependency Table untuk KeyPath \.name]
```

Ketika `viewModel.counter` berubah:
- Setter memanggil `withMutation(of: self, keyPath: \.counter)`.
- Registrar memeriksa daftar subscriber untuk keypath `\.counter`.
- Karena View hanya terdaftar pada keypath `\.name`, View **tidak** akan diinvalidation. Rendernya diskip sepenuhnya (*zero invalidation cost*).

```
   Legacy Combine Model (Object-level Invalidation)
   ┌──────────────────────────────────────────────┐
   │ LegacyViewModel                              │
   │  ├─ name (modified) ──┐                      │
   │  └─ counter           ▼                      │
   │           objectWillChange.send()            │
   └──────────────────────┬───────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
   ┌─────────────────┐         ┌─────────────────┐
   │ ViewA (reads    │         │ ViewB (reads    │
   │ only name)      │         │ only counter)   │
   │ [RE-RENDERED]   │         │ [RE-RENDERED]   │ ❌ Unnecessary Re-render!
   └─────────────────┘         └─────────────────┘

   Modern Observation Model (Property-level Invalidation)
   ┌──────────────────────────────────────────────┐
   │ ModernViewModel                              │
   │  ├─ name (modified) ──┐                      │
   │  └─ counter           │                      │
   └──────────────────────┼───────────────────────┘
                          │ access(\.name)
                          ▼
            ┌───────────────────────────┐
            │ ViewA (reads only name)   │
            │       [RE-RENDERED]       │ ✅ Targeted Invalidation
            └───────────────────────────┘
            (ViewB is NOT notified or evaluated)
```

### 3.3 MainActor Isolation & Cross-Actor Synchronization

SwiftUI rendering graph terikat secara mutlak pada thread utama (`@MainActor`). Namun, data ingestion sering terjadi pada *background worker actors*.

Jika mutasi state terjadi di luar MainActor, *race condition* terjadi pada `ObservationRegistrar`. Meskipun `ObservationRegistrar` didesain *thread-safe* secara internal via *os_unfair_lock*, pembaruan state yang men-trigger evaluasi `View.body` di luar *main thread* akan memicu runtime warning atau UI glitch (purple warning pada Xcode).

Untuk memastikan *strict concurrency safety*:
1. UI State Models harus diisolasi dengan `@MainActor`.
2. Integrasi background stream harus ditransformasikan melalui asynchronous pipelines yang secara eksplisit melompat ke MainActor context sebelum mutasi dilakukan.

---

## 4. Why & What

| Fitur / Konsep | Mengapa Dibutuhkan (Why) | Apa Itu (What) |
| :--- | :--- | :--- |
| **Observation Framework** | Mencegah *render storms* pada aplikasi besar di mana satu root state object memiliki puluhan properti yang berubah independen. | Mesin pelacakan reaktif compile-time berbasis macro yang menghubungkan view read-access langsung ke keypath model. |
| **MainActor ViewModels** | Mencegah crash *data race* saat concurrent background network task/sockets memperbarui array atau state UI secara serentak. | Anotasi kompilator yang menjamin eksekusi method dan manipulasi properti kelas hanya berjalan di *main runloop*. |
| **Unidirectional Data Flow (UDF)** | Mencegah *state drift*, *circular dependencies*, dan efek samping tak terduga (*spaghetti state updates*) pada aplikasi enterprise multi-modul. | Pola arsitektur di mana View hanya memancarkan *User Intent (Action)*, diproses oleh *State Container*, menghasilkan *State Snapshot* baru yang immutably diproyeksikan ke View. |
| **Debounced Async Pipelines** | Mencegah *cancellation churn* dan over-fetching HTTP API saat input pengguna terjadi sangat cepat (e.g., live search). | Implementasi manipulasi stream asinkron berbasis `Task` atau `AsyncStream` untuk menahan eksekusi proses berat hingga input stabil. |

---

## 5. How (Workflow Detail)

Alur kerja state update end-to-end dalam arsitektur UDF berbasis `@Observable`:

```
┌────────────────────────────────────────────────────────────────────────┐
│ UI Interaction (e.g., Button Click / Form Typing)                      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Dispatch Action (Intent) -> store.send(.updateSearch(query))          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Business Logic Handler (@MainActor Store)                              │
│ - Cancel previous pending tasks (if debounced)                         │
│ - Trigger Side Effect (API Call, DB Query via Background Actor)       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         │ (Asynchronous boundary)                           │
         ▼                                                   │
┌──────────────────────────────────────────────┐             │
│ Background Actor (Worker)                    │             │
│ - URLSession / CoreData / SwiftData process  │             │
│ - Returns Result<DTO, Error>                 │             │
└──────────────────────┬───────────────────────┘             │
                       │                                     │
                       ▼                                     │
┌──────────────────────────────────────────────┐             │
│ Mutation Phase (Back to @MainActor)          │◄────────────┘
│ - Mutates store.state.results                │
│ - ObservationRegistrar.withMutation triggers │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Dependency Evaluation (SwiftUI Engine)                                 │
│ - Only Views tracking \.results are marked for invalidation           │
│ - Computes new View Body layout (Differential evaluation)              │
│ - Renders pixels to screen via Metal/CoreAnimation                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Sistem Pengumuman Gedung vs Notifikasi Pager Terarah

- **Combine (`ObservableObject`)**: Mirip interkom sentral seluruh gedung. Setiap kali sekretaris mengetik satu baris surat baru, interkom menyala berbunyi: *"Ada dokumen berubah di kantor!"*. Seluruh karyawan di gedung (semua Views) harus berhenti bekerja, mengangkat kepala, dan memeriksa apakah memo tersebut ditujukan untuk mereka, memboroskan fokus dan waktu.
- **Modern Observation (`@Observable`)**: Mirip sistem pager individu. Jika Anda hanya mendaftar untuk memo keuangan (*KeyPath `\.balance`*), pager Anda hanya bergetar saat angka keuangan berubah. Rekan Anda yang mendaftar memo logistik (*KeyPath `\.inventory`*) tidak terganggu sama sekali ketika saldo berubah.

```
                     TRADITIONAL COMBINE BROADCAST
                     
   [State Model] ────(objectWillChange)────► [Interkom Sentral]
                                                   │
                          ┌────────────────────────┴────────────────────────┐
                          ▼                                                 ▼
                   [View Keuangan]                                   [View Logistik]
                (Cek seluruh state)                               (Cek seluruh state)
                
               MODERN OBSERVATION (DIRECT PROPERTY BINDING)
               
   [State Model]
     ├── balance ──────────────────────(Direct Wire)──────────────► [View Keuangan]
     └── inventory ────────────────────(Direct Wire)──────────────► [View Logistik]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Transisi `@Observable` Bersih Tanpa Wrapper Tambahan

```swift
import SwiftUI
import Observation

@Observable
final class SimpleCounterState {
    var count: Int = 0
    var isEnabled: Bool = true
    
    func increment() {
        count += 1
    }
}

struct CounterDisplayView: View {
    // Tidak butuh @ObservedObject! Otomatis ter-track via KeyPath runtime access.
    var state: SimpleCounterState

    var body: some View {
        let _ = Self._printChanges() // Diagnostic printer
        VStack(spacing: 12) {
            Text("Count: \(state.count)")
                .font(.headline)
            Button("Increment") {
                state.increment()
            }
        }
    }
}

struct UnrelatedToggleView: View {
    var state: SimpleCounterState

    var body: some View {
        let _ = Self._printChanges()
        // View ini HANYA membaca `isEnabled`.
        // Mengubah `state.count` TIDAK AKAN pernah memicu render ulang view ini!
        Toggle("Active Status", isOn: Binding(
            get: { state.isEnabled },
            set: { state.isEnabled = $0 }
        ))
        .padding()
    }
}
```

### 7.2 Practical Example: Enterprise Reactive Pipeline (UDF + Swift Concurrency + Observation)

Di bawah ini adalah implementasi sistem pemantauan data finansial (Stock Ticker) menggunakan arsitektur UDF modular, lengkap dengan isolasi actor, debouncing, dan *cancellation safety*.

```swift
import SwiftUI
import Observation

// MARK: - Domain Models
struct StockQuote: Identifiable, Equatable, Sendable {
    let id: String
    let symbol: String
    let price: Decimal
    let changePercentage: Double
}

enum MarketStatus: Sendable {
    case open
    case closed
    case suspended
}

// MARK: - Actions
enum TickerAction: Sendable {
    case startMonitoring(symbol: String)
    case stopMonitoring
    case updateQuotes([StockQuote])
    case setMarketStatus(MarketStatus)
    case setError(String?)
}

// MARK: - State Container
@Observable
@MainActor
final class TickerStore {
    // UI-Exposed Properties
    private(set) var quotes: [StockQuote] = []
    private(set) var status: MarketStatus = .closed
    private(set) var errorMessage: String?
    private(set) var isLoading: Bool = false
    
    // Internal Service & Concurrency Management
    @ObservationIgnored private let marketService: MarketServiceProtocol
    @ObservationIgnored private var streamTask: Task<Void, Never>?

    init(marketService: MarketServiceProtocol = LiveMarketService()) {
        self.marketService = marketService
    }

    func send(_ action: TickerAction) {
        switch action {
        case .startMonitoring(let symbol):
            handleStartMonitoring(symbol: symbol)
        case .stopMonitoring:
            handleStopMonitoring()
        case .updateQuotes(let newQuotes):
            self.quotes = newQuotes
            self.isLoading = false
        case .setMarketStatus(let newStatus):
            self.status = newStatus
        case .setError(let message):
            self.errorMessage = message
            self.isLoading = false
        }
    }

    private func handleStartMonitoring(symbol: String) {
        isLoading = true
        errorMessage = nil
        streamTask?.cancel()
        
        streamTask = Task { [weak self, marketService] in
            do {
                let quoteStream = try await marketService.subscribeToTicks(symbol: symbol)
                for try await tick in quoteStream {
                    guard !Task.isCancelled else { break }
                    self?.send(.updateQuotes(tick))
                }
            } catch {
                guard !Task.isCancelled else { return }
                self?.send(.setError(error.localizedDescription))
            }
        }
    }

    private func handleStopMonitoring() {
        streamTask?.cancel()
        streamTask = nil
        isLoading = false
    }

    deinit {
        streamTask?.cancel()
    }
}

// MARK: - Service Abstraction (Actor Isolated Engine)
protocol MarketServiceProtocol: Sendable {
    func subscribeToTicks(symbol: String) async throws -> AsyncThrowingStream<[StockQuote], Error>
}

actor LiveMarketService: MarketServiceProtocol {
    func subscribeToTicks(symbol: String) async throws -> AsyncThrowingStream<[StockQuote], Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                var currentPrice: Decimal = 150.00
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: 1_000_000_000)
                    let variance = Decimal(Double.random(in: -2.0...2.5))
                    currentPrice += variance
                    let quote = StockQuote(
                        id: UUID().uuidString,
                        symbol: symbol.uppercased(),
                        price: currentPrice,
                        changePercentage: Double.random(in: -1.5...1.5)
                    )
                    continuation.yield([quote])
                }
                continuation.finish()
            }
            
            continuation.onTermination = { @Sendable _ in
                task.cancel()
            }
        }
    }
}

// MARK: - View Layer
struct EnterpriseTickerView: View {
    @State private var store = TickerStore()
    @State private var searchSymbol: String = "AAPL"

    var body: some View {
        NavigationStack {
            VStack {
                HStack {
                    TextField("Enter Symbol", text: $searchSymbol)
                        .textFieldStyle(.roundedBorder)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.characters)
                    
                    Button("Monitor") {
                        store.send(.startMonitoring(symbol: searchSymbol))
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding()

                if store.isLoading {
                    ProgressView("Connecting to live feed...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let error = store.errorMessage {
                    ContentUnavailableView(
                        "Error Occurred",
                        systemImage: "exclamationmark.triangle",
                        description: Text(error)
                    )
                } else {
                    List(store.quotes) { quote in
                        HStack {
                            Text(quote.symbol)
                                .font(.headline)
                            Spacer()
                            VStack(alignment: .trailing) {
                                Text("$\(quote.price, format: .number.precision(.fractionLength(2)))")
                                    .monospacedDigit()
                                    .bold()
                                Text("\(quote.changePercentage, format: .percent.precision(.fractionLength(2)))")
                                    .font(.caption)
                                    .foregroundStyle(quote.changePercentage >= 0 ? .green : .red)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Live Market Pipeline")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Stop") {
                        store.send(.stopMonitoring)
                    }
                }
            }
        }
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### 8.1 Skenario Permasalahan: Multi-Channel Order Book High-Frequency Invalidation

Sebuah aplikasi perbankan tier-1 memiliki layar ringkasan portofolio gabungan:
- Menangani 50-100 transaksi/detik dari WebSocket pipeline.
- Menampilkan grafik portofolio, riwayat pesanan (orders history), dan indikator koneksi jaringan.
- **Gejala Buruk**: Penggunaan CPU mencapai 85-100%, konsumsi baterai ekstrem, dan *frame drop* (stuttering) hingga 18 FPS saat scrolling daftar riwayat order.

### 8.2 Analisis Masalah (Root Cause Diagnostic)

```
[WebSocket Engine]
       │
       ▼  (100 payloads/sec)
[MainStore: ObservableObject] 
       │
       ▼  triggers objectWillChange
[RootPortfolioDashboardView] ── (Re-evaluates ENTIRE view hierarchy)
       ├── [MarketGraphView] ──── (Expensive Path Geometry Recalculated 100x/s) ❌
       ├── [NetworkStatusBadge] ─ (Re-rendered 100x/s despite unchanging state) ❌
       └── [OrderHistoryList] ─── (Diffing algorithms pegged CPU) ❌
```

### 8.3 Solusi Arsitektural Terapan

1. **Migrasi ke `@Observable` + Property Boundary Isolation**:
   Isolasi data stream rate-tinggi ke dalam sub-store terisolasi dan cegah propagasi level-root.
2. **Time-based Throttling / Batching Buffer**:
   Gunakan background actor buffer untuk mengumpulkan paket transaksi mikro per 100 milidetik (10Hz rendering ceiling, batas mata manusia), kemudian pancarkan secara *batched*.
3. **Penyembunyian Field Melalui `@ObservationIgnored`**:
   Properti pembantu seperti metadata perhitungan atau internal tracking timestamp dikecualikan dari observasi UI.

```swift
actor HighFrequencyBufferActor {
    private var buffer: [StockQuote] = []
    private var continuation: AsyncStream<[StockQuote]>.Continuation?
    
    func append(_ quote: StockQuote) {
        buffer.append(quote)
    }
    
    func flush() -> [StockQuote] {
        defer { buffer.removeAll(keepingCapacity: true) }
        return buffer
    }
}

@Observable
@MainActor
final class OptimizedPortfolioStore {
    // Hanya properti ini yang memicu redraw View yang membacanya
    private(set) var batchedQuotes: [StockQuote] = []
    private(set) var connectionLatency: Double = 0.0

    // Dikecualikan dari UI tracking graph untuk mengeliminasi siklus pengamatan internal
    @ObservationIgnored private var internalTickCount: UInt64 = 0
    @ObservationIgnored private var batchTask: Task<Void, Never>?
    @ObservationIgnored private let bufferActor = HighFrequencyBufferActor()

    func startIngestion() {
        batchTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 100_000_000) // 100ms Throttle Engine
                let newBatch = await bufferActor.flush()
                if !newBatch.isEmpty {
                    self.batchedQuotes = newBatch
                    self.internalTickCount += UInt64(newBatch.count)
                }
            }
        }
    }
    
    func receiveRawSocketPayload(_ quote: StockQuote) {
        Task {
            await bufferActor.append(quote)
        }
    }
    
    deinit {
        batchTask?.cancel()
    }
}
```

**Hasil Metrik:**
- CPU Utilization turun dari 92% ke 14%.
- Frame rate kembali stabil pada 60 FPS / 120 FPS ProMotion.
- Invalidation views turun drastis sebesar 89%.

---

## 9. Trade-offs

| Pendekatan | Keunggulan (Pros) | Kelemahan / Konsekuensi (Cons) | Biaya Performa & Skalabilitas |
| :--- | :--- | :--- | :--- |
| **Observation Framework (`@Observable`)** | - Fine-grained dynamic tracking.<br>- Sintaksis minimalis tanpa wrapper `@Published` atau `@ObservedObject`.<br>- Rendah alokasi heap dibandingkan Combine pipeline. | - Memerlukan baseline runtime iOS 17+.<br>- Deteksi mutasi tersembunyi jika mutating non-observable class reference di dalam properti. | Alokasi memori minimal. CPU overhead sangat rendah saat evaluasi read/write graph. |
| **Combine (`ObservableObject`)** | - Kompatibel dengan legacy iOS (iOS 13-16).<br>- Ekosistem operator data flow luas (`combineLatest`, `merge`, `retry`). | - Object-level invalidation memicu broad re-render.<br>- Alokasi memory publisher/subscriber pipeline yang besar. | CPU spike tinggi jika terjadi mutasi frekuensi tinggi pada single store besar. |
| **Pure Redux / The Composable Architecture (TCA)** | - Deterministik total.<br>- Time-travel debugging & state replication luar biasa akurat.<br>- Pengujian (unit testing) exhaustively modular. | - Kurva pembelajaran curam.<br>- Boilerplate kode masif.<br>- Overhead stack call bertingkat untuk action sederhana. | Kompilasi build time lebih lambat; slight latency overhead pada deep-tree state reducer transformations. |
| **Distributed Multi-Store UDF (Modern Native)** | - Ringan dan optimal secara native.<br>- Mudah dipelihara per fitur.<br>- Skalabilitas tim horizontal yang baik. | - Disiplin tim mutlak dibutuhkan agar tidak terjadi *cross-store circular dependency*. | Terbaik untuk aplikasi enterprise modern yang menargetkan throughput UI tinggi. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Mistake 1: Dynamic Invalidation Tracking Loss akibat Direct Struct Exposure
*Kesalahan*: Mengaburkan reference graph dengan membungkus property observable di dalam nested struct tanpa isolasi tepat, menyebabkan dynamic tracker kehilangan jejak dereferensi.

```swift
// SALAH: Mutasi pada inner struct tidak terlacak jika macro gagal menelusuri nested reference mutations
struct Configuration {
    var maxRetries: Int = 3
}

@Observable
final class BrokenSettingsStore {
    var config = Configuration() // Mutasi config.maxRetries sering memicu missed-updates jika dipass via binding primitif
}
```
*Solusi*: Terapkan `@Observable` secara modular pada class container atau buat explicit mutating boundary methods yang merefleksikan perubahan secara eksplisit pada root class.

### 10.2 Mistake 2: Retain Cycle pada Swift Concurrency Task Lifecycle
*Kesalahan*: Menangkap `self` secara kuat (*strong reference*) di dalam asynchronous task tak terbatas di dalam Store.

```swift
// SALAH: Retain cycle! Store tidak akan pernah di-deallocate jika task looping terus berjalan
@Observable
final class LeakingStore {
    func startPinging() {
        Task {
            while true {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                self.ping() // Strong capture of self
            }
        }
    }
}
```
*Solusi*: Gunakan capture list `[weak self]` dan periksa pembatalan task:

```swift
// BENAR: Safe Lifecycle Execution
@Observable
final class SafeStore {
    @ObservationIgnored private var pingTask: Task<Void, Never>?

    func startPinging() {
        pingTask?.cancel()
        pingTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard let self else { break }
                self.ping()
            }
        }
    }
}
```

### 10.3 Mistake 3: View Invalidation Storm Akibat Identitas List yang Tidak Stabil
*Kesalahan*: Menggunakan data stream yang men-generate `UUID()` baru untuk field `id` setiap kali payload masuk dari server, memaksa List menghancurkan dan membangun ulang seluruh cell views.

*Penyelesaian*: Gunakan business/server deterministic primary key sebagai ID implementasi `Identifiable` (e.g., `order_id`, `hash_id`).

### 10.4 Troubleshooting Guide: Mendeteksi Over-Rendering via Xcode
1. **Tambahkan Debug Printing**:
   Sematkan kode `let _ = Self._printChanges()` di awal `body` view untuk mengidentifikasi properti mana yang memaksa view melakukan re-evaluation di terminal debugger console.
2. **Gunakan Instruments (SwiftUI View Body)**:
   Jalankan Profiler (`Cmd + I`) -> Pilih template **SwiftUI**.
   Lihat diagram *View Body Evaluation Count*. Jika garis grafik meningkat secara curam ketika aplikasi tidak disentuh pengguna, identifikasi node View yang over-active dan periksa keypath observation registrar terkait.

---

## 11. Best Practices (Production Checklist)

- [ ] **Macro Migration**: Seluruh state container eksternal baru wajib menggunakan macro `@Observable` (hilangkan warisan `ObservableObject` / `@Published` untuk target deployment iOS 17+).
- [ ] **Thread Enforcement**: Store yang langsung berinteraksi dengan layout diberi atribut `@MainActor`.
- [ ] **Ignore Non-UI State**: Properti yang hanya digunakan untuk internal computation, network socket client, task holder, atau token caching harus dianotasi `@ObservationIgnored`.
- [ ] **Encapsulated Mutability**: Jadikan setter bersifat private (`private(set) var`) untuk menegakkan mutasi satu arah (*Unidirectional Data Flow*).
- [ ] **Decoupled Business Engines**: Proses transformasi data berat, komputasi kriptografi, parsing JSON masif, dan sinkronisasi disk dijalankan di dalam isolated Swift `actor`, bukan di dalam ViewModel/Store.
- [ ] **Safe Cancellation Lifecycle**: Batalkan semua `Task` yang tertunda di dalam blok `deinit` Store atau saat view trigger `onDisappear`.
- [ ] **Stable Identity Modeling**: Semua entitas koleksi di dalam list wajib memiliki id deterministik non-transient untuk menjaga integritas reconciliation layout.

---

## 12. Hands-on Practice

### Instruksi Penyiapan Direktori
Siapkan struktur file berikut di environment Anda:
```
hands-on/
└── m02/
    ├── AppState.swift
    ├── PaymentProcessingActor.swift
    ├── CheckoutStore.swift
    └── CheckoutView.swift
```

### File 1: `hands-on/m02/AppState.swift`
```swift
import Foundation

public enum PaymentStatus: Sendable, Equatable {
    case idle
    case authorizing
    case authenticated
    case completed(transactionId: String)
    case failed(reason: String)
}

public struct CartItem: Identifiable, Sendable, Equatable {
    public let id: UUID
    public let name: String
    public let price: Decimal
    
    public init(id: UUID = UUID(), name: String, price: Decimal) {
        self.id = id
        self.name = name
        self.price = price
    }
}
```

### File 2: `hands-on/m02/PaymentProcessingActor.swift`
```swift
import Foundation

public protocol PaymentProcessorProtocol: Sendable {
    func processPayment(amount: Decimal) async throws -> String
}

public actor PaymentProcessingActor: PaymentProcessorProtocol {
    public init() {}

    public func processPayment(amount: Decimal) async throws -> String {
        // Simulasi latensi jaringan authorization payment gateway
        try await Task.sleep(nanoseconds: 1_500_000_000)
        
        if amount > 10000 {
            throw PaymentProcessingError.limitExceeded
        }
        
        return "TXN-" + UUID().uuidString.prefix(8).uppercased()
    }
}

public enum PaymentProcessingError: LocalizedError, Sendable {
    case limitExceeded
    
    public var errorDescription: String? {
        switch self {
        case .limitExceeded:
            return "Transaction amount exceeds the permitted limit ($10,000)."
        }
    }
}
```

### File 3: `hands-on/m02/CheckoutStore.swift`
```swift
import SwiftUI
import Observation

public enum CheckoutAction: Sendable {
    case addItem(CartItem)
    case removeItem(IndexSet)
    case executeCheckout
    case reset
}

@Observable
@MainActor
public final class CheckoutStore {
    public private(set) var items: [CartItem] = []
    public private(set) var status: PaymentStatus = .idle
    
    @ObservationIgnored private let paymentProcessor: PaymentProcessorProtocol
    @ObservationIgnored private var ongoingCheckoutTask: Task<Void, Never>?

    public var totalAmount: Decimal {
        items.reduce(Decimal(0)) { $0 + $1.price }
    }

    public init(paymentProcessor: PaymentProcessorProtocol = PaymentProcessingActor()) {
        self.paymentProcessor = paymentProcessor
    }

    public func dispatch(_ action: CheckoutAction) {
        switch action {
        case .addItem(let item):
            items.append(item)
        case .removeItem(let offsets):
            items.remove(atOffsets: offsets)
        case .executeCheckout:
            performCheckout()
        case .reset:
            status = .idle
            items.removeAll()
        }
    }

    private func performCheckout() {
        guard status != .authorizing, !items.isEmpty else { return }
        
        let amount = totalAmount
        status = .authorizing
        
        ongoingCheckoutTask?.cancel()
        ongoingCheckoutTask = Task { [weak self, paymentProcessor] in
            do {
                let txnId = try await paymentProcessor.processPayment(amount: amount)
                guard !Task.isCancelled else { return }
                self?.status = .completed(transactionId: txnId)
            } catch {
                guard !Task.isCancelled else { return }
                self?.status = .failed(reason: error.localizedDescription)
            }
        }
    }
    
    deinit {
        ongoingCheckoutTask?.cancel()
    }
}
```

### File 4: `hands-on/m02/CheckoutView.swift`
```swift
import SwiftUI

public struct CheckoutView: View {
    @State private var store = CheckoutStore()

    public init() {}

    public var body: some View {
        NavigationStack {
            VStack {
                List {
                    Section("Order Items") {
                        ForEach(store.items) { item in
                            HStack {
                                Text(item.name)
                                Spacer()
                                Text("$\(item.price, format: .number.precision(.fractionLength(2)))")
                            }
                        }
                        .onDelete { offsets in
                            store.dispatch(.removeItem(offsets))
                        }
                    }

                    Section("Summary") {
                        HStack {
                            Text("Total")
                                .bold()
                            Spacer()
                            Text("$\(store.totalAmount, format: .number.precision(.fractionLength(2)))")
                                .bold()
                        }
                    }
                }

                StatusFooterView(status: store.status)

                VStack(spacing: 8) {
                    Button(action: {
                        let sampleItems = [
                            CartItem(name: "MacBook Pro", price: 2499.00),
                            CartItem(name: "USB-C Hub", price: 79.50),
                            CartItem(name: "Mechanical Keyboard", price: 150.00),
                            CartItem(name: "Enterprise Server Rack", price: 12000.00)
                        ]
                        if let randomItem = sampleItems.randomElement() {
                            store.dispatch(.addItem(randomItem))
                        }
                    }) {
                        Label("Add Random Item", systemImage: "plus")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .disabled(store.status == .authorizing)

                    Button(action: {
                        store.dispatch(.executeCheckout)
                    }) {
                        if store.status == .authorizing {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Pay Now")
                                .bold()
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(store.items.isEmpty || store.status == .authorizing ? Color.gray : Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                    .disabled(store.items.isEmpty || store.status == .authorizing)
                }
                .padding()
            }
            .navigationTitle("Checkout Pipeline")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Reset") {
                        store.dispatch(.reset)
                    }
                }
            }
        }
    }
}

// Subview yang mendemonstrasikan fine-grained tracking: hanya re-render saat status berubah
struct StatusFooterView: View {
    let status: PaymentStatus

    var body: some View {
        Group {
            switch status {
            case .idle:
                EmptyView()
            case .authorizing:
                Text("Authorizing transaction with secure gateway...")
                    .foregroundColor(.secondary)
            case .authenticated:
                Text("Authenticated. Finalizing settlement...")
                    .foregroundColor(.blue)
            case .completed(let txnId):
                Text("Payment Success! Trans ID: \(txnId)")
                    .foregroundColor(.green)
                    .bold()
            case .failed(let reason):
                Text("Failed: \(reason)")
                    .foregroundColor(.red)
                    .bold()
            }
        }
        .padding(.horizontal)
    }
}
```

---

## 13. Exercise

### Level Easy
Ubah `CounterDisplayView` pada seksi 7.1 untuk menambahkan fitur Reset. State reset harus membersihkan riwayat mutasi tanpa menggunakan property wrapper `@Binding`.
*Syarat*: Gunakan mutasi langsung melalui action function yang terdokumentasi di dalam Store.

### Level Medium
Buat sebuah custom pipeline debouncing input teks pencarian menggunakan `AsyncStream`. Store harus menampung teks mentah dari input pengguna, namun proses eksekusi filtering query hanya boleh dijalankan setelah pengguna berhenti mengetik selama 400 milidetik.
*Syarat*: Jangan gunakan Combine framework (`PassthroughSubject`, dll). Wajib memanfaatkan Swift Concurrency primitives natively.

### Level Hard
Implementasikan sebuah multi-actor transactional caching layer untuk Store yang menampilkan riwayat pesanan (orders history).
1. State Store (`@Observable`, `@MainActor`) menerima pesanan real-time.
2. Store mendelegasikan serialisasi data ke `DatabasePersistenceActor` di background.
3. Jika penulisan database gagal, UI State harus melakukan *rollback* secara otomatis ke snapshot sebelumnya dan memancarkan localized error state banner tanpa memblokir interaksi pengguna di form list.

---

## 14. Challenge

Rancang arsitektur sistem state engine untuk modul **Offline-First Synchronized Medical Charting System** dengan spesifikasi enterprise berikut:
1. **High Concurrency & Dynamic Collision**: Perawat dan dokter memperbarui metrik vital pasien (detak jantung, tekanan darah, catatan resep) secara bersamaan pada kondisi iPad offline di ruang isolasi.
2. **Conflict Resolution Strategy**: Ketika konektivitas kembali, sistem harus menjalankan *three-way state merge engine* (Local Timestamp vs Server Timestamp vs Vector Clock Rules) tanpa memicu crash thread, tanpa *race conditions*, dan tanpa visual frame drop pada input form yang sedang aktif diisi oleh tenaga medis.
3. **Observation Optimization**: View tree terdiri dari lebih dari 200 field observasi terpisah. Terapkan pemisahan state container sedemikian rupa sehingga pengeditan pada input field "Sistolik" tidak menyebabkan kalkulasi ulang layout pada grafik EKG di layar yang sama.
4. **Deliverables**: Buat rancangan struktur tipe state (State, Actions, Store Actors, Conflict Resolver Engine) serta diagram urutan data asinkron (*sequence diagram ASCII*). Buktikan tidak adanya retain cycle dan isolasi `@MainActor` terjamin secara komprehensif.

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic (5 Soal)
1. **Bagaimana `@Observable` melacak dependensi antara model dan View?**
   - A. Melalui anotasi `@Published` pada tiap properti model secara manual.
   - B. Melalui panggilan compile-time macro yang meregistrasikan akses keypath di dalam getter properti saat View body dievaluasi.
   - C. Menggunakan notification center broadcast pada setiap tick runloop thread utama.
   - D. Dengan melakukan refleksi runtime (mirroring) seluruh properti saat object diinisialisasi.

2. **Apa fungsi dari anotasi `@ObservationIgnored`?**
   - A. Mengubah properti menjadi read-only bagi SwiftUI views.
   - B. Mengeluarkan properti dari dynamic tracking registrar sehingga mutasinya tidak memicu evaluasi view body.
   - C. Memaksa properti dijalankan di background thread secara otomatis.
   - D. Menghapus properti dari memori saat aplikasi memasuki mode background.

3. **Mengapa `ObservableObject` bawaan Combine rentan menyebabkan penurunan performa rendering pada aplikasi berskala masif?**
   - A. Karena tidak mendukung tipe data primitive Swift seperti `Int` atau `String`.
   - B. Karena `objectWillChange` memancarkan sinyal invalidasi pada level objek, memaksa semua subscriber view mengevaluasi ulang body meskipun data yang dibaca tidak berubah.
   - C. Karena Combine tidak dapat dijalankan di perangkat dengan RAM di bawah 6GB.
   - D. Karena `ObservableObject` selalu membocorkan memory retain cycles secara otomatis.

4. **Kapan sebaiknya sebuah Store/ViewModel dianotasi dengan `@MainActor`?**
   - A. Hanya saat Store tersebut berisi lebih dari 10 properti.
   - B. Setiap kali Store memiliki properti yang nilainya mengontrol tampilan UI SwiftUI secara langsung.
   - C. Hanya jika aplikasi dijalankan pada sistem operasi watchOS.
   - D. Tidak pernah, karena SwiftUI secara otomatis mengisolasi semua kelas ke Main Thread.

5. **Apa yang terjadi jika Anda memodifikasi properti `@Observable` yang diobservasi oleh View dari background thread tanpa isolasi MainActor?**
   - A. Kompiler Swift langsung menolak kompilasi (compile error mutlak).
   - B. Perubahan state tidak tersimpan di memori heap.
   - C. Terjadi potensi data race pada pipeline rendering UI yang memicu peringatan runtime Xcode (purple warning) atau graphical glitches.
   - D. Aplikasi secara otomatis menduplikasi View hierarchy ke background actor.

### 15.2 Pertanyaan Intermediate (5 Soal)
6. **Perhatikan cuplikan kode berikut:**
   ```swift
   @Observable
   final class UserProfileStore {
       var username: String = "Alice"
       var avatarURL: URL?
   }
   struct HeaderView: View {
       var store: UserProfileStore
       var body: some View {
           Text(store.username)
       }
   }
   ```
   *Jika `store.avatarURL` diubah dari nil menjadi sebuah link foto baru, apakah `HeaderView` akan dievaluasi ulang (re-rendered)? Jelaskan mekanismenya.*
   - A. Ya, karena setiap perubahan properti kelas akan membatalkan seluruh hierarchy tree.
   - B. Tidak, karena `HeaderView` hanya meregistrasikan akses pada keypath `\.username` saat evaluasi body; keypath `\.avatarURL` tidak ada dalam daftar dependensi View tersebut.
   - C. Ya, karena HeaderView tidak menggunakan property wrapper `@State`.
   - D. Tergantung pada ukuran dimensi foto dari URL tersebut.

7. **Bagaimana cara mencegah kebocoran memori (*retain cycle*) ketika memanggil fungsi asinkron panjang di dalam Store berbasis `@Observable`?**
   - A. Menggunakan kata kunci `inout` pada parameter Store.
   - B. Menyematkan capture list `[weak self]` di dalam closure `Task` dan melakukan pengecekan status pembatalan `Task.isCancelled`.
   - C. Menghapus destructor `deinit` dari definisi kelas Store.
   - D. Mengubah kelas Store menjadi `struct`.

8. **Mengapa penggunaan `UUID()` langsung pada inline loop `ForEach(store.items, id: \.uuid)` dianggap sebagai anti-pattern performa di SwiftUI?**
   - A. Karena tipe `UUID` tidak memenuhi syarat protokol `Hashable`.
   - B. Karena generator UUID memperlambat alokasi memori stack secara signifikan.
   - C. Karena menghasilkan identitas yang selalu berubah pada setiap siklus evaluasi, merusak mekanisme identitas view dan memicu alokasi serta re-render ulang elemen list yang tidak perlu.
   - D. Karena kompilator Swift membatasi batas penggunaan UUID maksimal 100 instance per detik.

9. **Apa perbedaan mendasar antara implementasi `@State` untuk struct primitif vs `@State` yang menginisialisasi instance kelas `@Observable` pada iOS 17+?**
   - A. Tidak ada perbedaan, keduanya disimpan langsung di stack memory frame View.
   - B. Pada kelas `@Observable`, `@State` mengelola siklus hidup (ownership lifecycle) dari instance referensi tersebut agar tidak terbuat ulang saat struct View diinisialisasi ulang oleh parent.
   - C. `@State` tidak dapat digunakan pada kelas `@Observable`.
   - D. `@State` pada struct memerlukan alokasi thread actor khusus sedangkan pada class tidak.

10. **Bagaimana cara menangani *high-frequency stream* (misal: 120 update/detik dari sensor accelerometer) agar UI tidak mengalami freeze/stutter?**
    - A. Memasang `DispatchQueue.main.sync` pada setiap pembaruan data sensor.
    - B. Mengumpulkan (batching/buffering) data pada background actor dan hanya memancarkan snapshot state terkonsolidasi ke MainActor Store pada interval frekuensi yang terkendali (misal: 10-30Hz).
    - C. Meningkatkan priority priority thread utama menjadi *real-time audio priority*.
    - D. Mengubah seluruh View menjadi representasi UIKit melalui `UIViewRepresentable`.

### 15.3 Skenario Kasus Produksi (3 Soal)

11. **Skenario 1**: Tim Anda memigrasikan aplikasi trading berskala besar dari arsitektur lama berbasis `ObservableObject` ke modern `@Observable`. Setelah migrasi, beberapa View kompleks yang bergantung pada `@EnvironmentObject` mengalami compile error atau runtime crash: *"Cannot find object in environment"*. Apa akar permasalahan struktural ini dan bagaimana strategi migrasi yang benar untuk environment injection?
12. **Skenario 2**: Profiler Instruments menunjukkan bahwa sebuah View body dievaluasi ulang 60 kali per detik padahal data yang ditampilkan statis. Setelah diinspeksi, View tersebut membaca properti computed `var formattedTimestamp: String { Date().formatted() }` di dalam `@Observable` store. Mengapa hal ini memicu siklus invalidasi berkelanjutan dan bagaimana solusinya?
13. **Skenario 3**: Sebuah aplikasi e-commerce enterprise memiliki keranjang belanja (`CartStore`). Saat pengguna menekan tombol "Checkout", koneksi jaringan fluktuatif menyebabkan pengguna mengetuk tombol tersebut 4 kali berturut-turut. Hasilnya, 2 transaksi terduplikasi masuk ke payment gateway. Rancang penanganan arsitektural di level State Machine dan Concurrency Task Management untuk mengeliminasi *double-submission race condition* ini.

---

### Kunci Jawaban & Panduan Evaluasi

#### Kunci Pilihan Ganda:
1. **B** – Macro menyisipkan tracking code melalui `ObservationRegistrar.access` saat read operation.
2. **B** – `@ObservationIgnored` mengecualikan properti dari observasi View.
3. **B** – `objectWillChange` bekerja di level instance objek secara granularitas kasar.
4. **B** – Properti state UI harus diisolasi ke MainActor untuk menjamin eksekusi render yang aman tanpa race condition.
5. **C** – Mutasi off-main-thread pada properti observasi memicu thread sanitization error dan layout synchronization glitches.
6. **B** – Tracking observation modern bekerja berbasis keypath akses yang dibaca secara aktual di dalam body view.
7. **B** – Menghindari strong reference retain loop antara context Task asinkron dan instance kelas pemilik.
8. **C** – Identitas acak baru pada tiap siklus render menghancurkan stabilitas diffing engine SwiftUI.
9. **B** – `@State` menjamin kestabilan lifecycle heap instance objek kelas `@Observable` di balik siklus pembuatan struct View.
10. **B** – Batching/throttling pada background actor adalah teknik esensial untuk membatasi UI render refresh ceiling.

#### Panduan Jawaban Skenario Produksi:
11. **Solusi Skenario 1**:
    - *Akar Masalah*: `@EnvironmentObject` memerlukan protokol `ObservableObject`. Kelas `@Observable` yang baru tidak mengadopsi protokol tersebut, sehingga injeksi via `.environmentObject(...)` gagal.
    - *Solusi*: Migrasikan modifier injeksi menjadi `.environment(store)` (tanpa kata 'Object'). Pada target View, konsumsi data menggunakan anotasi `@Environment(UserProfileStore.self) var store` langsung, yang secara penuh didukung oleh Observation engine.
12. **Solusi Skenario 2**:
    - *Akar Masalah*: Computed property yang memanggil state non-deterministik seperti `Date()` menghasilkan nilai yang selalu berubah secara terus-menerus jika ada dependency clock atau trigger re-evaluasi internal, namun yang lebih fatal: jika computed property tersebut memanggil getter properti lain yang terus termutasi di loop lain, tracking registrar memicu infinite cascade invalidation.
    - *Solusi*: Ubah computed property menjadi *stored property*. Perbarui nilai `formattedTimestamp` hanya ketika event perubahan data spesifik terjadi (event-driven update), bukan dihitung secara dinamis saat getter dibaca oleh view layout.
13. **Solusi Skenario 3**:
    - *Solusi Arsitektural*: Terapkan State Machine eksplisit (`idle`, `authorizing`, `completed`, `failed`). Pada method `performCheckout()`, baris pertama wajib melakukan pengecekan *guard condition*: `guard status != .authorizing else { return }`. Seketika sebelum Task asinkron dimulai, ubah `status = .authorizing`. Amankan task holder dengan membatalkan task sebelumnya (`checkoutTask?.cancel()`) atau mengabaikan aksi duplikat selama *ongoing state* aktif, serta kunci tombol (disable) di layer UI berdasarkan kondisi `store.status == .authorizing`.

---

## 16. Summary

- Framework **Observation** modern (`@Observable`) menggeser paradigma manajemen state SwiftUI dari *object-level broadcast* (Combine) menuju **fine-grained keypath-level dynamic tracking**.
- SwiftUI secara otomatis mendeteksi properti mana yang dibaca oleh View body, mengeliminasi evaluasi render ulang (*wasteful view invalidations*) pada komponen UI yang tidak berkepentingan secara langsung.
- Integrasi **Swift Concurrency** (`Actors`, `Task`, `@MainActor`) memberikan pemisahan tanggung jawab yang kokoh: kalkulasi berat dan sinkronisasi data stream terjadi di latar belakang (*background actor*), sedangkan UI State Store terisolasi secara aman di thread utama (*main thread*).
- Arsitektur produksi berskala enterprise menuntut implementasi **Unidirectional Data Flow (UDF)** yang ketat: View memicu Action/Intent $\rightarrow$ Store memproses via Services $\rightarrow$ State Snapshot bermutasi secara atomik $\rightarrow$ View melakukan rendering deklaratif secara efisien.