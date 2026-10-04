# Kurikulum Rekayasa Perangkat Lunak Enterprise: iOS Engineering
## Kategori: 03-Frontend-and-Mobile
### BAB-02: Desain Antarmuka Deklaratif dengan SwiftUI Tingkat Lanjut
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Principal/Senior iOS Engineer diharapkan mampu:
*   Menganalisis dan membedah siklus hidup *runtime* SwiftUI (*AttributeGraph*, identitas struktural vs eksplisit, dan rekonsiliasi graf dependensi).
*   Menguasai integrasi framework modern *Observation* (`@Observable`) serta memahami perbedaan alokasi memori dibanding protokol warisan `ObservableObject`.
*   Mengimplementasikan custom layout engine performa tinggi menggunakan protokol `Layout` untuk kalkulasi tata letak non-linier deterministik tanpa dependensi UIKit.
*   Mengembangkan arsitektur State-Driven berskala enterprise (Unidirectional Data Flow / The Composable Architecture / Clean Architecture) dengan isolasi modul dan pengujian deterministik.
*   Mengidentifikasi, mengukur, dan mengeliminasi *render invalidation cascade*, retensi siklus memori, serta *frame drop* (Hitch Rate) pada ProMotion Display (120Hz) menggunakan Xcode Instruments (SwiftUI View Body, Time Profiler, dan Allocations).

---

### 2. Prerequisite
*   Pemahaman mendalam tentang **Swift 5.9+ / Swift 6** (Generics tingkat lanjut, Opaque & Existential Types, Result Builders, Macro System, dan Swift Concurrency: `Sendable`, `@MainActor`, `AsyncSequence`).
*   Pengalaman arsitektural UIKit (Siklus hidup `UIViewController`, mekanisme *AutoLayout layout engine* Cassowary, `CALayer` rendering pipeline).
*   Pemahaman dasar SwiftUI (Penggunaan deklaratif: `VStack`, `HStack`, `@State`, `@Binding`).
*   Pengalaman menggunakan Instruments (Core Animation, Time Profiler, Leaks).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 AttributeGraph & Render Loop Internals
SwiftUI bukanlah sekadar *wrapper* tipis di atas UIKit/AppKit, melainkan sistem rendering independen berbasis grafik evaluasi dependensi (*Directed Acyclic Graph* atau DAG) yang dikelola oleh mesin privat bernama **AttributeGraph** (ditulis dalam C++).

```
[State Mutation (@State / @Observable)] 
                 │
                 ▼
    [AttributeGraph Mark Dirty] 
                 │
                 ▼
    [View Identity Verification] (Structural vs Explicit)
                 │
                 ▼
         [Re-evaluation Pass] ──(Skip if Body is Pure & Inputs Equal)
                 │
                 ▼
       [Layout Engine Phase] ──(ProposedSize -> Measure -> Place)
                 │
                 ▼
      [Display List Creation]
                 │
                 ▼
   [Render Server Commit (CA / Metal)]
```

1.  **State Mutation**: Mutasi nilai pada properti yang dipantau menandai simpul (*node*) terkait pada *AttributeGraph* sebagai *dirty*.
2.  **Graph Reconciliation**: Runtime menelusuri sub-grafik dependensi untuk menemukan simpul mana saja yang terpengaruh langsung. Runtime tidak mengevaluasi seluruh pohon tampilan, melainkan hanya sub-pohon terkecil yang validitas datanya telah kedaluwarsa.
3.  **View Evaluation**: Fungsi `body` dari tipe `View` yang terdampak dieksekusi. Karena `View` adalah nilai (*struct* murni yang dialokasikan di stack), pembuatan instansiasi ini sangat murah secara komputasi.
4.  **Display List Generation**: Hasil primitif representasi grafis dikonversi menjadi *Display List*, serialisasi operasi rendering yang dikirimkan melalui IPC (*Inter-Process Communication*) ke *Render Server* iOS (`backboardd` / `QuartzCore`).
5.  **Render Server Draw**: *Render Server* menggunakan Metal untuk menggambar geometri aktual langsung ke *Frame Buffer* GPU.

#### 3.2 View Identity: Structural Identity vs Explicit Identity
Identitas adalah mekanisme fundamental yang digunakan SwiftUI untuk mengasosiasikan elemen antarmuka antar siklus render. Kegagalan memahami identitas mengakibatkan destruksi status transien (*transient state*), animasi putus, dan degradasi performa render.

*   **Explicit Identity**: Identitas yang diberikan secara terprogram melalui `.id(...)` atau properti `Identifiable.id`. Ketika ID eksplisit berubah, SwiftUI menghancurkan instansiasi tampilan lama beserta seluruh status internalnya, lalu membuat instansiasi baru secara *in-place*.
*   **Structural Identity**: Identitas implisit yang diperoleh dari lokasi struktural sebuah tampilan di dalam hirarki kode result builder. Logika percabangan (`if-else`, `switch`) menciptakan *dua identitas struktural yang berbeda* di dalam grafik:
    ```swift
    // WARNING: Menghasilkan 2 Identitas Struktural Berbeda
    if isExpanded {
        DetailCardView(data: data) // Type: _ConditionalContent<DetailCardView, EmptyView>
    } else {
        EmptyView()
    }
    ```
    Penggunaan percabangan di atas menyebabkan penghancuran dan pembuatan ulang `DetailCardView` setiap kali kondisi boolean berubah. Pendekatan deklaratif yang optimal mempertahankan identitas tampilan dengan mengabstraksi properti dinamis:
    ```swift
    // PERFORMA TINGGI: Identitas Struktural Stabil
    DetailCardView(data: data)
        .opacity(isExpanded ? 1.0 : 0.0)
        .frame(height: isExpanded ? nil : 0)
    ```

#### 3.3 The Layout Protocol: Tiga Fase Negosiasi Ukuran
Sistem tata letak SwiftUI bersifat murni deterministik melalui tiga fase:
1.  **Parent Proposes Size**: Komponen induk menawarkan ukuran tertentu (*ProposedViewSize*) ke komponen anak. Pilihan proposal bisa berupa: nilai pasti, `.unspecified`, `.zero`, atau `.infinity`.
2.  **Child Chooses Size**: Komponen anak menghitung dan mengembalikan ukuran konkret (`CGSize`) yang benar-benar diinginkannya berdasarkan proposal tersebut. Komponen induk **harus menghormati** ukuran yang dikembalikan anak.
3.  **Parent Places Child**: Komponen induk menentukan koordinat geometris relatif anak dalam sistem koordinat lokalnya.

#### 3.4 Modern Observation Framework vs. Combine (ObservableObject)
Swift 5.9 memperkenalkan framework `Observation` yang menggantikan protokol `ObservableObject`.

| Karakteristik | `ObservableObject` (Combine) | `@Observable` Macro (Swift 5.9+) |
| :--- | :--- | :--- |
| **Mekanisme Notifikasi** | Mengirim sinyal melalui publisher `objectWillChange` sebelum mutasi. | Menggunakan *ObservationRegistrar* untuk pelacakan akses properti granular. |
| **Granularitas Evaluasi** | Berbasis **Instance**. Jika *satu* properti berubah, seluruh View yang mengamati objek di-render ulang. | Berbasis **Property**. View hanya di-render ulang jika properti *spesifik* yang dibaca pada `body` berubah. |
| **Alokasi Memori** | Membutuhkan alokasi *Combine pipeline* internal, *Cancellable tokens*, dan heap management ekstra. | Kompilasi berbasis Macro, zero Combine overhead, metadata langsung terintegrasi pada runtime Swift. |
| **Thread Affinity** | Memerlukan eksplisit `@Published` dan *pipeline scheduling* (`receive(on:)`). | Akses dan mutasi dilacak secara otomatis; tunduk pada model konkurensi Swift Actor (`@MainActor`). |

---

### 4. Why & What
*   **Mengapa UIKit imperative rendering tidak lagi memadai untuk arsitektur enterprise skala besar?**
    UIKit mengandalkan mutasi status secara langsung (*mutable state mutation*) yang rentan terhadap inkonsistensi (*state synchronization drift*). Pada aplikasi berskala ratusan modul dengan sinkronisasi multi-thread, kompleksitas *two-way binding* dan manipulasi hierarki tampilan manual sering memicu *race conditions*, memory leak pada *closures delegate*, dan bug transisi visual.
*   **Apa peran SwiftUI tingkat lanjut dalam ekosistem enterprise?**
    SwiftUI menyediakan jaminan deterministik: **UI adalah fungsi murni dari State** (`UI = f(State)`). Dengan memanfaatkan runtime berbasis *AttributeGraph* dan framework *Observation*, enterprise dapat membangun sistem modular berkecepatan tinggi, memutus dependensi ketat antar-tim, dan menurunkan biaya pemeliharaan kode secara radikal melalui isolasi status (*state containment*).

---

### 5. How (Workflow Detail)

Alur perancangan dan implementasi fitur SwiftUI kelas enterprise mencakup:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Enterprise SwiftUI Cycle                        │
└────────────────────────────────────────────────────────────────────────┘
  1. STATE MODELING
     └─ Definisikan Immutable State & Mutasi Terisolasi via @Observable & Actor
  2. COMPONENT DECOMPOSITION
     └─ Pisahkan View ke Unit Struktural Terkecil (Pemisahan Granular)
  3. LAYOUT SPECIFICATION
     └─ Evaluasi Kebutuhan Layout Engine (Standard vs Custom Layout Protocol)
  4. BRIDGING & INTEROP
     └─ Tentukan Batasan dengan UIKit via UIViewRepresentable (jika perlu)
  5. PROFILING & REGRESSION TEST
     └─ Verifikasi Body Re-evaluasi via _printChanges() & Instruments Profile
```

1.  **State Modeling**: Modelkan status aplikasi dalam bentuk pohon status deterministik. Hindari representasi status yang berlebihan (*redundant state*). Gunakan *derived state* (computed properties) yang dilacak langsung oleh *Observation engine*.
2.  **View Splitting untuk Isolasi Invalidation**: Pecah tampilan besar menjadi struktur-struktur kecil independen. Setiap kali sub-pohon dievaluasi, SwiftUI dapat mengabaikan (*skip*) evaluasi sub-pohon paralel yang dependensi datanya tidak berubah.
3.  **Layout Specialization**: Jika hirarki antarmuka memerlukan dynamic alignment kompleks (misal: staggered grid, circular dials, waterfall layout), gunakan protokol `Layout` daripada menyusun kombinasi nested `HStack`/`VStack` yang memperdalam hierarki grafik tampilan (*AttributeGraph depth*).
4.  **Audit Memory & Body Execution**: Jalankan instrumen `SwiftUI View Body` untuk memastikan *Hitch Time ratio* berada di bawah target SLA Apple (< 5 ms per frame transition).

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi AttributeGraph vs Git Tree
Bayangkan hierarki tampilan SwiftUI seperti repositori Git:
*   Struktur *View Struct* adalah **Commit Tree**.
*   *State* adalah **Data File** dalam pohon tersebut.
*   Ketika terjadi mutasi, runtime tidak membuat repositori baru, melainkan melakukan kalkulasi **`git diff`** tingkat tinggi.
*   Hanya simpul direktori/berkas yang memiliki hash berbeda yang akan di-checkout dan dikirim ke GPU (*working directory*).

#### 6.2 Diagram Interaksi Komponen Runtime

```
 [ External Event (WebSocket / Network / User Tap) ]
                         │
                         ▼
        ┌──────────────────────────────────┐
        │  AppStateDomain (@MainActor)     │
        │  @Observable class MarketEngine  │
        │  - bidPrice: Double              │
        │  - askPrice: Double              │
        └─────────────────┬────────────────┘
                          │ (Tracks Property Read Dependency)
                          ▼
        ┌──────────────────────────────────┐
        │       SwiftUI AttributeGraph     │
        │                                  │
        │   ┌──────────────────────────┐   │
        │   │ Node: MarketView (Root)  │   │
        │   └─────────────┬────────────┘   │
        │                 │                │
        │       ┌─────────┴─────────┐      │
        │       ▼                   ▼      │
        │ ┌───────────┐       ┌──────────┐ │
        │ │BidView    │       │AskView   │ │
        │ │(Subscribes│       │(Static / │ │
        │ │ bidPrice) │       │Unchanged)│ │
        │ └─────┬─────┘       └────┬─────┘ │
        └───────┼──────────────────┼───────┘
                │ (Dirty)          │ (Bypassed)
                ▼                  ▼
        ┌──────────────┐     ┌───────────┐
        │ Evaluated    │     │  SKIPPED  │
        │ Re-rendered  │     └───────────┘
        └───────┬──────┘
                ▼
        [ Display List Update ] ──> [ GPU Render Server ]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Implementasi Custom Layout Engine
Berikut adalah implementasi non-linier custom layout menggunakan protokol `Layout` untuk menyusun item secara horizontal dengan batas pembungkusan baris (*Flow Layout / Tag Cloud*).

```swift
import SwiftUI

public struct FlowLayout: Layout {
    public var spacing: CGFloat

    public init(spacing: CGFloat = 8) {
        self.spacing = spacing
    }

    public func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let containerWidth = proposal.replacingUnspecifiedDimensions().width
        var totalHeight: CGFloat = 0
        var currentLineWidth: CGFloat = 0
        var currentLineHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentLineWidth + size.width > containerWidth {
                totalHeight += currentLineHeight + spacing
                currentLineWidth = size.width + spacing
                currentLineHeight = size.height
            } else {
                currentLineWidth += size.width + spacing
                currentLineHeight = max(currentLineHeight, size.height)
            }
        }
        totalHeight += currentLineHeight
        return CGSize(width: containerWidth, height: totalHeight)
    }

    public func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var currentX = bounds.minX
        var currentY = bounds.minY
        var currentLineHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > bounds.maxX {
                currentX = bounds.minX
                currentY += currentLineHeight + spacing
                currentLineHeight = size.height
            } else {
                currentLineHeight = max(currentLineHeight, size.height)
            }
            
            subview.place(at: CGPoint(x: currentX, y: currentY), proposal: ProposedViewSize(size))
            currentX += size.width + spacing
        }
    }
}
```

#### 7.2 Practical Example: High-Throughput Financial Order Book
Arsitektur produksi: Tampilan buku pesanan (*Order Book*) real-time berkecepatan tinggi yang memisahkan update frekuensi tinggi dari *re-rendering tree* menggunakan `@Observable` dan bridging UIKit performa tinggi.

```swift
import SwiftUI
import Observation

// MARK: - Core Domain Models
public struct OrderBookLevel: Identifiable, Equatable, Sendable {
    public let id: Double // Price acts as identity
    public let price: Double
    public let quantity: Double
    public let orderCount: Int
}

// MARK: - Observable State (Granular Tracking)
@Observable
@MainActor
public final class OrderBookViewModel {
    public private(set) var bids: [OrderBookLevel] = []
    public private(set) var asks: [OrderBookLevel] = []
    public private(set) var spread: Double = 0.0
    
    public init() {}
    
    public func updateSnapshot(bids: [OrderBookLevel], asks: [OrderBookLevel]) {
        self.bids = bids
        self.asks = asks
        if let bestBid = bids.first?.price, let bestAsk = asks.first?.price {
            self.spread = bestAsk - bestBid
        }
    }
}

// MARK: - Root Container View
public struct OrderBookContainerView: View {
    @State private var viewModel = OrderBookViewModel()

    public init() {}

    public var body: some View {
        VStack(spacing: 0) {
            HeaderMetricView(viewModel: viewModel)
            HStack(alignment: .top, spacing: 1) {
                // Bid Side (Sub-tree terisolasi)
                OrderBookListView(levels: viewModel.bids, side: .bid)
                // Ask Side (Sub-tree terisolasi)
                OrderBookListView(levels: viewModel.asks, side: .ask)
            }
            .background(Color(uiColor: .systemGroupedBackground))
        }
    }
}

// MARK: - Isolated Header Metric Subview
private struct HeaderMetricView: View {
    // Hanya membaca `spread`. Perubahan pada quantity bids/asks TIDAK merender ulang view ini.
    var viewModel: OrderBookViewModel

    var body: some View {
        HStack {
            Text("SPREAD")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
            Text(viewModel.spread, format: .number.precision(.fractionLength(2)))
                .font(.headline)
                .monospacedDigit()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }
}

// MARK: - Order Book Table
private struct OrderBookListView: View {
    let levels: [OrderBookLevel]
    let side: Side
    
    enum Side {
        case bid, ask
        var tint: Color { self == .bid ? .green : .red }
    }

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            LazyVStack(spacing: 1) {
                ForEach(levels) { level in
                    OrderBookRowView(level: level, tintColor: side.tint)
                }
            }
        }
    }
}

// MARK: - Leaf View dengan Equatable Optimasi
private struct OrderBookRowView: View, Equatable {
    let level: OrderBookLevel
    let tintColor: Color

    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.level == rhs.level && lhs.tintColor == rhs.tintColor
    }

    var body: some View {
        HStack {
            Text(level.price, format: .number.precision(.fractionLength(2)))
                .font(.caption)
                .monospacedDigit()
                .foregroundStyle(tintColor)
            Spacer()
            Text(level.quantity, format: .number.precision(.fractionLength(4)))
                .font(.caption)
                .monospacedDigit()
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(Color(uiColor: .secondarySystemBackground))
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Masalah
Sebuah platform Super-App FinTech meluncurkan modul **Live Equity & Crypto Terminal**. Modul menerima streaming pembaruan harga via WebSocket sebanyak 30 hingga 60 mutasi per detik. 

**Simtom di Lapangan**:
*   Aplikasi mengalami *frame-drop* masif (Frame rate jatuh dari 120 FPS ke 18-24 FPS) pada perangkat iPhone 14/15 Pro.
*   *Thermal Throttling* terjadi setelah 3 menit penggunaan, berujung pada konsumsi baterai ekstrem.
*   Xcode Memory Gauge menunjukkan lonjakan alokasi memori sementara (*churn*) sebesar ~180MB/detik.

#### Analisis Akar Masalah (Root-Cause Deep Dive)
Menggunakan **Instruments (SwiftUI View Body & Time Profiler)**, ditemukan tiga arsitektural flaw:
1.  **Penggunaan `ObservableObject` Tunggal (God Object)**: Seluruh status terminal (grafik, order book, riwayat transaksi, ticker bar, data profil pengguna) digabungkan dalam satu kelas `TerminalViewModel: ObservableObject`. Setiap kali WebSocket memperbarui satu ticker, publisher `objectWillChange.send()` terpanggil, memaksa seluruh root hirarki dan 40+ subviews mengeksekusi properti `body`.
2.  **Structural Identity Throttling**: Tampilan grafik menggunakan percabangan eksplisit `if viewModel.selectedInterval == .intraday { ... } else { ... }`, memusnahkan Metal rendering context internal secara terus-menerus.
3.  **Tipe Penampung `AnyView`**: Komponen modular diekspor menggunakan *type-erased wrappers* (`AnyView(CustomModule())`). Hal ini melucuti kemampuan kompiler untuk mengoptimalkan hierarki visual statis dan memaksa alokasi *heap* dinamis untuk setiap iterasi render.

#### Solusi Arsitektur
1.  **Migrasi ke Modern Observation Engine**: Mengonversi `TerminalViewModel` ke pola `@Observable` terspesialisasi dan terisolasi per domain modular (`OrderBookState`, `TickerState`, `ChartState`).
2.  **Penghapusan Total `AnyView`**: Menggunakan generics eksplisit dan `@ViewBuilder` modifier untuk mempertahankan identitas statis pada kompilasi.
3.  **Throttling & Concurrency Sharding**: Memproses pembaruan socket murni pada background actor (`ActorIsolation`), lalu mendistribusikan *state diffing batch* ke `@MainActor` pada interval interval minimum 16ms (menyesuaikan kecepatan refresh frame layar).

#### Hasil Eksekusi
*   **Hitch Rate**: Menurun dari 8.4% menjadi **0.08%** (Target Apple Enterprise standard: < 1%).
*   **CPU Utilization**: Turun dari rata-rata 78% menjadi **12%**.
*   **Heap Allocations**: Mengurangi memory allocation churn sebesar **92%**.

---

### 9. Trade-offs

| Pendekatan / Teknologi | Keuntungan (Pros) | Konsekuensi & Risiko (Cons / Trade-offs) |
| :--- | :--- | :--- |
| **Observation Framework (`@Observable`)** | *Zero-boilerplate*; pelacakan dependensi granular per-properti; alokasi heap sangat minimal. | Membutuhkan dependensi minimum iOS 17+. Sulit digunakan pada ekosistem lama yang membutuhkan *backward compatibility* ke iOS 15/16. |
| **Combine (`ObservableObject`)** | Kompatibel penuh hingga iOS 13; kontrol alur reaktif canggih via operator Combine (`debounce`, `throttle`). | *Over-invalidation* pada level instansiasi; alokasi resource pipeline berat; potensi memory leaks jika pipeline tidak dibersihkan secara benar. |
| **Custom Layout Protocol** | Eksekusi layout performa native; kontrol perataan geometri piksel presisi; menghindari pembengkakan depth *AttributeGraph*. | Kurva pembelajaran matematika tata letak manual; tidak memiliki animasi transisi bawaan otomatis seperti komponen standar (`HStack`/`VStack`). |
| **Type-Erasure (`AnyView`)** | Fleksibilitas tinggi dalam arsitektur berbasis plugin atau rendering dinamis dari response JSON server (*SDUI*). | Menghancurkan performa kompilator Swift; menghentikan optimasi diffing graf *AttributeGraph*; memicu memory allocations konstan di stack/heap. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Kesalahan Fatal Umum (Common Anti-Patterns)
1.  **Inisialisasi Objek Status di dalam View Init**:
    ```swift
    // ANTI-PATTERN: View struct dibuat berulang kali oleh parent
    struct BadParentView: View {
        var body: some View {
            // Memory leak & instansiasi berulang setiap kali BadParentView dievaluasi
            BadChildView(viewModel: ExpensiveViewModel()) 
        }
    }
    ```
    *Solusi*: Gunakan `@State` untuk kepemilikan siklus hidup:
    ```swift
    struct GoodChildView: View {
        @State private var viewModel: ExpensiveViewModel

        init() {
            _viewModel = State(initialValue: ExpensiveViewModel())
        }
    }
    ```

2.  **Menyalahgunakan Identitas Eksplisit Mengakibatkan State Reset**:
    Menempatkan modifier `.id(UUID())` pada komponen yang sering di-render ulang akan merusak persistensi internal dan memutus rantai animasi transisi.

3.  **Melakukan Operasi Berat / Blocking di Dalam View Body**:
    Mengeksekusi format data kompleks (seperti `DateFormatter` instansiasi baru) secara langsung di dalam deklarasi `body`.

#### 10.2 Diagnostik & Panduan Troubleshooting
*   **Mendeteksi Penyebab Evaluasi Ulang (Re-evaluation)**:
    Suntikkan kode internal berikut pada properti `body` tampilan yang dicurigai lambat:
    ```swift
    let _ = Self._printChanges()
    ```
    Output console Xcode akan mencetak simpul pasti yang memicu render (Contoh: `@self changed`, `_viewModel changed`, atau `@identity changed`).
*   **Analisis Instruments**:
    Gunakan trace template **SwiftUI** di Xcode Instruments. Analisis panel **View Body** untuk melihat metrik durasi execution time dan jumlah pemanggilan (`Count`). Tampilan yang sehat harus memiliki rasio *Execution Count* berbanding perubahan data mendekati 1:1.

---

### 11. Best Practices (Production Checklist)

| Area | Item Pemeriksaan | Target Metrik / Standar |
| :--- | :--- | :--- |
| **Arsitektur** | Apakah seluruh domain state mutable menggunakan `@Observable` dan diisolasi ke `@MainActor`? | Nol mutasi state di luar thread utama; tidak ada ketergantungan antar instance viewModel yang melingkar. |
| **Struktur View** | Tidak ada penggunaan `AnyView` dalam codebase (Kecuali batasan dynamic UI framework eksternal). | 0 instansiasi `AnyView` terdeteksi di static analysis (SwiftLint). |
| **Identitas** | Elemen di dalam loop koleksi (`ForEach`) memiliki ID deterministik unik (bukan hash acak/array index). | Keberadaan ID stabil berbasis entitas domain database/API. |
| **Layout Depth** | Kedalaman hierarki komponen antarmuka terukur rata dan tidak bersarang terlalu dalam (> 10 levels deep). | Penggunaan `Layout` protocol untuk visual kompleks demi menjaga pohon DAG flat. |
| **Performansi** | Hitch Rate pada ProMotion Display (120 FPS). | **< 1.0%** durasi frame drop selama navigasi dan scrolling dinamis. |
| **Memori** | Tidak ada siklus retensi siklik pada closures atau bindings. | Bersih dari *leaked blocks* pada memory graph debugger saat menutup modul tampilan. |

---

### 12. Hands-on Practice

Implementasikan project terisolasi pada direktori lokal: `hands-on/m02/`.

#### Task: Mengembangkan Custom Canvas Matrix Layout dengan Observation
Bangun modul rendering matriks monitoring telemetri server enterprise yang menampilkan status CPU/Memori untuk 100 node simultan dengan target render 120 FPS.

#### Langkah Pengerjaan:
1.  Buka terminal dan navigasikan ke direktori kerja:
    ```bash
    mkdir -p hands-on/m02/TelemetryMatrix
    cd hands-on/m02/TelemetryMatrix
    swift package init --type executable
    ```
2.  Definisikan dependensi dan arsitektur file:
    *   `Sources/Model/NodeTelemetry.swift`: Model node berbasis identitas deterministik.
    *   `Sources/Engine/MatrixLayout.swift`: Protokol `Layout` kustom berbasis kalkulasi kisi adaptif (*Adaptive Grid Engine*).
    *   `Sources/ViewModel/TelemetryEngine.swift`: Status engine berbasis `@Observable` yang menerima emulasi fluktuasi sinyal.
    *   `Sources/Views/TelemetryMatrixView.swift`: Sub-tampilan terisolasi.
3.  Terapkan optimasi identitas struktural pada sel matriks sehingga perubahan pada Node #10 **tidak memicu render ulang** Node #0 hingga #9.
4.  Jalankan modul dan konfirmasi kestabilan memori menggunakan `Self._printChanges()`.

---

### 13. Exercise

#### Level: Easy
Refaktor kode di bawah ini untuk mengeliminasi penggunaan `AnyView` dan pertahankan struktur identitas tampilan statis:
```swift
// REFACTOR KODE INI:
struct StatusBadgeView: View {
    let isConnected: Bool
    
    var body: some View {
        if isConnected {
            return AnyView(Label("Online", systemImage: "bolt.fill").foregroundStyle(.green))
        } else {
            return AnyView(Label("Offline", systemImage: "bolt.slash").foregroundStyle(.red))
        }
    }
}
```

#### Level: Medium
Tuliskan sebuah custom modifier `.measureRenderTime(threshold: Double)` yang mencatat peringatan ke subsystem logging `OSLog` jika komputasi evaluasi rendering `body` sebuah tampilan melebihi ambang batas *threshold* yang ditentukan (misalnya: > 5ms).

#### Level: Hard
Implementasikan sebuah custom visual container bernama `RadialStackLayout` yang mengadopsi protokol `Layout`. Container ini harus mampu menempatkan subview secara melingkar (equidistant angles) berdasarkan kalkulasi trigonometris jari-jari (`radius`), menangani proposed size secara dinamis, dan mendukung animasi penambahan/pengurangan elemen secara mulus (*smooth transition*).

---

### 14. Challenge

**Skenario**: Anda adalah Lead Core UI Architect pada aplikasi perbankan tier-1. Tim desain menuntut dashboard transaksi real-time yang memiliki:
1.  Daftar transaksi tak hingga (*infinite scrolling*) dengan ratusan entri.
2.  Setiap baris berisi *mini-sparkline chart* yang terus beranimasi menampilkan fluktuasi nilai tukar valuta asing.
3.  Ketika aplikasi menerima notifikasi transfer masuk (Push via WebSocket), seluruh daftar harus otomatis bergeser turun secara dinamis untuk memberi ruang pada entri baru di posisi teratas tanpa menyebabkan *glitch* posisi scroll saat ini.

**Tantangan**:
*   Rancang implementasi arsitektur SwiftUI murni (iOS 17+) di mana *Hitch Rate* visual tetap berada di bawah **0.5%** pada layar 120Hz.
*   Anda tidak diizinkan menggunakan library eksternal (murni SwiftUI standard runtime).
*   Data mutasi nilai tukar yang masuk tiap detik tidak boleh memicu *re-render* terhadap komponen statis lain (label nama rekening, avatar, dan border container).
*   Sertakan strategi manajemen identitas transien untuk mempertahankan posisi scroll pengguna saat item baru disuntikkan di puncak daftar (*scroll offset stabilization*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1.  **Bagaimana sifat alokasi memori dari sebuah instance `struct` yang mengadopsi protokol `View` di SwiftUI?**
    *   A. Dialokasikan secara persisten di Heap bersama *Render Server*.
    *   B. Dialokasikan di Stack secara efisien dan dihancurkan segera setelah fungsi `body` mengembalikan representasi hierarki.
    *   C. Disimpan secara statis di segmen global aplikasi.
    *   D. Dikelola oleh reference counter ARC (Automatic Reference Counting).
2.  **Apa yang terjadi jika sebuah view memiliki dua kondisi percabangan `if-else` di dalam properti `body`?**
    *   A. Runtime SwiftUI menganggap kedua tampilan tersebut memiliki identitas yang sama.
    *   B. Kompiler membungkusnya ke dalam tipe `_ConditionalContent` dan memberikan dua identitas struktural terpisah.
    *   C. Terjadi error kompilasi karena result builder tidak mendukung percabangan logic.
    *   D. SwiftUI otomatis menggunakan UIKit fallback rendering.
3.  **Kapan sebaiknya modifier `.id(UUID())` digunakan secara berkala dalam siklus render yang sering berubah?**
    *   A. Selalu digunakan untuk menjamin data selalu diperbarui secara akurat.
    *   B. Sangat dianjurkan untuk transisi animasi performa tinggi.
    *   C. Hampir tidak pernah dianjurkan, karena memaksa runtime menghancurkan dan membangun kembali seluruh status internal tampilan.
    *   D. Hanya jika menggunakan `List` di iOS 13.
4.  **Apa fungsi utama dari protokol `Layout` yang diperkenalkan pada iOS 16?**
    *   A. Menggantikan seluruh siklus auto-layout UIKit secara imperative.
    *   B. Memungkinkan pengembang membuat layout engine kustom 2D non-linear dengan akses langsung ke ukuran proposal dan alokasi posisi anak.
    *   C. Mengonversi tampilan SwiftUI langsung ke drawing context Metal secara bypass.
    *   D. Mengatur rotasi layar antarmuka secara native.
5.  **Modifier `_printChanges()` berguna untuk apa dalam siklus pengembangan enterprise?**
    *   A. Mencetak dokumen antarmuka ke printer eksternal AirPrint.
    *   B. Melakukan logging serialisasi JSON status tampilan.
    *   C. Memeriksa simpul status atau identitas mana yang memicu evaluasi ulang `body` tampilan secara deterministik di console.
    *   D. Mengukur penggunaan daya baterai secara real-time.

#### Bagian 2: Intermediate (5 Pertanyaan)
6.  **Bagaimana `@Observable` (Observation framework) membedakan dependensi dibanding `ObservableObject` Combine?**
    *   A. `@Observable` memancarkan event setiap kali fungsi mutating dipanggil di latar belakang.
    *   B. `@Observable` mendaftarkan dependensi saat *runtime* hanya pada properti spesifik yang dibaca (*get*) selama evaluasi fungsi `body`, meminimalisir evaluasi yang tidak perlu.
    *   C. Combine lebih granular karena mengandalkan generic `@Published` property wrappers.
    *   D. `@Observable` memerlukan alokasi pipeline Combine ekstra yang tersembunyi secara macro.
7.  **Jika Parent View menawarkan ukuran `ProposedViewSize(width: nil, height: 100)` kepada Child View, apa arti proposal tersebut?**
    *   A. Induk menawarkan lebar bebas tak terhingga (*unspecified*) dan memaksa tinggi tepat 100 poin.
    *   B. Induk melarang anak memiliki lebar dan memotong tinggi menjadi 0.
    *   C. Induk membatalkan proses tata letak anak.
    *   D. Induk meminta anak untuk mengembalikan ukuran default layar perangkat.
8.  **Mengapa implementasi protokol `Equatable` pada View struct terkadang tidak mencegah pemanggilan `body`?**
    *   A. Karena SwiftUI mengabaikan seluruh implementasi protokol `Equatable`.
    *   B. Karena View tidak dibungkus dengan modifier `.equatable()` atau tidak dipisahkan dalam AttributeGraph node yang stabil.
    *   C. Karena struct View memiliki ukuran alokasi byte yang berbeda di memory register.
    *   D. Karena compiler Swift 6 secara otomatis menonaktifkan equality check pada UI types.
9.  **Apa peran cache (`inout Cache`) dalam implementasi custom `Layout` protocol?**
    *   A. Menyimpan buffer gambar bitmap hasil kalkulasi Metal.
    *   B. Memfasilitasi penyimpanan data kalkulasi komputasi geometris yang mahal antar pemanggilan fase `sizeThatFits` dan `placeSubviews`.
    *   C. Mengelola alokasi disk persistence status antar-aplikasi.
    *   D. Mencegah aplikasi mengalami crash ketika terjadi alokasi memori berlebih.
10. **Bagaimana cara mengisolasi pembacaan state frekuensi tinggi agar tidak merender ulang keseluruhan kompleks View?**
    *   A. Menggunakan modifier `.drawingGroup()` pada root container.
    *   B. Mengekstrak visual pembacaan nilai spesifik tersebut ke dalam unit Subview terkecil (*Leaf View*).
    *   C. Mengonversi tipe data menjadi objek string statis.
    *   D. Menjalankan SwiftUI View di background thread terpisah menggunakan detached Task.

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario Kasus 1**: Pada layar checkout pembayaran e-commerce, pengguna melaporkan input pada keyboard terasa macet (*lag/unresponsive*) saat mengetik alamat pengiriman. Analisis menunjukkan status alamat diikat langsung menggunakan binding (`$viewModel.shippingAddress`) ke dalam centralized `CheckoutState` yang memiliki 50 field data lainnya. Apa langkah remediasi arsitektural yang paling efisien?
12. **Skenario Kasus 2**: Anda mengintegrasikan komponen peta warisan berbasis `MKMapView` (UIKit) ke dalam aplikasi SwiftUI via `UIViewRepresentable`. Ketika parent view mengalami re-render, peta selalu me-reset titik zoom dan posisi koordinat ke titik default. Apa cacat implementasi yang terjadi pada `Coordinator` atau fungsi `updateUIView`?
13. **Skenario Kasus 3**: Profiling Time Profiler menunjukkan konsumsi CPU yang konstan (rata-rata 35%) bahkan saat aplikasi dalam kondisi idle (tidak ada interaksi pengguna). Ditemukan ada satu tampilan yang menggunakan animasi *infinite rotation effect* menggunakan timer Combine yang memutasi `@State`. Bagaimana merestrukturisasi animasi tersebut agar dieksekusi secara native di Render Server tanpa membebani CPU thread utama?

---

### Kunci Jawaban Evaluasi

#### Bagian 1: Basic
1.  **B**: View di SwiftUI adalah transient descriptions bertipe *struct*, yang dialokasikan sangat murah di stack dan langsung dihancurkan setelah *Display List* terbentuk.
2.  **B**: Kompiler membungkus percabangan result builder ke tipe generic internal `_ConditionalContent`, menciptakan dua identitas struktural unik yang terisolasi.
3.  **C**: Pemanggilan `.id(UUID())` memaksa destruksi eksplisit identitas tampilan beserta transien statenya, memicu alokasi ulang penuh yang merusak performa.
4.  **B**: Protokol `Layout` mengabstraksi fungsionalitas sizing 2D deterministik yang memberi kendali penuh pengukuran geometris tanpa perlu membungkus UIKit.
5.  **C**: Metode diagnostik internal `Self._printChanges()` mencetak pemicu re-evaluasi spesifik (state, identity, atau modifier) langsung ke output console.

#### Bagian 2: Intermediate
6.  **B**: Melalui macro registration, `@Observable` mencatat dependency reading saat *runtime* hanya untuk *field* yang diakses dalam fase eksekusi `body`.
7.  **A**: Nilai `nil` pada ProposedViewSize mewakili `.unspecified`, yang berarti komponen anak bebas menentukan ukuran idealnya sendiri pada sumbu tersebut.
8.  **B**: SwiftUI memerlukan pemanggilan eksplisit modifier `.equatable()` pada komponen yang mengadopsi `Equatable` agar AttributeGraph dapat menggunakan fungsi komparasi `==` kustom dan melompati pemanggilan `body`.
9.  **B**: Parameter `Cache` dirancang spesifik untuk menyimpan hasil pengukuran antara fase negosiasi ukuran (*size proposal*) dan fase peletakan visual (*subviews placement*), menghindari kalkulasi ganda.
10. **B**: Dengan mengekstrak pembacaan state ke leaf subview, hanya fungsi `body` subview tersebut yang dimasukkan ke antrean invalidate oleh AttributeGraph saat nilainya berubah.

#### Bagian 3: Skenario Kasus Produksi
11. **Jawaban Solusi Kasus 1**:
    Akar masalah adalah invalidasi hierarki global: Setiap ketukan tombol memperbarui status pusat yang menyebabkan seluruh layar checkout dievaluasi ulang. Solusinya: Pisahkan model data alamat menjadi sub-state terisolasi atau gunakan *local transient state* (`@State`) di dalam komponen `ShippingAddressTextField`. Sinkronisasikan data ke `CheckoutState` utama hanya saat fase *focus loss* (onEditingChanged false), *debounced input*, atau aksi penekanan tombol submit.
12. **Jawaban Solusi Kasus 2**:
    Cacat terjadi karena fungsi `updateUIView(_:context:)` secara keliru mengeksekusi ulang konfigurasi posisi titik kamera peta pada setiap siklus pembaruan tanpa memeriksa apakah koordinat baru berbeda dari status `MKMapView` saat ini. Solusi: Gunakan properti pembanding di dalam `updateUIView` untuk memverifikasi apakah `uiView.region.center != newCoordinate`. Jika perubahannya identik atau bersumber dari interaksi internal pengguna yang telah dicatat oleh `Coordinator`, lewati pemanggilan metode update pada `MKMapView`.
13. **Jawaban Solusi Kasus 3**:
    Menggunakan Combine Timer untuk memutasi `@State` sudut rotasi setiap tick menyebabkan evaluasi `body` terus berjalan berulang-ulang di CPU utama aplikasi (merusak AttributeGraph efficiency). Solusi: Hilangkan mutasi status via timer. Gunakan declarative transition murni SwiftUI dengan framework animasi:
    ```swift
    Image(systemName: "arrow.triangle.2.circlepath")
        .rotationEffect(.degrees(isSpinning ? 360 : 0))
        .animation(.linear(duration: 1).repeatForever(autoreverses: false), value: isSpinning)
        .onAppear { isSpinning = true }
    ```
    Animasi ini akan ditransfer (*offloaded*) langsung ke **Render Server** (*Core Animation / Metal pipeline*), sehingga konsumsi CPU aplikasi kembali ke level **0%** saat idle.

---

### 16. Summary
*   **SwiftUI Runtime**: Ditenagai oleh *AttributeGraph*, grafik dependensi non-siklik yang memetakan relasi antara State dan View primitives. Mutasi status hanya mengevaluasi sub-grafik yang terdampak langsung.
*   **View Identity**: Penentu masa hidup (*lifetime*) dan status komponen UI. Pertahankan *Structural Identity* yang stabil dan hindari penggunaan `AnyView` demi efisiensi diffing mesin render.
*   **Layout Lifecycle**: Mengikuti protokol negosiasi deterministik 3 langkah: *Parent proposes, child chooses, parent places*.
*   **Modern State Isolation**: Framework `Observation` (`@Observable`) menggeser paradigma notifikasi berbasis *instance* ke tingkat *properti*, secara radikal menekan over-invalidation antarmuka pada skala sistem enterprise.
*   **Production Discipline**: Performa tinggi (120 FPS tanpa frame drops) dicapai melalui modularitas leaf views, pemanfaatan protokol `Layout`, penanganan identitas deterministik, serta profiling berkelanjutan dengan Xcode Instruments.