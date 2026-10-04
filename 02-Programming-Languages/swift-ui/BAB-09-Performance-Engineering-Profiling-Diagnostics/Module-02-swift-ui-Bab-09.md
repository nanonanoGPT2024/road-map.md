# BAB 09: Performance Engineering, Profiling & Diagnostics
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Runtime SwiftUI Engine:** Menjelaskan secara presisi interaksi runtime antara *AttributeGraph*, dependensi grafis deklaratif, *Layout Engine*, dan subsistem *Render Server* (Core Animation).
- **Mendeteksi dan Memitigasi Render Bottleneck:** Mengidentifikasi dan mengeliminasi *Dynamic Property churn*, *View invalidation cascading*, dan *Hitch Time* (Input/Display Hitches) pada scroll view berfrekuensi tinggi.
- **Menguasai Memory Lifecycle & Leak Diagnostics:** Melacak *unmanaged retain cycles* pada closures, lifecycle modifiers (`.task`, `.onReceive`), serta memory bloat melalui Xcode Memory Graph dan Instruments Allocations.
- **Mendesain Arsitektur UI Berkinerja Tinggi:** Mengimplementasikan pola pemisahan *State Mutation* versus *View Consumption* menggunakan Swift 5.9+ `@Observable` macro atau custom slicing untuk mencegah evaluasi `body` yang tidak perlu.
- **Memanfaatkan Metal/Canvas untuk Beban Grafis Ekstrem:** Mengintegrasikan `Canvas`, `TimelineView`, dan `.drawingGroup()` untuk offloading UI graph berdensitas tinggi ke GPU pipelines.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- Pengetahuan mendalam tentang Swift Type System, Value Semantics, dan Existential Types.
- Prinsip dasar Concurrency Swift (`async`/`await`, `Task`, `@MainActor`, `Sendable`).
- Konsep dasar SwiftUI State Management: `@State`, `@Binding`, `@ObservedObject`, `@StateObject`, dan `@Observable`.
- Pengalaman dasar menggunakan Xcode Instruments (Time Profiler, Allocations).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Siklus Hidup dan Runtime SwiftUI: AttributeGraph & Render Pipeline
SwiftUI **bukan** sebuah *wrapper imperatif tipis* di atas UIKit/AppKit. Di balik layar, framework ini mengandalkan mesin reaktif berbasis grafis dependensi independen yang disebut **AttributeGraph** (framework internal C++ private: `AttributeGraph.framework`).

```
+----------------------------------------------------------------------+
|                           APP PROCESS                                |
|                                                                      |
|  [ View Declarations (Structs) ]                                     |
|               |                                                      |
|               v                                                      |
|  [ AttributeGraph Generation / Invalidation ]                        |
|        - Dynamic Property Graph (Sources of Truth: @State, @Binding) |
|        - Structural Identity vs Explicit Identity                    |
|        - Body Invalidation & Diffing Pass                            |
|               |                                                      |
|               v                                                      |
|  [ Layout Pass (ProposedSize -> ReportSize -> Geometry Placement) ]  |
|               |                                                      |
|               v                                                      |
|  [ DisplayList Encoding ]                                            |
|        - Primitives, Transforms, Opacities, Clips                    |
+---------------+------------------------------------------------------+
                | (IPC / Mach Message / Shared Memory)
                v
+---------------+------------------------------------------------------+
|                        RENDER SERVER (Backboard)                     |
|                                                                      |
|  [ Core Animation Pipeline ]                                         |
|        - Decode DisplayList into CA::Render Trees                    |
|        - Draw Calls to Metal Pipeline                                |
|        - VSync Synchronization (120Hz ProMotion = 8.33ms deadline)   |
|               |                                                      |
|               v                                                      |
|  [ Frame Buffer -> Display Panel ]                                   |
+----------------------------------------------------------------------+
```

#### Komponen Utama Pipeline:
1. **AttributeGraph:**
   Sebuah Directed Acyclic Graph (DAG) di mana setiap simpul merepresentasikan atribut nilai komputasi (contoh: frame ukuran view, warna latar, hasil evaluasi `body`). Ketika sebuah sumber data (*Source of Truth*) bermutasi, AttributeGraph menandai simpul-simpul terdampak sebagai *dirty* dan menjadwalkan pass evaluasi ulang (*re-evaluation*).
2. **DisplayList:**
   Representasi intermediate serializable dari apa yang harus digambar. SwiftUI tidak membuat `UIView` atau `CALayer` untuk setiap subview; ia menyusun deskripsi primitif vektor dan layer ke dalam `DisplayList`.
3. **Render Server (Commit Loop):**
   Aplikasi Anda bertindak sebagai *client*. Pada akhir runloop pass, modifikasi direkam dan di-encode ke `CATransaction`, lalu dikirimkan melalui inter-process communication (IPC) ke Render Server daemon. Render Server inilah yang mengeksekusi instruksi grafis riil ke GPU via Metal.

#### 3.2 View Identity: Structural Identity vs Explicit Identity
Kunci optimasi performa SwiftUI terletak pada bagaimana framework memahami apakah sebuah View merepresentasikan elemen UI yang sama atau entitas baru:
- **Structural Identity:** SwiftUI menggunakan struktur pohon deklaratif kode Anda (`_ConditionalContent<TrueContent, FalseContent>`) untuk menentukan identitas. Percabangan `if-else` mengubah struktur tipe graf, memicu *deallocation* simpul AttributeGraph lama dan *allocation* simpul baru.
- **Explicit Identity:** Menggunakan identifier eksplisit via modifier `.id(...)` atau protokol `Identifiable` pada `ForEach`. 

*Dampak Performa:* Jika identifier explicit berubah secara tak terduga (misalnya menggunakan `UUID()` baru saat init), SwiftUI menghancurkan seluruh state internal, membatalkan animasi, dan memicu reflow layout dari root sub-tree.

---

### 4. Why & What

| Pertanyaan | Analisis Teknis |
| :--- | :--- |
| **Why does it matter?** | Pada layar ProMotion 120Hz (iPhone Pro, iPad Pro), batas waktu pemrosesan satu frame (*frame budget*) adalah **8.33 milidetik** (atau 16.67ms pada 60Hz). Terlambat melewati batas ini memicu **Hitch** (frame drop). Hitch berdurasi panjang menyebabkan *perceived lag*, *thermal throttling*, dan pemborosan konsumsi baterai akibat CPU/GPU racing. |
| **What is dynamic property churn?** | Fenomena di mana properti penampung state (seperti `@State`, `@ObservedObject`) memicu `View.body` execution berantai karena dependensi data yang terlalu luas (*over-subscription*), meskipun data aktual yang dirender di layar tidak berubah. |
| **What is a Commit Hitch vs Render Hitch?** | **Commit Hitch:** App process memakan waktu > budget pada Main Thread sebelum mengirim data ke Render Server (penyebab: eksekusi `body` berat, kalkulasi layout kompleks, blocking I/O di main thread).<br>**Render Hitch:** Render server kehabisan waktu saat rasterisasi atau GPU draw call terlampau kompleks (penyebab: off-screen passes, excessive masking, complex shadows, unflattened layers). |

---

### 5. How: Alur Kerja Diagnostik & Optimasi Performa

Langkah terstruktur rekayasa performa UI di lingkungan enterprise:

```
[1. Metric Baselining] 
   └── Ukur Frame Hitch Rate & Time to Interactive (TTI) via MetricKit / XCTest Metrics
[2. Profiling via Instruments]
   ├── SwiftUI Template: Analisis Body Invalidation counts & Graph Churn
   ├── Time Profiler: Identifikasi CPU hotspots di Main Thread
   └── Allocations: Periksa View Struct instantiations & Heap allocations
[3. Isolate Problem Domain]
   ├── Apakah Commit Phase? (Body execution / Structural Identity changes)
   └── Apakah Render Phase? (Offscreen rendering / Layer blending / Complex visual effects)
[4. Architectural Refactoring]
   ├── Flatten view hierarchy
   ├── Slice State (Pemisahan Observable granularity)
   └── Ganti Stack berlebih dengan Canvas/Metal atau Lazy layout engines
[5. Verification & Regression Testing]
   └── Automasi XCTMetric test dalam CI/CD pipeline
```

---

### 6. Analogi & Diagram ASCII

#### Analogi: Pabrik Percetakan Brosur Dinamis
Bayangkan SwiftUI adalah jalur perakitan percetakan:
- **State** adalah dokumen naskah mentah.
- **AttributeGraph** adalah mandor yang membandingkan naskah lama dan baru: ia menandai hanya paragraf yang berubah tinta.
- **Layout & DisplayList** adalah cetakan pelat stensil.
- **Render Server** adalah mesin press berkecepatan tinggi (120 RPM / 120Hz).

Jika Anda mengubah font satu kata menggunakan percabangan tipe `if-else` (Structural Identity drop), mandor membuang seluruh cetakan pelat stensil dan memesan mesin berhenti mencetak untuk re-alignment. Namun, jika Anda hanya memperbarui teks pada slot pelat yang sama (Preserved Identity), mesin mencetak tanpa mengurangi kecepatan sedetik pun.

#### AttributeGraph Dependency & Propagation
```
State Mutation: User balance updated ($100 -> $105)
                   │
                   ▼
       [ Observable Store: Balance ]
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
 [ AccountHeaderView ]  [ HistoryListView ]
 (Depends on Balance)   (Does NOT depend on Balance)
         │                   │
         ▼                   ▼
 Body Invalidated       Skipped (0 cost)
         │
         ▼
 AttributeGraph Diff
         │
         ▼
 DisplayList Updated
         │
         ▼
 Render Server Commit
```

---

### 7. Simple Example & Practical Example

#### 7.1 Anti-Pattern vs Pattern: Granularity & Invalidation

##### Buruk (Over-invalidation & Memory Churn):
```swift
// ANTI-PATTERN: Mengamati monolith view model secara luas
final class BadFeedViewModel: ObservableObject {
    @Published var items: [String] = []
    @Published var scrollOffset: CGFloat = 0.0 // Berubah setiap 8ms saat scroll
    @Published var unreadNotificationCount: Int = 0
}

struct BadFeedView: View {
    @ObservedObject var viewModel: BadFeedViewModel

    var body: some View {
        // PERINGATAN: Seluruh body FeedView ter-evaluasi ulang setiap pixel scrollOffset berubah!
        VStack {
            Text("Unread: \(viewModel.unreadNotificationCount)")
            List(viewModel.items, id: \.self) { item in
                Text(item)
            }
        }
    }
}
```

##### Optimal (Production Grade: State Slicing & Observation Macro):
```swift
import SwiftUI
import Observation

// PATTERN: iOS 17+ Observation Engine (Field-level tracking)
@Observable
final class OptimizedFeedViewModel {
    var items: [FeedItem] = []
    var scrollOffset: CGFloat = 0.0
    var unreadNotificationCount: Int = 0

    struct FeedItem: Identifiable, Hashable, Sendable {
        let id: UUID
        let title: String
        let timestamp: Date
    }
}

// Subview hanya mengamati property yang diakses di dalam body-nya
struct HeaderBadgeView: View {
    // Inject referensi instance model
    var viewModel: OptimizedFeedViewModel

    var body: some View {
        // SwiftUI runtime HANYA meregistrasi dependensi ke `unreadNotificationCount`.
        // Mutasi `scrollOffset` TIDAK AKAN mengevaluasi ulang body ini!
        let _ = Self._printChanges() // Diagnostic helper
        Text("Unread: \(viewModel.unreadNotificationCount)")
            .font(.caption.bold())
            .padding(4)
            .background(.red)
            .clipShape(Capsule())
    }
}

struct OptimizedFeedView: View {
    @State private var viewModel = OptimizedFeedViewModel()

    var body: some View {
        VStack(spacing: 0) {
            HeaderBadgeView(viewModel: viewModel)
            
            // Menggunakan explicit scroll tracking yang terisolir
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(viewModel.items) { item in
                        ItemRow(item: item)
                    }
                }
            }
        }
    }
}

struct ItemRow: View, Equatable {
    let item: OptimizedFeedViewModel.FeedItem

    // Implementasi manual Equatable untuk proteksi rendering redundan
    static func == (lhs: ItemRow, rhs: ItemRow) -> Bool {
        lhs.item.id == rhs.item.id && lhs.item.title == rhs.item.title
    }

    var body: some View {
        Text(item.title)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .background(Color(uiColor: .secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
```

---

### 8. Real-World Case Study: Enterprise High-Frequency Ticker Feed

#### Latar Belakang Masalah
Aplikasi trading fintech enterprise menampilkan daftar 200 instrumen aset crypto/forex secara real-time via WebSocket. Data harga bermutasi 20–50 kali per detik di seluruh portofolio. Implementasi awal menghasilkan CPU utilization > 85%, baterai panas (thermal throttling), dan scroll hitch rate mencapai **18.4%** pada iPhone 15 Pro (120Hz).

#### Akar Masalah (Root Cause Profiling)
1. **Model Monolitik:** Tiap pembaruan WebSocket memicu mutasi `@Published var ticks: [String: Price]` pada Main Actor.
2. **View Instantiation Cost:** Inisialisasi struct baris baru secara terus-menerus memicu auto-diffing pada elemen yang berada di luar viewport.
3. **Overdraw & Blurring:** Row item menggunakan modifier multi-layered shadows dan continuous blur visual effects.

#### Solusi Arsitektural Terapan
1. **Engine Buffering/Throttling:** WebSocket mengalirkan paket ke Background Actor, di-batch setiap 100ms via `AsyncAlgorithms.throttle`.
2. **Slicing Graph via `Canvas` Engine:** Menggambar grafik chart mikro (sparkline) langsung menggunakan render pass instan GPU via `Canvas`, alih-alih membangun pohon ratusan elemen `Path`.
3. **Decoupled Observable Nodes:** Setiap baris mendaftar ke node data spesifiknya sendiri.

#### Implementasi Kode:

```swift
import SwiftUI
import Observation
import OSLog

private let logger = Logger(subsystem: "com.enterprise.fintech", category: "Performance")

// MARK: - State Architecture
@Observable
final class MarketInstrumentNode: Identifiable {
    let id: String
    let symbol: String
    var currentPrice: Double
    var priceHistory: [Double] // Fixed 30 points

    init(id: String, symbol: String, initialPrice: Double) {
        self.id = id
        self.symbol = symbol
        self.currentPrice = initialPrice
        self.priceHistory = Array(repeating: initialPrice, count: 30)
    }

    @MainActor
    func update(newPrice: Double) {
        guard newPrice != currentPrice else { return }
        self.currentPrice = newPrice
        self.priceHistory.removeFirst()
        self.priceHistory.append(newPrice)
    }
}

// MARK: - Ultra-Low Overhead Sparkline (Metal Canvas)
struct SparklineCanvas: View {
    let history: [Double]
    let lineColor: Color

    var body: some View {
        Canvas { context, size in
            guard history.count > 1 else { return }
            
            let minVal = history.min() ?? 0.0
            let maxVal = history.max() ?? 1.0
            let delta = (maxVal - minVal) == 0 ? 1.0 : (maxVal - minVal)
            
            let stepX = size.width / CGFloat(history.count - 1)
            var path = Path()
            
            for (index, val) in history.enumerated() {
                let normY = 1.0 - CGFloat((val - minVal) / delta)
                let point = CGPoint(x: CGFloat(index) * stepX, y: normY * size.height)
                
                if index == 0 {
                    path.move(to: point)
                } else {
                    path.addLine(to: point)
                }
            }
            
            context.stroke(path, with: .color(lineColor), lineWidth: 1.5)
        }
        .frame(width: 80, height: 28)
        // Hindari re-drawing canvas jika viewport belum terlihat
        .drawingGroup() 
    }
}

// MARK: - High Performance Row Cell
struct InstrumentRow: View {
    // Model di-passing langsung; Observation framework hanya mengikat 
    // atribut 'currentPrice' & 'priceHistory' di row ini secara isolated.
    var instrument: MarketInstrumentNode

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(instrument.symbol)
                    .font(.system(.body, design: .monospaced, weight: .bold))
                Text("Realtime Stream")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            
            Spacer()
            
            SparklineCanvas(
                history: instrument.priceHistory,
                lineColor: instrument.currentPrice >= (instrument.priceHistory.first ?? 0) ? .green : .red
            )
            
            Text(instrument.currentPrice, format: .currency(code: "USD"))
                .font(.system(.callout, design: .monospaced, weight: .semibold))
                .frame(minWidth: 90, alignment: .trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }
}

// MARK: - Root List Screen
struct MarketListView: View {
    @State private var instruments: [MarketInstrumentNode] = []

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(instruments) { instrument in
                        InstrumentRow(instrument: instrument)
                        Divider()
                    }
                }
            }
            .navigationTitle("Global Feeds")
            .task {
                setupBootstrapData()
            }
        }
    }

    private func setupBootstrapData() {
        instruments = (1...150).map { i in
            MarketInstrumentNode(id: "SYM-\(i)", symbol: "TICK-\(i)", initialPrice: Double.random(in: 100...2000))
        }
    }
}
```

---

### 9. Trade-offs: Analisis Matriks Rekayasa

| Pendekatan Arsitektur | Keuntungan | Kerugian / Trade-off | Dampak Resource |
| :--- | :--- | :--- | :--- |
| **`Canvas` / Metal Rendering** | Draw calls sangat minim, zero UIView/Layer instantiation, 120 FPS flat. | Hilangnya aksesibilitas bawaan (VoiceOver harus dibuat manual), tidak ada event-handling per elemen. | Mengurangi memori CPU hingga 70%, sedikit menaikkan beban komputasi GPU shader. |
| **Pemisahan `@Observable` granular** | Invalidation body strictly scoped ke leaf views. Tidak ada re-render global. | Kompleksitas injeksi state dependency; boilerplates manajemen life-cycle jika sub-node terhubung ke service eksternal. | Mengurangi commit hitch rate secara drastis (Main Thread CPU turun drastis). |
| **Manual `Equatable` View Modifiers** | Mencegah SwiftUI menyusuri sub-tree view yang tidak berubah. | Developer rawan membuat bug: state berubah tapi tampilan UI *stale* karena implementasi `==` mengabaikan property baru. | Mengorbankan developer velocity demi komputasi CPU render pipeline. |
| **`.drawingGroup()` Flattening** | Menggabungkan seluruh view tree ke dalam single Metal off-screen surface. | Komposit off-screen memakan memori alokasi frame buffer besar; berbahaya untuk hierarki text rendering kompleks. | Meningkatkan memori footprint; kurangi hitch jika digunakan tepat sasaran (kompleks grafis). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Inisialisasi Objek Berat di Dalam View Initializer
*Salah:*
```swift
struct ProblematicView: View {
    @StateObject private var viewModel: DataServiceViewModel

    init(endpoint: String) {
        // CRITICAL BUG: View initializer dieksekusi berkali-kali saat parent di-render!
        // Membuat instance baru terus menerus memicu alokasi heap yang masif.
        _viewModel = StateObject(wrappedValue: DataServiceViewModel(endpoint: endpoint))
    }
}
```
*Solusi:*
Lakukan delegasi passing dependency via `.task(id:)` atau Dependency Container yang terdaftar di luar lifecycle init View deklaratif.

#### 2. Identity Collision dan UUID() Baru di Render Loop
*Salah:*
```swift
ForEach(items, id: \.self) { item in
    // Setiap body re-evaluate, subview diberi id acak baru!
    ItemView(data: item)
        .id(UUID()) // Merusak cache AttributeGraph, mematikan transisi animasi
}
```
*Solusi:*
Gunakan property id yang stabil dan persisten (contoh: Primary Key database UUID dari payload backend).

#### 3. Diagnostic Helper: Menemukan Sumber Invalidation
Gunakan built-in compiler internal reflection method di dalam body struct Anda saat profiling:
```swift
var body: some View {
    #if DEBUG
    let _ = Self._printChanges() // Mencetak properti persis apa yang memicu re-render
    #endif
    VStack {
        // Konten UI
    }
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Stabilkan Struktur Identitas:** Hindari percabangan `if-else` untuk menyembunyikan/menampilkan layout visual statis; gunakan modifier `.opacity()` atau `.hidden()` jika struktur subview identik.
- [ ] **Isolasi MainActor Work:** Pastikan parsing JSON, pengurutan koleksi (`.sorted()`), dan pemrosesan gambar dijalankan di Swift Concurrency `Task.detached` atau non-MainActor actor.
- [ ] **Gunakan Primitive Sizing yang Pasti:** Tetapkan eksplisit `.frame(width:height:)` pada placeholder gambar remote untuk mencegah *layout thrashing* saat gambar selesai diunduh.
- [ ] **Optimalkan Sheet dan Navigation Destination:** Jangan letakkan modifier `.sheet(item:)` di dalam tiap elemen `ForEach`. Deklarasikan **satu** sheet modifier di level container/parent.
- [ ] **Minimalisir Layer Modifiers Berlebih:** Rantai modifier seperti `.shadow()`, `.clipShape()`, `.blendMode()`, dan `.blur()` memaksa Render Server melakukan off-screen buffer rendering pass. Pangkas atau ganti dengan pre-rendered asset.
- [ ] **Audit Retain Cycle pada Modifier Lifecycle:** Pastikan closure di dalam modifier `.onReceive` atau capturing di `.task` tidak menahan referensi *strong self* ke reference-type wrapper.

---

### 12. Hands-on Practice: Diagnostik & Refaktorisasi Lag

Studi praktikum ini mensimulasikan kasus nyata: Memperbaiki daftar transaksi e-commerce yang mengalami frame drop parah saat di-scroll.

#### Struktur Direktori:
Simpan file latihan di: `hands-on/m02/`
- `hands-on/m02/TransactionFeedBaseline.swift` (Unoptimized)
- `hands-on/m02/TransactionFeedOptimized.swift` (Refactored)

#### Step 1: Baseline Code (Unoptimized & Laggy)
Letakkan file ini pada `hands-on/m02/TransactionFeedBaseline.swift`:

```swift
import SwiftUI

struct UnoptimizedTransactionItem: Identifiable {
    let id: String
    let amount: Double
    let merchant: String
}

final class UnoptimizedTransactionStore: ObservableObject {
    @Published var transactions: [UnoptimizedTransactionItem] = []
    @Published var filterKeyword: String = ""

    init() {
        self.transactions = (0...2000).map {
            UnoptimizedTransactionItem(
                id: "TX-\($0)",
                amount: Double.random(in: 1...500),
                merchant: "Merchant Store #\($0)"
            )
        }
    }
}

public struct TransactionFeedBaselineView: View {
    @StateObject private var store = UnoptimizedTransactionStore()

    public init() {}

    public var body: some View {
        NavigationView {
            // MASALAH 1: ScrollView + VStack biasa memaksa inisialisasi 2000 View sekaligus di memori
            ScrollView {
                VStack(spacing: 8) {
                    TextField("Filter", text: $store.filterKeyword)
                        .padding()
                        .background(Color.gray.opacity(0.2))

                    ForEach(store.transactions) { tx in
                        // MASALAH 2: Berat komputasi string format & offscreen shadow di setiap baris
                        HStack {
                            Text(tx.merchant)
                            Spacer()
                            Text("$\(String(format: "%.2f", tx.amount))")
                        }
                        .padding()
                        .background(Color.white)
                        .cornerRadius(12)
                        .shadow(color: .black.opacity(0.15), radius: 5, x: 0, y: 4) // Render Server Hitch
                    }
                }
            }
            .navigationTitle("Transactions")
        }
    }
}
```

#### Step 2: Diagnostic via Xcode Instruments
1. Jalankan target skema aplikasi menggunakan profil **Release** (`Cmd + I`).
2. Pilih Template **SwiftUI** dan **Time Profiler**.
3. Rekam saat melakukan fling-scroll cepat ke bawah pada view di atas.
4. Perhatikan:
   - Nilai **Frame Hitch Rate** melompat tinggi (> 10%).
   - Total View allocations meledak secara linear pada *Allocations Instrument*.
   - CPU Core jenuh di thread utama (`com.apple.main-thread`).

#### Step 3: Implementasi Solusi (Optimized)
Terapkan solusi berikut pada `hands-on/m02/TransactionFeedOptimized.swift`:

```swift
import SwiftUI
import Observation

// Solusi 1: Pemodelan data stabil dengan Equatable conformance
struct OptimizedTransactionItem: Identifiable, Equatable, Sendable {
    let id: String
    let amountText: String // Pre-computed layout string, zero formatting cost in view body
    let merchant: String

    init(id: String, amount: Double, merchant: String) {
        self.id = id
        self.merchant = merchant
        self.amountText = amount.formatted(.currency(code: "USD"))
    }
}

@Observable
final class OptimizedTransactionStore {
    var filterKeyword: String = ""
    private(set) var transactions: [OptimizedTransactionItem] = []

    init() {
        let rawTransactions: [OptimizedTransactionItem] = (0...2000).map {
            OptimizedTransactionItem(
                id: "TX-\($0)",
                amount: Double.random(in: 1...500),
                merchant: "Merchant Store #\($0)"
            )
        }
        self.transactions = rawTransactions
    }
}

public struct TransactionFeedOptimizedView: View {
    @State private var store = OptimizedTransactionStore()

    public init() {}

    public var body: some View {
        NavigationStack {
            // Solusi 2: Gunakan Lazy layout engine untuk membatasi instansiasi hanya yang tampak
            ScrollView {
                LazyVStack(spacing: 8) {
                    TextField("Filter", text: $store.filterKeyword)
                        .padding()
                        .background(Color(uiColor: .tertiarySystemFill))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .padding(.horizontal)

                    ForEach(store.transactions) { tx in
                        OptimizedTransactionRow(tx: tx)
                    }
                }
                .padding(.vertical)
            }
            .navigationTitle("Transactions")
        }
    }
}

// Solusi 3: Ekstraksi row ke Equatable subview mandiri
struct OptimizedTransactionRow: View, Equatable {
    let tx: OptimizedTransactionItem

    static func == (lhs: OptimizedTransactionRow, rhs: OptimizedTransactionRow) -> Bool {
        lhs.tx == rhs.tx
    }

    var body: some View {
        HStack {
            Text(tx.merchant)
                .font(.body)
            Spacer()
            Text(tx.amountText)
                .font(.system(.body, design: .monospaced, weight: .medium))
        }
        .padding()
        .background(Color(uiColor: .secondarySystemGroupedBackground))
        // Solusi 4: Penggantian dynamic layer shadow dengan border tipis teroptimasi GPU
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color(uiColor: .separator), lineWidth: 0.5)
        )
        .padding(.horizontal)
    }
}
```

---

### 13. Exercises

#### Level: Easy
Refaktor blok tampilan berikut agar tidak mengevaluasi ulang teks persentase baterai saat status Wi-Fi berubah:
```swift
class DeviceStatus: ObservableObject {
    @Published var wifiSSID: String = "Office_5G"
    @Published var batteryLevel: Int = 98
}
```
*Tugas:* Buat arsitektur subview terisolir sehingga perubahan `wifiSSID` tidak menyentuh AttributeGraph node milik komponen baterai.

#### Level: Medium
Diberikan sebuah list dengan 500 item. Setiap item memiliki animasi pulsing border secara berkelanjutan. Jika menggunakan `.animation(.repeatForever())` standar, hitch rate akan meningkat pesat.
*Tugas:* Refaktor menggunakan `TimelineView` dan visual primitives yang dikerjakan via drawing pipeline terisolir tanpa memicu cascade invalidation ke item list di sekitarnya.

#### Level: Hard
Kembangkan custom layout engine menggunakan protokol `Layout` (`struct HighPerformanceWaterfallLayout: Layout`) yang menghitung komputasi masonry grid secara efisien. Aturan: Layout cache harus diimplementasikan menggunakan `Layout.makeCache(subviews:)` guna mencegah pass pengukuran ulang (`sizeThatFits`) berlebih saat scrolling.

---

### 14. Real-World Enterprise Challenge

#### Deskripsi Kasus
Sebuah aplikasi perbankan tier-1 menghadapi masalah memori dan frame latency kritis pada modul dashboard utamanya. Dashboard tersebut berisi:
1. Rekening tabungan dengan balance yang berdenyut (berubah dinamis).
2. Mini statement carousel horizontal bersarang di dalam scroll view vertikal utama.
3. Chart garis historis pengeluaran interaktif dengan gesture drag tracker.

#### Kendala & Spesifikasi Masalah
- Melakukan dragging pada chart memicu pembacaan titik koordinat yang frekuensinya mencapai 120 event per detik.
- Drag gesture ini saat ini diikat ke `@State` pada level root dashboard, mengakibatkan seluruh sub-tree carousel dan elemen statis lainnya dievaluasi ulang (re-rendered) secara brutal.
- Memori footprint meningkat stabil dari 65MB menjadi 480MB setelah 3 menit penggunaan karena retain-cycle pada task pembaruan live data.

#### Sasaran Challenge
Rancang arsitektur dashboard tanpa breaking design requirement:
1. Batasi cakupan gesture drag tracking menggunakan koordinasi state terisolasi (Isolate gesture phase state mutator).
2. Amankan pipeline concurrency sehingga saat user berpindah tab navigasi, seluruh background stream task langsung dibatalkan secara bersih tanpa memory leak.
3. Target Performa: Main Thread execution time tidak boleh melampaui **3.5 milidetik** per frame render pass (Zero Drop Frames pada 120Hz ProMotion).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa fungsi utama dari AttributeGraph pada runtime SwiftUI?**
   - A. Menangani network request aplikasi secara concurrent.
   - B. Memetakan dependensi data reaktif deklaratif dan melacak simpul yang harus dihitung ulang saat state bermutasi.
   - C. Menggantikan tugas Metal shader untuk merender piksel ke layar kaca.
   - D. Mengubah objek JSON secara otomatis menjadi struct Swift.
2. **Kapan SwiftUI mengeksekusi ulang closure `var body: some View` sebuah struct?**
   - A. Setiap milidetik secara konstan.
   - B. Hanya saat user menyentuh layar perangkat.
   - C. Ketika simpul Dynamic Property yang diamati di dalam body tersebut ditandai dirty oleh AttributeGraph.
   - D. Setiap kali compiler menyelesaikan build skema Release.
3. **Apa perbedaan mendasar antara `VStack` dan `LazyVStack`?**
   - A. `VStack` hanya bisa di-scroll secara horizontal, `LazyVStack` vertikal.
   - B. `VStack` menginstansiasi dan menghitung layout seluruh child views di awal; `LazyVStack` hanya menginstansiasi view saat mendekati viewport layar.
   - C. `LazyVStack` merender konten langsung menggunakan WebGL.
   - D. `LazyVStack` tidak mendukung penggunaan modifier `.padding()`.
4. **Metrik apa yang digunakan oleh Apple untuk mengukur frame drop pada instrumen Core Animation?**
   - A. Ping Response Time.
   - B. Memory Leaks Rate per second.
   - C. Hitch Time Ratio (ms/s).
   - D. Swift Syntax Complexity Score.
5. **Modifier mana yang memindahkan render komposit hierarki view ke buffer off-screen Metal?**
   - A. `.ignoresSafeArea()`
   - B. `.drawingGroup()`
   - C. `.clipped()`
   - D. `.compositingGroupOnly()`

#### Bagian 2: Intermediate (5 Soal)
6. **Mengapa penggunaan conditional structural identity berikut berisiko menurunkan performa animasi?**
   ```swift
   if isPremiumUser {
       ProfileCard(badge: true)
   } else {
       ProfileCard(badge: false)
   }
   ```
   - A. Menghasilkan alokasi 2 instance yang menghancurkan dan membangun ulang simpul state internal `ProfileCard`.
   - B. SwiftUI tidak mengizinkan percabangan `if-else` dalam ViewBuilder.
   - C. Menghasilkan error compiler pada Swift 6.
   - D. Memaksa prosesor berpindah ke arsitektur 32-bit.
7. **Bagaimana macro `@Observable` (iOS 17+) meningkatkan performa jika dibandingkan dengan `ObservableObject`?**
   - A. `@Observable` berjalan di thread kernel private.
   - B. `@Observable` menerapkan tracking berbasis field/property access; View hanya invalidate bila field spesifik yang ia baca bermutasi, bukan setiap field `@Published` bermutasi.
   - C. `@Observable` mengompres ukuran struct View menjadi 1-bit.
   - D. `@Observable` menonaktifkan mekanisme layout pass.
8. **Apa bahaya meletakkan operasi `.id(UUID())` di dalam sebuah baris `ForEach`?**
   - A. Nilai UUID akan mengalami integer overflow.
   - B. Merusak Explicit Identity; AttributeGraph menganggap elemen tersebut selalu baru setiap render pass, memicu deallokasi total dan hilangnya status animasi.
   - C. Menghentikan runloop aplikasi seketika karena fatal error.
   - D. Tidak ada dampak performa sama sekali.
9. **Kapan penggunaan `.drawingGroup()` justru memperburuk performa rendering aplikasi?**
   - A. Ketika hierarki view tersebut sangat sederhana (misal: satu Text view), karena overhead switching context off-screen Metal lebih mahal daripada penghematan komputasi yang didapat.
   - B. Ketika aplikasi dijalankan pada layar ProMotion.
   - C. Ketika view tersebut memiliki frame width lebih dari 100 pt.
   - D. Ketika view berada di dalam sub-class `UIWindow`.
10. **Bagaimana cara mencegah closure modifier `.task` membocorkan memory (retain leak)?**
    - A. Tidak pernah menggunakan keyword `await`.
    - B. Menghindari explicit strong reference cycle ke objek penampung yang memiliki masa hidup lebih panjang daripada view struct tersebut, atau mengandalkan cooperative task cancellation bawaan saat View unmount.
    - C. Selalu memanggil fungsi `exit(0)` di akhir task.
    - D. Mengubah seluruh struct menjadi protocol existential.

#### Bagian 3: Enterprise Case Scenarios (3 Soal)
11. **Skenario Kasus 1:**
    Sebuah aplikasi streaming video memiliki scroll view vertikal dengan ratusan thumbnail. Tim QA melaporkan terjadi **Commit Hitch** tinggi hanya ketika user melakukan scrolling cepat, tetapi GPU utilization tergolong rendah (< 20%). Tindakan arsitektural mana yang paling tepat untuk mengeliminasi Commit Hitch tersebut?
    - A. Membungkus setiap thumbnail menggunakan modifier `.drawingGroup()`.
    - B. Mengaudit `View.init()` dan `body` execution: Pindahkan kalkulasi parsing tanggal/format string ke asynchronous model processor dan pastikan list menggunakan `LazyVStack` bukan `VStack`.
    - C. Mengganti semua format gambar dari JPEG ke GIF.
    - D. Memaksa frame rate turun ke 30 FPS secara permanen via plist configuration.
12. **Skenario Kasus 2:**
    Pada fitur peta interaktif dengan 1.000 titik koordinat pin, pergerakan map terasa patah-patah (*lagging*). Setiap kali koordinat kamera bergeser sedikit, seluruh 1.000 pin memicu komputasi ulang. Bagaimana cara mendesain ulang arsitektur rendering pin tersebut?
    - A. Menggunakan `Canvas` untuk merender seluruh 1.000 pin dalam satu pass rasterisasi 2D, memisahkan data posisi dari deklarasi subview SwiftUI.
    - B. Menambahkan modifier `.animation(.bouncy)` ke setiap pin.
    - C. Mengubah data struct Pin menjadi Class bertingkat.
    - D. Membagi 1.000 pin ke dalam 1.000 Window terpisah.
13. **Skenario Kasus 3:**
    Aplikasi Anda mengonsumsi memory footprint yang terus merangkak naik (Memory Leak) dari 100MB hingga 1.2GB setelah membuka dan menutup halaman detail produk berulang kali. Halaman detail menggunakan `.task` untuk mendengarkan AsyncSequence dari NotificationCenter. Apa kemungkinan penyebab utama kebocoran tersebut?
    - A. AsyncSequence tetap hidup dan terus mendengarkan event di background karena Task tidak di-cancel secara kooperatif atau closure memegang referensi retain cycle ke instance luar.
    - B. SwiftUI tidak mendukung modifier `.task` lebih dari satu kali per aplikasi.
    - C. Warna latar belakang view terlalu terang sehingga memakan RAM.
    - D. Nilai struct di SwiftUI otomatis diubah compiler menjadi Objective-C pointers tanpa ARC.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** - AttributeGraph adalah DAG engine yang melacak keterikatan data dan memetakan dirty sub-nodes.
2. **C** - Invalidation terjadi hanya saat Dynamic Property dependencies dari simpul yang bersangkutan mengalami mutasi nilai.
3. **B** - Lazy layout engines menginstansiasi view on-demand berdasarkan proyeksi viewport, sedangkan stack biasa bersifat eager.
4. **C** - Hitch Time Ratio (rasio milidetik frame terlambat per detik) adalah standar resmi metrik kelancaran rendering Apple.
5. **B** - `.drawingGroup()` memindahkan instruksi gambar primitif subview ke Metal rendering context offscreen.

#### Bagian 2: Intermediate
6. **A** - Mengubah tipe dari satu cabang pohon ke cabang lain membuang Structural Identity simpul lama dan mengalokasikan ulang state.
7. **B** - `@Observable` membaca graph access via Swift Observation runtime macro, mengeliminasi over-subscription level objek yang ada di `Combine`/`ObservableObject`.
8. **B** - UUID baru pada tiap render loop merusak Explicit Identity, merusak sistem differential engine, animasi, dan memory caching.
9. **A** - Off-screen passes Metal membutuhkan alokasi tekstur sekunder yang memakan latensi commit; tidak boleh digunakan untuk hierarki trivial.
10. **B** - Lifecycle `.task` terikat pada mounting View, namun retain cycles pada custom capturing reference context dapat mencegah deallocation dependencies.

#### Bagian 3: Production Scenarios
11. **B** - Commit Hitch dengan GPU rendah menunjukkan bottleneck berada di Main Thread CPU (eksekusi body berlebih, eager layout instantiation, formatting berat).
12. **A** - `Canvas` menggabungkan ribuan entitas grafis vektor ke dalam single draw-call GPU yang menghemat alokasi AttributeGraph node secara drastis.
13. **A** - AsyncStreams/Sequences yang tidak terputus secara kooperatif akan menahan retain loop task context dan dependencies-nya di memori heap.

---

### 16. Summary

1. **Internal Engine Mechanics:**
   Performa prima SwiftUI dicapai dengan memahami mekanisme **AttributeGraph**, proses diffing struktural, serta pemisahan tegas antara fase evaluasi aplikasi (Commit Phase) dan rendering GPU (Render Server Phase).
2. **Identity Stability:**
   Menjaga kestabilan **Structural Identity** dan **Explicit Identity** adalah pertahanan lini pertama dalam mencegah komputasi View Invalidation yang sia-sia dan rusaknya status animasi antarmuka.
3. **Observation Granularity:**
   Transisi dari `ObservableObject` monolitik ke `@Observable` (iOS 17+) meminimalkan dynamic property churn, memastikan siklus hidup `body` hanya tereksekusi pada leaf views yang membutuhkan nilai data terbaru.
4. **Appropriate Primitives:**
   Terapkan lazy containers (`LazyVStack`, `LazyHGrid`) untuk koleksi data besar, dan eskalasikan beban gambar berdensitas ekstrem langsung ke **Metal/Canvas** pipeline guna menjaga frame latency berada di bawah ambang batas **8.33ms (120Hz)** secara konsisten.