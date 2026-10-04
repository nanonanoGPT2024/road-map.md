# Kurikulum iOS Engineering: Frontend & Mobile
## Kategori: 03-Frontend-and-Mobile
### Bab 02: Arsitektur UI Modern & Rekayasa Antarmuka Deklaratif
#### Modul 01: Desain Antarmuka Deklaratif dengan SwiftUI Tingkat Lanjut

---

### SEKSI 01 — IDENTITAS MODUL
* **Kode Modul**: `IOS-03-02-01`
* **Tingkat Kesulitan**: Advanced / Staff Engineer Level
* **Prasyarat**: Pemahaman mendalam tentang Swift 6 concurrency (`Sendable`, Actors), Swift Property Wrappers, UIKit Lifecycle, dasar-dasar SwiftUI (View protocol, View Hierarchy), dan Metal Core Animation Pipeline.
* **Target Environment**: Xcode 16+, iOS 18+ Deployment Target, Swift 6 Language Mode.
* **Estimasi Waktu Penyelesaian**: 8 - 12 Jam Kerja Terfokus.

---

### SEKSI 02 — LEARNING OBJECTIVES
1. **Menguasai Mekanisme Internal Evaluasi Subtree**: Memahami secara deterministik bagaimana SwiftUI Attribute Graph (AG) bekerja, melacak dependency graph, mengeliminasi re-render yang tidak perlu (*over-invalidation*), dan mengoptimalkan siklus diffing antarmuka.
2. **Implementasi Sistem Tata Letak Kustom Tingkat Rendah**: Merancang dan membangun komponen berbasis protocol `Layout` kustom dengan penghitungan geometric layout yang optimal, dynamic size caching via `LayoutCache`, dan subview measurement (`LayoutSubviews`).
3. **Rekayasa Komponen Berbasis Protokol dan Dynamic Preferences**: Menguasai propagasi data bottom-up melalui `PreferenceKey`, `Anchor<T>`, serta pembuatan custom dynamic view styling yang modular dan decoupled.
4. **Optimasi Tingkat Lanjut Pipeline Rendering**: Mengidentifikasi dan memitigasi frame drops (hitch rate < 5ms per frame) menggunakan instruments, memory layout profiling, direct Metal rendering via `Canvas`, dan offloading expensive layout computation.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma imperatif (seperti UIKit tradisional), UI dikelola sebagai pohon objek mutable stateful yang hidup panjang (*long-lived stateful objects*). Anda memanipulasi node secara langsung: `view.backgroundColor = .red`, `view.addSubview(subview)`. Kesalahan mentalitas terbesar engineer yang bermigrasi ke SwiftUI tingkat lanjut adalah memperlakukan `View` sebagai "objek visual".

```
Paradigma Imperatif (UIKit):
State A ---> [Developer Mutates View Manually] ---> State B (State & View desync prone)

Paradigma Deklaratif (SwiftUI Tingkat Lanjut):
UI = f(State)
                    +-------------------+
                    |    State Source   |
                    +-------------------+
                              |
                              v
                    +-------------------+
                    | Pure Function (f) |  <--- Immutable Struct Hierarchy
                    +-------------------+
                              |
                              v
                    +-------------------+
                    |  Attribute Graph  |  <--- SwiftUI Runtime Engine
                    +-------------------+
                              |
                              v
                    +-------------------+
                    |   Render Tree     |  <--- Render Server / Core Animation
                    +-------------------+
```

Di SwiftUI, `View` hanyalah resep cetak biru (*blueprint*) transien, immutable, dan berbobot sangat ringan (*pure struct value type*). `View` tidak memiliki lifecycle hidup panjang. Instansiasi struct view dievaluasi, dikonversi menjadi simpul internal dalam **Attribute Graph (AG)**, lalu dihancurkan. Attribute Graph adalah struktur data persisten sebenarnya yang menyimpan status, dependensi, dan menggerakkan komparasi diffing untuk diteruskan ke Core Animation Render Server.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di balik kesederhanaan deklarasi SwiftUI, terdapat runtime multi-tier yang mengelola binding status, graph evaluation, dan layout negotiation:

```
+-----------------------------------------------------------------------------+
|                          SWIFT APPLICATION LAYER                            |
|                                                                             |
|  +------------------------+                  +---------------------------+  |
|  |   View Hierarchy (f)   |                  | State Storage             |  |
|  |   (Immutable Structs)  | <--- Binding --- | (@State, @Observable,     |  |
|  +------------------------+                  |  Environment, Preferences)|  |
+--------------|---------------------------------------------|----------------+
               | Materialization                             | Invalidation
               v                                             v
+-----------------------------------------------------------------------------+
|                        SWIFTUI RUNTIME & ATTRIBUTE GRAPH                    |
|                                                                             |
|   +---------------------------------------------------------------------+   |
|   | AttributeGraph.framework (AG::Graph, AG::Node)                      |   |
|   |                                                                     |   |
|   |   [Node: Subtree A] <--- Tracks Dependency ---> [Node: State Prop]  |   |
|   |          |                                                          |   |
|   |          v (Dirty Marked)                                           |   |
|   |   [Re-evaluation via body] ---> Compute Structural / Identity Diff  |   |
|   +---------------------------------------------------------------------+   |
|                                      |                                      |
|                                      v Layout Negotiation                   |
|   +---------------------------------------------------------------------+   |
|   | SwiftUI Layout Engine (Layout Protocol & Cache Engine)               |   |
|   | 1. Parent proposes Size Proposal (unspecified, zero, exact)         |   |
|   | 2. Subviews calculate sizeThatFits via LayoutSubviews                |   |
|   | 3. Parent resolves final bounding rects and places children         |   |
|   +---------------------------------------------------------------------+   |
+--------------------------------------|--------------------------------------+
                                       | Transaction Commit
                                       v
+-----------------------------------------------------------------------------+
|                    CORE ANIMATION & RENDER SERVER (GPU)                     |
|                                                                             |
|  +------------------------+                  +---------------------------+  |
|  | CALayer Tree Assembly  | ------ IPC ----> | Render Server (Backing)   |  |
|  | Metal Shader Passes    |   (Out-of-proc)  | GPU Pipeline (Display)    |  |
|  +------------------------+                  +---------------------------+  |
+-----------------------------------------------------------------------------+
```

Alur siklus layout proposal:
1. **Parent Proposes**: Parent menawarkan ukuran `ProposedViewSize` ke Child.
2. **Child Decides**: Child merespons dengan ukuran absolut `CGSize` yang dibutuhkannya berdasarkan constraints internalnya.
3. **Parent Places**: Parent menempatkan Child di dalam ruang koordinatnya sendiri dengan origin yang ditentukan (`CGPoint`).

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

#### 1. Attribute Graph (AG) Engine
SwiftUI menggunakan framework C++ internal bernama `AttributeGraph.framework`. Ketika `body` suatu view dieksekusi, AG mengikat dependensi dinamis antara properti memori (misalnya slot memori `@State`) dan simpul AG dari view tersebut. 
- **Structural Identity vs Explicit Identity**: Structural Identity ditentukan oleh posisi view dalam pohon eksekusi deklaratif (misalnya cabang `if/else` dalam `@ViewBuilder`). Explicit Identity ditentukan secara manual melalui modifier `.id(...)`. Perubahan Structural Identity memicu destruksi total simpul AG dan alokasi state baru (kehilangan state lokal), sedangkan pembaruan data pada view dengan identitas yang stabil hanya memicu invalidasi properti visual.

#### 2. Layout Protocol Lifecycle & Caching Engine
Protocol `Layout` (diperkenalkan pada iOS 16) mengabstraksi algoritma tata letak 2 dimensi tanpa wrapper `UIView` / `NSView`. Mekanisme internalnya mengandalkan `LayoutCache`:
- `makeCache(subviews:)`: Menginisialisasi cache transien yang dialokasikan di stack/heap untuk memotong kompleksitas komputasi $O(n^2)$ menjadi $O(n)$ selama siklus layout pass berulang.
- `sizeThatFits(proposal:subviews:cache:)`: Dipanggil saat parent menanyakan dimensi layout.
- `placeSubviews(in:proposal:subviews:cache:)`: Mengalokasikan koordinat geometris aktual via instans `LayoutSubview`.

#### 3. PreferenceKey Engine & Dynamic Flow
`PreferenceKey` menggunakan mekanisme reverse-tree traversal. Saat pohon dievaluasi secara top-down, nilai `PreferenceKey` dipancarkan (*emitted*) oleh leaf nodes dan direduksi (*reduced*) ke atas menggunakan operator closure linear:
$$\text{reduce}(value: \text{inout Value}, nextValue: () \to \text{Value})$$
Jika data dependensi dari preference key dibaca oleh ancestor menggunakan `.onPreferenceChange`, runtime AG menjadwalkan pass layout kedua (*two-pass layout resolution*). Jika salah dirancang, hal ini dapat memicu infinite layout feedback loop (`AttributeGraph: cycle detected`).

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

#### Structural Identity: Bahaya Tersembunyi `AnyView`
Secara internal, SwiftUI mengenkode pohon view ke dalam concrete type signature yang sangat kompleks dan statically-typed pada saat kompilasi, contohnya:
`ModifiedContent<TupleView<(Text, Button<Text>)>, _PaddingLayout>`

Ketika Anda menggunakan type eraser `AnyView`, Anda merusak static type system ini:
1. **Type-Erasure Penalty**: Mengubah concrete layout node compile-time menjadi dynamic heap-allocated reference box type.
2. **Graph Reconstruction**: AG tidak dapat lagi melacak kesamaan tipe antar update frame. Perubahan kecil dalam `AnyView` memaksa penghancuran dan pembuatan ulang simpul AG secara agresif alih-alih diffing field-level.

#### View Equalization (`EquatableView`)
Secara default, SwiftUI membandingkan view berdasarkan kesamaan bitwise struktural atau dynamic attribute access tracking. Mengimplementasikan `Equatable` pada View struct dan membungkusnya dengan modifier `.equatable()` mencegah compiler memanggil `body` secara redundan jika state yang relevan tidak berubah:

```swift
struct ExpensiveNodeView: View, Equatable {
    let identifier: UUID
    let metrics: PerformanceMetrics
    
    // Explicit static equality check bypassing dynamic AG walk
    static func == (lhs: ExpensiveNodeView, rhs: ExpensiveNodeView) -> Bool {
        lhs.identifier == rhs.identifier && lhs.metrics == rhs.metrics
    }

    var body: some View {
        // Berat, hanya dieksekusi jika `==` mengembalikan false
        ComplexRenderNode(metrics: metrics)
    }
}
```

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi non-trivial dari sistem custom layout berkinerja tinggi: **AdaptiveFlowLayout** yang mendukung dynamic content wrapping, alignment modes, dan inter-item threshold caching.

```swift
import SwiftUI

// MARK: - 1. Cache Storage Structure
public struct FlowLayoutCacheData: Sendable {
    var lineAllocations: [[LayoutSubview]] = []
    var lineHeights: [CGFloat] = []
    var totalComputedHeight: CGFloat = 0.0
    var maxWidthCached: CGFloat = 0.0
}

// MARK: - 2. Custom Layout Implementation
public struct AdaptiveFlowLayout: Layout {
    public struct AlignmentConfiguration: Sendable {
        public enum HorizontalAlignment: Sendable {
            case leading, center, trailing
        }
        public var horizontal: HorizontalAlignment
        public var horizontalSpacing: CGFloat
        public var verticalSpacing: CGFloat

        public init(horizontal: HorizontalAlignment = .leading, horizontalSpacing: CGFloat = 8, verticalSpacing: CGFloat = 8) {
            self.horizontal = horizontal
            self.horizontalSpacing = horizontalSpacing
            self.verticalSpacing = verticalSpacing
        }
    }

    private let config: AlignmentConfiguration

    public init(config: AlignmentConfiguration = .init()) {
        self.config = config
    }

    public func makeCache(subviews: Subviews) -> FlowLayoutCacheData {
        FlowLayoutCacheData()
    }

    public func updateCache(_ cache: inout FlowLayoutCacheData, subviews: Subviews) {
        // Cache akan diinvalidation otomatis saat subview collections berubah
        cache.lineAllocations.removeAll(keepingCapacity: true)
        cache.lineHeights.removeAll(keepingCapacity: true)
        cache.totalComputedHeight = 0
        cache.maxWidthCached = 0
    }

    public func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout FlowLayoutCacheData
    ) -> CGSize {
        let containerWidth = proposal.width ?? .infinity
        computeRows(proposalWidth: containerWidth, subviews: subviews, cache: &cache)
        return CGSize(width: containerWidth.isInfinite ? cache.maxWidthCached : containerWidth, height: cache.totalComputedHeight)
    }

    public func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout FlowLayoutCacheData
    ) {
        computeRows(proposalWidth: bounds.width, subviews: subviews, cache: &cache)

        var currentY: CGFloat = bounds.minY

        for (rowIndex, rowSubviews) in cache.lineAllocations.enumerated() {
            let rowHeight = cache.lineHeights[rowIndex]
            let totalRowItemsWidth = rowSubviews.reduce(0.0) { sum, view in
                sum + view.sizeThatFits(.unspecified).width
            } + CGFloat(max(0, rowSubviews.count - 1)) * config.horizontalSpacing

            var currentX: CGFloat = bounds.minX

            switch config.horizontal {
            case .leading:
                currentX = bounds.minX
            case .center:
                currentX = bounds.minX + max(0, (bounds.width - totalRowItemsWidth) / 2)
            case .trailing:
                currentX = bounds.maxX - totalRowItemsWidth
            }

            for subview in rowSubviews {
                let itemSize = subview.sizeThatFits(.unspecified)
                let yOffset = currentY + (rowHeight - itemSize.height) / 2 // Align vertically centered within the row

                subview.place(
                    at: CGPoint(x: currentX, y: yOffset),
                    proposal: ProposedViewSize(itemSize)
                )

                currentX += itemSize.width + config.horizontalSpacing
            }

            currentY += rowHeight + config.verticalSpacing
        }
    }

    // MARK: - Core Allocation Algorithm
    private func computeRows(proposalWidth: CGFloat, subviews: Subviews, cache: inout FlowLayoutCacheData) {
        guard !subviews.isEmpty else {
            cache.totalComputedHeight = 0
            return
        }

        cache.lineAllocations.removeAll(keepingCapacity: true)
        cache.lineHeights.removeAll(keepingCapacity: true)

        var currentRow: [LayoutSubview] = []
        var currentLineWidth: CGFloat = 0.0
        var currentLineMaxHeight: CGFloat = 0.0
        var recordedMaxWidth: CGFloat = 0.0

        for subview in subviews {
            let itemSize = subview.sizeThatFits(.unspecified)
            
            // Check overflow
            if !currentRow.isEmpty && (currentLineWidth + config.horizontalSpacing + itemSize.width) > proposalWidth {
                cache.lineAllocations.append(currentRow)
                cache.lineHeights.append(currentLineMaxHeight)
                recordedMaxWidth = max(recordedMaxWidth, currentLineWidth)

                // Reset untuk baris berikutnya
                currentRow = [subview]
                currentLineWidth = itemSize.width
                currentLineMaxHeight = itemSize.height
            } else {
                currentRow.append(subview)
                currentLineWidth += (currentRow.count == 1 ? 0 : config.horizontalSpacing) + itemSize.width
                currentLineMaxHeight = max(currentLineMaxHeight, itemSize.height)
            }
        }

        if !currentRow.isEmpty {
            cache.lineAllocations.append(currentRow)
            cache.lineHeights.append(currentLineMaxHeight)
            recordedMaxWidth = max(recordedMaxWidth, currentLineWidth)
        }

        cache.maxWidthCached = recordedMaxWidth
        let totalSpacing = CGFloat(max(0, cache.lineAllocations.count - 1)) * config.verticalSpacing
        cache.totalComputedHeight = cache.lineHeights.reduce(0, +) + totalSpacing
    }
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 4–9 (`FlowLayoutCacheData`)**: Menggunakan `Sendable struct` sebagai mutable buffer cache. Komputasi baris dan subview wrapping disimpan di sini agar `sizeThatFits` dan `placeSubviews` tidak perlu melakukan parsing geometri yang sama secara berulang.
* **Baris 12 (`AdaptiveFlowLayout: Layout`)**: Mengadopsi protocol `Layout`. Mengabaikan ketergantungan pada `GeometryReader` berbasis subviews, yang secara inheren mengorbankan performa saat layout kompleks.
* **Baris 31–33 (`makeCache`)**: Dialokasikan satu kali oleh SwiftUI AG runtime. Disimpan di luar daur hidup frame rendering murni dan dipersistensikan selama input subviews tetap stabil.
* **Baris 42–50 (`sizeThatFits`)**: Menghitung bounded box minimum absolut. Logika handling `proposal.width ?? .infinity` penting agar layout tetap valid ketika ditampung di dalam horizontal scrollview yang menyuplai unbounded width proposal.
* **Baris 73–82 (Offset X Alignment Evaluation)**: Menghitung dynamic offset per baris secara modular. Sisa lebar ruang horizontal (`bounds.width - totalRowItemsWidth`) dibagi secara deterministik untuk mengakomodasi alignment types (`leading`, `center`, `trailing`).
* **Baris 86–91 (`subview.place`)**: Memberikan instruksi final transform affine matrix ke child node. Di sini `ProposedViewSize(itemSize)` secara eksplisit mengunci ukuran subview agar tidak terdistorsi oleh engine parent.
* **Baris 112–120 (Line Break Engine)**: Mengimplementasikan dynamic wrapping algorithm dengan batasan horizontal spacing. Memastikan tidak ada layout break yang menyebabkan subview overflow keluar dari frame bound.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario Enterprise
Pada aplikasi **High-Frequency Crypto/Stock Trading Terminal**, aplikasi menerima data orderbook dan market executions (hingga 50 tick pembaruan per detik via WebSocket). Desain lama menggunakan komponen `LazyVStack` standar yang dibungkus dengan berbagai `GeometryReader` dan `AnyView` styling builder.

#### Permasalahan Skala Produksi
1. **Core Animation Hitching**: Frame rate anjlok dari 120 FPS (ProMotion) ke rentang 28–45 FPS saat market rally volatil.
2. **Main Thread Blocking**: `body` pada root trading screen dievaluasi ulang 50 kali/detik karena state binding ke flat Observable object yang over-invalidating.
3. **Memory Spike**: Graph evaluation leaks terakumulasi dari transient state type erasure, mengakibatkan thermal throttling pada perangkat fisik.

#### Solusi Arsitektural
1. Mengembangkan pipeline visualisasi modular menggunakan **Metal Canvas API** berpasangan dengan custom SwiftUI Layout untuk orderbook depth representation.
2. Mengisolasi evaluasi graph dengan memecah state store menggunakan `@Observable` (Observation Framework Swift 5.9+) untuk *fine-grained dependency tracking*.
3. Eliminasi seluruh `GeometryReader` dan menggantinya dengan bottom-up `PreferenceKey` tracking yang dipasangkan dengan `AdaptiveLayoutEngine`.

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur trading terminal: Orderbook level depth rendering engine dengan atomic invalidation tracking dan custom canvas layout integration.

```swift
import SwiftUI
import Observation

// MARK: - Models
public struct OrderBookEntry: Identifiable, Equatable, Sendable {
    public let id: UUID
    public let price: Double
    public let quantity: Double
    public let side: OrderSide

    public enum OrderSide: Sendable {
        case bid, ask
    }
}

// MARK: - High-Performance Fine-Grained State Store
@Observable
public final class OrderBookEngine: @unchecked Sendable {
    // Dipisahkan untuk mengisolasi mutasi level graph evaluation
    public private(set) var bids: [OrderBookEntry] = []
    public private(set) var asks: [OrderBookEntry] = []
    public private(set) var lastExecutionPrice: Double = 0.0

    private let isolationQueue = DispatchQueue(label: "com.engine.orderbook", qos: .userInteractive)

    public init() {}

    public func batchUpdate(bids: [OrderBookEntry], asks: [OrderBookEntry], lastPrice: Double) {
        // Atomic synchronization passing ke main thread
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.bids = bids
            self.asks = asks
            self.lastExecutionPrice = lastPrice
        }
    }
}

// MARK: - Custom Preference Keys for Coordinate Tracking
public struct DepthRowBoundsPreferenceKey: PreferenceKey {
    public typealias Value = [UUID: Anchor<CGRect>]
    public static var defaultValue: Value = [:]

    public static func reduce(value: inout Value, nextValue: () -> Value) {
        value.merge(nextValue(), uniquingKeysWith: { $1 })
    }
}

// MARK: - Optimized View Implementations
public struct OrderBookContainerView: View {
    @Bindable var engine: OrderBookEngine
    @State private var hoveredEntry: UUID?

    public init(engine: OrderBookEngine) {
        self.engine = engine
    }

    public var body: some View {
        HStack(spacing: 0) {
            OrderBookSideList(entries: engine.bids, side: .bid)
            Divider().background(Color.secondary.opacity(0.3))
            OrderBookSideList(entries: engine.asks, side: .ask)
        }
        .overlayPreferenceValue(DepthRowBoundsPreferenceKey.self) { preferences in
            GeometryReader { proxy in
                if let hoveredId = hoveredEntry, let anchor = preferences[hoveredId] {
                    let rect = proxy[anchor]
                    Rectangle()
                        .stroke(Color.yellow, lineWidth: 1.5)
                        .frame(width: rect.width, height: rect.height)
                        .position(x: rect.midX, y: rect.midY)
                        .animation(.interactiveSpring(response: 0.2, dampingFraction: 0.8), value: rect)
                }
            }
        }
    }
}

public struct OrderBookSideList: View, Equatable {
    let entries: [OrderBookEntry]
    let side: OrderBookEntry.OrderSide

    public static func == (lhs: OrderBookSideList, rhs: OrderBookSideList) -> Bool {
        lhs.entries == rhs.entries && lhs.side == rhs.side
    }

    public var body: some View {
        VStack(spacing: 1) {
            ForEach(entries) { entry in
                OrderBookRowView(entry: entry)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

public struct OrderBookRowView: View, Equatable {
    let entry: OrderBookEntry

    public static func == (lhs: OrderBookRowView, rhs: OrderBookRowView) -> Bool {
        lhs.entry == rhs.entry
    }

    public var body: some View {
        HStack {
            Text(String(format: "%.2f", entry.price))
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(entry.side == .bid ? .green : .red)
            Spacer()
            Text(String(format: "%.4f", entry.quantity))
                .font(.system(.caption2, design: .monospaced))
                .foregroundColor(.secondary)
        }
        .padding(.horizontal, 8)
        .frame(height: 20)
        .background(
            GeometryReader { geo in
                // High-performance depth representation using Canvas context directly inside row background
                Canvas { context, size in
                    let depthWidth = size.width * CGFloat(min(entry.quantity / 100.0, 1.0))
                    let fillRect = CGRect(x: entry.side == .bid ? size.width - depthWidth : 0,
                                          y: 0,
                                          width: depthWidth,
                                          height: size.height)
                    let fillColor = entry.side == .bid ? Color.green.opacity(0.15) : Color.red.opacity(0.15)
                    context.fill(Path(fillRect), with: .color(fillColor))
                }
            }
        )
        // Propagate anchor bounds up using PreferenceKey without triggering body rebuilds
        .anchorPreference(key: DepthRowBoundsPreferenceKey.self, value: .bounds) { anchor in
            [self.entry.id: anchor]
        }
    }
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek / Metrik | Native SwiftUI `Layout` Protocol | UIKit Hosted (`UIViewRepresentable`) | Modern Canvas (`GraphicsContext`) |
| :--- | :--- | :--- | :--- |
| **Overhead Alokasi Memori** | Sangat Rendah (Struct-based, stack-allocated cache) | Tinggi (Reference types, overhead `CALayer` dan bridge metadata) | Minimal (Direct Metal texture pass, tanpa intermediate subviews) |
| **Rendering Hitch Risk** | Rendah (Terdiferensiasi secara native di AG) | Medium (Resiko layout pass ganda akibat AutoLayout synchronization) | Hampir Nol (Immediate GPU draw calls) |
| **Developer Ergonomics** | Deklaratif murni, Swift-idiomatic | Komparatif buruk (Boilerplate lifecycle bridge & coordinator) | Menengah (Manual path calculation, tidak ada accessibility otomatis) |
| **Dukungan Aksesibilitas** | Penuh secara inheren (VoiceOver & Accessibility Tree otomatis) | Manual via `UIAccessibilityElement` | Nihil tanpa implementasi eksplisit `.accessibilityElement()` |
| **Kompleksitas State Flow** | Satu arah, declarative diffing | Imperatif, rentan terjadi State Desync antara UIKit & SwiftUI | Stateless rendering function dari upstream state |

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. The Layout Feedback Infinite Cycle
**Failure Mode**: Mengubah state lokal di dalam closure `.onPreferenceChange` yang secara langsung atau tidak langsung mengubah ukuran layout node yang memancarkan preference tersebut.
```swift
// RUNTIME CRASH / FREEZE: Cycle detected in AttributeGraph
.onPreferenceChange(DepthRowBoundsPreferenceKey.self) { preferences in
    self.containerHeight = preferences.values.count * 20 // MEMICU RE-EVALUASI GRAPH TANPA HENTI
}
```
**Mitigasi**: Gunakan `Anchor<T>` bersama modifier `.overlayPreferenceValue` atau `.backgroundPreferenceValue`. Modifier ini membaca bounds geometris di render-tree pass terpisah tanpa memicu evaluasi ulang struktural pada level `View.body`.

#### 2. GeometryReader Unbounded Layout Proposal
**Failure Mode**: `GeometryReader` secara default bersikap "tamak" (*greedy*). Ia selalu menerima ukuran maksimal yang ditawarkan oleh parent (`proposal.width` dan `proposal.height`). Jika diletakkan di dalam container yang memberikan infinite bounds (seperti `ScrollView`), layout akan crash atau terpotong total dengan frame ukuran 0 atau infinity.
**Mitigasi**: Batasi `GeometryReader` menggunakan `.frame(width:..., height:...)` eksplisit atau ganti seluruh dependensi geometri visual ke protocol `Layout`.

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Anti-Pola 1: Dekomposisi Fungsi Pembantu Alih-Alih Custom View Struct
```swift
// BURUK: Invalidation pada MyBigView mengevaluasi ulang SELURUH fungsi pembantu ini
struct MyBigView: View {
    @State private var counter = 0
    var body: some View {
        VStack {
            renderHeader() // BUKAN struct terisolasi!
            Button("Increment") { counter += 1 }
        }
    }
    
    private func renderHeader() -> some View {
        Text("Total: \(counter)") // Invalidation menyebar ke seluruh body parent
    }
}

// BENAR: Ekstraksi ke Dedicated Equatable Struct
struct MyBigView: View {
    @State private var counter = 0
    var body: some View {
        VStack {
            HeaderView(counter: counter) // Attribute Graph membatasi invalidasi simpul lokal
            Button("Increment") { counter += 1 }
        }
    }
}
struct HeaderView: View, Equatable {
    let counter: Int
    var body: some View { Text("Total: \(counter)") }
}
```

#### Anti-Pola 2: Heavy Computation Langsung di Dalam `View.body`
Mengeksekusi penyortiran array, manipulasi data tanggal (`DateFormatter`), atau parsing regex di dalam accessor `body`. Ingat bahwa `body` dapat dipanggil hingga **120 kali per detik** selama animasi atau interaksi gesture.

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **State Partitioning**: Terapkan prinsip isolasi granular. Jangan letakkan seluruh variabel state global dalam satu `@Observable` class raksasa. Buat sub-domain store sehingga mutasi data spesifik tidak memicu evaluasi tree visual yang tidak berkaitan.
2. **Deterministic Struct Initialization**: Hindari inisialisasi side-effects (seperti network calls atau register notification observer) di dalam `init()` sebuah View struct. View struct dapat diinisialisasi puluhan kali tanpa jaminan `body`-nya akan dipanggil. Gunakan `.task` atau lifecycle modifier yang deterministik.
3. **Identity Preservation**: Gunakan pengidentifikasi stabil pada `ForEach` via `Identifiable`. Hindari penggunaan index array (`ForEach(0..<items.count)`) jika koleksi data dapat dihapus, disisipkan, atau diurutkan ulang. Penggunaan index merusak animasi diffing Core Animation dan mengakibatkan layout flickering.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI

#### Meminimalkan Core Animation Hitch Rate
Hitch terjadi ketika frame display terlambat dikirim ke GPU compositor (>8.33ms untuk 120Hz ProMotion display). 

```swift
// Instrument Diagnostic Pattern: Print Attribute Graph Evaluation
extension View {
    func debugPrintAGRebuild(_ message: String) -> Self {
        #if DEBUG
        Self._printChanges() // PRIVATE API tapi legal digunakan dalam dev profiling
        #endif
        return self
    }
}
```

Untuk memangkas rendering cost:
1. **Flattener Pass via `drawingGroup()`**: Untuk tampilan grafik vektor rumit yang terdiri dari puluhan sub-layer path, gunakan modifier `.drawingGroup()`. Modifier ini menginstruksikan Core Animation untuk merender sub-tree secara lokal ke dalam single Metal offscreen texture buffer sebelum dikirim ke Render Server.
2. **Text Caching Strategy**: Hindari dynamic font scaling tanpa caching. Gunakan sistem static rendering untuk tabel bertingkat ribuan baris dengan `.transaction { $0.animation = nil }` pada table tick update massal.

---

### SEKSI 16 — KEAMANAN & HARDENING

#### 1. Data Redaction (Snapshot Leak Mitigation)
Saat aplikasi beralih ke background/multitasking view, sistem mengambil snapshot layar. Jika ada data sensitif (saldo rekening, data medis), data tersebut dapat terekspos dalam flash snapshot iOS.

```swift
public struct RedactableSensitiveField: View {
    let rawValue: String
    @Environment(\.redactionReasons) private var redactionReasons

    public var body: some View {
        Text(rawValue)
            .privacySensitive() // Native iOS 15+ hardening modifier
            .redacted(reason: redactionReasons.contains(.privacy) ? .placeholder : [])
    }
}
```

#### 2. Thread Boundary Invariants
Pada Swift 6, data binding ke UI diwajibkan berjalan di bawah isolasi actor `@MainActor`. Seluruh class state presentation wajib didekorasi dengan:
```swift
@MainActor
@Observable
public final class SecureViewModel {
    // Menjamin compile-time race condition checks di level AG dispatch
}
```

---

### SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

#### 1. Menggunakan Instruments untuk SwiftUI Tracing
* Buka **Instruments -> SwiftUI Instrument**.
* Pantau metrik:
  * **View Body Execution**: Mengukur durasi total evaluasi fungsi `body`. Waspadai nilai jika waktu rata-rata > 1ms.
  * **View Properties Invalidation**: Menampilkan nama variabel state yang memicu rendering invalidasi.
  * **Core Animation Commits**: Memantau waktu commit frame render server.

#### 2. Debugging Attribute Graph Cycles
Tambahkan dynamic argument di Xcode Scheme Anda:
* Target -> Edit Scheme -> Run -> Arguments:
  * Masukkan: `-AG_LOG_CYCLES 1`
  * Masukkan: `-UIViewAlertForUnsatisfiableConstraints NO`

Jika ada preference key loop atau graph feedback recursion, AG engine akan mencetak dependensi simpul spesifik secara detail di console output sebelum stack overflow crash terjadi.

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

* **View Structs**: Blueprint transien, immutable, berukuran ringkas, dan dibuat instansiasi berulang kali. Bukan visual layer yang hidup panjang.
* **Structural Identity**: Ditentukan oleh branching deklaratif. Jangan hancurkan identitas struktural menggunakan `AnyView` tanpa pertimbangan matang.
* **Layout Proposal Contract**: 
  1. Parent proposes `ProposedViewSize`.
  2. Child computes and returns exact `CGSize`.
  3. Parent assigns `CGPoint` position.
* **Layout Protocol**: Memotong traversal overhead dengan memanfaatkan caching buffer (`makeCache`, `updateCache`) dalam satu alur komputasi.
* **Anchor & Preferences**: Jalur propagasi data bottom-up dari subview ke ancestor tanpa memicu pass invalidasi AG yang redundan jika digunakan bersama `.overlayPreferenceValue`.
* **State Invalidation**: `@Observable` melakukan tracking dependensi tingkat properti mikro, secara signifikan mengungguli performa global-invalidation milik `ObservableObject`.

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Soal 1
Mengapa penggunaan modifier `AnyView` secara masif di dalam daftar scroll berkinerja tinggi dikategorikan sebagai anti-pattern fatal pada SwiftUI?
* A. Karena `AnyView` memaksa view untuk dirender di background thread.
* B. Karena `AnyView` mengaburkan tipe konkret compile-time, merusak optimasi diffing internal Attribute Graph, serta memicu alokasi heap dan destruksi state view yang tidak perlu.
* C. Karena `AnyView` tidak mendukung layout modifiers seperti `.padding()` atau `.frame()`.
* D. Karena `AnyView` menonaktifkan Core Animation pipeline dan menurunkan frame rate ke fixed 30 FPS.

#### Soal 2
Perhatikan implementasi layout proposal. Apa yang terjadi jika parent view memberikan tawaran ukuran `ProposedViewSize.unspecified` kepada leaf view bertipe `Text("Test")`?
* A. `Text` akan mengalami crash runtime karena ukuran tidak terdefinisi.
* B. `Text` akan mengklaim ruang layar maksimal yang tersedia (menjadi serakah).
* C. `Text` akan menghitung ukuran intrinsik ideal yang dibutuhkan untuk menggambar karakternya secara utuh tanpa wrapping maupun pemotongan.
* D. `Text` akan mengembalikan frame berukuran `