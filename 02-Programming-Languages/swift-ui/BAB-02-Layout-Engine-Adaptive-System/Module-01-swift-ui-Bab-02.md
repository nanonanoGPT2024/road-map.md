# Bab 02 Module 01: Layout Engine & Adaptive System

---

## SEKSI 01 — IDENTITAS MODUL

* **Domain Kurikulum:** Pemrograman Deklaratif & Rekayasa Antarmuka iOS
* **Trek:** Apple Ecosystem Engineering (`swift-ui`)
* **Kategori:** 02-Programming-Languages
* **Modul:** Bab 02 Module 01 — Layout Engine & Adaptive System
* **Tingkat Kesulitan:** Advanced / Senior Level
* **Prasyarat:** Pemahaman mendalam tentang Swift Type System (Generics, Protocols, Opaque Return Types `some View`), Value Semantics, State-driven Rendering Lifecycle, dan dasar-dasar View hierarchy di SwiftUI.
* **Target Platform:** iOS 16.0+, iPadOS 16.0+, macOS 13.0+ (Menggunakan modern Layout API)

---

## SEKSI 02 — LEARNING OBJECTIVES

1. **Mendekonstruksi 3-Step Layout Negotiation:** Memahami secara matematis dan prosedural bagaimana parent view mengajukan proposal ukuran, child view menentukan ukurannya sendiri secara berdaulat, dan parent view memposisikan child view.
2. **Menguasai Protokol `Layout` (iOS 16+):** Mengimplementasikan algoritma layout 2D kustom yang deterministik menggunakan `sizeThatFits(proposal:subviews:cache:)` dan `placeSubviews(in:proposal:subviews:cache:)`.
3. **Mencegah Anti-Pattern `GeometryReader`:** Menggantikan pembacaan geometri imperatif dengan declarative primitives seperti `ViewThatFits`, `layoutPriority(_:)`, dan Alignment Guides.
4. **Membangun Sistem Adaptif Multi-Platform:** Merekayasa antarmuka responsif yang beradaptasi secara mulus terhadap `UserInterfaceSizeClass`, Dynamic Type accessibility scaling, orientasi layar, dan split-screen multitasking tanpa frame drops.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Auto Layout (Imperatif) vs SwiftUI Layout Engine (Deklaratif)

Di era UIKit/Auto Layout, antarmuka adalah sistem persamaan linear yang diselesaikan oleh mesin runtime Cassowary ($O(n^3)$ worst-case). Anda mendefinisikan batasan (*constraints*) eksternal, dan sistem memaksakan frame kepada view.

Di SwiftUI, tata letak adalah proses negosiasi berbasis rekursif murni fungsional ($O(n)$):

```
Parent View: "Ini ruang yang saya miliki (ProposedViewSize). Berapa ukuran yang kamu inginkan?"
Child View:  "Berdasarkan batasan internal dan anak-anak saya, ukuran saya adalah persis W x H."
Parent View: "Baik. Saya menempatkan kamu pada koordinat (X, Y) di ruang koordinat saya."
```

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTO LAYOUT (UIKit)                      │
│                                                             │
│   Solver Cassowary <--- [Constraints: Top, Bottom, Leading] │
│           │                                                 │
│           ▼                                                 │
│   Memaksa Frame Child (Child TIDAK memiliki kedaulatan)     │
└─────────────────────────────────────────────────────────────┘
                              VS
┌─────────────────────────────────────────────────────────────┐
│                   SWIFTUI LAYOUT ENGINE                     │
│                                                             │
│   Parent View ──── Proposes Size (Unspecified/Exact) ───►   │
│                                                          │  │
│   Child View  ◄─── Menentukan Ukuran Sendiri (Sovereign) ┘  │
│        │                                                    │
│        ▼                                                    │
│   Parent View memposisikan Child pada Canvas miliknya       │
└─────────────────────────────────────────────────────────────┘
```

**Aturan Emas:**
*Child view memiliki kedaulatan penuh atas ukurannya sendiri.* Parent tidak dapat memaksakan ukurannya kepada child, kecuali jika parent secara eksplisit memotong (*clipping*) frame tersebut.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur rekursif negosiasi tata letak dieksekusi dari root window hingga leaf views, kemudian dipropagasi kembali ke atas untuk menghitung frame akhir.

```
+-----------------------------------------------------------------------------+
|                          FASE 1: SIZE PROPOSAL                              |
|                          (Root ke Leaf / Top-Down)                          |
+-----------------------------------------------------------------------------+
                                       │
                                       ▼
                       +-------------------------------+
                       |          Window Root          |
                       |    (Proposes Screen Size)     |
                       +---------------+---------------+
                                       │
                                       │ ProposedViewSize(w: 393, h: 852)
                                       ▼
                       +-------------------------------+
                       |          VStack / ZStack      |
                       +---------------+---------------+
                                       │
                        Proposes Size  │ (Dikurangi Spacing & Non-flexible child)
                                       ▼
                       +-------------------------------+
                       |     Flexible Child (Leaf)     |
                       +-------------------------------+
                                       │
                                       │
+-----------------------------------------------------------------------------+
|                          FASE 2: SIZE DETERMINATION                         |
|                          (Leaf ke Root / Bottom-Up)                         |
+-----------------------------------------------------------------------------+
                                       │
                                       ▼
                       +-------------------------------+
                       |     Child Menentukan Ukuran   |
                       |     Returns: CGSize(w, h)     |
                       +---------------+---------------+
                                       │
                                       │ Resolved Size (CGSize)
                                       ▼
                       +-------------------------------+
                       |  Parent Menghitung Bounding   |
                       |      Box Semua Child          |
                       +---------------+---------------+
                                       │
                                       │ Computed Size
                                       ▼
                       +-------------------------------+
                       |       Root Mengonfirmasi      |
                       +-------------------------------+
                                       │
                                       │
+-----------------------------------------------------------------------------+
|                          FASE 3: PLACEMENT & RENDERING                      |
|                          (Top-Down Coordinate Origin)                       |
+-----------------------------------------------------------------------------+
                                       │
                                       ▼
                       +-------------------------------+
                       |  Parent Menempatkan Child:    |
                       |  child.place(at: CGPoint, ...)│
                       +-------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Struktur Negosiasi Internal

Secara internal, layout engine beroperasi di atas tipe `ProposedViewSize`. Tipe ini membungkus dua nilai `Optional<CGFloat>` untuk lebar (`width`) dan tinggi (`height`).

```swift
public struct ProposedViewSize: Equatable, Sendable {
    public var width: CGFloat?
    public var height: CGFloat?

    public static let zero = ProposedViewSize(width: 0, height: 0)
    public static let infinity = ProposedViewSize(width: .infinity, height: .infinity)
    public static let unspecified = ProposedViewSize(width: nil, height: nil)
}
```

Tiga skenario proposal ukuran:
1. **Fully Specified (`ProposedViewSize(width: 300, height: 100)`):** Parent menawarkan dimensi pasti. Child fleksibel akan mengadopsinya, child kaku (*inflexible*) mungkin menolaknya.
2. **Unspecified (`ProposedViewSize.unspecified` / `nil`):** Parent menanyakan: *"Berapa ukuran intrinsik alamimu jika ruang tidak terbatas?"* (Berguna untuk menghitung ukuran teks dinamis atau gambar).
3. **Zero / Infinity:** Digunakan untuk probe kompresi minimum atau ekspansi maksimum.

### Tiga Kategori View Berdasarkan Perilaku Ukuran

1. **Neutral Views:** Mengambil ukuran persis dari child-nya (contoh: `Group`, container transparan).
2. **Greedy / Expanding Views:** Memperbesar ukuran hingga batas maksimum proposal parent (contoh: `Color`, `Spacer`, `Rectangle`). Jika menerima `infinity`, mereka akan mengisinya.
3. **Shrinking / Inflexible Views:** Mempertahankan ukuran intrinsiknya terlepas dari tawaran parent (contoh: `Image`, `Text` yang tidak menggunakan `.flexible`).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. The Stack Layout Algorithm (`HStack` & `VStack`)

Algoritma internal stack membagi ruang horizontal/vertikal kepada anak-anaknya melalui langkah-langkah deterministik berikut:

1. **Eliminasi Spacing:** Kurangi total ruang yang tersedia dengan akumulasi *spacing* antar-child.
2. **Pemberian Ukuran Child Inflexible:** Identifikasi child yang tidak dapat berubah ukurannya. Tanyakan ukuran intrinsiknya via proposal `unspecified`. Kurangi ruang yang tersisa.
3. **Penyortiran Fleksibilitas Berdasarkan `layoutPriority(_:)`:**
   - Child dengan prioritas layout lebih tinggi dialokasikan ruang terlebih dahulu. Nilai bawaan adalah `0.0`.
4. **Alokasi Adil (*Fair-Share Allocation*):**
   - Ambil sisa ruang, bagi secara merata dengan jumlah child tersisa:
   $$\text{Ruang Tawaran} = \frac{\text{Sisa Ruang}}{\text{Jumlah Sisa Child}}$$
   - Ajukan penawaran kepada child paling tidak fleksibel di antara sisa child.
   - Child tersebut mengembalikan ukuran yang ia klaim.
   - Kurangi total ruang yang tersedia dengan klaim aktual tersebut, kurangi sisa jumlah child dengan 1.
   - Ulangi proses ini secara iteratif hingga seluruh child selesai dievaluasi.

### 2. Alignment Guides & Layout Dimensional Math

Alignment guide bukan sekadar enum (`.leading`, `.center`, `.trailing`). Secara internal, alignment guide adalah nilai titik skalar (`CGFloat`) pada sumbu 1D yang dihitung terhadap koordinat lokal sebuah view.

Ketika dua view disejajarkan secara `.top`, layout engine menghitung offset lokal dari masing-masing child untuk menyamakan posisi absolut guide tersebut pada canvas parent:

$$\Delta Y = \text{Guide}_{\text{Child 1}} - \text{Guide}_{\text{Child 2}}$$

### 3. Protokol Modern: `Layout` (SwiftUI 4+ / iOS 16+)

Protokol `Layout` mengabstraksi mesin layout di tingkat subview tanpa memerlukan manipulasi UIKit `UIView` atau wrapping manual via `UIViewRepresentable`:

```swift
public protocol Layout: Animatable {
    static var layoutProperties: LayoutProperties { get }
    typealias Cache = ...
    func makeCache(subviews: Self.Subviews) -> Self.Cache
    func updateCache(_ cache: inout Self.Cache, subviews: Self.Subviews)
    func sizeThatFits(proposal: ProposedViewSize, subviews: Self.Subviews, cache: inout Self.Cache) -> CGSize
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Self.Subviews, cache: inout Self.Cache)
}
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi custom layout engine berbasis protokol `Layout`: **EqualWidthHStack** yang memaksa semua child memiliki lebar yang identik (disesuaikan dengan child terlebar), mengabaikan batasan kompresi teks default.

```swift
import SwiftUI

// Step 1: Definisikan Layout kustom yang mengadopsi protokol Layout
public struct EqualWidthHStack: Layout {
    public var spacing: CGFloat

    public init(spacing: CGFloat = 8.0) {
        self.spacing = spacing
    }

    // Step 2: Hitung ukuran keseluruhan container (Bounding Box)
    public func sizeThatFits(
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) -> CGSize {
        guard !subviews.isEmpty else { return .zero }

        let maxChildWidth = calculateMaxChildWidth(subviews: subviews)
        let totalSpacing = spacing * CGFloat(subviews.count - 1)
        let totalWidth = (maxChildWidth * CGFloat(subviews.count)) + totalSpacing
        
        // Cari child tertinggi untuk menentukan tinggi container
        let maxHeight = subviews.reduce(CGFloat.zero) { currentMax, subview in
            let childSize = subview.sizeThatFits(ProposedViewSize(width: maxChildWidth, height: proposal.height))
            return max(currentMax, childSize.height)
        }

        return CGSize(width: totalWidth, height: maxHeight)
    }

    // Step 3: Posisikan subview di dalam ruang batas (bounds) yang diberikan parent
    public func placeSubviews(
        in bounds: CGRect,
        proposal: ProposedViewSize,
        subviews: Subviews,
        cache: inout ()
    ) {
        guard !subviews.isEmpty else { return }

        let maxChildWidth = calculateMaxChildWidth(subviews: subviews)
        var currentX = bounds.minX

        for subview in subviews {
            // Evaluasi tinggi lokal subview
            let childProposal = ProposedViewSize(width: maxChildWidth, height: bounds.height)
            let childSize = subview.sizeThatFits(childProposal)
            
            // Posisikan subview terpusat secara vertikal dalam bounds
            let yOffset = bounds.minY + (bounds.height - childSize.height) / 2.0

            subview.place(
                at: CGPoint(x: currentX, y: yOffset),
                anchor: .topLeading,
                proposal: childProposal
            )

            currentX += maxChildWidth + spacing
        }
    }

    // Helper: Hitung lebar terlebar dari seluruh child secara tidak terbatas
    private func calculateMaxChildWidth(subviews: Subviews) -> CGFloat {
        subviews.reduce(CGFloat.zero) { currentMax, subview in
            let intrinsicSize = subview.sizeThatFits(.unspecified)
            return max(currentMax, intrinsicSize.width)
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari implementasi `EqualWidthHStack`:

* **Baris 4:** `public struct EqualWidthHStack: Layout`  
  Mendeklarasikan tipe nilai yang memenuhi kontrak `Layout`. SwiftUI memperlakukan struktur ini sebagai tipe komputasi murni tanpa status referensi (*stateless*).
* **Baris 11–15:** `func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize`  
  Fungsi fase negosiasi ke-2. Parent menanyakan berapa ruang yang dibutuhkan `EqualWidthHStack` jika ditawari `proposal`. Fungsi ini **tidak boleh** memposisikan view; ia hanya melakukan proyeksi matematika murni.
* **Baris 16:** `guard !subviews.isEmpty else { return .zero }`  
  Edge-case handling. Jika container tidak memiliki subview (misal: kondisional kosong), ukuran yang diminta adalah nol instan.
* **Baris 18:** `let maxChildWidth = calculateMaxChildWidth(subviews: subviews)`  
  Melakukan probe awal dengan memanggil `subview.sizeThatFits(.unspecified)` ke setiap child. Ini mengekstrak lebar intrinsik sesungguhnya dari child tanpa kompresi paksa.
* **Baris 19–20:** `let totalWidth = (maxChildWidth * CGFloat(subviews.count)) + totalSpacing`  
  Menghitung akumulasi geometris sumbu horizontal secara deterministik.
* **Baris 32–37:** `func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ())`  
  Fase penempatan ke-3. `bounds` adalah CGRect aktual yang telah ditetapkan oleh parent, yang bisa memiliki origin non-zero ($x \neq 0, y \neq 0$).
* **Baris 48–52:** `subview.place(at: CGPoint(x: currentX, y: yOffset), anchor: .topLeading, proposal: childProposal)`  
  Instruksi placement final ke SwiftUI Render Tree. `anchor: .topLeading` memastikan perhitungan pergeseran `currentX` dimulai secara absolut dari sudut kiri atas child tersebut.
* **Baris 54:** `currentX += maxChildWidth + spacing`  
  Melakukan translasi pointer posisi horizontal untuk iterasi child berikutnya.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Responsive Adaptive Financial Analytics Feed

**Konteks Masalah:**  
Sebuah aplikasi instrumen perbankan/finansial menampilkan ringkasan portofolio.
- Pada **iPhone SE / Portrait**: Layout harus berupa list satu kolom vertikal. Nilai metrik tidak boleh terpotong (*truncated*).
- Pada **iPhone Pro Max / iPad Split View**: Jika ruang cukup, layout harus bertransisi menjadi grid multi-kolom horizontal.
- Penggunaan `GeometryReader` pada implementasi lama menyebabkan loop rendering tanpa henti (*infinite frame evaluation cycle*), konsumsi baterai berlebih, dan keterlambatan perataan (*layout hitching*) saat rotasi orientasi.

**Kebutuhan Rekayasa:**  
Membangun layout container adaptif tanpa menggunakan `GeometryReader` tunggal pun di root view, memanfaatkan `ViewThatFits` untuk fallback responsif, dan custom `AdaptiveFlowLayout` berbasis protokol `Layout` yang mendukung dynamic type.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi solusi arsitektural berskala produksi.

```swift
import SwiftUI

// MARK: - Model Domain
public struct MetricData: Identifiable, Equatable, Sendable {
    public let id: UUID = UUID()
    public let title: String
    public let value: String
    public let changePercentage: Double
    
    public init(title: String, value: String, changePercentage: Double) {
        self.title = title
        self.value = value
        self.changePercentage = changePercentage
    }
}

// MARK: - Custom Flow Layout (Wrapping dynamic grid)
public struct AdaptiveFlowLayout: Layout {
    public var spacing: CGFloat

    public init(spacing: CGFloat = 12.0) {
        self.spacing = spacing
    }

    public struct CacheData {
        var rowOffsets: [CGFloat]
        var boundsSize: CGSize
    }

    public func makeCache(subviews: Subviews) -> CacheData {
        CacheData(rowOffsets: [], boundsSize: .zero)
    }

    public func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout CacheData) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var totalHeight: CGFloat = 0
        var currentRowWidth: CGFloat = 0
        var currentRowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentRowWidth + size.width > maxWidth {
                // Pindah ke baris baru
                totalHeight += currentRowHeight + spacing
                currentRowWidth = size.width + spacing
                currentRowHeight = size.height
            } else {
                currentRowWidth += size.width + spacing
                currentRowHeight = max(currentRowHeight, size.height)
            }
        }
        totalHeight += currentRowHeight
        let calculatedSize = CGSize(width: maxWidth == .infinity ? currentRowWidth : maxWidth, height: totalHeight)
        cache.boundsSize = calculatedSize
        return calculatedSize
    }

    public func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout CacheData) {
        var currentOrigin = CGPoint(x: bounds.minX, y: bounds.minY)
        var currentRowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentOrigin.x + size.width > bounds.maxX {
                // Bungkus baris ke awal baris baru
                currentOrigin.x = bounds.minX
                currentOrigin.y += currentRowHeight + spacing
                currentRowHeight = 0
            }

            subview.place(
                at: currentOrigin,
                anchor: .topLeading,
                proposal: ProposedViewSize(size)
            )

            currentRowHeight = max(currentRowHeight, size.height)
            currentOrigin.x += size.width + spacing
        }
    }
}

// MARK: - Atomic Card Component
public struct MetricCardView: View {
    public let metric: MetricData

    public var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(metric.title)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            
            Text(metric.value)
                .font(.headline.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)

            HStack(spacing: 2) {
                Image(systemName: metric.changePercentage >= 0 ? "arrow.up.right" : "arrow.down.right")
                Text(String(format: "%.2f%%", abs(metric.changePercentage)))
            }
            .font(.caption2.bold())
            .foregroundStyle(metric.changePercentage >= 0 ? .green : .red)
        }
        .padding(12)
        .frame(minWidth: 140)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(uiColor: .secondarySystemBackground))
        )
    }
}

// MARK: - Production Adaptive Container
public struct PortfolioDashboardView: View {
    public let metrics: [MetricData]
    
    public init(metrics: [MetricData]) {
        self.metrics = metrics
    }

    public var body: some View {
        ScrollView(.vertical, showsIndicators: true) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Executive Financial Overview")
                    .font(.title2.bold())
                    .padding(.horizontal)

                // Layout Orchestration via ViewThatFits:
                // Engine mengevaluasi struktur visual terbaik dari urutan teratas ke bawah
                ViewThatFits(in: .horizontal) {
                    // Opsi 1: Multi-column horizontal row jika ruang melimpah (iPad / Landscape)
                    HStack(spacing: 12) {
                        ForEach(metrics) { metric in
                            MetricCardView(metric: metric)
                        }
                    }
                    .padding(.horizontal)

                    // Opsi 2: Dynamic Wrapping Layout jika opsi 1 overflow
                    AdaptiveFlowLayout(spacing: 12) {
                        ForEach(metrics) { metric in
                            MetricCardView(metric: metric)
                        }
                    }
                    .padding(.horizontal)

                    // Opsi 3: Vertical fallback stack jika layar terlampau sempit (iPhone SE)
                    VStack(spacing: 8) {
                        ForEach(metrics) { metric in
                            MetricCardView(metric: metric)
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .padding(.vertical)
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter / Pendekatan | `GeometryReader` | `ViewThatFits` | Protokol `Layout` (iOS 16+) |
| :--- | :--- | :--- | :--- |
| **Sifat Alokasi Ukuran** | Agresif (*Greedy* / Memenuhi semua ruang) | Pasif (Mengikuti ukuran child pertama yang cocok) | Netral / Terhitung secara presisi |
| **Kompleksitas Komputasi** | $O(1)$ deklarasi, tetapi berpotensi $O(N)$ re-render cascade | $O(K \times M)$ ($K$ representasi layout, $M$ subviews) | $O(M)$ eksekusi kalkulasi linier |
| **Siklus Lifecycle** | Memicu relayout setiap kali parent frame bergeser 1px | Dihitung statis selama ukuran parent muat | Layout terisolasi di engine, zero view recreation |
| **Layout Thrashing Risk**| **Tinggi** (Berbahaya jika di dalam `ScrollView` / `List`) | **Rendah** | **Sangat Rendah** (Ter-cache secara native) |
| **Fleksibilitas Desain** | Arbitrer / Perhitungan manual berbasis CGPoint | Terbatas pada memilih varian view hierarki | Tanpa batas / Bebas menyusun algoritma 2D |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Greedy Layout Collapse pada `GeometryReader` di dalam `ScrollView`:**  
   `GeometryReader` membutuhkan ukuran eksplisit dari parent. Namun, `ScrollView` pada sumbu scroll-nya memberikan proposal ukuran `ProposedViewSize(width: x, height: nil)`. Akibatnya, `GeometryReader` akan kolaps ke tinggi `0` atau mengambil nilai acak, memicu bug antarmuka kosong.
2. **Text Truncation Trap pada Dynamic Type:**  
   Menyetel `.frame(height: 44)` pada sebuah row yang berisi `Text` melanggar kedaulatan ukuran child saat Dynamic Type diatur ke Accessibility Sizes (`AX3`). Child meminta tinggi 80pt, tetapi parent memotongnya pada 44pt, menyebabkan teks terpotong sebagian.
3. **Infinite Render Loops (Cycle Thrashing):**  
   Menulis nilai dari `GeometryReader` langsung ke `@State` lokal di dalam blok rendering `body`:
   ```swift
   .background(GeometryReader { geo in
       Color.clear.onAppear { self.width = geo.size.width } // PERINGATAN: Mematikan pipeline perenderan!
   })
   ```
   Ini memicu siklus: *Render -> Mutasi State -> Invalidation -> Render Baru -> Mutasi State*. Gunakan `PreferenceData` atau murni protokol `Layout`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Menggunakan `GeometryReader` hanya untuk pembagian lebar 50-50

```swift
// BURUK: Mengakibatkan ekspansi agresif yang tidak diinginkan
HStack {
    GeometryReader { proxy in
        HStack {
            LeftView().frame(width: proxy.size.width * 0.5)
            RightView().frame(width: proxy.size.width * 0.5)
        }
    }
}
```

```swift
// BENAR: Menggunakan container frame fleksibel bawaan SwiftUI
HStack(spacing: 0) {
    LeftView()
        .frame(maxWidth: .infinity)
    RightView()
        .frame(maxWidth: .infinity)
}
```

### Anti-Pattern 2: Memaksa Alignment Menggunakan Hardcoded `Spacer` Offset

```swift
// BURUK: Patah saat ukuran font membesar atau device berbeda
HStack {
    Text("Title")
    Spacer().frame(width: 47)
    Text("Value")
}
```

```swift
// BENAR: Menggunakan Custom Alignment Guide
extension HorizontalAlignment {
    private enum MetricAlign: AlignmentID {
        static func defaultValue(in context: ViewDimensions) -> CGFloat {
            context[.leading]
        }
    }
    static let metricAlign = HorizontalAlignment(MetricAlign.self)
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Definisikan Layout Priority Secara Deklaratif:** Berikan `layoutPriority(1)` pada label teks esensial (seperti saldo mata uang) dan `layoutPriority(0)` pada label sekunder untuk memastikan degradasi tampilan berlangsung anggun saat terjadi kompresi ruang.
2. **Pisahkan Geometri dari Logika Domain:** Jangan biarkan view membaca geometri layar (`UIScreen.main.bounds`). Layar dapat berubah sewaktu-waktu (iPad Stage Manager, Mac resize). Gunakan dimensi kontainer proksimal.
3. **Terapkan `Layout.Cache` untuk Komputasi Rumit:** Ketika mengimplementasikan custom `Layout`, simpan kalkulasi kompleks (seperti text size measurement) di memori cache yang disediakan via `makeCache(subviews:)` guna menghindari eksekusi ulang algoritma pada frame rate 120Hz (ProMotion).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Pemanfaatan Layout Caching Internal

Saat menggunakan protokol `Layout`, method `sizeThatFits` dan `placeSubviews` dapat dipanggil belasan kali dalam satu siklus gestur interaktif. Buat representasi cache:

```swift
public struct OptimizedStackLayout: Layout {
    public struct Cache {
        var frames: [CGRect] = []
        var totalSize: CGSize = .zero
    }

    public func makeCache(subviews: Subviews) -> Cache {
        return Cache()
    }

    public func updateCache(_ cache: inout Cache, subviews: Subviews) {
        // Bersihkan atau re-alokasi buffer hanya jika subview berubah
        cache.frames.removeAll(keepingCapacity: true)
    }

    public func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) -> CGSize {
        // Kalkulasikan layout sekali, rekam ke dalam Cache
        let computed = calculateGeometry(for: subviews, proposal: proposal)
        cache.frames = computed.frames
        cache.totalSize = computed.size
        return computed.size
    }

    public func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout Cache) {
        // O(1) Access time, zero computation overhead saat rendering placement!
        for index in subviews.indices {
            let frame = cache.frames[index]
            subviews[index].place(
                at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY),
                proposal: ProposedViewSize(frame.size)
            )
        }
    }
    
    private func calculateGeometry(for subviews: Subviews, proposal: ProposedViewSize) -> (frames: [CGRect], size: CGSize) {
        // Logika layout deterministik
        return ([], .zero)
    }
}
```

---

## SEKSI 16 — KEAMANAN & HARDENING

Pada level rendering dan sistem antarmuka:
1. **Denial of Service (UI Freeze) via Layout Recursion:**  
   Hindari perhitungan layout berbasis floating point tak terhingga (`CGFloat.infinity`). Mengirimkan `ProposedViewSize.infinity` ke custom layout yang mengiterasi ruang berbasis sub-pixel division akan memicu infinite loop CPU dan membekukan thread utama (UI Hang Watchdog terminate `0x8badf00d`).
2. **Defensive Layout Bounds Sanity:**  
   Pastikan nilai masukan bounding box selalu divalidasi terhadap `isNaN` dan `isInfinite`:
   ```swift
   guard !bounds.width.isNaN && !bounds.height.isNaN else { return }
   let safeWidth = bounds.width.clamped(to: 0...10_000)
   ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

SwiftUI menyediakan instrumen tersembunyi yang sangat kuat untuk memvisualisasikan layout negotiation:

### 1. Visual Layout Feedback via Runtime Modifiers
```swift
extension View {
    public func debugLayoutBoundary(_ color: Color = .red) -> some View {
        self.border(color, width: 1)
            .background(
                GeometryReader { proxy in
                    Color.clear.overlay(
                        Text("\(Int(proxy.size.width))x\(Int(proxy.size.height))")
                            .font(.system(size: 8, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                            .background(Color.black.opacity(0.7))
                            .position(x: proxy.size.width / 2, y: proxy.size.height / 2)
                    )
                }
            )
    }
}
```

### 2. LLDB & Layout Negotiation Trace
Tambahkan argumen runtime di Xcode Scheme Settings (*Arguments Passed On Launch*):
`-NSDoubleLocalizedStrings YES` untuk mengecek layout stress pada Dynamic Translation.

Gunakan LLDB untuk memeriksa view hierarchy:
```lldb
(lldb) po [[UIWindow keyWindow] _autolayoutTrace] // UIKit debugging
(lldb) expr -l swift -- import SwiftUI
(lldb) po Context._printHierarchy() // Menampilkan hierarki deklaratif SwiftUI
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    SWIFTUI LAYOUT ENGINE CHEAT SHEET                       │
├────────────────────────────────┬───────────────────────────────────────────┤
│ Perilaku Ukuran View           │ Modifiers / Views Terkait                 │
├────────────────────────────────┼───────────────────────────────────────────┤
│ Menghormati Ukuran Child       │ Group, ZStack, Unspecified Frames         │
│ Menghabiskan Ruang (Greedy)   │ Spacer, Color, Rectangle, maxWidth: .inf  │
│ Kaku / Tidak Mengembang        │ Image, Text (tanpa scale modifier)        │
├────────────────────────────────┼───────────────────────────────────────────┤
│ Negosiasi Layout (Tiga Fase)   │ 1. Proposal -> 2. Resolution -> 3. Place  │
├────────────────────────────────┼───────────────────────────────────────────┤
│ Protokol Layout (iOS 16+)      │ sizeThatFits(...) -> Menghitung Bounding  │
│                                │ placeSubviews(...) -> Koordinat Penempatan│
│                                │ makeCache(...) -> Performa Tinggi ProMotion│
├────────────────────────────────┼───────────────────────────────────────────┤
│ Pengganti GeometryReader       │ ViewThatFits (Alternatif deklaratif)      │
│                                │ .layoutPriority(Double) (Distribusi beban)│
│                                │ Custom AlignmentGuide (Offset alignment)  │
└────────────────────────────────┴───────────────────────────────────────────┘
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Jelaskan apa yang terjadi jika sebuah view menerima proposal `ProposedViewSize.unspecified` dari parent-nya!**  
   *Jawaban Teknis:* View akan mengevaluasi dan mengembalikan ukuran intrinsik alaminya (*natural unconstrained size*). Misalnya, `Text` akan mengembalikan dimensi bounding box satu baris penuh tanpa wrapping, dan `Image` akan mengembalikan resolusi piksel aslinya.

2. **Kapan Anda sebaiknya menggunakan `layoutPriority(_:)`?**  
   *Jawaban Teknis:* Ketika berada di dalam stack fleksibel (`HStack`/`VStack`) di mana ruang terbatas, dan Anda ingin memprioritaskan view tertentu agar tidak mengalami kompresi/truncation sebelum view berprioritas rendah dikorbankan.

3. **Benar atau Salah: Parent di SwiftUI dapat memaksa Child untuk memiliki ukuran tertentu di luar kehendak Child tersebut.**  
   *Jawaban Teknis:* Salah. Child memiliki kedaulatan ukuran (*layout sovereignty*). Parent hanya dapat menyarankan ukuran atau memotong visual renderingnya (`clipped()`), tetapi child tetap melapor dan menempati frame pilihannya sendiri.

4. **Apa nilai default dari `layoutPriority` sebuah view?**  
   *Jawaban Teknis:* `0.0` (tipe `Double`).

5. **Apa fungsi dari modifier `.alignmentGuide`?**  
   *Jawaban Teknis:* Menimpa (*override*) perhitungan komputasi offset skalar eksplisit pada garis penyejajaran tertentu (seperti `.leading`, `.top`) pada sistem koordinat lokal view tersebut.

---

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa menempatkan `GeometryReader` langsung di dalam `ScrollView` dapat merusak rendering layout?**  
   *Jawaban Teknis:* `ScrollView` mengusulkan ukuran vertikal tak terhingga (`nil` height) pada konten di dalamnya. `GeometryReader` adalah view yang rakus (*greedy*) yang membutuhkan proposal pasti untuk menentukan ukurannya sendiri. Hal ini memicu ambiguitas dimensi, sering kali menghasilkan tinggi `0` atau perilaku melompat (*glitching*).

7. **Bagaimana algoritma `ViewThatFits` mengevaluasi varian anak-anaknya?**  
   *Jawaban Teknis:* Secara sekuensial (top-to-bottom). Ia mengajukan penawaran ruang saat ini kepada child pertama. Jika child pertama dapat merender dirinya di dalam batasan tersebut tanpa mengalami clipping/overflow pada sumbu yang dievaluasi, ia akan dipilih. Jika tidak, ia mencoba child kedua, dan seterusnya.

8. **Apa peran argumen `cache` pada implementasi protokol `Layout`?**  
   *Jawaban Teknis:* Menyediakan penyimpanan data persisten antar pemanggilan `sizeThatFits` dan `placeSubviews` selama satu siklus rendering, mencegah kalkulasi geometri yang redundan dan meminimalkan beban CPU pada display refresh rate 120Hz.

9. **Apa perbedaan antara `frame(minWidth:maxWidth:)` dengan memanggil `frame(width:)` langsung?**  
   *Jawaban Teknis:* `frame(width:)` memaksa proposal fixed size ke subview dan mengembalikan ukuran fixed ke parent. `minWidth:maxWidth:` mendefinisikan fleksibilitas jangkauan; subview bebas memilih ukuran apa pun selama masih dalam batas-batas tersebut.

10. **Bagaimana cara mencegah custom layout protokol melakukan kalkulasi ulang yang memicu memory leak atau hanging?**  
    *Jawaban Teknis:* Menghindari alokasi state baru secara imperatif di dalam method layout, memastikan closure layout bersifat murni (*side-effect free*), dan menjaga cache internal terikat secara deterministik terhadap array `subviews`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Circular Radial Dashboard Menu Layout

Bangun custom layout container bernama `RadialLayout` menggunakan protokol modern `Layout`.

**Kriteria Penerimaan Arsitektural:**
1. Mengadopsi protokol `Layout` secara penuh (iOS 16+).
2. Menempatkan seluruh elemen child dalam formasi lingkaran simetris 360 derajat. Jarak radius ($R$) harus dihitung secara otomatis berdasarkan ukuran terkecil antara lebar atau tinggi bounding box parent:
   $$R = \frac{\min(\text{width}, \text{height}) - \text{maxChildDimension}}{2}$$
3. Posisi setiap child ke-$i$ dihitung menggunakan trigonometri dasar:
   $$\theta_i = \left(\frac{2\pi}{N}\right) \times i - \frac{\pi}{2}$$
   $$X_i = \text{Center}_X + R \cdot \cos(\theta_i)$$
   $$Y_i = \text{Center}_Y + R \cdot \sin(\theta_i)$$
4. Mendukung animasi rotasi transisi halus saat item ditambahkan atau dihapus (`Animatable`).
5. **Anti-Crash:** Jika subview berjumlah 0 atau 1, layout harus menangani edge case tersebut secara elegan tanpa error pembagian dengan nol (*division by zero*).

---

### Solusi Referensi Praktikum

```swift
import SwiftUI

public struct RadialLayout: Layout {
    public var angleOffset: Angle

    public init(angleOffset: Angle = .zero) {
        self.angleOffset = angleOffset
    }

    public func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        // Menerima tawaran ukuran parent, atau fallback ke 300x300 jika unspecified
        let width = proposal.width ?? 300
        let height = proposal.height ?? 300
        let dimension = min(width, height)
        return CGSize(width: dimension, height: dimension)
    }

    public func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        guard !subviews.isEmpty else { return }

        // Tangani kasus tunggal: tempatkan di tengah absolut
        if subviews.count == 1 {
            subviews[0].place(
                at: CGPoint(x: bounds.midX, y: bounds.midY),
                anchor: .center,
                proposal: .unspecified
            )
            return
        }

        // Tentukan dimensi child terbesar untuk proteksi clipping radius
        let maxChildSize = subviews.reduce(CGFloat.zero) { currentMax, subview in
            let size = subview.sizeThatFits(.unspecified)
            return max(currentMax, max(size.width, size.height))
        }

        let radius = (min(bounds.width, bounds.height) - maxChildSize) / 2.0
        let angleStep = (2.0 * .pi) / Double(subviews.count)

        for (index, subview) in subviews.enumerated() {
            let angle = (angleStep * Double(index)) + angleOffset.radians - (.pi / 2.0)
            let xPosition = bounds.midX + (radius * CGFloat(cos(angle)))
            let yPosition = bounds.midY + (radius * CGFloat(sin(angle)))

            subview.place(
                at: CGPoint(x: xPosition, y: yPosition),
                anchor: .center,
                proposal: .unspecified
            )
        }
    }
}

// MARK: - Testing Canvas
struct RadialLayout_Previews: PreviewProvider {
    struct TestContainer: View {
        @State private var count = 6
        @State private var rotation: Double = 0

        var body: some View {
            VStack {
                RadialLayout(angleOffset: .degrees(rotation)) {
                    ForEach(0..<count, id: \.self) { index in
                        Circle()
                            .fill(Color.blue.gradient)
                            .frame(width: 44, height: 44)
                            .overlay(Text("\(index + 1)").bold().foregroundColor(.white))
                    }
                }
                .frame(width: 320, height: 320)
                .background(Circle().stroke(Color.gray.opacity(0.3), lineWidth: 1))
                .animation(.spring(response: 0.6, dampingFraction: 0.7), value: rotation)
                .animation(.default, value: count)

                HStack(spacing: 20) {
                    Button("Rotate") { rotation += 45 }
                    Button("Add") { if count < 12 { count += 1 } }
                    Button("Remove") { if count > 1 { count -= 1 } }
                }
                .buttonStyle(.borderedProminent)
                .padding(.top, 40)
            }
        }
    }

    static var previews: some View {
        TestContainer()
    }
}
```