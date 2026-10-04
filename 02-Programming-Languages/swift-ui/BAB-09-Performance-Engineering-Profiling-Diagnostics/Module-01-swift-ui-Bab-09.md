# BAB 09 MODULE 01: Performance Engineering, Profiling, & Diagnostics

---

## SEKSI 01 — IDENTITAS MODUL

| Parameter | Deskripsi |
| :--- | :--- |
| **Modul ID** | `SWIFTUI-PERF-0901` |
| **Kurikulum** | Apple Developer Ecosystem / Modern Swift & SwiftUI Architecture |
| **Track** | Core iOS Frameworks & Systems Engineering |
| **Kategori** | `02-Programming-Languages` |
| **Topik** | Performance Engineering, Profiling, & Diagnostics |
| **Tingkat Kesulitan** | Lanjutan (Advanced) |
| **Prasyarat** | Pemahaman mendalam tentang siklus hidup SwiftUI, Concurrency (async/await, Actor), Combine Framework, serta Memory Management ARC (Automatic Reference Counting). |
| **Tech Stack** | Swift 5.10 / Swift 6, SwiftUI 5.0 (iOS 17+), Xcode 15/16 Instruments, `os.signpost`, Observation Framework. |
| **Kata Kunci** | `AttributeGraph`, `Structural Identity`, `Explicit Identity`, `Hitch Rate`, `os_signpost`, `Time Profiler`, `Self._printChanges()`, `Micro-invalidation`. |

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik diharapkan mampu:

1. **Menganalisis (C4)** mekanisme internal *engine* SwiftUI, khususnya bagaimana `AttributeGraph` membangun dependensi state dan mengevaluasi node komputasi.
2. **Mendiagnosis (C4)** anomali rendering antarmuka seperti *frame hitches*, *micro-invalidations*, dan *dropped frames* menggunakan Xcode Instruments (SwiftUI View Hierarchy, Time Profiler, Allocations).
3. **Mengevaluasi (C5)** dampak dari *Structural Identity* vs *Explicit Identity* terhadap siklus hidup view dan konsumsi sumber daya CPU/GPU.
4. **Mengimplementasikan (C3)** instrumentasi kustom menggunakan `OSSignposter` dan `Logger` terpadu untuk melacak durasi eksekusi body dan latensi pemrosesan data.
5. **Merekayasa Ulang (C6)** antarmuka berfrekuensi pembaruan tinggi (seperti streaming data real-time) agar beroperasi secara konsisten dalam batas anggaran frame (16.6ms untuk 60Hz, 8.3ms untuk 120Hz ProMotion).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma imperatif (`UIKit`), performa berakar pada *manajemen mutasi langsung* terhadap pohon view (`UIView`/`CALayer`). Pengembang bertanggung jawab mengalokasikan, memperbarui properti, dan menghancurkan objek di memori secara manual. 

Dalam paradigma deklaratif (`SwiftUI`), antarmuka adalah fungsi murni dari state:

$$\text{View} = f(\text{State})$$

Mental model performa SwiftUI bergeser dari "Kapan objek ini dialokasikan?" ke:

> **"Kapan dan mengapa sub-graf dari dependensi state memicu evaluasi ulang blok `body`?"**

```
+------------------------------------------------------------------+
|                      MENTAL MODEL PERFORMA                       |
+------------------------------------------------------------------+
| View Structs != Visual Elements on Screen                        |
| - View Structs : Cetak biru deklaratif yang murah (Stack)        |
| - Render Tree  : Objek grafis persisten yang mahal (CoreAnimation|
|                  / Metal Render Server)                          |
|                                                                  |
| Biaya komputasi SwiftUI TIDAK berada pada alokasi struct view,   |
| melainkan pada:                                                  |
| 1. Evaluasi blok body yang redundant (Over-invalidation).        |
| 2. Perhitungan layout dan geometri yang berulang-ulang.          |
| 3. Kehilangan identitas view yang memicu reset state internal.   |
+------------------------------------------------------------------+
```

Pengembang sistem harus membedakan antara pembuatan struct (instansiasi cepat pada *call stack*) dan evaluasi `body` (yang menghasilkan node pada *AttributeGraph* dan diterjemahkan ke *render server*). Kunci rekayasa performa adalah meminimalkan frekuensi eksekusi `body` dan mempersempit cakupan invalidasi dependensi (*observation granularity*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Proses dari mutasi state hingga piksel digambar pada layar melewati serangkaian subsistem:

```
[State Mutation] 
       │
       ▼
[Dependency Registration] ──> (AttributeGraph Engine)
       │
       ▼
[Dirty Subgraph Marking]
       │
       ▼
[Dynamic Property Resolution] ──> (Evaluasi @State, @Binding, @Observable)
       │
       ▼
[Body Execution] ──> Menghasilkan Pohon View Baru (Value Types)
       │
       ▼
[Identity & Structural Diffing] ──> (Structural vs Explicit ID)
       │
  (Tidak Berubah) ──> [Bypass Layout & Draw]
       │ (Berubah)
       ▼
[Layout Engine Pass] ──> (ProposedSize -> Min/Ideal/Max -> CommittedSize)
       │
       ▼
[Render Tree Commit] ──> (Transaction dikirim via IPC ke Render Server)
       │
       ▼
[CoreAnimation / Metal Render Server] ──> [Display / VSYNC Signal]
```

### Siklus Frame Budgeting
Pada layar ProMotion 120Hz, *frame deadline* adalah **8.33 milidetik**. Waktu ini terbagi antara:
1. **App Process** (Mutasi State + Evaluasi `body` + Layout Calculation) $\le 4.0\text{ ms}$
2. **Render Server & IPC** (Display List generation & Commit) $\le 2.0\text{ ms}$
3. **GPU Rendering** (Pixel rasterization) $\le 2.33\text{ ms}$

Pelanggaran terhadap batas ini di tingkat aplikasi secara langsung menghasilkan *Scroll Hitch* atau visual stuttering.

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. AttributeGraph (AG)
`AttributeGraph` adalah mesin internal berbasis C++ milik Apple yang mengelola dependensi reaktif SwiftUI. Setiap kali properti terbungkus (seperti `@State`, `@FocusState`, atau properti `@Observable`) dibaca di dalam `body`, `AttributeGraph` membuat sebuah simpul (*node*) dan mencatat relasi *edge* terarah antara properti tersebut dan closure evaluasi view.
* Ketika properti dimutasi, simpul terkait ditandai sebagai *dirty*.
* Pada frame berikutnya, SwiftUI melintasi graf secara topologis untuk mengevaluasi hanya simpul-simpul yang *dirty*.

### 2. View Identity: Structural vs. Explicit
SwiftUI mengandalkan konsep identitas untuk mempertahankan status view antar render:

* **Structural Identity**: Ditentukan secara implisit oleh posisi view dalam pohon hirarki kondisional. Menggunakan kontrol alur Swift seperti `if-else` atau `switch` menciptakan struktur tipe:
  ```swift
  _ConditionalContent<TrueView, FalseView>
  ```
  Jika kondisi berubah, SwiftUI menghancurkan view lama beserta seluruh internal state-nya dan membuat view baru dari awal.
* **Explicit Identity**: Ditentukan menggunakan identifier eksplisit via parameter `id` pada `ForEach` atau modifier `.id(...)`. Perubahan pada eksplisit ID memaksa `AttributeGraph` melepaskan (*deallocate*) node lama dan merekonstruksi ulang node baru secara menyeluruh.

### 3. DynamicProperty Protocol
Semua property wrapper bawaan SwiftUI (`@State`, `@Environment`, `@ObservedObject`) mengadopsi protokol privat-publik `DynamicProperty`.
```swift
public protocol DynamicProperty {
    mutating func update()
}
```
Ketika view hendak dievaluasi, SwiftUI memanggil `update()` pada semua *fields* yang mengadopsi `DynamicProperty` untuk mengaitkan memori frame dengan simpul `AttributeGraph` yang aktif. Inilah mengapa membaca properti di luar evaluasi `body` (misalnya di dalam `init`) sering kali menyebabkan *undefined behavior* atau *crash*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Masalah Over-Invalidation pada Objek Pengamatan
Sebelum Swift 5.9, implementasi standar mengandalkan protokol `ObservableObject` dan Combine:

```swift
class FinancialFeedViewModel: ObservableObject {
    @Published var btcPrice: Double = 0.0
    @Published var ethPrice: Double = 0.0
}
```

Ketika `btcPrice` berubah, `objectWillChange.send()` dipanggil. Akibatnya, **seluruh view yang mengamati instance ini via `@ObservedObject` akan menginvalidation seluruh `body`-nya**, bahkan jika view tersebut hanya membaca properti `ethPrice`.

Dengan framework `Observation` (Swift 5.9+ / iOS 17+), model berubah menjadi sistem *field-level tracking* berbasis macro:

```swift
@Observable
class FinancialFeedModel {
    var btcPrice: Double = 0.0
    var ethPrice: Double = 0.0
}
```

Macro `@Observable` menyuntikkan instruksi `withMutation` dan mengimplementasikan pelacakan akses properti via registrasi runtime. Ketika suatu view mengevaluasi `body`, hanya pembacaan properti spesifik yang didaftarkan ke `AttributeGraph`. Perubahan pada `btcPrice` sekarang **hanya** mere-evaluasi view yang mengakses `btcPrice`.

### Offscreen Rendering dan Overdraw
Penggunaan modifier tertentu memaksa CoreAnimation memindahkan rendering dari pipeline standar satu-lintasan (*single-pass*) ke buffer terpisah di luar layar (*offscreen buffer*) sebelum dikomposisikan kembali ke frame buffer utama:
* `.cornerRadius()` yang digabungkan dengan `.clipped()` atau `.shadow()`
* Penggunaan berlebihan modifier `.opacity()` pada hirarki tampilan kompleks (alih-alih mengatur warna transparan langsung pada elemen anak).
* Masking via `.mask(...)`.

Offscreen rendering ini memicu *context switching* GPU yang signifikan, menaikkan utilisasi memori GPU, dan menjadi penyebab utama *Hitch Rate* tinggi saat proses *scrolling*.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah perbandingan langsung antara implementasi yang memiliki *performance defect* (over-invalidation dan identity destruction) dan implementasi yang telah dioptimalkan secara arsitektural.

### Skenario Antipattern: Monolithic Invalidation & Dynamic Identity
```swift
import SwiftUI

// MODEL NON-OPTIMAL
class TelemetryMonitor: ObservableObject {
    @Published var systemTemperature: Double = 45.0
    @Published var networkLatencyMs: Int = 12
    @Published var packetLog: [String] = []
}

struct UnoptimizedTelemetryView: View {
    @ObservedObject var monitor: TelemetryMonitor

    var body: some View {
        VStack(spacing: 20) {
            // Self._printChanges() akan menunjukkan bahwa view ini terus-menerus
            // dievaluasi ulang meskipun packetLog tidak berubah di sini.
            let _ = Self._printChanges()
            
            Text("Metrics Overview")
                .font(.headline)
            
            // Bug Performa: Menggunakan UUID baru menghancurkan identitas
            // dan memaksa penghitungan ulang layout seluruh subtree
            VStack {
                Text("Temp: \(monitor.systemTemperature, specifier: "%.1f")°C")
                Text("Latency: \(monitor.networkLatencyMs) ms")
            }
            .id(UUID()) // ANTIPATTERN: Penghancuran Explicit Identity
            
            ExpensiveStaticChart()
        }
    }
}

struct ExpensiveStaticChart: View {
    var body: some View {
        Rectangle()
            .fill(Color.blue.opacity(0.3))
            .frame(height: 150)
            .overlay(Text("Komputasi Layout Berat"))
    }
}
```

### Skenario Optimal: Granular State Isolation & Persistent Identity
```swift
import SwiftUI
import Observation

// MODEL OPTIMAL: Menggunakan Swift 5.9+ Observation Framework
@Observable
final class OptimizedTelemetryModel {
    var systemTemperature: Double = 45.0
    var networkLatencyMs: Int = 12
    var packetLog: [String] = []
}

struct OptimizedTelemetryView: View {
    // Model disuntikkan, tetapi tidak memicu invalidasi view induk 
    // jika propertinya tidak dibaca secara langsung di blok ini.
    var model: OptimizedTelemetryModel

    var body: some View {
        VStack(spacing: 20) {
            let _ = Self._printChanges()
            
            Text("Metrics Overview")
                .font(.headline)
            
            // Evaluasi diisolasi ke leaf-node subview
            MetricsDisplaySubView(model: model)
            
            // Subtree ini tidak pernah dievaluasi ulang ketika 
            // systemTemperature atau networkLatencyMs berubah
            ExpensiveStaticChart()
        }
    }
}

struct MetricsDisplaySubView: View {
    var model: OptimizedTelemetryModel

    var body: some View {
        let _ = Self._printChanges()
        VStack {
            // Hanya subview ini yang mendaftarkan dependensi 
            // ke model.systemTemperature dan model.networkLatencyMs
            Text("Temp: \(model.systemTemperature, specifier: "%.1f")°C")
            Text("Latency: \(model.networkLatencyMs) ms")
        }
        // Identitas struktural dipertahankan tanpa modifier .id(UUID())
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Evaluasi Kasus Unoptimized:
* **Baris 4–8 (`class TelemetryMonitor: ObservableObject`)**: Menggunakan `ObservableObject`. Setiap kali `packetLog` atau `networkLatencyMs` berubah, *publisher* `objectWillChange` memicu sinyal umum yang menandai seluruh instans sebagai *dirty*.
* **Baris 11 (`@ObservedObject var monitor: TelemetryMonitor`)**: Mendaftarkan seluruh `UnoptimizedTelemetryView` ke event perubahan model. Jika ada 1 properti termutasi 60 kali per detik, seluruh `body` dijalankan 60 kali per detik.
* **Baris 16 (`let _ = Self._printChanges()`)**: Method diagnostik internal SwiftUI. Mencetak alasan invalidasi ke Xcode Console (misalnya: `@ObservedObject changed`).
* **Baris 26 (`.id(UUID())`)**: Kesalahan fatal. Mengalokasikan `UUID` baru pada setiap siklus evaluasi `body`. SwiftUI menganggap view ini adalah entitas visual yang benar-benar berbeda, menghapus state animasi sebelumnya, melepaskan node cache `AttributeGraph`, dan mengalokasikan ulang memori.
* **Baris 28 (`ExpensiveStaticChart()`)**: Karena berada dalam `body` induk yang sama tanpa partisi dependensi, `ExpensiveStaticChart` dievaluasi ulang berulang kali meskipun isinya konstan.

### Evaluasi Kasus Optimized:
* **Baris 4–8 (`@Observable final class OptimizedTelemetryModel`)**: Menggunakan macro `@Observable`. Tidak ada agregasi pembaruan via `Combine`. Setiap properti memiliki *access observation tracking* independen.
* **Baris 13 (`var model: OptimizedTelemetryModel`)**: Perhatikan ketiadaan wrapper `@ObservedObject`. Dalam sistem `@Observable`, struct view murni cukup menyimpan referensi objek.
* **Baris 18–25 (`OptimizedTelemetryView.body`)**: `OptimizedTelemetryView` sama sekali tidak membaca nilai `systemTemperature` atau `networkLatencyMs`. Akibatnya, `AttributeGraph` **tidak meregistrasikan hubungan dependensi** antara `OptimizedTelemetryView` dan mutasi metrik.
* **Baris 33–45 (`MetricsDisplaySubView`)**: Akses aktual ke `model.systemTemperature` terjadi di sini. Maka, hanya node `MetricsDisplaySubView` pada `AttributeGraph` yang ditandai *dirty* saat nilai metrik berubah. `ExpensiveStaticChart()` tetap tidak tersentuh di memori render cache.

---

## SEKSI 09 — STUDI KASUS NYATA

### Latar Belakang Masalah
Sebuah platform pertukaran aset kripto enterprise melaporkan masalah degradasi performa (*critical hitching*) pada modul order-book transaksi real-time. Aplikasi berjalan pada target iOS 17 dengan refresh rate data WebSocket hingga 50 pembaruan per detik (50 Hz). 

### Gejala:
1. Pengguna mengalami *stuttering* parah (frame drop) saat menggulir daftar order book.
2. Metrik Xcode Instruments menunjukkan *Hitch Rate* rata-rata sebesar **42.8 ms/s** (ambang batas kritis Apple: > 5 ms/s dinilai buruk).
3. Penggunaan CPU melonjak ke 85% pada iPhone 14 Pro, memicu *thermal throttling* dalam waktu 3 menit penggunaan aktif.

### Temuan Diagnostik:
1. `Time Profiler` mengidentifikasi bahwa 60% siklus CPU dihabiskan dalam `AG::Graph::UpdateStack` dan fungsi pembuatan layout `SwiftUI.View.body.getter`.
2. Setiap kali paket WebSocket tiba di background thread, data di-dispatch secara mentah ke Main Thread, menyebabkan `List` yang berisi 200 baris merender ulang seluruh komponen baris, termasuk elemen yang tidak terlihat di viewport.
3. Objek baris model tidak memiliki *Stable Identity*, melainkan menggunakan indeks array numerik murni yang bergeser setiap kali ada order baru di posisi puncak (*order inserted at index 0*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Solusi performa tinggi menerapkan 3 pilar:
1. **Throttling/Coalescing Event**: Menyatukan pembaruan data frekuensi tinggi via Swift Concurrency AsyncSequence / Buffering.
2. **Stable Explicit Identity**: Mencegah realokasi hirarki view.
3. **OSSignpost Telemetry**: Mengukur durasi commit pembaruan antarmuka secara presisi.

```swift
import SwiftUI
import Observation
import OSLog

// MARK: - 1. DOMAIN MODEL DENGAN IDENTITAS STABIL
struct OrderBookEntry: Identifiable, Hashable, Sendable {
    let id: Double // Menggunakan harga unik sebagai stable explicit identity
    let price: Double
    var volume: Double
    let isAsk: Bool
}

// MARK: - 2. ACTOR BUFFERING ENGINE (OFF-MAIN THREAD)
actor OrderBookBufferEngine {
    private var pendingOrders: [Double: OrderBookEntry] = [:]
    
    func ingest(_ order: OrderBookEntry) {
        pendingOrders[order.id] = order
    }
    
    func flush() -> [OrderBookEntry] {
        defer { pendingOrders.removeAll(keepingCapacity: true) }
        return pendingOrders.values.sorted { $0.price > $1.price }
    }
}

// MARK: - 3. INSTRUMENTED VIEW MODEL
@Observable
@MainActor
final class OrderBookViewModel {
    private(set) var activeOrders: [OrderBookEntry] = []
    
    @ObservationIgnored
    private let logger = Logger(subsystem: "com.enterprise.orderbook", category: "Performance")
    @ObservationIgnored
    private let signposter = OSSignposter(subsystem: "com.enterprise.orderbook", category: "ViewRendering")
    @ObservationIgnored
    private let bufferEngine = OrderBookBufferEngine()
    @ObservationIgnored
    private var isStreaming = false
    
    func startReceivingTicks() {
        guard !isStreaming else { return }
        isStreaming = true
        
        // Background ingestion simulator
        Task.detached(priority: .userInitiated) { [bufferEngine = self.bufferEngine] in
            while true {
                try? await Task.sleep(nanoseconds: 5_000_000) // 200 pembaruan per detik (5ms)
                let dummyPrice = Double.random(in: 60000...61000).rounded()
                let entry = OrderBookEntry(
                    id: dummyPrice,
                    price: dummyPrice,
                    volume: Double.random(in: 0.1...5.0),
                    isAsk: Bool.random()
                )
                await bufferEngine.ingest(entry)
            }
        }
        
        // Display Synchronization Loop: Dibatasi pada 60 FPS (16.6ms) 
        // Mengurangi invalidasi AttributeGraph dari 200 Hz menjadi 60 Hz
        Task { @MainActor in
            while isStreaming {
                try? await Task.sleep(nanoseconds: 16_666_667)
                await self.drainBufferToUI()
            }
        }
    }
    
    private func drainBufferToUI() async {
        let state = signposter.beginInterval("FlushAndApplyState")
        let updates = await bufferEngine.flush()
        
        guard !updates.isEmpty else {
            signposter.endInterval("FlushAndApplyState", state)
            return
        }
        
        // Batch Mutation: Meminimalkan diskontinuitas State
        self.activeOrders = updates
        signposter.endInterval("FlushAndApplyState", state)
    }
}

// MARK: - 4. PERFORMANCE-OPTIMIZED VIEW HIERARCHY
struct HighSpeedOrderBookView: View {
    @State private var viewModel = OrderBookViewModel()
    
    var body: some View {
        VStack(spacing: 0) {
            HeaderMetricView()
            
            List {
                // List menggunakan UICollectionView di backend, 
                // efisien untuk cell reuse jika explicit identity konstan.
                ForEach(viewModel.activeOrders, id: \.id) { order in
                    OrderRowView(order: order)
                }
            }
            .listStyle(.plain)
            // Memaksa rendering CoreAnimation layer hardware caching
            .drawingGroup() 
        }
        .task {
            viewModel.startReceivingTicks()
        }
    }
}

struct HeaderMetricView: View {
    var body: some View {
        HStack {
            Text("Price (USD)").font(.caption).bold()
            Spacer()
            Text("Volume").font(.caption).bold()
        }
        .padding(.horizontal)
        .frame(height: 32)
        .background(Color(.secondarySystemBackground))
    }
}

// Subview Equatable murni untuk isolasi total
struct OrderRowView: View, Equatable {
    let order: OrderBookEntry
    
    // Equatable manual untuk memotong perbandingan diff yang tidak relevan
    static func == (lhs: OrderRowView, rhs: OrderRowView) -> Bool {
        lhs.order.id == rhs.order.id &&
        lhs.order.volume == rhs.order.volume
    }
    
    var body: some View {
        HStack {
            Text("\(order.price, specifier: "%.2f")")
                .font(.system(.body, design: .monospaced))
                .foregroundColor(order.isAsk ? .red : .green)
            Spacer()
            Text("\(order.volume, specifier: "%.4f")")
                .font(.system(.body, design: .monospaced))
        }
        .padding(.vertical, 2)
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih mekanisme arsitektural yang tepat melibatkan kompromi teknis:

| Karakteristik | `@Observable` (Macro) | `ObservableObject` (Combine) | View dengan State Binding Lokal |
| :--- | :--- | :--- | :--- |
| **Granularitas Tracking** | Per-field property read | Per-instance level (`objectWillChange`) | Per-value direct pass |
| **Alokasi Memori** | Rendah (tidak ada heap Combine publisher) | Menengah (overhead sink & cancellables) | Minimal (Stack allocation) |
| **Kompatibilitas Runtime** | iOS 17.0+ / macOS 14.0+ | iOS 13.0+ | iOS 13.0+ |
| **Kompleksitas Refactoring**| Rendah (menggunakan property standard) | Menengah (memerlukan `@Published`) | Rendah |

### Analisis `.drawingGroup()` vs Default Rendering

```
+--------------------------------------------------------------------------------+
|                        PILIHAN STRATEGI RENDERING                              |
+--------------------------------------------------------------------------------+
| Fitur                  | Default (CoreAnimation) | Metal (.drawingGroup())     |
|------------------------+-------------------------+-----------------------------|
| Tipe Pipeline          | Multiple CALayers       | Single MTLTexture (Raster)  |
| Penggunaan Komposisi   | Sangat baik untuk teks  | Berat pada teks halus       |
| Skalabilitas Elemen    | Drop frame jika > 500   | Stabil hingga ribuan node   |
| Overhead Memori Alokasi| Rendah per view         | Alokasi render buffer besar |
| Interaktivitas View    | Responsivitas sentuh UI | Berpotensi menurunkan touch |
|                        | bawaan                  | responsiveness jika statis  |
+--------------------------------------------------------------------------------+
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The `@State` Re-initialization Trap
Menginisialisasi properti `@State` secara eksplisit di dalam konstruktor struct view adalah salah satu sumber bug performa dan konsistensi data yang fatal:

```swift
// PITFALL
struct UserCardView: View {
    @State private var localName: String
    
    init(remoteName: String) {
        // ANTIPATTERN: Ini TIDAK memperbarui state jika remoteName berubah!
        // State storage persisten di AttributeGraph mengabaikan nilai baru ini.
        _localName = State(initialValue: remoteName)
    }
    
    var body: some View {
        Text(localName)
    }
}
```
*Dampak Performa:* SwiftUI mengalokasikan memori wrapper baru pada setiap panggilan `init`, tetapi runtime engine segera membuangnya untuk mempertahankan state lama yang sudah terdaftar di `AttributeGraph`.

### 2. Layout Thrashing via Computed Properties
Melakukan pemrosesan data (seperti filtering atau sorting) langsung di dalam computed property `body`:

```swift
// PITFALL
var body: some View {
    List(heavyList.sorted(by: { $0.date > $1.date })) { item in // RUNTIME DISASTER
        Text(item.title)
    }
}
```
*Dampak Performa:* Algoritma pengurutan dieksekusi **pada setiap siklus layout/render pass**, memblokir Main Thread dan menurunkan performa menjadi < 20 FPS.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Pemakaian `AnyView` Tanpa Batasan (Type Erasure Abuse)
* *Kesalahan:* Membungkus view dengan `AnyView` untuk mempermudah handling kompilasi.
* *Mengapa Berbahaya:* `AnyView` menghapus informasi tipe statis pada waktu kompilasi. Mesin SwiftUI kehilangan kemampuan untuk melakukan optimasi struktur hirarki (*structural diffing optimization*) dan harus menghancurkan serta membangun ulang seluruh node graf tampilan.
* *Solusi:* Gunakan `@ViewBuilder` atau bangun tipe kontainer komposit khusus.

```swift
// SALAH
func statusIndicator(state: Status) -> AnyView {
    if state == .active {
        return AnyView(Circle().fill(Color.green))
    } else {
        return AnyView(Rectangle().fill(Color.gray))
    }
}

// BENAR
@ViewBuilder
func statusIndicator(state: Status) -> some View {
    if state == .active {
        Circle().fill(Color.green)
    } else {
        Rectangle().fill(Color.gray)
    }
}
```

### 2. State Mutation Selama Body Evaluation
* *Kesalahan:* Mengubah variabel state secara langsung di dalam jalur eksekusi body.
* *Mengapa Berbahaya:* Memicu siklus rekursif: `Mutation -> Invalidates Graph -> Triggers Body -> Mutation`. Hal ini menyebabkan *log warnings*, degradasi performa seketika, atau pemutusan paksa (*crash*) oleh runtime SwiftUI (`AttributeGraph: cycle detected`).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Aturan Leaf-Node Dependency**: Pecah tampilan menjadi subview sekecil mungkin (*leaf nodes*) yang hanya menerima data primitif atau model yang dibutuhkannya. Semakin jauh dependensi state ditekan ke bawah pohon hierarki, semakin sedikit view induk yang perlu dievaluasi ulang.
2. **Deterministic Struct Identity**: Pastikan properti `id` pada `Identifiable` bersifat deterministik dan unik secara persisten (misalnya database ID atau UUID dari payload, **bukan** UUID instan yang digenerate di view).
3. **Strict Equatable Adoption**: Jika subview memiliki logika rendering kompleks yang sering terpapar evaluasi ulang dari view induk, terapkan protokol `Equatable` secara eksplisit dan gunakan modifier `.equatable()`.
4. **Isolasi Task Lifecycle**: Selalu bind *long-running tasks* ke siklus hidup tampilan menggunakan modifier `.task(id:)` agar komputasi otomatis dibatalkan (*cancelled*) ketika view keluar dari hirarki layar.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Hitches and Hitch Rate Metrics
Apple mengukur kualitas rendering aplikasi menggunakan metrik **Scroll Hitch Rate**:

$$\text{Hitch Rate} = \frac{\text{Total Hitch Time (ms)}}{\text{Total Scroll Time (seconds)}}$$

* Target: $\le 1.0\text{ ms/s}$ (Sangat Baik / Smooth)
* Kritis: $> 5.0\text{ ms/s}$ (Terlihat stuttering oleh mata manusia)

### Prosedur Profiling Menggunakan Xcode Instruments:
1. Buka Xcode $\rightarrow$ `Open Developer Tool` $\rightarrow$ `Instruments`.
2. Pilih template **SwiftUI** (tersedia sejak Xcode 13/14).
3. Tambahkan trace instrumen:
   * **View Body**: Melacak jumlah eksekusi body per tipe View dan durasi rata-rata per view.
   * **View Properties**: Menginspeksi frekuensi pembacaan DynamicProperty.
   * **Time Profiler**: Menganalisis *Hot Paths* pada CPU. Identifikasi pemanggilan fungsi sistem seperti `AG::Graph::UpdateStack`.
4. Sortir kolom `View Body` berdasarkan **Count**. Tampilan apa pun yang memiliki angka eksekusi puluhan kali lipat lebih tinggi dari interaksi pengguna mengindikasikan kebocoran invalidasi state (*micro-invalidation leak*).

---

## SEKSI 16 — KEAMANAN & HARDENING

Optimasi antarmuka performa tinggi memiliki implikasi keamanan langsung terhadap integritas data di memori:

1. **State Leakage via Long-Lived Singletons**: Menggunakan ViewModel bersama yang di-retain secara global untuk menghindari biaya alokasi dapat membocorkan data terenkripsi pengguna sebelumnya. Terapkan pembersihan memori agresif pada method `deinit`.
2. **Screen Redaction Performance**: Ketika aplikasi beralih ke background, sistem sering kali menerapkan modifier `.redacted(reason: .placeholder)` untuk menutupi informasi sensitif. Jika implementasi masking ini memicu layout recalculation yang masif saat transisi backgrounding, aplikasi berisiko dihentikan (*killed*) oleh *watchdog process* sistem operasi karena memakan waktu lebih dari alokasi waktu suspensi (5 detik). Pastikan masking tidak memicu kalkulasi ulang dependensi eksternal.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Diagnostic Runtime API Bawaan
SwiftUI menyediakan hook runtime internal yang dapat diaktifkan dalam mode debug:

```swift
struct DiagnosticsView: View {
    @State private var counter = 0

    var body: some View {
        #if DEBUG
        // Mencetak properti spesifik yang memicu re-render ke Xcode Console
        let _ = Self._printChanges()
        #endif
        
        Button("Increment: \(counter)") {
            counter += 1
        }
    }
}
```

### Advanced Tracing Menggunakan `os.signpost`
Integrasi pelacakan tingkat sistem untuk visualisasi langsung pada linimasa Instruments:

```swift
import OSLog

final class TelemetryInstrumentsEngine {
    static let shared = TelemetryInstrumentsEngine()
    let signposter = OSSignposter(subsystem: "com.enterprise.app", category: "LayoutPipeline")
    
    func traceCriticalWork<T>(_ workName: StaticString, execute: () -> T) -> T {
        let signpostID = signposter.makeSignpostID()
        let state = signposter.beginInterval(workName, id: signpostID)
        defer {
            signposter.endInterval(workName, state)
        }
        return execute()
    }
}
```
Interval ini akan muncul sebagai *metadata track* visual di Xcode Instruments, memungkinkan Anda membandingkan waktu eksekusi kode Anda dengan *Frame Commit* CoreAnimation secara mikrodetik.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+-----------------------------------------------------------------------------------+
|                        PERFORMANCE OPTIMIZATION CHEAT SHEET                       |
+-----------------------------------------------------------------------------------+
| Masalah Diagnostik           | Penyebab Utama              | Solusi Definitif     |
|------------------------------+-----------------------------+----------------------|
| Hitch Rate Tinggi saat Scroll| .id(UUID()) pada sel list   | Gunakan Persistent   |
|                              |                             | Stable Identity      |
|                              |                             |                      |
| CPU Spike saat Data Masuk    | Over-invalidation           | Gunakan @Observable  |
|                              | ObservableObject Combine    | Swift 5.9+ / Leaf Sub|
|                              |                             |                      |
| View Berkedip / Animasi Putus| Kerusakan Identitas         | Hindari percabangan  |
|                              | Struktural via if-else      | if-else pada view    |
|                              |                             | yang sama (gunakan   |
|                              |                             | modifier dinamis)    |
|                              |                             |                      |
| Evaluasi Body Berulang       | AnyView di mana-mana        | Gunakan @ViewBuilder |
|                              |                             | atau Generics        |
|                              |                             |                      |
| UI Macet (Freezing)          | Heavy sorting di `body`     | Geser komputasi ke   |
|                              |                             | Background Worker /  |
|                              |                             | ViewModel Task       |
+-----------------------------------------------------------------------------------+
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Pilihlah satu jawaban yang paling tepat untuk setiap pertanyaan di bawah ini.

### Soal Basic (1–5)

#### 1. Kapan blok evaluasi `body` dari suatu View SwiftUI dieksekusi?
A. Setiap 16 milidetik secara konstan tanpa memperhatikan state.  
B. Hanya ketika instans struct dari View tersebut pertama kali dialokasikan di call stack.  
C. Ketika simpul terkait pada `AttributeGraph` ditandai sebagai *dirty* akibat perubahan dependensi state.  
D. Hanya saat pengguna menyentuh layar perangkat.  
*Jawaban:* **C**. SwiftUI menggunakan *dependency-driven execution*; `body` hanya dipanggil jika simpul graf dependensinya berubah.

#### 2. Apa dampak memanggil `Self._printChanges()` di dalam blok `body`?
A. Mematikan sistem layout CoreAnimation.  
B. Mengeluarkan log ke konsol debugger mengenai properti yang menyebabkan view tersebut dievaluasi ulang.  
C. Memaksa view untuk menghapus memori cache lokal dan mereset identitasnya.  
D. Menghasilkan compile-time error jika kode dijalankan di environment Release.  
*Jawaban:* **B**. Fungsi diagnostik ini mencetak identifikasi perubahan state (misalnya perubahan nama variabel atau dependency) yang memicu pemanggilan `body`.

#### 3. Mengapa penggunaan `.id(UUID())` pada baris di dalam `List` dianggap sebagai antipattern performa?
A. Menghabiskan alokasi UUID pada kernel sistem operasi.  
B. Menghancurkan *explicit identity* pada setiap render, membatalkan animasi, dan memaksa alokasi ulang penuh dari elemen view.  
C. Mengubah tipe List menjadi ScrollView secara implisit.  
D. Memicu memori leak pada framework Combine.  
*Jawaban:* **B**. Pemberian UUID baru pada setiap pass render menghancurkan kontinuitas identitas tampilan, mereset state, dan memaksa rekonstruksi dari nol.

#### 4. Apa perbedaan mendasar antara macro `@Observable` (iOS 17+) dan protokol `ObservableObject`?
A. `@Observable` berjalan di background thread secara default, sedangkan `ObservableObject` di main thread.  
B. `@Observable` melacak dependensi hingga tingkat properti individu (*field-level*), sedangkan `ObservableObject` memicu invalidasi level objek secara keseluruhan.  
C. `ObservableObject` tidak mendukung struktur data class.  
D. `@Observable` mewajibkan penggunaan Combine framework.  
*Jawaban:* **B**. Macro `@Observable` membagi observabilitas per-field sehingga hanya view yang membaca field spesifik yang akan di-render ulang jika nilai tersebut berubah.

#### 5. Apa yang dimaksud dengan "Hitch" dalam performa antarmuka iOS?
A. Kondisi di mana alokasi memori heap melampaui 1 GB.  
B. Frame yang terlambat diserahkan ke sistem tampilan (*dropped/delayed frame*), mengakibatkan stuttering visual saat animasi/scrolling.  
C. Error kompilasi akibat recursive macro expansion.  
D. Kegagalan autentikasi background task ke main runloop.  
*Jawaban:* **B**. *Hitch* adalah kondisi fisik di mana frame visual tidak siap ditampilkan pada siklus VSYNC yang ditentukan.

---

### Soal Intermediate (6–10)

#### 6. Mengapa penggunaan `AnyView` dapat berdampak buruk pada performa hirarki tampilan yang dinamis?
A. `AnyView` memotong alokasi memori heap dan memaksanya ke stack.  
B. `AnyView` menghapus informasi tipe konkret, mencegah compiler mengoptimasi struktur pohon diffing dan memaksa perusakan/pembuatan ulang simpul AttributeGraph.  
C. Menggunakan `AnyView` secara otomatis mengaktifkan offscreen rendering pada CoreAnimation.  
D. `AnyView` memblokir pengiriman transaksi animasi secara permanen.  
*Jawaban:* **B**. Type erasure menyembunyikan identitas struktural statis dari SwiftUI engine, memaksa penghancuran dan pembuatan ulang node tree alih-alih melakukan diffing cerdas.

#### 7. Perhatikan kode berikut:
```swift
struct DataContainerView: View {
    @StateObject var dataStore = HeavyDataStore()
    var body: some View {
        ItemListingView(items: dataStore.filteredItems)
    }
}
```
#### Jika `HeavyDataStore` sering memperbarui properti lain yang *tidak dibaca* oleh `DataContainerView`, apa akibatnya?
A. Tidak ada dampak performa karena SwiftUI mendeteksi subview secara otomatis.  
B. `DataContainerView` akan terus-menerus mere-evaluasi `body`, mengevaluasi ulang `dataStore.filteredItems`, dan menginstansiasi ulang `ItemListingView`.  
C. Aplikasi akan melempar fatal exception `AttributeGraph: Cycle Detected`.  
D. Properti `filteredItems` akan otomatis dicache oleh sistem operasi.  
*Jawaban:* **B**. Karena `@StateObject` (berbasis `ObservableObject`) bekerja pada level *instance invalidation*, perubahan apa pun pada model akan mere-evaluasi `DataContainerView.body`, memicu komputasi `filteredItems` berulang kali.

#### 8. Apa fungsi utama dari modifier `.drawingGroup()` dalam rekayasa antarmuka SwiftUI?
A. Memindahkan rendering subview dari CALayer terpisah ke satu konteks grafis Metal berbasis raster texture.  
B. Menghapus batasan FPS pada layar ProMotion.  
C. Mengompresi resolusi teks secara dinamis untuk menghemat bandwidth memori.  
D. Memaksa pemrosesan layout berjalan di atas thread paralel non-UI.  
*Jawaban:* **A**. `.drawingGroup()` meratakan (*flattens*) hirarki subview ke dalam satu buffer gambar Metal langsung, memangkas beban kerja kompositor CoreAnimation pada antarmuka grafis yang padat.

#### 9. Apa kelemahan utama dari isolasi performa menggunakan protokol `Equatable` manual pada View struct?
A. View tidak lagi dapat menerima event sentuhan atau navigasi.  
B. Developer memikul tanggung jawab penuh; jika perbandingan `==` mengabaikan properti yang berdampak visual, tampilan tidak akan diperbarui (*stale UI bug*).  
C. Menghilangkan kompatibilitas dengan modifier `.animation()`.  
D. Menurunkan efisiensi konsumsi baterai hingga 50%.  
*Jawaban:* **B**. Logika `Equatable` yang keliru atau mengabaikan properti penting akan mengelabui mesin diffing SwiftUI, menyebabkan antarmuka tidak merespons mutasi data aktual (*false negative update*).

#### 10. Dalam instrumen *SwiftUI View Hierarchy*, metrik apa yang paling krusial untuk menemukan kebocoran komputasi render?
A. Heap Allocation size pada blok static binary.  
B. Rasio perbandingan antara "Body Evaluation Count" terhadap jumlah aktual event mutasi input/state.  
C. Jumlah total file Swift dalam build pipeline.  
D. Persentase penggunaan GPU instruction pipeline pada mode standby.  
*Jawaban:* **B**. Rasio evaluasi `body` yang tinggi terhadap mutasi input yang rendah secara akurat menunjukkan adanya propagasi invalidasi yang bocor (*over-invalidation leak*).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Deskripsi Masalah Proyek
Anda ditugaskan untuk memperbaiki modul **"Real-Time Telemetry Matrix"** pada aplikasi pemantauan drone enterprise. Modul saat ini mengalami *frame drop* parah (Hitch Rate $\approx 28.5\text{ ms/s}$) dan konsumsi CPU tinggi saat menerima data sensor IMU via background stream berkecepatan 100 Hz.

### Spesifikasi Kode Bermasalah (Starter Code):
```swift
import SwiftUI

class DroneIMUManager: ObservableObject {
    @Published var pitch: Double = 0.0
    @Published var roll: Double = 0.0
    @Published var yaw: Double = 0.0
    @Published var altitude: Double = 100.0
    @Published var batteryLevel: Double = 98.0
    @Published var logs: [String] = []
    
    // Dipanggil dari thread jaringan 100 kali per detik
    func simulateSensorTick() {
        pitch = Double.random(in: -45...45)
        roll = Double.random(in: -45...45)
        yaw = Double.random(in: 0...360)
        altitude += Double.random(in: -0.5...0.5)
        batteryLevel -= 0.001
        logs.append("Tick: \(Date().timeIntervalSince1970)")
    }
}

struct DroneMonitorRootView: View {
    @ObservedObject var manager: DroneIMUManager

    var body: some View {
        VStack {
            Text("Drone Telemetry HUD")
                .font(.largeTitle)
            
            // Artificial delay simulating heavy UI drawing
            ZStack {
                Circle()
                    .stroke(Color.blue, lineWidth: 4)
                Text("Pitch: \(manager.pitch, specifier: "%.1f")")
            }
            .frame(width: 150, height: 150)
            .id(UUID()) // Pitfall 1
            
            VStack {
                Text("Altitude: \(manager.altitude, specifier: "%.2f") m")
                Text("Battery: \(manager.batteryLevel, specifier: "%.1f")%")
            }
            
            // Pitfall 2: List rendering array yang terus bertambah tanpa virtualisasi stabil
            List(manager.logs.suffix(20), id: \.self) { log in
                Text(log)
            }
        }
    }
}
```

### Instruksi Tugas Perbaikan:
1. **Migrasi Paradigma Observasi**:
   * Ubah model data dari `ObservableObject` menjadi arsitektur `@Observable` (iOS 17+).
2. **Buffer & Coalesce Data Input**:
   * Implementasikan mekanika *rate limiting* atau *coalescing* menggunakan Swift Concurrency Actor untuk membatasi commit antarmuka maksimal pada frekuensi layar 60 Hz / 120 Hz, meskipun background data masuk pada 100 Hz+.
3. **Struktur Ulang Hirarki Pohon Tampilan**:
   * Pecah `DroneMonitorRootView` menjadi subview atomik terisolasi: `PitchIndicatorView`, `FlightStatusView`, dan `TelemetryLogView`.
   * Pastikan pembaruan pada `pitch` **tidak memicu** re-evaluasi pada `FlightStatusView` atau `Text("Drone Telemetry HUD")`.
4. **Hapus Kesalahan Fatal Identitas**:
   * Singkirkan modifikasi `.id(UUID())`.
   * Buat struktur data model yang stabil untuk baris `logs` menggunakan identitas deterministik (bukan string murni sebagai ID).
5. **Validasi Kriteria Keberhasilan**:
   * Jalankan instrumen `Self._printChanges()` pada setiap subview baru; buktikan bahwa view `FlightStatusView` tidak mencetak log ketika hanya `pitch` yang berubah.
   * Uji performa di Xcode Time Profiler untuk memastikan waktu komputasi frame aplikasi tetap berada di bawah **4 milidetik** secara konsisten.