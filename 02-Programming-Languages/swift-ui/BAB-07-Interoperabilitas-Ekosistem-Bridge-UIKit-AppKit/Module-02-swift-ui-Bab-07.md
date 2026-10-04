# BAB 07: Interoperabilitas Ekosistem Bridge (UIKit & AppKit)
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menguasai arsitektur internal siklus hidup (lifecycle) representable bridge: `UIViewRepresentable`, `UIViewControllerRepresentable`, `NSViewRepresentable`, dan `NSViewControllerRepresentable`.
- Mengimplementasikan sinkronisasi status dua arah (bidirectional data binding) bebas *memory leak* dan *retain cycle* antara paradigma deklaratif SwiftUI dan paradigma imperatif UIKit/AppKit.
- Melakukan arbitrase tata letak (*layout negotiation*) tingkat lanjut antara mesin Auto Layout UIKit (`systemLayoutSizeFitting`, Intrinsic Content Size) dan sistem *layout proposed size* SwiftUI.
- Mengintegrasikan manajemen gesture imperatif tingkat lanjut (`UIGestureRecognizerDelegate`, simultaneous gestures) yang beroperasi harmonis dengan *gesture graph* SwiftUI.
- Mengimplementasikan `UIHostingController` dan `NSHostingController` berkinerja tinggi di dalam container imperatif warisan (*legacy*) seperti `UICollectionViewCompositionalLayout`.
- Mengisolasi, mendiagnosis, dan menyelesaikan degradasi performa render, *redundant passes*, dan masalah *thread safety* pada konkurensi Swift modern (`@MainActor`).

---

### 2. Prerequisite
Untuk menyerap materi ini secara maksimal, Anda wajib memahami:
- **Swift Concurrency**: Penggunaan `@MainActor`, `Sendable`, dan penanganan *asynchronous task*.
- **Auto Layout Essentials**: *Constraint priorities*, *content hugging*, *compression resistance*, dan komputasi ukuran intrinsik imperatif.
- **SwiftUI Core**: Siklus hidup *view graph*, sistem dependensi status (`@Binding`, `@StateObject`, `@Observable`), serta fase *Layout*, *Update*, dan *Render*.
- **UIKit/AppKit Fundamentals**: Delegasi target-action, responder chain, dan hirarki subview.

---

### 3. Concept & Internal Architecture (Mendalam)

Interoperabilitas antara SwiftUI dan UIKit/AppKit bukanlah sekadar *wrapper* tipis, melainkan sebuah jembatan kompleks yang menghubungkan dua paradigma komputasi UI yang berbeda:

1. **Paradigma Komputasi UI**:
   - **SwiftUI**: Fungsional deklaratif murni. View adalah struktur data (`struct`) yang ringan, merepresentasikan deskripsi visual yang terus-menerus dibuat ulang (*ephemeral*) saat *state graph* bermutasi.
   - **UIKit/AppKit**: *Stateful object graph* berbasis referensi (`class`). View (`UIView`/`NSView`) adalah objek berumur panjang (*long-lived*) yang mempertahankan statusnya secara internal di heap memory.

```
+-----------------------------------------------------------------------+
|                           SWIFTUI ENGINE                              |
|                                                                       |
|  [State Change] ---> [Evaluate View Tree] ---> [Diffing Engine]       |
|                                                        |              |
+--------------------------------------------------------|---------------+
                                                         | 
                                                         v
                                  +------------------------------+
                                  |  Representable Bridge Host   |
                                  |  (_UIHostingView / Bridge)   |
                                  +------------------------------+
                                                 |
             +-----------------------------------+-----------------------------------+
             |                                                                       |
             v                                                                       v
   (Initial Mount Only)                                                     (On State Mutation)
+----------------------------+                                           +----------------------------+
|   makeCoordinator()        |                                           |   updateUIView(...)        |
|            |               |                                           |            |               |
|            v               |                                           |            v               |
|   makeUIView(context:)     |                                           | Synchronize props to UIKit |
+----------------------------+                                           +----------------------------+
             |                                                                       |
             +-----------------------------------+-----------------------------------+
                                                 |
                                                 v
                                  +------------------------------+
                                  |     Layout Arbitration       |
                                  |    sizeThatFits(_:uiView:)   |
                                  |              vs              |
                                  |   systemLayoutSizeFitting    |
                                  +------------------------------+
                                                 |
                                                 v
                                  +------------------------------+
                                  |       UIKit Rendering        |
                                  |   (CoreAnimation / Render)   |
                                  +------------------------------+
```

#### Komponen Internal Representable Engine

- **`Coordinator` Lifecycle**: 
  Objek koordinator diinisialisasi pertama kali melalui `makeCoordinator()`. Objek ini dialokasikan di heap dan dipertahankan sepanjang masa hidup *view tree node* representable terkait. Koordinator berperan sebagai *trampoline* delegasi imperatif (seperti `UIScrollViewDelegate`, `MKMapViewDelegate`) yang menerjemahkan callback imperatif menjadi mutasi status pada SwiftUI.
- **Mounting Sequence**:
  1. SwiftUI mengevaluasi body representable.
  2. `makeCoordinator()` dipanggil dan ditautkan ke internal host context.
  3. `makeUIView(context:)` (atau `makeUIViewController`) dipanggil tepat sekali untuk instansiasi.
  4. SwiftUI segera memanggil `updateUIView(_:context:)` sebelum view ditempatkan ke layar.
- **Update Loop & Diffing Hazard**:
  Setiap kali dependensi status yang dibaca oleh representable berubah, SwiftUI menjadwalkan eksekusi `updateUIView(_:context:)`. Jika pengembang memicu perubahan `@Binding` secara naif di dalam `updateUIView`, hal ini dapat memicu *infinite update cycle* yang berujung pada *crash* alokasi stack atau *freezing* CPU 100%.
- **Layout Arbitration**:
  SwiftUI bekerja menggunakan prinsip: *Parent Proposes Size -> Child Chooses Size -> Parent Positions Child*. UIKit sebaliknya, menggunakan Auto Layout berbasis constraint solver (Cassowary Algorithm). Jembatan ini mengimplementasikan metode `sizeThatFits(_:uiView:context:)` pada protokol representable untuk bernegosiasi antara ukuran yang diajukan oleh SwiftUI (`ProposedViewSize`) dengan kapasitas ekspansi imperatif UIKit (`systemLayoutSizeFitting`).

---

### 4. Why & What
- **Why**: 
  Meskipun SwiftUI terus berkembang, banyak fondasi sistem tingkat rendah (seperti `AVPlayerLayer`, `MKMapView` dengan clustering kompleks, `UITextView` dengan *custom text storage layout manager*, atau SDK pihak ketiga berbasis C++/Obj-C) hanya menyediakan interface Cocoa/UIKit. Memaksa reimplementasi langsung di SwiftUI sering kali tidak efisien atau bahkan mustahil.
- **What**: 
  Infrastruktur interoperabilitas tingkat lanjut adalah metodologi rekayasa untuk mengintegrasikan subsistem imperatif ke dalam sistem deklaratif SwiftUI secara aman, deterministik, dan berperforma tinggi tanpa mengorbankan siklus render sistem secara keseluruhan.

---

### 5. How (Workflow Detail)

Alur kerja arsitektural yang deterministik untuk membangun jembatan UIKit-to-SwiftUI kelas produksi mencakup langkah-langkah berikut:

```
[Start Layout/State Phase]
           |
           v
+-----------------------------------------------------------+
| 1. Evaluasi Perubahan Status (SwiftUI State Mutation)     |
+-----------------------------------------------------------+
           |
           v
+-----------------------------------------------------------+
| 2. Panggil updateUIView(uiView, context)                 |
|    - Bandingkan status baru dengan status eksisting view |
|    - Mutasi HANYA properti yang berubah (No Over-commit) |
+-----------------------------------------------------------+
           |
           v
+-----------------------------------------------------------+
| 3. Arbitrase Ukuran (Layout Negotiation)                  |
|    - sizeThatFits(proposal, uiView, context)              |
|    - Konversi ProposedViewSize -> CGSize                  |
|    - Jalankan systemLayoutSizeFitting jika Auto Layout     |
+-----------------------------------------------------------+
           |
           v
+-----------------------------------------------------------+
| 4. User Interaction (UIKit Event via Target-Action/Delegate)
+-----------------------------------------------------------+
           |
           v
+-----------------------------------------------------------+
| 5. Koordinator Mencegat Event                             |
|    - Nonaktifkan flag siklus update                       |
|    - Mutasi @Binding di SwiftUI via MainActor             |
+-----------------------------------------------------------+
           |
           v
[Selesai - Graph Tetap Sinkron]
```

---

### 6. Analogy & Diagram ASCII

Bayangkan dua entitas: **Birokrasi Sipil Tradisional (UIKit)** dan **Dewan Kontemporer Berbasis AI (SwiftUI)**. 
- UIKit bekerja menggunakan berkas fisik permanen (`UIView`), yang harus diisi dan dirawat oleh pegawai yang sama secara berkelanjutan.
- SwiftUI bekerja seperti dewan pengawas yang mengamati dunia dari atas, mencetak lembar instruksi baru setiap ada perubahan data, dan membuang lembaran lama.

Jika Dewan (SwiftUI) ingin mengendalikan kantor arsip (UIKit), mereka tidak bisa berbicara langsung. Mereka mengangkat seorang **Diplomat Tetap (`Coordinator`)**.

```
    SWIFTUI (DEWAN PENGAWAS)                        UIKIT (KANTOR ARSIP)
+-------------------------------+              +-------------------------------+
| - Mengirim Instruksi Baru     |              | - Objek Fisik Persisten       |
|   (updateUIView)              |              | - Auto Layout Constraints     |
| - Membaca Feedback Dinamis    |              | - Interaksi Delegate/Target   |
+-------------------------------+              +-------------------------------+
                ^                                              ^
                |                                              |
                +-----------------------\ /--------------------+
                                         X
                                        / \
                        +--------------------------------+
                        |     COORDINATOR (DIPLOMAT)     |
                        |                                |
                        | 1. Memegang referensi Binding  |
                        | 2. Menampung Delegate UIKit    |
                        | 3. Mencegah Infinite Loop      |
                        | 4. Menangani Memory Teardown   |
                        +--------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Auto-sizing Native Rich Text Viewer
Contoh implementasi dasar `UIViewRepresentable` yang membungkus `UITextView` dengan arbitrase ukuran yang benar (tidak collapse menjadi nol dan tidak memicu layout loop).

```swift
import SwiftUI
import UIKit

public struct NativeRichTextView: UIViewRepresentable {
    public let attributedText: NSAttributedString
    @Binding public var dynamicHeight: CGFloat

    public init(attributedText: NSAttributedString, dynamicHeight: Binding<CGFloat>) {
        self.attributedText = attributedText
        self._dynamicHeight = dynamicHeight
    }

    public func makeUIView(context: Context) -> UITextView {
        let textView = UITextView()
        textView.isEditable = false
        textView.isScrollEnabled = false
        textView.backgroundColor = .clear
        textView.textContainerInset = .zero
        textView.textContainer.lineFragmentPadding = 0
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        textView.setContentHuggingPriority(.required, for: .vertical)
        return textView
    }

    public func updateUIView(_ uiView: UITextView, context: Context) {
        if uiView.attributedText != attributedText {
            uiView.attributedText = attributedText
        }
        
        DispatchQueue.main.async {
            let targetSize = CGSize(width: uiView.bounds.width, height: CGFloat.greatestFiniteMagnitude)
            let calculatedSize = uiView.sizeThatFits(targetSize)
            if self.dynamicHeight != calculatedSize.height && calculatedSize.height > 0 {
                self.dynamicHeight = calculatedSize.height
            }
        }
    }

    public func sizeThatFits(_ proposal: ProposedViewSize, uiView: UITextView, context: Context) -> CGSize? {
        let targetWidth = proposal.width ?? UIScreen.main.bounds.width
        let size = uiView.sizeThatFits(CGSize(width: targetWidth, height: .greatestFiniteMagnitude))
        return CGSize(width: targetWidth, height: size.height)
    }
}
```

#### B. Practical Example: Production Camera Scanner Viewport
Komponen produksi tingkat lanjut yang membungkus `AVCaptureSession` dengan `Coordinator`, `AVCaptureVideoDataOutputSampleBufferDelegate`, handling status dua arah, dan manajemen siklus hidup thread-safe.

```swift
import SwiftUI
import AVFoundation

public struct CameraBarcodeScannerView: UIViewControllerRepresentable {
    @Binding public var isTorchOn: Bool
    @Binding public var lastScannedCode: String?
    public var onScanFailure: (Error) -> Void

    public init(
        isTorchOn: Binding<Bool>,
        lastScannedCode: Binding<String?>,
        onScanFailure: @escaping (Error) -> Void
    ) {
        self._isTorchOn = isTorchOn
        self._lastScannedCode = lastScannedCode
        self.onScanFailure = onScanFailure
    }

    public func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    public func makeUIViewController(context: Context) -> ScannerViewController {
        let controller = ScannerViewController()
        controller.delegate = context.coordinator
        return controller
    }

    public func updateUIViewController(_ uiViewController: ScannerViewController, context: Context) {
        uiViewController.setTorch(enabled: isTorchOn)
    }

    public static func dismantleUIViewController(_ uiViewController: ScannerViewController, coordinator: Coordinator) {
        uiViewController.stopSession()
    }

    // MARK: - Coordinator
    public final class Coordinator: NSObject, ScannerViewControllerDelegate {
        private var parent: CameraBarcodeScannerView

        init(parent: CameraBarcodeScannerView) {
            self.parent = parent
        }

        @MainActor
        public func didCapture(code: String) {
            // Mencegah duplicate emissions yang tidak perlu
            guard self.parent.lastScannedCode != code else { return }
            self.parent.lastScannedCode = code
        }

        @MainActor
        public func didFail(error: Error) {
            self.parent.onScanFailure(error)
        }
    }
}

// MARK: - Delegate Protocol
public protocol ScannerViewControllerDelegate: AnyObject {
    func didCapture(code: String)
    func didFail(error: Error)
}

// MARK: - Underlying Imperative UIViewController
public final class ScannerViewController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    public weak var delegate: ScannerViewControllerDelegate?
    private let captureSession = AVCaptureSession()
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private let sessionQueue = DispatchQueue(label: "com.enterprise.camera.sessionQueue")

    public override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        setupSession()
    }

    public override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.bounds
    }

    private func setupSession() {
        sessionQueue.async { [weak self] in
            guard let self = self else { return }
            self.captureSession.beginConfiguration()
            self.captureSession.sessionPreset = .high

            guard let videoCaptureDevice = AVCaptureDevice.default(for: .video),
                  let videoInput = try? AVCaptureDeviceInput(device: videoCaptureDevice),
                  self.captureSession.canAddInput(videoInput) else {
                self.captureSession.commitConfiguration()
                DispatchQueue.main.async {
                    self.delegate?.didFail(error: NSError(domain: "CameraScanner", code: -1, userInfo: [NSLocalizedDescriptionKey: "Input hardware failure"]))
                }
                return
            }

            self.captureSession.addInput(videoInput)

            let metadataOutput = AVCaptureMetadataOutput()
            if self.captureSession.canAddOutput(metadataOutput) {
                self.captureSession.addOutput(metadataOutput)
                metadataOutput.setMetadataObjectsDelegate(self, queue: DispatchQueue.main)
                metadataOutput.metadataObjectTypes = [.qr, .ean13, .code128]
            } else {
                self.captureSession.commitConfiguration()
                DispatchQueue.main.async {
                    self.delegate?.didFail(error: NSError(domain: "CameraScanner", code: -2, userInfo: [NSLocalizedDescriptionKey: "Output pipeline failure"]))
                }
                return
            }

            self.captureSession.commitConfiguration()
            self.captureSession.startRunning()

            DispatchQueue.main.async {
                let preview = AVCaptureVideoPreviewLayer(session: self.captureSession)
                preview.videoGravity = .resizeAspectFill
                preview.frame = self.view.bounds
                self.view.layer.addSublayer(preview)
                self.previewLayer = preview
            }
        }
    }

    public func setTorch(enabled: Bool) {
        sessionQueue.async {
            guard let device = AVCaptureDevice.default(for: .video), device.hasTorch else { return }
            do {
                try device.lockForConfiguration()
                device.torchMode = enabled ? .on : .off
                device.unlockForConfiguration()
            } catch {
                // Torch failure handling
            }
        }
    }

    public func stopSession() {
        sessionQueue.async { [weak self] in
            guard let self = self, self.captureSession.isRunning else { return }
            self.captureSession.stopRunning()
        }
    }

    public func metadataOutput(
        _ output: AVCaptureMetadataOutput,
        didOutput metadataObjects: [AVMetadataObject],
        from connection: AVCaptureConnection
    ) {
        guard let metadataObject = metadataObjects.first,
              let readableObject = metadataObject as? AVMetadataMachineReadableCodeObject,
              let stringValue = readableObject.stringValue else {
            return
        }
        delegate?.didCapture(code: stringValue)
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Integrasi High-Performance Map Engine SDK (C++ / UIKit Wrapper) pada Aplikasi Logistik Enterprise
Sebuah aplikasi armada logistik multinasional dengan 200.000 *courier active daily sessions* bermigrasi ke SwiftUI. Namun, mesin peta utama adalah SDK UIKit tertutup (*proprietary*) yang memproses puluhan mutasi marker koordinat GPS per detik via socket UDP.

#### Permasalahan Skalabilitas & Performa
- **State Churning**: Setiap pembaruan posisi kurir memicu mutasi `@State` di SwiftUI, yang menyebabkan `updateUIView` dieksekusi 60 kali per detik. Ini memicu penghitungan ulang layout tree SwiftUI dan menyebabkan *frame drops* (FPS jatuh ke <25 FPS).
- **Coordinate Space Collision**: Gestur panning dan zoom pada SDK peta bentrok dengan `DragGesture` dari sheet interaktif SwiftUI.
- **Memory Leaks**: `MKMapView`/Custom Map Engine menahan referensi delegate yang tidak dibersihkan saat navigasi SwiftUI melakukan *pop* secara dinamis.

#### Solusi Arsitektur
1. **Throttled Binding & DisplayLink Layer**:
   Menerapkan peredam (*decoupling*) pada frekuensi data binding. Komunikasi real-time dialihkan langsung dari layer transport ke `Coordinator` via AsyncStream, menghindari siklus render SwiftUI body.
2. **Gesture Resolver Interceptor**:
   Membuat subclass `UIView` kustom yang menimpa `hitTest(_:with:)` untuk menentukan kontrol alur responder chain ke UIKit atau SwiftUI.
3. **Explicit Teardown Lifecycle Hook**:
   Memanfaatkan implementasi eksplisit `dismantleUIView` untuk memutus listener delegate, menghentikan texture rendering CADisplayLink, dan membersihkan node memori UIKit secara manual.

```swift
// Implementasi Arsitektural Isolasi Re-render Berlebih
public struct EnterpriseMapViewBridge: UIViewRepresentable {
    public let routeId: String
    @Binding public var cameraPitch: Double

    public func makeCoordinator() -> Coordinator {
        Coordinator(routeId: routeId)
    }

    public func makeUIView(context: Context) -> HighThroughputMapView {
        let mapView = HighThroughputMapView()
        mapView.delegate = context.coordinator
        context.coordinator.attachEngine(mapView)
        return mapView
    }

    public func updateUIView(_ uiView: HighThroughputMapView, context: Context) {
        // HANYA update properti jika ada delta signifikan secara terukur
        if abs(uiView.currentPitch - cameraPitch) > 0.01 {
            uiView.updatePitch(cameraPitch)
        }
    }

    public static func dismantleUIView(_ uiView: HighThroughputMapView, coordinator: Coordinator) {
        coordinator.detachEngine()
        uiView.destroyContext()
    }

    public final class Coordinator: NSObject, HighThroughputMapDelegate {
        private var routeId: String
        private weak var engine: HighThroughputMapView?
        private var telemetryTask: Task<Void, Never>?

        init(routeId: String) {
            self.routeId = routeId
            super.init()
            startTelemetrySubscription()
        }

        func attachEngine(_ engine: HighThroughputMapView) {
            self.engine = engine
        }

        func detachEngine() {
            telemetryTask?.cancel()
            telemetryTask = nil
            engine?.delegate = nil
            engine = nil
        }

        private func startTelemetrySubscription() {
            // Bypass SwiftUI body invalidation loop for 60Hz telemetry
            telemetryTask = Task { [weak self] in
                guard let stream = TelemetrySocketClient.shared.stream(for: self?.routeId ?? "") else { return }
                for await coordinate in stream {
                    guard !Task.isCancelled else { break }
                    await MainActor.run {
                        self?.engine?.renderMarkerPositionDirect(coordinate)
                    }
                }
            }
        }

        public func mapDidFinishRenderingFrame() {
            // No-op atau telemetry internal
        }
    }
}

public protocol HighThroughputMapDelegate: AnyObject {
    func mapDidFinishRenderingFrame()
}

public final class HighThroughputMapView: UIView {
    public weak var delegate: HighThroughputMapDelegate?
    public private(set) var currentPitch: Double = 0.0

    public func updatePitch(_ pitch: Double) {
        self.currentPitch = pitch
        // Kirim update ke layer CoreGraphics/OpenGL/Metal internal
    }

    public func renderMarkerPositionDirect(_ coord: CGPoint) {
        // Direct memory injection to Metal pipeline, zero SwiftUI overhead
    }

    public func destroyContext() {
        // Invalidate render timers, cleanup Metal command buffers
    }
}

public final class TelemetrySocketClient {
    public static let shared = TelemetrySocketClient()
    public func stream(for routeId: String) -> AsyncStream<CGPoint>? {
        return AsyncStream { continuation in
            // Mock connection telemetry
            continuation.onTermination = { _ in }
        }
    }
}
```

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Representable Direct Bridge | UIHostingController in UIKit Cell | Pure Native SwiftUI Rewrite |
| :--- | :--- | :--- | :--- |
| **Render Latency** | **Rendah (0.5 - 2ms)**. Langsung mengeksekusi view pipeline CoreAnimation tanpa overhead hosting ekstra. | **Sedang ke Tinggi (4 - 12ms)**. Terdapat alokasi overhead deklaratif di dalam setiap cell imperatif. | **Sangat Rendah (0.1 - 1ms)**. Bebas komputasi bridging dan negosiasi sizing antarmuka. |
| **Memory Footprint** | Rendah. Mempertahankan objek yang sama secara deterministik. | Tinggi. Alokasi ganda (`UICollectionViewCell` + `UIHostingController` + SwiftUI State Graph node). | Sangat Hemat. Tidak ada overhead runtime subclass UIKit atau bridging context. |
| **Engineering Cost** | **Tinggi**. Membutuhkan pemahaman mendalam tentang dua paradigma, constraint solver, dan gesture chain. | **Sedang**. Cepat digunakan saat migrasi modular dari UIKit lama. | **Sangat Tinggi**. Menulis ulang SDK/logika kompleks dari awal di SwiftUI membutuhkan investasi waktu besar. |
| **Scalability** | Bagus. Cocok untuk komponen individual berkategori *heavy-duty* (Map, Camera, Canvas). | Buruk jika dipakai di infinite list bertempo cepat tanpa implementasi pooling view yang agresif. | Optimal untuk arsitektur UI modern di ekosistem Apple. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Menembakkan Mutasi State SwiftUI Langsung di `updateUIView`
*Penyebab*: Merubah `@Binding` atau `@State` di dalam `updateUIView` memicu evaluasi ulang `body` SwiftUI, yang kemudian kembali memanggil `updateUIView`.
*Gejala*: *Looping* CPU 100%, UI macet (*freeze*), dan konsol dipenuhi pesan: `Modifying state during view update, this will cause undefined behavior.`
*Solusi*: Gunakan perbandingan nilai sebelum mengirim perubahan, atau tempatkan mutasi state hanya di dalam callback delegasi `Coordinator` yang dipicu oleh input pengguna/event eksternal.

```swift
// SALAH
func updateUIView(_ uiView: UISlider, context: Context) {
    uiView.value = value
    self.value = uiView.value // CRASH/LOOP
}

// BENAR
func updateUIView(_ uiView: UISlider, context: Context) {
    if uiView.value != value {
        uiView.value = value
    }
}
```

#### Kesalahan 2: Retain Cycles pada Coordinator via Strong Self
*Penyebab*: Objek UIKit (misalnya `CADisplayLink`, `Timer`, atau completion closure) menangkap `Coordinator` secara kuat (*strong reference*), sementara `Coordinator` memegang target UIKit tersebut tanpa pembatalan saat unmount.
*Gejala*: Memori terus meningkat (*leak*) saat membuka-tutup layar representable.
*Solusi*: Implementasikan fungsi statis `dismantleUIView(_:coordinator:)` atau `dismantleUIViewController(_:coordinator:)` untuk membatalkan semua langganan dan melepaskan referensi.

```swift
// BENAR
public static func dismantleUIView(_ uiView: CustomChartView, coordinator: Coordinator) {
    coordinator.cleanup()
}
```

#### Kesalahan 3: Auto Layout Broken Sizing (View Mengecil Menjadi 0x0)
*Penyebab*: Subview UIKit menggunakan `translatesAutoresizingMaskIntoConstraints = false`, tetapi representable tidak mengimplementasikan `sizeThatFits(_:uiView:context:)` atau constraint gagal menyelesaikan ukuran horizontal/vertikal intrinsik.
*Gejala*: View UIKit tidak terlihat di layar, atau console menampilkan log: `Unable to simultaneously satisfy constraints`.
*Solusi*: Implementasikan `sizeThatFits` secara eksplisit atau berikan modifier `.frame(minWidth:..., minHeight:...)` pada SwiftUI tree host.

---

### 11. Best Practices (Production Checklist)

- [ ] **Coordinator Independence**: Pastikan `Coordinator` bersifat `final class` dan mengisolasi interaksi UI di `@MainActor`.
- [ ] **No-Op Update Guards**: Selalu bandingkan properti lama vs properti baru di `updateUIView` sebelum menerapkan perubahan pada objek UIKit.
- [ ] **Explicit Layout Sizing**: Implementasikan `func sizeThatFits(_ proposal: ProposedViewSize, uiView: UIViewType, context: Context) -> CGSize?` untuk kontrol ukuran yang deterministik.
- [ ] **Dismantle Cleanliness**: Implementasikan `dismantleUIView` / `dismantleUIViewController` untuk membersihkan observer KVO, notification center, timer, atau delegasi perangkat keras.
- [ ] **Hosting Inset Optimization**: Saat menggunakan `UIHostingController`, matikan *safe area margin* yang tidak diinginkan dengan `hostingController.safeAreaRegions = []` atau `.ignoresSafeArea()`.
- [ ] **Thread Concurrency Guard**: Jangan pernah mengeksekusi inisialisasi view UIKit di thread sekunder. Jembatan representable harus selalu berjalan di *Main Thread*.

---

### 12. Hands-on Practice

Buatlah implementasi bridge interaktif dua arah antara UIKit `UIScrollView` dengan zoom scale handling kustom dan antarmuka SwiftUI. 
Struktur repositori target: `hands-on/m02/`

#### File: `hands-on/m02/ZoomableScrollContainer.swift`

```swift
import SwiftUI
import UIKit

public struct ZoomableScrollContainer<Content: View>: UIViewRepresentable {
    private let content: Content
    private let maxScale: CGFloat
    private let minScale: CGFloat
    @Binding private var currentScale: CGFloat

    public init(
        maxScale: CGFloat = 4.0,
        minScale: CGFloat = 1.0,
        currentScale: Binding<CGFloat>,
        @ViewBuilder content: () -> Content
    ) {
        self.maxScale = maxScale
        self.minScale = minScale
        self._currentScale = currentScale
        self.content = content()
    }

    public func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    public func makeUIView(context: Context) -> UIScrollView {
        let scrollView = UIScrollView()
        scrollView.showsVerticalScrollIndicator = false
        scrollView.showsHorizontalScrollIndicator = false
        scrollView.maximumZoomScale = maxScale
        scrollView.minimumZoomScale = minScale
        scrollView.delegate = context.coordinator

        let hostedController = context.coordinator.hostingController
        hostedController.rootView = AnyView(content)
        hostedController.view.backgroundColor = .clear
        hostedController.view.translatesAutoresizingMaskIntoConstraints = false

        scrollView.addSubview(hostedController.view)

        NSLayoutConstraint.activate([
            hostedController.view.leadingAnchor.constraint(equalTo: scrollView.contentLayoutGuide.leadingAnchor),
            hostedController.view.trailingAnchor.constraint(equalTo: scrollView.contentLayoutGuide.trailingAnchor),
            hostedController.view.topAnchor.constraint(equalTo: scrollView.contentLayoutGuide.topAnchor),
            hostedController.view.bottomAnchor.constraint(equalTo: scrollView.contentLayoutGuide.bottomAnchor),
            hostedController.view.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor),
            hostedController.view.heightAnchor.constraint(equalTo: scrollView.frameLayoutGuide.heightAnchor)
        ])

        return scrollView
    }

    public func updateUIView(_ uiView: UIScrollView, context: Context) {
        context.coordinator.hostingController.rootView = AnyView(content)
        
        // Cek toleransi floating point agar terhindar dari siklus rekursi tak berujung
        if abs(uiView.zoomScale - currentScale) > 0.01 {
            uiView.setZoomScale(currentScale, animated: true)
        }
    }

    public final class Coordinator: NSObject, UIScrollViewDelegate {
        var parent: ZoomableScrollContainer
        let hostingController: UIHostingController<AnyView>

        init(parent: ZoomableScrollContainer) {
            self.parent = parent
            self.hostingController = UIHostingController(rootView: AnyView(EmptyView()))
        }

        public func viewForZooming(in scrollView: UIScrollView) -> UIView? {
            return hostingController.view
        }

        public func scrollViewDidEndZooming(_ scrollView: UIScrollView, with view: UIView?, atScale scale: CGFloat) {
            DispatchQueue.main.async {
                if abs(self.parent.currentScale - scale) > 0.001 {
                    self.parent.currentScale = scale
                }
            }
        }
    }
}
```

---

### 13. Exercise

#### Level: Easy
1. **Soal**: Buat struct `NativeActivityIndicator` menggunakan `UIViewRepresentable` yang membungkus `UIActivityIndicatorView`.
2. **Kebutuhan**: Menerima parameter `isAnimating: Bool` dan `style: UIActivityIndicatorView.Style`.
3. **Instruksi**: Pastikan indikator berputar saat `isAnimating` bernilai `true` dan berhenti saat bernilai `false` di dalam siklus `updateUIView`.

#### Level: Medium
1. **Soal**: Bungkus `UISearchBar` ke dalam `SearchBarBridge` dengan `UIViewRepresentable`.
2. **Kebutuhan**:
   - Sinkronkan isi teks pencarian ke `@Binding var text: String`.
   - Implementasikan tombol "Cancel" via delegasi `UISearchBarDelegate` di dalam `Coordinator` untuk mengosongkan teks dan melepaskan keyboard (`resignFirstResponder`).

#### Level: Hard
1. **Soal**: Bangun bridge multiplatform `CrossPlatformColorWell` yang menggunakan `NSColorWell` pada macOS (menggunakan `NSViewRepresentable`) dan `UIColorPickerViewController` pada iOS (menggunakan `UIViewControllerRepresentable`).
2. **Kebutuhan**:
   - Memiliki antarmuka publik tunggal terpadu: `CrossPlatformColorWell(selectedColor: Binding<Color>)`.
   - Gunakan conditional compilation (`#if os(iOS)` / `#if os(macOS)`).
   - Terapkan pencegahan siklus rekursi warna yang identik pada kedua platform.

---

### 14. Challenge

**Studi Kasus**: Implementasikan High-Throughput PDF Rendering Engine Bridge.

**Spesifikasi Desain**:
1. Buat bridge representable bernama `EnterprisePDFReaderView` yang membungkus `PDFView` dari framework `PDFKit`.
2. **Fitur Kritis**:
   - Menerima `URL` lokal dokumen PDF secara asinkron.
   - Mengirim status progress pembacaan halaman aktif ke SwiftUI: `@Binding var currentPageIndex: Int`.
   - Mengirim total keseluruhan halaman via *closure*: `onDocumentLoaded: (Int) -> Void`.
   - Mendukung pencarian teks in-document: Menerima binding `searchKeyword: String`. Komponen harus menyorot hasil pencarian (*highlight search results*) secara native tanpa memicu *freeze* pada Main Thread.
3. **Konstrain Teknis**:
   - Memori tidak boleh bocor saat beralih antar dokumen besar (>1000 halaman).
   - Seluruh interaksi delegasi harus sepenuhnya thread-safe dan mematuhi aturan konkurensi Swift 6 (`Sendable` checking).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Konseptual Dasar (Basic)
1. **Kapan `makeCoordinator()` dipanggil dalam siklus hidup `UIViewRepresentable`?**
   - A. Setiap kali ada perubahan `@Binding`.
   - B. Tepat sekali sebelum `makeUIView(context:)` pertama kali dieksekusi.
   - C. Dipanggil setiap kali metode `updateUIView` selesai berjalan.
   - D. Hanya dipanggil saat layout constraint mengalami tabrakan (*conflict*).
   *Kunci: B. Coordinator dibuat pertama kali sebelum view dibuat agar dapat langsung diteruskan melalui `context`.*

2. **Apa fungsi utama dari metode `dismantleUIView(_:coordinator:)`?**
   - A. Menghapus constraint Auto Layout dari memori.
   - B. Memaksa SwiftUI untuk merender ulang root window.
   - C. Membersihkan resource, timer, observer KVO, dan delegate UIKit sebelum view dilepas dari view graph.
   - D. Mereset ukuran intrinsic content size menjadi zero.
   *Kunci: C.*

3. **Mengapa memanggil mutasi `@State` secara langsung di dalam `updateUIView` berbahaya?**
   - A. Menyebabkan aplikasi mengalami segmentation fault secara instan.
   - B. Dapat memicu siklus rekursi rendering tak terbatas (*infinite render loop*).
   - C. Menghapus seluruh subview dari hierarki visual.
   - D. Mengubah background view menjadi transparan.
   *Kunci: B.*

4. **Protokol representable mana yang digunakan untuk membungkus view native pada ekosistem macOS (AppKit)?**
   - A. `CocoaViewRepresentable`
   - B. `NSViewRepresentable`
   - C. `AppKitBridgeRepresentable`
   - D. `MacUIViewRepresentable`
   *Kunci: B.*

5. **Apa peran dari struct `ProposedViewSize` pada implementasi `sizeThatFits`?**
   - A. Ukuran pasti yang dipaksakan parent view kepada child.
   - B. Ukuran layar fisik perangkat dalam pixel.
   - C. Proposal ukuran dari parent layout SwiftUI yang dapat berupa nilai pasti, nol, atau tidak terbatas (*unspecified*).
   - D. Ukuran batas rendering CoreAnimation.
   *Kunci: C.*

#### Bagian B: Analisis Arsitektur & Intermediat
6. **Manakah pendekatan yang benar untuk mencegah memory leak pada `Coordinator` yang menjadi delegasi objek UIKit?**
   - A. Mendeklarasikan Coordinator sebagai `struct`.
   - B. Memberikan modifier `unowned` pada semua instance view.
   - C. Menjadikan instance target UIKit di Coordinator sebagai referensi yang dibersihkan di `dismantleUIView`.
   - D. Melarang penggunaan closure di dalam Coordinator.
   *Kunci: C.*

7. **Bagaimana cara Auto Layout di dalam `UIView` memberitahu SwiftUI bahwa ukuran kontennya telah berubah secara mandiri?**
   - A. Memanggil `uiView.setNeedsLayout()`.
   - B. Memanggil `uiView.invalidateIntrinsicContentSize()`.
   - C. Mengirim event `NotificationCenter` global.
   - D. Menyetel `translatesAutoresizingMaskIntoConstraints = true`.
   *Kunci: B.*

8. **Saat mengintegrasikan `UIHostingController` di dalam `UICollectionViewCell`, apa yang harus dilakukan saat cell di-reuse (`prepareForReuse`)?**
   - A. Menghancurkan instance UIHostingController dan membuat baru dari nol.
   - B. Memanggil `hostingController.view.removeFromSuperview()` tanpa memutus kaitan hierarki controller.
   - C. Mengupdate `rootView` dengan data baru atau mereset status untuk mencegah data berkedip (*flickering*).
   - D. Mematikan rendering engine SwiftUI secara global.
   *Kunci: C.*

9. **Jika `ProposedViewSize.width` bernilai `nil`, bagaimana child view representable harus merespons dalam `sizeThatFits`?**
   - A. Melempar runtime error (`fatalError`).
   - B. Mengembalikan nilai `CGSize.zero`.
   - C. Mengembalikan ukuran intrinsik ideal child view tanpa batasan lebar (*unconstrained ideal size*).
   - D. Mengambil lebar layar penuh via `UIScreen.main.bounds.width`.
   *Kunci: C.*

10. **Bagaimana memastikan bahwa event pembaharuan dari delegasi UIKit dieksekusi secara aman di thread yang tepat saat berinteraksi dengan state SwiftUI?**
    - A. Membungkus mutasi binding di dalam blok Task detached.
    - B. Mengisolasi metode delegasi atau mutasi state dengan anotasi `@MainActor`.
    - C. Mengeksekusi mutasi di queue global background.
    - D. Menggunakan semaphor sync locks di main thread.
    *Kunci: B.*

#### Bagian C: Skenario Kasus Produksi
11. **Skenario Kasus 1**:
    Tim Anda menemukan bahwa interaksi `Pinch-to-zoom` pada representable kustom `MKMapView` terasa tersendat-sendat (*stuttering/jank*) dan FPS anjlok dari 120 FPS ke 35 FPS pada iPhone 15 Pro. Profiling di Instruments (*Time Profiler*) menunjukkan bahwa `SwiftUI.ViewGraph.updateOutputs` terpanggil terus-menerus selama gestur berlangsung.
    **Apa akar masalahnya dan bagaimana solusinya?**
    *Jawaban/Solusi*:
    Akar masalahnya adalah delegasi `mapViewDidChangeVisibleRegion` memperbarui status binding koordinat kamera secara real-time ke SwiftUI parent view, sehingga memicu proses diffing View Graph pada setiap tick gestur. Solusinya: Hentikan pembaruan binding terus-menerus selama gestur aktif. Perbarui status binding hanya saat interaksi zoom/pan selesai melalui delegasi `mapView(_:regionDidChangeAnimated:)`, atau isolasi status koordinat visual hanya di dalam level imperatif `Coordinator` tanpa memicu re-render pada body parent SwiftUI.

12. **Skenario Kasus 2**:
    Sebuah form input teks berbasis `UITextView` kustom di dalam sheet SwiftUI mengalami masalah layout: ketika pengguna mengetik kalimat yang sangat panjang, text view meluap (*overflow*) ke luar batas layar alih-alih menambah tinggi sheet atau memunculkan scrollbar.
    **Bagaimana mengonfigurasi layout constraint dan representable bridge untuk mengatasinya?**
    *Jawaban/Solusi*:
    Setel `isScrollEnabled = false` pada `UITextView` agar ia memiliki ukuran intrinsik (*intrinsic content size*) berbasis teks. Berikan prioritas kompresi vertikal yang tinggi (`setContentCompressionResistancePriority(.required, for: .vertical)`), implementasikan `sizeThatFits` yang mengkalkulasi tinggi aktual menggunakan `sizeThatFits(CGSize(width: proposal.width ?? defaultWidth, height: .greatestFiniteMagnitude))`, dan panggil `invalidateIntrinsicContentSize()` di `textViewDidChange`.

13. **Skenario Kasus 3**:
    Aplikasi perbankan Anda menggunakan `UIHostingController` untuk menyematkan kartu transaksi SwiftUI baru ke dalam legacy `UITableViewController`. Pengguna melaporkan bahwa animasi perubahan status (misal: kartu terbuka/expand) terpotong secara kaku (*clipping*) dan tidak sinkron dengan animasi tabel UIKit.
    **Bagaimana menyinkronkan sistem animasi antara SwiftUI dan UITableView?**
    *Jawaban/Solusi*:
    Di dalam block animasi UIKit (`tableView.beginUpdates()` / `tableView.endUpdates()` atau snapshot layout), bungkus pembaruan state SwiftUI di dalam `withAnimation`. Selain itu, jalankan `cell.contentView.layoutIfNeeded()` di dalam blok `UIView.animate` yang terkoordinasi agar Auto Layout cell UIKit beranimasi selaras dengan perubahan ukuran host SwiftUI.

---

### 16. Summary

- **Bridging Paradigms**: Menghubungkan UIKit/AppKit dengan SwiftUI membutuhkan pemahaman transisi antara lifecycle berbasis class yang persisten dan lifecycle deklaratif yang *transient*.
- **The Role of the Coordinator**: Berfungsi sebagai jembatan persisten yang menampung delegasi, observer, dan target-action imperatif untuk dikonversi menjadi data binding deklaratif.
- **Render Safeguards**: Hindari mutasi state SwiftUI langsung di dalam `updateUIView`/`updateUIViewController` untuk mencegah terjadinya *infinite render loops*. Gunakan *equality checks* sebelum memutasi properti view native.
- **Layout Arbitration**: Auto Layout imperatif dan layout tree deklaratif harus bernegosiasi via `sizeThatFits(_:uiView:context:)` dan `systemLayoutSizeFitting` agar tata letak tidak mengalami kolaps (*zero bounds*).
- **Graceful Dismantling**: Memori bocor pada arsitektur bridge hampir selalu disebabkan oleh delegasi yang menggantung atau observer yang tidak dibersihkan. Manfaatkan `dismantleUIView` sebagai fase teardown deterministik aplikasi enterprise Anda.