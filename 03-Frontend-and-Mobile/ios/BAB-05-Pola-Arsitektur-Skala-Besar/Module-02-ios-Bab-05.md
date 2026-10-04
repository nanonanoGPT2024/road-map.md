# BAB 05: Pola Arsitektur Skala Besar
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- **Menganalisis & Menguraikan (Analyze & Deconstruct):** Mengidentifikasi *architectural bottleneck*, *tight coupling*, dan *circular dependency* pada basis kode iOS monolitik skala jutaan baris kode (LOC).
- **Merancang Arsitektur Skala Besar (Synthesize & Design):** Membangun arsitektur multi-modul berbasis *Unidirectional Data Flow* (UDF) dan *Domain-Driven Design* (DDD) menggunakan Swift Package Manager (SPM) atau Tuist dengan pemisahan tegas antara *Interface*, *Implementation*, dan *Testing Doubles*.
- **Mengimplementasikan Navigasi Terdistribusi (Implement):** Merekayasa sistem navigasi decoupled berbasis *URL/Intent Router* dan *Coordinator Pattern* yang mendukung *deep linking*, *dynamic feature delivery*, dan *state restoration* lintas modul.
- **Mengoptimalkan Kinerja Waktu Kompilasi & Runtime (Optimize):** Mengelola konfigurasi *Static vs Dynamic Frameworks*, meminimalkan *dynamic dispatch* overhead, dan meniadakan *re-compilation cascade* melalui *ABI stability* dan modularisasi berbasis protokol.
- **Mengisolasi Konkurensi & Memory Safety (Evaluate):** Mengintegrasikan Swift Concurrency (`Sendable`, `Actors`, `@MainActor`) secara *thread-safe* di seluruh lapisan arsitektur tanpa menimbulkan *data races* atau *deadlocks*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
1. **Swift Concurrency Mendalam:** Pemahaman eksekusi non-blocking, `Actor`, `Task`, `AsyncSequence`, cooperative thread pool, dan aturan penegakan `Sendable` pada Swift 5.9/6.
2. **Pola Desain Dasar iOS:** Penguasaan tingkat lanjut atas MVVM, Clean Architecture, VIPER, Delegate Pattern, dan Inversion of Control (IoC).
3. **Sistem Build iOS & Tooling:** Pemahaman siklus kompilasi Clang/Swiftc, LLVM, struktur mach-O binary, dylib vs static archive (`.a`), serta konfigurasi dasar Swift Package Manager (SPM).
4. **Manajemen Memori:** Pemahaman mendalam terkait ARC (Automatic Reference Counting), retain cycle, `weak`/`unowned` references, autorelease pools, dan instrumentasi via Xcode Instruments (Leaks, Allocations).

---

### 3. Concept & Internal Architecture

Membangun aplikasi iOS enterprise berskala ratusan insinyur menuntut transisi dari sekadar "pola tampilan" (seperti MVVM standar) ke "arsitektur modular skala sistem". 

```
+-----------------------------------------------------------------------------------+
|                                  App Executable                                   |
|               (AppDelegate, SceneDelegate, AppCompositionRoot)                    |
+-----------------------------------------------------------------------------------+
                                         |
         +-------------------------------+-------------------------------+
         | (Dependency Graph Resolution via Pure DI / Interface Binding) |
         v                                                               v
+-----------------------+                               +-----------------------+
|  FeatureHome (Impl)   |                               | FeatureCheckout(Impl) |
+-----------------------+                               +-----------------------+
         |                                                               |
         v                                                               v
+-----------------------+                               +-----------------------+
| FeatureHomeInterface  |<==============================|FeatureCheckoutInterface
|  (Protocols, Models)  |    (Cross-Module Navigation   |  (Protocols, Models)  |
+-----------------------+         via Router)           +-----------------------+
         |                                                               |
         +-------------------------------+-------------------------------+
                                         |
                                         v
                      +-------------------------------------+
                      |       Core / Domain Services        |
                      |   (Networking, Storage, Auth API)   |
                      +-------------------------------------+
                                         |
                                         v
                      +-------------------------------------+
                      |           Foundation / OS           |
                      +-------------------------------------+
```

#### 3.1 Pemisahan Interface vs Implementation (Interface-Driven Modularization)
Pada struktur monolitik, modul fitur A yang mengimpor modul fitur B (`import FeatureB`) menciptakan *compile-time coupling*. Jika implementasi internal fitur B berubah, seluruh fitur A dan modul turunannya wajib dikompilasi ulang. 

Arsitektur produksi enterprise memecah setiap modul menjadi minimal dua target:
1. **`FeatureXInterface`:** Berisi protokol input/output, model entitas (`Struct`), dan abstraction interface router. Modul ini ringan, stabil, jarang berubah, dan tidak memiliki dependensi ke modul pihak ketiga yang berat.
2. **`FeatureX` (Implementation):** Berisi `View`, `ViewModel`/`Presenter`, `Worker`, dan *business logic*. Mengimplementasikan protokol dari `FeatureXInterface`.
3. **`FeatureXTesting`:** Berisi Mock/Spy/Stub dari `FeatureXInterface` untuk konsumsi unit test fitur lain tanpa memicu dependensi ke implementasi konkret.

#### 3.2 Dynamic Linker (dyld) vs Static Linker & Binary Size
- **Static Libraries (`.a` / Static Frameworks):** Kode biner langsung disatukan ke dalam *executable* utama pada saat build time.
  - *Kelebihan:* Mengurangi waktu start-up aplikasi (*pre-main execution time*), karena `dyld` tidak perlu memetakan dan merelokasi simbol eksternal saat aplikasi diluncurkan.
  - *Kekurangan:* Jika modul statis A diimpor oleh modul dinamis B dan modul dinamis C, dapat terjadi duplikasi simbol biner (*code bloat*), kecuali dikonfigurasi secara presisi.
- **Dynamic Frameworks (`.framework` / `.dylib`):** Dimuat ke dalam alokasi memori secara dinamis saat runtime oleh `dyld3` / `dyld4`.
  - *Kelebihan:* Menghindari duplikasi simbol biner, memungkinkan modularisasi independen yang bersih.
  - *Kekurangan:* Setiap dynamic library menambahkan *launch time penalty* (drebinding, rebinding pointer, initializers execution). Apple merekomendasikan batas optimal total dynamic frameworks tidak melebihi angka puluhan tanpa merge (*mergeable libraries* pada Xcode 15+).

#### 3.3 Memory Footprint & Retain Cycle Elimination across Modular Boundaries
Dalam arsitektur *Coordinator* atau *Router* lintas modul, retain cycles kerap terjadi saat Router memegang referensi kuat ke `UIHostingController` atau `UIViewController`, sementara controller tersebut memegang referensi kuat ke `Coordinator` melalui delegasi atau closures. Penggunaan closure inter-module harus diverifikasi:
- Menegakkan capturing `[weak self]` secara ketat pada seluruh boundary async/concurrency.
- Menggunakan pendekatan *Value-oriented state machines* (seperti TCA atau Redux) di mana state direpresentasikan oleh immutable structs, sehingga memori state dapat dibersihkan secara deterministik saat stack navigasi dihancurkan.

---

### 4. Why & What

| Kondisi | Monolitik MVVM Tradisional | Enterprise Modularized Clean/UDF |
| :--- | :--- | :--- |
| **Waktu Kompilasi (Clean Build)** | Eksponensial seiring bertambahnya LOC (bisa >20 menit). | Linier dan terdistribusi; cache modul via remote caching (Tuist/Bazel). |
| **Batas Domain (Boundaries)** | Rentan dilanggar; developer dapat memanggil `Manager` kelas lain secara langsung. | Ditegakkan via *Compiler Verification*. Modul A tidak bisa mengakses internal Modul B. |
| **Konflik Tim Git** | Sering terjadi konflik pbxproj dan merge hell pada file repositori tunggal. | Terisolasi per paket/modul; insinyur bekerja pada package terpisah dengan PR terisolasi. |
| **Navigasi & Routing** | `NavigationLink` atau `UINavigationController.push` langsung memanggil View tujuan. | Terabstraksi via *Decoupled Router/Coordinator*; view tidak tahu siapa layer selanjutnya. |
| **Testability** | UI Testing lambat, unit test membutuhkan bootstrap seluruh dependensi aplikasi. | Micro-apps memungkinkan eksekusi dan unit test modul fitur tertentu secara terisolasi penuh. |

---

### 5. How (Workflow Detail)

Alur kerja pengembangan arsitektur produksi:
1. **Analisis Graph Dependensi:** Tentukan *Domain Boundary* menggunakan prinsip DDD. Pastikan tidak ada dependensi melingkar (*A -> B -> A*).
2. **Definisi Kontrak Interface:** Tulis protokol public dan model data transfer (DTO) pada `FeatureInterface`.
3. **Penyusunan Inversion of Control (IoC):** Registrasikan implementasi fitur ke dependency container terpusat pada *Composition Root* aplikasi utama.
4. **Implementasi State Management:** Susun State, Intent/Action, dan Reducer/Engine dengan jaminan mutasi berbasis *Single Source of Truth*.
5. **Konstruksi Navigation Router:** Bangun routing berbasis *deep link pattern* yang memetakan URL atau Universal Links ke instansiasi `Interface` tujuan secara dinamis.
6. **Optimasi Pipeline Kompilasi:** Atur link type SPM (Dynamic vs Static) dan validasikan *build time analyzer* untuk mencegah kompilasi lambat akibat kompleksitas *type-inference*.

---

### 6. Analogy & Diagram ASCII

#### 6.1 Analogi: Pabrik Otomotif Modular
Sebuah monolitik MVVM seperti merakit mobil di mana semua kabel, bodi, dan mesin dilas langsung di satu ruang. Jika kabel audio ingin diganti, seluruh mesin harus dibongkar. 

Arsitektur Modular Enterprise ibarat sistem komponen bersertifikasi:
- Departemen Navigasi mempublikasikan kabel standar (*Interface/Socket*).
- Tim Infotainment memproduksi perangkat yang sesuai dengan colokan tersebut (*Implementation*).
- Modul Dashboard tidak perlu tahu chip apa yang dipakai di dalam sistem Audio; Dashboard hanya tahu sinyal output yang dikirimkan via soket interface standar.

#### 6.2 Visualisasi Alur Data Unidirectional (UDF) & Router

```
+---------------------------------------------------------------------------------+
|                               Feature Boundary                                  |
|                                                                                 |
|   +------------------+         User Action         +------------------------+   |
|   |                  | --------------------------> |                        |   |
|   |      View        |                             |     Store / Worker     |   |
|   |  (SwiftUI/UIKit) | <-------------------------- |  (Actor/State Engine)  |   |
|   +------------------+         State Stream        +------------------------+   |
|            |                                                    |               |
+------------|----------------------------------------------------|---------------+
             | (Triggers Navigation)                              | (Side-Effect)
             v                                                    v
+--------------------------+                         +----------------------------+
| Feature Router/Coord     |                         | Domain Service (API)       |
| (Navigates via Interface)|                         | (Thread-safe Dependency)   |
+--------------------------+                         +----------------------------+
             |                                                    |
             | Resolve target                                     | URLSession / Database
             v                                                    v
+--------------------------+                         +----------------------------+
| App Composition Root     |                         | External Backend Server    |
+--------------------------+                         +----------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Abstraksi Interface dan Inversion of Control Dasar
Contoh bagaimana modul Interface mendefinisikan kontrak tanpa mengetahui siapa yang akan mengeksekusinya.

```swift
// Target: FeatureAccountInterface
import Foundation

public struct UserProfile: Identifiable, Sendable, Equatable {
    public let id: UUID
    public let username: String
    public let email: String
    
    public init(id: UUID, username: String, email: String) {
        self.id = id
        self.username = username
        self.email = email
    }
}

public protocol AccountServiceProtocol: Sendable {
    func fetchProfile() async throws -> UserProfile
}
```

```swift
// Target: AppCompositionRoot (App Layer)
import Foundation
import FeatureAccountInterface

// Service Locator / Factory Container sederhana
public final class DependencyContainer: @unchecked Sendable {
    public static let shared = DependencyContainer()
    
    private var registry: [String: Any] = [:]
    private let lock = NSLock()
    
    private init() {}
    
    public func register<T>(_ serviceType: T.Type, factory: @escaping () -> T) {
        lock.lock()
        defer { lock.unlock() }
        let key = String(reflecting: serviceType)
        registry[key] = factory
    }
    
    public func resolve<T>(_ serviceType: T.Type) -> T {
        lock.lock()
        defer { lock.unlock() }
        let key = String(reflecting: serviceType)
        guard let factory = registry[key] as? () -> T else {
            fatalError("Dependency '\(key)' belum diregistrasikan!")
        }
        return factory()
    }
}
```

---

#### 7.2 Practical Example: Enterprise UDF, Modular Router, dan Thread-Safe State Engine
Di bawah ini adalah implementasi standar produksi Clean-UDF:

##### A. Target: `FeatureOrderInterface`
```swift
import SwiftUI

public protocol OrderDetailRouting: Sendable {
    @MainActor func navigateToPayment(orderId: String)
}

public protocol OrderServiceProtocol: Sendable {
    func loadOrderDetails(id: String) async throws -> OrderDetailEntity
}

public struct OrderDetailEntity: Sendable, Equatable {
    public let id: String
    public let totalAmount: Decimal
    public let itemsCount: Int
    
    public init(id: String, totalAmount: Decimal, itemsCount: Int) {
        self.id = id
        self.totalAmount = totalAmount
        self.itemsCount = itemsCount
    }
}
```

##### B. Target: `FeatureOrder` (Implementasi Nyata)
```swift
import SwiftUI
import FeatureOrderInterface

// MARK: - State & Intent (UDF)
public struct OrderViewState: Sendable, Equatable {
    public var isLoading: Bool = false
    public var order: OrderDetailEntity?
    public var errorMessage: String?
    
    public init() {}
}

public enum OrderViewIntent: Sendable {
    case onAppear
    case checkoutTapped
}

// MARK: - ViewModel (State Store)
@MainActor
public final class OrderViewModel: ObservableObject {
    @Published public private(set) var state: OrderViewState = .init()
    
    private let orderId: String
    private let service: OrderServiceProtocol
    private let router: OrderDetailRouting
    
    public init(orderId: String, service: OrderServiceProtocol, router: OrderDetailRouting) {
        self.orderId = orderId
        self.service = service
        self.router = router
    }
    
    public func handle(intent: OrderViewIntent) {
        switch intent {
        case .onAppear:
            fetchOrder()
        case .checkoutTapped:
            router.navigateToPayment(orderId: orderId)
        }
    }
    
    private func fetchOrder() {
        state.isLoading = true
        state.errorMessage = nil
        
        Task { [weak self] in
            guard let self = self else { return }
            do {
                let entity = try await self.service.loadOrderDetails(id: self.orderId)
                self.state.order = entity
                self.state.isLoading = false
            } catch {
                self.state.errorMessage = error.localizedDescription
                self.state.isLoading = false
            }
        }
    }
}

// MARK: - SwiftUI View
public struct OrderDetailView: View {
    @StateObject private var viewModel: OrderViewModel
    
    public init(viewModel: OrderViewModel) {
        _viewModel = StateObject(wrappedValue: viewModel)
    }
    
    public var body: some View {
        VStack(spacing: 20) {
            if viewModel.state.isLoading {
                ProgressView("Mengambil Data Transaksi...")
            } else if let error = viewModel.state.errorMessage {
                Text("Error: \(error)").foregroundColor(.red)
            } else if let order = viewModel.state.order {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Order ID: \(order.id)").font(.headline)
                    Text("Jumlah Barang: \(order.itemsCount)")
                    Text("Total: Rp \(order.totalAmount.description)")
                }
                .padding()
                
                Button("Lanjutkan ke Pembayaran") {
                    viewModel.handle(intent: .checkoutTapped)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .task {
            viewModel.handle(intent: .onAppear)
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks & Masalah
Sebuah aplikasi perbankan digital skala regional (Tier-1 Banking App) memiliki lebih dari 120 insinyur iOS yang bekerja pada basis kode monolitik tunggal berisi ~1.800.000 baris kode (LOC).
1. **Waktu Kompilasi Lambat:** Clean build pada CI server mencapai **42 menit**. Pull Request merge queue sering memicu timeout.
2. **Kerapuhan Kode (Brittle Architecture):** Perubahan pada modul `PaymentCore` memicu kerusakan regression tak terduga pada fitur `Investment` karena pemanggilan global singleton tanpa batas kontraktual.
3. **Dynamic Link Overhead:** Penggunaan 84 Dynamic Frameworks independen menyebabkan waktu startup aplikasi (*cold launch time*) menjadi **4.8 detik** pada perangkat iPhone generasi lama, melanggar batas regulasi SLA (< 2 detik).

#### Solusi Rekayasa
1. **Migrasi Modularisasi Terbalik Menggunakan Tuist & SPM:**
   - Basis kode dipecah menjadi 4 layer vertikal: `App`, `Features`, `Core Domain`, dan `Foundation Base`.
   - Menerapkan pola `FeatureInterface` + `FeatureImplementation`.
2. **Konversi ke Static Binaries dengan Dynamic Relink Optimization:**
   - Seluruh modul fitur dikonversi menjadi Static Libraries (`.a`).
   - Modul inti pihak ketiga yang besar dikompilasi menggunakan format XCFramework terenkapsulasi secara statis.
3. **Penyusunan Deep-Link Router & Dependency Injection Terpusat:**
   - Seluruh interaksi antar-modul wajib melewati *Uniform Resource Coordinator* (URC). Modul `Investment` tidak lagi mengimpor implementasi `PaymentCore`, melainkan hanya memanggil skema `AppRouter.shared.route(to: "bank://payment/checkout?source=investment")`.

#### Metrik Keberhasilan
- **Waktu Kompilasi CI:** Turun dari 42 menit menjadi **7.5 menit** (menggunakan SPM/Tuist remote caching terdistribusi).
- **Cold Launch Time:** Berkurang dari 4.8 detik menjadi **1.1 detik** (eliminasi beban dynamic loader `dyld`).
- **Regression Rate:** Turun hingga **64%** pada siklus rilis kuartal pertama pasca refactoring.

---

### 9. Trade-offs

| Aspek | Monolit Terpusat | Modular Multi-Target (Interface/Impl) |
| :--- | :--- | :--- |
| **Kompleksitas Tooling** | **Rendah:** Cukup konfigurasi standar Xcode target tunggal. | **Sangat Tinggi:** Memerlukan deklarasi SPM ganda, Tuist/Bazel manifests, dan audit dependensi berkala. |
| **Overhead Kode Awal** | **Minimal:** Langsung menulis view dan business logic. | **Tinggi:** Harus membuat Interface Protocol, Mock, DTO, dan Factory Resolver untuk setiap fitur. |
| **Binary Size (IPA)** | **Lebih Ramping (Secara Baku):** Tidak ada metadata interface ekstra atau overhead boundary package. | **Sedikit Meningkat (3-8%):** Adanya redundansi simbol antarmuka dan metadata dynamic linker jika konfigurasi salah. |
| **Skalabilitas Organisasi** | **Buruk:** Bottleneck pada file project dan regression merge. Skala terhenti di ~15-20 insinyur. | **Sangat Baik:** Mampu mengakomodasi ratusan developer dengan kepemilikan modul (*Code Ownership*) independen. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Circular Dependency Antar Modul
- **Gejala:** Error kompilasi LLVM: `Circular dependency between targets 'FeatureA' and 'FeatureB'`.
- **Penyebab:** Modul `FeatureA` mengimpor `FeatureB`, lalu ada fungsi di `FeatureB` yang membutuhkan class dari `FeatureA`.
- **Solusi:** Ekstraksi komponen bersama atau protokol komunikasi ke dalam `FeatureCommonInterface` atau `FeatureSharedEntities`. Tidak boleh ada relasi siklik pada arsitektur Directed Acyclic Graph (DAG).

#### 10.2 Capturing `@MainActor` Context pada Concurrency Boundaries
- **Gejala:** State mutasi berjalan di background thread secara sporadis; Xcode Thread Sanitizer melempar warning: `Data race detected at Swift runtime`.
- **Penyebab:** Pemanggilan callback closures dari repository background thread yang lupa dianotasi `@Sendable` atau tanpa dispatch ke `@MainActor`.
- **Solusi:** Pastikan seluruh `ViewModel` dideklarasikan dengan anotasi `@MainActor`, dan gunakan Task terstruktur:
  ```swift
  // Benar: Mempertahankan main actor execution context
  @MainActor
  func updateUI() {
      Task {
          let data = try await backgroundWorker.fetch()
          self.state.data = data // Terjamin aman di Main Thread
      }
  }
  ```

#### 10.3 Dynamic Framework Proliferation (Launch Time Slowness)
- **Gejala:** Aplikasi membutuhkan waktu >3 detik hanya untuk mencapai frame pertama `didFinishLaunchingWithOptions`.
- **Penyebab:** Membagi proyek menjadi 50+ dynamic framework modules, menyebabkan `dyld` memakan CPU time tinggi untuk *rebinding* dan *fixup*.
- **Solusi:** Ubah package type pada SPM `Package.swift`:
  ```swift
  // Ganti: type: .dynamic
  // Menjadi tipe default (static) atau omit parameter 'type'
  .library(
      name: "FeatureAccount",
      targets: ["FeatureAccount"]
  )
  ```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Strict Interface Segregation:** Tidak ada modul `FeatureImplementation` yang mengimpor modul `FeatureImplementation` lain secara langsung. Komunikasi hanya via `Interface`.
2. [ ] **Explicit Dependency Injection:** Menghindari akses state global (`Singletons`) tanpa protokol. Gunakan Inversion of Control container.
3. [ ] **Concurrency Strict Checking:** Aktifkan flag `SWIFT_STRICT_CONCURRENCY=complete` pada seluruh build settings modul.
4. [ ] **Thread Safe Value Types:** Gunakan `Sendable` `Struct` untuk mendefinisikan state dan event lintas batas modular.
5. [ ] **Leak & Allocations Verification:** Lakukan automated test menggunakan `XCTest` dengan validasi pelepasan memory (assert reference count nil setelah dismiss).
6. [ ] **Mergeable Libraries (Xcode 15+):** Gunakan setting `MERGED_BINARY_TYPE` untuk static libraries yang membutuhkan fleksibilitas dynamic framework tanpa penalti launch time.
7. [ ] **Explicit SPM Targets Definition:** Definisikan modul secara deklaratif, hindari *wildcard target directory* yang memperlambat resolusi SPM file tracking.

---

### 12. Hands-on Practice

Struktur direktori kerja praktikum:
```text
hands-on/m02/
├── Core/
│   └── NetworkKit/
│       ├── Package.swift
│       └── Sources/
├── Features/
│   ├── Profile/
│   │   ├── ProfileInterface/
│   │   │   ├── Package.swift
│   │   │   └── Sources/ProfileInterface/ProfileContracts.swift
│   │   └── ProfileImplementation/
│   │       ├── Package.swift
│   │       └── Sources/ProfileImplementation/ProfileViewModel.swift
└── EnterpriseApp/
    └── EnterpriseApp/CompositionRoot.swift
```

#### Langkah 1: Buat Modul Interface
Buat file `hands-on/m02/Features/Profile/ProfileInterface/Sources/ProfileInterface/ProfileContracts.swift`:
```swift
import Foundation

public struct UserEntity: Sendable, Equatable, Identifiable {
    public let id: String
    public let name: String
    
    public init(id: String, name: String) {
        self.id = id
        self.name = name
    }
}

public protocol ProfileServiceProtocol: Sendable {
    func getUser(by id: String) async throws -> UserEntity
}

public protocol ProfileRouting: Sendable {
    @MainActor func routeToSettings()
}
```

#### Langkah 2: Buat Modul Implementasi
Buat file `hands-on/m02/Features/Profile/ProfileImplementation/Sources/ProfileImplementation/ProfileViewModel.swift`:
```swift
import SwiftUI
import ProfileInterface

@MainActor
public final class ProfileProductionViewModel: ObservableObject {
    @Published public private(set) var user: UserEntity?
    @Published public private(set) var isBusy: Bool = false
    
    private let service: ProfileServiceProtocol
    private let router: ProfileRouting
    
    public init(service: ProfileServiceProtocol, router: ProfileRouting) {
        self.service = service
        self.router = router
    }
    
    public func loadData(userId: String) {
        isBusy = true
        Task {
            do {
                self.user = try await service.getUser(by: userId)
            } catch {
                self.user = nil
            }
            self.isBusy = false
        }
    }
    
    public func openSettings() {
        router.routeToSettings()
    }
}
```

#### Langkah 3: Setup Composition Root di Aplikasi Utama
Buat file `hands-on/m02/EnterpriseApp/EnterpriseApp/CompositionRoot.swift`:
```swift
import SwiftUI
import ProfileInterface
import ProfileImplementation

// Mock Service untuk demo runtime
final class RemoteProfileService: ProfileServiceProtocol {
    func getUser(by id: String) async throws -> UserEntity {
        try await Task.sleep(nanoseconds: 500_000_000)
        return UserEntity(id: id, name: "Siti Rahmawati (Senior Engineer)")
    }
}

// Router Implementation
final class AppProfileCoordinator: ProfileRouting {
    @MainActor
    func routeToSettings() {
        print("LOG: Berhasil navigasi ke Settings Screen secara decoupled.")
    }
}

@main
struct EnterpriseAppDemo: App {
    var body: some Scene {
        WindowGroup {
            let service = RemoteProfileService()
            let router = AppProfileCoordinator()
            let viewModel = ProfileProductionViewModel(service: service, router: router)
            
            VStack {
                if viewModel.isBusy {
                    ProgressView()
                } else if let user = viewModel.user {
                    Text("Halo, \(user.name)")
                    Button("Pengaturan") {
                        viewModel.openSettings()
                    }
                }
            }
            .task {
                viewModel.loadData(userId: "usr_102")
            }
        }
    }
}
```

---

### 13. Exercise

#### Level Easy
Buat protocol `AnalyticsTrackerInterface` yang memiliki method `logEvent(name: String, parameters: [String: Sendable])`. Implementasikan mock analytics tracker di layer unit testing tanpa mengimpor framework analitik asli (seperti Firebase/Mixpanel).
- **Kriteria Keberhasilan:** Unit test dapat memvalidasi apakah event terpanggil tanpa melibatkan third-party framework runtime.

#### Level Medium
Konstruksikan modul `AuthenticationInterface` dan `AuthenticationImplementation`. Buat token-refreshing logic via Swift `actor` yang menangani *concurrent refresh requests* (jika ada 3 request jaringan bersamaan saat token expired, hanya 1 request refresh token yang berjalan, 2 request lainnya menunggu hasil token baru yang sama).
- **Kriteria Keberhasilan:** Actor mencegah data race dan API spam pada endpoint refresh token.

#### Level Hard
Rancang dan implementasikan Router Terdistribusi berbasis Deep Link URI Parsing (`myapp://feature/subfeature?param=value`). Router harus mendukung registrasi dinamis menggunakan *Type-Erased Handlers* dari modul interface yang berbeda tanpa saling mereferensikan modul implementasi secara statis.
- **Kriteria Keberhasilan:** Modul checkout dapat menavigasi pengguna ke halaman profil akun lain melalui *deep link parser engine* yang terisolasi dari kedua modul tersebut.

---

### 14. Challenge

**Skenario Sistem:**
Anda adalah Principal iOS Architect di unicorn e-commerce global. Aplikasi Anda mengadopsi integrasi dinamis Server-Driven UI (SDUI) dengan 40+ modul fungsional. 

**Tantangan Arsitektur:**
1. Rancang modul **Core Navigation & Routing Mesh Engine** yang mampu:
   - Menangani deep link resolusi dinamis dengan payload payload parameter JSON kompleks.
   - Mengautentikasi *state session user* secara asinkron sebelum view controller tujuan diinisialisasi (misal: jika sesi kedaluwarsa saat navigasi ke `/checkout`, rute dialihkan otomatis ke `/auth/login`, lalu melakukan *resume* otomatis ke `/checkout` setelah autentikasi sukses).
   - Mengalokasikan dependency tree modul tujuan secara *lazy* (hanya dimuat ke memori saat rute dituju).
2. Tulis implementasi lengkap dari **State Restorer & Navigation Mesh Coordinator** ini dalam bahasa Swift modern dengan mode koncurrency penuh (`Swift 6 Strict Concurrency Safe`), bebas dari compiler warnings data races, serta bebas memory leaks. Wajib menyertakan skema representasi graph tanpa menggunakan UI visual (headless router harness).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa memisahkan sebuah fitur menjadi modul `Interface` dan `Implementation` dapat mempercepat build time aplikasi secara dramatis?
2. Apa dampak memuat terlalu banyak (misal: > 100) dynamic frameworks terhadap performa aplikasi iOS saat fase launch?
3. Sebutkan perbedaan perilaku referensi memory antara `weak` dan `unowned` pada implementasi closure Coordinator/Router!
4. Mengapa kita harus memberi anotasi `@MainActor` pada class `ObservableObject` atau `ViewModel` dalam arsitektur berbasis UDF modern?
5. Apa bahaya penggunaan Singleton global tanpa abstraksi protocol pada arsitektur skala enterprise?

#### B. Pertanyaan Intermediate
6. Bagaimana cara mencegah *re-compilation cascade* pada SPM package dependency tree saat struktur data model internal mengalami pembaruan?
7. Apa peran anotasi `@Sendable` pada Swift Concurrency ketika kita melemparkan closures antar batas modul arsitektur?
8. Mengapa `Static Libraries` dapat menyebabkan error kompilasi *duplicate symbols* pada linker stage, dan bagaimana cara memitigasinya?
9. Jelaskan konsep *Micro-Apps* dalam pengembangan iOS enterprise dan bagaimana hal ini meningkatkan produktivitas tim pengembang!
10. Bagaimana cara mendeteksi circular dependencies antar target SPM sebelum kode dinaikkan ke branch utama (CI pipeline)?

#### C. Skenario Kasus Produksi
11. **Kasus 1:** Tim Anda mendapati bahwa unit test berjalan sangat lambat pada CI pipeline karena modul `FeatureAuth` mengimpor `CoreNetworking` yang menginisialisasi framework network pihak ketiga asli. Bagaimana Anda merestrukturisasi target modul untuk mengisolasi unit testing?
12. **Kasus 2:** Sebuah class `StoreCoordinator` yang mengelola alur navigasi dari Cart ke Checkout mengalami memory leak. Halaman Cart tetap tersimpan di memori meskipun navigasi telah kembali ke Home root view. Berikan root-cause analysis dan perbaikan kodenya.
13. **Kasus 3:** Pada saat mengaktifkan compiler flag `SWIFT_STRICT_CONCURRENCY=complete`, muncul puluhan warning: `Capture of 'self' with non-sendable type 'MyViewModel' in a `@Sendable` closure`. Langkah arsitektural apa yang harus diambil untuk menyelesaikan error ini secara sistemik tanpa menggunakan `@unchecked Sendable`?

---

#### Kunci Jawaban & Pembahasan Quiz

##### A. Basic
1. **Pembahasan:** Perubahan implementasi internal pada modul `Implementation` tidak mengubah signature modul `Interface`. Akibatnya, modul lain yang hanya bergantung pada `Interface` tidak perlu dikompilasi ulang oleh compiler Clang/Swiftc (*cache hit* tetap valid).
2. **Pembahasan:** Dynamic loader (`dyld`) membutuhkan waktu kompilasi startup untuk membaca mach-O header, memverifikasi cryptographic code signature, mengalokasikan virtual memory, dan melakukan pointer rebinding (*fixups*). Hal ini menyebabkan peningkatan tajam pada *pre-main launch time*.
3. **Pembahasan:** `weak` mengubah pointer menjadi zeroing weak reference (berubah menjadi `nil` otomatis saat objek dihancurkan; bertipe optional). `unowned` mengasumsikan objek target selalu ada dalam memori (non-optional); jika objek target deallocated dan diakses, aplikasi akan langsung *crash* (`EXC_BAD_ACCESS`).
4. **Pembahasan:** UI Framework (SwiftUI/UIKit) hanya boleh dimutasi dan diakses secara eksklusif dari Thread Utama (Main Thread). `@MainActor` memastikan compiler Swift secara statis menjamin mutasi properti `@Published` selalu terjadi di Main RunLoop.
5. **Pembahasan:** Singleton langsung menciptakan *tight coupling*, menyulitkan mocking/stubbing pada unit testing, berpotensi memicu race conditions jika tidak diisolasi oleh aktor, dan menghalangi pemisahan fungsionalitas modular murni.

##### B. Intermediate
6. **Pembahasan:** Definisikan entitas data sebagai protokol atau batasi eksposure model public pada `Interface`. Gunakan DTO mapper internal di lapisan `Implementation` agar modifikasi field internal tidak memicu invalidasi biner pada consumer module.
7. **Pembahasan:** `@Sendable` memberi sinyal ke compiler bahwa closure tersebut aman ditransfer melintasi batas domain konkurensi (thread boundaries) tanpa membawa mutable captured state yang dapat menimbulkan data races.
8. **Pembahasan:** Jika sebuah static library di-link ke dalam dua target dynamic framework yang berbeda dan keduanya dimuat ke dalam executable yang sama, linker mendapati ada dua definisi simbol yang identik. Solusinya adalah mengubah kedua modul consumer menjadi static, atau mengemas dependency shared sebagai static framework yang di-link eksklusif pada executable root target saja.
9. **Pembahasan:** *Micro-App* adalah target runnable application independen yang ringan, hanya mengonsumsi satu fitur tertentu (misal: `FeatureCheckoutMicroApp`) dengan Composition Root minimalis. Pengembang dapat menguji fitur secara langsung tanpa perlu melakukan build pada keseluruhan aplikasi monolitik yang masif.
10. **Pembahasan:** Menggunakan automated build-graph analyzer via CLI (seperti `tuist graph`, `swift package dump-package`, atau custom script Graphviz/Python) di CI gate. Linker Clang/SPM akan gagal mengeksekusi graph jika ditemukan dependency cycles (DAG must be acyclic).

##### C. Skenario Kasus Produksi
11. **Pembahasan Kasus 1:**
    - Pecah `CoreNetworking` menjadi `CoreNetworkingInterface` (berisi protokol request handler) dan `CoreNetworking` (implementasi nyata dengan framework pihak ketiga).
    - Buat modul `CoreNetworkingTestDoubles` yang mengimplementasikan mock in-memory network client.
    - Pada `FeatureAuthTests`, arahkan dependensi ke `CoreNetworkingInterface` dan injeksikan mock dari `CoreNetworkingTestDoubles`. Modul pihak ketiga tidak akan ikut dikompilasi atau di-load selama test run.
12. **Pembahasan Kasus 2:**
    - *Root-cause:* Terjadi retain cycle di mana `StoreCoordinator` memegang instance `CartViewController`, dan callback handler (atau delegasi) di dalam `CartViewController` memegang referensi kuat (*strong reference*) kembali ke `StoreCoordinator`. Saat pop view, view controller tidak dapat di-deallocate oleh ARC.
    - *Solusi:* Ubah delegasi menjadi `weak var coordinator: StoreCoordinatorDelegate?` atau gunakan `[weak self]` pada navigation closure bindings. Pastikan view controller melepaskan references coordinator saat `didMove(toParent: nil)`.
13. **Pembahasan Kasus 3:**
    - *Solusi Sistemik:* Tandai class ViewModel dengan atribut `@MainActor`. Objek yang diisolasi dengan `@MainActor` secara implisit memenuhi kriteria safe concurrency saat diakses dari Main Actor context. Jika closure asynchronous tersebut dijalankan dari background task context, ubah closure agar menerima isolated parameter atau gunakan explicit `await` invocation untuk menyeberangi actor boundary secara aman.

---

### 16. Summary

Arsitektur iOS enterprise berskala besar menuntut disiplin struktural yang melampaui pola modularisasi biasa. Pemisahan yang ketat antara **Interface**, **Implementation**, dan **Testing Doubles** adalah fondasi deterministik untuk menjaga performa kompilasi lokal maupun CI server. 

Dengan menggabungkan pola **Unidirectional Data Flow (UDF)**, sistem perutean navigasi yang decoupled via **Coordinator/Router**, serta penegakan **Swift Concurrency Strict Mode**, sistem aplikasi dapat tumbuh hingga jutaan baris kode dengan ratusan kontributor insinyur, tanpa mengorbankan stabilitas, performa runtime, kecepatan peluncuran aplikasi (*launch time*), maupun kemudahan pengujian (*testability*).