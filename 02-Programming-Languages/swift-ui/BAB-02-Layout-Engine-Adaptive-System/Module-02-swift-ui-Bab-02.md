# Kurikulum Rekayasa Perangkat Lunak Enterprise: SwiftUI
## BAB 02: Layout Engine & Adaptive System
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Internal Layout Engine**: Membedah siklus hidup *three-step layout negotiation* SwiftUI dan merekonstruksi pohon evaluasi *AttributeGraph*.
2. **Mengeliminasi Anti-Pattern Layout**: Mengganti ketergantungan destruktif terhadap `GeometryReader` dengan `Layout` Protocol modern, `ViewThatFits`, dan sistem `PreferenceKey`.
3. **Mengembangkan Custom Container**: Mengimplementasikan `Layout` protocol kustom yang dilengkapi mekanisme *two-pass sizing* dan *cache invalidation engine* untuk performa 120 FPS (ProMotion).
4. **Membangun Sistem Desain Multiplatform Adaptif**: Mengorkestrasikan layout responsif yang adaptif terhadap *Size Classes*, *Dynamic Type*, *Display Cutouts/Safe Areas*, dan *Windowing Resizing* (macOS/iPadOS Stage Manager) tanpa *frame drop*.
5. **Mendiagnosis Layout Thrashing**: Menemukan dan memitigasi anomali *layout loops*, *dependency cycles*, dan *render invalidation cascading* menggunakan Xcode Instruments (Core Animation & SwiftUI View Body).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
* Fundamental SwiftUI View lifecycle & deklarasi View (`body`, `@ViewBuilder`).
* Pemahaman mendalam terkait Memory Management Swift (Value Types vs Reference Types, Memory Layout, Copy-on-Write).
* Pemahaman teoritis Algoritma Graf: *Directed Acyclic Graph* (DAG).
* Familiaritas dasar dengan sistem AutoLayout UIKit (Cassowary Constraint Solving Engine) sebagai pembanding arsitektur.

---

### 3. Concept & Internal Architecture

#### 3.1 Transisi dari Cassowary (UIKit) ke Algoritma O(n) SwiftUI
UIKit mengandalkan algoritma *Cassowary Linear Constraint Solver*. Cassowary bekerja dengan menyelesaikan sistem persamaan dan pertidaksamaan linear secara simultan. Kompleksitas komputasinya berada pada rentang $O(n)$ hingga $O(n^3)$ dalam skenario terburuk (*worst-case*), menyebabkan degradasi eksponensial saat kedalaman hierarki UI bertambah.

Sebaliknya, layout engine SwiftUI beroperasi sebagai algoritma traversal pohon deterministik satu arah dengan kompleksitas strictly $O(n)$ per pass, di mana $n$ adalah jumlah node dalam pohon layout aktif.

```
       [ Parent View ]
          |        ^
 1. Propose Size   | 2. Report Chosen Size
          v        |
       [ Child View ]
          |
 3. Parent Positions Child in Coordinate Space
```

#### 3.2 Siklus Negosiasi Layout 3-Tahap (*The 3-Step Layout Negotiation*)
Layout engine SwiftUI memproses penempatan setiap node view melalui tiga fase:
1. **Proposal**: Parent view mengajukan ukuran dimensi (`ProposedViewSize`) kepada child view. Dimensi ini dapat bernilai spesifik, nol (`.zero`), tak terhingga (`.infinity`), atau tidak terdefinisi (`.unspecified`).
2. **Determination**: Child view mengevaluasi proposal tersebut berdasarkan karakteristik intrinsiknya (apakah bersifat *greedy*, *neutral*, atau *reluctant*) dan mengembalikan ukuran konkret (`CGSize`) yang dipilihnya secara independen kepada parent.
3. **Placement**: Parent view mengalokasikan titik koordinat pusat (`CGPoint`) untuk meletakkan child view tersebut ke dalam sistem koordinat lokal parent, membulatkan nilai titik ke batas piksel fisik terdekat (*pixel snapping*) untuk mencegah *anti-aliasing artifacts*.

```
Parent View                       Child View
   |                                  |
   |--- 1. Propose(width, height) --->|
   |                                  | (Calculates own intrinsic size)
   |<-- 2. Return CGSize(w, h) -------|
   |                                  |
   |--- 3. PlaceAt(CGPoint(x, y)) --->|
   v                                  v
```

#### 3.3 Anatomi `ProposedViewSize`
Tipe data `ProposedViewSize` tersusun atas dua komponen bertipe `Optional<CGFloat>`:
* **Unspecified (`ProposedViewSize.unspecified` / `width: nil, height: nil`)**: Parent meminta child view melaporkan *ideal/intrinsic size*-nya. Kasus ini terjadi di dalam container seperti `ScrollView`.
* **Zero (`ProposedViewSize.zero` / `width: 0, height: 0`)**: Parent meminta child view melaporkan ukuran minimum absolut yang dimungkinkannya.
* **Infinity (`ProposedViewSize.infinity` / `width: .infinity, height: .infinity`)**: Parent menawarkan ruang seluas mungkin. Digunakan oleh container seperti `.frame(maxWidth: .infinity)`.
* **Concrete (`ProposedViewSize(width: CGFloat, height: CGFloat)`)**: Parent membatasi dimensi pada rentang angka pasti.

#### 3.4 AttributeGraph & Layout Invalidation
SwiftUI tidak memelihara pohon `UIView` yang persisten. SwiftUI mengompilasi representasi View menjadi runtime dependency graph yang disebut **AttributeGraph** (ditulis dalam C++). 
* Node dalam AttributeGraph mewakili data, modifier, atau layout state.
* Edge mewakili dependensi reaktif.
* Saat sebuah state berubah, AttributeGraph melakukan algoritma *dirty-marking* selektif hanya pada sub-graf yang terdampak.
* Layout engine kemudian mengeksekusi pass penataan ulang tanpa mengalokasikan ulang memori untuk struktur view primitif.

---

### 4. Why & What

| Dimensi | AutoLayout (UIKit) | SwiftUI Layout Protocol |
| :--- | :--- | :--- |
| **Algoritma Dasar** | Cassowary Constraint Solver | Pure Tree Traversal (Top-Down Proposal, Bottom-Up Sizing) |
| **Kompleksitas Komputasi**| Rata-rata $O(n)$, Terburuk $O(n^3)$ | Strictly $O(n)$ per pass layout |
| **Representasi State** | Mutable Constraint Objects (Stateful) | Pure Stateless Structs & Layout Descriptors |
| **Cache Management** | Manual update / AutoResizing masks | Built-in explicitly managed `Layout.Cache` engine |
| **Overhead Kompilasi** | Runtime string/anchor parsing | Compile-time static type system checking |
| **Biaya Hierarki Dalam** | Sering terjadi *exponential slowdown* | Linear degradation, aman untuk hierarki bertingkat dalam |

#### Mengapa Bukan `GeometryReader`?
`GeometryReader` sering disalahgunakan untuk membaca dimensi layar atau parent container. Namun secara arsitektur, `GeometryReader`:
1. Bersifat agresif (*greedy*): Memaksa mengambil seluruh ruang yang dialokasikan parent (`ProposedViewSize.infinity`).
2. Memicu eksekusi *layout pass* tambahan.
3. Menyebabkan *dependency cycles* jika nilai yang dibaca dari geometry langsung mengubah state yang mengontrol dimensi parent (`AttributeGraph cycle`).

`Layout` Protocol (diperkenalkan pada iOS 16+) hadir sebagai substitusi terisolasi yang menyediakan kontrol akses layout tingkat rendah tanpa mengubah geometri view parent dan tanpa overhead alokasi state view.

---

### 5. How (Workflow Detail)

Alur kerja implementasi sistem adaptif tingkat produksi:

```
[ Window Resize / Dynamic Type / Orientation Change ]
                          │
                          ▼
            [ Environment Propagation ]
      (horizontalSizeClass, dynamicTypeSize)
                          │
                          ▼
             [ Container Decisioning ]
    (ViewThatFits / Custom Layout Protocol Engine)
                          │
                          ▼
             [ Size Proposal & Sizing Pass ]
            sizeThatFits(proposal, subviews, cache)
                          │
                          ▼
              [ Placement Calculation ]
       placeSubviews(in, proposal, subviews, cache)
                          │
                          ▼
              [ AttributeGraph Flush ]
                          │
                          ▼
         [ Render Output to CoreAnimation ]
```

1. **Environment Invalidation**: Perubahan lingkungan runtime (misal: rotasi layar, split screen) memicu modifikasi variabel `@Environment`.
2. **Container Strategy Selection**: View memilih struktur layout terbaik melalui `ViewThatFits` atau layout kustom.
3. **Execution of `sizeThatFits`**: Container mengevaluasi seluruh subview untuk mengkalkulasi total *bounding box* menggunakan cache fungsional.
4. **Execution of `placeSubviews`**: Node container menentukan titik koordinat akhir setiap subview dengan memanfaatkan nilai *alignment guides* dan *coordinate spaces*.
5. **Flush ke Framebuffer**: AttributeGraph memperbarui CoreAnimation render tree untuk rendering 120 FPS yang mulus.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Negosiasi Kontrak Konstruksi
* **Parent View** = Kontraktor Utama. Parent membawa denah area dan mendatangi Subkontraktor: *"Saya punya kavling 400m x 200m. Berapa meter yang kamu butuhkan untuk membangun modul ini?"*
* **Child View** = Subkontraktor Spesialis. Child memeriksa cetak biru materialnya sendiri (intrinsic content size) dan menjawab: *"Saya hanya butuh 150m x 200m."*
* **Parent View Sizing Decision** = Kontraktor Utama mengangguk: *"Baik, ambil 150m x 200m. Dan letakkan fondasimu di koordinat X: 50, Y: 0."*

#### Diagram Arsitektur Layout Negosiasi
```
+-------------------------------------------------------------------------+
| Parent View: ProposedViewSize(width: 400, height: 200)                  |
|                                                                         |
|    +---------------------------+       +---------------------------+    |
|    | Subview A (Reluctant)     |       | Subview B (Greedy)        |    |
|    |                           |       |                           |    |
|    | 1. Propose: (w:200, h:200)|       | 1. Propose: (w:200, h:200)|    |
|    | 2. Returns: (w:80,  h:40) |       | 2. Returns: (w:200, h:200)|    |
|    | 3. Placed at: (x:0, y:80) |       | 3. Placed at: (x:80, y:0) |    |
|    +---------------------------+       +---------------------------+    |
+-------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Alignment Guide
Menyelaraskan dua elemen UI yang berada di luar hierarki stack yang sama tanpa menggunakan `GeometryReader`.

```swift
import SwiftUI

private extension HorizontalAlignment {
    enum CustomBadgeAlignment: AlignmentID {
        static func defaultValue(in context: ViewDimensions) -> CGFloat {
            context[HorizontalAlignment.center]
        }
    }
    static let customBadgeLeading = HorizontalAlignment(CustomBadgeAlignment.self)
}

struct SimpleAlignmentView: View {
    var body: some View {
        VStack(alignment: .customBadgeLeading, spacing: 16) {
            HStack {
                Text("Enterprise Subscription")
                    .font(.headline)
                    .alignmentGuide(.customBadgeLeading) { d in d[.leading] }
                Spacer()
                Text("Active")
            }
            .padding()
            .background(Color.secondary.opacity(0.1))
            
            HStack {
                Image(systemName: "shield.checkerboard")
                Text("Secured via AttributeGraph Engine")
                    .font(.caption)
                    .alignmentGuide(.customBadgeLeading) { d in d[.leading] }
            }
        }
        .padding()
    }
}
```

#### 7.2 Practical Example: Custom FlowLayout Menggunakan Layout Protocol
Layout berbasis baris yang secara dinamis memindahkan elemen ke baris berikutnya jika ruang horizontal tidak mencukupi (mirip flex-wrap), dilengkapi implementasi caching eksplisit.

```swift
import SwiftUI

public struct FlowLayout: Layout {
    public struct CacheData {
        var sizes: [CGSize]
        var lineBreaks: [Int]
        var totalSize: CGSize
    }

    public var horizontalSpacing: CGFloat
    public var verticalSpacing: CGFloat

    public init(horizontalSpacing: CGFloat = 8, verticalSpacing: CGFloat = 8) {
        self.horizontalSpacing = horizontalSpacing
        self.verticalSpacing = verticalSpacing
    }

    public func makeCache(subviews: Subviews) -> CacheData {
        CacheData(sizes: [], lineBreaks: [], totalSize: .zero)
    }

    public func updateCache(_ cache: inout CacheData, subviews: Subviews) {
        cache.sizes.removeAll(keepingCapacity: true)
        cache.lineBreaks.removeAll(keepingCapacity: true)
    }

    public func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout CacheData
    ) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var lineHeight: CGFloat = 0
        var maxRowWidth: CGFloat = 0

        cache.sizes = subviews.map { $0.sizeThatFits(.unspecified) }

        for (index, size) in cache.sizes.enumerated() {
            if currentX + size.width > maxWidth && currentX > 0 {
                cache.lineBreaks.append(index)
                currentY += lineHeight + verticalSpacing
                maxRowWidth = max(maxRowWidth, currentX - horizontalSpacing)
                currentX = 0
                lineHeight = 0
            }
            currentX += size.width + horizontalSpacing
            lineHeight = max(lineHeight, size.height)
        }

        currentY += lineHeight
        maxRowWidth = max(maxRowWidth, currentX - horizontalSpacing)
        cache.totalSize = CGSize(width: maxRowWidth, height: currentY)
        return cache.totalSize
    }

    public func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout CacheData
    ) {
        var currentX: CGFloat = bounds.minX
        var currentY: CGFloat = bounds.minY
        var lineHeight: CGFloat = 0
        var lineBreakIndex = 0

        for (index, subview) in subviews.enumerated() {
            if lineBreakIndex < cache.lineBreaks.count && index == cache.lineBreaks[lineBreakIndex] {
                currentY += lineHeight + verticalSpacing
                currentX = bounds.minX
                lineHeight = 0
                lineBreakIndex += 1
            }

            let size = cache.sizes[index]
            subview.place(
                at: CGPoint(x: currentX, y: currentY),
                anchor: .topLeading,
                proposal: ProposedViewSize(size)
            )

            lineHeight = max(lineHeight, size.height)
            currentX += size.width + horizontalSpacing
        }
    }
}
```

---

### 8. Real World Case Study: Adaptive Financial Analytics Dashboard

#### Skenario Enterprise
Aplikasi perbankan investasi membutuhkan modul dashboard analitik instrumen keuangan. 
* Pada iPhone portrait: Tampilan stacked vertikal, grafik terkompresi, metriks horizontal scrollable.
* Pada iPadOS (Stage Manager) & macOS: Tampilan multi-kolom asimetris adaptif dengan container data real-time streaming tanpa re-rendering grafis menyeluruh.

#### Implementasi Arsitektur

```swift
import SwiftUI

// MARK: - Layout State Key Preferences
struct ComponentMetricsPreferenceKey: PreferenceKey {
    typealias Value = [String: CGRect]
    static var defaultValue: [String: CGRect] = [:]
    
    static func reduce(value: inout [String: CGRect], nextValue: () -> [String: CGRect]) {
        value.merge(nextValue(), uniquingKeysWith: { $1 })
    }
}

// MARK: - Adaptive Engine Strategy
struct AdaptiveFinancialDashboard: View {
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @State private var elementFrames: [String: CGRect] = [:]

    var isCompact: Bool {
        horizontalSizeClass == .compact || dynamicTypeSize >= .accessibility1
    }

    var body: some View {
        ViewThatFits(in: .horizontal) {
            // Priority 1: Multi-column Split Layout (Desktop / iPad Fullscreen)
            WideDashboardLayout(spacing: 16) {
                MetricsSection()
                ChartSection()
                OrderBookSection()
            }
            
            // Priority 2: Balanced Two-Column (iPad Split View / Compact Landscape)
            MediumDashboardLayout(spacing: 12) {
                MetricsSection()
                ChartSection()
                OrderBookSection()
            }
            
            // Priority 3: Fallback Strict Single-Column (iPhone Portrait / Accessibility Mode)
            VerticalDashboardFallback {
                MetricsSection()
                ChartSection()
                OrderBookSection()
            }
        }
        .coordinateSpace(name: "DashboardCoordinateSpace")
        .onPreferenceChange(ComponentMetricsPreferenceKey.self) { preferences in
            self.elementFrames = preferences
        }
    }
}

// MARK: - Specialized Layout Implementations
struct WideDashboardLayout: Layout {
    var spacing: CGFloat
    
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        guard subviews.count >= 3 else { return .zero }
        let totalWidth = proposal.width ?? 1200
        let targetHeight: CGFloat = 600
        return CGSize(width: totalWidth, height: targetHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard subviews.count >= 3 else { return }
        
        let availableWidth = bounds.width - (spacing * 2)
        let leftColWidth = availableWidth * 0.25
        let centerColWidth = availableWidth * 0.50
        let rightColWidth = availableWidth * 0.25
        
        // Col 1: Metrics
        subviews[0].place(
            at: bounds.origin,
            proposal: ProposedViewSize(width: leftColWidth, height: bounds.height)
        )
        // Col 2: High Frequency Chart
        subviews[1].place(
            at: CGPoint(x: bounds.minX + leftColWidth + spacing, y: bounds.minY),
            proposal: ProposedViewSize(width: centerColWidth, height: bounds.height)
        )
        // Col 3: Order Book
        subviews[2].place(
            at: CGPoint(x: bounds.minX + leftColWidth + centerColWidth + (spacing * 2), y: bounds.minY),
            proposal: ProposedViewSize(width: rightColWidth, height: bounds.height)
        )
    }
}

struct MediumDashboardLayout: Layout {
    var spacing: CGFloat
    
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 800
        return CGSize(width: width, height: 900)
    }
    
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        // Implementasi distribusi dua kolom
    }
}

struct VerticalDashboardFallback: View {
    @ViewBuilder var content: () -> AnyView
    
    init<V0: View, V1: View, V2: View>(@ViewBuilder content: () -> TupleView<(V0, V1, V2)>) {
        let views = content()
        self.content = {
            AnyView(
                VStack(spacing: 16) {
                    views.value.0
                    views.value.1
                    views.value.2
                }
            )
        }
    }

    var body: some View {
        ScrollView(.vertical) {
            content()
                .padding()
        }
    }
}

// Dummy presentation primitives for synthesis
struct MetricsSection: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(Color.blue.opacity(0.15))
            .overlay(Text("Metrics Core Engine").font(.headline))
            .frame(minHeight: 150)
    }
}

struct ChartSection: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(Color.green.opacity(0.15))
            .overlay(Text("High-Frequency Tick Graph").font(.headline))
            .frame(minHeight: 300)
    }
}

struct OrderBookSection: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(Color.orange.opacity(0.15))
            .overlay(Text("Real-Time Order Flow").font(.headline))
            .frame(minHeight: 200)
    }
}
```

---

### 9. Trade-offs

| Pendekatan Layout | Keuntungan (Pros) | Konsekuensi & Risiko (Cons) | Dampak Performa / Resource |
| :--- | :--- | :--- | :--- |
| **Custom `Layout` Protocol** | Kalkulasi layout deterministik, $O(n)$ time complexity, isolasi alokasi memory via `Cache`. | Kompleksitas kode tinggi; ketiadaan animasi transisi bawaan antar pass sizing manual. | **Sangat Ringan**: 0 allocation overhead jika cache dioptimalkan. 120 FPS target. |
| **`ViewThatFits` Engine** | Deklaratif murni, penanganan multi-resolusi otomatis tanpa dependensi state eksternal. | Mengevaluasi semua subview di dalamnya secara eager hingga menemukan yang muat. | **Moderat**: Potensial komputasi sizing ganda untuk view yang dievaluasi namun dibuang. |
| **`PreferenceKey` Extraction** | Mengalirkan child layout metadata naik hierarki secara terstruktur. | Resiko siklus tak hingga (*Infinite Layout Loop*) jika state diperbarui dalam render pass. | **Tinggi**: Menyebabkan *two-pass layout rendering* minimum. |
| **`GeometryReader` Primitives** | Memberikan koordinat lokal, global, dan safe area secara instan. | Mengubah layout behavior child menjadi *greedy*, merusak flow fleksibel stack container. | **Kritis**: Pemborosan memory pipeline CoreAnimation jika disarangkan (*nested*). |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus 1: AttributeGraph Infinite Invalidation Loop via Preferences
* **Gejala**: CPU usage 100%, Xcode console memuntahkan warning terus-menerus: `Bound preference key tried to update multiple times per frame`.
* **Akar Masalah**: Mengupdate `@State` di dalam `.onPreferenceChange` yang secara langsung atau tidak langsung mengubah ukuran child view yang memancarkan preference tersebut.
* **Solusi**: Putus dependensi ukuran terhadap state tersebut, atau gunakan custom `Layout` protocol agar pengukuran dan penataan terjadi dalam komputasi layout pass murni tanpa modifikasi SwiftUI View State.

```swift
// ANTI-PATTERN: Memicu Layout Thrashing Loop
.background(
    GeometryReader { proxy in
        Color.clear.preference(key: HeightKey.self, value: proxy.size.height)
    }
)
.onPreferenceChange(HeightKey.self) { newHeight in
    self.parentHeight = newHeight // MUTASI STATE MEMICU RE-EVALUATION BODY SECARA TAK HINGGA
}
```

#### Kasus 2: Pixel Blurring Karena Manual Offset Calculation
* **Gejala**: Teks dan border tipis tampak buram (*fuzzy*) pada display Retina non-3x.
* **Akar Masalah**: Menghitung titik koordinat dengan pembagian angka ganjil (`width / 2.0`) yang menghasilkan nilai sub-pixel fractional (misal: 12.333 pt) tanpa normalisasi skala layar.
* **Solusi**: Gunakan pixel snapping berbasis display scale:

```swift
// SOLUSI: Core Graphics Pixel Snapping Extension
extension CGFloat {
    func pixelAligned(scale: CGFloat) -> CGFloat {
        return (self * scale).rounded() / scale
    }
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Gantikan `GeometryReader` Global**: Verifikasi hierarki tidak menggunakan `GeometryReader` selain untuk rendering grafik berbasis path murni atau shader effects.
- [ ] **Optimasi Container Adaptif**: Gunakan `ViewThatFits` untuk skenario adaptasi ukuran terbatas daripada mengandalkan kombinasi `UIScreen.main.bounds` yang melanggar isolasi windowing iPadOS.
- [ ] **Dynamic Type Resilience**: Pastikan seluruh container teks menggunakan `minimumScaleFactor` atau bertransformasi ke arah `VStack` vertikal jika `dynamicTypeSize.isAccessibilitySize` bernilai `true`.
- [ ] **Cache Implementation di Custom Layout**: Selalu implementasikan `makeCache` dan `updateCache` pada implementasi `Layout` kompleks untuk menghindari alokasi ulang array `CGSize` di setiap frame animasi.
- [ ] **Safe Area Management**: Pisahkan dekorasi background menggunakan `.ignoresSafeArea()` murni pada layer background tanpa memperluas layout interaktif keluar dari margin interaksi aman pengguna.

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum ini pada direktori proyek lokal di `hands-on/m02/`.

#### Langkah 1: Inisialisasi Proyek Swift Package
Buka Terminal dan eksekusi struktur scaffold berikut:
```bash
mkdir -p hands-on/m02/AdaptiveLayoutEngine
cd hands-on/m02/AdaptiveLayoutEngine
swift package init --type library
```

#### Langkah 2: Mengembangkan Asymmetric Mosaic Layout
Buat file `Sources/AdaptiveLayoutEngine/MosaicLayout.swift`:

```swift
import SwiftUI

public struct MosaicLayout: Layout {
    public struct CacheData {
        var frames: [CGRect] = []
    }

    public var spacing: CGFloat

    public init(spacing: CGFloat = 8) {
        self.spacing = spacing
    }

    public func makeCache(subviews: Subviews) -> CacheData {
        CacheData()
    }

    public func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout CacheData
    ) -> CGSize {
        let width = proposal.width ?? 400
        calculateFrames(width: width, subviews: subviews, cache: &cache)
        let totalHeight = cache.frames.map(\.maxY).max() ?? 0
        return CGSize(width: width, height: totalHeight)
    }

    public func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout CacheData
    ) {
        for (index, subview) in subviews.enumerated() {
            guard index < cache.frames.count else { break }
            let frame = cache.frames[index]
            subview.place(
                at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY),
                proposal: ProposedViewSize(frame.size)
            )
        }
    }

    private func calculateFrames(width: CGFloat, subviews: Subviews, cache: inout CacheData) {
        cache.frames.removeAll(keepingCapacity: true)
        let usableWidth = width - spacing
        let largeCellWidth = usableWidth * 0.65
        let smallCellWidth = usableWidth * 0.35
        
        var yOffset: CGFloat = 0
        var i = 0

        while i < subviews.count {
            // Evaluasi pasangan ganjil-genap untuk membentuk pola asimetris
            if i + 1 < subviews.count {
                let cellHeight: CGFloat = 120
                if (i / 2) % 2 == 0 {
                    // Kiri besar, kanan kecil
                    cache.frames.append(CGRect(x: 0, y: yOffset, width: largeCellWidth, height: cellHeight))
                    cache.frames.append(CGRect(x: largeCellWidth + spacing, y: yOffset, width: smallCellWidth, height: cellHeight))
                } else {
                    // Kiri kecil, kanan besar
                    cache.frames.append(CGRect(x: 0, y: yOffset, width: smallCellWidth, height: cellHeight))
                    cache.frames.append(CGRect(x: smallCellWidth + spacing, y: yOffset, width: largeCellWidth, height: cellHeight))
                }
                yOffset += cellHeight + spacing
                i += 2
            } else {
                // Sisa 1 elemen terakhir: Ambil lebar penuh
                cache.frames.append(CGRect(x: 0, y: yOffset, width: width, height: 100))
                yOffset += 100 + spacing
                i += 1
            }
        }
    }
}
```

#### Langkah 3: Menjalankan Testing Visual
Uji coba implementasi layout di canvas target atau executable host app untuk memverifikasi penataan asimetris dan integritas cache.

---

### 13. Exercise

#### Level 1 (Easy): Adaptive Tag Capsule Stack
* **Problem**: Buat komponen `TagCloudView` menggunakan `FlowLayout` dari seksi 7.2.
* **Requirements**: Menerima array `[String]`, merender teks dalam bentuk kapsul (`Capsule`), dan membungkus tag ke baris baru ketika mencapai batas container proposal.

#### Level 2 (Medium): Dynamic Radial/Circular Menu
* **Problem**: Buat komponen kustom yang mengadopsi `Layout` protocol bernama `RadialMenuLayout`.
* **Requirements**: Mengatur seluruh child subviews dalam formasi lingkaran sempurna secara simetris ($360^\circ / N$). Menerima parameter konfigurasi `radius: CGFloat` dan mengalokasikan ukuran total container sebesar `(radius * 2) x (radius * 2)`.

#### Level 3 (Hard): Sticky Collapsible Section Header Engine
* **Problem**: Kembangkan sistem layout tanpa `GeometryReader` yang membaca scroll-offset menggunakan `AnchorPreferences` dan `CoordinateSpace`.
* **Requirements**: Saat child discroll melewati threshold safe-area atas, layout mengecilkan header dari skala 1.0 ke skala 0.6 dan menerapkan efek material backdrop secara halus tanpa memicu re-render pada body container scrollable content.

---

### 14. Challenge

#### Skenario: Multi-Lane Kanban Engine dengan Dynamic Self-Balancing

**Konteks**: Anda adalah Principal Mobile Architect pada platform Enterprise Task Management. Aplikasi membutuhkan antarmuka Kanban Board adaptif multi-kolom yang mampu beroperasi dari perangkat iPhone (single column paging) hingga iPad Pro 12.9" dan Mac Pro Ultra Display (hingga 6 kolom swimlane paralel).

**Spesifikasi Kritis & Batasan Arsitektural**:
1. **Zero-Lag Dynamic Re-balancing**: Buat custom layout bernama `KanbanBoardLayout: Layout`. Engine harus mampu membagi proporsi kolom secara dinamis berdasarkan parameter `minColumnWidth: CGFloat = 280` dan `maxColumnWidth: CGFloat = 400`. Jika layar ditarik, engine harus menyeimbangkan ulang lebar antar kolom dalam fraksi milidetik tanpa merusak state scrolling vertikal masing-masing list internal.
2. **Prohibition Constraints**: 
   * Dilarang keras menggunakan `GeometryReader` di seluruh modul Kanban.
   * Dilarang melakukan update `@State` internal selama proses kalkulasi di `sizeThatFits` dan `placeSubviews`.
3. **Cache Invalidation Architecture**: Rancang struktur `CacheData` pada `KanbanBoardLayout` yang dapat mendeteksi apakah data mutasi murni berasal dari pergeseran pixel parent window (tidak perlu kalkulasi ulang subview items) atau berasal dari penambahan item task baru (memerlukan recalculation total).
4. **Dynamic Type Survivability**: Saat pengguna mengaktifkan mode *Accessibility Large Fonts*, board harus secara anggun menonaktifkan sifat multi-kolom horizontalnya dan bertransformasi menjadi *Segmented Vertical Paging System* untuk mempertahankan standar WCAG 2.1 AAA Compliance.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic (Pilihan Ganda)
1. Kapan `ProposedViewSize.unspecified` dikirimkan oleh parent view ke child view?
   - A. Saat parent view berukuran `0 x 0`.
   - B. Saat parent view ingin mengetahui ukuran intrinsik ideal child tanpa batasan paksaan.
   - C. Saat parent view mengalami kegagalan memori alokasi.
   - D. Saat child view dibungkus oleh modifier `.frame(maxWidth: .infinity)`.

2. Apa kompleksitas komputasi penataan hierarchy view pada layout engine SwiftUI per pass?
   - A. $O(n^3)$
   - B. $O(n \log n)$
   - C. $O(n)$
   - D. $O(1)$

3. Mengapa penggunaan `GeometryReader` di dalam `VStack` yang tidak memiliki fixed-frame dapat mengubah struktur tampilan?
   - A. Karena `GeometryReader` mengabaikan safe area secara default.
   - B. Karena `GeometryReader` memiliki sifat layout yang rakus (*greedy*) dan mengambil seluruh proposal dimensi tak terhingga parent.
   - C. Karena `GeometryReader` secara otomatis merender view ke dalam bitmap terkompresi.
   - D. Karena `GeometryReader` menurunkan prioritas layout child view menjadi nol.

4. Kapan metode `makeCache(subviews:)` pada custom `Layout` protocol dipanggil?
   - A. Setiap 60/120 kali per detik di setiap frame refresh CoreAnimation.
   - B. Hanya saat inisialisasi awal hierarki subview, atau saat komposisi koleksi subview mengalami mutasi struktural.
   - C. Hanya ketika perangkat berotasi dari portrait ke landscape.
   - D. Ketika pengguna menyentuh komponen subview.

5. Apa fungsi dari modifier `.alignmentGuide` dalam siklus layout SwiftUI?
   - A. Memaksa parent view untuk merentang selebar ukuran layar.
   - B. Mengubah offset fisik CoreAnimation layer tanpa mengubah frame komputasi layout.
   - C. Menimpa titik anchor layout spesifik dari sebuah view untuk dicocokkan dengan panduan alignment container parent.
   - D. Menghapus margin padding bawaan antar elemen teks.

#### Soal Intermediate (Pilihan Ganda)
6. Bagaimana cara kerja internal `ViewThatFits` dalam memilih tampilan terbaik?
   - A. Memilih subview pertama yang ukuran intrinsiknya muat ke dalam dimensi proposal yang diberikan parent, dievaluasi dari atas ke bawah.
   - B. Mengukur semua child subviews secara paralel dan memilih subview dengan rasio memory footprint terendah.
   - C. Merender semua subview secara bersamaan dan mengatur nilai alpha subview yang tidak muat menjadi 0.
   - D. Membagi ukuran parent rata secara simetris untuk semua subview yang didaftarkan.

7. Perhatikan kode berikut:
   ```swift
   Color.red
       .frame(width: 100)
       .frame(width: 200)
   ```
   Berapa dimensi lebar akhir dari `Color.red` yang dirender di layar?
   - A. 200 pt.
   - B. 100 pt.
   - C. 300 pt.
   - D. 150 pt.

8. Apa implikasi teknis dari mutasi state lokal `@State` di dalam callback closure `.onPreferenceChange`?
   - A. State mutasi tersebut akan diabaikan secara diam-diam oleh runtime SwiftUI.
   - B. Layout pass kedua dipicu secara instan. Jika perubahan state tersebut mempengaruhi dimensi elemen yang membangkitkan preference, aplikasi terjebak dalam *infinite layout cycle*.
   - C. Memori grafik dialokasikan ganda pada Metal pipeline, mengakibatkan Out-Of-Memory (OOM) seketika.
   - D. Nilai koordinat global dari view tersebut di-reset kembali ke titik `(0,0)`.

9. Di dalam method `placeSubviews` pada `Layout` protocol, parameter `anchor` berfungsi untuk:
   - A. Menentukan titik pusat rotasi 3D matrix.
   - B. Mendefinisikan titik referensi pada child view yang akan ditempatkan tepat pada koordinat posisi yang ditentukan.
   - C. Mengunci subview agar posisinya statis terhadap scroll delta.
   - D. Menghubungkan subview ke root window screen anchor.

10. Mengapa perhitungan alignment berbasis floating-point division wajib dinormalisasi menggunakan skala layar fisik (`screen.scale`)?
    - A. Untuk menghindari komputasi NaN (*Not a Number*) pada arsitektur CPU ARM64.
    - B. Untuk mencegah cacat visual akibat penempatan elemen di tengah boundary physical pixel (*pixel straddling/anti-aliasing blurring*).
    - C. Karena CoreAnimation menolak angka bertipe data `CGFloat` di luar format integer.
    - D. Agar framework SwiftUI tidak melempar pengecualian fatal runtime assertion.

#### Skenario Kasus Produksi
11. **Skenario Kasus A**: 
    Tim Anda merilis aplikasi perbankan enterprise. Pada saat fitur baru digulirkan, terjadi lonjakan laporan crash di sentry dengan log: `AttributeGraph: cycle detected through attribute 42084`. Identifikasi mekanisme internal yang memicu error ini dan tentukan langkah remediasi arsitektural yang paling mutlak.
    
12. **Skenario Kasus B**:
    Sebuah list transaksi dengan 500 item diuji menggunakan Xcode Instruments (Core Animation FPS & Time Profiler). Hasil analisis menunjukkan frame rate anjlok dari 120 FPS ke 42 FPS saat scrolling cepat. Setiap row transaksi memiliki badge yang dibungkus oleh layout engine berbasis `GeometryReader` bersarang yang membaca koordinat global untuk analytics tracking. Jelaskan apa yang terjadi pada *CoreAnimation display pipeline* dan deskripsikan solusinya.

13. **Skenario Kasus C**:
    Anda merancang layout form checkout pembayaran multi-mata uang yang harus tampil responsif di mode Split View iPad (1/3 view, 1/2 view, 2/3 view) dan dynamic orientation. Desainer menginginkan form bertransisi mulus dari 2-kolom horizontal menjadi 1-kolom vertikal tanpa merusak nilai input data text field yang sedang diketik user. Mengapa penggunaan percabangan `if-else` deklaratif standar (`if horizontalSizeClass == .compact { VStack } else { HStack }`) dapat merusak state teks field input user, dan bagaimana cara mengatasi masalah ini secara murni struktural?

---

### Kunci Jawaban & Pembahasan Quiz

#### Jawaban Soal Basic
1. **B**: `ProposedViewSize.unspecified` mengirimkan sinyal kepada child view untuk menentukan ukuran idealnya sendiri tanpa paksaan dari parent container (misalnya di dalam viewport `ScrollView`).
2. **C**: Arsitektur internal SwiftUI traversal berbasis pohon satu arah secara strictly menjamin efisiensi linear $O(n)$ per pass, berbeda drastis dari Cassowary $O(n^3)$ di AutoLayout.
3. **B**: `GeometryReader` secara internal bertindak sebagai greedy container, menerima ukuran dimensi infinity dari parent proposal sehingga merusak flow dinamis yang dibutuhkan parent layout.
4. **B**: `makeCache` hanya dieksekusi saat inisialisasi awal dari hierarki subviews atau saat terjadi perubahan identitas struktural subviews, bukan di setiap frame rendering.
5. **C**: `.alignmentGuide` secara spesifik mengesampingkan kalkulasi letak titik komputasi dimensi tertentu (leading, trailing, center) relatif terhadap layout parent.

#### Jawaban Soal Intermediate
6. **A**: `ViewThatFits` secara sekuensial mengevaluasi daftar view deklaratif yang diberikan dan memilih view pertama yang validitas dimensinya memenuhi ruang proposal.
7. **B**: Evaluasi layout frame berlangsung dari luar ke dalam (outside-in untuk proposal, inside-out untuk sizing). Modifier `.frame(width: 100)` paling dalam mengembalikan ukuran konkret 100 pt secara independen kepada frame 200 pt di atasnya, sehingga ukuran child view yang dirender tetap berukuran 100 pt di tengah area alokasi 200 pt.
8. **B**: Mutasi state SwiftUI di dalam lifecycle feedback preference dapat memicu cascade invalidation jika ukuran child dependent pada nilai state tersebut.
9. **B**: `anchor` menentukan titik referensi penempatan spesifik (misal: `.topLeading`, `.center`) dari child bounding box terhadap koordinat point target.
10. **B**: Nilai fractional sub-pixel membagi intensitas cahaya pada physical pixel boundary, menghasilkan tampilan teks dan border yang buram (*blurry edge*).

#### Pembahasan Skenario Kasus Produksi
11. **Pembahasan Skenario A**: 
    Crash `AttributeGraph: cycle detected` terjadi karena adanya relasi sirkular dependensi dalam runtime graph. Contoh umum: Subview A mengubah PreferenceKey -> Ditangkap oleh Parent View -> Parent View memperbarui State -> State mengubah parameter layout Subview A -> Subview A kembali mengubah PreferenceKey dalam frame render yang sama. **Remediasi**: Hentikan sinkronisasi layout dimensi melalui `@State`. Pindahkan logika sizing langsung ke tingkat mesin menggunakan custom `Layout` protocol, di mana ukuran ditentukan murni melalui fungsi matematis fungsional `sizeThatFits` tanpa modifikasi status view reaktif.

12. **Pembahasan Skenario B**:
    Penurunan performa hingga 42 FPS disebabkan oleh *Layout Thrashing*. Kehadiran `GeometryReader` di setiap baris cell memaksa SwiftUI keluar dari optimasi layout 1-pass standar dan memaksa eksekusi layout multipass tambahan untuk setiap node baris. Penggunaan koordinat global menyebabkan invalidasi parsial pohon display tree secara konstan selama scrolling. **Remediasi**: Buang seluruh instance `GeometryReader` dari sel list. Gunakan `UICollectionViewLayout` bridge atau Custom `Layout` SwiftUI protocol. Untuk pelacakan analytics scroll impression, manfaatkan modifier non-intrusif seperti `.scrollPosition` (iOS 17+) atau `onScrollGeometryChange`.

13. **Pembahasan Skenario C**:
    Percabangan deklaratif struktural `if-else` (`if sizeClass == .compact { VStack } else { HStack }`) mengubah *structural identity* dari subview hierarki di mata AttributeGraph. Akibatnya, SwiftUI menganggap textfield pada `VStack` adalah node yang sama sekali baru dan menghancurkan node lama pada `HStack`, menghapus seluruh transient state memori lokal (isi teks input, status first responder keyboard). **Remediasi**: Pertahankan identitas struktural stabil (*structural identity preservation*) dengan menggunakan custom `Layout` engine (misal: `AnyLayout(isCompact ? VStackLayout() : HStackLayout())`) atau menggunakan `ViewThatFits` dengan view identity tags persisten, sehingga hanya layout strategy engine yang berganti tanpa membongkar instance representasi memori child text field.

---

### 16. Summary

Layout Engine SwiftUI menandai pergeseran paradigma dari *constraint solving engine* (Cassowary/UIKit) yang berat dan berpotensi eksponensial menuju sistem *one-pass tree traversal negotiation* deterministik $O(n)$ berbasis top-down proposal dan bottom-up sizing.

Untuk membangun aplikasi berskala enterprise yang tangguh:
* **Hentikan ketergantungan pada `GeometryReader`**: Gunakan `Layout` Protocol, `ViewThatFits`, dan Custom Alignment Guides sebagai gantinya.
* **Jaga Structural Identity**: Hindari penggunaan percabangan `if-else` untuk transformasi layout adaptif agar transient state dan focus state elemen antarmuka tidak terhapus.
* **Isolasi Logika Layout dari State**: Gunakan komputasi layout murni melalui caching `Layout` protocol untuk mencegah pembentukan dependensi sirkular pada **AttributeGraph** yang memicu *infinite layout cycles* dan *frame drops*.