# Kurikulum Rekayasa Perangkat Lunak iOS Enterprise
## Bab 08: Pengujian Perangkat Lunak Komprehensif
### Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Mengimplementasikan arsitektur pengujian tingkat lanjut yang deterministik, terisolasi, dan bebas efek samping (*zero-side-effect*) pada aplikasi iOS skala enterprise.
- Membangun *custom networking interceptor* menggunakan subkelas `URLProtocol` dan arsitektur *mocking* tanpa mengubah kode produksi (*zero-code pollution*).
- Merancang dan mengeksekusi *Snapshot Testing* lintas perangkat, orientasi, serta variasi *Dynamic Type* secara otomatis dengan pustaka berbasis Swift modern.
- Menulis pengujian performa mendalam berbasis `XCTMetric` (`XCTClockMetric`, `XCTMemoryMetric`, `XCTCPUMetric`, `XCTOSSignpostMetric`) untuk mengukur degradasi memori dan *rendering latency*.
- Mengelola isolasi konkuren (*Swift 6 Concurrency / MainActor isolation*) dalam `XCTestCase` tanpa menimbulkan *race condition* atau *deadlock*.
- Mengotomatisasi dan mengoptimasi eksekusi pengujian skala besar di CI/CD dengan *test sharding*, paralelisasi simulasi (*simctl concurrency*), dan eliminasi *flakiness*.

---

### 2. Prerequisite
Untuk mengikuti modul ini dengan optimal, peserta wajib menguasai:
1. **Swift Concurrency**: `async`/`await`, `Task`, `Actor`, dan `@MainActor`.
2. **Dasar XCTest**: Siklus hidup `XCTestCase` (`setUpWithError`, `tearDownWithError`), *Unit Testing* dasar, serta *Assertion APIs*.
3. **Arsitektur Aplikasi iOS**: Pola Clean Architecture, VIPER, atau Modular Architecture (SPM/CocoaPods).
4. **Networking Fundamental**: `URLSession`, `URLSessionConfiguration`, HTTP protocol specs, dan JSON serialization.
5. **Tooling & CLI**: `xcodebuild`, `xcrun simctl`, Git, serta pemahaman dasar *toolchain* CI/CD (GitHub Actions/Fastlane).

---

### 3. Concept & Internal Architecture

#### 3.1 XCUITest Runtime Daemon & Inter-Process Communication (IPC)
Pengujian UI pada iOS tidak berjalan langsung di dalam proses aplikasi target. Pengujian UI berjalan di proses terpisah yang diinjeksi oleh daemon sistem operasi.

```
+-----------------------------------------------------------------------+
|                            macOS / Runner                             |
|                                                                       |
|  +--------------------+                   +------------------------+  |
|  |   Test Runner      |                   |    Target Application  |  |
|  |  (YourTest.xctest) |                   |      (App Process)     |  |
|  +---------+----------+                   +-----------+------------+  |
|            |                                          |               |
|            | Mach Messages / XPC                      | Accessibility |
|            |                                          | Runtime Hooks |
|            v                                          v               |
|  +-----------------------------------------------------------------+  |
|  |                     testmanagerd (Daemon)                       |  |
|  |  - Directs synthesized input events (Touch, Tap, Keystrokes)    |  |
|  |  - Queries Accessibility Hierarchy via AXRuntime               |  |
|  |  - Synchronizes RunLoop & Animation States                      |  |
|  +-----------------------------------------------------------------+  |
+-----------------------------------------------------------------------+
```

1. **Test Runner Process**: Menjalankan *test bundle*. Runner berkomunikasi dengan `testmanagerd` melalui IPC (*Inter-Process Communication*) berbasis XPC.
2. **`testmanagerd`**: Daemon pengujian tingkat sistem yang memiliki hak akses (*entitlements*) istimewa untuk menyintesis interaksi perangkat keras (sentuhan, rotasi, masukan teks).
3. **Target Process (App)**: Membuka representasi struktur pohon aksesibilitas (*AX UI Tree*) ke `testmanagerd`. Ketika aplikasi mengubah UI, subsistem `AXRuntime` memicu pembaruan pohon aksesibilitas yang kemudian dibaca oleh `XCUIApplication`.

#### 3.2 URLProtocol Interception Pipeline
Untuk pengujian integrasi jaringan tanpa server (*hermetic integration testing*), pendekatan terbaik pada tingkat Foundation adalah memanfaatkan `URLProtocol`.

```
[ DataTask via URLSession ]
             │
             ▼
[ URLSessionConfiguration.protocolClasses ]
             │
   ┌─────────┴─────────┐
   ▼                   ▼
[ CustomURLProtocol ] [ Native Protocols: HTTP, HTTPS, etc. ]
   │
   ├─ canInit(with:) == true?
   │        │
   │        ├─► startLoading() ──► Intercept & Inject Stubbed Data / Error
   │        │                         │
   │        │                         └─► URLProtocolClient (Notify URLSession)
   │        │
   │        └─► Stop pipeline traversal
   │
   └─ canInit(with:) == false?
            │
            └─► Fallback to next protocol in chain (System Network Stack)
```

`URLSession` mengevaluasi koleksi `protocolClasses` secara sekuensial. Saat mengembalikan `true` pada fungsi `canInit(with:)`, *runtime* menghentikan propagasi *downstream* dan menyerahkan kendali penanganan koneksi sepenuhnya kepada implementasi `URLProtocol` kustom tersebut. Hal ini memungkinkan simulasi latensi, korupsi payload, *packet drops*, dan status kode HTTP spesifik secara terisolasi tanpa ketergantungan koneksi internet.

#### 3.3 Snapshot Testing Core Mechanics
*Snapshot Testing* memvalidasi kesesuaian visual antarmuka pengguna terhadap artefak referensi (*golden images*).
1. Komponen antarmuka (`UIView` atau `View` SwiftUI yang dibungkus `UIHostingController`) dipaksa melakukan *layout pass* dan *render pass* secara *offscreen*.
2. Konteks grafis mengalokasikan *framebuffer* memori menggunakan `UIGraphicsImageRenderer` yang membaca representasi layer visual (`CALayer.render(in:)`).
3. Gambar yang dihasilkan diubah ke representasi biner (format PNG tanpa kompresi *lossy*).
4. Pengujian membandingkan *byte-array* atau melakukan perbandingan piksel-demi-piksel (*pixel-by-pixel diffing*) dengan toleransi deviasi warna (misalnya toleransi RMSD < 1%) terhadap file referensi yang tersimpan di repositori.

#### 3.4 Swift Concurrency Isolation dalam XCTest
Sebelum Swift 6, banyak *test suite* mengalami *flakiness* akibat manipulasi state asinkronus yang tidak aman. Pada Swift 6:
- `XCTestCase` secara default tidak terisolasi ke *actor* tertentu kecuali ditandai secara eksplisit dengan `@MainActor`.
- UI Testing dan pengujian komponen UI (SwiftUI Views, ViewControllers) **wajib** diisolasi ke `@MainActor`.
- Pengujian asinkronus harus menunggu kondisi selesai melalui *structured concurrency* (`await`, `withCheckedContinuation`, `AsyncStream`) daripada menggunakan pemblokiran *runloop* manual berbasis `wait(for:timeout:)` yang rentan terhadap *priority inversion* dan *deadlock*.

---

### 4. Why & What

| Dimensi Pengujian | Pendekatan Naif / Tradisional | Pendekatan Enterprise Modern |
| :--- | :--- | :--- |
| **Integrasi Jaringan** | Menggunakan server *staging* riil atau memalsukan *repository class* (*shallow mocking*). | Intersepsi *network layer* via `URLProtocol` / *Hermetic Local Mock Server*. |
| **Validasi UI** | Memeriksa teks secara manual menggunakan *assertion* string satu-per-satu. | Otomasi *Snapshot Testing* visual lintas resolusi layar, mode gelap, dan *Dynamic Type*. |
| **Evaluasi Performa** | Stopwatch manual, pengukuran subjektif, atau pengujian *ad-hoc* di *development device*. | Otomasi `XCTMetric` (*regression gate* di CI) untuk mengukur Alokasi Memori, CPU, dan *Launch Time*. |
| **Eksekusi Concurrency** | `sleep()` sembarangan dan `XCTestExpectation` manual dengan timeout panjang. | *Strict Actor Isolation*, *deterministic continuation assertion*, dan *Virtual Clock scheduling*. |
| **Skalabilitas CI** | Satu alur sekuensial; memakan waktu 1–2 jam per eksekusi *pull request*. | *Test sharding*, *parallel simulator testing*, seleksi uji pintar (*Impact Analysis*). |

---

### 5. How (Workflow Detail)

Alur kerja pengujian komprehensif tingkat produksi dirancang melalui *tiered pipeline*:

```
+-------------------------------------------------------------------------------+
|                       L1: Fast Local Feedback Loop                            |
| Unit Tests + Isolation Mocks (< 60 detik)                                     |
+---------------------------------------+---------------------------------------+
                                        │ PASS
                                        v
+-------------------------------------------------------------------------------+
|                       L2: Visual & Hermetic Integration                       |
| Snapshot Tests + Integration via URLProtocol (< 5 menit)                      |
+---------------------------------------+---------------------------------------+
                                        │ PASS
                                        v
+-------------------------------------------------------------------------------+
|                       L3: Automation & Performance Gate                       |
| Mocked End-to-End XCUITest + XCTMetric Regression Check (< 15 menit)          |
+---------------------------------------+---------------------------------------+
                                        │ PASS
                                        v
+-------------------------------------------------------------------------------+
|                       L4: CI Parallel Distribution                            |
| Matrix Test Sharding via Fastlane & Xcodebuild (Paralel di 4-8 Node)         |
+-------------------------------------------------------------------------------+
```

1. **Fase Hermetisisme Jaringan**: Konfigurasi injeksi dependensi memastikan instance `URLSessionConfiguration` aplikasi dapat menerima `protocolClasses` pengujian tanpa modifikasi logika bisnis produksi.
2. **Fase Visual Regression**: Komponen UI diuji dengan variasi ukuran layar (iPhone SE, iPhone 16 Pro Max, iPad Pro), variasi tema (Light/Dark Mode), dan aksesibilitas (Accessibility Extra Extra Large Font).
3. **Fase Metrik Performa**: Eksekusi pengujian performa memanfaatkan *baseline artifact*. Jika alokasi memori naik > 10% atau waktu peluncuran aplikasi (*Time-to-Interactive*) terdegradasi melebihi *threshold*, proses integrasi CI digagalkan (*fail build*).
4. **Fase Distribusi Paralel**: Menggunakan `xcodebuild -parallel-testing-enabled YES` atau melakukan *sharding* skenario pengujian ke beberapa mesin virtual CI menggunakan skrip orkestrasi.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Terowongan Angin Industri Dirgantara
Menguji aplikasi enterprise di lingkungan produksi nyata ibarat menerbangkan prototipe pesawat komersial langsung ke badai topan nyata untuk mengukur ketahanan aerodinamika. Risikonya sangat fatal: server *staging* bisa *down*, data pihak ketiga tidak stabil, dan biaya kegagalan sangat tinggi. 

Arsitektur pengujian tingkat lanjut adalah **terowongan angin tertutup (*wind tunnel*) terkomputerisasi**:
- Kita mensimulasikan hembusan angin dan tekanan udara secara deterministik (`URLProtocol`).
- Kita merekam stabilitas struktur sayap secara mikroskopis melalui sensor berkecepatan tinggi (`XCTMetric`).
- Kita mengambil foto presisi tinggi di setiap milidetik untuk memastikan tidak ada deformasi bentuk fisik komponen (`Snapshot Testing`).
- Seluruh simulasi dijalankan berkali-kali secara identik di fasilitas uji paralel tanpa pernah membakar bahan bakar jet sungguhan.

---

### 7. Implementation: Simple vs Enterprise Practical Example

#### 7.1 Simple Example: Mocking via URLProtocol Sederhana
Contoh dasar intersepsi jaringan menggunakan subkelas `URLProtocol`.

```swift
import Foundation
import XCTest

public final class MockURLProtocol: URLProtocol {
    public static var stubHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    public override class func canInit(with request: URLRequest) -> Bool {
        return true // Intersep semua request
    }

    public override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }

    public override func startLoading() {
        guard let handler = MockURLProtocol.stubHandler else {
            XCTFail("Stub handler belum dikonfigurasi.")
            return
        }

        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    public override func stopLoading() {}
}
```

---

#### 7.2 Practical Enterprise Example: Robust Network Stubbing & UI Performance Testing

Berikut adalah arsitektur pengujian jaringan tingkat lanjut yang *thread-safe*, modular, dan deterministik, dipadukan dengan pengujian metrik performa sistem menggunakan modern Swift Concurrency.

##### Bagian A: Thread-Safe HTTP Interception Engine
```swift
import Foundation
import XCTest

public struct HTTPStubResponse: Sendable {
    public let statusCode: Int
    public let headers: [String: String]
    public let body: Data
    public let simulatedDelay: Duration

    public init(
        statusCode: Int = 200,
        headers: [String: String] = ["Content-Type": "application/json"],
        body: Data,
        simulatedDelay: Duration = .zero
    ) {
        self.statusCode = statusCode
        self.headers = headers
        self.body = body
        self.simulatedDelay = simulatedDelay
    }
}

public final class EnterpriseNetworkInterceptor: URLProtocol, @unchecked Sendable {
    private static let lock = NSLock()
    private static var registry: [URL: HTTPStubResponse] = [:]

    public static func register(response: HTTPStubResponse, for url: URL) {
        lock.lock()
        defer { lock.unlock() }
        registry[url] = response
    }

    public static func reset() {
        lock.lock()
        defer { lock.unlock() }
        registry.removeAll()
    }

    private static func findStub(for url: URL?) -> HTTPStubResponse? {
        guard let url = url else { return nil }
        lock.lock()
        defer { lock.unlock() }
        return registry[url]
    }

    public override class func canInit(with request: URLRequest) -> Bool {
        return findStub(for: request.url) != nil
    }

    public override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        return request
    }

    public override func startLoading() {
        guard let url = request.url, let stub = Self.findStub(for: url) else {
            client?.urlProtocol(self, didFailWithError: URLError(.unsupportedURL))
            return
        }

        Task {
            if stub.simulatedDelay > .zero {
                try? await Task.sleep(for: stub.simulatedDelay)
            }

            guard let response = HTTPURLResponse(
                url: url,
                statusCode: stub.statusCode,
                httpVersion: "HTTP/1.1",
                headerFields: stub.headers
            ) else {
                client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
                return
            }

            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: stub.body)
            client?.urlProtocolDidFinishLoading(self)
        }
    }

    public override func stopLoading() {}
}
```

##### Bagian B: Session Factory untuk Pengujian & Produksi
```swift
public protocol URLSessionConfigurationFactoryProtocol: Sendable {
    func makeConfiguration() -> URLSessionConfiguration
}

public struct ProductionSessionConfigurationFactory: URLSessionConfigurationFactoryProtocol {
    public init() {}
    public func makeConfiguration() -> URLSessionConfiguration {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30.0
        return config
    }
}

public struct HermeticTestSessionConfigurationFactory: URLSessionConfigurationFactoryProtocol {
    public init() {}
    public func makeConfiguration() -> URLSessionConfiguration {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [EnterpriseNetworkInterceptor.self]
        return config
    }
}
```

##### Bagian C: XCTMetric-Based Performance Test Case
Pengujian performa peluncuran modul transaksi perbankan dan alokasi memori secara ketat di bawah isolasi `@MainActor`.

```swift
import XCTest

@MainActor
final class PortfolioPerformanceRegressionTests: XCTestCase {
    private var sutSession: URLSession!
    private let targetEndpoint = URL(string: "https://api.enterprise-bank.internal/v1/portfolio")!

    override func setUpWithError() throws {
        try super.setUpWithError()
        EnterpriseNetworkInterceptor.reset()

        let configFactory = HermeticTestSessionConfigurationFactory()
        sutSession = URLSession(configuration: configFactory.makeConfiguration())
    }

    override func tearDownWithError() throws {
        EnterpriseNetworkInterceptor.reset()
        sutSession = nil
        try super.tearDownWithError()
    }

    func test_portfolioDataProcessing_resourceConsumptionBaseline() throws {
        // Mock payload besar berukuran 5MB JSON
        let largePayload = """
        {
            "transactions": \(Array(repeating: "{\"id\":\"tx-9821\",\"amount\":1250.50,\"currency\":\"USD\"}", count: 25000).joined(separator: ","))
        }
        """.data(using: .utf8)!

        EnterpriseNetworkInterceptor.register(
            response: HTTPStubResponse(statusCode: 200, body: largePayload),
            for: targetEndpoint
        )

        let options = XCTMeasureOptions()
        options.iterationCount = 5

        // Mengukur Memory Allocation dan Clock Time secara simultan
        measure(metrics: [XCTMemoryMetric(), XCTClockMetric(), XCTCPUMetric()], options: options) {
            let expectation = self.expectation(description: "Download and parse payload")

            Task {
                let (data, response) = try await self.sutSession.data(from: self.targetEndpoint)
                XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)

                // Parsing stress test
                let json = try JSONSerialization.jsonObject(with: data, options: [])
                XCTAssertNotNil(json)
                expectation.fulfill()
            }

            self.wait(for: [expectation], timeout: 10.0)
        }
    }
}
```

##### Bagian D: Framework Snapshot Testing Komponen UI Lintas Trait
Implementasi snapshot sederhana tanpa dependensi luar yang menangani konfigurasi multi-trait (Light/Dark Mode, Dynamic Type) untuk SwiftUI View.

```swift
import SwiftUI
import XCTest

@MainActor
public final class EnterpriseSnapshotRenderer {
    public struct Configuration {
        public let size: CGSize
        public let userInterfaceStyle: UIUserInterfaceStyle
        public let contentSizeCategory: UIContentSizeCategory

        public static let iPhone16ProPortrait = Configuration(
            size: CGSize(width: 393, height: 852),
            userInterfaceStyle: .unspecified,
            contentSizeCategory: .large
        )
    }

    public static func render<Content: View>(
        view: Content,
        configuration: Configuration
    ) -> UIImage {
        let hostingController = UIHostingController(rootView: view)
        let targetSize = configuration.size

        hostingController.view.bounds = CGRect(origin: .zero, size: targetSize)
        hostingController.overrideUserInterfaceStyle = configuration.userInterfaceStyle

        let traits = UITraitCollection(traitsFrom: [
            UITraitCollection(userInterfaceStyle: configuration.userInterfaceStyle),
            UITraitCollection(preferredContentSizeCategory: configuration.contentSizeCategory)
        ])
        
        let format = UIGraphicsImageRendererFormat(for: traits)
        format.scale = 3.0 // Retina 3x precision

        let window = UIWindow(frame: CGRect(origin: .zero, size: targetSize))
        window.rootViewController = hostingController
        window.makeKeyAndVisible()
        hostingController.view.setNeedsLayout()
        hostingController.view.layoutIfNeeded()

        let renderer = UIGraphicsImageRenderer(size: targetSize, format: format)
        return renderer.image { _ in
            hostingController.view.drawHierarchy(in: CGRect(origin: .zero, size: targetSize), afterScreenUpdates: true)
        }
    }

    public static func compare(
        newImage: UIImage,
        goldenImage: UIImage,
        tolerancePercentage: Double = 0.005
    ) -> Bool {
        guard let newCGImage = newImage.cgImage,
              let goldenCGImage = goldenImage.cgImage,
              newCGImage.width == goldenCGImage.width,
              newCGImage.height == goldenCGImage.height else {
            return false
        }

        let width = newCGImage.width
        let height = newCGImage.height
        let bytesPerPixel = 4
        let bytesPerRow = width * bytesPerPixel
        let totalBytes = height * bytesPerRow

        var newBytes = [UInt8](repeating: 0, count: totalBytes)
        var goldenBytes = [UInt8](repeating: 0, count: totalBytes)

        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let bitmapInfo = CGImageAlphaInfo.premultipliedLast.rawValue

        guard let contextNew = CGBitmapContextCreate(&newBytes, width, height, 8, bytesPerRow, colorSpace, bitmapInfo),
              let contextGolden = CGBitmapContextCreate(&goldenBytes, width, height, 8, bytesPerRow, colorSpace, bitmapInfo) else {
            return false
        }

        contextNew.draw(newCGImage, in: CGRect(x: 0, y: 0, width: width, height: height))
        contextGolden.draw(goldenCGImage, in: CGRect(x: 0, y: 0, width: width, height: height))

        var diffPixelCount = 0
        let totalPixels = width * height

        for i in stride(from: 0, to: totalBytes, by: bytesPerPixel) {
            let rDiff = abs(Int(newBytes[i]) - Int(goldenBytes[i]))
            let gDiff = abs(Int(newBytes[i + 1]) - Int(goldenBytes[i + 1]))
            let bDiff = abs(Int(newBytes[i + 2]) - Int(goldenBytes[i + 2]))
            let aDiff = abs(Int(newBytes[i + 3]) - Int(goldenBytes[i + 3]))

            if (rDiff + gDiff + bDiff + aDiff) > 0 {
                diffPixelCount += 1
            }
        }

        let diffRatio = Double(diffPixelCount) / Double(totalPixels)
        return diffRatio <= tolerancePercentage
    }
}
```

---

### 8. Real World Case Study: Aplikasi Transaksi Finansial Skala Besar

#### Konteks Masalah
Sebuah institusi perbankan digital memiliki aplikasi monolit modular dengan lebih dari 250 modul internal (SPM). CI/CD membutuhkan waktu **95 menit** untuk menjalankan seluruh test suite (unit, integrasi, snapshot, dan UI tests). 

Tingkat kegagalan *flakiness* mencapai **18%**, di mana build CI sering gagal bukan karena adanya *bug* kode aktual, melainkan karena:
1. Server staging lambat atau mengalami *timeout* saat pengujian integrasi UI.
2. Perubahan kecil pada antarmuka menyebabkan *snapshot mismatch* karena *font rendering sub-pixel* yang berbeda antara mesin lokal pengembang (M1/M2) dan agen CI berbasis x86 Intel.
3. *Data races* sporadis dalam pengujian asinkronus yang memanfaatkan `XCTestExpectation` global yang tidak terisolasi.

#### Desain Solusi Rekayasa
1. **Network Hermeticism**: Mengganti semua pemanggilan jaringan luar pada level integrasi dan UI test dengan `URLProtocol` mock orchestration engine. Seluruh status respons HTTP, payload biner, dan kegagalan jaringan diinjeksikan secara terisolasi tanpa mengakses internet.
2. **Deterministic UI Container & OS Standardization**: Menstandarisasi agen pelari CI ke arsitektur Apple Silicon seragam (`macos-14-arm64`), mengunci resolusi layar, mematikan animasi (`UIView.setAnimationsEnabled(false)`), dan menetapkan aturan toleransi *anti-aliasing* *snapshot* sebesar 0.8% RMSD.
3. **Targeted Test Sharding**: Memecah rangkaian pengujian secara terprogram menjadi 8 *bucket* mandiri yang dijalankan secara bersamaan pada *node* CI terpisah memanfaatkan Fastlane dan `xcodebuild -only-testing`.
4. **Swift Concurrency Enforced Gate**: Menghapus seluruh penggunaan `sleep()` dan beralih ke pola pengujian terstruktur (`await Task.yield()`, custom `AsyncChannel`, serta `@MainActor` binding).

```
[ Git Push / PR Opened ]
            │
            ├─► [ Matrix Pipeline Runner Engine ]
            │       │
            │       ├─► Node 1: Unit Tests (Shard 1/4)
            │       ├─► Node 2: Unit Tests (Shard 2/4)
            │       ├─► Node 3: Unit Tests (Shard 3/4)
            │       ├─► Node 4: Unit Tests (Shard 4/4)
            │       ├─► Node 5: Snapshot & AX Validation
            │       ├─► Node 6: Hermetic UI Flows (Core Bank)
            │       ├─► Node 7: Hermetic UI Flows (Invest & Cards)
            │       └─► Node 8: XCTMetric Performance Regressions
            │
            ▼
[ Result Aggregator: XCFramework Coverage Report + Pass/Fail Gate ] (Durasi: 11 Menit)
```

#### Hasil Terukur (Metrics & Business Value)
- **CI Execution Time**: Turun dari **95 menit** menjadi **11 menit** (efisiensi ~88.4%).
- **Flakiness Rate**: Berkurang drastis dari **18%** menjadi **0.05%**.
- **Regresi Terditeksi Pra-Rilis**: Berhasil mengidentifikasi regresi alokasi memori (*memory leak* CoreAnimation) pada tahap PR sebelum merger ke branch `main`.

---

### 9. Trade-offs Architecture Matrix

| Strategi / Pilihan | Keuntungan Utama | Kerugian / Biaya | Konteks Optimal Penggunaan |
| :--- | :--- | :--- | :--- |
| **URLProtocol Mocking** | Zero code change di arsitektur produksi; deterministic; super cepat. | Sulit mensimulasikan *stateful socket connection* kompleks seperti WebSocket. | Pengujian integrasi REST/gRPC-Web dan simulasi skenario *bad network*. |
| **Local Mock Server (Localhost HTTP)** | Menguji networking stack sesungguhnya dari OS hingga socket TCP. | Overhead I/O lokal; butuh port management dinamis agar tidak *conflict*. | Validasi Certificate Pinning, HTTP/3, atau TLS handshake integrity. |
| **Snapshot Testing (Golden Image)** | Mendeteksi regresi layout visual mikroskopis, font clipping, dan constraint error. | Memperbesar ukuran repositori Git; sangat sensitif terhadap OS minor version update. | Design System components, Screen template, Billing Statements. |
| **XCTMetric Profiling** | Otomasi pendeteksian regresi performa, CPU throttling, dan memory leak di CI. | Eksekusi membutuhkan iterasi berulang (`iterationCount >= 5`); memakan waktu relatif lama. | Core critical paths (App Launch, Payment Checkout, List Scrolling). |
| **UI Automation (XCUITest)** | Menguji integrasi end-to-end secara faktual melalui *Accessibility Tree*. | Waktu eksekusi lambat, biaya komputasi CI tinggi, pemeliharaan kode tinggi. | Smoke test skenario bisnis paling krusial (*Happy Paths*). |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Anti-Pattern: Menggunakan `sleep(seconds)` untuk Menunggu Operasi Asinkronus
- **Gejala**: Pengujian UI atau asinkronus sering gagal secara acak saat agen CI mengalami beban CPU tinggi (*resource contention*).
- **Akar Masalah**: `sleep()` membekukan *thread* tanpa sinkronisasi dengan *event loop* aplikasi atau penyelesaian *Task* asinkronus.
- **Solusi**: Gunakan `fulfillment(of:timeout:)` dengan `XCTestExpectation` atau gunakan *polling deterministic predicate*:

```swift
// BURUK
func testBadAsyncFetch() async throws {
    viewModel.loadData()
    sleep(3) // Flaky!
    XCTAssertTrue(viewModel.isLoaded)
}

// BENAR (Modern Swift Concurrency)
func testGoodAsyncFetch() async throws {
    await viewModel.loadData() // Asynchronous call natively awaited
    XCTAssertTrue(viewModel.isLoaded)
}
```

#### 10.2 Anti-Pattern: Leakage State Global pada `URLProtocol`
- **Gejala**: Pengujian B gagal secara misterius hanya ketika dijalankan setelah Pengujian A.
- **Akar Masalah**: Pendaftaran stub pada `URLProtocol` menggunakan variabel statis tanpa pembersihan (*cleanup*) menyeluruh di `tearDown()`.
- **Solusi**: Bersihkan registry secara mutlak di `tearDownWithError()` dan gunakan instansiasi `URLSessionConfiguration` yang bersih (`ephemeral`).

#### 10.3 Troubleshooting Flaky Snapshot Rendering pada Simulators
- **Gejala**: Gambar snapshot lokal (macOS host) berbeda beberapa *byte* dibandingkan gambar yang di-generate pada mesin Linux atau mesin agen CI.
- **Penyebab**: Perbedaan *color profile* (sRGB vs Display P3) atau versi simulator runtime iOS (misal: iOS 17.2 vs iOS 17.4 mengubah sub-pixel layout font San Francisco).
- **Protokol Diagnosa**:
  1. Jalankan `xcrun simctl list devices` di agen CI untuk memastikan simulator model dan build OS persis identik.
  2. Paksa *color space* rendering ke standar sRGB saat menginisialisasi `CGBitmapContext`.
  3. Tetapkan toleransi *perceptual difference* minimal (misal `0.5% - 1%`) untuk mengakomodasi variasi rasterisasi GPU.

---

### 11. Best Practices & Production Checklist

- [ ] **Gunakan Ephemeral Session untuk Testing**: Hindari penggunaan `URLSession.shared` pada kode aplikasi agar dependensi konfigurasi dapat diinjeksi (*dependency injection*).
- [ ] **Isolasi Concurrency Total**: Tandai test case yang menguji View atau ViewModel dengan `@MainActor`. Aktifkan build setting `Strict Concurrency Checking = Complete`.
- [ ] **Disable Simulators Animations**: Tambahkan argumen peluncuran skema pengujian atau panggil `UIView.setAnimationsEnabled(false)` saat bootstrapping test suite UI untuk memangkas *render wait time*.
- [ ] **Golden Image Storage Management**: Gunakan Git LFS (*Large File Storage*) atau hosting artefak eksternal untuk menyimpan gambar snapshot guna mencegah pembengkakan (*bloat*) ukuran repositori Git.
- [ ] **Deterministic UUID & Date Providers**: Abstraksikan pemanggilan `UUID()` dan `Date()` menggunakan protocol terinjeksi agar data pengujian tidak berubah-ubah di setiap eksekusi.
- [ ] **Fail Fast di CI Pipeline**: Susun pengujian berjenjang: Unit Testing (cepat) -> Snapshot Testing (menengah) -> UI & Metric Testing (berat). Gagalkan pipeline segera (*fail-fast*) pada tahap paling awal.
- [ ] **Baseline Locking untuk XCTMetric**: Catat dan perbarui *Performance Baseline* hanya pada mesin target standar CI, bukan pada laptop pengembang dengan variasi spesifikasi hardware.

---

### 12. Hands-on Practice

Buat dan simpan struktur pengujian komprehensif berikut di direktori direktori modul: `hands-on/m02/`.

#### Struktur Berkas
```text
hands-on/m02/
├── Package.swift
├── Sources/
│   └── BankingCore/
│       ├── AccountService.swift
│       ├── TransactionModel.swift
│       └── TransactionView.swift
└── Tests/
    └── BankingCoreTests/
        ├── Helpers/
        │   ├── EnterpriseNetworkInterceptor.swift
        │   └── SnapshotTestUtility.swift
        ├── IntegrationTests/
        │   └── AccountServiceIntegrationTests.swift
        ├── PerformanceTests/
        │   └── TransactionRenderingPerformanceTests.swift
        └── SnapshotTests/
            └── TransactionViewSnapshotTests.swift
```

#### Langkah-langkah Implementasi

1. **Inisialisasi Package**:
   ```bash
   mkdir -p hands-on/m02 && cd hands-on/m02
   swift package init --type library --name BankingCore
   ```

2. **Perbarui `Package.swift`**:
   Pastikan mendukung platform iOS v16+ atau macOS v13+ dan konfigurasi Swift 5.10 / 6.
   ```swift
   // swift-tools-version: 5.10
   import PackageDescription

   let package = Package(
       name: "BankingCore",
       platforms: [.iOS(.v16), .macOS(.v13)],
       products: [
           .library(name: "BankingCore", targets: ["BankingCore"]),
       ],
       targets: [
           .target(name: "BankingCore"),
           .testTarget(
               name: "BankingCoreTests",
               dependencies: ["BankingCore"]
           ),
       ]
   )
   ```

3. **Tulis Domain Model & Service di `Sources/BankingCore/AccountService.swift`**:
   Implementasikan `AccountService` yang menerima `URLSessionConfigurationFactoryProtocol` secara terinjeksi.

4. **Tulis Integration Test di `Tests/BankingCoreTests/IntegrationTests/AccountServiceIntegrationTests.swift`**:
   Uji skenario:
   - Respon sukses HTTP 200 dengan payload JSON.
   - Respon error HTTP 500 Internal Server Error.
   - Respon lambat dengan `simulatedDelay` untuk memverifikasi timeout handling.

5. **Jalankan Test via CLI**:
   ```bash
   swift test --parallel
   ```

---

### 13. Exercise

#### 13.1 Level: Easy
Buat unit test asinkronus menggunakan Swift Concurrency untuk fungsi `TransactionProcessor.calculateBalance(transactions:)`. Fungsi ini berjalan secara asinkronus dan mengembalikan nilai akumulasi balance. Pengujian harus memastikan *empty transaction list* mengembalikan balance 0.0 tanpa *flakiness*.

#### 13.2 Level: Medium
Implementasikan skenario *chaos engineering* pada `EnterpriseNetworkInterceptor`. Tambahkan kemampuan simulasi *network drop* (koneksi terputus di tengah transmisi data) dengan memanggil `client?.urlProtocol(self, didFailWithError: URLError(.networkConnectionLost))` setelah mengirimkan separuh dari total *byte buffer*. Tulis integrasi pengujian untuk membuktikan bahwa lapisan *Repository* melakukan *retry policy* maksimal 3 kali sebelum akhirnya melempar error.

#### 13.3 Level: Hard
Bangun implementasi `XCTestCase` yang mengukur alokasi memori (`XCTMemoryMetric`) saat merender `LazyVStack` berisi 50.000 item riwayat mutasi rekening. Pengujian harus memverifikasi bahwa pengguliran (*scrolling*) virtualisasi list tidak menyebabkan *unbounded memory growth* (kebocoran memori), dengan assertion bahwa kenaikan memori dari iterasi ke-1 hingga iterasi ke-10 tidak boleh melebihi ambang batas 15 megabyte.

---

### 14. Challenge: Enterprise-Scale Architecture Case

#### Skenario Kasus
Aplikasi Super-App Perbankan Anda memiliki fitur verifikasi biometrik yang terhubung ke modul otentikasi transaksi tinggi. Modul ini memiliki dependensi rumit:
1. Panggilan jaringan terenkripsi dua arah (mutual TLS simulation).
2. Penyimpanan lokal berbasis SwiftData/CoreData yang melakukan sinkronisasi *background context*.
3. Antarmuka UI yang sensitif terhadap *Dynamic Type* (Aksesibilitas bagi tunanetra).

#### Tantangan Arsitektur
Rancang sebuah rangkaian pengujian komprehensif (`Harness Architecture`) tanpa modifikasi kode produksi yang mampu:
- Menguji alur otentikasi gagal sebanyak 3 kali -> memicu *lockout state* di CoreData -> mengupdate antarmuka visual ke mode darurat (*warning alert*).
- Menjamin bahwa pengujian berjalan 100% deterministik tanpa memunculkan prompt biometrik sistem (`LAContext`) sungguhan.
- Menangkap *Snapshot* tampilan antarmuka secara otomatis pada status *lockout* dalam 3 konfigurasi aksesibilitas ekstrem (Extra Large, Extra Extra Large, Accessibility XXXL).
- Menjalankan seluruh pengujian tersebut dalam lingkungan *isolated background thread* yang memvalidasi bahwa tidak ada kebocoran operasi antarmuka di luar `@MainActor`.

*Instruksi: Susun arsitektur mock injection, protocols abstraction, dan harness test class secara lengkap.*

---

### 15. Quiz Evaluasi Pemahaman

#### 15.1 Bagian 1: Basic Concept (5 Soal)
1. **Mengapa `XCTestCase` secara default tidak terisolasi ke `@MainActor` pada Swift Concurrency?**
   - A. Karena XCTest tidak mendukung Swift Concurrency.
   - B. Agar pengujian dapat mengeksekusi operasi background secara efisien tanpa membebani antarmuka pengguna secara default.
   - C. Karena XCTest berjalan di proses macOS yang berbeda.
   - D. Ini adalah bug sementara pada compiler Xcode.

2. **Apa fungsi utama dari method `canInit(with request: URLRequest)` pada `URLProtocol`?**
   - A. Memulai download task secara instan.
   - B. Menentukan apakah subkelas protokol tersebut bersedia dan mampu menangani request yang diberikan.
   - C. Mengonversi URLRequest menjadi URLResponse.
   - D. Menghapus cache jaringan sebelum request dieksekusi.

3. **Apa bahaya utama menggunakan fungsi `sleep(UInt32)` di dalam unit test iOS?**
   - A. Mengakibatkan CPU thermal throttling secara permanen.
   - B. Memblokir eksekusi thread saat ini secara non-deterministik dan menyebabkan *test flakiness* di CI.
   - C. Menghentikan proses kompilasi Swift.
   - D. Membatalkan sertifikasi Apple Developer Program.

4. **Metrik mana di bawah ini yang disediakan oleh `XCTMetric` untuk mengukur durasi waktu eksekusi riil?**
   - A. `XCTCPUMetric`
   - B. `XCTMemoryMetric`
   - C. `XCTClockMetric`
   - D. `XCTStorageMetric`

5. **Apa format representasi gambar yang ideal digunakan sebagai *baseline reference* pada Snapshot Testing visual antarmuka?**
   - A. JPEG dengan kompresi 80%
   - B. Lossless PNG
   - C. GIF beresolusi rendah
   - D. HEIC dengan dynamic bit rate

#### 15.2 Bagian 2: Intermediate Concept (5 Soal)
6. **Bagaimana cara yang benar untuk mencegah `URLProtocol` mengalami *infinite recursion* saat memproses request yang diteruskan?**
   - A. Memanggil `fatalError()` di dalam method `startLoading()`.
   - B. Menandai request yang sudah diproses dengan atribut kustom menggunakan `URLProtocol.setProperty(_:forKey:in:)`.
   - C. Membuat subclass baru untuk setiap request.
   - D. Mengubah domain name URL target menjadi localhost.

7. **Mengapa kita harus menyetel `UIView.setAnimationsEnabled(false)` saat menjalankan automated UI Tests di CI?**
   - A. Agar tampilan UI menjadi hitam-putih.
   - B. Untuk menghilangkan delay durasi animasi sehingga assertions dapat dievaluasi langsung tanpa menunggu transition selesai.
   - C. Untuk menghemat alokasi memori GPU simulator hingga 90%.
   - D. Karena UIKit tidak mendukung animasi di simulator.

8. **Apa perbedaan mendasar antara `URLSessionConfiguration.default` dan `URLSessionConfiguration.ephemeral` dalam konteks testing?**
   - A. `default` tidak mendukung HTTP method POST.
   - B. `ephemeral` tidak menyimpan cookies, caches, atau credential data ke disk penyimpanan permanen.
   - C. `ephemeral` memiliki timeout default 1 detik.
   - D. `default` otomatis mematikan dukungan TLS.

9. **Ketika melakukan Snapshot Testing pada view SwiftUI yang memanfaatkan UIKit traits, mengapa kita perlu memanggil `setNeedsLayout()` dan `layoutIfNeeded()`?**
   - A. Untuk mereset background color view ke transparan.
   - B. Untuk memaksa siklus *layout engine* menghitung ulang ukuran frame dan posisi hierarki subview sebelum dirender ke grafik konteks.
   - C. Untuk membersihkan cache CoreGraphics.
   - D. Untuk menghubungkan view ke sistem window server macOS host.

10. **Apa implikasi menyetel parameter `options.iterationCount = 10` pada fungsi `measure(metrics:options:block:)`?**
    - A. Test runner akan menjalankan blok uji sebanyak 10 kali untuk mengumpulkan data sampel statistik rata-rata dan deviasi standar.
    - B. Test runner akan membuat 10 simulator secara paralel.
    - C. Memory allocated akan dikalikan 10 secara sintetis.
    - D. Timeout otomatis dinaikkan menjadi 10 menit.

#### 15.3 Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Skenario Kasus 1**:
    Tim Anda menemukan bahwa Snapshot Testing untuk modul Checkout selalu *pass* di mesin lokal pengembang (M3 Max, macOS 14.4), namun selalu gagal dengan deviasi pixel 2.1% pada mesin GitHub Actions runner (`macos-13` Intel). Setelah diteliti, teks label harga terpotong (*truncated*) sebesar 1 pixel di CI.
    **Apa akar masalah paling potensial dan langkah korektif enterprise yang tepat?**
    - A. Intel CPU tidak mendukung aritmatika Floating Point secara presisi; ubah semua tipe data ke Integer.
    - B. Terdapat perbedaan versi rendering antarmuka CoreText/Font Engine antar versi mayor OS host simulator; standarisasi image runner CI ke macOS dan versi runtime iOS simulator yang identik dengan mesin lokal.
    - C. Snapshot testing dilarang dijalankan pada arsitektur CI berbasis Cloud; nonaktifkan test tersebut di GitHub Actions.
    - D. Memory RAM CI terlalu kecil; tambahkan swap space memori pada runner.

12. **Skenario Kasus 2**:
    Sebuah pengujian asinkronus yang memvalidasi WebSocket listener mengalami *deadlock* dan timeout setelah beralih ke Swift 6 language mode. Kode pengujian ditulis sebagai berikut:
    ```swift
    func testWebSocketReceive() {
        let expectation = expectation(description: "Receive")
        Task {
            let message = await socketClient.receiveNext()
            XCTAssertNotNil(message)
            expectation.fulfill()
        }
        waitForExpectations(timeout: 5.0)
    }
    ```
    **Mengapa deadlock ini terjadi dan bagaimana perbaikan asinkronus yang benar?**
    - A. `waitForExpectations` memblokir main runloop sinkronus secara total sehingga cooperative thread pool kehabisan slot thread untuk melanjutkan task; ganti method pengujian menjadi `func testWebSocketReceive() async throws` dan gunakan `await socketClient.receiveNext()` secara langsung.
    - B. `Task` tidak diizinkan di dalam unit testing iOS.
    - C. Parameter timeout 5.0 terlalu pendek; naikkan timeout ke 60.0 detik.
    - D. WebSocket client harus selalu dijalankan di Main Thread.

13. **Skenario Kasus 3**:
    Pada pipeline CI/CD, eksekusi 120 skenario `XCUITest` memakan waktu 80 menit dan gagal secara intermiten (flaky) akibat dialog sistem operasi *"Allow Notifications?"* muncul secara acak di tengah pengujian.
    **Pendekatan rekayasa apa yang paling elegan untuk menuntaskan kedua masalah tersebut secara permanen?**
    - A. Tambahkan kode `sleep(10)` di awal aplikasi; gunakan robot fisik penekan layar.
    - B. Manfaatkan *test sharding* menggunakan `xcodebuild -only-testing` lintas simulator paralel, serta tangani *system alert* secara deterministik menggunakan `addUIInterruptionMonitor(withDescription:)` di `XCTestCase` atau setujui hak akses secara deklaratif via `xcrun simctl privacy`.
    - C. Hapus semua izin notifikasi dari Info.plist aplikasi produksi.
    - D. Jalankan UI Test secara berurutan satu per satu pada malam hari saja.

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Bagian 1
1. **B**: `XCTestCase` dirancang serbaguna untuk menguji logika non-UI (algoritma, I/O disk, protokol jaringan) pada background thread. Jika secara default terikat ke `@MainActor`, overhead perpindahan konteks (*thread hopping*) akan memperlambat test suite.
2. **B**: `canInit(with:)` adalah *gatekeeper inspection point*. URL loading system menanyakan ini ke setiap protokol terdaftar untuk mengetahui apakah protokol tersebut ingin menangani request bersangkutan.
3. **B**: `sleep()` menidurkan thread tanpa memproses runloop event, menghentikan progress operasi asinkronus yang dijadwalkan pada thread tersebut, dan rentan terhadap keterlambatan acak pada mesin CI yang sibuk.
4. **C**: `XCTClockMetric` digunakan untuk mencatat durasi elapsed time eksekusi blok kode.
5. **B**: Lossless PNG menyimpan representasi data pixel secara murni tanpa artefak kompresi, sangat esensial untuk perbandingan biner *golden image*.

#### Bagian 2
6. **B**: Jika tidak ditandai dengan flag khusus via `URLProtocol.setProperty`, pemanggilan request turunan yang dibuat oleh protokol tersebut akan kembali ditangkap oleh method `canInit(with:)` miliknya sendiri tanpa henti.
7. **B**: Mematikan animasi meratakan timeline visual, menjadikan state akhir UI tersedia seketika untuk diverifikasi oleh assertion engine, sekaligus memangkas waktu eksekusi pengujian secara drastis.
8. **B**: Konfigurasi `ephemeral` menjamin *zero disk persistence* (RAM-only), mencegah terjadinya pencemaran state (*cross-test pollution*) antar eksekusi kasus uji.
9. **B**: Hosting controller SwiftUI yang berjalan *off-screen* tidak secara otomatis memicu alur *layout & display pass*. Memanggil `layoutIfNeeded()` memaksa kalkulasi *autolayout engine* selesai sebelum gambar digambar.
10. **A**: Metrik performa membutuhkan variansi statistik (*standard deviation*) untuk membuang anomali (*outlier*), sehingga block dijalankan berulang kali sesuai `iterationCount`.

#### Bagian 3
11. **B**: Rendering teks bergantung pada subsistem grafis OS. Perbedaan macOS host atau versi iOS simulator sering membawa penyesuaian rasterisasi tipografi mikro pada font San Francisco. Standarisasi environment eksekusi mutlak diperlukan.
12. **A**: Mengombinasikan synchronous blocking expectation (`waitForExpectations`) dengan Swift Concurrency `Task` pada thread yang sama berisiko memblokir alur *continuation resume*. Pola modern adalah mengubah signature test function menjadi `async` dan meng-`await` operasi secara langsung.
13. **B**: `xcrun simctl privacy <sim-id> grant notifications <bundle-id>` menyuntikkan izin sebelum aplikasi dibuka, dan `addUIInterruptionMonitor` menangani dialog tak terduga. *Test sharding* memecah beban eksekusi panjang ke beberapa node paralel.

---

### 16. Summary

Implementasi arsitektur pengujian tingkat lanjut pada rekayasa perangkat lunak iOS enterprise bukan sekadar menambahkan *unit test*, melainkan membangun sebuah **sistem verifikasi deterministik tertutup**. 

Pilar utama dari arsitektur pengujian produksi meliputi:
1. **Network Hermeticism**: Mengisolasi lapisan jaringan secara mutlak dari server staging/produksi menggunakan *in-memory* protocol interception (`URLProtocol`) untuk menghasilkan pengujian yang deterministik dan berkecepatan tinggi.
2. **Visual Snapshot Integrity**: Mengotomatisasi validasi visual antarmuka lintas ukuran layar, tema, dan preferensi aksesibilitas menggunakan perbandingan piksel bermetrik toleransi terukur.
3. **Performance Metric Gating**: Memposisikan `XCTMetric` sebagai *circuit breaker* otomatis di CI/CD untuk mencegah penurunan performa (*regresi memori, lonjakan CPU, dan waktu rendering*).
4. **Modern Swift Concurrency Testing**: Mengadopsi isolasi `@MainActor` secara eksplisit dan mengeksekusi assertion asinkronus terstruktur guna mengeliminasi kondisi *flakiness* dan *deadlock*.
5. **Continuous Distribution Optimization**: Mengurangi waktu feedback loop pengembang melalui strategi *test sharding* dan paralelisasi terorkestrasi.