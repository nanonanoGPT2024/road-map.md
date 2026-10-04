# MODUL 07-01: Interoperabilitas Ekosistem: Bridge UIKit & AppKit

---

## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Topik Inti:** Swift & SwiftUI Framework Architecture
* **Kode Modul:** SWIFTUI-MOD-07-01
* **Tingkat Kesulitan:** Advanced / L4
* **Prasyarat Teknis:** 
  * Pemahaman mendalam terkait SwiftUI State Management (`@Binding`, `@StateObject`, `@Observable`).
  * Pemahaman mendalam terkait UIKit/AppKit lifecycle, Memory Management (ARC, Retain Cycles), Auto Layout, dan Delegate Pattern.
  * Swift Concurrency (`@MainActor`, `Sendable`).
* **Target Ekosistem:** iOS 16.0+, macOS 13.0+, visionOS 1.0+, Mac Catalyst.
* **Waktu Estimasi Pembelajaran:** 4.5 Jam (Teori, Bedah Kode, Hands-on Lab).

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, arsitek sistem dan senior engineer diharapkan mampu:

1. **Menganalisis dan Membedah Arsitektur Representable:** Memahami siklus hidup internal antarmuka `UIViewRepresentable`, `UIViewControllerRepresentable`, `NSViewRepresentable`, dan `NSViewControllerRepresentable`.
2. **Menguasai Sinkronisasi Status Dua Arah (Bidirectional Data Flow):** Mengintegrasikan sistem reaktif deklaratif SwiftUI dengan paradigma imperatif UIKit/AppKit menggunakan `Coordinator`, Delegate, KVO, dan Target-Action tanpa memicu siklus pembaruan tak terbatas (*infinite layout loops*).
3. **Mengelola Siklus Hidup dan Memori Tingkat Lanjut:** Mengimplementasikan teardown sumber daya yang benar melalui `dismantleUIView`/`dismantleNSView` untuk mencegah memory leak, retain cycle, dan thread violation.
4. **Menerapkan Bridging Sebaliknya (Embedding SwiftUI into UIKit/AppKit):** Mengoperasikan `UIHostingController` dan `NSHostingController` dalam arsitektur eksisting berbasis imperatif, termasuk penyesuaian ukuran intrinsik (*dynamic intrinsic content sizing*) dan propagasi environment.
5. **Membangun Komponen Lintas-Platform yang Resilien:** Mengabstraksi komponen imperatif legacy menjadi komponen deklaratif cross-platform (iOS & macOS) dengan performa setara native framework.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Deklaratif vs. Imperatif

Dalam ekosistem Apple, bridging bukan sekadar "membungkus tampilan" (*wrapping a view*), melainkan menjembatani dua paradigma komputasi UI yang berbeda secara fundamental:

```
+------------------------------------+------------------------------------+
| PARADIGMA IMPERATIF (UIKit/AppKit) | PARADIGMA DEKLARATIF (SwiftUI)     |
+------------------------------------+------------------------------------+
| State = Mutasi Objek Referensi     | State = Single Source of Truth     |
| (UIView/NSView adalah Class)       | (View adalah Struct/Nilai Ephemeral)|
+------------------------------------+------------------------------------+
| View bersifat persisten di memori. | View diciptakan dan dihancurkan    |
| Developer memutasi propertinya     | berulang kali setiap ada mutasi    |
| secara eksplisit langkah-demi-     | State. SwiftUI menghitung diff     |
| langkah (e.g., `view.text = "A"`). | pada graph view.                   |
+------------------------------------+------------------------------------+
| Layout: Auto Layout Constraint     | Layout: Proposisi Ukuran Parent -> |
| Engine (Cassowary Algorithm).      | Respon Child -> Parent Menempatkan |
| Sizing berbasis Frame / AutoLayout.| Sizing berbasis Layout Identity.   |
+------------------------------------+------------------------------------+
```

### Mental Model: The Diplomatic Ambassador (Coordinator Pattern)

Pandanglah `UIViewRepresentable` / `NSViewRepresentable` sebagai **Kedutaan Besar** dan `Coordinator` sebagai **Duta Besar**.
* **SwiftUI View Struct:** Bersifat fana (*ephemeral*), dibentuk dan dimusnahkan dalam hitungan milidetik saat *render pass*.
* **UIKit / AppKit View:** Bersifat persisten (*long-lived object*), hidup selama view hierarki menampilkannya.
* **Coordinator:** Entitas referensi (`class`) persisten yang dijamin tetap hidup sepanjang representable berada dalam tree. Coordinator bertindak sebagai penerjemah simultan: ia mendengarkan event delegasi imperatif dari UIKit/AppKit lalu memutasi state SwiftUI via `@Binding`, sekaligus menyaring pembaruan dari SwiftUI agar tidak diterapkan secara berlebihan ke UIKit/AppKit.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Alur Siklus Hidup dan Aliran Data Bridge (SwiftUI ↔ UIKit)

```
[ SwiftUI Engine ]                      [ Representable Bridge ]              [ UIKit / AppKit Platform ]
       |                                          |                                        |
       |--- 1. Evaluasi Dependency Graph ------->|                                        |
       |                                          |                                        |
       |--- 2. makeCoordinator() --------------->|                                        |
       |                                          |--- Inisialisasi Coordinator Instance ->|
       |                                          |                                        |
       |--- 3. makeUIView(context:) ------------>|                                        |
       |                                          |--- Inisialisasi Instance UIView ------>|
       |                                          |<-- Kembalikan Instance UIView --------|
       |                                          |                                        |
       |--- 4. updateUIView(uiView, context:) --->|                                        |
       |       (Difusi State Awal)                |--- Mutasi Properti UIKit ------------->|
       |                                          |                                        |
       |<======================= RUNTIME STEADY-STATE ====================================>|
       |                                          |                                        |
       |                                          |        [User Melakukan Interaksi]     |
       |                                          |                 |                      |
       |                                          |<-- 5. Target-Action / Delegate --------|
       |                                          |    (Coordinator Menerima Event)        |
       |<-- 6. Mutasi @Binding State ------------|                                        |
       |                                          |                                        |
       |--- 7. Engine Merender Ulang View Graph ->|                                        |
       |                                          |                                        |
       |--- 8. updateUIView(uiView, context:) --->|                                        |
       |       (Pencegahan Loop Diperlukan!)      |--- Mutasi Nilai Baru ke UIKit -------->|
       |                                          |                                        |
       |<======================= TEARDOWN PHASE ==========================================>|
       |                                          |                                        |
       |--- 9. dismantleUIView(uiView, coord:) -->|                                        |
       |       (Hapus dari Hierarki View)         |--- Lepas Delegate, Hentikan Thread --->|
       |                                          |--- Deallokasi Instance UIKit --------->|
       v                                          v                                        v
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Protokol `UIViewRepresentable` dan `NSViewRepresentable`

Struktur protokol jembatan mendefinisikan kontrak presisi tinggi:

```swift
public protocol UIViewRepresentable: View {
    associatedtype UIViewType: UIView
    associatedtype Coordinator = Void

    @MainActor func makeUIView(context: Self.Context) -> Self.UIViewType
    @MainActor func updateUIView(_ uiView: Self.UIViewType, context: Self.Context)
    @MainActor static func dismantleUIView(_ uiView: Self.UIViewType, coordinator: Self.Coordinator)
    @MainActor func makeCoordinator() -> Self.Coordinator
    @MainActor func sizeThatFits(_ proposal: ProposedViewSize, uiView: Self.UIViewType, context: Self.Context) -> CGSize?
}
```

### Anatomi `Context`

Struktur `Context` memuat dependensi krusial runtime:
1. `context.coordinator`: Akses ke instance tunggal kelas `Coordinator`.
2. `context.environment`:Snapshot dari `EnvironmentValues` saat pemanggilan fungsi berlangsung.
3. `context.transaction`: Berisi metadata animasi, transaction flags, dan status transisi dari engine SwiftUI.

### Mekanisme Internal: Siklus Mutasi vs Siklus Render

* **Instansiasi Awal:**
  1. SwiftUI mendeteksi node `UIViewRepresentable` baru pada tree layout.
  2. Engine memanggil `makeCoordinator()`. Objek ini disimpan secara internal di *Render Node NodeStorage*.
  3. `makeUIView(context:)` dipanggil. Objek `UIView` diinstansiasi dan dikembalikan.
  4. Segera setelah `makeUIView`, engine memanggil `updateUIView(_:context:)` untuk memastikan nilai-nilai awal dari SwiftUI State diterapkan ke UIKit View.
* **Siklus Pembaruan (Update Cycle):**
  * Ketika nilai `@State` atau `@Binding` luar berubah, node SwiftUI diperbarui.
  * `updateUIView(_:context:)` dieksekusi **kembali**.
  * **BAHAYA:** Jika di dalam `updateUIView`, pembaruan properti UIKit memicu event `UIControlEventValueChanged` atau delegate callback yang kembali memutasi `@Binding` SwiftUI, maka akan tercipta **Feedback Loop Tak Terbatas**, mengakibatkan CPU 100% dan stack overflow / frame drops drastis.
* **Siklus Pembongkaran (Dismantle Phase):**
  * Ketika node terdepresiasi dan dikeluarkan dari View Graph, SwiftUI memanggil `static dismantleUIView(_:coordinator:)`.
  * Metode ini bersifat `static` untuk mencegah akses implisit ke state struct yang sudah tidak valid.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Negosiasi Sistem Layout (Cassowary Auto Layout vs SwiftUI Propose-Size-Place)

SwiftUI beroperasi menggunakan algoritma proposisi layout tiga-tahap:
1. **Parent mengusulkan ukuran** (`ProposedViewSize` yang dapat bernilai konkret, `nil`, atau `infinity`).
2. **Child menghitung ukurannya sendiri** berdasarkan usulan tersebut.
3. **Parent menempatkan Child** pada koordinat tertentu.

UIKit, sebaliknya, menggunakan Cassowary Constraint Solver Engine yang berbasis sistem persamaan linier atau sistem `intrinsicContentSize`.

Ketika dijembatani:
* Default-nya, SwiftUI membungkus `UIView` ke dalam hosting layer privat (`_UIHostingView`).
* SwiftUI menanyakan `sizeThatFits(_:uiView:context:)`. Jika tidak di-override, implementasi default akan memanggil `uiView.systemLayoutSizeFitting(...)` atau membaca `uiView.intrinsicContentSize`.
* **Ketidakcocokan Umum:** `UIView` yang memanfaatkan constraint fleksibel tanpa batasan implisit (contoh: `UIScrollView` tanpa content size terdefinisi) akan collapse menjadi `CGSize.zero` di SwiftUI kecuali modifier `.frame()` diterapkan, atau metode `sizeThatFits` diimplementasikan secara eksplisit.

### 2. UIHostingController & NSHostingController

Bridging dari SwiftUI ke UIKit/AppKit menggunakan:
* iOS: `UIHostingController<Content: View>`
* macOS: `NSHostingController<Content: View>`

`UIHostingController` adalah subclass dari `UIViewController` yang memegang view tree deklaratif di dalamnya.
* **Sizing Target:** Menggunakan `sizingOptions` (misalnya `.intrinsicContentSize`) untuk menentukan bagaimana controller menginformasikan sistem Auto Layout UIKit mengenai ukurannya.
* **Safe Area Propagation:** `UIHostingController` secara default memperhitungkan safe area controller induknya. Bila safe area ganda terjadi, flag `disableSafeArea()` internal atau pengaturan layout margins harus dikonfigurasi.

### 3. Thread Concurrency & MainActor Boundaries

Semua operasi pada `UIViewRepresentable` dan `NSViewRepresentable` diwajibkan berjalan pada `@MainActor`. Swift 6 strict concurrency checks akan mengidentifikasi pelanggaran di mana delegate UIKit dipanggil dari background thread dan memutasi state representable tanpa context hopping ke MainActor.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental: Bridging komponen `UITextView` UIKit ke SwiftUI dengan sinkronisasi teks dua arah dan penanganan auto-sizing dinamis.

```swift
import SwiftUI
import UIKit

// MARK: - 1. Definition of UIViewRepresentable
struct ResilientTextView: UIViewRepresentable {
    @Binding var text: String
    var placeholder: String
    var onCommit: () -> Void

    // MARK: - 2. Coordinator Implementation
    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    // MARK: - 3. Lifecycle: makeUIView
    func makeUIView(context: Context) -> UITextView {
        let textView = UITextView()
        textView.delegate = context.coordinator
        textView.font = UIFont.preferredFont(forTextStyle: .body)
        textView.backgroundColor = .clear
        textView.isScrollEnabled = false // Mengharuskan sizing dinamis
        textView.textContainerInset = UIEdgeInsets(top: 8, left: 4, bottom: 8, right: 4)
        
        // Accessibility
        textView.accessibilityLabel = placeholder
        return textView
    }

    // MARK: - 4. Lifecycle: updateUIView
    func updateUIView(_ uiView: UITextView, context: Context) {
        // PENTING: Mencegah siklus umpan balik tak terbatas (Feedback Loop)
        // Hanya update teks UIKit jika nilainya benar-benar berbeda dari state SwiftUI
        if uiView.text != text {
            uiView.text = text
        }
    }

    // MARK: - 5. Lifecycle: dismantleUIView
    static func dismantleUIView(_ uiView: UITextView, coordinator: Coordinator) {
        // Membersihkan delegate untuk memutus dependensi memori
        uiView.delegate = nil
    }

    // MARK: - 6. Coordinator Class
    final class Coordinator: NSObject, UITextViewDelegate {
        var parent: ResilientTextView

        init(parent: ResilientTextView) {
            self.parent = parent
        }

        func textViewDidChange(_ textView: UITextView) {
            // Mencegah propagasi jika nilainya identik
            if self.parent.text != textView.text {
                self.parent.text = textView.text
            }
        }

        func textView(_ textView: UITextView, shouldChangeTextIn range: NSRange, replacementText text: String) -> Bool {
            // Menangani tombol 'Return' sebagai event onCommit
            if text == "\n" {
                textView.resignFirstResponder()
                parent.onCommit()
                return false
            }
            return true
        }
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Pemeriksaan Mendalam Kode Seksi 07:

1. **`struct ResilientTextView: UIViewRepresentable`**: Mendeklarasikan struct penyesuai tipe nilai. Struktur ini akan dihancurkan dan dibuat ulang secara berkala oleh SwiftUI layout graph engine.
2. **`@Binding var text: String`**: Sumber kebenaran tunggal (*Single Source of Truth*). Nilai ini dioperasikan secara referensial dari parent view SwiftUI.
3. **`func makeCoordinator() -> Coordinator`**:
   * Dieksekusi **tepat satu kali** saat inisialisasi awal oleh SwiftUI runtime.
   * Instance `Coordinator` disimpan secara persisten di storage node SwiftUI, terpisah dari struct representable yang fana.
4. **`makeUIView(context: Context)`**:
   * Bertanggung jawab murni untuk alokasi memori dan konfigurasi statis awal dari `UITextView`.
   * Pemasangan `textView.delegate = context.coordinator` menghubungkan delegate imperatif ke duta besar persisten.
5. **`updateUIView(_ uiView: UITextView, context: Context)`**:
   * `if uiView.text != text`: **Pencegah Feedback Loop.** Apabila baris ini ditiadakan dan langsung menetapkan `uiView.text = text`, kursor (caret position) pengguna akan meloncat ke akhir teks setiap kali satu karakter diketik, dan berisiko memicu infinite re-layout pipeline.
6. **`static func dismantleUIView(_ uiView: UITextView, coordinator: Coordinator)`**:
   * Pemutusan eksplisit `uiView.delegate = nil` adalah pertahanan wajib dari insiden *dangling pointers* atau pemanggilan delegate setelah node dihapus dari scene aktif.
7. **`func textViewDidChange(_ textView: UITextView)`**:
   * Mengambil input imperatif pengguna dari sub-sistem iOS dan meneruskannya kembali ke SwiftUI melalui pembaruan state `parent.text = textView.text`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Enterprise Cross-Platform Hybrid WKWebView

**Kebutuhan Bisnis:**
Sebuah aplikasi FinTech memerlukan komponen penampil dokumen legal dan dashboard analitik berbasis Web dengan spesifikasi:
1. Berjalan secara seragam di **iOS** (`UIViewRepresentable`) dan **macOS** (`NSViewRepresentable`).
2. Mampu menyuntikkan token otentikasi Bearer ke header permintaan HTTP secara aman sebelum memuat URL.
3. Menerima pesan telemetry dari JavaScript via WebKit Script Message Handler (`window.webkit.messageHandlers.telemetry.postMessage(...)`).
4. Mengomunikasikan status loading (`isLoading`), estimasi progress (`progress`), dan error handling secara reaktif ke SwiftUI UI Shell.
5. Menghentikan semua script engine dan menghapus script message handlers saat view ditutup guna mencegah memory leak skala besar (WebProcess leakage).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi lintas platform (Unified Cross-Platform Engine) menggunakan conditional compilation directives (`#if os(...)`) yang mematuhi standar produksi tingkat tinggi:

```swift
import SwiftUI
import WebKit

// MARK: - Platform Aliasing
#if os(iOS)
public typealias PlatformViewRepresentable = UIViewRepresentable
public typealias NativeView = UIView
#elseif os(macOS)
public typealias PlatformViewRepresentable = NSViewRepresentable
public typealias NativeView = NSView
#endif

// MARK: - Core Component
public struct UnifiedWebView: PlatformViewRepresentable {
    public let url: URL
    public let authToken: String?
    @Binding public var isLoading: Bool
    @Binding public var estimatedProgress: Double
    public var onTelemetryReceived: ((String) -> Void)?

    public init(
        url: URL,
        authToken: String? = nil,
        isLoading: Binding<Bool>,
        estimatedProgress: Binding<Double>,
        onTelemetryReceived: ((String) -> Void)? = nil
    ) {
        self.url = url
        self.authToken = authToken
        self._isLoading = isLoading
        self._estimatedProgress = estimatedProgress
        self.onTelemetryReceived = onTelemetryReceived
    }

    // MARK: - Coordinator Factory
    public func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - iOS Implementation
    #if os(iOS)
    public func makeUIView(context: Context) -> WKWebView {
        createAndConfigureWebView(context: context)
    }

    public func updateUIView(_ uiView: WKWebView, context: Context) {
        updateWebViewState(uiView, context: context)
    }

    public static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        tearDownWebView(uiView, coordinator: coordinator)
    }
    #endif

    // MARK: - macOS Implementation
    #if os(macOS)
    public func makeNSView(context: Context) -> WKWebView {
        createAndConfigureWebView(context: context)
    }

    public func updateNSView(_ nsView: WKWebView, context: Context) {
        updateWebViewState(nsView, context: context)
    }

    public static func dismantleNSView(_ nsView: WKWebView, coordinator: Coordinator) {
        tearDownWebView(nsView, coordinator: coordinator)
    }
    #endif

    // MARK: - Shared Configuration Logic
    private func createAndConfigureWebView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        let userContentController = WKUserContentController()

        // Pasang Script Message Handler yang dibungkus Leak-Avoider Proxy
        let handlerProxy = WeakScriptMessageHandler(delegate: context.coordinator)
        userContentController.add(handlerProxy, name: "telemetry")
        configuration.userContentController = userContentController

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator

        // KVO Observers
        context.coordinator.setupObservers(for: webView)

        // Load Request Awal
        var request = URLRequest(url: url)
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        webView.load(request)

        return webView
    }

    private func updateWebViewState(_ webView: WKWebView, context: Context) {
        // Hindari load ulang jika URL tidak berubah
        if webView.url != url && !url.absoluteString.isEmpty {
            var request = URLRequest(url: url)
            if let token = authToken {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
            webView.load(request)
        }
    }

    private static func tearDownWebView(_ webView: WKWebView, coordinator: Coordinator) {
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.configuration.userContentController.removeScriptMessageHandler(forName: "telemetry")
        coordinator.invalidateObservers(for: webView)
    }

    // MARK: - Coordinator Class
    @MainActor
    public final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        private var parent: UnifiedWebView
        private var progressObservation: NSKeyValueObservation?
        private var loadingObservation: NSKeyValueObservation?

        init(_ parent: UnifiedWebView) {
            self.parent = parent
            super.init()
        }

        func setupObservers(for webView: WKWebView) {
            progressObservation = webView.observe(\.estimatedProgress, options: [.new]) { [weak self] _, change in
                guard let self = self, let newValue = change.newValue else { return }
                Task { @MainActor in
                    self.parent.estimatedProgress = newValue
                }
            }

            loadingObservation = webView.observe(\.isLoading, options: [.new]) { [weak self] _, change in
                guard let self = self, let newValue = change.newValue else { return }
                Task { @MainActor in
                    self.parent.isLoading = newValue
                }
            }
        }

        func invalidateObservers(for webView: WKWebView) {
            progressObservation?.invalidate()
            progressObservation = nil
            loadingObservation?.invalidate()
            loadingObservation = nil
        }

        // WKNavigationDelegate
        public func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            Task { @MainActor in
                self.parent.isLoading = false
            }
        }

        public func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            Task { @MainActor in
                self.parent.isLoading = false
            }
        }

        // WKScriptMessageHandler
        public func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            if message.name == "telemetry", let body = message.body as? String {
                self.parent.onTelemetryReceived?(body)
            }
        }
    }

    // MARK: - Memory Leak Avoider Proxy
    private final class WeakScriptMessageHandler: NSObject, WKScriptMessageHandler {
        private weak var delegate: WKScriptMessageHandler?

        init(delegate: WKScriptMessageHandler) {
            self.delegate = delegate
            super.init()
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            delegate?.userContentController(userContentController, didReceive: message)
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

```
+-----------------------------------+-----------------------------------+-----------------------------------+
| PARAMETER                         | NATIVE SWIFTUI (Pure Declarative) | BRIDGED (UIKit / AppKit Bridge)   |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Biaya Eksekusi Runtime (Overhead) | Mendekati nol; diff engine        | Menengah-Tinggi; ada overhead     |
|                                   | dioptimasi langsung ke CoreAnim.  | hosting layer & bridging wrapper. |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Kontrol Perilaku Komponen Rendah  | Rendah. Bergantung pada API yang  | Mutlak (100%). Akses langsung     |
| (Low-Level Customization)         | diekspos oleh framework SwiftUI.  | ke CoreAnimation layer, Subviews, |
|                                   |                                   | delegate methods tersembunyi.     |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Stabilitas Layout                 | Otomatis mengadaptasi dynamic-    | Rawan glitch (sizing collapse)    |
|                                   | type & safe areas.                | bila AutoLayout & Frame contract  |
|                                   |                                   | tidak sinkron sempurna.           |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Biaya Perawatan Kode (Maintain)   | Rendah; lebih sedikit baris kode. | Tinggi; perlu mitigasi memori,    |
|                                   |                                   | thread crossing, dan deallokasi.  |
+-----------------------------------+-----------------------------------+-----------------------------------+
| Kompatibilitas Sistem Legacy      | Tidak dapat memuat API pre-iOS 13 | Memungkinkan adopsi gradual code  |
|                                   | secara native.                    | basis tua (10+ tahun) ke SwiftUI. |
+-----------------------------------+-----------------------------------+-----------------------------------+
```

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Catastrophic Infinite Update Loop
* **Penyebab:** Memodifikasi SwiftUI State di dalam `updateUIView` atau melalui delegate yang terpicu secara otomatis oleh manipulasi programatik.
* **Gejala:** Aplikasi membeku (*UI freeze*), konsumsi baterai melonjak, konsol log dibanjiri pemanggilan view evaluation tanpa akhir.
* **Solusi Mitigasi:** Selalu validasi perbedaan nilai:
  ```swift
  if uiView.property != context.coordinator.cachedProperty {
      uiView.property = context.coordinator.cachedProperty
  }
  ```

### 2. AutoLayout Sizing Collapse
* **Penyebab:** Membungkus `UIView` yang relies pada constraints internal tanpa menetapkan batasan vertikal/horizontal yang rigid, atau tanpa override `sizeThatFits`.
* **Solusi Mitigasi:**
  Tentukan nilai eksplisit untuk *compression resistance* dan *content hugging*:
  ```swift
  uiView.setContentHuggingPriority(.defaultHigh, for: .vertical)
  uiView.setContentCompressionResistancePriority(.defaultHigh, for: .vertical)
  ```
  Atau implementasikan protokol:
  ```swift
  func sizeThatFits(_ proposal: ProposedViewSize, uiView: MyUIView, context: Context) -> CGSize? {
      let targetSize = proposal.replacingUnspecifiedDimensions()
      return uiView.systemLayoutSizeFitting(targetSize)
  }
  ```

### 3. State Inconsistency Selama Transisi SwiftUI Animation
* **Penyebab:** Ketika SwiftUI menjalankan blok `withAnimation`, mutasi nilai di dalam `updateUIView` diterapkan seketika (*instant mutation*), merusak interpolasi kurva animasi SwiftUI.
* **Solusi Mitigasi:** Gunakan `context.transaction` untuk mendeteksi apakah pembaruan terjadi dalam konteks animasi:
  ```swift
  if let animation = context.transaction.animation {
      UIView.animate(withDuration: 0.35) {
          uiView.alpha = newAlpha
      }
  } else {
      uiView.alpha = newAlpha
  }
  ```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Mengalokasikan Coordinator Secara Manual dalam Body View
```swift
// SALAH: Coordinator dibuat ulang setiap render pass!
func updateUIView(_ uiView: MyView, context: Context) {
    let coordinator = Coordinator()
    uiView.delegate = coordinator
}

// BENAR: Wajib gunakan lifecycle makeCoordinator bawaan protokol
func makeCoordinator() -> Coordinator {
    Coordinator(self)
}
```

### Anti-Pattern 2: Capturing Strong Reference Struct Representable di Coordinator
```swift
// SALAH: Menyimpan referensi struct secara langsung pada escaping block
class Coordinator: NSObject {
    var parent: MyRepresentable // Struct disalin atau mereferensikan state usang!
    
    func onAction() {
        // Parent di sini mungkin snapshot lama, BUKAN representable aktif!
        parent.stateValue = true 
    }
}

// BENAR: Update data melalui Binding atau pass updateUIView context
class Coordinator: NSObject {
    var parent: MyRepresentable
    init(_ parent: MyRepresentable) { self.parent = parent }
    
    // Perbarui referensi struct pada setiap cycle updateUIView
    func update(parent: MyRepresentable) {
        self.parent = parent
    }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Selalu Implementasikan `dismantleUIView` / `dismantleNSView`**: Jangan berasumsi ARC akan membersihkan segalanya. Khususnya untuk NotificationCenter, Delegate, KVO, Hardware Sensors (CoreLocation, AVFoundation), pembersihan eksplisit adalah keharusan.
2. **Patuhi Batasan Thread `@MainActor`**: Seluruh interaksi kelas `Coordinator` yang menyentuh UI atau mengabarkan SwiftUI State harus didekorasi dengan atribut `@MainActor`.
3. **Penyelarasan SwiftUI Environment**: Teruskan nilai `context.environment` (seperti `colorScheme`, `isEnabled`, `layoutDirection`) ke subview platform UIKit/AppKit agar adaptasi Dark Mode dan Localization terjadi secara instan dan sinkron.
4. **Isolasi Logika Komponen**: Bungkus komponen representable ke dalam module/paket independen (Swift Package) terisolasi untuk membatasi polusi dependensi legacy ke view tree modern.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

* **Menghindari Redundant Allocations:** Alokasikan objek berat (seperti layout engines, formatters, image filters) di dalam `makeUIView` atau di dalam instance `Coordinator`, jangan pernah menginisialisasinya di dalam `updateUIView`.
* **Memanfaatkan `CATransaction.disableActions()`**: Bila UIKit component melakukan sinkronisasi ukuran internal, nonaktifkan animasi implisit CoreAnimation agar tidak terjadi visual stutter/glitch:
  ```swift
  CATransaction.begin()
  CATransaction.setDisableActions(true)
  uiView.frame = newFrame
  CATransaction.commit()
  ```
* **Bypass SwiftUI Diffing yang Tidak Perlu:** Jangan memutasi atribut UIKit jika nilainya secara semantik bernilai sama. Diffing manual pada tipe primitif (String, Int, Bool, Color) jauh lebih cepat daripada memicu layout pass UIKit yang lambat (`setNeedsLayout()`).

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Memory Corruption & Retain Cycles Pada WKWebView Message Handlers**: `WKUserContentController.add(_:name:)` mempertahankan referensi kuat (*strong reference*) ke receiver. Mengirimkan `Coordinator` secara langsung tanpa proxy pelepas (*Weak proxy*) akan menyebabkan kebocoran controller permanen dari memori.
2. **Sanitasi Data Antar Boundary**: Ketika menerima string, data, atau skrip dari JavaScript/C-libraries melalui `Coordinator`, lakukan decoding tipe yang aman (*safe type casting*) sebelum memutasi `@Binding` SwiftUI.
3. **Thread-Safe State Synchronization**: Hindari penggunaan GCD unsafe primitives (`DispatchQueue.main.sync`). Selalu gunakan `Task { @MainActor in ... }` untuk melompati context execution kembali ke UI thread.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

* **Mengaktifkan Runtime View Hierarchy Debugger:**
  Gunakan Xcode View Hierarchy Inspector. View UIKit yang dibungkus SwiftUI akan muncul di bawah node bertipe `_UIHostingView` atau `SwiftUI.RepresentablePlatformViewHost`.
* **Trace Lifecycle Menggunakan `os.Logger`:**
  Pasang Structured Logging pada setiap tahap siklus hidup bridging:
  ```swift
  import os

  private let logger = Logger(subsystem: "com.enterprise.app", category: "BridgeLifecycle")

  func makeUIView(context: Context) -> CustomUIView {
      logger.debug("[LIFECYCLE] makeUIView invoked on MainThread: \(Thread.isMainThread)")
      return CustomUIView()
  }

  func updateUIView(_ uiView: CustomUIView, context: Context) {
      logger.debug("[LIFECYCLE] updateUIView triggered. Transaction: \(String(describing: context.transaction))")
  }

  static func dismantleUIView(_ uiView: CustomUIView, coordinator: Coordinator) {
      logger.debug("[LIFECYCLE] dismantleUIView triggered. Cleaning up resources.")
  }
  ```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+------------------------------------+------------------------------------+
| FUNGSI PROTOKOL                    | TUJUAN / FREKUENSI EKSEKUSI        |
+------------------------------------+------------------------------------+
| `makeCoordinator()`                | Alokasi Duta Besar; dipanggil      |
|                                    | HANYA 1x saat inisialisasi awal.   |
+------------------------------------+------------------------------------+
| `makeUIView(context:)`             | Instansiasi Objek UI imperatif;    |
|                                    | dipanggil HANYA 1x di awal hidup.  |
+------------------------------------+------------------------------------+
| `updateUIView(_:context:)`         | Rekonsiliasi State SwiftUI ke View |
|                                    | UIKit; dipanggil BERKALI-KALI      |
|                                    | setiap dependensi state berubah.   |
+------------------------------------+------------------------------------+
| `sizeThatFits(_:uiView:context:)`  | Menghitung usulan ukuran spesifik; |
|                                    | jembatan antara AutoLayout-SwiftUI.|
+------------------------------------+------------------------------------+
| `dismantleUIView(_:coordinator:)`  | Final teardown; dipanggil 1x saat  |
|                                    | node dihapus dari Scene permanen.  |
+------------------------------------+------------------------------------+
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Tingkat Dasar (Basic)

1. **Kapan metode `makeCoordinator()` dipanggil pertama kali oleh runtime SwiftUI?**
   * **A.** Setiap kali nilai `@Binding` berubah.
   * **B.** Tepat sebelum `makeUIView` dijalankan pada awal pembentukan view hierarchy.
   * **C.** Tepat setelah `dismantleUIView` selesai.
   * **D.** Bersamaan dengan `sizeThatFits`.
   * *Jawaban:* **B**.
   * *Alasan:* SwiftUI membentuk objek `Coordinator` persisten sebelum memanggil `makeUIView` sehingga instance coordinator sudah dapat disuntikkan ke dalam `Context`.

2. **Mengapa `dismantleUIView` dideklarasikan sebagai metode `static`?**
   * **A.** Agar dapat mengakses private property struct.
   * **B.** Untuk mencegah memory leak akibat retain struct representable yang sudah kedaluwarsa.
   * **C.** Karena UIKit memerlukan static C-function pointer.
   * **D.** Agar compiler dapat mengabaikan pemanggilan metode ini jika tidak di-override.
   * *Jawaban:* **B**.
   * *Alasan:* Metode static memastikan tidak ada capturing closure yang tidak disengaja terhadap nilai internal struct representable yang sedang dihancurkan.

3. **Komponen manakah yang digunakan untuk memasukkan View SwiftUI ke dalam view hierarchy UIKit eksisting?**
   * **A.** `UIViewRepresentable`
   * **B.** `UIHostingController`
   * **C.** `NSViewBridge`
   * **D.** `AppKitHostingView`
   * *Jawaban:* **B**.
   * *Alasan:* `UIHostingController` membungkus representasi view deklaratif SwiftUI ke dalam arsitektur `UIViewController` milik UIKit.

4. **Apa akibat langsung jika di dalam `updateUIView` kita memutasi `@Binding` state tanpa conditional checking?**
   * **A.** Compile-time Error.
   * **B.** Retain cycle seketika.
   * **C.** Infinite render update loop yang membekukan aplikasi.
   * **D.** Deallocator thread crash.
   * *Jawaban:* **C**.
   * *Alasan:* Mutasi binding memicu SwiftUI me-render ulang view, yang kemudian memanggil `updateUIView` kembali, memicu binding lagi, tanpa akhir.

5. **Di thread manakah protokol `UIViewRepresentable` menjamin eksekusi semua metodenya?**
   * **A.** Background Worker Thread.
   * **B.** CoreAnimation ThreadPool.
   * **C.** `@MainActor` (UI Thread).
   * **D.** Sesuai thread pemanggil sebelumnya.
   * *Jawaban:* **C**.
   * *Alasan:* Seluruh manipulasi UI pada UIKit/AppKit dan SwiftUI wajib berjalan secara eksklusif di `@MainActor`.

---

### Tingkat Menengah (Intermediate)

6. **Bagaimana cara paling efisien mencegah memory leak saat menggunakan delegate berbasis target-action atau WebKit handlers pada `Coordinator`?**
   * **A.** Menjadikan struct representable sebagai weak reference.
   * **B.** Menggunakan Weak Proxy pattern dan membersihkan relasi di `dismantleUIView`.
   * **C.** Menghapus coordinator di `makeUIView`.
   * **D.** Memanggil `fatalError()` saat deinit.
   * *Jawaban:* **B**.
   * *Alasan:* Weak proxy memutus retain cycle yang dibuat oleh API legacy (seperti `WKUserContentController`) dan `dismantleUIView` memastikan pelepasan delegate saat representable dihancurkan.

7. **Apa yang terjadi secara default jika komponen `UIScrollView` di-wrap ke `UIViewRepresentable` tanpa frame dan tanpa implementasi `sizeThatFits`?**
   * **A.** ScrollView mengambil seluruh layar otomatis.
   * **B.** ScrollView akan collapse menjadi ukuran nol (`CGSize.zero`) karena intrinsic content size-nya tidak terdefinisi bagi engine layout SwiftUI.
   * **C.** SwiftUI menghasilkan runtime assertion crash.
   * **D.** Compiler gagal mem-build module.
   * *Jawaban:* **B**.
   * *Alasan:* ScrollView tidak memiliki intrinsic content size yang pasti tanpa constraints yang mengikat ke boundary parent, sehingga usulan layout SwiftUI menghasilkan ukuran 0.

8. **Bagaimana kita dapat menyinkronkan status animasi antara SwiftUI `withAnimation` block dan mutasi UIKit di dalam `updateUIView`?**
   * **A.** Menggunakan `DispatchQueue.main.asyncAfter`.
   * **B.** Menambahkan decorator `@Animatable`.
   * **C.** Memeriksa properti `context.transaction.animation` dan mengaplikasikan `UIView.animate` yang sesuai.
   * **D.** Memanggil `uiView.layer.removeAllAnimations()`.
   * *Jawaban:* **C**.
   * *Alasan:* `context.transaction` memuat metadata animasi aktif yang sedang dijalankan oleh engine SwiftUI.

9. **Jika representable memerlukan nilai Environment (contoh: `@Environment(\.colorScheme)`), bagaimana coordinator dapat mengakses nilai mutakhir tersebut saat event delegasi berlangsung?**
   * **A.** Lewat `UIApplication.shared.windows`.
   * **B.** Dengan meng-update properti referensi parent di dalam `updateUIView(_:context:)` pada setiap pass.
   * **C.** Environment tidak bisa diakses di Coordinator.
   * **D.** Melalui UserDefaults.
   * *Jawaban:* **B**.
   * *Alasan:* Menugaskan `context.coordinator.parent = self` pada `updateUIView` menjamin snapshot struct terbaru (beserta environment-nya) tersimpan pada duta besar persisten.

10. **Apa perbedaan mendasar antara `NSViewRepresentable` (macOS) dan `UIViewRepresentable` (iOS)?**
    * **A.** Tidak ada perbedaan, keduanya memiliki method signature yang persis sama.
    * **B.** `NSViewRepresentable` menggunakan `makeNSView`/`updateNSView` dan mengelola hierarki koordinat terbalik (*flipped coordinates*) serta paradigma layout AppKit.
    * **C.** `NSViewRepresentable` berjalan di background thread secara asynchronous.
    * **D.** `NSViewRepresentable` tidak mendukung coordinator pattern.
    * *Jawaban:* **B**.
    * *Alasan:* `NSViewRepresentable` disesuaikan khusus untuk AppKit, termasuk tipe view `NSView` yang secara historis memiliki orientasi origin (0,0) di kiri bawah, bukan kiri atas seperti UIKit.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Objective
Bangun komponen kamera live-preview tingkat produksi bernama **`UnifiedCameraScannerView`** yang membungkus komponen `AVCaptureSession` dari framework **AVFoundation** ke dalam **SwiftUI** dengan spesifikasi:

### Kriteria Fungsional:
1. **Representable Implementation:**
   * Buat `CustomCameraPreviewView: UIView` yang memiliki `AVCaptureVideoPreviewLayer` sebagai layer utamanya (`override class var layerClass: AnyClass { return AVCaptureVideoPreviewLayer.self }`).
   * Bungkus dalam `CameraScannerBridge: UIViewRepresentable`.
2. **Sinkronisasi Status Dua Arah:**
   * Berikan `@Binding var isTorchOn: Bool`.
   * Berikan closure callback: `onBarcodeDetected: (String) -> Void`.
3. **Pemberisihan Sumber Daya (Teardown):**
   * Pastikan `dismantleUIView` menghentikan `AVCaptureSession` secara asynchronous di serial queue agar tidak memblokir Main Thread (*UI Hitch*).
4. **Error Handling & Concurrency:**
   * Tangani izin akses kamera (`AVCaptureDevice.authorizationStatus`).
   * Tampilkan fallback SwiftUI View jika izin ditolak pengguna.
5. **Testing Verification:**
   * Uji dengan Instruments (Leaks & Time Profiler): Pastikan saat view berganti via SwiftUI `NavigationStack`, tidak ada memory leak dari session kamera atau retain cycle antara Coordinator dan AVCaptureMetadataOutputObjectsDelegate.