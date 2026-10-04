# Bab 01 Module 01: Arsitektur Sistem iOS, Runtime Environment, dan Application Lifecycle

---

## 1. Metadata Modul

* **Jalur Pembelajaran:** Advanced iOS Software Engineering
* **Modul:** 01 — Core System Architecture & Execution Lifecycle
* **Prasyarat:** Pemahaman dasar bahasa pemrograman Swift (OOP, POP, Concurrency dasar)
* **Target Runtime:** iOS 17.0+ / iPadOS 17.0+, Xcode 15.0+, Swift 5.9+
* **Tingkat Kesulitan:** Intermediate to Advanced

---

## 2. Ringkasan Eksekutif

Aplikasi iOS modern beroperasi di atas abstraksi berlapis yang diatur secara ketat oleh kernel Darwin (XNU) hingga Cocoa Touch Framework. Mengabaikan cara kerja lapisan-lapisan ini di tingkat subsistem sering kali berujung pada degradasi performa, pelanggaran batasan memori (jetsam OOM events), dan terminasi mendadak oleh sistem operasi (watchdog termination).

Modul ini mengupas tuntas anatomi arsitektur sistem iOS, mekanisme *sandboxing*, siklus hidup eksekusi aplikasi dari inisialisasi kernel hingga ke lapisan UI (`SceneDelegate` dan SwiftUI Lifecycle), model konkurensi berbasis `CFRunLoop`, serta mitigasi terminasi deterministik yang dikontrol oleh OS.

---

## 3. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis** struktur lapisan arsitektur iOS (Darwin/Core OS, Core Services, Media, Cocoa Touch) untuk memetakan alokasi dependensi framework secara optimal.
2. **Mengonfigurasi** daur hidup proses aplikasi (*Application and Scene Lifecycle*) menggunakan `UIApplicationDelegate` dan `UIWindowSceneDelegate` untuk meminimalkan *cold-launch latency* di bawah 400 milidetik.
3. **Mendiagnosis** pemutusan paksa proses oleh OS Watchdog (`0x8badf00d`) dan Jetsam Memory Pressure (`0x2badf00d`) melalui analisis *crash logs* dan `OSLog`.
4. **Menerapkan** eksekusi *background task scheduling* berbasis `BGTaskScheduler` tanpa melanggar batasan termal dan alokasi daya baterai sistem.

---

## 4. Konsep Kunci

* **Darwin Kernel (XNU):** Jantung sistem operasi yang menggabungkan Mach microkernel (manajemen memori virtual, IPC berbasis *Mach ports*, *thread scheduling*) dan BSD POSIX (model sekuritas, abstraksi filesystem, *networking*).
* **Application Sandboxing:** Batasan keamanan tingkat OS yang mengisolasi file, memori, dan akses *hardware* aplikasi dari aplikasi lain serta kernel eksternal.
* **CFRunLoop & Threading:** Mekanisme *event-processing loop* yang bertugas menerima dan mendistribusikan *event* masukan (sentuhan, *timer*, soket jaringan) secara sinkron pada *thread* tertentu.
* **Scene-Based Lifecycle:** Paradigma modular iOS 13+ di mana UI instanced (`UIWindowScene`) dipisahkan secara struktural dari status proses global (`UIApplication`).
* **Memory Management & Jetsam:** Mekanisme pengosongan paksa memori fisik oleh subsistem kernel iOS ketika tekanan memori sistem (*system-wide memory pressure*) mencapai ambang batas kritis.

---

## 5. Mengapa Ini Penting

Di lingkungan produksi enterprise, mayoritas crash "aneh" tidak berasal dari exception Swift/Objective-C standar, melainkan dari sanksi OS yang tidak toleran terhadap penyalahgunaan resource:

1. **Watchdog Termination (`0x8badf00d`):** Memblokir *main thread* selama lebih dari 10–20 detik saat aplikasi melakukan boot atau penanganan status background akan memicu eksekusi *kill signal* instan oleh SpringBoard.
2. **Out-of-Memory (Jetsam Kill):** iOS tidak menggunakan *swap memory* disk konvensional layaknya macOS. Jika batas *dirty memory* aplikasi terlampaui saat berada di background, kernel akan menghancurkan proses tanpa memicu sinyal exception standar.
3. **Multi-Window & State Corruption:** Sejak iPadOS memperkenalkan multi-window, kegagalan memisahkan logika data dari *window state* menghasilkan inkonsistensi sinkronisasi antar UI scene secara masif.

---

## 6. Arsitektur Mental Model

Untuk memahami sistem iOS, bayangkan sebuah piramida 4 lapis berorientasi isolasi. Aplikasi Anda hidup di puncak piramida (**Cocoa Touch**) di dalam kontainer kedap udara (*Sandbox*). Segala instruksi yang membutuhkan sumber daya fisik (memori, jaringan, grafis, disk) wajib didelegasikan menembus lapisan **Media** dan **Core Services** hingga diterjemahkan oleh **Darwin (Mach/BSD)** ke perangkat keras.

Setiap *Window* UI tidak merepresentasikan keseluruhan aplikasi; ia hanyalah sebuah jendela proyeksi (*Scene*) dari satu proses tunggal yang diawasi ketat oleh pengawas sistem (*SpringBoard Daemon*).

---

## 7. Diagram Alur Kerja / Arsitektur

### 7.1. Lapisan Abstraksi Arsitektur iOS

```text
+-------------------------------------------------------------+
|                        Cocoa Touch                          |
|         (UIKit, SwiftUI, MapKit, PushKit, Combine)          |
+-------------------------------------------------------------+
|                           Media                             |
|          (Core Graphics, Metal, AVFoundation, Core Image)   |
+-------------------------------------------------------------+
|                       Core Services                         |
|   (Foundation, Core Data, Core Foundation, Network, Security) |
+-------------------------------------------------------------+
|                      Core OS / Darwin                       |
|     +-------------------------+-------------------------+   |
|     |       Mach Layer        |        BSD Layer        |   |
|     | (Threads, IPC, Mach VM) | (POSIX, Security, Sockets)|   |
|     +-------------------------+-------------------------+   |
|     |                   I/O Kit (Drivers)               |   |
+-----+---------------------------------------------------+---+
                               Hardware
             (Apple Silicon: CPU, GPU, Secure Enclave)
```

### 7.2. Scene & Application Lifecycle Execution Flow

```text
               +----------------------------------+
               | User Taps App Icon / URL Trigger |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |      kernel_task / launchd       |
               | (Fork process, Map Mach Virtual) |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |            dyld4/dyld             |
               | (Load dylibs, Rebase, Bind, Init)|
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |        main() / @main Entry      |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |       UIApplicationMain()        |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |      AppDelegate (Process Level) |
               | didFinishLaunchingWithOptions    |
               +----------------------------------+
                                |
                                v
               +----------------------------------+
               |  SceneDelegate (Interface Level) |
               |     willConnectToSession         |
               +----------------------------------+
                                |
        +-----------------------+-----------------------+
        v                                               v
+---------------+                               +---------------+
| UI Background |                               |  UI Active    |
| (Suspended /  |                               | (Interactive /|
|  BG Running)  |                               |  Foreground)  |
+---------------+                               +---------------+
```

---

## 8. Bedah Komponen

### Komponen 1: Dynamic Linker (`dyld`)
Saat aplikasi dieksekusi, kernel memetakan binary Mach-O ke memori virtual. `dyld` kemudian memuat *dynamic libraries* (`.dylib`), menjalankan *rebase*, *binding*, inisialisasi runtime Objective-C/Swift, dan memanggil fungsi `main()`. Optimalisasi dylib mengurangi *cold boot time* secara drastis.

### Komponen 2: Application Sandbox Directory
Setiap aplikasi diisolasi ke dalam direktori tersendiri:
* `Bundle Container`: Berisi berkas executable, aset, dan framework. Bersifat *read-only*.
* `Data Container`:
  * `Documents/`: Data kritis pengguna; disinkronkan ke iCloud via default backup.
  * `Library/Caches/`: Berkas semi-permanen yang bisa dihapus sistem saat ruang penyimpanan menipis.
  * `Library/Preferences/`: Berkas preferensi konfigurasi (`UserDefaults`).
  * `tmp/`: Berkas sementara yang dapat dihapus sistem kapan saja ketika aplikasi tidak berjalan.

### Komponen 3: Main CFRunLoop
Thread utama menjalankan loop berkelanjutan:
```text
do {
    1. Wait for Mach message or Source 0/1 event.
    2. Wake up on event dispatch.
    3. Execute handlers (Layout, Drawing, Target-Action).
    4. Transition to sleep state.
} while (!terminated);
```
Memblokir loop ini menyebabkan UI membeku (*frame drop*) dan memicu *watchdog termination*.

### Komponen 4: Scene-Driven Architecture
Diperkenalkan pada iOS 13, memisahkan penanganan siklus proses (*process-level*) ke `AppDelegate` dan penyajian antarmuka grafis (*window-level*) ke `SceneDelegate`. Setiap sesi tampilan diwakili oleh instance `UIWindowScene`, memungkinkan beberapa instansiasi antarmuka berjalan independen di bawah proses yang sama.

---

## 9. Panduan Implementasi Bertahap

Untuk mengintegrasikan penanganan lifecycle, diagnostik booting, dan background persistence yang aman, ikuti prosedur berikut:

1. **Konfigurasi Info.plist:** Matikan pembuatan antarmuka otomatis (*Storyboard initialization*) jika menggunakan pendekatan *programmatic UI*.
2. **Kustomisasi Application Entry Point:** Inisialisasi dependensi inti (logging, error reporting) sebelum window dibuat.
3. **Penyiapan Scene Delegate:** Bangun `UIWindow` secara manual di dalam `scene(_:willConnectTo:options:)`.
4. **Implementasi State Serialization:** Tangani `sceneDidEnterBackground(_:)` untuk menyimpan draf data pengguna.
5. **Observasi Memory Pressure:** Pasang listener `UIApplication.didReceiveMemoryWarningNotification` untuk membuang image cache dan data sementara.

---

## 10. Minimal Reproducible Example

Berikut adalah implementasi minimal iOS lifecycle programmatic murni tanpa antarmuka Storyboard:

```swift
import UIKit

// 1. Entry Point
@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        // Inisialisasi minimum logging / analytics
        print("[AppDelegate] didFinishLaunchingWithOptions")
        return true
    }

    // MARK: UISceneSession Lifecycle
    func application(
        _ application: UIApplication,
        configurationForConnecting connectingSceneSession: UISceneSession,
        options: UIScene.ConnectionOptions
    ) -> UISceneConfiguration {
        return UISceneConfiguration(
            name: "Default Configuration",
            sessionRole: connectingSceneSession.role
        )
    }
}

// 2. Window/Scene Management
final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        guard let windowScene = (scene as? UIWindowScene) else { return }
        
        let window = UIWindow(windowScene: windowScene)
        let rootViewController = RootLifecycleViewController()
        window.rootViewController = UINavigationController(rootViewController: rootViewController)
        self.window = window
        window.makeKeyAndVisible()
    }
}

// 3. Root UI Presentation
final class RootLifecycleViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        title = "Runtime Lifecycle Minimal"
    }
}
```

---

## 11. Production-Ready Code Example

Contoh berikut mengimplementasikan `LifecycleManager` berbasis enterprise dengan integrasi `os.Logger`, pelaporan metrik booting, penanganan *memory pressure warning*, dan mitigasi *background state persistence* yang aman.

```swift
import UIKit
import OSLog

// MARK: - Core System Lifecycle Diagnostics & Telemetry
final class SystemLifecycleManager {
    static let shared = SystemLifecycleManager()
    
    private let logger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "com.app.ios", category: "Lifecycle")
    private var backgroundTaskID: UIBackgroundTaskIdentifier = .invalid
    private let stateQueue = DispatchQueue(label: "com.app.lifecycle.stateQueue", qos: .utility)

    private init() {
        setupMemoryPressureObserver()
    }

    func logBootPhase(phase: String) {
        logger.info("[BOOT PHASE]: \(phase, privacy: .public)")
    }

    private func setupMemoryPressureObserver() {
        NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.handleMemoryPressure()
        }
    }

    private func handleMemoryPressure() {
        logger.critical("[RESOURCE ALERT]: Low Memory Warning Received! Evicting transient caches.")
        // Eviction logic: Clear memory caches, abort non-essential image decodes
        URLCache.shared.removeAllCachedResponses()
    }

    func beginDefensiveBackgroundTask() {
        guard backgroundTaskID == .invalid else { return }
        
        logger.debug("[TASK]: Requesting Background Execution Budget")
        backgroundTaskID = UIApplication.shared.beginBackgroundTask(withName: "CriticalStatePersistence") { [weak self] in
            // Expiration Handler: Eksekusi jika OS mendesak proses harus ditutup
            self?.logger.warning("[TASK]: OS Watchdog warned task expiration. Halting.")
            self?.endDefensiveBackgroundTask()
        }
    }

    func endDefensiveBackgroundTask() {
        guard backgroundTaskID != .invalid else { return }
        logger.debug("[TASK]: Releasing Background Execution Budget")
        UIApplication.shared.endBackgroundTask(backgroundTaskID)
        backgroundTaskID = .invalid
    }

    func persistPendingStateSafely(operation: @escaping () -> Void) {
        beginDefensiveBackgroundTask()
        stateQueue.async { [weak self] in
            defer { self?.endDefensiveBackgroundTask() }
            operation()
        }
    }
}

// MARK: - Production Application Delegate
@main
final class EnterpriseAppDelegate: UIResponder, UIApplicationDelegate {
    
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        SystemLifecycleManager.shared.logBootPhase(phase: "didFinishLaunchingWithOptions Start")
        
        // Aturan ketat Apple: Jangan lakukan parsing JSON, setup database berat, 
        // atau HTTP blocking call pada main thread di sini (Watchdog mitigation).
        return true
    }

    func application(
        _ application: UIApplication,
        configurationForConnecting connectingSceneSession: UISceneSession,
        options: UIScene.ConnectionOptions
    ) -> UISceneConfiguration {
        let configuration = UISceneConfiguration(
            name: "Enterprise Config",
            sessionRole: connectingSceneSession.role
        )
        configuration.delegateClass = EnterpriseSceneDelegate.self
        return configuration
    }
}

// MARK: - Production Scene Delegate
final class EnterpriseSceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?
    private let logger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "com.app.ios", category: "Scene")

    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        guard let windowScene = (scene as? UIWindowScene) else { return }
        
        let targetWindow = UIWindow(windowScene: windowScene)
        let rootVC = EnterpriseRootViewController()
        targetWindow.rootViewController = UINavigationController(rootViewController: rootVC)
        self.window = targetWindow
        targetWindow.makeKeyAndVisible()
        
        logger.info("[SCENE]: UI Window hierarchy successfully attached.")
    }

    func sceneDidEnterBackground(_ scene: UIScene) {
        logger.info("[SCENE]: Entered Background. Scheduling critical data flush.")
        
        SystemLifecycleManager.shared.persistPendingStateSafely {
            // Simulasi operasi persistence I/O write ke Dokumen Terenkripsi
            let documentsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let checkpoint = documentsURL.appendingPathComponent("checkpoint.meta")
            try? "Checkpoint-Active".write(to: checkpoint, atomically: true, encoding: .utf8)
        }
    }

    func sceneWillEnterForeground(_ scene: UIScene) {
        logger.info("[SCENE]: Returning to Foreground. Re-syncing transient states.")
    }
}

// MARK: - Minimal Presentation Layer
final class EnterpriseRootViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemGroupedBackground
        title = "Core Architecture"
    }
}
```

---

## 12. Edge Cases, Race Conditions & Failure Modes

* **Background Task Timeouts:** Memanggil `beginBackgroundTask` mewajibkan pemanggilan `endBackgroundTask`. Jika terlewat karena crash atau dead-lock logika, OS akan menghentikan paksa aplikasi dengan kode terminasi `0xbaddcafe` saat jatah alokasi waktu habis.
* **Cold-Start File Access Under Data Protection:** Jika file dienkripsi dengan flag `NSFileProtectionComplete`, file tersebut *tidak dapat dibaca* sebelum user membuka kunci perangkat (passcode). Mengakses file ini ketika aplikasi berjalan otomatis di background via push notification akan memicu `POSIX error: Operation not permitted`.
* **State Race Condition on Multi-Scene:** Di iPadOS, pengguna dapat membuka 2 window secara simultan. Jika kedua scene memperbarui singleton state yang sama pada background event, akan terjadi race condition memori kecuali state tersebut dilindungi oleh Swift `actor` atau serial dispatch queue.

---

## 13. Anti-Patterns & Pitfalls

| Kesalahan Umum | Mengapa Buruk | Solusi Standar Arsitektur |
| :--- | :--- | :--- |
| **Heavy I/O di `didFinishLaunching`** | Mengakibatkan freeze rendering. Melebihi 10 detik memicu *0x8badf00d watchdog termination*. | Pindahkan tugas ke background task via GCD/Swift Concurrency (`Task.detached`). |
| **Penyimpanan Cache di `Documents/`** | Menyebabkan iCloud Backup membesar; aplikasi dapat ditolak Apple Review Guideline 2.2. | Gunakan direktori `Library/Caches/` atau beri tanda `URLIsExcludedFromBackupKey`. |
| **Menyimpan UI State di `AppDelegate`** | Hancur pada lingkungan iPadOS dengan multi-scene split view; layout saling tumpang tindih. | Simpan state window di context controller atau delegasi `UIWindowSceneDelegate`. |
| **Thread Block di `NotificationCenter`** | NotificationCenter mendispatch notifikasi pada thread pengirim secara default. Blokade di listener = blokade pengirim. | Selalu alokasikan ke queue yang tepat saat meregister atau menangani event broadcast. |

---

## 14. Analisis Trade-off

| Keputusan Arsitektur | Keuntungan | Biaya / Kerugian |
| :--- | :--- | :--- |
| **Single-Window vs Multi-Window (`SceneDelegate`)** | Single-window mempermudah state isolation dan state tracking. | Menolak adaptasi iPadOS; pengalaman desktop-class tidak tercapai. |
| **Static Frameworks vs Dynamic Frameworks (`.dylib`)** | Static framework mempercepat *initial dynamic linker boot time* (dyld). | Meningkatkan ukuran biner aplikasi executable; duplikasi simbol jika tidak dikelola. |
| **`beginBackgroundTask` vs `BGAppRefreshTask`** | `beginBackgroundTask` langsung berjalan saat exit; eksekusi instan. | Dibatasi sekitar 30 detik; bukan untuk tugas komputasi berat/sinkronisasi massal. |

---

## 15. Keamanan & Efisiensi Sistem

### 15.1. Proteksi Berkas (Data Protection API)
Manfaatkan enkripsi bawaan *Hardware AES Cryptographic Engine* dengan menyetel atribut keamanan:
```swift
try data.write(to: fileURL, options: .completeFileProtection)
```
Tingkatan:
* `completeFileProtection`: Hanya bisa dibaca saat device unlocked.
* `completeFileProtectionUnlessOpen`: Dapat terus diakses meski terkunci jika dibuka sebelum penguncian.
* `completeFileProtectionUntilFirstUserAuthentication`: Dapat diakses setelah boot dan user unlock satu kali (standar background sync).

### 15.2. Profiling Memory Footprint (Jetsam Optimization)
Aplikasi iOS tidak memiliki *dirty memory swap*. Batasi akumulasi alokasi citra resolusi tinggi mentah. Gunakan teknik *downsampling* menggunakan `ImageIO` (`CGImageSourceCreateThumbnailAtIndex`) sebelum me-render bitmap ke memori grafis via UI.

---

## 16. Observability, Logging, & Telemetry

Apple melarang penggunaan `print()` berlebihan di sistem produksi karena tidak aman (membocorkan data PII) dan lambat. Gunakan `os.Logger`:

```swift
import OSLog

struct DiagnosticsService {
    // Subsystem membagi area app; Category mengelompokkan modul kerja
    private static let logger = Logger(subsystem: "com.enterprise.ios", category: "EngineDiagnostics")

    static func recordSystemTransition(from: String, to: String) {
        // Logging terstruktur: Menghindari interpolasi string dynamic berbahaya
        logger.notice("Transitioned from [\(from, privacy: .public)] to [\(to, privacy: .public)]")
    }

    static func captureSensitiveUserData(userID: String) {
        // Redaction otomatis oleh OS: userID akan muncul sebagai <private> di console publik
        logger.debug("Active user authorization token refreshed for ID: \(userID, privacy: .private(mask: .hash))")
    }
}
```

Pelacakan *crash lifecycle* tingkat lanjut dapat diamati menggunakan framework `MetricKit`:
```swift
import MetricKit

final class MetricSubscriber: NSObject, MXMetricManagerSubscriber {
    func setupSubscription() {
        MXMetricManager.shared.add(self)
    }

    func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads {
            if let launchMetrics = payload.applicationLaunchMetrics {
                let coldLaunchTime = launchMetrics.histogrammedTimeToFirstDraw
                // Ekspor histogram data metrik cold-start ke back-end telemetry
            }
        }
    }
}
```

---

## 17. Verifikasi & Pengujian

Berikut contoh pengujian unit menguji parsing konfigurasi bootstrapping dan ketahanan serialisasi lifecycle state:

```swift
import XCTest
@testable import YourAppModule

final class LifecycleManagerTests: XCTestCase {
    
    var sut: SystemLifecycleManager!

    override func setUp() {
        super.setUp()
        sut = SystemLifecycleManager.shared
    }

    func test_BackgroundExecution_CompletesWithoutDeadlock() {
        let expectation = self.expectation(description: "Safely execute background persistence")
        var executionCompleted = false

        sut.persistPendingStateSafely {
            // Simulasi thread-safe critical task
            executionCompleted = true
            expectation.fulfill()
        }

        waitForExpectations(timeout: 2.0) { _ in
            XCTAssertTrue(executionCompleted, "Eksekusi safe background state serialization gagal dieksekusi.")
        }
    }
    
    func test_AppSandboxDocumentsDirectory_IsReachable() {
        let paths = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)
        XCTAssertFalse(paths.isEmpty, "Sandbox Documents path wajib terdeteksi oleh sistem.")
        XCTAssertEqual(paths.first?.scheme, "file", "Sandbox container URL skema harus berupa file:///")
    }
}
```

---

## 18. Rekomendasi Praktik Terbaik

1. [ ] **Verifikasi Cold Launch:** Pastikan waktu antara invoke binary sampai render frame pertama (`time-to-first-draw`) di bawah 400 milidetik pada perangkat acuan target.
2. [ ] **Main Thread Sanitation:** Pastikan tidak ada dependensi database (CoreData/SQLite/Realm), deserialisasi JSON besar, atau operasi disk blocking di `application(_:didFinishLaunchingWithOptions:)`.
3. [ ] **Ukur Jetsam Overhead:** Gunakan *Instruments (Allocations & Leaks)* untuk memastikan alokasi *Dirty Memory* tetap berada di bawah batas regulasi memory footprint (biasanya `< 50MB` saat transisi background).
4. [ ] **Isolasi Logika Multi-Scene:** Jangan gunakan referensi `UIApplication.shared.keyWindow` (sudah deprecated). Manfaatkan *scene context resolution*.
5. [ ] **Implementasi MXMetricManager:** Pantau crash rate, watchdog, dan performa peluncuran aplikasi langsung dari perangkat end-user via Apple MetricKit.

---

## 19. Latihan Mandiri Bertingkat

### Tingkat 1: Guided
Hapus Storyboard default dari project baru (`Main.storyboard`). Konfigurasikan `Info.plist` agar mengabaikan referensi Main Storyboard, lalu implementasikan `SceneDelegate` manual untuk menginstansiasi sebuah `UINavigationController` dengan root controller sederhana berwarna merah. Amati run-log untuk membuktikan flow daur hidup berjalan murni secara programatik.

### Tingkat 2: Semi-Guided
Implementasikan pencatat waktu performa booting. Gunakan `os_signpost` untuk menandai titik awal eksekusi di `AppDelegate.didFinishLaunchingWithOptions` dan titik akhir saat tampilan pertama di root controller selesai digambar (`viewDidAppear`). Buka profiling template **App Launch** di **Instruments** dan periksa trace signpost yang baru saja Anda buat.

### Tingkat 3: Open Challenge
Bangun sistem penulisan draft data mandiri (*Draft Auto-Save Engine*). Jika aplikasi tiba-tiba dipindah ke background atau menerima sinyal `sceneWillResignActive`, sistem wajib memanfaatkan `beginBackgroundTask` untuk mendeposit payload teks ke dalam direktori terenkripsi (`.completeFileProtection`). Uji fungsionalitas ini dengan mensimulasikan force-kill dari Xcode, dan validasi bahwa data berhasil tersimpan tanpa terkorupsi saat dibuka kembali.

---

## 20. Referensi & Bacaan Lanjutan

* Apple Developer Documentation: *About the iOS Technologies*.
* Apple Developer Documentation: *Managing Your App's Life Cycle*.
* WWDC 2019: *Session 212 - Optimizing App Launch*.
* WWDC 2020: *Session 10078 - Eliminate Animation Hitches with Instruments*.
* Jonathan Levin: *Mac OS X and iOS Internals: To the Apple's Core (Architecture Deep Dive)*.
* Apple Security Documentation: *iOS Security Guide (Hardware & Sandboxing Infrastructure)*.